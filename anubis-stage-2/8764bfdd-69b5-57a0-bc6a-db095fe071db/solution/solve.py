#!/usr/bin/env python3
"""Oracle: repair estatectl and use it to consolidate /app/data into /app/out.

The repaired tool is the complete implementation of ECS-standard.md written below. It reads only
the export set it is given, so the same program is what the hidden export sets exercise.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

DATA = Path("/app/data")
TOOL = Path("/app/tool")
OUT = Path("/app/out")
REPAIRED = r'''#!/usr/bin/env python3
"""estatectl - estate consolidation per the Estate Consolidation Standard (ECS).

    python3 estatectl.py run --data DIR --out DIR
    python3 estatectl.py export-report --config FILE --out FILE --commands JSON

Reads only --data; output is deterministic for the same input. A missing input file is
reported on stderr and skipped: everything that can still be computed is computed.
"""
from __future__ import annotations

import argparse
import base64
import configparser
import csv
import hashlib
import html.parser
import io
import json
import quopri
import re
import sqlite3
import sys
import tomllib
import unicodedata
import zipfile
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_FLOOR
from pathlib import Path
from xml.etree import ElementTree as ET

DAY = 86400
REASONS = ["OUT_OF_AUTHORITY", "SUPERSEDED_SCOPE", "VOIDED", "NOT_A_FILE", "STALE_EVENT", "DEFERRED_EVENT",
           "PATH_UNRESOLVED", "SIZE_UNKNOWN", "HASH_UNRESOLVED", "OWNER_UNRESOLVED", "DUPLICATE_PATH",
           "ORPHAN_EVENT", "DELETED", "REPLACED", "HARDLINK_ALIAS", "PURGED"]
UNIT = {"B": 1, "KB": 1000, "KIB": 1024, "MIB": 1048576, "BLK512": 512, "BLK4096": 4096}
FS_CASE = {"ntfs": "insensitive", "hfsplus": "insensitive", "exfat": "insensitive"}
NO_PURGE = {"ARC01"}
MISSING: list[str] = []


def warn(msg):
    print(f"estatectl: {msg}", file=sys.stderr)


def clean(s):
    if s is None:
        return ""
    s = str(s).replace("\ufeff", "").replace("\u200b", "").strip()
    return unicodedata.normalize("NFC", s)


def up(s):
    return clean(s).upper()


# ------------------------------------------------------------------------------- time


def days_from_civil(y, m, d):
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    return era * 146097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719468


def civil(t):
    z = t // DAY + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    rem = t % DAY
    return yoe + era * 400 + (m <= 2), m, d, rem // 3600, rem % 3600 // 60, rem % 60


def stamp(y, mo, d, h=0, mi=0, s=0):
    return days_from_civil(y, mo, d) * DAY + h * 3600 + mi * 60 + s


def iso(t):
    y, m, d, hh, mi, ss = civil(t)
    return f"{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mi:02d}:{ss:02d}Z"


ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")


def parse_iso(s):
    s = clean(s)
    m = ISO_RE.match(s)
    if not m:
        raise ValueError(f"bad instant {s!r}")
    base = stamp(*(int(m.group(i)) for i in range(1, 7)))
    z = m.group(8)
    if z and z != "Z":
        sign = 1 if z[0] == "+" else -1
        digits = z[1:].replace(":", "")
        base -= sign * (int(digits[:2]) * 3600 + int(digits[2:4]) * 60)
    return base


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_rfc2822(s):
    p = clean(s).split()
    d, mo, y = int(p[1]), MONTHS.index(p[2]) + 1, int(p[3])
    hh, mi, ss = (int(x) for x in p[4].split(":"))
    z = p[5]
    sign = 1 if z[0] == "+" else -1
    return stamp(y, mo, d, hh, mi, ss) - sign * (int(z[1:3]) * 3600 + int(z[3:5]) * 60)


def floor_div(num: int, den: int) -> int:
    return num // den


def serial_seconds(v) -> int:
    d = Decimal(repr(v)) if isinstance(v, float) else Decimal(str(v))
    return int((d * DAY).to_integral_value(rounding=ROUND_HALF_EVEN))


class Zones:
    def __init__(self):
        self.seg = {}

    def add(self, zone, frm, to, off, dst):
        self.seg.setdefault(zone.lower(), []).append((frm, to, off, dst))

    def finish(self):
        for v in self.seg.values():
            v.sort()

    def std(self, zone):
        segs = self.seg.get(zone.lower(), [])
        for s in segs:
            if s[3] == 0:
                return s[2]
        return segs[0][2] if segs else 0

    def to_utc(self, zone, local):
        offs = [off for (s, e, off, _d) in self.seg.get(zone.lower(), ()) if s <= local - off < e]
        if not offs:
            return local - self.std(zone)
        return local - min(offs)


def parse_offset(v):
    s = clean(v)
    if ":" in s:
        sign = -1 if s.startswith("-") else 1
        hh, mm = s.lstrip("+-").split(":")
        return sign * (int(hh) * 3600 + int(mm) * 60)
    return int(s)


# ------------------------------------------------------------------------------- numbers


GROUP = re.compile(r"[,\s'\u2009\u202f\u00a0.]")


def int_grouped(s):
    s = clean(s)
    neg = s.startswith("-")
    digits = GROUP.sub("", s.lstrip("+-"))
    return -int(digits) if neg else int(digits)


def exact_bytes(value: str, unit: int) -> int:
    v = Decimal(clean(value).replace(",", ""))
    return int(v * unit)


def kb_de(value: str) -> int:
    s = clean(value).replace(".", "").replace(",", ".")
    return int((Decimal(s) * 1000).to_integral_value(rounding=ROUND_HALF_EVEN))


def to_bool(v):
    if isinstance(v, bool):
        return v
    s = clean(v).lower()
    if s in ("true", "yes", "on", "1"):
        return True
    if s in ("false", "no", "off", "0"):
        return False
    raise ValueError(f"bad boolean {v!r}")


def to_int(v):
    if isinstance(v, bool):
        raise ValueError("bool is not int")
    if isinstance(v, int):
        return v
    s = clean(v)
    m = re.match(r"^([\d_,.\s]+)\s*(KiB|MiB)?$", s, re.I)
    if not m:
        raise ValueError(f"bad integer {v!r}")
    n = int(re.sub(r"[_,.\s]", "", m.group(1)))
    mult = {"kib": 1024, "mib": 1048576}.get((m.group(2) or "").lower(), 1)
    return n * mult


# ------------------------------------------------------------------------------- readers
REV = {"remark": "note", "state": "status", "label": "display", "why": "reason", "bytes_raw": "size",
       "size_bytes": "bytes", "owned_by": "owner"}
CTL_RE = re.compile(r"ctl_id=(\S+)\s+prev=(\S+)\s+rows=(\d+)")


def remap(names, base):
    out = []
    for n in names:
        n = clean(n)
        if n in base:
            out.append(n)
        elif n.endswith("_v2") and n[:-3] in base:
            out.append(n[:-3])
        elif REV.get(n) in base:
            out.append(REV[n])
        else:
            out.append(n)
    return out


class Doc:
    """One parsed input: control record, metadata and named tables of row dicts."""

    def __init__(self, name):
        self.name = name
        self.ctl = None
        self.meta = {}
        self.tables = {}
        self.text = ""

    def rows(self, table=None):
        if table is None:
            out = []
            for v in self.tables.values():
                out.extend(v)
            return out
        return self.tables.get(table, [])


def ctl_from_text(s):
    m = CTL_RE.search(s)
    return (m.group(1), m.group(2), int(m.group(3))) if m else None


def is_header(cells, base):
    vals = [clean(c) for c in cells if clean(c)]
    if len(vals) < 2:
        return False
    known = set(base) | {REV_k for REV_k in REV} | {b + "_v2" for b in base}
    return all(v in known for v in vals)


def read_csv(p: Path, doc: Doc):
    text = p.read_bytes().decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    base = None
    cur = None
    out = []
    for r in rows:
        if not r:
            continue
        if base is None and r[0].startswith("#"):
            line = ",".join(r)
            c = ctl_from_text(line)
            if c and doc.ctl is None:
                doc.ctl = c
            else:
                for kv in re.findall(r"(\w+)=(\S+)", line):
                    doc.meta[kv[0]] = kv[1]
                doc.meta.setdefault("comments", []).append(line)
            continue
        if base is None:
            base = [clean(c) for c in r]
            cur = base
            continue
        if is_header(r, base):
            cur = remap(r, base)
            continue
        out.append({cur[i]: (r[i].rstrip("\r") if i < len(r) else "") for i in range(len(cur))})
    doc.tables["main"] = out


def tsv_unescape(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            out.append({"t": "\t", "n": "\n", "r": "\r", "\\": "\\"}.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def read_tsv(p: Path, doc: Doc, enc_col=None):
    base = None
    cur = None
    out = []
    for raw in p.read_bytes().split(b"\n"):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        if not raw:
            continue
        if base is None and raw.startswith(b"#"):
            line = raw.decode("utf-8")
            c = ctl_from_text(line)
            if c and doc.ctl is None:
                doc.ctl = c
            else:
                for kv in re.findall(r"(\w+)=(\S+)", line):
                    doc.meta[kv[0]] = kv[1]
            continue
        cells_b = raw.split(b"\t")
        if base is None:
            base = [clean(c.decode("utf-8")) for c in cells_b]
            cur = base
            continue
        probe = [c.decode("latin-1") for c in cells_b]
        if is_header(probe, base):
            cur = remap(probe, base)
            continue
        enc = "utf-8"
        if enc_col and enc_col in cur:
            enc = cells_b[cur.index(enc_col)].decode("ascii").strip() or "utf-8"
        cells = [tsv_unescape(c.decode(enc)) for c in cells_b]
        out.append({cur[i]: (cells[i] if i < len(cells) else "") for i in range(len(cur))})
    doc.tables["main"] = out


def read_jsonl(p: Path, doc: Doc):
    rename = {}
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if "_ctl" in obj:
            c = obj["_ctl"]
            doc.ctl = (c["ctl_id"], c["prev"], int(c["rows"]))
            continue
        if len(obj) == 1 and next(iter(obj)).startswith("_"):
            k = next(iter(obj))
            if k == "_schema":
                rename = {v: k2 for k2, v in obj[k].get("rename", {}).items()}
            else:
                doc.meta.update(obj[k])
            continue
        out.append({rename.get(k, k): v for k, v in obj.items()})
    doc.tables["main"] = out


def read_json_lists(obj, doc: Doc):
    if "_ctl" in obj:
        c = obj["_ctl"]
        doc.ctl = (c["ctl_id"], c["prev"], int(c["rows"]))
    for k, v in obj.items():
        if isinstance(v, list) and not k.endswith("_v2"):
            rows = list(v)
            if f"{k}_v2" in obj:
                ren = {b: a for a, b in obj.get(f"{k}_v2_renames", {}).items()}
                rows += [{ren.get(x, x): y for x, y in r.items()} for r in obj[f"{k}_v2"]]
            doc.tables[k] = rows
        elif isinstance(v, dict) and k != "_ctl":
            doc.meta[k] = v
        elif k not in ("_ctl",) and not k.endswith("_renames"):
            doc.meta[k] = v


def read_json(p: Path, doc: Doc):
    read_json_lists(json.loads(p.read_text(encoding="utf-8")), doc)


def read_xml(p: Path, doc: Doc, elem):
    root = ET.parse(str(p)).getroot()
    doc.meta.update(root.attrib)
    doc.ctl = (root.get("ctl-id"), root.get("ctl-prev"), int(root.get("ctl-rows")))
    ren = {}
    out = []
    for child in root:
        if child.tag == "schema-change":
            ren = {v: k for k, v in json.loads(child.get("renames", "{}")).items()}
            continue
        if child.tag != elem:
            doc.tables.setdefault(child.tag, []).append(dict(child.attrib))
            continue
        row = {ren.get(k, k): v for k, v in child.attrib.items()}
        for sub in child:
            row[ren.get(sub.tag, sub.tag)] = sub.text or ""
            for ak, av in sub.attrib.items():
                row[f"{ren.get(sub.tag, sub.tag)}@{ak}"] = av
        out.append(row)
    doc.tables["main"] = out


def read_xlsx(p: Path, doc: Doc):
    import openpyxl
    wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
    doc.meta["date1904"] = bool(getattr(wb, "epoch", None) and wb.epoch.year == 1904)
    with zipfile.ZipFile(p) as zf:
        core = zf.read("docProps/core.xml").decode("utf-8")
    m = re.search(r"<dc:subject>(.*?)</dc:subject>", core, re.S)
    if m:
        doc.ctl = ctl_from_text(m.group(1))
    m = re.search(r"<dc:description>(.*?)</dc:description>", core, re.S)
    doc.meta["description"] = m.group(1) if m else ""
    for ws in wb.worksheets:
        base = None
        cur = None
        out = []
        for r in ws.iter_rows(values_only=True):
            if r is None or all(v is None for v in r):
                continue
            cells = ["" if v is None else v for v in r]
            if base is None:
                base = [clean(c) for c in cells]
                cur = base
                continue
            if all(isinstance(c, str) for c in cells if c != "") and is_header([str(c) for c in cells], base):
                cur = remap([str(c) for c in cells], base)
                continue
            out.append({cur[i]: (cells[i] if i < len(cells) else "") for i in range(len(cur))})
        doc.tables[ws.title] = out
    wb.close()


def read_parquet(p: Path, doc: Doc):
    import pyarrow.parquet as pq
    t = pq.read_table(str(p))
    md = {k.decode(): v.decode() for k, v in (t.schema.metadata or {}).items()}
    doc.meta.update(md)
    doc.ctl = (md.get("ctl_id"), md.get("ctl_prev"), int(md.get("ctl_rows", "0")))
    doc.tables["main"] = t.to_pylist()


def read_sqlite(p: Path, doc: Doc):
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    c = con.execute("SELECT * FROM _control").fetchone()
    doc.ctl = (c["ctl_id"], c["prev"], int(c["rows"]))
    names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    views = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='view'")]
    if "_export" in views:
        doc.meta.update(dict(con.execute("SELECT * FROM _export").fetchone()))
    groups = {}
    for n in names:
        groups.setdefault(n[:-3] if n.endswith("_v2") else n, []).append(n)
    for basen, parts in groups.items():
        rows = []
        base_cols = None
        for n in sorted(parts, key=len):
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{n}")')]
            if base_cols is None:
                base_cols = cols
            mapped = remap(cols, base_cols)
            for r in con.execute(f'SELECT * FROM "{n}"'):
                rows.append({mapped[i]: r[i] for i in range(len(cols))})
        doc.tables[basen] = rows
    con.close()


def read_yaml(p: Path, doc: Doc):
    import yaml
    obj = yaml.safe_load(p.read_text(encoding="utf-8"))
    out = {}
    for k, v in obj.items():
        if k == "_ctl":
            doc.ctl = (str(v["ctl_id"]), str(v["prev"]), int(v["rows"]))
        elif isinstance(v, list):
            if k.endswith("_v2"):
                ren = {}
                rows = []
                for item in v:
                    if "_renames" in item:
                        r = item["_renames"]
                        ren = {b: a for a, b in (json.loads(r) if isinstance(r, str) else r).items()}
                        continue
                    rows.append({ren.get(a, a): b for a, b in item.items()})
                out.setdefault(k[:-3], []).extend(rows)
            else:
                out.setdefault(k, []).extend(v)
        else:
            doc.meta[k] = v
    doc.tables = out


def read_toml(p: Path, doc: Doc):
    obj = tomllib.loads(p.read_text(encoding="utf-8"))
    c = obj.pop("_ctl")
    doc.ctl = (c["ctl_id"], c["prev"], int(c["rows"]))
    for k, v in obj.items():
        if isinstance(v, list):
            doc.tables.setdefault(k[:-3] if k.endswith("_v2") else k, []).extend(v)
        else:
            doc.meta[k] = v


def read_ini(p: Path, doc: Doc):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read_string(p.read_bytes().decode("utf-8-sig"))
    ren = {}
    out = []
    for sec in cp.sections():
        items = dict(cp.items(sec))
        if sec == "_ctl":
            doc.ctl = (items["ctl_id"], items["prev"], int(items["rows"]))
            continue
        if sec == "__layout__":
            ren = {b: a for a, b in json.loads(items.get("renames", "{}")).items()}
            continue
        row = {ren.get(k, k): v for k, v in items.items()}
        row["_section"] = sec
        out.append(row)
    doc.tables["main"] = out


def md_cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, i = [], [], 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            cur.append(s[i + 1])
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return [c.replace("<br>", "\n") for c in cells]


def read_md(p: Path, doc: Doc):
    text = p.read_text(encoding="utf-8")
    doc.text = text
    doc.ctl = ctl_from_text(text.split("\n", 1)[0])
    tables = []
    cur = None
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("|"):
            if cur is None:
                cur = {"header": md_cells(ln), "rows": [], "title": next((lines[j].strip() for j in range(i - 1, -1, -1) if lines[j].strip()), "")}
                continue
            if re.match(r"^\|(-+\|)+$", ln.strip()):
                continue
            cur["rows"].append(md_cells(ln))
        else:
            if cur is not None:
                tables.append(cur)
                cur = None
    if cur is not None:
        tables.append(cur)
    doc.raw_tables = tables


class _HTMLTables(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.cur = None
        self.row = None
        self.cell = None
        self.comments = []
        self.heading = ""
        self.in_h = False
        self.banner = ""
        self.in_banner = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.cur = {"title": self.heading, "rows": []}
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag in ("h1", "h2"):
            self.in_h = True
            self.heading = ""
        elif tag == "div" and ("class", "banner") in attrs:
            self.in_banner = True

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.cur["rows"].append(self.row)
            self.row = None
        elif tag == "table":
            self.tables.append(self.cur)
            self.cur = None
        elif tag in ("h1", "h2"):
            self.in_h = False
        elif tag == "div":
            self.in_banner = False

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
        elif self.in_h:
            self.heading += data
        elif self.in_banner:
            self.banner += data

    def handle_comment(self, data):
        self.comments.append(data)


def read_html(p: Path, doc: Doc):
    h = _HTMLTables()
    h.feed(p.read_text(encoding="utf-8"))
    for c in h.comments:
        if ctl_from_text(c):
            doc.ctl = ctl_from_text(c)
    doc.meta["banner"] = h.banner
    doc.raw_tables = [{"title": t["title"], "header": t["rows"][0], "rows": t["rows"][1:]} for t in h.tables]


WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_docx(p: Path, doc: Doc):
    with zipfile.ZipFile(p) as zf:
        core = zf.read("docProps/core.xml").decode("utf-8")
        body = ET.fromstring(zf.read("word/document.xml"))
    m = re.search(r"<dc:subject>(.*?)</dc:subject>", core, re.S)
    doc.ctl = ctl_from_text(m.group(1)) if m else None
    doc.meta["subject"] = m.group(1) if m else ""

    def ptext(pel):
        out = []
        for node in pel.iter():
            if node.tag == WNS + "t":
                out.append(node.text or "")
            elif node.tag == WNS + "tab":
                out.append("\t")
        return "".join(out)

    tables = []
    last_p = ""
    paras = []
    for el in body.find(WNS + "body"):
        if el.tag == WNS + "p":
            last_p = ptext(el)
            paras.append(last_p)
        elif el.tag == WNS + "tbl":
            rows = []
            for tr in el.findall(WNS + "tr"):
                rows.append([ptext(tc) for tc in tr.findall(WNS + "tc")])
            tables.append({"title": last_p, "header": rows[0], "rows": rows[1:]})
    doc.text = "\n".join(paras)
    doc.raw_tables = tables


def pdf_unescape(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "u":
                out.append(chr(int(s[i + 2:i + 6], 16)))
                i += 6
                continue
            if n == "U":
                out.append(chr(int(s[i + 2:i + 10], 16)))
                i += 10
                continue
            out.append({"t": "\t", "n": "\n"}.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def pdf_split(line):
    cells, cur, i = [], [], 0
    while i < len(line):
        if line.startswith(" | ", i):
            cells.append("".join(cur))
            cur = []
            i += 3
            continue
        if line[i] == "\\" and i + 1 < len(line):
            cur.append(line[i:i + 2])
            i += 2
            continue
        cur.append(line[i])
        i += 1
    cells.append("".join(cur))
    return [pdf_unescape(c) for c in cells]


def pdf_lines(p: Path):
    import pypdf
    r = pypdf.PdfReader(str(p))
    lines = []
    for page in r.pages:
        lines.extend(page.extract_text().split("\n"))
    return lines


def read_pdf(p: Path, doc: Doc):
    lines = pdf_lines(p)
    doc.ctl = ctl_from_text(lines[0])
    tables = []
    cur = None
    title = ""
    for ln in lines[1:]:
        if ln.startswith("COLUMNS: "):
            hdr = [c.strip() for c in ln[9:].split(" | ")]
            if cur is None or title:
                cur = {"title": title, "rows": [], "base": hdr}
                tables.append(cur)
                title = ""
            cur["current"] = remap(hdr, cur["base"])
            continue
        if cur is not None and " | " in ln:
            cells = ["" if c == "~" else c for c in pdf_split(ln)]
            cur["rows"].append(dict(zip(cur["current"], cells)))
            continue
        if ln.strip():
            title = ln.strip()
    doc.pdf_tables = tables
    doc.text = "\n".join(lines)


def tables_as_dicts(raw_tables):
    """Group md/html/docx tables: a table right after another with the same title is its continuation."""
    out = []
    for t in raw_tables:
        if out and t.get("title") and (t["title"].startswith(("Rows below", "The table continues")) or t["title"] == out[-1]["title"]):
            base = out[-1]["base"]
            hdr = remap(t["header"], base)
            out[-1]["rows"] += [dict(zip(hdr, r)) for r in t["rows"]]
            continue
        base = [clean(h) for h in t["header"]]
        out.append({"title": t.get("title", ""), "base": base, "rows": [dict(zip(base, r)) for r in t["rows"]]})
    return out


# ------------------------------------------------------------------------------- estate model
VOL_OF = {
    "inv_eng01_q3.csv": "ENG01", "inv_eng01_q3_part2.db": "ENG01", "inv_eng01_q3_deep.jsonl": "ENG01",
    "inv_eng02_q3.txt": "ENG02", "inv_mkt01_q3.jsonl": "MKT01", "inv_mkt01_supplement.xlsx": "MKT01",
    "inv_fin01_q3.parquet": "FIN01", "inv_fin01_q3_r2.csv": "FIN01", "inv_fin02_q3.tsv": "FIN02",
    "arc01_tape_catalog.txt": "ARC01", "arc01_ltfs_index.db": "ARC01", "inv_obj01_q3_r2.csv": "OBJ01",
    "inv_hr01_q3.xlsx": "HR01", "inv_lab01_q3.jsonl": "LAB01", "inv_ops01_q3.tsv": "OPS01",
    "inv_rnd01_q3.json": "RND01", "rnd01_cold_listing.pdf": "RND01", "inv_leg01_q3.xml": "LEG01",
}
JOURNALS = {
    "journal_eng01_q3.log": ("ENG01", "iso"), "journal_mkt01_q3.log": ("MKT01", "iso"),
    "journal_mkt01_q3_b.log": ("MKT01", "iso"), "journal_fin01_q3.log": ("FIN01", "frac"),
    "journal_ops01_q3.log": ("OPS01", "local"), "journal_eng02_q3.csv": ("ENG02", None),
    "journal_hr01_q3.jsonl": ("HR01", None), "journal_obj01_events.jsonl": ("OBJ01", None),
    "journal_fin02_q3.xml": ("FIN02", None), "journal_rnd01_q3.json": ("RND01", None),
    "journal_leg01_notifications.mbox": ("LEG01", None),
}
HOST_JOURNALS = {"journal_eng01_q3.log", "journal_fin01_q3.log", "journal_ops01_q3.log"}
XWALK_PART = {"ENG02": "md5A", "LEG01": "md5A", "MKT01": "md5B", "OBJ01": "md5B", "LAB01": "md5B", "HR01": "md5C",
              "FIN02": "sha1A", "RND01": "sha1B", "ARC01": "sha1V"}
ALL_FILES = [
    "inv_eng01_q3.csv", "inv_obj01_q3_r2.csv", "inv_fin01_q3_r2.csv", "journal_eng02_q3.csv", "principal_merges.csv",
    "void_register_q3.csv", "change_tickets.csv", "errata_register_q3.csv", "legal_holds_register.csv",
    "store_index_prior_a.csv", "hash_xwalk_md5_eng.csv", "case_sensitive_dirs.csv", "export_batches_a.csv",
    "inv_fin02_q3.tsv", "inv_ops01_q3.tsv", "tz_transitions_a.tsv", "ext_families_a.tsv", "alias_remap_nas.tsv",
    "principal_uid_map.tsv", "export_batches_b.tsv", "errata_register_q3_r2.tsv", "inv_mkt01_q3.jsonl",
    "inv_lab01_q3.jsonl", "inv_eng01_q3_deep.jsonl", "journal_hr01_q3.jsonl", "journal_obj01_events.jsonl",
    "hash_xwalk_md5_mkt.jsonl", "void_register_supplement.jsonl", "store_index_prior_b.jsonl", "inv_hr01_q3.xlsx",
    "inv_mkt01_supplement.xlsx", "principal_directory.xlsx", "authority_matrix.xlsx", "principal_sid_map.xlsx",
    "alias_remap_sharepoint.xlsx", "ext_families_b.xlsx", "holds_matter_index.xlsx", "inv_rnd01_q3.json",
    "volumes_cmdb.json", "volume-policy.json", "principal_s3_ids.json", "journal_rnd01_q3.json",
    "hash_xwalk_sha1_fin.json", "inv_leg01_q3.xml", "void_register_q3_r2.xml", "journal_fin02_q3.xml",
    "alias_remap_dfs.xml", "case_sensitive_dirs_leg01.xml", "errata_register_tape.xml", "inv_fin01_q3.parquet",
    "hash_index_master.parquet", "estate_manifest_q2.parquet", "store_index_prior_c.parquet",
    "hash_xwalk_md5_fin.parquet", "tz_transitions_b.parquet", "ECS-handbook-paths.docx",
    "retention-schedule-2026-r2.docx", "legal-hold-memo-q3.docx", "owner-migration-plan.docx",
    "errata-bulletin-q3.docx", "tape-operations-notes.docx", "retention-schedule-2026-r3.docx",
    "ECS-annex-hosts-rev6.pdf", "hr-roster-q3.pdf", "audit-scope-letter-fin.pdf", "rnd01_cold_listing.pdf",
    "vendor-hash-attestation.pdf", "units-bulletin.pdf", "ECS-annex-hosts-rev7.pdf", "journal_eng01_q3.log",
    "journal_mkt01_q3.log", "journal_fin01_q3.log", "journal_ops01_q3.log", "journal_mkt01_q3_b.log",
    "inv_eng01_q3_part2.db", "arc01_ltfs_index.db", "principal_legacy.db", "store_index_prior_d.db", "volumes.yaml",
    "site-policy.yaml", "retention_rules_v3.yaml", "site-policy-v2.yaml", "estate-defaults.toml",
    "retention_rules_v4.toml", "retention_overlays.toml", "operator-overrides.ini", "host_aliases.ini",
    "service_accounts.ini", "ECS-standard.md", "source-register.md", "ops-runbook.md", "principal_map_ldap.html",
    "ext_families_wiki.html", "holds_portal_export.html", "inv_eng02_q3.txt", "arc01_tape_catalog.txt",
    "principal_mainframe_ids.txt", "journal_leg01_notifications.mbox", "legal_hold_windows.ics", "tool.zip",
]


class Estate:
    def __init__(self, data: Path):
        self.data = data
        self.docs = {}
        self.missing = []

    def path(self, name):
        p = self.data / name
        if not p.is_file():
            if name not in self.missing:
                self.missing.append(name)
                warn(f"missing input {name}; continuing without it")
            return None
        return p

    def doc(self, name, reader, *args):
        if name in self.docs:
            return self.docs[name]
        d = Doc(name)
        p = self.path(name)
        if p is not None:
            reader(p, d, *args)
        self.docs[name] = d
        return d

    def tabular(self, name):
        if name in self.docs:
            return self.docs[name]
        d = Doc(name)
        p = self.path(name)
        if p is None:
            self.docs[name] = d
            return d
        if name.endswith(".md"):
            read_md(p, d)
            d.tdict = tables_as_dicts(d.raw_tables)
        elif name.endswith(".html"):
            read_html(p, d)
            d.tdict = tables_as_dicts(d.raw_tables)
        elif name.endswith(".docx"):
            read_docx(p, d)
            d.tdict = tables_as_dicts(d.raw_tables)
        elif name.endswith(".pdf"):
            read_pdf(p, d)
            d.tdict = [{"title": t["title"], "rows": t["rows"]} for t in d.pdf_tables]
        self.docs[name] = d
        return d

    def table(self, name, title_part=None, index=None):
        d = self.tabular(name)
        tabs = getattr(d, "tdict", [])
        if index is not None:
            return tabs[index]["rows"] if index < len(tabs) else []
        for t in tabs:
            if title_part is None or title_part.lower() in (t["title"] or "").lower():
                return t["rows"]
        return []


def ctl_of(es, name):
    p = es.path(name)
    if p is None:
        return None
    if name == "tool.zip":
        with zipfile.ZipFile(p) as zf:
            return ctl_from_text(zf.read("CONTROL").decode().replace("\n", " "))
    if name.endswith((".csv",)):
        return es.doc(name, read_csv).ctl
    if name.endswith(".tsv"):
        return es.doc(name, read_tsv, "enc" if name == "inv_fin02_q3.tsv" else None).ctl
    if name.endswith(".jsonl"):
        return es.doc(name, read_jsonl).ctl
    if name.endswith(".json"):
        return es.doc(name, read_json).ctl
    if name.endswith(".xml"):
        return ctl_from_text(" ".join(f"{k.replace('ctl-', '').replace('id', 'ctl_id')}={v}" for k, v in
                                      ET.parse(str(p)).getroot().attrib.items() if k.startswith("ctl-")))
    if name.endswith(".xlsx"):
        with zipfile.ZipFile(p) as zf:
            core = zf.read("docProps/core.xml").decode()
        return ctl_from_text(re.search(r"<dc:subject>(.*?)</dc:subject>", core, re.S).group(1))
    if name.endswith(".parquet"):
        import pyarrow.parquet as pq
        md = {k.decode(): v.decode() for k, v in (pq.read_schema(str(p)).metadata or {}).items()}
        return (md["ctl_id"], md["ctl_prev"], int(md["ctl_rows"]))
    if name.endswith(".db"):
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        c = con.execute("SELECT ctl_id, prev, rows FROM _control").fetchone()
        con.close()
        return (c[0], c[1], int(c[2]))
    if name.endswith(".yaml"):
        return es.doc(name, read_yaml).ctl
    if name.endswith(".toml"):
        return es.doc(name, read_toml).ctl
    if name.endswith(".ini"):
        return es.doc(name, read_ini).ctl
    if name.endswith((".md", ".html", ".docx", ".pdf")):
        return es.tabular(name).ctl
    if name.endswith(".txt"):
        first = p.read_bytes().split(b"\n", 1)[0].decode()
        return ctl_from_text(first)
    if name.endswith(".log"):
        first = p.read_bytes().split(b"\n", 1)[0].decode()
        return ctl_from_text(first)
    if name.endswith(".mbox"):
        head = p.read_bytes()[:4000].decode("utf-8", "replace")
        g = lambda h: re.search(rf"^{h}: (\S+)", head, re.M).group(1)
        return (g("X-Ctl-Id"), g("X-Ctl-Prev"), int(g("X-Ctl-Rows")))
    if name.endswith(".ics"):
        head = p.read_bytes()[:4000].decode("utf-8", "replace")
        g = lambda h: re.search(rf"^{h}:(\S+)", head, re.M).group(1)
        return (g("X-CTL-ID"), g("X-CTL-PREV"), int(g("X-CTL-ROWS")))
    return None


# ------------------------------------------------------------------------------- tickets and config
class Tickets:
    def __init__(self, es):
        self.best = {}
        for r in es.doc("change_tickets.csv", read_csv).rows():
            t = up(r.get("ticket"))
            rev = int(clean(r.get("rev")))
            if t not in self.best or rev > self.best[t][0]:
                self.best[t] = (rev, up(r.get("state")), clean(r.get("decided_utc")))
        self.window_end = None

    def ok(self, t):
        b = self.best.get(up(t))
        if not b or b[1] != "APPROVED" or b[2].startswith("0000"):
            return False
        return parse_iso(b[2]) < self.window_end


def toml_rows(doc, name):
    rows = doc.rows(name)
    if not rows:
        return rows
    base = set(rows[0].keys())
    return [{(k if k in base else REV.get(k, k)): v for k, v in r.items()} for r in rows]


def norm_key(k):
    k = clean(k)
    ns, _, rest = k.partition(".")
    return ns.lower() + "." + rest if rest else k.lower()


def typed(key, v):
    if key in ("window.start", "window.end"):
        return iso(parse_iso(v))
    if key == "purge.enabled" or key.startswith("subtree."):
        return to_bool(v)
    if key == "store.block_size":
        return to_int(v)
    return clean(v)


def config_rows(es):
    layers = {}
    d10 = es.doc("estate-defaults.toml", read_toml)
    layers[10] = toml_rows(d10, "setting")
    layers[20] = es.doc("site-policy.yaml", read_yaml).rows("settings")
    layers[30] = es.doc("volume-policy.json", read_json).rows("settings")
    layers[40] = es.doc("operator-overrides.ini", read_ini).rows()
    out = {}
    for layer, rows in layers.items():
        lst = []
        for r in rows:
            if "key" not in r:
                continue
            key = norm_key(r["key"])
            if key.startswith("subtree."):
                body, _, flag = key.rpartition(".")
                vol, _, prefix = body[8:].partition(":")
                key = f"subtree.{vol.upper()}:{prefix}.{flag.lower()}"
            elif key.startswith("vol."):
                parts = key.split(".")
                key = f"vol.{parts[1].upper()}.{parts[2].lower()}"
            lst.append({"key": key, "value": r.get("value"), "profile": clean(r.get("profile") or "*"),
                        "final": to_bool(r.get("final", False)) if r.get("final") not in (None, "") else False,
                        "ticket": r.get("ticket"), "oid": up(r.get("override_id") or r.get("_section", "").split(":", 1)[-1])})
        out[layer] = lst
    return out


def resolve_config(es, tickets, profile, layers, revoked):
    locked = set()
    eff = {}
    for layer in (10, 20, 30, 40):
        new_locks = set()
        for want in ("*", profile):
            for r in layers.get(layer, []):
                if r["profile"] != want or r["key"] in locked:
                    continue
                if layer == 40:
                    if tickets.window_end is None or not tickets.ok(r["ticket"]) or r["oid"] in revoked:
                        continue
                try:
                    eff[r["key"]] = typed(r["key"], r["value"])
                except ValueError as exc:
                    warn(f"bad setting {r['key']}: {exc}")
                    continue
                if r["final"]:
                    new_locks.add(r["key"])
        locked |= new_locks
    return dict(sorted(eff.items()))


# ------------------------------------------------------------------------------- reference tables
def best_by(rows, keyf, revf=lambda r: int(clean(r.get("rev") or 1))):
    best = {}
    for r in rows:
        k = keyf(r)
        if k is None:
            continue
        rv = revf(r)
        if k not in best or rv > best[k][0]:
            best[k] = (rv, r)
    return {k: v[1] for k, v in best.items()}


def root_key(root):
    root = clean(root)
    if root.startswith("\\\\"):
        root = root.replace("\\", "/")
    return root if root.startswith("/") and not root.startswith("//") else root.lower()


class Refs:
    def __init__(self, es, tickets):
        self.es = es
        self.t = tickets
        self._aliases()
        self._serials()
        self._csdirs()
        self._principals()
        self._hosts()
        self._batches()
        self._exts()
        self._rules()
        self._holds()
        self._xwalk()
        self._store()
        self._voids_errata()
        self._authority()

    def _aliases(self):
        es = self.es
        rows = []
        rows += es.doc("alias_remap_nas.tsv", read_tsv).rows()
        rows += es.doc("alias_remap_sharepoint.xlsx", read_xlsx).rows()
        rows += es.doc("alias_remap_dfs.xml", read_xml, "alias").rows("main")
        rows += es.table("ECS-handbook-paths.docx", "Table D")
        rows += es.doc("volumes.yaml", read_yaml).rows("aliases")
        rows += es.table("ECS-standard.md", "Appendix F")
        self.alias = best_by(rows, lambda r: root_key(r["root"]) if r.get("root") else None)
        self.vol_info = {clean(v["code"]).upper(): v for v in es.doc("volumes.yaml", read_yaml).rows("volumes")}

    def _serials(self):
        rows = self.es.doc("volumes_cmdb.json", read_json).rows("serials")
        self.serial = {}
        for k, r in best_by(rows, lambda r: up(r["serial"])).items():
            if clean(r.get("status")).lower() == "active":
                self.serial[k] = up(r["volume"])

    def _csdirs(self):
        rows = [dict(r, volume=r.get("volume") or "ENG02") for r in self.es.doc("case_sensitive_dirs.csv", read_csv).rows()]
        rows += self.es.doc("case_sensitive_dirs_leg01.xml", read_xml, "dir").rows("main")
        b = best_by(rows, lambda r: (up(r["volume"]), clean(r["prefix"]).lower()))
        self.cs = {}
        for (vol, pfx), r in b.items():
            if clean(r.get("status")).lower() == "active":
                self.cs.setdefault(vol, []).append(pfx)
        for v in self.cs.values():
            v.sort(key=len, reverse=True)

    def _principals(self):
        es = self.es
        sidmap = es.doc("principal_sid_map.xlsx", read_xlsx)
        self.register = {up(r["principal_id"]): clean(r["account"]) for r in sidmap.rows("principals") if r.get("principal_id")}
        self.maps = {}

        def add(ns, rows, keyf):
            m = {}
            for r in rows:
                if clean(r.get("status") or "active").lower() != "active":
                    continue
                k = keyf(r)
                if k is None:
                    continue
                vf = clean(r.get("valid_from")) or "1900-01-01T00:00:00Z"
                if k not in m or vf > m[k][0]:
                    m[k] = (vf, up(r.get("principal_id")))
            self.maps[ns] = {k: v[1] for k, v in m.items()}

        add("sid", sidmap.rows("sids"), lambda r: up(r.get("sid")) or None)
        self.host_alias = {}
        for r in es.doc("host_aliases.ini", read_ini).rows():
            a = clean(r["_section"].split(":", 1)[1]).lower()
            self.host_alias[a] = clean(r.get("host")).lower()
        add("uid", es.doc("principal_uid_map.tsv", read_tsv).rows(),
            lambda r: (self.canon_host(r.get("host")), int(clean(r.get("uid")))))
        add("corp", es.table("owner-migration-plan.docx", "Login map"), lambda r: (up(r["domain"]), clean(r["login"]).lower()))
        add("oldcorp", es.table("principal_map_ldap.html", "OLDCORP"), lambda r: (up(r["domain"]), clean(r["login"]).lower())
            if up(r["domain"]) == "OLDCORP" else None)
        add("legacy", es.doc("principal_legacy.db", read_sqlite).rows("logins"),
            lambda r: (up(r["domain"]), clean(r["login"]).lower()))
        add("email", es.table("hr-roster-q3.pdf", "Roster"), lambda r: self.norm_email(r.get("email")))
        add("s3", es.doc("principal_s3_ids.json", read_json).rows("ids"), lambda r: clean(r["canonical_id"]).lower())
        add("svc", [dict(r, account=r["_section"]) for r in es.doc("service_accounts.ini", read_ini).rows()],
            lambda r: clean(r["account"]).lower())
        add("mf", self.fixed_rows("principal_mainframe_ids.txt"), lambda r: up(r.get("mf_id")) or None)
        d02 = es.doc("principal_directory.xlsx", read_xlsx)
        self.sid_hist = {k: up(r["new_sid"]) for k, r in best_by(d02.rows("sid_history"), lambda r: up(r["old_sid"])).items()}
        merges = es.doc("principal_merges.csv", read_csv).rows() + es.table("ops-runbook.md", "Appendix M")
        self.merges = best_by(merges, lambda r: up(r["from_principal"]))

    def canon_host(self, h):
        h = clean(h).lower()
        return self.host_alias.get(h, h)

    @staticmethod
    def norm_email(e):
        e = clean(e).lower()
        local, _, dom = e.partition("@")
        return local.split("+", 1)[0] + "@" + dom

    def fixed_rows(self, name):
        p = self.es.path(name)
        if p is None:
            return []
        return parse_fixed(p)[1]

    def owner(self, tok, we):
        t = clean(tok)
        if not t:
            return None
        u = t.upper()
        if u in ("S-1-0-0", "NOBODY@CORP.EXAMPLE", "CORP\\-", "OLDCORP\\-", "-", "SVC-NONE", "MF?????", "N/A") or u == "0" * 64:
            return None
        pid = None
        if u.startswith("S-1-"):
            pid = self.maps["sid"].get(self.sid_hist.get(u, u))
        elif u.startswith("UID:"):
            _p, host, n = t.split(":")
            if int(n) == 65534:
                return None
            pid = self.maps["uid"].get((self.canon_host(host), int(n)))
        elif "\\" in t:
            dom, _, login = t.partition("\\")
            dom = dom.strip().upper()
            key = (dom, login.strip().lower())
            pid = (self.maps["corp"] if dom == "CORP" else self.maps["oldcorp"] if dom == "OLDCORP" else self.maps["legacy"]).get(key)
        elif "@" in t:
            pid = self.maps["email"].get(self.norm_email(t))
        elif re.fullmatch(r"[0-9a-fA-F]{64}", t):
            pid = self.maps["s3"].get(t.lower())
        elif u.startswith("SVC-"):
            pid = self.maps["svc"].get(t.lower())
        elif u.startswith("MF"):
            pid = self.maps["mf"].get(u)
        if pid is None or pid not in self.register:
            return None
        seen = set()
        while pid in self.merges and pid not in seen:
            m = self.merges[pid]
            if clean(m["status"]).lower() != "applied" or parse_iso(m["effective_utc"]) >= we:
                break
            seen.add(pid)
            pid = up(m["to_principal"])
        return self.register.get(pid)

    def _hosts(self):
        es = self.es
        rows = es.table("source-register.md", "Appendix H") + es.table("ECS-annex-hosts-rev6.pdf", "Hosts")
        self.host_zone = {clean(r["host"]).lower(): clean(r["zone"]) for r in rows if r.get("host")}
        self.zones = Zones()
        for r in es.doc("tz_transitions_a.tsv", read_tsv).rows() + es.doc("tz_transitions_b.parquet", read_parquet).rows():
            self.zones.add(clean(r["zone"]), parse_iso(r["from_utc"]), parse_iso(r["to_utc"]), parse_offset(r["offset_seconds"]),
                           int(clean(r["is_dst"])))
        self.zones.finish()
        inc = es.table("ECS-annex-hosts-rev7.pdf", "Clock incidents")
        best = best_by(inc, lambda r: (clean(r["host"]).lower(), clean(r["from_utc"])))
        self.incidents = {}
        for (h, _f), r in best.items():
            if clean(r["status"]).lower() == "adopted":
                self.incidents.setdefault(h, []).append((parse_iso(r["from_utc"]), parse_iso(r["to_utc"]), int(clean(r["skew_seconds"]))))

    def _batches(self):
        es = self.es
        base = {}
        corr = {}
        for rows in (es.doc("export_batches_a.csv", read_csv).rows(), es.doc("export_batches_b.tsv", read_tsv).rows(),
                     es.table("tape-operations-notes.docx", "Batch register"), es.table("units-bulletin.pdf", "Batch units")):
            for r in rows:
                b = up(r.get("batch_id"))
                if not b:
                    continue
                if clean(r.get("source")).lower() == "correction":
                    corr[b] = r
                else:
                    base[b] = r
        self.batch = {}
        for b, r in base.items():
            unit = clean((corr.get(b) or r)["unit"])
            self.batch[b] = (UNIT.get(unit.upper()), parse_iso(r["captured_utc"]))

    def _exts(self):
        es = self.es
        tabs = [es.doc("ext_families_a.tsv", read_tsv).rows(), es.doc("ext_families_b.xlsx", read_xlsx).rows(),
                es.table("retention-schedule-2026-r2.docx", "Annex C"), es.table("ext_families_wiki.html", "Families"),
                self.tool_ext_rows()]
        corr = best_by(es.table("retention-schedule-2026-r3.docx", "Annex F"), lambda r: clean(r["ext"]).lower().lstrip("."))
        self.ext_tables = []
        for i, rows in enumerate(tabs):
            b = best_by(rows, lambda r: clean(r["ext"]).lower().lstrip(".") if r.get("ext") else None)
            t = {}
            for e, r in b.items():
                fam = clean(r["family"])
                if i == 0 and clean(r.get("pending")).lower() == "yes" and e in corr:
                    fam = clean(corr[e]["family"])
                t[e] = (clean(r["status"]).lower(), fam)
            self.ext_tables.append(t)
        self.ext_eff = {}
        for t in reversed(self.ext_tables):
            for e, (st, fam) in t.items():
                if st == "active" and fam.upper() != "N/A":
                    self.ext_eff[e] = fam.upper()

    def tool_ext_rows(self):
        p = self.es.path("tool.zip")
        if p is None:
            return []
        with zipfile.ZipFile(p) as zf:
            data = zf.read("estatectl/ext_families_builtin.tsv")
        tmp = Doc("ext_e")
        base = None
        cur = None
        out = []
        for raw in data.split(b"\n"):
            raw = raw.rstrip(b"\r")
            if not raw:
                continue
            cells = [tsv_unescape(c) for c in raw.decode("utf-8").split("\t")]
            if base is None:
                base = cells
                cur = base
                continue
            if is_header(cells, base):
                cur = remap(cells, base)
                continue
            out.append(dict(zip(cur, cells)))
        return out

    def family(self, name):
        low = name.lower()
        if low.startswith(".") and low.count(".") == 1:
            return None
        parts = low.split(".")
        for k in range(1, len(parts)):
            cand = ".".join(parts[k:])
            if cand in self.ext_eff:
                return self.ext_eff[cand]
        return None

    def _rules(self):
        es = self.es
        v3 = es.doc("retention_rules_v3.yaml", read_yaml).rows("rules")
        wd = {int(clean(w["rule_seq"])) for w in toml_rows(es.doc("retention_rules_v4.toml", read_toml), "withdrawal")
              if self.t.ok(w["ticket"])}
        rules = sorted((r for r in v3 if clean(r.get("status")).lower() == "active" and int(r["seq"]) not in wd),
                       key=lambda r: int(r["seq"]))
        rules += sorted(toml_rows(es.doc("retention_overlays.toml", read_toml), "overlay"), key=lambda r: int(r["seq"]))
        self.matcher = Matcher([(clean(r["scope"]).upper() if clean(r["scope"]) != "*" else "*", clean(r["pattern"]),
                                 clean(r["class"]).lower()) for r in rules])
        self.classes = {}
        for r in es.table("retention-schedule-2026-r2.docx", "Table 1"):
            pa = clean(r["purge_after_days"])
            aa = clean(r["archive_after_days"])
            self.classes[clean(r["class"]).lower()] = (int(pa) if pa else None, int(aa) if aa else None)

    def _holds(self):
        es = self.es
        rel = {}
        for r in es.table("legal-hold-memo-q3.docx", "Releases"):
            rel.setdefault(up(r["hold_id"]), []).append(r)
        self.releases = rel
        self.matters = {up(r["matter_id"]): clean(r["status"]).lower() for r in es.doc("holds_matter_index.xlsx", read_xlsx).rows("matters")}
        rows = es.doc("legal_holds_register.csv", read_csv).rows() + es.doc("holds_matter_index.xlsx", read_xlsx).rows("holds")
        rows += es.table("holds_portal_export.html", "Holds")
        rows += read_ics_holds(es)
        self.hold_rows = rows

    def active_holds(self, ws, we):
        out = {}
        for r in self.hold_rows:
            if clean(r.get("status")).lower() != "active":
                continue
            hid = up(r["hold_id"])
            if self.matters.get(up(r.get("matter"))) == "closed":
                continue
            if any(self.t.ok(x["ticket"]) and parse_iso(x["released_utc"]) < we for x in self.releases.get(hid, [])):
                continue
            frm = parse_iso(r["from_utc"])
            to = clean(r.get("to_utc"))
            if not (frm < we and (not to or parse_iso(to) > ws)):
                continue
            pfx = clean(r["prefix"]).rstrip("/")
            out.setdefault((up(r["volume"]), pfx.strip("/").split("/")[0]), []).append(pfx)
        return out

    def _xwalk(self):
        es = self.es
        parts = {"md5A": es.doc("hash_xwalk_md5_eng.csv", read_csv).rows(),
                 "md5B": es.doc("hash_xwalk_md5_mkt.jsonl", read_jsonl).rows(),
                 "md5C": es.doc("hash_xwalk_md5_fin.parquet", read_parquet).rows(),
                 "sha1A": es.doc("hash_xwalk_sha1_fin.json", read_json).rows("crosswalk"),
                 "sha1B": es.table("vendor-hash-attestation.pdf", "Attested"),
                 "sha1V": [r for r in es.doc("hash_index_master.parquet", read_parquet).rows() if up(r.get("origin")) == "ARC01"]}
        self.xwalk = {}
        for part, rows in parts.items():
            b = best_by(rows, lambda r: clean(r["digest"]).lower())
            self.xwalk[part] = {k: clean(r["sha256"]).lower() for k, r in b.items() if clean(r["status"]).lower() == "ok"}

    def _store(self):
        es = self.es
        rows = (es.doc("store_index_prior_a.csv", read_csv).rows() + es.doc("store_index_prior_b.jsonl", read_jsonl).rows()
                + es.doc("store_index_prior_c.parquet", read_parquet).rows()
                + es.doc("store_index_prior_d.db", read_sqlite).rows("store_index"))
        b = best_by(rows, lambda r: clean(r["sha256"]).lower())
        self.stored = {k for k, r in b.items() if clean(r["status"]).lower() == "present"}

    def _voids_errata(self):
        es = self.es
        rows = es.doc("void_register_q3.csv", read_csv).rows() + es.doc("void_register_supplement.jsonl", read_jsonl).rows()
        b = best_by(rows, lambda r: up(r["rec_id"]))
        voided = {k for k, r in b.items() if clean(r["status"]).lower() == "active" and self.t.ok(r["ticket"])}
        d07 = es.doc("void_register_q3_r2.xml", read_xml, "void")
        for r in d07.tables.get("reinstate", []):
            if self.t.ok(r.get("ticket")):
                voided.discard(up(r.get("rec-id")))
        self.audit_excluded = {up(r["rec_id"]) for r in es.table("audit-scope-letter-fin.pdf", "Excluded")
                               if clean(r.get("status")).lower() == "excluded"}
        self.voided = voided
        withdrawn = {up(r["errata_id"]) for r in es.doc("errata_register_q3_r2.tsv", read_tsv).rows()
                     if up(r.get("field")) == "WITHDRAW" and self.t.ok(r.get("ticket"))}
        rows = (es.doc("errata_register_q3.csv", read_csv).rows() + es.doc("errata_register_tape.xml", read_xml, "erratum").rows("main")
                + es.table("errata-bulletin-q3.docx", "Errata register"))
        rows = [r for r in rows if up(r.get("errata_id")) not in withdrawn and self.t.ok(r.get("ticket"))]
        b = best_by(rows, lambda r: (up(r["rec_id"]), clean(r["field"]).lower()))
        self.errata = {}
        for (rid, field), r in b.items():
            self.errata.setdefault(rid, {})[field] = clean(r["value"])

    def _authority(self):
        es = self.es
        am = es.doc("authority_matrix.xlsx", read_xlsx)
        self.runs = am.rows("runs")
        self.overrides = []
        self.ratified = {}
        for r in am.rows("scope"):
            if clean(r.get("record")).lower() == "override" and self.t.ok(r.get("ticket")):
                self.overrides.append((clean(r["subject"]), up(r["volume_or_version"]), clean(r["prefix"]).rstrip("/")))
        self.ovr_idx = {}
        for f, v, pfx in self.overrides:
            self.ovr_idx.setdefault((v, pfx.strip("/").split("/")[0]), []).append((f, pfx))


def read_ics_holds(es):
    p = es.path("legal_hold_windows.ics")
    if p is None:
        return []
    text = p.read_bytes().decode("utf-8")
    text = re.sub(r"\r?\n[ \t]", "", text)
    rows = []
    cur = None

    def unesc(s):
        out, i = [], 0
        while i < len(s):
            if s[i] == "\\" and i + 1 < len(s):
                out.append({"n": "\n", "N": "\n"}.get(s[i + 1], s[i + 1]))
                i += 2
                continue
            out.append(s[i])
            i += 1
        return "".join(out)

    def ical_time(v):
        v = clean(v)
        return f"{v[0:4]}-{v[4:6]}-{v[6:8]}T{v[9:11]}:{v[11:13]}:{v[13:15]}Z"

    for line in text.splitlines():
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            rows.append({"hold_id": cur.get("UID", ""), "volume": cur.get("X-VOLUME", ""),
                         "prefix": cur.get("X-HOLD-PREFIX", cur.get("X-PREFIX", "")),
                         "from_utc": ical_time(cur["DTSTART"]), "to_utc": ical_time(cur["DTEND"]) if "DTEND" in cur else "",
                         "status": "active" if cur.get("STATUS", "").upper() == "CONFIRMED" else "cancelled",
                         "matter": cur.get("X-MATTER", "")})
            cur = None
        elif cur is not None and ":" in line:
            k, _, v = line.partition(":")
            cur[k.split(";")[0].upper()] = unesc(v)
    return rows


# ------------------------------------------------------------------------------- fixed width
def parse_fixed(p: Path):
    meta = {}
    rows = []
    layout = None
    enc = "utf-8"
    ctl = None
    last = None
    for raw in p.read_bytes().split(b"\n"):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        if not raw:
            continue
        if raw.startswith(b"CTL "):
            ctl = ctl_from_text(raw.decode())
            continue
        if raw.startswith(b"#ENC "):
            enc = raw[5:].decode().strip()
            continue
        if raw.startswith(b"#LAYOUT"):
            layout = []
            for part in raw.decode().split()[2:]:
                name, _, span = part.partition(":")
                a, _, b = span.partition("-")
                layout.append((name, int(a) - 1, int(b)))
            continue
        if raw.startswith(b"#"):
            for kv in re.findall(r"(\w+)=(\S+)", raw.decode("utf-8", "replace")):
                meta[kv[0]] = kv[1]
            continue
        line = raw.decode(enc)
        if line.startswith("+") and last is not None and last.get("_open"):
            last["path"] += line[1:]
            continue
        row = {}
        for name, a, b in layout:
            cell = line[a:b]
            row[name] = cell.rstrip() if name == "path" else cell.strip()
        if "path" in row:
            width = next(b - a for n, a, b in layout if n == "path")
            if len(line[next(a for n, a, b in layout if n == "path"):][:width]) == width and row["path"].endswith("+"):
                row["path"] = row["path"][:-1]
                row["_open"] = True
        rows.append(row)
        last = row
    for r in rows:
        r.pop("_open", None)
    return (ctl, rows, meta)


# ------------------------------------------------------------------------------- records
SIZE_SENT = {"inv_eng01_q3.csv": {"-1"}, "inv_obj01_q3_r2.csv": {"-1"}, "inv_eng02_q3.txt": {"?"},
             "inv_hr01_q3.xlsx": {"9999"}, "arc01_tape_catalog.txt": {"*******"}, "rnd01_cold_listing.pdf": {"-"},
             "inv_ops01_q3.tsv": {"-"}}


class Rec:
    __slots__ = ("rec_id", "file", "kind", "vol", "raw", "raw_to", "size", "na", "time", "sha", "legacy", "lalg",
                 "owner", "fid", "nlink", "batch", "seq", "op", "host", "tsraw", "tskind")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def floor_frac(s):
    s = clean(s)
    return int(Decimal(s).to_integral_value(rounding=ROUND_FLOOR))


def filetime(v):
    return (int(v) - 116444736000000000) // 10**7


def julian(s):
    s = clean(s)
    y, doy = int(s[0:4]), int(s[4:7])
    return (days_from_civil(y, 1, 1) + doy - 1) * DAY + int(s[8:10]) * 3600 + int(s[10:12]) * 60 + int(s[12:14])


def local_stamp(s):
    s = clean(s)
    if re.match(r"^\d{2}\.\d{2}\.\d{4}", s):
        return stamp(int(s[6:10]), int(s[3:5]), int(s[0:2]), int(s[11:13]), int(s[14:16]), int(s[17:19]))
    return stamp(int(s[0:4]), int(s[5:7]), int(s[8:10]), int(s[11:13]), int(s[14:16]), int(s[17:19]))


def parse_log_line(line):
    out = {}
    i = 0
    n = len(line)
    while i < n:
        while i < n and line[i] == " ":
            i += 1
        j = line.find("=", i)
        if j < 0:
            break
        key = line[i:j]
        i = j + 1
        if i < n and line[i] == '"':
            i += 1
            buf = []
            while i < n and line[i] != '"':
                if line[i] == "\\" and i + 1 < n:
                    buf.append(line[i + 1])
                    i += 2
                    continue
                buf.append(line[i])
                i += 1
            i += 1
            out[key] = "".join(buf)
        else:
            k = line.find(" ", i)
            k = n if k < 0 else k
            out[key] = line[i:k]
            i = k
    return out


def read_mbox(p: Path):
    text = p.read_bytes().decode("utf-8")
    msgs = []
    cur = []
    for line in text.split("\n"):
        if line.startswith("From ") and (not cur or cur[-1] == ""):
            if cur:
                msgs.append(cur)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        msgs.append(cur)
    out = []
    for m in msgs:
        hdr = {}
        k = 1
        while k < len(m) and m[k] != "":
            name, _, val = m[k].partition(":")
            hdr[name.strip().lower()] = val.strip()
            k += 1
        body = "\n".join(ln[1:] if ln.startswith(">From ") else ln for ln in m[k + 1:])
        cte = hdr.get("content-transfer-encoding", "8bit").lower()
        if cte == "base64":
            body = base64.b64decode(body.encode()).decode("utf-8")
        elif cte == "quoted-printable":
            body = quopri.decodestring(body.encode()).decode("utf-8")
        hdr["_body"] = body
        out.append(hdr)
    return out


def get(r, *names):
    for n in names:
        if n in r and r[n] not in (None, ""):
            return r[n]
    return None


def mk(file, kind, vol, r, **kw):
    rid = up(kw.pop("rec_id"))
    return Rec(rec_id=rid, file=file, kind=kind, vol=vol, **kw)


def load_records(es, refs):
    recs = []
    for file, vol in VOL_OF.items():
        p = es.path(file)
        if p is None:
            continue
        try:
            recs.extend(load_inventory(es, refs, file, vol, p))
        except Exception as exc:
            warn(f"cannot read {file}: {exc}")
    for file, (vol, _k) in JOURNALS.items():
        p = es.path(file)
        if p is None:
            continue
        try:
            recs.extend(load_journal(es, file, vol, p))
        except Exception as exc:
            warn(f"cannot read {file}: {exc}")
    return recs


def hexfid(v):
    if v in (None, ""):
        return None
    s = clean(v)
    return int(s, 16) if not s.isdigit() or s.startswith("0x") else int(s)


def load_inventory(es, refs, file, vol, p):
    out = []
    S = lambda r, *n: get(r, *n)
    if file == "inv_eng01_q3.csv":
        d = es.doc(file, read_csv)
        for r in d.rows():
            out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["path"], size=("grouped", r["size_bytes"]),
                          time=("filetime", r["mtime_filetime"]), sha=r["sha256"], owner=r["owner_sid"],
                          fid=hexfid(r["file_id"]), nlink=int(clean(r["links"]) or 1), batch=r["batch"]))
        mode = d.meta.get("run_mode")
    elif file == "inv_obj01_q3_r2.csv":
        d = es.doc(file, read_csv)
        for r in d.rows():
            na = clean(r["is_latest"]).lower() == "false" or clean(r["delete_marker"]).lower() == "true"
            out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["key"], size=("grouped", r["size"]),
                          time=("iso", r["last_modified"]), sha=r["sha256"], legacy=r["etag"], lalg="etag",
                          owner=r["owner_id"], nlink=1, batch=r["batch"], na=na))
        mode = d.meta.get("run_mode")
    elif file == "inv_fin01_q3_r2.csv":
        d = es.doc(file, read_csv)
        for r in d.rows():
            out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["path"], size=("unit", r["size"]),
                          time=("iso", r["mtime"]), sha=r["sha256"], owner=r["owner"], fid=hexfid(r["inode"]) if clean(r["inode"]) else None,
                          nlink=int(clean(r["nlink"]) or 1), batch=r["batch"]))
        mode = d.meta.get("run_mode")
    elif file == "inv_fin02_q3.tsv":
        d = es.doc(file, read_tsv, "enc")
        for r in d.rows():
            out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["path"], size=("kib", r["size_kib"]),
                          time=("epoch_s", r["mtime_epoch"]), sha=r["sha256"], legacy=r["sha1"], lalg="sha1",
                          owner=r["owner"], nlink=1, batch=r["batch"]))
        mode = d.meta.get("run_mode")
    elif file == "inv_ops01_q3.tsv":
        d = es.doc(file, read_tsv)
        for r in d.rows():
            out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["path"], size=("kb4de", r["size_kb"]),
                          time=("local", r["mtime_local"]), sha=r["sha256"], owner=r["owner"],
                          fid=int(clean(r["inode"])) if clean(r["inode"]) else None, nlink=int(clean(r["nlink"]) or 1),
                          batch=r["batch"]))
        mode = d.meta.get("run_mode")
    elif file == "inv_mkt01_q3.jsonl":
        d = es.doc(file, read_jsonl)
        for r in d.rows():
            out.append(mk(file, "inv", vol, r, rec_id=r["id"], raw=r["p"], size=("int", r.get("sz")),
                          time=("epoch_s", r["mt"]), sha=r.get("sha256"), legacy=r.get("md5b64"), lalg="md5b64",
                          owner=r["own"], nlink=1, batch=r["batch"]))
        mode = d.meta.get("run_mode")
    elif file == "inv_lab01_q3.jsonl":
        d = es.doc(file, read_jsonl)
        for r in d.rows():
            out.append(mk(file, "inv", vol, r, rec_id=r["rec"], raw=r["path"], size=("unit", r.get("size")),
                          time=("tzq", (r["mtime_local"], r.get("tzq"))), sha=r.get("sha256"), legacy=r.get("md5"),
                          lalg="md5", owner=r["uid"], nlink=1, batch=r["batch"]))
        mode = d.meta.get("run_mode")
    elif file == "inv_eng01_q3_deep.jsonl":
        d = es.doc(file, read_jsonl)
        for r in d.rows():
            out.append(mk(file, "inv", vol, r, rec_id=r["id"], raw=r["path"], size=("int", r.get("bytes")),
                          time=("iso", r["mtime"]), sha=r.get("sha256"), owner=r["owner"], fid=hexfid(r.get("fid")),
                          nlink=int(r.get("links") or 1), batch=r["batch"]))
        mode = d.meta.get("run_mode")
    elif file in ("inv_hr01_q3.xlsx", "inv_mkt01_supplement.xlsx"):
        d = es.doc(file, read_xlsx)
        for r in d.rows():
            if file == "inv_hr01_q3.xlsx":
                out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["path"], size=("hr", r["size"]),
                              time=("excel1900", r["modified"]), sha=r["sha256"], legacy=r["md5"], lalg="md5",
                              owner=r["owner"], nlink=1, batch=r["batch"]))
            else:
                out.append(mk(file, "inv", vol, r, rec_id=r["record"], raw=r["location"], size=("unit", r["size"]),
                              time=("excel1904", r["modified"]), sha=r["sha256"], owner=r["owner"], nlink=1, batch=r["batch"]))
        mode = re.search(r"run_mode=(\S+)", d.meta.get("description", "")).group(1)
    elif file == "inv_fin01_q3.parquet":
        d = es.doc(file, read_parquet)
        for r in d.rows():
            out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["path"], size=("unit", r["size"]),
                          time=("epoch_ns", r["mtime_ns"]), sha=r["sha256"], owner=r["owner"], fid=r["inode"],
                          nlink=int(r["nlink"] or 1), batch=r["batch"]))
        mode = d.meta.get("run_mode")
    elif file in ("inv_eng01_q3_part2.db", "arc01_ltfs_index.db"):
        d = es.doc(file, read_sqlite)
        if file == "inv_eng01_q3_part2.db":
            for r in d.rows("inventory"):
                out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["unc_path"], size=("int", r["bytes"]),
                              time=("epoch_ms", r["mtime_ms"]), sha=r["sha256"], owner=r["owner"], fid=r["fid"],
                              nlink=int(r["nlink"] or 1), batch=r["batch"]))
        else:
            for r in d.rows("ltfs_files"):
                out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["path"], size=("int", r["bytes"]),
                              time=("iso", r["mtime"]), sha=r["sha256"], legacy=r["sha1"], lalg="sha1", owner=r["owner"],
                              fid=hexfid(r["file_id"]), nlink=int(r["nlink"] or 1), batch=r["batch"]))
        mode = d.meta.get("run_mode")
    elif file in ("inv_eng02_q3.txt", "arc01_tape_catalog.txt"):
        ctl, rows, meta = parse_fixed(p)
        d = es.docs.setdefault(file, Doc(file))
        d.ctl = ctl
        for r in rows:
            if file == "inv_eng02_q3.txt":
                out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["path"], size=("grouped", r["size"]),
                              time=("local", r["mtime_local"]), sha=r["sha256"], legacy=r["md5"], lalg="md5",
                              owner=r["owner"], nlink=1, batch=r["batch"]))
            else:
                out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["path"], size=("unit", r["size"]),
                              time=("julian", r["mtime_julian"]), sha=r["sha256"], legacy=r["sha1"], lalg="sha1",
                              owner=r["owner"], nlink=1, batch=r["batch"], na=r.get("flag") == "X"))
        mode = meta.get("run_mode")
    elif file == "inv_rnd01_q3.json":
        d = es.doc(file, read_json)
        for r in d.rows("items"):
            out.append(mk(file, "inv", vol, r, rec_id=r["id"], raw=r["path"], size=("grouped", r.get("bytes")),
                          time=("epoch_ms", r["mtime_ms"]), sha=r.get("sha256"), legacy=r.get("sha1"), lalg="sha1",
                          owner=r["owner"], nlink=1, batch=r["batch"]))
        mode = d.meta.get("export", {}).get("run_mode")
    elif file == "rnd01_cold_listing.pdf":
        d = es.tabular(file)
        for r in es.table(file, "Listing"):
            out.append(mk(file, "inv", vol, r, rec_id=r["rec_id"], raw=r["path"], size=("pdfunit", r["size"]),
                          time=("local", r["modified"]), sha=r["sha256"], legacy=r["sha1"], lalg="sha1", owner=r["owner"],
                          nlink=1, batch=r["batch"]))
        m = re.search(r"run_mode=(\S+)", d.text)
        mode = m.group(1) if m else None
    elif file == "inv_leg01_q3.xml":
        d = es.doc(file, read_xml, "file")
        for r in d.rows("main"):
            sz = get(r, "size", "bytes")
            unit = get(r, "size@unit", "bytes@unit") or "B"
            out.append(mk(file, "inv", vol, r, rec_id=r["id"], raw=r["path"], size=("xml", (sz, unit)),
                          time=("filetime", r["mtime"]), sha=r.get("sha256"), legacy=r.get("md5"), lalg="md5",
                          owner=r["owner"], nlink=1, batch=r["batch"]))
        mode = d.meta.get("run-mode")
    else:
        raise ValueError(file)
    for rec in out:
        rec.tskind = mode
    return out


def load_journal(es, file, vol, p):
    out = []
    if file.endswith(".log"):
        role = "primary"
        v2 = False
        for raw in p.read_bytes().split(b"\n"):
            line = raw.decode("utf-8").rstrip("\r")
            if not line:
                continue
            if line.startswith("#"):
                m = re.search(r"role=(\S+)", line)
                if m:
                    role = m.group(1)
                if line.startswith("# FORMAT v2"):
                    v2 = True
                continue
            r = parse_log_line(line)
            dig_alg = "sha1" if "sha1" in r else "md5b64" if "md5b64" in r else None
            out.append(mk(file, "jrn", vol, r, rec_id=r["id"], raw=r["path"], raw_to=r.get("to"),
                          size=("kb4de" if file == "journal_ops01_q3.log" else "int", get(r, "sz" if v2 else "size")),
                          sha=get(r, "h256" if v2 else "sha256"), legacy=r.get(dig_alg) if dig_alg else None, lalg=dig_alg,
                          owner=get(r, "own" if v2 else "owner"), batch=r.get("batch"), seq=int(r["seq"]), op=r["op"],
                          host=r.get("host"), tsraw=r["ts"], tskind={"journal_fin01_q3.log": "epoch_frac",
                                                                    "journal_ops01_q3.log": "local"}.get(file, "iso"),
                          nlink=1))
        for rec in out:
            rec.na = role
    elif file == "journal_eng02_q3.csv":
        for r in es.doc(file, read_csv).rows():
            out.append(mk(file, "jrn", vol, r, rec_id=r["rec_id"], raw=r["path"], raw_to=r["new_path"] or None,
                          size=("int", r["size"]), sha=r["sha256"], legacy=r["md5"], lalg="md5", owner=r["owner"],
                          batch=r["batch"], seq=int(r["seq"]), op=r["op"], tsraw=r["filetime"], tskind="filetime", nlink=1))
    elif file == "journal_hr01_q3.jsonl":
        for r in es.doc(file, read_jsonl).rows():
            out.append(mk(file, "jrn", vol, r, rec_id=r["id"], raw=r["path"], raw_to=r.get("to"), size=("int", r.get("size")),
                          sha=r.get("sha256"), legacy=r.get("md5"), lalg="md5", owner=r.get("owner"), batch=r["batch"],
                          seq=int(r["seq"]), op=r["op"], tsraw=r["at"], tskind="iso", nlink=1))
    elif file == "journal_obj01_events.jsonl":
        for r in es.doc(file, read_jsonl).rows():
            o = r["s3"]["object"]
            op = "CREATE" if r["eventName"].startswith("ObjectCreated") else "DELETE"
            out.append(mk(file, "jrn", vol, r, rec_id=r["id"], raw=f"s3://{r['s3']['bucket']['name']}/{o['key']}",
                          size=("int", o.get("size")), sha=o.get("sha256"), legacy=o.get("eTag"), lalg="etag",
                          owner=(r.get("userIdentity") or {}).get("canonicalId"), batch=r.get("batch"),
                          seq=int(o["sequencer"], 16), op=op, tsraw=r["eventTime"], tskind="iso", nlink=1))
    elif file == "journal_fin02_q3.xml":
        for r in es.doc(file, read_xml, "event").rows("main"):
            out.append(mk(file, "jrn", vol, r, rec_id=r["id"], raw=get(r, "path", "source"), raw_to=r.get("to"),
                          size=("grouped", r.get("size")), sha=r.get("sha256"), legacy=r.get("sha1"), lalg="sha1",
                          owner=r.get("owner"), batch=r.get("batch"), seq=int(r["seq"]), op=r["op"], tsraw=r["at"],
                          tskind="epoch_ms", nlink=1))
    elif file == "journal_rnd01_q3.json":
        for r in es.doc(file, read_json).rows("events"):
            out.append(mk(file, "jrn", vol, r, rec_id=r["id"], raw=r["path"], raw_to=r.get("to"), size=("grouped", r.get("bytes")),
                          sha=r.get("sha256"), legacy=r.get("sha1"), lalg="sha1", owner=r.get("owner"), batch=r.get("batch"),
                          seq=int(r["seq"]), op=r["op"], tsraw=r["at"], tskind="iso", nlink=1))
    elif file == "journal_leg01_notifications.mbox":
        for h in read_mbox(p):
            body = {}
            for ln in h["_body"].split("\n"):
                k, _, v = ln.partition(": ")
                if k in ("Path", "To"):
                    body[k] = v
            subj = h["subject"].split()
            out.append(mk(file, "jrn", vol, h, rec_id=subj[2], raw=body.get("Path"), raw_to=body.get("To"),
                          size=("int", h.get("x-size") or h.get("x-size-bytes")), sha=h.get("x-sha256"), legacy=h.get("x-md5"),
                          lalg="md5", owner=h.get("x-owner") or h.get("x-principal"), batch=h.get("x-batch"),
                          seq=int(h["x-seq"]), op=subj[1], tsraw=h["date"], tskind="rfc2822", nlink=1))
    for rec in out:
        if rec.na is None:
            rec.na = "primary"
    return out


# ------------------------------------------------------------------------------- engine
def pct_decode(key):
    out = bytearray()
    i = 0
    while i < len(key):
        if key[i] == "%" and i + 2 < len(key) + 1 and re.fullmatch(r"[0-9A-Fa-f]{2}", key[i + 1:i + 3] or ""):
            out.append(int(key[i + 1:i + 3], 16))
            i += 3
        else:
            out += key[i].encode("utf-8")
            i += 1
    return out.decode("utf-8")


class Ctx:
    def __init__(self, refs, cfg, tickets):
        self.refs = refs
        self.cfg = cfg
        self.t = tickets
        self.we = parse_iso(cfg["window.end"])
        self.ws = parse_iso(cfg["window.start"])

    def case(self, vol):
        info = self.refs.vol_info.get(vol, {})
        fs = clean(info.get("fs_type")).lower()
        if fs == "apfs":
            return clean(self.cfg.get(f"vol.{vol}.case", "sensitive")).lower()
        return FS_CASE.get(fs, "sensitive")

    def zone(self, vol):
        z = self.cfg.get(f"vol.{vol}.zone")
        if z:
            return z
        host = clean(self.refs.vol_info.get(vol, {}).get("host")).lower()
        return self.refs.host_zone.get(host, "")

    def path(self, raw):
        if raw is None:
            return None, None
        raw = str(raw)
        if raw.startswith("s3://"):
            bucket, _, key = raw[5:].partition("/")
            return "OBJ01", unicodedata.normalize("NFC", f"/{bucket}/{pct_decode(key)}")
        norm = raw.replace("\\", "/") if raw.startswith("\\\\") else raw
        ci_style = not norm.startswith("/") or norm.startswith("//")
        best = None
        j = norm.find("/")
        while j >= 0:
            cand = norm[: j + 1]
            key = cand.lower() if ci_style else cand
            if key in self.refs.alias:
                best = (j + 1, self.refs.alias[key])
            j = norm.find("/", j + 1)
        if best is None:
            return None, None
        cut, row = best
        if clean(row.get("status")).lower() != "active":
            return None, None
        vol = clean(row["volume"])
        if vol.lower().startswith("serial:"):
            vol = self.refs.serial.get(up(vol[7:]))
            if vol is None:
                return None, None
        vol = vol.upper()
        segs = []
        for s in norm[cut:].split("/"):
            if s in ("", "."):
                continue
            if s == "..":
                if not segs:
                    return None, None
                segs.pop()
                continue
            segs.append(unicodedata.normalize("NFC", s))
        full = clean(row["prefix"]) + "/".join(segs)
        if self.case(vol) == "insensitive":
            low = full.lower()
            for pfx in self.refs.cs.get(vol, ()):
                if low.startswith(pfx):
                    return vol, (low[: len(pfx)] + full[len(pfx):]).rstrip("/")
            return vol, low.rstrip("/")
        return vol, full.rstrip("/")

    def size(self, rec):
        dial, v = rec.size
        if dial == "xml":
            sz, unit = v
            if sz in (None, ""):
                return None
            return exact_bytes(sz, 1024) if clean(unit) == "KiB" else int_grouped(sz)
        if v is None or (isinstance(v, str) and clean(v) == ""):
            return None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if rec.file in SIZE_SENT and str(int(v)) in SIZE_SENT[rec.file]:
                return None
            if dial in ("unit", "hr", "pdfunit"):
                b = self.refs.batch.get(up(rec.batch))
                return None if b is None or b[0] is None else exact_bytes(repr(v) if isinstance(v, float) else str(v), b[0])
            return int(v)
        s = clean(v)
        if s in SIZE_SENT.get(rec.file, ()):
            return None
        if s == "N/A":
            return "NA"
        if dial == "kb4de":
            return kb_de(s)
        if dial == "kib":
            return 0 if s.lstrip("-") == "0" else exact_bytes(s, 1024)
        if dial in ("unit", "hr", "pdfunit"):
            b = self.refs.batch.get(up(rec.batch))
            if b is None or b[0] is None:
                return None
            return exact_bytes(s.replace("\u2009", "").replace("\u202f", ""), b[0])
        return int_grouped(s)

    def mtime(self, rec):
        kind, v = rec.time
        zone = self.zone(rec.vol)
        if kind == "filetime":
            return filetime(v)
        if kind == "epoch_ms":
            return int(v) // 1000
        if kind == "epoch_ns":
            return int(v) // 10**9
        if kind == "epoch_s":
            return int(v)
        if kind == "iso":
            return parse_iso(v)
        if kind == "julian":
            return julian(v)
        if kind == "local":
            return self.refs.zones.to_utc(zone, local_stamp(v))
        if kind == "tzq":
            loc, q = v
            base = local_stamp(loc)
            return base - int(q) * 900 if q is not None else self.refs.zones.to_utc(zone, base)
        if kind in ("excel1900", "excel1904"):
            if v in (None, ""):
                return None
            num = v if isinstance(v, (int, float)) else float(clean(v))
            if kind == "excel1900":
                if num in (0, 60):
                    return None
                return self.refs.zones.to_utc(zone, stamp(1899, 12, 30) + serial_seconds(num))
            return stamp(1904, 1, 1) + serial_seconds(num)
        raise ValueError(kind)

    def ts(self, rec):
        v, kind = rec.tsraw, rec.tskind
        if kind == "iso":
            t = parse_iso(v)
        elif kind == "epoch_frac":
            t = floor_frac(v)
        elif kind == "epoch_ms":
            t = int(clean(v)) // 1000
        elif kind == "filetime":
            t = filetime(clean(v))
        elif kind == "rfc2822":
            t = parse_rfc2822(v)
        elif kind == "local":
            t = self.refs.zones.to_utc(self.zone(rec.vol), local_stamp(v))
        else:
            raise ValueError(kind)
        if rec.file in HOST_JOURNALS and rec.host:
            for frm, to, skew in self.refs.incidents.get(clean(rec.host).lower(), ()):
                if frm <= t < to:
                    t -= skew
                    break
        return t

    def digest(self, rec):
        sha = clean(rec.sha)
        if sha:
            sha = sha.lower()
            return None if set(sha) == {"0"} else sha
        leg = clean(rec.legacy)
        if not leg:
            return None
        if rec.lalg == "md5b64":
            leg = base64.b64decode(leg).hex()
        leg = leg.strip('"').lower()
        if set(leg.replace("-", "")) <= {"0"}:
            return None
        return self.refs.xwalk.get(XWALK_PART.get(rec.vol, ""), {}).get(leg)


def under(path, prefix):
    p = prefix.rstrip("/")
    return path == p or path.startswith(p + "/")


def evaluate(refs, recs, cfg, tickets, prior, snapshots, modes):
    ctx = Ctx(refs, cfg, tickets)
    we, ws = ctx.we, ctx.ws
    out = {}
    valid = []
    events = []
    gap = refs.gap
    for rec in recs:
        vol, path = ctx.path(rec.raw)
        if vol is not None and vol != rec.vol:
            vol, path = None, None
        reason = None
        errata = refs.errata.get(rec.rec_id, {})
        if rec.kind == "inv":
            near = refs.ovr_idx.get((rec.vol, path.strip("/").split("/")[0]), ()) if path else ()
            if modes.get(rec.file) not in ("full", "continuation"):
                if not (path and any(f == rec.file and under(path, pfx) for f, pfx in near)):
                    reason = "OUT_OF_AUTHORITY"
            elif path and any(f != rec.file and under(path, pfx) for f, pfx in near):
                reason = "SUPERSEDED_SCOPE"
        elif rec.na == "replica":
            if gap is None or not (gap[0] <= rec.seq <= gap[1]):
                reason = "OUT_OF_AUTHORITY"
        if reason is None and rec.rec_id in refs.voided:
            reason = "VOIDED"
        size = None
        if rec.kind == "inv" or rec.op in ("CREATE", "MODIFY"):
            try:
                size = ctx.size(rec) if rec.size is not None else None
            except Exception as exc:
                warn(f"size unreadable on {rec.rec_id}: {exc}")
                size = None
        if reason is None and (rec.kind == "inv" and (rec.na is True or size == "NA" or not_a_file(rec.vol, path, rec.raw))):
            reason = "NOT_A_FILE"
        t = None
        if rec.kind == "jrn":
            t = ctx.ts(rec)
            if reason is None:
                snap = snapshots.get(rec.vol)
                if snap is None or t < snap:
                    reason = "STALE_EVENT"
                elif t >= we:
                    reason = "DEFERRED_EVENT"
        newpath = None
        if rec.kind == "jrn" and rec.op == "RENAME":
            v2, p2 = ctx.path(rec.raw_to)
            newpath = p2 if v2 == vol else None
        needs = ("size", "hash", "owner") if rec.kind == "inv" or rec.op == "CREATE" else (("size", "hash") if rec.op == "MODIFY" else ())
        if reason is None and (path is None or (rec.op == "RENAME" and newpath is None)):
            reason = "PATH_UNRESOLVED"
        if "bytes" in errata:
            size = int_grouped(errata["bytes"])
        if size == "NA":
            size = None
        if reason is None and "size" in needs and size is None:
            reason = "SIZE_UNKNOWN"
        sha = errata["sha256"].lower() if "sha256" in errata else (ctx.digest(rec) if "hash" in needs else None)
        if reason is None and "hash" in needs and sha is None:
            reason = "HASH_UNRESOLVED"
        owner = errata["owner"] if "owner" in errata else (refs.owner(rec.owner, we) if "owner" in needs else None)
        if reason is None and "owner" in needs and owner is None:
            reason = "OWNER_UNRESOLVED"
        if reason:
            out[rec.rec_id] = reason
            continue
        if rec.kind == "inv":
            mt = ctx.mtime(rec)
            if mt is None:
                b = refs.batch.get(up(rec.batch))
                mt = b[1] if b else 0
            if "mtime" in errata:
                mt = parse_iso(errata["mtime"])
            valid.append((rec, vol, path, size, sha, owner, mt))
        else:
            events.append((rec, vol, path, newpath, size, sha, owner, t))
    state = {}
    for item in valid:
        rec, vol, path = item[0], item[1], item[2]
        b = refs.batch.get(up(rec.batch))
        key_rank = (b[1] if b else -10**12, rec.rec_id)
        cur = state.get((vol, path))
        if cur is None:
            state[(vol, path)] = (key_rank, item)
        elif key_rank > cur[0]:
            out[cur[1][0].rec_id] = "DUPLICATE_PATH"
            state[(vol, path)] = (key_rank, item)
        else:
            out[rec.rec_id] = "DUPLICATE_PATH"
    live = {}
    for key, (_k, (rec, vol, path, size, sha, owner, mt)) in state.items():
        fid = refs.ltfs_fid.get(path) if vol == "ARC01" else rec.fid
        nl = refs.ltfs_nlink.get(path, 1) if vol == "ARC01" else rec.nlink
        live[key] = {"vol": vol, "path": path, "sha": sha, "bytes": size, "mtime": mt, "owner": owner,
                     "origin": rec.rec_id, "fid": fid, "nlink": nl or 1}
    deleted = {}
    events.sort(key=lambda e: (e[1], e[0].seq))
    for rec, vol, path, newpath, size, sha, owner, t in events:
        key = (vol, path)
        op = rec.op
        if op == "CREATE":
            if key in live:
                out[live[key]["origin"]] = "REPLACED"
            live[key] = {"vol": vol, "path": path, "sha": sha, "bytes": size, "mtime": t, "owner": owner,
                         "origin": rec.rec_id, "fid": None, "nlink": 1}
        elif op == "MODIFY":
            if key not in live:
                out[rec.rec_id] = "ORPHAN_EVENT"
                continue
            live[key].update(sha=sha, bytes=size, mtime=t)
        elif op == "RENAME":
            nkey = (vol, newpath)
            if key not in live or nkey == key:
                out[rec.rec_id] = "ORPHAN_EVENT"
                continue
            e = live.pop(key)
            if nkey in live:
                out[live[nkey]["origin"]] = "REPLACED"
            e["path"] = newpath
            live[nkey] = e
        elif op == "DELETE":
            if key not in live:
                out[rec.rec_id] = "ORPHAN_EVENT"
                continue
            e = live.pop(key)
            out[e["origin"]] = "DELETED"
            deleted.setdefault(key, []).append(e)
        elif op == "RESTORE":
            if key in live or not deleted.get(key):
                out[rec.rec_id] = "ORPHAN_EVENT"
                continue
            e = deleted[key].pop()
            out.pop(e["origin"], None)
            live[key] = e
    groups = {}
    for key, e in live.items():
        if e["fid"] is not None and e["nlink"] > 1:
            groups.setdefault((e["vol"], e["fid"]), []).append(key)
    for keys in groups.values():
        if len(keys) < 2:
            continue
        keys.sort(key=lambda k: k[1])
        for k in keys[1:]:
            out[live[k]["origin"]] = "HARDLINK_ALIAS"
            del live[k]
    holds = refs.active_holds(ws, we)
    sub = {}
    for k, v in cfg.items():
        if k.startswith("subtree."):
            body, _, flag = k.rpartition(".")
            vol, _, pfx = body[8:].partition(":")
            sub.setdefault((flag, vol, pfx.strip("/").split("/")[0]), []).append((pfx, v))

    def flag(name, vol, path):
        best = None
        for pfx, v in sub.get((name, vol, path.strip("/").split("/")[0]), ()):
            if under(path, pfx) and (best is None or len(pfx) > len(best[0])):
                best = (pfx, v)
        return bool(best and best[1])

    entries = []
    for key in sorted(live):
        e = live[key]
        name = e["path"].rsplit("/", 1)[-1]
        ci = ctx.case(e["vol"]) == "insensitive"
        cls = refs.matcher.classify(e["vol"], e["path"], refs.family(name), ci)
        purge_after, archive_after = refs.classes.get(cls, (None, None))
        age = (we - e["mtime"]) // DAY
        held = any(under(e["path"], p) for p in holds.get((e["vol"], e["path"].strip("/").split("/")[0]), ()))
        if (cfg.get("purge.enabled") is True and purge_after is not None and age > purge_after and not held
                and e["vol"] not in NO_PURGE and not flag("purge_exempt", e["vol"], e["path"])):
            out[e["origin"]] = "PURGED"
            continue
        action = "archive" if archive_after is not None and age >= archive_after and not flag("archive_exempt", e["vol"], e["path"]) else "keep"
        entries.append(dict(e, cls=cls, action=action))
    plive = prior["live"]
    new_keys = sorted((e["vol"], e["path"]) for e in entries if (e["vol"], e["path"]) not in plive)
    ids = {k: prior["next_id"] + i for i, k in enumerate(new_keys)}
    for e in entries:
        k = (e["vol"], e["path"])
        e["entry_id"] = plive.get(k, ids.get(k))
    bs = int(cfg["store.block_size"])
    seen = set()
    new_store = 0
    for e in entries:
        if e["sha"] in seen:
            continue
        seen.add(e["sha"])
        if e["sha"] in refs.stored:
            continue
        new_store += -(-e["bytes"] // bs) * bs
    keys = {(e["vol"], e["path"]) for e in entries}
    carried = sum(1 for k in keys if k in plive)
    vols = {}
    for e in entries:
        v = vols.setdefault(e["vol"], [0, 0])
        v[0] += 1
        v[1] += e["bytes"]
    exc = {}
    for r in out.values():
        exc[r] = exc.get(r, 0) + 1
    ledger = {"opening": dict(prior["opening"]),
              "movement": {"carried": carried, "new": len(entries) - carried, "retired": sum(1 for k in plive if k not in keys)},
              "closing": {"entries": len(entries), "logical_bytes": sum(e["bytes"] for e in entries),
                          "store_bytes": prior["opening"]["store_bytes"] + new_store,
                          "id_hash_total": sum(e["entry_id"] for e in entries) % 1000000007},
              "volumes": [{"volume": v, "entries": c[0], "logical_bytes": c[1]} for v, c in sorted(vols.items())],
              "exceptions": dict(sorted(exc.items()))}
    return entries, out, ledger


NOT_FILE_RULES = [
    (("ENG01", "ENG02", "LEG01"), lambda n, p: n == "desktop.ini"),
    (("MKT01",), lambda n, p: n == ".ds_store"),
    (("LAB01",), lambda n, p: n.startswith("._")),
    (("OBJ01",), lambda n, p: "/_temporary/" in p),
    (("HR01", "OPS01"), lambda n, p: "/lost+found/" in p),
    (("ARC01",), lambda n, p: n.endswith(".spanned")),
    (("RND01",), lambda n, p: n.endswith(".hsmstub")),
]


def not_a_file(vol, path, raw=None):
    if not path:
        if not raw:
            return False
        path = str(raw).replace("\\", "/")
    name = path.rsplit("/", 1)[-1]
    for vols, test in NOT_FILE_RULES:
        if vol in vols and test(name.lower() if vol in ("MKT01",) else name, path):
            return True
    return False


# ------------------------------------------------------------------------------- retention matcher
def glob_re(pat):
    out = []
    i = 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pat.startswith("/**", i) and i + 3 == len(pat):
            out.append("(?:/.*)?")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        elif pat[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pat[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pat[i]))
            i += 1
    return "".join(out) + r"\Z"


class Matcher:
    def __init__(self, rules):
        self.glob = []
        self.top = {}
        for order, (scope, pat, cls) in enumerate(rules):
            if pat.startswith("family:"):
                item = (order, scope, cls, "family", pat[7:].upper(), None, None, None)
                self.glob.append(item)
                continue
            dir_only = pat.endswith("/")
            body = pat[:-1] if dir_only else pat
            anchored = "/" in body
            body = body.lstrip("/")
            item = (order, scope, cls, "glob", re.compile(glob_re(body)), re.compile(glob_re(body.lower())), anchored, dir_only)
            first = body.split("/", 1)[0] if anchored else None
            if first and not any(c in first for c in "*?"):
                self.top.setdefault(first, []).append(item)
            else:
                self.glob.append(item)

    def classify(self, vol, path, family, ci):
        segs = path.strip("/").split("/")
        rel = "/".join(segs)
        cls = "standard"
        for item in sorted(self.glob + self.top.get(segs[0], []), key=lambda x: x[0]):
            _o, scope, c, kind, a, b, anchored, dir_only = item
            if scope != "*" and scope != vol:
                continue
            if kind == "family":
                if family is not None and family == a:
                    cls = c
                continue
            rx = b if ci else a
            if dir_only:
                dirs = segs[:-1]
                hit = any(rx.match("/".join(dirs[:k])) for k in range(1, len(dirs) + 1)) if anchored else any(rx.match(d) for d in dirs)
            else:
                hit = bool(rx.match(rel if anchored else segs[-1]))
            if hit:
                cls = c
        return cls


# ------------------------------------------------------------------------------- orchestration
def chain_order(es, opening):
    ctls = {}
    for f in ALL_FILES:
        try:
            c = ctl_of(es, f)
        except Exception as exc:
            warn(f"cannot read control record of {f}: {exc}")
            c = None
        if c:
            ctls[f] = c
    by_prev = {c[1]: f for f, c in ctls.items()}
    out = []
    cur = opening
    seen = set()
    while cur in by_prev and by_prev[cur] not in seen:
        f = by_prev[cur]
        seen.add(f)
        out.append({"file": f, "ctl_id": ctls[f][0], "rows": ctls[f][2]})
        cur = ctls[f][0]
    for f in sorted(set(ctls) - seen):
        out.append({"file": f, "ctl_id": ctls[f][0], "rows": ctls[f][2]})
    return out


def run(data: Path, out: Path):
    es = Estate(data)
    tickets = Tickets(es)
    layers = config_rows(es)
    pre = resolve_config(es, tickets, "prod", {k: v for k, v in layers.items() if k < 40}, set())
    tickets.window_end = parse_iso(pre["window.end"])
    revoked = {up(r["override_id"]) for r in es.doc("site-policy-v2.yaml", read_yaml).rows("revocations")
               if tickets.ok(r.get("ticket"))}
    cfgs = {p: resolve_config(es, tickets, p, layers, revoked) for p in ("prod", "dev")}
    tickets.window_end = parse_iso(cfgs["prod"]["window.end"])
    refs = Refs(es, tickets)
    m = re.search(r"sequence numbers (\d+) through (\d+)", es.tabular("ops-runbook.md").text or "")
    refs.gap = (int(m.group(1)), int(m.group(2))) if m else None
    recs = load_records(es, refs)
    fin = {r.rec_id for r in recs if r.vol in ("FIN01", "FIN02")}
    refs.voided |= refs.audit_excluded & fin
    modes = {r.file: r.tskind for r in recs if r.kind == "inv"}
    snapshots = {}
    for row in refs.runs:
        f = clean(row.get("file"))
        if (f in VOL_OF and modes.get(f) == "full" and clean(row.get("kind")).lower() == "full"
                and clean(row.get("status")).lower() == "complete" and not clean(row.get("superseded_by"))):
            snapshots[VOL_OF[f]] = parse_iso(row["completed_utc"])
    pm = es.doc("estate_manifest_q2.parquet", read_parquet)
    prior = {"live": {}, "next_id": int(pm.meta.get("next_entry_id", 1)),
             "opening": {"entries": int(pm.meta.get("closing_entries", 0)),
                         "logical_bytes": int(pm.meta.get("closing_logical_bytes", 0)),
                         "store_bytes": int(pm.meta.get("closing_store_bytes", 0))}}
    for r in pm.rows():
        if clean(r.get("status")).lower() == "live" and clean(r.get("volume")) in refs.vol_info:
            prior["live"][(clean(r["volume"]), r["path"])] = int(r["entry_id"])
    ctxp = Ctx(refs, cfgs["prod"], tickets)
    refs.ltfs_fid = {}
    refs.ltfs_nlink = {}
    for r in recs:
        if r.file == "arc01_ltfs_index.db":
            v, pth = ctxp.path(r.raw)
            if pth is not None and r.fid is not None:
                refs.ltfs_fid[pth] = r.fid
                refs.ltfs_nlink[pth] = r.nlink
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for prof in ("prod", "dev"):
        entries, exc, ledger = evaluate(refs, recs, cfgs[prof], tickets, prior, snapshots, modes)
        results[prof] = (entries, exc, ledger)
        doc = {"profile": prof, "config": cfgs[prof], "control": ledger["closing"],
               "entries": [{"entry_id": e["entry_id"], "volume": e["vol"], "path": e["path"], "sha256": e["sha"],
                            "bytes": e["bytes"], "mtime": iso(e["mtime"]), "owner": e["owner"], "class": e["cls"],
                            "action": e["action"], "origin": e["origin"]} for e in entries]}
        (out / f"profile_{prof}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (out / "config.json").write_text(json.dumps(cfgs["prod"], ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    vr = {p: [{"rec_id": k, "reason": v} for k, v in sorted(results[p][1].items())] for p in ("prod", "dev")}
    (out / "validation_report.json").write_text(json.dumps(vr, separators=(",", ":")) + "\n", encoding="utf-8")
    opening_ctl = pm.meta.get("closing_ctl_id", "")
    summary = {"opening_ctl_id": opening_ctl, "chain": chain_order(es, opening_ctl),
               "profiles": {p: results[p][2] for p in ("prod", "dev")}}
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    if es.missing:
        warn(f"{len(es.missing)} input file(s) missing: " + ", ".join(es.missing))
    print("ok")


def cmd_report(args):
    digest = hashlib.sha256(Path(args.config).read_bytes()).hexdigest()
    report = {"ok": True, "tool": "estatectl", "config_sha256": digest, "commands": json.loads(args.commands)}
    Path(args.out).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print("reported")


def main():
    ap = argparse.ArgumentParser(prog="estatectl")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--data", required=True)
    r.add_argument("--out", required=True)
    e = sub.add_parser("export-report")
    e.add_argument("--config", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--commands", required=True)
    a = ap.parse_args()
    if a.cmd == "run":
        run(Path(a.data), Path(a.out))
    else:
        cmd_report(a)


if __name__ == "__main__":
    main()
'''


def extract():
    if TOOL.exists():
        shutil.rmtree(TOOL)
    TOOL.mkdir(parents=True)
    if not (DATA / "tool.zip").is_file():
        print("solve: /app/data/tool.zip is missing; rebuilding the tool without its shipped files", file=sys.stderr)
        (TOOL / "estatectl").mkdir()
        return
    with zipfile.ZipFile(DATA / "tool.zip") as zf:
        for info in zf.infolist():
            name = info.filename
            if name.startswith("/") or ".." in Path(name).parts:
                raise SystemExit(f"unsafe member {name}")
            dest = TOOL / name
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info))


def run(*args):
    argv = ["python3", "estatectl/estatectl.py", *args]
    proc = subprocess.run(argv, cwd=TOOL, capture_output=True, text=True, check=False)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")
    entry = {"argv": argv, "returncode": proc.returncode, "stdout": proc.stdout.strip()}
    if proc.returncode != 0:
        raise SystemExit(f"command failed: {entry}")
    return entry


def package():
    target = OUT / "tool.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in TOOL.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            info = zipfile.ZipInfo(path.relative_to(TOOL).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())


def main():
    extract()
    (TOOL / "estatectl" / "estatectl.py").write_text(REPAIRED, encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    commands = [run("run", "--data", str(DATA), "--out", str(OUT))]
    report_cmd = ["export-report", "--config", str(OUT / "config.json"), "--out", str(OUT / "report.json")]
    planned = commands + [{"argv": ["python3", "estatectl/estatectl.py", *report_cmd, "--commands", "<this list>"],
                           "returncode": 0, "stdout": "reported"}]
    run(*report_cmd, "--commands", json.dumps(planned))
    package()


if __name__ == "__main__":
    main()
