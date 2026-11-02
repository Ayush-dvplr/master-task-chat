#!/usr/bin/env python3
"""Corvid Cloud Platform - monthly SLA service-credit close.

Usage: transform.py [DATA_DIR] [OUT_DIR] [--prior PRIOR_OUT_DIR]
"""
from __future__ import annotations

import calendar
import csv
import datetime as dt
import hashlib
import io
import itertools
import json
import logging
import os
import re
import sqlite3
import sys
import warnings
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN

UTC = dt.timezone.utc

logging.getLogger("pypdf").setLevel(logging.CRITICAL)
logging.getLogger("pdfminer").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------- helpers ----

BLANKS = "\u00a0\u200b\ufeff\u2007\u202f\u2009\u2008 \t"
ID_DIGITS = {"SUB": 6, "ACC": 5, "INS": 7}


def clean_text(v) -> str:
    """Text of a raw cell with surrounding/embedded invisible blanks removed."""
    if v is None:
        return ""
    if not isinstance(v, str):
        if isinstance(v, float) and v == int(v):
            return str(int(v))
        return str(v)
    return v.replace("\ufeff", "").replace("\u200b", "").strip(BLANKS).strip()


def norm_ident(raw) -> str | None:
    """Canonical identifier (PREFIX-digits) or None when malformed/empty."""
    if raw is None:
        return ""
    s = raw if isinstance(raw, str) else str(raw)
    s = s.replace("\ufeff", "").replace("\u200b", "")
    s = "".join(ch for ch in s if ch not in "\u00a0\u2007\u202f\u2009\u2008 \t\r\n")
    if s == "":
        return ""
    if any(ord(ch) > 127 for ch in s):
        return None
    m = re.fullmatch(r"([A-Za-z]+)[-_]?([0-9]+)", s)
    if not m:
        return None
    pfx = m.group(1).upper()
    digits = m.group(2)
    want = ID_DIGITS.get(pfx)
    if want is not None and len(digits) != want:
        return None
    return f"{pfx}-{digits}"


def ctrl_digits(raw) -> int:
    """Integer formed by the ASCII digits of a control field as written."""
    if raw is None:
        return 0
    s = clean_text(raw) if not isinstance(raw, str) else raw
    ds = "".join(ch for ch in s if ch in "0123456789")
    return int(ds) if ds else 0


NUM_GROUP = "\u00a0\u202f\u2009\u2008\u2007 '"


def parse_count(v):
    """Integer count; None when the value marks a placeholder."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return None if v == -1 else v
    if isinstance(v, float):
        if v != v:
            return None
        iv = int(round(v))
        return None if iv == -1 else iv
    s = clean_text(v)
    if s == "" or s.upper() in ("N/A", "NA", "NAN", "NONE", "NULL"):
        return None
    s = "".join(ch for ch in s if ch not in NUM_GROUP)
    mult = 1
    if s and s[-1] in "kK":
        s = s[:-1]
        mult = 1000
    s = s.replace(",", ".")
    try:
        d = Decimal(s)
    except Exception:
        return None
    d = d * mult
    if d == -1:
        return None
    return int(d.to_integral_value(rounding=ROUND_HALF_EVEN))


def parse_decimal(v):
    """Decimal value or None."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return Decimal(str(v))
    s = clean_text(v)
    if s == "" or s.upper() in ("N/A", "NA", "NONE", "NULL"):
        return None
    s = "".join(ch for ch in s if ch not in NUM_GROUP)
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return None


def round_half_even(d: Decimal) -> int:
    return int(d.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


# ------------------------------------------------------------- time parsing --

EPOCH_1900 = dt.datetime(1899, 12, 30, tzinfo=UTC)
EPOCH_1904 = dt.datetime(1904, 1, 1, tzinfo=UTC)


def parse_date(v):
    """Calendar date -> datetime.date, None when empty/open-ended/invalid."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (EPOCH_1900 + dt.timedelta(days=float(v))).date()
    s = clean_text(v)
    if s == "" or s in ("9999-12-31", "99991231", "31.12.9999"):
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if m:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.fullmatch(r"(\d{8})", s)
    if m:
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    inst = parse_instant(s)
    if inst is not None:
        return inst.date()
    return None


def parse_instant(v, serial_epoch=EPOCH_1900, tz=None):
    """Instant -> aware UTC datetime, or None."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        if v.tzinfo is None:
            if tz is not None:
                return local_to_utc(v, tz)
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day, tzinfo=UTC)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return _numeric_instant(v, serial_epoch)
    s = clean_text(v)
    if s == "":
        return None
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return _numeric_instant(float(s) if "." in s else int(s), serial_epoch)
    s2 = s.replace("Z", "+00:00").replace("z", "+00:00")
    s2 = s2.replace(" ", "T", 1) if re.fullmatch(r"\d{4}-\d{2}-\d{2} .*", s2) else s2
    try:
        d = dt.datetime.fromisoformat(s2)
    except Exception:
        m = re.fullmatch(r"(\d{8})T?(\d{6})Z?", s)
        if m:
            d = dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        else:
            return None
    if d.tzinfo is None:
        if tz is not None:
            return local_to_utc(d, tz)
        return d.replace(tzinfo=UTC)
    return d.astimezone(UTC)


def _numeric_instant(n, serial_epoch):
    v = float(n)
    an = abs(v)
    if an >= 1e12:  # epoch milliseconds
        return dt.datetime.fromtimestamp(v / 1000.0, UTC)
    if an >= 1e9:  # epoch seconds
        return dt.datetime.fromtimestamp(v, UTC)
    # spreadsheet serial day numbers carry rounding noise below a second
    return serial_epoch + dt.timedelta(seconds=round(v * 86400))


# --------------------------------------------------------------- time zones --


class Zone:
    """Zone with a standard offset and the EU daylight-saving rule."""

    def __init__(self, std_offset_min: int, dst_rule: str):
        self.std = dt.timedelta(minutes=std_offset_min)
        self.dst = dst_rule.upper() == "EU"
        self._cache = {}

    def _transitions(self, year: int):
        if year in self._cache:
            return self._cache[year]
        start = _last_sunday(year, 3).replace(tzinfo=UTC) + dt.timedelta(hours=1)
        end = _last_sunday(year, 10).replace(tzinfo=UTC) + dt.timedelta(hours=1)
        self._cache[year] = (start, end)
        return self._cache[year]

    def offset_at_utc(self, when: dt.datetime) -> dt.timedelta:
        if not self.dst:
            return self.std
        start, end = self._transitions(when.year)
        if start <= when < end:
            return self.std + dt.timedelta(hours=1)
        return self.std

    def to_utc(self, naive_local: dt.datetime) -> dt.datetime:
        """Local wall clock -> UTC instant (earlier instant for repeats)."""
        if not self.dst:
            return naive_local.replace(tzinfo=UTC) - self.std
        for off in (self.std + dt.timedelta(hours=1), self.std):
            cand = naive_local.replace(tzinfo=UTC) - off
            if self.offset_at_utc(cand) == off:
                return cand
        # skipped local hour: use the offset in force before the change
        return naive_local.replace(tzinfo=UTC) - self.std

    def to_local(self, when: dt.datetime) -> dt.datetime:
        return (when + self.offset_at_utc(when)).replace(tzinfo=None)


def _last_sunday(year: int, month: int) -> dt.datetime:
    last = calendar.monthrange(year, month)[1]
    d = dt.date(year, month, last)
    d -= dt.timedelta(days=(d.weekday() + 1) % 7)
    return dt.datetime(d.year, d.month, d.day)


def local_to_utc(naive: dt.datetime, zone: Zone) -> dt.datetime:
    return zone.to_utc(naive)


# ------------------------------------------------------------- raw readers ---


def read_lines(path):
    """Decoded lines of a text file (UTF-8 with a Latin-1 fallback per line)."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data.endswith(b"\n"):
        data = data[:-1]
    out = []
    for raw in data.split(b"\n"):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        try:
            out.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(raw.decode("latin-1"))
    return out


def _quote_parity(line: str, inside: bool) -> bool:
    i = 0
    while i < len(line):
        if line[i] == '"':
            if inside and i + 1 < len(line) and line[i + 1] == '"':
                i += 2
                continue
            inside = not inside
        i += 1
    return inside


def read_delimited(path, delim):
    """Rows of a delimited file: [(cells, is_record)] with headers tracked."""
    lines = read_lines(path)
    kept = []
    inside = False
    for line in lines:
        if not inside:
            s = line.lstrip("\ufeff")
            if s.strip() == "" or s.lstrip().startswith("#"):
                continue
        kept.append(line)
        inside = _quote_parity(line, inside)
    text = "\n".join(kept)
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))
    out = []
    header = None
    for cells in rows:
        cells = [clean_text(c) for c in cells]
        if not any(c != "" for c in cells):
            continue
        if header is None:
            header = cells
            continue
        if sorted(cells) == sorted(header):
            header = cells
            continue
        d = {}
        for i, name in enumerate(header):
            d[name] = cells[i] if i < len(cells) else ""
        out.append(d)
    return header, out


def read_json(path):
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def read_jsonl(path):
    out = []
    for line in read_lines(path):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        obj = json.loads(s)
        if isinstance(obj, dict) and "_meta" in obj:
            continue
        out.append(obj)
    return out


def read_xlsx(path):
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    epoch = EPOCH_1904 if wb.epoch == dt.datetime(1904, 1, 1) else EPOCH_1900
    sheets = []
    for ws in wb.worksheets:
        header = None
        rows = []
        for cells in ws.iter_rows(values_only=True):
            vals = list(cells)
            while vals and vals[-1] is None:
                vals.pop()
            if not vals:
                continue
            if header is None:
                header = [clean_text(c) for c in vals]
                continue
            txt = [clean_text(c) for c in vals]
            if txt == header:
                continue
            rows.append({header[i]: (vals[i] if i < len(vals) else None) for i in range(len(header))})
        sheets.append((ws.title, header or [], rows))
    wb.close()
    return sheets, epoch


def read_sqlite(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        names = [r[0] for r in con.execute(
            "select name from sqlite_master where type='table' order by rowid")]
        tables = []
        for n in names:
            cols = [r[1] for r in con.execute(f"pragma table_info('{n}')")]
            rows = [dict(zip(cols, r)) for r in con.execute(f"select * from '{n}' order by rowid")]
            tables.append((n, cols, rows))
        return tables
    finally:
        con.close()


def read_parquet(path):
    import pyarrow.parquet as pq

    t = pq.read_table(path)
    return t.schema.names, t.to_pylist()


def read_docx_tables(path):
    """[(caption, header, rows)] for captioned document tables."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(path)
    out = []
    caption = None
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            t = Paragraph(child, d).text.strip()
            if t.startswith("Table:"):
                caption = t[6:].strip()
        elif tag == "tbl":
            tb = Table(child, d)
            header = None
            rows = []
            for row in tb.rows:
                cells = [clean_text(c.text) for c in row.cells]
                if header is None:
                    header = cells
                    continue
                if cells == header:
                    continue
                rows.append({header[i]: cells[i] for i in range(min(len(header), len(cells)))})
            out.append((caption, header or [], rows))
            caption = None
    return out


def _split_md_row(line: str):
    """Cells of a markdown table row, honouring backslash-escaped pipes."""
    cells = []
    cur = []
    i = 0
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            cur.append(s[i + 1])
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur))
    return cells


def read_md_tables(path):
    out = []
    caption = None
    header = None
    rows = None
    for line in read_lines(path):
        s = line.strip()
        m = re.fullmatch(r"\*\*Table:\s*(.*?)\*\*", s)
        if m:
            if header is not None:
                out.append((caption, header, rows))
            caption = m.group(1).strip()
            header = None
            rows = []
            continue
        if s.startswith("|") and rows is not None:
            cells = [clean_text(c) for c in _split_md_row(s)]
            if all(re.fullmatch(r":?-{2,}:?", c.strip()) for c in cells if c != ""):
                continue
            if header is None:
                header = cells
                continue
            if cells == header:
                continue
            rows.append({header[i]: cells[i] for i in range(min(len(header), len(cells)))})
        elif s == "" or not s.startswith("|"):
            if s and not s.startswith("|") and header is not None and rows:
                out.append((caption, header, rows))
                caption, header, rows = None, None, None
    if header is not None:
        out.append((caption, header, rows))
    return out


def read_html_tables(path):
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8")
    out = []
    for m in re.finditer(r"<table[^>]*>(.*?)</table>", text, re.S):
        body = m.group(1)
        cm = re.search(r"<caption[^>]*>(.*?)</caption>", body, re.S)
        caption = _unescape(cm.group(1)) if cm else None
        header = None
        hm = re.search(r"<thead[^>]*>(.*?)</thead>", body, re.S)
        if hm:
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", hm.group(1), re.S)
            header = [clean_text(_unescape(c)) for c in cells]
        rows = []
        bm = re.search(r"<tbody[^>]*>(.*?)</tbody>", body, re.S)
        section = bm.group(1) if bm else body
        for rm in re.finditer(r"<tr[^>]*>(.*?)</tr>", section, re.S):
            cells = [clean_text(_unescape(c))
                     for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rm.group(1), re.S)]
            if header is None:
                header = cells
                continue
            if cells == header:
                continue
            rows.append({header[i]: cells[i] for i in range(min(len(header), len(cells)))})
        out.append((caption, header or [], rows))
    return out


def _unescape(s: str) -> str:
    return (s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            .replace("&#39;", "'").replace("&nbsp;", "\u00a0").replace("&amp;", "&"))


def read_pdf_tables(path):
    """[(caption, header, rows)] from pipe-separated PDF tables."""
    import pypdf

    reader = pypdf.PdfReader(path)
    rows_by_cap = {}
    header_by_cap = {}
    order = []
    caption = None
    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.split("\n"):
            s = line.strip()
            if not s:
                continue
            if s.startswith("Table:"):
                cap = s[6:].strip()
                if cap.endswith("(continued)"):
                    cap = cap[: -len("(continued)")].strip()
                caption = cap
                if cap not in rows_by_cap:
                    rows_by_cap[cap] = []
                    order.append(cap)
                continue
            if caption is None or "|" not in s:
                continue
            cells = [clean_text(c) for c in s.split("|")]
            if caption not in header_by_cap:
                header_by_cap[caption] = cells
                continue
            hdr = header_by_cap[caption]
            if cells == hdr:
                continue
            rows_by_cap[caption].append(
                {hdr[i]: cells[i] for i in range(min(len(hdr), len(cells)))})
    return [(cap, header_by_cap.get(cap, []), rows_by_cap[cap]) for cap in order]


def read_xml(path):
    import lxml.etree as ET

    tree = ET.parse(path)
    root = tree.getroot()
    groups = {}
    order = []
    for child in root:
        tag = child.tag
        if not isinstance(tag, str):
            continue
        if tag not in groups:
            groups[tag] = []
            order.append(tag)
        groups[tag].append(dict(child.attrib))
    return [(tag, groups[tag]) for tag in order]


def read_yaml(path):
    import yaml

    with open(path, "rb") as fh:
        doc = yaml.safe_load(fh.read().decode("utf-8"))
    out = []
    for key, val in doc.items():
        if isinstance(val, list):
            out.append((key, val))
    return out


def read_toml(path):
    import tomli

    with open(path, "rb") as fh:
        doc = tomli.load(fh)
    out = []
    for key, val in doc.items():
        if isinstance(val, list):
            out.append((key, val))
    return out


LOG_RE = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)=(\"(?:[^\"\\]|\\.)*\"|\S*)")


def read_log(path):
    """[(timestamp_text, dict_of_fields)] for log event lines."""
    out = []
    for line in read_lines(path):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split(None, 3)
        ts = parts[0] if parts else ""
        fields = {}
        for m in LOG_RE.finditer(s):
            key, val = m.group(1), m.group(2)
            if val.startswith('"'):
                val = val[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            if key not in fields:
                fields[key] = val
        fields["_ts"] = ts
        out.append(fields)
    return out


def read_ini(path):
    """[(section_name, dict)] preserving file order."""
    out = []
    cur = None
    for line in read_lines(path):
        s = line.strip()
        if not s or s.startswith(";") or s.startswith("#"):
            continue
        if s.startswith("["):
            cur = {}
            out.append((s[1:-1].strip(), cur))
        elif "=" in s and cur is not None:
            k, v = s.split("=", 1)
            cur[k.strip()] = v.strip()
    return out


def read_ics(path):
    """[(dict)] for VEVENTs; property values keep their parameters."""
    lines = []
    for line in read_lines(path):
        if line.startswith(" ") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    out = []
    cur = None
    for line in lines:
        s = line.strip()
        if s == "BEGIN:VEVENT":
            cur = {}
        elif s == "END:VEVENT":
            if cur is not None:
                out.append(cur)
            cur = None
        elif cur is not None and ":" in s:
            name, val = s.split(":", 1)
            parts = name.split(";")
            key = parts[0].upper()
            params = {}
            for p in parts[1:]:
                if "=" in p:
                    pk, pv = p.split("=", 1)
                    params[pk.upper()] = pv
            cur[key] = (val, params)
    return out


def read_mbox(path):
    """[(dict)] of messages with headers and decoded body."""
    import email

    with open(path, "rb") as fh:
        data = fh.read()
    chunks = re.split(rb"(?m)^From [^\n]*\n", data)
    out = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        msg = email.message_from_bytes(chunk)
        payload = msg.get_payload(decode=True)
        if payload is None:
            body = msg.get_payload() if isinstance(msg.get_payload(), str) else ""
        else:
            try:
                body = payload.decode("utf-8")
            except UnicodeDecodeError:
                body = payload.decode("latin-1")
        rec = {k.lower(): v for k, v in msg.items()}
        rec["_body"] = body
        out.append(rec)
    return out


def _first_key(rows):
    for r in rows:
        if isinstance(r, dict):
            for k in r:
                return k
    return None


def read_fwf(path, layouts):
    """[(record_type, dict)] of fixed-width records; H records switch layout."""
    out = []
    layout = None
    for line in read_lines(path):
        if not line.strip():
            continue
        kind = line[0]
        rest = line[1:]
        if kind == "H":
            name = rest[:4].strip()
            layout = layouts.get(name)
            out.append(("H", {"layout": name}))
            continue
        if kind == "T":
            out.append(("T", {"raw": rest.strip()}))
            continue
        rec = {}
        pos = 0
        for field, width in (layout or []):
            rec[field] = rest[pos:pos + width].strip()
            pos += width
        out.append(("D", rec))
    return out


# ------------------------------------------------------------ table loading --


class Table:
    __slots__ = ("name", "ctrl_field", "rows", "ctrl_values")

    def __init__(self, name, ctrl_field, rows, ctrl_values=None):
        self.name = name
        self.ctrl_field = ctrl_field
        self.rows = rows
        if ctrl_values is None:
            ctrl_values = [r.get(ctrl_field) if isinstance(r, dict) else None for r in rows]
        self.ctrl_values = ctrl_values


class Repo:
    """Lazily loaded, cached view of the export directory."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.catalog = {}
        self.catalog_order = []
        self._tables = {}
        self._errors = {}
        self.epochs = {}
        self.fwf_layouts = {}

    def path(self, name):
        return os.path.join(self.dir, name)

    def tables(self, name):
        """List of Table for a file; raises on missing/unreadable files."""
        if name in self._tables:
            return self._tables[name]
        if name in self._errors:
            raise self._errors[name]
        try:
            tabs = self._load(name)
        except FileNotFoundError as exc:
            self._errors[name] = exc
            raise
        except Exception as exc:  # unreadable
            self._errors[name] = exc
            raise
        self._tables[name] = tabs
        return tabs

    def table(self, name, table_name):
        for t in self.tables(name):
            if t.name == table_name:
                return t.rows
        return []

    def reorder(self, name, order):
        """Reorder the tables of a loaded file (record order follows the register)."""
        tables = self.tables(name)
        self._tables[name] = [tables[i] for i in order]

    def epoch_of(self, name):
        """Serial-date epoch of a workbook."""
        self.tables(name)
        return self.epochs.get(name, EPOCH_1900)

    def first_table(self, name):
        tabs = self.tables(name)
        return tabs[0].rows if tabs else []

    def all_rows(self, name):
        out = []
        for t in self.tables(name):
            out.extend(t.rows)
        return out

    def _load(self, name):
        fmt = self.catalog.get(name, {}).get("format")
        hint = self.catalog.get(name, {}).get("control_field")
        path = self.path(name)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        if fmt is None:
            fmt = os.path.splitext(name)[1].lstrip(".")
        if fmt == "csv":
            header, rows = read_delimited(path, ",")
            return [Table(name, (header or [None])[0], rows)]
        if fmt == "tsv":
            header, rows = read_delimited(path, "\t")
            return [Table(name, (header or [None])[0], rows)]
        if fmt == "xlsx":
            sheets, epoch = read_xlsx(path)
            self.epochs[name] = epoch
            return [Table(title, (hdr or [None])[0], rows) for title, hdr, rows in sheets]
        if fmt == "sqlite":
            return [Table(tn, (cols or [None])[0], rows) for tn, cols, rows in read_sqlite(path)]
        if fmt == "parquet":
            cols, rows = read_parquet(path)
            return [Table(name, (cols or [None])[0], rows)]
        if fmt == "json":
            doc = read_json(path)
            out = []
            if isinstance(doc, list):
                out.append(Table(name, _first_key(doc), doc))
            else:
                for key, val in doc.items():
                    if isinstance(val, list):
                        out.append(Table(key, _first_key(val), val))
            return out
        if fmt == "jsonl":
            rows = read_jsonl(path)
            return [Table(name, _first_key(rows), rows)]
        if fmt == "xml":
            return [Table(tag, _first_key(rows), rows) for tag, rows in read_xml(path)]
        if fmt == "yaml":
            return [Table(key, _first_key(val), val) for key, val in read_yaml(path)]
        if fmt == "toml":
            return [Table(key, _first_key(val), val) for key, val in read_toml(path)]
        if fmt == "docx":
            return [Table(cap, (hdr or [None])[0], rows) for cap, hdr, rows in read_docx_tables(path)]
        if fmt == "md":
            return [Table(cap, (hdr or [None])[0], rows) for cap, hdr, rows in read_md_tables(path)]
        if fmt == "html":
            return [Table(cap, (hdr or [None])[0], rows) for cap, hdr, rows in read_html_tables(path)]
        if fmt == "pdf":
            return [Table(cap, (hdr or [None])[0], rows) for cap, hdr, rows in read_pdf_tables(path)]
        if fmt == "log":
            rows = read_log(path)
            return [Table(name, hint, rows)]
        if fmt == "ini":
            secs = read_ini(path)
            rows = [d for _, d in secs]
            ctrl = [sec.rsplit(".", 1)[-1] for sec, _ in secs]
            for (sec, d) in secs:
                d["_section"] = sec
            return [Table(name, hint, rows, ctrl)]
        if fmt == "mbox":
            rows = read_mbox(path)
            ctrl = []
            for r in rows:
                mid = r.get("message-id", "")
                m = re.search(r"<?([^<>@]+)@?", mid)
                ctrl.append(m.group(1) if m else "")
            return [Table(name, "message_id", rows, ctrl)]
        if fmt == "ics":
            evs = read_ics(path)
            rows = evs
            ctrl = [e.get("UID", ("", {}))[0] for e in evs]
            return [Table(name, "uid", rows, ctrl)]
        if fmt == "fwf":
            recs = read_fwf(path, self.fwf_layouts)
            rows = [r for kind, r in recs if kind == "D"]
            return [Table(name, "record_id", rows)]
        raise ValueError(f"unknown format {fmt} for {name}")


# --------------------------------------------------------- source register ---


def load_register(repo):
    """Close parameters, regions, currencies and the source catalog."""
    tabs = {t.name: t.rows for t in repo.tables("source_register.md")}
    params = {clean_text(r["key"]): clean_text(r["value"]) for r in tabs["Close parameters"]}
    regions = {}
    for r in tabs["Regions"]:
        code = clean_text(r["region"]).split("|")[0].strip()
        regions[code] = {
            "city": clean_text(r["city"]),
            "region_group": clean_text(r["region_group"]),
            "tzid": clean_text(r["tzid"]),
            "zone": Zone(int(parse_decimal(r["std_offset_min"])), clean_text(r["dst_rule"])),
        }
    currencies = {clean_text(r["currency"]): int(parse_decimal(r["minor_exponent"]))
                  for r in tabs["Currencies"]}
    catalog = []
    for r in tabs["Source catalog"]:
        catalog.append({
            "file": clean_text(r["file"]),
            "format": clean_text(r["format"]),
            "control_field": clean_text(r["control_field"]),
            "role": clean_text(r["role"]),
        })
    legacy_orders = {}
    for r in tabs.get("Legacy order references", []):
        legacy_orders[norm_ident(r["order_ref"])] = norm_ident(r["subscription_id"])
    return params, regions, currencies, catalog, legacy_orders


# ------------------------------------------------------------- controls ------


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def load_expected_controls(repo):
    """file -> {block: (records, control_sum)} from the register and outside it."""
    exp = defaultdict(dict)
    best_rev = defaultdict(dict)
    try:
        rows = repo.table("audit_control_register.pdf", "Control blocks")
    except Exception:
        rows = []
    for r in rows:
        name = clean_text(r.get("file"))
        block = parse_count(r.get("block"))
        records = parse_count(r.get("records"))
        csum = parse_count(r.get("control_sum"))
        rev = parse_count(r.get("revision"))
        if not name or block is None or records is None or csum is None or rev is None:
            continue
        if block in best_rev[name] and best_rev[name][block] >= rev:
            continue
        best_rev[name][block] = rev
        exp[name][block] = (records, csum)
    try:
        for r in repo.first_table("ingest_reprocess.log"):
            if clean_text(r.get("event")) != "CONTROL":
                continue
            name = clean_text(r.get("file"))
            block = parse_count(r.get("block"))
            records = parse_count(r.get("records"))
            csum = parse_count(r.get("control_sum"))
            if name and block is not None and records is not None and csum is not None:
                exp[name][block] = (records, csum)
    except Exception:
        pass
    try:
        for r in repo.table("region_groups_2025.toml", "control"):
            name = clean_text(r.get("file"))
            block = parse_count(r.get("block"))
            records = parse_count(r.get("records"))
            csum = parse_count(r.get("control_sum"))
            if name and block is not None and records is not None and csum is not None:
                exp[name][block] = (records, csum)
    except Exception:
        pass
    return exp


def _block_sums(tables, order):
    flat = []
    for i in order:
        flat.extend(tables[i].ctrl_values)
    return [(len(c), sum(ctrl_digits(v) for v in c)) for c in _chunks(flat, 100)]


def _matches(blocks, want):
    if len(blocks) != len(want):
        return False
    for i, (recs, csum) in enumerate(blocks, 1):
        if want.get(i) != (recs, csum):
            return False
    return True


def check_controls(repo, catalog):
    """Per-file record counts, control results and held reasons."""
    expected = load_expected_controls(repo)
    sources = []
    reasons = []
    total_records = 0
    total_blocks = 0
    failures = 0
    for entry in catalog:
        name = entry["file"]
        try:
            tables = repo.tables(name)
        except FileNotFoundError:
            sources.append({"file": name, "records": 0, "control_blocks": 0, "control_ok": False})
            reasons.append("MISSING:" + name)
            failures += 1
            continue
        except Exception:
            sources.append({"file": name, "records": 0, "control_blocks": 0, "control_ok": False})
            reasons.append("UNREADABLE:" + name)
            failures += 1
            continue
        records = sum(len(t.rows) for t in tables)
        total_records += records
        want = expected.get(name)
        if not want:
            sources.append({"file": name, "records": records, "control_blocks": 0,
                            "control_ok": True})
            continue
        order = list(range(len(tables)))
        blocks = _block_sums(tables, order)
        ok = _matches(blocks, want)
        if not ok and 1 < len(tables) <= 4:
            # the register fixes the record order; some workbooks list their
            # sheets in another order than the one the controls were taken in
            for perm in itertools.permutations(order):
                if list(perm) == order:
                    continue
                cand = _block_sums(tables, perm)
                if _matches(cand, want):
                    repo.reorder(name, perm)
                    blocks = cand
                    ok = True
                    break
        nblocks = max(len(blocks), len(want))
        total_blocks += nblocks
        sources.append({"file": name, "records": records, "control_blocks": nblocks,
                        "control_ok": ok})
        if not ok:
            reasons.append("CONTROL_MISMATCH:" + name)
            failures += 1
    recon = {"files": len(catalog), "records": total_records,
             "control_blocks": total_blocks, "control_failures": failures}
    return sources, sorted(reasons), recon


def _ceil_div(a, b):
    return -((-a) // b)


def _is_placeholder_fee(value):
    """True when a monthly fee marks a placeholder record."""
    if value is None:
        return True
    if isinstance(value, str):
        s = clean_text(value)
        if s == "" or s.upper() in ("N/A", "NA", "NONE", "NULL"):
            return True
        if s.upper() == "LIST":
            return False
        head = s.split(" ")[0]
        return parse_decimal(head) is None
    return parse_count(value) is None


def norm_site(raw) -> str:
    """Canonical business-calendar site code."""
    s = clean_text(raw).upper()
    return "".join(ch for ch in s if ch.isalnum())


# ------------------------------------------------------------ field access --


def camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def rget(row, *names):
    """Value of the first present field, accepting camelCase spellings."""
    for name in names:
        if name in row:
            return row[name]
        c = camel(name)
        if c in row:
            return row[c]
    return None


def mask_range(lo, hi):
    """Bit mask of window indices [lo, hi)."""
    if hi <= lo:
        return 0
    return ((1 << (hi - lo)) - 1) << lo


class Sub:
    __slots__ = ("sid", "account_raw", "account", "product", "region", "start", "end",
                 "plan_code", "fee_raw", "currency", "active_days", "active_mask",
                 "plan", "segment", "version", "sla_class", "target", "region_group")

    def __init__(self, sid):
        self.sid = sid
        self.active_mask = None


class Close:
    """All reference data and computations of one monthly close."""

    def __init__(self, repo, prior_dir=None):
        self.repo = repo
        self.prior_dir = prior_dir
        (self.params, self.regions, self.currencies, self.catalog,
         self.legacy_orders) = load_register(repo)
        self.period = self.params["period"]
        year, month = (int(x) for x in self.period.split("-"))
        self.month_start = dt.datetime(year, month, 1, tzinfo=UTC)
        self.days = calendar.monthrange(year, month)[1]
        self.last_day = dt.date(year, month, self.days)
        self.next_start = self.month_start + dt.timedelta(days=self.days)
        self.nw = self.days * 288
        self.quarter_start = parse_date(self.params["quarter_start"])
        self.quarter_start_ts = dt.datetime.combine(self.quarter_start, dt.time(), UTC)
        self.crm_cutover = parse_instant(self.params["crm_cutover"])
        self.full_mask = (1 << self.nw) - 1
        self._acct_cache = {}

    # --------------------------------------------------------------- basics --

    def win_of(self, when):
        """Window index of an instant, or None when outside the month."""
        if when is None or when < self.month_start or when >= self.next_start:
            return None
        return int((when - self.month_start).total_seconds()) // 300

    def interval_mask(self, start, end):
        """Mask of windows whose start instant lies in [start, end)."""
        if start is None or end is None:
            return 0
        if end <= self.month_start or start >= self.next_start:
            return 0
        lo = 0 if start <= self.month_start else _ceil_div(
            int((start - self.month_start).total_seconds()), 300)
        if end >= self.next_start:
            hi = self.nw
        else:
            hi = _ceil_div(int((end - self.month_start).total_seconds()), 300)
        return mask_range(max(lo, 0), min(hi, self.nw))

    def canon_region(self, raw):
        s = clean_text(raw).lower()
        if not s:
            return None
        if s in self.regions:
            return s
        return self.region_alias.get(s)

    # ---------------------------------------------------------- reference ----

    def load_reference(self):
        self.load_regions()
        self.load_accounts()
        self.load_subscriptions()
        self.load_enrollment()
        self.load_plans()
        self.load_versions()
        self.load_targets()
        self.load_fees()
        self.load_quotas()
        self.load_calendars()
        self.load_claims()
        self.load_fx()
        self.load_caps()

    # regions ------------------------------------------------------------
    def load_regions(self):
        repo = self.repo
        self.region_alias = {}
        for r in repo.table("region_groups_2025.toml", "region_alias"):
            alias = clean_text(rget(r, "alias")).lower()
            region = clean_text(rget(r, "region")).lower()
            if alias and region:
                self.region_alias[alias] = region
        self.region_site = {}
        for r in repo.table("region_groups_2025.toml", "region_site"):
            region = clean_text(rget(r, "region")).lower()
            site = norm_site(rget(r, "site"))
            if region and site:
                self.region_site[region] = site
        self.site_region = {}
        for region, site in self.region_site.items():
            self.site_region.setdefault(site, region)
        self.region_group = {r: info["region_group"] for r, info in self.regions.items()}
        regroup = []
        for r in repo.table("governance_charter.docx", "Region regroupings"):
            region = clean_text(rget(r, "region")).lower()
            group = clean_text(rget(r, "region_group"))
            eff = parse_date(rget(r, "effective"))
            if region in self.region_group and group and eff and eff <= self.last_day:
                regroup.append((eff, region, group))
        for eff, region, group in sorted(regroup, key=lambda x: x[0]):
            self.region_group[region] = group
        self.zone = {r: info["zone"] for r, info in self.regions.items()}
        self.tz_by_id = {info["tzid"]: info["zone"] for info in self.regions.values()}

    # accounts -----------------------------------------------------------
    def load_accounts(self):
        repo = self.repo
        self.accounts = {}
        for r in repo.first_table("accounts_master.csv"):
            aid = norm_ident(rget(r, "account_id"))
            if not aid:
                continue
            self.accounts[aid] = {
                "created": parse_date(rget(r, "created")),
                "currency": clean_text(rget(r, "currency")),
                "status": clean_text(rget(r, "status")),
            }
        self.ref_map = {}
        for r in repo.first_table("account_aliases.tsv"):
            alias = norm_ident(rget(r, "alias_id"))
            target = norm_ident(rget(r, "account_id"))
            if alias and target and alias != target:
                self.ref_map[alias] = target
        decisions = []
        for r in repo.table("governance_charter.docx", "Account decisions"):
            did = norm_ident(rget(r, "decision_id"))
            src = norm_ident(rget(r, "from_account"))
            dst = norm_ident(rget(r, "to_account"))
            decided = parse_date(rget(r, "decided_on"))
            if not did or not src or not dst or decided is None:
                continue
            if decided > self.last_day:
                continue
            decisions.append((decided, did, src, dst))
        for _, _, src, dst in sorted(decisions, key=lambda x: (x[0], x[1])):
            if src != dst:
                self.ref_map[src] = dst
        self.internal = set()
        self.ban_account = {}
        for r in repo.table("account_snapshot_legacy.sqlite", "accounts"):
            aid = norm_ident(rget(r, "account_id"))
            if not aid:
                continue
            if clean_text(rget(r, "internal_flag")).upper() in ("Y", "YES", "TRUE", "1"):
                self.internal.add(aid)
            ban = clean_text(rget(r, "ban"))
            if ban:
                self.ban_account.setdefault(ban, aid)

    def resolve_account(self, raw):
        """Canonical account of a reference, or None when it is unknown."""
        key = raw if isinstance(raw, str) else str(raw)
        if key in self._acct_cache:
            return self._acct_cache[key]
        aid = norm_ident(raw)
        result = None
        if aid:
            seen = set()
            cur = aid
            while cur in self.ref_map and cur not in seen:
                seen.add(cur)
                cur = self.ref_map[cur]
            if cur in self.accounts:
                result = cur
        self._acct_cache[key] = result
        return result

    def is_internal(self, account):
        return account in self.internal

    # subscriptions ------------------------------------------------------
    def load_subscriptions(self):
        repo = self.repo
        self.subs = {}
        files = ["subscriptions_central.csv", "subscriptions_east.parquet",
                 "subscriptions_north.sqlite", "subscriptions_south.jsonl",
                 "subscriptions_west.xlsx"]
        for name in files:
            for t in repo.tables(name):
                if t.name == "Contract discounts":
                    continue
                for r in t.rows:
                    sid = norm_ident(rget(r, "subscription_id"))
                    if not sid:
                        continue
                    acct_raw = rget(r, "account_ref")
                    if norm_ident(acct_raw) is None:
                        continue
                    fee_raw = rget(r, "monthly_fee")
                    if _is_placeholder_fee(fee_raw):
                        continue
                    region = self.canon_region(rget(r, "region"))
                    start = parse_date(rget(r, "start_date"))
                    if region is None or start is None:
                        continue
                    sub = Sub(sid)
                    sub.account_raw = acct_raw
                    sub.product = clean_text(rget(r, "product")).upper()
                    sub.region = region
                    sub.start = start
                    sub.end = parse_date(rget(r, "end_date"))
                    sub.plan_code = clean_text(rget(r, "plan_code")).upper()
                    sub.fee_raw = fee_raw
                    sub.currency = clean_text(rget(r, "currency")).upper()
                    if sid not in self.subs:
                        self.subs[sid] = sub
        for sub in self.subs.values():
            lo = max(sub.start, self.month_start.date())
            hi = sub.end if sub.end is not None else self.last_day
            hi = min(hi, self.last_day)
            if hi < lo:
                sub.active_days = 0
                sub.active_mask = 0
                continue
            first = (lo - self.month_start.date()).days
            last = (hi - self.month_start.date()).days
            sub.active_days = last - first + 1
            sub.active_mask = mask_range(first * 288, (last + 1) * 288)
        self.in_period = sorted(sid for sid, s in self.subs.items() if s.active_days > 0)

    # enrollment ---------------------------------------------------------
    def load_enrollment(self):
        repo = self.repo
        best = {}
        files = ["sla_enrollment_central.md", "sla_enrollment_east.html",
                 "sla_enrollment_north.pdf", "sla_enrollment_south.pdf",
                 "sla_enrollment_west.csv"]
        for name in files:
            for r in repo.all_rows(name):
                eid = norm_ident(rget(r, "enrollment_id"))
                sid = norm_ident(rget(r, "subscription_id"))
                if not eid or not sid:
                    continue
                eff = parse_date(rget(r, "effective"))
                if eff is None or eff > self.last_day:
                    continue
                key = (eff, eid)
                cur = best.get(sid)
                if cur is None or key > cur[0]:
                    best[sid] = (key, clean_text(rget(r, "action")).upper(),
                                 clean_text(rget(r, "sla_class")).upper())
        self.enrollment = {sid: (action, cls) for sid, (_, action, cls) in best.items()}

    # plans --------------------------------------------------------------
    def load_plans(self):
        repo = self.repo
        self.legacy_plan = {}
        for r in repo.table("sla_policy_v4_draft.docx", "Legacy plan codes"):
            legacy = clean_text(rget(r, "legacy_code")).upper()
            plan = clean_text(rget(r, "plan_code")).upper()
            if legacy and plan:
                self.legacy_plan[legacy] = plan
        self.plan_segment = {}
        for r in repo.table("governance_charter.docx", "Plan segments"):
            plan = clean_text(rget(r, "plan_code")).upper()
            seg = clean_text(rget(r, "segment")).lower()
            if plan and seg:
                self.plan_segment[plan] = seg
        changes = defaultdict(list)
        reverted = set()
        files = {
            "plan_changes_central.tsv": None,
            "plan_changes_east.json": None,
            "plan_changes_north.xml": None,
            "plan_changes_south.yaml": None,
            "plan_changes_west.log": None,
        }
        for name in files:
            for r in repo.all_rows(name):
                cid = norm_ident(rget(r, "change_id"))
                sid = norm_ident(rget(r, "subscription_id"))
                if not cid or not sid:
                    continue
                reverts = rget(r, "reverts")
                rev_id = norm_ident(reverts)
                if rev_id is None:
                    continue
                eff = parse_instant(rget(r, "effective"))
                if eff is None or eff >= self.next_start:
                    continue
                action = clean_text(rget(r, "action")).upper()
                plan = clean_text(rget(r, "plan_code")).upper()
                if action == "REVERT":
                    if rev_id:
                        reverted.add(rev_id)
                elif action == "APPLY":
                    changes[sid].append((eff, cid, plan))
        self.plan_changes = {}
        for sid, lst in changes.items():
            lst = [x for x in lst if x[1] not in reverted]
            if lst:
                lst.sort(key=lambda x: (x[0], x[1]))
                self.plan_changes[sid] = lst[-1][2]

    def plan_of(self, sub):
        plan = self.plan_changes.get(sub.sid) or sub.plan_code
        return self.legacy_plan.get(plan, plan)

    # versions -----------------------------------------------------------
    def load_versions(self):
        repo = self.repo
        self.cutovers = []
        for r in repo.table("sla_policy_2026.docx", "Version cutovers"):
            version = clean_text(rget(r, "version"))
            signed = parse_date(rget(r, "signed_from"))
            if version and signed:
                self.cutovers.append((signed, version))
        self.cutovers.sort()
        pins = {}
        for r in repo.table("sla_policy_2026.docx", "Subscription pins"):
            pid = norm_ident(rget(r, "pin_id"))
            sid = norm_ident(rget(r, "subscription_id"))
            if not pid or not sid:
                continue
            pinned = parse_date(rget(r, "pinned_on"))
            version = clean_text(rget(r, "version"))
            if pinned is None or pinned > self.last_day or not version:
                continue
            cur = pins.get(sid)
            if cur is None or (pinned, pid) > cur[0]:
                pins[sid] = ((pinned, pid), version)
        self.pins = {sid: v for sid, (_, v) in pins.items()}
        contracts = {}
        for r in repo.table("contracts_register.xlsx", "Contracts"):
            cid = norm_ident(rget(r, "contract_id"))
            aid = norm_ident(rget(r, "account_id"))
            if not cid or aid is None:
                continue
            signed = parse_date(rget(r, "signed_on"))
            contracts[cid] = (aid, signed)
        self.contract_signature = {}

        def note(account_raw, signed):
            account = self.resolve_account(account_raw)
            if account is None or signed is None or signed > self.last_day:
                return
            cur = self.contract_signature.get(account)
            if cur is None or signed > cur:
                self.contract_signature[account] = signed

        for cid, (aid, signed) in contracts.items():
            note(aid, signed)
        for r in repo.table("contracts_register.xlsx", "Amendments"):
            amid = norm_ident(rget(r, "amendment_id"))
            cid = norm_ident(rget(r, "contract_id"))
            if not amid or not cid or cid not in contracts:
                continue
            note(contracts[cid][0], parse_date(rget(r, "signed_on")))
        schedules = {}
        for r in repo.all_rows("enterprise_sla_schedules.pdf"):
            schid = norm_ident(rget(r, "schedule_id"))
            sid = norm_ident(rget(r, "subscription_id"))
            if not schid or not sid:
                continue
            eff = parse_date(rget(r, "effective"))
            target = parse_decimal(rget(r, "target_pct"))
            credit = parse_count(rget(r, "credit_pct"))
            if eff is None or eff > self.last_day or target is None or credit is None:
                continue
            schedules[schid] = (sid, eff, target, credit)
        revoked = set()
        for r in repo.table("credit_tiers_2026.xlsx", "Revocations"):
            rid = norm_ident(rget(r, "revocation_id"))
            schid = norm_ident(rget(r, "schedule_id"))
            if not rid or not schid:
                continue
            if clean_text(rget(r, "status")).upper() != "RATIFIED":
                continue
            when = parse_date(rget(r, "revoked_on"))
            if when is None or when > self.last_day:
                continue
            revoked.add(schid)
        self.schedules = {}
        for schid, (sid, eff, target, credit) in schedules.items():
            if schid in revoked:
                continue
            cur = self.schedules.get(sid)
            if cur is None or (eff, schid) > cur[0]:
                self.schedules[sid] = ((eff, schid), target, credit)

    def version_of(self, sub, segment):
        if segment == "enterprise" and sub.sid in self.schedules:
            return "custom"
        pinned = self.pins.get(sub.sid)
        if pinned:
            return pinned
        signed = self.contract_signature.get(sub.account)
        if signed is None:
            info = self.accounts.get(sub.account) or {}
            signed = info.get("created")
        version = None
        if signed is not None:
            for start, name in self.cutovers:
                if start <= signed:
                    version = name
        return version or self.cutovers[0][1]

    # targets and tiers --------------------------------------------------
    def load_targets(self):
        repo = self.repo
        self.targets = {}
        for r in repo.table("sla_policy_2026.docx", "Service targets"):
            version = clean_text(rget(r, "version"))
            cls = clean_text(rget(r, "sla_class")).upper()
            target = parse_decimal(rget(r, "target_pct"))
            if version and cls and target is not None:
                self.targets[(version, cls)] = target
        for r in repo.table("sla_policy_v4_draft.docx", "Legacy schedule v2 targets"):
            version = clean_text(rget(r, "version"))
            cls = clean_text(rget(r, "sla_class")).upper()
            target = parse_decimal(rget(r, "target_pct"))
            if version == "v2" and cls and target is not None:
                self.targets[(version, cls)] = target
        self.v5_targets = {}
        for r in repo.table("credit_tiers_2026.xlsx", "Ratified"):
            tid = norm_ident(rget(r, "target_id"))
            if not tid:
                continue
            product = clean_text(rget(r, "product")).upper()
            region = self.canon_region(rget(r, "region"))
            cls = clean_text(rget(r, "sla_class")).upper()
            target = parse_decimal(rget(r, "target_pct"))
            eff = parse_date(rget(r, "effective"))
            if not product or region is None or not cls or target is None or eff is None:
                continue
            if eff > self.last_day:
                continue
            key = (product, region, cls)
            cur = self.v5_targets.get(key)
            if cur is None or (eff, tid) > cur[0]:
                self.v5_targets[key] = ((eff, tid), target)
        self.tiers = defaultdict(list)
        for r in repo.table("sla_policy_2026.docx", "Credit tiers"):
            version = clean_text(rget(r, "version"))
            kind = clean_text(rget(r, "kind")).lower()
            threshold = parse_decimal(rget(r, "threshold"))
            pct = parse_count(rget(r, "credit_pct"))
            if version and kind and threshold is not None and pct is not None:
                self.tiers[version].append((kind, threshold, pct))
        for r in repo.table("sla_policy_v4_draft.docx", "Legacy schedule v2 tiers"):
            version = clean_text(rget(r, "version"))
            kind = clean_text(rget(r, "kind")).lower()
            threshold = parse_decimal(rget(r, "threshold"))
            pct = parse_count(rget(r, "credit_pct"))
            if version == "v2" and kind and threshold is not None and pct is not None:
                self.tiers[version].append((kind, threshold, pct))
        self.permille = {}
        for r in repo.table("sla_policy_2026.docx", "Bad window thresholds"):
            version = clean_text(rget(r, "version"))
            pm = parse_count(rget(r, "permille"))
            if version and pm is not None:
                self.permille[version] = pm
        for r in repo.table("sla_policy_v4_draft.docx", "Legacy schedule v2 thresholds"):
            version = clean_text(rget(r, "version"))
            pm = parse_count(rget(r, "permille"))
            if version == "v2" and pm is not None:
                self.permille[version] = pm
        self.permille["custom"] = self.permille.get("v5")

    def target_of(self, sub, version, sla_class):
        if version == "custom":
            return self.schedules[sub.sid][1]
        if version == "v5":
            entry = self.v5_targets.get((sub.product, sub.region, sla_class))
            if entry:
                return entry[1]
            return None
        return self.targets.get((version, sla_class))

    def credit_pct_of(self, sub, version, uptime, target):
        if target is None:
            return 0
        if version == "custom":
            return self.schedules[sub.sid][2] if uptime < target else 0
        best = 0
        for kind, threshold, pct in self.tiers.get(version, ()):
            if kind == "rel":
                hit = uptime < target - threshold
            else:
                hit = uptime < threshold
            if hit and pct > best:
                best = pct
        return best

    # fees ---------------------------------------------------------------
    def load_fees(self):
        repo = self.repo
        self.fee_override = {}
        for t in repo.tables("fee_overrides.xlsx"):
            for r in t.rows:
                oid = norm_ident(rget(r, "override_id"))
                sid = norm_ident(rget(r, "subscription_id"))
                if not oid or not sid:
                    continue
                if clean_text(rget(r, "status")).upper() != "APPROVED":
                    continue
                approved = parse_date(rget(r, "approved_on"))
                if approved is None or approved > self.last_day:
                    continue
                revision = parse_count(rget(r, "revision"))
                fee = rget(r, "fee_minor")
                if revision is None or _is_placeholder_fee(fee):
                    continue
                cur = self.fee_override.get(sid)
                if cur is None or (revision, oid) > cur[0]:
                    self.fee_override[sid] = ((revision, oid), fee)
        self.price_book = defaultdict(list)
        for r in repo.all_rows("price_book.toml"):
            pid = norm_ident(rget(r, "price_id"))
            if not pid:
                continue
            plan = clean_text(rget(r, "plan")).upper()
            product = clean_text(rget(r, "product")).upper()
            currency = clean_text(rget(r, "currency")).upper()
            eff = parse_date(rget(r, "effective"))
            amount = parse_count(rget(r, "amount"))
            if not plan or not product or not currency or eff is None or amount is None:
                continue
            if eff > self.last_day:
                continue
            self.price_book[(plan, product, currency)].append((eff, pid, amount))
        self.discount = {}
        for r in repo.table("subscriptions_west.xlsx", "Contract discounts"):
            did = norm_ident(rget(r, "discount_id"))
            account = self.resolve_account(rget(r, "account_ref"))
            if not did or account is None:
                continue
            eff = parse_date(rget(r, "effective"))
            bp = parse_count(rget(r, "discount_bp"))
            if eff is None or bp is None or eff > self.last_day:
                continue
            cur = self.discount.get(account)
            if cur is None or (eff, did) > cur[0]:
                self.discount[account] = ((eff, did), bp)

    def money_minor(self, value, currency):
        """Minor units of an amount; decimal major amounts carry their currency."""
        if value is None:
            return None
        if isinstance(value, str):
            s = clean_text(value)
            if s.upper() == "LIST":
                return "LIST"
            m = re.fullmatch(r"(.+?)\s*([A-Z]{3})", s)
            if m:
                amount = parse_decimal(m.group(1))
                code = m.group(2)
                if amount is None:
                    return None
                exp = self.currencies.get(code, 2)
                return round_half_even(amount * (10 ** exp))
        return parse_count(value)

    def fee_of(self, sub, plan):
        override = self.fee_override.get(sub.sid)
        if override is not None:
            fee = self.money_minor(override[1], sub.currency)
            if isinstance(fee, int):
                return fee
        own = self.money_minor(sub.fee_raw, sub.currency)
        if isinstance(own, int):
            return own
        entries = self.price_book.get((plan, sub.product, sub.currency))
        if not entries:
            return 0
        best = max(entries, key=lambda x: (x[0], x[1]))
        amount = Decimal(best[2])
        bp = self.discount.get(sub.account)
        if bp is not None:
            amount = amount * (Decimal(10000) - Decimal(bp[1])) / Decimal(10000)
        return round_half_even(amount)

    # quotas -------------------------------------------------------------
    def load_quotas(self):
        repo = self.repo
        self.quota_changes = defaultdict(list)
        for r in repo.first_table("quota_changes.tsv"):
            cid = norm_ident(rget(r, "change_id"))
            sid = norm_ident(rget(r, "subscription"))
            if not cid or not sid:
                continue
            eff = parse_instant(rget(r, "effective"))
            quota = parse_count(rget(r, "quota"))
            if eff is None or quota is None:
                continue
            self.quota_changes[sid].append((eff, cid, quota))
        for lst in self.quota_changes.values():
            lst.sort(key=lambda x: (x[0], x[1]))
        self.quota_base = {}
        for name in ["quotas_central.yaml", "quotas_east.toml", "quotas_north.sqlite",
                     "quotas_south.md", "quotas_west.html"]:
            for r in repo.all_rows(name):
                sid = norm_ident(rget(r, "subscription"))
                if not sid:
                    continue
                quota = parse_count(rget(r, "quota_per_window"))
                as_of = parse_date(rget(r, "as_of"))
                if quota is None or as_of is None or as_of > self.last_day:
                    continue
                cur = self.quota_base.get(sid)
                if cur is None or as_of >= cur[0]:
                    self.quota_base[sid] = (as_of, quota)

    def quota_at(self, sid, when):
        """Request quota per window, or None when unlimited."""
        changes = self.quota_changes.get(sid)
        if changes:
            found = None
            for eff, _, quota in changes:
                if eff <= when:
                    found = quota
                else:
                    break
            if found is not None:
                return None if found == 0 else found
        base = self.quota_base.get(sid)
        if base is not None:
            return None if base[1] == 0 else base[1]
        return None

    # calendars ----------------------------------------------------------
    def load_calendars(self):
        repo = self.repo
        self.site_cal = defaultdict(dict)
        for r in repo.table("maintenance_policy.docx", "Site calendars"):
            site = norm_site(rget(r, "site"))
            day = parse_date(rget(r, "date"))
            flag = clean_text(rget(r, "business")).upper()
            if site and day and flag:
                self.site_cal[site][day] = (flag == "Y")
        self.account_site = {}
        for r in repo.table("credit_operations_manual.docx", "Account calendar sites"):
            account = norm_ident(rget(r, "account_id"))
            site = norm_site(rget(r, "calendar_site"))
            if account and site:
                self.account_site.setdefault(account, site)

    def is_business_day(self, site, day):
        cal = self.site_cal.get(site)
        if cal is not None and day in cal:
            return cal[day]
        return day.weekday() < 5

    def step_business_days(self, site, day, count, forward=True):
        step = dt.timedelta(days=1 if forward else -1)
        left = count
        cur = day
        while left > 0:
            cur = cur + step
            if self.is_business_day(site, cur):
                left -= 1
        return cur


    # claims -------------------------------------------------------------
    def load_claims(self):
        repo = self.repo
        self.crm_subscription = {}
        crm_rows = []
        for r in repo.first_table("claims_crm_legacy.csv"):
            case = norm_ident(rget(r, "case_id"))
            sid = norm_ident(rget(r, "subscription_id"))
            if not case or not sid:
                continue
            filed = parse_instant(rget(r, "filed_at"))
            self.crm_subscription.setdefault(case, sid)
            crm_rows.append((case, sid, filed))
        self.claims = defaultdict(list)
        for r in repo.first_table("claims_portal.csv"):
            cid = norm_ident(rget(r, "claim_id"))
            sid = norm_ident(rget(r, "subscription_id"))
            if not cid or not sid:
                continue
            filed = parse_instant(rget(r, "filed_at"))
            if filed is None:
                continue
            self.claims[sid].append((filed, cid, "PORTAL", None))
        for r in repo.first_table("support_tickets.jsonl"):
            tid = norm_ident(rget(r, "ticket_id"))
            if not tid:
                continue
            if clean_text(rget(r, "category")).upper() != "SLA_CLAIM":
                continue
            case = rget(r, "crm_case")
            order = rget(r, "order_ref")
            sid = None
            if case is not None and clean_text(case):
                case_id = norm_ident(case)
                if case_id is None:
                    continue
                sid = self.crm_subscription.get(case_id)
            elif order is not None and clean_text(order):
                order_id = norm_ident(order)
                if order_id is None:
                    continue
                sid = self.legacy_orders.get(order_id)
            if not sid:
                continue
            filed = parse_instant(rget(r, "opened_at"))
            if filed is None:
                continue
            self.claims[sid].append((filed, tid, "TICKET", None))
        decisions = {}
        for r in repo.table("claims_backoffice.xlsx", "Decisions"):
            did = norm_ident(rget(r, "decision_id"))
            rid = norm_ident(rget(r, "receipt_id"))
            if not did or not rid:
                continue
            decided = parse_date(rget(r, "decided_on"))
            if decided is None:
                continue
            cur = decisions.get(rid)
            if cur is None or (decided, did) > cur[0]:
                decisions[rid] = ((decided, did), clean_text(rget(r, "decision")).upper())
        for r in repo.table("claims_backoffice.xlsx", "Received"):
            rid = norm_ident(rget(r, "receipt_id"))
            sid = norm_ident(rget(r, "subscription_id"))
            if not rid or not sid:
                continue
            entry = decisions.get(rid)
            if entry is not None and entry[1] == "REJECTED":
                continue
            filed = parse_instant(rget(r, "received"))
            if filed is None:
                continue
            ban = clean_text(rget(r, "ban"))
            self.claims[sid].append((filed, rid, "RECEIPT", ban))
        for case, sid, filed in crm_rows:
            if filed is None or self.crm_cutover is None or filed >= self.crm_cutover:
                continue
            self.claims[sid].append((filed, case, "CRM", None))
        self.withdrawn = set()
        refs = {}
        for r in repo.table("sla_report_draft.pdf", "Claim references"):
            ref = norm_ident(rget(r, "ref"))
            cid = norm_ident(rget(r, "claim_id"))
            if ref and cid:
                refs[ref] = cid
        for r in repo.first_table("claims_workflow.log"):
            if clean_text(rget(r, "event")).upper() != "WITHDRAWN":
                continue
            ref = norm_ident(rget(r, "ref"))
            if not ref:
                continue
            target = refs.get(ref)
            if target:
                self.withdrawn.add(target)
        self.auto_credit = set()
        for r in repo.first_table("credit_preferences.json"):
            account = self.resolve_account(rget(r, "account_id"))
            if account is None:
                continue
            value = rget(r, "auto_credit")
            if value is True or (isinstance(value, str) and clean_text(value).upper() in
                                 ("TRUE", "Y", "YES", "1")):
                self.auto_credit.add(account)

    def claim_for(self, sub, segment):
        """(claim_id, filing instant) of the earliest valid claim, or None."""
        site = self.account_site.get(sub.account)
        deadline = self.step_business_days(site, self.last_day, 10) if site else None
        zone = self.zone.get(self.site_region.get(site)) if site else None
        best = None
        for filed, cid, kind, extra in self.claims.get(sub.sid, ()):
            if cid in self.withdrawn:
                continue
            if kind == "CRM" and segment != "smb":
                continue
            if kind == "RECEIPT":
                if self.ban_account.get(extra) != sub.account:
                    continue
            if filed < self.month_start:
                continue
            if zone is not None and deadline is not None:
                if zone.to_local(filed).date() > deadline:
                    continue
            key = (filed, cid)
            if best is None or key < best:
                best = key
        return best

    # fx -----------------------------------------------------------------
    def load_fx(self):
        repo = self.repo
        recalled = set()
        for r in repo.table("fx_rates_unofficial.json", "recalls"):
            rid = norm_ident(rget(r, "recall_id"))
            fid = norm_ident(rget(r, "fixing_id"))
            if rid and fid:
                recalled.add(fid)
        treasury = defaultdict(dict)
        for r in repo.first_table("fx_hourly_treasury.csv"):
            fid = norm_ident(rget(r, "fixing_id"))
            if not fid or fid in recalled:
                continue
            ccy = clean_text(rget(r, "currency")).upper()
            hour = parse_instant(rget(r, "hour"))
            rate = parse_decimal(rget(r, "usd_per_unit"))
            revision = parse_count(rget(r, "revision"))
            if not ccy or hour is None or rate is None or revision is None:
                continue
            cur = treasury[ccy].get(hour)
            if cur is None or (revision, fid) > cur[0]:
                treasury[ccy][hour] = ((revision, fid), rate)
        unofficial = defaultdict(dict)
        for r in repo.table("fx_rates_unofficial.json", "rates"):
            fid = norm_ident(rget(r, "fixing_id"))
            if not fid:
                continue
            ccy = clean_text(rget(r, "currency")).upper()
            hour = parse_instant(rget(r, "hour"))
            rate = parse_decimal(rget(r, "usd_per_unit"))
            if not ccy or hour is None or rate is None:
                continue
            unofficial[ccy][hour] = ((0, fid), rate)
        self.fx = {}
        for ccy, hours in treasury.items():
            self.fx[ccy] = sorted((h, v[1]) for h, v in hours.items())
        for ccy, hours in unofficial.items():
            if ccy in self.fx:
                continue
            self.fx[ccy] = sorted((h, v[1]) for h, v in hours.items())

    def rate_at(self, currency, when):
        if currency == "USD":
            return Decimal(1)
        series = self.fx.get(currency)
        if not series or when is None:
            return None
        hour = when.replace(minute=0, second=0, microsecond=0)
        found = None
        for h, rate in series:
            if h <= hour:
                found = rate
            else:
                break
        return found

    # caps and quarter-to-date -------------------------------------------
    def load_caps(self):
        repo = self.repo
        self.cap = {}
        for t in repo.tables("account_caps.xlsx"):
            for r in t.rows:
                cid = norm_ident(rget(r, "cap_id"))
                account = self.resolve_account(rget(r, "account_ref"))
                if not cid or account is None:
                    continue
                eff = parse_date(rget(r, "effective"))
                amount = self.money_minor(rget(r, "quarterly_cap_usd"), "USD")
                if eff is None or eff > self.last_day or not isinstance(amount, int):
                    continue
                cur = self.cap.get(account)
                if cur is None or (eff, cid) > cur[0]:
                    self.cap[account] = ((eff, cid), amount)
        voided = set()
        for r in repo.table("sla_report_draft.pdf", "Voided July postings"):
            ref = norm_ident(rget(r, "void_ref"))
            pid = norm_ident(rget(r, "posting_id"))
            if ref and pid:
                voided.add(pid)
        self.qtd = defaultdict(int)
        for r in repo.table("credit_ledger.sqlite", "postings"):
            pid = norm_ident(rget(r, "posting_id"))
            account = self.resolve_account(rget(r, "account_ref"))
            if not pid or account is None or pid in voided:
                continue
            posted = parse_instant(rget(r, "posted_at"))
            amount = self.money_minor(rget(r, "amount_usd_cents"), "USD")
            if posted is None or not isinstance(amount, int):
                continue
            if not (self.quarter_start_ts <= posted < self.month_start):
                continue
            kind = clean_text(rget(r, "kind")).upper()
            if kind == "CREDIT":
                self.qtd[account] += amount
            elif kind == "REVERSAL":
                self.qtd[account] -= amount
        for r in repo.table("credit_ledger.sqlite", "goodwill"):
            gid = norm_ident(rget(r, "grant_id"))
            account = self.resolve_account(rget(r, "account_ref"))
            if not gid or account is None:
                continue
            granted = parse_instant(rget(r, "granted_at"))
            amount = self.money_minor(rget(r, "amount_usd_cents"), "USD")
            if granted is None or not isinstance(amount, int):
                continue
            if not (self.quarter_start_ts <= granted < self.next_start):
                continue
            self.qtd[account] += amount
        self.load_prior()

    def load_prior(self):
        if not self.prior_dir:
            return
        summary_path = os.path.join(self.prior_dir, "summary.json")
        records_path = os.path.join(self.prior_dir, "normalized.jsonl")
        if not os.path.exists(summary_path) or not os.path.exists(records_path):
            return
        try:
            with open(summary_path, "rb") as fh:
                summary = json.loads(fh.read().decode("utf-8"))
        except Exception:
            return
        period = summary.get("period")
        if not isinstance(period, str) or not re.fullmatch(r"\d{4}-\d{2}", period):
            return
        year, month = (int(x) for x in period.split("-"))
        if (year, (month - 1) // 3) != (self.month_start.year,
                                        (self.month_start.month - 1) // 3):
            return
        if dt.date(year, month, 1) >= self.month_start.date():
            return
        with open(records_path, "rb") as fh:
            for line in fh.read().decode("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("status") != "CREDITED":
                    continue
                account = rec.get("account_id")
                amount = rec.get("credit_usd_cents")
                if isinstance(account, str) and isinstance(amount, int):
                    self.qtd[account] += amount


    # ------------------------------------------------------------ windows --

    def load_windows(self):
        self.load_suspensions()
        self.load_maintenance()
        self.load_outages()
        self.load_incidents()
        self.load_dependencies()
        self.load_telemetry()

    # suspensions --------------------------------------------------------
    def load_suspensions(self):
        repo = self.repo
        events = defaultdict(list)
        for r in repo.first_table("lifecycle_events.log"):
            eid = norm_ident(rget(r, "event_id"))
            sid = norm_ident(rget(r, "subscription"))
            if not eid or not sid:
                continue
            action = clean_text(rget(r, "event")).upper()
            if action not in ("SUSPEND", "RESUME"):
                continue
            when = parse_instant(rget(r, "_ts"))
            if when is None:
                continue
            events[sid].append((when, eid, action))
        self.suspended = defaultdict(int)
        for sid, lst in events.items():
            lst.sort(key=lambda x: (x[0], x[1]))
            start = None
            mask = 0
            for when, _, action in lst:
                if action == "SUSPEND":
                    if start is None:
                        start = when
                else:
                    if start is not None:
                        mask |= self.interval_mask(start, when)
                        start = None
            if start is not None:
                mask |= self.interval_mask(start, self.next_start)
            if mask:
                self.suspended[sid] |= mask
        for r in repo.all_rows("suspension_orders.pdf"):
            oid = norm_ident(rget(r, "order_id"))
            sid = norm_ident(rget(r, "subscription"))
            if not oid or not sid:
                continue
            if clean_text(rget(r, "status")).upper() != "ACTIVE":
                continue
            start = parse_instant(rget(r, "from"))
            end = parse_instant(rget(r, "to"))
            mask = self.interval_mask(start, end)
            if mask:
                self.suspended[sid] |= mask

    # maintenance --------------------------------------------------------
    def load_maintenance(self):
        repo = self.repo
        epoch = repo.epoch_of("maintenance_changes.xlsx")
        changes = {}
        for r in repo.table("maintenance_changes.xlsx", "Changes"):
            cid = norm_ident(rget(r, "change_id"))
            if not cid:
                continue
            region = self.canon_region(rget(r, "region"))
            product = clean_text(rget(r, "product")).upper()
            kind = clean_text(rget(r, "type")).upper()
            start = _naive_local(rget(r, "start_local"), epoch)
            end = _naive_local(rget(r, "end_local"), epoch)
            if region is None or not product or start is None or end is None:
                continue
            changes[cid] = {"region": region, "product": product, "type": kind,
                            "start": start, "end": end, "utc": None}
        approvals = {}
        for r in repo.table("maintenance_changes.xlsx", "Approvals"):
            aid = norm_ident(rget(r, "approval_id"))
            cid = norm_ident(rget(r, "change_id"))
            if not aid or not cid:
                continue
            seq = parse_count(rget(r, "seq"))
            if seq is None:
                continue
            cur = approvals.get(cid)
            if cur is None or (seq, aid) > cur[0]:
                approvals[cid] = ((seq, aid), clean_text(rget(r, "decision")).upper())
        events = {}
        for ev in repo.first_table("change_calendar.ics"):
            uid = norm_ident(ev.get("UID", ("", {}))[0])
            if not uid:
                continue
            seq = parse_count(ev.get("SEQUENCE", (None, {}))[0])
            if seq is None:
                continue
            cur = events.get(uid)
            if cur is None or seq >= cur[0]:
                events[uid] = (seq, ev)
        notices = {}
        for msg in repo.first_table("maintenance_notices.mbox"):
            subject = msg.get("subject", "")
            body = msg.get("_body", "")
            cid = None
            m = re.search(r"(CHG[-_ ]?\d+)", subject) or re.search(r"(CHG[-_ ]?\d+)", body)
            if m:
                cid = norm_ident(m.group(1))
            if not cid:
                continue
            when = _parse_mail_date(msg.get("date", ""))
            if when is None:
                continue
            cur = notices.get(cid)
            if cur is None or when < cur:
                notices[cid] = when
        self.maintenance = defaultdict(int)
        for cid, info in changes.items():
            if info["type"] != "PLANNED":
                continue
            decision = approvals.get(cid)
            if decision is None or decision[1] != "APPROVED":
                continue
            zone = self.zone[info["region"]]
            start_utc = zone.to_utc(info["start"])
            end_utc = zone.to_utc(info["end"])
            ev = events.get(cid)
            if ev is not None:
                status = clean_text(ev[1].get("STATUS", ("", {}))[0]).upper()
                if status == "CANCELLED":
                    continue
                s = _ics_instant(ev[1].get("DTSTART"), self)
                e = _ics_instant(ev[1].get("DTEND"), self)
                if s is not None and e is not None:
                    start_utc, end_utc = s, e
            notice = notices.get(cid)
            if notice is None:
                continue
            site = self.region_site.get(info["region"])
            local_start = zone.to_local(start_utc).date()
            cutoff = self.step_business_days(site, local_start, 5, forward=False)
            if zone.to_local(notice).date() > cutoff:
                continue
            mask = self.interval_mask(start_utc, end_utc)
            if mask:
                self.maintenance[(info["region"], info["product"])] |= mask

    # outages ------------------------------------------------------------
    def load_outages(self):
        repo = self.repo
        targets = {}
        for r in repo.table("probe_targets.json", "targets"):
            tid = norm_ident(rget(r, "target_id"))
            if not tid:
                continue
            product = clean_text(rget(r, "product")).upper()
            region = self.canon_region(rget(r, "region"))
            if not product or region is None:
                continue
            targets[tid] = (product, region)
        successor = {}
        for r in repo.table("uptime_dashboard_snapshot.html", "Retired probe targets"):
            retired = norm_ident(rget(r, "retired_id"))
            target = norm_ident(rget(r, "target_id"))
            if retired and target:
                successor[retired] = target
        vantage = {}
        flapvoid = set()
        for r in repo.first_table("probe_results_mirror.tsv"):
            rid = norm_ident(rget(r, "row_id"))
            if not rid:
                continue
            kind = clean_text(rget(r, "kind")).upper()
            if kind == "VANTAGE":
                code = clean_text(rget(r, "vantage"))
                vid = clean_text(rget(r, "vantage_id"))
                if code and vid:
                    vantage[code] = vid
            elif kind == "FLAPVOID":
                pid = norm_ident(rget(r, "probe_id"))
                if pid:
                    flapvoid.add(pid)
        down = defaultdict(set)
        for name in ["probes_core.tsv", "probes_compute.tsv", "probes_data.tsv"]:
            for r in repo.first_table(name):
                pid = norm_ident(rget(r, "probe_id"))
                if not pid or pid in flapvoid:
                    continue
                if clean_text(rget(r, "status")).upper() != "DOWN":
                    continue
                code = clean_text(rget(r, "vantage"))
                vid = vantage.get(code)
                if not vid:
                    continue
                tid = norm_ident(rget(r, "target"))
                if not tid:
                    continue
                tid = successor.get(tid, tid)
                info = targets.get(tid)
                if info is None:
                    continue
                win = self.win_of(parse_instant(rget(r, "observed_at")))
                if win is None:
                    continue
                down[(info[0], info[1], win)].add(vid)
        self.outage = defaultdict(int)
        for (product, region, win), vids in down.items():
            if len(vids) >= 2:
                self.outage[(product, region)] |= 1 << win
        retracted = set()
        for r in repo.table("incident_register_preliminary.xml", "Retraction"):
            rid = norm_ident(rget(r, "retraction_id"))
            nid = norm_ident(rget(r, "noc_id"))
            if rid and nid:
                retracted.add(nid)
        for r in repo.all_rows("noc_outage_declarations.pdf"):
            nid = norm_ident(rget(r, "noc_id"))
            if not nid or nid in retracted:
                continue
            if clean_text(rget(r, "status")).upper() != "CONFIRMED":
                continue
            product = clean_text(rget(r, "product")).upper()
            region = self.canon_region(rget(r, "region"))
            if not product or region is None:
                continue
            mask = self.interval_mask(parse_instant(rget(r, "start")),
                                      parse_instant(rget(r, "end")))
            if mask:
                self.outage[(product, region)] |= mask

    # incidents ----------------------------------------------------------
    def load_incidents(self):
        repo = self.repo
        final_of = {}
        for r in repo.table("incident_register_preliminary.xml", "Preliminary"):
            pid = norm_ident(rget(r, "prelim_id"))
            fid = norm_ident(rget(r, "final_id"))
            if pid and fid:
                final_of[pid] = fid
        incidents = {}
        for r in repo.table("incident_register.xml", "Incident"):
            iid = norm_ident(rget(r, "incident_id"))
            if not iid:
                continue
            product = clean_text(rget(r, "product")).upper()
            region = self.canon_region(rget(r, "region"))
            opened = parse_instant(rget(r, "opened"))
            if not product or region is None or opened is None:
                continue
            closed = parse_instant(rget(r, "closed"))
            if closed is None:
                closed = self.next_start
            incidents[iid] = {"product": product, "region": region,
                              "intervals": [[opened, closed]]}
        updates = []
        for r in repo.table("incident_register.xml", "Update"):
            uid = norm_ident(rget(r, "update_id"))
            ref = norm_ident(rget(r, "ref"))
            if not uid or not ref:
                continue
            at = parse_instant(rget(r, "at"))
            until = parse_instant(rget(r, "until"))
            action = clean_text(rget(r, "action")).upper()
            if at is None:
                continue
            updates.append((at, uid, ref, action, until))
        updates.sort(key=lambda x: (x[0], x[1]))
        for at, uid, ref, action, until in updates:
            target = final_of.get(ref, ref)
            inc = incidents.get(target)
            if inc is None:
                continue
            if action == "EXTEND":
                if until is not None and until > inc["intervals"][-1][1]:
                    inc["intervals"][-1][1] = until
            elif action == "CLOSE":
                if until is not None:
                    inc["intervals"][-1][1] = until
            elif action == "REOPEN":
                if until is not None:
                    inc["intervals"].append([at, until])
        self.incident = defaultdict(int)
        for inc in incidents.values():
            mask = 0
            for start, end in inc["intervals"]:
                mask |= self.interval_mask(start, end)
            if mask:
                self.incident[(inc["product"], inc["region"])] |= mask

    # dependencies -------------------------------------------------------
    def load_dependencies(self):
        repo = self.repo
        self.product_deps = defaultdict(set)
        for r in repo.table("incident_attribution_policy.docx", "Service dependencies"):
            product = clean_text(rget(r, "product")).upper()
            upstream = clean_text(rget(r, "upstream")).upper()
            if product and upstream:
                self.product_deps[product].add(upstream)
        events = defaultdict(list)
        sources = [("dependency_links.tsv", None),
                   ("incident_attribution_policy.docx", "Dependency declarations")]
        for name, table in sources:
            rows = repo.table(name, table) if table else repo.first_table(name)
            for r in rows:
                lid = norm_ident(rget(r, "link_id"))
                down = norm_ident(rget(r, "downstream"))
                up = norm_ident(rget(r, "upstream"))
                if not lid or not down or not up:
                    continue
                when = parse_instant(rget(r, "registered_at"))
                action = clean_text(rget(r, "action")).upper()
                if when is None or action not in ("ADD", "REMOVE"):
                    continue
                events[(down, up)].append((when, lid, action))
        self.link_mask = {}
        for pair, lst in events.items():
            lst.sort(key=lambda x: (x[0], x[1]))
            mask = 0
            open_at = None
            for when, _, action in lst:
                if action == "ADD":
                    if open_at is None:
                        open_at = when
                else:
                    if open_at is not None:
                        mask |= self.interval_mask(open_at, when)
                        open_at = None
            if open_at is not None:
                mask |= self.interval_mask(open_at, self.next_start)
            if mask:
                self.link_mask[pair] = mask

    # telemetry ----------------------------------------------------------
    def load_telemetry(self):
        repo = self.repo
        registrations = {}
        for r in repo.first_table("ingest_batches.jsonl"):
            bid = norm_ident(rget(r, "batch_id"))
            if not bid:
                continue
            loaded = parse_instant(rget(r, "loaded_at"))
            if loaded is None:
                continue
            cur = registrations.get(bid)
            if cur is None or (loaded, bid) > cur[0]:
                registrations[bid] = ((loaded, bid), clean_text(rget(r, "status")).upper())
        replays = set()
        for r in repo.first_table("ingest_reprocess.log"):
            if clean_text(rget(r, "event")).upper() != "REPLAY":
                continue
            bid = norm_ident(rget(r, "batch"))
            if bid:
                replays.add(bid)
        self.batch_ok = {bid: (status == "LOADED" and bid not in replays)
                         for bid, (_, status) in registrations.items()}
        voids = {}
        for r in repo.first_table("telemetry_voids.jsonl"):
            vid = norm_ident(rget(r, "void_id"))
            target = norm_ident(rget(r, "target"))
            if not vid or not target:
                continue
            at = parse_instant(rget(r, "at"))
            if at is None:
                continue
            cur = voids.get(target)
            if cur is None or (at, vid) > cur[0]:
                voids[target] = ((at, vid), clean_text(rget(r, "action")).upper())
        self.voided = {t for t, (_, action) in voids.items() if action == "VOID"}
        for r in repo.first_table("lb_errors_east_replay.csv"):
            if clean_text(rget(r, "marker")).upper() != "VOID":
                continue
            rid = norm_ident(rget(r, "record_id"))
            if rid:
                self.voided.add(rid)
        node_host = {}
        for r in repo.first_table("svc_metrics_compacted.parquet"):
            cid = norm_ident(rget(r, "record_id"))
            if not cid:
                continue
            kind = clean_text(rget(r, "kind")).upper()
            if kind == "TOMBSTONE":
                target = norm_ident(rget(r, "target"))
                if target:
                    self.voided.add(target)
            elif kind == "ALIAS":
                node = clean_text(rget(r, "node")).lower()
                host = clean_text(rget(r, "host")).lower()
                if node and host:
                    node_host[node] = host
        self.host_info = {}
        for r in repo.first_table("host_inventory.csv"):
            host = clean_text(rget(r, "host")).lower()
            region = self.canon_region(rget(r, "region"))
            product = clean_text(rget(r, "product")).upper()
            if host and region is not None and product:
                self.host_info[host] = (region, product)
        lanes = {}
        for r in repo.table("telemetry_collection_standard.docx", "Host lane assignments"):
            host = clean_text(rget(r, "host")).lower()
            lane = clean_text(rget(r, "lane")).upper()
            assigned = parse_date(rget(r, "assigned_on"))
            if not host or not lane or assigned is None or assigned > self.last_day:
                continue
            cur = lanes.get(host)
            if cur is None or assigned >= cur[0]:
                lanes[host] = (assigned, lane)
        self.host_lane = {host: lane for host, (_, lane) in lanes.items()}
        self.quarantine = defaultdict(list)
        for r in repo.table("telemetry_quarantine.json", "quarantine"):
            qid = norm_ident(rget(r, "quarantine_id"))
            if not qid:
                continue
            if clean_text(rget(r, "status")).upper() != "ACTIVE":
                continue
            host = clean_text(rget(r, "host")).lower()
            start = parse_instant(rget(r, "from"))
            end = parse_instant(rget(r, "to"))
            if not host or start is None or end is None:
                continue
            self.quarantine[host].append((start, end))
        self.sampling = defaultdict(list)
        for r in repo.first_table("lb_sampling.parquet"):
            sid = norm_ident(rget(r, "sampling_id"))
            if not sid:
                continue
            host = clean_text(rget(r, "host")).lower()
            eff = parse_instant(rget(r, "effective_from"))
            factor = parse_count(rget(r, "one_in"))
            if not host or eff is None or factor is None:
                continue
            self.sampling[host].append((eff, sid, factor))
        for lst in self.sampling.values():
            lst.sort(key=lambda x: (x[0], x[1]))
        self.load_schemas()
        self.gaps = []
        for r in repo.table("telemetry_collection_standard.docx", "Collector gap windows"):
            gid = norm_ident(rget(r, "gap_id"))
            if not gid:
                continue
            region = self.canon_region(rget(r, "region"))
            collector = clean_text(rget(r, "collector")).upper()
            start = parse_instant(rget(r, "from"))
            end = parse_instant(rget(r, "to"))
            if region is None or not collector or start is None or end is None:
                continue
            self.gaps.append((region, collector, start, end))
        self.used = defaultdict(dict)
        self.collect_lb(node_host)
        self.collect_svc(node_host)
        self.collect_edge()
        self.collect_cdn()
        self.collect_sdk()

    def load_schemas(self):
        repo = self.repo
        waves = defaultdict(dict)
        for r in repo.first_table("deploy_manifests.xml"):
            mid = norm_ident(rget(r, "member_id"))
            if not mid:
                continue
            wave = clean_text(rget(r, "wave"))
            revision = parse_count(rget(r, "revision"))
            host = clean_text(rget(r, "host")).lower()
            if not wave or revision is None or not host:
                continue
            waves[wave].setdefault(revision, []).append(host)
        wave_hosts = {}
        for wave, revs in waves.items():
            top = max(revs)
            wave_hosts[wave] = revs[top]
        aborted = set()
        for r in repo.table("collector_schema_proposed.yaml", "aborted_rollouts"):
            eid = norm_ident(rget(r, "event_id"))
            if eid:
                aborted.add(eid)
        self.host_schema_events = defaultdict(list)
        for r in repo.first_table("deploy_events.log"):
            eid = norm_ident(rget(r, "event_id"))
            if not eid or eid in aborted:
                continue
            action = clean_text(rget(r, "event")).upper()
            if action not in ("ROLLOUT", "ROLLBACK"):
                continue
            seq = parse_count(rget(r, "seq"))
            when = parse_instant(rget(r, "_ts"))
            schema = clean_text(rget(r, "schema")).lower()
            wave = clean_text(rget(r, "wave"))
            if seq is None or when is None or not schema or not wave:
                continue
            for host in wave_hosts.get(wave, ()):
                self.host_schema_events[host].append((when, seq, schema))
        self.baseline_schema = {}
        for r in repo.table("schema_registry.yaml", "baseline"):
            host = clean_text(rget(r, "host")).lower()
            schema = clean_text(rget(r, "schema")).lower()
            if host and schema:
                self.baseline_schema[host] = schema
        self.schema_includes_429 = {}
        for r in repo.table("schema_registry.yaml", "versions"):
            version = clean_text(rget(r, "version")).lower()
            flag = rget(r, "err_5xx_includes_429")
            if isinstance(flag, str):
                flag = clean_text(flag).upper() in ("TRUE", "Y", "YES", "1")
            self.schema_includes_429[version] = bool(flag)

    def schema_at(self, host, when):
        best = None
        for ts, seq, schema in self.host_schema_events.get(host, ()):
            if ts <= when and (best is None or seq > best[0]):
                best = (seq, schema)
        if best is not None:
            return best[1]
        return self.baseline_schema.get(host, "v1")

    def quarantined(self, host, when):
        for start, end in self.quarantine.get(host, ()):
            if start <= when < end:
                return True
        return False

    def sampling_factor(self, host, when):
        factor = 1
        for eff, _, value in self.sampling.get(host, ()):
            if eff <= when:
                factor = value
            else:
                break
        return factor

    def window_start(self, win):
        return self.month_start + dt.timedelta(seconds=300 * win)

    def offer(self, sid, win, prec, seq, rid, requests, e5, e429):
        """Keep the record of lowest precedence, then highest seq, then identifier."""
        slot = self.used[sid]
        cur = slot.get(win)
        if cur is not None:
            best_prec, best_seq, best_rid = cur[0]
            if prec > best_prec:
                return
            if prec == best_prec:
                if seq < best_seq:
                    return
                if seq == best_seq and rid <= best_rid:
                    return
        slot[win] = ((prec, seq, rid), requests, e5, e429)

    def valid(self, sid, win, host, bid, rid, lane):
        sub = self.subs.get(sid)
        if sub is None or win is None:
            return False
        if not (sub.active_mask >> win) & 1:
            return False
        if not self.batch_ok.get(bid, False):
            return False
        if rid in self.voided:
            return False
        if host is not None:
            info = self.host_info.get(host)
            if info is None or info[0] != sub.region or info[1] != sub.product:
                return False
            if self.host_lane.get(host) != lane:
                return False
            if self.quarantined(host, self.window_start(win)):
                return False
        return True

    def collect_lb(self, node_host):
        repo = self.repo
        files = ["lb_errors_central.csv", "lb_errors_east.csv", "lb_errors_north.csv",
                 "lb_errors_south.csv", "lb_errors_west.csv"]
        for name in files:
            for r in repo.first_table(name):
                self._lb_row(r)
        for r in repo.first_table("lb_errors_east_replay.csv"):
            if clean_text(rget(r, "marker")).upper() != "GAPFILL":
                continue
            self._lb_row(r, gapfill=True)

    def _lb_row(self, r, gapfill=False):
        rid = norm_ident(rget(r, "record_id"))
        sid = norm_ident(rget(r, "subscription"))
        bid = norm_ident(rget(r, "batch_id"))
        if not rid or not sid or not bid:
            return
        host = clean_text(rget(r, "host")).lower()
        when = parse_instant(rget(r, "window_start"))
        win = self.win_of(when)
        counts = [parse_count(rget(r, f)) for f in
                  ("requests", "err_5xx", "err_429", "err_4xx")]
        seq = parse_count(rget(r, "seq"))
        if seq is None or any(c is None for c in counts):
            return
        if not self.valid(sid, win, host, bid, rid, "LB"):
            return
        start = self.window_start(win)
        if gapfill:
            info = self.host_info.get(host)
            region = info[0] if info else None
            if not any(region == g[0] and g[1] == "LB" and g[2] <= start < g[3]
                       for g in self.gaps):
                return
        factor = self.sampling_factor(host, start)
        requests, e5, e429 = counts[0] * factor, counts[1] * factor, counts[2] * factor
        if self.schema_includes_429.get(self.schema_at(host, start), False):
            e5 = e5 - e429
        self.offer(sid, win, 1, seq, rid, requests, e5, e429)

    def collect_svc(self, node_host):
        repo = self.repo
        for name in ["svc_metrics_part1.parquet", "svc_metrics_part2.parquet",
                     "svc_metrics_part3.parquet"]:
            for r in repo.first_table(name):
                rid = norm_ident(rget(r, "record_id"))
                sid = norm_ident(rget(r, "subscription"))
                bid = norm_ident(rget(r, "batch_id"))
                if not rid or not sid or not bid:
                    continue
                node = clean_text(rget(r, "node")).lower()
                host = node_host.get(node)
                if host is None:
                    continue
                win = self.win_of(parse_instant(rget(r, "window_start_ms")))
                raw_k = rget(r, "requests_k")
                if raw_k is not None:
                    requests = (None if parse_count(raw_k) is None
                                else round_half_even(parse_decimal(raw_k) * 1000))
                else:
                    requests = parse_count(rget(r, "requests"))
                e5 = parse_count(rget(r, "err_5xx"))
                e429 = parse_count(rget(r, "err_429"))
                e4 = parse_count(rget(r, "err_4xx"))
                seq = parse_count(rget(r, "seq"))
                if None in (requests, e5, e429, e4, seq):
                    continue
                if not self.valid(sid, win, host, bid, rid, "SVC"):
                    continue
                self.offer(sid, win, 2, seq, rid, requests, e5, e429)

    def collect_edge(self):
        repo = self.repo
        skews = defaultdict(list)
        for name in ["host_clock_edge_a.ini", "host_clock_edge_b.ini",
                     "host_clock_edge_c.ini"]:
            for r in repo.first_table(name):
                host = clean_text(rget(r, "host")).lower()
                when = parse_instant(rget(r, "measured_at"))
                skew = parse_count(rget(r, "skew_s"))
                if not host or when is None or skew is None:
                    continue
                skews[host].append((when, skew))
        for lst in skews.values():
            lst.sort(key=lambda x: x[0])
        for name in ["edge_legacy_a.txt", "edge_legacy_b.txt", "edge_legacy_c.txt"]:
            for r in repo.first_table(name):
                rid = norm_ident(rget(r, "record_id"))
                sid = norm_ident(rget(r, "subscription"))
                bid = norm_ident(rget(r, "batch_id"))
                if not rid or not sid or not bid:
                    continue
                host = clean_text(rget(r, "host")).lower()
                info = self.host_info.get(host)
                counts = [parse_count(rget(r, f)) for f in
                          ("requests", "err_5xx", "err_429", "err_4xx")]
                seq = parse_count(rget(r, "seq"))
                if info is None or seq is None or any(c is None for c in counts):
                    continue
                naive = _naive_local(rget(r, "reading"), EPOCH_1900)
                if naive is None:
                    continue
                zone = self.zone[info[0]]
                raw = zone.to_utc(naive)
                skew = 0
                for when, value in skews.get(host, ()):
                    if when <= raw:
                        skew = value
                    else:
                        break
                true_instant = raw - dt.timedelta(seconds=skew)
                win = self.win_of(true_instant)
                if not self.valid(sid, win, host, bid, rid, "EDGE"):
                    continue
                self.offer(sid, win, 3, seq, rid, counts[0], counts[1], counts[2])

    def collect_cdn(self):
        repo = self.repo
        epoch = repo.epoch_of("cdn_attestations.xlsx")
        for t in repo.tables("cdn_attestations.xlsx"):
            for r in t.rows:
                self._cdn_row(r, 4, epoch, "window_start")
        for name in ["cdn_logs_akamoto.xml", "cdn_logs_fastedge.xml"]:
            for r in repo.first_table(name):
                self._cdn_row(r, 5, EPOCH_1900, "window_epoch")

    def _cdn_row(self, r, prec, epoch, time_field):
        rid = norm_ident(rget(r, "record_id"))
        sid = norm_ident(rget(r, "subscription"))
        bid = norm_ident(rget(r, "batch_id"))
        if not rid or not sid or not bid:
            return
        host = clean_text(rget(r, "host")).lower()
        counts = [parse_count(rget(r, f)) for f in
                  ("requests", "err_5xx", "err_429", "err_4xx")]
        seq = parse_count(rget(r, "seq"))
        if seq is None or any(c is None for c in counts):
            return
        win = self.win_of(parse_instant(rget(r, time_field), serial_epoch=epoch))
        if not self.valid(sid, win, host, bid, rid, "CDN"):
            return
        self.offer(sid, win, prec, seq, rid, counts[0], counts[1], counts[2])

    def collect_sdk(self):
        repo = self.repo
        install_sub = {}
        withdrawn_builds = set()
        for r in repo.first_table("client_sdk_dedup.jsonl"):
            rid = norm_ident(rget(r, "record_id"))
            if not rid:
                continue
            kind = clean_text(rget(r, "kind")).upper()
            if kind == "INSTALL":
                install = norm_ident(rget(r, "install_id"))
                sid = norm_ident(rget(r, "subscription"))
                if install and sid:
                    install_sub[install] = sid
            elif kind == "WITHDRAWN_BUILD":
                build = clean_text(rget(r, "build"))
                if build:
                    withdrawn_builds.add(build)
        builds = {}
        for r in repo.table("sdk_builds.json", "builds"):
            build = clean_text(rget(r, "build"))
            if not build:
                continue
            builds[build] = (clean_text(rget(r, "clock")).upper(),
                             clean_text(rget(r, "status")).upper())
        receipts = {}
        for r in repo.first_table("sdk_server_receipts.csv"):
            eid = norm_ident(rget(r, "event_id"))
            if not eid:
                continue
            when = parse_instant(rget(r, "received_at"))
            if when is not None:
                receipts[eid] = when
        for name in ["sdk_events_1.jsonl", "sdk_events_2.jsonl", "sdk_events_3.jsonl"]:
            for r in repo.first_table(name):
                eid = norm_ident(rget(r, "event_id"))
                install = norm_ident(rget(r, "install_id"))
                bid = norm_ident(rget(r, "batch_id"))
                if not eid or not install or not bid:
                    continue
                sid = install_sub.get(install)
                if not sid:
                    continue
                build = clean_text(rget(r, "build"))
                info = builds.get(build)
                if info is None or info[1] == "RECALLED" or build in withdrawn_builds:
                    continue
                if info[0] == "DEVICE":
                    when = receipts.get(eid)
                else:
                    when = parse_instant(rget(r, "ts"))
                requests = parse_count(rget(r, "requests"))
                e5 = parse_count(rget(r, "errors_5xx"))
                e429 = parse_count(rget(r, "errors_429"))
                e4 = parse_count(rget(r, "errors_4xx"))
                seq = parse_count(rget(r, "seq"))
                if None in (requests, e5, e429, e4, seq) or when is None:
                    continue
                win = self.win_of(when)
                if not self.valid(sid, win, None, bid, eid, "NONE"):
                    continue
                self.offer(sid, win, 6, seq, eid, requests, e5, e429)


    # ------------------------------------------------------------ grading --

    def load_beta(self):
        self.beta = set()
        for r in self.repo.table("uptime_dashboard_snapshot.html", "Beta product-regions"):
            bid = clean_text(rget(r, "beta_id"))
            if not bid:
                continue
            product = clean_text(rget(r, "product")).upper()
            region = self.canon_region(rget(r, "region"))
            start = parse_date(rget(r, "beta_from"))
            end = parse_date(rget(r, "beta_to"))
            if not product or region is None or start is None:
                continue
            if start <= self.last_day and (end is None or end > self.last_day):
                self.beta.add((product, region))

    def index_subs(self):
        self.by_account_region = defaultdict(list)
        for sub in self.subs.values():
            sub.account = self.resolve_account(sub.account_raw)
            if sub.account is not None and sub.active_days > 0:
                self.by_account_region[(sub.account, sub.region)].append(sub)

    def attribute(self, sub, bad):
        if not bad:
            return 0
        upstream_products = self.product_deps.get(sub.product)
        if not upstream_products:
            return 0
        result = 0
        for other in self.by_account_region.get((sub.account, sub.region), ()):
            if other.sid == sub.sid or other.product not in upstream_products:
                continue
            incident = self.incident.get((other.product, sub.region), 0)
            if not incident:
                continue
            link = self.link_mask.get((sub.sid, other.sid), 0)
            if not link:
                continue
            result |= bad & incident & link & other.active_mask
        return result

    def grade(self):
        """Per-subscription results and exclusions."""
        self.load_beta()
        self.index_subs()
        self.exclusions = []
        results = []
        for sid in self.in_period:
            sub = self.subs[sid]
            reason = None
            sla_class = None
            if sub.account is None:
                reason = "UNKNOWN_ACCOUNT"
            elif self.is_internal(sub.account):
                reason = "INTERNAL_ACCOUNT"
            elif (sub.product, sub.region) in self.beta:
                reason = "BETA_PRODUCT_REGION"
            else:
                action, cls = self.enrollment.get(sid, (None, None))
                if action != "ENROLLED" or not cls:
                    reason = "NO_SLA_ENROLLMENT"
                else:
                    sla_class = cls
            if reason is not None:
                self.exclusions.append({"subscription_id": sid, "reason": reason})
                continue
            results.append(self.grade_one(sub, sla_class))
        self.results = results

    def grade_one(self, sub, sla_class):
        plan = self.plan_of(sub)
        segment = self.plan_segment.get(plan, "")
        version = self.version_of(sub, segment)
        target = self.target_of(sub, version, sla_class)
        active = sub.active_mask
        suspended = self.suspended.get(sub.sid, 0) & active
        rest = active & ~suspended
        maintenance = self.maintenance.get((sub.region, sub.product), 0) & rest
        eligible = rest & ~maintenance
        outage = self.outage.get((sub.product, sub.region), 0) & eligible
        used = self.used.get(sub.sid) or {}
        permille = self.permille.get(version)
        telemetry = 0
        bad_telemetry = 0
        for win, (_, requests, e5, e429) in used.items():
            if not (eligible >> win) & 1:
                continue
            telemetry |= 1 << win
            quota = self.quota_at(sub.sid, self.window_start(win))
            counted = e429 if (quota is None or requests <= quota) else 0
            if (permille is not None and requests > 0
                    and (e5 + counted) * 1000 >= permille * requests):
                bad_telemetry |= 1 << win
        bad = bad_telemetry | outage
        attributed = self.attribute(sub, bad)
        bad &= ~attributed
        n_eligible = eligible.bit_count()
        n_bad = bad.bit_count()
        if n_eligible:
            uptime = (Decimal(100) * (n_eligible - n_bad)) / Decimal(n_eligible)
        else:
            uptime = Decimal(100)
        credit_pct = self.credit_pct_of(sub, version, uptime, target)
        fee = self.fee_of(sub, plan)
        credit_minor = round_half_even(
            Decimal(fee) * sub.active_days * credit_pct / (Decimal(self.days) * 100))
        claim = self.claim_for(sub, segment)
        auto = segment == "enterprise" or (
            segment == "corporate" and sub.account in self.auto_credit)
        if auto:
            claim_id = "AUTO"
            filed = self.next_start - dt.timedelta(hours=1)
            claim_filed = None
        elif claim is not None:
            claim_id = claim[1]
            filed = claim[0]
            claim_filed = filed
        else:
            claim_id = None
            filed = None
            claim_filed = None
        exponent = self.currencies.get(sub.currency, 2)
        rate = self.rate_at(sub.currency, filed) if filed is not None else None
        if rate is not None:
            usd = round_half_even(
                Decimal(credit_minor) / (10 ** exponent) * rate * 100)
        else:
            usd = 0
        cap = self.cap.get(sub.account)
        return {
            "subscription_id": sub.sid,
            "account_id": sub.account,
            "product": sub.product,
            "region": sub.region,
            "region_group": self.region_group.get(sub.region, ""),
            "segment": segment,
            "plan": plan,
            "sla_class": sla_class,
            "sla_version": version,
            "target_pct": _fmt(target, 3) if target is not None else None,
            "currency": sub.currency,
            "fee_minor": fee,
            "active_days": sub.active_days,
            "active_windows": active.bit_count(),
            "suspended_windows": suspended.bit_count(),
            "maintenance_windows": maintenance.bit_count(),
            "eligible_windows": n_eligible,
            "telemetry_windows": telemetry.bit_count(),
            "outage_windows": outage.bit_count(),
            "bad_windows": n_bad,
            "attributed_windows": attributed.bit_count(),
            "bad_window_digest": _digest(bad),
            "uptime_pct": _fmt(uptime, 3),
            "credit_pct": credit_pct,
            "credit_minor": credit_minor,
            "claim_id": claim_id,
            "claim_filed_utc": _fmt_instant(claim_filed),
            "fx_rate": _fmt(rate, 6) if rate is not None else None,
            "credit_usd_cents": usd,
            "qtd_before_usd_cents": 0,
            "cap_usd_cents": cap[1] if cap is not None else None,
            "status": "MET",
        }

    def apply_caps(self):
        by_account = defaultdict(list)
        for rec in self.results:
            by_account[rec["account_id"]].append(rec)
        for account, recs in by_account.items():
            total = self.qtd.get(account, 0)
            cap = self.cap.get(account)
            limit = cap[1] if cap is not None else None
            for rec in sorted(recs, key=lambda r: r["subscription_id"]):
                rec["qtd_before_usd_cents"] = total
                if rec["credit_pct"] <= 0:
                    rec["status"] = "MET"
                    continue
                if rec["claim_id"] is None:
                    rec["status"] = "UNCLAIMED"
                    continue
                amount = rec["credit_usd_cents"]
                if limit is None or total + amount <= limit:
                    rec["status"] = "CREDITED"
                    total += amount
                else:
                    rec["status"] = "CAP_EXHAUSTED"
        self.results.sort(key=lambda r: r["subscription_id"])


def _fmt(value, places):
    if value is None:
        return None
    q = Decimal(1).scaleb(-places)
    return str(Decimal(value).quantize(q, rounding=ROUND_HALF_EVEN))


def _fmt_instant(when):
    if when is None:
        return None
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest(mask):
    indices = []
    value = mask
    while value:
        low = value & -value
        indices.append(low.bit_length() - 1)
        value ^= low
    text = ",".join(str(i) for i in indices)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _naive_local(value, epoch):
    """Naive local wall-clock datetime from a serial, ISO text or YYYYMMDDHHMMSS."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return epoch.replace(tzinfo=None) + dt.timedelta(seconds=round(float(value) * 86400))
    s = clean_text(value)
    if s == "":
        return None
    if re.fullmatch(r"\d{14}", s):
        return dt.datetime.strptime(s, "%Y%m%d%H%M%S")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return epoch.replace(tzinfo=None) + dt.timedelta(seconds=round(float(s) * 86400))
    try:
        parsed = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _parse_mail_date(text):
    import email.utils

    if not text:
        return None
    try:
        when = email.utils.parsedate_to_datetime(text)
    except Exception:
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        return when.replace(tzinfo=UTC)
    return when.astimezone(UTC)


def _ics_instant(prop, close):
    if not prop:
        return None
    value, params = prop
    value = clean_text(value)
    if not value:
        return None
    tzid = params.get("TZID")
    if value.endswith("Z"):
        return dt.datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    naive = None
    if re.fullmatch(r"\d{8}T\d{6}", value):
        naive = dt.datetime.strptime(value, "%Y%m%dT%H%M%S")
    elif re.fullmatch(r"\d{8}", value):
        naive = dt.datetime.strptime(value, "%Y%m%d")
    if naive is None:
        return None
    zone = close.tz_by_id.get(tzid) if tzid else None
    if zone is None:
        return naive.replace(tzinfo=UTC)
    return zone.to_utc(naive)


# --------------------------------------------------------------- outputs -----

STATUSES = ("CAP_EXHAUSTED", "CREDITED", "MET", "UNCLAIMED")
REGION_GROUPS = ("central", "east", "north", "south", "west")
SEGMENTS = ("consumer", "corporate", "enterprise", "smb")


def empty_status_counts():
    return {s: 0 for s in STATUSES}


def write_json(path, doc):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, sort_keys=True, indent=2, ensure_ascii=False)
        fh.write("\n")


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=False))
            fh.write("\n")


def write_outputs(out_dir, close, sources, recon, held_reasons):
    os.makedirs(out_dir, exist_ok=True)
    names = ["normalized.jsonl", "summary.json", "data_quality.json",
             "product_summary.json"]
    names += ["region_%s.json" % g for g in REGION_GROUPS]
    names += ["segment_%s.json" % s for s in SEGMENTS]
    if held_reasons:
        write_jsonl(os.path.join(out_dir, "normalized.jsonl"), [])
        write_json(os.path.join(out_dir, "summary.json"),
                   {"status": "HELD", "period": close.period,
                    "held_reasons": held_reasons})
        write_json(os.path.join(out_dir, "data_quality.json"),
                   {"sources": sorted(sources, key=lambda s: s["file"]),
                    "exclusions": []})
        for name in names:
            if name in ("normalized.jsonl", "summary.json", "data_quality.json"):
                continue
            write_json(os.path.join(out_dir, name), {"status": "HELD"})
        return
    records = close.results
    write_jsonl(os.path.join(out_dir, "normalized.jsonl"), records)
    status_counts = empty_status_counts()
    credited = 0
    minor_by_currency = defaultdict(int)
    eligible = bad = attributed = 0
    for rec in records:
        status_counts[rec["status"]] += 1
        eligible += rec["eligible_windows"]
        bad += rec["bad_windows"]
        attributed += rec["attributed_windows"]
        if rec["status"] == "CREDITED":
            credited += rec["credit_usd_cents"]
            minor_by_currency[rec["currency"]] += rec["credit_minor"]
    write_json(os.path.join(out_dir, "summary.json"), {
        "status": "PUBLISHED",
        "period": close.period,
        "records": len(records),
        "excluded": len(close.exclusions),
        "status_counts": status_counts,
        "credited_usd_cents": credited,
        "credit_minor_by_currency": dict(minor_by_currency),
        "eligible_windows": eligible,
        "bad_windows": bad,
        "attributed_windows": attributed,
        "reconciliation": recon,
    })
    write_json(os.path.join(out_dir, "data_quality.json"), {
        "sources": sorted(sources, key=lambda s: s["file"]),
        "exclusions": sorted(close.exclusions, key=lambda e: e["subscription_id"]),
    })
    products = {}
    for rec in records:
        entry = products.setdefault(rec["product"], {
            "records": 0, "eligible_windows": 0, "bad_windows": 0,
            "attributed_windows": 0, "credited_usd_cents": 0,
            "status_counts": empty_status_counts()})
        entry["records"] += 1
        entry["eligible_windows"] += rec["eligible_windows"]
        entry["bad_windows"] += rec["bad_windows"]
        entry["attributed_windows"] += rec["attributed_windows"]
        entry["status_counts"][rec["status"]] += 1
        if rec["status"] == "CREDITED":
            entry["credited_usd_cents"] += rec["credit_usd_cents"]
    write_json(os.path.join(out_dir, "product_summary.json"), {"products": products})
    for group in REGION_GROUPS:
        doc = {"region_group": group, "records": 0,
               "status_counts": empty_status_counts(), "credited_usd_cents": 0,
               "regions": {}}
        for rec in records:
            if rec["region_group"] != group:
                continue
            doc["records"] += 1
            doc["status_counts"][rec["status"]] += 1
            entry = doc["regions"].setdefault(rec["region"], {
                "records": 0, "eligible_windows": 0, "bad_windows": 0,
                "credited_usd_cents": 0})
            entry["records"] += 1
            entry["eligible_windows"] += rec["eligible_windows"]
            entry["bad_windows"] += rec["bad_windows"]
            if rec["status"] == "CREDITED":
                doc["credited_usd_cents"] += rec["credit_usd_cents"]
                entry["credited_usd_cents"] += rec["credit_usd_cents"]
        write_json(os.path.join(out_dir, "region_%s.json" % group), doc)
    for segment in SEGMENTS:
        doc = {"segment": segment, "records": 0,
               "status_counts": empty_status_counts(), "credited_usd_cents": 0,
               "plans": {}}
        for rec in records:
            if rec["segment"] != segment:
                continue
            doc["records"] += 1
            doc["status_counts"][rec["status"]] += 1
            entry = doc["plans"].setdefault(rec["plan"], {
                "records": 0, "credited_usd_cents": 0})
            entry["records"] += 1
            if rec["status"] == "CREDITED":
                doc["credited_usd_cents"] += rec["credit_usd_cents"]
                entry["credited_usd_cents"] += rec["credit_usd_cents"]
        write_json(os.path.join(out_dir, "segment_%s.json" % segment), doc)


# ------------------------------------------------------------------- main ----


def run(data_dir, out_dir, prior_dir=None):
    repo = Repo(data_dir)
    close = Close(repo, prior_dir)
    repo.catalog = {entry["file"]: entry for entry in close.catalog}
    layouts = {}
    try:
        layouts["V6"] = [(clean_text(rget(r, "field")), parse_count(rget(r, "width")))
                         for r in repo.table("telemetry_collection_standard.docx",
                                             "Edge record layout V6")]
    except Exception:
        layouts["V6"] = []
    try:
        layouts["V7"] = [(clean_text(rget(r, "field")), parse_count(rget(r, "width")))
                         for r in repo.table("collector_schema_proposed.yaml",
                                             "edge_layout_v7")]
    except Exception:
        layouts["V7"] = []
    repo.fwf_layouts = layouts
    sources, held_reasons, recon = check_controls(repo, close.catalog)
    if not held_reasons:
        close.load_reference()
        close.load_windows()
        close.grade()
        close.apply_caps()
    write_outputs(out_dir, close, sources, recon, held_reasons)
    return close


def main(argv):
    args = []
    prior = None
    i = 0
    while i < len(argv):
        if argv[i] == "--prior":
            prior = argv[i + 1]
            i += 2
            continue
        args.append(argv[i])
        i += 1
    data_dir = args[0] if len(args) > 0 else "/app/data"
    out_dir = args[1] if len(args) > 1 else "/app/out"
    run(data_dir, out_dir, prior)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
