#!/usr/bin/env python3
"""PES-3 review engine: builds the Q3 2026 release review artifacts.

Usage: python3 evalctl.py ESTATE_DIR OUT_DIR
"""
from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from fractions import Fraction

# ---------------------------------------------------------------- constants

CUTOFF = datetime(2026, 11, 12, 18, 0, 0, tzinfo=timezone.utc)
WIN_START = datetime(2026, 9, 14, 0, 0, 0, tzinfo=timezone.utc)
WIN_END = datetime(2026, 11, 9, 0, 0, 0, tzinfo=timezone.utc)

CLASSES = ["pedestrian", "cyclist", "wheelchair_user", "stroller", "dog", "car",
           "truck", "bus", "motorcycle", "parked_bicycle", "traffic_cone", "bollard"]
PROTECTED = ["pedestrian", "cyclist", "wheelchair_user", "stroller"]
REASONS = ["WITHDRAWN", "OUT_OF_WINDOW", "CORRUPT", "PRIVACY_HOLD", "BOARD_OVERRIDE",
           "LEAK_EXACT", "LEAK_NEAR", "LEAK_SEQUENCE", "UNLABELED"]

SYN = {
    "frame": "image_id", "camera": "camera_id", "local_time": "captured_local",
    "fold": "dst_fold", "width_px": "stored_width", "height_px": "stored_height",
    "sequence": "sequence_id", "frame_no": "frame_index", "hash": "dhash_u64",
    "ann_id": "annotation_id", "annotation": "annotation_id", "decided": "decided_at",
    "category": "label", "rev": "revision", "img": "image_id", "proj": "project",
    "det": "det_id", "cls": "class_index", "request": "request_id",
    "item": "item_id", "box": "box_id",
}

# ---------------------------------------------------------------- text / numbers


def read_lines(path):
    """Decode a text delivery line by line (UTF-8 else Latin-1); drop a leading BOM."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    out = []
    for raw in data.split(b"\n"):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        try:
            out.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(raw.decode("latin-1"))
    if out and out[-1] == "":
        out.pop()
    return out


_NUM_RE = re.compile(r"^[-+]?[0-9]*[.,]?[0-9]+([eE][-+]?[0-9]+)?$")


def parse_num(s):
    """Parse a delivered number into an exact Fraction (section 4 rules)."""
    if s is None:
        return None
    if isinstance(s, (int, Fraction)):
        return Fraction(s)
    if isinstance(s, float):
        return Fraction(repr(s))
    t = str(s).strip()
    if not t:
        return None
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1].strip()
    t = t.replace("%", "").strip()
    if t.startswith("+"):
        t = t[1:]
    if t.startswith("-"):
        neg = not neg
        t = t[1:]
    t = t.replace(" ", "").replace("\u00a0", "")
    nd, nc = t.count("."), t.count(",")
    if nd and nc:
        sep = "." if t.rfind(".") > t.rfind(",") else ","
        other = "," if sep == "." else "."
        t = t.replace(other, "")
        t = t.replace(sep, ".")
    elif nc == 1:
        t = t.replace(",", ".")
    elif nc > 1:
        t = t.replace(",", "")
    elif nd > 1:
        t = t.replace(".", "")
    if t == "" or t == ".":
        return None
    try:
        v = Fraction(t)
    except (ValueError, ZeroDivisionError):
        return None
    return -v if neg else v


def frac_from_cell(v):
    """A workbook/parquet value read exactly; floats to the nearest 0.01 happen elsewhere."""
    if v is None:
        return None
    if isinstance(v, bool):
        return Fraction(int(v))
    if isinstance(v, int):
        return Fraction(v)
    if isinstance(v, float):
        return Fraction(repr(v))
    return parse_num(v)


def to_cent(v):
    """Model coordinate: read to the nearest 0.01 px."""
    if v is None:
        return None
    if isinstance(v, float):
        f = Fraction(repr(v))
    else:
        f = parse_num(v)
        if f is None:
            return None
    return Fraction(round_half_even(f * 100), 100)


def round_half_even(f):
    """Round an exact Fraction to the nearest integer, halves to even."""
    n = f.numerator
    d = f.denominator
    q, r = divmod(n, d)
    twice = 2 * r
    if twice > d or (twice == d and q % 2 == 1):
        q += 1
    return q


def round6(f):
    """Format an exact value with six decimals, half to even."""
    if f is None:
        return "NA"
    scaled = round_half_even(Fraction(f) * 1000000)
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    whole, frac = divmod(scaled, 1000000)
    return "%s%d.%06d" % (sign, whole, frac)


def dec6(f):
    """The exact value of f rounded to six decimals, as a Fraction."""
    if f is None:
        return None
    return Fraction(round_half_even(Fraction(f) * 1000000), 1000000)


# ---------------------------------------------------------------- timestamps

_TS_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:[.,](\d+))?)?"
    r"\s*(Z|z|[+-]\d{2}:?\d{2})?$")


def parse_instant(s):
    """Parse a timestamp carrying an offset or Z into an aware UTC datetime."""
    if s is None:
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    t = str(s).strip()
    if not t:
        return None
    m = _TS_RE.match(t)
    if not m:
        m2 = re.match(r"^(\d{8})T(\d{6})(Z?)$", t)
        if m2:
            d, tm = m2.group(1), m2.group(2)
            return datetime(int(d[:4]), int(d[4:6]), int(d[6:8]), int(tm[:2]),
                            int(tm[2:4]), int(tm[4:6]), tzinfo=timezone.utc)
        return None
    y, mo, da, hh, mi = (int(m.group(i)) for i in range(1, 6))
    ss = int(m.group(6) or 0)
    frac = m.group(7)
    micro = 0
    if frac:
        micro = int((frac + "000000")[:6])
    off = m.group(8)
    dt = datetime(y, mo, da, hh, mi, ss, micro)
    if off in (None, "", "Z", "z"):
        return dt.replace(tzinfo=timezone.utc)
    sign = 1 if off[0] == "+" else -1
    off = off[1:].replace(":", "")
    delta = timedelta(hours=int(off[:2]), minutes=int(off[2:4]))
    return (dt - sign * delta).replace(tzinfo=timezone.utc)


def parse_local(s):
    """Parse a wall-clock timestamp without offset into a naive datetime."""
    if s is None:
        return None
    if isinstance(s, datetime):
        return s.replace(tzinfo=None)
    t = str(s).strip()
    m = _TS_RE.match(t)
    if not m:
        return None
    y, mo, da, hh, mi = (int(m.group(i)) for i in range(1, 6))
    ss = int(m.group(6) or 0)
    return datetime(y, mo, da, hh, mi, ss)


_XL_EPOCH = datetime(1899, 12, 30)


def excel_instant(v):
    """Workbook date cell: Excel 1900-system serial (UTC) or an ISO text instant."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v
    if isinstance(v, (int, float)) or (isinstance(v, str) and _NUM_RE.match(v.strip() or "x")):
        f = parse_num(v)
        if f is None:
            return None
        if f < 61:
            base = datetime(1899, 12, 31)
            days = f
        else:
            base = _XL_EPOCH
            days = f
        whole = int(days)
        secs = round_half_even((Fraction(days) - whole) * 86400)
        return (base + timedelta(days=whole, seconds=secs)).replace(tzinfo=timezone.utc)
    return parse_instant(v)


def iso_z(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_offset(s):
    m = re.match(r"^([+-])(\d{2}):?(\d{2})$", str(s).strip())
    if not m:
        return None
    sign = 1 if m.group(1) == "+" else -1
    return sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))


# ---------------------------------------------------------------- identifiers


class Ids:
    """Identifier canonicalisation (section 3)."""

    def __init__(self, homoglyphs, aliases):
        self.homo = homoglyphs
        self.aliases = aliases
        self._cache = {}

    def canon(self, s):
        if s is None:
            return None
        key = s
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        t = unicodedata.normalize("NFKC", str(s)).strip()
        t = "".join(self.homo.get(c, c) for c in t)
        t = t.upper().replace("-", "").replace("_", "")
        m = re.match(r"^IMG(\d+)$", t)
        if m:
            t = "IMG" + m.group(1).zfill(7)
        self._cache[key] = t
        return t

    def image(self, s):
        """Canonical image id, resolving legacy aliases; None when unknown."""
        t = self.canon(s)
        if t is None or t == "":
            return None
        if t.startswith("IMG") and re.match(r"^IMG\d{7,}$", t):
            return t
        seen = set()
        cur = t
        while cur.startswith("LGC") and cur not in seen:
            seen.add(cur)
            nxt = self.aliases.get(cur)
            if nxt is None:
                return None
            cur = nxt
            if cur.startswith("IMG"):
                return cur
        return None


def canon_camera(s):
    if s is None:
        return None
    t = unicodedata.normalize("NFKC", str(s)).strip().upper()
    t = t.replace(" ", "-").replace("_", "-")
    return t


def canon_seq(s):
    if s is None:
        return None
    t = unicodedata.normalize("NFKC", str(s)).strip().upper()
    m = re.search(r"(\d+)", t)
    if not m:
        return None
    return "SEQ-" + m.group(1).zfill(5)


def canon_ann(s, vendor=None):
    if s is None:
        return None
    t = unicodedata.normalize("NFKC", str(s)).strip().upper()
    if t.startswith("OB:"):
        return "OB-" + t[3:].strip().zfill(7)
    if vendor == "KS" and re.match(r"^\d+$", t):
        return "KS-" + t.zfill(7)
    if vendor == "OB" and re.match(r"^\d+$", t):
        return "OB-" + t.zfill(7)
    return t


def det_number(s):
    if s is None:
        return None
    t = str(s).strip().upper()
    m = re.search(r"(\d+)", t)
    if not m:
        return None
    return int(m.group(1))


# ---------------------------------------------------------------- delimited files


def _canon_cols(row, extra=None):
    out = []
    for c in row:
        k = str(c).strip().lower()
        if extra and k in extra:
            k = extra[k]
        elif k in SYN:
            k = SYN[k]
        out.append(k)
    return out


def delim_rows(path, delim=",", extra_syn=None, lines=None):
    """Yield dict rows of a CSV/TSV delivery, honouring repeated/reordered headers."""
    if lines is None:
        lines = read_lines(path)
    body = [l for l in lines if not l.startswith("#")]
    header = None
    hset = None
    for row in csv.reader(body, delimiter=delim):
        if not row or all(c == "" for c in row):
            continue
        cols = _canon_cols(row, extra_syn)
        if header is None:
            header = cols
            hset = frozenset(cols)
            continue
        if frozenset(cols) == hset and len(cols) == len(header):
            header = cols
            continue
        vals = row
        if len(vals) == len(header) + 1 and vals[-1] == "":
            vals = vals[:-1]
        yield dict(zip(header, vals))


# ---------------------------------------------------------------- registers


class Register:
    """A document register: rows (list of dicts) plus the raw errata lines."""

    def __init__(self, rows, errata):
        self.rows = rows
        self.errata = errata


def docx_register(path):
    """Read the appendix table and errata paragraphs of a .docx policy document."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = docx.Document(path)
    tables = []
    paras = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            t = Paragraph(child, doc).text.strip()
            if t:
                paras.append(("p", t, len(tables)))
        elif tag == "tbl":
            tables.append(Table(child, doc))
    # the appendix table is the one introduced by a paragraph starting "Appendix"
    idx = None
    for kind, text, ntab in paras:
        if text.lower().startswith("appendix") and ntab < len(tables):
            idx = ntab
    if idx is None:
        idx = len(tables) - 1
    rows = []
    tb = tables[idx]
    header = None
    for r in tb.rows:
        cells = [c.text.strip() for c in r.cells]
        if header is None:
            header = [c.strip().lower() for c in cells]
            continue
        rows.append(dict(zip(header, cells)))
    errata = []
    seen_err = False
    for kind, text, ntab in paras:
        if text.lower().startswith("errata to the register"):
            seen_err = True
            continue
        if seen_err:
            errata.append(text)
    extra = {i: [] for i in range(len(tables))}
    for i, tb2 in enumerate(tables):
        if i == idx:
            continue
        hdr = None
        for r in tb2.rows:
            cells = [c.text.strip() for c in r.cells]
            if hdr is None:
                hdr = [c.strip().lower() for c in cells]
                continue
            extra[i].append(dict(zip(hdr, cells)))
    reg = Register(rows, errata)
    reg.other_tables = [extra[i] for i in range(len(tables)) if i != idx]
    return reg


def pdf_register(path):
    """Read the APPENDIX REGISTER rows and ERRATA lines of a PDF register."""
    from pypdf import PdfReader
    reader = PdfReader(path)
    lines = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        for l in txt.split("\n"):
            l = l.strip()
            if l:
                lines.append(l)
    rows = []
    errata = []
    header = None
    state = 0
    for l in lines:
        up = l.upper()
        if up.startswith("APPENDIX REGISTER"):
            state = 1
            header = None
            continue
        if up.startswith("ERRATA TO THE REGISTER"):
            state = 2
            continue
        if state == 1:
            if "|" not in l:
                continue
            parts = [p.strip() for p in l.split("|")]
            if header is None:
                header = [p.lower() for p in parts]
                continue
            if [p.lower() for p in parts] == header:
                continue
            if len(parts) != len(header):
                continue
            rows.append(dict(zip(header, parts)))
        elif state == 2:
            errata.append(l)
    return Register(rows, errata)


def md_register(path, lines=None):
    """Read a Markdown appendix table (voids marked ~~...~~) and its errata."""
    if lines is None:
        lines = read_lines(path)
    rows = []
    errata = []
    header = None
    state = 0
    for l in lines:
        s = l.strip()
        low = s.lower()
        if low.startswith("## appendix"):
            state = 1
            header = None
            continue
        if low.startswith("## errata to the register"):
            state = 2
            continue
        if low.startswith("## ") and state == 1:
            state = 0
            continue
        if state == 1:
            if not s.startswith("|"):
                continue
            parts = [p.strip() for p in s.strip("|").split("|")]
            if header is None:
                header = [p.lower() for p in parts]
                continue
            if all(set(p) <= set("-: ") for p in parts):
                continue
            row = {}
            void = False
            vals = []
            for p in parts:
                if p.startswith("~~") and p.endswith("~~"):
                    void = True
                    p = p[2:-2].strip()
                vals.append(p)
            row = dict(zip(header, vals))
            row["__void__"] = void
            rows.append(row)
        elif state == 2:
            if s:
                errata.append(s)
    return Register(rows, errata)


_TAG_RE = re.compile(r"<[^>]+>")


def html_tables(path):
    """Return (list of tables as row lists, errata strings) of an HTML register."""
    text = "\n".join(read_lines(path))
    tables = []
    for tm in re.finditer(r"<table[^>]*>(.*?)</table>", text, re.S):
        body = tm.group(1)
        rows = []
        for rm in re.finditer(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            cells = [unescape_html(_TAG_RE.sub("", c)).strip()
                     for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rm.group(1), re.S)]
            rows.append(cells)
        tables.append(rows)
    errata = []
    em = re.search(r"errata to the register</h2>(.*?)(?:</body>|$)", text, re.S | re.I)
    if em:
        for li in re.findall(r"<li[^>]*>(.*?)</li>", em.group(1), re.S):
            errata.append(unescape_html(_TAG_RE.sub("", li)).strip())
    return tables, errata


def unescape_html(s):
    import html
    return html.unescape(s)


def table_dicts(rows):
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0]]
    out = []
    for r in rows[1:]:
        if len(r) != len(header):
            continue
        out.append(dict(zip(header, r)))
    return out


# ---------------------------------------------------------------- workbooks


def sheet_rows(path):
    """Yield (sheet, dict row) for every data row of a workbook."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        header = None
        hset = None
        for raw in ws.iter_rows(values_only=True):
            if raw is None:
                continue
            vals = list(raw)
            while vals and vals[-1] is None:
                vals.pop()
            if not vals:
                continue
            if all(isinstance(v, str) or v is None for v in vals):
                cols = _canon_cols([("" if v is None else v) for v in vals])
                if header is None:
                    header = cols
                    hset = frozenset(cols)
                    continue
                if frozenset(cols) == hset and len(cols) == len(header):
                    header = cols
                    continue
            if header is None:
                continue
            yield ws.title, dict(zip(header, vals))
    wb.close()


# ---------------------------------------------------------------- misc readers


def parquet_rows(path):
    import pyarrow.parquet as pq
    return pq.read_table(path).to_pylist()


def xml_records(path, tags=("event", "object", "det")):
    from lxml import etree
    root = etree.parse(path).getroot()
    out = []
    for el in root.iter():
        if etree.QName(el).localname in tags:
            out.append(el)
    return out


def mbox_messages(path):
    """Split an mbox into messages (From_ lines start a message)."""
    lines = read_lines(path)
    msgs = []
    cur = None
    for l in lines:
        if l.startswith("From ") and (cur is None or cur and cur[-1] == ""):
            if cur is not None:
                msgs.append(cur)
            cur = [l]
        elif cur is not None:
            cur.append(l)
    if cur is not None:
        msgs.append(cur)
    return msgs


def ics_events(path):
    """Yield dicts of VEVENT properties (unfolded)."""
    lines = read_lines(path)
    unfolded = []
    for l in lines:
        if l[:1] in (" ", "\t") and unfolded:
            unfolded[-1] += l[1:]
        else:
            unfolded.append(l)
    out = []
    cur = None
    for l in unfolded:
        if l.strip() == "BEGIN:VEVENT":
            cur = {}
        elif l.strip() == "END:VEVENT":
            if cur is not None:
                out.append(cur)
            cur = None
        elif cur is not None and ":" in l:
            k, v = l.split(":", 1)
            cur[k.split(";")[0].strip().upper()] = v.strip()
    return out


def yaml_load(path):
    import yaml
    with open(path, "rb") as fh:
        return yaml.safe_load(fh)


def toml_load(path):
    import tomli
    with open(path, "rb") as fh:
        return tomli.load(fh)


def ini_sections(path):
    """Return an ordered list of (section, [(key, value), ...])."""
    out = []
    cur = None
    for l in read_lines(path):
        s = l.strip()
        if not s or s.startswith(";") or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = (s[1:-1].strip(), [])
            out.append(cur)
            continue
        if cur is not None and "=" in s:
            k, v = s.split("=", 1)
            cur[1].append((k.strip(), v.strip()))
    return out


def sqlite_tables(path):
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    con.row_factory = sqlite3.Row
    names = [r[0] for r in con.execute(
        "select name from sqlite_master where type='table' order by name")]
    return con, names


# ---------------------------------------------------------------- record counts


YAML_LIST_KEY = {"camera_deployment_roster.yaml": "roster",
                 "camera_deployment_roster_ops.yaml": "roster",
                 "ob_label_aliases.yaml": "aliases"}
EXTRA_SYN = {"train_hash_index_b.csv": {"status": "state"}}


def count_records(name, path):
    """The records actually present in a delivery (section 15)."""
    ext = name.rsplit(".", 1)[-1].lower()
    if name.startswith("preprocess_") and ext == "log":
        return len([l for l in read_lines(path) if l.strip() != ""])
    if ext in ("csv", "tsv"):
        delim = "\t" if ext == "tsv" else ","
        return sum(1 for _ in delim_rows(path, delim, EXTRA_SYN.get(name)))
    if ext == "txt":
        return len([l for l in read_lines(path)
                    if l.strip() != "" and not l.lstrip().startswith("#")])
    if ext == "jsonl":
        return len([l for l in read_lines(path) if l.strip() != ""])
    if ext == "json":
        with open(path, "rb") as fh:
            obj = json.load(fh)
        if isinstance(obj, list):
            return len(obj)
        for key in ("records", "waivers", "statuses"):
            if isinstance(obj.get(key), list):
                return len(obj[key])
        for v in obj.values():
            if isinstance(v, list):
                return len(v)
        return 0
    if ext == "xml":
        return len(xml_records(path))
    if ext == "xlsx":
        return sum(1 for _ in sheet_rows(path))
    if ext == "parquet":
        import pyarrow.parquet as pq
        return pq.ParquetFile(path).metadata.num_rows
    if ext == "db":
        con, names = sqlite_tables(path)
        total = 0
        for t in names:
            if t in ("preprocess", "meta"):
                continue
            total += con.execute('select count(*) from "%s"' % t).fetchone()[0]
        con.close()
        return total
    if ext == "mbox":
        return len(mbox_messages(path))
    if ext == "ics":
        return len(ics_events(path))
    if ext in ("yaml", "yml"):
        obj = yaml_load(path)
        key = YAML_LIST_KEY.get(name)
        if key and isinstance(obj, dict):
            return len(obj.get(key) or [])
        if isinstance(obj, list):
            return len(obj)
        if isinstance(obj, dict):
            best = 0
            for v in obj.values():
                if isinstance(v, list):
                    best = max(best, len(v))
                elif isinstance(v, dict):
                    for w in v.values():
                        if isinstance(w, list):
                            best = max(best, len(w))
            return best
        return 0
    if ext == "toml":
        obj = toml_load(path)
        total = 0
        for v in obj.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                total += len(v)
        return total
    if ext == "ini":
        total = 0
        for sec, items in ini_sections(path):
            if sec.lower() in ("homoglyphs", "meta"):
                continue
            total += len(items)
        return total
    if ext == "docx":
        return len(docx_register(path).rows)
    if ext == "pdf":
        return len(pdf_register(path).rows)
    if ext == "md":
        return len(md_register(path).rows)
    if ext == "html":
        tables, _ = html_tables(path)
        reg = tables[-1] if tables else []
        return max(0, len(reg) - 1)
    return 0


def docx_paragraphs(path):
    """All paragraph text of a .docx, newline separated."""
    import docx
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def clip_box(x1, y1, x2, y2, width, height):
    """Round half to even, clip, and drop boxes with no area (section 7)."""
    a = round_half_even(Fraction(x1))
    b = round_half_even(Fraction(y1))
    c = round_half_even(Fraction(x2))
    d = round_half_even(Fraction(y2))
    w = int(width)
    h = int(height)
    a = 0 if a < 0 else (w if a > w else a)
    c = 0 if c < 0 else (w if c > w else c)
    b = 0 if b < 0 else (h if b > h else b)
    d = 0 if d < 0 else (h if d > h else d)
    if c <= a or d <= b:
        return None
    return (a, b, c, d)


# ================================================================ estate


def _apply_errata(rows, errata, patterns):
    """Apply errata lines to register rows.

    patterns: list of (compiled regex, handler(rows, match)).
    """
    for line in errata:
        for rx, fn in patterns:
            m = rx.search(line)
            if m:
                fn(rows, m)
                break


class Estate:
    def __init__(self, root):
        self.root = root

    def p(self, name):
        return os.path.join(self.root, name)

    # ------------------------------------------------------------ policy text
    def load_policy(self):
        body = []
        for line in read_lines(self.p("eval_standard_v3.md")):
            if line.lower().startswith("## appendix"):
                break
            body.append(line)
        text = "\n".join(body)
        m = re.search(r"freeze cutoff is (\S+?)\.", text)
        self.cutoff = parse_instant(m.group(1)) if m else CUTOFF
        m = re.search(r"half-open interval \[(\S+?),\s*(\S+?)\)", text)
        self.win_start = parse_instant(m.group(1)) if m else WIN_START
        self.win_end = parse_instant(m.group(2)) if m else WIN_END
        m = re.search(r"incumbent is (\S+) \(run (\w+)\)", text)
        self.incumbent_model = m.group(1) if m else "skye-v6.4"
        self.incumbent = m.group(2) if m else "R1"
        m = re.search(r"LEAK_NEAR distance (\d+) to (\d+)", text)
        self.near_lo = int(m.group(1)) if m else 1
        self.near_hi = int(m.group(2)) if m else 4
        m = re.search(r"below (\d+) square pixels", text)
        self.small_area = int(m.group(1)) if m else 64
        m = re.search(r"first reason in this precedence:\s*([^.]+)\.", text)
        order = [r.strip() for r in m.group(1).split(",")] if m else []
        order = [r for r in order if r in REASONS]
        self.reason_order = order or list(REASONS)


    # ------------------------------------------------------------ identifiers
    def load_ids(self):
        homo = {}
        aliases = {}
        for sec, items in ini_sections(self.p("image_id_aliases.ini")):
            low = sec.lower()
            if low == "homoglyphs":
                for k, v in items:
                    code = k.strip()
                    if code.upper().startswith("U+"):
                        homo[chr(int(code[2:], 16))] = v.split(";")[0].strip()
            elif low == "aliases":
                for k, v in items:
                    aliases[k] = v.split(";")[0].strip()
        plain = Ids(homo, {})
        self.ids = Ids(homo, {plain.canon(k): plain.canon(v) for k, v in aliases.items()})

    # ------------------------------------------------------------ freeze
    def load_freeze(self):
        reg = md_register(self.p("eval_standard_v3.md"))
        rows = reg.rows

        def fix(rows, m):
            for r in rows:
                if r["image_id"] == m.group(1):
                    r["image_id"] = m.group(2)
                    break
        _apply_errata(rows, reg.errata, [
            (re.compile(r"Row listing (\S+) is a transcription error; "
                        r"the frozen image is (\S+?)\."), fix)])
        freeze = []
        seen = set()
        for r in rows:
            if r.get("__void__"):
                continue
            img = self.ids.image(r["image_id"])
            if img and img not in seen:
                seen.add(img)
                freeze.append(img)
        freeze = set(freeze)

        draft = md_register(self.p("eval_standard_v3_1_draft.md"))
        drows = draft.rows

        def dfix(rows, m):
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(rows):
                rows[idx]["action"] = m.group(3)
        _apply_errata(drows, draft.errata, [
            (re.compile(r"Row (\d+) \((\S+?)\): action is (\S+?)\."), dfix)])
        for r in drows:
            if r.get("__void__"):
                continue
            if str(r.get("status", "")).strip().lower() != "ratified":
                continue
            img = self.ids.image(r.get("image_id"))
            if not img:
                continue
            act = str(r.get("action", "")).strip().lower()
            if act == "add":
                freeze.add(img)
            elif act == "remove":
                freeze.discard(img)
        self.freeze = freeze

    # ------------------------------------------------------------ frames
    def load_frames(self):
        frames = {}
        cams = set()
        for name in ("frames_index_east.csv", "frames_index_west.csv"):
            for r in delim_rows(self.p(name)):
                img = self.ids.image(r.get("image_id"))
                cam = canon_camera(r.get("camera_id"))
                if not img:
                    continue
                cams.add(cam)
                frames[img] = {"camera": cam, "local": r.get("captured_local"),
                               "fold": r.get("dst_fold")}
        v2 = {}
        for r in delim_rows(self.p("frames_index_east_v2.csv")):
            cam = canon_camera(r.get("camera_id"))
            if cam in cams:
                continue
            if not str(r.get("captured_utc") or "").strip():
                continue
            img = self.ids.image(r.get("image_id"))
            if not img:
                continue
            v2[img] = {"camera": cam, "local": r.get("captured_local"),
                       "fold": r.get("dst_fold")}
        for img, rec in v2.items():
            frames.setdefault(img, rec)
        self.frames = frames
        self.candidates = sorted(i for i in self.freeze if i in frames)

    # ------------------------------------------------------------ roster
    def load_roster(self):
        roster = {}
        main_cams = set()
        for e in (yaml_load(self.p("camera_deployment_roster.yaml")) or {}).get("roster") or []:
            cam = canon_camera(e.get("camera"))
            main_cams.add(cam)
            roster[(cam, str(e.get("date")))] = e
        for e in (yaml_load(self.p("camera_deployment_roster_ops.yaml")) or {}).get("roster") or []:
            cam = canon_camera(e.get("camera"))
            if cam in main_cams:
                continue
            if e.get("active") is False:
                continue
            roster[(cam, str(e.get("date")))] = e
        self.roster = roster

    def load_clocks(self):
        skews = {}
        for ev in ics_events(self.p("camera_clock_sync.ics")):
            if (ev.get("STATUS") or "").strip().upper() != "CONFIRMED":
                continue
            summ = ev.get("SUMMARY") or ""
            m = re.search(r"CLOCKSYNC\s+(\S+)", summ)
            if not m:
                continue
            cam = canon_camera(m.group(1))
            start = parse_instant(ev.get("DTSTART"))
            end = parse_instant(ev.get("DTEND"))
            desc = ev.get("DESCRIPTION") or ""
            sk = Fraction(0)
            m2 = re.search(r"skew_ms\s*=\s*([-+]?[\d.,]+)", desc)
            if m2:
                sk = parse_num(m2.group(1)) / 1000
            else:
                m2 = re.search(r"skew_s\s*=\s*([-+]?[\d.,]+)", desc)
                if m2:
                    sk = parse_num(m2.group(1))
            if start is None or end is None:
                continue
            skews.setdefault(cam, []).append((start, end, sk))
        for v in skews.values():
            v.sort(key=lambda t: t[0])
        self.skews = skews

    def capture_instant(self, img):
        """Corrected capture instant, the local date and the site, or None."""
        fr = self.frames.get(img)
        if fr is None:
            return None
        local = parse_local(fr["local"])
        if local is None:
            return None
        cam = fr["camera"]
        date = local.date().isoformat()
        ent = self.roster.get((cam, date))
        if ent is None:
            return None
        off = parse_offset(ent.get("utc_offset"))
        if off is None:
            return None
        site = ent.get("site")
        sw = ent.get("switch_local")
        if sw:
            after = parse_offset(ent.get("offset_after"))
            t = parse_local(date + "T" + str(sw))
            if t is not None and after is not None:
                if local >= t:
                    off = after
                elif after < off:
                    d = off - after
                    if local >= t - d:
                        fold = str(fr.get("fold") or "").strip()
                        if fold == "1":
                            off = after
        inst = (local - off).replace(tzinfo=timezone.utc)
        sk = Fraction(0)
        for start, end, s in self.skews.get(cam, ()):
            if start <= inst < end:
                sk = s
                break
        micro = round_half_even(sk * 1000000)
        corrected = inst - timedelta(microseconds=micro)
        return corrected, date, site

    # ------------------------------------------------------------ geometry
    def load_geometry(self):
        audit = pdf_register(self.p("frame_integrity_audit.pdf"))
        arows = audit.rows

        def afix(rows, m):
            for r in rows:
                if r["image_id"] == m.group(1):
                    r["status"] = m.group(2)
        _apply_errata(arows, audit.errata, [
            (re.compile(r"Line (\S+): status is (\S+)"), afix)])
        self.audit = {}
        for r in arows:
            img = self.ids.image(r["image_id"])
            if img:
                self.audit[img] = r
        geo = {}
        for r in delim_rows(self.p("frame_geometry.tsv"), "\t"):
            img = self.ids.image(r.get("image_id"))
            if not img:
                continue
            w = parse_num(r.get("stored_width"))
            h = parse_num(r.get("stored_height"))
            sc = parse_num(r.get("dim_scale"))
            if sc is None:
                sc = Fraction(1)
            if w is None or h is None:
                continue
            geo[img] = (w * sc, h * sc)
        self.stored = {}
        for img, (w, h) in geo.items():
            au = self.audit.get(img)
            st = (au.get("status") or "").strip().upper() if au else ""
            if w == 0 or h == 0 or st == "REENCODED":
                if au:
                    dw = parse_num(au.get("decoded_w"))
                    dh = parse_num(au.get("decoded_h"))
                    if dw and dh:
                        w, h = dw, dh
            self.stored[img] = (w, h)

    def load_orientation(self):
        exif = {}
        for line in read_lines(self.p("exif_orientation_scan.jsonl")):
            if not line.strip():
                continue
            o = json.loads(line)
            img = self.ids.image(o.get("image"))
            if not img:
                continue
            v = o.get("exif_orientation")
            exif[img] = 1 if v in (0, None) else int(v)
        corr = pdf_register(self.p("orientation_corrections.pdf"))
        crows = corr.rows

        def cfix(rows, m):
            for r in rows:
                if r["correction_id"] == m.group(1):
                    r["orientation"] = m.group(2)
        _apply_errata(crows, corr.errata, [
            (re.compile(r"Correction (\S+): orientation is (\S+?)\."), cfix)])
        best = {}
        for r in crows:
            if (r.get("status") or "").strip().lower() != "confirmed":
                continue
            img = self.ids.image(r.get("image_id"))
            if not img:
                continue
            decided = parse_instant(r.get("decided_at"))
            if decided is None or decided > self.cutoff:
                continue
            key = (decided, str(r.get("correction_id")))
            if img not in best or key > best[img][0]:
                best[img] = (key, int(parse_num(r.get("orientation"))))
        self.orient = {}
        for img in self.stored:
            o = best[img][1] if img in best else exif.get(img, 1)
            self.orient[img] = o
        self.upright = {}
        for img, (w, h) in self.stored.items():
            o = self.orient.get(img, 1)
            self.upright[img] = (h, w) if o in (6, 8) else (w, h)

    def load_sequences(self):
        seqs = {}
        for sheet, r in sheet_rows(self.p("sequence_membership.xlsx")):
            img = self.ids.image(r.get("image_id"))
            if not img:
                continue
            seqs[img] = canon_seq(r.get("sequence_id"))
        self.seq_of = seqs

    # ------------------------------------------------------------ registry
    def load_registry(self):
        tables, errata = html_tables(self.p("inference_run_registry.html"))
        runs = {}
        labelmap = {}
        assign_rows = None
        for rows in tables:
            d = table_dicts(rows)
            if not d:
                continue
            keys = set(d[0])
            if {"run_id", "model", "status"} <= keys:
                for r in d:
                    runs[r["run_id"].strip()] = r
            elif {"run_id", "class_index", "label"} <= keys:
                for r in d:
                    labelmap[(r["run_id"].strip(), int(parse_num(r["class_index"])))] = \
                        r["label"].strip()
            elif {"run_id", "sequence_id", "node"} <= keys:
                assign_rows = d

        def rfix(rows, m):
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(rows):
                rows[idx]["node"] = m.group(4)
        _apply_errata(assign_rows or [], errata, [
            (re.compile(r"Row (\d+) \(run (\S+), sequence (\S+?)\): node is (\S+?)\."), rfix)])
        assign = {}
        for r in assign_rows or []:
            assign[(r["run_id"].strip(), canon_seq(r["sequence_id"]))] = r["node"].strip()
        mtables, merrata = html_tables(self.p("inference_run_registry_mirror.html"))
        mrows = None
        for rows in mtables:
            d = table_dicts(rows)
            if d and {"run_id", "sequence_id", "node"} <= set(d[0]):
                mrows = d
        _apply_errata(mrows or [], merrata, [
            (re.compile(r"Row (\d+) \(run (\S+), sequence (\S+?)\): node is (\S+?)\."), rfix)])
        listed_seqs = {k[1] for k in assign}
        for r in mrows or []:
            seq = canon_seq(r["sequence_id"])
            if seq in listed_seqs:
                continue
            assign[(r["run_id"].strip(), seq)] = r["node"].strip()
        self.runs = runs
        self.labelmap = labelmap
        self.assign = assign
        self.reviewed = sorted(rid for rid, r in runs.items()
                               if (r.get("status") or "").strip().lower() == "review")
        self.model_run = {}
        for rid, r in runs.items():
            self.model_run[(r.get("model") or "").strip()] = rid
        self.run_param = {}
        for rid, r in runs.items():
            self.run_param[rid] = {
                "model": (r.get("model") or "").strip(),
                "threshold": parse_num(r.get("score_threshold")),
                "nms": parse_num(r.get("nms_iou")),
                "maxdet": int(parse_num(r.get("max_detections"))),
                "index": (r.get("training_index") or "").strip(),
                "input": parse_num(r.get("input_size")),
            }

    def run_of(self, tag):
        """The run of a record: a run id or a model name."""
        if tag is None:
            return None
        t = str(tag).strip()
        if t in self.runs:
            return t
        return self.model_run.get(t)

    # ============================================================ annotation

    def load_annotation_meta(self):
        # --- batch receipts
        reg = docx_register(self.p("vendor_batch_receipts.docx"))

        def rfix(rows, m):
            for r in rows:
                if r["batch_id"] == m.group(1):
                    r["received_at"] = m.group(2)
        _apply_errata(reg.rows, reg.errata, [
            (re.compile(r"Batch (\S+): received at (\S+?)\."), rfix)])
        self.batch_ontime = {}
        for r in reg.rows:
            ts = parse_instant(r.get("received_at"))
            self.batch_ontime[r["batch_id"].strip().upper()] = \
                bool(ts is not None and ts <= self.cutoff)

        # --- batch conventions
        conv = docx_register(self.p("annotation_batch_conventions.docx"))

        def cfix(rows, m):
            for r in rows:
                if r["batch_id"] == m.group(1):
                    r["coord_format"] = m.group(2)
                    r["frame"] = m.group(3)
        _apply_errata(conv.rows, conv.errata, [
            (re.compile(r"Batch (\S+) was delivered as (\S+) in the (\S+) frame"), cfix)])
        fmt_syn = {"x,y,w,h": "xywh", "x1,y1,x2,y2": "xyxy",
                   "cx,cy,w,h/norm": "cxcywh_norm", "x1,y1,x2,y2/incl": "xyxy_inclusive",
                   "xywh": "xywh", "xyxy": "xyxy", "cxcywh_norm": "cxcywh_norm",
                   "xyxy_inclusive": "xyxy_inclusive"}
        self.batch_conv = {}
        self.batch_resub = {}
        for r in conv.rows:
            bid = r["batch_id"].strip().upper()
            fmt = fmt_syn.get((r.get("coord_format") or "").strip().lower())
            frame = (r.get("frame") or "").strip().lower()
            if frame not in ("stored", "upright"):
                frame = None
            self.batch_conv[bid] = (fmt, frame)
            self.batch_resub[bid] = (r.get("resubmission_accepted") or "").strip().upper() == "Y"

        # --- vendor assignment
        dap = docx_register(self.p("data_authority_policy.docx"))

        def vfix(rows, m):
            for r in rows:
                if r["image_id"] == m.group(1) and r["assigned_on"].strip() == m.group(2):
                    r["vendor"] = m.group(3)
        _apply_errata(dap.rows, dap.errata, [
            (re.compile(r"Image (\S+) assigned on (\S+): vendor is (\S+?)\."), vfix)])
        best = {}
        for r in dap.rows:
            img = self.ids.image(r.get("image_id"))
            if not img:
                continue
            key = str(r.get("assigned_on") or "").strip()
            if img not in best or key >= best[img][0]:
                best[img] = (key, (r.get("vendor") or "").strip().upper())
        self.vendor_of = {k: v[1] for k, v in best.items()}

        # --- taxonomy
        tax = docx_register(self.p("taxonomy_v3_charter.docx"))

        def tfix(rows, m):
            for r in rows:
                if r["project"] == m.group(1) and r["raw_label"] == m.group(2):
                    r["class"] = m.group(3)
        _apply_errata(tax.rows, tax.errata, [
            (re.compile(r"Project (\S+) label (\S+): class is (\S+?)\."), tfix)])
        self.nl_map = {}
        for r in tax.rows:
            self.nl_map[(r["project"].strip().upper(), r["raw_label"])] = \
                (r["class"].strip(), (r.get("disposition") or "").strip().lower())
        self.v2_map = {}
        for tbl in tax.other_tables:
            for r in tbl:
                if "model_label" in r:
                    self.v2_map[r["model_label"].strip()] = \
                        (r["class"].strip(), (r.get("disposition") or "").strip().lower())
        self.classes = list(CLASSES)
        charter_text = docx_paragraphs(self.p("taxonomy_v3_charter.docx"))
        m = re.search(r"Taxonomy v3 evaluation classes:\s*([^.]+)\.", charter_text)
        if m:
            cls = [c.strip() for c in m.group(1).split(",") if c.strip()]
            if cls:
                self.classes = cls
        self.class_set = set(self.classes)

        # --- kestrel codebook
        cb = pdf_register(self.p("ks_class_codebook.pdf"))

        def kfix(rows, m):
            for r in rows:
                if (r["project"] == m.group(1) and r["code"].strip() == m.group(2)
                        and r["valid_from"].startswith(m.group(3))):
                    r["class"] = m.group(4)
        _apply_errata(cb.rows, cb.errata, [
            (re.compile(r"Project (\S+) code (\S+) from (\S+): class is (\S+?)\."), kfix)])
        self.ks_map = {}
        for r in cb.rows:
            key = (r["project"].strip().upper(), int(parse_num(r["code"])))
            vf = parse_instant(r.get("valid_from"))
            vt = r.get("valid_to", "").strip()
            vt = None if vt in ("-", "") else parse_instant(vt)
            self.ks_map.setdefault(key, []).append(
                (vf, vt, r["class"].strip(), (r.get("disposition") or "").strip().lower()))

        # --- orbis aliases
        self.ob_map = {}
        for e in (yaml_load(self.p("ob_label_aliases.yaml")) or {}).get("aliases") or []:
            disp = e.get("disposition")
            disp = "eval" if disp is None else str(disp).strip().lower()
            if disp in ("~", "none", ""):
                disp = "eval"
            self.ob_map[(str(e.get("project")).strip().upper(), str(e.get("alias")))] = \
                (str(e.get("class")).strip(), disp)

        # --- QA decisions
        tables, errata = html_tables(self.p("labeling_qa_portal.html"))
        text = "\n".join(read_lines(self.p("labeling_qa_portal.html"))[:40])
        m = re.search(r"snapshot\s+(\S+?)\)", text)
        self.qa_snapshot = parse_instant(m.group(1)) if m else parse_instant("2026-10-31T00:00:00Z")
        qrows = table_dicts(tables[-1])

        def qfix(rows, m):
            for r in rows:
                if (r["annotation_id"] == m.group(1) and r["revision"].strip() == m.group(2)
                        and r["decided_at"].strip() == m.group(3)):
                    r["decision"] = m.group(4)
        _apply_errata(qrows, errata, [
            (re.compile(r"Decision on (\S+) revision (\S+) at (\S+) is (\S+?)\."), qfix)])
        decisions = []
        for i, r in enumerate(qrows):
            decisions.append((parse_instant(r["decided_at"]), 0, i,
                              canon_ann(r["annotation_id"]), int(parse_num(r["revision"])),
                              r["decision"].strip().lower()))
        j = 0
        for sheet, r in sheet_rows(self.p("labeling_qa_export.xlsx")):
            j += 1
            if str(r.get("state") or "").strip().lower() != "final":
                continue
            ts = excel_instant(r.get("decided_at"))
            if ts is None or ts <= self.qa_snapshot or ts > self.cutoff:
                continue
            decisions.append((ts, 1, j, canon_ann(r.get("annotation_id")),
                              int(parse_num(r.get("revision"))),
                              str(r.get("decision") or "").strip().lower()))
        decisions.sort(key=lambda t: (t[0], t[1], t[2]))
        latest = {}
        for ts, src, idx, ann, rev, dec in decisions:
            latest[(ann, rev)] = dec
        self.qa_rejected = {k for k, v in latest.items() if v == "rejected"}

        # --- annotation errata
        er = md_register(self.p("annotation_errata_register.md"))

        def efix(rows, m):
            for r in rows:
                if r["errata_id"] == m.group(1):
                    r["value"] = m.group(2)
        _apply_errata(er.rows, er.errata, [
            (re.compile(r"^(\S+): value is (.+?)\.$"), efix)])
        items = []
        for r in er.rows:
            if r.get("__void__"):
                continue
            eff = str(r.get("effective") or "").strip()
            if not eff or eff > self.cutoff.date().isoformat():
                continue
            items.append((eff, str(r.get("errata_id")), canon_ann(r.get("annotation_id")),
                          str(r.get("action") or "").strip().upper(),
                          str(r.get("value") or "").strip()))
        items.sort(key=lambda t: (t[0], t[1]))
        self.ann_errata = items

        # --- relabel campaign
        statuses = {}
        with open(self.p("relabel_campaign_status.json"), "rb") as fh:
            obj = json.load(fh)
        rows = obj.get("statuses") or []
        for i, s in enumerate(rows):
            ts = parse_instant(s.get("at"))
            if ts is None or ts > self.cutoff:
                continue
            item = str(s.get("item") or "").strip().upper()
            key = (ts, i)
            if item not in statuses or key > statuses[item][0]:
                statuses[item] = (key, str(s.get("status") or "").strip().lower())
        approved = {k for k, v in statuses.items() if v[1] == "approved"}
        items_by_img = {}
        item_img = {}
        for sheet, r in sheet_rows(self.p("relabel_campaign_2026q3.xlsx")):
            if "item_id" in r and "image_id" in r:
                iid = str(r.get("item_id") or "").strip().upper()
                img = self.ids.image(r.get("image_id"))
                if not iid or not img:
                    continue
                item_img[iid] = img
                if iid in approved:
                    items_by_img.setdefault(img, []).append(iid)
        boxes = {}
        for sheet, r in sheet_rows(self.p("relabel_campaign_2026q3.xlsx")):
            if "box_id" in r and "item_id" in r:
                iid = str(r.get("item_id") or "").strip().upper()
                if iid not in approved:
                    continue
                boxes.setdefault(iid, []).append(r)
        self.campaign_items = items_by_img
        self.campaign_boxes = boxes

    # ------------------------------------------------------------ vendor records
    def _keep_batch(self, batch, is_resub):
        if not self.batch_ontime.get(batch, False):
            return False
        return self.batch_resub.get(batch, False) == is_resub

    def load_vendor_records(self):
        recs = {}

        def add(img, rec):
            if img is None:
                return
            recs.setdefault(img, []).append(rec)

        # --- Northlake
        nl_files = ["nl_boxes_batch01.csv", "nl_boxes_batch02.csv",
                    "nl_boxes_batch03.tsv", "nl_boxes_batch04.csv"]
        nl_rows = []
        for name in nl_files:
            delim = "\t" if name.endswith(".tsv") else ","
            rows = list(delim_rows(self.p(name), delim))
            if name == "nl_boxes_batch02.csv":
                rows = rows + self._recover_batch02(rows)
            nl_rows.extend(rows)
        for sheet, r in sheet_rows(self.p("nl_boxes_q3_extra.xlsx")):
            nl_rows.append(r)
        for r in nl_rows:
            batch = str(r.get("batch_id") or "").strip().upper()
            if not self._keep_batch(batch, False):
                continue
            img = self.ids.image(r.get("image_id"))
            coords = tuple(parse_num(r.get("coord_%d" % i)) for i in (1, 2, 3, 4))
            if any(c is None for c in coords):
                continue
            crowd = str(r.get("crowd") or "").strip().upper()
            add(img, {
                "vendor": "NL",
                "ann": canon_ann(r.get("annotation_id")),
                "batch": batch,
                "project": str(r.get("project") or "").strip().upper(),
                "label": r.get("label"),
                "coords": coords,
                "kind": None,
                "crowd": crowd == "Y",
                "rev": int(parse_num(r.get("revision")) or 0),
                "deleted": str(r.get("status") or "").strip().lower() == "deleted",
                "ts": None,
            })

        # --- Kestrel
        ks_rows = []
        for name in ("ks_boxes_part1.jsonl", "ks_boxes_part2.jsonl"):
            for line in read_lines(self.p(name)):
                if line.strip():
                    ks_rows.append((json.loads(line), False))
        for name in ("ks_boxes_part3.json", "ks_boxes_part5.json"):
            with open(self.p(name), "rb") as fh:
                for o in (json.load(fh).get("records") or []):
                    ks_rows.append((o, False))
        for r in parquet_rows(self.p("ks_boxes_part4.parquet")):
            ks_rows.append((r, False))
        for r in delim_rows(self.p("ks_boxes_part6.csv")):
            ks_rows.append((r, False))
        with open(self.p("ks_boxes_resubmitted.json"), "rb") as fh:
            for o in (json.load(fh).get("records") or []):
                ks_rows.append((o, True))
        for o, is_resub in ks_rows:
            batch = str(o.get("batch") or o.get("batch_id") or "").strip().upper()
            if not self._keep_batch(batch, is_resub):
                continue
            img = self.ids.image(o.get("image_id") if "image_id" in o else o.get("img"))
            kind = None
            if "bbox" in o and isinstance(o["bbox"], (list, tuple)):
                coords = tuple(parse_num(x) for x in o["bbox"])
            elif "bbox_px" in o and isinstance(o["bbox_px"], (list, tuple)):
                coords = tuple(parse_num(x) for x in o["bbox_px"])
                kind = "px"
            else:
                coords = tuple(parse_num(o.get("b%d" % i)) for i in (1, 2, 3, 4))
                if str(o.get("bbox_unit") or "").strip().lower() == "px":
                    kind = "px"
            if any(c is None for c in coords) or len(coords) != 4:
                continue
            crowd = parse_num(o.get("crowd"))
            ts = parse_num(o.get("ts"))
            add(img, {
                "vendor": "KS",
                "ann": canon_ann(o.get("id"), "KS"),
                "batch": batch,
                "project": str(o.get("project") or o.get("proj") or "").strip().upper(),
                "label": int(parse_num(o.get("code"))) if o.get("code") is not None else None,
                "coords": coords,
                "kind": kind,
                "crowd": crowd == 1,
                "rev": int(parse_num(o.get("revision") if "revision" in o else o.get("rev")) or 0),
                "deleted": str(o.get("state") or "").strip().lower() == "void",
                "ts": ts,
            })

        # --- Orbis
        for name, is_resub in (("ob_boxes_east.xml", False), ("ob_boxes_west.xml", False),
                               ("ob_boxes_resubmitted.xml", True)):
            for el in xml_records(self.p(name), ("object",)):
                batch = str(el.get("batch") or "").strip().upper()
                if not self._keep_batch(batch, is_resub):
                    continue
                img = self.ids.image(el.get("image"))
                bnd = el.find("bndbox")
                if bnd is None:
                    continue
                coords = tuple(parse_num(bnd.get("c%d" % i)) for i in (1, 2, 3, 4))
                if any(c is None for c in coords):
                    continue
                crowd = parse_num(el.findtext("crowd"))
                add(img, {
                    "vendor": "OB",
                    "ann": canon_ann(el.get("id"), "OB"),
                    "batch": batch,
                    "project": str(el.get("project") or "").strip().upper(),
                    "label": el.findtext("name"),
                    "coords": coords,
                    "kind": None,
                    "crowd": crowd == 1,
                    "rev": int(parse_num(el.findtext("revision")) or 0),
                    "deleted": parse_num(el.findtext("deleted")) == 1,
                    "ts": None,
                })
        self.vrecs = recs

    def _recover_batch02(self, delivered):
        """Recover the partitions nl_boxes_batch02.csv is missing (DAP section 3)."""
        man = toml_load(self.p("delivery_manifest.toml")).get("partition") or []
        parts = [p for p in man if p.get("file") == "nl_boxes_batch02.csv"
                 and p.get("status") not in ("superseded", "voided", "withdrawn")]
        parts.sort(key=lambda p: p["part"])
        extra = list(delim_rows(self.p("nl_boxes_batch02_reextract.csv")))
        have = {canon_ann(r.get("annotation_id")) for r in delivered}
        out = []
        for p in parts:
            start = 100 * (p["part"] - 1)
            chunk = extra[start:start + p["records"]]
            if not chunk:
                continue
            present = sum(1 for r in chunk if canon_ann(r.get("annotation_id")) in have)
            if present * 2 <= len(chunk):
                out.extend(chunk)
        return out

    # ------------------------------------------------------------ label mapping
    def map_label(self, rec):
        """(class, disposition) of a vendor record, or None when unknown."""
        v = rec["vendor"]
        if v == "NL":
            hit = self.nl_map.get((rec["project"], str(rec["label"])))
        elif v == "OB":
            hit = self.ob_map.get((rec["project"], str(rec["label"])))
        else:
            rows = self.ks_map.get((rec["project"], rec["label"]))
            hit = None
            if rows:
                ts = rec["ts"]
                inst = None
                if ts is not None:
                    secs = ts / 1000 if ts >= 100000000000 else ts
                    inst = datetime.fromtimestamp(float(secs), timezone.utc)
                for vf, vt, cls, disp in rows:
                    if inst is None:
                        continue
                    if (vf is None or inst >= vf) and (vt is None or inst < vt):
                        hit = (cls, disp)
                        break
        if hit is None:
            return None
        cls, disp = hit
        if disp not in ("eval", "ignore", "drop"):
            disp = "eval"
        return cls, disp

    # ------------------------------------------------------------ boxes
    def to_canonical(self, img, coords, fmt, frame, kind=None):
        W, H = self.stored[img]
        UW, UH = self.upright[img]
        o = self.orient.get(img, 1)
        c1, c2, c3, c4 = coords
        fw, fh = (W, H) if frame == "stored" else (UW, UH)
        if kind == "px":
            cx, cy, w, h = c1, c2, c3, c4
            x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        elif fmt == "cxcywh_norm":
            cx, cy, w, h = c1 * fw, c2 * fh, c3 * fw, c4 * fh
            x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        elif fmt == "xywh":
            x1, y1, x2, y2 = c1, c2, c1 + c3, c2 + c4
        elif fmt == "xyxy_inclusive":
            x1, y1, x2, y2 = c1, c2, c3 + 1, c4 + 1
        else:
            x1, y1, x2, y2 = c1, c2, c3, c4
        if frame == "stored":
            if o == 3:
                x1, y1, x2, y2 = W - x2, H - y2, W - x1, H - y1
            elif o == 6:
                x1, y1, x2, y2 = H - y2, x1, H - y1, x2
            elif o == 8:
                x1, y1, x2, y2 = y1, W - x2, y2, W - x1
        return clip_box(x1, y1, x2, y2, UW, UH)

    def record_format(self, rec):
        fmt, frame = self.batch_conv.get(rec["batch"], (None, None))
        v = rec["vendor"]
        if fmt is None:
            fmt = {"NL": "xywh", "KS": "cxcywh_norm", "OB": "xyxy_inclusive"}[v]
        if frame is None:
            frame = {"NL": "stored", "KS": "upright", "OB": "upright"}[v]
        return fmt, frame

    # ------------------------------------------------------------ ground truth
    def ground_truth(self, img):
        """The ground-truth boxes of an evaluated image: list of dicts."""
        out = []
        items = self.campaign_items.get(img)
        if items:
            for iid in sorted(items):
                for r in self.campaign_boxes.get(iid, ()):
                    cls = str(r.get("class") or "").strip()
                    if cls not in self.class_set:
                        continue
                    coords = [frac_from_cell(r.get(k)) for k in ("x1", "y1", "x2", "y2")]
                    if any(c is None for c in coords):
                        continue
                    box = clip_box(*coords, *self.upright[img])
                    if box is None:
                        continue
                    crowd = parse_num(r.get("crowd")) == 1
                    area = (box[2] - box[0]) * (box[3] - box[1])
                    ign = crowd or area < self.small_area
                    out.append({"gt_id": str(r.get("box_id") or "").strip(),
                                "class": cls, "box": box, "ignore": ign,
                                "source": "CAMPAIGN"})
            return out
        vendor = self.vendor_of.get(img)
        byann = {}
        for rec in self.vrecs.get(img, ()):
            if rec["vendor"] != vendor:
                continue
            byann.setdefault(rec["ann"], {})[rec["rev"]] = rec
        chosen = {}
        for ann, revs in byann.items():
            avail = [rv for rv in revs if (ann, rv) not in self.qa_rejected]
            if not avail:
                continue
            rec = revs[max(avail)]
            if rec["deleted"]:
                continue
            chosen[ann] = rec
        state = {}
        for ann, rec in chosen.items():
            hit = self.map_label(rec)
            if hit is None:
                state[ann] = None
                continue
            cls, disp = hit
            state[ann] = {"class": cls, "disp": disp, "rec": rec, "box": None}
        for eff, eid, ann, action, value in self.ann_errata:
            if ann not in state:
                continue
            st = state[ann]
            if action == "VOID":
                del state[ann]
            elif st is None:
                continue
            elif action == "RECLASS":
                st["class"] = value
            elif action == "REBOX":
                vals = [parse_num(x) for x in value.split(",")]
                if len(vals) == 4 and all(v is not None for v in vals):
                    st["box"] = vals
        for ann in sorted(state):
            st = state[ann]
            if st is None:
                continue
            if st["disp"] == "drop" or st["class"] not in self.class_set:
                continue
            rec = st["rec"]
            if st["box"] is not None:
                box = clip_box(*st["box"], *self.upright[img])
            else:
                fmt, frame = self.record_format(rec)
                box = self.to_canonical(img, rec["coords"], fmt, frame, rec["kind"])
            if box is None:
                continue
            area = (box[2] - box[0]) * (box[3] - box[1])
            ign = st["disp"] == "ignore" or rec["crowd"] or area < self.small_area
            out.append({"gt_id": ann, "class": st["class"], "box": box,
                        "ignore": ign, "source": rec["vendor"]})
        return out

    # ============================================================ exclusions

    def load_lifecycle(self):
        evs = []
        for el in xml_records(self.p("image_lifecycle_events.xml"), ("event",)):
            ts = parse_instant(el.get("at"))
            if ts is None or ts > self.cutoff:
                continue
            img = self.ids.image(el.get("image"))
            if not img:
                continue
            evs.append((ts, int(parse_num(el.get("seq")) or 0), str(el.get("id")),
                        str(el.get("type") or "").strip().lower(), img))
        evs.sort(key=lambda t: (t[0], t[1]))
        seen = set()
        state = {}
        for ts, seq, eid, typ, img in evs:
            if eid in seen:
                continue
            seen.add(eid)
            if typ == "withdrawn":
                state[img] = True
            elif typ == "restored":
                state[img] = False
        self.withdrawn = {i for i, v in state.items() if v}

    def load_privacy(self):
        exp = docx_register(self.p("exclusion_policy.docx"))

        def pfix(rows, m):
            for r in rows:
                if r["request_id"] == m.group(1):
                    r["status"] = m.group(2)
        _apply_errata(exp.rows, exp.errata, [
            (re.compile(r"Request (\S+): status is (\S+?)\."), pfix)])
        text = docx_paragraphs(self.p("exclusion_policy.docx"))
        m = re.search(r"register as of (\d{4}-\d{2}-\d{2}(?:T[\d:.]+Z?)?)", text)
        self.priv_asof = parse_instant(m.group(1)) if m else parse_instant("2026-10-15T00:00:00Z")
        held = {}
        for r in exp.rows:
            img = self.ids.image(r.get("image_id"))
            if not img:
                continue
            st = (r.get("status") or "").strip().upper()
            if st == "HOLD":
                held[img] = True
            else:
                held.setdefault(img, False)
        # mailbox
        msgs = []
        for lines in mbox_messages(self.p("privacy_requests.mbox")):
            hdr = {}
            key = None
            for i, l in enumerate(lines[1:], 1):
                if l == "":
                    break
                if l[:1] in (" ", "\t") and key:
                    hdr[key] += " " + l.strip()
                elif ":" in l:
                    key, v = l.split(":", 1)
                    key = key.strip().lower()
                    hdr[key] = v.strip()
            msgs.append(hdr)
        parsed = []
        for i, hdr in enumerate(msgs):
            sender = hdr.get("from", "")
            dom = sender.rsplit("@", 1)[-1].strip().strip(">").lower()
            if dom != "privacy-office.skye.example":
                continue
            ts = parse_email_date(hdr.get("date"))
            if ts is None or ts <= self.priv_asof or ts > self.cutoff:
                continue
            subj = decode_header(hdr.get("subject", ""))
            m = re.match(r"\s*(\w+)\s+(\S+)", subj)
            if not m:
                continue
            action = m.group(1).strip().upper()
            img = self.ids.image(m.group(2))
            if not img:
                continue
            parsed.append((ts, i, action, img))
        parsed.sort(key=lambda t: (t[0], t[1]))
        for ts, i, action, img in parsed:
            if action == "TAKEDOWN":
                held[img] = True
            elif action == "RELEASE":
                held[img] = False
        legal = set()
        for r in delim_rows(self.p("privacy_register_export.tsv"), "\t"):
            if (r.get("status") or "").strip().upper() != "LEGAL-HOLD":
                continue
            img = self.ids.image(r.get("image_id"))
            if img:
                legal.add(img)
        self.privacy_hold = {i for i, v in held.items() if v} | legal

    def load_board(self):
        rows = []
        for name in ("release_governance.docx", "release_governance_v2_signed.docx"):
            reg = docx_register(self.p(name))

            def bfix(rs, m):
                for r in rs:
                    if r["decision_id"] == m.group(1):
                        r["decision"] = m.group(2)
            _apply_errata(reg.rows, reg.errata, [
                (re.compile(r"Decision (\S+): decision is (\S+?)\."), bfix)])
            rows.extend(reg.rows)
        best = {}
        for r in rows:
            img = self.ids.image(r.get("image_id"))
            if not img:
                continue
            day = str(r.get("decided_on") or "").strip()
            if not day or day > self.cutoff.date().isoformat():
                continue
            key = (day, str(r.get("decision_id")))
            if img not in best or key > best[img][0]:
                best[img] = (key, (r.get("decision") or "").strip().upper())
        self.board_exclude = {i for i, v in best.items() if v[1] == "EXCLUDE"}

    def load_governance(self):
        text = docx_paragraphs(self.p("release_governance.docx"))
        m = re.search(r"map_50_95 is at least ([\d.]+) above", text)
        self.promote_map = parse_num(m.group(1)) if m else Fraction(5, 1000)
        m = re.search(r"not more than ([\d.]+) below", text)
        self.promote_drop = parse_num(m.group(1)) if m else Fraction(10, 1000)
        m = re.search(r"Protected classes:\s*([^.]+)\.", text)
        self.protected = [c.strip() for c in m.group(1).split(",")] if m else list(PROTECTED)
        m = re.search(r"Target precision for operating points is ([\d.]+) for protected "
                      r"classes and ([\d.]+) for every other class", text)
        if m:
            self.target_prot = parse_num(m.group(1))
            self.target_other = parse_num(m.group(2))
        else:
            self.target_prot = Fraction(90, 100)
            self.target_other = Fraction(80, 100)

    # ------------------------------------------------------------ leakage
    def load_training_hashes(self):
        idx = {"v7-train": set(), "v6-core": set()}

        def add(tag, h, purged):
            if purged or h is None or h == 0:
                return
            if tag in idx:
                idx[tag].add(h)

        for r in parquet_rows(self.p("train_hash_index_a.parquet")):
            add(str(r.get("set_tag")).strip(), parse_hash(r.get("dhash_hex")),
                str(r.get("status")).strip().lower() == "purged")
        for r in delim_rows(self.p("train_hash_index_b.csv"), ",",
                            EXTRA_SYN["train_hash_index_b.csv"]):
            add(str(r.get("set_tag")).strip(), parse_hash(r.get("dhash_u64")),
                str(r.get("state")).strip().upper() == "P")
        con, names = sqlite_tables(self.p("train_hash_index_c.db"))
        for row in con.execute("select h, purged, set_tag from train_hashes"):
            add(str(row["set_tag"]).strip(), parse_hash(row["h"]), bool(row["purged"]))
        con.close()
        for name in ("train_hash_index_d.txt", "train_hash_index_h.txt"):
            for l in read_lines(self.p(name)):
                if not l.strip() or l.lstrip().startswith("#"):
                    continue
                parts = l.split()
                if len(parts) < 3:
                    continue
                add(parts[1], parse_hash(parts[0]), parts[2].strip().upper() == "P")
        for l in read_lines(self.p("train_hash_index_e.jsonl")):
            if not l.strip():
                continue
            o = json.loads(l)
            h = parse_hash(o.get("h")) if "h" in o else parse_hash(o.get("h_dec"))
            add(str(o.get("tag") or o.get("set_tag")).strip(), h, bool(o.get("purged")))
        for r in parquet_rows(self.p("train_hash_index_f_dedup.parquet")):
            if str(r.get("source_shard")).strip().lower() != "g":
                continue
            add("v7-train", parse_hash(r.get("dhash_hex")), bool(r.get("purged")))
        for l in read_lines(self.p("train_hash_index_legacy.txt")):
            if not l.strip() or l.lstrip().startswith("#"):
                continue
            parts = l.split()
            if len(parts) < 3:
                continue
            if parts[1].strip() != "v6-core":
                continue
            add("v6-core", parse_hash(parts[0]), parts[2].strip().upper() == "P")
        self.train_index = idx
        used = {self.run_param[r]["index"] for r in self.reviewed}
        self.train_used = set()
        for k in used:
            self.train_used |= idx.get(k, set())
        self.train_chunks = [{} for _ in range(4)]
        for h in self.train_used:
            for ci in range(4):
                self.train_chunks[ci].setdefault((h >> (16 * ci)) & 0xFFFF, []).append(h)

    def load_frame_hashes(self):
        out = {}
        for r in parquet_rows(self.p("frame_dhash.parquet")):
            img = self.ids.image(r.get("image_id"))
            if not img:
                continue
            v = r.get("dhash")
            if v is None:
                continue
            h = int(v) & 0xFFFFFFFFFFFFFFFF
            if str(r.get("byte_order") or "").strip().lower() == "be":
                h = int.from_bytes(h.to_bytes(8, "big"), "little")
            out[img] = h
        self.frame_hash = out

    def load_waivers(self):
        with open(self.p("leakage_waivers.json"), "rb") as fh:
            obj = json.load(fh)
        best = {}
        for w in obj.get("waivers") or []:
            img = self.ids.image(w.get("image"))
            h = parse_hash(w.get("train_dhash"))
            if img is None or h is None:
                continue
            decided = parse_instant(w.get("decided_at"))
            if decided is not None and decided > self.cutoff:
                continue
            key = (decided or datetime.min.replace(tzinfo=timezone.utc),
                   str(w.get("waiver_id")))
            cur = best.get((img, h))
            if cur is None or key > cur[0]:
                best[(img, h)] = (key, w)
        waived = set()
        for (img, h), (key, w) in best.items():
            if str(w.get("status") or "").strip().lower() != "granted":
                continue
            exp = w.get("expires_at")
            if exp is None or str(exp).strip() in ("", "null"):
                waived.add((img, h))
            else:
                ts = parse_instant(exp)
                if ts is not None and ts > self.cutoff:
                    waived.add((img, h))
        self.waived = waived

    def leak_of(self, img):
        """LEAK_EXACT, LEAK_NEAR or None for a candidate."""
        h = self.frame_hash.get(img)
        if not h:
            return None
        cands = set()
        for ci in range(4):
            v = (h >> (16 * ci)) & 0xFFFF
            table = self.train_chunks[ci]
            hit = table.get(v)
            if hit:
                cands.update(hit)
            for b in range(16):
                hit = table.get(v ^ (1 << b))
                if hit:
                    cands.update(hit)
        exact = False
        near = False
        for t in cands:
            if (img, t) in self.waived:
                continue
            d = (h ^ t).bit_count()
            if d == 0:
                exact = True
                break
            if self.near_lo <= d <= self.near_hi:
                near = True
        if exact:
            return "LEAK_EXACT"
        if near:
            return "LEAK_NEAR"
        return None

    def load_trained_sequences(self):
        reg = pdf_register(self.p("training_sequence_register.pdf"))

        def sfix(rows, m):
            for r in rows:
                if r["sequence_id"] == m.group(1):
                    r["status"] = m.group(2)
        _apply_errata(reg.rows, reg.errata, [
            (re.compile(r"Sequence (\S+): status is (\S+?)\."), sfix)])
        used = {self.run_param[r]["index"] for r in self.reviewed}
        self.trained_seqs = set()
        for r in reg.rows:
            if (r.get("status") or "").strip().lower() != "trained":
                continue
            if (r.get("training_index") or "").strip() not in used:
                continue
            seq = canon_seq(r.get("sequence_id"))
            if seq:
                self.trained_seqs.add(seq)

    # ------------------------------------------------------------ verdicts
    def _reason_holds(self, reason, img, leak):
        if reason == "WITHDRAWN":
            return img in self.withdrawn
        if reason == "OUT_OF_WINDOW":
            ci = self.capture_instant(img)
            return ci is None or not (self.win_start <= ci[0] < self.win_end)
        if reason == "CORRUPT":
            au = self.audit.get(img)
            return bool(au) and (au.get("status") or "").strip().upper() == "FAIL"
        if reason == "PRIVACY_HOLD":
            return img in self.privacy_hold
        if reason == "BOARD_OVERRIDE":
            return img in self.board_exclude
        if reason in ("LEAK_EXACT", "LEAK_NEAR"):
            return leak == reason
        if reason == "LEAK_SEQUENCE":
            return self.seq_of.get(img) in self.trained_seqs
        if reason == "UNLABELED":
            if self.campaign_items.get(img):
                return False
            vendor = self.vendor_of.get(img)
            return not any(r["vendor"] == vendor for r in self.vrecs.get(img, ()))
        return False

    def exclusion_of(self, img):
        leak = self.leak_of(img)
        for reason in self.reason_order:
            if self._reason_holds(reason, img, leak):
                return reason
        return None


UNIT_FACTOR = {"fraction": Fraction(1), "percent": Fraction(1, 100),
               "pct": Fraction(1, 100), "permille": Fraction(1, 1000),
               "bp": Fraction(1, 10000), "basis points": Fraction(1, 10000)}


class Detections:
    """Loads and reduces the detection records of the reviewed runs."""

    def __init__(self, est):
        self.e = est

    # ------------------------------------------------------------ metadata
    def load_nodes(self):
        tables, _ = html_tables(self.e.p("inference_run_registry.html"))
        info = {}
        for rows in tables:
            d = table_dicts(rows)
            if d and "node" in d[0] and "score unit" in d[0]:
                for r in d:
                    info[r["node"].strip()] = {
                        "box": r.get("box format", "").strip().lower(),
                        "unit": r.get("score unit", "").strip().lower(),
                        "lb": r.get("letterbox source", "").strip(),
                    }
        self.node_info = info

    def load_preprocess(self):
        prep = {}
        for name in sorted(os.listdir(self.e.root)):
            m = re.match(r"^preprocess_(n\d+)\.log$", name)
            if not m:
                continue
            node = m.group(1)
            table = {}
            for line in read_lines(self.e.p(name)):
                rec = parse_prep_line(line)
                if rec is None:
                    continue
                runtag, imgtag, scale, px, py, attempt, ok = rec
                if not ok:
                    continue
                run = self.e.run_of(runtag)
                img = self.e.ids.image(imgtag)
                if run is None or img is None or scale is None:
                    continue
                key = (run, img)
                cur = table.get(key)
                if cur is None or attempt > cur[0]:
                    table[key] = (attempt, scale, px, py)
            prep[node] = table
        self.prep = prep

    def load_routing(self):
        ledger = toml_load(self.e.p("rerun_batches.toml")).get("rerun") or []
        last = {}
        for r in ledger:
            run = str(r.get("run") or "").strip()
            img = self.e.ids.image(r.get("image"))
            if not img:
                continue
            last[(run, img)] = (str(r.get("store") or "").strip(),
                                str(r.get("status") or "").strip().lower())
        self.route = {k: v[0] for k, v in last.items() if v[1] == "completed"}
        reg = pdf_register(self.e.p("node_quarantine_report.pdf"))

        def qfix(rows, m):
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(rows):
                rows[idx]["node"] = m.group(4)
        _apply_errata(reg.rows, reg.errata, [
            (re.compile(r"Row (\d+) \((\S+), run (\S+?)\): node is (\S+?)\."), qfix)])
        self.quarantine = set()
        for r in reg.rows:
            if (r.get("status") or "").strip().lower() != "quarantined":
                continue
            img = self.e.ids.image(r.get("image_id"))
            if not img:
                continue
            self.quarantine.add((str(r.get("run")).strip(), str(r.get("node")).strip(), img))

    def load_calibration(self):
        knots = {}

        def put(run, cls, k, x, y):
            if run is None or x is None or y is None:
                return
            knots.setdefault(run, {}).setdefault(cls, {})[k] = (x, y)

        def yval(d):
            """A knot's y, a fraction; y_pct, y% and unit = pct hold percent."""
            for key in ("y", "y_pct", "y%"):
                if key in d and d[key] is not None:
                    v = parse_num(d[key])
                    if v is None:
                        return None
                    pct = (key != "y" or str(d.get("unit", "")).strip().lower() == "pct"
                           or str(d[key]).strip().endswith("%"))
                    return v / 100 if pct else v
            return None

        for name in sorted(os.listdir(self.e.root)):
            if not name.startswith("calibration"):
                continue
            path = self.e.p(name)
            if name.endswith(".yaml") or name.endswith(".yml"):
                obj = yaml_load(path) or {}
                cal = obj.get("calibration") or obj
                run = self.e.run_of(cal.get("run")) or self.e.run_of(cal.get("model"))
                for kn in cal.get("knots") or []:
                    put(run, str(kn.get("class")).strip(), int(kn.get("k")),
                        parse_num(kn.get("x")), yval(kn))
            elif name.endswith(".toml"):
                obj = toml_load(path)
                run = self.e.run_of(obj.get("run")) or self.e.run_of(obj.get("model"))
                for kn in obj.get("knot") or []:
                    put(run, str(kn.get("class")).strip(), int(kn.get("k")),
                        parse_num(kn.get("x")), yval(kn))
            elif name.endswith(".ini"):
                run = None
                secs = ini_sections(path)
                for sec, items in secs:
                    if sec.lower() == "meta":
                        for k, v in items:
                            if k.strip().lower() == "run":
                                run = self.e.run_of(v.strip())
                            elif k.strip().lower() == "model" and run is None:
                                run = self.e.run_of(v.strip())
                for sec, items in secs:
                    if sec.lower() == "meta":
                        continue
                    for k, v in items:
                        km = re.match(r"^k0*(\d+)$", k.strip())
                        if not km:
                            continue
                        d = {}
                        for part in v.split():
                            if "=" in part:
                                kk, vv = part.split("=", 1)
                                d[kk.strip().lower()] = vv.strip()
                        put(run, sec.strip(), int(km.group(1)),
                            parse_num(d.get("x")), yval(d))
            elif name.endswith(".pdf"):
                reg = pdf_register(path)
                head = pdf_head_text(path)
                m = re.search(r"\(run (\w+)\)", head)
                run = m.group(1) if m else None
                if run is None:
                    m = re.search(r"CALIBRATION CERTIFICATE - (\S+)", head)
                    run = self.e.run_of(m.group(1)) if m else None
                deferred = set()
                m = re.search(r"knots of the class(?:es)?\s+([^.]+?)\s+are deferred", head)
                if m:
                    deferred = {c.strip() for c in m.group(1).replace("\n", " ").split(",")}

                def rfix(rows, mm):
                    idx = int(mm.group(1)) - 1
                    if 0 <= idx < len(rows):
                        rows[idx]["y"] = mm.group(4)
                _apply_errata(reg.rows, reg.errata, [
                    (re.compile(r"Row (\d+) \(class (\S+), knot (\d+)\): y is (\S+?)\."),
                     rfix)])
                is_reissue = "REISSUE" in head.split("\n", 1)[0].upper()
                self._cert = getattr(self, "_cert", {})
                self._cert[("reissue" if is_reissue else "orig", run)] = (reg.rows, deferred)
        # certificates: the original, then the reissue for deferred classes only
        cert = getattr(self, "_cert", {})
        for (kind, run), (rows, deferred) in sorted(cert.items()):
            if kind != "orig":
                continue
            for r in rows:
                put(run, r["class"].strip(), int(parse_num(r["k"])),
                    parse_num(r["x"]), cert_y(r["y"]))
            for (kind2, run2), (rows2, _d) in sorted(cert.items()):
                if kind2 != "reissue" or run2 != run:
                    continue
                for r in rows2:
                    cls = r["class"].strip()
                    if cls not in deferred:
                        continue
                    put(run, cls, int(parse_num(r["k"])), parse_num(r["x"]),
                        cert_y(r["y"]))
        self.calib = {}
        for run, byc in knots.items():
            self.calib[run] = {}
            for cls, kk in byc.items():
                order = sorted(kk)
                xs = [kk[k][0] for k in order]
                ys = [kk[k][1] for k in order]
                self.calib[run][cls] = (xs, ys)

    def calibrate(self, run, cls, s):
        hit = self.calib.get(run, {}).get(cls)
        if hit is None:
            return s
        xs, ys = hit
        lo, hi = 0, len(xs) - 1
        if s < xs[0]:
            return ys[0]
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if xs[mid] <= s:
                lo = mid
            else:
                hi = mid - 1
        i = lo
        if i >= len(xs) - 1:
            return ys[-1]
        x0, x1 = xs[i], xs[i + 1]
        y0, y1 = ys[i], ys[i + 1]
        if x1 == x0:
            return y0
        return y0 + (y1 - y0) * (s - x0) / (x1 - x0)

    # ------------------------------------------------------------ class map
    def class_of(self, run, class_index):
        key = (run, class_index)
        hit = self._clscache.get(key)
        if hit is not None:
            return hit[0]
        lab = self.e.labelmap.get(key)
        cls = None
        if lab is not None:
            if lab in self.e.v2_map:
                c, disp = self.e.v2_map[lab]
                cls = c if disp != "drop" and c in self.e.class_set else None
            elif lab in self.e.class_set:
                cls = lab
        self._clscache[key] = (cls,)
        return cls

    # ------------------------------------------------------------ records
    def plan(self, eval_images):
        """Decide where each (run, image) pair's records come from."""
        need_node = {}
        need_store = {}
        self.pair_lb = {}
        for run in self.e.reviewed:
            for img in eval_images:
                store = self.route.get((run, img))
                if store:
                    need_store.setdefault(store, set()).add((run, img))
                    continue
                seq = self.e.seq_of.get(img)
                node = self.e.assign.get((run, seq))
                if node is None:
                    continue
                if (run, node, img) in self.quarantine:
                    continue
                info = self.node_info.get(node, {})
                lb = info.get("lb", "")
                if lb.endswith(".log"):
                    hit = self.prep.get(node, {}).get((run, img))
                    if hit is None:
                        continue
                    self.pair_lb[(run, img)] = (hit[1], hit[2], hit[3])
                need_node.setdefault(node, set()).add((run, img))
        self.need_node = need_node
        self.need_store = need_store

    def read_node_files(self):
        """Collect the records of every needed (run, image) pair from node dumps."""
        out = {}
        files = []
        for name in sorted(os.listdir(self.e.root)):
            m = re.match(r"^preds_r\d+_(n\d+)\.(csv|tsv|jsonl|xml|parquet|xlsx)$", name)
            if m:
                files.append((m.group(1), name, m.group(2)))
        for node, name, ext in files:
            need = self.need_node.get(node)
            if not need:
                continue
            info = self.node_info.get(node, {})
            default_unit = info.get("unit", "fraction")
            boxfmt = info.get("box", "xyxy")
            per_row_lb = not info.get("lb", "").endswith(".log")
            for rec in read_pred_file(self.e, self.e.p(name), ext, default_unit,
                                      boxfmt, per_row_lb):
                key = (rec[0], rec[1])
                if key not in need:
                    continue
                out.setdefault(key, {}).setdefault(rec[2], rec)
        return out

    def read_stores(self):
        out = {}
        store_files = {"n6": "node6_rerun_store.db", "n6-replica": "node6_ingest_replica.db",
                       "n2-replay": "preds_r3_n2_replay.jsonl"}
        for store, need in self.need_store.items():
            name = store_files.get(store)
            if not name:
                continue
            path = self.e.p(name)
            if not os.path.exists(path):
                continue
            if name.endswith(".db"):
                con, _ = sqlite_tables(path)
                lb = {}
                for row in con.execute(
                        "select run_id, image_id, scale, pad_x, pad_y, status from preprocess"):
                    if str(row["status"]).strip().lower() != "ok":
                        continue
                    run = self.e.run_of(row["run_id"])
                    img = self.e.ids.image(row["image_id"])
                    if run is None or img is None:
                        continue
                    lb[(run, img)] = (parse_num(row["scale"]), parse_num(row["pad_x"]),
                                      parse_num(row["pad_y"]))
                for row in con.execute(
                        "select run_id, image_id, det_id, class_index, cx, cy, w, h, score_bp"
                        " from dets"):
                    run = self.e.run_of(row["run_id"])
                    img = self.e.ids.image(row["image_id"])
                    key = (run, img)
                    if key not in need:
                        continue
                    box = tuple(to_cent(row[k]) for k in ("cx", "cy", "w", "h"))
                    if any(v is None for v in box):
                        continue
                    num = det_number(row["det_id"])
                    score = parse_num(row["score_bp"])
                    par = lb.get(key)
                    if par is None or par[0] is None:
                        continue
                    rec = (run, img, num, int(row["class_index"]), box, score,
                           Fraction(1, 10000), "cxcywh", par)
                    out.setdefault(key, {}).setdefault(num, rec)
                con.close()
            else:
                for line in read_lines(path):
                    if not line.strip():
                        continue
                    o = json.loads(line)
                    run = self.e.run_of(o.get("run"))
                    img = self.e.ids.image(o.get("image"))
                    key = (run, img)
                    if key not in need:
                        continue
                    rec = jsonl_record(self.e, o, "percent", "cxcywh", True)
                    if rec is None:
                        continue
                    out.setdefault(key, {}).setdefault(rec[2], rec)
        return out

    # ------------------------------------------------------------ reduction
    def build(self, eval_images, upright):
        self._clscache = {}
        self.plan(eval_images)
        records = self.read_node_files()
        for key, recs in self.read_stores().items():
            records.setdefault(key, {}).update(recs)
        counts = {r: {"accepted": 0, "after_threshold": 0, "after_nms": 0, "final": 0}
                  for r in self.e.reviewed}
        final = {}
        for (run, img), byid in records.items():
            par = self.e.run_param[run]
            thr = par["threshold"]
            nms = par["nms"]
            maxdet = par["maxdet"]
            UW, UH = upright[img]
            kept = []
            for num in sorted(byid):
                rec = byid[num]
                _run, _img, _num, ci, box, raw, factor, boxfmt, lb = rec
                if raw is None or raw == -1:
                    continue
                cls = self.class_of(run, ci)
                if cls is None:
                    continue
                if lb is None:
                    lb = self.pair_lb.get((run, img))
                    if lb is None:
                        continue
                scale, px, py = lb
                if boxfmt == "cxcywh":
                    cx, cy, w, h = box
                    x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
                else:
                    x1, y1, x2, y2 = box
                x1 = (x1 - px) / scale
                x2 = (x2 - px) / scale
                y1 = (y1 - py) / scale
                y2 = (y2 - py) / scale
                cbox = clip_box(x1, y1, x2, y2, UW, UH)
                if cbox is None:
                    continue
                counts[run]["accepted"] += 1
                score = self.calibrate(run, cls, raw * factor)
                if score < thr:
                    continue
                counts[run]["after_threshold"] += 1
                kept.append((score, num, cls, cbox))
            kept.sort(key=lambda t: (-t[0], t[1]))
            survivors = []
            bycls = {}
            for score, num, cls, cbox in kept:
                prev = bycls.setdefault(cls, [])
                sup = False
                for other in prev:
                    if iou(cbox, other) > nms:
                        sup = True
                        break
                if sup:
                    continue
                prev.append(cbox)
                survivors.append((score, num, cls, cbox))
            counts[run]["after_nms"] += len(survivors)
            survivors.sort(key=lambda t: (-t[0], t[1]))
            survivors = survivors[:maxdet]
            counts[run]["final"] += len(survivors)
            if survivors:
                final[(run, img)] = survivors
        self.counts = counts
        self.final = final
        return final


def cert_y(v):
    """A certificate y value: a fraction, or percent when it carries %."""
    t = str(v).strip()
    f = parse_num(t)
    if f is None:
        return None
    if t.endswith("%"):
        return f / 100
    return f


def pdf_head_text(path):
    from pypdf import PdfReader
    reader = PdfReader(path)
    return reader.pages[0].extract_text() or ""


def iou(a, b):
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        return Fraction(0)
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return Fraction(inter, union)


_PREP_PATTERNS = [
    # generic: PREP|time|run|image|scale|pad_x|pad_y|a/n|status
    re.compile(r"^(?:PREP|n\d+)\|[^|]*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|"
               r"(\d+)/(\d+)\|(\S+)(?:\s.*)?$"),
]


def parse_prep_line(line):
    """(run, image, scale, pad_x, pad_y, attempt, ok) of a preprocess log line."""
    s = line.strip()
    if not s:
        return None
    m = _PREP_PATTERNS[0].match(s)
    if m:
        return (m.group(1).strip(), m.group(2).strip(), parse_num(m.group(3)),
                parse_num(m.group(4)), parse_num(m.group(5)), int(m.group(6)),
                m.group(8).strip().lower() in ("ok", "OK".lower()))
    m = re.search(r"run=(\S+)\s+img=(\S+).*?scale=(\S+)\s+pad=([\d.,-]+),([\d.,-]+)\s+"
                  r"attempt=(\d+)/(\d+)\s+status=(\S+)", s)
    if m:
        return (m.group(1), m.group(2), parse_num(m.group(3)), parse_num(m.group(4)),
                parse_num(m.group(5)), int(m.group(6)), m.group(8).strip().lower() == "ok")
    m = re.search(r'image="([^"]+)"\s+run="([^"]+)"\s+letterbox\(scale=([^,]+),\s*'
                  r'pad_x=([^,]+),\s*pad_y=([^)]+)\)\s+try=(\d+) of (\d+)\s+(\S+)', s)
    if m:
        return (m.group(2), m.group(1), parse_num(m.group(3)), parse_num(m.group(4)),
                parse_num(m.group(5)), int(m.group(6)), m.group(8).strip().upper() == "OK")
    m = re.search(r":\s*(\S+)\s+(\S+)\s+scale\s+(\S+)\s+pads\s+(\S+)\s+(\S+)\s+attempt\s+"
                  r"(\d+)\s+of\s+(\d+)\s*->\s*(\S+)", s)
    if m:
        return (m.group(1), m.group(2), parse_num(m.group(3)), parse_num(m.group(4)),
                parse_num(m.group(5)), int(m.group(6)), m.group(8).strip().lower() == "ok")
    m = re.search(r"run=(\S+)\s+image=(\S+)\s+s=\S+\s*\(([^)]+)\)\s+px=(\S+)\s+py=(\S+)\s+"
                  r"a=(\d+)/(\d+)\s+(\S+)", s)
    if m:
        return (m.group(1), m.group(2), parse_num(m.group(3)), parse_num(m.group(4)),
                parse_num(m.group(5)), int(m.group(6)), m.group(8).strip().upper() == "OK")
    return None


def score_from(d):
    """(raw value, unit factor) of a detection record; factor None when unstated."""
    for key in ("score_pct", "score_permille", "score_bp"):
        if key in d and d[key] is not None:
            unit = key.split("_", 1)[1]
            return parse_num(d[key]), UNIT_FACTOR.get(unit, Fraction(1))
    v = d.get("score")
    if v is None:
        return None, None
    if isinstance(v, str) and v.strip().endswith("%"):
        return parse_num(v), Fraction(1, 100)
    unit = str(d.get("score_unit") or "").strip().lower()
    if unit:
        return parse_num(v), UNIT_FACTOR.get(unit, Fraction(1))
    return parse_num(v), None


def jsonl_record(est, o, default_unit, boxfmt, own_lb):
    run = est.run_of(o.get("run"))
    img = est.ids.image(o.get("image"))
    if run is None or img is None:
        return None
    num = det_number(o.get("det_id") if "det_id" in o else o.get("det"))
    ci = o.get("class_index") if "class_index" in o else o.get("cls")
    if num is None or ci is None:
        return None
    box = o.get("box_cxcywh") or o.get("box")
    if box is None:
        box = [o.get(k) for k in ("x1", "y1", "x2", "y2")]
        fmt = "xyxy"
    else:
        fmt = boxfmt
    cents = tuple(to_cent(v) for v in box)
    if len(cents) != 4 or any(v is None for v in cents):
        return None
    raw, factor = score_from(o)
    if factor is None:
        # a bare score key holds a fraction whatever the node's default unit
        factor = Fraction(1)
    lb = None
    if own_lb:
        d = o.get("letterbox") or {}
        sc = parse_num(d.get("scale"))
        if sc is None:
            return None
        lb = (sc, parse_num(d.get("pad_x")) or Fraction(0),
              parse_num(d.get("pad_y")) or Fraction(0))
    return (run, img, num, int(ci), cents, raw, factor, fmt, lb)


def read_pred_file(est, path, ext, default_unit, boxfmt, per_row_lb):
    """Yield detection records of a node dump."""
    if ext in ("csv", "tsv"):
        delim = "\t" if ext == "tsv" else ","
        for r in delim_rows(path, delim):
            rec = dict_record(est, r, default_unit, boxfmt, per_row_lb)
            if rec:
                yield rec
    elif ext == "jsonl":
        for line in read_lines(path):
            if not line.strip():
                continue
            rec = jsonl_record(est, json.loads(line), default_unit, boxfmt, per_row_lb)
            if rec:
                yield rec
    elif ext == "parquet":
        for r in parquet_rows(path):
            rec = dict_record(est, r, default_unit, boxfmt, per_row_lb)
            if rec:
                yield rec
    elif ext == "xlsx":
        for sheet, r in sheet_rows(path):
            rec = dict_record(est, r, default_unit, boxfmt, per_row_lb)
            if rec:
                yield rec
    elif ext == "xml":
        for el in xml_records(path, ("det",)):
            d = dict(el.attrib)
            box = el.find("box")
            if box is not None:
                d.update(box.attrib)
            sc = el.findtext("score")
            if sc is not None:
                d["score"] = sc
            rec = dict_record(est, d, default_unit, boxfmt, per_row_lb)
            if rec:
                yield rec


def dict_record(est, r, default_unit, boxfmt, per_row_lb):
    d = {}
    for k, v in r.items():
        kk = str(k).strip().lower()
        d[SYN.get(kk, kk)] = v
    run = est.run_of(d.get("run") or d.get("run_tag") or d.get("model"))
    img = est.ids.image(d.get("image_id") or d.get("image"))
    if run is None or img is None:
        return None
    num = det_number(d.get("det_id") or d.get("id"))
    ci = d.get("class_index")
    if num is None or ci is None or str(ci).strip() == "":
        return None
    if boxfmt == "cxcywh" and "cx" in d:
        keys = ("cx", "cy", "w", "h")
        fmt = "cxcywh"
    else:
        keys = ("x1", "y1", "x2", "y2")
        fmt = "xyxy"
    cents = tuple(to_cent(d.get(k)) for k in keys)
    if any(v is None for v in cents):
        return None
    raw, factor = score_from(d)
    if raw is None:
        return None
    if factor is None:
        factor = UNIT_FACTOR.get(default_unit, Fraction(1))
    lb = None
    if per_row_lb:
        sc = parse_num(d.get("lb_scale"))
        if sc is None:
            return None
        lb = (sc, parse_num(d.get("lb_pad_x")) or Fraction(0),
              parse_num(d.get("lb_pad_y")) or Fraction(0))
    return (run, img, num, int(parse_num(ci)), cents, raw, factor, fmt, lb)


IOU_STEPS = [Fraction(k, 100) for k in range(50, 100, 5)]


class Scorer:
    """Matching, average precision and operating points (sections 12 and 13)."""

    def __init__(self, est, gt, final):
        self.e = est
        self.gt = gt            # image -> list of gt dicts
        self.final = final      # (run, image) -> [(score, num, cls, box)]

    def prepare(self, run, images):
        """Per image and class: detections, ground truth and overlap tables."""
        per = {}
        for img in images:
            dets = self.final.get((run, img))
            gts = self.gt.get(img) or ()
            bycls = {}
            for score, num, cls, box in dets or ():
                bycls.setdefault(cls, {"d": [], "g": [], "i": []})["d"].append(
                    (score, num, box))
            for g in gts:
                cls = g["class"]
                slot = bycls.setdefault(cls, {"d": [], "g": [], "i": []})
                if g["ignore"]:
                    slot["i"].append(g["box"])
                else:
                    slot["g"].append((g["gt_id"], g["box"]))
            for cls, slot in bycls.items():
                slot["d"].sort(key=lambda t: (-t[0], t[1]))
                slot["g"].sort(key=lambda t: t[0])
                tbl = []
                ign = []
                for score, num, box in slot["d"]:
                    row = []
                    for gid, gbox in slot["g"]:
                        ix = min(box[2], gbox[2]) - max(box[0], gbox[0])
                        iy = min(box[3], gbox[3]) - max(box[1], gbox[1])
                        if ix <= 0 or iy <= 0:
                            row.append((0, 1))
                            continue
                        inter = ix * iy
                        union = ((box[2] - box[0]) * (box[3] - box[1])
                                 + (gbox[2] - gbox[0]) * (gbox[3] - gbox[1]) - inter)
                        row.append((inter, union))
                    tbl.append(row)
                    area = (box[2] - box[0]) * (box[3] - box[1])
                    best = 0
                    for ibox in slot["i"]:
                        ix = min(box[2], ibox[2]) - max(box[0], ibox[0])
                        iy = min(box[3], ibox[3]) - max(box[1], ibox[1])
                        if ix > 0 and iy > 0:
                            v = ix * iy
                            if v > best:
                                best = v
                    ign.append((best, area))
                slot["iou"] = tbl
                slot["ign"] = ign
                per.setdefault(cls, []).append((img, slot))
        return per

    def score_run(self, run, images):
        per = self.prepare(run, images)
        out = {}
        for cls in self.e.classes:
            entries = per.get(cls, [])
            gt_count = sum(len(s["g"]) for _i, s in entries)
            det_count = sum(len(s["d"]) for _i, s in entries)
            aps = []
            tp50 = fp50 = 0
            op = None
            for t in IOU_STEPS:
                num = t.numerator
                den = t.denominator
                ranked = []
                for img, slot in entries:
                    ngt = len(slot["g"])
                    used = [False] * ngt
                    for di, (score, dnum, box) in enumerate(slot["d"]):
                        row = slot["iou"][di]
                        best = -1
                        bi = -1
                        for gi in range(ngt):
                            if used[gi]:
                                continue
                            inter, union = row[gi]
                            if inter == 0:
                                continue
                            if bi < 0 or inter * bestu > best * union:
                                best, bestu, bi = inter, union, gi
                        hit = False
                        if bi >= 0 and best * den >= num * bestu:
                            used[bi] = True
                            hit = True
                        if hit:
                            ranked.append((score, dnum, 1))
                        else:
                            bign, area = slot["ign"][di]
                            if area and bign * den >= num * area:
                                continue
                            ranked.append((score, dnum, 0))
                ranked.sort(key=lambda r: (-r[0], r[1]))
                ap = average_precision(ranked, gt_count)
                aps.append(ap)
                if t == IOU_STEPS[0]:
                    tp50 = sum(1 for r in ranked if r[2])
                    fp50 = len(ranked) - tp50
                    op = ranked
            res = {
                "gt_count": gt_count, "det_count": det_count,
                "tp_50": tp50, "fp_50": fp50,
                "ap_50": aps[0] if gt_count else None,
                "ap_75": aps[5] if gt_count else None,
                "ap_50_95": (sum(aps) / len(aps)) if gt_count else None,
            }
            res.update(self.operating_point(cls, op, gt_count))
            out[cls] = res
        return out

    def operating_point(self, cls, ranked, gt_count):
        target = self.e.target_prot if cls in self.e.protected else self.e.target_other
        res = {"target_precision": target, "threshold": None,
               "precision": None, "recall": None}
        if not gt_count or not ranked:
            return res
        best = None
        tp = 0
        n = len(ranked)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and ranked[j + 1][0] == ranked[i][0]:
                j += 1
            for k in range(i, j + 1):
                tp += ranked[k][2]
            tau = ranked[i][0]
            total = j + 1
            prec = Fraction(tp, total)
            rec = Fraction(tp, gt_count)
            if prec >= target:
                cand = (rec, tau)
                if best is None or cand > (best[2], best[0]):
                    best = (tau, prec, rec)
            i = j + 1
        if best is not None:
            res["threshold"], res["precision"], res["recall"] = best
        return res


def average_precision(ranked, gt_count):
    """101-point interpolated AP over the precision envelope (section 12)."""
    if not gt_count:
        return None
    n = len(ranked)
    if n == 0:
        return Fraction(0)
    prec = [None] * n
    rec = [None] * n
    tp = 0
    for i, (score, num, hit) in enumerate(ranked):
        tp += hit
        prec[i] = Fraction(tp, i + 1)
        rec[i] = Fraction(tp, gt_count)
    env = [None] * n
    run_max = Fraction(0)
    for i in range(n - 1, -1, -1):
        if prec[i] > run_max:
            run_max = prec[i]
        env[i] = run_max
    total = Fraction(0)
    idx = 0
    for ri in range(101):
        r = Fraction(ri, 100)
        while idx < n and rec[idx] < r:
            idx += 1
        if idx >= n:
            continue
        total += env[idx]
    return total / 101


# ================================================================ output


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(header) + "\n")
        for r in rows:
            fh.write(",".join(r) + "\n")


def write_json(path, obj):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(obj, indent=2, ensure_ascii=False))
        fh.write("\n")


def run_review(estate_dir, out_dir):
    e = Estate(estate_dir)
    e.load_policy()
    e.load_ids()
    e.load_freeze()
    e.load_frames()
    e.load_roster()
    e.load_clocks()
    e.load_geometry()
    e.load_orientation()
    e.load_sequences()
    e.load_registry()
    e.load_governance()
    e.load_annotation_meta()
    e.load_vendor_records()
    e.load_lifecycle()
    e.load_privacy()
    e.load_board()
    e.load_training_hashes()
    e.load_frame_hashes()
    e.load_waivers()
    e.load_trained_sequences()

    exclusions = {}
    evaluated = []
    for img in e.candidates:
        reason = e.exclusion_of(img)
        if reason:
            exclusions[img] = reason
        else:
            evaluated.append(img)
    evaluated.sort()

    gt = {}
    for img in evaluated:
        gt[img] = e.ground_truth(img)

    det = Detections(e)
    det.load_nodes()
    det.load_preprocess()
    det.load_routing()
    det.load_calibration()
    final = det.build(set(evaluated), e.upright)

    scorer = Scorer(e, gt, final)
    metrics = {}
    for run in e.reviewed:
        metrics[run] = scorer.score_run(run, evaluated)

    os.makedirs(out_dir, exist_ok=True)

    # --- eval_images.csv
    rows = []
    for img in evaluated:
        inst, date, site = e.capture_instant(img)
        w, h = e.upright[img]
        boxes = gt[img]
        rows.append([
            img, e.seq_of.get(img) or "", e.frames[img]["camera"], str(site or ""),
            iso_z(inst), str(int(w)), str(int(h)), str(e.orient.get(img, 1)),
            str(sum(1 for b in boxes if not b["ignore"])),
            str(sum(1 for b in boxes if b["ignore"])),
        ])
    write_csv(os.path.join(out_dir, "eval_images.csv"),
              ["image_id", "sequence_id", "camera_id", "site_id", "captured_utc",
               "width", "height", "orientation", "gt_boxes", "ignore_regions"], rows)

    # --- exclusions.csv
    write_csv(os.path.join(out_dir, "exclusions.csv"), ["image_id", "reason"],
              [[img, exclusions[img]] for img in sorted(exclusions)])

    # --- ground_truth.csv
    rows = []
    for img in evaluated:
        for b in sorted(gt[img], key=lambda b: b["gt_id"]):
            x1, y1, x2, y2 = b["box"]
            rows.append([img, b["gt_id"], b["class"], str(x1), str(y1), str(x2), str(y2),
                         "1" if b["ignore"] else "0"])
    write_csv(os.path.join(out_dir, "ground_truth.csv"),
              ["image_id", "gt_id", "class", "x1", "y1", "x2", "y2", "ignore"], rows)

    # --- detections.csv
    rows = []
    for run in e.reviewed:
        for img in evaluated:
            got = final.get((run, img))
            if not got:
                continue
            for score, num, cls, box in sorted(got, key=lambda t: t[1]):
                rows.append([run, img, "D%09d" % num, cls, str(box[0]), str(box[1]),
                             str(box[2]), str(box[3]), round6(score)])
    write_csv(os.path.join(out_dir, "detections.csv"),
              ["run_id", "image_id", "det_id", "class", "x1", "y1", "x2", "y2", "score"],
              rows)

    ordered_classes = sorted(e.classes, key=lambda c: c.encode("utf-8"))

    # --- class_metrics.csv
    rows = []
    for run in e.reviewed:
        for cls in ordered_classes:
            m = metrics[run][cls]
            rows.append([run, cls, str(m["gt_count"]), str(m["det_count"]),
                         str(m["tp_50"]), str(m["fp_50"]), round6(m["ap_50"]),
                         round6(m["ap_75"]), round6(m["ap_50_95"])])
    write_csv(os.path.join(out_dir, "class_metrics.csv"),
              ["run_id", "class", "gt_count", "det_count", "tp_50", "fp_50",
               "ap_50", "ap_75", "ap_50_95"], rows)

    # --- operating_points.csv
    rows = []
    for run in e.reviewed:
        for cls in ordered_classes:
            m = metrics[run][cls]
            rows.append([run, cls, round6(m["target_precision"]), round6(m["threshold"]),
                         round6(m["precision"]), round6(m["recall"])])
    write_csv(os.path.join(out_dir, "operating_points.csv"),
              ["run_id", "class", "target_precision", "threshold", "precision", "recall"],
              rows)

    # --- leaderboard.json
    maps = {}
    for run in e.reviewed:
        vals = {k: [] for k in ("ap_50", "ap_75", "ap_50_95")}
        for cls in e.classes:
            m = metrics[run][cls]
            if m["gt_count"] > 0 and m["ap_50"] is not None:
                for k in vals:
                    vals[k].append(m[k])
        maps[run] = {k: (sum(v) / len(v) if v else None) for k, v in vals.items()}
    inc = e.incumbent
    runs_out = []
    promoted = []
    for run in e.reviewed:
        deltas = {}
        for cls in e.protected:
            a = dec6(metrics[run][cls]["ap_50"])
            b = dec6(metrics[inc][cls]["ap_50"]) if inc in metrics else None
            if run == inc:
                deltas[cls] = round6(Fraction(0)) if a is not None else "NA"
            elif a is None or b is None:
                deltas[cls] = "NA"
            else:
                deltas[cls] = round6(a - b)
        if run == inc:
            decision = "INCUMBENT"
        else:
            ok = True
            rm = dec6(maps[run]["ap_50_95"])
            im = dec6(maps[inc]["ap_50_95"]) if inc in maps else None
            if rm is None or im is None or rm - im < e.promote_map:
                ok = False
            if ok:
                for cls in e.protected:
                    a = dec6(metrics[run][cls]["ap_50"])
                    b = dec6(metrics[inc][cls]["ap_50"])
                    if a is None or b is None:
                        continue
                    if a - b < -e.promote_drop:
                        ok = False
                        break
            decision = "PROMOTE" if ok else "HOLD"
            if ok:
                promoted.append(run)
        runs_out.append({
            "run_id": run,
            "model": e.run_param[run]["model"],
            "map_50": round6(maps[run]["ap_50"]),
            "map_75": round6(maps[run]["ap_75"]),
            "map_50_95": round6(maps[run]["ap_50_95"]),
            "protected_ap_50_delta": deltas,
            "decision": decision,
        })
    candidate = None
    if promoted:
        best = None
        for run in promoted:
            v = dec6(maps[run]["ap_50_95"])
            if best is None or v > best[0] or (v == best[0] and run < best[1]):
                best = (v, run)
        candidate = best[1]
    write_json(os.path.join(out_dir, "leaderboard.json"), {
        "incumbent": inc,
        "release_candidate": candidate,
        "runs": runs_out,
    })

    # --- reconciliation.json
    total_gt = sum(sum(1 for b in gt[i] if not b["ignore"]) for i in evaluated)
    total_ign = sum(sum(1 for b in gt[i] if b["ignore"]) for i in evaluated)
    by_source = {k: 0 for k in ("CAMPAIGN", "KS", "NL", "OB")}
    for i in evaluated:
        for b in gt[i]:
            by_source[b["source"]] = by_source.get(b["source"], 0) + 1
    excluded_counts = {r: 0 for r in e.reason_order}
    for v in exclusions.values():
        excluded_counts[v] = excluded_counts.get(v, 0) + 1
    deliveries = {}
    man = toml_load(e.p("delivery_manifest.toml")).get("partition") or []
    declared = {}
    order = []
    for p in man:
        name = p.get("file")
        if name not in declared:
            declared[name] = 0
            order.append(name)
        if p.get("status") in ("superseded", "voided", "withdrawn"):
            continue
        declared[name] += int(p.get("records") or 0)
    for name in sorted(order):
        path = e.p(name)
        if not os.path.exists(path):
            continue
        deliveries[name] = {"declared": declared[name],
                            "parsed": count_records(name, path)}
    write_json(os.path.join(out_dir, "reconciliation.json"), {
        "freeze_list_ids": len(e.freeze),
        "candidates": len(e.candidates),
        "eval_images": len(evaluated),
        "excluded": excluded_counts,
        "gt_boxes": total_gt,
        "ignore_regions": total_ign,
        "gt_by_source": {k: by_source.get(k, 0) for k in ("CAMPAIGN", "KS", "NL", "OB")},
        "detections": {run: det.counts[run] for run in e.reviewed},
        "deliveries": deliveries,
    })


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: evalctl.py ESTATE_DIR OUT_DIR\n")
        return 2
    run_review(argv[1], argv[2])
    return 0


def parse_hash(v):
    """A 64-bit training hash from hex or decimal text (or an integer)."""
    if v is None:
        return None
    if isinstance(v, int):
        return v & 0xFFFFFFFFFFFFFFFF
    t = str(v).strip()
    if not t:
        return None
    low = t.lower()
    if low.startswith("0x"):
        return int(low[2:], 16) & 0xFFFFFFFFFFFFFFFF
    if low.startswith("x"):
        return int(low[1:], 16) & 0xFFFFFFFFFFFFFFFF
    if re.fullmatch(r"[0-9]+", t):
        return int(t) & 0xFFFFFFFFFFFFFFFF
    if re.fullmatch(r"[0-9a-fA-F]+", t):
        return int(t, 16) & 0xFFFFFFFFFFFFFFFF
    return None


_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def parse_email_date(s):
    """RFC 5322 date header to an aware UTC datetime."""
    if not s:
        return None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+(\d{2}):(\d{2}):(\d{2})"
                  r"\s*([+-]\d{4}|GMT|UTC|Z)?", s)
    if not m:
        return None
    day = int(m.group(1))
    mon = _MONTHS.get(m.group(2).lower())
    if not mon:
        return None
    dt = datetime(int(m.group(3)), mon, day, int(m.group(4)), int(m.group(5)),
                  int(m.group(6)))
    off = m.group(7)
    if off and off[0] in "+-":
        sign = 1 if off[0] == "+" else -1
        dt -= sign * timedelta(hours=int(off[1:3]), minutes=int(off[3:5]))
    return dt.replace(tzinfo=timezone.utc)


def decode_header(s):
    """Decode RFC 2047 encoded-words in a header value."""
    import base64
    import quopri

    def rep(m):
        charset, enc, data = m.group(1), m.group(2).upper(), m.group(3)
        try:
            if enc == "B":
                raw = base64.b64decode(data + "===")
            else:
                raw = quopri.decodestring(data.replace("_", " "))
            return raw.decode(charset, errors="replace")
        except Exception:
            return m.group(0)
    return re.sub(r"=\?([^?]+)\?([BbQq])\?([^?]*)\?=", rep, s or "")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
