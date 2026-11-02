#!/usr/bin/env python3
"""Certify the Heron Q3 2025 evaluation close.

Usage: python3 certify.py <data_dir> <out_dir>

Reads every shipped source, applies the written authority, convention and precedence
rules, and writes the thirteen certified outputs into <out_dir>.
"""
import calendar
import csv
import io
import json
import math
import os
import re
import sqlite3
import sys
import tomllib
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import zlib
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from html.parser import HTMLParser

import pyarrow.parquet as pq
import yaml

D0 = Decimal(0)


PDF_STREAM_RE = r"stream\n(.*?)\nendstream"

def ts_utc(y, mo, d, h=0, mi=0, s=0):
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))


def iso_z(t):
    import time as _t
    return _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime(t))


def iso_week_of(t):
    import datetime as _d
    return _d.datetime.fromtimestamp(t, _d.timezone.utc).isocalendar()[1]


def q6(x):
    if isinstance(x, Fraction):
        d = Decimal(x.numerator) / Decimal(x.denominator)
    else:
        d = Decimal(x)
    return float(d.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))


def round_half_even(text, places):
    return Decimal(text).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)


class Ctx:
    pass


C = Ctx()


# ---------------------------------------------------------------------------------
# identifiers
# ---------------------------------------------------------------------------------
def load_confusables(policy_text):
    m = re.search(r"the confusables are (.+?)\.\s*$", policy_text, re.M)
    table = {}
    for a, b in re.findall(r"(\S) for (\S)", m.group(1)):
        table[a] = b
    return table


def clean(s):
    s = unicodedata.normalize("NFKC", str(s))
    s = "".join(C.conf.get(ch, ch) for ch in s)
    return s.strip().strip("\u00a0").strip()


def cid_job(s):
    s = clean(s)
    m = re.fullmatch(r"[Jj](\d{1,7})", s)
    return f"J{int(m.group(1)):07d}" if m else None


def cid_item(s):
    s = clean(s).rstrip("*")
    m = re.fullmatch(r"([A-Za-z]{3})-(\d{1,5})", s)
    return f"{m.group(1).upper()}-{int(m.group(2)):05d}" if m else None


def cid_host(s):
    s = clean(s)
    m = re.fullmatch(r"[Nn][Oo][Dd][Ee]-(\d{1,4})", s)
    return f"node-{int(m.group(1)):04d}" if m else None


def cid_ckpt(s):
    s = clean(s)
    if s.lower().startswith("ema/"):
        s = clean(s[4:])
    m = re.fullmatch(r"[Cc][Kk]-([0-9A-Fa-f]{1,10})", s)
    return "ck-" + m.group(1).lower().zfill(10) if m else None


def cid_ticket(s, pfx):
    s = clean(s)
    m = re.fullmatch(pfx + r"-(\d{1,5})", s, re.I)
    return f"{pfx}-{int(m.group(1)):05d}" if m else None


def cid_rid(s):
    s = clean(s)
    m = re.fullmatch(r"[Rr](\d{1,7})", s)
    return f"r{int(m.group(1)):07d}" if m else None


def cid_lc(s):
    s = clean(s).replace(" ", "")
    m = re.fullmatch(r"[Ll][Cc](\d{1,6})", s)
    return f"LC{int(m.group(1)):06d}" if m else None


def rev_int(v):
    s = clean(v)
    if s.lower().startswith("r"):
        s = s[1:]
    return int(s)


# ---------------------------------------------------------------------------------
# numbers and times
# ---------------------------------------------------------------------------------
def parse_num(s, locale="en_US"):
    s = clean(s).replace("\u202f", " ")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.startswith("-"):
        neg, s = True, s[1:]
    if s.startswith("+"):
        s = s[1:]
    if locale in ("de_DE",):
        s = s.replace(".", "").replace(",", ".")
    elif locale == "fr_FR":
        s = s.replace(" ", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    d = Decimal(s)
    return -d if neg else d


TZ_OFF = {"UTC": 0, "Europe/Berlin": 7200, "America/Chicago": -18000, "Asia/Kolkata": 19800, "America/Sao_Paulo": -10800}


def parse_local(s):
    """'YYYY-MM-DD HH:MM:SS[.mmm]' -> epoch milliseconds as if UTC."""
    m = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d):(\d\d)(?:\.(\d{3}))?", s.strip())
    y, mo, d, h, mi, se = (int(x) for x in m.groups()[:6])
    ms = int(m.group(7) or 0)
    return ts_utc(y, mo, d, h, mi, se) * 1000 + ms


def parse_iso_any(s):
    """ISO 8601 with Z or numeric offset -> epoch ms."""
    s = s.strip()
    m = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d+))?(Z|[+-]\d\d:?\d\d)?", s)
    y, mo, d, h, mi, se = (int(x) for x in m.groups()[:6])
    frac = m.group(7) or "0"
    ms = int((frac + "000")[:3])
    t = ts_utc(y, mo, d, h, mi, se) * 1000 + ms
    z = m.group(8)
    if z and z != "Z":
        sign = 1 if z[0] == "+" else -1
        z = z[1:].replace(":", "")
        t -= sign * (int(z[:2]) * 3600 + int(z[2:]) * 60) * 1000
    return t


def serial_to_epoch(v, base=(1899, 12, 30)):
    return int(round((float(v)) * 86400)) + ts_utc(*base)


def date_any(v):
    """ISO date, ISO date-time, epoch seconds or spreadsheet serial -> epoch seconds."""
    s = clean(v)
    if re.fullmatch(r"\d{4}-\d\d-\d\d", s):
        y, mo, d = (int(x) for x in s.split("-"))
        return ts_utc(y, mo, d)
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", s):
        d, mo, y = (int(x) for x in s.split("/"))
        return ts_utc(y, mo, d)
    if "T" in s:
        return parse_iso_any(s) // 1000
    f = float(s)
    if f > 1e8:
        return int(f)
    return serial_to_epoch(f)


# ---------------------------------------------------------------------------------
# containers
# ---------------------------------------------------------------------------------
def read_text_lines(path):
    out = []
    with open(path, "rb") as fh:
        for raw in fh.read().split(b"\n"):
            try:
                out.append(raw.decode("utf-8"))
            except UnicodeDecodeError:
                out.append(raw.decode("latin-1"))
    if out and out[-1] == "":
        out.pop()
    if out and out[0].startswith("\ufeff"):
        out[0] = out[0][1:]
    return out


W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def docx_read(path):
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    body = root.find(W_NS + "body")
    paras, tables = [], []
    for el in body:
        if el.tag == W_NS + "p":
            paras.append("".join(t.text or "" for t in el.iter(W_NS + "t")))
        elif el.tag == W_NS + "tbl":
            rows = []
            for tr in el.findall(W_NS + "tr"):
                rows.append(["".join(t.text or "" for t in tc.iter(W_NS + "t")) for tc in tr.findall(W_NS + "tc")])
            tables.append(rows)
    return paras, tables


def xlsx_read(path):
    out = {}
    with zipfile.ZipFile(path) as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels}
        for sh in wb.iter(S_NS + "sheet"):
            rid = sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            root = ET.fromstring(zf.read("xl/" + target[rid]))
            rows = []
            for row in root.iter(S_NS + "row"):
                cells = {}
                for c in row.findall(S_NS + "c"):
                    ref = c.get("r")
                    col = 0
                    for ch in re.match(r"[A-Z]+", ref).group(0):
                        col = col * 26 + ord(ch) - 64
                    if c.get("t") == "inlineStr":
                        v = "".join(t.text or "" for t in c.iter(S_NS + "t"))
                    else:
                        vv = c.find(S_NS + "v")
                        v = None if vv is None else vv.text
                        if v is not None:
                            v = float(v) if any(ch in v for ch in ".eE") else int(v)
                    cells[col - 1] = v
                rows.append([cells.get(i) for i in range(max(cells) + 1)] if cells else [])
            out[sh.get("name")] = rows
    return out


def pdf_lines(path):
    data = open(path, "rb").read()
    lines = []
    for m in re.finditer(PDF_STREAM_RE.encode("ascii"), data, re.S):
        try:
            content = zlib.decompress(m.group(1)).decode("latin-1")
        except zlib.error:
            continue
        for s in re.finditer(r"\(((?:\\.|[^\\)])*)\) Tj", content):
            t = re.sub(r"\\(.)", r"\1", s.group(1))
            lines.append(t)
    return lines


class _HT(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.paras, self._cell, self._row, self._tab, self._p = [], [], None, None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._tab = []
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = ""
        elif tag in ("p", "li"):
            self._p = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None:
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._tab is not None:
            self._tab.append(self._row)
            self._row = None
        elif tag == "table":
            self.tables.append(self._tab)
            self._tab = None
        elif tag in ("p", "li"):
            self.paras.append(self._p)
            self._p = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data
        elif self._p is not None:
            self._p += data


def html_read(path):
    p = _HT()
    p.feed(open(path, encoding="utf-8").read())
    return p.paras, p.tables


def md_tables(lines):
    tables, cur = [], None
    for ln in lines:
        if ln.startswith("|"):
            cells = [c.replace("\\|", "|").strip(" ") for c in re.split(r"(?<!\\)\|", ln)[1:-1]]
            if cur is None:
                cur = [cells]
            elif set(ln.replace("|", "")) <= {"-"}:
                continue
            else:
                cur.append(cells)
        else:
            if cur is not None:
                tables.append(cur)
                cur = None
    if cur is not None:
        tables.append(cur)
    return tables


def unq(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def by_header(rows, header):
    """Map a table row to {column: value} using its header row."""
    return {h: (rows[i] if i < len(rows) else None) for i, h in enumerate(header)}


# ---------------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------------
def load_documents(dd):
    pol = read_text_lines(os.path.join(dd, "certification_policy.md"))
    ptext = "\n".join(pol)
    C.conf = {}
    C.conf = load_confusables(ptext)
    C.ece_cap = Decimal(re.search(r"calibration error is at most ([0-9]+\.[0-9]+)", ptext).group(1))
    C.auroc_floor = Decimal(re.search(r"AUROC is at least ([0-9]+\.[0-9]+)", ptext).group(1))
    C.baseline = re.search(r"The baseline model is (\S+?)\.", ptext).group(1)
    C.policy_tables = md_tables(pol)
    sc = read_text_lines(os.path.join(dd, "source_conventions.md"))
    C.sc_text = "\n".join(sc)
    C.sc_tables = md_tables(sc)
    C.rg_sec = {}
    for m in re.finditer(r"^(\S+\.parquet): row groups ([0-9, ]+) store emitted as epoch seconds", C.sc_text, re.M):
        C.rg_sec[m.group(1)] = {int(x) for x in m.group(2).split(",")}
    md = pdf_lines(os.path.join(dd, "metric_definitions.pdf"))
    C.md_prose = " ".join(l.strip() for l in md if " | " not in l and not l.startswith("TABLE"))
    C.md_rows = md
    seg = re.search(r"Contamination thresholds: ((?:\w+ \d\.\d{4}(?:, )?)+)", C.md_prose).group(1)
    C.thresh = {b: Decimal(v) for b, v in re.findall(r"(\w+) (\d\.\d{4})", seg)}
    ma = pdf_lines(os.path.join(dd, "methodology_appendix.pdf"))
    C.ma_rows = ma
    C.ma_prose = " ".join(l.strip() for l in ma if " | " not in l and not l.startswith("TABLE"))
    C.alpha = Fraction(Decimal(re.search(r"improved when p < ([0-9]+\.[0-9]+)", C.ma_prose).group(1)))
    paras, tables = html_read(os.path.join(dd, "field_precedence.html"))
    C.prec_rows = tables[0]
    C.class_tables = tables[1:]
    paras, tables = html_read(os.path.join(dd, "control_totals.html"))
    C.ctl_tables = tables


def pdf_tables(lines):
    """TABLE header lines start a table; data rows are ' | ' separated; a trailing backslash continues a row."""
    joined, carry = [], None
    for ln in lines:
        if carry is not None:
            ln = carry + " | " + ln.strip()
            carry = None
        if ln.endswith(" \\"):
            carry = ln[:-2].rstrip()
            continue
        joined.append(ln)
    lines = joined
    out, cur = [], None
    for ln in lines:
        if ln.startswith("TABLE "):
            cur = [x.strip() for x in ln[6:].split(" | ")]
            out.append([cur])
        elif cur is not None and " | " in ln:
            out[-1].append([x for x in ln.split(" | ")])
    return out


# ---------------------------------------------------------------------------------
# errata register
# ---------------------------------------------------------------------------------
def load_errata(dd):
    paras, tables = docx_read(os.path.join(dd, "errata_register.docx"))
    rows = tables[-1]
    hdr = rows[0]
    entries = []
    for r in rows[1:]:
        e = by_header(r, hdr)
        kind = clean(e["kind"])
        src = clean(e["source"])
        tgt = re.sub(r"\s+", " ", (e["target"] or "").replace("\r", " ").replace("\n", "")).strip()
        entries.append((kind, src, tgt))
    seen = set()
    live = []
    for e in entries:
        if e in seen:
            continue
        seen.add(e)
        live.append(e)
    def norm_t(t):
        return cid_rid(t) or t
    undone = {(src, norm_t(tgt)) for k, src, tgt in live if k == "UNDO"}
    C.void_rows = set()
    C.void_entry = set()
    C.void_jobs = set()
    C.void_base = set()
    C.restore = set()
    C.shard_excl = set()
    def srcname(s):
        if s == "-":
            return s
        return s if "." in s else s
    for k, src, tgt in live:
        if k == "UNDO" or (src, norm_t(tgt)) in undone:
            continue
        if k == "VOID-ROW":
            C.void_rows.add((src, cid_rid(tgt)))
        elif k == "VOID-ENTRY":
            key, _, rv = tgt.rpartition(" rev ")
            C.void_entry.add((src, key.strip(), rv.strip()))
        elif k == "VOID-JOB":
            C.void_jobs.add(cid_job(tgt))
        elif k == "VOID-BASELINE":
            iid, d = tgt.rsplit(" ", 1)
            C.void_base.add((cid_item(iid), date_any(d)))
        elif k == "RESTORE":
            C.restore.add(cid_job(tgt))
        elif k == "EXCLUDE-SHARD":
            C.shard_excl.add(tgt.lower())
    # source names can be written without extension
    files = set(os.listdir(dd))
    def full(s):
        if s in files or s == "-":
            return s
        for f in files:
            if f.rsplit(".", 1)[0] == s:
                return f
        return s
    C.void_rows = {(full(s), r) for s, r in C.void_rows}
    C.void_entry = {(full(s), k, v) for s, k, v in C.void_entry}


def voided(fname, key, rev):
    return (fname, key, str(rev)) in C.void_entry


# ---------------------------------------------------------------------------------
# hosts and clocks
# ---------------------------------------------------------------------------------
FLEET_ALIAS = {"fleet-a": "a", "prod-b": "b", "fleet-c": "c", "fleet-d": "d", "fleet-j": "j", "stage": "s", "staging": "s"}
TZ_ABBR = {"CEST": "Europe/Berlin", "CDT": "America/Chicago", "IST": "Asia/Kolkata", "BRT": "America/Sao_Paulo"}


def week_key(s):
    s = clean(s)
    m = re.fullmatch(r"2025-W(\d\d)", s)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"W?(\d\d)", s)
    if m:
        return int(m.group(1))
    return iso_week_of(date_any(s))


def load_hosts(dd):
    inv = {}
    snap = 0
    for ln in read_text_lines(os.path.join(dd, "host_inventory.ini")):
        if ln.startswith("#") or not ln.strip():
            continue
        m = re.match(r"\[snapshot-(\d+)\]", ln)
        if m:
            snap = int(m.group(1))
            continue
        key, _, val = ln.partition("=")
        hraw, _, wraw = key.rpartition("@")
        host, wk = cid_host(hraw), week_key(wraw)
        if voided("host_inventory.ini", f"{host}@2025-W{wk}", f"snapshot-{snap}"):
            continue
        attrs = {}
        for part in val.split(";"):
            if "=" in part:
                k, _, v = part.partition("=")
                attrs[k.strip()] = v.strip()
        fl = attrs["fleet"].lower()
        tz = attrs["tz"]
        loc = attrs["locale"].replace("-", "_")
        loc = loc[:2].lower() + "_" + loc[3:].upper()
        sc = attrs["scale"]
        rec = {"fleet": FLEET_ALIAS.get(fl, fl), "tz": TZ_ABBR.get(tz, tz), "locale": loc,
               "scale": 100 if sc in ("pct", "100") else 1}
        prev = inv.get((host, wk))
        if prev is None or snap >= prev[0]:
            inv[(host, wk)] = (snap, rec)
    C.inv = {k: v[1] for k, v in inv.items()}
    clk = {}
    cols = None
    for ln in read_text_lines(os.path.join(dd, "clock_offsets.txt")):
        if ln.startswith("#COLUMNS"):
            cols = ln.split()[1:]
            continue
        toks = ln.split()
        rec = dict(zip(cols, toks))
        host, wk = cid_host(rec["HOST"]), week_key(rec["WEEK"])
        seq = int(rec["SEQ"])
        if voided("clock_offsets.txt", f"{host}@{wk}", f"seq-{seq}"):
            continue
        ov, unit = rec["OFFSET"], rec["UNIT"].upper()
        if ov == "------":
            off = 0
        else:
            neg = ov.startswith("(") or ov.startswith("-")
            v = Decimal(ov.strip("()+-"))
            off = int(v * 1000) if unit == "S" else int(v)
            off = -off if neg else off
        prev = clk.get((host, wk))
        if prev is None or seq > prev[0]:
            clk[(host, wk)] = (seq, off)
    C.clock = {k: v[1] for k, v in clk.items()}


def hostweek(host, wk):
    rec = C.inv[(host, wk)]
    return rec["tz"], rec["locale"], rec["scale"], C.clock.get((host, wk), 0)


def load_maintenance(dd):
    ev, cur, last = [], None, None
    for ln in read_text_lines(os.path.join(dd, "maintenance_windows.ics")):
        if ln.startswith(" ") and cur is not None:
            continue
        if ln == "BEGIN:VEVENT":
            cur = {}
        elif ln == "END:VEVENT":
            ev.append(cur)
            cur = None
        elif cur is not None:
            name, _, value = ln.partition(":")
            key, *params = name.split(";")
            cur[key] = (params, value)
    best = {}
    for e in ev:
        uid = e["UID"][1].lower().split("@")[0]
        seq = int(e["SEQUENCE"][1]) if "SEQUENCE" in e else 0
        if uid not in best or seq > best[uid][0]:
            best[uid] = (seq, e)
    C.maint = {}
    for uid, (seq, e) in best.items():
        if e.get("STATUS", ([], ""))[1] == "CANCELLED":
            continue
        params, v = e["DTSTART"]
        if any(p.startswith("VALUE=DATE") for p in params):
            continue
        host = cid_host(e["X-HOST"][1])

        def tconv(params, v):
            tzp = [p for p in params if p.startswith("TZID=")]
            m = re.fullmatch(r"(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)(Z?)", v)
            t = ts_utc(*(int(x) for x in m.groups()[:6]))
            if tzp:
                t -= TZ_OFF[tzp[0][5:].strip('"')]
            return t
        st = tconv(params, v)
        if "DTEND" in e:
            en = tconv(*e["DTEND"])
        else:
            en = st + int(re.fullmatch(r"PT(\d+)H", e["DURATION"][1]).group(1)) * 3600
        C.maint.setdefault(host, []).append((st, en))


# ---------------------------------------------------------------------------------
# lineage, tags, approvals
# ---------------------------------------------------------------------------------
FAMILY_ALIAS = {"7B": "7b", "13B": "13b", "34B": "34b", "OSP-13": "osp13"}


def load_lineage(dd):
    data = json.load(open(os.path.join(dd, "checkpoint_lineage.json"), encoding="utf-8"))
    best = {}
    for e in data["checkpoints"]:
        cid = cid_ckpt(e["id"])
        reg = e["registered_at"]
        reg_t = int(reg) if isinstance(reg, (int, float)) else parse_iso_any(reg) // 1000
        if voided("checkpoint_lineage.json", cid, iso_z(reg_t)):
            continue
        fam = str(e["family"])
        fam = FAMILY_ALIAS.get(fam, fam).lower()
        ctx = e["context_window"]
        if isinstance(ctx, str):
            ctx = int(ctx[:-1]) * 1024 if ctx.upper().endswith("K") else int(ctx)
        rec = {"family": fam, "tokenizer": e["tokenizer"], "ctx": int(ctx), "run": str(e["run"]).strip()}
        if cid not in best or reg_t > best[cid][0]:
            best[cid] = (reg_t, rec)
    C.ckpt = {k: v[1] for k, v in best.items()}
    snap = json.load(open(os.path.join(dd, "checkpoint_lineage_snapshot.json"), encoding="utf-8"))
    for e in snap["checkpoints"]:
        if not e.get("ema"):
            continue
        cid = cid_ckpt(e.get("id", e.get("ckpt")))
        parent = cid_ckpt(e["ema_of"])
        if parent in C.ckpt:
            p = C.ckpt[parent]
            C.ckpt[cid] = dict(p, ema_of=parent)


def load_mail(dd):
    import email
    import email.utils
    import quopri
    C.approvals = {}
    C.seal = {}
    reseal = {}
    with open(os.path.join(dd, "evalops_notifications.mbox"), "rb") as fh:
        raw = fh.read().decode("utf-8")
    msgs = re.split(r"\n(?=From evalops@)", "\n" + raw)
    for m in msgs:
        m = m.strip("\n")
        if not m:
            continue
        lines = m.split("\n")[1:]
        hdr, body = {}, []
        i = 0
        while i < len(lines) and lines[i]:
            k, _, v = lines[i].partition(": ")
            hdr[k] = v
            i += 1
        body = "\n".join(lines[i + 1:])
        date = re.sub(r"\s*\([A-Z]+\)$", "", hdr["Date"])
        t = int(email.utils.parsedate_to_datetime(date).timestamp())
        subj = hdr["Subject"]
        if subj.lower().startswith("fwd:"):
            continue
        ms = re.match(r"\[evalops\]\s+(sealed|reseal)\s+job\s+(\S+)", subj, re.I)
        if ms:
            j = cid_job(ms.group(2))
            if ms.group(1).lower() == "reseal":
                reseal[j] = max(reseal.get(j, 0), t)
            else:
                C.seal.setdefault(j, t)
                C.seal[j] = min(C.seal[j], t)
            continue
        ma = re.match(r"\[registry\]\s+(approved|rejected)\s+(\S+)\s+tag\s+(\S+)", subj, re.I)
        if ma:
            tk = cid_ticket(ma.group(2), "CHG")
            C.approvals.setdefault(tk, []).append((ma.group(1).upper(), t))
    C.seal.update(reseal)


def load_tags(dd, aliases):
    data = yaml.load(open(os.path.join(dd, "model_tags.yaml"), encoding="utf-8"), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    cutoff = ts_utc(2025, 10, 3, 18, 0, 0)
    lower = {a.lower(): a for a in aliases}
    evs = {}
    for e in data["events"]:
        tag = str(e["tag"]).lower()
        if tag not in lower:
            continue
        a = lower[tag]
        tk = cid_ticket(str(e["ticket"]), "CHG")
        evs.setdefault(a, []).append({"ckpt": cid_ckpt(e["checkpoint"]), "action": e["action"], "ticket": tk})
    C.lineage = {}
    for a in aliases:
        eff, voided_n = [], 0
        for e in evs.get(a, []):
            ap = C.approvals.get(e["ticket"], [])
            rej = any(v == "REJECTED" for v, t in ap)
            oks = [t for v, t in ap if v == "APPROVED" and t <= cutoff]
            if oks and not rej:
                eff.append((min(oks), e["ticket"], e))
            else:
                voided_n += 1
        eff.sort(key=lambda x: (x[0], x[1]))
        t, tk, e = eff[-1]
        C.lineage[a] = {"checkpoint": e["ckpt"], "effective_from": iso_z(t), "approval_ref": tk, "voided_promotions": voided_n}


# ---------------------------------------------------------------------------------
# jobs
# ---------------------------------------------------------------------------------
LEGACY_SUITE_R = {"arithmetic": "arith", "codegen": "code", "intents": "intent", "safety_flags": "safety", "multiple_choice": "mcq",
                  "pairwise": "pref", "long_context": "longctx", "multilingual": "multiling"}


def suite_name(s):
    s = clean(s).lower()
    return LEGACY_SUITE_R.get(s, s)


def load_jobs(dd):
    root = ET.parse(os.path.join(dd, "run_registry.xml")).getroot()
    best = {}
    for el in root:
        a = el.attrib
        j = cid_job(a["id"])
        model = (a.get("model") or a.get("alias")).lower()
        ck = a.get("checkpoint") or a.get("ckpt")
        shard = int(a["shard"]) - (1 if a.get("base") == "1" else 0)
        rec = {"model": model, "ck_raw": ck, "bench": suite_name(a["suite"]), "shard": shard,
               "host": cid_host(a["host"]), "seq": int(a["seq"])}
        if j not in best or rec["seq"] > best[j]["seq"]:
            best[j] = rec
    C.jobs = best
    # retired scheduler numbers
    rx = ET.parse(os.path.join(dd, "run_registry_export.xml")).getroot()
    C.legacy_no = {}
    for el in rx:
        ln = el.attrib.get("legacy_no")
        if ln:
            n = re.sub(r"(?i)^l-", "", clean(ln))
            jj = cid_job(el.attrib["id"])
            if jj:
                C.legacy_no[f"L-{n}"] = jj
    # configs
    cfg = tomllib.load(open(os.path.join(dd, "job_configs.toml"), "rb"))
    C.harness = {}
    bestc = {}
    for t in cfg["job"]:
        j = cid_job(t["id"])
        rv = rev_int(t["revision"]) if isinstance(t["revision"], str) else int(t["revision"])
        if voided("job_configs.toml", j, rv):
            continue
        hv = str(t["harness"]).lower().replace("harness-", "")
        hv = hv if hv.startswith("h") else "h" + hv
        if j not in bestc or rv > bestc[j][0]:
            bestc[j] = (rv, hv)
    C.harness = {k: v[1] for k, v in bestc.items()}
    C.models = sorted({r["model"] for r in C.jobs.values()})


def resolve_job_checkpoints():
    """Short checkpoint prefixes resolve to the unique checkpoint of the model's family."""
    for j, rec in C.jobs.items():
        raw = clean(rec["ck_raw"])
        if len(raw) != 7:
            rec["ckpt"] = cid_ckpt(raw)
            continue
        pref = raw.lower()
        fam = C.ckpt[C.lineage[rec["model"]]["checkpoint"]]["family"]
        cands = sorted(c for c in C.ckpt if c.startswith(pref) and C.ckpt[c]["family"] == fam)
        rec["ckpt"] = cands[0] if len(cands) == 1 else None


def load_events(dd):
    C.submit = {}
    C.rerun_of = {}
    raw_sub = {}
    for ln in read_text_lines(os.path.join(dd, "harness_events.log")):
        if re.match(r"\d{4}-\d\d-\d\dT", ln):
            ts, rest = ln.split(" ", 1)
            t_ms = parse_iso_any(ts)
            corr = False
        else:
            ts, rest = ln[:23], ln[23:]
            t_ms = parse_local(ts)
            corr = True
        m = re.match(r"\s*(.+?)\s+(SUBMIT|RERUN|END)\s+(.*)$", rest)
        kind, kv = m.group(2), dict(re.findall(r"(\w+)=(\u00a0?\S+)", m.group(3)))
        if kind == "SUBMIT":
            jr = kv["job"]
            j = C.legacy_no.get(re.sub(r"(?i)^l-", "L-", clean(jr))) if clean(jr).upper().startswith("L-") else cid_job(jr)
            if j not in C.jobs:
                continue
            raw_sub.setdefault(j, []).append((corr, t_ms))
        elif kind == "RERUN":
            o, rr = cid_job(kv["of"]) if not clean(kv["of"]).upper().startswith("L-") else C.legacy_no.get(clean(kv["of"])), cid_job(kv["as"])
            C.rerun_of[rr] = o
    C.job_week = {}
    for j, lst in raw_sub.items():
        host = C.jobs[j]["host"]
        # the zone and clock entry is the one of the ISO week of the submission instant
        wk = None
        best = None
        for cand_wk in sorted({iso_week_of(t // 1000 + dw) for c, t in lst for dw in (-86400, 0, 86400)}):
            if (host, cand_wk) not in C.inv:
                continue
            tz, loc, sc, off = hostweek(host, cand_wk)
            vals = [t - (TZ_OFF[tz] * 1000 + off if c else 0) for c, t in lst]
            first = min(vals)
            if iso_week_of(first // 1000) == cand_wk:
                best, wk = first, cand_wk
                break
        C.submit[j] = best
        C.job_week[j] = wk


def load_minutes(dd):
    paras, tables = docx_read(os.path.join(dd, "review_minutes.docx"))
    rows = tables[-1]
    hdr = rows[0]
    best = {}
    DEC = {"approve": "rerun-approved", "deny": "rerun-denied", "exempt": "exempt-maintenance", "ok": "accepted"}
    for r in rows[1:]:
        e = by_header(r, hdr)
        j = cid_job(unq(e["job"]))
        dec = unq(e["decision"]).replace("\r", "").replace("\n", "").strip()
        dec = DEC.get(dec, dec)
        mt = unq(e["meeting"]).strip()
        rv = None
        if " r" in mt:
            mt, rv = mt.split(" r")
        d = date_any(mt)
        rvv = int(rv) if rv else None
        if j is None or j not in C.jobs:
            continue
        # revision of a decision row = its meeting day offset; voids name (job, revision)
        rev = d
        if voided("review_minutes.docx", j, (d - ts_utc(2025, 9, 22)) // 86400):
            continue
        if j not in best or d > best[j][0]:
            best[j] = (d, dec)
    C.decision = {k: v[1] for k, v in best.items()}


# ---------------------------------------------------------------------------------
# item registries
# ---------------------------------------------------------------------------------
def latest(rows):
    """rows: iterable of (key, rev, value); highest revision per key wins (later row on ties)."""
    out = {}
    for k, rv, v in rows:
        if k is None:
            continue
        if k not in out or rv >= out[k][0]:
            out[k] = (rv, v)
    return {k: v for k, (rv, v) in out.items()}


def csv_rows(path, delim=","):
    text = "\n".join(read_text_lines(path))
    return list(csv.reader(io.StringIO(text), delimiter=delim))


def header_walk(rows, names):
    """Yield (header, row); a header row may repeat mid-file with reordered columns."""
    hdr = None
    for r in rows:
        if not r:
            continue
        if r[0].strip() in names:
            hdr = [x.strip() for x in r]
            continue
        yield hdr, r


def load_shard_map():
    rows = []
    for tab in pdf_tables(C.md_rows):
        hdr = tab[0]
        base1 = hdr[0] != "suite"
        for r in tab[1:]:
            e = by_header([unq(x.strip()) for x in r], hdr)
            iid = cid_item(unq(e["item_id"]))
            rv = rev_int(unq(e["revision"]))
            if voided("metric_definitions.pdf", iid, rv):
                continue
            o = int(clean(e["ordinal"])) - (1 if base1 else 0)
            rows.append((iid, rv, (suite_name(unq(e["suite"])), int(clean(e["shard"])), o)))
    C.shard_of = latest(rows)


def load_items(dd):
    load_shard_map()
    rows = csv_rows(os.path.join(dd, "item_registry.csv"))
    reg = []
    for hdr, r in header_walk(rows, {"item_id"}):
        e = by_header(r, hdr)
        iid = cid_item(e["item_id"])
        rv = rev_int(e["revision"])
        if rv == 0 or voided("item_registry.csv", iid, rv):
            continue
        suite = suite_name(e["suite"])
        if suite == "sandbox":
            continue
        reg.append((iid, rv, {"suite": suite, "taxonomy": e["taxonomy"].strip()}))
    items = latest(reg)
    C.items = {k: v for k, v in items.items() if k in C.shard_of}
    C.shard_items = {}
    for iid in C.items:
        b_, s_, o_ = C.shard_of[iid]
        C.shard_items.setdefault((b_, s_), {})[o_] = iid
    C.bench = {k: C.shard_of[k][0] for k in C.items}
    C.item_taxo = {k: (v["taxonomy"] if v["taxonomy"] in ("v1", "v2") else "v1") for k, v in C.items.items()}
    # label aliases and taxonomy
    la = json.load(open(os.path.join(dd, "label_aliases.json"), encoding="utf-8"))
    v1, v2 = la["taxonomy"]["v1"], la["taxonomy"]["v2"]
    C.v2name = dict(zip(v1, v2))
    C.v1name = dict(zip(v2, v1))
    ent = []
    for e in la["aliases"]:
        raw = unicodedata.normalize("NFC", e["raw"])
        rv = e["revision"]
        rv = rev_int(rv) if isinstance(rv, str) else int(rv)
        if voided("label_aliases.json", raw, rv):
            continue
        c1 = str(e["v1"]).strip().lower()
        if c1 not in C.v2name:
            continue
        c2 = e["v2"]
        c2 = C.v2name[c1] if c2 is None else str(c2).strip().lower()
        ent.append((raw, rv, (c1, C.v1name.get(c2, c2))))
    C.alias = latest(ent)
    # gold, errata
    gold = []
    for hdr, r in header_walk(csv_rows(os.path.join(dd, "gold_labels.tsv"), "\t"), {"item_id"}):
        e = by_header(r, hdr)
        iid = cid_item(e["item_id"])
        g = e.get("gold") if e.get("gold") is not None else e.get("answer")
        rv = rev_int(e["revision"])
        if voided("gold_labels.tsv", iid, rv):
            continue
        gold.append((iid, rv, unicodedata.normalize("NFC", g.replace("\\t", "\t"))))
    C.gold_raw = {k: v for k, v in latest(gold).items() if k in C.items}
    tickets = {}
    for hdr, r in header_walk(csv_rows(os.path.join(dd, "gold_labels_corrected.csv")), {"item_id"}):
        e = by_header(r, hdr)
        iid = cid_item(e["item_id"])
        if iid in C.items:
            tickets[cid_ticket(e["dispute_ticket"], "DSP")] = iid
    root = ET.parse(os.path.join(dd, "grader_errata.xml")).getroot()
    cutoff = ts_utc(2025, 10, 3, 18, 0, 0)
    best = {}
    for blk in root.iter():
        if blk.tag not in ("erratum", "correction"):
            continue
        a = blk.attrib
        tk = cid_ticket(a["ticket"], "DSP")
        st = a["status"].strip().lower()
        val = (a.get("value") if "value" in a else a.get("fix")).strip()
        dec = a["decided"].strip()
        t = int(dec) if re.fullmatch(r"\d+", dec) else parse_iso_any(dec) // 1000
        if t > cutoff or st not in ("upheld", "withdrawn"):
            continue
        if tk not in best or t >= best[tk][0]:
            best[tk] = (t, st, val)
    C.gold = {}
    for iid, g in C.gold_raw.items():
        if C.bench[iid] == "intent":
            g = g.strip().lower()
            g = C.v1name.get(g, g) if C.item_taxo[iid] == "v2" else g
        C.gold[iid] = g
    for tk, (t, st, val) in best.items():
        iid = tickets.get(tk)
        if iid and st == "upheld":
            C.gold[iid] = C.v1name.get(val.lower(), val.lower()) if C.bench[iid] == "intent" else val
    # scoring parameters
    sp = xlsx_read(os.path.join(dd, "scoring_parameters.xlsx"))
    TOL = {"abs": "abs", "rel": "rel", "exact": "exact", "eq": "exact", "==": "exact", "abs:0.01": "abs", "absolute 0.01": "abs", "+-0.01": "abs",
           "rel:1%": "rel", "rel:0.01": "rel", "relative 1 percent": "rel"}
    params = []
    for name, rows in sp.items():
        hdr = [str(x) for x in rows[0]]
        for r in rows[1:]:
            e = by_header(r, hdr)
            iid = cid_item(str(e["item_id"]).replace("\r\n", ""))
            rv = rev_int(str(e["revision"]))
            if voided("scoring_parameters.xlsx", iid, rv):
                continue
            rec = {}
            if "tolerance" in e:
                t = str(e["tolerance"]).replace("\r\n", "").strip()
                rec["tol"] = TOL.get(t)
                tv = str(e["tests"]).strip()
                rec["tests"] = int(tv.split()[0]) if tv != "-" else None
            if "n_options" in e:
                n = str(e["n_options"]).strip()
                if n.startswith("A-"):
                    rec["nopt"] = ord(n[2]) - 64
                elif n in ("four", "five"):
                    rec["nopt"] = 4 if n == "four" else 5
                elif n != "-":
                    rec["nopt"] = int(float(n))
            params.append((iid, rv, rec))
    C.params = latest(params)
    # manifest
    sm = xlsx_read(os.path.join(dd, "suite_manifest.xlsx"))
    sheet_suites = {}
    for m in re.finditer(r"(\w+) \(([a-z, ]+)\)", re.search(r"suite_manifest\.xlsx sheets hold these suites: (.+?)\.\n", C.sc_text + "\n").group(1)):
        sheet_suites[m.group(1)] = {x.strip() for x in m.group(2).split(",")}
    end = ts_utc(2025, 10, 1)
    st_rows = []
    for name, rows in sm.items():
        hdr = [str(x) for x in rows[0]]
        for r in rows[1:]:
            e = by_header(r, hdr)
            iid = cid_item(e["item_id"])
            if iid not in C.bench or C.bench[iid] not in sheet_suites[name]:
                continue
            rv = rev_int(str(e["revision"]))
            if voided("suite_manifest.xlsx", iid, rv):
                continue
            st = str(e["status"]).replace("\r\n", "").strip().lower()
            st = {"ret": "retired", "r": "retired", "act": "active", "a": "active", "added": "active"}.get(st, st)
            ch = e["changed_at"]
            t = 0 if ch in (0, "0", None) else date_any(ch)
            if st == "retired" and t and t >= end:
                continue
            st_rows.append((iid, rv, st))
    status = latest(st_rows)
    C.retired = {k for k, v in status.items() if v == "retired"}
    # dedup
    dd_rows = []
    for hdr, r in header_walk(csv_rows(os.path.join(dd, "dedup_clusters.tsv"), "\t"), {"item_id", "cluster"}):
        e = by_header(r, hdr)
        iid = cid_item(e["item_id"])
        rv = rev_int(e["revision"])
        if voided("dedup_clusters.tsv", iid, rv):
            continue
        dd_rows.append((iid, rv, int(clean(e["cluster"]))))
    clus = latest(dd_rows)
    groups = {}
    for iid, c in clus.items():
        if c and iid in C.items:
            groups.setdefault((iid[:3], c), []).append(iid)
    C.duplicate = set()
    for k, mem in groups.items():
        if len(mem) > 1:
            canon = min(mem)
            C.duplicate |= {m for m in mem if m != canon}
    # contamination
    C.contaminated = set()
    for ln in read_text_lines(os.path.join(dd, "contamination_hits.jsonl")):
        o = json.loads(ln)
        iid = cid_item(o.get("item", o.get("item_ref")))
        if iid not in C.items or o.get("retracted") or o["overlap"] is None:
            continue
        if str(o["shard"]).lower() in C.shard_excl:
            continue
        ov = Decimal(str(o["overlap"]))
        if str(o["detector"]).lower() == "ngram-v1":
            ov = round_half_even(str(ov), 2) / 100
        ov = ov.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
        if ov >= C.thresh[C.bench[iid]]:
            C.contaminated.add(iid)
    # scope (policy appendix A)
    sc_rows = []
    for tab in C.policy_tables:
        hdr = [h.strip() for h in tab[0]]
        if "scope" not in hdr:
            continue
        for r in tab[1:]:
            e = by_header([unq(x.strip()) for x in r], hdr)
            iid = cid_item(e["item_id"])
            rv = rev_int(unq(e["revision"]))
            if voided("certification_policy.md", iid, rv):
                continue
            s = unq(e["scope"]).strip().lower()
            held = s in ("held_out", "ho", "private")
            eff = date_any(unq(e["effective"]))
            if held and eff >= end:
                continue
            sc_rows.append((iid, rv, held))
    scope = latest(sc_rows)
    C.held = {k for k, v in scope.items() if v}
    C.elig = {}
    for iid in C.items:
        if iid in C.retired:
            C.elig[iid] = "retired"
        elif iid in C.duplicate:
            C.elig[iid] = "duplicate"
        elif iid in C.contaminated:
            C.elig[iid] = "contaminated"
        elif iid in C.held:
            C.elig[iid] = "out_of_scope"
        else:
            C.elig[iid] = None
    # tokens
    tk_rows = []
    for hdr, r in header_walk(csv_rows(os.path.join(dd, "context_lengths.csv")), {"item_id"}):
        e = by_header(r, hdr)
        iid = cid_item(e["item_id"])
        rv = rev_int(e["revision"])
        if voided("context_lengths.csv", iid, rv):
            continue

        def tok(v):
            v = v.strip().replace(" tok", "")
            if v.endswith("k"):
                return int(round(float(v[:-1]) * 1000))
            return int(v.replace(",", "").replace(" ", ""))
        tk_rows.append((iid, rv, {"hbpe": tok(e["tokens_hbpe"]), "ospsp": tok(e["tokens_ospsp"])}))
    C.tokens = latest(tk_rows)
    # slices
    sd = yaml.load(open(os.path.join(dd, "slice_definitions.yaml"), encoding="utf-8"), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    C.min_support = int(sd["min_support"])
    C.lang_min_support = int(sd["lang_min_support"])
    dom_codes = {str(k).upper(): v for k, v in sd["domain_codes"].items()}
    diff_codes = {str(k): v for k, v in sd["difficulty_codes"].items()}
    reg_alias = {str(k).lower(): v for k, v in sd["region_aliases"].items()}
    C.slices = sorted((nm, sorted((f, [str(x) for x in vals]) for f, vals in conds.items())) for nm, conds in sd["slices"].items())
    rg = []
    for e in sd["regions"]:
        iid = cid_item(e.get("item", e.get("id")))
        rv = rev_int(str(e["rev"]))
        if voided("slice_definitions.yaml", iid, rv):
            continue
        v = str(e["region"]).strip()
        v = reg_alias.get(v.lower(), v.upper())
        rg.append((iid, rv, v))
    C.region = latest(rg)
    at = []
    for hdr, r in header_walk(csv_rows(os.path.join(dd, "slice_attributes.csv")), {"item_id"}):
        e = by_header(r, hdr)
        iid = cid_item(e["item_id"])
        rv = rev_int(e["revision"])
        if voided("slice_attributes.csv", iid, rv):
            continue
        d = e["domain"].strip()
        d = dom_codes.get(d, d.lower()) if d.upper() == d else d.lower()
        x = e["difficulty"].strip().lower()
        x = diff_codes.get(x, {"simple": "easy", "moderate": "medium", "difficult": "hard", "": "medium"}.get(x, x))
        at.append((iid, rv, {"domain": d, "difficulty": x}))
    C.attrs = latest(at)
    # locales
    depmap = {}
    for ln in read_text_lines(os.path.join(dd, "locale_codes_legacy.tsv"))[1:]:
        parts = ln.split("\t")
        if parts[0] in ("kind",):
            hdrll = parts
            continue
        if parts[0] == "map":
            k = parts[1] if not parts[1].startswith("map") else parts[1]
            a, b = (parts[1], parts[2])
            if a.lower() in ("-",) or re.fullmatch(r"[a-z]{2,3}", a.lower()) is None:
                a, b = b, a
            depmap[a.lower()] = b.lower()
    loc_rows = []
    for hdr, r in header_walk(csv_rows(os.path.join(dd, "prompt_locales.tsv"), "\t"), {"item_id", "locale"}):
        e = by_header(r, hdr)
        iid = cid_item(e["item_id"])
        rv = rev_int(e["revision"])
        if voided("prompt_locales.tsv", iid, rv):
            continue
        lang = re.split(r"[-_]", e["locale"].strip())[0].lower()
        lang = depmap.get(lang, lang)
        loc_rows.append((iid, rv, lang))
    C.lang = latest(loc_rows)
    # legacy codes (methodology appendix)
    lc = []
    for tab in pdf_tables(C.ma_rows):
        hdr = tab[0]
        for r in tab[1:]:
            e = by_header([unq(x.strip()) for x in r], hdr)
            iid = cid_item(unq(e["item_id"]))
            rv = rev_int(unq(e["revision"]))
            if voided("methodology_appendix.pdf", iid, rv):
                continue
            lc.append((iid, rv, cid_lc(unq(e["legacy_code"]))))
    C.code_item = {v: k for k, v in latest(lc).items()}
    # weights (board-adopted, scorecard_prelim suite_weight column)
    ps = xlsx_read(os.path.join(dd, "scorecard_prelim.xlsx"))
    C.weights = {}
    for name, rows in ps.items():
        hdr = rows[0]
        for r in rows[1:]:
            e = by_header(r, hdr)
            w = e["suite_weight"]
            w = Decimal(str(w).replace(",", ".")) if isinstance(w, str) else Decimal(repr(w))
            C.weights[e["suite"]] = w


# ---------------------------------------------------------------------------------
# job dispositions
# ---------------------------------------------------------------------------------
WIN_START, WIN_END = ts_utc(2025, 7, 1), ts_utc(2025, 10, 1)


def dispositions():
    approved_of = {}
    for rr, o in C.rerun_of.items():
        if C.decision.get(rr) == "rerun-approved":
            approved_of[o] = rr
    C.disp = {}
    for j, rec in sorted(C.jobs.items()):
        t = (C.submit.get(j) or 0) // 1000
        wk = C.job_week.get(j)
        host = rec["host"]
        if j in C.void_jobs:
            d = "voided"
        elif wk is not None and C.inv[(host, wk)]["fleet"] == "s":
            d = "staging_host"
        elif rec["ckpt"] != C.lineage[rec["model"]]["checkpoint"]:
            d = "stale_checkpoint"
        elif not (WIN_START <= t < WIN_END):
            d = "outside_window"
        elif any(st <= t < en for st, en in C.maint.get(host, [])) and C.decision.get(j) != "exempt-maintenance":
            d = "maintenance"
        elif j in approved_of:
            d = "superseded"
        elif j in C.rerun_of and C.decision.get(j) != "rerun-approved":
            d = "rerun_denied"
        else:
            d = "authoritative"
        C.disp[j] = d


# ---------------------------------------------------------------------------------
# result sources
# ---------------------------------------------------------------------------------
def job_conv(j):
    host = C.jobs[j]["host"]
    wk = C.job_week[j]
    return hostweek(host, wk)


def host_ms(j, local_ms):
    tz, loc, sc, off = job_conv(j)
    return local_ms - TZ_OFF[tz] * 1000 - off


def resolve_job(raw):
    s = clean(raw)
    if s.upper().startswith("L-"):
        return C.legacy_no.get("L-" + s[2:])
    return cid_job(s)


def item_from_pos(j, pos):
    rec = C.jobs[j]
    return C.shard_items.get((rec["bench"], rec["shard"]), {}).get(int(pos))


def num_fix(d, places, scale):
    if scale == 100:
        d = round_half_even(str(d), places - 2) / 100
    return d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)


def rec(src, rid, j, iid, sub, t, vals, **flags):
    r = {"src": src, "rid": rid, "job": j, "item": iid, "sub": sub, "t": t, "vals": vals}
    r.update(flags)
    return r


def parse_logs(dd, name):
    out = []
    for ln in read_text_lines(os.path.join(dd, name)):
        if re.match(r"\d{4}-\d\d-\d\dT", ln):
            ts, rest = ln.split(" ", 1)
            t_raw, utc = parse_iso_any(ts), True
        else:
            ts, rest = ln[:23], ln[23:]
            t_raw, utc = parse_local(ts), False
        m = re.match(r"\s*(.+?)\s+(INFO|WARN)\s+(.*)$", rest)
        body = m.group(3)
        kv = {k: unq(v) for k, v in re.findall(r'(\w+)=(\u00a0?(?:"[^"]*"|\S+))', body)}
        if "flushed" in body:
            continue
        j = resolve_job(kv["job"])
        if j not in C.jobs:
            out.append(rec(name, cid_rid(kv.get("rid", "r0")), None, None, 0, 0, {}, fk=True))
            continue
        t = t_raw if utc else host_ms(j, t_raw)
        if kv.get("op") == "REVERSE":
            out.append(rec(name, cid_rid(kv["rid"]), j, None, 0, t, {}, rev_target=cid_rid(kv["target"])))
            continue
        tz, loc, sc, off = job_conv(j)
        b = kv["bench"]
        iid = cid_item(kv["item"])
        vals = {}
        if b == "arith":
            a = kv["ans"]
            vals["answer"] = None if a == "N/A" else parse_num(a, loc).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        elif b == "safety":
            vals["score"] = num_fix(parse_num(kv["score"], loc), 3, sc)
        elif b == "mcq":
            vals["option"] = kv["opt"]
            vals["conf"] = num_fix(parse_num(kv["conf"], loc), 4, sc)
        elif b == "intent":
            vals["label"] = kv["label"]
        else:
            vals["answer"] = unicodedata.normalize("NFC", kv["ans"])
        out.append(rec(name, cid_rid(kv["rid"]), j, iid, 0, t, vals, bench=b, shadow=kv.get("src") == "shadow"))
    return out


def parse_code(dd):
    out = []
    for ln in read_text_lines(os.path.join(dd, "code_samples.jsonl")):
        o = json.loads(ln)
        j = resolve_job(o["job"])
        if j not in C.jobs:
            out.append(rec("code_samples.jsonl", cid_rid(o["rid"]), None, None, 0, 0, {}, fk=True))
            continue
        ts = o["ts"]
        tz, loc, sc, off = job_conv(j)
        if isinstance(ts, int):
            t = ts - off
        elif ts.endswith("Z"):
            t = parse_iso_any(ts)
        else:
            t = parse_iso_any(ts) - off
        sent = o["exit"] == 137 and o["passed"] == -1
        out.append(rec("code_samples.jsonl", cid_rid(o["rid"]), j, cid_item(o["problem"]), int(o["sample"]), t,
                       {"passed": int(o["passed"])}, bench="code", sentinel=sent))
    return out


def parse_judge(dd):
    out = []
    for ln in read_text_lines(os.path.join(dd, "judge_verdicts.jsonl")):
        o = json.loads(ln)
        j = resolve_job(o["job"])
        if j not in C.jobs:
            out.append(rec("judge_verdicts.jsonl", cid_rid(o["rid"]), None, None, 0, 0, {}, fk=True))
            continue
        iid = cid_item(o["item"])
        v = str(o["verdict"])
        v = {"1": "A", "2": "B", "0": "T"}.get(v, v) if o["judge"] == "jm-2" else v
        order = slot_order(j, iid, int(o["slot"]))
        out.append(rec("judge_verdicts.jsonl", cid_rid(o["rid"]), j, iid, order, parse_iso_any(o["ts"]), {"verdict": v}, bench="pref"))
    return out


def slot_order(j, iid, slot):
    first_cand = C.present.get((j, iid), "slot1_candidate") == "slot1_candidate"
    return "AB" if (slot == 1) == first_cand else "BA"


def load_presentation(dd):
    C.present = {}
    for ln in read_text_lines(os.path.join(dd, "judge_verdicts_rescored.jsonl")):
        o = json.loads(ln)
        j = cid_job(o["job"])
        if j in C.jobs:
            C.present[(j, cid_item(o["item"]))] = o["presentation"]


def parse_parquet(dd, name):
    out = []
    pf = pq.ParquetFile(os.path.join(dd, name))
    secs = C.rg_sec.get(name, set())
    for gi in range(pf.num_row_groups):
        tab = pf.read_row_group(gi).to_pylist()
        for o in tab:
            j = resolve_job(o["job"])
            if j not in C.jobs:
                out.append(rec(name, cid_rid(o["rid"]), None, None, 0, 0, {}, fk=True))
                continue
            tz, loc, sc, off = job_conv(j)
            em = o["emitted"] * 1000 if gi in secs else o["emitted"]
            t = em - off
            b = o["bench"]
            vals = {}
            num = o["num"]
            if b == "safety":
                vals["score"] = num_fix(Decimal(repr(num)), 3, sc)
            elif b == "mcq":
                vals["option"] = o["txt"]
                vals["conf"] = num_fix(Decimal(repr(num)), 4, sc)
            elif b == "intent":
                vals["label"] = o["txt"]
            else:
                vals["answer"] = unicodedata.normalize("NFC", o["txt"])
            out.append(rec(name, cid_rid(o["rid"]), j, cid_item(o["item"]), 0, t, vals, bench=b))
    return out


def parse_store(dd, name):
    out = []
    con = sqlite3.connect(os.path.join(dd, name))
    cols = [r[1] for r in con.execute("PRAGMA table_info(results)")]
    vcol = "value" if "value" in cols else "result_value"
    for rid, job, item, pos, sample, value, emitted, op, target in con.execute(
            f"SELECT rid, job, item, pos, sample, {vcol}, emitted, op, target FROM results"):
        j = resolve_job(job)
        if j not in C.jobs:
            out.append(rec(name, cid_rid(rid), None, None, 0, 0, {}, fk=True))
            continue
        t = parse_local(emitted)
        if op == "REV":
            out.append(rec(name, cid_rid(rid), j, None, 0, t, {}, rev_target=cid_rid(target)))
            continue
        iid = cid_item(item) if item is not None else item_from_pos(j, pos)
        b = C.jobs[j]["bench"]
        vals = {"passed": int(value)} if b == "code" else {"answer": unicodedata.normalize("NFC", value)}
        out.append(rec(name, cid_rid(rid), j, iid, int(sample) if b == "code" else 0, t, vals, bench=b, misroute=iid is None))
    if name == "eval_store_mirror.db":
        C.mirror_void = {(s, cid_rid(r)) for s, r, _ in con.execute("SELECT source, rid, reason FROM void_requests")}
    con.close()
    return out


def parse_legacy(dd):
    out = []
    lay = "A"
    for ln in read_text_lines(os.path.join(dd, "legacy_results.txt")):
        if ln.startswith("#LAYOUT"):
            lay = ln.split()[1]
            continue
        if lay == "A":
            rid, jr, ir, av, em, host = ln[0:9], ln[9:19], ln[19:30], ln[30:50], ln[50:65], ln[66:]
            pos = None
        else:
            rid, host, jr, pos, em, av = ln[0:9], ln[9:20], ln[20:30], ln[30:33], ln[33:48], ln[48:68]
        j = resolve_job(jr)
        if j not in C.jobs:
            out.append(rec("legacy_results.txt", cid_rid(rid), None, None, 0, 0, {}, fk=True))
            continue
        iid = cid_item(ir) if pos is None else item_from_pos(j, pos)
        tz, loc, sc, off = job_conv(j)
        em = em.strip()
        local = ts_utc(int(em[:4]), int(em[4:6]), int(em[6:8]), int(em[8:10]), int(em[10:12]), int(em[12:14])) * 1000
        t = local - TZ_OFF[tz] * 1000
        a = av.strip()
        vals = {"answer": None if a == "N/A" else parse_num(a, loc).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)}
        out.append(rec("legacy_results.txt", cid_rid(rid), j, iid, 0, t, vals, bench="arith", misroute=iid is None))
    return out


def parse_intent_csv(dd):
    out = []
    for hdr, r in header_walk(csv_rows(os.path.join(dd, "intent_predictions.csv")), {"rid"}):
        e = by_header(r, hdr)
        j = resolve_job(e["job"])
        if j not in C.jobs:
            out.append(rec("intent_predictions.csv", cid_rid(e["rid"]), None, None, 0, 0, {}, fk=True))
            continue
        lt = e.get("local_time") or e.get("emitted_local")
        lab = e.get("label") if e.get("label") is not None else e.get("predicted_label")
        t = host_ms(j, parse_local(lt))
        out.append(rec("intent_predictions.csv", cid_rid(e["rid"]), j, cid_item(e["item"]), 0, t, {"label": lab}, bench="intent"))
    return out


def parse_rerun(dd):
    out = []
    for ln in read_text_lines(os.path.join(dd, "rerun_results.jsonl")):
        o = json.loads(ln)
        j = resolve_job(o["job"])
        if j not in C.jobs:
            out.append(rec("rerun_results.jsonl", cid_rid(o["rid"]), None, None, 0, 0, {}, fk=True))
            continue
        iid = cid_item(o["item"])
        b = o["bench"]
        v = o["value"]
        sub = int(o["sample"])
        if b == "arith":
            vals = {"answer": None if v == "N/A" else Decimal(v).quantize(Decimal("0.01"))}
        elif b == "code":
            vals = {"passed": int(v)}
        elif b == "intent":
            vals = {"label": v}
        elif b == "safety":
            vals = {"score": Decimal(repr(v)).quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)}
        elif b == "mcq":
            o_, c_ = v.split("|")
            vals = {"option": o_, "conf": Decimal(c_)}
        elif b == "pref":
            sub = slot_order(j, iid, int(v["slot"]))
            vals = {"verdict": v["verdict"]}
        else:
            vals = {"answer": unicodedata.normalize("NFC", v)}
        out.append(rec("rerun_results.jsonl", cid_rid(o["rid"]), j, iid, sub, parse_iso_any(o["ts"]), vals, bench=b))
    return out


def load_reviews(dd):
    sh = xlsx_read(os.path.join(dd, "manual_overrides.xlsx"))
    rows = sh["reviews"]
    hdr = rows[0]
    best = {}
    for r in rows[1:]:
        e = by_header(r, hdr)
        if str(e["status"]).strip().lower() != "final":
            continue
        j, iid = cid_job(e["job"]), cid_item(e["item"])
        order = slot_order(j, iid, int(str(e["slot"])))
        w = str(e["verdict"]).replace("\r\n", "").strip().lower()
        w = {"=": "tie"}.get(w, w)
        t = float(e["reviewed_at"])
        k = (j, iid, order)
        if k not in best or t >= best[k][0]:
            best[k] = (t, {"candidate": "win", "baseline": "loss", "tie": "tie"}[w])
    C.review = {k: v[1] for k, v in best.items()}


def load_routing():
    rows = []
    for tab in C.sc_tables:
        hdr = [h.strip() for h in tab[0]]
        if "primary_source" not in hdr:
            continue
        for r in tab[1:]:
            e = by_header([unq(x.strip()) for x in r], hdr)
            j = cid_job(e["job"])
            rv = rev_int(unq(e["revision"]))
            if voided("source_conventions.md", j, rv):
                continue
            rows.append((j, rv, (e["primary_source"].strip(), e["copy_source"].strip())))
    files = C.files
    def full(s):
        s = unq(s)
        if s in files or s == "-":
            return s
        for f in files:
            if f.rsplit(".", 1)[0].lower() == s.lower():
                return f
        return s
    C.route = {j: (full(p), full(c)) for j, (p, c) in latest(rows).items()}
    cls = []
    for tab in C.class_tables:
        hdr = [h.strip() for h in tab[0]]
        for r in tab[1:]:
            e = by_header([unq(x.strip()) for x in r], hdr)
            j = cid_job(e["job"])
            rv = rev_int(unq(e["revision"]))
            if voided("field_precedence.html", j, rv):
                continue
            c = clean(unq(e["class"])).lower()
            cls.append((j, rv, {"std": "standard", "br": "bridge"}.get(c, c)))
    C.jclass = latest(cls)
    C.prec = {}
    hdr = C.prec_rows[0]
    for r in C.prec_rows[1:]:
        e = by_header(r, hdr)
        C.prec[(e["suite"], e["field"], e["source_1"], e["source_2"])] = e["winner"]


# ---------------------------------------------------------------------------------
# reconciliation of result rows
# ---------------------------------------------------------------------------------
FIELDS_OF = {"arith": ["answer"], "intent": ["label"], "safety": ["score"], "mcq": ["option", "conf"],
             "longctx": ["answer"], "multiling": ["answer"], "code": ["passed"], "pref": ["verdict"]}
PRODUCTION = ["results_fleet_a.log", "results_fleet_b.log", "results_fleet_c.log", "code_samples.jsonl", "judge_verdicts.jsonl",
              "scores_shard1.parquet", "scores_shard2.parquet", "eval_store.db", "legacy_results.txt", "intent_predictions.csv",
              "rerun_results.jsonl", "scores_staging.parquet"]
AUDITED = PRODUCTION + ["eval_store_mirror.db", "judge_verdicts_rescored.jsonl"]


def reconcile(all_recs):
    reversed_ = {(r["src"], r["rev_target"]) for r in all_recs if r.get("rev_target")}
    voids = C.void_rows | C.mirror_void
    best = {}
    for r in all_recs:
        r["valid"] = False
        if r.get("fk") or r.get("rev_target") or r["src"] not in PRODUCTION:
            continue
        j = r["job"]
        if C.disp.get(j) != "authoritative":
            continue
        p, c = C.route.get(j, ("-", "-"))
        if j in C.restore:
            allowed = {"scores_staging.parquet"}
        else:
            allowed = {p, c} - {"-", "scores_staging.parquet"}
        if r["src"] not in allowed:
            continue
        if (r["src"], r["rid"]) in voids or (r["src"], r["rid"]) in reversed_ or r.get("sentinel") or r.get("shadow"):
            continue
        iid = r["item"]
        rec_j = C.jobs[j]
        if iid is None or r.get("misroute") or C.shard_of.get(iid, (None, None))[:2] != (rec_j["bench"], rec_j["shard"]):
            continue
        seal = C.seal.get(j)
        if seal is not None and r["t"] > seal * 1000:
            continue
        r["valid"] = True
        k = (r["src"], j, iid, r["sub"])
        if k not in best or r["t"] >= best[k]["t"]:
            best[k] = r
    by_key = {}
    for (src, j, iid, sub), r in best.items():
        by_key.setdefault((j, iid, sub), {})[src] = r
    C.resolved = {}
    for (j, iid, sub), srcs in by_key.items():
        b = C.jobs[j]["bench"]
        vals = {}
        for f in FIELDS_OF[b]:
            if len(srcs) == 1:
                win = next(iter(srcs))
            else:
                a, c = sorted(srcs)
                w = None
                for (suite, field, s1, s2), winner in C.prec.items():
                    if suite == b and field == f and {s1, s2} == {a, c}:
                        w = winner
                if C.jclass.get(j) == "bridge":
                    w = c if w == a else a
                win = w
            vals[f] = srcs[win]["vals"][f]
            srcs[win]["used"] = True
        C.resolved[(j, iid, sub)] = vals
    # final reviews replace judge verdicts
    for (j, iid, order), outcome in C.review.items():
        k = (j, iid, order)
        if k in C.resolved and k in by_key and "judge_verdicts.jsonl" in by_key[k]:
            C.resolved[k]["outcome"] = outcome
            by_key[k]["judge_verdicts.jsonl"]["used"] = False
    C.by_key = by_key


def norm_answer(s, grader):
    s = unicodedata.normalize("NFC", s).casefold()
    if grader == "g3":
        s = unicodedata.normalize("NFC", "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn"))
    s = " ".join(s.split())
    return s.strip(" .,;:!?\"'")


def arith_ok(a, iid):
    if a is None:
        return 0
    g = Decimal(C.gold[iid])
    tol = C.params[iid]["tol"]
    if tol == "exact":
        return int(a == g)
    if tol == "abs":
        return int(abs(a - g) <= Decimal("0.01"))
    return int(abs(a - g) <= abs(g) / 100)


# ---------------------------------------------------------------------------------
# certified outputs
# ---------------------------------------------------------------------------------
def passk(n, c, k):
    if n - c < k:
        return Fraction(1)
    return 1 - Fraction(math.comb(n - c, k), math.comb(n, k))


def auroc(pairs):
    pos = [s for s, y in pairs if y == 1]
    neg = [s for s, y in pairs if y == 0]
    if not pos or not neg:
        return Fraction(1, 2)
    acc = Fraction(0)
    negs = sorted(neg)
    import bisect
    for s in pos:
        lo = bisect.bisect_left(negs, s)
        hi = bisect.bisect_right(negs, s)
        acc += lo + Fraction(hi - lo, 2)
    return acc / (len(pos) * len(neg))


def ece_bins(rows):
    rows = sorted(rows, key=lambda x: (x[0], x[2]))
    n = len(rows)
    base, extra = divmod(n, 10)
    pos, e, bins = 0, Fraction(0), []
    for bi in range(10):
        sz = base + (1 if bi < extra else 0)
        ch = rows[pos:pos + sz]
        pos += sz
        if not ch:
            bins.append({"count": 0, "mean_confidence": None, "accuracy": None})
            continue
        mc = sum((Fraction(c) for c, _, _ in ch), Fraction(0)) / sz
        ac = Fraction(sum(y for _, y, _ in ch), sz)
        e += Fraction(sz, n) * abs(ac - mc)
        bins.append({"count": sz, "mean_confidence": q6(mc), "accuracy": q6(ac)})
    return e, bins


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return Fraction(1)
    return min(Fraction(1), Fraction(2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)), 2 ** n))


def load_baseline(dd):
    rows = []
    for hdr, r in header_walk(csv_rows(os.path.join(dd, "baseline_reference.csv")), {"ref"}):
        e = by_header(r, hdr)
        ref = clean(e["ref"])
        lc = cid_lc(ref)
        iid = C.code_item.get(lc) if lc else cid_item(ref)
        if iid not in C.items:
            continue
        if e["status"].strip() == "withdrawn":
            continue
        rv = date_any(e["revised"])
        if (iid, rv - rv % 86400) in C.void_base or (iid, rv) in C.void_base:
            continue
        loc = "de_DE" if rv < ts_utc(2025, 8, 1) else "en_US"
        rows.append((iid, rv, (e["suite"].strip(), e["value"], e["confidence"], loc)))
    C.base = {}
    for iid, (suite, v, cf, loc) in latest(rows).items():
        b = C.bench[iid]
        if b == "arith":
            C.base[iid] = {"answer": None if v.strip() == "N/A" else parse_num(v, loc).quantize(Decimal("0.01"))}
        elif b == "code":
            C.base[iid] = {"c": int(v)}
        elif b == "intent":
            C.base[iid] = {"label": v.strip()}
        elif b == "safety":
            C.base[iid] = {"score": parse_num(v, loc).quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)}
        elif b == "mcq":
            C.base[iid] = {"option": v.strip(), "conf": parse_num(cf, loc).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)}
        else:
            C.base[iid] = {"answer": v}


def compute_outputs(dd):
    out = {}
    out["lineage.json"] = {a: C.lineage[a] for a in sorted(C.lineage)}
    rows = []
    for j in sorted(C.jobs):
        rec_j = C.jobs[j]
        rows.append({"job_id": j, "model": rec_j["model"], "benchmark": rec_j["bench"], "shard": rec_j["shard"],
                     "checkpoint": rec_j["ckpt"], "host": rec_j["host"], "submitted_at": iso_z(C.submit[j] // 1000),
                     "disposition": C.disp[j]})
    out["job_dispositions.jsonl"] = rows
    out["item_eligibility.jsonl"] = [{"item_id": i, "benchmark": C.bench[i], "eligible": C.elig[i] is None, "reason": C.elig[i]}
                                     for i in sorted(C.items)]
    auth = {}
    for j, d in C.disp.items():
        if d == "authoritative":
            r = C.jobs[j]
            auth[(r["model"], r["bench"], r["shard"])] = j
    cands = sorted(C.models)
    per = {}
    scores = []
    for m in cands:
        for b in FIELDS_OF:
            lst = []
            for iid in sorted(i for i in C.items if C.bench[i] == b and C.elig[i] is None):
                j = auth[(m, b, C.shard_of[iid][1])]
                h = C.harness[j]
                grader = "g3" if h == "h4.0" else "g2"
                taxo = "v2" if h == "h4.0" else "v1"
                conf = corr = None
                if b == "code":
                    tests = C.params[iid]["tests"]
                    value = sum(1 for s in range(10) if C.resolved[(j, iid, s)]["passed"] == tests)
                elif b == "pref":
                    o = {}
                    for order in ("AB", "BA"):
                        v = C.resolved[(j, iid, order)]
                        if "outcome" in v:
                            o[order] = v["outcome"]
                        else:
                            x = v["verdict"]
                            cand = "A" if order == "AB" else "B"
                            o[order] = "tie" if x == "T" else ("win" if x == cand else "loss")
                    value = "win" if o["AB"] == o["BA"] == "win" else ("loss" if o["AB"] == o["BA"] == "loss" else "tie")
                else:
                    v = C.resolved[(j, iid, 0)]
                    if b == "arith":
                        corr = arith_ok(v["answer"], iid)
                        value = None if v["answer"] is None else format(v["answer"], "f")
                    elif b == "intent":
                        cls = C.alias[v["label"]][0 if taxo == "v1" else 1]
                        corr = int(cls == C.gold[iid])
                        value = C.v2name[cls]
                    elif b == "safety":
                        value = float(v["score"])
                    elif b == "mcq":
                        value, conf = v["option"], float(v["conf"])
                        corr = int(value == C.gold[iid])
                    elif b == "longctx":
                        ck = C.ckpt[C.lineage[m]["checkpoint"]]
                        fits = C.tokens[iid][ck["tokenizer"]] <= ck["ctx"]
                        value = norm_answer(v["answer"], "g2")
                        corr = int(fits and value == norm_answer(C.gold[iid], "g2"))
                    else:
                        value = norm_answer(v["answer"], grader)
                        corr = int(value == norm_answer(C.gold[iid], grader))
                scores.append({"model": m, "item_id": iid, "benchmark": b, "value": value, "confidence": conf, "correct": corr})
                lst.append((iid, value, conf, corr))
            per[(m, b)] = lst
    scores.sort(key=lambda x: (x["model"], x["item_id"]))
    out["item_scores.jsonl"] = scores
    # baseline
    load_baseline(dd)
    bm = C.baseline
    bck = C.ckpt[C.lineage[bm]["checkpoint"]]
    for b in FIELDS_OF:
        if b == "pref":
            continue
        lst = []
        for iid in sorted(i for i in C.items if C.bench[i] == b and C.elig[i] is None):
            v = C.base[iid]
            if b == "code":
                lst.append((iid, v["c"], None, None))
            elif b == "safety":
                lst.append((iid, float(v["score"]), None, None))
            elif b == "mcq":
                lst.append((iid, v["option"], float(v["conf"]), int(v["option"] == C.gold[iid])))
            elif b == "arith":
                lst.append((iid, None, None, arith_ok(v["answer"], iid)))
            elif b == "intent":
                lst.append((iid, v["label"], None, int(v["label"] == C.gold[iid])))
            elif b == "longctx":
                fits = C.tokens[iid][bck["tokenizer"]] <= bck["ctx"]
                lst.append((iid, None, None, int(fits and norm_answer(v["answer"], "g2") == norm_answer(C.gold[iid], "g2"))))
            else:
                lst.append((iid, None, None, int(norm_answer(v["answer"], "g3") == norm_answer(C.gold[iid], "g3"))))
        per[(bm, b)] = lst
    models = cands + [bm]
    met, raw = {}, {}
    for m in models:
        mm = {}
        for b in FIELDS_OF:
            if b == "pref":
                continue
            lst = per[(m, b)]
            n = len(lst)
            if b in ("arith", "longctx", "mcq"):
                a = Fraction(sum(x[3] for x in lst), n)
                mm[b] = {"accuracy": q6(a), "n": n}
            elif b == "code":
                a = sum((passk(10, x[1], 1) for x in lst), Fraction(0)) / n
                mm[b] = {"pass@1": q6(a), "pass@5": q6(sum((passk(10, x[1], 5) for x in lst), Fraction(0)) / n), "n": n}
            elif b == "intent":
                gold = {x[0]: C.gold[x[0]] for x in lst}
                pred = {x[0]: (C.v1name.get(x[1], x[1]) if m != bm else x[1]) for x in lst}
                classes = sorted(set(gold.values()) | set(pred.values()))
                f1 = []
                for c in classes:
                    tp = sum(1 for i in gold if gold[i] == c and pred[i] == c)
                    fp = sum(1 for i in gold if gold[i] != c and pred[i] == c)
                    fn = sum(1 for i in gold if gold[i] == c and pred[i] != c)
                    f1.append(Fraction(2 * tp, 2 * tp + fp + fn))
                a = sum(f1, Fraction(0)) / len(f1)
                mm[b] = {"macro_f1": q6(a), "n": n}
            elif b == "safety":
                a = auroc([(Fraction(Decimal(repr(x[1]))), int(C.gold[x[0]])) for x in lst])
                mm[b] = {"auroc": q6(a), "n": n}
            else:
                byl = {}
                for x in lst:
                    byl.setdefault(C.lang[x[0]], []).append(x[3])
                langs = sorted(l for l, v in byl.items() if len(v) >= C.lang_min_support)
                a = sum((Fraction(sum(byl[l]), len(byl[l])) for l in langs), Fraction(0)) / len(langs)
                mm[b] = {"macro_accuracy": q6(a), "n": n, "languages": len(langs)}
            raw[(m, b)] = a
        met[m] = mm
    out["benchmark_metrics.json"] = met
    cal, ece = {}, {}
    for m in models:
        e, bins = ece_bins([(Fraction(Decimal(repr(x[2]))), x[3], x[0]) for x in per[(m, "mcq")]])
        ece[m] = e
        if m != bm:
            cal[m] = {"ece": q6(e), "bins": bins}
    out["calibration.json"] = cal
    pw = {}
    for m in cands:
        vals = [x[1] for x in per[(m, "pref")]]
        w, t, l = vals.count("win"), vals.count("tie"), vals.count("loss")
        raw[(m, "pref")] = Fraction(2 * w + t, 2 * len(vals))
        pw[m] = {"wins": w, "ties": t, "losses": l, "win_rate": q6(raw[(m, "pref")])}
    raw[(bm, "pref")] = Fraction(1, 2)
    out["pairwise.json"] = pw
    gated = ["arith", "mcq", "longctx", "multiling"]
    sig = {}
    for m in cands:
        sm = {}
        for b in gated:
            bc = {x[0]: x[3] for x in per[(bm, b)]}
            bb = sum(1 for x in per[(m, b)] if x[3] == 1 and bc[x[0]] == 0)
            cc = sum(1 for x in per[(m, b)] if x[3] == 0 and bc[x[0]] == 1)
            p = mcnemar(bb, cc)
            dec = "no_change"
            if p < C.alpha:
                dec = "improved" if bb > cc else ("regressed" if cc > bb else "no_change")
            sm[b] = {"b": bb, "c": cc, "p_value": q6(p), "decision": dec}
        sig[m] = sm
    out["significance.json"] = sig
    mcq_items = [x[0] for x in per[(cands[0], "mcq")]]
    chance = {"arith": Fraction(0), "code": Fraction(0), "intent": Fraction(1, len(C.v2name)), "safety": Fraction(1, 2),
              "pref": Fraction(1, 2), "longctx": Fraction(0), "multiling": Fraction(0),
              "mcq": sum((Fraction(1, C.params[i]["nopt"]) for i in mcq_items), Fraction(0)) / len(mcq_items)}
    order = ["arith", "code", "intent", "safety", "mcq", "pref", "longctx", "multiling"]
    agg, lb = {}, []
    for m in models:
        norms = {b: (raw[(m, b)] - chance[b]) / (1 - chance[b]) for b in order}
        ws = sum((Fraction(C.weights[b]) for b in order), Fraction(0))
        a = sum((Fraction(C.weights[b]) * norms[b] for b in order), Fraction(0)) / ws
        agg[m] = a
        lb.append((m, a, raw[(m, "code")], norms))
    lb.sort(key=lambda x: (-x[1], -x[2], x[0]))
    out["leaderboard.csv"] = [{"rank": i + 1, "model": m, "aggregate": q6(a), **{b: q6(n[b]) for b in order}} for i, (m, a, _p, n) in enumerate(lb)]
    gates = {}
    for m in cands:
        g = {"aggregate_vs_baseline": agg[m] >= agg[bm],
             "no_regression": all(sig[m][b]["decision"] != "regressed" for b in gated),
             "ece_within_cap": ece[m] <= Fraction(C.ece_cap),
             "safety_floor": raw[(m, "safety")] >= Fraction(C.auroc_floor)}
        g["release"] = all(g.values())
        gates[m] = g
    out["release_gates.json"] = gates
    sl = {}
    for m in cands:
        sm = {}
        for b in gated:
            bmap = {}
            for nm, conds in C.slices:
                vals = []
                for iid, _v, _c, corr in per[(m, b)]:
                    at = {"domain": C.attrs[iid]["domain"], "difficulty": C.attrs[iid]["difficulty"], "region": C.region.get(iid)}
                    if all(at[f] in allowed for f, allowed in conds):
                        vals.append(corr)
                bmap[nm] = q6(Fraction(sum(vals), len(vals))) if len(vals) >= C.min_support else None
            sm[b] = bmap
        sl[m] = sm
    out["slice_metrics.json"] = sl
    # source audit
    sa = {}
    for src in AUDITED:
        rs = [r for r in C.recs if r["src"] == src and not r.get("rev_target")]
        used = sum(1 for r in rs if r.get("used") and C.elig.get(r["item"]) is None)
        sa[src] = {"result_rows": len(rs), "used": used, "discarded": len(rs) - used}
    out["source_audit.json"] = sa
    # control reconciliation
    exp = {}
    for tab in C.ctl_tables:
        hdr = [h.strip() for h in tab[0]]
        rows_ = []
        for r in tab[1:]:
            e = by_header([unq(x.strip()) for x in r], hdr)
            j = cid_job(e["job"])
            rv = rev_int(unq(e["revision"]))
            if voided("control_totals.html", j, rv):
                continue
            rows_.append((j, rv, int(clean(e["expected_rows"]).split()[0])))
        for k, v in latest(rows_).items():
            exp[k] = v
    cr, tot = {}, {"authoritative_jobs": 0, "scored_items": 0, "expected_results": 0}
    for m in cands:
        aj = [j for j, d in C.disp.items() if d == "authoritative" and C.jobs[j]["model"] == m]
        rec_m = {"authoritative_jobs": len(aj), "scored_items": sum(1 for x in scores if x["model"] == m),
                 "expected_results": sum(exp[j] for j in aj)}
        cr[m] = rec_m
        for k in tot:
            tot[k] += rec_m[k]
    cr["_total"] = tot
    out["control_reconciliation.json"] = cr
    return out


def write_outputs(out, od):
    os.makedirs(od, exist_ok=True)
    for name, val in out.items():
        path = os.path.join(od, name)
        if name.endswith(".jsonl"):
            text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n" for r in val)
        elif name.endswith(".csv"):
            cols = ["rank", "model", "aggregate", "arith", "code", "intent", "safety", "mcq", "pref", "longctx", "multiling"]
            lines = [",".join(cols)]
            for r in val:
                lines.append(",".join([str(r["rank"]), r["model"]] + [f"{r[c]:.6f}" for c in cols[2:]]))
            text = "\n".join(lines) + "\n"
        else:
            text = json.dumps(val, ensure_ascii=False, indent=2) + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def main(argv):
    if len(argv) < 3:
        # reference run: install the program next to its outputs and certify the shipped corpus
        import shutil
        here = os.path.abspath(__file__)
        os.makedirs("/app/out", exist_ok=True)
        shutil.copyfile(here, "/app/out/certify.py")
        argv = [argv[0], "/app/data", "/app/out"]
    dd, od = argv[1], argv[2]
    C.files = sorted(os.listdir(dd))
    load_documents(dd)
    load_errata(dd)
    load_hosts(dd)
    load_maintenance(dd)
    load_lineage(dd)
    load_mail(dd)
    load_jobs(dd)
    load_tags(dd, C.models + [C.baseline])
    resolve_job_checkpoints()
    load_events(dd)
    load_minutes(dd)
    dispositions()
    load_items(dd)
    load_presentation(dd)
    load_reviews(dd)
    load_routing()
    recs = []
    for name in ("results_fleet_a.log", "results_fleet_b.log", "results_fleet_c.log"):
        recs += parse_logs(dd, name)
    recs += parse_code(dd)
    recs += parse_judge(dd)
    for name in ("scores_shard1.parquet", "scores_shard2.parquet", "scores_staging.parquet"):
        recs += parse_parquet(dd, name)
    C.mirror_void = set()
    recs += parse_store(dd, "eval_store_mirror.db")
    recs += parse_store(dd, "eval_store.db")
    recs += parse_legacy(dd)
    recs += parse_intent_csv(dd)
    recs += parse_rerun(dd)
    for ln in read_text_lines(os.path.join(dd, "judge_verdicts_rescored.jsonl")):
        o = json.loads(ln)
        recs.append(rec("judge_verdicts_rescored.jsonl", o["rid"], None, cid_item(o["item"]), 0, 0, {}))
    C.recs = recs
    reconcile(recs)
    write_outputs(compute_outputs(dd), od)


if __name__ == "__main__":
    main(sys.argv)
