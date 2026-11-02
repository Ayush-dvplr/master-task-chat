#!/usr/bin/env python3
"""KP-24 training data rebuild.

Stages:
    build.py phase1 DATA_DIR P1_DIR
    build.py phase2 P1_DIR P2_DIR
    build.py phase3 P1_DIR P2_DIR P3_DIR

Implements the FPS-4 standard (/app/data/fps4_rules.md) and the KP-24 output
contract (/app/docs/output_contract.md) generically: every register, profile,
segment and value is read from the estate the stage is given.
"""

import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from bisect import bisect_right
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN, getcontext

import yaml

getcontext().prec = 50

EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
ZERO = Decimal(0)


def die(msg, code=3):
    sys.stderr.write("error: %s\n" % msg)
    sys.exit(code)


# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------

def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def qdec(value, places):
    """Round a Decimal to places, half to even."""
    exp = Decimal(1).scaleb(-places)
    return value.quantize(exp, rounding=ROUND_HALF_EVEN)


def fmt_dec(value, places):
    """Format a Decimal with exactly places digits, no negative zero."""
    out = str(qdec(value, places))
    if out.startswith("-") and Decimal(out) == 0:
        out = out[1:]
    return out


def to_epoch(instant):
    return int((instant - EPOCH).total_seconds())


def iso(instant):
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch_to_iso(seconds):
    return iso(EPOCH + dt.timedelta(seconds=int(seconds)))


def parse_iso(text):
    """Parse an ISO-8601 timestamp (Z, offset or naive) to an aware datetime."""
    t = text.strip()
    if t.endswith("Z"):
        return dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", t):
        return dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})([+-])(\d{2}):?(\d{2})", t)
    if m:
        sign = 1 if m.group(2) == "+" else -1
        delta = dt.timedelta(hours=int(m.group(3)), minutes=int(m.group(4)))
        base = dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
        return (base - sign * delta).replace(tzinfo=dt.timezone.utc)
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})T? ?(\d{2}):?(\d{2})", t)
    if m:
        return dt.datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    raise ValueError("bad timestamp %r" % text)


def days_since_epoch(day):
    return (day - dt.date(1970, 1, 1)).days


def day_from_days(n):
    return dt.date(1970, 1, 1) + dt.timedelta(days=int(n))


# --------------------------------------------------------------------------
# registers of the standard
# --------------------------------------------------------------------------

class Registers(object):
    """Registers parsed out of the governing standard file."""

    def __init__(self, rules_text):
        tables = parse_markdown_tables(rules_text)
        self.site = {}          # code -> dict
        self.site_by_number = {}
        for row in tables["Site register"]:
            self.site[row["site"]] = {
                "code": row["site"], "number": row["number"],
                "tz": row["time zone rule"], "region": row["region"],
            }
            self.site_by_number[row["number"]] = row["site"]
        self.model_oem = {}
        for row in tables["Model catalogue"]:
            self.model_oem[row["model"]] = row["oem"]
        self.vocab = {}
        for row in tables["Code vocabularies"]:
            self.vocab[row["vocabulary"]] = [v.strip() for v in row["values"].split(",")]
        self.units = {}         # quantity -> list of (unit, extra places, factor)
        for row in tables["Unit register"]:
            self.units.setdefault(row["quantity"], []).append(
                (row["unit"], int(row["extra decimal places"]), row["meaning"]))
        self.role = {}
        for row in tables["Source register"]:
            self.role[row["file"]] = row["role"]
        self.fields = {}        # file -> table -> [(field, type)]
        for row in tables["Field register"]:
            self.fields.setdefault(row["file"], {}).setdefault(row["table"], []).append(
                (row["field"], row["type"]))
        self.rules_text = rules_text

    def unit_factor(self, quantity, unit):
        """Conversion factor (Decimal) from unit to the canonical unit."""
        first_unit = self.units[quantity][0][0]
        if unit == first_unit:
            return Decimal(1)
        if (quantity, unit) == ("vib", "in_s"):
            return Decimal("25.4")
        if (quantity, unit) == ("vib", "um_s"):
            return Decimal("0.001")
        if (quantity, unit) == ("temp", "f"):
            return None  # affine
        if (quantity, unit) == ("temp", "k"):
            return None
        if (quantity, unit) == ("prs", "kpa"):
            return Decimal("0.01")
        if (quantity, unit) == ("prs", "psi"):
            return Decimal(1) / Decimal("14.5037738")
        if (quantity, unit) == ("flw", "lps"):
            return Decimal("3.6")
        if (quantity, unit) == ("flw", "gpm"):
            return Decimal(1) / Decimal("4.402868")
        if (quantity, unit) == ("cur", "ma"):
            return Decimal("0.001")
        if (quantity, unit) == ("ppm", "ppb"):
            return Decimal("0.001")
        if (quantity, unit) == ("hrs", "min"):
            return Decimal(1) / Decimal(60)
        raise ValueError("unknown unit %s for %s" % (unit, quantity))

    def unit_extra(self, quantity, unit):
        for u, extra, _meaning in self.units[quantity]:
            if u == unit:
                return extra
        raise ValueError("unknown unit %s for %s" % (unit, quantity))


def parse_markdown_tables(text):
    """Parse every markdown table of the standard into {'name': [rows]}.

    Tables are named by the nearest preceding heading, with duplicates
    disambiguated by their position order.
    """
    lines = text.split("\n")
    heading = None
    tables = {}
    order = defaultdict(int)
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^#{2,4}\s+(.*)$", line)
        if m:
            heading = m.group(1).strip()
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[ :-]*-[ :-]*\|", lines[i + 1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                if len(cells) < len(header):
                    cells += [""] * (len(header) - len(cells))
                rows.append(dict(zip(header, cells)))
                j += 1
            name = heading or "table"
            order[name] += 1
            key = name
            tables[key] = rows
            i = j
            continue
        i += 1
    return tables


def parse_markdown_segment_tables(text):
    """Parse the export segments of a markdown source.

    Returns a list of (segment_id, header_names, rows-of-cells).
    """
    lines = text.split("\n")
    out = []
    seg = None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^#{2,4}\s+Segment\s+(\S+)", line)
        if m:
            seg = m.group(1)
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[ :-]*-[ :-]*\|", lines[i + 1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            out.append((seg, header, rows))
            i = j
            continue
        m = re.match(r"^Control:?\s*rows\s*=?\s*(\d+),?\s*sum\s*=?\s*(\S+)", line, re.I)
        if m and out:
            out[-1] = out[-1] + ((int(m.group(1)), m.group(2)),)
        i += 1
    return out


# --------------------------------------------------------------------------
# time zones
# --------------------------------------------------------------------------

def last_weekday(year, month, weekday):
    d = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    while d.weekday() != weekday:
        d -= dt.timedelta(days=1)
    return d


def nth_weekday(year, month, weekday, n):
    d = dt.date(year, month, 1)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    d += dt.timedelta(days=7 * (n - 1))
    return d


TZ_WINTER = {"eu": 60, "uk": 0, "us": -300, "ist": 330}
TZ_SUMMER = {"eu": 120, "uk": 60, "us": -240, "ist": 330}


def tz_transitions(rule, year):
    """(spring forward, fall back) transition instants in epoch seconds."""
    if rule == "ist":
        return None
    if rule in ("eu", "uk"):
        spring = last_weekday(year, 3, 6)   # last Sunday of March, 01:00 UTC
        fall = last_weekday(year, 10, 6)     # last Sunday of October, 01:00 UTC
    elif rule == "us":
        spring = nth_weekday(year, 3, 6, 2)  # second Sunday of March
        fall = nth_weekday(year, 11, 6, 1)   # first Sunday of November
    else:
        raise ValueError("unknown tz rule %r" % rule)
    base_s = to_epoch(dt.datetime(spring.year, spring.month, spring.day,
                                  tzinfo=dt.timezone.utc))
    base_f = to_epoch(dt.datetime(fall.year, fall.month, fall.day,
                                   tzinfo=dt.timezone.utc))
    if rule == "us":
        return (base_s + 7 * 3600, base_f + 6 * 3600)
    return (base_s + 3600, base_f + 3600)


def tz_offset_at(rule, instant):
    """Offset in force at an instant."""
    if rule == "ist":
        return 330
    year = (EPOCH + dt.timedelta(seconds=instant)).year
    spring, fall = tz_transitions(rule, year)
    if instant >= fall:
        return TZ_WINTER[rule]
    if instant >= spring:
        return TZ_SUMMER[rule]
    return TZ_WINTER[rule]


def summer_offset(rule, day):
    """Offset in force at 12:00 UTC of the given local date."""
    return tz_offset_at(rule, to_epoch(dt.datetime(day.year, day.month, day.day, 12,
                                                   tzinfo=dt.timezone.utc)))


def local_to_epoch(rule, day, seconds_of_day):
    """Resolve a wall-clock time to an instant in the site's time zone."""
    base = to_epoch(dt.datetime(day.year, day.month, day.day,
                                tzinfo=dt.timezone.utc)) + seconds_of_day
    candidates = sorted([(base - TZ_WINTER[rule] * 60, TZ_WINTER[rule]),
                         (base - TZ_SUMMER[rule] * 60, TZ_SUMMER[rule])])
    for instant, offset in candidates:
        if tz_offset_at(rule, instant) == offset:
            return instant
    return candidates[0][0]


# --------------------------------------------------------------------------
# profiles
# --------------------------------------------------------------------------

class Profiles(object):
    def __init__(self, main_entries, draft_entries, errata):
        self.main = main_entries
        self.draft = draft_entries
        self.errata = errata

    def entry_key(self, e):
        return "%s#%s#%s" % (e["file"], e["segment"], e["revision"])

    def resolve(self, fname, segment):
        """Resolve the profile entry for a file and segment."""
        active = [e for e in self.main
                  if e["file"] == fname and e["segment"] == segment and e["status"] == "active"]
        if not active:
            return None
        entry = max(active, key=lambda e: e["revision"])
        dims = {}
        if entry.get("inherit"):
            drafts = [e for e in self.draft if e["file"] == fname and e["segment"] == segment]
            if drafts:
                dims = dict(max(drafts, key=lambda e: e["revision"]).get("dims") or {})
        else:
            dims = dict(entry.get("dims") or {})
        dims = {str(k): str(v) for k, v in dims.items()}
        rid = self.entry_key(entry)
        for (tfile, trid, field), value in self.errata.items():
            if tfile == "profiles_r7.yaml" and trid == rid:
                if value is None:
                    dims.pop(field, None)
                else:
                    dims[field] = str(value)
        return dims


# --------------------------------------------------------------------------
# segment readers: raw records as dicts of column name -> raw text
# --------------------------------------------------------------------------

class Segment(object):
    __slots__ = ("name", "records", "control")

    def __init__(self, name):
        self.name = name
        self.records = []
        self.control = None


CONTROL_RE = re.compile(r"rows?\s*[:=]?\s*(\d+)[,; ]*sum\s*[:=]?\s*([^\s,;]+)", re.I)


def parse_control(text):
    m = CONTROL_RE.search(text)
    if not m:
        return None
    return (int(m.group(1)), m.group(2))


def read_segments(path, fname):
    """Read every export segment of a source file, detecting its format."""
    text = read_text(path)
    ext = os.path.splitext(fname)[1].lower()
    if ext == ".jsonl":
        return read_jsonl(text)
    if ext == ".json":
        return read_json(text)
    if ext in (".yaml", ".yml"):
        return read_json(yaml.safe_load(text))
    if ext == ".toml":
        return read_toml(text, fname)
    if ext == ".xml":
        return read_xml(text)
    if ext in (".html",):
        return read_html(text)
    if ext == ".md":
        return read_md(text)
    if ext == ".ini":
        return read_ini(text)
    if ext == ".ics":
        return read_ics(text)
    if ext == ".mbox":
        return read_mbox(text)
    if ext == ".sql":
        return read_sql(text)
    if ext == ".log":
        return read_hash_log(text)
    if ext in (".csv", ".tsv", ".txt"):
        return read_delimited(text, fname)
    raise ValueError("unknown format for %s" % fname)


def read_jsonl(text):
    segs = []
    cur = None
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            continue
        if "segment" in obj and len(obj) == 1:
            cur = Segment(obj["segment"])
            segs.append(cur)
        elif "control" in obj and len(obj) == 1:
            c = obj["control"]
            if cur is not None and cur.control is None:
                cur.control = (int(c["rows"]), str(c["sum"]))
        elif cur is not None:
            cur.records.append({k: ("" if v is None else str(v)) for k, v in obj.items()})
    return segs


def _json_segments(doc):
    segs = []
    for s in doc.get("segments", []):
        seg = Segment(s["segment"])
        if "control" in s:
            c = s["control"]
            seg.control = (int(c["rows"]), str(c["sum"]))
        for r in s.get("rows", []):
            seg.records.append({k: ("" if v is None else str(v)) for k, v in r.items()})
        segs.append(seg)
    return segs


def read_json(doc):
    """Segment list from a decoded JSON/YAML document."""
    if isinstance(doc, str):
        doc = json.loads(doc)
    return _json_segments(doc)


def read_toml(text, fname):
    import tomllib
    doc = tomllib.loads(text)
    segs = []
    for s in doc.get("segment", []):
        seg = Segment(s["id"])
        seg.control = (int(s["control"]["rows"]), str(s["control"]["sum"]))
        for r in s.get("rows", []):
            seg.records.append({k: ("" if v is None else str(v)) for k, v in r.items()})
        segs.append(seg)
    return segs


def read_xml(text):
    root = ET.fromstring(text)
    segs = []
    for node in root:
        if node.tag == "segment" or node.tag.endswith("segment"):
            seg = Segment(node.get("id"))
            for child in node:
                tag = child.tag
                if tag == "control" or tag.endswith("control"):
                    seg.control = (int(child.get("rows")), child.get("sum"))
                else:
                    seg.records.append(dict(child.attrib))
            segs.append(seg)
    return segs


def read_html(text):
    segs = []
    seg = None
    header = None
    for m in re.finditer(r"<table[^>]*data-segment=\"([^\"]+)\"(.*?)</table>|<p[^>]*class=\"control\"\s*>(.*?)</p>", text, re.S):
        if m.group(1):
            seg = Segment(m.group(1))
            segs.append(seg)
            body = m.group(2)
            rows = re.findall(r"<tr>(.*?)</tr>", body, re.S)
            header = None
            for r in rows:
                cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)
                cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
                if header is None:
                    header = cells
                else:
                    seg.records.append(dict(zip(header, cells)))
        else:
            ctl = parse_control(re.sub(r"<[^>]+>", " ", m.group(3)))
            if seg is not None and seg.control is None:
                seg.control = ctl
    return segs


def read_md(text):
    segs = []
    seg = None
    header = None
    rows = []

    def flush():
        if seg is not None and header is not None:
            for r in rows:
                seg.records.append(dict(zip(header, r)))
        rows.clear()

    for line in text.split("\n"):
        m = re.match(r"^#{2,4}\s+Segment\s+(\S+)", line)
        if m:
            flush()
            seg = Segment(m.group(1))
            segs.append(seg)
            header = None
            continue
        m = re.match(r"^Control:?\s*(.*)$", line, re.I)
        if m and seg is not None and seg.control is None:
            seg.control = parse_control(m.group(1))
            continue
        if line.startswith("|"):
            if re.match(r"^\|[ :-]*-[ :-]*\|", line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if header is None or len(cells) != len(header):
                flush()
                header = cells
            else:
                rows.append(cells)
            continue
    flush()
    return segs


def read_ini(text):
    segs = []
    seg = None
    header = None
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        m = re.match(r"^\[segment\s+(\S+)\]$", line, re.I)
        if m:
            seg = Segment(m.group(1))
            segs.append(seg)
            header = None
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "columns":
            header = [c.strip() for c in value.split(";")]
        elif key == "control":
            if seg is not None and seg.control is None:
                seg.control = parse_control(value)
        elif re.match(r"^row\d+$", key) and seg is not None:
            cells = [c.strip() for c in value.split(";")]
            if header is None:
                header = [None] * len(cells)
            seg.records.append(dict(zip(header, cells)))
    return segs


def read_ics(text):
    segs = []
    seg = None
    rec = None
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("X-SEGMENT:"):
            seg = Segment(line.split(":", 1)[1].strip())
            segs.append(seg)
        elif line == "BEGIN:VEVENT":
            rec = {}
        elif line == "END:VEVENT":
            if seg is not None and rec is not None:
                seg.records.append(dict(rec))
            rec = None
        elif line.startswith("X-CONTROL:"):
            if seg is not None and seg.control is None:
                seg.control = parse_control(line.split(":", 1)[1])
        elif rec is not None and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            if key == "UID":
                key = "rid"
            elif key.startswith("X-"):
                key = key[2:].lower()
            rec[key] = value.strip()
    return segs


def read_mbox(text):
    segs = []
    seg = None
    header = None
    for line in text.split("\n"):
        if line.startswith("Subject:"):
            m = re.search(r"segment\s+(\S+)", line)
            if m:
                seg = Segment(m.group(1))
                segs.append(seg)
                header = None
            continue
        if line.startswith("Columns:") and seg is not None:
            header = [c.strip() for c in line.split(":", 1)[1].split("|")]
            continue
        if line.startswith("Control:") and seg is not None and seg.control is None:
            seg.control = parse_control(line.split(":", 1)[1])
            continue
        if line.startswith("From "):
            continue
        if "|" in line and seg is not None and header is not None and line.strip():
            cells = [c.strip() for c in line.split("|")]
            if len(cells) == len(header):
                seg.records.append(dict(zip(header, cells)))
    return segs


def read_sql(text):
    segs = []
    seg = None
    header = None
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("--"):
            body = s.lstrip("-").strip()
            m = re.match(r"segment\s+(\S+)", body, re.I)
            if m:
                seg = Segment(m.group(1))
                segs.append(seg)
                header = None
                continue
            m = re.match(r"columns?:\s*(.+)$", body, re.I)
            if m and seg is not None:
                header = [c.strip() for c in m.group(1).split(",")]
                continue
            m = re.match(r"control\s+(.*)$", body, re.I)
            if m and seg is not None and seg.control is None:
                seg.control = parse_control(m.group(1))
                continue
            continue
        if s.upper().startswith("INSERT") and seg is not None:
            m = re.search(r"VALUES\s*\((.*)\)\s*;?\s*$", s, re.I)
            if not m:
                continue
            parts = next(csv.reader(io.StringIO(m.group(1)), quotechar="'", skipinitialspace=True))
            if header is None:
                header = [None] * len(parts)
            cells = []
            for c in parts:
                c = c.strip()
                if c.upper() == "NULL":
                    c = ""
                cells.append(c)
            seg.records.append(dict(zip(header, cells)))
    return segs


def read_hash_log(text):
    segs = []
    seg = None
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            body = s.lstrip("#").strip()
            m = re.match(r"segment\s+(\S+)", body, re.I)
            if m:
                seg = Segment(m.group(1))
                segs.append(seg)
                continue
            m = re.match(r"control\s+(.*)$", body, re.I)
            if m and seg is not None and seg.control is None:
                seg.control = parse_control(m.group(1))
                continue
            continue
        if seg is None:
            continue
        if re.match(r"^rec\s", s):
            seg.records.append(dict(re.findall(r"(\w+)=\"([^\"]*)\"", s)))
        elif "\t" in s or re.match(r"^\S+\s{2,}", s):
            cells = re.split(r"\t+|\s{2,}", s)
            if len(cells) > 1:
                header = [None] * len(cells)
                seg.records.append(dict(zip(header, cells)))
    return segs


def split_aligned(header_line, row):
    """Split a space aligned row by the column starts of its header line."""
    starts = [m.start() for m in re.finditer(r"\S+", header_line)]
    cells = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(row)
        cells.append(row[start:end].strip())
    return cells


def read_delimited(text, fname):
    """`#segment X` + header + rows + `#control`, space aligned text or CSV."""
    lines = text.split("\n")
    if any("\t" in l for l in lines if not l.startswith("#")):
        dialect = "tab"
    elif any(re.match(r"^\S+\s{2,}\S", l) for l in lines
             if not l.startswith("#") and l.strip()):
        dialect = "space"
    else:
        dialect = "comma"
    segs = []
    seg = None
    header = None
    header_line = None
    for line in lines:
        s = line.rstrip("\r")
        if s.startswith("#"):
            body = s.lstrip("#").strip()
            m = re.match(r"segment\s+(\S+)", body, re.I)
            if m:
                seg = Segment(m.group(1))
                segs.append(seg)
                header = None
                header_line = None
                continue
            m = re.match(r"control\s+(.*)$", body, re.I)
            if m and seg is not None and seg.control is None:
                seg.control = parse_control(m.group(1))
                continue
            continue
        if not s.strip():
            continue
        if re.match(r"^SEGMENT\s+(\S+)", s):
            seg = Segment(s.split()[1])
            segs.append(seg)
            header = None
            header_line = None
            continue
        m = re.match(r"^CONTROL\s+(.*)$", s)
        if m and seg is not None and seg.control is None:
            seg.control = parse_control(m.group(1))
            continue
        if dialect == "comma":
            cells = next(csv.reader(io.StringIO(s)))
        elif dialect == "tab":
            cells = s.split("\t")
        elif header is None:
            cells = re.split(r"\s{2,}", s.strip())
        else:
            cells = split_aligned(header_line, s)
        if header is None:
            header = [c.strip() for c in cells]
            header_line = s
        else:
            if len(cells) != len(header):
                fallback = [c.strip() for c in re.split(r"\s{2,}", s.strip())]
                if len(fallback) == len(header):
                    cells = fallback
            if len(cells) == len(header):
                seg.records.append(dict(zip(header, [c.strip() for c in cells])))
    return segs


# --------------------------------------------------------------------------
# decoded estate
# --------------------------------------------------------------------------

class Record(object):
    """A decoded source record: canonical field values."""

    __slots__ = ("rid", "fields", "segment", "file")

    def __init__(self, rid, fields, segment, file):
        self.rid = rid
        self.fields = fields
        self.segment = segment
        self.file = file


def parse_locale_number(text, locale):
    t = text.strip()
    if locale == "en":
        t = t.replace(",", "")
    elif locale == "de":
        t = t.replace(".", "").replace(",", ".")
    elif locale == "fr":
        t = (t.replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
             .replace(",", "."))
    elif locale == "ch":
        t = t.replace("'", "")
    return Decimal(t)


def parse_local_date(text, date_form):
    t = text.strip()
    if date_form == "iso":
        return dt.date(*[int(x) for x in t.split("-")])
    if date_form == "dmy":
        d, m, y = t.split("/")
        return dt.date(int(y), int(m), int(d))
    if date_form == "mdy":
        m, d, y = t.split("/")
        return dt.date(int(y), int(m), int(d))
    if date_form == "compact":
        return dt.date(int(t[:4]), int(t[4:6]), int(t[6:8]))
    raise ValueError("bad date form %r" % date_form)


NULL_TOKENS = {
    "empty": ("",),
    "na": ("", "NA"),
    "dash": ("", "-"),
    "nullword": ("", "null", "NULL", "Null"),
    "n999": ("", "-999"),
}


class Assets(object):
    """Asset change log replay (FPS-4 3.1, 3.2) and the serial registry."""

    def __init__(self, estate):
        self.estate = estate
        self.events = defaultdict(list)      # asset -> [(at, order, fields)]
        order = 0
        for rec in estate.decode_file("asset_changes.csv"):
            f = rec.fields
            if f["at"] > estate.freeze_at:
                continue
            self.events[f["asset"]].append((f["at"], order, f))
            order += 1
        self.rows = {}                        # asset -> state rows in order
        self.state = {}
        self.serial_map = {}
        for asset, evs in self.events.items():
            evs.sort(key=lambda e: (e[0], e[1]))
            site = None
            active = False
            setpoint = None
            crit = None
            model = None
            serial = None
            commissioned = None
            exists = False
            first_site = evs[0][2]["site"]
            timeline = []
            for at, _o, f in evs:
                kind = f["kind"]
                if kind in ("baseline", "commission"):
                    exists = True
                    site = f["site"] or site
                    setpoint = f["setpoint"] if f["setpoint"] is not None else setpoint
                    crit = f["criticality"] if f["criticality"] is not None else crit
                    active = True
                    model = f["model"] or model
                    serial = f["serial"] or serial
                    if kind == "commission":
                        commissioned = at
                elif kind == "relocate":
                    site = f["site"]
                elif kind == "decommission":
                    active = False
                    timeline.append((at, "decommission", None))
                elif kind == "reinstate":
                    active = True
                elif kind == "setpoint":
                    if f["setpoint"] is not None:
                        setpoint = f["setpoint"]
                elif kind == "criticality":
                    if f["criticality"] is not None:
                        crit = f["criticality"]
                timeline.append((at, kind, None))
            self.rows[asset] = {
                "asset": asset, "site": site or first_site, "model": model,
                "serial": serial, "setpoint": setpoint, "criticality": crit,
                "commissioned": commissioned, "exists": exists,
                "events": evs,
            }
            self.state[asset] = {"site": site or first_site, "active": active,
                                 "setpoint": setpoint, "criticality": crit}
            if serial and serial not in self.serial_map:
                self.serial_map[serial] = asset
        self._snapshot()

    def _snapshot(self):
        """The commissioned date of a baseline-only asset from the reference copy."""
        rows = self.estate.decode_file("asset_snapshot_q1.xml")
        best = {}
        freeze_day = dt.datetime.fromtimestamp(self.estate.freeze_at, dt.timezone.utc).date()
        for rec in rows:
            f = rec.fields
            if f["as_of"] > freeze_day:
                continue
            cur = best.get(f["asset"])
            if cur is None or f["as_of"] > cur["as_of"]:
                best[f["asset"]] = f
        for asset, row in best.items():
            info = self.rows.get(asset)
            if info is not None and info["commissioned"] is None:
                info["commissioned"] = to_epoch(dt.datetime(
                    row["commissioned"].year, row["commissioned"].month,
                    row["commissioned"].day, tzinfo=dt.timezone.utc))

    def site_rule_at(self, asset, instant):
        site = self.site_at(asset, instant)
        if site is None:
            return None
        return self.estate.reg.site[site]["tz"]

    def site_at(self, asset, instant):
        """The site in force at an instant; before the first row the site of
        that first row holds (FPS-4 3.1)."""
        events = self.rows.get(asset, {}).get("events", [])
        site = None
        for at, _o, f in events:
            if at > instant:
                break
            if f["kind"] in ("baseline", "commission", "relocate") and f["site"]:
                site = f["site"]
        if site is None and events:
            for at, _o, f in events:
                if f["kind"] in ("baseline", "commission", "relocate") and f["site"]:
                    return f["site"]
        return site

    def setpoint_at(self, asset, instant):
        sp = None
        for at, _o, f in self.rows.get(asset, {}).get("events", []):
            if at > instant:
                break
            if f["kind"] in ("baseline", "commission") and f["setpoint"] is not None:
                sp = f["setpoint"]
            elif f["kind"] == "setpoint" and f["setpoint"] is not None:
                sp = f["setpoint"]
        return sp

    def criticality_at(self, asset, instant):
        crit = None
        for at, _o, f in self.rows.get(asset, {}).get("events", []):
            if at > instant:
                break
            if f["kind"] in ("baseline", "commission") and f["criticality"] is not None:
                crit = f["criticality"]
            elif f["kind"] == "criticality" and f["criticality"] is not None:
                crit = f["criticality"]
        return crit

    def is_active_at(self, asset, instant):
        active = False
        exists = False
        for at, _o, f in self.rows.get(asset, {}).get("events", []):
            if at > instant:
                break
            kind = f["kind"]
            if kind in ("baseline", "commission", "reinstate"):
                active = True
                exists = True
            elif kind == "decommission":
                active = False
        return exists, active

    def decommission_at(self, asset):
        out = None
        for at, _o, f in self.rows.get(asset, {}).get("events", []):
            if f["kind"] == "decommission":
                out = at
        return out


class TagHistory(object):
    """Tag assignments (FPS-4 2.3 asset_ref tag)."""

    def __init__(self, estate):
        self.estate = estate
        self.rows = estate.decode_file("tag_history.ini")
        self.by_tag = defaultdict(list)
        for rec in self.rows:
            f = rec.fields
            if f["asset"] is None:
                continue
            self.by_tag[(f["system"], f["tag"])].append(
                (f["valid_from"], f["valid_to"], f["asset"]))

    def lookup(self, system, tag, instant):
        best = None
        for start, end, asset in self.by_tag.get((system, tag), []):
            if start is None or instant is None:
                match = instant is None
            else:
                match = start <= instant and (end is None or end > instant)
            if match:
                if best is None or start > best[0]:
                    best = (start, asset)
        return best[1] if best else None


class Estate(object):
    """Decodes an input estate directory under the FPS-4 standard."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.rules_text = read_text(os.path.join(data_dir, "fps4_rules.md"))
        self.reg = Registers(self.rules_text)
        self.freeze_at = self._find_freeze()
        self.files = sorted(f for f in os.listdir(data_dir)
                            if os.path.isfile(os.path.join(data_dir, f)))
        self.raw = {}
        self._read_raw()
        self._resolve_profiles()
        self.errata = self._decode_errata()
        self.records = {}
        self.current_file = None
        self.ref_fields = []
        self.serial_map = {}
        self.assets = Assets(self)
        self.serial_map = self.assets.serial_map
        self.tags = TagHistory(self)

    # -- reading ------------------------------------------------------

    def _read_raw(self):
        for fname in self.files:
            try:
                segs = read_segments(os.path.join(self.dir, fname), fname)
            except Exception as exc:
                die("cannot decode %s: %s" % (fname, exc))
            self.raw[fname] = segs

    def _resolve_profiles(self):
        main = yaml.safe_load(read_text(os.path.join(self.dir, "profiles_r7.yaml")))
        draft = yaml.safe_load(read_text(os.path.join(self.dir, "profiles_r7_draft.yaml")))
        self.dialects = main.get("dialects", {})
        self.main_entries = main.get("entries", [])
        self.draft_entries = draft.get("entries", [])
        self.profiles = Profiles(self.main_entries, self.draft_entries, {})

    def _find_freeze(self):
        m = re.search(r"as-of freeze is `([0-9T:+\-Z]+)`", self.rules_text)
        if not m:
            die("the standard states no freeze")
        return to_epoch(parse_iso(m.group(1)))

    # -- errata -------------------------------------------------------

    def _decode_errata(self):
        segs = self.raw["errata_feed.csv"]
        rows = []
        for seg in segs:
            dims = self.profiles.resolve("errata_feed.csv", seg.name) or {}
            cmap = self._column_map("errata_feed.csv", "erratum", dims)
            for raw in seg.records:
                rows.append(self._decode_one("errata_feed.csv", "erratum", raw, cmap, dims,
                                             seg.name))
        chosen = {}
        for order, rec in enumerate(rows):
            f = rec.fields
            if f["status"] != "approved":
                continue
            approved = f["approved_at"]
            if approved is None or approved > self.freeze_at:
                continue
            key = (f["target_file"], f["target_rid"], f["field"])
            prev = chosen.get(key)
            if prev is not None and (prev[0], prev[1]) >= (approved, order):
                continue
            chosen[key] = (approved, order, f["value"])
        out = {k: v[2] for k, v in chosen.items()}
        self.profiles.errata = out
        return out

    # -- decoding -----------------------------------------------------

    def _column_map(self, fname, table, dims):
        """Map raw column names to canonical fields for a segment."""
        cols = dims.get("cols", "std")
        alt = self.dialects.get(fname, {}).get("alt_columns", {})
        names = [f for f, _t in self.reg.fields[fname][table]]
        if cols == "std":
            mapping = {f: f for f in names}
        else:
            mapping = {alt.get(f, f): f for f in names}
        for f in names:
            low = f.lower()
            if low not in mapping:
                mapping[low] = f
        return mapping

    def segment_table(self, fname, raw_keys):
        tables = self.reg.fields.get(fname, {})
        if len(tables) == 1:
            return next(iter(tables))
        for table in tables:
            cmap = self._column_map(fname, table, {"cols": "alt"})
            if raw_keys and raw_keys <= set(cmap):
                return table
        for table in tables:
            cmap = self._column_map(fname, table, {"cols": "std"})
            if raw_keys and raw_keys <= set(cmap):
                return table
        return None

    def decode_file(self, fname):
        if fname in self.records:
            return self.records[fname]
        out = []
        self.current_file = fname
        for seg in self.raw[fname]:
            raw_keys = set()
            for raw in seg.records:
                raw_keys.update(raw.keys())
            table = self.segment_table(fname, raw_keys)
            if table is None:
                die("cannot identify the table of segment %s in %s" % (seg.name, fname))
            dims = self.profiles.resolve(fname, seg.name)
            if dims is None:
                die("no profile for %s segment %s" % (fname, seg.name))
            cmap = self._column_map(fname, table, dims)
            self.ref_fields = self.reg.fields[fname][table]
            for raw in seg.records:
                out.append(self._decode_one(fname, table, raw, cmap, dims, seg.name))
        self.records[fname] = out
        return out

    def _decode_one(self, fname, table, raw, cmap, dims, seg_name):
        fields = self.reg.fields[fname][table]
        values = {}
        for field, ftype in fields:
            raw_value = ""
            for key, value in raw.items():
                if cmap.get(key) == field:
                    raw_value = value
                    break
            values[field] = self._decode_value(fname, field, ftype, raw_value, dims,
                                               raw, values)
        return Record(values.get("rid"), values, seg_name, fname)

    def _decode_value(self, fname, field, ftype, raw_value, dims, raw, values):
        token = raw_value.strip() if raw_value else ""
        base = ftype[:-1] if ftype.endswith("?") else ftype
        nulls = dims.get("nulls", "empty")
        if token in NULL_TOKENS.get(nulls, ("",)):
            return None
        if base in ("text", "rid"):
            return token
        if base == "asset":
            return self._decode_asset_ref(token, dims, raw, values)
        if base == "site":
            return self._decode_site_ref(token, dims)
        if base == "ts":
            return self._decode_ts(token, dims, raw, values)
        if base == "date":
            return parse_local_date(token, dims.get("date_form", "iso"))
        if base == "bool":
            form = dims.get("bool", "tf")
            if form == "tf":
                return token.lower() == "true"
            if form == "yn":
                return token.upper() == "Y"
            if form == "10":
                return token == "1"
            raise ValueError("bad bool form %r" % form)
        if base == "acode":
            return self._decode_acode(token, dims)
        if base.startswith("code:"):
            return self._decode_code(token, base.split(":", 1)[1], dims)
        if base.startswith("q:") or base.startswith("n:"):
            if base.startswith("q:"):
                _tag, quantity, places = base.split(":")
                places = int(places)
                unit = dims.get("unit_" + quantity) or self.reg.units[quantity][0][0]
            else:
                _tag, places = base.split(":")
                places = int(places)
                quantity = unit = None
            return self._decode_number(token, quantity, unit, places, dims)
        if base == "int":
            return int(parse_locale_number(token, dims.get("locale", "plain")))
        raise ValueError("bad field type %r" % ftype)

    def _decode_number(self, token, quantity, unit, places, dims):
        locale = dims.get("locale", "plain")
        if dims.get("numform") == "scaled":
            extra = self.reg.unit_extra(quantity, unit) if quantity else 0
            p = max(places + extra, 0)
            if quantity == "temp" and unit == "k" and p < 2:
                p = 2
            value = parse_locale_number(token, locale).scaleb(-p)
        else:
            value = parse_locale_number(token, locale)
        if quantity is not None:
            factor = self.reg.unit_factor(quantity, unit)
            if factor is None:
                if unit == "f":
                    value = (value - 32) / Decimal("1.8")
                elif unit == "k":
                    value = value - Decimal("273.15")
                else:
                    raise ValueError("bad unit %s" % unit)
            else:
                value = value * factor
        return qdec(value, places)

    def _decode_acode(self, token, dims):
        form = dims.get("codeform", "dec")
        if form == "dec":
            return int(token)
        if form == "pref":
            return int(token[2:]) if token.startswith("E-") else int(token)
        if form == "hex":
            return int(token, 16)
        raise ValueError("bad codeform %r" % form)

    def _decode_code(self, token, vocab, dims):
        values = self.reg.vocab[vocab]
        form = dims.get("status", "word")
        if form == "num":
            return values[int(token) - 1]
        low = token.lower()
        for v in values:
            if v.lower() == low:
                return v
        raise ValueError("unknown code %r in vocabulary %s" % (token, vocab))

    def _decode_site_ref(self, token, dims):
        form = dims.get("site_ref", "code")
        if form == "code":
            return token if token in self.reg.site else None
        if form == "num":
            return self.reg.site_by_number.get(token)
        raise ValueError("bad site_ref %r" % form)

    def _decode_asset_ref(self, token, dims, raw, values):
        form = dims.get("asset_ref", "id")
        if form == "id":
            return token
        if form == "serial":
            return self.serial_map.get(token)
        if form == "tag":
            system = self.dialects.get(self.current_file, {}).get("tag_system")
            ref = self._reference_instant(values)
            return self.tags.lookup(system, token, ref)
        raise ValueError("bad asset_ref %r" % form)

    def _reference_instant(self, values):
        for field, ftype in self.ref_fields:
            if ftype.split("?")[0] == "ts" and values.get(field) is not None:
                return values[field]
        return None

    def _decode_ts(self, token, dims, raw, values):
        clock = dims.get("clock", "utc")
        if clock == "utc":
            return to_epoch(parse_iso(token if token.endswith("Z") else token + "Z"))
        if clock == "offset":
            return to_epoch(parse_iso(token))
        if clock == "epoch":
            return int(token)
        if clock == "epoch_ms":
            return int(round(int(token) / 1000))
        if clock == "local":
            return self._decode_local_ts(token, dims, raw, values)
        raise ValueError("bad clock %r" % clock)

    def _decode_local_ts(self, token, dims, raw, values):
        date_form = dims.get("date_form", "iso")
        if date_form == "compact":
            m = re.fullmatch(r"(\d{8})T?(\d{6})", token.strip())
            if not m:
                raise ValueError("bad compact local time %r" % token)
            day = dt.date(int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:8]))
            hh, mm, ss = (int(m.group(2)[:2]), int(m.group(2)[2:4]), int(m.group(2)[4:6]))
        else:
            m = re.fullmatch(r"(\S+)\s+(\d{2}):(\d{2}):(\d{2})", token.strip())
            if not m:
                raise ValueError("bad local time %r" % token)
            day = parse_local_date(m.group(1), date_form)
            hh, mm, ss = int(m.group(2)), int(m.group(3)), int(m.group(4))
        rule = None
        if values.get("site"):
            rule = self.reg.site[values["site"]]["tz"]
        else:
            asset = values.get("asset")
            if asset:
                rule = self.assets.site_rule_at(
                    asset, to_epoch(dt.datetime(day.year, day.month, day.day, 12,
                                                tzinfo=dt.timezone.utc)))
        if rule is None:
            rule = "eu"
        seconds = hh * 3600 + mm * 60 + ss
        return local_to_epoch(rule, day, seconds)



# --------------------------------------------------------------------------
# errata application
# --------------------------------------------------------------------------

_MISSING = object()


def canonical_to_value(reg, field, ftype, text):
    """Parse canonical text (FPS-4 2.4) back into a field value."""
    if text is None or text == "":
        return None
    base = ftype[:-1] if ftype.endswith("?") else ftype
    if base in ("text", "rid", "asset"):
        return text
    if base == "site":
        return text if text in reg.site else None
    if base == "ts":
        return to_epoch(parse_iso(text))
    if base == "date":
        return dt.date(*[int(x) for x in text.split("-")])
    if base == "bool":
        return text.lower() == "true"
    if base == "acode":
        return int(text)
    if base.startswith("code:"):
        return text
    if base.startswith("q:"):
        _tag, _quantity, places = base.split(":")
        return qdec(Decimal(text), int(places))
    if base.startswith("n:"):
        _tag, places = base.split(":")
        return qdec(Decimal(text), int(places))
    if base == "int":
        return int(text)
    raise ValueError("bad field type %r" % ftype)


class Source(object):
    """The decoded, errata-corrected records of one source file."""

    def __init__(self, estate, fname):
        self.estate = estate
        self.fname = fname
        self.records = estate.decode_file(fname)
        self.table_of = {}
        for rec in self.records:
            if rec.segment in self.table_of:
                continue
            raw_keys = set()
            for seg in estate.raw[fname]:
                if seg.name == rec.segment:
                    for raw in seg.records:
                        raw_keys.update(raw.keys())
            self.table_of[rec.segment] = estate.segment_table(fname, raw_keys)
        self.corrected = []
        for rec in self.records:
            fields = dict(rec.fields)
            if fname != "errata_feed.csv" and rec.rid is not None:
                for field, ftype in estate.reg.fields[fname][self.table_of[rec.segment]]:
                    value = estate.errata.get((fname, rec.rid, field), _MISSING)
                    if value is not _MISSING:
                        fields[field] = canonical_to_value(estate.reg, field, ftype, value)
            self.corrected.append(Record(rec.rid, fields, rec.segment, fname))

    def __iter__(self):
        return iter(self.corrected)

    def by_table(self):
        out = defaultdict(list)
        for rec in self.corrected:
            out[self.table_of.get(rec.segment)].append(rec)
        return out


def source_tables(estate):
    """Every source file decoded once, errata applied, indexed by table."""
    tables = defaultdict(dict)
    for fname in estate.files:
        src = Source(estate, fname)
        for table, records in src.by_table().items():
            tables[table].setdefault(fname, []).extend(records)
    return tables


# --------------------------------------------------------------------------
# phase 1
# --------------------------------------------------------------------------

def parse_window(rules_text):
    m = re.search(r"telemetry window runs from `(\d{4}-\d{2}-\d{2})` to "
                  r"`(\d{4}-\d{2}-\d{2})`", rules_text)
    if not m:
        die("the standard states no telemetry window")
    return parse_local_date(m.group(1), "iso"), parse_local_date(m.group(2), "iso")


def run_id_of(rules_text):
    m = re.search(r"rebuilt for run ([A-Za-z0-9\-]+)", rules_text)
    if not m:
        die("the standard states no run id")
    return m.group(1)


def mirror_opened_before(rules_text):
    m = re.search(r"opened before (\d{4}-\d{2}-\d{2})", rules_text)
    if m:
        return parse_local_date(m.group(1), "iso")
    return dt.date(2025, 3, 1)


def local_day(instant, rule):
    """The local calendar date of an instant in a site's time zone."""
    shifted = instant + tz_offset_at(rule, instant) * 60
    return day_from_days(shifted // 86400)


def day_bounds(day, rule):
    """The local midnights of a day as (start, end) instants, end exclusive."""
    start_epoch = to_epoch(dt.datetime(day.year, day.month, day.day,
                                       tzinfo=dt.timezone.utc))
    start = start_epoch - tz_offset_at(rule, start_epoch) * 60
    nxt = day + dt.timedelta(days=1)
    nxt_epoch = to_epoch(dt.datetime(nxt.year, nxt.month, nxt.day,
                                     tzinfo=dt.timezone.utc))
    end = nxt_epoch - tz_offset_at(rule, nxt_epoch) * 60
    return start, end


def _codes_of(appendix, oem):
    """The codes an OEM lists at all in the appendix (5.4)."""
    return set(code for (oem_id, code) in appendix if oem_id == oem)


class Phase1(object):
    """Decodes the estate and reconciles it into the phase 1 tables."""

    CHANNEL_PLACES = {"vib": 3, "tmp": 2, "prs": 3, "flw": 2, "cur": 2}
    # the channel of a reading field in the channel vocabulary
    CHANNEL_OF_FIELD = {"vib": "vib", "tmp": "temp", "prs": "prs",
                        "flw": "flw", "cur": "cur"}

    def __init__(self, estate):
        self.e = estate
        self.reg = estate.reg
        self.freeze = estate.freeze_at
        self.window = parse_window(estate.rules_text)
        self.run_id = run_id_of(estate.rules_text)
        self.opened_before = mirror_opened_before(estate.rules_text)
        self.tables = source_tables(estate)
        self.params = self.effective_parameters()

    # -- parameters ------------------------------------------------------

    def effective_parameters(self):
        params = {}
        rows = []
        for fname in sorted(self.tables.get("param", {})):
            rows.extend(self.tables["param"][fname])
        by_name = defaultdict(list)
        for rec in rows:
            by_name[rec.fields["name"]].append(rec)
        for name in sorted(by_name):
            best = None
            for rec in by_name[name]:
                f = rec.fields
                if f["status"] != "active" or f["set_at"] is None:
                    continue
                if f["set_at"] > self.freeze:
                    continue
                key = (f["rev"], f["set_at"])
                if best is None or key > best[0]:
                    best = (key, rec)
            if best is not None:
                params[name] = best[1].fields["value"]
        return params

    def holdout(self):
        return set(self.params["holdout_assets"].split())

    # -- assets ----------------------------------------------------------

    def asset_rows(self):
        rows = {}
        holdout = self.holdout()
        rated = self.rated_flow_at()
        for asset in sorted(self.e.assets.rows):
            info = self.e.assets.rows[asset]
            if not info["exists"]:
                continue
            _exists, active = self.e.assets.is_active_at(asset, self.freeze)
            dec = None if active else self.e.assets.decommission_at(asset)
            commissioned = None
            if info["commissioned"] is not None:
                commissioned = (EPOCH + dt.timedelta(seconds=info["commissioned"])).date()
            rows[asset] = {
                "asset_id": asset,
                "site": self.e.assets.site_at(asset, self.freeze) or "",
                "model": info["model"] or "",
                "oem": self.reg.model_oem.get(info["model"] or "", ""),
                "serial": info["serial"] or "",
                "commissioned_on": commissioned,
                "decommissioned_at": dec,
                "criticality": self.e.assets.criticality_at(asset, self.freeze) or "",
                "setpoint_bar": self.e.assets.setpoint_at(asset, self.freeze),
                "rated_flow_m3h": rated.get(asset),
                "holdout": asset in holdout,
            }
        return rows

    def rated_flow_at(self):
        """The rated flow in force at the freeze (FPS-4 3.3)."""
        best = {}
        order = 0
        for fname in sorted(self.tables.get("perf_point", {})):
            for rec in self.tables["perf_point"][fname]:
                f = rec.fields
                if not f["bep"] or not f["accepted"] or f["asset"] is None:
                    continue
                if f["tested_at"] > self.freeze:
                    continue
                key = (f["tested_at"], order)
                cur = best.get(f["asset"])
                if cur is None or key > cur[0]:
                    best[f["asset"]] = (key, f["flow"])
                order += 1
        return {a: v[1] for a, v in best.items()}

    def rated_flow_series(self):
        """All rated flow changes per asset, for the daily values (3.3)."""
        rows = defaultdict(list)
        order = 0
        for fname in sorted(self.tables.get("perf_point", {})):
            for rec in self.tables["perf_point"][fname]:
                f = rec.fields
                if not f["bep"] or not f["accepted"] or f["asset"] is None:
                    continue
                if f["tested_at"] > self.freeze:
                    continue
                rows[f["asset"]].append((f["tested_at"], order, f["flow"]))
                order += 1
        for asset in rows:
            rows[asset].sort()
        return rows

    # -- telemetry -------------------------------------------------------

    def group_files(self, table, backfill_field=None):
        """Files of a telemetry group, the backfill read after the others."""
        plain, backfill = [], []
        for fname in sorted(self.tables.get(table, {})):
            fields = [t for _f, t in self.reg.fields[fname][table]]
            if backfill_field is not None and backfill_field in fields:
                backfill.append(fname)
            else:
                plain.append(fname)
        return plain + backfill

    def readings(self):
        """One row survives per asset and instant within a group (4.1)."""
        out = {}
        for table, channels in (("cm", ("vib", "tmp")),
                               ("hist", ("prs", "flw", "cur"))):
            survivors = {}
            for fname in self.group_files(table, "received_at"):
                for rec in self.tables[table][fname]:
                    f = rec.fields
                    if f["asset"] is None or f["at"] is None:
                        continue
                    if table == "hist" and f.get("received_at") is not None:
                        if f["received_at"] > self.freeze:
                            continue
                    key = (f["asset"], f["at"])
                    cur = survivors.get(key)
                    rank = f["seq"]
                    if cur is None or rank >= cur[0]:
                        survivors[key] = (rank, f)
            out[table] = [(key, v[1]) for key, v in survivors.items()]
        resend = {}
        for fname in sorted(self.tables.get("resend", {})):
            for rec in self.tables["resend"][fname]:
                f = rec.fields
                if not f["gapfill"] or f["asset"] is None or f["at"] is None:
                    continue
                key = (f["asset"], f["at"])
                cur = resend.get(key)
                if cur is None or f["seq"] >= cur[0]:
                    resend[key] = (f["seq"], f)
        have = set(key for key, _f in out["cm"])
        for key in sorted(resend):
            if key not in have:
                out["cm"].append((key, resend[key][1]))
        return out

    def calibrations(self):
        """Certificates in force and the revocations (4.3)."""
        reviews = defaultdict(list)
        for fname in sorted(self.tables.get("cert_review", {})):
            for rec in self.tables["cert_review"][fname]:
                f = rec.fields
                if f["at"] is None or f["at"] > self.freeze:
                    continue
                reviews[f["cert_no"]].append((f["at"], f["outcome"]))
        revoked = {}
        for cert_no, rows in reviews.items():
            rows.sort()
            revoked[cert_no] = rows[-1][1] == "revoke"
        pending = {}
        for fname in sorted(self.tables.get("cert_pending", {})):
            for rec in self.tables["cert_pending"][fname]:
                f = rec.fields
                if f["approved_at"] is None or f["approved_at"] > self.freeze:
                    continue
                if f["cert_no"] not in pending:
                    pending[f["cert_no"]] = f
        certs = []
        for fname in sorted(self.tables.get("cert", {})):
            for rec in self.tables["cert"][fname]:
                f = rec.fields
                if f["recorded_at"] is None or f["recorded_at"] > self.freeze:
                    continue
                if f["status"] == "see_pending":
                    pend = pending.get(f["cert_no"])
                    if pend is None:
                        continue
                    gain, offset, effective = pend["gain"], pend["offset"], pend["effective_from"]
                elif f["status"] == "approved":
                    gain, offset, effective = f["gain"], f["offset"], f["effective_from"]
                else:
                    continue
                certs.append((f["serial"], f["cert_no"], f["rev"], effective, gain, offset))
        certs.sort(key=lambda c: (c[3], c[2], c[1]))
        return certs, revoked

    def sensor_moves(self):
        moves = defaultdict(list)
        for fname in sorted(self.tables.get("sensor_move", {})):
            for rec in self.tables["sensor_move"][fname]:
                f = rec.fields
                if f["asset"] is None or f["at"] is None:
                    continue
                moves[(f["asset"], f["channel"])].append((f["at"], f["action"], f["serial"]))
        for key in moves:
            moves[key].sort()
        return moves

    def envelopes(self):
        rows = defaultdict(list)
        for fname in sorted(self.tables.get("envelope", {})):
            for rec in self.tables["envelope"][fname]:
                f = rec.fields
                if f["status"] != "active" or f["asset"] is None:
                    continue
                rows[(f["asset"], f["channel"])].append((f["effective_from"], f["lo"], f["hi"]))
        for key in rows:
            rows[key].sort(key=lambda r: r[0])
        return rows

    def fault_windows(self):
        rows = defaultdict(list)
        for fname in sorted(self.tables.get("fault_window", {})):
            for rec in self.tables["fault_window"][fname]:
                f = rec.fields
                if f["decision"] != "accepted" or f["decided_at"] > self.freeze:
                    continue
                if f["asset"] is None or f["start"] is None or f["end"] is None:
                    continue
                rows[(f["asset"], f["channel"])].append((f["start"], f["end"]))
        return rows


    # -- asset days ------------------------------------------------------

    def window_days(self):
        first, last = self.window
        out = []
        day = first
        while day <= last:
            out.append(day)
            day += dt.timedelta(days=1)
        return out

    def asset_days(self):
        """The asset days with their readings (FPS-4 5)."""
        days = self.window_days()
        assets = self.e.assets
        active = defaultdict(list)
        for asset in assets.rows:
            if not assets.rows[asset]["exists"]:
                continue
            for day in days:
                noon = to_epoch(dt.datetime(day.year, day.month, day.day, 12,
                                            tzinfo=dt.timezone.utc))
                _exists, is_active = assets.is_active_at(asset, noon)
                if is_active:
                    active[asset].append((day, noon))
        return active

    def daily_readings(self):
        """Calibrated, usable readings grouped per asset, day and channel."""
        groups = self.readings()
        certs, revoked = self.calibrations()
        moves = self.sensor_moves()
        envelopes = self.envelopes()
        faults = self.fault_windows()
        assets = self.e.assets
        out = defaultdict(lambda: defaultdict(list))
        quarantined = defaultdict(int)
        for table in ("cm", "hist"):
            for (asset, instant), fields in groups[table]:
                noon = None
                rule = assets.site_rule_at(asset, instant)
                if rule is None:
                    continue
                day = local_day(instant, rule)
                if day < self.window[0] or day > self.window[1]:
                    continue
                for channel in self.channels_of(table):
                    raw = fields.get(channel)
                    if raw is None:
                        continue
                    key = (asset, self.CHANNEL_OF_FIELD[channel])
                    serial = self.serial_in_force(moves, key, instant)
                    if serial is None:
                        continue
                    cert = self.cert_in_force(certs, revoked, serial, instant)
                    if cert is None:
                        continue
                    if self.in_window(faults, key, instant):
                        continue
                    value = qdec(cert[4] * raw + cert[5],
                                 self.CHANNEL_PLACES[channel])
                    if self.outside_envelope(envelopes, key, instant, value):
                        quarantined[(asset, day)] += 1
                        continue
                    out[(asset, day)][channel].append(value)
        return out, quarantined

    def channels_of(self, table):
        return ("vib", "tmp") if table == "cm" else ("prs", "flw", "cur")

    def serial_in_force(self, moves, key, instant):
        serial = None
        for at, action, moved in moves.get(key, []):
            if at > instant:
                break
            if action == "install":
                serial = moved
            elif action == "remove" and moved == serial:
                serial = None
        return serial

    def cert_in_force(self, certs, revoked, serial, instant):
        best = None
        for row in certs:
            if row[0] != serial or row[3] > instant:
                continue
            if revoked.get(row[1]):
                continue
            if best is None or (row[3], row[2]) > (best[3], best[2]):
                best = row
        return best

    def in_window(self, windows, key, instant):
        for start, end in windows.get(key, []):
            if start <= instant < end:
                return True
        return False

    def outside_envelope(self, envelopes, key, instant, value):
        best = None
        for start, lo, hi in envelopes.get(key, []):
            if start > instant:
                break
            if best is None or start >= best[0]:
                best = (start, lo, hi)
        if best is None:
            return False
        return value < best[1] or value > best[2]

    # -- availability ----------------------------------------------------

    def embargoed(self):
        rows = defaultdict(list)
        for fname in sorted(self.tables.get("embargo", {})):
            for rec in self.tables["embargo"][fname]:
                f = rec.fields
                if f["asset"] is None or f["set_at"] is None or f["set_at"] > self.freeze:
                    continue
                month = f["month"]
                if month.day != 1:
                    continue
                rows[(f["asset"], month)].append((f["rev"], f["set_at"], f["flag"]))
        out = set()
        for (asset, month), items in rows.items():
            items.sort()
            if items[-1][2]:
                out.add((asset, month))
        return out

    def outages(self):
        rows = defaultdict(list)
        for fname in sorted(self.tables.get("outage", {})):
            for rec in self.tables["outage"][fname]:
                f = rec.fields
                if f["status"] != "logged" or f["asset"] is None:
                    continue
                if f["start"] is None or f["end"] is None:
                    continue
                rows[f["asset"]].append((f["start"], f["end"]))
        return rows

    def standby(self):
        best = {}
        for fname in sorted(self.tables.get("standby", {})):
            for rec in self.tables["standby"][fname]:
                f = rec.fields
                if f["asset"] is None or rec.rid is None:
                    continue
                cur = best.get(rec.rid)
                if cur is None or f["seq"] >= cur[0]:
                    best[rec.rid] = (f["seq"], f)
        rows = defaultdict(list)
        for _rid, (_seq, f) in best.items():
            if f["status"] != "confirmed" or f["start"] is None or f["end"] is None:
                continue
            rows[f["asset"]].append((f["start"], f["end"]))
        return rows

    def review_hold(self):
        """The review hold flag of an asset day (FPS-4 2.6)."""
        rows = set()
        for fname in sorted(self.tables.get("kp23_label", {})):
            for rec in self.tables["kp23_label"][fname]:
                f = rec.fields
                if f["review_hold"] and f["asset"] is not None and f["day"] is not None:
                    rows.add((f["asset"], f["day"]))
        return rows

    def coverage(self, windows, start, end):
        """The length of the union of windows clipped to [start, end)."""
        clipped = sorted((max(s, start), min(e, end)) for s, e in windows
                          if max(s, start) < min(e, end))
        total = 0
        cur_s = cur_e = None
        for s, e in clipped:
            if cur_s is None:
                cur_s, cur_e = s, e
            elif s <= cur_e:
                cur_e = max(cur_e, e)
            else:
                total += cur_e - cur_s
                cur_s, cur_e = s, e
        if cur_s is not None:
            total += cur_e - cur_s
        return total

    def availability(self, asset, day, rule, embargoed, outages, standby, holds):
        month = dt.date(day.year, day.month, 1)
        if (asset, month) in embargoed:
            return "embargo"
        start, end = day_bounds(day, rule)
        if self.coverage(outages.get(asset, []), start, end) >= 12 * 3600:
            return "outage"
        if self.coverage(standby.get(asset, []), start, end) >= 12 * 3600:
            return "standby"
        if (asset, day) in holds:
            return "hold"
        return "ok"

    # -- alarms ----------------------------------------------------------

    def firmware(self):
        rows = defaultdict(list)
        for fname in sorted(self.tables.get("firmware", {})):
            for rec in self.tables["firmware"][fname]:
                f = rec.fields
                if f["asset"] is None or f["at"] is None:
                    continue
                rows[f["asset"]].append((f["at"], f["status"], f["version"]))
        for asset in rows:
            rows[asset].sort()
        return rows

    def major_at(self, versions, instant):
        major = 1
        for at, status, version in versions:
            if at > instant:
                break
            if status in ("done", "rolledback"):
                major = int(version.split(".")[0])
        return major

    def alarm_dictionary(self):
        """The appendix rows and the draft rows of the alarm dictionary (5.4)."""
        appendix = defaultdict(list)
        draft = defaultdict(list)
        order = 0
        for fname in sorted(self.tables.get("alarm_code", {})):
            for rec in self.tables["alarm_code"][fname]:
                f = rec.fields
                item = (f["min_fw"], order, f["class"])
                order += 1
                if fname == "fps4_rules.md":
                    appendix[(f["oem"], f["code"])].append(item)
                else:
                    draft[(f["oem"], f["code"])].append(item)
        self._alarm_order = order
        return appendix, draft

    def alarm_class_of(self, oem, code, major, appendix, draft):
        """The class of a code for an OEM at a firmware major (5.4)."""
        if (oem, code) in appendix:
            rows = appendix
        elif oem in _codes_of(appendix, oem):
            # the draft dictionary only supplies codes the appendix does not
            # list at all for that OEM
            rows = {}
        else:
            rows = draft
        items = [i for i in rows.get((oem, code), []) if i[0] <= major]
        if not items:
            return None
        best = max(i[0] for i in items)
        same = sorted([i for i in items if i[0] == best], key=lambda i: i[1])
        return same[0][2]

    def alarm_counts(self):
        """The counted alarms per asset and local day (5.4)."""
        firmwares = self.firmware()
        appendix, draft = self.alarm_dictionary()
        assets = self.e.assets
        acks = defaultdict(list)
        for fname in sorted(self.tables.get("alarm_ack", {})):
            for rec in self.tables["alarm_ack"][fname]:
                f = rec.fields
                if f["acked_at"] is None or f["acked_at"] > self.freeze:
                    continue
                acks[f["alarm_rid"]].append((f["acked_at"], f["kind"]))
        shelve = defaultdict(list)
        for fname in sorted(self.tables.get("shelve", {})):
            for rec in self.tables["shelve"][fname]:
                f = rec.fields
                if f["status"] != "active" or f["asset"] is None:
                    continue
                if f["start"] is None or f["end"] is None:
                    continue
                shelve[(f["asset"], f["code"])].append((f["start"], f["end"]))
        counts = defaultdict(int)
        oems = {}
        for asset, info in self.e.assets.rows.items():
            oems[asset] = self.reg.model_oem.get(info["model"] or "", "")
        for fname in sorted(self.tables.get("alarm", {})):
            for rec in self.tables["alarm"][fname]:
                f = rec.fields
                if f["asset"] is None or f["at"] is None:
                    continue
                rule = assets.site_rule_at(f["asset"], f["at"])
                if rule is None:
                    continue
                day = local_day(f["at"], rule)
                oem = oems.get(f["asset"], "")
                major = self.major_at(firmwares.get(f["asset"], []), f["at"])
                alarm_class = self.alarm_class_of(oem, f["code"], major,
                                                 appendix, draft)
                if alarm_class not in ("warning", "trip"):
                    continue
                acked = False
                for acked_at, kind in acks.get(rec.rid, []):
                    if kind in ("nuisance", "test") and acked_at <= f["at"] + 15 * 60:
                        acked = True
                        break
                if acked:
                    continue
                if self.in_window(shelve, (f["asset"], f["code"]), f["at"]):
                    continue
                counts[(f["asset"], day)] += 1
        return counts


    # -- site days -------------------------------------------------------

    def site_days(self):
        """Shifts and ambient per site day (FPS-4 6)."""
        days = self.window_days()
        roster = defaultdict(list)
        for fname in sorted(self.tables.get("shift", {})):
            for rec in self.tables["shift"][fname]:
                f = rec.fields
                if f["site"] is None or f["day"] is None:
                    continue
                roster[(f["site"], f["day"], f["shift"])].append((f["rev"], f["status"]))
        shifts = {}
        for key, items in roster.items():
            items.sort()
            shifts[key] = items[-1][1]
        out = {}
        for code in sorted(self.reg.site):
            for day in days:
                count = sum(1 for shift in self.reg.vocab["shift_code"]
                            if shifts.get((code, day, shift)) == "operating")
                out[(code, day)] = {"shifts_operating": count,
                                    "operating": count >= 2,
                                    "ambient_c": None}
        ambient = self.ambient()
        for (code, day), kinds in ambient.items():
            if (code, day) not in out:
                continue
            low, high = kinds.get("min"), kinds.get("max")
            if low is not None and high is not None:
                out[(code, day)]["ambient_c"] = qdec((low + high) / 2, 2)
        return out

    def ambient(self):
        """The ambient min and max per site day (6.2)."""
        primary = defaultdict(list)
        mirror = defaultdict(list)
        for fname in sorted(self.tables.get("ambient", {})):
            for rec in self.tables["ambient"][fname]:
                f = rec.fields
                if f["site"] is None or f["at"] is None or f["temp"] is None:
                    continue
                rule = self.reg.site[f["site"]]["tz"]
                day = local_day(f["at"], rule)
                entry = (f["at"], rec.rid, f["kind"], f["temp"])
                if fname in self.reference_copies:
                    mirror[(f["site"], day, f["kind"])].append(entry)
                else:
                    primary[(f["site"], day, f["kind"])].append(entry)
        # the mirror fills only site days the in-scope source has no
        # observation for at all (FPS-4 2.6)
        for key, entries in mirror.items():
            if key not in primary:
                primary[key] = entries
        checks = defaultdict(list)
        for fname in sorted(self.tables.get("ambient_qc", {})):
            for rec in self.tables["ambient_qc"][fname]:
                f = rec.fields
                if f["at"] is None or f["at"] > self.freeze:
                    continue
                checks[f["obs_rid"]].append((f["at"], f["outcome"], f["temp"]))
        best = {}
        for key, entries in primary.items():
            decided = []
            for entry in entries:
                at, rid, kind, temp = entry
                value = temp
                rows = sorted(checks.get(rid, []))
                if rows:
                    latest = rows[-1]
                    if latest[1] == "reject":
                        continue
                    if latest[1] == "retest" and latest[2] is not None:
                        value = latest[2]
                decided.append((at, value, entry))
            if not decided:
                continue
            decided.sort(key=lambda d: (d[0], d[2][1]))
            best[key] = decided[-1][1]
        out = defaultdict(dict)
        for (site, day, kind), value in best.items():
            out[(site, day)][kind] = value
        return out

    @property
    def reference_copies(self):
        if getattr(self, "_reference_copies", None) is None:
            self._reference_copies = set(
                f for f, role in self.reg.role.items() if role == "reference_copy")
        return self._reference_copies

    # -- failures --------------------------------------------------------

    def failure_events(self):
        """The failure notifications with their decisions (FPS-4 7.1, 7.2)."""
        notifications = {}
        order = 0
        for fname in sorted(self.tables.get("notification", {})):
            for rec in self.tables["notification"][fname]:
                f = rec.fields
                if f["kind"] != "failure" or f["notif_no"] is None:
                    continue
                if f["notif_no"] in notifications:
                    continue
                notifications[f["notif_no"]] = (f, order)
                order += 1
        decisions = defaultdict(list)
        for fname in sorted(self.tables.get("rca", {})):
            for rec in self.tables["rca"][fname]:
                f = rec.fields
                if f["decided_at"] is None or f["decided_at"] > self.freeze:
                    continue
                if f["notif_no"] is None:
                    continue
                decisions[f["notif_no"]].append((0, f["decided_at"], f["rev"], 0,
                                                f["decision"], f["mode"], order))
                order += 1
        amendments = {}
        for fname in sorted(self.tables.get("amendment", {})):
            for rec in self.tables["amendment"][fname]:
                f = rec.fields
                if f["notif_no"] is None or f["status"] != "confirmed":
                    continue
                if f["amended_at"] is None:
                    continue
                cur = amendments.get(rec.rid)
                if cur is None or f["seq"] > cur[0]:
                    amendments[rec.rid] = (f["seq"], f, order)
                order += 1
        deferred = defaultdict(list)
        for rid, (seq, f, orderno) in amendments.items():
            if f["amended_at"] > self.freeze:
                deferred[f["notif_no"]].append((f["amended_at"], seq, orderno, f))
            else:
                decisions[f["notif_no"]].append((1, f["amended_at"], f["seq"], 1,
                                               f["decision"], f["mode"], orderno))
        events = {}
        for notif_no, (f, _order) in notifications.items():
            rows = sorted(decisions.get(notif_no, []),
                          key=lambda d: (d[1], -d[0], -d[2], d[6]))
            decided_at = None
            status = "unconfirmed"
            mode = f["mode"]
            if rows:
                last = rows[-1]
                decided_at = last[1]
                if last[4] in ("confirm", "reclassify"):
                    status = "confirmed"
                if last[4] == "reclassify" and last[5] is not None:
                    mode = last[5]
            pending = None
            if deferred.get(notif_no):
                pending = sorted(deferred[notif_no],
                                 key=lambda d: (d[0], d[1], d[2]))[-1][3]
            events[notif_no] = {
                "event_id": notif_no,
                "asset_id": f["asset"],
                "failed_at": f["failed_at"],
                "status": status,
                "mode": mode,
                "decided_at": decided_at,
                "pending_decision": pending["decision"] if pending else None,
                "pending_mode": (pending["mode"] if pending and
                                 pending["decision"] == "reclassify" else None),
                "pending_at": pending["amended_at"] if pending else None,
            }
        return events

    # -- maintenance -----------------------------------------------------

    def maintenance(self):
        """The services and the counted oil samples (FPS-4 7.4, 7.5)."""
        orders = {}
        for fname in sorted(self.tables.get("work_order", {})):
            for rec in self.tables["work_order"][fname]:
                f = rec.fields
                if f["wo_no"] is None or f["wo_no"] in orders:
                    continue
                orders[f["wo_no"]] = dict(f)
        revisions = defaultdict(list)
        for fname in sorted(self.tables.get("wo_rev", {})):
            for rec in self.tables["wo_rev"][fname]:
                f = rec.fields
                if f["revised_at"] is None or f["revised_at"] > self.freeze:
                    continue
                if f["wo_no"] is None:
                    continue
                revisions[f["wo_no"]].append((f["rev"], f["revised_at"], f["status"],
                                              f["closed_at"]))
        for wo_no, rows in revisions.items():
            rows.sort(key=lambda r: (r[0], r[1]))
            best = rows[-1]
            order = orders.get(wo_no)
            if order is None:
                continue
            order["status"] = best[2]
            order["closed_at"] = best[3]
        legacy = {}
        for fname in sorted(self.tables.get("work_order", {})):
            if fname not in self.reference_copies:
                continue
            for rec in self.tables["work_order"][fname]:
                f = rec.fields
                if f["wo_no"] is None or f["wo_no"] in legacy:
                    legacy[f["wo_no"]] = f
        limit = to_epoch(dt.datetime(self.opened_before.year, self.opened_before.month,
                                     self.opened_before.day, tzinfo=dt.timezone.utc))
        for wo_no, order in orders.items():
            if order["closed_at"] is not None or order.get("opened_at") is None:
                continue
            if order["opened_at"] >= limit:
                continue
            row = legacy.get(wo_no)
            if row is not None and row["closed_at"] is not None:
                order["closed_at"] = row["closed_at"]
        bookings = defaultdict(list)
        for fname in sorted(self.tables.get("labour", {})):
            for rec in self.tables["labour"][fname]:
                f = rec.fields
                if f["wo_no"] is None or f["end"] is None:
                    continue
                bookings[f["wo_no"]].append(f["end"])
        services = []
        for wo_no in sorted(orders):
            order = orders[wo_no]
            if order["status"] != "completed":
                continue
            ends = bookings.get(wo_no, [])
            instant = max(ends) if ends else order["closed_at"]
            if instant is None or instant > self.freeze:
                continue
            services.append({"asset_id": order["asset"], "event_at": instant,
                             "kind": order["kind"], "value": None, "ref": wo_no})
        return services, self.oil_samples()

    def oil_samples(self):
        checks = defaultdict(list)
        for fname in sorted(self.tables.get("oil_qc", {})):
            for rec in self.tables["oil_qc"][fname]:
                f = rec.fields
                if f["at"] is None or f["at"] > self.freeze:
                    continue
                if f["sample_no"] is None:
                    continue
                checks[f["sample_no"]].append((f["at"], f["outcome"], f["iron"]))
        out = []
        seen = set()
        for fname in sorted(self.tables.get("oil", {})):
            for rec in self.tables["oil"][fname]:
                f = rec.fields
                if f["sample_no"] is None or f["sample_no"] in seen:
                    continue
                seen.add(f["sample_no"])
                if f["status"] != "valid" or f["sampled_at"] is None:
                    continue
                if f["sampled_at"] > self.freeze:
                    continue
                value = f["iron"]
                rows = sorted(checks.get(f["sample_no"], []))
                if rows:
                    latest = rows[-1]
                    if latest[1] == "reject":
                        continue
                    if latest[1] == "retest" and latest[2] is not None:
                        value = latest[2]
                if value is None:
                    continue
                out.append({"asset_id": f["asset"], "event_at": f["sampled_at"],
                            "kind": "oil", "value": int(value),
                            "ref": f["sample_no"]})
        return out

    # -- sensor daily -----------------------------------------------------

    def sensor_daily(self):
        """One row per asset day (FPS-4 5)."""
        active = self.asset_days()
        readings, quarantined = self.daily_readings()
        alarms = self.alarm_counts()
        embargoed = self.embargoed()
        outages = self.outages()
        standby = self.standby()
        holds = self.review_hold()
        rated = self.rated_flow_series()
        assets = self.e.assets
        rows = []
        for asset in sorted(active):
            for day, noon in active[asset]:
                rule = assets.site_rule_at(asset, noon)
                site = assets.site_at(asset, noon)
                setpoint = assets.setpoint_at(asset, noon)
                flow = None
                for tested_at, _order, value in rated.get(asset, []):
                    if tested_at <= noon:
                        flow = value
                values = readings.get((asset, day), {})
                counts = {ch: values.get(ch, []) for ch in self.CHANNEL_PLACES}
                row = {
                    "asset_id": asset,
                    "day": day,
                    "site": site or "",
                    "availability": self.availability(asset, day, rule, embargoed,
                                                       outages, standby, holds),
                    "vib_mean_mm_s": mean_of(counts["vib"], 3),
                    "vib_max_mm_s": max_of(counts["vib"]),
                    "temp_c": mean_of(counts["tmp"], 2),
                    "pressure_bar": mean_of(counts["prs"], 3),
                    "flow_m3h": mean_of(counts["flw"], 2),
                    "current_a": mean_of(counts["cur"], 2),
                    "setpoint_bar": setpoint,
                    "rated_flow_m3h": flow,
                    "alarms": alarms.get((asset, day), 0),
                    "readings": sum(len(v) for v in counts.values()),
                    "quarantined": quarantined.get((asset, day), 0),
                }
                rows.append(row)
        rows.sort(key=lambda r: (r["asset_id"], r["day"]))
        return rows


def mean_of(values, places):
    if not values:
        return None
    total = ZERO
    for value in values:
        total += value
    return qdec(total / len(values), places)


def max_of(values):
    if not values:
        return None
    return max(values)


# --------------------------------------------------------------------------
# output helpers
# --------------------------------------------------------------------------

def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def write_csv(path, header, rows):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    write_text(path, out.getvalue())


def write_json(path, obj):
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)
    write_text(path, text + "\n")


def dec_text(value, places):
    if value is None:
        return ""
    return fmt_dec(value if isinstance(value, Decimal) else Decimal(str(value)), places)


def json_dec(value, places):
    if value is None:
        return None
    return fmt_dec(value if isinstance(value, Decimal) else Decimal(str(value)), places)


def canonical_text(reg, value, ftype):
    """The canonical text of a decoded value (FPS-4 2.4)."""
    if value is None:
        return ""
    base = ftype[:-1] if ftype.endswith("?") else ftype
    if base == "ts":
        return epoch_to_iso(value)
    if base == "date":
        return value.isoformat()
    if base == "bool":
        return "true" if value else "false"
    if base in ("text", "rid", "asset", "site"):
        return value
    if base == "acode":
        return str(value)
    if base.startswith("code:"):
        return value
    if base.startswith("q:") or base.startswith("n:"):
        places = int(base.split(":")[2] if base.startswith("q:") else base.split(":")[1])
        return fmt_dec(value, places)
    if base == "int":
        return str(value)
    raise ValueError("bad field type %r" % ftype)


def source_digest(estate, fname):
    """Records and digest of a source file, before errata."""
    records = estate.decode_file(fname)
    if fname == "profiles_r7.yaml" or fname == "profiles_r7_draft.yaml":
        entries = (estate.main_entries if fname == "profiles_r7.yaml"
                   else estate.draft_entries)
        lines = []
        for entry in entries:
            dims = ";".join(
                "%s=%s" % (k, entry_dims_value(k, v))
                for k, v in sorted((entry.get("dims") or {}).items()))
            lines.append("|".join([entry["file"], entry["segment"],
                                  str(entry["revision"]), entry["status"],
                                  entry.get("inherit") or "", dims]))
        return len(entries), hashlib.sha256(
            ("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
    lines = []
    for rec in records:
        table = estate.segment_table(fname, set())
        if table is None:
            raw_keys = set()
            for seg in estate.raw[fname]:
                if seg.name == rec.segment:
                    for raw in seg.records:
                        raw_keys.update(raw.keys())
            table = estate.segment_table(fname, raw_keys)
        values = []
        for field, ftype in estate.reg.fields[fname][table]:
            values.append(canonical_text(estate.reg, rec.fields.get(field), ftype))
        lines.append("|".join(values))
    return len(records), hashlib.sha256(
        ("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def entry_dims_value(key, value):
    if key == "bool":
        return str(value)
    return str(value)


# --------------------------------------------------------------------------
# phase 1 output
# --------------------------------------------------------------------------

ASSET_HEADER = ["asset_id", "site", "model", "oem", "serial", "commissioned_on",
                "decommissioned_at", "criticality", "setpoint_bar",
                "rated_flow_m3h", "holdout"]
SENSOR_HEADER = ["asset_id", "day", "site", "availability", "vib_mean_mm_s",
                 "vib_max_mm_s", "temp_c", "pressure_bar", "flow_m3h",
                 "current_a", "setpoint_bar", "rated_flow_m3h", "alarms",
                 "readings", "quarantined"]
EVENT_HEADER = ["event_id", "asset_id", "failed_at", "failed_day", "status",
                "mode", "decided_at", "pending_decision", "pending_mode",
                "pending_at"]
MAINT_HEADER = ["asset_id", "event_at", "event_day", "kind", "value", "ref"]
SITE_HEADER = ["site", "day", "shifts_operating", "operating", "ambient_c"]

P1_FILES = ["asset_registry.csv", "failure_events.csv", "maintenance_log.csv",
            "run_parameters.json", "sensor_daily.csv", "site_days.csv"]


def phase1(data_dir, out_dir):
    if not os.path.isdir(data_dir):
        die("input directory %s is missing" % data_dir)
    estate = Estate(data_dir)
    phase = Phase1(estate)
    os.makedirs(out_dir, exist_ok=True)
    # asset registry
    assets = phase.asset_rows()
    write_csv(os.path.join(out_dir, "asset_registry.csv"), ASSET_HEADER,
              [[row["asset_id"], row["site"], row["model"], row["oem"],
                row["serial"],
                row["commissioned_on"].isoformat() if row["commissioned_on"] else "",
                epoch_to_iso(row["decommissioned_at"]) if row["decommissioned_at"] else "",
                row["criticality"], dec_text(row["setpoint_bar"], 3),
                dec_text(row["rated_flow_m3h"], 2),
                "true" if row["holdout"] else "false"]
               for row in sorted(assets.values(), key=lambda r: r["asset_id"])])
    # sensor daily
    sensor = phase.sensor_daily()
    write_csv(os.path.join(out_dir, "sensor_daily.csv"), SENSOR_HEADER,
              [[row["asset_id"], row["day"].isoformat(), row["site"],
                row["availability"], dec_text(row["vib_mean_mm_s"], 3),
                dec_text(row["vib_max_mm_s"], 3), dec_text(row["temp_c"], 2),
                dec_text(row["pressure_bar"], 3), dec_text(row["flow_m3h"], 2),
                dec_text(row["current_a"], 2), dec_text(row["setpoint_bar"], 3),
                dec_text(row["rated_flow_m3h"], 2), row["alarms"],
                row["readings"], row["quarantined"]] for row in sensor])
    # failure events
    events = phase.failure_events()
    assets_map = estate.assets
    rows = []
    for event_id in sorted(events):
        ev = events[event_id]
        rule = None
        if ev["asset_id"]:
            rule = assets_map.site_rule_at(ev["asset_id"], ev["failed_at"] or 0)
        failed_day = ""
        if ev["failed_at"] is not None and rule:
            failed_day = local_day(ev["failed_at"], rule).isoformat()
        rows.append([ev["event_id"], ev["asset_id"] or "",
                     epoch_to_iso(ev["failed_at"]) if ev["failed_at"] else "",
                     failed_day, ev["status"], ev["mode"] or "",
                     epoch_to_iso(ev["decided_at"]) if ev["decided_at"] else "",
                     ev["pending_decision"] or "", ev["pending_mode"] or "",
                     epoch_to_iso(ev["pending_at"]) if ev["pending_at"] else ""])
    write_csv(os.path.join(out_dir, "failure_events.csv"), EVENT_HEADER, rows)
    # maintenance log
    services, oil = phase.maintenance()
    rows = []
    for item in services:
        rule = assets_map.site_rule_at(item["asset_id"], item["event_at"]) if item["asset_id"] else None
        day = local_day(item["event_at"], rule).isoformat() if rule else ""
        rows.append([item["asset_id"] or "", epoch_to_iso(item["event_at"]),
                     day, item["kind"] or "", "", item["ref"]])
    for item in oil:
        rule = assets_map.site_rule_at(item["asset_id"], item["event_at"]) if item["asset_id"] else None
        day = local_day(item["event_at"], rule).isoformat() if rule else ""
        rows.append([item["asset_id"] or "", epoch_to_iso(item["event_at"]),
                     day, "oil", str(item["value"]), item["ref"]])
    rows.sort(key=lambda r: (r[0], r[1], r[5]))
    write_csv(os.path.join(out_dir, "maintenance_log.csv"), MAINT_HEADER, rows)
    # site days
    days = phase.site_days()
    write_csv(os.path.join(out_dir, "site_days.csv"), SITE_HEADER,
              [[site, day.isoformat(), values["shifts_operating"],
                "true" if values["operating"] else "false",
                dec_text(values["ambient_c"], 2)]
               for (site, day), values in sorted(days.items())])
    # run parameters
    sources = []
    for fname in estate.files:
        records, digest = source_digest(estate, fname)
        sources.append({"file": fname, "role": estate.reg.role.get(fname, "in_scope"),
                        "records": records, "digest": digest})
    sources.sort(key=lambda s: s["file"])
    params = {name: value for name, value in phase.params.items()
              if name != "holdout_assets"}
    settings = {
        "run_id": phase.run_id,
        "freeze": epoch_to_iso(estate.freeze_at),
        "telemetry_window": [phase.window[0].isoformat(), phase.window[1].isoformat()],
        "parameters": params,
        "holdout_assets": sorted(phase.holdout()),
        "regions": {code: info["region"] for code, info in sorted(estate.reg.site.items())},
        "sources": sources,
    }
    write_json(os.path.join(out_dir, "run_parameters.json"), settings)
    verify_segments(estate)
    return 0


def verify_segments(estate):
    """Check every segment against the control it publishes (FPS-4 2.1)."""
    for fname in estate.files:
        records = estate.decode_file(fname)
        by_segment = defaultdict(list)
        for rec in records:
            by_segment[rec.segment].append(rec)
        for seg in estate.raw[fname]:
            if seg.control is None:
                continue
            rows, want_sum = seg.control
            recs = by_segment.get(seg.name, [])
            if len(recs) != rows:
                die("segment %s of %s has %d rows, its control says %d"
                    % (seg.name, fname, len(recs), rows))
            raw_keys = set()
            for raw in seg.records:
                raw_keys.update(raw.keys())
            table = estate.segment_table(fname, raw_keys)
            if table is None:
                continue
            fields = estate.reg.fields[fname][table]
            control = None
            for kind in ("q", "n", "int", "ts", "date"):
                for field, ftype in fields:
                    if field == "rid":
                        continue
                    base = ftype.split("?")[0]
                    if kind == "q" and base.startswith("q:"):
                        control = (field, base)
                    elif kind == "n" and base.startswith("n:"):
                        control = (field, base)
                    elif kind == "int" and base == "int":
                        control = (field, base)
                    elif kind == "ts" and base == "ts":
                        control = (field, base)
                    elif kind == "date" and base == "date":
                        control = (field, base)
                    if control:
                        break
                if control:
                    break
            if control is None:
                continue
            total = ZERO
            for rec in recs:
                value = rec.fields.get(control[0])
                if value is None:
                    continue
                if control[1] == "ts":
                    total += value
                elif control[1] == "date":
                    total += days_since_epoch(value)
                else:
                    total += value
            if str(total) != want_sum:
                die("segment %s of %s sums %s, its control says %s"
                    % (seg.name, fname, total, want_sum))


# --------------------------------------------------------------------------
# phase 2
# --------------------------------------------------------------------------

FEATURES = ["vib_mean_7d", "vib_max_7d", "temp_rise_7d", "pressure_dev_3d",
            "flow_ratio_7d", "current_7d", "days_since_service", "age_days",
            "iron_ppm", "alarms_7d"]
INT_FEATURES = {"days_since_service", "age_days", "iron_ppm", "alarms_7d"}
EXCLUDE_REASONS = ["non_operating", "embargo", "outage", "standby", "hold",
                   "low_coverage", "blackout", "maintenance", "purge"]

P2_FILES = ["label_table.json", "feature_matrix.json", "scaler_stats.json",
            "class_balance.json", "quarantine_summary.json", "bin_edges.json"]


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        out = []
        for values in reader:
            out.append(dict(zip(header, values)))
        return out


def load_phase1(p1_dir):
    """Read the six phase 1 files (FPS-4 8 onwards needs nothing else)."""
    for name in P1_FILES:
        if not os.path.isfile(os.path.join(p1_dir, name)):
            die("%s is missing from %s" % (name, p1_dir))
    assets = read_csv_rows(os.path.join(p1_dir, "asset_registry.csv"))
    sensor = read_csv_rows(os.path.join(p1_dir, "sensor_daily.csv"))
    events = read_csv_rows(os.path.join(p1_dir, "failure_events.csv"))
    maint = read_csv_rows(os.path.join(p1_dir, "maintenance_log.csv"))
    sites = read_csv_rows(os.path.join(p1_dir, "site_days.csv"))
    with open(os.path.join(p1_dir, "run_parameters.json"), encoding="utf-8") as fh:
        params = json.load(fh)
    return assets, sensor, events, maint, sites, params


def upstream_of_phase1(p1_dir):
    """The labels, digests and controls of the six phase 1 files."""
    labels = ["p1/" + name for name in sorted(P1_FILES)]
    digest = hashlib.sha256()
    controls = {}
    for label in labels:
        name = label[3:]
        path = os.path.join(p1_dir, name)
        if not os.path.isfile(path):
            die("%s is missing from %s" % (name, p1_dir))
        digest.update((label + "\n").encode("utf-8"))
        digest.update(sha256_file(path).encode("utf-8") + b"\n")
        if name == "run_parameters.json":
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            sources = doc["sources"]
            controls[label] = {
                "rows": len(sources),
                "total": str(sum(s["records"] for s in sources)),
                "last_key": sources[-1]["file"] if sources else "",
            }
            continue
        rows = read_csv_rows(path)
        if name == "asset_registry.csv":
            total = sum(Decimal(r["rated_flow_m3h"]) for r in rows
                         if r["rated_flow_m3h"] != "")
            last_key = rows[-1]["asset_id"] if rows else ""
        elif name == "sensor_daily.csv":
            total = sum(int(r["readings"]) for r in rows)
            last_key = "%s|%s" % (rows[-1]["asset_id"], rows[-1]["day"]) if rows else ""
        elif name == "failure_events.csv":
            total = Decimal(sum(1 for r in rows if r["status"] == "confirmed"))
            last_key = rows[-1]["event_id"] if rows else ""
        elif name == "maintenance_log.csv":
            total = sum(int(r["value"]) for r in rows if r["value"] != "")
            last_key = rows[-1]["ref"] if rows else ""
        else:
            total = sum(int(r["shifts_operating"]) for r in rows)
            last_key = "%s|%s" % (rows[-1]["site"], rows[-1]["day"]) if rows else ""
        controls[label] = {"rows": len(rows), "total": str(total),
                           "last_key": last_key}
    return labels, digest.hexdigest(), controls


def parse_day(text):
    return dt.date(*[int(x) for x in text.split("-")])


def decimal_or_none(text, places=4):
    if text == "" or text is None:
        return None
    return qdec(Decimal(text), places)


class Phase2(object):
    """Samples, features and fitted statistics from the phase 1 tables."""

    def __init__(self, p1_dir):
        (self.assets, self.sensor, self.events, self.maint, self.sites,
         self.settings) = load_phase1(p1_dir)
        self.p1_dir = p1_dir
        self.params = self.settings["parameters"]
        self.holdout = set(self.settings["holdout_assets"])
        self.days = {}
        for row in self.sensor:
            key = (row["asset_id"], parse_day(row["day"]))
            self.days[key] = row
        self.site_days = {}
        for row in self.sites:
            self.site_days[(row["site"], parse_day(row["day"]))] = row
        self.asset_info = {row["asset_id"]: row for row in self.assets}

    def number(self, name):
        return Decimal(self.params[name])

    def integer(self, name):
        return int(self.params[name])

    # -- samples --------------------------------------------------------

    def confirmed_days(self):
        out = defaultdict(set)
        for row in self.events:
            if row["status"] == "confirmed" and row["failed_day"]:
                out[row["asset_id"]].add(parse_day(row["failed_day"]))
        return out

    def candidate_days(self):
        start = parse_day(self.params["sample_start"])
        end = parse_day(self.params["sample_end"])
        out = defaultdict(list)
        for (asset, day) in sorted(self.days):
            if start <= day <= end:
                out[asset].append(day)
        return out

    def service_days(self):
        kinds = {"lubrication", "seal", "bearing", "impeller", "overhaul"}
        out = defaultdict(set)
        for row in self.maint:
            if row["kind"] in kinds and row["event_day"]:
                out[row["asset_id"]].add(parse_day(row["event_day"]))
        return out

    def samples(self):
        """The kept samples with their exclusion reason (FPS-4 8.1)."""
        min_readings = self.integer("min_readings")
        blackout = self.integer("blackout_days")
        horizon = self.integer("horizon_days")
        train_end = parse_day(self.params["train_end"])
        confirmed = self.confirmed_days()
        services = self.service_days()
        kept = []
        excluded = defaultdict(lambda: defaultdict(int))
        for asset, days in sorted(self.candidate_days().items()):
            for day in days:
                row = self.days[(asset, day)]
                site_row = self.site_days.get((row["site"], day))
                if site_row is None or site_row["operating"] != "true":
                    reason = "non_operating"
                elif row["availability"] != "ok":
                    reason = row["availability"]
                elif int(row["readings"]) < min_readings:
                    reason = "low_coverage"
                elif any(f <= day <= (f - dt.timedelta(days=1)
                                      + dt.timedelta(days=blackout))
                         for f in confirmed.get(asset, ())):
                    reason = "blackout"
                elif any(day in (s, s + dt.timedelta(days=1))
                         for s in services.get(asset, ())):
                    reason = "maintenance"
                elif (asset not in self.holdout
                      and train_end - dt.timedelta(days=horizon) < day <= train_end):
                    reason = "purge"
                else:
                    reason = None
                if reason:
                    excluded[row["site"]][reason] += 1
                    continue
                kept.append((asset, day, row["site"]))
        kept.sort(key=lambda s: (s[0], s[1]))
        return kept, excluded

    def split_of(self, asset, day):
        train_end = parse_day(self.params["train_end"])
        val_end = parse_day(self.params["val_end"])
        if asset in self.holdout:
            return "test"
        if day <= train_end:
            return "train"
        if day <= val_end:
            return "val"
        return "test"

    def labels(self, confirmed):
        horizon = self.integer("horizon_days")
        out = {}
        for asset, days in confirmed.items():
            out[asset] = sorted(days)
        return out

    def label_of(self, asset, day, confirmed, horizon):
        for failure in confirmed.get(asset, ()):
            if day <= failure - dt.timedelta(days=1) and failure <= day + dt.timedelta(
                    days=horizon):
                return 1
        return 0

    # -- features -------------------------------------------------------

    def features(self):
        """The feature values of every kept sample (FPS-4 9)."""
        kept, excluded = self.samples()
        confirmed = self.confirmed_days()
        horizon = self.integer("horizon_days")
        lookback = self.integer("iron_lookback_days")
        services = self.service_days()
        oil = defaultdict(list)
        for row in self.maint:
            if row["kind"] == "oil" and row["event_day"]:
                oil[row["asset_id"]].append(
                    (parse_day(row["event_day"]), epoch_of(row["event_at"]),
                     int(row["value"])))
        labels = {}
        rows = []
        for asset, day, site in kept:
            label = self.label_of(asset, day, confirmed, horizon)
            labels[(asset, day)] = label
            values = {}
            window7 = [day - dt.timedelta(days=i) for i in range(6, -1, -1)]
            window3 = [day - dt.timedelta(days=i) for i in range(2, -1, -1)]
            day_rows = [self.days.get((asset, d)) for d in window7]
            vib_means = [decimal_or_none(r["vib_mean_mm_s"]) for r in day_rows if r]
            vib_means = [v for v in vib_means if v is not None]
            vib_maxes = [decimal_or_none(r["vib_max_mm_s"]) for r in day_rows if r]
            vib_maxes = [v for v in vib_maxes if v is not None]
            rise = []
            for r in day_rows:
                if not r:
                    continue
                temp = decimal_or_none(r["temp_c"])
                ambient = self.site_days.get((r["site"], parse_day(r["day"])))
                amb = decimal_or_none(ambient["ambient_c"], 2) if ambient else None
                if temp is not None and amb is not None:
                    rise.append(temp - amb)
            dev = []
            for d in window3:
                r = self.days.get((asset, d))
                if not r:
                    continue
                pressure = decimal_or_none(r["pressure_bar"])
                setpoint = decimal_or_none(r["setpoint_bar"], 3)
                if pressure is not None and setpoint is not None:
                    dev.append(pressure - setpoint)
            ratio = []
            for r in day_rows:
                if not r:
                    continue
                flow = decimal_or_none(r["flow_m3h"])
                rated = decimal_or_none(r["rated_flow_m3h"], 2)
                if flow is not None and rated is not None and rated > 0:
                    ratio.append(flow / rated)
            current = [decimal_or_none(r["current_a"]) for r in day_rows if r]
            current = [v for v in current if v is not None]
            values["vib_mean_7d"] = mean_dec(vib_means, 4) if len(vib_means) >= 4 else None
            values["vib_max_7d"] = qdec(max(vib_maxes), 4) if len(vib_maxes) >= 4 else None
            values["temp_rise_7d"] = mean_dec(rise, 4) if len(rise) >= 4 else None
            values["pressure_dev_3d"] = mean_dec(dev, 4) if len(dev) >= 2 else None
            values["flow_ratio_7d"] = mean_dec(ratio, 4) if len(ratio) >= 4 else None
            values["current_7d"] = mean_dec(current, 4) if len(current) >= 4 else None
            latest = None
            for s in sorted(services.get(asset, ())):
                if s <= day:
                    latest = s
            values["days_since_service"] = ((day - latest).days
                                            if latest is not None else None)
            commissioned = self.asset_info.get(asset, {}).get("commissioned_on")
            values["age_days"] = ((day - parse_day(commissioned)).days
                                  if commissioned else None)
            iron = None
            best = None
            for sample_day, instant, value in oil.get(asset, ()):
                if sample_day <= day and sample_day >= day - dt.timedelta(
                        days=lookback):
                    if best is None or (instant, sample_day) >= best[0]:
                        best = ((instant, sample_day), value)
            values["iron_ppm"] = best[1] if best is not None else None
            alarms = 0
            for d in window7:
                r = self.days.get((asset, d))
                if r:
                    alarms += int(r["alarms"])
            values["alarms_7d"] = alarms
            rows.append({"asset_id": asset, "day": day, "site": site,
                         "label": label, "values": values})
        return rows, excluded


def epoch_of(text):
    return to_epoch(parse_iso(text))


def mean_dec(values, places):
    total = ZERO
    for value in values:
        total += value
    return qdec(total / len(values), places)


def feature_text(name, value):
    """A feature value as the contract writes it."""
    if value is None:
        return None
    if name in INT_FEATURES:
        return int(value)
    return fmt_dec(value if isinstance(value, Decimal) else Decimal(str(value)), 4)


def phase2(p1_dir, out_dir):
    if not os.path.isdir(p1_dir):
        die("phase 1 directory %s is missing" % p1_dir)
    phase = Phase2(p1_dir)
    labels, digest, controls = upstream_of_phase1(p1_dir)
    lineage = {"upstream_digest": digest, "upstream_controls": controls}
    rows, excluded = phase.features()
    splits = {}
    for row in rows:
        splits[(row["asset_id"], row["day"])] = phase.split_of(row["asset_id"],
                                                              row["day"])
    label_rows = [{"asset_id": row["asset_id"], "day": row["day"].isoformat(),
                   "split": splits[(row["asset_id"], row["day"])],
                   "label": row["label"]} for row in rows]
    feature_rows = []
    for row in rows:
        item = {"asset_id": row["asset_id"], "day": row["day"].isoformat()}
        for name in FEATURES:
            item[name] = feature_text(name, row["values"][name])
        feature_rows.append(item)
    train = [r for r in rows if splits[(r["asset_id"], r["day"])] == "train"]
    scaler = {}
    for name in FEATURES:
        values = [r["values"][name] for r in train if r["values"][name] is not None]
        n = len(values)
        if n < 2:
            scaler[name] = {"n": n, "mean": None, "std": None}
            continue
        total = ZERO
        for value in values:
            total += value
        mean = total / n
        variance = ZERO
        for value in values:
            variance += (value - mean) * (value - mean)
        std = (variance / (n - 1)).sqrt()
        scaler[name] = {"n": n, "mean": json_dec(qdec(mean, 6), 6),
                        "std": json_dec(qdec(std, 6), 6)}
    balance = {}
    for split in ("train", "val", "test"):
        split_rows = [r for r in rows if splits[(r["asset_id"], r["day"])] == split]
        positives = sum(1 for r in split_rows if r["label"] == 1)
        prevalence = qdec(Decimal(positives) / len(split_rows), 6) if split_rows \
            else ZERO
        balance[split] = {"rows": len(split_rows), "positives": positives,
                          "negatives": len(split_rows) - positives,
                          "prevalence": json_dec(prevalence, 6)}
    train_rows = balance["train"]["rows"]
    weights = {
        "positive": json_dec(qdec(Decimal(train_rows) /
                                  (2 * balance["train"]["positives"]), 6), 6)
        if balance["train"]["positives"] else None,
        "negative": json_dec(qdec(Decimal(train_rows) /
                                  (2 * balance["train"]["negatives"]), 6), 6)
        if balance["train"]["negatives"] else None,
    }
    edges = {}
    for name in FEATURES:
        values = sorted(r["values"][name] for r in train
                        if r["values"][name] is not None)
        if len(values) < 10:
            edges[name] = []
            continue
        out = []
        for k in range(1, 10):
            index = -(-k * len(values) // 10)
            out.append(feature_text(name, values[index - 1]))
        edges[name] = out
    sites = set(row["site"] for row in rows)
    sites |= set(excluded)
    sites |= set(row["site"] for row in phase.sensor)
    quarantine = {}
    for site in sorted(sites):
        readings = sum(int(row["quarantined"]) for row in phase.sensor
                      if row["site"] == site)
        kept = sum(1 for row in rows if row["site"] == site)
        reasons = {name: excluded.get(site, {}).get(name, 0)
                   for name in EXCLUDE_REASONS}
        quarantine[site] = {"readings_quarantined": readings,
                            "samples_kept": kept, "excluded": reasons}
    os.makedirs(out_dir, exist_ok=True)
    write_json(os.path.join(out_dir, "label_table.json"), dict(lineage, rows=label_rows))
    write_json(os.path.join(out_dir, "feature_matrix.json"),
               dict(lineage, features=FEATURES, rows=feature_rows))
    write_json(os.path.join(out_dir, "scaler_stats.json"),
               dict(lineage, fit_split="train", features=scaler))
    write_json(os.path.join(out_dir, "class_balance.json"),
               dict(lineage, splits=balance, class_weights=weights))
    write_json(os.path.join(out_dir, "quarantine_summary.json"),
               dict(lineage, sites=quarantine))
    write_json(os.path.join(out_dir, "bin_edges.json"),
               dict(lineage, features=edges))
    return 0


# --------------------------------------------------------------------------
# phase 3
# --------------------------------------------------------------------------

def load_phase2(p2_dir):
    docs = {}
    for name in P2_FILES:
        path = os.path.join(p2_dir, name)
        if not os.path.isfile(path):
            die("%s is missing from %s" % (name, p2_dir))
        with open(path, encoding="utf-8") as fh:
            docs[name] = json.load(fh)
    return docs


def file_digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def upstream_labels(p1_dir, p2_dir):
    labels = ["p1/" + name for name in sorted(P1_FILES)]
    labels += ["p2/" + name for name in sorted(P2_FILES)]
    digest = hashlib.sha256()
    for label in labels:
        name = label[3:]
        path = os.path.join(p1_dir if label.startswith("p1/") else p2_dir, name)
        if not os.path.isfile(path):
            die("%s is missing" % name)
        digest.update((label + "\n").encode("utf-8"))
        digest.update(file_digest(path).encode("utf-8") + b"\n")
    return labels, digest.hexdigest()


def controls_of_phase2(p1_controls, docs):
    """The upstream controls of the phase 2 files the contract defines."""
    out = dict(p1_controls)
    label_rows = docs["label_table.json"]["rows"]
    out["p2/label_table.json"] = {
        "rows": len(label_rows),
        "total": str(sum(int(r["label"]) for r in label_rows)),
        "last_key": ("%s|%s" % (label_rows[-1]["asset_id"], label_rows[-1]["day"])
                     if label_rows else ""),
    }
    feature_rows = docs["feature_matrix.json"]["rows"]
    out["p2/feature_matrix.json"] = {
        "rows": len(feature_rows),
        "total": str(sum(int(r["alarms_7d"]) for r in feature_rows
                         if r["alarms_7d"] is not None)),
        "last_key": ("%s|%s" % (feature_rows[-1]["asset_id"], feature_rows[-1]["day"])
                     if feature_rows else ""),
    }
    scaler = docs["scaler_stats.json"]["features"]
    names = sorted(scaler)
    out["p2/scaler_stats.json"] = {
        "rows": len(names),
        "total": str(sum(scaler[n]["n"] for n in names)),
        "last_key": names[-1] if names else "",
    }
    edges = docs["bin_edges.json"]["features"]
    names = sorted(edges)
    out["p2/bin_edges.json"] = {
        "rows": len(names),
        "total": str(sum(len(edges[n]) for n in names)),
        "last_key": names[-1] if names else "",
    }
    balance = docs["class_balance.json"]["splits"]
    names = sorted(balance)
    out["p2/class_balance.json"] = {
        "rows": len(names),
        "total": str(sum(balance[n]["rows"] for n in names)),
        "last_key": names[-1] if names else "",
    }
    quarantine = docs["quarantine_summary.json"]["sites"]
    names = sorted(quarantine)
    out["p2/quarantine_summary.json"] = {
        "rows": len(names),
        "total": str(sum(quarantine[n]["samples_kept"] for n in names)),
        "last_key": names[-1] if names else "",
    }
    return out


def auc_of(scores, labels):
    """AUC with average ranks for tied scores (FPS-4 11.3)."""
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [Decimal(0)] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        average = Decimal(i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    positives = sum(1 for label in labels if label == 1)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    rank_sum = ZERO
    for i in range(len(labels)):
        if labels[i] == 1:
            rank_sum += ranks[i]
    return (rank_sum - Decimal(positives * (positives + 1)) / 2) / (
        positives * negatives)


def f1_of(tp, fp, fn):
    precision = Decimal(tp) / (tp + fp) if tp + fp else ZERO
    recall = Decimal(tp) / (tp + fn) if tp + fn else ZERO
    if precision + recall == 0:
        return ZERO
    return 2 * precision * recall / (precision + recall)


def phase3(p1_dir, p2_dir, out_dir):
    if not os.path.isdir(p1_dir):
        die("phase 1 directory %s is missing" % p1_dir)
    if not os.path.isdir(p2_dir):
        die("phase 2 directory %s is missing" % p2_dir)
    _assets, sensor, events, _maint, _sites, settings = load_phase1(p1_dir)
    docs = load_phase2(p2_dir)
    params = settings["parameters"]
    labels, digest = upstream_labels(p1_dir, p2_dir)
    controls = controls_of_phase2(upstream_of_phase1(p1_dir)[2], docs)
    lineage = {"upstream_digest": digest, "upstream_controls": controls}
    scaler = docs["scaler_stats.json"]["features"]
    weights = docs["class_balance.json"]["class_weights"]
    label_rows = docs["label_table.json"]["rows"]
    feature_rows = docs["feature_matrix.json"]["rows"]
    edges = docs["bin_edges.json"]["features"]
    asset_info = {row["asset_id"]: row for row in _assets}
    train_end = parse_day(params["train_end"])
    decay = Decimal(params["decay_half_life_days"])
    cap = Decimal(params["asset_weight_cap"])
    crit = {"a": Decimal(params["crit_multiplier_a"]),
            "b": Decimal(params["crit_multiplier_b"]),
            "c": Decimal(params["crit_multiplier_c"])}
    rows = []
    for label_row, feature_row in zip(label_rows, feature_rows):
        split = label_row["split"]
        z = {}
        for name in FEATURES:
            raw = feature_row[name]
            stats = scaler[name]
            if raw is None or stats["mean"] is None or stats["std"] is None:
                z[name] = None
                continue
            deviation = Decimal(str(raw)) - Decimal(stats["mean"])
            std = Decimal(stats["std"])
            z[name] = json_dec(qdec(deviation / std, 4), 4) if std != 0 else None
        if split == "train":
            class_weight = Decimal(weights["positive"] if label_row["label"] == 1
                                   else weights["negative"])
            days = (train_end - parse_day(label_row["day"])).days
            recency = qdec(Decimal("0.5") ** (Decimal(days) / decay), 6)
            criticality = asset_info.get(label_row["asset_id"], {}).get(
                "criticality", "")
            weight = qdec(class_weight * recency * crit.get(criticality, Decimal(1)), 6)
        else:
            weight = Decimal(1)
        rows.append({"asset_id": label_row["asset_id"], "day": label_row["day"],
                     "split": split, "label": label_row["label"], "z": z,
                     "weight": weight})
    by_asset = defaultdict(list)
    for row in rows:
        if row["split"] == "train":
            by_asset[row["asset_id"]].append(row)
    for asset_rows in by_asset.values():
        remaining = cap
        for row in sorted(asset_rows, key=lambda r: r["day"]):
            if remaining <= 0:
                row["weight"] = ZERO
                continue
            if row["weight"] > remaining:
                row["weight"] = qdec(remaining, 6)
            remaining -= row["weight"]
    bias = Decimal(params["score_bias"])
    score_weights = {name: Decimal(params["score_weight_" + name])
                     for name in FEATURES if "score_weight_" + name in params}
    for row in rows:
        total = bias
        for name in FEATURES:
            if row["z"][name] is None or name not in score_weights:
                continue
            total += score_weights[name] * Decimal(row["z"][name])
        row["score"] = qdec(total, 6)

    def split_rows(split):
        return [r for r in rows if r["split"] == split]

    train_rows = split_rows("train")
    val_rows = split_rows("val")
    test_rows = split_rows("test")
    val_auc = auc_of([r["score"] for r in val_rows], [r["label"] for r in val_rows])
    test_auc = auc_of([r["score"] for r in test_rows], [r["label"] for r in test_rows])
    threshold = None
    best_f1 = ZERO
    for score in sorted(set(r["score"] for r in val_rows), reverse=True):
        tp = sum(1 for r in val_rows if r["score"] >= score and r["label"] == 1)
        fp = sum(1 for r in val_rows if r["score"] >= score and r["label"] == 0)
        fn = sum(1 for r in val_rows if r["score"] < score and r["label"] == 1)
        current = f1_of(tp, fp, fn)
        if threshold is None or current > best_f1:
            threshold = score
            best_f1 = current
    tp = fp = fn = tn = 0
    if threshold is not None:
        for row in test_rows:
            if row["score"] >= threshold:
                if row["label"] == 1:
                    tp += 1
                else:
                    fp += 1
            elif row["label"] == 1:
                fn += 1
            else:
                tn += 1
    precision = qdec(Decimal(tp) / (tp + fp), 6) if tp + fp else ZERO
    recall = qdec(Decimal(tp) / (tp + fn), 6) if tp + fn else ZERO
    test_f1 = qdec(f1_of(tp, fp, fn), 6)
    os.makedirs(out_dir, exist_ok=True)
    write_json(os.path.join(out_dir, "train_ready.json"), dict(
        lineage, features=FEATURES,
        rows=[{"asset_id": row["asset_id"], "day": row["day"],
               "split": row["split"], "label": row["label"], "z": row["z"],
               "sample_weight": json_dec(row["weight"], 6)} for row in rows]))
    write_json(os.path.join(out_dir, "baseline_metrics.json"), dict(
        lineage,
        val={"rows": len(val_rows),
             "positives": sum(1 for r in val_rows if r["label"] == 1),
             "auc": json_dec(qdec(val_auc, 6), 6) if val_auc is not None else None,
             "threshold": json_dec(threshold, 6) if threshold is not None else None,
             "f1": json_dec(best_f1, 6)},
        test={"rows": len(test_rows),
              "positives": sum(1 for r in test_rows if r["label"] == 1),
              "tp": tp, "fp": fp, "fn": fn, "tn": tn,
              "auc": json_dec(qdec(test_auc, 6), 6) if test_auc is not None else None,
              "precision": json_dec(precision, 6),
              "recall": json_dec(recall, 6), "f1": json_dec(test_f1, 6)}))
    # drift report (FPS-4 11.4)
    drift = {}
    for name in FEATURES:
        feature_edges = [Decimal(str(e)) for e in edges[name]]
        split_of_row = [r["split"] for r in rows]
        shares = {}
        for split_name in ("train", "test"):
            values = [Decimal(str(feature_rows[i][name])) for i, r in enumerate(rows)
                      if split_of_row[i] == split_name and feature_rows[i][name] is not None]
            counts = [0] * (len(feature_edges) + 1)
            for value in values:
                counts[sum(1 for e in feature_edges if value > e)] += 1
            total = len(values)
            shares[split_name] = [Decimal(c) / total if total else ZERO
                                  for c in counts]
            shares[split_name + "_n"] = total
        psi = ZERO
        for index in range(len(feature_edges) + 1):
            train_share = shares["train"][index]
            test_share = shares["test"][index]
            if train_share == 0:
                train_share = Decimal("0.0001")
            if test_share == 0:
                test_share = Decimal("0.0001")
            psi += (test_share - train_share) * (test_share / train_share).ln()
        drift[name] = {
            "psi": json_dec(qdec(psi, 6), 6),
            "null_share_train": json_dec(
                qdec(Decimal(len(train_rows) - shares["train_n"]) / len(train_rows), 6)
                if train_rows else ZERO, 6),
            "null_share_test": json_dec(
                qdec(Decimal(len(test_rows) - shares["test_n"]) / len(test_rows), 6)
                if test_rows else ZERO, 6),
        }
    write_json(os.path.join(out_dir, "drift_report.json"), dict(lineage, features=drift))
    # review budget allocation (FPS-4 12.1 - 12.3)
    regions = settings["regions"]
    budget = int(params["review_budget"])
    site_cap = int(Decimal(params["site_cap_share"]) * budget)
    region_cap = int(Decimal(params["region_cap_share"]) * budget)
    site_of_sample = {}
    for row in sensor:
        site_of_sample[(row["asset_id"], row["day"])] = row["site"]
    positives = defaultdict(int)
    for row in train_rows:
        if row["label"] == 1:
            positives[site_of_sample.get((row["asset_id"], row["day"]), "")] += 1
    total_positives = sum(positives.values())
    quotas = {}
    for site in sorted(set(positives) | set(regions)):
        quota = Decimal(budget) * positives.get(site, 0) / total_positives \
            if total_positives else ZERO
        quotas[site] = quota
    allocated = {site: 0 for site in quotas}
    remaining_region = {region: region_cap for region in sorted(set(regions.values()))}
    for site in sorted(quotas, key=lambda s: (-quotas[s], s)):
        take = min(int(quotas[site]), site_cap)
        region = regions.get(site)
        if region in remaining_region:
            take = min(take, remaining_region[region])
        allocated[site] = take
        if region in remaining_region:
            remaining_region[region] -= take
    remaining = budget - sum(allocated.values())
    while remaining > 0:
        progressed = False
        order = sorted(quotas, key=lambda s: (-(quotas[s] - int(quotas[s])), s))
        for site in order:
            if remaining <= 0:
                break
            if positives.get(site, 0) == 0:
                continue
            if allocated[site] >= site_cap:
                continue
            region = regions.get(site)
            if region in remaining_region and remaining_region[region] <= 0:
                continue
            allocated[site] += 1
            remaining -= 1
            progressed = True
            if region in remaining_region:
                remaining_region[region] -= 1
        if not progressed:
            break
    sites_out = {}
    for site in sorted(quotas):
        whole = int(quotas[site])
        sites_out[site] = {
            "region": regions.get(site, ""),
            "train_positives": positives.get(site, 0),
            "allocated": allocated[site],
            "quota": json_dec(qdec(quotas[site], 4), 4),
            "capped": allocated[site] < whole,
        }
    write_json(os.path.join(out_dir, "site_allocation.json"), dict(
        lineage, budget=budget, site_cap=site_cap, region_cap=region_cap,
        unallocated=remaining, sites=sites_out))
    # amendment impact (FPS-4 12.4)
    horizon = int(params["horizon_days"])
    confirmed = defaultdict(set)
    for row in events:
        if row["status"] == "confirmed" and row["failed_day"]:
            confirmed[row["asset_id"]].add(parse_day(row["failed_day"]))
    pending_events = set()
    amended = defaultdict(set)
    rejected = set()
    for row in events:
        if not row["pending_decision"]:
            continue
        pending_events.add(row["event_id"])
        if row["pending_decision"] in ("confirm", "reclassify"):
            if row["failed_day"]:
                amended[row["asset_id"]].add(parse_day(row["failed_day"]))
        else:
            rejected.add(row["asset_id"])
    amended_confirmed = {}
    for asset in set(confirmed) | set(amended) | rejected:
        days = set(confirmed.get(asset, set())) | set(amended.get(asset, set()))
        if asset in rejected:
            days -= set(parse_day(r["failed_day"]) for r in events
                        if r["asset_id"] == asset and r["status"] == "confirmed")
        amended_confirmed[asset] = days
    changes = []
    by_split = defaultdict(lambda: {"flipped_up": 0, "flipped_down": 0})
    for row in rows:
        asset = row["asset_id"]
        day = parse_day(row["day"])
        new_label = 0
        for failure in sorted(amended_confirmed.get(asset, ())):
            if day <= failure - dt.timedelta(days=1) and failure <= day + dt.timedelta(
                    days=horizon):
                new_label = 1
                break
        if new_label != row["label"]:
            changes.append({"asset_id": asset, "day": row["day"],
                            "split": row["split"], "old_label": row["label"],
                            "new_label": new_label})
            key = "flipped_up" if new_label == 1 else "flipped_down"
            by_split[row["split"]][key] += 1
    changes.sort(key=lambda c: (c["asset_id"], c["day"]))
    write_json(os.path.join(out_dir, "amendment_impact.json"), dict(
        lineage, events_with_pending_amendment=len(pending_events),
        label_changes=changes, by_split=dict(by_split)))
    # release manifest
    files = {}
    for label in labels:
        name = label[3:]
        path = os.path.join(p1_dir if label.startswith("p1/") else p2_dir, name)
        files[label] = file_digest(path)
    write_json(os.path.join(out_dir, "release_manifest.json"), dict(
        lineage, run_id=settings["run_id"], files=files,
        rows={split: len(split_rows(split)) for split in ("train", "val", "test")},
        features=FEATURES))
    return 0



# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

STAGES = {"phase1": 2, "phase2": 2, "phase3": 3}


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("error: no stage given\n")
        return 2
    stage = argv[1]
    if stage not in STAGES:
        sys.stderr.write("error: unknown stage %s\n" % stage)
        return 2
    if len(argv) != STAGES[stage] + 2:
        sys.stderr.write("error: %s takes %d directories\n"
                         % (stage, STAGES[stage]))
        return 2
    dirs = argv[2:]
    for name in dirs[:-1]:
        if not os.path.isdir(name):
            die("input directory %s is missing" % name)
    if stage == "phase1":
        return phase1(dirs[0], dirs[1])
    if stage == "phase2":
        return phase2(dirs[0], dirs[1])
    return phase3(dirs[0], dirs[1], dirs[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
