#!/usr/bin/env python3
"""Recompute the CBHS quarterly streamflow record from a data directory.

Usage: python3 run_flowrecord.py DATA_DIR OUT_DIR

The program reads only DATA_DIR, writes the twenty-one contract reports and manifest.json into OUT_DIR,
and follows hydrometry_handbook.md (H1 to H18), feed_layouts.md and output_contract.md.
"""
import csv
import hashlib
import io
import json
import math
import os
import re
import sqlite3
import sys
import zipfile
import zlib
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction

UTC = timezone.utc
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
FEET_PER = {"FT": Fraction(1), "M": Fraction(10000, 3048), "CM": Fraction(100, 3048), "MM": Fraction(10, 3048)}
CMS_PER_CFS = Fraction("0.028316846592")
REPORT_ORDER = ["unit_values.csv", "gh_corrections.tsv", "visit_errors.psv", "measurement_eval.csv", "shift_curves.json",
                "ice_periods.jsonl", "rating_tables_used.json", "daily_values.csv", "monthly_summary.xml", "period_statistics.json",
                "alias_resolution.csv", "dedup_report.json", "source_lineage.json", "reading_exclusions.jsonl", "amendment_ledger.psv",
                "parameters_used.yaml", "variance_vs_published.csv", "shift_vs_published.csv", "dashboard_disagreements.tsv",
                "cache_divergence.jsonl", "reconciliation.md"]


# ============================================================================ numbers
def exact(text):
    """Exact rational of a decimal text."""
    if isinstance(text, Fraction):
        return text
    s = str(text).strip().replace(",", ".")
    return Fraction(Decimal(s))


def round_to(x, exponent):
    """Half-even rounding of a rational to a multiple of 10**exponent."""
    x = Fraction(x)
    scale = Fraction(10) ** exponent
    v = x / scale
    whole = math.floor(v)
    frac = v - whole
    if frac > Fraction(1, 2) or (frac == Fraction(1, 2) and whole % 2):
        whole += 1
    return whole * scale


def dp(x, n):
    return round_to(x, -n)


def magnitude(x):
    """floor(log10(|x|)) of a nonzero rational."""
    x = abs(Fraction(x))
    k = len(str(x.numerator)) - len(str(x.denominator))
    while x >= Fraction(10) ** (k + 1):
        k += 1
    while x < Fraction(10) ** k:
        k -= 1
    return k


def sig(x, n):
    x = Fraction(x)
    if x == 0:
        return Fraction(0)
    return round_to(x, magnitude(x) - n + 1)


def discharge_table(x):
    x = Fraction(x)
    if x < 1:
        return dp(x, 2)
    if x < 10:
        return dp(x, 1)
    if x < 1000:
        return dp(x, 0)
    return sig(x, 3)


def show(x, places=None):
    """Plain decimal text; fixed places when given, else the shortest exact decimal."""
    if x is None:
        return ""
    x = Fraction(x)
    if places is None:
        places = 0
        while (x * 10 ** places).denominator != 1:
            places += 1
            if places > 40:
                raise ValueError("not a terminating decimal")
    else:
        x = dp(x, places)
    n = x * 10 ** places
    n = n.numerator
    neg = n < 0
    digits = str(abs(n)).rjust(places + 1, "0")
    body = digits if places == 0 else digits[:-places] + "." + digits[-places:]
    return ("-" if neg else "") + body


class Raw(str):
    """Text emitted verbatim as a JSON number."""


def jnum(x, places=None):
    return None if x is None else Raw(show(x, places))


def jdump(obj):
    if obj is None:
        return "null"
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if isinstance(obj, Raw):
        return str(obj)
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, str):
        return json.dumps(obj)
    if isinstance(obj, list):
        return "[" + ", ".join(jdump(v) for v in obj) + "]"
    if isinstance(obj, dict):
        return "{" + ", ".join(json.dumps(k) + ": " + jdump(v) for k, v in obj.items()) + "}"
    raise TypeError(obj)


def table_text(header, rows, delim):
    buf = io.StringIO()
    wr = csv.writer(buf, delimiter=delim, lineterminator="\n")
    wr.writerow(header)
    for row in rows:
        wr.writerow(["" if v is None else v for v in row])
    return buf.getvalue()


# ============================================================================ time
def civil_seconds(y, mo, d, hh=0, mi=0, ss=0):
    return (date(y, mo, d) - date(1970, 1, 1)).days * 86400 + hh * 3600 + mi * 60 + ss


def naive_text_seconds(text):
    """Seconds of a naive 'YYYY-MM-DD HH:MM[:SS]' or 'YYYY-MM-DDTHH:MM[:SS]' text."""
    m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?", text)
    if not m:
        raise ValueError(text)
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mi, ss = int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0)
    return civil_seconds(y, mo, d, hh, mi, ss)


def iso_to_utc(text):
    text = text.strip()
    if text.endswith("Z"):
        return naive_text_seconds(text[:-1])
    m = re.search(r"([+-])(\d{2}):(\d{2})$", text)
    if not m:
        return naive_text_seconds(text)
    off = int(m.group(2)) * 60 + int(m.group(3))
    if m.group(1) == "-":
        off = -off
    return naive_text_seconds(text[: m.start()]) - off * 60


class Clock:
    def __init__(self, std_minutes, rule):
        self.std = std_minutes
        self.rule = rule
        self._spans = {}

    def dst_span(self, year):
        if year not in self._spans:
            span = None
            if self.rule == "us":
                d1 = date(year, 3, 1)
                d1 += timedelta(days=(6 - d1.weekday()) % 7 + 7)
                d2 = date(year, 11, 1)
                d2 += timedelta(days=(6 - d2.weekday()) % 7)
                span = (civil_seconds(d1.year, d1.month, d1.day, 2) - self.std * 60, civil_seconds(d2.year, d2.month, d2.day, 1) - self.std * 60)
            elif self.rule == "eu":
                d1 = date(year, 3, 31)
                d1 -= timedelta(days=(d1.weekday() + 1) % 7)
                d2 = date(year, 10, 31)
                d2 -= timedelta(days=(d2.weekday() + 1) % 7)
                span = (civil_seconds(d1.year, d1.month, d1.day, 1), civil_seconds(d2.year, d2.month, d2.day, 1))
            self._spans[year] = span
        return self._spans[year]

    def in_dst(self, u):
        year = (EPOCH + timedelta(seconds=u + self.std * 60)).year
        span = self.dst_span(year)
        return bool(span) and span[0] <= u < span[1]

    def lst_to_utc(self, naive):
        return naive - self.std * 60

    def wall_to_utc(self, naive):
        guess = naive - self.std * 60 - 3600
        if self.in_dst(guess):
            return guess
        return naive - self.std * 60

    def wall_of(self, u):
        return u + self.std * 60 + (3600 if self.in_dst(u) else 0)

    def fmt(self, u):
        return (EPOCH + timedelta(seconds=u + self.std * 60)).strftime("%Y-%m-%d %H:%M")

    def lst_date(self, u):
        return (EPOCH + timedelta(seconds=u + self.std * 60)).date()


# ============================================================================ a small YAML reader
def _strip_comment(s):
    out, q = [], None
    for i, ch in enumerate(s):
        if q:
            out.append(ch)
            if ch == q:
                q = None
        elif ch in "'\"":
            q = ch
            out.append(ch)
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _scalar(s):
    s = s.strip()
    if s == "" or s in ("null", "~"):
        return None
    if s[0] == "'" and s[-1] == "'" and len(s) >= 2:
        return s[1:-1].replace("''", "'")
    if s[0] == '"' and s[-1] == '"' and len(s) >= 2:
        return s[1:-1]
    return s


def _flow(s, i=0):
    """Parse a flow collection or scalar starting at s[i]; returns (value, next index)."""
    while i < len(s) and s[i] == " ":
        i += 1
    if s[i] == "[":
        out, i = [], i + 1
        while True:
            while s[i] == " ":
                i += 1
            if s[i] == "]":
                return out, i + 1
            v, i = _flow(s, i)
            out.append(v)
            while s[i] == " ":
                i += 1
            if s[i] == ",":
                i += 1
    if s[i] == "{":
        out, i = {}, i + 1
        while True:
            while s[i] == " ":
                i += 1
            if s[i] == "}":
                return out, i + 1
            k, i = _flow_token(s, i, ":")
            i += 1
            v, i = _flow(s, i)
            out[_scalar(k)] = v
            while s[i] == " ":
                i += 1
            if s[i] == ",":
                i += 1
    tok, i = _flow_token(s, i, ",]}")
    return _scalar(tok), i


def _flow_token(s, i, stops):
    j, q = i, None
    while j < len(s):
        ch = s[j]
        if q:
            if ch == q:
                q = None
        elif ch in "'\"":
            q = ch
        elif ch in stops and (ch != ":" or j + 1 >= len(s) or s[j + 1] == " "):
            break
        j += 1
    return s[i:j].strip(), j


def _split_key(s):
    """(key, rest) when s is a mapping entry 'key: value' or 'key:', else None."""
    q = None
    for i, ch in enumerate(s):
        if q:
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
        elif ch in "[{":
            return None
        elif ch == ":" and (i + 1 == len(s) or s[i + 1] == " "):
            return _scalar(s[:i]), s[i + 1:].strip()
    return None


def _value(text):
    text = text.strip()
    if text.startswith("[") or text.startswith("{"):
        return _flow(text)[0]
    return _scalar(text)


def yaml_load(text):
    lines = []
    for raw in text.splitlines():
        body = _strip_comment(raw)
        if body.strip():
            lines.append((len(body) - len(body.lstrip(" ")), body.strip()))

    def block(i, ind):
        if lines[i][1].startswith("- ") or lines[i][1] == "-":
            out = []
            while i < len(lines) and lines[i][0] == ind and (lines[i][1].startswith("- ") or lines[i][1] == "-"):
                rest = lines[i][1][2:].strip()
                if not rest:
                    v, i = block(i + 1, lines[i + 1][0])
                    out.append(v)
                    continue
                kv = _split_key(rest)
                if kv is None:
                    out.append(_value(rest))
                    i += 1
                    continue
                sub_ind = ind + 2
                lines[i] = (sub_ind, rest)
                v, i = block(i, sub_ind)
                out.append(v)
            return out, i
        out = {}
        while i < len(lines) and lines[i][0] == ind:
            kv = _split_key(lines[i][1])
            if kv is None:
                raise ValueError(lines[i])
            key, rest = kv
            if rest:
                out[key] = _value(rest)
                i += 1
            elif i + 1 < len(lines) and lines[i + 1][0] > ind:
                out[key], i = block(i + 1, lines[i + 1][0])
            else:
                out[key] = None
                i += 1
        return out, i
    if not lines:
        return None
    return block(0, lines[0][0])[0]


# ============================================================================ PDF text by position
def B(text):
    """Bytes of an ASCII text, for patterns over raw PDF bytes."""
    return text.encode("latin-1")


OCTAL_DIGITS = B("0123" + "4567")


def _pdf_objects(blob):
    objs = {}
    for m in re.finditer(B(r"(\d+)\s+0\s+obj\b"), blob):
        start = m.end()
        end = blob.find(b"endobj", start)
        objs[int(m.group(1))] = blob[start:end]
    return objs


def _pdf_stream(body):
    m = re.search(B(r"stream\r?\n"), body)
    if not m:
        return b""
    head = body[: m.start()]
    lm = re.search(B(r"/Length\s+(\d+)"), head)
    data = body[m.end(): m.end() + int(lm.group(1))] if lm else body[m.end(): body.rfind(B("endstream"))]
    if B("/FlateDecode") in head:
        data = zlib.decompress(data)
    return data


def _pdf_tokens(data):
    i, n = 0, len(data)
    while i < n:
        c = data[i:i + 1]
        if c in b" \t\r\n\f\x00":
            i += 1
        elif c == b"%":
            while i < n and data[i:i + 1] not in b"\r\n":
                i += 1
        elif c == b"(":
            depth, i, buf = 1, i + 1, bytearray()
            while i < n:
                ch = data[i]
                if ch == 0x5C:
                    nx = data[i + 1:i + 2]
                    if nx in OCTAL_DIGITS:
                        j = i + 1
                        while j < i + 4 and data[j:j + 1] in OCTAL_DIGITS and data[j:j + 1] != b"":
                            j += 1
                        buf.append(int(data[i + 1:j], 8) & 0xFF)
                        i = j
                        continue
                    esc = {b"n": 10, b"r": 13, b"t": 9, b"b": 8, b"f": 12}.get(nx)
                    buf.append(esc if esc is not None else data[i + 1])
                    i += 2
                    continue
                if ch == 0x28:
                    depth += 1
                elif ch == 0x29:
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                buf.append(ch)
                i += 1
            yield ("str", buf.decode("latin-1"))
        elif c == b"<" and data[i + 1:i + 2] != b"<":
            j = data.index(b">", i)
            hx = re.sub(rb"\s", b"", data[i + 1:j])
            if len(hx) % 2:
                hx += b"0"
            yield ("str", bytes.fromhex(hx.decode()).decode("latin-1"))
            i = j + 1
        elif c in b"[]":
            yield (c.decode(), None)
            i += 1
        elif c == b"/":
            j = i + 1
            while j < n and data[j:j + 1] not in B(" \t\r\n/[]()<>"):
                j += 1
            yield ("name", data[i + 1:j].decode("latin-1"))
            i = j
        else:
            j = i
            while j < n and data[j:j + 1] not in B(" \t\r\n/[]()<>%"):
                j += 1
            word = data[i:j].decode("latin-1")
            if re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)", word):
                yield ("num", float(word))
            else:
                yield ("op", word)
            i = j


def pdf_rows(path):
    """Text rows of every page, top to bottom, each a dict column -> text."""
    blob = open(path, "rb").read()
    objs = _pdf_objects(blob)
    root = int(re.search(B(r"/Root\s+(\d+)"), blob).group(1))
    pages_ref = int(re.search(B(r"/Pages\s+(\d+)"), objs[root]).group(1))
    kids = [int(x) for x in re.findall(B(r"(\d+)\s+0\s+R"), re.search(B(r"/Kids\s*\[(.*?)\]"), objs[pages_ref], re.S).group(1))]
    rows = []
    for pid in kids:
        content = int(re.search(B(r"/Contents\s+(\d+)"), objs[pid]).group(1))
        data = _pdf_stream(objs[content])
        shows, stack, x, y, lx, ly, arr = [], [], 0.0, 0.0, 0.0, 0.0, None
        for kind, val in _pdf_tokens(data):
            if kind == "[":
                arr = []
            elif kind == "]":
                stack.append(("arr", arr))
                arr = None
            elif arr is not None:
                if kind == "str":
                    arr.append(val)
            elif kind == "op":
                if val == "BT":
                    x = y = lx = ly = 0.0
                elif val == "Tm":
                    nums = [v for k, v in stack if k == "num"][-6:]
                    x, y = nums[4], nums[5]
                    lx, ly = x, y
                elif val == "Td":
                    nums = [v for k, v in stack if k == "num"][-2:]
                    lx, ly = lx + nums[0], ly + nums[1]
                    x, y = lx, ly
                elif val == "Tj":
                    s = [v for k, v in stack if k == "str"][-1]
                    shows.append((y, x, s))
                elif val == "TJ":
                    a = [v for k, v in stack if k == "arr"][-1]
                    shows.append((y, x, "".join(a)))
                stack = []
            else:
                stack.append((kind, val))
        byy = {}
        for yy, xx, s in shows:
            byy.setdefault(round(yy, 1), []).append((xx, s))
        for yy in sorted(byy, reverse=True):
            cells = {}
            for xx, s in sorted(byy[yy]):
                cells[int(round((xx - 36) / 86.0))] = s
            rows.append(cells)
    return rows


def memo_tables(path):
    """{table id: {'status': .., 'header': [...], 'rows': [[...]]}} from the review minutes."""
    tables, cur = {}, None
    head_next = False
    for cells in pdf_rows(path):
        first = cells.get(0, "").strip()
        m = re.match(r"^Table ([A-Z]-\d+): .*\[([^\]]+)\]\s*$", first)
        mc = re.match(r"^Table ([A-Z]-\d+) \(continued\)$", first)
        if m:
            cur = tables.setdefault(m.group(1), {"status": m.group(2).strip(), "header": None, "rows": []})
            head_next = True
            continue
        if mc:
            cur = tables[mc.group(1)]
            head_next = True
            continue
        if cur is None:
            continue
        if head_next:
            cur["header"] = [cells.get(k, "").strip() for k in range(max(cells) + 1)]
            head_next = False
            continue
        if len(cells) < 2 or first.startswith("HRB "):
            if first.startswith("HRB ") or len(cells) < 2:
                continue
        cur["rows"].append([cells.get(k, "").strip() for k in range(len(cur["header"]))])
    return tables


# ============================================================================ XLSX
def _local(tag):
    return tag.rsplit("}", 1)[-1]


def xlsx_sheets(path):
    """(date1904, {sheet name: [[cell text, ...], ...]})."""
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    d1904 = False
    names = []
    for el in wb.iter():
        if _local(el.tag) == "workbookPr" and el.get("date1904") in ("1", "true"):
            d1904 = True
        if _local(el.tag) == "sheet":
            rid = next(v for k, v in el.attrib.items() if _local(k) == "id")
            names.append((el.get("name"), rid))
    rels = {}
    for el in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
        rels[el.get("Id")] = el.get("Target")
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
            shared.append("".join(t.text or "" for t in si.iter() if _local(t.tag) == "t"))
    out = {}
    for name, rid in names:
        target = rels[rid].lstrip("/")
        part = target if target.startswith("xl/") else "xl/" + target
        rows = []
        for row in ET.fromstring(z.read(part)).iter():
            if _local(row.tag) != "row":
                continue
            cells, col = {}, -1
            for c in row:
                if _local(c.tag) != "c":
                    continue
                ref = c.get("r")
                if ref:
                    letters = re.match(r"[A-Z]+", ref).group(0)
                    col = 0
                    for ch in letters:
                        col = col * 26 + ord(ch) - 64
                    col -= 1
                else:
                    col += 1
                t = c.get("t")
                text = ""
                if t == "inlineStr":
                    text = "".join(x.text or "" for x in c.iter() if _local(x.tag) == "t")
                else:
                    v = next((x for x in c if _local(x.tag) == "v"), None)
                    text = v.text if v is not None and v.text else ""
                    if t == "s":
                        text = shared[int(text)]
                cells[col] = text
            rows.append([cells.get(k, "") for k in range(max(cells) + 1)] if cells else [])
        out[name] = rows
    return d1904, out


def header_rows(rows, first_col):
    """Rows after the header row whose first cell is first_col, as dicts."""
    for k, r in enumerate(rows):
        if r and r[0].strip() == first_col:
            head = [h.strip() for h in r]
            out = []
            for rr in rows[k + 1:]:
                if len(rr) < 2:
                    continue
                out.append({h: (rr[i].strip() if i < len(rr) else "") for i, h in enumerate(head)})
            return out
    return []


# ============================================================================ shard readers
QUAL = {
    "L01": {"G": "G", "S": "S", "E": "E", "X": "X"}, "L03": {"OK": "G", "SUS": "S", "EST": "E", "FLT": "X"},
    "L04": {"A": "G", "S": "S", "E": "E", "F": "X"}, "L05": {"0": "G", "1": "S", "2": "E", "9": "X"},
    "L06": {"g": "G", "s": "S", "e": "E", "x": "X"}, "L08": {"good": "G", "suspect": "S", "estimated": "E", "fault": "X"},
    "L11": {"GOOD": "G", "SUSP": "S", "EST": "E", "FAULT": "X"}, "L12": {"10": "G", "30": "S", "40": "E", "90": "X"},
    "L15": {"g": "G", "s": "S", "e": "E", "x": "X"}, "L19": {"": "G", "S": "S", "E": "E", "X": "X"},
}


class Rec:
    __slots__ = ("tok", "sensor", "t", "val", "unit", "q", "rev", "void")

    def __init__(self, tok, sensor, t, val, unit, q="G", rev=1, void=False):
        self.tok, self.sensor, self.t, self.val, self.unit = str(tok), sensor, int(t), val, unit
        self.q, self.rev, self.void = q, int(rev), bool(void)


def _unit_suffix(text):
    m = re.match(r"^\s*(-?[\d.]+)\s*([A-Za-z]+)\s*$", text)
    return m.group(1), m.group(2).upper()


def read_shard(path, layout, clock):  # noqa: C901
    std = clock.std
    out = []
    if layout in ("L01", "L20", "L02"):
        lines = [ln for ln in open(path, encoding="utf-8").read().splitlines() if ln.strip() and not ln.startswith("#")]
        rows = list(csv.reader(lines))
        head = rows[0]
        for r in rows[1:]:
            d = dict(zip(head, r))
            if layout == "L01":
                out.append(Rec(d["station"], d["sensor"], iso_to_utc(d["obs_utc"]), d["stage"], None, d["qual"], d["rev"], d["void"] == "1"))
            elif layout == "L20":
                out.append(Rec(d["site"], "P", clock.lst_to_utc(naive_text_seconds(d["time_lst"])), d["gh_ft"], "FT"))
            else:
                if d["hour"].strip().upper() == "MEAN":
                    continue
                base = clock.lst_to_utc(naive_text_seconds(d["date_lst"]) + int(d["hour"]) * 3600)
                for k, col in enumerate(("m00", "m15", "m30", "m45")):
                    if d[col].strip():
                        out.append(Rec(d["site_id"], "P", base + 900 * k, d[col], d["unit"].upper(), "G", d["rev"]))
    elif layout in ("L03", "L04", "L05", "L06"):
        delim = "\t" if layout in ("L03", "L04") else "|"
        lines = [ln for ln in open(path, encoding="utf-8").read().splitlines() if ln.strip() and not ln.startswith("#")]
        head = lines[0].split(delim)
        for ln in lines[1:]:
            parts = ln.split(delim)
            if parts == head:
                continue
            d = dict(zip(head, parts))
            if layout == "L03":
                out.append(Rec(d["gauge"], "P" if d["chan"] == "1" else "B", int(d["t_epoch"]), d["h"].replace(",", "."), d["unit"].upper(),
                               QUAL["L03"][d["flag"]], d["revision"], d["status"] == "VOID"))
            elif layout == "L04":
                out.append(Rec(d["STN"], "P" if d["SENSOR"] == "PRI" else "B", clock.wall_to_utc(naive_text_seconds(d["WALLCLOCK"])), d["GH"], None,
                               QUAL["L04"][d["Q"]], d["REV"]))
            elif layout == "L05":
                out.append(Rec(d["site"], "P" if d["sens"] == "1" else "B", int(d["ts_ms"]) // 1000, d["value_cm"], "CM", QUAL["L05"][d["q"]],
                               d["rv"], d["vd"] == "Y"))
            else:
                v, u = _unit_suffix(d["stage"])
                out.append(Rec(d["alias"], "P", iso_to_utc(d["when"]), v, u, QUAL["L06"][d["code"]], d["ver"]))
    elif layout in ("L07", "L08", "L09", "L10"):
        for ln in open(path, encoding="utf-8"):
            if not ln.strip():
                continue
            o = json.loads(ln, parse_float=Decimal)
            if layout == "L07":
                if o.get("type") == "hb":
                    continue
                t = clock.lst_to_utc(civil_seconds(int(o["t"][:4]), int(o["t"][4:6]), int(o["t"][6:8]), int(o["t"][9:11]), int(o["t"][11:13])))
                out.append(Rec(o["s"], o["k"], t, o["v"], o["u"].upper(), o["q"], o["r"], o["x"]))
            elif layout == "L08":
                gh = o["reading"]["gh"]
                meta = o["meta"]
                out.append(Rec(o["station"]["id"], "P" if meta["channel"] == "primary" else "B", iso_to_utc(o["reading"]["time_utc"]),
                               None if gh["value"] is None else str(gh["value"]), gh["unit"].upper(), QUAL["L08"][meta["quality"]], meta["rev"], meta["void"]))
            elif layout == "L09":
                base = naive_text_seconds(o["hour_utc"][:10] + " " + o["hour_utc"][11:13] + ":00")
                for k, v in enumerate(o["vals"]):
                    if v is not None:
                        out.append(Rec(o["site"], "P", base + 900 * k, str(v), o["unit"].upper(), "G", o["rev"]))
            else:
                out.append(Rec(o["id"], "B", o["epoch"], None if o["stage_m"] is None else str(o["stage_m"]), "M", o["qa"], o["rev"], o["deleted"] == 1))
    elif layout in ("L11", "L12"):
        root = ET.parse(path).getroot()
        if layout == "L11":
            for site in root:
                for r in site:
                    out.append(Rec(site.get("code"), r.get("s"), iso_to_utc(r.get("t")), r.get("v"), None, QUAL["L11"][r.get("q")], r.get("rev"),
                                   r.get("void") == "1"))
        else:
            for rd in root:
                tm = rd.find("time")
                m = re.match(r"(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2})", tm.text)
                naive = civil_seconds(int(m.group(3)), int(m.group(2)), int(m.group(1)), int(m.group(4)), int(m.group(5)))
                zone = tm.get("zone")
                t = naive if zone == "UTC" else clock.lst_to_utc(naive) if zone == "LST" else clock.wall_to_utc(naive)
                val = rd.find("value")
                out.append(Rec(rd.find("station").text, "P", t, val.text, val.get("unit").upper(), QUAL["L12"][rd.find("qual").text], rd.find("rev").text))
    elif layout == "L13":
        for ln in open(path, encoding="utf-8").read().splitlines():
            if not re.match(r"^\S+\s*\d{4}-\d{2}-\d{2} \d{4} ", ln) or len(ln) < 39:
                continue
            tok, d, tm, val, unit, q, rev = ln[0:10].strip(), ln[10:20], ln[21:25], ln[26:33].strip(), ln[34:36].strip(), ln[37:38], ln[39:41].strip()
            t = clock.lst_to_utc(naive_text_seconds(d) + int(tm[:2]) * 3600 + int(tm[2:]) * 60)
            out.append(Rec(tok, "P", t, val, unit, q, rev))
    elif layout == "L14":
        for ln in open(path, encoding="utf-8").read().splitlines():
            if not ln.strip() or ln.startswith("NOTE"):
                continue
            kv = dict(re.findall(r"(\w+)=(\S+)", ln))
            if ln.startswith("VOID"):
                out.append(Rec(kv["stn"], kv["sensor"], iso_to_utc(kv["t"]), None, None, "G", kv["rev"], True))
            else:
                stamp = ln[:20]
                v, u = _unit_suffix(kv["gh"])
                out.append(Rec(kv["stn"], kv["sensor"], iso_to_utc(stamp), v, u, kv["q"], kv["rev"]))
    elif layout == "L15":
        doc = yaml_load(open(path, encoding="utf-8").read())
        for blk in doc["blocks"]:
            sen = "P" if blk["sensor"] == "primary" else "B"
            for row in blk["rows"]:
                out.append(Rec(blk["station"], sen, int(row[0]), row[1], blk["unit"].upper(), QUAL["L15"][row[2]], row[3]))
    elif layout == "L16":
        doc = yaml_load(open(path, encoding="utf-8").read())
        for tok, readings in doc["stations"].items():
            for key, r in readings.items():
                for one in (r if isinstance(r, list) else [r]):
                    out.append(Rec(tok, "P", iso_to_utc(key), one["v"], one["u"].upper(), "G", one["r"]))
    elif layout == "L17":
        doc = json.load(open(path, encoding="utf-8"), parse_float=Decimal)
        default = doc["meta"]["unit"].upper()
        for run in doc["series"]:
            for k, v in enumerate(run["values"]):
                if v is not None:
                    out.append(Rec(run["site"], run["sensor"], run["start"] + k * run["step"], str(v), run.get("unit", default).upper(), "G", run["rev"]))
    elif layout == "L18":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        toks = dict(con.execute("SELECT sid, token FROM sites"))
        for sid, sen, ser, val, unit, q, rev, void in con.execute("SELECT sid, sensor, t_serial, value, unit, q, rev, void FROM readings ORDER BY rid"):
            secs = ser * 86400
            minute = int(round(secs / 60.0)) * 60
            t = clock.lst_to_utc(civil_seconds(1899, 12, 30) + minute)
            out.append(Rec(toks[sid], sen, t, None if val is None else repr(val), unit.upper(), q, rev, void == 1))
        con.close()
    elif layout == "L19":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for stn, ts, mm, sen, rev, flag in con.execute("SELECT stn, ts, gh_mm, sensor, rev, flag FROM obs ORDER BY rowid"):
            out.append(Rec(stn, sen, ts, str(mm), "MM", QUAL["L19"][flag or ""], rev))
        for stn, ts, sen, rev in con.execute("SELECT stn, ts, sensor, rev FROM voids ORDER BY rowid"):
            out.append(Rec(stn, sen, ts, None, "MM", "G", rev, True))
        con.close()
    return out


# ============================================================================ registers
class Resolver:
    def __init__(self, stations, rows):
        self.known = set(stations)
        self.by = {}
        for tok, frm, to, target in rows:
            self.by.setdefault(tok, []).append((frm, to, target))

    @staticmethod
    def norm(tok):
        t = str(tok).strip().upper()
        if t.isdigit() and len(t) < 8:
            t = t.rjust(8, "0")
        return t

    def __call__(self, tok, u):
        """Station id of a token at instant u, following at most six cross-reference rows (H5)."""
        t = self.norm(tok)
        rows_followed = 0
        while t not in self.known:
            if rows_followed == 6:
                return None
            nxt = None
            for frm, to, target in self.by.get(t, ()):
                if frm <= u and (to is None or u < to):
                    nxt = target
            if nxt is None:
                return None
            t = self.norm(nxt)
            rows_followed += 1
        return t


def load_resolver(data, stations):
    rows = {}
    con = sqlite3.connect(f"file:{os.path.join(data, 'stn_xref.sqlite')}?mode=ro", uri=True)
    for tok, target, frm, to, _kind in con.execute("SELECT token, target, valid_from, valid_to, kind FROM xref"):
        rows[(Resolver.norm(tok), frm.strip())] = (target, to)
    con.close()
    add = yaml_load(open(os.path.join(data, "xref_addendum.yml"), encoding="utf-8").read())
    for r in add["rows"]:
        rows[(Resolver.norm(r["token"]), str(r["valid_from"]).strip())] = (r["target"], r["valid_to"])
    flat = []
    for (tok, frm), (target, to) in rows.items():
        flat.append((tok, iso_to_utc(frm), iso_to_utc(to) if to not in (None, "", "null") else None, target))
    return Resolver(stations, flat)


# ============================================================================ ratings
class Rating:
    def __init__(self, rid, site, eff, pts):
        self.rid, self.site, self.eff = rid, site, eff
        self.pts = sorted(pts, key=lambda p: p[0])
        self.f = [(float(h), float(q), float(e)) for h, q, e in self.pts]
        self.cache = {}

    def _beta(self, i):
        (h0, q0, e0), (h1, q1, _) = self.f[i], self.f[i + 1]
        return math.log(q1 / q0) / math.log((h1 - e0) / (h0 - e0))

    def q_of(self, gh):
        """(R(gh) at 4 significant figures, above rating)."""
        key = Fraction(gh)
        if key not in self.cache:
            self.cache[key] = self._q_of(key)
        return self.cache[key]

    def _q_of(self, gh):
        h = float(gh)
        f = self.f
        above = h > f[-1][0]
        for hi, qi, _ in f:
            if h == hi:
                return sig(Fraction(qi), 4), above
        if h < f[0][0]:
            if h <= f[0][2]:
                return Fraction(0), above
            i = 0
        else:
            i = len(f) - 2
            for k in range(len(f) - 1):
                if f[k][0] <= h < f[k + 1][0]:
                    i = k
                    break
        hi, qi, ei = f[i]
        val = qi * ((h - ei) / (hi - ei)) ** self._beta(i)
        return sig(Fraction(val), 4), above

    def gh_of(self, q):
        qf = float(q)
        f = self.f
        for hi, qi, _ in f:
            if qf == qi:
                return dp(Fraction(hi), 2)
        if qf < f[0][1]:
            i = 0
        else:
            i = len(f) - 2
            for k in range(len(f) - 1):
                if f[k][1] <= qf < f[k + 1][1]:
                    i = k
                    break
        hi, qi, ei = f[i]
        return dp(Fraction(ei + (hi - ei) * (qf / qi) ** (1.0 / self._beta(i))), 2)


def at_time(items, t, key):
    best = None
    for it in items:
        if key(it) <= t and (best is None or key(it) >= key(best)):
            best = it
    return best


def linear(points, t, places):
    """Piecewise-linear value over (time, value) points: first value before, last value after."""
    if t <= points[0][0]:
        return points[0][1]
    for (a, x), (b, y) in zip(points, points[1:]):
        if a <= t < b:
            return dp(x + (y - x) * Fraction(t - a, b - a), places)
    return points[-1][1]


# ============================================================================ the run
class Run:
    def __init__(self, data):
        self.data = data
        self.p = lambda name: os.path.join(data, name)

    # ---------------------------------------------------------------- settings
    def load_settings(self):
        prof = yaml_load(open(self.p("dv_profile.yml"), encoding="utf-8").read())
        self.network = prof["network"]
        self.period_start, self.period_end = str(prof["period_start"]), str(prof["period_end"])
        blk = prof["networks"][self.network]
        self.sheet_rating, self.sheet_index, self.sheet_site = blk["rating_sheet"], blk["index_sheet"], blk["site_sheet"]
        self.max_gap = int(blk["max_gap_minutes"])
        self.min_cov = exact(blk["min_coverage_fraction"])
        self.margin = int(blk["record_margin_hours"])
        self.drift_default = str(blk["drift_tolerance_ft"])
        ck = yaml_load(open(self.p("site_clock.yaml"), encoding="utf-8").read())
        self.clock = Clock(int(ck["standard_offset_minutes"]), str(ck["dst_rule"]).strip())
        ov = yaml_load(open(self.p("site_overlay.yaml"), encoding="utf-8").read())
        self.overlay = {str(k): v for k, v in (ov.get("sites") or {}).items()}
        self.stations = {}
        with open(self.p("stn_master.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                self.stations[r["station_id"].strip()] = r
        self.sites = sorted(s for s, r in self.stations.items() if r["status"].strip() == "ACTIVE" and r["network"].strip() == self.network)
        self.scope = set(self.sites)
        self.resolve = load_resolver(self.data, self.stations)
        y, m, d = (int(x) for x in self.period_start.split("-"))
        self.d0 = date(y, m, d)
        y, m, d = (int(x) for x in self.period_end.split("-"))
        self.d1 = date(y, m, d)
        self.p0 = self.clock.lst_to_utc(civil_seconds(self.d0.year, self.d0.month, self.d0.day))
        self.p1 = self.clock.lst_to_utc(civil_seconds(self.d1.year, self.d1.month, self.d1.day))
        self.w0, self.w1 = self.p0 - self.margin * 3600, self.p1 + self.margin * 3600

    def load_books(self):
        self.d1904, sheets = xlsx_sheets(self.p("cbhs_rt_26q2.xlsx"))
        base = date(1904, 1, 1) if self.d1904 else date(1899, 12, 30)
        site_rows = header_rows(sheets[self.sheet_site], "site")
        self.area, self.tol = {}, {}
        for r in site_rows:
            sid = r["site"].strip()
            self.area[sid] = exact(r["drainage_area_mi2"]) if r.get("drainage_area_mi2", "").strip() else None
            self.tol[sid] = r.get("drift_tol_ft", "").strip()
        self.memo = memo_tables(self.p("hrb_26-04_minutes.pdf"))
        inforce = {tid: t for tid, t in self.memo.items() if t["status"].upper() == "IN FORCE"}
        self.inforce = inforce
        self.tolerance = {r[0]: r[1] for r in inforce["T-2"]["rows"]}
        self.winter = {r[0]: r[1] for r in inforce["W-1"]["rows"]}
        errata = {(r[0], exact(r[1])): exact(r[2]) for r in inforce["R-2"]["rows"]}
        self.disregard = {int(r[0]) for r in inforce["V-1"]["rows"]}
        self.review = {int(r[0]): (r[2], r[3]) for r in inforce["M-1"]["rows"]}
        pts = {}
        for r in header_rows(sheets[self.sheet_rating], "rating_id"):
            if not r.get("gh_ft"):
                continue
            pts.setdefault(r["rating_id"], []).append([exact(r["gh_ft"]), exact(r["q_cfs"]), exact(r["offset_ft"])])
        self.ratings = {s: [] for s in self.sites}
        self.errata_applied = {}
        for r in header_rows(sheets[self.sheet_index], "rating_id"):
            if r.get("status", "").strip().upper() != "ACTIVE" or r["site"].strip() not in self.scope:
                continue
            day = base + timedelta(days=int(float(r["effective_date"])))
            hh, mm = (int(x) for x in r["effective_time"].strip().split(":"))
            eff = self.clock.lst_to_utc(civil_seconds(day.year, day.month, day.day, hh, mm))
            rid = r["rating_id"].strip()
            applied = []
            plist = []
            for h, q, e in sorted(pts[rid], key=lambda x: x[0]):
                if (rid, h) in errata:
                    applied.append((h, q, errata[(rid, h)]))
                    q = errata[(rid, h)]
                plist.append((h, q, e))
            self.errata_applied[rid] = applied
            self.ratings[r["site"].strip()].append(Rating(rid, r["site"].strip(), eff, plist))
        for s in self.sites:
            self.ratings[s].sort(key=lambda v: v.eff)

    def tol_of(self, sid):
        ov = self.overlay.get(sid) or {}
        if ov.get("drift_tolerance_ft") not in (None, ""):
            return exact(ov["drift_tolerance_ft"])
        if self.tol.get(sid):
            return exact(self.tol[sid])
        return exact(self.drift_default)

    def gap_of(self, sid):
        ov = self.overlay.get(sid) or {}
        return int(ov["max_gap_minutes"]) if ov.get("max_gap_minutes") not in (None, "") else self.max_gap

    # ---------------------------------------------------------------- ingest
    def ingest(self):
        cat = json.load(open(self.p("ingest_catalog.json"), encoding="utf-8"))
        layout = {f["file"]: f["layout"] for f in cat["files"]}
        routes = {}
        for r in cat["routes"]:
            if r["status"] == "ACTIVE":
                routes.setdefault((r["file"], r["site"], r["sensor"]), []).append((iso_to_utc(r["from_utc"]), iso_to_utc(r["to_utc"])))
        self.count = dict.fromkeys(["files_read", "records_read", "unknown_site", "out_of_scope", "unrouted", "out_of_window", "admitted",
                                    "superseded", "duplicates", "voided", "edits_applied", "edits_ignored", "edit_deleted", "sensor_fault",
                                    "backup_unused", "kept"], 0)
        self.lineage, self.tokens = [], {}
        best = {}
        groups = {}
        for pos, fname in enumerate(cat["file_order"]):
            if not os.path.exists(self.p(fname)):
                continue
            self.count["files_read"] += 1
            line = {"file": fname, "layout": layout[fname], "records": 0, "unknown_site": 0, "out_of_scope": 0, "unrouted": 0,
                    "out_of_window": 0, "admitted": 0}
            for rec in read_shard(self.p(fname), layout[fname], self.clock):
                line["records"] += 1
                sid = self.resolve(rec.tok, rec.t)
                if sid is None:
                    line["unknown_site"] += 1
                    continue
                if sid not in self.scope:
                    line["out_of_scope"] += 1
                    continue
                nt = Resolver.norm(rec.tok)
                if nt != sid:
                    self.tokens[(nt, sid)] = self.tokens.get((nt, sid), 0) + 1
                if not any(a <= rec.t < b for a, b in routes.get((fname, sid, rec.sensor), ())):
                    line["unrouted"] += 1
                    continue
                if not self.w0 <= rec.t < self.w1:
                    line["out_of_window"] += 1
                    continue
                line["admitted"] += 1
                groups.setdefault((sid, rec.sensor, rec.t), []).append((rec.rev, pos, fname, rec))
            for k in ("records", "unknown_site", "out_of_scope", "unrouted", "out_of_window", "admitted"):
                self.count["records_read" if k == "records" else k] += line[k]
            self.lineage.append(line)
        self.read, self.excluded = {}, []
        for key, copies in groups.items():
            top = max(c[0] for c in copies)
            win = max((c for c in copies if c[0] == top), key=lambda c: c[1])
            self.count["superseded"] += sum(1 for c in copies if c[0] < top)
            self.count["duplicates"] += sum(1 for c in copies if c[0] == top) - 1
            if win[3].void:
                self.count["voided"] += 1
                self.excluded.append((key, "VOIDED", win[2]))
            else:
                self.read[key] = [win[3].val, win[3].unit, win[3].q, win[2]]

    def apply_edits(self):
        edits = [json.loads(ln) for ln in open(self.p("uv_edits.jsonl"), encoding="utf-8") if ln.strip()]
        deleted, self.edit_rows = {}, []
        for e in sorted(edits, key=lambda e: int(e["seq"])):
            t = self.clock.lst_to_utc(naive_text_seconds(e["time_lst"]))
            sid = self.resolve(e["station"], t)
            if sid not in self.scope:
                continue
            key = (sid, e["sensor"], t)
            ok = False
            if self.w0 <= t < self.w1:
                if e["op"] == "SET" and key in self.read:
                    self.read[key] = [str(e["value"]), e["unit"].upper(), "G", self.read[key][3]]
                    ok = True
                elif e["op"] == "DELETE" and key in self.read:
                    deleted[key] = self.read.pop(key)
                    ok = True
                elif e["op"] == "RESTORE" and key in deleted:
                    self.read[key] = deleted.pop(key)
                    ok = True
            self.count["edits_applied" if ok else "edits_ignored"] += 1
            self.edit_rows.append([int(e["seq"]), sid, e["sensor"], self.clock.fmt(t), e["op"], "APPLIED" if ok else "IGNORED"])
        for key, r in deleted.items():
            self.count["edit_deleted"] += 1
            self.excluded.append((key, "EDIT_DELETED", r[3]))
        for key in [k for k, r in self.read.items() if r[2] == "X"]:
            self.count["sensor_fault"] += 1
            self.excluded.append((key, "SENSOR_FAULT", self.read[key][3]))
            del self.read[key]

    def stage(self):
        units = {}
        with open(self.p("eqp_reg.tsv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                units.setdefault((r["site"], r["sensor"]), []).append((self.clock.lst_to_utc(naive_text_seconds(r["valid_from_lst"])), r["unit"].upper()))
        datum = {}
        with open(self.p("dtm_hist.psv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="|"):
                if r["status"].strip().upper() == "ACTIVE":
                    datum.setdefault((r["site"], r["sensor"]), []).append((iso_to_utc(r["valid_from_utc"]), exact(r["offset_ft"])))
        for v in list(units.values()) + list(datum.values()):
            v.sort(key=lambda x: x[0])
        self.chosen = {}
        for (sid, sen, t), r in self.read.items():
            if sen == "P":
                self.chosen[(sid, t)] = ("P", r)
        for (sid, sen, t), r in self.read.items():
            if sen == "B":
                if (sid, t) in self.chosen:
                    self.count["backup_unused"] += 1
                    self.excluded.append(((sid, sen, t), "BACKUP_UNUSED", r[3]))
                else:
                    self.chosen[(sid, t)] = ("B", r)
        self.count["kept"] = len(self.chosen)
        self.raw_gh = {}
        for (sid, t), (sen, r) in self.chosen.items():
            unit = r[1]
            if unit is None:
                unit = at_time(units[(sid, sen)], t, lambda x: x[0])[1]
            off = at_time(datum.get((sid, sen), []), t, lambda x: x[0])
            self.raw_gh[(sid, t)] = exact(r[0]) * FEET_PER[unit] + (off[1] if off else 0)
        self.times = {}
        for sid, t in self.chosen:
            self.times.setdefault(sid, []).append(t)
        for s in self.times.values():
            s.sort()

    # ---------------------------------------------------------------- field visits
    def visits(self):
        con = sqlite3.connect(f"file:{self.p('fv_ledger_q2.db')}?mode=ro", uri=True)
        V = {}
        for vid, stn, vdate, vtime, logger, action, party in con.execute("SELECT vid, stn, vdate, vtime, logger_ft, action, party FROM visit"):
            t = self.clock.lst_to_utc(naive_text_seconds(vdate) + int(vtime[:2]) * 3600 + int(vtime[2:]) * 60)
            V[vid] = {"vid": vid, "stn": stn, "t": t, "logger": str(logger), "action": action.upper(), "refs": {}, "void": False}
        for vid, method, reading, _ in con.execute("SELECT vid, method, reading_ft, note FROM vref"):
            if vid in V:
                V[vid]["refs"][method.upper()] = str(reading)
        con.close()
        amends = sorted(ET.parse(self.p("fv_amend.xml")).getroot(), key=lambda a: int(a.get("no")))
        for a in amends:
            v = V.get(int(a.get("visit")))
            if v is None or v["void"]:
                continue
            field, text = a.get("field"), (a.text or "").strip()
            if field == "void":
                v["void"] = True
            elif field == "reference":
                v["refs"][a.get("method").upper()] = text
            elif field == "action":
                v["action"] = text.upper()
            elif field == "time":
                v["t"] = self.clock.lst_to_utc(naive_text_seconds(text))
            elif field == "logger":
                v["logger"] = text
        self.visit_rows, self.segments = [], {}
        for sid in self.sites:
            mine = sorted((v for v in V.values() if self.resolve(v["stn"], v["t"]) == sid), key=lambda v: (v["t"], v["vid"]))
            tol = self.tol_of(sid)
            used = []
            for v in mine:
                method = next(m for m in ("TAPE", "WIRE", "STAFF") if m in v["refs"])
                err = exact(v["refs"][method]) - exact(v["logger"])
                applied = err if abs(err) >= tol else Fraction(0)
                status = "VOID" if v["void"] else ("DISREGARDED" if v["vid"] in self.disregard else "USED")
                self.visit_rows.append([sid, v["vid"], v["t"], method, exact(v["refs"][method]), exact(v["logger"]), err,
                                        applied if status == "USED" else None, v["action"], status])
                if status == "USED":
                    used.append((v["t"], applied, v["action"]))
            segs = []
            for k, (t, applied, action) in enumerate(used):
                start = Fraction(0) if action == "RESET" else applied
                if k + 1 < len(used):
                    segs.append((t, used[k + 1][0], start, used[k + 1][1]))
                else:
                    segs.append((t, None, start, start))
            self.segments[sid] = segs
        self.gh = {}
        for (sid, t), raw in self.raw_gh.items():
            c = Fraction(0)
            for a, b, x, y in self.segments[sid]:
                if a <= t and (b is None or t < b):
                    c = x if b is None else x + (y - x) * Fraction(t - a, b - a)
                    break
            self.gh[(sid, t)] = dp(raw + c, 2)

    # ---------------------------------------------------------------- measurements, shifts, ice
    def version(self, sid, t):
        return at_time(self.ratings[sid], t, lambda v: v.eff)

    def measurements(self):  # noqa: C901
        entries = {}
        with open(self.p("qm_main_26q2.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                entries.setdefault(int(r["meas_no"]), []).append({
                    "no": int(r["meas_no"]), "stn": r["station"], "start": iso_to_utc(r["start"]), "end": iso_to_utc(r["end"]),
                    "q": exact(r["q_cfs"]), "grade": r["grade"].strip(), "cover": r["cover"].strip(), "field_gh": r["field_gh_ft"],
                    "entered": iso_to_utc(r["entered_utc"])})
        for m in ET.parse(self.p("qm_late.xml")).getroot():
            q = m.find("q")
            qv = exact(q.text)
            if (q.get("unit") or "").lower() == "cms":
                qv = qv / CMS_PER_CFS
            entries.setdefault(int(m.get("no")), []).append({
                "no": int(m.get("no")), "stn": m.find("station").text, "start": self.clock.lst_to_utc(naive_text_seconds(m.find("start").text)),
                "end": self.clock.lst_to_utc(naive_text_seconds(m.find("end").text)), "q": qv, "grade": m.find("grade").text.strip(),
                "cover": m.find("cover").text.strip(), "field_gh": m.find("field_gh_ft").text, "entered": iso_to_utc(m.find("entered").text)})
        self.meas = []
        for no in sorted(entries):
            m = max(entries[no], key=lambda e: e["entered"])
            inst = m["start"] + (m["end"] - m["start"]) // 2
            inst -= inst % 60
            sid = self.resolve(m["stn"], inst)
            if sid not in self.scope:
                continue
            verdict, grade = "ACCEPT", m["grade"]
            if no in self.review:
                verdict = self.review[no][0]
                if verdict == "REGRADE":
                    grade = self.review[no][1]
            inside = [self.gh[(sid, t)] for t in self.times.get(sid, []) if m["start"] <= t <= m["end"]]
            gh = dp(sum(inside, Fraction(0)) / len(inside), 2) if inside else None
            self.meas.append({"no": no, "site": sid, "t": inst, "grade": grade, "verdict": verdict, "cover": m["cover"], "gh": gh,
                              "q": m["q"], "rating": None, "use": None, "rated": None, "dev": None, "tol": None, "decision": None,
                              "shift": None, "k": None})
        self.ice_periods()
        last_shift = {}
        self.shift_points = {}
        order = sorted(self.meas, key=lambda m: (m["site"], m["t"], m["no"]))
        for m in order:
            if m["verdict"] == "REJECT":
                m["decision"] = "REJECTED"
                continue
            if m["gh"] is None:
                m["decision"] = "NO_RECORD"
                continue
            v = self.version(m["site"], m["t"])
            m["rating"] = v.rid
            if self.ice_at(m["site"], m["t"]) is not None:
                m["decision"] = "ICE"
                continue
            use = last_shift.get(v.rid, Fraction(0))
            rated, _ = v.q_of(m["gh"] + use)
            dev = dp((m["q"] - rated) / rated * 100, 1)
            tol = exact(self.tolerance[m["grade"]]) if m["grade"] in ("E", "G", "F") else None
            m.update(use=use, rated=rated, dev=dev, tol=tol)
            if tol is not None and abs(dev) > tol:
                m["shift"] = v.gh_of(m["q"]) - m["gh"]
                m["decision"] = "SHIFT"
                last_shift[v.rid] = m["shift"]
                self.shift_points.setdefault(v.rid, []).append((m["t"], m["shift"], m["no"]))
            else:
                m["decision"] = "CHECK"
        self.curves = {}
        for sid in self.sites:
            for v in self.ratings[sid]:
                self.curves[v.rid] = [(v.eff, Fraction(0), None)] + self.shift_points.get(v.rid, [])
        self.kpts = {}
        for m in order:
            if m["decision"] != "ICE":
                continue
            v = self.version(m["site"], m["t"])
            s = self.shift(v, m["t"])
            rated, _ = v.q_of(m["gh"] + s)
            m["use"], m["rated"] = s, rated
            m["k"] = dp(m["q"] / rated, 3)
            per = self.ice_at(m["site"], m["t"])
            self.kpts.setdefault((m["site"], per[0]), []).append((m["t"], m["k"], m["no"]))

    def shift(self, v, t):
        pts = [(a, x) for a, x, _ in self.curves[v.rid]]
        for (a, x), (b, y) in zip(pts, pts[1:]):
            if a <= t < b:
                return dp(x + (y - x) * Fraction(t - a, b - a), 2)
        return dp(pts[-1][1], 2)

    def ice_periods(self):
        ents = [json.loads(ln) for ln in open(self.p("ice_obs_j2.ndjson"), encoding="utf-8") if ln.strip()]
        events = {}
        for e in sorted(ents, key=lambda e: int(e["entry"])):
            kind = e["kind"]
            if kind in ("ON", "OFF"):
                t = self.clock.lst_to_utc(naive_text_seconds(e["at_lst"]))
                events[int(e["entry"])] = [self.resolve(e["station"], t), kind, t, int(e["entry"])]
            elif kind == "AMEND" and int(e["target"]) in events:
                events[int(e["target"])][2] = self.clock.lst_to_utc(naive_text_seconds(e["at_lst"]))
            elif kind == "WITHDRAW":
                events.pop(int(e["target"]), None)
        self.ice = {s: [] for s in self.sites}
        per = {}
        for ev in events.values():
            per.setdefault(ev[0], []).append(ev)
        for sid in self.sites:
            open_ev = None
            for _, kind, t, entry in sorted(per.get(sid, []), key=lambda e: (e[2], e[3])):
                if kind == "ON" and open_ev is None:
                    open_ev = (t, entry)
                elif kind == "OFF" and open_ev is not None:
                    self.ice[sid].append((open_ev[0], t, open_ev[1], entry))
                    open_ev = None
            if open_ev is not None:
                self.ice[sid].append((open_ev[0], None, open_ev[1], None))

    def ice_at(self, sid, t):
        for p in self.ice[sid]:
            if p[0] <= t and (p[1] is None or t < p[1]):
                return p
        return None

    # ---------------------------------------------------------------- unit and daily values
    def unit_values(self):
        self.uv = {}
        for sid in self.sites:
            for t in self.times.get(sid, []):
                gh = self.gh[(sid, t)]
                v = self.version(sid, t)
                s = self.shift(v, t)
                q_open, above = v.q_of(gh + s)
                per = self.ice_at(sid, t)
                k = None
                q = q_open
                if per is not None:
                    pts = self.kpts.get((sid, per[0]))
                    k = linear([(a, x) for a, x, _ in pts], t, 3) if pts else exact(self.winter[sid])
                    q = sig(k * q_open, 4)
                sen = self.chosen[(sid, t)][0]
                flags = ("B" if sen == "B" else "") + ("I" if per is not None else "") + (">" if above else "")
                self.uv[(sid, t)] = (sen, gh, s, gh + s, q_open, k, q, flags)

    def daily(self):
        self.days = [self.d0 + timedelta(days=i) for i in range((self.d1 - self.d0).days)]
        self.dv = {}
        for sid in self.sites:
            ts = self.times.get(sid, [])
            gap = self.gap_of(sid) * 60
            for d in self.days:
                a = self.clock.lst_to_utc(civil_seconds(d.year, d.month, d.day))
                b = a + 86400
                self.dv[(sid, d)] = [Fraction(0), 0, 0, set()]
            for t in ts:
                d = self.clock.lst_date(t)
                if (sid, d) in self.dv:
                    acc = self.dv[(sid, d)]
                    acc[2] += 1
                    fl = self.uv[(sid, t)][7]
                    acc[3].update({"B": "B", "I": "ICE", ">": ">"}[c] for c in fl)
            for ta, tb in zip(ts, ts[1:]):
                if tb - ta > gap:
                    continue
                qa, qb = self.uv[(sid, ta)][6], self.uv[(sid, tb)][6]
                d = self.clock.lst_date(ta)
                while True:
                    a = self.clock.lst_to_utc(civil_seconds(d.year, d.month, d.day))
                    b = a + 86400
                    if a >= tb:
                        break
                    lo, hi = max(ta, a), min(tb, b)
                    if hi > lo and (sid, d) in self.dv:
                        f_lo = qa + (qb - qa) * Fraction(lo - ta, tb - ta)
                        f_hi = qa + (qb - qa) * Fraction(hi - ta, tb - ta)
                        acc = self.dv[(sid, d)]
                        acc[0] += (f_lo + f_hi) / 2 * (hi - lo)
                        acc[1] += hi - lo
                    d += timedelta(days=1)
            for d in self.days:
                integral, cover, n, codes = self.dv[(sid, d)]
                inc = cover < self.min_cov * 86400
                mean = None if inc else discharge_table(integral / cover)
                order = (["INC"] if inc else []) + [c for c in ("ICE", "B", ">") if c in codes]
                self.dv[(sid, d)] = (mean, cover, n, order)

    # ---------------------------------------------------------------- reports
    def reports(self):  # noqa: C901
        fmt = self.clock.fmt
        R = {}
        rows = []
        for (sid, t) in sorted(self.uv):
            sen, gh, s, he, qo, k, q, fl = self.uv[(sid, t)]
            rows.append([sid, fmt(t), sen, show(gh, 2), show(s, 2), show(he, 2), show(qo), "" if k is None else show(k, 3), show(q), fl])
        R["unit_values.csv"] = table_text(["site", "time_lst", "sensor", "gh_ft", "shift_ft", "gh_eff_ft", "q_open_cfs", "k_factor", "q_cfs", "flags"], rows, ",")
        rows = []
        for sid in self.sites:
            for a, b, x, y in self.segments[sid]:
                rows.append([sid, fmt(a), "" if b is None else fmt(b), show(x, 2), show(y, 2)])
        R["gh_corrections.tsv"] = table_text(["site", "from_lst", "to_lst", "start_ft", "end_ft"], rows, "\t")
        rows = []
        for r in sorted(self.visit_rows, key=lambda r: (r[0], r[2], r[1])):
            rows.append([r[0], r[1], fmt(r[2]), r[3], show(r[4], 2), show(r[5], 2), show(r[6], 2), "" if r[7] is None else show(r[7], 2), r[8], r[9]])
        R["visit_errors.psv"] = table_text(["site", "visit_id", "time_lst", "method", "reference_ft", "logger_ft", "error_ft", "applied_ft", "action",
                                            "status"], rows, "|")
        rows = []
        for m in sorted(self.meas, key=lambda m: m["no"]):
            opt = lambda v, n=None: "" if v is None else show(v, n)  # noqa: E731
            rows.append([m["no"], m["site"], fmt(m["t"]), m["grade"], m["verdict"], m["cover"], opt(m["gh"], 2), m["rating"] or "", opt(m["use"], 2),
                         opt(m["rated"]), show(m["q"], 2), opt(m["dev"], 1), opt(m["tol"], 1), m["decision"], opt(m["shift"], 2), opt(m["k"], 3)])
        R["measurement_eval.csv"] = table_text(["meas_no", "site", "instant_lst", "grade", "verdict", "cover", "gh_ft", "rating_id", "shift_in_use_ft",
                                                "rated_q_cfs", "measured_q_cfs", "deviation_pct", "tolerance_pct", "decision", "shift_ft", "k_factor"], rows, ",")
        curves, rts = [], []
        for sid in self.sites:
            for v in self.ratings[sid]:
                curves.append({"site": sid, "rating_id": v.rid, "effective_lst": fmt(v.eff),
                               "points": [{"time_lst": fmt(a), "shift_ft": jnum(x, 2), "source": "START" if n is None else str(n)} for a, x, n in self.curves[v.rid]]})
                rts.append({"rating_id": v.rid, "site": sid, "effective_lst": fmt(v.eff),
                            "points": [{"gh_ft": jnum(h, 2), "q_cfs": jnum(q), "offset_ft": jnum(e, 2)} for h, q, e in v.pts],
                            "errata_applied": [{"gh_ft": jnum(h, 2), "from_q_cfs": jnum(a), "to_q_cfs": jnum(b)} for h, a, b in self.errata_applied[v.rid]]})
        R["shift_curves.json"] = jdump({"curves": curves}) + "\n"
        R["rating_tables_used.json"] = jdump({"ratings": rts}) + "\n"
        lines = []
        for sid in self.sites:
            for on, off, e_on, e_off in sorted(self.ice[sid], key=lambda p: p[0]):
                pts = self.kpts.get((sid, on), [])
                n = sum(1 for t in self.times.get(sid, []) if on <= t and (off is None or t < off))
                lines.append(jdump({"site": sid, "on_lst": fmt(on), "off_lst": None if off is None else fmt(off), "on_entry": e_on, "off_entry": e_off,
                                    "k_points": [{"meas_no": no, "time_lst": fmt(t), "k": jnum(k, 3)} for t, k, no in pts],
                                    "default_k": None if pts else jnum(exact(self.winter[sid]), 2), "unit_values": n}))
        R["ice_periods.jsonl"] = "".join(x + "\n" for x in lines)
        rows = []
        for sid in self.sites:
            for d in self.days:
                mean, cover, n, codes = self.dv[(sid, d)]
                rows.append([sid, d.isoformat(), "" if mean is None else show(mean), show(Fraction(cover, 3600), 2), n, ";".join(codes)])
        R["daily_values.csv"] = table_text(["site", "date", "q_mean_cfs", "coverage_h", "n_readings", "codes"], rows, ",")
        xml = [f'<monthly_summary network="{self.network}" period_start="{self.period_start}" period_end="{self.period_end}">']
        stats = []
        for sid in self.sites:
            months = {}
            for d in self.days:
                months.setdefault(d.strftime("%Y-%m"), []).append(self.dv[(sid, d)][0])
            for mon, vals in months.items():
                have = [v for v in vals if v is not None]
                attrs = {"site": sid, "month": mon, "days": str(len(vals)), "complete_days": str(len(have))}
                if have:
                    total = sum(have, Fraction(0))
                    vol = dp(total * Fraction(86400, 43560), 1)
                    attrs.update(mean_cfs=show(discharge_table(total / len(have))), min_cfs=show(min(have)), max_cfs=show(max(have)),
                                 volume_af=show(vol, 1), runoff_in=show(dp(vol * 12 / (self.area[sid] * 640), 2), 2))
                else:
                    attrs.update(mean_cfs="", min_cfs="", max_cfs="", volume_af="", runoff_in="")
                attrs["complete"] = "true" if len(have) == len(vals) else "false"
                xml.append("  <month " + " ".join(f'{k}="{v}"' for k, v in attrs.items()) + "/>")
            peak = None
            for t in self.times.get(sid, []):
                if self.p0 <= t < self.p1:
                    q = self.uv[(sid, t)][6]
                    if peak is None or q > peak[0]:
                        peak = (q, t)
            vals = [self.dv[(sid, d)][0] for d in self.days]
            low = None
            for i in range(len(vals) - 6):
                w = vals[i:i + 7]
                if None not in w:
                    mv = sum(w, Fraction(0)) / 7
                    if low is None or mv < low[0]:
                        low = (mv, self.days[i])
            have = [v for v in vals if v is not None]
            codes = [self.dv[(sid, d)][3] for d in self.days]
            stats.append({"site": sid, "peak_q_cfs": jnum(peak[0]) if peak else None, "peak_time_lst": fmt(peak[1]) if peak else None,
                          "min_7day_cfs": jnum(discharge_table(low[0])) if low else None, "min_7day_start": low[1].isoformat() if low else None,
                          "mean_cfs": jnum(discharge_table(sum(have, Fraction(0)) / len(have))) if have else None, "complete_days": len(have),
                          "inc_days": sum("INC" in c for c in codes), "ice_days": sum("ICE" in c for c in codes), "backup_days": sum("B" in c for c in codes),
                          "above_rating_days": sum(">" in c for c in codes),
                          "shift_points": sum(1 for m in self.meas if m["site"] == sid and m["decision"] == "SHIFT"),
                          "ice_measurements": sum(1 for m in self.meas if m["site"] == sid and m["decision"] == "ICE")})
        xml.append("</monthly_summary>")
        R["monthly_summary.xml"] = "\n".join(xml) + "\n"
        R["period_statistics.json"] = jdump({"sites": stats}) + "\n"
        R["alias_resolution.csv"] = table_text(["token", "site", "records"], [[t, s, n] for (t, s), n in sorted(self.tokens.items())], ",")
        R["dedup_report.json"] = jdump(dict(self.count)) + "\n"
        R["source_lineage.json"] = jdump({"files": self.lineage}) + "\n"
        lines = [jdump({"site": k[0], "sensor": k[1], "time_lst": fmt(k[2]), "reason": why, "file": f})
                 for k, why, f in sorted(self.excluded, key=lambda e: (e[0][0], e[0][2], e[0][1]))]
        R["reading_exclusions.jsonl"] = "".join(x + "\n" for x in lines)
        R["amendment_ledger.psv"] = table_text(["seq", "site", "sensor", "time_lst", "op", "status"], self.edit_rows, "|")
        kv = [("network", self.network), ("period_start", self.period_start), ("period_end", self.period_end), ("rating_sheet", self.sheet_rating),
              ("index_sheet", self.sheet_index), ("site_sheet", self.sheet_site), ("max_gap_minutes", self.max_gap),
              ("min_coverage_fraction", show(self.min_cov, 2)), ("record_margin_hours", self.margin), ("drift_tolerance_default_ft", self.drift_default),
              ("tolerance_table", "T-2"), ("tolerance_E_pct", self.tolerance["E"]), ("tolerance_G_pct", self.tolerance["G"]),
              ("tolerance_F_pct", self.tolerance["F"]), ("winter_table", "W-1"), ("errata_table", "R-2"),
              ("errata_applied", sum(len(v) for v in self.errata_applied.values())), ("date_system", "1904" if self.d1904 else "1900"),
              ("clock_standard_offset_minutes", self.clock.std), ("dst_rule", self.clock.rule)]
        for sid in self.sites:
            kv += [(f"drift_tolerance_{sid}", show(self.tol_of(sid), 2)), (f"max_gap_{sid}", self.gap_of(sid)), (f"winter_k_{sid}", self.winter[sid])]
        R["parameters_used.yaml"] = "".join(f"{k}: {v}\n" for k, v in kv)
        R.update(self.comparisons())
        return R

    def comparisons(self):  # noqa: C901
        fmt = self.clock.fmt
        R = {}
        pub = {}
        with open(self.p("dv_pub_26q2.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                sid = Resolver.norm(r["site"])
                if sid in self.scope:
                    y, m, d = (int(x) for x in r["date"].split("-"))
                    pub[(sid, date(y, m, d))] = exact(r["q_mean_cfs"]) if r["q_mean_cfs"].strip() else None
        rows = []
        for key in sorted(set(pub) | set(self.dv)):
            p = pub.get(key)
            q = self.dv[key][0] if key in self.dv else None
            if p is None and q is None:
                continue
            diff = None if p is None or q is None else q - p
            status = "ONLY_PUBLISHED" if q is None else "ONLY_RECOMPUTED" if p is None else ("MATCH" if diff == 0 else "DIFF")
            rows.append([key[0], key[1].isoformat(), "" if p is None else show(p), "" if q is None else show(q), "" if diff is None else show(diff), status])
        R["variance_vs_published.csv"] = table_text(["site", "date", "published_cfs", "recomputed_cfs", "diff_cfs", "status"], rows, ",")
        by = {m["no"]: m for m in self.meas}
        rows = []
        with open(self.p("shift_wksht_pub.csv"), encoding="utf-8") as fh:
            wk = sorted(csv.DictReader(fh), key=lambda r: int(r["meas_no"]))
        for r in wk:
            no = int(r["meas_no"])
            ps = exact(r["shift_ft"]) if r["shift_ft"].strip() else None
            m = by.get(no)
            if m is None:
                rows.append([no, r["site"], r["decision"], "" if ps is None else show(ps, 2), "", "", "NOT_FOUND"])
                continue
            agree = m["decision"] == r["decision"] and (m["decision"] != "SHIFT" or m["shift"] == ps)
            rows.append([no, m["site"], r["decision"], "" if ps is None else show(ps, 2), m["decision"], "" if m["shift"] is None else show(m["shift"], 2),
                         "AGREE" if agree else "DIFFER"])
        R["shift_vs_published.csv"] = table_text(["meas_no", "site", "published_decision", "published_shift_ft", "recomputed_decision",
                                                  "recomputed_shift_ft", "status"], rows, ",")
        rows = []
        with open(self.p("hydro_dash_export.tsv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                y, m, d = (int(x) for x in r["date"].split("-"))
                day = date(y, m, d)
                noon = self.clock.lst_to_utc(civil_seconds(y, m, d, 12))
                sid = self.resolve(r["station"], noon)
                if sid not in self.scope or (sid, day) not in self.dv:
                    continue
                dq = exact(r["daily_cfs"]) if r["daily_cfs"].strip() else None
                mean, _, _, codes = self.dv[(sid, day)]
                rice = "Y" if "ICE" in codes else "N"
                qok = dq == mean
                if qok and rice == r["ice_flag"]:
                    continue
                rows.append([sid, day.isoformat(), "" if dq is None else show(dq), "" if mean is None else show(mean), r["ice_flag"], rice,
                             "Y" if qok else "N", "Y" if rice == r["ice_flag"] else "N"])
        rows.sort(key=lambda r: (r[0], r[1]))
        R["dashboard_disagreements.tsv"] = table_text(["site", "date", "dashboard_cfs", "recomputed_cfs", "dashboard_ice", "recomputed_ice", "q_agrees",
                                                       "ice_agrees"], rows, "\t")
        out = []
        for ln in open(self.p("uv_cache_r3.jsonl"), encoding="utf-8"):
            if not ln.strip():
                continue
            o = json.loads(ln, parse_float=Decimal)
            t = self.clock.lst_to_utc(naive_text_seconds(o["t_lst"]))
            sid = self.resolve(o["station"], t)
            if sid not in self.scope:
                continue
            cq = exact(str(o["q_cfs"]))
            uv = self.uv.get((sid, t))
            status = "MISSING" if uv is None else ("CURRENT" if uv[6] == cq else "STALE")
            out.append((sid, t, {"site": sid, "time_lst": fmt(t), "cached_cfs": jnum(cq), "recomputed_cfs": jnum(uv[6]) if uv else None, "status": status}))
        out.sort(key=lambda x: (x[0], x[1]))
        R["cache_divergence.jsonl"] = "".join(jdump(x[2]) + "\n" for x in out)
        md = ["# Streamflow reconciliation", "", "## Summary", "", "| site | published_days | recomputed_days | compared | diff_count | mean_diff_cfs |",
              "|---|---|---|---|---|---|"]
        for sid in self.sites:
            pd = [k for k, v in pub.items() if k[0] == sid and v is not None]
            rd = [k for k in self.dv if k[0] == sid and self.dv[k][0] is not None]
            both = [k for k in rd if pub.get(k) is not None]
            diffs = [self.dv[k][0] - pub[k] for k in both]
            md.append(f"| {sid} | {len(pd)} | {len(rd)} | {len(both)} | {sum(1 for x in diffs if x != 0)} | "
                      f"{show(sum(diffs, Fraction(0)) / len(diffs), 2) if diffs else ''} |")
        md += ["", "## Run settings", "", "| setting | published_run | in_force |", "|---|---|---|"]
        inforce = {"rating_sheet": self.sheet_rating, "tolerance_table": "T-2", "errata": "R-2", "measurement_gage_height": "record_mean",
                   "deviation_basis": "shift_in_use", "daily_method": "time_weighted_discharge", "day_basis": "local_standard_time",
                   "gage_height_corrections": "prorated_visit_errors", "edits_journal": "seq_order"}
        pack = open(self.p("dv_compute_pack.md"), encoding="utf-8").read()
        sec = pack.split("## Run settings", 1)[1].split("\n## ", 1)[0]
        for ln in sec.splitlines():
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) == 2 and cells[0] in inforce:
                md.append(f"| {cells[0]} | {cells[1]} | {inforce[cells[0]]} |")
        md += ["", "## Measurement decisions", "", "| site | measurements | shift | check | ice | rejected | no_record |", "|---|---|---|---|---|---|---|"]
        for sid in self.sites:
            ms = [m for m in self.meas if m["site"] == sid]
            md.append(f"| {sid} | {len(ms)} | " + " | ".join(str(sum(1 for m in ms if m["decision"] == d))
                                                               for d in ("SHIFT", "CHECK", "ICE", "REJECTED", "NO_RECORD")) + " |")
        R["reconciliation.md"] = "\n".join(md) + "\n"
        return R


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: run_flowrecord.py DATA_DIR OUT_DIR\n")
        return 2
    data, out = os.path.abspath(argv[1]), os.path.abspath(argv[2])
    run = Run(data)
    run.load_settings()
    run.load_books()
    run.ingest()
    run.apply_edits()
    run.stage()
    run.visits()
    run.measurements()
    run.unit_values()
    run.daily()
    reports = run.reports()
    os.makedirs(out, exist_ok=True)
    files = []
    for name in REPORT_ORDER:
        blob = reports[name].encode("utf-8")
        with open(os.path.join(out, name), "wb") as fh:
            fh.write(blob)
        files.append({"name": name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()})
    with open(os.path.join(out, "manifest.json"), "wb") as fh:
        fh.write((json.dumps({"files": files}, indent=1) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
