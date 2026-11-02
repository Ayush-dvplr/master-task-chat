"""Derive one transmission day of the regional playout channel from source.

This is the author side reference for the conform and avail task, and it is
also the reusable program the task asks for, so it reads whichever corpus it
is pointed at and writes the twenty five published artifacts beside nothing
else. Nothing about the shipped day is built into it: every figure it needs
is lifted out of the records it was given, and the two directories default to
the container paths only when the command line names neither.

The derivation follows the fourteen stages of the pipeline contract. Whole
frame counts and whole minor units are the only published quantities, ratios
are published at a fixed ten places, and every intermediate value is an exact
rational so that no rounding happens anywhere except where a stage says it
does.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path

# Container defaults. They apply only when the command line supplies neither
# directory, which is how the grading harness runs the shipped bundle.
DEFAULT_DATA_DIR = "/app/data"
DEFAULT_OUT_DIR = "/app/out"

# Published ratios carry exactly this many decimal places.
RATIO_PLACES = 10

# The channel timebase and the broadcast day start. These are the published
# figures of the shipped channel and every one of them is re-resolved from
# the records of whichever day is read, in TransmissionDay._resolve_channel.
FPS_NUM = 30000
FPS_DEN = 1001
TC_BASE = 30
TC_DROP = True

# The broadcast day opens six hours into the calendar day, so the small hours
# of the following morning close it out rather than opening it.
DAY_OPENS_AT = "06:00:00;00"

# Drop frame skips two frame numbers in every minute whose number is not a
# multiple of ten: 1440 minutes a day less the 144 that are exempt, and 60
# minutes an hour less the 6 that are.
_DROPPED_MINUTES_PER_DAY = 24 * 60 - 24 * 6
_DROPPED_MINUTES_PER_HOUR = 60 - 6
FRAMES_PER_DAY = TC_BASE * 24 * 3600 - 2 * _DROPPED_MINUTES_PER_DAY
FRAMES_PER_CLOCK_HOUR = TC_BASE * 3600 - 2 * _DROPPED_MINUTES_PER_HOUR

# The twenty four clock hours of the broadcast day, labelled from the hour it
# opens so that the ordering of the labels is the ordering of the day.
CLOCK_HOURS = ["H%02d" % (6 + step) for step in range(24)]

# Closed vocabularies this module publishes against. The corpus is the source
# of every other token; these three are the ones the reports enumerate even
# where the day produced no member of them.
QC_ADMITS = ("QC_PASSED", "QC_PASSED_WITH_NOTES")

CORRECTION_VOCAB = ("CR_FILL_INSERT", "CR_NO_CHANGE", "CR_SLOT_DROPPED",
                    "CR_TRIM_BACKFILL", "CR_TRIM_FLEX", "CR_TRIM_SHORTFALL")

DEFERRAL_VOCAB = ("DF_BREAK_FULL", "DF_CLEARANCE_HELD", "DF_DAYPART_MISMATCH",
                  "DF_MARKET_BLACKED", "DF_NO_MATCHING_BREAK",
                  "DF_NO_RATE_CARD", "DF_OVER_CAP", "DF_SEPARATION")

# The seven artifacts the day digest runs over, in pipeline order. The digest
# is not taken over the alphabetical order and not over all twenty five.
DIGEST_ORDER = ("asset_register.csv", "segment_conform.csv",
                "break_positions.csv", "slot_placement.csv", "avail_plan.tsv",
                "settlement_ledger.psv", "minutage_report.csv")

# The four markets are read from the register rather than named here; only
# the per market artifact name is fixed by the contract.
MARKET_AVAILS_NAME = "market_avails_%s.json"

PUBLISHED = (
    "asset_register.csv", "segment_conform.csv", "break_positions.csv",
    "slot_placement.csv", "conform_trace.json", "filler_plan.csv",
    "avail_plan.tsv", "deferral_ledger.jsonl", "market_overrides.csv",
    "market_avails_mk_coast.json", "market_avails_mk_metro.json",
    "market_avails_mk_north.json", "market_avails_mk_valley.json",
    "market_avail_stream.jsonl", "settlement_ledger.psv",
    "makegood_ledger.json", "exception_ledger.jsonl",
    "advertiser_summary.csv", "minutage_report.csv", "carry_ledger.json",
    "reconciliation.xml", "playout_schedule.ini", "day_report.md",
    "compliance_summary.md", "manifest.json",
)


# ==========================================================================
# exact arithmetic
#
# Fraction throughout. No binary float is constructed anywhere in this
# module, so a tie lands where the stated rounding rule puts it rather than
# wherever the nearest representable double happens to sit.
# ==========================================================================
def half_even(value) -> int:
    """The nearest whole number, ties resolved toward the even neighbour."""
    exact = Fraction(value)
    below, remainder = divmod(exact.numerator, exact.denominator)
    doubled = 2 * remainder
    if doubled < exact.denominator:
        return below
    if doubled > exact.denominator:
        return below + 1
    return below if below % 2 == 0 else below + 1


def fixed_point(value, places: int = RATIO_PLACES) -> str:
    """Render an exact rational at a fixed number of places, ties to even.

    The result never carries an exponent and never carries a negative zero,
    because a value that rounds to zero rounds to the integer zero and loses
    its sign before it is rendered.
    """
    units = half_even(Fraction(value) * 10 ** places)
    body = str(abs(units)).rjust(places + 1, "0")
    if places > 0:
        body = body[:-places] + "." + body[-places:]
    return ("-" + body) if units < 0 else body


def as_date(text: str) -> date:
    return date.fromisoformat(str(text).strip())


def whole(text, fallback: int = 0) -> int:
    """A whole number out of a corpus cell, with a blank cell falling back."""
    cell = str(text).strip()
    return fallback if cell == "" else int(cell)


# ==========================================================================
# timecode
#
# A timecode labels a whole frame on an integer base. Drop frame renumbers
# rather than drops: the label keeps pace with the wall clock by skipping the
# first two frame numbers of most minutes, and the underlying count stays a
# plain run of whole frames.
# ==========================================================================
def _skipped_numbers(base: int) -> int:
    """Two skipped numbers a minute at base thirty, in proportion elsewhere."""
    return base * 2 // 30


def timecode_to_frames(label: str, base: int, drop: bool) -> int:
    """The whole frame count a timecode label names, per the V2 arithmetic."""
    fields = re.split(r"[:;]", str(label).strip())
    if len(fields) != 4 or not all(field.isdigit() for field in fields):
        raise ValueError("malformed timecode: " + str(label))
    hours, minutes, seconds, frames = (int(field) for field in fields)
    clock_minutes = 60 * hours + minutes
    count = (60 * clock_minutes + seconds) * base + frames
    if drop:
        count -= _skipped_numbers(base) * (clock_minutes - clock_minutes // 10)
    return count


def frames_to_timecode(count: int, base: int, drop: bool) -> str:
    """The label a whole frame count wears, wrapped into one timecode day."""
    if not drop:
        count %= base * 86400
        return "%02d:%02d:%02d:%02d" % (count // (base * 3600),
                                        count // (base * 60) % 60,
                                        count // base % 60, count % base)
    skip = _skipped_numbers(base)
    count %= base * 86400 - skip * _DROPPED_MINUTES_PER_DAY
    per_ten_minutes = base * 600 - 9 * skip
    per_short_minute = base * 60 - skip
    tens, inside = divmod(count, per_ten_minutes)
    if inside < base * 60:
        # The minute that opens a ten minute block keeps all of its numbers.
        extra_minutes, residue = 0, inside
    else:
        beyond = inside - base * 60
        extra_minutes = 1 + beyond // per_short_minute
        residue = beyond % per_short_minute + skip
    clock_minutes = 10 * tens + extra_minutes
    return "%02d:%02d:%02d;%02d" % (clock_minutes // 60, clock_minutes % 60,
                                    residue // base % 60, residue % base)


def timecode_day(base: int, drop: bool) -> int:
    """How many whole frames one timecode day holds on this base."""
    if drop:
        return base * 86400 - _skipped_numbers(base) * _DROPPED_MINUTES_PER_DAY
    return base * 86400


def to_channel_frames(source_frames, rate_num, rate_den) -> Fraction:
    """The exact channel frame count that a source frame count occupies. The
    result is rational on purpose; flooring it is the carry rule's business."""
    return Fraction(source_frames) * FPS_NUM * rate_den / (FPS_DEN * rate_num)


def seconds_in_frames(seconds) -> Fraction:
    return Fraction(seconds) * FPS_NUM / FPS_DEN


# ==========================================================================
# the carry rule
#
# Every conversion into channel frames is taken exactly, floored, and the
# fraction the floor threw away is banked in a named scope and spent on the
# next conversion made in that scope. A scope hands back a whole frame the
# moment what it holds reaches one. Nothing is rounded to nearest, and no
# intermediate value is rounded at all.
# ==========================================================================
class CarryPool:
    """The named scopes of the day and what each one is holding."""

    def __init__(self) -> None:
        self.residual: dict = {}
        self.conversions: dict = {}

    def open(self, scope: str) -> None:
        self.residual[scope] = Fraction(0)
        self.conversions.setdefault(scope, 0)

    def bank(self, exact, scope: str) -> int:
        """Floor an exact frame count inside a scope, banking the remainder."""
        self.conversions[scope] = self.conversions.get(scope, 0) + 1
        running = Fraction(exact) + self.residual.get(scope, Fraction(0))
        released = math.floor(running)
        self.residual[scope] = running - released
        return released

    def holding(self, scope: str) -> Fraction:
        return self.residual.get(scope, Fraction(0))

    def scopes(self) -> list:
        return sorted(self.residual)


# ==========================================================================
# readers
#
# Standard library only. The workbook is unzipped and its cached cell values
# are read straight out of the sheet parts; the memo is a document this
# corpus writes with uncompressed text operators, so its lines come back out
# of the content stream without a parser.
# ==========================================================================
_SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _column_index(reference: str) -> int:
    """Zero based column index out of a cell reference such as `AB7`."""
    index = 0
    for glyph in reference:
        if not glyph.isalpha():
            break
        index = index * 26 + ord(glyph.upper()) - 64
    return index - 1


def _sheet_rows(part: bytes, pool: list) -> list:
    grid = []
    for row_node in ET.fromstring(part).iter("{%s}row" % _SHEET_NS):
        line: list = []
        for cell in row_node.findall("{%s}c" % _SHEET_NS):
            at = _column_index(cell.get("r", "A1"))
            line.extend([""] * (at + 1 - len(line)))
            holder = cell.find("{%s}v" % _SHEET_NS)
            text = holder.text if holder is not None else ""
            if cell.get("t") == "s" and text:
                text = pool[int(text)]
            line[at] = text or ""
        grid.append(line)
    return grid


def read_workbook(path: Path) -> dict:
    """Every sheet of the workbook as a name keyed grid of cell strings."""
    with zipfile.ZipFile(path) as archive:
        pool: list = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in strings.findall("{%s}si" % _SHEET_NS):
                pool.append("".join(node.text or ""
                                    for node in item.iter("{%s}t" % _SHEET_NS)))
        targets = {node.get("Id"): node.get("Target")
                   for node in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        grids = {}
        for entry in book.find("{%s}sheets" % _SHEET_NS):
            part = targets[entry.get(_REL_ID)]
            if not part.startswith("xl/"):
                part = "xl/" + part
            grids[entry.get("name")] = _sheet_rows(archive.read(part), pool)
        return grids


_PDF_SHOWN = re.compile(r"\((.*?)\) Tj")


def read_document_lines(path: Path) -> list:
    """The shown text of a document, one entry per typeset line."""
    stream = Path(path).read_bytes().decode("latin-1")
    lines = []
    for shown in _PDF_SHOWN.findall(stream):
        for escaped, glyph in (("\\(", "("), ("\\)", ")"), ("\\\\", "\\")):
            shown = shown.replace(escaped, glyph)
        lines.append(shown)
    return lines


def document_table(lines: list, heading: str) -> list:
    """The pipe separated rows printed under one numbered section heading,
    up to the next section, header row excluded."""
    rows = []
    within = False
    for line in lines:
        if line.startswith("SECTION "):
            if within:
                break
            within = line.startswith(heading + " ")
            continue
        if within and line.count("|") >= 1:
            cells = [cell.strip() for cell in line.split("|")]
            if cells[0] != "market_ref":
                rows.append(cells)
    return rows


def arrival(stamp: str) -> datetime:
    """An ISO 8601 arrival time with its zone, as an aware instant."""
    if stamp.endswith("Z"):
        stamp = stamp[:-1] + "+00:00"
    return datetime.fromisoformat(stamp)


def document_value(lines: list, name: str) -> str:
    for line in lines:
        if line.startswith(name):
            return line.split("=", 1)[1].strip()
    raise KeyError(name)


# A national break reference: `bk_`, the slot id, an underscore and the break
# number.
_NATIONAL_BREAK = re.compile(r"^bk_(.+)_\d+$")


class Corpus:
    """One transmission day of records, read out of the directory it lives in.

    Nothing outside this directory is touched, and nothing inside it is
    written, so the same instance can be pointed at any day of this channel.
    """

    def __init__(self, root) -> None:
        self.root = Path(root)

    def _path(self, name: str) -> Path:
        return self.root / name

    def table(self, name: str, delimiter: str = ",") -> list:
        with open(self._path(name), newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle, delimiter=delimiter))

    def document(self, name: str):
        return json.loads(self._path(name).read_text(encoding="utf-8"))

    def stream(self, name: str) -> list:
        body = self._path(name).read_text(encoding="utf-8")
        return [json.loads(line) for line in body.splitlines() if line.strip()]

    def tree(self, name: str):
        return ET.fromstring(self._path(name).read_text(encoding="utf-8"))

    def workbook(self, name: str) -> dict:
        return read_workbook(self._path(name))

    def memo(self, name: str) -> list:
        return read_document_lines(self._path(name))


# ==========================================================================
# serialisation
#
# One line feed at the end of every artifact, no carriage return anywhere,
# sorted keys at every level of every json document, and the delimiter each
# format takes.
# ==========================================================================
def json_block(payload) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def json_line(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def delimited(columns: list, rows: list, delimiter: str) -> str:
    body = [delimiter.join(columns)]
    body.extend(delimiter.join(str(row[column]) for column in columns)
                for row in rows)
    return "\n".join(body) + "\n"


def json_lines(rows: list) -> str:
    if not rows:
        return "\n"
    return "\n".join(json_line(row) for row in rows) + "\n"


def attr(value) -> str:
    """Escape a value for an xml attribute."""
    text = str(value)
    for glyph, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"),
                          ('"', "&quot;")):
        text = text.replace(glyph, entity)
    return text


def utf8(text: str) -> bytes:
    return text.encode("utf-8")


def day_digest(published: dict) -> str:
    running = hashlib.sha256()
    for name in DIGEST_ORDER:
        running.update(published[name])
    return running.hexdigest()


# ==========================================================================
# the day
#
# One instance holds the records, the carry pool and every frozen stage
# result. The stages run in the dependency order the contract publishes,
# which is not the order the stages are numbered in: substitution settles
# before avail derivation because the avail set of a blacked market is the
# substitute break set and not the national one.
# ==========================================================================
class TransmissionDay:

    def __init__(self, data_dir) -> None:
        self.corpus = Corpus(data_dir)
        self.carry = CarryPool()
        self._load()

    # ---------------------------------------------------------------- load
    def _load(self) -> None:
        src = self.corpus
        self.config = src.document("channel_config.json")
        self.tx_date = as_date(self.config["transmission_date"])
        self.rate_register = {row["rate_code"]: row
                              for row in src.table("rate_code_register.csv")}
        self.ingest = src.table("ingest_attempt_register.csv")
        self.parts = src.table("segment_part_manifest.tsv", "\t")
        self.index = src.table("gop_index_channel.psv", "|")
        self.break_plan = src.table("break_plan_register.csv")
        self.schedule = src.table("transmission_schedule.csv")
        self.fillers = src.table("filler_library.csv")
        self.orders = src.stream("spot_order_book.jsonl")
        self.advertisers = src.table("advertiser_register.csv")
        self.cards = src.table("rate_card_book.csv")
        self.clearance_journal = src.table("clearance_state_journal.csv")
        self.market_rows = src.table("market_register.csv")
        self.substitutes = src.table("substitution_library.csv")
        self.prior = src.table("prior_conform_register.csv")
        self.dayparts = src.table("daypart_calendar.csv")
        self.minor_units = src.document("currency_minor_units.json")["exponents"]
        self.blackouts = [dict(node.attrib)
                          for node in src.tree("blackout_rule_set.xml").findall("rule")]
        self.markets = sorted(row["market_ref"] for row in self.market_rows)
        self._resolve_channel()
        self._load_contract_terms()
        self._load_regulatory_memo()

    def _resolve_channel(self) -> None:
        """Bind the channel timebase from the records of the day being read.

        The rate, the timecode base and the drop frame permission are
        properties of the channel's own rate code in the register, and the
        broadcast day start is published by the configuration, so a day of
        this channel carrying a different timebase conforms on its own
        figures. The register's `rounded_label` column is a display string
        and is never the rate.
        """
        global FPS_NUM, FPS_DEN, TC_BASE, TC_DROP, DAY_OPENS_AT
        global FRAMES_PER_DAY, FRAMES_PER_CLOCK_HOUR, CLOCK_HOURS
        rate = self.rate_register[str(self.config["channel_rate_code"])]
        FPS_NUM = int(rate["rate_num"])
        FPS_DEN = int(rate["rate_den"])
        TC_BASE = int(rate["tc_base"])
        TC_DROP = str(rate["df_allowed"]).strip().lower() == "yes"
        DAY_OPENS_AT = str(self.config["day_start_tc"])
        dropped_minutes_per_day = (24 * 60 - 24 * 6) if TC_DROP else 0
        dropped_minutes_per_hour = (60 - 6) if TC_DROP else 0
        FRAMES_PER_DAY = TC_BASE * 24 * 3600 - 2 * dropped_minutes_per_day
        FRAMES_PER_CLOCK_HOUR = TC_BASE * 3600 - 2 * dropped_minutes_per_hour
        CLOCK_HOURS = ["H%02d" % (int(DAY_OPENS_AT[:2]) + step)
                       for step in range(24)]

    def _load_contract_terms(self) -> None:
        """The workbook carries three control sets. The live one is the sheet
        whose control set cell carries the value the channel configuration
        publishes; the sheet name and the sheet position settle nothing."""
        wanted = str(self.config["workbook_control_set"])
        grids = self.corpus.workbook("contract_terms_workbook.xlsx")
        live = None
        for name in grids:
            head = grids[name][0] if grids[name] else []
            if len(head) >= 2 and head[0] == "control_set" and head[1] == wanted:
                live = (name, grids[name])
                break
        if live is None:
            raise KeyError("no workbook sheet carries control set " + wanted)
        self.control_set_sheet, rows = live
        self.terms = {}
        self.commission = {}
        for row in rows:
            if len(row) >= 2 and row[0] in ("snap_tolerance_frames",
                                            "makegood_cap_num",
                                            "makegood_cap_den"):
                self.terms[row[0]] = whole(row[1])
            if len(row) >= 5 and row[0] == "COMMISSION":
                self.commission[row[1]] = (whole(row[3]), whole(row[4]))

    def _load_regulatory_memo(self) -> None:
        """Three settlement constants are published nowhere but the memo."""
        lines = self.corpus.memo("regulatory_minutage_memo.pdf")
        self.regulatory = {
            name: whole(document_value(lines, name))
            for name in ("separation_minimum_positions", "billing_grain_seconds",
                         "regulatory_minutes_per_clock_hour")}
        # Section 2 overrides the standing minutes for the market hours it
        # lists; an unlisted market hour keeps the Section 1 figure.
        self.permitted_minutes = {
            (cells[0], cells[1]): whole(cells[2])
            for cells in document_table(lines, "SECTION 2") if len(cells) >= 3}

    # ------------------------------------------------------------ helpers
    def day_offset(self, label: str) -> int:
        """Where a transmission timecode sits measured from the open of the
        broadcast day rather than from midnight."""
        at = timecode_to_frames(label, TC_BASE, TC_DROP)
        opens = timecode_to_frames(DAY_OPENS_AT, TC_BASE, TC_DROP)
        return at - opens if at >= opens else at + FRAMES_PER_DAY - opens

    @staticmethod
    def clock_hour(frame: int) -> str:
        step = frame // FRAMES_PER_CLOCK_HOUR
        step = min(max(step, 0), 23)
        return CLOCK_HOURS[step]

    def asset_timebase(self, attempt: dict) -> tuple:
        """The editorial rate as an exact rational, the timecode base and
        whether drop frame labelling actually applies. `nominal_fps` is a
        rounded display label and the register is the record; drop frame
        applies only where the register permits it for that rate code."""
        register = self.rate_register[attempt["rate_code"]]
        drop = attempt["tc_mode"] == "DF" and register["df_allowed"] == "yes"
        return (whole(register["rate_num"]), whole(register["rate_den"]),
                whole(register["tc_base"]), drop)

    @staticmethod
    def _span(opening: str, closing: str, base: int, drop: bool) -> int:
        """An exclusive end of media, wrapping one timecode day when the end
        label sits below the start label."""
        length = (timecode_to_frames(closing, base, drop)
                  - timecode_to_frames(opening, base, drop))
        if length < 0:
            length += timecode_day(base, drop)
        return length

    # -------------------------------------------------- V1 canonicalisation
    def canonicalise(self) -> None:
        """Attempts cluster on the economic content reference. The canonical
        attempt of a cluster is the greatest revision among the quality
        passed attempts, ties settled on the ingest id that sorts first, and
        a cluster with no passed attempt leaves the day altogether. The house
        number stays with the first attempt received, which is very rarely
        the canonical one."""
        clusters: dict = {}
        for attempt in self.ingest:
            clusters.setdefault(attempt["content_ref"], []).append(attempt)

        self.content_refs = sorted(clusters)
        self.first_received = {}
        self.canonical = {}
        for ref in self.content_refs:
            attempts = clusters[ref]
            self.first_received[ref] = min(
                attempts, key=lambda row: (arrival(row["received_at"]),
                                           row["ingest_id"]))
            passed = [row for row in attempts if row["qc_state"] in QC_ADMITS]
            if passed:
                self.canonical[ref] = min(
                    passed,
                    key=lambda row: (-whole(row["revision_no"]), row["ingest_id"]))

    # ------------------------------------- V2 rate and V3 source span
    def resolve_assets(self) -> None:
        self.assets = {}
        self.asset_rows = []
        for ref in self.content_refs:
            received = self.first_received[ref]
            attempt = self.canonical.get(ref)
            if attempt is None:
                blank = dict.fromkeys(
                    ("canonical_ingest_id", "revision_no", "qc_state",
                     "rate_code", "rate_num", "rate_den", "tc_base",
                     "drop_frame", "som_tc", "eom_tc", "source_frames",
                     "channel_frames_exact"), "")
                blank.update({"content_ref": ref,
                              "house_no": received["house_no"],
                              "anchor_ingest_id": received["ingest_id"],
                              "inclusion_state": "AS_EXCLUDED"})
                self.asset_rows.append(blank)
                continue
            num, den, base, drop = self.asset_timebase(attempt)
            source = self._span(attempt["som_tc"], attempt["eom_tc"], base, drop)
            exact = to_channel_frames(source, num, den)
            self.assets[ref] = {"attempt": attempt, "rate_num": num,
                                "rate_den": den, "tc_base": base, "drop": drop,
                                "source_frames": source, "exact": exact,
                                "house_no": received["house_no"]}
            self.asset_rows.append({
                "content_ref": ref,
                "canonical_ingest_id": attempt["ingest_id"],
                "revision_no": attempt["revision_no"],
                "qc_state": attempt["qc_state"],
                "rate_code": attempt["rate_code"],
                "rate_num": str(num),
                "rate_den": str(den),
                "tc_base": str(base),
                "drop_frame": "yes" if drop else "no",
                "som_tc": attempt["som_tc"],
                "eom_tc": attempt["eom_tc"],
                "source_frames": str(source),
                "channel_frames_exact": fixed_point(exact),
                "house_no": received["house_no"],
                "anchor_ingest_id": received["ingest_id"],
                "inclusion_state": "AS_INCLUDED"})

    def order_the_day(self) -> None:
        """The day runs in ascending broadcast day offset, ties on slot id. A
        slot whose asset never reached a canonical attempt cannot transmit
        and leaves the running order."""
        ordered = sorted(self.schedule,
                         key=lambda slot: (self.day_offset(slot["sched_start_tc"]),
                                           slot["slot_id"]))
        self.slots = [s for s in ordered if s["content_ref"] in self.assets]
        self.dropped = [s for s in ordered if s["content_ref"] not in self.assets]

    # ------------------------------- V4 channel conversion, V5 assembly
    @staticmethod
    def retention(parts: list) -> list:
        """V5 R12: the run of black before the first other part is trimmed at
        the head, the run after the last other part is trimmed at the tail,
        and everything between is transmitted, black included."""
        kinds = [part["part_kind"] for part in parts]
        lead = next((at for at, kind in enumerate(kinds) if kind != "PT_BLACK"),
                    len(kinds))
        trail = next((at for at in range(len(kinds) - 1, -1, -1)
                      if kinds[at] != "PT_BLACK"), -1)
        return ["PR_TRIMMED_HEAD" if at < lead
                else "PR_TRIMMED_TAIL" if at > trail
                else "PR_RETAINED"
                for at in range(len(kinds))]

    def assemble_segments(self) -> None:
        by_content: dict = {}
        for part in self.parts:
            by_content.setdefault(part["content_ref"], []).append(part)

        self.segment_rows = []
        self.material = {}
        self.flex = {}
        for slot in self.slots:
            slot_id = slot["slot_id"]
            scope = "V4:" + slot_id
            self.carry.open(scope)
            self.material[slot_id] = 0
            self.flex[slot_id] = 0
            asset = self.assets[slot["content_ref"]]
            run = sorted(by_content.get(slot["content_ref"], []),
                         key=lambda part: whole(part["part_no"]))
            if not run:
                # An asset with no part rows transmits its whole source span
                # as a single programme part.
                run = [{"content_ref": slot["content_ref"], "part_no": "0",
                        "part_kind": "PT_PROGRAMME",
                        "part_som_tc": asset["attempt"]["som_tc"],
                        "part_eom_tc": asset["attempt"]["eom_tc"]}]
            transmitted = 0
            for part, mark in zip(run, self.retention(run)):
                source = self._span(part["part_som_tc"], part["part_eom_tc"],
                                    asset["tc_base"], asset["drop"])
                exact = to_channel_frames(source, asset["rate_num"],
                                          asset["rate_den"])
                if mark == "PR_RETAINED":
                    frames = self.carry.bank(exact, scope)
                    transmitted += frames
                    if part["part_no"] == slot["flex_part_no"]:
                        self.flex[slot_id] = frames
                else:
                    frames = 0
                self.segment_rows.append({
                    "slot_id": slot_id,
                    "content_ref": slot["content_ref"],
                    "part_no": part["part_no"],
                    "part_kind": part["part_kind"],
                    "retention_state": mark,
                    "source_frames": str(source),
                    "channel_frames_exact": fixed_point(exact),
                    "channel_frames": str(frames),
                    "carry_after": fixed_point(self.carry.holding(scope))})
            self.material[slot_id] = transmitted

    # ------------------------------------------- V6 splice conditioning
    @staticmethod
    def snap(target: int, points: list, tolerance: int) -> tuple:
        """A break lands on an index point: back where the point sits within
        the tolerance behind the target, forward otherwise."""
        if not points:
            return target, "SNAP_NONE"
        behind = [point for point in points if point <= target]
        ahead = [point for point in points if point > target]
        back = behind[-1] if behind else None
        forward = ahead[0] if ahead else None
        if back is not None and target - back <= tolerance:
            landed = back
        elif forward is not None:
            landed = forward
        elif back is not None:
            landed = back
        else:
            landed = target
        if landed == target:
            return landed, "SNAP_EXACT"
        return landed, ("SNAP_BACK" if landed < target else "SNAP_FORWARD")

    def condition_splices(self) -> None:
        """The last break of a slot absorbs whatever the earlier breaks of
        that slot were displaced by, so a slot's break run does not walk."""
        points: dict = {}
        for row in self.index:
            points.setdefault(row["content_ref"], []).append(whole(row["idr_frame"]))
        for ref in points:
            points[ref].sort()
        planned: dict = {}
        for row in self.break_plan:
            planned.setdefault(row["slot_id"], []).append(row)

        tolerance = self.terms["snap_tolerance_frames"]
        self.break_rows = []
        self.national_breaks = {}
        for slot in self.slots:
            slot_id = slot["slot_id"]
            scope = "V6:" + slot_id
            self.carry.open(scope)
            plan = sorted(planned.get(slot_id, []),
                          key=lambda row: whole(row["break_no"]))
            index_points = points.get(slot["content_ref"], [])
            displaced = 0
            conditioned = []
            for position, row in enumerate(plan):
                nominal = self.carry.bank(
                    seconds_in_frames(whole(row["nominal_offset_seconds"])), scope)
                if position == len(plan) - 1:
                    target = max(0, nominal - displaced)
                else:
                    target = nominal
                landed, side = self.snap(target, index_points, tolerance)
                displaced += landed - nominal
                number = whole(row["break_no"])
                reference = "bk_%s_%02d" % (slot_id, number)
                conditioned.append({"break_ref": reference, "break_no": number,
                                    "position": landed,
                                    "avail_seconds": whole(row["avail_seconds"])})
                self.break_rows.append({
                    "slot_id": slot_id,
                    "break_no": row["break_no"],
                    "break_ref": reference,
                    "nominal_offset_seconds": row["nominal_offset_seconds"],
                    "nominal_frame": str(nominal),
                    "adjusted_target_frame": str(target),
                    "position_frame": str(landed),
                    "snap_side": side,
                    "displacement_frames": str(landed - nominal),
                    "avail_seconds": row["avail_seconds"],
                    "carry_after": fixed_point(self.carry.holding(scope))})
            self.national_breaks[slot_id] = conditioned

    # ------------------------------ V7 placement, V8 drift correction
    def choose_filler(self, gap: int, daypart: str) -> tuple:
        """V8 R19: the available row of the lowest predicate order that serves
        the junction slot's daypart, or any daypart, and spans the gap; the
        house filler with selection index zero when no row does."""
        fitting = [row for row in self.fillers
                   if row["stock_state"] == "FS_AVAILABLE"
                   and row["daypart_ref"] in (daypart, "DP_ANY")
                   and whole(row["min_frames"]) <= gap <= whole(row["max_frames"])]
        if not fitting:
            return self.config["house_filler_ref"], 0
        chosen = min(fitting, key=lambda row: whole(row["predicate_order"]))
        return chosen["filler_ref"], whole(chosen["predicate_order"])

    def place_the_day(self) -> None:
        """V7 and V8: floating slots follow the running cursor; a fixed slot
        starts at its scheduled offset and the difference is corrected, by
        trimming flexible parts back to the previous fixed junction on an
        overrun, by a filler on an underrun, or by nothing at all."""
        order = [slot["slot_id"] for slot in self.slots]
        kept = {slot_id: self.material[slot_id] for slot_id in order}
        give = {slot_id: self.flex[slot_id] for slot_id in order}
        cut = dict.fromkeys(order, 0)
        start: dict = {}
        self.corrections = []
        self.fills = []

        def note(junction: str, reason: str, frames: int, detail: str,
                 filler: str = "") -> None:
            self.corrections.append({"slot_id": junction, "reason": reason,
                                     "frames": frames, "detail_slot": detail,
                                     "filler_ref": filler})

        cursor = 0
        last_fixed = None
        for at, slot in enumerate(self.slots):
            slot_id = slot["slot_id"]
            if slot["junction_kind"] != "JK_FIXED":
                start[slot_id] = cursor
                cursor += kept[slot_id] - cut[slot_id]
                continue
            due = self.day_offset(slot["sched_start_tc"])
            if cursor > due:
                owed = cursor - due
                floor_at = last_fixed if last_fixed is not None else 0
                back = at - 1
                while owed > 0 and back >= floor_at:
                    donor = order[back]
                    taken = min(give[donor] - cut[donor], owed)
                    if taken > 0:
                        cut[donor] += taken
                        owed -= taken
                        note(slot_id, "CR_TRIM_FLEX" if back == at - 1
                             else "CR_TRIM_BACKFILL", taken, donor)
                    back -= 1
                if owed > 0:
                    note(slot_id, "CR_TRIM_SHORTFALL", owed, slot_id)
                running = start[order[floor_at]] if last_fixed is not None else 0
                for earlier in order[floor_at:at]:
                    start[earlier] = running
                    running += kept[earlier] - cut[earlier]
            elif cursor < due:
                filler, rank = self.choose_filler(due - cursor, slot["daypart_ref"])
                note(slot_id, "CR_FILL_INSERT", due - cursor, slot_id, filler)
                self.fills.append({
                    "slot_id": slot_id,
                    "junction_offset_frame": str(due),
                    "gap_frames": str(due - cursor),
                    "filler_ref": filler,
                    "daypart_ref": slot["daypart_ref"],
                    "selection_index": str(rank)})
            else:
                note(slot_id, "CR_NO_CHANGE", 0, slot_id)
            start[slot_id] = due
            cursor = due + kept[slot_id] - cut[slot_id]
            last_fixed = at

        self.placed = []
        for at, slot in enumerate(self.slots):
            slot_id = slot["slot_id"]
            sent = kept[slot_id] - cut[slot_id]
            scheduled = self.day_offset(slot["sched_start_tc"])
            self.placed.append({
                "slot_id": slot_id,
                "content_ref": slot["content_ref"],
                "sequence_no": at + 1,
                "junction_kind": slot["junction_kind"],
                "sched_start_frame": scheduled,
                "actual_start_frame": start[slot_id],
                "material_frames": kept[slot_id],
                "trim_frames": cut[slot_id],
                "transmitted_frames": sent,
                "end_frame": start[slot_id] + sent,
                "drift_frames": start[slot_id] - scheduled,
                "hour_label": self.clock_hour(start[slot_id]),
                "daypart_ref": slot["daypart_ref"],
                "placement_state": "PL_PLACED"})
        self.day_end = max((row["end_frame"] for row in self.placed), default=0)

    # ---------------------------------------- V10 market substitution
    def substitute_markets(self) -> None:
        """A blackout window is inclusive of both its dates. Where more than
        one rule covers a slot the lowest precedence rule stands, unless a
        rule that overturns is among them, in which case the last overturning
        rule in precedence order takes it."""
        self.substitute_breaks = {}
        for row in self.substitutes:
            self.substitute_breaks.setdefault(row["substitute_ref"], []).append(row)

        self.blacked = {}
        self.override_rows = []
        for market in self.markets:
            for slot in self.placed:
                covering = [rule for rule in self.blackouts
                            if rule["market_ref"] == market
                            and rule["content_ref"] == slot["content_ref"]
                            and as_date(rule["window_from"]) <= self.tx_date
                            <= as_date(rule["window_to"])]
                if not covering:
                    continue
                covering.sort(key=lambda rule: (whole(rule["precedence"]),
                                                rule["rule_id"]))
                settled = covering[0]
                for rule in covering:
                    if rule["override"] == "yes":
                        settled = rule
                self.blacked[(market, slot["slot_id"])] = settled
                self.override_rows.append({
                    "market_ref": market,
                    "slot_id": slot["slot_id"],
                    "content_ref": slot["content_ref"],
                    "rule_id": settled["rule_id"],
                    "precedence": settled["precedence"],
                    "substitute_ref": settled["substitute_ref"],
                    "override_flag": settled["override"],
                    "national_break_count": str(
                        len(self.national_breaks.get(slot["slot_id"], []))),
                    "substitute_break_count": str(
                        len(self.substitute_breaks.get(settled["substitute_ref"], [])))})
        self.override_rows.sort(key=lambda row: (row["market_ref"], row["slot_id"]))

    # ----------------------------------------------- V9 avail derivation
    def derive_avails(self) -> None:
        """Each market carries the national break set except where it is
        blacked, where it carries the substitute set instead. Capacity is
        converted in transmission order inside a per market scope."""
        self.avails = {}
        for market in self.markets:
            capacity_scope = "V9:" + market
            substitute_scope = "V10:" + market
            self.carry.open(capacity_scope)
            self.carry.open(substitute_scope)
            breaks = []
            for slot in self.placed:
                rule = self.blacked.get((market, slot["slot_id"]))
                if rule is None:
                    for item in self.national_breaks.get(slot["slot_id"], []):
                        at = slot["actual_start_frame"] + item["position"]
                        breaks.append({
                            "break_ref": item["break_ref"],
                            "slot_id": slot["slot_id"],
                            "break_no": item["break_no"],
                            "origin": "BO_NATIONAL",
                            "position_frame": at,
                            "capacity_frames": 0,
                            "daypart_ref": slot["daypart_ref"],
                            "hour_label": self.clock_hour(at),
                            "avail_seconds": item["avail_seconds"]})
                    continue
                plan = sorted(self.substitute_breaks.get(rule["substitute_ref"], []),
                              key=lambda row: whole(row["break_no"]))
                for row in plan:
                    offset = self.carry.bank(
                        seconds_in_frames(whole(row["nominal_offset_seconds"])),
                        substitute_scope)
                    at = slot["actual_start_frame"] + offset
                    number = whole(row["break_no"])
                    breaks.append({
                        "break_ref": "sb_%s_%02d" % (rule["substitute_ref"], number),
                        "slot_id": slot["slot_id"],
                        "break_no": number,
                        "origin": "BO_SUBSTITUTE",
                        "position_frame": at,
                        "capacity_frames": 0,
                        "daypart_ref": slot["daypart_ref"],
                        "hour_label": self.clock_hour(at),
                        "avail_seconds": whole(row["avail_seconds"])})
            breaks.sort(key=lambda item: (item["position_frame"], item["break_ref"]))
            for item in breaks:
                item["capacity_frames"] = self.carry.bank(
                    seconds_in_frames(item.pop("avail_seconds")), capacity_scope)
            self.avails[market] = breaks

    # --------------------------------------------------- spot durations
    def convert_spot_durations(self) -> None:
        """Spot durations convert under a per advertiser carry scope, and
        they convert before any admission decision is taken, so the frames a
        spot occupies do not depend on whether it was admitted."""
        self.spot_frames = {}
        for order in sorted(self.orders,
                            key=lambda row: (row["advertiser_ref"], row["order_ref"])):
            scope = "V11:" + order["advertiser_ref"]
            if scope not in self.carry.residual:
                self.carry.open(scope)
            self.spot_frames[order["order_ref"]] = self.carry.bank(
                seconds_in_frames(int(order["nominal_seconds"])), scope)

    # ------------------------------------------------------- admission
    def settled_clearance(self) -> dict:
        """V9 R32: the state on the row with the greatest journal_seq."""
        latest: dict = {}
        for row in self.clearance_journal:
            seq = whole(row["journal_seq"])
            known = latest.get(row["clearance_ref"])
            if known is None or seq > known[0]:
                latest[row["clearance_ref"]] = (seq, row["clearance_state"])
        return {ref: state for ref, (_, state) in latest.items()}

    def rate_card(self, reference: str):
        """V11 R28: the row with the greatest effective_from that is on or
        before the transmission date, or None when no row is."""
        effective = [row for row in self.cards
                     if row["rate_card_ref"] == reference
                     and as_date(row["effective_from"]) <= self.tx_date]
        return max(effective, key=lambda row: (as_date(row["effective_from"]),
                                               whole(row["card_revision"])),
                   default=None)

    @staticmethod
    def slot_of_break(reference: str):
        matched = _NATIONAL_BREAK.match(reference)
        return matched.group(1) if matched else None

    def deferral_for(self, order: dict, market: str, breaks: dict,
                     filled: dict, seated: dict, clearance: dict,
                     minimum: int):
        """V9 R22: the first of the seven predicates that holds, as its one
        based index and its reason, or None when the order is admitted."""
        target = breaks.get(order["break_ref"])
        frames = self.spot_frames[order["order_ref"]]
        if clearance.get(order["clearance_ref"]) == "CL_HELD":
            return 1, "DF_CLEARANCE_HELD"
        if (market, self.slot_of_break(order["break_ref"])) in self.blacked:
            return 2, "DF_MARKET_BLACKED"
        if target is None:
            return 3, "DF_NO_MATCHING_BREAK"
        if order["daypart_ref"] != target["daypart_ref"]:
            return 4, "DF_DAYPART_MISMATCH"
        if self.rate_card(order["rate_card_ref"]) is None:
            return 5, "DF_NO_RATE_CARD"
        if filled.get(target["break_ref"], 0) + frames > target["capacity_frames"]:
            return 6, "DF_BREAK_FULL"
        classes = seated.get(target["break_ref"], [])
        landing = len(classes) + 1
        if any(klass == order["separation_class"] and landing - position < minimum
               for position, klass in enumerate(classes, start=1)):
            return 7, "DF_SEPARATION"
        return None

    def admit_spots(self) -> None:
        """V9: market by market, orders walked by ascending priority band and
        order reference, each admitted unless a predicate settles it."""
        minimum = self.regulatory["separation_minimum_positions"]
        clearance = self.settled_clearance()
        self.admitted = []
        self.deferred = []
        for market in self.markets:
            breaks = {item["break_ref"]: item for item in self.avails[market]}
            filled: dict = {}
            seated: dict = {}
            queue = sorted((order for order in self.orders
                            if order["market_ref"] == market),
                           key=lambda order: (int(order["priority_band"]),
                                              order["order_ref"]))
            for order in queue:
                frames = self.spot_frames[order["order_ref"]]
                settled = self.deferral_for(order, market, breaks, filled, seated,
                                            clearance, minimum)
                if settled is not None:
                    self.deferred.append({
                        "order_ref": order["order_ref"],
                        "market_ref": market,
                        "break_ref": order["break_ref"],
                        "deferral_reason": settled[1],
                        "predicate_index": settled[0],
                        "spot_frames": frames})
                    continue
                target = breaks[order["break_ref"]]
                opens = target["position_frame"] + filled.get(target["break_ref"], 0)
                filled[target["break_ref"]] = filled.get(target["break_ref"], 0) + frames
                seated.setdefault(target["break_ref"], []).append(order["separation_class"])
                self.admitted.append({
                    "market_ref": market,
                    "break_ref": target["break_ref"],
                    "break_position_frame": target["position_frame"],
                    "position_in_break": len(seated[target["break_ref"]]),
                    "order_ref": order["order_ref"],
                    "advertiser_ref": order["advertiser_ref"],
                    "separation_class": order["separation_class"],
                    "spot_frames": frames,
                    "start_frame": opens,
                    "end_frame": opens + frames,
                    "hour_label": self.clock_hour(opens)})
        self.admitted.sort(key=lambda row: (row["market_ref"],
                                            row["break_position_frame"],
                                            row["break_ref"],
                                            row["position_in_break"]))
        self.deferred.sort(key=lambda row: (row["order_ref"], row["market_ref"]))

    # ------------------------------------------------- V11 settlement
    def billable_grains(self, frames: int) -> int:
        """V11 R27: the smallest whole number of grains covering the frames."""
        grain = seconds_in_frames(self.regulatory["billing_grain_seconds"])
        return -(-Fraction(frames) // grain)

    def settle(self) -> None:
        """V11: grains priced by the eligible card, commission from the live
        control set at half even, the major figure at the currency's own
        number of places."""
        currency = {row["advertiser_ref"]: row["settlement_currency"]
                    for row in self.advertisers}
        by_reference = {order["order_ref"]: order for order in self.orders}
        self.settlement_rows = []
        self.exceptions = []
        for spot in self.admitted:
            order = by_reference[spot["order_ref"]]
            card = self.rate_card(order["rate_card_ref"])
            frames = spot["spot_frames"]
            unbilled = self.unbilled.get(spot["order_ref"], 0)
            grains = self.billable_grains(frames - unbilled)
            gross = grains * whole(card["minor_per_grain"])
            share_num, share_den = self.commission[spot["advertiser_ref"]]
            commission = half_even(Fraction(gross * share_num, share_den))
            places = self.minor_units[currency[spot["advertiser_ref"]]]
            self.settlement_rows.append({
                "order_ref": spot["order_ref"],
                "advertiser_ref": spot["advertiser_ref"],
                "market_ref": spot["market_ref"],
                "break_ref": spot["break_ref"],
                "currency": currency[spot["advertiser_ref"]],
                "delivered_frames": str(frames),
                "unbilled_frames": str(unbilled),
                "billable_grains": str(grains),
                "rate_card_ref": order["rate_card_ref"],
                "effective_from": card["effective_from"],
                "minor_per_grain": str(whole(card["minor_per_grain"])),
                "gross_minor": str(gross),
                "commission_minor": str(commission),
                "net_minor": str(gross - commission),
                "gross_major": fixed_point(Fraction(gross, 10 ** places), places)})
            if frames == 0:
                self.exceptions.append({
                    "order_ref": spot["order_ref"],
                    "exception_code": "EX_ZERO_DELIVERY",
                    "rate_card_ref": order["rate_card_ref"],
                    "detail": "admitted spot occupies no channel frame"})
        for order in self.orders:
            if self.rate_card(order["rate_card_ref"]) is not None:
                continue
            dates = sorted(row["effective_from"] for row in self.cards
                           if row["rate_card_ref"] == order["rate_card_ref"])
            self.exceptions.append({
                "order_ref": order["order_ref"],
                "exception_code": "EX_NO_CARD",
                "rate_card_ref": order["rate_card_ref"],
                "detail": "earliest card dated " + (dates[0] if dates else "")})
        self.settlement_rows.sort(key=lambda row: (row["order_ref"],
                                                   row["market_ref"]))
        self.exceptions.sort(key=lambda row: (row["order_ref"],
                                              row["exception_code"]))

    # -------------------------------------------------- V12 make good
    def make_good(self) -> None:
        """V12: a deferral that a card can value becomes an obligation; an
        advertiser's obligations above its cap share the cap by largest
        remainder, ties to the lower order reference."""
        cap_num = self.terms["makegood_cap_num"]
        cap_den = self.terms["makegood_cap_den"]
        by_reference = {order["order_ref"]: order for order in self.orders}
        day_gross: dict = {}
        for row in self.settlement_rows:
            day_gross[row["advertiser_ref"]] = (day_gross.get(row["advertiser_ref"], 0)
                                                + whole(row["gross_minor"]))
        owed: dict = {}
        for item in self.deferred:
            order = by_reference[item["order_ref"]]
            card = self.rate_card(order["rate_card_ref"])
            if item["deferral_reason"] == "DF_NO_RATE_CARD" or card is None:
                continue
            owed.setdefault(order["advertiser_ref"], []).append({
                "order_ref": item["order_ref"],
                "deferral_reason": item["deferral_reason"],
                "raw_minor": self.billable_grains(item["spot_frames"])
                * whole(card["minor_per_grain"])})
        # An admitted spot that lost whole grains to the cap is owed them.
        for row in self.settlement_rows:
            delivered = whole(row["delivered_frames"])
            lost = (self.billable_grains(delivered)
                    - self.billable_grains(delivered - whole(row["unbilled_frames"])))
            if lost:
                owed.setdefault(row["advertiser_ref"], []).append({
                    "order_ref": row["order_ref"],
                    "deferral_reason": "DF_OVER_CAP",
                    "raw_minor": lost * whole(row["minor_per_grain"])})

        self.makegood_entries = []
        self.makegood_total = 0
        for advertiser in sorted(set(owed) | set(day_gross)):
            obligations = sorted(owed.get(advertiser, []),
                                 key=lambda row: row["order_ref"])
            gross = day_gross.get(advertiser, 0)
            cap = (cap_num * gross) // cap_den
            raw_total = sum(row["raw_minor"] for row in obligations)
            if raw_total > cap:
                shares = [Fraction(cap * row["raw_minor"], raw_total)
                          for row in obligations]
                for row, share in zip(obligations, shares):
                    row["allocated_minor"] = share.numerator // share.denominator
                left = cap - sum(row["allocated_minor"] for row in obligations)
                ranking = sorted(range(len(obligations)),
                                 key=lambda at: (obligations[at]["allocated_minor"]
                                                 - shares[at],
                                                 obligations[at]["order_ref"]))
                for at in ranking[:left]:
                    obligations[at]["allocated_minor"] += 1
            else:
                for row in obligations:
                    row["allocated_minor"] = row["raw_minor"]
            allocated = sum(row["allocated_minor"] for row in obligations)
            self.makegood_total += allocated
            self.makegood_entries.append({
                "advertiser_ref": advertiser,
                "day_gross_minor": gross,
                "cap_minor": cap,
                "raw_total_minor": raw_total,
                "allocated_total_minor": allocated,
                "obligations": obligations})

    # ------------------------------------------ V13 minutage compliance
    def check_minutage(self) -> None:
        """V13: each admitted spot counts in every clock hour its frames fall
        in, the last hour taking whatever runs past the end of the day, and
        an hour breaches only when it is above its own floored cap. The
        frames above the cap go unbilled, latest spots first, before V11
        settles."""
        minutes = self.regulatory["regulatory_minutes_per_clock_hour"]
        self.minutage_cap = math.floor(seconds_in_frames(60 * minutes))
        daypart_of = {row["hour_label"]: row["daypart_ref"] for row in self.dayparts}
        tally: dict = {}
        occupants: dict = {}
        for spot in self.admitted:
            for step, hour in enumerate(CLOCK_HOURS):
                begin = step * FRAMES_PER_CLOCK_HOUR
                close = (spot["end_frame"] if step == len(CLOCK_HOURS) - 1
                         else min(spot["end_frame"], begin + FRAMES_PER_CLOCK_HOUR))
                inside = close - max(spot["start_frame"], begin)
                if inside > 0:
                    key = (spot["market_ref"], hour)
                    tally[key] = tally.get(key, 0) + inside
                    occupants.setdefault(key, []).append((spot, inside))

        self.minutage_rows = []
        self.breach_count = 0
        self.unbilled = {}
        for market in self.markets:
            for hour in CLOCK_HOURS:
                frames = tally.get((market, hour), 0)
                cap = math.floor(seconds_in_frames(
                    60 * self.permitted_minutes.get((market, hour), minutes)))
                breached = frames > cap
                self.breach_count += breached
                if breached:
                    # The excess goes unbilled, latest spots of the hour first.
                    excess = frames - cap
                    latest_first = sorted(
                        occupants[(market, hour)],
                        key=lambda pair: (pair[0]["start_frame"], pair[0]["order_ref"]),
                        reverse=True)
                    for spot, inside in latest_first:
                        if not excess:
                            break
                        given = min(inside, excess)
                        self.unbilled[spot["order_ref"]] = (
                            self.unbilled.get(spot["order_ref"], 0) + given)
                        excess -= given
                self.minutage_rows.append({
                    "market_ref": market,
                    "hour_label": hour,
                    "daypart_ref": daypart_of[hour],
                    "advertising_frames": str(frames),
                    "advertising_seconds": fixed_point(
                        Fraction(frames * FPS_DEN, FPS_NUM)),
                    "cap_frames": str(cap),
                    "headroom_frames": str(cap - frames),
                    "breach_state": "MB_BREACH" if breached else "MB_WITHIN"})

    # ==================================================================
    # V14  the delivered package
    # ==================================================================
    def derive(self) -> dict:
        """Run every stage and return the published bytes by artifact name."""
        self.canonicalise()
        self.resolve_assets()
        self.order_the_day()
        self.assemble_segments()
        self.condition_splices()
        self.place_the_day()
        self.substitute_markets()
        self.derive_avails()
        self.convert_spot_durations()
        self.admit_spots()
        self.check_minutage()
        self.settle()
        self.make_good()
        return self._publish()

    def _placement_rows(self) -> list:
        rows = [{name: str(value) for name, value in row.items()}
                for row in self.placed]
        for slot in self.dropped:
            rows.append({
                "slot_id": slot["slot_id"],
                "content_ref": slot["content_ref"],
                "sequence_no": "0",
                "junction_kind": slot["junction_kind"],
                "sched_start_frame": "0",
                "actual_start_frame": "0",
                "material_frames": "0",
                "trim_frames": "0",
                "transmitted_frames": "0",
                "end_frame": "0",
                "drift_frames": "0",
                "hour_label": "",
                "daypart_ref": slot["daypart_ref"],
                "placement_state": "PL_DROPPED"})
        rows.sort(key=lambda row: (whole(row["sequence_no"]), row["slot_id"]))
        return rows

    def _correction_trace(self) -> tuple:
        entries = list(self.corrections)
        for slot in self.dropped:
            entries.append({"slot_id": slot["slot_id"],
                            "reason": "CR_SLOT_DROPPED", "frames": 0,
                            "detail_slot": slot["slot_id"], "filler_ref": ""})
        tally: dict = {}
        trace = []
        for sequence, entry in enumerate(entries, start=1):
            tally[entry["reason"]] = tally.get(entry["reason"], 0) + 1
            traced = dict(entry)
            traced["sequence"] = sequence
            trace.append(traced)
        return trace, tally

    def _advertiser_totals(self) -> list:
        ledger = {}
        for row in self.advertisers:
            ledger[row["advertiser_ref"]] = {
                "currency": row["settlement_currency"], "admitted_spots": 0,
                "deferred_spots": 0, "delivered_frames": 0, "gross_minor": 0,
                "commission_minor": 0, "net_minor": 0, "makegood_minor": 0}
        for row in self.settlement_rows:
            entry = ledger[row["advertiser_ref"]]
            entry["admitted_spots"] += 1
            entry["delivered_frames"] += whole(row["delivered_frames"])
            entry["gross_minor"] += whole(row["gross_minor"])
            entry["commission_minor"] += whole(row["commission_minor"])
            entry["net_minor"] += whole(row["net_minor"])
        advertiser_of = {order["order_ref"]: order["advertiser_ref"]
                         for order in self.orders}
        for item in self.deferred:
            ledger[advertiser_of[item["order_ref"]]]["deferred_spots"] += 1
        for entry in self.makegood_entries:
            if entry["advertiser_ref"] in ledger:
                ledger[entry["advertiser_ref"]]["makegood_minor"] = \
                    entry["allocated_total_minor"]
        rows = []
        for reference in sorted(ledger):
            entry = ledger[reference]
            places = self.minor_units[entry["currency"]]
            rows.append({
                "advertiser_ref": reference,
                "currency": entry["currency"],
                "admitted_spots": str(entry["admitted_spots"]),
                "deferred_spots": str(entry["deferred_spots"]),
                "delivered_frames": str(entry["delivered_frames"]),
                "gross_minor": str(entry["gross_minor"]),
                "commission_minor": str(entry["commission_minor"]),
                "net_minor": str(entry["net_minor"]),
                "makegood_minor": str(entry["makegood_minor"]),
                "gross_major": fixed_point(
                    Fraction(entry["gross_minor"], 10 ** places), places)})
        return rows

    def _reconciliation(self, placement_rows: list, break_counts: dict) -> str:
        """The recomputed day set against the previous automated conform,
        which is a disavowed source everywhere except here."""
        previous = {row["slot_id"]: row for row in self.prior}
        by_slot = {row["slot_id"]: row for row in placement_rows}
        body = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<reconciliation channel_ref="%s" transmission_date="%s">'
                % (attr(self.config["channel_ref"]),
                   attr(self.config["transmission_date"]))]
        agreeing = 0
        differing = 0
        start_delta = 0
        material_delta = 0
        for slot_id in sorted(by_slot):
            row = by_slot[slot_id]
            was = previous.get(slot_id, {})
            was_start = whole(was.get("prior_start_frame", ""))
            was_material = whole(was.get("prior_material_frames", ""))
            was_breaks = whole(was.get("prior_break_count", ""))
            now_start = whole(row["actual_start_frame"])
            now_material = whole(row["material_frames"])
            now_breaks = break_counts.get(slot_id, 0)
            if (was_start, was_material, was_breaks) == (now_start, now_material,
                                                         now_breaks):
                agreeing += 1
            else:
                differing += 1
            start_delta += abs(now_start - was_start)
            material_delta += abs(now_material - was_material)
            body.append(
                '  <slot slot_id="%s" placement_state="%s" prior_start_frame="%d" '
                'start_frame="%d" start_delta="%d" prior_material_frames="%d" '
                'material_frames="%d" material_delta="%d" prior_break_count="%d" '
                'break_count="%d" break_delta="%d"/>'
                % (attr(slot_id), attr(row["placement_state"]), was_start,
                   now_start, now_start - was_start, was_material, now_material,
                   now_material - was_material, was_breaks, now_breaks,
                   now_breaks - was_breaks))
        body.append('  <totals slots="%d" agreeing="%d" differing="%d" '
                    'absolute_start_delta="%d" absolute_material_delta="%d"/>'
                    % (len(by_slot), agreeing, differing, start_delta,
                       material_delta))
        body.append("</reconciliation>")
        return "\n".join(body) + "\n"

    def _playout_schedule(self, break_counts: dict) -> str:
        opens = timecode_to_frames(DAY_OPENS_AT, TC_BASE, TC_DROP)
        body = ["[channel]",
                "channel_ref = %s" % self.config["channel_ref"],
                "transmission_date = %s" % self.config["transmission_date"],
                "day_start_tc = %s" % DAY_OPENS_AT,
                "day_end_frame = %d" % self.day_end,
                "placed_slot_count = %d" % len(self.placed),
                ""]
        for row in self.placed:
            at = (opens + row["actual_start_frame"]) % FRAMES_PER_DAY
            body.extend([
                "[slot:%s]" % row["slot_id"],
                "content_ref = %s" % row["content_ref"],
                "sequence_no = %d" % row["sequence_no"],
                "start_frame = %d" % row["actual_start_frame"],
                "start_tc = %s" % frames_to_timecode(at, TC_BASE, TC_DROP),
                "transmitted_frames = %d" % row["transmitted_frames"],
                "trim_frames = %d" % row["trim_frames"],
                "break_count = %d" % break_counts.get(row["slot_id"], 0),
                ""])
        return "\n".join(body).rstrip("\n") + "\n"

    def _publish(self) -> dict:
        published: dict = {}
        breaks_per_slot = {slot["slot_id"]: len(
            self.national_breaks.get(slot["slot_id"], []))
            for slot in self.schedule}

        published["asset_register.csv"] = utf8(delimited(
            ["content_ref", "canonical_ingest_id", "revision_no", "qc_state",
             "rate_code", "rate_num", "rate_den", "tc_base", "drop_frame",
             "som_tc", "eom_tc", "source_frames", "channel_frames_exact",
             "house_no", "anchor_ingest_id", "inclusion_state"],
            self.asset_rows, ","))

        published["segment_conform.csv"] = utf8(delimited(
            ["slot_id", "content_ref", "part_no", "part_kind",
             "retention_state", "source_frames", "channel_frames_exact",
             "channel_frames", "carry_after"],
            sorted(self.segment_rows,
                   key=lambda row: (row["slot_id"], whole(row["part_no"]))), ","))

        published["break_positions.csv"] = utf8(delimited(
            ["slot_id", "break_no", "break_ref", "nominal_offset_seconds",
             "nominal_frame", "adjusted_target_frame", "position_frame",
             "snap_side", "displacement_frames", "avail_seconds",
             "carry_after"],
            sorted(self.break_rows,
                   key=lambda row: (row["slot_id"], whole(row["break_no"]))), ","))

        placement_rows = self._placement_rows()
        published["slot_placement.csv"] = utf8(delimited(
            ["slot_id", "content_ref", "sequence_no", "junction_kind",
             "sched_start_frame", "actual_start_frame", "material_frames",
             "trim_frames", "transmitted_frames", "end_frame", "drift_frames",
             "hour_label", "daypart_ref", "placement_state"],
            placement_rows, ","))

        trace, correction_tally = self._correction_trace()
        published["conform_trace.json"] = utf8(json_block({
            "corrections": trace,
            "totals": correction_tally,
            "day_end_frame": self.day_end,
            "correction_count": len(trace)}))

        published["filler_plan.csv"] = utf8(delimited(
            ["slot_id", "junction_offset_frame", "gap_frames", "filler_ref",
             "daypart_ref", "selection_index"],
            sorted(self.fills, key=lambda row: row["slot_id"]), ","))

        published["avail_plan.tsv"] = utf8(delimited(
            ["market_ref", "break_ref", "break_position_frame",
             "position_in_break", "order_ref", "advertiser_ref",
             "separation_class", "spot_frames", "start_frame", "end_frame",
             "hour_label"],
            [{name: str(value) for name, value in row.items()}
             for row in self.admitted], "\t"))

        published["deferral_ledger.jsonl"] = utf8(json_lines(self.deferred))

        published["market_overrides.csv"] = utf8(delimited(
            ["market_ref", "slot_id", "content_ref", "rule_id", "precedence",
             "substitute_ref", "override_flag", "national_break_count",
             "substitute_break_count"], self.override_rows, ","))

        stream = []
        for market in self.markets:
            breaks = self.avails[market]
            published[MARKET_AVAILS_NAME % market] = utf8(json_block({
                "market_ref": market,
                "break_count": len(breaks),
                "capacity_frames_total": sum(item["capacity_frames"]
                                             for item in breaks),
                "carry_residual_capacity": fixed_point(
                    self.carry.holding("V9:" + market)),
                "carry_residual_substitute": fixed_point(
                    self.carry.holding("V10:" + market)),
                "breaks": breaks}))
            for item in breaks:
                stream.append(dict(item, market_ref=market))
        stream.sort(key=lambda row: (row["market_ref"], row["position_frame"],
                                     row["break_ref"]))
        published["market_avail_stream.jsonl"] = utf8(json_lines(stream))

        published["settlement_ledger.psv"] = utf8(delimited(
            ["order_ref", "advertiser_ref", "market_ref", "break_ref",
             "currency", "delivered_frames", "unbilled_frames",
             "billable_grains", "rate_card_ref", "effective_from",
             "minor_per_grain",
             "gross_minor", "commission_minor", "net_minor", "gross_major"],
            self.settlement_rows, "|"))

        published["makegood_ledger.json"] = utf8(json_block({
            "advertisers": self.makegood_entries,
            "allocated_total_minor": self.makegood_total,
            "cap_num": self.terms["makegood_cap_num"],
            "cap_den": self.terms["makegood_cap_den"]}))

        published["exception_ledger.jsonl"] = utf8(json_lines(self.exceptions))

        published["advertiser_summary.csv"] = utf8(delimited(
            ["advertiser_ref", "currency", "admitted_spots", "deferred_spots",
             "delivered_frames", "gross_minor", "commission_minor",
             "net_minor", "makegood_minor", "gross_major"],
            self._advertiser_totals(), ","))

        published["minutage_report.csv"] = utf8(delimited(
            ["market_ref", "hour_label", "daypart_ref", "advertising_frames",
             "advertising_seconds", "cap_frames", "headroom_frames",
             "breach_state"], self.minutage_rows, ","))

        scopes = [{"scope": name,
                   "conversions": self.carry.conversions.get(name, 0),
                   "residual": fixed_point(self.carry.residual[name])}
                  for name in self.carry.scopes()]
        published["carry_ledger.json"] = utf8(json_block({
            "scopes": scopes,
            "scope_count": len(scopes),
            "conversion_count": sum(entry["conversions"] for entry in scopes),
            "residual_total": fixed_point(
                sum(self.carry.residual.values(), Fraction(0)))}))

        published["reconciliation.xml"] = utf8(
            self._reconciliation(placement_rows, breaks_per_slot))
        published["playout_schedule.ini"] = utf8(
            self._playout_schedule(breaks_per_slot))

        gross_total = sum(whole(row["gross_minor"])
                          for row in self.settlement_rows)
        deferral_tally: dict = {}
        for item in self.deferred:
            deferral_tally[item["deferral_reason"]] = (
                deferral_tally.get(item["deferral_reason"], 0) + 1)
        deferral_tally["DF_OVER_CAP"] = sum(
            1 for entry in self.makegood_entries for row in entry["obligations"]
            if row["deferral_reason"] == "DF_OVER_CAP")

        report = ["# Transmission day report", "",
                  "- channel_ref: %s" % self.config["channel_ref"],
                  "- transmission_date: %s" % self.config["transmission_date"],
                  "- instance_ref: %s" % self.config["instance_ref"],
                  "- live_control_set: %s" % self.config["workbook_control_set"],
                  "- scheduled_slots: %d" % len(self.schedule),
                  "- placed_slots: %d" % len(self.placed),
                  "- dropped_slots: %d" % len(self.dropped),
                  "- day_end_frame: %d" % self.day_end,
                  "- corrections: %d" % len(trace),
                  "- admitted_spots: %d" % len(self.admitted),
                  "- deferred_spots: %d" % len(self.deferred),
                  "- gross_minor_total: %d" % gross_total,
                  "- makegood_minor_total: %d" % self.makegood_total,
                  "", "## Correction totals", ""]
        report.extend("- %s: %d" % (reason, correction_tally.get(reason, 0))
                      for reason in CORRECTION_VOCAB)
        report.extend(["", "## Deferral totals", ""])
        report.extend("- %s: %d" % (reason, deferral_tally.get(reason, 0))
                      for reason in DEFERRAL_VOCAB)
        published["day_report.md"] = utf8("\n".join(report) + "\n")

        frames_by_market: dict = {}
        for row in self.minutage_rows:
            frames_by_market[row["market_ref"]] = (
                frames_by_market.get(row["market_ref"], 0)
                + whole(row["advertising_frames"]))
        compliance = ["# Compliance summary", "",
                      "- regulatory_minutes_per_clock_hour: %d"
                      % self.regulatory["regulatory_minutes_per_clock_hour"],
                      "- cap_frames: %d" % self.minutage_cap,
                      "- separation_minimum_positions: %d"
                      % self.regulatory["separation_minimum_positions"],
                      "- billing_grain_seconds: %d"
                      % self.regulatory["billing_grain_seconds"],
                      "- snap_tolerance_frames: %d"
                      % self.terms["snap_tolerance_frames"],
                      "- breach_hours: %d" % self.breach_count,
                      "", "## Advertising frames by market", ""]
        compliance.extend("- %s: %d" % (market, frames_by_market.get(market, 0))
                          for market in self.markets)
        compliance.extend(["", "## Breach hours", ""])
        breached = [row for row in self.minutage_rows
                    if row["breach_state"] == "MB_BREACH"]
        if breached:
            compliance.extend(
                "- %s %s frames %s over %s"
                % (row["market_ref"], row["hour_label"],
                   row["advertising_frames"], row["cap_frames"])
                for row in breached)
        else:
            compliance.append("- none")
        published["compliance_summary.md"] = utf8("\n".join(compliance) + "\n")

        published["manifest.json"] = utf8(json_block({
            "instance_ref": self.config["instance_ref"],
            "channel_ref": self.config["channel_ref"],
            "transmission_date": self.config["transmission_date"],
            "artifact_count": len(PUBLISHED),
            "core_order": list(DIGEST_ORDER),
            "digest": day_digest(published),
            "slot_count": len(self.schedule),
            "placed_slot_count": len(self.placed),
            "dropped_slot_count": len(self.dropped),
            "admitted_spot_count": len(self.admitted),
            "deferred_spot_count": len(self.deferred),
            "breach_hour_count": self.breach_count,
            "live_control_set": self.control_set_sheet,
            "snap_tolerance_frames": self.terms["snap_tolerance_frames"],
            "makegood_cap_num": self.terms["makegood_cap_num"],
            "makegood_cap_den": self.terms["makegood_cap_den"],
            "separation_minimum_positions":
                self.regulatory["separation_minimum_positions"],
            "billing_grain_seconds": self.regulatory["billing_grain_seconds"],
            "regulatory_minutes_per_clock_hour":
                self.regulatory["regulatory_minutes_per_clock_hour"],
            "day_end_frame": self.day_end}))
        return published


# ==========================================================================
# entry point
# ==========================================================================
def publish(published: dict, out_dir) -> None:
    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for name in PUBLISHED:
        (destination / name).write_bytes(published[name])


def directories(argv: list) -> tuple:
    """`--data` and `--out`, each optional, each falling back to the path the
    container publishes. Anything else on the command line is ignored."""
    chosen = {"--data": DEFAULT_DATA_DIR, "--out": DEFAULT_OUT_DIR}
    walk = iter(range(len(argv)))
    for at in walk:
        if argv[at] in chosen and at + 1 < len(argv):
            chosen[argv[at]] = argv[at + 1]
            next(walk, None)
    return chosen["--data"], chosen["--out"]


def main(argv=None) -> int:
    data_dir, out_dir = directories(
        list(sys.argv[1:] if argv is None else argv))
    publish(TransmissionDay(data_dir).derive(), out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
