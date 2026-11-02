"""Deterministic verifier for the playout conform and avail task.

The verifier owns its corpus. It regenerates the whole input tree from a
named seed into a temporary directory, recomputes every expected artifact
from that regeneration, and grades the agent bytes under the output
directory against it. It never reads the agent corpus, which does not exist
in this container.

Most of the positive weight is spent on the delivered program rather than on
the delivered bytes. Seven further transmission days are minted here from
seeds the agent never sees. The delivered conform program is run against
three of them as a subprocess, one under a dense profile and one under a
sparse profile that the shipped day does not use, and its output is graded
byte for byte against the day those inputs entail. A fourth opens with a
scheduled slot that has no canonical attempt and is graded the same way. A
fifth is staged at the container paths and graded the same way through a run
with neither flag, a run over a sixth is graded on its manifest digest alone,
and the seventh is planted in the working directory of a run to catch a
program that reads a remembered path. The program is also run twice over the
shipped day to test that its output is deterministic.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path

from rewardkit import criteria, criterion

# Every published ratio carries this many decimal places. Every other
# published quantity is a whole number in the unit its stage names.
PLACES = 10

# The channel transmits at this exact rational rate and publishes drop frame
# timecode on a base of thirty.
CH_NUM = 30000
CH_DEN = 1001
CH_BASE = 30
CH_DF = True

# The broadcast day opens at this timecode and runs for one whole day of
# channel timecode frames.
DAY_START_TC = "06:00:00;00"
DAY_FRAMES = 24 * 3600 * CH_BASE - 2 * (24 * 60 - 24 * 6)

# Closed vocabularies. Every member of every one of these is emitted by the
# corpus generator, so no comparison in this module is ever made against a
# token the agent has not seen.
QC_STATES = [
    "QC_PASSED",
    "QC_PASSED_WITH_NOTES",
    "QC_PENDING",
    "QC_REJECTED",
    "QC_WITHDRAWN",
]
QC_PASSED_SET = ["QC_PASSED", "QC_PASSED_WITH_NOTES"]

PART_KINDS = ["PT_BLACK", "PT_BUMPER", "PT_PROGRAMME", "PT_PROMO"]

JUNCTION_KINDS = ["JK_FIXED", "JK_FLOAT"]

CORRECTION_REASONS = [
    "CR_FILL_INSERT",
    "CR_NO_CHANGE",
    "CR_SLOT_DROPPED",
    "CR_TRIM_BACKFILL",
    "CR_TRIM_FLEX",
    "CR_TRIM_SHORTFALL",
]

DEFERRAL_REASONS = [
    "DF_BREAK_FULL",
    "DF_CLEARANCE_HELD",
    "DF_DAYPART_MISMATCH",
    "DF_MARKET_BLACKED",
    "DF_NO_MATCHING_BREAK",
    "DF_NO_RATE_CARD",
    "DF_OVER_CAP",
    "DF_SEPARATION",
]

SNAP_SIDES = ["SNAP_BACK", "SNAP_EXACT", "SNAP_FORWARD", "SNAP_NONE"]

MARKETS = ["mk_coast", "mk_metro", "mk_north", "mk_valley"]

DAYPARTS = ["DP_BREAKFAST", "DP_DAYTIME", "DP_LATE", "DP_OVERNIGHT", "DP_PEAK"]

SEPARATION_CLASSES = [
    "SC_AUTO",
    "SC_FINANCE",
    "SC_PHARMA",
    "SC_RETAIL",
    "SC_TELCO",
]

CLEARANCE_STATES = ["CL_CLEARED", "CL_CONDITIONAL", "CL_HELD"]

FILLER_STATES = ["FS_AVAILABLE", "FS_EMBARGOED", "FS_EXPIRED"]

CURRENCIES = ["BHD", "EUR", "JPY", "USD"]

# The broadcast day is twenty four clock hours long and its hours are
# labelled from the hour the day opens, so the small hours sit at the end.
HOUR_LABELS = ["H%02d" % h for h in range(6, 30)]

FRAMES_PER_HOUR = 3600 * CH_BASE - 2 * (60 - 6)

DAYPART_BY_HOUR = {}
for _h in range(6, 30):
    if 6 <= _h < 10:
        DAYPART_BY_HOUR["H%02d" % _h] = "DP_BREAKFAST"
    elif 10 <= _h < 17:
        DAYPART_BY_HOUR["H%02d" % _h] = "DP_DAYTIME"
    elif 17 <= _h < 23:
        DAYPART_BY_HOUR["H%02d" % _h] = "DP_PEAK"
    elif 23 <= _h < 26:
        DAYPART_BY_HOUR["H%02d" % _h] = "DP_LATE"
    else:
        DAYPART_BY_HOUR["H%02d" % _h] = "DP_OVERNIGHT"

RATE_CODES = [
    "RC_2398",
    "RC_2400",
    "RC_2500",
    "RC_2997",
    "RC_3000",
    "RC_5000",
    "RC_5994",
]

CORE_FILES = [
    "asset_register.csv",
    "segment_conform.csv",
    "break_positions.csv",
    "slot_placement.csv",
    "avail_plan.tsv",
    "settlement_ledger.psv",
    "minutage_report.csv",
]

ARTIFACTS = [
    "asset_register.csv",
    "segment_conform.csv",
    "break_positions.csv",
    "slot_placement.csv",
    "conform_trace.json",
    "filler_plan.csv",
    "avail_plan.tsv",
    "deferral_ledger.jsonl",
    "market_overrides.csv",
    "market_avails_mk_coast.json",
    "market_avails_mk_metro.json",
    "market_avails_mk_north.json",
    "market_avails_mk_valley.json",
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

PROGRAM_NAME = "conform.py"


# --------------------------------------------------------------------------
# exact arithmetic
#
# Every derivation runs in Fraction. Nothing here ever touches a binary
# floating point number, so ties land where the rounding rule puts them and
# not where the hardware puts them.
# --------------------------------------------------------------------------
def F(x) -> Fraction:
    if isinstance(x, Fraction):
        return x
    return Fraction(x)


def nint(x) -> int:
    """Round an exact rational to a whole number, halves to even."""
    x = F(x)
    n, d = x.numerator, x.denominator
    q, r = divmod(n, d)
    twice = 2 * r
    if twice > d or (twice == d and q % 2 == 1):
        q += 1
    return q


def ffloor(x) -> int:
    """Floor of an exact rational, toward minus infinity."""
    x = F(x)
    return x.numerator // x.denominator


def fceil(x) -> int:
    x = F(x)
    return -((-x.numerator) // x.denominator)


def ratio(x, places: int = PLACES) -> str:
    """Render an exact rational as a fixed point decimal string, halves to
    even, with no negative zero and no exponent."""
    x = F(x)
    scale = 10 ** places
    n = nint(x * scale)
    sign = "-" if n < 0 else ""
    n = abs(n)
    whole, frac = divmod(n, scale)
    if places == 0:
        return f"{sign}{whole}"
    text = f"{sign}{whole}.{str(frac).rjust(places, '0')}"
    if text.startswith("-0.") and set(text[3:]) == {"0"}:
        return text[1:]
    return text


def safe_ratio(num, den, places: int = PLACES) -> str:
    """A ratio whose denominator may be zero. The rounding policy fixes the
    published value of an empty denominator at zero."""
    if F(den) == 0:
        return ratio(0, places)
    return ratio(F(num) / F(den), places)


def parse_date(text: str) -> date:
    y, m, d = (int(p) for p in text.strip().split("-"))
    return date(y, m, d)


def fmt_date(d: date) -> str:
    return d.isoformat()


# --------------------------------------------------------------------------
# timecode
#
# A timecode counts whole frames on an integer timecode base. Drop frame
# skips the first two frame numbers of every minute whose number is not a
# multiple of ten, scaled by the base, so the label tracks the wall clock
# while the frame count stays whole.
# --------------------------------------------------------------------------
_TC_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})[:;](\d{2,3})$")


def tc_parts(text: str) -> tuple:
    m = _TC_RE.match(text.strip())
    if m is None:
        raise ValueError("malformed timecode: " + text)
    return tuple(int(g) for g in m.groups())


def drop_per_minute(base: int) -> int:
    """Two frame numbers per minute at base thirty, and the same proportion
    at every other base the register admits."""
    return base * 2 // 30


def tc_to_frames(text: str, base: int, df: bool) -> int:
    hh, mm, ss, ff = tc_parts(text)
    total = ((hh * 60 + mm) * 60 + ss) * base + ff
    if df:
        minutes = hh * 60 + mm
        total -= drop_per_minute(base) * (minutes - minutes // 10)
    return total


def frames_to_tc(n: int, base: int, df: bool) -> str:
    sep = ";" if df else ":"
    if df:
        d = drop_per_minute(base)
        frames_per_10min = base * 600 - 9 * d
        frames_per_min = base * 60 - d
        n = n % (base * 86400 - d * (1440 - 144))
        block, rem = divmod(n, frames_per_10min)
        if rem < frames_per_min + d:
            minutes_in_block = 0
            rest = rem
        else:
            rem2 = rem - (frames_per_min + d)
            minutes_in_block = 1 + rem2 // frames_per_min
            rest = rem2 % frames_per_min + d
        minutes = block * 10 + minutes_in_block
        ff = rest % base
        ss = (rest // base) % 60
        mm = minutes % 60
        hh = minutes // 60
    else:
        n = n % (base * 86400)
        ff = n % base
        ss = (n // base) % 60
        mm = (n // (base * 60)) % 60
        hh = n // (base * 3600)
    return "%02d:%02d:%02d%s%02d" % (hh, mm, ss, sep, ff)


# --------------------------------------------------------------------------
# the pervasive carry rule
#
# Every conversion of a frame count from one rate to another is exact, then
# floored, and the fraction that the floor discarded is held in a named scope
# and added to the next conversion made inside that scope. A scope releases a
# whole frame as soon as the held fraction reaches one. Nothing is rounded to
# nearest anywhere, and no intermediate value is rounded at all.
# --------------------------------------------------------------------------
class Carry:
    def __init__(self, off=frozenset()) -> None:
        self.held: dict = {}
        self.count: dict = {}
        self.off = off

    def open(self, scope: str) -> None:
        self.held[scope] = Fraction(0)
        self.count.setdefault(scope, 0)

    def convert(self, exact, scope: str) -> int:
        """Take an exact rational frame count into whole frames under a
        named scope, carrying the discarded fraction forward."""
        self.count[scope] = self.count.get(scope, 0) + 1
        if "R10" in self.off:
            self.held.setdefault(scope, Fraction(0))
            return nint(F(exact))
        value = F(exact) + self.held.get(scope, Fraction(0))
        whole = ffloor(value)
        self.held[scope] = value - whole
        return whole

    def close(self, scope: str) -> Fraction:
        return self.held.get(scope, Fraction(0))


def rate_convert(n_src, src_num, src_den, dst_num=CH_NUM, dst_den=CH_DEN) -> Fraction:
    """The exact frame count that n_src source frames occupy at the
    destination rate. No rounding happens here."""
    return F(n_src) * F(dst_num) * F(src_den) / (F(dst_den) * F(src_num))


def seconds_to_frames(seconds, num=CH_NUM, den=CH_DEN) -> Fraction:
    return F(seconds) * F(num) / F(den)


# --------------------------------------------------------------------------
# readers
# --------------------------------------------------------------------------
def read_delim(path: Path, delim: str = ",") -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_lines_json(path: Path) -> list:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def read_flat_yaml(path: Path) -> dict:
    """A deliberately small reader for the flat policy files this corpus
    ships: scalars, and one level of list under a key."""
    out: dict = {}
    key = None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  - "):
            if key is not None:
                out.setdefault(key, [])
                if isinstance(out[key], list):
                    out[key].append(line[4:].strip().strip('"'))
            continue
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            key = k.strip()
            v = v.strip().strip('"')
            out[key] = v if v != "" else []
    return out


def read_xml_root(path: Path):
    return ET.fromstring(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# workbook reader (stdlib only: zipfile and xml, cached values)
# --------------------------------------------------------------------------
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col_to_idx(ref: str) -> int:
    letters = "".join(c for c in ref if c.isalpha())
    n = 0
    for c in letters:
        n = n * 26 + (ord(c) - 64)
    return n - 1


def read_xlsx_sheets(path: Path, off=frozenset()) -> dict:
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", _NS):
                runs = [t.text or "" for t in si.iter("{%s}t" % _NS["m"])]
                # R42: a rich text string is the concatenation of its runs.
                shared.append("".join(runs) if "R42" not in off else runs[0])
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {r.get("Id"): r.get("Target") for r in rels}
        sheets = {}
        for sh in wb.find("m:sheets", _NS):
            name = sh.get("name")
            target = rid_to_target[sh.get(_RID)]
            if not target.startswith("xl/"):
                target = "xl/" + target
            data = ET.fromstring(zf.read(target))
            rows = []
            for row in data.iter("{%s}row" % _NS["m"]):
                cells = []
                for c in row.findall("m:c", _NS):
                    idx = _col_to_idx(c.get("r", "A1"))
                    while len(cells) <= idx:
                        cells.append("")
                    v = c.find("m:v", _NS)
                    val = v.text if v is not None else ""
                    if c.get("t") == "s" and val != "":
                        val = shared[int(val)]
                    cells[idx] = val or ""
                rows.append(cells)
            sheets[name] = rows
        return sheets


# --------------------------------------------------------------------------
# pdf text extraction (the memo is written by write_pdf below, so its
# content streams are plain uncompressed text operators)
# --------------------------------------------------------------------------
def read_pdf_lines(path: Path) -> list:
    raw = Path(path).read_bytes().decode("latin-1")
    out = []
    for m in re.finditer(r"\((.*?)\) Tj", raw):
        out.append(m.group(1).replace(r"\(", "(").replace(r"\)", ")").replace("\\\\", "\\"))
    return out


def pdf_scalar(lines: list, key: str) -> str:
    for line in lines:
        if line.startswith(key):
            return line.split("=", 1)[1].strip()
    raise KeyError(key)


# --------------------------------------------------------------------------
# canonical serialization
# --------------------------------------------------------------------------
def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def compact_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def render_delim(header: list, rows: list, delim: str) -> str:
    out = [delim.join(header)]
    for row in rows:
        out.append(delim.join(str(row[c]) for c in header))
    return "\n".join(out) + "\n"


def render_jsonl(rows: list) -> str:
    if not rows:
        return "\n"
    return "\n".join(compact_json(r) for r in rows) + "\n"


def xml_escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def digest_over(blobs: dict, off=frozenset()) -> str:
    """The digest runs over the seven core artifacts in the order the
    manifest publishes them, which is the pipeline order and not the
    alphabetical one."""
    order = CORE_FILES if "R36" not in off else sorted(CORE_FILES)
    h = hashlib.sha256()
    for name in order:
        h.update(blobs[name])
    return h.hexdigest()


# Where the agent corpus sits in the agent container. This module never
# opens it: the string is quoted inside the documents the generator writes,
# and the verifier container has no such directory.
INPUT_ROOT = "/app/data"

# ==========================================================================
# corpus generator
#
# The verifier owns its corpus. Everything under the input root is minted
# here from a named seed, so the graded instances are drawn from the same
# generator as the shipped one and exist nowhere outside this file.
# ==========================================================================

import io
import os
import random
import shutil
import sqlite3
import subprocess
import tempfile
import threading


# --------------------------------------------------------------------------
# writers (stdlib only: real OOXML, real PDF 1.4, real sqlite)
# --------------------------------------------------------------------------
def _cell_ref(col: int, row: int) -> str:
    out = ""
    c = col
    while c > 0:
        c, r = divmod(c - 1, 26)
        out = chr(65 + r) + out
    return f"{out}{row}"


class RichText(tuple):
    """A cell value stored as a shared string split into formatted runs."""


def _split_runs(text: str) -> RichText:
    return RichText((text[:1], text[1:]))


def _sheet_xml(rows: list, shared: list, shared_idx: dict) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    out.append('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
    out.append("<sheetData>")
    for ri, row in enumerate(rows, start=1):
        out.append(f'<row r="{ri}">')
        for ci, val in enumerate(row, start=1):
            ref = _cell_ref(ci, ri)
            if val is None or val == "":
                continue
            if isinstance(val, RichText):
                key = ("rich",) + tuple(val)
                if key not in shared_idx:
                    shared_idx[key] = len(shared)
                    shared.append(val)
                out.append(f'<c r="{ref}" t="s"><v>{shared_idx[key]}</v></c>')
                continue
            sval = str(val)
            try:
                float(sval)
                is_num = True
            except ValueError:
                is_num = False
            if is_num:
                out.append(f'<c r="{ref}"><v>{sval}</v></c>')
            else:
                if sval not in shared_idx:
                    shared_idx[sval] = len(shared)
                    shared.append(sval)
                out.append(f'<c r="{ref}" t="s"><v>{shared_idx[sval]}</v></c>')
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(path: Path, sheets: dict) -> None:
    shared: list = []
    shared_idx: dict = {}
    sheet_xmls = {name: _sheet_xml(rows, shared, shared_idx) for name, rows in sheets.items()}

    ss = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ss.append(
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared)}" uniqueCount="{len(shared)}">'
    )
    for item in shared:
        if isinstance(item, RichText):
            first, rest = item
            ss.append(f"<si><r><rPr><b/></rPr><t>{first}</t></r>"
                      f"<r><t>{rest}</t></r></si>")
            continue
        esc = item.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ss.append(f"<si><t>{esc}</t></si>")
    ss.append("</sst>")

    ctypes = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ctypes.append('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">')
    ctypes.append('<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>')
    ctypes.append('<Default Extension="xml" ContentType="application/xml"/>')
    ctypes.append('<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>')
    ctypes.append('<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>')
    for i, _ in enumerate(sheets, start=1):
        ctypes.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ctypes.append("</Types>")

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb.append('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">')
    wb.append("<sheets>")
    for i, name in enumerate(sheets, start=1):
        wb.append(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>')
    wb.append("</sheets></workbook>")

    wb_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb_rels.append('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">')
    for i, _ in enumerate(sheets, start=1):
        wb_rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
    wb_rels.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>')
    wb_rels.append("</Relationships>")

    entries = [
        ("[Content_Types].xml", "".join(ctypes)),
        ("_rels/.rels", root_rels),
        ("xl/workbook.xml", "".join(wb)),
        ("xl/_rels/workbook.xml.rels", "".join(wb_rels)),
        ("xl/sharedStrings.xml", "".join(ss)),
    ]
    for i, (_, xml) in enumerate(sheet_xmls.items(), start=1):
        entries.append((f"xl/worksheets/sheet{i}.xml", xml))

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, payload)


def write_pdf(path: Path, lines: list) -> None:
    def esc(t: str) -> str:
        return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    pages = [lines[i:i + 52] for i in range(0, len(lines), 52)] or [[""]]
    objects: list = []
    n_pages = len(pages)
    font_obj = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>")
    for i, page_lines in enumerate(pages):
        content = "BT /F1 9 Tf 40 750 Td 11 TL\n"
        for ln in page_lines:
            content += f"({esc(ln)}) Tj T*\n"
        content += "ET"
        cbytes = content.encode("latin-1", "replace")
        page_obj = 3 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
            f"/Contents {page_obj + 1} 0 R >>"
        )
        objects.append((cbytes, f"<< /Length {len(cbytes)} >>"))
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        if isinstance(obj, tuple):
            cbytes, hdr = obj
            out.write(f"{i} 0 obj\n{hdr}\nstream\n".encode("latin-1"))
            out.write(cbytes)
            out.write(b"\nendstream\nendobj\n")
        else:
            out.write(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
    xref_pos = out.tell()
    n = len(objects) + 1
    out.write(f"xref\n0 {n}\n".encode("latin-1"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.write(
        f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    path.write_bytes(out.getvalue())


def write_sqlite(path: Path, tables: dict) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    for tname, (cols, rows) in tables.items():
        cur.execute("CREATE TABLE %s (%s)" % (tname, ", ".join(f"{c} TEXT" for c in cols)))
        ph = ", ".join("?" for _ in cols)
        cur.executemany(f"INSERT INTO {tname} VALUES ({ph})", rows)
    con.commit()
    con.close()


def _wtext(path: Path, text: str) -> None:
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _wdelim(path: Path, header: list, rows: list, delim: str) -> None:
    _wtext(path, render_delim(header, rows, delim))


def _wjsonl(path: Path, rows: list) -> None:
    _wtext(path, "\n".join(compact_json(r) for r in rows))


# --------------------------------------------------------------------------
# instance seeds
#
# The shipped instance is minted under SAMPLE_SEED. The three graded seeds
# are graded through the delivered program only, LEAD_DROP_SEED is the day
# whose opening slot is dropped, DEFAULT_SEED is the day the no-argument run
# is graded on, DIGEST_SEED is the day the manifest digest is graded on, and
# PLANT_SEED mints the day the remembered path detector plants; the agent
# never sees any of them. None of the graded seeds settles
# the control set at the shipped day's sheet position, so a reading that
# takes the workbook sheet by the shipped day's position is wrong on every
# one of them.
# --------------------------------------------------------------------------
SAMPLE_SEED = 20290714
EVAL_SEED = 20294065
CHALLENGE_SEED = 20300023
PROBE_SEED = 20298495
DEFAULT_SEED = 20300005
PLANT_SEED = 20299002
DIGEST_SEED = 20301100
# LEAD_DROP_SEED mints a day whose first scheduled slot carries an asset with
# no canonical attempt, so R17 drops the slot that opens the day.
LEAD_DROP_SEED = 20302207

_PROFILES = {
    SAMPLE_SEED: "standard",
    EVAL_SEED: "dense",
    CHALLENGE_SEED: "sparse",
    PROBE_SEED: "standard",
    DEFAULT_SEED: "standard",
    PLANT_SEED: "standard",
    DIGEST_SEED: "standard",
    LEAD_DROP_SEED: "standard",
}

_SIZES = {
    "standard": {"assets": 96, "slots": 28, "orders": 840, "advertisers": 18},
    "dense": {"assets": 120, "slots": 34, "orders": 1040, "advertisers": 22},
    "sparse": {"assets": 72, "slots": 22, "orders": 620, "advertisers": 14},
}

RATE_TABLE = {
    "RC_2398": (24000, 1001, 24, "no", "23.98"),
    "RC_2400": (24, 1, 24, "no", "24.00"),
    "RC_2500": (25, 1, 25, "no", "25.00"),
    "RC_2997": (30000, 1001, 30, "yes", "29.97"),
    "RC_3000": (30, 1, 30, "no", "30.00"),
    "RC_5000": (50, 1, 50, "no", "50.00"),
    "RC_5994": (60000, 1001, 60, "yes", "59.94"),
}




def _profile(seed: int) -> str:
    if seed in _PROFILES:
        return _PROFILES[seed]
    return ["standard", "dense", "sparse"][seed % 3]


def _rng(seed: int, salt: str) -> random.Random:
    raw = hashlib.blake2b(("%d:%s" % (seed, salt)).encode("utf-8"),
                          digest_size=16).digest()
    return random.Random(int.from_bytes(raw, "big"))


def _tx_date(seed: int) -> date:
    return date(2029, 1, 8) + timedelta(days=(seed % 617))


def _instance_ref(seed: int) -> str:
    return "inst-%s" % hashlib.blake2b(str(seed).encode("utf-8"),
                                       digest_size=5).hexdigest()


# --------------------------------------------------------------------------
# assets and ingest attempts
# --------------------------------------------------------------------------
def _build_assets(seed: int) -> dict:
    rng = _rng(seed, "assets")
    size = _SIZES[_profile(seed)]
    n = size["assets"]
    base_day = _tx_date(seed) - timedelta(days=90)
    assets = {}
    order = []
    counter = 0
    for i in range(n):
        title = "TC%04d" % (1200 + i)
        version = "ABCM"[i % 4] if i % 5 else rng.choice("ABCM")
        content_ref = "cr_%s_%s" % (title, version)
        order.append(content_ref)
        k = [1, 2, 2, 3, 3, 4][i % 6]
        no_pass = (i % 13 == 5)
        top_rejected = (i % 7 == 3) and k >= 2
        tie = (i % 11 == 4) and k >= 2
        revs = list(range(1, k + 1))
        if tie:
            revs[-1] = revs[-2]
        passed_flags = []
        for j in range(k):
            if no_pass:
                passed_flags.append(False)
            elif top_rejected and j == k - 1 and not tie:
                passed_flags.append(False)
            else:
                passed_flags.append(True)
        if not no_pass and not any(passed_flags):
            passed_flags[0] = True
        total_seconds = 900 + (i * 137) % 4200
        if i % 17 == 2:
            total_seconds = 120 + (i * 31) % 240
        attempts = []
        recv_offsets = list(range(k))
        rng.shuffle(recv_offsets)
        for j in range(k):
            counter += 1
            ingest_id = "ig_%06d" % (counter + 100000)
            rate_code = RATE_CODES[(i * 3 + j * 5) % len(RATE_CODES)]
            num, den, tc_base, df_allowed, nominal = RATE_TABLE[rate_code]
            if passed_flags[j]:
                qc_state = "QC_PASSED_WITH_NOTES" if (i + j) % 5 == 0 else "QC_PASSED"
            else:
                qc_state = ["QC_REJECTED", "QC_PENDING", "QC_WITHDRAWN"][(i + j) % 3]
            if df_allowed == "yes":
                tc_mode = "DF" if (i + j) % 3 != 0 else "NDF"
            else:
                tc_mode = "DF" if (i * 5 + j) % 17 == 1 else "NDF"
            fps_text = nominal
            if (i + j) % 23 == 7:
                fps_text = RATE_TABLE[RATE_CODES[(i + j) % len(RATE_CODES)]][4]
            length = int(F(total_seconds) * F(num) / F(den))
            if i % 29 == 9:
                som_frames = tc_base * 86400 - length // 2
            else:
                som_frames = rng.randrange(0, tc_base * 3600 * 20)
            df_here = (tc_mode == "DF" and df_allowed == "yes")
            if df_here:
                span = tc_base * 86400 - drop_per_minute(tc_base) * (1440 - 144)
            else:
                span = tc_base * 86400
            som_frames %= span
            if i % 31 == 13:
                length = 0
            eom_frames = (som_frames + length) % span
            attempts.append({
                "ingest_id": ingest_id,
                "content_ref": content_ref,
                "title_code": title,
                "version_tag": version,
                "revision_no": str(revs[j]),
                "qc_state": qc_state,
                "rate_code": rate_code,
                "tc_mode": tc_mode,
                "nominal_fps": fps_text,
                "som_tc": frames_to_tc(som_frames, tc_base, df_here),
                "eom_tc": frames_to_tc(eom_frames, tc_base, df_here),
                "house_no": "HN%05d" % (counter + 4000),
                "received_at": _received_text(
                    _received_instant(base_day, i, j, recv_offsets[j]),
                    (i * 3 + j * 5) % len(RECEIVED_OFFSETS)),
            })
        if i % 10 == 3 and k >= 2:
            # Two attempts arrive at the same instant, keyed at desks in
            # different zones, so the anchor is settled by the ingest_id
            # tie-break rather than by the text of the arrival time.
            first = recv_offsets.index(0)
            second = recv_offsets.index(1)
            zone = (first * 5 + i * 3) % len(RECEIVED_OFFSETS)
            other = (zone + 3) % len(RECEIVED_OFFSETS)
            if RECEIVED_OFFSETS[other][1] == RECEIVED_OFFSETS[zone][1]:
                other = (other + 1) % len(RECEIVED_OFFSETS)
            instant = _received_instant(base_day, i, first, 0)
            attempts[first]["received_at"] = _received_text(instant, zone)
            attempts[second]["received_at"] = _received_text(instant, other)
        rng.shuffle(attempts)
        assets[content_ref] = {
            "content_ref": content_ref,
            "attempts": attempts,
            "total_seconds": total_seconds,
            "no_pass": no_pass,
        }
    return {"assets": assets, "order": order}


# --------------------------------------------------------------------------
# segment parts
# --------------------------------------------------------------------------
# The zones the ingest desks key arrival times in: the suffix written and its
# offset from UTC in minutes.
RECEIVED_OFFSETS = [("Z", 0), ("+01:00", 60), ("-05:00", -300),
                    ("+05:30", 330), ("+00:00", 0), ("+09:00", 540),
                    ("-08:00", -480), ("+10:00", 600)]


def _received_instant(base_day: date, i: int, j: int, rank: int) -> datetime:
    """The UTC instant an attempt arrived. Attempts of one asset arrive seven
    hours apart in the order rank sets, close enough that the zone a desk
    keys the time in can reverse the textual order."""
    return (datetime(base_day.year, base_day.month, base_day.day, 6, 0)
            + timedelta(days=i % 5, hours=7 * rank, minutes=(i * 7) % 60 + j))


def _received_text(instant: datetime, zone: int) -> str:
    suffix, minutes = RECEIVED_OFFSETS[zone]
    local = instant + timedelta(minutes=minutes)
    return local.strftime("%Y-%m-%dT%H:%M:%S") + suffix


def _canonical_of(asset: dict) -> dict:
    best = None
    for row in asset["attempts"]:
        if row["qc_state"] not in QC_PASSED_SET:
            continue
        key = (int(row["revision_no"]), row["ingest_id"])
        if best is None:
            best = (key, row)
        elif key[0] > best[0][0] or (key[0] == best[0][0] and key[1] < best[0][1]):
            best = (key, row)
    return None if best is None else best[1]


def _build_parts(seed: int, estate: dict) -> list:
    rng = _rng(seed, "parts")
    rows = []
    for idx, content_ref in enumerate(estate["order"]):
        asset = estate["assets"][content_ref]
        canon = _canonical_of(asset)
        if canon is None:
            continue
        if idx % 37 == 11:
            continue
        num, den, tc_base, df_allowed, _ = RATE_TABLE[canon["rate_code"]]
        df_here = (canon["tc_mode"] == "DF" and df_allowed == "yes")
        span = (tc_base * 86400 - drop_per_minute(tc_base) * (1440 - 144)
                if df_here else tc_base * 86400)
        k = [2, 3, 3, 4, 5, 6][idx % 6]
        if idx % 19 == 6:
            k = 1
        kinds = []
        for j in range(k):
            if j == 0 and idx % 3 == 0 and k > 1:
                kinds.append("PT_BLACK")
            elif j == k - 1 and idx % 4 == 1 and k > 1:
                kinds.append("PT_BLACK")
            elif j == 1 and idx % 9 == 2 and k > 3:
                kinds.append("PT_BLACK")
            elif j % 3 == 1:
                kinds.append("PT_BUMPER" if idx % 2 else "PT_PROMO")
            else:
                kinds.append("PT_PROGRAMME")
        if "PT_PROGRAMME" not in kinds:
            kinds[0] = "PT_PROGRAMME"
        if idx % 18 == 10 and k == 5:
            # Head black, black between two other parts, and tail black in one
            # asset, so the three retention outcomes meet in a single slot.
            kinds = ["PT_BLACK", "PT_PROGRAMME", "PT_BLACK",
                     "PT_BUMPER" if idx % 2 else "PT_PROMO", "PT_BLACK"]
        weights = [rng.randrange(4, 40) for _ in kinds]
        for j, kind in enumerate(kinds):
            if kind == "PT_BLACK":
                weights[j] = 1
        total = sum(weights)
        cursor = rng.randrange(0, tc_base * 3600 * 12)
        for j, kind in enumerate(kinds):
            seconds = F(asset["total_seconds"]) * F(weights[j]) / F(total)
            length = max(1, int(seconds * F(num) / F(den)))
            if kind == "PT_BLACK":
                length = max(1, int(F(2 + j) * F(num) / F(den)))
            som = cursor % span
            eom = (som + length) % span
            rows.append({
                "content_ref": content_ref,
                "part_no": str(j + 1),
                "part_kind": kind,
                "part_som_tc": frames_to_tc(som, tc_base, df_here),
                "part_eom_tc": frames_to_tc(eom, tc_base, df_here),
                "source_note": "seg-%03d-%02d" % (idx, j + 1),
            })
            cursor = (cursor + length + 30) % span
    return rows


# --------------------------------------------------------------------------
# transmission schedule
# --------------------------------------------------------------------------
def _retained_rows(rows: list) -> list:
    """Head and tail black is trimmed, so it does not lay out the day."""
    n = len(rows)
    lo = 0
    while lo < n and rows[lo]["part_kind"] == "PT_BLACK":
        lo += 1
    hi = n - 1
    while hi >= lo and rows[hi]["part_kind"] == "PT_BLACK":
        hi -= 1
    return rows[lo:hi + 1]


def _part_seconds(rows: list, canon_by_ref: dict) -> dict:
    """Nominal retained seconds per content ref, used only to lay the
    schedule out."""
    by_ref: dict = {}
    for row in rows:
        by_ref.setdefault(row["content_ref"], []).append(row)
    out: dict = {}
    for content_ref, group in by_ref.items():
        canon = canon_by_ref.get(content_ref)
        if canon is None:
            continue
        num, den, tc_base, df_allowed, _ = RATE_TABLE[canon["rate_code"]]
        df_here = (canon["tc_mode"] == "DF" and df_allowed == "yes")
        span = (tc_base * 86400 - drop_per_minute(tc_base) * (1440 - 144)
                if df_here else tc_base * 86400)
        group = sorted(group, key=lambda r: int(r["part_no"]))
        total = 0
        for row in _retained_rows(group):
            a = tc_to_frames(row["part_som_tc"], tc_base, df_here)
            b = tc_to_frames(row["part_eom_tc"], tc_base, df_here)
            n = b - a
            if n < 0:
                n += span
            total += n * den / num
        out[content_ref] = total
    return out


def _build_schedule(seed: int, estate: dict, parts: list) -> dict:
    rng = _rng(seed, "schedule")
    size = _SIZES[_profile(seed)]
    canon_by_ref = {}
    for content_ref, asset in estate["assets"].items():
        canon = _canonical_of(asset)
        if canon is not None:
            canon_by_ref[content_ref] = canon
    seconds_by_ref = _part_seconds(parts, canon_by_ref)
    part_count: dict = {}
    for row in parts:
        part_count[row["content_ref"]] = part_count.get(row["content_ref"], 0) + 1

    included = [r for r in estate["order"] if r in canon_by_ref]
    excluded = [r for r in estate["order"] if r not in canon_by_ref]
    no_parts = [r for r in included if part_count.get(r, 0) == 0]
    picks = []
    step = max(1, len(included) // size["slots"])
    for i in range(size["slots"]):
        picks.append(included[(i * step) % len(included)])
    seen = set()
    unique = []
    for ref in picks:
        if ref in seen:
            for cand in included:
                if cand not in seen:
                    ref = cand
                    break
        seen.add(ref)
        unique.append(ref)
    picks = unique
    if no_parts and no_parts[0] not in picks:
        picks[7 % len(picks)] = no_parts[0]
    if excluded:
        picks[3] = excluded[0]
        if len(excluded) > 1 and len(picks) > 15:
            picks[15] = excluded[1]
        if seed == LEAD_DROP_SEED:
            # The slot that opens the day is dropped. It occupies no time, so
            # the floating slot after it moves up to the day start (R17); it
            # is not pinned at its own scheduled label behind a filler.
            picks[0] = excluded[-1]

    # A fixed junction is a real piece of work only when the running day
    # lands somewhere other than the published start. The offsets below make
    # every kind of correction happen on every instance.
    deltas = [0, -900, 420, -40, -1800, 520, -12, 640, -260, 380]
    rows = []
    cursor = 0
    fixed_seen = 0
    for i, content_ref in enumerate(picks):
        slot_id = "sl_%02d" % (i + 1)
        nominal = seconds_by_ref.get(content_ref, 900)
        junction = "JK_FIXED" if i % 3 == 2 else "JK_FLOAT"
        if i == 0:
            junction = "JK_FIXED"
        start_offset = cursor
        if junction == "JK_FIXED":
            start_offset = cursor + deltas[fixed_seen % len(deltas)]
            fixed_seen += 1
        start_offset = max(0, int(start_offset))
        hour = "H%02d" % (6 + min(23, start_offset // 3600))
        flex = str(part_count.get(content_ref, 1))
        rows.append({
            "slot_id": slot_id,
            "content_ref": content_ref,
            "sched_start_tc": frames_to_tc(
                (647352 + int(F(start_offset) * F(CH_BASE))) % DAY_FRAMES,
                CH_BASE, True),
            "junction_kind": junction,
            "flex_part_no": flex,
            "daypart_ref": DAYPART_BY_HOUR[hour],
            "service_note": "svc-%02d" % (i + 1),
        })
        cursor = start_offset + int(nominal) + rng.randrange(-12, 40)
    if len(rows) > 10:
        # Two floating slots share one scheduled label, so their running
        # order is settled by the slot_id tie-break. They are written to the
        # schedule file in the opposite order.
        rows[10]["sched_start_tc"] = rows[9]["sched_start_tc"]
        rows[10]["daypart_ref"] = rows[9]["daypart_ref"]
    if _profile(seed) == "dense":
        # The last slot of a dense day is pinned shortly before the next
        # day start, so its later breaks and spots run past the end of the
        # broadcast day and land in H29.
        late = rows[-1]
        late["junction_kind"] = "JK_FIXED"
        late["sched_start_tc"] = frames_to_tc(
            (647352 + DAY_FRAMES - LATE_SLOT_LEAD_FRAMES) % DAY_FRAMES, CH_BASE, True)
        late["daypart_ref"] = DAYPART_BY_HOUR["H29"]
    return {"rows": rows, "canon_by_ref": canon_by_ref}


# A quarter of an hour of channel frames: how far before the next day start
# the last slot of a dense day is pinned.
LATE_SLOT_LEAD_FRAMES = 26973


# The ways a channel frame count is commonly computed in floating point. The
# carry landings are chosen so that each of them floors one whole frame
# short somewhere in the day, while exact rational arithmetic lands on it.
_FLOAT_CONVERSIONS = [
    lambda n, num, den: n * (30000 / 1001) / (num / den),
    lambda n, num, den: n * 30000 * den / (1001 * num),
    lambda n, num, den: n / (num / den) * (30000 / 1001),
    lambda n, num, den: n * den / num * 30000 / 1001,
    lambda n, num, den: n * ((30000 * den) / (1001 * num)),
    lambda n, num, den: n / num * den * 30000 / 1001,
]


def _float_wholes(lengths: list, num: int, den: int, conv, cumulative: bool) -> list:
    out = []
    held = 0.0
    total = 0.0
    emitted = 0
    for n in lengths:
        x = conv(n, num, den)
        if cumulative:
            total += x
            w = int(total // 1) - emitted
            emitted += w
        else:
            t = x + held
            w = int(t // 1)
            held = t - w
        out.append(w)
    return out


def _exact_wholes(lengths: list, num: int, den: int) -> list:
    out = []
    held = F(0)
    for n in lengths:
        t = F(n * 30000 * den) / F(1001 * num) + held
        w = t.numerator // t.denominator
        held = t - w
        out.append(w)
    return out


def _plant_carry_landings(seed: int, estate: dict, parts: list) -> None:
    """For scheduled assets at an integer source rate with at least two
    retained parts, nudge the length of up to two retained parts so that the
    exact carry of the V4 scope lands on a whole frame at the end of them.
    Exact arithmetic floors there without loss; floating point lands a hair
    either side. Each nudge is chosen greedily to make a common float
    pipeline misfloor that has not misfloored yet in the day, and an asset no
    nudge helps is left as it was. Gaps between parts are kept."""
    picks = [row["content_ref"] for row in _build_schedule(seed, estate, parts)["rows"]]
    by_ref: dict = {}
    for row in parts:
        by_ref.setdefault(row["content_ref"], []).append(row)
    variants = [(k, c) for k in range(len(_FLOAT_CONVERSIONS)) for c in (False, True)]
    uncovered = set(variants)
    for content_ref in dict.fromkeys(picks):
        rows = by_ref.get(content_ref)
        canon = _canonical_of(estate["assets"][content_ref])
        if not rows or canon is None:
            continue
        num, den, tc_base, df_allowed, _ = RATE_TABLE[canon["rate_code"]]
        if den != 1:
            continue
        df_here = (canon["tc_mode"] == "DF" and df_allowed == "yes")
        span = (tc_base * 86400 - drop_per_minute(tc_base) * (1440 - 144)
                if df_here else tc_base * 86400)
        rows = sorted(rows, key=lambda r: int(r["part_no"]))
        retained = _retained_rows(rows)
        if len(retained) < 2:
            continue
        lengths = [(tc_to_frames(r["part_eom_tc"], tc_base, df_here)
                    - tc_to_frames(r["part_som_tc"], tc_base, df_here)) % span
                   for r in retained]
        original = list(lengths)
        # Up to two landings per asset: each nudges one retained part so the
        # running total of the scope ends that part on a whole frame.
        for _ in range(2):
            best = None
            for p in range(len(lengths)):
                base = (-sum(lengths[:p + 1])) % 1001
                for delta in sorted({base + 1001 * k for k in range(-5, 6)}, key=abs):
                    if lengths[p] + delta < max(100, lengths[p] // 2):
                        continue
                    trial = lengths[:p] + [lengths[p] + delta] + lengths[p + 1:]
                    exact = _exact_wholes(trial, num, den)
                    fails = {v for v in variants
                             if _float_wholes(trial, num, den,
                                              _FLOAT_CONVERSIONS[v[0]], v[1]) != exact}
                    score = len(fails & uncovered)
                    if best is None or score > best[0] or (
                            score == best[0] and abs(delta) < abs(best[1])):
                        best = (score, delta, fails, trial)
            if best is None or best[0] == 0:
                break
            uncovered -= best[2]
            lengths = best[3]
        if lengths == original:
            continue
        # Rewrite the labels: each part keeps its start relative to the end
        # of the part before it, and takes its new length.
        cursor = tc_to_frames(rows[0]["part_som_tc"], tc_base, df_here)
        new_len = {id(r): n for r, n in zip(retained, lengths)}
        old_eom: list = []
        for j, row in enumerate(rows):
            som = tc_to_frames(row["part_som_tc"], tc_base, df_here)
            eom = tc_to_frames(row["part_eom_tc"], tc_base, df_here)
            length = new_len.get(id(row), (eom - som) % span)
            gap = 0
            if j > 0:
                prev_eom_old = tc_to_frames(old_eom[j - 1], tc_base, df_here)
                gap = (som - prev_eom_old) % span
            start = cursor if j == 0 else (cursor + gap) % span
            old_eom.append(row["part_eom_tc"])
            row["part_som_tc"] = frames_to_tc(start, tc_base, df_here)
            row["part_eom_tc"] = frames_to_tc((start + length) % span, tc_base, df_here)
            cursor = (start + length) % span


def _straddles(out: dict) -> bool:
    """Whether an admitted spot of the day runs across a clock hour edge."""
    text = out["avail_plan.tsv"].decode("utf-8")
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        start, end = int(row["start_frame"]), int(row["end_frame"])
        if start // FRAMES_PER_HOUR != (end - 1) // FRAMES_PER_HOUR:
            return True
    return False


def _write_breaks(root: Path, breaks: list) -> None:
    _wdelim(root / "break_plan_register.csv",
            ["slot_id", "break_no", "nominal_offset_seconds", "avail_seconds",
             "break_note"], breaks, ",")


def _plant_hour_straddle(root: Path, breaks: list, avoid: set) -> None:
    """R33 splits a spot across the clock hours its frames fall in, so every
    day carries at least one admitted spot across an hour edge. When the
    written day has none, the last break of a slot that runs across an edge
    is moved to sit just before it, and the move is kept only if the day
    then admits a spot across that edge."""
    out = run_pipeline(root)
    if _straddles(out):
        return
    placement = csv.DictReader(io.StringIO(out["slot_placement.csv"].decode("utf-8")))
    by_slot: dict = {}
    for row in breaks:
        by_slot.setdefault(row["slot_id"], []).append(row)
    tries = 0
    for slot in placement:
        rows = sorted(by_slot.get(slot["slot_id"], []), key=lambda r: int(r["break_no"]))
        if slot["slot_id"] in avoid or not rows or slot["sequence_no"] == "0":
            continue
        start, end = int(slot["actual_start_frame"]), int(slot["end_frame"])
        edge = (start // FRAMES_PER_HOUR + 1) * FRAMES_PER_HOUR
        if edge - start < 1200 or edge + 600 > end:
            continue
        last = rows[-1]
        seconds = (edge - start - 200) * CH_DEN // CH_NUM
        floor_at = int(rows[-2]["nominal_offset_seconds"]) + 30 if len(rows) > 1 else 0
        if seconds <= floor_at:
            continue
        kept = last["nominal_offset_seconds"]
        last["nominal_offset_seconds"] = str(seconds)
        _write_breaks(root, breaks)
        if _straddles(run_pipeline(root)):
            return
        last["nominal_offset_seconds"] = kept
        _write_breaks(root, breaks)
        tries += 1
        if tries >= 12:
            return


def _flip_separator(label: str) -> str:
    """The same timecode keyed with the other separator before the frames."""
    return label[:8] + (":" if label[8] == ";" else ";") + label[9:]


def _plant_separators(estate: dict, parts: list, schedule: dict) -> None:
    """Labels keyed at the wrong desk: drop frame material written with a
    colon before the frames and non drop material written with a semicolon.
    The separator is never evidence of drop frame (R40), so the frame counts
    these labels stand for are unchanged."""
    for i, content_ref in enumerate(estate["order"]):
        if i % 5 == 1:
            for row in estate["assets"][content_ref]["attempts"]:
                row["som_tc"] = _flip_separator(row["som_tc"])
                row["eom_tc"] = _flip_separator(row["eom_tc"])
    index = {ref: i for i, ref in enumerate(estate["order"])}
    for row in parts:
        idx = index[row["content_ref"]]
        if idx % 6 == 1 or (idx % 7 == 4 and int(row["part_no"]) % 2 == 0):
            row["part_som_tc"] = _flip_separator(row["part_som_tc"])
            row["part_eom_tc"] = _flip_separator(row["part_eom_tc"])
    # One floating and one fixed slot carry a channel label with a colon.
    for i in (4, 5):
        if i < len(schedule["rows"]) - 1:
            row = schedule["rows"][i]
            row["sched_start_tc"] = _flip_separator(row["sched_start_tc"])


def _schedule_file_rows(rows: list) -> list:
    """The schedule in the order the files carry it, with the two slots that
    share a label swapped, so that file order never stands in for the
    slot_id tie-break."""
    written = list(rows)
    if len(written) > 10:
        written[9], written[10] = written[10], written[9]
    return written


def _build_gop(seed: int, schedule: dict) -> list:
    rng = _rng(seed, "gop")
    rows = []
    for i, slot in enumerate(schedule["rows"]):
        content_ref = slot["content_ref"]
        if i % 23 == 7:
            continue
        limit = 86000 if i % 13 != 5 else 24000
        frame = 0
        while frame < limit:
            rows.append({
                "content_ref": content_ref,
                "idr_frame": str(frame),
                "picture_kind": "IDR",
                "index_note": "gx-%02d" % i,
            })
            frame += rng.choice([24, 30, 36, 45, 60, 75, 90, 120])
    return rows


def _build_breaks(seed: int, schedule: dict, gop: list) -> list:
    rng = _rng(seed, "breaks")
    idr_by_ref: dict = {}
    for row in gop:
        idr_by_ref.setdefault(row["content_ref"], []).append(int(row["idr_frame"]))
    rows = []
    for i, slot in enumerate(schedule["rows"]):
        k = [0, 2, 3, 4, 3, 2, 4, 1][i % 8]
        offset = 240
        for j in range(k):
            offset += rng.randrange(210, 560)
            avail = [90, 120, 180, 240, 300][(i + j) % 5]
            if i % 17 == 4 and j == 0:
                avail = 0
            if (i + j) % 9 == 3:
                pool = idr_by_ref.get(slot["content_ref"], [])
                if pool:
                    target = [f for f in pool if f >= offset * 30]
                    if target:
                        offset = int(F(target[0]) * F(CH_DEN) / F(CH_NUM))
            rows.append({
                "slot_id": slot["slot_id"],
                "break_no": str(j + 1),
                "nominal_offset_seconds": str(offset),
                "avail_seconds": str(avail),
                "break_note": "bk-%02d-%02d" % (i + 1, j + 1),
            })
    return rows


def _plant_index_hits(gop: list, breaks: list, schedule: dict) -> set:
    """A break whose nominal position already sits on an index frame is a
    real case and a rare one, so a few are planted. Both frames the carry
    can land on are planted, because the scope decides which of the two the
    break aims at."""
    by_slot: dict = {}
    for row in breaks:
        by_slot.setdefault(row["slot_id"], []).append(row)
    content = {s["slot_id"]: s["content_ref"] for s in schedule["rows"]}
    indexed = set(r["content_ref"] for r in gop)
    have = set((r["content_ref"], int(r["idr_frame"])) for r in gop)
    planted = 0
    touched = set()
    for slot_id in sorted(by_slot):
        rows = sorted(by_slot[slot_id], key=lambda r: int(r["break_no"]))
        ref = content[slot_id]
        if len(rows) < 2 or ref not in indexed:
            continue
        seconds = int(rows[0]["nominal_offset_seconds"])
        base = int(F(seconds) * F(CH_NUM) / F(CH_DEN))
        for frame in (base, base + 1):
            if (ref, frame) not in have:
                gop.append({"content_ref": ref, "idr_frame": str(frame),
                            "picture_kind": "IDR", "index_note": "gx-hit"})
                have.add((ref, frame))
        planted += 1
        touched.add(slot_id)
        if planted >= 3:
            break
    gop.sort(key=lambda r: (r["content_ref"], int(r["idr_frame"])))
    return touched


def _plant_floored_target(gop: list, breaks: list, schedule: dict) -> set:
    """One placed two-break slot loses its index frames from just before its
    first break to past where its second break would sit. The first break
    then snaps forward so far that the second break's adjusted target falls
    below zero and is floored."""
    by_slot: dict = {}
    for row in breaks:
        by_slot.setdefault(row["slot_id"], []).append(row)
    frames: dict = {}
    for row in gop:
        frames.setdefault(row["content_ref"], []).append(int(row["idr_frame"]))
    for slot in reversed(schedule["rows"][:-1]):
        ref = slot["content_ref"]
        rows = sorted(by_slot.get(slot["slot_id"], []), key=lambda r: int(r["break_no"]))
        if ref not in schedule["canon_by_ref"] or len(rows) != 2 or not frames.get(ref):
            continue
        first = ffloor(seconds_to_frames(int(rows[0]["nominal_offset_seconds"])))
        second = ffloor(seconds_to_frames(int(rows[1]["nominal_offset_seconds"])))
        lo, hi = first - 400, first + second + 400
        if max(frames[ref]) <= hi:
            continue
        gop[:] = [r for r in gop
                  if not (r["content_ref"] == ref and lo <= int(r["idr_frame"]) <= hi)]
        return {slot["slot_id"]}
    return set()


# --------------------------------------------------------------------------
# filler library
# --------------------------------------------------------------------------
def _build_fillers(seed: int) -> list:
    """The library every instance carries. The breakfast junction underruns by
    more frames than any breakfast row covers, and more than the DP_ANY row
    covers, so that gap is the case the V8 specification calls out: no row
    qualifies, and the fill falls back to the house filler the channel
    configuration names, published with a selection index of zero. The other
    three junctions are covered by their own daypart rows, so the ordered
    predicate walk is exercised on every instance as well."""
    rows = []
    specs = [
        ("fl_promo_short", 1, 400, "DP_BREAKFAST", "FS_AVAILABLE"),
        ("fl_promo_mid", 1, 35000, "DP_BREAKFAST", "FS_AVAILABLE"),
        ("fl_promo_hold", 200, 1200, "DP_BREAKFAST", "FS_EMBARGOED"),
        ("fl_trail_day", 1, 1500, "DP_DAYTIME", "FS_AVAILABLE"),
        ("fl_trail_day_alt", 1, 40000, "DP_DAYTIME", "FS_AVAILABLE"),
        ("fl_trail_expired", 1, 9000, "DP_DAYTIME", "FS_EXPIRED"),
        ("fl_peak_ident", 1, 1200, "DP_PEAK", "FS_AVAILABLE"),
        ("fl_peak_long", 1, 40000, "DP_PEAK", "FS_AVAILABLE"),
        ("fl_late_music", 1, 40000, "DP_LATE", "FS_AVAILABLE"),
        ("fl_late_hold", 1, 9000, "DP_LATE", "FS_EMBARGOED"),
        ("fl_overnight_loop", 1, 40000, "DP_OVERNIGHT", "FS_AVAILABLE"),
        ("fl_overnight_bars", 1, 9000, "DP_OVERNIGHT", "FS_EXPIRED"),
        ("fl_house_black", 1, 35000, "DP_ANY", "FS_AVAILABLE"),
    ]
    for i, (ref, lo, hi, daypart, state) in enumerate(specs):
        rows.append({
            "filler_ref": ref,
            "predicate_order": str(i + 1),
            "min_frames": str(lo),
            "max_frames": str(hi),
            "daypart_ref": daypart,
            "stock_state": state,
            "stock_note": "fill-%02d" % (i + 1),
        })
    return rows


# --------------------------------------------------------------------------
# advertisers, rate cards, orders, clearance
# --------------------------------------------------------------------------
def _build_advertisers(seed: int) -> list:
    rng = _rng(seed, "advertisers")
    size = _SIZES[_profile(seed)]
    rows = []
    for i in range(size["advertisers"]):
        rows.append({
            "advertiser_ref": "ad_%03d" % (i + 1),
            "advertiser_name": "Advertiser %02d" % (i + 1),
            "settlement_currency": CURRENCIES[i % len(CURRENCIES)],
            "agency_ref": "ag_%02d" % (i % 6 + 1),
            "account_note": "acct-%03d" % (i + 1),
        })
    rng.shuffle(rows)
    rows.sort(key=lambda r: r["advertiser_ref"])
    return rows


def _build_rate_cards(seed: int) -> list:
    rng = _rng(seed, "ratecards")
    tx = _tx_date(seed)
    rows = []
    n_refs = 24
    for i in range(n_refs):
        ref = "rc_%03d" % (i + 1)
        if i % 11 == 4:
            offsets = [7, 21, 63]
        elif i % 7 == 2:
            offsets = [0, -45, -120]
        else:
            offsets = [-3 - (i % 9), -60 - i, -240 - i * 2]
        for j, off in enumerate(offsets):
            card = {
                "rate_card_ref": ref,
                "effective_from": (tx + timedelta(days=off)).isoformat(),
                "minor_per_grain": str(150 + rng.randrange(0, 900) + i * 13),
                "card_revision": str(3 - j),
                "card_note": "card-%03d-%d" % (i + 1, j + 1),
            }
            if j == 0 and i in (0, 5):
                # Two revisions of the live card share one effective date.
                # Revision 10 prices the day; compared as text, 9 would. One
                # reference carries revision 10 first in the file and the
                # other carries it second, so file order settles neither.
                card["card_revision"] = "9"
                reissue = dict(card, card_revision="10",
                               minor_per_grain=str(_int(card["minor_per_grain"])
                                                   + 37 + rng.randrange(0, 60)),
                               card_note="card-%03d-%dr" % (i + 1, j + 1))
                rows.extend([reissue, card] if i == 0 else [card, reissue])
                continue
            rows.append(card)
        if i in (2, 3, 7):
            # A card that takes effect on the calendar day after the
            # transmission date. Spots aired after midnight still belong to
            # the broadcast day and are never priced by it.
            rows.append({
                "rate_card_ref": ref,
                "effective_from": (tx + timedelta(days=1)).isoformat(),
                "minor_per_grain": str(150 + rng.randrange(0, 900) + i * 13),
                "card_revision": "4",
                "card_note": "card-%03d-n" % (i + 1),
            })
    rows.sort(key=lambda r: (r["rate_card_ref"], r["effective_from"]))
    return rows


def _build_orders(seed: int, breaks: list, schedule: dict,
                  advertisers: list, markets: list) -> tuple:
    """The order book, plus the clearance plan the journal is built from.

    Some orders are planted deliberately so that every admission predicate
    has something to settle on every instance: clusters of one separation
    class inside one wide break, and a handful of held and mismatched
    orders.
    """
    rng = _rng(seed, "orders")
    size = _SIZES[_profile(seed)]
    daypart_by_slot = {s["slot_id"]: s["daypart_ref"] for s in schedule["rows"]}
    catalogue = []
    for row in breaks:
        catalogue.append({
            "break_ref": "bk_%s_%02d" % (row["slot_id"], int(row["break_no"])),
            "daypart_ref": daypart_by_slot[row["slot_id"]],
            "avail_seconds": int(row["avail_seconds"]),
        })
    wide = [b for b in catalogue if b["avail_seconds"] >= 120] or catalogue
    market_refs = [m["market_ref"] for m in markets]
    adv_refs = [a["advertiser_ref"] for a in advertisers]

    rows = []
    plan = {}
    state = {"n": 0}

    def add(**fields):
        state["n"] += 1
        counter = state["n"]
        ref = "or_%05d" % counter
        row = {"order_ref": ref, "spot_ref": "sp_%05d" % counter,
               "traffic_note": "traf-%05d" % counter,
               "clearance_ref": "cl_%05d" % counter}
        row.update(fields)
        rows.append(row)
        return ref

    for c in range(10):
        if not wide:
            break
        brk = wide[(c * 7) % len(wide)]
        market = market_refs[c % len(market_refs)]
        cls = SEPARATION_CLASSES[c % len(SEPARATION_CLASSES)]
        for j in range(5):
            ref = add(advertiser_ref=adv_refs[(c + j) % len(adv_refs)],
                      nominal_seconds=10,
                      market_ref=market,
                      break_ref=brk["break_ref"],
                      daypart_ref=brk["daypart_ref"],
                      priority_band=[4, 3, 2, 1, 4][j],
                      separation_class=cls,
                      rate_card_ref="rc_%03d" % ((c % 20) + 1))
            plan[ref] = "cleared"

    while state["n"] < size["orders"]:
        i = state["n"]
        adv = adv_refs[i % len(adv_refs)]
        market = market_refs[i % len(market_refs)]
        brk = catalogue[(i * 5 + 3) % len(catalogue)] if catalogue else None
        break_ref = brk["break_ref"] if brk else "bk_sl_01_01"
        daypart = brk["daypart_ref"] if brk else "DP_PEAK"
        if i % 13 == 6:
            daypart = DAYPARTS[(i + 2) % len(DAYPARTS)]
        if i % 29 == 17:
            break_ref = "bk_sl_99_09"
        seconds = [10, 15, 20, 30, 30, 45, 60][i % 7]
        if i % 41 == 22:
            seconds = 0
        ref = add(advertiser_ref=adv,
                  nominal_seconds=seconds,
                  market_ref=market,
                  break_ref=break_ref,
                  daypart_ref=daypart,
                  priority_band=[1, 2, 2, 3, 3, 4][i % 6],
                  separation_class=SEPARATION_CLASSES[
                      (i // 3) % len(SEPARATION_CLASSES)],
                  rate_card_ref="rc_%03d" % ((i % 24) + 1))
        if i % 17 == 8:
            plan[ref] = "held"
        elif i % 9 == 4:
            plan[ref] = "conditional"
        else:
            plan[ref] = "cleared"

    # Every order of the last advertiser is held, so that advertiser carries
    # obligations against a day gross of zero and a make good cap of zero.
    for row in rows:
        if row["advertiser_ref"] == adv_refs[-1]:
            plan[row["order_ref"]] = "held"
    # One order names a rate card reference the book carries no row for.
    rows[len(rows) // 2]["rate_card_ref"] = "rc_%03d" % 99

    rng.shuffle(rows)
    rows.sort(key=lambda r: r["order_ref"])
    fields = ["order_ref", "advertiser_ref", "spot_ref", "nominal_seconds",
              "market_ref", "break_ref", "daypart_ref", "priority_band",
              "separation_class", "rate_card_ref", "clearance_ref",
              "traffic_note"]
    return [{k: row[k] for k in fields} for row in rows], plan


def _build_clearance(seed: int, orders: list, plan: dict) -> list:
    """Several rows per clearance reference. The row that settles the state
    is the one with the greatest sequence, and the logged timestamps are
    backfilled so that their order disagrees with it."""
    rng = _rng(seed, "clearance")
    tx = _tx_date(seed)
    final = {"held": "CL_HELD", "conditional": "CL_CONDITIONAL",
             "cleared": "CL_CLEARED"}
    rows = []
    for i, order in enumerate(orders):
        k = [1, 1, 2, 3][i % 4]
        long_journal = (i % 19 == 7)
        if long_journal:
            # A journal that runs past nine entries. Sequence 9 carries the
            # opposite of the settled state, so a sequence compared as text
            # settles the wrong one (R38).
            k = 10 + (i % 2)
        states = []
        for j in range(k):
            if j == k - 1:
                states.append(final[plan[order["order_ref"]]])
            elif long_journal and j == 8:
                states.append("CL_CLEARED" if plan[order["order_ref"]] == "held"
                              else "CL_HELD")
            else:
                states.append(
                    ["CL_HELD", "CL_CONDITIONAL", "CL_CLEARED"][(i + j) % 3])
        seqs = list(range(1, k + 1))
        logged = [(tx - timedelta(days=rng.randrange(1, 40))).isoformat()
                  for _ in range(k)]
        idx = list(range(k))
        rng.shuffle(idx)
        for j in idx:
            rows.append({
                "clearance_ref": order["clearance_ref"],
                "journal_seq": str(seqs[j]),
                "clearance_state": states[j],
                "logged_at": logged[j] + "T09:%02d:00" % ((i + j) % 60),
                "clearance_note": "clr-%05d-%d" % (i + 1, j + 1),
            })
    rows.sort(key=lambda r: (r["clearance_ref"], r["clearance_note"]))
    return rows



# --------------------------------------------------------------------------
# markets, blackouts, substitutes
# --------------------------------------------------------------------------
def _build_markets(seed: int) -> list:
    rows = []
    for i, ref in enumerate(MARKETS):
        rows.append({
            "market_ref": ref,
            "market_name": ref.replace("mk_", "").title() + " Region",
            "regulator_ref": "reg_%02d" % (i + 1),
            "feed_note": "feed-%d" % (i + 1),
        })
    return rows


def _build_substitutes(seed: int) -> list:
    rng = _rng(seed, "substitutes")
    rows = []
    for i in range(8):
        ref = "sub_%02d" % (i + 1)
        k = [1, 2, 3, 2][i % 4]
        offset = 300
        for j in range(k):
            offset += rng.randrange(240, 600)
            rows.append({
                "substitute_ref": ref,
                "break_no": str(j + 1),
                "nominal_offset_seconds": str(offset),
                "avail_seconds": str([60, 90, 120, 150][(i + j) % 4]),
                "substitute_note": "sub-%02d-%02d" % (i + 1, j + 1),
            })
    return rows


def _build_blackouts(seed: int, schedule: dict) -> list:
    rng = _rng(seed, "blackouts")
    tx = _tx_date(seed)
    slots = schedule["rows"]
    rows = []
    picks = [1, 4, 6, 9, 12, 14, 17, 19]
    rule_no = 0
    for n, si in enumerate(picks):
        if si >= len(slots):
            continue
        slot = slots[si]
        market = MARKETS[n % len(MARKETS)]
        if n == 0:
            lo, hi = tx, tx + timedelta(days=9)
        elif n == 1:
            lo, hi = tx - timedelta(days=6), tx
        else:
            lo = tx - timedelta(days=rng.randrange(0, 20))
            hi = tx + timedelta(days=rng.randrange(0, 20))
        rule_no += 1
        rows.append({
            "rule_id": "bo_%03d" % rule_no,
            "precedence": str(10 + n),
            "market_ref": market,
            "content_ref": slot["content_ref"],
            "window_from": lo.isoformat(),
            "window_to": hi.isoformat(),
            "substitute_ref": "sub_%02d" % ((n % 8) + 1),
            "override": "no",
        })
        if n in (2, 5):
            rule_no += 1
            rows.append({
                "rule_id": "bo_%03d" % rule_no,
                "precedence": str(40 + n),
                "market_ref": market,
                "content_ref": slot["content_ref"],
                "window_from": (lo - timedelta(days=2)).isoformat(),
                "window_to": (hi + timedelta(days=2)).isoformat(),
                "substitute_ref": "sub_%02d" % (((n + 3) % 8) + 1),
                "override": "yes",
            })
        if n == 4:
            rule_no += 1
            rows.append({
                "rule_id": "bo_%03d" % rule_no,
                "precedence": str(90 + n),
                "market_ref": market,
                "content_ref": slot["content_ref"],
                "window_from": (tx + timedelta(days=30)).isoformat(),
                "window_to": (tx + timedelta(days=60)).isoformat(),
                "substitute_ref": "sub_02",
                "override": "yes",
            })
    if rows:
        # A second rule at the first rule's precedence, written ahead of it,
        # so the base rule is settled by the rule_id tie-break and file order
        # would pick the wrong one.
        rows.insert(0, dict(rows[0], rule_id="bo_901", substitute_ref="sub_05"))
    return rows


# --------------------------------------------------------------------------
# the workbook, the memo, and the redundant stores
# --------------------------------------------------------------------------
SHEET_NAMES = ["TERMS_R07", "TERMS_R09", "TERMS_R11"]


def _control_sets(seed: int) -> tuple:
    """Three control sets sit in the workbook and one of them is settled.
    Which sheet holds the settled set is drawn per instance, so neither the
    sheet position nor the revision in the sheet name settles anything."""
    rng = _rng(seed, "control-set-order")
    year = _tx_date(seed).year
    settled = rng.randrange(3)
    codes = ["CS-%d-%02d-%s" % (year, rng.randrange(1, 13), letter)
             for letter in "ABC"]
    return codes, settled


def _workbook_scalars(seed: int) -> dict:
    rng = _rng(seed, "scalars")
    return {
        "snap_tolerance_frames": rng.choice([24, 36, 48]),
        "makegood_cap_num": rng.choice([1, 2, 3]),
        "makegood_cap_den": rng.choice([4, 5, 8]),
    }


def _memo_scalars(seed: int) -> dict:
    rng = _rng(seed, "memo")
    return {
        "separation_minimum_positions": rng.choice([2, 3]),
        "billing_grain_seconds": rng.choice([5, 10]),
        "regulatory_minutes_per_clock_hour": rng.choice([2, 3, 4]),
    }


def _sheet_rows(control_set: str, scalars: dict, advertisers: list,
                variant: int, rng: random.Random) -> list:
    """Variant zero carries the settled terms. The other two carry terms of
    their own, so reaching for the wrong sheet is wrong whichever wrong
    sheet it is."""
    shift = [0, 6, 12][variant]
    rows = [["control_set", control_set]]
    rows.append(["sheet_revision", control_set[-1]])
    rows.append([])
    rows.append(["scalar_key", "scalar_value", "unit_note"])
    for key in ("snap_tolerance_frames", "makegood_cap_num", "makegood_cap_den"):
        value = scalars[key] + (shift if key == "snap_tolerance_frames"
                                else shift // 6)
        # The snap tolerance was keyed with its first digit in bold, so the
        # cell is a rich text string of two runs (R42).
        rows.append([key, _split_runs(str(value)) if key == "snap_tolerance_frames"
                     else str(value),
                     "channel frames" if "frames" in key else "ratio term"])
    rows.append([])
    rows.append(["commission_key", "advertiser_ref", "daypart_ref",
                 "commission_num", "commission_den", "term_note"])
    for k, adv in enumerate(advertisers):
        num = rng.randrange(3, 23) + shift
        den = 200
        rows.append(["COMMISSION", adv["advertiser_ref"], "DP_ANY",
                     _split_runs(str(num)) if k % 3 == 1 and num >= 10 else str(num),
                     str(den), "agency commission on gross"])
    for adv in advertisers:
        for daypart in DAYPARTS:
            rows.append(["FEE", adv["advertiser_ref"], daypart,
                         str(rng.randrange(40, 400)), "1",
                         "traffic handling fee in minor units"])
    for adv in advertisers:
        for market in MARKETS:
            rows.append(["CLEARANCE", adv["advertiser_ref"], market,
                         str(rng.randrange(1, 9)), "10",
                         "clearance surcharge share"])
    for market in MARKETS:
        for daypart in DAYPARTS:
            rows.append(["FEED", market, daypart,
                         str(rng.randrange(1, 40)), "100", "feed loading share"])
    return rows


def _memo_variations(seed: int, scalars: dict) -> tuple:
    """Three market hours whose permitted minutes differ from the Section 1
    figure, and two market hours Section 2 does not list at all. The varied
    hours sit in the daytime, where the day carries advertising."""
    rng = _rng(seed, "memo-variations")
    standing = scalars["regulatory_minutes_per_clock_hour"]
    pairs = [(m, h) for m in MARKETS for h in HOUR_LABELS[1:17]]
    picked = rng.sample(pairs, 5)
    varied = {}
    for k, pair in enumerate(picked[:3]):
        varied[pair] = max(1, standing + (1 if k != 1 else -1))
        if varied[pair] == standing:
            varied[pair] = standing + 1
    return varied, set(picked[3:])


def _memo_lines(seed: int, scalars: dict, tx: date) -> list:
    rng = _rng(seed, "memoline")
    lines = []
    lines.append("REGIONAL PLAYOUT COMPLIANCE MEMORANDUM")
    lines.append("Issued for transmission date %s" % tx.isoformat())
    lines.append("Document class: normative. This memorandum is the only")
    lines.append("place the three settlement constants below are published.")
    lines.append("")
    lines.append("SECTION 1 - SETTLEMENT CONSTANTS")
    for key in ("separation_minimum_positions", "billing_grain_seconds",
                "regulatory_minutes_per_clock_hour"):
        lines.append("%s = %d" % (key, scalars[key]))
    lines.append("")
    lines.append("The separation minimum is counted in admitted positions")
    lines.append("inside one break. Two admitted spots that carry the same")
    lines.append("separation class must sit at least that many positions")
    lines.append("apart, so a minimum of two bars adjacent positions.")
    lines.append("")
    lines.append("The billing grain is the whole number of seconds that a")
    lines.append("delivered spot is billed in. A delivered spot is billed")
    lines.append("for the smallest whole number of grains that covers its")
    lines.append("delivered frames, and a delivery that lands exactly on a")
    lines.append("grain boundary bills that many grains and no more.")
    lines.append("")
    lines.append("The regulatory minutage is the permitted advertising")
    lines.append("minutes inside one clock hour of the broadcast day. The")
    lines.append("cap in channel frames is the whole number of frames that")
    lines.append("those minutes occupy at the channel rate, taken toward")
    lines.append("zero. An hour whose advertising frames exceed the cap is")
    lines.append("a breach; an hour that lands exactly on the cap is not.")
    lines.append("")
    lines.append("SECTION 2 - PERMITTED MINUTAGE BY MARKET AND CLOCK HOUR")
    lines.append("Where a market and clock hour is listed below, its permitted")
    lines.append("minutes govern that hour and replace the Section 1 figure.")
    lines.append("A market and clock hour not listed keeps the Section 1")
    lines.append("figure.")
    lines.append("market_ref | hour_label | permitted_minutes | notice_band")
    varied, omitted = _memo_variations(seed, scalars)
    for market in MARKETS:
        for hour in HOUR_LABELS:
            band = rng.randrange(1, 5)
            if (market, hour) in omitted:
                continue
            minutes = varied.get((market, hour),
                                 scalars["regulatory_minutes_per_clock_hour"])
            lines.append("%s | %s | %d | band_%d" % (market, hour, minutes, band))
    lines.append("")
    lines.append("SECTION 3 - DAYPART NOTICE TERMS")
    lines.append("market_ref | daypart_ref | notice_days | escalation_ref")
    for market in MARKETS:
        for daypart in DAYPARTS:
            lines.append("%s | %s | %d | esc_%02d" % (
                market, daypart, rng.randrange(3, 30), rng.randrange(1, 40)))
    lines.append("")
    lines.append("SECTION 4 - PENALTY BANDS")
    lines.append("band_ref | frames_over_cap_from | frames_over_cap_to | penalty_units")
    lo = 1
    for i in range(40):
        hi = lo + 180 + i * 37
        lines.append("band_%02d | %d | %d | %d" % (i + 1, lo, hi, (i + 1) * 25))
        lo = hi + 1
    lines.append("")
    lines.append("SECTION 4B - CLOCK HOUR BANDING OF THE BROADCAST DAY")
    lines.append("hour_label | daypart_ref | notice_band | filing_window_days")
    for hour in HOUR_LABELS:
        lines.append("%s | %s | band_%02d | %d" % (
            hour, DAYPART_BY_HOUR[hour], rng.randrange(1, 41),
            rng.randrange(5, 45)))
    lines.append("")
    lines.append("SECTION 5 - TERMS USED IN THIS MEMORANDUM")
    terms = [
        "admitted position: the one based index of a spot inside a break",
        "advertising frames: channel frames occupied by admitted spots",
        "avail: the commercial capacity published against one break",
        "break: a conditioned splice point inside a transmitted slot",
        "broadcast day: the day that opens at the published day start",
        "channel frame: one frame at the channel transmission rate",
        "clock hour: one whole hour measured from the broadcast day start",
        "conform: the frame exact placement of material into the day",
        "delivered frames: the frames an admitted spot actually occupies",
        "drop frame: the timecode labelling that skips frame numbers",
        "grain: the whole second unit a delivered spot is billed in",
        "junction: a point in the day where a slot start is published",
        "make good: an obligation raised against an undelivered spot",
        "market: one regional feed of the channel",
        "minor unit: the smallest indivisible unit of a currency",
        "minutage: advertising time measured inside one clock hour",
        "overrun: placement later than a fixed junction requires",
        "separation class: the competitive grouping of an advertiser",
        "slot: one scheduled transmission of one canonical asset",
        "snap: the movement of a break onto an index frame",
        "substitute: material carried in place of a blacked out slot",
        "underrun: placement earlier than a fixed junction requires",
    ]
    for term in terms:
        lines.append(term)
    lines.append("")
    lines.append("SECTION 6 - REVISION HISTORY")
    for i in range(36):
        lines.append("revision %02d issued %s by compliance desk %02d" % (
            i + 1, (tx - timedelta(days=30 * (36 - i))).isoformat(),
            rng.randrange(1, 9)))
    lines.append("")
    lines.append("END OF MEMORANDUM")
    return lines


# --------------------------------------------------------------------------
# the whole corpus
# --------------------------------------------------------------------------
def generate(seed: int, out_dir) -> dict:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    tx = _tx_date(seed)
    profile = _profile(seed)

    estate = _build_assets(seed)
    parts = _build_parts(seed, estate)
    _plant_carry_landings(seed, estate, parts)
    schedule = _build_schedule(seed, estate, parts)
    gop = _build_gop(seed, schedule)
    breaks = _build_breaks(seed, schedule, gop)
    planted_slots = (_plant_index_hits(gop, breaks, schedule)
                     | _plant_floored_target(gop, breaks, schedule))
    fillers = _build_fillers(seed)
    advertisers = _build_advertisers(seed)
    rate_cards = _build_rate_cards(seed)
    markets = _build_markets(seed)
    orders, clearance_plan = _build_orders(
        seed, breaks, schedule, advertisers, markets)
    clearance = _build_clearance(seed, orders, clearance_plan)
    substitutes = _build_substitutes(seed)
    blackouts = _build_blackouts(seed, schedule)

    wb_scalars = _workbook_scalars(seed)
    memo_scalars = _memo_scalars(seed)
    control_codes, settled_index = _control_sets(seed)
    live_set = control_codes[settled_index]
    _plant_separators(estate, parts, schedule)

    # ---- primary fact tables --------------------------------------------
    ingest_rows = []
    for content_ref in estate["order"]:
        for row in estate["assets"][content_ref]["attempts"]:
            ingest_rows.append(row)
    ingest_cols = ["ingest_id", "content_ref", "title_code", "version_tag",
                   "revision_no", "qc_state", "rate_code", "tc_mode",
                   "nominal_fps", "som_tc", "eom_tc", "house_no", "received_at"]
    _wdelim(root / "ingest_attempt_register.csv", ingest_cols, ingest_rows, ",")

    rate_rows = []
    for code in RATE_CODES:
        num, den, tc_base, df_allowed, nominal = RATE_TABLE[code]
        rate_rows.append({
            "rate_code": code, "rate_num": str(num), "rate_den": str(den),
            "tc_base": str(tc_base), "df_allowed": df_allowed,
            "rounded_label": nominal,
        })
    _wdelim(root / "rate_code_register.csv",
            ["rate_code", "rate_num", "rate_den", "tc_base", "df_allowed",
             "rounded_label"], rate_rows, ",")

    _wdelim(root / "segment_part_manifest.tsv",
            ["content_ref", "part_no", "part_kind", "part_som_tc",
             "part_eom_tc", "source_note"], parts, "\t")

    _wdelim(root / "gop_index_channel.psv",
            ["content_ref", "idr_frame", "picture_kind", "index_note"],
            gop, "|")

    _wdelim(root / "break_plan_register.csv",
            ["slot_id", "break_no", "nominal_offset_seconds", "avail_seconds",
             "break_note"], breaks, ",")

    _wdelim(root / "transmission_schedule.csv",
            ["slot_id", "content_ref", "sched_start_tc", "junction_kind",
             "flex_part_no", "daypart_ref", "service_note"],
            _schedule_file_rows(schedule["rows"]), ",")

    _wdelim(root / "filler_library.csv",
            ["filler_ref", "predicate_order", "min_frames", "max_frames",
             "daypart_ref", "stock_state", "stock_note"], fillers, ",")

    _wjsonl(root / "spot_order_book.jsonl", orders)

    _wdelim(root / "advertiser_register.csv",
            ["advertiser_ref", "advertiser_name", "settlement_currency",
             "agency_ref", "account_note"], advertisers, ",")

    _wdelim(root / "rate_card_book.csv",
            ["rate_card_ref", "effective_from", "minor_per_grain",
             "card_revision", "card_note"], rate_cards, ",")

    _wdelim(root / "clearance_state_journal.csv",
            ["clearance_ref", "journal_seq", "clearance_state", "logged_at",
             "clearance_note"], clearance, ",")

    _wdelim(root / "market_register.csv",
            ["market_ref", "market_name", "regulator_ref", "feed_note"],
            markets, ",")

    _wdelim(root / "substitution_library.csv",
            ["substitute_ref", "break_no", "nominal_offset_seconds",
             "avail_seconds", "substitute_note"], substitutes, ",")

    _wtext(root / "currency_minor_units.json", canonical_json(
        {"exponents": {"BHD": 3, "EUR": 2, "JPY": 0, "USD": 2},
         "note": "the exponent is the number of minor units per major unit "
                 "expressed as a power of ten"}))

    _wdelim(root / "daypart_calendar.csv",
            ["hour_label", "daypart_ref", "hour_note"],
            [{"hour_label": h, "daypart_ref": DAYPART_BY_HOUR[h],
              "hour_note": "clock hour %s of the broadcast day" % h}
             for h in HOUR_LABELS], ",")

    # ---- blackout rules and the disavowed draft overlay ------------------
    def _rule_xml(rows, root_tag, status):
        out = ['<?xml version="1.0" encoding="UTF-8"?>']
        out.append('<%s status="%s">' % (root_tag, status))
        for row in rows:
            out.append(
                '  <rule rule_id="%s" precedence="%s" market_ref="%s" '
                'content_ref="%s" window_from="%s" window_to="%s" '
                'substitute_ref="%s" override="%s"/>' % (
                    xml_escape(row["rule_id"]), xml_escape(row["precedence"]),
                    xml_escape(row["market_ref"]), xml_escape(row["content_ref"]),
                    xml_escape(row["window_from"]), xml_escape(row["window_to"]),
                    xml_escape(row["substitute_ref"]), xml_escape(row["override"])))
        out.append("</%s>" % root_tag)
        return "\n".join(out)

    _wtext(root / "blackout_rule_set.xml",
           _rule_xml(blackouts, "blackout_rules", "settled"))

    draft = []
    for i, row in enumerate(blackouts):
        copy = dict(row)
        copy["rule_id"] = "dr_%03d" % (i + 1)
        copy["precedence"] = str(int(row["precedence"]) - 5)
        copy["substitute_ref"] = "sub_0%d" % ((i % 8) + 1)
        draft.append(copy)
    _wtext(root / "blackout_overlay_drafts.xml",
           _rule_xml(draft, "blackout_overlay", "draft-superseded"))

    # ---- decoys ----------------------------------------------------------
    legacy = []
    for i, adv in enumerate(advertisers):
        legacy.append({
            "advertiser_ref": adv["advertiser_ref"],
            "commission_pct": ratio(F(3 + (i % 19)) / 2, 2),
            "table_status": "superseded",
            "legacy_note": "percent of gross under the retired schedule",
        })
    _wdelim(root / "legacy_commission_table.csv",
            ["advertiser_ref", "commission_pct", "table_status", "legacy_note"],
            legacy, ",")

    # ---- the prior computation the day is reconciled against -------------
    canon_by_ref = schedule["canon_by_ref"]
    part_by_ref: dict = {}
    for row in parts:
        part_by_ref.setdefault(row["content_ref"], []).append(row)
    break_count: dict = {}
    for row in breaks:
        break_count[row["slot_id"]] = break_count.get(row["slot_id"], 0) + 1
    prior_rows = []
    for slot in schedule["rows"]:
        canon = canon_by_ref.get(slot["content_ref"])
        material = 0
        if canon is not None:
            num, den, tc_base, df_allowed, _ = RATE_TABLE[canon["rate_code"]]
            df_here = (canon["tc_mode"] == "DF" and df_allowed == "yes")
            span = (tc_base * 86400 - drop_per_minute(tc_base) * (1440 - 144)
                    if df_here else tc_base * 86400)
            for row in part_by_ref.get(slot["content_ref"], []):
                a = tc_to_frames(row["part_som_tc"], tc_base, df_here)
                b = tc_to_frames(row["part_eom_tc"], tc_base, df_here)
                n = b - a
                if n < 0:
                    n += span
                material += nint(rate_convert(n, num, den))
        prior_rows.append({
            "slot_id": slot["slot_id"],
            "prior_start_frame": str(_sched_offset(slot["sched_start_tc"])),
            "prior_material_frames": str(material),
            "prior_break_count": str(break_count.get(slot["slot_id"], 0)),
            "register_status": "superseded",
        })
    # The prior computation never carried the last slot of the day, so the
    # reconciliation has one slot it must read as zero on the prior side.
    prior_rows = prior_rows[:-1]
    _wdelim(root / "prior_conform_register.csv",
            ["slot_id", "prior_start_frame", "prior_material_frames",
             "prior_break_count", "register_status"], prior_rows, ",")

    # ---- configuration ---------------------------------------------------
    _wtext(root / "channel_config.json", canonical_json({
        "channel_ref": "ch_regional_one",
        "transmission_date": tx.isoformat(),
        "channel_rate_code": "RC_2997",
        "day_start_tc": DAY_START_TC,
        "workbook_control_set": live_set,
        "instance_ref": _instance_ref(seed),
        "corpus_profile": profile,
        "house_filler_ref": "fl_house_black",
    }))

    # ---- the workbook and the memo ---------------------------------------
    sheets = {}
    superseded = 0
    for i, name in enumerate(SHEET_NAMES):
        if i == settled_index:
            variant = 0
        else:
            superseded += 1
            variant = superseded
        sheets[name] = _sheet_rows(control_codes[i], wb_scalars, advertisers,
                                   variant, _rng(seed, "sheet-%d" % i))
    write_xlsx(root / "contract_terms_workbook.xlsx", sheets)
    write_pdf(root / "regulatory_minutage_memo.pdf",
              _memo_lines(seed, memo_scalars, tx))

    # ---- redundant stores -------------------------------------------------
    write_sqlite(root / "playout_audit.sqlite", {
        "ingest_attempt": (ingest_cols,
                           [[row[c] for c in ingest_cols] for row in ingest_rows]),
        "schedule_slot": (["slot_id", "content_ref", "sched_start_tc",
                           "junction_kind", "flex_part_no", "daypart_ref"],
                          [[s["slot_id"], s["content_ref"], s["sched_start_tc"],
                            s["junction_kind"], s["flex_part_no"], s["daypart_ref"]]
                           for s in _schedule_file_rows(schedule["rows"])]),
    })
    write_sqlite(root / "traffic_audit.db", {
        "spot_order": (["order_ref", "advertiser_ref", "break_ref",
                        "nominal_seconds", "market_ref", "priority_band"],
                       [[o["order_ref"], o["advertiser_ref"], o["break_ref"],
                         str(o["nominal_seconds"]), o["market_ref"],
                         str(o["priority_band"])] for o in orders]),
        "clearance_event": (["clearance_ref", "journal_seq", "clearance_state",
                             "logged_at"],
                            [[c["clearance_ref"], c["journal_seq"],
                              c["clearance_state"], c["logged_at"]]
                             for c in clearance]),
    })

    # ---- worked vectors ---------------------------------------------------
    _wtext(root / "unit_test_vectors.json", canonical_json(_unit_vectors()))
    _wjsonl(root / "sample_worked_records.jsonl", _worked_records())

    # ---- the written corpus ------------------------------------------------
    for name, text in _documents(profile).items():
        _wtext(root / name, text)
    _plant_hour_straddle(root, breaks, planted_slots)

    return {
        "seed": seed,
        "profile": profile,
        "transmission_date": tx,
        "live_control_set": live_set,
        "workbook_scalars": wb_scalars,
        "memo_scalars": memo_scalars,
    }


def _sched_offset(tc: str) -> int:
    """A channel timecode taken into whole frames from the broadcast day
    start. A label before the day start belongs to the following calendar
    day and therefore to the end of this broadcast day."""
    frames = tc_to_frames(tc, CH_BASE, CH_DF)
    start = tc_to_frames(DAY_START_TC, CH_BASE, CH_DF)
    if frames < start:
        return frames + DAY_FRAMES - start
    return frames - start


# ==========================================================================
# the written corpus
#
# Every decision the pipeline grades is written down normatively in its
# stage specification. Where a specification names a wrong reading it does
# so only to rule it out, and no document publishes counts a day can be
# checked against.
# ==========================================================================

R = INPUT_ROOT


def _txt_readme() -> str:
    return """readme first
============

This directory is the whole of the material for one transmission day of a
regional playout channel. Nothing outside it is needed and nothing outside
it is authoritative.

The file names are deliberately non obvious. They name the record they hold
and not the stage that consumes them, so the way to find a value is to open
files rather than to guess from a stem. Start with these three:

  pipeline_contract_overview.md      what the fourteen stages are
  data_lineage.md                    which file feeds which stage
  output_artifact_contract.md        what has to be written, and where

Two load bearing sources are not plain text.

  contract_terms_workbook.xlsx       a real workbook with three sheets. One of
                                     them carries the settled control set and
                                     the other two are superseded, each with
                                     terms of its own. The sheet name settles
                                     nothing and neither does the sheet
                                     position; the control set cell does.
  regulatory_minutage_memo.pdf       a real document. Three settlement
                                     constants are published there and
                                     nowhere else in this directory.

Three files are decoys and each is disavowed in data_lineage.md:
legacy_commission_table.csv, blackout_overlay_drafts.xml and
prior_conform_register.csv. The prior register is the superseded automated
computation of this same day. It is reported against and never consumed.

Every identifier in this directory is minted for this instance. There is
nothing here to look up anywhere else, and no external source knows these
references.
"""


def _doc_overview() -> str:
    return """# Pipeline contract overview

One transmission day of the channel `ch_regional_one` is conformed in
fourteen stages. Each stage freezes a value that the next stage consumes.
The stages are numbered V1 to V14 and each has its own specification file in
this directory.

| stage | file | what it freezes |
|---|---|---|
| V1 | spec_stage_v1_asset_canonicalisation.md | the canonical ingest attempt per asset |
| V2 | spec_stage_v2_rate_resolution.md | the editorial rate and the drop frame flag |
| V3 | spec_stage_v3_source_span.md | the source frame span of an asset |
| V4 | spec_stage_v4_channel_conversion.md | the channel frame count of a part |
| V5 | spec_stage_v5_segment_assembly.md | the material duration of a slot |
| V6 | spec_stage_v6_splice_conditioning.md | the conditioned position of a break |
| V7 | spec_stage_v7_schedule_placement.md | the placed start of a slot |
| V8 | spec_stage_v8_drift_correction.md | the trims and the fills |
| V9 | spec_stage_v9_avail_derivation.md | the admitted spots and the deferrals |
| V10 | spec_stage_v10_market_substitution.md | the per market break set |
| V11 | spec_stage_v11_settlement.md | the money in minor units |
| V12 | spec_stage_v12_make_good.md | the make good obligations |
| V13 | spec_stage_v13_minutage_compliance.md | the advertising frames per clock hour and the frames left unbilled |
| V14 | spec_stage_v14_reconciliation.md | the deltas and the digest |

The numbers name the stages, not the order they run in. V10 runs before V9,
because V9 admits spots against the per market break set V10 freezes. V13
runs before V11, because V11 bills only the frames V13 leaves inside the
regulatory cap of each clock hour (R41), and V12 then values both the
deferrals and the grains V11 could not bill.

## The channel

The channel transmits at the exact rational rate `30000/1001` frames per
second and publishes drop frame timecode on a timecode base of thirty. The
broadcast day opens at the timecode `06:00:00;00` and runs for one whole day
of channel timecode frames, which is `2589408` frames. A timecode label
earlier than the day start belongs to the following calendar day and
therefore to the end of this broadcast day.

Every published frame count in every artifact is a whole number of channel
frames unless the column name says otherwise.

## The pervasive rule

Every conversion of a frame count or a duration into channel frames is
carried out in exact rational arithmetic, floored to a whole frame, and the
fraction that the floor discarded is held in a named carry scope and added
to the next conversion made inside that same scope. A scope releases a whole
frame as soon as the held fraction reaches one. Nothing is ever rounded to
nearest, and no intermediate value is rounded at all. The scopes are named
in spec_stage_v4_channel_conversion.md and their residuals are published.

## The correction this job is

`prior_conform_register.csv` holds the previous automated computation of
this same transmission day. It is wrong. Stage V14 reports the recomputation
against it. The prior register is never an input to any other stage.
"""


def _doc_v1() -> str:
    return """# V1 asset canonicalisation

Input: `ingest_attempt_register.csv`.

## R01 the natural key

The register holds one row per ingest attempt. The economic key of an asset
is `content_ref`. The `ingest_id` column identifies the attempt and not the
asset, so two rows carrying the same `content_ref` are two attempts at the
same asset and are clustered together.

## R02 the canonical attempt

Within a cluster the canonical attempt is the row with the greatest
`revision_no` among the rows whose `qc_state` is a passed state. The passed
states are exactly `QC_PASSED` and `QC_PASSED_WITH_NOTES`. The states
`QC_PENDING`, `QC_REJECTED` and `QC_WITHDRAWN` are not passed states.

A cluster in which no attempt carries a passed state has no canonical
attempt. It is excluded from every downstream stage and is published in the
asset register with the inclusion state `AS_EXCLUDED` and with every derived
field left empty.

The greatest `revision_no` in a cluster is frequently an attempt that did
not pass. The revision number alone never settles which attempt is
canonical.

## R03 the revision tie

When two or more passed attempts in one cluster carry the same
`revision_no`, the canonical attempt is the one whose `ingest_id` sorts
first as a string.

## R04 the house anchor

The house number published for an asset is the `house_no` of the cluster's
first received attempt, which is the attempt with the earliest
`received_at`, ties broken by the `ingest_id` that sorts first. The first
received attempt is called the anchor.

## R43 arrival is an instant

The ingest desks key `received_at` in their own zones, so every value is an
ISO 8601 date and time followed by its offset from UTC: `Z`, or a sign and
`hh:mm`. The earliest attempt is the one whose value names the earliest
instant once its offset is applied. Two values name the same instant when
they agree after their offsets are applied, however differently they are
written, and such a tie is broken by the `ingest_id`. The text of the value
is never the ordering key: compared as text, a time keyed at `+10:00` sorts
after one keyed at `-05:00` that arrived later. The anchor is computed for every
cluster, including a cluster with no canonical attempt.

The anchor is almost never the canonical attempt. The canonical attempt
supplies the rate code, the timecode mode and the timecodes; the anchor
supplies the house number and nothing else.

## Published

`asset_register.csv` carries one row per cluster, ordered by `content_ref`
ascending, with the columns named in output_schema_reference.md.
"""


def _doc_v2() -> str:
    return """# V2 rate resolution

Inputs: the canonical attempt from V1, and `rate_code_register.csv`.

## R05 the editorial rate

The editorial rate of an asset is the exact rational `rate_num / rate_den`
read from `rate_code_register.csv` against the canonical attempt's
`rate_code`. The `nominal_fps` column in the ingest register is a rounded
label kept for the traffic system's own display. It is never the rate. A
rate of `30000/1001` is not `29.97` and the difference matters at every
conversion.

The `nominal_fps` label is also occasionally inconsistent with the
attempt's own rate code. That is a recording defect in the source system and
is another reason the label is never read as a rate.

## R06 the drop frame flag

Drop frame labelling applies to an attempt when both of these hold:

  the attempt's `tc_mode` is `DF`
  the rate register's `df_allowed` for that rate code is `yes`

An attempt that claims `DF` on a rate code whose `df_allowed` is `no` is
read as non drop. Drop frame is a property of the rate, not of the row that
claims it.

## R40 the separator is not evidence

The registers are keyed at several desks. Some labels of drop frame material
carry a colon before the frame number, and some labels of non drop material
carry a semicolon there. The separator a label was keyed with says nothing
about drop frame: every label of an asset, its `som_tc`, its `eom_tc` and the
`part_som_tc` and `part_eom_tc` of each of its parts, is counted under the
drop frame flag R06 settles for the asset's canonical attempt, and every
`sched_start_tc` is counted under the channel's own drop frame behaviour.
A label is published, where a published column carries it, exactly as the
register records it.

## The timecode base

The `tc_base` column of the rate register is the whole number of frame
numbers a second of timecode carries at that rate code. Timecode fields
count in `tc_base`; durations convert at `rate_num / rate_den`. The two are
not the same number for any rate code whose denominator is `1001`.

## Drop frame arithmetic

At timecode base `b`, drop frame skips `b * 2 / 30` frame numbers at the
start of every minute whose minute number within the day is not a multiple
of ten. For a timecode `hh:mm:ss` with frame `ff` and `m = hh * 60 + mm`,
the whole frame count is

    ((hh * 60 + mm) * 60 + ss) * b + ff - (b * 2 / 30) * (m - m / 10)

with both divisions taken as whole number division.
"""


def _doc_v3() -> str:
    return """# V3 source span

Inputs: the canonical attempt from V1, and the rate resolved at V2.

## R08 the span

The source frame span of an asset is the frame count of its `eom_tc` less
the frame count of its `som_tc`, both taken at the asset's timecode base
under the asset's drop frame flag. The end of media timecode is exclusive:
an asset whose start and end labels are equal spans zero frames.

When the end frame count is less than the start frame count the asset wraps
the timecode day. One whole timecode day is added to the difference. A
timecode day at base `b` is `b * 86400` frames when the asset is non drop,
and `b * 86400 - (b * 2 / 30) * 1296` frames when it is drop frame.

A negative span is never published. Every span is zero or greater.

## Published

The span is published as `source_frames` in `asset_register.csv`, together
with `channel_frames_exact`, which is the exact rational count of channel
frames the span occupies rendered to ten decimal places. The exact count is
published rather than a whole number because no carry scope is open at the
asset level; the whole numbers appear at V4.
"""


def _doc_v4() -> str:
    return """# V4 channel conversion

Input: a source frame count and its editorial rate.

## R10 the carry rule

This is the rule that applies at every stage that converts anything into
channel frames.

A count of `n` frames at the editorial rate `p / q` occupies exactly

    n * 30000 * q / (1001 * p)

channel frames. That value is a rational number and it is almost never a
whole number. To take it into whole frames:

  1. add the fraction currently held in the conversion's named carry scope
  2. take the floor of the sum
  3. keep the difference between the sum and its floor as the new held
     fraction of that scope

A duration in seconds converts the same way, with the exact value
`seconds * 30000 / 1001`.

The floor is taken toward minus infinity. Nothing is rounded to nearest at
any point. A scope releases a whole extra frame into a conversion whenever
the fraction it holds has reached one, which is exactly what step two does.

## The carry scopes

Each scope is opened with a held fraction of zero, is used by the
conversions that name it, and its residual fraction is published at the end
of the run.

| scope name | opened for | conversions inside it |
|---|---|---|
| `V4:` and the slot id | each placed slot | the parts of that slot, in part order |
| `V6:` and the slot id | each placed slot | the break offsets of that slot, in break order |
| `V9:` and the market ref | each market | the break capacities of that market, in transmission order |
| `V10:` and the market ref | each market | the substitute break offsets of that market, slot by slot |
| `V11:` and the advertiser ref | each advertiser with an order in `spot_order_book.jsonl` | the spot durations of that advertiser, in order reference order |

The scope name is the prefix, a colon, and the identifier, with no spaces.

## R11 the order inside a scope

Conversions inside a scope happen in the order the scope's row names. Parts
run in ascending `part_no`. Break offsets run in ascending `break_no`.
Capacities run in the market's transmission order, which is ascending break
position and then ascending break reference. Substitute break offsets run
slot by slot in ascending `sequence_no` of the placed slots, and in
ascending `break_no` of the substitute within one slot. Spot durations run in
ascending `order_ref` within an advertiser, and the advertisers run in
ascending `advertiser_ref`.

The spot duration conversion happens once for the whole day, before any
admission decision is taken, because the capacity check at V9 needs the
frame count and the frame count depends on the advertiser's earlier spots.

## Published

`segment_conform.csv` publishes, for each part of each placed slot, the
source frames, the exact channel frames to ten decimal places, the whole
channel frames the carry rule produced, and the fraction the scope held
after that conversion.
"""


def _doc_v5() -> str:
    return """# V5 segment assembly

Inputs: `segment_part_manifest.tsv`, the assets from V1 to V3, and the
placed slots from V7.

## The parts of a slot

A slot transmits the parts of its `content_ref` in ascending `part_no`.
Each part carries its own `part_som_tc` and `part_eom_tc` at the asset's
timecode base and drop frame flag, and its span is taken by the V3 rule.
Part labels are counted under R40 whatever separator they were keyed with.

## R12 black trimming

Parts whose `part_kind` is `PT_BLACK` are trimmed when they sit at the head
or at the tail of the part sequence. A run of black at the head is trimmed,
a run of black at the tail is trimmed, and black anywhere between two parts
that are not black is transmitted.

A trimmed part is published with the retention state `PR_TRIMMED_HEAD` or
`PR_TRIMMED_TAIL`, contributes nothing to the material duration, and makes
no conversion, so it consumes no carry.

## R13 an asset with no parts

An asset with no rows in the part manifest transmits as a single part
covering the whole V3 span, published with `part_no` of `0` and a
`part_kind` of `PT_PROGRAMME`.

## The material duration

The material duration of a slot is the sum of the whole channel frame counts
of its retained parts, each produced by the carry rule inside the scope
`V4:` and the slot id.

## The flexible part

The transmission schedule names one `flex_part_no` per slot. That part is
the slot's flexible element and V8 trims it when a fixed junction has to be
met. The flexible part is always a tail element of the slot, so trimming it
moves no break position inside the slot.

The flexible part is the transmitted part whose `part_no` equals the slot's
`flex_part_no`. When no part of the slot carries that number, as with an
asset transmitted whole under R13 as part `0`, the slot has no flexible part
and gives up nothing to a trim.
"""


def _doc_v6() -> str:
    return """# V6 splice conditioning

Inputs: `break_plan_register.csv`, `gop_index_channel.psv`, and the snap
tolerance published in the settled sheet of `contract_terms_workbook.xlsx`.

## The nominal position

Each break carries a `nominal_offset_seconds` measured from the start of the
slot's material. It converts into whole channel frames by the carry rule
inside the scope `V6:` and the slot id, with the breaks of a slot converted
in ascending `break_no`.

## The index

`gop_index_channel.psv` publishes the channel frames at which the encoder
placed an index picture for a `content_ref`. A break can only be taken at an
index frame.

## R14 the snap

Let `t` be the position a break is aiming at and `T` the snap tolerance in
channel frames.

  If an index frame less than or equal to `t` exists and the greatest such
  frame is no more than `T` frames below `t`, the break snaps back to it.

  Otherwise, if an index frame greater than `t` exists, the break snaps
  forward to the least such frame.

  Otherwise, if an index frame less than or equal to `t` exists, the break
  snaps back to the greatest such frame whatever the distance.

  Otherwise the content has no index at all and the break stays where it is.

The published snap side is `SNAP_EXACT` when the snapped position equals
`t`, `SNAP_BACK` when it is below, `SNAP_FORWARD` when it is above, and
`SNAP_NONE` when the content carries no index frame.

## R15 the absorbed displacement

The displacement of a break is its snapped position less its nominal
position. Snapping moves breaks and the slot's material duration does not
change, so the displacement has to be absorbed inside the slot.

The last break of a slot aims not at its own nominal position but at its
nominal position less the sum of the displacements of every earlier break in
the same slot, floored at zero. It then snaps by R14 from that adjusted
target. Its published displacement is still measured against its own
nominal position.

A slot with one break has nothing to absorb and its single break aims at its
own nominal position. Snapping every break in a slot independently is
locally defensible and is wrong.

## Published

`break_positions.csv` publishes the nominal frame, the adjusted target
frame, the position frame, the snap side, the displacement and the carry
held after that break's conversion, ordered by slot and then by break
number.
"""


def _doc_v7() -> str:
    return """# V7 schedule placement

Inputs: `transmission_schedule.csv`, and the material durations from V5.

## R16 the broadcast day

Each slot carries a `sched_start_tc` as a channel drop frame timecode,
counted under the channel's drop frame behaviour whatever separator it was
keyed with (R40). Its scheduled offset is the frame count of that label less the frame count of
the day start label `06:00:00;00`. A label whose frame count is less than
the day start belongs to the following calendar day, and one whole broadcast
day of `2589408` frames is added to the difference.

Slots run in ascending scheduled offset, ties broken by ascending `slot_id`.
The sequence number published for a slot is its one based position in that
order.

## R17 a slot with no canonical asset

A slot whose `content_ref` has no canonical attempt is dropped from the day.
It is published in `slot_placement.csv` with a `sequence_no` of `0`, a
`placement_state` of `PL_DROPPED`, every frame column at zero and an empty
hour label, and a correction with the reason `CR_SLOT_DROPPED` is recorded
against it. It occupies no time and the slots after it move up.

## The junctions

A slot whose `junction_kind` is `JK_FIXED` publishes a junction that cannot
move: its placed start is its scheduled offset, always. A slot whose
`junction_kind` is `JK_FLOAT` starts where the slot before it ended.

The first slot of the day is a fixed junction.

## The running placement

Placement runs forward through the ordered slots. A floating slot starts at
the running cursor. A fixed slot starts at its scheduled offset, and the
difference between the running cursor and that offset is the correction V8
has to make. After a slot is placed the cursor moves to the slot's start
plus its transmitted frames, which are its material frames less any frames
V8 trimmed from it.
"""


def _doc_v8() -> str:
    return """# V8 drift correction

Inputs: the placement from V7, `filler_library.csv`, and the flexible part
named by each slot in `transmission_schedule.csv`.

## R18 an overrun

When the running cursor at a fixed junction is later than the junction's
scheduled offset, the day is overrunning by the difference.

The overrun is removed by trimming flexible parts, starting with the slot
immediately before the junction and walking backwards. The walk stops at the
previous fixed junction, and it includes that junction's own slot, because a
fixed junction pins a start and not an end.

A slot can give up at most the whole of its flexible part and never more, so
the floor of every trim is zero frames of flexible part remaining. The trim
taken from the slot immediately before the junction is recorded with the
reason `CR_TRIM_FLEX`, and every trim taken from a slot further back is
recorded with the reason `CR_TRIM_BACKFILL`.

If the overrun still cannot be removed after the whole walk, the residue is
recorded with the reason `CR_TRIM_SHORTFALL` and the junction is pinned
anyway. The slots between the previous fixed junction and this one are then
re-placed from the previous junction's start with their trimmed durations.

## R19 an underrun

When the running cursor at a fixed junction is earlier than the junction's
scheduled offset, the gap is filled.

The filler is chosen from `filler_library.csv` by walking the rows in
ascending `predicate_order` and taking the first row for which all three of
these hold:

  the row's `stock_state` is `FS_AVAILABLE`
  the row's `daypart_ref` is the junction slot's daypart or is `DP_ANY`
  the gap in frames is at least `min_frames` and at most `max_frames`

The first such row wins. If no row qualifies, the house filler named by
`house_filler_ref` in `channel_config.json` is used and the published
selection index is `0`. The fill is recorded with the reason
`CR_FILL_INSERT` and the filler is taken to occupy exactly the gap.

## R20 a junction that needs nothing

A fixed junction the cursor reaches exactly is recorded with the reason
`CR_NO_CHANGE` and a frame count of zero.

## Published

`slot_placement.csv` publishes every slot. `conform_trace.json` publishes
the corrections in the order they were made, numbered from one, with the
totals by reason and the day end frame. `filler_plan.csv` publishes the
fills.
"""


def _doc_v9() -> str:
    return """# V9 avail derivation

Inputs: `spot_order_book.jsonl`, `clearance_state_journal.csv`,
`rate_card_book.csv`, the break sets from V10, and the separation minimum
published in `regulatory_minutage_memo.pdf`.

## The break capacity

Each break carries an `avail_seconds`. Its capacity in channel frames is
that duration converted by the carry rule inside the scope `V9:` and the
market reference, with the breaks of a market converted in transmission
order. A break with an `avail_seconds` of zero has a capacity of zero
frames.

## R32 the effective clearance state

`clearance_state_journal.csv` holds several rows per `clearance_ref`. The
effective state is the state of the row with the greatest `journal_seq`.
The `logged_at` column is backfilled by the traffic system and its order
frequently disagrees with the sequence order. The sequence settles it.

## R38 the sequence is a whole number

`journal_seq` is a whole number and compares as one. A journal can run past
nine entries, and sequence 10 follows sequence 9. Compared as text, `9`
sorts after `10` and `11`, which settles the wrong row.

## R21 the spot duration

A spot occupies the channel frames its `nominal_seconds` converts to under
the carry rule inside the scope `V11:` and the advertiser reference, as V4
sets out. That conversion happens for every order in the book before any
admission decision is taken.

## R22 the admission predicates

Orders are considered market by market. Within a market, orders are ordered
by ascending `priority_band` and then by ascending `order_ref`, and are
walked in that order. That is rule R24.

For each order, these seven predicates are evaluated in this exact order and
the first one that holds settles the order. The break named by an order's
`break_ref` is the break it is sold against; it is never moved to another
break.

  1. the effective clearance state is `CL_HELD`, giving `DF_CLEARANCE_HELD`
  2. the slot the break belongs to is substituted in this market, giving
     `DF_MARKET_BLACKED`
  3. the break reference is not in this market's break set, giving
     `DF_NO_MATCHING_BREAK`
  4. the order's `daypart_ref` differs from the break's daypart, giving
     `DF_DAYPART_MISMATCH`
  5. the order's rate card has no row effective on or before the
     transmission date, giving `DF_NO_RATE_CARD`
  6. the frames already admitted to the break plus this spot's frames exceed
     the break's capacity, giving `DF_BREAK_FULL`
  7. the separation rule is breached, giving `DF_SEPARATION`

An order that none of the seven settles is admitted. It takes the next
admitted position in its break, starts at the break position plus the frames
already admitted there, and occupies its own frames.

The order of the predicates is the whole of the rule. A held order that
would also have overflowed its break is deferred as held, not as full.

## R23 the separation rule

Let `S` be the separation minimum positions published in the memorandum, and
let the order under consideration be about to take position `n` in its
break. The separation rule is breached when an already admitted spot at
position `p` in the same break carries the same `separation_class` and
`n - p` is less than `S`. A minimum of two therefore bars two spots of one
class from adjacent positions.

A deferral costs the break nothing: a deferred spot consumes no capacity and
takes no position.

## Published

`avail_plan.tsv` publishes the admitted spots ordered by market, then by
break position, then by break reference, then by position in break.
`deferral_ledger.jsonl` publishes one record per deferred order, ordered by
`order_ref` and then by market reference, carrying the reason and the one
based index of the predicate that settled it.
"""


def _doc_v10() -> str:
    return """# V10 market substitution

Inputs: `market_register.csv`, `blackout_rule_set.xml`,
`substitution_library.csv`, and the placed slots from V7 and V8.

The channel runs into four markets. The national conform is one day; what
differs between markets is which slots carry substitute material and
therefore which breaks exist.

## R25 the window

A blackout rule matches a slot in a market when the rule's `market_ref` is
that market, the rule's `content_ref` is the slot's content, and the
transmission date lies inside the rule's window. The window is inclusive at
both ends: a transmission date equal to `window_from` is inside it and a
transmission date equal to `window_to` is inside it.

## R26 the precedence and the overturn

The matching rules for one slot in one market are ordered by ascending
`precedence` and then by ascending `rule_id`. The first rule in that order
is the base rule.

A rule whose `override` is `yes` overturns every rule before it in that
order. When one or more overturning rules match, the last overturning rule
in the order wins. When none does, the base rule wins.

An overturning rule therefore wins from a higher precedence number, which is
the opposite of what precedence alone would give.

## The substituted break set

A slot substituted in a market carries the substitute's breaks in place of
its own. The substitute's breaks come from `substitution_library.csv` under
the winning rule's `substitute_ref`, in ascending `break_no`.

A substitute has no index of its own, so its break positions are not
snapped. Each substitute break offset converts by the carry rule inside the
scope `V10:` and the market reference, and its position is the slot's placed
start plus that offset. Its break reference is `sb_`, the substitute
reference, an underscore and the two digit break number.

A slot that is not substituted in a market carries its national breaks with
the positions V6 conditioned. Its break reference is `bk_`, the slot id, an
underscore and the two digit break number.

## Published

`market_overrides.csv` publishes one row per substituted slot per market,
ordered by market reference and then by slot id. Each per market avail
file, named for its market reference, publishes that market's whole break
set in transmission order together with the two carry residuals of that
market.
`market_avail_stream.jsonl` publishes every market's breaks in one stream.
"""


def _doc_v11() -> str:
    return """# V11 settlement

Inputs: the admitted spots from V9, `rate_card_book.csv`,
`advertiser_register.csv`, `currency_minor_units.json`, the commission terms
in the settled sheet of `contract_terms_workbook.xlsx`, and the billing
grain published in `regulatory_minutage_memo.pdf`.

## R27 the billable grains

A grain is the billing grain in whole seconds, and it occupies
`grain * 30000 / 1001` channel frames exactly. A delivered spot bills the
smallest whole number of grains that covers its delivered frames, so the
grain count is the ceiling of the delivered frames divided by the frames a
grain occupies. A delivery that lands exactly on a grain boundary bills that
many grains and no more. A delivered spot of zero frames bills zero grains.

The frames a spot bills are its delivered frames less its unbilled frames,
the frames V13 left above the regulatory cap of a clock hour under R41. The
grain count is taken over the billed frames, not over the delivered frames,
and a spot all of whose frames went unbilled bills zero grains. The
`delivered_frames` column still publishes every frame the spot occupied, and
`unbilled_frames` publishes the frames R41 took from it.

## R28 the rate card

The rate card that prices a spot is the row of `rate_card_book.csv` carrying
the order's `rate_card_ref` with the greatest `effective_from` that is on or
before the transmission date. A card whose `effective_from` equals the
transmission date is eligible. An order whose card has no eligible row is
never admitted, and is recorded in the exception ledger with the code
`EX_NO_CARD`.

The date compared is the transmission date of the broadcast day, for every
spot of the day. A spot that airs after midnight, in the hours `H24` to
`H29`, still belongs to the broadcast day that began at the day start, and a
card that takes effect on the following calendar day prices none of it.

## R39 two revisions on one date

When two eligible rows of one `rate_card_ref` share the greatest
`effective_from`, the row with the greater `card_revision` prices the spot.
`card_revision` is a whole number and compares as one, so revision 10
supersedes revision 9. The order the rows sit in the file settles nothing.

## R29 the money

The gross of a spot in minor units is its billable grains multiplied by the
card's `minor_per_grain`. The published major amount is the gross divided by
ten raised to the currency's exponent, rendered to that many decimal places.
The exponent comes from `currency_minor_units.json` per currency and is not
two for every currency.

## R30 the commission

The agency commission is the gross multiplied by the advertiser's
`commission_num` over `commission_den`, taken from the rows of the settled
workbook sheet whose first cell is `COMMISSION`, and rounded to a whole
minor unit with halves going to the even value. The net is the gross less
the commission.

`legacy_commission_table.csv` publishes a superseded commission in a
different parameter space and is never read.

## Published

`settlement_ledger.psv` publishes one row per admitted spot, ordered by
`order_ref` and then by market reference. `exception_ledger.jsonl` publishes
one record per exception, ordered by `order_ref` and then by exception code,
with the code `EX_ZERO_DELIVERY` for an admitted spot that occupies no
channel frame and the code `EX_NO_CARD` for an order with no eligible rate
card. `advertiser_summary.csv` publishes one row per advertiser in the
register, ordered by `advertiser_ref`, whether or not the advertiser has any
admitted spot.
"""


def _doc_v12() -> str:
    return """# V12 make good

Inputs: the deferrals from V9, the settlement from V11, and the make good
cap terms in the settled sheet of `contract_terms_workbook.xlsx`.

## The obligations

A deferred order raises a make good obligation valued at the gross it would
have earned, which is its billable grains under R27 priced by its rate card
under R28. An order that has no eligible rate card under R28 raises no
obligation, whatever the reason it was deferred with, because there is no
card to value it with. The reason `DF_NO_RATE_CARD` is the common case, but
an order deferred earlier in the predicate order can have no card too.

An admitted spot whose billable grains R41 cut raises an obligation too. Its
reason is `DF_OVER_CAP`, and it is valued at the grains it lost, priced by
the card that priced the spot: the grains its delivered frames would bill
under R27, less the grains its billed frames bill, multiplied by the card's
`minor_per_grain`. An admitted spot that lost frames to the cap but no whole
grain raises no obligation. An order is either admitted or deferred, so it
raises at most one obligation.

## The cap

An advertiser's day gross is the sum of the gross of its admitted spots, as
V11 billed them after R41. The
advertiser's make good cap in minor units is the day gross multiplied by
`makegood_cap_num` over `makegood_cap_den` from the settled workbook sheet,
floored to a whole minor unit. An advertiser with no admitted spot has a day
gross of zero and therefore a cap of zero.

## R31 the redistribution

When the sum of an advertiser's raw obligations is at most the cap, every
obligation is allocated its raw value.

When the sum exceeds the cap, the cap is allocated across the obligations in
proportion to their raw values by the largest remainder method. Each
obligation takes the floor of its exact proportional share; the minor units
left over between the sum of those floors and the cap are then handed out one
minor unit at a time to the obligations with the largest discarded
remainders, ties broken by ascending `order_ref`.

The allocation is mass preserving: the allocated total equals the cap
exactly. Flooring each share and discarding the remainder loses that mass
and is wrong.

## Published

`makegood_ledger.json` publishes one entry per advertiser that has either an
obligation or an admitted spot, ordered by `advertiser_ref`, each carrying
the day gross, the cap, the raw total, the allocated total and the
obligations in ascending `order_ref`.
"""


def _doc_v13() -> str:
    return """# V13 minutage compliance

Inputs: the admitted spots from V9, `daypart_calendar.csv`, and the
regulatory minutes published in Sections 1 and 2 of
`regulatory_minutage_memo.pdf`. V13 runs before V11.

## The clock hours

The broadcast day is twenty four clock hours long. Hour `H06` runs from the
day start to one hour of channel timecode frames later, which is `107892`
frames, and each following hour runs for the same count. The hours are
labelled `H06` through `H29`, so the small hours of the following calendar
day carry the labels `H24` through `H29` and sit at the end of the day.

The last hour of the day, `H29`, absorbs anything that runs past the end of
the day.

## R33 the advertising frames

The advertising frames of a market in a clock hour are the channel frames of
admitted spots that lie inside that hour. A spot that straddles an hour
boundary contributes to each hour exactly the frames that lie inside it. A
spot is not assigned whole to the hour its first frame falls in.

## R37 the minutes of one market hour

Section 1 of the memo publishes `regulatory_minutes_per_clock_hour`, the
standing figure. Section 2 lists permitted minutes per market and clock
hour. Where Section 2 lists a market and hour, its minutes govern that
market hour and replace the standing figure; where it does not list one,
the standing figure governs. Each market hour has its own cap.

## R34 the cap

The cap in channel frames of a market hour is its regulatory minutes under
R37 multiplied by sixty seconds, converted into channel frames by the exact rational
`seconds * 30000 / 1001`, and floored. It is not the minutes multiplied by
sixty and then by the timecode base of thirty. The channel does not run at
thirty frames per second and the two figures differ by several frames an
hour.

An hour whose advertising frames are greater than the cap is a breach and
publishes the state `MB_BREACH`. An hour that lands exactly on the cap is
not a breach and publishes `MB_WITHIN`. The published `headroom_frames` is
the cap less the advertising frames and is negative in a breach.

## R41 the frames above the cap go unbilled

In every breaching market hour, the frames by which the advertising frames
exceed that hour's cap go unbilled. They are taken from the admitted spots
of that market that have frames inside the hour, latest first: in
descending `start_frame`, ties broken by descending `order_ref`. Each spot
in turn gives up the smaller of its frames inside that hour and the frames
still to be taken, until the excess is taken. A spot that straddles two
breaching hours can give up frames to each, never more than it has inside
each. A spot's unbilled frames are the sum of what it gave up over the day.
V11 bills the rest, and V12 owes the grains it lost.

## Published

`minutage_report.csv` publishes one row per market per clock hour, ordered
by market reference and then by hour label, for all four markets and all
twenty four hours whether or not any spot fell in them. `cap_frames` is
that market hour's own cap under R37, and `headroom_frames` and
`breach_state` are judged against it.
"""


def _doc_v14() -> str:
    return """# V14 reconciliation and the digest

Inputs: everything above, and `prior_conform_register.csv`.

## The prior register

`prior_conform_register.csv` is the superseded automated computation of this
transmission day. It carries a start frame, a material frame count and a
break count per slot. It is wrong in places and it is never an input to any
other stage.

## R35 the reconciliation

`reconciliation.xml` publishes one `slot` element per slot in
`slot_placement.csv`, ordered by ascending `slot_id`, carrying the prior
value, the recomputed value and the delta for each of the start frame, the
material frames and the break count. The break count compared is the number
of national breaks the slot carries, which is the number of rows the slot
has in `break_positions.csv`.

The delta is the recomputed value less the prior value. A slot that agrees
on all three is counted as agreeing. The `totals` element carries the slot
count, the agreeing count, the differing count, and the sums of the absolute
start delta and the absolute material delta.

## R36 the digest

`manifest.json` publishes a `digest` which is the hexadecimal sha256 of the
concatenated bytes of the seven core artifacts, taken in the pipeline order
that `core_order` publishes and not in alphabetical order. The seven core
artifacts are the ones named in serialisation_and_digest_contract.md.
"""


def _doc_lineage() -> str:
    return """# Data lineage

Which file feeds which stage, and which files feed nothing.

| file | stages | note |
|---|---|---|
| `channel_config.json` | all | the transmission date, the day start and the live control set |
| `ingest_attempt_register.csv` | V1, V2, V3 | one row per ingest attempt |
| `rate_code_register.csv` | V2, V3, V4 | the exact rationals and the drop frame permission |
| `segment_part_manifest.tsv` | V5 | the parts of an asset |
| `transmission_schedule.csv` | V7, V8 | the day, the junctions and the flexible parts |
| `break_plan_register.csv` | V6, V9 | the nominal break offsets and the avail seconds |
| `gop_index_channel.psv` | V6 | the index frames a break can be taken at |
| `filler_library.csv` | V8 | the ordered filler predicates |
| `market_register.csv` | V9, V10, V13 | the four markets |
| `blackout_rule_set.xml` | V10 | the settled blackout rules |
| `substitution_library.csv` | V10 | the substitute break plans |
| `spot_order_book.jsonl` | V9, V11, V12 | one record per sold spot |
| `clearance_state_journal.csv` | V9 | several rows per clearance reference |
| `advertiser_register.csv` | V11, V12 | the settlement currency per advertiser |
| `rate_card_book.csv` | V9, V11, V12 | several dated rows per card reference |
| `currency_minor_units.json` | V11 | the minor unit exponent per currency |
| `daypart_calendar.csv` | V13 | the daypart of each clock hour |
| `contract_terms_workbook.xlsx` | V6, V11, V12 | the snap tolerance, the commission terms and the make good cap |
| `regulatory_minutage_memo.pdf` | V9, V11, V13 | the separation minimum, the billing grain, the regulatory minutes, and the permitted minutes per market hour |
| `prior_conform_register.csv` | V14 only | reported against, never consumed |

## The decoys

| file | why it is here | what it must not be used for |
|---|---|---|
| `legacy_commission_table.csv` | the retired commission schedule, kept for audit | it is a percentage in a different parameter space; the settled workbook sheet is the commission |
| `blackout_overlay_drafts.xml` | a draft overlay that was never signed off | its root element says `draft-superseded`; V10 reads `blackout_rule_set.xml` only |
| `prior_conform_register.csv` | the previous automated conform of this day | V14 reports against it; no other stage reads it |
| the two superseded workbook sheets | the terms of the other control sets | the settled sheet is the one whose control set cell matches the configuration |
| the `nominal_fps` column | the traffic system's display label | it is a rounded label, never a rate |

## The corroborating stores

`playout_audit.sqlite` and `traffic_audit.db` carry copies of the ingest
register, the schedule, the order book and the clearance journal. They
corroborate the flat files and add nothing to them.
"""


def _doc_glossary() -> str:
    return """# Glossary and field dictionary

## Terms

- **admitted position**: the one based index of a spot inside one break.
- **anchor**: the first received ingest attempt of an asset.
- **avail**: the commercial capacity published against one break.
- **break**: a conditioned splice point inside a transmitted slot.
- **broadcast day**: the day that opens at `06:00:00;00` and runs for
  `2589408` channel timecode frames.
- **canonical attempt**: the ingest attempt an asset is conformed from.
- **carry scope**: the named accumulator a conversion carries its discarded
  fraction into.
- **channel frame**: one frame at the channel rate of `30000/1001`.
- **clock hour**: one hour of channel timecode frames measured from the day
  start, which is `107892` frames.
- **daypart**: the commercial band a clock hour belongs to.
- **drop frame**: the timecode labelling that skips frame numbers.
- **grain**: the whole second unit a delivered spot is billed in.
- **index frame**: a channel frame the encoder marked as a splice point.
- **junction**: a scheduled slot start, fixed or floating.
- **make good**: an obligation raised against a deferred spot.
- **market**: one regional feed of the channel.
- **material duration**: the retained channel frames of a slot's parts.
- **minor unit**: the smallest indivisible unit of a currency.
- **slot**: one scheduled transmission of one asset.
- **substitute**: material carried in a market in place of a blacked out
  slot.

## Fields

### `ingest_attempt_register.csv`

- `ingest_id`: the identifier of one ingest attempt. Not an asset key.
- `content_ref`: the asset key. Several attempts share it.
- `title_code`, `version_tag`: the two components of the content reference.
- `revision_no`: the attempt's revision, a whole number.
- `qc_state`: one of `QC_PASSED`, `QC_PASSED_WITH_NOTES`, `QC_PENDING`,
  `QC_REJECTED`, `QC_WITHDRAWN`.
- `rate_code`: the key into `rate_code_register.csv`.
- `tc_mode`: `DF` or `NDF`, as the attempt claims it.
- `nominal_fps`: a rounded display label. Never a rate.
- `som_tc`, `eom_tc`: the start and the exclusive end of media. The
  separator before the frames is not evidence of drop frame (R40).
- `house_no`: the house number. Published from the anchor.
- `received_at`: when the attempt arrived, an ISO 8601 date and time with an
  explicit UTC offset. Orders the anchor by the instant it names (R43).

### `rate_code_register.csv`

- `rate_num`, `rate_den`: the exact editorial rate.
- `tc_base`: the whole frame numbers a second of timecode carries.
- `df_allowed`: whether drop frame labelling is permitted at that rate.
- `rounded_label`: the display label, matching `nominal_fps`.

### `segment_part_manifest.tsv`

- `part_no`: the transmission order of the part inside the asset.
- `part_kind`: one of `PT_BLACK`, `PT_BUMPER`, `PT_PROGRAMME`, `PT_PROMO`.
- `part_som_tc`, `part_eom_tc`: the part's own span, exclusive at the end,
  counted under the asset's drop frame flag (R40).

### `transmission_schedule.csv`

- `sched_start_tc`: the published channel timecode of the slot start,
  counted under the channel's drop frame behaviour (R40).
- `junction_kind`: `JK_FIXED` or `JK_FLOAT`.
- `flex_part_no`: the `part_no` of the slot's flexible tail element.
- `daypart_ref`: the slot's daypart.

### `break_plan_register.csv`

- `nominal_offset_seconds`: the break offset from the material start.
- `avail_seconds`: the commercial capacity of the break, in seconds.

### `gop_index_channel.psv`

- `idr_frame`: a channel frame the encoder marked, measured from the
  material start.

### `filler_library.csv`

- `predicate_order`: the order the filler predicates are walked in.
- `min_frames`, `max_frames`: the inclusive gap the filler covers.
- `stock_state`: one of `FS_AVAILABLE`, `FS_EMBARGOED`, `FS_EXPIRED`.

### `spot_order_book.jsonl`

- `break_ref`: the break the spot is sold against.
- `nominal_seconds`: the sold duration in whole seconds.
- `priority_band`: the admission band, lower is earlier.
- `separation_class`: the competitive grouping.
- `rate_card_ref`: the key into `rate_card_book.csv`.
- `clearance_ref`: the key into `clearance_state_journal.csv`.

### `rate_card_book.csv`

- `effective_from`: the calendar date the card takes effect, inclusive.
- `minor_per_grain`: the price of one billing grain in minor units.
- `card_revision`: the card's revision, a whole number (R39).

### `clearance_state_journal.csv`

- `journal_seq`: the sequence that settles the effective state, a whole
  number (R38).
- `logged_at`: backfilled, and not the ordering key.

### `blackout_rule_set.xml`

- `precedence`: ascending order of consideration.
- `override`: `yes` marks a rule that overturns everything before it.
- `window_from`, `window_to`: inclusive at both ends.
"""


def _doc_output_contract() -> str:
    return """# Output artifact contract

Twenty five artifacts are written into the output directory, plus the
reusable program. Every one of them is derived from this directory alone.

| artifact | format | stage |
|---|---|---|
| `asset_register.csv` | csv | V1 to V3 |
| `segment_conform.csv` | csv | V4 and V5 |
| `break_positions.csv` | csv | V6 |
| `slot_placement.csv` | csv | V7 and V8 |
| `conform_trace.json` | json | V8 |
| `filler_plan.csv` | csv | V8 |
| `avail_plan.tsv` | tsv | V9 |
| `deferral_ledger.jsonl` | jsonl | V9 |
| `market_overrides.csv` | csv | V10 |
| `market_avails_mk_coast.json` | json | V10 |
| `market_avails_mk_metro.json` | json | V10 |
| `market_avails_mk_north.json` | json | V10 |
| `market_avails_mk_valley.json` | json | V10 |
| `market_avail_stream.jsonl` | jsonl | V10 |
| `settlement_ledger.psv` | psv | V11 |
| `makegood_ledger.json` | json | V12 |
| `exception_ledger.jsonl` | jsonl | V11 |
| `advertiser_summary.csv` | csv | V11 and V12 |
| `minutage_report.csv` | csv | V13 |
| `carry_ledger.json` | json | V4 |
| `reconciliation.xml` | xml | V14 |
| `playout_schedule.ini` | ini | V7 and V8 |
| `day_report.md` | md | all |
| `compliance_summary.md` | md | V13 |
| `manifest.json` | json | V14 |

The reusable program is written as `conform.py` in the same directory. It
takes an optional `--data` directory and an optional `--out` directory on
the command line, defaults to the container paths when given neither, reads
nothing else, and writes exactly the twenty five artifacts above. It is run
against transmission days it has never seen, so nothing about this
particular day may be built into it.
"""


def _doc_output_schema() -> str:
    return """# Output schema reference

Column orders are exactly as published here. Delimited artifacts carry a
header row.

## `asset_register.csv`

`content_ref, canonical_ingest_id, revision_no, qc_state, rate_code,
rate_num, rate_den, tc_base, drop_frame, som_tc, eom_tc, source_frames,
channel_frames_exact, house_no, anchor_ingest_id, inclusion_state`

One row per cluster, ordered by `content_ref`. `drop_frame` is `yes` or
`no`. `channel_frames_exact` is a ratio to ten decimal places.
`som_tc` and `eom_tc` are the canonical attempt's labels exactly as the
ingest register records them, separator included.
`inclusion_state` is `AS_INCLUDED` or `AS_EXCLUDED`. An excluded row leaves
every field from `canonical_ingest_id` through `channel_frames_exact` empty
except `house_no` and `anchor_ingest_id`, which are always published.

## `segment_conform.csv`

`slot_id, content_ref, part_no, part_kind, retention_state, source_frames,
channel_frames_exact, channel_frames, carry_after`

One row per part of each placed slot, ordered by `slot_id` and then by
ascending `part_no`. `retention_state` is `PR_RETAINED`, `PR_TRIMMED_HEAD`
or `PR_TRIMMED_TAIL`. A trimmed part publishes `channel_frames` of `0` and
the unchanged `carry_after` of its scope.

## `break_positions.csv`

`slot_id, break_no, break_ref, nominal_offset_seconds, nominal_frame,
adjusted_target_frame, position_frame, snap_side, displacement_frames,
avail_seconds, carry_after`

One row per break of each placed slot, ordered by `slot_id` and then by
ascending `break_no`.

## `slot_placement.csv`

`slot_id, content_ref, sequence_no, junction_kind, sched_start_frame,
actual_start_frame, material_frames, trim_frames, transmitted_frames,
end_frame, drift_frames, hour_label, daypart_ref, placement_state`

One row per slot in the schedule, ordered by ascending `sequence_no` and
then by `slot_id`, so dropped slots with a sequence number of zero come
first.

`placement_state` is `PL_PLACED` for a placed slot and `PL_DROPPED` for a
dropped one, and the slot's element in `reconciliation.xml` carries the
same token. `drift_frames` is `actual_start_frame` less `sched_start_frame`.
`hour_label` is the clock hour that holds `actual_start_frame`, and is empty
for a dropped slot.

## `conform_trace.json`

An object with `corrections`, `totals`, `day_end_frame` and
`correction_count`. Each correction carries `sequence`, `slot_id`,
`reason`, `frames`, `detail_slot` and `filler_ref`. `totals` maps each
reason that occurred to its count. `day_end_frame` is the greatest
`end_frame` in `slot_placement.csv`, and `playout_schedule.ini`,
`day_report.md` and `manifest.json` publish the same value.

`slot_id` is the fixed junction the correction was made at, or the dropped
slot for `CR_SLOT_DROPPED`. `detail_slot` is the slot whose flexible part
gave up the frames for `CR_TRIM_FLEX` and `CR_TRIM_BACKFILL`, and is the
same slot as `slot_id` for every other reason. `filler_ref` is the chosen
filler for `CR_FILL_INSERT` and the empty string for every other reason.
The corrections of the placement walk come first, in the order the walk
made them, and the `CR_SLOT_DROPPED` corrections follow them in ascending
scheduled offset, ties by `slot_id`.

## `filler_plan.csv`

`slot_id, junction_offset_frame, gap_frames, filler_ref, daypart_ref,
selection_index`

One row per fill, ordered by `slot_id`.

## `avail_plan.tsv`

`market_ref, break_ref, break_position_frame, position_in_break, order_ref,
advertiser_ref, separation_class, spot_frames, start_frame, end_frame,
hour_label`

`hour_label` is the clock hour that holds the spot's `start_frame`. It
labels the spot; the advertising frames of each clock hour are counted as
`spec_stage_v13_minutage_compliance.md` sets out.

## `deferral_ledger.jsonl`

One object per line with `order_ref`, `market_ref`, `break_ref`,
`deferral_reason`, `predicate_index` and `spot_frames`.

## `market_overrides.csv`

`market_ref, slot_id, content_ref, rule_id, precedence, substitute_ref,
override_flag, national_break_count, substitute_break_count`

## The four per market avail files

An object with `market_ref`, `break_count`, `capacity_frames_total`,
`carry_residual_capacity`, `carry_residual_substitute` and `breaks`. Each
break carries `break_ref`, `slot_id`, `break_no`, `origin`,
`position_frame`, `capacity_frames`, `daypart_ref` and `hour_label`.
`origin` is `BO_NATIONAL` or `BO_SUBSTITUTE`.

## `market_avail_stream.jsonl`

One object per line, the union of the four market break lists with
`market_ref` added, ordered by market reference, then position frame, then
break reference.

## `settlement_ledger.psv`

`order_ref, advertiser_ref, market_ref, break_ref, currency,
delivered_frames, unbilled_frames, billable_grains, rate_card_ref,
effective_from, minor_per_grain, gross_minor, commission_minor, net_minor,
gross_major`

`unbilled_frames` is the whole number of the spot's frames that R41 left
unbilled, and `0` for a spot that lost none.

## `makegood_ledger.json`

An object with `advertisers`, `allocated_total_minor`, `cap_num` and
`cap_den`. Each advertiser entry carries `advertiser_ref`,
`day_gross_minor`, `cap_minor`, `raw_total_minor`, `allocated_total_minor`
and `obligations`. Each obligation carries `order_ref`, `deferral_reason`,
`raw_minor` and `allocated_minor`. The `deferral_reason` of an obligation an
admitted spot raised under R41 is `DF_OVER_CAP`.

## `exception_ledger.jsonl`

One object per line with `order_ref`, `exception_code`, `rate_card_ref` and
`detail`. The `detail` text is fixed per code and carries no other wording.
An `EX_ZERO_DELIVERY` record carries the detail `admitted spot occupies no
channel frame`. An `EX_NO_CARD` record carries the detail `earliest card
dated ` followed by the earliest `effective_from` of the order's rate card
reference, and an empty date when the book carries no row for that
reference at all.

## `advertiser_summary.csv`

`advertiser_ref, currency, admitted_spots, deferred_spots, delivered_frames,
gross_minor, commission_minor, net_minor, makegood_minor, gross_major`

## `minutage_report.csv`

`market_ref, hour_label, daypart_ref, advertising_frames,
advertising_seconds, cap_frames, headroom_frames, breach_state`

`advertising_seconds` is a ratio to ten decimal places. `breach_state` is
`MB_WITHIN` or `MB_BREACH`.

## `carry_ledger.json`

An object with `scopes`, `scope_count`, `conversion_count` and
`residual_total`. Each scope carries `scope`, `conversions` and `residual`,
ordered by scope name ascending. `residual` and `residual_total` are ratios
to ten decimal places.

## `reconciliation.xml`

A `reconciliation` root element with the attributes `channel_ref` and
`transmission_date`, then one `slot` element per slot ordered by `slot_id`,
then one `totals` element. Two space indent, one attribute set per line, and
one trailing line feed.

The first line is the declaration `<?xml version="1.0" encoding="UTF-8"?>`.
Each `slot` element is empty and carries these attributes in this order:
`slot_id`, `placement_state`, `prior_start_frame`, `start_frame`,
`start_delta`, `prior_material_frames`, `material_frames`,
`material_delta`, `prior_break_count`, `break_count` and `break_delta`. The
`totals` element is empty and carries `slots`, `agreeing`, `differing`,
`absolute_start_delta` and `absolute_material_delta` in that order. A slot
the prior register does not carry reads as a prior start frame, a prior
material frame count and a prior break count of zero. Every element sits on
its own line, attribute values are double quoted, and an empty element
closes with `/>` written directly after its last attribute.

## `playout_schedule.ini`

A `[channel]` section carrying `channel_ref`, `transmission_date`,
`day_start_tc`, `day_end_frame` and `placed_slot_count`, then one
slot section per placed slot in placement order, headed by the word slot
and a colon and the slot id inside square brackets, carrying
`content_ref`, `sequence_no`, `start_frame`, `start_tc`,
`transmitted_frames`, `trim_frames` and `break_count`. Keys are written as
`key = value`. Sections are separated by one blank line and the file ends
with one line feed.
`start_tc` is the channel drop frame timecode label of the slot's placed
start: the day start label plus `start_frame`, taken into one timecode day
and written `hh:mm:ss;ff`. Each section carries its keys in the order
listed above.

## `day_report.md`

Markdown, in this exact shape, with one blank line under every heading and
one blank line before the next heading.

The level one heading is `# Transmission day report`. Then a bullet list,
one figure per line written as `- key: value`, carrying `channel_ref`,
`transmission_date`, `instance_ref`, `live_control_set`, `scheduled_slots`,
`placed_slots`, `dropped_slots`, `day_end_frame`, `corrections`,
`admitted_spots`, `deferred_spots`, `gross_minor_total` and
`makegood_minor_total`, in that order. `live_control_set` here is the
`workbook_control_set` field of the channel configuration. `corrections` is
the correction count of `conform_trace.json`, and `gross_minor_total` is the
sum of the `gross_minor` column of `settlement_ledger.psv`.

Then the level two heading `## Correction totals` and one bullet per
correction reason written as `- reason: count`, covering every reason in
`correction_reason_reference.txt` in ascending reason order whether or not
it occurred.

Then the level two heading `## Deferral totals` and one bullet per deferral
reason written as `- reason: count`, covering every reason in
`deferral_reason_reference.txt` in ascending reason order whether or not it
occurred. Each count is the number of deferrals in `deferral_ledger.jsonl`
with that reason, except `DF_OVER_CAP`, which is never a deferral: its count
is the number of obligations in `makegood_ledger.json` with that reason.

## `compliance_summary.md`

Markdown, in this exact shape, with one blank line under every heading and
one blank line before the next heading.

The level one heading is `# Compliance summary`. Then a bullet list, one
figure per line written as `- key: value`, carrying
`regulatory_minutes_per_clock_hour`, `cap_frames`,
`separation_minimum_positions`, `billing_grain_seconds`,
`snap_tolerance_frames` and `breach_hours`, in that order. `cap_frames` is
the standing cap, the one the Section 1 figure gives, whatever Section 2
sets for single market hours. `breach_hours` is the number of rows of
`minutage_report.csv` whose breach state is `MB_BREACH`.

Then the level two heading `## Advertising frames by market` and one bullet
per market written as `- market_ref: frames`, ordered by market reference
ascending, where the count is that market's advertising frames summed over
the twenty four clock hours.

Then the level two heading `## Breach hours` and one bullet per breaching
row of `minutage_report.csv` in that file's order, written as
`- market_ref hour_label frames N over C` with `N` the advertising frames
and `C` the cap frames of that row. A day with no breaching hour publishes the single
bullet `- none`.

## `manifest.json`

An object carrying `instance_ref`, `channel_ref`, `transmission_date`,
`artifact_count`, `core_order`, `digest`, `slot_count`,
`placed_slot_count`, `dropped_slot_count`, `admitted_spot_count`,
`deferred_spot_count`, `breach_hour_count`, `live_control_set`,
`snap_tolerance_frames`, `makegood_cap_num`, `makegood_cap_den`,
`separation_minimum_positions`, `billing_grain_seconds`,
`regulatory_minutes_per_clock_hour` and `day_end_frame`.
`live_control_set` is the name of the workbook sheet the control set
selected.
"""


def _doc_serialisation() -> str:
    return """# Serialisation and digest contract

Bytes are graded, so serialisation is part of the answer.

## Every file

- utf-8, line feed endings, and exactly one trailing line feed.
- No byte order mark and no carriage returns.
- Ascii only. Nothing in this corpus needs anything else.

## Delimited files

- csv uses a comma, tsv uses a tab, psv uses a vertical bar.
- One header row carrying the column names in the published order.
- No quoting, no escaping and no spaces around a delimiter. No published
  value contains a delimiter.
- A file with no data rows is its header row and one line feed.

## json

- Two space indent, keys sorted at every level, ascii escaping, and one
  trailing line feed.

## jsonl

- One compact object per line, keys sorted, no spaces after the separators,
  and one trailing line feed.
- A ledger with no records is a single line feed.

## Numbers

- Every frame count, minor unit amount and count is a whole number written
  with no sign unless it is negative, no leading zero and no exponent.
- Every ratio is written to exactly ten decimal places, with halves going to
  the even value, no exponent and no negative zero.
- Rounding happens only when a value is written. No intermediate value is
  rounded anywhere in the pipeline.

## The core order

The digest in `manifest.json` runs over the concatenated bytes of these
seven artifacts in exactly this order:

  1. `asset_register.csv`
  2. `segment_conform.csv`
  3. `break_positions.csv`
  4. `slot_placement.csv`
  5. `avail_plan.tsv`
  6. `settlement_ledger.psv`
  7. `minutage_report.csv`

The digest is the lower case hexadecimal sha256 of that concatenation.
"""


def _yaml_ordering() -> str:
    return """# ordering_dependencies.yaml
# What each stage freezes, and what the next stage is not allowed to move.

day_start_tc: "06:00:00;00"
day_frames: "2589408"
frames_per_clock_hour: "107892"
channel_rate_num: "30000"
channel_rate_den: "1001"
channel_tc_base: "30"
channel_drop_frame: "yes"

frozen_at_v1:
  - "the canonical attempt of every asset"
  - "the anchor attempt of every asset"
  - "the excluded asset set"
frozen_at_v2:
  - "the editorial rate as an exact rational"
  - "the drop frame flag"
frozen_at_v3:
  - "the source frame span"
frozen_at_v4:
  - "the whole channel frame count of every part"
  - "the carry held by every scope"
frozen_at_v5:
  - "the material duration of every slot"
  - "the retention state of every part"
frozen_at_v6:
  - "the conditioned position of every national break"
frozen_at_v7:
  - "the order of the slots in the day"
  - "the scheduled offset of every junction"
frozen_at_v8:
  - "the trim of every slot"
  - "the placed start of every slot"
  - "the fills"
frozen_at_v9:
  - "the admitted spots and their positions"
  - "the deferrals and their reasons"
frozen_at_v10:
  - "the per market break set"
run_order:
  - "V1"
  - "V2"
  - "V3"
  - "V4"
  - "V5"
  - "V6"
  - "V7"
  - "V8"
  - "V10"
  - "V9"
  - "V13"
  - "V11"
  - "V12"
  - "V14"
frozen_at_v11:
  - "the gross, the commission and the net of every admitted spot"
frozen_at_v12:
  - "the make good allocation"
frozen_at_v13:
  - "the advertising frames of every market clock hour"
  - "the cap of every market clock hour"
  - "the unbilled frames of every admitted spot"
frozen_at_v14:
  - "the deltas against the prior register"
  - "the digest"

carry_scopes:
  - "V4 and the slot id"
  - "V6 and the slot id"
  - "V9 and the market ref"
  - "V10 and the market ref"
  - "V11 and the advertiser ref"
"""


def _yaml_rounding() -> str:
    return """# rounding_policy.yaml
# Where rounding is allowed to happen, and which way it goes.

intermediate_rounding: "forbidden"
arithmetic: "exact rational throughout"

conversion_into_channel_frames:
  rule: "floor, with the discarded fraction carried inside the named scope"
  direction: "toward minus infinity"
  applies_to:
    - "part spans at V4"
    - "break offsets at V6"
    - "break capacities at V9"
    - "substitute break offsets at V10"
    - "spot durations at V11"

billable_grains:
  rule: "ceiling of the billed frames over the frames one grain occupies"
  billed_frames: "delivered frames less the frames R41 left unbilled"
  exact_boundary: "bills that many grains and no more"

commission_minor_units:
  rule: "halves to even"

make_good_cap:
  rule: "floor"

make_good_allocation:
  rule: "largest remainder, ties by ascending order_ref"

regulatory_cap_frames:
  rule: "floor"

published_ratios:
  places: "10"
  rule: "halves to even"
  negative_zero: "forbidden"
"""


def _yaml_snap() -> str:
    return """# snap_policy.yaml
# The conditioning of a splice point against the index.

tolerance_source: "the settled sheet of contract_terms_workbook.xlsx"
tolerance_key: "snap_tolerance_frames"
tolerance_unit: "channel frames"

order:
  - "back to the greatest index frame at or below the target, when the gap is at most the tolerance"
  - "forward to the least index frame above the target"
  - "back to the greatest index frame at or below the target, whatever the gap"
  - "stay where it is, when the content carries no index frame"

sides:
  - "SNAP_EXACT"
  - "SNAP_BACK"
  - "SNAP_FORWARD"
  - "SNAP_NONE"

absorption:
  rule: "the last break of a slot aims at its nominal position less the sum of the earlier displacements in that slot"
  floor: "zero"
  single_break_slot: "nothing to absorb"

substitute_breaks:
  rule: "never snapped, because a substitute carries no index"
"""


def _yaml_junction() -> str:
    return """# junction_policy.yaml
# What a junction is allowed to do to the day.

fixed_junction:
  start: "always the scheduled offset"
  overrun: "trim flexible parts backwards to the previous fixed junction inclusive"
  underrun: "insert filler chosen by the first matching predicate"
  exact: "record CR_NO_CHANGE with zero frames"

float_junction:
  start: "the end of the slot before it"

trim_floor: "an empty flexible part"
trim_reason_immediate: "CR_TRIM_FLEX"
trim_reason_backwards: "CR_TRIM_BACKFILL"
trim_reason_residue: "CR_TRIM_SHORTFALL"
fill_reason: "CR_FILL_INSERT"
dropped_slot_reason: "CR_SLOT_DROPPED"

replacement_after_trim:
  rule: "the slots between the previous fixed junction and this one are re-placed from that junction start with their trimmed durations"

first_slot: "always a fixed junction"
"""


def _yaml_workbook() -> str:
    return """# workbook_sheet_rule.yaml
# Which sheet of the contract workbook is settled.

workbook: "contract_terms_workbook.xlsx"
sheet_count: "3"
selector_cell: "the first cell pair of row one"
selector_key: "control_set"
selector_source: "workbook_control_set in channel_config.json"

rule: "the settled sheet is the one whose control set cell equals the configured control set"
name_meaning: "none, the revision in the sheet name carries no settlement meaning"
position_meaning: "none, the position of the settled sheet varies by instance"
superseded_sheets: "the other two carry terms of their own, so either of them is wrong"

# R42 cell values
cell_values:
  stored_as: "a number, or a shared string"
  rich_text: "a shared string may be split into several formatted runs; its value is the concatenation of every run, in order"
  example: "a value of 57 keyed with a bold first digit is stored as the runs 5 and 7, and its value is 57"

scalar_rows:
  - "snap_tolerance_frames"
  - "makegood_cap_num"
  - "makegood_cap_den"

commission_rows:
  first_cell: "COMMISSION"
  advertiser_cell: "the second cell"
  numerator_cell: "the fourth cell"
  denominator_cell: "the fifth cell"

other_rows:
  - "FEE rows are traffic handling fees and are not read by any stage"
  - "CLEARANCE rows are clearance surcharge shares and are not read by any stage"
  - "FEED rows are feed loading shares and are not read by any stage"
"""


def _txt_reasons() -> str:
    return """deferral reason reference

The first seven entries are the reasons a spot can be deferred at V9, in the
order the predicates are evaluated; a deferral's predicate_index is the one
based position of its reason among these seven. The eighth entry is not an
admission predicate and V9 never defers a spot with it.

DF_CLEARANCE_HELD
    The effective clearance state of the order is CL_HELD. The effective
    state is the row of the clearance journal with the greatest journal_seq.

DF_MARKET_BLACKED
    The slot the break belongs to is substituted in this market, so the
    national break the order was sold against is not transmitted there.

DF_NO_MATCHING_BREAK
    The order's break reference is not in this market's break set at all.

DF_DAYPART_MISMATCH
    The order's daypart differs from the daypart of the break it is sold
    against.

DF_NO_RATE_CARD
    No row of the rate card book carrying the order's rate card reference is
    effective on or before the transmission date.

DF_BREAK_FULL
    Admitting the spot would put the break's admitted frames above its
    capacity.

DF_SEPARATION
    An already admitted spot in the same break carries the same separation
    class and sits fewer than the separation minimum positions away.

DF_OVER_CAP
    Not an admission predicate. The reason V12 records on the make good
    obligation it raises for an admitted spot whose billable grains were cut
    because its frames went unbilled above the regulatory cap of a clock
    hour (V13, R41).
"""


def _txt_snap_sides() -> str:
    return """snap side reference

SNAP_EXACT
    The snapped position equals the position the break was aiming at,
    because an index frame sits exactly there.

SNAP_BACK
    The break moved back to an index frame below the position it was aiming
    at. This is the ordinary case within the tolerance, and it is also the
    case when no index frame exists above the target.

SNAP_FORWARD
    The break moved forward to the least index frame above the position it
    was aiming at, because the nearest index frame below it was further away
    than the tolerance allows.

SNAP_NONE
    The content carries no index frame at all, so the break stays at the
    position it was aiming at.
"""


def _txt_corrections() -> str:
    return """correction reason reference

CR_NO_CHANGE
    A fixed junction the running cursor reached exactly. Recorded with zero
    frames.

CR_TRIM_FLEX
    Frames trimmed from the flexible part of the slot immediately before an
    overrunning fixed junction.

CR_TRIM_BACKFILL
    Frames trimmed from the flexible part of a slot further back than the
    one immediately before the junction, during the same backward walk.

CR_TRIM_SHORTFALL
    The residue of an overrun that the whole backward walk could not remove.
    The junction is pinned anyway.

CR_FILL_INSERT
    Filler inserted before a fixed junction the running cursor reached
    early. The frame count is the gap.

CR_SLOT_DROPPED
    A slot whose asset has no canonical ingest attempt. It occupies no time.
"""


def _txt_field_order() -> str:
    return """field order reference

The column order of every delimited artifact, one per line, so that no
artifact is written with its columns in a different order.

asset_register.csv
    content_ref canonical_ingest_id revision_no qc_state rate_code rate_num
    rate_den tc_base drop_frame som_tc eom_tc source_frames
    channel_frames_exact house_no anchor_ingest_id inclusion_state

segment_conform.csv
    slot_id content_ref part_no part_kind retention_state source_frames
    channel_frames_exact channel_frames carry_after

break_positions.csv
    slot_id break_no break_ref nominal_offset_seconds nominal_frame
    adjusted_target_frame position_frame snap_side displacement_frames
    avail_seconds carry_after

slot_placement.csv
    slot_id content_ref sequence_no junction_kind sched_start_frame
    actual_start_frame material_frames trim_frames transmitted_frames
    end_frame drift_frames hour_label daypart_ref placement_state

filler_plan.csv
    slot_id junction_offset_frame gap_frames filler_ref daypart_ref
    selection_index

avail_plan.tsv
    market_ref break_ref break_position_frame position_in_break order_ref
    advertiser_ref separation_class spot_frames start_frame end_frame
    hour_label

market_overrides.csv
    market_ref slot_id content_ref rule_id precedence substitute_ref
    override_flag national_break_count substitute_break_count

settlement_ledger.psv
    order_ref advertiser_ref market_ref break_ref currency delivered_frames
    unbilled_frames billable_grains rate_card_ref effective_from
    minor_per_grain gross_minor commission_minor net_minor gross_major

advertiser_summary.csv
    advertiser_ref currency admitted_spots deferred_spots delivered_frames
    gross_minor commission_minor net_minor makegood_minor gross_major

minutage_report.csv
    market_ref hour_label daypart_ref advertising_frames advertising_seconds
    cap_frames headroom_frames breach_state
"""


def _doc_runbook() -> str:
    return """# Operations runbook

Notes the playout desk keeps. Nothing here overrides a stage specification.

## Why the day starts at six

The channel hands over to the network at six in the morning, so the
operational day and the regulatory day both open there. The consequence
people forget is that a slot labelled `02:30:00;00` is at the end of the
day and not at the start of it, and that the clock hours `H24` to `H29` are
the small hours of the following calendar date.

## Why the rate is a fraction

The channel is a `30000/1001` service. Nothing in this house is `29.97`.
The traffic system prints `29.97` on its screens and that label has leaked
into the ingest register as `nominal_fps`, which is why the register
carries a rate code as well.

## Why there is a carry

A minute of `25` frames per second material is `1500` source frames and
`1798.2018` channel frames. Rounding each part to nearest loses a frame
every few parts and the slot drifts. The carry keeps the drift where it
belongs, which is inside the slot, and publishes what is left over.

## Why the last break moves

Splices have to land on an index frame, and the index does not care where
the break plan wanted the break. If every break in a slot moves independently
the slot ends in the wrong place and the whole rest of the day moves with
it. The last break carries the accumulated displacement back so that the
slot ends where the schedule says it ends.

## Why the workbook has three sheets

Contract terms are agreed two quarters ahead and a withdrawn revision stays
on the books for audit, so at any moment there are three sets in the
workbook and only one of them is settled. The configuration names the
settled control set. Reading either of the other two gives a snap tolerance
that is close enough to look right and a commission that is wrong, and the
two of them are wrong in different directions.

## Why the prior register is here

The old conform ran before the index was published and before the carry rule
was written down. It is kept so that the recomputation can be reported
against it. It is not an input.
"""


def _doc_governance() -> str:
    return """# Governance and revision notes

## Control sets

Contract terms are published as control sets. Three sets sit in the workbook
at any time and `channel_config.json` names the one that is settled. The
sheet names carry a revision label but the label is not the selector: a
sheet named with a higher revision is not necessarily the settled one,
because a revision can be raised and then withdrawn. The two superseded
sheets carry terms of their own, so reaching for either of them gives a snap
tolerance and a commission that look plausible and are wrong.

## The memorandum

The compliance memorandum is issued per transmission date and it is the only
publication of the separation minimum, the billing grain and the regulatory
minutes per clock hour. Those three constants are not repeated anywhere else
in this directory, by design, so that a change to them cannot be missed.
The memorandum also lists permitted minutes per market and clock hour in its
Section 2. Where that list departs from the standing figure for a market
hour, the list governs that hour (V13, R37).

## The rate register

Rate codes are added but never changed. `df_allowed` is a property of the
rate and is not negotiable per asset. Attempts that claim drop frame on a
rate that does not permit it are a known defect of one ingest station and
are corrected at V2 rather than in the register.

## The draft overlay

`blackout_overlay_drafts.xml` was prepared for a legal review that did not
complete. Its root element carries the status `draft-superseded`. It is kept
for audit and it is not read.

## The legacy commission table

Commission moved from a percentage of gross to an exact fraction when the
minor unit rounding was written down. `legacy_commission_table.csv` is the
old schedule and is kept for audit.
"""


def _doc_faq() -> str:
    return """# Operator questions

**Does an excluded asset still get a row in the asset register?**
Yes. It is published with the inclusion state `AS_EXCLUDED`, with its house
number and its anchor, and with every derived field empty.

**Which attempt supplies the house number?**
The anchor, which is the first received attempt. Not the canonical attempt.

**Is the end of media timecode inclusive?**
No. An asset whose start and end labels are equal spans zero frames.

**What happens when the end label is earlier than the start label?**
The asset wraps the timecode day and one whole timecode day is added to the
difference.

**Does a trimmed black part consume carry?**
No. It makes no conversion, so the scope's held fraction is unchanged and
the part publishes the fraction that was already held.

**Can a break snap outside the material?**
It can snap forward past the material end when the index runs that far. The
index is published for the content and the conditioning does not clip it.

**Does a deferred spot use capacity?**
No. It consumes no capacity and takes no position in the break.

**Can a spot be moved to a different break?**
No. A spot is sold against one break and is either admitted there or
deferred.

**Which currencies have an exponent that is not two?**
The exponent table publishes them. One of the four settlement currencies has
an exponent of zero and one has an exponent of three.

**Is an hour that lands exactly on the cap a breach?**
No. A breach is strictly above the cap.

**Is a rate card dated exactly on the transmission date eligible?**
Yes. The rule is on or before.

**Is a blackout window inclusive at both ends?**
Yes.
"""


def _worked_records() -> list:
    return [
        {"vector": "timecode_ndf", "note": "base 25, non drop",
         "input": "01:00:00:00", "frames": 90000},
        {"vector": "timecode_df", "note": "base 30, drop frame, the minute "
                                          "where frame numbers are skipped",
         "input": "00:01:00;02", "frames": 1800},
        {"vector": "timecode_df_tenth", "note": "base 30, drop frame, the "
                                                "tenth minute skips nothing",
         "input": "00:10:00;00", "frames": 17982},
        {"vector": "day_start", "note": "the broadcast day start in channel "
                                        "timecode frames",
         "input": "06:00:00;00", "frames": 647352},
    ]


def _unit_vectors() -> dict:
    return {
        "channel": {"rate_num": 30000, "rate_den": 1001, "tc_base": 30,
                    "drop_frame": True, "day_frames": 2589408,
                    "frames_per_clock_hour": 107892,
                    "day_start_frames": 647352},
        "rate_conversion": [
            {"source_frames": 1500, "rate_num": 25, "rate_den": 1,
             "channel_frames_exact": "1798.2017982018"},
            {"source_frames": 1000, "rate_num": 24000, "rate_den": 1001,
             "channel_frames_exact": "1250.0000000000"},
            {"source_frames": 1000, "rate_num": 60000, "rate_den": 1001,
             "channel_frames_exact": "500.0000000000"},
            {"source_frames": 1000, "rate_num": 30, "rate_den": 1,
             "channel_frames_exact": "999.0009990010"},
        ],
        "seconds_conversion": [
            {"seconds": 30, "channel_frames_exact": "899.1008991009"},
            {"seconds": 60, "channel_frames_exact": "1798.2017982018"},
            {"seconds": 720, "channel_frames_exact": "21578.4215784216",
             "floored": 21578},
        ],
        "drop_frame_examples": [
            {"timecode": "00:00:59;29", "base": 30, "frames": 1799},
            {"timecode": "00:01:00;02", "base": 30, "frames": 1800},
            {"timecode": "00:09:59;29", "base": 30, "frames": 17981},
            {"timecode": "00:10:00;00", "base": 30, "frames": 17982},
            {"timecode": "01:00:00;00", "base": 30, "frames": 107892},
        ],
    }


def _documents(profile: str) -> dict:
    return {
        "readme_first.txt": _txt_readme(),
        "pipeline_contract_overview.md": _doc_overview(),
        "spec_stage_v1_asset_canonicalisation.md": _doc_v1(),
        "spec_stage_v2_rate_resolution.md": _doc_v2(),
        "spec_stage_v3_source_span.md": _doc_v3(),
        "spec_stage_v4_channel_conversion.md": _doc_v4(),
        "spec_stage_v5_segment_assembly.md": _doc_v5(),
        "spec_stage_v6_splice_conditioning.md": _doc_v6(),
        "spec_stage_v7_schedule_placement.md": _doc_v7(),
        "spec_stage_v8_drift_correction.md": _doc_v8(),
        "spec_stage_v9_avail_derivation.md": _doc_v9(),
        "spec_stage_v10_market_substitution.md": _doc_v10(),
        "spec_stage_v11_settlement.md": _doc_v11(),
        "spec_stage_v12_make_good.md": _doc_v12(),
        "spec_stage_v13_minutage_compliance.md": _doc_v13(),
        "spec_stage_v14_reconciliation.md": _doc_v14(),
        "data_lineage.md": _doc_lineage(),
        "glossary_and_field_dictionary.md": _doc_glossary(),
        "output_artifact_contract.md": _doc_output_contract(),
        "output_schema_reference.md": _doc_output_schema(),
        "serialisation_and_digest_contract.md": _doc_serialisation(),
        "ordering_dependencies.yaml": _yaml_ordering(),
        "rounding_policy.yaml": _yaml_rounding(),
        "snap_policy.yaml": _yaml_snap(),
        "junction_policy.yaml": _yaml_junction(),
        "workbook_sheet_rule.yaml": _yaml_workbook(),
        "deferral_reason_reference.txt": _txt_reasons(),
        "snap_side_reference.txt": _txt_snap_sides(),
        "correction_reason_reference.txt": _txt_corrections(),
        "field_order_reference.txt": _txt_field_order(),
        "operations_runbook.md": _doc_runbook(),
        "governance_and_revision_notes.md": _doc_governance(),
        "operator_questions.md": _doc_faq(),
    }


# ==========================================================================
# the reference pipeline
#
# Every hidden decision sits behind a named rule id. Passing a rule id in
# `off` reverts that one decision to the reading a fluent implementer would
# reach for, and nothing else changes. That is what makes the per rule
# revert gate and the naive detectors possible.
# ==========================================================================

def _on(off, rule: str) -> bool:
    return rule not in off


def _int(text, default=0) -> int:
    text = str(text).strip()
    if text == "":
        return default
    return int(text)


def load_inputs(data_dir, off=frozenset()) -> dict:
    d = Path(data_dir)
    cfg = read_json(d / "channel_config.json")
    rates = {r["rate_code"]: r for r in read_delim(d / "rate_code_register.csv")}
    inp = {
        "config": cfg,
        "rates": rates,
        "ingest": read_delim(d / "ingest_attempt_register.csv"),
        "parts": read_delim(d / "segment_part_manifest.tsv", "\t"),
        "gop": read_delim(d / "gop_index_channel.psv", "|"),
        "breaks": read_delim(d / "break_plan_register.csv"),
        "schedule": read_delim(d / "transmission_schedule.csv"),
        "fillers": read_delim(d / "filler_library.csv"),
        "orders": read_lines_json(d / "spot_order_book.jsonl"),
        "advertisers": read_delim(d / "advertiser_register.csv"),
        "cards": read_delim(d / "rate_card_book.csv"),
        "clearance": read_delim(d / "clearance_state_journal.csv"),
        "markets": read_delim(d / "market_register.csv"),
        "substitutes": read_delim(d / "substitution_library.csv"),
        "prior": read_delim(d / "prior_conform_register.csv"),
        "legacy": read_delim(d / "legacy_commission_table.csv"),
        "exponents": read_json(d / "currency_minor_units.json")["exponents"],
        "dayparts": read_delim(d / "daypart_calendar.csv"),
        "tx_date": parse_date(cfg["transmission_date"]),
    }

    root = read_xml_root(d / "blackout_rule_set.xml")
    inp["blackouts"] = [dict(node.attrib) for node in root.findall("rule")]

    sheets = read_xlsx_sheets(d / "contract_terms_workbook.xlsx", off)
    inp["live_sheet_name"], live = _select_sheet(sheets, cfg, off)
    inp["sheet_scalars"] = _sheet_scalars(live)
    inp["commission"] = _sheet_commission(live)

    memo = read_pdf_lines(d / "regulatory_minutage_memo.pdf")
    inp["memo_scalars"] = {
        key: _int(pdf_scalar(memo, key))
        for key in ("separation_minimum_positions", "billing_grain_seconds",
                    "regulatory_minutes_per_clock_hour")
    }
    inp["memo_minutes"] = _memo_section2(memo)
    return inp


def _memo_section2(lines: list) -> dict:
    """R37: the permitted minutes Section 2 lists per market and clock hour."""
    out = {}
    inside = False
    for line in lines:
        if line.startswith("SECTION 2 "):
            inside = True
            continue
        if inside and line.startswith("SECTION "):
            break
        if not inside:
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) != 4 or cells[0] == "market_ref":
            continue
        out[(cells[0], cells[1])] = _int(cells[2])
    return out


def _select_sheet(sheets: dict, cfg: dict, off) -> tuple:
    """The live sheet is the one whose control set cell matches the field the
    channel configuration publishes. The sheet name settles nothing."""
    names = list(sheets)
    wanted = str(cfg["workbook_control_set"])
    if not _on(off, "R07"):
        # The reverted reading takes a sheet without consulting the control
        # set cell, which is what taking the workbook by position or by
        # revision label amounts to on every instance where the position
        # guessed is not this instance's. Picking a sheet that is definitely
        # not the settled one keeps this revert live on every instance
        # rather than only on the instances a fixed position happens to miss.
        wrong = [n for n in names
                 if not (sheets[n] and len(sheets[n][0]) >= 2
                         and sheets[n][0][0] == "control_set"
                         and sheets[n][0][1] == wanted)]
        return wrong[0], sheets[wrong[0]]
    for name in names:
        rows = sheets[name]
        if rows and len(rows[0]) >= 2 and rows[0][0] == "control_set" \
                and rows[0][1] == wanted:
            return name, rows
    raise KeyError("no workbook sheet carries control set " + wanted)


def _sheet_scalars(rows: list) -> dict:
    out = {}
    for row in rows:
        if len(row) >= 2 and row[0] in ("snap_tolerance_frames",
                                        "makegood_cap_num", "makegood_cap_den"):
            out[row[0]] = _int(row[1])
    return out


def _sheet_commission(rows: list) -> dict:
    out = {}
    for row in rows:
        if len(row) >= 5 and row[0] == "COMMISSION":
            out[row[1]] = (_int(row[3]), _int(row[4]))
    return out


# --------------------------------------------------------------------------
# V1  asset canonicalisation
# --------------------------------------------------------------------------
def _instant(text: str) -> datetime:
    """R43: an arrival time names an instant through its UTC offset."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def stage_v1(inp: dict, off) -> dict:
    key_field = "content_ref" if _on(off, "R01") else "ingest_id"
    clusters: dict = {}
    for row in inp["ingest"]:
        clusters.setdefault(row[key_field], []).append(row)

    canonical: dict = {}
    anchor: dict = {}
    included = []
    excluded = []
    for key in sorted(clusters):
        rows = clusters[key]
        if _on(off, "R43"):
            anchor[key] = sorted(rows, key=lambda r: (_instant(r["received_at"]),
                                                      r["ingest_id"]))[0]
        else:
            anchor[key] = sorted(rows, key=lambda r: (r["received_at"], r["ingest_id"]))[0]
        pool = rows if not _on(off, "R02") else [
            r for r in rows if r["qc_state"] in QC_PASSED_SET]
        if not pool:
            excluded.append(key)
            continue
        best = pool[0]
        for row in pool[1:]:
            a, b = _int(row["revision_no"]), _int(best["revision_no"])
            if a > b:
                best = row
            elif a == b:
                if _on(off, "R03"):
                    if row["ingest_id"] < best["ingest_id"]:
                        best = row
                elif row["ingest_id"] > best["ingest_id"]:
                    best = row
        canonical[key] = best
        if not _on(off, "R04"):
            anchor[key] = best
        included.append(key)
    return {"canonical": canonical, "anchor": anchor,
            "included": included, "excluded": excluded,
            "keys": sorted(clusters)}


# --------------------------------------------------------------------------
# V2  rate resolution   V3  source span
# --------------------------------------------------------------------------
def asset_rate(inp: dict, row: dict, off) -> tuple:
    """The editorial rate as an exact rational, the timecode base, and
    whether drop frame labelling applies to this attempt."""
    code = row["rate_code"]
    reg = inp["rates"][code]
    if _on(off, "R05"):
        num, den = _int(reg["rate_num"]), _int(reg["rate_den"])
    else:
        text = row["nominal_fps"]
        whole, _, frac = text.partition(".")
        num = _int(whole) * 100 + _int(frac or "0")
        den = 100
    tc_base = _int(reg["tc_base"])
    if _on(off, "R06"):
        df = (row["tc_mode"] == "DF" and reg["df_allowed"] == "yes")
    else:
        df = (row["tc_mode"] == "DF")
    return num, den, tc_base, df


def tc_span(tc_base: int, df: bool) -> int:
    if df:
        return tc_base * 86400 - drop_per_minute(tc_base) * (1440 - 144)
    return tc_base * 86400


def _label_df(label: str, df: bool, off) -> bool:
    """R40: a label is read under the drop frame flag of its asset or of the
    channel. The separator it was keyed with is not evidence of either."""
    if _on(off, "R40"):
        return df
    return ";" in label


def source_span(inp: dict, row: dict, som: str, eom: str, off) -> tuple:
    num, den, tc_base, df = asset_rate(inp, row, off)
    a = tc_to_frames(som, tc_base, _label_df(som, df, off))
    b = tc_to_frames(eom, tc_base, _label_df(eom, df, off))
    n = b - a
    if n < 0 and _on(off, "R08"):
        n += tc_span(tc_base, df)
    return n, num, den, tc_base, df


def stage_v23(inp: dict, v1: dict, off) -> dict:
    assets = {}
    rows = []
    for key in v1["keys"]:
        anchor = v1["anchor"][key]
        canon = v1["canonical"].get(key)
        if canon is None:
            rows.append({
                "content_ref": key, "canonical_ingest_id": "", "revision_no": "",
                "qc_state": "", "rate_code": "", "rate_num": "", "rate_den": "",
                "tc_base": "", "drop_frame": "", "som_tc": "", "eom_tc": "",
                "source_frames": "", "channel_frames_exact": "",
                "house_no": anchor["house_no"],
                "anchor_ingest_id": anchor["ingest_id"],
                "inclusion_state": "AS_EXCLUDED",
            })
            continue
        n, num, den, tc_base, df = source_span(
            inp, canon, canon["som_tc"], canon["eom_tc"], off)
        exact = rate_convert(n, num, den)
        assets[key] = {"canon": canon, "num": num, "den": den,
                       "tc_base": tc_base, "df": df, "source_frames": n,
                       "exact": exact, "house_no": anchor["house_no"]}
        rows.append({
            "content_ref": key,
            "canonical_ingest_id": canon["ingest_id"],
            "revision_no": canon["revision_no"],
            "qc_state": canon["qc_state"],
            "rate_code": canon["rate_code"],
            "rate_num": str(num), "rate_den": str(den),
            "tc_base": str(tc_base),
            "drop_frame": "yes" if df else "no",
            "som_tc": canon["som_tc"], "eom_tc": canon["eom_tc"],
            "source_frames": str(n),
            "channel_frames_exact": ratio(exact),
            "house_no": anchor["house_no"],
            "anchor_ingest_id": anchor["ingest_id"],
            "inclusion_state": "AS_INCLUDED",
        })
    return {"assets": assets, "rows": rows}


# --------------------------------------------------------------------------
# V4  channel conversion   V5  segment assembly
# --------------------------------------------------------------------------
def stage_v45(inp: dict, v23: dict, slots: list, carry: Carry, off) -> dict:
    by_ref: dict = {}
    for row in inp["parts"]:
        by_ref.setdefault(row["content_ref"], []).append(row)

    rows = []
    material: dict = {}
    flex: dict = {}
    for slot in slots:
        slot_id = slot["slot_id"]
        content_ref = slot["content_ref"]
        asset = v23["assets"].get(content_ref)
        scope = "V4:" + slot_id
        carry.open(scope)
        if asset is None:
            material[slot_id] = 0
            flex[slot_id] = 0
            continue
        parts = sorted(by_ref.get(content_ref, []),
                       key=lambda r: _int(r["part_no"]))
        if not parts:
            if _on(off, "R13"):
                parts = [{"content_ref": content_ref, "part_no": "0",
                          "part_kind": "PT_PROGRAMME",
                          "part_som_tc": asset["canon"]["som_tc"],
                          "part_eom_tc": asset["canon"]["eom_tc"]}]
            else:
                material[slot_id] = 0
                flex[slot_id] = 0
                continue
        states = _retention(parts, off)
        total = 0
        flex_frames = 0
        for part, state in zip(parts, states):
            a = tc_to_frames(part["part_som_tc"], asset["tc_base"],
                             _label_df(part["part_som_tc"], asset["df"], off))
            b = tc_to_frames(part["part_eom_tc"], asset["tc_base"],
                             _label_df(part["part_eom_tc"], asset["df"], off))
            n = b - a
            if n < 0 and _on(off, "R08"):
                n += tc_span(asset["tc_base"], asset["df"])
            exact = rate_convert(n, asset["num"], asset["den"])
            if state == "PR_RETAINED":
                frames = carry.convert(exact, scope)
                total += frames
                if part["part_no"] == slot["flex_part_no"]:
                    flex_frames = frames
            else:
                frames = 0
            rows.append({
                "slot_id": slot_id,
                "content_ref": content_ref,
                "part_no": part["part_no"],
                "part_kind": part["part_kind"],
                "retention_state": state,
                "source_frames": str(n),
                "channel_frames_exact": ratio(exact),
                "channel_frames": str(frames),
                "carry_after": ratio(carry.close(scope)),
            })
        material[slot_id] = total
        flex[slot_id] = flex_frames
    return {"rows": rows, "material": material, "flex": flex}


def _retention(parts: list, off) -> list:
    """Black at the head or the tail of the part sequence is trimmed. Black
    between two other parts is transmitted."""
    n = len(parts)
    states = ["PR_RETAINED"] * n
    if not _on(off, "R12"):
        for i, part in enumerate(parts):
            if part["part_kind"] == "PT_BLACK":
                states[i] = "PR_TRIMMED_HEAD"
        return states
    i = 0
    while i < n and parts[i]["part_kind"] == "PT_BLACK":
        states[i] = "PR_TRIMMED_HEAD"
        i += 1
    j = n - 1
    while j >= i and parts[j]["part_kind"] == "PT_BLACK":
        states[j] = "PR_TRIMMED_TAIL"
        j -= 1
    return states


# --------------------------------------------------------------------------
# V6  splice conditioning
# --------------------------------------------------------------------------
def _snap(target: int, idrs: list, tol: int, off) -> tuple:
    if not idrs:
        return target, "SNAP_NONE"
    back = None
    fwd = None
    for frame in idrs:
        if frame <= target:
            back = frame
        elif fwd is None:
            fwd = frame
    if not _on(off, "R14"):
        cands = [c for c in (back, fwd) if c is not None]
        pos = min(cands, key=lambda c: (abs(c - target), c))
    elif back is not None and target - back <= tol:
        pos = back
    elif fwd is not None:
        pos = fwd
    elif back is not None:
        pos = back
    else:
        pos = target
    if pos == target:
        return pos, "SNAP_EXACT"
    return pos, ("SNAP_BACK" if pos < target else "SNAP_FORWARD")


def stage_v6(inp: dict, v23: dict, slots: list, carry: Carry, off) -> dict:
    idr_by_ref: dict = {}
    for row in inp["gop"]:
        idr_by_ref.setdefault(row["content_ref"], []).append(_int(row["idr_frame"]))
    for key in idr_by_ref:
        idr_by_ref[key] = sorted(idr_by_ref[key])
    by_slot: dict = {}
    for row in inp["breaks"]:
        by_slot.setdefault(row["slot_id"], []).append(row)

    tol = inp["sheet_scalars"]["snap_tolerance_frames"]
    rows = []
    positions: dict = {}
    for slot in slots:
        slot_id = slot["slot_id"]
        scope = "V6:" + slot_id
        carry.open(scope)
        breaks = sorted(by_slot.get(slot_id, []), key=lambda r: _int(r["break_no"]))
        idrs = idr_by_ref.get(slot["content_ref"], [])
        displaced = 0
        out = []
        for i, brk in enumerate(breaks):
            nominal = carry.convert(
                seconds_to_frames(_int(brk["nominal_offset_seconds"])), scope)
            target = nominal
            if i == len(breaks) - 1 and _on(off, "R15"):
                target = max(0, nominal - displaced)
            pos, side = _snap(target, idrs, tol, off)
            displaced += pos - nominal
            break_ref = "bk_%s_%02d" % (slot_id, _int(brk["break_no"]))
            out.append({"break_ref": break_ref, "break_no": _int(brk["break_no"]),
                        "position": pos,
                        "avail_seconds": _int(brk["avail_seconds"])})
            rows.append({
                "slot_id": slot_id,
                "break_no": brk["break_no"],
                "break_ref": break_ref,
                "nominal_offset_seconds": brk["nominal_offset_seconds"],
                "nominal_frame": str(nominal),
                "adjusted_target_frame": str(target),
                "position_frame": str(pos),
                "snap_side": side,
                "displacement_frames": str(pos - nominal),
                "avail_seconds": brk["avail_seconds"],
                "carry_after": ratio(carry.close(scope)),
            })
        positions[slot_id] = out
    return {"rows": rows, "positions": positions}


# --------------------------------------------------------------------------
# V7  placement   V8  drift correction
# --------------------------------------------------------------------------
def sched_offset(tc: str, off) -> int:
    frames = tc_to_frames(tc, CH_BASE, _label_df(tc, CH_DF, off))
    if not _on(off, "R16"):
        return frames
    start = tc_to_frames(DAY_START_TC, CH_BASE, CH_DF)
    if frames < start:
        return frames + DAY_FRAMES - start
    return frames - start


def _hour_label(frame: int) -> str:
    idx = frame // FRAMES_PER_HOUR
    if idx < 0:
        idx = 0
    if idx > 23:
        idx = 23
    return "H%02d" % (6 + idx)


def _pick_filler(inp: dict, gap: int, daypart: str, off) -> tuple:
    rows = sorted(inp["fillers"], key=lambda r: _int(r["predicate_order"]))
    hits = []
    for row in rows:
        if row["stock_state"] != "FS_AVAILABLE":
            continue
        if row["daypart_ref"] not in (daypart, "DP_ANY"):
            continue
        if not (_int(row["min_frames"]) <= gap <= _int(row["max_frames"])):
            continue
        hits.append(row)
    if not hits:
        return inp["config"]["house_filler_ref"], 0
    row = hits[0] if _on(off, "R19") else hits[-1]
    return row["filler_ref"], _int(row["predicate_order"])


def stage_v78(inp: dict, v23: dict, v45: dict, v6: dict, slots: list, off) -> dict:
    n = len(slots)
    material = [v45["material"].get(s["slot_id"], 0) for s in slots]
    flex = [v45["flex"].get(s["slot_id"], 0) for s in slots]
    trim = [0] * n
    starts = [0] * n
    corrections = []
    fills = []
    cursor = 0
    prev_fixed = -1
    for i, slot in enumerate(slots):
        target = sched_offset(slot["sched_start_tc"], off)
        if slot["junction_kind"] != "JK_FIXED":
            starts[i] = cursor
            cursor = starts[i] + material[i] - trim[i]
            continue
        if cursor > target:
            rem = cursor - target
            lo = prev_fixed if prev_fixed >= 0 else 0
            if _on(off, "R18"):
                for j in range(i - 1, lo - 1, -1):
                    available = flex[j] - trim[j]
                    take = available if available < rem else rem
                    if take > 0:
                        trim[j] += take
                        rem -= take
                        corrections.append({
                            "slot_id": slot["slot_id"],
                            "reason": "CR_TRIM_FLEX" if j == i - 1 else "CR_TRIM_BACKFILL",
                            "frames": take,
                            "detail_slot": slots[j]["slot_id"],
                            "filler_ref": "",
                        })
                    if rem == 0:
                        break
            if rem > 0:
                corrections.append({
                    "slot_id": slot["slot_id"], "reason": "CR_TRIM_SHORTFALL",
                    "frames": rem, "detail_slot": slot["slot_id"],
                    "filler_ref": "",
                })
            base = starts[lo] if prev_fixed >= 0 else 0
            run = base
            for j in range(lo, i):
                starts[j] = run
                run += material[j] - trim[j]
        elif cursor < target:
            gap = target - cursor
            filler_ref, index = _pick_filler(inp, gap, slot["daypart_ref"], off)
            corrections.append({
                "slot_id": slot["slot_id"], "reason": "CR_FILL_INSERT",
                "frames": gap, "detail_slot": slot["slot_id"],
                "filler_ref": filler_ref,
            })
            fills.append({
                "slot_id": slot["slot_id"],
                "junction_offset_frame": str(target),
                "gap_frames": str(gap),
                "filler_ref": filler_ref,
                "daypart_ref": slot["daypart_ref"],
                "selection_index": str(index),
            })
        else:
            corrections.append({
                "slot_id": slot["slot_id"], "reason": "CR_NO_CHANGE",
                "frames": 0, "detail_slot": slot["slot_id"], "filler_ref": "",
            })
        starts[i] = target
        cursor = target + material[i] - trim[i]
        prev_fixed = i

    placed = []
    for i, slot in enumerate(slots):
        transmitted = material[i] - trim[i]
        placed.append({
            "slot_id": slot["slot_id"],
            "content_ref": slot["content_ref"],
            "sequence_no": i + 1,
            "junction_kind": slot["junction_kind"],
            "sched_start_frame": sched_offset(slot["sched_start_tc"], off),
            "actual_start_frame": starts[i],
            "material_frames": material[i],
            "trim_frames": trim[i],
            "transmitted_frames": transmitted,
            "end_frame": starts[i] + transmitted,
            "drift_frames": starts[i] - sched_offset(slot["sched_start_tc"], off),
            "hour_label": _hour_label(starts[i]),
            "daypart_ref": slot["daypart_ref"],
            "placement_state": "PL_PLACED",
        })
    day_end = max([p["end_frame"] for p in placed], default=0)
    return {"placed": placed, "corrections": corrections, "fills": fills,
            "day_end": day_end}


# --------------------------------------------------------------------------
# V10  market substitution
# --------------------------------------------------------------------------
def stage_v10(inp: dict, placed: list, off) -> dict:
    tx = inp["tx_date"]
    subs_by_ref: dict = {}
    for row in inp["substitutes"]:
        subs_by_ref.setdefault(row["substitute_ref"], []).append(row)
    rows = []
    winner: dict = {}
    for market in sorted(r["market_ref"] for r in inp["markets"]):
        for slot in placed:
            matches = []
            for rule in inp["blackouts"]:
                if rule["market_ref"] != market:
                    continue
                if rule["content_ref"] != slot["content_ref"]:
                    continue
                lo = parse_date(rule["window_from"])
                hi = parse_date(rule["window_to"])
                inside = lo <= tx <= hi if _on(off, "R25") else lo <= tx < hi
                if inside:
                    matches.append(rule)
            if not matches:
                continue
            matches.sort(key=lambda r: (_int(r["precedence"]), r["rule_id"]))
            chosen = matches[0]
            if _on(off, "R26"):
                overrides = [r for r in matches if r["override"] == "yes"]
                if overrides:
                    chosen = overrides[-1]
            winner[(market, slot["slot_id"])] = chosen
            rows.append({
                "market_ref": market,
                "slot_id": slot["slot_id"],
                "content_ref": slot["content_ref"],
                "rule_id": chosen["rule_id"],
                "precedence": chosen["precedence"],
                "substitute_ref": chosen["substitute_ref"],
                "override_flag": chosen["override"],
                "national_break_count": "",
                "substitute_break_count": str(len(
                    subs_by_ref.get(chosen["substitute_ref"], []))),
            })
    return {"rows": rows, "winner": winner, "subs_by_ref": subs_by_ref}


# --------------------------------------------------------------------------
# V9  avail derivation
# --------------------------------------------------------------------------
def stage_v9(inp: dict, v6: dict, v10: dict, placed: list,
             carry: Carry, off) -> dict:
    markets = sorted(r["market_ref"] for r in inp["markets"])
    per_market: dict = {}
    for market in markets:
        cap_scope = "V9:" + market
        sub_scope = "V10:" + market
        carry.open(cap_scope)
        carry.open(sub_scope)
        breaks = []
        for slot in placed:
            rule = v10["winner"].get((market, slot["slot_id"]))
            if rule is None:
                for brk in v6["positions"].get(slot["slot_id"], []):
                    position = slot["actual_start_frame"] + brk["position"]
                    breaks.append({
                        "break_ref": brk["break_ref"], "slot_id": slot["slot_id"],
                        "break_no": brk["break_no"], "origin": "BO_NATIONAL",
                        "position_frame": position, "capacity_frames": 0,
                        "daypart_ref": slot["daypart_ref"],
                        "hour_label": _hour_label(position),
                        "avail_seconds": brk["avail_seconds"],
                    })
            else:
                rows = sorted(v10["subs_by_ref"].get(rule["substitute_ref"], []),
                              key=lambda r: _int(r["break_no"]))
                for brk in rows:
                    offset = carry.convert(
                        seconds_to_frames(_int(brk["nominal_offset_seconds"])),
                        sub_scope)
                    position = slot["actual_start_frame"] + offset
                    breaks.append({
                        "break_ref": "sb_%s_%02d" % (rule["substitute_ref"],
                                                     _int(brk["break_no"])),
                        "slot_id": slot["slot_id"],
                        "break_no": _int(brk["break_no"]),
                        "origin": "BO_SUBSTITUTE",
                        "position_frame": position, "capacity_frames": 0,
                        "daypart_ref": slot["daypart_ref"],
                        "hour_label": _hour_label(position),
                        "avail_seconds": _int(brk["avail_seconds"]),
                    })
        breaks.sort(key=lambda b: (b["position_frame"], b["break_ref"]))
        walk = breaks if _on(off, "R11") else sorted(
            breaks, key=lambda b: b["break_ref"])
        for item in walk:
            item["capacity_frames"] = carry.convert(
                seconds_to_frames(item["avail_seconds"]), cap_scope)
        for item in breaks:
            del item["avail_seconds"]
        per_market[market] = breaks
    return {"per_market": per_market, "markets": markets}


def _clearance_state(inp: dict, off) -> dict:
    best: dict = {}
    for row in inp["clearance"]:
        ref = row["clearance_ref"]
        if not _on(off, "R38"):
            key = (row["journal_seq"], row["clearance_note"])
        elif _on(off, "R32"):
            key = (_int(row["journal_seq"]), row["clearance_note"])
        else:
            key = (row["logged_at"], row["clearance_note"])
        if ref not in best or key > best[ref][0]:
            best[ref] = (key, row["clearance_state"])
    return {ref: value[1] for ref, value in best.items()}


def _card_for(inp: dict, ref: str, off) -> dict:
    rows = [r for r in inp["cards"] if r["rate_card_ref"] == ref]
    if not rows:
        return None
    if _on(off, "R28"):
        rows = [r for r in rows if parse_date(r["effective_from"]) <= inp["tx_date"]]
        if not rows:
            return None
    if _on(off, "R39"):
        return max(rows, key=lambda r: (r["effective_from"], _int(r["card_revision"])))
    return max(rows, key=lambda r: (r["effective_from"], r["card_revision"]))


def stage_admission(inp: dict, v9: dict, v10: dict, placed: list,
                    spot_frames: dict, off) -> dict:
    sep_min = inp["memo_scalars"]["separation_minimum_positions"]
    clearance = _clearance_state(inp, off)
    slot_of = {p["slot_id"]: p for p in placed}
    orders_by_market: dict = {}
    for order in inp["orders"]:
        orders_by_market.setdefault(order["market_ref"], []).append(order)

    admitted = []
    deferred = []
    for market in v9["markets"]:
        breaks = v9["per_market"][market]
        by_ref = {b["break_ref"]: b for b in breaks}
        pool = orders_by_market.get(market, [])
        if _on(off, "R24"):
            pool = sorted(pool, key=lambda o: (int(o["priority_band"]), o["order_ref"]))
        else:
            pool = sorted(pool, key=lambda o: o["order_ref"])
        used: dict = {}
        seated: dict = {}
        for order in pool:
            ref = order["break_ref"]
            brk = by_ref.get(ref)
            slot_id = ref[3:].rsplit("_", 1)[0] if ref.startswith("bk_") else ""
            blacked = (market, slot_id) in v10["winner"]
            frames = spot_frames[order["order_ref"]]
            checks = [
                ("DF_CLEARANCE_HELD",
                 clearance.get(order["clearance_ref"]) == "CL_HELD"),
                ("DF_MARKET_BLACKED", blacked),
                ("DF_NO_MATCHING_BREAK", brk is None),
                ("DF_DAYPART_MISMATCH",
                 brk is not None and order["daypart_ref"] != brk["daypart_ref"]),
                ("DF_NO_RATE_CARD",
                 _card_for(inp, order["rate_card_ref"], off) is None),
                ("DF_BREAK_FULL",
                 brk is not None and used.get(ref, 0) + frames > brk["capacity_frames"]),
                ("DF_SEPARATION",
                 brk is not None and _separation_hit(
                     seated.get(ref, []), order["separation_class"], sep_min, off)),
            ]
            if not _on(off, "R22"):
                checks = [checks[5]] + checks[:5] + [checks[6]]
            reason = None
            index = 0
            for k, (code, hit) in enumerate(checks, start=1):
                if hit:
                    reason = code
                    index = k
                    break
            if reason is not None:
                deferred.append({
                    "order_ref": order["order_ref"],
                    "market_ref": market,
                    "break_ref": ref,
                    "deferral_reason": reason,
                    "predicate_index": index,
                    "spot_frames": frames,
                })
                continue
            start = brk["position_frame"] + used.get(ref, 0)
            used[ref] = used.get(ref, 0) + frames
            seated.setdefault(ref, []).append(order["separation_class"])
            admitted.append({
                "market_ref": market,
                "break_ref": ref,
                "break_position_frame": brk["position_frame"],
                "position_in_break": len(seated[ref]),
                "order_ref": order["order_ref"],
                "advertiser_ref": order["advertiser_ref"],
                "separation_class": order["separation_class"],
                "spot_frames": frames,
                "start_frame": start,
                "end_frame": start + frames,
                "hour_label": _hour_label(start),
            })
    admitted.sort(key=lambda a: (a["market_ref"], a["break_position_frame"],
                                 a["break_ref"], a["position_in_break"]))
    deferred.sort(key=lambda d: (d["order_ref"], d["market_ref"]))
    return {"admitted": admitted, "deferred": deferred}


def _separation_hit(seated: list, cls: str, sep_min: int, off) -> bool:
    if not _on(off, "R23"):
        return False
    nxt = len(seated) + 1
    for i, other in enumerate(seated, start=1):
        if other == cls and nxt - i < sep_min:
            return True
    return False


# --------------------------------------------------------------------------
# V11  settlement
# --------------------------------------------------------------------------
def _grains(frames: int, per_grain, off) -> int:
    if _on(off, "R27"):
        return fceil(F(frames) / per_grain)
    return nint(F(frames) / per_grain)


def stage_v11(inp: dict, adm: dict, spot_frames: dict, v13: dict, off) -> dict:
    grain = inp["memo_scalars"]["billing_grain_seconds"]
    per_grain = seconds_to_frames(grain)
    exponents = inp["exponents"]
    currency = {r["advertiser_ref"]: r["settlement_currency"]
                for r in inp["advertisers"]}
    legacy = {r["advertiser_ref"]: r["commission_pct"] for r in inp["legacy"]}
    order_by_ref = {o["order_ref"]: o for o in inp["orders"]}

    rows = []
    exceptions = []
    for spot in adm["admitted"]:
        order = order_by_ref[spot["order_ref"]]
        card = _card_for(inp, order["rate_card_ref"], off)
        frames = spot["spot_frames"]
        unbilled = v13["unbilled"].get(spot["order_ref"], 0)
        grains = _grains(frames - unbilled, per_grain, off)
        minor_per_grain = _int(card["minor_per_grain"])
        gross = minor_per_grain * grains
        adv = spot["advertiser_ref"]
        if _on(off, "R30"):
            num, den = inp["commission"][adv]
            commission = nint(F(gross) * F(num) / F(den))
        else:
            commission = nint(F(gross) * F(legacy[adv]) / 100)
        cur = currency[adv]
        exp = exponents[cur] if _on(off, "R29") else 2
        rows.append({
            "order_ref": spot["order_ref"],
            "advertiser_ref": adv,
            "market_ref": spot["market_ref"],
            "break_ref": spot["break_ref"],
            "currency": cur,
            "delivered_frames": str(frames),
            "unbilled_frames": str(unbilled),
            "billable_grains": str(grains),
            "rate_card_ref": order["rate_card_ref"],
            "effective_from": card["effective_from"],
            "minor_per_grain": str(minor_per_grain),
            "gross_minor": str(gross),
            "commission_minor": str(commission),
            "net_minor": str(gross - commission),
            "gross_major": ratio(F(gross) / (10 ** exp), exp),
        })
        if frames == 0:
            exceptions.append({"order_ref": spot["order_ref"],
                               "exception_code": "EX_ZERO_DELIVERY",
                               "rate_card_ref": order["rate_card_ref"],
                               "detail": "admitted spot occupies no channel frame"})
    for order in sorted(inp["orders"], key=lambda o: o["order_ref"]):
        if _card_for(inp, order["rate_card_ref"], off) is None:
            cards = [r for r in inp["cards"]
                     if r["rate_card_ref"] == order["rate_card_ref"]]
            earliest = min([r["effective_from"] for r in cards], default="")
            exceptions.append({"order_ref": order["order_ref"],
                               "exception_code": "EX_NO_CARD",
                               "rate_card_ref": order["rate_card_ref"],
                               "detail": "earliest card dated " + earliest})
    rows.sort(key=lambda r: (r["order_ref"], r["market_ref"]))
    exceptions.sort(key=lambda r: (r["order_ref"], r["exception_code"]))
    return {"rows": rows, "exceptions": exceptions}


# --------------------------------------------------------------------------
# V12  make good
# --------------------------------------------------------------------------
def stage_v12(inp: dict, adm: dict, v11: dict, spot_frames: dict, off) -> dict:
    grain = inp["memo_scalars"]["billing_grain_seconds"]
    per_grain = seconds_to_frames(grain)
    cap_num = inp["sheet_scalars"]["makegood_cap_num"]
    cap_den = inp["sheet_scalars"]["makegood_cap_den"]
    order_by_ref = {o["order_ref"]: o for o in inp["orders"]}

    gross_by_adv: dict = {}
    for row in v11["rows"]:
        gross_by_adv[row["advertiser_ref"]] = (
            gross_by_adv.get(row["advertiser_ref"], 0) + _int(row["gross_minor"]))

    raw_by_adv: dict = {}
    for item in adm["deferred"]:
        if item["deferral_reason"] == "DF_NO_RATE_CARD":
            continue
        order = order_by_ref[item["order_ref"]]
        card = _card_for(inp, order["rate_card_ref"], off)
        if card is None:
            continue
        frames = item["spot_frames"]
        grains = _grains(frames, per_grain, off)
        raw = _int(card["minor_per_grain"]) * grains
        raw_by_adv.setdefault(order["advertiser_ref"], []).append({
            "order_ref": item["order_ref"],
            "deferral_reason": item["deferral_reason"],
            "raw_minor": raw,
        })
    if _on(off, "R41"):
        # The grains an admitted spot lost to the cap are owed as make good.
        for row in v11["rows"]:
            delivered = _int(row["delivered_frames"])
            billed = delivered - _int(row["unbilled_frames"])
            lost = _grains(delivered, per_grain, off) - _grains(billed, per_grain, off)
            if lost > 0:
                raw_by_adv.setdefault(row["advertiser_ref"], []).append({
                    "order_ref": row["order_ref"],
                    "deferral_reason": "DF_OVER_CAP",
                    "raw_minor": _int(row["minor_per_grain"]) * lost,
                })

    entries = []
    grand = 0
    for adv in sorted(set(list(raw_by_adv) + list(gross_by_adv))):
        obligations = sorted(raw_by_adv.get(adv, []), key=lambda o: o["order_ref"])
        day_gross = gross_by_adv.get(adv, 0)
        cap = ffloor(F(cap_num) * F(day_gross) / F(cap_den))
        raw_total = sum(o["raw_minor"] for o in obligations)
        if raw_total <= cap or raw_total == 0:
            for item in obligations:
                item["allocated_minor"] = item["raw_minor"]
        elif _on(off, "R31"):
            base = []
            for item in obligations:
                exact = F(cap) * F(item["raw_minor"]) / F(raw_total)
                whole = ffloor(exact)
                base.append((exact - whole, item))
                item["allocated_minor"] = whole
            residue = cap - sum(o["allocated_minor"] for o in obligations)
            ranked = sorted(base, key=lambda p: (-p[0], p[1]["order_ref"]))
            for k in range(residue):
                ranked[k % len(ranked)][1]["allocated_minor"] += 1
        else:
            for item in obligations:
                item["allocated_minor"] = ffloor(
                    F(cap) * F(item["raw_minor"]) / F(raw_total))
        allocated = sum(o["allocated_minor"] for o in obligations)
        grand += allocated
        entries.append({
            "advertiser_ref": adv,
            "day_gross_minor": day_gross,
            "cap_minor": cap,
            "raw_total_minor": raw_total,
            "allocated_total_minor": allocated,
            "obligations": obligations,
        })
    return {"entries": entries, "allocated_total": grand}


# --------------------------------------------------------------------------
# V13  minutage compliance
# --------------------------------------------------------------------------
def _minutes_to_cap(minutes: int, off) -> int:
    if _on(off, "R34"):
        return ffloor(seconds_to_frames(minutes * 60))
    return minutes * 60 * CH_BASE


def _hour_spans(spot: dict, off) -> dict:
    """The frames of one admitted spot inside each clock hour (R33)."""
    if not _on(off, "R33"):
        return {_hour_label(spot["start_frame"]): spot["spot_frames"]}
    out = {}
    start, end = spot["start_frame"], spot["end_frame"]
    for idx in range(24):
        lo = idx * FRAMES_PER_HOUR
        hi = lo + FRAMES_PER_HOUR
        if idx == 23:
            hi = max(hi, end + 1)
        a = start if start > lo else lo
        b = end if end < hi else hi
        if b > a:
            out["H%02d" % (6 + idx)] = b - a
    return out


def stage_v13(inp: dict, v9: dict, adm: dict, off) -> dict:
    standing = inp["memo_scalars"]["regulatory_minutes_per_clock_hour"]
    cap = _minutes_to_cap(standing, off)
    daypart = {r["hour_label"]: r["daypart_ref"] for r in inp["dayparts"]}
    tally: dict = {}
    inside: dict = {}
    for spot in adm["admitted"]:
        market = spot["market_ref"]
        for hour, n in _hour_spans(spot, off).items():
            key = (market, hour)
            tally[key] = tally.get(key, 0) + n
            inside.setdefault(key, []).append((spot, n))
    rows = []
    breaches = 0
    unbilled: dict = {}
    for market in v9["markets"]:
        for hour in HOUR_LABELS:
            frames = tally.get((market, hour), 0)
            hour_cap = cap
            if _on(off, "R37"):
                hour_cap = _minutes_to_cap(
                    inp["memo_minutes"].get((market, hour), standing), off)
            over = frames > hour_cap if _on(off, "R34") else frames >= hour_cap
            if over and _on(off, "R41"):
                # R41: the frames above the cap go unbilled, taken from the
                # latest spots of the hour first.
                remaining = frames - hour_cap
                ranked = sorted(inside[(market, hour)],
                                key=lambda p: (p[0]["start_frame"], p[0]["order_ref"]),
                                reverse=True)
                for spot, n in ranked:
                    if remaining <= 0:
                        break
                    take = min(n, remaining)
                    unbilled[spot["order_ref"]] = unbilled.get(spot["order_ref"], 0) + take
                    remaining -= take
            if over:
                breaches += 1
            rows.append({
                "market_ref": market,
                "hour_label": hour,
                "daypart_ref": daypart[hour],
                "advertising_frames": str(frames),
                "advertising_seconds": ratio(F(frames) * F(CH_DEN) / F(CH_NUM)),
                "cap_frames": str(hour_cap),
                "headroom_frames": str(hour_cap - frames),
                "breach_state": "MB_BREACH" if over else "MB_WITHIN",
            })
    return {"rows": rows, "cap": cap, "breaches": breaches, "unbilled": unbilled}


# --------------------------------------------------------------------------
# V14  the delivered package
# --------------------------------------------------------------------------
def _b(text: str) -> bytes:
    return text.encode("utf-8")


def run_pipeline(data_dir, off=frozenset()) -> dict:
    inp = load_inputs(data_dir, off)
    cfg = inp["config"]
    v1 = stage_v1(inp, off)
    v23 = stage_v23(inp, v1, off)

    all_slots = sorted(inp["schedule"],
                       key=lambda s: (sched_offset(s["sched_start_tc"], off),
                                      s["slot_id"]))
    if _on(off, "R17"):
        slots = [s for s in all_slots if s["content_ref"] in v23["assets"]]
        dropped = [s for s in all_slots if s["content_ref"] not in v23["assets"]]
    else:
        slots = all_slots
        dropped = []

    carry = Carry(off)
    v45 = stage_v45(inp, v23, slots, carry, off)
    v6 = stage_v6(inp, v23, slots, carry, off)
    v78 = stage_v78(inp, v23, v45, v6, slots, off)
    v10 = stage_v10(inp, v78["placed"], off)
    v9 = stage_v9(inp, v6, v10, v78["placed"], carry, off)

    spot_frames = {}
    for order in sorted(inp["orders"],
                        key=lambda o: (o["advertiser_ref"], o["order_ref"])):
        scope = "V11:" + order["advertiser_ref"]
        if scope not in carry.held:
            carry.open(scope)
        exact = seconds_to_frames(int(order["nominal_seconds"]))
        if _on(off, "R21"):
            spot_frames[order["order_ref"]] = carry.convert(exact, scope)
        else:
            carry.count[scope] = carry.count.get(scope, 0) + 1
            spot_frames[order["order_ref"]] = nint(exact)

    adm = stage_admission(inp, v9, v10, v78["placed"], spot_frames, off)
    v13 = stage_v13(inp, v9, adm, off)
    v11 = stage_v11(inp, adm, spot_frames, v13, off)
    v12 = stage_v12(inp, adm, v11, spot_frames, off)

    out: dict = {}

    # ---- V1 to V3 ---------------------------------------------------------
    out["asset_register.csv"] = _b(render_delim(
        ["content_ref", "canonical_ingest_id", "revision_no", "qc_state",
         "rate_code", "rate_num", "rate_den", "tc_base", "drop_frame",
         "som_tc", "eom_tc", "source_frames", "channel_frames_exact",
         "house_no", "anchor_ingest_id", "inclusion_state"],
        v23["rows"], ","))

    # ---- V4 and V5 --------------------------------------------------------
    seg = sorted(v45["rows"], key=lambda r: (r["slot_id"], _int(r["part_no"])))
    out["segment_conform.csv"] = _b(render_delim(
        ["slot_id", "content_ref", "part_no", "part_kind", "retention_state",
         "source_frames", "channel_frames_exact", "channel_frames",
         "carry_after"], seg, ","))

    # ---- V6 ---------------------------------------------------------------
    brk = sorted(v6["rows"], key=lambda r: (r["slot_id"], _int(r["break_no"])))
    out["break_positions.csv"] = _b(render_delim(
        ["slot_id", "break_no", "break_ref", "nominal_offset_seconds",
         "nominal_frame", "adjusted_target_frame", "position_frame",
         "snap_side", "displacement_frames", "avail_seconds", "carry_after"],
        brk, ","))

    # ---- V7 and V8 --------------------------------------------------------
    place_rows = []
    for row in v78["placed"]:
        place_rows.append({k: str(v) for k, v in row.items()})
    for slot in dropped:
        place_rows.append({
            "slot_id": slot["slot_id"], "content_ref": slot["content_ref"],
            "sequence_no": "0", "junction_kind": slot["junction_kind"],
            "sched_start_frame": "0",
            "actual_start_frame": "0", "material_frames": "0",
            "trim_frames": "0", "transmitted_frames": "0", "end_frame": "0",
            "drift_frames": "0", "hour_label": "",
            "daypart_ref": slot["daypart_ref"], "placement_state": "PL_DROPPED",
        })
    place_rows.sort(key=lambda r: (_int(r["sequence_no"]), r["slot_id"]))
    out["slot_placement.csv"] = _b(render_delim(
        ["slot_id", "content_ref", "sequence_no", "junction_kind",
         "sched_start_frame", "actual_start_frame", "material_frames",
         "trim_frames", "transmitted_frames", "end_frame", "drift_frames",
         "hour_label", "daypart_ref", "placement_state"], place_rows, ","))

    corrections = list(v78["corrections"])
    for slot in dropped:
        corrections.append({
            "slot_id": slot["slot_id"], "reason": "CR_SLOT_DROPPED",
            "frames": 0, "detail_slot": slot["slot_id"], "filler_ref": "",
        })
    totals: dict = {}
    trace = []
    for i, item in enumerate(corrections, start=1):
        totals[item["reason"]] = totals.get(item["reason"], 0) + 1
        entry = dict(item)
        entry["sequence"] = i
        trace.append(entry)
    out["conform_trace.json"] = _b(canonical_json({
        "corrections": trace,
        "totals": totals,
        "day_end_frame": v78["day_end"],
        "correction_count": len(trace),
    }))

    out["filler_plan.csv"] = _b(render_delim(
        ["slot_id", "junction_offset_frame", "gap_frames", "filler_ref",
         "daypart_ref", "selection_index"],
        sorted(v78["fills"], key=lambda r: r["slot_id"]), ","))

    # ---- V9 and V10 -------------------------------------------------------
    adm_rows = [{k: str(v) for k, v in row.items()} for row in adm["admitted"]]
    out["avail_plan.tsv"] = _b(render_delim(
        ["market_ref", "break_ref", "break_position_frame", "position_in_break",
         "order_ref", "advertiser_ref", "separation_class", "spot_frames",
         "start_frame", "end_frame", "hour_label"], adm_rows, "\t"))

    out["deferral_ledger.jsonl"] = _b(render_jsonl(adm["deferred"]))

    override_rows = []
    for row in v10["rows"]:
        entry = dict(row)
        entry["national_break_count"] = str(len(
            v6["positions"].get(row["slot_id"], [])))
        override_rows.append(entry)
    override_rows.sort(key=lambda r: (r["market_ref"], r["slot_id"]))
    out["market_overrides.csv"] = _b(render_delim(
        ["market_ref", "slot_id", "content_ref", "rule_id", "precedence",
         "substitute_ref", "override_flag", "national_break_count",
         "substitute_break_count"], override_rows, ","))

    stream = []
    for market in v9["markets"]:
        breaks = v9["per_market"][market]
        payload = {
            "market_ref": market,
            "break_count": len(breaks),
            "capacity_frames_total": sum(b["capacity_frames"] for b in breaks),
            "carry_residual_capacity": ratio(carry.close("V9:" + market)),
            "carry_residual_substitute": ratio(carry.close("V10:" + market)),
            "breaks": breaks,
        }
        out["market_avails_%s.json" % market] = _b(canonical_json(payload))
        for item in breaks:
            entry = dict(item)
            entry["market_ref"] = market
            stream.append(entry)
    stream.sort(key=lambda r: (r["market_ref"], r["position_frame"], r["break_ref"]))
    out["market_avail_stream.jsonl"] = _b(render_jsonl(stream))

    # ---- V11 and V12 ------------------------------------------------------
    out["settlement_ledger.psv"] = _b(render_delim(
        ["order_ref", "advertiser_ref", "market_ref", "break_ref", "currency",
         "delivered_frames", "unbilled_frames", "billable_grains", "rate_card_ref",
         "effective_from", "minor_per_grain", "gross_minor",
         "commission_minor", "net_minor", "gross_major"], v11["rows"], "|"))

    out["makegood_ledger.json"] = _b(canonical_json({
        "advertisers": v12["entries"],
        "allocated_total_minor": v12["allocated_total"],
        "cap_num": inp["sheet_scalars"]["makegood_cap_num"],
        "cap_den": inp["sheet_scalars"]["makegood_cap_den"],
    }))

    out["exception_ledger.jsonl"] = _b(render_jsonl(v11["exceptions"]))

    summary: dict = {}
    for row in inp["advertisers"]:
        summary[row["advertiser_ref"]] = {
            "advertiser_ref": row["advertiser_ref"],
            "currency": row["settlement_currency"],
            "admitted_spots": 0, "deferred_spots": 0, "delivered_frames": 0,
            "gross_minor": 0, "commission_minor": 0, "net_minor": 0,
            "makegood_minor": 0,
        }
    for row in v11["rows"]:
        entry = summary[row["advertiser_ref"]]
        entry["admitted_spots"] += 1
        entry["delivered_frames"] += _int(row["delivered_frames"])
        entry["gross_minor"] += _int(row["gross_minor"])
        entry["commission_minor"] += _int(row["commission_minor"])
        entry["net_minor"] += _int(row["net_minor"])
    order_by_ref = {o["order_ref"]: o for o in inp["orders"]}
    for item in adm["deferred"]:
        summary[order_by_ref[item["order_ref"]]["advertiser_ref"]]["deferred_spots"] += 1
    for entry in v12["entries"]:
        if entry["advertiser_ref"] in summary:
            summary[entry["advertiser_ref"]]["makegood_minor"] = \
                entry["allocated_total_minor"]
    exponents = inp["exponents"]
    adv_rows = []
    for ref in sorted(summary):
        entry = summary[ref]
        exp = exponents[entry["currency"]] if _on(off, "R29") else 2
        adv_rows.append({
            "advertiser_ref": ref,
            "currency": entry["currency"],
            "admitted_spots": str(entry["admitted_spots"]),
            "deferred_spots": str(entry["deferred_spots"]),
            "delivered_frames": str(entry["delivered_frames"]),
            "gross_minor": str(entry["gross_minor"]),
            "commission_minor": str(entry["commission_minor"]),
            "net_minor": str(entry["net_minor"]),
            "makegood_minor": str(entry["makegood_minor"]),
            "gross_major": ratio(F(entry["gross_minor"]) / (10 ** exp), exp),
        })
    out["advertiser_summary.csv"] = _b(render_delim(
        ["advertiser_ref", "currency", "admitted_spots", "deferred_spots",
         "delivered_frames", "gross_minor", "commission_minor", "net_minor",
         "makegood_minor", "gross_major"], adv_rows, ","))

    # ---- V13 --------------------------------------------------------------
    out["minutage_report.csv"] = _b(render_delim(
        ["market_ref", "hour_label", "daypart_ref", "advertising_frames",
         "advertising_seconds", "cap_frames", "headroom_frames",
         "breach_state"], v13["rows"], ","))

    # ---- the carry ledger --------------------------------------------------
    scopes = []
    for name in sorted(carry.held):
        scopes.append({
            "scope": name,
            "conversions": carry.count.get(name, 0),
            "residual": ratio(carry.held[name]),
        })
    out["carry_ledger.json"] = _b(canonical_json({
        "scopes": scopes,
        "scope_count": len(scopes),
        "conversion_count": sum(carry.count.get(n, 0) for n in carry.held),
        "residual_total": ratio(sum(carry.held.values(), Fraction(0))),
    }))

    # ---- V14 reconciliation -------------------------------------------------
    prior = {r["slot_id"]: r for r in inp["prior"]}
    place_by_slot = {r["slot_id"]: r for r in place_rows}
    nat_count = {sid: len(v6["positions"].get(sid, [])) for sid in place_by_slot}
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<reconciliation channel_ref="%s" transmission_date="%s">'
                 % (xml_escape(cfg["channel_ref"]),
                    xml_escape(cfg["transmission_date"])))
    agree = 0
    differ = 0
    abs_start = 0
    abs_material = 0
    for slot_id in sorted(place_by_slot):
        row = place_by_slot[slot_id]
        was = prior.get(slot_id, {"prior_start_frame": "0",
                                  "prior_material_frames": "0",
                                  "prior_break_count": "0"})
        ps = _int(was["prior_start_frame"])
        pm = _int(was["prior_material_frames"])
        pb = _int(was["prior_break_count"])
        cs = _int(row["actual_start_frame"])
        cm = _int(row["material_frames"])
        cb = nat_count.get(slot_id, 0)
        if (ps, pm, pb) == (cs, cm, cb):
            agree += 1
        else:
            differ += 1
        abs_start += abs(cs - ps)
        abs_material += abs(cm - pm)
        lines.append(
            '  <slot slot_id="%s" placement_state="%s" prior_start_frame="%d" '
            'start_frame="%d" start_delta="%d" prior_material_frames="%d" '
            'material_frames="%d" material_delta="%d" prior_break_count="%d" '
            'break_count="%d" break_delta="%d"/>' % (
                xml_escape(slot_id), xml_escape(row["placement_state"]),
                ps, cs, cs - ps, pm, cm, cm - pm, pb, cb, cb - pb))
    lines.append('  <totals slots="%d" agreeing="%d" differing="%d" '
                 'absolute_start_delta="%d" absolute_material_delta="%d"/>'
                 % (len(place_by_slot), agree, differ, abs_start, abs_material))
    lines.append("</reconciliation>")
    out["reconciliation.xml"] = _b("\n".join(lines) + "\n")

    # ---- the playout schedule ----------------------------------------------
    day_start = tc_to_frames(DAY_START_TC, CH_BASE, CH_DF)
    ini = ["[channel]",
           "channel_ref = %s" % cfg["channel_ref"],
           "transmission_date = %s" % cfg["transmission_date"],
           "day_start_tc = %s" % DAY_START_TC,
           "day_end_frame = %d" % v78["day_end"],
           "placed_slot_count = %d" % len(v78["placed"]),
           ""]
    for row in v78["placed"]:
        ini.append("[slot:%s]" % row["slot_id"])
        ini.append("content_ref = %s" % row["content_ref"])
        ini.append("sequence_no = %d" % row["sequence_no"])
        ini.append("start_frame = %d" % row["actual_start_frame"])
        ini.append("start_tc = %s" % frames_to_tc(
            (day_start + row["actual_start_frame"]) % DAY_FRAMES, CH_BASE, CH_DF))
        ini.append("transmitted_frames = %d" % row["transmitted_frames"])
        ini.append("trim_frames = %d" % row["trim_frames"])
        ini.append("break_count = %d" % nat_count.get(row["slot_id"], 0))
        ini.append("")
    out["playout_schedule.ini"] = _b("\n".join(ini).rstrip("\n") + "\n")

    # ---- the two written reports --------------------------------------------
    digest = digest_over(out, off)
    admitted_count = len(adm["admitted"])
    deferred_count = len(adm["deferred"])
    gross_total = sum(_int(r["gross_minor"]) for r in v11["rows"])
    reasons: dict = {}
    for item in adm["deferred"]:
        reasons[item["deferral_reason"]] = reasons.get(item["deferral_reason"], 0) + 1
    for entry in v12["entries"]:
        for item in entry["obligations"]:
            if item["deferral_reason"] == "DF_OVER_CAP":
                reasons["DF_OVER_CAP"] = reasons.get("DF_OVER_CAP", 0) + 1

    day = ["# Transmission day report",
           "",
           "- channel_ref: %s" % cfg["channel_ref"],
           "- transmission_date: %s" % cfg["transmission_date"],
           "- instance_ref: %s" % cfg["instance_ref"],
           "- live_control_set: %s" % cfg["workbook_control_set"],
           "- scheduled_slots: %d" % len(inp["schedule"]),
           "- placed_slots: %d" % len(v78["placed"]),
           "- dropped_slots: %d" % len(dropped),
           "- day_end_frame: %d" % v78["day_end"],
           "- corrections: %d" % len(trace),
           "- admitted_spots: %d" % admitted_count,
           "- deferred_spots: %d" % deferred_count,
           "- gross_minor_total: %d" % gross_total,
           "- makegood_minor_total: %d" % v12["allocated_total"],
           "",
           "## Correction totals",
           ""]
    for reason in CORRECTION_REASONS:
        day.append("- %s: %d" % (reason, totals.get(reason, 0)))
    day.append("")
    day.append("## Deferral totals")
    day.append("")
    for reason in DEFERRAL_REASONS:
        day.append("- %s: %d" % (reason, reasons.get(reason, 0)))
    out["day_report.md"] = _b("\n".join(day) + "\n")

    comp = ["# Compliance summary",
            "",
            "- regulatory_minutes_per_clock_hour: %d"
            % inp["memo_scalars"]["regulatory_minutes_per_clock_hour"],
            "- cap_frames: %d" % v13["cap"],
            "- separation_minimum_positions: %d"
            % inp["memo_scalars"]["separation_minimum_positions"],
            "- billing_grain_seconds: %d"
            % inp["memo_scalars"]["billing_grain_seconds"],
            "- snap_tolerance_frames: %d"
            % inp["sheet_scalars"]["snap_tolerance_frames"],
            "- breach_hours: %d" % v13["breaches"],
            "",
            "## Advertising frames by market",
            ""]
    per_market_frames: dict = {}
    for row in v13["rows"]:
        per_market_frames[row["market_ref"]] = (
            per_market_frames.get(row["market_ref"], 0)
            + _int(row["advertising_frames"]))
    for market in v9["markets"]:
        comp.append("- %s: %d" % (market, per_market_frames.get(market, 0)))
    comp.append("")
    comp.append("## Breach hours")
    comp.append("")
    breach_lines = [r for r in v13["rows"] if r["breach_state"] == "MB_BREACH"]
    if breach_lines:
        for row in breach_lines:
            comp.append("- %s %s frames %s over %s"
                        % (row["market_ref"], row["hour_label"],
                           row["advertising_frames"], row["cap_frames"]))
    else:
        comp.append("- none")
    out["compliance_summary.md"] = _b("\n".join(comp) + "\n")

    # ---- the manifest --------------------------------------------------------
    out["manifest.json"] = _b(canonical_json({
        "instance_ref": cfg["instance_ref"],
        "channel_ref": cfg["channel_ref"],
        "transmission_date": cfg["transmission_date"],
        "artifact_count": len(ARTIFACTS),
        "core_order": list(CORE_FILES),
        "digest": digest,
        "slot_count": len(inp["schedule"]),
        "placed_slot_count": len(v78["placed"]),
        "dropped_slot_count": len(dropped),
        "admitted_spot_count": admitted_count,
        "deferred_spot_count": deferred_count,
        "breach_hour_count": v13["breaches"],
        "live_control_set": inp["live_sheet_name"],
        "snap_tolerance_frames": inp["sheet_scalars"]["snap_tolerance_frames"],
        "makegood_cap_num": inp["sheet_scalars"]["makegood_cap_num"],
        "makegood_cap_den": inp["sheet_scalars"]["makegood_cap_den"],
        "separation_minimum_positions":
            inp["memo_scalars"]["separation_minimum_positions"],
        "billing_grain_seconds": inp["memo_scalars"]["billing_grain_seconds"],
        "regulatory_minutes_per_clock_hour":
            inp["memo_scalars"]["regulatory_minutes_per_clock_hour"],
        "day_end_frame": v78["day_end"],
    }))
    return out


def write_outputs(blobs: dict, out_dir) -> None:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACTS:
        (root / name).write_bytes(blobs[name])


# ==========================================================================
# grading
#
# The shipped bytes are worth a little and the delivered program is worth a
# lot. Seven transmission days are minted here from seeds the agent has never
# seen. The delivered program is run against six of them, and the seventh is
# planted in the working directory of a run to catch a remembered path.
# ==========================================================================

OUT_DIR = Path("/app/out")
PROGRAM = OUT_DIR / PROGRAM_NAME
PROGRAM_TIMEOUT_SEC = 600

_CORPUS_CACHE: dict = {}
_EXPECTED_CACHE: dict = {}
_PROGRAM_CACHE: dict = {}


def _corpus(seed: int) -> Path:
    if seed not in _CORPUS_CACHE:
        root = Path(tempfile.mkdtemp(prefix="playout-corpus-")) / "data"
        generate(seed, root)
        _CORPUS_CACHE[seed] = root
    return _CORPUS_CACHE[seed]


def _expected(seed: int = SAMPLE_SEED) -> dict:
    if seed not in _EXPECTED_CACHE:
        _EXPECTED_CACHE[seed] = run_pipeline(_corpus(seed))
    return _EXPECTED_CACHE[seed]


def _open_to_the_runner(path) -> None:
    """Open a directory tree to the unprivileged user the delivered program
    runs as. The permission is opened rather than closed on purpose: the
    detectors need the program to be ABLE to dirty the day it was given and
    to reach a planted directory, because what is graded is whether it
    does, not whether it could."""
    root = Path(path)
    for target in [root] + list(root.rglob("*")):
        try:
            os.chmod(target, 0o777)
        except OSError:
            pass


def _sealed_for_the_runner() -> None:
    """Leave the graded output directory readable but not writable by the
    runner, so the delivered program cannot rewrite the artifacts it is
    being graded on while it runs."""
    for target, mode in ((OUT_DIR, 0o755), (PROGRAM, 0o644)):
        try:
            os.chmod(target, mode)
        except OSError:
            pass


def _unprivileged(argv: list) -> list:
    """Drop the delivered program to `nobody`. This verifier image carries
    the reference pipeline, the corpus generator and the instance seeds
    under /tests, and closes that tree to everyone but its owner, so a
    program run as root could import the grader and reproduce every
    expected artifact without deriving anything. Running it as `nobody` is
    what makes that chmod bite. Where the grader is not root the run happens
    exactly as it did before; a root grader without setpriv refuses to run
    the program at all, so the check that needed the run fails."""
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return argv
    if shutil.which("setpriv") is None:
        raise AssertionError(
            "the verifier image is missing setpriv, so the delivered program "
            "cannot be dropped to an unprivileged user")
    return ["setpriv", "--reuid=nobody", "--regid=nogroup",
            "--clear-groups"] + argv


def _run_isolated(argv: list, cwd: str, env=None) -> tuple:
    """Run delivered agent code as a subprocess in its own session, wait for
    it and then reap anything it left behind. The delivered program is
    hostile input, so a child that detaches its stdio and outlives the run
    could rewrite the graded files after grading has finished. Putting the
    run in a new process group and killing that group once the parent has
    exited closes that route, and the run itself is dropped to an
    unprivileged user so the program cannot read the grader."""
    proc = subprocess.Popen(_unprivileged(argv),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd=cwd, env=env,
                            start_new_session=hasattr(os, "killpg"))
    try:
        _, err = proc.communicate(timeout=PROGRAM_TIMEOUT_SEC)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise
    finally:
        if hasattr(os, "killpg"):
            try:
                os.killpg(proc.pid, 9)
            except (ProcessLookupError, PermissionError, OSError):
                pass
    return rc, (err or "")[-4000:]


def _tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            h.update(str(path.relative_to(root)).replace(os.sep, "/").encode("utf-8"))
            h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


# The second run of the probe day goes through this launcher, which takes every
# site-packages directory off the import path before running the delivered
# program, so that run can import nothing beyond the Python standard library.
STDLIB_ONLY_TAG = "another-day"
_STDLIB_ONLY_LAUNCHER = (
    "import os, runpy, sys\n"
    "sys.path[:] = [p for p in sys.path if os.path.basename(p.rstrip(os.sep))"
    " not in ('site-packages', 'dist-packages')]\n"
    "program = sys.argv[1]\n"
    "sys.argv = sys.argv[1:]\n"
    "sys.path.insert(0, os.path.dirname(os.path.abspath(program)))\n"
    "runpy.run_path(program, run_name='__main__')\n"
)


def _program_case(seed: int, tag: str = "case") -> dict:
    """Run the delivered program against a private copy of a transmission
    day this module mints. The agent has never seen the instance and cannot
    have tuned to it."""
    key = (seed, tag)
    if key in _PROGRAM_CACHE:
        return _PROGRAM_CACHE[key]
    if not PROGRAM.is_file():
        raise AssertionError("required deliverable is absent: " + PROGRAM_NAME)
    root = Path(tempfile.mkdtemp(prefix="playout-run-"))
    data = root / tag
    # The output directory is nested one level below a parent that does not
    # exist either, so the program has to create both.
    out = root / (tag + "-out") / "day"
    # A private home and temporary directory: anything the program leaves in
    # them is a write outside the directory it was told to write to.
    home = root / (tag + "-home")
    scratch = root / (tag + "-tmp")
    home.mkdir()
    scratch.mkdir()
    shutil.copytree(_corpus(seed), data)
    before = _tree_digest(data)
    _open_to_the_runner(root)
    _sealed_for_the_runner()
    launch = ([sys.executable, "-I", "-c", _STDLIB_ONLY_LAUNCHER]
              if tag == STDLIB_ONLY_TAG else [sys.executable])
    env = dict(os.environ, HOME=str(home), TMPDIR=str(scratch),
               TMP=str(scratch), TEMP=str(scratch))
    try:
        rc, err = _run_isolated(
            launch + [str(PROGRAM), "--data", str(data), "--out", str(out)],
            cwd=str(root), env=env)
    except subprocess.TimeoutExpired:
        rc, err = -1, "the program did not finish within the time allowed"
    kept = (data.name, out.parent.name, home.name, scratch.name)
    stray = sorted(p.name for p in root.iterdir() if p.name not in kept)
    if out.parent.is_dir():
        stray += sorted(out.parent.name + "/" + p.name
                        for p in out.parent.iterdir() if p.name != out.name)
    for private in (home, scratch):
        stray += sorted(str(p.relative_to(root)) for p in private.rglob("*"))
    _PROGRAM_CACHE[key] = {"rc": rc, "out": out, "stderr": err,
                           "before": before, "after": _tree_digest(data),
                           "stray": stray}
    return _PROGRAM_CACHE[key]


def _program_planted(seed: int) -> dict:
    """Run the delivered program on one minted day while a different day
    sits in a directory named `data` beside the working directory. A program
    that reaches for a remembered path instead of the one it was given picks
    up the wrong day. The planted day is minted from a seed that is neither
    the shipped one nor any graded one, so a delivery that simply memorised
    the shipped day cannot reproduce it and this detector charges the
    remembered path alone."""
    key = ("planted", seed)
    if key in _PROGRAM_CACHE:
        return _PROGRAM_CACHE[key]
    if not PROGRAM.is_file():
        raise AssertionError("required deliverable is absent: " + PROGRAM_NAME)
    root = Path(tempfile.mkdtemp(prefix="playout-planted-"))
    shutil.copytree(_corpus(PLANT_SEED), root / "data")
    shutil.copytree(_corpus(PLANT_SEED), root / "app" / "data")
    data = root / "given"
    out = root / "given-out"
    shutil.copytree(_corpus(seed), data)
    _open_to_the_runner(root)
    _sealed_for_the_runner()
    try:
        rc, err = _run_isolated(
            [sys.executable, str(PROGRAM), "--data", str(data), "--out", str(out)],
            cwd=str(root))
    except subprocess.TimeoutExpired:
        rc, err = -1, "the program did not finish within the time allowed"
    _PROGRAM_CACHE[key] = {"rc": rc, "out": out, "stderr": err}
    return _PROGRAM_CACHE[key]


def _program_repeat(seed: int) -> tuple:
    """Run the delivered program twice over one input directory, into two
    output directories. The input path is byte identical and name identical
    across the two runs, so a difference between them is nondeterminism and
    nothing else."""
    key = ("repeat-pair", seed)
    if key in _PROGRAM_CACHE:
        return _PROGRAM_CACHE[key]
    if not PROGRAM.is_file():
        raise AssertionError("required deliverable is absent: " + PROGRAM_NAME)
    root = Path(tempfile.mkdtemp(prefix="playout-repeat-"))
    data = root / "instance"
    shutil.copytree(_corpus(seed), data)
    _open_to_the_runner(root)
    _sealed_for_the_runner()
    runs = []
    for i in (1, 2):
        out = root / ("out-%d" % i)
        try:
            rc, _ = _run_isolated(
                [sys.executable, str(PROGRAM), "--data", str(data), "--out", str(out)],
                cwd=str(root))
        except subprocess.TimeoutExpired:
            rc = -1
        runs.append((rc, out))
    _PROGRAM_CACHE[key] = tuple(runs)
    return _PROGRAM_CACHE[key]


def _repeat_got(seed: int, name: str) -> tuple:
    blobs = []
    for rc, out in _program_repeat(seed):
        if rc != 0:
            raise AssertionError("the program failed on the minted day")
        path = out / name
        if not path.is_file():
            raise AssertionError("the program wrote no %s for the minted day" % name)
        blobs.append(path.read_bytes())
    return tuple(blobs)


def _got(name: str) -> bytes:
    path = OUT_DIR / name
    if not path.is_file():
        raise AssertionError("required artifact is absent: " + name)
    return path.read_bytes()


def _got_text(name: str) -> str:
    return _got(name).decode("utf-8")


def _case_got(seed: int, name: str, tag: str = "case") -> bytes:
    case = _program_case(seed, tag)
    if case["rc"] != 0:
        raise AssertionError(
            "the program failed on the minted day: " + str(case["stderr"]))
    path = case["out"] / name
    if not path.is_file():
        raise AssertionError("the program wrote no %s for the minted day" % name)
    return path.read_bytes()


# The spine carries one published observable of every stage of the chain, so
# a wrong reading anywhere on the chain fails the spine check. Each family is
# scored on its own artifacts alone: a stage read wrongly forfeits the weight
# of the spine and of whichever family publishes it, and leaves the families
# it does not touch earnable, so a near miss and a total miss do not collapse
# to the same score. The spine and the three families together are the
# twenty five artifacts.
FAM_CORE = list(CORE_FILES) + [
    "manifest.json", "conform_trace.json", "filler_plan.csv",
    "carry_ledger.json", "deferral_ledger.jsonl", "market_overrides.csv",
    "market_avail_stream.jsonl", "advertiser_summary.csv",
    "makegood_ledger.json", "exception_ledger.jsonl"]
FAM_CONFORM = ["playout_schedule.ini", "reconciliation.xml"]
FAM_AVAIL = ["market_avails_%s.json" % m for m in MARKETS]
FAM_MONEY = ["day_report.md", "compliance_summary.md"]


def _assert_full_core() -> None:
    """Compare the whole spine of the shipped day."""
    exp = _expected()
    for name in FAM_CORE:
        assert _got(name) == exp[name], "spine artifact differs: " + name


def _assert_shipped_family(names) -> None:
    exp = _expected()
    for name in names:
        assert _got(name) == exp[name], "artifact differs: " + name


def _assert_exact_inventory(root: Path, expected: set[str]) -> None:
    assert root.is_dir(), "output directory is absent: " + str(root)
    actual = {path.name for path in root.iterdir()}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    assert actual == expected, (
        "output inventory differs in %s: missing=%s; extra=%s"
        % (root, missing, extra))


def _assert_case_core(seed: int) -> None:
    exp = _expected(seed)
    for name in FAM_CORE:
        assert _case_got(seed, name) == exp[name], (
            "the program spine differs on the minted day: " + name)
    _assert_exact_inventory(_program_case(seed)["out"], set(ARTIFACTS))


def _assert_case_family(seed: int, names) -> None:
    exp = _expected(seed)
    for name in names:
        assert _case_got(seed, name) == exp[name], (
            "the program %s differs on the minted day" % name)


# --------------------------------------------------------------------------
# tier one: the existence floor
# --------------------------------------------------------------------------
def _a_all_artifacts_exist():
    """POSITIVE: every declared artifact and the conform program are present
    in the output directory."""
    _assert_exact_inventory(OUT_DIR, set(ARTIFACTS) | {PROGRAM_NAME})
    missing = [name for name in ARTIFACTS if not (OUT_DIR / name).is_file()]
    assert not missing, "artifacts absent: " + ", ".join(missing)
    assert PROGRAM.is_file(), "the conform program is absent: " + PROGRAM_NAME
    assert PROGRAM.stat().st_size > 0, "the conform program is empty"


def _a_core_documents_parse():
    """POSITIVE: the json, jsonl, xml and delimited artifacts parse and
    carry the header rows the schema reference publishes."""
    for name in ARTIFACTS:
        if name.endswith(".json"):
            json.loads(_got_text(name))
        elif name.endswith(".jsonl"):
            for line in _got_text(name).splitlines():
                if line.strip():
                    json.loads(line)
    ET.fromstring(_got_text("reconciliation.xml"))
    exp = _expected()
    for name in ARTIFACTS:
        if name.endswith((".csv", ".tsv", ".psv")):
            header = _got_text(name).splitlines()[0]
            wanted = exp[name].decode("utf-8").splitlines()[0]
            assert header == wanted, "wrong header row on " + name
    assert _got_text("playout_schedule.ini").startswith("[channel]")


# --------------------------------------------------------------------------
# tier two: the shipped transmission day, graded byte for byte
# --------------------------------------------------------------------------
def _a_shipped_core_exact():
    """POSITIVE: all seventeen spine artifacts of the shipped day are byte
    exact."""
    _assert_full_core()


def _a_shipped_conform_family_exact():
    """POSITIVE: the playout schedule and reconciliation of the shipped day
    are byte exact."""
    _assert_shipped_family(FAM_CONFORM)


def _a_shipped_avail_family_exact():
    """POSITIVE: the four per-market avail files of the shipped day are byte
    exact."""
    _assert_shipped_family(FAM_AVAIL)


def _a_shipped_money_family_exact():
    """POSITIVE: the two reports of the shipped day are byte exact."""
    _assert_shipped_family(FAM_MONEY)


# --------------------------------------------------------------------------
# tier three: the delivered program against days it has never seen
# --------------------------------------------------------------------------
def _a_program_default_paths_exact():
    """POSITIVE: a run with neither --data nor --out reads /app/data and
    writes the exact artifacts to /app/out.

    The verifier container carries no /app/data, so the check stages one
    itself and puts back only what was there before. The staged day is
    DEFAULT_SEED, which no other check grades, so this weight pays for the
    container defaults on a fourth unseen day and never for a day the
    --data/--out checks already pay for."""
    app_root = OUT_DIR.parent
    default_data = app_root / "data"
    assert app_root == Path("/app"), "default-path check requires the /app workspace"
    assert OUT_DIR.is_dir(), "default output directory is absent"
    assert PROGRAM.is_file(), "required deliverable is absent: " + PROGRAM_NAME

    staging = Path(tempfile.mkdtemp(prefix=".playout-defaults-", dir=app_root))
    saved_data = staging / "data"
    saved_out = staging / "out"
    had_data = default_data.exists()
    if had_data:
        os.replace(default_data, saved_data)
    os.replace(OUT_DIR, saved_out)
    try:
        shutil.copytree(_corpus(DEFAULT_SEED), default_data)
        OUT_DIR.mkdir()
        shutil.copy2(saved_out / PROGRAM_NAME, PROGRAM)
        _open_to_the_runner(default_data)
        os.chmod(OUT_DIR, 0o1777)
        os.chmod(PROGRAM, 0o644)
        before = _tree_digest(default_data)
        try:
            rc, err = _run_isolated([sys.executable, str(PROGRAM)], cwd=str(app_root))
        except subprocess.TimeoutExpired:
            raise AssertionError(
                "the no-argument program run did not finish within the time allowed")
        assert rc == 0, "the no-argument program run failed: " + err
        assert before == _tree_digest(default_data), (
            "the no-argument program run modified /app/data")
        _assert_exact_inventory(OUT_DIR, set(ARTIFACTS) | {PROGRAM_NAME})
        expected = _expected(DEFAULT_SEED)
        for name in ARTIFACTS:
            assert (OUT_DIR / name).read_bytes() == expected[name], (
                "default-path artifact differs: " + name)
    finally:
        if default_data.exists():
            shutil.rmtree(default_data)
        if OUT_DIR.exists():
            shutil.rmtree(OUT_DIR)
        if had_data:
            os.replace(saved_data, default_data)
        os.replace(saved_out, OUT_DIR)
        staging.rmdir()


def _a_program_eval_core_exact():
    """POSITIVE: the program reproduces the core of a dense day it has never
    seen."""
    _assert_case_core(EVAL_SEED)


def _a_program_eval_conform_exact():
    """POSITIVE: the program reproduces the conform family of a dense day."""
    _assert_case_family(EVAL_SEED, FAM_CONFORM)


def _a_program_eval_avail_exact():
    """POSITIVE: the program reproduces the avail family of a dense day."""
    _assert_case_family(EVAL_SEED, FAM_AVAIL)


def _a_program_eval_money_exact():
    """POSITIVE: the program reproduces the money family of a dense day."""
    _assert_case_family(EVAL_SEED, FAM_MONEY)


def _a_program_challenge_core_exact():
    """POSITIVE: the program reproduces the core of a sparse day it has
    never seen."""
    _assert_case_core(CHALLENGE_SEED)


def _a_program_challenge_conform_exact():
    """POSITIVE: the program reproduces the conform family of a sparse
    day."""
    _assert_case_family(CHALLENGE_SEED, FAM_CONFORM)


def _a_program_challenge_avail_exact():
    """POSITIVE: the program reproduces the avail family of a sparse day."""
    _assert_case_family(CHALLENGE_SEED, FAM_AVAIL)


def _a_program_challenge_money_exact():
    """POSITIVE: the program reproduces the money family of a sparse day."""
    _assert_case_family(CHALLENGE_SEED, FAM_MONEY)


def _a_program_probe_core_exact():
    """POSITIVE: the program reproduces the core of a third minted day."""
    _assert_case_core(PROBE_SEED)


def _a_program_probe_conform_exact():
    """POSITIVE: the program reproduces the conform family of a third minted
    day."""
    _assert_case_family(PROBE_SEED, FAM_CONFORM)


def _a_program_probe_avail_exact():
    """POSITIVE: the program reproduces the avail family of a third minted
    day."""
    _assert_case_family(PROBE_SEED, FAM_AVAIL)


def _a_program_probe_money_exact():
    """POSITIVE: the program reproduces the money family of a third minted
    day."""
    _assert_case_family(PROBE_SEED, FAM_MONEY)


# --------------------------------------------------------------------------
# tier four: the deliveries that are not a derivation
#
# Each of these fires on a delivery that cannot have been computed from the
# day it was handed, and each refuses to fire when the delivered bytes are
# correct. A wrong reading of a stated rule is not charged here: it already
# forfeits the spine and the families that publish it, and charging it twice
# would put an honest mistake below an empty submission.
# --------------------------------------------------------------------------
def _a_program_lead_drop_exact():
    """POSITIVE: on a minted day whose first scheduled slot has no canonical
    asset, the delivered program writes exactly the twenty five artifacts
    and every one of them is byte exact.

    R17 drops that slot and it occupies no time, so the slots after it move
    up: the floating slot that now leads the day starts where the slot
    before it ended, which is the day start, and the next fixed junction
    corrects whatever the running day is off by. Promoting the first placed slot to a fixed
    junction pinned at its own scheduled label puts a filler in front of a
    floating slot, which CR_FILL_INSERT never describes, and moves every
    slot, break and spot that follows."""
    exp = _expected(LEAD_DROP_SEED)
    for name in ARTIFACTS:
        assert _case_got(LEAD_DROP_SEED, name) == exp[name], (
            "the program %s differs on the day whose lead slot is dropped" % name)
    _assert_exact_inventory(_program_case(LEAD_DROP_SEED)["out"], set(ARTIFACTS))


def _a_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: the shipped day is right and the program is wrong on every
    minted day, which is what copying the answer looks like.

    Two guards keep an honest mistake out of this charge. The shipped side
    reads the whole spine rather than the seven core files, and the minted
    side requires every one of the three minted days to be wrong rather than
    one. A single bug that only shows under one profile leaves at least one
    minted day right, so it forfeits weight without being charged as a copy;
    a delivery that reproduces the day it was shown and fails all three days
    it was not cannot have derived anything.
    """
    exp = _expected()
    shipped_ok = all(_got(name) == exp[name] for name in FAM_CORE)
    wrong_days = 0
    for seed in (EVAL_SEED, CHALLENGE_SEED, PROBE_SEED):
        other = _expected(seed)
        if any(_case_got(seed, name) != other[name] for name in CORE_FILES):
            wrong_days += 1
    # Holds only when the copy happened; the negative weight does the punishing.
    assert shipped_ok and wrong_days == 3


def _a_manifest_digest_matches_core():
    """POSITIVE: on a day minted for this check alone, the digest the
    delivered program publishes in the manifest is the digest that day's
    derived core entails, and it also covers the core the program wrote.

    Both halves are needed. Hashing only the written bytes is satisfied by
    any self-consistent set, so a core with a matching digest would earn
    this without deriving anything. No other check reads this day, so the
    digest is paid once; the shipped manifest is read whole by the spine.
    """
    exp = _expected(DIGEST_SEED)
    wanted = hashlib.sha256()
    written = hashlib.sha256()
    for name in CORE_FILES:
        wanted.update(exp[name])
        written.update(_case_got(DIGEST_SEED, name, tag="digest"))
    manifest = _case_got(DIGEST_SEED, "manifest.json", tag="digest")
    published = json.loads(manifest.decode("utf-8")).get("digest")
    assert published == wanted.hexdigest(), (
        "the manifest digest is not the digest the derived core entails")
    assert published == written.hexdigest(), (
        "the manifest digest does not cover the core the program wrote")


def _a_negative_weight_program_ignores_its_input():
    """NEGATIVE: two different minted days produce the same core, from a
    delivery whose own shipped day is wrong.

    The second condition keeps this detector disjoint from the copied answer
    detector above. A delivery that reproduces the shipped day and ignores
    its input is one decision, and it is charged once, there. What is left
    here is a program that ignores its input without even reaching the
    shipped answer, which is a different delivery."""
    exp = _expected()
    if all(_got(name) == exp[name] for name in FAM_CORE):
        raise AssertionError(
            "the shipped day is byte exact; the copied answer detector owns "
            "this delivery and this one must not fire as well")
    a = [_case_got(EVAL_SEED, name) for name in CORE_FILES]
    b = [_case_got(CHALLENGE_SEED, name) for name in CORE_FILES]
    # Holds only when the input was ignored; the negative weight does the punishing.
    assert a == b


def _a_negative_weight_nondeterministic_output():
    """NEGATIVE: two runs over one byte identical day disagree.

    Every published artifact is compared, not only the seven core ones: the
    instruction promises that two runs over the same inputs produce the same
    bytes, and it promises it of everything the program writes."""
    differing = []
    for name in ARTIFACTS:
        first, second = _repeat_got(SAMPLE_SEED, name)
        if first != second:
            differing.append(name)
    # Holds only when the two runs disagree; the negative weight does the punishing.
    assert differing


def _a_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: the same day under a different directory name produces a
    different core.

    Two runs under different names are also two runs, so a delivery whose
    output already differs between two runs over one day under one name
    would trip this detector without depending on any name. That delivery is
    charged by the nondeterminism detector, so this one stands down for it
    rather than charging the same decision twice."""
    try:
        repeat = [_repeat_got(SAMPLE_SEED, name) for name in ARTIFACTS]
    except AssertionError:
        repeat = []
    if any(first != second for first, second in repeat):
        raise AssertionError(
            "two runs over one day already disagree; the nondeterminism "
            "detector owns this delivery and this one must not fire as well")
    differing = []
    for name in CORE_FILES:
        if _case_got(PROBE_SEED, name, tag="case") != \
                _case_got(PROBE_SEED, name, tag=STDLIB_ONLY_TAG):
            differing.append(name)
    # Holds only when the directory name changed the core; the negative weight punishes.
    assert differing


def _a_negative_weight_program_needs_a_third_party_package():
    """NEGATIVE: the delivered program completes a minted day on the full
    interpreter but stops on an import when the same day is run with nothing
    beyond the Python standard library importable."""
    plain = _program_case(PROBE_SEED)
    if plain["rc"] != 0:
        raise AssertionError(
            "the program failed on the minted day; there is no working run to compare")
    bare = _program_case(PROBE_SEED, tag=STDLIB_ONLY_TAG)
    # Holds only when an import outside the standard library stopped the run;
    # the negative weight does the punishing.
    assert bare["rc"] != 0 and ("ModuleNotFoundError" in bare["stderr"]
                                or "ImportError" in bare["stderr"])


def _a_negative_weight_program_dirties_its_directories():
    """NEGATIVE: the program writes into the day it was given to read."""
    dirtied = []
    for seed in (EVAL_SEED, CHALLENGE_SEED, PROBE_SEED):
        case = _program_case(seed)
        if case["before"] != case["after"]:
            dirtied.append(str(seed))
    # Holds only when an input tree changed; the negative weight does the punishing.
    assert dirtied


def _a_negative_weight_reads_training_corpus_at_runtime():
    """NEGATIVE: a day is planted in a directory named for the container
    path and the program reports that day instead of the one it was
    given."""
    case = _program_planted(EVAL_SEED)
    if case["rc"] != 0:
        raise AssertionError("the program failed on the planted day")
    wanted = _expected(EVAL_SEED)
    got = {}
    for name in CORE_FILES:
        path = case["out"] / name
        if not path.is_file():
            raise AssertionError("the program wrote no " + name)
        got[name] = path.read_bytes()
    if all(got[name] == wanted[name] for name in CORE_FILES):
        raise AssertionError(
            "the program read the day it was given; the detector must not fire")
    planted = _expected(PLANT_SEED)
    # Holds only when the planted day was reported; the negative weight punishes.
    assert all(got[name] == planted[name] for name in CORE_FILES)


def _a_negative_weight_program_writes_outside_its_out_dir():
    """NEGATIVE: on a minted day the program leaves a file or directory in
    its working directory, outside the output directory it was told to
    write to and outside the day it was given."""
    stray = []
    for seed in (EVAL_SEED, CHALLENGE_SEED, PROBE_SEED):
        stray.extend(_program_case(seed)["stray"])
    # Holds only when something was written outside --out; the negative weight punishes.
    assert stray


# --------------------------------------------------------------------------
# corpus staging, used when this module is run directly at authoring time
# --------------------------------------------------------------------------
def _write_corpus(seed: int, out_dir) -> dict:
    return generate(seed, Path(out_dir))


def main() -> int:
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--write-corpus":
        seed = int(args[2]) if len(args) > 2 else SAMPLE_SEED
        facts = _write_corpus(seed, args[1])
        print("wrote the %s day into %s" % (facts["profile"], args[1]))
        return 0
    print("nothing to do; pass --write-corpus and a directory")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ==========================================================================
# rewardkit registration
#
# Every check keeps the body it had: the assertions are the detail a failing
# criterion reports. _graded turns a raised assertion into False, which is
# what a rewardkit criterion must return, and binds the output directory to
# the workspace the harness hands in rather than to a fixed path.
# ==========================================================================


_GRADING_LOCK = threading.Lock()


def _graded(workspace, check) -> bool:
    global OUT_DIR, PROGRAM
    # rewardkit runs criteria on worker threads of one process, and the
    # default-path check moves /app/out aside while it runs, so every check
    # holds this lock for its whole body.
    with _GRADING_LOCK:
        OUT_DIR = Path(workspace) / "out"
        PROGRAM = OUT_DIR / PROGRAM_NAME
        try:
            check()
        except Exception:
            return False
        return True


@criterion(description="every declared artifact and the conform program are present in the output directory")
def all_artifacts_exist(workspace: Path) -> bool:
    return _graded(workspace, _a_all_artifacts_exist)


@criterion(description="the json, jsonl and xml artifacts parse and every delimited artifact opens with its published header row")
def core_documents_parse(workspace: Path) -> bool:
    return _graded(workspace, _a_core_documents_parse)


@criterion(description="on a day minted for this check alone the manifest digest equals the digest the derived core entails and the digest of the core the program wrote")
def manifest_digest_matches_core(workspace: Path) -> bool:
    return _graded(workspace, _a_manifest_digest_matches_core)


@criterion(description="the core spine of the shipped transmission day is byte exact")
def shipped_core_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_shipped_core_exact)


@criterion(description="the playout schedule and reconciliation of the shipped day are byte exact")
def shipped_conform_family_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_shipped_conform_family_exact)


@criterion(description="the four per market avail files of the shipped day are byte exact")
def shipped_avail_family_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_shipped_avail_family_exact)


@criterion(description="the day report and compliance summary of the shipped day are byte exact")
def shipped_money_family_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_shipped_money_family_exact)


@criterion(description="the delivered program writes exactly the twenty five artifacts for a dense day it has never seen, with the core spine byte exact")
def program_eval_core_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_eval_core_exact)


@criterion(description="a no-argument run reads /app/data and writes the exact artifacts of a fourth unseen day to /app/out")
def program_default_paths_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_default_paths_exact)


@criterion(description="the delivered program reproduces the conform family of a dense day it has never seen")
def program_eval_conform_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_eval_conform_exact)


@criterion(description="the delivered program reproduces the avail family of a dense day it has never seen")
def program_eval_avail_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_eval_avail_exact)


@criterion(description="the delivered program reproduces the money family of a dense day it has never seen")
def program_eval_money_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_eval_money_exact)


@criterion(description="the delivered program writes exactly the twenty five artifacts for a sparse day it has never seen, with the core spine byte exact")
def program_challenge_core_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_challenge_core_exact)


@criterion(description="the delivered program reproduces the conform family of a sparse day it has never seen")
def program_challenge_conform_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_challenge_conform_exact)


@criterion(description="the delivered program reproduces the avail family of a sparse day it has never seen")
def program_challenge_avail_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_challenge_avail_exact)


@criterion(description="the delivered program reproduces the money family of a sparse day it has never seen")
def program_challenge_money_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_challenge_money_exact)


@criterion(description="the delivered program writes exactly the twenty five artifacts for a third minted day, with the core spine byte exact")
def program_probe_core_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_probe_core_exact)


@criterion(description="the delivered program reproduces the conform family of a third minted day")
def program_probe_conform_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_probe_conform_exact)


@criterion(description="the delivered program reproduces the avail family of a third minted day")
def program_probe_avail_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_probe_avail_exact)


@criterion(description="the delivered program reproduces the money family of a third minted day")
def program_probe_money_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_probe_money_exact)


@criterion(description="the delivered program reproduces every artifact of a minted day whose first scheduled slot is dropped")
def program_lead_drop_exact(workspace: Path) -> bool:
    return _graded(workspace, _a_program_lead_drop_exact)


@criterion(description="the shipped spine is byte exact while the program is wrong on all three minted days")
def negative_weight_hardcoded_sample_answers(workspace: Path) -> bool:
    return _graded(workspace, _a_negative_weight_hardcoded_sample_answers)


@criterion(description="two different minted days produce the same core from a delivery whose own day is wrong")
def negative_weight_program_ignores_its_input(workspace: Path) -> bool:
    return _graded(workspace, _a_negative_weight_program_ignores_its_input)


@criterion(description="two runs over one byte identical day disagree")
def negative_weight_nondeterministic_output(workspace: Path) -> bool:
    return _graded(workspace, _a_negative_weight_nondeterministic_output)


@criterion(description="the same day under a different directory name produces a different core")
def negative_weight_filename_dependent_behaviour(workspace: Path) -> bool:
    return _graded(workspace, _a_negative_weight_filename_dependent_behaviour)


@criterion(description="the program completes a minted day but stops on an import once only the standard library is importable")
def negative_weight_program_needs_a_third_party_package(workspace: Path) -> bool:
    return _graded(workspace, _a_negative_weight_program_needs_a_third_party_package)


@criterion(description="the program writes into the day it was given to read")
def negative_weight_program_dirties_its_directories(workspace: Path) -> bool:
    return _graded(workspace, _a_negative_weight_program_dirties_its_directories)


@criterion(description="the program reports a day planted at the container path instead of the day it was given")
def negative_weight_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    return _graded(workspace, _a_negative_weight_reads_training_corpus_at_runtime)


@criterion(description="the program leaves a file outside the output directory it was told to write to")
def negative_weight_program_writes_outside_its_out_dir(workspace: Path) -> bool:
    return _graded(workspace, _a_negative_weight_program_writes_outside_its_out_dir)


criteria.all_artifacts_exist(weight=1)
criteria.core_documents_parse(weight=1)
criteria.manifest_digest_matches_core(weight=3)
criteria.shipped_core_exact(weight=3)
criteria.shipped_conform_family_exact(weight=3)
criteria.shipped_avail_family_exact(weight=3)
criteria.shipped_money_family_exact(weight=3)
criteria.program_default_paths_exact(weight=3)
criteria.program_eval_core_exact(weight=5)
criteria.program_eval_conform_exact(weight=5)
criteria.program_eval_avail_exact(weight=5)
criteria.program_eval_money_exact(weight=5)
criteria.program_challenge_core_exact(weight=5)
criteria.program_challenge_conform_exact(weight=5)
criteria.program_challenge_avail_exact(weight=5)
criteria.program_challenge_money_exact(weight=5)
criteria.program_probe_core_exact(weight=5)
criteria.program_probe_conform_exact(weight=5)
criteria.program_probe_avail_exact(weight=5)
criteria.program_probe_money_exact(weight=5)
criteria.program_lead_drop_exact(weight=5)
criteria.negative_weight_hardcoded_sample_answers(weight=-3)
criteria.negative_weight_program_ignores_its_input(weight=-3)
criteria.negative_weight_nondeterministic_output(weight=-3)
criteria.negative_weight_filename_dependent_behaviour(weight=-3)
criteria.negative_weight_program_needs_a_third_party_package(weight=-3)
criteria.negative_weight_program_dirties_its_directories(weight=-3)
criteria.negative_weight_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_weight_program_writes_outside_its_out_dir(weight=-3)
