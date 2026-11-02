#!/usr/bin/env python3
"""October 2025 build-minute close for the Kestrel CI fleets.

Usage: settle.py [DATA_DIR] [OUT_DIR]   (defaults /app/data and /app/out)

Reads every export in DATA_DIR, applies the written settlement rules found in
the documents of that directory, and writes the close artifacts to OUT_DIR.
Standard library only; output is byte-deterministic.
"""
import configparser
import csv
import gzip
import io
import json
import os
import re
import sqlite3
import sys
import tomllib
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import datetime, timezone
from fractions import Fraction
from html.parser import HTMLParser

UTC = timezone.utc
CONTROL_BLOCK = 50

# column kinds per file, read from the source catalog and the column semantics
KINDS = {
    "fleet_policy.ini": {"runner": "key", "rev": "int", "effective_from": "ts", "sku": "key"},
    "instance_classes.csv": {"sku": "key", "listed_at": "ts"},
    "rate_methodology.pdf": {"sku": "key", "granularity_s": "int"},
    "settlement_authority.md": {"runner": "key", "rev": "int"},
    "clock_sync.txt": {"runner": "key", "window_from": "ts", "window_to": "ts", "skew_ms": "int"},
    "change_freeze.ics": {"sequence": "int", "dtstart": "ts", "dtend": "ts", "runner": "key"},
    "close_parameters.toml": {"runner": "key", "day": "ts"},
    "fleet_north.log": {"ts": "ts", "attempt": "key", "job": "key", "no": "int", "runner": "key",
                        "mono_start": "dur", "mono_end": "dur", "wall_end": "ts"},
    "attempt_events.jsonl": {"attempt_id": "key", "job_id": "key", "attempt": "int", "runner": "key",
                             "started": "ts", "duration_ms": "dur"},
    "usage_events.jsonl": {"attempt": "key", "job": "key", "seq": "int", "runner": "key", "start": "ts",
                           "elapsed": "dur", "received": "ts"},
    "junit_results.xml": {"attempt": "key", "time": "dur"},
    "errata_register.docx": {"attempt": "key", "filed": "ts"},
    "approval_thread.mbox": {"decided_at": "ts"},
    "invoice_lines.xlsx": {"line_id": "key", "runner": "key", "week_start": "ts", "billed": "money"},
    "vendor_statement.xml": {"line": "key", "credit": "money", "runner": "key"},
    "rate_card.xlsx": {"effective_from": "ts", "recorded_at": "ts", "micro_per_min": "money"},
    "package_metadata.xml": {"manifest_bytes": "bytes"},
    "targets.csv": {"registered_at": "ts"},
    "toolchain_pins.yaml": {"pinned_at": "ts"},
    "edges.csv": {"declared_at": "ts"},
    "action_keys.lock": {"action": "key", "recorded": "ts"},
    "input_manifests.tsv": {"action": "key", "size": "bytes"},
    "env_allowlist.json": {"action": "key", "observed": "ts"},
    "shard_index.tsv": {"prefix": "key", "shard": "int", "assigned_at": "ts"},
    "lookups_shard1.jsonl": {"lookup": "key", "attempt": "key", "action": "key", "at": "ts", "bytes": "bytes"},
    "evictions.log": {"ts": "ts", "shard": "int", "action": "key", "eviction": "key"},
    "artifact_registry.db": {"artifact": "key", "bytes": "bytes", "created": "ts"},
    "gc_events.csv": {"artifact": "key", "at": "ts"},
    "flaky_windows.tsv": {"from": "ts", "until": "ts"},
    "amendment_minutes.docx": {"job": "key", "ratified_on": "ts"},
    "retry_policy.yaml": {"job": "key", "budget": "int"},
    "scope_rules.md": {"reviewed": "ts"},
    "field_precedence.html": {"job": "key", "opened": "ts"},
    "owners_registry.txt": {"seq": "int"},
    "team_roster.xlsx": {"effective_from": "ts"},
    "cost_centers.csv": {"cost_center": "key", "effective_from": "ts"},
    "opening_balances.json": {"cost_center": "key", "amount": "money"},
    "settlement_ledger.db": {"posting": "key", "cost_center": "key", "amount": "money", "posted_at": "ts"},
    "attempt_events_v3.jsonl": {"attempt_id": "key", "job_id": "key", "runner": "key", "started_utc": "ts",
                                "duration_ms": "dur"},
    "usage_export_legacy.log": {"ts": "ts", "attempt": "key", "runner": "key", "elapsed": "dur"},
    "lookups_archive.jsonl.gz": {"id": "key", "action": "key", "at": "ts"},
    "toolchain_pins_resolved.json": {"resolved_at": "ts"},
    "ownership_patterns_approved.tsv": {"effective": "ts"},
    "rate_card_final.xlsx": {"effective_from": "ts", "micro_per_min": "money"},
    "invoice_restatement.csv": {"line_id": "key", "restated": "money"},
    "audit_annex.pdf": {"block": "int", "records": "int", "control_sum": "int"},
    "control_totals_draft.html": {"block": "int", "records": "int", "control_sum": "int"},
}
KINDS["fleet_south.log"] = KINDS["fleet_north.log"]
KINDS["lookups_shard2.jsonl"] = KINDS["lookups_shard1.jsonl"]
KINDS["lookups_shard3.jsonl.gz"] = KINDS["lookups_shard1.jsonl"]
FACE = {"ts": "iso_z", "dur": "ms", "money": "usd6", "int": "plain", "bytes": "plain", "key": "exact"}
STRUCT = {"flag", "note", "batch"}


# ------------------------------------------------------------------ text helpers
def lines_of(data):
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    out = []
    for raw in data.split(b"\n"):
        try:
            out.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(raw.decode("latin-1"))
    if out and out[-1] == "":
        out.pop()
    return out


def parse_kv(text):
    out = {}
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] == " ":
            i += 1
        if i >= n:
            break
        j = text.index("=", i)
        key = text[i:j]
        i = j + 1
        if i < n and text[i] == '"':
            i += 1
            buf = []
            while text[i] != '"':
                if text[i] == "\\":
                    i += 1
                buf.append(text[i])
                i += 1
            i += 1
            out[key] = "".join(buf)
        else:
            j = text.find(" ", i)
            j = n if j < 0 else j
            out[key] = text[i:j]
            i = j
    return out


# ------------------------------------------------------------------ readers
def read_delim(data, sep):
    text = "\n".join(lines_of(data))
    header, rows = None, []
    for cells in csv.reader(io.StringIO(text), delimiter=sep, quotechar='"' if sep == "," else "\x00"):
        if not cells:
            continue
        if header is None or (len(cells) == len(header) and set(cells) == set(header)) or \
                (set(cells) >= {"flag", "note"} and len(set(cells) & set(header)) >= len(header) - 1 and cells[-2:] == ["flag", "note"]):
            header = cells
            continue
        rows.append(dict(zip(header, cells + [""] * (len(header) - len(cells)))))
    return {"records": rows}


def read_jsonl(data):
    return {"records": [json.loads(ln) for ln in lines_of(data) if ln.strip()]}


def read_json(data):
    obj = json.loads(data.decode("utf-8"))
    return {k: v for k, v in obj.items() if isinstance(v, list)}


def read_xml(data):
    root = ET.fromstring(data)
    out = {}
    for el in root:
        out.setdefault(el.tag, []).append(dict(el.attrib))
    return out


def read_log(data):
    rows = []
    for ln in lines_of(data):
        if not ln.strip() or ln.startswith("#"):
            continue
        _lvl, _comp, rest = ln.split(" ", 2)
        rows.append(parse_kv(rest))
    return {"records": rows}


def read_lock(data):
    return {"records": [parse_kv(ln) for ln in lines_of(data) if ln.strip() and not ln.startswith("#")]}


def _flow_map(s):
    s = s.strip()
    assert s.startswith("{") and s.endswith("}")
    s = s[1:-1]
    out, i, dec = {}, 0, json.JSONDecoder()
    while i < len(s):
        while s[i] in ", ":
            i += 1
        j = s.index(": ", i)
        key = s[i:j]
        val, end = dec.raw_decode(s, j + 2)
        out[key] = val
        i = end
    return out


def read_yaml(data):
    out, cur = {}, None
    for ln in lines_of(data):
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if not ln.startswith(" "):
            cur = ln.rstrip(":")
            out[cur] = []
        else:
            out[cur].append(_flow_map(ln.strip()[2:]))
    return out


def read_toml(data):
    obj = tomllib.loads("\n".join(lines_of(data)))
    params = {k: v for k, v in obj.items() if not isinstance(v, list)}
    out = {k: v for k, v in obj.items() if isinstance(v, list)}
    out["params"] = [{"key": k, "value": v} for k, v in params.items()]
    return out


def read_ini(data):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read_string("\n".join(ln for ln in lines_of(data) if not ln.startswith(";")))
    return {"runner": [dict(cp[s]) for s in cp.sections()]}


def read_txt(data, layouts):
    rows, cols = [], None
    for ln in lines_of(data):
        if ln.startswith("H"):
            cols = layouts[ln[1:].strip()]
        elif ln.startswith("D"):
            pos, rec = 1, {}
            for name, width in cols:
                rec[name] = ln[pos:pos + width].strip()
                pos += width
            rows.append(rec)
    return {"records": rows}


def read_mbox(data):
    rows, cur, body = [], None, False
    for ln in lines_of(data):
        if ln.startswith("From approvals@"):
            if cur is not None:
                rows.append(cur)
            cur, body = {}, False
            continue
        if cur is None:
            continue
        if not ln.strip():
            body = True
            continue
        key, _, val = ln.partition(": ")
        if not body:
            if key == "Message-ID":
                cur["mid"] = val.strip("<>")
            continue
        cur[key.lower().replace("-", "_")] = val
    if cur is not None:
        rows.append(cur)
    return {"message": rows}


ICS_KEYS = {"UID": "uid", "SEQUENCE": "sequence", "STATUS": "status", "X-RUNNER": "runner",
            "X-REVIEW-FLAG": "flag", "COMMENT": "note"}


def read_ics(data):
    rows, cur = [], None
    for ln in lines_of(data):
        if ln == "BEGIN:VEVENT":
            cur = {}
        elif ln == "END:VEVENT":
            rows.append(cur)
            cur = None
        elif cur is not None:
            k, _, v = ln.partition(":")
            cur[ICS_KEYS.get(k, k[2:].lower().replace("-", "_") if k.startswith("X-") else k.lower())] = v
    return {"VEVENT": rows}


XNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def read_xlsx(data):
    out = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels}
        for sh in wb.iter(XNS + "sheet"):
            root = ET.fromstring(z.read("xl/" + target[sh.get(RNS + "id")]))
            rows = []
            for row in root.iter(XNS + "row"):
                vals = []
                for c in row.iter(XNS + "c"):
                    if c.get("t") == "inlineStr":
                        vals.append("".join(t.text or "" for t in c.iter(XNS + "t")))
                    else:
                        v = c.find(XNS + "v")
                        vals.append(("num", v.text) if v is not None else "")
                rows.append(vals)
            header = rows[0]
            out[sh.get("name")] = [dict(zip(header, r)) for r in rows[1:]]
    return out


def read_db(data):
    con = sqlite3.connect(":memory:")
    con.deserialize(data)
    out = {}
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid"):
        cur = con.execute(f'SELECT * FROM "{name}" ORDER BY rowid')
        cols = [c[0] for c in cur.description]
        out[name] = [dict(zip(cols, r)) for r in cur]
    con.close()
    return out


def _md_cells(line):
    s = line.strip()[1:-1]
    cells, buf, i = [], "", 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf += "|"
            i += 2
            continue
        if s[i] == "|":
            cells.append(buf.strip())
            buf = ""
        else:
            buf += s[i]
        i += 1
    cells.append(buf.strip())
    return cells


def read_md(data):
    lines = lines_of(data)
    out, i = {}, 0
    while i < len(lines):
        m = re.fullmatch(r"\*\*Table: (.+)\*\*", lines[i].strip())
        if not m:
            i += 1
            continue
        i += 2
        header = _md_cells(lines[i])
        i += 2
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            rows.append(dict(zip(header, _md_cells(lines[i]))))
            i += 1
        out[m.group(1)] = rows
    return out


class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.rows, self.row, self.cell, self.cap, self.in_cap = {}, None, None, None, "", False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.rows, self.cap = [], ""
        elif tag == "caption":
            self.in_cap = True
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = ""

    def handle_endtag(self, tag):
        if tag == "caption":
            self.in_cap = False
        elif tag in ("td", "th"):
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr":
            self.rows.append(self.row)
        elif tag == "table":
            self.tables[self.cap] = [dict(zip(self.rows[0], r)) for r in self.rows[1:]]

    def handle_data(self, d):
        if self.in_cap:
            self.cap += d
        elif self.cell is not None:
            self.cell += d


def read_html(data):
    p = _Html()
    p.feed(data.decode("utf-8"))
    return p.tables


WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_docx(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(WNS + "body")
    out, cap = {}, None
    for el in body:
        if el.tag == WNS + "p":
            t = "".join(x.text or "" for x in el.iter(WNS + "t"))
            if t.startswith("Table: "):
                cap = t[7:]
        elif el.tag == WNS + "tbl":
            rows = [["".join(x.text or "" for x in tc.iter(WNS + "t")) for tc in tr.iter(WNS + "tc")]
                    for tr in el.iter(WNS + "tr")]
            out[cap] = [dict(zip(rows[0], r)) for r in rows[1:]]
    return out


def _pdf_lines(data):
    lines = []
    raw = data.decode("latin-1")
    for m in re.finditer(r"stream\n(.*?)\nendstream", raw, re.S):
        text = zlib.decompress(m.group(1).encode("latin-1")).decode("latin-1")
        for sm in re.finditer(r"\(((?:[^\\)]|\\.)*)\) Tj", text):
            lines.append(re.sub(r"\\(.)", r"\1", sm.group(1)))
    return lines


def read_pdf(data):
    lines = _pdf_lines(data)
    out, i = {}, 0
    while i < len(lines):
        if not lines[i].startswith("Table: "):
            i += 1
            continue
        name = lines[i][7:]
        header = lines[i + 1].split(" | ")
        i += 2
        rows = []
        while i < len(lines) and lines[i] != "":
            rows.append(dict(zip(header, lines[i].split(" | "))))
            i += 1
        out[name] = rows
    return out


READERS = {"csv": lambda d: read_delim(d, ","), "tsv": lambda d: read_delim(d, "\t"), "jsonl": read_jsonl,
           "json": read_json, "xml": read_xml, "log": read_log, "lock": read_lock, "yaml": read_yaml,
           "toml": read_toml, "ini": read_ini, "mbox": read_mbox, "ics": read_ics, "xlsx": read_xlsx,
           "db": read_db, "md": read_md, "html": read_html, "docx": read_docx, "pdf": read_pdf}


# ------------------------------------------------------------------ decoding
def ts_iso(s):
    return int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp())


def iso(t):
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Zones:
    def __init__(self, rules):
        self.rules = rules   # zone -> list of (until, offset_min) segments

    def off(self, zone, t):
        for until, off in self.rules[zone]:
            if until is None or t < until:
                return off

    def local_to_utc(self, zone, text):
        fold = text.endswith("+fold")
        naive = ts_iso(text.replace("+fold", "").replace(" ", "T") + "Z")
        offs = sorted({o for _, o in self.rules[zone]})
        cands = sorted(naive - o * 60 for o in offs if self.off(zone, naive - o * 60) == o)
        if not cands:
            return naive - self.off(zone, naive - 86400) * 60
        return cands[-1] if fold else cands[0]


def parse_zone_rules(prose):
    """Read the Clock zones paragraph of rate_methodology.pdf."""
    text = " ".join(prose)
    rules = {}
    for zone, body in re.findall(r"([A-Z]{2}[+-][\d:]+) is (UTC[^;.]*(?:\.\d+:\d+:\d+Z)?[^;]*)", text):
        segs = []
        for part in re.split(r" and ", body):
            m = re.match(r"UTC([+-]\d+)(?::(\d+))?(?: until (\S+))?(?: after)?", part.strip())
            if not m:
                continue
            h, mm = int(m.group(1)), int(m.group(2) or 0)
            off = h * 60 + (mm if h >= 0 else -mm)
            until = ts_iso(m.group(3)) if m.group(3) else None
            segs.append((until, off))
        rules[zone] = segs
    return rules


def dec(kind, codec, s, zone, zones):
    if isinstance(s, tuple):            # spreadsheet numeric cell
        s = s[1]
    s = str(s)
    if kind == "key":
        return s.strip().lower()
    if kind == "ts":
        if s == "":
            return None
        if codec == "iso_z":
            return ts_iso(s)
        if codec == "epoch":
            return int(s)
        if codec == "epoch_ms":
            return int(s) // 1000
        if codec == "utc_naive":
            return ts_iso(s.replace(" ", "T") + "Z")
        if codec == "local":
            return zones.local_to_utc(zone, s)
        if codec == "iso_off":
            sign = 1 if s[-6] == "+" else -1
            off = sign * (int(s[-5:-3]) * 60 + int(s[-2:]))
            return ts_iso(s[:-6] + "Z") - off * 60
        if codec == "xl1900":
            return round(Fraction(s) * 86400) - 2209161600
    if kind == "dur":
        if codec == "ms":
            return int(s)
        if codec == "us":
            return int(s) // 1000
        if codec == "ns":
            return int(s) // 1000000
        if codec == "s3":
            a, b = s.split(".")
            return int(a) * 1000 + int(b)
    if kind == "money":
        neg = s.startswith("-")
        s = s.lstrip("-")
        if codec == "usd6":
            a, b = s.split(".")
            v = int(a) * 10 ** 6 + int(b)
        elif codec == "micro":
            v = int(s)
        elif codec == "eu6":
            a, b = s.split(",")
            v = int(a.replace(".", "")) * 10 ** 6 + int(b)
        elif codec == "kusd9":
            a, b = s.split(".")
            v = int(a) * 10 ** 9 + int(b)
        return -v if neg else v
    if kind in ("int", "bytes"):
        if codec == "plain":
            return int(s)
        if codec == "sep":
            return int(s.replace(",", ""))
        if codec == "eu":
            return int(s.replace(".", ""))
        if codec == "kib":
            return int(s) * 1024
    raise ValueError((kind, codec, s))


# ------------------------------------------------------------------ the close
class Close:
    def __init__(self, data_dir):
        self.dir = data_dir
        self.raw = {}
        names = sorted(os.listdir(data_dir))
        for name in names:
            if name.endswith(".txt"):
                continue
            ext = "jsonl" if name.endswith(".jsonl.gz") else name.rsplit(".", 1)[1]
            data = open(os.path.join(data_dir, name), "rb").read()
            if name.endswith(".gz"):
                data = gzip.decompress(data)
            self.raw[name] = READERS[ext](data)
        self.docs = {n: t for n, t in self.raw.items() if n.rsplit(".", 1)[-1] in ("md", "html", "docx", "pdf")}
        self.layouts = {}
        for row in self.table_all("Fixed-width layouts"):
            self.layouts.setdefault((row["file"], row["layout"]), []).append((int(row["position"]), row["column"], int(row["width"])))
        for name in names:
            if name.endswith(".txt"):
                lay = {lid: [(c, wd) for _, c, wd in sorted(v)] for (f, lid), v in self.layouts.items() if f == name}
                self.raw[name] = read_txt(open(os.path.join(data_dir, name), "rb").read(), lay)
        self.conv = {}
        for row in self.table_all("Field conventions"):
            self.conv[(row["file"], row["column"], row["value"])] = row["codec"]
        self.ctxdim = {}
        for row in self.table_all("Field conventions"):
            self.ctxdim[(row["file"], row["column"])] = row["context"]
        self.alias = {}
        for row in self.table_all("Column aliases"):
            if row["file"] != "none":
                self.alias[row["file"]] = (row["alias"], row["column"])
        self.catalog = {r["file"]: r for r in self.table_all("Source catalog")}
        self.zone_of_region = {r["region"]: r["zone"] for r in self.table_all("Region zones")}
        meth = self.raw["rate_methodology.pdf"]
        prose = [ln for ln in _pdf_lines(open(os.path.join(data_dir, "rate_methodology.pdf"), "rb").read())]
        self.zones = Zones(parse_zone_rules(prose))

    def table_all(self, name):
        rows = []
        for doc in sorted(self.docs):
            rows.extend(self.docs[doc].get(name, []))
        return rows

    def primary(self, name):
        tabs = self.raw[name]
        t = self.catalog[name]["primary table"]
        rows = list(tabs.get(t, []))
        for cont in (t + " (cont)", t + " (continued)", t + "_cont"):
            rows += tabs.get(cont, [])
        if name in self.alias:
            al, col = self.alias[name]
            rows = [{(col if k == al else k): v for k, v in r.items()} for r in rows]
        return rows

    def decoded(self, name, ctxfn, zonefn=None):
        """Primary rows with re-exports removed; coded columns decoded."""
        kinds = KINDS[name]
        seen, out, allrows = set(), [], []
        for r in self.primary(name):
            sig = tuple(sorted((k, str(v)) for k, v in r.items()))
            dup = sig in seen
            seen.add(sig)
            ctx = ctxfn(r)
            d = dict(r)
            for col, kind in kinds.items():
                if col in r:
                    codec = self.conv.get((name, col, ctx), FACE[kind])
                    if zonefn is not None:
                        zone = zonefn(r)
                    else:
                        zone = self.zone_of_region[ctx] if self.ctxdim.get((name, col)) == "region" else None
                    d[col] = dec(kind, codec, r[col], zone, self.zones)
            allrows.append((dup, d))
            if not dup:
                out.append(d)
        self._all = getattr(self, "_all", {})
        self._all[name] = allrows
        return out


def vkey(v):
    return tuple(int(x) for x in v.split("."))


def satisfies(cons, ver):
    v = vkey(ver)
    if cons.startswith("="):
        return v == vkey(cons[1:])
    if cons.startswith(">="):
        lo, hi = cons[2:].split(" <")
        return vkey(lo) <= v < vkey(hi)
    base = vkey(cons[1:])
    if v < base:
        return False
    if cons.startswith("~"):
        return v[:2] == base[:2]
    if base[0] > 0:
        return v[0] == base[0]
    if base[1] > 0:
        return v[:2] == base[:2]
    return v == base


def half_even(fr):
    fl = fr.numerator // fr.denominator
    rem = fr - fl
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and fl % 2 == 1):
        return fl + 1
    return fl


def glob_rx(pat):
    rx, i = "", 0
    while i < len(pat):
        if pat.startswith("**", i):
            rx += ".*"
            i += 2
        elif pat[i] == "*":
            rx += "[^/:]*"
            i += 1
        else:
            rx += re.escape(pat[i])
            i += 1
    return re.compile(rx)


def run(data_dir, out_dir):
    C = Close(data_dir)
    params = {r["key"]: r["value"] for r in C.raw["close_parameters.toml"]["params"]}
    P0, P1, K = ts_iso(params["period_start"]), ts_iso(params["period_end"]), ts_iso(params["knowledge_cutoff"])
    batch = lambda r: r.get("batch")
    # --- batch-context references -------------------------------------------------
    placements = C.decoded("settlement_authority.md", batch)
    runner_zone, rev_region = {}, {}
    for p in placements:
        rev_region[(p["runner"], p["rev"])] = p["region"]
        if p["rev"] == 1:
            runner_zone[p["runner"]] = p["region"]
    pkg = {r["target"]: r for r in C.decoded("package_metadata.xml", batch)}
    lang = lambda t: pkg[t]["language"]
    roster = {r["handle"]: r["team"] for r in C.decoded("team_roster.xlsx", batch)}
    transfers = {}
    for r in C.raw["team_roster.xlsx"].get("Transfers", []):
        transfers.setdefault(r["handle"], []).append((ts_iso(r["effective_from"]), r["team"]))
    org = lambda h: roster[h].split("-")[0]
    zone_r = lambda r: runner_zone[str(r["runner"]).strip().lower()]
    vendors = C.decoded("vendor_statement.xml", zone_r)
    locale = {v["vendor"]: v["locale"] for v in vendors}
    # --- runner, sku, rates -------------------------------------------------------
    revs = {}
    for r in C.decoded("fleet_policy.ini", zone_r):
        revs.setdefault(r["runner"], []).append(r)
    for v in revs.values():
        v.sort(key=lambda r: r["effective_from"])
    sku_zone = {r["sku"]: runner_zone[r["runner"]] for v in revs.values() for r in v}
    skus = {r["sku"]: r for r in C.decoded("instance_classes.csv", lambda r: sku_zone[r["sku"].strip().lower()])}
    gran = {r["sku"]: r["granularity_s"] for r in C.decoded("rate_methodology.pdf", batch)}
    region_zone = lambda r: r["region"]
    rates = {}
    for r in C.decoded("rate_card.xlsx", region_zone):
        if r["recorded_at"] <= K:
            rates.setdefault((r["instance_class"], r["region"]), []).append(r)
    rate_rows = {}
    for key, rows in rates.items():
        best = {}
        for r in sorted(rows, key=lambda r: (r["effective_from"], r["recorded_at"])):
            best[r["effective_from"]] = r
        rate_rows[key] = [best[e] for e in sorted(best)]
    C.decoded("rate_card_final.xlsx", region_zone)
    spot_credit = {r["instance_class"]: int(r["spot_credit_permille"]) for r in C.raw["rate_card_final.xlsx"]["Spot credits"]}
    classes = {r["class"]: int(r["multiplier_permille"]) for r in C.table_all("Billing classes")}
    reserved_permille = int(params["reserved_permille"])
    windows = {}
    for r in C.decoded("clock_sync.txt", zone_r):
        windows.setdefault(r["runner"], []).append(r)
    reserv = {(r["runner"], iso(r["day"])[:10]) for r in C.decoded("close_parameters.toml", zone_r)}
    drains_by_uid = {}
    for r in C.decoded("change_freeze.ics", zone_r):
        cur = drains_by_uid.get(r["uid"])
        if cur is None or r["sequence"] > cur["sequence"]:
            drains_by_uid[r["uid"]] = r
    drains = {}
    for r in drains_by_uid.values():
        if r["status"] != "CANCELLED":
            drains.setdefault(r["runner"], []).append((r["dtstart"], r["dtend"]))
    # --- jobs, attempts ------------------------------------------------------------
    register = {r["job"]: r for r in C.decoded("field_precedence.html", batch)}
    job_lang = lambda r: lang(register[str(r["job"]).strip().lower()]["target"])
    grace = {r["fleet"]: int(r["grace_s"]) for r in C.raw["retry_policy.yaml"]["preemption_grace"]}
    default_budget = int({r["key"]: r["value"] for r in C.raw["retry_policy.yaml"]["defaults"]}["budget"])
    budgets = {r["job"]: r["budget"] for r in C.decoded("retry_policy.yaml", job_lang)}
    amend = {r["job"]: r["class"] for r in C.decoded("amendment_minutes.docx", job_lang) if r["ratified_on"] <= K}
    rz = lambda r: C.zone_of_region[runner_zone[str(r["runner"]).strip().lower()]]
    jl = lambda col: (lambda r: lang(register[str(r[col]).strip().lower()]["target"]))
    attempts = []
    for fleet, name in (("north", "fleet_north.log"), ("south", "fleet_south.log")):
        for r in C.decoded(name, jl("job"), rz):
            attempts.append({"id": r["attempt"], "job": r["job"], "no": r["no"], "runner": r["runner"], "fleet": fleet,
                             "status": r["status"], "rep": r["ts"], "dur": r["mono_end"] - r["mono_start"]})
    for r in C.decoded("attempt_events.jsonl", jl("job_id"), rz):
        attempts.append({"id": r["attempt_id"], "job": r["job_id"], "no": r["attempt"], "runner": r["runner"],
                         "fleet": "east", "status": r["status"], "rep": r["started"], "dur": r["duration_ms"]})
    for r in C.decoded("usage_events.jsonl", jl("job"), rz):
        attempts.append({"id": r["attempt"], "job": r["job"], "no": r["seq"], "runner": r["runner"], "fleet": "west",
                         "status": r["state"], "rep": r["start"], "dur": r["elapsed"]})
    att_by = {a["id"]: a for a in attempts}
    a_of = lambda r, col="attempt": att_by[str(r[col]).strip().lower()]
    att_lang = lambda r: lang(register[a_of(r)["job"]]["target"])
    att_zone = lambda r: C.zone_of_region[runner_zone[a_of(r)["runner"]]]
    origin = {r["attempt_id"]: r["cancel_origin"] for r in C.decoded("attempt_events_v3.jsonl", jl("job_id"), rz)}
    revoked = {r["attempt"] for r in C.decoded("usage_export_legacy.log", att_lang, rz) if r["kind"] == "REVOKE"}
    errata = {r["id"]: r for r in C.decoded("errata_register.docx", att_lang, att_zone)}
    er_att = lambda r: att_by[errata[r["erratum"]]["attempt"]]
    er_lang = lambda r: lang(register[er_att(r)["job"]]["target"])
    er_zone = lambda r: C.zone_of_region[runner_zone[er_att(r)["runner"]]]
    decisions = {}
    for m in sorted(C.decoded("approval_thread.mbox", er_lang, er_zone), key=lambda m: (m["decided_at"], m["mid"])):
        if m["decided_at"] <= K:
            decisions[m["erratum"]] = m["decision"]
    status = {a["id"]: a["status"] for a in attempts}
    for e in errata.values():
        if decisions.get(e["id"]) == "APPROVED":
            status[e["attempt"]] = e["new"]
    jcases = {}
    for r in C.decoded("junit_results.xml", att_lang):
        jcases.setdefault(r["attempt"], []).append(r["testcase"])
    quarantine = {}
    for r in C.decoded("flaky_windows.tsv", lambda r: lang(r["target"])):
        quarantine.setdefault((r["target"], r["testcase"]), []).append((r["from"], r["until"]))
    scope = {r["target"]: r["scope"] for r in C.decoded("scope_rules.md", batch)}
    # --- ownership -------------------------------------------------------------------
    patterns = sorted(C.decoded("owners_registry.txt", batch), key=lambda r: r["seq"])
    pidx = {}
    for p in patterns:
        pat = p["pattern"][1:] if p["pattern"].startswith("!") else p["pattern"]
        pidx.setdefault(pat.split("*", 1)[0], []).append((p["seq"], p["pattern"].startswith("!"), glob_rx(pat), p["handle"]))
    renames, earlier = {}, {}
    for r in C.decoded("ownership_patterns_approved.tsv", batch):
        if r["kind"] == "handle_rename":
            earlier[r["handle"]] = r["target"]
            if r["effective"] <= K:
                renames[r["target"]] = r["handle"]

    def owner(label):
        cands = []
        for k in range(1, len(label) + 1):
            cands.extend(pidx.get(label[:k], []))
        hit = None
        for _seq, neg, rx, h in sorted(cands, key=lambda c: c[0]):
            if rx.fullmatch(label):
                hit = None if neg else h
        return renames.get(hit, hit) if hit else None

    def base(h):
        return earlier.get(h, h)

    def team(h, t):
        b = base(h)
        cur = roster[b]
        for eff, tm in sorted(transfers.get(b, [])):
            if eff <= t:
                cur = tm
        return cur

    ccrows = {}
    for r in C.decoded("cost_centers.csv", lambda r: org(r["handle"])):
        ccrows.setdefault(r["handle"], []).append((r["effective_from"], r["cost_center"]))
    merges = {r["cost_center"]: (r["successor"], ts_iso(r["effective_at"])) for r in C.table_all("Cost center merges")}

    def merged(cc, t):
        if cc in merges and merges[cc][1] <= t:
            return merges[cc][0]
        return cc

    def cost_center(h, t):
        cur = None
        for eff, cc in sorted(ccrows[base(h)]):
            if eff <= t:
                cur = cc
        return merged(cur, t)

    # --- toolchains ------------------------------------------------------------------
    releases = {}
    for r in C.table_all("Toolchain releases"):
        releases.setdefault(r["toolchain"], []).append(
            (r["version"], ts_iso(r["released_at"]), None if r["yanked_at"] == "never" else ts_iso(r["yanked_at"])))
    pins = {r["target"]: r["constraint"] for r in C.decoded("toolchain_pins.yaml", lambda r: lang(r["target"]))}
    rcache = {}

    def resolve(target, t):
        key = (target, t)
        if key in rcache:
            return rcache[key]
        tc, cons = pkg[target]["toolchain"], pins[target]
        best = None
        for ver, rel, yank in releases[tc]:
            if rel > t or (yank is not None and yank <= t) or not satisfies(cons, ver):
                continue
            if best is None or vkey(ver) > vkey(best):
                best = ver
        rcache[key] = best
        return best

    # --- attempts out ------------------------------------------------------------------
    att_rows = []
    for a in sorted(attempts, key=lambda a: a["id"]):
        start = a["rep"]
        for wnd in windows.get(a["runner"], []):
            if wnd["window_from"] <= start < wnd["window_to"]:
                start = start - wnd["skew_ms"] // 1000
                break
        rev = None
        for r in revs[a["runner"]]:
            if r["effective_from"] <= start:
                rev = r
        sku = skus[rev["sku"]]
        region = rev_region[(a["runner"], rev["rev"])]
        label = register[a["job"]]["target"]
        st = status[a["id"]]
        excl = None
        if not P0 <= start < P1:
            excl = "out_of_period"
        elif a["id"] in revoked:
            excl = "revoked"
        elif any(lo <= start < hi for lo, hi in drains.get(a["runner"], [])):
            excl = "provider_drain"
        elif st == "cancelled" and origin.get(a["id"]) == "platform":
            excl = "platform_cancel"
        elif st == "failed" and a["id"] in jcases and all(
                any(lo <= start <= hi for lo, hi in quarantine.get((label, c), [])) for c in jcases[a["id"]]):
            excl = "quarantined_flake"
        elif st == "preempted" and a["dur"] < grace[a["fleet"]] * 1000:
            excl = "preempt_grace"
        elif a["no"] > budgets.get(a["job"], default_budget):
            excl = "over_budget"
        elif scope[label] == "exempt":
            excl = "exempt_scope"
        h = owner(label) or renames.get(register[a["job"]]["submitter"], register[a["job"]]["submitter"])
        klass = amend.get(a["job"], "standard")
        cur = None
        for r in rate_rows.get((sku["instance_class"], region), []):
            if r["effective_from"] <= start:
                cur = r
        rate = cur["micro_per_min"] if cur else 0
        g = gran[sku["sku"]]
        bs = -(-a["dur"] // (1000 * g)) * g
        res = (a["runner"], iso(start)[:10]) in reserv
        cost = 0
        if excl is None:
            fr = Fraction(bs * rate * classes[klass], 60 * 1000)
            if sku["spot"] == "true":
                fr = fr * (1000 - spot_credit[sku["instance_class"]]) / 1000
            if res:
                fr = fr * reserved_permille / 1000
            cost = half_even(fr)
        att_rows.append({"attempt_id": a["id"], "job_id": a["job"], "attempt_no": a["no"], "fleet": a["fleet"],
                         "runner": a["runner"], "runner_rev": rev["rev"], "region": region, "sku": sku["sku"],
                         "instance_class": sku["instance_class"], "target": label, "started_at": iso(start),
                         "duration_ms": a["dur"], "status": st, "exclusion": excl,
                         "billable_seconds": bs if excl is None else 0, "rate_micro_per_min": rate,
                         "billing_class": klass, "reserved": res, "cost_micro": cost, "owner_handle": h,
                         "team": team(h, start), "cost_center": cost_center(h, start)})
    att_out = {r["attempt_id"]: r for r in att_rows}
    # --- actions, cache --------------------------------------------------------------
    lock = {r["action"]: r for r in C.decoded("action_keys.lock", lambda r: lang(r["target"]))}
    act_lang = lambda r: lang(lock[str(r["action"]).strip().lower()]["target"])
    manifests = {r["action"]: r for r in C.decoded("input_manifests.tsv", act_lang)}
    allowed = {r["variable"] for r in C.raw["env_allowlist.json"]["allowed"]}
    envs = {r["action"]: r["reads"] for r in C.decoded("env_allowlist.json", act_lang)}
    by_prefix = {k[:6]: k for k in lock}
    home = {}
    for r in C.decoded("shard_index.tsv", lambda r: lang(lock[by_prefix[r["prefix"].strip().lower()]]["target"])):
        home[by_prefix[r["prefix"]]] = r["shard"]
    hermetic = {k: manifests[k]["declared"] == "true" and set(envs[k]) <= allowed for k in lock}
    digests = {r["digest"]: r["version"] for r in C.raw["toolchain_pins_resolved.json"]["digests"]}
    C.decoded("toolchain_pins_resolved.json", lambda r: lang(r["target"]))
    writes = {}
    for r in C.decoded("lookups_archive.jsonl.gz", act_lang):
        if r["kind"] == "write":
            writes.setdefault(r["action"], []).append(r["at"])
    evict = {}
    for r in C.decoded("evictions.log", act_lang):
        evict.setdefault((r["shard"], r["action"]), []).append((r["ts"], r["eviction"]))
    lk_rows = []
    for shard, name in ((1, "lookups_shard1.jsonl"), (2, "lookups_shard2.jsonl"), (3, "lookups_shard3.jsonl.gz")):
        for r in C.decoded(name, act_lang):
            key = r["action"]
            target = lock[key]["target"]
            evid = None
            if home[key] != shard:
                oc = "replay"
            elif r["result"] == "MISS":
                oc = "miss"
            elif not hermetic[key]:
                oc = "nonhermetic_hit"
            else:
                last = max(t for t in writes[key] if t <= r["at"])
                cands = sorted((e, i) for e, i in evict.get((shard, key), []) if last < e <= r["at"])
                if cands:
                    oc, evid = "evicted_hit", cands[0][1]
                elif resolve(target, last) != resolve(target, r["at"]):
                    oc = "stale_hit"
                else:
                    oc = "hit"
            lk_rows.append({"lookup_id": r["lookup"], "attempt_id": r["attempt"], "action_key": key, "shard": shard,
                            "at": iso(r["at"]), "bytes": r["bytes"], "outcome": oc, "eviction_id": evid})
    lk_rows.sort(key=lambda r: r["lookup_id"])
    # --- targets -------------------------------------------------------------------------
    targets = C.decoded("targets.csv", lambda r: lang(r["target"]))
    parents = {}
    for e in C.decoded("edges.csv", lambda r: lang(r["child"])):
        if e["kind"] != "data":
            parents.setdefault(e["child"], []).append(e["parent"])
    memo = {}

    def invalid(t):
        if t not in memo:
            memo[t] = False
            memo[t] = resolve(t, P0) != resolve(t, P1 - 1) or any(invalid(p) for p in parents.get(t, []))
        return memo[t]

    sys.setrecursionlimit(100000)
    owners = {}
    tg_rows = []
    for t in sorted(targets, key=lambda t: t["target"]):
        lab = t["target"]
        h = owner(lab)
        owners[lab] = h
        tg_rows.append({"target": lab, "kind": t["kind"], "language": pkg[lab]["language"],
                        "toolchain": pkg[lab]["toolchain"], "constraint": pins[lab], "version_at_open": resolve(lab, P0),
                        "version_at_close": resolve(lab, P1 - 1), "invalidated": invalid(lab), "scope": scope[lab],
                        "owner_handle": h, "team": team(h, P1 - 1) if h else None})
    ac_rows = []
    for k in sorted(lock):
        m = manifests[k]
        dg = lock[k]["digest"]
        ac_rows.append({"action_key": k, "target": lock[k]["target"], "home_shard": home[k], "hermetic": hermetic[k],
                        "undeclared_inputs": [] if m["declared"] == "true" else [m["path"]], "input_bytes": m["size"],
                        "disallowed_env": sorted(set(envs[k]) - allowed),
                        "toolchain_version": None if dg == "none" else digests[dg]})
    # --- artifacts ------------------------------------------------------------------------
    registry = C.decoded("artifact_registry.db", lambda r: lang(r["target"]))
    art_target = {r["artifact"]: r["target"] for r in registry}
    gcs = {}
    for g in C.decoded("gc_events.csv", lambda r: lang(art_target[r["artifact"].strip().lower()])):
        gcs.setdefault(g["artifact"], []).append(g)
    storage_rate = int(params["storage_micro_per_gib_hour"])
    ar_rows = []
    for ar in sorted(registry, key=lambda r: r["artifact"]):
        alive, t0, kept = True, ar["created"], 0
        for g in sorted(gcs.get(ar["artifact"], []), key=lambda g: g["at"]):
            if g["action"] == "delete" and alive:
                kept += max(0, min(g["at"], P1) - max(t0, P0))
                alive = False
            elif g["action"] == "restore" and not alive:
                alive, t0 = True, g["at"]
        if alive:
            kept += max(0, P1 - max(t0, P0))
        h = owners[ar["target"]]
        ar_rows.append({"artifact_id": ar["artifact"], "target": ar["target"], "bytes": ar["bytes"],
                        "retained_seconds": kept,
                        "storage_cost_micro": half_even(Fraction(ar["bytes"] * kept * storage_rate, 1073741824 * 3600)),
                        "team": team(h, P1 - 1) if h else None, "cost_center": cost_center(h, P1 - 1) if h else None})
    # --- invoices ----------------------------------------------------------------------------
    lines = C.decoded("invoice_lines.xlsx", lambda r: locale[r["vendor"]])
    credit = {v["line"]: v["credit"] for v in vendors}
    locale_of_line = {r["line_id"]: locale[r["vendor"]] for r in lines}
    closed = {r["line_id"] for r in C.decoded("invoice_restatement.csv", lambda r: locale_of_line[r["line_id"].strip().lower()])
              if r["type"] == "dispute_closure"}
    edges = sorted({r["week_start"] for r in lines}) + [P1]
    comp = {}
    for r in att_rows:
        if r["exclusion"] is None:
            t = ts_iso(r["started_at"])
            wk = max(e for e in edges[:-1] if e <= t)
            comp[(r["runner"], wk)] = comp.get((r["runner"], wk), 0) + r["cost_micro"]
    iv_rows = []
    for r in sorted(lines, key=lambda r: r["line_id"]):
        c = comp.get((r["runner"], r["week_start"]), 0)
        b = r["billed"]
        if r["line_id"] in closed:
            st = "closed"
        elif b == c:
            st = "match"
        elif b - credit[r["line_id"]] == c:
            st = "credited"
        else:
            st = "mismatch"
        iv_rows.append({"line_id": r["line_id"], "runner": r["runner"], "week": edges.index(r["week_start"]),
                        "billed_micro": b, "credit_micro": credit[r["line_id"]], "computed_micro": c, "status": st})
    # --- chargeback, cache effectiveness ------------------------------------------------------
    credit_micro = int(params["cache_credit_micro"])
    blank = lambda: {"attempts_billed": 0, "compute_micro": 0, "storage_micro": 0, "cache_credit_micro": 0}
    teams = {}
    for r in att_rows:
        d = teams.setdefault(r["team"], blank())
        if r["exclusion"] is None:
            d["attempts_billed"] += 1
            d["compute_micro"] += r["cost_micro"]
    for r in ar_rows:
        if r["team"]:
            teams.setdefault(r["team"], blank())["storage_micro"] += r["storage_cost_micro"]
    cache = {}
    for r in lk_rows:
        tm = att_out[r["attempt_id"]]["team"]
        d = cache.setdefault(tm, {k: 0 for k in ("evicted_hit", "hit", "miss", "nonhermetic_hit", "replay", "stale_hit")})
        d[r["outcome"]] += 1
        if r["outcome"] == "hit":
            teams.setdefault(tm, blank())["cache_credit_micro"] += credit_micro
    for d in cache.values():
        den = d["hit"] + d["miss"] + d["stale_hit"] + d["evicted_hit"] + d["nonhermetic_hit"]
        d["valid_hit_permille"] = d["hit"] * 1000 // den if den else 0
    for d in teams.values():
        d["net_micro"] = d["compute_micro"] + d["storage_micro"] - d["cache_credit_micro"]
    # --- ledger --------------------------------------------------------------------------------
    led = {}
    for r in C.decoded("opening_balances.json", batch):
        d = led.setdefault(r["cost_center"], {"opening_micro": 0, "postings_micro": 0, "charges_micro": 0})
        d["opening_micro"] += r["amount"]
    voids = {r["posting"] for r in C.raw["control_totals_draft.html"].get("Late voids", [])}
    postings = C.decoded("settlement_ledger.db", batch)
    reversed_ids = {p["reverses"] for p in postings if p["reverses"]}
    for p in postings:
        if not P0 <= p["posted_at"] < P1 or p["posting"] in voids or p["posting"] in reversed_ids or p["reverses"]:
            continue
        led[merged(p["cost_center"], p["posted_at"])]["postings_micro"] += p["amount"]
    for r in att_rows:
        if r["exclusion"] is None:
            led[r["cost_center"]]["charges_micro"] += r["cost_micro"]
    for r in ar_rows:
        if r["cost_center"]:
            led[r["cost_center"]]["charges_micro"] += r["storage_cost_micro"]
    for d in led.values():
        d["closing_micro"] = d["opening_micro"] + d["postings_micro"] + d["charges_micro"]
    # --- rate resolution -----------------------------------------------------------------------
    rr = {}
    for (cls, region), rows in sorted(rate_rows.items()):
        cur = [r for r in rows if r["effective_from"] <= P0]
        win = ([cur[-1]] if cur else []) + [r for r in rows if P0 < r["effective_from"] < P1]
        rr[f"{cls}|{region}"] = [[iso(max(r["effective_from"], P0)), r["micro_per_min"]] for r in win]
    # --- controls --------------------------------------------------------------------------------
    for name in sorted(C.catalog):
        if name not in C._all:
            ctx_dim = C.catalog[name]["context"]
            C.decoded(name, batch)
    ctrl = {}
    annex_rows = [d for dup, d in C._all["audit_annex.pdf"] if not dup]

    def blocks(name):
        col = C.catalog[name]["control column"]
        rows = C._all[name]
        out = []
        for b in range(0, len(rows), CONTROL_BLOCK):
            blk = [d for dup, d in rows[b:b + CONTROL_BLOCK] if not dup]
            out.append((len(blk), sum(int(d[col]) for d in blk)))
        return out

    cache_blocks = {}
    for r in annex_rows:
        bl = cache_blocks.setdefault(r["file"], blocks(r["file"]))
        n, s = bl[r["block"] - 1]
        ctrl[r["control_id"]] = {"file": r["file"], "block": r["block"], "expected_records": r["records"],
                                 "expected_sum": r["control_sum"], "records": n, "sum": s,
                                 "match": n == r["records"] and s == r["control_sum"]}
    ab = blocks("audit_annex.pdf")
    for dup, r in C._all["control_totals_draft.html"]:
        if not dup and r["file"] == "audit_annex.pdf" and r["control_id"].startswith("DT-"):
            n, s = ab[r["block"] - 1]
            ctrl[r["control_id"]] = {"file": r["file"], "block": r["block"], "expected_records": r["records"],
                                     "expected_sum": r["control_sum"], "records": n, "sum": s,
                                     "match": n == r["records"] and s == r["control_sum"]}
    audit = {name: {"records": sum(1 for dup, _ in C._all[name] if not dup)} for name in sorted(C._all)}
    tc = teams
    summary = {"attempts_listed": len(att_rows), "attempts_billed": sum(1 for r in att_rows if r["exclusion"] is None),
               "compute_micro": sum(d["compute_micro"] for d in tc.values()),
               "storage_micro": sum(d["storage_micro"] for d in tc.values()),
               "cache_credit_micro": sum(d["cache_credit_micro"] for d in tc.values()),
               "net_micro": sum(d["net_micro"] for d in tc.values()),
               "invoice_mismatches": sum(1 for r in iv_rows if r["status"] == "mismatch"),
               "controls_mismatched": sum(1 for c in ctrl.values() if not c["match"]),
               "closing_micro": sum(d["closing_micro"] for d in led.values())}
    os.makedirs(out_dir, exist_ok=True)

    def jl(name, rows):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")

    def js(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(obj, sort_keys=True, indent=2) + "\n")

    jl("attempts.jsonl", att_rows)
    jl("lookups.jsonl", lk_rows)
    jl("targets.jsonl", tg_rows)
    jl("actions.jsonl", ac_rows)
    jl("artifacts.jsonl", ar_rows)
    jl("invoice_reconciliation.jsonl", iv_rows)
    js("team_chargeback.json", teams)
    js("cost_center_ledger.json", led)
    js("rate_resolution.json", rr)
    js("cache_effectiveness.json", cache)
    js("control_reconciliation.json", ctrl)
    js("source_audit.json", audit)
    js("close_summary.json", summary)


def main(argv):
    if os.path.basename(argv[0]) == "solve.py":
        # reference install: place this program at /app/out/settle.py, then close /app/data
        root = os.environ.get("APP_ROOT", "/app")
        dest = os.path.join(root, "out", "settle.py")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(argv[0], encoding="utf-8") as src, open(dest, "w", encoding="utf-8") as fh:
            fh.write(src.read())
        os.chmod(dest, 0o755)
        argv = [dest, os.path.join(root, "data"), os.path.join(root, "out")]
    data_dir = argv[1] if len(argv) > 1 else "/app/data"
    out_dir = argv[2] if len(argv) > 2 else "/app/out"
    run(data_dir, out_dir)


if __name__ == "__main__":
    main(sys.argv)
