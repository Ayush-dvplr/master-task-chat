"""Deterministic verifier for the Ninefold Crown settlement recompute task.

The verifier owns its corpus. It regenerates the whole working paper tree from a
named seed into a temporary directory, recomputes every settlement document from
that regeneration, and grades the agent bytes under the output directory against
it. It never reads the agent corpus, which does not exist in this container.

Most of the positive weight is spent on the delivered program rather than on the
delivered bytes. Three further events are minted here from seeds the agent never
sees, one under a contested profile, one under a wide profile and one under a
thin profile the shipped event does not use, and the delivered settlement
program is run against each of them as a subprocess. Its output is graded byte
for byte against the settlement those papers entail. Each minted event carries
its own memorandum constants, directive key positions, division ranks and unit
conversion, so the program has to read the office papers it is pointed at.

The grading tree is split three ways so that the recomputed reference is never
reachable from the directory the graded program is handed: minted papers and the
program output directories live under a traversable work root, every recomputed
reference lives under a second root that stays root owned and unreadable to the
dropped child, and the program is run from its own empty directory.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from rewardkit import criteria, criterion

PROGRAM_NAME = "crownsettle.py"

# Grading launches the delivered program seven times: once per minted event, once
# more on the first event for the determinism detector, once on a renamed copy
# for the filename detector, once on a corpus missing a required paper and once
# on the shipped event re-minted under another identity for the replayer
# detector. Seven of these plus corpus minting have to finish inside [verifier]
# timeout_sec, which is 5400. The honest path finishes a run in seconds, so 600
# leaves orders of magnitude of headroom and still totals 4200 against the budget.
PROGRAM_TIMEOUT = 600

# The identity the replayer detector re-mints the shipped event under: an event
# identifier and reference that name neither the shipped event nor any of its
# prior references, and a player identifier prefix that replaces PL- on every
# identifier. Every identifier keeps its prefix, so their order is unchanged.
RENAMED_IDENTITY = ("EV-3C1D", "NC-4417-K6", "PM-")
PLAYER_PREFIX = "PL-"

BACKSLASH = chr(92)

DIVISIONS = ["dv_arbor", "dv_brine", "dv_cinder", "dv_dune"]

# One published observable per stage. Each family below is compared on its own
# documents and nothing else. A slip confined to the closing stages costs only
# the family its documents sit in; a stage of the round loop or of the entry
# and participation stages read the wrong way moves every round after it, as
# the overview paper states, and so every family downstream of it.
#
# The settlement manifest carries a digest of every other delivered document, so
# a one byte difference anywhere moves it. It is therefore never compared byte
# for byte against the reference; it is graded on whether it describes the
# documents delivered beside it, which a wrong document elsewhere leaves intact.
FAMILY_CORE = [
    "normalised_entries.jsonl",
    "participation_ledger.csv",
    "round_match_candidates.csv",
    "match_result_ledger.csv",
    "round_eligibility_ledger.csv",
    "bye_ledger.csv",
    "authoritative_pairing_ledger.csv",
    "void_adjudication_ledger.csv",
    "round_score_ledger.csv",
    "penalty_application_ledger.psv",
    "opponent_history_ledger.csv",
    "opponent_strength_ledger.csv",
    "standings_ledger.csv",
]

FAMILY_PAIRING = [
    "pairing_fallback_ledger.csv",
    "repeat_opponent_audit.tsv",
    "unpaired_ledger.tsv",
    "pairing_constraint_report.json",
]

FAMILY_STANDINGS = [
    "game_differential_ledger.psv",
    "tiebreak_resolution_ledger.csv",
    "final_ranking.json",
    "player_audit_trace.jsonl",
]

FAMILY_SETTLEMENT = [
    "prize_allocation_ledger.csv",
    "prize_tie_split.tsv",
    "standings_by_division.xml",
    "settlement_control_totals.conf",
    "event_settlement_summary.md",
    "division_report_dv_arbor.json",
    "division_report_dv_brine.json",
    "division_report_dv_cinder.json",
    "division_report_dv_dune.json",
    "settlement_manifest.json",
]

# FAMILY_SETTLEMENT fixes the artifact contract order the P14 specification
# prints. It is graded in two halves, neither of which holds the manifest.
FAMILY_PRIZE = [
    "prize_allocation_ledger.csv",
    "prize_tie_split.tsv",
    "division_report_dv_arbor.json",
    "division_report_dv_brine.json",
    "division_report_dv_cinder.json",
    "division_report_dv_dune.json",
]

FAMILY_PUBLICATION = [
    "standings_by_division.xml",
    "settlement_control_totals.conf",
    "event_settlement_summary.md",
]

ALL_DOCUMENTS = FAMILY_CORE + FAMILY_PAIRING + FAMILY_STANDINGS + FAMILY_SETTLEMENT

# The six documents the core digest of the settlement manifest covers.
CORE_DOCUMENTS = [
    "normalised_entries.jsonl",
    "match_result_ledger.csv",
    "authoritative_pairing_ledger.csv",
    "round_score_ledger.csv",
    "opponent_strength_ledger.csv",
    "standings_ledger.csv",
]

SAMPLE_SEED = 5518274093
EVAL_SEED = 6710482351
CHALLENGE_SEED = 7823591744
PROBE_SEED = 8934610285

SEED_PROFILE = {
    SAMPLE_SEED: "shipped",
    EVAL_SEED: "contested",
    CHALLENGE_SEED: "wide",
    PROBE_SEED: "thin",
}

MINTED_SEEDS = [EVAL_SEED, CHALLENGE_SEED, PROBE_SEED]

# The shipped event reaches neither the reinstate branch of P02 nor the voided
# exclusion of P01, and corpus_sentinel_note.txt tells the agent so. Both rules
# are normative, so both are given a triggering row on this minted profile: no
# graded input would otherwise come out differently if a solver left either
# branch out, which would leave the two rules stated but ungraded.
BRANCH_FIXTURE_PROFILE = "contested"

ABSENT = "--"

# --------------------------------------------------------------------------
# delimited and structured writers
# --------------------------------------------------------------------------


def _join(sep, values):
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


def _cell_ref(col, row):
    name = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        name = chr(65 + rem) + name
    return "%s%d" % (name, row)


def _xml_escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;"))


def _sheet_xml(rows, shared, shared_idx):
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


def write_xlsx(path, sheets):
    shared = []
    shared_idx = {}
    sheet_xmls = [(name, _sheet_xml(rows, shared, shared_idx)) for name, rows in sheets.items()]

    ss = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ss.append('<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              'count="%d" uniqueCount="%d">' % (len(shared), len(shared)))
    for item in shared:
        ss.append('<si><t xml:space="preserve">%s</t></si>' % _xml_escape(item))
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


def _docx_paragraph(text):
    return ('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % _xml_escape(text))


def _docx_table(rows):
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


def write_docx(path, blocks):
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


def write_pdf(path, lines):
    def esc(t):
        return (t.replace(BACKSLASH, BACKSLASH + BACKSLASH)
                 .replace("(", BACKSLASH + "(")
                 .replace(")", BACKSLASH + ")"))

    pages = [lines[i:i + 52] for i in range(0, len(lines), 52)] or [[""]]
    objects = []
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


def write_sqlite(path, tables):
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
# exact arithmetic the whole derivation runs on
# --------------------------------------------------------------------------


def round_half_even(value):
    """Round a Fraction or int to the nearest integer, ties to the even side."""
    frac = Fraction(value)
    floor = frac.numerator // frac.denominator
    rest = frac - floor
    if rest < Fraction(1, 2):
        return floor
    if rest > Fraction(1, 2):
        return floor + 1
    return floor if floor % 2 == 0 else floor + 1


def scaled(numerator, denominator, value):
    """Convert a quoted value into its base unit through a register entry."""
    return round_half_even(Fraction(int(value) * int(numerator), int(denominator)))


def nine_places(numerator, denominator):
    """A ratio published at exactly nine decimal places, half to even."""
    if int(denominator) == 0:
        return "0.000000000"
    scaled_value = round_half_even(Fraction(int(numerator) * 10 ** 9, int(denominator)))
    sign = "-" if scaled_value < 0 else ""
    scaled_value = abs(scaled_value)
    whole, rest = divmod(scaled_value, 10 ** 9)
    return "%s%d.%09d" % (sign, whole, rest)


def as_int(value, default=0):
    text = str(value).strip()
    if not text or text == ABSENT:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def is_absent(value):
    text = str(value).strip()
    return text == "" or text == ABSENT


# --------------------------------------------------------------------------
# closed vocabularies
# --------------------------------------------------------------------------

RATING_UNITS = [
    ("rating_point", 1000, 1),
    ("milli_rating", 1, 1),
    ("centi_point", 10, 1),
    ("decipoint", 100, 1),
    ("crown_grade", 2500, 9),
]

MODIFIER_CODES = [
    ("MOD_STD", 1, 1),
    ("MOD_HALF", 1, 2),
    ("MOD_DOUBLE", 2, 1),
    ("MOD_THREE_HALVES", 3, 2),
    ("MOD_FOUR_THIRDS", 4, 3),
]

RESULT_CODES = ["win_a", "win_b", "draw", "double_loss"]

VOID_REASONS = [
    "ineligible_player",
    "holds_bye",
    "cross_division",
    "repeat_opponent",
    "score_band",
]

RELAXATION_RUNGS = ["score_band", "repeat_opponent", "division"]

PENALTY_CLASSES = ["game", "match", "round", "tournament"]

SHADOW_DIVISION = "dv_ember"

PROFILE = {
    "shipped": {
        "rounds": 9,
        "ticks": 120,
        "counts": {"dv_arbor": 87, "dv_brine": 68, "dv_cinder": 3, "dv_dune": 0},
        "shadow": 5,
        "score_band": 3,
        "max_byes": 2,
        "pool_cents": 1284500,
        "strength_debit": 40,
    },
    "contested": {
        "rounds": 9,
        "ticks": 90,
        "counts": {"dv_arbor": 74, "dv_brine": 0, "dv_cinder": 61, "dv_dune": 9},
        "shadow": 4,
        "score_band": 2,
        "max_byes": 2,
        "pool_cents": 976300,
        "strength_debit": 55,
    },
    "wide": {
        "rounds": 11,
        "ticks": 150,
        "counts": {"dv_arbor": 52, "dv_brine": 47, "dv_cinder": 44, "dv_dune": 41},
        "shadow": 6,
        "score_band": 4,
        "max_byes": 3,
        "pool_cents": 2141750,
        "strength_debit": 25,
    },
    "thin": {
        "rounds": 7,
        "ticks": 120,
        "counts": {"dv_arbor": 31, "dv_brine": 1, "dv_cinder": 0, "dv_dune": 26},
        "shadow": 3,
        "score_band": 3,
        "max_byes": 1,
        "pool_cents": 613200,
        "strength_debit": 70,
    },
}

# Policy values the program contract requires the delivered program to read
# rather than hold. The shipped event keeps the canonical values; each unseen
# event moves some of them, so a program that holds the shipped values settles
# the shipped event and no other.
CANONICAL_SHARE_TABLE = [2600, 1800, 1300, 950, 720, 560, 430, 340, 260, 200,
                         150, 120, 100, 80, 60, 40]

CANONICAL_POLICY = {
    "points": (3, 1, 0),
    "tolerance": (0, 3, 3),
    "rungs": ["score_band", "repeat_opponent", "division"],
    "share_table": CANONICAL_SHARE_TABLE,
    "default_rating": (1200000, 40000),
    "seated_status": "seated",
}

PROFILE_POLICY = {
    "contested": {"points": (3, 1, 1), "tolerance": (0, 3, 2)},
    "wide": {"points": (4, 2, 0),
             "share_table": [2400, 1700, 1250, 1000, 800, 620, 480, 380, 300,
                             240, 190, 150, 120, 100, 80, 60],
             "default_rating": (1150000, 55000),
             "seated_status": "provisional"},
    "thin": {"tolerance": (1, 2, 3),
             "rungs": ["repeat_opponent", "score_band", "division"],
             "default_rating": (1180000, 30000)},
}

RUNG_PHRASE = {
    "score_band": "the score band",
    "repeat_opponent": "the prior opponent test",
    "division": "the division test",
}


def _event_id(seed):
    return "EV-%04X" % (seed % 0xFFFF)


def _event_reference(seed):
    return "NC-%04d-%s%d" % (seed % 9000 + 1000, chr(65 + seed % 23), seed % 7 + 2)


def _prior_references(seed, n):
    out = []
    for i in range(n):
        out.append("NC-%04d-%s%d" % ((seed // (7 + i)) % 9000 + 1000,
                                     chr(65 + (seed // (3 + i)) % 23),
                                     (seed // (11 + i)) % 7 + 2))
    return out


# --------------------------------------------------------------------------
# instance identity and roster
# --------------------------------------------------------------------------


def _with_prefix(value, prefix):
    """value with every string that opens on PLAYER_PREFIX opened on prefix
    instead, through nested lists, tuples, sets and dicts."""
    if isinstance(value, str):
        return prefix + value[len(PLAYER_PREFIX):] if value.startswith(PLAYER_PREFIX) else value
    if isinstance(value, list):
        return [_with_prefix(item, prefix) for item in value]
    if isinstance(value, tuple):
        return tuple(_with_prefix(item, prefix) for item in value)
    if isinstance(value, set):
        return {_with_prefix(item, prefix) for item in value}
    if isinstance(value, dict):
        return {_with_prefix(k, prefix): _with_prefix(v, prefix) for k, v in value.items()}
    return value


def mint_instance(seed, profile, identity=None):
    """identity, when given, is an (event_id, event_reference, player_prefix)
    triple that replaces the identity the seed would mint and the prefix of every
    player identifier. Nothing the generator draws depends on either, and the
    prefix is shared by every identifier, so the papers differ from the seed's
    own only in those strings and every order among identifiers is kept."""
    cfg = PROFILE[profile]
    rng = Rng(seed ^ 0x4E494E45)
    event_id, event_reference = (identity[:2] if identity
                                 else (_event_id(seed), _event_reference(seed)))
    policy = dict(CANONICAL_POLICY)
    policy.update(PROFILE_POLICY.get(profile, {}))
    inst = {
        "seed": seed,
        "profile": profile,
        "event_id": event_id,
        "event_reference": event_reference,
        "policy": policy,
        "rounds": cfg["rounds"],
        "ticks": cfg["ticks"],
        "counts": dict(cfg["counts"]),
        "shadow_count": cfg["shadow"],
        "score_band": cfg["score_band"],
        "max_byes": cfg["max_byes"],
        "pool_cents": cfg["pool_cents"],
        "strength_debit": cfg["strength_debit"],
        "prior_references": _prior_references(seed, 3),
        "rng": rng,
    }
    _mint_office_values(inst)
    _mint_players(inst, rng)
    _mint_roster_papers(inst, rng)
    _mint_configuration(inst, rng)
    _mint_status_journal(inst, rng)
    _mint_penalties(inst, rng)
    _mint_recorded_event(inst, rng)
    _mint_appeals(inst, rng)
    _mint_decoys(inst, rng)
    if profile == BRANCH_FIXTURE_PROFILE:
        _mint_precedence_fixtures(inst)
    if identity:
        for key, value in list(inst.items()):
            if key != "rng":
                inst[key] = _with_prefix(value, identity[2])
    return inst


def _mint_precedence_fixtures(inst):
    """Two notice fixtures the generator's draws never produce, appended after
    every draw so the rest of the corpus keeps its bytes.

    An expulsion against an entrant whose standing lapsed in the same round, so
    the rule that an expulsion outranks a lapsed standing decides a graded row.
    And three applied classes against one entrant in one round, two of them of
    the game class, so the summed magnitude, the lowest notice sequence and the
    applied class order of the penalty ledger each decide a graded row."""
    ref = inst["event_reference"]
    seq = max(int(row[5]) for row in inst["penalty_rows"])
    noticed = {row[1] for row in inst["penalty_rows"] if row[0] == ref}
    expelled = {pid for pid, _r in inst["expelled_players"]}
    lapsed = [(pid, r) for pid, r in inst["lapsed_players"]
              if pid not in expelled and pid not in noticed]
    if lapsed:
        pid, round_no = lapsed[0]
        seq += 1
        inst["penalty_rows"].append([ref, pid, "expulsion", 0, round_no, seq, "served"])
        inst["expelled_players"] = sorted(inst["expelled_players"] + [(pid, round_no)])
        noticed.add(pid)
        inst["expelled_lapsed_player"] = (pid, round_no)

    moved = {row[1] for row in inst["status_rows"] if row[0] == ref}
    barred = {pid for pid, _r in inst["lapsed_players"]} | expelled
    steady = sorted(p["pid"] for p in _journal_pool(inst)
                    if p["pid"] not in moved | barred | noticed
                    and p["pid"] != inst.get("voided_entry_player"))
    division_of = {p["pid"]: p["division"] for p in inst["players"]}
    if steady:
        pid = steady[0]
        # The round is one whose modifier is not the identity, so that with the
        # nonzero loss points of this profile the match penalty landing before
        # the modifier decides a graded row rather than commuting with it.
        modified_rounds = sorted(int(row[1]) for row in inst["round_config_rows"]
                                 if row[0] == ref and row[2] == division_of[pid]
                                 and row[3] == "modifier_code" and row[4] != "MOD_STD"
                                 and int(row[1]) >= 2)
        stacked_round = modified_rounds[0] if modified_rounds else 2
        for cls, magnitude in (("round", 2), ("game", 2), ("match", 1), ("game", 1)):
            seq += 1
            inst["penalty_rows"].append([ref, pid, cls, magnitude, stacked_round, seq,
                                         "served"])
        inst["stacked_notice_player"] = pid
        inst["stacked_notice_round"] = stacked_round

    # Two standing rows of one membership reference naming one round, a lapsed
    # row and a later restored row, so the notice_seq tie break of P02 decides
    # whether the entrant is barred in that round.
    if len(steady) > 1:
        pid = steady[1]
        member = next(p["membership_ref"] for p in inst["players"] if p["pid"] == pid)
        nseq = max(int(row[4]) for row in inst["membership_rows"])
        tie_round = min(3, inst["rounds"])
        inst["membership_rows"].append([ref, member, "lapsed", tie_round, nseq + 1])
        inst["membership_rows"].append([ref, member, "restored", tie_round, nseq + 2])
        inst["standing_tie_player"] = (pid, tie_round)


CANONICAL_MEMO_VALUES = {
    "bye_points": 3,
    "bye_game_delta": 2,
    "void_points": 1,
    "unpaired_points": 0,
    "no_record_points": 0,
    "round_points_floor": 0,
    "prize_disqualify_units": 2,
    "tie_group_depth": 2,
}

CROWN_GRADE_ALTERNATIVES = [(2000, 7), (3125, 11), (1750, 6)]


def _reordered(rng, keys, keep_last):
    """A permutation of keys that differs from the canonical order. With
    keep_last the final key stays in place, because the tiebreak, pairing and
    bye families end on the player identifier that makes each order total."""
    head = list(keys[:-1]) if keep_last else list(keys)
    for _ in range(8):
        order = rng.shuffled(head)
        if order != head:
            break
    else:
        order = head[1:] + head[:1]
    return order + ([keys[-1]] if keep_last else [])


def _mint_office_values(inst):
    """The values the three office papers and the unit register carry.

    The shipped event keeps the canonical values. Every other event draws its
    own memorandum constants, directive key positions, division ranks and
    crown_grade conversion, so a program that holds the shipped values instead
    of reading the papers it is pointed at comes out wrong on the events it has
    never seen. The draw uses its own generator so the rest of each corpus
    keeps the bytes it had."""
    if inst["profile"] == "shipped":
        inst["memo_values"] = dict(CANONICAL_MEMO_VALUES)
        inst["key_families"] = {family: list(keys) for family, keys in KEY_FAMILIES}
        inst["division_ranks"] = {div: i for i, div in enumerate(DIVISIONS, start=1)}
        inst["units"] = list(RATING_UNITS)
        return
    var = Rng(inst["seed"] ^ 0x56415259)
    memo = dict(CANONICAL_MEMO_VALUES)
    memo["bye_points"] = var.pick([2, 4])
    memo["bye_game_delta"] = var.pick([1, 3])
    memo["void_points"] = var.pick([0, 2])
    memo["unpaired_points"] = var.pick([0, 1])
    memo["no_record_points"] = var.pick([0, 1])
    memo["prize_disqualify_units"] = var.pick([1, 3])
    memo["tie_group_depth"] = var.pick([1, 3])
    inst["memo_values"] = memo
    families = {}
    for family, keys in KEY_FAMILIES:
        families[family] = _reordered(var, keys, keep_last=(family != "void_reason"))
    inst["key_families"] = families
    ranks = _reordered(var, [1, 2, 3, 4], keep_last=False)
    inst["division_ranks"] = {div: ranks[i] for i, div in enumerate(DIVISIONS)}
    num, den = var.pick(CROWN_GRADE_ALTERNATIVES)
    inst["units"] = [(name, num, den) if name == "crown_grade" else (name, n, d)
                     for name, n, d in RATING_UNITS]
    # Set after every draw, so the generator's sequence is untouched.
    for i, rung in enumerate(inst["policy"]["rungs"], start=1):
        memo["relaxation_rung_%d" % i] = rung
    # The score band check is ranked ahead of the cross division check on this
    # profile, so on a cross division board the band widening of the division
    # of player_a decides which reason P08 records.
    if inst["profile"] == BRANCH_FIXTURE_PROFILE:
        order = [key for key in families["void_reason"] if key != "score_band"]
        order.insert(order.index("cross_division"), "score_band")
        families["void_reason"] = order


def _mint_players(inst, rng):
    """One player record per seated entrant plus the shadow division entrants
    whose division the topology leaves out of force."""
    players = []
    order = 0
    for div in DIVISIONS:
        for _ in range(inst["counts"][div]):
            order += 1
            players.append({"pid": "PL-%s-%04d" % (div.split("_")[1][:2].upper(), order),
                            "division": div})
    for i in range(inst["shadow_count"]):
        order += 1
        players.append({"pid": "PL-EM-%04d" % (900 + i), "division": SHADOW_DIVISION})

    # Ratings are drawn in milli-rating and then quoted back in a register unit,
    # so the shipped quotation has to be converted to be comparable.
    for p in players:
        base = rng.between(980000, 2460000)
        p["rating_mr"] = base
        unit_name, num, den = rng.pick(inst["units"])
        p["unit"] = unit_name
        # Choose a quoted value whose exact conversion lands on rating_mr.
        quoted = round_half_even(Fraction(base * den, num))
        p["quoted"] = quoted
        p["rating_mr"] = scaled(num, den, quoted)
        p["membership_ref"] = "MB-%06d" % rng.between(100000, 999999)
    inst["players"] = players
    inst["in_force_players"] = [p for p in players if p["division"] in DIVISIONS]
    # The division with the fewest seated entrants is the one whose bye cap
    # binds, so it is the division that exercises the cap override, the third
    # rung of the admission ladder and the unpaired branch. Its entrants are
    # kept out of every journal so the branch is reached on every event.
    populated = [d for d in DIVISIONS if inst["counts"][d] > 0]
    inst["small_division"] = min(populated, key=lambda d: (inst["counts"][d], d))
    # The division that refuses cross admission in the closing rounds, so the
    # gate on the third rung of the ladder decides a board rather than decorating
    # one.
    inst["large_division"] = max(populated, key=lambda d: (inst["counts"][d], d))


def _journal_pool(inst):
    return [p for p in inst["in_force_players"]
            if p["division"] != inst["small_division"]]


def _mint_roster_papers(inst, rng):
    """The entry roster, the alias closure, the seat register and the rating
    return sheet, each carrying the documented revision and status traps."""
    players = inst["players"]
    roster = []
    aliases = []
    seats = []
    ratings = []
    memberships = []
    withdrawn = []
    seq = 1000

    # Absent ratings: the division default has to be used, never a zero.
    absent_players = set()
    for p in inst["in_force_players"]:
        if rng.chance(1, 26):
            absent_players.add(p["pid"])
    inst["absent_rating_players"] = sorted(absent_players)

    # Alias clusters: a folded entry id, a two step chain and one cycle.
    alias_targets = [p for p in inst["in_force_players"] if rng.chance(1, 9)]
    folded = {}
    chain_seq = 1
    for p in alias_targets:
        alias_id = "PL-XX-%04d" % (5000 + chain_seq)
        aliases.append([inst["event_reference"], alias_id, p["pid"], chain_seq, "direct"])
        folded[alias_id] = p["pid"]
        chain_seq += 1
        if rng.chance(1, 3):
            second = "PL-XX-%04d" % (5000 + chain_seq)
            aliases.append([inst["event_reference"], second, alias_id, chain_seq, "chained"])
            folded[second] = p["pid"]
            chain_seq += 1
    inst["alias_map"] = folded

    # One documented cycle: the lowest identifier of the cycle is canonical.
    cyc_a = "PL-ZY-7001"
    cyc_b = "PL-ZY-7002"
    aliases.append([inst["event_reference"], cyc_a, cyc_b, chain_seq, "chained"])
    aliases.append([inst["event_reference"], cyc_b, cyc_a, chain_seq + 1, "chained"])
    chain_seq += 2
    inst["alias_cycle"] = [cyc_a, cyc_b]
    # Every event seats both members of the cycle, so the rule that breaks a
    # cycle at its lowest member carries a fixture on the shipped event and on
    # each minted one. A rule inert on the shipped event would let a solver that
    # misread it look like a solver carrying answers.
    inst["cycle_seated"] = True

    while len(aliases) < 208:
        chain_seq += 1
        ref = rng.pick(inst["prior_references"])
        aliases.append([ref, "PL-XX-%04d" % (6000 + chain_seq),
                        "PL-XX-%04d" % (6500 + chain_seq), chain_seq, "direct"])
    inst["alias_rows"] = aliases

    alias_filing = {}
    for alias_id, canonical in sorted(folded.items()):
        if rng.chance(1, 2):
            alias_filing.setdefault(canonical, alias_id)
    inst["alias_filed_players"] = sorted(alias_filing)

    for p in players:
        seq += 1
        quoted = ABSENT if p["pid"] in absent_players else p["quoted"]
        # A superseded first filing, then the applicable revision.
        roster.append([inst["event_reference"], seq, p["pid"], p["division"],
                       quoted, p["unit"], p["membership_ref"], "confirmed", 1, 0])
        base_seq = seq
        if rng.chance(1, 5):
            seq += 1
            roster.append([inst["event_reference"], seq, p["pid"], p["division"],
                           quoted, p["unit"], p["membership_ref"], "amended", 2, 0])
        if rng.chance(1, 7):
            # A withdrawn revision above the applicable one: it never governs.
            seq += 1
            roster.append([inst["event_reference"], seq, p["pid"], p["division"],
                           rng.between(1, 9), p["unit"], p["membership_ref"],
                           "withdrawn", 9, 0])
            withdrawn.append([inst["event_reference"], p["pid"], 9, seq,
                              "withdrawn_revision"])
        alias_id = alias_filing.get(p["pid"])
        if alias_id is not None:
            seq += 1
            roster.append([inst["event_reference"], seq, alias_id, p["division"],
                           quoted, p["unit"], p["membership_ref"], "amended", 3, 0])
            base_seq = seq
        p["entry_seq"] = base_seq

    # Equal revision sequence resolved on the entry sequence.
    tie_players = [p for p in inst["in_force_players"] if rng.chance(1, 24)]
    for p in tie_players:
        seq += 1
        roster.append([inst["event_reference"], seq, p["pid"], p["division"],
                       ABSENT if p["pid"] in absent_players else p["quoted"],
                       p["unit"], p["membership_ref"], inst["policy"]["seated_status"],
                       1, 0])
        p["entry_seq"] = seq
    inst["revision_tie_players"] = sorted(p["pid"] for p in tie_players)

    if inst["cycle_seated"]:
        unit_name, num, den = inst["units"][0]
        for member in (cyc_a, cyc_b):
            seq += 1
            roster.append([inst["event_reference"], seq, member,
                           inst["large_division"],
                           round_half_even(Fraction(rng.between(980000, 2460000) * den,
                                                    num)),
                           unit_name, "MB-%06d" % rng.between(100000, 999999),
                           "confirmed", 1, 0])

    # A voided revision above the governing filing, carrying another division and
    # another rating. P01 excludes it whatever its revision_seq is, so a solver
    # that honours the excluded list of revision_precedence.toml never sees it and
    # a solver that reads only revision_seq takes it and moves the entrant.
    # Chosen without the generator's own randomness so the other three events keep
    # the bytes they had.
    if inst["profile"] == BRANCH_FIXTURE_PROFILE:
        spoken_for = ({row[1] for row in withdrawn} | absent_players
                      | {p["pid"] for p in tie_players} | set(alias_filing))
        target = sorted(p["pid"] for p in inst["in_force_players"]
                        if p["division"] == inst["large_division"]
                        and p["pid"] not in spoken_for)[0]
        seq += 1
        roster.append([inst["event_reference"], seq, target,
                       inst["small_division"], 1, "rating_point",
                       "MB-000000", "voided", 9, 0])
        inst["voided_entry_player"] = target

    # Rows filed against another event reference.
    while len(roster) < 268:
        seq += 1
        ref = rng.pick(inst["prior_references"])
        roster.append([ref, seq, "PL-QQ-%04d" % (7000 + seq), rng.pick(DIVISIONS),
                       rng.between(900, 2600), "rating_point",
                       "MB-%06d" % rng.between(100000, 999999), "confirmed", 1, 0])
    inst["roster_rows"] = roster

    # Declared seats: the register publishes a declared seed that disagrees with
    # the derived one for a documented handful of entrants.
    ranked = sorted(inst["in_force_players"],
                    key=lambda p: (-p["rating_mr"], p["pid"]))
    for i, p in enumerate(ranked, start=1):
        p["derived_seed"] = i
    disagree = set()
    for p in ranked:
        if rng.chance(1, 11):
            disagree.add(p["pid"])
    inst["declared_seed_disagreements"] = sorted(disagree)
    for p in ranked:
        declared = p["derived_seed"]
        if p["pid"] in disagree:
            declared = max(1, min(len(ranked), p["derived_seed"] + rng.between(-6, 6)))
        seats.append([inst["event_reference"], p["pid"], p["division"], declared,
                      "T%03d" % rng.between(1, 240), rng.between(1, 4)])
    for p in players:
        if p["division"] == SHADOW_DIVISION:
            seats.append([inst["event_reference"], p["pid"], p["division"], 0,
                          "T%03d" % rng.between(1, 240), 1])
    while len(seats) < 246:
        ref = rng.pick(inst["prior_references"])
        seats.append([ref, "PL-QQ-%04d" % (7500 + len(seats)), rng.pick(DIVISIONS),
                      rng.between(1, 400), "T%03d" % rng.between(1, 240), 1])
    inst["seat_rows"] = seats

    # Rating returns: a filed return outranks the roster quotation; a
    # superseded return never governs whatever its sequence.
    return_players = set()
    for p in inst["in_force_players"]:
        if rng.chance(1, 4):
            return_players.add(p["pid"])
    rseq = 500
    for p in inst["in_force_players"]:
        rseq += 1
        if p["pid"] in return_players:
            unit_name, num, den = rng.pick(inst["units"])
            value = round_half_even(Fraction(p["rating_mr"] * den, num))
            # An earlier filed return the higher sequence supersedes in fact
            # while carrying the applicable status.
            ratings.append([inst["event_reference"], p["pid"],
                            rng.between(900, 2600), "rating_point", rseq, "filed"])
            rseq += 1
            ratings.append([inst["event_reference"], p["pid"], value, unit_name,
                            rseq, "filed"])
            p["rating_source"] = "return"
            p["rating_mr"] = scaled(num, den, value)
            if rng.chance(1, 3):
                rseq += 1
                ratings.append([inst["event_reference"], p["pid"],
                                rng.between(1, 40), "rating_point", rseq,
                                "superseded"])
        else:
            p["rating_source"] = "roster"
            rseq += 1
            ratings.append([inst["event_reference"], p["pid"], rng.between(1, 40),
                            "rating_point", rseq, "superseded"])
    while len(ratings) < 258:
        rseq += 1
        ref = rng.pick(inst["prior_references"])
        ratings.append([ref, "PL-QQ-%04d" % (7800 + rseq), rng.between(900, 2600),
                        "rating_point", rseq, "filed"])
    inst["rating_rows"] = ratings
    inst["rating_return_players"] = sorted(return_players)

    # Membership standing: a lapsed notice bars from its effective round, a
    # restored notice at a later round re-admits.
    lapsed = []
    nseq = 300
    pool = set(p["pid"] for p in _journal_pool(inst))
    for p in inst["in_force_players"]:
        nseq += 1
        if p["pid"] in pool and rng.chance(1, 21):
            round_no = rng.between(2, inst["rounds"])
            memberships.append([inst["event_reference"], p["membership_ref"],
                                "lapsed", round_no, nseq])
            lapsed.append((p["pid"], round_no))
            if rng.chance(1, 2) and round_no + 2 <= inst["rounds"]:
                nseq += 1
                memberships.append([inst["event_reference"], p["membership_ref"],
                                    "restored", round_no + 2, nseq])
        else:
            memberships.append([inst["event_reference"], p["membership_ref"],
                                "current", 1, nseq])
    while len(memberships) < 248:
        nseq += 1
        ref = rng.pick(inst["prior_references"])
        memberships.append([ref, "MB-%06d" % rng.between(100000, 999999),
                            "current", 1, nseq])
    inst["membership_rows"] = memberships
    inst["lapsed_players"] = sorted(lapsed)

    while len(withdrawn) < 212:
        ref = rng.pick(inst["prior_references"])
        withdrawn.append([ref, "PL-QQ-%04d" % (8000 + len(withdrawn)),
                          rng.between(1, 9), 9000 + len(withdrawn),
                          "withdrawn_revision"])
    inst["withdrawn_rows"] = withdrawn

    # Recompute the derived seat order after the rating returns moved ratings.
    ranked = sorted(inst["in_force_players"],
                    key=lambda p: (-p["rating_mr"], p["pid"]))
    for i, p in enumerate(ranked, start=1):
        p["derived_seed"] = i


def _mint_configuration(inst, rng):
    """The round configuration register and the division admission matrix, both
    in long parameter form so a reader has to select on the parameter name."""
    rounds = inst["rounds"]
    win, draw, loss = inst["policy"]["points"]
    default_base, default_step = inst["policy"]["default_rating"]
    cfg_rows = []
    seq = 100
    for r in range(1, rounds + 1):
        for div in DIVISIONS:
            code, _, _ = rng.pick(MODIFIER_CODES)
            for name, value in (
                ("win_points", win),
                ("draw_points", draw),
                ("loss_points", loss),
                ("modifier_code", code),
                ("board_span", rng.between(40, 120)),
                ("sheet_channel", "CH%02d" % rng.between(1, 9)),
            ):
                seq += 1
                cfg_rows.append([inst["event_reference"], r, div, name, value, seq])
    # Superseded configuration rows for another event reference.
    while len(cfg_rows) < 248:
        seq += 1
        cfg_rows.append([rng.pick(inst["prior_references"]),
                         rng.between(1, rounds), rng.pick(DIVISIONS),
                         "modifier_code", rng.pick(MODIFIER_CODES)[0], seq])
    inst["round_config_rows"] = cfg_rows

    matrix = []
    mseq = 200
    small = inst["small_division"]
    for div in DIVISIONS:
        for r in range(1, rounds + 1):
            cross = "yes" if rng.chance(4, 5) else "no"
            override = "yes" if rng.chance(3, 5) else "no"
            if div == small:
                cross = "yes"
                override = "yes" if r == max(1, rounds - 2) else "no"
            elif div == inst["large_division"] and r > rounds - 3:
                cross = "no"
            for name, value in (
                ("cross_admitted", cross),
                ("bye_override", override),
                ("default_rating_mr", default_base + default_step * DIVISIONS.index(div)),
                ("band_widening", rng.between(0, 2)),
                ("board_prefix", "B%s" % div.split("_")[1][:2].upper()),
                ("seat_channel", "SC%02d" % rng.between(1, 9)),
            ):
                mseq += 1
                matrix.append([inst["event_reference"], div, r, name, value, mseq])
    while len(matrix) < 236:
        mseq += 1
        matrix.append([rng.pick(inst["prior_references"]), rng.pick(DIVISIONS),
                       rng.between(1, rounds), "band_widening", rng.between(0, 3),
                       mseq])
    inst["division_matrix_rows"] = matrix

    priority = []
    pseq = 700
    for code, rank in (("sheet_adjudication", 1), ("game_concession", 2),
                       ("completed_game", 3), ("declared_count", 4),
                       ("no_evidence", 5)):
        pseq += 1
        priority.append([inst["event_reference"], code, rank, pseq, "operative"])
    while len(priority) < 210:
        pseq += 1
        priority.append([rng.pick(inst["prior_references"]),
                         rng.pick(["sheet_adjudication", "completed_game",
                                   "declared_count"]),
                         rng.between(1, 5), pseq, "withdrawn"])
    inst["source_priority_rows"] = priority


def _mint_status_journal(inst, rng):
    """Drop, reentry, absence and reinstatement events on the round tick grid,
    with three events landing exactly on a round boundary."""
    ticks = inst["ticks"]
    rounds = inst["rounds"]
    rows = []
    seq = 400
    boundary = []
    pool = _journal_pool(inst)
    for p in pool:
        if not rng.chance(1, 7):
            continue
        r = rng.between(2, rounds)
        if rng.chance(1, 4):
            tick = (r - 1) * ticks
            boundary.append((p["pid"], r, "drop"))
        else:
            tick = (r - 1) * ticks + rng.between(1, ticks - 1)
        seq += 1
        rows.append([inst["event_reference"], p["pid"], "drop", tick, seq])
        if rng.chance(2, 5) and r + 2 <= rounds:
            back = r + 2
            if rng.chance(1, 3):
                tick2 = (back - 1) * ticks
                boundary.append((p["pid"], back, "reentry"))
            else:
                tick2 = (back - 1) * ticks + rng.between(1, ticks - 1)
            seq += 1
            rows.append([inst["event_reference"], p["pid"], "reentry", tick2, seq])
    for p in pool:
        if rng.chance(1, 12):
            r = rng.between(1, rounds)
            seq += 1
            rows.append([inst["event_reference"], p["pid"], "absence",
                         (r - 1) * ticks + rng.between(1, ticks - 1), seq])

    # A reinstate row in the round after a drop that no reentry undoes. P02 has
    # reinstate restore the seated state and persist it, so a solver that leaves
    # the branch out keeps the entrant dropped for the rest of the event and
    # diverges from the round it lands in onward. The tick is kept off the round
    # boundary so the boundary fixtures stay the three they were, and the entrant
    # is chosen without the generator's own randomness so the other three events
    # keep the bytes they had.
    if inst["profile"] == BRANCH_FIXTURE_PROFILE:
        history = {}
        for ref, pid, code, tick, _seq in rows:
            if ref == inst["event_reference"]:
                history.setdefault(pid, []).append((tick // ticks + 1, code))
        for pid in sorted(history):
            codes = [code for _r, code in history[pid]]
            if "drop" not in codes or "reentry" in codes:
                continue
            back = max(r for r, code in history[pid] if code == "drop") + 1
            if back <= rounds:
                seq += 1
                rows.append([inst["event_reference"], pid, "reinstate",
                             (back - 1) * ticks + 1, seq])
                inst["reinstate_player"] = pid
                inst["reinstate_round"] = back
                break

    while len(rows) < 226:
        seq += 1
        rows.append([rng.pick(inst["prior_references"]),
                     "PL-QQ-%04d" % (8400 + seq), "drop",
                     rng.between(1, ticks * rounds), seq])
    inst["status_rows"] = rows
    inst["boundary_status_events"] = sorted(boundary)


def _mint_penalties(inst, rng):
    """Penalty notices across the four applied classes plus expulsion, with
    rescinded notices that never apply and one notice on a round boundary."""
    rounds = inst["rounds"]
    rows = []
    seq = 600
    expelled = []
    for p in _journal_pool(inst):
        if rng.chance(1, 6):
            cls = rng.pick(["game", "game", "match", "round", "tournament"])
            magnitude = {"game": rng.between(1, 3), "match": 1,
                         "round": rng.between(1, 4),
                         "tournament": rng.between(1, 3)}[cls]
            r = rng.between(1, rounds)
            seq += 1
            rows.append([inst["event_reference"], p["pid"], cls, magnitude, r, seq,
                         "served"])
            if rng.chance(1, 4):
                seq += 1
                rows.append([inst["event_reference"], p["pid"], cls,
                             magnitude + 3, r, seq, "rescinded"])
        elif rng.chance(1, 40):
            r = rng.between(3, rounds)
            seq += 1
            rows.append([inst["event_reference"], p["pid"], "expulsion", 0, r, seq,
                         "served"])
            expelled.append((p["pid"], r))
    while len(rows) < 236:
        seq += 1
        rows.append([rng.pick(inst["prior_references"]),
                     "PL-QQ-%04d" % (8700 + seq), rng.pick(PENALTY_CLASSES),
                     rng.between(1, 4), rng.between(1, rounds), seq, "served"])
    inst["penalty_rows"] = rows
    inst["expelled_players"] = sorted(expelled)


def _mint_appeals(inst, rng):
    """Appeal dispositions: the register the panel worked from. Every applicable
    disposition names the notice it disposes of."""
    rows = []
    seq = 800
    for row in inst["penalty_rows"]:
        if row[0] != inst["event_reference"]:
            continue
        if not rng.chance(1, 3):
            continue
        seq += 1
        rows.append({"event_reference": inst["event_reference"],
                     "disposition_seq": seq,
                     "notice_seq": row[5],
                     "player_ref": row[1],
                     "disposition": "upheld" if row[6] == "served" else "allowed",
                     "panel": "P%02d" % rng.between(1, 12)})
    while len(rows) < 214:
        seq += 1
        rows.append({"event_reference": rng.pick(inst["prior_references"]),
                     "disposition_seq": seq,
                     "notice_seq": rng.between(600, 900),
                     "player_ref": "PL-QQ-%04d" % (9000 + seq),
                     "disposition": "withdrawn",
                     "panel": "P%02d" % rng.between(1, 12)})
    inst["appeal_rows"] = rows


def _mint_decoys(inst, rng):
    """The three papers the lineage map says govern nothing."""
    legacy = []
    for i in range(216):
        legacy.append([rng.pick(inst["prior_references"]),
                       "PL-QQ-%04d" % (9300 + i), rng.between(1, 400),
                       rng.between(0, 27), rng.between(0, 9),
                       "S%02d" % rng.between(1, 30)])
    inst["legacy_rows"] = legacy

    gate = []
    for i in range(208):
        gate.append({"reference": rng.pick(inst["prior_references"]),
                     "hall": "H%02d" % rng.between(1, 12),
                     "session": i + 1,
                     "admissions": rng.between(40, 900),
                     "turnstile": "TS%03d" % rng.between(1, 300)})
    inst["gate_rows"] = gate

    audit = []
    for i in range(204):
        audit.append(("N%04d" % (i + 1), rng.pick(inst["prior_references"]),
                      "desk_note", str(rng.between(1, 9999))))
    inst["audit_rows"] = audit


# --------------------------------------------------------------------------
# the recorded event
#
# The papers record the event as the hall software ran it. That software worked
# a naive round state: it ordered on recorded match points alone, ignored the
# membership standing register and the expulsion notices, placed a status change
# that landed exactly on a round boundary in the earlier round, widened the
# score band by one, and let a documented share of boards through in breach of
# the pairing constraints. Nothing here is the authoritative settlement; it is
# the evidence the authoritative settlement is recomputed from.
# --------------------------------------------------------------------------


def _naive_state(inst, rng):
    ticks = inst["ticks"]
    drops = {}
    for row in inst["status_rows"]:
        if row[0] != inst["event_reference"]:
            continue
        pid, code, tick, seq = row[1], row[2], int(row[3]), int(row[4])
        # The software placed a boundary tick in the round that closed.
        if tick % ticks == 0 and tick > 0:
            round_no = tick // ticks
        else:
            round_no = tick // ticks + 1
        drops.setdefault(pid, []).append((round_no, seq, code))
    for pid in drops:
        drops[pid].sort()
    return drops


def _naive_eligible(inst, drops, round_no, pid):
    state = "seated"
    for r, _seq, code in drops.get(pid, []):
        if r > round_no:
            break
        if code == "drop":
            state = "dropped"
        elif code == "reentry":
            state = "seated"
        elif code == "absence":
            state = "absent" if r == round_no else state
        elif code == "reinstate":
            state = "seated"
    return state == "seated"


def _mint_recorded_event(inst, rng):
    rounds = inst["rounds"]
    band = inst["score_band"] + 1
    drops = _naive_state(inst, rng)
    reverse_alias = {}
    for alias, canonical in inst["alias_map"].items():
        reverse_alias.setdefault(canonical, []).append(alias)

    points = {p["pid"]: 0 for p in inst["in_force_players"]}
    history = {p["pid"]: set() for p in inst["in_force_players"]}
    byes = {p["pid"]: 0 for p in inst["in_force_players"]}

    pairing_rows = []
    sheet_records = []
    game_rows = []
    bye_rows = []
    breaches = {"repeat": [], "cross": [], "band": []}
    scenarios = {"adjudicated": [], "concession": [], "declared_only": [],
                 "no_evidence": [], "single_game": [], "double_concession": []}
    pseq = 10000
    gseq = 50000
    sseq = 30000
    bseq = 20000

    for r in range(1, rounds + 1):
        eligible = [p for p in inst["in_force_players"]
                    if _naive_eligible(inst, drops, r, p["pid"])]
        by_div = {}
        for p in eligible:
            by_div.setdefault(p["division"], []).append(p)

        pool = []
        for div in DIVISIONS:
            members = by_div.get(div, [])
            if len(members) % 2 == 1:
                candidates = sorted(members, key=lambda p: (points[p["pid"]], p["pid"]))
                chosen = candidates[0]
                byes[chosen["pid"]] += 1
                points[chosen["pid"]] += 3
                bseq += 1
                bye_rows.append([inst["event_reference"], r, div, chosen["pid"],
                                 byes[chosen["pid"]] - 1, bseq, "awarded"])
                members = [p for p in members if p["pid"] != chosen["pid"]]
            pool.extend(members)

        order = sorted(pool, key=lambda p: (-points[p["pid"]], p["pid"]))
        unpaired = list(order)
        table_no = 0
        while len(unpaired) >= 2:
            a = unpaired.pop(0)
            allow_repeat = rng.chance(1, 22)
            allow_cross = rng.chance(1, 44)
            allow_band = rng.chance(1, 18)
            chosen_index = None
            for i, b in enumerate(unpaired):
                if b["division"] != a["division"] and not allow_cross:
                    continue
                if b["pid"] in history[a["pid"]] and not allow_repeat:
                    continue
                if abs(points[a["pid"]] - points[b["pid"]]) > band and not allow_band:
                    continue
                chosen_index = i
                break
            if chosen_index is None:
                for i, b in enumerate(unpaired):
                    if b["division"] == a["division"]:
                        chosen_index = i
                        break
            if chosen_index is None:
                chosen_index = 0
            b = unpaired.pop(chosen_index)
            if b["pid"] in history[a["pid"]]:
                breaches["repeat"].append((r, a["pid"], b["pid"]))
            if b["division"] != a["division"]:
                breaches["cross"].append((r, a["pid"], b["pid"]))
            if abs(points[a["pid"]] - points[b["pid"]]) > inst["score_band"]:
                breaches["band"].append((r, a["pid"], b["pid"]))

            table_no += 1
            if rng.chance(1, 12):
                table_no += 1  # table numbers are not contiguous
            ref_a = a["pid"]
            ref_b = b["pid"]
            if reverse_alias.get(a["pid"]) and rng.chance(1, 3):
                ref_a = reverse_alias[a["pid"]][0]
            if reverse_alias.get(b["pid"]) and rng.chance(1, 3):
                ref_b = reverse_alias[b["pid"]][0]

            pseq += 1
            pairing_rows.append([inst["event_reference"], r, table_no, ref_a, ref_b,
                                 1, pseq, "recorded"])
            if rng.chance(1, 9):
                pseq += 1
                pairing_rows.append([inst["event_reference"], r, table_no, ref_a,
                                     ref_b, 2, pseq, "amended"])
            if rng.chance(1, 14):
                pseq += 1
                pairing_rows.append([inst["event_reference"], r, table_no, ref_b,
                                     ref_a, 4, pseq, "rescinded"])

            gseq, sseq, outcome = _mint_match_evidence(
                inst, rng, r, table_no, a, b, game_rows, sheet_records, gseq, sseq,
                scenarios)
            if outcome == "a":
                points[a["pid"]] += 3
            elif outcome == "b":
                points[b["pid"]] += 3
            elif outcome == "draw":
                points[a["pid"]] += 1
                points[b["pid"]] += 1
            history[a["pid"]].add(b["pid"])
            history[b["pid"]].add(a["pid"])

        for leftover in unpaired:
            bseq += 1
            bye_rows.append([inst["event_reference"], r, leftover["division"],
                             leftover["pid"], byes[leftover["pid"]], bseq,
                             "left_over"])

    # One table the hall double booked: two candidate boards of the same round
    # hold one entrant, and the lower table number is the board of that entrant.
    middle = max(1, rounds // 2)
    same_round = [row for row in pairing_rows
                  if row[1] == middle and row[7] == "recorded"]
    if len(same_round) >= 2:
        first, second = same_round[0], same_round[1]
        highest = max(row[2] for row in pairing_rows if row[1] == middle)
        pseq += 1
        sseq += 1
        pairing_rows.append([inst["event_reference"], middle, highest + 5,
                             first[3], second[4], 1, pseq, "recorded"])
        sheet_records.append({"event_reference": inst["event_reference"],
                              "round_no": middle, "table_no": highest + 5,
                              "adjudicated_result": ABSENT,
                              "declared_games_a": 2,
                              "declared_games_b": 1,
                              "sheet_seq": sseq, "sheet_status": "filed"})
        inst["double_booked"] = (middle, highest + 5, first[3], second[4])

    # One board carrying both an adjudicated result and a concession that
    # disagree, so the order of the first two evidence levels decides a graded
    # result rather than only being stated. Chosen without the generator's own
    # randomness so the other three events keep the bytes they had.
    if inst["profile"] == BRANCH_FIXTURE_PROFILE:
        single = sorted(set(scenarios["concession"]) - set(scenarios["double_concession"]))
        for r_no, t_no in single:
            conceded = [row[4] for row in game_rows
                        if row[1] == r_no and row[2] == t_no
                        and row[4].startswith("conceded_")]
            filed = [rec for rec in sheet_records
                     if rec["round_no"] == r_no and rec["table_no"] == t_no
                     and rec["sheet_status"] == "filed"]
            if len(conceded) != 1 or len(filed) != 1:
                continue
            # A concession by side a resolves to win_b, so the sheet rules win_a.
            filed[0]["adjudicated_result"] = ("win_a" if conceded[0] == "conceded_a"
                                              else "win_b")
            inst["adjudicated_concession_board"] = (r_no, t_no)
            break

    # Two filed result sheets on one board, the later one adjudicating a result
    # the completed games do not give, so the rule that the highest sheet_seq
    # governs decides a graded result. Chosen without the generator's own
    # randomness so the other three events keep the bytes they had.
    if inst["profile"] == BRANCH_FIXTURE_PROFILE:
        top_seq = max(int(rec["sheet_seq"]) for rec in sheet_records)
        spoken_for = set()
        for boards_of_kind in scenarios.values():
            spoken_for |= set(boards_of_kind)
        spoken_for.add(inst.get("adjudicated_concession_board"))
        for row in pairing_rows:
            if row[0] != inst["event_reference"] or row[7] != "recorded" or row[5] != 1:
                continue
            key = (row[1], row[2])
            if key in spoken_for:
                continue
            played = [g for g in game_rows if (g[1], g[2]) == key]
            won_a = sum(1 for g in played if g[4] == "won_a" and g[5] == "yes")
            won_b = sum(1 for g in played if g[4] == "won_b" and g[5] == "yes")
            filed = [rec for rec in sheet_records
                     if (rec["round_no"], rec["table_no"]) == key
                     and rec["sheet_status"] == "filed"]
            if won_a == won_b or len(filed) != 1 or filed[0]["adjudicated_result"] != ABSENT:
                continue
            sheet_records.append({"event_reference": inst["event_reference"],
                                  "round_no": key[0], "table_no": key[1],
                                  "adjudicated_result": "double_loss",
                                  "declared_games_a": ABSENT,
                                  "declared_games_b": ABSENT,
                                  "sheet_seq": top_seq + 1, "sheet_status": "filed"})
            inst["second_sheet_board"] = key
            break

    # Equal sheet revision on one board, resolved on the source sequence.
    if pairing_rows:
        anchor = pairing_rows[len(pairing_rows) // 3]
        pseq += 1
        pairing_rows.append([anchor[0], anchor[1], anchor[2], anchor[3], anchor[4],
                             anchor[5], pseq, "recorded"])
        inst["revision_tie_board"] = (anchor[1], anchor[2])
    while len(pairing_rows) < 780:
        pseq += 1
        pairing_rows.append([rng.pick(inst["prior_references"]),
                             rng.between(1, rounds), rng.between(1, 200),
                             "PL-QQ-%04d" % (9600 + pseq % 300),
                             "PL-QQ-%04d" % (9700 + pseq % 300), 1, pseq,
                             "recorded"])

    while len(bye_rows) < 214:
        bseq += 1
        bye_rows.append([rng.pick(inst["prior_references"]), rng.between(1, rounds),
                         rng.pick(DIVISIONS), "PL-QQ-%04d" % (9800 + bseq % 200),
                         rng.between(0, 3), bseq, "awarded"])

    inst["pairing_rows"] = pairing_rows
    inst["sheet_records"] = sheet_records
    inst["game_rows"] = game_rows
    inst["bye_rows"] = bye_rows
    inst["breaches"] = breaches
    inst["scenarios"] = scenarios


def _mint_match_evidence(inst, rng, r, table_no, a, b, game_rows, sheet_records,
                         gseq, sseq, scenarios):
    """Write the game records and the result sheet of one recorded board, and
    return which side the hall software credited."""
    ref = inst["event_reference"]
    scenario = "normal"
    if rng.chance(1, 15):
        scenario = "adjudicated"
    elif rng.chance(1, 15):
        scenario = "concession"
    elif rng.chance(1, 20):
        scenario = "declared_only"

    elif rng.chance(1, 40):
        scenario = "no_evidence"
    elif rng.chance(1, 17):
        scenario = "single_game"

    adjudicated = ABSENT
    declared_a = ABSENT
    declared_b = ABSENT
    wins_a = 0
    wins_b = 0

    if scenario == "no_evidence":
        scenarios["no_evidence"].append((r, table_no))
    elif scenario == "declared_only":
        declared_a = rng.between(0, 3)
        declared_b = rng.between(0, 3)
        scenarios["declared_only"].append((r, table_no))
        for game_no in range(1, rng.between(1, 3) + 1):
            gseq += 1
            game_rows.append([ref, r, table_no, game_no, "unplayed", "no", gseq])
    else:
        count = 1 if scenario == "single_game" else rng.between(2, 5)
        if scenario == "single_game":
            scenarios["single_game"].append((r, table_no))
        for game_no in range(1, count + 1):
            roll = rng.below(10)
            if roll < 4:
                outcome, completed = "won_a", "yes"
                wins_a += 1
            elif roll < 8:
                outcome, completed = "won_b", "yes"
                wins_b += 1
            elif roll < 9:
                outcome, completed = "drawn", "yes"
            else:
                outcome, completed = rng.pick(["won_a", "won_b"]), "no"
            gseq += 1
            game_rows.append([ref, r, table_no, game_no, outcome, completed, gseq])
            if rng.chance(1, 30):
                gseq += 1
                game_rows.append([ref, r, table_no, game_no,
                                  rng.pick(["won_a", "won_b"]), "no", gseq])
        if scenario == "concession":
            both = rng.chance(1, 6)
            side = rng.pick(["a", "b"])
            gseq += 1
            game_rows.append([ref, r, table_no, count + 1,
                              "conceded_%s" % side, "no", gseq])
            if both:
                other = "b" if side == "a" else "a"
                gseq += 1
                game_rows.append([ref, r, table_no, count + 2,
                                  "conceded_%s" % other, "no", gseq])
                scenarios["double_concession"].append((r, table_no))
            scenarios["concession"].append((r, table_no))
        if scenario == "adjudicated":
            adjudicated = rng.pick(RESULT_CODES)
            scenarios["adjudicated"].append((r, table_no))
        if rng.chance(1, 4):
            declared_a = wins_a
            declared_b = wins_b

    sseq += 1
    if rng.chance(1, 11):
        sheet_records.append({"event_reference": ref, "round_no": r,
                              "table_no": table_no,
                              "adjudicated_result": rng.pick(RESULT_CODES),
                              "declared_games_a": rng.between(0, 3),
                              "declared_games_b": rng.between(0, 3),
                              "sheet_seq": sseq + 400, "sheet_status": "superseded"})
    sheet_records.append({"event_reference": ref, "round_no": r, "table_no": table_no,
                          "adjudicated_result": adjudicated,
                          "declared_games_a": declared_a,
                          "declared_games_b": declared_b,
                          "sheet_seq": sseq, "sheet_status": "filed"})

    # What the hall software credited, on its own naive reading.
    if wins_a > wins_b:
        credited = "a"
    elif wins_b > wins_a:
        credited = "b"
    else:
        credited = "draw"
    return gseq, sseq, credited


# --------------------------------------------------------------------------
# register writers
# --------------------------------------------------------------------------


def _pad_rng(inst, salt):
    return Rng(inst["seed"] ^ (hash_salt(salt) & 0xFFFFFFFFFFFFFFFF))


def hash_salt(text):
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"),
                                         digest_size=8).digest(), "big")


def write_roster_papers(inst, root):
    write_rows(root / "entry_roster_register.csv",
               ["event_reference", "entry_seq", "entry_id", "division_id",
                "quoted_rating", "rating_unit", "membership_ref", "entry_status",
                "revision_seq", "reserved_flag"],
               inst["roster_rows"], ",")
    write_rows(root / "entry_alias_register.csv",
               ["event_reference", "alias_id", "canonical_id", "chain_seq",
                "alias_kind"],
               inst["alias_rows"], ",")
    write_rows(root / "seat_assignment_register.csv",
               ["event_reference", "entry_id", "division_id", "declared_seed",
                "hall_table", "seat_band"],
               inst["seat_rows"], ",")
    write_rows(root / "rating_return_sheet.psv",
               ["event_reference", "player_ref", "quoted_value", "quoted_unit",
                "return_seq", "return_status"],
               inst["rating_rows"], "|")
    write_rows(root / "membership_standing_register.csv",
               ["event_reference", "membership_ref", "standing_code",
                "effective_round", "notice_seq"],
               inst["membership_rows"], ",")
    write_rows(root / "withdrawn_entry_journal.tsv",
               ["event_reference", "entry_id", "revision_seq", "entry_seq",
                "withdrawal_kind"],
               inst["withdrawn_rows"], "\t")


def write_configuration_papers(inst, root):
    write_rows(root / "round_configuration_register.csv",
               ["event_reference", "round_no", "division_id", "parameter",
                "value", "notice_seq"],
               inst["round_config_rows"], ",")
    write_rows(root / "division_admission_matrix.csv",
               ["event_reference", "division_id", "round_no", "parameter",
                "value", "notice_seq"],
               inst["division_matrix_rows"], ",")
    write_rows(root / "source_priority_register.csv",
               ["event_reference", "source_code", "priority_rank", "notice_seq",
                "record_status"],
               inst["source_priority_rows"], ",")


def write_event_papers(inst, root):
    write_rows(root / "status_change_journal.tsv",
               ["event_reference", "player_ref", "change_code", "tick",
                "note_seq"],
               inst["status_rows"], "\t")
    write_rows(root / "penalty_notice_register.psv",
               ["event_reference", "player_ref", "penalty_class", "magnitude",
                "effective_round", "notice_seq", "notice_status"],
               inst["penalty_rows"], "|")
    write_jsonl(root / "appeal_disposition_journal.jsonl", inst["appeal_rows"])
    write_rows(root / "recorded_pairing_table.csv",
               ["event_reference", "round_no", "table_no", "player_a", "player_b",
                "sheet_revision", "source_seq", "pairing_status"],
               inst["pairing_rows"], ",")
    write_jsonl(root / "match_result_sheets.ndjson", inst["sheet_records"])
    write_rows(root / "game_records.csv",
               ["event_reference", "round_no", "table_no", "game_no", "outcome",
                "completed", "source_seq"],
               inst["game_rows"], ",")
    write_rows(root / "bye_award_journal.tsv",
               ["event_reference", "round_no", "division_id", "player_ref",
                "byes_before", "note_seq", "award_kind"],
               inst["bye_rows"], "\t")


def write_topology_paper(inst, root):
    rng = _pad_rng(inst, "topology")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<crown_event>"]
    lines.append("  <identity>")
    lines.append("    <event_id>%s</event_id>" % inst["event_id"])
    lines.append("    <event_reference>%s</event_reference>" % inst["event_reference"])
    lines.append("    <round_count>%d</round_count>" % inst["rounds"])
    lines.append("  </identity>")
    lines.append("  <divisions>")
    for div in DIVISIONS:
        lines.append('    <division id="%s" in_force="yes">' % div)
        lines.append("      <label>%s</label>" % div.split("_")[1].title())
        lines.append("      <hall>H%02d</hall>" % (DIVISIONS.index(div) + 1))
        lines.append("    </division>")
    lines.append('    <division id="%s" in_force="no">' % SHADOW_DIVISION)
    lines.append("      <label>Ember</label>")
    lines.append("      <hall>H09</hall>")
    lines.append("    </division>")
    lines.append("  </divisions>")
    lines.append("  <prior_events>")
    for ref in inst["prior_references"]:
        lines.append('    <prior reference="%s"/>' % ref)
    lines.append("  </prior_events>")
    lines.append("  <hall_layout>")
    for i in range(1, 201):
        lines.append('    <table number="%d" hall="H%02d" band="%d"/>'
                     % (i, rng.between(1, 4), rng.between(1, 4)))
    lines.append("  </hall_layout>")
    lines.append("</crown_event>")
    write_lines(root / "division_topology.xml", lines)


def write_roster_conf(inst, root):
    rng = _pad_rng(inst, "roster-conf")
    lines = ["# Reporting roster for the settlement publication.",
             "# A division section governs only when its record_status is operative",
             "# and its event_reference is this event.",
             "[event]",
             "event_reference = %s" % inst["event_reference"],
             "event_id = %s" % inst["event_id"],
             ""]
    places = rng.shuffled(list(range(1, len(DIVISIONS) + 1)))
    if places == sorted(places):
        places = places[1:] + places[:1]
    for i, div in enumerate(DIVISIONS):
        lines.append("[division:%s]" % div)
        lines.append("event_reference = %s" % inst["event_reference"])
        lines.append("report_order = %d" % places[i])
        lines.append("record_status = operative")
        lines.append("hall = H%02d" % places[i])
        lines.append("")
    lines.append("[division:%s]" % SHADOW_DIVISION)
    lines.append("event_reference = %s" % inst["event_reference"])
    lines.append("report_order = 9")
    lines.append("record_status = operative")
    lines.append("hall = H09")
    lines.append("")
    for div in DIVISIONS:
        lines.append("[division:%s]" % div)
        lines.append("event_reference = %s" % rng.pick(inst["prior_references"]))
        lines.append("report_order = %d" % rng.between(1, 9))
        lines.append("record_status = withdrawn")
        lines.append("hall = H%02d" % rng.between(1, 9))
        lines.append("")
    while len(lines) < 214:
        lines.append("[desk:%03d]" % rng.between(1, 900))
        lines.append("event_reference = %s" % rng.pick(inst["prior_references"]))
        lines.append("record_status = withdrawn")
        lines.append("hall = H%02d" % rng.between(1, 9))
        lines.append("")
    write_lines(root / "reporting_division_roster.conf", lines)


def write_decoy_papers(inst, root):
    write_rows(root / "legacy_season_extract.csv",
               ["season_reference", "entry_id", "season_rank", "season_points",
                "season_byes", "archive_code"],
               inst["legacy_rows"], ",")
    (root / "spectator_gate_returns.json").write_text(
        json.dumps({"returns": inst["gate_rows"]}, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    write_sqlite(root / "night_desk_audit.db",
                 {"desk_notes": (["note_id", "event_reference", "note_kind",
                                  "note_value"], inst["audit_rows"])})


def write_policy_papers(inst, root):
    write_lines(root / "unit_register_dictionary.toml", [
        "# Rating quotations are converted into milli-rating through the entry",
        "# whose name the quoting record carries. The conversion is",
        "# value * numerator / denominator, rounded half to even.",
        "",
        "base_unit = \"milli_rating\"",
        "",
    ] + sum([[
        "[unit.%s]" % name,
        "numerator = %d" % num,
        "denominator = %d" % den,
        "",
    ] for name, num, den in inst["units"]], []))

    write_lines(root / "rounding_and_arithmetic_policy.yaml", [
        "# Every quantity this settlement publishes is an exact scaled integer.",
        "arithmetic:",
        "  mode: exact_rational",
        "  binary_floating_point: forbidden",
        "rounding:",
        "  rule: half_to_even",
        "  placement: at_the_stage_the_specification_states",
        "  deferral: forbidden",
        "scales:",
        "  match_points: whole_points",
        "  game_differential: whole_games",
        "  rating: milli_rating",
        "  opponent_strength: thousandths_of_a_point",
        "  prize: whole_cents",
        "  published_ratio: nine_decimal_places",
        "notes:",
        "  - A rounded stage result is the input of the stage after it.",
        "  - A quantity that is exactly zero is published as zero and keeps no sign.",
        "  - A ratio whose denominator is zero is published as 0.000000000.",
    ])

    write_lines(root / "boundary_conventions.yaml", [
        "# Round intervals and the events that land on their edges.",
        "round_interval:",
        "  ticks_per_round: %d" % inst["ticks"],
        "  start: inclusive",
        "  end: exclusive",
        "  round_of_tick: tick divided by ticks_per_round, then one added",
        "status_change:",
        "  on_a_round_boundary: the later round",
        "  drop: persists until a reentry or a reinstatement",
        "  reentry: restores the seated state from its own round",
        "  absence: applies to its own round alone",
        "  reinstate: restores the seated state from its own round",
        "penalty_notice:",
        "  effective_round: the round the notice names, with no boundary arithmetic",
        "expulsion:",
        "  effective_round: bars from the round it names and every round after it",
    ])

    write_lines(root / "revision_precedence.toml", [
        "# Which filing of a record governs.",
        "",
        "[entry_roster]",
        "applicable_status = [\"confirmed\", \"amended\", \"%s\"]"
        % inst["policy"]["seated_status"],
        "excluded_status = [\"withdrawn\", \"voided\"]",
        "order = [\"revision_seq desc\", \"entry_seq desc\"]",
        "",
        "[rating_return]",
        "applicable_status = [\"filed\"]",
        "excluded_status = [\"superseded\"]",
        "order = [\"return_seq desc\"]",
        "",
        "[recorded_pairing]",
        "applicable_status = [\"recorded\", \"amended\"]",
        "excluded_status = [\"rescinded\"]",
        "order = [\"sheet_revision desc\", \"source_seq desc\"]",
        "",
        "[result_sheet]",
        "applicable_status = [\"filed\"]",
        "excluded_status = [\"superseded\"]",
        "order = [\"sheet_seq desc\"]",
        "",
        "[penalty_notice]",
        "applicable_status = [\"served\"]",
        "excluded_status = [\"rescinded\"]",
        "order = [\"notice_seq desc\"]",
        "",
        "[membership_standing]",
        "applicable_status = [\"current\", \"lapsed\", \"restored\"]",
        "order = [\"effective_round desc\", \"notice_seq desc\"]",
        "",
        "[reporting_roster]",
        "applicable_status = [\"operative\"]",
        "excluded_status = [\"withdrawn\"]",
        "",
        "[event_reference]",
        "rule = \"a record whose event_reference is not this event governs nothing\"",
    ])

    phrases = [RUNG_PHRASE[rung] for rung in inst["policy"]["rungs"]]
    bye_tolerance, unpaired_tolerance, ineligible_tolerance = inst["policy"]["tolerance"]
    write_lines(root / "pairing_precedence_policy.toml", [
        "# The admission ladder of the authoritative pairing.",
        "",
        "[admission]",
        "levels = 4",
        "level_0 = \"same division, inside the effective score band, no prior opponent\"",
        "level_1 = \"%s is set aside\"" % phrases[0],
        "level_2 = \"%s and %s are set aside\"" % (phrases[0], phrases[1]),
        "level_3 = \"%s, %s and %s are set aside\"" % tuple(phrases),
        "eligibility = \"never set aside at any level\"",
        "cumulative = true",
        "",
        "[search]",
        "shape = \"one global ordered pool, first admissible partner\"",
        "escalation = \"per player, the lowest level that admits a partner\"",
        "cross_division_gate = \"both divisions carry cross_admitted yes for the round\"",
        "",
        "[effective_band]",
        "rule = \"the score band of the live capacity sheet plus the band_widening of the division of the player taken first\"",
        "",
        "[unpaired]",
        "rule = \"a player no level admits a partner for is left unpaired\"",
        "",
        "[tolerance]",
        "rule = \"the tolerance of a recorded board is the lower of the admission levels its two players were admitted at\"",
        "bye_holder = %d" % bye_tolerance,
        "unpaired = %d" % unpaired_tolerance,
        "ineligible = %d" % ineligible_tolerance,
    ])

    write_lines(root / "penalty_precedence_policy.toml", [
        "# The order the four applied classes are worked in, and what each one",
        "# reaches. A class never reaches back into a stage before it.",
        "",
        "[order]",
        "sequence = [\"game\", \"match\", \"round\", \"tournament\"]",
        "",
        "[game]",
        "reaches = \"the game differential of the round it names\"",
        "leaves_untouched = \"the match result and the match points\"",
        "",
        "[match]",
        "reaches = \"the base match points of the round it names, which become the loss points\"",
        "leaves_untouched = \"the game differential and the result of the opponent\"",
        "",
        "[round]",
        "reaches = \"the round points after the round modifier has been applied\"",
        "floor = 0",
        "shortfall = \"recorded and carried nowhere\"",
        "",
        "[tournament]",
        "reaches = \"the event total after the last round\"",
        "floor = 0",
        "also_gates = \"prize eligibility and the penalty adjusted strength\"",
        "",
        "[expulsion]",
        "reaches = \"the participation state from the round it names onward\"",
        "class_of_applied_order = \"outside the four applied classes\"",
    ])

    (root / "tiebreak_rules.json").write_text(json.dumps({
        "event_reference": inst["event_reference"],
        "strength_scale": "thousandths",
        "rate_scale": 1000,
        "zero_strength_value": 0,
        "counted_bases": ["match", "bye", "void", "no_record"],
        "opponent_rate": {
            "numerator": "the event points of the opponent multiplied by the rate scale",
            "denominator": "the number of rounds the opponent was counted in, at least one",
            "rounding": "half_to_even_at_this_stage",
        },
        "opponent_strength": {
            "population": "the distinct opponents whose history row counts for strength",
            "aggregate": "the sum of the opponent rates divided by the population size",
            "rounding": "half_to_even_at_this_stage",
            "empty_population": "zero_strength_value",
        },
        "penalty_adjusted_strength": {
            "rule": "the opponent strength less the strength debit multiplied by the tournament penalty units",
            "floor": 0,
        },
        "ordering": [
            {"position": 1, "key": "event_points", "direction": "descending"},
            {"position": 2, "key": "adjusted_game_differential", "direction": "descending"},
            {"position": 3, "key": "opponent_strength", "direction": "descending"},
            {"position": 4, "key": "penalty_adjusted_strength", "direction": "descending"},
            {"position": 5, "key": "player_id", "direction": "ascending"},
        ],
    }, indent=1) + "\n", encoding="utf-8", newline="\n")

    (root / "prize_rules.json").write_text(json.dumps({
        "event_reference": inst["event_reference"],
        "pool": {
            "unit": "cents",
            "source": "the pool_cents parameter of the live sheet of the panel capacity workbook",
        },
        "share_table": [{"rank": rank, "basis_points": points} for rank, points
                        in enumerate(inst["policy"]["share_table"], start=1)],
        "tie_group": {
            "depth": "the tie_group_depth clause of the appeals procedure memorandum",
            "rule": "players adjacent in the standings and equal on every ordering key up to the depth form one group",
        },
        "group_amount": {
            "rule": "the pool multiplied by the summed basis points of the ranks the group occupies, divided by ten thousand",
            "rounding": "half_to_even_at_this_stage",
        },
        "split": {
            "base_share": "the group amount divided by the member count, discarding the remainder",
            "remainder": "one cent to each member in ascending player identifier order until the remainder is exhausted",
        },
        "eligibility": {
            "rule": "a player whose tournament penalty units reach the disqualify_units clause is not eligible",
            "forfeit": "the share of an ineligible member is added to the residue and is never redistributed",
        },
        "residue": {
            "rule": "the pool less every awarded cent",
        },
    }, indent=1) + "\n", encoding="utf-8", newline="\n")

    (root / "round_modifier_rules.json").write_text(json.dumps({
        "event_reference": inst["event_reference"],
        "applies_to": "the base match points of the round",
        "never_applies_to": "the game differential of the round",
        "rounding": "half_to_even_at_this_stage",
        "codes": [{"code": code, "numerator": num, "denominator": den}
                  for code, num, den in MODIFIER_CODES],
    }, indent=1) + "\n", encoding="utf-8", newline="\n")

    write_lines(root / "settlement_form_rules.toml", [
        "# How the delivered documents are written.",
        "",
        "[markers]",
        "absent = \"--\"",
        "note = \"an absent marker is an absence, never a zero\"",
        "",
        "[encoding]",
        "charset = \"utf-8\"",
        "line_ending = \"line feed\"",
        "trailing = \"exactly one line feed at the end of every document\"",
        "carriage_return = \"forbidden\"",
        "",
        "[delimited]",
        "header = \"always written, even when no row follows it\"",
        "empty_field = \"written as an empty field, never as the absent marker\"",
        "",
        "[json]",
        "indent = 1",
        "key_order = \"the order the schema reference lists\"",
        "empty_list = \"[]\"",
        "empty_object = \"{}\"",
        "",
        "[jsonl]",
        "separators = \"comma and colon with no spaces\"",
        "empty_document = \"an empty document is a single line feed\"",
    ])


# --------------------------------------------------------------------------
# the three papers that are not plain text
#
# Each carries values found nowhere else in the corpus. The workbook holds the
# score band, the bye cap, the prize pool in cents and the strength debit; the
# memorandum holds the point constants, the admission ladder and the penalty
# order; the directive holds the key positions of four ordered key families and
# the division ranks.
# --------------------------------------------------------------------------

SHEET_NAMES = ["capacity_working", "capacity_review", "capacity_final",
               "capacity_amended", "capacity_draft", "capacity_archive"]


def _capacity_block(inst, rng, live):
    band = inst["score_band"] if live else inst["score_band"] + rng.between(1, 3)
    byes = inst["max_byes"] if live else inst["max_byes"] + rng.between(1, 2)
    pool = inst["pool_cents"] if live else inst["pool_cents"] + rng.between(10000, 90000)
    debit = inst["strength_debit"] if live else inst["strength_debit"] + rng.between(5, 30)
    rows = [
        ["score_band", band, "points", "operative", "admission band in whole points"],
        ["score_band", band + rng.between(1, 4), "points", "withdrawn",
         "the band the first draw sheet carried"],
        ["max_byes", byes, "count", "operative", "cap on byes to one entrant"],
        ["max_byes", byes + 1, "count", "superseded", "cap before the panel sat"],
        ["pool_cents", pool, "cents", "operative", "settlement pool"],
        ["", "", "", "", ""],
        ["pool_cents", pool // 100, "crown", "withdrawn", "pool quoted in whole crowns"],
        ["strength_debit", debit, "thousandths", "operative",
         "debit against strength per penalty unit"],
        ["strength_debit", debit * 2, "thousandths", "indicative",
         "the customary debit of the preceding season"],
    ]
    return rows


def write_workbook(inst, root):
    rng = _pad_rng(inst, "workbook")
    live_index = inst["seed"] % 6
    names = rng.shuffled(SHEET_NAMES)
    sheets = {}
    for i, name in enumerate(names):
        live = i == live_index
        ref = inst["event_reference"] if live else rng.pick(inst["prior_references"])
        offset = 1 + (i % 3)
        rows = [["sheet_reference", ref, "", "", ""]]
        for _ in range(offset):
            rows.append(["", "", "", "", ""])
        rows.append(["parameter", "value", "unit", "status", "note"])
        rows.extend(_capacity_block(inst, rng, live))
        if not live and i == (live_index + 2) % 6:
            rows.append(["panel_note", "", "", "reference",
                         "cross filed against %s" % inst["event_reference"]])
        rows.append(["", "", "", "", ""])
        rows.append(["hall", "session", "seats", "marshals", "status"])
        for k in range(1, 27):
            rows.append(["H%02d" % rng.between(1, 12), k, rng.between(40, 260),
                         rng.between(2, 9), "operative"])
        sheets[name] = rows
    inst["live_sheet_name"] = names[live_index]
    write_xlsx(root / "panel_capacity_workbook.xlsx", sheets)


MEMO_CLAUSES = [
    ("bye_points", 3, "match points credited for a bye"),
    ("bye_game_delta", 2, "game differential credited for a bye"),
    ("void_points", 1, "match points credited to each side of a voided board"),
    ("unpaired_points", 0, "match points credited to a player left unpaired"),
    ("no_record_points", 0, "match points credited to an eligible player with no board"),
    ("round_points_floor", 0, "floor the round penalty leaves the round points at"),
    ("prize_disqualify_units", 2, "tournament penalty units that end prize eligibility"),
    ("tie_group_depth", 2, "ordering keys a prize tie group is formed on"),
    ("relaxation_rung_1", "score_band", "first constraint the ladder sets aside"),
    ("relaxation_rung_2", "repeat_opponent", "second constraint the ladder sets aside"),
    ("relaxation_rung_3", "division", "third constraint the ladder sets aside"),
    ("penalty_order_1", "game", "first applied penalty class"),
    ("penalty_order_2", "match", "second applied penalty class"),
    ("penalty_order_3", "round", "third applied penalty class"),
    ("penalty_order_4", "tournament", "fourth applied penalty class"),
]


def write_memo(inst, root):
    rng = _pad_rng(inst, "memo")
    lines = [
        "NINEFOLD CROWN APPEALS PANEL",
        "PROCEDURE MEMORANDUM",
        "",
        "Event identifier      %s" % inst["event_id"],
        "Event reference       %s" % inst["event_reference"],
        "Rounds settled        %d" % inst["rounds"],
        "",
        "A clause governs this settlement only when its status reads operative",
        "and its event reference is the reference printed above. A rescinded, a",
        "superseded and an indicative clause each record what the panel decided",
        "not to apply. Where two clauses carry one key, the operative one is the",
        "clause that governs and the others are kept for the record alone.",
        "",
        "CLAUSE REGISTER",
        "clause    status       reference     key                       value",
        "-------   ----------   -----------   -----------------------   ---------------",
    ]
    number = 100

    def clause(status, ref, key, value):
        nonlocal number
        number += 1
        lines.append("CL-%03d    %-10s   %-11s   %-23s   %s"
                     % (number, status, ref, key, value))

    for key, _canonical, _note in MEMO_CLAUSES:
        value = inst["memo_values"].get(key, _canonical)
        for _ in range(rng.between(1, 2)):
            bad = value
            if isinstance(value, int):
                bad = value + rng.between(1, 4)
            else:
                bad = rng.pick([v for v in ("score_band", "repeat_opponent",
                                            "division", "game", "match", "round",
                                            "tournament") if v != value])
            clause(rng.pick(["rescinded", "superseded"]),
                   rng.pick(inst["prior_references"]), key, bad)
        clause("operative", inst["event_reference"], key, value)
        if rng.chance(1, 3):
            bad = value + rng.between(1, 3) if isinstance(value, int) else value
            clause("indicative", inst["event_reference"], key, bad)

    lines.append("")
    lines.append("The register above is closed. No key it omits is settled here.")
    lines.append("")
    lines.append("PANEL ROSTER")
    lines.append("panel   member                     hall   sessions   status")
    lines.append("-----   ------------------------   ----   --------   ----------")
    surnames = ["Aldreth", "Bramwell", "Corvine", "Delaney", "Ebbsworth",
                "Fenmore", "Gaskill", "Harrowden", "Ilminster", "Jarrow",
                "Kelsey", "Lindsey", "Marchbank", "Norbury", "Oakhurst",
                "Pennard", "Quarrick", "Rushmere", "Sedgely", "Thurloe",
                "Underhill", "Vansittart", "Wexford", "Yardley"]
    for i in range(1, 141):
        lines.append("P%02d     %-24s   H%02d    %-8d   %s"
                     % (rng.between(1, 12), surnames[i % len(surnames)] + ", %s." % chr(65 + i % 26),
                        rng.between(1, 12), rng.between(1, 9),
                        "operative" if rng.chance(4, 5) else "withdrawn"))
    lines.append("")
    lines.append("END OF MEMORANDUM")
    write_pdf(root / "appeals_procedure_memo.pdf", lines)


KEY_FAMILIES = [
    ("tiebreak", ["event_points", "adjusted_game_differential", "opponent_strength",
                  "penalty_adjusted_strength", "player_id"]),
    ("pairing_order", ["running_points_descending", "running_differential_descending",
                       "division_rank_ascending", "seat_order_ascending",
                       "player_id_ascending"]),
    ("bye_order", ["byes_received_ascending", "running_points_ascending",
                   "running_differential_ascending", "seat_order_descending",
                   "player_id_ascending"]),
    ("void_reason", ["ineligible_player", "holds_bye", "cross_division",
                     "repeat_opponent", "score_band"]),
]


def write_directive(inst, root):
    rng = _pad_rng(inst, "directive")
    blocks = [
        ("p", "NINEFOLD CROWN STANDINGS PRECEDENCE DIRECTIVE"),
        ("p", "Event identifier %s, event reference %s, rounds settled %d."
              % (inst["event_id"], inst["event_reference"], inst["rounds"])),
        ("p", "A row of the key register governs only when its status reads "
              "operative and its event reference is the reference named above. "
              "A withdrawn row records an ordering the panel replaced. Within a "
              "family the keys are applied in ascending key position."),
    ]
    rows = [["event_reference", "revision", "key_family", "key_position",
             "key_name", "status"]]
    revision = 0
    for family, keys in KEY_FAMILIES:
        for shuffle_round in range(3):
            revision += 1
            order = rng.shuffled(keys)
            for pos, key in enumerate(order, start=1):
                rows.append([rng.pick(inst["prior_references"]), revision, family,
                             pos, key, "withdrawn"])
        revision += 1
        for pos, key in enumerate(inst["key_families"][family], start=1):
            rows.append([inst["event_reference"], revision, family, pos, key,
                         "operative"])
    while len(rows) < 196:
        revision += 1
        family, keys = rng.pick(KEY_FAMILIES)
        order = rng.shuffled(keys)
        for pos, key in enumerate(order, start=1):
            rows.append([rng.pick(inst["prior_references"]), revision, family, pos,
                         key, "withdrawn"])
    blocks.append(("table", rows))

    blocks.append(("p", "DIVISION RANK REGISTER"))
    rank_rows = [["event_reference", "division_id", "division_rank", "status"]]
    for div in DIVISIONS:
        rank_rows.append([rng.pick(inst["prior_references"]), div,
                          rng.between(1, 4), "withdrawn"])
        rank_rows.append([inst["event_reference"], div, inst["division_ranks"][div],
                          "operative"])
    rank_rows.append([inst["event_reference"], SHADOW_DIVISION, 9, "operative"])
    blocks.append(("table", rank_rows))
    blocks.append(("p", "END OF DIRECTIVE"))
    write_docx(root / "standings_precedence_directive.docx", blocks)


# --------------------------------------------------------------------------
# the delivered document schema, owned in one place
#
# publish() writes from this table and the shipped schema reference is generated
# from it, so the reference cannot drift away from the bytes it describes.
# --------------------------------------------------------------------------

SCHEMA = [
    ("normalised_entries.jsonl", "jsonl",
     ["player_id", "division_id", "seed_number", "rating_mr", "rating_source",
      "entry_seq", "folded_ids"],
     "one record per settled entrant, ascending player_id"),
    ("participation_ledger.csv", ",",
     ["player_id", "round_no", "state", "governing_code", "governing_seq"],
     "one row per entrant and round, ascending player_id then round_no"),
    ("round_match_candidates.csv", ",",
     ["round_no", "table_no", "player_a", "player_b", "sheet_revision",
      "source_seq"],
     "one row per applicable recorded board, ascending round_no then table_no"),
    ("match_result_ledger.csv", ",",
     ["round_no", "table_no", "player_a", "player_b", "result_code", "basis",
      "games_a", "games_b", "delta_a"],
     "one row per candidate board, ascending round_no then table_no"),
    ("round_eligibility_ledger.csv", ",",
     ["round_no", "player_id", "division_id", "eligible", "state",
      "running_points", "running_delta"],
     "one row per entrant and round, ascending round_no then player_id"),
    ("bye_ledger.csv", ",",
     ["round_no", "division_id", "player_id", "byes_before", "basis"],
     "one row per awarded bye, ascending round_no then division_id"),
    ("authoritative_pairing_ledger.csv", ",",
     ["round_no", "board_no", "player_a", "player_b", "division_a", "division_b",
      "admission_level", "points_a", "points_b"],
     "one row per authoritative board, ascending round_no then board_no"),
    ("void_adjudication_ledger.csv", ",",
     ["round_no", "table_no", "player_a", "player_b", "void_reason",
      "violation_level", "tolerance", "scored_a", "scored_b"],
     "one row per voided board, ascending round_no then table_no"),
    ("round_score_ledger.csv", ",",
     ["round_no", "player_id", "division_id", "basis", "base_points",
      "modifier_code", "modified_points", "round_points", "game_delta"],
     "one row per eligible entrant and round, ascending round_no then player_id"),
    ("penalty_application_ledger.psv", "|",
     ["round_no", "player_id", "penalty_class", "magnitude", "notice_seq",
      "value_before", "value_after", "shortfall"],
     "one row per applied notice, ascending round_no then player_id then the"
     " applied class order"),
    ("opponent_history_ledger.csv", ",",
     ["round_no", "player_id", "opponent_id", "counts_for_strength", "source"],
     "one row per encounter side, ascending round_no then player_id then"
     " opponent_id"),
    ("opponent_strength_ledger.csv", ",",
     ["player_id", "opponent_count", "rate_sum", "opponent_strength",
      "penalty_units", "penalty_adjusted_strength"],
     "one row per entrant, ascending player_id"),
    ("standings_ledger.csv", ",",
     ["rank", "player_id", "division_id", "event_points", "adjusted_delta",
      "opponent_strength", "penalty_adjusted_strength", "penalty_units",
      "prize_eligible"],
     "one row per entrant, ascending rank"),
    ("settlement_manifest.json", "json",
     ["event_id", "event_reference", "round_count", "player_count", "core_digest",
      "publication_digest", "documents"],
     "the core digest covers the six core documents in the order the artifact"
     " contract lists them; the publication digest covers every other delivered"
     " document in that same order; each documents entry carries name, sha256 and"
     " bytes in that key order, where name is the file name, sha256 the lowercase"
     " hexadecimal digest of its bytes and bytes its byte length as a JSON number"),
    ("pairing_fallback_ledger.csv", ",",
     ["round_no", "board_no", "player_a", "player_b", "admission_level",
      "relaxed_constraints"],
     "one row per board admitted above level zero, ascending round_no then"
     " board_no"),
    ("repeat_opponent_audit.tsv", "\t",
     ["player_id", "opponent_id", "meetings", "rounds"],
     "one row per ordered pair that met more than once, ascending player_id then"
     " opponent_id"),
    ("unpaired_ledger.tsv", "\t",
     ["round_no", "division_id", "player_id", "running_points", "reason"],
     "one row per eligible entrant left with neither a board nor a bye,"
     " ascending round_no then player_id"),
    ("pairing_constraint_report.json", "json",
     ["event_reference", "rounds"],
     "one rounds entry per round in ascending order, each carrying round_no,"
     " boards, byes, unpaired, level_counts, cross_division_boards,"
     " repeat_boards and voided_boards, where level_counts is a JSON object"
     " carrying level_0, level_1, level_2 and level_3 in that key order, each"
     " written even when the level admitted no board"),
    ("game_differential_ledger.psv", "|",
     ["player_id", "rounds_counted", "raw_delta", "game_penalty_units",
      "adjusted_delta"],
     "one row per entrant, ascending player_id"),
    ("tiebreak_resolution_ledger.csv", ",",
     ["rank", "player_id", "next_player_id", "separating_position",
      "separating_key"],
     "one row per adjacent pair in the standings, ascending rank"),
    ("final_ranking.json", "json",
     ["event_id", "event_reference", "round_count", "player_count", "ranking"],
     "one ranking entry per entrant in ascending rank, each carrying rank,"
     " player_id, event_points, adjusted_delta, opponent_strength and"
     " penalty_adjusted_strength"),
    ("player_audit_trace.jsonl", "jsonl",
     ["player_id", "division_id", "seed_number", "rounds", "event_points",
      "adjusted_delta", "opponent_strength", "rank", "awarded_cents"],
     "one record per entrant, ascending player_id; each rounds entry carries"
     " round_no, state, basis, round_points and game_delta"),
    ("prize_allocation_ledger.csv", ",",
     ["rank", "player_id", "group_id", "group_basis_points",
      "group_amount_cents", "members", "base_share_cents", "remainder_cent",
      "prize_eligible", "awarded_cents"],
     "one row per entrant whose prize group carries group_basis_points above"
     " zero, ascending rank"),
    ("prize_tie_split.tsv", "\t",
     ["group_id", "rank_span", "members", "group_basis_points",
      "group_amount_cents", "base_share_cents", "remainder_cents",
      "player_ids"],
     "one row per tie group holding more than one member, ascending group_id"),
    ("standings_by_division.xml", "xml",
     ["settlement", "division", "entrant"],
     "divisions in ascending report_order, entrants in ascending rank; the root"
     " settlement element carries the attributes event_id and event_reference, a"
     " division element carries id, report_order and entrants, and an entrant"
     " element carries rank, player_id, event_points, adjusted_delta,"
     " opponent_strength and awarded_cents, each in that attribute order"),
    ("settlement_control_totals.conf", "conf",
     ["event", "totals", "pairing", "prize"],
     "four sections in this order, keys inside a section in the order the stage"
     " specification lists them"),
    ("event_settlement_summary.md", "md",
     ["headings"],
     "the heading order and the sentence shapes the worked examples paper fixes"),
]

for _div in DIVISIONS:
    SCHEMA.append(("division_report_%s.json" % _div, "json",
                   ["division_id", "in_force", "report_order", "seated_players",
                    "paired_boards", "byes_awarded", "voided_boards",
                    "points_total", "game_delta_total", "awarded_cents",
                    "award_share_ratio", "top_player"],
                   "one report per division named in force by the topology,"
                   " written even when no entrant was seated in it; in_force is a"
                   " JSON boolean, award_share_ratio a JSON string of nine decimal"
                   " places, top_player a JSON string, and every other value a JSON"
                   " number"))

SCHEMA_BY_NAME = {name: (kind, cols, note) for name, kind, cols, note in SCHEMA}


def write_schema_reference(inst, root):
    lines = [
        "# Delivered document schema reference",
        "",
        "Every document below is written under the output directory with the",
        "exact name given. The column list of a delimited document is its header",
        "row in this order. The key list of a JSON document is its key order. The",
        "serialisation and digest contract governs encoding, line endings,",
        "indentation, empty shapes and trailing line feeds.",
        "",
        "A quantity described as whole is published as a whole number with no",
        "sign for zero. A ratio is published at exactly nine decimal places. A",
        "strength is published in thousandths as a whole number. A prize amount",
        "is published in whole cents.",
        "",
    ]
    for name, kind, cols, note in SCHEMA:
        if kind == "jsonl":
            shape = "one JSON object per line"
        elif kind == "json":
            shape = "one JSON object"
        elif kind == "xml":
            shape = "XML"
        elif kind == "conf":
            shape = "sectioned key and value text"
        elif kind == "md":
            shape = "free text"
        elif kind == "\t":
            shape = "tab separated"
        elif kind == "|":
            shape = "pipe separated"
        else:
            shape = "comma separated"
        lines.append("## %s" % name)
        lines.append("")
        lines.append("- shape: %s" % shape)
        if kind in ("jsonl", "json"):
            lines.append("- keys: %s" % ", ".join(cols))
        elif kind in (",", "\t", "|"):
            lines.append("- header: %s" % ", ".join(cols))
        else:
            lines.append("- structure: %s" % ", ".join(cols))
        lines.append("- rows: %s" % note)
        lines.append("")
    write_lines(root / "output_schema_reference.md", lines)


def write_guidance_papers(inst, root):
    write_lines(root / "open_this_first.txt", [
        "NINEFOLD CROWN SETTLEMENT WORKING PAPERS",
        "",
        "Event %s, reference %s, %d rounds settled." % (
            inst["event_id"], inst["event_reference"], inst["rounds"]),
        "",
        "The published settlement of this event was withdrawn after the appeals",
        "panel found that the hall software had worked the rounds in the wrong",
        "order. These papers are the whole evidence base. They were minted for",
        "this event alone and nothing outside them settles anything here.",
        "",
        "Read in this order:",
        "",
        "  1. crown_settlement_overview.md   the fourteen stages and their papers",
        "  2. paper_lineage.md               which paper feeds which stage",
        "  3. glossary_and_field_dictionary.md",
        "  4. output_schema_reference.md     the shape of every delivered document",
        "  5. serialisation_and_digest_contract.md",
        "  6. crownsettle_program_contract.md",
        "  7. the fourteen spec_stage_p01 to p14 papers, in order",
        "",
        "A file name here describes the role a paper plays, never the values it",
        "carries. Three papers are not plain text and carry values that appear",
        "nowhere else. Open every paper before deciding it is irrelevant.",
        "",
        "Nothing in these papers is the settlement. The recorded pairings, the",
        "recorded byes and the recorded results are evidence of what the hall did,",
        "and the hall was wrong. The settlement is recomputed from them.",
    ])

    write_lines(root / "crown_settlement_overview.md", [
        "# Crown settlement overview",
        "",
        "Event %s, reference %s. The settlement is recomputed in fourteen stages."
        % (inst["event_id"], inst["event_reference"]),
        "",
        "Stages one to four are worked once over the whole event. Stages five to",
        "eleven are worked round by round, in that order, and a round is closed",
        "before the round after it opens: stage seven of round four may not be",
        "worked until stage eleven of round three has closed, because the running",
        "state stage seven orders on is the state stage eleven left behind.",
        "Stages twelve to fourteen are worked once, after the last round closed.",
        "",
        "| stage | subject | specification |",
        "|---|---|---|",
        "| P01 | entry normalisation | spec_stage_p01_entry_normalisation.md |",
        "| P02 | participation state | spec_stage_p02_participation_state.md |",
        "| P03 | candidate board assembly | spec_stage_p03_candidate_boards.md |",
        "| P04 | game evidence resolution | spec_stage_p04_game_evidence.md |",
        "| P05 | round eligibility | spec_stage_p05_round_eligibility.md |",
        "| P06 | bye assignment | spec_stage_p06_bye_assignment.md |",
        "| P07 | authoritative pairing | spec_stage_p07_authoritative_pairing.md |",
        "| P08 | admissibility and voids | spec_stage_p08_admissibility_voids.md |",
        "| P09 | round scoring | spec_stage_p09_round_scoring.md |",
        "| P10 | penalty application | spec_stage_p10_penalty_application.md |",
        "| P11 | opponent history | spec_stage_p11_opponent_history.md |",
        "| P12 | opponent strength | spec_stage_p12_opponent_strength.md |",
        "| P13 | standings and tiebreaks | spec_stage_p13_standings_tiebreaks.md |",
        "| P14 | settlement and publication | spec_stage_p14_settlement_publication.md |",
        "",
        "## What the round loop couples",
        "",
        "A board the authoritative pairing admits at a strict level makes the",
        "recorded board of the same players answerable at that level, and a",
        "recorded board the panel voids credits the void points instead of the",
        "played result. The running points a void changes are the running points",
        "the next round orders and bands on, so a single misread round moves every",
        "round after it, the opponent strength of every player who met anybody in",
        "it, and the prize settlement at the end.",
        "",
        "## What is settled elsewhere",
        "",
        "The arithmetic policy, the boundary conventions, the revision precedence,",
        "the unit register, the pairing ladder, the penalty order, the tiebreak",
        "rules, the prize rules and the round modifier rules each sit in their own",
        "paper. A stage specification names the paper it takes a rule from and",
        "does not restate its content.",
    ])

    write_lines(root / "paper_lineage.md", [
        "# Paper lineage",
        "",
        "| paper | stage it feeds | what it settles |",
        "|---|---|---|",
        "| entry_roster_register.csv | P01 | the filed entries and their revisions |",
        "| entry_alias_register.csv | P01, P03 | the identifier closure |",
        "| rating_return_sheet.psv | P01 | the filed rating returns |",
        "| seat_assignment_register.csv | P01 | the declared seat order |",
        "| membership_standing_register.csv | P02 | lapsed and restored standing |",
        "| withdrawn_entry_journal.tsv | P01 | which revisions were withdrawn |",
        "| division_topology.xml | P01, P14 | the divisions in force and the event reference |",
        "| status_change_journal.tsv | P02 | drops, reentries, absences, reinstatements |",
        "| penalty_notice_register.psv | P02, P09, P10 | the notices and their classes |",
        "| appeal_disposition_journal.jsonl | P10 | how each notice was disposed of |",
        "| recorded_pairing_table.csv | P03, P08 | the boards the hall recorded |",
        "| match_result_sheets.ndjson | P04 | the filed result sheets |",
        "| game_records.csv | P04 | the game level evidence |",
        "| bye_award_journal.tsv | P08 | the byes the hall recorded |",
        "| round_configuration_register.csv | P09 | the per round point values and modifier codes |",
        "| division_admission_matrix.csv | P06, P07 | cross admission, bye override, band widening, default rating |",
        "| source_priority_register.csv | P04 | the rank of each evidence source |",
        "| panel_capacity_workbook.xlsx | P06, P07, P12, P14 | the score band, the bye cap, the strength debit and the prize pool |",
        "| appeals_procedure_memo.pdf | P06, P07, P08, P09, P10, P14 | the point constants, the admission ladder, the penalty order and the prize clauses |",
        "| standings_precedence_directive.docx | P06, P07, P08, P13 | the key positions of four key families and the division ranks |",
        "| reporting_division_roster.conf | P14 | the report order of each division |",
        "| unit_register_dictionary.toml | P01 | rating unit conversion |",
        "| rounding_and_arithmetic_policy.yaml | every stage | where a rounding sits |",
        "| boundary_conventions.yaml | P02, P10 | the round interval and its edges |",
        "| revision_precedence.toml | P01, P03, P04, P10, P14 | which filing governs |",
        "| pairing_precedence_policy.toml | P07, P08 | the ladder and the tolerance rule |",
        "| penalty_precedence_policy.toml | P09, P10 | what each class reaches |",
        "| tiebreak_rules.json | P12, P13 | the strength arithmetic and the ordering |",
        "| prize_rules.json | P14 | the share table and the split |",
        "| round_modifier_rules.json | P09 | the modifier fractions |",
        "| settlement_form_rules.toml | P14 | absent markers and document form |",
        "| output_schema_reference.md | P14 | the shape of every document |",
        "| serialisation_and_digest_contract.md | P14 | encoding and digests |",
        "| crownsettle_program_contract.md | the delivered program | its interface |",
        "| worked_examples.md | P14 | the form of the free text documents |",
        "",
        "## Navigation papers",
        "",
        "These carry no rule of their own and point at the papers that do.",
        "",
        "- open_this_first.txt names the reading order.",
        "- crown_settlement_overview.md names the fourteen stages and their",
        "  specifications.",
        "- paper_lineage.md is this map.",
        "- glossary_and_field_dictionary.md defines the terms the specifications use",
        "  and separates the field names that look alike.",
        "- known_traps_and_footguns.md registers which stage owns each decision the",
        "  settlement turns on, and states no rule itself.",
        "- corpus_sentinel_note.txt names the branches this event leaves unreached.",
        "",
        "## Papers that govern nothing",
        "",
        "Three papers were left in the bundle by the hall desk and settle no part",
        "of this event. They are kept because the panel minute refers to them.",
        "",
        "- legacy_season_extract.csv carries a previous season and no row of it",
        "  belongs to this event reference.",
        "- spectator_gate_returns.json carries hall admissions and no settlement",
        "  quantity is derived from attendance.",
        "- night_desk_audit.db carries desk notes filed against other references.",
        "",
        "Any figure taken from those three is a figure taken from outside this",
        "event.",
    ])

    write_lines(root / "glossary_and_field_dictionary.md", [
        "# Glossary and field dictionary",
        "",
        "- **admission level** the rung of the pairing ladder a board was admitted",
        "  at, zero when no constraint was set aside.",
        "- **adjusted game differential** the sum of the round game differentials",
        "  of a player after the game penalties have been taken off.",
        "- **basis** the reason a round score has the value it has: match, bye,",
        "  void, unpaired or no_record.",
        "- **board** a pairing the authoritative process produced, numbered in the",
        "  order the pairs were formed.",
        "- **candidate board** an applicable row of the recorded pairing table.",
        "- **counts for strength** whether an encounter contributes its opponent to",
        "  the opponent strength population.",
        "- **effective band** the score band of the live capacity sheet plus the",
        "  band widening of the division of the player taken first.",
        "- **event points** the sum of the round points of a player less the",
        "  tournament penalty, floored at zero.",
        "- **folded identifier** an entry identifier the alias closure resolves to",
        "  another player identifier.",
        "- **milli rating** the base rating unit, one thousandth of a rating point.",
        "- **opponent rate** the event points of an opponent scaled to thousandths",
        "  and divided by the rounds that opponent was counted in.",
        "- **round tick** the clock the status change journal is written on.",
        "- **running points** the event points of a player through the rounds",
        "  already closed, with no tournament penalty taken off.",
        "- **seat order** the derived order of entrants on their normalised rating.",
        "- **table** a board the hall recorded, numbered by the hall.",
        "- **tolerance** the lower of the admission levels the two players of a",
        "  recorded board were admitted at.",
        "- **void** a recorded board the panel set aside.",
        "",
        "## Field names that look alike",
        "",
        "- `declared_seed` on the seat assignment register is what the hall",
        "  published. `seed_number` on the delivered entry record is derived.",
        "- `sheet_revision` on the recorded pairing table and `sheet_seq` on the",
        "  result sheets are different sequences on different papers.",
        "- `magnitude` on a penalty notice is a count of units, not a point value,",
        "  except for the round class where the policy paper says what it reaches.",
        "- `running_points` is a running figure inside the round loop and",
        "  `event_points` is the closed figure after the last round.",
        "- `points_a` on the authoritative pairing ledger is a running figure at",
        "  the opening of that round, not a result.",
    ])

    write_lines(root / "known_traps_and_footguns.md", [
        "# Decisions this settlement turns on",
        "",
        "This register names the decisions the panel had to settle and the stage",
        "that owns each one. It states which paper carries the rule and states",
        "nothing about how the rule reads: the stage specification is the only",
        "normative text. A decision named here without being read there is a",
        "decision not made.",
        "",
        "| # | decision | owning stage |",
        "|---|---|---|",
        "| 1 | which filing of an entry governs when a withdrawn revision sits above it | P01 |",
        "| 2 | how an alias chain and an alias cycle resolve | P01 |",
        "| 3 | whether the rating comes from the roster quotation or a filed return | P01 |",
        "| 4 | what an absent rating quotation is worth | P01 |",
        "| 5 | which unit a rating quotation is converted through | P01 |",
        "| 6 | whether the seat order is the declared seed or a derived one | P01 |",
        "| 7 | what happens to an entrant whose division is not in force | P01 |",
        "| 8 | which round a status change on a round boundary belongs to | P02 |",
        "| 9 | how far an absence reaches compared with a drop | P02 |",
        "| 10 | what a lapsed membership standing does to eligibility | P02 |",
        "| 11 | which recorded pairing row governs a table | P03 |",
        "| 12 | the order the five evidence levels are tried in | P04 |",
        "| 13 | whether a concession outranks the game count | P04 |",
        "| 14 | what a board with no evidence at all resolves to | P04 |",
        "| 15 | whether an adjudicated result moves the game differential | P04 |",
        "| 16 | which entrants the bye candidate set holds when the cap is reached | P06 |",
        "| 17 | the key positions the bye is selected on | P06 |",
        "| 18 | the key positions the pairing pool is ordered on | P07 |",
        "| 19 | the order the pairing ladder sets constraints aside in | P07 |",
        "| 20 | what the effective band of a board is | P07 |",
        "| 21 | which constraints a cross division board needs both divisions to admit | P07 |",
        "| 22 | how the tolerance of a recorded board is taken from two admission levels | P08 |",
        "| 23 | the precedence of the five void reasons | P08 |",
        "| 24 | what a voided board credits each side | P08 |",
        "| 25 | what the holder of the authoritative bye is credited when the recorded board is voided | P08 |",
        "| 26 | where the round modifier sits among the penalty steps | P09 |",
        "| 27 | whether the round modifier reaches the game differential | P09 |",
        "| 28 | what a round penalty does when it exceeds the round points | P09 |",
        "| 29 | whether a match penalty moves the result of the opponent | P09 |",
        "| 30 | whether a voided encounter enters the repeat opponent ledger | P11 |",
        "| 31 | whether a voided encounter enters the opponent strength population | P11 |",
        "| 32 | whether a bye creates an opponent | P11 |",
        "| 33 | where the two roundings of the strength arithmetic sit | P12 |",
        "| 34 | what a player with no counted opponent is credited | P12 |",
        "| 35 | which ordering key separates two entrants first | P13 |",
        "| 36 | how deep a prize tie group is formed | P14 |",
        "| 37 | what happens to the share of an ineligible member | P14 |",
        "| 38 | where the remainder cents of a split go | P14 |",
        "| 39 | whether a division with no entrant is reported | P14 |",
        "| 40 | which sheet of the capacity workbook is live | P06, P07, P12, P14 |",
    ])

    if inst["profile"] == BRANCH_FIXTURE_PROFILE:
        unreached = ["  none"]
    else:
        unreached = [
            "  STANDING_REINSTATE        no journal row of this event carries the",
            "                            reinstate change code, so only a reentry",
            "                            exercises the restoring branch here.",
            "  ENTRY_STATUS_VOIDED       no roster row of this event carries the voided",
            "                            entry status, so only the withdrawn status",
            "                            exercises the exclusion here.",
        ]
    write_lines(root / "corpus_sentinel_note.txt", [
        "COVERAGE SENTINEL",
        "",
        "This event does not reach every branch the specifications describe. The",
        "settlement program is still answerable for the branches it leaves",
        "unreached, because the same program settles other events.",
        "",
        "Branches this event leaves unreached:",
        "",
    ] + unreached + [
        "",
        "Do not conclude from a quiet ledger that a rule is inert. Read the stage",
        "specification and implement every branch it states.",
    ])

    write_lines(root / "worked_examples.md", [
        "# Worked examples",
        "",
        "The figures below belong to an invented event, NC-0000-A0, with three",
        "rounds and four entrants. They fix the FORM of the two free text",
        "documents and of the sectioned control totals. Take shape from them and",
        "no figure.",
        "",
        "## event_settlement_summary.md",
        "",
        "```",
        "# Settlement summary NC-0000-A0",
        "",
        "Event EV-0000 settled over 3 rounds with 4 entrants seated.",
        "",
        "## Standings",
        "",
        "| rank | player_id | division_id | event_points | adjusted_delta |",
        "|---|---|---|---|---|",
        "| 1 | PL-AA-0001 | dv_arbor | 7 | 3 |",
        "| 2 | PL-AA-0002 | dv_arbor | 4 | 0 |",
        "| 3 | PL-AA-0003 | dv_brine | 4 | -1 |",
        "| 4 | PL-AA-0004 | dv_brine | 0 | -2 |",
        "",
        "## Pairing",
        "",
        "Boards admitted at level 0: 4. Level 1: 1. Level 2: 0. Level 3: 0.",
        "Byes awarded: 2. Boards voided: 1. Entrants left unpaired: 0.",
        "",
        "## Settlement",
        "",
        "Pool 100000 cents. Awarded 99998 cents. Residue 2 cents.",
        "Tie groups holding more than one member: 1.",
        "```",
        "",
        "## settlement_control_totals.conf",
        "",
        "```",
        "[event]",
        "event_id = EV-0000",
        "event_reference = NC-0000-A0",
        "round_count = 3",
        "player_count = 4",
        "",
        "[totals]",
        "round_points_total = 15",
        "game_delta_total = 0",
        "penalty_units_total = 1",
        "points_per_round_ratio = 1.250000000",
        "",
        "[pairing]",
        "boards_total = 5",
        "byes_total = 2",
        "voided_total = 1",
        "unpaired_total = 0",
        "level_1_boards = 1",
        "level_2_boards = 0",
        "level_3_boards = 0",
        "",
        "[prize]",
        "pool_cents = 100000",
        "awarded_cents = 99998",
        "residue_cents = 2",
        "tie_groups = 1",
        "award_share_ratio = 0.999980000",
        "```",
        "",
        "A section holds its keys in the order printed above. A ratio carries",
        "exactly nine decimal places. A whole quantity carries no decimal point.",
    ])

    write_lines(root / "serialisation_and_digest_contract.md", [
        "# Serialisation and digest contract",
        "",
        "## Encoding",
        "",
        "Every delivered document is UTF-8 with line feed line endings, no",
        "carriage return anywhere, and exactly one line feed at the end. A",
        "delimited document writes its header row even when no row follows it. A",
        "JSON document is written with an indent of one space and the key order",
        "the schema reference lists; a colon and one space separate a key from its",
        "value, and a line that continues ends with a comma and no space. A JSON",
        "lines document writes one compact",
        "object per line with a comma and a colon separator and no spaces, and its",
        "keys in the schema order.",
        "",
        "## Numbers",
        "",
        "A whole quantity is written as a decimal integer with no plus sign, no",
        "thousands separator and no decimal point. Zero is written as 0. A ratio",
        "is written with exactly nine digits after the decimal point. A strength",
        "is written in thousandths as a whole number. A prize amount is written in",
        "whole cents.",
        "",
        "## Empty shapes",
        "",
        "An empty delimited document is its header row and one line feed. An empty",
        "JSON list is written []. An empty JSON object is written {}. An empty JSON",
        "lines document is a single line feed. A field with no value in a",
        "delimited document is an empty field.",
        "",
        "## XML",
        "",
        "An XML document opens with the declaration",
        "`<?xml version=\"1.0\" encoding=\"UTF-8\"?>` on its own line. Indentation is",
        "one space per level of nesting. An element that carries no child element is",
        "written as a single self closing tag with one space between the last",
        "attribute and the closing slash. An element that carries child elements is",
        "written as an opening tag, its children each on their own line, and a",
        "closing tag at the indentation of the opening tag. Attribute values are",
        "written in double quotes in the order the stage specification gives.",
        "",
        "## Lists inside a field",
        "",
        "A list written inside one delimited field joins its members with a plus",
        "sign and no spaces, in the order the stage specification gives. A list",
        "written inside a JSON value is a JSON array in that same order.",
        "",
        "## Digests",
        "",
        "The settlement manifest carries two digests, each the lowercase",
        "hexadecimal SHA-256 of a concatenation of document bytes with no",
        "separator.",
        "",
        "- `core_digest` covers the six core documents, in the order the artifact",
        "  contract of the settlement stage lists them.",
        "- `publication_digest` covers every other delivered document except the",
        "  manifest itself, in the order the artifact contract of the settlement",
        "  stage lists them.",
        "",
        "The manifest also carries one entry per delivered document except itself,",
        "each with the document name, the lowercase hexadecimal SHA-256 of its",
        "bytes and its byte length, in that same contract order.",
    ])

    write_lines(root / "crownsettle_program_contract.md", [
        "# Settlement program contract",
        "",
        "The delivered program settles one event from one directory of working",
        "papers. It is the same program for every event: nothing about this event",
        "may sit inside it.",
        "",
        "## Interface",
        "",
        "It accepts `--data <directory>` and `--out <directory>`, in either order.",
        "It creates the output directory when it is absent, writes every declared",
        "document there, exits zero and writes nothing else anywhere.",
        "",
        "## Restrictions",
        "",
        "- Python standard library only. No package is installed at run time.",
        "- The three papers that are not plain text are read by the program",
        "  itself. It does not require them to be converted first.",
        "- Exact rational arithmetic throughout. No binary floating point in any",
        "  derivation.",
        "- No value this event carries is held inside the program: no identifier,",
        "  control value, threshold, boundary, unit conversion, rung order,",
        "  applicable or excluded status list, or key order. Each is read from the",
        "  directory the program is pointed at. The vocabulary the specifications",
        "  themselves define, such as state, basis, class, code and key names, is",
        "  not a value of the event.",
        "- The input directory is left exactly as it was found.",
        "- Two runs over one input directory produce identical bytes, and so does",
        "  the same event placed under another directory name.",
        "- The program derives its own answer. It never reads a document from",
        "  beside its input directory and copies it out.",
        "",
        "## Failure",
        "",
        "A paper the specifications require and the directory does not hold is a",
        "failure: the program exits non zero and writes no document.",
    ])


# --------------------------------------------------------------------------
# the fourteen stage specifications
#
# These are the only normative texts. Every rule the settlement turns on is
# stated here in full, with the paper each input is read from named.
# --------------------------------------------------------------------------


def write_stage_specs(inst, root):
    ref = inst["event_reference"]

    write_lines(root / "spec_stage_p01_entry_normalisation.md", [
        "# P01 entry normalisation",
        "",
        "Produces one settled entrant record per player of this event.",
        "",
        "## Which rows are in scope",
        "",
        "A row of any register governs only when its `event_reference` equals the",
        "`event_reference` of `division_topology.xml`. Every other row governs",
        "nothing, whatever else it carries.",
        "",
        "## The identifier closure",
        "",
        "`entry_alias_register.csv` maps an `alias_id` to a `canonical_id`. Resolve",
        "an identifier by following the mapping until an identifier is reached that",
        "the register does not carry as an `alias_id`. That identifier is the",
        "player identifier.",
        "",
        "When the walk revisits an identifier it has already seen, the mapping is a",
        "cycle. The player identifier of every member of a cycle is the",
        "lexicographically lowest identifier in that cycle.",
        "",
        "Two or more entry identifiers may resolve to one player identifier. They",
        "form one cluster and the cluster is one entrant.",
        "",
        "## Which filing governs",
        "",
        "Take the rows of `entry_roster_register.csv` whose resolved identifier is",
        "the player identifier. Keep only rows whose `entry_status` is in the",
        "applicable list of the `entry_roster` section of `revision_precedence.toml`",
        "and drop every row whose status is in the excluded list of that section. Of",
        "the rows that remain take the one with the highest `revision_seq`, and",
        "where two rows share that value take the one with the highest `entry_seq`.",
        "That row is the governing filing. Its `entry_seq` is the `entry_seq` of the",
        "entrant.",
        "",
        "A withdrawn or voided row is out of scope whatever its `revision_seq` is.",
        "An entrant whose rows are all out of scope is not an entrant of this event.",
        "",
        "The cluster of an entrant is the distinct `entry_id` values of the rows",
        "that remained in scope above. `folded_ids` is every member of the cluster",
        "other than the player identifier, in ascending order, written as a JSON",
        "array. An entrant whose cluster holds one identifier carries an empty",
        "array.",
        "",
        "## The division",
        "",
        "The division of an entrant is the `division_id` of the governing filing. An",
        "entrant whose division `division_topology.xml` does not carry with",
        "`in_force` equal to `yes` is not an entrant of this event and appears in no",
        "delivered document.",
        "",
        "## The rating",
        "",
        "Take the rows of `rating_return_sheet.psv` whose `player_ref` resolves to",
        "the player identifier, keep only those whose `return_status` is in the",
        "applicable list of the `rating_return` section of",
        "`revision_precedence.toml`, and take the one with the highest `return_seq`.",
        "When such a row exists the rating is quoted by that row and",
        "`rating_source` is `return`. When no such row exists the rating is quoted",
        "by the governing roster filing and `rating_source` is `roster`.",
        "",
        "A quotation carries a value and a unit. Convert it into milli rating",
        "through the entry of `unit_register_dictionary.toml` whose name is the",
        "unit the quoting row carries: multiply the value by the numerator, divide",
        "by the denominator and round half to even. The result is `rating_mr`.",
        "",
        "A quotation whose value is the absent marker of `settlement_form_rules.toml`",
        "is an absence. The rating of that entrant is the `default_rating_mr` of the",
        "`division_admission_matrix.csv` row for the division of the entrant and",
        "round one, and `rating_source` is `default`. An absence is never a zero.",
        "",
        "## The seat order",
        "",
        "`seed_number` is derived and never read. Order every entrant of this event",
        "by `rating_mr` descending, and where two entrants share a rating by player",
        "identifier ascending. The first entrant carries `seed_number` one and the",
        "numbers run without a gap.",
        "",
        "The `declared_seed` column of `seat_assignment_register.csv` is what the",
        "hall published. It is not the seat order of this settlement.",
        "",
        "## Delivered",
        "",
        "`normalised_entries.jsonl`, one record per entrant in ascending player",
        "identifier order.",
    ])

    write_lines(root / "spec_stage_p02_participation_state.md", [
        "# P02 participation state",
        "",
        "Produces the state of every entrant in every round of the event.",
        "",
        "## The round of a tick",
        "",
        "`status_change_journal.tsv` is written on the round tick clock. Round",
        "intervals are start inclusive and end exclusive and each spans the",
        "`ticks_per_round` of `boundary_conventions.yaml`. The round of a tick is",
        "the tick divided by `ticks_per_round`, discarding the remainder, with one",
        "added. A tick that lands exactly on a round boundary therefore belongs to",
        "the later of the two rounds it touches.",
        "",
        "## The governing change",
        "",
        "For an entrant and a round, take the applicable journal rows of that",
        "entrant whose round is at most that round, in ascending round then",
        "ascending `note_seq` order, and apply them in that order from a starting",
        "state of `seated`:",
        "",
        "- `drop` sets the state to `dropped` and it persists into later rounds.",
        "- `reentry` sets the state to `seated` and it persists into later rounds.",
        "- `reinstate` sets the state to `seated` and it persists into later rounds.",
        "- `absence` sets the state to `absent` for its own round alone and reaches",
        "  no later round.",
        "",
        "`governing_code` is the change code of the last applied row that still",
        "reaches the round and `governing_seq` its `note_seq`. An absence of an",
        "earlier round reaches no later round, so it never governs one. An entrant",
        "no row reached carries the code `none` and the sequence zero.",
        "",
        "## Membership standing",
        "",
        "`membership_standing_register.csv` is keyed on the `membership_ref` of the",
        "governing roster filing of the entrant. Take the applicable rows of that",
        "reference whose `effective_round` is at most the round, and of those the",
        "one with the highest `effective_round`, breaking a tie on the highest",
        "`notice_seq`. A `lapsed` standing sets the state to `barred`. A `current`",
        "or `restored` standing leaves the state as the journal left it.",
        "",
        "## Expulsion",
        "",
        "An applicable row of `penalty_notice_register.psv` whose `penalty_class` is",
        "`expulsion` sets the state to `barred` for its `effective_round` and every",
        "round after it. No boundary arithmetic is applied to an `effective_round`.",
        "",
        "`barred` outranks every other state. It is set by the standing register and",
        "by an expulsion notice and by nothing else, and no journal row lifts it. A",
        "bar set by an expulsion holds for its `effective_round` and every round",
        "after it. A bar set by a lapsed standing holds for as long as that lapsed",
        "row is the governing standing of the round, and it ends in the first round",
        "a later `current` or `restored` row governs. When an expulsion bars an",
        "entrant the `governing_code` of that",
        "round is `expulsion` and the `governing_seq` its `notice_seq`. When a",
        "lapsed standing bars an entrant the code is `lapsed` and the sequence its",
        "`notice_seq`. An expulsion outranks a lapsed standing when both reach the",
        "same round.",
        "",
        "## Delivered",
        "",
        "`participation_ledger.csv`, one row per entrant and round, ascending player",
        "identifier then ascending round.",
    ])

    write_lines(root / "spec_stage_p03_candidate_boards.md", [
        "# P03 candidate board assembly",
        "",
        "Produces the boards the hall recorded, as evidence to be screened later.",
        "",
        "## Which pairing row governs a table",
        "",
        "Group the applicable rows of `recorded_pairing_table.csv` by round and",
        "`table_no`. A row is applicable when its `event_reference` is this event",
        "and its `pairing_status` is in the applicable list of the",
        "`recorded_pairing` section of `revision_precedence.toml`. Of the rows of a",
        "group take the one with the highest `sheet_revision`, breaking a tie on the",
        "highest `source_seq`. A `rescinded` row is out of scope whatever its",
        "`sheet_revision` is.",
        "",
        "## Identifiers",
        "",
        "`player_a` and `player_b` are resolved through the identifier closure of",
        "P01. A candidate board whose resolved identifier is not an entrant of this",
        "event is dropped and appears in no delivered document.",
        "",
        "A candidate board whose two resolved identifiers are equal is dropped.",
        "",
        "## Delivered",
        "",
        "`round_match_candidates.csv`, one row per surviving group, ascending round",
        "then ascending `table_no`. `player_a` and `player_b` are the resolved",
        "identifiers in the column order the governing row carries them, and",
        "`sheet_revision` and `source_seq` are those of the governing row.",
    ])

    write_lines(root / "spec_stage_p04_game_evidence.md", [
        "# P04 game evidence resolution",
        "",
        "Produces the result and the game differential of every candidate board.",
        "",
        "## The governing result sheet",
        "",
        "Group the records of `match_result_sheets.ndjson` by round and `table_no`,",
        "keep the applicable ones under the `result_sheet` section of",
        "`revision_precedence.toml` and take the one with the highest `sheet_seq`. A",
        "`superseded` record is out of scope whatever its `sheet_seq` is. A board",
        "with no applicable sheet is treated as a board whose sheet carries the",
        "absent marker in every field.",
        "",
        "## The game rows in scope",
        "",
        "Every row of `game_records.csv` of this event whose round and `table_no`",
        "match the board is in scope, including rows that repeat a `game_no`.",
        "",
        "- `games_a` is the count of rows whose `outcome` is `won_a` and whose",
        "  `completed` is `yes`.",
        "- `games_b` is the count of rows whose `outcome` is `won_b` and whose",
        "  `completed` is `yes`.",
        "- A `drawn` row counts for neither side. An `unplayed` row counts for",
        "  neither side. A row whose `completed` is `no` counts for neither side.",
        "  A `conceded_a` or `conceded_b` row counts for neither side.",
        "",
        "`delta_a` is `games_a` less `games_b`. It is published as it falls,",
        "including a value of exactly zero, and it is never normalised by the",
        "result.",
        "",
        "## The five evidence levels",
        "",
        "The levels are tried in the order the `priority_rank` of the applicable",
        "rows of `source_priority_register.csv` gives, lowest rank first. The first",
        "level that decides the board decides it, and `basis` is that level's",
        "`source_code`.",
        "",
        "1. `sheet_adjudication`. The `adjudicated_result` of the governing sheet is",
        "   not the absent marker. `result_code` is that value. This level decides",
        "   the result alone: `games_a`, `games_b` and `delta_a` stay as the game",
        "   rows leave them, whatever the adjudicated result says.",
        "2. `game_concession`. A `conceded_a` row is in scope, or a `conceded_b`",
        "   row, or both. A `conceded_a` row makes `result_code` `win_b` and a",
        "   `conceded_b` row makes it `win_a`; when rows of both kinds are in scope",
        "   `result_code` is `double_loss`. The game counts are untouched, so a",
        "   conceding side keeps the games it had already won.",
        "3. `completed_game`. `games_a` and `games_b` are not both zero.",
        "   `result_code` is `win_a` when `games_a` exceeds `games_b`, `win_b` when",
        "   `games_b` exceeds `games_a`, and `draw` when they are equal.",
        "4. `declared_count`. Neither `declared_games_a` nor `declared_games_b` of",
        "   the governing sheet is the absent marker. `result_code` is `win_a` when",
        "   the declared count of side a exceeds that of side b, `win_b` in the",
        "   opposite case and `draw` when they are equal. The declared counts decide",
        "   the result alone and never become `games_a` or `games_b`.",
        "5. `no_evidence`. Nothing above decided the board. `result_code` is",
        "   `double_loss`.",
        "",
        "## Delivered",
        "",
        "`match_result_ledger.csv`, one row per candidate board, ascending round",
        "then ascending `table_no`.",
    ])

    write_lines(root / "spec_stage_p05_round_eligibility.md", [
        "# P05 round eligibility",
        "",
        "Opens a round. Worked once per round, before the bye of that round.",
        "",
        "## Who is eligible",
        "",
        "An entrant is eligible in a round when the participation state of P02 for",
        "that entrant and that round is `seated`. A `dropped`, an `absent` and a",
        "`barred` entrant is not eligible. Eligibility is never set aside by any",
        "rung of the pairing ladder and by no other rule of this settlement.",
        "",
        "## The running state",
        "",
        "`running_points` is the sum of the `round_points` P09 published for the",
        "entrant in every round already closed, with no tournament penalty taken",
        "off. `running_delta` is the sum of the `game_delta` P09 published for the",
        "entrant in every round already closed. In round one both are zero.",
        "",
        "The running state is the closed state. A round that has not closed",
        "contributes nothing to the round it opens.",
        "",
        "## Delivered",
        "",
        "`round_eligibility_ledger.csv`, one row per entrant and round, ascending",
        "round then ascending player identifier. `eligible` is `yes` or `no` and",
        "`state` is the P02 state.",
    ])

    write_lines(root / "spec_stage_p06_bye_assignment.md", [
        "# P06 bye assignment",
        "",
        "Worked once per round and per division, after P05 and before P07.",
        "",
        "## When a bye is awarded",
        "",
        "A division whose count of eligible entrants in the round is odd is awarded",
        "one bye. A division whose count is even or zero is awarded none.",
        "",
        "## The candidate set",
        "",
        "The candidate set is the eligible entrants of the division whose count of",
        "byes already awarded in earlier rounds is below the `max_byes` parameter of",
        "the live sheet of `panel_capacity_workbook.xlsx`.",
        "",
        "When the candidate set is empty the `bye_override` parameter of the",
        "`division_admission_matrix.csv` row for that division and round decides.",
        "With `yes` the candidate set becomes every eligible entrant of the division",
        "and `basis` is `cap_override`. With `no` no bye is awarded, the division",
        "keeps its odd count and P07 leaves one entrant unpaired.",
        "",
        "Otherwise `basis` is `normal`.",
        "",
        "## Which candidate takes it",
        "",
        "Order the candidate set on the keys of the `bye_order` family of",
        "`standings_precedence_directive.docx`, applied in ascending key position.",
        "The first candidate takes the bye. `byes_before` is its count of byes",
        "awarded in earlier rounds.",
        "",
        "## What the bye credits",
        "",
        "The bye credits the `bye_points` and the `bye_game_delta` clauses of",
        "`appeals_procedure_memo.pdf`. A bye creates no opponent.",
        "",
        "The `bye_award_journal.tsv` records the byes the hall awarded. It is",
        "evidence for P08 and it is not the bye of this settlement.",
        "",
        "## Delivered",
        "",
        "`bye_ledger.csv`, one row per awarded bye, ascending round then ascending",
        "`division_id`.",
    ])

    write_lines(root / "spec_stage_p07_authoritative_pairing.md", [
        "# P07 authoritative pairing",
        "",
        "Worked once per round, after P06 and before P08.",
        "",
        "## The pool",
        "",
        "The pool is every entrant eligible in the round that P06 did not award the",
        "bye to, across every division in force, held in one order. Order it on the",
        "keys of the `pairing_order` family of",
        "`standings_precedence_directive.docx`, applied in ascending key position.",
        "The `division_rank` a key refers to is the rank of the division rank",
        "register of the same directive.",
        "",
        "## The ladder",
        "",
        "`pairing_precedence_policy.toml` states four admission levels and that they",
        "are cumulative: level one sets aside the constraint of the first rung of",
        "`appeals_procedure_memo.pdf`, level two sets aside that rung and the",
        "second, level three sets aside all three. Eligibility is never set aside.",
        "",
        "A partner is admissible for a player at a level when every constraint the",
        "level has not set aside holds:",
        "",
        "- the division constraint: the two entrants are in the same division;",
        "- the band constraint: the absolute difference of their `running_points` is",
        "  at most the effective band;",
        "- the prior opponent constraint: the partner is in no encounter of the",
        "  player recorded by P11 in an earlier round, whether that encounter counts",
        "  for strength or not.",
        "",
        "The effective band is the `score_band` parameter of the live sheet of",
        "`panel_capacity_workbook.xlsx` plus the `band_widening` parameter of the",
        "`division_admission_matrix.csv` row for the division of the player taken",
        "first and that round.",
        "",
        "When the division constraint has been set aside and the two entrants are in",
        "different divisions, the partner is admissible only when the",
        "`cross_admitted` parameter of `division_admission_matrix.csv` is `yes` for",
        "both divisions in that round. This gate is part of every level and no level",
        "sets it aside.",
        "",
        "## The search",
        "",
        "Take the first entrant of the pool that is still unpaired. For level zero,",
        "then level one, then level two, then level three, scan the entrants still",
        "unpaired that follow it in the pool order and take the first admissible",
        "one. The first level that yields a partner is the `admission_level` of the",
        "board and the search stops there. Pair the two and continue with the next",
        "unpaired entrant of the pool.",
        "",
        "Board numbers run from one inside each round in the order the boards were",
        "formed. `player_a` is the entrant taken first and `player_b` the partner.",
        "`points_a` and `points_b` are their `running_points` at the opening of the",
        "round.",
        "",
        "An entrant no level yields a partner for is left unpaired. Its `reason` is",
        "`no_admissible_partner`. It is credited the `unpaired_points` clause of",
        "`appeals_procedure_memo.pdf` and a game differential of zero, and it",
        "creates no opponent.",
        "",
        "## Delivered",
        "",
        "`authoritative_pairing_ledger.csv`, ascending round then ascending board.",
        "`pairing_fallback_ledger.csv`, the boards whose `admission_level` is above",
        "zero, with `relaxed_constraints` the rung names of",
        "`appeals_procedure_memo.pdf` up to that level joined with a plus sign in",
        "rung order. `unpaired_ledger.tsv`, ascending round then ascending player",
        "identifier.",
        "",
        "`pairing_constraint_report.json` carries one entry per round. `boards` is",
        "the count of authoritative boards formed in the round, `byes` the byes P06",
        "awarded, `unpaired` the entrants left unpaired and `level_counts` the",
        "authoritative boards admitted at each level. `cross_division_boards` counts",
        "the authoritative boards whose two entrants are in different divisions and",
        "`repeat_boards` those whose two entrants are already in an encounter P11",
        "recorded in an earlier round. `voided_boards` is the count of candidate",
        "boards of the round P08 voided.",
    ])

    write_lines(root / "spec_stage_p08_admissibility_voids.md", [
        "# P08 admissibility and voids",
        "",
        "Worked once per round, after P07 and before P09. Screens the candidate",
        "boards of the round against what the regulations allowed.",
        "",
        "## The tolerance of a board",
        "",
        "The tolerance of a candidate board is the lower of the two admission",
        "levels its two entrants were admitted at in P07 of that round.",
        "`pairing_precedence_policy.toml` gives the tolerance of an entrant P06",
        "awarded the bye to, of an entrant P07 left unpaired and of an entrant",
        "that is not eligible in the round and so never entered P07.",
        "",
        "## The screen",
        "",
        "Each check below carries a violation level. A check whose violation level",
        "is above the tolerance of the board voids it; a check whose violation level",
        "is at most the tolerance does not.",
        "",
        "| check | violation level | condition |",
        "|---|---|---|",
        "| `ineligible_player` | 4 | either entrant is not eligible in the round |",
        "| `holds_bye` | 4 | either entrant is the entrant P06 awarded the bye to |",
        "| `cross_division` | 3 | the two entrants are in different divisions |",
        "| `repeat_opponent` | 2 | the two entrants are in an encounter P11 recorded in an earlier round |",
        "| `score_band` | 1 | the absolute difference of their `running_points` exceeds the effective band of P07 |",
        "",
        "A violation level of four is above every tolerance, so those two checks",
        "always void.",
        "",
        "## Which reason is recorded",
        "",
        "More than one check may void one board. The reason recorded is the first",
        "voiding check in the order of the `void_reason` family of",
        "`standings_precedence_directive.docx`, applied in ascending key position.",
        "That order is a precedence of reasons and it is not the rung order of the",
        "pairing ladder.",
        "",
        "`violation_level` is the violation level of the recorded reason.",
        "",
        "## What a voided board credits",
        "",
        "Each entrant of a voided board is credited the `void_points` clause of",
        "`appeals_procedure_memo.pdf` and a game differential of zero, and `basis`",
        "is `void`.",
        "",
        "An entrant P06 awarded the bye to keeps the bye and its `basis` in P09",
        "stays `bye`, so its `scored_a` or `scored_b` on this ledger is the",
        "`base_points` P09 published for its bye. The other entrant of that board is",
        "credited the void points like any other.",
        "",
        "A candidate board no check voids stands, and the result P04 resolved for it",
        "is what P09 scores.",
        "",
        "`scored_a` and `scored_b` are the `base_points` P09 published for the two",
        "entrants in that round, and the absent marker of",
        "`settlement_form_rules.toml` for an entrant P09 published no row for.",
        "",
        "The effective band this stage screens on is the `score_band` parameter of",
        "the live sheet plus the `band_widening` of the division of the `player_a`",
        "of the candidate board, in that round.",
        "",
        "## Delivered",
        "",
        "`void_adjudication_ledger.csv`, one row per voided board, ascending round",
        "then ascending `table_no`.",
    ])

    write_lines(root / "spec_stage_p09_round_scoring.md", [
        "# P09 round scoring",
        "",
        "Worked once per round, after P08 and before P10. Closes the round.",
        "",
        "## The basis of an entrant",
        "",
        "For each entrant eligible in the round, in this order:",
        "",
        "- `bye` when P06 awarded it the bye.",
        "- `void` when a candidate board of the round holds it and P08 voided that",
        "  board.",
        "- `match` when a candidate board of the round holds it and P08 left that",
        "  board standing.",
        "- `unpaired` when P07 left it unpaired.",
        "- `no_record` when none of the above holds.",
        "",
        "An entrant not eligible in the round has no row in this ledger and",
        "contributes nothing to its running state.",
        "",
        "When more than one candidate board of the round holds an entrant, the",
        "board with the lowest `table_no` is the board of that entrant.",
        "",
        "The magnitudes of the applicable notices of one class that name one round",
        "are summed and the sum is applied once.",
        "",
        "## The base points and the game differential",
        "",
        "The point values of a round come from the applicable rows of",
        "`round_configuration_register.csv` for that round and the division of the",
        "entrant: `win_points`, `draw_points` and `loss_points`.",
        "",
        "- `match`: the result P04 resolved, read from the side the entrant sits on.",
        "  A `win_a` credits `win_points` to side a and `loss_points` to side b, a",
        "  `win_b` the reverse, a `draw` credits `draw_points` to both and a",
        "  `double_loss` credits `loss_points` to both. The game differential is the",
        "  `delta_a` of P04 for side a and its negation for side b.",
        "- `bye`: the `bye_points` and `bye_game_delta` clauses of",
        "  `appeals_procedure_memo.pdf`.",
        "- `void`: the `void_points` clause and a game differential of zero.",
        "- `unpaired`: the `unpaired_points` clause and a game differential of zero.",
        "- `no_record`: the `no_record_points` clause and a game differential of",
        "  zero.",
        "",
        "## The six steps of a round, in this order",
        "",
        "1. The base points and the game differential above.",
        "2. The game penalty class. Each applicable notice of",
        "   `penalty_notice_register.psv` whose class is `game` and whose",
        "   `effective_round` is this round takes its `magnitude` off the game",
        "   differential. It reaches nothing else.",
        "3. The match penalty class. When an applicable notice whose class is",
        "   `match` names this round, the base points become the `loss_points` of",
        "   the round. The result of the opponent is untouched and the game",
        "   differential is untouched. `base_points` on the delivered ledger is the",
        "   value after this step.",
        "4. The round modifier. `modifier_code` is the value of the",
        "   `round_configuration_register.csv` row for this round and division whose",
        "   `parameter` is `modifier_code`. `modified_points` is `base_points`",
        "   multiplied by the numerator of that code in `round_modifier_rules.json`,",
        "   divided by its denominator and rounded half to even. The modifier",
        "   reaches the match points alone and never the game differential.",
        "5. The round penalty class. Each applicable notice whose class is `round`",
        "   and whose `effective_round` is this round takes its `magnitude` off",
        "   `modified_points`. The result is floored at the `round_points_floor`",
        "   clause of `appeals_procedure_memo.pdf` and the shortfall is recorded by",
        "   P10 and carried into no other round.",
        "6. `round_points` is the value after step five and `game_delta` the value",
        "   after step two. The round is now closed and its values are what P05 of",
        "   the next round reads.",
        "",
        "A notice of the `tournament` class reaches no round and is applied by P10.",
        "",
        "## Delivered",
        "",
        "`round_score_ledger.csv`, one row per eligible entrant and round, ascending",
        "round then ascending player identifier.",
    ])

    write_lines(root / "spec_stage_p10_penalty_application.md", [
        "# P10 penalty application",
        "",
        "Publishes every applied notice and settles the tournament class.",
        "",
        "## Which notices are applied",
        "",
        "An applicable row of `penalty_notice_register.psv` is one whose",
        "`event_reference` is this event, whose `player_ref` resolves to an entrant",
        "of this event and whose `notice_status` is in the applicable list of the",
        "`penalty_notice` section of `revision_precedence.toml`. A `rescinded`",
        "notice is out of scope whatever its `notice_seq` is.",
        "",
        "`appeal_disposition_journal.jsonl` records how the panel disposed of a",
        "notice. It changes no notice and it is published nowhere; a notice is",
        "applicable on its own `notice_status` alone.",
        "",
        "The four applied classes are the sequence of the `order` section of",
        "`penalty_precedence_policy.toml`, which is the same order the",
        "`penalty_order_1` to `penalty_order_4` clauses of",
        "`appeals_procedure_memo.pdf` print.",
        "",
        "## What each row carries",
        "",
        "One row is written per applied class that reached an entrant in a round.",
        "`magnitude` is the summed magnitude of the applicable notices of that class",
        "naming that round and `notice_seq` the lowest `notice_seq` among them.",
        "",
        "- `game`: `value_before` is the game differential of the round before the",
        "  notice, `value_after` the value after it, `shortfall` zero.",
        "- `match`: `value_before` is the base points before the notice,",
        "  `value_after` the `loss_points` of the round, `shortfall` zero.",
        "- `round`: `value_before` is `modified_points`, `value_after` the floored",
        "  round points, `shortfall` the magnitude less `value_before` when the",
        "  magnitude is the larger and zero otherwise.",
        "- `tournament`: `round_no` is zero, because the class reaches the event",
        "  total and no round. `value_before` is the sum of the `round_points` of",
        "  the entrant across every round, `value_after` that sum less the magnitude",
        "  floored at zero, `shortfall` the magnitude less the sum when the",
        "  magnitude is the larger and zero otherwise.",
        "",
        "A notice whose class is `expulsion` is not one of the four applied classes.",
        "It has no row here; it reaches the participation state of P02.",
        "",
        "A `game`, `match` or `round` notice whose `effective_round` names a round",
        "the entrant was not eligible in has no row here and reaches nothing. A",
        "`tournament` notice reaches the event total whatever the state of the",
        "entrant in the round it names, because the class reaches no round.",
        "",
        "## The event total",
        "",
        "`event_points` of an entrant is the sum of its `round_points` less the",
        "summed `magnitude` of its applicable `tournament` notices, floored at zero.",
        "`penalty_units` of an entrant is that summed magnitude.",
        "",
        "## Delivered",
        "",
        "`penalty_application_ledger.psv`, ascending `round_no` then ascending",
        "player identifier then the applied class order.",
    ])

    write_lines(root / "spec_stage_p11_opponent_history.md", [
        "# P11 opponent history",
        "",
        "Worked once per round, after P09. Closes the round loop.",
        "",
        "## What creates an encounter",
        "",
        "A candidate board of the round that P03 kept creates one encounter row for",
        "each of its two entrants, naming the other as `opponent_id`, whenever both",
        "entrants are eligible in the round. `source` is `board`.",
        "",
        "- A board P08 left standing carries `counts_for_strength` `yes`.",
        "- A board P08 voided carries `counts_for_strength` `no`. The two entrants",
        "  did sit down together, so the encounter is recorded and the prior",
        "  opponent constraint of P07 and the `repeat_opponent` check of P08 both",
        "  see it. It contributes no opponent to the strength population of P12.",
        "",
        "A bye creates no encounter. An unpaired entrant creates no encounter. A",
        "board holding an entrant that is not eligible in the round creates no",
        "encounter, on either side.",
        "",
        "## Delivered",
        "",
        "`opponent_history_ledger.csv`, ascending round then ascending player",
        "identifier then ascending `opponent_id`.",
        "",
        "`repeat_opponent_audit.tsv`, one row per ordered pair of entrants whose",
        "encounter count across the event is above one, ascending player identifier",
        "then ascending `opponent_id`. `meetings` is that count and `rounds` the",
        "rounds of those encounters in ascending order joined with a plus sign.",
    ])

    write_lines(root / "spec_stage_p12_opponent_strength.md", [
        "# P12 opponent strength",
        "",
        "Worked once, after the last round closed. Every figure here is taken from",
        "the closed event and never from a running state.",
        "",
        "## The rate of an opponent",
        "",
        "`rounds_counted` of an entrant is the number of rounds in which P09",
        "published a row for it, whatever the basis of that row was.",
        "",
        "The rate of an entrant is its `event_points` multiplied by the `rate_scale`",
        "of `tiebreak_rules.json`, divided by its `rounds_counted` or by one when",
        "that count is zero, rounded half to even. The rate is a whole number of",
        "thousandths and it is the rounded value that the aggregate below consumes.",
        "",
        "## The strength of an entrant",
        "",
        "The population of an entrant is the distinct `opponent_id` values of its",
        "encounter rows whose `counts_for_strength` is `yes`, across every round. An",
        "opponent met twice appears in the population once.",
        "",
        "`opponent_count` is the size of the population and `rate_sum` the sum of",
        "the rates of its members. `opponent_strength` is `rate_sum` divided by",
        "`opponent_count`, rounded half to even.",
        "",
        "An entrant whose population is empty carries the `zero_strength_value` of",
        "`tiebreak_rules.json` as its `opponent_strength`, with `opponent_count` and",
        "`rate_sum` both zero.",
        "",
        "## The penalty adjusted strength",
        "",
        "`penalty_adjusted_strength` is `opponent_strength` less the `strength_debit`",
        "parameter of the live sheet of `panel_capacity_workbook.xlsx` multiplied by",
        "the `penalty_units` of the entrant, floored at zero.",
        "",
        "## The game differential of the event",
        "",
        "`raw_delta` is the sum, across every round of the entrant, of the game",
        "differential of step one of P09, before the game penalty class reached it.",
        "`game_penalty_units` is the summed `magnitude` of its applicable `game`",
        "notices that named a round the entrant was eligible in. `adjusted_delta` is",
        "`raw_delta` less `game_penalty_units`, and it equals the sum of the",
        "`game_delta` P09 published. A differential of exactly zero is published as",
        "zero and carries no sign.",
        "",
        "## Delivered",
        "",
        "`opponent_strength_ledger.csv`, ascending player identifier.",
        "`game_differential_ledger.psv`, ascending player identifier.",
    ])

    write_lines(root / "spec_stage_p13_standings_tiebreaks.md", [
        "# P13 standings and tiebreaks",
        "",
        "## The order",
        "",
        "Order every entrant of this event on the keys of the `tiebreak` family of",
        "`standings_precedence_directive.docx`, applied in ascending key position,",
        "each key in the direction the `ordering` list of `tiebreak_rules.json`",
        "gives for it. The order is total because the last key is the player",
        "identifier.",
        "",
        "`rank` runs from one without a gap and no two entrants share a rank.",
        "",
        "## Prize eligibility",
        "",
        "`prize_eligible` is `no` when the `penalty_units` of the entrant reach the",
        "`prize_disqualify_units` clause of `appeals_procedure_memo.pdf`, and `yes`",
        "otherwise.",
        "",
        "## The separating key",
        "",
        "For each pair of entrants adjacent in the order, `separating_position` is",
        "the lowest key position at which their values differ and `separating_key`",
        "the `key_name` at that position. The last entrant has no row.",
        "",
        "## Delivered",
        "",
        "`standings_ledger.csv`, ascending rank. `tiebreak_resolution_ledger.csv`,",
        "ascending rank. `final_ranking.json`, with the ranking in ascending rank.",
    ])

    write_lines(root / "spec_stage_p14_settlement_publication.md", [
        "# P14 settlement and publication",
        "",
        "## The pool",
        "",
        "The pool is the `pool_cents` parameter of the live sheet of",
        "`panel_capacity_workbook.xlsx`, in whole cents. It appears in no other",
        "paper.",
        "",
        "## The live sheet",
        "",
        "`panel_capacity_workbook.xlsx` carries several sheets. The live sheet is",
        "the one whose `sheet_reference` cell carries the `event_reference` of",
        "`division_topology.xml`. The sheet name and the sheet position carry no",
        "signal. Inside the live sheet a parameter row governs only when its",
        "`status` is `operative`; a `withdrawn`, a `superseded` and an `indicative`",
        "row govern nothing. A row whose `unit` is not the unit the reader needs is",
        "still that row: read the unit.",
        "",
        "## Tie groups",
        "",
        "Walk the standings in ascending rank. Two adjacent entrants belong to one",
        "group when their values are equal on every ordering key up to the",
        "`tie_group_depth` clause of `appeals_procedure_memo.pdf`. Groups are",
        "numbered from one in that walk order.",
        "",
        "`group_basis_points` is the sum of the `basis_points` of",
        "`prize_rules.json` for the ranks the group occupies; a rank the share table",
        "does not carry contributes zero. `group_amount_cents` is the pool",
        "multiplied by `group_basis_points`, divided by ten thousand and rounded",
        "half to even.",
        "",
        "## The split",
        "",
        "`base_share_cents` is `group_amount_cents` divided by the member count,",
        "discarding the remainder. The remainder is handed out one cent at a time",
        "to the members in ascending player identifier order until it is exhausted;",
        "`remainder_cent` is one for a member that received a cent and zero",
        "otherwise. Eligibility does not enter the split: an ineligible member takes",
        "its place in the order and its cent.",
        "",
        "`awarded_cents` is `base_share_cents` plus `remainder_cent` for an eligible",
        "member and zero for an ineligible one. The amount an ineligible member",
        "would have taken is added to the residue and is redistributed to nobody.",
        "",
        "`residue_cents` is the pool less every awarded cent.",
        "",
        "## Delivered",
        "",
        "`prize_allocation_ledger.csv`, one row per entrant whose group carries",
        "`group_basis_points` above zero, ascending rank.",
        "",
        "`prize_tie_split.tsv`, one row per group holding more than one member and",
        "carrying `group_basis_points` above zero, ascending `group_id`.",
        "`rank_span` is the lowest and the highest rank of the group joined with a",
        "plus sign, and `player_ids` its members in ascending order joined with a",
        "plus sign. `remainder_cents` is the whole remainder of the group.",
        "",
        "## The division reports",
        "",
        "One report per division `division_topology.xml` carries with `in_force`",
        "equal to `yes`, written whether or not an entrant was seated in it.",
        "`report_order` is the `report_order` of the operative section of",
        "`reporting_division_roster.conf` for that division.",
        "",
        "- `seated_players` is the count of entrants of the division.",
        "- `paired_boards` is the count of authoritative boards of the event whose",
        "  `player_a` is an entrant of the division.",
        "- `byes_awarded` is the count of bye ledger rows of the division.",
        "- `voided_boards` is the count of voided boards whose `player_a` is an",
        "  entrant of the division.",
        "- `points_total` is the sum of the `event_points` of its entrants and",
        "  `game_delta_total` the sum of their `adjusted_delta`.",
        "- `awarded_cents` is the sum of the `awarded_cents` of its entrants and",
        "  `award_share_ratio` that sum divided by the pool, at nine decimal places.",
        "- `top_player` is the entrant of the division with the lowest rank, or the",
        "  absent marker when the division seated none.",
        "",
        "## The remaining documents",
        "",
        "`standings_by_division.xml` carries the divisions in ascending",
        "`report_order` and inside each the entrants of that division in ascending",
        "rank. The root element is `settlement` and it carries `event_id` and",
        "`event_reference`. A `division` element carries `id`, `report_order` and",
        "`entrants`, where `entrants` is the count of entrants seated in it. An",
        "`entrant` element carries `rank`, `player_id`, `event_points`,",
        "`adjusted_delta`, `opponent_strength` and `awarded_cents`. Each element",
        "prints its attributes in the order named here.",
        "",
        "`settlement_control_totals.conf` carries the four sections and the keys the",
        "worked examples paper prints. `round_points_total` is the sum of every",
        "`round_points` of `round_score_ledger.csv`, `game_delta_total` the sum of",
        "every `adjusted_delta`, `penalty_units_total` the sum of every",
        "`penalty_units`, and `points_per_round_ratio` the round points total",
        "divided by the round count. `boards_total`, `byes_total`, `voided_total`",
        "and `unpaired_total` are event counts, and `level_1_boards` to",
        "`level_3_boards` the counts of authoritative boards at those admission",
        "levels. `award_share_ratio` is the awarded total divided by the pool.",
        "`tie_groups` is the count of rows of `prize_tie_split.tsv`: the tie groups",
        "holding more than one member and carrying `group_basis_points` above zero.",
        "A tie group whose ranks the share table does not carry is not counted.",
        "The tie groups line of `event_settlement_summary.md` carries the same count.",
        "",
        "`player_audit_trace.jsonl` carries one record per entrant with its rounds",
        "in ascending order; a round the entrant was not eligible in carries the",
        "P02 state, the basis `none`, and zero for both figures.",
        "",
        "`event_settlement_summary.md` follows the form of `worked_examples.md`. Its",
        "standings table carries the first ten ranks, or every rank when the event",
        "seated fewer than ten entrants.",
        "",
        "`settlement_manifest.json` carries the two digests of",
        "`serialisation_and_digest_contract.md` and one entry per delivered document",
        "except itself. An entry carries the keys `name`, `sha256` and `bytes` in",
        "that order.",
        "",
        "## The artifact contract order",
        "",
        "The order the two digests and the manifest entries follow is the order",
        "below. The six core documents are the first six names.",
        "",
    ] + ["  %d. %s" % (i, name) for i, name in enumerate(
        CORE_DOCUMENTS + [n for n in ALL_DOCUMENTS
                          if n not in CORE_DOCUMENTS and n != "settlement_manifest.json"],
        start=1)])


# --------------------------------------------------------------------------
# readers
# --------------------------------------------------------------------------


def read_delim(path, sep):
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return []
    header = lines[0].split(sep)
    out = []
    for line in lines[1:]:
        parts = line.split(sep)
        while len(parts) < len(header):
            parts.append("")
        out.append(dict(zip(header, parts)))
    return out


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            out.append(json.loads(line))
    return out


def _toml_scalar(text):
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_toml_scalar(part) for part in inner.split(",")]
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    try:
        return int(text)
    except ValueError:
        return text


def read_toml(path):
    data = {}
    section = data
    for raw in path.read_text(encoding="utf-8").split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = data
            for part in line[1:-1].split("."):
                section = section.setdefault(part, {})
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        section[key.strip()] = _toml_scalar(value)
    return data


def read_yaml(path):
    """A nested mapping of scalars and simple lists, which is all the policy
    papers use."""
    root = {}
    stack = [(-1, root)]
    for raw in path.read_text(encoding="utf-8").split("\n"):
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            parent.setdefault("_items", []).append(line[2:].strip())
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            child = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = value
    return root


def read_conf(path):
    out = {}
    section = None
    for raw in path.read_text(encoding="utf-8").split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            out.setdefault(section, [])
            out[section].append({})
            continue
        if "=" not in line or section is None:
            continue
        key, value = line.split("=", 1)
        out[section][-1][key.strip()] = value.strip()
    return out


def _column_index(ref):
    letters = ""
    for ch in ref:
        if ch.isalpha():
            letters += ch
        else:
            break
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - 64)
    return index - 1


def read_xlsx(path):
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    sheets = {}
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst.findall(ns + "si"):
                text = "".join(node.text or "" for node in si.iter(ns + "t"))
                shared.append(text)
        rels = {}
        rroot = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        for rel in rroot:
            rels[rel.get("Id")] = rel.get("Target")
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        for sheet in wb.find(ns + "sheets"):
            name = sheet.get("name")
            target = rels[sheet.get(rel_ns + "id")]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            grid = []
            sroot = ET.fromstring(zf.read(target))
            data = sroot.find(ns + "sheetData")
            for row in (data if data is not None else []):
                cells = []
                for cell in row.findall(ns + "c"):
                    index = _column_index(cell.get("r") or "A1")
                    while len(cells) <= index:
                        cells.append("")
                    value = cell.find(ns + "v")
                    text = value.text if value is not None else ""
                    if cell.get("t") == "s" and text != "":
                        text = shared[int(text)]
                    cells[index] = text or ""
                grid.append(cells)
            sheets[name] = grid
    return sheets


def read_docx(path):
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    tables = []
    paragraphs = []
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    body = root.find(ns + "body")
    for node in body:
        if node.tag == ns + "tbl":
            rows = []
            for tr in node.findall(ns + "tr"):
                cells = []
                for tc in tr.findall(ns + "tc"):
                    cells.append("".join(t.text or "" for t in tc.iter(ns + "t")))
                rows.append(cells)
            tables.append(rows)
        elif node.tag == ns + "p":
            paragraphs.append("".join(t.text or "" for t in node.iter(ns + "t")))
    return {"tables": tables, "paragraphs": paragraphs}


def read_pdf_lines(path):
    raw = path.read_bytes().decode("latin-1")
    out = []
    index = 0
    while True:
        start = raw.find("(", index)
        if start < 0:
            break
        cursor = start + 1
        buf = []
        while cursor < len(raw):
            ch = raw[cursor]
            if ch == BACKSLASH:
                buf.append(raw[cursor + 1])
                cursor += 2
                continue
            if ch == ")":
                break
            buf.append(ch)
            cursor += 1
        tail = raw[cursor:cursor + 4]
        if tail.startswith(") Tj"):
            out.append("".join(buf))
        index = cursor + 1
    return out


# --------------------------------------------------------------------------
# the working papers, read once
# --------------------------------------------------------------------------


def live_sheet(sheets, reference):
    """The sheet whose sheet_reference cell carries this event reference."""
    for name in sorted(sheets):
        grid = sheets[name]
        for row in grid:
            if len(row) >= 2 and row[0] == "sheet_reference":
                if row[1] == reference:
                    return name, grid
                break
    raise ValueError("no live capacity sheet for %s" % reference)


def sheet_parameter(grid, parameter):
    header = None
    for row in grid:
        if row and row[0] == "parameter":
            header = row
            continue
        if header is None:
            continue
        if not row or row[0] != parameter:
            continue
        record = dict(zip(header, row))
        if record.get("status") == "operative":
            return record
    raise ValueError("no operative %s on the live sheet" % parameter)


def memo_clauses(lines, reference):
    """The operative clause register of the procedure memorandum."""
    out = {}
    for line in lines:
        if not line.startswith("CL-"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        _clause, status, ref, key = parts[0], parts[1], parts[2], parts[3]
        value = parts[4]
        if status != "operative" or ref != reference:
            continue
        out[key] = value
    return out


def directive_keys(doc, reference):
    """The operative key families and the division ranks of the directive."""
    families = {}
    ranks = {}
    for table in doc["tables"]:
        if not table:
            continue
        header = table[0]
        if "key_family" in header:
            for row in table[1:]:
                record = dict(zip(header, row))
                if record.get("status") != "operative":
                    continue
                if record.get("event_reference") != reference:
                    continue
                families.setdefault(record["key_family"], []).append(
                    (int(record["key_position"]), record["key_name"]))
        elif "division_rank" in header:
            for row in table[1:]:
                record = dict(zip(header, row))
                if record.get("status") != "operative":
                    continue
                if record.get("event_reference") != reference:
                    continue
                ranks[record["division_id"]] = int(record["division_rank"])
    for family in families:
        families[family] = [name for _pos, name in sorted(families[family])]
    return families, ranks


def load_event(data_dir):
    root = Path(data_dir)
    data = {"root": root}
    topology = ET.parse(str(root / "division_topology.xml")).getroot()
    identity = topology.find("identity")
    reference = identity.find("event_reference").text
    data["event_id"] = identity.find("event_id").text
    data["event_reference"] = reference
    data["round_count"] = int(identity.find("round_count").text)
    in_force = []
    for node in topology.find("divisions"):
        if node.get("in_force") == "yes":
            in_force.append(node.get("id"))
    data["divisions"] = in_force

    data["roster"] = read_delim(root / "entry_roster_register.csv", ",")
    data["aliases"] = read_delim(root / "entry_alias_register.csv", ",")
    data["seats"] = read_delim(root / "seat_assignment_register.csv", ",")
    data["ratings"] = read_delim(root / "rating_return_sheet.psv", "|")
    data["memberships"] = read_delim(root / "membership_standing_register.csv", ",")
    data["status"] = read_delim(root / "status_change_journal.tsv", "\t")
    data["penalties"] = read_delim(root / "penalty_notice_register.psv", "|")
    data["pairings"] = read_delim(root / "recorded_pairing_table.csv", ",")
    data["sheets"] = read_jsonl(root / "match_result_sheets.ndjson")
    data["games"] = read_delim(root / "game_records.csv", ",")
    data["config"] = read_delim(root / "round_configuration_register.csv", ",")
    data["matrix"] = read_delim(root / "division_admission_matrix.csv", ",")
    data["priority"] = read_delim(root / "source_priority_register.csv", ",")

    data["units"] = read_toml(root / "unit_register_dictionary.toml")
    data["precedence"] = read_toml(root / "revision_precedence.toml")
    data["form"] = read_toml(root / "settlement_form_rules.toml")
    data["boundaries"] = read_yaml(root / "boundary_conventions.yaml")
    data["tiebreaks"] = read_json(root / "tiebreak_rules.json")
    data["prizes"] = read_json(root / "prize_rules.json")
    data["modifiers"] = read_json(root / "round_modifier_rules.json")
    data["roster_conf"] = read_conf(root / "reporting_division_roster.conf")
    data["pairing_policy"] = read_toml(root / "pairing_precedence_policy.toml")

    sheets = read_xlsx(root / "panel_capacity_workbook.xlsx")
    name, grid = live_sheet(sheets, reference)
    data["live_sheet_name"] = name
    data["score_band"] = int(sheet_parameter(grid, "score_band")["value"])
    data["max_byes"] = int(sheet_parameter(grid, "max_byes")["value"])
    pool = sheet_parameter(grid, "pool_cents")
    data["pool_cents"] = int(pool["value"])
    data["pool_unit"] = pool["unit"]
    data["strength_debit"] = int(sheet_parameter(grid, "strength_debit")["value"])

    clauses = memo_clauses(read_pdf_lines(root / "appeals_procedure_memo.pdf"),
                           reference)
    data["clauses"] = clauses
    data["bye_points"] = int(clauses["bye_points"])
    data["bye_game_delta"] = int(clauses["bye_game_delta"])
    data["void_points"] = int(clauses["void_points"])
    data["unpaired_points"] = int(clauses["unpaired_points"])
    data["no_record_points"] = int(clauses["no_record_points"])
    data["round_points_floor"] = int(clauses["round_points_floor"])
    data["disqualify_units"] = int(clauses["prize_disqualify_units"])
    data["tie_group_depth"] = int(clauses["tie_group_depth"])
    data["ladder"] = [clauses["relaxation_rung_1"], clauses["relaxation_rung_2"],
                      clauses["relaxation_rung_3"]]
    data["penalty_order"] = [clauses["penalty_order_%d" % i] for i in range(1, 5)]

    families, ranks = directive_keys(
        read_docx(root / "standings_precedence_directive.docx"), reference)
    data["key_families"] = families
    data["division_rank"] = ranks

    data["ticks"] = int(data["boundaries"]["round_interval"]["ticks_per_round"])
    data["absent"] = data["form"]["markers"]["absent"]
    return data


def mine(rows, reference, field="event_reference"):
    return [r for r in rows if r.get(field) == reference]


def applicable(rows, precedence_section):
    allowed = set(precedence_section.get("applicable_status", []))
    excluded = set(precedence_section.get("excluded_status", []))
    out = []
    for row in rows:
        status = row.get("status")
        if status in excluded:
            continue
        if allowed and status not in allowed:
            continue
        out.append(row)
    return out


# --------------------------------------------------------------------------
# decisions the settlement turns on, each in its own named function
# --------------------------------------------------------------------------


def round_of_tick(tick, ticks):
    """A tick on a round boundary belongs to the later of the two rounds."""
    return tick // ticks + 1


def default_rating(matrix_value):
    """An absent rating quotation takes the division default, never a zero."""
    return matrix_value


def seed_numbers(entrants, declared):
    """The seat order is derived from the normalised rating."""
    order = sorted(entrants, key=lambda pid: (-entrants[pid]["rating_mr"], pid))
    return {pid: i for i, pid in enumerate(order, start=1)}


def evidence_order(priority_rows):
    ranked = sorted(priority_rows, key=lambda r: int(r["priority_rank"]))
    return [r["source_code"] for r in ranked]


def void_reason_order(families):
    """The recorded reason is the first voiding check in the directive order."""
    return list(families["void_reason"])


def tolerance_of(level_a, level_b):
    return min(level_a, level_b)


def apply_modifier(base_points, numerator, denominator):
    return round_half_even(Fraction(base_points * numerator, denominator))


def modifier_on_delta(game_delta, numerator, denominator):
    """The round modifier reaches the match points alone."""
    return game_delta


def round_penalty(modified_points, magnitude, floor):
    value = modified_points - magnitude
    if value < floor:
        return floor, magnitude - modified_points
    return value, 0


def counts_for_strength(voided):
    return "no" if voided else "yes"


def encounter_recorded(voided):
    """Both entrants sat down together, so a voided board is still an
    encounter."""
    return True


def opponent_rate(event_points, rounds_counted, scale):
    return round_half_even(Fraction(event_points * scale, max(1, rounds_counted)))


def aggregate_strength(rate_sum, count, zero_value):
    if count == 0:
        return zero_value
    return round_half_even(Fraction(rate_sum, count))


def award_for(base_share, remainder_cent, eligible):
    """The share of an ineligible member goes to the residue."""
    return (base_share + remainder_cent) if eligible else 0


# --------------------------------------------------------------------------
# P01 entry normalisation
# --------------------------------------------------------------------------


def stage_p01(data):
    reference = data["event_reference"]
    alias = {}
    for row in mine(data["aliases"], reference):
        alias[row["alias_id"]] = row["canonical_id"]

    resolved_cache = {}

    def resolve(identifier):
        if identifier in resolved_cache:
            return resolved_cache[identifier]
        seen = []
        cursor = identifier
        while cursor in alias:
            if cursor in seen:
                cycle = seen[seen.index(cursor):]
                answer = min(cycle)
                for member in seen:
                    resolved_cache[member] = answer
                return answer
            seen.append(cursor)
            cursor = alias[cursor]
        for member in seen:
            resolved_cache[member] = cursor
        resolved_cache[identifier] = cursor
        return cursor

    data["resolve"] = resolve

    section = data["precedence"]["entry_roster"]
    allowed = set(section["applicable_status"])
    excluded = set(section["excluded_status"])
    clusters = {}
    for row in mine(data["roster"], reference):
        status = row["entry_status"]
        if status in excluded or status not in allowed:
            continue
        pid = resolve(row["entry_id"])
        clusters.setdefault(pid, []).append(row)

    rsection = data["precedence"]["rating_return"]
    rallowed = set(rsection["applicable_status"])
    rexcluded = set(rsection["excluded_status"])
    returns = {}
    for row in mine(data["ratings"], reference):
        status = row["return_status"]
        if status in rexcluded or status not in rallowed:
            continue
        pid = resolve(row["player_ref"])
        current = returns.get(pid)
        if current is None or int(row["return_seq"]) > int(current["return_seq"]):
            returns[pid] = row

    defaults = {}
    for row in mine(data["matrix"], reference):
        if row["parameter"] == "default_rating_mr" and int(row["round_no"]) == 1:
            defaults[row["division_id"]] = int(row["value"])

    units = data["units"]["unit"]
    entrants = {}
    for pid, rows in clusters.items():
        governing = max(rows, key=lambda r: (int(r["revision_seq"]),
                                             int(r["entry_seq"])))
        division = governing["division_id"]
        if division not in data["divisions"]:
            continue
        source = "roster"
        quoted = governing["quoted_rating"]
        unit = governing["rating_unit"]
        row = returns.get(pid)
        if row is not None:
            source = "return"
            quoted = row["quoted_value"]
            unit = row["quoted_unit"]
        if is_absent(quoted):
            rating = default_rating(defaults[division])
            source = "default"
        else:
            entry = units[unit]
            rating = scaled(entry["numerator"], entry["denominator"], int(quoted))
        folded = sorted({r["entry_id"] for r in rows} - {pid})
        entrants[pid] = {
            "player_id": pid,
            "division_id": division,
            "rating_mr": rating,
            "rating_source": source,
            "entry_seq": int(governing["entry_seq"]),
            "membership_ref": governing["membership_ref"],
            "folded_ids": folded,
        }

    declared = {}
    for row in mine(data["seats"], reference):
        pid = resolve(row["entry_id"])
        if pid in entrants:
            declared[pid] = as_int(row["declared_seed"])
    seeds = seed_numbers(entrants, declared)
    for pid, number in seeds.items():
        entrants[pid]["seed_number"] = number

    data["entrants"] = entrants
    data["order"] = sorted(entrants)
    return entrants


# --------------------------------------------------------------------------
# P02 participation state
# --------------------------------------------------------------------------


def stage_p02(data):
    reference = data["event_reference"]
    resolve = data["resolve"]
    ticks = data["ticks"]
    rounds = data["round_count"]
    entrants = data["entrants"]

    journal = {}
    for row in mine(data["status"], reference):
        pid = resolve(row["player_ref"])
        if pid not in entrants:
            continue
        journal.setdefault(pid, []).append(
            (round_of_tick(int(row["tick"]), ticks), int(row["note_seq"]),
             row["change_code"]))
    for pid in journal:
        journal[pid].sort()

    standings = {}
    for row in mine(data["memberships"], reference):
        standings.setdefault(row["membership_ref"], []).append(
            (int(row["effective_round"]), int(row["notice_seq"]),
             row["standing_code"]))
    for ref in standings:
        standings[ref].sort()

    psection = data["precedence"]["penalty_notice"]
    pallowed = set(psection["applicable_status"])
    pexcluded = set(psection["excluded_status"])
    expulsions = {}
    for row in mine(data["penalties"], reference):
        if row["penalty_class"] != "expulsion":
            continue
        status = row["notice_status"]
        if status in pexcluded or status not in pallowed:
            continue
        pid = resolve(row["player_ref"])
        if pid not in entrants:
            continue
        current = expulsions.get(pid)
        entry = (int(row["effective_round"]), int(row["notice_seq"]))
        if current is None or entry < current:
            expulsions[pid] = entry

    ledger = []
    state_of = {}
    for pid in data["order"]:
        member = entrants[pid]["membership_ref"]
        for r in range(1, rounds + 1):
            state = "seated"
            code = "none"
            seq = 0
            for jround, jseq, jcode in journal.get(pid, []):
                if jround > r:
                    break
                if jcode == "drop":
                    state, code, seq = "dropped", jcode, jseq
                elif jcode in ("reentry", "reinstate"):
                    state, code, seq = "seated", jcode, jseq
                elif jcode == "absence":
                    if jround == r:
                        state, code, seq = "absent", jcode, jseq
            applicable_standing = [s for s in standings.get(member, [])
                                   if s[0] <= r]
            if applicable_standing:
                eround, eseq, scode = applicable_standing[-1]
                if scode == "lapsed":
                    state, code, seq = "barred", "lapsed", eseq
            expulsion = expulsions.get(pid)
            if expulsion is not None and expulsion[0] <= r:
                state, code, seq = "barred", "expulsion", expulsion[1]
            state_of[(pid, r)] = state
            ledger.append([pid, r, state, code, seq])
    data["participation"] = ledger
    data["state_of"] = state_of
    return ledger


# --------------------------------------------------------------------------
# P03 candidate board assembly
# --------------------------------------------------------------------------


def stage_p03(data):
    reference = data["event_reference"]
    resolve = data["resolve"]
    entrants = data["entrants"]
    section = data["precedence"]["recorded_pairing"]
    allowed = set(section["applicable_status"])
    excluded = set(section["excluded_status"])

    groups = {}
    for row in mine(data["pairings"], reference):
        status = row["pairing_status"]
        if status in excluded or status not in allowed:
            continue
        key = (int(row["round_no"]), int(row["table_no"]))
        current = groups.get(key)
        rank = (int(row["sheet_revision"]), int(row["source_seq"]))
        if current is None or rank > current[0]:
            groups[key] = (rank, row)

    boards = []
    for (round_no, table_no) in sorted(groups):
        _rank, row = groups[(round_no, table_no)]
        pa = resolve(row["player_a"])
        pb = resolve(row["player_b"])
        if pa not in entrants or pb not in entrants or pa == pb:
            continue
        boards.append({"round_no": round_no, "table_no": table_no,
                       "player_a": pa, "player_b": pb,
                       "sheet_revision": int(row["sheet_revision"]),
                       "source_seq": int(row["source_seq"])})
    data["candidates"] = boards
    data["candidates_by_round"] = {}
    for board in boards:
        data["candidates_by_round"].setdefault(board["round_no"], []).append(board)
    return boards


# --------------------------------------------------------------------------
# P04 game evidence resolution
# --------------------------------------------------------------------------


def stage_p04(data):
    reference = data["event_reference"]
    section = data["precedence"]["result_sheet"]
    allowed = set(section["applicable_status"])
    excluded = set(section["excluded_status"])
    absent = data["absent"]

    sheets = {}
    for record in data["sheets"]:
        if record.get("event_reference") != reference:
            continue
        status = record.get("sheet_status")
        if status in excluded or status not in allowed:
            continue
        key = (int(record["round_no"]), int(record["table_no"]))
        current = sheets.get(key)
        if current is None or int(record["sheet_seq"]) > int(current["sheet_seq"]):
            sheets[key] = record

    games = {}
    for row in mine(data["games"], reference):
        key = (int(row["round_no"]), int(row["table_no"]))
        games.setdefault(key, []).append(row)

    levels = evidence_order(
        [r for r in mine(data["priority"], reference)
         if r["record_status"] == "operative"])

    ledger = []
    results = {}
    for board in data["candidates"]:
        key = (board["round_no"], board["table_no"])
        sheet = sheets.get(key, {})
        rows = games.get(key, [])
        games_a = sum(1 for r in rows
                      if r["outcome"] == "won_a" and r["completed"] == "yes")
        games_b = sum(1 for r in rows
                      if r["outcome"] == "won_b" and r["completed"] == "yes")
        conceded_a = any(r["outcome"] == "conceded_a" for r in rows)
        conceded_b = any(r["outcome"] == "conceded_b" for r in rows)
        adjudicated = str(sheet.get("adjudicated_result", absent))
        declared_a = sheet.get("declared_games_a", absent)
        declared_b = sheet.get("declared_games_b", absent)

        code = None
        basis = None
        for level in levels:
            if level == "sheet_adjudication" and adjudicated != absent and adjudicated:
                code, basis = adjudicated, level
                break
            if level == "game_concession" and (conceded_a or conceded_b):
                if conceded_a and conceded_b:
                    code = "double_loss"
                elif conceded_a:
                    code = "win_b"
                else:
                    code = "win_a"
                basis = level
                break
            if level == "completed_game" and (games_a or games_b):
                if games_a > games_b:
                    code = "win_a"
                elif games_b > games_a:
                    code = "win_b"
                else:
                    code = "draw"
                basis = level
                break
            if level == "declared_count" and not is_absent(declared_a) \
                    and not is_absent(declared_b):
                if int(declared_a) > int(declared_b):
                    code = "win_a"
                elif int(declared_b) > int(declared_a):
                    code = "win_b"
                else:
                    code = "draw"
                basis = level
                break
            if level == "no_evidence":
                code, basis = "double_loss", level
                break
        ledger.append([board["round_no"], board["table_no"], board["player_a"],
                       board["player_b"], code, basis, games_a, games_b,
                       games_a - games_b])
        results[(board["round_no"], board["table_no"])] = {
            "code": code, "basis": basis, "delta_a": games_a - games_b}
    data["results"] = results
    data["result_ledger"] = ledger
    return ledger


# --------------------------------------------------------------------------
# the ordering keys, taken from the directive
# --------------------------------------------------------------------------


def _key_value(name, pid, ctx):
    if name == "running_points_descending":
        return -ctx["points"][pid]
    if name == "running_points_ascending":
        return ctx["points"][pid]
    if name == "running_differential_descending":
        return -ctx["delta"][pid]
    if name == "running_differential_ascending":
        return ctx["delta"][pid]
    if name == "division_rank_ascending":
        return ctx["rank"][ctx["division"][pid]]
    if name == "seat_order_ascending":
        return ctx["seed"][pid]
    if name == "seat_order_descending":
        return -ctx["seed"][pid]
    if name == "byes_received_ascending":
        return ctx["byes"][pid]
    if name == "player_id_ascending":
        return pid
    raise ValueError("unknown ordering key %s" % name)


def order_by(family, members, ctx):
    return sorted(members, key=lambda pid: tuple(_key_value(name, pid, ctx)
                                                 for name in family))


# --------------------------------------------------------------------------
# P05 to P11, worked round by round
# --------------------------------------------------------------------------


def stage_rounds(data):
    entrants = data["entrants"]
    order = data["order"]
    rounds = data["round_count"]
    reference = data["event_reference"]
    resolve = data["resolve"]
    divisions = data["divisions"]
    families = data["key_families"]

    matrix = {}
    for row in mine(data["matrix"], reference):
        matrix[(row["division_id"], int(row["round_no"]), row["parameter"])] = \
            row["value"]
    config = {}
    for row in mine(data["config"], reference):
        config[(int(row["round_no"]), row["division_id"], row["parameter"])] = \
            row["value"]
    modifier_by_code = {entry["code"]: (entry["numerator"], entry["denominator"])
                        for entry in data["modifiers"]["codes"]}

    section = data["precedence"]["penalty_notice"]
    allowed = set(section["applicable_status"])
    excluded = set(section["excluded_status"])
    notices = {}
    tournament_notices = {}
    for row in mine(data["penalties"], reference):
        status = row["notice_status"]
        if status in excluded or status not in allowed:
            continue
        pid = resolve(row["player_ref"])
        if pid not in entrants:
            continue
        cls = row["penalty_class"]
        if cls == "expulsion":
            continue
        if cls == "tournament":
            tournament_notices.setdefault(pid, []).append(
                (int(row["notice_seq"]), int(row["magnitude"])))
            continue
        notices.setdefault((pid, int(row["effective_round"]), cls), []).append(
            (int(row["notice_seq"]), int(row["magnitude"])))
    data["tournament_notices"] = tournament_notices

    points = {pid: 0 for pid in order}
    delta = {pid: 0 for pid in order}
    byes = {pid: 0 for pid in order}
    history = {pid: set() for pid in order}
    ctx = {"points": points, "delta": delta, "byes": byes,
           "seed": {pid: entrants[pid]["seed_number"] for pid in order},
           "division": {pid: entrants[pid]["division_id"] for pid in order},
           "rank": data["division_rank"]}

    eligibility_ledger = []
    bye_ledger = []
    pairing_ledger = []
    fallback_ledger = []
    unpaired_ledger = []
    void_ledger = []
    score_ledger = []
    penalty_ledger = []
    history_ledger = []
    round_report = []
    raw_delta = {pid: 0 for pid in order}
    game_penalty_units = {pid: 0 for pid in order}
    rounds_counted = {pid: 0 for pid in order}
    round_points_of = {}
    delta_of = {}
    basis_of = {}

    for r in range(1, rounds + 1):
        state = {pid: data["state_of"][(pid, r)] for pid in order}
        eligible = [pid for pid in order if state[pid] == "seated"]
        for pid in order:
            eligibility_ledger.append([r, pid, entrants[pid]["division_id"],
                                       "yes" if state[pid] == "seated" else "no",
                                       state[pid], points[pid], delta[pid]])

        # P06 bye assignment
        bye_holders = {}
        for div in divisions:
            members = [pid for pid in eligible
                       if entrants[pid]["division_id"] == div]
            if len(members) % 2 != 1:
                continue
            candidates = [pid for pid in members if byes[pid] < data["max_byes"]]
            basis = "normal"
            if not candidates:
                if matrix.get((div, r, "bye_override")) == "yes":
                    candidates = members
                    basis = "cap_override"
                else:
                    candidates = []
            if not candidates:
                continue
            chosen = order_by(families["bye_order"], candidates, ctx)[0]
            bye_ledger.append([r, div, chosen, byes[chosen], basis])
            bye_holders[chosen] = div

        # P07 authoritative pairing
        pool = order_by(families["pairing_order"],
                        [pid for pid in eligible if pid not in bye_holders], ctx)
        remaining = list(pool)
        unpaired_here = set()
        tolerance_policy = data["pairing_policy"]["tolerance"]
        level_of = {}
        for pid in bye_holders:
            level_of[pid] = int(tolerance_policy["bye_holder"])
        board_no = 0
        level_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        cross_boards = 0
        repeat_boards = 0

        def admissible(a, b, level):
            relaxed = set(data["ladder"][:level])
            div_a = entrants[a]["division_id"]
            div_b = entrants[b]["division_id"]
            if div_a != div_b:
                if "division" not in relaxed:
                    return False
                if matrix.get((div_a, r, "cross_admitted")) != "yes":
                    return False
                if matrix.get((div_b, r, "cross_admitted")) != "yes":
                    return False
            if "score_band" not in relaxed:
                band = data["score_band"] + as_int(
                    matrix.get((div_a, r, "band_widening")), 0)
                if abs(points[a] - points[b]) > band:
                    return False
            if "repeat_opponent" not in relaxed and b in history[a]:
                return False
            return True

        while remaining:
            a = remaining.pop(0)
            found = None
            for level in (0, 1, 2, 3):
                for index, b in enumerate(remaining):
                    if admissible(a, b, level):
                        found = (level, index)
                        break
                if found is not None:
                    break
            if found is None:
                unpaired_ledger.append([r, entrants[a]["division_id"], a,
                                        points[a], "no_admissible_partner"])
                level_of[a] = int(tolerance_policy["unpaired"])
                unpaired_here.add(a)
                continue
            level, index = found
            b = remaining.pop(index)
            board_no += 1
            level_of[a] = level
            level_of[b] = level
            level_counts[level] += 1
            if entrants[a]["division_id"] != entrants[b]["division_id"]:
                cross_boards += 1
            if b in history[a]:
                repeat_boards += 1
            pairing_ledger.append([r, board_no, a, b, entrants[a]["division_id"],
                                   entrants[b]["division_id"], level,
                                   points[a], points[b]])
            if level > 0:
                fallback_ledger.append([r, board_no, a, b, level,
                                        "+".join(data["ladder"][:level])])

        # P08 admissibility and voids
        boards = data["candidates_by_round"].get(r, [])
        board_of = {}
        for board in sorted(boards, key=lambda x: x["table_no"]):
            board_of.setdefault(board["player_a"], board)
            board_of.setdefault(board["player_b"], board)
        voided = {}
        reason_order = void_reason_order(families)
        for board in boards:
            pa, pb = board["player_a"], board["player_b"]
            checks = {}
            if state[pa] != "seated" or state[pb] != "seated":
                checks["ineligible_player"] = 4
            if pa in bye_holders or pb in bye_holders:
                checks["holds_bye"] = 4
            if entrants[pa]["division_id"] != entrants[pb]["division_id"]:
                checks["cross_division"] = 3
            if pb in history[pa]:
                checks["repeat_opponent"] = 2
            band = data["score_band"] + as_int(
                matrix.get((entrants[pa]["division_id"], r, "band_widening")), 0)
            if abs(points[pa] - points[pb]) > band:
                checks["score_band"] = 1
            outside = int(tolerance_policy["ineligible"])
            tolerance = tolerance_of(level_of.get(pa, outside),
                                     level_of.get(pb, outside))
            firing = [name for name, level in checks.items() if level > tolerance]
            if not firing:
                continue
            reason = next(name for name in reason_order if name in firing)
            voided[(board["round_no"], board["table_no"])] = {
                "reason": reason, "level": checks[reason], "tolerance": tolerance,
                "board": board}

        # P09 round scoring
        scored = {}
        for pid in eligible:
            div = entrants[pid]["division_id"]
            win_points = as_int(config.get((r, div, "win_points")), 0)
            draw_points = as_int(config.get((r, div, "draw_points")), 0)
            loss_points = as_int(config.get((r, div, "loss_points")), 0)
            board = board_of.get(pid)
            key = (r, board["table_no"]) if board is not None else None
            if pid in bye_holders:
                basis = "bye"
                base = data["bye_points"]
                game_delta = data["bye_game_delta"]
            elif board is not None and key in voided:
                basis = "void"
                base = data["void_points"]
                game_delta = 0
            elif board is not None:
                basis = "match"
                result = data["results"][key]
                side_a = board["player_a"] == pid
                code = result["code"]
                if code == "draw":
                    base = draw_points
                elif code == "double_loss":
                    base = loss_points
                elif code == "win_a":
                    base = win_points if side_a else loss_points
                else:
                    base = loss_points if side_a else win_points
                game_delta = result["delta_a"] if side_a else -result["delta_a"]
            elif pid in unpaired_here:
                basis = "unpaired"
                base = data["unpaired_points"]
                game_delta = 0
            else:
                basis = "no_record"
                base = data["no_record_points"]
                game_delta = 0

            raw_delta[pid] += game_delta
            game_notice = notices.get((pid, r, "game"), [])
            if game_notice:
                magnitude = sum(m for _seq, m in game_notice)
                before = game_delta
                game_delta -= magnitude
                game_penalty_units[pid] += magnitude
                penalty_ledger.append([r, pid, "game", magnitude,
                                       min(seq for seq, _m in game_notice),
                                       before, game_delta, 0])
            match_notice = notices.get((pid, r, "match"), [])
            if match_notice:
                magnitude = sum(m for _seq, m in match_notice)
                before = base
                base = loss_points
                penalty_ledger.append([r, pid, "match", magnitude,
                                       min(seq for seq, _m in match_notice),
                                       before, base, 0])
            code_value = config.get((r, div, "modifier_code"))
            numerator, denominator = modifier_by_code[code_value]
            modified = apply_modifier(base, numerator, denominator)
            game_delta = modifier_on_delta(game_delta, numerator, denominator)
            round_notice = notices.get((pid, r, "round"), [])
            round_points = modified
            if round_notice:
                magnitude = sum(m for _seq, m in round_notice)
                round_points, shortfall = round_penalty(
                    modified, magnitude, data["round_points_floor"])
                penalty_ledger.append([r, pid, "round", magnitude,
                                       min(seq for seq, _m in round_notice),
                                       modified, round_points, shortfall])
            score_ledger.append([r, pid, div, basis, base, code_value, modified,
                                 round_points, game_delta])
            scored[pid] = (round_points, game_delta, base)
            round_points_of[(pid, r)] = round_points
            delta_of[(pid, r)] = game_delta
            basis_of[(pid, r)] = basis
            rounds_counted[pid] += 1

        for key, entry in sorted(voided.items()):
            board = entry["board"]
            pa, pb = board["player_a"], board["player_b"]
            void_ledger.append([
                board["round_no"], board["table_no"], pa, pb, entry["reason"],
                entry["level"], entry["tolerance"],
                scored[pa][2] if pa in scored else data["absent"],
                scored[pb][2] if pb in scored else data["absent"]])

        # P11 opponent history
        for board in boards:
            pa, pb = board["player_a"], board["player_b"]
            if state[pa] != "seated" or state[pb] != "seated":
                continue
            is_void = (board["round_no"], board["table_no"]) in voided
            if not encounter_recorded(is_void):
                continue
            flag = counts_for_strength(is_void)
            history_ledger.append([r, pa, pb, flag, "board"])
            history_ledger.append([r, pb, pa, flag, "board"])
            history[pa].add(pb)
            history[pb].add(pa)

        for pid, (round_points, game_delta, _base) in scored.items():
            points[pid] += round_points
            delta[pid] += game_delta
        for pid in bye_holders:
            byes[pid] += 1

        round_report.append({
            "round_no": r,
            "boards": board_no,
            "byes": len(bye_holders),
            "unpaired": sum(1 for row in unpaired_ledger if row[0] == r),
            "level_counts": {"level_%d" % k: level_counts[k] for k in (0, 1, 2, 3)},
            "cross_division_boards": cross_boards,
            "repeat_boards": repeat_boards,
            "voided_boards": len(voided),
        })

    data["eligibility_ledger"] = eligibility_ledger
    data["bye_ledger"] = bye_ledger
    data["pairing_ledger"] = pairing_ledger
    data["fallback_ledger"] = fallback_ledger
    data["unpaired_ledger"] = unpaired_ledger
    data["void_ledger"] = void_ledger
    data["score_ledger"] = score_ledger
    data["penalty_ledger"] = penalty_ledger
    data["history_ledger"] = history_ledger
    data["round_report"] = round_report
    data["running_points"] = points
    data["running_delta"] = delta
    data["raw_delta"] = raw_delta
    data["game_penalty_units"] = game_penalty_units
    data["rounds_counted"] = rounds_counted
    data["round_points_of"] = round_points_of
    data["delta_of"] = delta_of
    data["basis_of"] = basis_of
    data["byes_awarded"] = byes


# --------------------------------------------------------------------------
# P10 tournament class, P12 strength, P13 standings
# --------------------------------------------------------------------------


def stage_p10_event(data):
    order = data["order"]
    event_points = {}
    penalty_units = {}
    for pid in order:
        total = data["running_points"][pid]
        magnitudes = data["tournament_notices"].get(pid, [])
        units = sum(m for _seq, m in magnitudes)
        penalty_units[pid] = units
        value = total - units
        shortfall = 0
        if value < 0:
            shortfall = units - total
            value = 0
        event_points[pid] = value
        if magnitudes:
            data["penalty_ledger"].append([0, pid, "tournament", units,
                                           min(seq for seq, _m in magnitudes),
                                           total, value, shortfall])
    data["event_points"] = event_points
    data["penalty_units"] = penalty_units


def stage_p12(data):
    order = data["order"]
    scale = int(data["tiebreaks"]["rate_scale"])
    zero_value = int(data["tiebreaks"]["zero_strength_value"])
    rate = {}
    for pid in order:
        rate[pid] = opponent_rate(data["event_points"][pid],
                                  data["rounds_counted"][pid], scale)
    population = {pid: set() for pid in order}
    for row in data["history_ledger"]:
        if row[3] == "yes":
            population[row[1]].add(row[2])
    strength_ledger = []
    strength = {}
    adjusted_strength = {}
    for pid in order:
        members = population[pid]
        rate_sum = sum(rate[member] for member in members)
        value = aggregate_strength(rate_sum, len(members), zero_value)
        debit = data["strength_debit"] * data["penalty_units"][pid]
        adjusted = max(0, value - debit)
        strength[pid] = value
        adjusted_strength[pid] = adjusted
        strength_ledger.append([pid, len(members), rate_sum, value,
                                data["penalty_units"][pid], adjusted])
    data["opponent_rate"] = rate
    data["strength"] = strength
    data["adjusted_strength"] = adjusted_strength
    data["strength_ledger"] = strength_ledger

    differential_ledger = []
    adjusted_delta = {}
    for pid in order:
        raw = data["raw_delta"][pid]
        units = data["game_penalty_units"][pid]
        adjusted_delta[pid] = raw - units
        differential_ledger.append([pid, data["rounds_counted"][pid], raw, units,
                                    raw - units])
    data["adjusted_delta"] = adjusted_delta
    data["differential_ledger"] = differential_ledger


_TIEBREAK_VALUE = {
    "event_points": lambda data, pid: data["event_points"][pid],
    "adjusted_game_differential": lambda data, pid: data["adjusted_delta"][pid],
    "opponent_strength": lambda data, pid: data["strength"][pid],
    "penalty_adjusted_strength": lambda data, pid: data["adjusted_strength"][pid],
    "player_id": lambda data, pid: pid,
}


def stage_p13(data):
    family = data["key_families"]["tiebreak"]
    directions = {entry["key"]: entry["direction"]
                  for entry in data["tiebreaks"]["ordering"]}

    def sort_key(pid):
        parts = []
        for name in family:
            value = _TIEBREAK_VALUE[name](data, pid)
            if directions[name] == "descending":
                parts.append(-value)
            else:
                parts.append(value)
        return tuple(parts)

    ranking = sorted(data["order"], key=sort_key)
    data["ranking"] = ranking
    data["rank_of"] = {pid: i for i, pid in enumerate(ranking, start=1)}

    standings = []
    for i, pid in enumerate(ranking, start=1):
        units = data["penalty_units"][pid]
        eligible = "no" if units >= data["disqualify_units"] else "yes"
        standings.append([i, pid, data["entrants"][pid]["division_id"],
                          data["event_points"][pid], data["adjusted_delta"][pid],
                          data["strength"][pid], data["adjusted_strength"][pid],
                          units, eligible])
    data["standings"] = standings
    data["prize_eligible"] = {row[1]: row[8] for row in standings}

    resolution = []
    for i in range(len(ranking) - 1):
        first, second = ranking[i], ranking[i + 1]
        position = len(family)
        name = family[-1]
        for index, key in enumerate(family, start=1):
            if _TIEBREAK_VALUE[key](data, first) != _TIEBREAK_VALUE[key](data, second):
                position, name = index, key
                break
        resolution.append([i + 1, first, second, position, name])
    data["resolution"] = resolution


# --------------------------------------------------------------------------
# P14 settlement and publication
# --------------------------------------------------------------------------


def stage_p14(data):
    order = data["order"]
    ranking = data["ranking"]
    depth = data["tie_group_depth"]
    family = data["key_families"]["tiebreak"]
    keys = family[:depth]
    pool = data["pool_cents"]
    share = {int(entry["rank"]): int(entry["basis_points"])
             for entry in data["prizes"]["share_table"]}

    groups = []
    current = []
    for index, pid in enumerate(ranking):
        if not current:
            current = [pid]
            continue
        previous = current[-1]
        same = all(_TIEBREAK_VALUE[key](data, previous) ==
                   _TIEBREAK_VALUE[key](data, pid) for key in keys)
        if same:
            current.append(pid)
        else:
            groups.append(current)
            current = [pid]
    if current:
        groups.append(current)

    allocation = []
    tie_split = []
    awarded_total = 0
    for group_id, members in enumerate(groups, start=1):
        ranks = [data["rank_of"][pid] for pid in members]
        basis_points = sum(share.get(rank, 0) for rank in ranks)
        if basis_points == 0:
            continue
        amount = round_half_even(Fraction(pool * basis_points, 10000))
        base_share = amount // len(members)
        remainder = amount - base_share * len(members)
        ordered = sorted(members)
        cent_of = {pid: 0 for pid in members}
        for pid in ordered[:remainder]:
            cent_of[pid] = 1
        for pid in sorted(members, key=lambda p: data["rank_of"][p]):
            eligible = data["prize_eligible"][pid]
            award = award_for(base_share, cent_of[pid], eligible == "yes")
            awarded_total += award
            allocation.append([data["rank_of"][pid], pid, group_id, basis_points,
                               amount, len(members), base_share, cent_of[pid],
                               eligible, award])
        if len(members) > 1:
            tie_split.append([group_id, "%d+%d" % (min(ranks), max(ranks)),
                              len(members), basis_points, amount, base_share,
                              remainder, "+".join(sorted(members))])
    data["allocation"] = allocation
    data["tie_split"] = tie_split
    data["awarded_total"] = awarded_total
    data["residue"] = pool - awarded_total
    data["awarded_of"] = {row[1]: row[9] for row in allocation}


def _out_rows(path, header, rows, sep):
    lines = [sep.join(str(value) for value in header)]
    for row in rows:
        lines.append(sep.join("" if value is None else str(value) for value in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _out_json(path, payload):
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8",
                    newline="\n")


def _out_jsonl(path, records):
    lines = [json.dumps(record, separators=(",", ":")) for record in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _out_lines(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _xml_attr(value):
    return _xml_escape(str(value))


def publish(data, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    entrants = data["entrants"]
    order = data["order"]
    absent = data["absent"]

    _out_jsonl(out / "normalised_entries.jsonl", [
        {"player_id": pid,
         "division_id": entrants[pid]["division_id"],
         "seed_number": entrants[pid]["seed_number"],
         "rating_mr": entrants[pid]["rating_mr"],
         "rating_source": entrants[pid]["rating_source"],
         "entry_seq": entrants[pid]["entry_seq"],
         "folded_ids": entrants[pid]["folded_ids"]}
        for pid in order])

    _out_rows(out / "participation_ledger.csv",
              SCHEMA_BY_NAME["participation_ledger.csv"][1],
              sorted(data["participation"], key=lambda row: (row[0], row[1])), ",")

    _out_rows(out / "round_match_candidates.csv",
              SCHEMA_BY_NAME["round_match_candidates.csv"][1],
              [[b["round_no"], b["table_no"], b["player_a"], b["player_b"],
                b["sheet_revision"], b["source_seq"]]
               for b in sorted(data["candidates"],
                               key=lambda b: (b["round_no"], b["table_no"]))], ",")

    _out_rows(out / "match_result_ledger.csv",
              SCHEMA_BY_NAME["match_result_ledger.csv"][1],
              sorted(data["result_ledger"], key=lambda row: (row[0], row[1])), ",")

    _out_rows(out / "round_eligibility_ledger.csv",
              SCHEMA_BY_NAME["round_eligibility_ledger.csv"][1],
              sorted(data["eligibility_ledger"], key=lambda row: (row[0], row[1])),
              ",")

    _out_rows(out / "bye_ledger.csv", SCHEMA_BY_NAME["bye_ledger.csv"][1],
              sorted(data["bye_ledger"], key=lambda row: (row[0], row[1])), ",")

    _out_rows(out / "authoritative_pairing_ledger.csv",
              SCHEMA_BY_NAME["authoritative_pairing_ledger.csv"][1],
              sorted(data["pairing_ledger"], key=lambda row: (row[0], row[1])), ",")

    _out_rows(out / "void_adjudication_ledger.csv",
              SCHEMA_BY_NAME["void_adjudication_ledger.csv"][1],
              sorted(data["void_ledger"], key=lambda row: (row[0], row[1])), ",")

    _out_rows(out / "round_score_ledger.csv",
              SCHEMA_BY_NAME["round_score_ledger.csv"][1],
              sorted(data["score_ledger"], key=lambda row: (row[0], row[1])), ",")

    class_order = {cls: i for i, cls in enumerate(data["penalty_order"])}
    _out_rows(out / "penalty_application_ledger.psv",
              SCHEMA_BY_NAME["penalty_application_ledger.psv"][1],
              sorted(data["penalty_ledger"],
                     key=lambda row: (row[0], row[1], class_order[row[2]])), "|")

    _out_rows(out / "opponent_history_ledger.csv",
              SCHEMA_BY_NAME["opponent_history_ledger.csv"][1],
              sorted(data["history_ledger"],
                     key=lambda row: (row[0], row[1], row[2])), ",")

    _out_rows(out / "opponent_strength_ledger.csv",
              SCHEMA_BY_NAME["opponent_strength_ledger.csv"][1],
              sorted(data["strength_ledger"], key=lambda row: row[0]), ",")

    _out_rows(out / "standings_ledger.csv",
              SCHEMA_BY_NAME["standings_ledger.csv"][1], data["standings"], ",")

    _out_rows(out / "pairing_fallback_ledger.csv",
              SCHEMA_BY_NAME["pairing_fallback_ledger.csv"][1],
              sorted(data["fallback_ledger"], key=lambda row: (row[0], row[1])), ",")

    meetings = {}
    for row in data["history_ledger"]:
        meetings.setdefault((row[1], row[2]), []).append(row[0])
    repeat_rows = []
    for (pid, opponent) in sorted(meetings):
        rounds = sorted(meetings[(pid, opponent)])
        if len(rounds) > 1:
            repeat_rows.append([pid, opponent, len(rounds),
                                "+".join(str(r) for r in rounds)])
    _out_rows(out / "repeat_opponent_audit.tsv",
              SCHEMA_BY_NAME["repeat_opponent_audit.tsv"][1], repeat_rows, "\t")

    _out_rows(out / "unpaired_ledger.tsv",
              SCHEMA_BY_NAME["unpaired_ledger.tsv"][1],
              sorted(data["unpaired_ledger"], key=lambda row: (row[0], row[2])),
              "\t")

    _out_json(out / "pairing_constraint_report.json",
              {"event_reference": data["event_reference"],
               "rounds": data["round_report"]})

    _out_rows(out / "game_differential_ledger.psv",
              SCHEMA_BY_NAME["game_differential_ledger.psv"][1],
              sorted(data["differential_ledger"], key=lambda row: row[0]), "|")

    _out_rows(out / "tiebreak_resolution_ledger.csv",
              SCHEMA_BY_NAME["tiebreak_resolution_ledger.csv"][1],
              data["resolution"], ",")

    _out_json(out / "final_ranking.json", {
        "event_id": data["event_id"],
        "event_reference": data["event_reference"],
        "round_count": data["round_count"],
        "player_count": len(order),
        "ranking": [{"rank": data["rank_of"][pid],
                     "player_id": pid,
                     "event_points": data["event_points"][pid],
                     "adjusted_delta": data["adjusted_delta"][pid],
                     "opponent_strength": data["strength"][pid],
                     "penalty_adjusted_strength": data["adjusted_strength"][pid]}
                    for pid in data["ranking"]]})

    traces = []
    for pid in order:
        rows = []
        for r in range(1, data["round_count"] + 1):
            if (pid, r) in data["round_points_of"]:
                rows.append({"round_no": r,
                             "state": data["state_of"][(pid, r)],
                             "basis": data["basis_of"][(pid, r)],
                             "round_points": data["round_points_of"][(pid, r)],
                             "game_delta": data["delta_of"][(pid, r)]})
            else:
                rows.append({"round_no": r,
                             "state": data["state_of"][(pid, r)],
                             "basis": "none",
                             "round_points": 0,
                             "game_delta": 0})
        traces.append({"player_id": pid,
                       "division_id": entrants[pid]["division_id"],
                       "seed_number": entrants[pid]["seed_number"],
                       "rounds": rows,
                       "event_points": data["event_points"][pid],
                       "adjusted_delta": data["adjusted_delta"][pid],
                       "opponent_strength": data["strength"][pid],
                       "rank": data["rank_of"][pid],
                       "awarded_cents": data["awarded_of"].get(pid, 0)})
    _out_jsonl(out / "player_audit_trace.jsonl", traces)

    _out_rows(out / "prize_allocation_ledger.csv",
              SCHEMA_BY_NAME["prize_allocation_ledger.csv"][1],
              sorted(data["allocation"], key=lambda row: row[0]), ",")
    _out_rows(out / "prize_tie_split.tsv",
              SCHEMA_BY_NAME["prize_tie_split.tsv"][1],
              sorted(data["tie_split"], key=lambda row: row[0]), "\t")

    report_order = {}
    for section, records in data["roster_conf"].items():
        if not section.startswith("division:"):
            continue
        division = section.split(":", 1)[1]
        for record in records:
            if record.get("record_status") != "operative":
                continue
            if record.get("event_reference") != data["event_reference"]:
                continue
            report_order[division] = int(record["report_order"])

    division_rows = {}
    for div in data["divisions"]:
        members = [pid for pid in order if entrants[pid]["division_id"] == div]
        boards = sum(1 for row in data["pairing_ledger"]
                     if entrants[row[2]]["division_id"] == div)
        byes = sum(1 for row in data["bye_ledger"] if row[1] == div)
        voided = sum(1 for row in data["void_ledger"]
                     if entrants[row[2]]["division_id"] == div)
        awarded = sum(data["awarded_of"].get(pid, 0) for pid in members)
        top = min(members, key=lambda pid: data["rank_of"][pid]) if members else absent
        payload = {
            "division_id": div,
            "in_force": True,
            "report_order": report_order[div],
            "seated_players": len(members),
            "paired_boards": boards,
            "byes_awarded": byes,
            "voided_boards": voided,
            "points_total": sum(data["event_points"][pid] for pid in members),
            "game_delta_total": sum(data["adjusted_delta"][pid] for pid in members),
            "awarded_cents": awarded,
            "award_share_ratio": nine_places(awarded, data["pool_cents"]),
            "top_player": top,
        }
        division_rows[div] = payload
        _out_json(out / ("division_report_%s.json" % div), payload)

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<settlement event_id="%s" event_reference="%s">'
             % (_xml_attr(data["event_id"]), _xml_attr(data["event_reference"]))]
    for div in sorted(data["divisions"], key=lambda d: report_order[d]):
        members = [pid for pid in data["ranking"]
                   if entrants[pid]["division_id"] == div]
        head = ' <division id="%s" report_order="%d" entrants="%d"' % (
            _xml_attr(div), report_order[div], len(members))
        if not members:
            lines.append(head + " />")
            continue
        lines.append(head + ">")
        for pid in members:
            lines.append('  <entrant rank="%d" player_id="%s" event_points="%d" '
                         'adjusted_delta="%d" opponent_strength="%d" '
                         'awarded_cents="%d" />'
                         % (data["rank_of"][pid], _xml_attr(pid),
                            data["event_points"][pid], data["adjusted_delta"][pid],
                            data["strength"][pid], data["awarded_of"].get(pid, 0)))
        lines.append(" </division>")
    lines.append("</settlement>")
    _out_lines(out / "standings_by_division.xml", lines)

    round_points_total = sum(row[7] for row in data["score_ledger"])
    game_delta_total = sum(data["adjusted_delta"][pid] for pid in order)
    penalty_units_total = sum(data["penalty_units"][pid] for pid in order)
    level_counts = {level: sum(entry["level_counts"]["level_%d" % level]
                               for entry in data["round_report"])
                    for level in (0, 1, 2, 3)}
    _out_lines(out / "settlement_control_totals.conf", [
        "[event]",
        "event_id = %s" % data["event_id"],
        "event_reference = %s" % data["event_reference"],
        "round_count = %d" % data["round_count"],
        "player_count = %d" % len(order),
        "",
        "[totals]",
        "round_points_total = %d" % round_points_total,
        "game_delta_total = %d" % game_delta_total,
        "penalty_units_total = %d" % penalty_units_total,
        "points_per_round_ratio = %s" % nine_places(round_points_total,
                                                    data["round_count"]),
        "",
        "[pairing]",
        "boards_total = %d" % len(data["pairing_ledger"]),
        "byes_total = %d" % len(data["bye_ledger"]),
        "voided_total = %d" % len(data["void_ledger"]),
        "unpaired_total = %d" % len(data["unpaired_ledger"]),
        "level_1_boards = %d" % level_counts[1],
        "level_2_boards = %d" % level_counts[2],
        "level_3_boards = %d" % level_counts[3],
        "",
        "[prize]",
        "pool_cents = %d" % data["pool_cents"],
        "awarded_cents = %d" % data["awarded_total"],
        "residue_cents = %d" % data["residue"],
        "tie_groups = %d" % len(data["tie_split"]),
        "award_share_ratio = %s" % nine_places(data["awarded_total"],
                                               data["pool_cents"]),
    ])

    top_rows = data["standings"][:10]
    summary = [
        "# Settlement summary %s" % data["event_reference"],
        "",
        "Event %s settled over %d rounds with %d entrants seated."
        % (data["event_id"], data["round_count"], len(order)),
        "",
        "## Standings",
        "",
        "| rank | player_id | division_id | event_points | adjusted_delta |",
        "|---|---|---|---|---|",
    ]
    for row in top_rows:
        summary.append("| %d | %s | %s | %d | %d |"
                       % (row[0], row[1], row[2], row[3], row[4]))
    summary.extend([
        "",
        "## Pairing",
        "",
        "Boards admitted at level 0: %d. Level 1: %d. Level 2: %d. Level 3: %d."
        % (level_counts[0], level_counts[1], level_counts[2], level_counts[3]),
        "Byes awarded: %d. Boards voided: %d. Entrants left unpaired: %d."
        % (len(data["bye_ledger"]), len(data["void_ledger"]),
           len(data["unpaired_ledger"])),
        "",
        "## Settlement",
        "",
        "Pool %d cents. Awarded %d cents. Residue %d cents."
        % (data["pool_cents"], data["awarded_total"], data["residue"]),
        "Tie groups holding more than one member: %d." % len(data["tie_split"]),
    ])
    _out_lines(out / "event_settlement_summary.md", summary)

    contract = CORE_DOCUMENTS + [name for name in ALL_DOCUMENTS
                                 if name not in CORE_DOCUMENTS
                                 and name != "settlement_manifest.json"]
    core_bytes = b""
    for name in CORE_DOCUMENTS:
        core_bytes += (out / name).read_bytes()
    rest_bytes = b""
    documents = []
    for name in contract:
        payload = (out / name).read_bytes()
        if name not in CORE_DOCUMENTS:
            rest_bytes += payload
        documents.append({"name": name,
                          "sha256": hashlib.sha256(payload).hexdigest(),
                          "bytes": len(payload)})
    _out_json(out / "settlement_manifest.json", {
        "event_id": data["event_id"],
        "event_reference": data["event_reference"],
        "round_count": data["round_count"],
        "player_count": len(order),
        "core_digest": hashlib.sha256(core_bytes).hexdigest(),
        "publication_digest": hashlib.sha256(rest_bytes).hexdigest(),
        "documents": documents,
    })


def run_pipeline(data_dir, out_dir):
    data = load_event(data_dir)
    stage_p01(data)
    stage_p02(data)
    stage_p03(data)
    stage_p04(data)
    stage_rounds(data)
    stage_p10_event(data)
    stage_p12(data)
    stage_p13(data)
    stage_p14(data)
    publish(data, out_dir)
    return data


# --------------------------------------------------------------------------
# corpus assembly
# --------------------------------------------------------------------------


def write_papers(inst, root):
    write_roster_papers(inst, root)
    write_configuration_papers(inst, root)
    write_event_papers(inst, root)
    write_topology_paper(inst, root)
    write_roster_conf(inst, root)
    write_decoy_papers(inst, root)
    write_policy_papers(inst, root)
    write_workbook(inst, root)
    write_memo(inst, root)
    write_directive(inst, root)
    write_schema_reference(inst, root)
    write_guidance_papers(inst, root)
    write_stage_specs(inst, root)


def _rounding_bites(settled):
    """True when at least one published ratio separates a half to even rounding
    from a truncation, so the placement of that rounding has a fixture here."""
    total = sum(row[7] for row in settled["score_ledger"])
    pairs = [(total, settled["round_count"]),
             (settled["awarded_total"], settled["pool_cents"])]
    for div in settled["divisions"]:
        paid = sum(settled["awarded_of"].get(pid, 0) for pid in settled["order"]
                   if settled["entrants"][pid]["division_id"] == div)
        pairs.append((paid, settled["pool_cents"]))
    for top, bottom in pairs:
        if int(bottom) == 0:
            continue
        exact = Fraction(int(top) * 10 ** 9, int(bottom))
        if round_half_even(exact) != exact.numerator // exact.denominator:
            return True
    return False


def _mint_band_division_board(inst, settled):
    """One recorded cross division board in the last round whose two entrants
    stand further apart than the effective band of the division of player_a and
    no further than that of player_b. The score band check is ranked ahead of
    the cross division check on this profile, so the division the band widening
    is read from decides the recorded reason. The board sits on a table above
    every other table of the round, so it is the board of neither entrant and
    moves no score; it is screened and enters the opponent history as a void."""
    last = inst["rounds"]
    ref = inst["event_reference"]
    widening = {row[1]: int(row[4]) for row in inst["division_matrix_rows"]
                if row[0] == ref and int(row[2]) == last and row[3] == "band_widening"}
    opening = {row[1]: row[5] for row in settled["eligibility_ledger"] if row[0] == last}
    seated_at_a_table = {pid for board in settled["candidates_by_round"].get(last, [])
                         for pid in (board["player_a"], board["player_b"])}
    strict = sorted({pid for row in settled["pairing_ledger"]
                     if row[0] == last and row[6] == 0 for pid in (row[2], row[3])}
                    & seated_at_a_table)
    division = {pid: settled["entrants"][pid]["division_id"] for pid in strict}
    band = settled["score_band"]
    for pa in strict:
        for pb in strict:
            if division[pa] == division[pb]:
                continue
            gap = abs(opening[pa] - opening[pb])
            if band + widening[division[pa]] < gap <= band + widening[division[pb]]:
                table = max(int(row[2]) for row in inst["pairing_rows"]
                            if row[0] == ref and int(row[1]) == last) + 1
                source_seq = max(int(row[6]) for row in inst["pairing_rows"]) + 1
                inst["pairing_rows"].append([ref, last, table, pa, pb, 1, source_seq,
                                             "recorded"])
                inst["band_division_board"] = (last, table, pa, pb)
                return


def _mint_tolerance_boards(inst, settled):
    """Recorded boards in the last round whose two entrants both take their
    tolerance from pairing_precedence_policy.toml rather than from an admission
    level: two entrants not eligible in the round, the holder of the bye against
    one such entrant, and an unpaired entrant against one. Each board holds an entrant that is not eligible, so it creates no
    encounter, and it sits above every other table of the round. Its void row
    and the void counts read the tolerance the policy gives. Each kind is placed
    in the latest round that offers it."""
    ref = inst["event_reference"]

    def outside_of(r):
        return sorted(row[1] for row in settled["eligibility_ledger"]
                      if row[0] == r and row[3] == "no")

    def seated_at_a_table(r):
        return {pid for board in settled["candidates_by_round"].get(r, [])
                for pid in (board["player_a"], board["player_b"])}

    boards = []
    for r in range(inst["rounds"], 0, -1):
        outside = outside_of(r)
        if len(outside) >= 2:
            boards.append((r, outside[0], outside[1]))
            break
    for r in range(inst["rounds"], 0, -1):
        outside = outside_of(r)
        holders = sorted(row[2] for row in settled["bye_ledger"] if row[0] == r)
        if holders and outside:
            boards.append((r, holders[0], outside[0]))
            break
    for r in range(inst["rounds"], 0, -1):
        outside = outside_of(r)
        unpaired = sorted(row[2] for row in settled["unpaired_ledger"] if row[0] == r)
        at_a_table = [pid for pid in unpaired if pid in seated_at_a_table(r)]
        # An unpaired entrant with no board of its own takes this void as its
        # board, which is allowed only in the last round, where it reaches no
        # later pairing.
        chosen = at_a_table or (unpaired if r == inst["rounds"] else [])
        if chosen and outside:
            boards.append((r, chosen[0], outside[0]))
            break
    source_seq = max(int(row[6]) for row in inst["pairing_rows"])
    for r, pa, pb in boards:
        table = max(int(row[2]) for row in inst["pairing_rows"]
                    if row[0] == ref and int(row[1]) == r) + 1
        source_seq += 1
        inst["pairing_rows"].append([ref, r, table, pa, pb, 1, source_seq, "recorded"])
    inst["tolerance_boards"] = boards


def mint_corpus(seed, profile, root, identity=None):
    """Mint the working papers of one event.

    The pass is done twice. Which entrant leads the standings is decided by the
    settlement itself, so the register cannot know at minting time which notice
    would put a prize winning entrant outside eligibility. The first pass settles
    the event, the notice is filed against the entrant that led it, and the
    notice register alone is rewritten; no other paper depends on it.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    inst = mint_instance(seed, profile, identity)
    write_papers(inst, root)
    probe = Path(tempfile.mkdtemp(prefix="crownsettle-probe-"))
    try:
        settled = run_pipeline(root, probe / "out")
        sequence = max(int(row[5]) for row in inst["penalty_rows"])
        # A notice against the entrant that led the standings, so the forfeit
        # branch of the prize split is reached.
        leader = settled["ranking"][0]
        sequence += 1
        inst["penalty_rows"].append([inst["event_reference"], leader, "tournament",
                                     settled["disqualify_units"], inst["rounds"],
                                     sequence, "served"])
        # A notice larger than the closed total of the entrant that scored least,
        # so the floor of the tournament class bites and a shortfall is recorded.
        tail = min(settled["order"], key=lambda pid: (settled["running_points"][pid],
                                                     pid))
        sequence += 1
        inst["penalty_rows"].append([
            inst["event_reference"], tail, "tournament",
            settled["running_points"][tail] + 2, inst["rounds"], sequence,
            "served"])
        # A notice heavy enough that the strength debit takes the weakest
        # opponent strength of the event below zero, so that floor bites too.
        weakest = min(settled["order"], key=lambda pid: (settled["strength"][pid],
                                                         pid))
        sequence += 1
        inst["penalty_rows"].append([
            inst["event_reference"], weakest, "tournament",
            settled["strength"][weakest] // inst["strength_debit"] + 1,
            inst["rounds"], sequence, "served"])
        if profile == BRANCH_FIXTURE_PROFILE:
            _mint_band_division_board(inst, settled)
        if inst["policy"]["tolerance"] != CANONICAL_POLICY["tolerance"]:
            _mint_tolerance_boards(inst, settled)
        write_event_papers(inst, root)
        # The pool is nudged until at least one published ratio separates the
        # half to even rounding of the arithmetic policy from a truncation, so
        # that convention carries a fixture on this event rather than only on
        # the ones the agent never sees. The notices above do not move with the
        # pool, so the search leaves their guarantees intact.
        base = inst["pool_cents"]
        for bump in range(0, 24):
            inst["pool_cents"] = base + bump
            write_workbook(inst, root)
            if _rounding_bites(run_pipeline(root, probe / ("pass_%d" % bump))):
                break
        else:
            raise ValueError("no pool in the search window gives the published "
                             "ratio rounding a fixture on this event")
    finally:
        shutil.rmtree(str(probe), ignore_errors=True)
    return inst


# --------------------------------------------------------------------------
# grading scaffolding
#
# Three roots. The work root is traversable, holds the minted papers and every
# output directory the graded program writes into, and is where the program is
# run from. The reference root keeps its 0700 root ownership and holds every
# recomputed settlement, so a program dropped to an unprivileged user cannot
# reach a reference and copy it out.
#
# rewardkit evaluates the checks below in worker threads. Every check holds
# _LOCK for its whole body, because the cached corpora, references and program
# runs in _STATE are shared between checks and minted on first use.
# --------------------------------------------------------------------------

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_STATE = {}
_LOCK = threading.RLock()

# The delivered program is hostile input. It gets no variable of the verifier
# environment, which carries the judge credentials, only what an interpreter
# needs to start.
_PROGRAM_ENV_PATH = "/usr/local/bin:/usr/bin:/bin"


def _bind(workspace):
    _STATE["workspace"] = Path(os.path.abspath(workspace))


def _drops_privileges():
    return os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() == 0


def _untrusted(command):
    """Submitted code runs as nobody so it cannot read this module, which holds
    the reference pipeline and the seeds."""
    if not _drops_privileges():
        return command
    if shutil.which("setpriv") is None:
        raise RuntimeError("setpriv is required to isolate submitted code from the tests")
    return [*_SETPRIV, *command]


def _workroot():
    root = _STATE.get("workroot")
    if root is None:
        root = Path(tempfile.mkdtemp(prefix="crownsettle-work-"))
        # mkdtemp is 0700 and root owned. The dropped child has to traverse it
        # and to create its own output directory inside it, because the contract
        # has the program create that directory rather than find it waiting.
        # Every entry here is scanned: the reference settlements the child must
        # never reach live under the reference root, which stays 0700.
        os.chmod(root, 0o777)
        _STATE["workroot"] = root
    return root


def _refroot():
    root = _STATE.get("refroot")
    if root is None:
        root = Path(tempfile.mkdtemp(prefix="crownsettle-ref-"))
        _STATE["refroot"] = root
    return root


def _programcwd():
    path = _STATE.get("programcwd")
    if path is None:
        path = _workroot() / "cwd"
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o777)
        _STATE["programcwd"] = path
    return path


def _relax(path):
    for item in Path(path).rglob("*"):
        try:
            os.chmod(item, 0o777 if item.is_dir() else 0o666)
        except OSError:
            pass
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass


def _case(seed):
    """Mint one event and recompute its settlement. Cached."""
    key = "case-%d" % seed
    cached = _STATE.get(key)
    if cached is not None:
        return cached
    data_dir = _workroot() / ("event_%d" % seed) / "papers"
    ref_dir = _refroot() / ("event_%d" % seed)
    if not data_dir.is_dir():
        mint_corpus(seed, SEED_PROFILE[seed], data_dir)
        run_pipeline(data_dir, ref_dir)
        _relax(data_dir)
        _relax(data_dir.parent)
    _STATE[key] = (data_dir, ref_dir)
    return _STATE[key]


def _renamed_case():
    """The shipped event re-minted under RENAMED_IDENTITY and its settlement.
    Cached."""
    key = "case-renamed"
    cached = _STATE.get(key)
    if cached is not None:
        return cached
    data_dir = _workroot() / "event_renamed" / "papers"
    ref_dir = _refroot() / "event_renamed"
    if not data_dir.is_dir():
        mint_corpus(SAMPLE_SEED, SEED_PROFILE[SAMPLE_SEED], data_dir, RENAMED_IDENTITY)
        run_pipeline(data_dir, ref_dir)
        _relax(data_dir)
        _relax(data_dir.parent)
    _STATE[key] = (data_dir, ref_dir)
    return _STATE[key]


def _delivered():
    return _STATE.get("workspace", Path("/app")) / "out"


def _program():
    path = _delivered() / PROGRAM_NAME
    if not path.is_file():
        raise AssertionError("no %s was delivered at %s" % (PROGRAM_NAME, path))
    return path


def _program_present():
    """A detector never fires on an empty container: with nothing delivered
    there is no program to charge."""
    return (_delivered() / PROGRAM_NAME).is_file()


def _digest_tree(root):
    root = Path(root)
    out = {}
    if not root.is_dir():
        return out
    for item in sorted(root.rglob("*")):
        if item.is_file():
            out[str(item.relative_to(root))] = hashlib.sha256(
                item.read_bytes()).hexdigest()
    return out


def _launch(data_dir, out_dir, swap=False):
    """Run the delivered program once and return its exit code.

    The contract has the program accept its two options in either order and
    create the output directory when it is absent, so the directory handed over
    does not exist yet. Only the parent is prepared, world writable, so the
    child dropped to an unprivileged user can create the leaf itself. The child
    leads its own process group and the whole group is killed before this
    returns, so nothing it spawned outlives the check."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(str(out_dir))
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    options = (["--out", str(out_dir), "--data", str(data_dir)] if swap
               else ["--data", str(data_dir), "--out", str(out_dir)])
    command = [sys.executable, str(_program()), *options]
    env = {"PATH": _PROGRAM_ENV_PATH, "LANG": "C.UTF-8",
           "HOME": str(_programcwd())}
    proc = subprocess.Popen(_untrusted(command), cwd=str(_programcwd()), env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    try:
        proc.communicate(timeout=PROGRAM_TIMEOUT)
    except subprocess.TimeoutExpired:
        # communicate() leaves a timed out child running, so the group is
        # killed before the pipes are drained, and the drain is bounded too,
        # because a grandchild that left the group can still hold them open.
        _kill_group(proc)
        try:
            proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        return None
    finally:
        _kill_group(proc)
    return proc.returncode


def _kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass


def _run_program(data_dir, out_dir, swap=False):
    code = _launch(data_dir, out_dir, swap=swap)
    if code != 0:
        raise AssertionError("%s exited %r" % (PROGRAM_NAME, code))


def _case_output(seed, tag="case"):
    """Run the delivered program once per minted event, and remember what the
    run did to both directories. Shared with the cheat detectors."""
    key = "output-%s-%d" % (tag, seed)
    cached = _STATE.get(key)
    if cached is not None:
        return cached
    if not _program_present():
        return None
    data_dir, _ = _case(seed)
    out_dir = _workroot() / ("%s_out_%d" % (tag, seed))
    before = _digest_tree(data_dir)
    failed = ""
    try:
        _run_program(data_dir, out_dir, swap=(seed == CHALLENGE_SEED))
    except Exception as exc:
        failed = str(exc) or "failed"
    after = _digest_tree(data_dir)
    record = {"out": out_dir, "before": before, "after": after, "failed": failed}
    _STATE[key] = record
    return record


def _same_bytes(ref_dir, got_dir, names):
    ref_dir = Path(ref_dir)
    got_dir = Path(got_dir)
    for name in names:
        target = got_dir / name
        if not target.is_file():
            return False
        if target.read_bytes() != (ref_dir / name).read_bytes():
            return False
    return True


def _minted_output(seed):
    """The directory the delivered program wrote for one minted event, or None
    when no program ran cleanly on it."""
    record = _case_output(seed)
    if record is None or record["failed"]:
        return None
    return record["out"]


def _contract_order():
    return CORE_DOCUMENTS + [name for name in ALL_DOCUMENTS
                             if name not in CORE_DOCUMENTS
                             and name != "settlement_manifest.json"]


def _manifest_consistent(ref_dir, got_dir):
    """The delivered manifest is the manifest the serialisation contract makes
    of the documents delivered beside it.

    The event fields come from the reference, the digests and lengths from the
    delivered bytes, so a wrong document anywhere costs its own family and
    leaves this check standing, while a manifest that does not describe the
    delivery fails it."""
    ref_dir = Path(ref_dir)
    got_dir = Path(got_dir)
    target = got_dir / "settlement_manifest.json"
    if not target.is_file():
        return False
    reference = json.loads((ref_dir / "settlement_manifest.json").read_text(encoding="utf-8"))
    core_bytes = b""
    rest_bytes = b""
    documents = []
    for name in _contract_order():
        beside = got_dir / name
        if not beside.is_file():
            return False
        payload = beside.read_bytes()
        if name in CORE_DOCUMENTS:
            core_bytes += payload
        else:
            rest_bytes += payload
        documents.append({"name": name,
                          "sha256": hashlib.sha256(payload).hexdigest(),
                          "bytes": len(payload)})
    expected = {
        "event_id": reference["event_id"],
        "event_reference": reference["event_reference"],
        "round_count": reference["round_count"],
        "player_count": reference["player_count"],
        "core_digest": hashlib.sha256(core_bytes).hexdigest(),
        "publication_digest": hashlib.sha256(rest_bytes).hexdigest(),
        "documents": documents,
    }
    want = (json.dumps(expected, indent=1) + "\n").encode("utf-8")
    return target.read_bytes() == want


ALL_ARTIFACTS = sorted(set(ALL_DOCUMENTS))

# Module names a planted file could shadow inside the verifier. The reference
# pipeline imports every one of them.
REBINDING_NAMES = {
    "ast.py", "fractions.py", "hashlib.py", "io.py", "json.py", "os.py", "pathlib.py",
    "shutil.py", "signal.py", "sitecustomize.py", "sqlite3.py", "subprocess.py",
    "sys.py", "tempfile.py", "threading.py", "usercustomize.py", "zipfile.py",
}

# The paper withheld from the corpus the missing paper check hands over. The
# memorandum is required by six stages, so a program that settles anything
# without it has read nothing from it.
WITHHELD_PAPER = "appeals_procedure_memo.pdf"


# --------------------------------------------------------------------------
# what each check measures
# --------------------------------------------------------------------------


def _artifacts_exist():
    out = _delivered()
    return (all((out / name).is_file() for name in ALL_ARTIFACTS)
            and (out / PROGRAM_NAME).is_file())


def _documents_parse():
    """The spine documents open as the shapes the contract names: the JSON
    documents parse, the JSON lines documents parse line by line, and each
    delimited document opens on the header field the schema reference puts
    first. Every byte inside them is graded by the family checks."""
    out = _delivered()
    for name in ("settlement_manifest.json", "pairing_constraint_report.json",
                 "final_ranking.json"):
        json.loads((out / name).read_text(encoding="utf-8"))
    for name in ("normalised_entries.jsonl", "player_audit_trace.jsonl"):
        for line in (out / name).read_text(encoding="utf-8").split("\n"):
            if line:
                json.loads(line)
    for name, sep, header in (
        ("participation_ledger.csv", ",", "player_id"),
        ("round_match_candidates.csv", ",", "round_no"),
        ("match_result_ledger.csv", ",", "round_no"),
        ("round_eligibility_ledger.csv", ",", "round_no"),
        ("bye_ledger.csv", ",", "round_no"),
        ("authoritative_pairing_ledger.csv", ",", "round_no"),
        ("void_adjudication_ledger.csv", ",", "round_no"),
        ("round_score_ledger.csv", ",", "round_no"),
        ("penalty_application_ledger.psv", "|", "round_no"),
        ("opponent_history_ledger.csv", ",", "round_no"),
        ("opponent_strength_ledger.csv", ",", "player_id"),
        ("standings_ledger.csv", ",", "rank"),
        ("game_differential_ledger.psv", "|", "player_id"),
        ("repeat_opponent_audit.tsv", "\t", "player_id"),
        ("prize_allocation_ledger.csv", ",", "rank"),
    ):
        first = (out / name).read_text(encoding="utf-8").split("\n")[0]
        if first.split(sep)[0] != header:
            return False
    return True


def _shipped_family(family):
    _, ref_dir = _case(SAMPLE_SEED)
    return _same_bytes(ref_dir, _delivered(), family)


def _shipped_manifest():
    _, ref_dir = _case(SAMPLE_SEED)
    return _manifest_consistent(ref_dir, _delivered())


def _program_family(seed, family):
    out = _minted_output(seed)
    if out is None:
        return False
    _, ref_dir = _case(seed)
    return _same_bytes(ref_dir, out, family)


def _program_manifest(seed):
    out = _minted_output(seed)
    if out is None:
        return False
    _, ref_dir = _case(seed)
    return _manifest_consistent(ref_dir, out)


def _refuses_missing_paper():
    """With a required paper absent the program exits non zero and writes no
    document, as the failure clause of the program contract states. A program
    that exits non zero on the complete corpus as well has refused nothing, so
    the refusal only counts once the same program settled that corpus cleanly."""
    if not _program_present():
        return False
    if _minted_output(EVAL_SEED) is None:
        return False
    data_dir, _ = _case(EVAL_SEED)
    partial = _workroot() / "missing_paper" / "papers"
    if not partial.is_dir():
        partial.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(data_dir), str(partial))
        (partial / WITHHELD_PAPER).unlink()
        _relax(partial)
        _relax(partial.parent)
    out_dir = _workroot() / "missing_paper_out"
    code = _launch(partial, out_dir)
    if code is None or code == 0:
        return False
    return not (out_dir.is_dir() and any(p.is_file() for p in out_dir.rglob("*")))


# --------------------------------------------------------------------------
# cheat detectors
#
# Several of these would otherwise fire together on one agent decision, which
# charges one mistake two or three times and distorts the reward floor. They are
# carved into disjoint conditions along a single ownership order, so every action
# below costs exactly one penalty:
#
#   nondeterministic_output    the program disagrees with itself on a declared
#                              document
#   filename_dependent         it agrees with itself, differs on a declared
#                              document when renamed
#   program_dirties            it changed its input or wrote an undeclared file,
#                              and neither detector above already charged it
#   rebinds_verifier           it planted a module the verifier imports
#   hardcoded_sample_answers   it replays the shipped answers, which the shipped
#                              event re-minted under another identity exposes,
#                              and none of the mechanical defects above explains it
#   program_ignores_its_input  it writes one answer for every input and is no
#                              replayer of the shipped one
#   names_shipped_event        it holds this event's identity as a value and it is
#                              no replayer
#
# The replayer deliberately stands down for the mechanical defects. An agent that
# derived the shipped event honestly and then shipped a general program carrying
# a nondeterminism or a filename bug broke all three unseen events for a reason
# that has its own detector, and charging it for cheating it did not do is the
# one false brand this set could produce.
# --------------------------------------------------------------------------


def _ran_everywhere():
    """Every minted event produced a run to compare. Without three runs none of
    the program-shape questions below can be answered at all."""
    records = []
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None or record["failed"]:
            return None
        records.append(record)
    return records


def _declared_digests(root):
    """The digests of the declared documents under root. The determinism and
    filename detectors compare these alone, so an undeclared file is charged
    once, by the dirtiness detector, and never again through its bytes."""
    declared = set(ALL_ARTIFACTS)
    return {name: digest for name, digest in _digest_tree(root).items()
            if name in declared}


def _nondeterministic():
    seed = MINTED_SEEDS[0]
    first = _case_output(seed)
    second = _case_output(seed, tag="repeat")
    if first is None or second is None or first["failed"] or second["failed"]:
        return False
    return _declared_digests(first["out"]) != _declared_digests(second["out"])


def _filename_dependent():
    """The same event under another directory name comes out differently. A
    program that already disagrees with itself is left to the determinism
    detector, because it would differ under a second name for that reason."""
    cached = _STATE.get("filename_dependent")
    if cached is not None:
        return cached
    seed = MINTED_SEEDS[0]
    record = _case_output(seed)
    if record is None or record["failed"] or _nondeterministic():
        return False
    data_dir, _ = _case(seed)
    renamed = _workroot() / "an_differently_named_event" / "papers"
    if not renamed.is_dir():
        renamed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(data_dir), str(renamed))
        _relax(renamed)
        _relax(renamed.parent)
    other = _workroot() / "renamed_out"
    if _launch(renamed, other) != 0:
        verdict = True
    else:
        verdict = _declared_digests(record["out"]) != _declared_digests(other)
    _STATE["filename_dependent"] = verdict
    return verdict


def _input_blind():
    """One answer for every input directory, delivered as the declared document
    set. A program that wrote no complete document set is no evidence of
    ignoring its input."""
    records = _ran_everywhere()
    if records is None:
        return False
    trees = []
    for record in records:
        tree = _digest_tree(record["out"])
        if sorted(tree) != sorted(ALL_ARTIFACTS):
            return False
        trees.append(tree)
    return all(tree == trees[0] for tree in trees)


def _planted_modules():
    """Names the program dropped where an import inside this container would
    find them ahead of the standard library."""
    planted = set()
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None or record["failed"]:
            continue
        if record["out"].is_dir():
            planted |= {p.name for p in record["out"].iterdir()} & REBINDING_NAMES
    planted |= {p.name for p in _workroot().iterdir() if p.is_file()} & REBINDING_NAMES
    if _delivered().is_dir():
        planted |= {p.name for p in _delivered().iterdir()
                    if p.is_file()} & REBINDING_NAMES
    return planted


def _dirtied():
    """The program changed the directory it was pointed at, or put something in
    the output directory that is no declared document. A declared document it
    left out is graded by the family checks and is no dirtiness."""
    records = _ran_everywhere()
    if records is None:
        return False
    declared = set(ALL_ARTIFACTS)
    for record in records:
        if record["before"] != record["after"]:
            return True
        if record["out"].is_dir():
            written = {p.name for p in record["out"].iterdir()}
            if written - declared:
                return True
    return any(p.is_file() for p in _workroot().iterdir())


def _mechanically_broken():
    """A defect of the program's machinery that already explains why the events
    it has never seen came out wrong, and that carries its own detector. The
    replayer charge stands down for every one of these, so an honest derivation
    shipped behind a buggy program is charged for the bug rather than for a cheat
    it did not commit."""
    return bool(_nondeterministic() or _filename_dependent()
                or _planted_modules() or _dirtied())


def _renamed_output():
    """The directory the delivered program wrote for the re-minted shipped event,
    or None when it did not run cleanly there. Cached."""
    key = "output-renamed"
    if key in _STATE:
        return _STATE[key]
    result = None
    if _program_present():
        data_dir, _ = _renamed_case()
        out_dir = _workroot() / "renamed_identity_out"
        try:
            _run_program(data_dir, out_dir)
            result = out_dir
        except Exception:
            result = None
    _STATE[key] = result
    return result


def _is_replayer():
    """The delivered program carries the shipped answers: the shipped delivery is
    byte exact, and the same program does not reproduce the shipped event once
    that event is re-minted under another identity.

    The re-minted papers differ from the shipped ones only in the event
    identifier, the event reference and the prefix every player identifier
    shares, so any reading of the rules, right or wrong, settles the two alike.
    Only a program keyed on the shipped identity or on the shipped bytes tells
    them apart. A solver that misread a rule whose effect the shipped event
    happens not to show reproduces both and is never branded a replayer; the
    unseen events already price that misreading.
    """
    cached = _STATE.get("replayer")
    if cached is not None:
        return cached
    _, ref_dir = _case(SAMPLE_SEED)
    verdict = False
    if _same_bytes(ref_dir, _delivered(), ALL_ARTIFACTS):
        out = _renamed_output()
        _, renamed_ref = _renamed_case()
        verdict = out is None or not _same_bytes(renamed_ref, out, ALL_ARTIFACTS)
    _STATE["replayer"] = verdict
    return verdict


def _replays_answers():
    if not _program_present() or _mechanically_broken():
        return False
    return _is_replayer()


def _held_literals(source):
    """The string literals the program holds, without its comments and
    docstrings, so an identifier mentioned in prose is not a held value. Source
    that does not parse is scanned whole."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return source
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    held = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and id(node) not in docstrings:
            if isinstance(node.value, str):
                held.append(node.value)
            elif isinstance(node.value, bytes):
                held.append(node.value.decode("latin-1"))
    return "\n".join(held)


def _names_this_event():
    """Its source holds this event identifier or its event reference as a value,
    both of which the program contract requires it to read from the directory it
    is pointed at."""
    if not _program_present() or _is_replayer():
        return False
    source = _program().read_text(encoding="utf-8", errors="replace")
    held = _held_literals(source)
    planted = [_event_id(SAMPLE_SEED), _event_reference(SAMPLE_SEED)]
    return any(token in held for token in planted)


def _ignores_input():
    if not _program_present() or _ran_everywhere() is None or _is_replayer():
        return False
    return _input_blind()


def _dirties():
    if not _program_present() or _ran_everywhere() is None or _planted_modules():
        return False
    # A program that changed its input can disagree with itself or with a
    # renamed copy for that reason alone; that act is charged once, by the
    # detector that owns it.
    if _nondeterministic() or _filename_dependent():
        return False
    return _dirtied()


# --------------------------------------------------------------------------
# positive checks
# --------------------------------------------------------------------------


@criterion(description="every declared settlement document and the program exist under /app/out")
def all_artifacts_exist(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _artifacts_exist()
    except Exception:
        return False


@criterion(description="the spine JSON, JSON lines and delimited documents open as the shapes the schema reference names")
def core_documents_parse(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _documents_parse()
    except Exception:
        return False


@criterion(description="the thirteen stage spine documents of the shipped event are byte exact")
def shipped_core_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _shipped_family(FAMILY_CORE)
    except Exception:
        return False


@criterion(description="the pairing family of the shipped event is byte exact")
def shipped_pairing_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _shipped_family(FAMILY_PAIRING)
    except Exception:
        return False


@criterion(description="the standings family of the shipped event is byte exact")
def shipped_standings_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _shipped_family(FAMILY_STANDINGS)
    except Exception:
        return False


@criterion(description="the prize allocation, tie split and division reports of the shipped event are byte exact")
def shipped_prize_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _shipped_family(FAMILY_PRIZE)
    except Exception:
        return False


@criterion(description="the division XML, control totals and settlement summary of the shipped event are byte exact")
def shipped_publication_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _shipped_family(FAMILY_PUBLICATION)
    except Exception:
        return False


@criterion(description="the shipped settlement manifest is the one the digest contract makes of the documents delivered beside it")
def shipped_manifest_consistent(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _shipped_manifest()
    except Exception:
        return False


@criterion(description="the delivered program reproduces the thirteen stage spine of the unseen contested event")
def contested_core_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(EVAL_SEED, FAMILY_CORE)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the pairing family of the unseen contested event")
def contested_pairing_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(EVAL_SEED, FAMILY_PAIRING)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the standings family of the unseen contested event")
def contested_standings_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(EVAL_SEED, FAMILY_STANDINGS)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the prize documents of the unseen contested event")
def contested_prize_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(EVAL_SEED, FAMILY_PRIZE)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the publication documents of the unseen contested event")
def contested_publication_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(EVAL_SEED, FAMILY_PUBLICATION)
    except Exception:
        return False


@criterion(description="the manifest the delivered program writes for the contested event describes the documents beside it")
def contested_manifest_consistent(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_manifest(EVAL_SEED)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the thirteen stage spine of the unseen wide event")
def wide_core_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(CHALLENGE_SEED, FAMILY_CORE)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the pairing family of the unseen wide event")
def wide_pairing_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(CHALLENGE_SEED, FAMILY_PAIRING)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the standings family of the unseen wide event")
def wide_standings_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(CHALLENGE_SEED, FAMILY_STANDINGS)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the prize documents of the unseen wide event")
def wide_prize_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(CHALLENGE_SEED, FAMILY_PRIZE)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the publication documents of the unseen wide event")
def wide_publication_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(CHALLENGE_SEED, FAMILY_PUBLICATION)
    except Exception:
        return False


@criterion(description="the manifest the delivered program writes for the wide event describes the documents beside it")
def wide_manifest_consistent(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_manifest(CHALLENGE_SEED)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the thirteen stage spine of the unseen thin event")
def thin_core_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(PROBE_SEED, FAMILY_CORE)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the pairing family of the unseen thin event")
def thin_pairing_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(PROBE_SEED, FAMILY_PAIRING)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the standings family of the unseen thin event")
def thin_standings_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(PROBE_SEED, FAMILY_STANDINGS)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the prize documents of the unseen thin event")
def thin_prize_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(PROBE_SEED, FAMILY_PRIZE)
    except Exception:
        return False


@criterion(description="the delivered program reproduces the publication documents of the unseen thin event")
def thin_publication_exact(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_family(PROBE_SEED, FAMILY_PUBLICATION)
    except Exception:
        return False


@criterion(description="the manifest the delivered program writes for the thin event describes the documents beside it")
def thin_manifest_consistent(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _program_manifest(PROBE_SEED)
    except Exception:
        return False


@criterion(description="the delivered program exits non zero and writes no document when a required paper is absent")
def program_refuses_missing_paper(workspace: Path) -> bool:
    try:
        with _LOCK:
            _bind(workspace)
            return _refuses_missing_paper()
    except Exception:
        return False


# --------------------------------------------------------------------------
# negative checks: each returns True when the cheat happened, and its negative
# weight does the punishing, so an honest delivery escapes the penalty
# --------------------------------------------------------------------------


@criterion(description="the delivered program reproduces the shipped event but not the same event re-minted under another identity, so it carries answers rather than a derivation")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        with _LOCK:
            _bind(workspace)
            return _replays_answers()
    except Exception:
        return False


@criterion(description="the delivered program holds the shipped event identifier or event reference as a string value")
def negative_names_shipped_event(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        with _LOCK:
            _bind(workspace)
            return _names_this_event()
    except Exception:
        return False


@criterion(description="the delivered program writes the same complete document set for every unseen event")
def negative_program_ignores_its_input(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        with _LOCK:
            _bind(workspace)
            return _ignores_input()
    except Exception:
        return False


@criterion(description="two runs of the delivered program over one input directory disagree")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        with _LOCK:
            _bind(workspace)
            return _program_present() and _nondeterministic()
    except Exception:
        return False


@criterion(description="the delivered program writes different bytes when the same event sits under another directory name")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        with _LOCK:
            _bind(workspace)
            return _program_present() and _filename_dependent()
    except Exception:
        return False


@criterion(description="the delivered program changes its input directory or writes an undeclared file")
def negative_program_dirties_its_directories(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        with _LOCK:
            _bind(workspace)
            return _dirties()
    except Exception:
        return False


@criterion(description="the delivered program plants a file that would shadow a module the verifier imports")
def negative_rebinds_verifier_dependencies(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        with _LOCK:
            _bind(workspace)
            return bool(_planted_modules())
    except Exception:
        return False


criteria.all_artifacts_exist(weight=1)
criteria.core_documents_parse(weight=1)
criteria.shipped_core_exact(weight=3)
criteria.shipped_pairing_exact(weight=3)
criteria.shipped_standings_exact(weight=3)
criteria.shipped_prize_exact(weight=3)
criteria.shipped_publication_exact(weight=3)
criteria.shipped_manifest_consistent(weight=1)
criteria.contested_core_exact(weight=5)
criteria.contested_pairing_exact(weight=5)
criteria.contested_standings_exact(weight=5)
criteria.contested_prize_exact(weight=3)
criteria.contested_publication_exact(weight=3)
criteria.contested_manifest_consistent(weight=1)
criteria.wide_core_exact(weight=5)
criteria.wide_pairing_exact(weight=5)
criteria.wide_standings_exact(weight=5)
criteria.wide_prize_exact(weight=3)
criteria.wide_publication_exact(weight=3)
criteria.wide_manifest_consistent(weight=1)
criteria.thin_core_exact(weight=5)
criteria.thin_pairing_exact(weight=5)
criteria.thin_standings_exact(weight=5)
criteria.thin_prize_exact(weight=3)
criteria.thin_publication_exact(weight=3)
criteria.thin_manifest_consistent(weight=1)
criteria.program_refuses_missing_paper(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_names_shipped_event(weight=-3)
criteria.negative_program_ignores_its_input(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_program_dirties_its_directories(weight=-3)
criteria.negative_rebinds_verifier_dependencies(weight=-3)
