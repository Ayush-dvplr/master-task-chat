#!/usr/bin/env python3
"""Conform one transmission day of a regional playout channel.

Reads only the data directory it is given and writes exactly the twenty five
artifacts of the output artifact contract into the output directory it is
given.  All arithmetic is exact rational or whole number; rounding happens
only where a value is written.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import zipfile
import zlib
import xml.etree.ElementTree as ET
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime
from fractions import Fraction

DEFAULT_DATA = "/app/data"
DEFAULT_OUT = "/app/out"

CORE_ORDER = [
    "asset_register.csv",
    "segment_conform.csv",
    "break_positions.csv",
    "slot_placement.csv",
    "avail_plan.tsv",
    "settlement_ledger.psv",
    "minutage_report.csv",
]

PASSED_QC = ("QC_PASSED", "QC_PASSED_WITH_NOTES")


# ---------------------------------------------------------------- numbers

def round_half_even(frac):
    """Round a Fraction to the nearest whole number, halves to even."""
    num, den = frac.numerator, frac.denominator
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2):
        q += 1
    return q


def fmt_ratio(frac):
    """Ten decimal places, halves to even, no negative zero."""
    scaled = round_half_even(Fraction(frac) * 10 ** 10)
    sign = "-" if scaled < 0 else ""
    mag = abs(scaled)
    return "%s%d.%010d" % (sign, mag // 10 ** 10, mag % 10 ** 10)


def fmt_major(minor, exponent):
    """A minor unit amount as a major amount with the currency's places."""
    sign = "-" if minor < 0 else ""
    mag = abs(minor)
    if exponent == 0:
        return "%s%d" % (sign, mag)
    scale = 10 ** exponent
    return "%s%d.%0*d" % (sign, mag // scale, exponent, mag % scale)


class Carry:
    """A named carry scope: floor the sum, hold the discarded fraction."""

    def __init__(self, name):
        self.name = name
        self.held = Fraction(0)
        self.conversions = 0

    def convert(self, exact):
        total = Fraction(exact) + self.held
        whole = total.numerator // total.denominator
        self.held = total - whole
        self.conversions += 1
        return whole


class CarryBook:
    def __init__(self):
        self.scopes = {}

    def scope(self, name):
        if name not in self.scopes:
            self.scopes[name] = Carry(name)
        return self.scopes[name]


# ---------------------------------------------------------------- timecode

def drop_skip(base):
    return base * 2 // 30


def tc_to_frames(label, base, drop):
    h, m, s, f = (int(x) for x in re.split(r"[:;.,]", label.strip()))
    total = ((h * 60 + m) * 60 + s) * base + f
    if drop:
        minutes = h * 60 + m
        total -= drop_skip(base) * (minutes - minutes // 10)
    return total


def tc_day_frames(base, drop):
    if drop:
        return base * 86400 - drop_skip(base) * 1296
    return base * 86400


def frames_to_tc(frames, base, drop):
    if not drop:
        ff = frames % base
        secs = frames // base
        return "%02d:%02d:%02d:%02d" % (
            secs // 3600, (secs // 60) % 60, secs % 60, ff)
    skip = drop_skip(base)
    block = base * 600 - 9 * skip
    minute_full = base * 60
    minute_short = minute_full - skip
    blocks, rem = divmod(frames, block)
    if rem < minute_full:
        minute_in = 0
        inside = rem
    else:
        rem -= minute_full
        minute_in = 1 + rem // minute_short
        inside = rem % minute_short
    minutes = blocks * 10 + minute_in
    if minute_in == 0:
        ss, ff = divmod(inside, base)
    elif inside < base - skip:
        ss, ff = 0, inside + skip
    else:
        ss, ff = divmod(inside - (base - skip), base)
        ss += 1
    return "%02d:%02d:%02d;%02d" % (minutes // 60, minutes % 60, ss, ff)


def source_span(som, eom, base, drop):
    span = tc_to_frames(eom, base, drop) - tc_to_frames(som, base, drop)
    if span < 0:
        span += tc_day_frames(base, drop)
    return max(span, 0)


# ---------------------------------------------------------------- readers

def read_delimited(path, delimiter):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def read_jsonl(path):
    out = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_vocabulary(path):
    tokens = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            token = line.rstrip("\n")
            if re.fullmatch(r"[A-Z][A-Z0-9_]+", token):
                tokens.append(token)
    return tokens


SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_workbook(path):
    """Every sheet of an xlsx as a list of rows of cell strings."""
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            sst = ET.fromstring(book.read("xl/sharedStrings.xml"))
            for item in sst.findall(SHEET_NS + "si"):
                shared.append("".join(
                    node.text or "" for node in item.iter(SHEET_NS + "t")))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target = {}
        for rel in rels:
            target[rel.get("Id")] = "xl/" + rel.get("Target").lstrip("/")
        meta = ET.fromstring(book.read("xl/workbook.xml"))
        sheets = []
        rid = "{http://schemas.openxmlformats.org/officeDocument/2006/" \
              "relationships}id"
        for sheet in meta.iter(SHEET_NS + "sheet"):
            data = ET.fromstring(book.read(target[sheet.get(rid)]))
            rows = []
            for row in data.iter(SHEET_NS + "row"):
                cells = []
                for cell in row.findall(SHEET_NS + "c"):
                    value = cell.find(SHEET_NS + "v")
                    text = "" if value is None else (value.text or "")
                    if cell.get("t") == "s" and text != "":
                        text = shared[int(text)]
                    cells.append(text)
                rows.append(cells)
            sheets.append((sheet.get("name"), rows))
        return sheets


def pdf_lines(path):
    """The text lines of a simple pdf, in page order."""
    with open(path, "rb") as handle:
        raw = handle.read()
    lines = []
    for match in re.finditer(rb"(?<!end)stream\r?\n", raw):
        start = match.end()
        end = raw.find(b"endstream", start)
        if end < 0:
            continue
        chunk = raw[start:end]
        try:
            chunk = zlib.decompress(chunk)
        except zlib.error:
            pass
        for piece in re.finditer(rb"\((.*?)\)\s*Tj", chunk, re.S):
            text = piece.group(1)
            text = re.sub(rb"\\([()\\])", rb"\1", text)
            lines.append(text.decode("latin-1"))
    return lines


# ---------------------------------------------------------------- writers

class Artifacts:
    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.blobs = {}

    def text(self, name, body):
        if not body.endswith("\n"):
            body += "\n"
        self.blobs[name] = body.encode("utf-8")

    def delimited(self, name, header, rows, delimiter):
        lines = [delimiter.join(header)]
        for row in rows:
            lines.append(delimiter.join(str(cell) for cell in row))
        self.text(name, "\n".join(lines))

    def json_doc(self, name, payload):
        self.text(name, json.dumps(
            payload, sort_keys=True, indent=2, ensure_ascii=True))

    def jsonl(self, name, records):
        body = "".join(json.dumps(
            record, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True) + "\n" for record in records)
        self.blobs[name] = (body if body else "\n").encode("utf-8")

    def flush(self):
        for name in sorted(self.blobs):
            with open(os.path.join(self.out_dir, name), "wb") as handle:
                handle.write(self.blobs[name])


# ---------------------------------------------------------------- pipeline

def conform(data_dir, out_dir):
    def path(name):
        return os.path.join(data_dir, name)

    art = Artifacts(out_dir)
    carries = CarryBook()

    config = read_json(path("channel_config.json"))
    channel_ref = config["channel_ref"]
    tx_date = config["transmission_date"]
    day_start_tc = config["day_start_tc"]
    house_filler = config["house_filler_ref"]
    instance_ref = config["instance_ref"]
    control_set = config["workbook_control_set"]

    snap_sides = read_vocabulary(path("snap_side_reference.txt"))
    correction_vocabulary = read_vocabulary(
        path("correction_reason_reference.txt"))
    deferral_vocabulary = read_vocabulary(
        path("deferral_reason_reference.txt"))

    def in_vocabulary(token, vocabulary):
        if token not in vocabulary:
            raise SystemExit("token outside its vocabulary: " + token)
        return token

    rate_codes = {r["rate_code"]: r
                  for r in read_delimited(path("rate_code_register.csv"), ",")}
    channel_rate = rate_codes[config["channel_rate_code"]]
    ch_num = int(channel_rate["rate_num"])
    ch_den = int(channel_rate["rate_den"])
    ch_base = int(channel_rate["tc_base"])
    ch_drop = channel_rate["df_allowed"] == "yes"
    day_start_frames = tc_to_frames(day_start_tc, ch_base, ch_drop)
    day_frames = tc_day_frames(ch_base, ch_drop)
    hour_frames = day_frames // 24
    first_hour = day_start_frames // hour_frames
    hour_labels = ["H%02d" % (first_hour + k) for k in range(24)]

    def frames_to_channel(count, rate_num, rate_den):
        return Fraction(count * ch_num * rate_den, ch_den * rate_num)

    def seconds_to_channel(seconds):
        return Fraction(seconds * ch_num, ch_den)

    def hour_of(frame):
        index = frame // hour_frames
        if index < 0:
            index = 0
        if index > 23:
            index = 23
        return hour_labels[index]

    # -- the settled workbook sheet
    sheets = read_workbook(path("contract_terms_workbook.xlsx"))
    settled_name, settled_rows = None, None
    for name, rows in sheets:
        head = rows[0] if rows else []
        if len(head) >= 2 and head[0] == "control_set" \
                and head[1] == control_set:
            settled_name, settled_rows = name, rows
            break
    if settled_rows is None:
        raise SystemExit("no workbook sheet carries control set " + control_set)
    scalars = {}
    commission = {}
    for row in settled_rows:
        if len(row) >= 2 and row[0] in (
                "snap_tolerance_frames", "makegood_cap_num",
                "makegood_cap_den"):
            scalars[row[0]] = int(row[1])
        elif len(row) >= 5 and row[0] == "COMMISSION":
            commission[row[1]] = Fraction(int(row[3]), int(row[4]))
    snap_tolerance = scalars["snap_tolerance_frames"]
    cap_num = scalars["makegood_cap_num"]
    cap_den = scalars["makegood_cap_den"]

    # -- the memorandum
    memo = pdf_lines(path("regulatory_minutage_memo.pdf"))
    constants = {}
    market_minutes = {}
    for line in memo:
        hit = re.fullmatch(r"\s*([a-z_]+)\s*=\s*(\d+)\s*", line)
        if hit:
            constants[hit.group(1)] = int(hit.group(2))
            continue
        hit = re.fullmatch(
            r"\s*(\S+)\s*\|\s*(H\d+)\s*\|\s*(\d+)\s*\|\s*(\S+)\s*", line)
        if hit:
            market_minutes[(hit.group(1), hit.group(2))] = int(hit.group(3))
    separation_minimum = constants["separation_minimum_positions"]
    grain_seconds = constants["billing_grain_seconds"]
    standing_minutes = constants["regulatory_minutes_per_clock_hour"]
    grain_frames = seconds_to_channel(grain_seconds)

    def cap_frames_of(minutes):
        exact = seconds_to_channel(minutes * 60)
        return exact.numerator // exact.denominator

    standing_cap = cap_frames_of(standing_minutes)

    # -- V1 to V3 asset canonicalisation, rate resolution, source span
    attempts = read_delimited(path("ingest_attempt_register.csv"), ",")
    clusters = defaultdict(list)
    for row in attempts:
        clusters[row["content_ref"]].append(row)

    def arrival(row):
        stamp = row["received_at"].strip()
        if stamp.endswith("Z"):
            stamp = stamp[:-1] + "+00:00"
        return datetime.fromisoformat(stamp)

    assets = {}
    asset_rows = []
    for content_ref in sorted(clusters):
        members = clusters[content_ref]
        anchor = min(members, key=lambda r: (arrival(r), r["ingest_id"]))
        passed = [r for r in members if r["qc_state"] in PASSED_QC]
        if not passed:
            asset_rows.append([
                content_ref, "", "", "", "", "", "", "", "", "", "", "", "",
                anchor["house_no"], anchor["ingest_id"], "AS_EXCLUDED"])
            continue
        canonical = min(passed,
                        key=lambda r: (-int(r["revision_no"]), r["ingest_id"]))
        rate = rate_codes[canonical["rate_code"]]
        rate_num = int(rate["rate_num"])
        rate_den = int(rate["rate_den"])
        base = int(rate["tc_base"])
        drop = canonical["tc_mode"] == "DF" and rate["df_allowed"] == "yes"
        span = source_span(canonical["som_tc"], canonical["eom_tc"], base, drop)
        exact = frames_to_channel(span, rate_num, rate_den)
        assets[content_ref] = {
            "content_ref": content_ref,
            "rate_num": rate_num,
            "rate_den": rate_den,
            "tc_base": base,
            "drop": drop,
            "source_frames": span,
        }
        asset_rows.append([
            content_ref, canonical["ingest_id"], canonical["revision_no"],
            canonical["qc_state"], canonical["rate_code"], rate_num, rate_den,
            base, "yes" if drop else "no", canonical["som_tc"],
            canonical["eom_tc"], span, fmt_ratio(exact), anchor["house_no"],
            anchor["ingest_id"], "AS_INCLUDED"])

    art.delimited("asset_register.csv", [
        "content_ref", "canonical_ingest_id", "revision_no", "qc_state",
        "rate_code", "rate_num", "rate_den", "tc_base", "drop_frame", "som_tc",
        "eom_tc", "source_frames", "channel_frames_exact", "house_no",
        "anchor_ingest_id", "inclusion_state"], asset_rows, ",")

    # -- the parts of every asset
    part_manifest = defaultdict(list)
    for row in read_delimited(path("segment_part_manifest.tsv"), "\t"):
        part_manifest[row["content_ref"]].append(row)

    def parts_of(content_ref):
        asset = assets[content_ref]
        rows = sorted(part_manifest.get(content_ref, []),
                      key=lambda r: int(r["part_no"]))
        if not rows:
            return [{"part_no": 0, "part_kind": "PT_PROGRAMME",
                     "source_frames": asset["source_frames"]}]
        out = []
        for row in rows:
            out.append({
                "part_no": int(row["part_no"]),
                "part_kind": row["part_kind"],
                "source_frames": source_span(
                    row["part_som_tc"], row["part_eom_tc"],
                    asset["tc_base"], asset["drop"]),
            })
        return out

    # -- V7 the order of the day
    schedule = read_delimited(path("transmission_schedule.csv"), ",")
    slots = []
    for row in schedule:
        offset = tc_to_frames(row["sched_start_tc"], ch_base, ch_drop) \
            - day_start_frames
        if offset < 0:
            offset += day_frames
        slots.append({
            "slot_id": row["slot_id"],
            "content_ref": row["content_ref"],
            "sched_offset": offset,
            "junction_kind": row["junction_kind"],
            "flex_part_no": row["flex_part_no"],
            "daypart_ref": row["daypart_ref"],
            "dropped": row["content_ref"] not in assets,
        })
    slots.sort(key=lambda s: (s["sched_offset"], s["slot_id"]))
    placed = [s for s in slots if not s["dropped"]]
    dropped = [s for s in slots if s["dropped"]]
    for index, slot in enumerate(placed, 1):
        slot["sequence_no"] = index
    for slot in dropped:
        slot["sequence_no"] = 0

    # -- V4 and V5 segment assembly
    segment_rows = []
    for slot in placed:
        asset = assets[slot["content_ref"]]
        parts = parts_of(slot["content_ref"])
        kinds = [p["part_kind"] for p in parts]
        head = 0
        while head < len(parts) and kinds[head] == "PT_BLACK":
            head += 1
        tail = len(parts)
        while tail > head and kinds[tail - 1] == "PT_BLACK":
            tail -= 1
        scope = carries.scope("V4:" + slot["slot_id"])
        material = 0
        flex_frames = 0
        for index, part in enumerate(parts):
            exact = frames_to_channel(
                part["source_frames"], asset["rate_num"], asset["rate_den"])
            if index < head:
                state = "PR_TRIMMED_HEAD"
            elif index >= tail:
                state = "PR_TRIMMED_TAIL"
            else:
                state = "PR_RETAINED"
            if state == "PR_RETAINED":
                frames = scope.convert(exact)
                material += frames
                if str(part["part_no"]) == str(slot["flex_part_no"]):
                    flex_frames = frames
            else:
                frames = 0
            segment_rows.append([
                slot["slot_id"], slot["content_ref"], part["part_no"],
                part["part_kind"], state, part["source_frames"],
                fmt_ratio(exact), frames, fmt_ratio(scope.held)])
        slot["material_frames"] = material
        slot["flex_frames"] = flex_frames

    segment_rows.sort(key=lambda r: (r[0], r[2]))
    art.delimited("segment_conform.csv", [
        "slot_id", "content_ref", "part_no", "part_kind", "retention_state",
        "source_frames", "channel_frames_exact", "channel_frames",
        "carry_after"], segment_rows, ",")

    # -- V6 splice conditioning
    index_frames = defaultdict(list)
    for row in read_delimited(path("gop_index_channel.psv"), "|"):
        index_frames[row["content_ref"]].append(int(row["idr_frame"]))
    for key in index_frames:
        index_frames[key].sort()

    break_plan = defaultdict(list)
    for row in read_delimited(path("break_plan_register.csv"), ","):
        break_plan[row["slot_id"]].append(row)
    for key in break_plan:
        break_plan[key].sort(key=lambda r: int(r["break_no"]))

    break_rows = []
    for slot in placed:
        scope = carries.scope("V6:" + slot["slot_id"])
        plan = break_plan.get(slot["slot_id"], [])
        marks = index_frames.get(slot["content_ref"], [])
        nominals = []
        held_after = []
        for row in plan:
            nominals.append(scope.convert(
                seconds_to_channel(int(row["nominal_offset_seconds"]))))
            held_after.append(scope.held)
        slot_breaks = []
        displacements = []
        for position, row in enumerate(plan):
            nominal = nominals[position]
            last = position == len(plan) - 1
            if last and displacements:
                target = max(0, nominal - sum(displacements))
            else:
                target = nominal
            if not marks:
                snapped, side = target, "SNAP_NONE"
            else:
                cut = bisect_right(marks, target)
                below = marks[cut - 1] if cut > 0 else None
                above = marks[cut] if cut < len(marks) else None
                if below is not None and target - below <= snap_tolerance:
                    snapped = below
                elif above is not None:
                    snapped = above
                else:
                    snapped = below
                if snapped == target:
                    side = "SNAP_EXACT"
                elif snapped < target:
                    side = "SNAP_BACK"
                else:
                    side = "SNAP_FORWARD"
            displacement = snapped - nominal
            displacements.append(displacement)
            break_no = int(row["break_no"])
            break_ref = "bk_%s_%02d" % (slot["slot_id"], break_no)
            slot_breaks.append({
                "break_ref": break_ref,
                "break_no": break_no,
                "slot_id": slot["slot_id"],
                "position_frame": snapped,
                "avail_seconds": int(row["avail_seconds"]),
            })
            break_rows.append([
                slot["slot_id"], break_no, break_ref,
                int(row["nominal_offset_seconds"]), nominal, target, snapped,
                in_vocabulary(side, snap_sides), displacement,
                int(row["avail_seconds"]), fmt_ratio(held_after[position])])
        slot["breaks"] = slot_breaks

    break_rows.sort(key=lambda r: (r[0], r[1]))
    art.delimited("break_positions.csv", [
        "slot_id", "break_no", "break_ref", "nominal_offset_seconds",
        "nominal_frame", "adjusted_target_frame", "position_frame",
        "snap_side", "displacement_frames", "avail_seconds", "carry_after"],
        break_rows, ",")

    # -- V8 drift correction and the placement walk
    filler_library = sorted(read_delimited(path("filler_library.csv"), ","),
                            key=lambda r: int(r["predicate_order"]))
    corrections = []
    filler_rows = []
    starts = [0] * len(placed)
    trims = [0] * len(placed)
    cursor = 0
    previous_fixed = None
    for index, slot in enumerate(placed):
        if slot["junction_kind"] == "JK_FIXED":
            target = slot["sched_offset"]
            if cursor > target:
                remaining = cursor - target
                low = previous_fixed if previous_fixed is not None else index
                for back in range(index - 1, low - 1, -1):
                    if remaining == 0:
                        break
                    available = placed[back]["flex_frames"] - trims[back]
                    take = min(available, remaining)
                    if take > 0:
                        trims[back] += take
                        remaining -= take
                        corrections.append({
                            "reason": "CR_TRIM_FLEX" if back == index - 1
                            else "CR_TRIM_BACKFILL",
                            "slot_id": slot["slot_id"],
                            "frames": take,
                            "detail_slot": placed[back]["slot_id"],
                            "filler_ref": "",
                        })
                if remaining > 0:
                    corrections.append({
                        "reason": "CR_TRIM_SHORTFALL",
                        "slot_id": slot["slot_id"],
                        "frames": remaining,
                        "detail_slot": slot["slot_id"],
                        "filler_ref": "",
                    })
                if previous_fixed is not None:
                    walk = starts[previous_fixed]
                    for back in range(previous_fixed, index):
                        starts[back] = walk
                        walk += placed[back]["material_frames"] - trims[back]
            elif cursor < target:
                gap = target - cursor
                chosen = None
                for row in filler_library:
                    if row["stock_state"] != "FS_AVAILABLE":
                        continue
                    if row["daypart_ref"] not in (slot["daypart_ref"], "DP_ANY"):
                        continue
                    if not (int(row["min_frames"]) <= gap
                            <= int(row["max_frames"])):
                        continue
                    chosen = row
                    break
                if chosen is None:
                    filler_ref = house_filler
                    selection = 0
                else:
                    filler_ref = chosen["filler_ref"]
                    selection = int(chosen["predicate_order"])
                corrections.append({
                    "reason": "CR_FILL_INSERT",
                    "slot_id": slot["slot_id"],
                    "frames": gap,
                    "detail_slot": slot["slot_id"],
                    "filler_ref": filler_ref,
                })
                filler_rows.append([
                    slot["slot_id"], target, gap, filler_ref,
                    slot["daypart_ref"], selection])
            else:
                corrections.append({
                    "reason": "CR_NO_CHANGE",
                    "slot_id": slot["slot_id"],
                    "frames": 0,
                    "detail_slot": slot["slot_id"],
                    "filler_ref": "",
                })
            starts[index] = target
            previous_fixed = index
        else:
            starts[index] = cursor
        cursor = starts[index] + placed[index]["material_frames"] - trims[index]

    for index, slot in enumerate(placed):
        slot["start_frame"] = starts[index]
        slot["trim_frames"] = trims[index]
        slot["transmitted_frames"] = slot["material_frames"] - trims[index]
        slot["end_frame"] = slot["start_frame"] + slot["transmitted_frames"]

    for slot in sorted(dropped, key=lambda s: (s["sched_offset"], s["slot_id"])):
        corrections.append({
            "reason": "CR_SLOT_DROPPED",
            "slot_id": slot["slot_id"],
            "frames": 0,
            "detail_slot": slot["slot_id"],
            "filler_ref": "",
        })

    filler_rows.sort(key=lambda r: r[0])
    art.delimited("filler_plan.csv", [
        "slot_id", "junction_offset_frame", "gap_frames", "filler_ref",
        "daypart_ref", "selection_index"], filler_rows, ",")

    placement_rows = []
    for slot in placed:
        placement_rows.append([
            slot["slot_id"], slot["content_ref"], slot["sequence_no"],
            slot["junction_kind"], slot["sched_offset"], slot["start_frame"],
            slot["material_frames"], slot["trim_frames"],
            slot["transmitted_frames"], slot["end_frame"],
            slot["start_frame"] - slot["sched_offset"],
            hour_of(slot["start_frame"]), slot["daypart_ref"], "PL_PLACED"])
    for slot in dropped:
        placement_rows.append([
            slot["slot_id"], slot["content_ref"], 0, slot["junction_kind"],
            0, 0, 0, 0, 0, 0, 0, "", slot["daypart_ref"], "PL_DROPPED"])
    placement_rows.sort(key=lambda r: (r[2], r[0]))
    art.delimited("slot_placement.csv", [
        "slot_id", "content_ref", "sequence_no", "junction_kind",
        "sched_start_frame", "actual_start_frame", "material_frames",
        "trim_frames", "transmitted_frames", "end_frame", "drift_frames",
        "hour_label", "daypart_ref", "placement_state"], placement_rows, ",")

    day_end_frame = max((row[9] for row in placement_rows), default=0)

    totals = defaultdict(int)
    trace = []
    for number, record in enumerate(corrections, 1):
        in_vocabulary(record["reason"], correction_vocabulary)
        totals[record["reason"]] += 1
        trace.append({
            "sequence": number,
            "slot_id": record["slot_id"],
            "reason": record["reason"],
            "frames": record["frames"],
            "detail_slot": record["detail_slot"],
            "filler_ref": record["filler_ref"],
        })
    art.json_doc("conform_trace.json", {
        "corrections": trace,
        "totals": dict(totals),
        "day_end_frame": day_end_frame,
        "correction_count": len(trace),
    })

    # -- V10 market substitution
    markets = [row["market_ref"]
               for row in read_delimited(path("market_register.csv"), ",")]
    markets.sort()
    rules = []
    root = ET.parse(path("blackout_rule_set.xml")).getroot()
    for rule in root.iter("rule"):
        rules.append({
            "rule_id": rule.get("rule_id"),
            "precedence": int(rule.get("precedence")),
            "market_ref": rule.get("market_ref"),
            "content_ref": rule.get("content_ref"),
            "window_from": rule.get("window_from"),
            "window_to": rule.get("window_to"),
            "substitute_ref": rule.get("substitute_ref"),
            "override": rule.get("override"),
        })
    substitutes = defaultdict(list)
    for row in read_delimited(path("substitution_library.csv"), ","):
        substitutes[row["substitute_ref"]].append(row)
    for key in substitutes:
        substitutes[key].sort(key=lambda r: int(r["break_no"]))

    override_rows = []
    market_breaks = {}
    substituted = {market: {} for market in markets}
    for market in markets:
        scope = carries.scope("V10:" + market)
        breaks = []
        for slot in placed:
            matching = sorted(
                (r for r in rules
                 if r["market_ref"] == market
                 and r["content_ref"] == slot["content_ref"]
                 and r["window_from"] <= tx_date <= r["window_to"]),
                key=lambda r: (r["precedence"], r["rule_id"]))
            winner = None
            if matching:
                overturning = [r for r in matching if r["override"] == "yes"]
                winner = overturning[-1] if overturning else matching[0]
            if winner is None:
                for item in slot["breaks"]:
                    breaks.append({
                        "break_ref": item["break_ref"],
                        "slot_id": slot["slot_id"],
                        "break_no": item["break_no"],
                        "origin": "BO_NATIONAL",
                        "position_frame": slot["start_frame"]
                        + item["position_frame"],
                        "daypart_ref": slot["daypart_ref"],
                        "avail_seconds": item["avail_seconds"],
                    })
                continue
            substituted[market][slot["slot_id"]] = winner
            library = substitutes.get(winner["substitute_ref"], [])
            for row in library:
                offset = scope.convert(
                    seconds_to_channel(int(row["nominal_offset_seconds"])))
                break_no = int(row["break_no"])
                breaks.append({
                    "break_ref": "sb_%s_%02d" % (
                        winner["substitute_ref"], break_no),
                    "slot_id": slot["slot_id"],
                    "break_no": break_no,
                    "origin": "BO_SUBSTITUTE",
                    "position_frame": slot["start_frame"] + offset,
                    "daypart_ref": slot["daypart_ref"],
                    "avail_seconds": int(row["avail_seconds"]),
                })
            override_rows.append([
                market, slot["slot_id"], slot["content_ref"],
                winner["rule_id"], winner["precedence"],
                winner["substitute_ref"], winner["override"],
                len(slot["breaks"]), len(library)])
        breaks.sort(key=lambda b: (b["position_frame"], b["break_ref"]))
        market_breaks[market] = breaks

    override_rows.sort(key=lambda r: (r[0], r[1]))
    art.delimited("market_overrides.csv", [
        "market_ref", "slot_id", "content_ref", "rule_id", "precedence",
        "substitute_ref", "override_flag", "national_break_count",
        "substitute_break_count"], override_rows, ",")

    # -- V9 break capacities
    for market in markets:
        scope = carries.scope("V9:" + market)
        for item in market_breaks[market]:
            item["capacity_frames"] = scope.convert(
                seconds_to_channel(item["avail_seconds"]))

    stream_records = []
    for market in markets:
        breaks = market_breaks[market]
        published = []
        for item in breaks:
            published.append({
                "break_ref": item["break_ref"],
                "slot_id": item["slot_id"],
                "break_no": item["break_no"],
                "origin": item["origin"],
                "position_frame": item["position_frame"],
                "capacity_frames": item["capacity_frames"],
                "daypart_ref": item["daypart_ref"],
                "hour_label": hour_of(item["position_frame"]),
            })
        art.json_doc("market_avails_%s.json" % market, {
            "market_ref": market,
            "break_count": len(published),
            "capacity_frames_total": sum(
                item["capacity_frames"] for item in published),
            "carry_residual_capacity": fmt_ratio(
                carries.scope("V9:" + market).held),
            "carry_residual_substitute": fmt_ratio(
                carries.scope("V10:" + market).held),
            "breaks": published,
        })
        for item in published:
            record = dict(item)
            record["market_ref"] = market
            stream_records.append(record)
    stream_records.sort(key=lambda r: (
        r["market_ref"], r["position_frame"], r["break_ref"]))
    art.jsonl("market_avail_stream.jsonl", stream_records)

    # -- V9 admission
    orders = read_jsonl(path("spot_order_book.jsonl"))
    journal = defaultdict(list)
    for row in read_delimited(path("clearance_state_journal.csv"), ","):
        journal[row["clearance_ref"]].append(row)
    clearance = {}
    for ref, rows in journal.items():
        clearance[ref] = max(
            rows, key=lambda r: int(r["journal_seq"]))["clearance_state"]

    cards = defaultdict(list)
    for row in read_delimited(path("rate_card_book.csv"), ","):
        cards[row["rate_card_ref"]].append(row)
    eligible_card = {}
    earliest_card = {}
    for ref, rows in cards.items():
        earliest_card[ref] = min(row["effective_from"] for row in rows)
        usable = [row for row in rows if row["effective_from"] <= tx_date]
        if usable:
            eligible_card[ref] = max(usable, key=lambda r: (
                r["effective_from"], int(r["card_revision"])))

    national_slot = {}
    for slot_id, rows in break_plan.items():
        for row in rows:
            national_slot["bk_%s_%02d" % (slot_id, int(row["break_no"]))] = \
                slot_id

    advertisers = read_delimited(path("advertiser_register.csv"), ",")
    currency_of = {row["advertiser_ref"]: row["settlement_currency"]
                   for row in advertisers}
    exponents = read_json(path("currency_minor_units.json"))["exponents"]

    spot_frames = {}
    by_advertiser = defaultdict(list)
    for order in orders:
        by_advertiser[order["advertiser_ref"]].append(order)
    for advertiser in sorted(by_advertiser):
        scope = carries.scope("V11:" + advertiser)
        for order in sorted(by_advertiser[advertiser],
                            key=lambda o: o["order_ref"]):
            spot_frames[order["order_ref"]] = scope.convert(
                seconds_to_channel(order["nominal_seconds"]))

    admitted = []
    deferrals = []
    for market in markets:
        lookup = {item["break_ref"]: item for item in market_breaks[market]}
        filled = defaultdict(int)
        taken = defaultdict(list)
        pool = [o for o in orders if o["market_ref"] == market]
        pool.sort(key=lambda o: (o["priority_band"], o["order_ref"]))
        for order in pool:
            frames = spot_frames[order["order_ref"]]
            break_ref = order["break_ref"]
            reason = None
            if clearance.get(order["clearance_ref"]) == "CL_HELD":
                reason = ("DF_CLEARANCE_HELD", 1)
            elif national_slot.get(break_ref) in substituted[market]:
                reason = ("DF_MARKET_BLACKED", 2)
            elif break_ref not in lookup:
                reason = ("DF_NO_MATCHING_BREAK", 3)
            elif order["daypart_ref"] != lookup[break_ref]["daypart_ref"]:
                reason = ("DF_DAYPART_MISMATCH", 4)
            elif order["rate_card_ref"] not in eligible_card:
                reason = ("DF_NO_RATE_CARD", 5)
            elif filled[break_ref] + frames > lookup[break_ref][
                    "capacity_frames"]:
                reason = ("DF_BREAK_FULL", 6)
            else:
                position = len(taken[break_ref]) + 1
                for seat, klass in taken[break_ref]:
                    if klass == order["separation_class"] \
                            and position - seat < separation_minimum:
                        reason = ("DF_SEPARATION", 7)
                        break
            if reason is not None:
                deferrals.append({
                    "order_ref": order["order_ref"],
                    "market_ref": market,
                    "break_ref": break_ref,
                    "deferral_reason": in_vocabulary(
                        reason[0], deferral_vocabulary),
                    "predicate_index": reason[1],
                    "spot_frames": frames,
                })
                continue
            item = lookup[break_ref]
            start = item["position_frame"] + filled[break_ref]
            position = len(taken[break_ref]) + 1
            taken[break_ref].append((position, order["separation_class"]))
            filled[break_ref] += frames
            admitted.append({
                "order": order,
                "market_ref": market,
                "break_ref": break_ref,
                "break_position_frame": item["position_frame"],
                "position_in_break": position,
                "spot_frames": frames,
                "start_frame": start,
                "end_frame": start + frames,
            })

    admitted.sort(key=lambda a: (
        a["market_ref"], a["break_position_frame"], a["break_ref"],
        a["position_in_break"]))
    art.delimited("avail_plan.tsv", [
        "market_ref", "break_ref", "break_position_frame", "position_in_break",
        "order_ref", "advertiser_ref", "separation_class", "spot_frames",
        "start_frame", "end_frame", "hour_label"], [[
            a["market_ref"], a["break_ref"], a["break_position_frame"],
            a["position_in_break"], a["order"]["order_ref"],
            a["order"]["advertiser_ref"], a["order"]["separation_class"],
            a["spot_frames"], a["start_frame"], a["end_frame"],
            hour_of(a["start_frame"])] for a in admitted], "\t")

    deferrals.sort(key=lambda d: (d["order_ref"], d["market_ref"]))
    art.jsonl("deferral_ledger.jsonl", deferrals)

    # -- V13 minutage compliance
    dayparts = {row["hour_label"]: row["daypart_ref"]
                for row in read_delimited(path("daypart_calendar.csv"), ",")}
    by_market = defaultdict(list)
    for spot in admitted:
        by_market[spot["market_ref"]].append(spot)
    unbilled = defaultdict(int)
    minutage_rows = []
    breach_count = 0
    market_totals = {}
    for market in markets:
        market_total = 0
        for index, label in enumerate(hour_labels):
            low = index * hour_frames
            high = low + hour_frames
            if index == len(hour_labels) - 1:
                high = None
            inside = []
            frames_total = 0
            for spot in by_market[market]:
                start = max(spot["start_frame"], low)
                end = spot["end_frame"] if high is None \
                    else min(spot["end_frame"], high)
                overlap = end - start
                if overlap > 0:
                    inside.append((spot, overlap))
                    frames_total += overlap
            minutes = market_minutes.get((market, label), standing_minutes)
            cap = cap_frames_of(minutes)
            breach = frames_total > cap
            if breach:
                breach_count += 1
                excess = frames_total - cap
                inside.sort(key=lambda pair: pair[0]["order"]["order_ref"],
                            reverse=True)
                inside.sort(key=lambda pair: pair[0]["start_frame"],
                            reverse=True)
                for spot, overlap in inside:
                    if excess == 0:
                        break
                    give = min(overlap, excess)
                    unbilled[spot["order"]["order_ref"]] += give
                    excess -= give
            market_total += frames_total
            minutage_rows.append([
                market, label, dayparts[label], frames_total,
                fmt_ratio(Fraction(frames_total * ch_den, ch_num)), cap,
                cap - frames_total,
                "MB_BREACH" if breach else "MB_WITHIN"])
        market_totals[market] = market_total

    minutage_rows.sort(key=lambda r: (r[0], r[1]))
    art.delimited("minutage_report.csv", [
        "market_ref", "hour_label", "daypart_ref", "advertising_frames",
        "advertising_seconds", "cap_frames", "headroom_frames",
        "breach_state"], minutage_rows, ",")

    # -- V11 settlement
    def grains_for(frames):
        if frames <= 0:
            return 0
        value = Fraction(frames) / grain_frames
        whole = value.numerator // value.denominator
        return whole if value == whole else whole + 1

    settlement_rows = []
    exceptions = []
    per_advertiser = defaultdict(lambda: {
        "admitted_spots": 0, "deferred_spots": 0, "delivered_frames": 0,
        "gross_minor": 0, "commission_minor": 0, "net_minor": 0})
    spot_money = {}
    for spot in sorted(admitted, key=lambda a: (
            a["order"]["order_ref"], a["market_ref"])):
        order = spot["order"]
        advertiser = order["advertiser_ref"]
        card = eligible_card[order["rate_card_ref"]]
        delivered = spot["spot_frames"]
        lost = unbilled[order["order_ref"]]
        billed = delivered - lost
        grains = grains_for(billed)
        price = int(card["minor_per_grain"])
        gross = grains * price
        rate = commission.get(advertiser, Fraction(0))
        fee = round_half_even(Fraction(gross) * rate)
        net = gross - fee
        currency = currency_of[advertiser]
        exponent = int(exponents[currency])
        settlement_rows.append([
            order["order_ref"], advertiser, spot["market_ref"],
            spot["break_ref"], currency, delivered, lost, grains,
            order["rate_card_ref"], card["effective_from"], price, gross,
            fee, net, fmt_major(gross, exponent)])
        bucket = per_advertiser[advertiser]
        bucket["admitted_spots"] += 1
        bucket["delivered_frames"] += delivered
        bucket["gross_minor"] += gross
        bucket["commission_minor"] += fee
        bucket["net_minor"] += net
        spot_money[order["order_ref"]] = {
            "advertiser_ref": advertiser,
            "delivered": delivered,
            "billed": billed,
            "price": price,
        }
        if delivered == 0:
            exceptions.append({
                "order_ref": order["order_ref"],
                "exception_code": "EX_ZERO_DELIVERY",
                "rate_card_ref": order["rate_card_ref"],
                "detail": "admitted spot occupies no channel frame",
            })

    art.delimited("settlement_ledger.psv", [
        "order_ref", "advertiser_ref", "market_ref", "break_ref", "currency",
        "delivered_frames", "unbilled_frames", "billable_grains",
        "rate_card_ref", "effective_from", "minor_per_grain", "gross_minor",
        "commission_minor", "net_minor", "gross_major"], settlement_rows, "|")

    for order in orders:
        if order["rate_card_ref"] not in eligible_card:
            exceptions.append({
                "order_ref": order["order_ref"],
                "exception_code": "EX_NO_CARD",
                "rate_card_ref": order["rate_card_ref"],
                "detail": "earliest card dated " + earliest_card.get(
                    order["rate_card_ref"], ""),
            })
    exceptions.sort(key=lambda e: (e["order_ref"], e["exception_code"]))
    art.jsonl("exception_ledger.jsonl", exceptions)

    order_by_ref = {order["order_ref"]: order for order in orders}
    for record in deferrals:
        advertiser = order_by_ref[record["order_ref"]]["advertiser_ref"]
        per_advertiser[advertiser]["deferred_spots"] += 1

    # -- V12 make good
    raw_obligations = defaultdict(list)
    for record in deferrals:
        order = order_by_ref[record["order_ref"]]
        if order["rate_card_ref"] not in eligible_card:
            continue
        card = eligible_card[order["rate_card_ref"]]
        value = grains_for(record["spot_frames"]) * int(card["minor_per_grain"])
        raw_obligations[order["advertiser_ref"]].append({
            "order_ref": record["order_ref"],
            "deferral_reason": record["deferral_reason"],
            "raw_minor": value,
        })
    for order_ref, money in spot_money.items():
        lost_grains = grains_for(money["delivered"]) \
            - grains_for(money["billed"])
        if lost_grains > 0:
            raw_obligations[money["advertiser_ref"]].append({
                "order_ref": order_ref,
                "deferral_reason": in_vocabulary(
                    "DF_OVER_CAP", deferral_vocabulary),
                "raw_minor": lost_grains * money["price"],
            })

    makegood_entries = []
    makegood_total = 0
    makegood_per_advertiser = defaultdict(int)
    over_cap_count = 0
    for advertiser in sorted(set(raw_obligations) | {
            key for key, value in per_advertiser.items()
            if value["admitted_spots"]}):
        obligations = sorted(raw_obligations.get(advertiser, []),
                             key=lambda o: o["order_ref"])
        over_cap_count += sum(
            1 for o in obligations if o["deferral_reason"] == "DF_OVER_CAP")
        day_gross = per_advertiser[advertiser]["gross_minor"]
        cap = (day_gross * cap_num) // cap_den
        raw_total = sum(o["raw_minor"] for o in obligations)
        if raw_total <= cap:
            allocated = [o["raw_minor"] for o in obligations]
        else:
            shares = [Fraction(o["raw_minor"] * cap, raw_total)
                      for o in obligations]
            allocated = [share.numerator // share.denominator
                         for share in shares]
            left = cap - sum(allocated)
            ranking = sorted(range(len(obligations)), key=lambda i: (
                -(shares[i] - allocated[i]), obligations[i]["order_ref"]))
            for position in range(left):
                allocated[ranking[position]] += 1
        published = []
        for obligation, value in zip(obligations, allocated):
            published.append({
                "order_ref": obligation["order_ref"],
                "deferral_reason": obligation["deferral_reason"],
                "raw_minor": obligation["raw_minor"],
                "allocated_minor": value,
            })
        total = sum(allocated)
        makegood_total += total
        makegood_per_advertiser[advertiser] = total
        makegood_entries.append({
            "advertiser_ref": advertiser,
            "day_gross_minor": day_gross,
            "cap_minor": cap,
            "raw_total_minor": raw_total,
            "allocated_total_minor": total,
            "obligations": published,
        })

    art.json_doc("makegood_ledger.json", {
        "advertisers": makegood_entries,
        "allocated_total_minor": makegood_total,
        "cap_num": cap_num,
        "cap_den": cap_den,
    })

    summary_rows = []
    for row in sorted(advertisers, key=lambda r: r["advertiser_ref"]):
        advertiser = row["advertiser_ref"]
        bucket = per_advertiser[advertiser]
        currency = currency_of[advertiser]
        exponent = int(exponents[currency])
        summary_rows.append([
            advertiser, currency, bucket["admitted_spots"],
            bucket["deferred_spots"], bucket["delivered_frames"],
            bucket["gross_minor"], bucket["commission_minor"],
            bucket["net_minor"], makegood_per_advertiser[advertiser],
            fmt_major(bucket["gross_minor"], exponent)])
    art.delimited("advertiser_summary.csv", [
        "advertiser_ref", "currency", "admitted_spots", "deferred_spots",
        "delivered_frames", "gross_minor", "commission_minor", "net_minor",
        "makegood_minor", "gross_major"], summary_rows, ",")

    # -- V4 carry ledger
    scope_entries = []
    conversion_count = 0
    residual_total = Fraction(0)
    for name in sorted(carries.scopes):
        scope = carries.scopes[name]
        conversion_count += scope.conversions
        residual_total += scope.held
        scope_entries.append({
            "scope": name,
            "conversions": scope.conversions,
            "residual": fmt_ratio(scope.held),
        })
    art.json_doc("carry_ledger.json", {
        "scopes": scope_entries,
        "scope_count": len(scope_entries),
        "conversion_count": conversion_count,
        "residual_total": fmt_ratio(residual_total),
    })

    # -- V14 reconciliation
    prior = {row["slot_id"]: row
             for row in read_delimited(path("prior_conform_register.csv"), ",")}
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<reconciliation channel_ref="%s" transmission_date="%s">'
             % (channel_ref, tx_date)]
    agreeing = differing = 0
    abs_start = abs_material = 0
    for row in sorted(placement_rows, key=lambda r: r[0]):
        slot_id = row[0]
        start = row[5]
        material = row[6]
        breaks = len(break_plan.get(slot_id, [])) if row[13] == "PL_PLACED" \
            else 0
        record = prior.get(slot_id)
        prior_start = int(record["prior_start_frame"]) if record else 0
        prior_material = int(record["prior_material_frames"]) if record else 0
        prior_breaks = int(record["prior_break_count"]) if record else 0
        start_delta = start - prior_start
        material_delta = material - prior_material
        break_delta = breaks - prior_breaks
        if start_delta == 0 and material_delta == 0 and break_delta == 0:
            agreeing += 1
        else:
            differing += 1
        abs_start += abs(start_delta)
        abs_material += abs(material_delta)
        lines.append(
            '  <slot slot_id="%s" placement_state="%s" prior_start_frame="%d"'
            ' start_frame="%d" start_delta="%d" prior_material_frames="%d"'
            ' material_frames="%d" material_delta="%d" prior_break_count="%d"'
            ' break_count="%d" break_delta="%d"/>'
            % (slot_id, row[13], prior_start, start, start_delta,
               prior_material, material, material_delta, prior_breaks, breaks,
               break_delta))
    lines.append(
        '  <totals slots="%d" agreeing="%d" differing="%d"'
        ' absolute_start_delta="%d" absolute_material_delta="%d"/>'
        % (len(placement_rows), agreeing, differing, abs_start, abs_material))
    lines.append("</reconciliation>")
    art.text("reconciliation.xml", "\n".join(lines))

    # -- the transmitted day
    ini = ["[channel]",
           "channel_ref = %s" % channel_ref,
           "transmission_date = %s" % tx_date,
           "day_start_tc = %s" % day_start_tc,
           "day_end_frame = %d" % day_end_frame,
           "placed_slot_count = %d" % len(placed)]
    for slot in placed:
        ini.append("")
        ini.append("[slot:%s]" % slot["slot_id"])
        ini.append("content_ref = %s" % slot["content_ref"])
        ini.append("sequence_no = %d" % slot["sequence_no"])
        ini.append("start_frame = %d" % slot["start_frame"])
        ini.append("start_tc = %s" % frames_to_tc(
            (day_start_frames + slot["start_frame"]) % day_frames,
            ch_base, ch_drop))
        ini.append("transmitted_frames = %d" % slot["transmitted_frames"])
        ini.append("trim_frames = %d" % slot["trim_frames"])
        ini.append("break_count = %d" % len(slot["breaks"]))
    art.text("playout_schedule.ini", "\n".join(ini))

    # -- the summaries
    gross_total = sum(row[11] for row in settlement_rows)
    report = ["# Transmission day report", ""]
    for key, value in (
            ("channel_ref", channel_ref),
            ("transmission_date", tx_date),
            ("instance_ref", instance_ref),
            ("live_control_set", control_set),
            ("scheduled_slots", len(slots)),
            ("placed_slots", len(placed)),
            ("dropped_slots", len(dropped)),
            ("day_end_frame", day_end_frame),
            ("corrections", len(trace)),
            ("admitted_spots", len(admitted)),
            ("deferred_spots", len(deferrals)),
            ("gross_minor_total", gross_total),
            ("makegood_minor_total", makegood_total)):
        report.append("- %s: %s" % (key, value))
    report.append("")
    report.append("## Correction totals")
    report.append("")
    for reason in sorted(correction_vocabulary):
        report.append("- %s: %d" % (reason, totals.get(reason, 0)))
    report.append("")
    report.append("## Deferral totals")
    report.append("")
    deferral_totals = defaultdict(int)
    for record in deferrals:
        deferral_totals[record["deferral_reason"]] += 1
    for reason in sorted(deferral_vocabulary):
        count = over_cap_count if reason == "DF_OVER_CAP" \
            else deferral_totals.get(reason, 0)
        report.append("- %s: %d" % (reason, count))
    art.text("day_report.md", "\n".join(report))

    compliance = ["# Compliance summary", ""]
    for key, value in (
            ("regulatory_minutes_per_clock_hour", standing_minutes),
            ("cap_frames", standing_cap),
            ("separation_minimum_positions", separation_minimum),
            ("billing_grain_seconds", grain_seconds),
            ("snap_tolerance_frames", snap_tolerance),
            ("breach_hours", breach_count)):
        compliance.append("- %s: %s" % (key, value))
    compliance.append("")
    compliance.append("## Advertising frames by market")
    compliance.append("")
    for market in markets:
        compliance.append("- %s: %d" % (market, market_totals[market]))
    compliance.append("")
    compliance.append("## Breach hours")
    compliance.append("")
    breaches = [row for row in minutage_rows if row[7] == "MB_BREACH"]
    if breaches:
        for row in breaches:
            compliance.append("- %s %s frames %d over %d"
                              % (row[0], row[1], row[3], row[5]))
    else:
        compliance.append("- none")
    art.text("compliance_summary.md", "\n".join(compliance))

    digest = hashlib.sha256()
    for name in CORE_ORDER:
        digest.update(art.blobs[name])
    art.json_doc("manifest.json", {
        "instance_ref": instance_ref,
        "channel_ref": channel_ref,
        "transmission_date": tx_date,
        "artifact_count": 25,
        "core_order": CORE_ORDER,
        "digest": digest.hexdigest(),
        "slot_count": len(slots),
        "placed_slot_count": len(placed),
        "dropped_slot_count": len(dropped),
        "admitted_spot_count": len(admitted),
        "deferred_spot_count": len(deferrals),
        "breach_hour_count": breach_count,
        "live_control_set": settled_name,
        "snap_tolerance_frames": snap_tolerance,
        "makegood_cap_num": cap_num,
        "makegood_cap_den": cap_den,
        "separation_minimum_positions": separation_minimum,
        "billing_grain_seconds": grain_seconds,
        "regulatory_minutes_per_clock_hour": standing_minutes,
        "day_end_frame": day_end_frame,
    })

    art.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    conform(args.data, args.out)


if __name__ == "__main__":
    main()
