#!/usr/bin/env python3
"""Sentinel training-set release builder.

usage: transform.py [DATA_DIR] [OUT_DIR] [--prior PRIOR_OUT_DIR]

Builds one training-set release of the Sentinel card-fraud model from the exports in DATA_DIR,
following the release build specification and the documents it references, and writes the
release outputs to OUT_DIR. With --prior the release is built as a delta release on top of the
prior release's output directory. Defaults: /app/data and /app/out.
"""
from __future__ import annotations

import bisect
import configparser
import csv
import datetime as dt
import hashlib
import io
import json
import mailbox
import math
import re
import sqlite3
import sys
import tempfile
import tomllib
import zipfile
from decimal import Decimal, getcontext
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

TRACE = None  # authoring hook: a dict filled with provenance when set by an importing script

UTC = dt.timezone.utc
EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)
DAY = 86400
SPLITS = ["train", "val", "test", "oot"]
REGION_GROUPS = ["central", "east", "north", "south", "west"]
SEGMENT_GROUPS = ["consumer", "corporate", "enterprise", "smb"]
PRECEDENCE = ["SET", "TRM", "LEG", "PAR", "GW", "SDK"]
NUMERIC = ["amount_usd_cents", "account_age_days", "txn_count_24h", "amount_sum_7d_usd_cents", "merchant_cb_rate_bps",
           "ip_risk_score", "kyc_tier"]
CATEGORICAL = ["entry_mode", "mcc_risk_group", "issuer_group"]
REASONS = ["invalid_key", "replay", "voided", "duplicate", "declined", "reversed", "refund", "test_transaction",
           "already_released", "lookback_context", "outside_window", "consent_withdrawn", "retracted", "immature_label",
           "unresolved_label"]
STATUS_REASON = {"declined": "declined", "reversed": "reversed", "refund": "refund", "test": "test_transaction"}
TIER_WEIGHT = {"gold": 3, "silver": 2, "bronze": 1, "probation": 0}
NO_IP = {"", "-", "UNKNOWN", "0.0.0.0", "NULL", "N/A"}
NO_DEVICE = {"", "UNKNOWN"}  # data dictionary: '', 'UNKNOWN' or null (a JSON null is read as '')


class Missing(Exception):
    pass


# ============================================================================================ time
def ts_of(text: str) -> int:
    t = text.strip()
    if len(t) == 10:
        t += "T00:00:00"
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    d = dt.datetime.fromisoformat(t)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return int((d - EPOCH).total_seconds())


def iso(sec: int) -> str:
    return (EPOCH + dt.timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_of(sec: int) -> str:
    return (EPOCH + dt.timedelta(seconds=sec)).strftime("%Y-%m-%d")


def date_ts(day: str) -> int:
    return ts_of(day)


def excel_ts(serial, epoch1904=False) -> int:
    if isinstance(serial, dt.datetime):
        return int(serial.replace(tzinfo=UTC).timestamp())
    base = dt.datetime(1904, 1, 1, tzinfo=UTC) if epoch1904 else dt.datetime(1899, 12, 30, tzinfo=UTC)
    v = Fraction(str(serial)) if not isinstance(serial, Fraction) else serial
    secs = v * 86400
    n = math.floor(secs + Fraction(1, 2))
    return int((base - EPOCH).total_seconds()) + n


def last_sunday(year, month):
    nxt = dt.date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - dt.timedelta(days=1)
    return last - dt.timedelta(days=(last.weekday() - 6) % 7)


def nth_sunday(year, month, n):
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))


class Zones:
    def __init__(self, zones):
        self.zones = zones  # name -> (std_minutes, rule, shift)

    def offset(self, zone, utc):
        std, rule, shift = self.zones[zone]
        y = int(day_of(utc)[:4])
        T = lambda d, h: ts_of(f"{d.isoformat()}T{h}")
        if rule == "eu":
            a, b = T(last_sunday(y, 3), "01:00:00"), T(last_sunday(y, 10), "01:00:00")
            return std + shift if a <= utc < b else std
        if rule == "il":
            a, b = T(last_sunday(y, 3), "00:00:00") - 2 * DAY, T(last_sunday(y, 10), "00:00:00")
            return std + shift if a <= utc < b else std
        if rule == "us":
            a = T(nth_sunday(y, 3, 2), "02:00:00") - std * 60
            b = T(nth_sunday(y, 11, 1), "02:00:00") - (std + shift) * 60
            return std + shift if a <= utc < b else std
        if rule == "south":
            a = T(nth_sunday(y, 10, 1), "02:00:00") - std * 60
            b = T(nth_sunday(y, 4, 1), "03:00:00") - (std + shift) * 60
            return std + shift if (utc >= a or utc < b) else std
        if rule == "nz":
            a = T(last_sunday(y, 9), "02:00:00") - std * 60
            b = T(nth_sunday(y, 4, 1), "03:00:00") - (std + shift) * 60
            return std + shift if (utc >= a or utc < b) else std
        if rule == "cl":
            a, b = T(nth_sunday(y, 9, 1), "04:00:00"), T(nth_sunday(y, 4, 1), "03:00:00")
            return std + shift if (utc >= a or utc < b) else std
        return std

    def local_to_utc(self, zone, naive_secs):
        """naive_secs: local wall clock read as if UTC. Gap -> pre-transition offset; overlap -> earlier instant."""
        std, rule, shift = self.zones[zone]
        cands = []
        for off in sorted({std, std + shift} if rule != "none" else {std}, reverse=True):
            u = naive_secs - off * 60
            if self.offset(zone, u) == off:
                cands.append(u)
        if cands:
            return min(cands)
        before = self.offset(zone, naive_secs - std * 60 - 6 * 3600)
        return naive_secs - before * 60


def naive_secs(text, fmt):
    return int((dt.datetime.strptime(text.strip(), fmt).replace(tzinfo=UTC) - EPOCH).total_seconds())


# ============================================================================================ numbers / ids
def half_even(v: Fraction) -> int:
    v = Fraction(v)
    fl = v.numerator // v.denominator
    rem = v - fl
    if rem > Fraction(1, 2):
        return fl + 1
    if rem < Fraction(1, 2):
        return fl
    return fl if fl % 2 == 0 else fl + 1


def fixed6(v) -> str:
    n = half_even(Fraction(v) * 1000000)
    sign = "-" if n < 0 else ""
    n = abs(n)
    return f"{sign}{n // 1000000}.{n % 1000000:06d}"


def dec_frac(text: str) -> Fraction:
    return Fraction(Decimal(text.strip()))


def major_to_minor(text, exp, eu=False):
    t = text.strip().replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg, t = True, t[1:-1]
    if t.startswith("-"):
        neg, t = True, t[1:]
    if eu:
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", "")
    v = Fraction(Decimal(t)) * 10 ** exp
    if v.denominator != 1:
        raise ValueError(f"amount {text!r} has more decimals than the currency exponent")
    return -int(v) if neg else int(v)


WS = " \t\r\n\u00a0\u202f"


def ck(x) -> str:
    """Reference-table key: trimmed (ASCII whitespace, no-break spaces) and upper-cased."""
    return "" if x is None else str(x).strip(WS).upper()


def canon(raw, kind):
    """Canonical identifier or None when invalid."""
    if raw is None:
        return None
    s = str(raw).strip(WS).upper()
    if not s or any(ord(c) > 127 for c in s):
        return None
    pats = {"account": ("AC-", 6, "d"), "merchant": ("MR-", 5, "d"), "legacy": ("L-", 7, "d"), "device": ("DV-", 8, "x"),
            "ip": ("IP-", 7, "x")}
    pre, width, kind_ = pats[kind]
    if not s.startswith(pre):
        return None
    body = s[len(pre):]
    if kind_ == "d":
        if not body.isdigit() or len(body) > width:
            return None
        return pre + body.rjust(width, "0")
    if not re.fullmatch(r"[0-9A-F]+", body) or len(body) > width:
        return None
    return pre + body.rjust(width, "0")


# ============================================================================================ readers
def decode_lines(data: bytes):
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


def read_delimited(data: bytes, delim: str, header_names: set):
    """-> (records as dicts by raw header, control lines, comment lines). Handles drift, ragged rows, comments."""
    lines = decode_lines(data)
    text = "\n".join(lines)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    header, recs, controls, comments = None, [], [], []
    for row in reader:
        if not row or all(c == "" for c in row):
            continue
        if row[0].startswith("#"):
            if row[0].startswith("#CONTROL|") and len(row) == 1:
                _, part, cnt, hsum = row[0].split("|")
                controls.append((part, int(cnt), int(hsum)))
            else:
                comments.append(delim.join(row))
            continue
        cells = [c.strip(" ") for c in row]
        if header is None:
            header = cells
            continue
        if len(cells) >= len(header) and set(c for c in cells if c) <= header_names and len([c for c in cells if c]) == len(header):
            header = [c for c in cells if c]
            continue
        while len(cells) > len(header) and cells[-1] == "":
            cells.pop()
        recs.append({h: (cells[i] if i < len(cells) else "") for i, h in enumerate(header)})
    return recs, controls, comments


def read_jsonl(data: bytes):
    recs, controls, metas = [], [], []
    for line in decode_lines(data):
        if not line.strip():
            continue
        o = json.loads(line)
        if "_control" in o:
            c = o["_control"]
            controls.append((c["partition"], int(c["row_count"]), int(c["hash_total"])))
        elif "_meta" in o:
            metas.append(o["_meta"])
        else:
            recs.append(o)
    return recs, controls, metas


def text_lines(data: bytes):
    return [ln for ln in decode_lines(data) if ln.strip()]


def kv_line(line):
    return dict(re.findall(r"(\w+)=(\S+)", line))


# ---- documents (md / html / docx / pdf) -> (tables {caption: (header, rows)}, paragraphs)
def md_tables(data: bytes):
    lines = data.decode("utf-8-sig").split("\n")
    tables, paras, i = {}, [], 0
    while i < len(lines):
        m = re.match(r"^\*\*Table: (.*)\*\*$", lines[i])
        if m:
            cap = m.group(1)
            i += 2
            header = split_md(lines[i])
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(split_md(lines[i]))
                i += 1
            tables[cap] = (header, rows)
            continue
        if lines[i].strip():
            paras.append(lines[i].lstrip("# "))
        i += 1
    return tables, paras


def split_md(line):
    body = line.strip()[1:-1]
    cells, cur, esc = [], "", False
    for ch in body:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += ch
    cells.append(cur.strip())
    return cells


def html_tables(data: bytes):
    data = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.tables, self.paras, self.mode, self.buf = {}, [], None, ""
            self.cap = self.row = self.header = self.rows = None

        def handle_starttag(self, tag, attrs):
            if tag == "caption":
                self.mode, self.buf = "cap", ""
            elif tag == "tr":
                self.row = []
            elif tag in ("td", "th"):
                self.mode, self.buf = "cell", ""
            elif tag in ("p", "h1", "h2"):
                self.mode, self.buf = "p", ""
            elif tag == "table":
                self.header, self.rows = None, []

        def handle_endtag(self, tag):
            if tag == "caption":
                self.cap, self.mode = self.buf.strip(), None
            elif tag in ("td", "th"):
                self.row.append(self.buf.strip())
                self.mode = None
            elif tag == "tr":
                if self.header is None:
                    self.header = self.row
                else:
                    self.rows.append(self.row)
            elif tag == "table":
                self.tables[self.cap] = (self.header, self.rows)
            elif tag in ("p", "h1", "h2"):
                self.paras.append(self.buf.strip())
                self.mode = None

        def handle_data(self, d):
            if self.mode:
                self.buf += d

    p = P()
    p.feed(data.decode("utf-8"))
    return p.tables, p.paras


def docx_tables(data: bytes):
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    body = root.find(W + "body")
    tables, paras, cap = {}, [], None
    for el in body:
        tag = el.tag[len(W):]
        if tag == "p":
            text = "".join(t.text or "" for t in el.iter(W + "t"))
            if text.startswith("Table: "):
                cap = text[7:]
            elif text:
                paras.append(text)
        elif tag == "tbl":
            rows = [["".join(t.text or "" for t in tc.iter(W + "t")) for tc in tr.findall(W + "tc")] for tr in el.findall(W + "tr")]
            tables[cap] = (rows[0], rows[1:])
    return tables, paras


def pdf_tables(data: bytes):
    from pypdf import PdfReader
    lines = []
    for page in PdfReader(io.BytesIO(data)).pages:
        lines.extend((page.extract_text() or "").split("\n"))
    tables, paras = {}, []
    cap = header = rows = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^Table: (.*?)( \(continued\))?$", ln)
        if m:
            if m.group(2):
                i += 2
                continue
            cap = m.group(1)
            header = [h.strip() for h in lines[i + 1].split(" | ")]
            rows = []
            tables[cap] = (header, rows)
            i += 2
            continue
        if re.match(r"^Page \d+$", ln.strip()):
            i += 1
            continue
        if cap is not None and " | " in ln and len(ln.split(" | ")) == len(header):
            rows.append([c.strip() for c in ln.split(" | ")])
        else:
            if ln.strip():
                cap = None
                paras.append(ln)
        i += 1
    return tables, paras


def doc_tables(name, data):
    if name.endswith(".md"):
        return md_tables(data)
    if name.endswith(".html"):
        return html_tables(data)
    if name.endswith(".docx"):
        return docx_tables(data)
    return pdf_tables(data)


def apply_overrides(doc):
    tables, paras = doc
    for p in paras:
        m = re.match(r"^Footnote: override (.+?); (.+?); (.+?); (.*)$", p.strip())
        if not m or m.group(1) not in tables:
            continue
        header, rows = tables[m.group(1)]
        if m.group(3) not in header:
            continue
        j = header.index(m.group(3))
        key = ck(m.group(2))
        for r in rows:
            if ck(r[0]) == key or (len(r) > 1 and ck(f"{r[0].strip()}/{r[1].strip()}") == key):
                r[j] = m.group(4).strip()
    return doc


def num(text) -> Fraction:
    t = str(text).strip().replace("\u00a0", "").replace(" ", "")
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    return Fraction(Decimal(t))


def dicts(table):
    header, rows = table
    return [dict(zip(header, r)) for r in rows]


# ============================================================================================ release
class Release:
    def __init__(self, data_dir: Path, out_dir: Path, prior: Path | None):
        self.data = data_dir
        self.out = out_dir
        self.prior_dir = prior
        self.problems = []
        self.cache = {}

    # ------------------------------------------------------------------------------ file access
    def raw(self, name):
        p = self.data / name
        if not p.is_file():
            raise Missing(name)
        return p.read_bytes()

    def wb(self, name):
        """All sheets of a workbook as lists of row tuples (header first), loaded once."""
        key = ("wb", name)
        if key not in self.cache:
            import openpyxl
            book = openpyxl.load_workbook(io.BytesIO(self.raw(name)), read_only=True, data_only=True)
            self.cache[key] = {ws.title: list(ws.iter_rows(values_only=True)) for ws in book.worksheets}
        return self.cache[key]

    def delim(self, name, delim, header_names=frozenset()):
        key = ("dl", name)
        if key not in self.cache:
            self.cache[key] = read_delimited(self.raw(name), delim, set(self.conventions(name)))
        return self.cache[key]

    def jsonl(self, name):
        key = ("jl", name)
        if key not in self.cache:
            self.cache[key] = read_jsonl(self.raw(name))
        return self.cache[key]

    def by_source(self, sid):
        return self.cat_by_sid.get(sid)

    def doc(self, sid):
        name = self.by_source(sid)
        if name is None:
            raise Missing(sid)
        if name not in self.cache:
            self.cache[name] = apply_overrides(doc_tables(name, self.raw(name)))
        return self.cache[name]

    def para(self, sid, pattern):
        for p in self.doc(sid)[1]:
            m = re.search(pattern, p)
            if m:
                return m
        raise Missing(f"{sid}: {pattern}")

    # ------------------------------------------------------------------------------ main
    def run(self):
        try:
            self.load_register()
        except Missing as exc:
            self.problems.append(f"missing {exc}")
            self.catalog = []
            return self.write_held()
        missing = [c["file"] for c in self.catalog if not (self.data / c["file"]).is_file()]
        if missing:
            self.problems += [f"missing {m}" for m in missing]
            return self.write_held()
        try:
            self.load_all()
            self.reconcile()
        except Missing as exc:
            self.problems.append(f"missing {exc}")
        if self.problems:
            return self.write_held()
        self.build()
        self.write_published()

    # ------------------------------------------------------------------------------ register + config
    def load_register(self):
        reg = None
        for p in sorted(self.data.glob("*.md")):
            tables, _ = md_tables(p.read_bytes())
            if "Catalog" in tables and "Column map" in tables:
                reg = (p.name, tables)
        if reg is None:
            raise Missing("source register")
        self.register_name, tables = reg
        self.catalog = dicts(tables["Catalog"])
        self.cat_by_sid = {c["source_id"]: c["file"] for c in self.catalog}
        self.sid_of = {c["file"]: c["source_id"] for c in self.catalog}
        self.colmap = {}
        for r in dicts(tables["Column map"]):
            self.colmap.setdefault(r["file"], []).append(r)
        self.batch_file = {r["batch_id"]: r["file"] for r in dicts(tables["Batch index"])}
        self.register_tables = tables

    def load_all(self):
        cfg = tomllib.loads(self.raw(self.by_source("release_config")).decode("utf-8-sig"))
        self.cfg = cfg["release"]
        self.pins = cfg.get("pinned", [])
        c = self.cfg
        self.mode = c["mode"]
        self.release_id = c["release_id"]
        self.t_lookback = date_ts(c["lookback_start"])
        self.t_start = date_ts(c["window_start"])
        self.t_end = date_ts(c["window_end"])
        self.t_cutoff = date_ts(c["label_cutoff"])
        self.t_oot = date_ts(c["oot_start"])
        self.maturity = int(c["maturity_days"])
        self.load_governance()
        self.load_reference()
        self.load_entities()
        self.load_events()
        self.load_labels()
        self.load_features()
        if self.mode == "delta":
            if self.prior_dir is None:
                raise Missing("prior release directory")
            st = json.loads((self.prior_dir / "product_summary.json").read_text(encoding="utf-8"))
            if st.get("status") != "PUBLISHED":
                raise Missing("published prior release state")
            st["account_splits"] = {c["account_id"]: c["split"] for c in st.get("clusters", [])}
            self.prior = st

    # ------------------------------------------------------------------------------ governance
    def load_governance(self):
        tables, paras = self.doc("governance_charter")
        self.authority = {}
        for r in dicts(tables["Source authority windows"]):
            self.authority.setdefault((r["file"].strip(), r["field_group"].strip()), []).append({k: v.strip() for k, v in r.items()})
        self.incidents = {}
        for line in text_lines(self.raw(self.by_source("incident_log"))):
            parts = line.split(" ", 3)
            if len(parts) < 3:
                continue
            at, inc, ev = parts[0], parts[1], parts[2]
            kv = kv_line(parts[3] if len(parts) > 3 else "")
            d = self.incidents.setdefault(inc, {})
            if ev == "OPENED":
                d["system"] = kv.get("system")
                d.setdefault("start", ts_of(kv["start"])) if "start" in kv else None
            elif ev == "WINDOW_REVISED":
                d["start"], d["end"] = ts_of(kv["start"]), ts_of(kv["end"])
                d["revised"] = True
            elif ev == "RESOLVED" and not d.get("revised") and "end" in kv:
                d["end"] = ts_of(kv["end"])

    def auth(self, file, group, t=None):
        rows = self.authority.get((file, group))
        if not rows:
            return False
        tt = self.t_cutoff if t is None else t
        for r in rows:
            if r["incident"] and r["incident"] in self.incidents and not r["valid_from"]:
                inc = self.incidents[r["incident"]]
                if r["authority"] == "primary" and inc["start"] <= tt < inc["end"]:
                    return True
                continue
            if r["valid_from"] and date_ts(r["valid_from"]) <= tt < date_ts(r["valid_to"]) and r["authority"] == "primary":
                return True
        return False

    def outage_windows(self, system):
        return [(d["start"], d["end"]) for d in self.incidents.values() if d.get("system") == system and "end" in d]

    # ------------------------------------------------------------------------------ reference data
    def load_reference(self):
        tz = tomllib.loads(self.raw(self.by_source("timezone_rules")).decode("utf-8-sig"))
        self.zones = Zones({ck(z["name"]): (int(z["std_offset_minutes"]), z["dst_rule"].strip(), int(z["dst_shift_minutes"])) for z in tz["zone"]})
        self.postal_zone = {str(p["prefix"]).strip(): ck(p["zone"]) for p in tz["postal_zone"]}
        clock = self.doc("clock_handbook")[0]
        self.zone_alias = {ck(r["alias"]): ck(r["zone"]) for r in dicts(clock["Zone aliases"])}
        fxh = self.doc("fx_handbook")[0]
        self.exponent = {ck(r["currency"]): int(r["exponent"]) for r in dicts(fxh["Minor units"])}
        self.fixing = {(ck(r["currency"]), r["date"].strip()): {k: v.strip() for k, v in r.items()} for r in dicts(fxh["Fixing calendar"])}
        self.treasury_ccy = {ck(r["currency"]) for r in dicts(fxh["Fixing calendar"])}
        root = ET.fromstring(self.raw(self.by_source("fx.treasury")))
        self.treasury = {}
        for fx in root.iter("Fixing"):
            self.treasury[(ck(fx.get("currency")), fx.get("date").strip())] = num(fx.get("rate")) / int(fx.get("unit"))
        import pyarrow.parquet as pq
        tbl = pq.read_table(io.BytesIO(self.raw(self.by_source("fx.vendor")))).to_pylist()
        self.vendor = {(ck(r["currency"]), r["rate_date"].isoformat()): Fraction(r["usd_per_unit"]) for r in tbl}
        recs, _, _ = self.delim(self.by_source("fx.corrections"), ",", frozenset(self.conventions(self.by_source("fx.corrections"))))
        self.fx_corr = {(ck(r["currency"]), r["rate_date"].strip()): num(r["corrected_usd_per_unit"]) for r in recs
                        if r["verdict"].strip() == "corrected"}
        self.fx_corr_rows = recs
        self.dict_tables = self.doc("data_dictionary")[0]
        self.region_group = {ck(r["region"]): r["group"].strip() for r in dicts(self.dict_tables["Region groups"])}
        self.segment_group = {ck(r["segment"]): r["group"].strip() for r in dicts(self.dict_tables["Segment groups"])}
        self.status = {(ck(r["system"]), ck(r["raw_code"])): r["meaning"].strip() for r in dicts(self.dict_tables["Status codes"])}
        self.entry = {(ck(r["system"]), ck(r["raw_code"])): r["entry_mode"].strip() for r in dicts(self.doc("entry_codes")[0]["Entry mode codes"])}

    def usd_per_unit(self, ccy, day):
        if ccy == "USD":
            return Fraction(1)
        if ccy in self.treasury_ccy:
            row = self.fixing.get((ccy, day))
            use = day
            if row and row["status"] == "holiday":
                use = row["substitute_date"]
            v = self.treasury.get((ccy, use))
            if v is None:
                raise Missing(f"treasury fixing {ccy} {use}")
            return v
        if (ccy, day) in self.fx_corr:
            return self.fx_corr[(ccy, day)]
        v = self.vendor.get((ccy, day))
        if v is None:
            raise Missing(f"vendor rate {ccy} {day}")
        return v

    def usd_cents(self, amt, ccy, t):
        return half_even(Fraction(amt) * self.usd_per_unit(ccy, day_of(t)) * 100 / 10 ** self.exponent[ccy])

    # ------------------------------------------------------------------------------ entities
    def load_entities(self):
        import yaml
        import pyarrow.parquet as pq
        base = yaml.safe_load(self.raw(self.by_source("accounts.base")))
        rev = yaml.safe_load(self.raw(self.by_source("accounts.revision")))
        nxt = yaml.safe_load(self.raw(self.by_source("accounts.next")))
        self.acc = {}
        for a in base["accounts"]:
            aid = canon(a["id"], "account")
            self.acc[aid] = dict(created=ts_of(str(a["created_at"])), segment=str(a["segment"]), postal=str(a["postal"]), change=None)
        self.rev_from = None
        for a in rev["accounts"]:
            aid = canon(a["id"], "account")
            cur = self.acc.get(aid)
            created = ts_of(str(a["created_at"]))
            if cur is None:
                self.acc[aid] = dict(created=created, segment=str(a["segment"]), postal=str(a["postal"]), change=None)
                continue
            if a.get("correction"):
                cur["created"] = created
            if a.get("effective_from"):
                cur["change"] = (date_ts(str(a["effective_from"])), str(a["segment"]), str(a["postal"]))
        self.legacy = {}
        nfile = self.by_source("accounts.next")
        if self.auth(nfile, "crosswalk"):
            for a in nxt["accounts"]:
                if a.get("legacy_id"):
                    self.legacy[canon(a["legacy_id"], "legacy")] = canon(a["id"], "account")
        self.merge = {}
        for line in text_lines(self.raw(self.by_source("account_merges.log"))):
            kv = kv_line(line)
            if " MERGE " in f" {line} ":
                self.merge[canon(kv["account"], "account")] = canon(kv["into"], "account")
        mm = json.loads(self.raw(self.by_source("account_merges.map")))
        for r in mm["map"]:
            a, c = canon(r["account"], "account"), canon(r["canonical"], "account")
            if a != c:
                self.merge[a] = c
        self.mer = {}
        self.mer_merge = {}
        for r in pq.read_table(io.BytesIO(self.raw(self.by_source("merchants.master")))).to_pylist():
            mid = canon(r["merchant_id"], "merchant")
            self.mer[mid] = dict(mcc=ck(r["mcc_subcode"]))
            if r["merged_into"]:
                self.mer_merge[mid] = canon(r["merged_into"], "merchant")
        nm = self.by_source("merchants.next")
        if self.auth(nm, "merges"):
            for r in pq.read_table(io.BytesIO(self.raw(nm))).to_pylist():
                if r["merged_into"]:
                    self.mer_merge[canon(r["merchant_id"], "merchant")] = canon(r["merged_into"], "merchant")
        recs, _, _ = self.delim(self.by_source("merchant_aliases"), ",", frozenset(self.conventions(self.by_source("merchant_aliases"))))
        self.alias = {}
        for r in recs:
            vt = r["valid_to"].strip()
            self.alias.setdefault(r["alias"].strip(WS).upper(), []).append(
                (r["valid_from"].strip(), None if vt in ("", "0000-00-00") else vt, canon(r["merchant_id"], "merchant")))
        hist = json.loads(self.raw(self.by_source("merchant_classification")))
        self.mcc_hist = {}
        for r in hist["history"]:
            self.mcc_hist.setdefault(canon(r["merchant_id"], "merchant"), []).append((ts_of(r["effective_from"]), ck(r["mcc_subcode"])))
        for v in self.mcc_hist.values():
            v.sort()
        ini = configparser.ConfigParser(interpolation=None)
        ini.read_string(self.raw(self.by_source("merchant_zones")).decode("utf-8-sig"))
        self.mer_zone = {canon(s, "merchant"): self.zone_alias[ck(ini[s]["zone"])] for s in ini.sections()}
        ini = configparser.ConfigParser(interpolation=None)
        ini.read_string(self.raw(self.by_source("terminal_skew")).decode("utf-8-sig"))
        self.skew = {ck(s): int(ini[s]["skew_seconds"]) for s in ini.sections()}
        recs, _, _ = self.delim(self.by_source("bin_ranges"), ",", frozenset(self.conventions(self.by_source("bin_ranges"))))
        self.bins = {ck(r["bin_prefix"]): r["issuer_group"].strip() for r in recs}
        recs, _, _ = self.delim(self.by_source("region_crosswalk"), ",", frozenset(self.conventions(self.by_source("region_crosswalk"))))
        self.region = {ck(r["postal"]): r["region"].strip() for r in recs}
        fd = tomllib.loads(self.raw(self.by_source("feature_definitions")).decode("utf-8-sig"))
        self.kyc_default = {(ck(k["segment"]), ck(k["region"])): int(k["tier"]) for k in fd["kyc_default"]}
        # consent
        self.withdrawn = set()
        recs, _, _ = self.delim(self.by_source("consent.portal"), ",", frozenset(self.conventions(self.by_source("consent.portal"))))
        last = {}
        for r in recs:
            if r["scope"].strip() not in ("training", "all"):
                continue
            at = ts_of(r["at"])
            if at > self.t_cutoff:
                continue
            a = canon(r["account_id"], "account")
            if a not in last or at >= last[a][0]:
                last[a] = (at, r["action"].strip())
        self.withdrawn |= {a for a, (at, act) in last.items() if act == "withdraw"}
        lg = json.loads(self.raw(self.by_source("consent.legal")))
        for o in lg["orders"]:
            if o["type"] == "erasure" and o["status"] == "executed" and ts_of(o["executed_at"]) <= self.t_cutoff:
                self.withdrawn.add(canon(o["account_id"], "account"))
        ini = configparser.ConfigParser(interpolation=None)
        ini.read_string(self.raw(self.by_source("consent.support")).decode("utf-8-sig"))
        for s in ini.sections():
            if ini[s]["status"].strip() == "withdrawn" and ts_of(ini[s]["updated"]) <= self.t_cutoff:
                self.withdrawn.add(canon(s, "account"))
        self.withdrawn = {self.canon_account(a) for a in self.withdrawn if a}

    def canon_account(self, aid):
        n = 0
        while aid in self.merge and n < 20:
            aid = self.merge[aid]
            n += 1
        return aid

    def canon_merchant(self, mid):
        n = 0
        while mid in self.mer_merge and n < 20:
            mid = self.mer_merge[mid]
            n += 1
        return mid

    def account_attr(self, aid, field, t):
        a = self.acc[aid]
        ch = a["change"]
        if ch and t >= ch[0]:
            return {"segment": ch[1], "postal": ch[2]}[field]
        return a[field]

    def mcc_at(self, mid, t):
        best = self.mer[mid]["mcc"]
        for eff, sc in self.mcc_hist.get(mid, ()):
            if eff <= t:
                best = sc
        return best

    def resolve_alias(self, text, t):
        day = day_of(t)
        best = None
        for vf, vt, mid in self.alias.get(text.strip(WS).upper(), ()):
            if vf <= day and (vt is None or day < vt):
                if best is None or vf > best[0]:
                    best = (vf, mid)
        return best[1] if best else None

    # ------------------------------------------------------------------------------ events
    def conventions(self, file):
        return {r["column"]: r for r in self.colmap.get(file, [])}

    def load_events(self):
        import pyarrow.parquet as pq
        self.rows = []
        self.controls_seen = {}
        self.records_count = {}
        for c in self.catalog:
            if c["role"] != "events":
                continue
            name, sid = c["file"], c["source_id"]
            cols = self.conventions(name)
            data = self.raw(name)
            sysname = sid.split(".")[0]
            out = []
            ctrl = []
            if sysname in ("settlement", "gateway"):
                delim = "," if sysname == "settlement" else "\t"
                recs, ctrl, _ = self.delim(name, delim, frozenset(cols))
                for r in recs:
                    out.append(self.norm_delim(name, sysname, r, cols))
            elif sysname == "sdk":
                recs, ctrl, _ = self.jsonl(name)
                for r in recs:
                    out.append(self.norm_sdk(name, r))
            elif sysname == "legacy":
                lines = decode_lines(data)
                layout = {}
                for col, r in cols.items():
                    m = re.match(r"(\w+)\[(\d+):(\d+)\]", col)
                    if m:
                        layout[m.group(1)] = (int(m.group(2)), int(m.group(3)))
                for ln in lines:
                    if not ln.strip():
                        continue
                    if ln[0] == "T":
                        ctrl.append((ln[1:14], int(ln[14:23]), int(ln[23:38])))
                    elif ln[0] == "D":
                        rec = {k: ln[s:e].rstrip(" ") for k, (s, e) in layout.items()}
                        out.append(self.norm_leg(name, rec))
            elif sysname == "partner":
                root = ET.fromstring(data)
                for o in root.iter("Order"):
                    out.append(self.norm_par(name, o))
                for cel in root.iter("Control"):
                    ctrl.append((cel.get("partition"), int(cel.get("rows")), int(cel.get("hash"))))
            elif sysname == "terminal":
                for r in pq.read_table(io.BytesIO(data)).to_pylist():
                    out.append(self.norm_trm(name, r))
            self.records_count[name] = len(out)
            for rw in out:
                rw["file"] = name
            if ctrl:
                self.controls_seen[name] = ctrl
            self.rows.extend(out)

    def _time(self, conv, text, zone=None):
        conv = conv.split(" ")[0]
        if conv == "iso_offset" or conv == "iso_utc":
            return ts_of(text)
        if conv == "epoch_s":
            return int(text)
        if conv == "epoch_ms":
            return int(text) // 1000
        raise ValueError(conv)

    def _amount(self, conv, text, ccy):
        if conv in ("minor", "minor_signed"):
            return int(str(text).strip().replace("+", ""))
        if conv == "major":
            return major_to_minor(str(text), self.exponent[ccy])
        if conv == "major_eu":
            return major_to_minor(str(text), self.exponent[ccy], eu=True)
        raise ValueError(conv)

    def norm_delim(self, name, sysname, r, cols):
        sysc = "SET" if sysname == "settlement" else "GW"
        f = {}
        for raw, v in r.items():
            spec = cols.get(raw)
            if spec is None:
                continue
            f.setdefault(spec["field"], (v, spec["convention"], raw))
        ccy = f["currency"][0].strip().upper()
        tconv = f["event_time"][1]
        if tconv.startswith("alias of"):
            tconv = cols[tconv[9:]]["convention"]
        aconv = f["amount"][1]
        if aconv.startswith("alias of"):
            aconv = cols[aconv[9:]]["convention"]
        rw = dict(sys=sysc, ref=f["record_ref"][0].strip(), acc_raw=f["account"][0], mer_raw=f["merchant"][0],
                  t=self._time(tconv, f["event_time"][0]), amt=self._amount(aconv, f["amount"][0], ccy), ccy=ccy,
                  code=f["status"][0].strip(), auth=f["auth_code"][0].strip().upper(), bin=f["bin"][0].strip(),
                  entry=f["entry_code"][0].strip(), ip=f.get("ip", ("", "", ""))[0], dev="", batch=f["batch"][0].strip(),
                  arn=f.get("arn", ("", "", ""))[0].strip())
        return rw

    def norm_sdk(self, name, o):
        if "ts_ms" in o:
            t = int(o["ts_ms"]) // 1000
        else:
            t = ts_of(o["ts"])
        ccy = o["currency"].strip().upper()
        if "amount_minor" in o:
            amt = int(o["amount_minor"])
        else:
            amt = major_to_minor(str(o["amount"]), self.exponent[ccy])
        dev = o.get("device_id")
        return dict(sys="SDK", ref=str(o["event_id"]).strip(), acc_raw=o["account"], mer_raw=o["merchant"], t=t, amt=amt, ccy=ccy,
                    code=str(o["status"]), auth=o["auth_code"].strip().upper(), bin="", entry=o.get("entry", ""),
                    ip=o.get("ip_ref") or "", dev=dev or "", batch=o["batch"], arn="")

    def norm_leg(self, name, rec):
        legacy = canon(rec["legacy_acct"], "legacy")
        acc = self.legacy.get(legacy) if legacy else None
        accc = self.canon_account(acc) if acc else None
        naive = naive_secs(rec["local_ts"], "%Y%m%d%H%M%S")
        t = None
        if accc and accc in self.acc:
            postal = self.account_attr(accc, "postal", naive)
            zone = self.postal_zone[postal[:4]]
            t = self.zones.local_to_utc(zone, naive)
        ccy = rec["currency"].strip().upper()
        return dict(sys="LEG", ref=rec["ref"], acc_raw=acc or "", acc_override=accc if accc else "INVALID", mer_raw=rec["merchant"],
                    t=t if t is not None else naive, amt=int(rec["amount_minor"].replace("+", "")), ccy=ccy,
                    code=rec["status"].strip(), auth=rec["auth"].strip().upper(), bin=rec["bin"].strip(), entry=rec["entry"].strip(),
                    ip="", dev="", batch=rec["batch"].strip(), arn="", t_unresolved=t is None)

    def norm_par(self, name, o):
        g = lambda tag: (o.find(tag).text or "") if o.find(tag) is not None else ""
        am = o.find("Amount")
        ccy = am.get("currency").strip().upper()
        amt = major_to_minor(am.text, self.exponent[ccy], eu=True) if am.get("unit") == "major" else int(am.text.strip())
        mer_raw = g("Merchant")
        mid = canon(mer_raw, "merchant")
        naive = naive_secs(g("PlacedAt"), "%Y-%m-%dT%H:%M:%S")
        t = None
        if mid:
            cm = self.canon_merchant(mid)
            if cm in self.mer_zone:
                t = self.zones.local_to_utc(self.mer_zone[cm], naive)
        return dict(sys="PAR", ref=o.get("ref").strip(), acc_raw=g("Customer"), mer_raw=mer_raw, t=t if t is not None else naive, amt=amt,
                    ccy=ccy, code=g("Status").strip(), auth=g("AuthCode").strip().upper(), bin=g("Bin").strip(), entry=g("Entry").strip(),
                    ip=g("Ip"), dev="", batch=o.get("batch"), arn="", t_unresolved=t is None)

    def norm_trm(self, name, r):
        rec = r["recorded_at"]
        t = int((rec - EPOCH).total_seconds()) + self.skew.get(ck(r["terminal_id"]), 0)
        return dict(sys="TRM", ref=str(r["trm_event_id"]).strip(), term=ck(r["terminal_id"]), acc_raw=r["account_id"], mer_raw=r["merchant_id"], t=t, amt=int(r["amount_minor"]),
                    ccy=r["currency"].strip().upper(), code=r["status_code"].strip(), auth=r["auth_code"].strip().upper(),
                    bin=r["card_bin"].strip(), entry=r["entry_mode_raw"].strip(), ip="", dev="", batch=r["batch_id"].strip(), arn="")

    # ------------------------------------------------------------------------------ labels
    def load_labels(self):
        # reason catalog, Orbis renumbering (crosswalk of the v4 document), merchant profiles
        self.reason = {(ck(r["network"]), ck(r["reason_code"])): r["class"].strip() for r in dicts(self.doc("reason_codes")[0]["Reason codes"])}
        v4 = self.by_source("label_policy.v4")
        self.orbis_legacy = {}
        if self.auth(v4, "crosswalk"):
            self.orbis_legacy = {ck(r["legacy_code"]): ck(r["current_code"]) for r in dicts(self.doc("label_policy.v4")[0]["Orbis reason code renumbering"])}
        v3t, v3p = self.doc("label_policy.v3")
        self.renumber_day = self.para("label_policy.v3", r"Renumbering day for this release: (\d{4}-\d\d-\d\d)").group(1)
        self.profile = {canon(r["merchant_id"], "merchant"): r["profile"].strip() for r in dicts(v3t["Merchant dispute-handling profiles"])}
        # ARN linkage
        con = self._sqlite(self.by_source("arn_crosswalk"))
        self.arn_link = {}
        for arn, system, ref, at in con.execute("SELECT arn, system, record_ref, linked_at FROM arn_links"):
            self.arn_link[arn.strip()] = (ck(system), ck(ref))
        for rw in self.rows:
            if rw.get("arn") and self.auth(rw["file"], "crosswalk"):
                self.arn_link.setdefault(rw["arn"], (rw["sys"], ck(rw["ref"])))
        import openpyxl
        trk = self.by_source("chargeback_tracker")
        self.arn_current = {}
        self.vantage_withdrawn = set()
        rows = self.wb(trk)["Disputes"]
        hdr = list(rows[0])
        for r in rows[1:]:
            d = dict(zip(hdr, r))
            if self.auth(trk, "crosswalk") and d["arn_current"] and d["arn_current"] != d["arn_original"]:
                self.arn_current[str(d["arn_current"]).strip()] = str(d["arn_original"]).strip()
            if self.auth(trk, "void_evidence") and d["network"] == "VANTAGE" and d["withdrawn_on"]:
                if date_ts(str(d["withdrawn_on"])[:10]) <= self.t_cutoff:
                    self.vantage_withdrawn.add(str(d["arn_original"]).strip())
        self.records_count[trk] = len(rows) - 1
        # chargeback rows -> disputes keyed by original ARN
        disputes = {}

        def add(network, did, arn, stage, day, reason):
            arn = arn.strip()
            arn = self.arn_current.get(arn, arn)
            d = disputes.setdefault((network, arn), dict(network=network, arn=arn, stages=[]))
            d["stages"].append((stage, day, reason.strip()))

        recs, _, _ = self.delim(self.by_source("chargebacks.kestrel"), ",", frozenset(self.conventions(self.by_source("chargebacks.kestrel"))))
        for r in recs:
            st = {"first_cb": "first_cb", "cb_reversal": "cb_reversal"}.get(r["stage"].strip(), "other")
            add("KESTREL", r["dispute_id"], r["arn"], st, r["stage_date"].strip(), r["reason_code"])
        recs, _, _ = self.delim(self.by_source("chargebacks.orbis"), "\t")
        for r in recs:
            st = {"1st CB": "first_cb", "CB Reversal": "cb_reversal"}.get(r["phase"].strip(), "other")
            dd = r["phase_date"].strip()
            day = f"{dd[6:10]}-{dd[3:5]}-{dd[0:2]}"
            code = r["reason"].strip()
            if st == "first_cb" and day < self.renumber_day:
                code = self.orbis_legacy.get(ck(code), "")
            add("ORBIS", r["case_no"], r["arn"], st, day, code)
        root = ET.fromstring(self.raw(self.by_source("chargebacks.vantage")))
        for dsp in root.iter("Dispute"):
            for s in dsp.iter("Stage"):
                st = {"FIRST": "first_cb", "REVERSAL": "cb_reversal"}.get(s.get("kind"), "other")
                add("VANTAGE", dsp.get("id"), dsp.get("arn"), st, s.get("date"), s.get("reason") or "")
        # notices
        latest = {}
        mb = self.by_source("dispute_notices")
        with tempfile.NamedTemporaryFile(suffix=".mbox", delete=False) as tmp:
            tmp.write(self.raw(mb))
            path = tmp.name
        nmsg = 0
        for msg in mailbox.mbox(path, factory=lambda f: BytesParser(policy=policy.default).parse(f)):
            nmsg += 1
            when = int(parsedate_to_datetime(msg["Date"]).timestamp())
            body = msg.get_body(preferencelist=("plain",)).get_content()
            m = re.search(r"ARN: (\d+)", body)
            a = re.search(r"Action: (\w+)", body)
            if not m or not a or a.group(1) not in ("WITHDRAWN", "REINSTATED") or when > self.t_cutoff:
                continue
            arn = self.arn_current.get(m.group(1), m.group(1))
            if arn not in latest or when >= latest[arn][0]:
                latest[arn] = (when, a.group(1))
        Path(path).unlink()
        self.records_count[mb] = nmsg
        withdrawn = {arn for arn, (w, act) in latest.items() if act == "WITHDRAWN"} | self.vantage_withdrawn
        self.fraud_cb = []  # (target (system, ref), first_cb day)
        for (net, arn), d in disputes.items():
            if arn in withdrawn or any(s[0] == "cb_reversal" and s[1] <= day_of(self.t_cutoff) for s in d["stages"]):
                continue
            firsts = sorted(s for s in d["stages"] if s[0] == "first_cb")
            if not firsts:
                continue
            st, day, code = firsts[0]
            tgt = self.arn_link.get(arn)
            if TRACE is not None and tgt:
                TRACE.setdefault("cb_codes", []).append((tgt, net, ck(code)))
            if self.reason.get((net, ck(code))) != "fraud":
                continue
            if tgt:
                self.fraud_cb.append((tgt, day))
        # analyst cases: primary + replica (decisions inside its label_evidence window)
        reverted = set()
        for line in text_lines(self.raw(self.by_source("cases.audit"))):
            kv = kv_line(line)
            if kv.get("action") == "DECISION_REVERTED" and ts_of(line.split(" ")[0]) <= self.t_cutoff:
                reverted.add(ck(kv["decision"]))
        self.decisions = []  # (target, decided_at, decision_id, code)
        for sid in ("cases.primary", "cases.r2"):
            name = self.by_source(sid)
            con = self._sqlite(name)
            cases = {ck(cid): (ck(sysc), ck(ref)) for cid, sysc, ref, _ in con.execute("SELECT case_id, event_system, event_ref, opened_at FROM cases")}
            for did, cid, code, at, an in con.execute("SELECT decision_id, case_id, decision, decided_at, analyst_id FROM decisions"):
                did, cid, code = ck(did), ck(cid), str(code).strip().lower()
                at = int(at) if isinstance(at, int) or str(at).strip().lstrip("-").isdigit() else ts_of(str(at))
                if sid == "cases.r2" and not self.auth(name, "label_evidence", at):
                    continue
                if did in reverted or at > self.t_cutoff:
                    continue
                self.decisions.append((cases[cid], at, did, code, cid))
        self.decisions = sorted(set(self.decisions))
        # vendor annotations
        tasks = {}
        root = ET.fromstring(self.raw(self.by_source("annotation_tasks")))
        for tk in root.iter("Task"):
            er = tk.find("EventRef")
            tasks[ck(tk.get("id"))] = ((ck(er.get("system")), ck(er.text)), ck(tk.get("batch")))
        bm = json.loads(self.raw(self.by_source("annotation_batches")))
        bstat = {ck(t["task_id"]): ((t["guideline_version"] or "").strip(), (t["batch_status"] or "").strip()) for t in bm["tasks"]}
        wb = self.wb(self.by_source("annotator_roster"))
        vend = {}
        for r in wb["Annotators"][1:]:
            vend[ck(r[0])] = str(r[1]).strip()
        tiers = {}
        for r in wb["TierHistory"][1:]:
            eff = excel_ts(r[2], epoch1904=True)
            tiers.setdefault(ck(r[0]), []).append((eff, str(r[1]).strip()))
        for v in tiers.values():
            v.sort()
        recs, _, _ = self.delim(self.by_source("label_taxonomy"), "\t")
        tax = {(r["vendor"].strip(), r["guideline_version"].strip(), ck(r["raw_label"])): r["class"].strip() for r in recs}
        gold = {(ck(r["annotator_id"]), ck(r["batch_id"])) for r in dicts(self.doc("annotation_guidelines")[0]["Gold check results"]) if r["result"].strip() == "fail"}
        rl = self.by_source("annotations.b.r2")
        xwalk, wd = {}, set()
        recs, _, _ = self.jsonl(rl)
        for o in recs:
            if "_crosswalk" in o and self.auth(rl, "crosswalk"):
                xwalk[ck(o["_crosswalk"]["old_annotator"])] = ck(o["_crosswalk"]["annotator"])
            elif o.get("status") == "withdrawn" and self.auth(rl, "void_evidence"):
                wd.add(ck(o["annotation_id"]))
        votes = {}
        for sid in ("annotations.a", "annotations.b"):
            recs, _, _ = self.jsonl(self.by_source(sid))
            for o in recs:
                if ck(o["annotation_id"]) in wd:
                    continue
                sub = o["submitted_at"]
                at = int(sub) // 1000 if isinstance(sub, int) else ts_of(sub)
                if at > self.t_cutoff:
                    continue
                tid = ck(o["task_id"])
                if tid not in tasks or tid not in bstat:
                    continue
                tgt, batch = tasks[tid]
                ver, status = bstat[tid]
                if status == "recalled" or not ver:
                    continue
                ann = xwalk.get(ck(o["annotator"]), ck(o["annotator"]))
                if (ann, batch) in gold or ann not in vend:
                    continue
                cls = tax.get((vend[ann], ver, str(o["label"]).strip().upper()))
                if cls not in ("fraud", "legit"):
                    continue
                tier = None
                for eff, tr in tiers.get(ann, ()):
                    if eff <= at:
                        tier = tr
                w = TIER_WEIGHT.get(tier, 0)
                if TRACE is not None:
                    TRACE.setdefault("vote_codes", []).append((tgt, tid, vend[ann], ver, ck(o["label"]), ann, batch))
                v = votes.setdefault((tgt, tid), [0, 0, 0])
                v[0 if cls == "fraud" else 1] += w
                v[2] += 1
        self.votes = votes

    def _sqlite(self, name):
        key = ("db", name)
        if key not in self.cache:
            self.cache[key] = self._sqlite_load(name)
        return self.cache[key]

    def _sqlite_load(self, name):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(self.raw(name))
            path = tmp.name
        con = sqlite3.connect(path)
        mem = sqlite3.connect(":memory:")
        con.backup(mem)
        con.close()
        Path(path).unlink()
        return mem

    # ------------------------------------------------------------------------------ point-in-time features
    def load_features(self):
        import openpyxl
        avail_t, avail_p = self.doc("availability_spec")
        self.lag_default = {"merchant_risk": int(self.para("availability_spec", r"merchant_risk (\d+) minutes").group(1)),
                            "ip_reputation": int(self.para("availability_spec", r"ip_reputation (\d+) minutes").group(1))}
        r2 = self.by_source("availability_spec.r2")
        self.rev2 = None
        m = self.para("availability_spec.r2", r"sets the ip_reputation lag to (\d+) minutes")
        s = self.para("availability_spec.r2", r"published at or after (\S+Z);")
        rev2_from = ts_of(s.group(1))
        if self.auth(r2, "rule_tables", rev2_from):
            self.rev2 = (rev2_from, int(m.group(1)))
        recs, _, _ = self.delim(self.by_source("lag_overrides"), ",", frozenset(self.conventions(self.by_source("lag_overrides"))))
        self.lag_ovr = {(r["source"].strip(), r["date"].strip(), int(r["hour"])): int(num(r["lag_minutes"].replace(",", ""))) for r in recs
                        if r["lag_minutes"].strip()}
        self.fs_out = {"merchant_risk": self.outage_windows("feature-store"), "ip_reputation": self.outage_windows("feature-store-ip")}
        # merchant risk publications
        cal = self.raw(self.by_source("publication_calendar")).decode("utf-8").replace("\r\n", "\n").split("\n")
        pub, cancelled, cur = {}, set(), {}
        for ln in cal:
            if ln == "BEGIN:VEVENT":
                cur = {}
            elif ln == "END:VEVENT":
                if cur.get("STATUS") == "CANCELLED":
                    cancelled.add(cur["UID"])
                else:
                    pub[cur["UID"]] = cur["T"]
            elif ln.startswith("UID:"):
                cur["UID"] = ck(ln[4:])
            elif ln.startswith("STATUS:"):
                cur["STATUS"] = ln[7:]
            elif ln.startswith("DTSTART"):
                head, val = ln.split(":", 1)
                if val.endswith("Z"):
                    cur["T"] = naive_secs(val[:-1], "%Y%m%dT%H%M%S")
                else:
                    zone = self.zone_alias.get(ck(head.split("TZID=")[1]), ck(head.split("TZID=")[1]))
                    cur["T"] = self.zones.local_to_utc(zone, naive_secs(val, "%Y%m%dT%H%M%S"))
        reg = json.loads(self.raw(self.by_source("snapshot_registry")))
        withdrawn = {ck(s["snapshot_id"]) for s in reg["snapshots"] if s["status"].strip() == "withdrawn"}
        v2 = self.by_source("merchant_risk.m4.r2")
        voids = set()
        if self.auth(v2, "void_evidence"):
            for r in self.wb(v2)["Snapshot"][1:]:
                if str(r[5]).strip() == "void":
                    voids.add((ck(r[0]), canon(r[1], "merchant")))
        self.mr = {}  # merchant -> list (as_of, available_ts, sid, value, corrections[(avail, value)])
        corr = {}
        snap_rows = []
        for k in range(1, 5):
            name = self.by_source(f"merchant_risk.m{k}")
            wb = self.wb(name)
            for r in wb["Snapshot"][1:]:
                snap_rows.append(r)
            for r in wb["Corrections"][1:]:
                corr.setdefault((ck(r[0]), canon(r[1], "merchant")), []).append((excel_ts(r[3]), int(r[2])))
        for sid_, mid, asof, bps, vol in snap_rows:
            mid = canon(mid, "merchant")
            sid_ = ck(sid_)
            if sid_ in cancelled or sid_ in withdrawn or (sid_, mid) in voids or sid_ not in pub:
                continue
            if isinstance(bps, str):
                continue
            if isinstance(asof, (int, float)):
                asof = day_of(excel_ts(asof))
            elif isinstance(asof, dt.datetime):
                asof = asof.date().isoformat()
            av = self.effective_pub("merchant_risk", pub[sid_])
            cs = [(self.effective_avail("merchant_risk", at), v) for at, v in corr.get((sid_, mid), [])]
            self.mr.setdefault(mid, []).append((str(asof)[:10], av, sid_, int(bps), sorted(cs)))
        # IP reputation
        sched = {ck(r["partition"]): ts_of(r["published_at"]) for r in dicts(avail_t["IP reputation partition schedule"])}
        fsm = self.by_source("feature_store_manifest")
        quarantined = set()
        if self.auth(fsm, "void_evidence"):
            for p in json.loads(self.raw(fsm))["partitions"]:
                if p["quarantined"]:
                    quarantined.add(ck(p["partition"]))
        recs, _, _ = self.delim(self.by_source("ip_reputation.corrections"), "\t")
        ipc = {ck(r["obs_id"]): (r["action"].strip(), r["new_score"].strip()) for r in recs}
        self.ip = {}
        for sid in ("ip_reputation.a", "ip_reputation.b"):
            recs, _, _ = self.jsonl(self.by_source(sid))
            for o in recs:
                part = ck(o["partition"])
                if part in quarantined or part not in sched:
                    continue
                score = o["score"]
                if o.get("score_scale") == "x10" and isinstance(score, str):
                    score = int(num(score) * 10)
                score = int(score)
                act = ipc.get(ck(o["obs_id"]))
                if act and act[0] == "void":
                    continue
                if act and act[0] == "rescore":
                    score = int(act[1])
                if score == -1:
                    continue
                obs = o["observed_at"]
                obs_t = int(obs) if isinstance(obs, int) else ts_of(obs)
                av = self.effective_pub("ip_reputation", sched[part])
                self.ip.setdefault(canon(o["ip"], "ip"), []).append((obs_t, ck(o["obs_id"]), av, score))
        # KYC
        wb = self.wb(self.by_source("kyc_reviews"))
        over = {}
        for r in wb["Appeals"][1:]:
            if str(r[1]).strip() == "overturned" and excel_ts(r[2]) <= self.t_cutoff:
                over[ck(r[0])] = True
        self.kyc = {}
        for r in wb["Reviews"][1:]:
            if int(r[2]) == 9 or ck(r[0]) in over:
                continue
            self.kyc.setdefault(canon(r[1], "account"), []).append((excel_ts(r[3]), r[0], int(r[2])))
        for v in self.kyc.values():
            v.sort()

    def lag(self, source, published):
        h = (published % DAY) // 3600
        key = (source, day_of(published), h)
        if key in self.lag_ovr:
            return self.lag_ovr[key]
        if source == "ip_reputation" and self.rev2 and published >= self.rev2[0]:
            return self.rev2[1]
        return self.lag_default[source]

    def effective_pub(self, source, t):
        for s, e in self.fs_out[source]:
            if s <= t < e:
                t = e
        return t + self.lag(source, t) * 60

    def effective_avail(self, source, t):
        return t + self.lag(source, t) * 60

    def mr_value(self, mid, t):
        best = None
        for asof, av, sid, val, cs in self.mr.get(mid, ()):
            if av > t:
                continue
            key = (asof, av, sid)
            if best is None or key > best[0]:
                v = val
                for cav, cv in cs:
                    if cav <= t:
                        v = cv
                best = (key, v)
        return None if best is None else best[1]

    def ip_value(self, ip, t):
        best = None
        for obs_t, oid, av, score in self.ip.get(ip, ()):
            if av > t:
                continue
            key = (obs_t, oid)
            if best is None or key > best[0]:
                best = (key, score)
        return None if best is None else best[1]

    def kyc_tier(self, aid, t):
        tier = None
        for eff, rid, tr in self.kyc.get(aid, ()):
            if eff <= t:
                tier = tr
        if tier is None:
            seg = self.account_attr(aid, "segment", t)
            reg = self.region.get(ck(self.account_attr(aid, "postal", t)))
            tier = self.kyc_default.get((ck(seg), ck(reg)))
        return tier

    # ------------------------------------------------------------------------------ lineage controls
    def count_records(self, name, scope):
        key = ("cnt", name, scope)
        if key not in self.cache:
            self.cache[key] = self._count(name, scope)
        return self.cache[key]

    def _count(self, name, scope):
        fmt = name.rsplit(".", 1)[1]
        data = self.raw(name)
        if fmt in ("csv", "tsv"):
            return len(self.delim(name, "," if fmt == "csv" else "\t", frozenset(self.conventions(name)))[0])
        if fmt == "jsonl":
            return len(self.jsonl(name)[0])
        if fmt == "txt":
            return sum(1 for ln in decode_lines(data) if ln[:1] == "D")
        if fmt == "xml":
            root = ET.fromstring(data)
            tag = {"Orders": "Order", "Disputes": "Stage", "Tasks": "Task", "Fixings": "Fixing"}[root.tag]
            return sum(1 for _ in root.iter(tag))
        if fmt == "parquet":
            import pyarrow.parquet as pq
            return pq.read_metadata(io.BytesIO(data)).num_rows
        if fmt == "xlsx":
            rows = self.wb(name)[scope][1:]
            return sum(1 for r in rows if any(c not in (None, "") for c in r))
        if fmt == "json":
            o = json.loads(data)
            return len(next(v for v in o.values() if isinstance(v, list)))
        if fmt == "db":
            return self._sqlite(name).execute(f'SELECT COUNT(*) FROM "{scope}"').fetchone()[0]
        if fmt == "yaml":
            import yaml
            o = yaml.safe_load(data)
            return len(next(v for v in o.values() if isinstance(v, list)))
        if fmt == "toml":
            o = tomllib.loads(data.decode("utf-8-sig"))
            return len(o[scope])
        if fmt == "ini":
            ini = configparser.ConfigParser(interpolation=None)
            ini.read_string(data.decode("utf-8-sig"))
            return len(ini.sections())
        if fmt == "log":
            return len(text_lines(data))
        if fmt == "mbox":
            with tempfile.NamedTemporaryFile(suffix=".mbox", delete=False) as tmp:
                tmp.write(data)
                path = tmp.name
            n = len(mailbox.mbox(path))
            Path(path).unlink()
            return n
        if fmt == "ics":
            return data.decode("utf-8").count("BEGIN:VEVENT")
        if fmt in ("md", "html", "docx", "pdf"):
            tables = self.cache.get(name) or doc_tables(name, data)
            self.cache[name] = tables
            return len(tables[0][scope][1]) if scope in tables[0] else -1
        raise ValueError(name)

    def reconcile(self):
        con = self._sqlite(self.by_source("lineage_controls"))
        rows = con.execute("SELECT source_file, scope, partition, row_count, hash_total, delivered_with FROM controls").fetchall()
        part = {}
        for rw in self.rows:
            p = part.setdefault(rw["file"], {})
            h = (rw["t"] % DAY) // 3600 // 3 * 3
            k = f"{day_of(rw['t'])}T{h:02d}"
            c = p.setdefault(k, [0, 0])
            c[0] += 1
            c[1] += rw["amt"]
        self.controls_ok = {c["file"]: True for c in self.catalog}
        expected = {}
        counts = {}
        for src, scope, partition, cnt, hsum, via in rows:
            if via:
                if not self.auth(via, "controls") or via not in self.controls_seen:
                    self.controls_ok[src] = False
                    continue
                for p_, c_, h_ in self.controls_seen[via]:
                    expected.setdefault(src, {})[p_] = (c_, h_)
            elif scope == "event_rows":
                expected.setdefault(src, {})[partition] = (cnt, hsum)
            else:
                key = (src, scope)
                counts[key] = cnt
        for src, exp in expected.items():
            got = {k: tuple(v) for k, v in part.get(src, {}).items()}
            if got != exp:
                self.controls_ok[src] = False
        for (src, scope), cnt in counts.items():
            try:
                if self.count_records(src, scope) != cnt:
                    self.controls_ok[src] = False
            except Missing:
                self.controls_ok[src] = False
        for c in self.catalog:
            if c["role"] == "events" and c["file"] not in expected:
                self.controls_ok[c["file"]] = False
        bad = [f for f, ok in self.controls_ok.items() if not ok]
        self.problems += [f"controls {b}" for b in bad]

    # ------------------------------------------------------------------------------ build
    def build(self):
        self.apply_errata()
        spec_t = self.doc("build_spec")[0]
        exceptions = {(r["file"].strip(), ck(r["record_ref"])) for r in dicts(spec_t["Split-tender exceptions"])}
        replay = {ck(r["batch_id"]) for r in dicts(self.doc("dedup_runbook")[0]["Replay batch register"]) if r["kind"].strip() == "replay"}
        self.batch_eff = {}
        for line in text_lines(self.raw(self.by_source("ingestion_audit"))):
            kv = kv_line(line)
            if kv.get("status") == "ok":
                self.batch_eff[ck(kv["batch"])] = ts_of(line.split(" ")[0])
        retracted = {tuple(ck(x) for x in r["event_ref"].split(":", 1)) for r in dicts(self.doc("prior_release_notes")[0]["Retracted examples"])}
        self.excl = []  # (file, ref, reason)
        cand = [rw for rw in self.rows if self.auth(rw["file"], "event_rows", rw["t"])]
        self.candidates_per_file = {}
        for rw in cand:
            self.candidates_per_file[rw["file"]] = self.candidates_per_file.get(rw["file"], 0) + 1
        groups = {}
        for rw in cand:
            acc = rw.get("acc_override")
            if acc is None:
                a = canon(rw["acc_raw"], "account")
                acc = self.canon_account(a) if a else None
            elif acc == "INVALID":
                acc = None
            mer = canon(rw["mer_raw"], "merchant")
            if mer is None and rw["sys"] == "GW":
                mer = self.resolve_alias(rw["mer_raw"], rw["t"])
            mer = self.canon_merchant(mer) if mer else None
            if (acc is None or acc not in self.acc or mer is None or mer not in self.mer or rw.get("t_unresolved")
                    or not self.optional_ids_valid(rw)):
                self.excl.append((rw["file"], rw["ref"], "invalid_key"))
                continue
            if ck(rw["batch"]) in replay:
                self.excl.append((rw["file"], rw["ref"], "replay"))
                continue
            if rw.get("voided"):
                self.excl.append((rw["file"], rw["ref"], "voided"))
                continue
            rw["acc"], rw["mer"] = acc, mer
            fp = f"{acc}|{mer}|{rw['amt']}|{rw['ccy']}|{rw['t']}|{rw['auth']}"
            if (rw["file"], ck(rw["ref"])) in exceptions:
                fp += f"|{rw['ref']}"
            groups.setdefault(fp, []).append(rw)
        self.member_of = {}
        keepers = []
        for fp, members in groups.items():
            members.sort(key=lambda x: (PRECEDENCE.index(x["sys"]), self.batch_eff.get(ck(x["batch"]), 1 << 62), x["ref"]))
            k = members[0]
            k["fp"] = fp
            k["members"] = members
            for m in members[1:]:
                self.excl.append((m["file"], m["ref"], "duplicate"))
            for m in members:
                self.member_of[(m["sys"], ck(m["ref"]))] = k
            for fld in ("bin", "ip", "dev"):
                for m in members:
                    v = m[fld]
                    v = "" if v is None else str(v)
                    if fld == "ip" and v.strip(WS).upper() in NO_IP:
                        v = ""
                    if fld == "dev" and v.strip(WS).upper() in NO_DEVICE:
                        v = ""
                    if v:
                        k["f_" + fld] = v
                        break
            for m in members:
                if m["entry"] and m["entry"].strip() != "????":
                    k["f_entry"] = (m["sys"], ck(m["entry"]))
                    break
            k["meaning"] = self.status.get((k["sys"], ck(k["code"])), "unknown")
            k["example_id"] = "EX-" + hashlib.sha256(fp.encode("utf-8")).hexdigest()[:16]
            keepers.append(k)
        self.keepers = keepers
        # kept events (velocity context)
        self.kept = {}
        for k in keepers:
            if k["meaning"] in ("approved", "settled"):
                k["usd"] = self.usd_cents(k["amt"], k["ccy"], k["t"])
                self.kept.setdefault(k["acc"], []).append((k["t"], k["usd"]))
        for v in self.kept.values():
            v.sort()
        self.kept_t = {a: [x[0] for x in v] for a, v in self.kept.items()}
        self.kept_cum = {}
        for a, v in self.kept.items():
            cum = [0]
            for _, u in v:
                cum.append(cum[-1] + u)
            self.kept_cum[a] = cum
        # evidence indexes
        ev_cb, ev_dec, ev_votes = {}, {}, {}
        for tgt, day in self.fraud_cb:
            k = self.member_of.get(tgt)
            if k:
                ev_cb.setdefault(k["example_id"], []).append(day)
        per_case = {}
        for tgt, at, did, code, cid in self.decisions:
            per_case.setdefault((tgt, cid), []).append((at, did, code))
        for (tgt, case), decs in per_case.items():
            at, did, code = max(decs)
            if code == "inconclusive":
                continue
            k = self.member_of.get(tgt)
            if k:
                cur = ev_dec.get(k["example_id"])
                if cur is None or (at, did) > cur[:2]:
                    ev_dec[k["example_id"]] = (at, did, code)
        for (tgt, task), v in self.votes.items():
            k = self.member_of.get(tgt)
            if k and v[2]:
                e = ev_votes.setdefault(k["example_id"], [0, 0, 0])
                for i in range(3):
                    e[i] += v[i]
        prior_ids = set(self.prior["released_example_ids"]) if self.mode == "delta" else set()
        released = []
        for k in keepers:
            reason = STATUS_REASON.get(k["meaning"])
            if reason is None and k["meaning"] not in ("approved", "settled"):
                reason = "declined"
            if reason is None and k["example_id"] in prior_ids:
                reason = "already_released"
            if reason is None and k["t"] < self.t_start:
                reason = "lookback_context"
            if reason is None and k["t"] >= self.t_end:
                reason = "outside_window"
            if reason is None and k["acc"] in self.withdrawn:
                reason = "consent_withdrawn"
            if reason is None and any((m["sys"], ck(m["ref"])) in retracted for m in k["members"]):
                reason = "retracted"
            if reason is None:
                reason = self.label(k, ev_dec.get(k["example_id"]), ev_cb.get(k["example_id"]), ev_votes.get(k["example_id"]))
            if reason:
                self.excl.append((k["file"], k["ref"], reason))
            else:
                released.append(k)
        self.released = released
        self.splits()
        self.features()
        self.fit_and_score()

    @staticmethod
    def optional_ids_valid(rw):
        """Device and IP references are identifiers too: a value that is no sentinel and fails its pattern is invalid."""
        for fld, kind, sentinels in (("dev", "device", NO_DEVICE), ("ip", "ip", NO_IP)):
            v = rw.get(fld)
            v = "" if v is None else str(v)
            if v.strip(WS).upper() not in sentinels and canon(v, kind) is None:
                return False
        return True

    def apply_errata(self):
        tables = self.doc("errata")[0]
        cons = self.by_source("errata.r2")
        withdrawn = set()
        if self.auth(cons, "void_evidence"):
            withdrawn = {ck(r["erratum_id"]) for r in dicts(self.doc("errata.r2")[0]["Withdrawn errata"])}
        best = {}
        for r in dicts(tables["Errata register"]):
            if ck(r["erratum_id"]) in withdrawn or r["field"].strip() == "remark":
                continue
            key = (r["file"].strip(), ck(r["record_ref"]), r["field"].strip())
            at = ts_of(r["issued_at"])
            if key not in best or (at, r["erratum_id"]) > best[key][:2]:
                best[key] = (at, r["erratum_id"], r["new_value"])
        idx = {(rw["file"], ck(rw["ref"])): rw for rw in self.rows}
        for (file, ref, field), (_, _, val) in best.items():
            rw = idx.get((file, ref))
            if rw is None:
                continue
            if field == "amount_minor":
                rw["amt"] = int(val)
            elif field == "event_time":
                rw["t"] = ts_of(val)
            elif field == "merchant_id":
                rw["mer_raw"] = val
            elif field == "void":
                rw["voided"] = True

    def label(self, k, dec, cbs, votes):
        mature = k["t"] + self.maturity * DAY <= self.t_cutoff
        if dec:
            if dec[2] == "confirmed_fraud":
                k["label"], k["label_source"] = 1, "analyst"
                return None
            if dec[2] == "confirmed_legit":
                if not mature:
                    return "immature_label"
                k["label"], k["label_source"] = 0, "analyst"
                return None
        if not mature:
            return "immature_label"
        d_ev = day_of(k["t"])
        limit = day_of(date_ts(d_ev) + self.maturity * DAY)
        if cbs and self.profile.get(k["mer"]) != "friendly_fraud_prone":
            if any(d_ev <= d < limit for d in cbs):
                k["label"], k["label_source"] = 1, "chargeback"
                return None
        if votes:
            if votes[0] > votes[1]:
                k["label"], k["label_source"] = 1, "vendor"
                return None
            if votes[1] > votes[0]:
                k["label"], k["label_source"] = 0, "vendor"
                return None
            return "unresolved_label"
        k["label"], k["label_source"] = 0, "no_chargeback"
        return None

    # ------------------------------------------------------------------------------ clusters and splits
    def splits(self):
        import pyarrow.parquet as pq
        import yaml
        est, ends = {}, {}
        for line in text_lines(self.raw(self.by_source("device_links.log"))):
            kv = kv_line(line)
            at = ts_of(line.split(" ")[0])
            key = (self.canon_account(canon(kv["account"], "account")), canon(kv["device"], "device"))
            if " LINK " in line:
                est[key] = min(est.get(key, at), at)
            elif " UNLINK " in line:
                ends.setdefault(key, []).append(at)
        for r in pq.read_table(io.BytesIO(self.raw(self.by_source("device_links.fingerprints")))).to_pylist():
            at = int(r["first_seen"].replace(tzinfo=UTC).timestamp())
            key = (self.canon_account(canon(r["account_id"], "account")), canon(r["device_id"], "device"))
            est[key] = min(est.get(key, at), at)
        recs, _, _ = self.delim(self.by_source("device_link_revocations"), ",", frozenset(self.conventions(self.by_source("device_link_revocations"))))
        last = {}
        for r in recs:
            at = ts_of(r["at"])
            if at > self.t_cutoff:
                continue
            key = (self.canon_account(canon(r["account_id"], "account")), canon(r["device_id"], "device"))
            if key not in last or at >= last[key][0]:
                last[key] = (at, r["action"].strip())
        reg = yaml.safe_load(self.raw(self.by_source("device_registry")))
        exempt = {canon(d["device_id"], "device") for d in reg["devices"] if d["kind"] == "kiosk"}
        exempt |= {canon(r["device_id"], "device") for r in dicts(self.doc("split_policy")[0]["Shared-device exemptions"])}
        parent = {}

        def find(x):
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                if rb < ra:
                    ra, rb = rb, ra
                parent[rb] = ra

        by_dev = {}
        for (acc, dev), at in est.items():
            if at > self.t_cutoff or dev in exempt or acc is None:
                continue
            if any(at < u <= self.t_cutoff for u in ends.get((acc, dev), ())):
                continue
            if last.get((acc, dev), (0, ""))[1] == "revoke":
                continue
            by_dev.setdefault(dev, []).append(acc)
        for dev, accs in by_dev.items():
            for a in accs[1:]:
                union(accs[0], a)
        comp = {}
        for x in list(parent):
            comp.setdefault(find(x), []).append(x)
        cid = {}
        for root, members in comp.items():
            m = min(members)
            for x in members:
                cid[x] = m
        for k in self.released:
            k["cluster"] = cid.get(k["acc"], k["acc"])
        pins = {}
        for p in self.pins:
            if p["status"] != "active":
                continue
            sysc, ref = p["event_ref"].split(":", 1)
            k = self.member_of.get((ck(sysc), ck(ref)))
            if k is not None and k in self.released_set():
                pins.setdefault(k["cluster"], set()).add(p["split"])
        prior = self.prior.get("account_splits", {}) if self.mode == "delta" else {}
        members_of_cluster = {}
        for acc, c in cid.items():
            members_of_cluster.setdefault(c, set()).add(acc)
        salt = self.cfg["split_salt"]
        lo, hi = int(self.cfg["split_train_below"]), int(self.cfg["split_val_below"])
        self.cluster_split = {}
        order = {"test": 0, "val": 1, "train": 2}
        for k in self.released:
            c = k["cluster"]
            if c in self.cluster_split:
                continue
            mem = members_of_cluster.get(c, {c})
            prs = [prior[a] for a in mem if a in prior]
            if prs:
                sp = min(prs, key=lambda s: order[s])
            elif c in pins:
                sp = "test" if "test" in pins[c] else "val"
            else:
                b = int(hashlib.sha256(f"{salt}:{c}".encode("utf-8")).hexdigest()[:8], 16) % 100
                sp = "train" if b < lo else "val" if b < hi else "test"
            self.cluster_split[c] = sp
        for k in self.released:
            k["split"] = "oot" if k["t"] >= self.t_oot else self.cluster_split[k["cluster"]]

    def released_set(self):
        if not hasattr(self, "_rs"):
            self._rs = {id(k) for k in self.released}
        return _IdSet(self._rs)

    # ------------------------------------------------------------------------------ features
    def features(self):
        std = self.doc("preprocessing_standard")[0]
        rg = {ck(r["mcc_subcode"]): r["risk_group"].strip() for r in dicts(std["MCC sub-code risk groups"])}
        for k in self.released:
            t, a = k["t"], k["acc"]
            ts_, cum = self.kept_t.get(a, []), self.kept_cum.get(a, [0])
            i1 = bisect.bisect_left(ts_, t - DAY)
            i2 = bisect.bisect_left(ts_, t)
            i7 = bisect.bisect_left(ts_, t - 7 * DAY)
            ip = canon(k.get("f_ip"), "ip") if k.get("f_ip") else None
            f = {
                "amount_usd_cents": k["usd"],
                "account_age_days": (t - self.acc[a]["created"]) // DAY,
                "txn_count_24h": i2 - i1,
                "amount_sum_7d_usd_cents": cum[i2] - cum[i7],
                "merchant_cb_rate_bps": self.mr_value(k["mer"], t),
                "ip_risk_score": self.ip_value(ip, t) if ip else None,
                "kyc_tier": self.kyc_tier(a, t),
            }
            k["raw"] = f
            e = k.get("f_entry")
            k["cat"] = {"entry_mode": self.entry.get(e, "UNKNOWN") if e else "UNKNOWN",
                        "mcc_risk_group": rg.get(self.mcc_at(k["mer"], t), "UNMAPPED"),
                        "issuer_group": self.issuer(k.get("f_bin", ""))}

    def issuer(self, b):
        b = (b or "").strip()
        for ln in range(len(b), 3, -1):
            g = self.bins.get(b[:ln])
            if g:
                return g
        return "UNMAPPED"

    def fit_and_score(self):
        train = [k for k in self.released if k["split"] == "train"]
        if self.mode == "delta":
            st = self.prior
            self.stats = {f: {x: Fraction(Decimal(v)) for x, v in st["features"][f].items()} for f in NUMERIC}
            self.vocab = st["vocab"]
            self.cw = {c: Fraction(Decimal(v)) for c, v in st["class_weights"].items()}
            self.psi_edges = {f: [Fraction(Decimal(x)) for x in st["psi_edges"][f]] for f in NUMERIC}
            self.psi_train = {f: [Fraction(Decimal(x)) for x in st["psi_train_props"][f]] for f in NUMERIC}
        else:
            self.stats = {}
            for f in NUMERIC:
                vals = sorted(k["raw"][f] for k in train if k["raw"][f] is not None)
                p01, p99 = nr(vals, Fraction(1, 100)), nr(vals, Fraction(99, 100))
                cl = sorted(min(max(v, p01), p99) for v in vals)
                self.stats[f] = {"p01": Fraction(p01), "p99": Fraction(p99), "median": Fraction(nr(cl, Fraction(1, 2))),
                                 "q1": Fraction(nr(cl, Fraction(1, 4))), "q3": Fraction(nr(cl, Fraction(3, 4)))}
            mv = int(self.cfg["min_vocab_count"])
            self.vocab = {}
            for c in CATEGORICAL:
                cnt = {}
                for k in train:
                    cnt[k["cat"][c]] = cnt.get(k["cat"][c], 0) + 1
                toks = sorted((t for t, n in cnt.items() if n >= mv), key=lambda t: (-cnt[t], t))
                self.vocab[c] = ["~RARE~"] + toks
            beta = Fraction(Decimal(self.cfg["class_weight_beta"]))
            n = {0: sum(1 for k in train if k["label"] == 0), 1: sum(1 for k in train if k["label"] == 1)}
            inv = {c: (1 - beta) / (1 - beta ** n[c]) for c in (0, 1)}
            tot = inv[0] + inv[1]
            self.cw = {str(c): Fraction(Decimal(fixed6(inv[c] * 2 / tot))) for c in (0, 1)}
        self.imputed = {f: 0 for f in NUMERIC}
        for k in self.released:
            sc = {}
            for f in NUMERIC:
                s = self.stats[f]
                v = k["raw"][f]
                if v is None:
                    self.imputed[f] += 1
                    x = s["median"]
                else:
                    x = min(max(Fraction(v), s["p01"]), s["p99"])
                iqr = s["q3"] - s["q1"]
                sc[f] = fixed6((x - s["median"]) / iqr if iqr != 0 else (x - s["median"]))
            k["scaled"] = sc
            k["idx"] = {c: (self.vocab[c].index(k["cat"][c]) if k["cat"][c] in self.vocab[c][1:] else 0) for c in CATEGORICAL}
            k["sw"] = fixed6(self.cw[str(k["label"])]) if k["split"] == "train" else "1.000000"
        sc_t = self.doc("scorer_card")[0]
        coef = {r["term"].strip(): num(r["coefficient"]) for r in dicts(sc_t["Coefficients"])}
        off = {canon(r["merchant_id"], "merchant"): num(r["offset"]) for r in dicts(sc_t["Merchant offsets"])}
        for k in self.released:
            s = coef["intercept"] + sum(coef[f] * Fraction(Decimal(k["scaled"][f])) for f in NUMERIC) + off.get(k["mer"], 0)
            k["score"] = fixed6(s)
        if self.mode != "delta":
            self.psi_edges, self.psi_train = {}, {}
            for f in NUMERIC:
                vals = sorted(Fraction(Decimal(k["scaled"][f])) for k in train)
                self.psi_edges[f] = [Fraction(nr(vals, Fraction(i, 10))) for i in range(1, 10)]
                self.psi_train[f] = props([Fraction(Decimal(k["scaled"][f])) for k in train], self.psi_edges[f])
        oot = [k for k in self.released if k["split"] == "oot"]
        self.psi = {}
        getcontext().prec = 40
        for f in NUMERIC:
            a = props([Fraction(Decimal(k["scaled"][f])) for k in oot], self.psi_edges[f])
            e = self.psi_train[f]
            tot = Decimal(0)
            for ai, ei in zip(a, e):
                da = Decimal(ai.numerator) / Decimal(ai.denominator)
                de = Decimal(ei.numerator) / Decimal(ei.denominator)
                tot += (da - de) * (da / de).ln()
            self.psi[f] = fixed6(Fraction(tot))
        self.auc = {sp: auc_of([k for k in self.released if k["split"] == sp]) for sp in ("val", "test", "oot")}

    # ------------------------------------------------------------------------------ outputs
    def write_held(self):
        self.out.mkdir(parents=True, exist_ok=True)
        rid = getattr(self, "release_id", None)
        if rid is None:
            try:
                rid = tomllib.loads(self.raw(self.by_source("release_config")).decode("utf-8-sig"))["release"]["release_id"]
            except Exception:  # noqa: BLE001 - a missing or broken config leaves the id unknown
                rid = None
        head = {"release_id": rid, "status": "HELD"}
        (self.out / "normalized.jsonl").write_text("", encoding="utf-8")
        for n in ["summary.json", "product_summary.json"] + [f"region_{g}.json" for g in REGION_GROUPS] + \
                [f"segment_{g}.json" for g in SEGMENT_GROUPS]:
            dump(self.out / n, head)
        srcs = [{"file": c["file"], "present": (self.data / c["file"]).is_file()} for c in getattr(self, "catalog", [])]
        dump(self.out / "data_quality.json", {**head, "sources": srcs, "exclusions": []})
        if TRACE is not None:
            TRACE["problems"] = list(self.problems)

    def slice_report(self, kind, group, rel):
        ks = [k for k in rel if k[kind] == group]
        counts = {sp: {"n": sum(1 for k in ks if k["split"] == sp), "positives": sum(1 for k in ks if k["split"] == sp and k["label"] == 1)}
                  for sp in SPLITS}
        return {"release_id": self.release_id, "status": "PUBLISHED", "slice": f"{kind}:{group}", "counts": counts,
                "auc": {sp: auc_of([k for k in ks if k["split"] == sp]) for sp in ("val", "test", "oot")}}

    def write_published(self):
        out = self.out
        out.mkdir(parents=True, exist_ok=True)
        rel = sorted(self.released, key=lambda k: (k["t"], k["example_id"]))
        for k in rel:
            k["region_group"] = self.region_group.get(ck(self.region.get(ck(self.account_attr(k["acc"], "postal", k["t"])))), "")
            k["segment_group"] = self.segment_group.get(ck(self.account_attr(k["acc"], "segment", k["t"])), "")
        lines = [jline({"example_id": k["example_id"], "event_ref": f"{k['sys']}:{k['ref']}", "account_id": k["acc"],
                        "cluster_id": k["cluster"], "split": k["split"], "event_time": iso(k["t"]), "label": k["label"],
                        "label_source": k["label_source"], "sample_weight": k["sw"], "features": k["scaled"],
                        "categorical": k["idx"], "score": k["score"]}) for k in rel]
        (out / "normalized.jsonl").write_text("".join(lines), encoding="utf-8")
        accs = sorted({k["acc"]: k["cluster"] for k in rel}.items())
        clusters = [{"account_id": a, "cluster_id": c, "split": self.cluster_split[c]} for a, c in accs]
        state = {"release_id": self.release_id, "status": "PUBLISHED", "parameters": self.cfg,
                 "features": {f: {x: fixed6(v) for x, v in self.stats[f].items()} for f in NUMERIC},
                 "vocab": self.vocab, "class_weights": {c: fixed6(v) for c, v in self.cw.items()},
                 "psi_edges": {f: [fixed6(x) for x in self.psi_edges[f]] for f in NUMERIC},
                 "psi_train_props": {f: [fixed6(x) for x in self.psi_train[f]] for f in NUMERIC},
                 "clusters": clusters, "released_example_ids": sorted(k["example_id"] for k in rel)}
        dump(out / "product_summary.json", state)
        counts = {sp: {"n": sum(1 for k in rel if k["split"] == sp), "positives": sum(1 for k in rel if k["split"] == sp and k["label"] == 1)}
                  for sp in SPLITS}
        dump(out / "summary.json", {"release_id": self.release_id, "status": "PUBLISHED", "counts": counts, "auc": self.auc,
                                    "psi": self.psi, "imputed": self.imputed})
        for g in REGION_GROUPS:
            dump(out / f"region_{g}.json", self.slice_report("region_group", g, rel))
        for g in SEGMENT_GROUPS:
            dump(out / f"segment_{g}.json", self.slice_report("segment_group", g, rel))
        rel_per = {}
        for k in rel:
            rel_per[k["file"]] = rel_per.get(k["file"], 0) + 1
        srcs = []
        for c in self.catalog:
            name = c["file"]
            srcs.append({"file": name, "records": self.records(name), "controls_ok": self.controls_ok[name],
                         "candidates": self.candidates_per_file.get(name, 0), "released": rel_per.get(name, 0)})
        ex = sorted(self.excl, key=lambda x: (x[0], x[1]))
        dump(out / "data_quality.json", {"release_id": self.release_id, "status": "PUBLISHED", "sources": srcs,
                                         "exclusions": [{"file": f, "record_ref": r, "reason": why} for f, r, why in ex]})
        if TRACE is not None:
            TRACE["release"] = self

    def records(self, name):
        if name in self.records_count:
            return self.records_count[name]
        con = None
        fmt = name.rsplit(".", 1)[1]
        if fmt in ("xlsx", "db") or fmt in ("md", "html", "docx", "pdf"):
            if fmt == "xlsx":
                return sum(self.count_records(name, s) for s in self.wb(name))
            if fmt == "db":
                con = self._sqlite(name)
                return sum(self.count_records(name, t) for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = self.cache.get(name) or doc_tables(name, self.raw(name))
            return sum(len(v[1]) for v in tables[0].values())
        if fmt == "toml":
            o = tomllib.loads(self.raw(name).decode("utf-8-sig"))
            return sum(len(v) for v in o.values() if isinstance(v, list))
        return self.count_records(name, None)


class _IdSet:
    def __init__(self, ids):
        self.ids = ids

    def __contains__(self, k):
        return id(k) in self.ids


def auc_of(ks):
    """Mann-Whitney AUC on the 6-decimal scores, ties count one half; None without both classes."""
    pos = sorted(Fraction(Decimal(k["score"])) for k in ks if k["label"] == 1)
    neg = sorted(Fraction(Decimal(k["score"])) for k in ks if k["label"] == 0)
    if not pos or not neg:
        return None
    tot = Fraction(0)
    for p in pos:
        lo = bisect.bisect_left(neg, p)
        hi = bisect.bisect_right(neg, p)
        tot += lo + Fraction(hi - lo, 2)
    return fixed6(tot / (len(pos) * len(neg)))


def nr(vals, p: Fraction):
    """Nearest-rank quantile v[ceil(p * n)] (1-based)."""
    n = len(vals)
    if n == 0:
        return 0
    k = math.ceil(p * n)
    return vals[max(1, k) - 1]


def props(vals, edges):
    cnt = [0] * 10
    for v in vals:
        cnt[sum(1 for e in edges if v > e)] += 1
    n = len(vals)
    floor = Fraction(1, 10000)
    return [max(Fraction(c, n) if n else Fraction(0), floor) for c in cnt]


def jline(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":")) + "\n"


def dump(path, o):
    path.write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv):
    args = [a for a in argv if not a.startswith("--prior")]
    prior = None
    if "--prior" in argv:
        i = argv.index("--prior")
        prior = Path(argv[i + 1])
        args = [a for j, a in enumerate(argv) if j not in (i, i + 1)]
    data = Path(args[0]) if len(args) > 0 else Path("/app/data")
    out = Path(args[1]) if len(args) > 1 else Path("/app/out")
    Release(data, out, prior).run()


if __name__ == "__main__":
    main(sys.argv[1:])
