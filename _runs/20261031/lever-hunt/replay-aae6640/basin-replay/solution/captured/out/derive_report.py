#!/usr/bin/env python3
"""Balance the closed storage basins of a season extract and write its reports.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib

OFF_VALUES = tuple(range(-95, 100, 5))
SENSES = ("fwd", "rev", "nil")
B_SENSE = {"1": "rev", "0": "fwd", "0.5": "nil"}
C_SENSE = {"from": "rev", "to": "fwd", "neither": "nil"}
FROM_POINTS = {"rev": 2, "fwd": 0, "nil": 1}
POINT_TEXT = {0: "0", 1: "1/2", 2: "1"}
WML = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SML = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKGREL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CML = "{urn:basin-authority:catchments}"
SCHEME_HEAD = ("scheme", "class", "segment")
PARAM_HEAD = ("basin", "damping_percent", "patience", "round_budget")
RATE_HEAD = "segment revised_on rate_milli"


class ExtractError(Exception):
    """An input breaks a rule the documents state for it."""


def rnd_div(num, den):
    """num/den to the nearest integer, a half going away from zero."""
    if den < 0:
        num, den = -num, -den
    whole, rest = divmod(abs(num), den)
    if 2 * rest >= den:
        whole += 1
    return whole if num >= 0 else -whole


def trunc_div(num, den):
    """num/den with the fraction dropped."""
    if den < 0:
        num, den = -num, -den
    whole = abs(num) // den
    return whole if num >= 0 else -whole


def stn_key(stn):
    """The register order key of a station code."""
    return int(stn[3:])


def table_rows(path, delimiter, header):
    """The rows of a delimited export with the given header, as dicts."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames != list(header):
            raise ExtractError("%s: unexpected header" % os.path.basename(path))
        rows = [dict(row) for row in reader]
    for row in rows:
        for name in header:
            if row[name] is None:
                raise ExtractError("%s: short record" % os.path.basename(path))
    return rows


def load_season(path):
    """The season label and the revision cutoff of basin_cfg.ini."""
    label = None
    cutoff = None
    section = None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith((";", "#")):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                continue
            key, _, value = line.partition("=")
            if section == "season" and key.strip() == "label":
                label = value.strip()
            if section == "season" and key.strip() == "revision_cutoff":
                cutoff = int(value.strip())
    if label is None or cutoff is None:
        raise ExtractError("basin_cfg.ini: season label or revision cutoff missing")
    return label, cutoff


def season_start(label):
    """The first day of the season the label names."""
    match = re.fullmatch(r"(\d{4})-S([1-4])", label)
    if match is None:
        raise ExtractError("basin_cfg.ini: season label %r" % label)
    return datetime.date(int(match.group(1)), 3 * int(match.group(2)) - 2, 1)


def load_register(path):
    """The reservoirs of the register authority, in register order."""
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        rows = list(con.execute("SELECT stn, station_name, catchment FROM station"))
    finally:
        con.close()
    seen = set()
    out = []
    for stn, name, catchment in rows:
        if stn in seen:
            raise ExtractError("station %s occurs twice in the register" % stn)
        seen.add(stn)
        out.append({"stn": stn, "station_name": name, "catchment": catchment})
    out.sort(key=lambda row: stn_key(row["stn"]))
    return out


def load_basin_map(path):
    """The basin of every catchment of bs_map.xml."""
    root = ET.parse(path).getroot()
    out = {}
    for elem in root.iter(CML + "catchment"):
        code = elem.get("code")
        basin = elem.find(CML + "basin")
        if code is None or basin is None or not (basin.text or "").strip():
            raise ExtractError("bs_map.xml: incomplete catchment element")
        out[code] = basin.text.strip()
    if not out:
        raise ExtractError("bs_map.xml: no catchment")
    return out


def mt_u8(blob, end, pos):
    """One byte of the meter file."""
    if pos + 1 > end:
        raise ExtractError("ob_s3.bin: a record runs past the last record")
    return blob[pos], pos + 1


def mt_varint(blob, end, pos):
    """The signed variable-length integer at pos."""
    raw = 0
    shift = 0
    while True:
        byte, pos = mt_u8(blob, end, pos)
        raw |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            break
    return (raw // 2 if raw % 2 == 0 else -((raw + 1) // 2)), pos


def mt_gauge(blob, end, pos, reference, gdict):
    """The gauge number at pos, in literal or reference form."""
    if reference:
        index, pos = mt_u8(blob, end, pos)
        if index >= len(gdict):
            raise ExtractError("ob_s3.bin: reference to dictionary position %d" % index)
        return gdict[index], pos
    high, pos = mt_u8(blob, end, pos)
    low, pos = mt_u8(blob, end, pos)
    number = high * 256 + low
    if number not in gdict:
        gdict.append(number)
    return number, pos


def parse_meter(path):
    """The records of the meter file, in file order."""
    with open(path, "rb") as handle:
        blob = handle.read()
    if len(blob) < 18:
        raise ExtractError("ob_s3.bin: too short")
    if blob[:4] != b"OBS3":
        raise ExtractError("ob_s3.bin: magic")
    if blob[4] != 1:
        raise ExtractError("ob_s3.bin: version")
    end = len(blob) - 4
    if int.from_bytes(blob[end:], "big") != zlib.crc32(blob[4:end]):
        raise ExtractError("ob_s3.bin: checksum")
    pos = 14
    gdict = []
    running = 0
    records = []
    for _ in range(int.from_bytes(blob[12:14], "big")):
        selector, pos = mt_u8(blob, end, pos)
        kind = selector >> 6
        if kind == 3:
            raise ExtractError("ob_s3.bin: record kind 3")
        gauge, pos = mt_gauge(blob, end, pos, (selector >> 5) & 1, gdict)
        if kind == 2:
            other, pos = mt_gauge(blob, end, pos, (selector >> 3) & 1, gdict)
            records.append(("replacement", gauge, other))
            continue
        if (selector >> 3) & 1:
            raise ExtractError("ob_s3.bin: reading or correction with the second gauge bit set")
        written, pos = mt_varint(blob, end, pos)
        running = written if not (selector >> 4) & 1 else running + written
        if kind == 0:
            records.append(("reading", gauge, running))
        else:
            day, pos = mt_u8(blob, end, pos)
            records.append(("correction", gauge, running, day))
    if pos != end:
        raise ExtractError("ob_s3.bin: the records do not end at the checksum")
    return records


def retired_gauges(records):
    """The gauge number that replaced every retired gauge number."""
    out = {}
    for record in records:
        if record[0] == "replacement":
            out[record[1]] = record[2]
    return out


def current_gauge(retired, gauge):
    """The gauge number a retired gauge number was replaced by."""
    seen = set()
    while gauge in retired:
        if gauge in seen:
            raise ExtractError("ob_s3.bin: replacement cycle at gauge %d" % gauge)
        seen.add(gauge)
        gauge = retired[gauge]
    return gauge


def meter_readings(records):
    """The meter reading of every gauge number that has a reading record."""
    out = {}
    for record in records:
        if record[0] == "reading":
            out[record[1]] = record[2]
    return out


def meter_corrections(records, survey_day):
    """The corrected reading of every gauge number a correction applies to."""
    retired = retired_gauges(records)
    best = {}
    for order, record in enumerate(records):
        if record[0] != "correction" or record[3] > survey_day:
            continue
        gauge = current_gauge(retired, record[1])
        key = (record[3], order)
        if gauge not in best or key > best[gauge][0]:
            best[gauge] = (key, record[2])
    return {gauge: value for gauge, (_, value) in best.items()}


def load_crosswalk(path):
    """The current gauge number of every station code."""
    out = {}
    for row in table_rows(path, ",", ("gauge_no", "stn")):
        out[row["stn"]] = row["gauge_no"]
    return out


def load_survey(path, station_codes):
    """The survey rows and the survey date."""
    rows = table_rows(path, ",", ("reach", "surveyed_on", "stations", "total_ml"))
    if not rows:
        raise ExtractError("sv_survey.csv: no row")
    dates = {row["surveyed_on"] for row in rows}
    if len(dates) != 1:
        raise ExtractError("sv_survey.csv: the rows carry more than one date")
    out = []
    for row in rows:
        stations = row["stations"].split(";")
        for stn in stations:
            if stn not in station_codes:
                raise ExtractError("sv_survey.csv: station %s is not in the register" % stn)
        out.append((stations, int(row["total_ml"])))
    return out, datetime.date.fromisoformat(dates.pop())


def survey_data(rows, readings, catch_of):
    """Per survey row, the reading sum, the catchment counts and the total."""
    data = []
    for stations, total in rows:
        counts = {}
        for stn in stations:
            counts[catch_of[stn]] = counts.get(catch_of[stn], 0) + 1
        data.append((sum(readings[stn] for stn in stations), counts, total))
    return data


def offset_order(data, catchments):
    """The catchments, ordered so that survey rows complete early."""
    order = []
    left = set(catchments)
    while left:
        choice = None
        for _, counts, _ in data:
            open_set = set(counts) & left
            if open_set and (choice is None or len(open_set) < len(choice)):
                choice = open_set
        if choice is None:
            choice = {min(left)}
        order.extend(sorted(choice))
        left -= choice
    return order


def offset_bounds(data, order):
    """Per prefix length and row, the least and greatest contribution left."""
    least = []
    most = []
    for step in range(len(order) + 1):
        done = set(order[:step])
        low = []
        high = []
        for _, counts, _ in data:
            left = sum(num for code, num in counts.items() if code not in done)
            low.append(left * OFF_VALUES[0])
            high.append(left * OFF_VALUES[-1])
        least.append(low)
        most.append(high)
    return least, most


def solve_offsets(data, catchments):
    """The one datum offset assignment under which every survey row holds."""
    order = offset_order(data, catchments)
    least, most = offset_bounds(data, order)
    touched = [[row for row, item in enumerate(data) if code in item[1]] for code in order]
    found = []
    chosen = {}

    def walk(step, sums):
        if step == len(order):
            for row, item in enumerate(data):
                if sums[row] // 10 * 10 != item[2]:
                    return
            found.append(dict(chosen))
            return
        code = order[step]
        for value in OFF_VALUES:
            nxt = list(sums)
            good = True
            for row in touched[step]:
                nxt[row] += data[row][1][code] * value
                total = data[row][2]
                if not total <= nxt[row] + most[step + 1][row]:
                    good = False
                    break
                if not nxt[row] + least[step + 1][row] <= total + 9:
                    good = False
                    break
            if good:
                chosen[code] = value
                walk(step + 1, nxt)
                if len(found) > 1:
                    return

    walk(0, [item[0] for item in data])
    if not found:
        raise ExtractError("no datum offset assignment makes every survey row hold")
    if len(found) > 1:
        raise ExtractError("more than one datum offset assignment makes every survey row hold")
    return found[0]


def load_gaugings(data_dir):
    """The gauging records of the three exports, in file order per export."""
    out = []
    head_a = ("gauging_id", "licence", "from_stn", "to_stn", "sense")
    for row in table_rows(os.path.join(data_dir, "gx_a.csv"), ",", head_a):
        if row["sense"] not in SENSES:
            raise ExtractError("gx_a.csv: sense %r" % row["sense"])
        out.append({"gauging_id": row["gauging_id"], "licence": row["licence"],
                    "from_stn": row["from_stn"], "to_stn": row["to_stn"],
                    "sense": row["sense"]})
    head_b = ("gid", "lic", "upper", "lower", "drawn_upper")
    for row in table_rows(os.path.join(data_dir, "gx_b.tsv"), "\t", head_b):
        if row["drawn_upper"] not in B_SENSE:
            raise ExtractError("gx_b.tsv: drawn_upper %r" % row["drawn_upper"])
        out.append({"gauging_id": row["gid"], "licence": row["lic"],
                    "from_stn": row["upper"], "to_stn": row["lower"],
                    "sense": B_SENSE[row["drawn_upper"]]})
    out.extend(load_contractor_gaugings(os.path.join(data_dir, "gx_c.jsonl")))
    seen = set()
    for gauging in out:
        if gauging["gauging_id"] in seen:
            raise ExtractError("gauging %s is recorded twice" % gauging["gauging_id"])
        seen.add(gauging["gauging_id"])
    return out


def load_contractor_gaugings(path):
    """The gauging records of the contractor feed."""
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            ends = record["ends"]
            if len(ends) != 2:
                raise ExtractError("gx_c.jsonl: %s has %d ends"
                                   % (record["id"], len(ends)))
            if record["drawn_by"] not in C_SENSE:
                raise ExtractError("gx_c.jsonl: drawn_by %r" % record["drawn_by"])
            out.append({"gauging_id": record["id"], "licence": record["licence"],
                        "from_stn": ends[0], "to_stn": ends[1],
                        "sense": C_SENSE[record["drawn_by"]]})
    return out


def load_revisions(path):
    """The revision lines of the revision log."""
    out = []
    seen = set()
    for row in table_rows(path, "|", ("seq", "gauging_id", "action", "value")):
        seq = int(row["seq"])
        if seq < 1:
            raise ExtractError("rv_log.psv: seq %d is not positive" % seq)
        if seq in seen:
            raise ExtractError("rv_log.psv: seq %d occurs twice" % seq)
        seen.add(seq)
        if row["action"] == "sense":
            if row["value"] not in SENSES:
                raise ExtractError("rv_log.psv: sense %r" % row["value"])
        elif row["action"] == "void":
            if row["value"] != "":
                raise ExtractError("rv_log.psv: a void revision carries a value")
        else:
            raise ExtractError("rv_log.psv: action %r" % row["action"])
        out.append({"seq": seq, "gauging_id": row["gauging_id"],
                    "action": row["action"], "value": row["value"]})
    return out


def apply_revisions(gaugings, revisions, cutoff):
    """The net gaugings and the input-quality counts of the revision log."""
    ids = {gauging["gauging_id"] for gauging in gaugings}
    decide = {}
    for revision in revisions:
        if revision["seq"] > cutoff:
            continue
        gid = revision["gauging_id"]
        if gid not in decide or decide[gid]["seq"] < revision["seq"]:
            decide[gid] = revision
    net = []
    voided = 0
    for gauging in gaugings:
        revision = decide.get(gauging["gauging_id"])
        if revision is not None and revision["action"] == "void":
            voided += 1
            continue
        state = dict(gauging)
        if revision is not None:
            state["sense"] = revision["value"]
        net.append(state)
    counts = {
        "gaugings_read": len(gaugings),
        "revisions_applied": len([r for r in revisions
                                  if r["seq"] <= cutoff and r["gauging_id"] in ids]),
        "revisions_after_cutoff": len([r for r in revisions if r["seq"] > cutoff]),
        "revisions_unmatched": len([r for r in revisions
                                    if r["seq"] <= cutoff and r["gauging_id"] not in ids]),
        "gaugings_voided": voided}
    return net, counts


def zip_part(archive, name):
    """One part of an Office Open XML package."""
    try:
        return archive.read(name)
    except KeyError:
        raise ExtractError("%s: part %s is missing"
                           % (os.path.basename(archive.filename), name))


def sheet_cell_text(cell, shared):
    """The text of a worksheet cell."""
    kind = cell.get("t")
    if kind == "inlineStr":
        node = cell.find(SML + "is")
        if node is None:
            return ""
        return "".join(item.text or "" for item in node.iter(SML + "t"))
    node = cell.find(SML + "v")
    raw = "" if node is None or node.text is None else node.text
    return shared[int(raw)] if kind == "s" else raw


def shared_strings(archive):
    """The shared strings of a workbook."""
    out = []
    if "xl/sharedStrings.xml" in archive.namelist():
        strings = ET.fromstring(zip_part(archive, "xl/sharedStrings.xml"))
        for item in strings.iter(SML + "si"):
            out.append("".join(node.text or "" for node in item.iter(SML + "t")))
    return out


def sheet_part_name(archive, wanted):
    """The package part of the named worksheet."""
    book = ET.fromstring(zip_part(archive, "xl/workbook.xml"))
    rels = ET.fromstring(zip_part(archive, "xl/_rels/workbook.xml.rels"))
    target = {rel.get("Id"): rel.get("Target") for rel in rels.iter(PKGREL + "Relationship")}
    for sheet in book.iter(SML + "sheet"):
        if sheet.get("name") == wanted:
            path = target[sheet.get(RELNS + "id")]
            return path[1:] if path.startswith("/") else "xl/" + path
    raise ExtractError("tab_h3.xlsx: sheet %s is missing" % wanted)


def load_offset_table(path):
    """The head offset of every draw share, from the offset sheet."""
    with zipfile.ZipFile(path) as archive:
        shared = shared_strings(archive)
        sheet = ET.fromstring(zip_part(archive, sheet_part_name(archive, "offset")))
    out = {}
    for row in sheet.iter(SML + "row"):
        if row.get("r") == "1":
            continue
        cells = list(row.iter(SML + "c"))
        if len(cells) < 2:
            raise ExtractError("tab_h3.xlsx: short row in sheet offset")
        out[sheet_cell_text(cells[0], shared)] = int(sheet_cell_text(cells[1], shared))
    if not out:
        raise ExtractError("tab_h3.xlsx: sheet offset holds no row")
    return out


def wml_text(elem):
    """The text of a WordprocessingML element, other namespaces unread."""
    parts = []
    for child in elem:
        if child.tag == WML + "t":
            parts.append(child.text or "")
        elif child.tag.startswith(WML):
            parts.append(wml_text(child))
    return "".join(parts)


def wml_tables(elem):
    """The tables of a WordprocessingML element, in document order."""
    out = []
    for child in elem:
        if child.tag == WML + "tbl":
            out.append(child)
        elif child.tag.startswith(WML):
            out.extend(wml_tables(child))
    return out


def wml_grid(table):
    """A table as a list of rows of cell texts."""
    rows = []
    for row in table:
        if row.tag == WML + "tr":
            rows.append([wml_text(cell) for cell in row if cell.tag == WML + "tc"])
    return rows


def load_docx(path):
    """The scheme segments and the basin operating parameters."""
    with zipfile.ZipFile(path) as archive:
        body = ET.fromstring(zip_part(archive, "word/document.xml"))
    schemes = []
    params = {}
    for table in wml_tables(body):
        grid = wml_grid(table)
        if not grid:
            continue
        head = tuple(grid[0])
        if head == SCHEME_HEAD:
            for row in grid[1:]:
                schemes.append({"scheme": row[0], "class": row[1], "segment": row[2]})
        elif head == PARAM_HEAD:
            for row in grid[1:]:
                params[row[0]] = {"damping_percent": int(row[1]), "patience": int(row[2]),
                                  "round_budget": int(row[3])}
    if not schemes:
        raise ExtractError("sc_k2.docx: the scheme table is missing")
    if not params:
        raise ExtractError("sc_k2.docx: the basin operating parameters are missing")
    for basin, row in params.items():
        if not 1 <= row["damping_percent"] <= 100 or row["patience"] < 1:
            raise ExtractError("sc_k2.docx: operating parameters of basin %s" % basin)
        if row["round_budget"] < 1:
            raise ExtractError("sc_k2.docx: round budget of basin %s" % basin)
    return schemes, params


def pdf_streams(blob):
    """The decoded content streams of a PDF file, in file order."""
    out = []
    for match in re.finditer(rb"(?<!end)stream(?:\r\n|\n|\r)", blob):
        head = blob[max(0, match.start() - 400):match.start()]
        stop = blob.find(b"endstream", match.end())
        if stop < 0:
            raise ExtractError("mt_loss.pdf: unterminated stream")
        body = blob[match.end():stop]
        if body.endswith(b"\r\n"):
            body = body[:-2]
        elif body.endswith(b"\n") or body.endswith(b"\r"):
            body = body[:-1]
        if b"FlateDecode" in head:
            body = zlib.decompress(body)
        out.append(body)
    return out


def pdf_string(body, pos):
    """The literal string of a PDF content stream that starts at pos."""
    escapes = {ord("n"): "\n", ord("r"): "\r", ord("t"): "\t",
               ord("b"): "\b", ord("f"): "\f"}
    text = []
    depth = 1
    pos += 1
    while pos < len(body):
        char = body[pos]
        if char == 0x5C:
            nxt = body[pos + 1]
            if 0x30 <= nxt <= 0x37:
                digits = ""
                pos += 1
                while len(digits) < 3 and pos < len(body) and 0x30 <= body[pos] <= 0x37:
                    digits += chr(body[pos])
                    pos += 1
                text.append(chr(int(digits, 8)))
                continue
            text.append(escapes.get(nxt, chr(nxt)))
            pos += 2
            continue
        if char == 0x28:
            depth += 1
        elif char == 0x29:
            depth -= 1
            if depth == 0:
                return "".join(text), pos + 1
        text.append(chr(char))
        pos += 1
    raise ExtractError("mt_loss.pdf: unterminated string")


def pdf_lines(path):
    """The text lines a PDF page shows, in reading order."""
    with open(path, "rb") as handle:
        blob = handle.read()
    breaks = (b"T*", b"Td", b"TD", b"ET", b"BT", b"'", b'"')
    lines = []
    for body in pdf_streams(blob):
        buffer = []
        pos = 0
        token = b""
        while pos < len(body):
            if body[pos] == 0x28:
                text, pos = pdf_string(body, pos)
                buffer.append(text)
                token = b""
                continue
            char = body[pos:pos + 1]
            pos += 1
            if char.isspace() or char in b"[]":
                if token in breaks and buffer:
                    lines.append("".join(buffer))
                    buffer = []
                token = b""
                continue
            token += char
        if buffer:
            lines.append("".join(buffer))
    return [line for line in lines if line != ""]


def load_loss_rates(path):
    """The rows of the conveyance loss rate schedule."""
    lines = pdf_lines(path)
    if RATE_HEAD not in lines:
        raise ExtractError("mt_loss.pdf: the rate table header is missing")
    out = []
    for line in lines[lines.index(RATE_HEAD) + 1:]:
        fields = line.split(" ")
        if len(fields) != 3 or not fields[2].lstrip("-").isdigit():
            break
        datetime.date.fromisoformat(fields[1])
        out.append({"segment": fields[0], "revised_on": fields[1],
                    "rate_milli": int(fields[2])})
    if not out:
        raise ExtractError("mt_loss.pdf: no rate row")
    return out


def load_licences(path):
    """The licences of the delivery licence register."""
    with open(path, encoding="utf-8") as handle:
        record = json.load(handle)
    out = {}
    for item in record["licences"]:
        if item["licence"] in out:
            raise ExtractError("lc_register.json: licence %s occurs twice" % item["licence"])
        datetime.date.fromisoformat(item["date"])
        out[item["licence"]] = {"licence": item["licence"], "scheme": item["scheme"],
                                "date": item["date"]}
    if not out:
        raise ExtractError("lc_register.json: no licence")
    return out


def rate_in_force(rates, segment, day):
    """The rate in force for a segment on a day."""
    best = None
    for rate in rates:
        if rate["segment"] != segment or rate["revised_on"] >= day:
            continue
        if best is None or rate["revised_on"] > best["revised_on"]:
            best = rate
    if best is None:
        raise ExtractError("no %s loss rate is in force on %s" % (segment, day))
    return best["rate_milli"]


def basin_residuals(state, order, partners, head, index_of):
    """The residual of every reservoir of a basin in a round."""
    out = []
    for place, stn in enumerate(order):
        mates = partners[stn]
        if mates:
            total = sum(state[index_of[mate]] for mate in mates)
            target = rnd_div(total, len(mates)) + head[stn]
        else:
            target = state[place]
        out.append(target - state[place])
    return out


def balance_basin(order, opening, partners, head, params):
    """The exit, round count, balanced storages and damping of a basin."""
    index_of = {stn: place for place, stn in enumerate(order)}
    state = tuple(opening[stn] for stn in order)
    history = [state]
    seen = {state: 0}
    damping = params["damping_percent"]
    tally = 0
    before = None
    index = 0
    while True:
        residuals = basin_residuals(state, order, partners, head, index_of)
        basin_residual = sum(abs(value) for value in residuals)
        if basin_residual == 0:
            return {"exit": "balanced", "rounds": index, "state": state, "damping": damping}
        if before is not None and basin_residual >= before:
            tally += 1
            if tally == params["patience"]:
                damping //= 2
                tally = 0
        before = basin_residual
        moves = [rnd_div(value * damping, 100) for value in residuals]
        total = sum(moves)
        if total != 0:
            far = max(range(len(order)), key=lambda place: (abs(residuals[place]), place))
            moves[far] -= total
        if not any(moves):
            return {"exit": "stalled", "rounds": index, "state": state, "damping": damping}
        state = tuple(state[place] + moves[place] for place in range(len(order)))
        if state in seen:
            return {"exit": "cycle", "rounds": -1, "damping": damping,
                    "state": min(history[seen[state]:])}
        index += 1
        history.append(state)
        seen[state] = index
        if index == params["round_budget"]:
            return {"exit": "budget", "rounds": index, "state": state, "damping": damping}


def basin_inputs(reservoirs, net, opening, offsets):
    """Per basin, the register order, partners and head offsets of balancing."""
    out = {}
    for row in reservoirs:
        basin = out.setdefault(row["basin"], {"order": [], "partners": {}, "points": {},
                                              "opening": {}, "head": {}})
        basin["order"].append(row["stn"])
        basin["partners"][row["stn"]] = []
        basin["points"][row["stn"]] = 0
        basin["opening"][row["stn"]] = opening[row["stn"]]
    for gauging in net:
        basin = out[gauging["basin"]]
        basin["partners"][gauging["from_stn"]].append(gauging["to_stn"])
        basin["partners"][gauging["to_stn"]].append(gauging["from_stn"])
        basin["points"][gauging["from_stn"]] += gauging["from_points"]
        basin["points"][gauging["to_stn"]] += 2 - gauging["from_points"]
    for basin in out.values():
        for stn, mates in basin["partners"].items():
            if not mates:
                basin["head"][stn] = 0
                continue
            share = rnd_div(basin["points"][stn] * 100, 2 * len(mates))
            key = "%d.%02d" % (share // 100, share % 100)
            if key not in offsets:
                raise ExtractError("tab_h3.xlsx: no head offset for draw share %s" % key)
            basin["head"][stn] = offsets[key]
    return out


def build_basin_reports(reservoirs, net, opening, offsets, params):
    """The basin report of every basin."""
    inputs = basin_inputs(reservoirs, net, opening, offsets)
    name_of = {row["stn"]: row["station_name"] for row in reservoirs}
    out = {}
    for basin, data in inputs.items():
        if basin not in params:
            raise ExtractError("sc_k2.docx: no operating parameters for basin %s" % basin)
        result = balance_basin(data["order"], data["opening"], data["partners"],
                               data["head"], params[basin])
        rows = []
        for place, stn in enumerate(data["order"]):
            start = data["opening"][stn]
            final = result["state"][place]
            rows.append({"stn": stn, "station_name": name_of[stn], "opening_ml": start,
                         "balanced_ml": final, "change": final - start})
        out[basin] = {"basin": basin, "exit": result["exit"], "rounds": result["rounds"],
                      "damping_percent": result["damping"], "reservoirs": rows,
                      "transferred_ml": sum(abs(row["change"]) for row in rows),
                      "storage_total": sum(row["balanced_ml"] for row in rows)}
    return out


def build_losses(net, licences, segment_of, rates, balanced):
    """Per net gauging, its licence, segment and conveyance loss."""
    out = []
    for gauging in sorted(net, key=lambda item: item["gauging_id"]):
        licence = licences.get(gauging["licence"])
        if licence is None:
            raise ExtractError("gauging %s names licence %s, which the register lacks"
                               % (gauging["gauging_id"], gauging["licence"]))
        if licence["scheme"] not in segment_of:
            raise ExtractError("licence %s names scheme %s, which sc_k2.docx lacks"
                               % (licence["licence"], licence["scheme"]))
        segment = segment_of[licence["scheme"]]
        rate = rate_in_force(rates, segment, licence["date"])
        ends = balanced[gauging["from_stn"]] + balanced[gauging["to_stn"]]
        out.append({"gauging_id": gauging["gauging_id"], "licence": licence["licence"],
                    "scheme": licence["scheme"], "segment": segment, "date": licence["date"],
                    "from_stn": gauging["from_stn"], "to_stn": gauging["to_stn"],
                    "from_points": gauging["from_points"],
                    "loss_kl": trunc_div(rate * ends, 1000)})
    return out


def build_segment_reports(losses, licences, segments):
    """The segment report of every segment."""
    out = {}
    for segment in sorted(segments):
        rows = []
        for code in sorted(licences):
            if licences[code]["scheme"] not in segments[segment]:
                continue
            mine = [loss for loss in losses if loss["licence"] == code]
            rows.append({"licence": code, "date": licences[code]["date"],
                         "gaugings": len(mine),
                         "loss_kl": sum(loss["loss_kl"] for loss in mine)})
        out[segment] = {"segment": segment, "licences": rows,
                        "gaugings": sum(row["gaugings"] for row in rows),
                        "loss_kl": sum(row["loss_kl"] for row in rows)}
    return out


def json_bytes(value):
    """A JSON report in its byte form."""
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def text_bytes(lines):
    """A text report in its byte form."""
    return "".join(line + "\n" for line in lines).encode("utf-8")


def xml_escape(text):
    """Text with the four characters the layout names escaped."""
    out = text.replace("&", "&amp;").replace("<", "&lt;")
    return out.replace(">", "&gt;").replace('"', "&quot;")


def sheet_xml(rows):
    """A worksheet part holding the given rows."""
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<worksheet xmlns="%s"><sheetData>' % SML[1:-1]]
    for number, row in enumerate(rows, 1):
        cells = []
        for place, value in enumerate(row):
            ref = "%s%d" % (chr(ord("A") + place), number)
            if isinstance(value, int):
                cells.append('<c r="%s"><v>%d</v></c>' % (ref, value))
            else:
                cells.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>'
                             % (ref, xml_escape(value)))
        parts.append('<row r="%d">%s</row>' % (number, "".join(cells)))
    parts.append("</sheetData></worksheet>")
    return "".join(parts).encode("utf-8")


def workbook_parts(sheets):
    """The package parts of a workbook holding the given sheets."""
    types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package'
             '.relationships+xml"/>', '<Default Extension="xml" ContentType="application/xml"/>',
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats'
             '-officedocument.spreadsheetml.sheet.main+xml"/>']
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="%s">' % PKGREL[1:-1]]
    book = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<workbook xmlns="%s" xmlns:r="%s"><sheets>' % (SML[1:-1], RELNS[1:-1])]
    sheet_parts = []
    for number, (name, rows) in enumerate(sheets, 1):
        part = "xl/worksheets/sheet%d.xml" % number
        types.append('<Override PartName="/%s" ContentType="application/vnd.openxmlformats-'
                     'officedocument.spreadsheetml.worksheet+xml"/>' % part)
        rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/'
                    'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d'
                    '.xml"/>' % (number, number))
        book.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>'
                    % (xml_escape(name), number, number))
        sheet_parts.append((part, sheet_xml(rows)))
    root = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="%s">' % PKGREL[1:-1],
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/officeDocument" Target="xl/workbook.xml"/>', '</Relationships>']
    return ([("[Content_Types].xml", "".join(types + ["</Types>"]).encode("utf-8")),
             ("_rels/.rels", "".join(root).encode("utf-8")),
             ("xl/workbook.xml", "".join(book + ["</sheets></workbook>"]).encode("utf-8")),
             ("xl/_rels/workbook.xml.rels",
              "".join(rels + ["</Relationships>"]).encode("utf-8"))] + sheet_parts)


def write_workbook(path, sheets):
    """An Office Open XML workbook holding the given sheets."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in workbook_parts(sheets):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o600 << 16
            archive.writestr(info, body)


def dump_rows(rows):
    """The content dump of a database or workbook report."""
    return text_bytes(["|".join(str(value) for value in row) for row in rows])


def write_database(path, basin_rows, reservoir_rows):
    """The balanced storage database."""
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    try:
        con.execute('CREATE TABLE basin (basin TEXT, "exit" TEXT, rounds INTEGER, '
                    "damping_percent INTEGER, transferred_ml INTEGER)")
        con.execute("CREATE TABLE reservoir (basin TEXT, stn TEXT, opening_ml INTEGER, "
                    "balanced_ml INTEGER, change INTEGER)")
        con.executemany("INSERT INTO basin VALUES (?, ?, ?, ?, ?)", basin_rows)
        con.executemany("INSERT INTO reservoir VALUES (?, ?, ?, ?, ?)", reservoir_rows)
        con.commit()
    finally:
        con.close()


def ledger_lines(reports, basins):
    """The lines of station_ledger.csv."""
    out = ["basin,stn,station_name,opening_ml,balanced_ml,change"]
    for basin in basins:
        for row in reports[basin]["reservoirs"]:
            out.append('%s,%s,"%s",%d,%d,%d'
                       % (basin, row["stn"], row["station_name"].replace('"', '""'),
                          row["opening_ml"], row["balanced_ml"], row["change"]))
    return out


def band_lines(reports, basins):
    """The lines of storage_bands.txt."""
    out = []
    for basin in basins:
        bands = {}
        for row in reports[basin]["reservoirs"]:
            low = (row["balanced_ml"] // 250) * 250
            bands[low] = bands.get(low, 0) + 1
        for low in sorted(bands):
            out.append("%s %d-%d %d" % (basin, low, low + 249, bands[low]))
    return out


def index_lines(reservoirs, label, gauge_of):
    """The lines of station_index.xml."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<stations season="%s">' % xml_escape(label)]
    for row in reservoirs:
        out.append('  <station stn="%s" gauge="%s" catchment="%s" basin="%s">%s</station>'
                   % (xml_escape(row["stn"]), xml_escape(gauge_of[row["stn"]]),
                      xml_escape(row["catchment"]), xml_escape(row["basin"]),
                      xml_escape(row["station_name"])))
    out.append("</stations>")
    return out


def exit_lines(reports, basins, label):
    """The lines of exits.yaml."""
    out = ["season: %s" % label, "basins:"]
    for basin in basins:
        out.append("  %s:" % basin)
        for key in ("exit", "rounds", "damping_percent", "transferred_ml"):
            out.append("    %s: %s" % (key, reports[basin][key]))
    return out


def brief_lines(reports, basins, label):
    """The lines of season_brief.md."""
    out = ["# Season %s balancing" % label, "",
           "| Basin | Exit | Rounds | Damping | Transferred ML |", "|---|---|---|---|---|"]
    for basin in basins:
        report = reports[basin]
        out.append("| %s | %s | %d | %d | %d |"
                   % (basin, report["exit"], report["rounds"], report["damping_percent"],
                      report["transferred_ml"]))
    return out


def licence_rows(licences, losses, segment_of):
    """Per licence, its scheme, segment, date, net gaugings and loss."""
    out = []
    for code in sorted(licences):
        mine = [loss for loss in losses if loss["licence"] == code]
        out.append({"licence": code, "scheme": licences[code]["scheme"],
                    "segment": segment_of[licences[code]["scheme"]],
                    "date": licences[code]["date"], "gaugings": len(mine),
                    "loss_kl": sum(loss["loss_kl"] for loss in mine)})
    return out


def scheme_rows(schemes, licences, rows):
    """Per scheme, its segment, licences, net gaugings and loss."""
    out = []
    for scheme in sorted(schemes, key=lambda item: item["scheme"]):
        mine = [row for row in rows if licences[row["licence"]]["scheme"] == scheme["scheme"]]
        out.append({"scheme": scheme["scheme"], "segment": scheme["segment"],
                    "licences": len(mine),
                    "gaugings": sum(row["gaugings"] for row in mine),
                    "loss_kl": sum(row["loss_kl"] for row in mine)})
    return out


def day_rows(licences, rows):
    """Per licence date, the net gaugings and the loss of that date."""
    out = []
    for day in sorted({licence["date"] for licence in licences.values()}):
        mine = [row for row in rows if row["date"] == day]
        out.append({"date": day, "gaugings": sum(row["gaugings"] for row in mine),
                    "loss_kl": sum(row["loss_kl"] for row in mine)})
    return out


def catchment_rows(catchments, reservoirs, reports):
    """Per catchment, its basin, reservoirs and storage totals."""
    opening = {}
    balanced = {}
    for report in reports.values():
        for row in report["reservoirs"]:
            opening[row["stn"]] = row["opening_ml"]
            balanced[row["stn"]] = row["balanced_ml"]
    out = []
    for code in sorted(catchments):
        mine = [row for row in reservoirs if row["catchment"] == code]
        out.append({"catchment": code, "basin": catchments[code], "reservoirs": len(mine),
                    "opening_ml": sum(opening[row["stn"]] for row in mine),
                    "balanced_ml": sum(balanced[row["stn"]] for row in mine)})
    return out


def mirror_mismatches(path, reservoirs, readings):
    """The reservoirs whose depot mirror row is missing or differs."""
    rows = {}
    for row in table_rows(path, ",", ("stn", "station_name", "basin", "reading_ml")):
        rows[row["stn"]] = row
    count = 0
    for row in reservoirs:
        mirror = rows.get(row["stn"])
        if mirror is None:
            count += 1
        elif (mirror["station_name"] != row["station_name"]
              or mirror["basin"] != row["basin"]
              or int(mirror["reading_ml"]) != readings[row["stn"]]):
            count += 1
    return count


def json_reports(ctx):
    """The JSON reports of the extract."""
    out = {"summary.json": json_bytes(ctx["summary"]),
           "policy_audit.json": json_bytes(ctx["policy_audit"]),
           "data_quality.json": json_bytes(ctx["quality"]),
           "reconciliation.json": json_bytes(ctx["reconciliation"]),
           "prior_delta.json": json_bytes(ctx["prior_delta"]),
           "scheme_losses.json": json_bytes({"schemes": ctx["schemes_out"]})}
    for basin in ctx["basins"]:
        out["region_%s.json" % basin] = json_bytes(ctx["reports"][basin])
    for segment, report in ctx["segment_reports"].items():
        out["segment_%s.json" % segment] = json_bytes(report)
    return out


def text_reports(ctx):
    """The plain text, csv, tsv and psv reports of the extract."""
    reports = ctx["reports"]
    basins = ctx["basins"]
    out = {"station_ledger.csv": text_bytes(ledger_lines(reports, basins)),
           "storage_bands.txt": text_bytes(band_lines(reports, basins)),
           "station_index.xml": text_bytes(index_lines(ctx["reservoirs"], ctx["label"],
                                                       ctx["gauge_of"])),
           "exits.yaml": text_bytes(exit_lines(reports, basins, ctx["label"])),
           "season_brief.md": text_bytes(brief_lines(reports, basins, ctx["label"]))}
    out.update(loss_reports(ctx))
    for basin in basins:
        out["basin_%s.tsv" % basin] = text_bytes(
            ["\t".join(("stn", "gauge_no", "catchment", "opening_ml", "balanced_ml", "change"))]
            + ["\t".join((row["stn"], ctx["gauge_of"][row["stn"]], ctx["catch_of"][row["stn"]],
                          str(row["opening_ml"]), str(row["balanced_ml"]), str(row["change"])))
               for row in reports[basin]["reservoirs"]])
    return out


def loss_reports(ctx):
    """The loss and gauging reports of the extract."""
    losses = ctx["losses"]
    out = {"loss_ledger.tsv": text_bytes(
        ["\t".join(("gauging_id", "licence", "segment", "from_stn", "to_stn", "loss_kl"))]
        + ["\t".join((loss["gauging_id"], loss["licence"], loss["segment"], loss["from_stn"],
                      loss["to_stn"], str(loss["loss_kl"]))) for loss in losses])}
    out["gauging_net.psv"] = text_bytes(
        ["|".join(("gauging_id", "licence", "from_stn", "to_stn", "from_points"))]
        + ["|".join((loss["gauging_id"], loss["licence"], loss["from_stn"], loss["to_stn"],
                     POINT_TEXT[loss["from_points"]])) for loss in losses])
    out["licence_losses.csv"] = text_bytes(
        ["licence,scheme,segment,date,gaugings,loss_kl"]
        + ["%s,%s,%s,%s,%d,%d" % (row["licence"], row["scheme"], row["segment"], row["date"],
                                  row["gaugings"], row["loss_kl"]) for row in ctx["lic_rows"]])
    out["loss_by_day.csv"] = text_bytes(
        ["date,gaugings,loss_kl"]
        + ["%s,%d,%d" % (row["date"], row["gaugings"], row["loss_kl"])
           for row in ctx["day_rows"]])
    out["catchment_totals.csv"] = text_bytes(
        ["catchment,basin,reservoirs,opening_ml,balanced_ml"]
        + ["%s,%s,%d,%d,%d" % (row["catchment"], row["basin"], row["reservoirs"],
                               row["opening_ml"], row["balanced_ml"])
           for row in ctx["catchment_rows"]])
    for segment in ctx["segment_reports"]:
        out["segment_%s.tsv" % segment] = text_bytes(
            ["\t".join(("gauging_id", "licence", "date", "loss_kl"))]
            + ["\t".join((loss["gauging_id"], loss["licence"], loss["date"],
                          str(loss["loss_kl"])))
               for loss in losses if loss["segment"] == segment])
    return out


def database_rows(ctx):
    """The rows of the two tables of balanced.sqlite."""
    basin_rows = []
    for basin in ctx["basins"]:
        report = ctx["reports"][basin]
        basin_rows.append((basin, report["exit"], report["rounds"],
                           report["damping_percent"], report["transferred_ml"]))
    reservoir_rows = []
    for basin in ctx["basins"]:
        for row in ctx["reports"][basin]["reservoirs"]:
            reservoir_rows.append((basin, row["stn"], row["opening_ml"],
                                   row["balanced_ml"], row["change"]))
    return basin_rows, reservoir_rows


def workbook_sheets(ctx):
    """The sheets of loss_book.xlsx."""
    licences = [["licence", "scheme", "segment", "date", "gaugings", "loss_kl"]]
    for row in ctx["lic_rows"]:
        licences.append([row["licence"], row["scheme"], row["segment"], row["date"],
                         row["gaugings"], row["loss_kl"]])
    segments = [["segment", "gaugings", "loss_kl"]]
    for segment, report in ctx["segment_reports"].items():
        segments.append([segment, report["gaugings"], report["loss_kl"]])
    return [("licences", licences), ("segments", segments)]


def write_reports(out_dir, ctx):
    """Every report of the extract, written into the output directory."""
    texts = dict(json_reports(ctx))
    texts.update(text_reports(ctx))
    basin_rows, reservoir_rows = database_rows(ctx)
    sheets = workbook_sheets(ctx)
    digests = {name: hashlib.sha256(body).hexdigest() for name, body in texts.items()}
    db_dump = dump_rows([("basin",) + row for row in basin_rows]
                        + [("reservoir",) + row for row in reservoir_rows])
    digests["balanced.sqlite"] = hashlib.sha256(db_dump).hexdigest()
    book_dump = dump_rows([(name,) + tuple(row) for name, rows in sheets for row in rows])
    digests["loss_book.xlsx"] = hashlib.sha256(book_dump).hexdigest()
    os.makedirs(out_dir, exist_ok=True)
    for name, body in sorted(texts.items()):
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(body)
    write_database(os.path.join(out_dir, "balanced.sqlite"), basin_rows, reservoir_rows)
    write_workbook(os.path.join(out_dir, "loss_book.xlsx"), sheets)
    with open(os.path.join(out_dir, "manifest.json"), "wb") as handle:
        handle.write(json_bytes({"reports": digests}))


def opening_storages(data_dir, reservoirs, gauge_of, label):
    """The opening storage and the meter reading of every reservoir."""
    records = parse_meter(os.path.join(data_dir, "ob_s3.bin"))
    codes = {row["stn"] for row in reservoirs}
    rows, survey_date = load_survey(os.path.join(data_dir, "sv_survey.csv"), codes)
    survey_day = (survey_date - season_start(label)).days + 1
    readings = meter_readings(records)
    corrections = meter_corrections(records, survey_day)
    plain = {}
    corrected = {}
    for row in reservoirs:
        stn = row["stn"]
        if stn not in gauge_of:
            raise ExtractError("xw_codes.csv: no gauge number for station %s" % stn)
        number = int(gauge_of[stn][1:])
        if number not in readings:
            raise ExtractError("ob_s3.bin: no reading for gauge %s" % gauge_of[stn])
        plain[stn] = readings[number]
        corrected[stn] = corrections.get(number, readings[number])
    catch_of = {row["stn"]: row["catchment"] for row in reservoirs}
    catchments = sorted({row["catchment"] for row in reservoirs})
    offsets = solve_offsets(survey_data(rows, corrected, catch_of), catchments)
    return {stn: corrected[stn] + offsets[catch_of[stn]] for stn in corrected}, plain


def net_gaugings(data_dir, cutoff, basin_of):
    """The net gaugings of the season and the input-quality counts."""
    gaugings = load_gaugings(data_dir)
    for gauging in gaugings:
        for key in ("from_stn", "to_stn"):
            if gauging[key] not in basin_of:
                raise ExtractError("gauging %s names station %s, which is not in the register"
                                   % (gauging["gauging_id"], gauging[key]))
        if basin_of[gauging["from_stn"]] != basin_of[gauging["to_stn"]]:
            raise ExtractError("gauging %s joins reservoirs of two basins"
                               % gauging["gauging_id"])
    revisions = load_revisions(os.path.join(data_dir, "rv_log.psv"))
    net, counts = apply_revisions(gaugings, revisions, cutoff)
    for gauging in net:
        gauging["basin"] = basin_of[gauging["from_stn"]]
        gauging["from_points"] = FROM_POINTS[gauging["sense"]]
    return net, counts


def build_context(data_dir):
    """Every figure the reports of the extract are built from."""
    label, cutoff = load_season(os.path.join(data_dir, "basin_cfg.ini"))
    reservoirs = load_register(os.path.join(data_dir, "stn_core.sqlite"))
    catchments = load_basin_map(os.path.join(data_dir, "bs_map.xml"))
    for row in reservoirs:
        if row["catchment"] not in catchments:
            raise ExtractError("bs_map.xml: no basin for catchment %s" % row["catchment"])
        row["basin"] = catchments[row["catchment"]]
    gauge_of = load_crosswalk(os.path.join(data_dir, "xw_codes.csv"))
    opening, plain = opening_storages(data_dir, reservoirs, gauge_of, label)
    basin_of = {row["stn"]: row["basin"] for row in reservoirs}
    net, counts = net_gaugings(data_dir, cutoff, basin_of)
    schemes, params = load_docx(os.path.join(data_dir, "sc_k2.docx"))
    offsets = load_offset_table(os.path.join(data_dir, "tab_h3.xlsx"))
    reports = build_basin_reports(reservoirs, net, opening, offsets, params)
    balanced = {}
    for report in reports.values():
        for row in report["reservoirs"]:
            balanced[row["stn"]] = row["balanced_ml"]
    rates = load_loss_rates(os.path.join(data_dir, "mt_loss.pdf"))
    licences = load_licences(os.path.join(data_dir, "lc_register.json"))
    segment_of = {scheme["scheme"]: scheme["segment"] for scheme in schemes}
    counts["mirror_mismatches"] = mirror_mismatches(
        os.path.join(data_dir, "stn_mirror.csv"), reservoirs, plain)
    ctx = {"data_dir": data_dir, "label": label, "cutoff": cutoff, "reservoirs": reservoirs,
           "reports": reports, "basins": sorted(set(catchments.values())), "quality": counts,
           "losses": build_losses(net, licences, segment_of, rates, balanced),
           "gauge_of": gauge_of, "catch_of": {r["stn"]: r["catchment"] for r in reservoirs},
           "params": params, "rates": rates, "licences": licences, "schemes": schemes,
           "segment_of": segment_of, "net": net, "catchments": catchments}
    finish_context(ctx)
    return ctx


def finish_context(ctx):
    """The summed reports of the extract, added to the context."""
    segments = {}
    for scheme in ctx["schemes"]:
        segments.setdefault(scheme["segment"], set()).add(scheme["scheme"])
    ctx["segment_reports"] = build_segment_reports(ctx["losses"], ctx["licences"], segments)
    ctx["lic_rows"] = licence_rows(ctx["licences"], ctx["losses"], ctx["segment_of"])
    ctx["schemes_out"] = scheme_rows(ctx["schemes"], ctx["licences"], ctx["lic_rows"])
    ctx["day_rows"] = day_rows(ctx["licences"], ctx["lic_rows"])
    ctx["catchment_rows"] = catchment_rows(ctx["catchments"], ctx["reservoirs"], ctx["reports"])
    reports = ctx["reports"]
    ctx["summary"] = {
        "season": ctx["label"],
        "basins": {basin: {"exit": reports[basin]["exit"], "rounds": reports[basin]["rounds"]}
                   for basin in ctx["basins"]},
        "transferred_ml_total": sum(reports[b]["transferred_ml"] for b in ctx["basins"]),
        "loss_kl_total": sum(report["loss_kl"] for report in ctx["segment_reports"].values()),
        "gaugings_net": len(ctx["net"]),
        "reservoirs": len(ctx["reservoirs"])}
    ctx["policy_audit"] = {
        "season": ctx["label"], "revision_cutoff": ctx["cutoff"],
        "basins": {basin: dict(ctx["params"][basin]) for basin in ctx["basins"]},
        "loss_rates": sorted(ctx["rates"], key=lambda row: (row["segment"], row["revised_on"]))}
    ctx["reconciliation"] = {
        "storage": {basin: {"opening_total": sum(row["opening_ml"] for row
                                                 in reports[basin]["reservoirs"]),
                            "balanced_total": reports[basin]["storage_total"]}
                    for basin in ctx["basins"]},
        "loss_kl": {"by_gauging": sum(loss["loss_kl"] for loss in ctx["losses"]),
                    "by_licence": sum(row["loss_kl"] for row in ctx["lic_rows"]),
                    "by_segment": ctx["summary"]["loss_kl_total"],
                    "by_day": sum(row["loss_kl"] for row in ctx["day_rows"])},
        "gaugings": {"net": len(ctx["net"]),
                     "by_licence": sum(row["gaugings"] for row in ctx["lic_rows"])}}
    ctx["prior_delta"] = prior_delta(ctx)


def prior_delta(ctx):
    """The comparison of the current run with the prior balancing summary."""
    with open(os.path.join(ctx["data_dir"], "prior_balance.json"), encoding="utf-8") as handle:
        prior = json.load(handle)
    out = {"prior_season": prior["season"], "basins": {}}
    for key in ("transferred_ml_total", "loss_kl_total"):
        out[key] = {"prior": prior[key], "current": ctx["summary"][key],
                    "difference": ctx["summary"][key] - prior[key]}
    for basin in ctx["basins"]:
        out["basins"][basin] = {"prior_exit": prior["basins"][basin]["exit"],
                                "exit": ctx["reports"][basin]["exit"],
                                "prior_rounds": prior["basins"][basin]["rounds"],
                                "rounds": ctx["reports"][basin]["rounds"]}
    return out


def main(argv):
    """Balance one extract and write its reports."""
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    try:
        ctx = build_context(argv[1])
        write_reports(argv[2], ctx)
    except ExtractError as error:
        sys.stderr.write("extract error: %s\n" % error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
