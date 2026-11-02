#!/usr/bin/env python3
"""Conform one transmission day of a regional playout channel.

Derives the whole day from the records in a data directory and writes
twenty five artifacts into an output directory.  Nothing about any
particular day is built in: every figure, identifier and constant is read
from the records, including the three constants published only in the
compliance memorandum and the contract terms published only in the
settled sheet of the terms workbook.

All arithmetic is exact rational or whole number arithmetic.  Rounding
happens only when a value is written.
"""

import argparse
import bisect
import collections
import csv
import datetime
import hashlib
import json
import os
import re
import sys
import zipfile
import zlib
from fractions import Fraction
from xml.etree import ElementTree as ET

DEFAULT_DATA = "/app/data"
DEFAULT_OUT = "/app/out"

ZERO = Fraction(0)

# The core order the digest runs over, from
# serialisation_and_digest_contract.md.
CORE_ORDER = [
    "asset_register.csv",
    "segment_conform.csv",
    "break_positions.csv",
    "slot_placement.csv",
    "avail_plan.tsv",
    "settlement_ledger.psv",
    "minutage_report.csv",
]

# The artifacts whose names do not depend on the records of the day.  The per
# market avail files are named for their market reference, so they are
# resolved against the market register when the day is run.
FIXED_ARTIFACTS = [
    "asset_register.csv",
    "segment_conform.csv",
    "break_positions.csv",
    "slot_placement.csv",
    "conform_trace.json",
    "filler_plan.csv",
    "avail_plan.tsv",
    "deferral_ledger.jsonl",
    "market_overrides.csv",
    "market_avail_stream.jsonl",
    "settlement_ledger.psv",
    "makegood_ledger.json",
    "exception_ledger.jsonl",
    "advertiser_summary.csv",
    "minutage_report.csv",
    "carry_ledger.json",
    "reconciliation.xml",
    "playout_schedule.ini",
    "day_report.md",
    "compliance_summary.md",
    "manifest.json",
]

PASSED_STATES = ("QC_PASSED", "QC_PASSED_WITH_NOTES")


# ---------------------------------------------------------------- rounding

def floor_frac(x):
    """Floor of a Fraction toward minus infinity, as an int."""
    return x.numerator // x.denominator


def round_half_even(value, places):
    """Render a Fraction to a fixed number of decimal places, halves to even.

    Returns the exact digits with no exponent and no negative zero.
    """
    negative = value < 0
    v = -value if negative else value
    scale = 10 ** places
    scaled = v * scale
    floor_part = scaled.numerator // scaled.denominator
    rem = scaled - floor_part
    if rem > Fraction(1, 2):
        floor_part += 1
    elif rem == Fraction(1, 2):
        if floor_part % 2 == 1:
            floor_part += 1
    digits = str(floor_part).rjust(places + 1, "0")
    if places == 0:
        out = digits
    else:
        out = digits[:-places] + "." + digits[-places:]
    if negative and floor_part != 0:
        out = "-" + out
    return out


def ratio_text(value):
    return round_half_even(Fraction(value), 10)


# ------------------------------------------------------------ timecode

def parse_tc(label):
    """Split a timecode label into hh, mm, ss, ff.  The separator between
    the seconds and the frames is not evidence of anything and is ignored."""
    m = re.match(r"^(\d+):(\d+):(\d+)[;:](\d+)$", label.strip())
    if not m:
        raise ValueError("bad timecode label %r" % label)
    return tuple(int(g) for g in m.groups())


def tc_frames(label, base, drop):
    """Whole frame count of a label at base b under the drop frame rule."""
    hh, mm, ss, ff = parse_tc(label)
    m = hh * 60 + mm
    total = ((hh * 60 + mm) * 60 + ss) * base + ff
    if drop:
        total -= (base * 2 // 30) * (m - m // 10)
    return total


def tc_day_frames(base, drop):
    """One whole timecode day at base b."""
    if drop:
        return base * 86400 - (base * 2 // 30) * 1296
    return base * 86400


def tc_label_from_frames(frames, base, drop):
    """The label of a whole frame count, taken into one timecode day."""
    day = tc_day_frames(base, drop)
    n = frames % day
    if drop:
        # invert: ((m*60)+ss)*b + ff - (b*2//30)*(m - m//10)
        # solve by search over minutes, the day is at most 1440 of them.
        drops_per_ten = base * 2 // 30
        lo, hi = 0, 1440
        while lo < hi:
            mid = (lo + hi) // 2
            start = start_of_minute(mid, base, drops_per_ten)
            if start <= n:
                lo = mid + 1
            else:
                hi = mid
        minute = lo - 1
        start = start_of_minute(minute, base, drops_per_ten)
        off = n - start
        ff = off % base
        secs = off // base
        ss = secs % 60
        hh = minute // 60
        mm = minute % 60
    else:
        ff = n % base
        secs = n // base
        ss = secs % 60
        minute = secs // 60
        hh = minute // 60
        mm = minute % 60
    return "%02d:%02d:%02d;%02d" % (hh, mm, ss, ff)


def start_of_minute(minute, base, drops_per_ten):
    """Frames elapsed by the start of a minute, at a drop base."""
    dropped = drops_per_ten * (minute - minute // 10)
    return minute * 60 * base - dropped


# ------------------------------------------------------------ carry scopes

class CarryScopes(object):
    """The named accumulators a conversion carries its discarded fraction
    into.  A scope releases a whole frame as soon as the held fraction
    reaches one, which is what taking the floor of the sum does."""

    def __init__(self):
        self.held = {}
        self.conversions = {}

    def open(self, scope):
        """Open a scope with a held fraction of zero."""
        if scope not in self.held:
            self.held[scope] = ZERO
            self.conversions[scope] = 0

    def convert(self, scope, exact):
        """Convert an exact rational channel frame count into whole frames,
        carrying the discarded fraction inside the named scope."""
        self.open(scope)
        total = exact + self.held[scope]
        whole = total.numerator // total.denominator
        self.held[scope] = total - whole
        self.conversions[scope] += 1
        return whole

    def residual(self, scope):
        self.open(scope)
        return self.held[scope]

    def scope_names(self):
        return sorted(self.held)


def channel_frames_of_frames(source_frames, rate_num, rate_den):
    """Exact channel frame count occupied by n frames at rate p/q."""
    return Fraction(source_frames * 30000 * rate_den, 1001 * rate_num)


def channel_frames_of_seconds(seconds):
    """Exact channel frame count occupied by a duration in seconds."""
    return Fraction(seconds * 30000, 1001)


# ------------------------------------------------------------ input readers

def read_csv(path, delimiter=","):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def read_jsonl(path):
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_isoz(text):
    """An ISO 8601 instant with an explicit UTC offset, as an aware value."""
    text = text.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    dt = datetime.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def parse_date(text):
    return datetime.date.fromisoformat(text.strip())


# ------------------------------------------------------------ xlsx

XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _column_index(ref):
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_xlsx(path):
    """Every sheet of a workbook, as a list of rows of cell values.

    A shared string may be split into several formatted runs; its value is
    the concatenation of every run, in order.
    """
    sheets = []
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall(XLSX_NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(XLSX_NS + "t")))
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        targets = {}
        for rel in rels.findall(PKG_REL_NS + "Relationship"):
            targets[rel.get("Id")] = rel.get("Target")
        for sheet in wb.find(XLSX_NS + "sheets").findall(XLSX_NS + "sheet"):
            rid = sheet.get(XLSX_NS + "id") or sheet.get(r"%sid" % "r")
            if rid is None:
                rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = targets.get(rid, "")
            if target.startswith("/"):
                target_path = target[1:]
            else:
                target_path = "xl/" + target
            root = ET.fromstring(zf.read(target_path))
            rows = []
            for row in root.find(XLSX_NS + "sheetData").findall(XLSX_NS + "row"):
                cells = {}
                for c in row.findall(XLSX_NS + "c"):
                    idx = _column_index(c.get("r", "A1"))
                    v = c.find(XLSX_NS + "v")
                    if c.get("t") == "s":
                        if v is not None:
                            cells[idx] = shared[int(v.text)]
                    elif c.get("t") == "inlineStr":
                        is_el = c.find(XLSX_NS + "is")
                        if is_el is not None:
                            cells[idx] = "".join(t.text or "" for t in is_el.iter(XLSX_NS + "t"))
                    else:
                        cells[idx] = v.text if v is not None else None
                rows.append(cells)
            sheets.append({"name": sheet.get("name"), "rows": rows})
    return sheets


def workbook_terms(path, control_set):
    """The terms of the settled sheet: scalars and per advertiser commission.

    The settled sheet is the one whose control set cell, the first cell pair
    of row one, equals the configured control set.  The sheet name and the
    sheet position settle nothing.
    """
    scalars = {}
    commissions = {}
    chosen = None
    for sheet in read_xlsx(path):
        rows = sheet["rows"]
        if not rows:
            continue
        first = rows[0]
        if first.get(0) != "control_set":
            continue
        if first.get(1) != control_set:
            continue
        if chosen is not None:
            raise ValueError("two sheets carry the control set %s" % control_set)
        chosen = sheet["name"]
        for cells in rows[1:]:
            key = cells.get(0)
            if key is None:
                continue
            key = key.strip()
            if key in ("snap_tolerance_frames", "makegood_cap_num", "makegood_cap_den"):
                scalars[key] = key_value(cells.get(1))
            elif key == "COMMISSION":
                adv = cells.get(1)
                num = key_value(cells.get(3))
                den = key_value(cells.get(4))
                commissions[adv] = (Fraction(num), Fraction(den))
    if chosen is None:
        raise ValueError("no workbook sheet carries the control set %s" % control_set)
    return {"sheet_name": chosen, "scalars": scalars, "commissions": commissions}


def key_value(text):
    """A workbook cell value, as an int when it is whole, else as text."""
    if text is None:
        return ""
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return int(float(text))
    except ValueError:
        return text


# ------------------------------------------------------------ pdf

def read_pdf_lines(path):
    """Every text line of a PDF, in page and stream order.

    Streams are read in the order the page tree names them, so the lines of
    a document come out in reading order.  Both plain and Flate compressed
    content streams are handled.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    pages = []
    for m in re.finditer(rb"(\d+) 0 obj\s*<<(.*?)>>\s*stream\r?\n", data, re.S):
        header = m.group(2)
        if b"/Page" not in header:
            continue
        start = m.end()
        end = data.find(b"endstream", start)
        raw = data[start:end]
        try:
            content = zlib.decompress(raw)
        except zlib.error:
            content = raw
        lines = []
        for tm in re.finditer(rb"\((.*?)\)\s*Tj", content):
            lines.append(tm.group(1).decode("latin-1"))
        pages.append(lines)
    return pages


def memo_constants(path):
    """The settlement constants and the per market hour permitted minutes.

    Section 1 publishes the separation minimum, the billing grain and the
    standing regulatory minutes per clock hour.  Section 2 lists permitted
    minutes per market and clock hour, which govern wherever a market hour
    is listed.
    """
    pages = read_pdf_lines(path)
    lines = [ln for page in pages for ln in page]
    constants = {}
    section = None
    table = {}
    for line in lines:
        text = line.strip()
        upper = text.upper()
        if upper.startswith("SECTION"):
            m = re.match(r"SECTION\s+(\d+)", upper)
            section = int(m.group(1)) if m else None
            continue
        if section == 1:
            m = re.match(r"([a-z0-9_]+)\s*=\s*([0-9]+)$", text)
            if m:
                constants[m.group(1)] = int(m.group(2))
        elif section == 2:
            parts = [p.strip() for p in text.split("|")]
            if len(parts) >= 3 and re.match(r"^mk_[a-z]+$", parts[0]) \
                    and re.match(r"^H\d+$", parts[1]) \
                    and re.match(r"^\d+$", parts[2]):
                table[(parts[0], parts[1])] = int(parts[2])
    for key in ("separation_minimum_positions", "billing_grain_seconds",
                "regulatory_minutes_per_clock_hour"):
        if key not in constants:
            raise ValueError("the memorandum does not publish %s" % key)
    return {
        "constants": constants,
        "permitted": table,
    }


# ------------------------------------------------------------ V1 to V3

def canonicalise_assets(data):
    """V1 to V3.  One row per cluster of ingest attempts."""
    ingest = read_csv(os.path.join(data, "ingest_attempt_register.csv"))
    rates = read_csv(os.path.join(data, "rate_code_register.csv"))
    rate_by_code = {r["rate_code"]: r for r in rates}

    clusters = collections.OrderedDict()
    for row in ingest:
        clusters.setdefault(row["content_ref"], []).append(row)

    assets = {}
    for ref in clusters:
        rows = clusters[ref]
        anchor = min(rows, key=lambda r: (parse_isoz(r["received_at"]), r["ingest_id"]))
        passed = [r for r in rows if r["qc_state"] in PASSED_STATES]
        canonical = None
        if passed:
            best_rev = max(int(r["revision_no"]) for r in passed)
            tied = [r for r in passed if int(r["revision_no"]) == best_rev]
            canonical = min(tied, key=lambda r: r["ingest_id"])
        entry = {
            "content_ref": ref,
            "anchor": anchor,
            "anchor_ingest_id": anchor["ingest_id"],
            "house_no": anchor["house_no"],
            "canonical": canonical,
        }
        if canonical is None:
            entry.update({
                "included": False, "canonical_ingest_id": "", "revision_no": "",
                "qc_state": "", "rate_code": "", "rate_num": None, "rate_den": None,
                "tc_base": None, "drop_frame": None, "som_tc": "", "eom_tc": "",
                "source_frames": None, "channel_frames_exact": None,
            })
        else:
            rate = rate_by_code[canonical["rate_code"]]
            rate_num = int(rate["rate_num"])
            rate_den = int(rate["rate_den"])
            tc_base = int(rate["tc_base"])
            drop = (canonical["tc_mode"] == "DF") and (rate["df_allowed"].strip().lower() == "yes")
            day = tc_day_frames(tc_base, drop)
            start = tc_frames(canonical["som_tc"], tc_base, drop)
            end = tc_frames(canonical["eom_tc"], tc_base, drop)
            span = end - start
            if span < 0:
                span += day
            exact = channel_frames_of_frames(span, rate_num, rate_den)
            entry.update({
                "included": True,
                "canonical_ingest_id": canonical["ingest_id"],
                "revision_no": int(canonical["revision_no"]),
                "qc_state": canonical["qc_state"],
                "rate_code": canonical["rate_code"],
                "rate_num": rate_num, "rate_den": rate_den,
                "tc_base": tc_base, "drop_frame": drop,
                "som_tc": canonical["som_tc"], "eom_tc": canonical["eom_tc"],
                "source_frames": span,
                "channel_frames_exact": exact,
            })
        assets[ref] = entry
    return assets


# ------------------------------------------------------------ V4 and V5

def build_segments(data, assets, placed_slot_ids, slots, carry):
    """V4 and V5.  The parts of each placed slot and the material duration."""
    manifest = read_csv(os.path.join(data, "segment_part_manifest.tsv"), delimiter="\t")
    by_ref = collections.defaultdict(list)
    for row in manifest:
        by_ref[row["content_ref"]].append(row)

    parts_out = []
    material = {}
    flex_frames = {}
    flex_present = {}
    for sid in placed_slot_ids:
        asset = assets[slots[sid]["content_ref"]]
        rows = by_ref.get(asset["content_ref"], [])
        scope = "V4:" + sid
        if rows:
            ordered = sorted(rows, key=lambda r: int(r["part_no"]))
            kinds = [r["part_kind"] for r in ordered]
            head = 0
            while head < len(kinds) and kinds[head] == "PT_BLACK":
                head += 1
            tail = len(kinds) - 1
            while tail >= head and kinds[tail] == "PT_BLACK":
                tail -= 1
            total = 0
            flex = None
            flex_part_no = int(slots[sid]["flex_part_no"])
            for idx, row in enumerate(ordered):
                kind = row["part_kind"]
                part_no = int(row["part_no"])
                if idx < head:
                    state = "PR_TRIMMED_HEAD"
                elif idx > tail:
                    state = "PR_TRIMMED_TAIL"
                else:
                    state = "PR_RETAINED"
                if state != "PR_RETAINED":
                    frames = 0
                    source = 0
                    exact = ZERO
                    after = carry.residual(scope)
                else:
                    base = asset["tc_base"]
                    drop = asset["drop_frame"]
                    day = tc_day_frames(base, drop)
                    s = tc_frames(row["part_som_tc"], base, drop)
                    e = tc_frames(row["part_eom_tc"], base, drop)
                    source = e - s
                    if source < 0:
                        source += day
                    exact = channel_frames_of_frames(source, asset["rate_num"], asset["rate_den"])
                    frames = carry.convert(scope, exact)
                    total += frames
                    if part_no == flex_part_no:
                        flex = frames
                parts_out.append({
                    "slot_id": sid, "content_ref": asset["content_ref"],
                    "part_no": part_no, "part_kind": kind, "retention_state": state,
                    "source_frames": source, "channel_frames_exact": exact,
                    "channel_frames": frames, "carry_after": carry.residual(scope),
                })
            material[sid] = total
            flex_frames[sid] = flex if flex is not None else 0
            flex_present[sid] = flex is not None
        else:
            # R13: an asset with no parts transmits as one whole part.
            span = asset["source_frames"]
            exact = channel_frames_of_frames(span, asset["rate_num"], asset["rate_den"])
            frames = carry.convert(scope, exact)
            parts_out.append({
                "slot_id": sid, "content_ref": asset["content_ref"],
                "part_no": 0, "part_kind": "PT_PROGRAMME", "retention_state": "PR_RETAINED",
                "source_frames": span, "channel_frames_exact": exact,
                "channel_frames": frames, "carry_after": carry.residual(scope),
            })
            material[sid] = frames
            flex_frames[sid] = 0
            flex_present[sid] = False
    return parts_out, material, flex_frames, flex_present


# ------------------------------------------------------------ V6

def condition_breaks(data, placed_slot_ids, slots, assets, carry, tolerance):
    """V6.  The conditioned position of every national break."""
    plan = read_csv(os.path.join(data, "break_plan_register.csv"))
    index_rows = read_csv(os.path.join(data, "gop_index_channel.psv"), delimiter="|")
    index = collections.defaultdict(list)
    for row in index_rows:
        index[row["content_ref"]].append(int(row["idr_frame"]))
    for ref in index:
        index[ref].sort()
    by_slot = collections.defaultdict(list)
    for row in plan:
        by_slot[row["slot_id"]].append(row)

    breaks_out = []
    break_positions = {}
    for sid in placed_slot_ids:
        rows = sorted(by_slot.get(sid, []), key=lambda r: int(r["break_no"]))
        if not rows:
            break_positions[sid] = []
            continue
        ref = slots[sid]["content_ref"]
        frames = index.get(ref, [])
        has_index = bool(frames)
        scope = "V6:" + sid
        nominal_frames = []
        for row in rows:
            seconds = int(row["nominal_offset_seconds"])
            exact = channel_frames_of_seconds(seconds)
            nominal_frames.append(carry.convert(scope, exact))
        displacements = []
        records = []
        for i, row in enumerate(rows):
            nominal = nominal_frames[i]
            if i == len(rows) - 1:
                adjusted = max(0, nominal - sum(displacements))
            else:
                adjusted = nominal
            position, side = snap(adjusted, frames, has_index, tolerance)
            displacement = position - nominal
            displacements.append(displacement)
            records.append({
                "slot_id": sid, "break_no": int(row["break_no"]),
                "break_ref": "bk_%s_%02d" % (sid, int(row["break_no"])),
                "nominal_offset_seconds": int(row["nominal_offset_seconds"]),
                "nominal_frame": nominal,
                "adjusted_target_frame": adjusted,
                "position_frame": position,
                "snap_side": side,
                "displacement_frames": displacement,
                "avail_seconds": int(row["avail_seconds"]),
                "capacity_exact": channel_frames_of_seconds(int(row["avail_seconds"])),
                "carry_after": carry.residual(scope),
            })
        break_positions[sid] = records
        breaks_out.extend(records)
    return breaks_out, break_positions


def snap(target, frames, has_index, tolerance):
    """R14.  Snap a target onto an index frame."""
    if not has_index:
        return target, "SNAP_NONE"
    below = None
    above = None
    i = bisect.bisect_right(frames, target)
    if i > 0:
        below = frames[i - 1]
    if i < len(frames):
        above = frames[i]
    if below is not None and (target - below) <= tolerance:
        position = below
    elif above is not None:
        position = above
    elif below is not None:
        position = below
    else:  # pragma: no cover - an index that is empty is caught above
        return target, "SNAP_NONE"
    if position == target:
        return position, "SNAP_EXACT"
    if position < target:
        return position, "SNAP_BACK"
    return position, "SNAP_FORWARD"


# ------------------------------------------------------------ V7 and V8

def place_slots(ordered, material, flex_frames, flex_present, fillers,
                house_filler, corrections):
    """V7 and V8.  The placed start of every slot, the trims and the fills.

    The slots arrive in ascending scheduled offset, ties by slot id, which
    is the order the sequence number publishes.
    """
    trims = {row["slot_id"]: 0 for row in ordered}
    starts = {}
    fills = []
    placed_ids = []
    last_fixed_index = None
    cursor = 0
    for i, row in enumerate(ordered):
        sid = row["slot_id"]
        if not row["placed"]:
            # R17: a slot with no canonical asset is dropped from the day.
            row["sequence_no"] = 0
            starts[sid] = 0
            corrections.append({
                "sequence": 0, "slot_id": sid, "reason": "CR_SLOT_DROPPED",
                "frames": 0, "detail_slot": sid, "filler_ref": "",
            })
            continue
        placed_ids.append(sid)
        if row["junction_kind"] != "JK_FIXED":
            starts[sid] = cursor
            cursor = starts[sid] + material[sid] - trims[sid]
            continue
        target = row["offset"]
        if last_fixed_index is None:
            # The first slot of the day is a fixed junction, and the running
            # cursor opens at the day start.
            starts[sid] = target
            if cursor == target:
                corrections.append({
                    "slot_id": sid, "reason": "CR_NO_CHANGE", "frames": 0,
                    "detail_slot": sid, "filler_ref": "",
                })
                cursor = target + material[sid]
            elif cursor < target:
                gap = target - cursor
                filler, index = choose_filler(fillers, gap,
                                              row["daypart_ref"], house_filler)
                fills.append({
                    "slot_id": sid, "junction_offset_frame": cursor,
                    "gap_frames": gap, "filler_ref": filler,
                    "daypart_ref": row["daypart_ref"],
                    "selection_index": index,
                })
                corrections.append({
                    "slot_id": sid, "reason": "CR_FILL_INSERT", "frames": gap,
                    "detail_slot": sid, "filler_ref": filler,
                })
                cursor = target + material[sid]
            else:
                # There is nothing before the first fixed junction to walk
                # back over, so the whole overrun is a shortfall and the
                # junction is pinned anyway.
                corrections.append({
                    "slot_id": sid, "reason": "CR_TRIM_SHORTFALL",
                    "frames": cursor - target, "detail_slot": sid,
                    "filler_ref": "",
                })
                cursor = target + material[sid]
            last_fixed_index = i
            continue
        if cursor > target:
            remove = trim_backwards(ordered, i, trims, flex_frames, flex_present,
                                    cursor - target, corrections)
            if remove > 0:
                corrections.append({
                    "slot_id": sid, "reason": "CR_TRIM_SHORTFALL",
                    "frames": remove, "detail_slot": sid, "filler_ref": "",
                })
            # The slots between the previous fixed junction and this one are
            # re-placed from that junction's start with their trimmed
            # durations.
            cursor = starts[ordered[last_fixed_index]["slot_id"]]
            for j in range(last_fixed_index, i):
                inner = ordered[j]["slot_id"]
                if not ordered[j]["placed"]:
                    continue
                starts[inner] = cursor
                cursor = starts[inner] + material[inner] - trims[inner]
            starts[sid] = target
            cursor = target + material[sid] - trims[sid]
            last_fixed_index = i
            continue
        if cursor < target:
            gap = target - cursor
            filler, index = choose_filler(fillers, gap, row["daypart_ref"],
                                          house_filler)
            fills.append({
                "slot_id": sid, "junction_offset_frame": cursor,
                "gap_frames": gap, "filler_ref": filler,
                "daypart_ref": row["daypart_ref"], "selection_index": index,
            })
            corrections.append({
                "slot_id": sid, "reason": "CR_FILL_INSERT", "frames": gap,
                "detail_slot": sid, "filler_ref": filler,
            })
            starts[sid] = target
            cursor = target + material[sid]
            last_fixed_index = i
            continue
        corrections.append({
            "slot_id": sid, "reason": "CR_NO_CHANGE", "frames": 0,
            "detail_slot": sid, "filler_ref": "",
        })
        starts[sid] = target
        cursor = target + material[sid]
        last_fixed_index = i
    return starts, trims, fills, placed_ids


def trim_backwards(ordered, junction_index, trims, flex_frames, flex_present,
                   remove, corrections):
    """R18.  Trim flexible parts walking back from the slot immediately
    before a fixed junction, and stop at the previous fixed junction, that
    junction's own slot included.  Returns the frames it could not remove."""
    j = junction_index - 1
    first = True
    while j >= 0 and remove > 0:
        row = ordered[j]
        sid = row["slot_id"]
        if row["placed"] and flex_present.get(sid, False):
            available = flex_frames[sid] - trims[sid]
            if available > 0:
                take = min(available, remove)
                trims[sid] += take
                remove -= take
                corrections.append({
                    "slot_id": ordered[junction_index]["slot_id"],
                    "reason": "CR_TRIM_FLEX" if first else "CR_TRIM_BACKFILL",
                    "frames": take, "detail_slot": sid, "filler_ref": "",
                })
        if row["junction_kind"] == "JK_FIXED" and row["placed"]:
            break
        first = False
        j -= 1
    return remove


def choose_filler(fillers, gap, daypart, house_filler):
    """R19.  The first available predicate row that covers the gap."""
    for row in fillers:
        if row["stock_state"] != "FS_AVAILABLE":
            continue
        if row["daypart_ref"] != daypart and row["daypart_ref"] != "DP_ANY":
            continue
        if int(row["min_frames"]) <= gap <= int(row["max_frames"]):
            return row["filler_ref"], int(row["predicate_order"])
    return house_filler, 0


# ------------------------------------------------------------ V10

def market_break_sets(data, slots, placed_ids, starts, break_positions,
                      transmission_date, carry):
    """V10.  The break set of every market."""
    markets = sorted(read_csv(os.path.join(data, "market_register.csv")),
                     key=lambda r: r["market_ref"])
    market_refs = [r["market_ref"] for r in markets]
    rules = []
    for el in ET.parse(os.path.join(data, "blackout_rule_set.xml")).getroot():
        if not isinstance(el.tag, str):
            continue
        rules.append({
            "rule_id": el.get("rule_id"),
            "precedence": int(el.get("precedence")),
            "market_ref": el.get("market_ref"),
            "content_ref": el.get("content_ref"),
            "window_from": parse_date(el.get("window_from")),
            "window_to": parse_date(el.get("window_to")),
            "substitute_ref": el.get("substitute_ref"),
            "override": el.get("override") == "yes",
        })
    subs = collections.defaultdict(list)
    for row in read_csv(os.path.join(data, "substitution_library.csv")):
        subs[row["substitute_ref"]].append(row)
    for ref in subs:
        subs[ref].sort(key=lambda r: int(r["break_no"]))

    overrides = []
    substitutions = {}
    for market in market_refs:
        subs_by_slot = {}
        for sid in placed_ids:
            content = slots[sid]["content_ref"]
            matching = [r for r in rules
                        if r["market_ref"] == market
                        and r["content_ref"] == content
                        and r["window_from"] <= transmission_date <= r["window_to"]]
            if not matching:
                continue
            matching.sort(key=lambda r: (r["precedence"], r["rule_id"]))
            overturning = [r for r in matching if r["override"]]
            winner = overturning[-1] if overturning else matching[0]
            subs_by_slot[sid] = winner
            overrides.append({
                "market_ref": market, "slot_id": sid, "content_ref": content,
                "rule_id": winner["rule_id"], "precedence": winner["precedence"],
                "substitute_ref": winner["substitute_ref"],
                "override_flag": "yes" if winner["override"] else "no",
                "national_break_count": len(break_positions.get(sid, [])),
                "substitute_break_count": len(subs.get(winner["substitute_ref"], [])),
            })
        substitutions[market] = subs_by_slot

    market_sets = {}
    for market in market_refs:
        entries = []
        sub_scope = "V10:" + market
        for sid in placed_ids:
            row = slots[sid]
            start = starts[sid]
            winner = substitutions[market].get(sid)
            if winner is not None:
                for sub in subs.get(winner["substitute_ref"], []):
                    offset = carry.convert(
                        sub_scope,
                        channel_frames_of_seconds(int(sub["nominal_offset_seconds"])))
                    entries.append({
                        "market_ref": market,
                        "break_ref": "sb_%s_%02d" % (winner["substitute_ref"],
                                                     int(sub["break_no"])),
                        "slot_id": sid, "break_no": int(sub["break_no"]),
                        "origin": "BO_SUBSTITUTE",
                        "position_frame": start + offset,
                        "capacity_exact": channel_frames_of_seconds(
                            int(sub["avail_seconds"])),
                        "daypart_ref": row["daypart_ref"],
                    })
            else:
                for rec in break_positions.get(sid, []):
                    entries.append({
                        "market_ref": market,
                        "break_ref": rec["break_ref"],
                        "slot_id": sid, "break_no": rec["break_no"],
                        "origin": "BO_NATIONAL",
                        "position_frame": start + rec["position_frame"],
                        "capacity_exact": rec["capacity_exact"],
                        "daypart_ref": row["daypart_ref"],
                    })
        # Transmission order is ascending break position then break reference,
        # and the break capacities of a market convert in that order.
        entries.sort(key=lambda e: (e["position_frame"], e["break_ref"]))
        scope = "V9:" + market
        for e in entries:
            e["capacity_frames"] = carry.convert(scope, e["capacity_exact"])
        market_sets[market] = entries
    overrides.sort(key=lambda r: (r["market_ref"], r["slot_id"]))
    return market_refs, market_sets, overrides, substitutions




def market_break_record(entry, hours, frames_per_hour):
    """One break of a market break set, as a published record."""
    return {
        "break_ref": entry["break_ref"], "slot_id": entry["slot_id"],
        "break_no": entry["break_no"], "origin": entry["origin"],
        "position_frame": entry["position_frame"],
        "capacity_frames": entry["capacity_frames"],
        "daypart_ref": entry["daypart_ref"],
        "hour_label": hour_of(entry["position_frame"], hours, frames_per_hour),
    }

# ------------------------------------------------------------ V9

def derive_avails(data, market_refs, market_sets, substitutions, slots,
                  carry, transmission_date, cards, separation, national,
                  admission_reasons):
    """V9.  The admitted spots and the deferrals."""
    orders = read_jsonl(os.path.join(data, "spot_order_book.jsonl"))
    journal = collections.defaultdict(list)
    for row in read_csv(os.path.join(data, "clearance_state_journal.csv")):
        journal[row["clearance_ref"]].append(row)
    clearance = {}
    for ref, rows in journal.items():
        best = max(rows, key=lambda r: int(r["journal_seq"]))
        clearance[ref] = best["clearance_state"]

    # R21: the spot duration conversion happens once for the whole day, in
    # advertiser then order reference order, before any admission decision.
    durations = {}
    by_advertiser = collections.defaultdict(list)
    for order in orders:
        by_advertiser[order["advertiser_ref"]].append(order)
    for adv in sorted(by_advertiser):
        scope = "V11:" + adv
        for order in sorted(by_advertiser[adv], key=lambda o: o["order_ref"]):
            exact = channel_frames_of_seconds(int(order["nominal_seconds"]))
            durations[order["order_ref"]] = carry.convert(scope, exact)

    # R28: the rate card that prices a spot, resolved once for the day.
    card_by_order = {}
    for order in orders:
        card_by_order[order["order_ref"]] = resolve_card(
            cards, order["rate_card_ref"], transmission_date)

    # The one based position of each admission predicate among the reasons
    # the reference file lists, in the order it lists them.
    predicate_index = {reason: position for position, reason
                       in enumerate(admission_reasons, start=1)}

    admitted = []
    deferrals = []
    national_slots = {}
    for sid, records in national.items():
        for rec in records:
            national_slots[rec["break_ref"]] = sid
    for market in sorted(market_refs):
        breaks = market_sets[market]
        by_ref = {e["break_ref"]: e for e in breaks}
        in_market = [o for o in orders if o["market_ref"] == market]
        in_market.sort(key=lambda o: (int(o["priority_band"]), o["order_ref"]))
        frames_in = collections.defaultdict(int)
        positions = collections.defaultdict(list)
        for order in in_market:
            reason, index = admission(
                order, by_ref, national_slots, substitutions[market], clearance,
                card_by_order, frames_in, positions, durations,
                separation, predicate_index)
            if reason is None:
                bref = order["break_ref"]
                entry = by_ref[bref]
                pos = len(positions[bref]) + 1
                start = entry["position_frame"] + frames_in[bref]
                frames = durations[order["order_ref"]]
                positions[bref].append((pos, order["separation_class"]))
                frames_in[bref] += frames
                admitted.append({
                    "market_ref": market, "break_ref": bref,
                    "break_position_frame": entry["position_frame"],
                    "position_in_break": pos,
                    "order_ref": order["order_ref"],
                    "advertiser_ref": order["advertiser_ref"],
                    "separation_class": order["separation_class"],
                    "spot_frames": frames,
                    "start_frame": start,
                    "end_frame": start + frames,
                    "slot_id": entry["slot_id"],
                    "daypart_ref": entry["daypart_ref"],
                })
            else:
                deferrals.append({
                    "order_ref": order["order_ref"], "market_ref": market,
                    "break_ref": order["break_ref"],
                    "deferral_reason": reason,
                    "predicate_index": index,
                    "spot_frames": durations[order["order_ref"]],
                    "advertiser_ref": order["advertiser_ref"],
                    "rate_card_ref": order["rate_card_ref"],
                    "nominal_seconds": int(order["nominal_seconds"]),
                })
    admitted.sort(key=lambda a: (a["market_ref"], a["break_position_frame"],
                                 a["break_ref"], a["position_in_break"]))
    deferrals.sort(key=lambda d: (d["order_ref"], d["market_ref"]))
    return admitted, deferrals, durations, card_by_order


def resolve_card(cards, rate_card_ref, transmission_date):
    """R28 and R39.  The row that prices a spot, or None."""
    rows = cards.get(rate_card_ref, [])
    eligible = [r for r in rows if r["effective_from"] <= transmission_date]
    if not eligible:
        return None
    greatest = max(r["effective_from"] for r in eligible)
    tied = [r for r in eligible if r["effective_from"] == greatest]
    return max(tied, key=lambda r: r["card_revision"])


def admission(order, by_ref, national_slots, subs_by_slot, clearance,
              card_by_order, frames_in, positions, durations, separation,
              predicate_index):
    """R22.  The seven admission predicates, evaluated in order.  The first
    one that holds settles the order, and the order of the predicates is the
    whole of the rule: a held order that would also have overflowed its break
    is deferred as held, not as full."""
    bref = order["break_ref"]
    if clearance.get(order["clearance_ref"]) == "CL_HELD":
        return "DF_CLEARANCE_HELD", predicate_index["DF_CLEARANCE_HELD"]
    # The break an order names belongs to the slot it was planned against,
    # whether or not that break is transmitted in this market.
    owner = national_slots.get(bref)
    if owner is not None and owner in subs_by_slot:
        return "DF_MARKET_BLACKED", predicate_index["DF_MARKET_BLACKED"]
    entry = by_ref.get(bref)
    if entry is None:
        return "DF_NO_MATCHING_BREAK", predicate_index["DF_NO_MATCHING_BREAK"]
    if order["daypart_ref"] != entry["daypart_ref"]:
        return "DF_DAYPART_MISMATCH", predicate_index["DF_DAYPART_MISMATCH"]
    if card_by_order.get(order["order_ref"]) is None:
        return "DF_NO_RATE_CARD", predicate_index["DF_NO_RATE_CARD"]
    frames = durations[order["order_ref"]]
    if frames_in[bref] + frames > entry["capacity_frames"]:
        return "DF_BREAK_FULL", predicate_index["DF_BREAK_FULL"]
    n = len(positions[bref]) + 1
    for pos, klass in positions[bref]:
        if klass == order["separation_class"] and n - pos < separation:
            return "DF_SEPARATION", predicate_index["DF_SEPARATION"]
    return None, 0


# ------------------------------------------------------------ V13

def minutage(market_refs, admitted, daypart_hours, hours, permitted,
             standing_minutes, frames_per_hour, day_frames):
    """V13.  The advertising frames of every market clock hour, and the cap
    of every market hour.  The last hour of the day absorbs anything that
    runs past the end of the day."""
    hour_count = len(hours)
    last = hour_count - 1
    adv_frames = collections.defaultdict(int)
    for spot in admitted:
        start = spot["start_frame"]
        end = spot["end_frame"]
        market = spot["market_ref"]
        i = min(start // frames_per_hour, last)
        while i < hour_count and i * frames_per_hour < end:
            lo = max(start, i * frames_per_hour)
            hi = min(end, (i + 1) * frames_per_hour)
            if i == last:
                hi = end
            if hi > lo:
                adv_frames[(market, i)] += hi - lo
            i += 1
    rows = []
    for market in sorted(market_refs):
        for i, hour in enumerate(hours):
            minutes = permitted.get((market, hour), standing_minutes)
            cap = floor_frac(channel_frames_of_seconds(minutes * 60))
            frames = adv_frames.get((market, i), 0)
            rows.append({
                "market_ref": market, "hour_label": hour,
                "hour_index": i,
                "daypart_ref": daypart_hours[hour],
                "advertising_frames": frames,
                "advertising_seconds": Fraction(frames * 1001, 30000),
                "cap_frames": cap,
                "headroom_frames": cap - frames,
                "breach_state": "MB_BREACH" if frames > cap else "MB_WITHIN",
            })
    return rows


def hour_of(frame, hours, frames_per_hour):
    """The clock hour that holds a frame.  The last hour absorbs anything
    past the end of the day."""
    return hours[min(frame // frames_per_hour, len(hours) - 1)]


def unbilled_frames(rows, admitted, frames_per_hour, day_frames):
    """R41.  The frames above the cap of every breaching market hour go
    unbilled, taken from the admitted spots of that market that have frames
    inside the hour, latest first: descending start frame, ties by
    descending order reference."""
    taken = collections.defaultdict(int)
    hour_count = max(r["hour_index"] for r in rows) + 1 if rows else 0
    last = hour_count - 1
    for row in rows:
        if row["breach_state"] != "MB_BREACH":
            continue
        market = row["market_ref"]
        i = row["hour_index"]
        excess = row["advertising_frames"] - row["cap_frames"]
        candidates = []
        for spot in admitted:
            if spot["market_ref"] != market:
                continue
            lo = max(spot["start_frame"], i * frames_per_hour)
            hi = min(spot["end_frame"], (i + 1) * frames_per_hour)
            if i == last:
                hi = spot["end_frame"]
            inside = max(0, hi - lo)
            if inside > 0:
                candidates.append((spot, inside))
        candidates.sort(key=lambda c: (c[0]["start_frame"], c[0]["order_ref"]),
                        reverse=True)
        for spot, inside in candidates:
            if excess <= 0:
                break
            give = min(inside, excess)
            taken[spot["order_ref"]] += give
            excess -= give
    return taken


# ------------------------------------------------------------ V11

def settle(admitted, card_by_order, advertisers, exponents, commissions,
           grain_seconds, taken):
    """V11.  The money of every admitted spot, in minor units."""
    grain_frames = channel_frames_of_seconds(grain_seconds)
    rows = []
    for spot in admitted:
        order = spot["order_ref"]
        adv = spot["advertiser_ref"]
        card = card_by_order[order]
        currency = advertisers[adv]["settlement_currency"]
        exponent = int(exponents["exponents"][currency])
        delivered = spot["spot_frames"]
        lost = taken.get(order, 0)
        billed = delivered - lost
        grains = 0
        if billed > 0:
            grains = ceil_ratio(Fraction(billed), grain_frames)
        gross = grains * card["minor_per_grain"]
        num, den = commissions[adv]
        commission = round_half_even_unit(Fraction(gross) * num / den)
        net = gross - commission
        rows.append({
            "order_ref": order, "advertiser_ref": adv,
            "market_ref": spot["market_ref"], "break_ref": spot["break_ref"],
            "currency": currency, "delivered_frames": delivered,
            "unbilled_frames": lost, "billable_grains": grains,
            "rate_card_ref": card["rate_card_ref"],
            "effective_from": card["effective_from_iso"],
            "minor_per_grain": card["minor_per_grain"],
            "gross_minor": gross, "commission_minor": commission,
            "net_minor": net,
            "gross_major": Fraction(gross, 10 ** exponent),
        })
    rows.sort(key=lambda r: (r["order_ref"], r["market_ref"]))
    return rows


def ceil_ratio(numerator, denominator):
    """The ceiling of an exact rational."""
    value = Fraction(numerator) / Fraction(denominator)
    return -((-value.numerator) // value.denominator)


def round_half_even_unit(value):
    """A rational rounded to a whole minor unit, halves to even."""
    return int(round_half_even(value, 0))


# ------------------------------------------------------------ V12

def make_good(deferrals, admitted, settlement, card_by_order, cap_num,
              cap_den, grain_seconds, taken):
    """V12.  The make good obligations and the cap that allocates them."""
    grain_frames = channel_frames_of_seconds(grain_seconds)
    raw = collections.defaultdict(list)
    for d in deferrals:
        card = card_by_order.get(d["order_ref"])
        if card is None:
            # An order with no eligible rate card raises no obligation,
            # whatever the reason it was deferred with.
            continue
        grains = ceil_ratio(Fraction(d["spot_frames"]), grain_frames) \
            if d["spot_frames"] > 0 else 0
        raw[d["advertiser_ref"]].append({
            "order_ref": d["order_ref"], "deferral_reason": d["deferral_reason"],
            "raw_minor": grains * card["minor_per_grain"],
        })
    for spot in admitted:
        lost = taken.get(spot["order_ref"], 0)
        if lost == 0:
            continue
        card = card_by_order[spot["order_ref"]]
        delivered_grains = ceil_ratio(Fraction(spot["spot_frames"]), grain_frames) \
            if spot["spot_frames"] > 0 else 0
        billed_frames = spot["spot_frames"] - lost
        billed_grains = ceil_ratio(Fraction(billed_frames), grain_frames) \
            if billed_frames > 0 else 0
        grains_lost = delivered_grains - billed_grains
        if grains_lost <= 0:
            # An admitted spot that lost frames but no whole grain raises no
            # obligation.
            continue
        raw[spot["advertiser_ref"]].append({
            "order_ref": spot["order_ref"], "deferral_reason": "DF_OVER_CAP",
            "raw_minor": grains_lost * card["minor_per_grain"],
        })

    day_gross = collections.defaultdict(int)
    for row in settlement:
        day_gross[row["advertiser_ref"]] += row["gross_minor"]

    entries = {}
    refs = set(raw) | set(day_gross)
    for adv in refs:
        obligations = sorted(raw.get(adv, []), key=lambda o: o["order_ref"])
        raw_total = sum(o["raw_minor"] for o in obligations)
        gross = day_gross.get(adv, 0)
        cap = floor_frac(Fraction(gross) * Fraction(cap_num, cap_den))
        if raw_total <= cap:
            for o in obligations:
                o["allocated_minor"] = o["raw_minor"]
        else:
            allocated = largest_remainder(obligations, cap)
            for o, value in zip(obligations, allocated):
                o["allocated_minor"] = value
        entries[adv] = {
            "advertiser_ref": adv,
            "day_gross_minor": gross,
            "cap_minor": cap,
            "raw_total_minor": raw_total,
            "allocated_total_minor": sum(o["allocated_minor"] for o in obligations),
            "obligations": [{"order_ref": o["order_ref"],
                             "deferral_reason": o["deferral_reason"],
                             "raw_minor": o["raw_minor"],
                             "allocated_minor": o["allocated_minor"]}
                            for o in obligations],
        }
    return entries


def largest_remainder(obligations, cap):
    """R31.  Allocate the cap across the obligations in proportion to their
    raw values, by the largest remainder method.  Mass preserving."""
    raw_total = sum(o["raw_minor"] for o in obligations)
    floors = []
    remainders = []
    for o in obligations:
        share = Fraction(cap) * Fraction(o["raw_minor"], raw_total)
        whole = share.numerator // share.denominator
        floors.append(whole)
        remainders.append(share - whole)
    leftover = cap - sum(floors)
    order = sorted(range(len(obligations)),
                   key=lambda i: (-remainders[i], obligations[i]["order_ref"]))
    for k in range(leftover):
        floors[order[k % len(order)]] += 1
    return floors


# ------------------------------------------------------------ writing

def write_text(out, name, text):
    data = text.encode("ascii")
    if b"\r" in data:
        raise ValueError("%s carries a carriage return" % name)
    with open(os.path.join(out, name), "wb") as fh:
        fh.write(data)


def delimited(rows, columns, delimiter):
    """A delimited artifact: one header row and one row per record, with no
    quoting, no escaping and no spaces around a delimiter."""
    lines = [delimiter.join(columns)]
    for row in rows:
        lines.append(delimiter.join(str(row[c]) for c in columns))
    return "\n".join(lines) + "\n"


def json_text(obj):
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def jsonl_text(rows):
    """A ledger with no records is a single line feed."""
    if not rows:
        return "\n"
    return "".join(
        json.dumps(r, sort_keys=True, ensure_ascii=True,
                   separators=(",", ":")) + "\n" for r in rows)


def read_reference(path, keep_order=False):
    """The members of a closed vocabulary.  A reference file names each
    member on a line of its own and indents its prose below it.

    The deferral reference lists its reasons in predicate order, which is
    why the order of that file is preserved.
    """
    members = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text or line.startswith((" ", "\t")):
                continue
            if not re.match(r"^[A-Z][A-Z0-9_]*$", text):
                continue
            if text not in members:
                members.append(text)
    return members if keep_order else sorted(members)


def ratio(value):
    return ratio_text(Fraction(value))


# ------------------------------------------------------------ the day

def hour_labels(day_start_hour, count):
    """The clock hour labels of the broadcast day, in order.  The small hours
    of the following calendar day carry the labels past twenty three."""
    return ["H%02d" % (day_start_hour + i) for i in range(count)]


def run(data, out):
    config = read_json(os.path.join(data, "channel_config.json"))
    channel_ref = config["channel_ref"]
    transmission_date = parse_date(config["transmission_date"])
    day_start_tc = config["day_start_tc"]
    instance_ref = config["instance_ref"]
    house_filler = config["house_filler_ref"]

    rate_register = read_csv(os.path.join(data, "rate_code_register.csv"))
    rate_by_code = {r["rate_code"]: r for r in rate_register}
    channel_rate = rate_by_code[config["channel_rate_code"]]
    channel_base = int(channel_rate["tc_base"])
    channel_drop = channel_rate["df_allowed"].strip().lower() == "yes"
    day_frames = tc_day_frames(channel_base, channel_drop)
    # A clock hour is one hour of channel timecode frames measured from the
    # day start.  Any sixty consecutive minutes carry exactly fifty four
    # minutes that are not a multiple of ten, and a drop base skips two
    # frame numbers at the start of each of them.
    dropped_minutes = 60 - 60 // 10
    frames_per_hour = channel_base * 3600
    if channel_drop:
        frames_per_hour -= (channel_base * 2 // 30) * dropped_minutes
    day_start = tc_frames(day_start_tc, channel_base, channel_drop)
    start_hour = parse_tc(day_start_tc)[0]
    hour_count = (day_frames + frames_per_hour - 1) // frames_per_hour

    terms = workbook_terms(os.path.join(data, "contract_terms_workbook.xlsx"),
                           config["workbook_control_set"])
    snap_tolerance = int(terms["scalars"]["snap_tolerance_frames"])
    cap_num = int(terms["scalars"]["makegood_cap_num"])
    cap_den = int(terms["scalars"]["makegood_cap_den"])
    commissions = terms["commissions"]

    memo = memo_constants(os.path.join(data, "regulatory_minutage_memo.pdf"))
    separation = memo["constants"]["separation_minimum_positions"]
    grain_seconds = memo["constants"]["billing_grain_seconds"]
    standing_minutes = memo["constants"]["regulatory_minutes_per_clock_hour"]
    permitted = memo["permitted"]
    correction_reasons = read_reference(
        os.path.join(data, "correction_reason_reference.txt"))
    deferral_reasons = read_reference(
        os.path.join(data, "deferral_reason_reference.txt"), keep_order=True)
    snap_sides = read_reference(os.path.join(data, "snap_side_reference.txt"))
    # DF_OVER_CAP is not an admission predicate and V9 never defers a spot
    # with it, so it carries no predicate index.
    admission_reasons = [r for r in deferral_reasons if r != "DF_OVER_CAP"]

    hours = hour_labels(start_hour, hour_count)
    daypart_hours = {}
    for row in read_csv(os.path.join(data, "daypart_calendar.csv")):
        daypart_hours[row["hour_label"]] = row["daypart_ref"]

    # The carry scopes are opened for the whole run: V4 and V6 for each
    # placed slot, V9 and V10 for each market, and V11 for each advertiser
    # with an order in the book.
    order_book = read_jsonl(os.path.join(data, "spot_order_book.jsonl"))
    market_refs_pre = sorted(r["market_ref"] for r in
                             read_csv(os.path.join(data, "market_register.csv")))
    carry = CarryScopes()

    # V1 to V3.
    assets = canonicalise_assets(data)

    # V7: the order of the slots in the day, and the scheduled offset of
    # every junction.
    schedule_rows = read_csv(os.path.join(data, "transmission_schedule.csv"))
    slots = {}
    for row in schedule_rows:
        offset = tc_frames(row["sched_start_tc"], channel_base, channel_drop)
        offset -= day_start
        if offset < 0:
            offset += day_frames
        slots[row["slot_id"]] = {
            "slot_id": row["slot_id"],
            "content_ref": row["content_ref"],
            "offset": offset,
            "junction_kind": row["junction_kind"],
            "flex_part_no": int(row["flex_part_no"]),
            "daypart_ref": row["daypart_ref"],
            "placed": row["content_ref"] in assets
                      and assets[row["content_ref"]]["included"],
            "sequence_no": 0,
        }
    ordered = sorted(slots.values(), key=lambda s: (s["offset"], s["slot_id"]))
    for i, row in enumerate(ordered):
        row["sequence_no"] = i + 1
    placed_ids = [r["slot_id"] for r in ordered if r["placed"]]
    dropped_ids = [r["slot_id"] for r in ordered if not r["placed"]]
    for sid in placed_ids:
        carry.open("V4:" + sid)
        carry.open("V6:" + sid)
    for market in market_refs_pre:
        carry.open("V9:" + market)
        carry.open("V10:" + market)
    for advertiser in sorted(set(o["advertiser_ref"] for o in order_book)):
        carry.open("V11:" + advertiser)

    # V6 must run before the placement, because the snap of a break does not
    # move a slot start but the material duration does.  The parts are
    # conditioned for the placed slots only.
    parts, material, flex_frames, flex_present = build_segments(
        data, assets, placed_ids, slots, carry)
    breaks_out, break_positions = condition_breaks(
        data, placed_ids, slots, assets, carry, snap_tolerance)

    # V7 and V8.
    corrections = []
    starts, trims, fills, placed_ids = place_slots(
        ordered, material, flex_frames, flex_present,
        read_csv(os.path.join(data, "filler_library.csv")), house_filler,
        corrections)

    # V10.
    market_refs, market_sets, overrides, substitutions = market_break_sets(
        data, slots, placed_ids, starts, break_positions, transmission_date,
        carry)

    # V9.
    cards = collections.defaultdict(list)
    for row in read_csv(os.path.join(data, "rate_card_book.csv")):
        cards[row["rate_card_ref"]].append({
            "rate_card_ref": row["rate_card_ref"],
            "effective_from": parse_date(row["effective_from"]),
            "effective_from_iso": row["effective_from"],
            "minor_per_grain": int(row["minor_per_grain"]),
            "card_revision": int(row["card_revision"]),
        })
    admitted, deferrals, durations, card_by_order = derive_avails(
        data, market_refs, market_sets, substitutions, slots, carry,
        transmission_date, cards, separation, break_positions,
        admission_reasons)
    # V13.
    minute_rows = minutage(market_refs, admitted, daypart_hours, hours,
                           permitted, standing_minutes, frames_per_hour,
                           day_frames)
    taken = unbilled_frames(minute_rows, admitted, frames_per_hour, day_frames)

    # V11.
    advertisers = {r["advertiser_ref"]: r
                   for r in read_csv(os.path.join(data, "advertiser_register.csv"))}
    exponents = read_json(os.path.join(data, "currency_minor_units.json"))
    settlement = settle(admitted, card_by_order, advertisers, exponents,
                        commissions, grain_seconds, taken)

    # V12.
    good = make_good(deferrals, admitted, settlement, card_by_order, cap_num,
                     cap_den, grain_seconds, taken)

    # V14.
    day = {
        "channel_ref": channel_ref,
        "transmission_date": config["transmission_date"],
        "transmission_date_obj": transmission_date,
        "day_start_tc": day_start_tc,
        "instance_ref": instance_ref,
        "day_frames": day_frames,
        "frames_per_hour": frames_per_hour,
        "hours": hours,
        "daypart_hours": daypart_hours,
        "snap_tolerance": snap_tolerance,
        "cap_num": cap_num,
        "cap_den": cap_den,
        "separation": separation,
        "grain_seconds": grain_seconds,
        "standing_minutes": standing_minutes,
        "terms": terms,
        "channel_base": channel_base,
        "channel_drop": channel_drop,
        "day_start": day_start,
        "correction_reasons": correction_reasons,
        "deferral_reasons": deferral_reasons,
        "admission_reasons": admission_reasons,
        "snap_sides": snap_sides,
        "advertisers": advertisers,
        "exponents": exponents,
        "commissions": commissions,
    }
    publish(data, out, config, day, assets, ordered, placed_ids,
            dropped_ids, starts, trims, fills, corrections, material, parts,
            breaks_out, break_positions, market_refs, market_sets, overrides,
            admitted, deferrals, minute_rows, settlement, good, card_by_order,
            carry, taken, order_book)


def publish(data, out, config, day, assets, ordered, placed_ids, dropped_ids,
            starts, trims, fills, corrections, material, parts, breaks_out,
            break_positions, market_refs, market_sets, overrides, admitted,
            deferrals, minute_rows, settlement, good, card_by_order, carry,
            taken, order_book):
    os.makedirs(out, exist_ok=True)

    # ---- asset_register.csv
    columns = ["content_ref", "canonical_ingest_id", "revision_no", "qc_state",
               "rate_code", "rate_num", "rate_den", "tc_base", "drop_frame",
               "som_tc", "eom_tc", "source_frames", "channel_frames_exact",
               "house_no", "anchor_ingest_id", "inclusion_state"]
    rows = []
    for ref in sorted(assets):
        a = assets[ref]
        if a["included"]:
            rows.append({
                "content_ref": ref,
                "canonical_ingest_id": a["canonical_ingest_id"],
                "revision_no": a["revision_no"],
                "qc_state": a["qc_state"],
                "rate_code": a["rate_code"],
                "rate_num": a["rate_num"],
                "rate_den": a["rate_den"],
                "tc_base": a["tc_base"],
                "drop_frame": "yes" if a["drop_frame"] else "no",
                "som_tc": a["som_tc"], "eom_tc": a["eom_tc"],
                "source_frames": a["source_frames"],
                "channel_frames_exact": ratio(a["channel_frames_exact"]),
                "house_no": a["house_no"],
                "anchor_ingest_id": a["anchor_ingest_id"],
                "inclusion_state": "AS_INCLUDED",
            })
        else:
            rows.append({
                "content_ref": ref, "canonical_ingest_id": "",
                "revision_no": "", "qc_state": "", "rate_code": "",
                "rate_num": "", "rate_den": "", "tc_base": "",
                "drop_frame": "", "som_tc": "", "eom_tc": "",
                "source_frames": "", "channel_frames_exact": "",
                "house_no": a["house_no"],
                "anchor_ingest_id": a["anchor_ingest_id"],
                "inclusion_state": "AS_EXCLUDED",
            })
    write_text(out, "asset_register.csv", delimited(rows, columns, ","))

    # ---- segment_conform.csv
    columns = ["slot_id", "content_ref", "part_no", "part_kind",
               "retention_state", "source_frames", "channel_frames_exact",
               "channel_frames", "carry_after"]
    seg_rows = []
    for row in sorted(parts, key=lambda r: (r["slot_id"], r["part_no"])):
        seg_rows.append({
            "slot_id": row["slot_id"], "content_ref": row["content_ref"],
            "part_no": row["part_no"], "part_kind": row["part_kind"],
            "retention_state": row["retention_state"],
            "source_frames": row["source_frames"],
            "channel_frames_exact": ratio(row["channel_frames_exact"]),
            "channel_frames": row["channel_frames"],
            "carry_after": ratio(row["carry_after"]),
        })
    write_text(out, "segment_conform.csv", delimited(seg_rows, columns, ","))

    for row in breaks_out:
        if row["snap_side"] not in day["snap_sides"]:
            raise ValueError("snap side %s is not in the vocabulary"
                             % row["snap_side"])

    # ---- break_positions.csv
    columns = ["slot_id", "break_no", "break_ref", "nominal_offset_seconds",
               "nominal_frame", "adjusted_target_frame", "position_frame",
               "snap_side", "displacement_frames", "avail_seconds",
               "carry_after"]
    bp_rows = []
    for row in sorted(breaks_out, key=lambda r: (r["slot_id"], r["break_no"])):
        bp_rows.append({
            "slot_id": row["slot_id"], "break_no": row["break_no"],
            "break_ref": row["break_ref"],
            "nominal_offset_seconds": row["nominal_offset_seconds"],
            "nominal_frame": row["nominal_frame"],
            "adjusted_target_frame": row["adjusted_target_frame"],
            "position_frame": row["position_frame"],
            "snap_side": row["snap_side"],
            "displacement_frames": row["displacement_frames"],
            "avail_seconds": row["avail_seconds"],
            "carry_after": ratio(row["carry_after"]),
        })
    write_text(out, "break_positions.csv", delimited(bp_rows, columns, ","))

    # ---- slot_placement.csv
    columns = ["slot_id", "content_ref", "sequence_no", "junction_kind",
               "sched_start_frame", "actual_start_frame", "material_frames",
               "trim_frames", "transmitted_frames", "end_frame",
               "drift_frames", "hour_label", "daypart_ref", "placement_state"]
    sp_rows = []
    end_frames = {}
    for row in ordered:
        sid = row["slot_id"]
        if not row["placed"]:
            sp_rows.append({
                "slot_id": sid, "content_ref": row["content_ref"],
                "sequence_no": 0, "junction_kind": row["junction_kind"],
                "sched_start_frame": 0, "actual_start_frame": 0,
                "material_frames": 0, "trim_frames": 0,
                "transmitted_frames": 0, "end_frame": 0, "drift_frames": 0,
                "hour_label": "", "daypart_ref": row["daypart_ref"],
                "placement_state": "PL_DROPPED",
            })
            continue
        start = starts[sid]
        mat = material[sid]
        trim = trims[sid]
        transmitted = mat - trim
        end = start + transmitted
        end_frames[sid] = end
        hour_label = hour_of(start, day["hours"], day["frames_per_hour"])
        sp_rows.append({
            "slot_id": sid, "content_ref": row["content_ref"],
            "sequence_no": row["sequence_no"],
            "junction_kind": row["junction_kind"],
            "sched_start_frame": row["offset"], "actual_start_frame": start,
            "material_frames": mat, "trim_frames": trim,
            "transmitted_frames": transmitted, "end_frame": end,
            "drift_frames": start - row["offset"],
            "hour_label": hour_label,
            "daypart_ref": row["daypart_ref"],
            "placement_state": "PL_PLACED",
        })
    sp_rows.sort(key=lambda r: (r["sequence_no"], r["slot_id"]))
    write_text(out, "slot_placement.csv", delimited(sp_rows, columns, ","))

    day_end_frame = max(end_frames.values()) if end_frames else 0

    # ---- conform_trace.json
    walk = [c for c in corrections if c["reason"] != "CR_SLOT_DROPPED"]
    # The dropped slot corrections follow the walk, in ascending scheduled
    # offset, ties by slot id.
    scheduled = {r["slot_id"]: r["offset"] for r in ordered}
    dropped = sorted([c for c in corrections
                      if c["reason"] == "CR_SLOT_DROPPED"],
                     key=lambda c: (scheduled[c["slot_id"]], c["slot_id"]))
    trace = []
    for i, c in enumerate(walk):
        trace.append({
            "sequence": i + 1, "slot_id": c["slot_id"], "reason": c["reason"],
            "frames": c["frames"], "detail_slot": c["detail_slot"],
            "filler_ref": c["filler_ref"],
        })
    trace.sort(key=lambda c: c["sequence"])
    totals = collections.Counter(c["reason"] for c in trace)
    for c in dropped:
        trace.append({
            "sequence": len(trace) + 1, "slot_id": c["slot_id"],
            "reason": "CR_SLOT_DROPPED", "frames": 0,
            "detail_slot": c["slot_id"], "filler_ref": "",
        })
        totals["CR_SLOT_DROPPED"] += 1
    for correction in trace:
        if correction["reason"] not in day["correction_reasons"]:
            raise ValueError("correction reason %s is not in the vocabulary"
                             % correction["reason"])

    conform_trace = {
        "corrections": trace,
        "totals": {r: totals.get(r, 0) for r in day["correction_reasons"]
                   if totals.get(r, 0)},
        "day_end_frame": day_end_frame,
        "correction_count": len(trace),
    }
    write_text(out, "conform_trace.json", json_text(conform_trace))

    # ---- filler_plan.csv
    columns = ["slot_id", "junction_offset_frame", "gap_frames", "filler_ref",
               "daypart_ref", "selection_index"]
    fill_rows = []
    for row in sorted(fills, key=lambda r: r["slot_id"]):
        fill_rows.append({
            "slot_id": row["slot_id"],
            "junction_offset_frame": row["junction_offset_frame"],
            "gap_frames": row["gap_frames"], "filler_ref": row["filler_ref"],
            "daypart_ref": row["daypart_ref"],
            "selection_index": row["selection_index"],
        })
    write_text(out, "filler_plan.csv", delimited(fill_rows, columns, ","))

    # ---- avail_plan.tsv
    columns = ["market_ref", "break_ref", "break_position_frame",
               "position_in_break", "order_ref", "advertiser_ref",
               "separation_class", "spot_frames", "start_frame", "end_frame",
               "hour_label"]
    av_rows = []
    for spot in admitted:
        av_rows.append({
            "market_ref": spot["market_ref"], "break_ref": spot["break_ref"],
            "break_position_frame": spot["break_position_frame"],
            "position_in_break": spot["position_in_break"],
            "order_ref": spot["order_ref"],
            "advertiser_ref": spot["advertiser_ref"],
            "separation_class": spot["separation_class"],
            "spot_frames": spot["spot_frames"],
            "start_frame": spot["start_frame"], "end_frame": spot["end_frame"],
            "hour_label": hour_of(spot["start_frame"], day["hours"],
                                  day["frames_per_hour"]),
        })
    write_text(out, "avail_plan.tsv", delimited(av_rows, columns, "\t"))

    for row in deferrals:
        if row["deferral_reason"] not in day["admission_reasons"]:
            raise ValueError("deferral reason %s is not in the vocabulary"
                             % row["deferral_reason"])
        if not 1 <= row["predicate_index"] <= len(day["admission_reasons"]):
            raise ValueError("predicate index %s is out of range"
                             % row["predicate_index"])

    # ---- deferral_ledger.jsonl
    dl_rows = [{
        "order_ref": d["order_ref"], "market_ref": d["market_ref"],
        "break_ref": d["break_ref"], "deferral_reason": d["deferral_reason"],
        "predicate_index": d["predicate_index"], "spot_frames": d["spot_frames"],
    } for d in deferrals]
    write_text(out, "deferral_ledger.jsonl", jsonl_text(dl_rows))

    # ---- market_overrides.csv
    columns = ["market_ref", "slot_id", "content_ref", "rule_id", "precedence",
               "substitute_ref", "override_flag", "national_break_count",
               "substitute_break_count"]
    write_text(out, "market_overrides.csv", delimited(overrides, columns, ","))

    # ---- the four per market avail files, and their union
    stream = []
    for market in market_refs:
        entries = market_sets[market]
        breaks = [market_break_record(e, day["hours"], day["frames_per_hour"])
                  for e in entries]
        payload = {
            "market_ref": market,
            "break_count": len(breaks),
            "capacity_frames_total": sum(b["capacity_frames"] for b in breaks),
            "carry_residual_capacity": ratio(carry.residual("V9:" + market)),
            "carry_residual_substitute": ratio(carry.residual("V10:" + market)),
            "breaks": breaks,
        }
        write_text(out, "market_avails_%s.json" % market, json_text(payload))
        for entry in breaks:
            stream.append(dict(entry, market_ref=market))
    stream.sort(key=lambda r: (r["market_ref"], r["position_frame"],
                               r["break_ref"]))
    write_text(out, "market_avail_stream.jsonl", jsonl_text(stream))

    # ---- settlement_ledger.psv
    columns = ["order_ref", "advertiser_ref", "market_ref", "break_ref",
               "currency", "delivered_frames", "unbilled_frames",
               "billable_grains", "rate_card_ref", "effective_from",
               "minor_per_grain", "gross_minor", "commission_minor",
               "net_minor", "gross_major"]
    st_rows = []
    for row in settlement:
        st_rows.append({
            "order_ref": row["order_ref"],
            "advertiser_ref": row["advertiser_ref"],
            "market_ref": row["market_ref"], "break_ref": row["break_ref"],
            "currency": row["currency"],
            "delivered_frames": row["delivered_frames"],
            "unbilled_frames": row["unbilled_frames"],
            "billable_grains": row["billable_grains"],
            "rate_card_ref": row["rate_card_ref"],
            "effective_from": row["effective_from"],
            "minor_per_grain": row["minor_per_grain"],
            "gross_minor": row["gross_minor"],
            "commission_minor": row["commission_minor"],
            "net_minor": row["net_minor"],
            "gross_major": round_half_even(row["gross_major"],
                                           exponent_of(row, day["advertisers"], day["exponents"])),
        })
    write_text(out, "settlement_ledger.psv", delimited(st_rows, columns, "|"))

    # ---- makegood_ledger.json
    makegood = {
        "advertisers": [good[a] for a in sorted(good)],
        "allocated_total_minor": sum(good[a]["allocated_total_minor"]
                                     for a in good),
        "cap_num": day["cap_num"], "cap_den": day["cap_den"],
    }
    write_text(out, "makegood_ledger.json", json_text(makegood))

    # ---- exception_ledger.jsonl
    exceptions = []
    for row in settlement:
        if row["delivered_frames"] == 0:
            exceptions.append({
                "order_ref": row["order_ref"],
                "exception_code": "EX_ZERO_DELIVERY",
                "rate_card_ref": row["rate_card_ref"],
                "detail": "admitted spot occupies no channel frame",
            })
    order_by_ref = {o["order_ref"]: o for o in order_book}
    card_rows = collections.defaultdict(list)
    for row in read_csv(os.path.join(data, "rate_card_book.csv")):
        card_rows[row["rate_card_ref"]].append(row["effective_from"])
    for order_ref in sorted(card_by_order):
        if card_by_order[order_ref] is not None:
            continue
        ref = order_by_ref[order_ref]["rate_card_ref"] if order_ref in order_by_ref else ""
        dates = card_rows.get(ref, [])
        exceptions.append({
            "order_ref": order_ref,
            "exception_code": "EX_NO_CARD",
            "rate_card_ref": ref,
            "detail": "earliest card dated %s" % (min(dates) if dates else ""),
        })
    exceptions.sort(key=lambda r: (r["order_ref"], r["exception_code"]))
    write_text(out, "exception_ledger.jsonl", jsonl_text(exceptions))

    # ---- advertiser_summary.csv
    columns = ["advertiser_ref", "currency", "admitted_spots", "deferred_spots",
               "delivered_frames", "gross_minor", "commission_minor",
               "net_minor", "makegood_minor", "gross_major"]
    adv_rows = []
    deferred_count = collections.Counter(d["advertiser_ref"] for d in deferrals)
    for adv in sorted(day["advertisers"]):
        currency = day["advertisers"][adv]["settlement_currency"]
        exponent = int(day["exponents"]["exponents"][currency])
        spots = [r for r in settlement if r["advertiser_ref"] == adv]
        gross = sum(r["gross_minor"] for r in spots)
        commission = sum(r["commission_minor"] for r in spots)
        net = sum(r["net_minor"] for r in spots)
        entry = good.get(adv)
        allocated = entry["allocated_total_minor"] if entry else 0
        adv_rows.append({
            "advertiser_ref": adv, "currency": currency,
            "admitted_spots": len(spots),
            "deferred_spots": deferred_count.get(adv, 0),
            "delivered_frames": sum(r["delivered_frames"] for r in spots),
            "gross_minor": gross, "commission_minor": commission,
            "net_minor": net, "makegood_minor": allocated,
            "gross_major": round_half_even(Fraction(gross, 10 ** exponent), exponent),
        })
    write_text(out, "advertiser_summary.csv", delimited(adv_rows, columns, ","))

    # ---- minutage_report.csv
    columns = ["market_ref", "hour_label", "daypart_ref", "advertising_frames",
               "advertising_seconds", "cap_frames", "headroom_frames",
               "breach_state"]
    mn_rows = []
    for row in minute_rows:
        mn_rows.append({
            "market_ref": row["market_ref"], "hour_label": row["hour_label"],
            "daypart_ref": row["daypart_ref"],
            "advertising_frames": row["advertising_frames"],
            "advertising_seconds": ratio(row["advertising_seconds"]),
            "cap_frames": row["cap_frames"],
            "headroom_frames": row["headroom_frames"],
            "breach_state": row["breach_state"],
        })
    write_text(out, "minutage_report.csv", delimited(mn_rows, columns, ","))

    # ---- carry_ledger.json
    scopes = []
    for name in carry.scope_names():
        scopes.append({
            "scope": name, "conversions": carry.conversions[name],
            "residual": ratio(carry.held[name]),
        })
    carry_ledger = {
        "scopes": scopes, "scope_count": len(scopes),
        "conversion_count": sum(carry.conversions.values()),
        "residual_total": ratio(sum(carry.held.values(), ZERO)),
    }
    write_text(out, "carry_ledger.json", json_text(carry_ledger))

    # ---- reconciliation.xml
    prior = {r["slot_id"]: r for r in read_csv(
        os.path.join(data, "prior_conform_register.csv"))}
    national_counts = collections.Counter(r["slot_id"] for r in breaks_out)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<reconciliation channel_ref="%s" transmission_date="%s">'
                 % (day["channel_ref"], config["transmission_date"]))
    agreeing = 0
    abs_start = 0
    abs_material = 0
    for row in sorted(sp_rows, key=lambda r: r["slot_id"]):
        sid = row["slot_id"]
        p = prior.get(sid)
        prior_start = int(p["prior_start_frame"]) if p else 0
        prior_material = int(p["prior_material_frames"]) if p else 0
        prior_break = int(p["prior_break_count"]) if p else 0
        start_delta = row["actual_start_frame"] - prior_start
        material_delta = row["material_frames"] - prior_material
        break_delta = national_counts.get(sid, 0) - prior_break
        if start_delta == 0 and material_delta == 0 and break_delta == 0:
            agreeing += 1
        abs_start += abs(start_delta)
        abs_material += abs(material_delta)
        lines.append('  <slot slot_id="%s" placement_state="%s" '
                     'prior_start_frame="%d" start_frame="%d" '
                     'start_delta="%d" prior_material_frames="%d" '
                     'material_frames="%d" material_delta="%d" '
                     'prior_break_count="%d" break_count="%d" '
                     'break_delta="%d"/>'
                     % (sid, row["placement_state"], prior_start,
                        row["actual_start_frame"], start_delta,
                        prior_material, row["material_frames"], material_delta,
                        prior_break, national_counts.get(sid, 0), break_delta))
    lines.append('  <totals slots="%d" agreeing="%d" differing="%d" '
                 'absolute_start_delta="%d" absolute_material_delta="%d"/>'
                 % (len(sp_rows), agreeing, len(sp_rows) - agreeing,
                    abs_start, abs_material))
    lines.append('</reconciliation>')
    write_text(out, "reconciliation.xml", "\n".join(lines) + "\n")

    # ---- playout_schedule.ini
    placed = [r for r in sp_rows if r["placement_state"] == "PL_PLACED"]
    placed.sort(key=lambda r: r["sequence_no"])
    sections = []
    head = ["[channel]",
            "channel_ref = %s" % day["channel_ref"],
            "transmission_date = %s" % config["transmission_date"],
            "day_start_tc = %s" % day["day_start_tc"],
            "day_end_frame = %d" % day_end_frame,
            "placed_slot_count = %d" % len(placed)]
    sections.append("\n".join(head))
    for row in placed:
        start_tc = tc_label_from_frames(
            tc_frames(day["day_start_tc"], day["channel_base"], day["channel_drop"]) + row["actual_start_frame"],
            day["channel_base"], day["channel_drop"])
        sections.append("\n".join([
            "[slot: %s]" % row["slot_id"],
            "content_ref = %s" % row["content_ref"],
            "sequence_no = %d" % row["sequence_no"],
            "start_frame = %d" % row["actual_start_frame"],
            "start_tc = %s" % start_tc,
            "transmitted_frames = %d" % row["transmitted_frames"],
            "trim_frames = %d" % row["trim_frames"],
            "break_count = %d" % national_counts.get(row["slot_id"], 0),
        ]))
    write_text(out, "playout_schedule.ini", "\n\n".join(sections) + "\n")

    # ---- day_report.md
    gross_total = sum(r["gross_minor"] for r in settlement)
    makegood_total = makegood.get("allocated_total_minor", 0)
    body = ["# Transmission day report", ""]
    figures = [
        ("channel_ref", day["channel_ref"]),
        ("transmission_date", config["transmission_date"]),
        ("instance_ref", day["instance_ref"]),
        ("live_control_set", config["workbook_control_set"]),
        ("scheduled_slots", len(sp_rows)),
        ("placed_slots", len(placed)),
        ("dropped_slots", len(dropped_ids)),
        ("day_end_frame", day_end_frame),
        ("corrections", len(trace)),
        ("admitted_spots", len(admitted)),
        ("deferred_spots", len(deferrals)),
        ("gross_minor_total", gross_total),
        ("makegood_minor_total", makegood_total),
    ]
    for key, value in figures:
        body.append("- %s: %s" % (key, value))
    body.append("")
    body.append("## Correction totals")
    body.append("")
    for reason in day["correction_reasons"]:
        body.append("- %s: %d" % (reason, totals.get(reason, 0)))
    body.append("")
    body.append("## Deferral totals")
    body.append("")
    defer_totals = collections.Counter(d["deferral_reason"] for d in deferrals)
    over_cap = sum(1 for a in good for o in good[a]["obligations"]
                   if o["deferral_reason"] == "DF_OVER_CAP")
    for reason in sorted(day["deferral_reasons"]):
        if reason == "DF_OVER_CAP":
            body.append("- %s: %d" % (reason, over_cap))
        else:
            body.append("- %s: %d" % (reason, defer_totals.get(reason, 0)))
    write_text(out, "day_report.md", "\n".join(body) + "\n")

    # ---- compliance_summary.md
    breach_rows = [r for r in mn_rows if r["breach_state"] == "MB_BREACH"]
    body = ["# Compliance summary", ""]
    figures = [
        ("regulatory_minutes_per_clock_hour", day["standing_minutes"]),
        ("cap_frames", floor_frac(channel_frames_of_seconds(
            day["standing_minutes"] * 60))),
        ("separation_minimum_positions", day["separation"]),
        ("billing_grain_seconds", day["grain_seconds"]),
        ("snap_tolerance_frames", day["snap_tolerance"]),
        ("breach_hours", len(breach_rows)),
    ]
    for key, value in figures:
        body.append("- %s: %s" % (key, value))
    body.append("")
    body.append("## Advertising frames by market")
    body.append("")
    for market in sorted(market_refs):
        frames = sum(r["advertising_frames"] for r in mn_rows
                     if r["market_ref"] == market)
        body.append("- %s: %d" % (market, frames))
    body.append("")
    body.append("## Breach hours")
    body.append("")
    if breach_rows:
        for row in breach_rows:
            body.append("- %s %s frames %d over %d"
                        % (row["market_ref"], row["hour_label"],
                           row["advertising_frames"], row["cap_frames"]))
    else:
        body.append("- none")
    write_text(out, "compliance_summary.md", "\n".join(body) + "\n")

    # ---- manifest.json
    digest = hashlib.sha256()
    for name in CORE_ORDER:
        with open(os.path.join(out, name), "rb") as fh:
            digest.update(fh.read())
    manifest = {
        "instance_ref": day["instance_ref"],
        "channel_ref": day["channel_ref"],
        "transmission_date": config["transmission_date"],
        "artifact_count": len(FIXED_ARTIFACTS) + len(market_refs),
        "core_order": CORE_ORDER,
        "digest": digest.hexdigest(),
        "slot_count": len(sp_rows),
        "placed_slot_count": len(placed),
        "dropped_slot_count": len(dropped_ids),
        "admitted_spot_count": len(admitted),
        "deferred_spot_count": len(deferrals),
        "breach_hour_count": len(breach_rows),
        "live_control_set": day["terms"]["sheet_name"],
        "snap_tolerance_frames": day["snap_tolerance"],
        "makegood_cap_num": day["cap_num"],
        "makegood_cap_den": day["cap_den"],
        "separation_minimum_positions": day["separation"],
        "billing_grain_seconds": day["grain_seconds"],
        "regulatory_minutes_per_clock_hour": day["standing_minutes"],
        "day_end_frame": day_end_frame,
    }
    write_text(out, "manifest.json", json_text(manifest))


def exponent_of(row, advertisers, exponents):
    currency = advertisers[row["advertiser_ref"]]["settlement_currency"]
    return int(exponents["exponents"][currency])


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Conform one transmission day of a playout channel.")
    parser.add_argument("--data", default=DEFAULT_DATA,
                        help="the directory holding the records of the day")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help="the directory the artifacts are written into")
    args = parser.parse_args(argv)
    data = os.path.abspath(args.data)
    out = os.path.abspath(args.out)
    if not os.path.isdir(data):
        parser.error("no data directory at %s" % data)
    parent = os.path.dirname(out) or "."
    os.makedirs(parent, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    run(data, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
