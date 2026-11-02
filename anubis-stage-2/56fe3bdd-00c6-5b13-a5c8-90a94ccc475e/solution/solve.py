#!/usr/bin/env python3
"""PES-3 review engine.

Usage: python3 evalctl.py ESTATE_DIR OUT_DIR

Reads one review estate laid out like /app/data and writes the eight review
artifacts of the Perception Evaluation Standard v3 into OUT_DIR.
"""
from __future__ import annotations

import configparser
import csv
import email
import email.policy
import email.utils
import html.parser
import io
import json
import logging
import mailbox
import re
import sqlite3
import sys
import tomllib
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from calendar import timegm
from datetime import date, datetime, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import openpyxl
import pyarrow.parquet as pq
import pypdf
import yaml

logging.getLogger("pypdf").setLevel(logging.ERROR)

CUTOFF = timegm((2026, 11, 12, 18, 0, 0))
WIN_LO = timegm((2026, 9, 14, 0, 0, 0))
WIN_HI = timegm((2026, 11, 9, 0, 0, 0))
REG_DATE = timegm((2026, 10, 15, 0, 0, 0))
QA_SNAP = timegm((2026, 10, 31, 0, 0, 0))
PRECEDENCE = ["WITHDRAWN", "OUT_OF_WINDOW", "CORRUPT", "PRIVACY_HOLD", "BOARD_OVERRIDE",
              "LEAK_EXACT", "LEAK_NEAR", "LEAK_SEQUENCE", "UNLABELED"]
SYN = {"frame": "image_id", "camera": "camera_id", "local_time": "captured_local", "fold": "dst_fold",
       "width_px": "stored_width", "height_px": "stored_height", "sequence": "sequence_id", "frame_no": "frame_index",
       "hash": "dhash_u64", "ann_id": "annotation_id", "annotation": "annotation_id", "decided": "decided_at",
       "category": "label", "rev": "revision", "img": "image_id", "proj": "project", "project": "project",
       "det": "det_id", "cls": "class_index", "request": "request_id", "item": "item_id", "box": "box_id"}
DEFAULT_CONV = {"NL": ("xywh", "stored"), "KS": ("cxcywh_norm", "upright"), "OB": ("xyxy_inclusive", "upright")}
CONV_SYN = {"x,y,w,h": "xywh", "x1,y1,x2,y2": "xyxy", "cx,cy,w,h/norm": "cxcywh_norm", "x1,y1,x2,y2/incl": "xyxy_inclusive"}


# ------------------------------------------------------------------ low level readers
def text_of(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    out = []
    for line in raw.splitlines(keepends=True):
        try:
            out.append(line.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(line.decode("latin-1"))
    return "".join(out)


def canon_col(name: str, extra=None) -> str:
    n = str(name).strip().lstrip("\ufeff")
    if extra and n in extra:
        return extra[n]
    return SYN.get(n, n)


def read_delimited(path: Path, delim: str, extra=None):
    rows = list(csv.reader(io.StringIO(text_of(path), newline=""), delimiter=delim))
    header = None
    out = []
    for row in rows:
        if not row or (len(row) == 1 and not row[0].strip()):
            continue
        if row[0].startswith("#"):
            continue
        if header is None:
            header = [canon_col(c, extra) for c in row]
            known = set(header)
            continue
        cand = [canon_col(c, extra) for c in row if c.strip()]
        if cand and all(c in known for c in cand) and len(cand) >= len(header) - 1:
            header = [canon_col(c, extra) for c in row]
            continue
        out.append({header[k]: row[k] for k in range(min(len(header), len(row)))})
    return out


def num(s) -> Fraction:
    if isinstance(s, (int,)):
        return Fraction(s)
    if isinstance(s, float):
        return Fraction(Decimal(repr(s)))
    if isinstance(s, Decimal):
        return Fraction(s)
    s = str(s).strip().replace(" ", "")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.startswith("+"):
        s = s[1:]
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        grp = "." if dec == "," else ","
        s = s.replace(grp, "").replace(dec, ".")
    elif "," in s:
        s = s.replace(",", ".")
    v = Fraction(Decimal(s))
    return -v if neg else v


def instant(s) -> int:
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        days = num(s)
        if days >= 61:
            days -= 1
        secs = days * 86400 + timegm((1899, 12, 31, 0, 0, 0))
        return int(round(secs))
    s = str(s).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp())


def day_start(s) -> int:
    d = date.fromisoformat(str(s).strip())
    return timegm((d.year, d.month, d.day, 0, 0, 0))


def rnd(fr: Fraction) -> int:
    n, r = divmod(fr.numerator, fr.denominator)
    if 2 * r > fr.denominator or (2 * r == fr.denominator and n % 2):
        n += 1
    return n


def six(fr) -> str:
    fr = Fraction(fr)
    q = fr * 1000000
    n = rnd(q)
    sign = "-" if n < 0 else ""
    n = abs(n)
    return "%s%d.%06d" % (sign, n // 1000000, n % 1000000)


def offset_minutes(s: str) -> int:
    s = s.strip().replace(":", "")
    sign = -1 if s[0] == "-" else 1
    return sign * (int(s[1:3]) * 60 + int(s[3:5]))


# ------------------------------------------------------------------ documents
def docx_blocks(path: Path):
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(ns + "body")
    blocks = []
    for el in body:
        if el.tag == ns + "p":
            style = el.find(ns + "pPr/" + ns + "pStyle")
            st = style.get(ns + "val") if style is not None else ""
            blocks.append(("p", st, "".join(t.text or "" for t in el.iter(ns + "t"))))
        elif el.tag == ns + "tbl":
            rows = []
            for tr in el.iter(ns + "tr"):
                rows.append(["".join(t.text or "" for t in tc.iter(ns + "t")) for tc in tr.iter(ns + "tc")])
            blocks.append(("tbl", "", rows))
    return blocks


def docx_register(path: Path):
    blocks = docx_blocks(path)
    reg, errata, tables, heading = None, [], {}, ""
    in_errata = False
    for kind, st, val in blocks:
        if kind == "p" and st.startswith("Heading"):
            heading = val
            in_errata = val.startswith("Errata to the register")
            continue
        if kind == "tbl":
            if heading.startswith("Appendix"):
                reg = val
            else:
                tables[heading] = val
        elif in_errata and val:
            errata.append(val)
    return reg[0], reg[1:], errata, tables, blocks


def pdf_lines(path: Path):
    reader = pypdf.PdfReader(str(path))
    lines = []
    for page in reader.pages:
        lines.extend((page.extract_text() or "").splitlines())
    return [ln.rstrip() for ln in lines]


def pdf_register(path: Path):
    lines = pdf_lines(path)
    a = lines.index("APPENDIX REGISTER")
    b = lines.index("END OF REGISTER")
    header = [c.strip() for c in lines[a + 1].split("|")]
    rows = [[c.strip() for c in ln.split("|")] for ln in lines[a + 2:b]]
    errata = []
    if "ERRATA TO THE REGISTER" in lines:
        errata = [ln for ln in lines[lines.index("ERRATA TO THE REGISTER") + 1:] if ln.strip()]
    return header, rows, errata, lines[:a]


def md_register(path: Path):
    lines = text_of(path).splitlines()
    rows, errata, header = [], [], None
    mode = None
    for ln in lines:
        if ln.startswith("## "):
            mode = "reg" if ln[3:].startswith("Appendix") else ("err" if ln[3:].startswith("Errata to the register") else None)
            continue
        if mode == "reg" and ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if header is None:
                header = cells
            elif set(ln.replace("|", "").strip()) <= set("-: "):
                continue
            else:
                rows.append(cells)
        elif mode == "err" and ln.strip():
            errata.append(ln.strip())
    return header, rows, errata


class _HTML(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.lis, self.cur_h, self.in_h = [], [], "", False
        self.row, self.cell, self.tbl, self.in_li, self.li = None, None, None, False, ""

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2"):
            self.in_h, self.cur_h = True, ""
        elif tag == "table":
            self.tbl = {"title": self.cur_h, "rows": []}
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = ""
        elif tag == "li":
            self.in_li, self.li = True, ""

    def handle_endtag(self, tag):
        if tag in ("h1", "h2"):
            self.in_h = False
        elif tag in ("td", "th") and self.row is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.tbl is not None:
            self.tbl["rows"].append(self.row)
            self.row = None
        elif tag == "table":
            self.tables.append(self.tbl)
            self.tbl = None
        elif tag == "li":
            self.in_li = False
            self.lis.append((self.cur_h, self.li))

    def handle_data(self, data):
        if self.in_h:
            self.cur_h += data
        elif self.cell is not None:
            self.cell += data
        elif self.in_li:
            self.li += data


def html_tables(path: Path):
    p = _HTML()
    p.feed(text_of(path))
    errata = [t for h, t in p.lis if h.startswith("Errata to the register")]
    return {t["title"]: t["rows"] for t in p.tables}, errata


def xlsx_sheets(path: Path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = {}
    for ws in wb.worksheets:
        header, rows = None, []
        for vals in ws.iter_rows(values_only=True):
            vals = list(vals)
            while vals and vals[-1] is None:
                vals.pop()
            if not vals:
                continue
            if header is None:
                header = [canon_col(v) for v in vals]
                known = set(header)
                continue
            if all(isinstance(v, str) for v in vals) and all(canon_col(v) in known for v in vals):
                header = [canon_col(v) for v in vals]
                continue
            rows.append({header[k]: vals[k] for k in range(min(len(header), len(vals)))})
        out[ws.title] = rows
    wb.close()
    return out


# ------------------------------------------------------------------ the engine
class Engine:
    def __init__(self, root: Path):
        self.root = root
        self.parsed: dict[str, int] = {}

    def p(self, name):
        return self.root / name

    # identifiers ------------------------------------------------------
    def load_aliases(self):
        cp = configparser.ConfigParser(strict=False, inline_comment_prefixes=(";",), interpolation=None)
        cp.optionxform = str
        cp.read_string(text_of(self.p("image_id_aliases.ini")))
        self.homo = {}
        for k, v in cp.items("homoglyphs"):
            self.homo[chr(int(k.strip()[2:], 16))] = v.strip()
        self.alias = {k.strip().upper(): v.strip() for k, v in cp.items("aliases")}
        self.parsed["image_id_aliases.ini"] = len(cp.items("aliases"))

    def img(self, s, depth=0):
        if s is None:
            return None
        t = unicodedata.normalize("NFKC", str(s)).strip()
        t = "".join(self.homo.get(c, c) for c in t).upper()
        if t.startswith("LGC-"):
            if depth > 20 or t not in self.alias:
                return None
            return self.img(self.alias[t], depth + 1)
        t = t.replace("-", "").replace("_", "")
        m = re.fullmatch(r"IMG(\d{1,7})", t)
        return "IMG%07d" % int(m.group(1)) if m else None

    @staticmethod
    def cam(s):
        return re.sub(r"[ _]", "-", str(s).strip().upper())

    @staticmethod
    def seq(s):
        m = re.fullmatch(r"SEQ-?(\d+)", str(s).strip().upper())
        return "SEQ-%05d" % int(m.group(1)) if m else str(s).strip().upper()

    @staticmethod
    def ann(s):
        t = str(s).strip().upper()
        if t.startswith("OB:"):
            return "OB-%07d" % int(t[3:])
        return t

    # ------------------------------------------------------------------
    def run(self, out: Path):
        self.load_aliases()
        self.load_manifest()
        self.load_registry()
        self.load_frames()
        self.load_time_sources()
        self.load_geometry()
        self.load_exclusion_sources()
        self.load_leakage()
        self.load_annotation_rules()
        self.load_annotations()
        self.load_detection_sources()
        self.load_calibration()
        self.decide_images()
        self.build_detections()
        self.score()
        self.write(out)

    # manifest ---------------------------------------------------------
    def load_manifest(self):
        data = tomllib.loads(text_of(self.p("delivery_manifest.toml")))
        self.declared: dict[str, int] = {}
        self.partitions: dict[str, dict[int, int]] = {}
        for e in data.get("partition", []):
            if e.get("status") in ("superseded", "voided", "withdrawn") or not (self.root / e["file"]).is_file():
                continue
            self.partitions.setdefault(e["file"], {})[e["part"]] = e["records"]
        for f, parts in self.partitions.items():
            self.declared[f] = sum(parts.values())

    # registry ---------------------------------------------------------
    def load_registry(self):
        tables, errata = html_tables(self.p("inference_run_registry.html"))
        runs = tables["Runs"]
        hdr = runs[0]
        self.runs = {}
        for r in runs[1:]:
            d = dict(zip(hdr, r))
            self.runs[d["run_id"]] = d
        self.review = sorted(r for r, d in self.runs.items() if d["status"] == "review")
        self.model_run = {d["model"]: r for r, d in self.runs.items()}
        self.labelmap = {}
        for r in tables["Label maps"][1:]:
            self.labelmap.setdefault(r[0], {})[int(r[1])] = r[2]
        self.incumbent = self.model_run["skye-v6.4"]
        reg = tables["Appendix - Sequence node assignments"]
        rows = [list(r) for r in reg[1:]]
        for e in errata:
            m = re.match(r"Row (\d+) \(run (\S+), sequence (\S+)\): node is (\w+)\.", e)
            if m:
                rows[int(m.group(1)) - 1][2] = m.group(4)
        self.parsed["inference_run_registry.html"] = len(rows)
        self.assign = {}
        for r in rows:
            self.assign[(r[0], self.seq(r[1]))] = r[2]
        mt, me = html_tables(self.p("inference_run_registry_mirror.html"))
        mrows = [list(r) for r in mt["Appendix - Sequence node assignments"][1:]]
        for e in me:
            m = re.match(r"Row (\d+) \(run (\S+), sequence (\S+)\): node is (\w+)\.", e)
            if m:
                mrows[int(m.group(1)) - 1][2] = m.group(4)
        self.parsed["inference_run_registry_mirror.html"] = len(mrows)
        listed = set(s for (_, s) in self.assign)
        for r in mrows:
            s = self.seq(r[1])
            if s not in listed:
                self.assign[(r[0], s)] = r[2]
        self.train_index = {r: [x.strip() for x in d["training_index"].split(",")] for r, d in self.runs.items()}
        # model vocabulary crosswalk lives in the taxonomy charter
        reg_hdr, reg_rows, xerr, tables2, _ = docx_register(self.p("taxonomy_v3_charter.docx"))
        mv = tables2["Model vocabulary crosswalk (taxonomy v2 model labels)"]
        self.model_vocab = {r[0]: (None if r[2] == "drop" else r[1]) for r in mv[1:]}
        self.classes = None
        self._tax = (reg_hdr, reg_rows, xerr, tables2)

    # frames -----------------------------------------------------------
    def load_frames(self):
        self.frames = {}
        prim_cams = set()
        for name in ("frames_index_east.csv", "frames_index_west.csv"):
            rows = read_delimited(self.p(name), ",")
            self.parsed[name] = len(rows)
            for r in rows:
                i = self.img(r["image_id"])
                c = self.cam(r["camera_id"])
                prim_cams.add(c)
                if i:
                    self.frames[i] = (c, r["captured_local"], (r.get("dst_fold") or "").strip())
        rows = read_delimited(self.p("frames_index_east_v2.csv"), ",")
        self.parsed["frames_index_east_v2.csv"] = len(rows)
        for r in rows:
            c = self.cam(r["camera_id"])
            if c in prim_cams or not (r.get("captured_utc") or "").strip():
                continue
            i = self.img(r["image_id"])
            if i:
                self.frames[i] = (c, r["captured_local"], (r.get("dst_fold") or "").strip())
        # sequences
        sheets = xlsx_sheets(self.p("sequence_membership.xlsx"))
        self.parsed["sequence_membership.xlsx"] = sum(len(v) for v in sheets.values())
        self.seq_of = {}
        for rows in sheets.values():
            for r in rows:
                i = self.img(r["image_id"])
                if i:
                    self.seq_of[i] = self.seq(r["sequence_id"])
        # freeze
        hdr, rows, errata = md_register(self.p("eval_standard_v3.md"))
        self.parsed["eval_standard_v3.md"] = len(rows)
        fix = {}
        for e in errata:
            m = re.match(r"Row listing (\S+) is a transcription error; the frozen image is (\S+)\.", e)
            if m:
                fix[m.group(1)] = m.group(2)
        freeze = set()
        for r in rows:
            v = r[0]
            if v.startswith("~~"):
                continue
            v = fix.get(v, v)
            i = self.img(v)
            if i:
                freeze.add(i)
        hdr, rows, errata = md_register(self.p("eval_standard_v3_1_draft.md"))
        self.parsed["eval_standard_v3_1_draft.md"] = len(rows)
        rows = [list(r) for r in rows]
        for e in errata:
            m = re.match(r"Row (\d+) \((\S+)\): action is (\w+)\.", e)
            if m:
                rows[int(m.group(1)) - 1][1] = m.group(3)
        for r in rows:
            if r[0].startswith("~~") or r[2] != "ratified":
                continue
            i = self.img(r[0])
            if not i:
                continue
            if r[1] == "add":
                freeze.add(i)
            elif r[1] == "remove":
                freeze.discard(i)
        self.freeze = freeze
        self.cands = sorted(i for i in freeze if i in self.frames)

    def load_time_sources(self):
        def roster(name):
            data = yaml.safe_load(text_of(self.p(name)))
            lst = data["roster"]
            self.parsed[name] = len(lst)
            return lst
        main = roster("camera_deployment_roster.yaml")
        self.roster = {}
        for e in main:
            self.roster[(self.cam(e["camera"]), str(e["date"]))] = e
        main_cams = set(c for c, _ in self.roster)
        for e in roster("camera_deployment_roster_ops.yaml"):
            c = self.cam(e["camera"])
            if c in main_cams or e.get("active") is False:
                continue
            self.roster[(c, str(e["date"]))] = e
        txt = text_of(self.p("camera_clock_sync.ics"))
        self.skews = {}
        n = 0
        for block in txt.split("BEGIN:VEVENT")[1:]:
            n += 1
            f = {}
            for ln in block.splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    f[k.strip()] = v.strip()
            if f.get("STATUS") != "CONFIRMED":
                continue
            c = self.cam(f["SUMMARY"].split(" ", 1)[1])
            key, val = f["DESCRIPTION"].split("=", 1)
            sk = num(val)
            if key.strip() == "skew_ms":
                sk = sk / 1000
            st = timegm(datetime.strptime(f["DTSTART"], "%Y%m%dT%H%M%SZ").timetuple())
            en = timegm(datetime.strptime(f["DTEND"], "%Y%m%dT%H%M%SZ").timetuple())
            self.skews.setdefault(c, []).append((st, en, sk))
        self.parsed["camera_clock_sync.ics"] = n

    def capture(self, i):
        c, local_s, fold = self.frames[i]
        d = datetime.fromisoformat(local_s.strip().replace(" ", "T")).replace(tzinfo=timezone.utc)
        local = int(d.timestamp())
        e = self.roster[(c, d.date().isoformat())]
        off = offset_minutes(e["utc_offset"])
        if e.get("switch_local"):
            h, m, s = (int(x) for x in str(e["switch_local"]).split(":"))
            sw = h * 3600 + m * 60 + s
            after = offset_minutes(e["offset_after"])
            sod = local % 86400
            if sod >= sw:
                off = after
            elif sod >= sw - (off - after) * 60 and fold == "1":
                off = after
        ucam = local - off * 60
        sk = Fraction(0)
        for st, en, v in self.skews.get(c, []):
            if st <= ucam < en:
                sk = v
        t = ucam - sk
        return c, e["site"], t

    def load_geometry(self):
        rows = read_delimited(self.p("frame_geometry.tsv"), "\t")
        self.parsed["frame_geometry.tsv"] = len(rows)
        self.geo = {}
        for r in rows:
            i = self.img(r["image_id"])
            sc = num(r["dim_scale"])
            self.geo[i] = (int(num(r["stored_width"]) * sc), int(num(r["stored_height"]) * sc))
        hdr, rows, errata, _ = pdf_register(self.p("frame_integrity_audit.pdf"))
        self.parsed["frame_integrity_audit.pdf"] = len(rows)
        fix = {}
        for e in errata:
            m = re.match(r"Line (\S+): status is (\S+) \(", e)
            if m:
                fix[m.group(1)] = m.group(2)
        self.integ = {}
        for r in rows:
            st = fix.get(r[0], r[1])
            self.integ[self.img(r[0])] = (st, r[2], r[3])
        self.exif = {}
        n = 0
        for ln in text_of(self.p("exif_orientation_scan.jsonl")).splitlines():
            if not ln.strip():
                continue
            n += 1
            o = json.loads(ln)
            self.exif[self.img(o["image"])] = int(o["exif_orientation"])
        self.parsed["exif_orientation_scan.jsonl"] = n
        hdr, rows, errata, _ = pdf_register(self.p("orientation_corrections.pdf"))
        self.parsed["orientation_corrections.pdf"] = len(rows)
        fix = {}
        for e in errata:
            m = re.match(r"Correction (\S+): orientation is (\d)\.", e)
            if m:
                fix[m.group(1)] = int(m.group(2))
        self.corr = {}
        for r in rows:
            if r[3] != "confirmed":
                continue
            i = self.img(r[1])
            key = (instant(r[4]), r[0])
            o = fix.get(r[0], int(r[2]))
            if i not in self.corr or key > self.corr[i][0]:
                self.corr[i] = (key, o)

    def image_geometry(self, i):
        o = self.exif.get(i, 0) or 1
        if i in self.corr:
            o = self.corr[i][1]
        st, dw, dh = self.integ[i]
        w, h = self.geo[i]
        if (w, h) == (0, 0) or st == "REENCODED":
            w, h = int(dw), int(dh)
        W, H = (h, w) if o in (6, 8) else (w, h)
        return o, w, h, W, H

    # exclusions -------------------------------------------------------
    def load_exclusion_sources(self):
        root = ET.parse(self.p("image_lifecycle_events.xml")).getroot()
        evs, seen = [], set()
        n = 0
        for e in root.iter("event"):
            n += 1
            if e.get("id") in seen:
                continue
            seen.add(e.get("id"))
            t = instant(e.get("at"))
            if t <= CUTOFF and e.get("type") in ("withdrawn", "restored"):
                evs.append((t, int(e.get("seq")), self.img(e.get("image")), e.get("type")))
        self.parsed["image_lifecycle_events.xml"] = n
        evs.sort(key=lambda x: (x[0], x[1]))
        self.withdrawn = {}
        for _, _, i, typ in evs:
            self.withdrawn[i] = typ == "withdrawn"
        hdr, rows, errata, _, _ = docx_register(self.p("exclusion_policy.docx"))
        self.parsed["exclusion_policy.docx"] = len(rows)
        fix = {}
        for e in errata:
            m = re.match(r"Request (\S+): status is (\w+)\.", e)
            if m:
                fix[m.group(1)] = m.group(2)
        self.hold = {}
        for r in rows:
            i = self.img(r[1])
            st = fix.get(r[0], r[2])
            if st == "HOLD":
                self.hold[i] = True
            else:
                self.hold.setdefault(i, False)
        box = mailbox.mbox(str(self.p("privacy_requests.mbox")), create=False)
        msgs = []
        n = 0
        for key in box.keys():
            m = email.message_from_bytes(box.get_bytes(key), policy=email.policy.default)
            n += 1
            sender = email.utils.parseaddr(m["From"])[1]
            t = int(email.utils.parsedate_to_datetime(m["Date"]).timestamp())
            subj = str(m["Subject"] or "").strip()
            if not sender.endswith("@privacy-office.skye.example") or subj.startswith("Fwd:"):
                continue
            if not (REG_DATE < t <= CUTOFF):
                continue
            act, ident = subj.split(None, 1)
            msgs.append((t, act, self.img(ident)))
        self.parsed["privacy_requests.mbox"] = n
        for t, act, i in sorted(msgs, key=lambda x: x[0]):
            if act == "TAKEDOWN":
                self.hold[i] = True
            elif act == "RELEASE":
                self.hold[i] = False
        rows = read_delimited(self.p("privacy_register_export.tsv"), "\t")
        self.parsed["privacy_register_export.tsv"] = len(rows)
        for r in rows:
            if r["status"].strip() == "LEGAL-HOLD":
                self.hold[self.img(r["image_id"])] = True
        self.board = {}
        for name in ("release_governance.docx", "release_governance_v2_signed.docx"):
            hdr, rows, errata, _, _ = docx_register(self.p(name))
            self.parsed[name] = len(rows)
            fix = {}
            for e in errata:
                m = re.match(r"Decision (\S+): decision is (\w+)\.", e)
                if m:
                    fix[m.group(1)] = m.group(2)
            for r in rows:
                t = day_start(r[3])
                if t > CUTOFF:
                    continue
                i = self.img(r[1])
                key = (t, r[0])
                if i not in self.board or key > self.board[i][0]:
                    self.board[i] = (key, fix.get(r[0], r[2]))
        hdr, rows, errata, _, prose = docx_register(self.p("release_governance.docx"))
        text = " ".join(v for k, s, v in prose if k == "p")
        self.margin = Fraction(Decimal(re.search(r"at least ([0-9.]+) above", text).group(1)))
        self.tolerance = Fraction(Decimal(re.search(r"not more than ([0-9.]+) below", text).group(1)))
        self.protected = [c.strip() for c in re.search(r"Protected classes: ([a-z_, ]+)\.", text).group(1).split(",")]
        m = re.search(r"Target precision for operating points is ([0-9.]+) for protected classes and ([0-9.]+) for every other class", text)
        self.tp_prot, self.tp_other = Fraction(Decimal(m.group(1))), Fraction(Decimal(m.group(2)))

    # leakage ----------------------------------------------------------
    @staticmethod
    def hexval(s):
        s = str(s).strip().lower()
        if s.startswith("0x"):
            s = s[2:]
        elif s.startswith("x"):
            s = s[1:]
        return int(s, 16)

    def load_leakage(self):
        idx_used = set()
        for r in self.review:
            idx_used.update(self.train_index[r])
        hashes = set()
        if "v7-train" in idx_used:
            t = pq.read_table(self.p("train_hash_index_a.parquet")).to_pydict()
            self.parsed["train_hash_index_a.parquet"] = len(t["dhash_hex"])
            for h, st, tag in zip(t["dhash_hex"], t["status"], t["set_tag"]):
                if st == "active" and tag == "v7-train":
                    hashes.add(self.hexval(h))
            rows = read_delimited(self.p("train_hash_index_b.csv"), ",", {"status": "state"})
            self.parsed["train_hash_index_b.csv"] = len(rows)
            for r in rows:
                v = r["dhash_u64"].strip()
                h = self.hexval(v) if v.lower().startswith(("0x", "x")) else int(v)
                if r["state"].strip() == "A" and r["set_tag"].strip() == "v7-train":
                    hashes.add(h)
            con = sqlite3.connect(str(self.p("train_hash_index_c.db")))
            rows = con.execute("SELECT h, purged, set_tag FROM train_hashes").fetchall()
            con.close()
            self.parsed["train_hash_index_c.db"] = len(rows)
            for h, pg, tag in rows:
                if not pg and tag == "v7-train":
                    hashes.add(self.hexval(h))
            n = 0
            for ln in text_of(self.p("train_hash_index_d.txt")).splitlines():
                if not ln.strip() or ln.startswith("#"):
                    continue
                n += 1
                if ln[17:25].strip() == "v7-train" and ln[26:27] == "A":
                    hashes.add(self.hexval(ln[0:16]))
            self.parsed["train_hash_index_d.txt"] = n
            n = 0
            for ln in text_of(self.p("train_hash_index_e.jsonl")).splitlines():
                if not ln.strip():
                    continue
                n += 1
                o = json.loads(ln)
                h = int(o["h_dec"]) if "h_dec" in o else self.hexval(o["h"])
                if not o["purged"] and o["tag"] == "v7-train":
                    hashes.add(h)
            self.parsed["train_hash_index_e.jsonl"] = n
            n = 0
            for ln in text_of(self.p("train_hash_index_h.txt")).splitlines():
                if not ln.strip() or ln.startswith("#"):
                    continue
                n += 1
                v = ln[0:20].strip()
                h = self.hexval(v) if v.lower().startswith(("0x", "x")) else int(v)
                if ln[21:29].strip() == "v7-train" and ln[30:31] == "A":
                    hashes.add(h)
            self.parsed["train_hash_index_h.txt"] = n
            t = pq.read_table(self.p("train_hash_index_f_dedup.parquet")).to_pydict()
            self.parsed["train_hash_index_f_dedup.parquet"] = len(t["dhash_hex"])
            for h, src, pg in zip(t["dhash_hex"], t["source_shard"], t["purged"]):
                if src == "g" and not pg:
                    hashes.add(self.hexval(h))
        n = 0
        for ln in text_of(self.p("train_hash_index_legacy.txt")).splitlines():
            if not ln.strip() or ln.startswith("#"):
                continue
            n += 1
            tag = ln[17:29].strip()
            if tag == "v6-core" and "v6-core" in idx_used and ln[30:31] == "A":
                hashes.add(self.hexval(ln[0:16]))
        self.parsed["train_hash_index_legacy.txt"] = n
        hashes.discard(0)
        self.buckets = [dict() for _ in range(5)]
        for h in hashes:
            for c in range(5):
                self.buckets[c].setdefault((h >> (13 * c)) & 0x1FFF, []).append(h)
        t = pq.read_table(self.p("frame_dhash.parquet")).to_pydict()
        self.parsed["frame_dhash.parquet"] = len(t["image_id"])
        self.dhash = {}
        for i, v, bo in zip(t["image_id"], t["dhash"], t["byte_order"]):
            u = v & 0xFFFFFFFFFFFFFFFF
            if bo == "be":
                u = int.from_bytes(u.to_bytes(8, "big"), "little")
            self.dhash[self.img(i)] = u
        data = json.loads(text_of(self.p("leakage_waivers.json")))
        self.parsed["leakage_waivers.json"] = len(data["waivers"])
        latest = {}
        for w in data["waivers"]:
            key = (self.img(w["image"]), self.hexval(w["train_dhash"]))
            k2 = (instant(w["decided_at"]), w["waiver_id"])
            if key not in latest or k2 > latest[key][0]:
                latest[key] = (k2, w)
        self.waived = set(k for k, (_, w) in latest.items() if w["status"] == "granted" and (w["expires_at"] is None or instant(w["expires_at"]) > CUTOFF))
        hdr, rows, errata, _ = pdf_register(self.p("training_sequence_register.pdf"))
        self.parsed["training_sequence_register.pdf"] = len(rows)
        fix = {}
        for e in errata:
            m = re.match(r"Sequence (\S+): status is (\S+)\.", e)
            if m:
                fix[self.seq(m.group(1))] = m.group(2)
        self.trained_seq = set()
        for r in rows:
            s = self.seq(r[0])
            if fix.get(s, r[1]) == "trained" and r[2] in idx_used:
                self.trained_seq.add(s)

    def leak(self, i):
        h = self.dhash.get(i, 0)
        if not h:
            return None
        cands = set()
        for c in range(5):
            cands.update(self.buckets[c].get((h >> (13 * c)) & 0x1FFF, ()))
        best = 65
        for th in cands:
            if (i, th) in self.waived:
                continue
            best = min(best, bin(h ^ th).count("1"))
        if best == 0:
            return "LEAK_EXACT"
        if best <= 4:
            return "LEAK_NEAR"
        return None

    # annotation rules -------------------------------------------------
    def load_annotation_rules(self):
        hdr, rows, errata, _, _ = docx_register(self.p("data_authority_policy.docx"))
        self.parsed["data_authority_policy.docx"] = len(rows)
        fix = {}
        for e in errata:
            m = re.match(r"Image (\S+) assigned on (\S+): vendor is (\w+)\.", e)
            if m:
                fix[(m.group(1), m.group(2))] = m.group(3)
        self.vendor = {}
        for r in rows:
            i = self.img(r[0])
            v = fix.get((i, r[2]), r[1])
            t = day_start(r[2])
            if i not in self.vendor or t >= self.vendor[i][0]:
                self.vendor[i] = (t, v)
        hdr, rows, errata, _, _ = docx_register(self.p("annotation_batch_conventions.docx"))
        self.parsed["annotation_batch_conventions.docx"] = len(rows)
        fix = {}
        for e in errata:
            m = re.match(r"Batch (\S+) was delivered as (\S+) in the (\w+) frame", e)
            if m:
                fix[m.group(1).upper()] = (m.group(2), m.group(3))
        self.conv = {}
        for r in rows:
            b = r[0].strip().upper()
            fmt = CONV_SYN.get(r[2], r[2])
            frame = r[3] if r[3] != "-" else DEFAULT_CONV[r[1]][1]
            if b in fix:
                fmt, frame = fix[b]
            self.conv[b] = (fmt, frame, r[4] == "Y")
        hdr, rows, errata, _, _ = docx_register(self.p("vendor_batch_receipts.docx"))
        self.parsed["vendor_batch_receipts.docx"] = len(rows)
        fix = {}
        for e in errata:
            m = re.match(r"Batch (\S+): received at (\S+)\.", e)
            if m:
                fix[m.group(1).upper()] = m.group(2)
        self.ontime = set()
        for r in rows:
            b = r[0].strip().upper()
            if instant(fix.get(b, r[2])) <= CUTOFF:
                self.ontime.add(b)
        reg_hdr, reg_rows, xerr, tables2 = self._tax
        self.parsed["taxonomy_v3_charter.docx"] = len(reg_rows)
        fix = {}
        for e in xerr:
            m = re.match(r"Project (\S+) label (.+): class is (\S+)\.", e)
            if m:
                fix[(m.group(1).upper(), m.group(2))] = m.group(3)
        self.nlx = {}
        for r in reg_rows:
            p = r[0].upper()
            self.nlx[(p, r[1])] = (fix.get((p, r[1]), r[2]), r[3])
        hdr, rows, errata, _ = pdf_register(self.p("ks_class_codebook.pdf"))
        self.parsed["ks_class_codebook.pdf"] = len(rows)
        fix = {}
        for e in errata:
            m = re.match(r"Project (\S+) code (\d+) from (\S+): class is (\S+)\.", e)
            if m:
                fix[(m.group(1).upper(), int(m.group(2)), m.group(3))] = m.group(4)
        self.ksb = {}
        for r in rows:
            p, code = r[0].upper(), int(r[1])
            frm = instant(r[4])
            to = None if r[5] == "-" else instant(r[5])
            cls = fix.get((p, code, datetime.fromtimestamp(frm, timezone.utc).strftime("%Y-%m-%d")), r[2])
            self.ksb.setdefault((p, code), []).append((frm, to, cls, r[3]))
        data = yaml.safe_load(text_of(self.p("ob_label_aliases.yaml")))
        self.parsed["ob_label_aliases.yaml"] = len(data["aliases"])
        self.obx = {}
        for e in data["aliases"]:
            self.obx[(str(e["project"]).upper(), str(e["alias"]))] = (e["class"], e["disposition"] or "eval")
        hdr, rows, notes = md_register(self.p("annotation_errata_register.md"))
        self.parsed["annotation_errata_register.md"] = len(rows)
        fix = {}
        for e in notes:
            m = re.match(r"(ER-\S+): value is (.*)\.$", e)
            if m:
                fix[m.group(1)] = "" if m.group(2) == "(empty)" else m.group(2)
        self.errata = {}
        for r in rows:
            eff = day_start(r[4])
            if eff > CUTOFF:
                continue
            self.errata.setdefault(self.ann(r[1]), []).append((eff, r[0], r[2], fix.get(r[0], r[3])))
        for v in self.errata.values():
            v.sort()
        tables, errata = html_tables(self.p("labeling_qa_portal.html"))
        reg = [t for k, t in tables.items() if k.startswith("Appendix")][0]
        self.parsed["labeling_qa_portal.html"] = len(reg) - 1
        fix = {}
        for e in errata:
            m = re.match(r"Decision on (\S+) revision (\d+) at (\S+) is (\w+)\.", e)
            if m:
                fix[(m.group(1), int(m.group(2)), instant(m.group(3)))] = m.group(4)
        self.qa = {}
        for r in reg[1:]:
            a, rev, t = self.ann(r[0]), int(r[1]), instant(r[3])
            dec = fix.get((a, rev, t), r[2])
            if (a, rev) not in self.qa or t >= self.qa[(a, rev)][0]:
                self.qa[(a, rev)] = (t, dec)
        sheets = xlsx_sheets(self.p("labeling_qa_export.xlsx"))
        self.parsed["labeling_qa_export.xlsx"] = sum(len(v) for v in sheets.values())
        for rows in sheets.values():
            for r in rows:
                if str(r["state"]).strip() != "final":
                    continue
                t = instant(r["decided_at"])
                if not (QA_SNAP < t <= CUTOFF):
                    continue
                a, rev = self.ann(r["annotation_id"]), int(r["revision"])
                if (a, rev) not in self.qa or t >= self.qa[(a, rev)][0]:
                    self.qa[(a, rev)] = (t, str(r["decision"]))
        sheets = xlsx_sheets(self.p("relabel_campaign_2026q3.xlsx"))
        self.parsed["relabel_campaign_2026q3.xlsx"] = sum(len(v) for v in sheets.values())
        self.camp_item = {}
        for r in sheets["items"]:
            self.camp_item[self.img(r["image_id"])] = str(r["item_id"])
        self.camp_boxes = {}
        for r in sheets["boxes"]:
            self.camp_boxes.setdefault(str(r["item_id"]), []).append(r)
        data = json.loads(text_of(self.p("relabel_campaign_status.json")))
        self.parsed["relabel_campaign_status.json"] = len(data["statuses"])
        st = {}
        for s in data["statuses"]:
            t = instant(s["at"])
            if t > CUTOFF:
                continue
            if s["item"] not in st or t >= st[s["item"]][0]:
                st[s["item"]] = (t, s["status"])
        self.camp_status = {k: v[1] for k, v in st.items()}

    # vendor records ---------------------------------------------------
    def load_annotations(self):
        recs = []

        def add(vendor, src, d):
            d["vendor"], d["src"] = vendor, src
            recs.append(d)

        nl_files = sorted(f.name for f in self.root.iterdir() if f.name.startswith("nl_boxes_"))
        for name in nl_files:
            if name.endswith(".xlsx"):
                sheets = xlsx_sheets(self.p(name))
                rows = [r for v in sheets.values() for r in v]
            else:
                rows = read_delimited(self.p(name), "\t" if name.endswith(".tsv") else ",")
            self.parsed[name] = len(rows)
            for k, r in enumerate(rows):
                add("NL", name, {"k": k, "ann": self.ann(r["annotation_id"]), "image": self.img(r["image_id"]),
                                 "batch": str(r["batch_id"]).strip().upper(), "project": str(r["project"]).upper(),
                                 "label": str(r["label"]), "c": [str(r["coord_%d" % j]) for j in (1, 2, 3, 4)],
                                 "crowd": 1 if str(r["crowd"]).strip() == "Y" else 0, "rev": int(num(r["revision"])),
                                 "deleted": str(r["status"]).strip() != "live", "px": False, "ts": None})
        ks_files = sorted(f.name for f in self.root.iterdir() if f.name.startswith("ks_boxes_"))
        for name in ks_files:
            rows = []
            if name.endswith(".jsonl"):
                for ln in text_of(self.p(name)).splitlines():
                    if ln.strip():
                        rows.append(json.loads(ln, parse_float=Decimal))
            elif name.endswith(".json"):
                rows = json.loads(text_of(self.p(name)), parse_float=Decimal)["records"]
            elif name.endswith(".parquet"):
                t = pq.read_table(self.p(name)).to_pylist()
                for o in t:
                    o = dict(o)
                    o["bbox_px" if o["bbox_unit"] == "px" else "bbox"] = [o["b1"], o["b2"], o["b3"], o["b4"]]
                    rows.append(o)
            else:
                for o in read_delimited(self.p(name), ","):
                    o["bbox_px" if o["bbox_unit"].strip() == "px" else "bbox"] = [o["b1"], o["b2"], o["b3"], o["b4"]]
                    o["img"] = o["image_id"]
                    o["proj"] = o["project"]
                    o["rev"] = o.get("revision", o.get("rev"))
                    rows.append(o)
            self.parsed[name] = len(rows)
            for k, o in enumerate(rows):
                px = "bbox_px" in o
                c = o["bbox_px"] if px else o["bbox"]
                ts = int(num(o["ts"]))
                if ts < 100000000000:
                    ts *= 1000
                add("KS", name, {"k": k, "ann": "KS-%07d" % int(num(o["id"])), "image": self.img(o.get("img", o.get("image_id"))),
                                 "batch": str(o["batch"]).strip().upper(), "project": str(o["proj"]).upper(),
                                 "label": int(num(o["code"])), "c": [str(x) for x in c], "crowd": 1 if int(num(o["crowd"])) == 1 else 0,
                                 "rev": int(num(o["rev"])), "deleted": str(o["state"]) != "active", "px": px, "ts": ts // 1000})
        ob_files = sorted(f.name for f in self.root.iterdir() if f.name.startswith("ob_boxes_"))
        for name in ob_files:
            root = ET.parse(self.p(name)).getroot()
            n = 0
            for k, o in enumerate(root.iter("object")):
                n += 1
                bb = o.find("bndbox")
                add("OB", name, {"k": k, "ann": self.ann(o.get("id")), "image": self.img(o.get("image")),
                                 "batch": o.get("batch").strip().upper(), "project": o.get("project").upper(),
                                 "label": o.findtext("name"), "c": [bb.get("c%d" % j) for j in (1, 2, 3, 4)],
                                 "crowd": 1 if int(o.findtext("crowd")) == 1 else 0, "rev": int(o.findtext("revision")),
                                 "deleted": o.findtext("deleted").strip() == "1", "px": False, "ts": None})
            self.parsed[name] = n
        # the short delivery and its re-extract
        short = "nl_boxes_batch02.csv"
        present = self.parsed[short]
        by_img = {}
        for r in recs:
            src = r["src"]
            if src == "nl_boxes_batch02_reextract.csv":
                if r["k"] < present:
                    continue
            elif src in ("ks_boxes_resubmitted.json", "ob_boxes_resubmitted.xml"):
                if not self.conv.get(r["batch"], (0, 0, False))[2]:
                    continue
            elif r["vendor"] in ("KS", "OB") and self.conv.get(r["batch"], (0, 0, False))[2]:
                continue
            if r["batch"] not in self.ontime:
                continue
            by_img.setdefault(r["image"], []).append(r)
        self.vrecs = by_img

    def box_from(self, r, i):
        o, w, h, W, H = self.image_geometry(i)
        fmt, frame, _ = self.conv[r["batch"]]
        c = [num(x) for x in r["c"]]
        fw, fh = (W, H) if frame == "upright" else (w, h)
        if fmt == "xywh":
            b = (c[0], c[1], c[0] + c[2], c[1] + c[3])
        elif fmt == "xyxy":
            b = tuple(c)
        elif fmt == "xyxy_inclusive":
            b = (c[0], c[1], c[2] + 1, c[3] + 1)
        else:
            if r["px"]:
                c = [c[0] / fw, c[1] / fh, c[2] / fw, c[3] / fh]
            b = ((c[0] - c[2] / 2) * fw, (c[1] - c[3] / 2) * fh, (c[0] + c[2] / 2) * fw, (c[1] + c[3] / 2) * fh)
        if frame == "stored":
            x1, y1, x2, y2 = b
            if o == 3:
                b = (w - x2, h - y2, w - x1, h - y1)
            elif o == 6:
                b = (h - y2, x1, h - y1, x2)
            elif o == 8:
                b = (y1, w - x2, y2, w - x1)
        b = [rnd(v) for v in b]
        return (max(0, min(W, b[0])), max(0, min(H, b[1])), max(0, min(W, b[2])), max(0, min(H, b[3])))

    def label_of(self, r):
        if r["vendor"] == "NL":
            return self.nlx.get((r["project"], r["label"]))
        if r["vendor"] == "OB":
            return self.obx.get((r["project"], r["label"]))
        for frm, to, cls, disp in self.ksb.get((r["project"], r["label"]), []):
            if frm <= r["ts"] and (to is None or r["ts"] < to):
                return (cls, disp)
        return None

    def ground_truth(self, i):
        item = self.camp_item.get(i)
        o, w, h, W, H = self.image_geometry(i)
        if item is not None and self.camp_status.get(item) == "approved":
            out = []
            for b in self.camp_boxes.get(item, []):
                box = tuple(int(num(b[k])) for k in ("x1", "y1", "x2", "y2"))
                area = (box[2] - box[0]) * (box[3] - box[1])
                out.append((str(b["box_id"]), str(b["class"]), box, int(num(b["crowd"])) == 1 or area < 64, "CAMPAIGN"))
            return out, True
        v = self.vendor[i][1]
        rows = [r for r in self.vrecs.get(i, []) if r["vendor"] == v]
        if not rows:
            return [], False
        anns = {}
        for r in rows:
            anns.setdefault(r["ann"], []).append(r)
        out = []
        for a in sorted(anns):
            live = [r for r in anns[a] if self.qa.get((a, r["rev"]), (0, ""))[1] != "rejected"]
            if not live:
                continue
            top = max(live, key=lambda r: r["rev"])
            if top["deleted"]:
                continue
            m = self.label_of(top)
            if m is None:
                continue
            cls, disp = m
            box = self.box_from(top, i)
            dead = False
            for eff, eid, act, val in self.errata.get(a, []):
                if act == "VOID":
                    dead = True
                elif act == "RECLASS":
                    cls = val
                elif act == "REBOX":
                    box = tuple(int(x) for x in val.split(","))
            if dead or disp == "drop":
                continue
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            area = (box[2] - box[0]) * (box[3] - box[1])
            out.append((a, cls, box, disp == "ignore" or top["crowd"] == 1 or area < 64, v))
        return out, True

    # image decisions --------------------------------------------------
    def decide_images(self):
        self.info, self.reason, self.gt = {}, {}, {}
        for i in self.cands:
            c, site, t = self.capture(i)
            o, w, h, W, H = self.image_geometry(i)
            self.info[i] = (c, site, t, o, W, H)
            rs = []
            if self.withdrawn.get(i):
                rs.append("WITHDRAWN")
            if not (WIN_LO <= t < WIN_HI):
                rs.append("OUT_OF_WINDOW")
            if self.integ[i][0] == "FAIL":
                rs.append("CORRUPT")
            if self.hold.get(i):
                rs.append("PRIVACY_HOLD")
            if i in self.board and self.board[i][1] == "EXCLUDE":
                rs.append("BOARD_OVERRIDE")
            lk = self.leak(i)
            if lk:
                rs.append(lk)
            if self.seq_of.get(i) in self.trained_seq:
                rs.append("LEAK_SEQUENCE")
            g, labeled = self.ground_truth(i)
            if not labeled:
                rs.append("UNLABELED")
            self.reason[i] = min(rs, key=PRECEDENCE.index) if rs else None
            self.gt[i] = g
        self.evals = [i for i in self.cands if self.reason[i] is None]

    # detections -------------------------------------------------------
    def load_detection_sources(self):
        data = tomllib.loads(text_of(self.p("rerun_batches.toml")))
        self.parsed["rerun_batches.toml"] = len(data["rerun"])
        self.rerun = {}
        for e in data["rerun"]:
            self.rerun[(e["run"], self.img(e["image"]))] = e
        hdr, rows, errata, _ = pdf_register(self.p("node_quarantine_report.pdf"))
        self.parsed["node_quarantine_report.pdf"] = len(rows)
        rows = [list(r) for r in rows]
        for e in errata:
            m = re.match(r"Row (\d+) \((\S+), run (\S+)\): node is (\w+)\.", e)
            if m:
                rows[int(m.group(1)) - 1][1] = m.group(4)
        self.quar = set((r[0], r[1], self.img(r[2])) for r in rows if r[3] == "quarantined")
        self.prep = {}
        for f in sorted(self.root.glob("preprocess_*.log")):
            node = f.stem.split("_", 1)[1]
            n = 0
            for ln in text_of(f).splitlines():
                if not ln.strip():
                    continue
                n += 1
                rec = self.parse_prep(node, ln)
                if rec is None:
                    continue
                run, i, sc, px, py, a, ok = rec
                if not ok:
                    continue
                key = (node, run, i)
                if key not in self.prep or a > self.prep[key][0]:
                    self.prep[key] = (a, sc, px, py)
            self.parsed[f.name] = n
        self.node_rows = {}
        self.store_rows = {"n6": {}, "n6-replica": {}, "n2-replay": {}}
        self.store_prep = {"n6": {}, "n6-replica": {}}
        for f in sorted(self.root.iterdir()):
            m = re.fullmatch(r"preds_(r\d)_(n\d)(_replay)?\.(\w+)", f.name)
            if not m:
                continue
            node = m.group(2)
            rows = self.read_preds(f, node)
            self.parsed[f.name] = len(rows)
            if m.group(3):
                tgt = self.store_rows["n2-replay"]
                seen = set()
                for d in rows:
                    key = (d["run"], d["det"], d["image"])
                    if key in seen:
                        continue
                    seen.add(key)
                    tgt.setdefault((d["run"], d["image"]), []).append(d)
                continue
            for d in rows:
                self.node_rows.setdefault((node, d["run"], d["image"]), {}).setdefault(d["det"], d)
        for store, name in (("n6", "node6_rerun_store.db"), ("n6-replica", "node6_ingest_replica.db")):
            con = sqlite3.connect(str(self.p(name)))
            dets = con.execute("SELECT run_id, image_id, det_id, class_index, cx, cy, w, h, score_bp FROM dets").fetchall()
            preps = con.execute("SELECT run_id, image_id, scale, pad_x, pad_y, status FROM preprocess").fetchall()
            con.close()
            self.parsed[name] = len(dets)
            for run, i, sc, px, py, st in preps:
                if st == "ok":
                    self.store_prep[store][(run, self.img(i))] = (Fraction(sc), px, py)
            seen = set()
            for run, i, det, ci, cx, cy, w, h, sbp in dets:
                ii = self.img(i)
                key = (run, det, ii)
                if key in seen:
                    continue
                seen.add(key)
                cx, cy, w, h = num(cx), num(cy), num(w), num(h)
                self.store_rows[store].setdefault((run, ii), []).append(
                    {"run": run, "image": ii, "det": det, "ci": ci, "box": (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                     "score": None if sbp == -1 else Fraction(sbp, 10000), "prep": None})

    def parse_prep(self, node, ln):
        ln = ln.rstrip()
        m = re.match(r"PREP\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|(-?\d+)\|(-?\d+)\|(\d+)/(\d+)\|(\w+)", ln)
        if m:
            return (m.group(2), self.img(m.group(3)), Fraction(m.group(4)), int(m.group(5)), int(m.group(6)), int(m.group(7)), m.group(9).lower() == "ok")
        if node == "n1":
            m = re.search(r"run=(\S+) img=(\S+) .*scale=(\d+/\d+) pad=(-?\d+),(-?\d+) attempt=(\d+)/(\d+) status=(\w+)", ln)
            if m:
                return (m.group(1), self.img(m.group(2)), Fraction(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), m.group(8) == "ok")
        elif node == "n2":
            m = re.search(r'image="([^"]+)" run="([^"]+)" letterbox\(scale=(\d+/\d+), pad_x=(-?\d+), pad_y=(-?\d+)\) try=(\d+) of (\d+) (\w+)', ln)
            if m:
                return (self.model_run.get(m.group(2), m.group(2)), self.img(m.group(1)), Fraction(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), m.group(8) == "OK")
        elif node == "n3":
            p = ln.split("|")
            if len(p) >= 9:
                a, n_ = p[7].split("/")
                return (p[2], self.img(p[3]), Fraction(p[4]), int(p[5]), int(p[6]), int(a), p[8].split()[0].lower() == "ok")
        elif node == "n4":
            m = re.search(r"evalprep\[\d+\]: (\S+) (.+?) scale (\d+/\d+) pads (-?\d+) (-?\d+) attempt (\d+) of (\d+) -> (\w+)", ln)
            if m:
                return (m.group(1), self.img(m.group(2)), Fraction(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), m.group(8) == "ok")
        elif node == "n5":
            m = re.search(r"run=(\S+) image=(\S+) s=\S+ \((\d+/\d+)\) px=(-?\d+) py=(-?\d+) a=(\d+)/(\d+) (\w+)", ln)
            if m:
                return (m.group(1), self.img(m.group(2)), Fraction(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), m.group(8) == "OK")
        return None

    def score_of(self, raw):
        """Return the score as a fraction, or None for the suppression sentinel."""
        if raw is None:
            return None
        s = str(raw).strip()
        if s.endswith("%"):
            return num(s[:-1]) / 100
        if num(s) == -1:
            return None
        return num(s)

    def read_preds(self, f: Path, node: str):
        out = []
        q2 = lambda v: Fraction(Decimal(repr(v)).quantize(Decimal("0.01"))) if isinstance(v, float) else num(v)
        runid = lambda r: self.model_run.get(r, r)
        if f.suffix in (".csv", ".tsv"):
            for r in read_delimited(f, "\t" if f.suffix == ".tsv" else ","):
                d = {"run": runid(r.get("run") or r.get("model")), "image": self.img(r["image_id"]), "det": int(num(r["det_id"])),
                     "ci": int(num(r["class_index"])), "box": tuple(num(r[k]) for k in ("x1", "y1", "x2", "y2")),
                     "score": self.score_of(r["score"]), "prep": None}
                if "lb_scale" in r:
                    d["prep"] = (Fraction(r["lb_scale"]), int(num(r["lb_pad_x"])), int(num(r["lb_pad_y"])))
                out.append(d)
        elif f.suffix == ".jsonl":
            for ln in text_of(f).splitlines():
                if not ln.strip():
                    continue
                o = json.loads(ln, parse_float=Decimal)
                cx, cy, w, h = (num(v) for v in o["box_cxcywh"])
                if "score" in o:
                    sc = self.score_of(o["score"])
                else:
                    v = o["score_pct"]
                    sc = None if num(v) == -1 else num(v) / 100
                d = {"run": runid(o["run"]), "image": self.img(o["image"]), "det": int(re.sub(r"\D", "", o["det"])), "ci": int(o["cls"]),
                     "box": (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), "score": sc, "prep": None}
                if "letterbox" in o:
                    lb = o["letterbox"]
                    d["prep"] = (Fraction(lb["scale"]), int(lb["pad_x"]), int(lb["pad_y"]))
                out.append(d)
        elif f.suffix == ".parquet":
            for o in pq.read_table(f).to_pylist():
                sc = o["score"]
                score = None if sc == -1 else (Fraction(sc, 10000) if o["score_unit"] == "bp" else Fraction(sc, 1000))
                out.append({"run": runid(o["run_tag"]), "image": self.img(o["image_id"]), "det": int(o["det_id"]), "ci": int(o["class_index"]),
                            "box": tuple(q2(o[k]) for k in ("x1", "y1", "x2", "y2")), "score": score, "prep": None})
        elif f.suffix == ".xml":
            for e in ET.parse(f).getroot().iter("det"):
                b = e.find("box")
                se = e.find("score")
                if se.get("unit") == "pct":
                    score = None if num(se.text) == -1 else num(se.text) / 100
                else:
                    score = self.score_of(se.text)
                out.append({"run": runid(e.get("run")), "image": self.img(e.get("image")), "det": int(re.sub(r"\D", "", e.get("id"))),
                            "ci": int(e.get("cls")), "box": tuple(num(b.get(k)) for k in ("x1", "y1", "x2", "y2")), "score": score, "prep": None})
        elif f.suffix == ".xlsx":
            for rows in xlsx_sheets(f).values():
                for r in rows:
                    out.append({"run": runid(r["model"]), "image": self.img(r["image_id"]), "det": int(num(r["det_id"])), "ci": int(num(r["class_index"])),
                                "box": tuple(q2(r[k]) for k in ("x1", "y1", "x2", "y2")), "score": self.score_of(r["score"]),
                                "prep": (Fraction(str(r["lb_scale"])), int(num(r["lb_pad_x"])), int(num(r["lb_pad_y"])))})
        return out

    def load_calibration(self):
        self.calib = {}

        def put(run, cls, k, x, y):
            self.calib.setdefault(run, {}).setdefault(cls, {})[k] = (x, y)

        data = yaml.safe_load(text_of(self.p("calibration_r1_v64.yaml")))["calibration"]
        self.parsed["calibration_r1_v64.yaml"] = len(data["knots"])
        for e in data["knots"]:
            y = num(e["y_pct"]) / 100 if "y_pct" in e else num(e["y"])
            put(data["run"], e["class"], int(e["k"]), num(e["x"]), y)
        data = tomllib.loads(text_of(self.p("calibration_r2_rc1.toml")))
        self.parsed["calibration_r2_rc1.toml"] = len(data["knot"])
        for e in data["knot"]:
            y = num(e["y"])
            if e.get("unit") == "pct":
                y = y / 100
            put(data["run"], e["class"], int(e["k"]), num(e["x"]), y)
        sec, run, n = None, None, 0
        for ln in text_of(self.p("calibration_r4_ema.ini")).splitlines():
            ln = ln.strip()
            if not ln or ln.startswith((";", "#")):
                continue
            if ln.startswith("["):
                sec = ln.strip("[]")
                continue
            key, val = (x.strip() for x in ln.split("=", 1))
            if sec == "meta":
                if key == "run":
                    run = val
                continue
            n += 1
            m = re.match(r"x=(\S+) y(%?)=(\S+)", val.split(" ;")[0].strip())
            y = num(m.group(3))
            if m.group(2):
                y = y / 100
            put(run, sec, int(key[1:]), num(m.group(1)), y)
        self.parsed["calibration_r4_ema.ini"] = n
        deferred = []
        for name in ("calibration_certificate_rc2.pdf", "calibration_certificate_rc2_reissue.pdf"):
            hdr, rows, errata, prose = pdf_register(self.p(name))
            self.parsed[name] = len(rows)
            model = re.search(r"CALIBRATION CERTIFICATE - (\S+)", prose[0]).group(1)
            run = self.model_run[model]
            rows = [list(r) for r in rows]
            for e in errata:
                m = re.match(r"Row (\d+) \(class (\S+), knot (\d+)\): y is (\S+)\.", e)
                if m:
                    rows[int(m.group(1)) - 1][3] = m.group(4)
            if "reissue" not in name:
                text = " ".join(prose)
                m = re.search(r"knots of the classes ([a-z_, ]+?) are deferred", text)
                deferred = [c.strip() for c in m.group(1).split(",")] if m else []
                for r in rows:
                    y = num(r[3][:-1]) / 100 if r[3].endswith("%") else num(r[3])
                    put(run, r[0], int(r[1]), num(r[2]), y)
            else:
                for r in rows:
                    if r[0] in deferred:
                        y = num(r[3][:-1]) / 100 if r[3].endswith("%") else num(r[3])
                        put(run, r[0], int(r[1]), num(r[2]), y)
        self.knots = {}
        for run, by in self.calib.items():
            for cls, kn in by.items():
                ks = sorted(kn)
                self.knots[(run, cls)] = ([kn[k][0] for k in ks], [kn[k][1] for k in ks])

    def calibrate(self, run, cls, s):
        xs, ys = self.knots[(run, cls)]
        lo, hi = 0, len(xs) - 2
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if xs[mid] <= s:
                lo = mid
            else:
                hi = mid - 1
        return ys[lo] + (ys[lo + 1] - ys[lo]) * (s - xs[lo]) / (xs[lo + 1] - xs[lo])

    def eval_class(self, run, ci):
        lab = self.labelmap[run].get(ci)
        if lab is None:
            return None
        if lab in self.model_vocab:
            return self.model_vocab[lab]
        return lab if lab in self.tax_classes else None

    def build_detections(self):
        self.tax_classes = set(c for c in re.findall(r"[a-z_]+", "pedestrian, cyclist, wheelchair_user, stroller, dog, car, truck, bus, motorcycle, parked_bicycle, traffic_cone, bollard"))
        blocks = docx_blocks(self.p("taxonomy_v3_charter.docx"))
        for kind, st, val in blocks:
            if kind == "p" and val.startswith("Taxonomy v3 evaluation classes:"):
                self.tax_classes = set(c.strip() for c in val.split(":", 1)[1].strip().rstrip(".").split(","))
        self.final = {}
        self.counts = {}
        for run in self.review:
            cfg = self.runs[run]
            thr, nms, md = num(cfg["score_threshold"]), num(cfg["nms_iou"]), int(cfg["max_detections"])
            cnt = [0, 0, 0, 0]
            for i in self.evals:
                c, site, t, o, W, H = self.info[i]
                node = self.assign.get((run, self.seq_of[i]))
                rr = self.rerun.get((run, i))
                rows = []
                if rr is not None and rr["status"] == "completed":
                    store = rr["store"]
                    for d in self.store_rows[store].get((run, i), []):
                        prep = d["prep"] if store == "n2-replay" else self.store_prep[store].get((run, i))
                        rows.append((d, prep))
                elif (run, node, i) not in self.quar:
                    lp = self.prep.get((node, run, i))
                    for d in self.node_rows.get((node, run, i), {}).values():
                        if node == "n7":
                            rows.append((d, d["prep"]))
                        elif lp is not None:
                            rows.append((d, lp[1:]))
                acc = []
                for d, prep in rows:
                    if d["score"] is None or prep is None:
                        continue
                    cls = self.eval_class(run, d["ci"])
                    if cls is None:
                        continue
                    sc, px, py = prep
                    x1, y1, x2, y2 = d["box"]
                    b = [rnd((x1 - px) / sc), rnd((y1 - py) / sc), rnd((x2 - px) / sc), rnd((y2 - py) / sc)]
                    b = (max(0, min(W, b[0])), max(0, min(H, b[1])), max(0, min(W, b[2])), max(0, min(H, b[3])))
                    if b[2] <= b[0] or b[3] <= b[1]:
                        continue
                    acc.append((self.calibrate(run, cls, d["score"]), d["det"], cls, b))
                cnt[0] += len(acc)
                acc = [a for a in acc if a[0] >= thr]
                cnt[1] += len(acc)
                kept = []
                for cls in sorted(set(a[2] for a in acc)):
                    keep = []
                    for a in sorted((a for a in acc if a[2] == cls), key=lambda a: (-a[0], a[1])):
                        if all(iou(a[3], k[3]) <= nms for k in keep):
                            keep.append(a)
                    kept += keep
                cnt[2] += len(kept)
                kept = sorted(kept, key=lambda a: (-a[0], a[1]))[:md]
                cnt[3] += len(kept)
                self.final[(run, i)] = kept
            self.counts[run] = cnt

    # scoring ----------------------------------------------------------
    def score(self):
        self.metrics = {}
        self.cm_rows, self.op_rows = [], []
        gts = {}
        for i in self.evals:
            for g in self.gt[i]:
                gts.setdefault(g[1], {}).setdefault(i, []).append(g)
        for run in self.review:
            dets = {}
            for i in self.evals:
                for a in self.final[(run, i)]:
                    dets.setdefault(a[2], {}).setdefault(i, []).append(a)
            for cls in sorted(self.tax_classes):
                gt_c = gts.get(cls, {})
                n_gt = sum(1 for v in gt_c.values() for g in v if not g[3])
                d_c = dets.get(cls, {})
                n_det = sum(len(v) for v in d_c.values())
                aps, at50 = [], None
                for k in range(10):
                    t = Fraction(50 + 5 * k, 100)
                    ranked = []
                    for i, ds in d_c.items():
                        g_eval = sorted((g for g in gt_c.get(i, []) if not g[3]), key=lambda g: g[0])
                        g_ign = [g for g in gt_c.get(i, []) if g[3]]
                        taken = set()
                        for a in sorted(ds, key=lambda a: (-a[0], a[1])):
                            best, bid = None, None
                            for g in g_eval:
                                if g[0] in taken:
                                    continue
                                v = iou(a[3], g[2])
                                if v >= t and (best is None or v > best):
                                    best, bid = v, g[0]
                            if bid is not None:
                                taken.add(bid)
                                ranked.append((a[0], a[1], 1))
                            elif any(iof(a[3], g[2]) >= t for g in g_ign):
                                pass
                            else:
                                ranked.append((a[0], a[1], 0))
                    ranked.sort(key=lambda x: (-x[0], x[1]))
                    if k == 0:
                        at50 = ranked
                    if n_gt:
                        aps.append(average_precision(ranked, n_gt))
                tp50 = sum(x[2] for x in at50)
                row = [run, cls, str(n_gt), str(n_det), str(tp50), str(len(at50) - tp50)]
                if n_gt:
                    self.metrics[(run, cls)] = (aps[0], aps[5], sum(aps) / 10)
                    row += [six(aps[0]), six(aps[5]), six(sum(aps) / 10)]
                else:
                    row += ["NA", "NA", "NA"]
                self.cm_rows.append(row)
                target = self.tp_prot if cls in self.protected else self.tp_other
                best = None
                if n_gt:
                    tp = fp = 0
                    pos = 0
                    for tau in sorted(set(x[0] for x in at50), reverse=True):
                        while pos < len(at50) and at50[pos][0] >= tau:
                            tp += at50[pos][2]
                            fp += 1 - at50[pos][2]
                            pos += 1
                        prec, rec = Fraction(tp, tp + fp), Fraction(tp, n_gt)
                        if prec >= target and (best is None or rec > best[2] or (rec == best[2] and tau > best[0])):
                            best = (tau, prec, rec)
                self.op_rows.append([run, cls, six(target)] + (["NA", "NA", "NA"] if best is None else [six(best[0]), six(best[1]), six(best[2])]))

    def write(self, out: Path):
        out.mkdir(parents=True, exist_ok=True)

        def csv_out(name, header, rows):
            (out / name).write_text("\n".join(",".join(r) for r in [header] + rows) + "\n", encoding="utf-8")

        rows = []
        for i in self.evals:
            c, site, t, o, W, H = self.info[i]
            g = self.gt[i]
            rows.append([i, self.seq_of[i], c, site, datetime.fromtimestamp(int(t), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         str(W), str(H), str(o), str(sum(1 for x in g if not x[3])), str(sum(1 for x in g if x[3]))])
        csv_out("eval_images.csv", ["image_id", "sequence_id", "camera_id", "site_id", "captured_utc", "width", "height", "orientation", "gt_boxes", "ignore_regions"], rows)
        csv_out("exclusions.csv", ["image_id", "reason"], [[i, self.reason[i]] for i in self.cands if self.reason[i]])
        rows = []
        for i in self.evals:
            for g in sorted(self.gt[i], key=lambda g: g[0]):
                rows.append([i, g[0], g[1]] + [str(v) for v in g[2]] + ["1" if g[3] else "0"])
        csv_out("ground_truth.csv", ["image_id", "gt_id", "class", "x1", "y1", "x2", "y2", "ignore"], rows)
        rows = []
        for run in self.review:
            for i in self.evals:
                for a in sorted(self.final[(run, i)], key=lambda a: a[1]):
                    rows.append([run, i, "D%09d" % a[1], a[2]] + [str(v) for v in a[3]] + [six(a[0])])
        csv_out("detections.csv", ["run_id", "image_id", "det_id", "class", "x1", "y1", "x2", "y2", "score"], rows)
        csv_out("class_metrics.csv", ["run_id", "class", "gt_count", "det_count", "tp_50", "fp_50", "ap_50", "ap_75", "ap_50_95"], self.cm_rows)
        csv_out("operating_points.csv", ["run_id", "class", "target_precision", "threshold", "precision", "recall"], self.op_rows)
        inc = self.incumbent
        means = {}
        for run in self.review:
            vals = [v for (r, c), v in self.metrics.items() if r == run]
            means[run] = tuple(sum(v[k] for v in vals) / len(vals) for k in range(3))
        board, promoted = [], []
        for run in self.review:
            deltas = {}
            for c in self.protected:
                if (run, c) in self.metrics and (inc, c) in self.metrics:
                    deltas[c] = six(Fraction(Decimal(six(self.metrics[(run, c)][0]))) - Fraction(Decimal(six(self.metrics[(inc, c)][0]))))
                else:
                    deltas[c] = "NA"
            if run == inc:
                dec = "INCUMBENT"
            else:
                gain = Fraction(Decimal(six(means[run][2]))) - Fraction(Decimal(six(means[inc][2])))
                ok = gain >= self.margin and all(v == "NA" or Fraction(Decimal(v)) >= -self.tolerance for v in deltas.values())
                dec = "PROMOTE" if ok else "HOLD"
                if ok:
                    promoted.append((-Fraction(Decimal(six(means[run][2]))), run))
            board.append({"run_id": run, "model": self.runs[run]["model"], "map_50": six(means[run][0]), "map_75": six(means[run][1]),
                          "map_50_95": six(means[run][2]), "protected_ap_50_delta": deltas, "decision": dec})
        (out / "leaderboard.json").write_text(json.dumps({"incumbent": inc, "release_candidate": min(promoted)[1] if promoted else None,
                                                          "runs": board}, indent=2) + "\n", encoding="utf-8")
        excluded = {r: 0 for r in PRECEDENCE}
        for i in self.cands:
            if self.reason[i]:
                excluded[self.reason[i]] += 1
        src = {"CAMPAIGN": 0, "KS": 0, "NL": 0, "OB": 0}
        for i in self.evals:
            for g in self.gt[i]:
                src[g[4]] += 1
        deliveries = {}
        for f in sorted(self.declared):
            deliveries[f] = {"declared": self.declared[f], "parsed": self.parsed.get(f, 0)}
        rec = {"freeze_list_ids": len(self.freeze), "candidates": len(self.cands), "eval_images": len(self.evals),
               "excluded": excluded, "gt_boxes": sum(1 for i in self.evals for g in self.gt[i] if not g[3]),
               "ignore_regions": sum(1 for i in self.evals for g in self.gt[i] if g[3]), "gt_by_source": src,
               "detections": {r: dict(zip(["accepted", "after_threshold", "after_nms", "final"], self.counts[r])) for r in self.review},
               "deliveries": deliveries}
        (out / "reconciliation.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iou(a, b):
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return Fraction(0)
    inter = iw * ih
    return Fraction(inter, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def iof(d, g):
    iw = min(d[2], g[2]) - max(d[0], g[0])
    ih = min(d[3], g[3]) - max(d[1], g[1])
    if iw <= 0 or ih <= 0:
        return Fraction(0)
    return Fraction(iw * ih, (d[2] - d[0]) * (d[3] - d[1]))


def average_precision(ranked, n_gt):
    prec, recs = [], []
    tp = 0
    for k, x in enumerate(ranked):
        tp += x[2]
        prec.append(Fraction(tp, k + 1))
        recs.append(tp)
    for k in range(len(prec) - 2, -1, -1):
        prec[k] = max(prec[k], prec[k + 1])
    total = Fraction(0)
    j = 0
    for r in range(101):
        while j < len(recs) and recs[j] * 100 < r * n_gt:
            j += 1
        if j < len(recs):
            total += prec[j]
    return total / 101


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    Engine(Path(argv[1])).run(Path(argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
