#!/usr/bin/env python3
"""Verifier for the GROUNDLINK contact settlement bundle.

Holds the corpus generator, an independent settlement reference, and
the graded assertions. The verifier owns its corpus: it mints every
case it grades from a named seed, so no graded byte depends on the
directory the agent was given.
"""
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
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from rewardkit import criteria, criterion

# ---------------------------------------------------------------------------
# Deterministic file emitters. Every corpus byte this bundle ships is written
# by one of these, so a corpus rebuilt at the same seed is byte identical.
# ---------------------------------------------------------------------------
NL = chr(10)
BS = chr(92)
Q = chr(34)
LT = chr(60)
GT = chr(62)
MASK64 = 0xFFFFFFFFFFFFFFFF


class Rng:
    """xorshift64. CPython random is not contractually stable across releases."""

    def __init__(self, seed):
        self.s = (int(seed) ^ 0x9E3779B97F4A7C15) & MASK64
        if self.s == 0:
            self.s = 0x2545F4914F6CDD1D

    def step(self):
        x = self.s
        x ^= (x << 13) & MASK64
        x ^= x >> 7
        x ^= (x << 17) & MASK64
        self.s = x
        return x

    def below(self, n):
        return self.step() % n

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def pick(self, seq):
        return seq[self.below(len(seq))]

    def chance(self, num, den):
        return self.below(den) < num


def xesc(text):
    return (str(text).replace("&", "&amp;").replace(LT, "&lt;")
            .replace(GT, "&gt;").replace(Q, "&quot;"))


XMLDECL = (LT + "?xml version=" + Q + "1.0" + Q + " encoding=" + Q + "UTF-8" + Q
           + " standalone=" + Q + "yes" + Q + "?" + GT)
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKGREL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CT_SHEETML = "application/vnd.openxmlformats-officedocument.spreadsheetml"
CT_WORDML = "application/vnd.openxmlformats-officedocument.wordprocessingml"


def _q(value):
    return Q + str(value) + Q


def _cell_ref(col, row):
    s = ""
    c = col
    while c > 0:
        c, r = divmod(c - 1, 26)
        s = chr(65 + r) + s
    return s + str(row)


def _sheet_xml(rows, shared, shared_idx):
    out = [XMLDECL]
    out.append("<worksheet xmlns=" + _q(NS_MAIN) + ">")
    out.append("<sheetData>")
    for ri, row in enumerate(rows, start=1):
        out.append("<row r=" + _q(ri) + ">")
        for ci, val in enumerate(row, start=1):
            if val is None or val == "":
                continue
            ref = _cell_ref(ci, ri)
            sval = str(val)
            try:
                float(sval)
                is_num = True
            except ValueError:
                is_num = False
            if is_num:
                out.append("<c r=" + _q(ref) + "><v>" + sval + "</v></c>")
            else:
                if sval not in shared_idx:
                    shared_idx[sval] = len(shared)
                    shared.append(sval)
                out.append("<c r=" + _q(ref) + " t=" + _q("s") + "><v>"
                           + str(shared_idx[sval]) + "</v></c>")
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def _zip_bytes(path, parts):
    stamp = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in parts:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            zf.writestr(info, payload)


def write_xlsx(path, sheets):
    shared = []
    shared_idx = {}
    sheet_xmls = []
    for name, rows in sheets.items():
        sheet_xmls.append((name, _sheet_xml(rows, shared, shared_idx)))

    ss = [XMLDECL]
    ss.append("<sst xmlns=" + _q(NS_MAIN) + " count=" + _q(len(shared))
              + " uniqueCount=" + _q(len(shared)) + ">")
    for s in shared:
        ss.append("<si><t>" + xesc(s) + "</t></si>")
    ss.append("</sst>")

    ct = [XMLDECL, "<Types xmlns=" + _q(NS_CT) + ">"]
    ct.append("<Default Extension=" + _q("rels") + " ContentType="
              + _q("application/vnd.openxmlformats-package.relationships+xml") + "/>")
    ct.append("<Default Extension=" + _q("xml") + " ContentType=" + _q("application/xml") + "/>")
    ct.append("<Override PartName=" + _q("/xl/workbook.xml") + " ContentType="
              + _q(CT_SHEETML + ".sheet.main+xml") + "/>")
    ct.append("<Override PartName=" + _q("/xl/sharedStrings.xml") + " ContentType="
              + _q(CT_SHEETML + ".sharedStrings+xml") + "/>")
    for i in range(1, len(sheets) + 1):
        ct.append("<Override PartName=" + _q("/xl/worksheets/sheet" + str(i) + ".xml")
                  + " ContentType=" + _q(CT_SHEETML + ".worksheet+xml") + "/>")
    ct.append("</Types>")

    root_rels = (XMLDECL + "<Relationships xmlns=" + _q(NS_PKGREL) + ">"
                 + "<Relationship Id=" + _q("rId1") + " Type=" + _q(NS_REL + "/officeDocument")
                 + " Target=" + _q("xl/workbook.xml") + "/></Relationships>")

    wb = [XMLDECL]
    wb.append("<workbook xmlns=" + _q(NS_MAIN) + " xmlns:r=" + _q(NS_REL) + ">")
    wb.append("<sheets>")
    for i, (name, _x) in enumerate(sheet_xmls, start=1):
        wb.append("<sheet name=" + _q(name) + " sheetId=" + _q(i)
                  + " r:id=" + _q("rId" + str(i)) + "/>")
    wb.append("</sheets></workbook>")

    wr = [XMLDECL, "<Relationships xmlns=" + _q(NS_PKGREL) + ">"]
    for i in range(1, len(sheets) + 1):
        wr.append("<Relationship Id=" + _q("rId" + str(i)) + " Type=" + _q(NS_REL + "/worksheet")
                  + " Target=" + _q("worksheets/sheet" + str(i) + ".xml") + "/>")
    wr.append("<Relationship Id=" + _q("rId" + str(len(sheets) + 1)) + " Type="
              + _q(NS_REL + "/sharedStrings") + " Target=" + _q("sharedStrings.xml") + "/>")
    wr.append("</Relationships>")

    parts = [("[Content_Types].xml", "".join(ct)),
             ("_rels/.rels", root_rels),
             ("xl/workbook.xml", "".join(wb)),
             ("xl/_rels/workbook.xml.rels", "".join(wr)),
             ("xl/sharedStrings.xml", "".join(ss))]
    for i, (name, xml) in enumerate(sheet_xmls, start=1):
        parts.append(("xl/worksheets/sheet" + str(i) + ".xml", xml))
    _zip_bytes(path, parts)


def _wpara(text, bold=False):
    props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return ("<w:p><w:r>" + props + "<w:t xml:space=" + _q("preserve") + ">"
            + xesc(text) + "</w:t></w:r></w:p>")


def _wtable(rows):
    out = ["<w:tbl><w:tblPr><w:tblW w:w=" + _q(0) + " w:type=" + _q("auto") + "/>",
           "<w:tblBorders>"]
    for edge in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        out.append("<w:" + edge + " w:val=" + _q("single") + " w:sz=" + _q(4)
                   + " w:space=" + _q(0) + " w:color=" + _q("auto") + "/>")
    out.append("</w:tblBorders></w:tblPr>")
    for row in rows:
        out.append("<w:tr>")
        for cell in row:
            out.append("<w:tc><w:tcPr><w:tcW w:w=" + _q(1800) + " w:type=" + _q("dxa")
                       + "/></w:tcPr>" + _wpara(str(cell)) + "</w:tc>")
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def write_docx(path, blocks):
    """blocks: [("h", text) | ("p", text) | ("table", [[cell, ...], ...])]."""
    body = []
    for kind, payload in blocks:
        if kind == "h":
            body.append(_wpara(str(payload), bold=True))
        elif kind == "p":
            body.append(_wpara(str(payload)))
        else:
            body.append(_wtable(payload))
            body.append(_wpara(""))
    document = (XMLDECL + "<w:document xmlns:w=" + _q(NS_WORD) + "><w:body>"
                + "".join(body)
                + "<w:sectPr><w:pgSz w:w=" + _q(11906) + " w:h=" + _q(16838) + "/>"
                + "<w:pgMar w:top=" + _q(1134) + " w:right=" + _q(1134) + " w:bottom="
                + _q(1134) + " w:left=" + _q(1134) + " w:header=" + _q(708)
                + " w:footer=" + _q(708) + " w:gutter=" + _q(0) + "/></w:sectPr>"
                + "</w:body></w:document>")
    ct = (XMLDECL + "<Types xmlns=" + _q(NS_CT) + ">"
          + "<Default Extension=" + _q("rels") + " ContentType="
          + _q("application/vnd.openxmlformats-package.relationships+xml") + "/>"
          + "<Default Extension=" + _q("xml") + " ContentType=" + _q("application/xml") + "/>"
          + "<Override PartName=" + _q("/word/document.xml") + " ContentType="
          + _q(CT_WORDML + ".document.main+xml") + "/></Types>")
    rels = (XMLDECL + "<Relationships xmlns=" + _q(NS_PKGREL) + ">"
            + "<Relationship Id=" + _q("rId1") + " Type=" + _q(NS_REL + "/officeDocument")
            + " Target=" + _q("word/document.xml") + "/></Relationships>")
    _zip_bytes(path, [("[Content_Types].xml", ct), ("_rels/.rels", rels),
                      ("word/document.xml", document)])


def write_pdf(path, lines):
    def esc(t):
        return t.replace(BS, BS + BS).replace("(", BS + "(").replace(")", BS + ")")

    pages = [lines[i:i + 52] for i in range(0, len(lines), 52)] or [[""]]
    objects = []
    n_pages = len(pages)
    font_obj = 3 + 2 * n_pages
    kids = " ".join(str(3 + 2 * i) + " 0 R" for i in range(n_pages))
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append("<< /Type /Pages /Kids [" + kids + "] /Count " + str(n_pages) + " >>")
    for i, page_lines in enumerate(pages):
        content = "BT /F1 9 Tf 40 750 Td 11 TL" + NL
        for one in page_lines:
            content += "(" + esc(one) + ") Tj T*" + NL
        content += "ET"
        cbytes = content.encode("latin-1", "replace")
        page_obj_num = 3 + 2 * i
        objects.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       "/Resources << /Font << /F1 " + str(font_obj) + " 0 R >> >> "
                       "/Contents " + str(page_obj_num + 1) + " 0 R >>")
        objects.append((cbytes, "<< /Length " + str(len(cbytes)) + " >>"))
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    out = io.BytesIO()
    out.write(("%PDF-1.4" + NL).encode("latin-1"))
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        if isinstance(obj, tuple):
            cbytes, hdr = obj
            out.write((str(i) + " 0 obj" + NL + hdr + NL + "stream" + NL).encode("latin-1"))
            out.write(cbytes)
            out.write((NL + "endstream" + NL + "endobj" + NL).encode("latin-1"))
        else:
            out.write((str(i) + " 0 obj" + NL + obj + NL + "endobj" + NL).encode("latin-1"))
    xref_pos = out.tell()
    n = len(objects) + 1
    out.write(("xref" + NL + "0 " + str(n) + NL).encode("latin-1"))
    out.write(("0000000000 65535 f " + NL).encode("latin-1"))
    for off in offsets[1:]:
        out.write((format(off, "010d") + " 00000 n " + NL).encode("latin-1"))
    out.write(("trailer" + NL + "<< /Size " + str(n) + " /Root 1 0 R >>" + NL
               + "startxref" + NL + str(xref_pos) + NL + "%%EOF" + NL).encode("latin-1"))
    Path(path).write_bytes(out.getvalue())


def write_sqlite(path, tables):
    p = Path(path)
    if p.exists():
        p.unlink()
    con = sqlite3.connect(str(p))
    cur = con.cursor()
    for tname in sorted(tables):
        cols, rows = tables[tname]
        cur.execute("CREATE TABLE " + tname + " ("
                    + ", ".join(c + " TEXT" for c in cols) + ")")
        cur.executemany("INSERT INTO " + tname + " VALUES ("
                        + ", ".join("?" for _ in cols) + ")", rows)
    con.commit()
    con.close()


def wtext(path, text):
    Path(path).write_bytes(text.encode("utf-8"))


def wtable(path, columns, rows, delim):
    out = [delim.join(columns)]
    for r in rows:
        out.append(delim.join(str(r[c]) for c in columns))
    wtext(path, NL.join(out) + NL)


def wjson(path, obj):
    wtext(path, json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + NL)


def wjsonl(path, rows):
    body = [json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            for r in rows]
    wtext(path, NL.join(body) + NL)

# ---------------------------------------------------------------------------
# Corpus readers. Stdlib only, so the settlement core runs anywhere the
# verifier image runs and nothing has to be installed at grade time.
# ---------------------------------------------------------------------------
def read_delim(path, delim=","):
    text = Path(path).read_text(encoding="utf-8")
    lines = [ln for ln in text.split(chr(10)) if ln != ""]
    if not lines:
        return []
    cols = lines[0].split(delim)
    out = []
    for ln in lines[1:]:
        parts = ln.split(delim)
        while len(parts) < len(cols):
            parts.append("")
        out.append(dict(zip(cols, parts)))
    return out


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_ndjson(path):
    out = []
    for ln in Path(path).read_text(encoding="utf-8").split(chr(10)):
        ln = ln.strip()
        if ln:
            out.append(json.loads(ln))
    return out


def read_ini(path):
    """Minimal INI reader. Sections in brackets, key equals value, semicolon
    and hash start a comment line."""
    out = {}
    section = ""
    for raw in Path(path).read_text(encoding="utf-8").split(chr(10)):
        ln = raw.strip()
        if not ln or ln[0] in ";#":
            continue
        if ln[0] == "[" and ln[-1] == "]":
            section = ln[1:-1].strip()
            out.setdefault(section, {})
            continue
        if "=" in ln:
            k, v = ln.split("=", 1)
            out.setdefault(section, {})[k.strip()] = v.strip()
    return out


def read_flat_yaml(path):
    """Two level mapping reader for the shipped yaml documents. Top level keys
    sit at column zero, nested keys are indented by two spaces, list items use
    a leading dash. Values stay strings."""
    out = {}
    cur = None
    for raw in Path(path).read_text(encoding="utf-8").split(chr(10)):
        if not raw.strip() or raw.strip()[0] == "#":
            continue
        if raw[0] not in " -":
            key, _, val = raw.partition(":")
            val = val.strip()
            if val == "":
                out[key.strip()] = {}
                cur = key.strip()
            else:
                out[key.strip()] = val
                cur = None
        elif raw.strip()[0] == "-":
            item = raw.strip()[1:].strip()
            if cur is not None:
                if not isinstance(out[cur], list):
                    out[cur] = []
                out[cur].append(item)
        else:
            key, _, val = raw.strip().partition(":")
            if cur is not None and isinstance(out[cur], dict):
                out[cur][key.strip()] = val.strip()
    return out


def read_xml_records(path, tag):
    """Pull every element with the given tag and return its attributes plus
    the text of its direct children."""
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
    out = []
    for node in root.iter(tag):
        rec = dict(node.attrib)
        for child in node:
            rec[child.tag] = (child.text or "").strip()
        out.append(rec)
    return out


def _col_to_idx(ref):
    col = 0
    for ch in ref:
        if ch.isalpha():
            col = col * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return col


def read_xlsx_sheets(path):
    """Return an ordered mapping of sheet name to a list of row lists."""
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sroot = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sroot:
                shared.append("".join(t.text or "" for t in si.iter()
                                      if t.tag.endswith("}t")))
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        names = []
        for sh in wb.iter():
            if sh.tag.endswith("}sheet"):
                names.append(sh.attrib.get("name"))
        out = {}
        for idx, name in enumerate(names, start=1):
            member = "xl/worksheets/sheet" + str(idx) + ".xml"
            if member not in zf.namelist():
                continue
            sroot = ET.fromstring(zf.read(member))
            rows = []
            for row in sroot.iter():
                if not row.tag.endswith("}row"):
                    continue
                cells = {}
                width = 0
                for c in row:
                    if not c.tag.endswith("}c"):
                        continue
                    ci = _col_to_idx(c.attrib.get("r", "A1"))
                    val = ""
                    for v in c:
                        if v.tag.endswith("}v"):
                            val = v.text or ""
                    if c.attrib.get("t") == "s" and val != "":
                        val = shared[int(val)]
                    cells[ci] = val
                    width = max(width, ci)
                rows.append([cells.get(i, "") for i in range(1, width + 1)])
            out[name] = rows
        return out


def read_pdf_lines(path):
    """Return the text lines of a PDF written by the corpus generator."""
    raw = Path(path).read_bytes()
    out = []
    depth = 0
    cur = []
    i = 0
    esc = False
    while i < len(raw):
        ch = raw[i:i + 1]
        if depth == 0:
            if ch == b"(":
                depth = 1
                cur = []
        else:
            if esc:
                cur.append(ch)
                esc = False
            elif ch == b"\\":
                esc = True
            elif ch == b"(":
                depth += 1
                cur.append(ch)
            elif ch == b")":
                depth -= 1
                if depth == 0:
                    out.append(b"".join(cur).decode("latin-1"))
                else:
                    cur.append(ch)
            else:
                cur.append(ch)
        i += 1
    return out


def read_docx_blocks(path):
    """Return the paragraph strings and the table rows of a DOCX in document
    order. A table row arrives as a list of cell strings."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    w = "{" + "http://schemas.openxmlformats.org/wordprocessingml/2006/main" + "}"
    out = []
    body = None
    for node in root:
        if node.tag == w + "body":
            body = node
    if body is None:
        return out
    for node in body:
        if node.tag == w + "p":
            out.append("".join(t.text or "" for t in node.iter(w + "t")))
        elif node.tag == w + "tbl":
            for tr in node.findall(w + "tr"):
                cells = []
                for tc in tr.findall(w + "tc"):
                    cells.append("".join(t.text or "" for t in tc.iter(w + "t")))
                out.append(cells)
    return out


def read_sqlite_table(path, table):
    con = sqlite3.connect(str(path))
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM " + table)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        con.close()

# ---------------------------------------------------------------------------
# The settlement core. Fourteen stages, integer arithmetic throughout, every
# stage boundary truncated before the next stage consumes the value.
# ---------------------------------------------------------------------------
PERIOD_IDS = ["P1", "P2", "P3"]
RANK = {"emergency_override": 1, "contracted_priority": 2, "ordinary_priority": 3}
COMMIT_GRADES = ("controller", "supervisor")
ADMISSIBLE_EVENTS = ("nominal", "partial")

# Named readings of single rules. The reference runs with the empty set. A
# reading in the set replaces the documented rule with the plausible wrong one
# that the shipped trap list names, which is how the naive path detectors know
# what a wrong reading would have produced.
RULE_IDS = [
    "terms_last_row",
    "cancel_boundary_rejects",
    "protection_as_tiebreak",
    "legacy_flat_rate",
    "aggregate_then_floor",
    "cap_after_aggregation",
    "running_backlog_demand",
    "ration_to_convergence",
    "no_minimum_step",
    "entitlement_before_carry",
    "utilisation_from_admitted",
    "utilisation_denominator_paid",
    "shortfall_reduced_not_waived",
    "late_cancel_in_exempt_pool",
]


def _on(rules, rid):
    return bool(rules) and rid in rules


REJECT_CODES = [
    ("E01", "alias_unresolved"),
    ("E02", "aperture_unknown"),
    ("E03", "station_out_of_scope"),
    ("E04", "phase_standdown"),
    ("E05", "cancelled_before_commit"),
    ("E06", "no_operational_event"),
    ("E07", "event_class_inadmissible"),
    ("E08", "no_eligible_interval"),
]


def _i(v, default=0):
    s = str(v).strip()
    if s == "" or s == "None":
        return default
    return int(s)


# ---------------------------------------------------------------------------
# interval algebra on half open integer second intervals
# ---------------------------------------------------------------------------
def norm_intervals(spans):
    out = []
    for a, b in sorted(spans):
        if b < a:
            continue
        if out and a <= out[-1][1]:
            if b > out[-1][1]:
                out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return [(a, b) for a, b in out if b > a]


def subtract(base, cuts):
    cur = list(base)
    for ca, cb in cuts:
        if cb <= ca:
            continue
        nxt = []
        for a, b in cur:
            if cb <= a or ca >= b:
                nxt.append((a, b))
                continue
            if a < ca:
                nxt.append((a, ca))
            if cb < b:
                nxt.append((cb, b))
        cur = nxt
    return [(a, b) for a, b in cur if b > a]


def intersect(one, two):
    out = []
    i = j = 0
    while i < len(one) and j < len(two):
        a = max(one[i][0], two[j][0])
        b = min(one[i][1], two[j][1])
        if b > a:
            out.append((a, b))
        if one[i][1] < two[j][1]:
            i += 1
        else:
            j += 1
    return out


def span_seconds(spans):
    return sum(b - a for a, b in spans)


def spans_touch(one, two):
    return span_seconds(intersect(one, two)) > 0


def contains_instant(spans, t):
    for a, b in spans:
        if a <= t < b:
            return True
    return False


# ---------------------------------------------------------------------------
# corpus loading
# ---------------------------------------------------------------------------
def load_corpus(data_dir):
    d = Path(data_dir)
    c = {}
    c["missions"] = read_delim(d / "mission_register.csv", ",")
    c["alias"] = read_delim(d / "mission_alias_crosswalk.csv", ",")
    c["stations"] = read_delim(d / "ground_segment_register.tsv", chr(9))
    c["antennas"] = read_delim(d / "aperture_register.csv", ",")
    c["windows"] = read_delim(d / "aperture_service_windows.csv", ",")
    c["rates"] = read_delim(d / "rate_schedule_effective.psv", "|")
    c["flat_rates"] = read_delim(d / "legacy_flat_rate_table.csv", ",")
    c["contacts"] = read_delim(d / "pass_plan_of_record.csv", ",")
    c["events"] = read_ndjson(d / "contact_event_journal.ndjson")
    c["maintenance"] = read_delim(d / "maintenance_dockets.csv", ",")
    c["blackouts"] = read_delim(d / "blackout_advisories.psv", "|")
    c["terms"] = read_delim(d / "contract_terms_amendments.tsv", chr(9))
    c["overrides"] = read_ndjson(d / "precedence_override_register.jsonl")
    c["backlog"] = read_delim(d / "onboard_backlog_reports.csv", ",")
    c["delivery"] = read_delim(d / "downlink_reports.csv", ",")
    c["prior"] = read_json(d / "prior_period_settlement.json")["opening_buckets"]
    c["cancel"] = read_delim(d / "cancellation_notices.csv", ",")
    c["calendar"] = read_delim(d / "station_accounting_calendar.csv", ",")
    c["outages"] = read_delim(d / "outage_claims.psv", "|")
    c["roster"] = read_delim(d / "operator_roster.tsv", chr(9))
    c["phases"] = read_xml_records(d / "campaign_schedule.xml", "phase")
    c["units"] = read_json(d / "unit_scaling_rules.json")
    c["sheet_rule"] = read_json(d / "workbook_sheet_selection.json")
    c["precision"] = read_flat_yaml(d / "rounding_and_precision.yml")
    c["ordering"] = read_flat_yaml(d / "ordering_dependencies.yaml")
    c["accounting"] = read_ini(d / "station_local_accounting.ini")
    c["workbook"] = read_xlsx_sheets(d / "aperture_contract_workbook.xlsx")
    c["memo"] = read_pdf_lines(d / "network_operations_memo.pdf")
    c["directive"] = read_docx_blocks(d / "precedence_directive.docx")
    c["scope_rows"] = read_sqlite_table(d / "reference_lookups.sqlite", "station_scope")
    c["rank_rows"] = read_sqlite_table(d / "reference_lookups.sqlite", "priority_rank")
    c["grade_rows"] = read_sqlite_table(d / "reference_lookups.sqlite", "grade_authority")
    c["carry_state"] = read_sqlite_table(d / "settlement_audit_trace.db", "carry_state")
    c["codes"] = read_xml_records(d / "exception_code_dictionary.xml", "code")
    return c


def code_book(corpus):
    """The reject reason and the exception report class are the slugs the code
    dictionary declares, so an undeclared code has no place to come from."""
    reason = {}
    report = {}
    for r in corpus["codes"]:
        reason[r["id"]] = r.get("reason_slug", "")
        report[r["id"]] = r.get("report_class", "")
    return reason, report


def memo_scalars(corpus):
    """The commit lead per station, the outage qualifying floor and the pass
    budget shape are published only in the operations memo."""
    out = {"commit_lead": {}, "qualify_min_s": None,
           "pass_budget_base": None, "pass_budget_ceiling": None}
    for line in corpus["memo"]:
        parts = [p.strip() for p in line.split(":", 1)]
        if len(parts) != 2:
            continue
        key, val = parts[0], parts[1]
        if key.startswith("commit-lead "):
            out["commit_lead"][key.split(" ", 1)[1].strip()] = int(val.split()[0])
        elif key == "outage-qualifying-floor-seconds":
            out["qualify_min_s"] = int(val.split()[0])
        elif key == "ration-pass-budget-base":
            out["pass_budget_base"] = int(val.split()[0])
        elif key == "ration-pass-budget-ceiling":
            out["pass_budget_ceiling"] = int(val.split()[0])
    return out


def live_sheet(corpus):
    """The workbook ships one sheet per revision. The selection rule names the
    status that is binding and the tie break between equal revisions."""
    rule = corpus["sheet_rule"]
    binding = rule["binding_status"]
    best = None
    for name, rows in corpus["workbook"].items():
        if not rows:
            continue
        head = {}
        for r in rows:
            if len(r) >= 2 and str(r[0]).strip() in ("sheet_status", "sheet_revision"):
                head[str(r[0]).strip()] = str(r[1]).strip()
        if head.get("sheet_status") != binding:
            continue
        rev = int(head.get("sheet_revision", "0"))
        if best is None or rev > best[0]:
            best = (rev, name, rows)
    if best is None:
        raise ValueError("no binding workbook sheet")
    return best[1], best[2]


def workbook_numbers(corpus):
    name, rows = live_sheet(corpus)
    caps = {}
    budgets = {}
    rates = {}
    mode = ""
    header = []
    for r in rows:
        cell0 = str(r[0]).strip() if r else ""
        if cell0.startswith("#"):
            mode = cell0[1:].strip()
            header = []
            continue
        if not cell0 or cell0 in ("sheet_status", "sheet_revision", "sheet_name"):
            continue
        if not header and mode in ("aperture_period_terms", "credit_rates"):
            header = [str(x).strip() for x in r]
            continue
        row = dict(zip(header, [str(x).strip() for x in r]))
        if mode == "aperture_period_terms":
            key = (row["antenna_uid"], row["period_id"])
            caps[key] = int(row["per_contact_cap_kib"])
            budgets[key] = int(row["period_budget_kib"])
        elif mode == "credit_rates":
            rates[row["rate_key"]] = int(row["rate_value"])
    return name, caps, budgets, rates


# ---------------------------------------------------------------------------
# stage 1: canonical identity and the effective dated crosswalk
# ---------------------------------------------------------------------------
def stage_identity(corpus):
    st = {}
    st["station_tz"] = {}
    for r in corpus["stations"]:
        if r["element_class"] == "accounting_site":
            st["station_tz"][r["station_id"]] = int(r["tz_offset_min"])
    st["stations"] = sorted(st["station_tz"])
    st["mission_class"] = {}
    for r in corpus["missions"]:
        if r["register_state"] == "current":
            st["mission_class"][r["mission_id"]] = r["priority_class"]
    st["missions"] = sorted(st["mission_class"])
    st["rank"] = {r["priority_class"]: int(r["rank_value"])
                  for r in corpus["rank_rows"]}
    st["authority"] = {r["operator_code"]: r["authority_grade"]
                       for r in corpus["roster"]}
    st["commit_grades"] = {r["authority_grade"] for r in corpus["grade_rows"]
                           if int(r["commit_evidence"]) == 1}
    ant = {}
    by_label = {}
    for r in corpus["antennas"]:
        if r["config_state"] != "current":
            continue
        ant[r["antenna_uid"]] = r
        by_label[(r["station_id"], r["local_label"])] = r["antenna_uid"]
    st["antennas"] = ant
    st["antenna_by_label"] = by_label
    st["antenna_ids"] = sorted(ant)

    alias = {}
    for r in corpus["alias"]:
        alias.setdefault(r["presentation_id"], []).append(
            (int(r["valid_from_s"]), int(r["valid_to_s"]), r["mission_id"]))
    for k in alias:
        alias[k].sort()
    st["alias"] = alias
    return st


def resolve_mission(st, presentation_id, t):
    for a, b, mid in st["alias"].get(presentation_id, []):
        if a <= t < b:
            return mid
    return None


# ---------------------------------------------------------------------------
# stage 2: availability, declared windows less maintenance and blackouts
# ---------------------------------------------------------------------------
def stage_availability(corpus, st):
    declared = {}
    for r in corpus["windows"]:
        if r["service_state"] != "in_service":
            continue
        declared.setdefault(r["antenna_uid"], []).append(
            (int(r["effective_from_s"]), int(r["effective_to_s"])))
    md = {}
    for r in corpus["maintenance"]:
        md.setdefault(r["antenna_uid"], []).append((int(r["start_s"]), int(r["end_s"])))
    bl = {}
    for r in corpus["blackouts"]:
        bl.setdefault(r["station_id"], []).append((int(r["start_s"]), int(r["end_s"])))
    avail = {}
    for uid in st["antenna_ids"]:
        base = norm_intervals(declared.get(uid, []))
        cuts = norm_intervals(md.get(uid, []))
        station = st["antennas"][uid]["station_id"]
        cuts = norm_intervals(cuts + bl.get(station, []))
        avail[uid] = subtract(base, cuts)
    return avail


def period_windows(corpus, st):
    """The station local accounting period, expressed in UTC seconds."""
    out = {}
    for r in corpus["calendar"]:
        key = (r["station_id"], r["period_id"])
        a = int(r["local_open_s"])
        b = int(r["local_close_s"])
        if key in out:
            a = min(a, out[key][0])
            b = max(b, out[key][1])
        out[key] = (a, b)
    return out


# ---------------------------------------------------------------------------
# stage 3 and 4: admission and clipping, in the published predicate order
# ---------------------------------------------------------------------------
def settled_terms(corpus, rules=None):
    best = {}
    for r in corpus["terms"]:
        if _on(rules, "terms_last_row"):
            best[(r["contract_id"], r["period_id"])] = r
            continue
        if r["amendment_status"] != "executed":
            continue
        key = (r["contract_id"], r["period_id"])
        seq = int(r["revision_seq"])
        if key not in best or seq > int(best[key]["revision_seq"]):
            best[key] = r
    return best


def contract_index(corpus, terms):
    out = {}
    for (cid, pid), row in terms.items():
        out.setdefault(cid, {})["mission_id"] = None
    for r in corpus["carry_state"]:
        out.setdefault(r["contract_id"], {})
        out[r["contract_id"]]["mission_id"] = r["mission_id"]
        out[r["contract_id"]]["valid_from_s"] = int(r["valid_from_s"])
        out[r["contract_id"]]["valid_to_s"] = int(r["valid_to_s"])
        out[r["contract_id"]]["carry_forward_enabled"] = int(r["carry_forward_enabled"])
    return out


def phase_index(corpus):
    out = {}
    for r in corpus["phases"]:
        out.setdefault(r["mission_id"], []).append(
            (int(r["phase_from_s"]), int(r["phase_to_s"]), r["phase_class"]))
    for k in out:
        out[k].sort()
    return out


def cancel_index(corpus):
    out = {}
    for r in corpus["cancel"]:
        out.setdefault(r["contact_id"], []).append(r)
    for k in out:
        out[k].sort(key=lambda r: int(r["issued_seq"]))
    return out


def effective_cancellation(rows):
    live = [r for r in rows if r["notice_state"] == "effective"]
    if not live:
        return None
    return live[-1]


def backlog_opening(corpus):
    out = {}
    for r in corpus["backlog"]:
        if r["report_state"] != "current":
            continue
        key = (r["mission_id"], r["period_id"])
        seq = int(r["report_seq"])
        if key not in out or seq > out[key][0]:
            out[key] = (seq, int(r["backlog_kib"]))
    return {k: v[1] for k, v in out.items()}


def rate_pieces(corpus):
    out = {}
    for r in corpus["rates"]:
        out.setdefault(r["antenna_uid"], []).append(
            (int(r["effective_from_s"]), int(r["effective_to_s"]),
             int(r["rate_mkib_per_s"])))
    for k in out:
        out[k].sort()
    return out


def split_by_edges(spans, edges):
    out = []
    for a, b in spans:
        cuts = sorted({a, b} | {e for e in edges if a < e < b})
        for i in range(len(cuts) - 1):
            if cuts[i + 1] > cuts[i]:
                out.append((cuts[i], cuts[i + 1]))
    return out


def stage_admit_and_clip(corpus, st, avail, pwin, terms, cidx, memo, rules=None):
    reason_of, _report_of = code_book(corpus)
    phases = phase_index(corpus)
    cancels = cancel_index(corpus)
    events = {r["contact_id"]: r for r in corpus["events"]}
    scope = {}
    for r in corpus["scope_rows"]:
        scope.setdefault(r["contract_id"], set()).add(r["station_id"])

    admitted = []
    rejected = []
    normalized = []
    for c in sorted(corpus["contacts"], key=lambda r: r["contact_id"]):
        cid = c["contact_id"]
        s0 = int(c["scheduled_start_s"])
        e0 = int(c["scheduled_end_s"])
        station = c["station_id"]
        code = None
        mission = resolve_mission(st, c["presentation_id"], s0)
        if mission is None:
            code = "E01"
        uid = st["antenna_by_label"].get((station, c["aperture_label"]))
        if code is None and uid is None:
            code = "E02"
        contracts = []
        if code is None:
            for con_id in sorted(cidx):
                meta = cidx[con_id]
                if meta.get("mission_id") != mission:
                    continue
                if not (meta["valid_from_s"] <= s0 < meta["valid_to_s"]):
                    continue
                if station not in scope.get(con_id, set()):
                    continue
                contracts.append(con_id)
            if not contracts:
                code = "E03"
        if code is None:
            cls = "routine"
            for a, b, k in phases.get(mission, []):
                if a <= s0 < b:
                    cls = k
                    break
            if cls == "standdown":
                code = "E04"
        lead = memo["commit_lead"][station]
        commit = s0 - lead
        late_cancel = 0
        if code is None:
            notice = effective_cancellation(cancels.get(cid, []))
            if notice is not None:
                eff = int(notice["effective_s"])
                bound = (eff <= commit if _on(rules, "cancel_boundary_rejects")
                         else eff < commit)
                if bound:
                    code = "E05"
                else:
                    late_cancel = 1
        ev = events.get(cid)
        if code is None and ev is None:
            code = "E06"
        if code is None and ev["event_status"] not in ADMISSIBLE_EVENTS:
            code = "E07"

        eligible = []
        if code is None:
            base = [(s0, e0)] if e0 > s0 else []
            if ev["event_status"] == "partial":
                base = intersect(base, [(int(ev["actual_start_s"]),
                                         int(ev["actual_end_s"]))])
            eligible = intersect(norm_intervals(base), avail[uid])
            if e0 == s0:
                if not contains_instant(avail[uid], s0):
                    code = "E08"
            elif span_seconds(eligible) == 0:
                code = "E08"

        if code is not None:
            rejected.append({
                "contact_id": cid, "station_id": station,
                "aperture_label": c["aperture_label"],
                "presentation_id": c["presentation_id"],
                "scheduled_start_s": s0, "scheduled_end_s": e0,
                "reject_code": code,
                "reject_reason": reason_of[code],
                "predicate_index": [k for k, _v in REJECT_CODES].index(code) + 1,
            })
            continue

        protected = 0
        if (int(ev["event_recorded_s"]) <= commit
                and st["authority"].get(ev["operator_code"]) in st["commit_grades"]):
            protected = 1

        for pid in PERIOD_IDS:
            pa, pb = pwin[(station, pid)]
            part = intersect(eligible, [(pa, pb)]) if e0 > s0 else []
            if e0 == s0:
                if not (pa <= s0 < pb):
                    continue
                part = []
            elif not part:
                continue
            admitted.append({
                "contact_id": cid, "period_id": pid, "station_id": station,
                "antenna_uid": uid, "aperture_label": c["aperture_label"],
                "mission_id": mission, "presentation_id": c["presentation_id"],
                "contract_candidates": contracts,
                "scheduled_start_s": s0, "scheduled_end_s": e0,
                "commit_boundary_s": commit, "protected": protected,
                "late_cancel": late_cancel,
                "event_status": ev["event_status"],
                "operator_code": ev["operator_code"],
                "eligible": part,
                "eligible_seconds": span_seconds(part),
            })
            for a, b in part:
                normalized.append({
                    "contact_id": cid, "period_id": pid, "antenna_uid": uid,
                    "segment_start_s": a, "segment_end_s": b,
                    "segment_seconds": b - a,
                })
            if not part:
                normalized.append({
                    "contact_id": cid, "period_id": pid, "antenna_uid": uid,
                    "segment_start_s": s0, "segment_end_s": s0,
                    "segment_seconds": 0,
                })
    admitted.sort(key=lambda r: (r["contact_id"], r["period_id"]))
    rejected.sort(key=lambda r: r["contact_id"])
    normalized.sort(key=lambda r: (r["contact_id"], r["period_id"],
                                   r["segment_start_s"]))
    return admitted, rejected, normalized


# ---------------------------------------------------------------------------
# stage 5: capacity, floored per rate piece and then capped per pass
# ---------------------------------------------------------------------------
def stage_capacity(corpus, rows, caps, scale, rules=None):
    rates = rate_pieces(corpus)
    if _on(rules, "legacy_flat_rate"):
        rates = {}
        seen = {}
        for fr in corpus["flat_rates"]:
            uid = fr["antenna_uid"]
            rev = int(fr["table_rev"])
            if uid not in seen or rev > seen[uid]:
                seen[uid] = rev
                rates[uid] = [(0, 1 << 62, int(fr["flat_rate_mkib_per_s"]))]
    cap_exceptions = []
    ledger = []
    for r in rows:
        uid = r["antenna_uid"]
        table = rates.get(uid, [])
        edges = set()
        for a, b, _v in table:
            edges.add(a)
            edges.add(b)
        pieces = split_by_edges(r["eligible"], edges)
        raw = 0
        detail = []
        product = 0
        for a, b in pieces:
            rate = 0
            for ra, rb, rv in table:
                if ra <= a < rb:
                    rate = rv
                    break
            part = ((b - a) * rate) // scale
            raw += part
            product += (b - a) * rate
            detail.append((a, b, rate, part))
        if _on(rules, "aggregate_then_floor"):
            raw = product // scale
        cap = caps[(uid, r["period_id"])]
        usable = raw if raw < cap else cap
        if _on(rules, "cap_after_aggregation"):
            usable = raw
        r["raw_capacity_kib"] = raw
        r["capacity_cap_kib"] = cap
        r["usable_capacity_kib"] = usable
        r["rate_pieces"] = detail
        if raw > cap:
            cap_exceptions.append({
                "contact_id": r["contact_id"], "period_id": r["period_id"],
                "antenna_uid": uid, "raw_capacity_kib": raw,
                "capacity_cap_kib": cap, "clipped_kib": raw - cap,
            })
        ledger.append({
            "contact_id": r["contact_id"], "period_id": r["period_id"],
            "antenna_uid": uid, "eligible_seconds": r["eligible_seconds"],
            "rate_piece_count": len(detail), "raw_capacity_kib": raw,
            "capacity_cap_kib": cap, "usable_capacity_kib": usable,
        })
    ledger.sort(key=lambda r: (r["contact_id"], r["period_id"]))
    cap_exceptions.sort(key=lambda r: (r["contact_id"], r["period_id"]))
    return ledger, cap_exceptions


# ---------------------------------------------------------------------------
# stage 6: effective precedence, overrides and the commit boundary
# ---------------------------------------------------------------------------
def stage_precedence(corpus, st, rows, rules=None):
    ov = {}
    for r in corpus["overrides"]:
        ov.setdefault((r["mission_id"], r["antenna_uid"]), []).append(r)
    for k in ov:
        ov[k].sort(key=lambda r: r["override_id"])
    out = []
    for r in rows:
        base = st["mission_class"][r["mission_id"]]
        chosen = None
        for cand in ov.get((r["mission_id"], r["antenna_uid"]), []):
            if not (int(cand["valid_from_s"]) <= r["scheduled_start_s"]
                    < int(cand["valid_to_s"])):
                continue
            if chosen is None or st["rank"][cand["granted_class"]] < st["rank"][chosen["granted_class"]]:
                chosen = cand
        cls = chosen["granted_class"] if chosen is not None else base
        if st["rank"][cls] > st["rank"][base]:
            cls = base
        r["base_class"] = base
        r["effective_class"] = cls
        r["effective_rank"] = st["rank"][cls]
        r["override_id"] = chosen["override_id"] if chosen is not None else ""
        out.append({
            "contact_id": r["contact_id"], "period_id": r["period_id"],
            "mission_id": r["mission_id"], "antenna_uid": r["antenna_uid"],
            "base_class": base, "effective_class": cls,
            "effective_rank": r["effective_rank"],
            "override_id": r["override_id"],
            "commit_boundary_s": r["commit_boundary_s"],
            "protected": r["protected"],
        })
    out.sort(key=lambda r: (r["contact_id"], r["period_id"]))
    return out


def obligation_of(terms, cidx, row, pid):
    best = 0
    for con_id in row["contract_candidates"]:
        t = terms.get((con_id, pid))
        if t is None:
            continue
        v = int(t["obligation_kib"])
        if v > best:
            best = v
    return best


def order_key(r, rules=None):
    if _on(rules, "protection_as_tiebreak"):
        return (r["effective_rank"], 0 if r["protected"] else 1,
                r["commit_boundary_s"], -r["remaining_obligation_kib"],
                r["contact_id"])
    return (0 if r["protected"] else 1, r["effective_rank"],
            r["commit_boundary_s"], -r["remaining_obligation_kib"],
            r["contact_id"])


# ---------------------------------------------------------------------------
# stage 7: contention resolution, greedy in the published order
# ---------------------------------------------------------------------------
def stage_contention(rows, terms, cidx, rules=None):
    for r in rows:
        r["remaining_obligation_kib"] = obligation_of(terms, cidx, r, r["period_id"])

    groups = {}
    for r in rows:
        groups.setdefault((r["antenna_uid"], r["period_id"]), []).append(r)

    group_report = []
    winners = []
    displaced = []
    ties = []
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda r: order_key(r, rules))
        comps = _components(members)
        for gi, comp in enumerate(comps, start=1):
            group_report.append({
                "antenna_uid": key[0], "period_id": key[1],
                "group_seq": gi, "member_count": len(comp),
                "member_ids": ",".join(sorted(m["contact_id"] for m in comp)),
                "eligible_seconds_total": sum(m["eligible_seconds"] for m in comp),
            })
        taken = []
        for r in members:
            hit = None
            for w in taken:
                if spans_touch(r["eligible"], w["eligible"]):
                    hit = w
                    break
            if hit is None:
                taken.append(r)
                r["allocation_state"] = "won"
                winners.append(r)
            else:
                r["allocation_state"] = "displaced"
                r["displaced_by"] = hit["contact_id"]
                displaced.append({
                    "contact_id": r["contact_id"], "period_id": r["period_id"],
                    "antenna_uid": r["antenna_uid"], "mission_id": r["mission_id"],
                    "displaced_by": hit["contact_id"],
                    "displaced_seconds": r["eligible_seconds"],
                    "usable_capacity_kib": r["usable_capacity_kib"],
                })
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                x, y = members[a], members[b]
                if not spans_touch(x["eligible"], y["eligible"]):
                    continue
                lvl = _tie_level(x, y)
                if lvl == 0:
                    continue
                ties.append({
                    "antenna_uid": key[0], "period_id": key[1],
                    "contact_id_kept": x["contact_id"],
                    "contact_id_yielded": y["contact_id"],
                    "decided_at_level": lvl,
                })
    winners.sort(key=lambda r: (r["contact_id"], r["period_id"]))
    displaced.sort(key=lambda r: (r["contact_id"], r["period_id"]))
    group_report.sort(key=lambda r: (r["antenna_uid"], r["period_id"], r["group_seq"]))
    ties.sort(key=lambda r: (r["antenna_uid"], r["period_id"],
                             r["contact_id_kept"], r["contact_id_yielded"]))
    return winners, displaced, group_report, ties


def _components(members):
    n = len(members)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a in range(n):
        for b in range(a + 1, n):
            if spans_touch(members[a]["eligible"], members[b]["eligible"]):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[ra] = rb
    buckets = {}
    for i in range(n):
        buckets.setdefault(find(i), []).append(members[i])
    return [buckets[k] for k in sorted(buckets,
                                       key=lambda k: min(m["contact_id"] for m in buckets[k]))]


def _tie_level(x, y):
    if (0 if x["protected"] else 1) != (0 if y["protected"] else 1):
        return 1
    if x["effective_rank"] != y["effective_rank"]:
        return 2
    if x["commit_boundary_s"] != y["commit_boundary_s"]:
        return 3
    if x["remaining_obligation_kib"] != y["remaining_obligation_kib"]:
        return 4
    return 5


# ---------------------------------------------------------------------------
# stage 8: entitlement, prior carry and the expiry forfeit
# ---------------------------------------------------------------------------
def stage_entitlement(corpus, terms, cidx, pwin):
    opening = {}
    for r in corpus["prior"]:
        if r["bucket_state"] != "open":
            continue
        key = r["contract_id"]
        opening[key] = opening.get(key, 0) + int(r["unsettled_kib"])
    state = {}
    for cid in sorted(cidx):
        state[cid] = {"carry_in_source_kib": opening.get(cid, 0)}
    return state


def entitlement_for(terms, cidx, state, cid, pid, carry_source, period_start):
    t = terms.get((cid, pid))
    if t is None:
        return None
    meta = cidx[cid]
    enabled = int(t["carry_forward_enabled"]) and meta["carry_forward_enabled"]
    cap = int(t["carry_cap_kib"])
    expired = meta["valid_to_s"] <= period_start
    forfeit = 0
    if not enabled:
        carry_in = 0
        forfeit = carry_source
    elif expired:
        carry_in = 0
        forfeit = carry_source
    else:
        carry_in = carry_source if carry_source < cap else cap
        forfeit = carry_source - carry_in
    return {
        "contract_id": cid, "period_id": pid,
        "carry_source_kib": carry_source, "carry_cap_kib": cap,
        "carry_in_kib": carry_in, "carry_forfeit_kib": forfeit,
        "entitlement_kib": int(t["entitlement_kib"]),
        "obligation_kib": int(t["obligation_kib"]),
        "reserved_kib": int(t["reserved_kib"]),
        "available_allowance_kib": carry_in + int(t["entitlement_kib"]),
        "contract_expired": 1 if expired else 0,
        "carry_forward_enabled": 1 if enabled else 0,
    }


# ---------------------------------------------------------------------------
# stage 9: demand, then the damped ration against the aperture period budget
# ---------------------------------------------------------------------------
def ration(demands, budget, theta_num, theta_den, base, ceiling, rules=None):
    n = len(demands)
    if n == 0:
        return [], []
    total = sum(demands)
    if total <= budget:
        return list(demands), []
    passes = base + n
    if passes > ceiling:
        passes = ceiling
    if _on(rules, "ration_to_convergence"):
        passes = 400
    x = [0] * n
    pinned = [False] * n
    trace = []
    for p in range(1, passes + 1):
        pinned_mass = sum(demands[i] for i in range(n) if pinned[i])
        active = [i for i in range(n) if not pinned[i]]
        if not active:
            trace.append({"pass_seq": p, "active_count": 0, "share_kib": 0,
                          "allocated_kib": sum(x)})
            continue
        room = budget - pinned_mass
        share = room // len(active) if room > 0 else 0
        moved = 0
        for i in active:
            target = demands[i] if demands[i] < share else share
            step = target - x[i]
            delta = (step * theta_num) // theta_den
            if step > 0 and delta < 1 and not _on(rules, "no_minimum_step"):
                delta = 1
            if delta < 0:
                delta = 0
            x[i] = x[i] + delta
            moved += delta
        for i in active:
            if x[i] >= demands[i]:
                x[i] = demands[i]
                pinned[i] = True
        if _on(rules, "ration_to_convergence") and moved == 0:
            trace.append({"pass_seq": p, "active_count": len(active),
                          "share_kib": share, "allocated_kib": sum(x)})
            break
        trace.append({"pass_seq": p, "active_count": len(active),
                      "share_kib": share, "allocated_kib": sum(x)})
    residual = budget - sum(x)
    for i in range(n):
        if residual <= 0:
            break
        room = demands[i] - x[i]
        if room <= 0:
            continue
        take = room if room < residual else residual
        x[i] += take
        residual -= take
    return x, trace


def stage_ration(winners, opening_backlog, budgets, memo, theta_num, theta_den,
                 rules=None):
    running = dict(opening_backlog)
    ordered = sorted(winners, key=lambda r: (PERIOD_IDS.index(r["period_id"]),
                                             r["station_id"], r["antenna_uid"],
                                             order_key(r, rules)))
    for r in ordered:
        key = (r["mission_id"], r["period_id"])
        if _on(rules, "running_backlog_demand"):
            avail = running.get(key, 0)
        else:
            avail = opening_backlog.get(key, 0)
        if avail < 0:
            avail = 0
        cap = r["usable_capacity_kib"]
        r["demand_kib"] = cap if cap < avail else avail
        if _on(rules, "running_backlog_demand"):
            running[key] = avail - r["demand_kib"]
    groups = {}
    for r in winners:
        groups.setdefault((r["antenna_uid"], r["period_id"]), []).append(r)
    traces = []
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda r: order_key(r, rules))
        budget = budgets[key]
        alloc, trace = ration([m["demand_kib"] for m in members], budget,
                              theta_num, theta_den,
                              memo["pass_budget_base"],
                              memo["pass_budget_ceiling"], rules)
        for m, v in zip(members, alloc):
            m["allocated_kib"] = v
        for t in trace:
            traces.append({
                "antenna_uid": key[0], "period_id": key[1],
                "pass_seq": t["pass_seq"], "active_count": t["active_count"],
                "share_kib": t["share_kib"], "allocated_kib": t["allocated_kib"],
                "budget_kib": budget,
                "demand_total_kib": sum(m["demand_kib"] for m in members),
            })
    traces.sort(key=lambda r: (r["antenna_uid"], r["period_id"], r["pass_seq"]))
    return traces


# ---------------------------------------------------------------------------
# stage 10: transmission accounting against backlog and allowance
# ---------------------------------------------------------------------------
def pick_contract(row, terms, pid):
    best = None
    for cid in row["contract_candidates"]:
        t = terms.get((cid, pid))
        if t is None:
            continue
        ob = int(t["obligation_kib"])
        if best is None or ob > best[0] or (ob == best[0] and cid < best[1]):
            best = (ob, cid)
    return best[1] if best is not None else ""


def resolution_order(winners, rules=None):
    return sorted(winners, key=lambda r: (PERIOD_IDS.index(r["period_id"]),
                                          r["station_id"], r["antenna_uid"],
                                          order_key(r, rules)))


def stage_accounting(winners, terms, cidx, state, opening_backlog, pwin, corpus,
                     rules=None):
    backlog_left = dict(opening_backlog)
    ent_rows = []
    carry_rows = []
    ledger = []
    deferred_rows = []
    unused_rows = []
    ent_state = {}
    carry_source = {cid: state[cid]["carry_in_source_kib"] for cid in state}

    for pid in PERIOD_IDS:
        pstart = min(pwin[(s, pid)][0] for s in sorted({k[0] for k in pwin}))
        for cid in sorted(cidx):
            e = entitlement_for(terms, cidx, state, cid, pid,
                                carry_source.get(cid, 0), pstart)
            if e is None:
                continue
            e["carry_remaining_kib"] = e["carry_in_kib"]
            e["new_remaining_kib"] = e["entitlement_kib"]
            ent_state[(cid, pid)] = e

        for r in resolution_order([w for w in winners if w["period_id"] == pid], rules):
            con = pick_contract(r, terms, pid)
            r["contract_id"] = con
            e = ent_state.get((con, pid))
            allowance = (e["carry_remaining_kib"] + e["new_remaining_kib"]) if e else 0
            key = (r["mission_id"], pid)
            left = backlog_left.get(key, 0)
            alloc = r["allocated_kib"]
            accepted = alloc
            if accepted > left:
                accepted = left
            if accepted > allowance:
                accepted = allowance
            if not e:
                from_carry = 0
            elif _on(rules, "entitlement_before_carry"):
                take_new = (accepted if accepted < e["new_remaining_kib"]
                            else e["new_remaining_kib"])
                from_carry = accepted - take_new
            elif accepted < e["carry_remaining_kib"]:
                from_carry = accepted
            else:
                from_carry = e["carry_remaining_kib"]
            from_new = accepted - from_carry
            if e:
                e["carry_remaining_kib"] -= from_carry
                e["new_remaining_kib"] -= from_new
            backlog_left[key] = left - accepted
            r["accepted_kib"] = accepted
            r["from_carry_kib"] = from_carry
            r["from_new_kib"] = from_new
            r["deferred_kib"] = r["demand_kib"] - accepted
            r["unused_capacity_kib"] = r["usable_capacity_kib"] - accepted
            ledger.append({
                "contact_id": r["contact_id"], "period_id": pid,
                "mission_id": r["mission_id"], "contract_id": con,
                "antenna_uid": r["antenna_uid"],
                "demand_kib": r["demand_kib"], "allocated_kib": alloc,
                "accepted_kib": accepted, "from_carry_kib": from_carry,
                "from_new_kib": from_new,
            })
            deferred_rows.append({
                "contact_id": r["contact_id"], "period_id": pid,
                "mission_id": r["mission_id"],
                "demand_kib": r["demand_kib"], "accepted_kib": accepted,
                "deferred_kib": r["deferred_kib"],
                "late_cancel": r["late_cancel"],
            })
            unused_rows.append({
                "contact_id": r["contact_id"], "period_id": pid,
                "antenna_uid": r["antenna_uid"],
                "usable_capacity_kib": r["usable_capacity_kib"],
                "accepted_kib": accepted,
                "unused_capacity_kib": r["unused_capacity_kib"],
            })

        for cid in sorted(cidx):
            e = ent_state.get((cid, pid))
            if e is None:
                carry_source[cid] = 0
                continue
            consumed = e["available_allowance_kib"] - (e["carry_remaining_kib"]
                                                       + e["new_remaining_kib"])
            e["consumed_kib"] = consumed
            e["unconsumed_kib"] = e["carry_remaining_kib"] + e["new_remaining_kib"]
            carry_source[cid] = e["unconsumed_kib"]
            ent_rows.append({
                "contract_id": cid, "period_id": pid,
                "carry_source_kib": e["carry_source_kib"],
                "carry_cap_kib": e["carry_cap_kib"],
                "carry_in_kib": e["carry_in_kib"],
                "carry_forfeit_kib": e["carry_forfeit_kib"],
                "entitlement_kib": e["entitlement_kib"],
                "available_allowance_kib": e["available_allowance_kib"],
                "consumed_kib": consumed,
                "unconsumed_kib": e["unconsumed_kib"],
                "contract_expired": e["contract_expired"],
            })
            carry_rows.append({
                "contract_id": cid, "period_id": pid,
                "carry_in_kib": e["carry_in_kib"],
                "carry_forfeit_kib": e["carry_forfeit_kib"],
                "carry_out_kib": e["unconsumed_kib"],
                "carry_forward_enabled": e["carry_forward_enabled"],
            })

    ledger.sort(key=lambda r: (r["contact_id"], r["period_id"]))
    deferred_rows.sort(key=lambda r: (r["contact_id"], r["period_id"]))
    unused_rows.sort(key=lambda r: (r["contact_id"], r["period_id"]))
    ent_rows.sort(key=lambda r: (r["contract_id"], r["period_id"]))
    carry_rows.sort(key=lambda r: (r["contract_id"], r["period_id"]))
    return ledger, deferred_rows, unused_rows, ent_rows, carry_rows, ent_state


# ---------------------------------------------------------------------------
# stage 11: utilisation, read off the resolved ledger and nothing else
# ---------------------------------------------------------------------------
def stage_utilisation(st, avail, pwin, winners, admitted=None, rules=None):
    per_ant = {}
    per_st = {}
    for uid in st["antenna_ids"]:
        station = st["antennas"][uid]["station_id"]
        for pid in PERIOD_IDS:
            pa, pb = pwin[(station, pid)]
            den = span_seconds(intersect(avail[uid], [(pa, pb)]))
            per_ant[(uid, pid)] = [0, den]
            key = (station, pid)
            if key not in per_st:
                per_st[key] = [0, 0]
            per_st[key][1] += den
    basis = winners
    if _on(rules, "utilisation_from_admitted") and admitted is not None:
        basis = admitted
    for r in basis:
        per_ant[(r["antenna_uid"], r["period_id"])][0] += r["eligible_seconds"]
        per_st[(r["station_id"], r["period_id"])][0] += r["eligible_seconds"]
    if _on(rules, "utilisation_denominator_paid"):
        paid_ant = {}
        paid_st = {}
        for r in winners:
            ka = (r["antenna_uid"], r["period_id"])
            ks = (r["station_id"], r["period_id"])
            paid_ant[ka] = paid_ant.get(ka, 0) + r["eligible_seconds"]
            paid_st[ks] = paid_st.get(ks, 0) + r["eligible_seconds"]
        for key in per_ant:
            per_ant[key][1] = paid_ant.get(key, 0)
        for key in per_st:
            per_st[key][1] = paid_st.get(key, 0)
    ant_rows = []
    for key in sorted(per_ant):
        num, den = per_ant[key]
        ant_rows.append({
            "antenna_uid": key[0], "period_id": key[1],
            "occupied_seconds": num, "available_seconds": den,
            "utilisation_bp": (num * 10000) // den if den > 0 else 0,
            "denominator_state": "empty" if den == 0 else "populated",
        })
    st_rows = []
    for key in sorted(per_st):
        num, den = per_st[key]
        st_rows.append({
            "station_id": key[0], "period_id": key[1],
            "occupied_seconds": num, "available_seconds": den,
            "utilisation_bp": (num * 10000) // den if den > 0 else 0,
            "denominator_state": "empty" if den == 0 else "populated",
        })
    return ant_rows, st_rows


# ---------------------------------------------------------------------------
# stage 13: credits, debits and the outage exemption that outranks a shortfall
# ---------------------------------------------------------------------------
def stage_credits(corpus, cidx, terms, ent_state, winners, memo, rates,
                  rules=None):
    claims = {}
    for r in corpus["outages"]:
        if r["claim_status"] != "accepted":
            continue
        claims.setdefault((r["mission_id"], r["period_id"]), []).append(r)

    by_contract = {}
    for r in winners:
        by_contract.setdefault((r["contract_id"], r["period_id"]), []).append(r)

    credit_rows = []
    compliance_rows = []
    outage_rows = []
    for key in sorted(ent_state):
        cid, pid = key
        e = ent_state[key]
        rows = by_contract.get(key, [])
        delivered = sum(r["accepted_kib"] for r in rows)
        obligation = e["obligation_kib"]
        reserved = e["reserved_kib"]
        shortfall = obligation - delivered
        if shortfall < 0:
            shortfall = 0
        unused_reserved = reserved - delivered
        if unused_reserved < 0:
            unused_reserved = 0
        mission = cidx[cid]["mission_id"]
        qualified = 0
        overlap_total = 0
        exempt = 0
        touched = []
        for cl in sorted(claims.get((mission, pid), []), key=lambda r: r["claim_id"]):
            window = [(int(cl["claim_from_s"]), int(cl["claim_to_s"]))]
            hit = 0
            for r in rows:
                if r["antenna_uid"] != cl["antenna_uid"]:
                    continue
                hit += span_seconds(intersect(r["eligible"], window))
            if hit > 0:
                touched.append((cl, hit))
            overlap_total += hit
        if overlap_total >= memo["qualify_min_s"]:
            qualified = 1
            pool = 0
            for cl, _hit in touched:
                for r in rows:
                    if r["antenna_uid"] != cl["antenna_uid"]:
                        continue
                    if r["late_cancel"] and not _on(rules,
                                                    "late_cancel_in_exempt_pool"):
                        continue
                    pool += r["deferred_kib"]
            exempt = shortfall if shortfall < pool else pool
        if qualified and _on(rules, "shortfall_reduced_not_waived"):
            residual_short = shortfall - exempt
            shortfall_debit = (residual_short
                               * rates["shortfall_debit_mcr_per_mib"]) // rates["credit_basis"]
            outage_credit = (exempt * rates["outage_credit_mcr_per_mib"]) // rates["credit_basis"]
            restore_room = e["carry_forfeit_kib"]
            restore = ((exempt * rates["carry_restore_num"])
                       // rates["carry_restore_den"])
            carry_restore = restore if restore < restore_room else restore_room
        elif qualified:
            shortfall_debit = 0
            outage_credit = (exempt * rates["outage_credit_mcr_per_mib"]) // rates["credit_basis"]
            restore_room = e["carry_forfeit_kib"]
            restore = (exempt * rates["carry_restore_num"]) // rates["carry_restore_den"]
            carry_restore = restore if restore < restore_room else restore_room
        else:
            shortfall_debit = (shortfall * rates["shortfall_debit_mcr_per_mib"]) // rates["credit_basis"]
            outage_credit = 0
            carry_restore = 0
        unused_credit = (unused_reserved
                         * rates["unused_reserved_credit_mcr_per_mib"]) // rates["credit_basis"]
        net = unused_credit + outage_credit - shortfall_debit
        credit_rows.append({
            "contract_id": cid, "period_id": pid,
            "shortfall_kib": shortfall, "shortfall_debit_mcr": shortfall_debit,
            "unused_reserved_kib": unused_reserved,
            "unused_credit_mcr": unused_credit,
            "outage_credit_mcr": outage_credit,
            "carry_restore_kib": carry_restore,
            "net_mcr": net,
        })
        compliance_rows.append({
            "contract_id": cid, "period_id": pid, "mission_id": mission,
            "obligation_kib": obligation, "delivered_kib": delivered,
            "reserved_kib": reserved, "shortfall_kib": shortfall,
            "compliance_state": ("met" if shortfall == 0 else
                                 ("exempt" if qualified else "short")),
        })
        outage_rows.append({
            "contract_id": cid, "period_id": pid, "mission_id": mission,
            "claim_overlap_seconds": overlap_total,
            "qualifying_floor_seconds": memo["qualify_min_s"],
            "outage_qualified": qualified, "exempt_kib": exempt,
            "carry_restore_kib": carry_restore,
        })
    credit_rows.sort(key=lambda r: (r["contract_id"], r["period_id"]))
    compliance_rows.sort(key=lambda r: (r["contract_id"], r["period_id"]))
    outage_rows.sort(key=lambda r: (r["contract_id"], r["period_id"]))
    return credit_rows, compliance_rows, outage_rows

# ---------------------------------------------------------------------------
# stage 12 and stage 14: aggregation and the reconciliation artifacts
# ---------------------------------------------------------------------------
CORE_ARTIFACTS = [
    "canonical_contact_ledger.csv",
    "admitted_contact_ledger.csv",
    "rejected_contact_ledger.psv",
    "normalized_contact_intervals.tsv",
    "antenna_capacity_ledger.csv",
    "capacity_cap_exceptions.psv",
    "contention_groups.jsonl",
    "winning_resource_assignments.csv",
    "displaced_contact_ledger.psv",
    "mission_entitlement_state.csv",
    "carry_forward_ledger.csv",
    "rationing_pass_trace.jsonl",
    "delivered_volume_ledger.csv",
    "deferred_volume_ledger.csv",
    "unused_capacity_ledger.tsv",
    "station_utilisation_ledger.csv",
    "antenna_utilisation_ledger.tsv",
    "mission_settlement_statements.csv",
    "station_settlement_statements.csv",
    "contract_compliance_ledger.csv",
    "credit_debit_ledger.csv",
    "outage_adjustment_ledger.psv",
    "exception_classification_report.jsonl",
    "tie_resolution_report.csv",
    "cross_source_discrepancy_report.psv",
    "invariant_check_report.json",
    "period_reconciliation_totals.json",
    "network_settlement_summary.xml",
    "per_mission_final_summary.md",
]
ALL_ARTIFACTS = CORE_ARTIFACTS + ["stage_digest_manifest.json"]
PROGRAM_NAME = "settle.py"


def btable(columns, rows, delim):
    out = [delim.join(columns)]
    for r in rows:
        out.append(delim.join(str(r[c]) for c in columns))
    return (chr(10).join(out) + chr(10)).encode("utf-8")


def bjsonl(rows):
    if not rows:
        return b""
    body = [json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            for r in rows]
    return (chr(10).join(body) + chr(10)).encode("utf-8")


def bjson(obj):
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True)
            + chr(10)).encode("utf-8")


def btext(text):
    return text.encode("utf-8")


def run_settlement(data_dir, rules=None):
    corpus = load_corpus(data_dir)
    scale = int(corpus["units"]["rate_scale_divisor"])
    theta_num = int(corpus["units"]["ration_damping_numerator"])
    theta_den = int(corpus["units"]["ration_damping_denominator"])
    mib_kib = int(corpus["units"]["credit_basis_kib_per_mib"])
    memo = memo_scalars(corpus)
    _sheet, caps, budgets, rates = workbook_numbers(corpus)
    rates["carry_restore_num"] = rates["carry_restore_numerator"]
    rates["carry_restore_den"] = rates["carry_restore_denominator"]
    rates["credit_basis"] = mib_kib

    st = stage_identity(corpus)
    avail = stage_availability(corpus, st)
    pwin = period_windows(corpus, st)
    terms = settled_terms(corpus, rules)
    cidx = contract_index(corpus, terms)
    admitted, rejected, normalized = stage_admit_and_clip(
        corpus, st, avail, pwin, terms, cidx, memo, rules)
    cap_ledger, cap_exceptions = stage_capacity(corpus, admitted, caps, scale, rules)
    precedence = stage_precedence(corpus, st, admitted, rules)
    winners, displaced, groups, ties = stage_contention(admitted, terms, cidx, rules)
    state = stage_entitlement(corpus, terms, cidx, pwin)
    opening = backlog_opening(corpus)
    traces = stage_ration(winners, opening, budgets, memo, theta_num, theta_den,
                          rules)
    (delivered, deferred, unused, ent_rows, carry_rows,
     ent_state) = stage_accounting(winners, terms, cidx, state, opening, pwin,
                                   corpus, rules)
    ant_util, st_util = stage_utilisation(st, avail, pwin, winners, admitted, rules)
    credits, compliance, outages = stage_credits(
        corpus, cidx, terms, ent_state, winners, memo, rates, rules)

    art = {}
    canon = []
    for r in sorted(admitted, key=lambda r: (r["contact_id"], r["period_id"])):
        canon.append({
            "contact_id": r["contact_id"], "period_id": r["period_id"],
            "station_id": r["station_id"], "antenna_uid": r["antenna_uid"],
            "mission_id": r["mission_id"],
            "contract_id": r.get("contract_id", ""),
            "eligible_seconds": r["eligible_seconds"],
            "raw_capacity_kib": r["raw_capacity_kib"],
            "usable_capacity_kib": r["usable_capacity_kib"],
            "effective_class": r["effective_class"],
            "protected": r["protected"],
            "late_cancel": r["late_cancel"],
            "allocation_state": r["allocation_state"],
            "demand_kib": r.get("demand_kib", 0),
            "allocated_kib": r.get("allocated_kib", 0),
            "accepted_kib": r.get("accepted_kib", 0),
        })
    art["canonical_contact_ledger.csv"] = btable(
        ["contact_id", "period_id", "station_id", "antenna_uid", "mission_id",
         "contract_id", "eligible_seconds", "raw_capacity_kib",
         "usable_capacity_kib", "effective_class", "protected", "late_cancel",
         "allocation_state", "demand_kib", "allocated_kib", "accepted_kib"],
        canon, ",")

    art["admitted_contact_ledger.csv"] = btable(
        ["contact_id", "period_id", "station_id", "antenna_uid", "mission_id",
         "presentation_id", "scheduled_start_s", "scheduled_end_s",
         "commit_boundary_s", "event_status", "operator_code", "protected",
         "late_cancel", "eligible_seconds"],
        [{k: r[k] for k in
          ["contact_id", "period_id", "station_id", "antenna_uid", "mission_id",
           "presentation_id", "scheduled_start_s", "scheduled_end_s",
           "commit_boundary_s", "event_status", "operator_code", "protected",
           "late_cancel", "eligible_seconds"]}
         for r in sorted(admitted, key=lambda r: (r["contact_id"], r["period_id"]))],
        ",")

    art["rejected_contact_ledger.psv"] = btable(
        ["contact_id", "station_id", "aperture_label", "presentation_id",
         "scheduled_start_s", "scheduled_end_s", "predicate_index",
         "reject_code", "reject_reason"], rejected, "|")

    art["normalized_contact_intervals.tsv"] = btable(
        ["contact_id", "period_id", "antenna_uid", "segment_start_s",
         "segment_end_s", "segment_seconds"], normalized, chr(9))

    art["antenna_capacity_ledger.csv"] = btable(
        ["contact_id", "period_id", "antenna_uid", "eligible_seconds",
         "rate_piece_count", "raw_capacity_kib", "capacity_cap_kib",
         "usable_capacity_kib"], cap_ledger, ",")

    art["capacity_cap_exceptions.psv"] = btable(
        ["contact_id", "period_id", "antenna_uid", "raw_capacity_kib",
         "capacity_cap_kib", "clipped_kib"], cap_exceptions, "|")

    art["contention_groups.jsonl"] = bjsonl(groups)

    art["winning_resource_assignments.csv"] = btable(
        ["contact_id", "period_id", "antenna_uid", "mission_id",
         "effective_class", "effective_rank", "protected",
         "commit_boundary_s", "remaining_obligation_kib", "eligible_seconds",
         "usable_capacity_kib"],
        [{k: r[k] for k in
          ["contact_id", "period_id", "antenna_uid", "mission_id",
           "effective_class", "effective_rank", "protected", "commit_boundary_s",
           "remaining_obligation_kib", "eligible_seconds", "usable_capacity_kib"]}
         for r in sorted(winners, key=lambda r: (r["contact_id"], r["period_id"]))],
        ",")

    art["displaced_contact_ledger.psv"] = btable(
        ["contact_id", "period_id", "antenna_uid", "mission_id", "displaced_by",
         "displaced_seconds", "usable_capacity_kib"], displaced, "|")

    art["mission_entitlement_state.csv"] = btable(
        ["contract_id", "period_id", "carry_source_kib", "carry_cap_kib",
         "carry_in_kib", "carry_forfeit_kib", "entitlement_kib",
         "available_allowance_kib", "consumed_kib", "unconsumed_kib",
         "contract_expired"], ent_rows, ",")

    art["carry_forward_ledger.csv"] = btable(
        ["contract_id", "period_id", "carry_in_kib", "carry_forfeit_kib",
         "carry_out_kib", "carry_forward_enabled"], carry_rows, ",")

    art["rationing_pass_trace.jsonl"] = bjsonl(traces)

    art["delivered_volume_ledger.csv"] = btable(
        ["contact_id", "period_id", "mission_id", "contract_id", "antenna_uid",
         "demand_kib", "allocated_kib", "accepted_kib", "from_carry_kib",
         "from_new_kib"], delivered, ",")

    art["deferred_volume_ledger.csv"] = btable(
        ["contact_id", "period_id", "mission_id", "demand_kib", "accepted_kib",
         "deferred_kib", "late_cancel"], deferred, ",")

    art["unused_capacity_ledger.tsv"] = btable(
        ["contact_id", "period_id", "antenna_uid", "usable_capacity_kib",
         "accepted_kib", "unused_capacity_kib"], unused, chr(9))

    art["station_utilisation_ledger.csv"] = btable(
        ["station_id", "period_id", "occupied_seconds", "available_seconds",
         "utilisation_bp", "denominator_state"], st_util, ",")

    art["antenna_utilisation_ledger.tsv"] = btable(
        ["antenna_uid", "period_id", "occupied_seconds", "available_seconds",
         "utilisation_bp", "denominator_state"], ant_util, chr(9))

    # stage 12: the same canonical ledger aggregated four ways
    mission_rows = _by_mission(st, winners, credits, cidx)
    art["mission_settlement_statements.csv"] = btable(
        ["mission_id", "period_id", "won_pass_count", "eligible_seconds",
         "usable_capacity_kib", "accepted_kib", "deferred_kib",
         "unused_capacity_kib", "net_mcr"], mission_rows, ",")

    station_rows = _by_station(st, winners, cidx, st_util)
    art["station_settlement_statements.csv"] = btable(
        ["station_id", "period_id", "won_pass_count", "eligible_seconds",
         "accepted_kib", "unused_capacity_kib", "utilisation_bp"],
        station_rows, ",")

    art["contract_compliance_ledger.csv"] = btable(
        ["contract_id", "period_id", "mission_id", "obligation_kib",
         "delivered_kib", "reserved_kib", "shortfall_kib", "compliance_state"],
        compliance, ",")

    art["credit_debit_ledger.csv"] = btable(
        ["contract_id", "period_id", "shortfall_kib", "shortfall_debit_mcr",
         "unused_reserved_kib", "unused_credit_mcr", "outage_credit_mcr",
         "carry_restore_kib", "net_mcr"], credits, ",")

    art["outage_adjustment_ledger.psv"] = btable(
        ["contract_id", "period_id", "mission_id", "claim_overlap_seconds",
         "qualifying_floor_seconds", "outage_qualified", "exempt_kib",
         "carry_restore_kib"], outages, "|")

    art["exception_classification_report.jsonl"] = bjsonl(
        _exceptions(corpus, rejected, cap_exceptions, displaced, ent_rows,
                    ant_util, deferred))

    art["tie_resolution_report.csv"] = btable(
        ["antenna_uid", "period_id", "contact_id_kept", "contact_id_yielded",
         "decided_at_level"], ties, ",")

    art["cross_source_discrepancy_report.psv"] = btable(
        ["source_left", "source_right", "subject_id", "period_id",
         "left_value", "right_value", "delta_value", "discrepancy_class"],
        _discrepancies(corpus, st, winners, scale), "|")

    art["invariant_check_report.json"] = bjson(
        _invariants(admitted, winners, displaced, delivered, unused, ent_rows,
                    credits, budgets, traces))

    art["period_reconciliation_totals.json"] = bjson(
        _period_totals(winners, credits, ent_rows, st_util))

    art["network_settlement_summary.xml"] = _summary_xml(
        mission_rows, station_rows, credits)

    art["per_mission_final_summary.md"] = _summary_md(st, mission_rows, credits,
                                                      cidx)

    digest = hashlib.sha256()
    for name in CORE_ARTIFACTS:
        digest.update(art[name])
    art["stage_digest_manifest.json"] = bjson({
        "artifact_count": len(CORE_ARTIFACTS),
        "core_digest": digest.hexdigest(),
        "per_artifact_sha256": {n: hashlib.sha256(art[n]).hexdigest()
                                for n in CORE_ARTIFACTS},
        "stage_count": 14,
    })
    return art


def _by_mission(st, winners, credits, cidx):
    agg = {}
    for r in winners:
        key = (r["mission_id"], r["period_id"])
        a = agg.setdefault(key, {"won_pass_count": 0, "eligible_seconds": 0,
                                 "usable_capacity_kib": 0, "accepted_kib": 0,
                                 "deferred_kib": 0, "unused_capacity_kib": 0})
        a["won_pass_count"] += 1
        a["eligible_seconds"] += r["eligible_seconds"]
        a["usable_capacity_kib"] += r["usable_capacity_kib"]
        a["accepted_kib"] += r["accepted_kib"]
        a["deferred_kib"] += r["deferred_kib"]
        a["unused_capacity_kib"] += r["unused_capacity_kib"]
    net = {}
    for c in credits:
        mission = cidx[c["contract_id"]]["mission_id"]
        net[(mission, c["period_id"])] = net.get((mission, c["period_id"]), 0) + c["net_mcr"]
    rows = []
    for m in st["missions"]:
        for pid in PERIOD_IDS:
            a = agg.get((m, pid), {"won_pass_count": 0, "eligible_seconds": 0,
                                   "usable_capacity_kib": 0, "accepted_kib": 0,
                                   "deferred_kib": 0, "unused_capacity_kib": 0})
            row = {"mission_id": m, "period_id": pid}
            row.update(a)
            row["net_mcr"] = net.get((m, pid), 0)
            rows.append(row)
    return rows


def _by_station(st, winners, cidx, st_util):
    util = {(r["station_id"], r["period_id"]): r["utilisation_bp"] for r in st_util}
    agg = {}
    for r in winners:
        key = (r["station_id"], r["period_id"])
        a = agg.setdefault(key, {"won_pass_count": 0, "eligible_seconds": 0,
                                 "accepted_kib": 0, "unused_capacity_kib": 0})
        a["won_pass_count"] += 1
        a["eligible_seconds"] += r["eligible_seconds"]
        a["accepted_kib"] += r["accepted_kib"]
        a["unused_capacity_kib"] += r["unused_capacity_kib"]
    rows = []
    for s in st["stations"]:
        for pid in PERIOD_IDS:
            a = agg.get((s, pid), {"won_pass_count": 0, "eligible_seconds": 0,
                                   "accepted_kib": 0, "unused_capacity_kib": 0})
            row = {"station_id": s, "period_id": pid}
            row.update(a)
            row["utilisation_bp"] = util.get((s, pid), 0)
            rows.append(row)
    return rows


def _exceptions(corpus, rejected, cap_exceptions, displaced, ent_rows,
                ant_util, deferred):
    _reason_of, report_of = code_book(corpus)
    out = []
    # _period is the published fourth sort key, stripped before return because
    # the period sorts the record without being a field of it. Sorting it
    # explicitly keeps the emission off sort stability, which
    # interval_and_tiebreak_notes.md forbids depending on.
    for r in rejected:
        out.append({"exception_class": report_of[r["reject_code"]],
                    "subject_id": r["contact_id"],
                    "code": r["reject_code"], "detail_value": r["predicate_index"],
                    "_period": r.get("period_id", "")})
    for r in cap_exceptions:
        out.append({"exception_class": report_of["X01"],
                    "subject_id": r["contact_id"],
                    "code": "X01", "detail_value": r["clipped_kib"],
                    "_period": r.get("period_id", "")})
    for r in displaced:
        out.append({"exception_class": report_of["X02"],
                    "subject_id": r["contact_id"],
                    "code": "X02", "detail_value": r["displaced_seconds"],
                    "_period": r.get("period_id", "")})
    for r in ent_rows:
        if r["carry_forfeit_kib"] > 0:
            out.append({"exception_class": report_of["X03"],
                        "subject_id": r["contract_id"], "code": "X03",
                        "detail_value": r["carry_forfeit_kib"],
                        "_period": r.get("period_id", "")})
    for r in ant_util:
        if r["denominator_state"] == "empty":
            out.append({"exception_class": report_of["X04"],
                        "subject_id": r["antenna_uid"], "code": "X04",
                        "detail_value": 0,
                        "_period": r.get("period_id", "")})
    for r in deferred:
        if r["late_cancel"]:
            out.append({"exception_class": report_of["X05"],
                        "subject_id": r["contact_id"], "code": "X05",
                        "detail_value": r["deferred_kib"],
                        "_period": r.get("period_id", "")})
    out.sort(key=lambda r: (r["exception_class"], r["subject_id"], r["code"],
                            r["_period"]))
    for r in out:
        del r["_period"]
    return out


def _discrepancies(corpus, st, winners, scale):
    out = []
    accepted = {}
    for r in winners:
        accepted[r["contact_id"]] = accepted.get(r["contact_id"], 0) + r["accepted_kib"]
    reports = {}
    for r in corpus["delivery"]:
        cid = r["contact_id"]
        seq = int(r["report_seq"])
        if cid not in reports or seq > reports[cid][0]:
            reports[cid] = (seq, int(r["reported_kib"]))
    for cid in sorted(accepted):
        if cid not in reports:
            continue
        left = accepted[cid]
        right = reports[cid][1]
        if left == right:
            continue
        out.append({
            "source_left": "canonical_ledger", "source_right": "downlink_report",
            "subject_id": cid, "period_id": "",
            "left_value": left, "right_value": right,
            "delta_value": left - right,
            "discrepancy_class": "over_report" if right > left else "under_report",
        })
    flat = {}
    seen_rev = {}
    for r in corpus["flat_rates"]:
        uid = r["antenna_uid"]
        rev = int(r["table_rev"])
        if uid not in seen_rev or rev > seen_rev[uid]:
            seen_rev[uid] = rev
            flat[uid] = int(r["flat_rate_mkib_per_s"])
    eff = {}
    for r in corpus["rates"]:
        uid = r["antenna_uid"]
        eff.setdefault(uid, []).append(int(r["rate_mkib_per_s"]))
    for uid in sorted(flat):
        band = eff.get(uid, [])
        if not band:
            continue
        lo, hi = min(band), max(band)
        if lo <= flat[uid] <= hi:
            continue
        out.append({
            "source_left": "rate_schedule", "source_right": "legacy_flat_table",
            "subject_id": uid, "period_id": "",
            "left_value": lo if flat[uid] < lo else hi,
            "right_value": flat[uid],
            "delta_value": (lo if flat[uid] < lo else hi) - flat[uid],
            "discrepancy_class": "retired_rate_outside_band",
        })
    out.sort(key=lambda r: (r["source_left"], r["subject_id"]))
    return out


def _invariants(admitted, winners, displaced, delivered, unused, ent_rows,
                credits, budgets, traces):
    checks = []

    def add(name, left, right):
        checks.append({"check_name": name, "left_value": left,
                       "right_value": right, "balanced": 1 if left == right else 0})

    add("admitted_equals_won_plus_displaced", len(admitted),
        len(winners) + len(displaced))
    add("accepted_never_exceeds_allocated",
        sum(1 for r in delivered if r["accepted_kib"] > r["allocated_kib"]), 0)
    add("allocated_never_exceeds_demand",
        sum(1 for r in delivered if r["allocated_kib"] > r["demand_kib"]), 0)
    add("unused_matches_capacity_less_accepted",
        sum(r["usable_capacity_kib"] - r["accepted_kib"] for r in unused),
        sum(r["unused_capacity_kib"] for r in unused))
    add("carry_split_matches_accepted",
        sum(r["from_carry_kib"] + r["from_new_kib"] for r in delivered),
        sum(r["accepted_kib"] for r in delivered))
    over = 0
    grouped = {}
    for r in winners:
        key = (r["antenna_uid"], r["period_id"])
        grouped[key] = grouped.get(key, 0) + r["allocated_kib"]
    for key, total in grouped.items():
        if total > budgets[key]:
            over += 1
    add("allocation_within_aperture_budget", over, 0)
    add("credit_rows_match_entitlement_rows", len(credits), len(ent_rows))
    add("ration_trace_groups_are_over_subscribed",
        len({(t["antenna_uid"], t["period_id"]) for t in traces
             if t["demand_total_kib"] <= t["budget_kib"]}), 0)
    return {"check_count": len(checks), "checks": checks,
            "all_balanced": 1 if all(c["balanced"] for c in checks) else 0}


def _period_totals(winners, credits, ent_rows, st_util):
    out = {}
    for pid in PERIOD_IDS:
        w = [r for r in winners if r["period_id"] == pid]
        c = [r for r in credits if r["period_id"] == pid]
        e = [r for r in ent_rows if r["period_id"] == pid]
        u = [r for r in st_util if r["period_id"] == pid]
        out[pid] = {
            "won_pass_count": len(w),
            "eligible_seconds": sum(r["eligible_seconds"] for r in w),
            "usable_capacity_kib": sum(r["usable_capacity_kib"] for r in w),
            "accepted_kib": sum(r["accepted_kib"] for r in w),
            "deferred_kib": sum(r["deferred_kib"] for r in w),
            "unused_capacity_kib": sum(r["unused_capacity_kib"] for r in w),
            "carry_in_kib": sum(r["carry_in_kib"] for r in e),
            "carry_forfeit_kib": sum(r["carry_forfeit_kib"] for r in e),
            "carry_out_kib": sum(r["unconsumed_kib"] for r in e),
            "shortfall_debit_mcr": sum(r["shortfall_debit_mcr"] for r in c),
            "unused_credit_mcr": sum(r["unused_credit_mcr"] for r in c),
            "outage_credit_mcr": sum(r["outage_credit_mcr"] for r in c),
            "net_mcr": sum(r["net_mcr"] for r in c),
            "occupied_seconds": sum(r["occupied_seconds"] for r in u),
            "available_seconds": sum(r["available_seconds"] for r in u),
        }
    out["network"] = {
        "net_mcr": sum(out[p]["net_mcr"] for p in PERIOD_IDS),
        "accepted_kib": sum(out[p]["accepted_kib"] for p in PERIOD_IDS),
        "won_pass_count": sum(out[p]["won_pass_count"] for p in PERIOD_IDS),
    }
    return out


def _summary_xml(mission_rows, station_rows, credits):
    lines = [XMLDECL, "<settlement>"]
    lines.append("<missions>")
    for r in mission_rows:
        lines.append("<mission id=" + Q + xesc(r["mission_id"]) + Q
                     + " period=" + Q + xesc(r["period_id"]) + Q + ">"
                     + "<accepted_kib>" + str(r["accepted_kib"]) + "</accepted_kib>"
                     + "<deferred_kib>" + str(r["deferred_kib"]) + "</deferred_kib>"
                     + "<net_mcr>" + str(r["net_mcr"]) + "</net_mcr></mission>")
    lines.append("</missions>")
    lines.append("<stations>")
    for r in station_rows:
        lines.append("<station id=" + Q + xesc(r["station_id"]) + Q
                     + " period=" + Q + xesc(r["period_id"]) + Q + ">"
                     + "<accepted_kib>" + str(r["accepted_kib"]) + "</accepted_kib>"
                     + "<utilisation_bp>" + str(r["utilisation_bp"])
                     + "</utilisation_bp></station>")
    lines.append("</stations>")
    lines.append("<network>")
    lines.append("<net_mcr>" + str(sum(c["net_mcr"] for c in credits)) + "</net_mcr>")
    lines.append("<contract_period_count>" + str(len(credits))
                 + "</contract_period_count>")
    lines.append("</network>")
    lines.append("</settlement>")
    return (chr(10).join(lines) + chr(10)).encode("utf-8")


def _summary_md(st, mission_rows, credits, cidx):
    net = {}
    for c in credits:
        mission = cidx[c["contract_id"]]["mission_id"]
        net[mission] = net.get(mission, 0) + c["net_mcr"]
    lines = ["# mission settlement summary", ""]
    lines.append("| mission_id | accepted_kib | deferred_kib | unused_capacity_kib | net_mcr |")
    lines.append("| --- | --- | --- | --- | --- |")
    for m in st["missions"]:
        rows = [r for r in mission_rows if r["mission_id"] == m]
        lines.append("| " + m + " | " + str(sum(r["accepted_kib"] for r in rows))
                     + " | " + str(sum(r["deferred_kib"] for r in rows))
                     + " | " + str(sum(r["unused_capacity_kib"] for r in rows))
                     + " | " + str(net.get(m, 0)) + " |")
    lines.append("")
    lines.append("network net_mcr " + str(sum(net.values())))
    return (chr(10).join(lines) + chr(10)).encode("utf-8")

# ---------------------------------------------------------------------------
# The network the operator runs, and the month end paperwork it produced.
# Everything here is a function of one seed, so a case regenerated at the same
# seed is byte identical and no graded value depends on anything else.
# ---------------------------------------------------------------------------
T0 = 1767225600
PERIOD_S = 1209600
DAY_S = 86400
PERIOD_DAYS = 14
PERIODS = ["P1", "P2", "P3"]
STATION_STEMS = ["aurora", "basalt", "cinder", "delta", "ember", "fathom",
                 "granite", "harbour", "isthmus", "juniper", "kelvin", "lantern"]
LOCAL_LABELS = ["A1", "A2", "A3"]
MISSION_STEMS = ["halcyon", "kestrel", "meridian", "nimbus", "orchid", "pelican",
                 "quartz", "rivulet", "solstice", "tamarind", "umber", "vellum",
                 "willow", "xenon", "yarrow", "zephyr", "auger", "beryl"]
PRIORITY_CLASSES = ["emergency_override", "contracted_priority", "ordinary_priority"]
PRIORITY_RANK = {"emergency_override": 1, "contracted_priority": 2,
                 "ordinary_priority": 3}
ADMITTED_EVENT_STATUS = ["nominal", "partial"]
AUTHORITY_GRADES = ["controller", "supervisor", "trainee", "observer"]
COMMIT_GRADE_SET = ["controller", "supervisor"]
PHASE_CLASSES = ["routine", "intensive", "standdown", "commissioning"]
OUTAGE_STATUS = ["accepted", "rejected", "withdrawn"]
CANCEL_REASONS = ["weather_hold", "spacecraft_safe_mode", "range_conflict",
                  "operator_request", ""]
FACILITY_ELEMENTS = [
    ("accounting_site", "period accounting anchor"),
    ("pedestal", "azimuth elevation pedestal"),
    ("pedestal", "secondary pedestal"),
    ("receiver", "wideband receiver"),
    ("receiver", "narrowband receiver"),
    ("recorder", "baseband recorder"),
    ("recorder", "archive recorder"),
    ("timing", "frequency standard"),
    ("timing", "distribution amplifier"),
    ("power", "primary feed"),
    ("power", "standby generator"),
    ("network", "terrestrial link"),
    ("network", "diverse link"),
    ("safety", "range interlock"),
    ("safety", "radiation hazard monitor"),
    ("workshop", "mechanical bay"),
    ("workshop", "electronics bay"),
    ("stores", "spares cage"),
]
THETA_NUM = 3
THETA_DEN = 4
PASS_BUDGET_BASE = 2
PASS_BUDGET_CEILING = 12
OUTAGE_QUALIFY_MIN_S = 900
CARRY_RESTORE_NUM = 2
CARRY_RESTORE_DEN = 5
RATE_SCALE = 1000
CREDIT_BASIS = 1024

STATIONS = ["ST-" + s[:3].upper() for s in STATION_STEMS]
MISSIONS = ["MSN-" + format(i + 1, "02d") for i in range(len(MISSION_STEMS))]
TWIN_CONTRACT_MISSIONS = ["MSN-02", "MSN-05", "MSN-08", "MSN-11", "MSN-14", "MSN-17"]
TZ_OFFSET_MIN = {}
COMMIT_LEAD_S = {}
for _i, _s in enumerate(STATIONS):
    TZ_OFFSET_MIN[_s] = [330, -300, 60, -480, 0, 210, -210, 480, -60, 120,
                         -420, 540][_i]
    COMMIT_LEAD_S[_s] = [5400, 3600, 7200, 2700, 4500, 6300, 3000, 8100,
                         3900, 5100, 4200, 6900][_i]


def period_bounds(idx):
    return T0 + idx * PERIOD_S, T0 + (idx + 1) * PERIOD_S


def local_period_bounds(station, idx):
    """The station local accounting period, expressed back in UTC seconds."""
    shift = TZ_OFFSET_MIN[station] * 60
    a, b = period_bounds(idx)
    return a - shift, b - shift


def build_instance(seed):
    rng = Rng(seed)
    ent = {"seed": int(seed)}

    ent["periods"] = []
    for i, pid in enumerate(PERIODS):
        a, b = period_bounds(i)
        ent["periods"].append({"period_id": pid, "start_s": a, "end_s": b, "index": i})

    ent["stations"] = []
    for i, st in enumerate(STATIONS):
        ent["stations"].append({
            "station_id": st, "site_name": STATION_STEMS[i],
            "tz_offset_min": TZ_OFFSET_MIN[st],
            "commit_lead_s": COMMIT_LEAD_S[st],
        })

    ent["antennas"] = []
    n = 0
    for st in STATIONS:
        for lbl in LOCAL_LABELS:
            n += 1
            ent["antennas"].append({
                "antenna_uid": "APR-" + format(1000 + n, "04d"),
                "station_id": st, "local_label": lbl,
                "band": rng.pick(["s-band", "x-band", "ka-band"]),
                "window_span_s": rng.between(18000, 30000),
                "window_start_s": rng.between(3600, 21600),
            })
    ent["antenna_by_uid"] = {a["antenna_uid"]: a for a in ent["antennas"]}

    ent["missions"] = []
    for i, m in enumerate(MISSIONS):
        cls = PRIORITY_CLASSES[2]
        if i % 7 == 3:
            cls = PRIORITY_CLASSES[0]
        elif i % 5 in (0, 2):
            cls = PRIORITY_CLASSES[1]
        ent["missions"].append({
            "mission_id": m, "call_name": MISSION_STEMS[i],
            "priority_class": cls,
            "operator_group": "grp-" + str(1 + (i % 4)),
        })
    ent["mission_by_id"] = {m["mission_id"]: m for m in ent["missions"]}

    ent["contracts"] = []
    cn = 100
    for m in MISSIONS:
        count = 2 if m in TWIN_CONTRACT_MISSIONS else 1
        for k in range(count):
            cn += 1
            expiring = (m == "MSN-13" and k == 0)
            ent["contracts"].append({
                "contract_id": "CTR-" + str(cn),
                "mission_id": m, "seq": k,
                "valid_from_s": T0 - DAY_S,
                # The expiry test at S08 uses the earliest station local
                # period open across the network, and the widest positive tz
                # offset pulls that instant ahead of T0 + 2 * PERIOD_S. Expire
                # a day earlier so the contract is really expired at P3.
                "valid_to_s": (T0 + 2 * PERIOD_S - DAY_S) if expiring
                              else (T0 + 3 * PERIOD_S + DAY_S),
                "carry_forward_enabled": 0 if m in ("MSN-06", "MSN-15") else 1,
                "scope": _scope_for(rng, k),
            })
    ent["contract_by_id"] = {c["contract_id"]: c for c in ent["contracts"]}

    _build_windows(ent, rng)
    _build_rates(ent, rng)
    _build_workbook_numbers(ent, rng)
    _build_terms(ent, rng)
    _build_phases(ent, rng)
    _build_roster(ent, rng)
    _build_contacts(ent, rng)
    _plant_rate_edge(ent)
    _build_events(ent, rng)
    _build_cancellations(ent, rng)
    _pin_corners(ent)
    _build_overrides(ent, rng)
    _build_backlog(ent, rng)
    _build_delivery(ent, rng)
    _build_prior(ent, rng)
    _build_outages(ent, rng)
    _plant_order_corner(ent)
    return ent


def _scope_for(rng, k):
    base = list(STATIONS)
    for _ in range(rng.between(0, 2)):
        drop = rng.pick(base)
        if len(base) > 10:
            base = [s for s in base if s != drop]
    if k == 1:
        base = base[:9]
    return sorted(base)


# ---------------------------------------------------------------------------
# operating windows, maintenance dockets and blackout advisories
# ---------------------------------------------------------------------------
def _build_windows(ent, rng):
    rows = []
    for a in ent["antennas"]:
        for d in range(len(PERIODS) * PERIOD_DAYS):
            day0 = T0 + d * DAY_S
            start = day0 + a["window_start_s"] + rng.between(0, 900) * 4
            span = a["window_span_s"] + rng.between(-1800, 1800)
            rows.append({
                "antenna_uid": a["antenna_uid"], "day_index": d,
                "effective_from_s": start, "effective_to_s": start + span,
                "service_state": "in_service",
            })
    dead = ent["antennas"][19]["antenna_uid"]
    # The station local P2 window is the UTC day range shifted by the station
    # tz offset, so a withdrawal keyed on the day index alone leaves a sliver
    # of in service window inside P2 and the denominator never empties. One
    # extra day on each side covers the shift, which is under a day.
    for r in rows:
        if (r["antenna_uid"] == dead
                and PERIOD_DAYS - 1 <= r["day_index"] < 2 * PERIOD_DAYS + 1):
            r["service_state"] = "withdrawn"
    ent["windows"] = rows
    ent["window_index"] = {}
    for r in rows:
        ent["window_index"][(r["antenna_uid"], r["day_index"])] = r

    md = []
    for a in ent["antennas"]:
        for d in range(len(PERIODS) * PERIOD_DAYS):
            if not rng.chance(4, 13):
                continue
            day0 = T0 + d * DAY_S
            start = day0 + a["window_start_s"] + rng.between(1, 40) * 600
            dur = rng.between(1, 9) * 600
            md.append({
                "docket_id": "MD-" + format(len(md) + 1, "05d"),
                "antenna_uid": a["antenna_uid"],
                "start_s": start, "end_s": start + dur,
                "docket_class": rng.pick(["preventive", "corrective", "calibration"]),
                "raised_by": "wo-" + format(rng.between(1000, 9999), "04d"),
            })
    ent["maintenance"] = md

    bl = []
    for st in STATIONS:
        for d in range(len(PERIODS) * PERIOD_DAYS):
            if not rng.chance(5, 11):
                continue
            day0 = T0 + d * DAY_S
            start = day0 + rng.between(2, 80) * 900
            dur = rng.between(1, 6) * 900
            bl.append({
                "advisory_id": "BA-" + format(len(bl) + 1, "05d"),
                "station_id": st, "start_s": start, "end_s": start + dur,
                "advisory_class": rng.pick(["rf_interference", "range_safety",
                                            "power_curtailment"]),
                "issued_s": start - rng.between(1, 12) * 3600,
            })
    ent["blackouts"] = bl


# ---------------------------------------------------------------------------
# effective dated rates and the retired flat table that disagrees with them
# ---------------------------------------------------------------------------
def _build_rates(ent, rng):
    rows = []
    for a in ent["antennas"]:
        base = rng.between(2400, 9600)
        cuts = sorted({rng.between(2, 40) * DAY_S for _ in range(5)})
        edges = [T0 - DAY_S] + [T0 + c for c in cuts] + [T0 + 3 * PERIOD_S + DAY_S]
        for i in range(len(edges) - 1):
            rows.append({
                "antenna_uid": a["antenna_uid"],
                "effective_from_s": edges[i], "effective_to_s": edges[i + 1],
                "rate_mkib_per_s": base + rng.between(-600, 900),
                "schedule_rev": i + 1,
            })
    ent["rates"] = rows
    ent["rate_index"] = {}
    for r in rows:
        ent["rate_index"].setdefault(r["antenna_uid"], []).append(r)

    flat = []
    for a in ent["antennas"]:
        band = [r["rate_mkib_per_s"] for r in ent["rate_index"][a["antenna_uid"]]]
        mid = sum(band) // len(band)
        for rev in range(1, 7):
            flat.append({
                "antenna_uid": a["antenna_uid"], "table_rev": rev,
                "flat_rate_mkib_per_s": mid + rng.between(-1400, 1400),
                "retired_on_s": T0 - DAY_S,
                "table_state": "retired",
            })
    ent["flat_rates"] = flat


# ---------------------------------------------------------------------------
# the workbook numbers, which live only in the spreadsheet
# ---------------------------------------------------------------------------
def _build_workbook_numbers(ent, rng):
    caps = {}
    budgets = {}
    for a in ent["antennas"]:
        for p in PERIODS:
            caps[(a["antenna_uid"], p)] = rng.between(3, 12) * 4096
            budgets[(a["antenna_uid"], p)] = rng.between(6, 22) * 8192
    for idx in (2, 8, 17, 26, 31):
        uid = ent["antennas"][idx]["antenna_uid"]
        budgets[(uid, PERIODS[idx % 3])] = rng.between(4, 9) * 4096
        caps[(uid, PERIODS[idx % 3])] = rng.between(5, 10) * 4096
    ent["caps"] = caps
    ent["budgets"] = budgets
    ent["superseded_caps"] = {k: v + 8192 for k, v in caps.items()}
    ent["superseded_budgets"] = {k: v + 32768 for k, v in budgets.items()}
    ent["draft_caps"] = {k: max(2048, v - 2048) for k, v in caps.items()}
    ent["draft_budgets"] = {k: max(8192, v - 8192) for k, v in budgets.items()}
    ent["credit_rates"] = {
        "shortfall_debit_mcr_per_mib": rng.between(180, 260),
        "unused_reserved_credit_mcr_per_mib": rng.between(40, 90),
        "outage_credit_mcr_per_mib": rng.between(120, 200),
        "carry_restore_numerator": CARRY_RESTORE_NUM,
        "carry_restore_denominator": CARRY_RESTORE_DEN,
    }


# ---------------------------------------------------------------------------
# contract terms, shipped as an amendment log rather than a settled table
# ---------------------------------------------------------------------------
def _build_terms(ent, rng):
    rows = []
    for c in ent["contracts"]:
        for p in PERIODS:
            revs = 4
            for r in range(1, revs + 1):
                executed = (r == revs - 1)
                status = "executed" if executed else (
                    "withdrawn" if r == revs else rng.pick(["draft", "withdrawn"]))
                rows.append({
                    "contract_id": c["contract_id"], "period_id": p,
                    "revision_seq": r, "amendment_status": status,
                    "obligation_kib": rng.between(40, 220) * 4096,
                    "entitlement_kib": rng.between(60, 260) * 4096,
                    "reserved_kib": rng.between(20, 120) * 4096,
                    "carry_cap_kib": 0 if not c["carry_forward_enabled"]
                                     else rng.between(10, 70) * 4096,
                    "carry_forward_enabled": c["carry_forward_enabled"],
                    "amended_on_s": T0 - DAY_S + r * 3600,
                })
    # A superseded amendment that carries a larger obligation than the executed
    # one, so a reader that takes the last row by file order is wrong.
    for r in rows:
        if r["revision_seq"] in (2, 4):
            r["obligation_kib"] = r["obligation_kib"] + 40960
            r["entitlement_kib"] = r["entitlement_kib"] + 20480
    zero = ent["contracts"][7]["contract_id"]
    for r in rows:
        if r["contract_id"] == zero and r["period_id"] == "P2":
            r["entitlement_kib"] = 0
            r["carry_cap_kib"] = 0
    ent["terms_rows"] = rows


# ---------------------------------------------------------------------------
# campaign phases and the operator roster
# ---------------------------------------------------------------------------
def _build_phases(ent, rng):
    rows = []
    for m in MISSIONS:
        cursor = T0 - DAY_S
        end = T0 + 3 * PERIOD_S + DAY_S
        idx = 0
        while idx < 12:
            idx += 1
            span = rng.between(3, 6) * DAY_S
            nxt = cursor + span
            if idx == 12:
                nxt = max(nxt, end)
            if idx == 1:
                cls = PHASE_CLASSES[0]
            elif rng.chance(1, 11):
                cls = PHASE_CLASSES[2]
            else:
                cls = rng.pick([PHASE_CLASSES[0], PHASE_CLASSES[1],
                                PHASE_CLASSES[3]])
            rows.append({
                "mission_id": m, "phase_seq": idx,
                "phase_from_s": cursor, "phase_to_s": nxt,
                "phase_class": cls,
            })
            cursor = nxt
    ent["phases"] = rows


def _build_roster(ent, rng):
    rows = []
    for i in range(216):
        grade = AUTHORITY_GRADES[0]
        if i % 9 == 4:
            grade = AUTHORITY_GRADES[1]
        elif i % 7 == 5:
            grade = AUTHORITY_GRADES[2]
        elif i % 11 == 9:
            grade = AUTHORITY_GRADES[3]
        rows.append({
            "operator_code": "op-" + format(i + 1, "04d"),
            "station_id": STATIONS[i % len(STATIONS)],
            "authority_grade": grade,
            "shift_code": "sh-" + str(1 + (i % 3)),
            "roster_state": "active" if i % 23 != 7 else "detached",
        })
    ent["roster"] = rows
    ent["commit_ops"] = [r["operator_code"] for r in rows
                         if r["authority_grade"] in COMMIT_GRADE_SET]
    ent["weak_ops"] = [r["operator_code"] for r in rows
                       if r["authority_grade"] not in COMMIT_GRADE_SET]


# ---------------------------------------------------------------------------
# the pass plan of record and the effective dated alias crosswalk
# ---------------------------------------------------------------------------
def _build_contacts(ent, rng):
    alias = []
    for m in ent["missions"]:
        cut = T0 + PERIOD_S + rng.between(1, 12) * DAY_S
        stem = m["call_name"]
        alias.append({"presentation_id": stem + "-a", "mission_id": m["mission_id"],
                      "valid_from_s": T0 - 2 * DAY_S, "valid_to_s": cut,
                      "crosswalk_rev": 1})
        alias.append({"presentation_id": stem + "-b", "mission_id": m["mission_id"],
                      "valid_from_s": cut,
                      "valid_to_s": T0 + 3 * PERIOD_S + DAY_S, "crosswalk_rev": 1})
        # Duplicate looking rows that belong to a different effective period.
        alias.append({"presentation_id": stem + "-a", "mission_id": m["mission_id"],
                      "valid_from_s": T0 + 3 * PERIOD_S + DAY_S,
                      "valid_to_s": T0 + 4 * PERIOD_S, "crosswalk_rev": 2})
        for k in range(9):
            alias.append({"presentation_id": stem + "-r" + str(k),
                          "mission_id": m["mission_id"],
                          "valid_from_s": T0 - 40 * DAY_S - k * DAY_S,
                          "valid_to_s": T0 - 39 * DAY_S - k * DAY_S,
                          "crosswalk_rev": 3})
    ent["alias"] = alias
    ent["alias_index"] = {}
    for r in alias:
        ent["alias_index"].setdefault(r["mission_id"], []).append(r)

    contacts = []
    cid = 0
    for a in ent["antennas"]:
        for d in range(len(PERIODS) * PERIOD_DAYS):
            if not rng.chance(4, 9):
                continue
            win = ent["window_index"].get((a["antenna_uid"], d))
            if win is None:
                continue
            for _s in range(rng.between(1, 3)):
                cid += 1
                mission = rng.pick(MISSIONS)
                start = win["effective_from_s"] + rng.between(0, 30) * 600
                dur = rng.between(2, 26) * 300
                contacts.append({
                    "contact_id": "PAS-" + format(cid, "05d"),
                    "presentation_id": _alias_at(ent, mission, start),
                    "station_id": a["station_id"],
                    "aperture_label": a["local_label"],
                    "scheduled_start_s": start, "scheduled_end_s": start + dur,
                    "requested_kib": rng.between(20, 200) * 1024,
                    "plan_rev": rng.between(1, 3),
                    "corner": "",
                })
    _place_corners(ent, contacts, rng)
    contacts.sort(key=lambda c: c["contact_id"])
    ent["contacts"] = contacts


def _alias_at(ent, mission, t):
    for row in ent["alias_index"].get(mission, []):
        if row["valid_from_s"] <= t < row["valid_to_s"]:
            return row["presentation_id"]
    return ent["mission_by_id"][mission]["call_name"] + "-a"


def _place_corners(ent, contacts, rng):
    """Hand placed boundary cases. Each is a pass whose start or end sits
    exactly on an edge that some other record declares."""
    seq = [0]

    def mint(a, start, end, mission, tag):
        seq[0] += 1
        contacts.append({
            "contact_id": "PAS-" + format(90000 + seq[0], "05d"),
            "presentation_id": _alias_at(ent, mission, start),
            "station_id": a["station_id"], "aperture_label": a["local_label"],
            "scheduled_start_s": start, "scheduled_end_s": end,
            "requested_kib": rng.between(20, 200) * 1024,
            "plan_rev": 1, "corner": tag,
        })

    apr = ent["antennas"]
    w = ent["window_index"][(apr[0]["antenna_uid"], 3)]
    mint(apr[0], w["effective_from_s"] + 3600, w["effective_from_s"] + 3600,
         MISSIONS[0], "zero_length")
    for md in ent["maintenance"]:
        a = ent["antenna_by_uid"][md["antenna_uid"]]
        if md["start_s"] - 1800 > T0:
            mint(a, md["start_s"] - 1800, md["start_s"], MISSIONS[1], "abuts_md_start")
            mint(a, md["end_s"], md["end_s"] + 1800, MISSIONS[2], "abuts_md_end")
            break
    w = ent["window_index"][(apr[4]["antenna_uid"], 6)]
    mid = w["effective_from_s"] + 5400
    mint(apr[4], mid - 1800, mid, MISSIONS[3], "adjacent_left")
    mint(apr[4], mid, mid + 1800, MISSIONS[4], "adjacent_right")
    w = ent["window_index"][(apr[9]["antenna_uid"], 9)]
    s = w["effective_from_s"] + 7200
    mint(apr[9], s, s + 2400, MISSIONS[5], "identical_a")
    mint(apr[9], s, s + 2400, MISSIONS[5], "identical_b")
    w = ent["window_index"][(apr[11]["antenna_uid"], 12)]
    s = w["effective_from_s"] + 3600
    mint(apr[11], s, s + 5400, MISSIONS[8], "triple_a")
    mint(apr[11], s + 900, s + 6300, MISSIONS[8], "triple_b")
    mint(apr[11], s + 1800, s + 7200, MISSIONS[8], "triple_c")
    for r in ent["rates"]:
        if T0 + DAY_S < r["effective_from_s"] < T0 + 3 * PERIOD_S:
            a = ent["antenna_by_uid"][r["antenna_uid"]]
            mint(a, r["effective_from_s"] - 1200, r["effective_from_s"] + 1200,
                 MISSIONS[6], "rate_edge")
            break
    st = STATIONS[0]
    a = [x for x in ent["antennas"] if x["station_id"] == st][0]
    lb = local_period_bounds(st, 1)[0]
    mint(a, lb - 2400, lb + 2400, MISSIONS[7], "period_straddle")
    dead = ent["antennas"][19]
    mint(dead, T0 + 15 * DAY_S + 3600, T0 + 15 * DAY_S + 7200, MISSIONS[0],
         "withdrawn_apr")
    # a presentation identifier whose windows all close before the campaign
    w = ent["window_index"][(apr[13]["antenna_uid"], 5)]
    s2 = w["effective_from_s"] + 2400
    mint(apr[13], s2, s2 + 1800, MISSIONS[10], "alias_unresolved")
    contacts[-1]["presentation_id"] = (
        ent["mission_by_id"][MISSIONS[10]]["call_name"] + "-r4")
    # an aperture label that binds under no current configuration row
    w = ent["window_index"][(apr[16]["antenna_uid"], 8)]
    s2 = w["effective_from_s"] + 3000
    mint(apr[16], s2, s2 + 1800, MISSIONS[11], "aperture_unknown")
    contacts[-1]["aperture_label"] = "A9"
    # a station outside every contract scope of the mission
    w = ent["window_index"][(apr[30]["antenna_uid"], 24)]
    s2 = w["effective_from_s"] + 3000
    mint(apr[30], s2, s2 + 1800, MISSIONS[12], "out_of_scope")
    w = ent["window_index"][(apr[23]["antenna_uid"], 20)]
    s = w["effective_from_s"] + 1800
    for k in range(6):
        mint(apr[23], s + k * 300, s + 5400 + k * 300, MISSIONS[9 + k], "crowded")


def _plant_order_corner(ent):
    """Two passes that fail more than one admission predicate at the head of
    the published order, so predicate one beating predicate two and predicate
    two beating predicate three are each decided by a graded row rather than
    left to a reading no case distinguishes.

    This runs last and draws nothing from the generator, so every earlier
    builder mints exactly what it minted before. Moving the call earlier would
    shift the draw sequence and rebuild the whole corpus. Neither pass carries
    an event, a cancellation, a downlink report or an outage claim, because the
    predicate that decides it fires before any of those is read.
    """
    first = ent["antennas"][13]
    window = ent["window_index"][(first["antenna_uid"], 5)]
    ent["contacts"].append({
        "contact_id": "PAS-99001",
        "presentation_id": ent["mission_by_id"][MISSIONS[10]]["call_name"] + "-r4",
        "station_id": first["station_id"],
        "aperture_label": "A9",
        "scheduled_start_s": window["effective_from_s"] + 1200,
        "scheduled_end_s": window["effective_from_s"] + 3000,
        "requested_kib": 65536,
        "plan_rev": 1,
        "corner": "order_one_over_two",
    })
    second = ent["antennas"][16]
    before_every_contract_opens = T0 - 2 * DAY_S + 3600
    ent["contacts"].append({
        "contact_id": "PAS-99002",
        "presentation_id": _alias_at(ent, MISSIONS[11], before_every_contract_opens),
        "station_id": second["station_id"],
        "aperture_label": "A9",
        "scheduled_start_s": before_every_contract_opens,
        "scheduled_end_s": before_every_contract_opens + 1800,
        "requested_kib": 65536,
        "plan_rev": 1,
        "corner": "order_two_over_three",
    })
    ent["contacts"].sort(key=lambda c: c["contact_id"])


def _plant_rate_edge(ent):
    """Put one rate schedule edge exactly on the scheduled start of a pass.

    The generated edges all sit on day boundaries and the passes all sit inside
    an operating window, so without this no pass ever begins on an edge and the
    S05 rule that an edge on a pass boundary splits nothing decides nothing.
    Splitting a row in two at the start of a real pass makes both readings
    visible: that pass keeps one rate piece, and a pass of the same aperture
    that spans the instant now carries two.
    """
    by_label = {(a["station_id"], a["local_label"]): a for a in ent["antennas"]}
    md = {}
    for r in ent["maintenance"]:
        md.setdefault(r["antenna_uid"], []).append((r["start_s"], r["end_s"]))
    bl = {}
    for r in ent["blackouts"]:
        bl.setdefault(r["station_id"], []).append((r["start_s"], r["end_s"]))

    def clear(a, lo, hi):
        """The whole span sits inside one in service window and outside every
        docket of the aperture and every advisory of its station, so the
        eligible interval of the pass opens exactly on its scheduled start."""
        win = None
        for w in ent["windows"]:
            if (w["antenna_uid"] == a["antenna_uid"]
                    and w["service_state"] == "in_service"
                    and w["effective_from_s"] <= lo and hi <= w["effective_to_s"]):
                win = w
                break
        if win is None:
            return False
        for x, y in md.get(a["antenna_uid"], []) + bl.get(a["station_id"], []):
            if x < hi and lo < y:
                return False
        return True

    for c in sorted(ent["contacts"], key=lambda r: r["contact_id"]):
        if c.get("corner"):
            continue
        a = by_label.get((c["station_id"], c["aperture_label"]))
        if a is None:
            continue
        uid = a["antenna_uid"]
        t = c["scheduled_start_s"]
        rows = ent["rate_index"][uid]
        host = None
        for r in rows:
            if r["effective_from_s"] < t < r["effective_to_s"]:
                host = r
                break
        if host is None:
            continue
        # The pass has to survive clipping whole, or its eligible interval
        # opens after its scheduled start and the planted edge lands strictly
        # inside it, which is the opposite of the case being placed.
        if not clear(a, c["scheduled_start_s"], c["scheduled_end_s"]):
            continue
        # No other edge may fall strictly inside it, so a correct reading
        # writes exactly one rate piece and an inclusive one writes two.
        if any(r["effective_from_s"] < c["scheduled_end_s"]
               and c["scheduled_start_s"] < r["effective_from_s"]
               for r in rows):
            continue
        # Only useful when another pass of the same aperture spans the instant,
        # so the split reading and the whole reading disagree somewhere.
        spans = [o for o in ent["contacts"]
                 if o is not c
                 and o["station_id"] == c["station_id"]
                 and o["aperture_label"] == c["aperture_label"]
                 and o["scheduled_start_s"] < t < o["scheduled_end_s"]
                 and clear(a, o["scheduled_start_s"], o["scheduled_end_s"])]
        if not spans:
            continue
        tail = dict(host)
        tail["effective_from_s"] = t
        host["effective_to_s"] = t
        rows.append(tail)
        rows.sort(key=lambda r: r["effective_from_s"])
        for i, r in enumerate(rows, start=1):
            r["schedule_rev"] = i
        ent["rates"] = [r for r in ent["rates"] if r["antenna_uid"] != uid]
        ent["rates"].extend(rows)
        ent["rates"].sort(key=lambda r: (r["antenna_uid"], r["schedule_rev"]))
        ent["rate_edge_contact"] = c["contact_id"]
        return


CORNER_MUST_ADMIT = ("zero_length", "identical_a", "identical_b")


def _pin_corners(ent):
    """Hold the hand placed corner passes at the state they were placed for.

    The event and cancellation draws run after the placement and would
    otherwise abort or cancel the very passes that carry the boundary cases,
    which leaves the rule they exercise decided by nothing.
    """
    corner = {c["contact_id"]: c.get("corner") for c in ent["contacts"]}
    want = {cid for cid, tag in corner.items() if tag in CORNER_MUST_ADMIT}
    if not want:
        return
    events = {e["contact_id"]: e for e in ent["events"]}
    op = sorted(ent["commit_ops"])[0]
    for c in ent["contacts"]:
        cid = c["contact_id"]
        if cid not in want:
            continue
        lead = COMMIT_LEAD_S[c["station_id"]]
        ev = events.get(cid)
        if ev is None:
            ev = {"contact_id": cid, "journal_seq": len(ent["events"]) + 1}
            ent["events"].append(ev)
            events[cid] = ev
        ev["event_status"] = "nominal"
        ev["actual_start_s"] = c["scheduled_start_s"]
        ev["actual_end_s"] = c["scheduled_end_s"]
        # The identical interval pair has to agree on protection as well as on
        # class, commit boundary and obligation, or the ladder stops at rung
        # one and rung five is never reached.
        if corner[cid] in ("identical_a", "identical_b"):
            ev["operator_code"] = op
            ev["event_recorded_s"] = c["scheduled_start_s"] - lead
    ent["events"].sort(key=lambda e: e["contact_id"])
    for i, e in enumerate(ent["events"], start=1):
        e["journal_seq"] = i
    ent["cancellations"] = [r for r in ent["cancellations"]
                            if r["contact_id"] not in want]


# ---------------------------------------------------------------------------
# operational events, cancellations, overrides
# ---------------------------------------------------------------------------
def _build_events(ent, rng):
    rows = []
    for c in ent["contacts"]:
        if rng.chance(1, 16):
            continue
        lead = COMMIT_LEAD_S[c["station_id"]]
        status = "nominal"
        roll = rng.below(20)
        if roll < 4:
            status = "partial"
        elif roll == 4:
            status = "aborted"
        elif roll == 5:
            status = "no_show"
        pick = rng.below(3)
        if pick == 0:
            rec = c["scheduled_start_s"] - lead - rng.between(60, 3600)
        elif pick == 1:
            rec = c["scheduled_start_s"] - lead
        else:
            rec = c["scheduled_start_s"] - lead + rng.between(60, 1800)
        actual_start = c["scheduled_start_s"]
        actual_end = c["scheduled_end_s"]
        if status == "partial":
            span = c["scheduled_end_s"] - c["scheduled_start_s"]
            actual_start = c["scheduled_start_s"] + rng.between(0, 600)
            actual_end = c["scheduled_end_s"] - rng.between(0, span // 2 + 1)
            if actual_end < actual_start:
                actual_end = actual_start
        op = rng.pick(ent["commit_ops"]) if rng.chance(5, 6) else rng.pick(ent["weak_ops"])
        rows.append({
            "contact_id": c["contact_id"], "event_status": status,
            "event_recorded_s": rec, "actual_start_s": actual_start,
            "actual_end_s": actual_end, "operator_code": op,
            "journal_seq": len(rows) + 1,
        })
    ent["events"] = rows


def _build_cancellations(ent, rng):
    rows = []
    for c in ent["contacts"]:
        if not rng.chance(3, 13):
            continue
        lead = COMMIT_LEAD_S[c["station_id"]]
        commit = c["scheduled_start_s"] - lead
        choice = rng.below(10)
        if choice < 5:
            eff = commit - rng.between(300, 7200)
        elif choice < 7:
            eff = commit
        else:
            eff = commit + rng.between(300, 3600)
        n = rng.between(1, 3)
        for k in range(1, n + 1):
            state = "effective"
            if k < n and rng.chance(1, 2):
                state = "rescinded"
            rows.append({
                "notice_id": "CN-" + format(len(rows) + 1, "05d"),
                "contact_id": c["contact_id"], "issued_seq": k,
                "notice_state": state, "effective_s": eff + (k - 1) * 60,
                "reason_code": rng.pick(CANCEL_REASONS),
            })
    ent["cancellations"] = rows


def _build_overrides(ent, rng):
    rows = []
    for m in MISSIONS:
        for _ in range(11):
            a = rng.pick(ent["antennas"])
            start = T0 + rng.between(0, 40) * DAY_S
            rows.append({
                "override_id": "PO-" + format(len(rows) + 1, "04d"),
                "mission_id": m, "antenna_uid": a["antenna_uid"],
                "granted_class": rng.pick(PRIORITY_CLASSES[:2]),
                "valid_from_s": start,
                "valid_to_s": start + rng.between(1, 6) * DAY_S,
                "instrument_ref": "DIR-" + format(rng.between(100, 999), "03d"),
            })
    span = (T0 + 5 * DAY_S, T0 + 9 * DAY_S)
    for a in (ent["antennas"][1], ent["antennas"][6]):
        rows.append({
            "override_id": "PO-" + format(len(rows) + 1, "04d"),
            "mission_id": MISSIONS[2], "antenna_uid": a["antenna_uid"],
            "granted_class": "emergency_override",
            "valid_from_s": span[0], "valid_to_s": span[1],
            "instrument_ref": "DIR-500",
        })
    ent["overrides"] = rows


def _build_backlog(ent, rng):
    rows = []
    for m in MISSIONS:
        for p in PERIODS:
            for r in range(1, 9):
                rows.append({
                    "mission_id": m, "period_id": p, "report_seq": r,
                    "report_state": "superseded" if r < 8 else "current",
                    "backlog_kib": rng.between(50, 600) * 1024,
                    "reported_at_s": T0 + PERIODS.index(p) * PERIOD_S + r * 3600,
                })
    for r in rows:
        if r["mission_id"] == MISSIONS[5] and r["period_id"] == "P3" and r["report_seq"] == 8:
            r["backlog_kib"] = 0
    ent["backlog_rows"] = rows


def _build_delivery(ent, rng):
    rows = []
    for c in ent["contacts"]:
        rows.append({
            "contact_id": c["contact_id"],
            "reported_kib": rng.between(0, 240) * 1024,
            "reporting_system": rng.pick(["gsops", "flightops", "netops"]),
            "report_seq": rng.between(1, 4),
            "reported_at_s": c["scheduled_end_s"] + rng.between(60, 7200),
        })
    ent["delivery_rows"] = rows


def _build_prior(ent, rng):
    rows = []
    for c in ent["contracts"]:
        for cls in ["telemetry", "payload", "housekeeping"]:
            for b in range(1, 4):
                rows.append({
                    "contract_id": c["contract_id"], "bucket_class": cls,
                    "bucket_seq": b,
                    "unsettled_kib": rng.between(0, 40) * 1024,
                    "bucket_state": "open" if b == 3 else "closed",
                })
    ent["prior_rows"] = rows


def _build_outages(ent, rng):
    """Claims are raised against real passes, because an outage the operator
    noticed is an outage that fell on a pass it had scheduled."""
    by_mission = {}
    for c in ent["contacts"]:
        uid = None
        for a in ent["antennas"]:
            if (a["station_id"] == c["station_id"]
                    and a["local_label"] == c["aperture_label"]):
                uid = a["antenna_uid"]
                break
        if uid is None:
            continue
        pi = (c["scheduled_start_s"] - T0) // PERIOD_S
        if pi < 0 or pi >= len(PERIODS):
            continue
        by_mission.setdefault((_mission_of(ent, c), PERIODS[pi]), []).append((c, uid))
    rows = []
    for m in MISSIONS:
        for p in PERIODS:
            pool = by_mission.get((m, p), [])
            for k in range(4):
                if k < 3 and pool:
                    c, uid = pool[rng.below(len(pool))]
                    span = c["scheduled_end_s"] - c["scheduled_start_s"]
                    lead = rng.between(0, 600)
                    start = c["scheduled_start_s"] - lead
                    stop = start + lead + (span if span > 0 else 1800) + rng.between(0, 900)
                    status = "accepted" if k < 2 else rng.pick(OUTAGE_STATUS)
                else:
                    a = rng.pick(ent["antennas"])
                    uid = a["antenna_uid"]
                    start = T0 + PERIODS.index(p) * PERIOD_S + rng.between(1, 12) * DAY_S
                    stop = start + rng.between(1, 8) * 1800
                    status = rng.pick(OUTAGE_STATUS)
                rows.append({
                    "claim_id": "OC-" + format(len(rows) + 1, "05d"),
                    "mission_id": m, "antenna_uid": uid,
                    "period_id": p, "claim_from_s": start,
                    "claim_to_s": stop, "claim_status": status,
                    "claim_class": rng.pick(["site_power", "feed_failure",
                                             "network_partition"]),
                })
    ent["outages"] = rows


def _mission_of(ent, c):
    for row in ent["alias"]:
        if (row["presentation_id"] == c["presentation_id"]
                and row["valid_from_s"] <= c["scheduled_start_s"] < row["valid_to_s"]):
            return row["mission_id"]
    return MISSIONS[0]

# ---------------------------------------------------------------------------
# The shipped specification. Every rule the graded cases exercise is written
# out here in full. Nothing is redacted; the difficulty is the breadth and the
# interaction of the rules, never a hidden one.
# ---------------------------------------------------------------------------
DATA_MOUNT = "/" + "app/data"
OUT_MOUNT = "/" + "app/out"


def doc_readme_first():
    return NL.join([
        "GROUNDLINK month end settlement, working papers",
        "",
        "This directory is the month end settlement snapshot for a satellite",
        "operator that flies several missions through a shared ground segment.",
        "Different systems recorded different parts of the same passes, so the",
        "papers disagree in places. The settlement is the act of deciding which",
        "record binds, in what order, and what each mission and each station is",
        "owed at the end of it.",
        "",
        "Where to start. Read pipeline_contract_overview.md first. It names the",
        "fourteen stages and says which document owns each one. The stage",
        "documents are spec_stage_s01 through spec_stage_s14 and they are the",
        "binding text. interval_and_tiebreak_notes.md, rounding_and_precision.yml",
        "and ordering_dependencies.yaml hold the rules that apply at every stage",
        "rather than at one of them.",
        "",
        "What the numbers are. Time is integer seconds. Volume is integer KiB.",
        "Rates are integer milli KiB per second and divide down by the scale in",
        "unit_scaling_rules.json. Credits are integer milli credits. No stage",
        "needs floating point and no stage is permitted to use it.",
        "",
        "What is not here. There is no settled answer anywhere in these papers.",
        "The registers are histories, the amendments are logs, and several files",
        "are superseded by later ones. data_lineage.md says which is which.",
        "known_traps_and_footguns.md lists the readings that look right and are",
        "wrong, with the stage each one belongs to.",
        "",
        "Three numbers you will need live only in the harder documents. The per",
        "contact cap and the aperture period budget live in the workbook. The",
        "commit lead per station and the outage qualifying floor live in the",
        "operations memo. The precedence exception lives in the directive.",
        "",
        "corpus_coverage_sentinel.md says plainly which mechanisms this",
        "particular month leaves no trace of. Read it before you conclude that a",
        "rule does not matter because you saw no example of it.",
    ]) + NL


def doc_overview():
    return NL.join([
        "# pipeline contract overview",
        "",
        "The settlement is one chain. Each stage freezes a value that the next",
        "stage consumes, and no stage may be reordered against the edges in",
        "ordering_dependencies.yaml.",
        "",
        "| stage | name | owns |",
        "| --- | --- | --- |",
        "| S01 | identity resolution | spec_stage_s01_identity_resolution.md |",
        "| S02 | availability construction | spec_stage_s02_availability_construction.md |",
        "| S03 | pass admission | spec_stage_s03_pass_admission.md |",
        "| S04 | interval clipping | spec_stage_s04_interval_clipping.md |",
        "| S05 | capacity derivation | spec_stage_s05_capacity_derivation.md |",
        "| S06 | precedence and commit | spec_stage_s06_precedence_and_commit.md |",
        "| S07 | contention resolution | spec_stage_s07_contention_resolution.md |",
        "| S08 | entitlement merge | spec_stage_s08_entitlement_merge.md |",
        "| S09 | deliverable volume | spec_stage_s09_deliverable_volume.md |",
        "| S10 | transmission accounting | spec_stage_s10_transmission_accounting.md |",
        "| S11 | utilisation basis | spec_stage_s11_utilisation_basis.md |",
        "| S12 | settlement aggregation | spec_stage_s12_settlement_aggregation.md |",
        "| S13 | credit and debit | spec_stage_s13_credit_and_debit.md |",
        "| S14 | reconciliation emission | spec_stage_s14_reconciliation_emission.md |",
        "",
        "## the spine",
        "",
        "The canonical contact ledger is the spine. It carries one row per pass",
        "per settlement period, and every artifact after S05 is a projection of",
        "it. A pass that is read wrong at S03 or S04 is wrong in the station",
        "statement, the mission statement, the compliance ledger and the credit",
        "ledger at the same time.",
        "",
        "## the two scarcities",
        "",
        "Antenna time is scarce twice over and the two scarcities are settled by",
        "different rules. S07 settles the clash of two passes that want the same",
        "aperture at the same instant, and it settles it by displacement: one",
        "pass keeps its whole eligible interval and the other keeps none of it.",
        "S09 settles the case where the passes that survived S07 want more volume",
        "in one accounting period than the aperture is contracted to carry, and it",
        "settles that by rationing the budget across them. A solution that folds",
        "the two together produces plausible totals and disagrees with every",
        "ledger below S07.",
        "",
        "## the two accountings",
        "",
        "Operational accounting and contractual accounting are separate and stay",
        "separate. An outage exemption at S13 changes what a mission is charged",
        "and never changes what an aperture was occupied for. S11 reads the",
        "resolved ledger and nothing else.",
        "",
        "## what a settlement run consumes",
        "",
        "A run reads " + DATA_MOUNT + " and writes " + OUT_MOUNT + ". It reads",
        "nothing else, it reaches no network, and it produces the same bytes",
        "every time it is given the same directory.",
    ]) + NL


def doc_s01():
    return NL.join([
        "# S01 identity resolution",
        "",
        "Three identities have to be settled before anything else can be read.",
        "",
        "## missions",
        "",
        "mission_register.csv is a revision history. One row per mission per",
        "register_rev. The binding row is the one whose register_state is",
        "current. There is exactly one current row per mission. Every other row",
        "is superseded and its priority_class is historical.",
        "",
        "The pass plan does not carry mission identifiers. It carries a",
        "presentation identifier, and mission_alias_crosswalk.csv maps that to a",
        "mission over a half open effective window. The binding row for a pass is",
        "the crosswalk row whose valid_from_s is at or before the pass",
        "scheduled_start_s and whose valid_to_s is strictly after it. The window",
        "that matters is the one containing the scheduled start of the pass, not",
        "the one containing the start of the settlement period.",
        "",
        "The crosswalk contains presentation identifiers that repeat across",
        "different effective windows. Two rows may carry the same",
        "presentation_id and resolve in different windows. A pass whose",
        "scheduled_start_s falls in no window for its presentation_id is",
        "unresolved and is rejected at S03 predicate one.",
        "",
        "## stations",
        "",
        "ground_segment_register.tsv is a facility register. It lists every",
        "element at every station, one row per element. Only the row whose",
        "element_class is accounting_site carries the station tz_offset_min that",
        "the accounting calendar is written against. Every other row carries zero",
        "in that column and means nothing by it.",
        "",
        "## apertures",
        "",
        "aperture_register.csv is a configuration history. One row per aperture",
        "per config_rev, and the binding row is the one whose config_state is",
        "current. The pass plan names an aperture by station_id and",
        "aperture_label together. The pair resolves against the current",
        "configuration rows only. A label that resolved under an older",
        "configuration and does not resolve under the current one is unknown, and",
        "the pass is rejected at S03 predicate two.",
        "",
        "## contracts",
        "",
        "A mission may hold more than one contract. settlement_audit_trace.db",
        "carries the contract identity, the mission it belongs to, its half open",
        "validity window and whether carry forward is enabled for it. The station",
        "scope of a contract is in reference_lookups.sqlite, table station_scope,",
        "one row per contract and station in scope.",
        "",
        "contract_terms_amendments.tsv is an amendment log, one row per contract",
        "per period per revision_seq. The settled terms for a contract period are",
        "the row with the highest revision_seq whose amendment_status is",
        "executed. A draft or withdrawn amendment binds nothing however late it",
        "sits in the file, and file order is not revision order.",
    ]) + NL


def doc_s02():
    return NL.join([
        "# S02 availability construction",
        "",
        "Availability is per aperture and is built once, before any pass is",
        "looked at.",
        "",
        "Start from aperture_service_windows.csv. Take only the rows whose",
        "service_state is in_service. Each row is a half open interval",
        "[effective_from_s, effective_to_s). Normalise the set: sort it, merge",
        "any two intervals that overlap or abut, and drop any interval of zero",
        "length.",
        "",
        "Subtract maintenance_dockets.csv for that aperture. Each docket is the",
        "half open interval [start_s, end_s).",
        "",
        "Subtract blackout_advisories.psv for the station the aperture belongs",
        "to. Each advisory is the half open interval [start_s, end_s). A blackout",
        "applies to every aperture at the station.",
        "",
        "The result is the availability set of the aperture: a sorted list of",
        "disjoint half open intervals. Subtraction is exact interval arithmetic",
        "on integer seconds. A cut that lands exactly on an edge removes nothing:",
        "a docket [b, c) does not touch an availability interval [a, b).",
        "",
        "An aperture whose service_state is withdrawn for a stretch contributes",
        "no availability over that stretch. An aperture that is withdrawn for a",
        "whole settlement period has an empty availability set in that period,",
        "which is what produces an empty utilisation denominator at S11.",
        "",
        "## the accounting period window",
        "",
        "station_accounting_calendar.csv carries one row per station per period",
        "per accounting day. The station local accounting period is the interval",
        "from the smallest local_open_s of its rows to the largest local_close_s",
        "of its rows, for that station and that period, and it is half open. The",
        "period windows of a station are contiguous and do not overlap.",
        "",
        "Because the offsets differ by station, the same instant sits in P1 at one",
        "station and in P2 at another. Every period question in this pipeline is",
        "asked against the calendar of the station that owns the aperture.",
    ]) + NL


def doc_s03():
    return NL.join([
        "# S03 pass admission",
        "",
        "Each row of pass_plan_of_record.csv is tested against eight predicates",
        "in the order below. The first predicate that fails decides the",
        "rejection, and the later predicates are not evaluated. The recorded",
        "predicate_index is the one based position of the failing predicate.",
        "",
        "| index | code | predicate |",
        "| --- | --- | --- |",
        "| 1 | E01 | the presentation_id resolves to a mission at scheduled_start_s |",
        "| 2 | E02 | station_id with aperture_label resolves to a current aperture |",
        "| 3 | E03 | the station lies in the scope of at least one contract of the mission that is valid at scheduled_start_s |",
        "| 4 | E04 | the mission campaign phase covering scheduled_start_s is not a standdown |",
        "| 5 | E05 | no effective cancellation lands strictly before the commit boundary |",
        "| 6 | E06 | the journal carries an operational event for the pass |",
        "| 7 | E07 | the event_status is nominal or partial |",
        "| 8 | E08 | the clipped eligible interval carries seconds, or the pass is zero length and its instant is available |",
        "",
        "## contract validity and scope",
        "",
        "A contract is valid at an instant when valid_from_s is at or before it",
        "and valid_to_s is strictly after it. The contracts of a pass are every",
        "contract of the pass mission that is valid at scheduled_start_s and",
        "whose station_scope contains the station of the pass. If that set is",
        "empty the pass fails predicate three.",
        "",
        "## campaign phase",
        "",
        "campaign_schedule.xml carries one phase element per mission per",
        "phase_seq, each a half open interval [phase_from_s, phase_to_s). The",
        "phase of a pass is the one containing scheduled_start_s. A pass in a",
        "standdown phase fails predicate four. routine, intensive and",
        "commissioning phases all admit.",
        "",
        "## the commit boundary",
        "",
        "The commit boundary of a pass is its scheduled_start_s less the commit",
        "lead of its station. The commit lead is published per station in",
        "network_operations_memo.pdf and appears in no other file.",
        "",
        "## cancellations",
        "",
        "cancellation_notices.csv carries one row per notice. Several notices may",
        "name the same pass. Order the notices of a pass by issued_seq. The",
        "binding notice is the last one whose notice_state is effective. A pass",
        "with no effective notice was never cancelled. A rescinded notice binds",
        "nothing, including when it is the last notice by issued_seq.",
        "",
        "A binding notice whose effective_s is strictly before the commit",
        "boundary rejects the pass at predicate five. A binding notice whose",
        "effective_s is at or after the commit boundary does not reject it: the",
        "pass stays admitted and carries late_cancel set to one. A notice landing",
        "exactly on the commit boundary is a late cancellation, not a rejection.",
        "",
        "A cancelled pass is rejected whether or not the journal recorded an",
        "operational event for it. The presence of an event resurrects nothing.",
        "",
        "## the operational event",
        "",
        "contact_event_journal.ndjson carries at most one event per pass. A pass",
        "with no event fails predicate six. An event whose event_status is",
        "aborted or no_show fails predicate seven.",
        "",
        "## the reject ledger",
        "",
        "Every rejected pass is written to the rejected ledger once, with its",
        "code, its reason and its predicate_index. A rejected pass appears in no",
        "later ledger.",
    ]) + NL


def doc_s04():
    return NL.join([
        "# S04 interval clipping",
        "",
        "Every interval in this pipeline is half open. [a, b) contains a and does",
        "not contain b. Two intervals that share only an endpoint do not overlap.",
        "An interval where b equals a is legal, has zero length and carries no",
        "capacity.",
        "",
        "## the base interval",
        "",
        "The base interval of a pass is [scheduled_start_s, scheduled_end_s).",
        "",
        "When the operational event carries event_status partial, the base",
        "interval is intersected with [actual_start_s, actual_end_s) from the",
        "journal. When the event is nominal, the journal times are ignored and the",
        "scheduled interval stands even if the journal reports something else.",
        "",
        "## the eligible interval set",
        "",
        "The eligible set of a pass is the base interval intersected with the",
        "availability set of its aperture from S02. It is a sorted list of",
        "disjoint half open intervals and it may have more than one member,",
        "because a maintenance docket in the middle of a pass splits it.",
        "",
        "## the accounting split",
        "",
        "The eligible set is then split at the station local accounting period",
        "boundaries from S02. Each piece belongs to exactly one settlement",
        "period, and a pass that straddles a boundary settles in both, as two",
        "rows of the canonical ledger sharing one contact_id.",
        "",
        "eligible_seconds of a canonical row is the total length of that row",
        "pieces. A pass that produces no piece in a period produces no row in",
        "that period.",
        "",
        "## the zero length pass",
        "",
        "A pass whose scheduled_end_s equals its scheduled_start_s is admitted",
        "when that instant lies inside an availability interval of its aperture,",
        "and rejected at predicate eight when it does not. It produces one",
        "canonical row, in the period whose window contains the instant, with",
        "eligible_seconds zero. It contends with nothing, because a zero length",
        "interval intersects nothing.",
        "",
        "## normalized_contact_intervals",
        "",
        "One row per eligible piece, ordered by contact_id, then period_id, then",
        "segment_start_s. A canonical row with no pieces, which is the zero",
        "length case, contributes one row whose start and end are both the pass",
        "scheduled_start_s and whose segment_seconds is zero.",
    ]) + NL


def doc_s05():
    return NL.join([
        "# S05 capacity derivation",
        "",
        "Capacity is derived per canonical row, which is per pass per period.",
        "",
        "## the rate schedule",
        "",
        "rate_schedule_effective.psv carries one row per aperture per",
        "schedule_rev, each a half open interval [effective_from_s,",
        "effective_to_s) with a rate in milli KiB per second. The rows of an",
        "aperture tile the campaign without gap or overlap.",
        "",
        "legacy_flat_rate_table.csv is retired. Its table_state says so and its",
        "retired_on_s predates the campaign. It binds no capacity. It is read at",
        "S14 for one purpose only, which is the discrepancy report.",
        "",
        "## the rate pieces",
        "",
        "Split every eligible piece of the row at every rate schedule edge of its",
        "aperture that falls strictly inside it. The result is the rate piece",
        "list: a set of half open intervals each of which lies inside exactly one",
        "rate row. The rate of a piece is the rate of the row whose interval",
        "contains the piece start.",
        "",
        "A rate edge that lands exactly on a pass boundary splits nothing,",
        "because the edge is not strictly inside the piece.",
        "",
        "## the per piece floor",
        "",
        "For each rate piece:",
        "",
        "    piece_kib = (piece_seconds * rate_mkib_per_s) // rate_scale_divisor",
        "",
        "rate_scale_divisor is in unit_scaling_rules.json. The division is a",
        "floor and it is applied to every piece separately. raw_capacity_kib is",
        "the sum of the piece values.",
        "",
        "Summing the seconds first and dividing once is a different number and is",
        "wrong. So is summing the products and dividing once. The floor belongs to",
        "the piece, not to the row. rate_piece_count records how many pieces the",
        "row was split into, so the split is visible in the ledger.",
        "",
        "## the per contact cap",
        "",
        "The per contact cap is per aperture per period and lives only in",
        "aperture_contract_workbook.xlsx. workbook_sheet_selection.json names the",
        "binding sheet: the sheet whose sheet_status equals binding_status, and",
        "where more than one qualifies, the highest sheet_revision. The other",
        "sheets are superseded or draft and bind nothing.",
        "",
        "    usable_capacity_kib = min(raw_capacity_kib, per_contact_cap_kib)",
        "",
        "The cap is applied to the canonical row before any aggregation of any",
        "kind. Applying it to a mission total, a station total or an aperture",
        "total produces a larger number and is wrong.",
        "",
        "A row whose raw capacity exceeds its cap is written to",
        "capacity_cap_exceptions with the clipped amount. A row whose raw",
        "capacity equals its cap exactly is not an exception.",
    ]) + NL


def doc_s06():
    return NL.join([
        "# S06 precedence and commit",
        "",
        "## the registered class",
        "",
        "The registered priority class of a mission is on its current",
        "mission_register.csv row. reference_lookups.sqlite table priority_rank",
        "gives the rank value of each class. A lower rank value outranks a higher",
        "one.",
        "",
        "## overrides",
        "",
        "precedence_override_register.jsonl carries one row per override. An",
        "override applies to a canonical row when it names the same mission, it",
        "names the same aperture_uid, and its half open window [valid_from_s,",
        "valid_to_s) contains the pass scheduled_start_s. An override that names a",
        "different aperture of the same station does not apply.",
        "",
        "Where more than one override applies, the one granting the strongest",
        "class wins, and where two grant the same class the lower override_id",
        "wins.",
        "",
        "An override may only raise a mission. When the granted class is weaker",
        "than the registered class, the registered class stands. This is clause",
        "three of precedence_directive.docx.",
        "",
        "effective_class is the resulting class and effective_rank its rank.",
        "",
        "## the commit boundary and protection",
        "",
        "The commit boundary is scheduled_start_s less the station commit lead",
        "from network_operations_memo.pdf.",
        "",
        "A canonical row is protected when both hold:",
        "",
        "  the operational event event_recorded_s is at or before the commit",
        "  boundary, and",
        "",
        "  the operator who signed the event holds a grade that carries commit",
        "  evidence.",
        "",
        "operator_roster.tsv gives the authority_grade of every operator code.",
        "reference_lookups.sqlite table grade_authority says which grades carry",
        "commit evidence. An event signed by a grade that does not carry it is no",
        "evidence of commitment however early it was recorded.",
        "",
        "An event recorded exactly on the commit boundary is protection.",
        "",
        "## why protection is not a priority",
        "",
        "Clause two of precedence_directive.docx states the exception that makes",
        "the whole of S07 state dependent: a protected pass outranks every",
        "unprotected pass whatever their classes say. An emergency override pass",
        "that was never committed loses its aperture to an ordinary priority pass",
        "that was. Protection is the first key of the ordering, not a tie break",
        "inside a class.",
    ]) + NL


def doc_s07():
    return NL.join([
        "# S07 contention resolution",
        "",
        "Contention is settled per aperture per settlement period, over the",
        "canonical rows that survived S03.",
        "",
        "## the ordering",
        "",
        "Order the rows of an aperture period by, in this order:",
        "",
        "  1. protection, protected before unprotected",
        "  2. effective_rank ascending",
        "  3. commit_boundary_s ascending",
        "  4. remaining contractual obligation descending",
        "  5. contact_id ascending",
        "",
        "The fifth key is total, so the order is total and no two runs disagree.",
        "",
        "remaining contractual obligation is the obligation_kib of the settled",
        "terms of the period, taken over the contracts of the pass from S03, and",
        "where the pass has more than one such contract it is the largest of",
        "them. It is read at the opening of the period and is not reduced as",
        "passes settle. This is the one edge that runs backwards, from S08 into",
        "S07, and ordering_dependencies.yaml names it.",
        "",
        "## the greedy walk",
        "",
        "Walk the ordered rows once. Keep a list of the rows already accepted for",
        "this aperture period, initially empty. For each row in turn:",
        "",
        "  if its eligible set intersects the eligible set of any accepted row by",
        "  one second or more, the row is displaced, and the first accepted row",
        "  it intersects in acceptance order is recorded as its displaced_by;",
        "",
        "  otherwise the row is accepted and joins the list.",
        "",
        "A displaced row keeps none of its interval. Displacement is whole, not",
        "partial. Its allocated and accepted volumes are zero and it appears in",
        "no delivery ledger.",
        "",
        "Two rows that abut, where one ends exactly where the other begins, do",
        "not intersect and both are accepted. A zero length row intersects",
        "nothing and is always accepted.",
        "",
        "## contention groups",
        "",
        "contention_groups is a report, not a decision. The groups are the",
        "connected components of the intersection graph over the rows of the",
        "aperture period, so a row that intersects nothing forms a group of one",
        "and is still listed. Components are ordered by their smallest",
        "contact_id. group_seq counts from one inside each aperture period.",
        "",
        "The greedy walk is over the whole aperture period in the published",
        "order, not over one component at a time. A row can be displaced by a row",
        "in its component and by no other.",
        "",
        "## the tie report",
        "",
        "tie_resolution_report carries one row for each pair of intersecting rows",
        "in one aperture period, naming which key decided between them:",
        "",
        "  1 protection, 2 effective_rank, 3 commit_boundary_s,",
        "  4 remaining obligation, 5 contact_id",
        "",
        "contact_id_kept is the row that came first in the published order and",
        "contact_id_yielded the one that came second, whichever of them the",
        "greedy walk went on to accept. Pairs that do not intersect are not",
        "reported.",
    ]) + NL


def doc_s08():
    return NL.join([
        "# S08 entitlement merge",
        "",
        "Entitlement is per contract per settlement period, and it carries state",
        "from one period into the next.",
        "",
        "## the opening carry",
        "",
        "prior_period_settlement.json holds the opening carry buckets, which are",
        "the state at the start of P1 and nothing later. Only buckets whose",
        "bucket_state is open carry. Closed buckets are already settled and carry",
        "nothing. The opening carry source of a contract is the sum of the",
        "unsettled_kib of its open buckets.",
        "",
        "The carry source for P2 is what P1 left unconsumed, and the carry source",
        "for P3 is what P2 left unconsumed. Those two are computed by this",
        "pipeline and appear in no shipped file.",
        "",
        "## the carry in",
        "",
        "For a contract period, with carry_cap_kib from the settled terms:",
        "",
        "  when carry forward is disabled, either on the settled terms or in",
        "  settlement_audit_trace.db, carry_in_kib is zero and the whole carry",
        "  source is forfeited;",
        "",
        "  when the contract has expired, meaning its valid_to_s is at or before",
        "  the start of the period, carry_in_kib is zero and the whole carry",
        "  source is forfeited;",
        "",
        "  otherwise carry_in_kib is the carry source capped at carry_cap_kib,",
        "  and the amount above the cap is forfeited.",
        "",
        "A carry source that equals the cap exactly carries in whole and forfeits",
        "nothing. The period start used for the expiry test is the earliest",
        "station local period open across the network, so one contract expires on",
        "the same instant everywhere.",
        "",
        "## the allowance",
        "",
        "    available_allowance_kib = carry_in_kib + entitlement_kib",
        "",
        "Carry is consumed before new entitlement. Every acceptance at S10 draws",
        "from the carry remainder first and only then from the new entitlement",
        "remainder, and the split is reported per pass.",
        "",
        "## the carry out",
        "",
        "carry_out_kib of a contract period is what the allowance had left when",
        "the period closed, which is the carry remainder plus the new entitlement",
        "remainder. It becomes the carry source of the next period, where it is",
        "capped again against that period carry_cap_kib.",
        "",
        "A contract with zero entitlement and zero carry cap has zero allowance",
        "and accepts nothing, however much capacity its passes carry.",
    ]) + NL


def doc_s09():
    return NL.join([
        "# S09 deliverable volume",
        "",
        "S09 turns the capacity of the surviving passes into an allocation",
        "against the aperture budget. It runs per aperture per settlement period,",
        "over the rows that S07 accepted.",
        "",
        "## demand",
        "",
        "    demand_kib = min(usable_capacity_kib, opening_backlog_kib)",
        "",
        "opening_backlog_kib is the backlog of the mission for the period, taken",
        "from onboard_backlog_reports.csv. Several reports exist per mission",
        "period; the binding one is the report whose report_state is current, and",
        "where more than one is current the highest report_seq. Superseded",
        "reports bind nothing.",
        "",
        "The backlog used here is the opening figure of the period, the same",
        "value for every pass of that mission in that period. The running backlog",
        "that S10 keeps is not used at S09. Using the running figure makes the",
        "ration depend on the order the apertures happen to be visited, and it is",
        "wrong.",
        "",
        "## the budget test",
        "",
        "The aperture period budget lives only in the binding sheet of",
        "aperture_contract_workbook.xlsx, column period_budget_kib.",
        "",
        "Let the accepted rows of the aperture period be ordered by the S07",
        "ordering, and let their demands be d1 to dn. When the sum of the demands",
        "is at or below the budget, every row is allocated its whole demand and",
        "the ration does not run. No trace row is written for that aperture",
        "period.",
        "",
        "## the ration",
        "",
        "When the sum of the demands exceeds the budget, the budget is rationed",
        "by the damped integer procedure in rationing_iteration_notes.md. That",
        "document is binding and carries a worked example.",
        "",
        "The allocation of a row is written to allocated_kib. The pass trace is",
        "written to rationing_pass_trace, one row per pass of the procedure per",
        "aperture period that ran it.",
    ]) + NL


def doc_ration():
    return NL.join([
        "# the damped ration",
        "",
        "This document is binding. It defines the only procedure by which an",
        "over subscribed aperture period budget is divided.",
        "",
        "## why it is iterative",
        "",
        "A single proportional split hands volume to passes that cannot use it,",
        "because a pass never takes more than its own demand. The surplus has to",
        "come back and be offered to the passes that can. The operator settles",
        "this by a fixed number of offer rounds rather than by running to",
        "convergence, so that a settlement run has a bounded cost and two runs",
        "of the same month agree to the unit.",
        "",
        "## the pass budget",
        "",
        "The number of passes is derived from the instance:",
        "",
        "    passes = min(ceiling, base + n)",
        "",
        "n is the number of accepted rows in the aperture period. base and",
        "ceiling are published in network_operations_memo.pdf as",
        "ration-pass-budget-base and ration-pass-budget-ceiling.",
        "",
        "The procedure stops when it has run that many passes. It does not stop",
        "early because the numbers settled, and it does not run on because they",
        "have not. A run that stops at convergence carries on offering after",
        "the published rounds are spent. On most over subscribed aperture",
        "periods it reaches a different allocation, and the residual step masks",
        "the difference on the rest, so a settlement built that way disagrees",
        "with this one and is wrong.",
        "",
        "## the state",
        "",
        "Each row i carries an allocation x_i, an integer number of KiB, and a",
        "pinned flag. Every x_i starts at zero and every row starts unpinned.",
        "",
        "## one pass",
        "",
        "For each pass from 1 to the pass budget, in order:",
        "",
        "  1. pinned_mass is the sum of the demands of the pinned rows.",
        "",
        "  2. the active rows are the rows that are not pinned. When there are",
        "     none, the pass is recorded with an active count of zero and a",
        "     share of zero and nothing changes.",
        "",
        "  3. room is the budget less pinned_mass. share is room floor divided",
        "     by the number of active rows, and share is zero when room is zero",
        "     or below.",
        "",
        "  4. for each active row i the target is min(demand_i, share), the step",
        "     is target less x_i, and the movement is",
        "",
        "         delta = (step * theta_num) // theta_den",
        "",
        "     except that when the step is positive and that expression comes",
        "     out below one, the movement is one. A positive step always moves",
        "     the row by at least one unit. Then x_i becomes x_i plus delta.",
        "",
        "     theta_num and theta_den are ration_damping_numerator and",
        "     ration_damping_denominator in unit_scaling_rules.json.",
        "",
        "     The minimum of one unit is what lets a row reach its demand at",
        "     all. Without it the damped step floors to zero as soon as the gap",
        "     falls below theta_den over theta_num, the row stalls one unit",
        "     short of its target, the pinning that would have raised the share",
        "     for the later passes mostly stops happening, and the surplus of",
        "     the rows that could not use their share reaches the rows that",
        "     could through the residual instead. A procedure without it",
        "     reaches a different allocation and is wrong.",
        "",
        "  5. after every active row has moved, any active row whose x_i has",
        "     reached or passed its demand is set to its demand exactly and",
        "     pinned.",
        "",
        "Every x_i is an integer at the end of every pass. The next pass starts",
        "from those integers. There is no unrounded shadow value carried between",
        "passes.",
        "",
        "## why the share never falls",
        "",
        "A row is pinned only when its demand is at or below the share it was",
        "offered, so removing it from the active set removes at most a share",
        "worth of room. The share of the next pass is therefore at or above the",
        "share of this one. The step is consequently never negative, the",
        "movement is never negative, and the sum of the allocations never",
        "exceeds the budget.",
        "",
        "## the residual",
        "",
        "After the last pass, residual is the budget less the sum of the x_i,",
        "and by the paragraph above it is at or above zero.",
        "",
        "Walk the rows in the S07 ordering and give each row",
        "min(residual, demand_i - x_i), stopping when the residual reaches zero.",
        "A row already at its demand takes nothing. When the residual is zero at",
        "the outset, nothing happens.",
        "",
        "## the trace",
        "",
        "One row per pass per aperture period that ran the procedure, carrying",
        "pass_seq, active_count, share_kib, the sum of the x_i after the pass as",
        "allocated_kib, the budget and the demand total. The residual step is",
        "not a pass and is not traced.",
        "",
        "## worked example",
        "",
        "Four rows with demands 500, 500, 100 and 40, a budget of 700, theta 3",
        "over 4, base 2 and ceiling 12, so the pass budget is 6.",
        "",
        "    pass 1  pinned_mass   0  active 4  share 175",
        "            targets 175 175 100  40",
        "            x       131 131  75  30",
        "    pass 2  pinned_mass   0  active 4  share 175",
        "            targets 175 175 100  40",
        "            x       164 164  93  37",
        "    pass 3  pinned_mass   0  active 4  share 175",
        "            x       172 172  98  39",
        "    pass 4  pinned_mass   0  active 4  share 175",
        "            steps     3   3   2   1, movements 2 2 1 1",
        "            x       174 174  99  40   row four reaches 40 and pins",
        "    pass 5  pinned_mass  40  active 3  share 220",
        "            targets 220 220 100",
        "            x       208 208 100        row three reaches 100 and pins",
        "    pass 6  pinned_mass 140  active 2  share 280",
        "            targets 280 280",
        "            x       262 262",
        "    residual 700 less 664 is 36",
        "            row one takes min(36, 238) which is 36, residual 0",
        "    allocation 298 262 100 40",
        "",
        "Pass four is the one that separates a correct procedure from a",
        "plausible one. Row four has a step of one, the damped expression gives",
        "zero, the minimum of one unit carries it to its demand of 40, and the",
        "pinning that follows raises the share for every later pass.",
        "",
        "The example is arithmetic on invented numbers and is not a row of any",
        "shipped file. Reproduce it before running the pipeline; a procedure that",
        "reproduces it reproduces the settlement.",
    ]) + NL


def doc_s10():
    return NL.join([
        "# S10 transmission accounting",
        "",
        "S10 decides what the allocation of S09 actually delivers, and it is the",
        "only stage that keeps running state across apertures.",
        "",
        "## the resolution order",
        "",
        "Within a settlement period, the accepted rows are visited in this order:",
        "",
        "  1. station_id ascending",
        "  2. antenna_uid ascending",
        "  3. the S07 ordering within the aperture",
        "",
        "The periods themselves are visited P1, then P2, then P3, because the",
        "carry out of one is the carry source of the next.",
        "",
        "## the contract of a row",
        "",
        "A pass may sit under more than one contract of its mission. The binding",
        "contract for the row is, among the contracts of the pass that have",
        "settled terms in the period, the one with the largest obligation_kib,",
        "and where two are equal the lower contract_id. A mission that holds two",
        "contracts competes against itself through this rule: both draw on their",
        "own allowance and the row is charged to one of them only.",
        "",
        "## the acceptance",
        "",
        "    accepted_kib = min(allocated_kib, backlog_remaining, allowance_remaining)",
        "",
        "backlog_remaining is the running backlog of the mission for the period.",
        "It opens at the binding backlog report figure and is reduced by the",
        "accepted volume of each row as it settles, never by the demand and never",
        "by the allocation.",
        "",
        "allowance_remaining is the carry remainder plus the new entitlement",
        "remainder of the binding contract for the period.",
        "",
        "    from_carry_kib = min(accepted_kib, carry_remainder)",
        "    from_new_kib   = accepted_kib - from_carry_kib",
        "",
        "and the two remainders are reduced by those two amounts.",
        "",
        "## the derived volumes",
        "",
        "    deferred_kib        = demand_kib - accepted_kib",
        "    unused_capacity_kib = usable_capacity_kib - accepted_kib",
        "",
        "Deferred volume is measured against demand and unused capacity against",
        "usable capacity, so the two differ whenever the backlog held demand",
        "below capacity. Both are recorded.",
        "",
        "## downlink reports are not authoritative",
        "",
        "downlink_reports.csv is what the reporting systems said moved. It is not",
        "an input to any accepted figure. A report larger than the physical",
        "capacity of its pass is possible and changes nothing. Reports are read at",
        "S14 for the discrepancy report only.",
    ]) + NL


def doc_s11():
    return NL.join([
        "# S11 utilisation basis",
        "",
        "Utilisation is an operational measure and it is computed from the",
        "resolved ledger.",
        "",
        "## the numerator",
        "",
        "The occupied seconds of an aperture period are the sum of",
        "eligible_seconds over the canonical rows that S07 accepted for that",
        "aperture and period. Rejected passes contribute nothing. Displaced",
        "passes contribute nothing, because the aperture was not occupied by",
        "them.",
        "",
        "Computing the numerator from pass_plan_of_record.csv gives a larger and",
        "plausible number that agrees with no ledger in this settlement. So does",
        "computing it from the admitted rows before S07.",
        "",
        "## the denominator",
        "",
        "The available seconds of an aperture period are the length of its",
        "availability set from S02 intersected with the station local accounting",
        "period from the calendar. The denominator is physical availability. It",
        "is not reduced because a contract could not pay for the time, and it is",
        "not reduced because a budget ran out.",
        "",
        "## the ratio",
        "",
        "    utilisation_bp = (occupied_seconds * 10000) // available_seconds",
        "",
        "The result is integer basis points and the division is a floor. When the",
        "denominator is zero the utilisation_bp is zero and denominator_state is",
        "empty. An aperture withdrawn from service for the whole period is the",
        "case that produces it. Any other denominator_state is populated.",
        "",
        "## stations",
        "",
        "A station numerator and denominator are the sums over its apertures,",
        "summed before the division rather than after. Averaging the aperture",
        "basis points gives a different number and is wrong.",
        "",
        "## what utilisation never sees",
        "",
        "An outage exemption at S13 does not restore utilisation. The aperture",
        "was idle and the ledger says so; the contract relief is a separate",
        "entry in a separate ledger. Nothing at S13 writes back into S11.",
    ]) + NL


def doc_s12():
    return NL.join([
        "# S12 settlement aggregation",
        "",
        "S12 is projection only. It introduces no new arithmetic beyond addition",
        "of values already frozen, and it reads the canonical ledger rather than",
        "any earlier file.",
        "",
        "## mission statements",
        "",
        "One row per mission per period, for every mission on the register and",
        "every period, including the pairs with no accepted pass. Those rows",
        "carry zeros rather than being omitted.",
        "",
        "won_pass_count is the number of accepted canonical rows. The seconds and",
        "volumes are sums over the same rows. net_mcr is the sum of net_mcr over",
        "the contracts of the mission for that period, from S13, so a mission",
        "with two contracts adds both.",
        "",
        "## station statements",
        "",
        "One row per station per period, for every station and period. The",
        "utilisation_bp column is the station figure from S11, carried across",
        "rather than recomputed.",
        "",
        "## ordering",
        "",
        "Mission rows are ordered by mission_id then by period. Station rows by",
        "station_id then by period. Period order is P1, P2, P3 throughout this",
        "pipeline and is never lexicographic on some other column.",
    ]) + NL


def doc_s13():
    return NL.join([
        "# S13 credit and debit",
        "",
        "Credits and debits are per contract per period, in integer milli",
        "credits. The three rates and the two carry restore terms live only in",
        "the credit_rates block of the binding workbook sheet.",
        "",
        "## the delivered figure",
        "",
        "delivered_kib of a contract period is the sum of accepted_kib over the",
        "accepted rows whose binding contract, from S10, is that contract.",
        "",
        "    shortfall_kib        = max(0, obligation_kib - delivered_kib)",
        "    unused_reserved_kib  = max(0, reserved_kib  - delivered_kib)",
        "",
        "## the outage test, which runs first",
        "",
        "outage_claims.psv carries one row per claim. Only claims whose",
        "claim_status is accepted count; rejected and withdrawn claims count for",
        "nothing.",
        "",
        "For the mission of the contract and the period in question, take every",
        "accepted claim. For each, sum the seconds by which its half open window",
        "[claim_from_s, claim_to_s) intersects the eligible sets of the accepted",
        "rows of that contract on the aperture the claim names. Total those",
        "seconds across the claims.",
        "",
        "When that total reaches the outage qualifying floor from",
        "network_operations_memo.pdf, the contract period is outage qualified.",
        "The floor is a floor: a total equal to it qualifies.",
        "",
        "A qualifying claim is an accepted claim whose own overlap total above",
        "is one second or more. An accepted claim that overlaps no accepted row",
        "of the contract contributes nothing to the test and is not a qualifying",
        "claim, so it takes no part in the pool below.",
        "",
        "## what qualification changes",
        "",
        "    exempt_kib = min(shortfall_kib, exempt_pool)",
        "",
        "exempt_pool is a sum taken claim by claim. Walk the qualifying",
        "claims in claim_id order, and for each of them add the deferred_kib of",
        "every accepted row of the contract that sits on the aperture that claim",
        "names, excluding any row whose late_cancel is one. A row on an aperture",
        "that two qualifying claims both name is added once for each of them, so",
        "the pool counts claim and row pairs rather than rows. A pass the",
        "operator cancelled after its commit boundary is the operator own doing",
        "and does not swell the pool.",
        "",
        "When the contract period is outage qualified:",
        "",
        "    shortfall_debit_mcr = 0",
        "    outage_credit_mcr   = (exempt_kib * outage_credit_mcr_per_mib) // credit_basis",
        "    carry_restore_kib   = min(carry_forfeit_kib,",
        "                              (exempt_kib * restore_num) // restore_den)",
        "",
        "The shortfall is waived, not reduced. A pass that looked responsible for",
        "a shortfall at S10 can be reclassified here, and the reclassification",
        "changes the settlement and nothing operational.",
        "",
        "When it is not qualified:",
        "",
        "    shortfall_debit_mcr = (shortfall_kib * shortfall_debit_mcr_per_mib) // credit_basis",
        "    outage_credit_mcr   = 0",
        "    carry_restore_kib   = 0",
        "",
        "## the unused reserved credit, which is always paid",
        "",
        "    unused_credit_mcr = (unused_reserved_kib * unused_reserved_credit_mcr_per_mib) // credit_basis",
        "",
        "credit_basis is credit_basis_kib_per_mib in unit_scaling_rules.json.",
        "Every one of these divisions is a floor applied once, at this stage,",
        "to the quantity named.",
        "",
        "    net_mcr = unused_credit_mcr + outage_credit_mcr - shortfall_debit_mcr",
        "",
        "## the compliance state",
        "",
        "met when the shortfall is zero. exempt when it is positive and the",
        "contract period is outage qualified. short otherwise.",
        "",
        "## the outage ledger",
        "",
        "One row per contract period, whether or not it qualified, carrying the",
        "overlap total, the floor, the verdict, the exempt volume and the carry",
        "restored. A contract period with no claim at all carries zeros.",
    ]) + NL


def doc_s14():
    return NL.join([
        "# S14 reconciliation emission",
        "",
        "S14 writes the artifacts. It computes nothing that the earlier stages",
        "did not already freeze, except the three reports below.",
        "",
        "## the discrepancy report",
        "",
        "cross_source_discrepancy_report carries two families.",
        "",
        "The first compares the canonical ledger against downlink_reports.csv.",
        "For each pass with at least one accepted canonical row, the left value",
        "is the sum of its accepted_kib across periods and the right value is the",
        "reported_kib of its binding report, which is the report with the highest",
        "report_seq. Rows that agree are not reported. discrepancy_class is",
        "over_report when the report is larger and under_report when it is",
        "smaller. source_left is canonical_ledger and source_right is",
        "downlink_report. period_id is empty for this family because the",
        "comparison is over the whole pass.",
        "",
        "The second compares the effective rate schedule against",
        "legacy_flat_rate_table.csv. For each aperture, take the binding legacy",
        "row, which is the one with the highest table_rev. When its flat rate",
        "lies inside the closed band from the smallest to the largest effective",
        "rate of that aperture, nothing is reported. When it lies outside, the",
        "left value is the nearer end of the band, the right value is the flat",
        "rate, and discrepancy_class is retired_rate_outside_band. source_left",
        "is rate_schedule and source_right is legacy_flat_table.",
        "",
        "The four source slugs are written exactly as given here. They name the",
        "side of the comparison and are not the file names of the papers the",
        "sides were read from.",
        "",
        "Rows are ordered by source_left then subject_id.",
        "",
        "## the invariant report",
        "",
        "A fixed list of balance checks, each carrying a left value, a right",
        "value and whether they matched. The checks and their order are in",
        "output_schema_reference.md. all_balanced is one when every check",
        "matched.",
        "",
        "## the exception report",
        "",
         "One record per exception, drawn from the admission rejections, the",
         "capacity cap clippings, the displacements, the carry forfeits, the empty",
         "utilisation denominators and the late cancellations. Codes are in",
         "exception_code_dictionary.xml. Ordered by exception_class, then",
         "subject_id, then code, then the period the exception arose in, P1",
         "before P2 before P3. Two exceptions that share a class, a subject and",
         "a code always arose in different periods, so that fourth key settles",
         "every tie. The period is a sort key only and is not a field of the",
         "record.",
        "",
        "## the digest manifest",
        "",
        "stage_digest_manifest.json carries the count of core artifacts, the",
        "sha256 of each of them, and core_digest, which is the sha256 of the",
        "concatenation of the core artifact bytes in the order given by",
        "output_artifact_contract.md. The manifest is not part of the",
        "concatenation.",
    ]) + NL


def doc_intervals():
    return NL.join([
        "# interval and tie break notes",
        "",
        "These rules apply at every stage and are not restated in the stage",
        "documents.",
        "",
        "## half open everywhere",
        "",
        "Every interval in every shipped file is [start, end). The start instant",
        "belongs to the interval and the end instant does not. This holds for",
        "service windows, maintenance dockets, blackout advisories, rate schedule",
        "rows, alias crosswalk windows, contract validity, override windows,",
        "campaign phases, accounting days and outage claims.",
        "",
        "Consequences worth stating because they are easy to lose:",
        "",
        "  two intervals that share only an endpoint do not overlap;",
        "",
        "  a lookup for instant t takes the row where from <= t and t < to;",
        "",
        "  an interval of zero length contains no instant and overlaps nothing,",
        "  yet is a legal record;",
        "",
        "  subtracting [b, c) from [a, b) removes nothing.",
        "",
        "## comparisons that are inclusive on purpose",
        "",
        "Three comparisons in this pipeline are at or before rather than strictly",
        "before, and each is stated in its own stage document as well:",
        "",
        "  a cancellation effective exactly on the commit boundary is a late",
        "  cancellation and not a rejection;",
        "",
        "  an event recorded exactly on the commit boundary is protection;",
        "",
        "  an outage overlap total exactly equal to the qualifying floor",
        "  qualifies.",
        "",
        "## the ordering ladder",
        "",
        "The five key ordering of S07 is used in three places: to resolve",
        "contention, to order the rows a ration walks, and to order the residual",
        "distribution. It is one ladder and the same ladder each time.",
        "",
        "Level five, contact_id ascending, is a total order over the rows of an",
        "aperture period, so the ladder never falls through. Two rows of the same",
        "pass in different periods never contend, because their intervals lie in",
        "different period windows.",
        "",
        "## sort stability is not a rule",
        "",
        "Nothing in this settlement may depend on the order rows happen to sit in",
        "a file, on the order a directory listing returns, or on the stability of",
        "a sort. Every ordering that decides a value is published.",
    ]) + NL


def doc_traps():
    return NL.join([
        "# known traps and footguns",
        "",
        "Each entry names a reading that looks right, the reading that binds, and",
        "the stage that owns it. Nothing here is new law; every entry restates a",
        "rule from a stage document.",
        "",
        "1. S01. Taking the last mission_register.csv row for a mission rather",
        "   than the row whose register_state is current. The file is a history",
        "   and its last row is not its binding row.",
        "",
        "2. S01. Resolving a presentation identifier against the settlement",
        "   period rather than against the scheduled start of the pass. The",
        "   crosswalk changes mid campaign and the same identifier reappears in a",
        "   later window.",
        "",
        "3. S01. Reading tz_offset_min from any facility element row. Only the",
        "   accounting_site row carries it; the others carry zero.",
        "",
        "4. S01. Taking the last contract amendment by file order. The settled",
        "   row is the highest revision_seq whose amendment_status is executed,",
        "   and a superseded revision in this corpus may carry a larger or a",
        "   smaller obligation than the executed one, so the direction of the",
        "   disagreement is no guide to which row binds.",
        "",
        "5. S02. Subtracting maintenance as a closed interval, so a docket that",
        "   begins exactly when availability ends removes a second that was never",
        "   there.",
        "",
        "6. S02. Forgetting that a blackout advisory is a station fact and",
        "   applies to every aperture at that station.",
        "",
        "7. S03. Evaluating the admission predicates in a different order, so a",
        "   pass that fails two of them is recorded under the wrong code.",
        "",
        "8. S03. Treating a cancellation on the commit boundary as a rejection.",
        "   It is a late cancellation and the pass stays admitted.",
        "",
        "9. S03. Letting an operational event override a cancellation. It does",
        "   not.",
        "",
        "10. S03. Taking the last cancellation notice by issued_seq without",
        "    checking notice_state. The binding notice is the last effective one.",
        "",
        "11. S04. Using the journal times for a nominal event. Only a partial",
        "    event narrows the interval.",
        "",
        "12. S04. Settling a pass that straddles a station local period boundary",
        "    in one period. It settles in both, as two canonical rows.",
        "",
        "13. S05. Multiplying total eligible seconds by one blended rate. The",
        "    floor belongs to each rate piece and the pieces are summed after.",
        "",
        "14. S05. Applying the per contact cap to a mission or aperture total",
        "    rather than to each canonical row before aggregation.",
        "",
        "15. S05. Reading the cap or the budget from the superseded or the draft",
        "    workbook sheet. Only the binding sheet counts.",
        "",
        "16. S05. Using legacy_flat_rate_table.csv for capacity. It is retired",
        "    and is read only for the discrepancy report.",
        "",
        "17. S06. Treating protection as a tie break inside a priority class",
        "    rather than as the first ordering key. An uncommitted emergency",
        "    override pass loses to a committed ordinary pass.",
        "",
        "18. S06. Accepting an event signed by an operator whose grade carries no",
        "    commit evidence as proof of commitment.",
        "",
        "19. S06. Letting an override lower a mission below its registered class.",
        "",
        "20. S07. Displacing a pass partially. Displacement is whole.",
        "",
        "21. S07. Running the greedy walk inside each connected component rather",
        "    than once over the whole aperture period in the published order.",
        "",
        "22. S07. Reducing the remaining obligation as passes settle. It is read",
        "    once at the opening of the period.",
        "",
        "23. S08. Counting closed opening buckets toward the carry source.",
        "",
        "24. S08. Applying new entitlement before carry.",
        "",
        "25. S08. Carrying forward for an expired contract instead of forfeiting.",
        "",
        "26. S09. Using the running backlog rather than the opening backlog when",
        "    computing demand for the ration.",
        "",
        "27. S09. Running the ration to convergence rather than to the published",
        "    pass budget.",
        "",
        "28. S09. Applying the damping to the target rather than to the movement",
        "    from the current value.",
        "",
        "29. S09. Dropping the minimum movement of one unit, so every row stalls",
        "    one unit short of its target, nothing is ever pinned and the share",
        "    never rises.",
        "",
        "30. S09. Treating the pass budget as a maximum and stopping at the",
        "    first pass that moves nothing.",
        "",
        "31. S10. Reducing the running backlog by the demand or the allocation",
        "    rather than by the accepted volume.",
        "",
        "32. S10. Treating downlink_reports.csv as an accepted volume.",
        "",
        "33. S10. Charging a pass to both contracts of a mission that holds two.",
        "",
        "34. S11. Computing the utilisation numerator from the pass plan or from",
        "    the admitted rows rather than from the accepted rows.",
        "",
        "35. S11. Reducing the utilisation denominator because a budget or an",
        "    allowance ran out.",
        "",
        "36. S11. Averaging aperture basis points to get a station figure rather",
        "    than summing the numerators and denominators first.",
        "",
        "37. S13. Reducing a shortfall by the exempt volume rather than waiving",
        "    it entirely.",
        "",
        "38. S13. Letting an outage exemption restore utilisation.",
        "",
        "39. S13. Including a late cancelled pass in the exempt pool.",
        "",
        "40. S13. Counting a rejected or withdrawn outage claim.",
        "",
        "41. S14. Including stage_digest_manifest.json in its own digest.",
        "",
        "42. Everywhere. Introducing floating point. Every quantity in this",
        "    settlement is an integer and every division is a floor.",
    ]) + NL


def doc_lineage():
    return NL.join([
        "# data lineage",
        "",
        "Which file feeds which stage, and which file feeds nothing.",
        "",
        "| file | stage | role |",
        "| --- | --- | --- |",
        "| mission_register.csv | S01 S06 | mission identity and registered class |",
        "| mission_alias_crosswalk.csv | S01 | presentation identifier to mission |",
        "| ground_segment_register.tsv | S01 S02 | station identity and accounting offset |",
        "| aperture_register.csv | S01 | aperture identity and label resolution |",
        "| aperture_service_windows.csv | S02 | declared operating windows |",
        "| maintenance_dockets.csv | S02 | aperture outage subtraction |",
        "| blackout_advisories.psv | S02 | station outage subtraction |",
        "| station_accounting_calendar.csv | S02 S04 | station local period windows |",
        "| station_local_accounting.ini | S02 | period shape and boundary convention |",
        "| pass_plan_of_record.csv | S03 | the passes to settle |",
        "| campaign_schedule.xml | S03 | mission phase admission |",
        "| cancellation_notices.csv | S03 | cancellation and late cancellation |",
        "| contact_event_journal.ndjson | S03 S04 S06 | event class, actual times, commit evidence |",
        "| operator_roster.tsv | S06 | operator authority grade |",
        "| reference_lookups.sqlite | S01 S03 S06 | scope, priority rank, commit grades |",
        "| settlement_audit_trace.db | S01 S08 | contract identity, validity and carry flag |",
        "| rate_schedule_effective.psv | S05 | effective dated rates |",
        "| aperture_contract_workbook.xlsx | S05 S09 S13 | per contact cap, period budget, credit rates |",
        "| workbook_sheet_selection.json | S05 | which workbook sheet binds |",
        "| network_operations_memo.pdf | S03 S06 S09 S13 | commit lead, pass budget shape, outage floor |",
        "| precedence_directive.docx | S06 | precedence order and the commit exception |",
        "| precedence_override_register.jsonl | S06 | narrow class overrides |",
        "| contract_terms_amendments.tsv | S07 S08 S13 | obligation, entitlement, reserve, carry cap |",
        "| prior_period_settlement.json | S08 | opening carry buckets |",
        "| onboard_backlog_reports.csv | S09 S10 | opening backlog per mission period |",
        "| outage_claims.psv | S13 | outage qualification |",
        "| unit_scaling_rules.json | S05 S09 S13 | scale divisors and damping terms |",
        "| rounding_and_precision.yml | all | the floor at every stage boundary |",
        "| ordering_dependencies.yaml | all | the stage edges including the S08 back edge |",
        "| exception_code_dictionary.xml | S03 S14 | the reject reason slug and the exception report class |",
        "| unit_test_vectors.json | none | self check vectors for the arithmetic |",
        "| sample_worked_records.jsonl | none | scheduled spans only, before clipping |",
        "| legacy_flat_rate_table.csv | S14 only | retired, read for the discrepancy report |",
        "",
        "## files that decide nothing",
        "",
        "legacy_flat_rate_table.csv is retired and binds no capacity. It exists",
        "because the discrepancy report has to name the apertures whose retired",
        "flat rate sits outside the effective band, and that report is graded.",
        "",
        "downlink_reports.csv is a reported figure and never an accepted one. It",
        "is read at S14 for the discrepancy report only.",
        "",
        "sample_worked_records.jsonl restates scheduled spans from the pass plan.",
        "It is a convenience for checking that a reader parses the plan and it",
        "carries no clipped, capped or settled value.",
        "",
        "unit_test_vectors.json is the arithmetic self check. Every vector is one",
        "documented operation with its exact expected output. A run that",
        "reproduces every vector has the arithmetic right; it says nothing about",
        "whether the stages were ordered right.",
        "",
        "The superseded rows inside mission_register.csv, aperture_register.csv,",
        "contract_terms_amendments.tsv and legacy_flat_rate_table.csv are real",
        "history, not padding. They are what makes the binding row a choice.",
    ]) + NL


def doc_sentinel():
    return NL.join([
        "# corpus coverage sentinel",
        "",
        "This month is one month. This note says what it does and does not",
        "show, so that the absence of an example is never read as the absence",
        "of a rule. Every rule in the stage documents binds whether or not this",
        "month happens to exercise it.",
        "",
        "## exercised in bulk",
        "",
        "  all eight admission predicates, each rejecting at least one pass;",
        "",
        "  the per contact cap, binding on a few hundred canonical rows;",
        "",
        "  displacement at S07, on around a hundred rows;",
        "",
        "  the damped ration, on roughly half the aperture periods;",
        "",
        "  carry forfeiture, on around fifty contract periods;",
        "",
        "  outage qualification and the waiver it triggers, on more than half",
        "  the contract periods.",
        "",
        "## exercised once, or nearly once",
        "",
        "  a presentation identifier that resolves in no window, so predicate",
        "  one fires on two passes, and one of those two also carries an",
        "  aperture label that binds under no configuration row, so the",
        "  published predicate order is what decides the code it is recorded",
        "  under;",
        "",
        "  an aperture label that binds under no current configuration row, so",
        "  predicate two fires on two passes, and one of those two is also",
        "  scheduled before every contract opens, so again the order is what",
        "  decides the code;",
        "",
        "  a zero length pass;",
        "",
        "  two passes with identical intervals, decided at the last rung of the",
        "  tie break ladder;",
        "",
        "  a pass straddling a station local accounting boundary;",
        "",
        "  a pass whose start sits on a rate schedule edge;",
        "",
        "  an aperture withdrawn from service for a whole period, so one empty",
        "  utilisation denominator;",
        "",
        "  a contract expiring at a period boundary, which changes only the",
        "  periods after it;",
        "",
        "  a contract period with zero entitlement and zero carry cap;",
        "",
        "  a mission whose binding backlog report reads zero.",
        "",
        "## shapes this month does not fix",
        "",
        "The pass budget of the ration is derived from the number of rows in",
        "each aperture period, so another month runs a different number of",
        "passes on differently sized groups. The tie break ladder is decided at",
        "different rungs in different months. The caps, the budgets and the",
        "credit rates are per month figures, and every other operating",
        "constant is read from the papers of the month being settled rather",
        "than carried from this one.",
        "",
        "A settlement run that reproduces this month by recognising it has done",
        "nothing. The rules are what carry across.",
    ]) + NL


def doc_artifact_contract():
    lines = [
        "# output artifact contract",
        "",
        "A settlement run writes every artifact below into its output directory,",
        "in this order for the purpose of the digest. Names are exact.",
        "",
    ]
    for i, name in enumerate(CORE_ARTIFACTS, start=1):
        lines.append("  " + format(i, "02d") + ". " + name)
    lines += [
        "",
        "  30. stage_digest_manifest.json",
        "",
        "Every artifact is written on every run, including when it has no rows.",
        "An artifact is never omitted because it turned out empty.",
        "",
        "The settlement program is a deliverable in its own right rather than",
        "one of the thirty. It is placed once at " + OUT_MOUNT + "/"
        + PROGRAM_NAME + ", and a run",
        "of it leaves its own source alone, so the data directory stays the",
        "only place a run reads from.",
    ]
    return NL.join(lines) + NL


def doc_serialization():
    return NL.join([
        "# serialization and digest contract",
        "",
        "Artifacts are compared byte for byte, so the shape below is as binding",
        "as the arithmetic.",
        "",
        "## delimited files",
        "",
        "csv uses a comma, tsv a tab, psv a vertical bar. The first line is the",
        "header, holding the column names in the order the stage document gives",
        "them. One line per row after it. Every line ends with a single line",
        "feed, including the last. There is no carriage return anywhere.",
        "",
        "No field is quoted and no field contains a delimiter, a quote or a line",
        "feed. Integers are written in decimal with no sign for zero and no",
        "leading zeros. A field documented as empty is written as the empty",
        "string, so two delimiters sit together.",
        "",
        "A delimited artifact with no rows is the header line alone, followed by",
        "one line feed.",
        "",
        "## jsonl and ndjson",
        "",
        "One JSON object per line, keys sorted ascending, no space after the",
        "comma or the colon, ASCII only. Every line ends with a line feed,",
        "including the last.",
        "",
        "A jsonl artifact with no rows is a file of zero bytes. It is not a file",
        "containing one line feed and it is not a file containing an empty array.",
        "",
        "## json",
        "",
        "One JSON document, keys sorted ascending, indented by two spaces, ASCII",
        "only, followed by a single trailing line feed.",
        "",
        "## xml",
        "",
        "The declaration line first, exactly",
        "",
        "    " + XMLDECL,
        "",
        "then one element per line with no indentation, and a single trailing",
        "line feed. Attribute values are in double quotes. An element with no",
        "children is written with an open tag and a close tag, never self",
        "closing.",
        "",
        "## markdown",
        "",
        "The layout in output_schema_reference.md, with a single trailing line",
        "feed.",
        "",
        "## the digest",
        "",
        "core_digest is the sha256, in lower case hexadecimal, of the",
        "concatenation of the bytes of the twenty nine core artifacts in the",
        "order given by output_artifact_contract.md. per_artifact_sha256 maps",
        "each core artifact name to the sha256 of its own bytes.",
        "stage_digest_manifest.json is not itself a core artifact and does not",
        "enter its own digest. artifact_count is twenty nine and stage_count is",
        "fourteen.",
    ]) + NL


def doc_schema():
    lines = ["# output schema reference", "",
             "Column order is binding. Every column is an integer unless the",
             "description says otherwise.", ""]
    schemas = [
        ("canonical_contact_ledger.csv",
         "contact_id, period_id, station_id, antenna_uid, mission_id, "
         "contract_id, eligible_seconds, raw_capacity_kib, usable_capacity_kib, "
         "effective_class, protected, late_cancel, allocation_state, "
         "demand_kib, allocated_kib, accepted_kib",
         "One row per admitted pass per period, ordered by contact_id then "
         "period_id. allocation_state is won or displaced. A displaced row "
         "carries zero in demand_kib, allocated_kib and accepted_kib and an "
         "empty contract_id."),
        ("admitted_contact_ledger.csv",
         "contact_id, period_id, station_id, antenna_uid, mission_id, "
         "presentation_id, scheduled_start_s, scheduled_end_s, "
         "commit_boundary_s, event_status, operator_code, protected, "
         "late_cancel, eligible_seconds",
         "Same rows as the canonical ledger, ordered the same way, carrying the "
         "admission evidence instead of the settlement figures."),
        ("rejected_contact_ledger.psv",
         "contact_id, station_id, aperture_label, presentation_id, "
         "scheduled_start_s, scheduled_end_s, predicate_index, reject_code, "
         "reject_reason",
         "One row per rejected pass, ordered by contact_id. Not per period."),
        ("normalized_contact_intervals.tsv",
         "contact_id, period_id, antenna_uid, segment_start_s, segment_end_s, "
         "segment_seconds",
         "One row per eligible piece, ordered by contact_id then period_id then "
         "segment_start_s."),
        ("antenna_capacity_ledger.csv",
         "contact_id, period_id, antenna_uid, eligible_seconds, "
         "rate_piece_count, raw_capacity_kib, capacity_cap_kib, "
         "usable_capacity_kib",
         "One row per canonical row, ordered by contact_id then period_id."),
        ("capacity_cap_exceptions.psv",
         "contact_id, period_id, antenna_uid, raw_capacity_kib, "
         "capacity_cap_kib, clipped_kib",
         "Only rows where raw capacity strictly exceeded the cap."),
        ("contention_groups.jsonl",
         "antenna_uid, period_id, group_seq, member_count, member_ids, "
         "eligible_seconds_total",
         "member_ids is the contact identifiers of the component sorted "
         "ascending and joined by commas. Ordered by antenna_uid then "
         "period_id then group_seq."),
        ("winning_resource_assignments.csv",
         "contact_id, period_id, antenna_uid, mission_id, effective_class, "
         "effective_rank, protected, commit_boundary_s, "
         "remaining_obligation_kib, eligible_seconds, usable_capacity_kib",
         "The accepted rows only, ordered by contact_id then period_id."),
        ("displaced_contact_ledger.psv",
         "contact_id, period_id, antenna_uid, mission_id, displaced_by, "
         "displaced_seconds, usable_capacity_kib",
         "The displaced rows only, ordered by contact_id then period_id."),
        ("mission_entitlement_state.csv",
         "contract_id, period_id, carry_source_kib, carry_cap_kib, "
         "carry_in_kib, carry_forfeit_kib, entitlement_kib, "
         "available_allowance_kib, consumed_kib, unconsumed_kib, "
         "contract_expired",
         "One row per contract per period with settled terms, ordered by "
         "contract_id then period_id."),
        ("carry_forward_ledger.csv",
         "contract_id, period_id, carry_in_kib, carry_forfeit_kib, "
         "carry_out_kib, carry_forward_enabled",
         "The same rows, carrying the state that crosses into the next period."),
        ("rationing_pass_trace.jsonl",
         "antenna_uid, period_id, pass_seq, active_count, share_kib, "
         "allocated_kib, budget_kib, demand_total_kib",
         "One row per pass of the ration, for the aperture periods that ran it, "
         "ordered by antenna_uid then period_id then pass_seq."),
        ("delivered_volume_ledger.csv",
         "contact_id, period_id, mission_id, contract_id, antenna_uid, "
         "demand_kib, allocated_kib, accepted_kib, from_carry_kib, "
         "from_new_kib",
         "The accepted rows only, ordered by contact_id then period_id."),
        ("deferred_volume_ledger.csv",
         "contact_id, period_id, mission_id, demand_kib, accepted_kib, "
         "deferred_kib, late_cancel",
         "The accepted rows only, ordered by contact_id then period_id."),
        ("unused_capacity_ledger.tsv",
         "contact_id, period_id, antenna_uid, usable_capacity_kib, "
         "accepted_kib, unused_capacity_kib",
         "The accepted rows only, ordered by contact_id then period_id."),
        ("station_utilisation_ledger.csv",
         "station_id, period_id, occupied_seconds, available_seconds, "
         "utilisation_bp, denominator_state",
         "One row per station per period, ordered by station_id then period_id. "
         "denominator_state is the word empty or the word populated, never a "
         "blank field."),
        ("antenna_utilisation_ledger.tsv",
         "antenna_uid, period_id, occupied_seconds, available_seconds, "
         "utilisation_bp, denominator_state",
         "One row per aperture per period, ordered by antenna_uid then "
         "period_id. denominator_state is the word empty or the word "
         "populated, never a blank field."),
        ("mission_settlement_statements.csv",
         "mission_id, period_id, won_pass_count, eligible_seconds, "
         "usable_capacity_kib, accepted_kib, deferred_kib, "
         "unused_capacity_kib, net_mcr",
         "One row per mission per period, every pair present, ordered by "
         "mission_id then period_id."),
        ("station_settlement_statements.csv",
         "station_id, period_id, won_pass_count, eligible_seconds, "
         "accepted_kib, unused_capacity_kib, utilisation_bp",
         "One row per station per period, every pair present, ordered by "
         "station_id then period_id."),
        ("contract_compliance_ledger.csv",
         "contract_id, period_id, mission_id, obligation_kib, delivered_kib, "
         "reserved_kib, shortfall_kib, compliance_state",
         "One row per contract period with settled terms. compliance_state is "
         "met, exempt or short."),
        ("credit_debit_ledger.csv",
         "contract_id, period_id, shortfall_kib, shortfall_debit_mcr, "
         "unused_reserved_kib, unused_credit_mcr, outage_credit_mcr, "
         "carry_restore_kib, net_mcr",
         "One row per contract period with settled terms."),
        ("outage_adjustment_ledger.psv",
         "contract_id, period_id, mission_id, claim_overlap_seconds, "
         "qualifying_floor_seconds, outage_qualified, exempt_kib, "
         "carry_restore_kib",
         "One row per contract period with settled terms, qualified or not."),
         ("exception_classification_report.jsonl",
          "exception_class, subject_id, code, detail_value",
          "exception_class is the report_class attribute that "
          "exception_code_dictionary.xml gives the code, and the reject_reason "
          "column of the rejected ledger is that code reason_slug attribute. "
          "Ordered by exception_class then subject_id then code, then the "
          "period the exception arose in, P1 before P2 before P3. That period "
          "is a sort key only and is not a column of this report. "
          "exception_class is admission, capacity_cap, displacement, "
          "carry_forfeit, empty_denominator or late_cancel. subject_id is the "
          "contact_id for admission, capacity_cap, displacement and "
          "late_cancel, the contract_id for carry_forfeit, and the antenna_uid "
          "for empty_denominator. detail_value is the "
          "predicate index, the clipped volume, the displaced seconds, the "
          "forfeited volume, zero, or the deferred volume respectively."),
        ("tie_resolution_report.csv",
         "antenna_uid, period_id, contact_id_kept, contact_id_yielded, "
         "decided_at_level",
         "Ordered by antenna_uid, period_id, contact_id_kept, "
         "contact_id_yielded."),
        ("cross_source_discrepancy_report.psv",
         "source_left, source_right, subject_id, period_id, left_value, "
         "right_value, delta_value, discrepancy_class",
         "delta_value is left_value less right_value. period_id is empty for "
         "both families. source_left and source_right name the two sides as "
         "fixed slugs rather than as file names: the first family writes "
         "canonical_ledger and downlink_report, the second writes "
         "rate_schedule and legacy_flat_table."),
        ("invariant_check_report.json",
         "check_count, checks, all_balanced",
         "checks is a list of objects with check_name, left_value, right_value "
         "and balanced, in the fixed order below."),
        ("period_reconciliation_totals.json",
         "P1, P2, P3, network",
         "Each period key holds won_pass_count, eligible_seconds, "
         "usable_capacity_kib, accepted_kib, deferred_kib, "
         "unused_capacity_kib, carry_in_kib, carry_forfeit_kib, "
         "carry_out_kib, shortfall_debit_mcr, unused_credit_mcr, "
         "outage_credit_mcr, net_mcr, occupied_seconds and available_seconds. "
         "The network key holds net_mcr, accepted_kib and won_pass_count "
         "summed across the periods."),
        ("network_settlement_summary.xml",
         "settlement, missions, stations, network",
         "See the layout below."),
        ("per_mission_final_summary.md",
         "mission_id, accepted_kib, deferred_kib, unused_capacity_kib, net_mcr",
         "See the layout below."),
        ("stage_digest_manifest.json",
         "artifact_count, core_digest, per_artifact_sha256, stage_count",
         "artifact_count is twenty nine and stage_count is fourteen. "
         "per_artifact_sha256 maps each core artifact name to the sha256 of "
         "its own bytes. core_digest is the sha256 of the concatenation of "
         "those bytes in the order output_artifact_contract.md gives. "
         "serialization_and_digest_contract.md owns the digest rules and this "
         "manifest is excluded from its own digest."),
    ]
    for name, cols, note in schemas:
        lines.append("## " + name)
        lines.append("")
        lines.append("columns: " + cols)
        lines.append("")
        lines.append(note)
        lines.append("")
    lines += [
        "## invariant check order",
        "",
        "  1. admitted_equals_won_plus_displaced",
        "  2. accepted_never_exceeds_allocated",
        "  3. allocated_never_exceeds_demand",
        "  4. unused_matches_capacity_less_accepted",
        "  5. carry_split_matches_accepted",
        "  6. allocation_within_aperture_budget",
        "  7. credit_rows_match_entitlement_rows",
        "  8. ration_trace_groups_are_over_subscribed",
        "",
        "Checks two, three, six and eight are counts of violations and their",
        "right value is zero. Checks one, four, five and seven compare two",
        "totals.",
        "",
        "## network_settlement_summary.xml layout",
        "",
        "    " + XMLDECL,
        "    <settlement>",
        "    <missions>",
        "    <mission id=\"MSN-01\" period=\"P1\"><accepted_kib>0</accepted_kib>"
        "<deferred_kib>0</deferred_kib><net_mcr>0</net_mcr></mission>",
        "    ... one line per mission period, in mission then period order ...",
        "    </missions>",
        "    <stations>",
        "    <station id=\"ST-AUR\" period=\"P1\"><accepted_kib>0</accepted_kib>"
        "<utilisation_bp>0</utilisation_bp></station>",
        "    ... one line per station period, in station then period order ...",
        "    </stations>",
        "    <network>",
        "    <net_mcr>0</net_mcr>",
        "    <contract_period_count>0</contract_period_count>",
        "    </network>",
        "    </settlement>",
        "",
        "contract_period_count is the number of rows in the credit ledger.",
        "",
        "## per_mission_final_summary.md layout",
        "",
        "    # mission settlement summary",
        "    (blank line)",
        "    | mission_id | accepted_kib | deferred_kib | unused_capacity_kib | net_mcr |",
        "    | --- | --- | --- | --- | --- |",
        "    | MSN-01 | 0 | 0 | 0 | 0 |",
        "    ... one row per mission, in mission_id order, summed over periods ...",
        "    (blank line)",
        "    network net_mcr 0",
        "",
        "Cells are separated by a vertical bar with one space on each side, and",
        "each line begins and ends with a vertical bar.",
    ]
    return NL.join(lines) + NL


def doc_program_contract():
    return NL.join([
        "# settlement program contract",
        "",
        "The settlement program is a deliverable in its own right and is graded",
        "on directories it has never seen.",
        "",
        "## the interface",
        "",
        "    python3 " + OUT_MOUNT + "/" + PROGRAM_NAME
        + " --data DIR --out DIR",
        "",
        "Both flags are required and both take a directory path. The program",
        "reads the working papers under the data directory, writes all thirty",
        "artifacts into the output directory, creating it when it does not",
        "exist, and exits with status zero.",
        "",
        "## what it may do",
        "",
        "It imports the Python standard library and nothing else. It reads only",
        "the directory given by the data flag. It writes only into the directory",
        "given by the out flag. It reaches no network, reads no environment",
        "variable that changes a value it emits, and consults no file outside",
        "the two directories.",
        "",
        "It produces the same bytes every time it is run against the same data",
        "directory. Nothing it emits depends on a clock, a random source, a",
        "process identifier, a hash seed, or the order a directory listing",
        "happens to return.",
        "",
        "## what it may not do",
        "",
        "It may not carry values derived from one particular month. A program",
        "that recognises a case by its shape and returns a remembered answer is",
        "not a settlement program, and a program whose output changes when a",
        "file is renamed is not one either. Every figure it writes is derived",
        "from the papers in front of it.",
        "",
        "## the papers it will be given",
        "",
        "Another month has the same file names, the same columns and the same",
        "rules. Its passes, operating windows, dockets, advisories, campaign",
        "phases, cancellations, journals, overrides, claims, backlog reports",
        "and contract amendments are its own, and so are its rates, its per",
        "contact caps, its aperture period budgets and its credit rates. Which",
        "of the remaining figures a month shares with this one is not",
        "published, so no figure read from these papers may be written into",
        "the program. Every figure it emits is read from the data directory it",
        "was handed on that run.",
        "",
        "The artifacts the program writes for a given directory are the same",
        "artifacts the run is graded on. A delivery whose artifacts disagree",
        "with what its own program produces for the same directory is a delivery",
        "that reports one thing and computes another.",
    ]) + NL


def doc_glossary():
    return NL.join([
        "# glossary and field dictionary",
        "",
        "aperture. One steerable antenna at one station. Identified network wide",
        "by antenna_uid and locally by station_id with aperture_label.",
        "",
        "accounting period. The station local settlement window, P1, P2 or P3,",
        "derived from station_accounting_calendar.csv. Half open.",
        "",
        "allowance. carry_in_kib plus entitlement_kib for one contract period.",
        "Consumed carry first.",
        "",
        "backlog. Volume the spacecraft is holding, in KiB, per mission per",
        "period. The opening figure feeds S09; the running figure feeds S10.",
        "",
        "basis point. One ten thousandth. utilisation_bp is an integer.",
        "",
        "binding row. The row of a history that decides, as opposed to the rows",
        "it superseded.",
        "",
        "canonical row. One pass in one settlement period. The unit of the",
        "canonical contact ledger and of everything after S04.",
        "",
        "carry forward. Unconsumed allowance moving into the next period,",
        "capped, and forfeited when the cap or the contract says so.",
        "",
        "commit boundary. scheduled_start_s less the station commit lead. The",
        "instant after which a pass counts as committed.",
        "",
        "commit evidence. An operational event recorded at or before the commit",
        "boundary by an operator whose grade carries it.",
        "",
        "demand. The smaller of usable capacity and opening backlog.",
        "",
        "displacement. Losing a whole eligible interval to an earlier ranked",
        "pass on the same aperture.",
        "",
        "eligible set. The clipped, availability intersected, period split",
        "interval set of a canonical row.",
        "",
        "KiB. 1024 bytes. All volumes are integer KiB.",
        "",
        "late cancellation. A binding cancellation effective at or after the",
        "commit boundary. The pass stays admitted.",
        "",
        "milli credit. One thousandth of a credit. All settlement money is",
        "integer milli credits, written mcr.",
        "",
        "milli KiB per second. The rate unit. Divide by rate_scale_divisor after",
        "multiplying by seconds, flooring each rate piece separately.",
        "",
        "MiB. 1024 KiB. Credit rates are quoted per MiB and the conversion",
        "divides by credit_basis_kib_per_mib.",
        "",
        "pass. One scheduled contact between one mission and one aperture. Also",
        "the name of one round of the ration; the context distinguishes them.",
        "",
        "pinned. A ration row that has reached its demand and takes no further",
        "part in the share arithmetic.",
        "",
        "protection. See commit evidence. The first key of the S07 ordering.",
        "",
        "ration. The damped integer division of an over subscribed aperture",
        "period budget across the passes that want it.",
        "",
        "residual. Budget less the sum of the allocations after the last ration",
        "pass. Distributed, or reclaimed when negative.",
        "",
        "settled terms. The highest executed revision of a contract period",
        "amendment.",
        "",
        "share. Room divided by active row count, floored, inside one ration",
        "pass.",
        "",
        "theta. The damping fraction, applied to the movement from the current",
        "allocation toward the target.",
        "",
        "trim. Not a term of this settlement. Rows are pinned, never trimmed.",
        "",
        "usable capacity. Raw capacity capped at the per contact cap.",
    ]) + NL


def write_prose(out, ent):
    wtext(out / "readme_first.txt", doc_readme_first())
    wtext(out / "pipeline_contract_overview.md", doc_overview())
    wtext(out / "spec_stage_s01_identity_resolution.md", doc_s01())
    wtext(out / "spec_stage_s02_availability_construction.md", doc_s02())
    wtext(out / "spec_stage_s03_pass_admission.md", doc_s03())
    wtext(out / "spec_stage_s04_interval_clipping.md", doc_s04())
    wtext(out / "spec_stage_s05_capacity_derivation.md", doc_s05())
    wtext(out / "spec_stage_s06_precedence_and_commit.md", doc_s06())
    wtext(out / "spec_stage_s07_contention_resolution.md", doc_s07())
    wtext(out / "spec_stage_s08_entitlement_merge.md", doc_s08())
    wtext(out / "spec_stage_s09_deliverable_volume.md", doc_s09())
    wtext(out / "spec_stage_s10_transmission_accounting.md", doc_s10())
    wtext(out / "spec_stage_s11_utilisation_basis.md", doc_s11())
    wtext(out / "spec_stage_s12_settlement_aggregation.md", doc_s12())
    wtext(out / "spec_stage_s13_credit_and_debit.md", doc_s13())
    wtext(out / "spec_stage_s14_reconciliation_emission.md", doc_s14())
    wtext(out / "rationing_iteration_notes.md", doc_ration())
    wtext(out / "interval_and_tiebreak_notes.md", doc_intervals())
    wtext(out / "known_traps_and_footguns.md", doc_traps())
    wtext(out / "data_lineage.md", doc_lineage())
    wtext(out / "corpus_coverage_sentinel.md", doc_sentinel())
    wtext(out / "output_artifact_contract.md", doc_artifact_contract())
    wtext(out / "output_schema_reference.md", doc_schema())
    wtext(out / "serialization_and_digest_contract.md", doc_serialization())
    wtext(out / "settlement_program_contract.md", doc_program_contract())
    wtext(out / "glossary_and_field_dictionary.md", doc_glossary())

# ---------------------------------------------------------------------------
# The corpus writer. One seed in, sixty files out, byte reproducible.
# ---------------------------------------------------------------------------
SAMPLE_SEED = 4415207
EVAL_SEED = 9182446
CHALLENGE_SEED = 3370915
STRESS_SEED = 6624138


def _binding_rev(rng, count):
    return count


def write_corpus(out_dir, seed):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ent = build_instance(seed)
    rng = Rng(seed ^ 0x5DEECE66D)

    # -- mission register, shipped as a revision history -------------------
    rows = []
    for m in ent["missions"]:
        for rev in range(1, 13):
            rows.append({
                "mission_id": m["mission_id"], "register_rev": rev,
                "register_state": "current" if rev == 12 else "superseded",
                "call_name": m["call_name"],
                "priority_class": (m["priority_class"] if rev == 12
                                   else rng.pick(PRIORITY_CLASSES)),
                "operator_group": m["operator_group"],
                "commissioned_s": T0 - rng.between(200, 900) * DAY_S,
            })
    wtable(out / "mission_register.csv",
           ["mission_id", "register_rev", "register_state", "call_name",
            "priority_class", "operator_group", "commissioned_s"], rows, ",")

    # -- alias crosswalk ---------------------------------------------------
    wtable(out / "mission_alias_crosswalk.csv",
           ["presentation_id", "mission_id", "valid_from_s", "valid_to_s",
            "crosswalk_rev"],
           sorted(ent["alias"], key=lambda r: (r["mission_id"],
                                               r["valid_from_s"],
                                               r["presentation_id"])), ",")

    # -- ground segment register, one row per facility element -------------
    rows = []
    for s in ent["stations"]:
        for i, (cls, desc) in enumerate(FACILITY_ELEMENTS):
            rows.append({
                "station_id": s["station_id"],
                "element_seq": i + 1,
                "element_class": cls,
                "element_name": desc,
                "site_name": s["site_name"],
                "tz_offset_min": (s["tz_offset_min"] if cls == "accounting_site"
                                  else 0),
                "element_state": "in_service" if i % 17 != 13 else "standby",
            })
    wtable(out / "ground_segment_register.tsv",
           ["station_id", "element_seq", "element_class", "element_name",
            "site_name", "tz_offset_min", "element_state"], rows, chr(9))

    # -- aperture register, one row per configuration revision -------------
    rows = []
    for a in ent["antennas"]:
        for rev in range(1, 7):
            rows.append({
                "antenna_uid": a["antenna_uid"], "config_rev": rev,
                "config_state": "current" if rev == 6 else "superseded",
                "station_id": a["station_id"],
                "local_label": (a["local_label"] if rev == 6
                                else rng.pick(LOCAL_LABELS)),
                "band": a["band"],
                "commissioned_s": T0 - rng.between(100, 800) * DAY_S,
            })
    wtable(out / "aperture_register.csv",
           ["antenna_uid", "config_rev", "config_state", "station_id",
            "local_label", "band", "commissioned_s"], rows, ",")

    # -- service windows, maintenance, blackouts ---------------------------
    wtable(out / "aperture_service_windows.csv",
           ["antenna_uid", "day_index", "effective_from_s", "effective_to_s",
            "service_state"], ent["windows"], ",")
    wtable(out / "maintenance_dockets.csv",
           ["docket_id", "antenna_uid", "start_s", "end_s", "docket_class",
            "raised_by"], ent["maintenance"], ",")
    wtable(out / "blackout_advisories.psv",
           ["advisory_id", "station_id", "start_s", "end_s", "advisory_class",
            "issued_s"], ent["blackouts"], "|")

    # -- rates -------------------------------------------------------------
    wtable(out / "rate_schedule_effective.psv",
           ["antenna_uid", "schedule_rev", "effective_from_s", "effective_to_s",
            "rate_mkib_per_s"], ent["rates"], "|")
    wtable(out / "legacy_flat_rate_table.csv",
           ["antenna_uid", "table_rev", "flat_rate_mkib_per_s", "retired_on_s",
            "table_state"], ent["flat_rates"], ",")

    # -- pass plan and journal ---------------------------------------------
    wtable(out / "pass_plan_of_record.csv",
           ["contact_id", "presentation_id", "station_id", "aperture_label",
            "scheduled_start_s", "scheduled_end_s", "requested_kib", "plan_rev"],
           ent["contacts"], ",")
    wjsonl(out / "contact_event_journal.ndjson",
           sorted(ent["events"], key=lambda r: r["contact_id"]))

    # -- contracts ---------------------------------------------------------
    wtable(out / "contract_terms_amendments.tsv",
           ["contract_id", "period_id", "revision_seq", "amendment_status",
            "obligation_kib", "entitlement_kib", "reserved_kib", "carry_cap_kib",
            "carry_forward_enabled", "amended_on_s"], ent["terms_rows"], chr(9))
    wjsonl(out / "precedence_override_register.jsonl", ent["overrides"])
    wtable(out / "onboard_backlog_reports.csv",
           ["mission_id", "period_id", "report_seq", "report_state",
            "backlog_kib", "reported_at_s"], ent["backlog_rows"], ",")
    wtable(out / "downlink_reports.csv",
           ["contact_id", "reported_kib", "reporting_system", "report_seq",
            "reported_at_s"], ent["delivery_rows"], ",")
    wjson(out / "prior_period_settlement.json",
          {"statement_of": "opening carry buckets at the start of P1",
           "opening_buckets": ent["prior_rows"]})
    wtable(out / "cancellation_notices.csv",
           ["notice_id", "contact_id", "issued_seq", "notice_state",
            "effective_s", "reason_code"], ent["cancellations"], ",")
    wtable(out / "outage_claims.psv",
           ["claim_id", "mission_id", "antenna_uid", "period_id", "claim_from_s",
            "claim_to_s", "claim_status", "claim_class"], ent["outages"], "|")
    wtable(out / "operator_roster.tsv",
           ["operator_code", "station_id", "authority_grade", "shift_code",
            "roster_state"], ent["roster"], chr(9))

    # -- station accounting calendar ---------------------------------------
    rows = []
    for s in ent["stations"]:
        for pi, pid in enumerate(PERIODS):
            open_s, _close = local_period_bounds(s["station_id"], pi)
            for d in range(PERIOD_DAYS):
                a = open_s + d * DAY_S
                rows.append({
                    "station_id": s["station_id"], "period_id": pid,
                    "accounting_day": d + 1,
                    "local_open_s": a, "local_close_s": a + DAY_S,
                    "tz_offset_min": s["tz_offset_min"],
                })
    wtable(out / "station_accounting_calendar.csv",
           ["station_id", "period_id", "accounting_day", "local_open_s",
            "local_close_s", "tz_offset_min"], rows, ",")

    # -- campaign schedule -------------------------------------------------
    lines = [XMLDECL, "<campaigns>"]
    for r in ent["phases"]:
        lines.append("<phase mission_id=" + Q + r["mission_id"] + Q
                     + " phase_seq=" + Q + str(r["phase_seq"]) + Q + ">"
                     + "<phase_from_s>" + str(r["phase_from_s"]) + "</phase_from_s>"
                     + "<phase_to_s>" + str(r["phase_to_s"]) + "</phase_to_s>"
                     + "<phase_class>" + r["phase_class"] + "</phase_class>"
                     + "</phase>")
    lines.append("</campaigns>")
    wtext(out / "campaign_schedule.xml", NL.join(lines) + NL)

    # -- sqlite lookups ----------------------------------------------------
    scope_rows = []
    for c in ent["contracts"]:
        for s in c["scope"]:
            scope_rows.append((c["contract_id"], c["mission_id"], s, "in_scope"))
    rank_rows = [(k, str(v)) for k, v in sorted(PRIORITY_RANK.items(),
                                                key=lambda kv: kv[1])]
    write_sqlite(out / "reference_lookups.sqlite", {
        "station_scope": (["contract_id", "mission_id", "station_id", "scope_state"],
                          scope_rows),
        "priority_rank": (["priority_class", "rank_value"], rank_rows),
        "grade_authority": (["authority_grade", "commit_evidence"],
                            [(g, "1" if g in COMMIT_GRADE_SET else "0")
                             for g in AUTHORITY_GRADES]),
    })
    carry_rows = []
    for c in ent["contracts"]:
        for pid in PERIODS:
            for cls in ["telemetry", "payload", "housekeeping"]:
                carry_rows.append((c["contract_id"], c["mission_id"], pid, cls,
                                   str(c["valid_from_s"]), str(c["valid_to_s"]),
                                   str(c["carry_forward_enabled"]),
                                   "open" if cls == "payload" else "closed"))
    write_sqlite(out / "settlement_audit_trace.db", {
        "carry_state": (["contract_id", "mission_id", "period_id", "bucket_class",
                         "valid_from_s", "valid_to_s", "carry_forward_enabled",
                         "trace_state"], carry_rows),
    })

    # -- workbook ----------------------------------------------------------
    write_xlsx(out / "aperture_contract_workbook.xlsx", _workbook_sheets(ent))

    # -- memo and directive ------------------------------------------------
    write_pdf(out / "network_operations_memo.pdf", _memo_lines(ent, rng))
    write_docx(out / "precedence_directive.docx", _directive_blocks(ent))

    # -- machine readable configuration ------------------------------------
    _write_config(out, ent)

    # -- prose -------------------------------------------------------------
    write_prose(out, ent)
    return ent


def _workbook_sheets(ent):
    def block(caps, budgets, rev, status):
        rows = [["sheet_name", "aperture period terms"],
                ["sheet_revision", str(rev)],
                ["sheet_status", status],
                ["#aperture_period_terms"],
                ["antenna_uid", "period_id", "per_contact_cap_kib",
                 "period_budget_kib"]]
        for a in ent["antennas"]:
            for p in PERIODS:
                rows.append([a["antenna_uid"], p,
                             str(caps[(a["antenna_uid"], p)]),
                             str(budgets[(a["antenna_uid"], p)])])
        rows.append(["#credit_rates"])
        rows.append(["rate_key", "rate_value"])
        for k in sorted(ent["credit_rates"]):
            rows.append([k, str(ent["credit_rates"][k])])
        return rows

    return {
        "REV2_SUPERSEDED": block(ent["superseded_caps"], ent["superseded_budgets"],
                                 2, "superseded"),
        "REV4_LIVE": block(ent["caps"], ent["budgets"], 4, "live"),
        "REV5_DRAFT": block(ent["draft_caps"], ent["draft_budgets"], 5, "draft"),
    }


def _memo_lines(ent, rng):
    out = ["GROUNDLINK NETWORK OPERATIONS MEMO",
           "month end settlement supplement, controlled copy",
           "",
           "SECTION 1 COMMIT LEAD BY STATION",
           "the commit lead is the interval before a scheduled start at which a",
           "pass is treated as committed. it is published here and nowhere else.",
           ""]
    for s in ent["stations"]:
        out.append("commit-lead " + s["station_id"] + ": "
                   + str(s["commit_lead_s"]) + " seconds")
    out += ["",
            "SECTION 2 SETTLEMENT SCALARS",
            "outage-qualifying-floor-seconds: " + str(OUTAGE_QUALIFY_MIN_S) + " seconds",
            "ration-pass-budget-base: " + str(PASS_BUDGET_BASE) + " passes",
            "ration-pass-budget-ceiling: " + str(PASS_BUDGET_CEILING) + " passes",
            "",
            "SECTION 3 DAILY OPERATIONS LOG",
            "one line per station accounting day, kept for audit only. the log",
            "records what the shift saw and is no substitute for the journals.",
            ""]
    for s in ent["stations"]:
        for pi, pid in enumerate(PERIODS):
            for d in range(1, 7):
                out.append("log " + s["station_id"] + " " + pid + " day "
                           + format(d, "02d") + " shift " + str(1 + (d % 3))
                           + " state " + rng.pick(["nominal", "degraded",
                                                   "recovered", "watch"])
                           + " note " + rng.pick(["no action", "feed retuned",
                                                  "link flapped", "handover late",
                                                  "spares drawn", "log reconciled"]))
    return out


def _directive_blocks(ent):
    blocks = [
        ("h", "CONTRACTUAL PRECEDENCE DIRECTIVE"),
        ("p", "This directive states the precedence order that binds antenna "
              "assignment, and the one exception that overturns it."),
        ("h", "Clause 1 precedence order"),
        ("p", "Emergency override outranks contracted priority, which outranks "
              "ordinary priority. A lower rank value wins."),
        ("table", [["priority_class", "rank_value", "clause_ref"],
                   ["emergency_override", "1", "1.1"],
                   ["contracted_priority", "2", "1.2"],
                   ["ordinary_priority", "3", "1.3"]]),
        ("h", "Clause 2 commit protection"),
        ("p", "A pass whose operational event was recorded at or before its "
              "commit boundary, by an operator holding controller or supervisor "
              "grade, is protected. A protected pass outranks every unprotected "
              "pass whatever their priority classes say."),
        ("h", "Clause 3 override ceiling"),
        ("p", "A precedence override may raise a mission above its registered "
              "class for the named aperture and window. An override that names a "
              "weaker class than the registered class leaves the registered class "
              "standing."),
        ("h", "Clause 4 per contract protection eligibility"),
    ]
    rows = [["contract_id", "period_id", "protection_eligible", "clause_ref"]]
    for c in ent["contracts"]:
        for p in PERIODS:
            rows.append([c["contract_id"], p, "yes", "4." + p[-1]])
    blocks.append(("table", rows))
    blocks.append(("h", "Clause 5 station protection register"))
    rows = [["mission_id", "station_group", "protection_state", "clause_ref"]]
    for m in ent["missions"]:
        for g in range(1, 9):
            rows.append([m["mission_id"], "grp-" + format(g, "02d"),
                         "standing", "5." + str(g)])
    blocks.append(("table", rows))
    return blocks


def _write_config(out, ent):
    units = {
        "time_unit": "integer seconds",
        "data_unit": "integer KiB",
        "rate_unit": "integer milli KiB per second",
        "credit_unit": "integer milli credits",
        "rate_scale_divisor": RATE_SCALE,
        "ration_damping_numerator": THETA_NUM,
        "ration_damping_denominator": THETA_DEN,
        "credit_basis_kib_per_mib": CREDIT_BASIS,
        "unit_registry": [],
    }
    quantities = ["eligible_seconds", "raw_capacity_kib", "usable_capacity_kib",
                  "demand_kib", "allocated_kib", "accepted_kib", "deferred_kib",
                  "unused_capacity_kib", "carry_in_kib", "carry_out_kib",
                  "carry_forfeit_kib", "shortfall_kib", "unused_reserved_kib",
                  "shortfall_debit_mcr", "unused_credit_mcr", "outage_credit_mcr",
                  "net_mcr", "utilisation_bp", "occupied_seconds",
                  "available_seconds"]
    # The stage that freezes each quantity. Every later stage reads it and
    # none of them re-derives it, so the floor belongs to the stage named here.
    owner = {
        "eligible_seconds": "S04", "raw_capacity_kib": "S05",
        "usable_capacity_kib": "S05", "demand_kib": "S09",
        "allocated_kib": "S09", "accepted_kib": "S10", "deferred_kib": "S10",
        "unused_capacity_kib": "S10", "carry_in_kib": "S08",
        "carry_out_kib": "S08", "carry_forfeit_kib": "S08",
        "shortfall_kib": "S13", "unused_reserved_kib": "S13",
        "shortfall_debit_mcr": "S13", "unused_credit_mcr": "S13",
        "outage_credit_mcr": "S13", "net_mcr": "S13",
        "utilisation_bp": "S11", "occupied_seconds": "S11",
        "available_seconds": "S11",
    }
    for si in range(1, 15):
        for q in quantities:
            units["unit_registry"].append({
                "stage": "S" + format(si, "02d"), "quantity": q,
                "storage": "int64", "scale": 1,
            })
    wjson(out / "unit_scaling_rules.json", units)

    sel = {
        "binding_status": "live",
        "revision_tie_break": "highest sheet_revision wins",
        "status_header_cell": "sheet_status",
        "revision_header_cell": "sheet_revision",
        "block_markers": ["#aperture_period_terms", "#credit_rates"],
        "sheet_row_index": [],
    }
    for name, offset in [("REV2_SUPERSEDED", 6), ("REV4_LIVE", 6),
                         ("REV5_DRAFT", 6)]:
        for i, a in enumerate(ent["antennas"]):
            for j, p in enumerate(PERIODS):
                sel["sheet_row_index"].append({
                    "sheet_name": name, "antenna_uid": a["antenna_uid"],
                    "period_id": p, "row_ordinal": offset + i * len(PERIODS) + j,
                })
    wjson(out / "workbook_sheet_selection.json", sel)

    lines = ["# precision rule per stage and quantity",
             "# every value is truncated toward negative infinity at the stage",
             "# boundary named here, before the next stage reads it",
             "policy: floor_at_stage_boundary",
             "float_arithmetic: forbidden",
             "stage_rules:"]
    for si in range(1, 15):
        lines.append("  S" + format(si, "02d") + ": floor_at_stage_boundary")
    lines.append("quantity_rules:")
    for q in quantities:
        lines.append("  " + owner[q] + "_" + q + ": floor_at_stage_boundary")
    wtext(out / "rounding_and_precision.yml", NL.join(lines) + NL)

    edges = ["# stage dependency edges, producer then consumer",
             "ordering: strict",
             "edges:"]
    chain = ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09",
             "S10", "S11", "S12", "S13", "S14"]
    for i in range(len(chain) - 1):
        edges.append("  - " + chain[i] + " feeds " + chain[i + 1])
    edges.append("  - S08 feeds S07 for the remaining obligation tie break only")
    edges.append("  - S07 feeds S11 because utilisation reads resolved passes")
    edges.append("  - S13 reads S10 and never writes back to S11")
    for q in quantities:
        edges.append("  - " + owner[q] + " publishes " + q)
    wtext(out / "ordering_dependencies.yaml", NL.join(edges) + NL)

    ini = ["; station local accounting parameters",
           "; the accounting period of a station is its calendar rows folded",
           "; to their minimum open and maximum close"]
    for s in ent["stations"]:
        ini.append("")
        ini.append("[" + s["station_id"] + "]")
        ini.append("site_name = " + s["site_name"])
        ini.append("tz_offset_min = " + str(s["tz_offset_min"]))
        ini.append("period_days = " + str(PERIOD_DAYS))
        ini.append("period_count = " + str(len(PERIODS)))
        ini.append("boundary_convention = half_open")
        ini.append("day_seconds = " + str(DAY_S))
    wtext(out / "station_local_accounting.ini", NL.join(ini) + NL)

    lines = [XMLDECL, "<exception_codes>"]
    catalogue = [
        ("E01", "admission", "alias_unresolved", "admission",
         "the presentation identifier resolves to no mission at the scheduled start"),
        ("E02", "admission", "aperture_unknown", "admission",
         "the station and aperture label pair resolves to no aperture"),
        ("E03", "admission", "station_out_of_scope", "admission",
         "the station lies outside every live contract scope for the mission"),
        ("E04", "admission", "phase_standdown", "admission",
         "the mission is in a standdown campaign phase at the scheduled start"),
        ("E05", "admission", "cancelled_before_commit", "admission",
         "an effective cancellation lands strictly before the commit boundary"),
        ("E06", "admission", "no_operational_event", "admission",
         "the journal carries no operational event for the pass"),
        ("E07", "admission", "event_class_inadmissible", "admission",
         "the operational event class is outside the admissible set"),
        ("E08", "admission", "no_eligible_interval", "admission",
         "the clipped eligible interval carries no seconds"),
        ("X01", "capacity", "capacity_cap", "capacity_cap",
         "raw capacity exceeded the per contact cap and was clipped"),
        ("X02", "contention", "displacement", "displacement",
         "the pass was displaced by an earlier ranked pass"),
        ("X03", "entitlement", "carry_forfeit", "carry_forfeit",
         "carry forward was forfeited"),
        ("X04", "utilisation", "empty_denominator", "empty_denominator",
         "the utilisation denominator is empty"),
        ("X05", "accounting", "late_cancel", "late_cancel",
         "the pass carried a late cancellation notice")]
    for code, cls, slug, report, desc in catalogue:
        lines.append("<code id=" + Q + code + Q + " class=" + Q + cls + Q
                     + " reason_slug=" + Q + slug + Q
                     + " report_class=" + Q + report + Q + ">"
                     + "<description>" + xesc(desc) + "</description></code>")
    for i in range(1, 190):
        lines.append("<code id=" + Q + "Z" + format(i, "03d") + Q + " class="
                     + Q + "reserved" + Q + " reason_slug=" + Q + "reserved" + Q
                     + " report_class=" + Q + "reserved" + Q
                     + "><description>"
                     + "reserved for future settlement use, slot "
                     + format(i, "03d") + "</description></code>")
    lines.append("</exception_codes>")
    wtext(out / "exception_code_dictionary.xml", NL.join(lines) + NL)

    _write_vectors(out, ent)


def _write_vectors(out, ent):
    """Self check vectors. Each one is a small worked example of a single
    documented rule, with the inputs and the exact expected output."""
    v = []
    for i in range(40):
        a, b = 1000 + i * 7, 1000 + i * 7 + 300 + i
        v.append({"vector_class": "interval_length", "start_s": a, "end_s": b,
                  "expected_seconds": b - a})
    for i in range(40):
        secs, rate = 60 + i * 13, 2400 + i * 91
        v.append({"vector_class": "capacity_piece", "seconds": secs,
                  "rate_mkib_per_s": rate, "scale_divisor": RATE_SCALE,
                  "expected_kib": (secs * rate) // RATE_SCALE})
    for i in range(40):
        raw, cap = 40000 + i * 1301, 30000 + i * 700
        v.append({"vector_class": "per_contact_cap", "raw_capacity_kib": raw,
                  "cap_kib": cap,
                  "expected_usable_kib": raw if raw < cap else cap})
    for i in range(40):
        x, t = 100 + i * 37, 900 - i * 11
        v.append({"vector_class": "damped_step", "current_kib": x,
                  "target_kib": t, "theta_numerator": THETA_NUM,
                  "theta_denominator": THETA_DEN,
                  "expected_kib": x + ((t - x) * THETA_NUM) // THETA_DEN})
    for i in range(40):
        kib = 1024 * (3 + i) + i
        rate = 180 + i
        v.append({"vector_class": "credit_conversion", "quantity_kib": kib,
                  "rate_mcr_per_mib": rate, "basis_kib_per_mib": CREDIT_BASIS,
                  "expected_mcr": (kib * rate) // CREDIT_BASIS})
    for i in range(24):
        num, den = 3600 * (i + 1), 86400 + i * 97
        v.append({"vector_class": "utilisation_bp", "occupied_seconds": num,
                  "available_seconds": den,
                  "expected_bp": (num * 10000) // den})
    wjson(out / "unit_test_vectors.json",
          {"vector_count": len(v), "vectors": v})

    rec = []
    for i, c in enumerate(ent["contacts"][:216]):
        rec.append({
            "contact_id": c["contact_id"],
            "presentation_id": c["presentation_id"],
            "station_id": c["station_id"],
            "aperture_label": c["aperture_label"],
            "scheduled_start_s": c["scheduled_start_s"],
            "scheduled_end_s": c["scheduled_end_s"],
            "scheduled_seconds": c["scheduled_end_s"] - c["scheduled_start_s"],
            "note": "scheduled span only, before availability clipping",
        })
    wjsonl(out / "sample_worked_records.jsonl", rec)

# ---------------------------------------------------------------------------
# The graded surface. The verifier mints every case it grades from a named
# seed, so no assertion here depends on the directory the agent was handed.
# ---------------------------------------------------------------------------
# Rebound from the workspace rewardkit hands each check; this is the default
# for a direct run of this file.
ART_ROOT = Path("/app/out")
UNSEEN_CASES = [(EVAL_SEED, "eval"), (CHALLENGE_SEED, "chal"),
                (STRESS_SEED, "stress")]

ADMISSION_GROUP = [
    "admitted_contact_ledger.csv",
    "rejected_contact_ledger.psv",
    "normalized_contact_intervals.tsv",
]
ALLOCATION_GROUP = [
    "canonical_contact_ledger.csv",
    "antenna_capacity_ledger.csv",
    "capacity_cap_exceptions.psv",
    "contention_groups.jsonl",
    "winning_resource_assignments.csv",
    "displaced_contact_ledger.psv",
    "tie_resolution_report.csv",
    "mission_entitlement_state.csv",
    "carry_forward_ledger.csv",
    "rationing_pass_trace.jsonl",
    "delivered_volume_ledger.csv",
    "deferred_volume_ledger.csv",
    "unused_capacity_ledger.tsv",
]
SETTLEMENT_GROUP = [
    "station_utilisation_ledger.csv",
    "antenna_utilisation_ledger.tsv",
    "mission_settlement_statements.csv",
    "station_settlement_statements.csv",
    "contract_compliance_ledger.csv",
    "credit_debit_ledger.csv",
    "outage_adjustment_ledger.psv",
    "exception_classification_report.jsonl",
    "cross_source_discrepancy_report.psv",
    "invariant_check_report.json",
    "period_reconciliation_totals.json",
    "network_settlement_summary.xml",
    "per_mission_final_summary.md",
    "stage_digest_manifest.json",
]

_CORPUS = {}
_REF = {}
_RUN = {}
_WORKROOT = None
# rewardkit runs the checks in a thread pool, so every memoised builder below
# is serialised: two threads minting one corpus into one directory would race.
_LOCK = threading.RLock()


def _workroot():
    global _WORKROOT
    if _WORKROOT is None:
        _WORKROOT = tempfile.mkdtemp(prefix="groundlink-")
        # mkdtemp is 0700 and the delivered program runs unprivileged, so the
        # root of the work tree has to be traversable or that program can reach
        # neither its input case nor its output directory.
        try:
            os.chmod(_WORKROOT, 0o755)
        except OSError:
            pass
    return _WORKROOT


def _corpus_dir(seed, tag):
    key = (int(seed), tag)
    if key not in _CORPUS:
        d = Path(_workroot()) / ("case-" + tag) / "data"
        write_corpus(d, seed)
        for p in sorted(d.iterdir()):
            try:
                os.chmod(p, 0o644)
            except OSError:
                pass
        try:
            os.chmod(d, 0o755)
            os.chmod(d.parent, 0o755)
        except OSError:
            pass
        _CORPUS[key] = d
    return _CORPUS[key]


def _reference(seed=None, rules=None, tag="sample"):
    if seed is None:
        seed = SAMPLE_SEED
    key = (int(seed), tag, tuple(sorted(rules)) if rules else ())
    if key not in _REF:
        _REF[key] = run_settlement(_corpus_dir(seed, tag), rules)
    return _REF[key]


def _got(name):
    p = ART_ROOT / name
    if not p.is_file():
        return None
    return p.read_bytes()


class _Failed(Exception):
    """Raised when a property a check reads does not hold."""


def _require(condition, message):
    # An explicit guard rather than an assert: the graded path has to keep its
    # checks under optimised Python too.
    if not condition:
        raise _Failed(message)


def _bind(workspace):
    global ART_ROOT
    # Resolved, because the delivered program is executed with its own working
    # directory and a relative path would resolve against that instead.
    ART_ROOT = Path(workspace).resolve() / "out"


def _verdict(workspace, probe):
    """Report whether one probe holds against the delivered workspace.

    A probe signals a property that does not hold by raising, and missing or
    hostile agent output raises too, so both become a False verdict instead of
    an exception that would abort grading and leave no reward at all.
    """
    with _LOCK:
        _bind(workspace)
        try:
            probe()
        except Exception:
            return False
        return True


def _priv_prefix():
    # setpriv comes from util-linux, which tests/Dockerfile installs. Dropping
    # privileges with an external binary rather than a preexec_fn matters
    # because rewardkit runs the checks in a thread pool, and forking with a
    # Python callback from a threaded parent can deadlock.
    if not (hasattr(os, "getuid") and os.getuid() == 0):
        return []
    setpriv = shutil.which("setpriv")
    if setpriv is None:
        return []
    return [setpriv, "--reuid", "65534", "--regid", "65534", "--clear-groups"]


def _grant_read(program):
    """Make the delivered program readable by the unprivileged uid the checks
    drop to, before they drop to it.

    solve.sh installs its program with cp, which leaves mode 0644, but a real
    agent writes the same program through an editor that renames a temp file
    into place, so it arrives at 0600 owned by the agent. Harbor hands /app to
    the verifier with those modes intact, and the dropped uid then cannot open
    the program at all: every check that executes it returns False on a
    perfectly correct submission while the oracle run still reads 1.000. The
    verifier runs as root, so it may widen the program and the directories
    above it; the agent wrote the file itself, so nothing is disclosed to it.
    """
    try:
        os.chmod(program, 0o755)
    except OSError:
        pass
    for above in (program.parent, program.parent.parent):
        try:
            os.chmod(above, 0o755)
        except OSError:
            pass


def _run_program(program, data, work):
    """Execute the delivered program once over one case, then take its whole
    process group down so nothing it forked outlives the check that ran it."""
    _grant_read(program)
    argv = _priv_prefix() + [sys.executable, str(program),
                             "--data", str(data), "--out", str(work)]
    try:
        proc = subprocess.Popen(
            argv, cwd=str(work),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
    except OSError:
        return
    # start_new_session makes the child its own group leader, so its pid is
    # the group id. It is read before the wait because a reaped child no
    # longer answers getpgid while its grandchildren still carry the group.
    pgid = proc.pid
    try:
        proc.wait(timeout=300)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        pass


def _program_output(seed, tag):
    """Run the delivered settlement program over a minted case and read back
    whatever it wrote. The program runs unprivileged so that it cannot read
    the verifier assets its own reward depends on."""
    key = (int(seed), tag)
    if key in _RUN:
        return _RUN[key]
    program = ART_ROOT / PROGRAM_NAME
    produced = {name: None for name in ALL_ARTIFACTS}
    if program.is_file():
        data = _corpus_dir(seed, tag)
        work = Path(_workroot()) / ("run-" + tag)
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        try:
            os.chmod(work, 0o777)
        except OSError:
            pass
        _run_program(program, data, work)
        for name in ALL_ARTIFACTS:
            p = work / name
            if p.is_file():
                produced[name] = p.read_bytes()
    _RUN[key] = produced
    return produced


def _program_ran(seed, tag):
    produced = _program_output(seed, tag)
    missing = [n for n in ALL_ARTIFACTS if produced[n] is None]
    _require(not missing, PROGRAM_NAME + " wrote no " + ", ".join(missing[:4])
             + " for case " + tag)
    return produced


def _require_delivered_group(names):
    """The artifacts of one stage group are defined as what the delivered
    program produces for the papers it was given, so that group is gated on
    its own program output and on nothing outside it. Gating it on the whole
    artifact set instead would make one wrong field in any group fail every
    group, so a near miss would score as a total miss."""
    exp = _reference()
    produced = _program_ran(SAMPLE_SEED, "sample")
    wrong = [n for n in names if produced[n] != exp[n]]
    _require(not wrong, PROGRAM_NAME + " disagrees with the settlement on "
             + ", ".join(wrong[:4]) + " for the shipped papers")


def _compare(names, produced, expected, label):
    wrong = [n for n in names if produced.get(n) != expected[n]]
    _require(not wrong, label + " differs on " + ", ".join(wrong[:4]))


def _delivered():
    return {n: _got(n) for n in ALL_ARTIFACTS}


# ---------------------------------------------------------------------------
# probes. Each reads one stage group, so a wrong field costs the group that
# carries it and leaves the other groups to be scored on their own bytes.
# ---------------------------------------------------------------------------
def _artifacts_present():
    missing = [n for n in ALL_ARTIFACTS if _got(n) is None]
    _require(not missing, "no " + ", ".join(missing[:6]))
    _require((ART_ROOT / PROGRAM_NAME).is_file(), "no " + PROGRAM_NAME)


def _artifacts_parse():
    for name in ALL_ARTIFACTS:
        raw = _got(name)
        _require(raw is not None, "no " + name)
        if name.endswith(".json"):
            json.loads(raw.decode("utf-8"))
        elif name.endswith(".jsonl"):
            for line in raw.decode("utf-8").split(NL):
                if line:
                    json.loads(line)
        elif name.endswith(".xml"):
            ET.fromstring(raw.decode("utf-8"))
        elif name.endswith(".md"):
            _require(raw.startswith(b"#"), name + " carries no heading")
        else:
            delim = {"csv": ",", "tsv": chr(9), "psv": "|"}[name.rsplit(".", 1)[1]]
            lines = raw.decode("utf-8").split(NL)
            _require(lines and lines[0], name + " carries no header")
            width = len(lines[0].split(delim))
            for line in lines[1:]:
                if line:
                    _require(len(line.split(delim)) == width,
                             name + " has a ragged row")


def _runs_on_every_unseen_case():
    for seed, tag in UNSEEN_CASES:
        _program_ran(seed, tag)


def _visible(group, label):
    _require_delivered_group(group)
    _compare(group, _delivered(), _reference(), label)


def _unseen_case(tag, group, label):
    """One stage group on papers the program has never seen. The delivered
    artifacts of the shipped month are the subject of the visible checks and
    are deliberately not re-read here, so no observable is paid for twice."""
    seed = dict((t, s) for s, t in UNSEEN_CASES)[tag]
    produced = _program_ran(seed, tag)
    _compare(group, produced, _reference(seed, None, tag),
             label + " on case " + tag)


def _took_reading(rule, names):
    """Hold only when the delivery reproduces one named wrong reading exactly.
    The reading is proved to change this month's settlement first, so a
    detector that could not discriminate stays quiet instead of firing."""
    exp = _reference()
    mut = _reference(SAMPLE_SEED, {rule}, "sample")
    touched = [n for n in names if mut[n] != exp[n]]
    _require(touched, "the reading " + rule + " agrees with the settlement on "
             + "this month, so this detector cannot fire cleanly")
    delivered = _delivered()
    matched = [n for n in touched if delivered.get(n) == mut[n]]
    _require(len(matched) == len(touched),
             "the delivery does not take the " + rule + " reading")


def _delivery_disagrees_with_its_own_program():
    produced = _program_output(SAMPLE_SEED, "sample")
    present = [n for n in ALL_ARTIFACTS if produced[n] is not None]
    _require(present, PROGRAM_NAME + " produced nothing to compare against")
    delivered = _delivered()
    _require([n for n in present if delivered.get(n) != produced[n]],
             "the delivered artifacts agree with the delivered program")


def _hardcoded_sample_answers():
    sample = _reference()
    for seed, tag in UNSEEN_CASES:
        other = _reference(seed, None, tag)
        coincident = [n for n in ALL_ARTIFACTS if other[n] == sample[n]]
        _require(not coincident, "case " + tag
                 + " reproduces the shipped month on "
                 + ", ".join(coincident[:3])
                 + ", so this detector cannot fire cleanly")
    echoed = []
    for seed, tag in UNSEEN_CASES:
        produced = _program_output(seed, tag)
        echoed += [n for n in ALL_ARTIFACTS
                   if produced[n] is not None and produced[n] == sample[n]]
    _require(echoed, "the program responded to every unseen month")


def _manifest_digest_disagreement():
    exp = _reference()
    raw = _got("stage_digest_manifest.json")
    _require(raw is not None, "no manifest to check")
    _require(raw != exp["stage_digest_manifest.json"],
             "the manifest is correct; this detector stays quiet")
    h = hashlib.sha256()
    for name in CORE_ARTIFACTS:
        part = _got(name)
        _require(part is not None, "no " + name + " to digest")
        h.update(part)
    claimed = json.loads(raw.decode("utf-8")).get("core_digest")
    _require(claimed != h.hexdigest(),
             "the manifest agrees with the delivered core")


# ---------------------------------------------------------------------------
# the packaging floor
# ---------------------------------------------------------------------------
@criterion(description="every declared artifact is present at its declared path")
def artifacts_present(workspace: Path) -> bool:
    return _verdict(workspace, _artifacts_present)


@criterion(description="every declared artifact parses as the format its name gives")
def artifacts_parse(workspace: Path) -> bool:
    return _verdict(workspace, _artifacts_parse)


@criterion(description="the delivered program writes the full artifact set for papers it has never seen")
def settlement_program_runs_on_every_unseen_case(workspace: Path) -> bool:
    return _verdict(workspace, _runs_on_every_unseen_case)


# ---------------------------------------------------------------------------
# the delivered artifacts of the shipped month, gated on the delivered package
# ---------------------------------------------------------------------------
@criterion(description="the delivered admission ledgers settle the shipped papers exactly")
def visible_admission_chain_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _visible(
        ADMISSION_GROUP, "the delivered admission chain"))


@criterion(description="the delivered capacity, contention and accounting ledgers settle the shipped papers exactly")
def visible_allocation_core_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _visible(
        ALLOCATION_GROUP, "the delivered allocation core"))


@criterion(description="the delivered utilisation, settlement and credit reports settle the shipped papers exactly")
def visible_settlement_reports_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _visible(
        SETTLEMENT_GROUP, "the delivered settlement reports"))


# ---------------------------------------------------------------------------
# the delivered program on papers it has never seen
# ---------------------------------------------------------------------------
@criterion(description="the program admits and clips the eval papers exactly")
def recompute_eval_admission_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _unseen_case(
        "eval", ADMISSION_GROUP, "the admission chain"))


@criterion(description="the program allocates the eval papers exactly")
def recompute_eval_allocation_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _unseen_case(
        "eval", ALLOCATION_GROUP, "the allocation core"))


@criterion(description="the program settles the eval papers exactly")
def recompute_eval_settlement_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _unseen_case(
        "eval", SETTLEMENT_GROUP, "the settlement reports"))


@criterion(description="the program admits and clips the challenge papers exactly")
def recompute_challenge_admission_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _unseen_case(
        "chal", ADMISSION_GROUP, "the admission chain"))


@criterion(description="the program allocates the challenge papers exactly")
def recompute_challenge_allocation_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _unseen_case(
        "chal", ALLOCATION_GROUP, "the allocation core"))


@criterion(description="the program settles the challenge papers exactly")
def recompute_challenge_settlement_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _unseen_case(
        "chal", SETTLEMENT_GROUP, "the settlement reports"))


@criterion(description="the program admits and clips the stress papers exactly")
def recompute_stress_admission_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _unseen_case(
        "stress", ADMISSION_GROUP, "the admission chain"))


@criterion(description="the program allocates the stress papers exactly")
def recompute_stress_allocation_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _unseen_case(
        "stress", ALLOCATION_GROUP, "the allocation core"))


@criterion(description="the program settles the stress papers exactly")
def recompute_stress_settlement_exact(workspace: Path) -> bool:
    return _verdict(workspace, lambda: _unseen_case(
        "stress", SETTLEMENT_GROUP, "the settlement reports"))


# ---------------------------------------------------------------------------
# naive reading detectors. Each holds only when the delivery reproduces one
# named wrong reading exactly, and each is proved discriminating on this case
# before it is allowed to fire.
# ---------------------------------------------------------------------------
@criterion(description="a cancellation effective on the commit boundary rejected the pass rather than marking it a late cancellation")
def negative_naive_cancellation_on_the_commit_boundary(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "cancel_boundary_rejects", ALL_ARTIFACTS))


@criterion(description="capacity multiplied the whole eligible span by its rates and floored once rather than flooring each rate piece")
def negative_naive_blended_rate_then_one_floor(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "aggregate_then_floor", ALL_ARTIFACTS))


@criterion(description="commit protection ranked below the priority class rather than above it")
def negative_naive_protection_as_a_tie_break(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "protection_as_tiebreak", ALL_ARTIFACTS))


@criterion(description="the ration stopped at the first pass that moved nothing rather than running the published pass budget")
def negative_naive_ration_run_to_convergence(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "ration_to_convergence", ALL_ARTIFACTS))


@criterion(description="demand at stage nine drew on the running backlog rather than the opening backlog of the period")
def negative_naive_running_backlog_in_demand(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "running_backlog_demand", ALL_ARTIFACTS))


@criterion(description="the utilisation numerator counted every admitted pass rather than the passes that survived contention")
def negative_naive_utilisation_from_admitted_passes(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "utilisation_from_admitted", ALL_ARTIFACTS))


@criterion(description="the per contact cap was left off the canonical row")
def negative_naive_cap_after_aggregation(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "cap_after_aggregation", ALL_ARTIFACTS))


@criterion(description="capacity used the retired flat rate table rather than the effective dated schedule")
def negative_naive_retired_flat_rate(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "legacy_flat_rate", ALL_ARTIFACTS))


@criterion(description="the settled terms were taken from the last amendment row by file order rather than the highest executed revision")
def negative_naive_last_amendment_row(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "terms_last_row", ALL_ARTIFACTS))


@criterion(description="the damped movement was allowed to floor to zero, so no row ever reached its demand")
def negative_naive_ration_without_the_minimum_step(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "no_minimum_step", ALL_ARTIFACTS))


@criterion(description="a qualifying outage reduced the shortfall debit rather than waiving it")
def negative_naive_shortfall_reduced_not_waived(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "shortfall_reduced_not_waived", ALL_ARTIFACTS))


@criterion(description="new entitlement was drawn before the carry remainder rather than after it")
def negative_naive_entitlement_before_carry(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "entitlement_before_carry", ALL_ARTIFACTS))


@criterion(description="the utilisation denominator fell to the time a contract paid for rather than the physical availability")
def negative_naive_utilisation_denominator_paid(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "utilisation_denominator_paid", ALL_ARTIFACTS))


@criterion(description="a late cancelled pass was counted into the outage exempt pool")
def negative_naive_late_cancel_in_exempt_pool(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, lambda: _took_reading(
        "late_cancel_in_exempt_pool", ALL_ARTIFACTS))


# ---------------------------------------------------------------------------
# structural cheat detectors
# ---------------------------------------------------------------------------
@criterion(description="the delivered artifacts and the delivered program disagree about the same papers")
def negative_delivery_disagrees_with_its_own_program(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, _delivery_disagrees_with_its_own_program)


@criterion(description="the program returns the shipped month whatever papers it is given")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, _hardcoded_sample_answers)


@criterion(description="the digest manifest disagrees with the delivered core bytes")
def negative_manifest_digest_disagreement(workspace: Path) -> bool:
    # True when the cheat happened; the negative weight does the punishing.
    return _verdict(workspace, _manifest_digest_disagreement)


criteria.artifacts_present(weight=1)
criteria.artifacts_parse(weight=1)
criteria.settlement_program_runs_on_every_unseen_case(weight=1)
criteria.visible_admission_chain_exact(weight=1)
criteria.visible_allocation_core_exact(weight=3)
criteria.visible_settlement_reports_exact(weight=3)
criteria.recompute_eval_admission_exact(weight=5)
criteria.recompute_eval_allocation_exact(weight=5)
criteria.recompute_eval_settlement_exact(weight=5)
criteria.recompute_challenge_admission_exact(weight=5)
criteria.recompute_challenge_allocation_exact(weight=5)
criteria.recompute_challenge_settlement_exact(weight=5)
criteria.recompute_stress_admission_exact(weight=5)
criteria.recompute_stress_allocation_exact(weight=5)
criteria.recompute_stress_settlement_exact(weight=5)
criteria.negative_naive_cancellation_on_the_commit_boundary(weight=-3)
criteria.negative_naive_blended_rate_then_one_floor(weight=-3)
criteria.negative_naive_protection_as_a_tie_break(weight=-3)
criteria.negative_naive_ration_run_to_convergence(weight=-3)
criteria.negative_naive_running_backlog_in_demand(weight=-3)
criteria.negative_naive_utilisation_from_admitted_passes(weight=-3)
criteria.negative_naive_cap_after_aggregation(weight=-1)
criteria.negative_naive_retired_flat_rate(weight=-1)
criteria.negative_naive_last_amendment_row(weight=-1)
criteria.negative_naive_ration_without_the_minimum_step(weight=-1)
criteria.negative_naive_shortfall_reduced_not_waived(weight=-1)
criteria.negative_naive_entitlement_before_carry(weight=-1)
criteria.negative_naive_utilisation_denominator_paid(weight=-1)
criteria.negative_naive_late_cancel_in_exempt_pool(weight=-1)
criteria.negative_delivery_disagrees_with_its_own_program(weight=-3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_manifest_digest_disagreement(weight=-1)

if __name__ == "__main__":
    write_corpus(Path(sys.argv[1]) / "data", SAMPLE_SEED)
