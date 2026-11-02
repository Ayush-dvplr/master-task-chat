#!/usr/bin/env python3
"""Verifier for the b28ebc90-3080-5d41-9f01-e02549d3efaf bundle.

Holds the corpus generator, the reference chain for the fourteen stage
routing recompute, and the graded assertions. The verifier owns its corpus:
every case it grades is minted here from a named seed, so no graded value
depends on the directory the agent was handed.

Two grading surfaces. The documents the agent published for the shipped cycle
are compared against this file's own reference chain over a corpus reminted
from SAMPLE_SEED. The package the agent delivered is extracted and driven
over three cycles minted from seeds it has never seen.
"""
import ast
import hashlib
import io
import json
import os
import pickle
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

SAMPLE_SEED = 4471902658331025419
EVAL_SEED = 7318264095517730886
CHALLENGE_SEED = 3902551748206611973
PROBE_SEED = 5188403627794150262

NL = chr(10)
BS = chr(92)
Q = chr(34)
LT = chr(60)
GT = chr(62)
PIPE = chr(124)
TAB = chr(9)
MASK64 = 0xFFFFFFFFFFFFFFFF

OUTPUT_ROOT = "/app/out"
PACKAGE_NAME = "daybreak"


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
# exact arithmetic helpers
#
# Every published whole quantity is an integer in the unit its stage names and
# every published ratio carries exactly twelve decimal places. Rounding happens
# where a stage specification places it and nowhere else, and it is always
# round half to even.
# --------------------------------------------------------------------------
def half_even(value):
    """Round a Fraction or int to the nearest integer, halves to even."""
    frac = Fraction(value)
    floor = frac.numerator // frac.denominator
    rest = frac - floor
    if rest < Fraction(1, 2):
        return floor
    if rest > Fraction(1, 2):
        return floor + 1
    return floor if floor % 2 == 0 else floor + 1


def floor_div(num, den):
    """Floor division that keeps its sign convention explicit."""
    return num // den


def ratio12(value):
    """Twelve decimal places, half to even, no negative zero."""
    frac = Fraction(value)
    scaled = half_even(frac * 10 ** 12)
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    whole, part = divmod(scaled, 10 ** 12)
    text = sign + str(whole) + "." + str(part).rjust(12, "0")
    if text == "-0." + "0" * 12:
        text = "0." + "0" * 12
    return text


def signed(value):
    """Whole number with an explicit sign and no negative zero."""
    value = int(value)
    if value == 0:
        return "0"
    return ("+" if value > 0 else "-") + str(abs(value))


def canonical_json(obj):
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True)


def compact_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(blob):
    return hashlib.sha256(blob).hexdigest()


# --------------------------------------------------------------------------
# office and archive writers, standard library only
# --------------------------------------------------------------------------
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
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


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


def _zip_parts(path, parts):
    """Every generated archive is stored rather than deflated. Deflate output
    varies with the zlib build, so a stored archive is the only form whose
    bytes are the same on the machine that stages the corpus and in the
    container that regenerates it."""
    stamp = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
        for name, payload in parts:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_STORED
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


def with_bom(path):
    """Prefix a written file with the UTF-8 byte order mark."""
    data = Path(path).read_bytes()
    Path(path).write_bytes(b"\xef\xbb\xbf" + data)


def with_crlf(path):
    """Re-terminate every line of a written file with CR LF."""
    data = Path(path).read_bytes()
    Path(path).write_bytes(data.replace(b"\n", b"\r\n"))


def _minted_shuffle(inst, tag, rows):
    """On the minted cycles a register's rows arrive in no particular order.
    Rows sharing a key keep no promise about their relative position beyond
    what the reading rules say about file order. The sample keeps id order."""
    if inst["seed"] == SAMPLE_SEED:
        return rows
    rng = Rng(child_seed(inst["seed"], tag))
    out = list(rows)
    for i in range(len(out) - 1, 0, -1):
        j = rng.below(i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def _tied_before(rows, key_col, rev_col, key, rev, decoy):
    """Insert a decoy row sharing a key and a revision with the row in force,
    ahead of it, so only the later of the two may be read."""
    for i, row in enumerate(rows):
        if row[key_col] == key and int(row[rev_col]) == rev:
            return rows[:i] + [decoy] + rows[i:]
    raise AssertionError("no row in force for " + key)


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
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        if ln.strip():
            out.append(json.loads(ln))
    return out


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_flat_yaml(path):
    """The policy papers use one flat mapping per document, one pair per line,
    with list values written inline in square brackets."""
    out = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip() or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            out[key] = [p.strip() for p in inner.split(",") if p.strip()] if inner else []
        elif val:
            out[key] = val
    return out


def read_flat_toml(path):
    """One flat table per document, one pair per line, no nesting."""
    out = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("[") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            parts = [p.strip().strip(Q) for p in inner.split(",") if p.strip()]
            out[key] = parts
        else:
            out[key] = val.strip(Q)
    return out


def read_flat_xml(path):
    """Element name to text for a one level document, plus the attribute map
    of every repeated child under the named container."""
    root = ET.parse(str(path)).getroot()
    scalars = {}
    groups = {}
    for child in root:
        if len(child) == 0:
            scalars[child.tag] = (child.text or "").strip()
        else:
            groups[child.tag] = [dict(g.attrib) for g in child]
    return scalars, groups



# ==========================================================================
# instance minting
#
# One instance is one closed routing cycle of a household assistant. Every
# fact the reference chain needs is minted here; emit_corpus writes those
# facts into the shipped papers under the documented recording rules, and the
# router reads them back through the exact inverse of each rule.
# ==========================================================================
N_WINDOWS = 12
N_DEVICES = 16
N_CONTEXTS = 10
N_ROUTED_ACTIONS = 220
N_FALLBACK_ACTIONS = 30
N_ROUTINES = 300
N_EDGES = 280
WINDOW_REVISIONS = 18
DEVICE_REVISIONS = 14
MS_PER_MIN = 60000

ROOM_WORDS = ["atrium", "bindery", "conservatory", "dovecote", "escritoire",
              "furnace", "garret", "hallway", "inglenook", "jamb", "kitchen",
              "larder", "mudroom", "nursery", "orangery", "pantry", "quarters",
              "reading", "scullery", "terrace", "undercroft", "vestibule"]

VERB_WORDS = ["prime", "settle", "brief", "warm", "dim", "vent", "chime",
              "arm", "sweep", "log", "chill", "raise", "lower", "flush",
              "sync", "hush", "kindle", "purge", "stage", "tally"]

DEVICE_CLASSES = ["speaker", "display", "thermal", "lighting", "shutter",
                  "sensor_hub", "kettle", "vacuum"]

ACTION_CLASSES = ["announce", "regulate", "capture", "actuate", "housekeep"]

CONTEXT_NAMES = ["at_home", "away", "asleep", "guests", "focus_block",
                 "commute", "cooking", "wind_down", "maintenance", "vacation"]

DURATION_UNITS = ["ms", "s", "min", "centis", "tick", "beat"]
ENERGY_UNITS = ["mwh", "wh", "centiwh", "microwh", "kj", "j"]
WEIGHT_UNITS = ["bp", "pct", "permille", "micro"]

# token -> (base, numerator, denominator, status)
UNIT_TABLE = {
    "ms": ("ms", 1, 1, "live"),
    "s": ("ms", 1000, 1, "live"),
    "min": ("ms", 60000, 1, "live"),
    "centis": ("ms", 10, 1, "live"),
    "tick": ("ms", 125, 2, "live"),
    "beat": ("ms", 1875, 4, "live"),
    "moment": ("ms", 1, 0, "withdrawn"),
    "mwh": ("mwh", 1, 1, "live"),
    "wh": ("mwh", 1000, 1, "live"),
    "centiwh": ("mwh", 10, 1, "live"),
    "microwh": ("mwh", 1, 1000, "live"),
    "kj": ("mwh", 2500, 9, "live"),
    "j": ("mwh", 5, 18, "live"),
    "pulse": ("mwh", 1, 0, "withdrawn"),
    "bp": ("bp", 1, 1, "live"),
    "pct": ("bp", 100, 1, "live"),
    "permille": ("bp", 10, 1, "live"),
    "micro": ("bp", 1, 100, "live"),
    "grade": ("bp", 1, 0, "withdrawn"),
    "stroke": ("ms", 3, 0, "live"),
}

LEGACY_UNIT_STEMS = ["chron", "glim", "hearth", "kindle", "lumen", "murmur",
                     "notch", "orbit", "pulseline", "quill", "rime", "sable",
                     "tally", "umbra", "vesper", "wick", "yarrow", "zephyr"]

LAYER_ORDER = ["mandatory", "oneshot", "context", "device", "action",
               "routine", "global"]

POLICY_FIELDS = ["tier", "intensity", "cooldown", "mandatory",
                 "max_occurrences", "suppress", "fallback_chain"]

QUARANTINE_REASONS = ["UNCONVERTIBLE_UNIT", "OUT_OF_DAY", "IMPLAUSIBLE_DEMAND",
                      "RETIRED_ROUTINE"]

WITHHELD_REASONS = ["COOLDOWN", "SUPPRESSED",
                    "PREREQ_MISSING", "NO_FALLBACK_FITS", "DISPLACED_FINAL",
                    "GATE_CLOSED", "PREREQ_WITHDRAWN"]

STAGE_IDS = ["r01", "r02", "r03", "r04", "r05", "r06", "r07",
             "r08", "r09", "r10", "r11", "r12", "r13", "r14"]

STAGE_TITLES = {
    "r01": "unit normalisation",
    "r02": "identifier resolution",
    "r03": "routine expansion",
    "r04": "policy layer resolution",
    "r05": "initial eligibility",
    "r06": "dependency graph",
    "r07": "cycle settlement",
    "r08": "canonical order",
    "r09": "demand",
    "r10": "capacity binding",
    "r11": "fallback expansion",
    "r12": "precedence overturn",
    "r13": "state transitions",
    "r14": "feedback and publication",
}

STAGE_EDGES = [
    ("r01", "r02"), ("r01", "r03"), ("r02", "r03"), ("r01", "r04"),
    ("r02", "r04"), ("r03", "r04"), ("r04", "r05"), ("r03", "r05"),
    ("r01", "r06"), ("r02", "r06"), ("r05", "r07"), ("r06", "r07"),
    ("r07", "r08"), ("r05", "r08"), ("r04", "r09"), ("r08", "r09"),
    ("r09", "r10"), ("r04", "r10"), ("r10", "r11"), ("r11", "r12"),
    ("r12", "r13"), ("r13", "r14"), ("r05", "r14"), ("r10", "r14"),
]


def _profile_of(seed):
    return "weekday" if child_seed(seed, "profile") % 2 == 0 else "weekend"


def _cycle_label(seed):
    rng = Rng(child_seed(seed, "cycle"))
    return ("HB-" + str(rng.between(2029, 2043)) + "-"
            + str(rng.between(101, 364)).rjust(3, "0"))


def _hist(base, drift, n_rev, rng):
    """A revision history for one recorded quantity. Exactly one revision is
    in force; the rest record what the value used to be."""
    out = []
    value = base
    for rev in range(1, n_rev + 1):
        out.append((rev, value))
        value = value + rng.between(-drift, drift)
        if value < 1:
            value = 1
    return out


def mint(seed):
    """Every fact of one routing cycle, before any recording rule is applied."""
    inst = {"seed": int(seed), "cycle": _cycle_label(seed),
            "profile": _profile_of(seed)}
    rng = Rng(child_seed(seed, "grid"))

    # ---- windows -------------------------------------------------------
    windows = []
    # the day opens after a non-zero origin; every chain starts there
    origin = Rng(child_seed(seed, "origin")).between(18, 42) * MS_PER_MIN
    inst["origin_ms"] = origin
    cursor = origin
    for i in range(1, N_WINDOWS + 1):
        span = rng.between(90, 150) * MS_PER_MIN
        windows.append({
            "wid": "W" + str(i).rjust(2, "0"),
            "ordinal": i,
            "start_ms": cursor,
            "end_ms": cursor + span,
            "span_ms": span,
            "capacity_class": rng.pick(["quiet", "standard", "peak"]),
            "frozen_rev": rng.between(6, WINDOW_REVISIONS),
        })
        cursor += span
    # W01, W02, W07, W08 and W09 are frozen at the grid wide revision; the
    # others are frozen strictly below it, so a reader that applies the grid
    # wide revision to every window reads later rows for W03-W06, W10-W12
    top = Rng(child_seed(seed, "frozen_top")).between(15, WINDOW_REVISIONS)
    low = Rng(child_seed(seed, "frozen_low"))
    for w in windows:
        if w["ordinal"] in (1, 2, 7, 8, 9):
            w["frozen_rev"] = top
        else:
            w["frozen_rev"] = low.between(6, top - 2)
    # W02 runs on past the start of W03: the two overlap, and a trigger on
    # the end of W02 lies inside W03 only
    windows[1]["span_ms"] += 20 * MS_PER_MIN
    windows[1]["end_ms"] += 20 * MS_PER_MIN
    inst["windows"] = windows
    inst["day_end_ms"] = cursor

    # ---- devices -------------------------------------------------------
    rng = Rng(child_seed(seed, "devices"))
    devices = []
    for i in range(1, N_DEVICES + 1):
        devices.append({
            "did": "DV-" + str(i).rjust(2, "0"),
            "cls": DEVICE_CLASSES[(i - 1) % len(DEVICE_CLASSES)],
            "slots": rng.between(1, 4),
            "frozen_rev": rng.between(5, DEVICE_REVISIONS),
        })
    inst["devices"] = devices

    # ---- per window per device energy ceilings (workbook only) ----------
    rng = Rng(child_seed(seed, "ceilings"))
    live = {}
    stale = {}
    for w in windows:
        for d in devices:
            base = rng.between(2, 15) * 1000 + rng.between(0, 999)
            if rng.chance(1, 26):
                base = 0
            live[(w["wid"], d["did"])] = base
            stale[(w["wid"], d["did"])] = base + rng.between(-1400, 1400)
    inst["ceiling_live"] = live
    inst["ceiling_stale"] = stale

    # ---- contexts ------------------------------------------------------
    rng = Rng(child_seed(seed, "contexts"))
    contexts = []
    for i, name in enumerate(CONTEXT_NAMES, start=1):
        start = rng.between(0, 10) * 60 * MS_PER_MIN
        span = rng.between(2, 9) * 60 * MS_PER_MIN
        contexts.append({
            "cid": "CX-" + str(i).rjust(2, "0"),
            "name": name,
            "start_ms": start,
            "end_ms": min(start + span, inst["day_end_ms"]),
        })
    # one context is active for exactly one boundary instant
    contexts[4]["start_ms"] = windows[5]["start_ms"]
    contexts[4]["end_ms"] = windows[5]["start_ms"]
    inst["contexts"] = contexts

    # ---- actions -------------------------------------------------------
    rng = Rng(child_seed(seed, "actions"))
    actions = []
    total = N_ROUTED_ACTIONS + N_FALLBACK_ACTIONS
    for i in range(1, total + 1):
        aid = "AC-" + str(i).rjust(3, "0")
        energy = rng.between(60, 8400)
        if i % 47 == 0:
            energy = 0
        actions.append({
            "aid": aid,
            "name": (rng.pick(VERB_WORDS) + "_" + rng.pick(ROOM_WORDS)
                     + "_" + str(i).rjust(3, "0")),
            "device": devices[rng.below(N_DEVICES)]["did"],
            "context": contexts[rng.below(N_CONTEXTS)]["cid"],
            "energy_mwh": energy,
            "duration_ms": rng.between(2, 900) * 1000,
            "cls": ACTION_CLASSES[(i - 1) % len(ACTION_CLASSES)],
            "seq": i,
            "routed": i <= N_ROUTED_ACTIONS,
            "energy_unit": ENERGY_UNITS[rng.below(len(ENERGY_UNITS))],
            "duration_unit": DURATION_UNITS[rng.below(len(DURATION_UNITS))],
        })
    # two catalogue rows carry a withdrawn unit token
    actions[13]["energy_unit"] = "pulse"
    actions[97]["duration_unit"] = "moment"
    inst["actions"] = actions
    by_aid = {a["aid"]: a for a in actions}
    inst["by_aid"] = by_aid

    # ---- routines ------------------------------------------------------
    rng = Rng(child_seed(seed, "routines"))
    routines = []
    for i in range(1, N_ROUTINES + 1):
        rid = "RT-" + str(i).rjust(3, "0")
        target = actions[(i - 1) % N_ROUTED_ACTIONS]
        anchor = rng.between(0, 1400) * MS_PER_MIN
        period = rng.pick([0, 45, 60, 75, 90, 120, 150, 180, 240]) * MS_PER_MIN
        span_start = rng.between(0, 4) * 60 * MS_PER_MIN
        span_end = min(inst["day_end_ms"], span_start
                       + rng.between(3, 22) * 60 * MS_PER_MIN)
        routines.append({
            "rid": rid,
            "aid": target["aid"],
            "anchor_ms": anchor,
            "period_ms": period,
            "span_start_ms": span_start,
            "span_end_ms": span_end,
            "enabled": not rng.chance(1, 23),
            "seq": i,
        })
    # boundary fixtures: an anchor exactly on a window start, one exactly on a
    # window end, one whose last occurrence lands exactly on the span end, and
    # one routine that reaches past the last window.
    routines[3]["anchor_ms"] = windows[2]["start_ms"]
    routines[3]["period_ms"] = 0
    routines[3]["span_start_ms"] = 0
    routines[3]["span_end_ms"] = inst["day_end_ms"]
    routines[9]["anchor_ms"] = windows[4]["end_ms"]
    routines[9]["period_ms"] = 0
    routines[9]["span_start_ms"] = 0
    routines[9]["span_end_ms"] = inst["day_end_ms"]
    routines[17]["anchor_ms"] = windows[1]["start_ms"]
    routines[17]["period_ms"] = 60 * MS_PER_MIN
    routines[17]["span_start_ms"] = windows[1]["start_ms"]
    routines[17]["span_end_ms"] = windows[1]["start_ms"] + 180 * MS_PER_MIN
    routines[33]["anchor_ms"] = windows[1]["end_ms"]
    routines[33]["period_ms"] = 0
    routines[33]["span_start_ms"] = 0
    routines[33]["span_end_ms"] = inst["day_end_ms"]
    routines[33]["enabled"] = True
    routines[25]["anchor_ms"] = inst["day_end_ms"]
    routines[25]["period_ms"] = 0
    routines[25]["span_start_ms"] = 0
    routines[25]["span_end_ms"] = inst["day_end_ms"] + 60 * MS_PER_MIN
    inst["routines"] = routines

    # ---- dependency edges ----------------------------------------------
    rng = Rng(child_seed(seed, "edges"))
    edges = []
    seq = 0
    for _ in range(N_EDGES - 24):
        seq += 1
        a = rng.below(N_ROUTED_ACTIONS)
        b = rng.below(N_ROUTED_ACTIONS)
        edges.append({"seq": seq, "prereq": actions[a]["aid"],
                      "dependent": actions[b]["aid"],
                      "strength_bp": rng.between(50, 9800),
                      "kind": "hard" if rng.chance(1, 5)
                      else rng.pick(["soft", "advisory"])})
    # a two cycle, a four cycle, two cycles sharing one node, a self edge,
    # a duplicate pair, and a cycle whose edges all carry equal strength
    def add(prereq, dependent, strength, kind="hard"):
        nonlocal seq
        seq += 1
        edges.append({"seq": seq, "prereq": prereq, "dependent": dependent,
                      "strength_bp": strength, "kind": kind})

    add("AC-011", "AC-012", 4200)
    add("AC-012", "AC-011", 3100)
    add("AC-031", "AC-032", 2600)
    add("AC-032", "AC-033", 2600)
    add("AC-033", "AC-034", 2600)
    add("AC-034", "AC-031", 2600)
    add("AC-051", "AC-052", 700)
    add("AC-052", "AC-051", 5500)
    add("AC-052", "AC-053", 900)
    add("AC-053", "AC-051", 6100)
    add("AC-071", "AC-071", 1200)
    add("AC-081", "AC-082", 3300)
    add("AC-081", "AC-082", 7700)
    add("AC-091", "AC-092", 1500, "soft")
    add("AC-092", "AC-093", 1500, "soft")
    add("AC-093", "AC-091", 1500, "soft")
    add("AC-101", "AC-102", 8800)
    add("AC-102", "AC-103", 400)
    add("AC-103", "AC-104", 8800)
    add("AC-104", "AC-101", 8800)
    add("AC-121", "AC-122", 2000)
    add("AC-122", "AC-121", 2000)
    add("AC-141", "AC-142", 6400)
    add("AC-142", "AC-141", 6400)
    inst["edges"] = edges

    # ---- policy layers --------------------------------------------------
    rng = Rng(child_seed(seed, "policy"))
    inst["global_layer"] = {
        "tier": 6,
        "intensity_bp": 10000,
        "cooldown_ms": 45 * MS_PER_MIN,
        "mandatory": False,
        "max_occurrences": 4,
        "suppress": False,
        "fallback_chain": [],
    }
    routine_layer = {}
    for r in routines:
        rec = {}
        if rng.chance(1, 2):
            rec["tier"] = rng.between(3, 8)
        if rng.chance(1, 3):
            rec["intensity_bp"] = rng.between(4000, 16000)
        if rng.chance(1, 3):
            rec["cooldown_ms"] = rng.between(0, 200) * MS_PER_MIN
        if rng.chance(1, 9):
            rec["max_occurrences"] = rng.between(0, 6)
        routine_layer[r["rid"]] = rec
    inst["routine_layer"] = routine_layer

    action_layer = {}
    for a in actions:
        rec = {}
        if not a["routed"]:
            rec["tier"] = rng.between(1, 3)
        elif rng.chance(2, 3):
            rec["tier"] = rng.between(2, 9)
        if rng.chance(1, 2):
            rec["intensity_bp"] = rng.between(3000, 18000)
        if rng.chance(1, 4):
            rec["cooldown_ms"] = rng.between(0, 420) * MS_PER_MIN
        if rng.chance(1, 6):
            rec["suppress"] = True
        if rng.chance(1, 2):
            depth = rng.between(1, 3)
            chain = []
            for _k in range(depth):
                pick = actions[N_ROUTED_ACTIONS + rng.below(N_FALLBACK_ACTIONS)]
                if pick["aid"] not in chain:
                    chain.append(pick["aid"])
            rec["fallback_chain"] = chain
        action_layer[a["aid"]] = rec
    inst["action_layer"] = action_layer

    device_layer = {}
    for d in devices:
        rec = {}
        if rng.chance(3, 4):
            rec["tier"] = rng.between(2, 7)
        if rng.chance(1, 2):
            rec["intensity_bp"] = rng.between(6000, 14000)
        if rng.chance(1, 3):
            rec["cooldown_ms"] = rng.between(0, 120) * MS_PER_MIN
        device_layer[d["did"]] = rec
    inst["device_layer"] = device_layer

    context_layer = {}
    for c in contexts:
        rec = {}
        if rng.chance(4, 5):
            rec["tier"] = rng.between(1, 6)
        if rng.chance(1, 2):
            rec["intensity_bp"] = rng.between(5000, 20000)
        if rng.chance(1, 4):
            rec["suppress"] = True
        context_layer[c["cid"]] = rec
    inst["context_layer"] = context_layer

    # one shot overrides
    overrides = []
    for i in range(1, 49):
        a = actions[rng.below(N_ROUTED_ACTIONS)]
        rec = {"override_id": "OV-" + str(i).rjust(3, "0"), "action": a["aid"],
               "remaining": rng.between(0, 2),
               "expires_ms": rng.between(2, 24) * 60 * MS_PER_MIN}
        if rng.chance(3, 4):
            rec["tier"] = rng.between(1, 4)
        if rng.chance(1, 2):
            rec["intensity_bp"] = rng.between(9000, 22000)
        if rng.chance(1, 3):
            rec["cooldown_ms"] = 0
        overrides.append(rec)
    # an override whose expiry lands exactly on a window boundary
    overrides[6]["expires_ms"] = windows[7]["start_ms"]
    inst["overrides"] = overrides

    # mandatory directives, layer one, published in the directive
    mandates = []
    for i in range(1, 211):
        a = actions[rng.below(total)]
        mandates.append({"seq": i, "action": a["aid"],
                         "window": windows[rng.below(N_WINDOWS)]["wid"],
                         "mandatory": rng.chance(2, 5),
                         "tier": rng.between(1, 3)})
    inst["mandates"] = mandates

    # ---- prior state ----------------------------------------------------
    rng = Rng(child_seed(seed, "state"))
    snapshot = {}
    for a in actions:
        rec = {}
        if rng.chance(3, 5):
            rec["last_fired_ms"] = -rng.between(0, 80) * MS_PER_MIN
        if rng.chance(1, 6):
            rec["suppressed_until_ms"] = rng.between(0, 900) * MS_PER_MIN
        snapshot[a["aid"]] = rec
    inst["snapshot"] = snapshot
    # the cooldown register is frozen in the snapshot, never at the window
    # grid revision recorded in the cycle header
    inst["cooldown_frozen"] = Rng(child_seed(seed, "cooldown_frozen")).between(4, 9)

    prior = []
    for i in range(1, 221):
        a = actions[rng.below(total)]
        prior.append({"cycle_index": rng.between(1, 3), "action": a["aid"],
                      "carried_cooldown_ms": rng.between(0, 180) * MS_PER_MIN,
                      "fired_ms": -rng.between(0, 600) * MS_PER_MIN})
    inst["prior_runs"] = prior

    effects = []
    for i in range(1, 73):
        a = actions[rng.below(N_ROUTED_ACTIONS)]
        effects.append({"seq": i, "action": a["aid"],
                        "key": "flag_" + str(rng.between(1, 18)).rjust(2, "0"),
                        "value": rng.pick(["on", "off"])})
    inst["effects"] = effects

    gates = []
    used = set()
    for i in range(1, 45):
        a = actions[rng.below(total)]
        if a["aid"] in used:
            continue
        used.add(a["aid"])
        gates.append({"action": a["aid"],
                      "key": "flag_" + str(rng.between(1, 18)).rjust(2, "0"),
                      "requires": rng.pick(["on", "off"])})
    # readmission fixtures. A gate sits on an action the action layer
    # suppresses and its key is written by an action the layer does not.
    suppressed = [a["aid"] for a in actions
                  if action_layer[a["aid"]].get("suppress")]
    setters = [a["aid"] for a in actions[:N_ROUTED_ACTIONS]
               if not action_layer[a["aid"]].get("suppress")]
    for i, aid in enumerate(suppressed[:40]):
        key = "gate_" + str(i).rjust(2, "0")
        gates = [g for g in gates if g["action"] != aid]
        gates.append({"action": aid, "key": key, "requires": "on"})
        effects.append({"seq": 500 + i,
                        "action": setters[(i * 7) % len(setters)],
                        "key": key, "value": "on"})
    inst["effects"] = effects
    inst["gates"] = gates

    # ---- scalar controls -------------------------------------------------
    rng = Rng(child_seed(seed, "controls"))
    inst["controls"] = {
        "implausible_demand_mwh": rng.between(9000, 13000),
        "fallback_chain_depth_cap": rng.between(2, 3),
        "default_max_occurrences": 4,
        "alias_hop_cap": 8,
        "reserve_bp": rng.between(400, 1800),
        "surcharge_bp": {cls: rng.between(-800, 1600) for cls in ACTION_CLASSES},
        "capacity_class_bp": {"quiet": rng.between(6000, 9000),
                              "standard": 10000,
                              "peak": rng.between(11000, 14000)},
    }

    # the directive's own figures: the ranks of the three middle layers and
    # the reconciliation round cap differ from every other paper's habit
    drng = Rng(child_seed(seed, "directive"))
    middle = ["device", "action", "routine"]
    if seed == SAMPLE_SEED:
        order = ["action", "device", "routine"]
    else:
        order = list(middle)
        while order == middle:
            order = list(middle)
            for k in range(len(order) - 1, 0, -1):
                j = drng.below(k + 1)
                order[k], order[j] = order[j], order[k]
    ranks = {"mandatory": 1, "oneshot": 2, "context": 3, "global": 7}
    for k, name in enumerate(order):
        ranks[name] = 4 + k
    inst["layer_ranks"] = ranks
    inst["round_cap"] = 3 if seed == SAMPLE_SEED else drng.between(4, 5)

    # per routine occurrence caps published only in the memo
    caps = {}
    for r in routines:
        caps[r["rid"]] = rng.between(1, 5) if rng.chance(2, 3) else None
    inst["memo_caps"] = caps

    # ---- aliases ---------------------------------------------------------
    rng = Rng(child_seed(seed, "alias"))
    primary = []
    supplement = []
    for i, a in enumerate(actions, start=1):
        primary.append({"alias": "legacy." + a["name"], "canonical": a["aid"],
                        "kind": "action", "seq": i})
    for d in devices:
        primary.append({"alias": "dev." + d["cls"] + "." + d["did"][-2:],
                        "canonical": d["did"], "kind": "device",
                        "seq": len(primary) + 1})
    for c in contexts:
        primary.append({"alias": "ctx." + c["name"], "canonical": c["cid"],
                        "kind": "context", "seq": len(primary) + 1})
    # a two hop chain, a self alias, and a two node alias cycle
    primary.append({"alias": "hop.one", "canonical": "hop.two",
                    "kind": "action", "seq": len(primary) + 1})
    primary.append({"alias": "hop.two", "canonical": "AC-007",
                    "kind": "action", "seq": len(primary) + 1})
    primary.append({"alias": "AC-009", "canonical": "AC-009",
                    "kind": "action", "seq": len(primary) + 1})
    primary.append({"alias": "loop.a", "canonical": "loop.b",
                    "kind": "action", "seq": len(primary) + 1})
    primary.append({"alias": "loop.b", "canonical": "loop.a",
                    "kind": "action", "seq": len(primary) + 1})
    # two alias rings: one exactly as long as the hop cap, which closes on
    # the hop that reaches the cap, and one a hop longer, which never closes
    # inside the cap
    cap = inst["controls"]["alias_hop_cap"]
    for ring, size in (("ring.a", cap), ("ring.b", cap + 1)):
        for k in range(1, size + 1):
            primary.append({"alias": ring + str(k),
                            "canonical": ring + str(k % size + 1),
                            "kind": "action", "seq": len(primary) + 1})
    for i in range(1, 61):
        a = actions[rng.below(total)]
        supplement.append({"alias": "legacy." + a["name"], "canonical":
                           actions[rng.below(total)]["aid"],
                           "kind": "action", "seq": i})
    for i in range(1, 41):
        a = actions[rng.below(total)]
        supplement.append({"alias": "old." + a["name"], "canonical": a["aid"],
                           "kind": "action", "seq": 60 + i})
    inst["alias_primary"] = primary
    inst["alias_supplement"] = supplement

    # references written into the catalogue as aliases rather than ids
    rng = Rng(child_seed(seed, "refs"))
    for a in actions:
        a["device_ref"] = a["device"]
        a["context_ref"] = a["context"]
        if rng.chance(1, 3):
            dev = next(d for d in devices if d["did"] == a["device"])
            a["device_ref"] = "dev." + dev["cls"] + "." + dev["did"][-2:]
        if rng.chance(1, 4):
            ctx = next(c for c in contexts if c["cid"] == a["context"])
            a["context_ref"] = "ctx." + ctx["name"]
    for r in routines:
        r["action_ref"] = r["aid"]
        if rng.chance(1, 3):
            r["action_ref"] = "legacy." + by_aid[r["aid"]]["name"]
    for e in edges:
        e["prereq_ref"] = e["prereq"]
        e["dependent_ref"] = e["dependent"]
        if rng.chance(1, 4):
            e["prereq_ref"] = "legacy." + by_aid[e["prereq"]]["name"]
        if rng.chance(1, 5):
            e["dependent_ref"] = "legacy." + by_aid[e["dependent"]]["name"]
    _fixtures(inst)
    return inst


def _boundary_fixtures(inst, far_past):
    """Equality fixtures. Each one lands two instants exactly on top of each
    other where a stage specification states which side of the boundary
    wins, so the inclusive and the exclusive reading publish different plans.

    - r05: a cooldown elapses exactly at the trigger (equality is eligible).
    - r08 and r14: a hard prerequisite fires at the same instant as its
      dependent (at or before satisfies it).
    - r14: a gate key is written at the same instant as the gated trigger
      (only a write strictly before closes the gate).
    - r14: a readmission key is written at the same instant as the withheld
      trigger (only a write strictly before readmits)."""
    windows = inst["windows"]
    by_aid = inst["by_aid"]
    routines = inst["routines"]
    names = ["AC-161", "AC-162", "AC-163", "AC-164", "AC-165", "AC-166",
             "AC-167"]
    slots = {aid: 160 + i for i, aid in enumerate(names)}
    cool = 600 * MS_PER_MIN
    t_cool = windows[1]["start_ms"] + 25 * MS_PER_MIN
    t_pre = windows[2]["start_ms"] + 35 * MS_PER_MIN
    t_gate = windows[4]["start_ms"] + 20 * MS_PER_MIN
    t_readmit = windows[6]["start_ms"] + 40 * MS_PER_MIN
    when = {"AC-161": t_cool, "AC-162": t_pre, "AC-163": t_pre,
            "AC-164": t_gate, "AC-165": t_gate, "AC-166": t_readmit,
            "AC-167": t_readmit}
    fixed = set(names)
    own = {slots[aid] for aid in names}
    for i, r in enumerate(routines):
        if i not in own and r["aid"] in fixed:
            r["enabled"] = False
    for aid in names:
        act = by_aid[aid]
        act["energy_mwh"] = 0
        if act["device"] == "DV-09":
            act["device"] = "DV-02"
            act["device_ref"] = "DV-02"
        act["context"] = inst["contexts"][4]["cid"]
        act["context_ref"] = inst["contexts"][4]["cid"]
        inst["action_layer"][aid].pop("suppress", None)
        inst["snapshot"][aid] = {"last_fired_ms": far_past}
        routines[slots[aid]].update({
            "aid": aid, "action_ref": aid, "anchor_ms": when[aid],
            "period_ms": 0, "span_start_ms": 0,
            "span_end_ms": inst["day_end_ms"], "enabled": True})
        inst["memo_caps"][routines[slots[aid]]["rid"]] = 1
    inst["mandates"] = [m for m in inst["mandates"]
                        if m["action"] not in fixed]
    inst["overrides"] = [o for o in inst["overrides"]
                         if o["action"] not in fixed]
    inst["prior_runs"] = [p for p in inst["prior_runs"]
                          if p["action"] not in fixed]
    inst["edges"] = [e for e in inst["edges"]
                     if e["dependent"] not in fixed
                     and e["prereq"] not in fixed]
    inst["effects"] = [e for e in inst["effects"] if e["action"] not in fixed]
    inst["gates"] = [g for g in inst["gates"] if g["action"] not in fixed]

    # r05: the one shot layer settles a ten hour cooldown, and the snapshot
    # records the last firing exactly ten hours before the trigger.
    inst["overrides"].append({"override_id": "OV-901", "action": "AC-161",
                              "remaining": 1,
                              "expires_ms": inst["day_end_ms"],
                              "tier": 3, "intensity_bp": 10000,
                              "cooldown_ms": cool})
    inst["snapshot_oneshot"]["OV-901"] = 1
    inst["snapshot"]["AC-161"] = {"last_fired_ms": t_cool - cool}

    # r08 and r14: AC-163 is the only hard prerequisite of AC-162 and fires
    # at the same instant.
    seq = max(e["seq"] for e in inst["edges"]) + 1
    inst["edges"].append({"seq": seq, "prereq": "AC-163",
                          "dependent": "AC-162", "prereq_ref": "AC-163",
                          "dependent_ref": "AC-162", "strength_bp": 4700,
                          "kind": "hard"})

    # r14: AC-165 writes the gate key of AC-164 to the wrong value at the
    # gated trigger itself.
    inst["gates"].append({"action": "AC-164", "key": "gate_40",
                          "requires": "on"})
    inst["effects"].append({"seq": 901, "action": "AC-165",
                            "key": "gate_40", "value": "off"})

    # r14: AC-166 is withheld as suppressed, and AC-167 writes its key to
    # the required value at the withheld trigger itself.
    inst["snapshot"]["AC-166"] = {"last_fired_ms": far_past,
                                  "suppressed_until_ms": inst["day_end_ms"]}
    inst["gates"].append({"action": "AC-166", "key": "gate_41",
                          "requires": "on"})
    inst["effects"].append({"seq": 902, "action": "AC-167",
                            "key": "gate_41", "value": "on"})


def _fixture_demand(inst, aid, window, intensity_bp, energy):
    """Stage r09 arithmetic for one fixture instance."""
    ctl = inst["controls"]
    cls = inst["by_aid"][aid]["cls"]
    intensity = intensity_bp + ctl["surcharge_bp"][cls]
    if intensity < 0:
        intensity = 0
    scale = ctl["capacity_class_bp"].get(window["capacity_class"], 10000)
    first = half_even(Fraction(energy * intensity, 10000))
    return half_even(Fraction(first * scale, 10000))


def _fixture_energy(inst, aid, window, lo, hi):
    """The least base energy whose demand lands in [lo, hi]."""
    energy = 0
    while _fixture_demand(inst, aid, window, 10000, energy) < lo:
        energy += 1
    assert _fixture_demand(inst, aid, window, 10000, energy) <= hi
    return energy


def _relay_fixtures(inst, far_past):
    """Chained fixtures. Each one makes a later stage depend on a rule two or
    more stages upstream, on one device the rest of the household never uses.

    - r10 -> r11 -> r12 -> r13 -> r14: an instance displaced in r10 proposes
      a fallback in r11; r12 keeps the fallback and overturns the incumbent
      only when incumbents and proposals compete for the same pool. The
      fallback writes a gate key the overturned incumbent would have written
      the other way, so the r14 readmission of a suppressed instance (and its
      next state cooldown) depends on the r12 candidate set. The readmitted
      demand fits the pool only when each kept proposal is drawn once.
    - r13 -> r14 -> next state: an instance consuming a one-shot override is
      withdrawn by its gate in r14, so the one-shot count published in the
      next state differs between the r13 and the second pass consumption.
    - r05 -> r07: a two edge cycle of equal strength whose dependents share
      their least eligible tier settles on declared sequence; an earlier
      instance under cooldown carries a lower tier that must not count.
    - r07: nine actions every pair of which depends on each other both ways,
      a dense dependency knot that takes dozens of settlement rounds."""
    windows = inst["windows"]
    by_aid = inst["by_aid"]
    routines = inst["routines"]
    device = "DV-16"
    spare = "DV-15"
    relay = ["AC-171", "AC-172", "AC-173", "AC-174", "AC-175", "AC-177",
             "AC-178"]
    knot = ["AC-18" + str(k) for k in range(1, 10)]
    fixed = set(relay) | set(knot)
    extra_slot = 290
    for a in inst["actions"]:
        if a["aid"] not in fixed and a["device"] == device:
            a["device"] = spare
            a["device_ref"] = spare
    inst["device_layer"][device] = {}
    for d in inst["devices"]:
        if d["did"] == device and d["frozen_rev"] > 13:
            d["frozen_rev"] = 13
    for i, r in enumerate(routines):
        if r["aid"] in fixed:
            r["enabled"] = False
    inst["mandates"] = [m for m in inst["mandates"] if m["action"] not in fixed]
    inst["overrides"] = [o for o in inst["overrides"]
                         if o["action"] not in fixed]
    inst["prior_runs"] = [p for p in inst["prior_runs"]
                          if p["action"] not in fixed]
    inst["edges"] = [e for e in inst["edges"]
                     if e["dependent"] not in fixed and e["prereq"] not in fixed]
    inst["effects"] = [e for e in inst["effects"] if e["action"] not in fixed]
    inst["gates"] = [g for g in inst["gates"] if g["action"] not in fixed]
    for aid in fixed:
        act = by_aid[aid]
        act["device"] = device
        act["device_ref"] = device
        act["context"] = inst["contexts"][4]["cid"]
        act["context_ref"] = inst["contexts"][4]["cid"]
        act["energy_mwh"] = 0
        inst["action_layer"][aid] = {"intensity_bp": 10000}
        inst["snapshot"][aid] = {"last_fired_ms": far_past}

    def place(aid, slot, anchor, tier=None):
        r = routines[slot]
        r.update({"aid": aid, "action_ref": aid, "anchor_ms": anchor,
                  "period_ms": 0, "span_start_ms": 0,
                  "span_end_ms": inst["day_end_ms"], "enabled": True})
        inst["memo_caps"][r["rid"]] = 1
        inst["routine_layer"][r["rid"]] = {} if tier is None else {"tier": tier}

    # the relay group
    w9 = windows[8]
    w10 = windows[9]
    ceiling = 5000
    inst["ceiling_live"][(w9["wid"], device)] = ceiling
    inst["ceiling_stale"][(w9["wid"], device)] = ceiling + 1300
    inst["ceiling_live"][(w10["wid"], device)] = ceiling
    inst["ceiling_stale"][(w10["wid"], device)] = ceiling - 1100
    reserve = half_even(Fraction(ceiling * inst["controls"]["reserve_bp"],
                                 10000))
    pool = ceiling - reserve
    t_disp = w9["start_ms"] + 10 * MS_PER_MIN
    t_inc = w9["start_ms"] + 30 * MS_PER_MIN
    t_sup = w9["start_ms"] + 50 * MS_PER_MIN
    tiers = {"AC-171": 3, "AC-172": 5, "AC-173": 2, "AC-174": 4, "AC-175": 4}
    for aid, tier in tiers.items():
        inst["action_layer"][aid]["tier"] = tier
    shares = {"AC-171": (pool + 40, pool + 90),
              "AC-172": (pool * 60 // 100, pool * 62 // 100),
              "AC-173": (pool * 45 // 100, pool * 47 // 100),
              "AC-174": (pool * 28 // 100, pool * 30 // 100)}
    for aid, (lo, hi) in shares.items():
        by_aid[aid]["energy_mwh"] = _fixture_energy(inst, aid, w9, lo, hi)
    inst["action_layer"]["AC-171"]["fallback_chain"] = ["AC-173"]
    place("AC-171", 170, t_disp)
    place("AC-172", 171, t_inc)
    place("AC-174", 173, t_sup)
    inst["snapshot"]["AC-174"] = {"last_fired_ms": far_past,
                                  "suppressed_until_ms": inst["day_end_ms"]}
    inst["effects"].append({"seq": 903, "action": "AC-173",
                            "key": "gate_42", "value": "on"})
    inst["effects"].append({"seq": 904, "action": "AC-172",
                            "key": "gate_42", "value": "off"})
    inst["gates"].append({"action": "AC-174", "key": "gate_42",
                          "requires": "on"})

    # the one shot spent in r13 and given back in r14
    place("AC-175", 174, w10["start_ms"] + 15 * MS_PER_MIN)
    inst["gates"].append({"action": "AC-175", "key": "gate_42",
                          "requires": "off"})
    inst["overrides"].append({"override_id": "OV-902", "action": "AC-175",
                              "remaining": 1,
                              "expires_ms": inst["day_end_ms"],
                              "tier": 4, "intensity_bp": 10000,
                              "cooldown_ms": 0})
    inst["snapshot_oneshot"]["OV-902"] = 1

    # the equal strength, equal tier cycle
    t_early = windows[3]["start_ms"] + 5 * MS_PER_MIN
    place("AC-177", 176, w10["start_ms"] + 20 * MS_PER_MIN, tier=5)
    place("AC-178", 177, w10["start_ms"] + 5 * MS_PER_MIN, tier=5)
    place("AC-178", extra_slot, t_early, tier=2)
    inst["snapshot"]["AC-178"] = {"last_fired_ms": t_early - MS_PER_MIN}
    seq = max(e["seq"] for e in inst["edges"]) + 1

    def edge(pre, dep, strength, kind="soft"):
        nonlocal seq
        inst["edges"].append({"seq": seq, "prereq": pre, "dependent": dep,
                              "prereq_ref": pre, "dependent_ref": dep,
                              "strength_bp": strength, "kind": kind})
        seq += 1
    edge("AC-178", "AC-177", 3300)
    edge("AC-177", "AC-178", 3300)

    # the dense knot
    idx = 0
    for a in knot:
        for b in knot:
            if a == b:
                continue
            edge(a, b, 1200 + ((idx * 29) % 72) * 100)
            idx += 1


def _depth_fixtures(inst, far_past):
    """Fixtures that give the later stages more than one deciding case, on
    the device the relay fixtures already cleared.

    - r11 -> r12: a displaced instance whose fallback overturns an
      incumbent, whose own fallback overturns the next, and so on. Every
      further round publishes a different plan, so the round cap binds.
    - r14: three withheld instances share one gate key and one pool. The
      first and the third are readmitted; the second no longer fits once
      the first has drawn.
    - r07: two cycles whose edges tie on strength, on the dependent's tier
      and on declared sequence, so the last key settles them.
    - r05 -> r07: two cycles of equal strength where the tier of a
      dependent read over every instance, rather than over its eligible
      instances, removes another edge."""
    windows = inst["windows"]
    by_aid = inst["by_aid"]
    routines = inst["routines"]
    device = "DV-16"
    cascade = ["AC-19" + str(k) for k in range(1, 9)]
    readmit = ["AC-201", "AC-202", "AC-203", "AC-204"]
    settle = ["AC-205", "AC-206", "AC-207", "AC-208", "AC-209"]
    eligible = ["AC-211", "AC-212", "AC-213", "AC-214", "AC-215"]
    fixed = set(cascade) | set(readmit) | set(settle) | set(eligible)
    extra_slot = 291
    for r in routines:
        if r["aid"] in fixed:
            r["enabled"] = False
    inst["mandates"] = [m for m in inst["mandates"] if m["action"] not in fixed]
    inst["overrides"] = [o for o in inst["overrides"]
                         if o["action"] not in fixed]
    inst["prior_runs"] = [p for p in inst["prior_runs"]
                          if p["action"] not in fixed]
    inst["edges"] = [e for e in inst["edges"]
                     if e["dependent"] not in fixed and e["prereq"] not in fixed]
    inst["effects"] = [e for e in inst["effects"] if e["action"] not in fixed]
    inst["gates"] = [g for g in inst["gates"] if g["action"] not in fixed]
    for a in inst["actions"]:
        if a["aid"] not in fixed:
            chain = inst["action_layer"].get(a["aid"], {}).get("fallback_chain")
            if chain and any(c in fixed for c in chain):
                inst["action_layer"][a["aid"]]["fallback_chain"] = [
                    c for c in chain if c not in fixed]
    for aid in fixed:
        act = by_aid[aid]
        act["device"] = device
        act["device_ref"] = device
        act["context"] = inst["contexts"][4]["cid"]
        act["context_ref"] = inst["contexts"][4]["cid"]
        act["energy_mwh"] = 0
        inst["action_layer"][aid] = {"intensity_bp": 10000}
        inst["snapshot"][aid] = {"last_fired_ms": far_past}

    def place(aid, slot, anchor, tier=None):
        r = routines[slot]
        r.update({"aid": aid, "action_ref": aid, "anchor_ms": anchor,
                  "period_ms": 0, "span_start_ms": 0,
                  "span_end_ms": inst["day_end_ms"], "enabled": True})
        inst["memo_caps"][r["rid"]] = 1
        inst["routine_layer"][r["rid"]] = {} if tier is None else {"tier": tier}

    def slot_of(aid):
        return int(aid[3:]) - 1

    ceiling = 5000
    reserve = half_even(Fraction(ceiling * inst["controls"]["reserve_bp"],
                                 10000))
    pool = ceiling - reserve

    # the cascade
    w11 = windows[10]
    inst["ceiling_live"][(w11["wid"], device)] = ceiling
    inst["ceiling_stale"][(w11["wid"], device)] = ceiling + 900
    head, inc, alt = cascade[0], cascade[1:4], cascade[4:8]
    tiers = {head: 3, inc[0]: 2, inc[1]: 3, inc[2]: 4}
    for aid in alt:
        tiers[aid] = 1
    for aid, tier in tiers.items():
        inst["action_layer"][aid]["tier"] = tier
    by_aid[head]["energy_mwh"] = _fixture_energy(inst, head, w11, pool + 40,
                                                 pool + 90)
    for aid in inc:
        by_aid[aid]["energy_mwh"] = _fixture_energy(
            inst, aid, w11, pool * 31 // 100, pool * 32 // 100)
    for aid in alt:
        by_aid[aid]["energy_mwh"] = _fixture_energy(
            inst, aid, w11, pool * 235 // 1000, pool * 240 // 1000)
    for src, dst in zip([head] + inc, alt):
        inst["action_layer"][src]["fallback_chain"] = [dst]
    for k, aid in enumerate([head] + inc):
        place(aid, slot_of(aid), w11["start_ms"] + (10 + 5 * k) * MS_PER_MIN)

    # the readmissions
    w12 = windows[11]
    inst["ceiling_live"][(w12["wid"], device)] = ceiling
    inst["ceiling_stale"][(w12["wid"], device)] = ceiling - 700
    setter = readmit[0]
    place(setter, slot_of(setter), w12["start_ms"] + 5 * MS_PER_MIN)
    inst["effects"].append({"seq": 905, "action": setter,
                            "key": "gate_43", "value": "on"})
    shares = [(pool * 50 // 100, pool * 52 // 100),
              (pool * 55 // 100, pool * 57 // 100),
              (pool * 40 // 100, pool * 42 // 100)]
    for k, aid in enumerate(readmit[1:]):
        lo, hi = shares[k]
        by_aid[aid]["energy_mwh"] = _fixture_energy(inst, aid, w12, lo, hi)
        place(aid, slot_of(aid), w12["start_ms"] + (20 + 5 * k) * MS_PER_MIN)
        inst["snapshot"][aid] = {"last_fired_ms": far_past,
                                 "suppressed_until_ms": inst["day_end_ms"]}
        inst["gates"].append({"action": aid, "key": "gate_43",
                              "requires": "on"})

    seq = max(e["seq"] for e in inst["edges"]) + 1

    def edge(pre, dep, strength, at=None):
        nonlocal seq
        inst["edges"].append({"seq": seq if at is None else at,
                              "prereq": pre, "dependent": dep,
                              "prereq_ref": pre, "dependent_ref": dep,
                              "strength_bp": strength, "kind": "soft"})
        if at is None:
            seq += 1

    # cycles settled on the last key: no instance, one strength, one
    # declared sequence across each cycle
    shared = seq
    seq += 1
    edge(settle[0], settle[1], 2400, shared)
    edge(settle[1], settle[2], 2400, shared)
    edge(settle[2], settle[0], 2400, shared)
    shared = seq
    seq += 1
    edge(settle[4], settle[3], 1900, shared)
    edge(settle[3], settle[4], 1900, shared)

    # cycles settled on the eligible tier
    w08 = windows[7]
    t_early = windows[2]["start_ms"] + 5 * MS_PER_MIN
    place(eligible[0], slot_of(eligible[0]), w08["start_ms"] + 10 * MS_PER_MIN,
          tier=3)
    place(eligible[1], slot_of(eligible[1]), w08["start_ms"] + 15 * MS_PER_MIN,
          tier=5)
    place(eligible[1], extra_slot, t_early, tier=2)
    inst["snapshot"][eligible[1]] = {"last_fired_ms": t_early - MS_PER_MIN}
    place(eligible[2], slot_of(eligible[2]), w08["start_ms"] + 20 * MS_PER_MIN,
          tier=4)
    place(eligible[3], slot_of(eligible[3]), w08["start_ms"] + 25 * MS_PER_MIN,
          tier=4)
    place(eligible[4], slot_of(eligible[4]), w08["start_ms"] + 30 * MS_PER_MIN,
          tier=3)
    inst["snapshot"][eligible[4]] = {"last_fired_ms": far_past,
                                     "suppressed_until_ms": inst["day_end_ms"]}
    edge(eligible[0], eligible[1], 2800)
    edge(eligible[1], eligible[2], 2800)
    edge(eligible[2], eligible[0], 2800)
    edge(eligible[3], eligible[4], 2100)
    edge(eligible[4], eligible[3], 2100)


def _fixtures(inst):
    """Named fixtures. Each one puts a documented boundary or precedence rule
    on the critical path of this cycle so that a reading which is plausible
    but not in force publishes a different plan."""
    windows = inst["windows"]
    by_aid = inst["by_aid"]
    far_past = -100000 * MS_PER_MIN

    # A zero ceiling window and device with a zero demand instance in it.
    # A demand at the pool fits; a zero demand fits a zero pool.
    inst["ceiling_live"][(windows[0]["wid"], "DV-01")] = 0
    inst["ceiling_stale"][(windows[0]["wid"], "DV-01")] = 500
    quiet = by_aid["AC-002"]
    quiet["energy_mwh"] = 0
    quiet["device"] = "DV-01"
    quiet["device_ref"] = "DV-01"
    quiet["context"] = inst["contexts"][4]["cid"]
    quiet["context_ref"] = inst["contexts"][4]["cid"]
    inst["action_layer"]["AC-002"].pop("suppress", None)
    inst["routines"][1].update({
        "aid": "AC-002", "action_ref": "AC-002",
        "anchor_ms": windows[0]["start_ms"] + 10 * MS_PER_MIN,
        "period_ms": 0, "span_start_ms": 0,
        "span_end_ms": inst["day_end_ms"], "enabled": True})
    inst["memo_caps"]["RT-002"] = 1
    inst["snapshot"]["AC-002"] = {"last_fired_ms": far_past}

    # A one shot override whose expiry lands exactly on a trigger.
    edge = by_aid["AC-004"]
    edge["context"] = inst["contexts"][4]["cid"]
    edge["context_ref"] = inst["contexts"][4]["cid"]
    inst["action_layer"]["AC-004"].pop("suppress", None)
    inst["snapshot"]["AC-004"] = {"last_fired_ms": far_past}
    inst["memo_caps"]["RT-004"] = 1
    # Overrides whose journal count and whose snapshot count disagree. The
    # snapshot is the one in force.
    inst["snapshot_oneshot"] = {}
    for rec in inst["overrides"]:
        inst["snapshot_oneshot"][rec["override_id"]] = rec["remaining"]
    for rec in inst["overrides"][:10]:
        rec["remaining"] = 0
        rec["expires_ms"] = inst["day_end_ms"]
        rec["tier"] = 2
        rec["intensity_bp"] = 19000
        inst["snapshot_oneshot"][rec["override_id"]] = 3
    for rec in inst["overrides"]:
        if rec["action"] == "AC-004":
            rec["action"] = "AC-005"
    inst["overrides"][6] = {"override_id": "OV-007", "action": "AC-004",
                            "remaining": 2,
                            "expires_ms": windows[2]["start_ms"],
                            "tier": 1, "intensity_bp": 21000,
                            "cooldown_ms": 0}
    inst["snapshot_oneshot"]["OV-007"] = 2

    inst["mandates"] = [m for m in inst["mandates"]
                        if m["action"] not in ("AC-002", "AC-004")]

    _boundary_fixtures(inst, far_past)
    _relay_fixtures(inst, far_past)
    _depth_fixtures(inst, far_past)

    # A window and device the workbook records no ceiling row for, carrying a
    # live instance, so stage r10 has to settle the group under
    # UNKNOWN_CEILING. Only the hidden cycles get it: the shipped corpus keeps
    # a complete grid, so the branch is reached only from its specification,
    # which states both the displacement and the missing capacity row.
    inst["ungridded"] = None
    if inst["seed"] != SAMPLE_SEED:
        gap_window = windows[3]
        gap_device = "DV-09"
        inst["ungridded"] = (gap_window["wid"], gap_device)
        stray = by_aid["AC-006"]
        stray["device"] = gap_device
        stray["device_ref"] = gap_device
        stray["context"] = inst["contexts"][4]["cid"]
        stray["context_ref"] = inst["contexts"][4]["cid"]
        inst["action_layer"]["AC-006"].pop("suppress", None)
        inst["snapshot"]["AC-006"] = {"last_fired_ms": far_past}
        inst["edges"] = [e for e in inst["edges"]
                         if e["dependent"] != "AC-006"]
        inst["routines"][5].update({
            "aid": "AC-006", "action_ref": "AC-006",
            "anchor_ms": gap_window["start_ms"] + 5 * MS_PER_MIN,
            "period_ms": 0, "span_start_ms": 0,
            "span_end_ms": inst["day_end_ms"], "enabled": True})
        inst["memo_caps"]["RT-006"] = 1
        inst["mandates"] = [m for m in inst["mandates"]
                            if m["action"] != "AC-006"]


# ==========================================================================
# corpus emission
#
# Each writer applies the recording rules the papers document. Every rule is
# a triple: the sentence in the lineage note that states it, the transform
# applied here, and the inverse the router applies when it reads the file.
# ==========================================================================
def _unit_pick(rng, pool):
    return pool[rng.below(len(pool))]


def _record_quantity(rng, base_value, base_unit_kind):
    """Choose a recording unit and the recorded value that converts back to
    base_value exactly. Units that do not divide the base value cleanly are
    only offered when the conversion is exact, so no recording rule loses
    information; the router still has to apply the registry to read it."""
    if base_unit_kind == "ms":
        pool = ["ms", "s", "min", "centis", "tick", "beat"]
    elif base_unit_kind == "mwh":
        pool = ["mwh", "wh", "centiwh", "microwh", "kj", "j"]
    else:
        pool = ["bp", "pct", "permille", "micro"]
    order = [pool[(rng.below(len(pool)) + i) % len(pool)] for i in range(len(pool))]
    for token in order:
        _base, num, den, status = UNIT_TABLE[token]
        if status != "live" or num == 0 or den == 0:
            continue
        val = Fraction(base_value) * den / num
        if val.denominator == 1:
            return str(val.numerator), token
        if (val * 1000).denominator == 1:
            text = str(Fraction(val))
            whole = val.numerator // val.denominator
            rest = val - whole
            digits = str(int(rest * 1000)).rjust(3, "0")
            return str(whole) + "." + digits, token
    return str(base_value), pool[0]


def emit_orientation(inst, dest):
    ctl = inst["controls"]
    write_lines(dest / "00_start_here.txt", [
        "DAYBREAK HOUSEHOLD ASSISTANT - ROUTING CYCLE " + inst["cycle"],
        "",
        "This directory is the whole record of one routing cycle. Nothing",
        "outside it settles any value in it.",
        "",
        "Read assistant_program_contract.md first. It names the fourteen",
        "stages and the paper that specifies each one. data_lineage.md maps",
        "every paper to the stage it serves, states the ten recording rules",
        "the registers are written under, and names the papers that govern",
        "nothing. readings_not_in_force.md lists readings of these papers",
        "this household does not support, each beside the reading in force.",
        "",
        "File names describe a role, not the contents. Open a paper before",
        "you decide what it holds.",
        "",
        "Three papers are not plain text and carry values found nowhere else.",
        "capacity_and_intensity_workbook.xlsx carries the per window per",
        "device energy ceilings on several sheets of the same shape, only",
        "one of them live.",
        "household_operations_memo.pdf carries the scalar controls and the",
        "per routine occurrence caps. precedence_directive.docx carries the",
        "seven policy layers, the settlement key order, the mandatory",
        "reserve and the number of reconciliation rounds. All three are",
        "load bearing.",
        "",
        "This cycle is one acquisition profile. It is the " + inst["profile"],
        "profile and it does not reach every documented branch. Implement a",
        "quiet branch from its stage specification rather than from what this",
        "cycle happens to exercise.",
        "",
        "Reason codes are a closed vocabulary. glossary_and_reason_codes.md",
        "holds every admissible member. A code outside it is not a code.",
    ])


def emit_header(inst, dest):
    windows = inst["windows"]
    devices = inst["devices"]
    write_json(dest / "cycle_header.json", {
        "cycle_key": inst["cycle"],
        "profile": inst["profile"],
        "cycle_index": 4,
        "frozen_revision_window_grid": max(w["frozen_rev"] for w in windows),
        "frozen_revision_device_register": max(d["frozen_rev"] for d in devices),
        "window_frozen_revisions": {w["wid"]: w["frozen_rev"] for w in windows},
        "device_frozen_revisions": {d["did"]: d["frozen_rev"] for d in devices},
        "origin_ms": inst["origin_ms"],
        "day_end_ms": inst["day_end_ms"],
        "base_units": {"duration": "ms", "energy": "mwh", "weight": "bp"},
    })
    write_lines(dest / "assistant_runtime.conf", [
        "# daybreak runtime declaration",
        "[invocation]",
        "module = daybreak",
        "data_option = --data",
        "out_option = --out",
        "options_order_free = true",
        "creates_missing_out = true",
        "",
        "[cycle]",
        "cycle_index = 4",
        "preceding_cycle_index = 3",
        "carry_source = prior_cycle_journal.jsonl",
        "archive_source = prior_cycle_archive.sqlite3",
        "archive_table = closing_state",
        "",
        "[arithmetic]",
        "float_permitted = false",
        "rounding = half_even",
        "ratio_places = 12",
    ])


def emit_registers(inst, dest):
    rng = Rng(child_seed(inst["seed"], "emit_registers"))
    windows = inst["windows"]

    # window_grid.csv - RR6 delta chain on the start, RR1 revision history,
    # RR2 unit tokens, RR8 superseded duplicates.
    rows = []
    prev_start = inst["origin_ms"]
    for w in windows:
        delta = w["start_ms"] - prev_start
        prev_start = w["start_ms"]
        for rev, span in _hist(w["span_ms"] // MS_PER_MIN, 9,
                               WINDOW_REVISIONS, rng):
            dtext, dunit = _record_quantity(
                rng, delta if rev == w["frozen_rev"]
                else delta + rng.between(0, 6) * MS_PER_MIN, "ms")
            stext, sunit = _record_quantity(
                rng, w["span_ms"] if rev == w["frozen_rev"]
                else span * MS_PER_MIN, "ms")
            rows.append([w["wid"], w["ordinal"], rev, dtext, dunit, stext, sunit,
                         w["capacity_class"]])
    rows.append([windows[3]["wid"], windows[3]["ordinal"],
                 windows[3]["frozen_rev"] - 1, "0", "ms", "1", "min",
                 windows[3]["capacity_class"]])
    rows = _minted_shuffle(inst, "shuf_wg", rows)
    write_delim(dest / "window_grid.csv",
                ["window_id", "ordinal", "revision", "start_delta_value",
                 "start_delta_unit", "span_value", "span_unit",
                 "capacity_class"], rows, ",")

    # device_register.csv - RR1 revision history, RR4 sentinel absence.
    rows = []
    for d in inst["devices"]:
        for rev, slots in _hist(d["slots"], 1, DEVICE_REVISIONS, rng):
            rows.append([d["did"], rev, d["cls"], slots,
                         "-" if rng.chance(1, 4) else str(rng.between(0, 3))])
    rows = _minted_shuffle(inst, "shuf_dr", rows)
    if inst["seed"] != SAMPLE_SEED:
        # two rows for one device at its frozen revision; the later is read
        tied = inst["devices"][2]
        decoy = [tied["did"], tied["frozen_rev"], tied["cls"],
                 tied["slots"] + 3, "-"]
        rows = _tied_before(rows, 0, 1, tied["did"], tied["frozen_rev"], decoy)
    write_delim(dest / "device_register.csv",
                ["device_id", "revision", "device_class", "slots",
                 "quiet_hours_flag"], rows, ",")

    # action_catalogue.csv - RR2 unit tokens, RR3 alias references.
    rows = []
    for a in inst["actions"]:
        etext, eunit = _record_quantity(rng, a["energy_mwh"], "mwh")
        dtext, dunit = _record_quantity(rng, a["duration_ms"], "ms")
        if a["energy_unit"] == "pulse":
            eunit = "pulse"
        if a["duration_unit"] == "moment":
            dunit = "moment"
        rows.append([a["aid"], a["name"], a["device_ref"], a["context_ref"],
                     etext, eunit, dtext, dunit, a["cls"], a["seq"],
                     "routed" if a["routed"] else "fallback_only"])
    write_delim(dest / "action_catalogue.csv",
                ["action_id", "action_name", "device_ref", "context_ref",
                 "energy_value", "energy_unit", "duration_value",
                 "duration_unit", "action_class", "declared_seq", "role"],
                rows, ",")

    # routine_register.csv - RR2 unit tokens, RR3 alias references,
    # RR7 explicit sign column on the anchor.
    rows = []
    for r in inst["routines"]:
        atext, aunit = _record_quantity(rng, abs(r["anchor_ms"]), "ms")
        ptext, punit = _record_quantity(rng, r["period_ms"], "ms")
        s0text, s0unit = _record_quantity(rng, r["span_start_ms"], "ms")
        s1text, s1unit = _record_quantity(rng, r["span_end_ms"], "ms")
        rows.append([r["rid"], r["action_ref"],
                     "-" if r["anchor_ms"] < 0 else "+", atext, aunit,
                     ptext, punit, s0text, s0unit, s1text, s1unit,
                     "yes" if r["enabled"] else "no", r["seq"]])
    write_delim(dest / "routine_register.csv",
                ["routine_id", "action_ref", "anchor_sign", "anchor_value",
                 "anchor_unit", "period_value", "period_unit",
                 "span_start_value", "span_start_unit", "span_end_value",
                 "span_end_unit", "enabled", "declared_seq"], rows, ",")

    # dependency_edges.tsv - RR2 unit tokens on the strength.
    rows = []
    for e in inst["edges"]:
        stext, sunit = _record_quantity(rng, e["strength_bp"], "bp")
        rows.append([e["seq"], e["prereq_ref"], e["dependent_ref"], stext,
                     sunit, e["kind"]])
    rows = _minted_shuffle(inst, "shuf_de", rows)
    write_delim(dest / "dependency_edges.tsv",
                ["declared_seq", "prereq_ref", "dependent_ref",
                 "strength_value", "strength_unit", "edge_kind"], rows, TAB)

    # context_activity_spans.tsv - RR6 delta chain on the span start.
    rows = []
    prev = inst["origin_ms"]
    for c in inst["contexts"]:
        delta = c["start_ms"] - prev
        prev = c["start_ms"]
        dtext, dunit = _record_quantity(rng, abs(delta), "ms")
        ltext, lunit = _record_quantity(rng, c["end_ms"] - c["start_ms"], "ms")
        rows.append([c["cid"], c["name"], "-" if delta < 0 else "+", dtext,
                     dunit, ltext, lunit])
    for i in range(len(rows), 210):
        c = inst["contexts"][i % N_CONTEXTS]
        rows.append([c["cid"] + ".hist." + str(i).rjust(3, "0"), c["name"],
                     "+", "0", "ms", "0", "ms"])
    write_delim(dest / "context_activity_spans.tsv",
                ["context_id", "context_name", "start_delta_sign",
                 "start_delta_value", "start_delta_unit", "length_value",
                 "length_unit"], rows, TAB)

    # cooldown_register.psv - per action class cooldown floors, one live row
    # per class chosen by the greatest revision at or below the frozen one.
    rows = []
    frozen = inst["cooldown_frozen"]
    for cls in ACTION_CLASSES:
        base = rng.between(30, 260)
        for rev in range(1, 13):
            val = base + rng.between(-8, 8)
            if val < 0:
                val = 0
            text, unit = _record_quantity(rng, val * MS_PER_MIN, "ms")
            rows.append([cls, rev, text, unit])
    # a revision above every frozen revision, recorded in a token whose
    # registry row is live but whose denominator is zero
    rows.append([ACTION_CLASSES[2], 13, "40", "stroke"])
    for i in range(len(rows), 205):
        rows.append(["retired_class_" + str(i).rjust(3, "0"), 1, "0", "ms"])
    rows = _minted_shuffle(inst, "shuf_cd", rows)
    write_delim(dest / "cooldown_register.psv",
                ["action_class", "revision", "floor_value", "floor_unit"],
                rows, PIPE)
    with_crlf(dest / "cooldown_register.psv")
    write_json(dest / "state_snapshot.json", {
        "cycle_key": inst["cycle"],
        "frozen_revision_cooldown_register": frozen,
        "actions": {aid: rec for aid, rec in sorted(inst["snapshot"].items())},
        "oneshot_remaining": {k: v for k, v in
                              sorted(inst["snapshot_oneshot"].items())},
    })


def _cell(rec, key, rng):
    """RR4. A hyphen records an absent field, which inherits from the next
    layer down. A written zero records an explicit zero, which does not."""
    if key not in rec:
        return "-"
    val = rec[key]
    if isinstance(val, bool):
        return "true" if val else "false"
    return str(val)


def emit_policies(inst, dest):
    rng = Rng(child_seed(inst["seed"], "emit_policies"))

    # global_defaults.yaml - the global layer, every field present.
    g = inst["global_layer"]
    write_lines(dest / "global_defaults.yaml", [
        "# daybreak global layer. Every field is present here, so",
        "# resolution always terminates. Its rank is in the directive.",
        "layer: global",
        "tier: " + str(g["tier"]),
        "intensity_value: " + str(g["intensity_bp"] // 100),
        "intensity_unit: pct",
        "cooldown_value: " + str(g["cooldown_ms"] // MS_PER_MIN),
        "cooldown_unit: min",
        "mandatory: false",
        "max_occurrences: " + str(g["max_occurrences"]),
        "suppress: false",
        "fallback_chain: []",
        "reason_code_vocabulary: closed",
        "absent_field_marker: '-'",
    ])

    # routine_defaults.toml - the routine layer.
    lines = ["# daybreak routine layer, one flat table, one routine per line.",
             "# value form: tier|intensity_bp|cooldown_min|max_occurrences",
             "# a hyphen in any position records an absent field.",
             "layer = " + Q + "routine" + Q, ""]
    for r in inst["routines"]:
        rec = inst["routine_layer"][r["rid"]]
        parts = [_cell(rec, "tier", rng),
                 str(rec["intensity_bp"]) if "intensity_bp" in rec else "-",
                 str(rec["cooldown_ms"] // MS_PER_MIN)
                 if "cooldown_ms" in rec else "-",
                 str(rec["max_occurrences"])
                 if "max_occurrences" in rec else "-"]
        lines.append(r["rid"] + " = " + Q + PIPE.join(parts) + Q)
    write_lines(dest / "routine_defaults.toml", lines)

    # action_policies.jsonl - the action layer. Absent keys are absent.
    recs = []
    for a in inst["actions"]:
        rec = dict(inst["action_layer"][a["aid"]])
        out = {"layer": "action", "action_id": a["aid"]}
        if "tier" in rec:
            out["tier"] = rec["tier"]
        if "intensity_bp" in rec:
            out["intensity"] = {"value": rec["intensity_bp"], "unit": "bp"}
        if "cooldown_ms" in rec:
            out["cooldown"] = {"value": rec["cooldown_ms"] // 1000,
                               "unit": "s"}
        if "suppress" in rec:
            out["suppress"] = rec["suppress"]
        if "fallback_chain" in rec:
            out["fallback_chain"] = rec["fallback_chain"]
        recs.append(out)
    write_jsonl(dest / "action_policies.jsonl", recs)

    # device_policies.csv - the device layer, empty cells are absent fields.
    rows = []
    for d in inst["devices"]:
        rec = inst["device_layer"][d["did"]]
        for rev in range(1, 14):
            live = rev == d["frozen_rev"]
            rows.append([
                d["did"], rev,
                (str(rec["tier"]) if "tier" in rec else "")
                if live else str(rng.between(2, 9)),
                (str(rec["intensity_bp"] // 10) if "intensity_bp" in rec else "")
                if live else str(rng.between(500, 2000)),
                ("permille" if "intensity_bp" in rec else "")
                if live else "permille",
                (str(rec["cooldown_ms"] // 1000) if "cooldown_ms" in rec else "")
                if live else str(rng.between(0, 9000)),
                ("s" if "cooldown_ms" in rec else "") if live else "s",
            ])
    rows = _minted_shuffle(inst, "shuf_dp", rows)
    if inst["seed"] != SAMPLE_SEED:
        # a stale copy of one device's row in force, at the same revision and
        # ahead of it in the file; the later row is the one read
        tied = inst["devices"][3]
        decoy = [tied["did"], tied["frozen_rev"], "9", "150", "permille",
                 "7200", "s"]
        rows = _tied_before(rows, 0, 1, tied["did"], tied["frozen_rev"], decoy)
    write_delim(dest / "device_policies.csv",
                ["device_id", "revision", "tier", "intensity_value",
                 "intensity_unit", "cooldown_value", "cooldown_unit"],
                rows, ",")

    # context_policies.tsv - the context layer.
    rows = []
    for c in inst["contexts"]:
        rec = inst["context_layer"][c["cid"]]
        rows.append([c["cid"], c["name"],
                     str(rec["tier"]) if "tier" in rec else "-",
                     str(rec["intensity_bp"] // 100)
                     if "intensity_bp" in rec else "-",
                     "pct" if "intensity_bp" in rec else "-",
                     "true" if rec.get("suppress") else
                     ("-" if "suppress" not in rec else "false")])
    for i in range(len(rows), 206):
        rows.append(["CX-hist-" + str(i).rjust(3, "0"), "retired", "-", "-",
                     "-", "-"])
    write_delim(dest / "context_policies.tsv",
                ["context_id", "context_name", "tier", "intensity_value",
                 "intensity_unit", "suppress"], rows, TAB)

    # override_journal.jsonl - the one shot layer.
    recs = []
    for o in inst["overrides"]:
        out = {"layer": "oneshot",
               "override_id": o["override_id"], "action_id": o["action"],
               "remaining": o["remaining"],
               "expires": {"value": o["expires_ms"] // 1000, "unit": "s"}}
        if "tier" in o:
            out["tier"] = o["tier"]
        if "intensity_bp" in o:
            out["intensity"] = {"value": o["intensity_bp"], "unit": "bp"}
        if "cooldown_ms" in o:
            out["cooldown"] = {"value": o["cooldown_ms"], "unit": "ms"}
        recs.append(out)
    for i in range(len(recs), 208):
        recs.append({"layer": "oneshot",
                     "override_id": "OV-void-" + str(i).rjust(3, "0"),
                     "action_id": "AC-000", "remaining": 0,
                     "expires": {"value": 0, "unit": "s"}})
    write_jsonl(dest / "override_journal.jsonl", recs)

    # source_priority_register.csv - which identifier source outranks which.
    rows = [["alias_crosswalk.tsv", 1, "primary", "identifier", "in_force"],
            ["identifier_supplement.psv", 2,
             '"supplement, secondary"', "identifier", "in_force"],
            ["action_catalogue.csv", 3, "catalogue", "identifier", "in_force"]]
    for i in range(len(rows), 202):
        rows.append(["retired_source_" + str(i).rjust(3, "0"), 9,
                     '"retired, superseded"' if i % 7 == 0 else "retired",
                     "identifier", "withdrawn"])
    write_delim(dest / "source_priority_register.csv",
                ["source_name", "source_rank", "source_role", "domain",
                 "status"], rows, ",")

    write_delim(dest / "alias_crosswalk.tsv",
                ["alias", "canonical", "kind", "declared_seq"],
                [[r["alias"], r["canonical"], r["kind"], r["seq"]]
                 for r in inst["alias_primary"]], TAB)
    with_bom(dest / "alias_crosswalk.tsv")
    sup = [[r["alias"], r["canonical"], r["kind"], r["seq"]]
           for r in inst["alias_supplement"]]
    for i in range(len(sup), 204):
        sup.append(["spare." + str(i).rjust(3, "0"), "AC-001", "action",
                    100 + i])
    write_delim(dest / "identifier_supplement.psv",
                ["alias", "canonical", "kind", "declared_seq"], sup, PIPE)

    # state effects and gates
    write_jsonl(dest / "state_effects.jsonl",
                [{"declared_seq": e["seq"], "action_id": e["action"],
                  "sets_key": e["key"], "sets_value": e["value"]}
                 for e in inst["effects"]]
                + [{"declared_seq": 1000 + i, "action_id": "AC-000",
                    "sets_key": "flag_00", "sets_value": "off"}
                   for i in range(1, 130)])
    lines = ["# daybreak gate table. An action listed here runs only while the",
             "# named derived state key holds the required value.",
             "layer = " + Q + "gate" + Q, ""]
    for grec in inst["gates"]:
        lines.append(grec["action"] + " = " + Q + grec["key"] + PIPE
                     + grec["requires"] + Q)
    for i in range(len(lines), 214):
        lines.append("AC-void-" + str(i).rjust(3, "0") + " = "
                     + Q + "flag_00" + PIPE + "off" + Q)
    write_lines(dest / "gating_rules.toml", lines)

    # prior cycle journal
    write_jsonl(dest / "prior_cycle_journal.jsonl",
                [{"cycle_index": p["cycle_index"], "action_id": p["action"],
                  "carried_cooldown": {"value": p["carried_cooldown_ms"] // 1000,
                                       "unit": "s"},
                  "fired": {"value": p["fired_ms"] // 1000, "unit": "s"}}
                 for p in inst["prior_runs"]])

    # energy ledger history, newline delimited json
    rng2 = Rng(child_seed(inst["seed"], "ledger"))
    recs = []
    for d in inst["devices"]:
        block = []
        for k in range(1, 14):
            block.append({"device_id": d["did"], "cycle_index": k,
                          "consumed": {"value": rng2.between(100, 90000),
                                       "unit": "mwh"},
                          "note": "closed"})
        # rows are posted as they are reconciled, not in cycle order: the
        # greatest cycle index is often not the last row for its device
        cut = rng2.between(3, 12)
        recs.extend(block[cut:] + block[:cut])
    write_jsonl(dest / "energy_ledger_history.ndjson", recs)

    # home topology, circuits over devices
    circuits = {}
    for i, d in enumerate(inst["devices"]):
        circuits.setdefault("CIR-" + str((i % 5) + 1), []).append(d["did"])
    parts = [XMLDECL, "<home cycle=" + _q(inst["cycle"]) + ">",
             "<origin>" + str(inst["origin_ms"]) + "</origin>",
             "<circuits>"]
    for cid in sorted(circuits):
        for did in circuits[cid]:
            parts.append("<circuit id=" + _q(cid) + " device=" + _q(did)
                         + " role=" + _q("member") + "/>")
    for i in range(200):
        parts.append("<circuit id=" + _q("CIR-retired") + " device="
                     + _q("DV-00") + " role=" + _q("withdrawn") + "/>")
    parts.append("</circuits></home>")
    write_text(dest / "home_topology.xml", "".join(parts))

    # prior cycle archive
    rng3 = Rng(child_seed(inst["seed"], "archive"))
    rows = []
    for a in inst["actions"]:
        rows.append([a["aid"], str(-rng3.between(0, 900) * MS_PER_MIN), "3",
                     "closed"])
    write_sqlite(dest / "prior_cycle_archive.sqlite3",
                 {"closing_state": (["action_id", "last_fired_ms",
                                     "cycle_index", "status"], rows)})


def _grid_text(val):
    frac = Fraction(val, 10)
    if frac.denominator == 1:
        return str(frac.numerator)
    return str(frac.numerator // 10) + "." + str(frac.numerator % 10)


def _ungridded_pair(inst):
    """The window and device the workbook records no ceiling for.

    None on the shipped cycle, so the corpus the agent receives is complete.
    On a hidden cycle it is the fixed pair _fixtures plants, window W04 and
    device DV-09, where AC-006 carries a live instance, so the missing row
    always displaces a real instance rather than an empty group."""
    if inst["seed"] == SAMPLE_SEED:
        return None
    return inst.get("ungridded")


def emit_workbook(inst, dest):
    """Four ceiling grids and one surcharge table. The live grid is the one
    whose key cell equals the cycle key in cycle_header.json. Sheet name and
    sheet position say nothing about which grid is live."""
    ctl = inst["controls"]
    windows = inst["windows"]
    devices = inst["devices"]
    live_first = child_seed(inst["seed"], "sheetorder") % 2 == 0
    grid_a = [["grid_key", inst["cycle"] if live_first
               else inst["cycle"] + "-SUPERSEDED"],
              ["recorded_unit", "centiwh"],
              ["window_id", "device_id", "ceiling_value", "ceiling_unit",
               "capacity_class"]]
    grid_b = [["grid_key", inst["cycle"] + "-SUPERSEDED" if live_first
               else inst["cycle"]],
              ["recorded_unit", "centiwh"],
              ["window_id", "device_id", "ceiling_value", "ceiling_unit",
               "capacity_class"]]
    # One window and device pair carries no ceiling row on the hidden cycles,
    # which stage r10 settles under UNKNOWN_CEILING. On every cycle one live
    # cell records the absent sentinel, which r10 settles the same way.
    missing = _ungridded_pair(inst)
    # live cells recorded unusually: a written zero beside an absent cell,
    # and two cells in microwh whose carried values are 0.5 and 2.5 mwh
    special = {("W05", "DV-05"): ("0", "centiwh"),
               ("W05", "DV-06"): ("-", "centiwh"),
               ("W04", "DV-05"): ("500", "microwh"),
               ("W04", "DV-06"): ("2500", "microwh")}
    # two more grids whose key cells are not the cycle key: one before both
    # carrying it in lower case, one after both carrying a trailing space
    grid_d = [["grid_key", inst["cycle"].lower()],
              ["recorded_unit", "centiwh"],
              ["window_id", "device_id", "ceiling_value", "ceiling_unit",
               "capacity_class"]]
    grid_c = [["grid_key", inst["cycle"] + " "],
              ["recorded_unit", "centiwh"],
              ["window_id", "device_id", "ceiling_value", "ceiling_unit",
               "capacity_class"]]
    for w in windows:
        for d in devices:
            if (w["wid"], d["did"]) == missing:
                continue
            live = inst["ceiling_live"][(w["wid"], d["did"])]
            stale = inst["ceiling_stale"][(w["wid"], d["did"])]
            live_cell = special.get((w["wid"], d["did"]),
                                    (_grid_text(live), "centiwh"))
            stale_cell = (_grid_text(stale), "centiwh")
            a_cell = live_cell if live_first else stale_cell
            b_cell = stale_cell if live_first else live_cell
            grid_a.append([w["wid"], d["did"], a_cell[0], a_cell[1],
                           w["capacity_class"]])
            grid_b.append([w["wid"], d["did"], b_cell[0], b_cell[1],
                           w["capacity_class"]])
            grid_c.append([w["wid"], d["did"], _grid_text(live + 900),
                           "centiwh", w["capacity_class"]])
            grid_d.append([w["wid"], d["did"], _grid_text(stale + 600),
                           "centiwh", w["capacity_class"]])
    surcharge = [["surcharge_key", inst["cycle"]],
                 ["action_class", "surcharge_value", "surcharge_unit"]]
    for cls in ACTION_CLASSES:
        surcharge.append([cls, str(ctl["surcharge_bp"][cls]), "bp"])
    surcharge.append(["capacity_class", "scale_value", "scale_unit"])
    for cls in ["quiet", "standard", "peak"]:
        surcharge.append([cls, str(ctl["capacity_class_bp"][cls]), "bp"])
    surcharge.append(["reserve", str(inst["controls"]["reserve_bp"]), "bp"])
    for i in range(len(surcharge), 210):
        surcharge.append(["retired_class_" + str(i).rjust(3, "0"), "0", "bp"])
    sheets = [("grid_draft", grid_d), ("grid_alpha", grid_a),
              ("grid_beta", grid_b), ("class_scales", surcharge),
              ("grid_current", grid_c)]
    if inst["seed"] != SAMPLE_SEED:
        # minted cycles place the sheets anywhere, the live grid never first
        live_name = "grid_alpha" if live_first else "grid_beta"
        srng = Rng(child_seed(inst["seed"], "sheetperm"))
        while True:
            sheets = _minted_shuffle(
                {"seed": srng.step()}, "sheetperm", sheets)
            if sheets[0][0] != live_name:
                break
    write_xlsx(dest / "capacity_and_intensity_workbook.xlsx", dict(sheets))


def emit_memo(inst, dest):
    """The household operations memo. Every scalar control the stages need and
    the per routine occurrence cap table live here and nowhere else."""
    ctl = inst["controls"]
    lines = [
        "DAYBREAK HOUSEHOLD OPERATIONS MEMO",
        "Routing cycle " + inst["cycle"] + " - acquisition profile "
        + inst["profile"],
        "",
        "SECTION 1 - SCALAR CONTROLS IN FORCE",
        "These values are recorded here and in no other paper. Each is quoted",
        "in the unit named beside it and converts under the unit registry.",
        "",
        "  implausible demand ceiling  " + str(ctl["implausible_demand_mwh"])
        + " mwh",
        "  fallback chain depth cap    " + str(ctl["fallback_chain_depth_cap"])
        + " candidates",
        "  default max occurrences     " + str(ctl["default_max_occurrences"])
        + " occurrences",
        "  alias hop cap               " + str(ctl["alias_hop_cap"]) + " hops",
        "",
        "SECTION 2 - READING THE CAP TABLE",
        "Column one is the routine identifier. Column two is the occurrence",
        "cap the routine carries in this cycle. A dash records that the",
        "routine carries no cap of its own and inherits the resolved policy",
        "max_occurrences instead. A cap of zero is an explicit zero and",
        "suppresses the routine; it is not an absent field.",
        "",
        "SECTION 3 - PER ROUTINE OCCURRENCE CAPS",
        "routine_id  cap",
    ]
    for r in inst["routines"]:
        cap = inst["memo_caps"][r["rid"]]
        lines.append("  " + r["rid"] + "  " + ("-" if cap is None else str(cap)))
    lines += [
        "",
        "SECTION 4 - NOTES",
        "The cap table is the only authority for the routine occurrence cap.",
        "The workbook grids do not carry it and the registers do not carry it.",
        "A cycle that reads the cap from the resolved policy alone will",
        "publish more occurrences than this household authorised.",
    ]
    write_pdf(dest / "household_operations_memo.pdf", lines)


def emit_directive(inst, dest):
    """The precedence directive. Layer ranks, the settlement key order, the
    mandatory reserve, the round cap and the layer one directive schedule."""
    ctl = inst["controls"]
    papers = {"mandatory": ("precedence_directive.docx",
                            "part D of this directive"),
              "oneshot": ("override_journal.jsonl",
                          "applies only while remaining is above zero"),
              "context": ("context_policies.tsv",
                          "applies only while the context is active at the "
                          "trigger instant"),
              "device": ("device_policies.csv", "live revision only"),
              "action": ("action_policies.jsonl", "as recorded"),
              "routine": ("routine_defaults.toml", "as recorded"),
              "global": ("global_defaults.yaml", "every field present")}
    layer_rows = [["rank", "layer", "paper", "note"]]
    for name in sorted(papers, key=lambda n: inst["layer_ranks"][n]):
        layer_rows.append([str(inst["layer_ranks"][name]), name]
                          + list(papers[name]))
    blocks = [
        ("h", "DAYBREAK PRECEDENCE DIRECTIVE - CYCLE " + inst["cycle"]),
        ("p", "This directive is the authority for the policy layer order, "
              "for the settlement key order used when the dependency graph "
              "carries a cycle, for the mandatory reserve, for the number of "
              "reconciliation rounds, and for the layer one directive "
              "schedule. Where another paper or an older habit of the package "
              "disagrees with a figure here, this directive settles it."),
        ("h", "PART A - POLICY LAYER ORDER"),
        ("p", "A field resolves at the strongest layer that records it. A "
              "layer that does not record a field does not settle it; "
              "resolution falls to the next layer down. An explicitly "
              "recorded zero settles the field at that layer."),
        ("table", layer_rows),
        ("h", "PART B - SETTLEMENT KEY ORDER"),
        ("p", "When the dependency graph carries a cycle, exactly one edge of "
              "that cycle is removed. The removable edge is the one that "
              "comes first under this key order, read top to bottom, each key "
              "settling the choice before the next is consulted."),
        ("table", [["order", "key", "direction"],
                   ["1", "edge strength in basis points", "least first"],
                   ["2", "resolved tier of the dependent action",
                    "greatest first"],
                   ["3", "declared sequence of the edge", "greatest first"],
                   ["4", "the text prereq|dependent", "greatest first"]]),
        ("h", "PART C - MANDATORY RESERVE AND ROUNDS"),
        ("p", "A share of every window and device energy ceiling is withheld "
              "from actions that are not mandatory. The share is "
              + str(ctl["reserve_bp"]) + " basis points of the ceiling, "
              "rounded half to even at whole mwh. Mandatory actions draw "
              "against the whole ceiling; what they have already drawn "
              "reduces the withheld share before the remainder is offered to "
              "the rest."),
        ("p", "Reconciliation runs for at most " + str(inst["round_cap"])
              + " rounds in total, the first binding counted as round one. An "
              "action still displaced when the last round closes is "
              "terminal."),
        ("h", "PART D - LAYER ONE DIRECTIVE SCHEDULE"),
        ("p", "Each row binds one action inside one window. A row whose "
              "mandatory column reads yes makes that action mandatory in that "
              "window and settles its tier at layer one. A row whose "
              "mandatory column reads no settles the tier at layer one and "
              "leaves the action discretionary."),
    ]
    table = [["seq", "action_id", "window_id", "mandatory", "tier"]]
    for m in inst["mandates"]:
        table.append([str(m["seq"]), m["action"], m["window"],
                      "yes" if m["mandatory"] else "no", str(m["tier"])])
    blocks.append(("table", table))
    write_docx(dest / "precedence_directive.docx", blocks)


def _md(lines):
    return NL.join(lines)


def emit_policy_papers(inst, dest):
    ctl = inst["controls"]
    lines = ["# daybreak unit registry",
             "# token = base|numerator|denominator|status",
             "# A quantity recorded as value and token carries base units",
             "# half_even(value * numerator / denominator). The multiplication",
             "# is exact rational; the rounding is the only rounding this",
             "# conversion performs and it happens once, on the way out.",
             "# A token whose status is not live, or whose denominator is",
             "# zero, cannot be carried: the record that holds it is set",
             "# aside under UNCONVERTIBLE_UNIT. That is a documented outcome,",
             "# not an error.",
             ""]
    for token in sorted(UNIT_TABLE):
        base, num, den, status = UNIT_TABLE[token]
        lines.append(token + " = " + Q + PIPE.join([base, str(num), str(den),
                                                    status]) + Q)
    lines.append("")
    lines.append("# Withdrawn legacy tokens. Each one names a base unit this")
    lines.append("# household once recorded in and no longer carries. A")
    lines.append("# quantity that names one of these is set aside under")
    lines.append("# UNCONVERTIBLE_UNIT even when its numerator and its")
    lines.append("# denominator would convert. Status settles it, not the")
    lines.append("# ratio and not the base name.")
    rng2 = Rng(child_seed(inst["seed"], "legacy_units"))
    for stem in LEGACY_UNIT_STEMS:
        for i in range(1, 12):
            token = stem + "_" + str(i).rjust(2, "0")
            base = rng2.pick(["ms", "mwh", "bp"])
            num = rng2.between(1, 4096)
            den = rng2.pick([0, 1, 2, 4, 8, 16, 100, 1000])
            lines.append(token + " = " + Q + PIPE.join(
                [base, str(num), str(den), "withdrawn"]) + Q)
    write_lines(dest / "unit_registry_dictionary.toml", lines)

    write_lines(dest / "rounding_and_arithmetic_policy.yaml", [
        "# daybreak arithmetic policy",
        "arithmetic: exact_rational",
        "binary_floating_point: forbidden",
        "rounding_mode: half_even",
        "rounding_placement: after_every_conversion_and_every_product",
        "carry_unrounded_between_stages: forbidden",
        "negative_zero: forbidden",
        "ratio_decimal_places: 12",
        "whole_quantities: integer_in_the_base_unit_of_the_stage",
        "demand_first_product: energy_mwh_times_effective_intensity_bp_over_10000",
        "demand_second_product: first_result_times_window_scale_bp_over_10000",
        "reserve_product: ceiling_mwh_times_reserve_bp_over_10000",
        "zero_denominator_behaviour: set_aside_under_UNCONVERTIBLE_UNIT",
        "empty_group_behaviour: publish_the_empty_document",
    ])

    write_lines(dest / "precedence_and_overturn.toml", [
        "# daybreak precedence and overturn",
        "# The layer order itself lives in precedence_directive.docx part A.",
        "# This paper states how the order is applied.",
        "field_list = " + Q + PIPE.join(POLICY_FIELDS) + Q,
        "absent_field_marker = " + Q + "-" + Q,
        "empty_cell_is_absent = " + Q + "true" + Q,
        "explicit_zero_settles_the_field = " + Q + "true" + Q,
        "resolution = " + Q + "strongest layer that records the field" + Q,
        "mandatory_layer_scope = " + Q + "one action inside one window" + Q,
        "mandatory_duplicate_rule = " + Q + "greatest seq wins" + Q,
        "oneshot_applicability = " + Q
        + "remaining above zero and trigger strictly before expiry" + Q,
        "oneshot_duplicate_rule = " + Q + "least override_id wins" + Q,
        "oneshot_remaining_source = " + Q
        + "state_snapshot.json oneshot_remaining, which outranks the journal"
        + Q,
        "context_applicability = " + Q
        + "context active at the trigger instant, start inclusive, end exclusive"
        + Q,
        "device_layer_revision = " + Q + "live revision only" + Q,
        "cooldown_class_floor = " + Q
        + "resolved cooldown is raised to the live class floor" + Q,
        "overturn_rounds = " + Q + "precedence_directive.docx part C" + Q,
        "overturn_scope = " + Q + "one window and one device" + Q,
        "overturn_candidates = " + Q
        + "current holders of that window and device together with the"
        + " fallbacks proposed for it in the round" + Q,
        "overturn_pool = " + Q + "the same pool the first round offered" + Q,
    ])

    write_lines(dest / "capacity_binding_policy.yaml", [
        "# daybreak capacity binding",
        "ceiling_source: capacity_and_intensity_workbook.xlsx",
        "ceiling_scope: one window and one device",
        "live_grid_rule: the grid whose key cell equals the cycle key",
        "reserve_source: precedence_directive.docx part C",
        "group_order: window ordinal ascending then device id ascending",
        "mandatory_first: true",
        "mandatory_draws_against: the whole ceiling",
        "mandatory_order: canonical order",
        "overrun_flag: raised when the mandatory draw exceeds the ceiling",
        "remaining_after_overrun: zero",
        "withheld_share: reserve minus the mandatory draw, floored at zero",
        "pool: remaining minus the withheld share, floored at zero",
        "discretionary_order: [tier ascending, demand descending, trigger ascending, instance_id ascending]",
        "fit_rule: demand at or below the pool fits",
        "equality_binds_without_displacing: true",
        "zero_demand_fits_a_zero_pool: true",
        "zero_capacity_window_is_legal: true",
        "a_candidate_that_does_not_fit: displaced, and the next candidate is still considered",
        "displaced_actions_are_not_discarded: true",
    ])

    write_lines(dest / "cycle_break_policy.toml", [
        "# daybreak cycle settlement",
        "# The key order lives in precedence_directive.docx part B. This",
        "# paper states the search that names the cycle to settle.",
        "cycles_are_legal = " + Q + "true" + Q,
        "search = " + Q + "depth first" + Q,
        "entry_order = " + Q + "node identifier ascending" + Q,
        "successor_order = " + Q + "node identifier ascending" + Q,
        "cycle_named_by = " + Q + "the first back edge reached" + Q,
        "edges_removed_per_round = 1",
        "repeat_until = " + Q + "no cycle remains" + Q,
        "dependent_tier_source = " + Q
        + "least resolved tier over the eligible instances of that action;"
        + " an action with no eligible instance takes the global tier" + Q,
        "key_settled_at = " + Q
        + "the ordinal of the first key whose values are not all equal across"
        + " the edges of the cycle; 4 when the first three keys tie" + Q,
    ])

    write_lines(dest / "expansion_policy.yaml", [
        "# daybreak routine expansion",
        "generation: trigger = anchor + step * period, step from zero",
        "period_zero: exactly one trigger, at the anchor, kept or discarded by the span rules",
        "span_start: inclusive",
        "span_end: exclusive",
        "before_span_start: discarded without consuming the cap",
        "generation_guard: 512 steps",
        "window_match: window start inclusive, window end exclusive",
        "trigger_on_a_window_end: belongs to the next window",
        "no_window_matches: OUT_OF_DAY",
        "disabled_routine: RETIRED_ROUTINE",
        "cap_resolution: [memo cap, routine layer max_occurrences, memo default]",
        "cap_zero: OCCURRENCE_CAP_ZERO",
        "occurrence_index: the ordinal of the surviving occurrence, from zero",
        "instance_id: routine_id then a hash then the occurrence index in two digits",
    ])

    write_lines(dest / "publication_form_rules.toml", [
        "# daybreak publication form",
        "encoding = " + Q + "utf-8" + Q,
        "line_ending = " + Q + "lf" + Q,
        "trailing_newline = " + Q + "one, on every document that has content" + Q,
        "json_indent = 2",
        "json_sort_keys = " + Q + "true" + Q,
        "json_ensure_ascii = " + Q + "true" + Q,
        "jsonl_form = " + Q + "one compact object per line, keys sorted,"
        + " separators comma and colon with no spaces" + Q,
        "jsonl_empty_form = " + Q + "an empty file of zero bytes" + Q,
        "csv_separator = " + Q + "," + Q,
        "csv_empty_form = " + Q + "the header line alone" + Q,
        "csv_quoting = " + Q + "none; no published field carries a comma" + Q,
        "boolean_form = " + Q + "true and false, lower case" + Q,
        "ratio_form = " + Q + "twelve decimal places, no negative zero" + Q,
        "manifest_line = " + Q + "sha256 then two spaces then the file name" + Q,
        "manifest_order = " + Q + "file name ascending" + Q,
        "manifest_trailers = " + Q + "core then publication" + Q,
        "core_digest_over = " + Q + "the bytes of unit_normalization.json,"
        + " canonical_action_order.json, final_action_order.json,"
        + " daily_automation_manifest.json and next_state_snapshot.json,"
        + " concatenated in that order" + Q,
        "publication_digest_over = " + Q + "the manifest body lines, each"
        + " followed by one line feed, before the two trailers are appended"
        + Q,
    ])

    write_lines(dest / "package_expectations.toml", [
        "# what the delivered archive has to contain",
        "archive_root_file = " + Q + "pyproject.toml" + Q,
        "source_root = " + Q + "src/daybreak" + Q,
        "tests_root = " + Q + "tests" + Q,
        "tests_carried_through = " + Q + "unchanged, module for module" + Q,
        "modules = " + Q + PIPE.join(["__init__.py", "__main__.py", "cli.py",
                                      "util.py", "loading.py", "stages.py",
                                      "allocate.py", "publish.py"]) + Q,
        "entry_point = " + Q + "python3 -m daybreak" + Q,
        "options = " + Q + "--data|--out" + Q,
        "options_order_free = " + Q + "true" + Q,
        "creates_missing_out = " + Q + "true" + Q,
        "third_party_imports = " + Q + "none" + Q,
        "python_series = " + Q + "3.12" + Q,
        "writes_only_the_derived_documents = " + Q + "true" + Q,
        "leaves_the_paper_directory_untouched = " + Q + "true" + Q,
        "document_count = 28",
        "stage_functions = " + Q + PIPE.join(
            ["loading.load_all"]
            + ["stages.stage_r" + str(i).rjust(2, "0") for i in range(1, 10)]
            + ["allocate.stage_r" + str(i) for i in range(10, 15)]
            + ["publish.render"]) + Q,
        "stage_interface = " + Q + "every stage function keeps the name, the"
        + " arguments and the record shapes it shipped with" + Q,
    ])


DOCUMENT_NAMES = [
    "unit_normalization.json", "alias_resolution.jsonl",
    "expansion_ledger.csv", "config_resolution.json", "parameter_audit.csv",
    "trigger_eligibility_index.json", "dependency_graph.json",
    "cycle_break_ledger.json", "canonical_action_order.json",
    "resource_demand.csv", "window_capacity_report.csv",
    "initial_allocation.json", "displaced_action_queue.json",
    "fallback_expansion.json", "precedence_reconciliation.json",
    "final_action_order.json", "cooldown_state.csv", "derived_state.json",
    "suppression_ledger.csv", "next_state_snapshot.json",
    "per_context_manifest.json", "per_device_manifest.csv",
    "daily_automation_manifest.json", "resource_utilization_report.csv",
    "terminal_action_report.md", "audit_ledger.jsonl", "run_manifest.txt",
    "summary.json",
]

STAGE_PAPER = {sid: "spec_stage_" + sid + "_" + STAGE_TITLES[sid].replace(" ", "_")
               + ".md" for sid in STAGE_IDS}


def emit_contract(inst, dest):
    lines = ["# Daybreak routing programme contract",
             "",
             "Cycle " + inst["cycle"] + ", acquisition profile "
             + inst["profile"] + ".",
             "",
             "The router turns one directory of working papers into the",
             "twenty eight derived documents of one routing cycle. It runs in",
             "fourteen stages. Each stage has one specification paper and",
             "consumes only what the stages before it published.",
             "",
             "## Stages and their papers",
             "",
             "| stage | title | paper |",
             "| --- | --- | --- |"]
    for sid in STAGE_IDS:
        lines.append("| " + sid + " | " + STAGE_TITLES[sid] + " | `"
                     + STAGE_PAPER[sid] + "` |")
    lines += ["",
              "## Stage order",
              "",
              "A stage runs only after every stage that feeds it. The feeding",
              "relation is:",
              ""]
    for a, b in STAGE_EDGES:
        lines.append("- " + a + " feeds " + b)
    lines += ["",
              "## What the router may not do",
              "",
              "- It holds nothing about a cycle. Every identifier, count,",
              "  control value, threshold and vocabulary member is read from",
              "  the directory it is pointed at.",
              "- It uses no binary floating point anywhere in the derivation.",
              "- It writes only the derived documents, and only into the",
              "  destination it is given.",
              "- It leaves the paper directory byte for byte as it found it.",
              "- Two runs over one directory produce identical bytes, and the",
              "  same cycle under another directory name produces them again.",
              "",
              "## Papers that are not plain text",
              "",
              "- `capacity_and_intensity_workbook.xlsx` carries the per window",
              "  per device energy ceilings, the per action class surcharges,",
              "  the per capacity class window scales and the reserve share.",
              "  Several grids of the same shape are present; the live one is",
              "  the grid whose key cell equals the cycle key in",
              "  `cycle_header.json`, byte for byte. Sheet name and sheet",
              "  position say nothing about which grid is live.",
              "- `household_operations_memo.pdf` carries the four scalar",
              "  controls and the per routine occurrence cap table.",
              "- `precedence_directive.docx` carries the seven policy layers",
              "  and their ranks, the settlement key order, the mandatory",
              "  reserve share, the number of reconciliation rounds and the",
              "  layer one directive schedule.",
              "",
              "None of those values appears in any other paper.",
              ]
    write_lines(dest / "assistant_program_contract.md", lines)


def emit_lineage(inst, dest):
    lines = ["# Data lineage and recording rules",
             "",
             "## The ten recording rules",
             "",
             "Every register in this directory is written under the rules",
             "below. Each rule is a triple: the sentence that states it, the",
             "transform applied when the register was written, and the",
             "inverse the router applies when it reads it.",
             "",
             "- **RR1 revision history.** A register carries every revision of",
             "  every key. The row in force for a key is the row with the",
             "  greatest `revision` that does not exceed that key's frozen",
             "  revision. Frozen revisions live in `cycle_header.json` for the",
             "  window grid, the device register and the device policies, and",
             "  in `state_snapshot.json` for the cooldown register. Two rows",
             "  that share a key and a revision settle on the one appearing",
             "  later in the file. The greatest revision present is not the",
             "  live one unless it happens to equal the frozen revision.",
             "- **RR2 unit tokens.** A recorded quantity is a value and a unit",
             "  token. The base value is",
             "  `half_even(value * numerator / denominator)` under",
             "  `unit_registry_dictionary.toml`. A withdrawn token or a zero",
             "  denominator sets the record aside under `UNCONVERTIBLE_UNIT`.",
             "- **RR3 alias references.** A column whose name ends in `_ref`",
             "  may hold an identifier or an alias of one. Resolve it under",
             "  stage r02 before using it.",
             "- **RR4 layered absence.** A hyphen, an empty cell or an absent",
             "  JSON key records an absent field, which inherits from the next",
             "  layer down. A written zero records an explicit zero and",
             "  settles the field where it is written.",
             "- **RR5 sign columns.** A quantity that may be negative carries",
             "  its sign in a separate column holding `+` or `-`. The value",
             "  column is always the magnitude.",
             "- **RR6 delta chains.** `window_grid.csv` records each window's",
             "  start as the difference from the previous window's start, read",
             "  in ascending `ordinal`, the first difference being taken from",
             "  `cycle_header.json.origin_ms`. `context_activity_spans.tsv`",
             "  records the same way in file order, its first difference",
             "  also taken from `cycle_header.json.origin_ms`, never from",
             "  zero. A row read on its own",
             "  gives the wrong start.",
             "- **RR7 interval ends are exclusive.** Every interval in this",
             "  directory is half open. A window runs from its start inclusive",
             "  to its end exclusive; a context is active from its start",
             "  inclusive to its end exclusive; a one shot override applies",
             "  strictly before its expiry.",
             "- **RR8 pipe packed values.** `routine_defaults.toml` and",
             "  `gating_rules.toml` pack several fields into one quoted string",
             "  separated by a vertical bar. The field order is stated in the",
             "  comment at the head of each file.",
             "- **RR9 closed vocabularies.** Reason codes, layer names, edge",
             "  kinds and statuses are closed sets. Their members are listed",
             "  in `glossary_and_reason_codes.md`.",
             "- **RR10 file order settles nothing.** Except where RR1 and RR6",
             "  name it, the order rows appear in a register carries no",
             "  meaning. Every published ordering is the ordering its stage",
             "  specification states.",
             "",
             "## Paper to stage map",
             "",
             "| paper | stage it serves |",
             "| --- | --- |",
             "| `unit_registry_dictionary.toml` | r01 |",
             "| `action_catalogue.csv` | r01, r03, r09 |",
             "| `dependency_edges.tsv` | r01, r06 |",
             "| `source_priority_register.csv` | r02 |",
             "| `alias_crosswalk.tsv` | r02 |",
             "| `identifier_supplement.psv` | r02 |",
             "| `window_grid.csv` | r02, r03, r10 |",
             "| `device_register.csv` | r02 |",
             "| `context_activity_spans.tsv` | r02, r04 |",
             "| `routine_register.csv` | r03 |",
             "| `expansion_policy.yaml` | r03 |",
             "| `household_operations_memo.pdf` | r03, r09, r11, r12 |",
             "| `precedence_directive.docx` | r04, r07, r10, r12 |",
             "| `override_journal.jsonl` | r04 |",
             "| `context_policies.tsv` | r04 |",
             "| `device_policies.csv` | r04 |",
             "| `action_policies.jsonl` | r04 |",
             "| `routine_defaults.toml` | r03, r04 |",
             "| `global_defaults.yaml` | r04 |",
             "| `cooldown_register.psv` | r04 |",
             "| `precedence_and_overturn.toml` | r04, r12 |",
             "| `state_snapshot.json` | r04, r05 |",
             "| `prior_cycle_journal.jsonl` | r05 |",
             "| `prior_cycle_archive.sqlite3` | r05 |",
             "| `assistant_runtime.conf` | r05, r14 |",
             "| `cycle_break_policy.toml` | r07 |",
             "| `capacity_and_intensity_workbook.xlsx` | r09, r10, r14 |",
             "| `capacity_binding_policy.yaml` | r10 |",
             "| `state_effects.jsonl` | r13 |",
             "| `gating_rules.toml` | r14 |",
             "| `energy_ledger_history.ndjson` | r14 |",
             "| `home_topology.xml` | r14 |",
             "| `rounding_and_arithmetic_policy.yaml` | every stage |",
             "| `publication_form_rules.toml` | r14 |",
             "| `output_schema_reference.md` | r14 |",
             "| `serialisation_and_digest_contract.md` | r14 |",
             "",
             "## Reading rules for the prose papers",
             "",
             "Every paper that carries prose rather than rows is written",
             "under the ten reading rules below.",
             "",
             "- **PR1 role naming.** A file name states a role, never its",
             "  contents. The contents settle what the paper holds.",
             "- **PR2 closed vocabulary.** Every code a paper uses is a member",
             "  of a set listed in `glossary_and_reason_codes.md`.",
             "- **PR3 stated order.** Where a paper lists keys, the list order",
             "  is the order the rule is applied in.",
             "- **PR4 stated boundary.** Every interval a paper names is half",
             "  open, start inclusive and end exclusive.",
             "- **PR5 stated tie break.** Every ordering a paper states ends",
             "  in a key that cannot tie.",
             "- **PR6 stated default.** A paper that names a default names the",
             "  layer the default sits at as well.",
             "- **PR7 stated cap.** A paper that names a cap names what",
             "  happens at the cap and what happens past it.",
             "- **PR8 stated exception.** A paper that names an exception",
             "  names the rule the exception sits inside.",
             "- **PR9 stated digest scope.** A paper that names a digest names",
             "  the exact bytes it is taken over and the moment it is taken.",
             "- **PR10 stated empty form.** A paper that names a document",
             "  names the form that document takes when its group is empty.",
             "",
             "## Papers that govern nothing",
             "",
             "`readings_not_in_force.md` and `worked_examples.md` are reading",
             "aids. `known_traps_and_footguns.md` is a reading aid. They",
             "settle no value; the papers they describe do.",
             "",
             "## Rows that govern nothing",
             "",
             "Several registers carry retired rows so that the live rows are",
             "not the only rows. A row is retired when its status column says",
             "so, when its revision exceeds the frozen revision for its key,",
             "when its identifier carries a `hist` or `retired` or `void` or",
             "`spare` stem, or when the register it sits in is not named for",
             "the stage in the map above. Retired rows are read and then not",
             "used; they are not deleted from the count of rows read.",
             ]
    write_lines(dest / "data_lineage.md", lines)


def emit_glossary(inst, dest):
    lines = ["# Glossary and closed vocabularies",
             "",
             "## Reason codes set at intake",
             ""]
    for code in QUARANTINE_REASONS + ["UNRESOLVED_ACTION",
                                      "OCCURRENCE_CAP_ZERO"]:
        lines.append("- `" + code + "`")
    lines += ["", "## Reason codes set after intake", ""]
    for code in WITHHELD_REASONS + ["CAPACITY_DISPLACED", "UNKNOWN_CEILING",
                                    "FALLBACK_DISPLACED", "READMITTED"]:
        lines.append("- `" + code + "`")
    lines += ["", "## Alias decision statuses", "",
              "- `bound` the alias binds to the canonical name shown",
              "- `collision` a stronger source already bound this alias",
              "- `self` the alias and the canonical name are the same text",
              "- `cycle` following the alias returned to a name already seen",
              "",
              "## Edge drop reasons", "",
              "- `SELF_EDGE`", "- `DUPLICATE_EDGE`",
              "- `UNRESOLVED_ENDPOINT`", "- `UNCONVERTIBLE_UNIT`",
              "",
              "## Policy layers", "",
              "Their ranks are in `precedence_directive.docx` part A; the",
              "list below is in no particular order of strength.", ""]
    for name in sorted(LAYER_ORDER):
        lines.append("- `" + name + "`")
    lines += ["- `class_floor` is not a layer. It is the floor stage r04",
              "  applies to the resolved cooldown after the layers have",
              "  settled it, and it is what the audit records as the winning",
              "  layer when the floor raised the value.",
              "",
              "## Policy fields", ""]
    for field in POLICY_FIELDS:
        lines.append("- `" + field + "`")
    lines += ["",
              "## Stage identifiers", ""]
    for sid in STAGE_IDS:
        lines.append("- `" + sid + "` " + STAGE_TITLES[sid])
    write_lines(dest / "glossary_and_reason_codes.md", lines)


def emit_readings(inst, dest):
    lines = ["# Readings this household does not support",
             "",
             "Each entry names a reading of these papers that is plausible and",
             "wrong, beside the reading in force. The list is a reading aid,",
             "not a defect list: most of these readings appear nowhere in the",
             "shipped project, and a reading absent from this list may still",
             "be wrong.",
             "",
             "1. **Not in force**: the last row for a key in a register wins.",
             "   **In force**: only when two rows share a key *and* a",
             "   revision (RR1).",
             "2. **Not in force**: an empty cell means zero. **In force**: an",
             "   empty cell means the field is absent and inherits from the",
             "   next layer down; a written zero settles the field (RR4).",
             "3. **Not in force**: the greatest revision in a register is the",
             "   live one. **In force**: the live row is the greatest revision",
             "   at or below the frozen revision for that key (RR1).",
             "4. **Not in force**: a context whose start equals its end is",
             "   active at that instant. **In force**: the interval is empty",
             "   and the context layer does not apply.",
             "5. **Not in force**: an instance whose elapsed time since the",
             "   last firing exactly equals its cooldown is still cooling",
             "   down. **In force**: the cooldown has elapsed and the instance",
             "   is eligible.",
             "6. **Not in force**: a carried cooldown replaces the resolved",
             "   one. **In force**: the greater of the two applies.",
             "7. **Not in force**: a soft edge withholds its dependent when",
             "   the prerequisite does not fire. **In force**: soft edges only",
             "   order; only hard edges withhold.",
             "8. **Not in force**: an action whose demand exactly equals the",
             "   pool is displaced. **In force**: equality fits, binds the",
             "   pool and does not displace.",
             "9. **Not in force**: a demand exactly at the implausibility",
             "   threshold is quarantined. **In force**: only a demand above",
             "   it is.",
             "10. **Not in force**: a displaced action is discarded. **In",
             "    force**: it is displaced, and its fallback chain is",
             "    consulted.",
             "11. **Not in force**: mandatory instances draw after the",
             "    discretionary selection. **In force**: they draw first,",
             "    before the reserve is withheld.",
             "12. **Not in force**: an alias that maps to itself is a cycle.",
             "    **In force**: it is a self alias and is ignored.",
             "13. **Not in force**: a binding resolved through several aliases",
             "    records one hop per link. **In force**: hops is one for",
             "    every binding that resolves to another name, zero for one",
             "    that resolves to itself.",
             "14. **Not in force**: a dependency cycle is an error. **In",
             "    force**: cycles are legal and are settled one edge at a",
             "    time under the directive's key order.",
             "15. **Not in force**: a gate key written at the very instant of",
             "    the gated trigger counts. **In force**: only a write",
             "    strictly before the trigger counts.",
             ]
    write_lines(dest / "readings_not_in_force.md", lines)


def emit_traps(inst, dest):
    lines = ["# Known traps and footguns",
             "",
             "Each item names a place where the data of this household is",
             "shaped in a way a casual reader can trip on. None of them names",
             "a rule; the rule for each is in the stage papers and in",
             "`data_lineage.md`.",
             "",
             "- `window_grid.csv` records a start difference, not a start, and",
             "  its revisions record different differences and spans.",
             "- `identifier_supplement.psv` repeats aliases that",
             "  `alias_crosswalk.tsv` already binds, to different targets.",
             "- `alias_crosswalk.tsv` carries alias rings of more than one",
             "  length.",
             "- `device_policies.csv` leaves cells empty.",
             "- `cooldown_register.psv` carries revisions above every frozen",
             "  revision this cycle uses.",
             "- The workbook carries more than one grid of the same shape.",
             "- Some cells of the live grid record a written `0` and some",
             "  record the absent sentinel.",
             "- Some registers open with a byte order mark, some end their",
             "  lines with a carriage return, and some carry quoted fields.",
             "- `state_effects.jsonl` and `gating_rules.toml` carry rows for",
             "  `AC-000` and other names the catalogue does not hold.",
             "- The energy ledger carries every prior cycle, in no particular",
             "  order.",
             "- The topology carries retired circuit rows whose role is not",
             "  `member`.",
             "- Some routines have a period of zero.",
             ]
    write_lines(dest / "known_traps_and_footguns.md", lines)


def emit_schema(inst, dest):
    lines = ["# Output schema reference",
             "",
             "Twenty eight documents. Every one is published for every cycle,",
             "including the cycles where its group is empty.",
             "",
             "## CSV documents",
             "",
             "Header line exactly as shown, columns in this order, one row per",
             "record, rows in the stated order.",
             "",
             "### `expansion_ledger.csv`",
             "`routine_id,instance_id,action_id,occurrence_index,trigger_ms,"
             "window_id,status,reason`",
             "One row per generated occurrence and one row per routine",
             "withheld before it generates any. A routine that is not withheld",
             "but generates no occurrence carries no row. `status` is",
             "`expanded` or `withheld`. `reason` is",
             "empty on an expanded row. Ordered by routine_id then",
             "occurrence_index; a withheld routine carries occurrence_index",
             "`-1` and an empty instance_id and window_id.",
             "",
             "### `parameter_audit.csv`",
             "`instance_id,field,value,winning_layer`",
             "One row per instance per policy field, fields in the order",
             "`tier`, `intensity_bp`, `cooldown_ms`, `mandatory`,",
             "`max_occurrences`, `suppress`, `fallback_chain`. Booleans are",
             "`true` and `false`; a fallback chain is joined with `;`.",
             "Ordered by instance_id ascending, then by the field order above.",
             "",
             "### `resource_demand.csv`",
             "`window_id,device_id,instance_id,action_id,base_energy_mwh,"
             "intensity_bp,surcharge_bp,window_scale_bp,demand_mwh`",
             "One row per instance that reached stage r09 and was not set",
             "aside. Ordered by window ordinal, then device_id, then",
             "instance_id.",
             "",
             "### `window_capacity_report.csv`",
             "`window_id,device_id,ceiling_mwh,reserve_mwh,mandatory_mwh,"
             "allocated_mwh,pool_remaining_mwh,overrun`",
             "One row per window and device that carried demand in r10",
             "against a ceiling row, in the group order stage r10 states. A",
             "group displaced under `UNKNOWN_CEILING` has no row. `overrun` is",
             "`yes` or `no`.",
             "`allocated_mwh` is the discretionary energy allocated in r10,",
             "which is the pool at the start of the discretionary phase less",
             "what remained.",
             "",
             "### `cooldown_state.csv`",
             "`action_id,cooldown_until_ms,source_layer`",
             "One row per action that fired in r13, ordered by action_id.",
             "`source_layer` is the literal `resolved`.",
             "",
             "### `suppression_ledger.csv`",
             "`instance_id,reason,stage`",
             "One row per instance set aside or withheld or displaced or",
             "withdrawn or readmitted, naming the stage that did it. The",
             "fallback outcomes are settled together: every terminal of r11",
             "and of r12 names `r12`. Rows are sorted as whole tuples",
             "ascending.",
             "",
             "### `per_device_manifest.csv`",
             "`device_id,circuit_id,instances,demand_mwh`",
             "One row per device carrying at least one surviving instance,",
             "ordered by device_id. `circuit_id` is empty when the topology",
             "carries no member row for that device.",
             "",
             "### `resource_utilization_report.csv`",
             "`circuit_id,device_id,ceiling_mwh,allocated_mwh,"
             "utilisation_ratio,prior_cycle_mwh,delta_mwh`",
             "One row per device that appears either in the surviving plan or",
             "as a circuit member, ordered by circuit_id then device_id.",
             "`ceiling_mwh` is the sum of that device's ceilings over every",
             "window. `utilisation_ratio` is allocated over ceiling at twelve",
             "decimal places, and is twelve zeros after the point when the",
             "ceiling is zero. `prior_cycle_mwh` is the consumption recorded",
             "for that device at the greatest cycle index in the energy",
             "ledger, or zero when the ledger carries none.",
             "",
             "## JSON documents",
             "",
             "Two space indent, keys sorted, ASCII only, one trailing line",
             "feed.",
             "",
             "### `unit_normalization.json`",
             "`{cycle_key, base_units, unit_counts, totals, quarantined}`.",
             "`unit_counts` maps every unit token seen in the action catalogue",
             "and the dependency edges to the number of recorded quantities",
             "that carried it. `totals` is",
             "`{duration_ms, energy_mwh, weight_bp}`: the summed durations and",
             "energies of the catalogue rows that converted, and the summed",
             "strengths of the edges that converted. `quarantined` is a list",
             "of `{record, field, unit, reason}` sorted by record then field.",
             "",
             "### `config_resolution.json`",
             "`{instances, layer_ranks, settled_by_layer,"
             " live_device_policy_revisions, cooldown_floors_ms, reserve_bp}`.",
             "`settled_by_layer` counts, per layer name and for `class_floor`,",
             "how many instance fields that layer settled.",
             "`live_device_policy_revisions` maps each device to the revision",
             "of its `device_policies.csv` row in force under RR1.",
             "",
             "### `trigger_eligibility_index.json`",
             "`{eligible, withheld, counts}`. `eligible` is instance ids",
             "ascending. `withheld` is `{instance_id, reason}` sorted.",
             "`counts` maps reason to count.",
             "",
             "### `dependency_graph.json`",
             "`{nodes, edges, dropped}`. `edges` are",
             "`{prereq, dependent, strength_bp, declared_seq, kind}` ordered by",
             "prereq then dependent. `dropped` are",
             "`{declared_seq, prereq, dependent, reason}` sorted by",
             "declared_seq then reason.",
             "",
             "### `cycle_break_ledger.json`",
             "`{rounds, removals, surviving_edges}`. Each removal is",
             "`{round, cycle, removed_prereq, removed_dependent, strength_bp,"
             " dependent_tier, declared_seq, key_settled_at}` in the order the",
             "removals happened. `cycle` lists the nodes of the settled cycle",
             "in the order the search found them, without repeating the first.",
             "",
             "### `canonical_action_order.json`",
             "`{action_order, instance_order, withheld}`.",
             "",
             "### `initial_allocation.json`",
             "`{count, allocated}` where each entry is",
             "`{instance_id, window_id, device_id}` sorted by instance_id.",
             "",
             "### `displaced_action_queue.json`",
             "`{count, displaced}` where each entry is",
             "`{instance_id, reason}` sorted.",
             "",
             "### `fallback_expansion.json`",
             "`{proposals, terminal}`. Each proposal is",
             "`{instance_id, action_id, stands_in_for, window_id, device_id,"
             " demand_mwh}` sorted by instance_id.",
             "",
             "### `precedence_reconciliation.json`",
             "`{round_cap, groups, overturned}`. Each group is",
             "`{window_id, device_id, round, proposals, incumbents, kept,"
             " pool_remaining_mwh}` sorted by round, then window_id, then",
             "device_id; `incumbents` counts the holders the round started",
             "with. Each overturned entry is",
             "`{instance_id, window_id, device_id, round}`. `round_cap` is the",
             "directive's cap.",
             "",
             "### `final_action_order.json`",
             "`{count, order}` in the final order stage r14 states.",
             "",
             "### `derived_state.json`",
             "`{state, set_at}`. `state` maps key to value. `set_at` maps key",
             "to `{trigger_ms, action_id}` for the instance that last wrote it.",
             "",
             "### `next_state_snapshot.json`",
             "`{cycle_key, cycle_index, actions, oneshot_remaining, state}`.",
             "`cycle_index` is the runtime's cycle index plus one. `actions`",
             "maps action_id to `{last_fired_ms, cooldown_until_ms}` over the",
             "actions that fired in the recomputed state pass. `state` is the",
             "recomputed state.",
             "",
             "### `per_context_manifest.json`",
             "`{contexts}` mapping context_id to `{instances, demand_mwh}`,",
             "instances sorted ascending.",
             "",
             "### `daily_automation_manifest.json`",
             "`{cycle_key, profile, windows, totals}`. Each window entry is",
             "`{window_id, ordinal, instances, demand_mwh}` in window ordinal",
             "order. `totals` is",
             "`{instances, demand_mwh, terminal, readmitted}`.",
             "",
             "### `summary.json`",
             "`{cycle_key, profile, core_digest, publication_digest,"
             " control_totals}`. `control_totals` carries `actions_read`,",
             "`aliases_bound`, `instances_expanded`, `instances_eligible`,",
             "`edges_kept`, `cycles_settled`, `demand_rows`,",
             "`initial_allocations`, `displaced`, `fallback_proposals`,",
             "`overturned`, `final_instances`, `readmitted`, `terminal` and",
             "`total_demand_mwh`.",
             "",
             "## JSONL documents",
             "",
             "One compact object per line, keys sorted, no spaces after the",
             "separators. An empty group publishes a file of zero bytes.",
             "",
             "### `alias_resolution.jsonl`",
             "`{alias, canonical, kind, source, hops, status}`, one per",
             "binding decision, sorted by alias then source then status.",
             "",
             "### `audit_ledger.jsonl`",
             "`{stage, records}` for each of the fourteen stages in stage",
             "order. `records` is the size of that stage's principal result:",
             "actions read, alias decisions, instances expanded, instances",
             "resolved, instances eligible, edges kept, cycle removals,",
             "instances ordered, demand rows, initial allocations, fallback",
             "proposals, survivors after overturn, instances in the r13 order,",
             "and instances in the final order.",
             "",
             "## Markdown and text documents",
             "",
             "### `terminal_action_report.md`",
             "A level one heading `# Terminal actions for cycle <cycle key>`,",
             "a blank line, a two column table with the header row",
             "`| instance_id | reason |` and the separator row",
             "`| --- | --- |`, one row per terminal instance sorted by",
             "instance_id, a blank line, and the line",
             "`Total terminal instances: <n>`.",
             "",
             "### `run_manifest.txt`",
             "One line per document other than `run_manifest.txt` and",
             "`summary.json`, in file name order, each `sha256` then two",
             "spaces then the file name. Then the line `core <hex>` and the",
             "line `publication <hex>`.",
             "",
             "## The repair record",
             "",
             "Four further documents accompany the twenty eight and the",
             "archive. They record the repair rather than the cycle. The",
             "first two carry only a form; the register and the notes carry",
             "facts, and those facts are checked.",
             "",
             "### `build_report.json`",
             "A JSON object, not an array and not empty.",
             "",
             "### `selftest.json`",
             "A JSON object, not an array and not empty, recording the run of",
             "the shipped suite.",
             "",
             "### `defect_register.md`",
             "A markdown table carrying one row per repaired defect, each row",
             "beginning with `|`, under the header row",
             "`| defect | stage | function | rule restored |` and the usual",
             "`| --- | --- | --- | --- |` separator. A register naming no",
             "defect carries no row.",
             "",
             "- `defect` is the solver's own label for the departure.",
             "- `stage` is the stage, `r01` to `r14`, whose paper states the",
             "  rule the shipped code departed from. A departure in a reader",
             "  shared by every stage names the first stage that reads the",
             "  affected paper.",
             "- `function` names the top level function of the shipped",
             "  project that carried the departure, as `<module>.<function>`",
             "  with the module named without its package or suffix, for",
             "  example `stages.stage_r03`. Two departures in one function",
             "  are two rows.",
             "- `rule restored` states the rule in a sentence.",
             "",
             "The register is compared with the departures the shipped",
             "source actually carries. A row naming a function of the",
             "shipped project that carries no departure is a wrong entry, as",
             "is a departure left out.",
             "",
             "### `verification_notes.md`",
             "At least three non blank lines, one per check the solver made.",
             "Among them, for the cycle in `/app/data`, the line",
             "`last_window_start_ms <n>` giving the start of the window with",
             "the greatest ordinal, and for each distinct value of the",
             "`reason` column of `suppression_ledger.csv` the line",
             "`set_aside <REASON> <n>` giving the number of rows carrying it.",
             "Each such line stands alone, with nothing else on it.",
             ]
    write_lines(dest / "output_schema_reference.md", lines)


def emit_serialisation(inst, dest):
    write_lines(dest / "serialisation_and_digest_contract.md", [
        "# Serialisation and digest contract",
        "",
        "- Every document is UTF-8 with line feed endings and exactly one",
        "  trailing line feed, except a JSONL document with no records, which",
        "  is zero bytes.",
        "- JSON is `indent=2`, `sort_keys=true`, `ensure_ascii=true`.",
        "- JSONL is one object per line, `sort_keys=true`, separators `,` and",
        "  `:` with no spaces.",
        "- CSV is comma separated with no quoting. No published field carries",
        "  a comma. A CSV whose group is empty is published as its header line",
        "  alone.",
        "- Booleans publish as `true` and `false`.",
        "- Whole quantities publish as integers in the base unit of their",
        "  stage. Ratios publish at exactly twelve decimal places. Negative",
        "  zero never appears.",
        "",
        "## Digests",
        "",
        "- The core digest is the SHA-256, in lower case hexadecimal, of the",
        "  concatenated bytes of `unit_normalization.json`,",
        "  `canonical_action_order.json`, `final_action_order.json`,",
        "  `daily_automation_manifest.json` and `next_state_snapshot.json`, in",
        "  that order.",
        "- The manifest body is one line per document other than",
        "  `run_manifest.txt` and `summary.json`, in ascending file name",
        "  order, each being the SHA-256 of that document's bytes, then two",
        "  spaces, then the file name.",
        "- The publication digest is the SHA-256 of the manifest body: every",
        "  body line followed by one line feed, taken before the two trailer",
        "  lines are appended.",
        "- `run_manifest.txt` is the manifest body followed by `core <hex>`",
        "  and `publication <hex>`.",
        "- `summary.json` carries both digests and is written last.",
        "- Both digests are taken over bytes already written. Nothing is",
        "  recomputed after a digest is taken.",
        "",
        "## Reading the working papers",
        "",
        "- A text paper may open with a UTF-8 byte order mark. The mark is",
        "  not part of the paper: it never belongs to the first line, the",
        "  first header name or the first field.",
        "- A line may end with a carriage return and a line feed or with a",
        "  line feed alone. The carriage return is not part of the last",
        "  field.",
        "- In a delimited register (`.csv`, `.tsv`, `.psv`) a field that",
        "  opens with a double quote runs to its closing double quote. A",
        "  separator inside the quotes is text, a doubled double quote",
        "  inside them is one literal double quote, and the enclosing",
        "  quotes are not part of the value. Every other field runs from",
        "  separator to separator exactly as written.",
        "- A workbook grid's key cell is compared with",
        "  `cycle_header.json.cycle_key` byte for byte. A key cell that",
        "  differs in case, or carries a space the cycle key does not,",
        "  names some other cycle.",
    ])


def emit_worked(inst, dest):
    units = UNIT_TABLE
    lines = ["# Worked examples",
             "",
             "Every example below is arithmetic on invented values. None of",
             "them is a value from this cycle.",
             "",
             "## RR2, converting a recorded quantity",
             "",
             "`7.5 kj` with `kj = mwh|2500|9|live` is",
             "`half_even(15/2 * 2500/9) = half_even(6250/3) =",
             " half_even(2083.333...) = 2083 mwh`.",
             "",
             "`4.5 tick` with `tick = ms|125|2|live` is",
             "`half_even(9/2 * 125/2) = half_even(1125/4) =",
             " half_even(281.25) = 281 ms`.",
             "",
             "`2.5 beat` with `beat = ms|1875|4|live` is",
             "`half_even(5/2 * 1875/4) = half_even(9375/8) =",
             " half_even(1171.875) = 1172 ms`.",
             "",
             "A halfway case: `1 tick` is `half_even(125/2) =",
             " half_even(62.5) = 62`, because 62 is even. `3 tick` is",
             "`half_even(375/2) = half_even(187.5) = 188`, because 188 is",
             "even. Rounding half up would give 63 and 188.",
             "",
             "`900 pulse` with `pulse = mwh|1|0|withdrawn` converts to",
             "nothing: the record is set aside under `UNCONVERTIBLE_UNIT`.",
             "",
             "## RR6, reading a delta chain",
             "",
             "With `origin_ms = 1800000` and the live rows for the first",
             "three windows recording start differences of `0 ms`, `120 min`",
             "and `90 min`, the starts are `1800000`, `9000000` and",
             "`14400000`. Reading",
             "the third row alone and taking `90 min` as a start would place",
             "that window at `5400000`.",
             "",
             "## RR1, picking the live row",
             "",
             "A key whose frozen revision is `9` and whose register carries",
             "revisions `3, 7, 9, 12, 14` settles on revision `9`. If the",
             "register carried `3, 7, 12, 14` instead it would settle on `7`.",
             "The greatest revision, `14`, is never the answer unless the",
             "frozen revision is at least `14`.",
             "",
             "## RR4, absence against an explicit zero",
             "",
             "A device policy row with an empty `cooldown_value` does not",
             "settle the cooldown; resolution falls to the action layer. A",
             "device policy row with `cooldown_value` `0` and",
             "`cooldown_unit` `s` settles the cooldown at zero milliseconds",
             "and the audit records `device` as the winning layer.",
             "",
             "## Stage r09, the two products",
             "",
             "An action of `3333 mwh` at a resolved intensity of `11000 bp`",
             "with a class surcharge of `-500 bp` and a window scale of",
             "`12500 bp` gives an effective intensity of `10500 bp`, then",
             "`half_even(3333 * 10500 / 10000) = half_even(3499.65) = 3500`,",
             "then `half_even(3500 * 12500 / 10000) = half_even(4375) =",
             " 4375 mwh`. Multiplying `3333 * 10500 * 12500` and rounding",
             "once gives `4374.5625` rounded to `4375` here, but the two",
             "rounding points and the one rounding point disagree in general;",
             "the two rounding points are the contract.",
             "",
             "## Stage r10, the pool",
             "",
             "A ceiling of `40000 mwh` with a reserve of `750 bp` withholds",
             "`half_even(40000 * 750 / 10000) = 3000 mwh`. If mandatory",
             "actions drew `1200 mwh`, the withheld share falls to",
             "`3000 - 1200 = 1800`, the remainder is `40000 - 1200 = 38800`,",
             "and the discretionary pool is `38800 - 1800 = 37000 mwh`. If",
             "mandatory actions had drawn `5000 mwh`, the withheld share",
             "would be zero and the pool would be `35000 mwh`.",
             "",
             "## Stage r12, an overturn",
             "",
             "A pool of `1000 mwh` first offered to incumbents `X` at tier 5",
             "demanding `600` and `Y` at tier 6 demanding `300` takes both.",
             "If `Z`, a fallback at tier 2 demanding `700`, is proposed for",
             "the same window and device, the second round orders `Z`, `X`,",
             "`Y` and takes `Z` and `Y`; `X` is overturned and is terminal.",
             "The first round's allocation was correct on its own inputs and",
             "wrong once the proposal existed.",
             "",
             "## Stage r13, one shot consumption",
             "",
             "An override with one remaining that applied to an instance",
             "which r12 kept and r14 withdrew is not consumed. The",
             "next snapshot still records one remaining.",
             ]
    write_lines(dest / "worked_examples.md", lines)


def _spec(dest, sid, body):
    lines = ["# Stage " + sid + " - " + STAGE_TITLES[sid], ""]
    feeds = [a for a, b in STAGE_EDGES if b == sid]
    into = [b for a, b in STAGE_EDGES if a == sid]
    lines.append("Fed by: " + (", ".join(feeds) if feeds else "nothing") + ".")
    lines.append("Feeds: " + (", ".join(into) if into else "nothing") + ".")
    lines.append("")
    lines.extend(body)
    write_lines(dest / STAGE_PAPER[sid], lines)


def emit_stage_specs(inst, dest):
    _spec(dest, "r01", [
        "Read `action_catalogue.csv` and `dependency_edges.tsv` and carry",
        "every recorded quantity into its base unit under RR2.",
        "",
        "- A catalogue row whose energy or duration cannot be carried is set",
        "  aside under `UNCONVERTIBLE_UNIT` and takes no further part. Both",
        "  its unit tokens are still counted.",
        "- Edge strength is recorded once per declared sequence. Every row",
        "  of `dependency_edges.tsv` is counted, and the strength recorded",
        "  for a declared sequence is the converted strength of the last of",
        "  its rows, in file order, whose strength can be carried. A declared",
        "  sequence none of whose rows can be carried records no strength,",
        "  and its edges are dropped in r06 under the same reason.",
        "- `unit_counts` counts one for every recorded quantity, by the token",
        "  it carried, over the catalogue energies, the catalogue durations",
        "  and the edge strengths.",
        "- `totals.energy_mwh` and `totals.duration_ms` sum the catalogue rows",
        "  that converted. `totals.weight_bp` sums the edge strengths that",
        "  converted.",
        "- Publish `unit_normalization.json`.",
    ])
    _spec(dest, "r02", [
        "Bind every alias and resolve every `_ref` column.",
        "",
        "- Take every identifier source named in `source_priority_register.csv`",
        "  whose status is `in_force`: `alias_crosswalk.tsv` and",
        "  `identifier_supplement.psv`. A source not named there, or named and",
        "  withdrawn, contributes nothing.",
        "- Order the rows of all in force sources by source rank ascending,",
        "  then declared sequence ascending, then alias ascending.",
        "- Walk that order. A row whose alias equals its canonical name is a",
        "  `self` decision and binds nothing. A row whose alias is already",
        "  bound is a `collision` decision and binds nothing. Any other row is",
        "  a `bound` decision and binds the alias.",
        "- Resolving a name follows bindings until a name that is not bound is",
        "  reached, up to the alias hop cap. If a name repeats before then,",
        "  the resolution is a `cycle` and the name resolves to itself. A",
        "  repeat reached by the very hop that uses up the cap still counts.",
        "  When the cap is used up with no repeat, the name reached by then",
        "  is the resolution, even though it is still bound.",
        "- A `bound` or `cycle` decision's `hops` is `0` when the alias",
        "  resolves to itself and `1` otherwise, and its `canonical` is the",
        "  name the alias finally resolves to, not the name its own row",
        "  recorded. A `self` or `collision` decision binds nothing, so it",
        "  keeps the canonical its own row recorded and its `hops` is `0`.",
        "- Build the window grid from `window_grid.csv` under RR1 and RR6,",
        "  the device grid from `device_register.csv` under RR1, and the",
        "  context grid from `context_activity_spans.tsv` under RR5 and RR6.",
        "  A context row whose identifier is not a bare context id carries the",
        "  chain forward and is not itself a context.",
        "- Publish `alias_resolution.jsonl`.",
    ])
    _spec(dest, "r03", [
        "Expand every routine into the occurrences it fires this cycle,",
        "under `expansion_policy.yaml`.",
        "",
        "- A routine whose `enabled` column is not `yes` is withheld under",
        "  `RETIRED_ROUTINE`.",
        "- Resolve `action_ref`. A reference that does not resolve to a",
        "  catalogue action is withheld under `UNRESOLVED_ACTION`.",
        "- Carry the anchor, period, span start and span end under RR2, and",
        "  apply the anchor sign under RR5. A quantity that cannot be carried",
        "  withholds the routine under `UNCONVERTIBLE_UNIT`.",
        "- Resolve the occurrence cap from three sources in order: the memo",
        "  cap table, the routine layer `max_occurrences`, the memo default.",
        "  The first source that records a cap settles it. A cap of zero or",
        "  less withholds the routine under `OCCURRENCE_CAP_ZERO`.",
        "- Generate `trigger = anchor + step * period` for `step` from zero.",
        "  Stop when the trigger reaches the span end, when the cap is met, or",
        "  after 512 steps. A trigger below the span start is discarded and",
        "  does not consume the cap. A period of zero generates exactly one",
        "  trigger, at the anchor, which the span rules then keep or discard.",
        "- The occurrence index is the ordinal of the surviving occurrence",
        "  from zero. The instance id is the routine id, a `#`, and the index",
        "  in two digits.",
        "- Place the occurrence in the window whose start is at or below the",
        "  trigger and whose end is above it. Where two windows qualify, the",
        "  one with the lower ordinal takes it. A trigger matching no window is",
        "  withheld under `OUT_OF_DAY` and still consumes the cap.",
        "- Publish `expansion_ledger.csv`.",
    ])
    _spec(dest, "r04", [
        "Resolve the effective policy of every expanded instance.",
        "",
        "- The layers and their ranks are in `precedence_directive.docx`",
        "  part A, rank 1 the strongest. The fields are in",
        "  `precedence_and_overturn.toml`. The layers are described below by",
        "  name; this paper does not rank them.",
        "- The mandatory layer applies when the directive schedule carries a",
        "  row for this instance's action inside this instance's window. Among",
        "  several such rows the greatest `seq` wins. The row records `tier`",
        "  and `mandatory` and nothing else.",
        "- The oneshot layer applies when an override for this action has",
        "  remaining above zero and the trigger is strictly before its expiry.",
        "  Remaining is read from `state_snapshot.json.oneshot_remaining`,",
        "  which outranks the journal's own field. Among several applicable",
        "  overrides the least override id wins. The override records only the",
        "  fields it carries.",
        "- The context layer applies when the instance's resolved context is",
        "  active at the trigger, start inclusive and end exclusive. A context",
        "  whose start equals its end is never active.",
        "- The device layer is the live revision of `device_policies.csv` for",
        "  the instance's resolved device, under RR1 with the device frozen",
        "  revisions. Empty cells are absent fields.",
        "- The action layer is `action_policies.jsonl` for the instance's",
        "  action. The routine layer is `routine_defaults.toml` for the",
        "  instance's routine, packed under RR8 as",
        "  `tier|intensity_bp|cooldown_min|max_occurrences`. The global layer",
        "  is `global_defaults.yaml` and records every field.",
        "- For each field, the strongest applicable layer that records it",
        "  settles it. A layer that does not record a field does not settle it.",
        "- `layer_ranks` in `config_resolution.json` carries the directive's",
        "  rank for every layer, keyed by layer name.",
        "- After the layers have settled the cooldown, raise it to the live",
        "  class floor in `cooldown_register.psv` for the action's class, if",
        "  the floor is greater. The floor's live row is chosen under RR1",
        "  against `state_snapshot.json.frozen_revision_cooldown_register`.",
        "  When the floor raised the value, the winning layer recorded is",
        "  `class_floor`.",
        "- Publish `config_resolution.json` and `parameter_audit.csv`.",
    ])
    _spec(dest, "r05", [
        "Decide which expanded instances are eligible before any capacity is",
        "considered.",
        "",
        "- `last_fired_ms` for an action is the snapshot value when the",
        "  snapshot records one, otherwise the `last_fired_ms` of that action",
        "  in the archive table named by `assistant_runtime.conf`, otherwise",
        "  it is absent.",
        "- `suppressed_until_ms` is the snapshot value or zero.",
        "- A carried cooldown is the greatest `carried_cooldown` in",
        "  `prior_cycle_journal.jsonl` whose `cycle_index` equals the runtime's",
        "  preceding cycle index, for this action. When one exists the",
        "  cooldown in force is the greater of the resolved cooldown and the",
        "  carried one.",
        "- An instance is withheld under `SUPPRESSED` when its resolved",
        "  `suppress` is true, or when its trigger is below",
        "  `suppressed_until_ms`.",
        "- An instance is withheld under `COOLDOWN` when a last fired time is",
        "  known and `trigger - last_fired` is below the cooldown in force.",
        "  Equality is eligible.",
        "- Publish `trigger_eligibility_index.json`.",
    ])
    _spec(dest, "r06", [
        "Build the dependency graph over actions.",
        "",
        "- Resolve both endpoints of every edge under r02.",
        "- Every edge takes the strength r01 recorded for its declared",
        "  sequence. Drop an edge whose declared sequence recorded no",
        "  strength, under `UNCONVERTIBLE_UNIT`.",
        "- Drop an edge either of whose endpoints is not a catalogue action,",
        "  under `UNRESOLVED_ENDPOINT`.",
        "- Drop an edge whose endpoints are the same action, under",
        "  `SELF_EDGE`.",
        "- When two edges share a prereq and a dependent, keep one: its",
        "  strength is the greater of the two and its declared sequence is the",
        "  lesser. The later row is recorded as `DUPLICATE_EDGE`.",
        "- Publish `dependency_graph.json`.",
    ])
    _spec(dest, "r07", [
        "Settle every cycle in the dependency graph.",
        "",
        "- Cycles are legal. Find one under `cycle_break_policy.toml`, remove",
        "  exactly one of its edges, and repeat until no cycle remains.",
        "- The removable edge is chosen under the key order in",
        "  `precedence_directive.docx` part B.",
        "- The tier of a dependent action is the least resolved tier over the",
        "  eligible instances of that action. An action with no eligible",
        "  instance takes the global tier.",
        "- `key_settled_at` is the ordinal of the first key in that order",
        "  whose values are not all equal across all of the cycle's edges.",
        "  It is a property of the cycle, not of the removed edge: a key on",
        "  which the removed edge ties with some edges but not with others",
        "  still settles the cycle. When the first three keys tie across",
        "  every edge of the cycle the text key settles it and",
        "  `key_settled_at` is `4`.",
        "- The declared sequence is not unique. Rows of",
        "  `dependency_edges.tsv` that describe different edges may share one,",
        "  and r06 keeps them all, each at the strength r01 recorded for that",
        "  declared sequence.",
        "- Publish `cycle_break_ledger.json`.",
    ])
    _spec(dest, "r08", [
        "Put the surviving graph and the eligible instances in canonical",
        "order.",
        "",
        "- Order the actions by Kahn's method over the surviving edges: at",
        "  each step take the least action identifier among those with no",
        "  unsatisfied prerequisite. Every catalogue action appears, including",
        "  actions no edge touches.",
        "- Only an edge whose kind is `hard` imposes an instance level",
        "  prerequisite. A `soft` or `advisory` edge orders the graph and",
        "  withholds nothing.",
        "- An eligible instance whose action has a hard prerequisite with no",
        "  eligible instance at or before its own trigger is withheld under",
        "  `PREREQ_MISSING`. Withholding one instance can withhold another;",
        "  repeat until nothing changes.",
        "- Order the surviving instances by trigger ascending, then by the",
        "  action's position in the action order, then by instance id.",
        "- Publish `canonical_action_order.json`.",
    ])
    _spec(dest, "r09", [
        "Compute the energy demand of every ordered instance.",
        "",
        "- The effective intensity is the resolved intensity plus the class",
        "  surcharge for the action's class from the workbook, floored at",
        "  zero. The surcharge may be negative.",
        "- The window scale is the workbook scale for the window's capacity",
        "  class.",
        "- The demand is",
        "  `half_even(half_even(energy * effective_intensity / 10000)",
        "  * window_scale / 10000)`. Both roundings happen. The first result",
        "  is never carried unrounded into the second product.",
        "- An instance whose demand exceeds the memo's implausible demand",
        "  ceiling is set aside under `IMPLAUSIBLE_DEMAND` and takes no",
        "  further part.",
        "- Publish `resource_demand.csv`.",
    ])
    _spec(dest, "r10", [
        "Bind the demand against the ceilings, under",
        "`capacity_binding_policy.yaml`.",
        "",
        "- Group the demand by window and device. Take the groups in window",
        "  ordinal order, then device identifier order.",
        "- The ceiling is the live workbook grid's value for that window and",
        "  device, carried under RR2. A group with no ceiling row displaces",
        "  every instance in it under `UNKNOWN_CEILING` and writes no row to",
        "  `window_capacity_report.csv`. A ceiling cell recording the absent",
        "  sentinel is read under RR4 as no ceiling row; a written `0` is a",
        "  ceiling of zero. The utilisation report sums an absent cell as",
        "  zero.",
        "- The reserve is `half_even(ceiling * reserve_bp / 10000)` with the",
        "  reserve share from the directive part C.",
        "- Mandatory instances draw first, in canonical order, against the",
        "  whole ceiling. When their total exceeds the ceiling the group is",
        "  flagged `overrun` and the remainder is zero.",
        "- The withheld share is the reserve less the mandatory draw, floored",
        "  at zero. The pool is the remainder less the withheld share, floored",
        "  at zero.",
        "- Offer the pool to the discretionary instances ordered by tier",
        "  ascending, then demand descending, then trigger ascending, then",
        "  instance id ascending. A demand at or below the pool fits and",
        "  reduces it. A demand above the pool displaces that instance under",
        "  `CAPACITY_DISPLACED`, and the next candidate is still considered.",
        "- Publish `window_capacity_report.csv`, `initial_allocation.json`",
        "  and `displaced_action_queue.json`.",
    ])
    _spec(dest, "r11", [
        "Consult the fallback chain of every displaced instance.",
        "",
        "- Take the displaced instances in canonical order.",
        "- The chain is the instance's resolved `fallback_chain`, truncated to",
        "  the memo's fallback chain depth cap.",
        "- A candidate qualifies when it is a catalogue action, when its own",
        "  policy resolved for this window, trigger and routine does not",
        "  suppress it, when every hard prerequisite of the candidate in the",
        "  surviving graph has an allocated instance in this window or an",
        "  earlier one, and when no earlier displacement has already proposed",
        "  that candidate for this window and device.",
        "- The first qualifying candidate is proposed. It stands in for the",
        "  displaced instance, runs on the displaced instance's device, and",
        "  takes its own catalogue energy and class. Its instance id is the",
        "  candidate action id, an `@`, and the displaced instance id.",
        "- No capacity test happens here. Capacity is settled in r12.",
        "- A displaced instance with no qualifying candidate is terminal under",
        "  `NO_FALLBACK_FITS`. r12 carries these terminals forward with its",
        "  own, and the suppression ledger records them under `r12`.",
        "- Publish `fallback_expansion.json`.",
    ])
    _spec(dest, "r12", [
        "Re-run the binding over the holders and the proposals together,",
        "round after round, until no proposal is left or the cap is reached.",
        "",
        "- The round cap is in `precedence_directive.docx` part C. It counts",
        "  every binding of the chain, r10 included as round one, so r12",
        "  runs rounds two up to the cap. A cap of two means one round here.",
        "- The holders of a window and device start as the discretionary",
        "  instances r10 allocated there. Round two takes the proposals of",
        "  r11.",
        "- In each round, for every window and device that received at least",
        "  one proposal in that round, take its current holders together",
        "  with the round's proposals for it, and offer them the same pool",
        "  r10 offered at the start of its discretionary phase, under the",
        "  same order key. Whatever fits becomes the holders. A window and",
        "  device r10 never pooled keeps none of its proposals; they are",
        "  terminal under `FALLBACK_DISPLACED`.",
        "- A proposal or an earlier kept proposal that loses is terminal",
        "  under `FALLBACK_DISPLACED`. An instance r10 allocated that loses",
        "  is terminal under `DISPLACED_FINAL` and is recorded as overturned",
        "  with the round that overturned it.",
        "- When the round is not the last the cap allows, the instances it",
        "  overturned consult their own fallback chains under exactly the",
        "  rules of r11, the candidates already proposed for a window and",
        "  device in any earlier round staying taken. Those proposals make",
        "  the next round. An overturned instance with no qualifying",
        "  candidate stays under `DISPLACED_FINAL`. Instances overturned in",
        "  the last round consult nothing.",
        "- Publish `precedence_reconciliation.json`, one group per window,",
        "  device and round that bound proposals.",
    ])
    _spec(dest, "r13", [
        "Carry the surviving instances into state.",
        "",
        "- Order the survivors by window ordinal, then trigger, then the",
        "  action's position in the action order, then instance id.",
        "- Walking that order, each instance sets its action's last fired time",
        "  to its trigger and its cooldown until to trigger plus the resolved",
        "  cooldown, and applies every row of `state_effects.jsonl` whose",
        "  action is its own, in declared sequence order. The last write to a",
        "  key wins, and the key records the trigger and action that wrote it.",
        "- An instance to which a one shot override applied in r04 marks that",
        "  override as consumed once, whichever layer settled its tier.",
        "- Consumption never changes `remaining` within the cycle. r04 reads",
        "  the snapshot's `remaining` for every instance of the day, however",
        "  many earlier instances the same override applied to; the next",
        "  state's `remaining` is the snapshot's less the consumption,",
        "  floored at zero.",
        "- This stage runs twice. The first pass is over the survivors of r12",
        "  and publishes `cooldown_state.csv` and `derived_state.json`. The",
        "  second pass is over the survivors of r14 and feeds",
        "  `next_state_snapshot.json`. A one shot override is consumed only",
        "  by the second pass, so an instance r14 withdraws never consumes it.",
    ])
    _spec(dest, "r14", [
        "Feed the derived state back, then publish.",
        "",
        "- `gating_rules.toml` binds an action to a state key and a required",
        "  value under RR8.",
        "- A surviving instance whose action is gated is withdrawn under",
        "  `GATE_CLOSED` when the key was written by the first pass at a",
        "  trigger strictly before this instance's own trigger and the value",
        "  written is not the required one. A key no surviving instance wrote",
        "  closes no gate.",
        "- Withdrawing an instance can leave another instance without a hard",
        "  prerequisite at or before its trigger; that instance is withdrawn",
        "  under `PREREQ_WITHDRAWN`. Repeat until nothing changes.",
        "- An instance withheld in r05 under `SUPPRESSED` is readmitted when",
        "  its action is gated, the key was written before its trigger with",
        "  the required value, and its demand fits what is left of its window",
        "  and device pool after the survivors have drawn. A window and",
        "  device that carried no demand in r10 still has a pool: its ceiling",
        "  less the reserve, with no mandatory draw. Every discretionary",
        "  survivor of r14, a kept fallback proposal included, draws its",
        "  demand from its pool exactly once; a mandatory survivor draws",
        "  nothing here. Readmission takes",
        "  the withheld instances in instance id order, each readmitted",
        "  instance drawing from the pool before the next is considered, and",
        "  is recorded under `READMITTED`.",
        "- This is one pass. Nothing withdrawn or readmitted here is",
        "  reconsidered.",
        "- Publish the remaining documents: `final_action_order.json`,",
        "  `suppression_ledger.csv`, `next_state_snapshot.json`,",
        "  `per_context_manifest.json`, `per_device_manifest.csv`,",
        "  `daily_automation_manifest.json`,",
        "  `resource_utilization_report.csv`, `terminal_action_report.md`,",
        "  `audit_ledger.jsonl`, `run_manifest.txt` and `summary.json`.",
    ])


REFERENCE_PACKAGE = {
    "pyproject.toml": "[build-system]\nrequires = [\"setuptools>=68\"]\nbuild-backend = \"setuptools.build_meta\"\n\n[project]\nname = \"daybreak\"\nversion = \"3.4.0\"\ndescription = \"Household assistant routing chain for one cycle of working papers\"\nrequires-python = \">=3.12\"\ndependencies = []\n\n[tool.setuptools.packages.find]\nwhere = [\"src\"]\n",
    "src/daybreak/__init__.py": "\"\"\"daybreak - the household assistant routing chain.\n\nFourteen stages turn one directory of working papers into the derived\ndocuments of one routing cycle. Nothing about a cycle is held here.\n\"\"\"\n__all__ = [\"main\", \"run_chain\"]\n\nVERSION = \"3.4.0\"\n\n\ndef main(argv=None):\n    from daybreak.cli import main as _main\n    return _main(argv)\n\n\ndef run_chain(root):\n    from daybreak.publish import run_chain as _run\n    return _run(root)\n",
    "src/daybreak/__main__.py": "import sys\n\nfrom daybreak.cli import main\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n",
    "src/daybreak/allocate.py": "\"\"\"Stages r10 to r14 of the daybreak routing chain.\"\"\"\nfrom fractions import Fraction\n\nfrom daybreak.loading import convert\nfrom daybreak.stages import _absent, demand_of, hard_prereqs, resolve_policy\nfrom daybreak.util import half_even\n\n\ndef _ceiling(data, window_id, device_id):\n    entry = data[\"workbook\"][\"ceilings\"].get((window_id, device_id))\n    if entry is None or _absent(entry[0]):\n        return None\n    value, _base = convert(data[\"units\"], entry[0], entry[1])\n    return value\n\n\ndef _order_key(rec, r04, r08):\n    inst = rec[\"instance\"]\n    resolved = rec[\"resolved\"]\n    return (resolved[\"tier\"], -rec[\"demand\"][\"demand_mwh\"],\n            inst[\"trigger_ms\"], inst[\"instance_id\"])\n\n\ndef _select(pool, candidates, r04, r08):\n    \"\"\"Candidates taken from a pool, candidates set aside, pool left.\"\"\"\n    taken = []\n    rejected = []\n    for rec in sorted(candidates, key=lambda c: _order_key(c, r04, r08)):\n        if rec[\"demand\"][\"demand_mwh\"] <= pool:\n            pool -= rec[\"demand\"][\"demand_mwh\"]\n            taken.append(rec)\n        else:\n            rejected.append(rec)\n    return taken, rejected, pool\n\n\ndef stage_r10(data, r01, r02, r04, r08, r09):\n    reserve_bp = int(data[\"directive\"][\"reserve_bp\"])\n    groups = {}\n    for row in r09[\"rows\"]:\n        groups.setdefault((row[\"window_id\"], row[\"device_id\"]), []).append(row)\n    report = []\n    allocated = {}\n    displaced = []\n    pools = {}\n    for key in sorted(groups, key=lambda k: (r02[\"windows\"][k[0]][\"ordinal\"],\n                                             k[1])):\n        window_id, device_id = key\n        ceiling = _ceiling(data, window_id, device_id)\n        if ceiling is None:\n            for row in groups[key]:\n                displaced.append({\"instance_id\": row[\"instance_id\"],\n                                  \"reason\": \"UNKNOWN_CEILING\"})\n            continue\n        reserve = half_even(Fraction(ceiling * reserve_bp, 10000))\n        mandatory = []\n        discretionary = []\n        for row in groups[key]:\n            rec = {\"instance\": r08[\"by_id\"][row[\"instance_id\"]],\n                   \"resolved\": r04[\"resolved\"][row[\"instance_id\"]],\n                   \"demand\": row}\n            if rec[\"resolved\"][\"mandatory\"]:\n                mandatory.append(rec)\n            else:\n                discretionary.append(rec)\n        mandatory.sort(key=lambda c: r09[\"order\"].index(c[\"instance\"][\"instance_id\"]))\n        drawn = 0\n        for rec in mandatory:\n            drawn += rec[\"demand\"][\"demand_mwh\"]\n            allocated[rec[\"instance\"][\"instance_id\"]] = key\n        remaining = ceiling - drawn\n        overrun = remaining < 0\n        if overrun:\n            remaining = 0\n        withheld = reserve - drawn\n        if withheld < 0:\n            withheld = 0\n        pool = remaining - withheld\n        if pool < 0:\n            pool = 0\n        taken, rejected, left = _select(pool, discretionary, r04, r08)\n        for rec in taken:\n            allocated[rec[\"instance\"][\"instance_id\"]] = key\n        for rec in rejected:\n            displaced.append({\"instance_id\": rec[\"instance\"][\"instance_id\"],\n                              \"reason\": \"CAPACITY_DISPLACED\"})\n        pools[key] = {\"ceiling_mwh\": ceiling, \"reserve_mwh\": reserve,\n                      \"mandatory_mwh\": drawn, \"pool_start_mwh\": pool,\n                      \"pool_remaining_mwh\": left, \"overrun\": overrun}\n        report.append({\"window_id\": window_id, \"device_id\": device_id,\n                       \"ceiling_mwh\": ceiling, \"reserve_mwh\": reserve,\n                       \"mandatory_mwh\": drawn,\n                       \"allocated_mwh\": pool - left,\n                       \"pool_remaining_mwh\": left,\n                       \"overrun\": \"yes\" if overrun else \"no\"})\n    return {\"allocated\": allocated, \"displaced\": displaced, \"report\": report,\n            \"pools\": pools, \"groups\": groups}\n\n\ndef _allocated_actions(r02, r08, r10):\n    out = {}\n    for iid, key in r10[\"allocated\"].items():\n        inst = r08[\"by_id\"][iid]\n        out.setdefault(inst[\"action_id\"], []).append(\n            r02[\"windows\"][key[0]][\"ordinal\"])\n    return out\n\n\ndef _expand(data, r01, r02, r04, r08, r09, prereqs, allocated_actions,\n            displaced_ids, taken_here):\n    depth_cap = int(data[\"controls\"][\"fallback_chain_depth_cap\"])\n    proposals = []\n    unplaced = []\n    for iid in sorted(displaced_ids, key=r09[\"order\"].index):\n        inst = r08[\"by_id\"][iid]\n        resolved = r04[\"resolved\"][iid]\n        key = (inst[\"window_id\"], resolved[\"device_id\"])\n        chain = list(resolved[\"fallback_chain\"])[:depth_cap]\n        placed = None\n        for candidate in chain:\n            if candidate not in r01[\"actions\"]:\n                continue\n            synthetic = {\"instance_id\": candidate + \"@\" + iid,\n                         \"routine_id\": inst[\"routine_id\"],\n                         \"action_id\": candidate,\n                         \"occurrence_index\": 0,\n                         \"trigger_ms\": inst[\"trigger_ms\"],\n                         \"window_id\": inst[\"window_id\"]}\n            crec, _win = resolve_policy(r04[\"layers\"], r04[\"floors\"], r01,\n                                        r02, synthetic)\n            if crec[\"suppress\"]:\n                continue\n            ordinal = r02[\"windows\"][inst[\"window_id\"]][\"ordinal\"]\n            satisfied = True\n            for pre in sorted(prereqs.get(candidate, set())):\n                seen = [o for o in allocated_actions.get(pre, [])\n                        if o <= ordinal]\n                if not seen:\n                    satisfied = False\n                    break\n            if not satisfied:\n                continue\n            if (candidate, key) in taken_here:\n                continue\n            crec = dict(crec)\n            crec[\"device_id\"] = resolved[\"device_id\"]\n            demand = demand_of(data, r01, r02, r04, synthetic[\"instance_id\"],\n                               candidate, inst[\"window_id\"], crec)\n            placed = {\"instance\": synthetic, \"resolved\": crec,\n                      \"demand\": demand, \"stands_in_for\": iid, \"group\": key}\n            taken_here.add((candidate, key))\n            break\n        if placed is None:\n            unplaced.append(iid)\n        else:\n            proposals.append(placed)\n    return proposals, unplaced\n\n\ndef stage_r11(data, r01, r02, r04, r07, r08, r09, r10):\n    proposals, unplaced = _expand(\n        data, r01, r02, r04, r08, r09, hard_prereqs(r07[\"edges\"]),\n        _allocated_actions(r02, r08, r10),\n        [entry[\"instance_id\"] for entry in r10[\"displaced\"]], set())\n    terminal = [{\"instance_id\": iid, \"reason\": \"NO_FALLBACK_FITS\"}\n                for iid in unplaced]\n    return {\"proposals\": proposals, \"terminal\": terminal}\n\n\ndef stage_r12(data, r01, r02, r04, r07, r08, r09, r10, r11):\n    cap = int(data[\"directive\"][\"round_cap\"])\n    prereqs = hard_prereqs(r07[\"edges\"])\n    allocated_actions = _allocated_actions(r02, r08, r10)\n    taken_here = {(rec[\"instance\"][\"action_id\"], rec[\"group\"])\n                  for rec in r11[\"proposals\"]}\n    holders = {}\n    for iid, gkey in r10[\"allocated\"].items():\n        resolved = r04[\"resolved\"][iid]\n        if resolved[\"mandatory\"]:\n            continue\n        holders.setdefault(gkey, []).append(\n            {\"instance\": r08[\"by_id\"][iid], \"resolved\": resolved,\n             \"demand\": r09[\"by_instance\"][iid], \"stands_in_for\": \"\",\n             \"group\": gkey})\n    survivors = dict(r10[\"allocated\"])\n    terminal = list(r11[\"terminal\"])\n    overturned = []\n    report = []\n    index = {}\n    pending = list(r11[\"proposals\"])\n    rnd = 2\n    while pending and rnd <= cap:\n        by_group = {}\n        for rec in pending:\n            index[rec[\"instance\"][\"instance_id\"]] = rec\n            by_group.setdefault(rec[\"group\"], []).append(rec)\n        displaced_now = []\n        for key in sorted(by_group,\n                          key=lambda k: (r02[\"windows\"][k[0]][\"ordinal\"], k[1])):\n            pools = r10[\"pools\"].get(key)\n            if pools is None:\n                for rec in by_group[key]:\n                    terminal.append({\"instance_id\": rec[\"instance\"][\"instance_id\"],\n                                     \"reason\": \"FALLBACK_DISPLACED\"})\n                continue\n            incumbents = holders.get(key, [])\n            candidates = incumbents + by_group[key]\n            taken, rejected, left = _select(pools[\"pool_start_mwh\"], candidates,\n                                            r04, r08)\n            holders[key] = taken\n            for rec in taken:\n                survivors[rec[\"instance\"][\"instance_id\"]] = key\n            for rec in rejected:\n                iid = rec[\"instance\"][\"instance_id\"]\n                survivors.pop(iid, None)\n                if rec[\"stands_in_for\"]:\n                    terminal.append({\"instance_id\": iid,\n                                     \"reason\": \"FALLBACK_DISPLACED\"})\n                    continue\n                overturned.append({\"instance_id\": iid, \"window_id\": key[0],\n                                   \"device_id\": key[1], \"round\": rnd})\n                terminal.append({\"instance_id\": iid,\n                                 \"reason\": \"DISPLACED_FINAL\"})\n                if rnd < cap:\n                    displaced_now.append(iid)\n            report.append({\"window_id\": key[0], \"device_id\": key[1],\n                           \"round\": rnd, \"proposals\": len(by_group[key]),\n                           \"incumbents\": len(incumbents),\n                           \"kept\": len(taken),\n                           \"pool_remaining_mwh\": left})\n        rnd += 1\n        pending, _unplaced = _expand(data, r01, r02, r04, r08, r09, prereqs,\n                                     allocated_actions, displaced_now,\n                                     taken_here)\n    return {\"survivors\": survivors, \"terminal\": terminal,\n            \"overturned\": overturned, \"report\": report, \"round_cap\": cap,\n            \"proposal_index\": index}\n\n\ndef _instance_of(iid, r08, r12):\n    if iid in r08[\"by_id\"]:\n        return r08[\"by_id\"][iid]\n    return r12[\"proposal_index\"][iid][\"instance\"]\n\n\ndef _resolved_of(iid, r04, r12):\n    if iid in r04[\"resolved\"]:\n        return r04[\"resolved\"][iid]\n    return r12[\"proposal_index\"][iid][\"resolved\"]\n\n\ndef final_order(survivors, r02, r04, r08, r12):\n    items = []\n    for iid in survivors:\n        inst = _instance_of(iid, r08, r12)\n        ordinal = r02[\"windows\"][inst[\"window_id\"]][\"ordinal\"]\n        rank = r08[\"rank\"].get(inst[\"action_id\"], len(r08[\"rank\"]))\n        items.append((ordinal, inst[\"trigger_ms\"], rank, iid))\n    items.sort()\n    return [item[3] for item in items]\n\n\ndef stage_r13(data, r01, r02, r04, r08, r12):\n    order = final_order(r12[\"survivors\"], r02, r04, r08, r12)\n    effects = sorted(data[\"effects\"], key=lambda e: int(e[\"declared_seq\"]))\n    by_action = {}\n    for rec in effects:\n        by_action.setdefault(rec[\"action_id\"], []).append(rec)\n    state = {}\n    set_at = {}\n    cooldowns = {}\n    last_fired = {}\n    consumed = {}\n    for iid in order:\n        inst = _instance_of(iid, r08, r12)\n        resolved = _resolved_of(iid, r04, r12)\n        aid = inst[\"action_id\"]\n        last_fired[aid] = inst[\"trigger_ms\"]\n        cooldowns[aid] = {\"action_id\": aid,\n                          \"cooldown_until_ms\": inst[\"trigger_ms\"]\n                          + resolved[\"cooldown_ms\"],\n                          \"source_layer\": \"resolved\"}\n        if resolved[\"oneshot_id\"]:\n            consumed[resolved[\"oneshot_id\"]] = consumed.get(\n                resolved[\"oneshot_id\"], 0) + 1\n        for rec in by_action.get(aid, []):\n            state[rec[\"sets_key\"]] = rec[\"sets_value\"]\n            set_at[rec[\"sets_key\"]] = (inst[\"trigger_ms\"], aid)\n    return {\"order\": order, \"state\": state, \"set_at\": set_at,\n            \"cooldowns\": cooldowns, \"last_fired\": last_fired,\n            \"consumed\": consumed}\n\n\ndef stage_r14(data, r01, r02, r04, r05, r07, r08, r09, r10, r12, r13):\n    gates = {}\n    for key, spec in data[\"gates\"].items():\n        if not key.startswith(\"AC-\"):\n            continue\n        parts = str(spec).split(chr(124))\n        if len(parts) == 2:\n            gates[key] = (parts[0], parts[1])\n    survivors = dict(r12[\"survivors\"])\n    withdrawn = []\n    for iid in list(r13[\"order\"]):\n        inst = _instance_of(iid, r08, r12)\n        gate = gates.get(inst[\"action_id\"])\n        if gate is None:\n            continue\n        key, required = gate\n        if key not in r13[\"set_at\"]:\n            continue\n        when, _who = r13[\"set_at\"][key]\n        if when < inst[\"trigger_ms\"] and r13[\"state\"][key] != required:\n            survivors.pop(iid, None)\n            withdrawn.append({\"instance_id\": iid, \"reason\": \"GATE_CLOSED\"})\n    prereqs = hard_prereqs(r07[\"edges\"])\n    changed = True\n    while changed:\n        changed = False\n        for iid in sorted(survivors):\n            inst = _instance_of(iid, r08, r12)\n            need = prereqs.get(inst[\"action_id\"], set())\n            for pre in sorted(need):\n                ok = False\n                for other in survivors:\n                    cand = _instance_of(other, r08, r12)\n                    if (cand[\"action_id\"] == pre\n                            and cand[\"trigger_ms\"] <= inst[\"trigger_ms\"]):\n                        ok = True\n                        break\n                if not ok:\n                    survivors.pop(iid, None)\n                    withdrawn.append({\"instance_id\": iid,\n                                      \"reason\": \"PREREQ_WITHDRAWN\"})\n                    changed = True\n                    break\n            if changed:\n                break\n    readmitted = []\n    readmit_demand = {}\n    pools = {}\n    for key, rec in r10[\"pools\"].items():\n        pools[key] = rec[\"pool_start_mwh\"]\n\n    def pool_for(key):\n        \"\"\"A window and device that carried no demand in r10 still has a\n        pool: its ceiling less the reserve, with no mandatory draw.\"\"\"\n        if key in pools:\n            return pools[key]\n        ceiling = _ceiling(data, key[0], key[1])\n        if ceiling is None:\n            return None\n        reserve = half_even(Fraction(ceiling * int(\n            data[\"directive\"][\"reserve_bp\"]), 10000))\n        value = ceiling - reserve\n        pools[key] = value if value > 0 else 0\n        return pools[key]\n    for iid, key in survivors.items():\n        if iid in r12[\"proposal_index\"]:\n            continue\n        demand = r09[\"by_instance\"][iid]\n        resolved = _resolved_of(iid, r04, r12)\n        if resolved[\"mandatory\"]:\n            continue\n        if key in pools:\n            pools[key] -= demand[\"demand_mwh\"]\n    for iid in sorted(r12[\"proposal_index\"]):\n        if iid not in survivors:\n            continue\n        key = survivors[iid]\n        if key in pools:\n            pools[key] -= r12[\"proposal_index\"][iid][\"demand\"][\"demand_mwh\"]\n    for entry in sorted(r05[\"withheld\"], key=lambda w: w[\"instance_id\"]):\n        if entry[\"reason\"] != \"SUPPRESSED\":\n            continue\n        iid = entry[\"instance_id\"]\n        inst = r08[\"by_id\"].get(iid)\n        if inst is None:\n            continue\n        gate = gates.get(inst[\"action_id\"])\n        if gate is None:\n            continue\n        key, required = gate\n        if key not in r13[\"set_at\"]:\n            continue\n        when, _who = r13[\"set_at\"][key]\n        if not (when < inst[\"trigger_ms\"] and r13[\"state\"][key] == required):\n            continue\n        resolved = r04[\"resolved\"][iid]\n        row = demand_of(data, r01, r02, r04, iid, inst[\"action_id\"],\n                        inst[\"window_id\"], resolved)\n        group = (inst[\"window_id\"], resolved[\"device_id\"])\n        if pool_for(group) is None:\n            continue\n        if row[\"demand_mwh\"] <= pools[group]:\n            pools[group] -= row[\"demand_mwh\"]\n            survivors[iid] = group\n            readmit_demand[iid] = row\n            readmitted.append({\"instance_id\": iid, \"reason\": \"READMITTED\",\n                               \"demand_mwh\": row[\"demand_mwh\"]})\n    order = final_order(survivors, r02, r04, r08, r12)\n    return {\"survivors\": survivors, \"order\": order, \"withdrawn\": withdrawn,\n            \"readmitted\": readmitted, \"pools\": pools,\n            \"demand\": readmit_demand}\n",
    "src/daybreak/cli.py": "\"\"\"Command line entry point for the daybreak router.\"\"\"\nimport sys\nfrom pathlib import Path\n\nfrom daybreak.publish import run_chain\n\n\nUSAGE = \"usage: python3 -m daybreak --data <papers> --out <destination>\"\n\n\ndef parse_args(argv):\n    data = None\n    out = None\n    i = 0\n    while i < len(argv):\n        token = argv[i]\n        if token == \"--data\" and i + 1 < len(argv):\n            data = argv[i + 1]\n            i += 2\n            continue\n        if token == \"--out\" and i + 1 < len(argv):\n            out = argv[i + 1]\n            i += 2\n            continue\n        raise SystemExit(USAGE)\n    if data is None or out is None:\n        raise SystemExit(USAGE)\n    return Path(data), Path(out)\n\n\ndef main(argv=None):\n    argv = list(sys.argv[1:] if argv is None else argv)\n    data, out = parse_args(argv)\n    if not data.is_dir():\n        raise SystemExit(\"paper directory not found: \" + str(data))\n    blobs = run_chain(data)\n    out.mkdir(parents=True, exist_ok=True)\n    for name in sorted(blobs):\n        (out / name).write_bytes(blobs[name])\n    return 0\n",
    "src/daybreak/loading.py": "\"\"\"Reads the working papers into plain records under the documented rules.\"\"\"\nfrom fractions import Fraction\nfrom pathlib import Path\n\nfrom daybreak.util import (as_fraction, half_even, read_conf, read_delim,\n                           read_docx_blocks, read_flat_toml, read_flat_yaml,\n                           read_json, read_jsonl, read_pdf_lines,\n                           read_sqlite_table, read_text, read_xlsx_sheets,\n                           read_xml, PIPE, TAB)\n\nLAYER_ORDER = [\"mandatory\", \"oneshot\", \"context\", \"device\", \"action\",\n               \"routine\", \"global\"]\nPOLICY_FIELDS = [\"tier\", \"intensity_bp\", \"cooldown_ms\", \"mandatory\",\n                 \"max_occurrences\", \"suppress\", \"fallback_chain\"]\n\n\nclass Unresolved(Exception):\n    pass\n\n\ndef unit_table(root):\n    \"\"\"token -> (base, num, den, status).\"\"\"\n    out = {}\n    for raw in read_text(root / \"unit_registry_dictionary.toml\").splitlines():\n        line = raw.split(\"#\", 1)[0].strip()\n        if not line or line.startswith(\"[\") or \"=\" not in line:\n            continue\n        token, spec = line.split(\"=\", 1)\n        token = token.strip()\n        parts = spec.strip().strip(chr(34)).split(PIPE)\n        if len(parts) != 4:\n            continue\n        out[token] = (parts[0], int(parts[1]), int(parts[2]), parts[3])\n    return out\n\n\ndef convert(units, value, token):\n    \"\"\"Quantity in base units, or (None, reason) when it cannot be carried.\"\"\"\n    if token not in units:\n        return None, \"UNCONVERTIBLE_UNIT\"\n    base, num, den, status = units[token]\n    if status != \"live\" or den == 0:\n        return None, \"UNCONVERTIBLE_UNIT\"\n    return half_even(as_fraction(value) * Fraction(num, den)), base\n\n\ndef live_rows(rows, key_field, frozen_for, rev_field=\"revision\"):\n    \"\"\"Rows in force, one per key.\"\"\"\n    best = {}\n    for idx, row in enumerate(rows):\n        key = row[key_field]\n        rev = int(row[rev_field])\n        limit = frozen_for(key)\n        if limit is None or rev > limit:\n            continue\n        prev = best.get(key)\n        if prev is None or (rev, idx) >= (prev[0], prev[1]):\n            best[key] = (rev, idx, row)\n    return {k: v[2] for k, v in best.items()}\n\n\ndef _memo_scalar(lines, label):\n    for line in lines:\n        stripped = line.strip()\n        if stripped.startswith(label):\n            rest = stripped[len(label):].strip()\n            parts = rest.split()\n            if parts:\n                return int(parts[0])\n    raise Unresolved(\"memo scalar not found: \" + label)\n\n\ndef read_memo(root):\n    lines = read_pdf_lines(root / \"household_operations_memo.pdf\")\n    ctl = {\n        \"implausible_demand_mwh\": _memo_scalar(lines, \"implausible demand ceiling\"),\n        \"fallback_chain_depth_cap\": _memo_scalar(lines, \"fallback chain depth cap\"),\n        \"default_max_occurrences\": _memo_scalar(lines, \"default max occurrences\"),\n        \"alias_hop_cap\": _memo_scalar(lines, \"alias hop cap\"),\n    }\n    caps = {}\n    for line in lines:\n        parts = line.strip().split()\n        if len(parts) == 2 and parts[0].startswith(\"RT-\"):\n            caps[parts[0]] = None if parts[1] == \"-\" else int(parts[1])\n    return ctl, caps\n\n\ndef read_directive(root):\n    blocks = read_docx_blocks(root / \"precedence_directive.docx\")\n    ranks = {}\n    keys = []\n    reserve_bp = None\n    round_cap = None\n    mandates = []\n    for block in blocks:\n        if isinstance(block, str):\n            if \"Reconciliation runs for at most\" in block:\n                for word in block.split():\n                    if word.isdigit():\n                        round_cap = int(word)\n                        break\n            if \"basis points of the ceiling\" in block:\n                for word in block.replace(\",\", \" \").split():\n                    if word.isdigit():\n                        reserve_bp = int(word)\n                        break\n            continue\n        if len(block) >= 2 and block[0].isdigit() and block[1] in LAYER_ORDER:\n            ranks[block[1]] = int(block[0])\n        elif len(block) == 3 and block[0].isdigit() and \"first\" in block[2]:\n            keys.append((int(block[0]), block[1], block[2]))\n        elif len(block) == 5 and block[0].isdigit() and block[1].startswith(\"AC-\"):\n            mandates.append({\"seq\": int(block[0]), \"action\": block[1],\n                             \"window\": block[2],\n                             \"mandatory\": block[3] == \"yes\",\n                             \"tier\": int(block[4])})\n    if reserve_bp is None:\n        raise Unresolved(\"directive carries no mandatory reserve\")\n    if round_cap is None:\n        raise Unresolved(\"directive carries no reconciliation round cap\")\n    if sorted(ranks) != sorted(LAYER_ORDER):\n        raise Unresolved(\"directive does not rank every layer\")\n    return {\"ranks\": ranks, \"settlement_keys\": keys, \"reserve_bp\": reserve_bp,\n            \"round_cap\": round_cap, \"mandates\": mandates}\n\n\ndef read_workbook(root, cycle_key):\n    \"\"\"Capacity grid and surcharge scales from the workbook.\"\"\"\n    sheets = read_xlsx_sheets(root / \"capacity_and_intensity_workbook.xlsx\")\n    live = None\n    scales = None\n    for name, rows in sheets.items():\n        if not rows:\n            continue\n        head = rows[0]\n        if len(head) >= 2 and head[0] == \"grid_key\" and head[1] == cycle_key:\n            live = rows\n        if len(head) >= 2 and head[0] == \"surcharge_key\":\n            scales = rows\n    if live is None:\n        raise Unresolved(\"no workbook grid carries the cycle key\")\n    if scales is None:\n        raise Unresolved(\"workbook carries no class scale table\")\n    recorded_unit = \"centiwh\"\n    for row in live[:3]:\n        if row and row[0] == \"recorded_unit\":\n            recorded_unit = row[1]\n    ceilings = {}\n    for row in live:\n        if len(row) >= 4 and row[0].startswith(\"W\") and row[1].startswith(\"DV-\"):\n            ceilings[(row[0], row[1])] = (row[2], row[3] or recorded_unit)\n    surcharge = {}\n    capacity_scale = {}\n    reserve = None\n    mode = \"surcharge\"\n    for row in scales:\n        if not row:\n            continue\n        if row[0] == \"action_class\":\n            mode = \"surcharge\"\n            continue\n        if row[0] == \"capacity_class\":\n            mode = \"capacity\"\n            continue\n        if row[0] == \"reserve\":\n            reserve = int(row[1])\n            continue\n        if row[0] in (\"surcharge_key\",):\n            continue\n        if len(row) < 2:\n            continue\n        if mode == \"surcharge\":\n            surcharge[row[0]] = int(row[1])\n        else:\n            capacity_scale[row[0]] = int(row[1])\n    return {\"ceilings\": ceilings, \"surcharge\": surcharge,\n            \"capacity_scale\": capacity_scale, \"workbook_reserve_bp\": reserve}\n\n\ndef load_all(root):\n    root = Path(root)\n    data = {}\n    data[\"header\"] = read_json(root / \"cycle_header.json\")\n    data[\"runtime\"] = read_conf(root / \"assistant_runtime.conf\")\n    data[\"units\"] = unit_table(root)\n    data[\"rounding\"] = read_flat_yaml(root / \"rounding_and_arithmetic_policy.yaml\")\n    data[\"precedence\"] = read_flat_toml(root / \"precedence_and_overturn.toml\")\n    data[\"binding\"] = read_flat_yaml(root / \"capacity_binding_policy.yaml\")\n    data[\"settlement\"] = read_flat_toml(root / \"cycle_break_policy.toml\")\n    data[\"expansion\"] = read_flat_yaml(root / \"expansion_policy.yaml\")\n    data[\"publication\"] = read_flat_toml(root / \"publication_form_rules.toml\")\n    data[\"window_rows\"] = read_delim(root / \"window_grid.csv\", \",\")\n    data[\"device_rows\"] = read_delim(root / \"device_register.csv\", \",\")\n    data[\"device_policy_rows\"] = read_delim(root / \"device_policies.csv\", \",\")\n    data[\"catalogue\"] = read_delim(root / \"action_catalogue.csv\", \",\")\n    data[\"routines\"] = read_delim(root / \"routine_register.csv\", \",\")\n    data[\"edges\"] = read_delim(root / \"dependency_edges.tsv\", TAB)\n    data[\"context_spans\"] = read_delim(root / \"context_activity_spans.tsv\", TAB)\n    data[\"context_policies\"] = read_delim(root / \"context_policies.tsv\", TAB)\n    data[\"cooldown_rows\"] = read_delim(root / \"cooldown_register.psv\", PIPE)\n    data[\"action_policies\"] = read_jsonl(root / \"action_policies.jsonl\")\n    data[\"routine_defaults\"] = read_flat_toml(root / \"routine_defaults.toml\")\n    data[\"global_defaults\"] = read_flat_yaml(root / \"global_defaults.yaml\")\n    data[\"overrides\"] = read_jsonl(root / \"override_journal.jsonl\")\n    data[\"snapshot\"] = read_json(root / \"state_snapshot.json\")\n    data[\"prior_journal\"] = read_jsonl(root / \"prior_cycle_journal.jsonl\")\n    data[\"effects\"] = read_jsonl(root / \"state_effects.jsonl\")\n    data[\"gates\"] = read_flat_toml(root / \"gating_rules.toml\")\n    data[\"sources\"] = read_delim(root / \"source_priority_register.csv\", \",\")\n    data[\"alias_primary\"] = read_delim(root / \"alias_crosswalk.tsv\", TAB)\n    data[\"alias_supplement\"] = read_delim(root / \"identifier_supplement.psv\", PIPE)\n    data[\"ledger\"] = read_jsonl(root / \"energy_ledger_history.ndjson\")\n    data[\"archive\"] = read_sqlite_table(root / \"prior_cycle_archive.sqlite3\",\n                                        data[\"runtime\"][\"archive_table\"])\n    _scalars, groups = read_xml(root / \"home_topology.xml\")\n    data[\"circuits\"] = groups.get(\"circuits\", [])\n    ctl, caps = read_memo(root)\n    data[\"controls\"] = ctl\n    data[\"memo_caps\"] = caps\n    data[\"directive\"] = read_directive(root)\n    data[\"workbook\"] = read_workbook(root, data[\"header\"][\"cycle_key\"])\n    return data\n",
    "src/daybreak/publish.py": "\"\"\"Renders the derived documents of one routing cycle as bytes.\"\"\"\nfrom fractions import Fraction\n\nfrom daybreak.allocate import (_instance_of, _resolved_of, stage_r10,\n                               stage_r11, stage_r12, stage_r13, stage_r14)\nfrom daybreak.loading import LAYER_ORDER, POLICY_FIELDS, live_rows, load_all\nfrom daybreak.stages import (demand_of, stage_r01, stage_r02, stage_r03,\n                             stage_r04, stage_r05, stage_r06, stage_r07,\n                             stage_r08, stage_r09)\nfrom daybreak.util import (canonical_json, compact_json, half_even, ratio12,\n                           sha256_hex, NL)\n\nSTAGE_IDS = [\"r01\", \"r02\", \"r03\", \"r04\", \"r05\", \"r06\", \"r07\",\n             \"r08\", \"r09\", \"r10\", \"r11\", \"r12\", \"r13\", \"r14\"]\n\nDOCUMENTS = [\n    \"unit_normalization.json\", \"alias_resolution.jsonl\",\n    \"expansion_ledger.csv\", \"config_resolution.json\", \"parameter_audit.csv\",\n    \"trigger_eligibility_index.json\", \"dependency_graph.json\",\n    \"cycle_break_ledger.json\", \"canonical_action_order.json\",\n    \"resource_demand.csv\", \"window_capacity_report.csv\",\n    \"initial_allocation.json\", \"displaced_action_queue.json\",\n    \"fallback_expansion.json\", \"precedence_reconciliation.json\",\n    \"final_action_order.json\", \"cooldown_state.csv\", \"derived_state.json\",\n    \"suppression_ledger.csv\", \"next_state_snapshot.json\",\n    \"per_context_manifest.json\", \"per_device_manifest.csv\",\n    \"daily_automation_manifest.json\", \"resource_utilization_report.csv\",\n    \"terminal_action_report.md\", \"audit_ledger.jsonl\",\n]\n\n\ndef _json(obj):\n    return (canonical_json(obj) + NL).encode(\"utf-8\")\n\n\ndef _jsonl(records):\n    if not records:\n        return b\"\"\n    return (NL.join(compact_json(r) for r in records) + NL).encode(\"utf-8\")\n\n\ndef _csv(header, rows):\n    body = [\",\".join(str(h) for h in header)]\n    for row in rows:\n        body.append(\",\".join(str(c) for c in row))\n    return (NL.join(body) + NL).encode(\"utf-8\")\n\n\ndef _text(lines):\n    return (NL.join(str(x) for x in lines) + NL).encode(\"utf-8\")\n\n\ndef run_chain(root):\n    data = load_all(root)\n    r01 = stage_r01(data)\n    r02 = stage_r02(data, r01)\n    r03 = stage_r03(data, r01, r02)\n    r04 = stage_r04(data, r01, r02, r03)\n    r05 = stage_r05(data, r01, r02, r03, r04)\n    r06 = stage_r06(data, r01, r02)\n    tier_index = {}\n    by_id = {i[\"instance_id\"]: i for i in r03[\"instances\"]}\n    for iid in r05[\"eligible\"]:\n        aid = by_id[iid][\"action_id\"]\n        tier = r04[\"resolved\"][iid][\"tier\"]\n        if aid not in tier_index or tier < tier_index[aid]:\n            tier_index[aid] = tier\n    fallback_tier = r04[\"layers\"][\"global\"][\"tier\"]\n    r07 = stage_r07(data, r06, tier_index, fallback_tier)\n    r08 = stage_r08(data, r01, r03, r05, r07)\n    r09 = stage_r09(data, r01, r02, r04, r08)\n    r10 = stage_r10(data, r01, r02, r04, r08, r09)\n    r11 = stage_r11(data, r01, r02, r04, r07, r08, r09, r10)\n    r12 = stage_r12(data, r01, r02, r04, r07, r08, r09, r10, r11)\n    r13 = stage_r13(data, r01, r02, r04, r08, r12)\n    r14 = stage_r14(data, r01, r02, r04, r05, r07, r08, r09, r10, r12, r13)\n    r13b = stage_r13(data, r01, r02, r04, r08,\n                     {\"survivors\": r14[\"survivors\"],\n                      \"proposal_index\": r12[\"proposal_index\"]})\n    state = {\"data\": data, \"r01\": r01, \"r02\": r02, \"r03\": r03, \"r04\": r04,\n             \"r05\": r05, \"r06\": r06, \"r07\": r07, \"r08\": r08, \"r09\": r09,\n             \"r10\": r10, \"r11\": r11, \"r12\": r12, \"r13\": r13, \"r14\": r14,\n             \"r13b\": r13b, \"tier_index\": tier_index}\n    return render(state)\n\n\ndef render(state):\n    data = state[\"data\"]\n    r01, r02, r03, r04 = state[\"r01\"], state[\"r02\"], state[\"r03\"], state[\"r04\"]\n    r05, r06, r07, r08 = state[\"r05\"], state[\"r06\"], state[\"r07\"], state[\"r08\"]\n    r09, r10, r11, r12 = state[\"r09\"], state[\"r10\"], state[\"r11\"], state[\"r12\"]\n    r13, r14, r13b = state[\"r13\"], state[\"r14\"], state[\"r13b\"]\n    header = data[\"header\"]\n    out = {}\n\n    out[\"unit_normalization.json\"] = _json({\n        \"cycle_key\": header[\"cycle_key\"],\n        \"base_units\": header[\"base_units\"],\n        \"unit_counts\": r01[\"unit_counts\"],\n        \"totals\": r01[\"totals\"],\n        \"quarantined\": sorted(r01[\"notes\"],\n                              key=lambda n: (n[\"record\"], n[\"field\"])),\n    })\n\n    out[\"alias_resolution.jsonl\"] = _jsonl(\n        sorted(r02[\"decisions\"],\n               key=lambda d: (d[\"alias\"], d[\"source\"], d[\"status\"])))\n\n    out[\"expansion_ledger.csv\"] = _csv(\n        [\"routine_id\", \"instance_id\", \"action_id\", \"occurrence_index\",\n         \"trigger_ms\", \"window_id\", \"status\", \"reason\"],\n        [[e[\"routine_id\"], e[\"instance_id\"], e[\"action_id\"],\n          e[\"occurrence_index\"], e[\"trigger_ms\"], e[\"window_id\"],\n          e[\"status\"], e[\"reason\"]]\n         for e in sorted(r03[\"ledger\"],\n                         key=lambda e: (e[\"routine_id\"],\n                                        e[\"occurrence_index\"]))])\n\n    frozen = header[\"device_frozen_revisions\"]\n    live = live_rows(data[\"device_policy_rows\"], \"device_id\",\n                     lambda k: frozen.get(k))\n    live_dev = {did: int(row[\"revision\"]) for did, row in sorted(live.items())}\n    out[\"config_resolution.json\"] = _json({\n        \"instances\": len(r03[\"instances\"]),\n        \"layer_ranks\": {name: r04[\"layers\"][\"ranks\"][name] for name in LAYER_ORDER},\n        \"settled_by_layer\": {k: v for k, v in sorted(r04[\"counts\"].items())},\n        \"live_device_policy_revisions\": live_dev,\n        \"cooldown_floors_ms\": {k: v for k, v in sorted(r04[\"floors\"].items())},\n        \"reserve_bp\": int(data[\"directive\"][\"reserve_bp\"]),\n    })\n\n    rows = []\n    for iid in sorted(r04[\"resolved\"]):\n        rec = r04[\"resolved\"][iid]\n        win = r04[\"winners\"][iid]\n        for field in POLICY_FIELDS:\n            value = rec[field]\n            if field == \"fallback_chain\":\n                value = \";\".join(value)\n            elif isinstance(value, bool):\n                value = \"true\" if value else \"false\"\n            rows.append([iid, field, value, win[field]])\n    out[\"parameter_audit.csv\"] = _csv(\n        [\"instance_id\", \"field\", \"value\", \"winning_layer\"], rows)\n\n    counts = {}\n    for entry in r05[\"withheld\"]:\n        counts[entry[\"reason\"]] = counts.get(entry[\"reason\"], 0) + 1\n    out[\"trigger_eligibility_index.json\"] = _json({\n        \"eligible\": sorted(r05[\"eligible\"]),\n        \"withheld\": sorted(r05[\"withheld\"],\n                           key=lambda w: (w[\"instance_id\"], w[\"reason\"])),\n        \"counts\": {k: counts[k] for k in sorted(counts)},\n    })\n\n    out[\"dependency_graph.json\"] = _json({\n        \"nodes\": r06[\"nodes\"],\n        \"edges\": [{\"prereq\": e[\"prereq\"], \"dependent\": e[\"dependent\"],\n                   \"strength_bp\": e[\"strength_bp\"],\n                   \"declared_seq\": e[\"declared_seq\"], \"kind\": e[\"kind\"]}\n                  for e in r06[\"edges\"]],\n        \"dropped\": sorted(r06[\"dropped\"],\n                          key=lambda d: (d[\"declared_seq\"], d[\"reason\"])),\n    })\n\n    out[\"cycle_break_ledger.json\"] = _json({\n        \"rounds\": len(r07[\"ledger\"]),\n        \"removals\": r07[\"ledger\"],\n        \"surviving_edges\": len(r07[\"edges\"]),\n    })\n\n    out[\"canonical_action_order.json\"] = _json({\n        \"action_order\": r08[\"action_order\"],\n        \"instance_order\": r08[\"instance_order\"],\n        \"withheld\": sorted(r08[\"withheld\"],\n                           key=lambda w: (w[\"instance_id\"], w[\"reason\"])),\n    })\n\n    out[\"resource_demand.csv\"] = _csv(\n        [\"window_id\", \"device_id\", \"instance_id\", \"action_id\",\n         \"base_energy_mwh\", \"intensity_bp\", \"surcharge_bp\",\n         \"window_scale_bp\", \"demand_mwh\"],\n        [[r[\"window_id\"], r[\"device_id\"], r[\"instance_id\"], r[\"action_id\"],\n          r[\"base_energy_mwh\"], r[\"intensity_bp\"], r[\"surcharge_bp\"],\n          r[\"window_scale_bp\"], r[\"demand_mwh\"]]\n         for r in sorted(r09[\"rows\"],\n                         key=lambda r: (r02[\"windows\"][r[\"window_id\"]][\"ordinal\"],\n                                        r[\"device_id\"], r[\"instance_id\"]))])\n\n    out[\"window_capacity_report.csv\"] = _csv(\n        [\"window_id\", \"device_id\", \"ceiling_mwh\", \"reserve_mwh\",\n         \"mandatory_mwh\", \"allocated_mwh\", \"pool_remaining_mwh\", \"overrun\"],\n        [[r[\"window_id\"], r[\"device_id\"], r[\"ceiling_mwh\"], r[\"reserve_mwh\"],\n          r[\"mandatory_mwh\"], r[\"allocated_mwh\"], r[\"pool_remaining_mwh\"],\n          r[\"overrun\"]] for r in r10[\"report\"]])\n\n    out[\"initial_allocation.json\"] = _json({\n        \"count\": len(r10[\"allocated\"]),\n        \"allocated\": [{\"instance_id\": iid, \"window_id\": key[0],\n                       \"device_id\": key[1]}\n                      for iid, key in sorted(r10[\"allocated\"].items())],\n    })\n\n    out[\"displaced_action_queue.json\"] = _json({\n        \"count\": len(r10[\"displaced\"]),\n        \"displaced\": sorted(r10[\"displaced\"],\n                            key=lambda d: (d[\"instance_id\"], d[\"reason\"])),\n    })\n\n    out[\"fallback_expansion.json\"] = _json({\n        \"proposals\": [{\"instance_id\": p[\"instance\"][\"instance_id\"],\n                       \"action_id\": p[\"instance\"][\"action_id\"],\n                       \"stands_in_for\": p[\"stands_in_for\"],\n                       \"window_id\": p[\"instance\"][\"window_id\"],\n                       \"device_id\": p[\"resolved\"][\"device_id\"],\n                       \"demand_mwh\": p[\"demand\"][\"demand_mwh\"]}\n                      for p in sorted(r11[\"proposals\"],\n                                      key=lambda p: p[\"instance\"][\"instance_id\"])],\n        \"terminal\": sorted(r11[\"terminal\"],\n                           key=lambda t: (t[\"instance_id\"], t[\"reason\"])),\n    })\n\n    out[\"precedence_reconciliation.json\"] = _json({\n        \"round_cap\": int(r12[\"round_cap\"]),\n        \"groups\": sorted(r12[\"report\"],\n                         key=lambda g: (g[\"round\"], g[\"window_id\"],\n                                        g[\"device_id\"])),\n        \"overturned\": sorted(r12[\"overturned\"],\n                             key=lambda o: o[\"instance_id\"]),\n    })\n\n    out[\"final_action_order.json\"] = _json({\n        \"count\": len(r14[\"order\"]),\n        \"order\": r14[\"order\"],\n    })\n\n    out[\"cooldown_state.csv\"] = _csv(\n        [\"action_id\", \"cooldown_until_ms\", \"source_layer\"],\n        [[rec[\"action_id\"], rec[\"cooldown_until_ms\"], rec[\"source_layer\"]]\n         for _aid, rec in sorted(r13[\"cooldowns\"].items())])\n\n    out[\"derived_state.json\"] = _json({\n        \"state\": {k: r13[\"state\"][k] for k in sorted(r13[\"state\"])},\n        \"set_at\": {k: {\"trigger_ms\": r13[\"set_at\"][k][0],\n                       \"action_id\": r13[\"set_at\"][k][1]}\n                   for k in sorted(r13[\"set_at\"])},\n    })\n\n    ledger = []\n    for entry in r03[\"ledger\"]:\n        if entry[\"reason\"]:\n            ledger.append([entry[\"instance_id\"] or entry[\"routine_id\"],\n                           entry[\"reason\"], \"r03\"])\n    for entry in r05[\"withheld\"]:\n        ledger.append([entry[\"instance_id\"], entry[\"reason\"], \"r05\"])\n    for entry in r08[\"withheld\"]:\n        ledger.append([entry[\"instance_id\"], entry[\"reason\"], \"r08\"])\n    for entry in r09[\"quarantined\"]:\n        ledger.append([entry[\"instance_id\"], entry[\"reason\"], \"r09\"])\n    for entry in r10[\"displaced\"]:\n        ledger.append([entry[\"instance_id\"], entry[\"reason\"], \"r10\"])\n    for entry in r12[\"terminal\"]:\n        ledger.append([entry[\"instance_id\"], entry[\"reason\"], \"r12\"])\n    for entry in r14[\"withdrawn\"]:\n        ledger.append([entry[\"instance_id\"], entry[\"reason\"], \"r14\"])\n    for entry in r14[\"readmitted\"]:\n        ledger.append([entry[\"instance_id\"], entry[\"reason\"], \"r14\"])\n    out[\"suppression_ledger.csv\"] = _csv(\n        [\"instance_id\", \"reason\", \"stage\"], sorted(ledger))\n\n    remaining = dict(data[\"snapshot\"].get(\"oneshot_remaining\", {}))\n    for oid, used in r13b[\"consumed\"].items():\n        left = int(remaining.get(oid, 0)) - used\n        remaining[oid] = left if left > 0 else 0\n    out[\"next_state_snapshot.json\"] = _json({\n        \"cycle_key\": header[\"cycle_key\"],\n        \"cycle_index\": int(data[\"runtime\"][\"cycle_index\"]) + 1,\n        \"actions\": {aid: {\"last_fired_ms\": r13b[\"last_fired\"][aid],\n                          \"cooldown_until_ms\":\n                          r13b[\"cooldowns\"][aid][\"cooldown_until_ms\"]}\n                    for aid in sorted(r13b[\"last_fired\"])},\n        \"oneshot_remaining\": {k: int(remaining[k]) for k in sorted(remaining)},\n        \"state\": {k: r13b[\"state\"][k] for k in sorted(r13b[\"state\"])},\n    })\n\n    per_context = {}\n    per_device = {}\n    per_window = {}\n    total_demand = 0\n    for iid in r14[\"order\"]:\n        inst = _instance_of(iid, r08, r12)\n        rec = _resolved_of(iid, r04, r12)\n        demand = (r09[\"by_instance\"].get(iid) or r14[\"demand\"].get(iid)\n                  or r12[\"proposal_index\"][iid][\"demand\"])\n        value = demand[\"demand_mwh\"]\n        total_demand += value\n        ctx = per_context.setdefault(rec[\"context_id\"],\n                                     {\"instances\": [], \"demand_mwh\": 0})\n        ctx[\"instances\"].append(iid)\n        ctx[\"demand_mwh\"] += value\n        dev = per_device.setdefault(rec[\"device_id\"],\n                                    {\"instances\": 0, \"demand_mwh\": 0})\n        dev[\"instances\"] += 1\n        dev[\"demand_mwh\"] += value\n        win = per_window.setdefault(inst[\"window_id\"],\n                                    {\"instances\": [], \"demand_mwh\": 0})\n        win[\"instances\"].append(iid)\n        win[\"demand_mwh\"] += value\n    out[\"per_context_manifest.json\"] = _json({\n        \"contexts\": {cid: {\"instances\": sorted(per_context[cid][\"instances\"]),\n                           \"demand_mwh\": per_context[cid][\"demand_mwh\"]}\n                     for cid in sorted(per_context)},\n    })\n\n    circuit_of = {}\n    for entry in data[\"circuits\"]:\n        if entry.get(\"role\") != \"member\":\n            continue\n        circuit_of[entry[\"device\"]] = entry[\"id\"]\n    out[\"per_device_manifest.csv\"] = _csv(\n        [\"device_id\", \"circuit_id\", \"instances\", \"demand_mwh\"],\n        [[did, circuit_of.get(did, \"\"), per_device[did][\"instances\"],\n          per_device[did][\"demand_mwh\"]] for did in sorted(per_device)])\n\n    out[\"daily_automation_manifest.json\"] = _json({\n        \"cycle_key\": header[\"cycle_key\"],\n        \"profile\": header[\"profile\"],\n        \"windows\": [{\"window_id\": wid,\n                     \"ordinal\": r02[\"windows\"][wid][\"ordinal\"],\n                     \"instances\": sorted(per_window[wid][\"instances\"]),\n                     \"demand_mwh\": per_window[wid][\"demand_mwh\"]}\n                    for wid in sorted(per_window,\n                                      key=lambda w: r02[\"windows\"][w][\"ordinal\"])],\n        \"totals\": {\"instances\": len(r14[\"order\"]),\n                   \"demand_mwh\": total_demand,\n                   \"terminal\": len(r12[\"terminal\"]) + len(r14[\"withdrawn\"]),\n                   \"readmitted\": len(r14[\"readmitted\"])},\n    })\n\n    prior = {}\n    for rec in data[\"ledger\"]:\n        did = rec[\"device_id\"]\n        idx = int(rec[\"cycle_index\"])\n        cur = prior.get(did)\n        if cur is None or idx > cur[0]:\n            prior[did] = (idx, int(rec[\"consumed\"][\"value\"]))\n    util_rows = []\n    for did in sorted(set(list(per_device.keys()) + list(circuit_of.keys()))):\n        ceiling = 0\n        for (wid, dev), entry in data[\"workbook\"][\"ceilings\"].items():\n            if dev != did:\n                continue\n            value, _b = _convert_cell(data, entry)\n            ceiling += value\n        allocated = per_device.get(did, {}).get(\"demand_mwh\", 0)\n        ratio = ratio12(Fraction(allocated, ceiling)) if ceiling else ratio12(0)\n        prior_value = prior.get(did, (0, 0))[1]\n        util_rows.append([circuit_of.get(did, \"\"), did, ceiling, allocated,\n                          ratio, prior_value, allocated - prior_value])\n    out[\"resource_utilization_report.csv\"] = _csv(\n        [\"circuit_id\", \"device_id\", \"ceiling_mwh\", \"allocated_mwh\",\n         \"utilisation_ratio\", \"prior_cycle_mwh\", \"delta_mwh\"],\n        sorted(util_rows, key=lambda r: (r[0], r[1])))\n\n    lines = [\"# Terminal actions for cycle \" + header[\"cycle_key\"], \"\"]\n    terminal = {}\n    for entry in r12[\"terminal\"]:\n        terminal[entry[\"instance_id\"]] = entry[\"reason\"]\n    for entry in r14[\"withdrawn\"]:\n        terminal[entry[\"instance_id\"]] = entry[\"reason\"]\n    lines.append(\"| instance_id | reason |\")\n    lines.append(\"| --- | --- |\")\n    for iid in sorted(terminal):\n        lines.append(\"| \" + iid + \" | \" + terminal[iid] + \" |\")\n    lines.append(\"\")\n    lines.append(\"Total terminal instances: \" + str(len(terminal)))\n    out[\"terminal_action_report.md\"] = _text(lines)\n\n    audit = []\n    sizes = {\"r01\": len(r01[\"actions\"]), \"r02\": len(r02[\"decisions\"]),\n             \"r03\": len(r03[\"instances\"]), \"r04\": len(r04[\"resolved\"]),\n             \"r05\": len(r05[\"eligible\"]), \"r06\": len(r06[\"edges\"]),\n             \"r07\": len(r07[\"ledger\"]), \"r08\": len(r08[\"instance_order\"]),\n             \"r09\": len(r09[\"rows\"]), \"r10\": len(r10[\"allocated\"]),\n             \"r11\": len(r11[\"proposals\"]), \"r12\": len(r12[\"survivors\"]),\n             \"r13\": len(r13[\"order\"]), \"r14\": len(r14[\"order\"])}\n    for sid in STAGE_IDS:\n        audit.append({\"stage\": sid, \"records\": sizes[sid]})\n    out[\"audit_ledger.jsonl\"] = _jsonl(audit)\n\n    core_names = [\"unit_normalization.json\", \"canonical_action_order.json\",\n                  \"final_action_order.json\", \"daily_automation_manifest.json\",\n                  \"next_state_snapshot.json\"]\n    core_digest = sha256_hex(b\"\".join(out[name] for name in core_names))\n    manifest_lines = []\n    for name in sorted(DOCUMENTS):\n        manifest_lines.append(sha256_hex(out[name]) + \"  \" + name)\n    publication = sha256_hex(\n        \"\".join(line + NL for line in manifest_lines).encode(\"utf-8\"))\n    manifest_lines.append(\"core \" + core_digest)\n    manifest_lines.append(\"publication \" + publication)\n    out[\"run_manifest.txt\"] = _text(manifest_lines)\n\n    out[\"summary.json\"] = _json({\n        \"cycle_key\": header[\"cycle_key\"],\n        \"profile\": header[\"profile\"],\n        \"core_digest\": core_digest,\n        \"publication_digest\": publication,\n        \"control_totals\": {\n            \"actions_read\": len(r01[\"actions\"]),\n            \"aliases_bound\": sum(1 for d in r02[\"decisions\"]\n                                 if d[\"status\"] == \"bound\"),\n            \"instances_expanded\": len(r03[\"instances\"]),\n            \"instances_eligible\": len(r05[\"eligible\"]),\n            \"edges_kept\": len(r06[\"edges\"]),\n            \"cycles_settled\": len(r07[\"ledger\"]),\n            \"demand_rows\": len(r09[\"rows\"]),\n            \"initial_allocations\": len(r10[\"allocated\"]),\n            \"displaced\": len(r10[\"displaced\"]),\n            \"fallback_proposals\": len(r11[\"proposals\"]),\n            \"overturned\": len(r12[\"overturned\"]),\n            \"final_instances\": len(r14[\"order\"]),\n            \"readmitted\": len(r14[\"readmitted\"]),\n            \"terminal\": len(r12[\"terminal\"]) + len(r14[\"withdrawn\"]),\n            \"total_demand_mwh\": total_demand,\n        },\n    })\n    return out\n\n\ndef _convert_cell(data, entry):\n    from daybreak.loading import convert\n    from daybreak.stages import _absent\n    if _absent(entry[0]):\n        return 0, None\n    value, base = convert(data[\"units\"], entry[0], entry[1])\n    return (value if value is not None else 0), base\n",
    "src/daybreak/stages.py": "\"\"\"Stages r01 to r09 of the daybreak routing chain.\"\"\"\nfrom fractions import Fraction\n\nfrom daybreak.loading import (LAYER_ORDER, POLICY_FIELDS, Unresolved, convert,\n                              live_rows)\nfrom daybreak.util import half_even, PIPE\n\nABSENT = \"-\"\nGEN_CAP = 512\n\n\ndef _absent(text):\n    \"\"\"True when a policy cell records nothing.\"\"\"\n    return text is None or str(text).strip() in (\"\", ABSENT)\n\n\ndef _q(rec, field, unit_field, units, notes, where):\n    value, base = convert(units, rec[field], rec[unit_field])\n    if value is None:\n        notes.append({\"record\": where, \"field\": field,\n                      \"unit\": rec[unit_field], \"reason\": \"UNCONVERTIBLE_UNIT\"})\n    return value\n\n\n# --------------------------------------------------------------------------\n# r01 unit normalisation\n# --------------------------------------------------------------------------\ndef stage_r01(data):\n    units = data[\"units\"]\n    notes = []\n    counts = {}\n    totals = {\"duration_ms\": 0, \"energy_mwh\": 0, \"weight_bp\": 0}\n    actions = {}\n    for row in data[\"catalogue\"]:\n        aid = row[\"action_id\"]\n        where = \"action_catalogue.csv:\" + aid\n        energy = _q(row, \"energy_value\", \"energy_unit\", units, notes, where)\n        duration = _q(row, \"duration_value\", \"duration_unit\", units, notes, where)\n        for token in (row[\"energy_unit\"], row[\"duration_unit\"]):\n            counts[token] = counts.get(token, 0) + 1\n        if energy is None or duration is None:\n            continue\n        actions[aid] = {\n            \"action_id\": aid, \"name\": row[\"action_name\"],\n            \"device_ref\": row[\"device_ref\"], \"context_ref\": row[\"context_ref\"],\n            \"energy_mwh\": energy, \"duration_ms\": duration,\n            \"action_class\": row[\"action_class\"],\n            \"declared_seq\": int(row[\"declared_seq\"]), \"role\": row[\"role\"],\n        }\n        totals[\"energy_mwh\"] += energy\n        totals[\"duration_ms\"] += duration\n    strength = {}\n    for row in data[\"edges\"]:\n        seq = int(row[\"declared_seq\"])\n        counts[row[\"strength_unit\"]] = counts.get(row[\"strength_unit\"], 0) + 1\n        value = _q(row, \"strength_value\", \"strength_unit\", units, notes,\n                   \"dependency_edges.tsv:\" + str(seq))\n        if value is None:\n            continue\n        strength[seq] = value\n        totals[\"weight_bp\"] += value\n    return {\"actions\": actions, \"edge_strength\": strength,\n            \"unit_counts\": counts, \"notes\": notes, \"totals\": totals}\n\n\n# --------------------------------------------------------------------------\n# r02 identifier resolution\n# --------------------------------------------------------------------------\ndef stage_r02(data, r01):\n    ranks = {}\n    for row in data[\"sources\"]:\n        if row[\"status\"] != \"in_force\":\n            continue\n        ranks[row[\"source_name\"]] = int(row[\"source_rank\"])\n    pool = []\n    for name, rows in ((\"alias_crosswalk.tsv\", data[\"alias_primary\"]),\n                       (\"identifier_supplement.psv\", data[\"alias_supplement\"])):\n        if name not in ranks:\n            continue\n        for row in rows:\n            alias = row.get(\"alias\", \"\")\n            if not alias:\n                continue\n            pool.append((ranks[name], int(row[\"declared_seq\"]), name,\n                         alias, row[\"canonical\"], row[\"kind\"]))\n    pool.sort(key=lambda item: (item[0], item[1], item[3]))\n    bindings = {}\n    decisions = []\n    for rank, seq, source, alias, canonical, kind in pool:\n        if alias == canonical:\n            decisions.append({\"alias\": alias, \"canonical\": canonical,\n                              \"kind\": kind, \"source\": source, \"hops\": 0,\n                              \"status\": \"self\"})\n            continue\n        if alias in bindings:\n            decisions.append({\"alias\": alias, \"canonical\": canonical,\n                              \"kind\": kind, \"source\": source, \"hops\": 0,\n                              \"status\": \"collision\"})\n            continue\n        bindings[alias] = canonical\n        decisions.append({\"alias\": alias, \"canonical\": canonical,\n                          \"kind\": kind, \"source\": source, \"hops\": 1,\n                          \"status\": \"bound\"})\n    cap = int(data[\"controls\"][\"alias_hop_cap\"])\n    resolved_cache = {}\n    cyclic = set()\n\n    def resolve(name):\n        if name in resolved_cache:\n            return resolved_cache[name]\n        seen = [name]\n        cur = name\n        hops = 0\n        while cur in bindings and hops < cap:\n            cur = bindings[cur]\n            hops += 1\n            if cur in seen:\n                cyclic.add(name)\n                cur = name\n                break\n            seen.append(cur)\n        resolved_cache[name] = cur\n        return cur\n\n    for decision in decisions:\n        if decision[\"status\"] == \"bound\":\n            target = resolve(decision[\"alias\"])\n            decision[\"canonical\"] = target\n            decision[\"hops\"] = 0 if target == decision[\"alias\"] else 1\n            if decision[\"alias\"] in cyclic:\n                decision[\"status\"] = \"cycle\"\n    windows = window_grid(data)\n    devices = device_grid(data)\n    contexts = context_grid(data)\n    known = {\"action\": set(r01[\"actions\"]), \"device\": set(devices),\n             \"context\": set(contexts)}\n    return {\"bindings\": bindings, \"decisions\": decisions, \"resolve\": resolve,\n            \"known\": known, \"windows\": windows, \"devices\": devices,\n            \"contexts\": contexts, \"cyclic\": sorted(cyclic)}\n\n\ndef window_grid(data):\n    \"\"\"Window id -> ordinal, start and end.\"\"\"\n    units = data[\"units\"]\n    frozen = data[\"header\"][\"window_frozen_revisions\"]\n    rows = sorted(data[\"window_rows\"], key=lambda r: int(r[\"ordinal\"]))\n    live = live_rows(rows, \"window_id\", lambda k: frozen.get(k))\n    out = {}\n    cursor = int(data[\"header\"][\"origin_ms\"])\n    for wid in sorted(live, key=lambda k: int(live[k][\"ordinal\"])):\n        row = live[wid]\n        delta, _b = convert(units, row[\"start_delta_value\"],\n                            row[\"start_delta_unit\"])\n        span, _b2 = convert(units, row[\"span_value\"], row[\"span_unit\"])\n        if delta is None or span is None:\n            raise Unresolved(\"window grid carries an unconvertible quantity\")\n        start = cursor + delta\n        cursor = start\n        out[wid] = {\"window_id\": wid, \"ordinal\": int(row[\"ordinal\"]),\n                    \"start_ms\": start, \"end_ms\": start + span,\n                    \"capacity_class\": row[\"capacity_class\"]}\n    return out\n\n\ndef device_grid(data):\n    frozen = data[\"header\"][\"device_frozen_revisions\"]\n    live = live_rows(data[\"device_rows\"], \"device_id\", lambda k: frozen.get(k))\n    return {did: {\"device_id\": did, \"device_class\": row[\"device_class\"],\n                  \"slots\": int(row[\"slots\"])}\n            for did, row in live.items()}\n\n\ndef context_grid(data):\n    units = data[\"units\"]\n    out = {}\n    cursor = int(data[\"header\"][\"origin_ms\"])\n    for row in data[\"context_spans\"]:\n        cid = row[\"context_id\"]\n        delta, _b = convert(units, row[\"start_delta_value\"],\n                            row[\"start_delta_unit\"])\n        length, _b2 = convert(units, row[\"length_value\"], row[\"length_unit\"])\n        if delta is None or length is None:\n            continue\n        if row[\"start_delta_sign\"] == \"-\":\n            delta = -delta\n        cursor = cursor + delta\n        if \".\" in cid or \"hist\" in cid:\n            continue\n        out[cid] = {\"context_id\": cid, \"context_name\": row[\"context_name\"],\n                    \"start_ms\": cursor, \"end_ms\": cursor + length}\n    return out\n\n\n# --------------------------------------------------------------------------\n# r03 routine expansion\n# --------------------------------------------------------------------------\ndef _routine_cap(data, rid, routine_layer):\n    \"\"\"Occurrence cap of one routine.\"\"\"\n    cap = data[\"memo_caps\"].get(rid)\n    if cap is not None:\n        return cap, \"memo\"\n    rec = routine_layer.get(rid, {})\n    if \"max_occurrences\" in rec:\n        return rec[\"max_occurrences\"], \"routine\"\n    return int(data[\"controls\"][\"default_max_occurrences\"]), \"default\"\n\n\ndef routine_layer_records(data):\n    out = {}\n    for key, spec in data[\"routine_defaults\"].items():\n        if not key.startswith(\"RT-\"):\n            continue\n        parts = str(spec).split(PIPE)\n        rec = {}\n        if len(parts) == 4:\n            if not _absent(parts[0]):\n                rec[\"tier\"] = int(parts[0])\n            if not _absent(parts[1]):\n                rec[\"intensity_bp\"] = int(parts[1])\n            if not _absent(parts[2]):\n                rec[\"cooldown_ms\"] = int(parts[2]) * 60000\n            if not _absent(parts[3]):\n                rec[\"max_occurrences\"] = int(parts[3])\n        out[key] = rec\n    return out\n\n\ndef stage_r03(data, r01, r02):\n    units = data[\"units\"]\n    routine_layer = routine_layer_records(data)\n    windows = r02[\"windows\"]\n    ordered = sorted(windows.values(), key=lambda w: w[\"ordinal\"])\n    instances = []\n    ledger = []\n    for row in sorted(data[\"routines\"], key=lambda r: r[\"routine_id\"]):\n        rid = row[\"routine_id\"]\n        aid = r02[\"resolve\"](row[\"action_ref\"])\n        if row[\"enabled\"] != \"yes\":\n            ledger.append({\"routine_id\": rid, \"instance_id\": \"\",\n                           \"action_id\": aid, \"occurrence_index\": -1,\n                           \"trigger_ms\": 0, \"window_id\": \"\",\n                           \"status\": \"withheld\", \"reason\": \"RETIRED_ROUTINE\"})\n            continue\n        if aid not in r01[\"actions\"]:\n            ledger.append({\"routine_id\": rid, \"instance_id\": \"\",\n                           \"action_id\": aid, \"occurrence_index\": -1,\n                           \"trigger_ms\": 0, \"window_id\": \"\",\n                           \"status\": \"withheld\", \"reason\": \"UNRESOLVED_ACTION\"})\n            continue\n        anchor, _b = convert(units, row[\"anchor_value\"], row[\"anchor_unit\"])\n        period, _b2 = convert(units, row[\"period_value\"], row[\"period_unit\"])\n        span0, _b3 = convert(units, row[\"span_start_value\"],\n                             row[\"span_start_unit\"])\n        span1, _b4 = convert(units, row[\"span_end_value\"], row[\"span_end_unit\"])\n        if None in (anchor, period, span0, span1):\n            ledger.append({\"routine_id\": rid, \"instance_id\": \"\",\n                           \"action_id\": aid, \"occurrence_index\": -1,\n                           \"trigger_ms\": 0, \"window_id\": \"\",\n                           \"status\": \"withheld\",\n                           \"reason\": \"UNCONVERTIBLE_UNIT\"})\n            continue\n        if row[\"anchor_sign\"] == \"-\":\n            anchor = -anchor\n        cap, _src = _routine_cap(data, rid, routine_layer)\n        if cap <= 0:\n            ledger.append({\"routine_id\": rid, \"instance_id\": \"\",\n                           \"action_id\": aid, \"occurrence_index\": -1,\n                           \"trigger_ms\": 0, \"window_id\": \"\",\n                           \"status\": \"withheld\",\n                           \"reason\": \"OCCURRENCE_CAP_ZERO\"})\n            continue\n        kept = 0\n        step = 0\n        while step < GEN_CAP and kept < cap:\n            trigger = anchor + step * period\n            if trigger >= span1:\n                break\n            if trigger >= span0:\n                wid = \"\"\n                for win in ordered:\n                    if win[\"start_ms\"] <= trigger < win[\"end_ms\"]:\n                        wid = win[\"window_id\"]\n                        break\n                iid = rid + \"#\" + str(kept).rjust(2, \"0\")\n                if wid == \"\":\n                    ledger.append({\"routine_id\": rid, \"instance_id\": iid,\n                                   \"action_id\": aid, \"occurrence_index\": kept,\n                                   \"trigger_ms\": trigger, \"window_id\": \"\",\n                                   \"status\": \"withheld\",\n                                   \"reason\": \"OUT_OF_DAY\"})\n                else:\n                    instances.append({\"instance_id\": iid, \"routine_id\": rid,\n                                      \"action_id\": aid, \"occurrence_index\": kept,\n                                      \"trigger_ms\": trigger, \"window_id\": wid})\n                    ledger.append({\"routine_id\": rid, \"instance_id\": iid,\n                                   \"action_id\": aid, \"occurrence_index\": kept,\n                                   \"trigger_ms\": trigger, \"window_id\": wid,\n                                   \"status\": \"expanded\", \"reason\": \"\"})\n                kept += 1\n            if period == 0:\n                break\n            step += 1\n    return {\"instances\": instances, \"ledger\": ledger,\n            \"routine_layer\": routine_layer}\n\n\n# --------------------------------------------------------------------------\n# r04 policy layer resolution\n# --------------------------------------------------------------------------\ndef _layer_records(data, r01, r02, r03):\n    units = data[\"units\"]\n    mandatory = {}\n    for row in data[\"directive\"][\"mandates\"]:\n        key = (row[\"action\"], row[\"window\"])\n        prev = mandatory.get(key)\n        if prev is None or row[\"seq\"] > prev[\"seq\"]:\n            mandatory[key] = row\n    oneshot = {}\n    remaining = dict(data[\"snapshot\"].get(\"oneshot_remaining\", {}))\n    for rec in data[\"overrides\"]:\n        oid = rec[\"override_id\"]\n        aid = rec[\"action_id\"]\n        expires, _b = convert(units, rec[\"expires\"][\"value\"],\n                              rec[\"expires\"][\"unit\"])\n        entry = {\"override_id\": oid, \"action_id\": aid,\n                 \"expires_ms\": expires if expires is not None else 0,\n                 \"remaining\": int(remaining.get(oid, rec.get(\"remaining\", 0)))}\n        if \"tier\" in rec:\n            entry[\"tier\"] = int(rec[\"tier\"])\n        if \"intensity\" in rec:\n            entry[\"intensity_bp\"] = convert(units, rec[\"intensity\"][\"value\"],\n                                            rec[\"intensity\"][\"unit\"])[0]\n        if \"cooldown\" in rec:\n            entry[\"cooldown_ms\"] = convert(units, rec[\"cooldown\"][\"value\"],\n                                           rec[\"cooldown\"][\"unit\"])[0]\n        oneshot.setdefault(aid, []).append(entry)\n    for aid in oneshot:\n        oneshot[aid].sort(key=lambda e: e[\"override_id\"])\n    context = {}\n    for row in data[\"context_policies\"]:\n        cid = row[\"context_id\"]\n        if cid not in r02[\"contexts\"]:\n            continue\n        rec = {}\n        if not _absent(row[\"tier\"]):\n            rec[\"tier\"] = int(row[\"tier\"])\n        if not _absent(row[\"intensity_value\"]) and not _absent(row[\"intensity_unit\"]):\n            rec[\"intensity_bp\"] = convert(units, row[\"intensity_value\"],\n                                          row[\"intensity_unit\"])[0]\n        if not _absent(row[\"suppress\"]):\n            rec[\"suppress\"] = row[\"suppress\"] == \"true\"\n        context[cid] = rec\n    frozen = data[\"header\"][\"device_frozen_revisions\"]\n    device = {}\n    live = live_rows(data[\"device_policy_rows\"], \"device_id\",\n                     lambda k: frozen.get(k))\n    for did, row in live.items():\n        rec = {}\n        if not _absent(row[\"tier\"]):\n            rec[\"tier\"] = int(row[\"tier\"])\n        if not _absent(row[\"intensity_value\"]) and not _absent(row[\"intensity_unit\"]):\n            rec[\"intensity_bp\"] = convert(units, row[\"intensity_value\"],\n                                          row[\"intensity_unit\"])[0]\n        if not _absent(row[\"cooldown_value\"]) and not _absent(row[\"cooldown_unit\"]):\n            rec[\"cooldown_ms\"] = convert(units, row[\"cooldown_value\"],\n                                         row[\"cooldown_unit\"])[0]\n        device[did] = rec\n    action = {}\n    for rec in data[\"action_policies\"]:\n        out = {}\n        if \"tier\" in rec:\n            out[\"tier\"] = int(rec[\"tier\"])\n        if \"intensity\" in rec:\n            out[\"intensity_bp\"] = convert(units, rec[\"intensity\"][\"value\"],\n                                          rec[\"intensity\"][\"unit\"])[0]\n        if \"cooldown\" in rec:\n            out[\"cooldown_ms\"] = convert(units, rec[\"cooldown\"][\"value\"],\n                                         rec[\"cooldown\"][\"unit\"])[0]\n        if \"suppress\" in rec:\n            out[\"suppress\"] = bool(rec[\"suppress\"])\n        if \"fallback_chain\" in rec:\n            out[\"fallback_chain\"] = list(rec[\"fallback_chain\"])\n        action[rec[\"action_id\"]] = out\n    g = data[\"global_defaults\"]\n    glob = {\n        \"tier\": int(g[\"tier\"]),\n        \"intensity_bp\": convert(units, g[\"intensity_value\"],\n                                g[\"intensity_unit\"])[0],\n        \"cooldown_ms\": convert(units, g[\"cooldown_value\"],\n                               g[\"cooldown_unit\"])[0],\n        \"mandatory\": g[\"mandatory\"] == \"true\",\n        \"max_occurrences\": int(g[\"max_occurrences\"]),\n        \"suppress\": g[\"suppress\"] == \"true\",\n        \"fallback_chain\": [],\n    }\n    ranks = {name: int(data[\"directive\"][\"ranks\"][name]) for name in LAYER_ORDER}\n    return {\"mandatory\": mandatory, \"oneshot\": oneshot, \"context\": context,\n            \"device\": device, \"action\": action,\n            \"routine\": r03[\"routine_layer\"], \"global\": glob, \"ranks\": ranks}\n\n\ndef cooldown_floors(data):\n    frozen = int(data[\"snapshot\"][\"frozen_revision_cooldown_register\"])\n    live = live_rows(data[\"cooldown_rows\"], \"action_class\", lambda k: frozen)\n    out = {}\n    for cls, row in live.items():\n        value, _b = convert(data[\"units\"], row[\"floor_value\"], row[\"floor_unit\"])\n        out[cls] = value if value is not None else 0\n    return out\n\n\ndef resolve_policy(layers, floors, r01, r02, instance):\n    \"\"\"Resolved policy of one instance and the layer that settled each field.\"\"\"\n    action = r01[\"actions\"][instance[\"action_id\"]]\n    did = r02[\"resolve\"](action[\"device_ref\"])\n    cid = r02[\"resolve\"](action[\"context_ref\"])\n    trigger = instance[\"trigger_ms\"]\n    applicable = []\n    mrec = layers[\"mandatory\"].get((instance[\"action_id\"],\n                                    instance[\"window_id\"]))\n    if mrec is not None:\n        applicable.append((\"mandatory\", {\"tier\": mrec[\"tier\"],\n                                         \"mandatory\": mrec[\"mandatory\"]}))\n    else:\n        applicable.append((\"mandatory\", {}))\n    chosen = None\n    for entry in layers[\"oneshot\"].get(instance[\"action_id\"], []):\n        if entry[\"remaining\"] > 0 and trigger < entry[\"expires_ms\"]:\n            chosen = entry\n            break\n    if chosen is None:\n        applicable.append((\"oneshot\", {}))\n    else:\n        rec = {k: v for k, v in chosen.items()\n               if k in (\"tier\", \"intensity_bp\", \"cooldown_ms\")}\n        applicable.append((\"oneshot\", rec))\n    ctx = r02[\"contexts\"].get(cid)\n    if ctx is not None and ctx[\"start_ms\"] <= trigger < ctx[\"end_ms\"]:\n        applicable.append((\"context\", layers[\"context\"].get(cid, {})))\n    else:\n        applicable.append((\"context\", {}))\n    applicable.append((\"device\", layers[\"device\"].get(did, {})))\n    applicable.append((\"action\", layers[\"action\"].get(instance[\"action_id\"], {})))\n    applicable.append((\"routine\", layers[\"routine\"].get(instance[\"routine_id\"], {})))\n    applicable.append((\"global\", layers[\"global\"]))\n    applicable.sort(key=lambda item: layers[\"ranks\"][item[0]])\n    resolved = {}\n    winner = {}\n    for field in POLICY_FIELDS:\n        for name, rec in applicable:\n            if field in rec and rec[field] is not None:\n                resolved[field] = rec[field]\n                winner[field] = name\n                break\n    floor = floors.get(action[\"action_class\"], 0)\n    if resolved[\"cooldown_ms\"] < floor:\n        resolved[\"cooldown_ms\"] = floor\n        winner[\"cooldown_ms\"] = \"class_floor\"\n    resolved[\"device_id\"] = did\n    resolved[\"context_id\"] = cid\n    resolved[\"oneshot_id\"] = chosen[\"override_id\"] if chosen else \"\"\n    return resolved, winner\n\n\ndef stage_r04(data, r01, r02, r03):\n    layers = _layer_records(data, r01, r02, r03)\n    floors = cooldown_floors(data)\n    resolved = {}\n    winners = {}\n    counts = {name: 0 for name in LAYER_ORDER}\n    counts[\"class_floor\"] = 0\n    for inst in r03[\"instances\"]:\n        rec, win = resolve_policy(layers, floors, r01, r02, inst)\n        resolved[inst[\"instance_id\"]] = rec\n        winners[inst[\"instance_id\"]] = win\n        for field in POLICY_FIELDS:\n            counts[win[field]] = counts.get(win[field], 0) + 1\n    return {\"layers\": layers, \"floors\": floors, \"resolved\": resolved,\n            \"winners\": winners, \"counts\": counts}\n\n\n# --------------------------------------------------------------------------\n# r05 initial eligibility\n# --------------------------------------------------------------------------\ndef prior_state(data):\n    units = data[\"units\"]\n    snapshot = data[\"snapshot\"].get(\"actions\", {})\n    last = {}\n    suppressed = {}\n    for aid, rec in snapshot.items():\n        if \"last_fired_ms\" in rec:\n            last[aid] = int(rec[\"last_fired_ms\"])\n        if \"suppressed_until_ms\" in rec:\n            suppressed[aid] = int(rec[\"suppressed_until_ms\"])\n    for row in data[\"archive\"]:\n        aid = row[\"action_id\"]\n        if aid not in last:\n            last[aid] = int(row[\"last_fired_ms\"])\n    preceding = int(data[\"runtime\"][\"preceding_cycle_index\"])\n    carried = {}\n    for rec in data[\"prior_journal\"]:\n        if int(rec[\"cycle_index\"]) != preceding:\n            continue\n        value, _b = convert(units, rec[\"carried_cooldown\"][\"value\"],\n                            rec[\"carried_cooldown\"][\"unit\"])\n        if value is None:\n            continue\n        aid = rec[\"action_id\"]\n        if aid not in carried or value > carried[aid]:\n            carried[aid] = value\n    return last, suppressed, carried\n\n\ndef stage_r05(data, r01, r02, r03, r04):\n    last, suppressed, carried = prior_state(data)\n    eligible = []\n    withheld = []\n    for inst in r03[\"instances\"]:\n        aid = inst[\"action_id\"]\n        rec = r04[\"resolved\"][inst[\"instance_id\"]]\n        cooldown = rec[\"cooldown_ms\"]\n        if aid in carried and carried[aid] > cooldown:\n            cooldown = carried[aid]\n        trigger = inst[\"trigger_ms\"]\n        if rec[\"suppress\"]:\n            withheld.append({\"instance_id\": inst[\"instance_id\"],\n                             \"reason\": \"SUPPRESSED\"})\n            continue\n        if trigger < suppressed.get(aid, 0):\n            withheld.append({\"instance_id\": inst[\"instance_id\"],\n                             \"reason\": \"SUPPRESSED\"})\n            continue\n        if aid in last and trigger - last[aid] < cooldown:\n            withheld.append({\"instance_id\": inst[\"instance_id\"],\n                             \"reason\": \"COOLDOWN\"})\n            continue\n        eligible.append(inst[\"instance_id\"])\n    return {\"eligible\": eligible, \"withheld\": withheld, \"last\": last,\n            \"suppressed\": suppressed, \"carried\": carried}\n\n\n# --------------------------------------------------------------------------\n# r06 dependency graph\n# --------------------------------------------------------------------------\ndef stage_r06(data, r01, r02):\n    dropped = []\n    kept = {}\n    for row in data[\"edges\"]:\n        seq = int(row[\"declared_seq\"])\n        strength = r01[\"edge_strength\"].get(seq)\n        prereq = r02[\"resolve\"](row[\"prereq_ref\"])\n        dependent = r02[\"resolve\"](row[\"dependent_ref\"])\n        if strength is None:\n            dropped.append({\"declared_seq\": seq, \"prereq\": prereq,\n                            \"dependent\": dependent,\n                            \"reason\": \"UNCONVERTIBLE_UNIT\"})\n            continue\n        if prereq not in r01[\"actions\"] or dependent not in r01[\"actions\"]:\n            dropped.append({\"declared_seq\": seq, \"prereq\": prereq,\n                            \"dependent\": dependent,\n                            \"reason\": \"UNRESOLVED_ENDPOINT\"})\n            continue\n        if prereq == dependent:\n            dropped.append({\"declared_seq\": seq, \"prereq\": prereq,\n                            \"dependent\": dependent, \"reason\": \"SELF_EDGE\"})\n            continue\n        key = (prereq, dependent)\n        if key in kept:\n            prev = kept[key]\n            dropped.append({\"declared_seq\": seq, \"prereq\": prereq,\n                            \"dependent\": dependent, \"reason\": \"DUPLICATE_EDGE\"})\n            if strength > prev[\"strength_bp\"]:\n                prev[\"strength_bp\"] = strength\n            if seq < prev[\"declared_seq\"]:\n                prev[\"declared_seq\"] = seq\n            continue\n        kept[key] = {\"prereq\": prereq, \"dependent\": dependent,\n                     \"strength_bp\": strength, \"declared_seq\": seq,\n                     \"kind\": row[\"edge_kind\"]}\n    edges = [kept[k] for k in sorted(kept)]\n    nodes = sorted({e[\"prereq\"] for e in edges} | {e[\"dependent\"] for e in edges})\n    return {\"edges\": edges, \"nodes\": nodes, \"dropped\": dropped}\n\n\n# --------------------------------------------------------------------------\n# r07 cycle settlement\n# --------------------------------------------------------------------------\ndef find_cycle(nodes, out_edges):\n    \"\"\"Deterministic search. Nodes are entered in ascending order and each\n    node's successors are visited in ascending order; the first back edge\n    reached names the cycle.\"\"\"\n    colour = {n: 0 for n in nodes}\n    stack = []\n\n    def walk(node):\n        colour[node] = 1\n        stack.append(node)\n        for nxt in out_edges.get(node, []):\n            if colour.get(nxt, 0) == 1:\n                idx = stack.index(nxt)\n                return stack[idx:] + [nxt]\n            if colour.get(nxt, 0) == 0:\n                found = walk(nxt)\n                if found is not None:\n                    return found\n        stack.pop()\n        colour[node] = 2\n        return None\n\n    for node in nodes:\n        if colour[node] == 0:\n            found = walk(node)\n            if found is not None:\n                return found\n    return None\n\n\ndef _tier_of(action_id, tier_index, fallback_tier):\n    return tier_index.get(action_id, fallback_tier)\n\n\ndef stage_r07(data, r06, tier_index, fallback_tier):\n    edges = [dict(e) for e in r06[\"edges\"]]\n    ledger = []\n    rounds = 0\n    while True:\n        rounds += 1\n        if rounds > 4096:\n            raise Unresolved(\"cycle settlement did not terminate\")\n        out_edges = {}\n        index = {}\n        for e in edges:\n            out_edges.setdefault(e[\"prereq\"], []).append(e[\"dependent\"])\n            index[(e[\"prereq\"], e[\"dependent\"])] = e\n        for key in out_edges:\n            out_edges[key].sort()\n        nodes = sorted(set(list(out_edges.keys())\n                           + [d for v in out_edges.values() for d in v]))\n        cycle = find_cycle(nodes, out_edges)\n        if cycle is None:\n            break\n        members = []\n        for i in range(len(cycle) - 1):\n            members.append(index[(cycle[i], cycle[i + 1])])\n        ranked = []\n        for e in members:\n            ranked.append((\n                e[\"strength_bp\"],\n                -_tier_of(e[\"dependent\"], tier_index, fallback_tier),\n                -e[\"declared_seq\"],\n                _neg_key(e[\"prereq\"] + PIPE + e[\"dependent\"]),\n                e))\n        ranked.sort(key=lambda item: item[:4])\n        removed = ranked[0][4]\n        settled = 4\n        for pos in range(4):\n            values = {item[pos] for item in ranked}\n            if len(values) > 1:\n                settled = pos + 1\n                break\n        ledger.append({\"round\": len(ledger) + 1,\n                       \"cycle\": cycle[:-1],\n                       \"removed_prereq\": removed[\"prereq\"],\n                       \"removed_dependent\": removed[\"dependent\"],\n                       \"strength_bp\": removed[\"strength_bp\"],\n                       \"dependent_tier\": _tier_of(removed[\"dependent\"],\n                                                  tier_index, fallback_tier),\n                       \"declared_seq\": removed[\"declared_seq\"],\n                       \"key_settled_at\": settled})\n        edges = [e for e in edges\n                 if not (e[\"prereq\"] == removed[\"prereq\"]\n                         and e[\"dependent\"] == removed[\"dependent\"])]\n    return {\"edges\": edges, \"ledger\": ledger}\n\n\ndef _neg_key(text):\n    \"\"\"Sort helper that orders text descending inside an ascending sort.\"\"\"\n    return tuple(-ord(ch) for ch in text)\n\n\n# --------------------------------------------------------------------------\n# r08 canonical order\n# --------------------------------------------------------------------------\ndef hard_prereqs(edges):\n    \"\"\"Only a hard edge imposes the instance level prerequisite. A soft or\n    advisory edge orders the graph and withholds nothing.\"\"\"\n    out = {}\n    for e in edges:\n        if e[\"kind\"] != \"hard\":\n            continue\n        out.setdefault(e[\"dependent\"], set()).add(e[\"prereq\"])\n    return out\n\n\ndef stage_r08(data, r01, r03, r05, r07):\n    edges = r07[\"edges\"]\n    nodes = sorted(r01[\"actions\"])\n    incoming = {n: 0 for n in nodes}\n    out_edges = {}\n    for e in edges:\n        out_edges.setdefault(e[\"prereq\"], []).append(e[\"dependent\"])\n        incoming[e[\"dependent\"]] = incoming.get(e[\"dependent\"], 0) + 1\n    ready = sorted([n for n in nodes if incoming.get(n, 0) == 0])\n    order = []\n    while ready:\n        node = ready.pop(0)\n        order.append(node)\n        for nxt in sorted(out_edges.get(node, [])):\n            incoming[nxt] -= 1\n            if incoming[nxt] == 0:\n                ready.append(nxt)\n                ready.sort()\n    rank = {aid: i for i, aid in enumerate(order)}\n    by_id = {i[\"instance_id\"]: i for i in r03[\"instances\"]}\n    eligible = set(r05[\"eligible\"])\n    prereqs = hard_prereqs(edges)\n    withheld = []\n    changed = True\n    while changed:\n        changed = False\n        for iid in sorted(eligible):\n            inst = by_id[iid]\n            need = prereqs.get(inst[\"action_id\"], set())\n            for pre in sorted(need):\n                ok = False\n                for other in eligible:\n                    cand = by_id[other]\n                    if (cand[\"action_id\"] == pre\n                            and cand[\"trigger_ms\"] <= inst[\"trigger_ms\"]):\n                        ok = True\n                        break\n                if not ok:\n                    eligible.discard(iid)\n                    withheld.append({\"instance_id\": iid,\n                                     \"reason\": \"PREREQ_MISSING\"})\n                    changed = True\n                    break\n            if changed:\n                break\n    ordered = sorted(eligible, key=lambda iid: (by_id[iid][\"trigger_ms\"],\n                                                rank.get(by_id[iid][\"action_id\"],\n                                                         len(order)), iid))\n    return {\"action_order\": order, \"rank\": rank, \"instance_order\": ordered,\n            \"withheld\": withheld, \"by_id\": by_id}\n\n\n# --------------------------------------------------------------------------\n# r09 demand\n# --------------------------------------------------------------------------\ndef demand_of(data, r01, r02, r04, instance_id, action_id, window_id,\n              resolved):\n    action = r01[\"actions\"][action_id]\n    surcharge = data[\"workbook\"][\"surcharge\"].get(action[\"action_class\"], 0)\n    intensity = resolved[\"intensity_bp\"] + surcharge\n    if intensity < 0:\n        intensity = 0\n    window = r02[\"windows\"][window_id]\n    scale = data[\"workbook\"][\"capacity_scale\"].get(window[\"capacity_class\"],\n                                                   10000)\n    first = half_even(Fraction(action[\"energy_mwh\"] * intensity, 10000))\n    second = half_even(Fraction(first * scale, 10000))\n    return {\"instance_id\": instance_id, \"action_id\": action_id,\n            \"window_id\": window_id, \"device_id\": resolved[\"device_id\"],\n            \"base_energy_mwh\": action[\"energy_mwh\"],\n            \"intensity_bp\": resolved[\"intensity_bp\"],\n            \"surcharge_bp\": surcharge, \"window_scale_bp\": scale,\n            \"demand_mwh\": second}\n\n\ndef stage_r09(data, r01, r02, r04, r08):\n    ceiling = int(data[\"controls\"][\"implausible_demand_mwh\"])\n    rows = []\n    quarantined = []\n    kept = []\n    for iid in r08[\"instance_order\"]:\n        inst = r08[\"by_id\"][iid]\n        rec = r04[\"resolved\"][iid]\n        row = demand_of(data, r01, r02, r04, iid, inst[\"action_id\"],\n                        inst[\"window_id\"], rec)\n        if row[\"demand_mwh\"] > ceiling:\n            quarantined.append({\"instance_id\": iid,\n                                \"reason\": \"IMPLAUSIBLE_DEMAND\"})\n            continue\n        rows.append(row)\n        kept.append(iid)\n    return {\"rows\": rows, \"quarantined\": quarantined, \"order\": kept,\n            \"by_instance\": {r[\"instance_id\"]: r for r in rows}}\n",
    "src/daybreak/util.py": "\"\"\"Reading and arithmetic helpers for the daybreak router.\n\nNothing here knows anything about this cycle. Every value the router uses is\nread from the paper directory it is pointed at.\n\"\"\"\nimport hashlib\nimport json\nimport sqlite3\nimport zipfile\nimport xml.etree.ElementTree as ET\nfrom fractions import Fraction\nfrom pathlib import Path\n\nNL = chr(10)\nBS = chr(92)\nQ = chr(34)\nTAB = chr(9)\nPIPE = chr(124)\n\n\ndef half_even(value):\n    \"\"\"Nearest integer, halves to even. The only rounding this package does.\"\"\"\n    frac = Fraction(value)\n    floor = frac.numerator // frac.denominator\n    rest = frac - floor\n    if rest < Fraction(1, 2):\n        return floor\n    if rest > Fraction(1, 2):\n        return floor + 1\n    return floor if floor % 2 == 0 else floor + 1\n\n\ndef as_fraction(text):\n    \"\"\"Exact rational value of a recorded decimal. No binary floating point.\"\"\"\n    text = str(text).strip()\n    if text == \"\":\n        raise ValueError(\"empty quantity\")\n    sign = 1\n    if text[0] in \"+-\":\n        if text[0] == \"-\":\n            sign = -1\n        text = text[1:]\n    if \".\" in text:\n        whole, part = text.split(\".\", 1)\n    else:\n        whole, part = text, \"\"\n    whole = whole or \"0\"\n    part = part or \"\"\n    num = int(whole + part) if part else int(whole)\n    den = 10 ** len(part)\n    return Fraction(sign * num, den)\n\n\ndef ratio12(value):\n    \"\"\"Twelve decimal places, half to even, never negative zero.\"\"\"\n    frac = Fraction(value)\n    scaled = half_even(frac * 10 ** 12)\n    sign = \"-\" if scaled < 0 else \"\"\n    scaled = abs(scaled)\n    whole, part = divmod(scaled, 10 ** 12)\n    text = sign + str(whole) + \".\" + str(part).rjust(12, \"0\")\n    if text == \"-0.\" + \"0\" * 12:\n        text = \"0.\" + \"0\" * 12\n    return text\n\n\ndef canonical_json(obj):\n    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True)\n\n\ndef compact_json(obj):\n    return json.dumps(obj, sort_keys=True, separators=(\",\", \":\"), ensure_ascii=True)\n\n\ndef sha256_hex(blob):\n    return hashlib.sha256(blob).hexdigest()\n\n\ndef read_text(path):\n    return Path(path).read_bytes().decode(\"utf-8-sig\")\n\n\ndef _split_fields(line, sep):\n    \"\"\"Fields of one record.\"\"\"\n    fields = []\n    cur = []\n    quoted = False\n    i = 0\n    while i < len(line):\n        ch = line[i]\n        if quoted:\n            if ch == '\"' and line[i + 1:i + 2] == '\"':\n                cur.append('\"')\n                i += 1\n            elif ch == '\"':\n                quoted = False\n            else:\n                cur.append(ch)\n        elif ch == '\"' and not cur:\n            quoted = True\n        elif ch == sep:\n            fields.append(\"\".join(cur))\n            cur = []\n        else:\n            cur.append(ch)\n        i += 1\n    fields.append(\"\".join(cur))\n    return fields\n\n\ndef read_delim(path, sep=\",\"):\n    lines = [ln for ln in read_text(path).splitlines() if ln.strip() != \"\"]\n    header = _split_fields(lines[0], sep)\n    return [dict(zip(header, _split_fields(ln, sep))) for ln in lines[1:]]\n\n\ndef read_json(path):\n    return json.loads(read_text(path))\n\n\ndef read_jsonl(path):\n    return [json.loads(ln) for ln in read_text(path).splitlines() if ln.strip()]\n\n\ndef read_flat_yaml(path):\n    out = {}\n    for raw in read_text(path).splitlines():\n        line = raw.split(\"#\", 1)[0].rstrip()\n        if not line.strip() or \":\" not in line:\n            continue\n        key, val = line.split(\":\", 1)\n        key = key.strip()\n        val = val.strip()\n        if val.startswith(\"[\") and val.endswith(\"]\"):\n            inner = val[1:-1].strip()\n            out[key] = [p.strip() for p in inner.split(\",\") if p.strip()] if inner else []\n        elif val:\n            out[key] = val\n    return out\n\n\ndef read_flat_toml(path):\n    out = {}\n    for raw in read_text(path).splitlines():\n        line = raw.split(\"#\", 1)[0].strip()\n        if not line or line.startswith(\"[\") or \"=\" not in line:\n            continue\n        key, val = line.split(\"=\", 1)\n        key = key.strip()\n        val = val.strip()\n        if val.startswith(\"[\") and val.endswith(\"]\"):\n            inner = val[1:-1].strip()\n            out[key] = [p.strip().strip(Q) for p in inner.split(\",\") if p.strip()]\n        else:\n            out[key] = val.strip(Q)\n    return out\n\n\ndef read_conf(path):\n    \"\"\"key = value, one per line, section headers ignored.\"\"\"\n    return read_flat_toml(path)\n\n\ndef read_xml(path):\n    root = ET.parse(str(path)).getroot()\n    scalars = {}\n    groups = {}\n    for child in root:\n        if len(child) == 0:\n            scalars[child.tag] = (child.text or \"\").strip()\n        else:\n            groups[child.tag] = [dict(g.attrib) for g in child]\n    return scalars, groups\n\n\ndef read_sqlite_table(path, table):\n    con = sqlite3.connect(str(path))\n    try:\n        cur = con.cursor()\n        cur.execute(\"SELECT * FROM \" + table)\n        cols = [c[0] for c in cur.description]\n        return [dict(zip(cols, row)) for row in cur.fetchall()]\n    finally:\n        con.close()\n\n\ndef _col_to_idx(ref):\n    col = 0\n    for ch in ref:\n        if ch.isalpha():\n            col = col * 26 + (ord(ch.upper()) - 64)\n        else:\n            break\n    return col\n\n\ndef read_xlsx_sheets(path):\n    with zipfile.ZipFile(path) as zf:\n        shared = []\n        if \"xl/sharedStrings.xml\" in zf.namelist():\n            sroot = ET.fromstring(zf.read(\"xl/sharedStrings.xml\"))\n            for si in sroot:\n                shared.append(\"\".join(t.text or \"\" for t in si.iter()\n                                      if t.tag.endswith(\"}t\")))\n        wb = ET.fromstring(zf.read(\"xl/workbook.xml\"))\n        names = []\n        for sh in wb.iter():\n            if sh.tag.endswith(\"}sheet\"):\n                names.append(sh.attrib.get(\"name\"))\n        out = {}\n        for idx, name in enumerate(names, start=1):\n            member = \"xl/worksheets/sheet\" + str(idx) + \".xml\"\n            if member not in zf.namelist():\n                continue\n            sroot = ET.fromstring(zf.read(member))\n            rows = []\n            for row in sroot.iter():\n                if not row.tag.endswith(\"}row\"):\n                    continue\n                cells = {}\n                width = 0\n                for c in row:\n                    if not c.tag.endswith(\"}c\"):\n                        continue\n                    ci = _col_to_idx(c.attrib.get(\"r\", \"A1\"))\n                    val = \"\"\n                    for v in c:\n                        if v.tag.endswith(\"}v\"):\n                            val = v.text or \"\"\n                    if c.attrib.get(\"t\") == \"s\" and val != \"\":\n                        val = shared[int(val)]\n                    cells[ci] = val\n                    width = max(width, ci)\n                rows.append([cells.get(i, \"\") for i in range(1, width + 1)])\n            out[name] = rows\n        return out\n\n\nW_NS = \"{http://schemas.openxmlformats.org/wordprocessingml/2006/main}\"\n\n\ndef read_docx_blocks(path):\n    with zipfile.ZipFile(path) as zf:\n        root = ET.fromstring(zf.read(\"word/document.xml\"))\n    out = []\n    body = None\n    for node in root:\n        if node.tag == W_NS + \"body\":\n            body = node\n    if body is None:\n        return out\n    for node in body:\n        if node.tag == W_NS + \"p\":\n            out.append(\"\".join(t.text or \"\" for t in node.iter(W_NS + \"t\")))\n        elif node.tag == W_NS + \"tbl\":\n            for tr in node.findall(W_NS + \"tr\"):\n                out.append([\"\".join(t.text or \"\" for t in tc.iter(W_NS + \"t\"))\n                            for tc in tr.findall(W_NS + \"tc\")])\n    return out\n\n\ndef read_pdf_lines(path):\n    raw = Path(path).read_bytes()\n    out = []\n    depth = 0\n    cur = []\n    esc = False\n    for i in range(len(raw)):\n        ch = raw[i:i + 1]\n        if depth == 0:\n            if ch == b\"(\":\n                depth = 1\n                cur = []\n        else:\n            if esc:\n                cur.append(ch)\n                esc = False\n            elif ch == BS.encode(\"latin-1\"):\n                esc = True\n            elif ch == b\"(\":\n                depth += 1\n                cur.append(ch)\n            elif ch == b\")\":\n                depth -= 1\n                if depth == 0:\n                    out.append(b\"\".join(cur).decode(\"latin-1\"))\n                else:\n                    cur.append(ch)\n            else:\n                cur.append(ch)\n    return out\n",
    "tests/test_arithmetic.py": "\"\"\"Arithmetic and parsing checks that hold for every cycle.\n\nThese cover the helpers, not the chain. They pass on the package exactly as\nit shipped and they pass on a repaired package too, so a green suite says\nnothing about whether the chain is right.\n\"\"\"\nimport unittest\nfrom fractions import Fraction\n\nfrom daybreak.cli import parse_args\nfrom daybreak.util import as_fraction, half_even, ratio12, sha256_hex\n\n\nclass HalfEven(unittest.TestCase):\n    def test_exact_integers_are_unchanged(self):\n        for value in (-4, -1, 0, 1, 7, 1000):\n            self.assertEqual(half_even(value), value)\n\n    def test_halves_go_to_even(self):\n        self.assertEqual(half_even(Fraction(1, 2)), 0)\n        self.assertEqual(half_even(Fraction(3, 2)), 2)\n        self.assertEqual(half_even(Fraction(5, 2)), 2)\n        self.assertEqual(half_even(Fraction(-1, 2)), 0)\n        self.assertEqual(half_even(Fraction(-3, 2)), -2)\n\n    def test_non_halves_go_to_nearest(self):\n        self.assertEqual(half_even(Fraction(7, 3)), 2)\n        self.assertEqual(half_even(Fraction(8, 3)), 3)\n\n\nclass Quantities(unittest.TestCase):\n    def test_decimal_strings_are_exact(self):\n        self.assertEqual(as_fraction(\"7.5\"), Fraction(15, 2))\n        self.assertEqual(as_fraction(\"-0.125\"), Fraction(-1, 8))\n        self.assertEqual(as_fraction(\"12\"), Fraction(12))\n\n    def test_ratio_has_twelve_places(self):\n        text = ratio12(Fraction(1, 3))\n        self.assertEqual(len(text.split(\".\")[1]), 12)\n        self.assertEqual(ratio12(0), \"0.000000000000\")\n        self.assertEqual(ratio12(Fraction(-1, 10 ** 15)), \"0.000000000000\")\n\n\nclass Invocation(unittest.TestCase):\n    def test_options_are_order_free(self):\n        a = parse_args([\"--data\", \"x\", \"--out\", \"y\"])\n        b = parse_args([\"--out\", \"y\", \"--data\", \"x\"])\n        self.assertEqual(str(a[0]), str(b[0]))\n        self.assertEqual(str(a[1]), str(b[1]))\n\n    def test_missing_option_is_refused(self):\n        with self.assertRaises(SystemExit):\n            parse_args([\"--data\", \"x\"])\n\n\nclass Digests(unittest.TestCase):\n    def test_digest_is_lower_case_hex(self):\n        text = sha256_hex(b\"daybreak\")\n        self.assertEqual(len(text), 64)\n        self.assertEqual(text, text.lower())\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n",
    "tests/test_readers.py": "\"\"\"Reader checks over documents this test writes for itself.\"\"\"\nimport tempfile\nimport unittest\nfrom pathlib import Path\n\nfrom daybreak.util import (read_conf, read_delim, read_flat_toml,\n                           read_flat_yaml, read_json, read_jsonl, PIPE, TAB)\n\n\nclass Readers(unittest.TestCase):\n    def setUp(self):\n        self.root = Path(tempfile.mkdtemp(prefix=\"daybreak-readers-\"))\n\n    def test_comma_and_tab_and_pipe(self):\n        (self.root / \"a.csv\").write_text(\"k,v\" + chr(10) + \"x,1\" + chr(10))\n        (self.root / \"b.tsv\").write_text(\"k\" + TAB + \"v\" + chr(10)\n                                         + \"x\" + TAB + \"1\" + chr(10))\n        (self.root / \"c.psv\").write_text(\"k\" + PIPE + \"v\" + chr(10)\n                                         + \"x\" + PIPE + \"1\" + chr(10))\n        self.assertEqual(read_delim(self.root / \"a.csv\", \",\")[0][\"v\"], \"1\")\n        self.assertEqual(read_delim(self.root / \"b.tsv\", TAB)[0][\"v\"], \"1\")\n        self.assertEqual(read_delim(self.root / \"c.psv\", PIPE)[0][\"v\"], \"1\")\n\n    def test_empty_cell_survives_reading(self):\n        (self.root / \"d.csv\").write_text(\"k,v\" + chr(10) + \"x,\" + chr(10))\n        self.assertEqual(read_delim(self.root / \"d.csv\", \",\")[0][\"v\"], \"\")\n\n    def test_flat_mappings(self):\n        (self.root / \"e.yaml\").write_text(\"a: 1\" + chr(10)\n                                          + \"b: [p, q]\" + chr(10))\n        (self.root / \"f.toml\").write_text(\"a = \" + chr(34) + \"1\" + chr(34)\n                                          + chr(10))\n        self.assertEqual(read_flat_yaml(self.root / \"e.yaml\")[\"b\"], [\"p\", \"q\"])\n        self.assertEqual(read_flat_toml(self.root / \"f.toml\")[\"a\"], \"1\")\n\n    def test_json_and_jsonl(self):\n        (self.root / \"g.json\").write_text(\"{\" + chr(34) + \"a\" + chr(34)\n                                          + \": 2}\")\n        (self.root / \"h.jsonl\").write_text(\"{\" + chr(34) + \"a\" + chr(34)\n                                           + \": 3}\" + chr(10))\n        self.assertEqual(read_json(self.root / \"g.json\")[\"a\"], 2)\n        self.assertEqual(read_jsonl(self.root / \"h.jsonl\")[0][\"a\"], 3)\n\n    def test_conf_reads_key_equals_value(self):\n        (self.root / \"i.conf\").write_text(\"[s]\" + chr(10) + \"k = v\" + chr(10))\n        self.assertEqual(read_conf(self.root / \"i.conf\")[\"k\"], \"v\")\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n",
}

DEFECTS = (
    ('DFC-01', 'src/daybreak/loading.py',
     '        if limit is None or rev > limit:\n            continue\n',
     '        if limit is None:\n            continue\n'),
    ('DFC-02', 'src/daybreak/stages.py',
     '    return text is None or str(text).strip() in ("", ABSENT)\n',
     '    return text is None or str(text).strip() in ("", ABSENT, "0")\n'),
    ('DFC-03', 'src/daybreak/stages.py',
     '        start = cursor + delta\n        cursor = start\n',
     '        start = delta\n        cursor = start\n'),
    ('DFC-04', 'src/daybreak/stages.py',
     '                    if win["start_ms"] <= trigger < win["end_ms"]:\n',
     '                    if win["start_ms"] <= trigger <= win["end_ms"]:\n'),
    ('DFC-05', 'src/daybreak/stages.py',
     '        if entry["remaining"] > 0 and trigger < entry["expires_ms"]:\n',
     '        if entry["remaining"] > 0 and trigger <= entry["expires_ms"]:\n'),
    ('DFC-06', 'src/daybreak/stages.py',
     '    remaining = dict(data["snapshot"].get("oneshot_remaining", {}))\n    for rec in data["overrides"]:\n        oid = rec["override_id"]\n        aid = rec["action_id"]\n        expires, _b = convert(units, rec["expires"]["value"],\n                              rec["expires"]["unit"])\n        entry = {"override_id": oid, "action_id": aid,\n                 "expires_ms": expires if expires is not None else 0,\n                 "remaining": int(remaining.get(oid, rec.get("remaining", 0)))}\n',
     '    for rec in data["overrides"]:\n        oid = rec["override_id"]\n        aid = rec["action_id"]\n        expires, _b = convert(units, rec["expires"]["value"],\n                              rec["expires"]["unit"])\n        entry = {"override_id": oid, "action_id": aid,\n                 "expires_ms": expires if expires is not None else 0,\n                 "remaining": int(rec.get("remaining", 0))}\n'),
    ('DFC-07', 'src/daybreak/stages.py',
     '    first = half_even(Fraction(action["energy_mwh"] * intensity, 10000))\n    second = half_even(Fraction(first * scale, 10000))\n',
     '    first = Fraction(action["energy_mwh"] * intensity, 10000)\n    second = half_even(first * Fraction(scale, 10000))\n'),
    ('DFC-08', 'src/daybreak/allocate.py',
     '        if rec["demand"]["demand_mwh"] <= pool:\n',
     '        if rec["demand"]["demand_mwh"] < pool:\n'),
    ('DFC-09', 'src/daybreak/allocate.py',
     '        else:\n            rejected.append(rec)\n    return taken, rejected, pool\n',
     '        else:\n            rejected.append(rec)\n            break\n    return taken, rejected, pool\n'),
    ('DFC-10', 'src/daybreak/allocate.py',
     '        candidates = incumbents + by_group[key]\n',
     '        candidates = list(by_group[key])\n'),
    ('DFC-11', 'src/daybreak/publish.py',
     '    for oid, used in r13b["consumed"].items():\n',
     '    for oid, used in r13["consumed"].items():\n'),
    ('DFC-12', 'src/daybreak/stages.py',
     '            ranked.append((\n                e["strength_bp"],\n                -_tier_of(e["dependent"], tier_index, fallback_tier),\n',
     '            ranked.append((\n                -_tier_of(e["dependent"], tier_index, fallback_tier),\n                e["strength_bp"],\n'),
    ('DFC-13', 'src/daybreak/loading.py',
     '        if len(head) >= 2 and head[0] == "grid_key" and head[1] == cycle_key:\n            live = rows\n',
     '        if len(head) >= 2 and head[0] == "grid_key" and live is None:\n            live = rows\n'),
    ('DFC-14', 'src/daybreak/stages.py',
     '    cap = data["memo_caps"].get(rid)\n    if cap is not None:\n        return cap, "memo"\n    rec = routine_layer.get(rid, {})\n    if "max_occurrences" in rec:\n        return rec["max_occurrences"], "routine"\n',
     '    rec = routine_layer.get(rid, {})\n    if "max_occurrences" in rec:\n        return rec["max_occurrences"], "routine"\n    cap = data["memo_caps"].get(rid)\n    if cap is not None:\n        return cap, "memo"\n'),
    ('DFC-15', 'src/daybreak/stages.py',
     '    out = {}\n    cursor = int(data["header"]["origin_ms"])\n    for row in data["context_spans"]:\n',
     '    out = {}\n    cursor = 0\n    for row in data["context_spans"]:\n'),
    ('DFC-16', 'src/daybreak/stages.py',
     '    frozen = int(data["snapshot"]["frozen_revision_cooldown_register"])\n',
     '    frozen = int(data["header"]["frozen_revision_window_grid"])\n'),
    ('DFC-17', 'src/daybreak/stages.py',
     '    frozen = data["header"]["window_frozen_revisions"]\n    rows = sorted(data["window_rows"], key=lambda r: int(r["ordinal"]))\n    live = live_rows(rows, "window_id", lambda k: frozen.get(k))\n',
     '    frozen = data["header"]["frozen_revision_window_grid"]\n    rows = sorted(data["window_rows"], key=lambda r: int(r["ordinal"]))\n    live = live_rows(rows, "window_id", lambda k: frozen)\n'),
    ('DFC-18', 'src/daybreak/publish.py',
     '    for iid in r05["eligible"]:\n        aid = by_id[iid]["action_id"]\n',
     '    for iid in by_id:\n        aid = by_id[iid]["action_id"]\n'),
    ('DFC-19', 'src/daybreak/publish.py',
     '        if cur is None or idx > cur[0]:\n',
     '        if cur is None or idx != cur[0]:\n'),
    ('DFC-20', 'src/daybreak/allocate.py',
     '        if iid in r12["proposal_index"]:\n            continue\n        demand = r09["by_instance"][iid]\n',
     '        demand = (r09["by_instance"].get(iid)\n                  or r12["proposal_index"][iid]["demand"])\n'),
    ('DFC-21', 'src/daybreak/util.py',
     '    return Path(path).read_bytes().decode("utf-8-sig")\n',
     '    return Path(path).read_bytes().decode("utf-8")\n'),
    ('DFC-22', 'src/daybreak/util.py',
     'def _split_fields(line, sep):\n    """Fields of one record."""\n    fields = []\n    cur = []\n    quoted = False\n    i = 0\n    while i < len(line):\n        ch = line[i]\n        if quoted:\n            if ch == \'"\' and line[i + 1:i + 2] == \'"\':\n                cur.append(\'"\')\n                i += 1\n            elif ch == \'"\':\n                quoted = False\n            else:\n                cur.append(ch)\n        elif ch == \'"\' and not cur:\n            quoted = True\n        elif ch == sep:\n            fields.append("".join(cur))\n            cur = []\n        else:\n            cur.append(ch)\n        i += 1\n    fields.append("".join(cur))\n    return fields\n\n\ndef read_delim(path, sep=","):\n    lines = [ln for ln in read_text(path).splitlines() if ln.strip() != ""]\n    header = _split_fields(lines[0], sep)\n    return [dict(zip(header, _split_fields(ln, sep))) for ln in lines[1:]]\n\n\n',
     'def read_delim(path, sep=","):\n    lines = [ln for ln in read_text(path).split("\\n") if ln.strip() != ""]\n    header = [name.strip() for name in lines[0].split(sep)]\n    return [dict(zip(header, ln.split(sep))) for ln in lines[1:]]\n\n\n'),
    ('DFC-23', 'src/daybreak/stages.py',
     '    applicable.append(("global", layers["global"]))\n    applicable.sort(key=lambda item: layers["ranks"][item[0]])\n',
     '    applicable.append(("global", layers["global"]))\n'),
    ('DFC-24', 'src/daybreak/allocate.py',
     '    cap = int(data["directive"]["round_cap"])\n',
     '    cap = 2\n'),
)


# --------------------------------------------------------------------------
# the package as the household currently runs it
#
# REFERENCE_PACKAGE is the source that satisfies every stage specification.
# DEFECTS names, for each catalogued defect, the anchor the specification puts
# in force and the anchor the shipped package carries instead. The shipped
# archive is the reference with every defect applied.
# --------------------------------------------------------------------------
def shipped_package_files():
    out = {}
    for name, text in REFERENCE_PACKAGE.items():
        for _code, path, correct, broken in DEFECTS:
            if path != name:
                continue
            if text.count(correct) != 1:
                raise AssertionError("defect anchor is not unique: " + _code)
            text = text.replace(correct, broken)
        out[name] = text
    return out


def emit_package(inst, dest):
    parts = []
    for name in sorted(shipped_package_files()):
        parts.append((name, shipped_package_files()[name].encode("utf-8")))
    _zip_parts(dest / "project.zip", parts)


def generate(seed, dest):
    """Mint one routing cycle and write the whole paper directory."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    inst = mint(seed)
    emit_orientation(inst, dest)
    emit_header(inst, dest)
    emit_registers(inst, dest)
    emit_policies(inst, dest)
    emit_policy_papers(inst, dest)
    emit_workbook(inst, dest)
    emit_memo(inst, dest)
    emit_directive(inst, dest)
    emit_contract(inst, dest)
    emit_package(inst, dest)
    emit_glossary(inst, dest)
    emit_readings(inst, dest)
    emit_traps(inst, dest)
    emit_schema(inst, dest)
    emit_serialisation(inst, dest)
    emit_worked(inst, dest)
    emit_stage_specs(inst, dest)
    emit_lineage(inst, dest)
    return {"files": sorted(p.name for p in dest.iterdir()),
            "cycle": inst["cycle"], "profile": inst["profile"],
            "instance": inst}


# ==========================================================================
# grading surfaces
#
# Two of them. The documents the agent published for the shipped cycle are
# compared against this file's own reference chain over a corpus reminted
# from SAMPLE_SEED. The package the agent delivered is extracted and driven
# over three cycles minted from seeds it has never seen.
# ==========================================================================
OUT = Path(OUTPUT_ROOT)
INTAKE_FILES = ["unit_normalization.json", "alias_resolution.jsonl",
                "expansion_ledger.csv"]
POLICY_FILES = ["config_resolution.json", "parameter_audit.csv",
                "trigger_eligibility_index.json"]
GRAPH_FILES = ["dependency_graph.json", "cycle_break_ledger.json",
               "canonical_action_order.json"]
BINDING_FILES = ["resource_demand.csv", "window_capacity_report.csv",
                 "initial_allocation.json", "displaced_action_queue.json"]
RECONCILE_FILES = ["fallback_expansion.json",
                   "precedence_reconciliation.json",
                   "final_action_order.json"]
STATE_FILES = ["cooldown_state.csv", "derived_state.json",
               "suppression_ledger.csv", "next_state_snapshot.json"]
PUBLISH_FILES = ["per_context_manifest.json", "per_device_manifest.csv",
                 "daily_automation_manifest.json",
                 "resource_utilization_report.csv",
                 "terminal_action_report.md", "audit_ledger.jsonl",
                 "run_manifest.txt", "summary.json"]
DOCUMENT_FILES = (INTAKE_FILES + POLICY_FILES + GRAPH_FILES + BINDING_FILES
                  + RECONCILE_FILES + STATE_FILES + PUBLISH_FILES)
REPAIR_FILES = ["package.zip", "build_report.json", "selftest.json",
                "defect_register.md", "verification_notes.md"]
CORE_FILES = ["unit_normalization.json", "canonical_action_order.json",
              "final_action_order.json", "daily_automation_manifest.json",
              "next_state_snapshot.json"]

_CACHE = {}


def _reference_src():
    """The reference package, written once into a private directory."""
    if "refsrc" in _CACHE:
        return _CACHE["refsrc"]
    root = Path(tempfile.mkdtemp(prefix="dbk-ref-"))
    for name, text in REFERENCE_PACKAGE.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _CACHE["refsrc"] = root
    return root


def _reference_blobs(corpus):
    """Run the reference chain over a corpus and return the document bytes."""
    src = _reference_src() / "src"
    script = (
        "import json, sys" + NL
        + "sys.path.insert(0, " + repr(str(src)) + ")" + NL
        + "from daybreak.publish import run_chain" + NL
        + "blobs = run_chain(" + repr(str(corpus)) + ")" + NL
        + "import base64" + NL
        + "print(json.dumps({k: base64.b64encode(v).decode() "
          "for k, v in blobs.items()}))" + NL)
    proc = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise AssertionError("reference chain failed: "
                             + proc.stderr.strip()[-400:])
    import base64
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return {k: base64.b64decode(v) for k, v in payload.items()}


def _corpus_for(seed, tag):
    key = "corpus-" + tag
    if key in _CACHE:
        return _CACHE[key]
    root = Path(tempfile.mkdtemp(prefix="dbk-corpus-" + tag + "-")) / "data"
    generate(seed, root)
    _open_tree(root.parent)
    # Taken here, before any chain has run over it. The corpus is read only to
    # the sandbox user, so this digest stays true for the whole run.
    _CACHE["clean-" + tag] = _tree_digest(root)
    _CACHE[key] = root
    return root


def _verify_clean(tag, corpus):
    """No graded truth is ever derived from a corpus that has moved.

    The delivery only ever runs over private copies, so this holds by
    construction; it stays as a guard on the verifier's own invariant."""
    if _tree_digest(corpus) != _CACHE["clean-" + tag]:
        raise AssertionError("the " + tag + " corpus was modified before its "
                             "reference chain ran, so no graded truth can be "
                             "taken from it")


def _expected(tag="shipped", seed=None):
    key = "expected-" + tag
    if key in _CACHE:
        return _CACHE[key]
    corpus = _corpus_for(SAMPLE_SEED if seed is None else seed, tag)
    _verify_clean(tag, corpus)
    _CACHE[key] = _reference_blobs(corpus)
    return _CACHE[key]


def _got(name):
    path = OUT / name
    if not path.is_file():
        raise AssertionError("missing deliverable: " + name)
    return path.read_bytes()


def _compare(names, expected, produced, where):
    bad = []
    for name in names:
        if name not in produced:
            bad.append(name + ": absent")
            continue
        if produced[name] != expected[name]:
            bad.append(name + ": " + _first_difference(expected[name],
                                                       produced[name]))
    if bad:
        raise AssertionError(where + " -> " + "; ".join(bad[:4]))


def _first_difference(want, got):
    wl = want.decode("utf-8", "replace").splitlines()
    gl = got.decode("utf-8", "replace").splitlines()
    for i in range(max(len(wl), len(gl))):
        a = wl[i] if i < len(wl) else "<end>"
        b = gl[i] if i < len(gl) else "<end>"
        if a != b:
            return ("line " + str(i + 1) + " want " + a[:90]
                    + " got " + b[:90])
    return "identical text, differing bytes"


# --------------------------------------------------------------------------
# the delivered package
#
# Everything the agent delivered is hostile input. Grading runs as root, so the
# package is driven under an unprivileged user: that is what makes the
# `chmod -R go-rwx /tests` in tests/Dockerfile bite, keeping the delivery out of
# the reference chain it is graded against, and what keeps it out of the
# root owned /logs/verifier where the reward is written.
# --------------------------------------------------------------------------
SANDBOX_USER = "nobody"
SANDBOX_GROUP = "nogroup"


def _sandbox_available():
    if "sandbox" in _CACHE:
        return _CACHE["sandbox"]
    _CACHE["sandbox"] = bool(getattr(os, "geteuid", None)
                             and os.geteuid() == 0
                             and shutil.which("setpriv"))
    return _CACHE["sandbox"]


def _sandboxed(cmd):
    """Wrap a command so it runs without privileges."""
    if not _sandbox_available():
        return list(cmd)
    return ["setpriv", "--reuid=" + SANDBOX_USER,
            "--regid=" + SANDBOX_GROUP, "--clear-groups"] + list(cmd)


def _open_tree(root, writable=False):
    """Let the unprivileged user reach a tree the verifier made as root.

    mkdtemp hands back a 0700 directory, which that user cannot even traverse.
    A tree is opened writable only when it is a private copy handed to one
    run of the delivered package. The corpora a graded reference is taken
    from stay read only to that user, so nothing it runs can move them."""
    if not _sandbox_available():
        return
    dir_mode = 0o777 if writable else 0o755
    file_mode = 0o666 if writable else 0o644
    root = Path(root)
    os.chmod(root, dir_mode)
    for path in root.rglob("*"):
        os.chmod(path, dir_mode if path.is_dir() else file_mode)


def _sandbox_env(src_root):
    """Only what the delivered package needs to run. The verifier's own
    environment carries the judge credential, so none of it is inherited:
    agent code never sees a variable this allowlist does not name."""
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": str(src_root),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": tempfile.gettempdir(),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def _run_agent_code(cmd, cwd, env, timeout, stdin_text=None):
    """Run agent code in its own session and reap the whole group afterwards,
    so nothing it forked is still alive when the reward is written."""
    proc = subprocess.Popen(_sandboxed(cmd), cwd=cwd, env=env,
                            stdin=subprocess.DEVNULL if stdin_text is None
                            else subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        out, err = proc.communicate(input=stdin_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        out, err = "", "timed out after " + str(timeout) + "s"
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        proc.poll()
    return proc.returncode, out, err


def reap_sandbox_processes():
    """Kill everything still running as the sandbox user.

    A delivered package can fork a child into its own session, which escapes
    the process group kill in _run_agent_code, and it could then rewrite the
    reward after grading has finished. The reward is written only after this
    sweep, so nothing the delivery spawned is alive to touch it. This does not
    rely on the permissions of the verifier log directory, which is a bind
    mount whose modes some hosts do not enforce."""
    if not _sandbox_available():
        return 0
    try:
        import pwd
        uid = pwd.getpwnam(SANDBOX_USER).pw_uid
    except Exception:
        return 0
    killed = 0
    try:
        entries = os.listdir("/proc")
    except OSError:
        return 0
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open("/proc/" + entry + "/status") as fh:
                for line in fh:
                    if not line.startswith("Uid:"):
                        continue
                    if int(line.split()[1]) == uid:
                        os.kill(int(entry), signal.SIGKILL)
                        killed += 1
                    break
        except (OSError, ValueError, IndexError):
            continue
    return killed


def _tree_digest(root):
    """Content digest of a directory, so a same length rewrite still shows."""
    root = Path(root)
    parts = []
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_file():
            parts.append(rel + ":" + sha256_hex(path.read_bytes()))
        else:
            parts.append(rel + ":dir")
    return sha256_hex(NL.join(parts).encode("utf-8"))


def _package_root():
    if "pkgroot" in _CACHE:
        return _CACHE["pkgroot"]
    blob = _got("package.zip")
    root = Path(tempfile.mkdtemp(prefix="dbk-pkg-"))
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for info in zf.infolist():
            name = info.filename
            if name.startswith("/") or ".." in name.split("/"):
                raise AssertionError("unsafe archive member: " + name)
        zf.extractall(root)
    _open_tree(root)
    _CACHE["pkgroot"] = root
    return root


def _package_sources():
    if "pkgsrc" in _CACHE:
        return _CACHE["pkgsrc"]
    root = _package_root()
    out = {}
    for path in sorted(root.rglob("*.py")):
        out[str(path.relative_to(root))] = path.read_text(encoding="utf-8",
                                                          errors="replace")
    _CACHE["pkgsrc"] = out
    return out


def _private_copy(corpus, tag):
    """A writable copy of a corpus for one run of the delivered package. The
    copy keeps the corpus's own directory name, so a package that keys on the
    name sees exactly the name it would have seen."""
    work = Path(tempfile.mkdtemp(prefix="dbk-work-" + tag + "-")) / Path(corpus).name
    shutil.copytree(corpus, work)
    _open_tree(work.parent, writable=True)
    return work


def _run_package(corpus, tag):
    key = "run-" + tag
    if key in _CACHE:
        return _CACHE[key]
    root = _package_root()
    src = root / "src"
    if not (src / PACKAGE_NAME / "__init__.py").is_file():
        raise AssertionError("delivered archive has no src/" + PACKAGE_NAME
                             + " package")
    work = _private_copy(corpus, tag)
    before = _tree_digest(work)
    dest = Path(tempfile.mkdtemp(prefix="dbk-run-" + tag + "-")) / "out"
    _open_tree(dest.parent, writable=True)
    code, _out, err = _run_agent_code(
        [sys.executable, "-m", PACKAGE_NAME,
         "--data", str(work), "--out", str(dest)],
        cwd=str(root), env=_sandbox_env(src), timeout=300)
    _CACHE["dirtied-" + tag] = _tree_digest(work) != before
    if code != 0:
        _CACHE[key] = ("FAILED", err.strip()[-400:])
        return _CACHE[key]
    produced = {}
    if dest.is_dir():
        for path in sorted(dest.iterdir()):
            if path.is_file():
                produced[path.name] = path.read_bytes()
    _CACHE[key] = ("OK", produced)
    return _CACHE[key]


def _case_got(tag, seed):
    corpus = _corpus_for(seed, tag)
    status, payload = _run_package(corpus, tag)
    if status != "OK":
        raise AssertionError("delivered package failed on the " + tag
                             + " cycle: " + str(payload))
    return payload


def _case_expected(tag, seed):
    return _expected(tag, seed)


# --------------------------------------------------------------------------
# positive assertions
# --------------------------------------------------------------------------
def _check_all_artifacts_exist():
    """POSITIVE: every declared deliverable is present under /app/out."""
    missing = [name for name in DOCUMENT_FILES + REPAIR_FILES
               if not (OUT / name).is_file()]
    assert not missing, "missing deliverables: " + ", ".join(missing)


def _check_documents_parse_and_conform():
    """POSITIVE: every published document parses in its own form and carries
    the header or key set the schema reference states."""
    for name in DOCUMENT_FILES:
        blob = _got(name)
        if name.endswith(".json"):
            json.loads(blob.decode("utf-8"))
        elif name.endswith(".jsonl"):
            for line in blob.decode("utf-8").splitlines():
                if line.strip():
                    json.loads(line)
        elif name.endswith(".csv"):
            lines = blob.decode("utf-8").splitlines()
            assert lines, name + " has no header line"
            width = len(lines[0].split(","))
            for line in lines[1:]:
                assert len(line.split(",")) == width, name + " ragged row"
    summary = json.loads(_got("summary.json").decode("utf-8"))
    for key in ["cycle_key", "profile", "core_digest", "publication_digest",
                "control_totals"]:
        assert key in summary, "summary.json lacks " + key
    manifest = _got("run_manifest.txt").decode("utf-8").splitlines()
    assert manifest[-1].startswith("publication "), "manifest has no publication digest"
    assert manifest[-2].startswith("core "), "manifest has no core digest"


def _check_repair_records_conform():
    """POSITIVE: the four repair records carry the account of the repair the
    instruction asks for."""
    report = json.loads(_got("build_report.json").decode("utf-8"))
    assert isinstance(report, dict) and report, "build_report.json is empty"
    selftest = json.loads(_got("selftest.json").decode("utf-8"))
    assert isinstance(selftest, dict) and selftest, "selftest.json is empty"
    register = _got("defect_register.md").decode("utf-8").splitlines()
    rows = [line for line in register
            if line.startswith("|") and set(line) - set("| -")]
    assert len(rows) >= 2, ("defect_register.md carries no table row per "
                            "repaired defect")
    table = [[cell.strip() for cell in line.strip().strip("|").split("|")]
             for line in register if line.strip().startswith("|")]
    assert table and table[0] == ["defect", "stage", "function",
                                  "rule restored"], (
        "defect_register.md does not open on the header the schema reference "
        "states")
    assert len(table) >= 2 and len(table[1]) == 4 and all(
        cell and set(cell) <= set("-:") and cell.count("-") >= 3
        for cell in table[1]), (
        "defect_register.md has no separator row under its header")
    notes = [line for line in _got("verification_notes.md")
             .decode("utf-8").splitlines() if line.strip()]
    assert len(notes) >= 3, "verification_notes.md lists no checks"


# The one stage each departure is booked against: the earliest stage, in
# chain order, whose paper the departure breaks. For a helper several
# stages call that is the first of them whose result the departure
# changes; for a reader every paper goes through it is the first stage
# that serves a paper carrying the trap, by the paper to stage map.
DEFECT_STAGES = {
    "DFC-01": {"r02"}, "DFC-02": {"r03"}, "DFC-03": {"r02"},
    "DFC-04": {"r03"}, "DFC-05": {"r04"}, "DFC-06": {"r04"},
    "DFC-07": {"r09"}, "DFC-08": {"r10"}, "DFC-09": {"r10"},
    "DFC-10": {"r12"}, "DFC-11": {"r13"}, "DFC-12": {"r07"},
    "DFC-13": {"r10"}, "DFC-14": {"r03"}, "DFC-15": {"r02"},
    "DFC-16": {"r04"}, "DFC-17": {"r02"}, "DFC-18": {"r07"},
    "DFC-19": {"r14"}, "DFC-20": {"r14"}, "DFC-21": {"r02"},
    "DFC-22": {"r02"}, "DFC-23": {"r04"}, "DFC-24": {"r12"},
}

# DFC-22 breaks two reading rules of serialisation_and_digest_contract.md:
# the quoted field (first met at r02, source_priority_register.csv) and the
# carriage return (first met at r04, cooldown_register.psv). A function that
# departs from two rules takes two rows, so the register books it once under
# r02 and once more under r04.
DEFECT_SECOND_RULE_STAGES = {"DFC-22": {"r04"}}


def _top_level_spans(text):
    """(name, first line, last line) of every top level function."""
    return [(node.name, node.lineno, node.end_lineno)
            for node in ast.parse(text).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _module_of(path):
    return path.rsplit("/", 1)[-1][:-len(".py")]


def _real_departures():
    """For every planted departure, the functions of the shipped project it
    sits in and the stages it may be booked against."""
    if "departures" in _CACHE:
        return _CACHE["departures"]
    found = []
    for code, path, correct, _broken in DEFECTS:
        text = REFERENCE_PACKAGE[path]
        first = text[:text.index(correct)].count("\n") + 1
        last = first + correct.rstrip("\n").count("\n")
        names = {_module_of(path) + "." + name
                 for name, lo, hi in _top_level_spans(text)
                 if lo <= last and hi >= first}
        found.append((code, frozenset(names), frozenset(DEFECT_STAGES[code]),
                      _module_of(path)))
    _CACHE["departures"] = found
    return found


def _shipped_functions():
    names = set()
    for path, text in shipped_package_files().items():
        if path.startswith("src/") and path.endswith(".py"):
            names |= {_module_of(path) + "." + name
                      for name, _lo, _hi in _top_level_spans(text)}
    return names


def _register_rows():
    """(stage, function) of every data row of the delivered register."""
    import re
    lines = [ln.strip() for ln in _got("defect_register.md")
             .decode("utf-8").splitlines() if ln.strip().startswith("|")]
    cells = [[c.strip().strip("`").strip() for c in ln.strip("|").split("|")]
             for ln in lines]
    head = None
    rows = []
    for row in cells:
        lowered = [c.lower() for c in row]
        if head is None:
            if "stage" in lowered and "function" in lowered:
                head = (lowered.index("stage"), lowered.index("function"))
            continue
        if not set("".join(row)) - set(" -:"):
            continue
        stage_cell = row[head[0]] if head[0] < len(row) else ""
        func_cell = row[head[1]] if head[1] < len(row) else ""
        stage = re.search(r"\b[rR](0[1-9]|1[0-4])\b", stage_cell)
        func_cell = func_cell.replace("`", "").replace("()", "")
        func_cell = func_cell.replace(".py", "").replace(":", ".")
        parts = [x for x in func_cell.split(".") if x]
        func = ".".join(parts[-2:]) if len(parts) >= 2 else ""
        rows.append(("r" + stage.group(1) if stage else "", func))
    assert head is not None, "defect_register.md has no stage and function header"
    return rows

def _delivered_helpers(module, callers):
    """Top level functions the delivered module adds beside the shipped ones
    that one of the departure's own functions calls by name."""
    try:
        path = _package_root() / "src" / PACKAGE_NAME / (module + ".py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    defs = {node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    called = set()
    for qual in callers:
        node = defs.get(qual.split(".", 1)[1])
        for sub in (ast.walk(node) if node is not None else ()):
            if isinstance(sub, ast.Name):
                called.add(sub.id)
            elif isinstance(sub, ast.Attribute):
                called.add(sub.attr)
    return {module + "." + name for name in defs if name in called}


def _check_defect_register_matches_departures():
    """POSITIVE: the register books every departure the shipped source carries
    against its function and stage, and books no function that carries none."""
    rows = _register_rows()
    shipped = _shipped_functions()
    used = [False] * len(rows)
    open_codes = list(_real_departures())
    # Rows naming the very function are matched first; a helper the repair
    # introduced then stands for a departure left in the module it joined.
    for exact in (True, False):
        left = []
        for code, funcs, stages, module in open_codes:
            hit = None
            for i, (stage, func) in enumerate(rows):
                if used[i] or stage not in stages:
                    continue
                if exact and func in funcs:
                    hit = i
                elif (not exact and func not in shipped
                      and func in _delivered_helpers(module, funcs)):
                    hit = i
                if hit is not None:
                    break
            if hit is None:
                left.append((code, funcs, stages, module))
            else:
                used[hit] = True
        open_codes = left
    missing = [entry[0] for entry in open_codes]
    # A reader that breaks two separately stated reading rules takes one row
    # per rule: the second names the same function, or the helper the repair
    # introduced for it, under the first stage that reads a paper carrying
    # the second trap.
    for code, funcs, _stages, module in _real_departures():
        extra = DEFECT_SECOND_RULE_STAGES.get(code)
        if not extra or code in missing:
            continue
        for i, (stage, func) in enumerate(rows):
            if used[i] or stage not in extra:
                continue
            if func in funcs or (func not in shipped and func
                                 in _delivered_helpers(module, funcs)):
                used[i] = True
                break
        else:
            missing.append(code + " (second rule)")
    assert not missing, ("the register leaves out " + str(len(missing))
                         + " departure(s)")
    wrong = [func for i, (stage, func) in enumerate(rows)
             if not used[i] and func in shipped]
    assert not wrong, ("the register books functions that carry no departure: "
                       + ", ".join(sorted(set(wrong))))


def _reference_figures():
    """The figures the notes must state for the shipped cycle."""
    expected = _expected()
    figures = {}
    report = expected["suppression_ledger.csv"].decode("utf-8").splitlines()
    for line in report[1:]:
        reason = line.split(",")[1]
        figures["set_aside " + reason] = figures.get("set_aside " + reason, 0) + 1
    inst = mint(SAMPLE_SEED)
    figures["last_window_start_ms"] = inst["windows"][-1]["start_ms"]
    return figures


def _check_verification_notes_state_figures():
    """POSITIVE: the notes state the start of the last window and the count
    per reason of the shipped cycle, and every figure line they carry is the
    figure the cycle yields."""
    expected = _reference_figures()
    stated = {}
    for line in _got("verification_notes.md").decode("utf-8").splitlines():
        words = line.strip().strip("-*` ").split()
        if len(words) == 2 and words[0] == "last_window_start_ms":
            stated.setdefault(words[0], set()).add(words[1])
        elif len(words) == 3 and words[0] == "set_aside":
            stated.setdefault(words[0] + " " + words[1], set()).add(words[2])
    for key, value in expected.items():
        assert stated.get(key) == {str(value)}, "notes misstate " + key
    extra = [key for key in stated if key not in expected]
    assert not extra, "notes state reasons the cycle does not carry"


def _check_delivered_package_shape():
    """POSITIVE: the archive is laid out as the package expectations state and
    carries the shipped test modules unchanged."""
    root = _package_root()
    assert (root / "pyproject.toml").is_file(), "archive root has no pyproject.toml"
    src = root / "src" / PACKAGE_NAME
    assert src.is_dir(), "archive has no src/" + PACKAGE_NAME + " tree"
    for module in ["__init__.py", "__main__.py", "cli.py", "util.py",
                   "loading.py", "stages.py", "allocate.py", "publish.py"]:
        assert (src / module).is_file(), "archive lacks module " + module
    shipped_tests = {name: text for name, text in REFERENCE_PACKAGE.items()
                     if name.startswith("tests/")}
    for name, text in shipped_tests.items():
        path = root / name
        assert path.is_file(), "archive lacks " + name
        assert path.read_text(encoding="utf-8") == text, name + " was altered"


def _check_shipped_intake_documents_exact():
    """POSITIVE: the intake documents of the shipped cycle are byte exact."""
    expected = _expected()
    _compare(INTAKE_FILES, expected, {n: _got(n) for n in INTAKE_FILES},
             "shipped intake")


def _check_shipped_policy_documents_exact():
    """POSITIVE: the policy resolution documents of the shipped cycle are
    byte exact."""
    expected = _expected()
    _compare(POLICY_FILES, expected, {n: _got(n) for n in POLICY_FILES},
             "shipped policy")


def _check_shipped_graph_documents_exact():
    """POSITIVE: the dependency documents of the shipped cycle are byte
    exact."""
    expected = _expected()
    _compare(GRAPH_FILES, expected, {n: _got(n) for n in GRAPH_FILES},
             "shipped graph")


def _check_shipped_binding_documents_exact():
    """POSITIVE: the capacity binding documents of the shipped cycle are byte
    exact."""
    expected = _expected()
    _compare(BINDING_FILES, expected, {n: _got(n) for n in BINDING_FILES},
             "shipped binding")


def _check_shipped_reconciliation_documents_exact():
    """POSITIVE: the fallback and overturn documents of the shipped cycle are
    byte exact."""
    expected = _expected()
    _compare(RECONCILE_FILES, expected,
             {n: _got(n) for n in RECONCILE_FILES}, "shipped reconciliation")


def _check_shipped_state_documents_exact():
    """POSITIVE: the state documents of the shipped cycle are byte exact."""
    expected = _expected()
    _compare(STATE_FILES, expected, {n: _got(n) for n in STATE_FILES},
             "shipped state")


def _check_shipped_publication_documents_exact():
    """POSITIVE: the manifests, the utilisation report, the audit ledger and
    both digests of the shipped cycle are byte exact."""
    expected = _expected()
    _compare(PUBLISH_FILES, expected, {n: _got(n) for n in PUBLISH_FILES},
             "shipped publication")


def _check_package_runs_from_module_entry_point():
    """POSITIVE: the delivered package runs as a module with the two options
    in either order and creates the destination when it is absent."""
    root = _package_root()
    corpus = _private_copy(_corpus_for(EVAL_SEED, "eval"), "entrypoint")
    dest = Path(tempfile.mkdtemp(prefix="dbk-order-")) / "nested" / "out"
    _open_tree(dest.parent.parent, writable=True)
    code, _out, err = _run_agent_code(
        [sys.executable, "-m", PACKAGE_NAME,
         "--out", str(dest), "--data", str(corpus)],
        cwd=str(root), env=_sandbox_env(root / "src"), timeout=300)
    assert code == 0, ("reversed options were refused: "
                       + err.strip()[-300:])
    produced = sorted(p.name for p in dest.iterdir()) if dest.is_dir() else []
    assert produced == sorted(DOCUMENT_FILES), (
        "the run wrote " + str(len(produced)) + " files, not the "
        + str(len(DOCUMENT_FILES)) + " derived documents")


def _minted_case(tag, seed, names, label):
    expected = _case_expected(tag, seed)
    produced = _case_got(tag, seed)
    _compare(names, expected, produced, label + " " + tag)


def _check_package_eval_intake_exact():
    """POSITIVE: on a cycle minted from a seed the agent never saw, the
    delivered package publishes the intake and policy documents exactly."""
    _minted_case("eval", EVAL_SEED, INTAKE_FILES + POLICY_FILES, "minted")


def _check_package_eval_binding_exact():
    """POSITIVE: on the eval cycle the delivered package publishes the graph
    and capacity binding documents exactly."""
    _minted_case("eval", EVAL_SEED, GRAPH_FILES + BINDING_FILES, "minted")


def _check_package_eval_publication_exact():
    """POSITIVE: on the eval cycle the delivered package publishes the
    reconciliation, state and publication documents exactly."""
    _minted_case("eval", EVAL_SEED,
                 RECONCILE_FILES + STATE_FILES + PUBLISH_FILES, "minted")


def _check_package_challenge_intake_exact():
    """POSITIVE: on the challenge cycle the delivered package publishes the
    intake and policy documents exactly."""
    _minted_case("challenge", CHALLENGE_SEED, INTAKE_FILES + POLICY_FILES,
                 "minted")


def _check_package_challenge_binding_exact():
    """POSITIVE: on the challenge cycle the delivered package publishes the
    graph and capacity binding documents exactly."""
    _minted_case("challenge", CHALLENGE_SEED, GRAPH_FILES + BINDING_FILES,
                 "minted")


def _check_package_challenge_publication_exact():
    """POSITIVE: on the challenge cycle the delivered package publishes the
    reconciliation, state and publication documents exactly."""
    _minted_case("challenge", CHALLENGE_SEED,
                 RECONCILE_FILES + STATE_FILES + PUBLISH_FILES, "minted")


def _check_package_probe_intake_exact():
    """POSITIVE: on the probe cycle the delivered package publishes the
    intake and policy documents exactly."""
    _minted_case("probe", PROBE_SEED, INTAKE_FILES + POLICY_FILES, "minted")


def _check_package_probe_binding_exact():
    """POSITIVE: on the probe cycle the delivered package publishes the graph
    and capacity binding documents exactly."""
    _minted_case("probe", PROBE_SEED, GRAPH_FILES + BINDING_FILES, "minted")


def _check_package_probe_publication_exact():
    """POSITIVE: on the probe cycle the delivered package publishes the
    reconciliation, state and publication documents exactly."""
    _minted_case("probe", PROBE_SEED,
                 RECONCILE_FILES + STATE_FILES + PUBLISH_FILES, "minted")


# --------------------------------------------------------------------------
# per stage assertions
#
# The whole chain documents cascade: one upstream departure moves every
# document after it. These checks feed each delivered stage function the
# reference records of the stages before it, on the probe cycle, and compare
# what it returns with what the reference stage returns. The stage functions
# and the records they pass are the interface package_expectations.toml
# names, so a delivery that repairs every stage but one loses that stage's
# check and keeps the rest.
# --------------------------------------------------------------------------
STAGE_ENCODER = r"""

def enc(o):
    if o is None or isinstance(o, (bool, str, int)):
        return o
    if isinstance(o, float):
        return {"__float__": repr(o)}
    if isinstance(o, Fraction):
        return {"__fraction__": [o.numerator, o.denominator]}
    if isinstance(o, (bytes, bytearray)):
        return {"__bytes__": base64.b64encode(bytes(o)).decode("ascii")}
    if isinstance(o, dict):
        items = [[enc(k), enc(v)] for k, v in o.items()]
        items.sort(key=lambda kv: json.dumps(kv[0], sort_keys=True))
        return {"__dict__": items}
    if isinstance(o, (list, tuple)):
        return [enc(x) for x in o]
    if isinstance(o, (set, frozenset)):
        return {"__set__": sorted((enc(x) for x in o),
                                  key=lambda x: json.dumps(x, sort_keys=True))}
    if isinstance(o, PurePath):
        return {"__path__": str(o)}
    return {"__object__": type(o).__name__}
"""

# Runs only the reference chain, as the verifier, and writes each stage's
# arguments to a file in a directory the sandbox user cannot read.
STAGE_HARNESS = r"""
import base64, io, json, pickle, sys, types
from fractions import Fraction
from pathlib import Path, PurePath

ref_src, corpus, calls_file = sys.argv[1:4]
sys.path.insert(0, ref_src)
from dbkref import allocate, loading, publish, stages
reference = {"loading": loading, "stages": stages,
             "allocate": allocate, "publish": publish}
""" + STAGE_ENCODER + r"""

records = {}
calls = []


class ArgsPickler(pickle.Pickler):
    # r02 hands later stages its resolver closure. It is sent by name and
    # rebuilt on the other side, so no reference function, and through its
    # globals no reference module, ever reaches the delivered process.
    def persistent_id(self, obj):
        if (isinstance(obj, types.FunctionType)
                and obj.__qualname__ == "stage_r02.<locals>.resolve"):
            return "r02.resolve"
        return None


def snapshot(args):
    buf = io.BytesIO()
    ArgsPickler(buf, protocol=pickle.HIGHEST_PROTOCOL).dump(args)
    return buf.getvalue()


def call(key, mod, fn, *args):
    # Each stage's arguments are serialised at call time, so the delivered
    # stage later receives exactly the records the reference stage
    # received, and nothing the reference did afterwards.
    calls.append((key, mod, fn, snapshot(args)))
    result = getattr(reference[mod], fn)(*args)
    records[key] = enc(result)
    return result


data = call("load_all", "loading", "load_all", Path(corpus))
r01 = call("r01", "stages", "stage_r01", data)
r02 = call("r02", "stages", "stage_r02", data, r01)
r03 = call("r03", "stages", "stage_r03", data, r01, r02)
r04 = call("r04", "stages", "stage_r04", data, r01, r02, r03)
r05 = call("r05", "stages", "stage_r05", data, r01, r02, r03, r04)
r06 = call("r06", "stages", "stage_r06", data, r01, r02)
tier_index = {}
by_id = {i["instance_id"]: i for i in r03["instances"]}
for iid in r05["eligible"]:
    aid = by_id[iid]["action_id"]
    tier = r04["resolved"][iid]["tier"]
    if aid not in tier_index or tier < tier_index[aid]:
        tier_index[aid] = tier
fallback_tier = r04["layers"]["global"]["tier"]
r07 = call("r07", "stages", "stage_r07", data, r06, tier_index, fallback_tier)
r08 = call("r08", "stages", "stage_r08", data, r01, r03, r05, r07)
r09 = call("r09", "stages", "stage_r09", data, r01, r02, r04, r08)
r10 = call("r10", "allocate", "stage_r10", data, r01, r02, r04, r08, r09)
r11 = call("r11", "allocate", "stage_r11", data, r01, r02, r04, r07, r08,
           r09, r10)
r12 = call("r12", "allocate", "stage_r12", data, r01, r02, r04, r07, r08,
           r09, r10, r11)
r13 = call("r13", "allocate", "stage_r13", data, r01, r02, r04, r08, r12)
r14 = call("r14", "allocate", "stage_r14", data, r01, r02, r04, r05, r07,
           r08, r09, r10, r12, r13)
r13b = call("r13b", "allocate", "stage_r13", data, r01, r02, r04, r08,
            {"survivors": r14["survivors"],
             "proposal_index": r12["proposal_index"]})
state = {"data": data, "r01": r01, "r02": r02, "r03": r03, "r04": r04,
         "r05": r05, "r06": r06, "r07": r07, "r08": r08, "r09": r09,
         "r10": r10, "r11": r11, "r12": r12, "r13": r13, "r14": r14,
         "r13b": r13b, "tier_index": tier_index}
call("render", "publish", "render", state)

Path(calls_file).write_bytes(pickle.dumps(calls, protocol=pickle.HIGHEST_PROTOCOL))
sys.stdout.write(chr(10) + json.dumps(records, sort_keys=True) + chr(10))
"""

# One delivered stage per process. Its arguments arrive on stdin, so the
# process holds nothing but its own inputs: no reference module, no record
# of a later stage, no file of the verifier's it could read.
STAGE_CALL = r"""
import base64, importlib, io, json, pickle, sys
from fractions import Fraction
from pathlib import PurePath

delivered_src, mod, fn = sys.argv[1:4]
RESOLVE = object()


class ArgsUnpickler(pickle.Unpickler):
    def persistent_load(self, pid):
        if pid != "r02.resolve":
            raise pickle.UnpicklingError("unknown persistent id")
        return RESOLVE


def make_resolver(bindings, cap):
    # RR3 as stage r02 states it: follow bindings up to the hop cap; a name
    # that repeats is a cycle and resolves to itself.
    cache = {}

    def resolve(name):
        if name in cache:
            return cache[name]
        seen = [name]
        cur = name
        hops = 0
        while cur in bindings and hops < cap:
            cur = bindings[cur]
            hops += 1
            if cur in seen:
                cur = name
                break
            seen.append(cur)
        cache[name] = cur
        return cur
    return resolve


def rebind(obj, cap, done):
    if id(obj) in done:
        return
    done.add(id(obj))
    if isinstance(obj, dict):
        if obj.get("resolve") is RESOLVE:
            obj["resolve"] = make_resolver(obj["bindings"], cap)
        for value in obj.values():
            rebind(value, cap, done)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            rebind(value, cap, done)


args = ArgsUnpickler(io.BytesIO(base64.b64decode(sys.stdin.read()))).load()
first = args[0] if args and isinstance(args[0], dict) else {}
controls = first.get("controls") or first.get("data", {}).get("controls", {})
rebind(args, int(controls.get("alias_hop_cap", 0)), set())
sys.path.insert(0, delivered_src)
""" + STAGE_ENCODER + r"""

try:
    module = importlib.import_module("daybreak." + mod)
    record = enc(getattr(module, fn)(*args))
except BaseException as exc:
    record = {"__error__": type(exc).__name__}
sys.stdout.write(chr(10) + json.dumps(record, sort_keys=True) + chr(10))
"""

STAGE_GROUPS = {
    "loading": ("load_all",),
    "intake": ("r01", "r02", "r03"),
    "policy": ("r04", "r05"),
    "graph": ("r06", "r07", "r08"),
    "binding": ("r09", "r10"),
    "reconciliation": ("r11", "r12", "r13", "r14", "r13b", "render"),
}


def _stage_reference_src():
    """The reference package under the private name dbkref, so one process
    can hold it beside the delivered daybreak package."""
    if "stage-src" in _CACHE:
        return _CACHE["stage-src"]
    work = Path(tempfile.mkdtemp(prefix="dbk-stage-"))
    for name, text in REFERENCE_PACKAGE.items():
        if not name.startswith("src/daybreak/"):
            continue
        text = text.replace("from daybreak", "from dbkref")
        text = text.replace("import daybreak", "import dbkref")
        path = work / "src" / "dbkref" / name[len("src/daybreak/"):]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    # The tree stays the verifier's own 0700 directory: delivered code never
    # runs inside it and the sandbox user cannot read it.
    _CACHE["stage-src"] = work
    return work


STAGE_CASES = {"probe": PROBE_SEED, "challenge": CHALLENGE_SEED}

# Single stages re-run on the challenge cycle, where the fixtures of the
# relay group, the equal-strength cycle and the dense knot all bite.
SINGLE_STAGES = ("r03", "r07", "r10", "r12", "r14")


def _stage_reference(tag="probe"):
    """Reference record of every stage on a minted cycle, and the arguments
    each stage received."""
    if ("stage-ref", tag) in _CACHE:
        return _CACHE[("stage-ref", tag)]
    seed = STAGE_CASES[tag]
    corpus = _corpus_for(seed, tag)
    _verify_clean(tag, corpus)
    work = _stage_reference_src()
    calls_file = work / ("calls-" + tag + ".pickle")
    # -I keeps the working directory, PYTHONPATH and user site packages off
    # the import path, so the reference cannot be shadowed from outside.
    cmd = [sys.executable, "-I", "-c", STAGE_HARNESS, str(work / "src"),
           str(corpus), str(calls_file)]
    proc = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True,
                          timeout=300)
    if proc.returncode != 0:
        raise AssertionError("reference stage run failed: "
                             + proc.stderr.strip()[-400:])
    expected = json.loads(proc.stdout.strip().splitlines()[-1])
    import base64
    rendered = {k: base64.b64decode(v["__bytes__"])
                for k, v in expected["render"]["__dict__"]}
    if rendered != _expected(tag, seed):
        raise AssertionError("the stage harness does not reproduce the "
                             "reference chain")
    _CACHE[("stage-calls", tag)] = pickle.loads(calls_file.read_bytes())
    calls_file.unlink()
    _CACHE[("stage-ref", tag)] = expected
    return expected


def _stage_delivered(tag="probe", only=None):
    """What each delivered stage returns when fed the reference records."""
    if ("stage-got", tag) in _CACHE:
        got = _CACHE[("stage-got", tag)]
    else:
        got = _CACHE[("stage-got", tag)] = {}
    _stage_reference(tag)
    import base64
    src = _package_root() / "src"
    env = _sandbox_env(src)
    env.pop("PYTHONPATH", None)
    for key, mod, fn, args in _CACHE[("stage-calls", tag)]:
        if only is not None and key not in only:
            continue
        if key in got:
            continue
        got[key] = None
        cwd = Path(tempfile.mkdtemp(prefix="dbk-stagecall-"))
        _open_tree(cwd)
        payload = base64.b64encode(args).decode("ascii")
        cmd = [sys.executable, "-I", "-c", STAGE_CALL, str(src), mod, fn]
        code, out, _err = _run_agent_code(cmd, cwd=str(cwd), env=env,
                                          timeout=120, stdin_text=payload)
        reap_sandbox_processes()
        lines = [ln for ln in (out or "").splitlines() if ln.strip()]
        if code == 0 and lines:
            try:
                got[key] = json.loads(lines[-1])
            except ValueError:
                pass
    return got


def _check_stage_group(name):
    expected = _stage_reference()
    got = _stage_delivered()
    bad = [key for key in STAGE_GROUPS[name]
           if got.get(key) != expected[key]]
    assert not bad, "stage " + name + " departs at " + ", ".join(bad)


def _check_single_stage(key):
    """One stage fed the reference records of the challenge cycle returns
    exactly the reference record."""
    expected = _stage_reference("challenge")
    got = _stage_delivered("challenge", only=(key,))
    assert got.get(key) == expected[key], ("stage " + key + " departs on the "
                                           "challenge cycle")


# --------------------------------------------------------------------------
# negative assertions
#
# Each one passes only when a cheat is present in the delivery: a replayed
# answer, a fixed directory, a name keyed output, a varying output, a write
# into the papers, a digest that does not describe its documents, a smuggled
# import hook or an installed import. A wrong reading of a paper is never
# charged here; the positive checks already withhold its weight.
# --------------------------------------------------------------------------
def _core_is_right():
    expected = _expected()
    for name in CORE_FILES:
        if _got(name) != expected[name]:
            return False
    return True


def _binds_fixed_directory():
    try:
        return _reads_fixed_directory()
    except Exception:
        return False


def _check_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: the delivered package replays the shipped cycle's documents
    whatever cycle it is pointed at, so a memorised answer stands where a
    chain should.

    The trigger is the copy itself, never the absence of output. Two cycles
    minted from different seeds carry different cycle keys, so a chain that
    reads its input can never publish one cycle's core documents for another,
    and a package that raises is a chain with a bug rather than a copy: the
    minted families already charge that bug once, and this detector stays
    silent on it."""
    if not _core_is_right():
        raise AssertionError("the shipped core is wrong; this detector stays silent")
    if _binds_fixed_directory():
        raise AssertionError("a replay through a fixed directory is charged by "
                             "the hardcoded directory detector alone")
    expected = _expected()
    first = _case_got("eval", EVAL_SEED)
    second = _case_got("challenge", CHALLENGE_SEED)
    assert all(name in first and first[name] == second.get(name)
               and first[name] == expected[name] for name in CORE_FILES)


def _probe_fixed_directory():
    """True when the delivered package reads the fixed path /app/data in
    place of the paper directory it is handed.

    The verifier has no /app/data, so the probe plants one for the length of a
    single run, filled with a different cycle, and drives the package over the
    probe cycle again. A package that takes its papers from --data publishes
    the same bytes with or without the decoy; one that reaches for the fixed
    path publishes the decoy's cycle instead. A package that varies between
    runs is charged by the determinism detector alone, so the probe stands
    down on it."""
    fixed = Path("/app" + "/data")
    if fixed.exists():
        return False
    corpus = _corpus_for(PROBE_SEED, "probe")
    plain = _run_package(corpus, "probe")
    eval_corpus = _corpus_for(EVAL_SEED, "eval")
    if _run_package(eval_corpus, "eval") != _run_package(eval_corpus, "repeat"):
        return False
    shutil.copytree(_corpus_for(CHALLENGE_SEED, "challenge"), fixed)
    try:
        _open_tree(fixed)
        decoyed = _run_package(corpus, "decoy")
    finally:
        shutil.rmtree(fixed, ignore_errors=True)
    return decoyed[0] == "OK" and decoyed != plain


def _reads_fixed_directory():
    if "fixed-dir" not in _CACHE:
        _CACHE["fixed-dir"] = _probe_fixed_directory()
    return _CACHE["fixed-dir"]


def _check_negative_weight_reads_fixed_paper_directory():
    """NEGATIVE: the delivered package reads the fixed path /app/data in
    place of the paper directory it is handed."""
    assert _reads_fixed_directory()


def _check_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: the delivered package publishes different bytes for the same
    cycle depending on the name of the directory it was handed.

    The repeat run over the original directory is taken first and has to agree
    with the original run. Without that step a package that simply varies
    between runs would satisfy this detector too, and one decision would be
    charged twice: a package that is not deterministic is charged by the
    determinism detector alone and this one stays silent on it."""
    corpus = _corpus_for(EVAL_SEED, "eval")
    first = _case_got("eval", EVAL_SEED)
    status, repeat = _run_package(corpus, "repeat")
    assert status == "OK", "the package failed on the second run"
    if any(first.get(name) != repeat.get(name) for name in DOCUMENT_FILES):
        raise AssertionError("the package varies between runs; the determinism "
                             "detector charges that and this one stays silent")
    twin = Path(tempfile.mkdtemp(prefix="dbk-twin-")) / "another_name"
    shutil.copytree(corpus, twin)
    _open_tree(twin.parent, writable=True)
    status, second = _run_package(twin, "twin")
    assert status == "OK", "the package failed on the renamed directory"
    assert any(first.get(name) != second.get(name)
               for name in DOCUMENT_FILES)


def _check_negative_weight_nondeterministic_output():
    """NEGATIVE: two runs of the delivered package over one directory publish
    different bytes."""
    corpus = _corpus_for(EVAL_SEED, "eval")
    first = _case_got("eval", EVAL_SEED)
    status, second = _run_package(corpus, "repeat")
    assert status == "OK", "the package failed on the second run"
    assert any(first.get(name) != second.get(name)
               for name in DOCUMENT_FILES)


def _check_negative_weight_package_dirties_its_directories():
    """NEGATIVE: the delivered package wrote into the paper directory it was
    pointed at.

    Every run drives the package over its own copy of a corpus and compares
    that copy before and after, so a write into the papers is seen without
    ever touching a corpus a graded reference is taken from. Stray files in
    the destination are not charged here: the entry point assertion already
    withholds its weight from a run that writes anything beside the twenty
    eight documents, and one decision is charged once."""
    _case_got("probe", PROBE_SEED)
    assert _CACHE.get("dirtied-probe")


def _check_negative_weight_manifest_digest_mismatch():
    """NEGATIVE: the manifest digests do not describe the documents that were
    actually written beside them."""
    manifest = _got("run_manifest.txt").decode("utf-8").splitlines()
    body = [line for line in manifest if not line.startswith(("core ",
                                                              "publication "))]
    bad = False
    for line in body:
        parts = line.split("  ")
        if len(parts) != 2:
            bad = True
            continue
        digest, name = parts
        path = OUT / name
        if not path.is_file() or sha256_hex(path.read_bytes()) != digest:
            bad = True
    # The publication trailer is graded byte for byte by the publication
    # families; only body lines that misdescribe the files are a cheat.
    assert bad


def _check_negative_weight_rebinds_verifier_dependencies():
    """NEGATIVE: the delivered archive smuggles a startup hook or a standard
    library shadow onto the import path beside the package.

    The archive is the surface that reaches the verifier, not the output
    directory: only the declared artifacts are uploaded, so a file dropped
    beside them is never seen here. A `sitecustomize.py`, a `usercustomize.py`
    or a `.pth` on the path the package is driven with runs before the package
    does, and a module named after a standard library one shadows it, which is
    code outside the eight modules the shape assertion inspects."""
    root = _package_root()
    shadows = {"sitecustomize.py", "usercustomize.py", "json.py",
               "hashlib.py", "zipfile.py", "fractions.py", "pathlib.py",
               "subprocess.py", "os.py"}
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in shadows or path.suffix == ".pth":
            hits.append(str(path.relative_to(root)))
    assert hits


def _check_negative_weight_third_party_import():
    """NEGATIVE: the delivered package imports a module that has to be
    installed, against the standard library only rule the package
    expectations state.

    An absence belongs on this side of the ledger, so an honest delivery
    makes this assertion fail and is charged nothing. Anything the archive
    itself ships is resolved from the archive rather than counted as third
    party, and a module that will not parse is left to the assertions that
    run the package."""
    sources = _package_sources()
    assert sources, "no package source to judge"
    root = _package_root()
    shipped = {PACKAGE_NAME}
    for parent in (root, root / "src"):
        for path in sorted(parent.glob("*")):
            shipped.add(path.name.split(".")[0])
    outside = set()
    for _name, text in sources.items():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    outside.add(alias.name.split(".")[0])
            elif (isinstance(node, ast.ImportFrom) and node.level == 0
                    and node.module):
                outside.add(node.module.split(".")[0])
    outside -= shipped
    outside -= set(sys.stdlib_module_names)
    assert outside


# --------------------------------------------------------------------------
# rewardkit registration
#
# rewardkit runs criteria on worker threads. Every grading surface above
# shares one memo and drives agent code under one sandbox user, so each
# criterion holds a single lock for its whole body and sweeps the sandbox
# user's processes before it releases it: nothing the delivery forked can
# outlive the criterion that started it, and so nothing can outlive the
# final reward write.
# --------------------------------------------------------------------------
_GRADE_LOCK = threading.Lock()


def _holds(check):
    """True when the named check runs to completion. A positive check
    completes when its property holds; a negative check completes only when
    its cheat is present. Any failure, including hostile or missing output,
    is False and never escapes into the rewardkit run."""
    with _GRADE_LOCK:
        try:
            check()
            return True
        except Exception:
            return False
        finally:
            try:
                reap_sandbox_processes()
            except Exception:
                pass


@criterion(description='every declared deliverable is present under /app/out')
def all_artifacts_exist(workspace: Path) -> bool:
    return _holds(_check_all_artifacts_exist)


@criterion(description='every published document parses in its own form, summary.json carries its five keys and run_manifest.txt ends in its two digest lines')
def documents_parse_and_conform(workspace: Path) -> bool:
    return _holds(_check_documents_parse_and_conform)


@criterion(description='the four repair records carry the structural form the schema reference states for them')
def repair_records_conform(workspace: Path) -> bool:
    return _holds(_check_repair_records_conform)


@criterion(description='the defect register books every departure the shipped source carries against its function and stage, and books no function that carries none')
def defect_register_matches_departures(workspace: Path) -> bool:
    return _holds(_check_defect_register_matches_departures)


@criterion(description='the verification notes state the start of the last window and the count per suppression reason of the shipped cycle, each as the cycle yields it')
def verification_notes_state_figures(workspace: Path) -> bool:
    return _holds(_check_verification_notes_state_figures)


@criterion(description='the archive is laid out as the package expectations state and carries the shipped test modules unchanged')
def delivered_package_shape(workspace: Path) -> bool:
    return _holds(_check_delivered_package_shape)


@criterion(description='the intake documents of the shipped cycle are byte exact')
def shipped_intake_documents_exact(workspace: Path) -> bool:
    return _holds(_check_shipped_intake_documents_exact)


@criterion(description='the policy resolution documents of the shipped cycle are byte exact')
def shipped_policy_documents_exact(workspace: Path) -> bool:
    return _holds(_check_shipped_policy_documents_exact)


@criterion(description='the dependency documents of the shipped cycle are byte exact')
def shipped_graph_documents_exact(workspace: Path) -> bool:
    return _holds(_check_shipped_graph_documents_exact)


@criterion(description='the capacity binding documents of the shipped cycle are byte exact')
def shipped_binding_documents_exact(workspace: Path) -> bool:
    return _holds(_check_shipped_binding_documents_exact)


@criterion(description='the delivered package runs as a module with the two options in either order and creates the destination when it is absent')
def package_runs_from_module_entry_point(workspace: Path) -> bool:
    return _holds(_check_package_runs_from_module_entry_point)


@criterion(description='the fallback and overturn documents of the shipped cycle are byte exact')
def shipped_reconciliation_documents_exact(workspace: Path) -> bool:
    return _holds(_check_shipped_reconciliation_documents_exact)


@criterion(description='the state documents of the shipped cycle are byte exact')
def shipped_state_documents_exact(workspace: Path) -> bool:
    return _holds(_check_shipped_state_documents_exact)


@criterion(description='the manifests, the utilisation report, the audit ledger and both digests of the shipped cycle are byte exact')
def shipped_publication_documents_exact(workspace: Path) -> bool:
    return _holds(_check_shipped_publication_documents_exact)


@criterion(description='on a cycle minted from a seed the agent never saw, the delivered package publishes the intake and policy documents exactly')
def package_eval_intake_exact(workspace: Path) -> bool:
    return _holds(_check_package_eval_intake_exact)


@criterion(description='on the eval cycle the delivered package publishes the graph and capacity binding documents exactly')
def package_eval_binding_exact(workspace: Path) -> bool:
    return _holds(_check_package_eval_binding_exact)


@criterion(description='on the eval cycle the delivered package publishes the reconciliation, state and publication documents exactly')
def package_eval_publication_exact(workspace: Path) -> bool:
    return _holds(_check_package_eval_publication_exact)


@criterion(description='on the challenge cycle the delivered package publishes the intake and policy documents exactly')
def package_challenge_intake_exact(workspace: Path) -> bool:
    return _holds(_check_package_challenge_intake_exact)


@criterion(description='on the challenge cycle the delivered package publishes the graph and capacity binding documents exactly')
def package_challenge_binding_exact(workspace: Path) -> bool:
    return _holds(_check_package_challenge_binding_exact)


@criterion(description='on the challenge cycle the delivered package publishes the reconciliation, state and publication documents exactly')
def package_challenge_publication_exact(workspace: Path) -> bool:
    return _holds(_check_package_challenge_publication_exact)


@criterion(description='on the probe cycle the delivered package publishes the intake and policy documents exactly')
def package_probe_intake_exact(workspace: Path) -> bool:
    return _holds(_check_package_probe_intake_exact)


@criterion(description='on the probe cycle the delivered package publishes the graph and capacity binding documents exactly')
def package_probe_binding_exact(workspace: Path) -> bool:
    return _holds(_check_package_probe_binding_exact)


@criterion(description='on the probe cycle the delivered package publishes the reconciliation, state and publication documents exactly')
def package_probe_publication_exact(workspace: Path) -> bool:
    return _holds(_check_package_probe_publication_exact)


@criterion(description='on the probe cycle the delivered loading.load_all returns the records the reference reader returns')
def stage_loading_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_stage_group("loading"))


@criterion(description='fed the reference records of the probe cycle, the delivered stages r01 to r03 each return what the reference stage returns')
def stage_intake_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_stage_group("intake"))


@criterion(description='fed the reference records of the probe cycle, the delivered stages r04 and r05 each return what the reference stage returns')
def stage_policy_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_stage_group("policy"))


@criterion(description='fed the reference records of the probe cycle, the delivered stages r06 to r08 each return what the reference stage returns')
def stage_graph_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_stage_group("graph"))


@criterion(description='fed the reference records of the probe cycle, the delivered stages r09 and r10 each return what the reference stage returns')
def stage_binding_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_stage_group("binding"))


@criterion(description='fed the reference records of the probe cycle, the delivered stages r11 to r14, the second state pass and the renderer each return what the reference returns')
def stage_reconciliation_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_stage_group("reconciliation"))


@criterion(description='fed the reference records of the challenge cycle, the delivered r03 (routine expansion) returns exactly what the reference stage returns')
def stage_r03_challenge_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_single_stage("r03"))


@criterion(description='fed the reference records of the challenge cycle, the delivered r07 (cycle settlement) returns exactly what the reference stage returns')
def stage_r07_challenge_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_single_stage("r07"))


@criterion(description='fed the reference records of the challenge cycle, the delivered r10 (initial capacity binding) returns exactly what the reference stage returns')
def stage_r10_challenge_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_single_stage("r10"))


@criterion(description='fed the reference records of the challenge cycle, the delivered r12 (precedence reconciliation) returns exactly what the reference stage returns')
def stage_r12_challenge_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_single_stage("r12"))


@criterion(description='fed the reference records of the challenge cycle, the delivered r14 (state feedback and readmission) returns exactly what the reference stage returns')
def stage_r14_challenge_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_single_stage("r14"))


@criterion(description="the delivered package replays the shipped cycle's documents whatever cycle it is pointed at, so a memorised answer stands where a chain should")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Inverted: True means the cheat was seen; the negative weight punishes it.
    return _holds(_check_negative_weight_hardcoded_sample_answers)


@criterion(description='the delivered package reads the fixed path /app/data in place of the paper directory it is handed')
def negative_reads_fixed_paper_directory(workspace: Path) -> bool:
    # Inverted: True means the cheat was seen; the negative weight punishes it.
    return _holds(_check_negative_weight_reads_fixed_paper_directory)


@criterion(description='the delivered package publishes different bytes for the same cycle depending on the name of the directory it was handed')
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Inverted: True means the cheat was seen; the negative weight punishes it.
    return _holds(_check_negative_weight_filename_dependent_behaviour)


@criterion(description='two runs of the delivered package over one directory publish different bytes')
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Inverted: True means the cheat was seen; the negative weight punishes it.
    return _holds(_check_negative_weight_nondeterministic_output)


@criterion(description='the delivered package wrote into the paper directory it was pointed at')
def negative_package_edits_its_paper_directory(workspace: Path) -> bool:
    # Inverted: True means the cheat was seen; the negative weight punishes it.
    return _holds(_check_negative_weight_package_dirties_its_directories)


@criterion(description='the manifest digests do not describe the documents that were actually written beside them')
def negative_manifest_digest_mismatch(workspace: Path) -> bool:
    # Inverted: True means the cheat was seen; the negative weight punishes it.
    return _holds(_check_negative_weight_manifest_digest_mismatch)


@criterion(description='the delivered archive smuggles a startup hook or a standard library shadow onto the import path beside the package')
def negative_rebinds_verifier_dependencies(workspace: Path) -> bool:
    # Inverted: True means the cheat was seen; the negative weight punishes it.
    return _holds(_check_negative_weight_rebinds_verifier_dependencies)


@criterion(description='the delivered package imports a module that has to be installed, against the standard library only rule the package expectations state')
def negative_third_party_import(workspace: Path) -> bool:
    # Inverted: True means the cheat was seen; the negative weight punishes it.
    return _holds(_check_negative_weight_third_party_import)


criteria.all_artifacts_exist(weight=1)
criteria.documents_parse_and_conform(weight=1)
criteria.repair_records_conform(weight=1)
criteria.delivered_package_shape(weight=1)
criteria.shipped_intake_documents_exact(weight=3)
criteria.shipped_policy_documents_exact(weight=3)
criteria.shipped_graph_documents_exact(weight=3)
criteria.shipped_binding_documents_exact(weight=3)
criteria.package_runs_from_module_entry_point(weight=3)
criteria.shipped_reconciliation_documents_exact(weight=5)
criteria.shipped_state_documents_exact(weight=5)
criteria.shipped_publication_documents_exact(weight=5)
criteria.package_eval_intake_exact(weight=5)
criteria.package_eval_binding_exact(weight=5)
criteria.package_eval_publication_exact(weight=5)
criteria.package_challenge_intake_exact(weight=5)
criteria.package_challenge_binding_exact(weight=5)
criteria.package_challenge_publication_exact(weight=5)
criteria.package_probe_intake_exact(weight=5)
criteria.package_probe_binding_exact(weight=5)
criteria.package_probe_publication_exact(weight=5)
criteria.stage_loading_exact(weight=5)
criteria.stage_intake_exact(weight=5)
criteria.stage_policy_exact(weight=5)
criteria.stage_graph_exact(weight=5)
criteria.stage_binding_exact(weight=5)
criteria.stage_reconciliation_exact(weight=5)
criteria.defect_register_matches_departures(weight=5)
criteria.verification_notes_state_figures(weight=3)
criteria.stage_r03_challenge_exact(weight=3)
criteria.stage_r07_challenge_exact(weight=3)
criteria.stage_r10_challenge_exact(weight=3)
criteria.stage_r12_challenge_exact(weight=3)
criteria.stage_r14_challenge_exact(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_fixed_paper_directory(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_package_edits_its_paper_directory(weight=-3)
criteria.negative_manifest_digest_mismatch(weight=-3)
criteria.negative_rebinds_verifier_dependencies(weight=-3)
criteria.negative_third_party_import(weight=-3)


def _write_corpus(root):
    """Regenerate the shipped paper directory from SAMPLE_SEED."""
    return generate(SAMPLE_SEED, Path(root))


def main():
    if len(sys.argv) > 1:
        root = Path(sys.argv[1]) / "data"
    else:
        root = Path(tempfile.mkdtemp(prefix="dbk-selfcheck-")) / "data"
    info = _write_corpus(root)
    blobs = _reference_blobs(root)
    print("corpus files", len(info["files"]))
    print("cycle", info["cycle"], "profile", info["profile"])
    print("documents", len(blobs))
    print("manifest tail", blobs["run_manifest.txt"].decode().splitlines()[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
