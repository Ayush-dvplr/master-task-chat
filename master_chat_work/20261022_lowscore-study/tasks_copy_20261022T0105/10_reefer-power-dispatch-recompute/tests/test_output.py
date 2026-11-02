"""Deterministic verifier for the reefer yard power dispatch task.

The verifier owns its corpus. It regenerates the whole working paper tree from
a named seed into a temporary directory, recomputes every published document
from that regeneration, and grades the agent bytes under the output directory
against it. It never reads the agent corpus, which does not exist in this
container.

Most of the positive weight is spent on the delivered program rather than on
the delivered bytes. Three further operating days are minted here from seeds
the agent never sees, one under a strained feeder profile, one under a wide
profile and one under a sparse profile the shipped day does not use, and the
delivered dispatch program is run against each of them as a subprocess. Its
output is graded byte for byte against the publication those papers entail.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

# Imports the corpus generator and the grading half need. The reference
# pipeline needs none of them, so the delivered program carries no import it
# does not use.
import os
import shutil
import sqlite3
import tokenize
import subprocess
import tempfile
import threading

from rewardkit import criteria, criterion

OUTPUT_ROOT = "/app/out"
PROGRAM_NAME = "reeferdispatch.py"

SUBSTATIONS = ["sb_alder", "sb_bourne", "sb_calloway"]

# One published observable per stage, plus the manifest that digests the whole
# publication.
FAMILY_CORE = [
    "normalised_reefers.jsonl",
    "availability_lattice.csv",
    "energy_floor_ledger.csv",
    "dispatch_priority_queue.csv",
    "provisional_allocation.psv",
    "feeder_violation_ledger.csv",
    "crane_adjusted_capacity.csv",
    "battery_schedule.csv",
    "reconciliation_iterations.csv",
    "tariff_charge_ledger.csv",
    "deadline_correction.csv",
    "cycle_break_report.json",
    "objective_vector.json",
    "final_schedule.csv",
    "publication_manifest.json",
]

FAMILY_LOAD = [
    "interval_demand.csv",
    "feeder_load_ledger.csv",
    "spill_decisions.tsv",
    "soc_ledger.psv",
    "constraint_certificate.json",
]

FAMILY_TARIFF = [
    "peak_demand_certificate.json",
    "unmet_requirement_report.tsv",
    "reefer_service_certificate.csv",
    "audit_trace.jsonl",
    "dispatch_control_totals.conf",
]

FAMILY_PUBLICATION = [
    "final_schedule_by_feeder.psv",
    "final_schedule_by_vessel.xml",
    "substation_report_sb_alder.json",
    "substation_report_sb_bourne.json",
    "substation_report_sb_calloway.json",
    "daily_dispatch_summary.md",
]

ALL_DOCUMENTS = FAMILY_CORE + FAMILY_LOAD + FAMILY_TARIFF + FAMILY_PUBLICATION

# Stage ordered scoring blocks. They partition the publication: every document
# sits in exactly one block and no block is gated on another, so a stage read
# the wrong way costs the blocks that stage feeds and leaves every earlier
# block banked. Full reward still needs every block of every operating day.
BLOCK_P01_P02 = ["normalised_reefers.jsonl", "availability_lattice.csv",
                 "interval_demand.csv"]
BLOCK_P03_P04 = ["energy_floor_ledger.csv", "dispatch_priority_queue.csv"]
BLOCK_P05_P06 = ["provisional_allocation.psv", "feeder_load_ledger.csv",
                 "feeder_violation_ledger.csv", "spill_decisions.tsv"]
BLOCK_P07_P09 = ["crane_adjusted_capacity.csv", "battery_schedule.csv",
                 "soc_ledger.psv", "reconciliation_iterations.csv"]
BLOCK_P10_P14 = ["tariff_charge_ledger.csv", "peak_demand_certificate.json",
                 "deadline_correction.csv", "unmet_requirement_report.tsv",
                 "cycle_break_report.json", "objective_vector.json",
                 "constraint_certificate.json", "final_schedule.csv",
                 "reefer_service_certificate.csv", "audit_trace.jsonl",
                 "dispatch_control_totals.conf",
                 "final_schedule_by_feeder.psv", "final_schedule_by_vessel.xml",
                 "substation_report_sb_alder.json",
                 "substation_report_sb_bourne.json",
                 "substation_report_sb_calloway.json",
                 "daily_dispatch_summary.md", "publication_manifest.json"]

SHIPPED_BLOCKS = [BLOCK_P01_P02, BLOCK_P03_P04, BLOCK_P05_P06,
                  BLOCK_P07_P09, BLOCK_P10_P14]
PROGRAM_EARLY = BLOCK_P01_P02 + BLOCK_P03_P04 + BLOCK_P05_P06
PROGRAM_MIDDLE = list(BLOCK_P07_P09)
PROGRAM_LATE = list(BLOCK_P10_P14)

# The module asserts the partition rather than trusting it.
_PARTITION = [name for block in SHIPPED_BLOCKS for name in block]
if sorted(_PARTITION) != sorted(ALL_DOCUMENTS) or len(_PARTITION) != len(set(_PARTITION)):
    raise RuntimeError("the scoring blocks do not partition the publication")

# The six documents the core digest of the publication manifest covers.
CORE_DOCUMENTS = [
    "normalised_reefers.jsonl",
    "energy_floor_ledger.csv",
    "provisional_allocation.psv",
    "reconciliation_iterations.csv",
    "objective_vector.json",
    "final_schedule.csv",
]

INTERVAL_COUNT = 96
INTERVAL_MINUTES = 15

SAMPLE_SEED = 4193067712
EVAL_SEED = 6218455093
CHALLENGE_SEED = 7331566104
PROBE_SEED = 8442677215

SEED_PROFILE = {
    SAMPLE_SEED: "shipped",
    EVAL_SEED: "strained",
    CHALLENGE_SEED: "wide",
    PROBE_SEED: "sparse",
}

MINTED_SEEDS = [EVAL_SEED, CHALLENGE_SEED, PROBE_SEED]

# --------------------------------------------------------------------------
# delimited and structured writers
# --------------------------------------------------------------------------


def _join(sep: str, values) -> str:
    return sep.join("" if v is None else str(v) for v in values)


def write_rows(path, header, rows, sep):
    lines = [_join(sep, header)]
    for row in rows:
        lines.append(_join(sep, row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_lines(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path, records):
    out = []
    for rec in records:
        out.append(json.dumps(rec, separators=(",", ":"), sort_keys=False))
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------
# spreadsheet writer (minimal, stdlib only, real OOXML)
# --------------------------------------------------------------------------


def _cell_ref(col: int, row: int) -> str:
    name = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        name = chr(65 + rem) + name
    return "%s%d" % (name, row)


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;"))


def _sheet_xml(rows: list, shared: list, shared_idx: dict) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    out.append('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
    out.append("<sheetData>")
    for ri, row in enumerate(rows, start=1):
        out.append('<row r="%d">' % ri)
        for ci, val in enumerate(row, start=1):
            if val is None or val == "":
                continue
            ref = _cell_ref(ci, ri)
            sval = str(val)
            is_num = True
            try:
                int(sval)
            except ValueError:
                is_num = False
            if is_num:
                out.append('<c r="%s"><v>%s</v></c>' % (ref, sval))
            else:
                if sval not in shared_idx:
                    shared_idx[sval] = len(shared)
                    shared.append(sval)
                out.append('<c r="%s" t="s"><v>%d</v></c>' % (ref, shared_idx[sval]))
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(path, sheets: dict) -> None:
    shared: list = []
    shared_idx: dict = {}
    sheet_xmls = [(name, _sheet_xml(rows, shared, shared_idx)) for name, rows in sheets.items()]

    ss = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ss.append('<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              'count="%d" uniqueCount="%d">' % (len(shared), len(shared)))
    for item in shared:
        ss.append("<si><t xml:space=\"preserve\">%s</t></si>" % _xml_escape(item))
    ss.append("</sst>")

    ctypes = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ctypes.append('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">')
    ctypes.append('<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>')
    ctypes.append('<Default Extension="xml" ContentType="application/xml"/>')
    ctypes.append('<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>')
    ctypes.append('<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>')
    for i, _ in enumerate(sheet_xmls, start=1):
        ctypes.append('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % i)
    ctypes.append("</Types>")

    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 "</Relationships>")

    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb.append('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">')
    wb.append("<sheets>")
    for i, (name, _) in enumerate(sheet_xmls, start=1):
        wb.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_xml_escape(name), i, i))
    wb.append("</sheets></workbook>")

    wb_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb_rels.append('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">')
    for i, _ in enumerate(sheet_xmls, start=1):
        wb_rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i, i))
    wb_rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>' % (len(sheet_xmls) + 1))
    wb_rels.append("</Relationships>")

    entries = [
        ("[Content_Types].xml", "".join(ctypes)),
        ("_rels/.rels", root_rels),
        ("xl/workbook.xml", "".join(wb)),
        ("xl/_rels/workbook.xml.rels", "".join(wb_rels)),
        ("xl/sharedStrings.xml", "".join(ss)),
    ]
    for i, (_, xml) in enumerate(sheet_xmls, start=1):
        entries.append(("xl/worksheets/sheet%d.xml" % i, xml))

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, payload)


# --------------------------------------------------------------------------
# word processing writer (minimal, stdlib only, real OOXML)
# --------------------------------------------------------------------------


def _docx_paragraph(text: str) -> str:
    return ('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % _xml_escape(text))


def _docx_table(rows: list) -> str:
    out = ['<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>']
    for row in rows:
        out.append("<w:tr>")
        for cell in row:
            out.append('<w:tc><w:tcPr><w:tcW w:w="1800" w:type="dxa"/></w:tcPr>'
                       '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
                       % _xml_escape(str(cell)))
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def write_docx(path, blocks: list) -> None:
    """blocks is a list of ('p', text) and ('table', rows) pairs."""
    body = []
    for kind, payload in blocks:
        if kind == "p":
            body.append(_docx_paragraph(payload))
        else:
            body.append(_docx_table(payload))
            body.append(_docx_paragraph(""))
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>" + "".join(body) +
                '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'
                "</w:body></w:document>")

    ctypes = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/>'
              '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
              "</Types>")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                 "</Relationships>")
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')

    entries = [
        ("[Content_Types].xml", ctypes),
        ("_rels/.rels", root_rels),
        ("word/document.xml", document),
        ("word/_rels/document.xml.rels", doc_rels),
    ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, payload)


# --------------------------------------------------------------------------
# pdf writer (minimal, stdlib only, real PDF 1.4, no embedded timestamp)
# --------------------------------------------------------------------------


def write_pdf(path, lines: list) -> None:
    def esc(t: str) -> str:
        return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    pages = [lines[i:i + 52] for i in range(0, len(lines), 52)] or [[""]]
    objects: list = []
    n_pages = len(pages)
    font_obj = 3 + 2 * n_pages
    kids = " ".join("%d 0 R" % (3 + 2 * i) for i in range(n_pages))
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n_pages))
    for i, page_lines in enumerate(pages):
        content = "BT /F1 9 Tf 34 754 Td 11 TL\n"
        for ln in page_lines:
            content += "(%s) Tj T*\n" % esc(ln)
        content += "ET"
        cbytes = content.encode("latin-1", "replace")
        page_obj = 3 + 2 * i
        objects.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       "/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                       % (font_obj, page_obj + 1))
        objects.append((cbytes, "<< /Length %d >>" % len(cbytes)))
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        if isinstance(obj, tuple):
            cbytes, hdr = obj
            out.write(("%d 0 obj\n%s\nstream\n" % (i, hdr)).encode("latin-1"))
            out.write(cbytes)
            out.write(b"\nendstream\nendobj\n")
        else:
            out.write(("%d 0 obj\n%s\nendobj\n" % (i, obj)).encode("latin-1"))
    xref_pos = out.tell()
    n = len(objects) + 1
    out.write(("xref\n0 %d\n" % n).encode("latin-1"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(("%010d 00000 n \n" % off).encode("latin-1"))
    out.write(("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
               % (n, xref_pos)).encode("latin-1"))
    path.write_bytes(out.getvalue())


def write_sqlite(path, tables: dict) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    for tname, (cols, rows) in tables.items():
        cur.execute("CREATE TABLE %s (%s)" % (tname, ", ".join("%s TEXT" % c for c in cols)))
        ph = ", ".join("?" for _ in cols)
        cur.executemany("INSERT INTO %s VALUES (%s)" % (tname, ph), rows)
    con.commit()
    con.close()

# --------------------------------------------------------------------------
# deterministic rng
#
# The random module of CPython is not contractually stable across releases, so
# the corpus is minted from a xorshift64 the module owns.
# --------------------------------------------------------------------------


class Rng:
    """xorshift64star, fully specified so a regeneration reproduces bytes."""

    def __init__(self, seed):
        s = seed & 0xFFFFFFFFFFFFFFFF
        self.state = s if s else 0x9E3779B97F4A7C15

    def _next(self):
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x & 0xFFFFFFFFFFFFFFFF
        return (self.state * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def below(self, n):
        if n <= 0:
            raise ValueError("bound must be positive")
        return self._next() % n

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def pick(self, items):
        return items[self.below(len(items))]

    def chance(self, num, den):
        return self.below(den) < num

    def shuffled(self, items):
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = self.below(i + 1)
            out[i], out[j] = out[j], out[i]
        return out


# --------------------------------------------------------------------------
# closed vocabularies
# --------------------------------------------------------------------------

TEMP_CLASSES = ["frozen", "chilled", "deep_frozen", "pharma", "banana"]
POWER_UNITS = ["wh_h", "kwh_h", "mj_h"]
ENERGY_UNITS = ["wh", "kwh", "mj"]
TARIFF_BANDS = ["off_peak", "shoulder", "peak", "super_peak"]
AMBIENT_CLASSES = ["cool", "temperate", "warm", "hot"]
SERVICE_GROUPS = ["sg_north", "sg_levant", "sg_gulf", "sg_baltic"]
PLUG_ZONES = ["standard", "reefer", "hazard"]
ZONE_CYCLE = ["reefer", "standard", "reefer", "hazard"]
DUTY_STATES = ["hoisting", "traversing", "idle", "gantry"]
DESTINATIONS = ["PT_ALKENA", "PT_BRESHOR", "PT_CIRVAL", "PT_DUNMARK",
                "PT_ESKHOLM", "PT_FARNWAY"]
VESSEL_WORDS = ["alba", "borre", "cendal", "durran", "esker", "fenn",
                "gullane", "hesper", "ivell", "jarrow", "kelso", "lorne"]

# The order the admission ladder is read in. The first rung that catches a
# reefer settles it, and this order is not the alphabetical order of the rung
# codes.
LADDER_RUNGS = [
    "DR_UNKNOWN_PLUG",
    "DR_FEEDER_OUT_OF_FORCE",
    "DR_WINDOW_EMPTY",
    "DR_UNKNOWN_POWER_UNIT",
    "DR_PLUG_ZONE_REFUSED",
    "DR_DUPLICATE_CONNECTION",
]

REFUSAL_TEXT = {
    "DR_UNKNOWN_PLUG": "the reefer names a plug the plug assignment register does not carry",
    "DR_FEEDER_OUT_OF_FORCE": "the plug hangs off a feeder the substation topology omits",
    "DR_WINDOW_EMPTY": "the connection window covers no interval of the grid",
    "DR_UNKNOWN_POWER_UNIT": "the nameplate names a power unit the unit register does not carry",
    "DR_PLUG_ZONE_REFUSED": "the plug zone refuses the temperature class the reefer declares",
    "DR_DUPLICATE_CONNECTION": "an earlier reefer in the same cluster already took the plug",
}

PROFILES = {
    "shipped": {
        "soc_below_reserve": 0, "unknown_state_rows": 0, "band_floor_on_peak": False,
        "roster_order": [0, 1, 2],
        "reefers": 138, "feeders": 12, "vessels": 8, "cranes": 5,
        "capacity_scale": 66, "reserve_scale": 118, "crane_scale": 100,
        "sheet_index": 2, "names": 0, "soc_scale": 3, "charge_scale": 21, "discharge_scale": 27,
        "cycle_pair": True,
    },
    "strained": {
        "soc_below_reserve": 30000, "unknown_state_rows": 1, "band_floor_on_peak": False,
        "roster_order": [0, 1, 2],
        "reefers": 121, "feeders": 10, "vessels": 7, "cranes": 6,
        "capacity_scale": 26, "reserve_scale": 150, "crane_scale": 140,
        "sheet_index": 3, "names": 1, "soc_scale": 0, "charge_scale": 100, "discharge_scale": 100,
        "cycle_pair": False,
    },
    "wide": {
        "soc_below_reserve": 0, "unknown_state_rows": 0, "band_floor_on_peak": True,
        "roster_order": [2, 0, 1],
        "reefers": 166, "feeders": 15, "vessels": 10, "cranes": 4,
        "capacity_scale": 95, "reserve_scale": 126, "crane_scale": 96,
        "sheet_index": 1, "names": 2, "soc_scale": 220, "charge_scale": 100, "discharge_scale": 61,
        "cycle_pair": False,
    },
    "sparse": {
        "soc_below_reserve": 0, "unknown_state_rows": 0, "band_floor_on_peak": False,
        "roster_order": [1, 2, 0],
        "reefers": 96, "feeders": 9, "vessels": 6, "cranes": 3,
        "capacity_scale": 34, "reserve_scale": 112, "crane_scale": 118,
        "sheet_index": 4, "names": 3, "soc_scale": 100, "charge_scale": 64, "discharge_scale": 100,
        "cycle_pair": True,
    },
}

# Four sheet name pools, one per profile, drawn from one pool of six names so
# that a sheet name carries no information about which sheet is live. Across
# the four profiles the live sheet has four pairwise distinct file positions,
# four pairwise distinct sorted ranks and four distinct names, and it is never
# the first or the last sheet under either ordering. So no fixed reading of
# position, position from the end, sorted rank or name is right more than
# once, and every one of them is wrong on at least three profiles. The build
# asserts that property rather than trusting it.
SHEET_NAME_POOL = [
    ["Clearance", "Dispatch", "Berthing", "Allocation", "Equipment", "Forecast"],
    ["Equipment", "Allocation", "Forecast", "Clearance", "Berthing", "Dispatch"],
    ["Forecast", "Dispatch", "Allocation", "Equipment", "Berthing", "Clearance"],
    ["Berthing", "Forecast", "Clearance", "Allocation", "Equipment", "Dispatch"],
]

PROFILE_ORDER = ["shipped", "strained", "wide", "sparse"]

NOT_SUPPLIED = "-"


def _day_id(seed):
    return "AP-%d-D%03d" % (2040 + (seed % 9), 17 + (seed % 331))


def _day_reference(seed):
    return "DSP-%06d" % (seed % 1000000)


def _prior_days(seed, n):
    out = []
    for k in range(1, n + 1):
        out.append("AP-%d-D%03d" % (2040 + (seed % 9), 17 + (seed % 331) - k))
    return out


def mint_instance(seed, profile):
    """Build the whole operating day as data. Nothing here decides an answer;
    the reference pipeline derives every published quantity from these
    papers."""
    cfg = PROFILES[profile]
    rng = Rng(seed)
    inst = {
        "seed": seed,
        "profile": profile,
        "day_id": _day_id(seed),
        "day_reference": _day_reference(seed),
        "prior": _prior_days(seed, 3),
        "cfg": cfg,
    }
    _mint_grid(inst, rng, cfg)
    _mint_network(inst, rng, cfg)
    _mint_vessels(inst, rng, cfg)
    _mint_controls(inst, rng, cfg)
    _mint_reefers(inst, rng, cfg)
    _mint_energy_returns(inst, rng, cfg)
    _mint_cranes(inst, rng, cfg)
    _mint_maintenance(inst, rng, cfg)
    _mint_tariff(inst, rng, cfg)
    _mint_battery(inst, rng, cfg)
    _mint_exceptions(inst, rng, cfg)
    return inst


# --------------------------------------------------------------------------
# the interval grid
# --------------------------------------------------------------------------


def _mint_grid(inst, rng, cfg):
    """Ninety six quarter hour intervals. The ambient class walks slowly so a
    reefer sitting across a class change picks up two multipliers."""
    intervals = []
    ambient = 0
    for n in range(1, INTERVAL_COUNT + 1):
        if n <= 24:
            band = "off_peak"
        elif n <= 40:
            band = "shoulder"
        elif n <= 60:
            band = "peak"
        elif n <= 76:
            band = "shoulder"
        elif n <= 88:
            band = "super_peak"
        else:
            band = "off_peak"
        if n % 11 == 0:
            ambient = min(len(AMBIENT_CLASSES) - 1, ambient + 1)
        if n > 78 and n % 7 == 0:
            ambient = max(0, ambient - 1)
        intervals.append({
            "n": n,
            "code": "iv_%02d" % n,
            "start_minute": (n - 1) * INTERVAL_MINUTES,
            "end_minute": n * INTERVAL_MINUTES,
            "band": band,
            "ambient": AMBIENT_CLASSES[ambient],
        })
    inst["intervals"] = intervals


# --------------------------------------------------------------------------
# substations, feeders and plugs
# --------------------------------------------------------------------------


def _mint_network(inst, rng, cfg):
    feeders = []
    n_feeders = cfg["feeders"]
    for i in range(n_feeders):
        sub = SUBSTATIONS[i % len(SUBSTATIONS)]
        base = 42000 + rng.between(0, 26) * 1300
        nominal = (base * cfg["capacity_scale"]) // 100
        # A nominal capacity that is never a multiple of the quarter hour
        # divisor keeps the watt hour conversion off an exact boundary.
        if nominal % 4 == 0:
            nominal += rng.between(1, 3)
        reserve = ((3100 + rng.between(0, 18) * 190) * cfg["reserve_scale"]) // 100
        feeders.append({
            "id": "fd_%02d" % (i + 1),
            "substation": sub,
            "nominal_w": nominal,
            "reserve_w": reserve,
            "in_force": True,
        })
    # Two feeders carry a capacity row but the substation topology omits them,
    # so they are out of force and every plug hanging off them is refused.
    out_of_force = {feeders[2]["id"], feeders[n_feeders - 2]["id"]}
    for f in feeders:
        if f["id"] in out_of_force:
            f["in_force"] = False
    # One further feeder carries nothing but the pair of identical reefers
    # the deadline correction cycles on. Its capacity is settled once the
    # floors of that pair are known.
    cycle_id = "fd_%02d" % (n_feeders + 1)
    feeders.append({
        "id": cycle_id, "substation": SUBSTATIONS[n_feeders % len(SUBSTATIONS)],
        "nominal_w": 90000, "reserve_w": 0, "in_force": True,
    })
    inst["cycle_feeder"] = cycle_id
    equality_id = "fd_%02d" % (n_feeders + 2)
    feeders.append({
        "id": equality_id,
        "substation": SUBSTATIONS[(n_feeders + 1) % len(SUBSTATIONS)],
        "nominal_w": 90000, "reserve_w": 0, "in_force": True,
    })
    inst["equality_feeder"] = equality_id
    inst["feeders"] = feeders
    inst["feeders_by_id"] = dict((f["id"], f) for f in feeders)

    plugs = []
    per = 16
    for i, f in enumerate(feeders):
        for k in range(per):
            zone = ZONE_CYCLE[(i + k) % len(ZONE_CYCLE)]
            plugs.append({
                "id": "pl_%04d" % (len(plugs) + 1),
                "feeder": f["id"],
                "zone": zone,
                "state": "isolated" if rng.chance(1, 23) else "live",
            })
    inst["plugs"] = plugs
    inst["plugs_by_id"] = dict((p["id"], p) for p in plugs)


# --------------------------------------------------------------------------
# vessels and their calls
# --------------------------------------------------------------------------


def _mint_vessels(inst, rng, cfg):
    vessels = []
    words = rng.shuffled(VESSEL_WORDS)[:cfg["vessels"]]
    for i, word in enumerate(sorted(words)):
        vessels.append({
            "id": "vs_" + word,
            "name": word.capitalize() + " Point",
            "service_group": SERVICE_GROUPS[i % len(SERVICE_GROUPS)],
            "urgency_rank": 1 + (i % 4),
            "cutoff_interval": rng.between(46, 92),
            "berth": "bt_%d" % (1 + (i % 4)),
            "destination": DESTINATIONS[i % len(DESTINATIONS)],
        })
    inst["vessels"] = vessels
    inst["vessels_by_id"] = dict((v["id"], v) for v in vessels)

    # Every vessel carries a revision history. The applicable call is the
    # highest revision sequence whose record state reads current. One vessel
    # carries a withdrawn revision ABOVE its current one, so a reading that
    # takes the highest sequence outright lands on a withdrawn call. One
    # further vessel has every revision withdrawn and therefore no applicable
    # call at all.
    calls = []
    withdrawn_rows = []
    high_withdrawn = vessels[1]["id"] if len(vessels) > 1 else vessels[0]["id"]
    all_withdrawn = vessels[len(vessels) - 2]["id"]
    for v in vessels:
        base = rng.between(3, 9)
        n_rev = rng.between(2, 4)
        for k in range(n_rev):
            seq = base + k
            state = "current"
            cutoff = v["cutoff_interval"] - (n_rev - 1 - k) * 3
            urgency = v["urgency_rank"]
            if v["id"] == all_withdrawn:
                state = "withdrawn"
            calls.append({
                "vessel_id": v["id"], "day_id": inst["day_id"],
                "revision_seq": seq, "record_state": state,
                "cutoff_interval": max(6, cutoff),
                "urgency_rank": urgency,
                "service_group": v["service_group"],
                "berth": v["berth"], "destination": v["destination"],
                "name": v["name"],
            })
        if v["id"] == high_withdrawn:
            calls.append({
                "vessel_id": v["id"], "day_id": inst["day_id"],
                "revision_seq": base + n_rev, "record_state": "withdrawn",
                "cutoff_interval": min(95, v["cutoff_interval"] + 14),
                "urgency_rank": 1,
                "service_group": v["service_group"],
                "berth": v["berth"], "destination": v["destination"],
                "name": v["name"],
            })
        for day in inst["prior"]:
            calls.append({
                "vessel_id": v["id"], "day_id": day,
                "revision_seq": rng.between(2, 11), "record_state": "current",
                "cutoff_interval": rng.between(20, 94),
                "urgency_rank": rng.between(1, 4),
                "service_group": v["service_group"],
                "berth": v["berth"], "destination": v["destination"],
                "name": v["name"],
            })
    inst["calls"] = calls
    inst["high_withdrawn_vessel"] = high_withdrawn
    inst["all_withdrawn_vessel"] = all_withdrawn
    for row in calls:
        if row["record_state"] == "withdrawn":
            withdrawn_rows.append(row)
    inst["withdrawn_calls"] = withdrawn_rows


# --------------------------------------------------------------------------
# the reefers themselves
# --------------------------------------------------------------------------


def _mint_reefers(inst, rng, cfg):
    reefers = []
    live_plugs = [p for p in inst["plugs"] if p["state"] == "live"]
    cycle_feeder = inst["cycle_feeder"]
    in_force_plugs = [p for p in live_plugs
                      if inst["feeders_by_id"][p["feeder"]]["in_force"]
                      and p["feeder"] not in (cycle_feeder,
                                              inst["equality_feeder"])]
    cycle_plugs = [p for p in inst["plugs"] if p["feeder"] == cycle_feeder]
    out_plugs = [p for p in live_plugs
                 if not inst["feeders_by_id"][p["feeder"]]["in_force"]]
    n = cfg["reefers"]
    used = set()
    for i in range(n):
        rid = "rf_%04d" % (i + 1)
        temp = TEMP_CLASSES[rng.below(len(TEMP_CLASSES))]
        pool = in_force_plugs
        plug = pool[rng.below(len(pool))]
        guard = 0
        while plug["id"] in used and guard < 40:
            plug = pool[rng.below(len(pool))]
            guard += 1
        used.add(plug["id"])
        unit = POWER_UNITS[rng.below(len(POWER_UNITS))]
        if unit == "wh_h":
            value = rng.between(2100, 7600)
        elif unit == "kwh_h":
            value = rng.between(3, 9)
        else:
            value = rng.between(9, 27)
        start = rng.between(0, 84) * 15 + rng.between(0, 14)
        span = rng.between(3, 46) * 15 + rng.between(0, 14)
        reefers.append({
            "id": rid,
            "plug_id": plug["id"],
            "vessel_id": inst["vessels"][rng.below(len(inst["vessels"]))]["id"],
            "temperature_class": temp,
            "nameplate_value": value,
            "nameplate_unit": unit,
            "connect_minute": start,
            "disconnect_minute": min(1440, start + span),
            "source_system": ["yard_office", "gate_terminal", "quay_desk",
                              "reefer_desk"][rng.below(4)],
            "revision_seq": rng.between(2, 6),
            "record_state": "current",
        })
    inst["reefers"] = reefers

    def at(idx):
        return reefers[idx % len(reefers)]

    # --- fixtures the admission ladder needs -----------------------------
    # An unknown plug: the reefer names a plug identifier the assignment
    # register does not carry.
    at(3)["plug_id"] = "pl_9001"
    at(41)["plug_id"] = "pl_9002"
    isolated = [p for p in inst["plugs"] if p["state"] == "isolated"]
    if isolated:
        at(15)["plug_id"] = isolated[0]["id"]
    # A plug hanging off a feeder the topology omits.
    if out_plugs:
        at(7)["plug_id"] = out_plugs[0]["id"]
        at(52)["plug_id"] = out_plugs[len(out_plugs) // 2]["id"]
    # An empty connection window, and a window that closes on the minute it
    # opens.
    at(11)["connect_minute"] = 615
    at(11)["disconnect_minute"] = 615
    at(63)["connect_minute"] = 1440
    at(63)["disconnect_minute"] = 1440
    # A power unit the register does not carry.
    at(17)["nameplate_unit"] = "btu_h"
    at(17)["nameplate_value"] = 24000
    at(74)["nameplate_unit"] = "btu_h"
    at(74)["nameplate_value"] = 31000
    # A plug zone that refuses the class the reefer declares. The standard
    # zone admits neither deep frozen nor pharma.
    std = [p for p in in_force_plugs if p["zone"] == "standard"]
    if std:
        at(23)["plug_id"] = std[0]["id"]
        at(23)["temperature_class"] = "deep_frozen"
        at(58)["plug_id"] = std[len(std) // 3]["id"]
        at(58)["temperature_class"] = "pharma"
    # A cluster of three reefers on one plug. The lowest identifier of the
    # cluster is itself caught by an earlier rung, so the canonical member is
    # the second, and a reading that takes the lowest identifier outright
    # picks a reefer the ladder had already set aside.
    haz = [p for p in in_force_plugs if p["zone"] == "hazard"]
    shared = haz[0]["id"] if haz else in_force_plugs[0]["id"]
    at(29)["plug_id"] = shared
    at(29)["temperature_class"] = "chilled"
    at(30)["plug_id"] = shared
    at(30)["temperature_class"] = "frozen"
    at(31)["plug_id"] = shared
    at(31)["temperature_class"] = "deep_frozen"
    # --- boundary fixtures ------------------------------------------------
    # A window that opens exactly on an interval boundary.
    at(5)["connect_minute"] = 300
    at(5)["disconnect_minute"] = 795
    # A window that closes exactly on an interval boundary; the closing
    # interval is excluded.
    at(9)["connect_minute"] = 187
    at(9)["disconnect_minute"] = 600
    # A window one interval wide, opening and closing on boundaries.
    at(13)["connect_minute"] = 900
    at(13)["disconnect_minute"] = 915
    # A window one minute wide inside a single interval.
    at(19)["connect_minute"] = 1207
    at(19)["disconnect_minute"] = 1208
    # A window that runs to the last minute of the grid.
    at(27)["connect_minute"] = 1380
    at(27)["disconnect_minute"] = 1440
    # A nameplate quoted in megajoules per hour whose conversion never lands
    # on a whole watt.
    at(2)["nameplate_unit"] = "mj_h"
    at(2)["nameplate_value"] = 13
    at(37)["nameplate_unit"] = "mj_h"
    at(37)["nameplate_value"] = 22
    # A reefer against the vessel whose every call revision is withdrawn.
    at(33)["vessel_id"] = inst["all_withdrawn_vessel"]
    at(34)["vessel_id"] = inst["all_withdrawn_vessel"]
    # A reefer against the vessel whose highest revision is a withdrawn one.
    at(35)["vessel_id"] = inst["high_withdrawn_vessel"]
    at(36)["vessel_id"] = inst["high_withdrawn_vessel"]

    _mint_cycle_pair(inst, rng, cfg, at, cycle_plugs)
    _mint_equality_reefer(inst, rng, cfg, at)

    # Prior day rows pad the register and are set aside by the day filter. A
    # handful of current day rows carry a superseded state at a HIGHER
    # revision sequence than their current row, so the state filter is not a
    # consequence of the sequence filter.
    rows = []
    for r in reefers:
        rows.append(dict(r, day_id=inst["day_id"]))
    for idx in (6, 21, 47):
        base = at(idx)
        rows.append(dict(base, day_id=inst["day_id"],
                         revision_seq=base["revision_seq"] + 2,
                         record_state="superseded",
                         nameplate_value=base["nameplate_value"] + 900,
                         connect_minute=max(0, base["connect_minute"] - 120)))
    for day in inst["prior"]:
        for r in reefers[::3]:
            rows.append(dict(r, day_id=day, record_state="current",
                             revision_seq=rng.between(2, 9),
                             nameplate_value=r["nameplate_value"] + rng.between(1, 400),
                             connect_minute=rng.between(0, 1200)))
    inst["reefer_rows"] = rows
    inst["shared_plug"] = shared


def _mint_cycle_pair(inst, rng, cfg, at, cycle_plugs):
    """Two reefers of one nameplate on one feeder, whose four interval
    windows the feeder admits together in three intervals and singly in the
    fourth. The deadline correction hands that fourth interval back and forth
    between them, which is the two state cycle stage p12 breaks."""
    if not cfg["cycle_pair"]:
        return
    pool = [p for p in cycle_plugs
            if p["state"] == "live" and p["zone"] in ("reefer", "standard")]
    if len(pool) < 2:
        return
    first = at(76)
    second = at(77)
    vessel = inst["vessels"][0]["id"]
    for rec, plug in ((first, pool[0]), (second, pool[1])):
        rec["plug_id"] = plug["id"]
        rec["temperature_class"] = "chilled"
        rec["nameplate_unit"] = "wh_h"
        rec["nameplate_value"] = 5000
        rec["connect_minute"] = 435
        rec["disconnect_minute"] = 495
        rec["vessel_id"] = vessel
    draws = {}
    for n in (30, 31, 32, 33):
        draws[n] = _interval_draw(inst, "chilled", 5000, n)
    feeder = inst["feeders_by_id"][inst["cycle_feeder"]]
    widest = max(draws.values())
    nominal = 2 * widest + 37
    feeder["nominal_w"] = nominal
    feeder["reserve_w"] = 0
    target = draws[33] + 11
    permille = -((-target * 1000) // nominal)
    inst["cycle_derate"] = (feeder["id"], 33, 33, permille)
    inst["cycle_pair"] = (first["id"], second["id"])


def _interval_draw(inst, temperature_class, nameplate_w, n):
    """The watt draw stage P03 stores for one reefer in one interval."""
    coeff_num, coeff_den = inst["controls"]["maintenance_coefficient"][
        temperature_class]
    ambient = inst["intervals"][n - 1]["ambient"]
    pair = inst["controls"]["ambient_multiplier"].get(
        (temperature_class, ambient))
    if pair is None:
        pair = inst["controls"]["class_default_multiplier"]
    value = Fraction(nameplate_w) * Fraction(pair[0], pair[1]) \
        * Fraction(coeff_num, coeff_den)
    return _round_half_up(value)


def _mint_equality_reefer(inst, rng, cfg, at):
    """One reefer alone on one feeder, connected for a single interval, whose
    draw in that interval is exactly the nominal capacity of the feeder. The
    lawfulness of a load equal to the capacity is settled there and nowhere
    else."""
    plugs = [p for p in inst["plugs"]
             if p["feeder"] == inst["equality_feeder"] and p["state"] == "live"
             and p["zone"] == "reefer"]
    if not plugs:
        return
    rec = at(80)
    rec["plug_id"] = plugs[0]["id"]
    rec["temperature_class"] = "frozen"
    rec["nameplate_unit"] = "wh_h"
    rec["nameplate_value"] = 6100
    rec["connect_minute"] = 900
    rec["disconnect_minute"] = 915
    rec["vessel_id"] = inst["vessels"][0]["id"]
    feeder = inst["feeders_by_id"][inst["equality_feeder"]]
    feeder["nominal_w"] = _interval_draw(inst, "frozen", 6100, 61)
    feeder["reserve_w"] = 0
    inst["equality_reefer"] = rec["id"]


def _round_half_up(value):
    if value >= 0:
        return int((value * 2 + 1) // 2)
    return -int(((-value) * 2 + 1) // 2)


# --------------------------------------------------------------------------
# declared energy returns
# --------------------------------------------------------------------------


def _mint_energy_returns(inst, rng, cfg):
    rows = []
    reefers = inst["reefers"]
    for i, r in enumerate(reefers):
        if rng.chance(1, 9):
            continue
        unit = ENERGY_UNITS[rng.below(len(ENERGY_UNITS))]
        if unit == "wh":
            value = rng.between(40000, 268000)
        elif unit == "kwh":
            value = rng.between(45, 291)
        else:
            value = rng.between(161, 1033)
        seq = rng.between(2, 6)
        rows.append({
            "reefer_id": r["id"], "day_id": inst["day_id"],
            "declared_value": value, "energy_unit": unit,
            "declaration_seq": seq, "record_state": "filed",
        })
        if rng.chance(1, 13):
            rows.append({
                "reefer_id": r["id"], "day_id": inst["day_id"],
                "declared_value": value + rng.between(400, 3000),
                "energy_unit": unit, "declaration_seq": seq - 1,
                "record_state": "filed",
            })
    # Two reefers file a return carrying the not supplied marker. That is a
    # return with no declared energy, and it is not a declaration of zero.
    for idx in (12, 44):
        rows.append({
            "reefer_id": reefers[idx % len(reefers)]["id"],
            "day_id": inst["day_id"], "declared_value": NOT_SUPPLIED,
            "energy_unit": "wh", "declaration_seq": 9, "record_state": "filed",
        })
    # Three reefers carry a superseded return at a HIGHER sequence than their
    # filed one, so the state filter bites on its own.
    for idx in (8, 26, 55):
        rid = reefers[idx % len(reefers)]["id"]
        rows.append({
            "reefer_id": rid, "day_id": inst["day_id"],
            "declared_value": rng.between(70000, 140000), "energy_unit": "wh",
            "declaration_seq": 11, "record_state": "superseded",
        })
    for day in inst["prior"]:
        for r in reefers[::2]:
            rows.append({
                "reefer_id": r["id"], "day_id": day,
                "declared_value": rng.between(8000, 52000),
                "energy_unit": ENERGY_UNITS[rng.below(len(ENERGY_UNITS))],
                "declaration_seq": rng.between(2, 8), "record_state": "filed",
            })
    inst["energy_rows"] = rows


# --------------------------------------------------------------------------
# crane duty and its confirmations
# --------------------------------------------------------------------------


def _mint_cranes(inst, rng, cfg):
    feeders = [f for f in inst["feeders"]
               if f["in_force"] and f["id"] != inst["cycle_feeder"]
               and f["id"] != inst["equality_feeder"]]
    cranes = []
    for i in range(cfg["cranes"]):
        cranes.append({
            "id": "cr_%d" % (i + 1),
            "feeder_id": feeders[i % len(feeders)]["id"],
            "gang": "gang_%s" % "abcdef"[i % 6],
        })
    inst["cranes"] = cranes

    duties = []
    confirms = []
    for c in cranes:
        for n in range(1, INTERVAL_COUNT + 1):
            if rng.chance(2, 5):
                continue
            state = DUTY_STATES[rng.below(len(DUTY_STATES))]
            if state == "idle":
                kw = rng.between(1, 4)
            elif state == "gantry":
                kw = rng.between(9, 21)
            else:
                kw = rng.between(24, 71)
            kw = (kw * cfg["crane_scale"]) // 100
            duties.append({
                "crane_id": c["id"], "day_id": inst["day_id"], "interval": n,
                "duty_state": state, "demand_kw": kw,
                "feeder_id": c["feeder_id"], "duty_seq": rng.between(1, 4),
            })
            landed = not rng.chance(1, 7)
            confirms.append({
                "crane_id": c["id"], "day_id": inst["day_id"], "interval": n,
                "confirmation_state": "landed" if landed else "cancelled",
                "confirm_seq": 2,
            })
    # Six duties carry two confirmations. The earlier sequence cancels and the
    # later one lands, so a reading that takes the last confirmation charges a
    # duty the terminal called off.
    marks = duties[::max(1, len(duties) // 7)][:6]
    for d in marks:
        confirms.append({
            "crane_id": d["crane_id"], "day_id": inst["day_id"],
            "interval": d["interval"], "confirmation_state": "cancelled",
            "confirm_seq": 1,
        })
    # A block of intervals where one feeder carries crane duty heavy enough to
    # take the reefer available capacity to zero, so the clamp at zero is
    # reached rather than a negative capacity.
    heavy_feeder = feeders[0]["id"]
    heavy_crane = None
    for c in cranes:
        if c["feeder_id"] == heavy_feeder:
            heavy_crane = c["id"]
            break
    if heavy_crane is None:
        heavy_crane = cranes[0]["id"]
        heavy_feeder = cranes[0]["feeder_id"]
    heavy = set(range(52, 58))
    duties = [d for d in duties
              if not (d["crane_id"] == heavy_crane and d["interval"] in heavy)]
    confirms = [d for d in confirms
                if not (d["crane_id"] == heavy_crane and d["interval"] in heavy)]
    cap = inst["feeders_by_id"][heavy_feeder]["nominal_w"]
    for n in sorted(heavy):
        duties.append({
            "crane_id": heavy_crane, "day_id": inst["day_id"], "interval": n,
            "duty_state": "hoisting", "demand_kw": (cap // 1000) + 9,
            "feeder_id": heavy_feeder, "duty_seq": 1,
        })
        confirms.append({
            "crane_id": heavy_crane, "day_id": inst["day_id"], "interval": n,
            "confirmation_state": "landed", "confirm_seq": 2,
        })
    for day in inst["prior"]:
        for c in cranes:
            for n in range(1, INTERVAL_COUNT + 1, 5):
                duties.append({
                    "crane_id": c["id"], "day_id": day, "interval": n,
                    "duty_state": DUTY_STATES[rng.below(len(DUTY_STATES))],
                    "demand_kw": rng.between(2, 66),
                    "feeder_id": c["feeder_id"], "duty_seq": 1,
                })
    inst["crane_duties"] = duties
    inst["crane_confirms"] = confirms
    inst["heavy_feeder"] = heavy_feeder


# --------------------------------------------------------------------------
# maintenance windows and derating notices
# --------------------------------------------------------------------------


def _mint_maintenance(inst, rng, cfg):
    windows = []
    feeders = [f for f in inst["feeders"]
               if f["id"] not in (inst["cycle_feeder"], inst["equality_feeder"])]
    for i in range(6):
        f = feeders[(i * 3 + 1) % len(feeders)]
        first = rng.between(4, 80)
        windows.append({
            "resource_kind": "feeder", "resource_id": f["id"],
            "day_id": inst["day_id"], "first_interval": first,
            "last_interval": min(INTERVAL_COUNT, first + rng.between(1, 5)),
            "window_state": "booked" if i % 3 else "cancelled",
            "notice_seq": rng.between(1, 4),
        })
    for i in range(4):
        p = inst["plugs"][(i * 37 + 5) % len(inst["plugs"])]
        first = rng.between(10, 70)
        windows.append({
            "resource_kind": "plug", "resource_id": p["id"],
            "day_id": inst["day_id"], "first_interval": first,
            "last_interval": min(INTERVAL_COUNT, first + rng.between(2, 8)),
            "window_state": "booked", "notice_seq": 2,
        })
    for c in inst["cranes"][:2]:
        windows.append({
            "resource_kind": "crane", "resource_id": c["id"],
            "day_id": inst["day_id"], "first_interval": 61,
            "last_interval": 66, "window_state": "booked", "notice_seq": 1,
        })
    # A booked battery window, so the battery is offline for a block of the
    # peak band and the state of charge holds flat across it.
    windows.append({
        "resource_kind": "battery", "resource_id": "bt_main",
        "day_id": inst["day_id"], "first_interval": 44,
        "last_interval": 48, "window_state": "booked", "notice_seq": 1,
    })
    # A window that opens on the first interval of the grid and one that
    # closes on the last.
    windows.append({
        "resource_kind": "feeder", "resource_id": feeders[1]["id"],
        "day_id": inst["day_id"], "first_interval": 1, "last_interval": 1,
        "window_state": "booked", "notice_seq": 3,
    })
    windows.append({
        "resource_kind": "feeder", "resource_id": feeders[len(feeders) - 1]["id"],
        "day_id": inst["day_id"], "first_interval": INTERVAL_COUNT,
        "last_interval": INTERVAL_COUNT, "window_state": "booked",
        "notice_seq": 3,
    })
    for day in inst["prior"]:
        for f in feeders:
            windows.append({
                "resource_kind": "feeder", "resource_id": f["id"],
                "day_id": day, "first_interval": rng.between(1, 80),
                "last_interval": rng.between(81, 96),
                "window_state": "booked", "notice_seq": 1,
            })
    inst["maintenance"] = windows

    derates = []
    for i, f in enumerate(feeders):
        if i % 4 == 0:
            first = rng.between(20, 60)
            derates.append({
                "feeder_id": f["id"], "day_id": inst["day_id"],
                "first_interval": first,
                "last_interval": min(INTERVAL_COUNT, first + rng.between(4, 12)),
                "derate_permille": rng.between(561, 889),
                "notice_seq": 3, "record_state": "current",
            })
            # A superseded derating notice at a HIGHER sequence, so the state
            # filter bites on its own rather than through the sequence.
            derates.append({
                "feeder_id": f["id"], "day_id": inst["day_id"],
                "first_interval": first,
                "last_interval": min(INTERVAL_COUNT, first + 20),
                "derate_permille": 250, "notice_seq": 6,
                "record_state": "superseded",
            })
    for day in inst["prior"]:
        for f in feeders[::2]:
            derates.append({
                "feeder_id": f["id"], "day_id": day,
                "first_interval": rng.between(1, 50),
                "last_interval": rng.between(51, 96),
                "derate_permille": rng.between(500, 950), "notice_seq": 1,
                "record_state": "current",
            })
    if inst.get("cycle_derate"):
        fid, first, last, permille = inst["cycle_derate"]
        derates.append({
            "feeder_id": fid, "day_id": inst["day_id"],
            "first_interval": first, "last_interval": last,
            "derate_permille": permille, "notice_seq": 3,
            "record_state": "current",
        })
    inst["derates"] = derates


# --------------------------------------------------------------------------
# tariff schedule and demand charge bands
# --------------------------------------------------------------------------


def _mint_tariff(inst, rng, cfg):
    prices = {
        "off_peak": 91, "shoulder": 147, "peak": 233, "super_peak": 311,
    }
    rows = []
    for iv in inst["intervals"]:
        price = prices[iv["band"]] + rng.between(0, 9)
        rows.append({
            "day_id": inst["day_id"], "interval": iv["n"], "band": iv["band"],
            "price_tenth_cents_per_kwh": price, "schedule_seq": 4,
            "record_state": "current",
        })
    # One interval carries a superseded price at a higher sequence.
    rows.append({
        "day_id": inst["day_id"], "interval": 57, "band": "peak",
        "price_tenth_cents_per_kwh": 999, "schedule_seq": 7,
        "record_state": "superseded",
    })
    for day in inst["prior"]:
        for iv in inst["intervals"][::2]:
            rows.append({
                "day_id": day, "interval": iv["n"], "band": iv["band"],
                "price_tenth_cents_per_kwh": prices[iv["band"]] + rng.between(0, 30),
                "schedule_seq": 2, "record_state": "current",
            })
    inst["tariff_rows"] = rows

    bands = []
    floor = 0
    for i in range(9):
        ceiling = floor + 24000 + i * 5000
        bands.append({
            "band_code": "dc_%02d" % (i + 1), "floor_w": floor,
            "ceiling_w": ceiling, "charge_cents": 1900 + i * 2300,
        })
        floor = ceiling
    bands.append({
        "band_code": "dc_10", "floor_w": floor, "ceiling_w": 99999999,
        "charge_cents": 1900 + 9 * 2300,
    })
    inst["demand_bands"] = bands


# --------------------------------------------------------------------------
# battery policy and telemetry
# --------------------------------------------------------------------------


def _mint_battery(inst, rng, cfg):
    capacity = 260000 + rng.between(0, 40) * 1100
    reserve = 41000 + rng.between(0, 20) * 300
    # A state of charge scale of zero puts the battery on its reserve at the
    # opening interval. Sitting exactly on the reserve is a lawful state and
    # it is not a violation, but nothing may be drawn from it.
    initial = (reserve + ((capacity - reserve) * cfg["soc_scale"]) // 220
               - cfg["soc_below_reserve"])
    battery = {
        "id": "bt_main",
        "substation": SUBSTATIONS[0],
        "capacity_wh": capacity,
        "initial_soc_wh": initial,
        "reserve_wh": reserve,
        "max_charge_w": ((33000 + rng.between(0, 12) * 700)
                         * cfg["charge_scale"]) // 100,
        "max_discharge_w": ((47000 + rng.between(0, 12) * 900)
                            * cfg["discharge_scale"]) // 100,
        "charge_efficiency_permille": 917,
        "discharge_efficiency_permille": 943,
        "charge_bands": ["off_peak", "shoulder"],
    }
    inst["battery"] = battery

    telemetry = []
    for iv in inst["intervals"]:
        state = "online"
        if 44 <= iv["n"] <= 48:
            state = "offline"
        telemetry.append({
            "day_id": inst["day_id"], "interval": iv["n"],
            "availability_state": state,
            "measured_soc_wh": initial + rng.between(0, 900),
            "telemetry_seq": 3,
        })
    for day in inst["prior"]:
        for iv in inst["intervals"][::2]:
            telemetry.append({
                "day_id": day, "interval": iv["n"],
                "availability_state": "online",
                "measured_soc_wh": rng.between(40000, 250000),
                "telemetry_seq": 1,
            })
    inst["battery_telemetry"] = telemetry


# --------------------------------------------------------------------------
# exception notices
# --------------------------------------------------------------------------


def _mint_exceptions(inst, rng, cfg):
    reefers = inst["reefers"]
    notices = []

    def rid(idx):
        return reefers[idx % len(reefers)]["id"]

    # The zone waiver lifts the zone refusal for one named reefer, so a rung
    # that would otherwise catch it does not.
    notices.append({"notice_id": "ex_0001", "kind": "zone_waiver",
                    "day_id": inst["day_id"], "subject_id": rid(58),
                    "interval": 0,
                    "note": "the harbour engineer cleared the pharma load on a standard plug"})
    # The priority override marks two reefers vessel critical. A vessel
    # critical reefer overturns an ordinary queue position at the deadline
    # correction pass.
    notices.append({"notice_id": "ex_0002", "kind": "priority_override",
                    "day_id": inst["day_id"], "subject_id": rid(69),
                    "interval": 0,
                    "note": "the vessel agent declared the consignment critical"})
    notices.append({"notice_id": "ex_0003", "kind": "priority_override",
                    "day_id": inst["day_id"], "subject_id": rid(88),
                    "interval": 0,
                    "note": "the vessel agent declared the consignment critical"})
    notices.append({"notice_id": "ex_0004", "kind": "priority_override",
                    "day_id": inst["day_id"], "subject_id": rid(101),
                    "interval": 0,
                    "note": "the vessel agent declared the consignment critical"})
    # A notice against a prior day, which governs nothing here.
    notices.append({"notice_id": "ex_0005", "kind": "zone_waiver",
                    "day_id": inst["prior"][0], "subject_id": rid(23),
                    "interval": 0,
                    "note": "a waiver filed against an earlier operating day"})
    # A notice of a kind the specification does not carry.
    notices.append({"notice_id": "ex_0006", "kind": "berth_shuffle",
                    "day_id": inst["day_id"], "subject_id": rid(4),
                    "interval": 31,
                    "note": "a notice of a kind no stage specification carries"})
    for i in range(1, 15):
        notices.append({"notice_id": "ex_1%03d" % i, "kind": "priority_override",
                        "day_id": inst["day_id"], "subject_id": rid(i * 7 + 3),
                        "interval": 0,
                        "note": "the vessel agent declared the consignment critical"})
    for i in range(7, 41):
        notices.append({
            "notice_id": "ex_%04d" % i,
            "kind": ["zone_waiver", "priority_override", "berth_shuffle"][i % 3],
            "day_id": inst["prior"][i % len(inst["prior"])],
            "subject_id": rid(i * 3), "interval": 0,
            "note": "an earlier notice retained for the audit file",
        })
    inst["notices"] = notices


# --------------------------------------------------------------------------
# the control values the three office papers carry
# --------------------------------------------------------------------------


def _mint_controls(inst, rng, cfg):
    coeff = {}
    for i, tc in enumerate(TEMP_CLASSES):
        coeff[tc] = (1000 + 60 * i + rng.between(1, 40), 1000)
    ambient_mult = {}
    for tc in TEMP_CLASSES:
        for ac in AMBIENT_CLASSES:
            if tc == "banana" and ac == "hot":
                continue
            if tc == "pharma" and ac == "cool":
                continue
            ambient_mult[(tc, ac)] = (
                900 + AMBIENT_CLASSES.index(ac) * 90 + rng.between(1, 30), 1000)
    ceilings = {}
    for i, v in enumerate(inst["vessels"]):
        if i % 3 == 0:
            ceilings[v["id"]] = rng.between(2, 9) * 1000
        else:
            ceilings[v["id"]] = rng.between(31, 93) * 1000
    sub_ceiling = {}
    for s in SUBSTATIONS:
        sub_ceiling[s] = rng.between(151, 233) * 1000
    class_rank = {}
    order = rng.shuffled(TEMP_CLASSES)
    for i, tc in enumerate(order):
        class_rank[tc] = i + 1
    inst["controls"] = {
        "damping_num": 7,
        "damping_den": 16,
        "pass_budget": 5,
        "minimum_step_wh": 400,
        "protection_depth": 2,
        "base_service_charge_cents": 1400 + rng.between(0, 60),
        "maintenance_coefficient": coeff,
        "ambient_multiplier": ambient_mult,
        "vessel_share_ceiling_wh": ceilings,
        "substation_ceiling_w": sub_ceiling,
        "class_rank": class_rank,
        "ordering_keys": ["deadline_slack", "class_rank", "urgency_rank",
                          "reefer_id"],
        "class_default_multiplier": (1000, 1000),
        "surcharge_ladder": [(0, 0), (1, 240), (3, 610), (7, 1450)],
    }


# --------------------------------------------------------------------------
# the registers, journals and feeds
# --------------------------------------------------------------------------


def _pad_rng(inst, salt):
    return Rng((inst["seed"] * 1000003) ^ (sum(ord(c) for c in salt) * 7919))


def _sheet_names(inst):
    return SHEET_NAME_POOL[inst["cfg"]["names"]]


def write_grid_papers(inst, root):
    rows = []
    for day in [inst["day_id"]] + inst["prior"]:
        for iv in inst["intervals"]:
            rows.append([day, iv["n"], iv["code"], iv["start_minute"],
                         iv["end_minute"], iv["band"], iv["ambient"]])
    write_rows(root / "interval_grid_calendar.csv",
               ["day_id", "interval", "interval_code", "start_minute",
                "end_minute", "tariff_band", "ambient_class"], rows, ",")

    rng = _pad_rng(inst, "zone")
    rows = []
    admit = {
        "standard": ["frozen", "chilled", "banana"],
        "reefer": ["frozen", "chilled", "deep_frozen", "pharma", "banana"],
        "hazard": ["frozen", "deep_frozen", "pharma"],
    }
    for day in [inst["day_id"]] + inst["prior"]:
        for rev in range(1, 5):
            for zone in PLUG_ZONES:
                for tc in TEMP_CLASSES:
                    state = "current" if rev == 4 else "superseded"
                    verdict = "admitted" if tc in admit[zone] else "refused"
                    if day != inst["day_id"] and rng.chance(1, 5):
                        verdict = "refused"
                    rows.append([day, rev, zone, tc, verdict, state])
    write_rows(root / "plug_zone_admission_matrix.csv",
               ["day_id", "revision_seq", "plug_zone", "temperature_class",
                "admission", "record_state"], rows, ",")


def write_network_papers(inst, root):
    rng = _pad_rng(inst, "network")
    rows = []
    for day in [inst["day_id"]] + inst["prior"]:
        for rev in range(1, 6):
            for f in inst["feeders"]:
                state = "current" if rev == 5 else "superseded"
                nominal = f["nominal_w"] if (day == inst["day_id"] and rev == 5) \
                    else f["nominal_w"] + rng.between(1, 900) - 450
                reserve = f["reserve_w"] if (day == inst["day_id"] and rev == 5) \
                    else f["reserve_w"] + rng.between(1, 400) - 200
                rows.append([day, rev, f["id"], f["substation"], nominal,
                             reserve, "energised", state])
    write_rows(root / "feeder_capacity_register.csv",
               ["day_id", "revision_seq", "feeder_id", "substation_id",
                "nominal_capacity_w", "standing_reserve_w", "feeder_state",
                "record_state"], rows, ",")

    rows = []
    for p in inst["plugs"]:
        rows.append([inst["day_id"], p["id"], p["feeder"], p["zone"],
                     p["state"], 4])
    for day in inst["prior"]:
        for p in inst["plugs"][::4]:
            rows.append([day, p["id"], p["feeder"], p["zone"], "live", 2])
    write_rows(root / "plug_assignment_register.csv",
               ["day_id", "plug_id", "feeder_id", "plug_zone", "plug_state",
                "revision_seq"], rows, ",")

    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<topology day="%s" reference="%s">' % (inst["day_id"],
                                                     inst["day_reference"])]
    for s in SUBSTATIONS:
        ceiling = inst["controls"]["substation_ceiling_w"][s]
        lines.append('  <substation id="%s" ceiling_w="%d">' % (s, ceiling))
        for f in inst["feeders"]:
            if f["substation"] != s or not f["in_force"]:
                continue
            lines.append('    <feeder id="%s">' % f["id"])
            for p in inst["plugs"]:
                if p["feeder"] == f["id"]:
                    lines.append('      <plug id="%s" zone="%s"/>'
                                 % (p["id"], p["zone"]))
            lines.append("    </feeder>")
        lines.append("  </substation>")
    lines.append("</topology>")
    write_lines(root / "substation_topology.xml", lines)

    rows = []
    for d in inst["derates"]:
        rows.append([d["day_id"], d["feeder_id"], d["first_interval"],
                     d["last_interval"], d["derate_permille"],
                     d["notice_seq"], d["record_state"]])
    rng = _pad_rng(inst, "derate")
    while len(rows) < 214:
        f = inst["feeders"][rng.below(len(inst["feeders"]))]
        day = inst["prior"][rng.below(len(inst["prior"]))]
        first = rng.between(1, 60)
        rows.append([day, f["id"], first, first + rng.between(2, 20),
                     rng.between(400, 980), rng.between(1, 3), "current"])
    write_rows(root / "feeder_derating_notices.csv",
               ["day_id", "feeder_id", "first_interval", "last_interval",
                "derate_permille", "notice_seq", "record_state"], rows, ",")

    lines = ["# reporting roster for the substation control office",
             "# a substation appears here when its report is published",
             "day_id = %s" % inst["day_id"]]
    for s in [SUBSTATIONS[i] for i in inst["cfg"]["roster_order"]]:
        lines.append("[%s]" % s)
        lines.append("report = substation_report_%s.json" % s)
        lines.append("published = yes")
    rng = _pad_rng(inst, "roster")
    for i in range(1, 201):
        lines.append("desk_%03d = %s" % (i, ["day", "night", "relief"][i % 3]))
    write_lines(root / "reporting_feeder_roster.conf", lines)


def write_reefer_papers(inst, root):
    rows = []
    planted = inst["cfg"]["unknown_state_rows"]
    seen = set()
    for r in inst["reefer_rows"]:
        if (planted and r["day_id"] == inst["day_id"]
                and r["record_state"] == "current" and r["id"] not in seen):
            seen.add(r["id"])
            planted -= 1
            # Its nameplate and window differ from the governing row, so a
            # solver that mistakes an unrecognised state for an applicable one
            # publishes a different reefer and loses the day.
            rows.append([r["day_id"], r["id"], r["plug_id"], r["vessel_id"],
                         r["temperature_class"],
                         str(as_int(r["nameplate_value"]) + 7),
                         r["nameplate_unit"],
                         str(max(0, as_int(r["connect_minute"]) - 45)),
                         r["disconnect_minute"], r["source_system"],
                         r["revision_seq"] + 40, "pending"])
        rows.append([r["day_id"], r["id"], r["plug_id"], r["vessel_id"],
                     r["temperature_class"], r["nameplate_value"],
                     r["nameplate_unit"], r["connect_minute"],
                     r["disconnect_minute"], r["source_system"],
                     r["revision_seq"], r["record_state"]])
    write_rows(root / "reefer_service_register.csv",
               ["day_id", "reefer_id", "plug_id", "vessel_id",
                "temperature_class", "nameplate_value", "nameplate_unit",
                "connect_minute", "disconnect_minute", "source_system",
                "revision_seq", "record_state"], rows, ",")

    rng = _pad_rng(inst, "thermal")
    rows = []
    for day in [inst["day_id"]] + inst["prior"]:
        for r in inst["reefers"][::2]:
            rows.append([day, r["id"], r["temperature_class"],
                         rng.between(-30, 12), rng.between(1, 9),
                         "probe_%02d" % rng.between(1, 24)])
    while len(rows) < 208:
        r = inst["reefers"][rng.below(len(inst["reefers"]))]
        rows.append([inst["prior"][0], r["id"], r["temperature_class"],
                     rng.between(-30, 12), rng.between(1, 9),
                     "probe_%02d" % rng.between(1, 24)])
    write_rows(root / "reefer_thermal_supplement.csv",
               ["day_id", "reefer_id", "temperature_class", "set_point_c",
                "probe_count", "probe_id"], rows, ",")

    rows = []
    for e in inst["energy_rows"]:
        rows.append([e["day_id"], e["reefer_id"], e["declared_value"],
                     e["energy_unit"], e["declaration_seq"],
                     e["record_state"]])
    write_rows(root / "energy_declaration_returns.psv",
               ["day_id", "reefer_id", "declared_value", "energy_unit",
                "declaration_seq", "record_state"], rows, "|")


def write_vessel_papers(inst, root):
    rng = _pad_rng(inst, "calls")
    rows = []
    for c in inst["calls"]:
        rows.append([c["day_id"], c["vessel_id"], c["name"], c["revision_seq"],
                     c["record_state"], c["cutoff_interval"],
                     c["urgency_rank"], c["service_group"], c["berth"],
                     c["destination"]])
    for day in inst["prior"]:
        for v in inst["vessels"]:
            for k in range(8):
                rows.append([day, v["id"], v["name"], k + 1,
                             "withdrawn" if k % 5 == 0 else "current",
                             rng.between(20, 94), rng.between(1, 4),
                             v["service_group"], v["berth"], v["destination"]])
    write_rows(root / "vessel_call_register.csv",
               ["day_id", "vessel_id", "vessel_name", "revision_seq",
                "record_state", "cutoff_interval", "urgency_rank",
                "service_group", "berth", "destination"], rows, ",")

    write_rows(root / "withdrawn_call_journal.tsv",
               ["day_id", "vessel_id", "revision_seq", "withdrawn_by",
                "withdrawal_note"], rows_of_withdrawn(inst), "\t")


def rows_of_withdrawn(inst):
    rng = _pad_rng(inst, "withdrawn")
    out = []
    for c in inst["withdrawn_calls"]:
        out.append([c["day_id"], c["vessel_id"], c["revision_seq"],
                    "berth_office", "the call revision was withdrawn by the "
                    "berth office before the cutoff was published"])
    for day in inst["prior"]:
        for v in inst["vessels"]:
            for k in range(0, 8, 5):
                out.append([day, v["id"], k + 1, "berth_office",
                            "an earlier withdrawal retained for the audit file"])
    while len(out) < 206:
        v = inst["vessels"][rng.below(len(inst["vessels"]))]
        out.append([inst["prior"][rng.below(len(inst["prior"]))], v["id"],
                    rng.between(1, 12), "vessel_agent",
                    "an earlier withdrawal retained for the audit file"])
    return out


def write_crane_papers(inst, root):
    lines = []
    for d in inst["crane_duties"]:
        lines.append(json.dumps({
            "day_id": d["day_id"], "crane_id": d["crane_id"],
            "interval": d["interval"], "duty_state": d["duty_state"],
            "demand_kw": d["demand_kw"], "feeder_id": d["feeder_id"],
            "duty_seq": d["duty_seq"],
        }, separators=(",", ":")))
    write_lines(root / "crane_duty_feed.ndjson", lines)

    lines = []
    for c in inst["crane_confirms"]:
        lines.append(json.dumps({
            "day_id": c["day_id"], "crane_id": c["crane_id"],
            "interval": c["interval"],
            "confirmation_state": c["confirmation_state"],
            "confirm_seq": c["confirm_seq"],
        }, separators=(",", ":")))
    rng = _pad_rng(inst, "confirm")
    while len(lines) < 214:
        c = inst["cranes"][rng.below(len(inst["cranes"]))]
        lines.append(json.dumps({
            "day_id": inst["prior"][rng.below(len(inst["prior"]))],
            "crane_id": c["id"], "interval": rng.between(1, 96),
            "confirmation_state": "landed", "confirm_seq": 2,
        }, separators=(",", ":")))
    write_lines(root / "crane_confirmation_journal.jsonl", lines)


def write_maintenance_papers(inst, root):
    rng = _pad_rng(inst, "maint")
    rows = []
    for w in inst["maintenance"]:
        rows.append([w["day_id"], w["resource_kind"], w["resource_id"],
                     w["first_interval"], w["last_interval"],
                     w["window_state"], w["notice_seq"]])
    while len(rows) < 209:
        f = inst["feeders"][rng.below(len(inst["feeders"]))]
        first = rng.between(1, 80)
        rows.append([inst["prior"][rng.below(len(inst["prior"]))], "feeder",
                     f["id"], first, first + rng.between(1, 8), "booked", 1])
    write_rows(root / "maintenance_window_register.csv",
               ["day_id", "resource_kind", "resource_id", "first_interval",
                "last_interval", "window_state", "notice_seq"], rows, ",")

    lines = []
    for n in inst["notices"]:
        lines.append(json.dumps(n, separators=(",", ":")))
    rng = _pad_rng(inst, "notice")
    idx = len(lines)
    while len(lines) < 203:
        idx += 1
        r = inst["reefers"][rng.below(len(inst["reefers"]))]
        lines.append(json.dumps({
            "notice_id": "ex_%04d" % (1000 + idx), "kind": "berth_shuffle",
            "day_id": inst["prior"][rng.below(len(inst["prior"]))],
            "subject_id": r["id"], "interval": 0,
            "note": "an earlier notice retained for the audit file",
        }, separators=(",", ":")))
    write_lines(root / "exception_notices.jsonl", lines)


def write_tariff_papers(inst, root):
    rows = []
    for t in inst["tariff_rows"]:
        rows.append([t["day_id"], t["interval"], t["band"],
                     t["price_tenth_cents_per_kwh"], t["schedule_seq"],
                     t["record_state"]])
    write_rows(root / "tariff_interval_schedule.csv",
               ["day_id", "interval", "tariff_band",
                "price_tenth_cents_per_kwh", "schedule_seq", "record_state"],
               rows, ",")

    rng = _pad_rng(inst, "bands")
    rows = []
    for day in [inst["day_id"]] + inst["prior"]:
        for rev in range(1, 8):
            for s in SUBSTATIONS:
                for b in inst["demand_bands"]:
                    if day == inst["day_id"] and rev == 7:
                        state = "current"
                        charge = b["charge_cents"]
                    else:
                        state = "superseded"
                        charge = b["charge_cents"] + rng.between(1, 300)
                    rows.append([day, rev, s, b["band_code"], b["floor_w"],
                                 b["ceiling_w"], charge, state])
                if len(rows) > 230:
                    break
            if len(rows) > 230:
                break
        if len(rows) > 230:
            break
    write_rows(root / "demand_charge_bands.tsv",
               ["day_id", "revision_seq", "substation_id", "band_code",
                "floor_w", "ceiling_w", "charge_cents", "record_state"],
               rows, "\t")

    rng = _pad_rng(inst, "legacy")
    rows = []
    while len(rows) < 212:
        rows.append([inst["prior"][rng.below(len(inst["prior"]))],
                     rng.between(1, 96),
                     TARIFF_BANDS[rng.below(len(TARIFF_BANDS))],
                     rng.between(60, 400), "retired"])
    write_rows(root / "legacy_tariff_extract.csv",
               ["day_id", "interval", "tariff_band",
                "price_tenth_cents_per_kwh", "extract_state"], rows, ",")


def write_battery_papers(inst, root):
    b = inst["battery"]
    lines = [
        "# operating policy for the yard storage battery",
        'day_id = "%s"' % inst["day_id"],
        'battery_id = "%s"' % b["id"],
        'substation_id = "%s"' % b["substation"],
        "capacity_wh = %d" % b["capacity_wh"],
        "initial_state_of_charge_wh = %d" % b["initial_soc_wh"],
        "reserve_wh = %d" % b["reserve_wh"],
        "max_charge_w = %d" % b["max_charge_w"],
        "max_discharge_w = %d" % b["max_discharge_w"],
        "charge_efficiency_permille = %d" % b["charge_efficiency_permille"],
        "discharge_efficiency_permille = %d" % b["discharge_efficiency_permille"],
        "charge_eligible_bands = [%s]" % ", ".join(
            '"%s"' % x for x in b["charge_bands"]),
    ]
    write_lines(root / "battery_operating_policy.toml", lines)

    rows = []
    for t in inst["battery_telemetry"]:
        rows.append([t["day_id"], t["interval"], t["availability_state"],
                     t["measured_soc_wh"], t["telemetry_seq"]])
    write_rows(root / "battery_telemetry_returns.csv",
               ["day_id", "interval", "availability_state", "measured_soc_wh",
                "telemetry_seq"], rows, ",")


def write_ambient_papers(inst, root):
    rng = _pad_rng(inst, "ambient")
    readings = []
    for day in [inst["day_id"]] + inst["prior"]:
        for iv in inst["intervals"]:
            readings.append({
                "day_id": day, "interval": iv["n"],
                "ambient_class": iv["ambient"] if day == inst["day_id"]
                else AMBIENT_CLASSES[rng.below(len(AMBIENT_CLASSES))],
                "dry_bulb_c": rng.between(2, 38),
            })
    table = []
    for (tc, ac), (num, den) in sorted(inst["controls"]["ambient_multiplier"].items()):
        table.append({"temperature_class": tc, "ambient_class": ac,
                      "multiplier_numerator": num,
                      "multiplier_denominator": den})
    payload = {
        "day_id": inst["day_id"],
        "day_reference": inst["day_reference"],
        "class_default_multiplier": {
            "multiplier_numerator": inst["controls"]["class_default_multiplier"][0],
            "multiplier_denominator": inst["controls"]["class_default_multiplier"][1],
        },
        "multiplier_table": table,
        "interval_readings": readings,
    }
    (root / "ambient_condition_returns.json").write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8", newline="\n")


def write_policy_papers(inst, root):
    lines = [
        "# the unit register. every quantity is converted into its base unit",
        "# through the entry its own record names.",
        'day_id = "%s"' % inst["day_id"],
        "",
        "[power]",
        "base_unit = \"w\"",
        "wh_h = { numerator = 1, denominator = 1 }",
        "kwh_h = { numerator = 1000, denominator = 1 }",
        "mj_h = { numerator = 2500, denominator = 9 }",
        "",
        "[energy]",
        "base_unit = \"wh\"",
        "wh = { numerator = 1, denominator = 1 }",
        "kwh = { numerator = 1000, denominator = 1 }",
        "mj = { numerator = 2500, denominator = 9 }",
        "",
        "[demand]",
        "base_unit = \"w\"",
        "kw = { numerator = 1000, denominator = 1 }",
        "",
        "[money]",
        "base_unit = \"cent\"",
        "tenth_cent = { numerator = 1, denominator = 10 }",
        "",
        "[time]",
        "base_unit = \"minute\"",
        "interval_minutes = 15",
        "intervals_per_day = 96",
    ]
    write_lines(root / "unit_register_dictionary.toml", lines)

    c = inst["controls"]
    lines = [
        "# the precedence hierarchy the priority queue and the deadline",
        "# correction pass are settled under.",
        'day_id = "%s"' % inst["day_id"],
        "ordering_keys = [%s]" % ", ".join('"%s"' % k for k in c["ordering_keys"]),
        "absent_call_slack_sentinel = 999",
        "vessel_critical_overturns_queue = true",
        "override_notice_kind = \"priority_override\"",
        "zone_waiver_notice_kind = \"zone_waiver\"",
        "",
        "[ladder]",
        "rung_order_source = \"dispatch_admission_ladder.txt\"",
        "first_matching_rung_settles = true",
        "",
        "[cluster]",
        "cluster_key = \"plug_id\"",
        "canonical_member = \"lowest reefer identifier among those the earlier rungs left standing\"",
    ]
    write_lines(root / "priority_precedence_policy.toml", lines)

    lines = [
        "# how the reconciliation passes are bounded and damped.",
        'day_id = "%s"' % inst["day_id"],
        "pass_budget_source = \"dispatch_operations_memo.pdf\"",
        "damping_source = \"substation_capacity_workbook.xlsx\"",
        "minimum_step_source = \"dispatch_operations_memo.pdf\"",
        "round_at_end_of_every_pass = true",
        "redistribution_scope = \"substation and service group\"",
        "spill_target = \"next eligible interval\"",
        "capacity_equality_is_lawful = true",
    ]
    write_lines(root / "reconciliation_pass_policy.toml", lines)

    lines = [
        "# how the precedence of a register row is settled.",
        "# where a stage specification states its own rule for choosing among the",
        "# rows of a register, that rule governs for that stage and the general",
        "# rule below does not apply to it.",
        'day_id = "%s"' % inst["day_id"],
        "day_filter_first = true",
        "record_state_filter_second = true",
        "highest_sequence_last = true",
        "",
        "[record_state]",
        "applicable = [\"current\", \"filed\", \"booked\", \"landed\"]",
        "set_aside = [\"superseded\", \"withdrawn\", \"cancelled\", \"retired\"]",
        "",
        "[sequence_field]",
        "reefer_service_register = \"revision_seq\"",
        "energy_declaration_returns = \"declaration_seq\"",
        "vessel_call_register = \"revision_seq\"",
        "feeder_capacity_register = \"revision_seq\"",
        "feeder_derating_notices = \"notice_seq\"",
        "tariff_interval_schedule = \"schedule_seq\"",
        "demand_charge_bands = \"revision_seq\"",
        "plug_zone_admission_matrix = \"revision_seq\"",
        "maintenance_window_register = \"notice_seq\"",
        "crane_confirmation_journal = \"confirm_seq\"",
    ]
    write_lines(root / "revision_precedence.toml", lines)

    lines = [
        "# the published form of every document.",
        'day_id = "%s"' % inst["day_id"],
        "whole_quantities = \"written as a whole number with no sign on zero\"",
        "ratios = \"written at exactly nine decimal places\"",
        "money = \"written in whole cents\"",
        "power = \"written in whole watts\"",
        "energy = \"written in whole watt hours\"",
        "negative_zero = \"never published\"",
        "absent_marker = \"-\"",
        "",
        "[state_words]",
        "powered = \"powered\"",
        "held = \"held\"",
        "spilled = \"spilled\"",
        "refused = \"refused\"",
        "unmet = \"unmet\"",
        "met = \"met\"",
    ]
    write_lines(root / "publication_form_rules.toml", lines)

    lines = [
        "# rounding and arithmetic policy",
        "arithmetic: exact rational",
        "binary_floating_point: forbidden",
        "carry_between_stages: forbidden",
        "rule: |",
        "  every stage converts, multiplies, divides, rounds by the rule its",
        "  own specification names, stores the rounded whole number, and every",
        "  later stage reads that stored number. no stage carries a hidden",
        "  remainder past its own rounding step.",
        "rounding_rules:",
        "  half_up: a remainder of exactly one half is carried away from zero",
        "  floor: the largest whole number at or below the value",
        "  ceiling: the smallest whole number at or above the value",
        "placement:",
        "  p01_normalisation: half_up",
        "  p03_energy_floor_per_interval: half_up",
        "  p05_provisional_draw: exact",
        "  p07_crane_adjusted_capacity: floor",
        "  p08_battery_draw: floor",
        "  p08_battery_state_of_charge: ceiling",
        "  p09_reconciliation_share: half_up at the end of every pass",
        "  p10_interval_charge: half_up at the end of every interval",
        "  p13_objective_ratio: nine decimal places, half_up",
    ]
    write_lines(root / "rounding_and_arithmetic_policy.yaml", lines)

    lines = [
        "# boundary conventions",
        "connection_window: |",
        "  a connection window runs from the connect minute inclusive to the",
        "  disconnect minute exclusive.",
        "interval_membership: |",
        "  interval n covers the minutes from fifteen times n minus one",
        "  inclusive to fifteen times n exclusive. an interval belongs to a",
        "  window when the two overlap in at least one minute.",
        "capacity_equality: |",
        "  a load equal to the capacity is lawful. only a load above the",
        "  capacity is a violation.",
        "state_of_charge_equality: |",
        "  a state of charge equal to the reserve is lawful. nothing may be",
        "  drawn from it while it sits there.",
        "demand_band_boundary: |",
        "  a peak equal to the floor of a band belongs to that band.",
        "peak_tie: |",
        "  when two intervals carry the same peak the earlier interval is the",
        "  certified one.",
        "empty_group: |",
        "  a group with no member publishes its row with a zero measure and",
        "  the state word its stage names.",
    ]
    write_lines(root / "boundary_conventions.yaml", lines)


def write_ladder_paper(inst, root):
    lines = [
        "ASHGROVE POINT REEFER YARD",
        "dispatch admission ladder for %s" % inst["day_id"],
        "",
        "The ladder is read from the top. The first rung that catches a reefer",
        "settles it and no lower rung is consulted for that reefer. This",
        "printed order is the order of application. It is not the alphabetical",
        "order of the rung codes.",
        "",
    ]
    for i, rung in enumerate(LADDER_RUNGS, start=1):
        lines.append("rung %d  %s" % (i, rung))
        lines.append("        %s" % REFUSAL_TEXT[rung])
        lines.append("")
    lines.append("applicability by source system")
    lines.append("")
    sources = ["yard_office", "gate_terminal", "quay_desk", "reefer_desk"]
    n = 0
    for rung in LADDER_RUNGS:
        for src in sources:
            for k in range(1, 10):
                n += 1
                lines.append("  %-24s %-14s revision %d  applies"
                             % (rung, src, k))
    write_lines(root / "dispatch_admission_ladder.txt", lines)

    rng = _pad_rng(inst, "source")
    rows = []
    for day in [inst["day_id"]] + inst["prior"]:
        for rev in range(1, 6):
            for i, src in enumerate(sources):
                state = "current" if rev == 5 else "retired"
                # A retired row carries the highest revision sequence on the
                # operating day, so the state filter bites on its own.
                if day == inst["day_id"] and rev == 5 and i == 1:
                    state = "current"
                rank = i + 1 if (day == inst["day_id"] and rev == 5) \
                    else rng.between(1, 4)
                rows.append([day, rev, src, rank, state])
    for i, src in enumerate(sources):
        rows.append([inst["day_id"], 9, src, 4 - i, "retired"])
    while len(rows) < 206:
        rows.append([inst["prior"][0], rng.between(6, 12),
                     sources[rng.below(4)], rng.between(1, 4), "retired"])
    write_rows(root / "source_priority_register.csv",
               ["day_id", "revision_seq", "source_system", "priority_rank",
                "record_state"], rows, ",")


def write_audit_db(inst, root):
    rng = _pad_rng(inst, "audit")
    rows = []
    for i in range(1, 231):
        rows.append((
            "au_%04d" % i,
            inst["prior"][i % len(inst["prior"])],
            "night_office",
            ["opened", "closed", "amended", "noted"][i % 4],
            "entry retained for the audit file",
            str(rng.between(1, 96)),
        ))
    write_sqlite(root / "night_office_audit.db", {
        "audit_entries": (["entry_id", "day_id", "desk", "action", "note",
                           "interval"], rows),
    })


# --------------------------------------------------------------------------
# the three office papers
#
# The workbook carries six sheets and only one of them governs this operating
# day. The live sheet is the one whose key cell carries this day reference.
# Neither its position, nor its position from the end, nor its sorted rank,
# nor its name is stable across operating days.
# --------------------------------------------------------------------------


def _sheet_rows(inst, reference, live, rng):
    c = inst["controls"]
    rows = [["Ashgrove Point substation capacity workbook"],
            ["day reference", reference],
            ["sheet state", "governing" if live else "retained"],
            []]
    damp_n = c["damping_num"] if live else rng.between(2, 15)
    damp_d = c["damping_den"] if live else rng.between(17, 32)
    charge = c["base_service_charge_cents"] if live else rng.between(700, 2600)
    rows.append(["control", "numerator", "denominator"])
    rows.append(["reconciliation damping fraction", damp_n, damp_d])
    rows.append(["base service charge cents", charge, 1])
    rows.append([])
    rows.append(["temperature class", "maintenance coefficient numerator",
                 "maintenance coefficient denominator"])
    for tc in TEMP_CLASSES:
        num, den = c["maintenance_coefficient"][tc]
        if not live:
            num = num + rng.between(11, 190)
        rows.append([tc, num, den])
    rows.append([])
    rows.append(["vessel", "share ceiling wh"])
    for v in inst["vessels"]:
        val = c["vessel_share_ceiling_wh"][v["id"]]
        if not live:
            val = val + rng.between(1000, 9000)
        rows.append([v["id"], val])
    rows.append([])
    rows.append(["substation", "ceiling w"])
    for s in SUBSTATIONS:
        val = c["substation_ceiling_w"][s]
        if not live:
            val = val + rng.between(1000, 9000)
        rows.append([s, val])
    rows.append([])
    rows.append(["feeder", "cable class", "survey note"])
    for f in inst["feeders"]:
        rows.append([f["id"], "cc_%d" % rng.between(1, 6),
                     "cable surveyed on the standing programme"])
    while len(rows) < 42:
        rows.append(["survey line %d" % len(rows), rng.between(1, 99),
                     "retained for the engineering file"])
    return rows


def write_workbook(inst, root):
    rng = _pad_rng(inst, "workbook")
    names = _sheet_names(inst)
    live_index = inst["cfg"]["sheet_index"]
    sheets = {}
    for i, name in enumerate(names):
        if i == live_index:
            reference = inst["day_reference"]
        else:
            reference = "DSP-%06d" % ((inst["seed"] + 7919 * (i + 1)) % 1000000)
            if reference == inst["day_reference"]:
                reference = "DSP-%06d" % ((inst["seed"] + 104729 * (i + 3)) % 1000000)
        sheets[name] = _sheet_rows(inst, reference, i == live_index, rng)
    write_xlsx(root / "substation_capacity_workbook.xlsx", sheets)


def write_memo(inst, root):
    c = inst["controls"]
    rng = _pad_rng(inst, "memo")
    lines = [
        "ASHGROVE POINT REEFER YARD",
        "dispatch operations memorandum",
        "operating day %s      day reference %s" % (inst["day_id"],
                                                    inst["day_reference"]),
        "",
        "1  RECONCILIATION PASSES",
        "",
        "   The load reconciliation is worked as a bounded sequence of passes.",
        "   The pass budget for this operating day is %d passes." % c["pass_budget"],
        "   The budget is spent whether or not the shares have settled. A pass",
        "   that would move a share by less than the minimum step moves it by",
        "   the minimum step instead.",
        "",
        "   pass budget                  %d" % c["pass_budget"],
        "   minimum step watt hours      %d" % c["minimum_step_wh"],
        "   dependency protection depth  %d" % c["protection_depth"],
        "",
        "2  DEADLINE SURCHARGE LADDER",
        "",
        "   A reefer that leaves its mandatory floor unmet at the vessel",
        "   cutoff carries a surcharge read off the rung its shortfall reaches,",
        "   measured in whole intervals of shortfall.",
        "",
        "   intervals short    surcharge cents",
    ]
    for lo, cents in c["surcharge_ladder"]:
        lines.append("   %-18d %d" % (lo, cents))
    lines += [
        "",
        "   The rung that governs is the highest rung whose interval figure is",
        "   at or below the shortfall.",
        "",
        "3  CRANE GANG ROSTER",
        "",
        "   gang        crane      shift        supervisor",
    ]
    for i, cr in enumerate(inst["cranes"]):
        lines.append("   %-11s %-10s %-12s %s"
                     % (cr["gang"], cr["id"],
                        ["day", "night", "relief"][i % 3],
                        "supervisor_%02d" % (i + 1)))
    lines += [
        "",
        "4  STANDING NOTES",
        "",
    ]
    # Eight standing warnings, then the administrative notes the duty desk
    # files against the yard's own plant. The administrative notes settle
    # nothing and are deliberately distinct: a memo that repeated one line
    # twenty times would be padding rather than a record.
    notes = [
        "the standing reserve of a feeder is withheld before any free capacity is counted",
        "a crane duty reduces the capacity available to reefers and is not an extra load",
        "the state of charge may sit on the reserve and nothing may be drawn from it there",
        "a load equal to the capacity is lawful and is not a violation",
        "a displaced reefer moves to the next eligible interval and not to the cheapest one",
        "the pass budget is spent even where the shares are still moving",
        "the ambient multiplier absent for a class pairing falls back to the class default",
        "a peak equal to the floor of a demand band belongs to that band",
    ]
    # One bucket per kind of entry, each shuffled, then taken round robin so
    # consecutive notes differ in kind the way a desk log does.
    buckets = []
    for template, rows in (
        ("%s was walked at the shift handover and its cabinet read sealed",
         [f["id"] for f in inst["feeders"]]),
        ("the earth bond of %s was tested at the quarterly inspection",
         [f["id"] for f in inst["feeders"]]),
        ("%s carries a spare contactor in the quay store",
         [f["id"] for f in inst["feeders"]]),
        ("%s is listed on the night office key register",
         [f["id"] for f in inst["feeders"]]),
        ("%s had its rail clamps greased by the maintenance gang",
         [c["id"] for c in inst["cranes"]]),
        ("the load cell of %s was recalibrated last quarter",
         [c["id"] for c in inst["cranes"]]),
        ("%s keeps a laminated plug zone card in its cab",
         [c["id"] for c in inst["cranes"]]),
        ("the agent for %s asked to be called on arrival",
         [v["id"] for v in inst["vessels"]]),
        ("%s lodged its manifest with the berth office on time",
         [v["id"] for v in inst["vessels"]]),
        ("%s is booked against the berth its previous call used",
         [v["id"] for v in inst["vessels"]]),
        ("the switchroom of %s is reached through the north stair", list(SUBSTATIONS)),
        ("%s keeps its single line diagram inside the panel door", list(SUBSTATIONS)),
        ("%s was photographed for the condition file",
         [q["id"] for q in inst["plugs"]]),
        ("the lid gasket of %s is due for replacement next season",
         [q["id"] for q in inst["plugs"]]),
    ):
        buckets.append([template % name for name in rng.shuffled(sorted(set(rows)))])
    pool = []
    while len(pool) < 164 - len(notes):
        drained = True
        for bucket in buckets:
            if bucket:
                pool.append(bucket.pop())
                drained = False
        if drained:
            break
    notes = notes + pool[:164 - len(notes)]
    if len(notes) != 164 or len(set(notes)) != 164:
        raise RuntimeError("the standing notes are not 164 distinct lines")
    for i, note in enumerate(notes, start=1):
        lines.append("   note %03d   %s" % (i, note))
    write_pdf(root / "dispatch_operations_memo.pdf", lines)


def write_directive(inst, root):
    c = inst["controls"]
    rng = _pad_rng(inst, "directive")
    blocks = [
        ("p", "ASHGROVE POINT REEFER YARD"),
        ("p", "priority ordering directive for operating day %s" % inst["day_id"]),
        ("p", "day reference %s" % inst["day_reference"]),
        ("p", "The dispatch priority queue is ordered on the four keys below, "
              "read in the key position order this directive prints. Every key "
              "is read ascending. The reefer identifier settles any remaining "
              "tie and no two reefers share one."),
        ("table", [["key position", "ordering key", "direction"]] +
         [[str(i + 1), k, "ascending"]
          for i, k in enumerate(c["ordering_keys"])]),
        ("p", "The class rank of a temperature class is the rank this "
              "directive prints for it. A lower rank is served earlier."),
        ("table", [["temperature class", "class rank"]] +
         [[tc, str(c["class_rank"][tc])] for tc in TEMP_CLASSES]),
        ("p", "The standing service order below is retained for the vessel "
              "agents and settles nothing on its own."),
    ]
    table = [["line", "vessel", "temperature class", "service group",
              "standing order"]]
    n = 0
    for v in inst["vessels"]:
        for tc in TEMP_CLASSES:
            for k in range(1, 6):
                n += 1
                table.append([str(n), v["id"], tc, v["service_group"],
                              str(rng.between(1, 40))])
                if n >= 210:
                    break
            if n >= 210:
                break
        if n >= 210:
            break
    blocks.append(("table", table))
    write_docx(root / "priority_ordering_directive.docx", blocks)


# --------------------------------------------------------------------------
# the written papers
# --------------------------------------------------------------------------


def write_guidance_papers(inst, root):
    day = inst["day_id"]
    ref = inst["day_reference"]

    write_lines(root / "readme_first.txt", [
        "ASHGROVE POINT REEFER YARD",
        "working papers for operating day %s" % day,
        "",
        "These papers were minted for this operating day alone. Nothing",
        "outside this directory settles anything about it.",
        "",
        "Read terminal_contract_overview.md next. It names the fourteen",
        "stages of the recomputation and the specification paper that",
        "governs each of them.",
        "",
        "data_lineage.md maps every paper in this directory to the stage it",
        "feeds and names the papers that govern nothing.",
        "",
        "File names describe a role and not a content. Open them.",
        "",
        "Three papers are not plain text. The substation capacity workbook,",
        "the dispatch operations memorandum and the priority ordering",
        "directive carry control values that appear nowhere else.",
        "",
        "The operating day identifier and the day reference are the pair",
        "carried by the topology paper. Every register in this directory",
        "holds rows for earlier operating days as well, and those rows",
        "govern nothing here.",
    ])

    lines = [
        "# Terminal contract overview",
        "",
        "Operating day %s, day reference %s." % (day, ref),
        "",
        "The recomputation is worked in fourteen stages, in the order below.",
        "Each stage reads the papers its own specification names, stores the",
        "whole numbers that specification tells it to store, and hands those",
        "stored numbers to the stage after it. No stage reaches back into a",
        "quantity an earlier stage rounded away.",
        "",
    ]
    stages = [
        ("p01", "unit normalisation", "spec_stage_p01_unit_normalisation.md"),
        ("p02", "availability lattice", "spec_stage_p02_availability_lattice.md"),
        ("p03", "mandatory energy floor", "spec_stage_p03_energy_floor.md"),
        ("p04", "dispatch priority queue", "spec_stage_p04_priority_queue.md"),
        ("p05", "provisional allocation", "spec_stage_p05_provisional_allocation.md"),
        ("p06", "feeder reconciliation", "spec_stage_p06_feeder_reconciliation.md"),
        ("p07", "crane adjusted capacity", "spec_stage_p07_crane_interaction.md"),
        ("p08", "battery intervention", "spec_stage_p08_battery_intervention.md"),
        ("p09", "load reconciliation passes", "spec_stage_p09_load_reconciliation.md"),
        ("p10", "tariff and demand charge", "spec_stage_p10_tariff_and_demand.md"),
        ("p11", "deadline correction", "spec_stage_p11_deadline_correction.md"),
        ("p12", "cycle detection and break", "spec_stage_p12_cycle_break.md"),
        ("p13", "objective reconciliation", "spec_stage_p13_objective.md"),
        ("p14", "publication", "spec_stage_p14_publication.md"),
    ]
    for code, title, paper in stages:
        lines.append("Stage %s, %s. Specification `%s`." % (code, title, paper))
        lines.append("")
    lines += [
        "The arithmetic policy in rounding_and_arithmetic_policy.yaml and the",
        "boundary conventions in boundary_conventions.yaml apply to every",
        "stage. The publication form rules and the serialisation contract",
        "apply to every published document.",
        "",
        "Three control papers are read once and used throughout. The",
        "substation capacity workbook carries the reconciliation damping",
        "fraction, the maintenance coefficients, the base service charge, the",
        "vessel share ceilings and the substation ceilings. The dispatch",
        "operations memorandum carries the pass budget, the minimum step, the",
        "dependency protection depth, the deadline surcharge ladder and the",
        "crane gang roster. The priority ordering directive carries the four",
        "ordering keys in their key positions and the class rank of every",
        "temperature class.",
    ]
    write_lines(root / "terminal_contract_overview.md", lines)

    lines = [
        "# Data lineage",
        "",
        "Every paper in this directory, the stage it feeds and what it",
        "settles.",
        "",
        "| paper | stage | what it settles |",
        "| --- | --- | --- |",
        "| substation_topology.xml | p01 | the operating day and its reference, the feeders in force and their plugs |",
        "| feeder_capacity_register.csv | p01 p05 p06 | the nominal capacity and the standing reserve of every feeder |",
        "| plug_assignment_register.csv | p01 | the feeder and the zone of every plug |",
        "| reefer_service_register.csv | p01 | the reefers presented for the operating day |",
        "| energy_declaration_returns.psv | p01 | the declared energy of a reefer |",
        "| unit_register_dictionary.toml | p01 | the conversion of every quoted unit into its base unit |",
        "| vessel_call_register.csv | p01 p04 | the applicable call of every vessel |",
        "| withdrawn_call_journal.tsv | p01 | the call revisions the berth office withdrew |",
        "| interval_grid_calendar.csv | p02 p08 p10 | the ninety six intervals and the tariff band of each |",
        "| maintenance_window_register.csv | p02 p07 p08 | the booked windows that take a resource out |",
        "| ambient_condition_returns.json | p03 | the ambient class of every interval and the multiplier table |",
        "| plug_zone_admission_matrix.csv | p04 | the temperature classes a plug zone admits |",
        "| dispatch_admission_ladder.txt | p04 | the rungs and the order they are read in |",
        "| exception_notices.jsonl | p04 p11 | the zone waivers and the priority overrides |",
        "| priority_ordering_directive.docx | p04 | the ordering keys and the class ranks |",
        "| feeder_derating_notices.csv | p05 | the derating that applies to a feeder over a span |",
        "| crane_duty_feed.ndjson | p07 | the crane duty demand of every interval |",
        "| crane_confirmation_journal.jsonl | p07 | whether a crane duty landed or was called off |",
        "| battery_operating_policy.toml | p08 | the battery capacity, reserve, limits and efficiencies |",
        "| battery_telemetry_returns.csv | p08 | the intervals the battery was online for |",
        "| substation_capacity_workbook.xlsx | p03 p09 p10 | the damping fraction, the maintenance coefficients, the base service charge, the vessel share ceilings and the substation ceilings |",
        "| dispatch_operations_memo.pdf | p09 p11 p13 | the pass budget, the minimum step, the protection depth and the surcharge ladder |",
        "| reconciliation_pass_policy.toml | p06 p09 | the scope of the spill and of the redistribution |",
        "| priority_precedence_policy.toml | p04 p11 | the precedence hierarchy and the absent call sentinel |",
        "| revision_precedence.toml | every stage | how a register row is set aside and which sequence field settles it |",
        "| tariff_interval_schedule.csv | p10 | the price of every interval |",
        "| demand_charge_bands.tsv | p10 | the demand charge band of a substation peak |",
        "| source_priority_register.csv | p04 | the priority rank of a source system |",
        "| reporting_feeder_roster.conf | p14 | the substations whose report is published |",
        "| rounding_and_arithmetic_policy.yaml | every stage | where each stage rounds and by which rule |",
        "| boundary_conventions.yaml | every stage | the inclusive and exclusive boundaries |",
        "| publication_form_rules.toml | p14 | the written form of every published quantity |",
        "| output_schema_reference.md | p14 | the header, the column order and the row order of every document |",
        "| serialisation_and_digest_contract.md | p14 | the encoding, the line endings and the two digests |",
        "| reeferdispatch_program_contract.md | p14 | the contract the delivered program answers |",
        "| worked_examples.md | p14 | the form of the free text documents |",
        "| glossary_and_field_dictionary.md | reference | the field names and what they mean |",
        "| known_traps_and_footguns.md | reference | the readings that have gone wrong before |",
        "| corpus_sentinel_note.txt | reference | the branches this operating day leaves unreached |",
        "",
        "## Papers that govern nothing",
        "",
        "Three papers are retained for the audit file and settle no published",
        "quantity on this operating day.",
        "",
        "reefer_thermal_supplement.csv carries probe set points. No stage",
        "reads a set point.",
        "",
        "legacy_tariff_extract.csv carries a retired price extract. The price",
        "of an interval is settled by tariff_interval_schedule.csv alone.",
        "",
        "night_office_audit.db carries desk entries against earlier operating",
        "days. No stage reads it.",
    ]
    write_lines(root / "data_lineage.md", lines)

    lines = [
        "# Glossary and field dictionary",
        "",
        "adjusted capacity. The capacity left for reefers on a feeder in an",
        "interval once the standing reserve has been withheld and the",
        "confirmed crane duty has been taken off. Never below zero.",
        "",
        "allowance. Energy granted to a reefer beyond its mandatory floor out",
        "of the day headroom of its feeder, settled by the reconciliation",
        "passes and then placed into intervals.",
        "",
        "applicable row. The row of a register that governs a key: the row",
        "carries this operating day, its record state is an applicable one,",
        "and among those rows it carries the highest sequence.",
        "",
        "base draw. The watt draw of a reefer in an interval, which is the",
        "whole watt figure RULE P03.i stores. It is not four times the stored",
        "watt hour floor of that interval: the floor and the draw are two",
        "separate roundings of the same quantity and neither is derived from",
        "the other.",
        "",
        "cluster. The set of reefers naming one plug.",
        "",
        "day headroom. The sum over the intervals of a feeder of the adjusted",
        "capacity plus the battery support less the reconciled load.",
        "",
        "discretionary energy. The requested energy of a reefer less its",
        "mandatory floor, never below zero.",
        "",
        "mandatory floor. The energy a reefer must take to hold its",
        "temperature over the intervals it is connected for.",
        "",
        "reserved capacity. The nominal capacity of a feeder in an interval",
        "less its standing reserve, never below zero.",
        "",
        "set aside. A row whose record state reads superseded, withdrawn,",
        "cancelled or retired. It is dropped before any sequence is read.",
        "",
        "shortfall. The mandatory floor a reefer required at or before its",
        "vessel cutoff less what it was served at or before that cutoff.",
        "",
        "spill. The move of a placement out of an interval a reconciliation",
        "removed it from and into the next interval that admits it.",
        "",
        "standing reserve. The watts a feeder withholds before any free",
        "capacity is counted.",
        "",
        "## Field names",
        "",
        "day_id. The operating day a row belongs to.",
        "record_state. current, filed, booked and landed are applicable.",
        "superseded, withdrawn, cancelled and retired are set aside.",
        "revision_seq, declaration_seq, notice_seq, schedule_seq, confirm_seq,",
        "duty_seq, telemetry_seq. The sequence field of a register, named per",
        "register in revision_precedence.toml.",
        "interval. An interval ordinal from 1 to 96.",
        "nameplate_value and nameplate_unit. The quoted running power of a",
        "reefer and the unit it is quoted in.",
        "declared_value and energy_unit. The quoted energy a reefer asks for.",
        "demand_kw. Crane duty demand, quoted in kilowatts.",
        "derate_permille. Parts per thousand of the nominal capacity that a",
        "derating notice leaves standing.",
    ]
    write_lines(root / "glossary_and_field_dictionary.md", lines)

    lines = [
        "# Known traps and footguns",
        "",
        "Readings that have gone wrong on earlier operating days. Each is",
        "settled by a stage specification; this paper only warns.",
        "",
        "A load equal to the capacity is lawful. Only a load above the",
        "capacity is a violation.",
        "",
        "A state of charge equal to the reserve is lawful. Nothing may be",
        "drawn from it while it sits there.",
        "",
        "The standing reserve of a feeder is withheld before any free",
        "capacity is counted, not after.",
        "",
        "A confirmed crane duty reduces the capacity available to reefers. It",
        "is not an extra load added to the reefer load, and the published",
        "adjusted capacity shows the difference.",
        "",
        "A disconnection minute is open. A window that closes on an interval",
        "boundary closes the interval before it.",
        "",
        "An absent ambient multiplier falls back to the class default. It is",
        "not a multiplier of zero.",
        "",
        "A declared energy return carrying the not supplied marker is a",
        "return with no declared energy. It is not a declaration of zero.",
        "",
        "A displaced placement moves to the next interval that admits it. It",
        "does not move to the cheapest interval of the day.",
        "",
        "The reconciliation pass budget is spent whether or not the shares",
        "have settled. It is not a guard on a convergence loop.",
        "",
        "The reconciliation rounds at the end of every pass and the next pass",
        "opens from the rounded share.",
        "",
        "What a share ceiling frees is redistributed inside the cross",
        "classification of substation and service group, not across the whole",
        "feeder.",
        "",
        "The workbook sheet that governs is the one whose key cell carries",
        "this day reference. Its position, its position from the end, its",
        "sorted rank and its name all move from one operating day to the",
        "next.",
        "",
        "The admission ladder is read in the order the ladder paper prints.",
        "That order is not the alphabetical order of the rung codes.",
        "",
        "A set aside row is dropped before the sequence is read, so a set",
        "aside row carrying the highest sequence settles nothing.",
        "",
        "The objective is lexicographic. A schedule with a lower energy cost",
        "still loses when an earlier component of the vector is worse.",
    ]
    write_lines(root / "known_traps_and_footguns.md", lines)

    write_lines(root / "corpus_sentinel_note.txt", [
        "SENTINEL NOTE",
        "",
        "This operating day does not reach every branch the stage",
        "specifications describe. Before deciding a branch is absent, read",
        "this note.",
        "",
        "The outcomes below are described by their stage specifications and",
        "are left unreached by this operating day. Implement them from those",
        "specifications.",
        "",
        "  BATTERY_BELOW_RESERVE   the state of charge falling under the",
        "                          reserve, which stage p08 forbids and stage",
        "                          p13 counts as a hard violation",
        "",
        "  DR_STATE_UNKNOWN        a reefer row whose record state is a word",
        "                          revision_precedence.toml carries in",
        "                          neither list",
        "",
        "  CYCLE_CLOSE_SETTLED     a correction sweep applying no",
        "                          displacement at all, which stage p12",
        "                          closes with a settled closing state",
        "",
        "  PEAK_ON_A_BAND_FLOOR    a substation peak landing exactly on the",
        "                          floor of a demand charge band, which stage",
        "                          p10 places in that band",
        "",
        "  YARD_PEAK_TIE           two intervals carrying the same yard peak,",
        "                          which stage p10 settles by taking the",
        "                          earlier interval",
        "",
        "  POOL_FULLY_ALLOCATED    a reconciliation pass opening with the",
        "                          day pool of a feeder already allocated",
        "                          in full, which stage p09 settles by",
        "                          holding every target at its standing",
        "                          share",
        "",
        "  CHARGE_NO_ROOM          a charging interval whose charge comes",
        "                          out at zero, which stage p08 settles",
        "                          with a limit reason of no_room",
        "",
        "  SHARE_STEP_DOWNWARD     a reconciliation pass whose damped move",
        "                          lowers a share by less than the minimum",
        "                          step, which stage p09 settles by",
        "                          lowering it by the minimum step",
        "",
        "  CHARGE_AT_CAPACITY      a charging interval whose charge is held",
        "                          to the room left under the capacity,",
        "                          which stage p08 settles with a limit",
        "                          reason of capacity_limit",
        "",
        "  CHARGE_AT_HEADROOM      a charging interval whose charge is held",
        "                          to the substation headroom, which stage",
        "                          p08 settles with a limit reason of",
        "                          headroom_limit",
        "",
        "Every other outcome named by a stage specification is reached at",
        "least once on this operating day.",
    ])


DELIMITED_SCHEMA = [
    ("availability_lattice.csv", ",",
     ["reefer_id", "first_interval", "last_interval", "slot_count",
      "window_state"]),
    ("interval_demand.csv", ",",
     ["interval", "feeder_id", "connected_count", "nominal_demand_w"]),
    ("energy_floor_ledger.csv", ",",
     ["reefer_id", "slot_count", "mandatory_wh", "requested_wh",
      "discretionary_wh", "floor_state"]),
    ("dispatch_priority_queue.csv", ",",
     ["rank", "reefer_id", "deadline_slack", "class_rank", "urgency_rank",
      "queue_state"]),
    ("provisional_allocation.psv", "|",
     ["interval", "feeder_id", "reefer_id", "draw_w", "allocation_state"]),
    ("feeder_load_ledger.csv", ",",
     ["interval", "feeder_id", "capacity_w", "reserve_w",
      "reserved_capacity_w", "load_w", "headroom_w", "load_state"]),
    ("feeder_violation_ledger.csv", ",",
     ["interval", "feeder_id", "provisional_load_w", "reserved_capacity_w",
      "excess_w", "removed_count"]),
    ("spill_decisions.tsv", "tab",
     ["reefer_id", "from_interval", "to_interval", "feeder_id", "draw_w",
      "spill_state"]),
    ("crane_adjusted_capacity.csv", ",",
     ["interval", "feeder_id", "reserved_capacity_w", "crane_draw_w",
      "adjusted_capacity_w", "clamp_state"]),
    ("battery_schedule.csv", ",",
     ["interval", "action", "deficit_wh", "discharge_wh", "charge_wh",
      "limit_reason"]),
    ("soc_ledger.psv", "|",
     ["interval", "opening_soc_wh", "closing_soc_wh", "reserve_wh",
      "soc_state"]),
    ("reconciliation_iterations.csv", ",",
     ["pass", "feeder_id", "reefer_id", "opening_share_wh", "need_wh",
      "target_wh", "closing_share_wh", "pass_state"]),
    ("tariff_charge_ledger.csv", ",",
     ["interval", "tariff_band", "price_tenth_cents_per_kwh", "load_w",
      "energy_wh", "charge_cents"]),
    ("deadline_correction.csv", ",",
     ["reefer_id", "interval", "displaced_reefer_id", "feeder_id",
      "correction_state"]),
    ("final_schedule.csv", ",",
     ["interval", "feeder_id", "reefer_id", "base_draw_w", "allowance_wh",
      "energy_wh", "schedule_state"]),
    ("final_schedule_by_feeder.psv", "|",
     ["feeder_id", "interval", "load_w", "adjusted_capacity_w",
      "battery_support_w", "feeder_state"]),
    ("unmet_requirement_report.tsv", "tab",
     ["reefer_id", "feeder_id", "vessel_id", "shortfall_wh",
      "shortfall_intervals", "unplaced_allowance_wh", "surcharge_cents"]),
    ("reefer_service_certificate.csv", ",",
     ["reefer_id", "feeder_id", "vessel_id", "required_wh", "served_wh",
      "shortfall_wh", "shortfall_intervals", "allowance_wh",
      "unplaced_allowance_wh", "surcharge_cents", "service_state"]),
]

ROW_ORDER = {
    "availability_lattice.csv": "reefer identifier ascending",
    "interval_demand.csv": "interval ascending, then feeder identifier ascending",
    "energy_floor_ledger.csv": "reefer identifier ascending",
    "dispatch_priority_queue.csv":
        "the queued reefers by rank ascending, then the reefers the ladder set "
        "aside by reefer identifier ascending",
    "provisional_allocation.psv":
        "interval ascending, then feeder identifier, then reefer identifier",
    "feeder_load_ledger.csv": "interval ascending, then feeder identifier",
    "feeder_violation_ledger.csv": "interval ascending, then feeder identifier",
    "spill_decisions.tsv":
        "from interval ascending, then feeder identifier, then reefer identifier",
    "crane_adjusted_capacity.csv": "interval ascending, then feeder identifier",
    "battery_schedule.csv": "interval ascending",
    "soc_ledger.psv": "interval ascending",
    "reconciliation_iterations.csv":
        "pass ascending, then feeder identifier, then reefer identifier",
    "tariff_charge_ledger.csv": "interval ascending",
    "deadline_correction.csv":
        "interval ascending, then feeder identifier, then reefer identifier",
    "final_schedule.csv":
        "interval ascending, then feeder identifier, then reefer identifier",
    "final_schedule_by_feeder.psv": "feeder identifier, then interval ascending",
    "unmet_requirement_report.tsv": "reefer identifier ascending",
    "reefer_service_certificate.csv": "reefer identifier ascending",
}


def write_contract_papers(inst, root):
    day = inst["day_id"]
    lines = [
        "# Output schema reference",
        "",
        "Every published document, its delimiter, its header and its row",
        "order. A header is written once, as the first line, with the columns",
        "in the order below and nothing else on the line.",
        "",
    ]
    for name, sep, header in DELIMITED_SCHEMA:
        word = {",": "comma", "|": "vertical bar", "tab": "tab"}[sep]
        lines.append("## `%s`" % name)
        lines.append("")
        lines.append("delimiter: %s" % word)
        lines.append("")
        lines.append("header: %s" % ", ".join(header))
        lines.append("")
        lines.append("row order: %s" % ROW_ORDER[name])
        lines.append("")
    lines += [
        "## `normalised_reefers.jsonl`",
        "",
        "One object per reefer, in reefer identifier order, with the keys in",
        "this order: reefer_id, plug_id, feeder_id, substation_id, vessel_id,",
        "temperature_class, nameplate_w, unit_state, connect_minute,",
        "disconnect_minute, declared_energy_wh, source_system. Every value is",
        "a string except nameplate_w, connect_minute and disconnect_minute,",
        "which are numbers, and declared_energy_wh, which is a number when a",
        "return declared one and the string not_declared when none did.",
        "",
        "## `audit_trace.jsonl`",
        "",
        "One object per stage, in stage order, with the keys stage, note and",
        "measure. The note is the stage title the contract overview prints,",
        "without the stage label that precedes it. RULE P14.i of",
        "spec_stage_p14_publication.md settles what the measure of a stage",
        "counts.",
        "",
        "## `cycle_break_report.json`",
        "",
        "Keys in this order: day_id, sweeps_run, sweep_budget, closing_state,",
        "settled_at_sweep, correction_count, cycle_count, cycles,",
        "frozen_reefers, state_signatures. settled_at_sweep is zero when",
        "the closing state is not settled. Each entry of cycles carries",
        "sweep, short_reefer, displaced_reefer, interval and broken, in",
        "that order. frozen_reefers is a list of reefer identifiers in",
        "ascending order. state_signatures is a list of the first sixteen",
        "characters of each state signature, the opening state first.",
        "",
        "## `peak_demand_certificate.json`",
        "",
        "Keys in this order: day_id, yard_peak_w, yard_peak_interval,",
        "substations, demand_charge_cents. Each entry of substations carries",
        "substation_id, peak_w, peak_interval, band_code and charge_cents, in",
        "that order, and the entries follow the substation order the topology",
        "prints.",
        "",
        "## `objective_vector.json`",
        "",
        "Keys in this order: day_id, lexicographic_order, hard_violations,",
        "unmet_mandatory_wh, deadline_penalty_cents, peak_demand_w,",
        "energy_cost_cents, battery_cycle_wh, tie_key. lexicographic_order is",
        "the list of the six measured component names followed by tie_key, in",
        "the order the objective is compared in.",
        "",
        "## `constraint_certificate.json`",
        "",
        "Keys in this order: day_id, feeder_intervals_over_capacity,",
        "state_of_charge_below_reserve, reefers_at_share_ceiling,",
        "unplaced_allowance_wh, reefers_refused, reefers_queued, spill_count,",
        "unspilled_count. feeder_intervals_over_capacity and",
        "state_of_charge_below_reserve are the two counts RULE P13.b adds into",
        "the hard violations. reefers_at_share_ceiling counts the queued",
        "reefers whose share after the last pass stands above zero and equals",
        "its limit under RULE P09.f. unplaced_allowance_wh is the sum of the",
        "unplaced allowances of RULE P09.l. reefers_refused counts the reefers",
        "a rung caught and reefers_queued the reefers the queue carries.",
        "spill_count counts every removal spill_decisions.tsv carries, spilled",
        "and unspilled together, and unspilled_count the unspilled ones.",
        "",
        "## `substation_report_<one substation identifier>.json`",
        "",
        "One report per substation the reporting roster publishes, named for",
        "that substation. Keys in this order: day_id, substation_id,",
        "feeder_count, feeders, ceiling_w, peak_w, peak_interval, band_code,",
        "demand_charge_cents, served_energy_wh. feeders is the list of feeder",
        "identifiers of that substation in ascending order.",
        "",
        "## `publication_manifest.json`",
        "",
        "Keys in this order: day_id, day_reference, document_count,",
        "core_digest, publication_digest, documents. document_count is the",
        "number of entries documents carries. Each entry of documents",
        "carries name, bytes and sha256 in that order.",
        "",
        "## `final_schedule_by_vessel.xml`",
        "",
        "A dispatch element carrying the day and reference attributes, then",
        "one vessel element per vessel holding at least one queued reefer, in",
        "vessel identifier order, carrying the id, cutoff and members",
        "attributes, then one reefer element per member in reefer identifier",
        "order carrying id, required_wh, served_wh, shortfall_wh and",
        "allowance_wh.",
        "",
        "## `dispatch_control_totals.conf`",
        "",
        "One comment line made of `# control totals for`, one space and the",
        "operating day identifier, then one key and value",
        "per line separated by a space, an equals sign and a space, in this",
        "order: day_id, day_reference, live_sheet, reefers_normalised,",
        "reefers_queued, reefers_refused, spill_count, hard_violations,",
        "unmet_mandatory_wh, deadline_penalty_cents, peak_demand_w,",
        "energy_cost_cents, battery_cycle_wh, unmet_share_of_mandatory.",
        "live_sheet is the name of the governing workbook sheet. The keys",
        "shared with constraint_certificate.json and objective_vector.json",
        "carry the same values. unmet_share_of_mandatory is",
        "unmet_mandatory_wh divided by the sum of the required energy RULE",
        "P11.a gives every queued reefer, written as a ratio, and zero when",
        "that sum is zero.",
        "",
        "## `daily_dispatch_summary.md`",
        "",
        "The free text summary. worked_examples.md fixes its shape.",
    ]
    write_lines(root / "output_schema_reference.md", lines)

    write_lines(root / "serialisation_and_digest_contract.md", [
        "# Serialisation and digest contract",
        "",
        "Every published document is written as utf-8 with a line feed as the",
        "line ending and no carriage return anywhere. Every document ends",
        "with exactly one line feed and carries no blank line before it.",
        "",
        "A delimited document writes its header once as the first line. A",
        "field is never quoted and never carries its own delimiter.",
        "",
        "A document with no data row is written as its header line alone.",
        "",
        "Every object document is written with an indent of two spaces, the",
        "keys in the order the output schema reference prints them, and a",
        "single line feed after the closing brace. A key is followed by a",
        "colon and one space, an item closes a line with a bare comma, and",
        "an empty object or list is written on one line as {} or [].",
        "Key order is the written order and is never sorted.",
        "",
        "Every line delimited object document writes one object per line with",
        "no space after a comma or a colon, the keys in the order the output",
        "schema reference prints them, and one line feed after the last",
        "object.",
        "",
        "An extensible markup document opens with the line",
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>, indents every nesting",
        "level below the root element by two spaces, and writes an element",
        "carrying no child as one self closing tag.",
        "",
        "A free text document writes each of its paragraphs on a single",
        "line and never wraps one. worked_examples.md wraps its own lines",
        "to the width of the page and that wrapping is no part of the",
        "shape it fixes.",
        "",
        "A whole quantity is written as a whole number. A ratio is written at",
        "exactly nine decimal places. Money is written in whole cents. Power",
        "is written in whole watts and energy in whole watt hours. Negative",
        "zero is never written.",
        "",
        "## The two digests",
        "",
        "publication_manifest.json carries a core digest and a publication",
        "digest.",
        "",
        "The core digest is the sha256, in lowercase hexadecimal, of the",
        "bytes of the six core documents concatenated in this order:",
        "normalised_reefers.jsonl, energy_floor_ledger.csv,",
        "provisional_allocation.psv, reconciliation_iterations.csv,",
        "objective_vector.json, final_schedule.csv.",
        "",
        "The publication digest is the sha256 of the bytes of every other",
        "published document concatenated in the order the documents list of",
        "the manifest prints them, with the six core documents and the",
        "manifest itself left out.",
        "",
        "The documents list carries every published document except the",
        "manifest, in this order.",
        "",
        "First the fourteen stage documents, one for each stage in stage",
        "order: normalised_reefers.jsonl, availability_lattice.csv,",
        "energy_floor_ledger.csv, dispatch_priority_queue.csv,",
        "provisional_allocation.psv, feeder_violation_ledger.csv,",
        "crane_adjusted_capacity.csv, battery_schedule.csv,",
        "reconciliation_iterations.csv, tariff_charge_ledger.csv,",
        "deadline_correction.csv, cycle_break_report.json,",
        "objective_vector.json and final_schedule.csv.",
        "",
        "Then the load family: interval_demand.csv,",
        "feeder_load_ledger.csv, spill_decisions.tsv, soc_ledger.psv and",
        "constraint_certificate.json.",
        "",
        "Then the tariff family: peak_demand_certificate.json,",
        "unmet_requirement_report.tsv, reefer_service_certificate.csv,",
        "audit_trace.jsonl and dispatch_control_totals.conf.",
        "",
        "Then the publication family: final_schedule_by_feeder.psv,",
        "final_schedule_by_vessel.xml, one substation report for each",
        "substation the reporting roster publishes in the order that",
        "roster prints them, and daily_dispatch_summary.md.",
        "",
        "Each entry carries the document name, its length in bytes and the",
        "sha256 of its bytes.",
    ])

    write_lines(root / "reeferdispatch_program_contract.md", [
        "# Program contract",
        "",
        "The delivered program answers to this contract.",
        "",
        "It accepts a --data option and an --out option, in either order,",
        "each followed by a directory path.",
        "",
        "It creates the output directory when it is absent, writes every",
        "published document there, exits zero, writes nothing else anywhere,",
        "and leaves its input directory exactly as it found it.",
        "",
        "It reads the substation capacity workbook, the dispatch operations",
        "memorandum and the priority ordering directive from the directory it",
        "is pointed at.",
        "",
        "It uses the Python standard library and nothing else.",
        "",
        "It holds nothing about this operating day inside it. Every",
        "identifier, control value, threshold, boundary and rung code is read",
        "from the directory it is pointed at.",
        "",
        "Two runs over one input directory produce identical bytes, and so",
        "does the same operating day placed under another directory name.",
        "",
        "It uses exact rational arithmetic and no binary floating point.",
        "",
        "It carries the fourteen stages as fourteen separately named steps, in",
        "the stage order terminal_contract_overview.md prints.",
    ])

    write_lines(root / "worked_examples.md", [
        "# Worked examples",
        "",
        "The figures below belong to an invented operating day and settle",
        "nothing here. Take the shape from them and no figure.",
        "",
        "## A unit conversion",
        "",
        "A nameplate quoted as 11 in megajoules per hour converts through the",
        "power entry of the unit register, which carries a numerator of 2500",
        "and a denominator of 9. Eleven times 2500 is 27500, and 27500 over 9",
        "is 3055 and 5 ninths, which rounds half up to 3056 watts. That whole",
        "number is what the stage stores, and every later stage reads the",
        "stored number rather than the fraction it came from.",
        "",
        "## A window on a boundary",
        "",
        "A reefer connecting at minute 300 and disconnecting at minute 600",
        "holds the intervals 21 through 40. The interval that opens at minute",
        "600 is interval 41 and the window does not reach it.",
        "",
        "## The shape of the summary",
        "",
        "# Ashgrove Point reefer yard dispatch summary",
        "",
        "Operating day INVENTED-DAY was recomputed from the working papers",
        "under the input directory. The governing workbook sheet was Invented.",
        "",
        "## Admission",
        "",
        "9 reefers were normalised and 7 of them reached the dispatch",
        "priority queue. 2 were set aside by the admission ladder.",
        "",
        "## Reconciliation",
        "",
        "The feeder reconciliation removed 3 placements and spilled 2 of them",
        "into a later interval. The reconciliation ran 4 passes against the",
        "pass budget.",
        "",
        "## Objective",
        "",
        "hard violations 0, unmet mandatory energy 0 watt hours, deadline",
        "penalty 0 cents, peak demand 0 watts, energy cost 0 cents, battery",
        "cycle 0 watt hours.",
        "",
        "## The shape of the control totals",
        "",
        "The first line is a comment naming the operating day. Every later",
        "line is a key, a space, an equals sign, a space and the value.",
    ])


def write_stage_specs(inst, root):
    day = inst["day_id"]

    write_lines(root / "spec_stage_p01_unit_normalisation.md", [
        "# Stage P01, unit normalisation",
        "",
        "This stage settles which rows of every register govern operating day",
        "%s and converts every quoted quantity into its base unit." % day,
        "",
        "RULE P01.a  The operating day identifier and the day reference are",
        "the day and reference attributes of substation_topology.xml. Every",
        "row of every register carrying another day identifier is set aside.",
        "",
        "RULE P01.b  A row governs only while its record state is one of the",
        "words the applicable list of revision_precedence.toml carries. A row",
        "whose record state reads superseded, withdrawn, cancelled or retired",
        "is set aside, and so is a row whose record state is a word neither",
        "list carries. The set aside test is applied before any sequence is",
        "compared, so a set aside row carrying the highest sequence of its key",
        "settles nothing.",
        "",
        "RULE P01.c  Among the rows of a key that survive P01.a and P01.b,",
        "the row carrying the highest value of that register sequence field",
        "governs. revision_precedence.toml names the sequence field of every",
        "register.",
        "",
        "RULE P01.d  The feeder of a reefer is the feeder its plug is",
        "assigned to by the governing row of plug_assignment_register.csv.",
        "The substation of a reefer is the substation the governing row of",
        "feeder_capacity_register.csv gives that feeder.",
        "",
        "RULE P01.e  The nameplate is converted to watts through the power",
        "entry of unit_register_dictionary.toml the nameplate unit names.",
        "Multiply the quoted value by the entry numerator, divide by the",
        "entry denominator, round half up and store the whole watt figure.",
        "",
        "RULE P01.f  A nameplate quoting a unit the power section does not",
        "carry stores a nameplate of zero and a unit state of unknown_unit.",
        "Every other reefer stores a unit state of converted.",
        "",
        "RULE P01.g  The declared energy of a reefer is the declared value of",
        "the governing row of energy_declaration_returns.psv converted",
        "through the energy entry its energy unit names, rounded half up to a",
        "whole watt hour.",
        "",
        "RULE P01.h  A reefer with no governing return, or whose governing",
        "return carries the not supplied marker as its declared value, stores",
        "the string not_declared. That is a return with no declared energy",
        "and it is not a declaration of zero.",
        "",
        "RULE P01.i  The applicable call of a vessel is the governing row of",
        "vessel_call_register.csv under P01.a to P01.c. A vessel whose every",
        "row for this operating day is set aside has no applicable call.",
        "",
        "## Published document",
        "",
        "normalised_reefers.jsonl, one object per reefer in reefer identifier",
        "order.",
    ])

    write_lines(root / "spec_stage_p02_availability_lattice.md", [
        "# Stage P02, the availability lattice",
        "",
        "This stage places every reefer on the interval grid.",
        "",
        "RULE P02.a  The grid carries 96 intervals of 15 minutes. Interval n",
        "covers the minutes from 15 times n minus 15 inclusive to 15 times n",
        "exclusive.",
        "",
        "RULE P02.b  A connection window runs from the connect minute",
        "inclusive to the disconnect minute exclusive. An interval belongs to",
        "a window when the two overlap in at least one minute.",
        "",
        "RULE P02.c  A disconnection landing exactly on an interval boundary",
        "closes the interval before it and does not open the interval that",
        "starts there. A connection landing exactly on an interval boundary",
        "opens that interval, so a window whose disconnect minute equals its",
        "connect minute covers no interval at all.",
        "",
        "RULE P02.d  An interval covered by a booked maintenance window",
        "against the feeder of the reefer, or against the plug of the reefer,",
        "is struck out of the lattice of that reefer. A window whose state",
        "reads cancelled strikes nothing out.",
        "",
        "RULE P02.e  The window state of a reefer reads empty when its",
        "lattice holds no interval, single_slot when it holds exactly one and",
        "open otherwise. A reefer with an empty lattice publishes a first and",
        "a last interval of zero.",
        "",
        "RULE P02.f  The interval demand of a feeder in an interval counts",
        "every reefer whose lattice holds that interval and sums their stored",
        "nameplate watts. The count is taken before the admission ladder runs.",
        "",
        "## Published documents",
        "",
        "availability_lattice.csv and interval_demand.csv.",
    ])

    write_lines(root / "spec_stage_p03_energy_floor.md", [
        "# Stage P03, the mandatory energy floor",
        "",
        "This stage settles the energy each reefer must take to hold its",
        "temperature, interval by interval.",
        "",
        "RULE P03.a  The ambient class of an interval is the ambient class the",
        "interval readings of ambient_condition_returns.json carry for this",
        "operating day.",
        "",
        "RULE P03.b  The ambient multiplier of a reefer in an interval is the",
        "multiplier the multiplier table carries for the pairing of the",
        "temperature class of the reefer and the ambient class of the",
        "interval.",
        "",
        "RULE P03.c  A pairing the multiplier table carries no row for falls",
        "back to the class default multiplier the same paper carries. An",
        "absent pairing is a fallback to that default and it is not a",
        "multiplier of zero.",
        "",
        "RULE P03.d  The maintenance coefficient of a temperature class is",
        "the numerator and denominator the governing sheet of",
        "substation_capacity_workbook.xlsx carries for that class.",
        "",
        "RULE P03.e  The floor of a reefer in an interval is its stored",
        "nameplate watts, taken over a quarter of an hour, multiplied by the",
        "ambient multiplier and by the maintenance coefficient, rounded half",
        "up and stored as a whole watt hour. The rounding happens once per",
        "interval and the stored whole numbers are what the mandatory floor",
        "sums.",
        "",
        "RULE P03.f  The mandatory floor of a reefer is the sum of its stored",
        "interval floors over its lattice.",
        "",
        "RULE P03.g  The requested energy of a reefer is its declared energy",
        "when a return declared one, and its mandatory floor otherwise. The",
        "floor state reads declared in the first case and defaulted in the",
        "second.",
        "",
        "RULE P03.h  The discretionary energy of a reefer is its requested",
        "energy less its mandatory floor, and never below zero.",
        "",
        "RULE P03.i  The draw of a reefer in an interval is its stored",
        "nameplate watts multiplied by the ambient multiplier and by the",
        "maintenance coefficient, rounded half up and stored as a whole watt.",
        "The interval floor and the interval draw are two roundings of the",
        "same quantity, taken over a quarter of an hour and over the hour, so",
        "the draw is rarely four times the floor and neither is derived from",
        "the other.",
        "",
        "## Published document",
        "",
        "energy_floor_ledger.csv.",
    ])

    write_lines(root / "spec_stage_p04_priority_queue.md", [
        "# Stage P04, the admission ladder and the dispatch priority queue",
        "",
        "This stage sets aside the reefers the yard cannot serve and orders",
        "the rest.",
        "",
        "RULE P04.a  The ladder is read in the order",
        "dispatch_admission_ladder.txt prints its rungs. The first rung that",
        "catches a reefer settles it and no lower rung is consulted for that",
        "reefer. The printed order is not the alphabetical order of the rung",
        "codes.",
        "",
        "RULE P04.b  DR_UNKNOWN_PLUG catches a reefer whose plug has no",
        "governing row in plug_assignment_register.csv, and a reefer whose",
        "governing plug row carries a plug state other than live.",
        "",
        "RULE P04.c  DR_FEEDER_OUT_OF_FORCE catches a reefer whose feeder is",
        "absent from substation_topology.xml. A feeder carrying a capacity",
        "row is out of force when the topology omits it.",
        "",
        "RULE P04.d  DR_WINDOW_EMPTY catches a reefer whose lattice holds no",
        "interval.",
        "",
        "RULE P04.e  DR_UNKNOWN_POWER_UNIT catches a reefer whose unit state",
        "reads unknown_unit.",
        "",
        "RULE P04.f  DR_PLUG_ZONE_REFUSED catches a reefer whose plug zone",
        "and temperature class pairing carries the admission refused in the",
        "governing rows of plug_zone_admission_matrix.csv, unless a zone",
        "waiver notice of this operating day names that reefer.",
        "",
        "RULE P04.g  DR_DUPLICATE_CONNECTION is settled among the reefers the",
        "five rungs above left standing. The cluster key is the plug",
        "identifier. The canonical member of a cluster is the lowest reefer",
        "identifier among those standing reefers, and every other standing",
        "member of the cluster is caught. A cluster member an earlier rung",
        "already caught is not a candidate to be canonical.",
        "",
        "RULE P04.h  The deadline slack of a queued reefer is the cutoff",
        "interval of its applicable call less the last interval of its",
        "lattice. A reefer whose vessel has no applicable call takes the",
        "absent call slack sentinel priority_precedence_policy.toml names,",
        "an urgency rank of 9, a service group of sg_none and a cutoff",
        "interval of 96.",
        "",
        "RULE P04.i  The queue is ordered on the four keys the priority",
        "ordering directive prints, in the key positions it prints them,",
        "every key ascending. The class rank of a temperature class is the",
        "rank the same directive prints.",
        "",
        "RULE P04.j  A queued reefer publishes its rank from 1 upward and a",
        "queue state of queued. A reefer a rung caught publishes a rank of",
        "zero, zero on every key and the rung code as its queue state.",
        "",
        "## Published document",
        "",
        "dispatch_priority_queue.csv.",
    ])

    write_lines(root / "spec_stage_p05_provisional_allocation.md", [
        "# Stage P05, the provisional allocation",
        "",
        "This stage places the queue against the nominal capacity of the",
        "feeders, interval by interval. It is a local settlement and later",
        "stages unpick part of it.",
        "",
        "RULE P05.a  The nominal capacity of a feeder in an interval is the",
        "nominal capacity watts of its governing capacity row.",
        "",
        "RULE P05.b  An interval covered by a booked maintenance window",
        "against the feeder carries a nominal capacity of zero.",
        "",
        "RULE P05.c  The governing derating notice of a feeder is its",
        "applicable notice carrying the highest notice sequence. Over the",
        "intervals from its first interval to its last interval inclusive the",
        "nominal capacity is multiplied by the derate permille, divided by a",
        "thousand and floored. Outside that span the notice does nothing.",
        "",
        "RULE P05.d  The draw of a reefer in an interval is the whole watt",
        "figure stage P03 stored for it under P03.i.",
        "",
        "RULE P05.e  Within an interval the queue is walked in rank order.",
        "A reefer is powered when the running load of its feeder plus its own",
        "draw is at or below the nominal capacity, and held otherwise. A load",
        "equal to the capacity is lawful. Only a load above the capacity is a",
        "violation.",
        "",
        "RULE P05.f  A reefer held in an interval is not reconsidered in that",
        "interval. The standing reserve is not withheld at this stage.",
        "",
        "## Published document",
        "",
        "provisional_allocation.psv, one row per reefer and interval of its",
        "lattice.",
    ])

    write_lines(root / "spec_stage_p06_feeder_reconciliation.md", [
        "# Stage P06, the feeder reconciliation and the spill",
        "",
        "This stage withholds the standing reserve and unpicks the placements",
        "the reserve no longer admits.",
        "",
        "RULE P06.a  The reserved capacity of a feeder in an interval is its",
        "nominal capacity for that interval less its standing reserve watts,",
        "and never below zero. The reserve is withheld before any free",
        "capacity is counted.",
        "",
        "RULE P06.b  The intervals are worked in ascending order. Within an",
        "interval, while the load of a feeder stands above its reserved",
        "capacity, the powered reefer of that feeder carrying the highest",
        "rank is removed.",
        "",
        "RULE P06.c  A removed placement spills to the next eligible",
        "interval: the lowest interval of the lattice of that reefer that is",
        "above the interval it was removed from, that the reefer does not",
        "already hold, and where the load of the feeder plus the draw of that",
        "interval stands at or below the reserved capacity. It does not move",
        "to the cheapest interval of the day.",
        "",
        "RULE P06.d  A removed placement that finds no such interval",
        "publishes a target interval of zero and a spill state of unspilled.",
        "Every other removal publishes its target interval and a spill state",
        "of spilled.",
        "",
        "RULE P06.e  A violation row is published for every feeder and",
        "interval where a removal happened, carrying the load standing before",
        "the removals, the reserved capacity, the excess and the number of",
        "removals.",
        "",
        "RULE P06.f  The load state of a feeder and interval reads",
        "over_capacity above the capacity it is taken against, at_capacity",
        "at it and clear below it. The load ledger of this stage takes it",
        "against the reserved capacity, and the removals of RULE P06.d",
        "leave no feeder and interval of that ledger above its reserved",
        "capacity, so only the lower two readings appear there.",
        "",
        "## Published documents",
        "",
        "feeder_load_ledger.csv, feeder_violation_ledger.csv and",
        "spill_decisions.tsv.",
    ])

    write_lines(root / "spec_stage_p07_crane_interaction.md", [
        "# Stage P07, the crane adjusted capacity",
        "",
        "This stage merges the crane records into the feeder capacity. A",
        "crane changes the capacity available to reefers. It is not an extra",
        "load added to the reefer load.",
        "",
        "RULE P07.a  A crane duty of this operating day counts when the",
        "confirmation carrying the lowest confirm sequence for that crane and",
        "interval reads landed. A duty whose lowest confirmation reads",
        "cancelled draws nothing, and so does a duty with no confirmation at",
        "all.",
        "",
        "RULE P07.b  A crane covered by a booked maintenance window in an",
        "interval draws nothing in that interval.",
        "",
        "RULE P07.c  The crane draw of a feeder in an interval is the sum of",
        "the demand of its counting duties, converted from kilowatts to watts",
        "through the demand entry of the unit register.",
        "",
        "RULE P07.d  The adjusted capacity of a feeder in an interval is its",
        "reserved capacity less its crane draw. A difference below zero is",
        "clamped to zero and publishes a clamp state of clamped. Every other",
        "interval publishes a clamp state of clear.",
        "",
        "## Published document",
        "",
        "crane_adjusted_capacity.csv.",
    ])

    write_lines(root / "spec_stage_p08_battery_intervention.md", [
        "# Stage P08, the battery intervention",
        "",
        "This stage works the yard battery against the reconciled load, one",
        "interval at a time, carrying the state of charge forward.",
        "",
        "RULE P08.a  The battery serves the substation its operating policy",
        "names. Its deficit in an interval is the sum, over the feeders of",
        "that substation, of the reconciled load less the adjusted capacity,",
        "counting only the feeders where that difference is above zero. The",
        "published deficit is that watt figure divided by four and floored.",
        "",
        "RULE P08.b  The battery is available in an interval when the",
        "telemetry of this operating day reads online for it and no booked",
        "maintenance window against the battery covers it. An unavailable",
        "interval publishes an action of offline and moves nothing.",
        "",
        "RULE P08.c  In an available interval carrying a deficit the battery",
        "discharges. The discharge is the least of the deficit watt hours,",
        "the maximum discharge watts divided by four and floored, and the",
        "state of charge above the reserve multiplied by the discharge",
        "efficiency permille and divided by a thousand and floored.",
        "",
        "RULE P08.d  A state of charge sitting exactly on the reserve is",
        "lawful. Nothing may be drawn from it there, so the discharge is zero",
        "and the limit reason reads state_of_charge_on_reserve.",
        "",
        "RULE P08.e  A discharge of e watt hours lowers the state of charge",
        "by e multiplied by a thousand, divided by the discharge efficiency",
        "permille, taken to the ceiling.",
        "",
        "RULE P08.f  In an available interval carrying no deficit whose",
        "tariff band is one of the charge eligible bands the battery charges.",
        "The charge is the least of the maximum charge watts divided by four",
        "and floored, the substation headroom watts divided by four and",
        "floored, and the room left under the capacity. A charge of c watt",
        "hours raises the state of charge by c multiplied by the charge",
        "efficiency permille, divided by a thousand and floored.",
        "",
        "RULE P08.g  An available interval carrying no deficit whose tariff",
        "band is not a charge eligible band publishes an action of idle and a",
        "limit reason of band_ineligible.",
        "",
        "RULE P08.h  The discharge of an interval supports the feeders of the",
        "substation in ascending feeder identifier order, each taking what",
        "its own deficit needs until the discharge is spent.",
        "",
        "RULE P08.i  Every schedule row publishes a limit reason. An",
        "offline interval reads none and an idle interval reads",
        "band_ineligible. A discharging interval reads",
        "state_of_charge_on_reserve when its discharge is zero,",
        "discharge_limit when its discharge equals the maximum discharge",
        "watts divided by four and floored, state_of_charge_limit when its",
        "discharge equals what the state of charge above the reserve",
        "allows, and deficit_met otherwise, the three tested in that",
        "order. A charging interval reads no_room when its charge is zero,",
        "capacity_limit when its charge equals the room left under the",
        "capacity, charge_limit when its charge equals the maximum charge",
        "watts divided by four and floored, and headroom_limit otherwise,",
        "the three tested in that order.",
        "",
        "RULE P08.j  The state of charge state reads at_reserve when the",
        "closing charge equals the reserve, below_reserve under it and",
        "above_reserve over it. A closing charge under the reserve is a hard",
        "violation stage P13 counts.",
        "",
        "## Published documents",
        "",
        "battery_schedule.csv and soc_ledger.psv.",
    ])

    write_lines(root / "spec_stage_p09_load_reconciliation.md", [
        "# Stage P09, the load reconciliation passes",
        "",
        "This stage settles how much discretionary energy each reefer is",
        "allowed out of the day headroom of its feeder, and then places that",
        "allowance into intervals.",
        "",
        "RULE P09.a  The headroom of a feeder in an interval is its adjusted",
        "capacity plus its battery support less its reconciled load, and",
        "never below zero. The day pool of a feeder is the sum of its",
        "interval headroom watts divided by four and floored.",
        "",
        "RULE P09.b  The members of a feeder are its queued reefers carrying",
        "a discretionary energy above zero. A pass settles every member of a",
        "feeder together, so their order within the pass settles nothing.",
        "",
        "RULE P09.c  Every share opens at zero. The reconciliation runs the",
        "number of passes the pass budget of dispatch_operations_memo.pdf",
        "names. The budget is spent whether or not the shares have settled.",
        "It is not a guard on a convergence loop.",
        "",
        "RULE P09.d  Within a pass the need of a member is its discretionary",
        "energy less its standing share, never below zero. The unallocated",
        "pool is the day pool less the sum of the standing shares.",
        "",
        "RULE P09.e  When the unallocated pool and the total need both stand",
        "above zero, the target of a member is its standing share plus the",
        "unallocated pool multiplied by its own need and divided by the total",
        "need. Otherwise the target is the standing share.",
        "",
        "RULE P09.f  The limit of a member is the lesser of its discretionary",
        "energy and the share ceiling the governing workbook sheet carries",
        "for its vessel. A target above the limit is cut to the limit and the",
        "difference is freed.",
        "",
        "RULE P09.g  What a limit frees is redistributed inside the cross",
        "classification of substation and service group, among the members of",
        "that cell whose target stands below their own limit, in proportion",
        "to the room each has left. It is not spread across the whole feeder.",
        "",
        "RULE P09.h  The share is then damped: the closing share is the",
        "standing share plus the damping fraction of the difference between",
        "the target and the standing share. The damping fraction is the",
        "numerator and denominator the governing workbook sheet carries.",
        "",
        "RULE P09.i  A pass that would move a share by less than the minimum",
        "step of dispatch_operations_memo.pdf moves it by the minimum step",
        "instead, in the direction it was moving.",
        "",
        "RULE P09.j  The pass closes by rounding the share half up to a whole",
        "watt hour and holding it between zero and the limit. The pass after",
        "it opens from that rounded share.",
        "",
        "RULE P09.k  A pass row publishes a pass state of moving when its",
        "closing share differs from its opening share and settled otherwise.",
        "",
        "RULE P09.l  The allowance of a reefer is placed after the last pass.",
        "The queue is walked in rank order and each reefer fills its share",
        "from the earliest interval of its lattice onward, taking from each",
        "interval no more than the headroom watt hours left there. What no",
        "interval could take is the unplaced allowance.",
        "",
        "RULE P09.m  The final load of a feeder in an interval is its",
        "reconciled load plus four times the allowance placed there.",
        "",
        "## Published document",
        "",
        "reconciliation_iterations.csv, one row per pass, feeder and member.",
    ])

    write_lines(root / "spec_stage_p10_tariff_and_demand.md", [
        "# Stage P10, the tariff and the demand charge",
        "",
        "RULE P10.a  The price of an interval is the price of its governing",
        "row of tariff_interval_schedule.csv, quoted in tenths of a cent for",
        "each kilowatt hour.",
        "",
        "RULE P10.b  The energy of an interval is its final yard load watts",
        "divided by four and rounded half up to a whole watt hour. That",
        "stored whole number is what the charge is computed from.",
        "",
        "RULE P10.c  The charge of an interval is its stored energy watt",
        "hours multiplied by its price and divided by ten thousand, rounded",
        "half up to a whole cent. The rounding happens once per interval.",
        "",
        "RULE P10.d  The peak of a substation is the highest final load its",
        "feeders carry together in any one interval. A tie is settled by the",
        "earlier interval.",
        "",
        "RULE P10.e  The demand charge band of a substation is the governing",
        "band row of demand_charge_bands.tsv for that substation whose floor",
        "stands at or below the peak and whose ceiling stands above it. A",
        "peak equal to the floor of a band belongs to that band.",
        "",
        "RULE P10.f  The demand charge is the sum of the band charges of the",
        "substations. The yard peak is the highest final yard load in any one",
        "interval, with a tie settled by the earlier interval.",
        "",
        "## Published documents",
        "",
        "tariff_charge_ledger.csv and peak_demand_certificate.json.",
    ])

    write_lines(root / "spec_stage_p11_deadline_correction.md", [
        "# Stage P11, the deadline correction",
        "",
        "This stage tries to serve the reefers the reconciliation left short",
        "of their mandatory floor at the vessel cutoff.",
        "",
        "RULE P11.a  The required energy of a reefer is the sum of its stored",
        "interval floors over the intervals of its lattice at or below its",
        "cutoff interval. What it was served is the same sum restricted to",
        "the intervals it is powered in. The shortfall is the difference,",
        "never below zero. The shortfall intervals are the intervals of its",
        "lattice at or below its cutoff it is not powered in.",
        "",
        "RULE P11.b  The allowance an earlier stage placed is discretionary",
        "energy and it does not count toward the mandatory floor.",
        "",
        "RULE P11.c  The correction is worked as a sequence of sweeps. In a",
        "sweep the reefers standing short are taken with the vessel critical",
        "ones first and the rest after, each group in rank order. A reefer is",
        "vessel critical when a priority override notice of this operating",
        "day names it. A vessel critical reefer overturns an ordinary queue",
        "position.",
        "",
        "RULE P11.d  A short reefer looks at the intervals of its lattice at",
        "or below its cutoff that it is not powered in, in ascending order,",
        "and takes the first one that admits a displacement. It takes at most",
        "one displacement per sweep.",
        "",
        "RULE P11.e  A candidate to be displaced is a reefer powered on the",
        "same feeder in that interval, that is neither vessel critical nor",
        "frozen, and that holds more powered intervals at or below its own",
        "cutoff than the dependency protection depth of",
        "dispatch_operations_memo.pdf. The candidate carrying the highest",
        "rank is displaced.",
        "",
        "RULE P11.f  A displacement that raises the load of the feeder is",
        "admitted only when the raised load stands at or below the adjusted",
        "capacity plus the battery support of that interval. A displacement",
        "that does not raise the load is always admitted.",
        "",
        "RULE P11.g  An interval offering no candidate publishes a correction",
        "state of refused_protected. An interval whose candidate would raise",
        "the load beyond what P11.f admits publishes refused_no_headroom. A",
        "displacement that is applied publishes corrected.",
        "",
        "## Published document",
        "",
        "deadline_correction.csv.",
    ])

    write_lines(root / "spec_stage_p12_cycle_break.md", [
        "# Stage P12, the cycle detection and the break",
        "",
        "RULE P12.a  A displacement is the triple of the short reefer, the",
        "reefer it displaced and the interval it happened in. Every",
        "displacement a sweep applies is remembered.",
        "",
        "RULE P12.b  The state of a sweep is the set of reefer and interval",
        "pairs standing powered at the close of that sweep. Its signature is",
        "the sha256 of those pairs written as the reefer identifier, an at",
        "sign and the interval, joined by semicolons in ascending order. The",
        "opening state is recorded before the first sweep and the closing",
        "state of every sweep after it.",
        "",
        "RULE P12.c  The sweep budget is the dependency protection depth of",
        "dispatch_operations_memo.pdf plus two.",
        "",
        "RULE P12.d  A sweep that applies no displacement closes the",
        "correction. The closing state reads settled.",
        "",
        "RULE P12.e  A displacement whose reverse triple was applied in an",
        "earlier sweep is a cycle. Every cycle of a sweep is recorded, in",
        "ascending order of the short reefer, the displaced reefer and the",
        "interval.",
        "",
        "RULE P12.f  The cycle of a sweep carrying the lowest incremental",
        "penalty is the one that is broken, and it publishes a broken flag of",
        "true while every other cycle of that sweep publishes false. The",
        "penalty of a cycle is the draw of the displaced reefer in that",
        "interval, then the interval, then the displaced identifier, then the",
        "short identifier, compared in that order.",
        "",
        "RULE P12.g  Breaking a cycle freezes both of its reefers. A frozen",
        "reefer is neither corrected nor displaced again. The sweeps carry on",
        "after the break.",
        "",
        "RULE P12.h  Sweeps that run the budget out without a sweep applying",
        "nothing close with a closing state of budget_spent.",
        "",
        "## Published document",
        "",
        "cycle_break_report.json, whose keys are day_id, sweeps_run,",
        "sweep_budget, closing_state, settled_at_sweep, correction_count,",
        "cycle_count, cycles, frozen_reefers and state_signatures, in that",
        "order. settled_at_sweep is zero when the closing state is not",
        "settled. Each entry of cycles carries sweep, short_reefer,",
        "displaced_reefer, interval and broken, in that order.",
    ])

    write_lines(root / "spec_stage_p13_objective.md", [
        "# Stage P13, the objective reconciliation",
        "",
        "RULE P13.a  The objective is a lexicographic vector compared in this",
        "order: hard violations, unmet mandatory energy, deadline penalty,",
        "peak demand, energy cost, battery cycle, then the tie key. A",
        "schedule with a lower energy cost still loses when an earlier",
        "component is worse.",
        "",
        "RULE P13.b  A hard violation is a feeder and interval whose final",
        "load stands above its adjusted capacity plus its battery support,",
        "and every interval whose closing state of charge stands below the",
        "reserve. The hard violation component is the count of both together.",
        "",
        "RULE P13.c  The unmet mandatory energy is the sum of the shortfalls",
        "of every queued reefer at the close of the correction.",
        "",
        "RULE P13.d  The deadline penalty of a reefer standing short is the",
        "surcharge of the highest rung of the ladder in",
        "dispatch_operations_memo.pdf whose interval figure stands at or",
        "below its shortfall intervals.",
        "",
        "RULE P13.e  The energy cost is the sum of the interval charges, the",
        "demand charge and the base service charge the governing workbook",
        "sheet carries.",
        "",
        "RULE P13.f  The battery cycle is the sum of every discharge and",
        "every charge in watt hours.",
        "",
        "RULE P13.g  The tie key is the first sixteen characters of the",
        "sha256 of the reefer identifiers standing powered anywhere, taken",
        "once each in ascending order and joined by semicolons.",
        "",
        "## Published documents",
        "",
        "objective_vector.json and constraint_certificate.json.",
    ])

    write_lines(root / "spec_stage_p14_publication.md", [
        "# Stage P14, the publication",
        "",
        "RULE P14.a  Every document named by output_schema_reference.md is",
        "written, with the header, the column order, the key order and the",
        "row order that paper prints, under the serialisation contract.",
        "",
        "RULE P14.b  A reefer is powered in an interval when the correction",
        "left it powered there. Its base draw is the draw of that interval",
        "and zero otherwise. Its allowance is what stage P09 placed there.",
        "",
        "RULE P14.c  The schedule state reads powered_with_allowance when the",
        "base draw and the allowance both stand above zero, powered when only",
        "the base draw does, allowance_only when only the allowance does and",
        "held when neither does.",
        "",
        "RULE P14.d  The energy of a schedule row is its base draw divided by",
        "four and rounded half up, plus its allowance watt hours.",
        "",
        "RULE P14.e  A substation report is published for every substation",
        "the reporting roster carries. Its served energy is the sum, over its",
        "feeders and intervals, of the final load divided by four and rounded",
        "half up.",
        "",
        "RULE P14.f  The unmet requirement report carries a row for every",
        "queued reefer standing at a shortfall above zero or an unplaced",
        "allowance above zero.",
        "",
        "RULE P14.g  The publication manifest is written last and carries the",
        "two digests the serialisation contract defines.",
        "",
        "RULE P14.h  The feeder state of the schedule by feeder reads under",
        "the three readings of RULE P06.f, taken against the adjusted",
        "capacity of that feeder and interval plus its battery support in",
        "place of the reserved capacity.",
        "",
        "RULE P14.i  The measure of a stage in the audit trace is the count",
        "of data rows the stage document of that stage carries, the stage",
        "documents being the fourteen the serialisation contract lists",
        "first, one for each stage in stage order. Five stages publish a",
        "quantity in place of a count: stage p08 publishes the watt hours",
        "the battery cycled over the day, stage p10 the energy charge of",
        "the day in cents, stage p12 the number of sweeps that ran, stage",
        "p13 the unmet mandatory watt hours and stage p14 the number of",
        "documents the publication carries.",
        "",
        "## Published documents",
        "",
        "Every remaining document of the publication.",
    ])


# --------------------------------------------------------------------------
# the corpus entry point
# --------------------------------------------------------------------------


def mint_corpus(seed, profile, root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    inst = mint_instance(seed, profile)
    write_grid_papers(inst, root)
    write_network_papers(inst, root)
    write_reefer_papers(inst, root)
    write_vessel_papers(inst, root)
    write_crane_papers(inst, root)
    write_maintenance_papers(inst, root)
    write_tariff_papers(inst, root)
    write_battery_papers(inst, root)
    write_ambient_papers(inst, root)
    write_policy_papers(inst, root)
    write_ladder_paper(inst, root)
    write_audit_db(inst, root)
    write_workbook(inst, root)
    write_memo(inst, root)
    write_directive(inst, root)
    write_guidance_papers(inst, root)
    write_contract_papers(inst, root)
    write_stage_specs(inst, root)
    if inst["cfg"]["band_floor_on_peak"]:
        _align_band_floor_to_peak(inst, root)
    _prune_sentinel_note(root)
    return inst


def _prune_sentinel_note(root):
    """Drop from corpus_sentinel_note.txt the outcomes this operating day does
    reach, so the note is true of the day it ships with.

    The blocks are removed from the text that was already written rather than
    the note being rebuilt, so a day that reaches none of them leaves the file
    byte for byte as it was.
    """
    note = Path(root) / "corpus_sentinel_note.txt"
    probe = Path(tempfile.mkdtemp()) / "sentinel"
    reached = _outcomes_reached(run_pipeline(root, probe), probe)
    shutil.rmtree(probe.parent, ignore_errors=True)
    if not reached:
        return
    text = note.read_text(encoding="utf-8")
    blocks = text.split("\n\n")
    kept = []
    for block in blocks:
        head = block.strip().split(" ")[0] if block.strip() else ""
        if head in reached:
            continue
        kept.append(block)
    note.write_text("\n\n".join(kept), encoding="utf-8", newline="\n")


def _align_band_floor_to_peak(inst, root):
    """Make one substation peak land exactly on the floor of its demand charge
    band, the case RULE P10.e of spec_stage_p10_tariff_and_demand.md settles by
    placing the peak in that band.

    The peak follows from the final load and the band table has no influence on
    it, so one probe pass is enough to learn the peak and then shift the band
    boundary onto it. The bands stay contiguous: the floor moves down onto the
    peak and the ceiling of the band below it moves to the same value.
    """
    probe = Path(tempfile.mkdtemp()) / "probe"
    data = run_pipeline(root, probe)
    chosen = None
    for entry in data["peak_certificate"]["substations"]:
        if entry["peak_w"] > 0:
            chosen = entry
            break
    if chosen is None:
        raise RuntimeError("no substation carries a peak to align a band floor to")
    station = chosen["substation_id"]
    peak = chosen["peak_w"]

    rows = read_delim(root / "demand_charge_bands.tsv", "\t")
    mine = [r for r in rows
            if r["substation_id"] == station and r["day_id"] == inst["day_id"]
            and r["record_state"] in APPLICABLE_STATES]
    mine.sort(key=lambda r: as_int(r["floor_w"]))
    holder = None
    for i, r in enumerate(mine):
        if as_int(r["floor_w"]) <= peak < as_int(r["ceiling_w"]):
            holder = i
            break
    if holder is None:
        raise RuntimeError("the peak of %s falls in no band" % station)
    # band 0 keeps its floor of zero, so bring the band above it down instead.
    j = holder if holder >= 1 else 1
    if j >= len(mine):
        raise RuntimeError("no band boundary available to align")
    mine[j]["floor_w"] = str(peak)
    mine[j - 1]["ceiling_w"] = str(peak)

    write_rows(root / "demand_charge_bands.tsv",
               ["day_id", "revision_seq", "substation_id", "band_code",
                "floor_w", "ceiling_w", "charge_cents", "record_state"],
               [[r["day_id"], r["revision_seq"], r["substation_id"],
                 r["band_code"], r["floor_w"], r["ceiling_w"],
                 r["charge_cents"], r["record_state"]] for r in rows], "\t")
    shutil.rmtree(probe.parent, ignore_errors=True)


# --------------------------------------------------------------------------
# readers
# --------------------------------------------------------------------------

APPLICABLE_STATES = {"current", "filed", "booked", "landed"}
SET_ASIDE_STATES = {"superseded", "withdrawn", "cancelled", "retired"}


def read_delim(path, sep):
    text = Path(path).read_text(encoding="utf-8")
    lines = [ln for ln in text.split("\n") if ln != ""]
    if not lines:
        return []
    header = lines[0].split(sep)
    out = []
    for ln in lines[1:]:
        parts = ln.split(sep)
        while len(parts) < len(header):
            parts.append("")
        out.append(dict(zip(header, parts)))
    return out


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    out = []
    for ln in Path(path).read_text(encoding="utf-8").split("\n"):
        if ln.strip():
            out.append(json.loads(ln))
    return out


def read_toml(path):
    """A small reader for the flat declarative papers. Only the shapes those
    papers use are handled: sections, scalars, lists and inline tables."""
    data = {}
    section = data
    for raw in Path(path).read_text(encoding="utf-8").split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = data.setdefault(line[1:-1], {})
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        section[key] = _toml_value(value)
    return data


def _toml_value(value):
    if value.startswith("{") and value.endswith("}"):
        inner = {}
        for part in value[1:-1].split(","):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            inner[k.strip()] = _toml_value(v.strip())
        return inner
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if not body:
            return []
        return [_toml_value(p.strip()) for p in body.split(",")]
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    if value in ("true", "false"):
        return value == "true"
    try:
        return int(value)
    except ValueError:
        return value


_XL_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_W_MAIN = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_xlsx(path):
    """Return an ordered list of (sheet name, rows) read out of the package."""
    sheets = []
    with zipfile.ZipFile(str(path)) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst.findall(_XL_MAIN + "si"):
                text = ""
                for t in si.iter(_XL_MAIN + "t"):
                    text += t.text or ""
                shared.append(text)
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target = {}
        for rel in rels:
            target[rel.get("Id")] = rel.get("Target")
        rid_key = ("{http://schemas.openxmlformats.org/officeDocument/2006/"
                   "relationships}id")
        for sheet in wb.find(_XL_MAIN + "sheets"):
            name = sheet.get("name")
            part = target.get(sheet.get(rid_key), "")
            if not part.startswith("xl/"):
                part = "xl/" + part
            rows = []
            ws = ET.fromstring(zf.read(part))
            for row in ws.iter(_XL_MAIN + "row"):
                cells = []
                for c in row.findall(_XL_MAIN + "c"):
                    v = c.find(_XL_MAIN + "v")
                    raw = v.text if v is not None else ""
                    if c.get("t") == "s" and raw != "":
                        raw = shared[int(raw)]
                    cells.append(raw or "")
                rows.append(cells)
            sheets.append((name, rows))
    return sheets


def read_docx(path):
    """Return the paragraphs and tables of the directive in document order."""
    blocks = []
    with zipfile.ZipFile(str(path)) as zf:
        doc = ET.fromstring(zf.read("word/document.xml"))
    body = doc.find(_W_MAIN + "body")
    for node in body:
        if node.tag == _W_MAIN + "p":
            text = ""
            for t in node.iter(_W_MAIN + "t"):
                text += t.text or ""
            blocks.append(("p", text))
        elif node.tag == _W_MAIN + "tbl":
            rows = []
            for tr in node.findall(_W_MAIN + "tr"):
                cells = []
                for tc in tr.findall(_W_MAIN + "tc"):
                    text = ""
                    for t in tc.iter(_W_MAIN + "t"):
                        text += t.text or ""
                    cells.append(text)
                rows.append(cells)
            blocks.append(("table", rows))
    return blocks


# The two content stream markers are assembled rather than written as byte
# literals, so this module carries no opaque constant.
_NEWLINE = chr(10)
_STREAM_OPEN = ("stream" + _NEWLINE).encode("ascii")
_STREAM_CLOSE = (_NEWLINE + "end" + "stream").encode("ascii")


def read_pdf_lines(path):
    """Pull the text lines back out of the memorandum content streams."""
    raw = Path(path).read_bytes()
    out = []
    pos = 0
    while True:
        start = raw.find(_STREAM_OPEN, pos)
        if start < 0:
            break
        end = raw.find(_STREAM_CLOSE, start)
        if end < 0:
            break
        body = raw[start + len(_STREAM_OPEN):end].decode("latin-1", "replace")
        pos = end + 1
        for piece in body.split("\n"):
            piece = piece.strip()
            if not piece.endswith("Tj T*") and not piece.endswith("Tj"):
                continue
            if not piece.startswith("("):
                continue
            text = piece[1:piece.rfind(") Tj")] if ") Tj" in piece else ""
            text = text.replace("\\(", "(").replace("\\)", ")")
            text = text.replace("\\\\", "\\")
            out.append(text)
    return out


# --------------------------------------------------------------------------
# small arithmetic helpers
# --------------------------------------------------------------------------


def as_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def is_absent(value):
    return value is None or str(value).strip() in ("", "-")


def round_half_up(value):
    """Exact half up rounding of a Fraction, away from zero on a tie."""
    if not isinstance(value, Fraction):
        value = Fraction(value)
    if value >= 0:
        return int((value * 2 + 1) // 2)
    return -int(((-value) * 2 + 1) // 2)


def floor_div(value):
    if not isinstance(value, Fraction):
        value = Fraction(value)
    return int(value // 1)


def ceil_div(value):
    if not isinstance(value, Fraction):
        value = Fraction(value)
    return -int((-value) // 1)


def ratio_text(num, den):
    """Nine decimal places, half up, with no negative zero published."""
    if den == 0:
        return "0.000000000"
    scaled = round_half_up(Fraction(num * 1000000000, den))
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    whole, frac = divmod(scaled, 1000000000)
    if whole == 0 and frac == 0:
        sign = ""
    return "%s%d.%09d" % (sign, whole, frac)


# --------------------------------------------------------------------------
# loading the operating day
# --------------------------------------------------------------------------


def load_day(data_dir):
    d = Path(data_dir)
    data = {"root": d}
    topology = ET.fromstring(d.joinpath("substation_topology.xml").read_text(
        encoding="utf-8"))
    data["day_id"] = topology.get("day")
    data["day_reference"] = topology.get("reference")
    data["topology"] = topology
    data["grid_rows"] = read_delim(d / "interval_grid_calendar.csv", ",")
    data["zone_rows"] = read_delim(d / "plug_zone_admission_matrix.csv", ",")
    data["feeder_rows"] = read_delim(d / "feeder_capacity_register.csv", ",")
    data["plug_rows"] = read_delim(d / "plug_assignment_register.csv", ",")
    data["derate_rows"] = read_delim(d / "feeder_derating_notices.csv", ",")
    data["reefer_rows"] = read_delim(d / "reefer_service_register.csv", ",")
    data["energy_rows"] = read_delim(d / "energy_declaration_returns.psv", "|")
    data["call_rows"] = read_delim(d / "vessel_call_register.csv", ",")
    data["maintenance_rows"] = read_delim(d / "maintenance_window_register.csv", ",")
    data["tariff_rows"] = read_delim(d / "tariff_interval_schedule.csv", ",")
    data["band_rows"] = read_delim(d / "demand_charge_bands.tsv", "\t")
    data["telemetry_rows"] = read_delim(d / "battery_telemetry_returns.csv", ",")
    data["source_rows"] = read_delim(d / "source_priority_register.csv", ",")
    data["duty_rows"] = read_jsonl(d / "crane_duty_feed.ndjson")
    data["confirm_rows"] = read_jsonl(d / "crane_confirmation_journal.jsonl")
    data["notices"] = read_jsonl(d / "exception_notices.jsonl")
    data["ambient"] = read_json(d / "ambient_condition_returns.json")
    data["units"] = read_toml(d / "unit_register_dictionary.toml")
    data["battery_policy"] = read_toml(d / "battery_operating_policy.toml")
    data["precedence"] = read_toml(d / "priority_precedence_policy.toml")
    data["ladder"] = read_ladder(d / "dispatch_admission_ladder.txt")
    data["roster"] = read_roster(d / "reporting_feeder_roster.conf")
    data["workbook"] = read_xlsx(d / "substation_capacity_workbook.xlsx")
    data["memo"] = read_pdf_lines(d / "dispatch_operations_memo.pdf")
    data["directive"] = read_docx(d / "priority_ordering_directive.docx")
    return data


def read_roster(path):
    """The substations the reporting roster publishes, in the order it prints
    them. RULE P14.e and the serialisation contract both name this paper as
    the authority for which reports are published and in what order, so it is
    read rather than assumed."""
    out = []
    current = None
    for line in Path(path).read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
        elif current is not None and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() == "published":
                if value.strip() == "yes" and current not in out:
                    out.append(current)
                current = None
    return out


def read_ladder(path):
    """The rung codes in the order the ladder prints them."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").split("\n"):
        stripped = line.strip()
        if stripped.startswith("rung ") and " DR_" in stripped:
            out.append(stripped.split()[-1])
    return out


def live_sheet(data):
    """The governing sheet is the one whose key cell carries this day
    reference. Position, position from the end, sorted rank and name all vary
    from one operating day to the next."""
    for name, rows in data["workbook"]:
        for row in rows[:6]:
            if len(row) >= 2 and row[0] == "day reference" \
                    and row[1] == data["day_reference"]:
                return name, rows
    raise ValueError("no workbook sheet carries the day reference")


def _sheet_section(rows, header_first):
    """Rows of the block that follows the header row whose first cell reads
    header_first, up to the next blank row."""
    out = []
    seen = False
    for row in rows:
        if not seen:
            if row and row[0] == header_first:
                seen = True
            continue
        if not row or not row[0]:
            break
        out.append(row)
    return out


def read_controls(data):
    name, rows = live_sheet(data)
    controls = {"live_sheet": name}
    for row in _sheet_section(rows, "control"):
        if row[0] == "reconciliation damping fraction":
            controls["damping_num"] = as_int(row[1])
            controls["damping_den"] = as_int(row[2])
        elif row[0] == "base service charge cents":
            controls["base_service_charge_cents"] = as_int(row[1])
    coeff = {}
    for row in _sheet_section(rows, "temperature class"):
        coeff[row[0]] = (as_int(row[1]), as_int(row[2]))
    controls["maintenance_coefficient"] = coeff
    ceilings = {}
    for row in _sheet_section(rows, "vessel"):
        ceilings[row[0]] = as_int(row[1])
    controls["vessel_share_ceiling_wh"] = ceilings
    sub_ceiling = {}
    for row in _sheet_section(rows, "substation"):
        sub_ceiling[row[0]] = as_int(row[1])
    controls["substation_ceiling_w"] = sub_ceiling

    ladder = []
    for line in data["memo"]:
        text = line.strip()
        if text.startswith("pass budget "):
            controls["pass_budget"] = as_int(text.split()[-1])
        elif text.startswith("minimum step watt hours"):
            controls["minimum_step_wh"] = as_int(text.split()[-1])
        elif text.startswith("dependency protection depth"):
            controls["protection_depth"] = as_int(text.split()[-1])
        else:
            parts = text.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                ladder.append((int(parts[0]), int(parts[1])))
    controls["surcharge_ladder"] = sorted(set(ladder))

    keys = []
    ranks = {}
    for kind, payload in data["directive"]:
        if kind != "table":
            continue
        head = payload[0]
        if head and head[0] == "key position":
            for row in payload[1:]:
                keys.append(row[1])
        elif head and head[0] == "temperature class" and len(head) == 2:
            for row in payload[1:]:
                ranks[row[0]] = as_int(row[1])
    controls["ordering_keys"] = keys
    controls["class_rank"] = ranks
    return controls


# --------------------------------------------------------------------------
# precedence
# --------------------------------------------------------------------------


def applicable(rows, key_fields, day_id, seq_field):
    """The row that governs a key: this operating day, an applicable record
    state, and among those the highest sequence. A set aside row is dropped
    before the sequence is read, so a set aside row carrying the highest
    sequence settles nothing."""
    best = {}
    for row in rows:
        if row.get("day_id") != day_id:
            continue
        if row.get("record_state", "current") not in APPLICABLE_STATES:
            continue
        key = tuple(row.get(f, "") for f in key_fields)
        seq = as_int(row.get(seq_field), 0)
        prior = best.get(key)
        if prior is None or seq > prior[0]:
            best[key] = (seq, row)
    return dict((k, v[1]) for k, v in best.items())


def mine(rows, day_id):
    return [r for r in rows if r.get("day_id") == day_id]


# --------------------------------------------------------------------------
# stage p01, unit normalisation
# --------------------------------------------------------------------------


def _unit_factor(table, unit):
    entry = table.get(unit)
    if not isinstance(entry, dict):
        return None
    return Fraction(as_int(entry.get("numerator"), 0),
                    as_int(entry.get("denominator"), 1))


def declared_reading(ret, factor):
    """The declared energy a return carries. A return with the not supplied
    marker, and a reefer with no governing return at all, declared nothing;
    neither declared zero."""
    if ret is None or is_absent(ret.get("declared_value")):
        return "not_declared"
    if factor is None:
        return "not_declared"
    return round_half_up(Fraction(as_int(ret.get("declared_value"))) * factor)


def stage_p01(data):
    day = data["day_id"]
    controls = read_controls(data)
    data["controls"] = controls

    plugs = applicable(data["plug_rows"], ["plug_id"], day, "revision_seq")
    data["plugs"] = plugs

    in_force = set()
    plug_in_topology = set()
    for feeder in data["topology"].iter("feeder"):
        in_force.add(feeder.get("id"))
        for plug in feeder.iter("plug"):
            plug_in_topology.add(plug.get("id"))
    data["feeders_in_force"] = in_force
    data["plugs_in_topology"] = plug_in_topology

    feeders = applicable(data["feeder_rows"], ["feeder_id"], day, "revision_seq")
    data["feeder_records"] = feeders

    calls = applicable(data["call_rows"], ["vessel_id"], day, "revision_seq")
    data["calls"] = calls

    energy = applicable(data["energy_rows"], ["reefer_id"], day, "declaration_seq")
    reefer_rows = applicable(data["reefer_rows"], ["reefer_id"], day, "revision_seq")

    power_units = data["units"].get("power", {})
    energy_units = data["units"].get("energy", {})

    records = []
    for key in sorted(reefer_rows):
        row = reefer_rows[key]
        rid = row["reefer_id"]
        plug_id = row["plug_id"]
        plug = plugs.get((plug_id,))
        feeder_id = plug["feeder_id"] if plug else ""
        substation = ""
        if feeder_id and (feeder_id,) in feeders:
            substation = feeders[(feeder_id,)]["substation_id"]
        factor = _unit_factor(power_units, row["nameplate_unit"])
        if factor is None:
            nameplate_w = 0
            unit_state = "unknown_unit"
        else:
            nameplate_w = round_half_up(
                Fraction(as_int(row["nameplate_value"])) * factor)
            unit_state = "converted"
        ret = energy.get((rid,))
        efactor = None
        if ret is not None:
            efactor = _unit_factor(energy_units, ret.get("energy_unit"))
        declared = declared_reading(ret, efactor)
        records.append({
            "reefer_id": rid,
            "plug_id": plug_id,
            "feeder_id": feeder_id,
            "substation_id": substation,
            "vessel_id": row["vessel_id"],
            "temperature_class": row["temperature_class"],
            "nameplate_w": nameplate_w,
            "unit_state": unit_state,
            "connect_minute": as_int(row["connect_minute"]),
            "disconnect_minute": as_int(row["disconnect_minute"]),
            "source_system": row["source_system"],
            "declared_energy_wh": declared,
        })
    data["reefers"] = records
    data["reefer_by_id"] = dict((r["reefer_id"], r) for r in records)
    return data


# --------------------------------------------------------------------------
# stage p02, the availability lattice
# --------------------------------------------------------------------------


def interval_of(minute):
    """Interval n covers the minutes from fifteen times n minus one inclusive
    to fifteen times n exclusive."""
    return (minute // INTERVAL_MINUTES) + 1


def window_intervals(connect, disconnect):
    """The connection window is closed at the connect minute and open at the
    disconnect minute, so a disconnection landing on a boundary closes the
    interval before it."""
    if disconnect <= connect:
        return []
    first = interval_of(connect)
    last = interval_of(disconnect - 1)
    first = max(1, first)
    last = min(INTERVAL_COUNT, last)
    if last < first:
        return []
    return list(range(first, last + 1))


def stage_p02(data):
    day = data["day_id"]
    grid = {}
    for row in mine(data["grid_rows"], day):
        grid[as_int(row["interval"])] = row
    data["grid"] = grid

    blocked_feeder = {}
    blocked_plug = {}
    blocked_crane = {}
    battery_offline = set()
    for row in mine(data["maintenance_rows"], day):
        if row.get("window_state") != "booked":
            continue
        first = as_int(row["first_interval"])
        last = as_int(row["last_interval"])
        span = set(range(max(1, first), min(INTERVAL_COUNT, last) + 1))
        kind = row["resource_kind"]
        rid = row["resource_id"]
        if kind == "feeder":
            blocked_feeder.setdefault(rid, set()).update(span)
        elif kind == "plug":
            blocked_plug.setdefault(rid, set()).update(span)
        elif kind == "crane":
            blocked_crane.setdefault(rid, set()).update(span)
        elif kind == "battery":
            battery_offline.update(span)
    data["blocked_feeder"] = blocked_feeder
    data["blocked_plug"] = blocked_plug
    data["blocked_crane"] = blocked_crane
    data["battery_blocked"] = battery_offline

    lattice = {}
    rows = []
    for rec in data["reefers"]:
        spans = window_intervals(rec["connect_minute"], rec["disconnect_minute"])
        out = []
        for n in spans:
            if n in blocked_feeder.get(rec["feeder_id"], ()):
                continue
            if n in blocked_plug.get(rec["plug_id"], ()):
                continue
            out.append(n)
        lattice[rec["reefer_id"]] = out
        if not out:
            state = "empty"
        elif len(out) == 1:
            state = "single_slot"
        else:
            state = "open"
        rows.append([rec["reefer_id"], out[0] if out else 0,
                     out[-1] if out else 0, len(out), state])
    data["lattice"] = lattice
    data["lattice_rows"] = rows

    demand = {}
    for rec in data["reefers"]:
        for n in lattice[rec["reefer_id"]]:
            key = (n, rec["feeder_id"])
            entry = demand.setdefault(key, [0, 0])
            entry[0] += 1
            entry[1] += rec["nameplate_w"]
    data["interval_demand"] = demand
    return data


# --------------------------------------------------------------------------
# stage p03, the mandatory energy floor
# --------------------------------------------------------------------------


def ambient_multiplier(data, temperature_class, ambient_class):
    """The pairing the multiplier table carries, and the class default when
    the table carries no row for that pairing. An absent multiplier is a
    fallback to the default and it is not a multiplier of zero."""
    key = (temperature_class, ambient_class)
    table = data["ambient_index"]
    if key in table:
        return table[key]
    default = data["ambient"]["class_default_multiplier"]
    return Fraction(as_int(default["multiplier_numerator"]),
                    as_int(default["multiplier_denominator"]))


def stage_p03(data):
    day = data["day_id"]
    index = {}
    for row in data["ambient"]["multiplier_table"]:
        index[(row["temperature_class"], row["ambient_class"])] = Fraction(
            as_int(row["multiplier_numerator"]),
            as_int(row["multiplier_denominator"]))
    data["ambient_index"] = index

    ambient_of = {}
    for row in data["ambient"]["interval_readings"]:
        if row.get("day_id") == day:
            ambient_of[as_int(row["interval"])] = row["ambient_class"]
    data["ambient_of"] = ambient_of

    coeff = data["controls"]["maintenance_coefficient"]
    per_interval = {}
    per_interval_draw = {}
    rows = []
    for rec in data["reefers"]:
        rid = rec["reefer_id"]
        num, den = coeff.get(rec["temperature_class"], (1000, 1000))
        cfactor = Fraction(num, den)
        table = {}
        draws = {}
        total = 0
        for n in data["lattice"][rid]:
            mult = ambient_multiplier(data, rec["temperature_class"],
                                      ambient_of.get(n, "temperate"))
            scaled = Fraction(rec["nameplate_w"]) * mult * cfactor
            stored = round_half_up(scaled / 4)
            table[n] = stored
            draws[n] = round_half_up(scaled)
            total += stored
        per_interval[rid] = table
        per_interval_draw[rid] = draws
        if rec["declared_energy_wh"] == "not_declared":
            requested = total
            state = "defaulted"
        else:
            requested = rec["declared_energy_wh"]
            state = "declared"
        rows.append([rid, len(table), total, requested,
                     max(0, requested - total), state])
        rec["mandatory_wh"] = total
        rec["requested_wh"] = requested
        rec["discretionary_wh"] = max(0, requested - total)
        rec["floor_state"] = state
    data["per_interval_floor"] = per_interval
    data["per_interval_draw"] = per_interval_draw
    data["floor_rows"] = rows
    return data


# --------------------------------------------------------------------------
# stage p04, the admission ladder and the dispatch priority queue
# --------------------------------------------------------------------------

ABSENT_SLACK = 999
ABSENT_URGENCY = 9


def stage_p04(data):
    day = data["day_id"]
    zone_rows = applicable(data["zone_rows"], ["plug_zone", "temperature_class"],
                           day, "revision_seq")
    admission = {}
    for key, row in zone_rows.items():
        admission[key] = row["admission"]

    waived = set()
    critical = set()
    for notice in data["notices"]:
        if notice.get("day_id") != day:
            continue
        if notice.get("kind") == "zone_waiver":
            waived.add(notice.get("subject_id"))
        elif notice.get("kind") == "priority_override":
            critical.add(notice.get("subject_id"))
    data["waived"] = waived
    data["critical"] = critical

    rungs = data["ladder"]
    verdict = {}
    survivors = []
    for rec in data["reefers"]:
        rid = rec["reefer_id"]
        caught = ""
        for rung in rungs:
            if rung == "DR_UNKNOWN_PLUG":
                plug = data["plugs"].get((rec["plug_id"],))
                if plug is None or plug.get("plug_state") != "live":
                    caught = rung
            elif rung == "DR_FEEDER_OUT_OF_FORCE":
                if rec["feeder_id"] not in data["feeders_in_force"]:
                    caught = rung
            elif rung == "DR_WINDOW_EMPTY":
                if not data["lattice"][rid]:
                    caught = rung
            elif rung == "DR_UNKNOWN_POWER_UNIT":
                if rec["unit_state"] == "unknown_unit":
                    caught = rung
            elif rung == "DR_PLUG_ZONE_REFUSED":
                plug = data["plugs"].get((rec["plug_id"],))
                zone = plug.get("plug_zone") if plug else ""
                if admission.get((zone, rec["temperature_class"])) == "refused" \
                        and rid not in waived:
                    caught = rung
            if caught:
                break
        verdict[rid] = caught
        if not caught:
            survivors.append(rec)

    # The cluster rung is settled among the reefers the earlier rungs left
    # standing. The canonical member of a cluster is the lowest identifier of
    # those survivors, which is not always the lowest identifier in the
    # cluster.
    clusters = {}
    for rec in survivors:
        clusters.setdefault(rec["plug_id"], []).append(rec["reefer_id"])
    for plug_id, members in clusters.items():
        for rid in sorted(members)[1:]:
            verdict[rid] = "DR_DUPLICATE_CONNECTION"
    data["ladder_verdict"] = verdict

    ranks = data["controls"]["class_rank"]
    queued = []
    for rec in data["reefers"]:
        rid = rec["reefer_id"]
        if verdict[rid]:
            continue
        call = data["calls"].get((rec["vessel_id"],))
        if call is None:
            slack = ABSENT_SLACK
            urgency = ABSENT_URGENCY
            cutoff = INTERVAL_COUNT
            group = "sg_none"
        else:
            cutoff = as_int(call["cutoff_interval"])
            slack = cutoff - data["lattice"][rid][-1]
            urgency = as_int(call["urgency_rank"])
            group = call["service_group"]
        rec["cutoff_interval"] = cutoff
        rec["service_group"] = group
        rec["class_rank"] = ranks.get(rec["temperature_class"], 9)
        rec["deadline_slack"] = slack
        rec["urgency_rank"] = urgency
        queued.append(rec)

    queued.sort(key=lambda r: (r["deadline_slack"], r["class_rank"],
                               r["urgency_rank"], r["reefer_id"]))
    rows = []
    for i, rec in enumerate(queued, start=1):
        rec["rank"] = i
        rows.append([i, rec["reefer_id"], rec["deadline_slack"],
                     rec["class_rank"], rec["urgency_rank"], "queued"])
    for rec in data["reefers"]:
        rid = rec["reefer_id"]
        if verdict[rid]:
            rec["rank"] = 0
            rows.append([0, rid, 0, 0, 0, verdict[rid]])
    data["queue"] = queued
    data["queue_rows"] = rows
    return data


# --------------------------------------------------------------------------
# stage p05, the provisional allocation
# --------------------------------------------------------------------------


def nominal_capacity(data, feeder_id, n):
    record = data["feeder_records"].get((feeder_id,))
    if record is None:
        return 0
    if n in data["blocked_feeder"].get(feeder_id, ()):
        return 0
    base = as_int(record["nominal_capacity_w"])
    notice = data["derating"].get(feeder_id)
    if notice is not None and notice[0] <= n <= notice[1]:
        base = floor_div(Fraction(base * notice[2], 1000))
    return base


def stage_p05(data):
    day = data["day_id"]
    derating = {}
    for key, row in applicable(data["derate_rows"], ["feeder_id"], day,
                               "notice_seq").items():
        derating[key[0]] = (as_int(row["first_interval"]),
                            as_int(row["last_interval"]),
                            as_int(row["derate_permille"]))
    data["derating"] = derating

    feeders = sorted(data["feeders_in_force"])
    data["feeder_list"] = feeders
    cap_nominal = {}
    for f in feeders:
        for n in range(1, INTERVAL_COUNT + 1):
            cap_nominal[(f, n)] = nominal_capacity(data, f, n)
    data["cap_nominal"] = cap_nominal

    draw = {}
    for rec in data["queue"]:
        rid = rec["reefer_id"]
        for n, watts in data["per_interval_draw"][rid].items():
            draw[(rid, n)] = watts
    data["draw"] = draw

    powered = {}
    load = {}
    rows = []
    for n in range(1, INTERVAL_COUNT + 1):
        running = {}
        for rec in data["queue"]:
            rid = rec["reefer_id"]
            if (rid, n) not in draw:
                continue
            f = rec["feeder_id"]
            cap = cap_nominal.get((f, n), 0)
            amount = draw[(rid, n)]
            current = running.get(f, 0)
            if current + amount <= cap:
                running[f] = current + amount
                powered[(rid, n)] = True
            else:
                powered[(rid, n)] = False
        for rec in data["queue"]:
            rid = rec["reefer_id"]
            if (rid, n) not in draw:
                continue
            rows.append([n, rec["feeder_id"], rid, draw[(rid, n)],
                         "powered" if powered[(rid, n)] else "held"])
        for f in feeders:
            load[(f, n)] = running.get(f, 0)
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    data["provisional_powered"] = powered
    data["provisional_load"] = load
    data["provisional_rows"] = rows
    return data


# --------------------------------------------------------------------------
# stage p06, feeder reconciliation and the spill
# --------------------------------------------------------------------------


def reserve_of(data, feeder_id):
    record = data["feeder_records"].get((feeder_id,))
    if record is None:
        return 0
    return as_int(record["standing_reserve_w"])


def spill_candidates(data, reefer_id, from_interval):
    """The intervals a removed placement may spill into, in the order they
    are tried. A displaced placement moves to the next eligible interval and
    it does not move to the cheapest interval of the day."""
    return [m for m in data["lattice"][reefer_id] if m > from_interval]


def stage_p06(data):
    feeders = data["feeder_list"]
    draw = data["draw"]
    cap_reserved = {}
    for f in feeders:
        reserve = reserve_of(data, f)
        for n in range(1, INTERVAL_COUNT + 1):
            cap_reserved[(f, n)] = max(0, data["cap_nominal"][(f, n)] - reserve)
    data["cap_reserved"] = cap_reserved

    powered = dict(data["provisional_powered"])
    load = {}
    for f in feeders:
        for n in range(1, INTERVAL_COUNT + 1):
            load[(f, n)] = 0
    by_interval = {}
    for rec in data["queue"]:
        rid = rec["reefer_id"]
        for n in data["lattice"][rid]:
            by_interval.setdefault(n, []).append(rec)

    rank_of = dict((r["reefer_id"], r["rank"]) for r in data["queue"])
    feeder_of = dict((r["reefer_id"], r["feeder_id"]) for r in data["queue"])
    lattice = data["lattice"]

    violations = []
    spills = []
    for n in range(1, INTERVAL_COUNT + 1):
        for rec in by_interval.get(n, []):
            rid = rec["reefer_id"]
            if powered.get((rid, n)):
                load[(rec["feeder_id"], n)] += draw[(rid, n)]
        for f in feeders:
            cap = cap_reserved[(f, n)]
            before = load[(f, n)]
            removed = 0
            while load[(f, n)] > cap:
                standing = [rec for rec in by_interval.get(n, [])
                            if rec["feeder_id"] == f and powered.get(
                                (rec["reefer_id"], n))]
                if not standing:
                    break
                standing.sort(key=lambda r: (-r["rank"], r["reefer_id"]))
                victim = standing[0]
                vid = victim["reefer_id"]
                powered[(vid, n)] = False
                load[(f, n)] -= draw[(vid, n)]
                removed += 1
                target = 0
                for m in spill_candidates(data, vid, n):
                    if powered.get((vid, m)):
                        continue
                    amount = draw[(vid, m)]
                    if load[(f, m)] + amount <= cap_reserved[(f, m)]:
                        powered[(vid, m)] = True
                        load[(f, m)] += amount
                        target = m
                        break
                spills.append([vid, n, target, f, draw[(vid, n)],
                               "spilled" if target else "unspilled"])
            if removed:
                violations.append([n, f, before, cap, before - cap, removed])
    data["reconciled_powered"] = powered
    data["reconciled_load"] = load
    data["violation_rows"] = violations
    spills.sort(key=lambda r: (r[1], r[3], r[0]))
    data["spill_rows"] = spills
    data["rank_of"] = rank_of
    data["feeder_of"] = feeder_of
    data["by_interval"] = by_interval
    return data


# --------------------------------------------------------------------------
# stage p07, the crane adjusted capacity
# --------------------------------------------------------------------------


def crane_adjustment(reserved, drawn):
    """A confirmed crane duty reduces the capacity left for reefers. It is
    not an extra load added to the reefer load."""
    value = reserved - drawn
    if value < 0:
        return 0, "clamped"
    return value, "clear"


def stage_p07(data):
    day = data["day_id"]
    earliest = {}
    for row in data["confirm_rows"]:
        if row.get("day_id") != day:
            continue
        key = (row["crane_id"], as_int(row["interval"]))
        seq = as_int(row["confirm_seq"])
        prior = earliest.get(key)
        if prior is None or seq < prior[0]:
            earliest[key] = (seq, row["confirmation_state"])
    data["confirmation"] = earliest

    crane_draw = {}
    for row in data["duty_rows"]:
        if row.get("day_id") != day:
            continue
        crane = row["crane_id"]
        n = as_int(row["interval"])
        if n in data["blocked_crane"].get(crane, ()):
            continue
        landed = earliest.get((crane, n))
        if landed is None or landed[1] != "landed":
            continue
        key = (row["feeder_id"], n)
        crane_draw[key] = crane_draw.get(key, 0) + as_int(row["demand_kw"]) * 1000
    data["crane_draw"] = crane_draw

    adjusted = {}
    rows = []
    for f in data["feeder_list"]:
        for n in range(1, INTERVAL_COUNT + 1):
            reserved = data["cap_reserved"][(f, n)]
            drawn = crane_draw.get((f, n), 0)
            value, state = crane_adjustment(reserved, drawn)
            adjusted[(f, n)] = value
            rows.append([n, f, reserved, drawn, value, state])
    rows.sort(key=lambda r: (r[0], r[1]))
    data["adjusted_capacity"] = adjusted
    data["adjusted_rows"] = rows
    return data


# --------------------------------------------------------------------------
# stage p08, the battery
# --------------------------------------------------------------------------


def dischargeable_wh(soc, reserve, discharge_eff):
    """What the battery may deliver in one interval given where its state of
    charge stands. Nothing below the reserve is available."""
    return floor_div(Fraction((soc - reserve) * discharge_eff, 1000))


def stage_p08(data):
    day = data["day_id"]
    policy = data["battery_policy"]
    substation = policy["substation_id"]
    capacity = as_int(policy["capacity_wh"])
    reserve = as_int(policy["reserve_wh"])
    soc = as_int(policy["initial_state_of_charge_wh"])
    max_charge = as_int(policy["max_charge_w"])
    max_discharge = as_int(policy["max_discharge_w"])
    charge_eff = as_int(policy["charge_efficiency_permille"])
    discharge_eff = as_int(policy["discharge_efficiency_permille"])
    bands = policy["charge_eligible_bands"]

    online = set()
    for row in mine(data["telemetry_rows"], day):
        if row.get("availability_state") == "online":
            online.add(as_int(row["interval"]))
    served = [f for f in data["feeder_list"]
              if data["feeder_records"].get((f,), {}).get("substation_id")
              == substation]

    support = {}
    schedule = []
    soc_rows = []
    cycled = 0
    for n in range(1, INTERVAL_COUNT + 1):
        opening = soc
        available = n in online and n not in data["battery_blocked"]
        deficit_w = 0
        for f in served:
            deficit_w += max(0, data["reconciled_load"][(f, n)]
                             - data["adjusted_capacity"][(f, n)])
        discharge_wh = 0
        charge_wh = 0
        reason = "none"
        if not available:
            action = "offline"
        elif deficit_w > 0:
            action = "discharge"
            limit_draw = floor_div(Fraction(max_discharge, 4))
            limit_soc = dischargeable_wh(soc, reserve, discharge_eff)
            want = floor_div(Fraction(deficit_w, 4))
            discharge_wh = min(want, limit_draw, limit_soc)
            if discharge_wh <= 0:
                discharge_wh = 0
                reason = "state_of_charge_on_reserve"
            elif discharge_wh == limit_draw:
                reason = "discharge_limit"
            elif discharge_wh == limit_soc:
                reason = "state_of_charge_limit"
            else:
                reason = "deficit_met"
            soc -= ceil_div(Fraction(discharge_wh * 1000, discharge_eff))
            cycled += discharge_wh
        elif data["grid"][n]["tariff_band"] in bands:
            action = "charge"
            headroom_w = 0
            for f in served:
                headroom_w += max(0, data["adjusted_capacity"][(f, n)]
                                  - data["reconciled_load"][(f, n)])
            limit_charge = floor_div(Fraction(max_charge, 4))
            limit_head = floor_div(Fraction(headroom_w, 4))
            limit_room = capacity - soc
            charge_wh = min(limit_charge, limit_head, limit_room)
            if charge_wh <= 0:
                charge_wh = 0
                reason = "no_room"
            elif charge_wh == limit_room:
                reason = "capacity_limit"
            elif charge_wh == limit_charge:
                reason = "charge_limit"
            else:
                reason = "headroom_limit"
            soc += floor_div(Fraction(charge_wh * charge_eff, 1000))
            cycled += charge_wh
        else:
            action = "idle"
            reason = "band_ineligible"
        schedule.append([n, action, floor_div(Fraction(deficit_w, 4)),
                         discharge_wh, charge_wh, reason])
        soc_rows.append([n, opening, soc, reserve,
                         "at_reserve" if soc == reserve else
                         ("below_reserve" if soc < reserve else "above_reserve")])
        remaining = discharge_wh * 4
        for f in served:
            need = max(0, data["reconciled_load"][(f, n)]
                       - data["adjusted_capacity"][(f, n)])
            take = min(need, remaining)
            support[(f, n)] = take
            remaining -= take
    for f in data["feeder_list"]:
        for n in range(1, INTERVAL_COUNT + 1):
            support.setdefault((f, n), 0)
    data["battery_support"] = support
    data["battery_rows"] = schedule
    data["soc_rows"] = soc_rows
    data["battery_cycled_wh"] = cycled
    data["battery_closing_soc"] = soc
    data["battery_reserve"] = reserve
    data["battery_capacity"] = capacity
    data["battery_substation"] = substation
    return data


# --------------------------------------------------------------------------
# stage p09, the damped reconciliation passes and the allowance placement
# --------------------------------------------------------------------------


def reconciliation_budget(controls):
    return controls["pass_budget"]


def quantise_share(value, pass_number, budget):
    """Every pass closes on a whole watt hour, and the pass after it opens
    from that rounded share."""
    return round_half_up(value)


def cell_key(data, rec):
    return (rec.get("substation_id", ""), rec.get("service_group", "sg_none"))


def stage_p09(data):
    controls = data["controls"]
    damping = Fraction(controls["damping_num"], controls["damping_den"])
    budget = reconciliation_budget(controls)
    minimum = controls["minimum_step_wh"]
    ceilings = controls["vessel_share_ceiling_wh"]

    headroom_w = {}
    pool = {}
    for f in data["feeder_list"]:
        total = 0
        for n in range(1, INTERVAL_COUNT + 1):
            value = max(0, data["adjusted_capacity"][(f, n)]
                        + data["battery_support"][(f, n)]
                        - data["reconciled_load"][(f, n)])
            headroom_w[(f, n)] = value
            total += value
        pool[f] = floor_div(Fraction(total, 4))
    data["headroom_w"] = headroom_w
    data["pool"] = pool

    members = {}
    for rec in data["queue"]:
        if rec["discretionary_wh"] <= 0:
            continue
        members.setdefault(rec["feeder_id"], []).append(rec)
    for f in members:
        members[f].sort(key=lambda r: r["rank"])

    share = {}
    limit = {}
    for f, group in members.items():
        for rec in group:
            rid = rec["reefer_id"]
            share[rid] = 0
            ceiling = ceilings.get(rec["vessel_id"], rec["discretionary_wh"])
            limit[rid] = min(rec["discretionary_wh"], ceiling)

    rows = []
    for p in range(1, budget + 1):
        for f in sorted(members):
            group = members[f]
            opening = dict((r["reefer_id"], share[r["reefer_id"]]) for r in group)
            need = {}
            for rec in group:
                rid = rec["reefer_id"]
                need[rid] = max(0, rec["discretionary_wh"] - share[rid])
            need_total = sum(need.values())
            unallocated = pool[f] - sum(share[r["reefer_id"]] for r in group)
            target = {}
            for rec in group:
                rid = rec["reefer_id"]
                if need_total > 0 and unallocated > 0:
                    target[rid] = Fraction(share[rid]) + Fraction(
                        unallocated * need[rid], need_total)
                else:
                    target[rid] = Fraction(share[rid])
            freed = {}
            for rec in group:
                rid = rec["reefer_id"]
                if target[rid] > limit[rid]:
                    key = cell_key(data, rec)
                    freed[key] = freed.get(key, Fraction(0)) + (
                        target[rid] - Fraction(limit[rid]))
                    target[rid] = Fraction(limit[rid])
            if freed:
                for key, mass in freed.items():
                    room = {}
                    for rec in group:
                        rid = rec["reefer_id"]
                        if cell_key(data, rec) != key:
                            continue
                        spare = Fraction(limit[rid]) - target[rid]
                        if spare > 0:
                            room[rid] = spare
                    total_room = sum(room.values())
                    if total_room <= 0:
                        continue
                    for rid, spare in room.items():
                        target[rid] = target[rid] + mass * spare / total_room
            for rec in group:
                rid = rec["reefer_id"]
                moved = Fraction(share[rid]) + damping * (
                    target[rid] - Fraction(share[rid]))
                if moved != Fraction(share[rid]):
                    step = moved - Fraction(share[rid])
                    if step > 0 and step < minimum:
                        moved = Fraction(share[rid] + minimum)
                    elif step < 0 and -step < minimum:
                        moved = Fraction(share[rid] - minimum)
                value = quantise_share(moved, p, budget)
                value = max(0, min(value, limit[rid]))
                share[rid] = value
            for rec in group:
                rid = rec["reefer_id"]
                rows.append([p, f, rid, opening[rid], need[rid],
                             round_half_up(target[rid]), share[rid],
                             "moving" if share[rid] != opening[rid] else "settled"])
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    data["share"] = share
    data["reconciliation_rows"] = rows

    headroom_wh = {}
    for key, value in headroom_w.items():
        headroom_wh[key] = floor_div(Fraction(value, 4))
    placed = {}
    unplaced = {}
    for rec in data["queue"]:
        rid = rec["reefer_id"]
        remaining = share.get(rid, 0)
        if remaining <= 0:
            unplaced[rid] = 0
            continue
        f = rec["feeder_id"]
        for n in data["lattice"][rid]:
            if remaining <= 0:
                break
            room = headroom_wh.get((f, n), 0)
            if room <= 0:
                continue
            take = min(remaining, room)
            placed[(rid, n)] = take
            headroom_wh[(f, n)] = room - take
            remaining -= take
        unplaced[rid] = remaining
    data["placed"] = placed
    data["unplaced"] = unplaced

    final_load = {}
    for f in data["feeder_list"]:
        for n in range(1, INTERVAL_COUNT + 1):
            final_load[(f, n)] = data["reconciled_load"][(f, n)]
    for (rid, n), wh in placed.items():
        f = data["feeder_of"][rid]
        final_load[(f, n)] += wh * 4
    data["final_load"] = final_load
    return data


# --------------------------------------------------------------------------
# stage p10, the tariff and the demand charge
# --------------------------------------------------------------------------


def stage_p10(data):
    day = data["day_id"]
    prices = {}
    for key, row in applicable(data["tariff_rows"], ["interval"], day,
                               "schedule_seq").items():
        prices[as_int(key[0])] = as_int(row["price_tenth_cents_per_kwh"])
    data["prices"] = prices

    rows = []
    energy_cents = 0
    yard_load = {}
    for n in range(1, INTERVAL_COUNT + 1):
        total_w = 0
        for f in data["feeder_list"]:
            total_w += data["final_load"][(f, n)]
        yard_load[n] = total_w
        energy_wh = round_half_up(Fraction(total_w, 4))
        price = prices.get(n, 0)
        charge = round_half_up(Fraction(energy_wh * price, 10000))
        energy_cents += charge
        rows.append([n, data["grid"][n]["tariff_band"], price, total_w,
                     energy_wh, charge])
    data["tariff_rows_out"] = rows
    data["energy_charge_cents"] = energy_cents
    data["yard_load"] = yard_load

    bands = {}
    for key, row in applicable(data["band_rows"], ["substation_id", "band_code"],
                               day, "revision_seq").items():
        bands.setdefault(key[0], []).append(row)
    for s in bands:
        bands[s].sort(key=lambda r: as_int(r["floor_w"]))

    sub_load = {}
    for s in SUBSTATIONS:
        for n in range(1, INTERVAL_COUNT + 1):
            sub_load[(s, n)] = 0
    for f in data["feeder_list"]:
        record = data["feeder_records"].get((f,))
        if record is None:
            continue
        s = record["substation_id"]
        for n in range(1, INTERVAL_COUNT + 1):
            sub_load[(s, n)] = sub_load.get((s, n), 0) + data["final_load"][(f, n)]
    data["substation_load"] = sub_load

    entries = []
    demand_cents = 0
    for s in SUBSTATIONS:
        peak = 0
        at = 0
        for n in range(1, INTERVAL_COUNT + 1):
            value = sub_load.get((s, n), 0)
            if value > peak:
                peak = value
                at = n
        if at == 0:
            at = 1
        code = ""
        charge = 0
        for row in bands.get(s, []):
            if as_int(row["floor_w"]) <= peak < as_int(row["ceiling_w"]):
                code = row["band_code"]
                charge = as_int(row["charge_cents"])
                break
        demand_cents += charge
        entries.append({"substation_id": s, "peak_w": peak,
                        "peak_interval": at, "band_code": code,
                        "charge_cents": charge})
    yard_peak = 0
    yard_at = 1
    for n in range(1, INTERVAL_COUNT + 1):
        if yard_load[n] > yard_peak:
            yard_peak = yard_load[n]
            yard_at = n
    data["demand_charge_cents"] = demand_cents
    data["peak_certificate"] = {
        "day_id": day,
        "yard_peak_w": yard_peak,
        "yard_peak_interval": yard_at,
        "substations": entries,
        "demand_charge_cents": demand_cents,
    }
    return data


# --------------------------------------------------------------------------
# stages p11 and p12, the deadline correction and the cycle break
# --------------------------------------------------------------------------


def _served_state(data, powered):
    out = {}
    for rec in data["queue"]:
        rid = rec["reefer_id"]
        cutoff = rec["cutoff_interval"]
        table = data["per_interval_floor"][rid]
        required = 0
        served = 0
        short_intervals = 0
        for n in data["lattice"][rid]:
            if n > cutoff:
                continue
            required += table[n]
            if powered.get((rid, n)):
                served += table[n]
            else:
                short_intervals += 1
        out[rid] = (required, served, max(0, required - served), short_intervals)
    return out


def _signature(powered):
    items = sorted(key for key, on in powered.items() if on)
    text = ";".join("%s@%d" % (rid, n) for rid, n in items)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stage_p11(data):
    depth = data["controls"]["protection_depth"]
    powered = dict(data["reconciled_powered"])
    load = dict(data["final_load"])
    draw = data["draw"]
    eff_cap = {}
    for f in data["feeder_list"]:
        for n in range(1, INTERVAL_COUNT + 1):
            eff_cap[(f, n)] = data["adjusted_capacity"][(f, n)] \
                + data["battery_support"][(f, n)]

    by_rank = sorted(data["queue"], key=lambda r: r["rank"])
    critical = data["critical"]
    frozen = set()
    seen_moves = set()
    cycles = []
    corrections = []
    signatures = [_signature(powered)]
    closing = "budget_spent"
    repeated_at = 0
    max_sweeps = depth + 2
    sweeps = 0
    for sweep in range(1, max_sweeps + 1):
        sweeps = sweep
        state = _served_state(data, powered)
        deficient = [rec for rec in by_rank if state[rec["reefer_id"]][2] > 0]
        deficient.sort(key=lambda r: (0 if r["reefer_id"] in critical else 1,
                                      r["rank"]))
        applied = []
        for rec in deficient:
            rid = rec["reefer_id"]
            if rid in frozen:
                continue
            f = rec["feeder_id"]
            for n in data["lattice"][rid]:
                if n > rec["cutoff_interval"] or powered.get((rid, n)):
                    continue
                standing = []
                for other in data["by_interval"].get(n, []):
                    oid = other["reefer_id"]
                    if oid == rid or other["feeder_id"] != f:
                        continue
                    if not powered.get((oid, n)) or oid in critical \
                            or oid in frozen:
                        continue
                    held = 0
                    for m in data["lattice"][oid]:
                        if m <= other["cutoff_interval"] and powered.get((oid, m)):
                            held += 1
                    if held <= depth:
                        continue
                    standing.append(other)
                if not standing:
                    corrections.append([rid, n, "", f, "refused_protected"])
                    continue
                standing.sort(key=lambda r: (-r["rank"], r["reefer_id"]))
                victim = standing[0]
                vid = victim["reefer_id"]
                gain = draw[(rid, n)] - draw[(vid, n)]
                if gain > 0 and load[(f, n)] - draw[(vid, n)] + draw[(rid, n)] \
                        > eff_cap[(f, n)]:
                    corrections.append([rid, n, vid, f, "refused_no_headroom"])
                    continue
                powered[(vid, n)] = False
                powered[(rid, n)] = True
                load[(f, n)] += gain
                corrections.append([rid, n, vid, f, "corrected"])
                applied.append((rid, vid, n))
                break
        signatures.append(_signature(powered))
        reversed_hits = [t for t in applied if (t[1], t[0], t[2]) in seen_moves]
        if reversed_hits:
            best = None
            for rid, vid, n in reversed_hits:
                penalty = (draw[(vid, n)], n, vid, rid)
                if best is None or penalty < best[0]:
                    best = (penalty, rid, vid, n)
            for rid, vid, n in sorted(reversed_hits):
                cycles.append({"sweep": sweep, "short_reefer": rid,
                               "displaced_reefer": vid, "interval": n,
                               "broken": (rid, vid, n) == best[1:]})
            frozen.add(best[1])
            frozen.add(best[2])
        seen_moves.update(applied)
        if not applied:
            closing = "settled"
            repeated_at = sweep
            break
    corrections.sort(key=lambda r: (r[1], r[3], r[0]))
    data["corrected_powered"] = powered
    data["corrected_load"] = load
    data["correction_rows"] = corrections
    data["cycle_report"] = {
        "day_id": data["day_id"],
        "sweeps_run": sweeps,
        "sweep_budget": max_sweeps,
        "closing_state": closing,
        "settled_at_sweep": repeated_at,
        "correction_count": len([r for r in corrections if r[4] == "corrected"]),
        "cycle_count": len(cycles),
        "cycles": cycles,
        "frozen_reefers": sorted(frozen),
        "state_signatures": [item[:16] for item in signatures],
    }
    return data


# --------------------------------------------------------------------------
# stage p13, the lexicographic objective
# --------------------------------------------------------------------------


def surcharge_for(controls, intervals_short):
    charge = 0
    for rung, cents in controls["surcharge_ladder"]:
        if intervals_short >= rung:
            charge = cents
    return charge


def stage_p13(data):
    controls = data["controls"]
    powered = data["corrected_powered"]
    load = data["corrected_load"]
    state = _served_state(data, powered)

    violations = 0
    for f in data["feeder_list"]:
        for n in range(1, INTERVAL_COUNT + 1):
            cap = data["adjusted_capacity"][(f, n)] + data["battery_support"][(f, n)]
            if load[(f, n)] > cap:
                violations += 1
    soc_violations = 0
    for row in data["soc_rows"]:
        if row[4] == "below_reserve":
            soc_violations += 1

    unmet = 0
    penalty = 0
    service = []
    for rec in sorted(data["queue"], key=lambda r: r["reefer_id"]):
        rid = rec["reefer_id"]
        required, served, short, short_intervals = state[rid]
        unmet += short
        cents = surcharge_for(controls, short_intervals) if short > 0 else 0
        penalty += cents
        service.append([rid, rec["feeder_id"], rec["vessel_id"], required,
                        served, short, short_intervals,
                        data["share"].get(rid, 0), data["unplaced"].get(rid, 0),
                        cents, "unmet" if short > 0 else "met"])
    data["service_rows"] = service
    data["served_state"] = state

    peak = data["peak_certificate"]["yard_peak_w"]
    cost = data["energy_charge_cents"] + data["demand_charge_cents"] \
        + controls["base_service_charge_cents"]
    # RULE P13.g takes each powered reefer identifier once, so the digest is
    # over the set of identifiers and never over one entry per interval.
    tie = hashlib.sha256(";".join(
        sorted(set(rid for rid, n in powered if powered[(rid, n)]))
    ).encode("utf-8")).hexdigest()[:16]

    data["objective"] = {
        "day_id": data["day_id"],
        "lexicographic_order": [
            "hard_violations", "unmet_mandatory_wh", "deadline_penalty_cents",
            "peak_demand_w", "energy_cost_cents", "battery_cycle_wh",
            "tie_key",
        ],
        "hard_violations": violations + soc_violations,
        "unmet_mandatory_wh": unmet,
        "deadline_penalty_cents": penalty,
        "peak_demand_w": peak,
        "energy_cost_cents": cost,
        "battery_cycle_wh": data["battery_cycled_wh"],
        "tie_key": tie,
    }
    data["constraint_certificate"] = {
        "day_id": data["day_id"],
        "feeder_intervals_over_capacity": violations,
        "state_of_charge_below_reserve": soc_violations,
        "reefers_at_share_ceiling": len([
            r for r in data["queue"]
            if data["share"].get(r["reefer_id"], 0) > 0
            and data["share"][r["reefer_id"]] == min(
                r["discretionary_wh"],
                controls["vessel_share_ceiling_wh"].get(
                    r["vessel_id"], r["discretionary_wh"]))]),
        "unplaced_allowance_wh": sum(data["unplaced"].values()),
        "reefers_refused": len([r for r in data["reefers"]
                                if data["ladder_verdict"][r["reefer_id"]]]),
        "reefers_queued": len(data["queue"]),
        "spill_count": len(data["spill_rows"]),
        "unspilled_count": len([r for r in data["spill_rows"]
                                if r[5] == "unspilled"]),
    }
    return data


# --------------------------------------------------------------------------
# stage p14, the publication
# --------------------------------------------------------------------------


def _out_join(sep, values):
    return sep.join("" if v is None else str(v) for v in values)


def _out_rows(path, header, rows, sep):
    lines = [_out_join(sep, header)]
    for row in rows:
        lines.append(_out_join(sep, row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _out_lines(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _out_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n",
                    encoding="utf-8", newline="\n")


def _out_jsonl(path, records):
    lines = [json.dumps(rec, separators=(",", ":"), sort_keys=False)
             for rec in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _xml_text(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _publication_sequence(data):
    """ALL_DOCUMENTS with the substation reports taken in the order the
    reporting roster prints them, which is the order the serialisation
    contract fixes for the documents list and the publication digest."""
    reports = ["substation_report_%s.json" % s for s in data["roster"]]
    out = []
    for name in ALL_DOCUMENTS:
        if name.startswith("substation_report_"):
            if reports:
                out.extend(reports)
                reports = []
            continue
        out.append(name)
    return out


def publish(data, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    powered = data["corrected_powered"]
    load = data["corrected_load"]
    draw = data["draw"]
    placed = data["placed"]

    _out_jsonl(out / "normalised_reefers.jsonl", [
        {
            "reefer_id": r["reefer_id"],
            "plug_id": r["plug_id"],
            "feeder_id": r["feeder_id"],
            "substation_id": r["substation_id"],
            "vessel_id": r["vessel_id"],
            "temperature_class": r["temperature_class"],
            "nameplate_w": r["nameplate_w"],
            "unit_state": r["unit_state"],
            "connect_minute": r["connect_minute"],
            "disconnect_minute": r["disconnect_minute"],
            "declared_energy_wh": r["declared_energy_wh"],
            "source_system": r["source_system"],
        }
        for r in data["reefers"]])

    _out_rows(out / "availability_lattice.csv",
              ["reefer_id", "first_interval", "last_interval", "slot_count",
               "window_state"], data["lattice_rows"], ",")

    demand_rows = []
    for n in range(1, INTERVAL_COUNT + 1):
        for f in data["feeder_list"]:
            count, watts = data["interval_demand"].get((n, f), (0, 0))
            demand_rows.append([n, f, count, watts])
    _out_rows(out / "interval_demand.csv",
              ["interval", "feeder_id", "connected_count", "nominal_demand_w"],
              demand_rows, ",")

    _out_rows(out / "energy_floor_ledger.csv",
              ["reefer_id", "slot_count", "mandatory_wh", "requested_wh",
               "discretionary_wh", "floor_state"], data["floor_rows"], ",")

    _out_rows(out / "dispatch_priority_queue.csv",
              ["rank", "reefer_id", "deadline_slack", "class_rank",
               "urgency_rank", "queue_state"], data["queue_rows"], ",")

    _out_rows(out / "provisional_allocation.psv",
              ["interval", "feeder_id", "reefer_id", "draw_w",
               "allocation_state"], data["provisional_rows"], "|")

    load_rows = []
    for n in range(1, INTERVAL_COUNT + 1):
        for f in data["feeder_list"]:
            cap = data["cap_nominal"][(f, n)]
            reserve = reserve_of(data, f)
            reserved = data["cap_reserved"][(f, n)]
            value = data["reconciled_load"][(f, n)]
            if value > reserved:
                state = "over_capacity"
            elif value == reserved:
                state = "at_capacity"
            else:
                state = "clear"
            load_rows.append([n, f, cap, reserve, reserved, value,
                              reserved - value, state])
    _out_rows(out / "feeder_load_ledger.csv",
              ["interval", "feeder_id", "capacity_w", "reserve_w",
               "reserved_capacity_w", "load_w", "headroom_w", "load_state"],
              load_rows, ",")

    _out_rows(out / "feeder_violation_ledger.csv",
              ["interval", "feeder_id", "provisional_load_w",
               "reserved_capacity_w", "excess_w", "removed_count"],
              data["violation_rows"], ",")

    _out_rows(out / "spill_decisions.tsv",
              ["reefer_id", "from_interval", "to_interval", "feeder_id",
               "draw_w", "spill_state"], data["spill_rows"], "\t")

    _out_rows(out / "crane_adjusted_capacity.csv",
              ["interval", "feeder_id", "reserved_capacity_w", "crane_draw_w",
               "adjusted_capacity_w", "clamp_state"], data["adjusted_rows"], ",")

    _out_rows(out / "battery_schedule.csv",
              ["interval", "action", "deficit_wh", "discharge_wh",
               "charge_wh", "limit_reason"], data["battery_rows"], ",")

    _out_rows(out / "soc_ledger.psv",
              ["interval", "opening_soc_wh", "closing_soc_wh", "reserve_wh",
               "soc_state"], data["soc_rows"], "|")

    _out_rows(out / "reconciliation_iterations.csv",
              ["pass", "feeder_id", "reefer_id", "opening_share_wh", "need_wh",
               "target_wh", "closing_share_wh", "pass_state"],
              data["reconciliation_rows"], ",")

    _out_rows(out / "tariff_charge_ledger.csv",
              ["interval", "tariff_band", "price_tenth_cents_per_kwh",
               "load_w", "energy_wh", "charge_cents"],
              data["tariff_rows_out"], ",")

    _out_json(out / "peak_demand_certificate.json", data["peak_certificate"])

    _out_rows(out / "deadline_correction.csv",
              ["reefer_id", "interval", "displaced_reefer_id", "feeder_id",
               "correction_state"], data["correction_rows"], ",")

    _out_json(out / "cycle_break_report.json", data["cycle_report"])

    _out_json(out / "objective_vector.json", data["objective"])

    _out_json(out / "constraint_certificate.json",
              data["constraint_certificate"])

    schedule_rows = []
    for n in range(1, INTERVAL_COUNT + 1):
        for rec in data["by_interval"].get(n, []):
            rid = rec["reefer_id"]
            base = draw[(rid, n)] if powered.get((rid, n)) else 0
            allowance = placed.get((rid, n), 0)
            if base == 0 and allowance == 0:
                state = "held"
            elif base and allowance:
                state = "powered_with_allowance"
            elif base:
                state = "powered"
            else:
                state = "allowance_only"
            energy = round_half_up(Fraction(base, 4)) + allowance
            schedule_rows.append([n, rec["feeder_id"], rid, base, allowance,
                                  energy, state])
    schedule_rows.sort(key=lambda r: (r[0], r[1], r[2]))
    _out_rows(out / "final_schedule.csv",
              ["interval", "feeder_id", "reefer_id", "base_draw_w",
               "allowance_wh", "energy_wh", "schedule_state"],
              schedule_rows, ",")

    feeder_rows = []
    for n in range(1, INTERVAL_COUNT + 1):
        for f in data["feeder_list"]:
            cap = data["adjusted_capacity"][(f, n)]
            support = data["battery_support"][(f, n)]
            value = load[(f, n)]
            if value > cap + support:
                state = "over_capacity"
            elif value == cap + support:
                state = "at_capacity"
            else:
                state = "clear"
            feeder_rows.append([f, n, value, cap, support, state])
    _out_rows(out / "final_schedule_by_feeder.psv",
              ["feeder_id", "interval", "load_w", "adjusted_capacity_w",
               "battery_support_w", "feeder_state"], feeder_rows, "|")

    vessels = {}
    for rec in data["queue"]:
        vessels.setdefault(rec["vessel_id"], []).append(rec)
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<dispatch day="%s" reference="%s">'
             % (_xml_text(data["day_id"]), _xml_text(data["day_reference"]))]
    state = data["served_state"]
    for vid in sorted(vessels):
        members = sorted(vessels[vid], key=lambda r: r["reefer_id"])
        call = data["calls"].get((vid,))
        cutoff = as_int(call["cutoff_interval"]) if call else INTERVAL_COUNT
        lines.append('  <vessel id="%s" cutoff="%d" members="%d">'
                     % (_xml_text(vid), cutoff, len(members)))
        for rec in members:
            rid = rec["reefer_id"]
            required, served, short, short_intervals = state[rid]
            lines.append('    <reefer id="%s" required_wh="%d" served_wh="%d" '
                         'shortfall_wh="%d" allowance_wh="%d"/>'
                         % (_xml_text(rid), required, served, short,
                            data["share"].get(rid, 0)))
        lines.append("  </vessel>")
    lines.append("</dispatch>")
    _out_lines(out / "final_schedule_by_vessel.xml", lines)

    for s in data["roster"]:
        entry = None
        for item in data["peak_certificate"]["substations"]:
            if item["substation_id"] == s:
                entry = item
        feeders = [f for f in data["feeder_list"]
                   if data["feeder_records"].get((f,), {}).get("substation_id") == s]
        served_wh = 0
        for f in feeders:
            for n in range(1, INTERVAL_COUNT + 1):
                served_wh += round_half_up(Fraction(load[(f, n)], 4))
        _out_json(out / ("substation_report_%s.json" % s), {
            "day_id": data["day_id"],
            "substation_id": s,
            "feeder_count": len(feeders),
            "feeders": feeders,
            "ceiling_w": data["controls"]["substation_ceiling_w"].get(s, 0),
            "peak_w": entry["peak_w"] if entry else 0,
            "peak_interval": entry["peak_interval"] if entry else 0,
            "band_code": entry["band_code"] if entry else "",
            "demand_charge_cents": entry["charge_cents"] if entry else 0,
            "served_energy_wh": served_wh,
        })

    unmet_rows = []
    for row in data["service_rows"]:
        if row[10] == "unmet" or row[8] > 0:
            unmet_rows.append([row[0], row[1], row[2], row[5], row[6], row[8],
                               row[9]])
    _out_rows(out / "unmet_requirement_report.tsv",
              ["reefer_id", "feeder_id", "vessel_id", "shortfall_wh",
               "shortfall_intervals", "unplaced_allowance_wh",
               "surcharge_cents"], unmet_rows, "\t")

    _out_rows(out / "reefer_service_certificate.csv",
              ["reefer_id", "feeder_id", "vessel_id", "required_wh",
               "served_wh", "shortfall_wh", "shortfall_intervals",
               "allowance_wh", "unplaced_allowance_wh", "surcharge_cents",
               "service_state"], data["service_rows"], ",")

    trace = []
    for stage, note, measure in [
        ("p01", "unit normalisation", len(data["reefers"])),
        ("p02", "availability lattice", len(data["lattice_rows"])),
        ("p03", "mandatory energy floor", len(data["floor_rows"])),
        ("p04", "dispatch priority queue", len(data["queue_rows"])),
        ("p05", "provisional allocation", len(data["provisional_rows"])),
        ("p06", "feeder reconciliation", len(data["violation_rows"])),
        ("p07", "crane adjusted capacity", len(data["adjusted_rows"])),
        ("p08", "battery intervention", data["battery_cycled_wh"]),
        ("p09", "load reconciliation passes",
         len(data["reconciliation_rows"])),
        ("p10", "tariff and demand charge", data["energy_charge_cents"]),
        ("p11", "deadline correction", len(data["correction_rows"])),
        ("p12", "cycle detection and break",
         data["cycle_report"]["sweeps_run"]),
        ("p13", "objective reconciliation",
         data["objective"]["unmet_mandatory_wh"]),
        ("p14", "publication", len(ALL_DOCUMENTS)),
    ]:
        trace.append({"stage": stage, "note": note, "measure": measure})
    _out_jsonl(out / "audit_trace.jsonl", trace)

    obj = data["objective"]
    lines = [
        "# control totals for %s" % data["day_id"],
        "day_id = %s" % data["day_id"],
        "day_reference = %s" % data["day_reference"],
        "live_sheet = %s" % data["controls"]["live_sheet"],
        "reefers_normalised = %d" % len(data["reefers"]),
        "reefers_queued = %d" % len(data["queue"]),
        "reefers_refused = %d" % data["constraint_certificate"]["reefers_refused"],
        "spill_count = %d" % len(data["spill_rows"]),
        "hard_violations = %d" % obj["hard_violations"],
        "unmet_mandatory_wh = %d" % obj["unmet_mandatory_wh"],
        "deadline_penalty_cents = %d" % obj["deadline_penalty_cents"],
        "peak_demand_w = %d" % obj["peak_demand_w"],
        "energy_cost_cents = %d" % obj["energy_cost_cents"],
        "battery_cycle_wh = %d" % obj["battery_cycle_wh"],
        "unmet_share_of_mandatory = %s" % ratio_text(
            obj["unmet_mandatory_wh"],
            max(1, sum(v[0] for v in data["served_state"].values()))),
    ]
    _out_lines(out / "dispatch_control_totals.conf", lines)

    summary = [
        "# Ashgrove Point reefer yard dispatch summary",
        "",
        "Operating day %s was recomputed from the working papers under the "
        "input directory. The governing workbook sheet was %s."
        % (data["day_id"], data["controls"]["live_sheet"]),
        "",
        "## Admission",
        "",
        "%d reefers were normalised and %d of them reached the dispatch "
        "priority queue. %d were set aside by the admission ladder."
        % (len(data["reefers"]), len(data["queue"]),
           data["constraint_certificate"]["reefers_refused"]),
        "",
        "## Reconciliation",
        "",
        "The feeder reconciliation removed %d placements and spilled %d of "
        "them into a later interval. The reconciliation ran %d passes against "
        "the pass budget."
        % (len(data["spill_rows"]),
           len([r for r in data["spill_rows"] if r[5] == "spilled"]),
           data["controls"]["pass_budget"]),
        "",
        "## Objective",
        "",
        "hard violations %d, unmet mandatory energy %d watt hours, deadline "
        "penalty %d cents, peak demand %d watts, energy cost %d cents, "
        "battery cycle %d watt hours."
        % (obj["hard_violations"], obj["unmet_mandatory_wh"],
           obj["deadline_penalty_cents"], obj["peak_demand_w"],
           obj["energy_cost_cents"], obj["battery_cycle_wh"]),
        "",
    ]
    _out_lines(out / "daily_dispatch_summary.md", summary)

    published = _publication_sequence(data)
    documents = []
    for name in published:
        if name == "publication_manifest.json":
            continue
        payload = (out / name).read_bytes()
        documents.append({"name": name, "bytes": len(payload),
                          "sha256": hashlib.sha256(payload).hexdigest()})
    core = hashlib.sha256()
    for name in CORE_DOCUMENTS:
        core.update((out / name).read_bytes())
    rest = hashlib.sha256()
    for name in published:
        if name in CORE_DOCUMENTS or name == "publication_manifest.json":
            continue
        rest.update((out / name).read_bytes())
    _out_json(out / "publication_manifest.json", {
        "day_id": data["day_id"],
        "day_reference": data["day_reference"],
        "document_count": len(documents),
        "core_digest": core.hexdigest(),
        "publication_digest": rest.hexdigest(),
        "documents": documents,
    })
    return out


def run_pipeline(data_dir, out_dir):
    data = load_day(data_dir)
    stage_p01(data)
    stage_p02(data)
    stage_p03(data)
    stage_p04(data)
    stage_p05(data)
    stage_p06(data)
    stage_p07(data)
    stage_p08(data)
    stage_p09(data)
    stage_p10(data)
    stage_p11(data)
    stage_p13(data)
    publish(data, out_dir)
    return data


# --------------------------------------------------------------------------
# grading scaffolding
# --------------------------------------------------------------------------

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_STATE = {}


def _drops_privileges():
    return os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() == 0


def _untrusted(command):
    """Submitted code runs as nobody so it cannot read this module, which
    holds the reference pipeline and the seeds."""
    if not _drops_privileges():
        return command
    if shutil.which("setpriv") is None:
        raise RuntimeError("setpriv is required to isolate submitted code from the tests")
    return [*_SETPRIV, *command]


def _workroot():
    """The public half of the grading tree: minted papers, the output
    directories the delivered program writes into, and its working
    directory. Readable by the unprivileged user the program runs as."""
    root = _STATE.get("workroot")
    if root is None:
        root = Path(tempfile.mkdtemp(prefix="reeferdispatch-grade-"))
        # mkdtemp is 0700 and root owned; the dropped child has to traverse it.
        os.chmod(root, 0o755)
        _STATE["workroot"] = root
    return root


def _refroot():
    """The answer key: every recomputed publication and every variant. This
    root keeps mkdtemp's 0700 root ownership and is never relaxed, so the
    delivered program cannot read the output it is being graded against."""
    root = _STATE.get("refroot")
    if root is None:
        root = Path(tempfile.mkdtemp(prefix="reeferdispatch-reference-"))
        _STATE["refroot"] = root
    return root


def _programcwd():
    """An empty directory of its own to run the delivered program in, so a
    listing of the working directory reaches nothing of the grading tree."""
    cwd = _STATE.get("programcwd")
    if cwd is None:
        cwd = _workroot() / "run"
        cwd.mkdir(parents=True, exist_ok=True)
        os.chmod(cwd, 0o777)
        _STATE["programcwd"] = cwd
    return cwd


def _relax(path):
    for item in Path(path).rglob("*"):
        try:
            os.chmod(item, 0o777 if item.is_dir() else 0o666)
        except OSError:
            pass
    try:
        os.chmod(path, 0o777)
    except OSError:
        pass


def _case(seed):
    """Mint one operating day and recompute its publication. Cached."""
    key = "case-%d" % seed
    cached = _STATE.get(key)
    if cached is not None:
        return cached
    data_dir = _workroot() / ("day_%d" % seed) / "papers"
    ref_dir = _refroot() / ("day_%d" % seed)
    if not data_dir.is_dir():
        mint_corpus(seed, SEED_PROFILE[seed], data_dir)
        run_pipeline(data_dir, ref_dir)
        # only the papers are relaxed; ref_dir stays under _refroot().
        _relax(data_dir.parent)
    _STATE[key] = (data_dir, ref_dir)
    return _STATE[key]


def _program():
    path = Path(OUTPUT_ROOT) / PROGRAM_NAME
    if not path.is_file():
        raise AssertionError("no %s was delivered at %s" % (PROGRAM_NAME, path))
    return path


def _program_present():
    """A detector never fires on an empty container: with nothing delivered
    there is no wrong reading to report."""
    return (Path(OUTPUT_ROOT) / PROGRAM_NAME).is_file()


def _delivered():
    return Path(OUTPUT_ROOT)


def _digest_tree(root):
    root = Path(root)
    out = {}
    for item in sorted(root.rglob("*")):
        if item.is_file():
            out[str(item.relative_to(root))] = hashlib.sha256(
                item.read_bytes()).hexdigest()
    return out


def _run_program(data_dir, out_dir, cwd=None, reversed_options=False,
                 precreate=True):
    """precreate False leaves the output directory absent, so the program has
    to create it, which its contract promises. reversed_options hands the two
    options the other way round, which its contract also promises."""
    out_dir = Path(out_dir)
    if precreate:
        out_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(out_dir, 0o777)
    else:
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(out_dir.parent, 0o777)
    work = Path(cwd) if cwd is not None else _programcwd()
    if reversed_options:
        options = ["--out", str(out_dir), "--data", str(data_dir)]
    else:
        options = ["--data", str(data_dir), "--out", str(out_dir)]
    command = [sys.executable, str(_program()), *options]
    result = subprocess.run(_untrusted(command), cwd=str(work), timeout=900,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError("%s exited %d: %s"
                             % (PROGRAM_NAME, result.returncode,
                                (result.stderr or "")[-600:]))


def _case_output(seed, tag="case"):
    """Run the delivered program once per minted day, and remember what the
    run did to both directories. Shared with the cheat detectors."""
    key = "output-%s-%d" % (tag, seed)
    cached = _STATE.get(key)
    if cached is not None:
        return cached
    if not _program_present():
        return None
    data_dir, _ = _case(seed)
    out_dir = _workroot() / ("%s_out_%d" % (tag, seed)) / "published"
    before = _digest_tree(data_dir)
    failed = ""
    # The strained day exercises the two option promises of the program
    # contract: the options arrive the other way round and the output
    # directory does not exist yet.
    awkward = seed == EVAL_SEED and tag == "case"
    try:
        _run_program(data_dir, out_dir, reversed_options=awkward,
                     precreate=not awkward)
    except Exception as exc:
        failed = str(exc)
    after = _digest_tree(data_dir)
    record = {"out": out_dir, "before": before, "after": after, "failed": failed}
    _STATE[key] = record
    return record


def _compare(ref_dir, got_dir, names, label):
    ref_dir = Path(ref_dir)
    got_dir = Path(got_dir)
    for name in names:
        want = (ref_dir / name).read_bytes()
        target = got_dir / name
        if not target.is_file():
            raise AssertionError("%s wrote no %s" % (label, name))
        got = target.read_bytes()
        if got != want:
            raise AssertionError("%s: %s differs, %d bytes against %d"
                                 % (label, name, len(got), len(want)))



ALL_ARTIFACTS = sorted(set(ALL_DOCUMENTS))

# Module names a planted file could shadow inside the verifier. The reference
# pipeline imports every one of them.
REBINDING_NAMES = {
    "fractions.py", "hashlib.py", "io.py", "json.py", "os.py", "pathlib.py",
    "re.py", "shutil.py", "sitecustomize.py", "sqlite3.py", "subprocess.py",
    "sys.py", "tempfile.py", "tokenize.py", "usercustomize.py", "xml.py",
    "zipfile.py",
}


# --------------------------------------------------------------------------
# positive tests
# --------------------------------------------------------------------------


def _t_all_artifacts_exist():
    """POSITIVE: every declared document and the program are present."""
    out = _delivered()
    missing = [name for name in ALL_ARTIFACTS if not (out / name).is_file()]
    if missing:
        raise AssertionError("missing published documents: %s" % ", ".join(missing))
    if not (out / PROGRAM_NAME).is_file():
        raise AssertionError("no %s was delivered" % PROGRAM_NAME)


def _t_core_documents_parse():
    """POSITIVE: the spine documents parse as the shapes the contract names."""
    out = _delivered()
    for name in ("cycle_break_report.json", "objective_vector.json",
                 "publication_manifest.json", "peak_demand_certificate.json",
                 "constraint_certificate.json"):
        try:
            parsed = json.loads((out / name).read_text(encoding="utf-8"))
        except ValueError as exc:
            raise AssertionError("%s is not one JSON object: %s" % (name, exc))
        if not isinstance(parsed, dict):
            raise AssertionError("%s is not one JSON object" % name)
    for name in ("normalised_reefers.jsonl", "audit_trace.jsonl"):
        for number, line in enumerate(
                (out / name).read_text(encoding="utf-8").split("\n"), start=1):
            if not line:
                continue
            try:
                json.loads(line)
            except ValueError as exc:
                raise AssertionError("%s line %d is not one JSON object: %s"
                                     % (name, number, exc))
    for name, sep, header in (
        ("availability_lattice.csv", ",", "reefer_id"),
        ("interval_demand.csv", ",", "interval"),
        ("energy_floor_ledger.csv", ",", "reefer_id"),
        ("dispatch_priority_queue.csv", ",", "rank"),
        ("provisional_allocation.psv", "|", "interval"),
        ("feeder_load_ledger.csv", ",", "interval"),
        ("crane_adjusted_capacity.csv", ",", "interval"),
        ("battery_schedule.csv", ",", "interval"),
        ("soc_ledger.psv", "|", "interval"),
        ("reconciliation_iterations.csv", ",", "pass"),
        ("tariff_charge_ledger.csv", ",", "interval"),
        ("final_schedule.csv", ",", "interval"),
        ("reefer_service_certificate.csv", ",", "reefer_id"),
    ):
        text = (out / name).read_text(encoding="utf-8")
        if not text.endswith("\n"):
            raise AssertionError("%s does not end with one line feed" % name)
        if "\r" in text:
            raise AssertionError("%s carries a carriage return" % name)
        first = text.split("\n")[0]
        if first.split(sep)[0] != header:
            raise AssertionError("%s header starts %r" % (name, first[:60]))


def _shipped_block(block, label):
    _, ref_dir = _case(SAMPLE_SEED)
    _compare(ref_dir, _delivered(), block, label)


def _program_block(seed, block, label):
    record = _case_output(seed)
    if record is None:
        raise AssertionError("no %s was delivered" % PROGRAM_NAME)
    if record["failed"]:
        raise AssertionError(record["failed"])
    _, ref_dir = _case(seed)
    _compare(ref_dir, record["out"], block, label)


def _t_shipped_p01_p02_exact():
    """POSITIVE: the shipped normalisation and lattice documents are byte exact."""
    _shipped_block(BLOCK_P01_P02, "shipped p01 p02")


def _t_shipped_p03_p04_exact():
    """POSITIVE: the shipped energy floor and queue documents are byte exact."""
    _shipped_block(BLOCK_P03_P04, "shipped p03 p04")


def _t_shipped_p05_p06_exact():
    """POSITIVE: the shipped allocation, reserve and spill documents are byte exact."""
    _shipped_block(BLOCK_P05_P06, "shipped p05 p06")


def _t_shipped_p07_p09_exact():
    """POSITIVE: the shipped crane, battery and pass documents are byte exact."""
    _shipped_block(BLOCK_P07_P09, "shipped p07 p09")


def _t_shipped_p10_p14_exact():
    """POSITIVE: the shipped tariff, correction and publication documents are byte exact."""
    _shipped_block(BLOCK_P10_P14, "shipped p10 p14")


def _t_program_strained_early_exact():
    """POSITIVE: the program reproduces stages p01 to p06 of the strained day."""
    _program_block(EVAL_SEED, PROGRAM_EARLY, "strained p01 to p06")


def _t_program_strained_middle_exact():
    """POSITIVE: the program reproduces stages p07 to p09 of the strained day."""
    _program_block(EVAL_SEED, PROGRAM_MIDDLE, "strained p07 to p09")


def _t_program_strained_late_exact():
    """POSITIVE: the program reproduces stages p10 to p14 of the strained day."""
    _program_block(EVAL_SEED, PROGRAM_LATE, "strained p10 to p14")


def _t_program_wide_early_exact():
    """POSITIVE: the program reproduces stages p01 to p06 of the wide day."""
    _program_block(CHALLENGE_SEED, PROGRAM_EARLY, "wide p01 to p06")


def _t_program_wide_middle_exact():
    """POSITIVE: the program reproduces stages p07 to p09 of the wide day."""
    _program_block(CHALLENGE_SEED, PROGRAM_MIDDLE, "wide p07 to p09")


def _t_program_wide_late_exact():
    """POSITIVE: the program reproduces stages p10 to p14 of the wide day."""
    _program_block(CHALLENGE_SEED, PROGRAM_LATE, "wide p10 to p14")


def _t_program_sparse_early_exact():
    """POSITIVE: the program reproduces stages p01 to p06 of the sparse day."""
    _program_block(PROBE_SEED, PROGRAM_EARLY, "sparse p01 to p06")


def _t_program_sparse_middle_exact():
    """POSITIVE: the program reproduces stages p07 to p09 of the sparse day."""
    _program_block(PROBE_SEED, PROGRAM_MIDDLE, "sparse p07 to p09")


def _t_program_sparse_late_exact():
    """POSITIVE: the program reproduces stages p10 to p14 of the sparse day."""
    _program_block(PROBE_SEED, PROGRAM_LATE, "sparse p10 to p14")


# --------------------------------------------------------------------------
# named wrong readings
#
# Each variant below is one documented decision read the other way. A detector
# asserts that the delivered bytes MATCH the wrong reading, so a delivery that
# read the decision correctly fails the assertion and escapes the penalty, and
# a delivery that produced nothing fails it too.
# --------------------------------------------------------------------------

_ORIG = {
    "read_ladder": read_ladder,
    "reserve_of": reserve_of,
    "crane_adjustment": crane_adjustment,
    "spill_candidates": spill_candidates,
    "dischargeable_wh": dischargeable_wh,
    "reconciliation_budget": reconciliation_budget,
    "quantise_share": quantise_share,
    "cell_key": cell_key,
    "ambient_multiplier": ambient_multiplier,
    "window_intervals": window_intervals,
    "declared_reading": declared_reading,
}


def _variant(tag, patches):
    """Recompute the shipped day with one decision read the other way."""
    key = "variant-" + tag
    cached = _STATE.get(key)
    if cached is not None:
        return cached
    data_dir, _ = _case(SAMPLE_SEED)
    out = _refroot() / ("variant_" + tag)
    if not out.is_dir():
        for name, fn in patches.items():
            globals()[name] = fn
        try:
            run_pipeline(data_dir, out)
        finally:
            for name in patches:
                globals()[name] = _ORIG[name]
    _STATE[key] = out
    return out


def _matches_variant(tag, patches, witnesses):
    out = _delivered()
    for name in witnesses:
        if not (out / name).is_file():
            raise AssertionError("no %s was delivered; this detector must stay "
                                 "silent" % name)
    ref_dir = _case(SAMPLE_SEED)[1]
    variant = _variant(tag, patches)
    differs = False
    for name in witnesses:
        if (variant / name).read_bytes() != (ref_dir / name).read_bytes():
            differs = True
    if not differs:
        raise AssertionError("the wrong reading of %s changes none of its "
                             "witnesses; this detector grades nothing" % tag)
    for name in witnesses:
        if (out / name).read_bytes() != (variant / name).read_bytes():
            return False
    return True


def _t_negative_weight_alphabetical_ladder_order():
    """NEGATIVE: the admission ladder was applied in the alphabetical order of
    its rung codes rather than the order dispatch_admission_ladder.txt prints.
    The assertion holds when the defect is present, so a delivery that read
    the printed order fails it and escapes the penalty."""
    assert _matches_variant(
        "alpha_ladder",
        {"read_ladder": lambda path: sorted(_ORIG["read_ladder"](path))},
        ["dispatch_priority_queue.csv", "final_schedule.csv",
         "reefer_service_certificate.csv"])


def _t_negative_weight_free_capacity_before_reserve():
    """NEGATIVE: the placements were reconciled against the whole nominal
    capacity, with the standing reserve of the feeder left in the free
    capacity rather than withheld before it. The assertion holds when the
    defect is present, so a delivery that withheld the reserve first fails it
    and escapes the penalty."""
    assert _matches_variant(
        "free_first",
        {"reserve_of": lambda data, feeder_id: 0},
        ["feeder_load_ledger.csv", "feeder_violation_ledger.csv",
         "spill_decisions.tsv"])


def _t_negative_weight_crane_demand_added_as_load():
    """NEGATIVE: the confirmed crane duty was carried as an extra load beside
    the reefer load rather than taken off the capacity left for reefers, so
    the published adjusted capacity is the reserved capacity untouched. The
    assertion holds when the defect is present, so a delivery that took the
    duty off the capacity fails it and escapes the penalty."""
    assert _matches_variant(
        "crane_as_load",
        {"crane_adjustment": lambda reserved, drawn: (reserved, "clear")},
        ["crane_adjusted_capacity.csv", "final_schedule_by_feeder.psv",
         "objective_vector.json"])


def _t_negative_weight_reconciliation_run_to_convergence():
    """NEGATIVE: the reconciliation was iterated until the shares stopped
    moving rather than for the number of passes the pass budget of
    dispatch_operations_memo.pdf allows. The assertion holds when the defect
    is present, so a delivery that stopped at the budget fails it and escapes
    the penalty."""
    assert _matches_variant(
        "convergence",
        {"reconciliation_budget": lambda controls: 400},
        ["reconciliation_iterations.csv", "final_schedule.csv",
         "reefer_service_certificate.csv"])


def _t_negative_weight_reconciliation_rounds_once():
    """NEGATIVE: the reconciliation carried exact shares through every pass
    and rounded once at the end instead of rounding at the end of every pass.
    The assertion holds when the defect is present, so a delivery that rounded
    per pass fails it and escapes the penalty."""
    assert _matches_variant(
        "round_last",
        {"quantise_share": lambda value, pass_number, budget:
             round_half_up(value) if pass_number == budget else value},
        ["reconciliation_iterations.csv", "final_schedule.csv",
         "unmet_requirement_report.tsv"])


def _t_negative_weight_spill_to_cheapest_interval():
    """NEGATIVE: a removed placement was spilled into the cheapest interval of
    the day rather than the next eligible one. The assertion holds when the
    defect is present, so a delivery that took the next eligible interval
    fails it and escapes the penalty."""
    def wrong(data, reefer_id, from_interval):
        bands = {"off_peak": 0, "shoulder": 1, "peak": 2, "super_peak": 3}
        pool = [m for m in data["lattice"][reefer_id] if m != from_interval]
        return sorted(pool, key=lambda m: (bands.get(
            data["grid"][m]["tariff_band"], 9), m))
    assert _matches_variant(
        "cheapest_spill",
        {"spill_candidates": wrong},
        ["spill_decisions.tsv", "final_schedule.csv",
         "feeder_load_ledger.csv"])


def _t_negative_weight_absent_ambient_read_as_zero():
    """NEGATIVE: a temperature class and ambient class pairing the multiplier
    table carries no row for was read as a multiplier of zero rather than the
    class default. The assertion holds when the defect is present, so a
    delivery that fell back to the class default fails it and escapes the
    penalty."""
    def wrong(data, temperature_class, ambient_class):
        if (temperature_class, ambient_class) in data["ambient_index"]:
            return data["ambient_index"][(temperature_class, ambient_class)]
        return Fraction(0, 1)
    assert _matches_variant(
        "zero_ambient",
        {"ambient_multiplier": wrong},
        ["energy_floor_ledger.csv", "final_schedule.csv"])


def _t_negative_weight_disconnect_boundary_opens_interval():
    """NEGATIVE: a disconnection landing exactly on an interval boundary was
    read as opening the interval that starts there rather than closing the one
    before it. The assertion holds when the defect is present, so a delivery
    that used the closing convention fails it and escapes the penalty."""
    def wrong(connect, disconnect):
        if disconnect < connect:
            return []
        first = max(1, interval_of(connect))
        last = min(INTERVAL_COUNT, interval_of(disconnect))
        if last < first:
            return []
        return list(range(first, last + 1))
    assert _matches_variant(
        "open_boundary",
        {"window_intervals": wrong},
        ["availability_lattice.csv", "energy_floor_ledger.csv",
         "final_schedule.csv"])


def _t_negative_weight_redistribution_across_the_feeder():
    """NEGATIVE: what a share ceiling freed was spread across the whole feeder
    rather than inside the cross classification of substation and service
    group. The assertion holds when the defect is present, so a delivery that
    redistributed inside the cell fails it and escapes the penalty."""
    assert _matches_variant(
        "flat_cell",
        {"cell_key": lambda data, rec: "one_cell"},
        ["reconciliation_iterations.csv", "reefer_service_certificate.csv"])


def _t_negative_weight_battery_discharges_at_reserve():
    """NEGATIVE: the battery was drawn through its reserve, so the state of
    charge available for discharge was read from the whole charge rather than
    from the charge standing above the reserve. The assertion holds when the
    defect is present, so a delivery that held the reserve back fails it and
    escapes the penalty."""
    assert _matches_variant(
        "reserve_drawn",
        {"dischargeable_wh": lambda soc, reserve, eff: floor_div(
            Fraction(soc * eff, 1000))},
        ["battery_schedule.csv", "soc_ledger.psv", "objective_vector.json"])


def _t_negative_weight_absent_declaration_read_as_zero():
    """NEGATIVE: an energy return carrying the not supplied marker was read as
    a declaration of zero rather than as a return declaring nothing. The
    assertion holds when the defect is present, so a delivery that defaulted
    to the mandatory floor fails it and escapes the penalty."""
    def wrong(ret, factor):
        if ret is not None and is_absent(ret.get("declared_value")):
            return 0
        return _ORIG["declared_reading"](ret, factor)
    assert _matches_variant(
        "zero_declaration",
        {"declared_reading": wrong},
        ["normalised_reefers.jsonl", "energy_floor_ledger.csv"])


# --------------------------------------------------------------------------
# cheat detectors
# --------------------------------------------------------------------------


def _code_without_comments(path):
    """The program source with comments removed, as str.

    A comment cannot make the program day dependent, so a sample row written
    in one is not the defect this detector is for. String literals are kept,
    because a day value hardcoded in one is exactly the defect. Uses the text
    tokenizer, whose untokenize returns str; the bytes tokenizer would return
    bytes and the membership test below would raise. If the source will not
    tokenize, fall back to scanning it whole rather than scanning nothing.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        kept = [t for t in tokenize.generate_tokens(io.StringIO(text).readline)
                if t.type != tokenize.COMMENT]
        stripped = tokenize.untokenize(kept)
    except Exception:
        return text
    if not isinstance(stripped, str):
        return text
    return stripped


def _names_this_day():
    """True when the delivered program source carries a value belonging to the
    shipped operating day alone.

    Only the day identifier and the day reference qualify. Both are unique to
    this day, so neither appears by accident. Feeder identifiers are
    deliberately NOT scanned: fd_01 and its neighbours occur in every
    operating day the verifier mints, so their presence in the source proves
    nothing about hardcoding, while a program that really did hardcode a
    feeder list is caught behaviourally by the two detectors below.
    """
    source = _code_without_comments(_program())
    planted = [_day_id(SAMPLE_SEED), _day_reference(SAMPLE_SEED)]
    return any(token in source for token in planted)


def _reproduces_only_the_shipped_day():
    """True when the delivery is right about the shipped day and the program,
    pointed at every day it has never seen, writes the shipped day's core
    documents back byte for byte. That is a replay of carried answers. A
    program that is merely wrong or crashes on the unseen days is an honest
    miss, already unpaid by the program blocks, and is not caught here. The
    hardcoded answer detector owns that defect."""
    try:
        _, shipped_ref = _case(SAMPLE_SEED)
        _compare(shipped_ref, _delivered(), FAMILY_CORE, "shipped")
    except AssertionError:
        return False
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None or record["failed"]:
            return False
        try:
            _compare(shipped_ref, record["out"], FAMILY_CORE, "replayed")
        except AssertionError:
            return False
    return True


def _t_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: the delivered program reproduces the shipped day and writes
    those same core bytes back on days it has never seen, so it carries
    answers rather than a derivation.
    The assertion holds when the defect is present."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    if _names_this_day():
        raise AssertionError("the program names this operating day; the "
                             "training corpus detector owns that defect")
    assert _reproduces_only_the_shipped_day()


def _t_negative_weight_reads_training_corpus_at_runtime():
    """NEGATIVE: the delivered program carries the shipped operating day
    inside it. Its source names this day identifier or its day reference,
    both of which the program contract requires it
    to read from the directory it is pointed at, so on another day it would be
    reading the training corpus rather than its input. The assertion holds
    when the defect is present, so a program that reads those values fails it
    and escapes the penalty."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    assert _names_this_day()


def _t_negative_weight_program_ignores_its_input():
    """NEGATIVE: the delivered program writes the same bytes whatever
    directory it is pointed at, so it is not reading its input. The assertion
    holds when the defect is present."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    if _names_this_day():
        raise AssertionError("the program names this operating day; the "
                             "training corpus detector owns that defect")
    if _reproduces_only_the_shipped_day():
        raise AssertionError("the program reproduces the shipped day "
                             "alone; the hardcoded answer detector owns "
                             "that defect")
    trees = []
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None or record["failed"]:
            raise AssertionError("the program produced nothing; the hardcoded "
                                 "answer detector owns that defect")
        trees.append(_digest_tree(record["out"]))
    assert all(tree == trees[0] for tree in trees)


def _t_negative_weight_nondeterministic_output():
    """NEGATIVE: two runs of the delivered program over one input directory
    disagree. The assertion holds when the defect is present."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    seed = MINTED_SEEDS[0]
    first = _case_output(seed)
    second = _case_output(seed, tag="repeat")
    if first is None or second is None or first["failed"] or second["failed"]:
        raise AssertionError("the program produced nothing; the hardcoded "
                             "answer detector owns that defect")
    assert _digest_tree(first["out"]) != _digest_tree(second["out"])


def _t_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: the delivered program writes different bytes when the same
    operating day is placed under another directory name. The assertion holds
    when the defect is present."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    seed = MINTED_SEEDS[0]
    record = _case_output(seed)
    if record is None or record["failed"]:
        raise AssertionError("the program produced nothing; the hardcoded "
                             "answer detector owns that defect")
    repeat = _case_output(seed, tag="repeat")
    if repeat is None or repeat["failed"]:
        raise AssertionError("the program produced nothing; the hardcoded "
                             "answer detector owns that defect")
    if _digest_tree(record["out"]) != _digest_tree(repeat["out"]):
        raise AssertionError("the program is not deterministic; the "
                             "nondeterministic output detector owns that "
                             "defect")
    data_dir, _ = _case(seed)
    renamed = _workroot() / "a_differently_named_yard"
    if not renamed.is_dir():
        shutil.copytree(str(data_dir), str(renamed))
        _relax(renamed)
    other = _workroot() / "renamed_out" / "published"
    try:
        _run_program(renamed, other)
    except AssertionError:
        assert True
        return
    assert _digest_tree(record["out"]) != _digest_tree(other)


def _t_negative_weight_program_dirties_its_directories():
    """NEGATIVE: the delivered program changed the directory it was pointed
    at, or wrote something into the output directory that is no declared
    document. The assertion holds when the defect is present."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    dirty = False
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None or record["failed"]:
            raise AssertionError("the program produced nothing; the hardcoded "
                                 "answer detector owns that defect")
        written = sorted(p.name for p in record["out"].iterdir())
        if set(written) & REBINDING_NAMES:
            raise AssertionError("the program planted a shadowing module; the "
                                 "rebinding detector owns that defect")
        if record["before"] != record["after"]:
            dirty = True
        if set(written) - set(ALL_ARTIFACTS):
            dirty = True
    assert dirty


def _t_negative_weight_rebinds_verifier_dependencies():
    """NEGATIVE: the delivered program plants a file that would shadow a
    module the verifier imports, so a later import inside the grading
    container would load agent code. The assertion holds when the defect is
    present."""
    planted = set()
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None or record["failed"]:
            raise AssertionError("the program produced nothing; the hardcoded "
                                 "answer detector owns that defect")
        planted |= {p.name for p in record["out"].iterdir()} & REBINDING_NAMES
    planted |= {p.name for p in _workroot().iterdir() if p.is_file()} & REBINDING_NAMES
    planted |= {p.name for p in _programcwd().iterdir() if p.is_file()} & REBINDING_NAMES
    planted |= {p.name for p in _delivered().iterdir() if p.is_file()} & REBINDING_NAMES
    assert planted


def _t_negative_weight_manifest_digest_mismatch():
    """NEGATIVE: the publication manifest disagrees with the bytes of every
    document delivered beside it, so the manifest was written from something
    other than the delivery. The assertion holds when the defect is
    present."""
    out = _delivered()
    target = out / "publication_manifest.json"
    if not target.is_file():
        raise AssertionError("no manifest was delivered; this detector must stay silent")
    try:
        manifest = json.loads(target.read_text(encoding="utf-8"))
    except ValueError:
        raise AssertionError("the manifest does not parse; this detector must "
                             "stay silent")
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise AssertionError("the manifest lists no document; this detector "
                             "must stay silent")
    checked = 0
    mismatched = 0
    for entry in documents:
        if not isinstance(entry, dict):
            continue
        beside = out / str(entry.get("name"))
        if not beside.is_file():
            continue
        checked += 1
        if hashlib.sha256(beside.read_bytes()).hexdigest() != entry.get("sha256"):
            mismatched += 1
    assert checked > 0 and mismatched == checked


# --------------------------------------------------------------------------
# corpus regeneration entry point
# --------------------------------------------------------------------------


# Every outcome corpus_sentinel_note.txt names as unreached by the shipped day,
# with the minted day that does reach it. The note tells the agent to implement
# these from their specifications, so grading has to exercise them somewhere or
# the requirement is unverifiable.
SENTINEL_COVERAGE = {
    "BATTERY_BELOW_RESERVE": EVAL_SEED,
    "DR_STATE_UNKNOWN": EVAL_SEED,
    "POOL_FULLY_ALLOCATED": EVAL_SEED,
    "CHARGE_NO_ROOM": CHALLENGE_SEED,
    "CYCLE_CLOSE_SETTLED": CHALLENGE_SEED,
    "PEAK_ON_A_BAND_FLOOR": CHALLENGE_SEED,
    "YARD_PEAK_TIE": PROBE_SEED,
}

# SHARE_STEP_DOWNWARD is deliberately absent, and it is the one outcome no
# fixture can construct. The downward half of RULE P09.i cannot fire under the
# algorithm the stage specifications define: a share opens at zero and is held
# in [0, limit] at the close of every pass; RULE P09.e sets the target to the
# standing share plus a non negative portion of the unallocated pool; RULE
# P09.f only ever cuts the target down to the limit, which the share never
# exceeds; RULE P09.g only adds. So the target is never below the standing
# share, the damped move is never downward, and the step is never negative.
# The branch is vacuous rather than unfixtured, so it is recorded here instead
# of being chased, and solution/TRUTH.md carries the same reasoning.
SENTINEL_INERT = {"SHARE_STEP_DOWNWARD"}


def _outcomes_reached(data, ref_dir):
    """Which sentinel outcomes one recomputed operating day reaches, read from
    the documents it published rather than from the papers it was given.

    That distinction is the whole point. A day can carry the condition in its
    input while every reading of the rule produces the same published bytes, in
    which case the rule is not graded at all. Each probe below therefore reads a
    value the publication carries, so any other reading of its rule changes the
    bytes a block compares and costs reward.
    """
    ref = Path(ref_dir)
    got = set()

    soc = ref.joinpath("soc_ledger.psv").read_text(encoding="utf-8")
    if any(line.endswith("|below_reserve") for line in soc.split("\n")):
        got.add("BATTERY_BELOW_RESERVE")

    battery = ref.joinpath("battery_schedule.csv").read_text(encoding="utf-8")
    if any(line.endswith(",no_room") for line in battery.split("\n")):
        got.add("CHARGE_NO_ROOM")
    if any(line.endswith(",capacity_limit") for line in battery.split("\n")):
        got.add("CHARGE_AT_CAPACITY")
    if any(line.endswith(",headroom_limit") for line in battery.split("\n")):
        got.add("CHARGE_AT_HEADROOM")

    cycle = json.loads(ref.joinpath("cycle_break_report.json").read_text(
        encoding="utf-8"))
    if cycle["closing_state"] == "settled" and cycle["settled_at_sweep"] > 0:
        got.add("CYCLE_CLOSE_SETTLED")

    # The published band code of a substation whose peak sits exactly on that
    # band's floor. Reading the floor as exclusive publishes a different band.
    certificate = json.loads(ref.joinpath("peak_demand_certificate.json")
                             .read_text(encoding="utf-8"))
    for entry in certificate["substations"]:
        if entry["peak_w"] <= 0:
            continue
        for row in data["band_rows"]:
            if (row.get("substation_id") == entry["substation_id"]
                    and row.get("band_code") == entry["band_code"]
                    and row.get("record_state") in APPLICABLE_STATES
                    and as_int(row["floor_w"]) == entry["peak_w"]):
                got.add("PEAK_ON_A_BAND_FLOOR")

    # Two intervals carry the published yard peak and the earlier one is the
    # certified interval. Settling the tie the other way publishes the later.
    peak = certificate["yard_peak_w"]
    tied = sorted(n for n, load in data["yard_load"].items() if load == peak)
    if peak > 0 and len(tied) > 1 and certificate["yard_peak_interval"] == tied[0]:
        got.add("YARD_PEAK_TIE")

    # A published pass whose feeder day pool is exhausted while a member still
    # needs energy, so the target had to be held at the standing share. The
    # proportional formula would publish a lower target.
    pool = {}
    for feeder in data["feeder_list"]:
        total = 0
        for n in range(1, INTERVAL_COUNT + 1):
            total += max(0, data["adjusted_capacity"][(feeder, n)]
                         + data["battery_support"].get((feeder, n), 0)
                         - data["reconciled_load"][(feeder, n)])
        pool[feeder] = floor_div(Fraction(total, 4))
    groups = {}
    for row in read_delim(ref / "reconciliation_iterations.csv", ","):
        groups.setdefault((row["pass"], row["feeder_id"]), []).append(row)
    for (_, feeder), rows in groups.items():
        standing = sum(as_int(r["opening_share_wh"]) for r in rows)
        if (pool.get(feeder, 0) - standing <= 0
                and any(as_int(r["need_wh"]) > 0 for r in rows)
                and all(as_int(r["target_wh"]) == as_int(r["opening_share_wh"])
                        for r in rows)):
            got.add("POOL_FULLY_ALLOCATED")

    # A register row carrying a record state neither list of
    # revision_precedence.toml names, set aside under RULE P01.b even though it
    # holds the highest sequence of its key, and differing from the row that
    # does govern in a field the publication carries.
    published = {}
    for line in ref.joinpath("normalised_reefers.jsonl").read_text(
            encoding="utf-8").split("\n"):
        if line:
            record = json.loads(line)
            published[record["reefer_id"]] = record
    for row in data["reefer_rows"]:
        if row.get("day_id") != data["day_id"]:
            continue
        state = row.get("record_state")
        if state in APPLICABLE_STATES or state in SET_ASIDE_STATES:
            continue
        record = published.get(row["reefer_id"])
        if record is not None and record["connect_minute"] != as_int(
                row["connect_minute"]):
            got.add("DR_STATE_UNKNOWN")

    for row in read_delim(ref / "reconciliation_iterations.csv", ","):
        if as_int(row["closing_share_wh"]) < as_int(row["opening_share_wh"]):
            got.add("SHARE_STEP_DOWNWARD")
    return got


def assert_branch_coverage():
    """Preflight: every sentinel outcome that can be reached is reached by a
    graded day, in its published documents. Nothing agent produced is touched
    here, so this belongs to the preflight phase and may abort without writing
    a reward."""
    reached = {}
    for seed in MINTED_SEEDS:
        data_dir, ref_dir = _case(seed)
        probe = Path(tempfile.mkdtemp()) / "coverage"
        reached[seed] = _outcomes_reached(run_pipeline(data_dir, probe), ref_dir)
        shutil.rmtree(probe.parent, ignore_errors=True)
    union = set()
    for got in reached.values():
        union |= got
    missing = sorted(set(SENTINEL_COVERAGE) - union)
    if missing:
        raise RuntimeError(
            "sentinel outcomes reached by no graded day: %s" % ", ".join(missing))
    misplaced = sorted(name for name, seed in SENTINEL_COVERAGE.items()
                       if name not in reached.get(seed, set()))
    if misplaced:
        raise RuntimeError(
            "sentinel outcomes no longer reached by the day recorded for them: %s"
            % ", ".join(misplaced))
    stale = sorted(SENTINEL_INERT & union)
    if stale:
        raise RuntimeError(
            "outcomes recorded as inert are now reachable, so the reasoning in "
            "SENTINEL_INERT is wrong: %s" % ", ".join(stale))


def _write_corpus(root):
    """Regenerate the shipped working papers under the data directory.

    The contents are cleared rather than the directory itself, so a shell
    sitting inside it does not block the regeneration.
    """
    target = Path(root) / "data"
    if target.exists():
        for item in target.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    mint_corpus(SAMPLE_SEED, SEED_PROFILE[SAMPLE_SEED], target)



# --------------------------------------------------------------------------
# rewardkit registration
#
# rewardkit runs criteria on worker threads. The checks share one cache of
# minted days and the variant detectors rebind module globals while they
# recompute, so every check runs under one lock. A check returns True when
# its assertion held: a positive property was earned, or a negative defect
# was seen. Any exception, from bad or missing output alike, returns False.
# --------------------------------------------------------------------------

_GRADE_LOCK = threading.Lock()


def _holds(check) -> bool:
    with _GRADE_LOCK:
        try:
            check()
        except Exception:
            return False
        return True

@criterion(description="every declared document and the program are present.")
def all_artifacts_exist(workspace: Path) -> bool:
    return _holds(_t_all_artifacts_exist)

@criterion(description="the spine documents parse as the shapes the contract names.")
def core_documents_parse(workspace: Path) -> bool:
    return _holds(_t_core_documents_parse)

@criterion(description="the shipped normalisation and lattice documents are byte exact.")
def shipped_p01_p02_exact(workspace: Path) -> bool:
    return _holds(_t_shipped_p01_p02_exact)

@criterion(description="the shipped energy floor and queue documents are byte exact.")
def shipped_p03_p04_exact(workspace: Path) -> bool:
    return _holds(_t_shipped_p03_p04_exact)

@criterion(description="the shipped allocation, reserve and spill documents are byte exact.")
def shipped_p05_p06_exact(workspace: Path) -> bool:
    return _holds(_t_shipped_p05_p06_exact)

@criterion(description="the shipped crane, battery and pass documents are byte exact.")
def shipped_p07_p09_exact(workspace: Path) -> bool:
    return _holds(_t_shipped_p07_p09_exact)

@criterion(description="the shipped tariff, correction and publication documents are byte exact.")
def shipped_p10_p14_exact(workspace: Path) -> bool:
    return _holds(_t_shipped_p10_p14_exact)

@criterion(description="the program reproduces stages p01 to p06 of the strained day.")
def program_strained_early_exact(workspace: Path) -> bool:
    return _holds(_t_program_strained_early_exact)

@criterion(description="the program reproduces stages p07 to p09 of the strained day.")
def program_strained_middle_exact(workspace: Path) -> bool:
    return _holds(_t_program_strained_middle_exact)

@criterion(description="the program reproduces stages p10 to p14 of the strained day.")
def program_strained_late_exact(workspace: Path) -> bool:
    return _holds(_t_program_strained_late_exact)

@criterion(description="the program reproduces stages p01 to p06 of the wide day.")
def program_wide_early_exact(workspace: Path) -> bool:
    return _holds(_t_program_wide_early_exact)

@criterion(description="the program reproduces stages p07 to p09 of the wide day.")
def program_wide_middle_exact(workspace: Path) -> bool:
    return _holds(_t_program_wide_middle_exact)

@criterion(description="the program reproduces stages p10 to p14 of the wide day.")
def program_wide_late_exact(workspace: Path) -> bool:
    return _holds(_t_program_wide_late_exact)

@criterion(description="the program reproduces stages p01 to p06 of the sparse day.")
def program_sparse_early_exact(workspace: Path) -> bool:
    return _holds(_t_program_sparse_early_exact)

@criterion(description="the program reproduces stages p07 to p09 of the sparse day.")
def program_sparse_middle_exact(workspace: Path) -> bool:
    return _holds(_t_program_sparse_middle_exact)

@criterion(description="the program reproduces stages p10 to p14 of the sparse day.")
def program_sparse_late_exact(workspace: Path) -> bool:
    return _holds(_t_program_sparse_late_exact)

@criterion(description="the admission ladder was applied in the alphabetical order of its rung codes rather than the order dispatch_admission_ladder.txt prints.")
def negative_alphabetical_ladder_order(workspace: Path) -> bool:
    return _holds(_t_negative_weight_alphabetical_ladder_order)

@criterion(description="the placements were reconciled against the whole nominal capacity, with the standing reserve of the feeder left in the free capacity rather than withheld before it.")
def negative_free_capacity_before_reserve(workspace: Path) -> bool:
    return _holds(_t_negative_weight_free_capacity_before_reserve)

@criterion(description="the confirmed crane duty was carried as an extra load beside the reefer load rather than taken off the capacity left for reefers, so the published adjusted capacity is the reserved capacity untouched.")
def negative_crane_demand_added_as_load(workspace: Path) -> bool:
    return _holds(_t_negative_weight_crane_demand_added_as_load)

@criterion(description="the reconciliation was iterated until the shares stopped moving rather than for the number of passes the pass budget of dispatch_operations_memo.pdf allows.")
def negative_reconciliation_run_to_convergence(workspace: Path) -> bool:
    return _holds(_t_negative_weight_reconciliation_run_to_convergence)

@criterion(description="the reconciliation carried exact shares through every pass and rounded once at the end instead of rounding at the end of every pass.")
def negative_reconciliation_rounds_once(workspace: Path) -> bool:
    return _holds(_t_negative_weight_reconciliation_rounds_once)

@criterion(description="the delivered program carries the shipped operating day inside it. Its source names this day identifier, its day reference or one of its feeder identifiers, all of which the program contract requires it to read from the directory it is pointed at, so on another day it would be reading the training corpus rather than its input.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    return _holds(_t_negative_weight_reads_training_corpus_at_runtime)

@criterion(description="a removed placement was spilled into the cheapest interval of the day rather than the next eligible one.")
def negative_spill_to_cheapest_interval(workspace: Path) -> bool:
    return _holds(_t_negative_weight_spill_to_cheapest_interval)

@criterion(description="a temperature class and ambient class pairing the multiplier table carries no row for was read as a multiplier of zero rather than the class default.")
def negative_absent_ambient_read_as_zero(workspace: Path) -> bool:
    return _holds(_t_negative_weight_absent_ambient_read_as_zero)

@criterion(description="a disconnection landing exactly on an interval boundary was read as opening the interval that starts there rather than closing the one before it.")
def negative_disconnect_boundary_opens_interval(workspace: Path) -> bool:
    return _holds(_t_negative_weight_disconnect_boundary_opens_interval)

@criterion(description="what a share ceiling freed was spread across the whole feeder rather than inside the cross classification of substation and service group.")
def negative_redistribution_across_the_feeder(workspace: Path) -> bool:
    return _holds(_t_negative_weight_redistribution_across_the_feeder)

@criterion(description="the battery was drawn through its reserve, so the state of charge available for discharge was read from the whole charge rather than from the charge standing above the reserve.")
def negative_battery_discharges_at_reserve(workspace: Path) -> bool:
    return _holds(_t_negative_weight_battery_discharges_at_reserve)

@criterion(description="an energy return carrying the not supplied marker was read as a declaration of zero rather than as a return declaring nothing.")
def negative_absent_declaration_read_as_zero(workspace: Path) -> bool:
    return _holds(_t_negative_weight_absent_declaration_read_as_zero)

@criterion(description="the delivered program reproduces the shipped day and fails on days it has never seen, so it carries answers rather than a derivation.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_t_negative_weight_hardcoded_sample_answers)

@criterion(description="the delivered program writes the same bytes whatever directory it is pointed at, so it is not reading its input.")
def negative_program_ignores_its_input(workspace: Path) -> bool:
    return _holds(_t_negative_weight_program_ignores_its_input)

@criterion(description="two runs of the delivered program over one input directory disagree.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _holds(_t_negative_weight_nondeterministic_output)

@criterion(description="the delivered program writes different bytes when the same operating day is placed under another directory name.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    return _holds(_t_negative_weight_filename_dependent_behaviour)

@criterion(description="the delivered program changed the directory it was pointed at, or wrote something into the output directory that is no declared document.")
def negative_program_dirties_its_directories(workspace: Path) -> bool:
    return _holds(_t_negative_weight_program_dirties_its_directories)

@criterion(description="the delivered program plants a file that would shadow a module the verifier imports, so a later import inside the grading container would load agent code.")
def negative_rebinds_verifier_dependencies(workspace: Path) -> bool:
    return _holds(_t_negative_weight_rebinds_verifier_dependencies)

@criterion(description="the publication manifest disagrees with the bytes of every document delivered beside it, so the manifest was written from something other than the delivery.")
def negative_manifest_digest_mismatch(workspace: Path) -> bool:
    return _holds(_t_negative_weight_manifest_digest_mismatch)


criteria.all_artifacts_exist(weight=1)
criteria.core_documents_parse(weight=1)
criteria.shipped_p01_p02_exact(weight=3)
criteria.shipped_p03_p04_exact(weight=3)
criteria.shipped_p05_p06_exact(weight=3)
criteria.shipped_p07_p09_exact(weight=3)
criteria.shipped_p10_p14_exact(weight=3)
criteria.program_strained_early_exact(weight=5)
criteria.program_strained_middle_exact(weight=5)
criteria.program_strained_late_exact(weight=5)
criteria.program_wide_early_exact(weight=5)
criteria.program_wide_middle_exact(weight=5)
criteria.program_wide_late_exact(weight=5)
criteria.program_sparse_early_exact(weight=5)
criteria.program_sparse_middle_exact(weight=5)
criteria.program_sparse_late_exact(weight=5)
criteria.negative_alphabetical_ladder_order(weight=-3)
criteria.negative_free_capacity_before_reserve(weight=-3)
criteria.negative_crane_demand_added_as_load(weight=-3)
criteria.negative_reconciliation_run_to_convergence(weight=-3)
criteria.negative_reconciliation_rounds_once(weight=-3)
criteria.negative_reads_training_corpus_at_runtime(weight=-3)
criteria.negative_spill_to_cheapest_interval(weight=-3)
criteria.negative_absent_ambient_read_as_zero(weight=-3)
criteria.negative_disconnect_boundary_opens_interval(weight=-3)
criteria.negative_redistribution_across_the_feeder(weight=-3)
criteria.negative_battery_discharges_at_reserve(weight=-3)
criteria.negative_absent_declaration_read_as_zero(weight=-3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_program_ignores_its_input(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_program_dirties_its_directories(weight=-3)
criteria.negative_rebinds_verifier_dependencies(weight=-3)
criteria.negative_manifest_digest_mismatch(weight=-3)


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))
