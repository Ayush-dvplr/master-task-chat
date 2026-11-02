#!/usr/bin/env python3
"""Verifier for the slipway-overhaul-replan-repair bundle.

Holds the corpus generator, an independent reference chain for the fourteen
stage incremental replan, and the graded assertions. The verifier owns its
corpus: every round it grades is minted here from a named seed, so no graded
value depends on the directory the agent was handed.

Two grading surfaces. The documents the agent delivered for the shipped round
are compared against this file's own reference chain. The package the agent
delivered is extracted and driven over three rounds minted from seeds it has
never seen, in a subprocess with privileges dropped to nobody.
"""
import ast
import hashlib
import io
import json
import os
import shutil
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

SAMPLE_SEED = 9012384756102938475
EVAL_SEED = 2951730846621509887
CHALLENGE_SEED = 6183094725530817449
PROBE_SEED = 8407261539924610337

NL = chr(10)
BS = chr(92)
Q = chr(34)
TAB = chr(9)
PIPE = chr(124)
MASK64 = 0xFFFFFFFFFFFFFFFF

# The wrong readings a detector rebuilds the publication under.
WRONG = set()

# No string constant in this module names the agent side corpus path. The
# verifier container has no such directory and a literal here would be
# indistinguishable from a grade time read.
OUTPUT_ROOT = "/app/out"
PACKAGE_NAME = "slwopt"

XMLDECL = "<?xml version=" + Q + "1.0" + Q + " encoding=" + Q + "UTF-8" + Q + "?>"
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_PKGREL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CT_SHEETML = "application/vnd.openxmlformats-officedocument.spreadsheetml"
CT_WORDML = "application/vnd.openxmlformats-officedocument.wordprocessingml"
W_NS = "{" + NS_WORD + "}"


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


def child_seed(root, tag):
    h = hashlib.blake2b(str(root).encode("utf-8"), digest_size=8,
                        person=tag.encode("utf-8")[:16])
    return int.from_bytes(h.digest(), "big") >> 1


# --------------------------------------------------------------------------
# exact arithmetic
#
# Every published whole quantity is an integer in the unit its stage names and
# every published ratio carries exactly twelve decimal places. Rounding happens
# where a stage specification places it and nowhere else, and it is always half
# away from zero on an exact rational. Binary floating point never enters the
# derivation.
# --------------------------------------------------------------------------
RATIO_PLACES = 12
RATIO_SCALE = 10 ** RATIO_PLACES


def half_up(value):
    """Round an exact Fraction to the nearest integer, halves away from zero."""
    f = Fraction(value)
    n, d = f.numerator, f.denominator
    if d == 1:
        return n
    if n >= 0:
        return (2 * n + d) // (2 * d)
    return -((2 * (-n) + d) // (2 * d))


def ratio_text(value):
    """Twelve decimal places, half away from zero, with no negative zero."""
    f = Fraction(value)
    scaled = half_up(f * RATIO_SCALE)
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    whole, frac = divmod(scaled, RATIO_SCALE)
    text = sign + str(whole) + "." + str(frac).rjust(RATIO_PLACES, "0")
    if text == "-0." + "0" * RATIO_PLACES:
        text = "0." + "0" * RATIO_PLACES
    return text


def safe_ratio(num, den):
    """A ratio whose denominator may be zero publishes as an exact zero."""
    if den == 0:
        return ratio_text(0)
    return ratio_text(Fraction(int(num), int(den)))


def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + NL


def compact_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def digest_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def digest_text(text):
    return digest_bytes(text.encode("utf-8"))


def digest_file(path):
    return digest_bytes(Path(path).read_bytes())


def xesc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace(Q, "&quot;"))


def _q(value):
    return Q + str(value) + Q


# --------------------------------------------------------------------------
# writers used by the corpus generator
# --------------------------------------------------------------------------
def _cell_ref(col, row):
    name = ""
    c = col
    while c > 0:
        c, rem = divmod(c - 1, 26)
        name = chr(65 + rem) + name
    return name + str(row)


def _sheet_xml(rows, shared, shared_idx):
    out = [XMLDECL, "<worksheet xmlns=" + _q(NS_MAIN) + "><sheetData>"]
    for r, row in enumerate(rows, start=1):
        out.append("<row r=" + _q(r) + ">")
        for c, value in enumerate(row, start=1):
            ref = _cell_ref(c, r)
            text = "" if value is None else str(value)
            if text == "":
                continue
            if isinstance(value, int) and not isinstance(value, bool):
                out.append("<c r=" + _q(ref) + "><v>" + text + "</v></c>")
                continue
            if text not in shared_idx:
                shared_idx[text] = len(shared)
                shared.append(text)
            out.append("<c r=" + _q(ref) + " t=" + _q("s") + "><v>"
                       + str(shared_idx[text]) + "</v></c>")
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def _zip_parts(path, parts):
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
    ct.append("<Default Extension=" + _q("xml") + " ContentType="
              + _q("application/xml") + "/>")
    ct.append("<Override PartName=" + _q("/xl/workbook.xml") + " ContentType="
              + _q(CT_SHEETML + ".sheet.main+xml") + "/>")
    ct.append("<Override PartName=" + _q("/xl/sharedStrings.xml") + " ContentType="
              + _q(CT_SHEETML + ".sharedStrings+xml") + "/>")
    for i in range(1, len(sheets) + 1):
        ct.append("<Override PartName=" + _q("/xl/worksheets/sheet" + str(i) + ".xml")
                  + " ContentType=" + _q(CT_SHEETML + ".worksheet+xml") + "/>")
    ct.append("</Types>")

    root_rels = (XMLDECL + "<Relationships xmlns=" + _q(NS_PKGREL) + ">"
                 + "<Relationship Id=" + _q("rId1") + " Type="
                 + _q(NS_REL + "/officeDocument")
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
        wr.append("<Relationship Id=" + _q("rId" + str(i)) + " Type="
                  + _q(NS_REL + "/worksheet")
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
    _zip_parts(path, parts)


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
    """blocks: (kind, payload) with kind h, p or table."""
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
          + "<Default Extension=" + _q("xml") + " ContentType="
          + _q("application/xml") + "/>"
          + "<Override PartName=" + _q("/word/document.xml") + " ContentType="
          + _q(CT_WORDML + ".document.main+xml") + "/></Types>")
    rels = (XMLDECL + "<Relationships xmlns=" + _q(NS_PKGREL) + ">"
            + "<Relationship Id=" + _q("rId1") + " Type=" + _q(NS_REL + "/officeDocument")
            + " Target=" + _q("word/document.xml") + "/></Relationships>")
    _zip_parts(path, [("[Content_Types].xml", ct), ("_rels/.rels", rels),
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
                        + ", ".join("?" for _ in cols) + ")",
                        [tuple(str(v) for v in row) for row in rows])
    con.commit()
    con.close()


def write_text(path, text):
    if not text.endswith(NL):
        text += NL
    Path(path).write_bytes(text.encode("utf-8"))


def write_lines(path, lines):
    write_text(path, NL.join(str(x) for x in lines))


def write_delim(path, header, rows, sep):
    out = [sep.join(str(h) for h in header)]
    for row in rows:
        out.append(sep.join(str(c) for c in row))
    write_lines(path, out)


def write_jsonl(path, records):
    write_lines(path, [compact_json(r) for r in records])


def write_json(path, obj):
    write_text(path, canonical_json(obj))


# --------------------------------------------------------------------------
# readers used by the reference chain
# --------------------------------------------------------------------------
def _col_to_idx(ref):
    col = 0
    for ch in ref:
        if ch.isalpha():
            col = col * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return col


def read_xlsx_sheets(path):
    """Ordered mapping of sheet name to list of row lists."""
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
    """Text lines of a PDF written by the corpus generator."""
    raw = Path(path).read_bytes()
    out = []
    depth = 0
    cur = []
    esc = False
    for i in range(len(raw)):
        ch = raw[i:i + 1]
        if depth == 0:
            if ch == b"(":
                depth = 1
                cur = []
        else:
            if esc:
                cur.append(ch)
                esc = False
            elif ch == BS.encode("latin-1"):
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
    return out


def read_docx_blocks(path):
    """Paragraph strings and table rows in document order; a table row comes
    back as a list of cell strings."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    out = []
    body = None
    for node in root:
        if node.tag == W_NS + "body":
            body = node
    if body is None:
        return out
    for node in body:
        if node.tag == W_NS + "p":
            out.append("".join(t.text or "" for t in node.iter(W_NS + "t")))
        elif node.tag == W_NS + "tbl":
            for tr in node.findall(W_NS + "tr"):
                out.append(["".join(t.text or "" for t in tc.iter(W_NS + "t"))
                            for tc in tr.findall(W_NS + "tc")])
    return out


def read_sqlite_table(path, table):
    con = sqlite3.connect(str(path))
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM " + table)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        con.close()


def read_delim(path, sep=","):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    lines = [ln for ln in lines if ln.strip() != ""]
    header = lines[0].split(sep)
    return [dict(zip(header, ln.split(sep))) for ln in lines[1:]]


def read_jsonl(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _scalar(value):
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if inner == "":
            return []
        return [_scalar(part) for part in inner.split(",")]
    if len(text) >= 2 and text[0] == Q and text[-1] == Q:
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    try:
        return int(text)
    except ValueError:
        return text


def read_flat_yaml(path):
    """The corpus writes a restricted yaml: scalars, one level of mapping, and
    inline lists in square brackets."""
    out = {}
    section = None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indented = raw.startswith(" ")
        key, _sep, value = raw.strip().partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            if indented and section is not None:
                out[section][key] = {}
            else:
                section = key
                out[section] = {}
            continue
        parsed = _scalar(value)
        if indented and section is not None:
            out[section][key] = parsed
        else:
            out[key] = parsed
    return out


def read_conf(path):
    """Sectioned key equals value file with hash comments."""
    out = {}
    section = "default"
    out[section] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            out.setdefault(section, {})
            continue
        key, _sep, value = line.partition("=")
        out[section][key.strip()] = value.strip()
    return out


def read_flat_toml(path):
    out = {}
    section = "root"
    out[section] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            out.setdefault(section, {})
            continue
        key, _sep, value = line.partition("=")
        out[section][key.strip()] = _scalar(value)
    return out


def read_xml_rows(path, tag):
    root = ET.parse(str(path)).getroot()
    return [dict(node.attrib) for node in root.iter(tag)]


def _int(text):
    return int(str(text).strip())


# --------------------------------------------------------------------------
# the corpus generator
#
# One round of the yard's replan desk: six precincts, their berth jobs, the
# precedence edges between them, the exclusive slot groups, the pool capacity
# history, the conditional charge rules and the amendment journal the desk
# lodged during the round. Every table below is minted from one seed and
# written out as the working papers; nothing about the round exists outside
# the directory the papers land in.
# --------------------------------------------------------------------------
POOLS = ["berth_quarter_days", "crane_lifts", "crew_minutes"]

PRECINCT_SHAPES = [
    ("PCT-ALG", "Aldergrave", "chain"),
    ("PCT-BRH", "Brinehead", "diamond"),
    ("PCT-CDW", "Calderwick", "fanin"),
    ("PCT-DNM", "Dunmarsh", "scatter"),
    ("PCT-ELS", "Elmshoal", "boundary"),
    ("PCT-FNW", "Fenwick", "tie"),
]

CLASSES = ["A", "B", "C", "D"]

LICENCE_CODES = ["LIC-HOTWORK", "LIC-CONFINED", "LIC-HIGHLIFT", "LIC-COATING",
                 "LIC-TANKENTRY", "LIC-DIVEOPS", "LIC-SHORELINK"]

TITLE_HEADS = ["hull", "shaft", "rudder", "tank", "valve", "davit", "keel",
               "bilge", "anode", "thruster", "winch", "hatch", "stern",
               "bow", "deck", "sea chest", "propeller", "fairlead"]
TITLE_TAILS = ["survey", "renewal", "blasting", "coating", "clearance",
               "gauging", "alignment", "overhaul", "lift", "strip out",
               "recertification", "seal change", "bearing change"]
OWNERS = ["desk.aldis", "desk.brannon", "desk.corley", "desk.dunnet",
          "desk.ellwood", "desk.fanshaw", "desk.garrity", "desk.hollis"]

SET_ASIDE_ORDER = ["JOB-DRAFTONLY", "JOB-WITHDRAWN", "JOB-NOPRECINCT",
                   "JOB-CYCLE", "JOB-LICENCE", "JOB-OUTOFROUND",
                   "JOB-CLOSUREBLOCKED"]

EDGE_REJECT_ORDER = ["EDG-WITHDRAWN", "EDG-ADVISORY", "EDG-SELF",
                     "EDG-UNKNOWNJOB", "EDG-CROSSPRECINCT", "EDG-DUPLICATE"]

AMENDMENT_KINDS = ["capacity_revision", "carryover_revision",
                   "charge_rule_revision", "class_rate_revision",
                   "edge_lodged", "edge_withdrawn", "group_member_revision",
                   "job_field_revision", "job_note_revision", "restatement",
                   "reversal"]

GOVERNED_JOB_FIELDS = ["base_charge_mills", "berth_quantity", "berth_unit",
                       "class", "crane_lifts", "crew_quantity", "crew_unit",
                       "deferral_weight", "earliest_round", "latest_round",
                       "licence_code", "precinct", "standing"]

PRESENTATION_JOB_FIELDS = ["display_order", "note", "owner", "title"]


def _job_id(precinct_index, n):
    return "JOB-" + str(1000 + 100 * precinct_index + n)


def _title(rng):
    return rng.pick(TITLE_HEADS) + " " + rng.pick(TITLE_TAILS)


def _skeleton(shape, ids):
    """Precedence edges inside one precinct, before any amendment.

    Each shape plants one graph the replan has to reason over: a chain that
    carries a change several levels downstream, a diamond that shares a
    prerequisite between two routes, a fan in that hangs five jobs off one
    hub, a scatter that holds a cycle and a self edge, and two small shapes
    that carry the capacity boundary and the objective tie.
    """
    e = []
    if shape == "chain":
        for i in range(1, 5):
            e.append((ids[i], ids[i - 1]))
        e.append((ids[8], ids[6]))
        e.append((ids[9], ids[5]))
    elif shape == "diamond":
        e.append((ids[0], ids[1]))
        e.append((ids[0], ids[2]))
        e.append((ids[1], ids[3]))
        e.append((ids[2], ids[3]))
        e.append((ids[4], ids[0]))
        e.append((ids[6], ids[5]))
    elif shape == "fanin":
        for i in range(1, 6):
            e.append((ids[i], ids[0]))
        e.append((ids[6], ids[1]))
    elif shape == "scatter":
        e.append((ids[1], ids[2]))
        e.append((ids[2], ids[4]))
    elif shape == "boundary":
        e.append((ids[1], ids[0]))
        e.append((ids[3], ids[2]))
    else:
        e.append((ids[4], ids[3]))
    return e


def _seat_ranking_keys(E):
    """Seat a three way tie in the first precinct, so the objective has to
    reach past the charge and past the weighted resource to settle a round.

    Three jobs of that precinct stand together in one binding slot group, so
    exactly one of them can be taken. All three come to the same charge and
    draw the same three pools, so the first two ranking keys are level across
    them. One opens an optional job through its closure, and it is the one
    canonical job order puts first, so the count of optional jobs is the only
    key that turns it down. Of the two left, the one canonical order prefers
    is the one the mask reaches second, so a round that settles a level tie by
    the order it examined the subsets in takes the other.
    """
    ids = E["precincts"][0]["jobs"]
    by = E["by_id"]
    bp = E["class_rate"]["C"]
    weight = 6
    penalty = E["deferral_rate"]["C"] * weight
    common = {"class": "C", "standing": "charter", "crew_unit": "minute",
              "berth_unit": "quarter_day", "deferral_weight": weight,
              "licence_code": "LIC-HOTWORK",
              "earliest_round": E["round_index"] - 2,
              "latest_round": E["round_index"] + 2}

    # the rival that opens an optional job, and the optional job itself
    opener = dict(common, standing="optional", base_charge=12000,
                  crew_quantity=300, berth_quantity=2, crane_lifts=1)
    optional_rival = dict(common, base_charge=20000, crew_quantity=500,
                          berth_quantity=3, crane_lifts=2)
    level = _charge_for(opener["base_charge"], bp) + _charge_for(
        optional_rival["base_charge"], bp)

    # the rival that stands on its own, at that same charge and draw
    lone = dict(common,
                base_charge=_base_for(level, bp),
                crew_quantity=(opener["crew_quantity"]
                               + optional_rival["crew_quantity"]),
                berth_quantity=(opener["berth_quantity"]
                                + optional_rival["berth_quantity"]),
                crane_lifts=(opener["crane_lifts"]
                             + optional_rival["crane_lifts"]))

    # the rival that opens a charter job. That job is dear enough that the
    # round would never take it on its own, so the only way it enters the
    # closed set is behind the rival that names it.
    carried_charge = penalty + level // 2
    carried = dict(common, base_charge=_base_for(carried_charge, bp),
                   crew_quantity=600, berth_quantity=4, crane_lifts=2)
    if carried_charge <= penalty:
        raise SystemExit("the carried job is worth taking on its own")
    if level + penalty - carried_charge < 1000:
        raise SystemExit("the rival that names it has no charge left to carry")
    charter_rival = dict(common,
                         base_charge=_base_for(level + penalty - carried_charge,
                                               bp),
                         crew_quantity=(lone["crew_quantity"]
                                        - carried["crew_quantity"]),
                         berth_quantity=(lone["berth_quantity"]
                                         - carried["berth_quantity"]),
                         crane_lifts=(lone["crane_lifts"]
                                      - carried["crane_lifts"]))
    for seat in (lone, carried, charter_rival):
        if seat["base_charge"] is None:
            raise SystemExit("no whole base charge scales to the level charge")

    by[ids[5]].update(opener)
    by[ids[6]].update(carried)
    by[ids[7]].update(lone)
    by[ids[8]].update(charter_rival)
    by[ids[9]].update(optional_rival)


def mint(seed):
    """Mint one replan round. Returns every table the papers carry."""
    rng = Rng(child_seed(seed, "round"))
    round_index = rng.between(40, 68)
    round_key = "RND-" + str(2300 + rng.between(4, 19)) + "-" + rng.pick(
        ["KETTLE", "MARLOW", "PENRHOS", "STOWE", "VARNEY", "WILDER"])
    E = {
        "seed": seed,
        "round_index": round_index,
        "round_key": round_key,
        "yard": rng.pick(["Nethergate", "Sowerby", "Threpwood", "Ormsgate"])
                + " Slipway",
        "sealed_on": str(2300 + rng.between(4, 19)) + "-0" + str(rng.between(1, 9))
                     + "-" + str(rng.between(10, 28)),
    }
    E["workbook_round_cell"] = "R" + str(round_index) + "-" + round_key.split("-")[2][:3]

    # The control values that stand in the parameter workbook and the board
    # memo and in no other paper. They are minted per round, so an engine
    # holding this round's figures inside itself is wrong on the rounds it has
    # not seen. The six lengths are a permutation of one set, so exactly one
    # precinct carries the four hundred and eighty of the retired scale table
    # and the flat reading looks right for that one precinct and wrong for the
    # other five.
    crng = Rng(child_seed(seed, "controls"))
    shifts = [420, 450, 480, 510, 540, 465]
    for i in range(len(shifts) - 1, 0, -1):
        j = crng.below(i + 1)
        shifts[i], shifts[j] = shifts[j], shifts[i]
    if len(set(shifts)) < 2:
        raise SystemExit("the yard would carry one shift length")
    E["shift_minutes"] = shifts

    precincts = []
    jobs = []
    edges = []
    for pi, (code, name, shape) in enumerate(PRECINCT_SHAPES):
        prng = Rng(child_seed(seed, "precinct" + str(pi)))
        count = 9 if shape in ("boundary", "tie") else 10
        ids = [_job_id(pi, n) for n in range(count)]
        precincts.append({
            "code": code,
            "name": name,
            "shape": shape,
            "shift_minutes": E["shift_minutes"][pi],
            "jobs": ids,
        })
        for n, jid in enumerate(ids):
            klass = CLASSES[prng.below(4)]
            optional = prng.chance(7, 20)
            crew_unit = "shift" if prng.chance(1, 2) else "minute"
            crew_q = (prng.between(1, 6) if crew_unit == "shift"
                      else prng.between(240, 2400))
            berth_unit = "day" if prng.chance(1, 2) else "quarter_day"
            berth_q = (prng.between(1, 4) if berth_unit == "day"
                       else prng.between(2, 14))
            jobs.append({
                "job_id": jid,
                "precinct": code,
                "class": klass,
                "standing": "optional" if optional else "charter",
                "base_charge": prng.between(38000, 62000),
                "crew_quantity": crew_q,
                "crew_unit": crew_unit,
                "berth_quantity": berth_q,
                "berth_unit": berth_unit,
                "crane_lifts": prng.between(0, 7),
                "earliest_round": round_index - prng.between(0, 6),
                "latest_round": round_index + prng.between(0, 5),
                "licence_code": prng.pick(LICENCE_CODES),
                "deferral_weight": prng.between(3, 6),
                "title": _title(prng),
                "note": "raised at the " + prng.pick(
                    ["spring", "autumn", "interim", "standing"]) + " sitting",
                "owner": prng.pick(OWNERS),
                "display_order": 10 * (n + 1),
                "revision": prng.between(2, 5),
            })
        for a, b in _skeleton(shape, ids):
            edges.append({"requiring_job": a, "required_job": b,
                          "kind": "hard", "status": "active"})

    E["precincts"] = precincts
    E["jobs"] = jobs
    by_id = {j["job_id"]: j for j in jobs}
    E["by_id"] = by_id
    codes = [p["code"] for p in precincts]

    # the scatter precinct carries a three job cycle and a self edge
    scatter = precincts[3]["jobs"]
    edges.append({"requiring_job": scatter[5], "required_job": scatter[6],
                  "kind": "hard", "status": "active"})
    edges.append({"requiring_job": scatter[6], "required_job": scatter[7],
                  "kind": "hard", "status": "active"})
    edges.append({"requiring_job": scatter[7], "required_job": scatter[5],
                  "kind": "hard", "status": "active"})
    edges.append({"requiring_job": scatter[8], "required_job": scatter[8],
                  "kind": "hard", "status": "active"})

    # a duplicate of one fan in edge, which the withdrawal amendment removes
    fanin = precincts[2]["jobs"]
    E["duplicate_edge"] = (fanin[3], fanin[0])
    edges.append({"requiring_job": fanin[3], "required_job": fanin[0],
                  "kind": "hard", "status": "active"})

    # one advisory edge and one cross precinct edge, both of which the papers
    # say create no prerequisite at all
    edges.append({"requiring_job": precincts[1]["jobs"][7],
                  "required_job": precincts[1]["jobs"][8],
                  "kind": "advisory", "status": "active"})
    edges.append({"requiring_job": precincts[0]["jobs"][9],
                  "required_job": precincts[4]["jobs"][2],
                  "kind": "hard", "status": "active"})
    edges.append({"requiring_job": precincts[5]["jobs"][7],
                  "required_job": "JOB-9903", "kind": "hard", "status": "active"})
    edges.append({"requiring_job": precincts[1]["jobs"][6],
                  "required_job": precincts[1]["jobs"][5],
                  "kind": "hard", "status": "withdrawn"})

    # two rows that fail more than one test, so the first failure decides:
    # advisory stands before self, and self stands before unknown job
    edges.append({"requiring_job": precincts[0]["jobs"][3],
                  "required_job": precincts[0]["jobs"][3],
                  "kind": "advisory", "status": "active"})
    edges.append({"requiring_job": "JOB-9904", "required_job": "JOB-9904",
                  "kind": "hard", "status": "active"})

    erng = Rng(child_seed(seed, "edges"))
    for i, e in enumerate(edges):
        e["edge_id"] = "EDG-" + str(4100 + 7 * i)
        e["raised_round"] = round_index - erng.between(1, 9)
        e["note"] = erng.pick(["desk lodged", "survey lodged", "class lodged",
                               "carried from the prior round"])
    E["edges"] = edges

    # exclusive slot groups
    grng = Rng(child_seed(seed, "groups"))
    groups = []
    groups.append({"group_id": "GRP-201", "precinct": codes[1], "precedence": 10,
                   "members": [precincts[1]["jobs"][4], precincts[1]["jobs"][7]]})
    groups.append({"group_id": "GRP-202", "precinct": codes[2], "precedence": 20,
                   "members": [precincts[2]["jobs"][2], precincts[2]["jobs"][4],
                               precincts[2]["jobs"][7]]})
    groups.append({"group_id": "GRP-203", "precinct": codes[3], "precedence": 30,
                   "members": [precincts[3]["jobs"][0], precincts[3]["jobs"][3]]})
    groups.append({"group_id": "GRP-204", "precinct": codes[3], "precedence": 40,
                   "members": [precincts[3]["jobs"][3]]})
    groups.append({"group_id": "GRP-205", "precinct": codes[5], "precedence": 50,
                   "members": [precincts[5]["jobs"][1], precincts[5]["jobs"][2]]})
    groups.append({"group_id": "GRP-206", "precinct": codes[0], "precedence": 60,
                   "members": [precincts[0]["jobs"][7], precincts[0]["jobs"][8],
                               precincts[0]["jobs"][9]]})
    groups.append({"group_id": "GRP-207", "precinct": codes[3], "precedence": 30,
                   "members": [precincts[3]["jobs"][0], precincts[3]["jobs"][4],
                               precincts[3]["jobs"][9]]})
    groups.append({"group_id": "GRP-208", "precinct": codes[3], "precedence": 25,
                   "members": [precincts[3]["jobs"][9]]})
    E["groups"] = groups
    E["double_booked"] = (precincts[3]["jobs"][3], "GRP-204")
    E["single_member_group"] = "GRP-204"
    E["amended_group"] = "GRP-206"

    # licences
    lic = []
    for i, code in enumerate(LICENCE_CODES):
        state = "valid"
        if code == "LIC-DIVEOPS":
            state = "lapsed"
        lic.append({"licence_code": code, "state": state,
                    "valid_from_round": round_index - 20 + i,
                    "valid_to_round": round_index + 12 - i,
                    "note": "issued by the marine surveyor"})
    E["licences"] = lic

    # pool capacities and carried commitments, engineered later for the
    # boundary precinct
    cap = {}
    crng = Rng(child_seed(seed, "capacity"))
    for pi, p in enumerate(precincts):
        cap[p["code"]] = {
            "crew_minutes": crng.between(38, 62) * 240,
            "berth_quarter_days": crng.between(30, 48),
            "crane_lifts": crng.between(16, 26),
        }
    E["capacity"] = cap

    carry = []
    for pi, p in enumerate(precincts):
        for pool in POOLS:
            carry.append({
                "commitment_id": "CMT-" + str(700 + 10 * pi + POOLS.index(pool)),
                "precinct": p["code"],
                "pool": pool,
                "quantity": {"crew_minutes": crng.between(2, 9) * 120,
                             "berth_quarter_days": crng.between(1, 5),
                             "crane_lifts": crng.between(0, 4)}[pool],
                "state": "binding",
            })
    carry.append({"commitment_id": "CMT-799", "precinct": codes[2],
                  "pool": "crane_lifts", "quantity": 9, "state": "released"})
    E["carryover"] = carry

    # class charge multipliers, in basis points
    E["class_rate"] = {k: v + crng.between(-3, 3) * 50 for k, v in
                       (("A", 10850), ("B", 10400), ("C", 9900), ("D", 9650))}

    # the values that live in no plain text paper. None of the pool weights can
    # come out flat, which is the reading the retired scale table carries, and
    # the retention never reaches the forty eight of the rescinded sitting.
    E["pool_weights"] = {"berth_quarter_days": (crng.between(23, 27), 1),
                         "crane_lifts": (crng.between(6, 8), 1),
                         "crew_minutes": (1, crng.between(57, 63))}
    E["deferral_rate"] = {k: v + crng.between(-6, 6) * 100 for k, v in
                          (("A", 17400), ("B", 16100), ("C", 14800),
                           ("D", 13500))}
    E["retention"] = crng.between(30, 34)
    E["ceiling"] = crng.between(118, 124) * 1000

    _seat_ranking_keys(E)

    # conditional charge rules
    rules = []
    rules.append({"rule_id": "CCR-301", "precinct": codes[0],
                  "kind": "pair_surcharge",
                  "first_job": precincts[0]["jobs"][2],
                  "second_job": precincts[0]["jobs"][4],
                  "amount_text": "4,800 mills"})
    rules.append({"rule_id": "CCR-302", "precinct": codes[1],
                  "kind": "threshold_surcharge", "pool": "crane_lifts",
                  "threshold": 9, "class": "B", "amount_text": "1.75 GBP"})
    rules.append({"rule_id": "CCR-303", "precinct": codes[2],
                  "kind": "closure_rebate",
                  "anchor_job": precincts[2]["jobs"][6],
                  "rebate_bp": 1200, "amount_text": "0"})
    rules.append({"rule_id": "CCR-304", "precinct": codes[4],
                  "kind": "pair_surcharge",
                  "first_job": precincts[4]["jobs"][0],
                  "second_job": precincts[4]["jobs"][1],
                  "amount_text": "2600"})
    rules.append({"rule_id": "CCR-305", "precinct": codes[5],
                  "kind": "threshold_surcharge", "pool": "berth_quarter_days",
                  "threshold": 11, "class": "C", "amount_text": "2,150 mills"})
    rules.append({"rule_id": "CCR-306", "precinct": codes[3],
                  "kind": "closure_rebate",
                  "anchor_job": precincts[3]["jobs"][1],
                  "rebate_bp": 900, "amount_text": "0"})
    rules.append({"rule_id": "CCR-307", "precinct": codes[2],
                  "kind": "pair_surcharge",
                  "first_job": precincts[2]["jobs"][0],
                  "second_job": precincts[2]["jobs"][1],
                  "amount_text": "3,150 mills"})
    rules.append({"rule_id": "CCR-308", "precinct": codes[3],
                  "kind": "pair_surcharge",
                  "first_job": precincts[3]["jobs"][2],
                  "second_job": precincts[3]["jobs"][4],
                  "amount_text": "1.900 GBP"})
    for r in rules:
        r["state"] = "in_force"
        r["revision"] = 1
        r["note"] = "carried from the standing schedule"
        r["author"] = "desk.corley"
    E["rules"] = rules
    return E


# --------------------------------------------------------------------------
# the registers
#
# Every register carries its own revision history, so the row in force has to
# be picked out of a file that also holds superseded rows, rows sealed for a
# later round and rows that were withdrawn. The current copy of the job
# register is the drafting copy and is never in force.
# --------------------------------------------------------------------------
JOB_HEADER = ["job_id", "revision", "state", "sealed_round", "precinct",
              "class", "standing", "base_charge_mills", "crew_quantity",
              "crew_unit", "berth_quantity", "berth_unit", "crane_lifts",
              "earliest_round", "latest_round", "licence_code",
              "deferral_weight", "title", "note", "owner", "display_order"]


def _job_row(job, revision, state, sealed_round, shift=0):
    """One register row for a job at one revision."""
    return [job["job_id"], revision, state, sealed_round, job["precinct"],
            job["class"], job["standing"],
            job["base_charge"] + shift * 700,
            job["crew_quantity"] + (shift if job["crew_unit"] == "shift"
                                    else shift * 30),
            job["crew_unit"],
            job["berth_quantity"] + shift, job["berth_unit"],
            max(0, job["crane_lifts"] + shift),
            job["earliest_round"], job["latest_round"], job["licence_code"],
            job["deferral_weight"], job["title"], job["note"], job["owner"],
            job["display_order"]]


def _decoy_jobs(E, rng):
    """Jobs the papers carry that the round never selects, one per set aside
    reason the catalogue names."""
    ri = E["round_index"]
    out = []
    base = {"class": "B", "standing": "charter", "base_charge": 44000,
            "crew_quantity": 3, "crew_unit": "shift", "berth_quantity": 2,
            "berth_unit": "day", "crane_lifts": 2,
            "earliest_round": ri - 3, "latest_round": ri + 3,
            "licence_code": "LIC-COATING", "deferral_weight": 4,
            "note": "carried by the standing schedule", "owner": OWNERS[0],
            "display_order": 950}
    bp = E["class_rate"]["B"]

    def _base_at(target):
        """The whole base charge whose class B scaled charge is this figure."""
        return (int(target) * 10000 + bp // 2) // bp

    live = E["precincts"][0]["code"]
    out.append(dict(base, job_id="JOB-9001", precinct=live,
                    title="quarter berth strip out", kind="draft_only"))
    out.append(dict(base, job_id="JOB-9002", precinct=live,
                    title="forepeak tank gauging", kind="withdrawn"))
    out.append(dict(base, job_id="JOB-9003", precinct="PCT-ZZZ",
                    title="offsite crane recertification", kind="no_precinct"))
    # its scaled charge lands between the ceiling of the rescinded sitting and
    # the ceiling in force, so the two sittings disagree on whether it is
    # reported and the ceiling has to be read off the right one
    out.append(dict(base, job_id="JOB-9004", precinct=E["precincts"][1]["code"],
                    title="dive team shell survey", licence_code="LIC-DIVEOPS",
                    base_charge=_base_at(E["ceiling"] - 15000),
                    kind="lapsed_licence"))
    out.append(dict(base, job_id="JOB-9005", precinct=E["precincts"][2]["code"],
                    title="late season anode renewal",
                    earliest_round=ri + 2, latest_round=ri + 6,
                    kind="out_of_round"))
    out.append(dict(base, job_id="JOB-9006", precinct=E["precincts"][4]["code"],
                    title="sealed for the following round",
                    kind="future_only"))
    # both admissibility tests fail on this one, so the order stage p04 puts
    # them in is what decides the reason it is published under
    # and this one stands above both ceilings, so the report fires whichever
    # sitting is read and a round that never reads a ceiling at all is wrong
    out.append(dict(base, job_id="JOB-9007", precinct=E["precincts"][3]["code"],
                    title="winter dive survey on a lapsed ticket",
                    licence_code="LIC-DIVEOPS",
                    base_charge=_base_at(E["ceiling"] + 150000),
                    earliest_round=ri + 2, latest_round=ri + 6,
                    kind="lapsed_and_out_of_round"))
    return out


def write_job_registers(dest, E):
    rng = Rng(child_seed(E["seed"], "registers"))
    ri = E["round_index"]
    frozen = []
    current = []
    for job in E["jobs"]:
        top = job["revision"]
        for rev in range(1, top + 1):
            sealed = ri - 4 * (top - rev) - (0 if rev == top else 1)
            if rev == top and job["job_id"].endswith("00"):
                sealed = ri
            frozen.append(_job_row(job, rev, "sealed", sealed,
                                   shift=0 if rev == top else (top - rev)))
        # one row sealed for a later round, which this round never reads
        frozen.append(_job_row(job, top + 1, "sealed", ri + rng.between(1, 4),
                               shift=3))
        # the drafting copy carries a further revision that is not in force
        for rev in range(1, top + 1):
            current.append(_job_row(job, rev, "sealed", ri - 4 * (top - rev),
                                    shift=0 if rev == top else (top - rev)))
        current.append(_job_row(job, top + 1, "draft", ri, shift=2))

    for decoy in _decoy_jobs(E, rng):
        kind = decoy.pop("kind")
        if kind == "draft_only":
            frozen.append(_job_row(decoy, 1, "draft", ri - 2))
            frozen.append(_job_row(decoy, 2, "draft", ri - 1))
        elif kind == "withdrawn":
            frozen.append(_job_row(decoy, 1, "sealed", ri - 6))
            frozen.append(_job_row(decoy, 2, "withdrawn", ri - 2))
        elif kind == "future_only":
            frozen.append(_job_row(decoy, 1, "sealed", ri + 2))
        else:
            frozen.append(_job_row(decoy, 1, "sealed", ri - 5))
            frozen.append(_job_row(decoy, 2, "sealed", ri - 3))
        current.append(_job_row(decoy, 1, "sealed", ri - 5))

    frozen.sort(key=lambda r: (str(r[0]), int(r[1])))
    current.sort(key=lambda r: (str(r[0]), int(r[1])))
    write_delim(dest / "berth_job_register_frozen.csv", JOB_HEADER, frozen, ",")
    write_delim(dest / "berth_job_register_current.csv", JOB_HEADER, current, ",")


def write_crosswalk(dest, E):
    rng = Rng(child_seed(E["seed"], "crosswalk"))
    rows = []
    for job in E["jobs"]:
        legacy = "OLD-" + job["job_id"].split("-")[1]
        rows.append([legacy, job["job_id"], "active", "carried from the yard book"])
    for i in range(150):
        legacy = "OLD-" + str(7000 + 3 * i)
        rows.append([legacy, "JOB-" + str(8000 + 3 * i),
                     "withdrawn" if i % 4 else "active",
                     rng.pick(["prior round", "merged berth", "renumbered",
                               "closed by the desk"])])
    rows.sort(key=lambda r: r[0])
    write_delim(dest / "identifier_crosswalk.tsv",
                ["legacy_id", "canonical_id", "status", "note"], rows, TAB)


def write_edge_journal(dest, E):
    rng = Rng(child_seed(E["seed"], "edgefile"))
    rows = []
    for e in E["edges"]:
        rows.append([e["edge_id"], e["requiring_job"], e["required_job"],
                     e["kind"], e["status"], e["raised_round"], e["note"]])
    for i in range(170):
        rows.append(["EDG-" + str(6000 + 5 * i),
                     "JOB-" + str(8000 + 3 * i),
                     "JOB-" + str(8003 + 3 * i),
                     rng.pick(["hard", "advisory"]),
                     rng.pick(["withdrawn", "withdrawn", "lapsed"]),
                     E["round_index"] - rng.between(10, 60),
                     rng.pick(["prior round", "closed with the berth",
                               "superseded by the standing schedule"])])
    rows.sort(key=lambda r: r[0])
    write_delim(dest / "precedence_edge_journal.psv",
                ["edge_id", "requiring_job", "required_job", "kind", "status",
                 "raised_round", "note"], rows, PIPE)


def write_groups(dest, E):
    rng = Rng(child_seed(E["seed"], "groupfile"))
    rows = []
    for g in E["groups"]:
        for member in g["members"]:
            rows.append([g["group_id"], member, g["precinct"], g["precedence"],
                         "open", "lodged by the berth desk"])
    # the double booked member, which the later group loses
    dbl_job, dbl_group = E["double_booked"]
    for i in range(190):
        rows.append(["GRP-" + str(1000 + 7 * i),
                     "JOB-" + str(8000 + 3 * (i % 150)),
                     PRECINCT_SHAPES[i % 6][0], 100 + i, "closed",
                     rng.pick(["prior round", "berth closed", "group retired"])])
    rows.sort(key=lambda r: (r[0], r[1]))
    write_delim(dest / "exclusive_slot_groups.csv",
                ["group_id", "member_job", "precinct", "precedence", "state",
                 "note"], rows, ",")


def write_capacity(dest, E):
    rng = Rng(child_seed(E["seed"], "capfile"))
    ri = E["round_index"]
    rows = []
    for p in E["precincts"]:
        for pool in POOLS:
            live = E["capacity"][p["code"]][pool]
            for k in range(10):
                eff = ri - 4 * (k + 1)
                rows.append([p["code"], pool, eff,
                             live - (k + 1) * (60 if pool == "crew_minutes" else 1),
                             "in_force", "history"])
            eff_live = ri if pool == "crew_minutes" and p["code"] == E["precincts"][4]["code"] else ri - 1
            rows.append([p["code"], pool, eff_live, live, "in_force",
                         "in force for this round"])
            rows.append([p["code"], pool, ri + rng.between(1, 3),
                         live + 400, "rescinded",
                         "rescinded at the board sitting"])
    rows.sort(key=lambda r: (r[0], r[1], int(r[2])))
    write_delim(dest / "pool_capacity_history.tsv",
                ["precinct", "pool", "effective_round", "capacity", "state",
                 "note"], rows, TAB)


def write_carryover(dest, E):
    rng = Rng(child_seed(E["seed"], "carryfile"))
    rows = []
    for c in E["carryover"]:
        rows.append([c["commitment_id"], c["precinct"], c["pool"],
                     c["quantity"], c["state"], "accepted in the prior round"])
    for i in range(190):
        rows.append(["CMT-" + str(2000 + 3 * i), PRECINCT_SHAPES[i % 6][0],
                     POOLS[i % 3], rng.between(20, 900), "discharged",
                     "discharged at the prior round close"])
    rows.sort(key=lambda r: r[0])
    write_delim(dest / "carried_commitment_ledger.csv",
                ["commitment_id", "precinct", "pool", "quantity", "state",
                 "note"], rows, ",")


def write_charge_rules(dest, E):
    rng = Rng(child_seed(E["seed"], "rulefile"))
    rows = []
    for r in E["rules"]:
        rows.append(dict(r))
    for i in range(200):
        rows.append({"rule_id": "CCR-" + str(500 + 3 * i),
                     "precinct": PRECINCT_SHAPES[i % 6][0],
                     "kind": rng.pick(["pair_surcharge", "threshold_surcharge",
                                       "closure_rebate"]),
                     "first_job": "JOB-" + str(8000 + 3 * (i % 150)),
                     "second_job": "JOB-" + str(8003 + 3 * (i % 150)),
                     "anchor_job": "JOB-" + str(8000 + 3 * (i % 150)),
                     "pool": POOLS[i % 3], "threshold": rng.between(4, 30),
                     "class": CLASSES[i % 4], "rebate_bp": rng.between(200, 1800),
                     "amount_text": str(rng.between(400, 9000)),
                     "state": "lapsed", "revision": 1,
                     "note": "lapsed with the prior schedule",
                     "author": rng.pick(OWNERS)})
    rows.sort(key=lambda r: r["rule_id"])
    write_jsonl(dest / "conditional_charge_rules.jsonl", rows)


def write_class_rates(dest, E):
    rng = Rng(child_seed(E["seed"], "classfile"))
    ri = E["round_index"]
    rows = []
    for klass in CLASSES:
        live = E["class_rate"][klass]
        for k in range(48):
            rows.append([klass, ri - 3 * (k + 1), live - 25 * (k + 1),
                         "in_force", "history"])
        rows.append([klass, ri - 2, live, "in_force", "in force for this round"])
        rows.append([klass, ri + rng.between(1, 4), live + 300, "proposed",
                     "put to the board and held over"])
    rows.sort(key=lambda r: (r[0], int(r[1])))
    write_delim(dest / "class_rate_register.csv",
                ["class", "effective_round", "multiplier_bp", "state", "note"],
                rows, ",")


def write_class_vocabulary(dest, E):
    rng = Rng(child_seed(E["seed"], "vocab"))
    rows = []
    labels = {"A": "charter critical", "B": "class driven",
              "C": "condition driven", "D": "opportunity"}
    for i, klass in enumerate(CLASSES):
        rows.append([klass, labels[klass], i + 1, "in_force",
                     "the four classes this round recognises"])
    for i in range(200):
        rows.append(["X" + str(i // 26) + chr(65 + i % 26),
                     rng.pick(["retired scheme", "yard scheme",
                               "owner scheme", "class scheme"]),
                     50 + i, "withdrawn", "withdrawn with the prior scheme"])
    write_delim(dest / "priority_class_vocabulary.csv",
                ["class", "label", "rank", "state", "note"], rows, ",")


def write_licences(dest, E):
    rng = Rng(child_seed(E["seed"], "licfile"))
    rows = []
    for lic in E["licences"]:
        rows.append([lic["licence_code"], lic["state"], lic["valid_from_round"],
                     lic["valid_to_round"], lic["note"]])
    for i in range(200):
        rows.append(["LIC-" + str(3000 + 3 * i),
                     rng.pick(["lapsed", "suspended", "valid"]),
                     E["round_index"] - rng.between(30, 90),
                     E["round_index"] - rng.between(1, 25),
                     "retired by the marine surveyor"])
    write_delim(dest / "licence_validity_register.csv",
                ["licence_code", "state", "valid_from_round", "valid_to_round",
                 "note"], rows, ",")


# --------------------------------------------------------------------------
# the amendment journal
#
# Fourteen amendments reach this round. They are minted so that the journal
# holds one of every kind the classification table names, and so that the
# round exercises an inert change, a change whose normalised value is
# unchanged, a withdrawal that leaves the accepted edge set alone, a
# withdrawal that does not, a change several levels below the job it moves, a
# capacity that lands on the boundary, a reversal of an earlier amendment, a
# repeat of an amendment already applied, and two amendments whose regions
# overlap.
# --------------------------------------------------------------------------
def _amendments(E):
    p = E["precincts"]
    ri = E["round_index"]
    dup_a, dup_b = E["duplicate_edge"]
    dup_edge = None
    seen = 0
    for e in E["edges"]:
        if e["requiring_job"] == dup_a and e["required_job"] == dup_b:
            seen += 1
            if seen == 2:
                dup_edge = e["edge_id"]
    live_edge = None
    for e in E["edges"]:
        if (e["requiring_job"] == p[1]["jobs"][1]
                and e["required_job"] == p[1]["jobs"][3]):
            live_edge = e["edge_id"]
    out = [
        {"amendment_id": "AMD-101", "sequence": 1, "kind": "job_note_revision",
         "payload": {"job_id": p[2]["jobs"][0], "field": "title",
                     "value": "stern tube bearing change"},
         "note": "desk wording put right"},
        {"amendment_id": "AMD-102", "sequence": 2, "kind": "edge_lodged",
         "payload": {"requiring_job": p[0]["jobs"][0],
                     "required_job": p[0]["jobs"][8]},
         "note": "survey found the blasting cannot open before the staging"},
        {"amendment_id": "AMD-103", "sequence": 3, "kind": "capacity_revision",
         "payload": {"precinct": p[4]["code"], "pool": "crew_minutes",
                     "capacity": E["capacity"][p[4]["code"]]["crew_minutes"] - 1},
         "note": "one minute came off the shift allowance"},
        {"amendment_id": "AMD-104", "sequence": 4, "kind": "restatement",
         "payload": {"rule_id": "CCR-301", "amount_text": "4.800 GBP"},
         "note": "the amount was restated in pounds"},
        {"amendment_id": "AMD-105", "sequence": 5, "kind": "edge_withdrawn",
         "payload": {"edge_id": dup_edge},
         "note": "the duplicate lodgement came off the journal"},
        {"amendment_id": "AMD-106", "sequence": 6, "kind": "charge_rule_revision",
         "payload": {"rule_id": "CCR-305"},
         "note": "the berth surcharge was reset at the board sitting"},
        {"amendment_id": "AMD-107", "sequence": 7, "kind": "reversal",
         "payload": {"amendment_id": "AMD-103"},
         "note": "the shift allowance was put back"},
        {"amendment_id": "AMD-108", "sequence": 8, "kind": "edge_withdrawn",
         "payload": {"edge_id": live_edge},
         "note": "the staging no longer gates the shaft draw"},
        {"amendment_id": "AMD-109", "sequence": 9, "kind": "class_rate_revision",
         "payload": {"class": "B", "multiplier_bp": E["class_rate"]["B"] + 150},
         "note": "class B was reset across the yard"},
        {"amendment_id": "AMD-110", "sequence": 10, "kind": "class_rate_revision",
         "payload": {"class": "B", "multiplier_bp": E["class_rate"]["B"] + 150},
         "note": "the same reset was lodged a second time"},
        {"amendment_id": "AMD-111", "sequence": 11,
         "kind": "group_member_revision",
         "payload": {"group_id": E["amended_group"],
                     "member_job": p[0]["jobs"][9], "action": "remove"},
         "note": "the second berth came out of the slot group"},
        {"amendment_id": "AMD-112", "sequence": 12, "kind": "job_field_revision",
         "payload": {"job_id": p[2]["jobs"][0], "field": "crew_quantity"},
         "note": "the survey put more crew on the opening job"},
        {"amendment_id": "AMD-113", "sequence": 13, "kind": "carryover_revision",
         "payload": {"commitment_id": "CMT-721", "quantity": 1},
         "note": "the carried lift count was corrected"},
        {"amendment_id": "AMD-114", "sequence": 14, "kind": "reversal",
         "payload": {"amendment_id": "AMD-112"},
         "note": "the contractor withdrew the revised crew figure"},
        # the two the round turns down. Stage p13 rejects an amendment that
        # names nothing the round holds and one that would close a precedence
        # cycle, so one of each is lodged and both have to move nothing.
        {"amendment_id": "AMD-115", "sequence": 15, "kind": "carryover_revision",
         "payload": {"commitment_id": "CMT-999", "quantity": 12},
         "note": "the desk quoted a commitment this round does not carry"},
        {"amendment_id": "AMD-116", "sequence": 16, "kind": "edge_lodged",
         "payload": {"requiring_job": p[0]["jobs"][1],
                     "required_job": p[0]["jobs"][2], "kind": "hard"},
         "note": "the berth desk lodged the pair the other way round"},
        {"amendment_id": "AMD-117", "sequence": 17, "kind": "reversal",
         "payload": {"amendment_id": "AMD-999"},
         "note": "the reversal names a lodgement of an earlier round"},
        {"amendment_id": "AMD-118", "sequence": 18, "kind": "edge_lodged",
         "payload": {"requiring_job": p[0]["jobs"][0],
                     "required_job": "JOB-9902", "kind": "hard"},
         "note": "the required end was struck off before the round opened"},
        {"amendment_id": "AMD-119", "sequence": 19, "kind": "edge_lodged",
         "payload": {"requiring_job": p[1]["jobs"][0],
                     "required_job": p[1]["jobs"][3]},
         "note": "the dock gate has to open before the shaft draw"},
    ]
    for a in out:
        a["state"] = "lodged"
        a["raised_round"] = ri
        a["raised_by"] = OWNERS[a["sequence"] % len(OWNERS)]
    return out


def write_amendments(dest, E):
    """The journal, the supplement that completes two payloads, and the
    provenance ledger that says which of the two a row is read from."""
    rng = Rng(child_seed(E["seed"], "amendfile"))
    rows = []
    supplement = []
    provenance = []
    for a in E["amendments"]:
        rec = {"amendment_id": a["amendment_id"], "sequence": a["sequence"],
               "kind": a["kind"], "state": a["state"],
               "raised_round": a["raised_round"], "raised_by": a["raised_by"],
               "note": a["note"], "payload": dict(a["payload"])}
        if a["amendment_id"] == "AMD-106":
            supplement.append({"amendment_id": "AMD-106", "field": "amount_text",
                               "value": "3,400 mills", "state": "in_force",
                               "note": "the amount reached the desk late"})
            provenance.append(["AMD-106", "amount_text",
                               "amendment_supplement.ndjson", "in_force",
                               "the journal row carries no amount"])
        if a["amendment_id"] == "AMD-102":
            # the supplement offers a kind and the provenance ledger sends the
            # field back to the journal, so the provenance gate has to refuse it
            supplement.append({"amendment_id": "AMD-102", "field": "kind",
                               "value": "advisory", "state": "in_force",
                               "note": "the desk offered a kind for this lodgement"})
            provenance.append(["AMD-102", "kind", "amendment_journal.jsonl",
                               "in_force", "the lodged row settles the kind"])
        if a["amendment_id"] == "AMD-119":
            # here the provenance ledger does point at the supplement and the
            # supplement row itself is withdrawn, so the state filter refuses it
            supplement.append({"amendment_id": "AMD-119", "field": "kind",
                               "value": "advisory", "state": "withdrawn",
                               "note": "withdrawn before the sitting"})
            provenance.append(["AMD-119", "kind",
                               "amendment_supplement.ndjson", "in_force",
                               "the journal row carries no kind"])
        if a["amendment_id"] == "AMD-112":
            moved = E["by_id"][a["payload"]["job_id"]]
            step = 2 if moved["crew_unit"] == "shift" else 600
            supplement.append({"amendment_id": "AMD-112", "field": "value",
                               "value": str(moved["crew_quantity"] + step),
                               "state": "in_force",
                               "note": "the revised quotation reached the desk late"})
            provenance.append(["AMD-112", "value",
                               "amendment_supplement.ndjson", "in_force",
                               "the journal row carries no value"])
        rows.append(rec)
    for i in range(200):
        rows.append({"amendment_id": "AMD-" + str(300 + 3 * i),
                     "sequence": 100 + i,
                     "kind": AMENDMENT_KINDS[i % len(AMENDMENT_KINDS)],
                     "state": "withdrawn",
                     "raised_round": E["round_index"] - rng.between(1, 40),
                     "raised_by": rng.pick(OWNERS),
                     "note": rng.pick(["withdrawn before the sitting",
                                       "withdrawn by the desk",
                                       "raised against a prior round"]),
                     "payload": {"job_id": "JOB-" + str(8000 + 3 * (i % 150))}})
    rows.sort(key=lambda r: r["amendment_id"])
    write_jsonl(dest / "amendment_journal.jsonl", rows)

    for i in range(200):
        supplement.append({"amendment_id": "AMD-" + str(300 + 3 * i),
                           "field": rng.pick(["value", "amount_text", "note"]),
                           "value": str(rng.between(100, 9000)),
                           "state": "withdrawn",
                           "note": "withdrawn with the amendment it completed"})
    supplement.sort(key=lambda r: (r["amendment_id"], r["field"]))
    write_lines(dest / "amendment_supplement.ndjson",
                [compact_json(r) for r in supplement])

    for i in range(200):
        provenance.append(["AMD-" + str(300 + 3 * i),
                           rng.pick(["value", "amount_text", "note"]),
                           rng.pick(["amendment_journal.jsonl",
                                     "amendment_supplement.ndjson"]),
                           "withdrawn", "prior round"])
    provenance.sort(key=lambda r: (r[0], r[1]))
    write_delim(dest / "row_provenance_ledger.csv",
                ["amendment_id", "field", "source_file", "state", "note"],
                provenance, ",")


def write_reason_catalogue(dest, E):
    rng = Rng(child_seed(E["seed"], "reasons"))
    rows = []
    stage_of = {"JOB-DRAFTONLY": "p01", "JOB-WITHDRAWN": "p01",
                "JOB-NOPRECINCT": "p01", "JOB-CYCLE": "p02",
                "JOB-LICENCE": "p04", "JOB-OUTOFROUND": "p04",
                "JOB-CLOSUREBLOCKED": "p05"}
    for code in SET_ASIDE_ORDER:
        rows.append([code, stage_of[code], "job set aside",
                     "the job takes no part in the replan"])
    for code in EDGE_REJECT_ORDER:
        rows.append([code, "p02", "edge rejected",
                     "the lodgement creates no prerequisite"])
    rows.append(["EDG-CYCLE", "p02", "edge rejected",
                 "the lodgement would close a precedence cycle"])
    rows.append(["GRP-DOUBLEBOOKED", "p08", "group membership rejected",
                 "the job already stands in a group of earlier precedence"])
    rows.append(["GRP-SINGLE", "p08", "group carries no constraint",
                 "a group of one member binds nothing"])
    rows.append(["AMD-NOTARGET", "p13", "amendment rejected",
                 "the reversal names no amendment this round applied"])
    rows.append(["CMT-UNKNOWN", "p13", "amendment rejected",
                 "the commitment named is not binding this round"])
    for i in range(200):
        rows.append(["RET-" + str(400 + 3 * i), "p" + str(1 + i % 14).rjust(2, "0"),
                     rng.pick(["retired", "withdrawn", "superseded"]),
                     "retired with the prior schedule"])
    write_delim(dest / "amendment_reason_catalogue.psv",
                ["reason_code", "stage", "label", "note"], rows, PIPE)


def write_source_priority(dest, E):
    rng = Rng(child_seed(E["seed"], "sources"))
    rows = [["amendment_supplement.ndjson", 10,
             "completes a journal row whose payload field is empty"],
            ["amendment_journal.jsonl", 20, "the lodged payload"],
            ["berth_job_register_frozen.csv", 30, "the register in force"],
            ["berth_job_register_current.csv", 90, "the drafting copy"],
            ["legacy_scale_table.csv", 95, "retired with the prior scheme"]]
    for i in range(200):
        rows.append(["retired_source_" + str(i).rjust(3, "0") + ".csv",
                     200 + i, rng.pick(["prior round", "retired", "closed"])])
    write_delim(dest / "source_priority_register.csv",
                ["source_file", "priority", "note"], rows, ",")


def write_legacy_scale(dest, E):
    """The retired scale table. Its shift lengths and pool weights were
    superseded by the workbook and reading them here reproduces the fault."""
    rng = Rng(child_seed(E["seed"], "legacy"))
    rows = []
    for p in E["precincts"]:
        rows.append([p["code"], "shift_minutes", 480, "retired",
                     "single yard wide shift before the workbook"])
    for pool, num, den in [("berth_quarter_days", 1, 1), ("crane_lifts", 1, 1),
                           ("crew_minutes", 1, 1)]:
        rows.append(["ALL", "weight_" + pool, str(num) + "/" + str(den),
                     "retired", "flat weighting before the workbook"])
    for klass in CLASSES:
        rows.append(["ALL", "deferral_rate_" + klass, 900, "retired",
                     "flat deferral rate before the board memo"])
    for i in range(200):
        rows.append([PRECINCT_SHAPES[i % 6][0], "retired_key_" + str(i),
                     rng.between(100, 900), "retired", "prior scheme"])
    write_delim(dest / "legacy_scale_table.csv",
                ["scope", "key", "value", "state", "note"], rows, ",")


# --------------------------------------------------------------------------
# topology, archive and the three papers that are not plain text
# --------------------------------------------------------------------------
def write_topology(dest, E):
    rng = Rng(child_seed(E["seed"], "topology"))
    live = [XMLDECL, "<yard key=" + _q(E["round_key"]) + " state=" + _q("in_force") + ">"]
    for p in E["precincts"]:
        live.append("<precinct code=" + _q(p["code"]) + " name=" + _q(p["name"])
                    + " state=" + _q("open") + " berths=" + _q(rng.between(3, 7)) + ">")
        for b in range(34):
            live.append("<berth ref=" + _q(p["code"] + "-B" + str(b).rjust(2, "0"))
                        + " length_m=" + _q(rng.between(40, 190))
                        + " draught_dm=" + _q(rng.between(30, 110))
                        + " state=" + _q("open" if b < 30 else "closed") + "/>")
        live.append("</precinct>")
    live.append("</yard>")
    write_lines(dest / "yard_topology.xml", live)

    draft = [XMLDECL, "<yard key=" + _q(E["round_key"] + "-DRAFT")
             + " state=" + _q("draft") + ">"]
    for p in E["precincts"] + [{"code": "PCT-ZZZ", "name": "Zennorgate"}]:
        draft.append("<precinct code=" + _q(p["code"]) + " name=" + _q(p["name"])
                     + " state=" + _q("proposed") + " berths=" + _q(rng.between(3, 9)) + ">")
        for b in range(30):
            draft.append("<berth ref=" + _q(p["code"] + "-D" + str(b).rjust(2, "0"))
                         + " length_m=" + _q(rng.between(40, 190))
                         + " draught_dm=" + _q(rng.between(30, 110))
                         + " state=" + _q("proposed") + "/>")
        draft.append("</precinct>")
    draft.append("</yard>")
    write_lines(dest / "topology_drafts.xml", draft)


def write_archive(dest, E):
    rng = Rng(child_seed(E["seed"], "archive"))
    sel = [[str(E["round_index"] - 1), p["code"], j,
            str(rng.between(20000, 90000)), "accepted"]
           for p in E["precincts"] for j in p["jobs"][:5]]
    counters = [[str(E["round_index"] - 1), p["code"],
                 str(rng.between(4, 30)), str(rng.between(30, 400)),
                 str(rng.between(0, 12))] for p in E["precincts"]]
    for i in range(90):
        counters.append([str(E["round_index"] - 2 - i % 9),
                         PRECINCT_SHAPES[i % 6][0], str(rng.between(4, 30)),
                         str(rng.between(30, 400)), str(rng.between(0, 12))])
    for i in range(160):
        sel.append([str(E["round_index"] - 2 - i % 7),
                    PRECINCT_SHAPES[i % 6][0], "JOB-" + str(8000 + 3 * i),
                    str(rng.between(20000, 90000)),
                    rng.pick(["accepted", "deferred"])])
    amendments = []
    for i in range(210):
        amendments.append([str(E["round_index"] - 1 - i % 12),
                           "AMD-" + str(300 + 3 * i),
                           AMENDMENT_KINDS[i % len(AMENDMENT_KINDS)],
                           str(rng.between(0, 40)), str(rng.between(0, 2048))])
    write_sqlite(dest / "prior_round_archive.db", {
        "prior_amendment_log": (["round_index", "amendment_id", "kind",
                                 "cells_visited", "subsets_examined"],
                                amendments),
        "prior_selection": (["round_index", "precinct", "job_id",
                             "charge_mills", "disposition"], sel),
        "prior_work_counters": (["round_index", "precinct", "cells_visited",
                                 "cells_recomputed", "cache_evictions"],
                                counters),
    })


def _sheet_block(E, live):
    """One workbook sheet. The live sheet is the one whose key cell matches the
    round header; the other carries the superseded scale."""
    rng = Rng(child_seed(E["seed"], "sheet" + ("live" if live else "old")))
    rows = [["sheet_key", E["workbook_round_cell"] if live
             else E["workbook_round_cell"] + "-SUPERSEDED"],
            ["sheet_state", "in_force" if live else "superseded"],
            ["", ""],
            ["section", "precinct_shift_minutes"],
            ["precinct", "shift_minutes"]]
    for p in E["precincts"]:
        rows.append([p["code"], p["shift_minutes"] if live
                     else p["shift_minutes"] - 30])
    rows.append(["", ""])
    rows.append(["section", "pool_weights"])
    rows.append(["pool", "weight_numerator", "weight_denominator"])
    weights = E["pool_weights"] if live else {"berth_quarter_days": (1, 1),
                                              "crane_lifts": (1, 1),
                                              "crew_minutes": (1, 1)}
    for pool in POOLS:
        num, den = weights[pool]
        rows.append([pool, num, den])
    rows.append(["", ""])
    rows.append(["section", "berth_allowances"])
    rows.append(["berth", "precinct", "allowance_quarter_days", "state"])
    for p in E["precincts"]:
        for b in range(34):
            rows.append([p["code"] + "-B" + str(b).rjust(2, "0"), p["code"],
                         rng.between(1, 9), "open" if b < 30 else "closed"])
    return rows


def write_workbook(dest, E):
    write_xlsx(dest / "yard_parameter_workbook.xlsx", {
        "Schedule Q": _sheet_block(E, False),
        "Schedule R": _sheet_block(E, True),
    })


def write_board_memo(dest, E):
    rng = Rng(child_seed(E["seed"], "memo"))
    ri = E["round_index"]
    lines = []
    lines.append(E["yard"].split()[0].upper()
                 + " YARD BOARD  MINUTES OF THE REPLAN SITTINGS")
    lines.append("Round key " + E["round_key"] + "   round index " + str(ri))
    lines.append("")
    lines.append("SITTING " + str(ri - 6) + "  RESCINDED IN FULL AT SITTING " + str(ri - 1))
    lines.append("Resolution " + str(ri - 6) + "-1 RESCINDED  the deferral rate for")
    lines.append("  a charter job left out of the accepted set is charged per weight")
    lines.append("  unit at")
    for klass in CLASSES:
        lines.append("    class " + klass + "  "
                     + str(E["deferral_rate"][klass] - 4200)
                     + " mills per weight unit")
    lines.append("Resolution " + str(ri - 6) + "-2 RESCINDED  the working store retains")
    lines.append("  at most 48 derived entries.")
    lines.append("Resolution " + str(ri - 6) + "-3 RESCINDED  a pool is within its")
    lines.append("  capacity while usage stands below the available quantity.")
    lines.append("Resolution " + str(ri - 6) + "-4 RESCINDED  a charge above "
                 + str(E["ceiling"] - 30000) + " mills is")
    lines.append("  implausible and the job carrying it is reported to the desk.")
    lines.append("")
    for i in range(30):
        lines.append("Minute " + str(ri - 6) + "." + str(i + 1)
                     + "  " + rng.pick([
                         "the berth desk reported on the tide window",
                         "the surveyor reported on the coating trials",
                         "the class society noted the survey backlog",
                         "the owner representative asked after the shaft draw",
                         "the desk reported on the crane maintenance window"]) + ".")
    lines.append("")
    lines.append("SITTING " + str(ri - 1) + "  IN FORCE FOR ROUND " + str(ri))
    lines.append("Resolution " + str(ri - 1) + "-1  the deferral rate for a charter job")
    lines.append("  left out of the accepted set is charged per weight unit at")
    for klass in CLASSES:
        lines.append("    class " + klass + "  " + str(E["deferral_rate"][klass])
                     + " mills per weight unit")
    lines.append("Resolution " + str(ri - 1) + "-2  the working store retains at most")
    lines.append("  " + str(E["retention"]) + " derived entries. The entry read or written")
    lines.append("  longest ago is dropped when a further entry arrives at a full")
    lines.append("  store. Dropping an entry moves no published quantity.")
    lines.append("Resolution " + str(ri - 1) + "-3  a pool stands within its capacity")
    lines.append("  while usage is at or below the available quantity, so usage")
    lines.append("  equal to the available quantity is within capacity.")
    lines.append("Resolution " + str(ri - 1) + "-4  a charge above " + str(E["ceiling"])
                 + " mills is")
    lines.append("  implausible and the job carrying it is reported to the desk.")
    lines.append("Resolution " + str(ri - 1) + "-5  the shift lengths and the pool")
    lines.append("  weights are those of the parameter workbook sheet whose key cell")
    lines.append("  matches the round header. The retired scale table settles nothing.")
    lines.append("")
    for i in range(34):
        lines.append("Minute " + str(ri - 1) + "." + str(i + 1) + "  " + rng.pick([
            "the desk reported on the amendment load",
            "the surveyor reported on the licence renewals",
            "the board noted the carried commitments",
            "the desk reported on the slot groups",
            "the board noted the precedence directive stands unchanged"]) + ".")
    lines.append("")
    lines.append("APPENDIX A  CARRIED COMMITMENT SUMMARY BY PRECINCT")
    for p in E["precincts"]:
        for pool in POOLS:
            lines.append("  " + p["code"] + "  " + pool + "  carried "
                         + str(rng.between(2, 900)) + " units at the prior close")
    lines.append("")
    lines.append("APPENDIX B  SITTING ATTENDANCE")
    for i in range(60):
        lines.append("  " + rng.pick(OWNERS) + " attended sitting "
                     + str(ri - rng.between(1, 9)))
    lines.append("")
    lines.append("APPENDIX C  PRIOR RESOLUTIONS CARRIED FORWARD UNCHANGED")
    for i in range(70):
        lines.append("  Resolution " + str(ri - 6 - i % 11) + "-"
                     + str(20 + i) + " carried forward on "
                     + rng.pick(["berth allocation", "tide windows",
                                 "crane maintenance", "coating trials",
                                 "survey backlog", "licence renewals",
                                 "slot group precedence"]))
    return write_pdf(dest / "yard_board_memo.pdf", lines)


def write_directive(dest, E):
    rng = Rng(child_seed(E["seed"], "directive"))
    blocks = [("h", "PRECEDENCE AND CASCADE DIRECTIVE"),
              ("p", "In force for round " + E["round_key"]
               + ". This directive settles how an amendment reaches the derived"
               + " state, in what order two stages that bear on one job apply,"
               + " and when a cascade stops."),
              ("h", "1 CLASSIFICATION OF AN AMENDMENT"),
              ("p", "Each lodged amendment is classified by its kind. The seed"
               + " set is the derived cell or cells named here and nothing"
               + " else. A cell that is not seeded and is not reached by the"
               + " cascade keeps the value it holds.")]
    table = [["amendment kind", "seed set"],
             ["job_field_revision", "norm cell of the named job"],
             ["job_note_revision", "empty; the fields it moves govern nothing"],
             ["edge_lodged", "closure cell of the requiring job"],
             ["edge_withdrawn", "closure cell of the requiring job on the row"],
             ["group_member_revision", "group cell of the named group"],
             ["capacity_revision", "solve cell of the named precinct"],
             ["carryover_revision", "solve cell of the precinct of the commitment"],
             ["charge_rule_revision", "rule cell of the named rule"],
             ["class_rate_revision", "charge cell of every job of that class"],
             ["restatement", "the cell its kind would seed"],
             ["reversal", "the seed set of the amendment it names"]]
    blocks.append(("table", table))
    blocks.append(("h", "2 WHERE A CASCADE STOPS"))
    blocks.append(("p", "A cell reached by the cascade is computed again. When"
                   + " the value it comes back with carries the digest it"
                   + " already held, the cell is revalidated and the cascade"
                   + " stops there. The cells that stand behind it keep their"
                   + " values and are never visited. When the digest moves, the"
                   + " cells that read this one are reached in turn."))
    blocks.append(("p", "A withdrawal of an edge that leaves the accepted"
                   + " prerequisite list of the requiring job unchanged"
                   + " therefore moves nothing behind that job, and a"
                   + " restatement of an amount whose normalised value is"
                   + " unchanged moves nothing behind the rule."))
    blocks.append(("h", "3 WHICH CELL READS WHICH"))
    blocks.append(("table", [
        ["cell", "the cells it is read by"],
        ["norm of a job", "closure, demand and charge of that job, demand of"
         + " every other job whose closure holds it, group of every group"
         + " holding it, solve of its precinct"],
        ["closure of a job", "demand of that job, closure of every job that"
         + " names it as a prerequisite, solve of its precinct"],
        ["demand of a job", "solve of its precinct"],
        ["charge of a job", "solve of its precinct"],
        ["group", "solve of its precinct"],
        ["solve of a precinct", "nothing"]]))
    blocks.append(("h", "4 ORDER WHERE TWO STAGES BEAR ON ONE JOB"))
    blocks.append(("p", "The class multiplier applies to the base charge before"
                   + " any surcharge is added. The surcharges of a precinct are"
                   + " added next. The closure rebate is taken last, on the sum"
                   + " of the scaled charges and the surcharges of that"
                   + " precinct, and never on the scaled charges alone."))
    blocks.append(("h", "5 DUPLICATE AND REJECTED LODGEMENTS"))
    blocks.append(("p", "Two rows of the edge journal that name the same"
                   + " requiring job and the same required job after the"
                   + " crosswalk is applied are one prerequisite. The second"
                   + " row is rejected as a duplicate and withdrawing either"
                   + " row while the other stands leaves the prerequisite in"
                   + " place."))
    blocks.append(("p", "A job that stands in two open slot groups keeps the"
                   + " group of the lower precedence number, whichever of the"
                   + " two identifiers that group carries, and keeps the group"
                   + " of the lower identifier where the two carry one"
                   + " precedence number. Its membership of the other group is"
                   + " rejected. A group left holding one open member binds"
                   + " nothing at all."))
    blocks.append(("h", "6 PRIOR DIRECTIVES WITHDRAWN BY THIS ONE"))
    prior = [["directive", "sitting", "subject", "state"]]
    for i in range(200):
        prior.append(["DIR-" + str(600 + 3 * i), str(E["round_index"] - 1 - i % 40),
                      rng.pick(["cascade depth", "seed sets", "rebate order",
                                "duplicate lodgements", "store retention",
                                "group precedence"]), "withdrawn"])
    blocks.append(("table", prior))
    write_docx(dest / "cascade_precedence_directive.docx", blocks)


# --------------------------------------------------------------------------
# the reference chain
#
# Fourteen stages, written flat here so the verifier owns a derivation that
# does not share a line with the package the agent repairs. Nothing below
# reads a value the agent cannot read: every constant it uses is loaded out of
# the paper directory it is handed.
# --------------------------------------------------------------------------
LAYERS = ["norm", "rule", "closure", "demand", "charge", "group", "solve"]
LAYER_RANK = {name: i for i, name in enumerate(LAYERS)}

ARTIFACT_NAMES = [
    "01_identifier_canon.json", "02_precedence_edges.tsv",
    "03_reverse_index.json", "04_normalised_jobs.csv",
    "05_normalised_rules.csv", "06_feasibility_map.csv",
    "07_closure_map.jsonl", "08_demand_vectors.csv",
    "09_conflict_groups.json", "10_charge_contributions.csv",
    "11_baseline_selection.json", "12_baseline_trace.jsonl",
    "13_amendment_classification.csv", "14_invalidation_sets.jsonl",
    "15_reuse_ledger.csv", "16_work_counters.csv", "17_cache_summary.json",
    "18_final_selection.json", "19_rejected_register.csv",
    "20_resource_usage.tsv", "21_amendment_optima.csv",
    "22_defect_register.md", "23_verification_notes.md",
    "24_run_manifest.txt", "25_summary.json",
]

PACKAGE_MODULES = ["__init__", "__main__", "cache", "cells", "charge",
                   "closure", "graph", "mutate", "normalise", "objective",
                   "publish", "reading", "search"]


def amount_mills(text):
    """Stage p03. One amount, however the desk wrote it, as whole mills."""
    raw = str(text).strip().replace(",", "")
    if raw == "":
        return 0
    parts = raw.split()
    number = parts[0]
    unit = parts[1].lower() if len(parts) > 1 else "mills"
    if unit == "gbp":
        if "." in number:
            whole, frac = number.split(".", 1)
            return int(whole) * 1000 + int((frac + "000")[:3])
        return int(number) * 1000
    if "." in number:
        whole, frac = number.split(".", 1)
        if int(frac) != 0:
            raise ValueError("an amount in mills carries no fraction")
        return int(whole)
    return int(number)


def ref_params(root):
    """Stage p01 parameter layer, three of which are not plain text."""
    root = Path(root)
    header = read_json(root / "round_header.json")
    ri = int(header["round_index"])

    sheets = read_xlsx_sheets(root / "yard_parameter_workbook.xlsx")
    live_rows = None
    for name in sorted(sheets):
        rows = sheets[name]
        for row in rows:
            if row and str(row[0]) == "sheet_key":
                if str(row[1]) == str(header["workbook_round_cell"]):
                    live_rows = rows
                break
    if live_rows is None:
        raise SystemExit("no workbook sheet carries the round key cell")
    shift_minutes = {}
    weights = {}
    legacy = {}
    for row in read_delim(root / "legacy_scale_table.csv"):
        legacy[(row["scope"], row["key"])] = row["value"]
    section = ""
    for row in live_rows:
        if not row:
            continue
        head = str(row[0])
        if head == "section":
            section = str(row[1])
            continue
        if section == "precinct_shift_minutes" and head.startswith("PCT-"):
            shift_minutes[head] = int(row[1])
        elif section == "pool_weights" and head in POOLS:
            weights[head] = (int(row[1]), int(row[2]))

    lines = read_pdf_lines(root / "yard_board_memo.pdf")
    rescinded = "R_RESCINDED_MEMO" in WRONG
    live = []
    holding = False
    for line in lines:
        if "RESCINDED IN FULL" in line:
            holding = rescinded
            continue
        if "IN FORCE FOR ROUND" in line:
            holding = not rescinded
            continue
        if line.startswith("APPENDIX"):
            holding = False
        if holding:
            live.append(line)
    deferral = {}
    retention = 0
    ceiling = 0
    for line in live:
        words = line.split()
        if len(words) >= 3 and words[0] == "class" and words[1] in CLASSES:
            deferral[words[1]] = int(words[2])
        if "derived entries" in line:
            retention = int([w for w in words if w.isdigit()][0])
        if "a charge above" in line:
            ceiling = int([w for w in words if w.isdigit()][0])
    if len(deferral) != len(CLASSES) or retention <= 0 or ceiling <= 0:
        raise SystemExit("the board memo did not settle the round parameters")
    if "R_FLAT_SHIFT" in WRONG:
        flat = int(legacy[(sorted(shift_minutes)[0], "shift_minutes")])
        shift_minutes = {k: flat for k in shift_minutes}
    if "R_LEGACY_WEIGHTS" in WRONG:
        weights = {pool: (1, 1) for pool in POOLS}


    rates = {}
    for row in read_delim(root / "class_rate_register.csv"):
        if row["state"] != "in_force" or int(row["effective_round"]) > ri:
            continue
        cur = rates.get(row["class"])
        if cur is None or int(row["effective_round"]) >= cur[0]:
            rates[row["class"]] = (int(row["effective_round"]),
                                   int(row["multiplier_bp"]))
    class_bp = {k: v[1] for k, v in rates.items()}

    licences = {}
    for row in read_delim(root / "licence_validity_register.csv"):
        licences[row["licence_code"]] = row

    precincts = [node["code"] for node in read_xml_rows(root / "yard_topology.xml",
                                                        "precinct")]
    return {"round_index": ri, "round_key": header["round_key"],
            "shift_minutes": shift_minutes, "pool_weights": weights,
            "deferral_rate": deferral, "retention": retention,
            "ceiling": ceiling, "class_bp": class_bp, "licences": licences,
            "precincts": precincts, "header": header}


def ref_aliases(root):
    out = {}
    for row in read_delim(Path(root) / "identifier_crosswalk.tsv", TAB):
        if row["status"] == "active":
            out[row["legacy_id"]] = row["canonical_id"]
    return out


def ref_register(root, params, aliases):
    """Stage p01. The rows in force out of the frozen register."""
    ri = params["round_index"]
    best = {}
    source = ("berth_job_register_current.csv" if "R_CURRENT_REGISTER" in WRONG
              else "berth_job_register_frozen.csv")
    for row in read_delim(Path(root) / source):
        jid = aliases.get(row["job_id"], row["job_id"])
        if row["state"] not in ("sealed", "withdrawn"):
            continue
        if int(row["sealed_round"]) > ri:
            continue
        cur = best.get(jid)
        if cur is None or int(row["revision"]) > int(cur["revision"]):
            best[jid] = dict(row, job_id=jid)
    jobs = {}
    aside = []
    for jid in sorted(best):
        row = best[jid]
        if row["state"] == "withdrawn":
            aside.append((jid, "JOB-WITHDRAWN", row["precinct"]))
            continue
        if row["precinct"] not in params["precincts"]:
            aside.append((jid, "JOB-NOPRECINCT", row["precinct"]))
            continue
        jobs[jid] = row
    seen = set(best)
    drafted = set()
    for row in read_delim(Path(root) / source):
        jid = aliases.get(row["job_id"], row["job_id"])
        if jid not in seen:
            drafted.add(jid)
    for jid in sorted(drafted):
        aside.append((jid, "JOB-DRAFTONLY", ""))
    return jobs, aside


def ref_edge_journal(root, jobs, aliases):
    """Stage p02. The accepted prerequisite list of every job, and one row per
    lodgement the papers reject."""
    rows = read_delim(Path(root) / "precedence_edge_journal.psv", PIPE)
    accepted = {}
    rejected = []
    seen = set()
    for row in rows:
        req = aliases.get(row["requiring_job"], row["requiring_job"])
        dep = aliases.get(row["required_job"], row["required_job"])
        eid = row["edge_id"]
        if row["status"] != "active":
            rejected.append((eid, req, dep, "EDG-WITHDRAWN"))
            continue
        if row["kind"] != "hard" and "R_ADVISORY_EDGE" not in WRONG:
            rejected.append((eid, req, dep, "EDG-ADVISORY"))
            continue
        if req == dep:
            rejected.append((eid, req, dep, "EDG-SELF"))
            continue
        if req not in jobs or dep not in jobs:
            rejected.append((eid, req, dep, "EDG-UNKNOWNJOB"))
            continue
        if jobs[req]["precinct"] != jobs[dep]["precinct"]:
            rejected.append((eid, req, dep, "EDG-CROSSPRECINCT"))
            continue
        if (req, dep) in seen and "R_DUP_NOT_DEDUPED" not in WRONG:
            rejected.append((eid, req, dep, "EDG-DUPLICATE"))
            continue
        seen.add((req, dep))
        accepted.setdefault(req, []).append(dep)
    for req in accepted:
        accepted[req].sort()
    return accepted, rejected


def ref_rules(root, params):
    aliases = ref_aliases(root)
    out = {}
    for rec in read_jsonl(Path(root) / "conditional_charge_rules.jsonl"):
        if rec.get("state") != "in_force":
            continue
        rec = dict(rec)
        for field in JOB_FIELDS_OF_RULES:
            if isinstance(rec.get(field), str):
                rec[field] = aliases.get(rec[field], rec[field])
        out[rec["rule_id"]] = rec
    return out


JOB_FIELDS_OF_RULES = ("first_job", "second_job", "anchor_job")
JOB_FIELDS_OF_PAYLOADS = ("job_id", "requiring_job", "required_job",
                          "member_job")


def ref_capacity(root, params):
    ri = params["round_index"]
    live = {}
    for row in read_delim(Path(root) / "pool_capacity_history.tsv", TAB):
        if row["state"] != "in_force" or int(row["effective_round"]) > ri:
            continue
        key = (row["precinct"], row["pool"])
        cur = live.get(key)
        if cur is None or int(row["effective_round"]) >= cur[0]:
            live[key] = (int(row["effective_round"]), int(row["capacity"]))
    return {k: v[1] for k, v in live.items()}


def ref_carryover(root):
    out = {}
    for row in read_delim(Path(root) / "carried_commitment_ledger.csv"):
        if row["state"] != "binding":
            continue
        out[row["commitment_id"]] = {"precinct": row["precinct"],
                                     "pool": row["pool"],
                                     "quantity": int(row["quantity"])}
    return out


def ref_groups(root, jobs, aliases):
    """Stage p08. Open memberships, with a job standing in two open groups
    kept by the group of the lower precedence number."""
    rows = [dict(r, member_job=aliases.get(r["member_job"], r["member_job"]))
            for r in read_delim(Path(root) / "exclusive_slot_groups.csv")]
    rows = [r for r in rows if r["state"] == "open" and r["member_job"] in jobs]
    order = {}
    for r in rows:
        order[r["group_id"]] = int(r["precedence"])
    owner = {}
    for r in sorted(rows, key=lambda r: (int(r["precedence"]), r["group_id"],
                                         r["member_job"])):
        cur = owner.get(r["member_job"])
        if cur is None:
            owner[r["member_job"]] = r["group_id"]
    groups = {}
    rejected = []
    for r in sorted(rows, key=lambda r: (r["group_id"], r["member_job"])):
        if owner[r["member_job"]] != r["group_id"]:
            rejected.append((r["group_id"], r["member_job"], "GRP-DOUBLEBOOKED"))
            continue
        g = groups.setdefault(r["group_id"], {"group_id": r["group_id"],
                                              "precinct": r["precinct"],
                                              "precedence": int(r["precedence"]),
                                              "members": []})
        g["members"].append(r["member_job"])
    for g in groups.values():
        g["members"].sort()
    return groups, rejected


def ref_amendments(root):
    """Stage p13. The lodged amendments in sequence, with the payload fields
    the supplement completes folded in under the provenance ledger."""
    journal = [r for r in read_jsonl(Path(root) / "amendment_journal.jsonl")
               if r.get("state") == "lodged"]
    supplement = {}
    for rec in read_jsonl(Path(root) / "amendment_supplement.ndjson"):
        if rec.get("state") == "in_force":
            supplement[(rec["amendment_id"], rec["field"])] = rec["value"]
    aliases = ref_aliases(root)
    provenance = {}
    for row in read_delim(Path(root) / "row_provenance_ledger.csv"):
        if row["state"] == "in_force":
            provenance[(row["amendment_id"], row["field"])] = row["source_file"]
    out = []
    for rec in sorted(journal, key=lambda r: int(r["sequence"])):
        payload = dict(rec.get("payload") or {})
        for (aid, field), value in sorted(supplement.items()):
            if aid != rec["amendment_id"]:
                continue
            if provenance.get((aid, field)) != "amendment_supplement.ndjson":
                continue
            payload[field] = value
        for field in JOB_FIELDS_OF_PAYLOADS:
            if isinstance(payload.get(field), str):
                payload[field] = aliases.get(payload[field], payload[field])
        out.append({"amendment_id": rec["amendment_id"],
                    "sequence": int(rec["sequence"]), "kind": rec["kind"],
                    "payload": payload, "note": rec.get("note", "")})
    return out


# --------------------------------------------------------------------------
# the derived cells
#
# Seven layers. Each cell carries a key over the inputs it reads and a value
# whose digest decides whether a cascade that reaches it carries on. The key
# holds every input the cell reads and nothing the cell does not read, which
# is what keeps a change to a title out of the optimiser and a change to a
# capacity out of the closures.
# --------------------------------------------------------------------------
GOVERNED_REGISTER_FIELDS = ["base_charge_mills", "berth_quantity",
                            "berth_unit", "class", "crane_lifts",
                            "crew_quantity", "crew_unit", "deferral_weight",
                            "earliest_round", "job_id", "latest_round",
                            "licence_code", "precinct", "standing"]

GOVERNED_RULE_FIELDS = ["amount_text", "anchor_job", "class", "first_job",
                        "kind", "pool", "precinct", "rebate_bp", "rule_id",
                        "second_job", "state", "threshold"]


def cell_id(layer, name):
    return layer + PIPE + name


def cell_sort_key(model, cid):
    layer, name = cid.split(PIPE, 1)
    depth = model["depth"].get(name, 0) if layer == "closure" else 0
    return (LAYER_RANK[layer], depth, name)


class Store:
    """The working store. It holds the value in force for every cell and, in
    addition, up to the retained number of superseded entries, so a
    configuration the round has already stood in is read back rather than
    computed again. Dropping a superseded entry moves no published quantity.
    """

    def __init__(self, retention):
        self.retention = int(retention)
        self.current = {}
        self.history = {}
        self.stamps = {}
        self.clock = 0
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _touch(self, key):
        self.clock += 1
        self.stamps[key] = self.clock

    def lookup(self, cid, key):
        cur = self.current.get(cid)
        if cur is not None and cur[0] == key:
            self.hits += 1
            self._touch((cid, key))
            return cur[1], cur[2]
        held = self.history.get((cid, key))
        if held is not None:
            self.hits += 1
            del self.history[(cid, key)]
            self._touch((cid, key))
            if cur is not None:
                self._retire(cid, cur)
            self.current[cid] = (key, held[0], held[1])
            return held[0], held[1]
        self.misses += 1
        return None

    def _retire(self, cid, entry):
        self.history[(cid, entry[0])] = (entry[1], entry[2])
        self._touch((cid, entry[0]))
        while len(self.history) > self.retention:
            oldest = min(self.history, key=lambda k: self.stamps.get(k, 0))
            del self.history[oldest]
            self.stamps.pop(oldest, None)
            self.evictions += 1

    def install(self, cid, key, value, digest):
        cur = self.current.get(cid)
        if cur is not None and cur[0] != key:
            self._retire(cid, cur)
        self.current[cid] = (key, value, digest)
        self._touch((cid, key))


def _deep(value):
    """A cell hands back its own copy, so a later stage that walks over the
    value it was given leaves the stored value where it stands."""
    return json.loads(json.dumps(value))


def _available(model, precinct, pool):
    cap = model["capacity"].get((precinct, pool), 0)
    used = sum(c["quantity"] for c in model["carryover"].values()
               if c["precinct"] == precinct and c["pool"] == pool)
    return cap - used


def _accept_edges(model, precinct):
    """The accepted prerequisite lists of one precinct, rebuilt from the
    journal rows the precinct holds."""
    jobs = model["jobs"]
    seen = set()
    fresh = {}
    for eid in sorted(model["journal"]):
        row = model["journal"][eid]
        req, dep = row["requiring_job"], row["required_job"]
        if req not in jobs or jobs[req]["precinct"] != precinct:
            continue
        if row["status"] != "active" or row["kind"] != "hard":
            continue
        if req == dep or dep not in jobs:
            continue
        if jobs[dep]["precinct"] != precinct:
            continue
        if (req, dep) in seen:
            continue
        seen.add((req, dep))
        fresh.setdefault(req, []).append(dep)
    for jid in list(model["accepted"]):
        if jid in jobs and jobs[jid]["precinct"] == precinct:
            del model["accepted"][jid]
    for jid, deps in fresh.items():
        model["accepted"][jid] = sorted(deps)
    _rank(model, precinct)


def _rank(model, precinct):
    """Longest chain below each job, so a cascade visits a prerequisite before
    the job that names it."""
    order = [j for j in sorted(model["jobs"])
             if model["jobs"][j]["precinct"] == precinct]
    depth = {}

    def walk(jid, active):
        if jid in depth:
            return depth[jid]
        if jid in active:
            return 0
        active = active | {jid}
        best = 0
        for dep in model["accepted"].get(jid, []):
            if dep in model["jobs"]:
                best = max(best, 1 + walk(dep, active))
        depth[jid] = best
        return best

    for jid in order:
        walk(jid, frozenset())
    model["depth"].update(depth)


def _reaches(model, start, target):
    """Whether target stands among the prerequisites of start."""
    stack = [start]
    seen = set()
    while stack:
        jid = stack.pop()
        if jid == target and jid != start:
            return True
        if jid in seen:
            continue
        seen.add(jid)
        for dep in model["accepted"].get(jid, []):
            if dep == target:
                return True
            stack.append(dep)
    return False


def _reverse_closure(model, jid):
    """Every job whose closure holds this one."""
    out = set()
    precinct = model["jobs"][jid]["precinct"]
    for other in model["jobs"]:
        if model["jobs"][other]["precinct"] != precinct:
            continue
        if other != jid and _reaches(model, other, jid):
            out.add(other)
    return out


# --------------------------------------------------------------------------
# cell keys and cell values
# --------------------------------------------------------------------------
def norm_key(model, jid):
    job = model["jobs"][jid]
    params = model["params"]
    lic = params["licences"].get(job["licence_code"], {})
    fields = list(GOVERNED_REGISTER_FIELDS)
    if "R_META_IN_KEY" in WRONG:
        fields = sorted(fields + PRESENTATION_JOB_FIELDS)
    return digest_text(compact_json([
        {k: (model["meta"].get(jid, {}).get(k) if k in PRESENTATION_JOB_FIELDS
             else job[k]) for k in fields},
        params["shift_minutes"].get(job["precinct"]),
        [lic.get("state"), lic.get("valid_from_round"), lic.get("valid_to_round")],
        params["round_index"]]))


def norm_value(model, cells, jid):
    job = model["jobs"][jid]
    params = model["params"]
    shift = int(params["shift_minutes"][job["precinct"]])
    crew = int(job["crew_quantity"])
    crew = crew * shift if job["crew_unit"] == "shift" else crew
    berth = int(job["berth_quantity"])
    berth = berth * 4 if job["berth_unit"] == "day" else berth
    lic = params["licences"].get(job["licence_code"])
    ri = params["round_index"]
    admissible = True
    reason = ""
    if (lic is None or lic["state"] != "valid"
            or not (int(lic["valid_from_round"]) <= ri <= int(lic["valid_to_round"]))):
        admissible = False
        reason = "JOB-LICENCE"
    elif not (int(job["earliest_round"]) <= ri <= int(job["latest_round"])):
        admissible = False
        reason = "JOB-OUTOFROUND"
    return {"job_id": jid, "precinct": job["precinct"], "class": job["class"],
            "standing": job["standing"],
            "base_charge_mills": int(job["base_charge_mills"]),
            "berth_quarter_days": berth, "crane_lifts": int(job["crane_lifts"]),
            "crew_minutes": crew, "deferral_weight": int(job["deferral_weight"]),
            "admissible": admissible, "admission_reason": reason}


def rule_key(model, rid):
    rec = model["rules"][rid]
    return digest_text(compact_json({k: rec.get(k) for k in GOVERNED_RULE_FIELDS}))


def rule_value(model, cells, rid):
    rec = model["rules"][rid]
    out = {"rule_id": rid, "precinct": rec["precinct"], "kind": rec["kind"]}
    if rec["kind"] == "pair_surcharge":
        out["first_job"] = rec["first_job"]
        out["second_job"] = rec["second_job"]
        out["amount_mills"] = amount_mills(rec["amount_text"])
    elif rec["kind"] == "threshold_surcharge":
        out["pool"] = rec["pool"]
        out["threshold"] = int(rec["threshold"])
        out["class"] = rec["class"]
        out["amount_mills"] = amount_mills(rec["amount_text"])
    else:
        out["anchor_job"] = rec["anchor_job"]
        out["rebate_bp"] = int(rec["rebate_bp"])
    return out


def closure_key(model, cells, jid):
    deps = model["accepted"].get(jid, [])
    return digest_text(compact_json([
        deps, [cells[cell_id("closure", d)]["digest"] for d in deps
               if cell_id("closure", d) in cells],
        cells[cell_id("norm", jid)]["digest"]]))


def closure_value(model, cells, jid):
    stack = list(model["accepted"].get(jid, []))
    reach = set()
    missing = False
    while stack:
        cur = stack.pop()
        if cur in reach or cur == jid:
            continue
        if cur not in model["jobs"]:
            missing = True
            continue
        reach.add(cur)
        stack.extend(model["accepted"].get(cur, []))
    own = cells[cell_id("norm", jid)]["value"]
    blocked = False
    reason = ""
    if not own["admissible"]:
        blocked = True
        reason = own["admission_reason"]
    elif missing or any(not cells[cell_id("norm", m)]["value"]["admissible"]
                        for m in reach):
        blocked = True
        reason = "JOB-CLOSUREBLOCKED"
    return {"job_id": jid, "closure": sorted(reach), "blocked": blocked,
            "reason": reason}


def demand_key(model, cells, jid):
    closure = cells[cell_id("closure", jid)]
    members = [jid] + list(closure["value"]["closure"])
    return digest_text(compact_json([
        closure["digest"],
        [cells[cell_id("norm", m)]["digest"] for m in sorted(members)]]))


def demand_value(model, cells, jid):
    own = cells[cell_id("norm", jid)]["value"]
    members = [jid] + list(cells[cell_id("closure", jid)]["value"]["closure"])
    closed = {}
    for pool in POOLS:
        closed[pool] = sum(cells[cell_id("norm", m)]["value"][pool]
                           for m in sorted(set(members)))
    return {"job_id": jid,
            "own": {pool: own[pool] for pool in POOLS},
            "closed": closed}


def charge_key(model, cells, jid):
    params = model["params"]
    klass = cells[cell_id("norm", jid)]["value"]["class"]
    return digest_text(compact_json([
        cells[cell_id("norm", jid)]["digest"],
        params["class_bp"].get(klass), params["deferral_rate"].get(klass)]))


def charge_value(model, cells, jid):
    params = model["params"]
    norm = cells[cell_id("norm", jid)]["value"]
    bp = int(params["class_bp"][norm["class"]])
    scaled = half_up(Fraction(int(norm["base_charge_mills"]) * bp, 10000))
    penalty = int(params["deferral_rate"][norm["class"]]) * int(norm["deferral_weight"])
    return {"job_id": jid, "scaled_charge_mills": scaled,
            "deferral_penalty_mills": penalty,
            "multiplier_bp": bp,
            "implausible": scaled > int(params["ceiling"])}


def group_key(model, cells, gid):
    grp = model["groups"][gid]
    members = [m for m in grp["members"] if m in model["jobs"]]
    return digest_text(compact_json([
        sorted(members), grp["precedence"], grp["precinct"],
        [cells[cell_id("norm", m)]["digest"] for m in sorted(members)]]))


def group_value(model, cells, gid):
    grp = model["groups"][gid]
    members = sorted(m for m in grp["members"] if m in model["jobs"])
    return {"group_id": gid, "precinct": grp["precinct"],
            "precedence": grp["precedence"], "members": members,
            "binding": len(members) >= 2}


def solve_key(model, cells, precinct):
    params = model["params"]
    jobs = [j for j in sorted(model["jobs"])
            if model["jobs"][j]["precinct"] == precinct]
    groups = [g for g in sorted(model["groups"])
              if model["groups"][g]["precinct"] == precinct]
    rules = [r for r in sorted(model["rules"])
             if model["rules"][r]["precinct"] == precinct]
    return digest_text(compact_json([
        [[pool, _available(model, precinct, pool)] for pool in POOLS],
        [[cells[cell_id("closure", j)]["digest"],
          cells[cell_id("demand", j)]["digest"],
          cells[cell_id("charge", j)]["digest"]] for j in jobs],
        [cells[cell_id("group", g)]["digest"] for g in groups],
        ([] if "R_RULE_KEY_OMITS" in WRONG
         else [cells[cell_id("rule", r)]["digest"] for r in rules]),
        [[pool, params["pool_weights"][pool][0], params["pool_weights"][pool][1]]
         for pool in POOLS]]))


def evaluate(model, cells, precinct):
    """Stages p09 to p11. Every subset of the selectable jobs of one precinct
    is examined in ascending mask order. Hands back the running counts and
    every feasible set with the lexicographic key the objective gives it."""
    params = model["params"]
    jobs = [j for j in sorted(model["jobs"])
            if model["jobs"][j]["precinct"] == precinct]
    selectable = [j for j in jobs
                  if not cells[cell_id("closure", j)]["value"]["blocked"]]
    closures = {j: cells[cell_id("closure", j)]["value"]["closure"]
                for j in selectable}
    own = {j: cells[cell_id("demand", j)]["value"]["own"] for j in jobs}
    charges = {j: cells[cell_id("charge", j)]["value"] for j in jobs}
    norms = {j: cells[cell_id("norm", j)]["value"] for j in jobs}
    groups = [cells[cell_id("group", g)]["value"] for g in sorted(model["groups"])
              if model["groups"][g]["precinct"] == precinct]
    binding = [g["members"] for g in groups if g["binding"]]
    rules = [cells[cell_id("rule", r)]["value"] for r in sorted(model["rules"])
             if model["rules"][r]["precinct"] == precinct]
    available = {pool: _available(model, precinct, pool) for pool in POOLS}
    weights = {pool: Fraction(params["pool_weights"][pool][0],
                              params["pool_weights"][pool][1]) for pool in POOLS}
    charter = [j for j in selectable if norms[j]["standing"] == "charter"]

    examined = 0
    group_rejected = 0
    capacity_rejected = 0
    feasible = 0
    best = None
    best_body = None
    found = []
    count = len(selectable)
    for mask in range(1 << count):
        examined += 1
        chosen = [selectable[i] for i in range(count) if mask >> i & 1]
        closed = set(chosen)
        for j in chosen:
            closed.update(closures[j])
        closed = sorted(closed)
        if any(len(set(members) & set(closed)) > 1 for members in binding):
            group_rejected += 1
            continue
        usage = {pool: sum(own[j][pool] for j in closed) for pool in POOLS}
        tight = ("R_STRICT_CAPACITY" in WRONG)
        if any((usage[pool] >= available[pool]) if tight
               else (usage[pool] > available[pool]) for pool in POOLS):
            capacity_rejected += 1
            continue
        feasible += 1
        base = sum(charges[j]["scaled_charge_mills"] for j in closed)
        surcharge = 0
        for rule in rules:
            if rule["kind"] == "pair_surcharge":
                if rule["first_job"] in closed and rule["second_job"] in closed:
                    surcharge += rule["amount_mills"]
            elif rule["kind"] == "threshold_surcharge":
                if usage[rule["pool"]] > rule["threshold"]:
                    surcharge += rule["amount_mills"] * sum(
                        1 for j in closed if norms[j]["class"] == rule["class"])
        rebate = 0
        for rule in rules:
            if rule["kind"] != "closure_rebate":
                continue
            anchor = rule["anchor_job"]
            if anchor in closed and len(closures.get(anchor, [])) >= 2:
                over = base if "R_REBATE_BEFORE" in WRONG else base + surcharge
                rebate += half_up(Fraction(over * rule["rebate_bp"], 10000))
        if "R_PENALTY_ALL" in WRONG:
            penalty = sum(charges[j]["deferral_penalty_mills"]
                          for j in jobs if j not in closed)
        else:
            penalty = sum(charges[j]["deferral_penalty_mills"]
                          for j in charter if j not in closed)
        total = base + surcharge - rebate + penalty
        weighted = sum(weights[pool] * usage[pool] for pool in POOLS)
        optional = sum(1 for j in closed if norms[j]["standing"] == "optional")
        key = ((total, Fraction(0), 0, ()) if "R_COST_ONLY" in WRONG
               else (total, weighted, optional, tuple(closed)))
        body = {"selected": list(chosen), "closed_set": closed,
                "usage": usage, "base_mills": base,
                "surcharge_mills": surcharge, "rebate_mills": rebate,
                "penalty_mills": penalty, "total_mills": total,
                "optional_count": optional,
                "weighted_resource": ratio_text(weighted)}
        found.append((key, body))
        if best is None or key < best:
            best = key
            best_body = body
    stats = {"precinct": precinct, "selectable": selectable,
             "subsets_examined": examined,
             "subsets_group_rejected": group_rejected,
             "subsets_capacity_rejected": capacity_rejected,
             "subsets_feasible": feasible, "available": available}
    return stats, found, best_body


def solve_value(model, cells, precinct):
    """The exact lexicographic optimum of one precinct."""
    stats, _found, best_body = evaluate(model, cells, precinct)
    if best_body is None:
        raise SystemExit("precinct " + precinct + " admits no feasible set")
    return {**stats, **best_body}


VALUE_OF = {"norm": norm_value, "rule": rule_value, "closure": closure_value,
            "demand": demand_value, "charge": charge_value,
            "group": group_value, "solve": solve_value}
KEY_OF = {"norm": lambda m, c, n: norm_key(m, n),
          "rule": lambda m, c, n: rule_key(m, n),
          "closure": closure_key, "demand": demand_key, "charge": charge_key,
          "group": group_key, "solve": solve_key}


# --------------------------------------------------------------------------
# building the model and driving the cascade
# --------------------------------------------------------------------------
def _new_counters():
    return {"visited": {name: 0 for name in LAYERS},
            "recomputed": {name: 0 for name in LAYERS},
            "revalidated": {name: 0 for name in LAYERS},
            "subsets_examined": 0}


def dependents(model, cid):
    layer, name = cid.split(PIPE, 1)
    out = []
    if layer == "norm":
        precinct = model["jobs"][name]["precinct"]
        out.append(cell_id("closure", name))
        out.append(cell_id("demand", name))
        out.append(cell_id("charge", name))
        if "R_SHALLOW_CASCADE" not in WRONG:
            for other in sorted(_reverse_closure(model, name)):
                out.append(cell_id("demand", other))
        for gid in sorted(model["groups"]):
            if name in model["groups"][gid]["members"]:
                out.append(cell_id("group", gid))
        out.append(cell_id("solve", precinct))
    elif layer == "rule":
        out.append(cell_id("solve", model["rules"][name]["precinct"]))
    elif layer == "closure":
        precinct = model["jobs"][name]["precinct"]
        out.append(cell_id("demand", name))
        for other in sorted(model["accepted"]):
            if name in model["accepted"][other] and other in model["jobs"]:
                out.append(cell_id("closure", other))
        out.append(cell_id("solve", precinct))
    elif layer in ("demand", "charge"):
        out.append(cell_id("solve", model["jobs"][name]["precinct"]))
    elif layer == "group":
        out.append(cell_id("solve", model["groups"][name]["precinct"]))
    return out


def visit(ctx, cid, counters, touched):
    model, cells, store = ctx["model"], ctx["cells"], ctx["store"]
    layer, name = cid.split(PIPE, 1)
    key = KEY_OF[layer](model, cells, name)
    counters["visited"][layer] += 1
    found = store.lookup(cid, key)
    if found is None:
        value = VALUE_OF[layer](model, cells, name)
        digest = digest_text(compact_json(value))
        store.install(cid, key, value, digest)
        counters["recomputed"][layer] += 1
        if layer == "solve":
            counters["subsets_examined"] += value["subsets_examined"]
        touched.append((cid, "recomputed"))
    else:
        value, digest = found
        touched.append((cid, "read_from_store"))
    previous = cells.get(cid)
    cells[cid] = {"key": key, "value": _deep(value), "digest": digest}
    if previous is not None and previous["digest"] == digest:
        counters["revalidated"][layer] += 1
        touched[-1] = (cid, "revalidated")
        return "R_NO_CUTOFF" in WRONG
    return True


def cascade(ctx, seeds, counters):
    model = ctx["model"]
    queue = set(seeds)
    done = set()
    touched = []
    changed = []
    while queue:
        cid = min(queue, key=lambda c: cell_sort_key(model, c))
        queue.discard(cid)
        if cid in done:
            continue
        done.add(cid)
        if visit(ctx, cid, counters, touched):
            changed.append(cid)
            for nxt in dependents(model, cid):
                if nxt not in done:
                    queue.add(nxt)
    return touched, changed


def ref_model(root):
    """Stages p01 to p03 and p08. The model the round opens with."""
    root = Path(root)
    params = ref_params(root)
    aliases = ref_aliases(root)
    jobs, aside = ref_register(root, params, aliases)
    accepted, edge_rejected = ref_edge_journal(root, jobs, aliases)

    model = {"params": params, "jobs": jobs, "accepted": accepted,
             "journal": {}, "depth": {}, "meta": {}, "groups": {},
             "capacity": ref_capacity(root, params),
             "carryover": ref_carryover(root),
             "rules": ref_rules(root, params)}
    for row in read_delim(root / "precedence_edge_journal.psv", PIPE):
        model["journal"][row["edge_id"]] = {
            "requiring_job": aliases.get(row["requiring_job"], row["requiring_job"]),
            "required_job": aliases.get(row["required_job"], row["required_job"]),
            "kind": row["kind"], "status": row["status"]}

    # a job standing in a precedence cycle takes no part in the round
    cycles = set()
    for jid in sorted(jobs):
        if _reaches(model, jid, jid) or jid in model["accepted"].get(jid, []):
            cycles.add(jid)
    for jid in sorted(cycles):
        aside.append((jid, "JOB-CYCLE", jobs[jid]["precinct"]))
        del jobs[jid]
    if cycles:
        accepted, edge_rejected = ref_edge_journal(root, jobs, aliases)
        model["accepted"] = accepted

    groups, group_rejected = ref_groups(root, jobs, aliases)
    model["groups"] = groups
    for jid in sorted(jobs):
        model["meta"][jid] = {k: jobs[jid][k] for k in PRESENTATION_JOB_FIELDS}
    for precinct in sorted(set(j["precinct"] for j in jobs.values())):
        _rank(model, precinct)
    model["aside"] = sorted(aside)
    model["edge_rejected"] = sorted(edge_rejected)
    model["group_rejected"] = sorted(group_rejected)
    return model


def ref_open(root):
    """Stages p04 to p12. Every cell built once, in canonical order."""
    model = ref_model(root)
    ctx = {"model": model, "cells": {},
           "store": Store(model["params"]["retention"]), "root": Path(root)}
    counters = _new_counters()
    cids = []
    for jid in sorted(model["jobs"]):
        cids.append(cell_id("norm", jid))
    for rid in sorted(model["rules"]):
        cids.append(cell_id("rule", rid))
    for jid in sorted(model["jobs"]):
        cids.append(cell_id("closure", jid))
        cids.append(cell_id("demand", jid))
        cids.append(cell_id("charge", jid))
    for gid in sorted(model["groups"]):
        cids.append(cell_id("group", gid))
    for precinct in sorted(set(j["precinct"] for j in model["jobs"].values())):
        cids.append(cell_id("solve", precinct))
    touched = []
    for cid in sorted(cids, key=lambda c: cell_sort_key(model, c)):
        visit(ctx, cid, counters, touched)
    ctx["build_counters"] = counters
    ctx["inverse"] = {}
    ctx["precincts"] = sorted(set(j["precinct"] for j in model["jobs"].values()))
    return ctx


def _seed_set(ctx, amendment, payload):
    """The seed set the directive gives the kind of this amendment."""
    model = ctx["model"]
    kind = amendment["kind"]
    if kind == "job_note_revision":
        if "R_META_IN_KEY" in WRONG:
            return [cell_id("norm", payload["job_id"])], "governed"
        return [], "inert"
    if kind == "job_field_revision":
        return [cell_id("norm", payload["job_id"])], "governed"
    if kind == "edge_withdrawn" and "R_REMOVAL_INERT" in WRONG:
        return [], "governed"
    if kind in ("edge_lodged", "edge_withdrawn"):
        return [cell_id("closure", payload["requiring_job"])], "governed"
    if kind == "group_member_revision":
        return [cell_id("group", payload["group_id"])], "governed"
    if kind == "capacity_revision":
        if "R_CAPACITY_SEEDS_CLOSURE" in WRONG:
            return ([cell_id("closure", j) for j in sorted(model["jobs"])
                     if model["jobs"][j]["precinct"] == payload["precinct"]]
                    + [cell_id("solve", payload["precinct"])], "governed")
        return [cell_id("solve", payload["precinct"])], "governed"
    if kind == "carryover_revision":
        return [cell_id("solve", payload["precinct"])], "governed"
    if kind in ("charge_rule_revision", "restatement"):
        return [cell_id("rule", payload["rule_id"])], "governed"
    if kind == "class_rate_revision":
        return [cell_id("charge", j) for j in sorted(model["jobs"])
                if model["jobs"][j]["class"] == payload["class"]], "governed"
    raise SystemExit("the directive classifies no kind " + kind)


def _apply_payload(ctx, kind, payload):
    """Move the model and hand back the payload that puts it back."""
    model = ctx["model"]
    if kind == "job_note_revision":
        jid, field = payload["job_id"], payload["field"]
        back = {"job_id": jid, "field": field, "value": model["meta"][jid][field]}
        model["meta"][jid][field] = payload["value"]
        return back
    if kind == "job_field_revision":
        jid, field = payload["job_id"], payload["field"]
        back = {"job_id": jid, "field": field,
                "value": model["jobs"][jid][field]}
        model["jobs"][jid][field] = payload["value"]
        return back
    if kind == "edge_lodged":
        eid = payload["edge_id"]
        back = {"edge_id": eid, "requiring_job": payload["requiring_job"],
                "required_job": payload["required_job"],
                "kind": payload.get("kind", "hard")}
        if payload.get("undo"):
            del model["journal"][eid]
        else:
            model["journal"][eid] = {"requiring_job": payload["requiring_job"],
                                     "required_job": payload["required_job"],
                                     "kind": payload.get("kind", "hard"),
                                     "status": "active"}
            back["undo"] = True
        _accept_edges(model, model["jobs"][payload["requiring_job"]]["precinct"])
        return back
    if kind == "edge_withdrawn":
        eid = payload["edge_id"]
        row = model["journal"][eid]
        back = {"edge_id": eid, "requiring_job": row["requiring_job"],
                "required_job": row["required_job"], "kind": row["kind"]}
        if payload.get("undo"):
            row["status"] = payload["undo"]
        else:
            back["undo"] = row["status"]
            row["status"] = "withdrawn"
        _accept_edges(model, model["jobs"][row["requiring_job"]]["precinct"])
        return back
    if kind == "group_member_revision":
        gid, member = payload["group_id"], payload["member_job"]
        grp = model["groups"][gid]
        if payload["action"] == "remove":
            grp["members"] = [m for m in grp["members"] if m != member]
            return {"group_id": gid, "member_job": member, "action": "add"}
        grp["members"] = sorted(set(grp["members"]) | {member})
        return {"group_id": gid, "member_job": member, "action": "remove"}
    if kind == "capacity_revision":
        key = (payload["precinct"], payload["pool"])
        back = {"precinct": payload["precinct"], "pool": payload["pool"],
                "capacity": model["capacity"][key]}
        model["capacity"][key] = int(payload["capacity"])
        return back
    if kind == "carryover_revision":
        cid = payload["commitment_id"]
        back = {"commitment_id": cid,
                "quantity": model["carryover"][cid]["quantity"],
                "precinct": model["carryover"][cid]["precinct"]}
        model["carryover"][cid]["quantity"] = int(payload["quantity"])
        return back
    if kind in ("charge_rule_revision", "restatement"):
        rid = payload["rule_id"]
        back = {"rule_id": rid, "amount_text": model["rules"][rid]["amount_text"]}
        model["rules"][rid]["amount_text"] = payload["amount_text"]
        return back
    if kind == "class_rate_revision":
        klass = payload["class"]
        back = {"class": klass, "multiplier_bp": model["params"]["class_bp"][klass]}
        model["params"]["class_bp"][klass] = int(payload["multiplier_bp"])
        return back
    raise SystemExit("no payload rule for " + kind)


def _resolve(ctx, amendment):
    """Fill in the fields the payload needs before it can be applied."""
    model = ctx["model"]
    kind = amendment["kind"]
    payload = dict(amendment["payload"])
    if kind == "reversal":
        named = ctx["inverse"].get(payload["amendment_id"])
        if named is None:
            return "reversal", payload, "rejected", "AMD-NOTARGET"
        return named[0], dict(named[1]), "governed", ""
    if kind == "edge_lodged":
        req, dep = payload["requiring_job"], payload["required_job"]
        payload["edge_id"] = amendment["amendment_id"] + "-E"
        if req == dep:
            return kind, payload, "rejected", "EDG-SELF"
        if req not in model["jobs"] or dep not in model["jobs"]:
            return kind, payload, "rejected", "EDG-UNKNOWNJOB"
        if model["jobs"][req]["precinct"] != model["jobs"][dep]["precinct"]:
            return kind, payload, "rejected", "EDG-CROSSPRECINCT"
        if _reaches(model, dep, req) or dep == req:
            return kind, payload, "rejected", "EDG-CYCLE"
        if dep in model["accepted"].get(req, []):
            return kind, payload, "rejected", "EDG-DUPLICATE"
    if kind == "edge_withdrawn":
        eid = payload["edge_id"]
        row = model["journal"].get(eid)
        if row is None or row["requiring_job"] not in model["jobs"]:
            return kind, payload, "rejected", "EDG-UNKNOWNJOB"
        payload["requiring_job"] = row["requiring_job"]
        payload["required_job"] = row["required_job"]
    if kind == "carryover_revision":
        cid = payload["commitment_id"]
        if cid not in model["carryover"]:
            return kind, payload, "rejected", "CMT-UNKNOWN"
        payload["precinct"] = model["carryover"][cid]["precinct"]
    return kind, payload, ("inert" if kind == "job_note_revision"
                           else "governed"), ""


def ref_amend(ctx, amendment):
    """Stage p13. One amendment: classify it, move the model, seed the cells
    the directive names, and let the cascade stop where a value stands."""
    kind, payload, verdict, reason = _resolve(ctx, amendment)
    counters = _new_counters()
    record = {"amendment_id": amendment["amendment_id"],
              "sequence": amendment["sequence"],
              "lodged_kind": amendment["kind"], "applied_kind": kind,
              "classification": verdict, "reason": reason}
    if verdict == "rejected":
        record["seed_cells"] = []
        record["invalidated"] = []
        record["revalidated"] = []
        record["counters"] = counters
        record["touched"] = []
        return record
    back = _apply_payload(ctx, kind, payload)
    ctx["inverse"][amendment["amendment_id"]] = (kind, back)
    seeds, _label = _seed_set(ctx, {"kind": kind}, payload)
    if not seeds and kind in ("job_note_revision", "class_rate_revision"):
        record["classification"] = "inert"
    touched, changed = cascade(ctx, seeds, counters)
    record["seed_cells"] = sorted(seeds)
    record["invalidated"] = sorted(changed)
    record["revalidated"] = sorted(cid for cid, state in touched
                                   if state == "revalidated")
    record["counters"] = counters
    record["touched"] = touched
    record["target"] = compact_json(payload)
    return record


# --------------------------------------------------------------------------
# publication
#
# Twenty five documents, each in the shape the schema reference fixes. The
# manifest and the summary are taken last, over the bytes already written.
# --------------------------------------------------------------------------
def _selection_body(ctx, order):
    cells = ctx["cells"]
    precincts = []
    total = 0
    weighted = Fraction(0)
    selected = 0
    for precinct in order:
        body = cells[cell_id("solve", precinct)]["value"]
        precincts.append({
            "precinct": precinct,
            "selected": list(body["selected"]),
            "closed_set": list(body["closed_set"]),
            "total_mills": body["total_mills"],
            "base_mills": body["base_mills"],
            "surcharge_mills": body["surcharge_mills"],
            "rebate_mills": body["rebate_mills"],
            "penalty_mills": body["penalty_mills"],
            "optional_count": body["optional_count"],
            "weighted_resource": body["weighted_resource"],
            "usage": body["usage"], "available": body["available"]})
        total += body["total_mills"]
        weights = ctx["model"]["params"]["pool_weights"]
        weighted += sum(Fraction(weights[pool][0], weights[pool][1])
                        * body["usage"][pool] for pool in POOLS)
        selected += len(body["closed_set"])
    return {"precincts": precincts, "total_mills": total,
            "weighted_resource": ratio_text(weighted),
            "accepted_job_count": selected}


def _layer_totals(ctx):
    out = {name: 0 for name in LAYERS}
    for cid in ctx["cells"]:
        out[cid.split(PIPE, 1)[0]] += 1
    return out


def ref_publish(root, out, rules=()):
    """Run the whole round out of one paper directory into one destination."""
    global WRONG
    WRONG = set(rules)
    root = Path(root)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ctx = ref_open(root)
    model = ctx["model"]
    cells = ctx["cells"]
    params = model["params"]
    order = ctx["precincts"]
    jobs = sorted(model["jobs"])

    aliases = ref_aliases(root)
    write_json(out / "01_identifier_canon.json", {
        "round_key": params["round_key"],
        "round_index": params["round_index"],
        "yard": params["header"]["yard"],
        "workbook_sheet_key": params["header"]["workbook_round_cell"],
        "jobs_in_force": len(jobs),
        "aliases_active": sum(1 for row in read_delim(
            Path(root) / "identifier_crosswalk.tsv", TAB)
            if row["status"] == "active"),
        "set_aside_count": len(model["aside"]),
        "precincts": [{"code": p,
                       "jobs": sum(1 for j in jobs
                                   if model["jobs"][j]["precinct"] == p)}
                      for p in order]})

    edge_rows = []
    accepted_pairs = set()
    for req in sorted(model["accepted"]):
        for dep in model["accepted"][req]:
            accepted_pairs.add((req, dep))
    for eid, _req, _dep, reason in model["edge_rejected"]:
        edge_rows.append([eid, _req, _dep,
                          model["jobs"].get(_req, {}).get("precinct", ""),
                          "rejected", reason])
    for req in sorted(model["accepted"]):
        for dep in model["accepted"][req]:
            eid = ""
            for cand in sorted(model["journal"]):
                row = model["journal"][cand]
                if (row["requiring_job"] == req and row["required_job"] == dep
                        and row["status"] == "active" and row["kind"] == "hard"):
                    eid = cand
                    break
            edge_rows.append([eid, req, dep, model["jobs"][req]["precinct"],
                              "accepted", ""])
    edge_rows.sort(key=lambda r: (r[0], r[1], r[2]))
    write_delim(out / "02_precedence_edges.tsv",
                ["edge_id", "requiring_job", "required_job", "precinct",
                 "state", "reason"], edge_rows, TAB)

    reverse = {}
    for req, dep in sorted(accepted_pairs):
        reverse.setdefault(dep, []).append(req)
    write_json(out / "03_reverse_index.json",
               {k: sorted(v) for k, v in sorted(reverse.items())})

    norm_rows = []
    feas_rows = []
    closure_rows = []
    demand_rows = []
    charge_rows = []
    for jid in jobs:
        n = cells[cell_id("norm", jid)]["value"]
        c = cells[cell_id("closure", jid)]["value"]
        d = cells[cell_id("demand", jid)]["value"]
        g = cells[cell_id("charge", jid)]["value"]
        norm_rows.append([jid, n["precinct"], n["class"], n["standing"],
                          n["base_charge_mills"], n["crew_minutes"],
                          n["berth_quarter_days"], n["crane_lifts"],
                          n["deferral_weight"],
                          "yes" if n["admissible"] else "no",
                          n["admission_reason"]])
        feas_rows.append([jid, n["precinct"],
                          "yes" if n["admissible"] else "no",
                          "yes" if c["blocked"] else "no", c["reason"],
                          "no" if c["blocked"] else "yes"])
        closure_rows.append({"job_id": jid, "precinct": n["precinct"],
                             "closure": c["closure"],
                             "closure_size": len(c["closure"]),
                             "blocked": c["blocked"], "reason": c["reason"]})
        demand_rows.append([jid, n["precinct"]]
                           + [d["own"][pool] for pool in POOLS]
                           + [d["closed"][pool] for pool in POOLS])
        charge_rows.append([jid, n["precinct"], n["class"], g["multiplier_bp"],
                            n["base_charge_mills"], g["scaled_charge_mills"],
                            n["deferral_weight"], g["deferral_penalty_mills"],
                            "yes" if g["implausible"] else "no"])
    write_delim(out / "04_normalised_jobs.csv",
                ["job_id", "precinct", "class", "standing", "base_charge_mills",
                 "crew_minutes", "berth_quarter_days", "crane_lifts",
                 "deferral_weight", "admissible", "admission_reason"],
                norm_rows, ",")
    write_delim(out / "06_feasibility_map.csv",
                ["job_id", "precinct", "admissible", "blocked", "reason",
                 "selectable"], feas_rows, ",")
    write_jsonl(out / "07_closure_map.jsonl", closure_rows)
    write_delim(out / "08_demand_vectors.csv",
                ["job_id", "precinct"]
                + ["own_" + pool for pool in POOLS]
                + ["closed_" + pool for pool in POOLS], demand_rows, ",")
    write_delim(out / "10_charge_contributions.csv",
                ["job_id", "precinct", "class", "multiplier_bp",
                 "base_charge_mills", "scaled_charge_mills", "deferral_weight",
                 "deferral_penalty_mills", "implausible"], charge_rows, ",")

    rule_rows = []
    for rid in sorted(model["rules"]):
        v = cells[cell_id("rule", rid)]["value"]
        rule_rows.append([rid, v["precinct"], v["kind"],
                          v.get("first_job", v.get("anchor_job", "")),
                          v.get("second_job", ""), v.get("pool", ""),
                          v.get("threshold", ""), v.get("class", ""),
                          v.get("amount_mills", ""), v.get("rebate_bp", "")])
    write_delim(out / "05_normalised_rules.csv",
                ["rule_id", "precinct", "kind", "subject_a", "subject_b",
                 "pool", "threshold", "class", "amount_mills", "rebate_bp"],
                rule_rows, ",")

    write_json(out / "09_conflict_groups.json", {
        "groups": [dict(cells[cell_id("group", gid)]["value"])
                   for gid in sorted(model["groups"])],
        "rejected_memberships": [{"group_id": g, "member_job": m,
                                  "reason": r}
                                 for g, m, r in model["group_rejected"]]})

    baseline = _selection_body(ctx, order)
    write_json(out / "11_baseline_selection.json", baseline)
    write_jsonl(out / "12_baseline_trace.jsonl", [
        {"precinct": p,
         "selectable_count": len(cells[cell_id("solve", p)]["value"]["selectable"]),
         "subsets_examined": cells[cell_id("solve", p)]["value"]["subsets_examined"],
         "subsets_group_rejected":
             cells[cell_id("solve", p)]["value"]["subsets_group_rejected"],
         "subsets_capacity_rejected":
             cells[cell_id("solve", p)]["value"]["subsets_capacity_rejected"],
         "subsets_feasible":
             cells[cell_id("solve", p)]["value"]["subsets_feasible"],
         "base_mills": cells[cell_id("solve", p)]["value"]["base_mills"],
         "surcharge_mills": cells[cell_id("solve", p)]["value"]["surcharge_mills"],
         "rebate_mills": cells[cell_id("solve", p)]["value"]["rebate_mills"],
         "penalty_mills": cells[cell_id("solve", p)]["value"]["penalty_mills"],
         "total_mills": cells[cell_id("solve", p)]["value"]["total_mills"]}
        for p in order])

    store = ctx["store"]
    stages = [{"stage": "build", "sequence": 0, "amendment_id": "",
               "counters": ctx["build_counters"],
               "cache": {"hits": store.hits, "misses": store.misses,
                         "evictions": store.evictions}}]
    records = []
    optima_rows = []
    previous = {p: cells[cell_id("solve", p)]["digest"] for p in order}
    marks = (store.hits, store.misses, store.evictions)
    for amendment in ref_amendments(root):
        record = ref_amend(ctx, amendment)
        now = (store.hits, store.misses, store.evictions)
        record["cache"] = {"hits": now[0] - marks[0], "misses": now[1] - marks[1],
                           "evictions": now[2] - marks[2]}
        marks = now
        records.append(record)
        stages.append({"stage": "amendment", "sequence": record["sequence"],
                       "amendment_id": record["amendment_id"],
                       "counters": record["counters"], "cache": record["cache"]})
        for p in order:
            body = cells[cell_id("solve", p)]["value"]
            digest = cells[cell_id("solve", p)]["digest"]
            optima_rows.append([record["sequence"], record["amendment_id"], p,
                                body["total_mills"], body["weighted_resource"],
                                len(body["closed_set"]),
                                "yes" if digest != previous[p] else "no"])
            previous[p] = digest

    write_delim(out / "13_amendment_classification.csv",
                ["sequence", "amendment_id", "lodged_kind", "applied_kind",
                 "classification", "reason", "seed_count", "seed_cells"],
                [[r["sequence"], r["amendment_id"], r["lodged_kind"],
                  r["applied_kind"], r["classification"], r["reason"],
                  len(r["seed_cells"]), ";".join(r["seed_cells"])]
                 for r in records], ",")
    write_jsonl(out / "14_invalidation_sets.jsonl", [
        {"sequence": r["sequence"], "amendment_id": r["amendment_id"],
         "seed_cells": r["seed_cells"], "invalidated": r["invalidated"],
         "revalidated": r["revalidated"],
         "invalidated_count": len(r["invalidated"]),
         "revalidated_count": len(r["revalidated"])} for r in records])

    totals = _layer_totals(ctx)
    reuse_rows = []
    for stage in stages:
        for layer in LAYERS:
            visited = stage["counters"]["visited"][layer]
            reuse_rows.append([stage["sequence"], stage["amendment_id"], layer,
                               visited, stage["counters"]["recomputed"][layer],
                               stage["counters"]["revalidated"][layer],
                               totals[layer] - visited])
    write_delim(out / "15_reuse_ledger.csv",
                ["sequence", "amendment_id", "layer", "visited", "recomputed",
                 "revalidated", "reused"], reuse_rows, ",")

    counter_rows = []
    for stage in stages:
        visited = sum(stage["counters"]["visited"].values())
        counter_rows.append([
            stage["stage"], stage["sequence"], stage["amendment_id"], visited,
            sum(stage["counters"]["recomputed"].values()),
            sum(stage["counters"]["revalidated"].values()),
            sum(totals.values()) - visited,
            stage["counters"]["subsets_examined"],
            stage["cache"]["hits"], stage["cache"]["misses"],
            stage["cache"]["evictions"]])
    write_delim(out / "16_work_counters.csv",
                ["stage", "sequence", "amendment_id", "cells_visited",
                 "cells_recomputed", "cells_revalidated", "cells_reused",
                 "subsets_examined", "cache_hits", "cache_misses",
                 "cache_evictions"], counter_rows, ",")

    write_json(out / "17_cache_summary.json", {
        "retention": store.retention,
        "entries_in_force": len(store.current),
        "entries_retained": len(store.history),
        "hits": store.hits, "misses": store.misses,
        "evictions": store.evictions,
        "hit_ratio": safe_ratio(store.hits, store.hits + store.misses)})

    final = _selection_body(ctx, order)
    write_json(out / "18_final_selection.json", final)

    rejected_rows = []
    for jid, reason, precinct in model["aside"]:
        rejected_rows.append(["job", jid, reason, precinct])
    for eid, req, dep, reason in model["edge_rejected"]:
        rejected_rows.append(["edge", eid, reason, req + ">" + dep])
    for gid, member, reason in model["group_rejected"]:
        rejected_rows.append(["group_membership", gid, reason, member])
    for r in records:
        if r["classification"] == "rejected":
            rejected_rows.append(["amendment", r["amendment_id"], r["reason"],
                                  r["lodged_kind"]])
    rejected_rows.sort(key=lambda r: (r[0], r[1], r[2], r[3]))
    write_delim(out / "19_rejected_register.csv",
                ["scope", "identifier", "reason", "detail"], rejected_rows, ",")

    usage_rows = []
    for body in final["precincts"]:
        for pool in POOLS:
            num, den = params["pool_weights"][pool]
            carried = sum(c["quantity"] for c in model["carryover"].values()
                          if c["precinct"] == body["precinct"] and c["pool"] == pool)
            usage_rows.append([body["precinct"], pool,
                               model["capacity"][(body["precinct"], pool)],
                               carried, body["available"][pool],
                               body["usage"][pool],
                               body["available"][pool] - body["usage"][pool],
                               num, den,
                               ratio_text(Fraction(num, den) * body["usage"][pool])])
    write_delim(out / "20_resource_usage.tsv",
                ["precinct", "pool", "capacity", "carried", "available",
                 "usage", "headroom", "weight_numerator", "weight_denominator",
                 "weighted_usage"], usage_rows, TAB)

    write_delim(out / "21_amendment_optima.csv",
                ["sequence", "amendment_id", "precinct", "total_mills",
                 "weighted_resource", "accepted_job_count", "optimum_moved"],
                optima_rows, ",")

    catalogue = []
    for row in read_delim(root / "amendment_reason_catalogue.psv", PIPE):
        code = row["reason_code"].strip()
        if code in SET_ASIDE_ORDER or code in EDGE_REJECT_ORDER or code in (
                "EDG-CYCLE", "GRP-DOUBLEBOOKED", "GRP-SINGLE",
                "AMD-NOTARGET", "CMT-UNKNOWN"):
            catalogue.append((row["stage"].strip(), code, row["label"].strip()))
    lines = ["# Defect register", "", "| stage | reason code | label |",
             "| --- | --- | --- |"]
    for stage, code, label in sorted(set(catalogue)):
        lines.append("| " + stage + " | " + code + " | " + label + " |")
    lines.append("")
    lines.append("Modules in force: " + ", ".join(PACKAGE_MODULES))
    write_lines(out / "22_defect_register.md", lines)

    moved = sum(1 for row in optima_rows if row[6] == "yes")
    inert = sum(1 for r in records if r["classification"] == "inert")
    write_lines(out / "23_verification_notes.md", [
        "# Verification notes", "",
        "round " + params["round_key"],
        "round index " + str(params["round_index"]),
        "workbook sheet key " + str(params["header"]["workbook_round_cell"]),
        "jobs in force " + str(len(jobs)),
        "jobs set aside " + str(len(model["aside"])),
        "edges accepted " + str(len(accepted_pairs)),
        "edges rejected " + str(len(model["edge_rejected"])),
        "amendments applied " + str(len(records)),
        "amendments classified inert " + str(inert),
        "precinct optima moved " + str(moved),
        "cells in the model " + str(sum(totals.values())),
        "cells recomputed after the build "
        + str(sum(sum(s["counters"]["recomputed"].values())
                  for s in stages[1:])),
        "store retention " + str(store.retention),
        "store evictions " + str(store.evictions),
        "baseline total mills " + str(baseline["total_mills"]),
        "final total mills " + str(final["total_mills"]),
        ""])

    write_json(out / "25_summary.json", {
        "round_key": params["round_key"],
        "round_index": params["round_index"],
        "package": PACKAGE_NAME,
        "modules": PACKAGE_MODULES,
        "control_totals": {
            "jobs_in_force": len(jobs),
            "jobs_set_aside": len(model["aside"]),
            "edges_accepted": len(accepted_pairs),
            "edges_rejected": len(model["edge_rejected"]),
            "groups_open": len(model["groups"]),
            "amendments_applied": len(records),
            "baseline_total_mills": baseline["total_mills"],
            "final_total_mills": final["total_mills"],
            "baseline_accepted_jobs": baseline["accepted_job_count"],
            "final_accepted_jobs": final["accepted_job_count"],
            "cells_in_model": sum(totals.values()),
            "cells_recomputed_after_build":
                sum(sum(s["counters"]["recomputed"].values()) for s in stages[1:]),
            "subsets_examined_after_build":
                sum(s["counters"]["subsets_examined"] for s in stages[1:]),
            "cache_hits": store.hits,
            "cache_evictions": store.evictions},
        "final_weighted_resource": final["weighted_resource"]})

    manifest = []
    for name in ARTIFACT_NAMES:
        if name == "24_run_manifest.txt":
            continue
        manifest.append(name + " " + digest_file(out / name))
    manifest.append("publication " + digest_text(NL.join(manifest) + NL))
    write_lines(out / "24_run_manifest.txt", manifest)
    WRONG = set()
    return out


# --------------------------------------------------------------------------
# assembling one paper directory
#
# The tables go down first, then two of them are moved so the round lands on
# the two boundaries the stage papers describe: one precinct whose accepted
# set uses its crew pool to the last minute, and one precinct where two
# different accepted sets carry the same charge and the objective has to reach
# past the charge to settle between them.
# --------------------------------------------------------------------------
def _write_header(root, E):
    write_json(root / "round_header.json", {
        "round_key": E["round_key"],
        "round_index": E["round_index"],
        "yard": E["yard"],
        "sealed_on": E["sealed_on"],
        "workbook_round_cell": E["workbook_round_cell"],
        "register_in_force": "berth_job_register_frozen.csv",
        "amendment_window": len(AMENDMENT_KINDS)})


def _write_tables(root, E):
    _write_header(root, E)
    write_job_registers(root, E)
    write_crosswalk(root, E)
    write_edge_journal(root, E)
    write_groups(root, E)
    write_capacity(root, E)
    write_carryover(root, E)
    write_charge_rules(root, E)
    write_class_rates(root, E)
    write_class_vocabulary(root, E)
    write_licences(root, E)
    write_reason_catalogue(root, E)
    write_source_priority(root, E)
    write_legacy_scale(root, E)
    write_topology(root, E)
    write_archive(root, E)
    write_workbook(root, E)
    write_board_memo(root, E)
    write_directive(root, E)


def _carried(model, precinct, pool):
    return sum(c["quantity"] for c in model["carryover"].values()
               if c["precinct"] == precinct and c["pool"] == pool)


def _engineer_boundary(root, E):
    """Bring one precinct's crew pool down until the accepted set uses every
    minute of it, so the reading of the capacity test decides the round."""
    target = E["precincts"][4]["code"]
    ctx = ref_open(root)
    body = ctx["cells"][cell_id("solve", target)]["value"]
    usage = body["usage"]["crew_minutes"]
    if usage < 60:
        return False
    want = usage + _carried(ctx["model"], target, "crew_minutes")
    if want == E["capacity"][target]["crew_minutes"]:
        return True
    E["capacity"][target]["crew_minutes"] = want
    write_capacity(root, E)
    ctx = ref_open(root)
    body = ctx["cells"][cell_id("solve", target)]["value"]
    return body["usage"]["crew_minutes"] == body["available"]["crew_minutes"]


def _engineer_rebate(root, E):
    """Lift each closure rebate until the job it hangs on is worth taking, so
    the rebate and the surcharges of that precinct both bear on one round and
    the order the directive puts them in decides the charge."""
    fired = True
    for rule in E["rules"]:
        if rule["kind"] != "closure_rebate" or rule["state"] != "in_force":
            continue
        anchor = rule["anchor_job"]
        precinct = rule["precinct"]
        seated = False
        for bp in range(int(rule["rebate_bp"]), 12001, 100):
            rule["rebate_bp"] = bp
            write_charge_rules(root, E)
            ctx = ref_open(root)
            body = ctx["cells"][cell_id("solve", precinct)]["value"]
            if anchor in body["closed_set"] and body["surcharge_mills"] > 0:
                seated = True
                break
        fired = fired and seated
    return fired


def _charge_for(base, bp):
    return half_up(Fraction(int(base) * int(bp), 10000))


def _base_for(target_charge, bp):
    """The whole base charge that scales to exactly this charge."""
    guess = int(Fraction(int(target_charge) * 10000, int(bp)))
    for cand in range(max(1, guess - 40), guess + 41):
        if _charge_for(cand, bp) == target_charge:
            return cand
    return None


def _cost_only_winner(found):
    best = None
    for key, body in found:
        if best is None or key[0] < best[0][0]:
            best = (key, body)
    return best


def _first_seen(found):
    """Each distinct accepted set with the mask position it first appears at."""
    out = {}
    for index, (key, body) in enumerate(found):
        name = tuple(body["closed_set"])
        if name not in out:
            out[name] = (index, key, body)
    return out


def _try_tie(root, E, target, jid, gap, rise):
    """Move one base charge by the gap and hand back the reopened round."""
    job = E["by_id"].get(jid)
    if job is None:
        return None
    ctx = ref_open(root)
    bp = ctx["model"]["params"]["class_bp"][job["class"]]
    scaled = _charge_for(job["base_charge"], bp)
    want = scaled + gap if rise else scaled - gap
    if want < 1000:
        return None
    fresh = _base_for(want, bp)
    if fresh is None or fresh < 1000:
        return None
    held = job["base_charge"]
    job["base_charge"] = fresh
    write_job_registers(root, E)
    return held


def _engineer_tie(root, E):
    """Bring one base charge down until the accepted set of one precinct and
    one set behind it carry the same charge, so the round cannot be settled on
    the charge alone and the resource criterion has to decide it."""
    target = E["precincts"][5]["code"]
    ctx = ref_open(root)
    _stats, found, _best = evaluate(ctx["model"], ctx["cells"], target)
    if not found:
        return False
    seen = _first_seen(found)
    head_name, (_hi, head_key, _hb) = min(seen.items(), key=lambda kv: kv[1][1])
    behind = sorted(((name, entry) for name, entry in seen.items()
                     if name != head_name and entry[1][0] > head_key[0]),
                    key=lambda kv: kv[1][1][0] - head_key[0])
    for name, (_index, key, _body) in behind[:80]:
        gap = key[0] - head_key[0]
        for jid in sorted(set(name) - set(head_name)):
            held = _try_tie(root, E, target, jid, gap, False)
            if held is None:
                continue
            probe = ref_open(root)
            _s, found2, best2 = evaluate(probe["model"], probe["cells"], target)
            naive = _cost_only_winner(found2)
            level = sum(1 for _n, (_i, k, _b) in _first_seen(found2).items()
                        if k[0] == best2["total_mills"])
            if (level >= 2 and naive is not None
                    and list(naive[1]["closed_set"]) != list(best2["closed_set"])):
                return True
            E["by_id"][jid]["base_charge"] = held
            write_job_registers(root, E)
    return False


def _write_withdrawn(root, E):
    """The publication the desk pulled, and the counters it published beside
    it. Both were produced by the engine as it stands and neither settles
    anything."""
    rng = Rng(child_seed(E["seed"], "withdrawn"))
    scratch = Path(tempfile.mkdtemp(prefix="slwopt-withdrawn-"))
    try:
        ref_publish(root, scratch, WITHDRAWN_RULES)
        selection = read_json(scratch / "18_final_selection.json")
        counters = read_delim(scratch / "16_work_counters.csv")
    finally:
        pass
    taken = set()
    for body in selection["precincts"]:
        taken.update(body["closed_set"])
    rows = []
    for job in E["jobs"]:
        rows.append([job["job_id"], job["precinct"],
                     "accepted" if job["job_id"] in taken else "deferred",
                     job["class"], job["base_charge"], "withdrawn"])
    for i in range(160):
        rows.append(["JOB-" + str(8000 + 3 * i), PRECINCT_SHAPES[i % 6][0],
                     rng.pick(["accepted", "deferred"]), CLASSES[i % 4],
                     rng.between(18000, 94000), "prior round"])
    rows.sort(key=lambda r: r[0])
    write_delim(root / "withdrawn_plan_publication.tsv",
                ["job_id", "precinct", "disposition", "class",
                 "base_charge_mills", "state"], rows, TAB)

    crows = []
    for row in counters:
        crows.append([row["stage"], row["sequence"], row["amendment_id"],
                      row["cells_visited"], row["cells_recomputed"],
                      row["subsets_examined"], "withdrawn"])
    for i in range(190):
        crows.append(["amendment", 100 + i, "AMD-" + str(300 + 3 * i),
                      rng.between(10, 300), rng.between(1, 300),
                      rng.between(0, 9000), "prior round"])
    write_delim(root / "withdrawn_counter_publication.csv",
                ["stage", "sequence", "amendment_id", "cells_visited",
                 "cells_recomputed", "subsets_examined", "state"], crows, ",")
    shutil.rmtree(scratch, ignore_errors=True)


def write_corpus(dest, seed=None):
    """Write one paper directory. Running this twice over one seed comes out
    byte identical."""
    seed = SAMPLE_SEED if seed is None else seed
    dest = Path(dest)
    root = dest / "data" if dest.name == "environment" else dest
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    E = mint(seed)
    _write_tables(root, E)
    _engineer_rebate(root, E)
    if not _engineer_boundary(root, E):
        raise SystemExit("no precinct was seated on the capacity boundary")
    if not _engineer_tie(root, E):
        raise SystemExit("no precinct was seated on a level charge")
    E["amendments"] = _amendments(E)
    write_amendments(root, E)
    write_papers(root, E)
    _write_withdrawn(root, E)
    write_project(root, E)
    return root


# --------------------------------------------------------------------------
# the repaired package source
#
# The corpus writer turns this tree into the shipped tree by applying every
# catalogued defect in reverse, so the repaired source and the source the
# agent is handed can never drift apart.
# --------------------------------------------------------------------------
PACKAGE_FILES = {
    "pyproject.toml": "[project]\nname = \"slwopt\"\nversion = \"5.2.0\"\ndescription = \"Deterministic incremental replan engine for the slipway overhaul programme.\"\nrequires-python = \">=3.12\"\ndependencies = []\n\n[build-system]\nrequires = [\"setuptools>=68\"]\nbuild-backend = \"setuptools.build_meta\"\n\n[tool.setuptools]\npackage-dir = {\"\" = \"src\"}\n",
    "README.md": "# slwopt\n\nThe replan desk's engine. It reads one round of working papers, builds the\nderived state of the round, solves each precinct exactly, then applies the\namendments the desk lodged one at a time, reusing every derived value the\namendment leaves standing.\n\n    python3 -m slwopt --data <papers> --out <destination>\n\nBoth options are accepted in either order. The destination is created when it\nis absent. The paper directory is only ever read.\n\nThe engine is standard library only on the 3.12 series.\n",
    "src/slwopt/__init__.py": "\"\"\"slwopt: the deterministic incremental replan engine.\n\nThe package reads one round of working papers, derives the state of the round\nin seven layers, solves every precinct exactly against the lexicographic\nobjective, and then folds in the amendments the desk lodged, visiting only the\nderived cells an amendment actually reaches.\n\"\"\"\nfrom pathlib import Path\n\nfrom . import publish\n\n__all__ = [\"run\", \"publish\"]\nVERSION = \"5.2.0\"\n\n\ndef run(data, out):\n    \"\"\"Replan one round out of the paper directory and publish it.\"\"\"\n    return publish.publish(Path(data), Path(out))\n",
    "src/slwopt/__main__.py": "\"\"\"Command line entry point.\"\"\"\nimport sys\nfrom pathlib import Path\n\nfrom . import run\n\n\ndef parse(argv):\n    data = None\n    out = None\n    rest = list(argv)\n    while rest:\n        head = rest.pop(0)\n        if head == \"--data\" and rest:\n            data = rest.pop(0)\n        elif head == \"--out\" and rest:\n            out = rest.pop(0)\n        else:\n            raise SystemExit(\"usage: python3 -m slwopt --data DIR --out DIR\")\n    if data is None or out is None:\n        raise SystemExit(\"usage: python3 -m slwopt --data DIR --out DIR\")\n    return Path(data), Path(out)\n\n\ndef main(argv=None):\n    data, out = parse(sys.argv[1:] if argv is None else argv)\n    if not data.is_dir():\n        raise SystemExit(\"the paper directory does not exist: \" + str(data))\n    out.mkdir(parents=True, exist_ok=True)\n    run(data, out)\n    return 0\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n",
    "src/slwopt/cache.py": "\"\"\"The working store.\n\nIt holds the value in force for every cell and, beside that, up to the\nretained number of superseded entries, so a configuration the round has\nalready stood in is read back rather than derived again. Dropping a superseded\nentry moves no published quantity: a cell whose entry has gone is simply\nderived once more.\n\"\"\"\n\n\nclass Store:\n\n    def __init__(self, retention):\n        self.retention = int(retention)\n        self.live = {}\n        self.retired = {}\n        self.stamps = {}\n        self.clock = 0\n        self.hits = 0\n        self.misses = 0\n        self.evictions = 0\n\n    def _stamp(self, marker):\n        self.clock += 1\n        self.stamps[marker] = self.clock\n\n    def _retire(self, name, entry):\n        self.retired[(name, entry[0])] = (entry[1], entry[2])\n        self._stamp((name, entry[0]))\n        while len(self.retired) > self.retention:\n            oldest = min(self.retired, key=lambda m: self.stamps.get(m, 0))\n            del self.retired[oldest]\n            self.stamps.pop(oldest, None)\n            self.evictions += 1\n\n    def take(self, name, key):\n        \"\"\"The value this cell holds for this key, when the store holds it.\"\"\"\n        standing = self.live.get(name)\n        if standing is not None and standing[0] == key:\n            self.hits += 1\n            self._stamp((name, key))\n            return standing[1], standing[2]\n        kept = self.retired.get((name, key))\n        if kept is not None:\n            self.hits += 1\n            del self.retired[(name, key)]\n            self._stamp((name, key))\n            if standing is not None:\n                self._retire(name, standing)\n            self.live[name] = (key, kept[0], kept[1])\n            return kept[0], kept[1]\n        self.misses += 1\n        return None\n\n    def put(self, name, key, value, digest):\n        standing = self.live.get(name)\n        if standing is not None and standing[0] != key:\n            self._retire(name, standing)\n        self.live[name] = (key, value, digest)\n        self._stamp((name, key))\n",
    "src/slwopt/cells.py": "\"\"\"The derived state of one round, held as seven layers of cells.\n\nEach cell carries a key over the inputs it reads and a value whose digest\ndecides whether a cascade that reaches it carries on. The key holds every\ninput the cell reads and nothing it does not read, which is what keeps a\nchange to a title out of the optimiser and a change to a capacity out of the\nclosures.\n\"\"\"\nfrom . import cache, charge, closure, graph, normalise, search\n\nLAYERS = [\"norm\", \"rule\", \"closure\", \"demand\", \"charge\", \"group\", \"solve\"]\nRANK = {name: index for index, name in enumerate(LAYERS)}\nMARK = \"|\"\n\n\ndef named(layer, name):\n    return layer + MARK + name\n\n\ndef fresh_counters():\n    return {\"visited\": {layer: 0 for layer in LAYERS},\n            \"recomputed\": {layer: 0 for layer in LAYERS},\n            \"revalidated\": {layer: 0 for layer in LAYERS},\n            \"subsets_examined\": 0}\n\n\nclass Round:\n    \"\"\"The model the round opens with, and the cells derived from it.\"\"\"\n\n    def __init__(self, root):\n        self.root = root\n        self.params = normalise.parameters(root)\n        alias = normalise.crosswalk(root)\n        self.alias = alias\n        self.jobs, aside = normalise.register(root, self.params, alias)\n        self.journal = graph.journal(root, alias)\n        accepted, rejected = graph.sift(self.journal, self.jobs)\n        self.accepted = accepted\n        self.edge_rejected = sorted(rejected)\n        for name in graph.in_a_cycle(self.accepted, sorted(self.jobs)):\n            aside.append((name, \"JOB-CYCLE\", self.jobs[name][\"precinct\"]))\n            del self.jobs[name]\n        for name in list(self.accepted):\n            if name not in self.jobs:\n                del self.accepted[name]\n            else:\n                self.accepted[name] = [step for step in self.accepted[name]\n                                       if step in self.jobs]\n        self.aside = sorted(aside)\n        self.groups, group_rejected = graph.groups(root, self.jobs)\n        self.group_rejected = sorted(group_rejected)\n        self.meta = {name: {field: self.jobs[name][field]\n                            for field in charge.PRESENTATION_FIELDS}\n                     for name in self.jobs}\n        self.rules = {}\n        for record in graph.reading.records(root / \"conditional_charge_rules.jsonl\"):\n            if record.get(\"state\") == \"in_force\":\n                self.rules[record[\"rule_id\"]] = dict(record)\n        self.capacity = self._capacity(root)\n        self.carryover = self._carryover(root)\n        self.precincts = sorted({self.jobs[name][\"precinct\"]\n                                 for name in self.jobs})\n        self.depth = {}\n        for precinct in self.precincts:\n            self._rank(precinct)\n        self.cells = {}\n        self.store = cache.Store(self.params[\"retention\"])\n        self.inverse = {}\n\n    def _capacity(self, root):\n        index = self.params[\"round_index\"]\n        held = {}\n        for row in graph.reading.delimited(root / \"pool_capacity_history.tsv\",\n                                           graph.reading.TAB):\n            if row[\"state\"] != \"in_force\" or int(row[\"effective_round\"]) > index:\n                continue\n            marker = (row[\"precinct\"], row[\"pool\"])\n            standing = held.get(marker)\n            if standing is None or int(row[\"effective_round\"]) >= standing[0]:\n                held[marker] = (int(row[\"effective_round\"]), int(row[\"capacity\"]))\n        return {marker: value[1] for marker, value in held.items()}\n\n    def _carryover(self, root):\n        out = {}\n        for row in graph.reading.delimited(root / \"carried_commitment_ledger.csv\"):\n            if row[\"state\"] == \"binding\":\n                out[row[\"commitment_id\"]] = {\"precinct\": row[\"precinct\"],\n                                             \"pool\": row[\"pool\"],\n                                             \"quantity\": int(row[\"quantity\"])}\n        return out\n\n    def in_precinct(self, precinct):\n        return [name for name in sorted(self.jobs)\n                if self.jobs[name][\"precinct\"] == precinct]\n\n    def _rank(self, precinct):\n        names = self.in_precinct(precinct)\n        self.depth.update(graph.depths(self.accepted, names))\n\n    def refresh_edges(self, precinct):\n        \"\"\"Rebuild the accepted prerequisite lists of one precinct.\"\"\"\n        fresh = graph.within(self.journal, self.jobs, precinct)\n        for name in list(self.accepted):\n            if name in self.jobs and self.jobs[name][\"precinct\"] == precinct:\n                del self.accepted[name]\n        self.accepted.update(fresh)\n        self._rank(precinct)\n\n    # -- the cell table -------------------------------------------------\n    def inputs_of(self, marker):\n        layer, name = marker.split(MARK, 1)\n        if layer == \"norm\":\n            return charge.norm_inputs(self, name)\n        if layer == \"rule\":\n            return charge.rule_inputs(self, name)\n        if layer == \"closure\":\n            return closure.closure_inputs(self, name, self.cells)\n        if layer == \"demand\":\n            return closure.demand_inputs(self, name, self.cells)\n        if layer == \"charge\":\n            return charge.charge_inputs(self, name, self.cells)\n        if layer == \"group\":\n            return charge.group_inputs(self, name, self.cells)\n        return search.solve_inputs(self, name, self.cells)\n\n    def value_of(self, marker):\n        layer, name = marker.split(MARK, 1)\n        if layer == \"norm\":\n            return charge.norm(self, name)\n        if layer == \"rule\":\n            return charge.rule(self, name)\n        if layer == \"closure\":\n            return closure.closure(self, name, self.cells)\n        if layer == \"demand\":\n            return closure.demand(self, name, self.cells)\n        if layer == \"charge\":\n            return charge.charge(self, name, self.cells)\n        if layer == \"group\":\n            return charge.group(self, name, self.cells)\n        return search.sweep(self, name, self.cells)\n\n    def order_of(self, marker):\n        layer, name = marker.split(MARK, 1)\n        depth = self.depth.get(name, 0) if layer == \"closure\" else 0\n        return (RANK[layer], depth, marker)\n\n    def readers_of(self, marker):\n        \"\"\"The cells that read this one.\"\"\"\n        layer, name = marker.split(MARK, 1)\n        if layer == \"norm\":\n            precinct = self.jobs[name][\"precinct\"]\n            out = [named(\"closure\", name), named(\"demand\", name),\n                   named(\"charge\", name)]\n            for other in sorted(graph.readers_of(self.accepted, name,\n                                                 self.jobs, precinct)):\n                out.append(named(\"demand\", other))\n            for group_id in sorted(self.groups):\n                if name in self.groups[group_id][\"members\"]:\n                    out.append(named(\"group\", group_id))\n            out.append(named(\"solve\", precinct))\n            return out\n        if layer == \"rule\":\n            return [named(\"solve\", self.rules[name][\"precinct\"])]\n        if layer == \"closure\":\n            precinct = self.jobs[name][\"precinct\"]\n            out = [named(\"demand\", name)]\n            for other in sorted(self.accepted):\n                if name in self.accepted[other] and other in self.jobs:\n                    out.append(named(\"closure\", other))\n            out.append(named(\"solve\", precinct))\n            return out\n        if layer in (\"demand\", \"charge\"):\n            return [named(\"solve\", self.jobs[name][\"precinct\"])]\n        if layer == \"group\":\n            return [named(\"solve\", self.groups[name][\"precinct\"])]\n        return []\n\n    # -- visiting -------------------------------------------------------\n    def visit(self, marker, counters, trail):\n        layer = marker.split(MARK, 1)[0]\n        key = normalise.digest(self.inputs_of(marker))\n        counters[\"visited\"][layer] += 1\n        held = self.store.take(marker, key)\n        if held is None:\n            value = self.value_of(marker)\n            digest = normalise.digest(value)\n            self.store.put(marker, key, value, digest)\n            counters[\"recomputed\"][layer] += 1\n            if layer == \"solve\":\n                counters[\"subsets_examined\"] += value[\"subsets_examined\"]\n            trail.append((marker, \"recomputed\"))\n        else:\n            value, digest = held\n            trail.append((marker, \"read_from_store\"))\n        standing = self.cells.get(marker)\n        self.cells[marker] = {\"key\": key, \"value\": normalise.copy_of(value),\n                              \"digest\": digest}\n        if standing is not None and standing[\"digest\"] == digest:\n            counters[\"revalidated\"][layer] += 1\n            trail[-1] = (marker, \"revalidated\")\n            return False\n        return True\n\n    def cascade(self, seeds, counters):\n        waiting = set(seeds)\n        done = set()\n        trail = []\n        moved = []\n        while waiting:\n            marker = min(waiting, key=self.order_of)\n            waiting.discard(marker)\n            if marker in done:\n                continue\n            done.add(marker)\n            if self.visit(marker, counters, trail):\n                moved.append(marker)\n                for reader in self.readers_of(marker):\n                    if reader not in done:\n                        waiting.add(reader)\n        return trail, moved\n\n    def open_round(self):\n        \"\"\"Stages p04 to p12. Every cell built once, in canonical order.\"\"\"\n        counters = fresh_counters()\n        markers = []\n        for name in sorted(self.jobs):\n            markers.append(named(\"norm\", name))\n            markers.append(named(\"closure\", name))\n            markers.append(named(\"demand\", name))\n            markers.append(named(\"charge\", name))\n        for rule_id in sorted(self.rules):\n            markers.append(named(\"rule\", rule_id))\n        for group_id in sorted(self.groups):\n            markers.append(named(\"group\", group_id))\n        for precinct in self.precincts:\n            markers.append(named(\"solve\", precinct))\n        trail = []\n        for marker in sorted(markers, key=self.order_of):\n            self.visit(marker, counters, trail)\n        return counters\n\n    def layer_totals(self):\n        out = {layer: 0 for layer in LAYERS}\n        for marker in self.cells:\n            out[marker.split(MARK, 1)[0]] += 1\n        return out\n",
    "src/slwopt/charge.py": "\"\"\"Stages p03, p04 and p07. The per job layers and the rule layer.\n\nThe norm layer holds what the register says about a job once the units are\nput right and the licence and the round window are tested. The charge layer\nholds the class scaled charge and the deferral penalty. The rule layer holds\none conditional charge rule with its amount put into whole mills.\n\"\"\"\nfrom fractions import Fraction\n\nfrom . import normalise\n\nREGISTER_FIELDS = [\"base_charge_mills\", \"berth_quantity\", \"berth_unit\",\n                   \"class\", \"crane_lifts\", \"crew_quantity\", \"crew_unit\",\n                   \"deferral_weight\", \"earliest_round\", \"job_id\",\n                   \"latest_round\", \"licence_code\", \"precinct\", \"standing\"]\n\nRULE_FIELDS = [\"amount_text\", \"anchor_job\", \"class\", \"first_job\", \"kind\",\n               \"pool\", \"precinct\", \"rebate_bp\", \"rule_id\", \"second_job\",\n               \"state\", \"threshold\"]\n\nPRESENTATION_FIELDS = [\"display_order\", \"note\", \"owner\", \"title\"]\n\n\ndef norm_inputs(model, name):\n    job = model.jobs[name]\n    licence = model.params[\"licences\"].get(job[\"licence_code\"], {})\n    return [{field: job[field] for field in REGISTER_FIELDS},\n            model.params[\"shift_minutes\"].get(job[\"precinct\"]),\n            [licence.get(\"state\"), licence.get(\"valid_from_round\"),\n             licence.get(\"valid_to_round\")],\n            model.params[\"round_index\"]]\n\n\ndef norm(model, name):\n    job = model.jobs[name]\n    params = model.params\n    shift = int(params[\"shift_minutes\"][job[\"precinct\"]])\n    crew = int(job[\"crew_quantity\"])\n    if job[\"crew_unit\"] == \"shift\":\n        crew = crew * shift\n    berth = int(job[\"berth_quantity\"])\n    if job[\"berth_unit\"] == \"day\":\n        berth = berth * 4\n    licence = params[\"licences\"].get(job[\"licence_code\"])\n    index = params[\"round_index\"]\n    admissible = True\n    reason = \"\"\n    if (licence is None or licence[\"state\"] != \"valid\"\n            or not (int(licence[\"valid_from_round\"]) <= index\n                    <= int(licence[\"valid_to_round\"]))):\n        admissible = False\n        reason = \"JOB-LICENCE\"\n    elif not (int(job[\"earliest_round\"]) <= index <= int(job[\"latest_round\"])):\n        admissible = False\n        reason = \"JOB-OUTOFROUND\"\n    return {\"job_id\": name, \"precinct\": job[\"precinct\"], \"class\": job[\"class\"],\n            \"standing\": job[\"standing\"],\n            \"base_charge_mills\": int(job[\"base_charge_mills\"]),\n            \"berth_quarter_days\": berth, \"crane_lifts\": int(job[\"crane_lifts\"]),\n            \"crew_minutes\": crew,\n            \"deferral_weight\": int(job[\"deferral_weight\"]),\n            \"admissible\": admissible, \"admission_reason\": reason}\n\n\ndef charge_inputs(model, name, seen):\n    klass = seen[\"norm|\" + name][\"value\"][\"class\"]\n    return [seen[\"norm|\" + name][\"digest\"],\n            model.params[\"class_bp\"].get(klass),\n            model.params[\"deferral_rate\"].get(klass)]\n\n\ndef charge(model, name, seen):\n    held = seen[\"norm|\" + name][\"value\"]\n    params = model.params\n    points = int(params[\"class_bp\"][held[\"class\"]])\n    scaled = normalise.half_up(\n        Fraction(int(held[\"base_charge_mills\"]) * points, 10000))\n    penalty = (int(params[\"deferral_rate\"][held[\"class\"]])\n               * int(held[\"deferral_weight\"]))\n    return {\"job_id\": name, \"scaled_charge_mills\": scaled,\n            \"deferral_penalty_mills\": penalty, \"multiplier_bp\": points,\n            \"implausible\": scaled > int(params[\"ceiling\"])}\n\n\ndef rule_inputs(model, name):\n    record = model.rules[name]\n    return {field: record.get(field) for field in RULE_FIELDS}\n\n\ndef rule(model, name):\n    record = model.rules[name]\n    out = {\"rule_id\": name, \"precinct\": record[\"precinct\"],\n           \"kind\": record[\"kind\"]}\n    if record[\"kind\"] == \"pair_surcharge\":\n        out[\"first_job\"] = record[\"first_job\"]\n        out[\"second_job\"] = record[\"second_job\"]\n        out[\"amount_mills\"] = normalise.amount(record[\"amount_text\"])\n    elif record[\"kind\"] == \"threshold_surcharge\":\n        out[\"pool\"] = record[\"pool\"]\n        out[\"threshold\"] = int(record[\"threshold\"])\n        out[\"class\"] = record[\"class\"]\n        out[\"amount_mills\"] = normalise.amount(record[\"amount_text\"])\n    else:\n        out[\"anchor_job\"] = record[\"anchor_job\"]\n        out[\"rebate_bp\"] = int(record[\"rebate_bp\"])\n    return out\n\n\ndef group_inputs(model, name, seen):\n    entry = model.groups[name]\n    members = sorted(m for m in entry[\"members\"] if m in model.jobs)\n    return [members, entry[\"precedence\"], entry[\"precinct\"],\n            [seen[\"norm|\" + m][\"digest\"] for m in members]]\n\n\ndef group(model, name, seen):\n    entry = model.groups[name]\n    members = sorted(m for m in entry[\"members\"] if m in model.jobs)\n    return {\"group_id\": name, \"precinct\": entry[\"precinct\"],\n            \"precedence\": entry[\"precedence\"], \"members\": members,\n            \"binding\": len(members) >= 2}\n",
    "src/slwopt/closure.py": "\"\"\"Stages p05 and p06. The closure layer and the demand layer.\n\nThe closure of a job is every job that stands behind it, however far back. A\njob is blocked when it is inadmissible itself or when anything in its closure\nis, and a blocked job is never selectable. The demand layer holds what a job\ndraws on its own and what the closed set it opens draws once each distinct\njob is counted one time.\n\"\"\"\nfrom . import normalise\n\nPOOLS = normalise.POOLS\n\n\ndef closure_inputs(model, name, seen):\n    behind = model.accepted.get(name, [])\n    return [behind,\n            [seen[\"closure|\" + step][\"digest\"] for step in behind\n             if \"closure|\" + step in seen],\n            seen[\"norm|\" + name][\"digest\"]]\n\n\ndef closure(model, name, seen):\n    walk = list(model.accepted.get(name, []))\n    reached = set()\n    missing = False\n    while walk:\n        here = walk.pop()\n        if here in reached or here == name:\n            continue\n        if here not in model.jobs:\n            missing = True\n            continue\n        reached.add(here)\n        walk.extend(model.accepted.get(here, []))\n    own = seen[\"norm|\" + name][\"value\"]\n    blocked = False\n    reason = \"\"\n    if not own[\"admissible\"]:\n        blocked = True\n        reason = own[\"admission_reason\"]\n    elif missing or any(not seen[\"norm|\" + step][\"value\"][\"admissible\"]\n                        for step in reached):\n        blocked = True\n        reason = \"JOB-CLOSUREBLOCKED\"\n    return {\"job_id\": name, \"closure\": sorted(reached), \"blocked\": blocked,\n            \"reason\": reason}\n\n\ndef demand_inputs(model, name, seen):\n    held = seen[\"closure|\" + name]\n    members = sorted(set([name] + list(held[\"value\"][\"closure\"])))\n    return [held[\"digest\"], [seen[\"norm|\" + m][\"digest\"] for m in members]]\n\n\ndef demand(model, name, seen):\n    own = seen[\"norm|\" + name][\"value\"]\n    members = sorted(set([name] + list(seen[\"closure|\" + name][\"value\"][\"closure\"])))\n    closed = {}\n    for pool in POOLS:\n        closed[pool] = sum(seen[\"norm|\" + m][\"value\"][pool] for m in members)\n    return {\"job_id\": name, \"own\": {pool: own[pool] for pool in POOLS},\n            \"closed\": closed}\n",
    "src/slwopt/graph.py": "\"\"\"Stage p02. The precedence graph and the indexes the cascade walks.\n\nAn edge journal row is a lodgement, not a prerequisite. A row becomes a\nprerequisite only once it has survived the crosswalk, the status test, the\nkind test, the self test, the precinct test and the duplicate test. Two rows\nthat name the same pair after the crosswalk are one prerequisite.\n\"\"\"\nfrom . import reading\n\nREJECTIONS = [\"EDG-WITHDRAWN\", \"EDG-ADVISORY\", \"EDG-SELF\", \"EDG-UNKNOWNJOB\",\n              \"EDG-CROSSPRECINCT\", \"EDG-DUPLICATE\"]\n\n\ndef journal(root, alias):\n    \"\"\"Every lodgement, with both ends put through the crosswalk.\"\"\"\n    out = {}\n    for row in reading.delimited(root / \"precedence_edge_journal.psv\",\n                                 reading.PIPE):\n        out[row[\"edge_id\"]] = {\n            \"requiring_job\": alias.get(row[\"requiring_job\"], row[\"requiring_job\"]),\n            \"required_job\": alias.get(row[\"required_job\"], row[\"required_job\"]),\n            \"kind\": row[\"kind\"], \"status\": row[\"status\"]}\n    return out\n\n\ndef sift(rows, jobs):\n    \"\"\"Accepted prerequisite lists and one rejection row per lodgement the\n    papers turn down.\"\"\"\n    accepted = {}\n    rejected = []\n    seen = set()\n    for edge_id in sorted(rows):\n        row = rows[edge_id]\n        requiring = row[\"requiring_job\"]\n        required = row[\"required_job\"]\n        trail = (edge_id, requiring, required)\n        if row[\"status\"] != \"active\":\n            rejected.append(trail + (\"EDG-WITHDRAWN\",))\n        elif row[\"kind\"] != \"hard\":\n            rejected.append(trail + (\"EDG-ADVISORY\",))\n        elif requiring == required:\n            rejected.append(trail + (\"EDG-SELF\",))\n        elif requiring not in jobs or required not in jobs:\n            rejected.append(trail + (\"EDG-UNKNOWNJOB\",))\n        elif jobs[requiring][\"precinct\"] != jobs[required][\"precinct\"]:\n            rejected.append(trail + (\"EDG-CROSSPRECINCT\",))\n        elif (requiring, required) in seen:\n            rejected.append(trail + (\"EDG-DUPLICATE\",))\n        else:\n            seen.add((requiring, required))\n            accepted.setdefault(requiring, []).append(required)\n    for requiring in accepted:\n        accepted[requiring].sort()\n    return accepted, rejected\n\n\ndef within(rows, jobs, precinct):\n    \"\"\"The accepted prerequisite lists of one precinct on their own.\"\"\"\n    accepted = {}\n    seen = set()\n    for edge_id in sorted(rows):\n        row = rows[edge_id]\n        requiring = row[\"requiring_job\"]\n        required = row[\"required_job\"]\n        if requiring not in jobs or jobs[requiring][\"precinct\"] != precinct:\n            continue\n        if row[\"status\"] != \"active\" or row[\"kind\"] != \"hard\":\n            continue\n        if requiring == required or required not in jobs:\n            continue\n        if jobs[required][\"precinct\"] != precinct:\n            continue\n        if (requiring, required) in seen:\n            continue\n        seen.add((requiring, required))\n        accepted.setdefault(requiring, []).append(required)\n    for requiring in accepted:\n        accepted[requiring].sort()\n    return accepted\n\n\ndef stands_behind(accepted, start, target):\n    \"\"\"Whether the target stands among the prerequisites of the start job.\"\"\"\n    walk = [start]\n    seen = set()\n    while walk:\n        here = walk.pop()\n        if here == target and here != start:\n            return True\n        if here in seen:\n            continue\n        seen.add(here)\n        for step in accepted.get(here, []):\n            if step == target:\n                return True\n            walk.append(step)\n    return False\n\n\ndef depths(accepted, names):\n    \"\"\"Longest chain below each job, so a cascade reaches a prerequisite\n    before the job that names it.\"\"\"\n    out = {}\n\n    def walk(name, active):\n        if name in out:\n            return out[name]\n        if name in active:\n            return 0\n        active = active | {name}\n        best = 0\n        for step in accepted.get(name, []):\n            best = max(best, 1 + walk(step, active))\n        out[name] = best\n        return best\n\n    for name in names:\n        walk(name, frozenset())\n    return out\n\n\ndef in_a_cycle(accepted, names):\n    return sorted(name for name in names\n                  if stands_behind(accepted, name, name)\n                  or name in accepted.get(name, []))\n\n\ndef reverse(accepted):\n    out = {}\n    for requiring in sorted(accepted):\n        for required in accepted[requiring]:\n            out.setdefault(required, []).append(requiring)\n    return {k: sorted(v) for k, v in out.items()}\n\n\ndef readers_of(accepted, name, jobs, precinct):\n    \"\"\"Every job of this precinct whose closure holds this one.\"\"\"\n    out = set()\n    for other in jobs:\n        if jobs[other][\"precinct\"] != precinct or other == name:\n            continue\n        if stands_behind(accepted, other, name):\n            out.add(other)\n    return out\n\n\ndef groups(root, jobs):\n    \"\"\"Stage p08. Open memberships, with a job standing in two open groups\n    kept by the group of the lower precedence number.\"\"\"\n    rows = [row for row in reading.delimited(root / \"exclusive_slot_groups.csv\")\n            if row[\"state\"] == \"open\" and row[\"member_job\"] in jobs]\n    owner = {}\n    for row in sorted(rows, key=lambda r: (int(r[\"precedence\"]), r[\"group_id\"],\n                                           r[\"member_job\"])):\n        owner.setdefault(row[\"member_job\"], row[\"group_id\"])\n    held = {}\n    rejected = []\n    for row in sorted(rows, key=lambda r: (r[\"group_id\"], r[\"member_job\"])):\n        if owner[row[\"member_job\"]] != row[\"group_id\"]:\n            rejected.append((row[\"group_id\"], row[\"member_job\"],\n                             \"GRP-DOUBLEBOOKED\"))\n            continue\n        entry = held.setdefault(row[\"group_id\"],\n                                {\"group_id\": row[\"group_id\"],\n                                 \"precinct\": row[\"precinct\"],\n                                 \"precedence\": int(row[\"precedence\"]),\n                                 \"members\": []})\n        entry[\"members\"].append(row[\"member_job\"])\n    for entry in held.values():\n        entry[\"members\"].sort()\n    return held, rejected\n",
    "src/slwopt/mutate.py": "\"\"\"Stage p13. The amendments, their classification and their cascade.\n\nAn amendment is classified by its kind. The seed set is the cell or cells the\ndirective names for that kind and nothing else. A reversal carries the seed\nset of the amendment it names, and a restatement carries the seed set its own\nkind would carry, which is why a restatement whose normalised value stands\nunchanged reaches the rule cell and stops there.\n\"\"\"\nfrom . import cells, graph, normalise\n\nJOURNAL = \"amendment_journal.jsonl\"\nSUPPLEMENT = \"amendment_supplement.ndjson\"\nPROVENANCE = \"row_provenance_ledger.csv\"\n\n\ndef lodged(root):\n    \"\"\"The lodged amendments in sequence, with the payload fields the\n    supplement completes folded in under the provenance ledger.\"\"\"\n    rows = [record for record in graph.reading.records(root / JOURNAL)\n            if record.get(\"state\") == \"lodged\"]\n    late = {}\n    for record in graph.reading.records(root / SUPPLEMENT):\n        if record.get(\"state\") == \"in_force\":\n            late[(record[\"amendment_id\"], record[\"field\"])] = record[\"value\"]\n    source = {}\n    for row in graph.reading.delimited(root / PROVENANCE):\n        if row[\"state\"] == \"in_force\":\n            source[(row[\"amendment_id\"], row[\"field\"])] = row[\"source_file\"]\n    out = []\n    for record in sorted(rows, key=lambda r: int(r[\"sequence\"])):\n        payload = dict(record.get(\"payload\") or {})\n        for (amendment_id, field), value in sorted(late.items()):\n            if amendment_id != record[\"amendment_id\"]:\n                continue\n            if source.get((amendment_id, field)) != SUPPLEMENT:\n                continue\n            payload[field] = value\n        out.append({\"amendment_id\": record[\"amendment_id\"],\n                    \"sequence\": int(record[\"sequence\"]),\n                    \"kind\": record[\"kind\"], \"payload\": payload,\n                    \"note\": record.get(\"note\", \"\")})\n    return out\n\n\ndef seeds_for(model, kind, payload):\n    if kind == \"job_note_revision\":\n        return []\n    if kind == \"job_field_revision\":\n        return [cells.named(\"norm\", payload[\"job_id\"])]\n    if kind in (\"edge_lodged\", \"edge_withdrawn\"):\n        return [cells.named(\"closure\", payload[\"requiring_job\"])]\n    if kind == \"group_member_revision\":\n        return [cells.named(\"group\", payload[\"group_id\"])]\n    if kind in (\"capacity_revision\", \"carryover_revision\"):\n        return [cells.named(\"solve\", payload[\"precinct\"])]\n    if kind in (\"charge_rule_revision\", \"restatement\"):\n        return [cells.named(\"rule\", payload[\"rule_id\"])]\n    if kind == \"class_rate_revision\":\n        return [cells.named(\"charge\", name) for name in sorted(model.jobs)\n                if model.jobs[name][\"class\"] == payload[\"class\"]]\n    raise SystemExit(\"the directive classifies no kind \" + kind)\n\n\ndef resolve(model, amendment):\n    \"\"\"Fill in what the payload needs, and turn down a lodgement the papers\n    do not accept.\"\"\"\n    kind = amendment[\"kind\"]\n    payload = dict(amendment[\"payload\"])\n    if kind == \"reversal\":\n        named = model.inverse.get(payload[\"amendment_id\"])\n        if named is None:\n            return \"reversal\", payload, \"rejected\", \"AMD-NOTARGET\"\n        return named[0], dict(named[1]), \"governed\", \"\"\n    if kind == \"edge_lodged\":\n        requiring = payload[\"requiring_job\"]\n        required = payload[\"required_job\"]\n        payload[\"edge_id\"] = amendment[\"amendment_id\"] + \"-E\"\n        if requiring not in model.jobs or required not in model.jobs:\n            return kind, payload, \"rejected\", \"EDG-UNKNOWNJOB\"\n        if requiring == required:\n            return kind, payload, \"rejected\", \"EDG-SELF\"\n        if model.jobs[requiring][\"precinct\"] != model.jobs[required][\"precinct\"]:\n            return kind, payload, \"rejected\", \"EDG-CROSSPRECINCT\"\n        if graph.stands_behind(model.accepted, required, requiring):\n            return kind, payload, \"rejected\", \"EDG-CYCLE\"\n        if required in model.accepted.get(requiring, []):\n            return kind, payload, \"rejected\", \"EDG-DUPLICATE\"\n    if kind == \"edge_withdrawn\":\n        row = model.journal.get(payload[\"edge_id\"])\n        if row is None or row[\"requiring_job\"] not in model.jobs:\n            return kind, payload, \"rejected\", \"EDG-UNKNOWNJOB\"\n        payload[\"requiring_job\"] = row[\"requiring_job\"]\n        payload[\"required_job\"] = row[\"required_job\"]\n    if kind == \"carryover_revision\":\n        if payload[\"commitment_id\"] not in model.carryover:\n            return kind, payload, \"rejected\", \"CMT-UNKNOWN\"\n        payload[\"precinct\"] = model.carryover[payload[\"commitment_id\"]][\"precinct\"]\n    verdict = \"inert\" if kind == \"job_note_revision\" else \"governed\"\n    return kind, payload, verdict, \"\"\n\n\ndef apply(model, kind, payload):\n    \"\"\"Move the model and hand back the payload that puts it back.\"\"\"\n    if kind == \"job_note_revision\":\n        name, field = payload[\"job_id\"], payload[\"field\"]\n        back = {\"job_id\": name, \"field\": field,\n                \"value\": model.meta[name][field]}\n        model.meta[name][field] = payload[\"value\"]\n        return back\n    if kind == \"job_field_revision\":\n        name, field = payload[\"job_id\"], payload[\"field\"]\n        back = {\"job_id\": name, \"field\": field, \"value\": model.jobs[name][field]}\n        model.jobs[name][field] = payload[\"value\"]\n        return back\n    if kind == \"edge_lodged\":\n        model.journal[payload[\"edge_id\"]] = {\n            \"requiring_job\": payload[\"requiring_job\"],\n            \"required_job\": payload[\"required_job\"],\n            \"kind\": payload.get(\"kind\", \"hard\"), \"status\": \"active\"}\n        model.refresh_edges(model.jobs[payload[\"requiring_job\"]][\"precinct\"])\n        return {\"edge_id\": payload[\"edge_id\"]}\n    if kind == \"edge_withdrawn\":\n        row = model.journal[payload[\"edge_id\"]]\n        back = {\"edge_id\": payload[\"edge_id\"],\n                \"requiring_job\": row[\"requiring_job\"],\n                \"required_job\": row[\"required_job\"], \"kind\": row[\"kind\"]}\n        row[\"status\"] = \"withdrawn\"\n        model.refresh_edges(model.jobs[row[\"requiring_job\"]][\"precinct\"])\n        return back\n    if kind == \"group_member_revision\":\n        entry = model.groups[payload[\"group_id\"]]\n        member = payload[\"member_job\"]\n        if payload[\"action\"] == \"remove\":\n            entry[\"members\"] = [m for m in entry[\"members\"] if m != member]\n            return {\"group_id\": payload[\"group_id\"], \"member_job\": member,\n                    \"action\": \"add\"}\n        entry[\"members\"] = sorted(set(entry[\"members\"]) | {member})\n        return {\"group_id\": payload[\"group_id\"], \"member_job\": member,\n                \"action\": \"remove\"}\n    if kind == \"capacity_revision\":\n        marker = (payload[\"precinct\"], payload[\"pool\"])\n        back = {\"precinct\": payload[\"precinct\"], \"pool\": payload[\"pool\"],\n                \"capacity\": model.capacity[marker]}\n        model.capacity[marker] = int(payload[\"capacity\"])\n        return back\n    if kind == \"carryover_revision\":\n        entry = model.carryover[payload[\"commitment_id\"]]\n        back = {\"commitment_id\": payload[\"commitment_id\"],\n                \"quantity\": entry[\"quantity\"], \"precinct\": entry[\"precinct\"]}\n        entry[\"quantity\"] = int(payload[\"quantity\"])\n        return back\n    if kind in (\"charge_rule_revision\", \"restatement\"):\n        record = model.rules[payload[\"rule_id\"]]\n        back = {\"rule_id\": payload[\"rule_id\"],\n                \"amount_text\": record[\"amount_text\"]}\n        record[\"amount_text\"] = payload[\"amount_text\"]\n        return back\n    if kind == \"class_rate_revision\":\n        klass = payload[\"class\"]\n        back = {\"class\": klass, \"multiplier_bp\": model.params[\"class_bp\"][klass]}\n        model.params[\"class_bp\"][klass] = int(payload[\"multiplier_bp\"])\n        return back\n    raise SystemExit(\"no payload rule for \" + kind)\n\n\ndef fold(model, amendment):\n    \"\"\"One amendment: classify it, move the model, seed the cells the\n    directive names, and let the cascade stop where a value stands.\"\"\"\n    kind, payload, verdict, reason = resolve(model, amendment)\n    counters = cells.fresh_counters()\n    record = {\"amendment_id\": amendment[\"amendment_id\"],\n              \"sequence\": amendment[\"sequence\"],\n              \"lodged_kind\": amendment[\"kind\"], \"applied_kind\": kind,\n              \"classification\": verdict, \"reason\": reason,\n              \"seed_cells\": [], \"invalidated\": [], \"revalidated\": [],\n              \"counters\": counters}\n    if verdict == \"rejected\":\n        return record\n    back = apply(model, kind, payload)\n    model.inverse[amendment[\"amendment_id\"]] = (kind, back)\n    seeds = seeds_for(model, kind, payload)\n    trail, moved = model.cascade(seeds, counters)\n    record[\"seed_cells\"] = sorted(seeds)\n    record[\"invalidated\"] = sorted(moved)\n    record[\"revalidated\"] = sorted(marker for marker, state in trail\n                                   if state == \"revalidated\")\n    record[\"target\"] = normalise.tight(payload)\n    return record\n",
    "src/slwopt/normalise.py": "\"\"\"Exact arithmetic, canonical serialisation and the parameter layer.\n\nEvery published whole quantity is an integer in the unit its stage names and\nevery published ratio carries twelve decimal places. Rounding is half away\nfrom zero on an exact rational and happens only where a stage paper puts it.\nBinary floating point never enters the derivation.\n\"\"\"\nimport hashlib\nimport json\nfrom fractions import Fraction\nfrom pathlib import Path\n\nfrom . import reading\n\nPLACES = 12\nSCALE = 10 ** PLACES\nPOOLS = [\"berth_quarter_days\", \"crane_lifts\", \"crew_minutes\"]\nCLASSES = [\"A\", \"B\", \"C\", \"D\"]\nNEWLINE = chr(10)\n\n\ndef half_up(value):\n    \"\"\"Nearest whole number, halves away from zero, on an exact rational.\"\"\"\n    share = Fraction(value)\n    top, bottom = share.numerator, share.denominator\n    if bottom == 1:\n        return top\n    if top >= 0:\n        return (2 * top + bottom) // (2 * bottom)\n    return -((2 * (-top) + bottom) // (2 * bottom))\n\n\ndef ratio(value):\n    \"\"\"Twelve decimal places, half away from zero, never a negative zero.\"\"\"\n    scaled = half_up(Fraction(value) * SCALE)\n    sign = \"-\" if scaled < 0 else \"\"\n    scaled = abs(scaled)\n    whole, part = divmod(scaled, SCALE)\n    out = sign + str(whole) + \".\" + str(part).rjust(PLACES, \"0\")\n    if out == \"-0.\" + \"0\" * PLACES:\n        return \"0.\" + \"0\" * PLACES\n    return out\n\n\ndef ratio_of(top, bottom):\n    if int(bottom) == 0:\n        return ratio(0)\n    return ratio(Fraction(int(top), int(bottom)))\n\n\ndef tight(obj):\n    return json.dumps(obj, ensure_ascii=False, sort_keys=True,\n                      separators=(\",\", \":\"))\n\n\ndef laid_out(obj):\n    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + NEWLINE\n\n\ndef digest(obj):\n    return hashlib.sha256(tight(obj).encode(\"utf-8\")).hexdigest()\n\n\ndef digest_of_file(path):\n    return hashlib.sha256(Path(path).read_bytes()).hexdigest()\n\n\ndef copy_of(value):\n    \"\"\"A cell hands back its own copy, so a stage that walks over the value it\n    was given leaves the stored value where it stands.\"\"\"\n    return json.loads(json.dumps(value))\n\n\ndef amount(text):\n    \"\"\"One amount, however the desk wrote it, as whole mills.\"\"\"\n    raw = str(text).strip().replace(\",\", \"\")\n    if raw == \"\":\n        return 0\n    parts = raw.split()\n    number = parts[0]\n    unit = parts[1].lower() if len(parts) > 1 else \"mills\"\n    if unit == \"gbp\":\n        if \".\" in number:\n            whole, part = number.split(\".\", 1)\n            return int(whole) * 1000 + int((part + \"000\")[:3])\n        return int(number) * 1000\n    if \".\" in number:\n        whole, part = number.split(\".\", 1)\n        if int(part) != 0:\n            raise ValueError(\"an amount in mills carries no fraction\")\n        return int(whole)\n    return int(number)\n\n\ndef _live_sheet(root, header):\n    for name in sorted(reading.sheets(root / \"yard_parameter_workbook.xlsx\")):\n        rows = reading.sheets(root / \"yard_parameter_workbook.xlsx\")[name]\n        for row in rows:\n            if row and str(row[0]) == \"sheet_key\":\n                if str(row[1]) == str(header[\"workbook_round_cell\"]):\n                    return rows\n                break\n    raise SystemExit(\"no workbook sheet carries the round key cell\")\n\n\ndef workbook(root, header):\n    \"\"\"The shift lengths and the pool weights, which stand in no other paper.\"\"\"\n    rows = _live_sheet(root, header)\n    shifts = {}\n    weights = {}\n    section = \"\"\n    for row in rows:\n        if not row:\n            continue\n        head = str(row[0])\n        if head == \"section\":\n            section = str(row[1])\n        elif section == \"precinct_shift_minutes\" and head.startswith(\"PCT-\"):\n            shifts[head] = int(row[1])\n        elif section == \"pool_weights\" and head in POOLS:\n            weights[head] = (int(row[1]), int(row[2]))\n    return shifts, weights\n\n\ndef memo(root):\n    \"\"\"The deferral rates, the store retention and the charge ceiling, which\n    stand in no other paper. Only the sitting in force is read.\"\"\"\n    holding = False\n    rates = {}\n    retention = 0\n    ceiling = 0\n    for line in reading.pdf_lines(root / \"yard_board_memo.pdf\"):\n        if \"IN FORCE FOR ROUND\" in line:\n            holding = True\n            continue\n        if line.startswith(\"APPENDIX\"):\n            holding = False\n        if not holding:\n            continue\n        words = line.split()\n        if len(words) >= 3 and words[0] == \"class\" and words[1] in CLASSES:\n            rates[words[1]] = int(words[2])\n        if \"derived entries\" in line:\n            retention = int([w for w in words if w.isdigit()][0])\n        if \"a charge above\" in line:\n            ceiling = int([w for w in words if w.isdigit()][0])\n    if len(rates) != len(CLASSES) or retention <= 0 or ceiling <= 0:\n        raise SystemExit(\"the board memo did not settle the round parameters\")\n    return rates, retention, ceiling\n\n\ndef parameters(root):\n    \"\"\"Stage p01. Every control value the round stands on.\"\"\"\n    header = reading.document(root / \"round_header.json\")\n    index = int(header[\"round_index\"])\n    shifts, weights = workbook(root, header)\n    rates, retention, ceiling = memo(root)\n\n    multipliers = {}\n    for row in reading.delimited(root / \"class_rate_register.csv\"):\n        if row[\"state\"] != \"in_force\" or int(row[\"effective_round\"]) > index:\n            continue\n        held = multipliers.get(row[\"class\"])\n        if held is None or int(row[\"effective_round\"]) >= held[0]:\n            multipliers[row[\"class\"]] = (int(row[\"effective_round\"]),\n                                         int(row[\"multiplier_bp\"]))\n\n    licences = {}\n    for row in reading.delimited(root / \"licence_validity_register.csv\"):\n        licences[row[\"licence_code\"]] = row\n\n    precincts = [node[\"code\"] for node\n                 in reading.xml_nodes(root / \"yard_topology.xml\", \"precinct\")]\n    return {\"header\": header, \"round_index\": index,\n            \"round_key\": header[\"round_key\"],\n            \"shift_minutes\": shifts, \"pool_weights\": weights,\n            \"deferral_rate\": rates, \"retention\": retention,\n            \"ceiling\": ceiling,\n            \"class_bp\": {k: v[1] for k, v in multipliers.items()},\n            \"licences\": licences, \"precincts\": precincts}\n\n\ndef crosswalk(root):\n    out = {}\n    for row in reading.delimited(root / \"identifier_crosswalk.tsv\", reading.TAB):\n        if row[\"status\"] == \"active\":\n            out[row[\"legacy_id\"]] = row[\"canonical_id\"]\n    return out\n\n\ndef register(root, params, alias):\n    \"\"\"Stage p01. The rows in force out of the register the header names.\"\"\"\n    index = params[\"round_index\"]\n    held = {}\n    source = params[\"header\"][\"register_in_force\"]\n    for row in reading.delimited(root / source):\n        name = alias.get(row[\"job_id\"], row[\"job_id\"])\n        if row[\"state\"] not in (\"sealed\", \"withdrawn\"):\n            continue\n        if int(row[\"sealed_round\"]) > index:\n            continue\n        standing = held.get(name)\n        if standing is None or int(row[\"revision\"]) > int(standing[\"revision\"]):\n            held[name] = dict(row, job_id=name)\n    jobs = {}\n    aside = []\n    for name in sorted(held):\n        row = held[name]\n        if row[\"state\"] == \"withdrawn\":\n            aside.append((name, \"JOB-WITHDRAWN\", row[\"precinct\"]))\n        elif row[\"precinct\"] not in params[\"precincts\"]:\n            aside.append((name, \"JOB-NOPRECINCT\", row[\"precinct\"]))\n        else:\n            jobs[name] = row\n    drafted = set()\n    for row in reading.delimited(root / source):\n        name = alias.get(row[\"job_id\"], row[\"job_id\"])\n        if name not in held:\n            drafted.add(name)\n    for name in sorted(drafted):\n        aside.append((name, \"JOB-DRAFTONLY\", \"\"))\n    return jobs, aside\n",
    "src/slwopt/objective.py": "\"\"\"Stage p10. What one accepted set costs and how two of them are ranked.\n\nThe class multiplier reaches the base charge first. The surcharges of the\nprecinct are added next. The closure rebate is taken last, over the scaled\ncharges and the surcharges together. A charter job that is admissible, is not\nblocked and is left out of the closed set carries its deferral penalty; a job\nthat could not be taken carries none.\n\"\"\"\nfrom fractions import Fraction\n\nfrom . import normalise\n\nPOOLS = normalise.POOLS\n\n\ndef usage_of(closed, own):\n    return {pool: sum(own[name][pool] for name in closed) for pool in POOLS}\n\n\ndef within_capacity(usage, available):\n    for pool in POOLS:\n        if usage[pool] > available[pool]:\n            return False\n    return True\n\n\ndef surcharge_of(closed, rules, usage, norms):\n    total = 0\n    for rule in rules:\n        if rule[\"kind\"] == \"pair_surcharge\":\n            if rule[\"first_job\"] in closed and rule[\"second_job\"] in closed:\n                total += rule[\"amount_mills\"]\n        elif rule[\"kind\"] == \"threshold_surcharge\":\n            if usage[rule[\"pool\"]] > rule[\"threshold\"]:\n                total += rule[\"amount_mills\"] * sum(\n                    1 for name in closed\n                    if norms[name][\"class\"] == rule[\"class\"])\n    return total\n\n\ndef rebate_of(closed, rules, closures, over):\n    total = 0\n    for rule in rules:\n        if rule[\"kind\"] != \"closure_rebate\":\n            continue\n        anchor = rule[\"anchor_job\"]\n        if anchor in closed and len(closures.get(anchor, [])) >= 2:\n            total += normalise.half_up(Fraction(over * rule[\"rebate_bp\"], 10000))\n    return total\n\n\ndef weighted_of(usage, weights):\n    total = Fraction(0)\n    for pool in POOLS:\n        top, bottom = weights[pool]\n        total += Fraction(top, bottom) * usage[pool]\n    return total\n\n\ndef ranking(total, weighted, optional, closed):\n    \"\"\"The lexicographic key: charge, then weighted resource, then the count\n    of optional jobs taken, then the canonical job order.\"\"\"\n    return (total, weighted, optional, tuple(closed))\n",
    "src/slwopt/publish.py": "\"\"\"Stage p14. The twenty five documents, and the digests taken over them.\n\nEvery document is written in the shape the schema reference fixes: the header\nline, the column order, the row order, the key names and the value types. The\nmanifest is taken last, over the bytes already on disk.\n\"\"\"\nimport hashlib\nfrom fractions import Fraction\n\nfrom . import cells, graph, mutate, normalise, search\n\nNEWLINE = chr(10)\nTAB = \"\\t\"\nPOOLS = normalise.POOLS\n\nMODULES = [\"__init__\", \"__main__\", \"cache\", \"cells\", \"charge\", \"closure\",\n           \"graph\", \"mutate\", \"normalise\", \"objective\", \"publish\", \"reading\",\n           \"search\"]\n\nDOCUMENTS = [\n    \"01_identifier_canon.json\", \"02_precedence_edges.tsv\",\n    \"03_reverse_index.json\", \"04_normalised_jobs.csv\",\n    \"05_normalised_rules.csv\", \"06_feasibility_map.csv\",\n    \"07_closure_map.jsonl\", \"08_demand_vectors.csv\",\n    \"09_conflict_groups.json\", \"10_charge_contributions.csv\",\n    \"11_baseline_selection.json\", \"12_baseline_trace.jsonl\",\n    \"13_amendment_classification.csv\", \"14_invalidation_sets.jsonl\",\n    \"15_reuse_ledger.csv\", \"16_work_counters.csv\", \"17_cache_summary.json\",\n    \"18_final_selection.json\", \"19_rejected_register.csv\",\n    \"20_resource_usage.tsv\", \"21_amendment_optima.csv\",\n    \"22_defect_register.md\", \"23_verification_notes.md\",\n    \"24_run_manifest.txt\", \"25_summary.json\",\n]\n\nSET_ASIDE = [\"JOB-DRAFTONLY\", \"JOB-WITHDRAWN\", \"JOB-NOPRECINCT\", \"JOB-CYCLE\",\n             \"JOB-LICENCE\", \"JOB-OUTOFROUND\", \"JOB-CLOSUREBLOCKED\"]\nOTHER_REASONS = [\"EDG-CYCLE\", \"GRP-DOUBLEBOOKED\", \"GRP-SINGLE\",\n                 \"AMD-NOTARGET\", \"CMT-UNKNOWN\"]\n\n\ndef _lines(path, rows):\n    body = NEWLINE.join(str(row) for row in rows)\n    if not body.endswith(NEWLINE):\n        body += NEWLINE\n    path.write_bytes(body.encode(\"utf-8\"))\n\n\ndef _delimited(path, header, rows, sep):\n    out = [sep.join(str(cell) for cell in header)]\n    for row in rows:\n        out.append(sep.join(str(cell) for cell in row))\n    _lines(path, out)\n\n\ndef _json(path, obj):\n    path.write_bytes(normalise.laid_out(obj).encode(\"utf-8\"))\n\n\ndef _records(path, rows):\n    _lines(path, [normalise.tight(row) for row in rows])\n\n\ndef _selection(model):\n    out = []\n    total = 0\n    weighted = Fraction(0)\n    taken = 0\n    for precinct in model.precincts:\n        body = model.cells[cells.named(\"solve\", precinct)][\"value\"]\n        out.append({\"precinct\": precinct,\n                    \"selected\": list(body[\"selected\"]),\n                    \"closed_set\": list(body[\"closed_set\"]),\n                    \"total_mills\": body[\"total_mills\"],\n                    \"base_mills\": body[\"base_mills\"],\n                    \"surcharge_mills\": body[\"surcharge_mills\"],\n                    \"rebate_mills\": body[\"rebate_mills\"],\n                    \"penalty_mills\": body[\"penalty_mills\"],\n                    \"optional_count\": body[\"optional_count\"],\n                    \"weighted_resource\": body[\"weighted_resource\"],\n                    \"usage\": body[\"usage\"], \"available\": body[\"available\"]})\n        total += body[\"total_mills\"]\n        weighted += Fraction(body[\"weighted_resource\"])\n        taken += len(body[\"closed_set\"])\n    return {\"precincts\": out, \"total_mills\": total,\n            \"weighted_resource\": normalise.ratio(weighted),\n            \"accepted_job_count\": taken}\n\n\ndef publish(root, out):\n    model = cells.Round(root)\n    build = model.open_round()\n    params = model.params\n    names = sorted(model.jobs)\n\n    _json(out / \"01_identifier_canon.json\", {\n        \"round_key\": params[\"round_key\"],\n        \"round_index\": params[\"round_index\"],\n        \"yard\": params[\"header\"][\"yard\"],\n        \"workbook_sheet_key\": params[\"header\"][\"workbook_round_cell\"],\n        \"jobs_in_force\": len(names),\n        \"aliases_active\": len(model.alias),\n        \"set_aside_count\": len(model.aside),\n        \"precincts\": [{\"code\": precinct,\n                       \"jobs\": len(model.in_precinct(precinct))}\n                      for precinct in model.precincts]})\n\n    edges = []\n    pairs = set()\n    for requiring in sorted(model.accepted):\n        for required in model.accepted[requiring]:\n            pairs.add((requiring, required))\n    for edge_id, requiring, required, reason in model.edge_rejected:\n        edges.append([edge_id, requiring, required,\n                      model.jobs.get(requiring, {}).get(\"precinct\", \"\"),\n                      \"rejected\", reason])\n    for requiring, required in sorted(pairs):\n        edge_id = \"\"\n        for candidate in sorted(model.journal):\n            row = model.journal[candidate]\n            if (row[\"requiring_job\"] == requiring\n                    and row[\"required_job\"] == required\n                    and row[\"status\"] == \"active\" and row[\"kind\"] == \"hard\"):\n                edge_id = candidate\n                break\n        edges.append([edge_id, requiring, required,\n                      model.jobs[requiring][\"precinct\"], \"accepted\", \"\"])\n    edges.sort(key=lambda row: (row[0], row[1], row[2]))\n    _delimited(out / \"02_precedence_edges.tsv\",\n               [\"edge_id\", \"requiring_job\", \"required_job\", \"precinct\",\n                \"state\", \"reason\"], edges, TAB)\n\n    _json(out / \"03_reverse_index.json\", graph.reverse(model.accepted))\n\n    normalised = []\n    feasibility = []\n    closures = []\n    demands = []\n    charges = []\n    for name in names:\n        held = model.cells[cells.named(\"norm\", name)][\"value\"]\n        shut = model.cells[cells.named(\"closure\", name)][\"value\"]\n        draw = model.cells[cells.named(\"demand\", name)][\"value\"]\n        cost = model.cells[cells.named(\"charge\", name)][\"value\"]\n        normalised.append([name, held[\"precinct\"], held[\"class\"],\n                           held[\"standing\"], held[\"base_charge_mills\"],\n                           held[\"crew_minutes\"], held[\"berth_quarter_days\"],\n                           held[\"crane_lifts\"], held[\"deferral_weight\"],\n                           \"yes\" if held[\"admissible\"] else \"no\",\n                           held[\"admission_reason\"]])\n        feasibility.append([name, held[\"precinct\"],\n                            \"yes\" if held[\"admissible\"] else \"no\",\n                            \"yes\" if shut[\"blocked\"] else \"no\", shut[\"reason\"],\n                            \"no\" if shut[\"blocked\"] else \"yes\"])\n        closures.append({\"job_id\": name, \"precinct\": held[\"precinct\"],\n                         \"closure\": shut[\"closure\"],\n                         \"closure_size\": len(shut[\"closure\"]),\n                         \"blocked\": shut[\"blocked\"], \"reason\": shut[\"reason\"]})\n        demands.append([name, held[\"precinct\"]]\n                       + [draw[\"own\"][pool] for pool in POOLS]\n                       + [draw[\"closed\"][pool] for pool in POOLS])\n        charges.append([name, held[\"precinct\"], held[\"class\"],\n                        cost[\"multiplier_bp\"], held[\"base_charge_mills\"],\n                        cost[\"scaled_charge_mills\"], held[\"deferral_weight\"],\n                        cost[\"deferral_penalty_mills\"],\n                        \"yes\" if cost[\"implausible\"] else \"no\"])\n    _delimited(out / \"04_normalised_jobs.csv\",\n               [\"job_id\", \"precinct\", \"class\", \"standing\", \"base_charge_mills\",\n                \"crew_minutes\", \"berth_quarter_days\", \"crane_lifts\",\n                \"deferral_weight\", \"admissible\", \"admission_reason\"],\n               normalised, \",\")\n    _delimited(out / \"06_feasibility_map.csv\",\n               [\"job_id\", \"precinct\", \"admissible\", \"blocked\", \"reason\",\n                \"selectable\"], feasibility, \",\")\n    _records(out / \"07_closure_map.jsonl\", closures)\n    _delimited(out / \"08_demand_vectors.csv\",\n               [\"job_id\", \"precinct\"] + [\"own_\" + pool for pool in POOLS]\n               + [\"closed_\" + pool for pool in POOLS], demands, \",\")\n    _delimited(out / \"10_charge_contributions.csv\",\n               [\"job_id\", \"precinct\", \"class\", \"multiplier_bp\",\n                \"base_charge_mills\", \"scaled_charge_mills\", \"deferral_weight\",\n                \"deferral_penalty_mills\", \"implausible\"], charges, \",\")\n\n    rules = []\n    for rule_id in sorted(model.rules):\n        held = model.cells[cells.named(\"rule\", rule_id)][\"value\"]\n        rules.append([rule_id, held[\"precinct\"], held[\"kind\"],\n                      held.get(\"first_job\", held.get(\"anchor_job\", \"\")),\n                      held.get(\"second_job\", \"\"), held.get(\"pool\", \"\"),\n                      held.get(\"threshold\", \"\"), held.get(\"class\", \"\"),\n                      held.get(\"amount_mills\", \"\"), held.get(\"rebate_bp\", \"\")])\n    _delimited(out / \"05_normalised_rules.csv\",\n               [\"rule_id\", \"precinct\", \"kind\", \"subject_a\", \"subject_b\",\n                \"pool\", \"threshold\", \"class\", \"amount_mills\", \"rebate_bp\"],\n               rules, \",\")\n\n    _json(out / \"09_conflict_groups.json\", {\n        \"groups\": [dict(model.cells[cells.named(\"group\", group_id)][\"value\"])\n                   for group_id in sorted(model.groups)],\n        \"rejected_memberships\": [{\"group_id\": group_id, \"member_job\": member,\n                                  \"reason\": reason}\n                                 for group_id, member, reason\n                                 in model.group_rejected]})\n\n    baseline = _selection(model)\n    _json(out / \"11_baseline_selection.json\", baseline)\n    trace = []\n    for precinct in model.precincts:\n        body = model.cells[cells.named(\"solve\", precinct)][\"value\"]\n        trace.append({\"precinct\": precinct,\n                      \"selectable_count\": len(body[\"selectable\"]),\n                      \"subsets_examined\": body[\"subsets_examined\"],\n                      \"subsets_group_rejected\": body[\"subsets_group_rejected\"],\n                      \"subsets_capacity_rejected\":\n                          body[\"subsets_capacity_rejected\"],\n                      \"subsets_feasible\": body[\"subsets_feasible\"],\n                      \"base_mills\": body[\"base_mills\"],\n                      \"surcharge_mills\": body[\"surcharge_mills\"],\n                      \"rebate_mills\": body[\"rebate_mills\"],\n                      \"penalty_mills\": body[\"penalty_mills\"],\n                      \"total_mills\": body[\"total_mills\"]})\n    _records(out / \"12_baseline_trace.jsonl\", trace)\n\n    store = model.store\n    stages = [{\"stage\": \"build\", \"sequence\": 0, \"amendment_id\": \"\",\n               \"counters\": build,\n               \"cache\": {\"hits\": store.hits, \"misses\": store.misses,\n                         \"evictions\": store.evictions}}]\n    records = []\n    optima = []\n    standing = {precinct: model.cells[cells.named(\"solve\", precinct)][\"digest\"]\n                for precinct in model.precincts}\n    marks = (store.hits, store.misses, store.evictions)\n    for amendment in mutate.lodged(root):\n        record = mutate.fold(model, amendment)\n        now = (store.hits, store.misses, store.evictions)\n        record[\"cache\"] = {\"hits\": now[0] - marks[0],\n                           \"misses\": now[1] - marks[1],\n                           \"evictions\": now[2] - marks[2]}\n        marks = now\n        records.append(record)\n        stages.append({\"stage\": \"amendment\", \"sequence\": record[\"sequence\"],\n                       \"amendment_id\": record[\"amendment_id\"],\n                       \"counters\": record[\"counters\"],\n                       \"cache\": record[\"cache\"]})\n        for precinct in model.precincts:\n            body = model.cells[cells.named(\"solve\", precinct)][\"value\"]\n            digest = model.cells[cells.named(\"solve\", precinct)][\"digest\"]\n            optima.append([record[\"sequence\"], record[\"amendment_id\"], precinct,\n                           body[\"total_mills\"], body[\"weighted_resource\"],\n                           len(body[\"closed_set\"]),\n                           \"yes\" if digest != standing[precinct] else \"no\"])\n            standing[precinct] = digest\n\n    _delimited(out / \"13_amendment_classification.csv\",\n               [\"sequence\", \"amendment_id\", \"lodged_kind\", \"applied_kind\",\n                \"classification\", \"reason\", \"seed_count\", \"seed_cells\"],\n               [[r[\"sequence\"], r[\"amendment_id\"], r[\"lodged_kind\"],\n                 r[\"applied_kind\"], r[\"classification\"], r[\"reason\"],\n                 len(r[\"seed_cells\"]), \";\".join(r[\"seed_cells\"])]\n                for r in records], \",\")\n    _records(out / \"14_invalidation_sets.jsonl\",\n             [{\"sequence\": r[\"sequence\"], \"amendment_id\": r[\"amendment_id\"],\n               \"seed_cells\": r[\"seed_cells\"], \"invalidated\": r[\"invalidated\"],\n               \"revalidated\": r[\"revalidated\"],\n               \"invalidated_count\": len(r[\"invalidated\"]),\n               \"revalidated_count\": len(r[\"revalidated\"])} for r in records])\n\n    totals = model.layer_totals()\n    ledger = []\n    for stage in stages:\n        for layer in cells.LAYERS:\n            visited = stage[\"counters\"][\"visited\"][layer]\n            ledger.append([stage[\"sequence\"], stage[\"amendment_id\"], layer,\n                           visited, stage[\"counters\"][\"recomputed\"][layer],\n                           stage[\"counters\"][\"revalidated\"][layer],\n                           totals[layer] - visited])\n    _delimited(out / \"15_reuse_ledger.csv\",\n               [\"sequence\", \"amendment_id\", \"layer\", \"visited\", \"recomputed\",\n                \"revalidated\", \"reused\"], ledger, \",\")\n\n    counted = []\n    for stage in stages:\n        visited = sum(stage[\"counters\"][\"visited\"].values())\n        counted.append([stage[\"stage\"], stage[\"sequence\"],\n                        stage[\"amendment_id\"], visited,\n                        sum(stage[\"counters\"][\"recomputed\"].values()),\n                        sum(stage[\"counters\"][\"revalidated\"].values()),\n                        sum(totals.values()) - visited,\n                        stage[\"counters\"][\"subsets_examined\"],\n                        stage[\"cache\"][\"hits\"], stage[\"cache\"][\"misses\"],\n                        stage[\"cache\"][\"evictions\"]])\n    _delimited(out / \"16_work_counters.csv\",\n               [\"stage\", \"sequence\", \"amendment_id\", \"cells_visited\",\n                \"cells_recomputed\", \"cells_revalidated\", \"cells_reused\",\n                \"subsets_examined\", \"cache_hits\", \"cache_misses\",\n                \"cache_evictions\"], counted, \",\")\n\n    _json(out / \"17_cache_summary.json\", {\n        \"retention\": store.retention,\n        \"entries_in_force\": len(store.live),\n        \"entries_retained\": len(store.retired),\n        \"hits\": store.hits, \"misses\": store.misses,\n        \"evictions\": store.evictions,\n        \"hit_ratio\": normalise.ratio_of(store.hits, store.hits + store.misses)})\n\n    final = _selection(model)\n    _json(out / \"18_final_selection.json\", final)\n\n    rejected = []\n    for name, reason, precinct in model.aside:\n        rejected.append([\"job\", name, reason, precinct])\n    for edge_id, requiring, required, reason in model.edge_rejected:\n        rejected.append([\"edge\", edge_id, reason, requiring + \">\" + required])\n    for group_id, member, reason in model.group_rejected:\n        rejected.append([\"group_membership\", group_id, reason, member])\n    for record in records:\n        if record[\"classification\"] == \"rejected\":\n            rejected.append([\"amendment\", record[\"amendment_id\"],\n                             record[\"reason\"], record[\"lodged_kind\"]])\n    rejected.sort(key=lambda row: (row[0], row[1], row[2], row[3]))\n    _delimited(out / \"19_rejected_register.csv\",\n               [\"scope\", \"identifier\", \"reason\", \"detail\"], rejected, \",\")\n\n    usage = []\n    for body in final[\"precincts\"]:\n        for pool in POOLS:\n            top, bottom = params[\"pool_weights\"][pool]\n            carried = sum(entry[\"quantity\"] for entry in model.carryover.values()\n                          if entry[\"precinct\"] == body[\"precinct\"]\n                          and entry[\"pool\"] == pool)\n            usage.append([body[\"precinct\"], pool,\n                          model.capacity[(body[\"precinct\"], pool)], carried,\n                          body[\"available\"][pool], body[\"usage\"][pool],\n                          body[\"available\"][pool] - body[\"usage\"][pool],\n                          top, bottom,\n                          normalise.ratio(Fraction(top, bottom)\n                                          * body[\"usage\"][pool])])\n    _delimited(out / \"20_resource_usage.tsv\",\n               [\"precinct\", \"pool\", \"capacity\", \"carried\", \"available\",\n                \"usage\", \"headroom\", \"weight_numerator\", \"weight_denominator\",\n                \"weighted_usage\"], usage, TAB)\n\n    _delimited(out / \"21_amendment_optima.csv\",\n               [\"sequence\", \"amendment_id\", \"precinct\", \"total_mills\",\n                \"weighted_resource\", \"accepted_job_count\", \"optimum_moved\"],\n               optima, \",\")\n\n    catalogue = []\n    for row in graph.reading.delimited(root / \"amendment_reason_catalogue.psv\",\n                                       graph.reading.PIPE):\n        code = row[\"reason_code\"].strip()\n        if code in SET_ASIDE or code in graph.REJECTIONS or code in OTHER_REASONS:\n            catalogue.append((row[\"stage\"].strip(), code, row[\"label\"].strip()))\n    register = [\"# Defect register\", \"\", \"| stage | reason code | label |\",\n                \"| --- | --- | --- |\"]\n    for stage, code, label in sorted(set(catalogue)):\n        register.append(\"| \" + stage + \" | \" + code + \" | \" + label + \" |\")\n    register.append(\"\")\n    register.append(\"Modules in force: \" + \", \".join(MODULES))\n    _lines(out / \"22_defect_register.md\", register)\n\n    moved = sum(1 for row in optima if row[6] == \"yes\")\n    inert = sum(1 for r in records if r[\"classification\"] == \"inert\")\n    _lines(out / \"23_verification_notes.md\", [\n        \"# Verification notes\", \"\",\n        \"round \" + params[\"round_key\"],\n        \"round index \" + str(params[\"round_index\"]),\n        \"workbook sheet key \" + str(params[\"header\"][\"workbook_round_cell\"]),\n        \"jobs in force \" + str(len(names)),\n        \"jobs set aside \" + str(len(model.aside)),\n        \"edges accepted \" + str(len(pairs)),\n        \"edges rejected \" + str(len(model.edge_rejected)),\n        \"amendments applied \" + str(len(records)),\n        \"amendments classified inert \" + str(inert),\n        \"precinct optima moved \" + str(moved),\n        \"cells in the model \" + str(sum(totals.values())),\n        \"cells recomputed after the build \"\n        + str(sum(sum(s[\"counters\"][\"recomputed\"].values())\n                  for s in stages[1:])),\n        \"store retention \" + str(store.retention),\n        \"store evictions \" + str(store.evictions),\n        \"baseline total mills \" + str(baseline[\"total_mills\"]),\n        \"final total mills \" + str(final[\"total_mills\"]),\n        \"\"])\n\n    _json(out / \"25_summary.json\", {\n        \"round_key\": params[\"round_key\"],\n        \"round_index\": params[\"round_index\"],\n        \"package\": \"slwopt\",\n        \"modules\": MODULES,\n        \"control_totals\": {\n            \"jobs_in_force\": len(names),\n            \"jobs_set_aside\": len(model.aside),\n            \"edges_accepted\": len(pairs),\n            \"edges_rejected\": len(model.edge_rejected),\n            \"groups_open\": len(model.groups),\n            \"amendments_applied\": len(records),\n            \"baseline_total_mills\": baseline[\"total_mills\"],\n            \"final_total_mills\": final[\"total_mills\"],\n            \"baseline_accepted_jobs\": baseline[\"accepted_job_count\"],\n            \"final_accepted_jobs\": final[\"accepted_job_count\"],\n            \"cells_in_model\": sum(totals.values()),\n            \"cells_recomputed_after_build\":\n                sum(sum(s[\"counters\"][\"recomputed\"].values())\n                    for s in stages[1:]),\n            \"subsets_examined_after_build\":\n                sum(s[\"counters\"][\"subsets_examined\"] for s in stages[1:]),\n            \"cache_hits\": store.hits,\n            \"cache_evictions\": store.evictions},\n        \"final_weighted_resource\": final[\"weighted_resource\"]})\n\n    manifest = []\n    for name in DOCUMENTS:\n        if name == \"24_run_manifest.txt\":\n            continue\n        manifest.append(name + \" \" + normalise.digest_of_file(out / name))\n    body = NEWLINE.join(manifest) + NEWLINE\n    manifest.append(\"publication \"\n                    + hashlib.sha256(body.encode(\"utf-8\")).hexdigest())\n    _lines(out / \"24_run_manifest.txt\", manifest)\n    return out\n",
    "src/slwopt/reading.py": "\"\"\"Readers for every shape the working papers come in.\n\nNothing here interprets a paper. Each function hands back rows, records or\nlines exactly as the file holds them, and the stages above decide what they\nmean.\n\"\"\"\nimport json\nimport sqlite3\nimport xml.etree.ElementTree as ET\nimport zipfile\nfrom pathlib import Path\n\nTAB = \"\\t\"\nPIPE = \"|\"\nWORD_NS = \"{http://schemas.openxmlformats.org/wordprocessingml/2006/main}\"\n\n\ndef text_lines(path):\n    return Path(path).read_text(encoding=\"utf-8\").splitlines()\n\n\ndef delimited(path, sep=\",\"):\n    \"\"\"Rows of a delimited file as dictionaries keyed by the header line.\"\"\"\n    rows = [line for line in text_lines(path) if line.strip() != \"\"]\n    if not rows:\n        return []\n    header = rows[0].split(sep)\n    return [dict(zip(header, line.split(sep))) for line in rows[1:]]\n\n\ndef records(path):\n    \"\"\"One json object per line.\"\"\"\n    out = []\n    for line in text_lines(path):\n        if line.strip():\n            out.append(json.loads(line))\n    return out\n\n\ndef document(path):\n    return json.loads(Path(path).read_text(encoding=\"utf-8\"))\n\n\ndef xml_nodes(path, tag):\n    root = ET.parse(str(path)).getroot()\n    return [dict(node.attrib) for node in root.iter(tag)]\n\n\ndef table(path, name):\n    connection = sqlite3.connect(str(path))\n    try:\n        cursor = connection.cursor()\n        cursor.execute(\"SELECT * FROM \" + name)\n        columns = [c[0] for c in cursor.description]\n        return [dict(zip(columns, row)) for row in cursor.fetchall()]\n    finally:\n        connection.close()\n\n\ndef _column(reference):\n    index = 0\n    for ch in reference:\n        if not ch.isalpha():\n            break\n        index = index * 26 + (ord(ch.upper()) - 64)\n    return index\n\n\ndef sheets(path):\n    \"\"\"Every sheet of a workbook as a mapping of name to row lists.\"\"\"\n    with zipfile.ZipFile(path) as archive:\n        pool = []\n        if \"xl/sharedStrings.xml\" in archive.namelist():\n            root = ET.fromstring(archive.read(\"xl/sharedStrings.xml\"))\n            for item in root:\n                pool.append(\"\".join(node.text or \"\" for node in item.iter()\n                                    if node.tag.endswith(\"}t\")))\n        book = ET.fromstring(archive.read(\"xl/workbook.xml\"))\n        names = [node.attrib.get(\"name\") for node in book.iter()\n                 if node.tag.endswith(\"}sheet\")]\n        out = {}\n        for position, name in enumerate(names, start=1):\n            member = \"xl/worksheets/sheet\" + str(position) + \".xml\"\n            if member not in archive.namelist():\n                continue\n            grid = ET.fromstring(archive.read(member))\n            rows = []\n            for row in grid.iter():\n                if not row.tag.endswith(\"}row\"):\n                    continue\n                cells = {}\n                width = 0\n                for cell in row:\n                    if not cell.tag.endswith(\"}c\"):\n                        continue\n                    index = _column(cell.attrib.get(\"r\", \"A1\"))\n                    held = \"\"\n                    for value in cell:\n                        if value.tag.endswith(\"}v\"):\n                            held = value.text or \"\"\n                    if cell.attrib.get(\"t\") == \"s\" and held != \"\":\n                        held = pool[int(held)]\n                    cells[index] = held\n                    width = max(width, index)\n                rows.append([cells.get(i, \"\") for i in range(1, width + 1)])\n            out[name] = rows\n        return out\n\n\ndef pdf_lines(path):\n    \"\"\"The text lines of a board minute.\"\"\"\n    raw = Path(path).read_bytes()\n    out = []\n    depth = 0\n    held = []\n    escaped = False\n    for position in range(len(raw)):\n        ch = raw[position:position + 1]\n        if depth == 0:\n            if ch == b\"(\":\n                depth = 1\n                held = []\n            continue\n        if escaped:\n            held.append(ch)\n            escaped = False\n        elif ch == b\"\\\\\":\n            escaped = True\n        elif ch == b\"(\":\n            depth += 1\n            held.append(ch)\n        elif ch == b\")\":\n            depth -= 1\n            if depth == 0:\n                out.append(b\"\".join(held).decode(\"latin-1\"))\n            else:\n                held.append(ch)\n        else:\n            held.append(ch)\n    return out\n\n\ndef docx_blocks(path):\n    \"\"\"Paragraphs and table rows of a directive, in document order.\"\"\"\n    with zipfile.ZipFile(path) as archive:\n        root = ET.fromstring(archive.read(\"word/document.xml\"))\n    body = None\n    for node in root:\n        if node.tag == WORD_NS + \"body\":\n            body = node\n    out = []\n    if body is None:\n        return out\n    for node in body:\n        if node.tag == WORD_NS + \"p\":\n            out.append(\"\".join(t.text or \"\" for t in node.iter(WORD_NS + \"t\")))\n        elif node.tag == WORD_NS + \"tbl\":\n            for row in node.findall(WORD_NS + \"tr\"):\n                out.append([\"\".join(t.text or \"\" for t in cell.iter(WORD_NS + \"t\"))\n                            for cell in row.findall(WORD_NS + \"tc\")])\n    return out\n",
    "src/slwopt/search.py": "\"\"\"Stages p09 and p11. The exact optimum of one precinct.\n\nEvery subset of the selectable jobs is examined in ascending mask order. A\nsubset is opened into its closed set, tested against the binding slot groups\nand against the pool capacities, charged, and ranked. The lexicographic least\nis kept.\n\"\"\"\nfrom . import normalise, objective\n\nPOOLS = normalise.POOLS\n\n\ndef available_of(model, precinct):\n    out = {}\n    for pool in POOLS:\n        carried = sum(entry[\"quantity\"] for entry in model.carryover.values()\n                      if entry[\"precinct\"] == precinct and entry[\"pool\"] == pool)\n        out[pool] = model.capacity.get((precinct, pool), 0) - carried\n    return out\n\n\ndef solve_inputs(model, precinct, seen):\n    names = model.in_precinct(precinct)\n    groups = [g for g in sorted(model.groups)\n              if model.groups[g][\"precinct\"] == precinct]\n    rules = [r for r in sorted(model.rules)\n             if model.rules[r][\"precinct\"] == precinct]\n    available = available_of(model, precinct)\n    return [[[pool, available[pool]] for pool in POOLS],\n            [[seen[\"closure|\" + n][\"digest\"], seen[\"demand|\" + n][\"digest\"],\n              seen[\"charge|\" + n][\"digest\"]] for n in names],\n            [seen[\"group|\" + g][\"digest\"] for g in groups],\n            [seen[\"rule|\" + r][\"digest\"] for r in rules],\n            [[pool, model.params[\"pool_weights\"][pool][0],\n              model.params[\"pool_weights\"][pool][1]] for pool in POOLS]]\n\n\ndef sweep(model, precinct, seen):\n    names = model.in_precinct(precinct)\n    norms = {n: seen[\"norm|\" + n][\"value\"] for n in names}\n    closures = {n: seen[\"closure|\" + n][\"value\"][\"closure\"] for n in names}\n    blocked = {n: seen[\"closure|\" + n][\"value\"][\"blocked\"] for n in names}\n    own = {n: seen[\"demand|\" + n][\"value\"][\"own\"] for n in names}\n    charges = {n: seen[\"charge|\" + n][\"value\"] for n in names}\n    selectable = [n for n in names if not blocked[n]]\n    groups = [seen[\"group|\" + g][\"value\"] for g in sorted(model.groups)\n              if model.groups[g][\"precinct\"] == precinct]\n    binding = [g[\"members\"] for g in groups if g[\"binding\"]]\n    rules = [seen[\"rule|\" + r][\"value\"] for r in sorted(model.rules)\n             if model.rules[r][\"precinct\"] == precinct]\n    available = available_of(model, precinct)\n    weights = model.params[\"pool_weights\"]\n    charter = [n for n in selectable if norms[n][\"standing\"] == \"charter\"]\n\n    examined = 0\n    by_group = 0\n    by_capacity = 0\n    feasible = 0\n    best = None\n    body = None\n    width = len(selectable)\n    for mask in range(1 << width):\n        examined += 1\n        chosen = [selectable[i] for i in range(width) if mask >> i & 1]\n        opened = set(chosen)\n        for name in chosen:\n            opened.update(closures[name])\n        closed = sorted(opened)\n        clash = False\n        for members in binding:\n            if len(set(members) & set(closed)) > 1:\n                clash = True\n                break\n        if clash:\n            by_group += 1\n            continue\n        usage = objective.usage_of(closed, own)\n        if not objective.within_capacity(usage, available):\n            by_capacity += 1\n            continue\n        feasible += 1\n        base = sum(charges[name][\"scaled_charge_mills\"] for name in closed)\n        surcharge = objective.surcharge_of(closed, rules, usage, norms)\n        rebate = objective.rebate_of(closed, rules, closures, base + surcharge)\n        penalty = sum(charges[name][\"deferral_penalty_mills\"]\n                      for name in charter if name not in closed)\n        total = base + surcharge - rebate + penalty\n        weighted = objective.weighted_of(usage, weights)\n        optional = sum(1 for name in closed\n                       if norms[name][\"standing\"] == \"optional\")\n        key = objective.ranking(total, weighted, optional, closed)\n        if best is None or key < best:\n            best = key\n            body = {\"selected\": list(chosen), \"closed_set\": closed,\n                    \"usage\": usage, \"base_mills\": base,\n                    \"surcharge_mills\": surcharge, \"rebate_mills\": rebate,\n                    \"penalty_mills\": penalty, \"total_mills\": total,\n                    \"optional_count\": optional,\n                    \"weighted_resource\": normalise.ratio(weighted)}\n    if body is None:\n        raise SystemExit(\"precinct \" + precinct + \" admits no feasible set\")\n    return {\"precinct\": precinct, \"selectable\": selectable,\n            \"subsets_examined\": examined, \"subsets_group_rejected\": by_group,\n            \"subsets_capacity_rejected\": by_capacity,\n            \"subsets_feasible\": feasible, \"available\": available, **body}\n",
    "tests/test_visible.py": "\"\"\"The suite the yard runs before it accepts a build of the engine.\n\nIt covers the parts of the engine the desk has never had trouble with: the\narithmetic, the amount grammar, the working store and the command line. It\nsays nothing about the derivation, which is why it passes on a build whose\nfigures are wrong.\n\"\"\"\nimport unittest\nfrom fractions import Fraction\n\nfrom slwopt import cache, graph, normalise, objective\nfrom slwopt.__main__ import parse\n\n\nclass Arithmetic(unittest.TestCase):\n\n    def test_half_away_from_zero(self):\n        self.assertEqual(normalise.half_up(Fraction(5, 2)), 3)\n        self.assertEqual(normalise.half_up(Fraction(-5, 2)), -3)\n        self.assertEqual(normalise.half_up(Fraction(7, 3)), 2)\n        self.assertEqual(normalise.half_up(Fraction(4, 1)), 4)\n\n    def test_ratio_carries_twelve_places(self):\n        self.assertEqual(normalise.ratio(Fraction(1, 4)), \"0.250000000000\")\n        self.assertEqual(normalise.ratio(0), \"0.000000000000\")\n        self.assertEqual(normalise.ratio_of(3, 0), \"0.000000000000\")\n\n    def test_ratio_publishes_no_negative_zero(self):\n        self.assertEqual(normalise.ratio(Fraction(-1, 10 ** 16)),\n                         \"0.000000000000\")\n\n\nclass Amounts(unittest.TestCase):\n\n    def test_forms_of_one_amount_agree(self):\n        self.assertEqual(normalise.amount(\"4800\"), 4800)\n        self.assertEqual(normalise.amount(\"4,800 mills\"), 4800)\n        self.assertEqual(normalise.amount(\"4.800 GBP\"), 4800)\n        self.assertEqual(normalise.amount(\"4 GBP\"), 4000)\n\n    def test_an_empty_amount_is_nothing(self):\n        self.assertEqual(normalise.amount(\"\"), 0)\n\n    def test_a_fraction_of_a_mill_is_refused(self):\n        with self.assertRaises(ValueError):\n            normalise.amount(\"12.5\")\n\n\nclass WorkingStore(unittest.TestCase):\n\n    def test_a_key_already_held_is_a_hit(self):\n        store = cache.Store(4)\n        store.put(\"norm|A\", \"k1\", {\"v\": 1}, \"d1\")\n        self.assertEqual(store.take(\"norm|A\", \"k1\")[1], \"d1\")\n        self.assertEqual(store.hits, 1)\n        self.assertEqual(store.misses, 0)\n\n    def test_a_superseded_key_comes_back(self):\n        store = cache.Store(4)\n        store.put(\"norm|A\", \"k1\", {\"v\": 1}, \"d1\")\n        store.put(\"norm|A\", \"k2\", {\"v\": 2}, \"d2\")\n        self.assertEqual(store.take(\"norm|A\", \"k1\")[1], \"d1\")\n\n    def test_the_retained_count_is_held(self):\n        store = cache.Store(2)\n        for step in range(6):\n            store.put(\"norm|A\", \"k\" + str(step), {\"v\": step}, \"d\" + str(step))\n        self.assertLessEqual(len(store.retired), 2)\n        self.assertEqual(store.evictions, 3)\n\n\nclass Graph(unittest.TestCase):\n\n    def test_depth_counts_the_longest_chain(self):\n        accepted = {\"c\": [\"b\"], \"b\": [\"a\"]}\n        depth = graph.depths(accepted, [\"a\", \"b\", \"c\"])\n        self.assertEqual([depth[\"a\"], depth[\"b\"], depth[\"c\"]], [0, 1, 2])\n\n    def test_a_prerequisite_is_found_through_the_chain(self):\n        accepted = {\"c\": [\"b\"], \"b\": [\"a\"]}\n        self.assertTrue(graph.stands_behind(accepted, \"c\", \"a\"))\n        self.assertFalse(graph.stands_behind(accepted, \"a\", \"c\"))\n\n    def test_the_reverse_index_turns_the_edges_around(self):\n        self.assertEqual(graph.reverse({\"c\": [\"a\", \"b\"]}),\n                         {\"a\": [\"c\"], \"b\": [\"c\"]})\n\n\nclass Objective(unittest.TestCase):\n\n    def test_usage_adds_each_job_once(self):\n        own = {\"a\": {\"berth_quarter_days\": 2, \"crane_lifts\": 1,\n                     \"crew_minutes\": 60},\n               \"b\": {\"berth_quarter_days\": 3, \"crane_lifts\": 0,\n                     \"crew_minutes\": 30}}\n        usage = objective.usage_of([\"a\", \"b\"], own)\n        self.assertEqual(usage[\"berth_quarter_days\"], 5)\n        self.assertEqual(usage[\"crew_minutes\"], 90)\n\n    def test_weighting_stays_exact(self):\n        usage = {\"berth_quarter_days\": 1, \"crane_lifts\": 1, \"crew_minutes\": 1}\n        weights = {\"berth_quarter_days\": (25, 1), \"crane_lifts\": (7, 1),\n                   \"crew_minutes\": (1, 60)}\n        self.assertEqual(objective.weighted_of(usage, weights),\n                         Fraction(1921, 60))\n\n\nclass CommandLine(unittest.TestCase):\n\n    def test_the_two_options_come_in_either_order(self):\n        first = parse([\"--data\", \"papers\", \"--out\", \"here\"])\n        second = parse([\"--out\", \"here\", \"--data\", \"papers\"])\n        self.assertEqual(str(first[0]), str(second[0]))\n        self.assertEqual(str(first[1]), str(second[1]))\n\n    def test_a_missing_option_is_refused(self):\n        with self.assertRaises(SystemExit):\n            parse([\"--data\", \"papers\"])\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n",
}


# --------------------------------------------------------------------------
# the defects the shipped engine carries
#
# One entry per catalogued defect: the code, the module it sits in, the block
# the repaired engine holds, and the block the shipped engine holds instead.
# --------------------------------------------------------------------------
DEFECTS = (
    ("DFC-01", "src/slwopt/cells.py",
     "            for other in sorted(graph.readers_of(self.accepted, name,\n                                                 self.jobs, precinct)):\n                out.append(named(\"demand\", other))\n",
     "            out.append(named(\"demand\", name))\n"),
    ("DFC-02", "src/slwopt/search.py",
     "            [seen[\"rule|\" + r][\"digest\"] for r in rules],\n",
     "            [],\n"),
    ("DFC-03", "src/slwopt/cells.py",
     "            trail[-1] = (marker, \"revalidated\")\n            return False\n",
     "            trail[-1] = (marker, \"revalidated\")\n            return True\n"),
    ("DFC-04", "src/slwopt/charge.py",
     "    return [{field: job[field] for field in REGISTER_FIELDS},\n",
     "    held = dict(model.meta.get(name, {}))\n    held.update({field: job[field] for field in REGISTER_FIELDS})\n    return [held,\n"),
    ("DFC-05", "src/slwopt/mutate.py",
     "    if kind == \"job_note_revision\":\n        return []\n",
     "    if kind == \"job_note_revision\":\n        return [cells.named(\"norm\", payload[\"job_id\"])]\n"),
    ("DFC-06", "src/slwopt/mutate.py",
     "    if kind in (\"capacity_revision\", \"carryover_revision\"):\n        return [cells.named(\"solve\", payload[\"precinct\"])]\n",
     "    if kind == \"capacity_revision\":\n        return [cells.named(\"closure\", name) for name in sorted(model.jobs)\n                if model.jobs[name][\"precinct\"] == payload[\"precinct\"]] + [\n                    cells.named(\"solve\", payload[\"precinct\"])]\n    if kind == \"carryover_revision\":\n        return [cells.named(\"solve\", payload[\"precinct\"])]\n"),
    ("DFC-07", "src/slwopt/mutate.py",
     "    if kind in (\"edge_lodged\", \"edge_withdrawn\"):\n        return [cells.named(\"closure\", payload[\"requiring_job\"])]\n",
     "    if kind == \"edge_withdrawn\":\n        return []\n    if kind == \"edge_lodged\":\n        return [cells.named(\"closure\", payload[\"requiring_job\"])]\n"),
    ("DFC-08", "src/slwopt/objective.py",
     "    return (total, weighted, optional, tuple(closed))\n",
     "    return (total,)\n"),
    ("DFC-09", "src/slwopt/objective.py",
     "        if usage[pool] > available[pool]:\n",
     "        if usage[pool] >= available[pool]:\n"),
    ("DFC-10", "src/slwopt/normalise.py",
     "        elif section == \"precinct_shift_minutes\" and head.startswith(\"PCT-\"):\n            shifts[head] = int(row[1])\n",
     "        elif section == \"precinct_shift_minutes\" and head.startswith(\"PCT-\"):\n            shifts[head] = 480\n"),
    ("DFC-11", "src/slwopt/normalise.py",
     "        elif section == \"pool_weights\" and head in POOLS:\n            weights[head] = (int(row[1]), int(row[2]))\n",
     "        elif section == \"pool_weights\" and head in POOLS:\n            weights[head] = (1, 1)\n"),
    ("DFC-12", "src/slwopt/search.py",
     "        rebate = objective.rebate_of(closed, rules, closures, base + surcharge)\n",
     "        rebate = objective.rebate_of(closed, rules, closures, base)\n"),
    ("DFC-13", "src/slwopt/search.py",
     "        penalty = sum(charges[name][\"deferral_penalty_mills\"]\n                      for name in charter if name not in closed)\n",
     "        penalty = sum(charges[name][\"deferral_penalty_mills\"]\n                      for name in names if name not in closed)\n"),
    ("DFC-14", "src/slwopt/normalise.py",
     "        if \"IN FORCE FOR ROUND\" in line:\n            holding = True\n            continue\n        if line.startswith(\"APPENDIX\"):\n            holding = False\n",
     "        if \"RESCINDED IN FULL\" in line:\n            holding = True\n            continue\n        if line.startswith(\"APPENDIX\") or \"IN FORCE FOR ROUND\" in line:\n            holding = False\n"),
    ("DFC-15", "src/slwopt/normalise.py",
     "    source = params[\"header\"][\"register_in_force\"]\n",
     "    source = \"berth_job_register_current.csv\"\n"),
)


def write_project(root, E):
    """Write the engine as the yard currently runs it."""
    held = dict(PACKAGE_FILES)
    for code, relative, repaired, shipped in DEFECTS:
        text = held[relative]
        if text.count(repaired) != 1:
            raise SystemExit("defect " + code + " does not match " + relative
                             + " exactly once")
        held[relative] = text.replace(repaired, shipped)
    stamp = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(Path(root) / "project.zip", "w",
                         zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(held):
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, held[name].encode("utf-8"))



WITHDRAWN_RULES = ("R_CAPACITY_SEEDS_CLOSURE", "R_COST_ONLY",
                   "R_CURRENT_REGISTER", "R_FLAT_SHIFT", "R_LEGACY_WEIGHTS",
                   "R_META_IN_KEY", "R_NO_CUTOFF", "R_PENALTY_ALL",
                   "R_REBATE_BEFORE", "R_REMOVAL_INERT", "R_RESCINDED_MEMO",
                   "R_RULE_KEY_OMITS", "R_SHALLOW_CASCADE", "R_STRICT_CAPACITY")


# --------------------------------------------------------------------------
# the working papers
#
# Everything the round is governed by is written here. The stage papers fix
# the derivation, the policy papers fix the arithmetic and the form of the
# publication, and the three papers that are not plain text carry the control
# values that stand in no other file.
# --------------------------------------------------------------------------
def _stage_papers(root, E):
    ri = E["round_index"]
    papers = {}

    papers["spec_stage_p01_identifier_and_revision.md"] = """# Stage p01  identifiers, the register in force and the parameter layer

The round opens against one register. `round_header.json` names it in
`register_in_force`. The other copy of the register is the drafting copy the
desk works on between rounds and it settles nothing, however recent its rows
look.

Inside the register in force a job may carry several rows. The row in force is
the row of the greatest revision among the rows whose `state` is `sealed` or
`withdrawn` and whose `sealed_round` is at or below the round index. A row
sealed for a later round is read by a later round and not by this one. A job
whose row in force carries the state `withdrawn` is set aside under
`JOB-WITHDRAWN`. A job with no such row at all, because every row it carries
is a draft or is sealed for a later round, is set aside under `JOB-DRAFTONLY`.
A job whose row in force names a precinct that the live yard topology does not
carry is set aside under `JOB-NOPRECINCT`. A job that is set aside takes no
part in the round and holds no derived cell.

Both ends of every identifier are put through `identifier_crosswalk.tsv`
before anything else reads them. A crosswalk row whose status is not `active`
maps nothing.

The parameter layer is assembled here. The class multipliers come from
`class_rate_register.csv`, taking for each class the row of the greatest
`effective_round` at or below the round index whose state is `in_force`. The
licence register is read whole. The precinct list comes from the live yard
topology. The shift length of each precinct and the weight of each pool come
from the parameter workbook, from the sheet whose `sheet_key` cell matches
`workbook_round_cell` in the round header. The deferral rate of each class,
the number of entries the working store retains and the charge above which a
job is reported as implausible come from the board memo, from the sitting the
memo marks as in force for this round. A sitting the memo marks as rescinded
settles nothing.
"""

    papers["spec_stage_p02_precedence_graph.md"] = """# Stage p02  the precedence graph and the indexes over it

`precedence_edge_journal.psv` holds lodgements, not prerequisites. A lodgement
becomes a prerequisite only after it has passed, in this order, every test
below. The first test a row fails is the reason it is rejected, and a rejected
row appears once in the rejection register with that reason.

`EDG-WITHDRAWN`  the row status is not `active`.
`EDG-ADVISORY`  the row kind is not `hard`. An advisory lodgement records an
  opinion and creates no prerequisite.
`EDG-SELF`  the two ends are one job after the crosswalk.
`EDG-UNKNOWNJOB`  either end is not a job in force.
`EDG-CROSSPRECINCT`  the two ends stand in different precincts. A prerequisite
  never crosses a precinct.
`EDG-DUPLICATE`  a row already accepted names the same pair after the
  crosswalk. Rows are taken in ascending edge identifier, so the row of the
  lowest identifier is the one that carries the prerequisite and every later
  row naming that pair is the duplicate.

A job that stands among its own prerequisites, at any depth, is set aside
under `JOB-CYCLE` together with every other job of that cycle, and the
lodgements that named it are then rejected under `EDG-UNKNOWNJOB` by the test
above.

Two indexes are derived here. The reverse index maps a job to the jobs that
name it directly as a prerequisite. The depth of a job is the longest chain of
prerequisites standing below it, counted in edges, and it is what puts a
prerequisite before the job that names it whenever a cascade reaches both.
"""

    papers["spec_stage_p03_normalisation.md"] = """# Stage p03  units, amounts and the normalised record

Every quantity is carried in the unit `unit_registry.toml` names, and the
register may state it in either of two units.

A crew quantity stated in shifts is multiplied by the shift length of the
precinct the job stands in. A crew quantity stated in minutes is already in
the unit. A berth quantity stated in days is multiplied by four. A berth
quantity stated in quarter days is already in the unit. A lift count is a
count. Money is whole mills throughout and a thousand mills is one pound.

An amount written by the desk is put into whole mills as follows. Thousands
separators are dropped. An amount that ends in `GBP` is read as pounds, with
up to three decimal places standing for the mills, so `4.800 GBP` is four
thousand eight hundred mills and `4 GBP` is four thousand. A fraction shorter
than three places is padded on the right to reach the mills, so `1.75 GBP` is
one thousand seven hundred and fifty mills and never one thousand and seventy
five. An amount that ends
in `mills`, or that carries no unit word at all, is already whole mills, and a
fractional part on such an amount is refused. Two amounts that reach the same
whole mills are the same amount, whatever the desk wrote.

The normalised record of a job carries its precinct, class, standing, base
charge in mills, crew minutes, berth quarter days, lift count, deferral weight
and whether it is admissible. It carries nothing of the title, the note, the
owner or the display order: those govern nothing and are the presentation
fields. The normalised record of a conditional charge rule carries its
precinct, its kind, the jobs or the pool it names, and its amount in whole
mills or its rebate in basis points. It carries nothing of the note or the
author.
"""

    papers["spec_stage_p04_admissibility.md"] = """# Stage p04  admissibility of one job

A job is admissible when both tests below pass, and the first test it fails is
the reason it is inadmissible.

`JOB-LICENCE`  the licence code the job carries stands in
`licence_validity_register.csv` with the state `valid`, and the round index
lies between `valid_from_round` and `valid_to_round` inclusive.
`JOB-OUTOFROUND`  the round index lies between `earliest_round` and
`latest_round` inclusive.

An inadmissible job stays in the round and holds its cells. It is never
selectable and, because it could not have been taken, it carries no deferral
penalty. That is what separates it from a job that was admissible and was left
out.
"""

    papers["spec_stage_p05_closure.md"] = """# Stage p05  the closure of a job

The closure of a job is every job that stands behind it through accepted
prerequisites, at any depth, the job itself left out. Taking a job takes its
whole closure with it; a closure member is never taken optionally.

A job is blocked when it is inadmissible itself, and then it carries the
reason of stage p04. A job is blocked under `JOB-CLOSUREBLOCKED` when anything
in its closure is inadmissible or has been set aside. A blocked job is never
selectable and, like an inadmissible job, carries no deferral penalty.
"""

    papers["spec_stage_p06_demand.md"] = """# Stage p06  what a job draws

Two vectors are carried for each job. The own vector is what that job draws by
itself, in the three pools of `unit_registry.toml`. The closed vector is what
the job and its whole closure draw together, counting each distinct job once.

The usage of an accepted set is taken over the closed set of that selection,
each distinct job counted once, from the own vectors. Adding the closed
vectors of the jobs selected would charge a shared prerequisite twice and is
not what the yard is billed.
"""

    papers["spec_stage_p07_charges.md"] = """# Stage p07  the charge a job carries

The scaled charge of a job is its base charge in mills multiplied by the class
multiplier in basis points and divided by ten thousand, rounded once, half
away from zero.

The deferral penalty of a job is the deferral rate of its class, in mills per
weight unit, multiplied by the deferral weight the register gives it. The
deferral rate stands in the board memo and nowhere else.

A scaled charge above the implausible charge ceiling of the board memo is
reported to the desk as implausible. The report changes no figure.
"""

    papers["spec_stage_p08_slot_groups.md"] = """# Stage p08  the exclusive slot groups

An open membership row of `exclusive_slot_groups.csv` puts a job in a group. A
job that stands in two open groups keeps the group of the lower precedence
number, and keeps the group of the lower identifier where two groups carry one
precedence number. Its membership of the other group is rejected under
`GRP-DOUBLEBOOKED`.

A group left holding two or more open members binds: at most one of its
members may stand in the closed set of an accepted selection. A group left
holding one open member, or none at all, binds nothing.

The test is over the closed set and not over the jobs selected, so a group is
breached just as surely by a prerequisite that a selection pulls in as by a
job the selection names.
"""

    papers["spec_stage_p09_capacity.md"] = """# Stage p09  the pools and what is left of them

The capacity of a pool is the row of `pool_capacity_history.tsv` for that
precinct and pool with the greatest `effective_round` at or below the round
index whose state is `in_force`. A row with a later effective round, or with
any other state, settles nothing.

The carried quantity of a pool is the sum of the binding rows of
`carried_commitment_ledger.csv` for that precinct and pool. A row that is not
binding carries nothing.

The available quantity is the capacity less the carried quantity. A selection
stands within a pool while its usage is at or below the available quantity, so
a usage equal to the available quantity is within it. The board memo carries
the resolution in force on this point.
"""

    papers["spec_stage_p10_objective.md"] = """# Stage p10  what one accepted set costs and how two are ranked

The charge of an accepted set is built in this order and no other.

The class multiplier reaches the base charge of each job first, at stage p07.
The scaled charges of the closed set are added. The surcharges of the precinct
are added next: a pair surcharge is added once when both of the jobs it names
stand in the closed set, and a threshold surcharge is added once for each job
of the class it names that stands in the closed set, but only while the usage
of the pool it names is above its threshold. The closure rebate is taken last:
where the job it hangs on stands in the closed set and that job holds two or
more jobs in its closure, the rebate in basis points is taken of the scaled
charges and the surcharges together, rounded once, half away from zero. The
precedence directive carries the order these three stages apply in.

The deferral penalties are added last of all. A job carries its penalty when
it is selectable, its standing is `charter`, and it is left out of the closed
set. A job that is inadmissible, blocked or set aside carries none, and an
optional job carries none whatever happens to it.

Two accepted sets are ranked on four keys in this order: the charge in mills,
then the weighted resource, then the count of optional jobs standing in the
closed set, then the closed set itself in canonical job order. The weighted
resource of a set is the sum over the three pools of the usage of that pool
multiplied by the weight of that pool, held as an exact rational and published
to twelve decimal places. The pool weights stand in the parameter workbook and
nowhere else. Two sets equal on all four keys are one set.
"""

    papers["spec_stage_p11_search.md"] = """# Stage p11  the exact optimum of one precinct

Every subset of the selectable jobs of a precinct is examined, in ascending
mask order, the empty subset first. The selectable jobs of a precinct are its
jobs in force that are not blocked, taken in canonical job order, and the bit
positions of the mask follow that order.

A subset is opened into its closed set, tested against the binding slot groups
of the precinct, and tested against the three pools. A subset that breaches a
group is counted against the group rejections and goes no further. A subset
that leaves a pool is counted against the capacity rejections and goes no
further. What survives is charged and ranked by stage p10, and the
lexicographically least of them is the accepted set of that precinct.

Precincts are settled one at a time and the round is their sum. A prerequisite
never crosses a precinct, a slot group never crosses a precinct, a charge rule
never crosses a precinct and a pool never crosses a precinct, so the least
total over the yard is the sum of the least total of each precinct.
"""

    papers["spec_stage_p12_provenance.md"] = """# Stage p12  what the optimum was derived from

The solve of a precinct reads the closure, the demand and the charge of every
job of that precinct, the group of every group of that precinct, the rule of
every charge rule of that precinct, the available quantity of its three pools
and the pool weights. Those are the inputs of its key and there are no others.

The baseline trace records, for each precinct, how many jobs were selectable,
how many subsets were examined, how many were turned down by a group, how many
were turned down by a pool, how many survived, and what the accepted set came
to under each head of the charge.
"""

    papers["spec_stage_p13_amendments.md"] = """# Stage p13  the amendments and the cascade

The lodged rows of `amendment_journal.jsonl`, in ascending sequence, are the
amendments of the round. A row that is not lodged is not an amendment. Where a
payload field is empty on the journal row, the field is completed from
`amendment_supplement.ndjson`, but only for the amendment and field that
`row_provenance_ledger.csv` records against the supplement with the state
`in_force`.

Each amendment is classified by its kind and seeds the cells the precedence
directive names for that kind, and no others. A `job_note_revision` moves only
presentation fields and seeds nothing at all. A `restatement` seeds what its
own kind would seed. A `reversal` names an earlier amendment and applies the
exact inverse of what that amendment did, and is classified by the kind of the
amendment it names. An amendment that names nothing the round holds, or that
would close a precedence cycle, is rejected and moves nothing.

A seeded cell is derived again. When the value it comes back with carries the
digest it already held, it is revalidated and the cascade stops there: the
cells that read it keep their values and are never visited. When the digest
moves, every cell that reads it is reached in turn, prerequisites before the
jobs that name them, and the same test is applied at each of them.

The cells one cell is read by are fixed by the precedence directive. A
mistake in either direction is a defect. Reaching too few cells leaves a stale
value standing in the publication. Reaching too many leaves the publication
right and the work ledger wrong, and the work ledger is published.
"""

    papers["spec_stage_p14_publication.md"] = """# Stage p14  the publication

The twenty five documents are written in the shape
`output_schema_reference.md` fixes, under the encoding and the line endings
`serialisation_and_digest_contract.md` fixes. The manifest is written last, of
the twenty four documents before it in the order the schema reference lists
them, each with the digest of the bytes already on disk, and then a line
carrying the digest of those lines. The run writes nothing else into the
destination and leaves the paper directory exactly as it found it.
"""
    for name, body in papers.items():
        write_text(root / name, body)


def _policy_papers(root, E):
    ri = E["round_index"]
    write_text(root / "unit_registry.toml", """# The unit each quantity is carried in.

[pools]
berth_quarter_days = "quarter days of a berth"
crane_lifts = "lifts"
crew_minutes = "minutes of crew time"

[conversions]
crew_shift_to_minutes = "the shift length of the precinct, from the workbook"
berth_day_to_quarter_days = 4
pound_to_mills = 1000

[money]
unit = "mills"
""")
    write_text(root / "rounding_and_arithmetic_policy.yaml", """# Where rounding happens and where it does not.
arithmetic:
  mode: exact_rational
  binary_floating_point: false
rounding:
  rule: half_away_from_zero
  places:
    scaled_charge: 0
    closure_rebate: 0
    weighted_resource: 12
    store_hit_ratio: 12
  applied_at:
    - stage_p07_scaled_charge
    - stage_p10_closure_rebate
    - stage_p14_weighted_resource
    - stage_p14_store_hit_ratio
publication:
  negative_zero: forbidden
  whole_quantities: integers_in_the_unit_of_the_stage
""")
    write_text(root / "revision_precedence.toml", """# Which row of a register the round takes.

[register]
in_force = "the file round_header.json names in register_in_force"
drafting_copy = "berth_job_register_current.csv"
row = "greatest revision among sealed or withdrawn rows sealed at or below the round index"

[capacity]
row = "greatest effective_round at or below the round index with state in_force"

[class_rate]
row = "greatest effective_round at or below the round index with state in_force"

[workbook]
sheet = "the sheet whose sheet_key cell matches workbook_round_cell"

[memo]
sitting = "the sitting the memo marks as in force for this round"
""")
    write_text(root / "precedence_and_order_policy.toml", """# Canonical order, used wherever a tie has to be settled.

[order]
jobs = "ascending job identifier"
edges = "ascending edge identifier"
groups = "ascending group identifier"
rules = "ascending rule identifier"
precincts = "ascending precinct code"
amendments = "ascending sequence"
subsets = "ascending mask over the selectable jobs in canonical job order"

[cells]
layers = ["norm", "rule", "closure", "demand", "charge", "group", "solve"]
visiting = "layer order, then depth for a closure cell, then cell name"

[groups]
double_booked = "lower precedence number wins, then lower group identifier"
""")
    write_text(root / "publication_form_rules.toml", """# The form of the published documents.

# The [form] table governs the delimited documents only. A json or jsonl
# document carries json types, and its booleans are the json literals.

[form]
csv_separator = ","
tsv_separator = "tab"
psv_separator = "pipe"
header_line = "required on every delimited document"
boolean_cell = ["yes", "no"]
empty_cell = "an empty string"

[json]
indent = 2
sort_keys = true
trailing_newline = true
booleans = "the json literals true and false, never the words yes and no"

[jsonl]
one_record_per_line = true
compact = true
sort_keys = true
booleans = "the json literals true and false, never the words yes and no"
""")
    write_text(root / "package_expectations.toml", """# What the delivered engine has to be.

[package]
name = "slwopt"
layout = "a src tree with the package under src/slwopt"
entry_point = "python3 -m slwopt --data DIR --out DIR"
options = "both options are accepted in either order"
standard_library_only = true
python = ">=3.12"

[modules]
required = ["__init__", "__main__", "cache", "cells", "charge", "closure",
            "graph", "mutate", "normalise", "objective", "publish", "reading",
            "search"]

[suite]
carried = "the tests directory travels with the package unchanged"

[behaviour]
reads = "only the directory the data option names"
writes = "only the directory the out option names"
determinism = "two runs over one directory produce identical bytes"
portability = "one round under another directory name produces the same bytes"
""")
    write_text(root / "engine_defaults.ini", """# Desk defaults. None of these settle a governed quantity.
[run]
verbose = false
progress_every = 25
locale = C

[desk]
contact = replan.desk
sitting_room = north office

[legacy]
scale_table = legacy_scale_table.csv
note = retired when the parameter workbook came in
""")
    roster = ["# The desks that lodge against this yard.", "",
              "[desks]"]
    for i, owner in enumerate(OWNERS):
        roster.append(owner + " = " + PRECINCT_SHAPES[i % 6][0])
    roster += ["", "[hours]"]
    for i, owner in enumerate(OWNERS):
        roster.append(owner + " = shift " + str(1 + i % 3))
    roster += ["", "[note]",
               "governs = nothing; the roster is a contact list"]
    write_lines(root / "planning_desk_roster.conf", roster)


def _schema_paper(root, E):
    body = """# Output schema reference

Twenty five documents, written in this order of identifiers. Every delimited
document carries the header line named here, in this column order, and the row
order named here. Every whole quantity is an integer in the unit its stage
names. Every ratio carries exactly twelve decimal places.

## 01_identifier_canon.json
Keys: `round_key`, `round_index`, `yard`, `workbook_sheet_key`,
`jobs_in_force`, `aliases_active`, `set_aside_count`, `precincts`.
`precincts` is a list, one object per precinct in ascending precinct code,
with keys `code` and `jobs`. `aliases_active` is the count of active crosswalk
rows.

## 02_precedence_edges.tsv
Header `edge_id`, `requiring_job`, `required_job`, `precinct`, `state`,
`reason`. One row per lodgement the journal holds that concerns the round,
accepted or rejected. The state is `accepted` or `rejected`. The reason is the
rejection code for a rejected row and empty for an accepted one. For an
accepted row the edge identifier is the lowest identifier naming that pair.
Rows ascend by edge identifier, then requiring job, then required job.

## 03_reverse_index.json
An object keyed by job identifier, each value the ascending list of jobs that
name that job directly as a prerequisite. A job that nothing names is absent.

## 04_normalised_jobs.csv
Header `job_id`, `precinct`, `class`, `standing`, `base_charge_mills`,
`crew_minutes`, `berth_quarter_days`, `crane_lifts`, `deferral_weight`,
`admissible`, `admission_reason`. One row per job in force, ascending by job
identifier. `admissible` is `yes` or `no`; `admission_reason` is empty for an
admissible job.

## 05_normalised_rules.csv
Header `rule_id`, `precinct`, `kind`, `subject_a`, `subject_b`, `pool`,
`threshold`, `class`, `amount_mills`, `rebate_bp`. One row per charge rule in
force, ascending by rule identifier. `subject_a` is the first job of a pair
surcharge or the anchor job of a closure rebate. A cell a kind does not carry
is empty.

## 06_feasibility_map.csv
Header `job_id`, `precinct`, `admissible`, `blocked`, `reason`, `selectable`.
One row per job in force, ascending by job identifier. Each of `admissible`,
`blocked` and `selectable` is `yes` or `no`.

## 07_closure_map.jsonl
One record per job in force, ascending by job identifier, keys `job_id`,
`precinct`, `closure`, `closure_size`, `blocked`, `reason`. `closure` is the
ascending list of the jobs standing behind it.

## 08_demand_vectors.csv
Header `job_id`, `precinct`, `own_berth_quarter_days`, `own_crane_lifts`,
`own_crew_minutes`, `closed_berth_quarter_days`, `closed_crane_lifts`,
`closed_crew_minutes`. One row per job in force, ascending by job identifier.

## 09_conflict_groups.json
Keys `groups` and `rejected_memberships`. `groups` is a list in ascending
group identifier with keys `group_id`, `precinct`, `precedence`, `members`,
`binding`. `rejected_memberships` is a list with keys `group_id`,
`member_job`, `reason`.

## 10_charge_contributions.csv
Header `job_id`, `precinct`, `class`, `multiplier_bp`, `base_charge_mills`,
`scaled_charge_mills`, `deferral_weight`, `deferral_penalty_mills`,
`implausible`. One row per job in force, ascending by job identifier.

## 11_baseline_selection.json
Keys `precincts`, `total_mills`, `weighted_resource`, `accepted_job_count`.
`precincts` is a list in ascending precinct code with keys `precinct`,
`selected`, `closed_set`, `total_mills`, `base_mills`, `surcharge_mills`,
`rebate_mills`, `penalty_mills`, `optional_count`, `weighted_resource`,
`usage`, `available`. `selected` is the subset the search named, in the
canonical job order of the precinct; `closed_set` is that subset opened, in
ascending job identifier. `usage` and `available` are objects keyed by pool.
`accepted_job_count` is the total size of the closed sets.

## 12_baseline_trace.jsonl
One record per precinct in ascending precinct code, keys `precinct`,
`selectable_count`, `subsets_examined`, `subsets_group_rejected`,
`subsets_capacity_rejected`, `subsets_feasible`, `base_mills`,
`surcharge_mills`, `rebate_mills`, `penalty_mills`, `total_mills`.

## 13_amendment_classification.csv
Header `sequence`, `amendment_id`, `lodged_kind`, `applied_kind`,
`classification`, `reason`, `seed_count`, `seed_cells`. One row per amendment
in ascending sequence. The classification is `governed`, `inert` or
`rejected`. The reason is empty except on a rejected amendment. `seed_cells`
is the ascending seed set joined by semicolons and is empty when nothing is
seeded. A cell is named as its layer, a vertical bar, and the job, rule, group
or precinct it stands for.

## 14_invalidation_sets.jsonl
One record per amendment in ascending sequence, keys `sequence`,
`amendment_id`, `seed_cells`, `invalidated`, `revalidated`,
`invalidated_count`, `revalidated_count`. `invalidated` is the ascending list
of the cells whose digest moved. `revalidated` is the ascending list of the
cells that were visited and came back with the digest they already held.

## 15_reuse_ledger.csv
Header `sequence`, `amendment_id`, `layer`, `visited`, `recomputed`,
`revalidated`, `reused`. Seven rows per stage, the layers in the order
`norm`, `rule`, `closure`, `demand`, `charge`, `group`, `solve`. The build is
sequence 0 with an empty amendment identifier; then one stage per amendment in
ascending sequence. `visited` counts the cells of that layer the stage
reached, `recomputed` those it had to derive again because the store did not
hold the key, `revalidated` those that came back with the digest they held,
and `reused` is the cells of that layer the stage never reached at all.

## 16_work_counters.csv
Header `stage`, `sequence`, `amendment_id`, `cells_visited`,
`cells_recomputed`, `cells_revalidated`, `cells_reused`, `subsets_examined`,
`cache_hits`, `cache_misses`, `cache_evictions`. The stage is `build` or
`amendment`. One row for the build and one per amendment. The cache columns
are the movement over that stage alone, not a running total. `subsets_examined`
counts the subsets the solves derived again during that stage, so a solve read
back out of the store adds nothing to it.

## 17_cache_summary.json
Keys `retention`, `entries_in_force`, `entries_retained`, `hits`, `misses`,
`evictions`, `hit_ratio`. The ratio is hits over hits plus misses, to twelve
decimal places, and is an exact zero when nothing was looked up.

## 18_final_selection.json
The shape of `11_baseline_selection.json`, after every amendment.

## 19_rejected_register.csv
Header `scope`, `identifier`, `reason`, `detail`. The scope is `job`, `edge`,
`group_membership` or `amendment`. For a job the detail is its precinct, for
an edge the requiring job, a greater than sign and the required job, for a
group membership the member job, and for an amendment its lodged kind. Rows
ascend by scope, then identifier, then reason, then detail.

## 20_resource_usage.tsv
Header `precinct`, `pool`, `capacity`, `carried`, `available`, `usage`,
`headroom`, `weight_numerator`, `weight_denominator`, `weighted_usage`. Three
rows per precinct, the pools in ascending pool name, the precincts in
ascending code, taken over the final selection. The headroom is the available
quantity less the usage. The weighted usage carries twelve decimal places.

## 21_amendment_optima.csv
Header `sequence`, `amendment_id`, `precinct`, `total_mills`,
`weighted_resource`, `accepted_job_count`, `optimum_moved`. One row per
amendment per precinct, the amendments in ascending sequence and the precincts
in ascending code, holding the standing of that precinct after that amendment.
`optimum_moved` is `yes` when the solve of that precinct came back with a
digest other than the one it held before that amendment.

## 22_defect_register.md
A markdown table with the columns `stage`, `reason code` and `label`, one row
per reason code of the catalogue that this contract names, ascending by stage
then code, under the heading `# Defect register`, and a closing line naming
the modules in force.

## 23_verification_notes.md
The heading `# Verification notes`, a blank line, then one line for each of:
the round key, the round index, the workbook sheet key, the jobs in force, the
jobs set aside, the edges accepted, the edges rejected, the amendments
applied, the amendments classified inert, the precinct optima moved, the cells
in the model, the cells recomputed after the build, the store retention, the
store evictions, the baseline total mills and the final total mills.

## 24_run_manifest.txt
One line per document above, in this order, the file name, a space and the
digest of its bytes. A last line reads `publication` and the digest of the
lines before it.

## 25_summary.json
Keys `round_key`, `round_index`, `package`, `modules`, `control_totals`,
`final_weighted_resource`. `control_totals` carries `jobs_in_force`,
`jobs_set_aside`, `edges_accepted`, `edges_rejected`, `groups_open`,
`amendments_applied`, `baseline_total_mills`, `final_total_mills`,
`baseline_accepted_jobs`, `final_accepted_jobs`, `cells_in_model`,
`cells_recomputed_after_build`, `subsets_examined_after_build`, `cache_hits`
and `cache_evictions`.
"""
    write_text(root / "output_schema_reference.md", body)

    write_text(root / "serialisation_and_digest_contract.md", """# Serialisation and digest contract

Every document is UTF-8 with a single line feed ending every line, including
the last. No carriage returns and no byte order mark.

A json document is written with two space indentation, keys sorted, and one
trailing newline after the closing brace. A jsonl document is one compact json
object per line, keys sorted, no spaces after the separators.

A delimited document carries its header line first and then its rows. A csv is
separated by commas, a tsv by tabs, a psv by vertical bars. No field is
quoted, because no field carries a separator. An empty field is written as
nothing at all.

A digest is the sha256 of the bytes of the file as written, in lower case hex.
The digests of the manifest are taken last, after the twenty four documents
before it are on disk, and the closing digest of the manifest is taken over
the lines above it joined by line feeds with a trailing line feed.
""")

    write_text(root / "work_ledger_counter_contract.md", """# The work ledger

The desk publishes what the engine did as well as what it decided, because a
round that reaches the right figures by deriving the whole model again has
told the desk nothing about which of its papers actually moved.

A cell is visited when a stage reaches it, whether the stage went on to derive
it or read it back out of the store. A cell is recomputed when the store did
not hold its key and the value had to be derived. A cell is revalidated when
it was visited and the value it came back with carries the digest it already
held, and a revalidated cell stops the cascade. A cell is reused when the
stage never reached it at all, so for each layer the reused count is the cells
of that layer in the model less the cells of that layer the stage visited.

The cache counters move on lookups. A lookup that finds the key the cell
already stands at, or finds it among the superseded entries the store retains,
is a hit; anything else is a miss. An eviction is a superseded entry dropped
to keep the store inside the retained count the board memo fixes. The store
always holds the value in force for every cell, so an eviction never drops a
value the round still stands on and never moves a published figure.

Two mistakes are visible here and they are visible in different documents.
Reaching too few cells leaves a stale value standing and the selection
documents disagree with the papers. Reaching too many leaves the selection
right and the work ledger wrong. The work ledger is published, so both are
defects.
""")


def _narrative_papers(root, E):
    ri = E["round_index"]
    write_text(root / "00_open_this_first.txt", """READ THIS BEFORE THE REST

This directory holds the working papers of one replan round of the yard. A
file name here describes the role a paper plays at the desk, not what the
paper contains, so open a paper before you decide what it settles.

Start with replan_programme_contract.md. It names the fourteen stages and the
paper that specifies each one. data_lineage_and_governance.md maps every file
in this directory to the stage it serves and names the files that govern
nothing. readings_not_in_force.md lists readings of these papers that this
yard does not support, each beside the reading in force.

Three papers are not plain text. The parameter workbook carries the shift
length of each precinct and the weight of each pool. The board memo carries
the deferral rate of each class, the number of entries the working store
retains and the charge above which a job is reported as implausible. The
precedence directive carries the classification of each amendment kind, the
table of which cell is read by which, the order in which two stages that bear
on one job apply, and the rules on duplicate lodgements and double booked slot
group members. None of those values stands in any other paper in this
directory.

Two files in here are the publication the desk pulled and the counters it
published beside it. They are evidence of what the engine did. No figure in
them is authoritative, and a round that agrees with them on a governed
quantity has reproduced the fault rather than corrected it.

This round is one acquisition profile and does not reach every documented
branch. Implement each quiet branch from its stage paper rather than from what
these particular jobs happen to exercise.
""")

    write_text(root / "replan_programme_contract.md", """# Replan programme contract

The yard settles one round at a time. A round opens against the register in
force, derives the state of every job, solves each precinct exactly, and then
folds in the amendments the desk lodged during the round, one at a time, in
sequence.

The fourteen stages and the paper that specifies each one:

| stage | subject | paper |
| --- | --- | --- |
| p01 | identifiers, the register in force, the parameter layer | spec_stage_p01_identifier_and_revision.md |
| p02 | the precedence graph and its indexes | spec_stage_p02_precedence_graph.md |
| p03 | units, amounts and the normalised records | spec_stage_p03_normalisation.md |
| p04 | admissibility of one job | spec_stage_p04_admissibility.md |
| p05 | the closure of a job | spec_stage_p05_closure.md |
| p06 | what a job draws | spec_stage_p06_demand.md |
| p07 | the charge a job carries | spec_stage_p07_charges.md |
| p08 | the exclusive slot groups | spec_stage_p08_slot_groups.md |
| p09 | the pools and what is left of them | spec_stage_p09_capacity.md |
| p10 | the objective | spec_stage_p10_objective.md |
| p11 | the exact optimum of one precinct | spec_stage_p11_search.md |
| p12 | what the optimum was derived from | spec_stage_p12_provenance.md |
| p13 | the amendments and the cascade | spec_stage_p13_amendments.md |
| p14 | the publication | spec_stage_p14_publication.md |

The derived state of the round is held in seven layers of cells: `norm` and
`rule` at the bottom, then `closure`, `demand` and `charge`, then `group`, and
`solve` at the top. Each cell carries a key over the inputs it reads and a
value. A key that holds an input the cell does not read makes the round derive
work it did not need; a key that leaves out an input the cell does read leaves
a stale value standing. Both are defects and both are visible in the
publication.

The work ledger is published beside the selection. See
work_ledger_counter_contract.md for what each counter means.
""")

    write_text(root / "data_lineage_and_governance.md", """# Data lineage and governance

| file | stage | what it settles |
| --- | --- | --- |
| round_header.json | p01 | the round key and index, the workbook sheet key, the register in force |
| berth_job_register_frozen.csv | p01 | the register in force |
| berth_job_register_current.csv | p01 | nothing; the drafting copy |
| identifier_crosswalk.tsv | p01 | legacy identifiers |
| yard_topology.xml | p01 | the precincts that exist |
| topology_drafts.xml | none | nothing; a proposal |
| class_rate_register.csv | p01 | the class multipliers |
| licence_validity_register.csv | p04 | licence validity |
| priority_class_vocabulary.csv | p01 | the closed set of classes |
| yard_parameter_workbook.xlsx | p01 | shift lengths, pool weights |
| yard_board_memo.pdf | p01 | deferral rates, store retention, charge ceiling |
| cascade_precedence_directive.docx | p10, p13 | seed sets, reader table, order of application, duplicate and double booking rules |
| precedence_edge_journal.psv | p02 | the lodgements |
| exclusive_slot_groups.csv | p08 | the slot group memberships |
| pool_capacity_history.tsv | p09 | the pool capacities |
| carried_commitment_ledger.csv | p09 | the carried quantities |
| conditional_charge_rules.jsonl | p10 | the surcharges and the rebates |
| amendment_journal.jsonl | p13 | the amendments |
| amendment_supplement.ndjson | p13 | payload fields the journal leaves empty |
| row_provenance_ledger.csv | p13 | which file a payload field is read from |
| amendment_reason_catalogue.psv | p02, p08, p14 | the reason code vocabulary |
| source_priority_register.csv | p13 | the standing of each source file |
| legacy_scale_table.csv | none | nothing; retired when the workbook came in |
| prior_round_archive.db | none | nothing; the prior round, for context |
| withdrawn_plan_publication.tsv | none | nothing; the publication the desk pulled |
| withdrawn_counter_publication.csv | none | nothing; the counters beside it |
| planning_desk_roster.conf | none | nothing; a contact list |
| engine_defaults.ini | none | nothing; desk defaults |
| unit_registry.toml | p03 | the units |
| rounding_and_arithmetic_policy.yaml | p07, p10, p14 | where rounding happens |
| revision_precedence.toml | p01, p09 | which row of a register is in force |
| precedence_and_order_policy.toml | all | canonical order |
| publication_form_rules.toml | p14 | the form of the documents |
| package_expectations.toml | p14 | what the delivered engine has to be |
| output_schema_reference.md | p14 | the shape of every document |
| serialisation_and_digest_contract.md | p14 | encoding, line endings, digests |
| work_ledger_counter_contract.md | p13 | what each counter counts |
| project.zip | none | the engine as the yard currently runs it |
| 00_open_this_first.txt | none | nothing; where to start |
| replan_programme_contract.md | all | the fourteen stages and their papers |
| data_lineage_and_governance.md | none | nothing; this table |
| spec_stage_p01_identifier_and_revision.md | p01 | the register in force and the parameter layer |
| spec_stage_p02_precedence_graph.md | p02 | the graph and the order of the edge tests |
| spec_stage_p03_normalisation.md | p03 | the units, the amount grammar, the normalised record |
| spec_stage_p04_admissibility.md | p04 | the two admissibility tests and their order |
| spec_stage_p05_closure.md | p05 | the closure of a job and what blocks it |
| spec_stage_p06_demand.md | p06 | the own and closed vectors |
| spec_stage_p07_charges.md | p07 | the scaled charge, the penalty, the ceiling |
| spec_stage_p08_slot_groups.md | p08 | the double booking rule and what binds |
| spec_stage_p09_capacity.md | p09 | the capacities, the carried quantities, the boundary |
| spec_stage_p10_objective.md | p10 | the order of the charge stages and the four ranking keys |
| spec_stage_p11_search.md | p11 | the exact optimum of one precinct |
| spec_stage_p12_provenance.md | p12 | the inputs of a solve key |
| spec_stage_p13_amendments.md | p13 | the classification, the seeds and the cut off |
| spec_stage_p14_publication.md | p14 | the twenty five documents and the manifest |
| readings_not_in_force.md | none | nothing; readings this yard refuses |
| known_traps_and_footguns.md | none | nothing; what the desk has been caught by |
| worked_examples.md | none | nothing; invented figures showing each rule |
| glossary_and_reason_codes.md | none | nothing; the vocabulary |

A file marked as settling nothing is still worth opening: it is where a wrong
reading of this round is most easily reached from.
""")

    write_text(root / "readings_not_in_force.md", """# Readings this yard does not support

Each line names a reading the desk has seen taken of these papers, and the
reading in force beside it.

Not in force: the drafting copy of the job register is the more recent file
and so the more authoritative. In force: the round header names the register
in force and the drafting copy settles nothing at all.

Not in force: the shift length is four hundred and eighty minutes across the
yard. In force: the shift length is per precinct and stands on the live sheet
of the parameter workbook. The four hundred and eighty minute figure is the
retired scale table.

Not in force: the pools are weighted alike when two accepted sets are ranked.
In force: each pool carries its own weight, on the live sheet of the parameter
workbook. The flat weighting is the retired scale table.

Not in force: the deferral rate is one figure for the whole yard. In force:
the rate is per class and stands in the sitting of the board memo that is in
force for this round. A rate carried by a rescinded sitting settles nothing.

Not in force: a pool is left when its usage reaches the available quantity. In
force: a usage equal to the available quantity is within the pool.

Not in force: an accepted set is settled on the charge alone. In force: the
charge is the first of four keys and the three behind it settle a tie.

Not in force: every job outside the accepted set carries a deferral penalty.
In force: only a selectable charter job left out carries one.

Not in force: the closure rebate is taken of the scaled charges. In force: it
is taken of the scaled charges and the surcharges together.

Not in force: a withdrawal of a lodgement moves nothing, because a withdrawal
removes rather than adds. In force: a withdrawal seeds the closure of the
requiring job like any other movement of the graph, and the cascade decides
what follows from the value that comes back.

Not in force: a change of capacity reaches the closures of the precinct. In
force: it reaches the solve of that precinct and nothing else.

Not in force: a change to a title, a note, an owner or a display order reaches
the round. In force: those fields govern nothing, stand in no key, and seed
nothing.

Not in force: a cell whose value comes back unchanged still passes the cascade
on to the cells that read it. In force: the cascade stops there.

Not in force: a change to one job reaches only that job's own demand. In
force: it reaches the demand of every job whose closure holds it.

Not in force: the solve of a precinct is keyed on its jobs alone. In force: it
is keyed on the charge rules of that precinct as well, and a rule whose
normalised value moves moves the solve with it.

Not in force: the source priority register settles which file a payload field
is read from, and the supplement outranks the journal wherever both carry the
field. In force: row_provenance_ledger.csv names the source for that amendment
and that field, and a supplement row is folded in only where the ledger names
the supplement in force and the supplement row itself stands in force. The
priority register orders the files and settles no field.
""")

    write_text(root / "known_traps_and_footguns.md", """# Known traps and footguns

The desk has kept this list across several rounds.

A register holds rows sealed for a later round. They are not amendments and
this round does not read them.

A register holds withdrawn rows. A withdrawn row that is the row in force sets
the job aside; a withdrawn row behind a later sealed row does nothing.

The capacity history holds rescinded rows with a later effective round. They
look like the newest word on the pool and they settle nothing.

The charge rule file holds lapsed rules from earlier schedules. Only a rule in
force is read.

The amendment journal holds withdrawn rows from this round and rows raised
against earlier rounds. Only a lodged row is an amendment.

Two amendments may carry the same payload. The second one still has to be
classified, seeded and cascaded; what it costs is a matter for the store, not
for the classification.

An amendment may be the exact inverse of an earlier one. It is applied like
any other amendment and the store is what makes it cheap.

A slot group may be left with one member, or with none. Such a group binds
nothing, and a round that treats a group of one as a constraint will refuse
sets it should have accepted.

A precinct may carry a rule that never fires in this round. It is still a rule
and it still stands in the key of that precinct's solve.

The closure rebate needs the job it hangs on to hold two or more jobs in its
closure, counted at any depth. A rebate on a job whose closure holds one job
is not taken, however many prerequisites that job names directly.

The amount grammar accepts three forms of one figure. Two amounts that reach
the same whole mills are the same amount, and a restatement from one form to
another moves nothing behind the rule.

The edge journal may hold the same pair twice. One prerequisite, and
withdrawing either row while the other stands leaves the prerequisite in
place.
""")


def _worked_examples(root, E):
    ri = E["round_index"]
    body = """# Worked examples

These are worked against invented figures. They show the shape of each rule,
not the values of this round.

## An amount in three forms

`4800`, `4,800 mills` and `4.800 GBP` are one amount of four thousand eight
hundred mills. `4 GBP` is four thousand mills. `12.5` is refused: an amount in
mills carries no fraction.

## A crew quantity

A job in a precinct whose shift length is 450 minutes, carrying a crew
quantity of 3 in the unit `shift`, draws 1350 crew minutes. The same job
carrying a crew quantity of 1350 in the unit `minute` draws the same 1350.

## A scaled charge

A base charge of 41 250 mills at a class multiplier of 10 400 basis points is
41 250 times 10 400 over 10 000, which is 42 900 exactly, so the scaled charge
is 42 900 mills. A base charge of 41 251 at the same multiplier is
42 901.04 exactly, which rounds to 42 901.

## A closure and what it draws

Take D requiring C, C requiring B, and B requiring A. The closure of D is A, B
and C. Selecting D alone opens the closed set A, B, C, D. If A draws 4 quarter
days and the other three draw 3 each, the usage is 13 quarter days, not the
4 plus 13 that adding the closed vectors of two of them would give.

## The order of the three charge stages

Take a precinct whose closed set carries scaled charges of 60 000 mills, a
pair surcharge of 5 000 mills, and a closure rebate of 900 basis points on a
job whose closure holds two jobs. The rebate is taken of 65 000, which is
5 850, so the charge is 60 000 plus 5 000 less 5 850, or 59 150. Taking the
rebate of 60 000 instead would give 5 400 and a charge of 59 600, which is the
reading not in force.

## The capacity test on its boundary

A pool of capacity 900 with 120 carried has 780 available. A selection using
780 is within the pool. A selection using 781 is not.

## Ranking two accepted sets

Two sets both come to 118 400 mills. The first uses 20 quarter days, 6 lifts
and 2 400 crew minutes; the second uses 18 quarter days, 8 lifts and 2 400.
At pool weights of 25, 7 and one sixtieth, the first weighs
500 plus 42 plus 40, which is 582; the second weighs 450 plus 56 plus 40,
which is 546. The second is the accepted set. Under a flat weighting they
would weigh 2 426 and 2 426 and the tie would fall through to the count of
optional jobs, which is a different answer.

## A cascade that stops

A restatement moves the text of a rule amount from `4,800 mills` to
`4.800 GBP`. The rule cell is seeded and derived again. Its normalised value
is the same four thousand eight hundred mills, so its digest has not moved,
the cell is revalidated, and the solve of that precinct is never visited. The
work ledger for that amendment shows one cell visited, one revalidated, one
recomputed if the store did not hold the key, and no subsets examined at all.

## A cascade that does not stop

A lodgement adds a prerequisite at the bottom of a chain of six jobs. The
closure of the job it names moves, so the closure of the job that names that
one is visited, and so on up the chain. Each of those closures moves the
demand of its own job, and the demand of every job whose closure now holds the
new prerequisite. The solve of that precinct is visited once, at the end.

## A reversal

An amendment takes a pool capacity from 900 to 899. A later amendment names
it and reverses it, so the capacity goes back to 900. The solve of that
precinct is seeded and its key is the key it stood at before the first
amendment. The store is holding that key among its superseded entries, so the
value comes back as a hit, nothing is recomputed, and no subsets are examined.
"""
    write_text(root / "worked_examples.md", body)


def _glossary(root, E):
    lines = ["# Glossary and reason codes", "",
             "**Precinct**  one part of the yard, with its own pools, its own",
             "slot groups, its own charge rules and its own jobs. Nothing",
             "crosses a precinct.", "",
             "**Job**  one berth job the desk may accept or defer.", "",
             "**Standing**  `charter` for a job the yard owes, which carries a",
             "deferral penalty when it is left out, or `optional` for a job",
             "that carries none.", "",
             "**Closure**  every job standing behind a job through accepted",
             "prerequisites, at any depth.", "",
             "**Closed set**  a selection together with the closure of every",
             "job in it, each distinct job counted once.", "",
             "**Cell**  one derived value with a key over the inputs it reads.",
             "", "**Seed set**  the cells an amendment reaches first.", "",
             "**Cascade**  the walk from the seed set through the cells that",
             "read them, stopping wherever a value comes back unchanged.", "",
             "**Working store**  what lets a configuration the round has",
             "already stood in be read back rather than derived again.", "",
             "## Reason codes", "",
             "| code | stage | what it says |", "| --- | --- | --- |"]
    rows = [
        ("JOB-DRAFTONLY", "p01", "the register in force holds no sealed row for this job at or below the round index"),
        ("JOB-WITHDRAWN", "p01", "the row in force carries the state withdrawn"),
        ("JOB-NOPRECINCT", "p01", "the precinct named is not in the live topology"),
        ("JOB-CYCLE", "p02", "the job stands among its own prerequisites"),
        ("JOB-LICENCE", "p04", "the licence is not valid for this round"),
        ("JOB-OUTOFROUND", "p04", "the round index lies outside the window of the job"),
        ("JOB-CLOSUREBLOCKED", "p05", "something in the closure is inadmissible or set aside"),
        ("EDG-WITHDRAWN", "p02", "the lodgement is not active"),
        ("EDG-ADVISORY", "p02", "the lodgement is advisory and creates no prerequisite"),
        ("EDG-SELF", "p02", "both ends are one job"),
        ("EDG-UNKNOWNJOB", "p02", "an end is not a job in force"),
        ("EDG-CROSSPRECINCT", "p02", "the ends stand in different precincts"),
        ("EDG-DUPLICATE", "p02", "the pair is already carried by a lower lodgement"),
        ("EDG-CYCLE", "p02", "the lodgement would close a precedence cycle"),
        ("GRP-DOUBLEBOOKED", "p08", "the job already stands in a group of earlier precedence"),
        ("GRP-SINGLE", "p08", "a group of one open member binds nothing"),
        ("AMD-NOTARGET", "p13", "the reversal names no amendment this round applied"),
        ("CMT-UNKNOWN", "p13", "the commitment named is not binding this round"),
    ]
    for code, stage, meaning in rows:
        lines.append("| " + code + " | " + stage + " | " + meaning + " |")
    lines.append("")
    write_lines(root / "glossary_and_reason_codes.md", lines)


def write_papers(root, E):
    _narrative_papers(root, E)
    _stage_papers(root, E)
    _policy_papers(root, E)
    _schema_paper(root, E)
    _worked_examples(root, E)
    _glossary(root, E)


# --------------------------------------------------------------------------
# graded assertions
#
# Two surfaces. The documents delivered for the shipped round are compared
# against this file's own reference chain over a corpus minted here from
# SAMPLE_SEED. The engine delivered beside them is extracted and driven over
# three rounds minted from seeds it has never seen.
# --------------------------------------------------------------------------
MINTED_SEEDS = (EVAL_SEED, CHALLENGE_SEED, PROBE_SEED)

IDENTIFIER_GROUP = ["01_identifier_canon.json", "04_normalised_jobs.csv",
                    "06_feasibility_map.csv"]
GRAPH_GROUP = ["02_precedence_edges.tsv", "03_reverse_index.json",
               "19_rejected_register.csv"]
CLOSURE_GROUP = ["07_closure_map.jsonl", "08_demand_vectors.csv"]
CHARGE_GROUP = ["05_normalised_rules.csv", "10_charge_contributions.csv"]
BASELINE_GROUP = ["09_conflict_groups.json", "11_baseline_selection.json",
                  "12_baseline_trace.jsonl"]
CLASSIFICATION_GROUP = ["13_amendment_classification.csv"]
INVALIDATION_GROUP = ["14_invalidation_sets.jsonl"]
LEDGER_GROUP = ["15_reuse_ledger.csv", "16_work_counters.csv"]
STORE_GROUP = ["17_cache_summary.json"]
FINAL_GROUP = ["18_final_selection.json", "20_resource_usage.tsv",
               "21_amendment_optima.csv"]
AUDIT_GROUP = ["22_defect_register.md", "23_verification_notes.md",
               "24_run_manifest.txt", "25_summary.json"]

STATE_FAMILY = (IDENTIFIER_GROUP + CHARGE_GROUP + CLOSURE_GROUP
                + BASELINE_GROUP + ["18_final_selection.json",
                                    "19_rejected_register.csv",
                                    "20_resource_usage.tsv"])
CASCADE_FAMILY = (CLASSIFICATION_GROUP + INVALIDATION_GROUP + LEDGER_GROUP
                  + STORE_GROUP + ["21_amendment_optima.csv"])
PUBLICATION_FAMILY = (GRAPH_GROUP + AUDIT_GROUP)

_CACHE = {}
# rewardkit runs checks in parallel threads, and ref_publish switches the
# module-wide WRONG set while it runs. Every corpus and reference build holds
# this lock so no build ever reads another thread's WRONG.
_BUILD_LOCK = threading.RLock()


def _scratch(tag):
    path = Path(tempfile.mkdtemp(prefix="slwopt-" + tag + "-"))
    os.chmod(path, 0o777)
    return path


def _corpus(seed):
    key = ("corpus", seed)
    with _BUILD_LOCK:
        if key not in _CACHE:
            root = write_corpus(_scratch("corpus"), seed)
            for path in [root] + list(root.rglob("*")):
                os.chmod(path, 0o777 if path.is_dir() else 0o666)
            _CACHE[key] = root
        return _CACHE[key]


def _reference(seed, rules=()):
    key = ("reference", seed, tuple(sorted(rules)))
    with _BUILD_LOCK:
        if key not in _CACHE:
            out = _scratch("reference")
            ref_publish(_corpus(seed), out, rules)
            _CACHE[key] = {p.name: p.read_bytes() for p in sorted(out.iterdir())}
        return _CACHE[key]


def _delivered(name):
    path = Path(OUTPUT_ROOT) / name
    if not path.is_file():
        raise AssertionError("delivered document is absent: " + name)
    return path.read_bytes()


def _demote():
    if os.geteuid() != 0:
        return None

    def drop():
        os.setgid(65534)
        os.setuid(65534)

    return drop


def _engine_root():
    if "engine" not in _CACHE:
        raw = _delivered("patched_engine.zip")
        root = _scratch("engine")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for member in archive.namelist():
                if member.startswith("/") or ".." in Path(member).parts:
                    raise AssertionError("archive member escapes the root: "
                                         + member)
            archive.extractall(root)
        for path in [root] + list(root.rglob("*")):
            os.chmod(path, 0o777 if path.is_dir() else 0o666)
        _CACHE["engine"] = root
    return _CACHE["engine"]


def _tree_digest(root):
    """The bytes of one paper directory, as a digest over name and content."""
    root = Path(root)
    parts = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            parts.append(str(path.relative_to(root)))
            parts.append(digest_file(path))
    return digest_text(NL.join(parts))


def _drive(data, tag, cwd=None, data_first=False):
    """Run the delivered engine over one round and collect what it wrote.

    The destination is named but never made, because the engine has to
    create it when it is absent. The paper directory is digested either side
    of the run, because the contract has the engine read it and leave it.
    The two options are written out first on every round but one, where they
    are written data first, because the contract has the engine take them in
    either order and an assertion settles that more cheaply than a judge.
    """
    root = _engine_root()
    out = _scratch(tag) / "destination"
    home = _scratch(tag + "-home") if cwd is None else cwd
    before = _tree_digest(data)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin",
           "PYTHONPATH": str(root / "src"),
           "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": str(home), "TMPDIR": str(home), "LC_ALL": "C"}
    options = (["--data", str(data), "--out", str(out)] if data_first
               else ["--out", str(out), "--data", str(data)])
    proc = subprocess.run([sys.executable, "-m", PACKAGE_NAME] + options,
                          capture_output=True, text=True, env=env,
                          cwd=str(home), preexec_fn=_demote(), timeout=300)
    if proc.returncode != 0:
        raise AssertionError("the delivered engine exited "
                             + str(proc.returncode) + ": "
                             + proc.stderr.strip()[-400:])
    if _tree_digest(data) != before:
        raise AssertionError("the delivered engine moved the paper directory")
    return {p.name: p.read_bytes() for p in sorted(out.iterdir())}


def _case(seed, tag="case"):
    """The probe round is the one driven with the data option written first."""
    key = ("case", seed, tag)
    if key not in _CACHE:
        _CACHE[key] = _drive(_corpus(seed), tag, data_first=(seed == PROBE_SEED))
    return _CACHE[key]


def _compare(family, got, expected, label):
    wrong = []
    for name in family:
        if name not in got:
            wrong.append(name + " absent")
        elif got[name] != expected[name]:
            wrong.append(name)
    if wrong:
        raise AssertionError(label + " disagrees on: " + ", ".join(wrong))


def _shipped(family):
    expected = _reference(SAMPLE_SEED)
    got = {name: _delivered(name) for name in family}
    _compare(family, got, expected, "the shipped round")


def _minted(seed, family):
    got = _case(seed)
    extra = sorted(set(got) - set(ARTIFACT_NAMES))
    if extra:
        raise AssertionError("the minted round " + str(seed)
                             + " carries documents the contract does not"
                             + " name: " + ", ".join(extra))
    _compare(family, got, _reference(seed),
             "the minted round " + str(seed))


# --------------------------------------------------------------------------
# structural assertions
# --------------------------------------------------------------------------
def test_delivered_documents_present_and_parse():
    """POSITIVE: every declared document is present, parses in its own shape,
    and carries the header line the schema reference fixes."""
    for name in ARTIFACT_NAMES:
        raw = _delivered(name)
        text = raw.decode("utf-8")
        assert text.endswith(NL), name + " has no trailing newline"
        assert "\r" not in text, name + " carries a carriage return"
        if name.endswith(".json"):
            json.loads(text)
        elif name.endswith(".jsonl"):
            for line in text.splitlines():
                json.loads(line)
        elif name.endswith(".csv") or name.endswith(".tsv"):
            sep = TAB if name.endswith(".tsv") else ","
            head = text.splitlines()[0]
            assert sep in head, name + " carries no header line"
    manifest = _delivered("24_run_manifest.txt").decode("utf-8").splitlines()
    assert len(manifest) == len(ARTIFACT_NAMES), "the manifest is the wrong length"
    assert manifest[-1].startswith("publication "), "the manifest has no closing digest"


def test_delivered_package_shape():
    """POSITIVE: the delivered archive carries the module list the package
    expectations name, under a src layout, with the shipped suite carried
    through byte for byte and no third party import anywhere in it."""
    root = _engine_root()
    assert (root / "pyproject.toml").is_file(), "the archive carries no pyproject"
    for module in PACKAGE_MODULES:
        path = root / "src" / PACKAGE_NAME / (module + ".py")
        assert path.is_file(), "the archive carries no module " + module
    shipped = _scratch("shipped")
    with zipfile.ZipFile(_corpus(SAMPLE_SEED) / "project.zip") as archive:
        archive.extractall(shipped)
    carried = shipped / "tests" / "test_visible.py"
    delivered = root / "tests" / "test_visible.py"
    assert delivered.is_file(), "the shipped suite was dropped"
    assert delivered.read_bytes() == carried.read_bytes(), \
        "the shipped suite was edited"
    allowed = set(sys.stdlib_module_names) | {PACKAGE_NAME, ""}
    for path in sorted((root / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in allowed, \
                        "third party import " + alias.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                head = (node.module or "").split(".")[0]
                assert head in allowed, "third party import " + str(node.module)


# --------------------------------------------------------------------------
# the shipped round
# --------------------------------------------------------------------------
def test_shipped_identifier_layer_exact():
    """POSITIVE: the register in force, the crosswalk, the licence test and
    the round window come out as the papers put them."""
    _shipped(IDENTIFIER_GROUP)


def test_shipped_graph_layer_exact():
    """POSITIVE: every lodgement is accepted or rejected under the reason the
    papers give it, and the reverse index and the rejection register agree
    with the accepted graph."""
    _shipped(GRAPH_GROUP)


def test_shipped_closure_and_demand_exact():
    """POSITIVE: the closure of every job and the two demand vectors come out
    as stages p05 and p06 put them."""
    _shipped(CLOSURE_GROUP)


def test_shipped_rule_and_charge_exact():
    """POSITIVE: the normalised charge rules and the scaled charges and
    deferral penalties come out as stages p03 and p07 put them."""
    _shipped(CHARGE_GROUP)


def test_shipped_baseline_optimum_exact():
    """POSITIVE: the open slot groups, the accepted set of every precinct
    before any amendment and the trace of the search that reached it come out
    exactly."""
    _shipped(BASELINE_GROUP)


def test_shipped_amendment_classification_exact():
    """POSITIVE: every amendment is classified and seeded as the precedence
    directive fixes, including the inert one and the restatement."""
    _shipped(CLASSIFICATION_GROUP)


def test_shipped_invalidation_sets_exact():
    """POSITIVE: the cells whose digest moved and the cells that came back
    with the digest they held come out exactly, amendment by amendment."""
    _shipped(INVALIDATION_GROUP)


def test_shipped_work_ledger_exact():
    """POSITIVE: the reuse ledger and the work counters come out exactly, so
    the round reached the cells it had to reach and no others."""
    _shipped(LEDGER_GROUP)


def test_shipped_store_summary_exact():
    """POSITIVE: the working store summary comes out exactly, with the
    retention the board memo fixes and the hits, misses and evictions that
    follow from it."""
    _shipped(STORE_GROUP)


def test_shipped_final_optimum_exact():
    """POSITIVE: the accepted set after every amendment, the standing of each
    precinct at each amendment, and the capacities, carried quantities,
    headroom and weighted usage of every pool come out exactly."""
    _shipped(FINAL_GROUP)


def test_shipped_audit_documents_exact():
    """POSITIVE: the defect register, the verification notes, the manifest and
    the summary come out exactly."""
    _shipped(AUDIT_GROUP)


# --------------------------------------------------------------------------
# rounds the delivered engine has never seen
# --------------------------------------------------------------------------
def test_package_eval_state_exact():
    """POSITIVE: driven over a round minted from a seed it has never seen, the
    delivered engine reaches the same derived state and the same accepted
    sets."""
    _minted(EVAL_SEED, STATE_FAMILY)


def test_package_eval_cascade_exact():
    """POSITIVE: on that round the classification, the invalidation sets, the
    work ledger and the store summary come out exactly."""
    _minted(EVAL_SEED, CASCADE_FAMILY)


def test_package_challenge_state_exact():
    """POSITIVE: on a second unseen round the derived state and the accepted
    sets come out exactly."""
    _minted(CHALLENGE_SEED, STATE_FAMILY)


def test_package_challenge_cascade_exact():
    """POSITIVE: on that second round the classification, the invalidation
    sets, the work ledger and the store summary come out exactly."""
    _minted(CHALLENGE_SEED, CASCADE_FAMILY)


def test_package_probe_publication_exact():
    """POSITIVE: on a third unseen round the graph documents, the defect
    register, the verification notes, the manifest and the summary come out
    exactly."""
    _minted(PROBE_SEED, PUBLICATION_FAMILY)


# --------------------------------------------------------------------------
# negative detectors
#
# Each semantic detector rebuilds the whole publication under one named wrong
# reading and fires only when the delivered bytes match that reconstruction on
# every document the reading moves. Each short circuits on a correct delivery,
# so a correct submission trips none of them, and each raises rather than
# returning when a document is absent, so an empty container trips none of
# them either.
# --------------------------------------------------------------------------
def _detector(rule):
    expected = _reference(SAMPLE_SEED)
    naive = _reference(SAMPLE_SEED, (rule,))
    moved = sorted(name for name in expected if naive[name] != expected[name])
    if not moved:
        raise AssertionError("the reading moves nothing; the detector cannot fire")
    got = {name: _delivered(name) for name in moved}
    if all(got[name] == expected[name] for name in moved):
        raise AssertionError("the documents are correct; this detector stays silent")
    assert all(got[name] == naive[name] for name in moved)


def test_negative_weight_shift_length_taken_flat():
    """NEGATIVE: the crew quantities were converted at one shift length across
    the yard, which is the retired scale table, in place of the per precinct
    shift length on the live sheet of the parameter workbook."""
    _detector("R_FLAT_SHIFT")


def test_negative_weight_pool_weights_taken_flat():
    """NEGATIVE: the three pools were weighted alike when two accepted sets
    were ranked, which is the retired scale table, in place of the pool
    weights on the live sheet of the parameter workbook."""
    _detector("R_LEGACY_WEIGHTS")


def test_negative_weight_deferral_rate_from_the_rescinded_sitting():
    """NEGATIVE: the deferral rates were taken from the sitting of the board
    memo marked as rescinded in full, in place of the sitting the memo marks
    as in force for this round."""
    _detector("R_RESCINDED_MEMO")


def test_negative_weight_drafting_register_read():
    """NEGATIVE: the round was derived from the drafting copy of the job
    register in place of the register the round header names."""
    _detector("R_CURRENT_REGISTER")


def test_negative_weight_capacity_boundary_read_as_strict():
    """NEGATIVE: a selection using exactly the available quantity of a pool
    was turned down, so the capacity test was read as strict against the
    resolution the board memo carries."""
    _detector("R_STRICT_CAPACITY")


def test_negative_weight_set_ranked_on_charge_alone():
    """NEGATIVE: two accepted sets carrying one charge were settled by the
    order they were examined in, leaving the weighted resource, the count of
    optional jobs and the canonical job order unread."""
    _detector("R_COST_ONLY")


def test_negative_weight_rebate_taken_before_the_surcharges():
    """NEGATIVE: the closure rebate was taken of the scaled charges alone,
    leaving the surcharges of that precinct out of the sum the directive puts
    the rebate over."""
    _detector("R_REBATE_BEFORE")


def test_negative_weight_penalty_charged_on_every_job():
    """NEGATIVE: a deferral penalty was charged for every job outside the
    closed set, so optional jobs and jobs that could never have been taken
    were charged as though the yard had deferred them."""
    _detector("R_PENALTY_ALL")


def test_negative_weight_cascade_stopped_at_the_first_hop():
    """NEGATIVE: a change to one job reached that job's own demand and stopped
    there, leaving the demand of every job whose closure holds it standing at
    the value it held before."""
    _detector("R_SHALLOW_CASCADE")


def test_negative_weight_cascade_never_stopped():
    """NEGATIVE: a cell that came back with the digest it already held still
    passed the cascade on, so the round reached cells that no amendment
    touched and the work ledger records work that was never owed."""
    _detector("R_NO_CUTOFF")


def test_negative_weight_withdrawal_treated_as_inert():
    """NEGATIVE: the withdrawal of a lodgement seeded nothing, on the reading
    that removing an edge can only take work away."""
    _detector("R_REMOVAL_INERT")


def test_negative_weight_rebinds_verifier_dependencies():
    """NEGATIVE: the delivered archive carries a module or a startup hook whose
    name would shadow a standard library module or a site hook once the
    archive is placed on the import path, which is how a submission reaches
    for the machinery that grades it."""
    root = _engine_root()
    shadowed = set(sys.stdlib_module_names) | {"sitecustomize", "usercustomize",
                                               "conftest", "pytest", "pth"}
    carried = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".pth":
            carried.append(str(path.relative_to(root)))
        elif path.suffix == ".py" and path.stem in shadowed:
            if path.parent == root / "src":
                carried.append(str(path.relative_to(root)))
    assert carried, "the archive shadows no verifier dependency"


def test_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: the shipped documents are right while the delivered engine
    produces no usable output at all on any minted round, so there is no
    engine behind the delivery. The trigger is the absence of output rather
    than the wrongness of it: an engine that runs and reads a rule wrongly
    already forfeits the minted tier without being charged for a copy it did
    not make."""
    expected = _reference(SAMPLE_SEED)
    core = STATE_FAMILY + CASCADE_FAMILY
    if any(_delivered(name) != expected[name] for name in core):
        raise AssertionError("the shipped record is wrong; this detector stays silent")
    silent = 0
    for seed in MINTED_SEEDS:
        try:
            _case(seed)
        except Exception:
            silent += 1
    assert silent == len(MINTED_SEEDS)


def test_negative_weight_package_ignores_its_input():
    """NEGATIVE: the engine writes one constant record whatever round it is
    pointed at, and that constant is not the shipped round. The shipped round
    case belongs to the detector above, so the two are disjoint and one
    delivery never fires both."""
    shipped = _reference(SAMPLE_SEED)["18_final_selection.json"]
    first = _case(EVAL_SEED)["18_final_selection.json"]
    second = _case(PROBE_SEED)["18_final_selection.json"]
    if first == shipped:
        raise AssertionError("the engine emits the shipped round; the corpus "
                             "detector owns that defect")
    assert first == second


def test_negative_weight_nondeterministic_output():
    """NEGATIVE: two runs of the engine over one round, at one identical path,
    disagree, so the delivered figures are not reproducible. Holding the path
    fixed is what keeps this detector off the directory name defect."""
    first = _case(CHALLENGE_SEED)
    second = _drive(_corpus(CHALLENGE_SEED), "repeat")
    assert any(first.get(name) != second.get(name) for name in ARTIFACT_NAMES)


def test_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: the engine is reproducible at one path and still writes
    something else when the same round is presented under a different
    directory name. The reproducibility clause keeps this detector disjoint
    from the one above."""
    first = _case(CHALLENGE_SEED)
    second = _drive(_corpus(CHALLENGE_SEED), "repeat")
    if any(first.get(name) != second.get(name) for name in ARTIFACT_NAMES):
        raise AssertionError("the engine is not reproducible; the determinism "
                             "detector owns that defect")
    moved = _scratch("renamed") / "papers_under_another_name"
    shutil.copytree(_corpus(CHALLENGE_SEED), moved)
    for path in [moved] + list(moved.rglob("*")):
        os.chmod(path, 0o777 if path.is_dir() else 0o666)
    third = _drive(moved, "renamed-run")
    assert any(first.get(name) != third.get(name) for name in ARTIFACT_NAMES)


def test_negative_weight_reads_training_corpus_at_runtime():
    """NEGATIVE: the engine reached for a round sitting beside its working
    directory in place of the one its data option named."""
    home = _scratch("ambient")
    shutil.copytree(_corpus(PROBE_SEED), home / "data")
    for path in list((home / "data").rglob("*")) + [home / "data"]:
        os.chmod(path, 0o777 if path.is_dir() else 0o666)
    got = _drive(_corpus(EVAL_SEED), "ambient-run", cwd=home)
    wanted = _reference(EVAL_SEED)["18_final_selection.json"]
    if got.get("18_final_selection.json") == wanted:
        raise AssertionError("the engine read the round it was given; this "
                             "detector stays silent")
    assert got.get("18_final_selection.json") == \
        _reference(PROBE_SEED)["18_final_selection.json"]


# rewardkit criteria. The wrapper turns a raising check into False because a
# raise inside any check aborts the whole run and writes no reward.
def _bind(workspace):
    global OUTPUT_ROOT
    OUTPUT_ROOT = str(Path(workspace) / "out")


def _graded(workspace, check):
    _bind(workspace)
    try:
        check()
        return True
    except Exception:
        return False


@criterion(description="every declared document is present, parses in its own shape and carries the header line the schema reference fixes")
def delivered_documents_present_and_parse(workspace: Path) -> bool:
    return _graded(workspace, test_delivered_documents_present_and_parse)


@criterion(description="the delivered archive carries the expected module list under a src layout with the shipped suite byte for byte and no third party import")
def delivered_package_shape(workspace: Path) -> bool:
    return _graded(workspace, test_delivered_package_shape)


@criterion(description="the register in force, the crosswalk, the licence test and the round window come out as the papers put them")
def shipped_identifier_layer_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_identifier_layer_exact)


@criterion(description="every lodgement is accepted or rejected under the reason the papers give it and the reverse index and rejection register agree")
def shipped_graph_layer_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_graph_layer_exact)


@criterion(description="the closure of every job and the two demand vectors come out as stages p05 and p06 put them")
def shipped_closure_and_demand_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_closure_and_demand_exact)


@criterion(description="the normalised charge rules and the scaled charges and deferral penalties come out as stages p03 and p07 put them")
def shipped_rule_and_charge_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_rule_and_charge_exact)


@criterion(description="the open slot groups, the accepted set of every precinct before any amendment and the search trace come out exactly")
def shipped_baseline_optimum_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_baseline_optimum_exact)


@criterion(description="every amendment is classified and seeded as the precedence directive fixes, including the inert one and the restatement")
def shipped_amendment_classification_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_amendment_classification_exact)


@criterion(description="the cells whose digest moved and the cells that came back unchanged come out exactly, amendment by amendment")
def shipped_invalidation_sets_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_invalidation_sets_exact)


@criterion(description="the reuse ledger and the work counters come out exactly, so the round reached the cells it had to reach and no others")
def shipped_work_ledger_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_work_ledger_exact)


@criterion(description="the working store summary comes out exactly, with the retention the board memo fixes and the hits, misses and evictions that follow")
def shipped_store_summary_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_store_summary_exact)


@criterion(description="the accepted set after every amendment, the standing of each precinct and the pool capacities and usage come out exactly")
def shipped_final_optimum_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_final_optimum_exact)


@criterion(description="the defect register, the verification notes, the manifest and the summary come out exactly")
def shipped_audit_documents_exact(workspace: Path) -> bool:
    return _graded(workspace, test_shipped_audit_documents_exact)


@criterion(description="driven over a round minted from an unseen seed, the delivered engine reaches the same derived state and accepted sets")
def package_eval_state_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_eval_state_exact)


@criterion(description="on that round the classification, invalidation sets, work ledger and store summary come out exactly")
def package_eval_cascade_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_eval_cascade_exact)


@criterion(description="on a second unseen round the derived state and the accepted sets come out exactly")
def package_challenge_state_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_challenge_state_exact)


@criterion(description="on that second round the classification, invalidation sets, work ledger and store summary come out exactly")
def package_challenge_cascade_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_challenge_cascade_exact)


@criterion(description="on a third unseen round the graph documents, defect register, verification notes, manifest and summary come out exactly")
def package_probe_publication_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_probe_publication_exact)


@criterion(description="the crew quantities were converted at one flat shift length across the yard in place of the per precinct shift length on the live sheet")
def negative_shift_length_taken_flat(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_shift_length_taken_flat)


@criterion(description="the three pools were weighted alike when accepted sets were ranked in place of the pool weights on the live sheet")
def negative_pool_weights_taken_flat(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_pool_weights_taken_flat)


@criterion(description="the deferral rates were taken from the sitting the memo marks rescinded in place of the sitting in force")
def negative_deferral_rate_from_the_rescinded_sitting(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_deferral_rate_from_the_rescinded_sitting)


@criterion(description="the round was derived from the drafting copy of the job register in place of the register the round header names")
def negative_drafting_register_read(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_drafting_register_read)


@criterion(description="a selection using exactly the available quantity of a pool was turned down, reading the capacity test as strict")
def negative_capacity_boundary_read_as_strict(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_capacity_boundary_read_as_strict)


@criterion(description="two accepted sets carrying one charge were settled by examination order, leaving the three ranking keys unread")
def negative_set_ranked_on_charge_alone(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_set_ranked_on_charge_alone)


@criterion(description="the closure rebate was taken of the scaled charges alone, leaving the precinct surcharges out of the sum")
def negative_rebate_taken_before_the_surcharges(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_rebate_taken_before_the_surcharges)


@criterion(description="a deferral penalty was charged for every job outside the closed set, including optional and blocked jobs")
def negative_penalty_charged_on_every_job(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_penalty_charged_on_every_job)


@criterion(description="a change to one job reached its own demand and stopped, leaving the demand of jobs whose closure holds it unmoved")
def negative_cascade_stopped_at_the_first_hop(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_cascade_stopped_at_the_first_hop)


@criterion(description="a cell that came back unchanged still passed the cascade on, so the round reached cells no amendment touched")
def negative_cascade_never_stopped(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_cascade_never_stopped)


@criterion(description="the withdrawal of a lodgement seeded nothing, on the reading that removing an edge only takes work away")
def negative_withdrawal_treated_as_inert(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_withdrawal_treated_as_inert)


@criterion(description="the delivered archive carries a module or startup hook that would shadow a standard library module or site hook on the import path")
def negative_rebinds_verifier_dependencies(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_rebinds_verifier_dependencies)


@criterion(description="the shipped documents are right while the engine produces no usable output on any minted round, so there is no engine behind the delivery")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_hardcoded_sample_answers)


@criterion(description="the engine writes one constant record whatever round it is pointed at and that constant is not the shipped round")
def negative_package_ignores_its_input(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_package_ignores_its_input)


@criterion(description="two runs of the engine over one round at one path disagree, so the figures are not reproducible")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_nondeterministic_output)


@criterion(description="the engine is reproducible at one path yet writes something else when the same round is presented under another directory name")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_filename_dependent_behaviour)


@criterion(description="the engine reached for a round sitting beside its working directory in place of the one its data option named")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    return _graded(workspace, test_negative_weight_reads_training_corpus_at_runtime)


criteria.delivered_documents_present_and_parse(weight=1)
criteria.delivered_package_shape(weight=1)
criteria.shipped_identifier_layer_exact(weight=3)
criteria.shipped_graph_layer_exact(weight=3)
criteria.shipped_closure_and_demand_exact(weight=5)
criteria.shipped_rule_and_charge_exact(weight=5)
criteria.shipped_baseline_optimum_exact(weight=5)
criteria.shipped_amendment_classification_exact(weight=3)
criteria.shipped_invalidation_sets_exact(weight=5)
criteria.shipped_work_ledger_exact(weight=5)
criteria.shipped_store_summary_exact(weight=3)
criteria.shipped_final_optimum_exact(weight=5)
criteria.shipped_audit_documents_exact(weight=3)
criteria.package_eval_state_exact(weight=5)
criteria.package_eval_cascade_exact(weight=5)
criteria.package_challenge_state_exact(weight=5)
criteria.package_challenge_cascade_exact(weight=3)
criteria.package_probe_publication_exact(weight=3)
criteria.negative_shift_length_taken_flat(weight=-5)
criteria.negative_pool_weights_taken_flat(weight=-5)
criteria.negative_deferral_rate_from_the_rescinded_sitting(weight=-5)
criteria.negative_drafting_register_read(weight=-3)
criteria.negative_capacity_boundary_read_as_strict(weight=-3)
criteria.negative_set_ranked_on_charge_alone(weight=-5)
criteria.negative_rebate_taken_before_the_surcharges(weight=-3)
criteria.negative_penalty_charged_on_every_job(weight=-3)
criteria.negative_cascade_stopped_at_the_first_hop(weight=-5)
criteria.negative_cascade_never_stopped(weight=-3)
criteria.negative_withdrawal_treated_as_inert(weight=-3)
criteria.negative_rebinds_verifier_dependencies(weight=-3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_package_ignores_its_input(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_reads_training_corpus_at_runtime(weight=-3)


def _write_corpus(dest):
    """Rebuild the shipped corpus in place.

        python3 tests/test_output.py environment

    writes the SAMPLE_SEED round into environment/data and comes out byte
    identical every time it is run.
    """
    return write_corpus(dest, SAMPLE_SEED)


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))
