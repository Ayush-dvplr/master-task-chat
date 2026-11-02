#!/usr/bin/env python3
"""Verifier for the 4da82574-5e37-514d-aba2-a86b179fb55a bundle.

Holds the corpus generator, an independent reference chain for the fourteen
stage custody replay, and the graded assertions. The verifier owns its corpus:
every case it grades is minted here from a named seed, so no graded value
depends on the directory the agent was handed.

Two grading surfaces. The artifacts the agent delivered for the shipped epoch
are compared against this file's own reference chain. The package the agent
delivered is extracted and driven over three epochs minted from seeds it has
never seen, in a subprocess with privileges dropped to nobody.
"""
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
import zlib
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from rewardkit import criteria, criterion

SAMPLE_SEED = 6420917853311647203
EVAL_SEED = 3148806572290143759
CHALLENGE_SEED = 8072451936604821377
PROBE_SEED = 6730543763647290293

NL = chr(10)
BS = chr(92)
Q = chr(34)
TAB = chr(9)
PIPE = chr(124)
MASK64 = 0xFFFFFFFFFFFFFFFF

OUTPUT_ROOT = "/app/out"
_OUT_ROOT = [OUTPUT_ROOT]
PACKAGE_NAME = "bcrep"
ARCHIVE_BUDGET_BYTES = 256 * 1024 * 1024
# Generous enough that only a package which does not terminate trips it. The
# contract states no per run budget, so a tight limit would quietly forfeit
# the whole minted tier on slow hardware for work that is in fact correct.
# Delivered runs are taken one at a time, so the limit also keeps every run
# a package that never terminates can force inside the verifier's own budget.
PACKAGE_RUN_TIMEOUT_SEC = 300

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


# --------------------------------------------------------------------------
# exact arithmetic
#
# Every published whole quantity is an integer in the unit its stage names and
# every published ratio carries exactly twelve decimal places. Rounding happens
# where a stage specification places it and nowhere else, and it is always
# half away from zero on an exact rational. Binary floating point never enters
# the derivation.
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


def write_xlsx(path, sheets, parts=None):
    """parts gives, for each sheet in workbook order, the number of the
    worksheet part its relationship points at; by default the k-th sheet
    sits in sheetk.xml."""
    shared = []
    shared_idx = {}
    sheet_xmls = []
    for name, rows in sheets.items():
        sheet_xmls.append((name, _sheet_xml(rows, shared, shared_idx)))
    parts = list(parts or range(1, len(sheet_xmls) + 1))

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
                  + " Target=" + _q("worksheets/sheet" + str(parts[i - 1])
                                    + ".xml") + "/>")
    wr.append("<Relationship Id=" + _q("rId" + str(len(sheets) + 1)) + " Type="
              + _q(NS_REL + "/sharedStrings") + " Target=" + _q("sharedStrings.xml") + "/>")
    wr.append("</Relationships>")

    members = [("[Content_Types].xml", "".join(ct)),
               ("_rels/.rels", root_rels),
               ("xl/workbook.xml", "".join(wb)),
               ("xl/_rels/workbook.xml.rels", "".join(wr)),
               ("xl/sharedStrings.xml", "".join(ss))]
    for number, (name, xml) in sorted(zip(parts, sheet_xmls)):
        members.append(("xl/worksheets/sheet" + str(number) + ".xml", xml))
    _zip_parts(path, members)


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
    """A line given as a string is shown with Tj. A line given as a list of
    fragments is shown with one kerned TJ array, its fragments joined in
    order. Every content stream is FlateDecode compressed."""
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
            if isinstance(one, str):
                content += "(" + esc(one) + ") Tj T*" + NL
                continue
            shown = []
            for k, fragment in enumerate(one):
                if k:
                    shown.append(str(-6 - 3 * (k % 3)))
                shown.append("(" + esc(fragment) + ")")
            content += "[" + " ".join(shown) + "] TJ T*" + NL
        content += "ET"
        cbytes = zlib.compress(content.encode("latin-1", "replace"), 9)
        page_obj_num = 3 + 2 * i
        objects.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       "/Resources << /Font << /F1 " + str(font_obj) + " 0 R >> >> "
                       "/Contents " + str(page_obj_num + 1) + " 0 R >>")
        objects.append((cbytes, "<< /Length " + str(len(cbytes))
                        + " /Filter /FlateDecode >>"))
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
    """Ordered mapping of sheet name to list of row lists. Each sheet reaches
    its worksheet part through the workbook relationship its r:id names."""
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sroot = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sroot:
                shared.append("".join(t.text or "" for t in si.iter()
                                      if t.tag.endswith("}t")))
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        part_of = {}
        for rel in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels")):
            target = rel.attrib.get("Target", "")
            part_of[rel.attrib.get("Id")] = (target.lstrip("/") if target.startswith("/")
                                             else "xl/" + target)
        sheets = []
        for sh in wb.iter():
            if sh.tag.endswith("}sheet"):
                sheets.append((sh.attrib.get("name"),
                               part_of.get(sh.attrib.get("{" + NS_REL + "}id"), "")))
        out = {}
        for name, member in sheets:
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


def _pdf_contents(raw):
    """The payload of every stream, inflated when its dictionary carries
    /FlateDecode."""
    out = []
    opening = (NL + "stream" + NL).encode("latin-1")
    at = raw.find(opening)
    while at >= 0:
        head = raw[raw.rfind(b"<<", 0, at):at].decode("latin-1")
        fields = head.replace("<<", " ").replace(">>", " ").split()
        size = int(fields[fields.index("/Length") + 1])
        start = at + len(opening)
        payload = raw[start:start + size]
        if "/FlateDecode" in fields:
            payload = zlib.decompress(payload)
        out.append(payload)
        at = raw.find(opening, start + size)
    return out


def read_pdf_lines(path):
    """Text lines of a PDF written by the corpus generator: one line per text
    showing operator, a TJ array giving its strings joined in order."""
    out = []
    for payload in _pdf_contents(Path(path).read_bytes()):
        tokens = []
        i = 0
        while i < len(payload):
            ch = payload[i:i + 1]
            if ch == b"(":
                depth, cur, i = 1, [], i + 1
                while depth:
                    ch = payload[i:i + 1]
                    if ch == BS.encode("latin-1"):
                        cur.append(payload[i + 1:i + 2])
                        i += 2
                        continue
                    depth += {b"(": 1, b")": -1}.get(ch, 0)
                    if depth:
                        cur.append(ch)
                    i += 1
                tokens.append(("str", b"".join(cur).decode("latin-1")))
            elif ch in (b"[", b"]"):
                tokens.append((ch.decode("latin-1"), ""))
                i += 1
            elif ch.isspace():
                i += 1
            else:
                j = i
                while (j < len(payload) and not payload[j:j + 1].isspace()
                       and payload[j:j + 1] not in (b"(", b")", b"[", b"]")):
                    j += 1
                tokens.append(("word", payload[i:j].decode("latin-1")))
                i = j
        held, inside = [], None
        for kind, value in tokens:
            if kind == "[":
                inside = []
            elif kind == "]":
                held.append(("array", inside))
                inside = None
            elif kind == "str" and inside is not None:
                inside.append(value)
            elif kind == "str":
                held.append(("str", value))
            elif value == "Tj" and held and held[-1][0] == "str":
                out.append(held[-1][1])
                held = []
            elif value == "TJ" and held and held[-1][0] == "array":
                out.append("".join(held[-1][1]))
                held = []
            elif inside is None and value[:1].isalpha():
                held = []
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


def read_xml_rows(path, tag):
    root = ET.parse(str(path)).getroot()
    return [dict(node.attrib) for node in root.iter(tag)]


# --------------------------------------------------------------------------
# the reference chain
#
# Fourteen stages, written flat here so the verifier owns a derivation that
# does not share a line with the package the agent repairs. Nothing below
# reads a value the agent cannot read: every constant it uses is loaded out of
# the corpus directory it is handed.
# --------------------------------------------------------------------------
STAGE_IDS = ["r01", "r02", "r03", "r04", "r05", "r06", "r07",
             "r08", "r09", "r10", "r11", "r12", "r13", "r14"]

COUNTER_NAMES = ["compensations", "deferred_admitted", "granted_cu", "grants",
                 "retired_cu", "retires", "reversed_cu", "spilled_cu",
                 "transferred_cu", "transfers"]

QUARANTINE_ORDER = ["EVT-DRAFTREVISION", "EVT-WITHDRAWN", "EVT-UNKNOWNSTATION",
                    "EVT-UNKNOWNPROGRAMME", "EVT-NONPOSITIVE",
                    "EVT-IMPLAUSIBLE", "CMP-WITHDRAWN", "CMP-NOTARGET",
                    "DEP-SELF", "DEP-CYCLE", "DEP-MISSING"]

STAGE_OF = {"EVT-DRAFTREVISION": "r01", "EVT-WITHDRAWN": "r01",
            "EVT-UNKNOWNSTATION": "r02", "EVT-UNKNOWNPROGRAMME": "r02",
            "EVT-NONPOSITIVE": "r01", "EVT-IMPLAUSIBLE": "r01",
            "CMP-WITHDRAWN": "r09", "CMP-NOTARGET": "r09",
            "DEP-SELF": "r07", "DEP-CYCLE": "r07", "DEP-MISSING": "r07"}

CORE_DOCUMENTS = ["canonical_order.csv", "checkpoint_selection.json",
                  "replay_window.json", "dependency_closure.json",
                  "transition_log.jsonl", "compensation_register.csv",
                  "final_state.json"]

ARTIFACT_NAMES = [
    "alias_resolution.jsonl", "bounded_replay.json", "canonical_order.csv",
    "checkpoint_reconciliation.json", "checkpoint_selection.json",
    "compensation_register.csv", "defect_register.md", "derived_counters.csv",
    "derived_index.jsonl", "dependency_closure.json",
    "eligibility_passes.json", "equivalence_report.json", "final_state.json",
    "quarantine_ledger.csv", "replay_window.json", "repair_report.json",
    "run_manifest.txt", "selftest.json", "state_at_event.json",
    "summary.json", "transition_log.jsonl", "unit_normalisation.json",
    "verification_notes.md",
]

PACKAGE_MODULES = ["__init__", "__main__", "checkpointing", "compensation",
                   "derived", "depends", "normalise", "ordering", "params",
                   "publish", "reading", "replay", "transitions", "window"]


def _int(text):
    return int(str(text).strip())


def _flat_toml(path):
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


# --------------------------------------------------------------------------
# the reference chain
#
# An independent implementation of the fourteen stages, written from the stage
# papers under environment/data/ rather than from the bcrep source it grades.
# Only the format plumbing above is shared with the corpus generator: the
# readers for the shapes the papers arrive in, the writers for the shapes the
# documents go out in, the digest, the half away from zero rounding and the
# twelve place ratio. Every decision this chain takes about the epoch comes
# from the stage paper that specifies it.
#
# That independence is the whole point of the oracle run. A reference copied
# from the package it grades cannot disagree with it, so the run would return
# a green light whatever the papers say. Two implementations written apart
# agree only when both are right, and that agreement is the evidence.
# --------------------------------------------------------------------------
COUNTERS = COUNTER_NAMES
STAGES = STAGE_IDS
CODES = QUARANTINE_ORDER


def _i(value):
    return int(str(value).strip())


def _s(value):
    return str(value).strip()


# ---------------------------------------------------------------- r01, r02
def in_force(rows, key_field, revision_field, frozen):
    """A row is in force at or below the frozen revision; among those the
    greatest revision governs (revision_precedence.toml)."""
    held = {}
    for row in rows:
        if _i(row[revision_field]) > frozen:
            continue
        key = _s(row[key_field])
        if key not in held or _i(row[revision_field]) >= _i(held[key][revision_field]):
            held[key] = row
    return held


def live_sheet(root, epoch_key):
    """r01: the sheet whose epoch_key cell equals the header key. Sheet names
    and sheet order carry no meaning."""
    for name, rows in read_xlsx_sheets(root / "custody_parameter_workbook.xlsx").items():
        for row in rows:
            if len(row) >= 2 and _s(row[0]) == "epoch_key":
                if _s(row[1]) == epoch_key:
                    return name, rows
                break
    raise SystemExit("no workbook sheet carries the epoch key in force")


def sheet_layers(rows):
    """r01: conversion, reversal, carry_quantum and ceiling rows. Rows tagged
    calibration are bench notes and settle nothing."""
    classes, ceilings = {}, {}
    fields = {"conversion": ("conversion_num", "conversion_den"),
              "reversal": ("reversal_num", "reversal_den")}
    for row in rows:
        if not row:
            continue
        tag = _s(row[0])
        if tag in fields and len(row) >= 4:
            num, den = fields[tag]
            classes.setdefault(_s(row[1]), {})[num] = _i(row[2])
            classes[_s(row[1])][den] = _i(row[3])
        elif tag == "carry_quantum" and len(row) >= 3:
            classes.setdefault(_s(row[1]), {})["carry_quantum"] = _i(row[2])
        elif tag == "ceiling" and len(row) >= 4:
            ceilings[(_i(row[1]), _s(row[2]))] = _i(row[3])
    return classes, ceilings


def memo_scalars(root):
    """r01: a resolution carries its sitting. Among live resolutions on one
    subject the greater sitting governs; a RESCINDED line is not a resolution."""
    held = {}
    for raw in read_pdf_lines(root / "custody_board_memo.pdf"):
        line = raw.strip()
        if not line.startswith("RESOLUTION "):
            continue
        words = line.split(" ")
        if len(words) < 4 or words[2] != "SITTING":
            continue
        sitting = int(words[3])
        subject, joined, value = " ".join(words[4:]).partition(" = ")
        if not joined:
            continue
        subject = subject.strip()
        if subject not in held or sitting > held[subject][0]:
            held[subject] = (sitting, value.strip())
    return {k: v[1] for k, v in held.items()}


def directive(root):
    """r07, r10, r12: the five level ladder and the two closure rules."""
    ladder, duplicate, closure = [], "", ""
    for block in read_docx_blocks(root / "precedence_directive.docx"):
        if isinstance(block, list):
            if len(block) >= 3 and block[0] == "level":
                ladder.append((_i(block[1]), _s(block[2])))
        elif block.startswith("DUPLICATE TARGET RULE: "):
            duplicate = block.split(": ", 1)[1].strip()
        elif block.startswith("DEPENDENCY CLOSURE RULE: "):
            closure = block.split(": ", 1)[1].strip()
    return [name for _rank, name in sorted(ladder)], duplicate, closure


def parameters(root):
    header = read_json(root / "epoch_header.json")
    name, rows = live_sheet(root, _s(header["workbook_epoch_key"]))
    classes, ceilings = sheet_layers(rows)
    memo = memo_scalars(root)
    ladder, duplicate, closure = directive(root)
    units = _flat_toml(root / "unit_registry.toml").get("units", {})
    policy = read_flat_yaml(root / "eligibility_policy.yaml")
    arithmetic = read_flat_yaml(root / "rounding_and_arithmetic_policy.yaml")
    form = _flat_toml(root / "publication_form_rules.toml")
    reversal = _flat_toml(root / "compensation_policy.toml")
    roster = read_conf(root / "reporting_station_roster.conf")
    frozen = int(header["frozen_register_revision"])
    forms = {}
    for predicate, row in in_force(read_delim(root / "eligibility_predicates.csv"),
                                   "predicate_id", "revision", frozen).items():
        forms[predicate] = (_s(row["status"]), _s(row["form"]).split(":")[1:])
    legacy = {_s(row["class"]): _i(row["carry_quantum"])
              for row in read_delim(root / "legacy_scale_table.csv")}
    return {
        "header": header,
        "live_sheet": name,
        "classes": classes,
        "ceilings": ceilings,
        "round_ceiling": int(memo["revalidation round ceiling"]),
        "implausible_ceiling": int(memo["implausible quantity ceiling cu"]),
        "settlement_floor": int(memo["settlement floor cu"]),
        "levels": ladder,
        "duplicate_rule": duplicate,
        "closure_rule": closure,
        "units": {k: int(v) for k, v in units.items()},
        "screen_order": policy["screen_order"]["order"],
        "ratio_places": int(arithmetic["ratio"]["places"]),
        "core_documents": form["core_digest"]["documents"],
        "counter_map": dict(reversal["reversal_counter_map"]),
        "regions": {k: int(v) for k, v in roster.get("region_rank", {}).items()},
        "forms": forms,
        "legacy_quanta": legacy,
    }


def registers(root, frozen, rules=()):
    """r02: the frozen register governs; the current one governs nothing."""
    station_paper = ("station_register_current.csv" if "R_CURRENT_REGISTER" in rules
                     else "station_register_frozen.csv")
    stations = in_force(read_delim(root / station_paper),
                        "station", "revision", frozen)
    programmes = in_force(read_delim(root / "programme_register.csv"),
                          "programme", "revision", frozen)
    crosswalk = {}
    for row in read_delim(root / "alias_crosswalk.tsv", TAB):
        if _i(row["in_force_from_revision"]) > frozen:
            continue
        key = (_s(row["kind"]), _s(row["alias"]))
        if key not in crosswalk or _i(row["in_force_from_revision"]) >= _i(
                crosswalk[key]["in_force_from_revision"]):
            crosswalk[key] = row
    scope = {}
    for node in read_xml_rows(root / "topology_and_scope.xml", "station"):
        if _i(node["revision"]) <= frozen:
            scope[_s(node["id"])] = node
    return stations, programmes, crosswalk, scope


def canonical_name(crosswalk, kind, recorded):
    row = crosswalk.get((kind, _s(recorded)))
    return _s(row["canonical"]) if row else _s(recorded)


# -------------------------------------------------------------------- r03
def canonical_history(root, frozen, crosswalk, rules):
    """r03: one record survives per identifier, then the five level order."""
    priority = {name: _i(row["priority"]) for name, row in in_force(
        read_delim(root / "source_priority_register.csv"),
        "source", "revision", frozen).items()}
    ranks = {name: _i(row["rank"]) for name, row in in_force(
        read_delim(root / "event_kind_ranks.csv"),
        "kind", "revision", frozen).items()}
    lodged_by = {}
    for row in read_delim(root / "row_provenance_ledger.csv"):
        lodged_by.setdefault(_s(row["record_id"]), {})[_s(row["file"])] = _s(row["source"])
    recalled = {_s(row["event_id"])
                for row in read_delim(root / "withdrawn_event_journal.tsv", TAB)
                if _i(row["withdrawn_at_revision"]) <= frozen}
    # data_lineage.md: supplement rows under one identifier prefix were
    # lodged for a later epoch and govern nothing here.
    lineage = " ".join((root / "data_lineage.md").read_text(encoding="utf-8").split())
    later = lineage.partition("whose identifier begins `")[2].partition("`")[0]

    surviving = {}
    for paper in ("event_journal.jsonl", "event_supplement.ndjson"):
        for record in read_jsonl(root / paper):
            record = dict(record)
            eid = _s(record["event_id"])
            if paper == "event_supplement.ndjson" and later and eid.startswith(later):
                continue
            source = _s(record.get("source") or "")
            if source == "":
                # r03: the provenance ledger names the source of a record
                # that carries none.
                source = lodged_by.get(eid, {}).get(paper, "")
            standing = (priority.get(source, 0), int(record["revision"]))
            if eid not in surviving or standing > surviving[eid][0]:
                surviving[eid] = (standing, record)

    history = []
    for eid, (_standing, record) in surviving.items():
        entry = dict(record)
        entry["event_id"] = eid
        entry["withdrawn"] = eid in recalled
        entry["draft"] = int(record["revision"]) > frozen
        entry["station"] = canonical_name(crosswalk, "station", record["station"])
        entry["programme"] = canonical_name(crosswalk, "programme", record["programme"])
        if record.get("counterparty"):
            entry["counterparty"] = canonical_name(crosswalk, "station",
                                                   record["counterparty"])
        entry["rank"] = ranks.get(_s(record["kind"]), 99)
        history.append(entry)

    if "R_ARRIVAL_ORDER" in rules:
        levels = (lambda r: (int(r["sequence"]), int(r["stamp"])))
    else:
        levels = (lambda r: (int(r["sequence"]), int(r["stamp"]), int(r["rank"]),
                             str(r["tiebreak"]), str(r["event_id"])))
    history.sort(key=levels)
    for index, entry in enumerate(history, start=1):
        entry["position"] = index
    return history


# -------------------------------------------------------------------- r07
def requires_edges(root, frozen):
    """r07: only requires rows in force are edges. The depends_on list inside
    a journal record is a stale copy and governs nothing."""
    edges = {}
    for row in read_delim(root / "dependency_edges.psv", PIPE):
        if _i(row["revision"]) > frozen or _s(row["edge_kind"]) != "requires":
            continue
        named = _s(row["depends_on"])
        held = edges.setdefault(_s(row["event_id"]), [])
        if named and named not in held:
            held.append(named)
    for key in edges:
        edges[key].sort()
    return edges


def cycle_members(history, edges, by_id):
    """r07: an identifier stands on a cycle when some path of edges in force
    leads from it back to itself. Edges naming an identifier the canonical
    history does not carry take no part."""
    members = set()
    for entry in history:
        start = entry["event_id"]
        seen = set()
        frontier = [n for n in edges.get(start, []) if n in by_id]
        while frontier:
            node = frontier.pop()
            if node == start:
                members.add(start)
                break
            if node in seen:
                continue
            seen.add(node)
            frontier.extend(n for n in edges.get(node, []) if n in by_id)
    return members


# -------------------------------------------------------------------- r09
def compensation_links(root, frozen):
    return in_force(read_delim(root / "compensation_links.csv"),
                    "compensation_id", "revision", frozen)


# ------------------------------------------------------------------- r01
def rounded(value, rules):
    """Half away from zero; the banker's reading rounds halves to even."""
    if "R_BANKERS_ROUNDING" in rules:
        return round(Fraction(value))
    return half_up(value)


def normalise(record, params, stations, rules=()):
    """r01: the unit scale first, then the class conversion, rounded once
    here, half away from zero, on an exact rational."""
    station = stations.get(_s(record["station"]))
    if station is None:
        return None, None
    klass = _s(station["class"])
    factors = params["classes"].get(klass)
    scale = params["units"].get(_s(record["unit"]))
    if factors is None or scale is None:
        return None, klass
    exact = (Fraction(int(record["quantity"]) * scale)
             * Fraction(factors["conversion_num"], factors["conversion_den"]))
    return rounded(exact, rules), klass


def ref_context(root, rules=()):
    rules = set(rules)
    params = parameters(root)
    frozen = int(params["header"]["frozen_register_revision"])
    stations, programmes, crosswalk, scope = registers(root, frozen, rules)
    history = canonical_history(root, frozen, crosswalk, rules)
    by_id = {entry["event_id"]: entry for entry in history}
    edges = requires_edges(root, frozen)
    quantity, klass = {}, {}
    for entry in history:
        value, name = normalise(entry, params, stations, rules)
        quantity[entry["event_id"]] = value
        klass[entry["event_id"]] = name
    station_paper = ("station_register_current.csv" if "R_CURRENT_REGISTER" in rules
                     else "station_register_frozen.csv")
    return {"root": Path(root), "params": params, "frozen": frozen,
            "rules": rules, "stations": stations, "programmes": programmes,
            "alias": crosswalk, "scope": scope, "events": history,
            "by_id": by_id, "edges": edges,
            "links": compensation_links(root, frozen),
            "norm": quantity, "cls": klass,
            "station_rows": read_delim(root / station_paper),
            "cycles": cycle_members(history, edges, by_id)}


# -------------------------------------------------------------- screening
def screen(ep, record):
    """r01, r02, r09: the first test a record fails decides its code, and the
    tests run in the order eligibility_policy.yaml gives."""
    kind = _s(record["kind"])
    compensating = kind == "compensate"
    value = ep["norm"].get(record["event_id"])
    link = ep["links"].get(record["event_id"])

    def unknown_station():
        if _s(record["station"]) not in ep["stations"]:
            return True
        if kind != "transfer":
            return False
        other = _s(record.get("counterparty") or "")
        return other == "" or other not in ep["stations"]

    tests = {
        "EVT-DRAFTREVISION": lambda: bool(record["draft"]),
        "EVT-WITHDRAWN": lambda: bool(record["withdrawn"]),
        "EVT-UNKNOWNSTATION": unknown_station,
        # A compensating event names no programme and carries no quantity of
        # its own, so the programme and quantity codes never fire on one.
        "EVT-UNKNOWNPROGRAMME": lambda: not compensating and _s(
            record["programme"]) not in ep["programmes"],
        "EVT-NONPOSITIVE": lambda: not compensating and (value is None or value <= 0),
        "EVT-IMPLAUSIBLE": lambda: not compensating and value is not None and (
            value > ep["params"]["implausible_ceiling"]),
        "CMP-WITHDRAWN": lambda: compensating and (
            link is None or _s(link["status"]) != "registered"),
        "CMP-NOTARGET": lambda: compensating and link is not None and (
            _s(link["target_event_id"]) not in ep["by_id"]),
    }
    for code in ep["params"]["screen_order"]:
        probe = tests.get(code)
        if probe is not None and probe():
            return code
    return None


def dependency(ep, record, opening):
    """r07: self edges and cycles first, then each named dependency by its
    canonical position against the window opening and the depending event."""
    eid = record["event_id"]
    named = ep["edges"].get(eid, [])
    if eid in named:
        return "DEP-SELF", []
    if eid in ep["cycles"]:
        return "DEP-CYCLE", []
    routes = []
    for dep in named:
        target = ep["by_id"].get(dep)
        if target is None:
            return "DEP-MISSING", routes
        at = int(target["position"])
        if at < opening:
            # Already folded into the restored checkpoint (directive closure
            # rule, spec_stage_r07).
            if "R_CHECKPOINT_DEP_MISSING" in ep["rules"]:
                return "DEP-MISSING", routes
            routes.append("checkpoint")
        elif at < int(record["position"]):
            routes.append("window")
        else:
            return "DEP-MISSING", routes
    return None, routes


# ----------------------------------------------------------------- state
class Ledger:
    """r05, r08, r13: the whole state one replay carries."""

    __slots__ = ("balances", "allotments", "counters", "pending",
                 "applied", "reversed")

    def __init__(self):
        self.balances = {}
        self.allotments = {}
        self.counters = dict.fromkeys(COUNTERS, 0)
        self.pending = []
        self.applied = []
        self.reversed = []

    @classmethod
    def restored_from(cls, body):
        """r05: restoration copies the body, nested containers included, so a
        second replay from one checkpoint opens from the same state."""
        state = cls()
        state.balances = dict(body["balances"])
        state.allotments = {k: dict(v) for k, v in body["allotments"].items()}
        state.counters = dict(body["counters"])
        state.pending = list(body["pending"])
        state.applied = list(body["applied"])
        state.reversed = list(body["reversed"])
        return state

    def move(self, station, programme, amount):
        self.balances[station] = self.balances.get(station, 0) + amount
        held = self.allotments.setdefault(station, {})
        held[programme] = held.get(programme, 0) + amount

    def body(self, position):
        """r13: zero balances drop, zero allotments drop, and a station left
        holding none drops with them."""
        allotments = {}
        for station, held in self.allotments.items():
            surviving = {k: v for k, v in held.items() if v != 0}
            if surviving:
                allotments[station] = surviving
        return {"position": position,
                "balances": {k: v for k, v in self.balances.items() if v != 0},
                "allotments": allotments,
                "counters": dict(self.counters),
                "pending": list(self.pending),
                "applied": sorted(self.applied),
                "reversed": sorted(self.reversed)}


def ref_digest(body):
    """The serialisation contract: sha256 of the compact json of the seven
    state keys, sorted, with applied and reversed ascending."""
    payload = {key: body[key] for key in ("position", "balances", "allotments",
                                          "counters", "pending", "applied",
                                          "reversed")}
    return digest_bytes(compact_json(payload).encode("utf-8"))


def settle(ep, state, touched):
    """r11: after every applied transition and compensation the stations the
    event touched settle, in ascending station order."""
    for station in sorted(touched):
        row = ep["stations"].get(station)
        if row is None:
            continue
        klass = _s(row["class"])
        ceiling = ep["params"]["ceilings"].get((ep["frozen"], klass))
        if "R_DEFAULT_QUANTUM" in ep["rules"]:
            quantum = 50
        elif "R_LEGACY_QUANTUM" in ep["rules"]:
            quantum = ep["params"]["legacy_quanta"].get(klass)
        else:
            quantum = ep["params"]["classes"].get(klass, {}).get("carry_quantum")
        if ceiling is None or not quantum:
            continue
        balance = state.balances.get(station, 0)
        if balance <= ceiling:
            continue
        carried = ((balance - ceiling) // quantum) * quantum
        if carried <= 0:
            continue
        state.balances[station] = balance - carried
        state.counters["spilled_cu"] += carried


def predicate_holds(text, state, stations, forms):
    """r12: the register in force gives each form its status and the order of
    its arguments. A form the register does not carry as active, or a
    predicate whose argument count disagrees with its form, is false whenever
    it is read. Arguments are read as written."""
    if not text:
        return True
    parts = str(text).split(":")
    status, names = forms.get(parts[0], ("", []))
    if status != "active" or len(names) != len(parts) - 1:
        return False
    arg = dict(zip(names, parts[1:]))
    form = parts[0]
    if form == "balance_at_least":
        return state.balances.get(arg["station"], 0) >= int(arg["amount_cu"])
    if form == "allotment_below":
        held = state.allotments.get(arg["station"], {})
        return held.get(arg["programme"], 0) < int(arg["amount_cu"])
    if form == "counter_at_least":
        return state.counters.get(arg["counter"], 0) >= int(arg["amount"])
    if form == "no_pending":
        return not state.pending
    if form == "station_active":
        row = stations.get(arg["station"])
        return row is not None and _s(row["status"]) == "active"
    return False


# ----------------------------------------------------------- r08, r10, r12
def apply_transition(ep, state, record, log, order):
    """r08: the ordinary transitions and the counters each one moves."""
    eid = record["event_id"]
    amount = ep["norm"][eid]
    station = _s(record["station"])
    programme = _s(record["programme"])
    kind = _s(record["kind"])
    touched = {station}
    if kind == "grant":
        state.move(station, programme, amount)
    elif kind == "retire":
        state.move(station, programme, -amount)
    else:
        other = _s(record["counterparty"])
        state.move(station, programme, -amount)
        state.move(other, programme, amount)
        touched.add(other)
    state.counters[kind + "s"] += 1
    state.counters[{"grant": "granted_cu", "retire": "retired_cu",
                    "transfer": "transferred_cu"}[kind]] += amount
    settle(ep, state, touched)
    state.applied.append(eid)
    log.append({"order": order[0], "event_id": eid,
                "position": int(record["position"]), "kind": kind,
                "station": station, "programme": programme,
                "quantity_cu": amount,
                "balance_after": state.balances.get(station, 0)})
    order[0] += 1


def apply_compensation(ep, state, record, register, order):
    """r09, r10: the target is read off the canonical history wherever it
    stands, and reversed exactly once."""
    eid = record["event_id"]
    target_id = _s(ep["links"][eid]["target_event_id"])
    target = ep["by_id"][target_id]
    row = {"compensation_id": eid, "target_event_id": target_id,
           "target_position": int(target["position"]),
           "disposition": "", "reversed_cu": 0, "applied_order": 0}

    duplicate = target_id in state.reversed
    if duplicate and "R_DUPLICATE_APPLIED" not in ep["rules"]:
        row["disposition"] = "void_duplicate"
        register.append(row)
        return
    if target_id not in state.applied:
        row["disposition"] = "void_unapplied"
        register.append(row)
        return

    amount = ep["norm"][target_id]
    station = _s(target["station"])
    programme = _s(target["programme"])
    kind = _s(target["kind"])
    touched = {station}
    if kind == "grant":
        state.move(station, programme, -amount)
    elif kind == "retire":
        state.move(station, programme, amount)
    else:
        other = _s(target["counterparty"])
        state.move(station, programme, amount)
        state.move(other, programme, -amount)
        touched.add(other)

    # r10: the reversal scale belongs to the class the frozen register carried
    # for the target station at the revision of the target record itself.
    lodged = in_force(ep["station_rows"], "station", "revision", int(target["revision"]))
    held = lodged.get(station)
    klass = _s(held["class"]) if held else ep["cls"][target_id]
    factors = ep["params"]["classes"][klass]
    reversed_cu = rounded(Fraction(amount)
                          * Fraction(factors["reversal_num"],
                                     factors["reversal_den"]), ep["rules"])
    if "R_NO_DERIVED_REVERSAL" not in ep["rules"]:
        state.counters[ep["params"]["counter_map"][kind]] -= reversed_cu
        state.counters[kind + "s"] -= 1
    state.counters["reversed_cu"] += reversed_cu
    state.counters["compensations"] += 1
    state.reversed.append(target_id)
    settle(ep, state, touched)
    row["disposition"] = "applied"
    row["reversed_cu"] = reversed_cu
    row["applied_order"] = order[0]
    order[0] += 1
    register.append(row)


def ladder_key(ep, record):
    """r12: the five level ladder the directive puts in force."""
    scope_rank = 0 if str(record.get("scope", "standard")) == "mandatory" else 1
    station = ep["stations"].get(_s(record["station"]))
    region = _s(station["region"]) if station else ""
    return (scope_rank, ep["params"]["regions"].get(region, 99),
            ep["norm"].get(record["event_id"]) or 0,
            int(record["position"]), str(record["event_id"]))


def build_window(ep, start, end, watermark, total):
    """r06: half open. The opening is the later of the requested start and one
    past the watermark; the close is one before the requested end or the last
    canonical position."""
    step = 0 if "R_WATERMARK" in ep["rules"] else 1
    opening = max(int(start), watermark + step)
    closing = int(end)
    if "R_END_INCLUSIVE" in ep["rules"]:
        last = min(closing, total)
        return opening, closing, list(range(opening, last + 1))
    return opening, closing, list(range(opening, min(closing, total + 1)))


def replay(ep, start, end, body=None, run_rounds=True):
    """r05 to r12: one forward pass over the window, then the re offer rounds."""
    history = ep["events"]
    total = len(history)
    if body is None:
        state, watermark = Ledger(), 0
    else:
        state, watermark = Ledger.restored_from(body), int(body["position"])
    opening, closing, positions = build_window(ep, start, end, watermark, total)

    quarantine, deferred, log, register, unsatisfied = [], [], [], [], []
    closure = {"checkpoint": 0, "window": 0}
    order = [1]

    for at in positions:
        record = history[at - 1]
        reason = screen(ep, record)
        routes = []
        if reason is None:
            reason, routes = dependency(ep, record, opening)
        if reason is None:
            for where in routes:
                closure[where] += 1
        else:
            quarantine.append({"event_id": record["event_id"], "position": at,
                               "stage": STAGE_OF[reason],
                               "reason_code": reason,
                               "detail": _s(record["kind"])})
            if reason.startswith("DEP-"):
                unsatisfied.append({"event_id": record["event_id"],
                                    "reason": reason})
            continue
        if _s(record["kind"]) == "compensate":
            if "R_TARGET_IN_WINDOW" in ep["rules"]:
                named = ep["by_id"][_s(ep["links"][record["event_id"]]["target_event_id"])]
                if int(named["position"]) < opening:
                    quarantine.append({"event_id": record["event_id"],
                                       "position": at, "stage": "r09",
                                       "reason_code": "CMP-NOTARGET",
                                       "detail": _s(record["kind"])})
                    continue
            apply_compensation(ep, state, record, register, order)
            continue
        if predicate_holds(record.get("requires"), state, ep["stations"],
                           ep["params"]["forms"]):
            apply_transition(ep, state, record, log, order)
        else:
            # r12: a false predicate defers, it does not quarantine.
            state.pending.append(record["event_id"])
            deferred.append(record["event_id"])

    rounds, stable = [], True
    if run_rounds:
        stable = False
        ceiling = 1 if "R_SINGLE_ROUND" in ep["rules"] else int(
            ep["params"]["round_ceiling"])
        for index in range(1, ceiling + 1):
            if "R_QUEUE_CANONICAL" in ep["rules"]:
                queue = list(state.pending)
            else:
                queue = sorted(state.pending,
                               key=lambda eid: ladder_key(ep, ep["by_id"][eid]))
            admitted = []
            for eid in queue:
                record = ep["by_id"][eid]
                if not predicate_holds(record.get("requires"), state, ep["stations"],
                                       ep["params"]["forms"]):
                    continue
                state.pending.remove(eid)
                apply_transition(ep, state, record, log, order)
                state.counters["deferred_admitted"] += 1
                admitted.append(eid)
            if not admitted:
                stable = True
                break
            rounds.append({"round": index, "admitted": admitted,
                           "admitted_count": len(admitted)})

    return {"state": state, "watermark": watermark, "window_start": opening,
            "window_end": closing, "positions": positions,
            "quarantine": quarantine, "deferred": deferred, "log": log,
            "register": register, "closure": closure,
            "unsatisfied": unsatisfied, "rounds": rounds, "stable": stable}


# -------------------------------------------------------------------- r04
def select_checkpoint(ep, end):
    """r04: sealed, lodged, digest matching, in force, its applied ledger
    standing at or before its watermark, and strictly before the end boundary.
    Among those the greatest position is selected."""
    lodged = {_s(body["checkpoint_id"]): body
              for body in read_jsonl(ep["root"] / "checkpoint_states.jsonl")}
    usable, rejected = [], []
    for row in read_delim(ep["root"] / "checkpoint_register.csv"):
        cid = _s(row["checkpoint_id"])
        body = lodged.get(cid)
        grounds = None
        if _i(row["revision"]) > ep["frozen"]:
            grounds = "draft_revision"
        elif _s(row["status"]) != "sealed":
            grounds = "not_sealed"
        elif body is None:
            grounds = "body_missing"
        elif ref_digest(body) != _s(row["state_digest"]):
            grounds = "digest_mismatch"
        elif not all(eid in ep["by_id"]
                     and int(ep["by_id"][eid]["position"]) <= int(body["position"])
                     for eid in body["applied"]):
            grounds = "ledger_past_watermark"
        elif int(body["position"]) >= int(end):
            grounds = "position_at_or_after_end"
        if grounds is not None:
            rejected.append({"checkpoint_id": cid, "reason": grounds})
            continue
        usable.append((int(body["position"]), cid, body, row))
    usable.sort()
    rejected.sort(key=lambda r: (r["checkpoint_id"], r["reason"]))
    if not usable:
        return None, [], rejected
    return usable[-1], [cid for _at, cid, _b, _r in usable], rejected


# -------------------------------------------------------------- r13, r14
def ref_publish(root, out, rules=()):
    """r13, r14: materialise the epoch and write the twenty three derived
    documents, taking the two digests last over the bytes already written."""
    root, out = Path(root), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ep = ref_context(root, rules)
    params, header = ep["params"], ep["params"]["header"]
    frozen, history = ep["frozen"], ep["events"]
    total = len(history)

    start = int(header["replay_start_position"])
    end = int(header["replay_end_position"])
    probe_at = int(header["state_probe_position"])
    bounded_start = int(header["bounded_start_position"])
    bounded_end = int(header["bounded_end_position"])

    chosen, usable, rejected = select_checkpoint(ep, end)
    main = replay(ep, start, end, chosen[2] if chosen else None)
    scratch = replay(ep, 1, end, None)
    probe = replay(ep, 1, probe_at + 1, None, run_rounds=False)
    bounded_pick, _u, _r = select_checkpoint(ep, bounded_end)
    bounded = replay(ep, bounded_start, bounded_end,
                     bounded_pick[2] if bounded_pick else None)
    state = main["state"]
    final = state.body(main["window_end"])
    scratch_final = scratch["state"].body(scratch["window_end"])

    write_json(out / "unit_normalisation.json", {
        "epoch_id": header["epoch_id"],
        "workbook_epoch_key": header["workbook_epoch_key"],
        "live_sheet": params["live_sheet"],
        "frozen_register_revision": frozen,
        "round_ceiling": params["round_ceiling"],
        "implausible_ceiling_cu": params["implausible_ceiling"],
        "settlement_floor_cu": params["settlement_floor"],
        "precedence_levels": params["levels"],
        "units": dict(params["units"]),
        "classes": {k: dict(v) for k, v in params["classes"].items()},
        "ceilings": {str(rev) + ":" + klass: value
                     for (rev, klass), value in params["ceilings"].items()},
        "event_count": total,
        "normalised_total_cu": sum(v for v in ep["norm"].values()
                                   if v is not None and v > 0),
    })

    write_jsonl(out / "alias_resolution.jsonl", [
        {"alias": alias, "canonical": _s(ep["alias"][(kind, alias)]["canonical"]),
         "kind": kind,
         "in_force_from_revision": _i(ep["alias"][(kind, alias)]["in_force_from_revision"])}
        for kind, alias in sorted(ep["alias"])])

    write_delim(out / "canonical_order.csv",
                  ["position", "event_id", "sequence", "stamp", "kind", "rank",
                   "tiebreak"],
                  [[e["position"], e["event_id"], int(e["sequence"]),
                    int(e["stamp"]), e["kind"], e["rank"], e["tiebreak"]]
                   for e in history], ",")

    write_json(out / "checkpoint_selection.json", {
        "requested_start": start, "requested_end": end,
        "usable": sorted(usable),
        "selected": chosen[1] if chosen else "",
        "selected_position": chosen[0] if chosen else 0,
        "watermark_position": main["watermark"],
        "rejected": rejected,
    })

    write_json(out / "replay_window.json", {
        "start_position": main["window_start"],
        "end_position": main["window_end"],
        "replayed_count": len(main["positions"]),
        "first_replayed_position": main["positions"][0] if main["positions"] else 0,
        "last_replayed_position": main["positions"][-1] if main["positions"] else 0,
        "skipped_before_watermark": max(0, main["watermark"] - start + 1),
        "boundary": "start inclusive, end exclusive",
    })

    write_json(out / "dependency_closure.json", {
        "edges_in_force": sum(len(v) for v in ep["edges"].values()),
        "satisfied_by_checkpoint": main["closure"]["checkpoint"],
        "satisfied_by_window": main["closure"]["window"],
        "unsatisfied": sorted(main["unsatisfied"],
                              key=lambda r: (r["event_id"], r["reason"])),
        "cycle_members": sorted(ep["cycles"]),
    })

    write_delim(out / "quarantine_ledger.csv",
                  ["event_id", "position", "stage", "reason_code", "detail"],
                  [[r["event_id"], r["position"], r["stage"], r["reason_code"],
                    r["detail"]]
                   for r in sorted(main["quarantine"],
                                   key=lambda r: (r["position"], r["event_id"]))],
                  ",")

    write_jsonl(out / "transition_log.jsonl", main["log"])

    write_delim(out / "compensation_register.csv",
                  ["compensation_id", "target_event_id", "target_position",
                   "disposition", "reversed_cu", "applied_order"],
                  [[r["compensation_id"], r["target_event_id"],
                    r["target_position"], r["disposition"], r["reversed_cu"],
                    r["applied_order"]]
                   for r in sorted(main["register"],
                                   key=lambda r: r["compensation_id"])], ",")

    write_delim(out / "derived_counters.csv", ["counter", "value"],
                  [[name, state.counters[name]] for name in COUNTERS], ",")

    write_json(out / "eligibility_passes.json", {
        "pass_ceiling": params["round_ceiling"],
        "deferred_at_first_pass": sorted(main["deferred"]),
        "rounds": main["rounds"],
        "round_count": len(main["rounds"]),
        "stable": main["stable"],
        "deferred_remaining": list(state.pending),
    })

    write_json(out / "final_state.json", final)

    index = []
    for station in sorted(final["allotments"]):
        node = ep["scope"].get(station, {})
        held = final["allotments"][station]
        across = sum(held.values())
        for programme in sorted(held):
            index.append({"region": node.get("region", ""),
                          "hub": node.get("hub", ""),
                          "station": station, "programme": programme,
                          "allotment_cu": held[programme],
                          "share": safe_ratio(held[programme], across)})
    index.sort(key=lambda r: (r["region"], r["hub"], r["station"], r["programme"]))
    write_jsonl(out / "derived_index.jsonl", index)

    # The schema counts and sums rows: a row lodged twice counts twice.
    archive = read_sqlite_table(root / "prior_epoch_archive.db", "prior_counters")
    ceiling_rows = read_delim(root / "allotment_ceiling_history.tsv", TAB)
    deltas, historic, declared, recomputed = {}, 0, "", ""
    if chosen:
        for name in COUNTERS:
            kept = [int(row["value"]) for row in archive
                    if _s(row["checkpoint_id"]) == chosen[1] and _s(row["counter"]) == name]
            if kept:
                deltas[name] = kept[-1] - int(chosen[2]["counters"].get(name, 0))
        declared = _s(chosen[3]["state_digest"])
        recomputed = ref_digest(chosen[2])
        at_revision = _i(chosen[3]["revision"])
        historic = sum(_i(row["ceiling_cu"]) for row in ceiling_rows
                       if _i(row["revision"]) == at_revision)
    write_json(out / "checkpoint_reconciliation.json", {
        "selected": chosen[1] if chosen else "",
        "declared_digest": declared, "recomputed_digest": recomputed,
        "matches": declared == recomputed and declared != "",
        "archive_rows": len(archive),
        "counter_deltas": dict(deltas),
        "historic_ceiling_total_cu": historic,
        "rejected_count": len(rejected),
    })

    write_json(out / "equivalence_report.json", {
        "comparison_start": 1, "comparison_end": end,
        "checkpoint_used": chosen[1] if chosen else "",
        "from_scratch_digest": ref_digest(scratch_final),
        "from_checkpoint_digest": ref_digest(final),
        "identical": scratch_final == final,
        "scratch_replayed_count": len(scratch["positions"]),
        "checkpoint_replayed_count": len(main["positions"]),
    })

    write_json(out / "state_at_event.json", probe["state"].body(probe_at))

    write_json(out / "bounded_replay.json", {
        "start_position": bounded["window_start"],
        "end_position": bounded["window_end"],
        "replayed_count": len(bounded["positions"]),
        "state": bounded["state"].body(bounded["window_end"]),
    })

    write_json(out / "repair_report.json", {
        "package": PACKAGE_NAME, "modules": PACKAGE_MODULES,
        "stage_ids": STAGES, "stage_count": len(STAGES),
        "entry_point": PACKAGE_NAME + ".__main__",
        "standard_library_only": True, "reason_codes": CODES,
    })

    checks = [
        ("canonical_order_total", total),
        ("checkpoint_digest_matches", 1 if (chosen and declared == recomputed) else 0),
        ("window_end_exclusive",
         1 if (not main["positions"] or main["positions"][-1] < end) else 0),
        ("watermark_replayed_once", 0 if main["watermark"] in main["positions"] else 1),
        ("scratch_matches_checkpoint", 1 if scratch_final == final else 0),
        ("targets_reversed_once",
         1 if len(set(state.reversed)) == len(state.reversed) else 0),
        ("pending_after_rounds", len(state.pending)),
        ("rounds_run", len(main["rounds"])),
    ]
    counts = ("canonical_order_total", "pending_after_rounds", "rounds_run")
    flags = [v for n, v in checks if n not in counts]
    write_json(out / "selftest.json", {
        "checks": [{"name": n, "value": v} for n, v in checks],
        "passed": flags.count(1), "failed": flags.count(0)})

    catalogue = set()
    for row in read_delim(root / "quarantine_reason_catalogue.psv", PIPE):
        if _i(row["revision"]) <= frozen and _s(row["code"]) in CODES:
            catalogue.add((_s(row["code"]), _s(row["stage"]), _s(row["meaning"])))
    register_lines = ["# Defect register", "",
                      "| stage | reason code | meaning |", "| --- | --- | --- |"]
    for code, stage, meaning in sorted(catalogue):
        register_lines.append("| " + stage + " | " + code + " | " + meaning + " |")
    register_lines += ["", "Stages in force: " + ", ".join(STAGES)]
    write_lines(out / "defect_register.md", register_lines)

    floor = params["settlement_floor"]
    breaches = [k for k, v in final["balances"].items() if v < floor]
    applied = sum(1 for r in main["register"] if r["disposition"] == "applied")
    void = len(main["register"]) - applied
    write_lines(out / "verification_notes.md", [
        "# Verification notes", "",
        "epoch " + str(header["epoch_id"]),
        "live sheet " + str(params["live_sheet"]),
        "watermark position " + str(main["watermark"]),
        "window " + str(main["window_start"]) + " to " + str(main["window_end"])
        + " end exclusive",
        "rounds run " + str(len(main["rounds"])),
        "stable " + ("yes" if main["stable"] else "no"),
        "pending after rounds " + str(len(state.pending)),
        "compensations applied " + str(applied),
        "compensations void " + str(void),
        "reversed cu " + str(state.counters["reversed_cu"]),
        "spilled cu " + str(state.counters["spilled_cu"]),
        "settlement floor " + str(floor),
        "settlement floor breaches " + str(len(breaches)),
        "scratch equals checkpoint " + ("yes" if scratch_final == final else "no"),
        ""])

    balance_total = sum(final["balances"].values())
    allotment_total = sum(sum(v.values()) for v in final["allotments"].values())
    write_json(out / "summary.json", {
        "epoch_id": header["epoch_id"], "live_sheet": params["live_sheet"],
        "frozen_register_revision": frozen,
        "control_totals": {
            "canonical_events": total,
            "checkpoint_position": main["watermark"],
            "window_start": main["window_start"],
            "window_end": main["window_end"],
            "replayed_positions": len(main["positions"]),
            "quarantined_events": len(main["quarantine"]),
            "deferred_at_first_pass": len(main["deferred"]),
            "admitted_in_rounds": sum(r["admitted_count"] for r in main["rounds"]),
            "round_count": len(main["rounds"]),
            "pending_remaining": len(state.pending),
            "compensations_applied": applied, "compensations_void": void,
            "reversed_cu": state.counters["reversed_cu"],
            "spilled_cu": state.counters["spilled_cu"],
            "balance_total_cu": balance_total,
            "allotment_total_cu": allotment_total,
            "index_rows": len(index),
            "settlement_floor_breaches": len(breaches),
        },
        "stable": main["stable"],
        "equivalence_identical": scratch_final == final,
        "balance_share": safe_ratio(balance_total, allotment_total),
    })

    core = b"".join((out / name).read_bytes() for name in params["core_documents"])
    whole = b"".join((out / name).read_bytes()
                     for name in sorted(ARTIFACT_NAMES)
                     if name != "run_manifest.txt")
    write_lines(out / "run_manifest.txt",
                  ["core " + digest_bytes(core),
                   "publication " + digest_bytes(whole)])
    return out


def ref_snapshots(ep, limit):
    """The checkpoint bodies of one epoch: the state after each canonical
    position in the forward pass, before any re offer round runs."""
    body, held = None, {}
    total = len(ep["events"])
    for position in range(1, min(limit, total) + 1):
        body = replay(ep, position, position + 1, body,
                      run_rounds=False)["state"].body(position)
        held[position] = body
    return held


# --------------------------------------------------------------------------
# corpus generator
#
# One epoch of the custody ledger, minted from a named seed. Every rule the
# graded chain exercises is written into the papers this function emits, so a
# careful reader of the shipped directory can derive every published value.
# --------------------------------------------------------------------------
CLASS_NAMES = ["AX", "BR", "CN", "DL", "LX", "RX"]
REGIONS = ["R-ALPHA", "R-BRAVO", "R-CORAL", "R-DELTA", "R-ECHO", "R-FLINT"]
HUBS = ["H-01", "H-02", "H-03", "H-04", "H-05", "H-06", "H-07", "H-08"]
UNIT_NAMES = ["cu", "dcu", "kcu", "shift", "halfshift", "block"]
UNIT_SCALES = {"cu": 1, "dcu": 10, "kcu": 1000, "shift": 480,
               "halfshift": 240, "block": 2880}
STATION_COUNT = 224
PROGRAMME_COUNT = 208
EVENT_COUNT = 300
SNAPSHOT_LIMIT = 270
LADDER_STATION = "ST-0224"
LADDER_CLASS = "LX"
HALF_STATION = "ST-0223"
HALF_CLASS = "RX"
HALF_GRANT_INDEX = 120
HALF_COMPENSATION_INDEX = 139
HALF_QUANTITY = 4001
ROUND_CEILING = 3
END_POSITION = 240
BOUNDED_START = 140
BOUNDED_END = 205
PROBE_POSITION = 67
LADDER_AT = 150
LADDER_BASE = 4000
LADDER_STEPS = [(600, 4000), (500, 4600), (400, 5100),
                (300, 5500), (200, 5800), (100, 6000)]
SHIPPED_USABLE = [8]
MINTED_USABLE = {EVAL_SEED: SHIPPED_USABLE + [220], PROBE_SEED: [220]}
# The readings every checkpoint body other than a usable one is replayed
# under, so a body the register does not offer is a plausible state that is
# not the state the forward pass reached.
DECOY_READINGS = ("R_ARRIVAL_ORDER", "R_BANKERS_ROUNDING",
                  "R_CURRENT_REGISTER", "R_LEGACY_QUANTUM")
SHARED_SPAN = (158, END_POSITION - 1)
LATER_EPOCH_IDS = ["EVT-881000", "EVT-881002", "EVT-883117"]
MINTED_ROUND_CEILING = {PROBE_SEED: ROUND_CEILING + 9}
MINTED_PROBE = {CHALLENGE_SEED: 160}
FIXTURE_SPAN = (100, 230)
TIE_INDEXES = {offset + step + 1
               for offset, steps in [(o, 4) for o in (11, 40, 77, 133, 190, 233, 261)]
               + [(o, 3) for o in (58, 145, 212)] + [(o, 2) for o in (95, 178)]
               for step in range(steps)}


def plant_shared_fixtures(events, stations, classes, clean, live_programmes,
                          pool, frozen):
    """Rewrite plain events of every epoch, the shipped one included, so that
    each rule the shipped epoch used to leave quiet moves a published value.
    No draw is taken from the epoch generator, so every later draw holds."""
    by_station = {s["station"]: s for s in stations}
    rank = {name: k for k, name in enumerate(REGIONS, start=1)}
    fresh = [s["station"] for s in stations[120:220]
             if s["revision"] <= frozen and s["status"] == "active"
             and s["station"] not in (LADDER_STATION, HALF_STATION)][5:]
    compensating = [i for i in range(1, EVENT_COUNT + 1) if i % 9 == 4
                    and not LADDER_AT <= i <= LADDER_AT + len(LADDER_STEPS)]
    # 171, 203, 215 and 226 carry the self edge and the three event cycle.
    free = [i for i in sorted(clean)
            if SHARED_SPAN[0] <= i <= SHARED_SPAN[1] and i not in TIE_INDEXES
            and i not in (171, 203, 215, 226)]
    used, held = [], []

    def eid(index):
        return "EVT-" + str(index).rjust(6, "0")

    def take(after=0):
        index = next(i for i in free if i not in used and i > after)
        used.append(index)
        return index

    def station(test):
        name = next(s for s in fresh if s not in held and test(by_station[s]))
        held.append(name)
        return name

    def rewrite(index, **fields):
        record = events[index - 1]
        record.update({"requires": None, "counterparty": None, "unit": "cu",
                       "revision": 1, "scope": "standard",
                       "station": pool[(index * 13) % len(pool)]})
        record.update(fields)
        return record

    def compensation_after(index):
        found = next(i for i in compensating if i > index and i not in used
                     and SHARED_SPAN[0] <= i <= SHARED_SPAN[1]
                     and i not in TIE_INDEXES and i % 29 != 5)
        used.append(found)
        rewrite(found, kind="compensate", quantity=0)
        return found

    def normalised(name, quantity):
        factors = classes[by_station[name]["class"]]
        return half_up(Fraction(quantity) * Fraction(factors["conversion_num"],
                                                     factors["conversion_den"]))

    def scale(klass):
        return Fraction(classes[klass]["reversal_num"], classes[klass]["reversal_den"])

    # Position one waits on an empty queue. The register retires no_pending at
    # revision 7, so in an epoch frozen at 7 or later the grant never lands.
    used.append(1)
    events[0]["requires"] = "no_pending"

    # A grant behind the shipped checkpoint that the first compensation of the
    # window reverses, its target read off the canonical history.
    used.extend([6, 13])
    rewrite(6, kind="grant", programme=live_programmes[18], quantity=30)

    # Six events sharing sequence and stamp: the canonical order puts the
    # compensation ahead of the grant it names, arrival order puts it after.
    group = next(i for i in range(SHARED_SPAN[0], SHARED_SPAN[1] - 5) if i % 9 == 1
                 and all(j not in TIE_INDEXES and j % 29 != 5 for j in range(i, i + 6)))
    for offset, kind in enumerate(["grant", "retire", "transfer", "compensate",
                                   "grant", "retire"]):
        index = group + offset
        used.append(index)
        other = pool[(index * 29 + 5) % len(pool)]
        if other == pool[(index * 13) % len(pool)]:
            other = pool[(index * 29 + 6) % len(pool)]
        rewrite(index, kind=kind, quantity=0 if kind == "compensate" else 20 + offset,
                counterparty=other if kind == "transfer" else None,
                sequence=events[group - 1]["sequence"], stamp=events[group - 1]["stamp"])

    # A retire that a later compensation reverses, ahead of the counter offers.
    retired = take(after=group + 5)
    rewrite(retired, kind="retire", station=station(lambda s: True),
            programme=live_programmes[15], quantity=35)
    retire_reversal = compensation_after(retired)

    # A grant lodged while its station still carried the class of its revision
    # one row, reversed later at that class's scale; and a grant whose
    # allotment predicate, written in the argument order the register puts in
    # force at revision 6, only holds once that reversal has landed.
    holder = station(lambda s: (int(s["station"][3:]) - 1) % 3 == 0
                     and s["revision"] >= 3 and s["class"] in CLASS_NAMES[:4]
                     and scale(CLASS_NAMES[(CLASS_NAMES.index(s["class"]) + 2) % 4])
                     != scale(s["class"]))
    lodged = take(after=retire_reversal)
    rewrite(lodged, kind="grant", station=holder, programme=live_programmes[11],
            quantity=40)
    waiting = take(after=lodged)
    rewrite(waiting, kind="grant", station=holder, programme=live_programmes[12],
            quantity=9, requires="allotment_below:" + live_programmes[11] + ":"
            + holder + ":" + str(normalised(holder, 40)))
    reversal = compensation_after(waiting)

    # Two pairs that both wait for the third round of the ladder chain. In each
    # pair the second grant waits on the first one's station, and the region
    # the frozen register gives the drafted station decides whether the ladder
    # offers it before or after the first one inside that round.
    threshold = LADDER_STEPS[3][1]
    for drafted in ("ST-0058", "ST-0145"):
        row = by_station[drafted]
        shade = REGIONS[(REGIONS.index(row["region"]) + 2) % len(REGIONS)]
        low, high = sorted((rank[row["region"]], rank[shade]))
        anchor = station(lambda s, low=low, high=high: low < rank[s["region"]] < high)
        first, second = take(after=reversal), take(after=reversal)
        rewrite(first, kind="grant", station=anchor, programme=live_programmes[13],
                quantity=16, requires="balance_at_least:" + LADDER_STATION + ":"
                + str(threshold))
        rewrite(second, kind="grant", station=drafted, programme=live_programmes[14],
                quantity=11, requires="balance_at_least:" + anchor + ":"
                + str(normalised(anchor, 16)))

    # A cycle a depth first walk misses one member of: edges a to b, b to c,
    # c to a, a to d and d to b, where the walk reaches b before d.
    ring = [take(), take(), take(), take()]
    for index in ring:
        rewrite(index, kind="grant", programme=live_programmes[(index * 7) % 120],
                quantity=17)
    a, b, c, d = ring

    # Two grants offered last whose counter predicates the derived reversal
    # decides. The thresholds are set once the corpus is on disk.
    granted, retired_wait = sorted(i for i in free if i not in used)[-2:][::-1]
    used.extend([granted, retired_wait])
    if retired_wait < retire_reversal:
        raise SystemExit("the retire reversal must land before its counter offer")
    rewrite(granted, kind="grant", station=station(lambda s: True),
            programme=live_programmes[16], quantity=13,
            requires="counter_at_least:granted_cu:" + str(10 ** 9))
    rewrite(retired_wait, kind="grant", station=station(lambda s: True),
            programme=live_programmes[17], quantity=12,
            requires="counter_at_least:retired_cu:" + str(10 ** 9))

    for index in used:
        if index in clean:
            clean.remove(index)
    return {"ids": {eid(i) for i in used},
            "links": {eid(13): eid(6), eid(group + 3): eid(group),
                      eid(reversal): eid(lodged),
                      eid(retire_reversal): eid(retired)},
            "cycle": [(eid(a), eid(b)), (eid(b), eid(c)), (eid(c), eid(a)),
                      (eid(a), eid(d)), (eid(d), eid(b))],
            "counters": [(eid(granted), "granted_cu"),
                         (eid(retired_wait), "retired_cu")],
            "ledger_anchor": eid(group)}


def plant_minted_fixtures(events, stations, classes, clean, live_programmes,
                          pool, frozen, implausible, settlement_floor,
                          absent, shut, top):
    """Rewrite a handful of plain events of a minted epoch so that each branch
    and boundary the shipped epoch never reaches carries one graded input."""
    by_station = {s["station"]: s for s in stations}
    fresh = [s["station"] for s in stations[120:220]
             if s["revision"] <= frozen and s["status"] == "active"
             and s["station"] not in (LADDER_STATION, HALF_STATION)]
    dormant = next(s["station"] for s in stations
                   if s["status"] == "dormant" and s["revision"] <= frozen)
    candidates = [i for i in sorted(clean)
                  if FIXTURE_SPAN[0] <= i <= FIXTURE_SPAN[1]
                  and i not in TIE_INDEXES
                  and not LADDER_AT <= i <= LADDER_AT + len(LADDER_STEPS)
                  and i not in (HALF_GRANT_INDEX, HALF_COMPENSATION_INDEX)]
    used = []

    def take(test=lambda i: True):
        index = next(i for i in candidates if i not in used and test(i))
        used.append(index)
        return events[index - 1]

    def rewrite(record, **fields):
        record.update({"requires": None, "counterparty": None, "unit": "cu",
                       "revision": 1})
        record.update(fields)
        return record

    def normalised(station, quantity, unit="cu"):
        factors = classes[by_station[station]["class"]]
        return half_up(Fraction(quantity * UNIT_SCALES[unit])
                       * Fraction(factors["conversion_num"],
                                  factors["conversion_den"]))

    ceiling_hit = None
    for index in candidates:
        station = events[index - 1]["station"]
        if events[index - 1]["kind"] != "grant" or station not in by_station:
            continue
        factors = classes[by_station[station]["class"]]
        for unit in UNIT_NAMES:
            exact = Fraction(implausible * factors["conversion_den"],
                             UNIT_SCALES[unit] * factors["conversion_num"])
            if exact.denominator == 1:
                ceiling_hit = (index, station, unit, int(exact))
                break
        if ceiling_hit:
            break
    if ceiling_hit is None:
        raise SystemExit("no plain grant can land exactly on the implausible ceiling")
    index, station, unit, quantity = ceiling_hit
    used.append(index)
    rewrite(events[index - 1], kind="grant", station=station, unit=unit,
            quantity=quantity)

    transfer = take(lambda i: events[i - 1]["kind"] == "transfer")
    transfer["counterparty"] = ""

    held_at, held_programme, zero_station = fresh[0], live_programmes[5], fresh[1]
    rewrite(take(), kind="grant", station=held_at, programme=held_programme,
            quantity=25)
    rewrite(take(), kind="grant", station=held_at, programme=live_programmes[6],
            quantity=10,
            requires="allotment_below:" + held_programme + ":" + held_at + ":"
            + str(normalised(held_at, 25)))
    rewrite(take(), kind="grant", station=pool[0], programme=live_programmes[4],
            quantity=12, requires="station_active:" + dormant)
    rewrite(take(), kind="grant", station=pool[1], programme=live_programmes[4],
            quantity=14, requires="no_pending")
    rewrite(take(), kind="grant", station=zero_station,
            programme=live_programmes[7], quantity=30)
    rewrite(take(), kind="retire", station=zero_station,
            programme=live_programmes[8], quantity=30)
    rewrite(take(lambda i: i > HALF_COMPENSATION_INDEX), kind="retire",
            station=HALF_STATION, programme=live_programmes[2],
            quantity=-settlement_floor)
    recalled = take()

    # Each adjacent pair of the screening order needs one record that fails
    # both of its tests, or the order between them decides nothing and a
    # solver that tests them the other way round publishes the same ledger.
    # The pairs the order cannot reach are left alone: a quantity cannot be
    # both non-positive and above the implausible ceiling, and the
    # implausible and compensation codes never fire on one record because one
    # requires a compensating event and the other requires a plain one.
    # The register writers lodge a revision 1 shadow row for every third
    # station and every fourth programme, which puts that key back in force
    # however high its own revision stands. Only the keys without a shadow
    # row are genuinely absent, and only those make the unknown codes fire.
    unseen_stations = [s["station"] for k, s in enumerate(stations)
                       if s["revision"] > frozen and k % 3 != 0]
    unseen_programmes = [p for k, p in enumerate(shut) if k % 4 != 1]

    # A record carries its own revision into the history only when no
    # supplement twin outranks it, and a twin is lodged for every index the
    # journal writer does not skip, at a revision capped to the frozen one.
    def no_twin(index):
        return (index - 1) % 3 == 0 and (index - 1) % 11 != 5

    draft_and_recalled = rewrite(take(no_twin), kind="grant", station=fresh[2],
                                 programme=live_programmes[9], quantity=18,
                                 revision=top)
    recalled_unknown_station = rewrite(
        take(), kind="grant", station=unseen_stations[0],
        programme=live_programmes[9], quantity=19)
    rewrite(take(), kind="grant", station=unseen_stations[1],
            programme=unseen_programmes[0], quantity=20)
    rewrite(take(), kind="grant", station=fresh[3],
            programme=unseen_programmes[1], quantity=0)

    # Two offers that agree on scope, region and normalised quantity, so the
    # canonical position is the level of the directive ladder that separates
    # them. Both wait for the counter the first round moves, so both are
    # admitted in one later round and the queue order reaches the documents.
    for quantum in (21, 21):
        rewrite(take(), kind="grant", station=fresh[4],
                programme=live_programmes[10], quantity=quantum,
                scope="standard",
                requires="counter_at_least:deferred_admitted:1")

    for index in used:
        clean.remove(index)
    return {"ids": {events[i - 1]["event_id"] for i in used},
            "withdrawn_draft": recalled["event_id"],
            "withdrawn_live": [draft_and_recalled["event_id"],
                               recalled_unknown_station["event_id"]]}


def mint(seed):
    """The whole epoch as plain data, before any of it reaches disk."""
    rng = Rng(seed)
    frozen = rng.between(6, 9)
    top = frozen + rng.between(2, 4)
    epoch_id = "EP-" + str(rng.between(2000, 9999))
    live_key = "EPK-" + str(rng.between(1000, 4999))
    dead_key = "EPK-" + str(rng.between(5000, 9999))

    classes = {}
    for name in CLASS_NAMES:
        if name == LADDER_CLASS:
            classes[name] = {"conversion_num": 1, "conversion_den": 1,
                             "reversal_num": 1, "reversal_den": 1,
                             "carry_quantum": 100000}
            continue
        if name == HALF_CLASS:
            classes[name] = {"conversion_num": 1, "conversion_den": 1,
                             "reversal_num": 1, "reversal_den": 2,
                             "carry_quantum": 100000}
            continue
        classes[name] = {
            "conversion_num": rng.pick([3, 5, 7, 9, 11, 13]),
            "conversion_den": rng.pick([1, 2, 4, 5]),
            "reversal_num": rng.pick([1, 3, 5, 7]),
            "reversal_den": rng.pick([1, 2, 4]),
            "carry_quantum": rng.pick([25, 40, 50, 64, 80, 125]),
        }

    implausible = rng.between(180, 320) * 1000
    settlement_floor = -1 * rng.between(4, 12) * 1000
    ceilings = {}
    for revision in range(1, top + 1):
        for name in CLASS_NAMES:
            if name in (LADDER_CLASS, HALF_CLASS):
                ceilings[(revision, name)] = 999999
            else:
                ceilings[(revision, name)] = (
                    rng.between(9, 26) * 1000 + revision * 250)

    stations = []
    for i in range(1, STATION_COUNT + 1):
        sid = "ST-" + str(i).rjust(4, "0")
        fixed = sid in (LADDER_STATION, HALF_STATION)
        klass = CLASS_NAMES[i % 4]
        if sid == LADDER_STATION:
            klass = LADDER_CLASS
        elif sid == HALF_STATION:
            klass = HALF_CLASS
        region = REGIONS[0] if fixed else rng.pick(REGIONS)
        status = "active"
        if i % 17 == 0 and not fixed:
            status = "dormant"
        revision = 1 if fixed else rng.between(1, frozen)
        if i % 29 == 0 and not fixed:
            revision = top
        stations.append({"station": sid, "class": klass, "region": region,
                         "hub": rng.pick(HUBS), "status": status,
                         "revision": revision})
    known = {s["station"] for s in stations if s["revision"] <= frozen}

    programmes = []
    for i in range(1, PROGRAMME_COUNT + 1):
        pid = "PGM-" + str(i).rjust(4, "0")
        revision = rng.between(1, frozen)
        if i % 31 == 0:
            revision = top
        programmes.append({"programme": pid,
                           "category": rng.pick(["core", "guest", "pilot",
                                                 "review"]),
                           "status": "open" if i % 13 else "shut",
                           "revision": revision})
    open_programmes = [p["programme"] for p in programmes
                       if p["revision"] <= frozen]

    live_stations = [s["station"] for s in stations[:72]
                     if s["station"] in known]
    if LADDER_STATION not in live_stations:
        live_stations.append(LADDER_STATION)

    aliases = []
    alias_for = {}
    for i in range(240):
        target = stations[rng.below(STATION_COUNT)]["station"]
        alias = "SITE-" + str(1000 + i)
        revision = rng.between(1, top)
        aliases.append({"alias": alias, "canonical": target, "kind": "station",
                        "in_force_from_revision": revision,
                        "note": "site code carried over from the prior epoch"})
        if revision <= frozen and target in live_stations and target != LADDER_STATION:
            alias_for.setdefault(target, alias)
    for i in range(48):
        target = open_programmes[rng.below(len(open_programmes))]
        aliases.append({"alias": "PROJ-" + str(2000 + i), "canonical": target,
                        "kind": "programme",
                        "in_force_from_revision": rng.between(1, top),
                        "note": "project code carried over from the prior epoch"})

    pool = [s["station"] for s in stations[:96]
            if s["revision"] <= frozen
            and s["station"] not in (LADDER_STATION, HALF_STATION)]
    absent = [s["station"] for s in stations if s["revision"] > frozen]
    shut = [p["programme"] for p in programmes if p["revision"] > frozen]
    live_programmes = open_programmes[:120]

    events = []
    sequence = 0
    stamp = 1755000000

    def add(kind, station, programme, quantity, unit, extra=None):
        nonlocal sequence, stamp
        index = len(events) + 1
        sequence += 1 if index % 7 else 0
        stamp += rng.between(11, 400)
        rec = {
            "event_id": "EVT-" + str(index).rjust(6, "0"),
            "sequence": sequence,
            "stamp": stamp,
            "kind": kind,
            "station": station,
            "programme": programme,
            "counterparty": None,
            "quantity": quantity,
            "unit": unit,
            "tiebreak": "TB-" + str(rng.between(100, 999)),
            "scope": "mandatory" if index % 11 == 0 else "standard",
            "requires": None,
            "depends_on": [],
            "revision": rng.between(1, frozen),
            "source": "journal",
        }
        if extra:
            rec.update(extra)
        events.append(rec)
        return rec

    ladder_at = LADDER_AT
    ladder_span = range(ladder_at, ladder_at + len(LADDER_STEPS) + 1)
    clean = []
    for index in range(1, EVENT_COUNT + 1):
        if index == HALF_GRANT_INDEX:
            add("grant", HALF_STATION, live_programmes[2], HALF_QUANTITY, "cu",
                {"scope": "standard", "revision": 1})
            continue
        if index in ladder_span:
            if index == ladder_at + len(LADDER_STEPS):
                add("grant", LADDER_STATION, live_programmes[0], LADDER_BASE,
                    "cu", {"scope": "standard", "revision": 1})
            else:
                step = LADDER_STEPS[index - ladder_at]
                add("grant", LADDER_STATION, live_programmes[1], step[0], "cu",
                    {"scope": "standard", "revision": 1,
                     "requires": "balance_at_least:" + LADDER_STATION + ":"
                                 + str(step[1])})
            continue

        station = pool[(index * 13) % len(pool)]
        programme = live_programmes[(index * 7) % len(live_programmes)]
        unit = ["cu", "dcu", "shift", "halfshift"][index % 4]
        quantity = rng.between(6, 70)
        extra = {}
        kind = "grant"
        if index % 9 == 4:
            kind = "compensate"
            quantity = 0
            unit = "cu"
        elif index % 5 == 2:
            kind = "retire"
        elif index % 5 == 3:
            kind = "transfer"
            other = pool[(index * 29 + 5) % len(pool)]
            if other == station:
                other = pool[(index * 29 + 6) % len(pool)]
            extra["counterparty"] = other

        flawed = False
        if index % 31 == 0:
            extra["revision"] = top
            flawed = True
        if index % 37 == 0 and kind != "compensate":
            quantity = 0
            flawed = True
        if index % 41 == 0 and kind != "compensate":
            unit = "block"
            quantity = 200
            flawed = True
        if index % 43 == 0:
            extra["station"] = absent[(index * 3) % len(absent)]
            flawed = True
        if index % 47 == 0 and kind != "compensate":
            extra["programme"] = shut[(index * 5) % len(shut)]
            flawed = True
        if index % 29 == 5:
            flawed = True
        if index % 17 == 3 and kind != "compensate":
            extra["requires"] = "counter_at_least:grants:" + str(
                40 + (index % 9) * 6)
            flawed = True
        if index % 53 == 0 and kind != "compensate":
            extra["requires"] = "hub_open:" + rng.pick(HUBS)
            flawed = True
        if (index % 3 == 1 and not flawed and kind != "compensate"
                and station in alias_for):
            extra["station"] = alias_for[station]
        add(kind, station, programme, quantity, unit, extra)
        if not flawed and kind != "compensate":
            clean.append(index)

    by_index = {rec["event_id"]: rec for rec in events}
    for offset in (11, 40, 77, 133, 190, 233, 261):
        base = events[offset]["sequence"]
        for step in range(4):
            events[offset + step]["sequence"] = base
    for offset in (58, 145, 212):
        base_stamp = events[offset]["stamp"]
        for step in range(3):
            events[offset + step]["stamp"] = base_stamp
    for offset in (95, 178):
        events[offset + 1]["sequence"] = events[offset]["sequence"]
        events[offset + 1]["stamp"] = events[offset]["stamp"]
        events[offset + 1]["kind"] = events[offset]["kind"]
        events[offset + 1]["tiebreak"] = events[offset]["tiebreak"]

    def eid(index):
        return "EVT-" + str(index).rjust(6, "0")

    # The epochs minted for grading carry the branches and boundaries the
    # shipped epoch never reaches, so every stated rule has an input that
    # comes out differently when the rule is broken.
    extended = seed != SAMPLE_SEED
    shared = plant_shared_fixtures(events, stations, classes, clean,
                                   live_programmes, pool, frozen)
    fixtures = {"ids": set()}
    if extended:
        events[96]["tiebreak"] = "TB-000"
        fixtures = plant_minted_fixtures(events, stations, classes, clean,
                                         live_programmes, pool, frozen,
                                         implausible, settlement_floor,
                                         absent, shut, top)

    withdrawn = []
    for index in range(1, EVENT_COUNT + 1):
        if index in ladder_span or index % 29 != 5:
            continue
        withdrawn.append({"event_id": eid(index),
                          "withdrawn_at_revision": frozen,
                          "reason": rng.pick(["desk recall", "duplicate lodge",
                                              "operator error",
                                              "programme closed"])})
    if extended:
        withdrawn.append({"event_id": fixtures["withdrawn_draft"],
                          "withdrawn_at_revision": top,
                          "reason": "recall lodged for a later epoch"})
        for event_id in fixtures["withdrawn_live"]:
            withdrawn.append({"event_id": event_id,
                              "withdrawn_at_revision": frozen,
                              "reason": "desk recall"})
    for i in range(len(withdrawn), 204):
        withdrawn.append({"event_id": "EVT-9" + str(700000 + i),
                          "withdrawn_at_revision": top,
                          "reason": "lodged for a later epoch"})

    comp_indexes = [i for i in range(1, EVENT_COUNT + 1)
                    if i not in ladder_span and i % 9 == 4]
    target_pool = [i for i in clean
                   if i < EVENT_COUNT - 10 and i != HALF_GRANT_INDEX]
    links = []
    duplicates = 0
    for slot, index in enumerate(comp_indexes):
        status = "registered"
        target = None
        earlier = [c for c in target_pool if c < index - 10]
        if index == HALF_COMPENSATION_INDEX:
            target = eid(HALF_GRANT_INDEX)
        elif slot % 11 == 3:
            status = "withdrawn"
            target = eid(earlier[slot % len(earlier)]) if earlier else eid(1)
        elif slot % 17 == 7:
            target = "EVT-77" + str(1000 + slot)
        elif slot % 7 == 5 and links and duplicates < 6:
            target = links[-1]["target_event_id"]
            duplicates += 1
        elif earlier:
            target = eid(earlier[(slot * 5 + 2) % len(earlier)])
        else:
            target = eid(1)
        links.append({"compensation_id": eid(index),
                      "target_event_id": target, "status": status,
                      "revision": rng.between(1, frozen),
                      "note": "link lodged by the custody desk"})
    if extended:
        live_links = [k for k, link in enumerate(links)
                      if link["status"] == "registered"
                      and link["target_event_id"] in {eid(i) for i in clean}]
        slot = live_links[len(live_links) // 2]
        links[slot]["revision"] = frozen
        links.insert(slot, {"compensation_id": links[slot]["compensation_id"],
                            "target_event_id": eid(1), "status": "registered",
                            "revision": 1,
                            "note": "earlier lodge of the same link"})
    if extended:
        slot = next(k for k, link in enumerate(links)
                    if link["status"] == "registered"
                    and link["target_event_id"].startswith("EVT-0")
                    and 100 < int(link["compensation_id"][4:]) < 230
                    and all(int(link["compensation_id"][4:]) % m != r
                            for m, r in ((31, 0), (43, 0), (29, 5))))
        links[slot]["revision"] = frozen
        fixtures["ids"].add(links[slot]["compensation_id"])
        links.insert(slot, {"compensation_id": links[slot]["compensation_id"],
                            "target_event_id": eid(1), "status": "registered",
                            "revision": 1,
                            "note": "earlier lodge of the same link"})
    if extended:
        # The last adjacent pair of the screening order: a compensation whose
        # in force link is withdrawn AND names a target the history does not
        # carry, so the two compensation codes both hold and only their order
        # decides which one the ledger records.
        slot = next(k for k, link in enumerate(links)
                    if link["status"] == "withdrawn"
                    and link["compensation_id"].startswith("EVT-0")
                    and all(int(link["compensation_id"][4:]) % m != r
                            for m, r in ((31, 0), (43, 0), (29, 5))))
        links[slot]["target_event_id"] = "EVT-66" + str(1000 + slot)
        links[slot]["note"] = "link withdrawn against a target lodged elsewhere"
    for compensation_id, target in shared["links"].items():
        lodged = [link for link in links if link["compensation_id"] == compensation_id]
        latest = max(link["revision"] for link in lodged)
        [link for link in lodged if link["revision"] == latest][-1].update(
            {"target_event_id": target, "status": "registered"})
    for i in range(len(links), 206):
        links.append({"compensation_id": "CMP-RSV-" + str(i).rjust(4, "0"),
                      "target_event_id": eid(1), "status": "withdrawn",
                      "revision": top, "note": "reserved link"})

    edges = []
    plain = [i for i in range(1, EVENT_COUNT + 1) if i not in ladder_span]
    for index in plain:
        if index <= 14 or index % 2 == 0:
            continue
        stale = index - 5 - (index % 4)
        if stale < 1 or stale in ladder_span:
            continue
        carried = [eid(stale)]
        if index % 9 == 1 and index + 6 <= EVENT_COUNT:
            carried.append(eid(index + 6))
        events[index - 1]["depends_on"] = carried
    for slot, index in enumerate(plain):
        if index <= 12 or slot % 2:
            continue
        back = index - 8 - (slot % 5) * 3
        if back < 1 or back in ladder_span:
            continue
        edges.append({"event_id": eid(index), "depends_on": eid(back),
                      "edge_kind": "requires",
                      "revision": rng.between(1, frozen)})
    for slot in range(10):
        index = plain[(slot * 23 + 9) % len(plain)]
        ahead = index + 9
        if ahead > EVENT_COUNT or index in ladder_span or ahead in ladder_span:
            continue
        edges.append({"event_id": eid(index), "depends_on": eid(ahead),
                      "edge_kind": "requires", "revision": 1})
    for slot in range(6):
        index = plain[(slot * 31 + 17) % len(plain)]
        edges.append({"event_id": eid(index),
                      "depends_on": "EVT-88" + str(1000 + slot),
                      "edge_kind": "requires", "revision": 1})
    edges.append({"event_id": eid(171), "depends_on": eid(171),
                  "edge_kind": "requires", "revision": 1})
    edges.append({"event_id": eid(203), "depends_on": eid(215),
                  "edge_kind": "requires", "revision": 1})
    edges.append({"event_id": eid(215), "depends_on": eid(226),
                  "edge_kind": "requires", "revision": 1})
    edges.append({"event_id": eid(226), "depends_on": eid(203),
                  "edge_kind": "requires", "revision": 1})
    for slot in range(60):
        index = plain[(slot * 23 + 3) % len(plain)]
        other = plain[(slot * 11 + 2) % len(plain)]
        edges.append({"event_id": eid(index), "depends_on": eid(other),
                      "edge_kind": "advisory", "revision": rng.between(1, top)})
    for slot in range(40):
        index = plain[(slot * 19 + 7) % len(plain)]
        other = plain[(slot * 31 + 13) % len(plain)]
        edges.append({"event_id": eid(index), "depends_on": eid(other),
                      "edge_kind": "requires", "revision": top})
    if extended:
        edges = [e for e in edges if e["event_id"] not in fixtures["ids"]]
    ring = {name for pair in shared["cycle"] for name in pair}
    edges = [e for e in edges if e["event_id"] not in shared["ids"]
             and e["depends_on"] not in ring]
    for event_id, named in shared["cycle"]:
        edges.append({"event_id": event_id, "depends_on": named,
                      "edge_kind": "requires", "revision": 1})

    return {
        "seed": seed, "frozen": frozen, "top": top, "epoch_id": epoch_id,
        "live_key": live_key, "dead_key": dead_key, "classes": classes,
        "ceilings": ceilings, "stations": stations, "programmes": programmes,
        "aliases": aliases, "events": events, "links": links, "edges": edges,
        "withdrawn": withdrawn, "rng": rng, "known": known,
        "implausible": implausible, "settlement_floor": settlement_floor,
        "open_programmes": open_programmes, "live_stations": pool,
        "extended": extended,
        "fixture_ids": fixtures["ids"] | shared["ids"],
        "counter_fixtures": shared["counters"],
        "ledger_anchor": shared["ledger_anchor"],
        "usable": MINTED_USABLE.get(seed, SHIPPED_USABLE),
        "round_ceiling": MINTED_ROUND_CEILING.get(seed, ROUND_CEILING),
        "probe": MINTED_PROBE.get(seed, PROBE_POSITION),
    }


REASON_CATALOGUE = [("EVT-DRAFTREVISION", "r01", "the record lodges above the frozen register revision"),
                    ("EVT-WITHDRAWN", "r01", "the identifier sits in the withdrawn journal"),
                    ("EVT-UNKNOWNSTATION", "r02", "the station is absent from the frozen register"),
                    ("EVT-UNKNOWNPROGRAMME", "r02", "the programme is absent from the register"),
                    ("EVT-NONPOSITIVE", "r01", "the normalised quantity is zero or below"),
                    ("EVT-IMPLAUSIBLE", "r01", "the normalised quantity passes the memo ceiling"),
                    ("CMP-WITHDRAWN", "r09", "the compensation link is absent or withdrawn"),
                    ("CMP-NOTARGET", "r09", "the named target sits outside the canonical history"),
                    ("DEP-SELF", "r07", "the record names itself as a dependency"),
                    ("DEP-CYCLE", "r07", "the record sits on a dependency cycle"),
                    ("DEP-MISSING", "r07", "a dependency is neither in the checkpoint nor earlier in the window")]

# A minted epoch words every reason afresh, in the catalogue and the glossary
# alike, so a package that carries the shipped catalogue inside it rather
# than reading the paper it is pointed at publishes the wrong register.
MINTED_REASON_MEANINGS = {
    "EVT-DRAFTREVISION": "the record was lodged at a revision past the frozen register",
    "EVT-WITHDRAWN": "the withdrawn journal names the identifier",
    "EVT-UNKNOWNSTATION": "the frozen register carries no row for the station",
    "EVT-UNKNOWNPROGRAMME": "the programme register carries no row for the programme",
    "EVT-NONPOSITIVE": "the quantity normalises to zero or less",
    "EVT-IMPLAUSIBLE": "the quantity normalises past the implausible ceiling",
    "CMP-WITHDRAWN": "no registered link in force names the compensation",
    "CMP-NOTARGET": "the target is absent from the canonical history",
    "DEP-SELF": "the record lists itself among its dependencies",
    "DEP-CYCLE": "a dependency path leads back to the record",
    "DEP-MISSING": "a dependency lies neither behind the window nor earlier in it",
}


def reason_catalogue(E):
    """The reason codes of one epoch with the stage and meaning of each."""
    if not E["extended"]:
        return list(REASON_CATALOGUE)
    return [(code, stage, MINTED_REASON_MEANINGS[code])
            for code, stage, _meaning in REASON_CATALOGUE]


def write_tables(dest, E):
    """The registers, journals and policy papers of one epoch."""
    rng = E["rng"]
    frozen = E["frozen"]
    top = E["top"]
    events = E["events"]

    write_json(dest / "epoch_header.json", {
        "epoch_id": E["epoch_id"],
        "frozen_register_revision": frozen,
        "highest_lodged_revision": top,
        "workbook_epoch_key": E["live_key"],
        "replay_start_position": 1,
        "replay_end_position": END_POSITION,
        "bounded_start_position": BOUNDED_START,
        "bounded_end_position": BOUNDED_END,
        "state_probe_position": E["probe"],
        "lodged_event_records": len(events),
    })

    lines = ["[units]"]
    for name in UNIT_NAMES:
        lines.append(name + " = " + str(UNIT_SCALES[name]))
    lines.append("")
    lines.append("[notes]")
    lines.append("basis = " + Q + "cu" + Q)
    lines.append("retired_symbol = " + Q + "quarter" + Q)
    write_lines(dest / "unit_registry.toml", lines)

    conf = ["# roster of reporting regions and the rank each one takes in the",
            "# re offer ladder. lower rank is offered first.", "",
            "[region_rank]"]
    for i, name in enumerate(REGIONS, start=1):
        conf.append(name + " = " + str(i))
    conf.append("")
    conf.append("[roster]")
    for i, station in enumerate(E["stations"][:120]):
        conf.append(station["station"] + " = " + station["region"])
    write_lines(dest / "reporting_station_roster.conf", conf)

    policy = ["screen_order:",
              "  order: [" + ", ".join(Q + c + Q for c in QUARANTINE_ORDER)
              + "]",
              "predicate_basis:",
              "  evaluated_against: " + Q + "state immediately before offer" + Q,
              "  unknown_form: " + Q + "false" + Q,
              "rounds:",
              "  ceiling_source: " + Q + "custody_board_memo.pdf" + Q,
              "  admitted_counter: " + Q + "deferred_admitted" + Q,
              "  stop_rule: " + Q + "a round that admits nothing ends the run" + Q]
    write_lines(dest / "eligibility_policy.yaml", policy)

    write_lines(dest / "rounding_and_arithmetic_policy.yaml", [
        "arithmetic:",
        "  basis: " + Q + "exact rational" + Q,
        "  binary_floating_point: " + Q + "forbidden" + Q,
        "  rounding: " + Q + "half away from zero" + Q,
        "  negative_zero: " + Q + "forbidden" + Q,
        "ratio:",
        "  places: 12",
        "  zero_denominator: " + Q + "publish an exact zero" + Q,
        "placement:",
        "  r01: " + Q + "once after the class conversion" + Q,
        "  r10: " + Q + "once on the derived reversal" + Q,
        "  elsewhere: " + Q + "no rounding" + Q,
    ])

    comp = ["# how a compensating event reverses the event it names.", "",
            "[reversal_counter_map]",
            "grant = " + Q + "granted_cu" + Q,
            "retire = " + Q + "retired_cu" + Q,
            "transfer = " + Q + "transferred_cu" + Q,
            "", "[dispositions]",
            "applied = " + Q + "the target effect came off exactly once" + Q,
            "void_duplicate = " + Q + "a later compensation names an already reversed target" + Q,
            "void_unapplied = " + Q + "the named target never took effect in this run" + Q,
            "", "[counters]",
            "void_rows_move_no_counter = true",
            "reversed_counter = " + Q + "reversed_cu" + Q,
            "compensation_counter = " + Q + "compensations" + Q]
    write_lines(dest / "compensation_policy.toml", comp)

    write_lines(dest / "publication_form_rules.toml", [
        "# the shape every published document takes.", "",
        "[core_digest]",
        "documents = [" + ", ".join(Q + n + Q for n in CORE_DOCUMENTS) + "]",
        "", "[publication_digest]",
        "excludes = [" + Q + "package.zip" + Q + ", " + Q + "run_manifest.txt"
        + Q + "]",
        "order = " + Q + "file name ascending" + Q,
        "", "[ratio]",
        "places = 12",
    ])

    write_lines(dest / "package_expectations.toml", [
        "# the shape the delivered archive has to carry.", "",
        "[archive]",
        "root_files = [" + Q + "pyproject.toml" + Q + "]",
        "source_root = " + Q + "src/" + PACKAGE_NAME + Q,
        "tests_root = " + Q + "tests" + Q,
        "", "[modules]",
        "names = [" + ", ".join(Q + m + Q for m in PACKAGE_MODULES) + "]",
        "", "[runtime]",
        "python_series = " + Q + "3.12" + Q,
        "third_party_imports = 0",
        "entry_point = " + Q + PACKAGE_NAME + ".__main__" + Q,
    ])

    write_lines(dest / "revision_precedence.toml", [
        "# which paper governs when two papers disagree.", "",
        "[registers]",
        "stations = " + Q + "station_register_frozen.csv" + Q,
        "stations_superseded = " + Q + "station_register_current.csv" + Q,
        "scope = " + Q + "topology_and_scope.xml" + Q,
        "scope_superseded = " + Q + "topology_drafts.xml" + Q,
        "scales = " + Q + "custody_parameter_workbook.xlsx" + Q,
        "scales_superseded = " + Q + "legacy_scale_table.csv" + Q,
        "dependency_edges = " + Q + "dependency_edges.psv" + Q,
        "dependency_edges_superseded = " + Q + "the depends_on list inside each journal record" + Q,
        "", "[rule]",
        "in_force = " + Q + "a row whose revision exceeds the frozen register revision is a draft" + Q,
        "tie = " + Q + "greatest revision at or below the frozen register revision" + Q,
        "workbook_sheet = " + Q + "the sheet whose epoch key cell equals the header epoch key" + Q,
    ])

    header = ["station", "class", "region", "hub", "status", "revision"]
    frozen_rows = []
    for i, s in enumerate(E["stations"]):
        if s["revision"] >= 2 and i % 3 == 0:
            frozen_rows.append([s["station"],
                                CLASS_NAMES[(CLASS_NAMES.index(s["class"]) + 2) % 4],
                                REGIONS[(REGIONS.index(s["region"]) + 2) % len(REGIONS)],
                                s["hub"], "dormant", 1])
        frozen_rows.append([s["station"], s["class"], s["region"], s["hub"],
                            s["status"], s["revision"]])
    write_delim(dest / "station_register_frozen.csv", header, frozen_rows, ",")
    drift = []
    for i, s in enumerate(E["stations"]):
        klass = s["class"]
        if s["station"] != LADDER_STATION and i % 3 == 1:
            klass = CLASS_NAMES[(CLASS_NAMES.index(klass) + 1) % 4]
        region = REGIONS[(REGIONS.index(s["region"]) + 1) % len(REGIONS)]
        drift.append([s["station"], klass, region, s["hub"], s["status"],
                      min(s["revision"], frozen)])
    for i, s in enumerate(E["stations"]):
        if i % 4:
            continue
        drift.append([s["station"], CLASS_NAMES[(i + 2) % 4],
                      REGIONS[(i + 3) % len(REGIONS)], s["hub"],
                      "dormant" if i % 8 else "active", top])
    write_delim(dest / "station_register_current.csv", header, drift, ",")

    programme_rows = []
    for i, prog in enumerate(E["programmes"]):
        if prog["revision"] >= 2 and i % 4 == 1:
            programme_rows.append([prog["programme"], "withdrawn", "shut", 1])
        programme_rows.append([prog["programme"], prog["category"],
                               prog["status"], prog["revision"]])
    write_delim(dest / "programme_register.csv",
                ["programme", "category", "status", "revision"],
                programme_rows, ",")

    alias_rows = []
    for i, a in enumerate(E["aliases"]):
        if a["in_force_from_revision"] >= 2 and i % 5 == 2:
            alias_rows.append([a["alias"],
                               E["stations"][(i * 7) % len(E["stations"])]["station"]
                               if a["kind"] == "station"
                               else E["programmes"][(i * 3) % len(E["programmes"])]["programme"],
                               a["kind"], 1,
                               "earlier lodge of the same code"])
        alias_rows.append([a["alias"], a["canonical"], a["kind"],
                           a["in_force_from_revision"], a["note"]])
    write_delim(dest / "alias_crosswalk.tsv",
                ["alias", "canonical", "kind", "in_force_from_revision", "note"],
                alias_rows, TAB)

    ranks = []
    for revision in range(1, top + 1):
        for kind, rank in [("compensate", 1), ("retire", 2), ("transfer", 3),
                           ("grant", 4)]:
            ranks.append([kind, rank, revision,
                          "rank in force from revision " + str(revision)])
    for i in range(len(ranks), 208):
        ranks.append(["reserved" + str(i), 9, top,
                      "kind held for a later epoch"])
    write_delim(dest / "event_kind_ranks.csv",
                ["kind", "rank", "revision", "note"], ranks, ",")

    forms = [["balance_at_least", "balance_at_least:station:amount_cu", 2,
              "active", "the station balance stands at or above the amount"],
             ["allotment_below", "allotment_below:station:programme:amount_cu",
              3, "active",
              "the station programme allotment stands below the amount"],
             ["counter_at_least", "counter_at_least:counter:amount", 2,
              "active", "the named derived counter stands at or above the amount"],
             ["no_pending", "no_pending", 0, "active",
              "no event is waiting in the pending queue"],
             ["station_active", "station_active:station", 1, "active",
              "the frozen register carries the station as active"],
             ["hub_open", "hub_open:hub", 1, "retired",
              "withdrawn at the close of the prior epoch"]]
    # allotment_below names the programme first from revision 6; no_pending is
    # retired at revision 7, and a minted epoch restores it at its frozen
    # revision and drafts the earlier argument order above it.
    pred_rows = []
    for revision in range(1, top + 1):
        for form in forms:
            name, shape, count, status, meaning = form
            if name == "allotment_below" and revision >= 6 and not (
                    E["extended"] and revision > frozen):
                shape = "allotment_below:programme:station:amount_cu"
                meaning = "the allotment the station holds under the programme stands below the amount"
            if name == "no_pending" and revision >= 7 and not (
                    E["extended"] and revision >= frozen):
                status = "retired"
                meaning = "retired at the seventh sitting"
            pred_rows.append([name, shape, count, status, revision, meaning])
    for i in range(len(pred_rows), 210):
        pred_rows.append(["reserved_" + str(i), "reserved", 0, "retired", top,
                          "held for a later epoch"])
    write_delim(dest / "eligibility_predicates.csv",
                ["predicate_id", "form", "argument_count", "status",
                 "revision", "description"], pred_rows, ",")

    reasons = reason_catalogue(E)

    cat_rows = []
    for revision in range(1, top + 1):
        for code, stage, meaning in reasons:
            cat_rows.append([code, stage, meaning, revision])
    for i in range(len(cat_rows), 212):
        cat_rows.append(["RSV-" + str(i).rjust(4, "0"), "r14",
                         "reserved for a later epoch", top])
    write_delim(dest / "quarantine_reason_catalogue.psv",
                ["code", "stage", "meaning", "revision"], cat_rows, PIPE)

    ceil_rows = []
    for revision in range(1, top + 1):
        for name in CLASS_NAMES:
            row = [revision, name, E["ceilings"][(revision, name)],
                   "carried from the workbook of that revision"]
            ceil_rows.append(row)
            if revision == 1 and name in (CLASS_NAMES[0], CLASS_NAMES[3]):
                ceil_rows.append(list(row))
    for i in range(len(ceil_rows), 204):
        ceil_rows.append([top, "RSV" + str(i), 0, "reserved"])
    write_delim(dest / "allotment_ceiling_history.tsv",
                ["revision", "class", "ceiling_cu", "note"], ceil_rows, TAB)

    src_rows = [["journal", 2, 1, "the desk journal as first lodged"],
                ["supplement", 1 if E["extended"] else 4, 1,
                 "late lodges taken at the counter"],
                ["supplement", 5, frozen, "counter lodges raised above the journal"],
                ["archive", 1, 1, "prior epoch carry over"]]
    for i in range(len(src_rows), 206):
        src_rows.append(["feed_" + str(i).rjust(3, "0"), (i % 3) + 1, top,
                         "feed held for a later epoch"])
    write_delim(dest / "source_priority_register.csv",
                ["source", "priority", "revision", "note"], src_rows, ",")

    legacy = []
    for name in CLASS_NAMES:
        legacy.append([name, E["classes"][name]["conversion_num"] + 2,
                       max(1, E["classes"][name]["conversion_den"]),
                       E["classes"][name]["carry_quantum"] + 5,
                       "superseded at the close of the prior epoch"])
    for i in range(len(legacy), 202):
        legacy.append(["CL" + str(i).rjust(3, "0"), (i % 7) + 1, (i % 3) + 1,
                       25 * ((i % 5) + 1), "superseded scale row"])
    write_delim(dest / "legacy_scale_table.csv",
                ["class", "conversion_num", "conversion_den", "carry_quantum",
                 "note"], legacy, ",")

    write_delim(dest / "withdrawn_event_journal.tsv",
                ["event_id", "withdrawn_at_revision", "reason"],
                [[w["event_id"], w["withdrawn_at_revision"], w["reason"]]
                 for w in E["withdrawn"]], TAB)

    write_delim(dest / "dependency_edges.psv",
                ["event_id", "depends_on", "edge_kind", "revision"],
                [[e["event_id"], e["depends_on"], e["edge_kind"], e["revision"]]
                 for e in E["edges"]], PIPE)

    write_delim(dest / "compensation_links.csv",
                ["compensation_id", "target_event_id", "status", "revision",
                 "note"],
                [[l["compensation_id"], l["target_event_id"], l["status"],
                  l["revision"], l["note"]] for l in E["links"]], ",")

    write_journals(dest, E)

    scope_lines = [XMLDECL, "<scope epoch=" + _q(E["epoch_id"]) + ">"]
    draft_lines = [XMLDECL, "<scope epoch=" + _q(E["epoch_id"]) + ">"]
    for s in E["stations"]:
        scope_lines.append("  <station id=" + _q(s["station"]) + " region="
                           + _q(s["region"]) + " hub=" + _q(s["hub"])
                           + " revision=" + _q(min(s["revision"], frozen))
                           + "/>")
        draft_lines.append("  <station id=" + _q(s["station"]) + " region="
                           + _q(REGIONS[(REGIONS.index(s["region"]) + 1)
                                        % len(REGIONS)])
                           + " hub=" + _q(s["hub"]) + " revision="
                           + _q(top) + "/>")
    scope_lines.append("</scope>")
    draft_lines.append("</scope>")
    write_lines(dest / "topology_and_scope.xml", scope_lines)
    write_lines(dest / "topology_drafts.xml", draft_lines)


def write_journals(dest, E):
    """The journal, the supplement and the provenance ledger. A minted epoch
    also lodges supplement rows for a later epoch."""
    frozen = E["frozen"]
    events = E["events"]
    journal = []
    supplement = []
    provenance = []
    dup_at = None
    if E["extended"]:
        dup_at = next(i for i in range(100, 200)
                      if i % 3 and i % 9 != 2 and (i + 1) % 31
                      and events[i]["event_id"] not in E["fixture_ids"])
    for i, rec in enumerate(events):
        row = dict(rec)
        if (i % 3 or i % 11 == 5) and i > 2:
            twin = dict(row)
            twin["source"] = "supplement"
            twin["revision"] = min(frozen, int(row["revision"]) + 1)
            if i % 9 == 2:
                twin["source"] = ""
            if i % 13 == 6:
                twin["tiebreak"] = "TB-000"
            if i == dup_at:
                early = dict(twin, revision=1, tiebreak="TB-001")
                supplement.append(early)
                provenance.append([row["event_id"], "event_supplement.ndjson",
                                   len(supplement), "supplement", 1])
            supplement.append(twin)
            provenance.append([row["event_id"], "event_supplement.ndjson",
                               len(supplement), "supplement",
                               twin["revision"]])
        journal.append(row)
        provenance.append([row["event_id"], "event_journal.jsonl",
                           len(journal), "journal", row["revision"]])
    if E["extended"]:
        # Lodged for a later epoch under the prefix data_lineage.md names,
        # between canonical events, and under identifiers dependency edges
        # already name.
        for k, event_id in enumerate(LATER_EPOCH_IDS):
            after = events[30 + 70 * k]
            supplement.append({
                "event_id": event_id, "sequence": after["sequence"],
                "stamp": after["stamp"] + 1, "kind": "grant",
                "station": E["live_stations"][k],
                "programme": E["open_programmes"][k], "counterparty": None,
                "quantity": 20 + k, "unit": "cu", "tiebreak": "TB-" + str(810 + k),
                "scope": "standard", "requires": None, "depends_on": [],
                "revision": min(frozen, 2), "source": "supplement"})
            provenance.append([event_id, "event_supplement.ndjson",
                               len(supplement), "supplement", min(frozen, 2)])
    write_jsonl(dest / "event_journal.jsonl", journal)
    write_jsonl(dest / "event_supplement.ndjson", supplement)
    write_delim(dest / "row_provenance_ledger.csv",
                ["record_id", "file", "line", "source", "lodged_revision"],
                provenance, ",")


STAGE_TITLES = [
    ("r01", "unit_normalisation", "Unit normalisation and parameter layers"),
    ("r02", "identifier_resolution", "Identifier resolution and registers"),
    ("r03", "canonical_order", "Canonical event order"),
    ("r04", "checkpoint_selection", "Checkpoint selection"),
    ("r05", "checkpoint_restoration", "Checkpoint restoration"),
    ("r06", "replay_window", "Replay window construction"),
    ("r07", "dependency_closure", "Dependency closure"),
    ("r08", "state_transitions", "Ordinary state transitions"),
    ("r09", "compensation_targets", "Compensating event targets"),
    ("r10", "compensation_effects", "Compensation effects"),
    ("r11", "carry_settlement", "Carry settlement"),
    ("r12", "eligibility_rounds", "State dependent eligibility"),
    ("r13", "materialisation", "Materialisation and the derived index"),
    ("r14", "publication", "Publication, serialisation and digests"),
]


def write_papers(dest, E):
    """The contract, the stage papers, the policy notes and the reading guide."""
    write_lines(dest / "00_open_this_first.txt", [
        "READ THIS BEFORE ANYTHING ELSE",
        "",
        "This directory holds the working papers of one observation epoch of",
        "the beamtime custody ledger, together with the package the facility",
        "currently runs over them. The published epoch was withdrawn because",
        "the numbers came out wrong. The papers themselves are sound.",
        "",
        "custody_program_contract.md names the fourteen stages and the paper",
        "that specifies each one. data_lineage.md maps every paper to the",
        "stage it serves and names the papers that govern nothing.",
        "readings_not_in_force.md lists readings of these papers this facility",
        "does not support, each beside the reading in force.",
        "",
        "Three papers are not plain text and carry values that appear in no",
        "other file. custody_parameter_workbook.xlsx holds the class",
        "conversion factors, the class reversal scales, the class carry",
        "quanta and the per revision allotment ceilings, across two sheets of",
        "which exactly one is in force. custody_board_memo.pdf holds the",
        "revalidation round ceiling, the implausible quantity ceiling and the",
        "settlement floor. precedence_directive.docx holds the five level",
        "re offer ladder, the duplicate target rule and the dependency",
        "closure rule. Open all three.",
        "",
        "The file names describe a role, not the contents. Open a paper",
        "before deciding what it holds.",
        "",
        "This epoch is one acquisition profile. It does not reach every",
        "documented branch. Implement each quiet branch from its stage paper",
        "rather than from what this epoch happens to exercise.",
    ])

    write_lines(dest / "custody_program_contract.md", [
        "# Custody replay contract",
        "",
        "The engine reconstructs the credit state of one observation epoch",
        "from an append only event journal, a sealed checkpoint and the",
        "registers that govern them. Every quantity it publishes is an exact",
        "integer in credit units, written `cu`. Every ratio it publishes",
        "carries exactly twelve decimal places.",
        "",
        "## Stages",
        "",
        "| stage | subject | paper |",
        "| --- | --- | --- |",
    ] + [
        "| " + sid + " | " + title + " | `spec_stage_" + sid + "_" + slug
        + ".md` |" for sid, slug, title in STAGE_TITLES
    ] + [
        "",
        "## Entry points",
        "",
        "The same replay machinery serves every published document. A replay",
        "runs over a half open range of canonical positions, optionally on",
        "top of a restored checkpoint. The epoch header names four ranges:",
        "the publication range, the bounded range, the probe position and",
        "the from scratch comparison range, which always opens at position",
        "one.",
        "",
        "## Invariants",
        "",
        "A replay that starts from a restored checkpoint and a replay that",
        "starts from scratch over the same end boundary reach the same state,",
        "byte for byte, because the checkpoint body carries the whole state,",
        "the pending queue and the applied and reversed ledgers included.",
        "",
        "Replaying the same directory twice produces the same bytes. Running",
        "the engine over the same epoch under another directory name produces",
        "them again. The paper directory is never written to.",
        "",
        "No published quantity comes from binary floating point. Rounding",
        "happens where a stage paper places it and nowhere else, and it is",
        "always half away from zero on an exact rational.",
    ])

    write_lines(dest / "data_lineage.md", [
        "# Paper lineage",
        "",
        "| paper | stage | what it settles |",
        "| --- | --- | --- |",
        "| `epoch_header.json` | r01 r04 r06 | the frozen revision, the workbook epoch key and the four ranges |",
        "| `custody_parameter_workbook.xlsx` | r01 r10 r11 | conversion factors, reversal scales, carry quanta, ceilings |",
        "| `custody_board_memo.pdf` | r01 r11 r12 | round ceiling, implausible ceiling, settlement floor |",
        "| `precedence_directive.docx` | r07 r10 r12 | the re offer ladder and the two closure rules |",
        "| `unit_registry.toml` | r01 | the scale of each recorded unit symbol |",
        "| `station_register_frozen.csv` | r02 r10 | the station class, region, hub and status in force |",
        "| `programme_register.csv` | r02 | the programmes in force |",
        "| `alias_crosswalk.tsv` | r02 | site and project codes carried over from earlier epochs |",
        "| `topology_and_scope.xml` | r13 | the region and hub each station reports under |",
        "| `event_journal.jsonl` | r03 | the desk journal as first lodged |",
        "| `event_supplement.ndjson` | r03 | late lodges taken at the counter |",
        "| `source_priority_register.csv` | r03 | which lodging source outranks which |",
        "| `row_provenance_ledger.csv` | r03 | the lodging source of a record that carries none |",
        "| `event_kind_ranks.csv` | r03 | the rank each kind takes in the canonical order |",
        "| `withdrawn_event_journal.tsv` | r01 | identifiers the desk has recalled |",
        "| `checkpoint_register.csv` | r04 | the status, digest and revision of each checkpoint |",
        "| `checkpoint_states.jsonl` | r05 | the body of each checkpoint |",
        "| `dependency_edges.psv` | r07 | the authoritative dependency edges |",
        "| `compensation_links.csv` | r09 | the target each compensating event names |",
        "| `compensation_policy.toml` | r10 | which counter each reversed kind moves |",
        "| `eligibility_predicates.csv` | r12 | the closed predicate vocabulary and argument order |",
        "| `eligibility_policy.yaml` | r01 r09 | the order the screening tests run in |",
        "| `reporting_station_roster.conf` | r12 | the region rank on the re offer ladder |",
        "| `allotment_ceiling_history.tsv` | r04 | the ceilings of earlier revisions |",
        "| `prior_epoch_archive.db` | r04 | the counters the archive holds for each checkpoint |",
        "| `quarantine_reason_catalogue.psv` | r14 | the reason codes and the stage each sits in |",
        "| `rounding_and_arithmetic_policy.yaml` | r01 r10 r14 | the arithmetic basis and the ratio places |",
        "| `publication_form_rules.toml` | r14 | the core digest document list |",
        "| `package_expectations.toml` | r14 | the shape the delivered archive carries |",
        "| `revision_precedence.toml` | all | which paper governs when two disagree |",
        "| `project.zip` | all | the package as the facility currently runs it |",
        "",
        "## Papers that govern nothing",
        "",
        "`station_register_current.csv` carries revisions lodged after the",
        "frozen register revision and is kept for comparison only.",
        "`topology_drafts.xml` is the draft of the scope map.",
        "`legacy_scale_table.csv` holds the scales of the prior epoch.",
        "The `depends_on` list inside a journal record is a convenience copy",
        "of an earlier edge set. `event_supplement.ndjson` rows whose",
        "identifier begins `EVT-8` were lodged for a later epoch.",
    ])

    write_lines(dest / "readings_not_in_force.md", [
        "# Readings this facility does not support",
        "",
        "Each line names a reading of these papers that looks reasonable and",
        "is wrong here, beside the reading in force.",
        "",
        "1. Not in force: a checkpoint watermark names the next position to",
        "   replay. In force: a watermark names a position already processed,",
        "   so the first candidate the window can replay is the watermark",
        "   plus one.",
        "2. Not in force: the requested range is closed at both ends. In",
        "   force: the range is start inclusive and end exclusive.",
        "3. Not in force: a compensating event reverses the event next to it.",
        "   In force: it reverses the event the link register names, resolved",
        "   against the whole canonical history.",
        "4. Not in force: a compensation target must sit inside the replay",
        "   window. In force: the target may sit behind the restored",
        "   checkpoint, and its metadata is read from the canonical history",
        "   without replaying it again.",
        "5. Not in force: eligibility is settled once, before the pass. In",
        "   force: an event whose predicate is false waits in the pending",
        "   queue and is offered again after the window is exhausted.",
        "6. Not in force: the pending queue is offered in canonical order. In",
        "   force: it is offered in the order the directive ladder gives.",
        "7. Not in force: a compensation reverses primary state only. In",
        "   force: it also reverses the derived counter its kind moves, at",
        "   the class reversal scale, exactly once.",
        "8. Not in force: two compensations on one target each take effect.",
        "   In force: the target is reversed once and the later compensation",
        "   is recorded as void with no effect on any counter.",
        "9. Not in force: a dependency behind the window is missing. In",
        "   force: it is already folded into the restored checkpoint and is",
        "   satisfied.",
        "10. Not in force: `station_register_current.csv` gives the class. In",
        "    force: `station_register_frozen.csv` does.",
        "11. Not in force: `legacy_scale_table.csv` gives the carry quantum.",
        "    In force: the live sheet of the workbook does, and the quantum",
        "    appears in no other paper.",
        "12. Not in force: the workbook sheet is chosen by name or position.",
        "    In force: it is chosen by matching its epoch key cell against",
        "    the epoch key in the header.",
        "13. Not in force: the first resolution in the memo governs. In",
        "    force: among resolutions on one subject the later sitting",
        "    governs, and a line marked RESCINDED carries no force.",
        "14. Not in force: canonical order is arrival order. In force: it is",
        "    sequence, then stamp, then kind rank, then tie break key, then",
        "    event identifier.",
        "15. Not in force: two records that carry the same payload are one",
        "    event. In force: an event is its identifier, and two identifiers",
        "    are two events however alike their payloads look.",
        "16. Not in force: a record whose `source` field is empty was lodged",
        "    by the journal. In force: the provenance ledger names the source",
        "    of a record that carries none.",
    ])

    write_lines(dest / "glossary_and_reason_codes.md", [
        "# Glossary and reason codes",
        "",
        "**credit unit (cu)** the basis unit of every published quantity.",
        "",
        "**canonical position** the one based index of an event in the",
        "canonical order. Every range, watermark and probe is a position.",
        "",
        "**watermark** the canonical position a checkpoint stands after.",
        "",
        "**pending queue** the ordered list of events whose eligibility",
        "predicate was false when they were offered. It is part of the state",
        "and travels inside a checkpoint body.",
        "",
        "**re offer round** one sweep of the pending queue after the window",
        "is exhausted. Rounds run until a round admits nothing or the round",
        "ceiling is reached.",
        "",
        "**disposition** what became of a compensating event: `applied`,",
        "`void_duplicate` or `void_unapplied`.",
        "",
        "## Reason codes",
        "",
        "| code | stage | meaning |",
        "| --- | --- | --- |",
        *["| " + code + " | " + stage + " | " + meaning + " |"
          for code, stage, meaning in reason_catalogue(E)],
        "",
        "A record that fails two tests carries the code that comes first in",
        "the screening order in `eligibility_policy.yaml`.",
    ])

    write_lines(dest / "known_traps_and_footguns.md", [
        "# Known traps",
        "",
        "Every trap below is a documented rule, a forward step and an exact",
        "inverse. Nothing here depends on a value that is absent from this",
        "directory.",
        "",
        "1. **Revision layering.** Every register carries rows above the",
        "   frozen register revision. Those rows are drafts and govern",
        "   nothing. Among the rows at or below the frozen revision, the",
        "   greatest revision for a key is the row in force.",
        "2. **Twin registers.** `station_register_frozen.csv` and",
        "   `station_register_current.csv` carry the same keys with different",
        "   classes and regions. The frozen one governs.",
        "3. **Twin scope maps.** `topology_and_scope.xml` and",
        "   `topology_drafts.xml` carry the same station identifiers with",
        "   different regions. The first one governs.",
        "4. **Twin scale tables.** `legacy_scale_table.csv` restates the",
        "   class scales with a shifted numerator and a shifted carry",
        "   quantum. The workbook governs.",
        "5. **Two workbook sheets.** One sheet is in force. Match the epoch",
        "   key cell, never the sheet name and never the sheet position.",
        "6. **Rescinded resolutions.** The memo carries lines that begin",
        "   RESCINDED. They carry no force. Among live resolutions on one",
        "   subject the later sitting governs.",
        "7. **Aliased identifiers.** A station or programme may be recorded",
        "   under a site or project code. Resolve it through the crosswalk",
        "   before anything else touches it.",
        "8. **Recorded units.** A quantity is recorded in one of six unit",
        "   symbols. Carry it through the unit registry before the class",
        "   conversion, not after.",
        "9. **Blank lodging source.** Some supplement records carry an empty",
        "   `source`. The provenance ledger names the source of those.",
        "10. **Convenience dependency copy.** The `depends_on` list inside a",
        "    journal record is stale. The pipe file governs, and only its",
        "    `requires` edges count.",
        "11. **Full canonical ties.** Some events agree on sequence, stamp",
        "    and kind. The tie break key separates them, and where that also",
        "    agrees the event identifier does.",
        "12. **Checkpoint digests.** Some sealed checkpoints declare a digest",
        "    that no longer matches the body they point at. Recompute and",
        "    reject the ones that disagree.",
        "13. **Register rows with no body.** Some checkpoint register rows",
        "    point at bodies that were never lodged.",
        "14. **Checkpoints past the end.** Some checkpoints stand at or after",
        "    the requested end boundary and cannot be used for that range.",
        "15. **Zero denominators.** A station whose allotments cancel to zero",
        "    has no share to publish. Publish an exact zero rather than",
        "    dividing.",
        "16. **Archive drift.** `prior_epoch_archive.db` holds counters that",
        "    can disagree with the checkpoint body. The recomputed digest",
        "    governs; the archive difference is reported, not applied.",
        "17. **Boundary positions.** The bounded range opens on a position",
        "    that carries an event and closes one past the last position it",
        "    replays.",
        "18. **Reserved rows.** Several registers carry rows whose key begins",
        "    `reserved`, `RSV` or `feed_`. They are lodged for later epochs.",
        "19. **Retired predicate form.** `hub_open` is carried in the",
        "    predicate register as retired. A predicate the register does not",
        "    carry as active is false whenever it is read.",
        "20. **Round ceiling binding.** When the round ceiling is reached",
        "    while a round is still admitting, publish the pass the ceiling",
        "    stops at and record that the run did not settle.",
    ])

    write_lines(dest / "serialisation_and_digest_contract.md", [
        "# Serialisation and digest contract",
        "",
        "Encoding is utf-8 with no byte order mark. Line endings are line",
        "feed. Every text document ends with exactly one trailing newline.",
        "",
        "Indented json is written with sorted keys, two space indentation and",
        "a trailing newline. A json lines document writes one compact record",
        "per line with sorted keys and the separators `,` and `:` carrying no",
        "surrounding space. A delimited document writes its header line",
        "first, then one line per row, with no quoting and no padding.",
        "",
        "Every whole quantity is a json integer or a bare integer field. No",
        "quantity is written as a decimal. Every ratio is a string carrying",
        "exactly twelve decimal places, half away from zero, and negative",
        "zero is never written.",
        "",
        "## Checkpoint digest",
        "",
        "The digest of a checkpoint body is the lowercase hexadecimal sha256",
        "of the compact json of the object holding exactly the keys",
        "`position`, `balances`, `allotments`, `counters`, `pending`,",
        "`applied` and `reversed`, with sorted keys and the compact",
        "separators. `applied` and `reversed` are written sorted ascending;",
        "`pending` keeps its queue order.",
        "",
        "## Run manifest",
        "",
        "`run_manifest.txt` carries two lines. The first is `core` followed",
        "by a space and the sha256 of the concatenated bytes of the documents",
        "`publication_form_rules.toml` names, in the order it names them. The",
        "second is `publication` followed by a space and the sha256 of the",
        "concatenated bytes of every published document except `package.zip`",
        "and `run_manifest.txt`, taken in ascending file name order. Both",
        "digests are taken last, over the bytes already on disk.",
    ])

    write_lines(dest / "worked_examples.md", [
        "# Worked examples",
        "",
        "The numbers below are invented for the example. They show the shape",
        "of each rule, not this epoch's values.",
        "",
        "## Unit normalisation",
        "",
        "A record lodges `quantity` 7 in unit `shift`. The unit registry",
        "gives `shift` a scale of 480. The station sits in class `BR` on the",
        "frozen register, and the live workbook sheet gives class `BR` a",
        "conversion of 9 over 4. The normalised quantity is",
        "`half_up(7 * 480 * 9 / 4)` which is 7560 cu exactly. The rounding",
        "happens once, here.",
        "",
        "## Window construction",
        "",
        "The requested range is positions 1 to 180 and the selected",
        "checkpoint stands at watermark 62. The window opens at 63 and closes",
        "one before 180, so it replays positions 63 to 179. Position 62 is",
        "behind the engine and is never replayed again. The skipped count is",
        "62.",
        "",
        "## Compensation across the boundary",
        "",
        "A compensating event at position 150 names a target at position 44,",
        "which is behind the checkpoint. The target is read out of the",
        "canonical history for its station, programme, kind and normalised",
        "quantity. The target is not replayed. The restored `applied` ledger",
        "says the target took effect, so the reversal goes ahead: a grant of",
        "800 cu comes off the station balance and off the station programme",
        "allotment, and the derived counter the compensation policy names for",
        "`grant` comes down by `half_up(800 * reversal_num / reversal_den)`.",
        "The counter `reversed_cu` goes up by the same amount and",
        "`compensations` goes up by one.",
        "",
        "## A second compensation on the same target",
        "",
        "A later compensating event names the same target at position 44.",
        "The target already sits in the reversed ledger, so the row is",
        "written with disposition `void_duplicate`, `reversed_cu` zero and",
        "`applied_order` zero, and no counter moves.",
        "",
        "## Carry settlement",
        "",
        "A station in class `CN` reaches a balance of 21440 cu. The ceiling",
        "for the frozen revision and class `CN` is 20100 cu and the class",
        "carry quantum is 80. The spill is 1340, the carried part is",
        "`(1340 // 80) * 80` which is 1280, the balance settles at",
        "`21440 - 1280` which is 20160, and `spilled_cu` goes up by 1280.",
        "",
        "## Re offer rounds",
        "",
        "Three events wait in the pending queue. The ladder offers them by",
        "scope, then region rank, then normalised quantity ascending. Round",
        "one admits the one whose predicate now holds; admitting it changes",
        "the balance the next predicate reads, but that event was already",
        "offered this round, so it waits for round two. When a round admits",
        "nothing the run has settled. When the round ceiling is reached while",
        "a round is still admitting, the run publishes that pass and records",
        "that it did not settle.",
        "",
        "## Ratio",
        "",
        "A station holds 3 cu under one programme out of 8 cu across all its",
        "programmes. The share is `0.375000000000`. A station whose",
        "allotments cancel to zero publishes `0.000000000000` rather than",
        "dividing.",
    ])

    _write_stage_papers(dest)
    _write_schema(dest)


STAGE_BODIES = {
"r01": [
 "The recorded quantity of an event is carried into credit units in two",
 "steps. First the unit symbol on the record is looked up in",
 "`unit_registry.toml` and the recorded quantity is multiplied by that",
 "scale. Second the station class is looked up on the frozen station",
 "register and the result is multiplied by the class conversion factor,",
 "a numerator over a denominator, taken from the live sheet of",
 "`custody_parameter_workbook.xlsx`. The product is an exact rational and",
 "is rounded to a whole number of credit units once, here, half away from",
 "zero. No later stage rounds a quantity again.",
 "",
 "The live sheet is the sheet whose `epoch_key` cell equals the",
 "`workbook_epoch_key` field of `epoch_header.json`: the value beside the",
 "label cell that reads exactly `epoch_key`. Sheet names and sheet order",
 "carry no meaning in choosing it, and the name published for it is the",
 "name the workbook gives that sheet. The other sheet belongs to a prior",
 "epoch and its numbers differ.",
 "",
 "The live sheet carries four kinds of row. A `conversion` row gives a",
 "class, a numerator and a denominator. A `reversal` row gives a class, a",
 "numerator and a denominator. A `carry_quantum` row gives a class and a",
 "whole number. A `ceiling` row gives a revision, a class and a ceiling in",
 "credit units. Rows tagged `calibration` are bench notes and settle",
 "nothing.",
 "",
 "`custody_board_memo.pdf` carries the three scalars this epoch runs",
 "under. A resolution line reads `RESOLUTION` then its number then",
 "`SITTING` then the sitting number then the subject then ` = ` then the",
 "value. Where two live resolutions carry one subject the greater sitting",
 "governs. A line that begins `RESCINDED` is not a resolution.",
 "",
 "A record is screened before it is applied. The screening tests run in",
 "the order `eligibility_policy.yaml` gives, and the first test a record",
 "fails decides its reason code. `EVT-DRAFTREVISION` fires when the record",
 "revision passes the frozen register revision. `EVT-WITHDRAWN` fires when",
 "the identifier sits in `withdrawn_event_journal.tsv` at a revision at or",
 "below the frozen revision. `EVT-NONPOSITIVE` fires when the normalised",
 "quantity is absent, zero or below. `EVT-IMPLAUSIBLE` fires when it",
 "passes the implausible quantity ceiling in the memo. The last two never",
 "fire on a compensating event, which carries no quantity of its own.",
],
"r02": [
 "A station or programme may be recorded under a code carried over from",
 "an earlier epoch. `alias_crosswalk.tsv` maps such a code to the",
 "canonical identifier. A crosswalk row is in force when its",
 "`in_force_from_revision` stands at or below the frozen register",
 "revision; among the in force rows for one code and kind the greatest",
 "revision governs. Resolution happens before screening, before ordering",
 "and before any register lookup.",
 "",
 "`station_register_frozen.csv` is the station register in force. For each",
 "station the row in force is the one with the greatest revision at or",
 "below the frozen register revision. A station with no such row is absent,",
 "and an event naming it carries `EVT-UNKNOWNSTATION`. A transfer names a",
 "counterparty as well, and an absent or empty counterparty carries the",
 "same code.",
 "",
 "`station_register_current.csv` carries later lodges of the same keys",
 "with different classes and regions and governs nothing here.",
 "",
 "`programme_register.csv` is read the same way. An event naming a",
 "programme with no in force row carries `EVT-UNKNOWNPROGRAMME`. A",
 "compensating event names no programme of its own and never carries this",
 "code.",
],
"r03": [
 "The lodged records arrive in two files. `event_journal.jsonl` holds the",
 "desk journal and `event_supplement.ndjson` holds the late lodges. One",
 "record survives per event identifier: the one whose lodging source",
 "carries the greater priority in `source_priority_register.csv`, and",
 "among records of one source the greater revision. A source register row",
 "is in force at or below the frozen revision, and among in force rows for",
 "one source the greatest revision gives the priority.",
 "",
 "A record may carry an empty `source`. `row_provenance_ledger.csv` names",
 "the source of each record identifier in each file, and that name is used",
 "when the record carries none.",
 "",
 "A supplement row whose identifier begins with the prefix",
 "`data_lineage.md` reserves for a later epoch takes no part in the merge.",
 "",
 "An event is its identifier. Two records that agree on kind, station,",
 "programme and quantity but carry different identifiers are two events,",
 "and both are placed in the order.",
 "",
 "The canonical order is, in this exact precedence: `sequence` ascending,",
 "then `stamp` ascending, then the kind rank in force from",
 "`event_kind_ranks.csv` ascending, then the `tiebreak` key ascending as",
 "text, then `event_id` ascending as text. Arrival order, file order and",
 "json key order settle nothing. The one based index of an event in this",
 "order is its canonical position, and every range, watermark and probe in",
 "this contract is stated as a canonical position.",
],
"r04": [
 "`checkpoint_register.csv` lists the checkpoints and",
 "`checkpoint_states.jsonl` holds their bodies. A checkpoint is usable for",
 "a replay whose end boundary is E when every one of these holds: its",
 "register row stands at a revision at or below the frozen register",
 "revision; its status is `sealed`; a body carrying its identifier is",
 "lodged; the digest recomputed from that body equals the digest the",
 "register declares; every identifier in the body's applied ledger stands",
 "at or before the body position in the canonical order; and the body",
 "position is strictly less than E. A ledger identifier the canonical",
 "history does not carry stands at no position and fails that test.",
 "",
 "Among the usable checkpoints the one with the greatest position is",
 "selected. When none is usable the replay runs from an empty state with",
 "watermark zero.",
 "",
 "Every rejected register row is reported with one reason:",
 "`draft_revision`, `not_sealed`, `body_missing`, `digest_mismatch`,",
 "`ledger_past_watermark` or `position_at_or_after_end`, tested in that",
 "order.",
 "",
 "`prior_epoch_archive.db` holds the counters the archive kept for some",
 "checkpoints and the station and applied counts for each. Where the",
 "archive and the body disagree the body governs; the difference is",
 "reported and never applied. `allotment_ceiling_history.tsv` holds the",
 "ceilings of earlier revisions and is read for the revision the selected",
 "register row carries.",
],
"r05": [
 "A checkpoint body carries the whole state: the position it stands after,",
 "the station balances, the nested station and programme allotments, every",
 "derived counter, the pending queue in queue order, the ledger of applied",
 "event identifiers and the ledger of reversed target identifiers.",
 "",
 "Restoration copies the body. The parsed body is left exactly as it was",
 "read, so a second replay from the same checkpoint opens from the same",
 "state as the first. Nested containers are copied too; sharing the",
 "allotment mapping with the parsed body lets one replay bleed into the",
 "next.",
 "",
 "A restored watermark of N means the event at canonical position N was",
 "already processed and folded into the state. It is not an event to",
 "process again.",
],
"r06": [
 "A replay is asked for a half open range of canonical positions: the",
 "start is included and the end is excluded. The window it actually",
 "replays opens at the later of the requested start and the restored",
 "watermark plus one, and closes one before the requested end or at the",
 "last canonical position, whichever comes first.",
 "",
 "The count of positions skipped because the checkpoint already covers",
 "them is the watermark less the requested start plus one, and never less",
 "than zero.",
 "",
 "The event at the watermark position is never replayed. The event at the",
 "end position is never replayed either.",
],
"r07": [
 "`dependency_edges.psv` is the authoritative edge set. Only rows whose",
 "`edge_kind` is `requires` and whose revision stands at or below the",
 "frozen register revision are edges. The `depends_on` list carried inside",
 "a journal record is a copy of an earlier edge set and governs nothing.",
 "",
 "An event that names itself carries `DEP-SELF`. An event that sits on a",
 "cycle in the edge graph carries `DEP-CYCLE`. These two are tested",
 "before any other dependency test. A self edge is a cycle of one, so an",
 "event that names itself also stands among the cycle members, and",
 "`DEP-SELF`, tested first, decides its code.",
 "",
 "An event sits on a cycle when some path of edges in force leads from it",
 "back to itself, however long the path and wherever a walk that finds it",
 "begins. An edge naming an identifier the canonical history does not",
 "carry takes no part in the cycle test.",
 "",
 "Otherwise each dependency is settled by the canonical position of the",
 "event it names. A dependency whose position stands before the window",
 "opening is already folded into the restored checkpoint and is satisfied",
 "without being replayed. A dependency whose position stands at or after",
 "the window opening and before the depending event is satisfied inside",
 "the window. Anything else, including a dependency naming an identifier",
 "that is not in the canonical history and a dependency standing later",
 "than the depending event, leaves the event with `DEP-MISSING`.",
 "",
 "The published closure counts how many dependencies each of the two",
 "satisfying routes accounted for across the whole window, over the",
 "events that clear every screening and dependency test. An event that is",
 "set aside adds nothing to either count, even for a dependency of it that",
 "was satisfied.",
],
"r08": [
 "A `grant` adds the normalised quantity to the station balance and to the",
 "station programme allotment, adds one to `grants` and adds the quantity",
 "to `granted_cu`.",
 "",
 "A `retire` subtracts the normalised quantity from the station balance",
 "and from the station programme allotment, adds one to `retires` and adds",
 "the quantity to `retired_cu`.",
 "",
 "A `transfer` subtracts the normalised quantity from the station balance",
 "and the station programme allotment and adds it to the counterparty",
 "balance and the counterparty allotment under the same programme, adds",
 "one to `transfers` and adds the quantity to `transferred_cu`.",
 "",
 "Every applied event appends its identifier to the applied ledger and one",
 "row to the transition log. The transition log row carries the one based",
 "application order, the identifier, the canonical position, the kind, the",
 "station, the programme, the quantity in credit units and the station",
 "balance after the event settled.",
 "",
 "Applied transitions and applied compensations draw their application",
 "order from one counter, which starts at one in each replay. The",
 "transition log therefore skips the orders applied compensations took.",
],
"r09": [
 "A compensating event carries no quantity and no programme of its own. It",
 "names the event it reverses through `compensation_links.csv`. A link row",
 "is in force at or below the frozen register revision, and among in force",
 "rows for one compensation identifier the greatest revision governs.",
 "",
 "A compensating event with no in force link, or whose in force link is",
 "not `registered`, carries `CMP-WITHDRAWN`. A compensating event whose",
 "named target is not an identifier in the canonical history carries",
 "`CMP-NOTARGET`.",
 "",
 "The named target is resolved against the whole canonical history. It may",
 "stand anywhere, including behind the restored checkpoint. Its position",
 "relative to the replay window is not a reason to reject it, and the",
 "target is never replayed in order to reverse it: its station,",
 "programme, kind, class and normalised quantity are read straight off the",
 "canonical record.",
],
"r10": [
 "A compensating event whose target already sits in the reversed ledger is",
 "recorded with disposition `void_duplicate`, a reversed amount of zero",
 "and an applied order of zero, and moves no state and no counter. A",
 "compensating event whose target does not sit in the applied ledger is",
 "recorded with disposition `void_unapplied` on the same terms.",
 "",
 "Otherwise the target effect comes off exactly. A reversed `grant`",
 "subtracts its quantity from the target station balance and allotment. A",
 "reversed `retire` adds it back. A reversed `transfer` adds it back to",
 "the origin and subtracts it from the counterparty. Reversing a target",
 "does not remove it from the canonical history and does not return it to",
 "the pending queue.",
 "",
 "The derived effect comes off as well. The reversed amount is",
 "`half_up(quantity * reversal_num / reversal_den)` in exact rational",
 "arithmetic, rounded here and nowhere else, half away from zero. The",
 "quantity is the target's normalised quantity. The scale is the live",
 "sheet's reversal scale for the class the frozen station register carried",
 "for the target station at the revision of the target record that",
 "survived the merge: the register row with the greatest revision at or",
 "below that revision. When the register carries no row for the station",
 "that early, the class in force at the frozen register revision is used.",
 "The counter",
 "`compensation_policy.toml` names for the target kind comes down by that",
 "amount, the count counter for that kind comes down by one, `reversed_cu`",
 "goes up by that amount and `compensations` goes up by one. The target",
 "identifier is appended to the reversed ledger and the touched stations",
 "settle.",
 "",
 "The compensation register carries one row per compensating event that",
 "reached this stage, in ascending compensation identifier order, holding",
 "the compensation identifier, the target identifier, the target canonical",
 "position, the disposition, the reversed amount and the application",
 "order.",
],
"r11": [
 "After every applied transition and every applied compensation each",
 "station the event touched settles on its own balance.",
 "",
 "A station whose balance stands at or below the ceiling for the frozen",
 "register revision and its class does not settle. Otherwise the spill is",
 "the balance less the ceiling, the carried part is the spill floored to a",
 "whole number of the class carry quantum, the balance comes down by the",
 "carried part and `spilled_cu` goes up by the carried part. A carried",
 "part of zero leaves the balance where it stands.",
 "",
 "The class carry quantum appears on the live workbook sheet and in no",
 "other paper in this directory. The superseded scale table restates a",
 "shifted quantum and governs nothing.",
],
"r12": [
 "An event may carry a `requires` predicate, read against the state as it",
 "stands immediately before the event is offered. A compensating event is",
 "never deferred: a `requires` field it carries is not read.",
 "",
 "`eligibility_predicates.csv` carries the predicate forms, one row per",
 "form and revision, and the row in force for a form is the one with the",
 "greatest revision at or below the frozen register revision. A predicate",
 "writes its form and then its arguments, separated by colons, in the",
 "order the form in force lists them. A form the register in force does",
 "not carry as active, and a predicate whose argument count disagrees with",
 "its form, is false whenever it is read. Arguments are read as written;",
 "the crosswalk is not applied to them.",
 "",
 "`balance_at_least` holds when the balance of `station` stands at or",
 "above `amount_cu`. `allotment_below` holds when the allotment `station`",
 "holds under `programme` stands strictly below `amount_cu`.",
 "`counter_at_least` holds when the derived counter `counter` stands at or",
 "above `amount`. `no_pending` holds when the pending queue is empty.",
 "`station_active` holds when the frozen register carries `station` as",
 "active.",
 "",
 "An event whose predicate is false is not discarded and is not",
 "quarantined. Its identifier joins the end of the pending queue and the",
 "pass moves on. A compensating event later in the same window can change",
 "the state its predicate reads, which is why eligibility cannot be",
 "settled once before the pass.",
 "",
 "When the window is exhausted the re offer rounds begin. Each round",
 "offers the pending identifiers in the order the ladder in",
 "`precedence_directive.docx` gives, each against the state as it then",
 "stands, and applies the ones whose predicate holds, removing them from",
 "the queue and adding one to `deferred_admitted` for each. The queue",
 "itself keeps the order in which identifiers joined it: the ladder orders",
 "a round's offers, never the queue, and an identifier that leaves the",
 "queue leaves the others in place. Admitting an event inside a round changes",
 "the state the rest of that round reads, but an identifier already",
 "offered this round waits for the next one. The region an event takes on",
 "the ladder is the region the frozen register carries for its station,",
 "ranked by the reporting roster.",
 "",
 "A round that admits nothing ends the run and the run has settled. A run",
 "that reaches the round ceiling in the memo while the last round was",
 "still admitting stops there and has not settled. Only rounds that",
 "admitted at least one identifier are published.",
],
"r13": [
 "The published state carries its position, the station balances with",
 "every zero balance dropped, the nested station and programme allotments",
 "with every zero allotment dropped and every station left holding none",
 "dropped with it, every derived counter, the pending queue in queue",
 "order, the applied ledger sorted ascending and the reversed ledger",
 "sorted ascending. The position of a replay's state is the end boundary",
 "of the range the replay was asked for, a position it never replays; the",
 "position of the probe document is the probe position.",
 "",
 "The derived index carries one record per surviving station and programme",
 "pair. Each record holds the region and hub the station reports under in",
 "`topology_and_scope.xml`, the station, the programme, the allotment in",
 "credit units and the share that allotment takes of the station total,",
 "as a ratio at twelve places. A station whose allotments cancel to zero",
 "publishes a zero share rather than dividing. The index is ordered by",
 "region, then hub, then station, then programme.",
 "",
 "The probe document holds the state after the probe position in a from",
 "scratch forward pass with no re offer round run at all. The bounded",
 "document holds the state a replay of the bounded range reaches, with its",
 "own checkpoint selected against the bounded end boundary.",
],
"r14": [
 "Every published document follows",
 "`serialisation_and_digest_contract.md` and the shape",
 "`output_schema_reference.md` gives, header line, column order, row",
 "order, key names and value types.",
 "",
 "The equivalence document compares the state a replay from the selected",
 "checkpoint reaches against the state a replay from scratch over the same",
 "end boundary reaches, and publishes the digest of each and whether they",
 "agree.",
 "",
 "The verification notes and the defect register are derived documents",
 "like any other: the register is the reason code catalogue filtered to",
 "the codes in force and sorted, and the notes carry the run scalars in",
 "the order the schema gives.",
 "",
 "The two digests in the run manifest are taken last, over the bytes",
 "already written.",
],
}


def _write_stage_papers(dest):
    for sid, slug, title in STAGE_TITLES:
        lines = ["# Stage " + sid + ": " + title, ""]
        lines.extend(STAGE_BODIES[sid])
        lines.append("")
        write_lines(dest / ("spec_stage_" + sid + "_" + slug + ".md"), lines)


def _write_schema(dest):
    write_lines(dest / "output_schema_reference.md", [
        "# Output schema reference",
        "",
        "Twenty four documents are published. Every one is written through",
        "`serialisation_and_digest_contract.md`.",
        "",
        "## package.zip",
        "",
        "The repaired package. `pyproject.toml` sits at the archive root, the",
        "source tree sits under `src/bcrep`, and the shipped `tests`",
        "directory is carried through unchanged.",
        "",
        "## unit_normalisation.json",
        "",
        "Keys: `epoch_id`, `workbook_epoch_key`, `live_sheet`,",
        "`frozen_register_revision`, `round_ceiling`, `implausible_ceiling_cu`,",
        "`settlement_floor_cu`, `precedence_levels` as a list of strings in",
        "level order, `units` as a mapping of symbol to scale, `classes` as a",
        "mapping of class to a mapping holding `carry_quantum`,",
        "`conversion_den`, `conversion_num`, `reversal_den` and",
        "`reversal_num`, `ceilings` as a mapping whose key is the revision, a",
        "colon and the class, `event_count` and `normalised_total_cu`. The",
        "normalised total sums the normalised quantity of every canonical",
        "event whose quantity resolved above zero.",
        "",
        "## alias_resolution.jsonl",
        "",
        "One record per kind and alias pair that carries an in force",
        "crosswalk row, taken from the row that governs the pair, ordered by",
        "kind then alias, each holding `alias`, `canonical`, `kind` and",
        "`in_force_from_revision`.",
        "",
        "## canonical_order.csv",
        "",
        "Header `position,event_id,sequence,stamp,kind,rank,tiebreak`, one row",
        "per canonical event in canonical order.",
        "",
        "## checkpoint_selection.json",
        "",
        "Keys: `requested_start`, `requested_end`, `usable` as a sorted list",
        "of identifiers, `selected`, `selected_position`, `watermark_position`",
        "and `rejected` as a list of objects holding `checkpoint_id` and",
        "`reason`, ordered by identifier then reason. An unselected run",
        "publishes an empty `selected` and a zero `selected_position`.",
        "",
        "## replay_window.json",
        "",
        "Keys: `start_position`, `end_position`, `replayed_count`,",
        "`first_replayed_position`, `last_replayed_position`,",
        "`skipped_before_watermark` and `boundary`, whose value is the string",
        "`start inclusive, end exclusive`. An empty window publishes zero for",
        "the first and last position.",
        "",
        "## dependency_closure.json",
        "",
        "Keys: `edges_in_force`, `satisfied_by_checkpoint`,",
        "`satisfied_by_window`, `unsatisfied` as a list of objects holding",
        "`event_id` and `reason` ordered by identifier then reason, and",
        "`cycle_members` as a sorted list of identifiers.",
        "",
        "## quarantine_ledger.csv",
        "",
        "Header `event_id,position,stage,reason_code,detail`, ordered by",
        "position then identifier. `detail` carries the event kind.",
        "",
        "## transition_log.jsonl",
        "",
        "One record per applied transition in application order, holding",
        "`order`, `event_id`, `position`, `kind`, `station`, `programme`,",
        "`quantity_cu` and `balance_after`. Compensations are not transitions",
        "and do not appear here.",
        "",
        "## compensation_register.csv",
        "",
        "Header `compensation_id,target_event_id,target_position,disposition,",
        "reversed_cu,applied_order`, ordered by compensation identifier.",
        "",
        "## derived_counters.csv",
        "",
        "Header `counter,value`, one row per counter in ascending counter",
        "name order: `compensations`, `deferred_admitted`, `granted_cu`,",
        "`grants`, `retired_cu`, `retires`, `reversed_cu`, `spilled_cu`,",
        "`transferred_cu`, `transfers`.",
        "",
        "## eligibility_passes.json",
        "",
        "Keys: `pass_ceiling`, `deferred_at_first_pass` as a sorted list of",
        "identifiers, `rounds` as a list of objects holding `round`,",
        "`admitted` in admission order and `admitted_count`, `round_count`,",
        "`stable` as a boolean and `deferred_remaining` in queue order.",
        "",
        "## final_state.json",
        "",
        "Keys: `position`, `balances`, `allotments`, `counters`, `pending`,",
        "`applied` and `reversed`, exactly as stage r13 describes them.",
        "",
        "## derived_index.jsonl",
        "",
        "One record per surviving station and programme pair holding",
        "`region`, `hub`, `station`, `programme`, `allotment_cu` and `share`.",
        "",
        "## checkpoint_reconciliation.json",
        "",
        "Keys: `selected`, `declared_digest`, `recomputed_digest`, `matches`,",
        "`archive_rows` as the number of rows the archive's `prior_counters`",
        "table holds across every checkpoint, `counter_deltas` as a mapping of",
        "counter name to the",
        "archive value less the checkpoint value for the counters the archive",
        "carries for the selected checkpoint, `historic_ceiling_total_cu` as",
        "the sum of the ceiling history rows at the revision the selected",
        "register row carries, and `rejected_count`.",
        "",
        "## equivalence_report.json",
        "",
        "Keys: `comparison_start`, `comparison_end`, `checkpoint_used`,",
        "`from_scratch_digest`, `from_checkpoint_digest`, `identical` and the",
        "two replayed counts `scratch_replayed_count` and",
        "`checkpoint_replayed_count`.",
        "",
        "## state_at_event.json",
        "",
        "The published state shape at the probe position.",
        "",
        "## bounded_replay.json",
        "",
        "Keys: `start_position`, `end_position`, `replayed_count` and `state`,",
        "whose value is the published state shape.",
        "",
        "## repair_report.json",
        "",
        "Keys: `package`, `modules` as the module list the package",
        "expectations name, `stage_ids`, `stage_count`, `entry_point`,",
        "`standard_library_only` and `reason_codes` in screening order.",
        "",
        "## selftest.json",
        "",
        "Keys: `checks` as a list of objects holding `name` and `value` in",
        "this order: `canonical_order_total`, `checkpoint_digest_matches`,",
        "`window_end_exclusive`, `watermark_replayed_once`,",
        "`scratch_matches_checkpoint`, `targets_reversed_once`,",
        "`pending_after_rounds`, `rounds_run`; then `passed` and `failed`.",
        "Each flag check publishes one when it holds and zero when it does",
        "not; `canonical_order_total`, `pending_after_rounds` and `rounds_run`",
        "publish their count. `passed` is the number of flag checks that",
        "publish one and `failed` the number that publish zero; the three",
        "counts are counted in neither.",
        "",
        "## defect_register.md",
        "",
        "A title line reading `# Defect register`, a blank line, a three",
        "column table of stage, reason code and meaning under the header row",
        "`| stage | reason code | meaning |` and the separator row",
        "`| --- | --- | --- |`, over the reason codes in force sorted ascending by",
        "code, a blank line, then a line reading `Stages in force: ` followed",
        "by the fourteen stage identifiers separated by a comma and a space.",
        "",
        "## verification_notes.md",
        "",
        "A title line reading `# Verification notes`, a blank line, then one",
        "line each in this order, a single space between words: `epoch`",
        "and the identifier, `live sheet` and the sheet name, `watermark",
        "position` and the number, `window` then the opening position then",
        "`to` then the closing position then `end exclusive`, `rounds run` and",
        "the number, `stable` and `yes` or `no`, `pending after rounds` and",
        "the number, `compensations applied` and the number, `compensations",
        "void` and the number, `reversed cu` and the number, `spilled cu` and",
        "the number, `settlement floor` and the number, `settlement floor",
        "breaches` and the number, `scratch equals checkpoint` and `yes` or",
        "`no`. Nothing follows that last line but the one trailing newline.",
        "",
        "## run_manifest.txt",
        "",
        "Two lines: `core` and the digest, then `publication` and the digest.",
        "",
        "## summary.json",
        "",
        "Keys: `epoch_id`, `live_sheet`, `frozen_register_revision`,",
        "`control_totals`, `stable`, `equivalence_identical` and",
        "`balance_share`. The control totals hold `admitted_in_rounds`,",
        "`allotment_total_cu`, `balance_total_cu`, `canonical_events`,",
        "`checkpoint_position`, `compensations_applied`, `compensations_void`,",
        "`deferred_at_first_pass`, `index_rows`, `pending_remaining`,",
        "`quarantined_events`, `replayed_positions`, `reversed_cu`,",
        "`round_count`, `settlement_floor_breaches`, `spilled_cu`,",
        "`window_end` and `window_start`. The balance share is the total",
        "balance over the total allotment as a ratio at twelve places, and it",
        "publishes an exact zero when the total allotment is zero.",
        "",
        "A settlement floor breach is a published station balance standing",
        "strictly below the settlement floor the memo names.",
    ])


def _sheet_block(E, key, live, prior):
    """One workbook sheet. Under a header row, the epoch key of the epoch
    before the sheet's own sits above the epoch key that says whether the
    sheet is in force."""
    rows = [["parameter", "value"],
            ["epoch_key_prior", prior],
            ["epoch_key", key],
            ["sheet_state", "lodged" if live else "lodged"],
            ["basis_unit", "cu"],
            ["prepared_for", E["epoch_id"] if live else "prior epoch"]]
    shift = 0 if live else 2
    for name in CLASS_NAMES:
        c = E["classes"][name]
        rows.append(["conversion", name, c["conversion_num"] + shift,
                     c["conversion_den"]])
    for name in CLASS_NAMES:
        c = E["classes"][name]
        rows.append(["reversal", name, c["reversal_num"] + shift,
                     c["reversal_den"]])
    for name in CLASS_NAMES:
        c = E["classes"][name]
        rows.append(["carry_quantum", name,
                     c["carry_quantum"] + (0 if live else 15)])
    for revision in range(1, E["top"] + 1):
        for name in CLASS_NAMES:
            rows.append(["ceiling", revision, name,
                         E["ceilings"][(revision, name)]
                         + (0 if live else 500)])
    index = 0
    while len(rows) < 214:
        station = E["stations"][index % len(E["stations"])]
        rows.append(["calibration", station["station"], station["class"],
                     (index * 37) % 900, "bench offset carried from survey"])
        index += 1
    return rows


def write_binaries(dest, E):
    older = "EPK-" + str(5000 + (int(E["dead_key"][4:]) - 2500) % 5000)
    live = _sheet_block(E, E["live_key"], True, E["dead_key"])
    dead = _sheet_block(E, E["dead_key"], False, older)
    order = [("Table B", dead), ("Table A", live)]
    if E["extended"]:
        order = [("Table B", live), ("Table A", dead)]
    # The first sheet's relationship points at the second worksheet part, so
    # a reader that pairs names with parts by position swaps the two names.
    write_xlsx(dest / "custody_parameter_workbook.xlsx", dict(order), parts=[2, 1])

    def kerned(text):
        """A resolution typeset as one kerned TJ array, broken inside its
        subject so that no fragment reads as a resolution of its own."""
        head, _sep, tail = text.partition(" = ")
        cut = len(head) - 5
        return [head[:cut], head[cut:] + " =", " " + tail]

    lines = ["CUSTODY BOARD OF THE BEAMTIME FACILITY",
             "MINUTES OF THE SITTINGS THAT GOVERN EPOCH " + str(E["epoch_id"]),
             "",
             "A resolution carries the sitting that adopted it. Where two",
             "sittings carry the same subject the later sitting governs. A",
             "line marked RESCINDED carries no force at all.",
             ""]
    ceiling = E["round_ceiling"]
    early_floor = ("RESOLUTION 013 SITTING 03 settlement floor cu = "
                   + str(E["settlement_floor"] - 3000))
    late_floor = ("RESOLUTION 023 SITTING 07 settlement floor cu = "
                  + str(E["settlement_floor"]))
    lines.append("RESOLUTION 004 SITTING 02 revalidation round ceiling = "
                 + str(ceiling + 4))
    lines.append("RESOLUTION 006 SITTING 02 implausible quantity ceiling cu = "
                 + str(E["implausible"] + 40000))
    lines.append("RESCINDED RESOLUTION 009 SITTING 06 revalidation round "
                 "ceiling = " + str(ceiling + 9))
    lines.append("RESOLUTION 011 SITTING 07 revalidation round ceiling = "
                 + str(ceiling))
    if E["extended"]:
        lines.append("RESOLUTION 041 SITTING 05 revalidation round ceiling = "
                     + str(ceiling + 2))
    lines.append(late_floor if E["extended"] else early_floor)
    lines.append("RESOLUTION 019 SITTING 07 implausible quantity ceiling cu = "
                 + str(E["implausible"]))
    lines.append(early_floor if E["extended"] else late_floor)
    lines.append("RESCINDED RESOLUTION 027 SITTING 09 settlement floor cu = 0")
    lines.append("RESOLUTION 031 SITTING 07 window end boundary = exclusive")
    lines.append("RESOLUTION 037 SITTING 07 watermark meaning = state after "
                 "the position it names")
    lines.append("")
    lines.append("APPENDIX A. SITTING REGISTER AND STATION OBSERVING RETURNS")
    lines.append("row station sitting sessions minutes note")
    for index, station in enumerate(E["stations"], start=1):
        sitting = ((index * 3) % 9) + 1
        lines.append("APPENDIX A ROW " + str(index).rjust(3, "0")
                     + " station " + station["station"]
                     + " sitting " + str(sitting).rjust(2, "0")
                     + " sessions " + str((index * 7) % 40 + 1)
                     + " minutes " + str((index * 53) % 900 + 30)
                     + " return lodged by the " + station["region"] + " desk")
    lines = [kerned(line) if line.startswith("RESCINDED ")
             or (line.startswith("RESOLUTION ") and " SITTING 07 " in line)
             else line for line in lines]
    write_pdf(dest / "custody_board_memo.pdf", lines)

    blocks = [("h", "DIRECTIVE ON PRECEDENCE, COMPENSATION AND CLOSURE"),
              ("p", "Issued for epoch " + str(E["epoch_id"]) + " by the "
                    "custody desk. The ladder below orders the pending queue "
                    "each time it is offered again."),
              ("table", [["level", "1", "scope rank, mandatory before standard"],
                         ["level", "2", "region rank on the reporting roster"],
                         ["level", "3", "normalised quantity ascending"],
                         ["level", "4", "canonical position ascending"],
                         ["level", "5", "event identifier ascending"]]),
              ("p", "DUPLICATE TARGET RULE: a target is reversed exactly once "
                    "however many compensating events name it, and every later "
                    "compensation on that target is recorded as void with no "
                    "effect on state or on any counter."),
              ("p", "DEPENDENCY CLOSURE RULE: a dependency whose canonical "
                    "position stands before the replay window is already "
                    "folded into the restored checkpoint and is satisfied "
                    "without being replayed again."),
              ("p", "CLAUSE REGISTER"),
              ]
    clauses = [["clause", "station", "region", "sitting", "force"]]
    for index, station in enumerate(E["stations"], start=1):
        clauses.append(["C-" + str(index).rjust(4, "0"), station["station"],
                        station["region"], str(((index * 5) % 9) + 1),
                        "in force" if index % 11 else "withdrawn"])
    blocks.append(("table", clauses))
    write_docx(dest / "precedence_directive.docx", blocks)


def write_checkpoints(dest, E, snaps, decoys, ledger_at, past_ledger=None):
    """The checkpoint register and the bodies it points at.

    Only a checkpoint the register offers as usable carries the state the
    forward pass reached. Every other row points at the state the same pass
    reaches under the decoy readings: a plausible body with a digest of its
    own, which keeps the forward pass state of every other position out of
    the agent's reach. The row at ledger_at is usable in every respect but
    its applied ledger, which runs past its watermark in the canonical
    order. In a minted epoch past_ledger names one position at or after the
    end boundary and an identifier that sits after it, so that body fails
    the ledger test and the end boundary test together and the order the
    tests run in decides the reason it is rejected under."""
    frozen = E["frozen"]
    top = E["top"]
    usable_positions = E["usable"]
    bodies = []
    rows = []
    for position in sorted(snaps):
        cid = "CKP-" + str(position).rjust(4, "0")
        body = dict(snaps[position] if position in usable_positions
                    else decoys[position])
        body["checkpoint_id"] = cid
        if past_ledger is not None and position == past_ledger[0]:
            body["applied"] = sorted(list(body["applied"]) + [past_ledger[1]])
        bodies.append(body)
        lodged_digest = ref_digest(body)
        if position in usable_positions or position == ledger_at:
            rows.append([cid, position, "sealed", lodged_digest, 1,
                         "sealed at the close of the sitting"])
        elif position >= END_POSITION and E["extended"] and position % 4 == 0:
            rows.append([cid, position, "sealed",
                         "0" * 8 + lodged_digest[8:], 1,
                         "sealed after the end boundary against a moved body"])
        elif position >= END_POSITION:
            rows.append([cid, position, "sealed", lodged_digest, 1,
                         "sealed after the requested end boundary"])
        elif position % 4 == 0:
            rows.append([cid, position, "sealed",
                         "0" * 8 + lodged_digest[8:], 1,
                         "sealed against a body that has since moved"])
        elif position % 4 == 1:
            rows.append([cid, position, "sealed", lodged_digest, frozen + 1,
                         "lodged above the frozen register revision"])
        elif position % 4 == 2:
            rows.append([cid, position, "void", lodged_digest, 1,
                         "voided by the desk"])
        else:
            rows.append([cid, position, "draft", lodged_digest, 1,
                         "held in draft"])
    for i in range(30):
        rows.append(["CKP-9" + str(100 + i), 900 + i, "sealed",
                     "f" * 64, 1, "register row with no body lodged"])
    if E["extended"]:
        rows.append(["CKP-8001", 50, "void", "f" * 64, top,
                     "voided above the frozen register revision"])
        rows.append(["CKP-8002", 51, "draft", "f" * 64, 1,
                     "held in draft with no body lodged"])
    write_jsonl(dest / "checkpoint_states.jsonl", bodies)
    write_delim(dest / "checkpoint_register.csv",
                ["checkpoint_id", "position", "status", "state_digest",
                 "revision", "note"], rows, ",")
    return bodies


def write_archive(dest, E, bodies):
    """The archive reads its counts off the lodged bodies, holds two counters
    off the body, and lodged the rows of each usable checkpoint twice."""
    counters = []
    positions = []
    for body in bodies:
        cid = body["checkpoint_id"]
        position = int(body["position"])
        positions.append([cid, position, len(body["balances"]),
                          len(body["applied"])])
        if position % 9 and position not in E["usable"]:
            continue
        lodged = []
        for name in COUNTER_NAMES:
            value = int(body["counters"][name])
            if name == "grants":
                value -= 2
            elif name == "spilled_cu":
                value += 7
            lodged.append([cid, name, value])
        counters.extend(lodged * (2 if position in E["usable"] else 1))
    write_sqlite(dest / "prior_epoch_archive.db", {
        "prior_counters": (["checkpoint_id", "counter", "value"], counters),
        "prior_positions": (["checkpoint_id", "position", "station_count",
                             "applied_count"], positions),
    })


def write_project(dest):
    """The package as the facility currently runs it."""
    stamp = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(dest / "project.zip", "w",
                         zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(PACKAGE_FILES):
            text = PACKAGE_FILES[name]
            for _code, member, correct, broken in DEFECTS:
                if member != name:
                    continue
                if text.count(correct) != 1:
                    raise SystemExit("defect anchor is not unique in " + name)
                text = text.replace(correct, broken)
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, text)


def write_corpus(dest, seed=None):
    """Mint one epoch into dest. Called by the module entry point to rebuild
    the shipped corpus, and by the graded tests to mint epochs the agent has
    never seen."""
    dest = Path(dest)
    if dest.name != "data":
        dest = dest / "data"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    E = mint(SAMPLE_SEED if seed is None else seed)
    write_papers(dest, E)
    write_tables(dest, E)
    write_binaries(dest, E)
    write_project(dest)
    tune_counter_fixtures(dest, E)
    ctx = ref_context(dest)
    snaps = ref_snapshots(ctx, SNAPSHOT_LIMIT)
    decoy = ref_context(dest, DECOY_READINGS)
    decoys = ref_snapshots(decoy, SNAPSHOT_LIMIT)
    ledger_at = int(decoy["by_id"][E["ledger_anchor"]]["position"])
    if all(int(ctx["by_id"][eid]["position"]) <= ledger_at
           for eid in decoys[ledger_at]["applied"]):
        raise SystemExit("the ledger decoy does not run past its watermark")
    past_ledger = None
    if E["extended"]:
        past_at = END_POSITION + 1
        past_ledger = (past_at, ctx["events"][past_at]["event_id"])
    bodies = write_checkpoints(dest, E, snaps, decoys, ledger_at, past_ledger)
    write_archive(dest, E, bodies)
    return dest


def tune_counter_fixtures(dest, E):
    """Set each counter fixture one above the counter its forward pass offer
    reads, so it waits under the reading in force and lands at that offer
    when the derived reversal is left out."""
    ctx = ref_context(dest)
    for event_id, counter in E["counter_fixtures"]:
        at = int(ctx["by_id"][event_id]["position"])
        held = replay(ctx, 1, at, None, run_rounds=False)["state"].counters[counter]
        E["events"][int(event_id[4:]) - 1]["requires"] = (
            "counter_at_least:" + counter + ":" + str(held + 1))
    write_journals(dest, E)
    naive = ref_context(dest, ("R_NO_DERIVED_REVERSAL",))
    for event_id, _counter in E["counter_fixtures"]:
        at = int(naive["by_id"][event_id]["position"])
        if event_id not in replay(naive, 1, at + 1, None,
                                  run_rounds=False)["state"].applied:
            raise SystemExit("a counter fixture does not separate the derived reversal")


# --------------------------------------------------------------------------
# the defects the shipped package carries
#
# One entry per catalogued defect: the module it sits in, the block the
# repaired package holds, and the block the shipped package holds instead.
# The corpus writer turns the repaired source into the shipped source by
# applying each pair in reverse, so the two can never drift apart.
# --------------------------------------------------------------------------
def _b(*lines):
    return NL.join(lines) + NL


DEFECTS = (
    ("DFC-01", "src/bcrep/window.py",
     _b("    window_start = max(int(start), int(watermark) + 1)"),
     _b("    window_start = max(int(start), int(watermark))")),
    ("DFC-02", "src/bcrep/replay.py",
     _b("        if str(rec[" + Q + "kind" + Q + "]).strip() == "
        + Q + "compensate" + Q + ":",
        "            compensation.apply_compensation(ctx, state, rec, register, order)",
        "            continue"),
     _b("        if str(rec[" + Q + "kind" + Q + "]).strip() == "
        + Q + "compensate" + Q + ":",
        "            link = ctx[" + Q + "links" + Q + "][rec[" + Q + "event_id" + Q + "]]",
        "            named = ctx[" + Q + "by_id" + Q + "][link[" + Q
        + "target_event_id" + Q + "].strip()]",
        "            if int(named[" + Q + "position" + Q + "]) < window_start:",
        "                quarantine.append({" + Q + "event_id" + Q + ": rec["
        + Q + "event_id" + Q + "],",
        "                                   " + Q + "position" + Q + ": p,",
        "                                   " + Q + "stage" + Q + ": " + Q + "r09" + Q + ",",
        "                                   " + Q + "reason_code" + Q + ": "
        + Q + "CMP-NOTARGET" + Q + ",",
        "                                   " + Q + "detail" + Q + ": str(rec["
        + Q + "kind" + Q + "])})",
        "                continue",
        "            compensation.apply_compensation(ctx, state, rec, register, order)",
        "            continue")),
    ("DFC-03", "src/bcrep/replay.py",
     _b("        ceiling = int(ctx[" + Q + "params" + Q + "][" + Q
        + "round_ceiling" + Q + "])"),
     _b("        ceiling = 1")),
    ("DFC-04", "src/bcrep/compensation.py",
     _b("    counter = ctx[" + Q + "params" + Q + "][" + Q + "counter_map"
        + Q + "][kind]",
        "    state[" + Q + "counters" + Q + "][counter] -= reversed_cu",
        "    state[" + Q + "counters" + Q + "][kind + " + Q + "s" + Q + "] -= 1",
        "    state[" + Q + "counters" + Q + "][" + Q + "reversed_cu" + Q
        + "] += reversed_cu"),
     _b("    state[" + Q + "counters" + Q + "][" + Q + "reversed_cu" + Q
        + "] += reversed_cu")),
    ("DFC-05", "src/bcrep/window.py",
     _b("    positions = [p for p in range(window_start, min(window_end, total + 1))]"),
     _b("    positions = [p for p in range(window_start, min(window_end, total) + 1)]")),
    ("DFC-06", "src/bcrep/derived.py",
     _b("    state[" + Q + "balances" + Q + "] = dict(body[" + Q + "balances" + Q + "])",
        "    state[" + Q + "allotments" + Q + "] = {k: dict(v) for k, v in body["
        + Q + "allotments" + Q + "].items()}"),
     _b("    state[" + Q + "balances" + Q + "] = body[" + Q + "balances" + Q + "]",
        "    state[" + Q + "allotments" + Q + "] = body[" + Q + "allotments" + Q + "]")),
    ("DFC-07", "src/bcrep/ordering.py",
     _b("    events.sort(key=lambda r: (int(r[" + Q + "sequence" + Q + "]), int(r["
        + Q + "stamp" + Q + "]),",
        "                               int(r[" + Q + "rank" + Q + "]), str(r["
        + Q + "tiebreak" + Q + "]),",
        "                               str(r[" + Q + "event_id" + Q + "])))"),
     _b("    events.sort(key=lambda r: (int(r[" + Q + "sequence" + Q + "]), int(r["
        + Q + "stamp" + Q + "])))")),
    ("DFC-08", "src/bcrep/ordering.py",
     _b("        source = str(rec.get(" + Q + "source" + Q + ") or " + Q + Q
        + ").strip()",
        "        if source == " + Q + Q + ":",
        "            source = provenance.get(eid, {}).get(rec[" + Q + "lodged_in"
        + Q + "], " + Q + Q + ")"),
     _b("        source = str(rec.get(" + Q + "source" + Q + ") or " + Q + Q
        + ").strip()")),
    ("DFC-09", "src/bcrep/depends.py",
     _b("        if pos < window_start:",
        "            sources.append((dep, " + Q + "checkpoint" + Q + "))"),
     _b("        if pos < window_start:",
        "            return " + Q + "DEP-MISSING" + Q + ", sources")),
    ("DFC-10", "src/bcrep/compensation.py",
     _b("    if target_id in state[" + Q + "reversed" + Q + "]:",
        "        row[" + Q + "disposition" + Q + "] = " + Q + "void_duplicate" + Q,
        "        register.append(row)",
        "        return",
        "    if target_id not in state[" + Q + "applied" + Q + "]:"),
     _b("    if target_id not in state[" + Q + "applied" + Q + "]:")),
    ("DFC-11", "src/bcrep/compensation.py",
     _b("    reversed_cu = normalise.half_up(",
        "        Fraction(quantity) * Fraction(factors[" + Q + "reversal_num" + Q + "],",
        "                                      factors[" + Q + "reversal_den" + Q + "]))"),
     _b("    reversed_cu = round(quantity * factors[" + Q + "reversal_num" + Q + "]",
        "                        / factors[" + Q + "reversal_den" + Q + "])")),
    ("DFC-12", "src/bcrep/derived.py",
     _b("        quantum = params[" + Q + "classes" + Q + "].get(cls, {}).get("
        + Q + "carry_quantum" + Q + ")"),
     _b("        quantum = 50")),
    ("DFC-13", "src/bcrep/normalise.py",
     _b("    stations = latest_by(reading.read_delim(root / " + Q
        + "station_register_frozen.csv" + Q + "),"),
     _b("    stations = latest_by(reading.read_delim(root / " + Q
        + "station_register_current.csv" + Q + "),")),
    ("DFC-14", "src/bcrep/replay.py",
     _b("            queue = sorted(state[" + Q + "pending" + Q + "],",
        "                           key=lambda eid: precedence_key(ctx, ctx["
        + Q + "by_id" + Q + "][eid]))"),
     _b("            queue = list(state[" + Q + "pending" + Q + "])")),
    ("DFC-14", "src/bcrep/replay.py",
     _b("def precedence_key(ctx, rec):",
        "    " + Q + Q + Q
           + "The five level ladder the directive puts in force: scope, then the",
        "    region rank on the roster, then the normalised quantity, then the",
        "    canonical position, then the event identifier." + Q + Q + Q,
        "    scope_rank = 0 if str(rec.get(" + Q + "scope" + Q + ", " + Q + "standard"
           + Q + ")) == " + Q + "mandatory" + Q + " else 1",
        "    station = ctx[" + Q + "stations" + Q + "].get(str(rec[" + Q + "station" + Q
           + "]).strip())",
        "    region = str(station[" + Q + "region" + Q + "]).strip() if station else "
           + Q + Q,
        "    region_rank = ctx[" + Q + "params" + Q + "][" + Q + "regions" + Q
           + "].get(region, 99)",
        "    quantity = ctx[" + Q + "norm" + Q + "].get(rec[" + Q + "event_id" + Q
           + "]) or 0",
        "    return (scope_rank, region_rank, quantity, int(rec[" + Q + "position" + Q
           + "]),",
        "            str(rec[" + Q + "event_id" + Q + "]))",
        "",
        "",
        "def run(ctx, start, end, body=None, run_rounds=True):"),
     _b("def run(ctx, start, end, body=None, run_rounds=True):")),
    ("DFC-15", "src/bcrep/reading.py",
     _b("        wb = ET.fromstring(zf.read(" + Q + "xl/workbook.xml" + Q + "))",
        "        rels = ET.fromstring(zf.read(" + Q + "xl/_rels/workbook.xml.rels" + Q
           + "))",
        "        targets = {rel.attrib.get(" + Q + "Id" + Q + "): rel.attrib.get(" + Q
           + "Target" + Q + ", " + Q + Q + ")",
        "                   for rel in rels.iter() if rel.tag.endswith(" + Q
           + "}Relationship" + Q + ")}",
        "        rid = (" + Q
           + "{http://schemas.openxmlformats.org/officeDocument/2006/" + Q,
        "               " + Q + "relationships}id" + Q + ")",
        "        out = {}",
        "        for sh in wb.iter():",
        "            if not sh.tag.endswith(" + Q + "}sheet" + Q + "):",
        "                continue",
        "            target = targets.get(sh.attrib.get(rid), " + Q + Q + ")",
        "            member = target[1:] if target.startswith(" + Q + "/" + Q
           + ") else " + Q + "xl/" + Q + " + target",
        "            if member not in zf.namelist():",
        "                continue",
        "            out[sh.attrib.get(" + Q + "name" + Q
           + ")] = _sheet_rows(zf.read(member), shared)",
        "        return out"),
     _b("        wb = ET.fromstring(zf.read(" + Q + "xl/workbook.xml" + Q + "))",
        "        names = []",
        "        for sh in wb.iter():",
        "            if sh.tag.endswith(" + Q + "}sheet" + Q + "):",
        "                names.append(sh.attrib.get(" + Q + "name" + Q + "))",
        "        out = {}",
        "        for idx, name in enumerate(names, start=1):",
        "            member = " + Q + "xl/worksheets/sheet" + Q + " + str(idx) + " + Q
           + ".xml" + Q,
        "            if member not in zf.namelist():",
        "                continue",
        "            out[name] = _sheet_rows(zf.read(member), shared)",
        "        return out")),
    ("DFC-16", "src/bcrep/reading.py",
     _b("def _shown_text(content):",
        "    " + Q + Q + Q
           + "One line per text showing operator: the string a Tj shows, and the",
        "    strings of a TJ array joined in order, its kerning numbers dropped." + Q
           + Q + Q,
        "    lines = []",
        "    operands = []",
        "    array = None",
        "    at = 0",
        "    while at < len(content):",
        "        ch = content[at]",
        "        if ch == " + Q + "(" + Q + ":",
        "            text, at = _pdf_string(content, at)",
        "            (operands if array is None else array).append(text)",
        "        elif ch == " + Q + "[" + Q + ":",
        "            array = []",
        "            at += 1",
        "        elif ch == " + Q + "]" + Q + ":",
        "            operands.append(array)",
        "            array = None",
        "            at += 1",
        "        elif ch.isspace():",
        "            at += 1",
        "        else:",
        "            end = at",
        "            while (end < len(content) and not content[end].isspace()",
        "                   and content[end] not in " + Q + "()[]" + Q + "):",
        "                end += 1",
        "            word = content[at:end]",
        "            at = end",
        "            if word == " + Q + "Tj" + Q
           + " and operands and isinstance(operands[-1], str):",
        "                lines.append(operands[-1])",
        "            elif word == " + Q + "TJ" + Q
           + " and operands and isinstance(operands[-1], list):",
        "                lines.append(" + Q + Q + ".join(operands[-1]))",
        "            if word[:1].isalpha():",
        "                operands = []",
        "    return lines",
        "",
        "",
        "def read_pdf_lines(path):",
        "    out = []",
        "    for content in _pdf_streams(Path(path).read_bytes()):",
        "        out.extend(_shown_text(content))"),
     _b("def _strings(content):",
        "    " + Q + Q + Q + "The text a content stream shows, one string per line." + Q
           + Q + Q,
        "    out = []",
        "    at = 0",
        "    while at < len(content):",
        "        if content[at] == " + Q + "(" + Q + ":",
        "            text, at = _pdf_string(content, at)",
        "            out.append(text)",
        "        else:",
        "            at += 1",
        "    return out",
        "",
        "",
        "def read_pdf_lines(path):",
        "    out = []",
        "    for content in _pdf_streams(Path(path).read_bytes()):",
        "        out.extend(_strings(content))")),
    ("DFC-17", "src/bcrep/transitions.py",
     _b("from . import derived, reading",
        "",
        "# The vocabulary as first lodged, read when no register is handed over.",
        "DEFAULT_FORMS = {",
        "    " + Q + "balance_at_least" + Q + ": (" + Q + "active" + Q + ", [" + Q
           + "station" + Q + ", " + Q + "amount_cu" + Q + "]),",
        "    " + Q + "allotment_below" + Q + ": (" + Q + "active" + Q + ", [" + Q
           + "station" + Q + ", " + Q + "programme" + Q + ", " + Q + "amount_cu" + Q
           + "]),",
        "    " + Q + "counter_at_least" + Q + ": (" + Q + "active" + Q + ", [" + Q
           + "counter" + Q + ", " + Q + "amount" + Q + "]),",
        "    " + Q + "no_pending" + Q + ": (" + Q + "active" + Q + ", []),",
        "    " + Q + "station_active" + Q + ": (" + Q + "active" + Q + ", [" + Q
           + "station" + Q + "]),",
        "}",
        "",
        "",
        "def predicate_forms(root, frozen):",
        "    " + Q + Q + Q
           + "The predicate register in force. For each form the row with the",
        "    greatest revision at or below the frozen revision gives its status and",
        "    the order its arguments are written in." + Q + Q + Q,
        "    held = {}",
        "    for row in reading.read_delim(root / " + Q + "eligibility_predicates.csv"
           + Q + "):",
        "        revision = int(str(row[" + Q + "revision" + Q + "]).strip())",
        "        if revision > frozen:",
        "            continue",
        "        name = row[" + Q + "predicate_id" + Q + "].strip()",
        "        if name not in held or revision >= held[name][0]:",
        "            held[name] = (revision, row)",
        "    return {name: (row[" + Q + "status" + Q + "].strip(), row[" + Q + "form"
           + Q + "].strip().split(" + Q + ":" + Q + ")[1:])",
        "            for name, (_revision, row) in held.items()}",
        "",
        "",
        "def predicate_holds(text, state, stations, forms=None):",
        "    " + Q + Q + Q
           + "A predicate names its form and then its arguments in the order the",
        "    form in force lists them, read against the state as it stands immediately",
        "    before the event is offered. A form the register does not carry as",
        "    active is false whenever it is read." + Q + Q + Q,
        "    if not text:",
        "        return True",
        "    parts = str(text).split(" + Q + ":" + Q + ")",
        "    head = parts[0]",
        "    status, names = (DEFAULT_FORMS if forms is None else forms).get(",
        "        head, (" + Q + Q + ", []))",
        "    if status != " + Q + "active" + Q + " or len(parts) - 1 != len(names):",
        "        return False",
        "    args = dict(zip(names, parts[1:]))",
        "    if head == " + Q + "balance_at_least" + Q + ":",
        "        return (state[" + Q + "balances" + Q + "].get(args[" + Q + "station"
           + Q + "], 0)",
        "                >= int(args[" + Q + "amount_cu" + Q + "]))",
        "    if head == " + Q + "allotment_below" + Q + ":",
        "        inner = state[" + Q + "allotments" + Q + "].get(args[" + Q + "station"
           + Q + "], {})",
        "        return inner.get(args[" + Q + "programme" + Q + "], 0) < int(args[" + Q
           + "amount_cu" + Q + "])",
        "    if head == " + Q + "counter_at_least" + Q + ":",
        "        return state[" + Q + "counters" + Q + "].get(args[" + Q + "counter" + Q
           + "], 0) >= int(args[" + Q + "amount" + Q + "])",
        "    if head == " + Q + "no_pending" + Q + ":",
        "        return not state[" + Q + "pending" + Q + "]",
        "    if head == " + Q + "station_active" + Q + ":",
        "        row = stations.get(args[" + Q + "station" + Q + "])",
        "        return row is not None and str(row[" + Q + "status" + Q
           + "]).strip() == " + Q + "active" + Q,
        "    return False",
        "",
        "",
        "def admissible(ctx, state, rec):",
        "    if " + Q + "forms" + Q + " not in ctx:",
        "        ctx[" + Q + "forms" + Q + "] = predicate_forms(ctx[" + Q + "root" + Q
           + "], ctx[" + Q + "frozen" + Q + "])",
        "    return predicate_holds(rec.get(" + Q + "requires" + Q + "), state, ctx["
           + Q + "stations" + Q + "],",
        "                           ctx[" + Q + "forms" + Q + "])"),
     _b("from . import derived",
        "",
        "",
        "def predicate_holds(text, state, stations):",
        "    " + Q + Q + Q
           + "The closed predicate vocabulary, read against the state as it stands",
        "    immediately before the event is offered." + Q + Q + Q,
        "    if not text:",
        "        return True",
        "    parts = str(text).split(" + Q + ":" + Q + ")",
        "    head = parts[0]",
        "    if head == " + Q + "balance_at_least" + Q + ":",
        "        return state[" + Q + "balances" + Q
           + "].get(parts[1], 0) >= int(parts[2])",
        "    if head == " + Q + "allotment_below" + Q + ":",
        "        inner = state[" + Q + "allotments" + Q + "].get(parts[1], {})",
        "        return inner.get(parts[2], 0) < int(parts[3])",
        "    if head == " + Q + "counter_at_least" + Q + ":",
        "        return state[" + Q + "counters" + Q
           + "].get(parts[1], 0) >= int(parts[2])",
        "    if head == " + Q + "no_pending" + Q + ":",
        "        return not state[" + Q + "pending" + Q + "]",
        "    if head == " + Q + "station_active" + Q + ":",
        "        row = stations.get(parts[1])",
        "        return row is not None and str(row[" + Q + "status" + Q
           + "]).strip() == " + Q + "active" + Q,
        "    return False",
        "",
        "",
        "def admissible(ctx, state, rec):",
        "    return predicate_holds(rec.get(" + Q + "requires" + Q + "), state, ctx["
           + Q + "stations" + Q + "])")),
    ("DFC-18", "src/bcrep/depends.py",
     _b("def cycle_members(events, edges, by_id):",
        "    " + Q + Q + Q
           + "Every event some path of edges leads back to: the members of each",
        "    strongly connected group of two or more, and every event with a self",
        "    edge. Edges naming an identifier outside the history take no part." + Q + Q
           + Q,
        "    order = {}",
        "    low = {}",
        "    stack = []",
        "    on_stack = set()",
        "    found = set()",
        "",
        "    def visit(node):",
        "        order[node] = low[node] = len(order)",
        "        stack.append(node)",
        "        on_stack.add(node)",
        "        for nxt in edges.get(node, []):",
        "            if nxt not in by_id:",
        "                continue",
        "            if nxt not in order:",
        "                visit(nxt)",
        "                low[node] = min(low[node], low[nxt])",
        "            elif nxt in on_stack:",
        "                low[node] = min(low[node], order[nxt])",
        "        if low[node] != order[node]:",
        "            return",
        "        group = []",
        "        while True:",
        "            member = stack.pop()",
        "            on_stack.discard(member)",
        "            group.append(member)",
        "            if member == node:",
        "                break",
        "        if len(group) > 1 or node in edges.get(node, []):",
        "            found.update(group)",
        "",
        "    for rec in events:",
        "        if rec[" + Q + "event_id" + Q + "] not in order:",
        "            visit(rec[" + Q + "event_id" + Q + "])",
        "    return found"),
     _b("def cycle_members(events, edges, by_id):",
        "    found = set()",
        "    stack = []",
        "    seen = {}",
        "",
        "    def walk(node):",
        "        seen[node] = 1",
        "        stack.append(node)",
        "        for nxt in edges.get(node, []):",
        "            if nxt not in by_id:",
        "                continue",
        "            if seen.get(nxt) == 1:",
        "                cut = stack.index(nxt)",
        "                for member in stack[cut:]:",
        "                    found.add(member)",
        "            elif seen.get(nxt) is None:",
        "                walk(nxt)",
        "        stack.pop()",
        "        seen[node] = 2",
        "",
        "    for rec in events:",
        "        if seen.get(rec[" + Q + "event_id" + Q + "]) is None:",
        "            walk(rec[" + Q + "event_id" + Q + "])",
        "    return found")),
    ("DFC-19", "src/bcrep/publish.py",
     _b("    archive = reading.read_sqlite_table(root / " + Q + "prior_epoch_archive.db"
           + Q + ",",
        "                                        " + Q + "prior_counters" + Q + ")",
        "    history = reading.read_delim(root / " + Q + "allotment_ceiling_history.tsv"
           + Q + ", TAB)",
        "    deltas = {}",
        "    historic_total = 0",
        "    declared = " + Q + Q,
        "    recomputed = " + Q + Q,
        "    if chosen:",
        "        for name in derived.COUNTER_NAMES:",
        "            held = [int(row[" + Q + "value" + Q + "]) for row in archive",
        "                    if str(row[" + Q + "checkpoint_id" + Q
           + "]).strip() == chosen[1]",
        "                    and str(row[" + Q + "counter" + Q + "]).strip() == name]",
        "            if held:",
        "                deltas[name] = held[-1] - int(chosen[2][" + Q + "counters" + Q
           + "].get(name, 0))",
        "        declared = chosen[3][" + Q + "state_digest" + Q + "].strip()",
        "        recomputed = derived.state_digest(chosen[2])",
        "        checkpoint_revision = _int(chosen[3][" + Q + "revision" + Q + "])",
        "        historic_total = sum(_int(row[" + Q + "ceiling_cu" + Q
           + "]) for row in history",
        "                             if _int(row[" + Q + "revision" + Q
           + "]) == checkpoint_revision)"),
     _b("    archive = {}",
        "    for row in reading.read_sqlite_table(root / " + Q
           + "prior_epoch_archive.db" + Q + ",",
        "                                         " + Q + "prior_counters" + Q + "):",
        "        archive[(row[" + Q + "checkpoint_id" + Q + "], row[" + Q + "counter"
           + Q + "])] = int(row[" + Q + "value" + Q + "])",
        "    history = {}",
        "    for row in reading.read_delim(root / " + Q
           + "allotment_ceiling_history.tsv" + Q + ", TAB):",
        "        history[(_int(row[" + Q + "revision" + Q + "]), row[" + Q + "class" + Q
           + "].strip())] = _int(",
        "            row[" + Q + "ceiling_cu" + Q + "])",
        "    deltas = {}",
        "    historic_total = 0",
        "    declared = " + Q + Q,
        "    recomputed = " + Q + Q,
        "    if chosen:",
        "        for name in derived.COUNTER_NAMES:",
        "            held = archive.get((chosen[1], name))",
        "            if held is not None:",
        "                deltas[name] = held - int(chosen[2][" + Q + "counters" + Q
           + "].get(name, 0))",
        "        declared = chosen[3][" + Q + "state_digest" + Q + "].strip()",
        "        recomputed = derived.state_digest(chosen[2])",
        "        checkpoint_revision = _int(chosen[3][" + Q + "revision" + Q + "])",
        "        historic_total = sum(v for (rev, _cls), v in history.items()",
        "                             if rev == checkpoint_revision)")),
    ("DFC-20", "src/bcrep/compensation.py",
     _b("    lodged = normalise.latest_by(",
        "        reading.read_delim(ctx[" + Q + "root" + Q + "] / " + Q
           + "station_register_frozen.csv" + Q + "),",
        "        " + Q + "station" + Q + ", " + Q + "revision" + Q + ", int(target[" + Q
           + "revision" + Q + "]))",
        "    held = lodged.get(str(target[" + Q + "station" + Q + "]).strip())",
        "    klass = str(held[" + Q + "class" + Q + "]).strip() if held else ctx[" + Q
           + "cls" + Q + "][target_id]"),
     _b("    klass = ctx[" + Q + "cls" + Q + "][target_id]")),
    ("DFC-21", "src/bcrep/checkpointing.py",
     _b("        watermark = int(body[" + Q + "position" + Q + "])",
        "        if any(eid not in ctx[" + Q + "by_id" + Q + "]",
        "               or int(ctx[" + Q + "by_id" + Q + "][eid][" + Q + "position" + Q
           + "]) > watermark",
        "               for eid in body[" + Q + "applied" + Q + "]):",
        "            rejected.append({" + Q + "checkpoint_id" + Q + ": cid,",
        "                             " + Q + "reason" + Q + ": " + Q
           + "ledger_past_watermark" + Q + "})",
        "            continue",
        "        if int(body[" + Q + "position" + Q + "]) >= int(end):"),
     _b("        if int(body[" + Q + "position" + Q + "]) >= int(end):")),
    ("DFC-22", "src/bcrep/ordering.py",
     _b("def later_epoch_prefix(root):",
        "    " + Q + Q + Q
           + "The identifier prefix data_lineage.md reserves for supplement rows",
        "    lodged for a later epoch." + Q + Q + Q,
        "    text = " + Q + " " + Q + ".join((root / " + Q + "data_lineage.md" + Q
           + ").read_text(encoding=" + Q + "utf-8" + Q + ").split())",
        "    marker = " + Q + "whose identifier begins `" + Q,
        "    at = text.find(marker)",
        "    if at < 0:",
        "        return None",
        "    begin = at + len(marker)",
        "    return text[begin:text.index(" + Q + "`" + Q + ", begin)]",
        "",
        "",
        "def load_events(root, frozen, alias):"),
     _b("def load_events(root, frozen, alias):")),
    ("DFC-22", "src/bcrep/ordering.py",
     _b("    raw = []",
        "    later = later_epoch_prefix(root)",
        "    for name in (" + Q + "event_journal.jsonl" + Q + ", " + Q
           + "event_supplement.ndjson" + Q + "):",
        "        for rec in reading.read_jsonl(root / name):",
        "            if (name == " + Q + "event_supplement.ndjson" + Q + " and later",
        "                    and str(rec[" + Q + "event_id" + Q
           + "]).strip().startswith(later)):",
        "                continue",
        "            rec = dict(rec)"),
     _b("    raw = []",
        "    for name in (" + Q + "event_journal.jsonl" + Q + ", " + Q
           + "event_supplement.ndjson" + Q + "):",
        "        for rec in reading.read_jsonl(root / name):",
        "            rec = dict(rec)")),
)


# --------------------------------------------------------------------------
# the repaired package source
#
# The corpus writer turns this tree into the shipped tree by
# applying every defect pair in reverse, so the repaired source
# and the shipped source can never drift apart.
# --------------------------------------------------------------------------
PACKAGE_FILES = {
    "pyproject.toml": "[project]\nname = \"bcrep\"\nversion = \"3.4.0\"\ndescription = \"Deterministic custody replay engine for the beamtime credit ledger.\"\nrequires-python = \">=3.12\"\ndependencies = []\n\n[build-system]\nrequires = [\"setuptools>=68\"]\nbuild-backend = \"setuptools.build_meta\"\n\n[tool.setuptools]\npackage-dir = {\"\" = \"src\"}\n",
    "src/bcrep/__init__.py": "\"\"\"bcrep: the deterministic custody replay engine.\n\nThe package reconstructs the credit state of one observation epoch from an\nappend only event journal, a sealed checkpoint and the working papers that\ngovern them, and publishes the epoch as a fixed set of documents.\n\"\"\"\nfrom pathlib import Path\n\nfrom . import publish\n\n__all__ = [\"run\", \"publish\"]\nVERSION = \"3.4.0\"\n\n\ndef run(data, out):\n    \"\"\"Replay one epoch out of the paper directory and publish it.\"\"\"\n    return publish.publish(Path(data), Path(out))\n",
    "src/bcrep/__main__.py": "\"\"\"Command line entry point.\n\n    python3 -m bcrep --data <papers> --out <destination>\n\nThe two options are accepted in either order. The destination is created when\nit is absent. The paper directory is only read.\n\"\"\"\nimport sys\nfrom pathlib import Path\n\nfrom . import run\n\n\ndef parse(argv):\n    data = None\n    out = None\n    index = 0\n    while index < len(argv):\n        token = argv[index]\n        if token == \"--data\" and index + 1 < len(argv):\n            data = argv[index + 1]\n            index += 2\n            continue\n        if token == \"--out\" and index + 1 < len(argv):\n            out = argv[index + 1]\n            index += 2\n            continue\n        raise SystemExit(\"usage: python3 -m bcrep --data DIR --out DIR\")\n    if data is None or out is None:\n        raise SystemExit(\"usage: python3 -m bcrep --data DIR --out DIR\")\n    return Path(data), Path(out)\n\n\ndef main(argv):\n    data, out = parse(argv)\n    out.mkdir(parents=True, exist_ok=True)\n    run(data, out)\n    return 0\n\n\nif __name__ == \"__main__\":\n    sys.exit(main(sys.argv[1:]))\n",
    "src/bcrep/checkpointing.py": "\"\"\"Stages r04 and r05. Checkpoint selection and restoration.\n\nA checkpoint that carries watermark N is the state after the event at\ncanonical position N was processed. Position N is therefore behind the\nengine, and the first candidate the window can replay is position N plus one.\n\"\"\"\nfrom . import derived, reading\n\n\ndef _int(text):\n    return int(str(text).strip())\n\n\ndef bodies(root):\n    out = {}\n    for rec in reading.read_jsonl(root / \"checkpoint_states.jsonl\"):\n        out[str(rec[\"checkpoint_id\"]).strip()] = rec\n    return out\n\n\ndef select(ctx, end):\n    \"\"\"Usable means sealed, present, digest matching, and standing strictly\n    before the requested end boundary. The greatest usable position wins.\"\"\"\n    root = ctx[\"root\"]\n    held = bodies(root)\n    usable = []\n    rejected = []\n    for row in reading.read_delim(root / \"checkpoint_register.csv\"):\n        cid = row[\"checkpoint_id\"].strip()\n        if _int(row[\"revision\"]) > ctx[\"frozen\"]:\n            rejected.append({\"checkpoint_id\": cid, \"reason\": \"draft_revision\"})\n            continue\n        if row[\"status\"].strip() != \"sealed\":\n            rejected.append({\"checkpoint_id\": cid, \"reason\": \"not_sealed\"})\n            continue\n        body = held.get(cid)\n        if body is None:\n            rejected.append({\"checkpoint_id\": cid, \"reason\": \"body_missing\"})\n            continue\n        if derived.state_digest(body) != row[\"state_digest\"].strip():\n            rejected.append({\"checkpoint_id\": cid, \"reason\": \"digest_mismatch\"})\n            continue\n        watermark = int(body[\"position\"])\n        if any(eid not in ctx[\"by_id\"]\n               or int(ctx[\"by_id\"][eid][\"position\"]) > watermark\n               for eid in body[\"applied\"]):\n            rejected.append({\"checkpoint_id\": cid,\n                             \"reason\": \"ledger_past_watermark\"})\n            continue\n        if int(body[\"position\"]) >= int(end):\n            rejected.append({\"checkpoint_id\": cid,\n                             \"reason\": \"position_at_or_after_end\"})\n            continue\n        usable.append((int(body[\"position\"]), cid, body, row))\n    usable.sort()\n    rejected.sort(key=lambda r: (r[\"checkpoint_id\"], r[\"reason\"]))\n    if not usable:\n        return None, [], rejected\n    return usable[-1], [c for _p, c, _b, _r in usable], rejected\n",
    "src/bcrep/compensation.py": "\"\"\"Stages r09 and r10. Compensating events.\n\nA compensating event names the event it reverses through the link register.\nThe named target is resolved against the whole canonical history, which\nreaches behind the restored checkpoint, and never against the replay window\nalone. Reversing a target does not remove it from history, and a target is\nreversed exactly once however many compensations name it.\n\"\"\"\nfrom fractions import Fraction\n\nfrom . import derived, normalise, reading\n\n\ndef _int(text):\n    return int(str(text).strip())\n\n\ndef load_links(root, frozen):\n    best = {}\n    for row in reading.read_delim(root / \"compensation_links.csv\"):\n        if _int(row[\"revision\"]) > frozen:\n            continue\n        key = row[\"compensation_id\"].strip()\n        prior = best.get(key)\n        if prior is None or _int(row[\"revision\"]) >= _int(prior[\"revision\"]):\n            best[key] = row\n    return best\n\n\ndef apply_compensation(ctx, state, rec, register, order):\n    eid = rec[\"event_id\"]\n    link = ctx[\"links\"][eid]\n    target_id = link[\"target_event_id\"].strip()\n    target = ctx[\"by_id\"][target_id]\n    row = {\"compensation_id\": eid, \"target_event_id\": target_id,\n           \"target_position\": int(target[\"position\"]),\n           \"disposition\": \"\", \"reversed_cu\": 0, \"applied_order\": 0}\n    if target_id in state[\"reversed\"]:\n        row[\"disposition\"] = \"void_duplicate\"\n        register.append(row)\n        return\n    if target_id not in state[\"applied\"]:\n        row[\"disposition\"] = \"void_unapplied\"\n        register.append(row)\n        return\n    quantity = ctx[\"norm\"][target_id]\n    lodged = normalise.latest_by(\n        reading.read_delim(ctx[\"root\"] / \"station_register_frozen.csv\"),\n        \"station\", \"revision\", int(target[\"revision\"]))\n    held = lodged.get(str(target[\"station\"]).strip())\n    klass = str(held[\"class\"]).strip() if held else ctx[\"cls\"][target_id]\n    factors = ctx[\"params\"][\"classes\"][klass]\n    station = str(target[\"station\"]).strip()\n    programme = str(target[\"programme\"]).strip()\n    touched = {station}\n    kind = str(target[\"kind\"]).strip()\n    if kind == \"grant\":\n        derived.move(state, station, programme, -quantity)\n    elif kind == \"retire\":\n        derived.move(state, station, programme, quantity)\n    else:\n        other = str(target[\"counterparty\"]).strip()\n        derived.move(state, station, programme, quantity)\n        derived.move(state, other, programme, -quantity)\n        touched.add(other)\n    reversed_cu = normalise.half_up(\n        Fraction(quantity) * Fraction(factors[\"reversal_num\"],\n                                      factors[\"reversal_den\"]))\n    counter = ctx[\"params\"][\"counter_map\"][kind]\n    state[\"counters\"][counter] -= reversed_cu\n    state[\"counters\"][kind + \"s\"] -= 1\n    state[\"counters\"][\"reversed_cu\"] += reversed_cu\n    state[\"counters\"][\"compensations\"] += 1\n    state[\"reversed\"].append(target_id)\n    derived.settle(state, ctx, touched)\n    row[\"disposition\"] = \"applied\"\n    row[\"reversed_cu\"] = reversed_cu\n    row[\"applied_order\"] = order[0]\n    order[0] += 1\n    register.append(row)\n",
    "src/bcrep/depends.py": "\"\"\"Stage r07. Dependency closure across the checkpoint and the window.\n\nThe pipe file is the authoritative edge set. The depends_on list inside a\njournal record is a convenience copy carried over from an earlier revision and\ngoverns nothing.\n\"\"\"\nfrom . import reading\n\nPIPE = chr(124)\n\n\ndef _int(text):\n    return int(str(text).strip())\n\n\ndef load_edges(root, frozen):\n    edges = {}\n    for row in reading.read_delim(root / \"dependency_edges.psv\", PIPE):\n        if _int(row[\"revision\"]) > frozen:\n            continue\n        if row[\"edge_kind\"].strip() != \"requires\":\n            continue\n        key = row[\"event_id\"].strip()\n        edges.setdefault(key, [])\n        target = row[\"depends_on\"].strip()\n        if target and target not in edges[key]:\n            edges[key].append(target)\n    for key in edges:\n        edges[key].sort()\n    return edges\n\n\ndef cycle_members(events, edges, by_id):\n    \"\"\"Every event some path of edges leads back to: the members of each\n    strongly connected group of two or more, and every event with a self\n    edge. Edges naming an identifier outside the history take no part.\"\"\"\n    order = {}\n    low = {}\n    stack = []\n    on_stack = set()\n    found = set()\n\n    def visit(node):\n        order[node] = low[node] = len(order)\n        stack.append(node)\n        on_stack.add(node)\n        for nxt in edges.get(node, []):\n            if nxt not in by_id:\n                continue\n            if nxt not in order:\n                visit(nxt)\n                low[node] = min(low[node], low[nxt])\n            elif nxt in on_stack:\n                low[node] = min(low[node], order[nxt])\n        if low[node] != order[node]:\n            return\n        group = []\n        while True:\n            member = stack.pop()\n            on_stack.discard(member)\n            group.append(member)\n            if member == node:\n                break\n        if len(group) > 1 or node in edges.get(node, []):\n            found.update(group)\n\n    for rec in events:\n        if rec[\"event_id\"] not in order:\n            visit(rec[\"event_id\"])\n    return found\n\n\ndef dependency_reason(ctx, rec, window_start, window_end):\n    \"\"\"A dependency already folded into the restored checkpoint is satisfied\n    and is never replayed a second time. A dependency that would still have to\n    be replayed later in the window is not satisfied.\"\"\"\n    eid = rec[\"event_id\"]\n    deps = ctx[\"edges\"].get(eid, [])\n    sources = []\n    for dep in deps:\n        if dep == eid:\n            return \"DEP-SELF\", sources\n    if eid in ctx[\"cycles\"]:\n        return \"DEP-CYCLE\", sources\n    for dep in deps:\n        target = ctx[\"by_id\"].get(dep)\n        if target is None:\n            return \"DEP-MISSING\", sources\n        pos = int(target[\"position\"])\n        if pos < window_start:\n            sources.append((dep, \"checkpoint\"))\n        elif pos < int(rec[\"position\"]) and pos < window_end:\n            sources.append((dep, \"window\"))\n        else:\n            return \"DEP-MISSING\", sources\n    return None, sources\n",
    "src/bcrep/derived.py": "\"\"\"Stages r11 and r13. Carry quantisation, state shape and the derived index.\"\"\"\nfrom . import reading\n\nCOUNTER_NAMES = [\"compensations\", \"deferred_admitted\", \"granted_cu\", \"grants\",\n                 \"retired_cu\", \"retires\", \"reversed_cu\", \"spilled_cu\",\n                 \"transferred_cu\", \"transfers\"]\n\n\ndef new_state():\n    return {\"balances\": {}, \"allotments\": {}, \"pending\": [],\n            \"counters\": {name: 0 for name in COUNTER_NAMES},\n            \"applied\": [], \"reversed\": []}\n\n\ndef restore(body):\n    \"\"\"A restored checkpoint is a copy. The parsed body stays as it was read,\n    so a second replay from the same checkpoint starts from the same state.\"\"\"\n    state = new_state()\n    state[\"balances\"] = dict(body[\"balances\"])\n    state[\"allotments\"] = {k: dict(v) for k, v in body[\"allotments\"].items()}\n    state[\"counters\"] = dict(body[\"counters\"])\n    state[\"pending\"] = list(body[\"pending\"])\n    state[\"applied\"] = list(body[\"applied\"])\n    state[\"reversed\"] = list(body[\"reversed\"])\n    return state\n\n\ndef state_body(state, position):\n    balances = {k: v for k, v in state[\"balances\"].items() if v != 0}\n    allotments = {}\n    for station in state[\"allotments\"]:\n        inner = {k: v for k, v in state[\"allotments\"][station].items() if v != 0}\n        if inner:\n            allotments[station] = inner\n    return {\"position\": position, \"balances\": balances,\n            \"allotments\": allotments, \"counters\": dict(state[\"counters\"]),\n            \"pending\": list(state[\"pending\"]),\n            \"applied\": sorted(state[\"applied\"]),\n            \"reversed\": sorted(state[\"reversed\"])}\n\n\ndef state_digest(body):\n    payload = {k: body[k] for k in (\"position\", \"balances\", \"allotments\",\n                                    \"counters\", \"pending\", \"applied\",\n                                    \"reversed\")}\n    return reading.digest_bytes(reading.compact_json(payload).encode(\"utf-8\"))\n\n\ndef move(state, station, programme, amount):\n    state[\"balances\"][station] = state[\"balances\"].get(station, 0) + amount\n    inner = state[\"allotments\"].setdefault(station, {})\n    inner[programme] = inner.get(programme, 0) + amount\n\n\ndef settle(state, ctx, touched):\n    \"\"\"A balance above its class ceiling spills. The spill is quantised down\n    to a whole number of carry quanta, the quantised part leaves the balance,\n    and the remainder stays where it is.\"\"\"\n    stations = ctx[\"stations\"]\n    params = ctx[\"params\"]\n    frozen = ctx[\"frozen\"]\n    for station in sorted(touched):\n        row = stations.get(station)\n        if row is None:\n            continue\n        cls = str(row[\"class\"]).strip()\n        ceiling = params[\"ceilings\"].get((frozen, cls))\n        quantum = params[\"classes\"].get(cls, {}).get(\"carry_quantum\")\n        if ceiling is None or not quantum:\n            continue\n        balance = state[\"balances\"].get(station, 0)\n        if balance <= ceiling:\n            continue\n        spill = balance - ceiling\n        carried = (spill // quantum) * quantum\n        if carried <= 0:\n            continue\n        state[\"balances\"][station] = balance - carried\n        state[\"counters\"][\"spilled_cu\"] += carried\n",
    "src/bcrep/normalise.py": "\"\"\"Stages r01 and r02. Registers, aliases, quantities and exact arithmetic.\"\"\"\nfrom fractions import Fraction\n\nfrom . import reading\n\nTAB = chr(9)\n\n\ndef _int(text):\n    return int(str(text).strip())\n\n\ndef half_up(value):\n    \"\"\"Nearest integer, halves away from zero, on an exact rational.\"\"\"\n    f = Fraction(value)\n    n, d = f.numerator, f.denominator\n    if d == 1:\n        return n\n    if n >= 0:\n        return (2 * n + d) // (2 * d)\n    return -((2 * (-n) + d) // (2 * d))\n\n\ndef ratio_text(value, places):\n    scale = 10 ** places\n    scaled = half_up(Fraction(value) * scale)\n    sign = \"-\" if scaled < 0 else \"\"\n    scaled = abs(scaled)\n    whole, frac = divmod(scaled, scale)\n    text = sign + str(whole) + \".\" + str(frac).rjust(places, \"0\")\n    if text == \"-0.\" + \"0\" * places:\n        text = \"0.\" + \"0\" * places\n    return text\n\n\ndef safe_ratio(num, den, places):\n    if den == 0:\n        return ratio_text(0, places)\n    return ratio_text(Fraction(int(num), int(den)), places)\n\n\ndef latest_by(rows, key, revision_field, frozen):\n    \"\"\"One row per key: the greatest revision at or below the frozen register\n    revision. A row above that revision is a draft and governs nothing.\"\"\"\n    out = {}\n    for row in rows:\n        if _int(row[revision_field]) > frozen:\n            continue\n        name = row[key].strip()\n        prior = out.get(name)\n        if prior is None or _int(row[revision_field]) >= _int(prior[revision_field]):\n            out[name] = row\n    return out\n\n\ndef load_registers(root, frozen):\n    stations = latest_by(reading.read_delim(root / \"station_register_frozen.csv\"),\n                         \"station\", \"revision\", frozen)\n    programmes = latest_by(reading.read_delim(root / \"programme_register.csv\"),\n                           \"programme\", \"revision\", frozen)\n    alias = {}\n    for row in reading.read_delim(root / \"alias_crosswalk.tsv\", TAB):\n        if _int(row[\"in_force_from_revision\"]) > frozen:\n            continue\n        key = (row[\"kind\"].strip(), row[\"alias\"].strip())\n        prior = alias.get(key)\n        if prior is None or _int(row[\"in_force_from_revision\"]) >= _int(\n                prior[\"in_force_from_revision\"]):\n            alias[key] = row\n    scope = {}\n    for node in reading.read_xml_rows(root / \"topology_and_scope.xml\", \"station\"):\n        if _int(node[\"revision\"]) > frozen:\n            continue\n        scope[node[\"id\"].strip()] = node\n    return stations, programmes, alias, scope\n\n\ndef resolve_alias(alias, kind, name):\n    row = alias.get((kind, str(name).strip()))\n    if row is None:\n        return str(name).strip()\n    return row[\"canonical\"].strip()\n\n\ndef normalise_quantity(rec, params, stations):\n    \"\"\"The recorded quantity is carried into credit units through the unit\n    registry and the class conversion factor, in exact rational arithmetic,\n    and rounded once here.\"\"\"\n    station = stations.get(str(rec[\"station\"]).strip())\n    if station is None:\n        return None, None\n    cls = str(station[\"class\"]).strip()\n    factors = params[\"classes\"].get(cls)\n    if factors is None:\n        return None, cls\n    scale = params[\"units\"].get(str(rec[\"unit\"]).strip())\n    if scale is None:\n        return None, cls\n    value = (Fraction(int(rec[\"quantity\"]) * scale)\n             * Fraction(factors[\"conversion_num\"], factors[\"conversion_den\"]))\n    return half_up(value), cls\n",
    "src/bcrep/ordering.py": "\"\"\"Stage r03. Merge, screen and place the lodged records in canonical order.\n\nArrival order, file order and json key order settle nothing. The canonical\norder is sequence, then stamp, then the kind rank in force, then the tie break\nkey, and the event identifier settles a full tie.\n\"\"\"\nfrom . import normalise, reading\n\nTAB = chr(9)\n\n\ndef _int(text):\n    return int(str(text).strip())\n\n\ndef source_priority(root, frozen):\n    out = {}\n    for row in reading.read_delim(root / \"source_priority_register.csv\"):\n        if _int(row[\"revision\"]) > frozen:\n            continue\n        name = row[\"source\"].strip()\n        prior = out.get(name)\n        if prior is None or _int(row[\"revision\"]) >= prior[0]:\n            out[name] = (_int(row[\"revision\"]), _int(row[\"priority\"]))\n    return {k: v[1] for k, v in out.items()}\n\n\ndef provenance_sources(root):\n    out = {}\n    for row in reading.read_delim(root / \"row_provenance_ledger.csv\"):\n        out.setdefault(row[\"record_id\"].strip(), {})[\n            row[\"file\"].strip()] = row[\"source\"].strip()\n    return out\n\n\ndef kind_ranks(root, frozen):\n    out = {}\n    for row in reading.read_delim(root / \"event_kind_ranks.csv\"):\n        if _int(row[\"revision\"]) > frozen:\n            continue\n        name = row[\"kind\"].strip()\n        prior = out.get(name)\n        if prior is None or _int(row[\"revision\"]) >= prior[0]:\n            out[name] = (_int(row[\"revision\"]), _int(row[\"rank\"]))\n    return {k: v[1] for k, v in out.items()}\n\n\ndef withdrawn_ids(root, frozen):\n    out = set()\n    for row in reading.read_delim(root / \"withdrawn_event_journal.tsv\", TAB):\n        if _int(row[\"withdrawn_at_revision\"]) <= frozen:\n            out.add(row[\"event_id\"].strip())\n    return out\n\n\ndef later_epoch_prefix(root):\n    \"\"\"The identifier prefix data_lineage.md reserves for supplement rows\n    lodged for a later epoch.\"\"\"\n    text = \" \".join((root / \"data_lineage.md\").read_text(encoding=\"utf-8\").split())\n    marker = \"whose identifier begins `\"\n    at = text.find(marker)\n    if at < 0:\n        return None\n    begin = at + len(marker)\n    return text[begin:text.index(\"`\", begin)]\n\n\ndef load_events(root, frozen, alias):\n    \"\"\"One record survives per event identifier. Two records that carry the\n    same payload under different identifiers are two events.\"\"\"\n    priority = source_priority(root, frozen)\n    provenance = provenance_sources(root)\n    ranks = kind_ranks(root, frozen)\n    withdrawn = withdrawn_ids(root, frozen)\n\n    raw = []\n    later = later_epoch_prefix(root)\n    for name in (\"event_journal.jsonl\", \"event_supplement.ndjson\"):\n        for rec in reading.read_jsonl(root / name):\n            if (name == \"event_supplement.ndjson\" and later\n                    and str(rec[\"event_id\"]).strip().startswith(later)):\n                continue\n            rec = dict(rec)\n            rec[\"lodged_in\"] = name\n            raw.append(rec)\n\n    merged = {}\n    for rec in raw:\n        eid = str(rec[\"event_id\"]).strip()\n        source = str(rec.get(\"source\") or \"\").strip()\n        if source == \"\":\n            source = provenance.get(eid, {}).get(rec[\"lodged_in\"], \"\")\n        rank = (priority.get(source, 0), int(rec[\"revision\"]))\n        prior = merged.get(eid)\n        if prior is None or rank > prior[0]:\n            merged[eid] = (rank, rec)\n\n    events = []\n    for eid in merged:\n        rec = dict(merged[eid][1])\n        rec[\"event_id\"] = eid\n        rec[\"withdrawn\"] = eid in withdrawn\n        rec[\"draft\"] = int(rec[\"revision\"]) > frozen\n        rec[\"station\"] = normalise.resolve_alias(alias, \"station\", rec[\"station\"])\n        rec[\"programme\"] = normalise.resolve_alias(alias, \"programme\",\n                                                   rec[\"programme\"])\n        if rec.get(\"counterparty\"):\n            rec[\"counterparty\"] = normalise.resolve_alias(\n                alias, \"station\", rec[\"counterparty\"])\n        rec[\"rank\"] = ranks.get(str(rec[\"kind\"]).strip(), 99)\n        events.append(rec)\n\n    events.sort(key=lambda r: (int(r[\"sequence\"]), int(r[\"stamp\"]),\n                               int(r[\"rank\"]), str(r[\"tiebreak\"]),\n                               str(r[\"event_id\"])))\n    for position, rec in enumerate(events, start=1):\n        rec[\"position\"] = position\n    return events\n",
    "src/bcrep/params.py": "\"\"\"Stage r01. The parameter layers of one epoch.\n\nThree papers are not plain text. The workbook carries the class scales, the\ncarry quanta and the per revision ceilings on two sheets, one in force and one\nsuperseded. The memo carries the round ceiling and the two quantity limits.\nThe directive carries the re offer ladder and the two compensation rules.\n\"\"\"\nfrom . import reading\n\nQ = chr(34)\n\n\ndef _int(text):\n    return int(str(text).strip())\n\n\ndef live_sheet(root, header):\n    \"\"\"The sheet in force is the one whose epoch key cell equals the epoch key\n    the header names. Sheet name and sheet position settle nothing.\"\"\"\n    sheets = reading.read_xlsx_sheets(root / \"custody_parameter_workbook.xlsx\")\n    wanted = str(header[\"workbook_epoch_key\"]).strip()\n    for name in sheets:\n        for row in sheets[name]:\n            if len(row) >= 2 and str(row[0]).strip() == \"epoch_key\":\n                if str(row[1]).strip() == wanted:\n                    return name, sheets[name]\n                break\n    raise SystemExit(\"no workbook sheet carries the epoch key in force\")\n\n\ndef workbook_layers(rows):\n    classes = {}\n    ceilings = {}\n    for row in rows:\n        if not row:\n            continue\n        tag = str(row[0]).strip()\n        if tag == \"conversion\" and len(row) >= 4:\n            cls = str(row[1]).strip()\n            classes.setdefault(cls, {})[\"conversion_num\"] = _int(row[2])\n            classes[cls][\"conversion_den\"] = _int(row[3])\n        elif tag == \"reversal\" and len(row) >= 4:\n            cls = str(row[1]).strip()\n            classes.setdefault(cls, {})[\"reversal_num\"] = _int(row[2])\n            classes[cls][\"reversal_den\"] = _int(row[3])\n        elif tag == \"carry_quantum\" and len(row) >= 3:\n            cls = str(row[1]).strip()\n            classes.setdefault(cls, {})[\"carry_quantum\"] = _int(row[2])\n        elif tag == \"ceiling\" and len(row) >= 4:\n            ceilings[(_int(row[1]), str(row[2]).strip())] = _int(row[3])\n    return classes, ceilings\n\n\ndef memo_resolutions(root):\n    \"\"\"A resolution carries the sitting that adopted it. Where two sittings\n    carry the same subject the later sitting governs.\"\"\"\n    held = {}\n    for line in reading.read_pdf_lines(root / \"custody_board_memo.pdf\"):\n        text = line.strip()\n        if not text.startswith(\"RESOLUTION \"):\n            continue\n        parts = text.split(\" \")\n        if len(parts) < 4 or parts[2] != \"SITTING\":\n            continue\n        sitting = int(parts[3])\n        body = \" \".join(parts[4:])\n        name, sep, value = body.partition(\" = \")\n        if not sep:\n            continue\n        name = name.strip()\n        if name not in held or sitting > held[name][0]:\n            held[name] = (sitting, value.strip())\n    return {name: held[name][1] for name in held}\n\n\ndef directive_rules(root):\n    levels = []\n    duplicate_rule = \"\"\n    closure_rule = \"\"\n    for block in reading.read_docx_blocks(root / \"precedence_directive.docx\"):\n        if isinstance(block, list) and len(block) >= 3 and block[0] == \"level\":\n            levels.append((_int(block[1]), block[2].strip()))\n        elif isinstance(block, str) and block.startswith(\"DUPLICATE TARGET RULE: \"):\n            duplicate_rule = block.split(\": \", 1)[1].strip()\n        elif isinstance(block, str) and block.startswith(\"DEPENDENCY CLOSURE RULE: \"):\n            closure_rule = block.split(\": \", 1)[1].strip()\n    levels.sort()\n    return [name for _rank, name in levels], duplicate_rule, closure_rule\n\n\ndef load(root):\n    header = reading.read_json(root / \"epoch_header.json\")\n    name, rows = live_sheet(root, header)\n    classes, ceilings = workbook_layers(rows)\n    memo = memo_resolutions(root)\n    levels, duplicate_rule, closure_rule = directive_rules(root)\n\n    units = reading.read_flat_toml(root / \"unit_registry.toml\").get(\"units\", {})\n    units = {k: int(v) for k, v in units.items()}\n\n    policy = reading.read_flat_yaml(root / \"eligibility_policy.yaml\")\n    screen_order = policy[\"screen_order\"][\"order\"]\n\n    arithmetic = reading.read_flat_yaml(root / \"rounding_and_arithmetic_policy.yaml\")\n    places = int(arithmetic[\"ratio\"][\"places\"])\n\n    form = reading.read_flat_toml(root / \"publication_form_rules.toml\")\n    core_documents = form[\"core_digest\"][\"documents\"]\n\n    comp = reading.read_flat_toml(root / \"compensation_policy.toml\")\n    counter_map = dict(comp[\"reversal_counter_map\"])\n\n    conf = reading.read_conf(root / \"reporting_station_roster.conf\")\n    regions = {k: int(v) for k, v in conf.get(\"region_rank\", {}).items()}\n\n    return {\n        \"header\": header,\n        \"live_sheet\": name,\n        \"classes\": classes,\n        \"ceilings\": ceilings,\n        \"round_ceiling\": int(memo[\"revalidation round ceiling\"]),\n        \"implausible_ceiling\": int(memo[\"implausible quantity ceiling cu\"]),\n        \"settlement_floor\": int(memo[\"settlement floor cu\"]),\n        \"levels\": levels,\n        \"duplicate_rule\": duplicate_rule,\n        \"closure_rule\": closure_rule,\n        \"units\": units,\n        \"screen_order\": screen_order,\n        \"ratio_places\": places,\n        \"core_documents\": core_documents,\n        \"counter_map\": counter_map,\n        \"regions\": regions,\n    }\n",
    "src/bcrep/publish.py": "\"\"\"Stage r14. Materialise the epoch and write it out.\n\nEvery document is written through one canonical serialisation: utf-8, line\nfeed endings, sorted keys, two space indentation for the indented json, one\ntrailing newline, and ratios at the number of places the arithmetic policy\nnames. The two digests are taken last, over the bytes already written.\n\"\"\"\nfrom pathlib import Path\n\nfrom . import derived, normalise, reading, replay\n\nTAB = chr(9)\nPIPE = chr(124)\n\nARTIFACT_NAMES = [\n    \"alias_resolution.jsonl\", \"bounded_replay.json\", \"canonical_order.csv\",\n    \"checkpoint_reconciliation.json\", \"checkpoint_selection.json\",\n    \"compensation_register.csv\", \"defect_register.md\", \"derived_counters.csv\",\n    \"derived_index.jsonl\", \"dependency_closure.json\",\n    \"eligibility_passes.json\", \"equivalence_report.json\", \"final_state.json\",\n    \"quarantine_ledger.csv\", \"replay_window.json\", \"repair_report.json\",\n    \"run_manifest.txt\", \"selftest.json\", \"state_at_event.json\",\n    \"summary.json\", \"transition_log.jsonl\", \"unit_normalisation.json\",\n    \"verification_notes.md\",\n]\n\nPACKAGE_MODULES = [\"__init__\", \"__main__\", \"checkpointing\", \"compensation\",\n                   \"derived\", \"depends\", \"normalise\", \"ordering\", \"params\",\n                   \"publish\", \"reading\", \"replay\", \"transitions\", \"window\"]\n\nQUARANTINE_CODES = [\"EVT-DRAFTREVISION\", \"EVT-WITHDRAWN\",\n                    \"EVT-UNKNOWNSTATION\", \"EVT-UNKNOWNPROGRAMME\",\n                    \"EVT-NONPOSITIVE\", \"EVT-IMPLAUSIBLE\", \"CMP-WITHDRAWN\",\n                    \"CMP-NOTARGET\", \"DEP-SELF\", \"DEP-CYCLE\", \"DEP-MISSING\"]\n\n\ndef _int(text):\n    return int(str(text).strip())\n\n\ndef publish(root, out):\n    root = Path(root)\n    out = Path(out)\n    out.mkdir(parents=True, exist_ok=True)\n    ctx = replay.build_context(root)\n    settings = ctx[\"params\"]\n    header = settings[\"header\"]\n    frozen = ctx[\"frozen\"]\n    events = ctx[\"events\"]\n    total = len(events)\n    places = settings[\"ratio_places\"]\n\n    start = int(header[\"replay_start_position\"])\n    end = int(header[\"replay_end_position\"])\n    probe = int(header[\"state_probe_position\"])\n    b_start = int(header[\"bounded_start_position\"])\n    b_end = int(header[\"bounded_end_position\"])\n\n    chosen, usable, rejected = replay.select_checkpoint(ctx, end)\n    body = chosen[2] if chosen else None\n    run = replay.run(ctx, start, end, body)\n    scratch = replay.run(ctx, 1, end, None)\n    probe_run = replay.run(ctx, 1, probe + 1, None, run_rounds=False)\n    b_chosen, _bu, _br = replay.select_checkpoint(ctx, b_end)\n    bounded = replay.run(ctx, b_start, b_end, b_chosen[2] if b_chosen else None)\n\n    state = run[\"state\"]\n\n    reading.write_json(out / \"unit_normalisation.json\", {\n        \"epoch_id\": header[\"epoch_id\"],\n        \"workbook_epoch_key\": header[\"workbook_epoch_key\"],\n        \"live_sheet\": settings[\"live_sheet\"],\n        \"frozen_register_revision\": frozen,\n        \"round_ceiling\": settings[\"round_ceiling\"],\n        \"implausible_ceiling_cu\": settings[\"implausible_ceiling\"],\n        \"settlement_floor_cu\": settings[\"settlement_floor\"],\n        \"precedence_levels\": settings[\"levels\"],\n        \"units\": {k: settings[\"units\"][k] for k in sorted(settings[\"units\"])},\n        \"classes\": {k: {j: settings[\"classes\"][k][j]\n                        for j in sorted(settings[\"classes\"][k])}\n                    for k in sorted(settings[\"classes\"])},\n        \"ceilings\": {str(rev) + \":\" + cls: settings[\"ceilings\"][(rev, cls)]\n                     for rev, cls in sorted(settings[\"ceilings\"])},\n        \"event_count\": total,\n        \"normalised_total_cu\": sum(v for v in ctx[\"norm\"].values()\n                                   if v is not None and v > 0),\n    })\n\n    alias_rows = []\n    for kind, name in sorted(ctx[\"alias\"]):\n        row = ctx[\"alias\"][(kind, name)]\n        alias_rows.append({\"alias\": name, \"canonical\": row[\"canonical\"].strip(),\n                           \"kind\": kind,\n                           \"in_force_from_revision\":\n                               _int(row[\"in_force_from_revision\"])})\n    reading.write_jsonl(out / \"alias_resolution.jsonl\", alias_rows)\n\n    reading.write_delim(out / \"canonical_order.csv\",\n                        [\"position\", \"event_id\", \"sequence\", \"stamp\", \"kind\",\n                         \"rank\", \"tiebreak\"],\n                        [[rec[\"position\"], rec[\"event_id\"],\n                          int(rec[\"sequence\"]), int(rec[\"stamp\"]),\n                          rec[\"kind\"], rec[\"rank\"], rec[\"tiebreak\"]]\n                         for rec in events])\n\n    reading.write_json(out / \"checkpoint_selection.json\", {\n        \"requested_start\": start, \"requested_end\": end,\n        \"usable\": sorted(usable),\n        \"selected\": chosen[1] if chosen else \"\",\n        \"selected_position\": chosen[0] if chosen else 0,\n        \"watermark_position\": run[\"watermark\"],\n        \"rejected\": rejected,\n    })\n\n    from . import window as window_mod\n    reading.write_json(out / \"replay_window.json\", {\n        \"start_position\": run[\"window_start\"],\n        \"end_position\": run[\"window_end\"],\n        \"replayed_count\": len(run[\"positions\"]),\n        \"first_replayed_position\": run[\"positions\"][0] if run[\"positions\"] else 0,\n        \"last_replayed_position\": run[\"positions\"][-1] if run[\"positions\"] else 0,\n        \"skipped_before_watermark\": window_mod.skipped_before(start,\n                                                              run[\"watermark\"]),\n        \"boundary\": \"start inclusive, end exclusive\",\n    })\n\n    reading.write_json(out / \"dependency_closure.json\", {\n        \"edges_in_force\": sum(len(v) for v in ctx[\"edges\"].values()),\n        \"satisfied_by_checkpoint\": run[\"closure\"][\"checkpoint\"],\n        \"satisfied_by_window\": run[\"closure\"][\"window\"],\n        \"unsatisfied\": sorted(run[\"unsatisfied\"],\n                              key=lambda r: (r[\"event_id\"], r[\"reason\"])),\n        \"cycle_members\": sorted(ctx[\"cycles\"]),\n    })\n\n    reading.write_delim(out / \"quarantine_ledger.csv\",\n                        [\"event_id\", \"position\", \"stage\", \"reason_code\",\n                         \"detail\"],\n                        [[r[\"event_id\"], r[\"position\"], r[\"stage\"],\n                          r[\"reason_code\"], r[\"detail\"]]\n                         for r in sorted(run[\"quarantine\"],\n                                         key=lambda r: (r[\"position\"],\n                                                        r[\"event_id\"]))])\n\n    reading.write_jsonl(out / \"transition_log.jsonl\", run[\"log\"])\n\n    reading.write_delim(out / \"compensation_register.csv\",\n                        [\"compensation_id\", \"target_event_id\",\n                         \"target_position\", \"disposition\", \"reversed_cu\",\n                         \"applied_order\"],\n                        [[r[\"compensation_id\"], r[\"target_event_id\"],\n                          r[\"target_position\"], r[\"disposition\"],\n                          r[\"reversed_cu\"], r[\"applied_order\"]]\n                         for r in sorted(run[\"register\"],\n                                         key=lambda r: r[\"compensation_id\"])])\n\n    reading.write_delim(out / \"derived_counters.csv\", [\"counter\", \"value\"],\n                        [[name, state[\"counters\"][name]]\n                         for name in derived.COUNTER_NAMES])\n\n    reading.write_json(out / \"eligibility_passes.json\", {\n        \"pass_ceiling\": settings[\"round_ceiling\"],\n        \"deferred_at_first_pass\": sorted(run[\"deferred\"]),\n        \"rounds\": run[\"rounds\"],\n        \"round_count\": len(run[\"rounds\"]),\n        \"stable\": run[\"stable\"],\n        \"deferred_remaining\": list(state[\"pending\"]),\n    })\n\n    final = derived.state_body(state, run[\"window_end\"])\n    reading.write_json(out / \"final_state.json\", final)\n\n    index_rows = []\n    for station in sorted(final[\"allotments\"]):\n        node = ctx[\"scope\"].get(station, {})\n        inner = final[\"allotments\"][station]\n        station_total = sum(inner.values())\n        for programme in sorted(inner):\n            index_rows.append({\n                \"region\": node.get(\"region\", \"\"), \"hub\": node.get(\"hub\", \"\"),\n                \"station\": station, \"programme\": programme,\n                \"allotment_cu\": inner[programme],\n                \"share\": normalise.safe_ratio(inner[programme], station_total,\n                                              places),\n            })\n    index_rows.sort(key=lambda r: (r[\"region\"], r[\"hub\"], r[\"station\"],\n                                   r[\"programme\"]))\n    reading.write_jsonl(out / \"derived_index.jsonl\", index_rows)\n\n    archive = reading.read_sqlite_table(root / \"prior_epoch_archive.db\",\n                                        \"prior_counters\")\n    history = reading.read_delim(root / \"allotment_ceiling_history.tsv\", TAB)\n    deltas = {}\n    historic_total = 0\n    declared = \"\"\n    recomputed = \"\"\n    if chosen:\n        for name in derived.COUNTER_NAMES:\n            held = [int(row[\"value\"]) for row in archive\n                    if str(row[\"checkpoint_id\"]).strip() == chosen[1]\n                    and str(row[\"counter\"]).strip() == name]\n            if held:\n                deltas[name] = held[-1] - int(chosen[2][\"counters\"].get(name, 0))\n        declared = chosen[3][\"state_digest\"].strip()\n        recomputed = derived.state_digest(chosen[2])\n        checkpoint_revision = _int(chosen[3][\"revision\"])\n        historic_total = sum(_int(row[\"ceiling_cu\"]) for row in history\n                             if _int(row[\"revision\"]) == checkpoint_revision)\n    reading.write_json(out / \"checkpoint_reconciliation.json\", {\n        \"selected\": chosen[1] if chosen else \"\",\n        \"declared_digest\": declared, \"recomputed_digest\": recomputed,\n        \"matches\": declared == recomputed and declared != \"\",\n        \"archive_rows\": len(archive),\n        \"counter_deltas\": {k: deltas[k] for k in sorted(deltas)},\n        \"historic_ceiling_total_cu\": historic_total,\n        \"rejected_count\": len(rejected),\n    })\n\n    scratch_final = derived.state_body(scratch[\"state\"], scratch[\"window_end\"])\n    reading.write_json(out / \"equivalence_report.json\", {\n        \"comparison_start\": 1, \"comparison_end\": end,\n        \"checkpoint_used\": chosen[1] if chosen else \"\",\n        \"from_scratch_digest\": derived.state_digest(scratch_final),\n        \"from_checkpoint_digest\": derived.state_digest(final),\n        \"identical\": scratch_final == final,\n        \"scratch_replayed_count\": len(scratch[\"positions\"]),\n        \"checkpoint_replayed_count\": len(run[\"positions\"]),\n    })\n\n    reading.write_json(out / \"state_at_event.json\",\n                       derived.state_body(probe_run[\"state\"], probe))\n\n    reading.write_json(out / \"bounded_replay.json\", {\n        \"start_position\": bounded[\"window_start\"],\n        \"end_position\": bounded[\"window_end\"],\n        \"replayed_count\": len(bounded[\"positions\"]),\n        \"state\": derived.state_body(bounded[\"state\"], bounded[\"window_end\"]),\n    })\n\n    reading.write_json(out / \"repair_report.json\", {\n        \"package\": \"bcrep\",\n        \"modules\": PACKAGE_MODULES,\n        \"stage_ids\": replay.STAGE_IDS,\n        \"stage_count\": len(replay.STAGE_IDS),\n        \"entry_point\": \"bcrep.__main__\",\n        \"standard_library_only\": True,\n        \"reason_codes\": QUARANTINE_CODES,\n    })\n\n    checks = [\n        {\"name\": \"canonical_order_total\", \"value\": total},\n        {\"name\": \"checkpoint_digest_matches\",\n         \"value\": 1 if (chosen and declared == recomputed) else 0},\n        {\"name\": \"window_end_exclusive\",\n         \"value\": 1 if (not run[\"positions\"] or run[\"positions\"][-1] < end)\n         else 0},\n        {\"name\": \"watermark_replayed_once\",\n         \"value\": 0 if run[\"watermark\"] in run[\"positions\"] else 1},\n        {\"name\": \"scratch_matches_checkpoint\",\n         \"value\": 1 if scratch_final == final else 0},\n        {\"name\": \"targets_reversed_once\",\n         \"value\": 1 if len(set(state[\"reversed\"])) == len(state[\"reversed\"])\n         else 0},\n        {\"name\": \"pending_after_rounds\", \"value\": len(state[\"pending\"])},\n        {\"name\": \"rounds_run\", \"value\": len(run[\"rounds\"])},\n    ]\n    flags = [c[\"value\"] for c in checks\n             if c[\"name\"] not in (\"canonical_order_total\",\n                                  \"pending_after_rounds\", \"rounds_run\")]\n    reading.write_json(out / \"selftest.json\", {\n        \"checks\": checks,\n        \"passed\": sum(1 for value in flags if value == 1),\n        \"failed\": sum(1 for value in flags if value == 0),\n    })\n\n    catalogue = []\n    for row in reading.read_delim(root / \"quarantine_reason_catalogue.psv\",\n                                  PIPE):\n        if _int(row[\"revision\"]) > frozen:\n            continue\n        if row[\"code\"].strip() in QUARANTINE_CODES:\n            catalogue.append((row[\"code\"].strip(), row[\"stage\"].strip(),\n                              row[\"meaning\"].strip()))\n    catalogue = sorted(set(catalogue))\n    lines = [\"# Defect register\", \"\",\n             \"| stage | reason code | meaning |\",\n             \"| --- | --- | --- |\"]\n    for code, stage, meaning in catalogue:\n        lines.append(\"| \" + stage + \" | \" + code + \" | \" + meaning + \" |\")\n    lines.append(\"\")\n    lines.append(\"Stages in force: \" + \", \".join(replay.STAGE_IDS))\n    reading.write_lines(out / \"defect_register.md\", lines)\n\n    floor = settings[\"settlement_floor\"]\n    breaches = sorted(k for k, v in final[\"balances\"].items() if v < floor)\n    applied_count = sum(1 for r in run[\"register\"]\n                        if r[\"disposition\"] == \"applied\")\n    void_count = len(run[\"register\"]) - applied_count\n    reading.write_lines(out / \"verification_notes.md\", [\n        \"# Verification notes\", \"\",\n        \"epoch \" + str(header[\"epoch_id\"]),\n        \"live sheet \" + str(settings[\"live_sheet\"]),\n        \"watermark position \" + str(run[\"watermark\"]),\n        \"window \" + str(run[\"window_start\"]) + \" to \" + str(run[\"window_end\"])\n        + \" end exclusive\",\n        \"rounds run \" + str(len(run[\"rounds\"])),\n        \"stable \" + (\"yes\" if run[\"stable\"] else \"no\"),\n        \"pending after rounds \" + str(len(state[\"pending\"])),\n        \"compensations applied \" + str(applied_count),\n        \"compensations void \" + str(void_count),\n        \"reversed cu \" + str(state[\"counters\"][\"reversed_cu\"]),\n        \"spilled cu \" + str(state[\"counters\"][\"spilled_cu\"]),\n        \"settlement floor \" + str(floor),\n        \"settlement floor breaches \" + str(len(breaches)),\n        \"scratch equals checkpoint \"\n        + (\"yes\" if scratch_final == final else \"no\"),\n        \"\"])\n\n    balance_total = sum(final[\"balances\"].values())\n    allotment_total = sum(sum(v.values()) for v in final[\"allotments\"].values())\n    reading.write_json(out / \"summary.json\", {\n        \"epoch_id\": header[\"epoch_id\"],\n        \"live_sheet\": settings[\"live_sheet\"],\n        \"frozen_register_revision\": frozen,\n        \"control_totals\": {\n            \"canonical_events\": total,\n            \"checkpoint_position\": run[\"watermark\"],\n            \"window_start\": run[\"window_start\"],\n            \"window_end\": run[\"window_end\"],\n            \"replayed_positions\": len(run[\"positions\"]),\n            \"quarantined_events\": len(run[\"quarantine\"]),\n            \"deferred_at_first_pass\": len(run[\"deferred\"]),\n            \"admitted_in_rounds\": sum(r[\"admitted_count\"]\n                                      for r in run[\"rounds\"]),\n            \"round_count\": len(run[\"rounds\"]),\n            \"pending_remaining\": len(state[\"pending\"]),\n            \"compensations_applied\": applied_count,\n            \"compensations_void\": void_count,\n            \"reversed_cu\": state[\"counters\"][\"reversed_cu\"],\n            \"spilled_cu\": state[\"counters\"][\"spilled_cu\"],\n            \"balance_total_cu\": balance_total,\n            \"allotment_total_cu\": allotment_total,\n            \"index_rows\": len(index_rows),\n            \"settlement_floor_breaches\": len(breaches),\n        },\n        \"stable\": run[\"stable\"],\n        \"equivalence_identical\": scratch_final == final,\n        \"balance_share\": normalise.safe_ratio(balance_total, allotment_total,\n                                              places),\n    })\n\n    core = b\"\".join((out / name).read_bytes()\n                    for name in settings[\"core_documents\"])\n    publication = b\"\".join((out / name).read_bytes()\n                           for name in sorted(ARTIFACT_NAMES)\n                           if name != \"run_manifest.txt\")\n    reading.write_lines(out / \"run_manifest.txt\",\n                        [\"core \" + reading.digest_bytes(core),\n                         \"publication \" + reading.digest_bytes(publication)])\n    return out\n",
    "src/bcrep/reading.py": "\"\"\"Readers for the shapes the working papers arrive in.\n\nNothing in this module knows what any file means. It turns bytes into rows,\nrecords, cells and lines, and the stage modules decide what governs.\n\"\"\"\nimport hashlib\nimport json\nimport sqlite3\nimport zipfile\nimport zlib\nimport xml.etree.ElementTree as ET\nfrom pathlib import Path\n\nNL = chr(10)\nBS = chr(92)\nQ = chr(34)\nTAB = chr(9)\nPIPE = chr(124)\nNS_WORD = \"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"\nW_NS = \"{\" + NS_WORD + \"}\"\n\n\ndef digest_bytes(payload):\n    return hashlib.sha256(payload).hexdigest()\n\n\ndef compact_json(obj):\n    return json.dumps(obj, ensure_ascii=False, sort_keys=True,\n                      separators=(\",\", \":\"))\n\n\ndef canonical_json(obj):\n    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + NL\n\n\ndef read_json(path):\n    return json.loads(Path(path).read_text(encoding=\"utf-8\"))\n\n\ndef read_jsonl(path):\n    out = []\n    for line in Path(path).read_text(encoding=\"utf-8\").splitlines():\n        if line.strip():\n            out.append(json.loads(line))\n    return out\n\n\ndef read_delim(path, sep=\",\"):\n    lines = Path(path).read_text(encoding=\"utf-8\").splitlines()\n    lines = [ln for ln in lines if ln.strip() != \"\"]\n    header = lines[0].split(sep)\n    return [dict(zip(header, ln.split(sep))) for ln in lines[1:]]\n\n\ndef read_conf(path):\n    out = {}\n    section = \"default\"\n    out[section] = {}\n    for raw in Path(path).read_text(encoding=\"utf-8\").splitlines():\n        line = raw.strip()\n        if not line or line.startswith(\"#\"):\n            continue\n        if line.startswith(\"[\") and line.endswith(\"]\"):\n            section = line[1:-1]\n            out.setdefault(section, {})\n            continue\n        key, _sep, value = line.partition(\"=\")\n        out[section][key.strip()] = value.strip()\n    return out\n\n\ndef scalar(value):\n    text = value.strip()\n    if text.startswith(\"[\") and text.endswith(\"]\"):\n        inner = text[1:-1].strip()\n        if inner == \"\":\n            return []\n        return [scalar(part) for part in inner.split(\",\")]\n    if len(text) >= 2 and text[0] == Q and text[-1] == Q:\n        return text[1:-1]\n    if text in (\"true\", \"false\"):\n        return text == \"true\"\n    try:\n        return int(text)\n    except ValueError:\n        return text\n\n\ndef read_flat_yaml(path):\n    out = {}\n    section = None\n    for raw in Path(path).read_text(encoding=\"utf-8\").splitlines():\n        if not raw.strip() or raw.lstrip().startswith(\"#\"):\n            continue\n        indented = raw.startswith(\" \")\n        key, _sep, value = raw.strip().partition(\":\")\n        key = key.strip()\n        value = value.strip()\n        if value == \"\":\n            if indented and section is not None:\n                out[section][key] = {}\n            else:\n                section = key\n                out[section] = {}\n            continue\n        parsed = scalar(value)\n        if indented and section is not None:\n            out[section][key] = parsed\n        else:\n            out[key] = parsed\n    return out\n\n\ndef read_flat_toml(path):\n    out = {}\n    section = \"root\"\n    out[section] = {}\n    for raw in Path(path).read_text(encoding=\"utf-8\").splitlines():\n        line = raw.strip()\n        if not line or line.startswith(\"#\"):\n            continue\n        if line.startswith(\"[\") and line.endswith(\"]\"):\n            section = line[1:-1]\n            out.setdefault(section, {})\n            continue\n        key, _sep, value = line.partition(\"=\")\n        out[section][key.strip()] = scalar(value)\n    return out\n\n\ndef read_xml_rows(path, tag):\n    root = ET.parse(str(path)).getroot()\n    return [dict(node.attrib) for node in root.iter(tag)]\n\n\ndef read_sqlite_table(path, table):\n    con = sqlite3.connect(str(path))\n    try:\n        cur = con.cursor()\n        cur.execute(\"SELECT * FROM \" + table)\n        cols = [c[0] for c in cur.description]\n        return [dict(zip(cols, row)) for row in cur.fetchall()]\n    finally:\n        con.close()\n\n\ndef _col_to_idx(ref):\n    col = 0\n    for ch in ref:\n        if ch.isalpha():\n            col = col * 26 + (ord(ch.upper()) - 64)\n        else:\n            break\n    return col\n\n\ndef _sheet_rows(payload, shared):\n    rows = []\n    for row in ET.fromstring(payload).iter():\n        if not row.tag.endswith(\"}row\"):\n            continue\n        cells = {}\n        width = 0\n        for c in row:\n            if not c.tag.endswith(\"}c\"):\n                continue\n            ci = _col_to_idx(c.attrib.get(\"r\", \"A1\"))\n            val = \"\"\n            for v in c:\n                if v.tag.endswith(\"}v\"):\n                    val = v.text or \"\"\n            if c.attrib.get(\"t\") == \"s\" and val != \"\":\n                val = shared[int(val)]\n            cells[ci] = val\n            width = max(width, ci)\n        rows.append([cells.get(i, \"\") for i in range(1, width + 1)])\n    return rows\n\n\ndef read_xlsx_sheets(path):\n    with zipfile.ZipFile(path) as zf:\n        shared = []\n        if \"xl/sharedStrings.xml\" in zf.namelist():\n            sroot = ET.fromstring(zf.read(\"xl/sharedStrings.xml\"))\n            for si in sroot:\n                shared.append(\"\".join(t.text or \"\" for t in si.iter()\n                                      if t.tag.endswith(\"}t\")))\n        wb = ET.fromstring(zf.read(\"xl/workbook.xml\"))\n        rels = ET.fromstring(zf.read(\"xl/_rels/workbook.xml.rels\"))\n        targets = {rel.attrib.get(\"Id\"): rel.attrib.get(\"Target\", \"\")\n                   for rel in rels.iter() if rel.tag.endswith(\"}Relationship\")}\n        rid = (\"{http://schemas.openxmlformats.org/officeDocument/2006/\"\n               \"relationships}id\")\n        out = {}\n        for sh in wb.iter():\n            if not sh.tag.endswith(\"}sheet\"):\n                continue\n            target = targets.get(sh.attrib.get(rid), \"\")\n            member = target[1:] if target.startswith(\"/\") else \"xl/\" + target\n            if member not in zf.namelist():\n                continue\n            out[sh.attrib.get(\"name\")] = _sheet_rows(zf.read(member), shared)\n        return out\n\n\ndef _pdf_streams(raw):\n    \"\"\"Every stream of a PDF as latin-1 text, inflated where its dictionary\n    names FlateDecode.\"\"\"\n    marker = (\">>\" + NL + \"stream\" + NL).encode(\"latin-1\")\n    out = []\n    at = raw.find(marker)\n    while at >= 0:\n        words = raw[raw.rfind(b\"<<\", 0, at):at].decode(\"latin-1\").split()\n        begin = at + len(marker)\n        length = int(words[words.index(\"/Length\") + 1])\n        payload = raw[begin:begin + length]\n        if \"/FlateDecode\" in words:\n            payload = zlib.decompress(payload)\n        out.append(payload.decode(\"latin-1\"))\n        at = raw.find(marker, begin + length)\n    return out\n\n\ndef _pdf_string(content, at):\n    \"\"\"The literal string opening at content[at], and the index past it.\"\"\"\n    depth = 1\n    text = []\n    at += 1\n    while at < len(content):\n        ch = content[at]\n        if ch == BS:\n            text.append(content[at + 1:at + 2])\n            at += 2\n            continue\n        if ch == \"(\":\n            depth += 1\n        elif ch == \")\":\n            depth -= 1\n            if depth == 0:\n                return \"\".join(text), at + 1\n        text.append(ch)\n        at += 1\n    return \"\".join(text), at\n\n\ndef _shown_text(content):\n    \"\"\"One line per text showing operator: the string a Tj shows, and the\n    strings of a TJ array joined in order, its kerning numbers dropped.\"\"\"\n    lines = []\n    operands = []\n    array = None\n    at = 0\n    while at < len(content):\n        ch = content[at]\n        if ch == \"(\":\n            text, at = _pdf_string(content, at)\n            (operands if array is None else array).append(text)\n        elif ch == \"[\":\n            array = []\n            at += 1\n        elif ch == \"]\":\n            operands.append(array)\n            array = None\n            at += 1\n        elif ch.isspace():\n            at += 1\n        else:\n            end = at\n            while (end < len(content) and not content[end].isspace()\n                   and content[end] not in \"()[]\"):\n                end += 1\n            word = content[at:end]\n            at = end\n            if word == \"Tj\" and operands and isinstance(operands[-1], str):\n                lines.append(operands[-1])\n            elif word == \"TJ\" and operands and isinstance(operands[-1], list):\n                lines.append(\"\".join(operands[-1]))\n            if word[:1].isalpha():\n                operands = []\n    return lines\n\n\ndef read_pdf_lines(path):\n    out = []\n    for content in _pdf_streams(Path(path).read_bytes()):\n        out.extend(_shown_text(content))\n    return out\n\n\ndef read_docx_blocks(path):\n    with zipfile.ZipFile(path) as zf:\n        root = ET.fromstring(zf.read(\"word/document.xml\"))\n    out = []\n    body = None\n    for node in root:\n        if node.tag == W_NS + \"body\":\n            body = node\n    if body is None:\n        return out\n    for node in body:\n        if node.tag == W_NS + \"p\":\n            out.append(\"\".join(t.text or \"\" for t in node.iter(W_NS + \"t\")))\n        elif node.tag == W_NS + \"tbl\":\n            for tr in node.findall(W_NS + \"tr\"):\n                out.append([\"\".join(t.text or \"\" for t in tc.iter(W_NS + \"t\"))\n                            for tc in tr.findall(W_NS + \"tc\")])\n    return out\n\n\ndef write_text(path, text):\n    if not text.endswith(NL):\n        text += NL\n    Path(path).write_bytes(text.encode(\"utf-8\"))\n\n\ndef write_lines(path, lines):\n    write_text(path, NL.join(str(x) for x in lines))\n\n\ndef write_json(path, obj):\n    write_text(path, canonical_json(obj))\n\n\ndef write_jsonl(path, records):\n    write_lines(path, [compact_json(r) for r in records])\n\n\ndef write_delim(path, header, rows, sep=\",\"):\n    out = [sep.join(str(h) for h in header)]\n    for row in rows:\n        out.append(sep.join(str(c) for c in row))\n    write_lines(path, out)\n",
    "src/bcrep/replay.py": "\"\"\"Stages r05 to r12. One forward pass over the window, then the re offer\nrounds.\n\nAn event whose eligibility predicate is false when it is first offered is not\ndiscarded. It waits in the pending queue and is offered again after the window\nis exhausted, because a compensating event later in the window can change the\nstate the predicate reads. The rounds run until a round admits nothing or the\nround ceiling in the board memo is reached.\n\"\"\"\nfrom . import checkpointing, compensation, depends, derived, normalise\nfrom . import ordering, params, transitions\n\nSTAGE_IDS = [\"r01\", \"r02\", \"r03\", \"r04\", \"r05\", \"r06\", \"r07\",\n             \"r08\", \"r09\", \"r10\", \"r11\", \"r12\", \"r13\", \"r14\"]\n\n\ndef build_context(root):\n    settings = params.load(root)\n    frozen = int(settings[\"header\"][\"frozen_register_revision\"])\n    stations, programmes, alias, scope = normalise.load_registers(root, frozen)\n    events = ordering.load_events(root, frozen, alias)\n    edges = depends.load_edges(root, frozen)\n    links = compensation.load_links(root, frozen)\n    by_id = {rec[\"event_id\"]: rec for rec in events}\n    norm = {}\n    cls = {}\n    for rec in events:\n        quantity, klass = normalise.normalise_quantity(rec, settings, stations)\n        norm[rec[\"event_id\"]] = quantity\n        cls[rec[\"event_id\"]] = klass\n    return {\n        \"root\": root, \"params\": settings, \"frozen\": frozen,\n        \"stations\": stations, \"programmes\": programmes, \"alias\": alias,\n        \"scope\": scope, \"events\": events, \"by_id\": by_id, \"edges\": edges,\n        \"links\": links, \"norm\": norm, \"cls\": cls,\n        \"cycles\": depends.cycle_members(events, edges, by_id),\n    }\n\n\ndef stage_of(reason):\n    table = {\"EVT-DRAFTREVISION\": \"r01\", \"EVT-WITHDRAWN\": \"r01\",\n             \"EVT-UNKNOWNSTATION\": \"r02\", \"EVT-UNKNOWNPROGRAMME\": \"r02\",\n             \"EVT-NONPOSITIVE\": \"r01\", \"EVT-IMPLAUSIBLE\": \"r01\",\n             \"CMP-WITHDRAWN\": \"r09\", \"CMP-NOTARGET\": \"r09\",\n             \"DEP-SELF\": \"r07\", \"DEP-CYCLE\": \"r07\", \"DEP-MISSING\": \"r07\"}\n    return table[reason]\n\n\ndef precedence_key(ctx, rec):\n    \"\"\"The five level ladder the directive puts in force: scope, then the\n    region rank on the roster, then the normalised quantity, then the\n    canonical position, then the event identifier.\"\"\"\n    scope_rank = 0 if str(rec.get(\"scope\", \"standard\")) == \"mandatory\" else 1\n    station = ctx[\"stations\"].get(str(rec[\"station\"]).strip())\n    region = str(station[\"region\"]).strip() if station else \"\"\n    region_rank = ctx[\"params\"][\"regions\"].get(region, 99)\n    quantity = ctx[\"norm\"].get(rec[\"event_id\"]) or 0\n    return (scope_rank, region_rank, quantity, int(rec[\"position\"]),\n            str(rec[\"event_id\"]))\n\n\ndef run(ctx, start, end, body=None, run_rounds=True):\n    events = ctx[\"events\"]\n    total = len(events)\n    if body is None:\n        state = derived.new_state()\n        watermark = 0\n    else:\n        state = derived.restore(body)\n        watermark = int(body[\"position\"])\n\n    from . import window as window_mod\n    window_start, window_end, positions = window_mod.build(\n        start, end, watermark, total)\n\n    quarantine = []\n    deferred = []\n    log = []\n    register = []\n    closure = {\"checkpoint\": 0, \"window\": 0}\n    unsatisfied = []\n    order = [1]\n\n    for p in positions:\n        rec = events[p - 1]\n        reason = transitions.screen(ctx, rec)\n        if reason is None:\n            reason, sources = depends.dependency_reason(ctx, rec, window_start,\n                                                        window_end)\n            if reason is None:\n                for _dep, where in sources:\n                    closure[where] += 1\n        if reason is not None:\n            quarantine.append({\"event_id\": rec[\"event_id\"], \"position\": p,\n                               \"stage\": stage_of(reason),\n                               \"reason_code\": reason,\n                               \"detail\": str(rec[\"kind\"])})\n            if reason.startswith(\"DEP-\"):\n                unsatisfied.append({\"event_id\": rec[\"event_id\"],\n                                    \"reason\": reason})\n            continue\n        if str(rec[\"kind\"]).strip() == \"compensate\":\n            compensation.apply_compensation(ctx, state, rec, register, order)\n            continue\n        if transitions.admissible(ctx, state, rec):\n            transitions.apply_transition(ctx, state, rec, log, order)\n        else:\n            state[\"pending\"].append(rec[\"event_id\"])\n            deferred.append(rec[\"event_id\"])\n\n    rounds = []\n    stable = True\n    if run_rounds:\n        ceiling = int(ctx[\"params\"][\"round_ceiling\"])\n        stable = False\n        for index in range(1, ceiling + 1):\n            queue = sorted(state[\"pending\"],\n                           key=lambda eid: precedence_key(ctx, ctx[\"by_id\"][eid]))\n            admitted = []\n            for eid in queue:\n                rec = ctx[\"by_id\"][eid]\n                if transitions.admissible(ctx, state, rec):\n                    state[\"pending\"].remove(eid)\n                    transitions.apply_transition(ctx, state, rec, log, order)\n                    state[\"counters\"][\"deferred_admitted\"] += 1\n                    admitted.append(eid)\n            if not admitted:\n                stable = True\n                break\n            rounds.append({\"round\": index, \"admitted\": admitted,\n                           \"admitted_count\": len(admitted)})\n\n    return {\"state\": state, \"watermark\": watermark,\n            \"window_start\": window_start, \"window_end\": window_end,\n            \"positions\": positions, \"quarantine\": quarantine,\n            \"deferred\": deferred, \"log\": log, \"register\": register,\n            \"closure\": closure, \"unsatisfied\": unsatisfied,\n            \"rounds\": rounds, \"stable\": stable}\n\n\ndef select_checkpoint(ctx, end):\n    return checkpointing.select(ctx, end)\n",
    "src/bcrep/transitions.py": "\"\"\"Stages r08 and r12. Ordinary transitions and the eligibility predicate.\"\"\"\nfrom . import derived, reading\n\n# The vocabulary as first lodged, read when no register is handed over.\nDEFAULT_FORMS = {\n    \"balance_at_least\": (\"active\", [\"station\", \"amount_cu\"]),\n    \"allotment_below\": (\"active\", [\"station\", \"programme\", \"amount_cu\"]),\n    \"counter_at_least\": (\"active\", [\"counter\", \"amount\"]),\n    \"no_pending\": (\"active\", []),\n    \"station_active\": (\"active\", [\"station\"]),\n}\n\n\ndef predicate_forms(root, frozen):\n    \"\"\"The predicate register in force. For each form the row with the\n    greatest revision at or below the frozen revision gives its status and\n    the order its arguments are written in.\"\"\"\n    held = {}\n    for row in reading.read_delim(root / \"eligibility_predicates.csv\"):\n        revision = int(str(row[\"revision\"]).strip())\n        if revision > frozen:\n            continue\n        name = row[\"predicate_id\"].strip()\n        if name not in held or revision >= held[name][0]:\n            held[name] = (revision, row)\n    return {name: (row[\"status\"].strip(), row[\"form\"].strip().split(\":\")[1:])\n            for name, (_revision, row) in held.items()}\n\n\ndef predicate_holds(text, state, stations, forms=None):\n    \"\"\"A predicate names its form and then its arguments in the order the\n    form in force lists them, read against the state as it stands immediately\n    before the event is offered. A form the register does not carry as\n    active is false whenever it is read.\"\"\"\n    if not text:\n        return True\n    parts = str(text).split(\":\")\n    head = parts[0]\n    status, names = (DEFAULT_FORMS if forms is None else forms).get(\n        head, (\"\", []))\n    if status != \"active\" or len(parts) - 1 != len(names):\n        return False\n    args = dict(zip(names, parts[1:]))\n    if head == \"balance_at_least\":\n        return (state[\"balances\"].get(args[\"station\"], 0)\n                >= int(args[\"amount_cu\"]))\n    if head == \"allotment_below\":\n        inner = state[\"allotments\"].get(args[\"station\"], {})\n        return inner.get(args[\"programme\"], 0) < int(args[\"amount_cu\"])\n    if head == \"counter_at_least\":\n        return state[\"counters\"].get(args[\"counter\"], 0) >= int(args[\"amount\"])\n    if head == \"no_pending\":\n        return not state[\"pending\"]\n    if head == \"station_active\":\n        row = stations.get(args[\"station\"])\n        return row is not None and str(row[\"status\"]).strip() == \"active\"\n    return False\n\n\ndef admissible(ctx, state, rec):\n    if \"forms\" not in ctx:\n        ctx[\"forms\"] = predicate_forms(ctx[\"root\"], ctx[\"frozen\"])\n    return predicate_holds(rec.get(\"requires\"), state, ctx[\"stations\"],\n                           ctx[\"forms\"])\n\n\ndef apply_transition(ctx, state, rec, log, order):\n    eid = rec[\"event_id\"]\n    quantity = ctx[\"norm\"][eid]\n    station = str(rec[\"station\"]).strip()\n    programme = str(rec[\"programme\"]).strip()\n    touched = {station}\n    kind = str(rec[\"kind\"]).strip()\n    if kind == \"grant\":\n        derived.move(state, station, programme, quantity)\n        state[\"counters\"][\"grants\"] += 1\n        state[\"counters\"][\"granted_cu\"] += quantity\n    elif kind == \"retire\":\n        derived.move(state, station, programme, -quantity)\n        state[\"counters\"][\"retires\"] += 1\n        state[\"counters\"][\"retired_cu\"] += quantity\n    else:\n        other = str(rec[\"counterparty\"]).strip()\n        derived.move(state, station, programme, -quantity)\n        derived.move(state, other, programme, quantity)\n        touched.add(other)\n        state[\"counters\"][\"transfers\"] += 1\n        state[\"counters\"][\"transferred_cu\"] += quantity\n    derived.settle(state, ctx, touched)\n    state[\"applied\"].append(eid)\n    log.append({\"order\": order[0], \"event_id\": eid,\n                \"position\": int(rec[\"position\"]), \"kind\": kind,\n                \"station\": station, \"programme\": programme,\n                \"quantity_cu\": quantity,\n                \"balance_after\": state[\"balances\"].get(station, 0)})\n    order[0] += 1\n\n\ndef screen(ctx, rec):\n    \"\"\"Stage r01 and r09 screening. The order the policy paper puts the tests\n    in decides which code a record that fails two tests carries.\"\"\"\n    eid = rec[\"event_id\"]\n    checks = {\n        \"EVT-DRAFTREVISION\": lambda: bool(rec[\"draft\"]),\n        \"EVT-WITHDRAWN\": lambda: bool(rec[\"withdrawn\"]),\n        \"EVT-UNKNOWNSTATION\": lambda: _station_unknown(ctx, rec),\n        \"EVT-UNKNOWNPROGRAMME\": lambda: _programme_unknown(ctx, rec),\n        \"EVT-NONPOSITIVE\": lambda: _nonpositive(ctx, rec),\n        \"EVT-IMPLAUSIBLE\": lambda: _implausible(ctx, rec),\n        \"CMP-WITHDRAWN\": lambda: _link_absent(ctx, rec),\n        \"CMP-NOTARGET\": lambda: _target_absent(ctx, rec),\n    }\n    for code in ctx[\"params\"][\"screen_order\"]:\n        test = checks.get(code)\n        if test is not None and test():\n            return code\n    return None\n\n\ndef _station_unknown(ctx, rec):\n    if str(rec[\"station\"]).strip() not in ctx[\"stations\"]:\n        return True\n    if str(rec[\"kind\"]).strip() == \"transfer\":\n        other = str(rec.get(\"counterparty\") or \"\").strip()\n        return other == \"\" or other not in ctx[\"stations\"]\n    return False\n\n\ndef _programme_unknown(ctx, rec):\n    if str(rec[\"kind\"]).strip() == \"compensate\":\n        return False\n    return str(rec[\"programme\"]).strip() not in ctx[\"programmes\"]\n\n\ndef _nonpositive(ctx, rec):\n    if str(rec[\"kind\"]).strip() == \"compensate\":\n        return False\n    quantity = ctx[\"norm\"].get(rec[\"event_id\"])\n    return quantity is None or quantity <= 0\n\n\ndef _implausible(ctx, rec):\n    if str(rec[\"kind\"]).strip() == \"compensate\":\n        return False\n    quantity = ctx[\"norm\"].get(rec[\"event_id\"])\n    if quantity is None:\n        return False\n    return quantity > ctx[\"params\"][\"implausible_ceiling\"]\n\n\ndef _link_absent(ctx, rec):\n    if str(rec[\"kind\"]).strip() != \"compensate\":\n        return False\n    link = ctx[\"links\"].get(rec[\"event_id\"])\n    return link is None or link[\"status\"].strip() != \"registered\"\n\n\ndef _target_absent(ctx, rec):\n    if str(rec[\"kind\"]).strip() != \"compensate\":\n        return False\n    link = ctx[\"links\"].get(rec[\"event_id\"])\n    if link is None:\n        return False\n    return link[\"target_event_id\"].strip() not in ctx[\"by_id\"]\n",
    "src/bcrep/window.py": "\"\"\"Stage r06. Replay window construction.\n\nThe requested range is start inclusive and end exclusive. The restored\nwatermark is a processed position, never a position to replay again, so the\nwindow opens at the later of the requested start and the watermark plus one.\n\"\"\"\n\n\ndef build(start, end, watermark, total):\n    window_start = max(int(start), int(watermark) + 1)\n    window_end = int(end)\n    positions = [p for p in range(window_start, min(window_end, total + 1))]\n    return window_start, window_end, positions\n\n\ndef skipped_before(start, watermark):\n    return max(0, int(watermark) - int(start) + 1)\n",
    "tests/test_shipped.py": "\"\"\"The suite the package shipped with.\n\nIt exercises the shapes the engine works in, not the epoch it publishes, so it\npasses exactly as it shipped. Where the engine departs from the working papers\nthe suite is silent, which tells a reader where the faults are absent rather\nthan where they are.\n\"\"\"\nimport unittest\nfrom fractions import Fraction\n\nfrom bcrep import derived, normalise, transitions, window\n\n\nclass TestArithmetic(unittest.TestCase):\n    def test_half_up_positive(self):\n        self.assertEqual(normalise.half_up(Fraction(5, 2)), 3)\n\n    def test_half_up_negative(self):\n        self.assertEqual(normalise.half_up(Fraction(-5, 2)), -3)\n\n    def test_half_up_whole(self):\n        self.assertEqual(normalise.half_up(Fraction(7, 1)), 7)\n\n    def test_ratio_places(self):\n        self.assertEqual(normalise.ratio_text(Fraction(1, 4), 12),\n                         \"0.250000000000\")\n\n    def test_ratio_no_negative_zero(self):\n        self.assertEqual(normalise.ratio_text(Fraction(0, 5), 12),\n                         \"0.000000000000\")\n\n    def test_safe_ratio_zero_denominator(self):\n        self.assertEqual(normalise.safe_ratio(3, 0, 12), \"0.000000000000\")\n\n\nclass TestState(unittest.TestCase):\n    def test_new_state_counters(self):\n        state = derived.new_state()\n        self.assertEqual(sorted(state[\"counters\"]), derived.COUNTER_NAMES)\n\n    def test_move_creates_nested_entry(self):\n        state = derived.new_state()\n        derived.move(state, \"ST-0001\", \"PGM-0001\", 40)\n        self.assertEqual(state[\"allotments\"][\"ST-0001\"][\"PGM-0001\"], 40)\n\n    def test_state_body_drops_zero_rows(self):\n        state = derived.new_state()\n        derived.move(state, \"ST-0001\", \"PGM-0001\", 0)\n        body = derived.state_body(state, 3)\n        self.assertEqual(body[\"balances\"], {})\n        self.assertEqual(body[\"allotments\"], {})\n\n    def test_restore_carries_every_field(self):\n        body = {\"position\": 4, \"balances\": {\"ST-0001\": 5},\n                \"allotments\": {\"ST-0001\": {\"PGM-0001\": 5}},\n                \"counters\": {k: 0 for k in derived.COUNTER_NAMES},\n                \"pending\": [\"EVT-000009\"], \"applied\": [\"EVT-000004\"],\n                \"reversed\": []}\n        state = derived.restore(body)\n        self.assertEqual(state[\"pending\"], [\"EVT-000009\"])\n        self.assertEqual(state[\"applied\"], [\"EVT-000004\"])\n        self.assertEqual(state[\"balances\"][\"ST-0001\"], 5)\n\n    def test_state_digest_is_stable(self):\n        body = {\"position\": 1, \"balances\": {}, \"allotments\": {},\n                \"counters\": {k: 0 for k in derived.COUNTER_NAMES},\n                \"pending\": [], \"applied\": [], \"reversed\": []}\n        self.assertEqual(derived.state_digest(body), derived.state_digest(body))\n\n\nclass TestPredicates(unittest.TestCase):\n    def setUp(self):\n        self.state = derived.new_state()\n        self.state[\"balances\"][\"ST-0001\"] = 700\n        self.state[\"counters\"][\"grants\"] = 6\n        self.stations = {\"ST-0001\": {\"status\": \"active\", \"class\": \"AX\",\n                                     \"region\": \"R-ALPHA\"}}\n\n    def test_empty_predicate_holds(self):\n        self.assertTrue(transitions.predicate_holds(None, self.state,\n                                                    self.stations))\n\n    def test_balance_predicate(self):\n        self.assertTrue(transitions.predicate_holds(\n            \"balance_at_least:ST-0001:700\", self.state, self.stations))\n        self.assertFalse(transitions.predicate_holds(\n            \"balance_at_least:ST-0001:701\", self.state, self.stations))\n\n    def test_counter_predicate(self):\n        self.assertTrue(transitions.predicate_holds(\n            \"counter_at_least:grants:6\", self.state, self.stations))\n\n    def test_unknown_form_is_false(self):\n        self.assertFalse(transitions.predicate_holds(\n            \"hub_open:H-01\", self.state, self.stations))\n\n\nclass TestWindow(unittest.TestCase):\n    def test_window_reports_the_requested_range(self):\n        start, end, _positions = window.build(1, 5, 0, 20)\n        self.assertEqual((start, end), (1, 5))\n\n    def test_window_clamps_to_history(self):\n        _s, _e, positions = window.build(1, 50, 0, 3)\n        self.assertEqual(positions, [1, 2, 3])\n\n    def test_skipped_before_watermark(self):\n        self.assertEqual(window.skipped_before(1, 9), 9)\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n",
}


# --------------------------------------------------------------------------
# graded assertions
#
# Two surfaces. The documents delivered for the shipped epoch are compared
# against this file's own reference chain over a corpus minted here from
# SAMPLE_SEED. The package delivered beside them is extracted and driven over
# three epochs minted from seeds it has never seen.
# --------------------------------------------------------------------------
MINTED_SEEDS = (EVAL_SEED, CHALLENGE_SEED, PROBE_SEED)

SETTLED_GROUP = ["alias_resolution.jsonl", "checkpoint_selection.json",
                 "defect_register.md", "repair_report.json"]
ORDER_GROUP = ["canonical_order.csv"]
PARAMETER_GROUP = ["unit_normalisation.json"]
BOUNDARY_GROUP = ["replay_window.json", "checkpoint_reconciliation.json"]
CLOSURE_GROUP = ["dependency_closure.json", "quarantine_ledger.csv"]
ROUNDS_GROUP = ["eligibility_passes.json", "state_at_event.json"]
REVERSAL_GROUP = ["compensation_register.csv", "transition_log.jsonl"]
SETTLEMENT_GROUP = ["final_state.json", "derived_counters.csv",
                    "derived_index.jsonl", "bounded_replay.json",
                    "equivalence_report.json", "summary.json",
                    "verification_notes.md", "selftest.json",
                    "run_manifest.txt"]

PREPARATION_FAMILY = ["unit_normalisation.json", "alias_resolution.jsonl",
                      "canonical_order.csv", "quarantine_ledger.csv"]
WINDOW_FAMILY = ["checkpoint_selection.json", "replay_window.json",
                 "dependency_closure.json", "checkpoint_reconciliation.json"]
REPLAY_FAMILY = ["transition_log.jsonl", "compensation_register.csv",
                 "derived_counters.csv", "eligibility_passes.json"]
PUBLICATION_FAMILY = ["final_state.json", "derived_index.jsonl",
                      "equivalence_report.json", "state_at_event.json",
                      "bounded_replay.json", "summary.json", "selftest.json",
                      "repair_report.json", "defect_register.md",
                      "verification_notes.md", "run_manifest.txt"]

_CACHE = {}


def _scratch(tag):
    path = Path(tempfile.mkdtemp(prefix="bcrep-" + tag + "-"))
    os.chmod(path, 0o777)
    return path


def _corpus(seed):
    key = ("corpus", seed)
    if key not in _CACHE:
        root = write_corpus(_scratch("corpus"), seed)
        for path in [root] + list(root.rglob("*")):
            os.chmod(path, 0o777 if path.is_dir() else 0o666)
        _CACHE[key] = root
        _pristine(root)
    return _CACHE[key]


def _tree_digests(root):
    """One digest per file of a paper directory, keyed by relative path."""
    return {str(path.relative_to(root)): digest_bytes(path.read_bytes())
            for path in sorted(Path(root).rglob("*")) if path.is_file()}


def _pristine(root):
    """The digests a paper directory carried when it was first laid down.

    Recorded once per path and reused, so a package that writes the same
    substitution on every run is caught on the second run as well as the
    first. Comparing against the state immediately before each run would let
    a repeated write look like no change at all."""
    key = ("pristine", str(Path(root).resolve()))
    if key not in _CACHE:
        _CACHE[key] = _tree_digests(root)
    return _CACHE[key]


def _reference(seed, rules=()):
    key = ("reference", seed, tuple(sorted(rules)))
    if key not in _CACHE:
        out = _scratch("reference")
        # The ground truth is written and read back by the verifier alone, so
        # its directory is closed to the demoted uid the package runs under.
        os.chmod(out, 0o700)
        ref_publish(_corpus(seed), out, rules)
        _CACHE[key] = {p.name: p.read_bytes() for p in sorted(out.iterdir())}
    return _CACHE[key]


def _delivered(name):
    path = Path(_OUT_ROOT[0]) / name
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


def _kill_leftovers(pid):
    """Kill every process the delivered code left behind.

    The child leads a session of its own, so its whole process group goes
    first. When the child ran demoted, any process still running as the
    demoted uid has escaped that group (a setsid daemon), and it is killed
    too, so no delivered code outlives the check that started it."""
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # the group had already exited
    if os.geteuid() != 0 or not Path("/proc").is_dir():
        return
    for _sweep in range(5):
        found = False
        for status in sorted(Path("/proc").glob("[0-9]*/status")):
            try:
                lines = status.read_text().splitlines()
            except OSError:
                continue  # the process exited while it was being read
            uids = [line.split()[1:] for line in lines if line.startswith("Uid:")]
            if uids and "65534" in uids[0]:
                found = True
                try:
                    os.kill(int(status.parent.name), signal.SIGKILL)
                except ProcessLookupError:
                    pass  # it exited between the read and the kill
        if not found:
            return


_DELIVERED_RUN = threading.Lock()


def _run_delivered(argv, cwd, env):
    """Run delivered code demoted, in a session of its own, with a timeout,
    and reap everything it started before returning.

    The checks run concurrently, so one run at a time holds the lock: the
    sweep of the demoted uid then reaches only what this run left behind.
    Output goes to files rather than pipes, so a process that inherits them
    and stays alive cannot hold the wait open past the child's own exit."""
    with _DELIVERED_RUN, tempfile.TemporaryFile() as out_file, \
            tempfile.TemporaryFile() as err_file:
        proc = subprocess.Popen(argv, stdout=out_file, stderr=err_file,
                                env=env, cwd=cwd, preexec_fn=_demote(),
                                start_new_session=True)
        try:
            proc.wait(timeout=PACKAGE_RUN_TIMEOUT_SEC)
        finally:
            _kill_leftovers(proc.pid)
            proc.wait()
        out_file.seek(0)
        err_file.seek(0)
        stdout = out_file.read().decode("utf-8", "replace")
        stderr = err_file.read().decode("utf-8", "replace")
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


def _package_root():
    if "package" not in _CACHE:
        raw = _delivered("package.zip")
        root = _scratch("package")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for member in archive.namelist():
                if member.startswith("/") or ".." in Path(member).parts:
                    raise AssertionError("archive member escapes the root: "
                                         + member)
            expanded = sum(info.file_size for info in archive.infolist())
            if expanded > ARCHIVE_BUDGET_BYTES:
                raise AssertionError("the archive expands to "
                                     + str(expanded)
                                     + " bytes, past the grading budget")
            archive.extractall(root)
        for path in [root] + list(root.rglob("*")):
            os.chmod(path, 0o777 if path.is_dir() else 0o666)
        _CACHE["package"] = root
    return _CACHE["package"]


def _drive(data, tag, cwd=None, data_first=False):
    """Run the delivered package over one corpus and collect what it wrote.

    The destination is named but not created, because the contract makes the
    package responsible for creating it when it is absent.

    The paper directory is digested before the run and again after it. The
    contract makes it read only ("leave the paper directory byte for byte as
    it found it"), and the reference chain derives the expected answer from
    that same directory, so a package that writes into it is both breaking the
    contract and moving the ground truth it is about to be graded against."""
    root = _package_root()
    before = _pristine(data)
    out = _scratch(tag) / "published"
    home = _scratch(tag + "-home") if cwd is None else cwd
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin",
           "PYTHONPATH": str(root / "src"),
           "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": str(home), "TMPDIR": str(home), "LC_ALL": "C"}
    # The contract puts the two options in either order, so the order is
    # varied here rather than fixed: a package that accepts only one of them
    # breaks the entry point clause and fails the epochs driven the other way.
    options = (["--data", str(data), "--out", str(out)] if data_first
               else ["--out", str(out), "--data", str(data)])
    proc = _run_delivered([sys.executable, "-m", PACKAGE_NAME] + options,
                          cwd=str(home), env=env)
    if proc.returncode != 0:
        raise AssertionError("the delivered package exited "
                             + str(proc.returncode) + ": "
                             + proc.stderr.strip()[-400:])
    if not out.is_dir():
        raise AssertionError("the package left the destination uncreated: "
                             + str(out))
    after = _tree_digests(data)
    touched = sorted(set(before) ^ set(after))
    touched += sorted(name for name in before
                      if name in after and before[name] != after[name])
    if touched:
        raise AssertionError("the package wrote into the paper directory: "
                             + ", ".join(sorted(set(touched))[:8]))
    return {p.name: p.read_bytes() for p in sorted(out.iterdir())}


def _case(seed, tag="case"):
    key = ("case", seed, tag)
    if key not in _CACHE:
        # The reference is pinned BEFORE the delivered package runs. It is
        # derived from the same paper directory the package is handed, so
        # computing it afterwards would let a package that rewrote that
        # directory be graded against its own substitution.
        _reference(seed)
        _CACHE[key] = _drive(_corpus(seed), tag,
                             data_first=(seed == PROBE_SEED))
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
    _compare(family, got, expected, "the shipped epoch")


def _minted(seed, family):
    _compare(family, _case(seed), _reference(seed),
             "the minted epoch " + str(seed))


# --------------------------------------------------------------------------
# structural assertions
# --------------------------------------------------------------------------
def _assert_delivered_documents_present_and_parse():
    """POSITIVE: every declared document is present, parses in its own shape,
    ends in one line feed, carries no carriage return, and publishes every
    ratio at twelve places with no negative zero."""
    for name in ARTIFACT_NAMES + ["package.zip"]:
        assert _delivered(name), name + " is empty"
    for name in ARTIFACT_NAMES:
        payload = _delivered(name)
        assert b"\r" not in payload, name + " carries a carriage return"
        assert payload.endswith(b"\n"), name + " has no trailing newline"
        assert not payload.endswith(b"\n\n"), name + " has a blank last line"
        text = payload.decode("utf-8")
        if name.endswith(".jsonl"):
            for line in text.splitlines():
                json.loads(line)
        elif name.endswith(".json"):
            json.loads(text)
        elif name.endswith(".csv"):
            rows = [ln.split(",") for ln in text.splitlines()]
            assert len({len(r) for r in rows}) == 1, name + " is ragged"
    ratios = []
    for record in _delivered("derived_index.jsonl").decode("utf-8").splitlines():
        ratios.append(json.loads(record)["share"])
    ratios.append(json.loads(
        _delivered("summary.json").decode("utf-8"))["balance_share"])
    for value in ratios:
        head, _dot, tail = str(value).partition(".")
        assert len(tail) == RATIO_PLACES, \
            "ratio is not at twelve places: " + str(value)
        assert not (head == "-0" and set(tail) == {"0"}), \
            "negative zero was published"


def _assert_delivered_package_shape():
    """POSITIVE: the delivered archive carries the project layout the package
    expectations name, every module, the shipped suite byte for byte and
    passing against the delivered source, and no import from outside the
    standard library."""
    root = _package_root()
    assert (root / "pyproject.toml").is_file(), \
        "pyproject.toml is not at the archive root"
    for module in PACKAGE_MODULES:
        path = root / "src" / PACKAGE_NAME / (module + ".py")
        assert path.is_file(), "module is absent: " + module
    shipped = PACKAGE_FILES["tests/test_shipped.py"].encode("utf-8")
    carried = root / "tests" / "test_shipped.py"
    assert carried.is_file(), "the shipped suite was dropped"
    assert carried.read_bytes() == shipped, "the shipped suite was edited"
    allowed = set(sys.stdlib_module_names)
    for path in sorted((root / "src" / PACKAGE_NAME).glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    head = alias.name.split(".")[0]
                    assert head in allowed or head == PACKAGE_NAME, \
                        "third party import " + alias.name + " in " + path.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                head = (node.module or "").split(".")[0]
                assert head in allowed or head == PACKAGE_NAME, \
                    "third party import " + str(node.module) + " in " + path.name
    home = _scratch("suite-home")
    proc = _run_delivered([sys.executable, "-m", "unittest", "discover",
                           "-s", "tests", "-t", "tests", "-q"],
                          cwd=str(root),
                          env={"PATH": "/usr/local/bin:/usr/bin:/bin",
                               "PYTHONPATH": str(root / "src"),
                               "PYTHONDONTWRITEBYTECODE": "1",
                               "HOME": str(home), "TMPDIR": str(home),
                               "LC_ALL": "C"})
    assert proc.returncode == 0, \
        "the shipped suite fails against the delivered source: " + proc.stderr.strip()[-400:]


# --------------------------------------------------------------------------
# the shipped epoch, graded one stage group at a time so a repair that lands
# part of the chain is credited for the part it landed
# --------------------------------------------------------------------------
def _assert_shipped_settled_documents_exact():
    """POSITIVE: the documents no stage of the replay can move are exact."""
    _shipped(SETTLED_GROUP)


def _assert_shipped_canonical_order_exact():
    """POSITIVE: the canonical order of the shipped epoch is exact."""
    _shipped(ORDER_GROUP)


def _assert_shipped_parameter_layer_exact():
    """POSITIVE: the parameter layer record of the shipped epoch is exact."""
    _shipped(PARAMETER_GROUP)


def _assert_shipped_boundary_record_exact():
    """POSITIVE: the window and checkpoint reconciliation record of the shipped
    epoch is exact."""
    _shipped(BOUNDARY_GROUP)


def _assert_shipped_closure_record_exact():
    """POSITIVE: the dependency closure and quarantine record of the shipped
    epoch is exact."""
    _shipped(CLOSURE_GROUP)


def _assert_shipped_rounds_record_exact():
    """POSITIVE: the eligibility round and probe record of the shipped epoch is
    exact."""
    _shipped(ROUNDS_GROUP)


def _assert_shipped_reversal_record_exact():
    """POSITIVE: the compensation and transition record of the shipped epoch is
    exact."""
    _shipped(REVERSAL_GROUP)


def _assert_shipped_settlement_record_exact():
    """POSITIVE: the settled state, the derived record and the two digests of
    the shipped epoch are exact."""
    _shipped(SETTLEMENT_GROUP)


# --------------------------------------------------------------------------
# minted epochs, driven through the delivered package
# --------------------------------------------------------------------------
def _assert_package_eval_preparation_exact():
    """POSITIVE: the delivered package prepares a minted epoch exactly."""
    _minted(EVAL_SEED, PREPARATION_FAMILY)


def _assert_package_eval_window_exact():
    """POSITIVE: the delivered package selects and builds the window of a
    minted epoch exactly."""
    _minted(EVAL_SEED, WINDOW_FAMILY)


def _assert_package_eval_replay_exact():
    """POSITIVE: the delivered package replays a minted epoch exactly."""
    _minted(EVAL_SEED, REPLAY_FAMILY)


def _assert_package_eval_publication_exact():
    """POSITIVE: the delivered package publishes a minted epoch exactly, into a
    destination holding the twenty three derived documents and nothing else."""
    written = sorted(_case(EVAL_SEED))
    if written != sorted(ARTIFACT_NAMES):
        raise AssertionError("the destination holds " + ", ".join(written))
    _minted(EVAL_SEED, PUBLICATION_FAMILY)


def _assert_package_challenge_window_exact():
    """POSITIVE: the delivered package selects and builds the window of a
    second minted epoch exactly."""
    _minted(CHALLENGE_SEED, WINDOW_FAMILY)


def _assert_package_challenge_replay_exact():
    """POSITIVE: the delivered package replays a second minted epoch exactly."""
    _minted(CHALLENGE_SEED, REPLAY_FAMILY)


def _assert_package_challenge_publication_exact():
    """POSITIVE: the delivered package publishes a second minted epoch
    exactly, into a destination holding the twenty three derived documents
    and nothing else."""
    written = sorted(_case(CHALLENGE_SEED))
    if written != sorted(ARTIFACT_NAMES):
        raise AssertionError("the destination holds " + ", ".join(written))
    _minted(CHALLENGE_SEED, PUBLICATION_FAMILY)


def _assert_package_probe_window_exact():
    """POSITIVE: the delivered package selects and builds the window of a third
    minted epoch exactly."""
    _minted(PROBE_SEED, WINDOW_FAMILY)


def _assert_package_probe_replay_exact():
    """POSITIVE: the delivered package replays a third minted epoch exactly."""
    _minted(PROBE_SEED, REPLAY_FAMILY)


def _assert_package_probe_publication_exact():
    """POSITIVE: the delivered package publishes a third minted epoch
    exactly, into a destination holding the twenty three derived documents
    and nothing else."""
    written = sorted(_case(PROBE_SEED))
    if written != sorted(ARTIFACT_NAMES):
        raise AssertionError("the destination holds " + ", ".join(written))
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


def _assert_negative_weight_watermark_position_replayed_again():
    """NEGATIVE: the window opened at the restored watermark instead of one
    past it, so the event already folded into the checkpoint was applied a
    second time."""
    _detector("R_WATERMARK")


def _assert_negative_weight_compensation_target_sought_in_the_window():
    """NEGATIVE: a compensating event whose target stands behind the restored
    checkpoint was quarantined as having no target, instead of being resolved
    against the whole canonical history."""
    _detector("R_TARGET_IN_WINDOW")


def _assert_negative_weight_pending_queue_offered_once():
    """NEGATIVE: the pending queue was offered a single time instead of once
    per round up to the round ceiling the board memo carries."""
    _detector("R_SINGLE_ROUND")


def _assert_negative_weight_reversal_left_the_derived_counters():
    """NEGATIVE: a compensation came off the balances and the allotments and
    left the derived counter of the reversed kind where it stood."""
    _detector("R_NO_DERIVED_REVERSAL")


def _assert_negative_weight_checkpoint_dependency_called_missing():
    """NEGATIVE: a dependency already folded into the restored checkpoint was
    reported as missing and its event was quarantined."""
    _detector("R_CHECKPOINT_DEP_MISSING")


def _assert_negative_weight_end_boundary_included():
    """NEGATIVE: the requested end position was replayed, so the range was
    read as closed at both ends."""
    _detector("R_END_INCLUSIVE")


def _assert_negative_weight_target_reversed_twice():
    """NEGATIVE: two compensating events named one target and both took
    effect, so the target came off the state twice."""
    _detector("R_DUPLICATE_APPLIED")


def _assert_negative_weight_carry_quantum_defaulted():
    """NEGATIVE: the carry quantum was taken from a constant in place of the
    per class quantum on the live workbook sheet."""
    _detector("R_DEFAULT_QUANTUM")



def _assert_negative_weight_queue_offered_in_canonical_order():
    """NEGATIVE: the pending queue was offered in canonical order in place of
    the five level ladder the directive puts in force."""
    _detector("R_QUEUE_CANONICAL")


def _assert_negative_weight_rebinds_verifier_dependencies():
    """NEGATIVE: the delivered archive carries a module or a startup hook whose
    name would shadow a standard library module or a site hook once the
    archive is placed on the import path, which is how a submission reaches
    for the machinery that grades it."""
    root = _package_root()
    # Only two kinds of file can actually shadow anything: a path
    # configuration file, which the interpreter reads wherever it sits, and a
    # module at an import root, which is the source directory the package is
    # run from. A module nested inside a subpackage is reachable only through
    # its own package name and shadows nothing, so an honest tree that happens
    # to carry src/bcrep/helpers/io.py is not a submission reaching for the
    # machinery that grades it.
    shadowed = set(sys.stdlib_module_names) | {"pytest", "pth"}
    hooks = {"sitecustomize", "usercustomize", "conftest"}
    carried = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".pth":
            carried.append(str(path.relative_to(root)))
        elif path.suffix == ".py":
            stem = path.stem
            at_import_root = path.parent == root / "src"
            if stem in hooks or (stem in shadowed and at_import_root):
                carried.append(str(path.relative_to(root)))
    assert carried, "the archive shadows no verifier dependency"


def _assert_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: the shipped documents are right while the delivered package
    produces no usable output at all on any minted epoch, so there is no engine
    behind the delivery. The trigger is the absence of output rather than the
    wrongness of it: a package that runs and reads a rule wrongly is an engine
    with a defect and already forfeits the minted tier without being charged
    for a copy it did not make."""
    expected = _reference(SAMPLE_SEED)
    core = PREPARATION_FAMILY + WINDOW_FAMILY + REPLAY_FAMILY
    if any(_delivered(name) != expected[name] for name in core):
        raise AssertionError("the shipped record is wrong; this detector stays silent")
    silent = 0
    for seed in MINTED_SEEDS:
        try:
            _case(seed)
        except Exception:
            silent += 1
    assert silent == len(MINTED_SEEDS)


def _assert_negative_weight_package_ignores_its_input():
    """NEGATIVE: the package writes one constant record whatever epoch it is
    pointed at, and that constant is not the shipped epoch. The shipped epoch
    case belongs to the detector above, so the two are disjoint and one
    delivery never fires both."""
    shipped = _reference(SAMPLE_SEED)["final_state.json"]
    first = _case(EVAL_SEED)["final_state.json"]
    second = _case(PROBE_SEED)["final_state.json"]
    if first == shipped:
        raise AssertionError("the package emits the shipped epoch; the corpus "
                             "detector owns that defect")
    assert first == second


def _assert_negative_weight_nondeterministic_output():
    """NEGATIVE: two runs of the package over one corpus, at one identical
    path, disagree, so the delivered figures are not reproducible. Holding the
    path fixed is what keeps this detector off the directory name defect."""
    first = _case(CHALLENGE_SEED)
    second = _drive(_corpus(CHALLENGE_SEED), "repeat")
    assert any(first.get(name) != second.get(name) for name in ARTIFACT_NAMES)


def _assert_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: the package is reproducible at one path and still writes
    something else when the same epoch is presented under a different
    directory name. The reproducibility clause keeps this detector disjoint
    from the one above."""
    first = _case(CHALLENGE_SEED)
    second = _drive(_corpus(CHALLENGE_SEED), "repeat")
    if any(first.get(name) != second.get(name) for name in ARTIFACT_NAMES):
        raise AssertionError("the package is not reproducible; the determinism "
                             "detector owns that defect")
    moved = _scratch("renamed") / "papers_under_another_name"
    shutil.copytree(_corpus(CHALLENGE_SEED), moved)
    for path in [moved] + list(moved.rglob("*")):
        os.chmod(path, 0o777 if path.is_dir() else 0o666)
    third = _drive(moved, "renamed-run")
    assert any(first.get(name) != third.get(name) for name in ARTIFACT_NAMES)


def _assert_negative_weight_reads_training_corpus_at_runtime():
    """NEGATIVE: the package reached for a corpus sitting beside its working
    directory in place of the one its data option named."""
    wanted = _reference(EVAL_SEED)["final_state.json"]
    decoy = _reference(PROBE_SEED)["final_state.json"]
    home = _scratch("ambient")
    shutil.copytree(_corpus(PROBE_SEED), home / "data")
    for path in list((home / "data").rglob("*")) + [home / "data"]:
        os.chmod(path, 0o777 if path.is_dir() else 0o666)
    got = _drive(_corpus(EVAL_SEED), "ambient-run", cwd=home)
    if got.get("final_state.json") == wanted:
        raise AssertionError("the package read the corpus it was given; this "
                             "detector stays silent")
    assert got.get("final_state.json") == decoy





# --------------------------------------------------------------------------
# rewardkit criteria
#
# Each check wraps one assertion above. The assertion signals by raising, so
# the wrapper converts that signal into the bool rewardkit grades on: a
# positive pays when its property holds, and a negative fires only when its
# cheat is positively identified. Nothing here raises, so no check can abort
# the run and leave the bundle without a reward.
# --------------------------------------------------------------------------
def _graded(workspace, assertion):
    _OUT_ROOT[0] = str(Path(workspace) / "out")
    try:
        assertion()
    except BaseException:
        # BaseException rather than Exception: the reference chain signals a
        # broken author side invariant with SystemExit, which would otherwise
        # abort rewardkit and leave the submission with no reward at all.
        return False
    return True


@criterion(description="every declared document is present, parses in its own shape, ends in one line feed, carries no carriage return, and publishes every ratio at twelve places with no negative zero.")
def delivered_documents_present_and_parse(workspace) -> bool:
    return _graded(workspace, _assert_delivered_documents_present_and_parse)


@criterion(description="the delivered archive carries the project layout the package expectations name, every module, the shipped suite byte for byte, and no import from outside the standard library.")
def delivered_package_shape(workspace) -> bool:
    return _graded(workspace, _assert_delivered_package_shape)


@criterion(description="the documents no stage of the replay can move are exact.")
def shipped_settled_documents_exact(workspace) -> bool:
    return _graded(workspace, _assert_shipped_settled_documents_exact)


@criterion(description="the canonical order of the shipped epoch is exact.")
def shipped_canonical_order_exact(workspace) -> bool:
    return _graded(workspace, _assert_shipped_canonical_order_exact)


@criterion(description="the parameter layer record of the shipped epoch is exact.")
def shipped_parameter_layer_exact(workspace) -> bool:
    return _graded(workspace, _assert_shipped_parameter_layer_exact)


@criterion(description="the window and checkpoint reconciliation record of the shipped epoch is exact.")
def shipped_boundary_record_exact(workspace) -> bool:
    return _graded(workspace, _assert_shipped_boundary_record_exact)


@criterion(description="the dependency closure and quarantine record of the shipped epoch is exact.")
def shipped_closure_record_exact(workspace) -> bool:
    return _graded(workspace, _assert_shipped_closure_record_exact)


@criterion(description="the eligibility round and probe record of the shipped epoch is exact.")
def shipped_rounds_record_exact(workspace) -> bool:
    return _graded(workspace, _assert_shipped_rounds_record_exact)


@criterion(description="the compensation and transition record of the shipped epoch is exact.")
def shipped_reversal_record_exact(workspace) -> bool:
    return _graded(workspace, _assert_shipped_reversal_record_exact)


@criterion(description="the settled state, the derived record and the two digests of the shipped epoch are exact.")
def shipped_settlement_record_exact(workspace) -> bool:
    return _graded(workspace, _assert_shipped_settlement_record_exact)


@criterion(description="the delivered package prepares a minted epoch exactly.")
def package_eval_preparation_exact(workspace) -> bool:
    return _graded(workspace, _assert_package_eval_preparation_exact)


@criterion(description="the delivered package selects and builds the window of a minted epoch exactly.")
def package_eval_window_exact(workspace) -> bool:
    return _graded(workspace, _assert_package_eval_window_exact)


@criterion(description="the delivered package replays a minted epoch exactly.")
def package_eval_replay_exact(workspace) -> bool:
    return _graded(workspace, _assert_package_eval_replay_exact)


@criterion(description="the delivered package publishes a minted epoch exactly, into a destination holding the twenty three derived documents and nothing else.")
def package_eval_publication_exact(workspace) -> bool:
    return _graded(workspace, _assert_package_eval_publication_exact)


@criterion(description="the delivered package selects and builds the window of a second minted epoch exactly.")
def package_challenge_window_exact(workspace) -> bool:
    return _graded(workspace, _assert_package_challenge_window_exact)


@criterion(description="the delivered package replays a second minted epoch exactly.")
def package_challenge_replay_exact(workspace) -> bool:
    return _graded(workspace, _assert_package_challenge_replay_exact)


@criterion(description="the delivered package publishes a second minted epoch exactly.")
def package_challenge_publication_exact(workspace) -> bool:
    return _graded(workspace, _assert_package_challenge_publication_exact)


@criterion(description="the delivered package selects and builds the window of a third minted epoch exactly.")
def package_probe_window_exact(workspace) -> bool:
    return _graded(workspace, _assert_package_probe_window_exact)


@criterion(description="the delivered package replays a third minted epoch exactly.")
def package_probe_replay_exact(workspace) -> bool:
    return _graded(workspace, _assert_package_probe_replay_exact)


@criterion(description="the delivered package publishes a third minted epoch exactly.")
def package_probe_publication_exact(workspace) -> bool:
    return _graded(workspace, _assert_package_probe_publication_exact)


@criterion(description="the window opened at the restored watermark instead of one past it, so the event already folded into the checkpoint was applied a second time.")
def negative_watermark_position_replayed_again(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_watermark_position_replayed_again)


@criterion(description="a compensating event whose target stands behind the restored checkpoint was quarantined as having no target, instead of being resolved against the whole canonical history.")
def negative_compensation_target_sought_in_the_window(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_compensation_target_sought_in_the_window)


@criterion(description="the pending queue was offered a single time instead of once per round up to the round ceiling the board memo carries.")
def negative_pending_queue_offered_once(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_pending_queue_offered_once)


@criterion(description="a compensation came off the balances and the allotments and left the derived counter of the reversed kind where it stood.")
def negative_reversal_left_the_derived_counters(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_reversal_left_the_derived_counters)


@criterion(description="a dependency already folded into the restored checkpoint was reported as missing and its event was quarantined.")
def negative_checkpoint_dependency_called_missing(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_checkpoint_dependency_called_missing)


@criterion(description="the requested end position was replayed, so the range was read as closed at both ends.")
def negative_end_boundary_included(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_end_boundary_included)


@criterion(description="two compensating events named one target and both took effect, so the target came off the state twice.")
def negative_target_reversed_twice(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_target_reversed_twice)


@criterion(description="the carry quantum was taken from a constant in place of the per class quantum on the live workbook sheet.")
def negative_carry_quantum_defaulted(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_carry_quantum_defaulted)


@criterion(description="the pending queue was offered in canonical order in place of the five level ladder the directive puts in force.")
def negative_queue_offered_in_canonical_order(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_queue_offered_in_canonical_order)


@criterion(description="the delivered archive carries a module or a startup hook whose name would shadow a standard library module or a site hook once the archive is placed on the import path, which is how a submission reaches for the machinery that grades it.")
def negative_rebinds_verifier_dependencies(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_rebinds_verifier_dependencies)


@criterion(description="the shipped documents are right while the delivered package produces no usable output at all on any minted epoch, so there is no engine behind the delivery.")
def negative_hardcoded_sample_answers(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_hardcoded_sample_answers)


@criterion(description="the package writes one constant record whatever epoch it is pointed at, and that constant is not the shipped epoch.")
def negative_package_ignores_its_input(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_package_ignores_its_input)


@criterion(description="two runs of the package over one corpus, at one identical path, disagree, so the delivered figures are not reproducible.")
def negative_nondeterministic_output(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_nondeterministic_output)


@criterion(description="the package is reproducible at one path and still writes something else when the same epoch is presented under a different directory name.")
def negative_filename_dependent_behaviour(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_filename_dependent_behaviour)


@criterion(description="the package reached for a corpus sitting beside its working directory in place of the one its data option named.")
def negative_reads_training_corpus_at_runtime(workspace) -> bool:
    return _graded(workspace, _assert_negative_weight_reads_training_corpus_at_runtime)


criteria.delivered_documents_present_and_parse(weight=1)
criteria.delivered_package_shape(weight=1)
criteria.shipped_settled_documents_exact(weight=1)
criteria.shipped_canonical_order_exact(weight=3)
criteria.shipped_parameter_layer_exact(weight=3)
criteria.shipped_boundary_record_exact(weight=3)
criteria.shipped_closure_record_exact(weight=3)
criteria.shipped_rounds_record_exact(weight=3)
criteria.shipped_reversal_record_exact(weight=3)
criteria.shipped_settlement_record_exact(weight=3)
criteria.package_eval_preparation_exact(weight=5)
criteria.package_eval_window_exact(weight=5)
criteria.package_eval_replay_exact(weight=5)
criteria.package_eval_publication_exact(weight=5)
criteria.package_challenge_window_exact(weight=5)
criteria.package_challenge_replay_exact(weight=5)
criteria.package_challenge_publication_exact(weight=5)
criteria.package_probe_window_exact(weight=5)
criteria.package_probe_replay_exact(weight=5)
criteria.package_probe_publication_exact(weight=5)
criteria.negative_watermark_position_replayed_again(weight=-5)
criteria.negative_compensation_target_sought_in_the_window(weight=-5)
criteria.negative_pending_queue_offered_once(weight=-5)
criteria.negative_reversal_left_the_derived_counters(weight=-5)
criteria.negative_checkpoint_dependency_called_missing(weight=-3)
criteria.negative_end_boundary_included(weight=-3)
criteria.negative_target_reversed_twice(weight=-3)
criteria.negative_carry_quantum_defaulted(weight=-3)
criteria.negative_queue_offered_in_canonical_order(weight=-3)
criteria.negative_rebinds_verifier_dependencies(weight=-3)
criteria.negative_hardcoded_sample_answers(weight=-3)
criteria.negative_package_ignores_its_input(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)


def _write_corpus(dest):
    """Rebuild the shipped corpus in place.

        python3 tests/test_output.py environment

    writes the SAMPLE_SEED epoch into environment/data and comes out byte
    identical every time it is run.
    """
    return write_corpus(dest, SAMPLE_SEED)


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))
