#!/usr/bin/env python3
"""Kestrel feature pipeline: rebuild the training data of the pump failure model.

  build.py phase1 DATA_DIR P1_DIR
  build.py phase2 P1_DIR P2_DIR
  build.py phase3 P1_DIR P2_DIR P3_DIR

Exit status 2 for wrong arguments, 3 for an input or upstream directory that is missing,
unreadable or lacks a required file; in both cases one line starting with "error:" goes to
standard error and nothing is written.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from pathlib import Path

UTC = timezone.utc


class UsageError(Exception):
    pass


class InputError(Exception):
    pass


def dq(x, dp: int) -> Decimal:
    if isinstance(x, Fraction):
        with localcontext() as c:
            c.prec = 60
            x = Decimal(x.numerator) / Decimal(x.denominator)
    v = Decimal(x).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_EVEN)
    return v.copy_abs() if v == 0 else v


def sfmt(x, dp: int) -> str:
    return format(dq(x, dp), "f")


# ---------------------------------------------------------------- the standard
class Standard:
    """Reference tables read from the shipped standard."""

    def __init__(self, text: str):
        self.text = text
        self.register: dict[str, dict[str, list]] = {}
        self.vocabs: dict[str, list[str]] = {}
        self.sites: dict[str, dict] = {}
        self.site_by_num: dict[str, str] = {}
        self.models: dict[str, str] = {}
        self.roles: dict[str, str] = {}
        self.freeze = None
        self.window = None
        for rows, header in self._tables():
            h = tuple(header)
            if h == ("file", "table", "field", "type"):
                for f, t, fld, ty in rows:
                    self.register.setdefault(f, {}).setdefault(t, []).append((fld, ty))
            elif h == ("vocabulary", "values"):
                for v, vals in rows:
                    self.vocabs[v] = vals.split(", ")
            elif h == ("site", "number", "name", "time zone rule", "region"):
                for code, num, name, tz, reg in rows:
                    self.sites[code] = {"num": num, "tz": tz, "region": reg}
                    self.site_by_num[num] = code
            elif h == ("model", "oem"):
                self.models = {m: o for m, o in rows}
            elif h == ("file", "role"):
                self.roles = {f: r for f, r in rows}
        m = re.search(r"as-of freeze is `([0-9TZ:\-]+)`", text)
        self.freeze = parse_iso_z(m.group(1))
        m = re.search(r"telemetry window runs from `([0-9\-]+)` to `([0-9\-]+)`", text)
        self.window = (date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2)))

    def _tables(self):
        lines = self.text.split("\n")
        i = 0
        while i < len(lines):
            if lines[i].startswith("| ") and i + 1 < len(lines) and lines[i + 1].startswith("|---"):
                header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows = []
                j = i + 2
                while j < len(lines) and lines[j].startswith("| "):
                    rows.append([c.strip() for c in lines[j].strip()[1:-1].split(" | ")])
                    j += 1
                yield rows, header
                i = j
            else:
                i += 1


def parse_iso_z(s: str) -> datetime:
    return datetime(int(s[0:4]), int(s[5:7]), int(s[8:10]), int(s[11:13]), int(s[14:16]), int(s[17:19]), tzinfo=UTC)


def iso_z(t: datetime) -> str:
    t = t.astimezone(UTC)
    return f"{t.year:04d}-{t.month:02d}-{t.day:02d}T{t.hour:02d}:{t.minute:02d}:{t.second:02d}Z"


# ---------------------------------------------------------------- time zones
def _last_sunday(y: int, m: int) -> date:
    d = date(y, m + 1, 1) - timedelta(days=1)
    while d.weekday() != 6:
        d -= timedelta(days=1)
    return d


def _nth_sunday(y: int, m: int, n: int) -> date:
    d = date(y, m, 1)
    while d.weekday() != 6:
        d += timedelta(days=1)
    return d + timedelta(days=7 * (n - 1))


def utc_offset(rule: str, t: datetime) -> int:
    if rule == "ist":
        return 330
    y = t.year
    if rule in ("eu", "uk"):
        a = datetime.combine(_last_sunday(y, 3), datetime.min.time(), UTC) + timedelta(hours=1)
        b = datetime.combine(_last_sunday(y, 10), datetime.min.time(), UTC) + timedelta(hours=1)
        return (60 if rule == "eu" else 0) + (60 if a <= t < b else 0)
    if rule == "us":
        a = datetime.combine(_nth_sunday(y, 3, 2), datetime.min.time(), UTC) + timedelta(hours=7)
        b = datetime.combine(_nth_sunday(y, 11, 1), datetime.min.time(), UTC) + timedelta(hours=6)
        return -300 + (60 if a <= t < b else 0)
    raise InputError(f"unknown time zone rule {rule}")


def local_to_utc(rule: str, ln: datetime) -> datetime:
    for probe in (-12, 12):
        off = utc_offset(rule, ln.replace(tzinfo=UTC) + timedelta(hours=probe))
        cand = (ln - timedelta(minutes=off)).replace(tzinfo=UTC)
        if utc_offset(rule, cand) == off:
            return cand
    raise InputError(f"local time {ln} does not exist")


def local_date(rule: str, t: datetime) -> date:
    return (t + timedelta(minutes=utc_offset(rule, t))).date()


def day_span(rule: str, d: date) -> tuple[datetime, datetime]:
    return (local_to_utc(rule, datetime.combine(d, datetime.min.time())),
            local_to_utc(rule, datetime.combine(d + timedelta(days=1), datetime.min.time())))


# ---------------------------------------------------------------- a small YAML reader
def read_yaml(text: str):
    """Reads the block YAML used by the registers: mappings, lists, JSON flow values."""
    lines = [ln for ln in text.split("\n") if ln.strip() and not ln.lstrip().startswith("#")]
    pos = 0

    def scalar(v: str):
        v = v.strip()
        if v.startswith("{") or v.startswith("[") or v.startswith('"'):
            return json.loads(v)
        return v

    def block(indent: int):
        nonlocal pos
        if pos >= len(lines):
            return None
        first = lines[pos]
        if first[indent:].startswith("- "):
            out = []
            while pos < len(lines) and len(lines[pos]) - len(lines[pos].lstrip()) == indent and lines[pos][indent:].startswith("- "):
                body = lines[pos][indent + 2:]
                if ": " in body and not body.startswith("{") or body.endswith(":"):
                    lines[pos] = " " * (indent + 2) + body
                    out.append(block(indent + 2))
                else:
                    out.append(scalar(body))
                    pos += 1
            return out
        out = {}
        while pos < len(lines) and len(lines[pos]) - len(lines[pos].lstrip()) == indent and not lines[pos][indent:].startswith("- "):
            key, _, val = lines[pos][indent:].partition(":")
            pos += 1
            if val.strip():
                out[key] = scalar(val)
            else:
                nxt = len(lines[pos]) - len(lines[pos].lstrip()) if pos < len(lines) else -1
                out[key] = block(nxt) if nxt > indent or (nxt == indent and pos < len(lines) and lines[pos][indent:].startswith("- ")) else None
        return out

    return block(0)


# ---------------------------------------------------------------- container formats -> segments
def _kv_line(line: str) -> list[tuple[str, str]]:
    return re.findall(r'(\w+)="([^"]*)"', line)


def read_segments(fmt: str, text: str) -> list[dict]:
    """Each segment: {"id", "table", "rows": list of dict name -> text or None, "control": (rows, sum)}."""
    segs: list[dict] = []
    lines = text.split("\n")
    if fmt in ("csv", "tsv"):
        delim = "," if fmt == "csv" else "\t"
        cur = None
        header = None
        for ln in lines:
            if ln.startswith("#segment "):
                cur = {"id": ln.split()[1], "rows": [], "table": None}
                segs.append(cur)
                header = None
            elif ln.startswith("#control "):
                kv = dict(x.split("=") for x in ln.split()[1:])
                cur["control"] = (int(kv["rows"]), kv["sum"])
            elif ln and cur is not None:
                vals = next(csv.reader([ln], delimiter=delim))
                if header is None:
                    header = vals
                else:
                    cur["rows"].append(dict(zip(header, vals)))
    elif fmt == "jsonl":
        cur = None
        for ln in lines:
            if not ln:
                continue
            obj = json.loads(ln)
            if set(obj) == {"segment"}:
                cur = {"id": obj["segment"], "rows": [], "table": None}
                segs.append(cur)
            elif set(obj) == {"control"}:
                cur["control"] = (obj["control"]["rows"], obj["control"]["sum"])
            else:
                cur["rows"].append(obj)
    elif fmt == "json":
        doc = json.loads(text)
        for s in doc["segments"]:
            segs.append({"id": s["segment"], "rows": s["rows"], "table": None, "control": (s["control"]["rows"], s["control"]["sum"])})
    elif fmt == "xml":
        root = ET.fromstring(text)
        for s in root.findall("segment"):
            c = s.find("control")
            segs.append({"id": s.get("id"), "table": None, "rows": [dict(r.attrib) for r in s.findall("r")],
                         "control": (int(c.get("rows")), c.get("sum"))})
    elif fmt == "yaml":
        doc = read_yaml(text)
        for s in doc["segments"]:
            segs.append({"id": s["segment"], "table": None, "rows": s["rows"], "control": (s["control"]["rows"], s["control"]["sum"])})
    elif fmt == "toml":
        doc = tomllib.loads(text)
        for s in doc["segment"]:
            segs.append({"id": s["id"], "table": s.get("table"), "rows": s["rows"], "control": (s["control"]["rows"], s["control"]["sum"])})
    elif fmt == "ini":
        cur = None
        cols = None
        for ln in lines:
            if ln.startswith("[segment "):
                cur = {"id": ln[9:-1], "rows": [], "table": None}
                segs.append(cur)
            elif ln.startswith("columns = "):
                cols = ln[10:].split(";")
            elif ln.startswith("control = "):
                kv = dict(x.split("=") for x in ln[10:].split(";"))
                cur["control"] = (int(kv["rows"]), kv["sum"])
            elif ln.startswith("row") and cur is not None:
                cur["rows"].append(dict(zip(cols, ln.split(" = ", 1)[1].split(";"))))
    elif fmt == "md":
        cur = None
        header = None
        for ln in lines:
            if ln.startswith("### Segment "):
                cur = {"id": ln[12:].strip(), "rows": [], "table": None}
                segs.append(cur)
                header = None
            elif cur is not None and ln.startswith("| "):
                cells = [c.strip() for c in ln.strip()[1:-1].split(" | ")]
                if header is None:
                    header = cells
                else:
                    cur["rows"].append(dict(zip(header, cells)))
            elif cur is not None and ln.startswith("Control: rows "):
                m = re.match(r"Control: rows (\d+), sum (\S+)", ln)
                cur["control"] = (int(m.group(1)), m.group(2))
    elif fmt == "html":
        cur = None
        header = None
        for ln in lines:
            m = re.match(r'<table data-segment="([^"]+)">', ln)
            if m:
                cur = {"id": m.group(1), "rows": [], "table": None}
                segs.append(cur)
                header = None
            elif ln.startswith("<tr><th>"):
                header = re.findall(r"<th>(.*?)</th>", ln)
            elif ln.startswith("<tr><td>"):
                cur["rows"].append(dict(zip(header, [html.unescape(x) for x in re.findall(r"<td>(.*?)</td>", ln)])))
            elif ln.startswith('<p class="control">'):
                m = re.match(r'<p class="control">rows (\d+) sum (\S+)</p>', ln)
                cur["control"] = (int(m.group(1)), m.group(2))
    elif fmt == "log":
        cur = None
        for ln in lines:
            if ln.startswith("# segment "):
                cur = {"id": ln[10:].strip(), "rows": [], "table": None}
                segs.append(cur)
            elif ln.startswith("# control "):
                kv = dict(x.split("=") for x in ln[10:].split())
                cur["control"] = (int(kv["rows"]), kv["sum"])
            elif ln.startswith("rec "):
                cur["rows"].append(dict(_kv_line(ln)))
    elif fmt == "mbox":
        cur = None
        cols = None
        for ln in lines:
            if ln.startswith("Subject: data quality tickets, segment "):
                cur = {"id": ln.rsplit(" ", 1)[1], "rows": [], "table": None}
                segs.append(cur)
            elif ln.startswith("Columns: "):
                cols = ln[9:].split(" | ")
            elif ln.startswith("Control: rows "):
                m = re.match(r"Control: rows (\d+) sum (\S+)", ln)
                cur["control"] = (int(m.group(1)), m.group(2))
            elif cur is not None and " | " in ln and cols:
                cur["rows"].append(dict(zip(cols, ln.split(" | "))))
    elif fmt == "ics":
        cur = None
        ev = None
        for ln in lines:
            if ln.startswith("X-SEGMENT:"):
                cur = {"id": ln[10:], "rows": [], "table": None}
                segs.append(cur)
            elif ln == "BEGIN:VEVENT":
                ev = {}
            elif ln == "END:VEVENT":
                cur["rows"].append(ev)
                ev = None
            elif ln.startswith("X-CONTROL:"):
                kv = dict(x.split("=") for x in ln[10:].split(";"))
                cur["control"] = (int(kv["rows"]), kv["sum"])
            elif ev is not None:
                k, _, v = ln.partition(":")
                ev["@uid" if k == "UID" else k[2:].lower()] = v
    elif fmt == "txt":
        cur = None
        starts = names = None
        for ln in lines:
            if ln.startswith("SEGMENT "):
                cur = {"id": ln[8:].strip(), "rows": [], "table": None}
                segs.append(cur)
                starts = None
            elif ln.startswith("CONTROL "):
                kv = dict(x.split("=") for x in ln[8:].split())
                cur["control"] = (int(kv["rows"]), kv["sum"])
            elif cur is not None and ln:
                if starts is None:
                    names = ln.split()
                    starts = [m.start() for m in re.finditer(r"\S+", ln)]
                else:
                    vals = [ln[a:(starts[i + 1] if i + 1 < len(starts) else None)].strip() for i, a in enumerate(starts)]
                    cur["rows"].append(dict(zip(names, vals)))
    elif fmt == "sql":
        cur = None
        cols = None
        for ln in lines:
            if ln.startswith("-- segment "):
                cur = {"id": ln[11:].strip(), "rows": [], "table": None}
                segs.append(cur)
            elif ln.startswith("-- columns: "):
                cols = ln[12:].split(", ")
            elif ln.startswith("-- control "):
                kv = dict(x.split("=") for x in ln[11:].split())
                cur["control"] = (int(kv["rows"]), kv["sum"])
            elif ln.startswith("INSERT INTO "):
                body = ln[ln.index("VALUES (") + 8:-2]
                vals = re.findall(r"NULL|'((?:[^']|'')*)'", body)
                raw = re.findall(r"NULL|'(?:[^']|'')*'", body)
                out = [None if tok == "NULL" else v.replace("''", "'") for tok, v in zip(raw, vals)]
                cur["rows"].append(dict(zip(cols, out)))
    else:
        raise InputError(f"unknown format {fmt}")
    return segs


# ---------------------------------------------------------------- profiles
UNIT_FROM = {
    "mm_s": lambda x: x, "in_s": lambda x: x * Decimal("25.4"), "um_s": lambda x: x / 1000,
    "c": lambda x: x, "f": lambda x: (x - 32) / Decimal("1.8"), "k": lambda x: x - Decimal("273.15"),
    "bar": lambda x: x, "kpa": lambda x: x / 100, "psi": lambda x: x / Decimal("14.5037738"),
    "m3h": lambda x: x, "lps": lambda x: x * Decimal("3.6"), "gpm": lambda x: x / Decimal("4.402868"),
    "a": lambda x: x, "ma": lambda x: x / 1000, "ppm": lambda x: x, "ppb": lambda x: x / 1000,
    "h": lambda x: x, "min": lambda x: x / 60,
}
UNIT_EXTRA_DP = {"mm_s": 0, "in_s": 3, "um_s": -3, "c": 0, "f": 1, "k": 0, "bar": 0, "kpa": -2, "psi": 2,
                 "m3h": 0, "lps": 2, "gpm": 1, "a": 0, "ma": -3, "ppm": 0, "ppb": -3, "h": 0, "min": -2}
NULL_TOKENS = {"empty": "", "na": "NA", "dash": "-", "nullword": "null", "n999": "-999"}


def unit_places(base: int, unit: str) -> int:
    dp = base + UNIT_EXTRA_DP[unit]
    if unit == "k":
        dp = max(dp, 2)
    return max(dp, 0)


def resolve_profiles(registry: dict, draft: dict, errata: list | None, freeze: datetime) -> dict:
    """(file, segment) -> dims, following revisions, withdrawals, draft inheritance and errata."""
    best: dict = {}
    for e in registry["entries"]:
        if e["status"] != "active":
            continue
        key = (e["file"], e["segment"])
        if key not in best or int(e["revision"]) >= int(best[key]["revision"]):
            best[key] = e
    dbest: dict = {}
    for e in draft["entries"]:
        key = (e["file"], e["segment"])
        if key not in dbest or int(e["revision"]) >= int(dbest[key]["revision"]):
            dbest[key] = e
    fixes: dict = {}
    for x in errata or []:
        if x["target_file"] != "profiles_r7.yaml" or x["status"] != "approved" or x["approved_at"] > freeze:
            continue
        k = (x["target_rid"], x["field"])
        if k not in fixes or x["approved_at"] >= fixes[k]["approved_at"]:
            fixes[k] = x
    out = {}
    for key, e in best.items():
        dims = dict(dbest[key]["dims"]) if e.get("inherit") == "draft" else dict(e.get("dims") or {})
        ek = f"{key[0]}#{key[1]}#{e['revision']}"
        for (rid, fld), x in fixes.items():
            if rid == ek:
                dims[fld] = x["value"]
        out[key] = dims
    return out


# ---------------------------------------------------------------- value decoding
def unlocale(s: str, loc: str) -> str:
    s = s.strip()
    if loc == "plain":
        return s
    if loc == "en":
        return s.replace(",", "")
    if loc == "de":
        return s.replace(".", "").replace(",", ".")
    if loc == "fr":
        return s.replace(" ", "").replace(",", ".")
    if loc == "ch":
        return s.replace("'", "")
    raise InputError(loc)


def parse_date(s: str, form: str) -> date:
    if form == "iso":
        return date.fromisoformat(s)
    if form == "dmy":
        return date(int(s[6:10]), int(s[3:5]), int(s[0:2]))
    if form == "mdy":
        return date(int(s[6:10]), int(s[0:2]), int(s[3:5]))
    return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))


def parse_local(s: str, form: str) -> datetime:
    if form == "compact":
        return datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]), int(s[9:11]), int(s[11:13]), int(s[13:15]))
    d, t = s.split(" ")
    return datetime.combine(parse_date(d, form), time(int(t[0:2]), int(t[3:5]), int(t[6:8])))


class Context:
    """Reference data needed to resolve asset, site and local-time references."""

    def __init__(self, std: Standard):
        self.std = std
        self.serial_to_asset: dict[str, str] = {}
        self.site_events: dict[str, list] = {}
        self.tags: dict[tuple, list] = {}

    def site_at(self, asset: str, t: datetime) -> str | None:
        evs = self.site_events.get(asset, [])
        s = evs[0][1] if evs else None
        for at, site in evs:
            if at <= t:
                s = site
        return s

    def site_on_date(self, asset: str, d: date) -> str | None:
        return self.site_at(asset, datetime.combine(d, datetime.min.time(), UTC) + timedelta(hours=12))

    def tag_asset(self, system: str, tag: str, t: datetime) -> str:
        for vf, vt, aid in self.tags.get((system, tag), []):
            if vf <= t and (vt is None or t < vt):
                return aid
        raise InputError(f"tag {tag} has no assignment at {iso_z(t)}")


def decode_scalar(ftype: str, s, prof: dict):
    base = ftype.rstrip("?")
    nullable = ftype.endswith("?")
    tok = NULL_TOKENS[prof.get("nulls", "empty")]
    if s is None or (nullable and s == tok):
        if not nullable:
            raise InputError(f"null in non-nullable field ({ftype})")
        return None
    k = base.split(":")[0]
    if k in ("rid", "text"):
        return s
    if k == "date":
        return parse_date(s, prof["date_form"])
    if k == "int":
        return int(unlocale(s, prof.get("locale", "plain")))
    if k in ("q", "n"):
        parts = base.split(":")
        dp = int(parts[-1])
        txt = unlocale(s, prof.get("locale", "plain"))
        if k == "q":
            unit = prof["unit_" + parts[1]]
            dpu = unit_places(dp, unit)
        else:
            unit, dpu = None, dp
        val = Decimal(txt)
        if prof.get("numform") == "scaled":
            val = val.scaleb(-dpu)
        if unit:
            val = UNIT_FROM[unit](val)
        return dq(val, dp)
    if k == "code":
        st = prof.get("status", "word")
        voc = VOCAB[base.split(":")[1]]
        if st == "word":
            v = s
        elif st == "caps":
            v = s.lower()
        else:
            v = voc[int(s) - 1]
        if v not in voc:
            raise InputError(f"code {s} not in {base}")
        return v
    if k == "bool":
        b = prof.get("bool", "tf")
        t, f = {"tf": ("true", "false"), "yn": ("Y", "N"), "10": ("1", "0")}[b]
        if s not in (t, f):
            raise InputError(f"bool {s}")
        return s == t
    if k == "acode":
        cf = prof.get("codeform", "dec")
        return int(s) if cf == "dec" else (int(s[2:]) if cf == "pref" else int(s[2:], 16))
    raise InputError(ftype)


def decode_ts(s: str, prof: dict, rule: str | None) -> datetime:
    c = prof["clock"]
    if c == "utc":
        return parse_iso_z(s)
    if c == "epoch":
        return datetime.fromtimestamp(int(s), UTC)
    if c == "epoch_ms":
        return datetime.fromtimestamp(int(s) // 1000, UTC)
    if c == "offset":
        return datetime.fromisoformat(s).astimezone(UTC)
    if rule is None:
        raise InputError("local time without a site")
    return local_to_utc(rule, parse_local(s, prof["date_form"]))


VOCAB: dict[str, list[str]] = {}


def check_segment_control(name: str, seg: dict, fields: list, records: list[dict]) -> None:
    """Verify the pre-errata row count and control-field sum published by a segment."""
    control = seg.get("control")
    if control is None:
        raise InputError(f"{name} {seg['id']}: missing segment control")
    want_rows, want_sum = control
    if len(records) != want_rows:
        raise InputError(f"{name} {seg['id']}: control row count mismatch")
    selected = None
    for kind in ("q", "n", "int", "ts", "date"):
        selected = next(((field, spec) for field, spec in fields[1:] if spec.rstrip("?").split(":", 1)[0] == kind), None)
        if selected is not None:
            break
    if selected is None:
        raise InputError(f"{name} {seg['id']}: no control field")
    field, spec = selected
    kind = spec.rstrip("?").split(":", 1)[0]
    total = Fraction(0)
    for record in records:
        value = record[field]
        if value is None:
            continue
        if kind == "ts":
            total += Fraction(int(value.timestamp()))
        elif kind == "date":
            total += Fraction((value - date(1970, 1, 1)).days)
        else:
            total += Fraction(value)
    if total != Fraction(want_sum):
        raise InputError(f"{name} {seg['id']}: control sum mismatch")


def decode_segment(name: str, seg: dict, fields: list, prof: dict, alt: dict, system: str, ctx: Context) -> list[dict]:
    """Turn the text rows of one segment into canonical records (field -> value)."""
    names = {f: (f if prof.get("cols", "std") == "std" else alt[f]) for f, _ in fields}
    out = []
    types = dict(fields)
    for raw in seg["rows"]:
        if "@uid" in raw:
            raw = dict(raw)
            raw[names["rid"]] = raw.pop("@uid")
        rec: dict = {}
        get = {}
        for f, _t in fields:
            key = names[f]
            if key not in raw:
                key = key.lower()
            if key not in raw:
                raise InputError(f"{name} {seg['id']}: column {names[f]} missing")
            get[f] = raw[key]
        for f, t in fields:
            k = t.rstrip("?").split(":")[0]
            if k in ("ts", "asset", "site"):
                continue
            rec[f] = decode_scalar(t, get[f], prof)
        tok = NULL_TOKENS[prof.get("nulls", "empty")]
        if "site" in types:
            s = get["site"]
            if s is None or (types["site"].endswith("?") and s == tok):
                rec["site"] = None
            else:
                rec["site"] = s if prof.get("site_ref", "code") == "code" else ctx.std.site_by_num[s]
        ref = prof.get("asset_ref", "id")
        if "asset" in types:
            s = get["asset"]
            if ref == "id":
                rec["asset"] = s
            elif ref == "serial":
                rec["asset"] = ctx.serial_to_asset[s]
        for f, t in fields:
            if t.rstrip("?") != "ts":
                continue
            s = get[f]
            if s is None or (t.endswith("?") and s == tok):
                rec[f] = None
                continue
            rule = None
            if prof["clock"] == "local":
                if rec.get("site"):
                    rule = ctx.std.sites[rec["site"]]["tz"]
                else:
                    d = parse_local(s, prof["date_form"]).date()
                    rule = ctx.std.sites[ctx.site_on_date(rec["asset"], d)]["tz"]
            rec[f] = decode_ts(s, prof, rule)
        if "asset" in types and ref == "tag":
            reft = next(rec[f] for f, t in fields if t.rstrip("?") == "ts" and rec[f] is not None)
            rec["asset"] = ctx.tag_asset(system, get["asset"], reft)
        out.append(rec)
    return out


def canon_text(ftype: str, v) -> str:
    if v is None:
        return ""
    k = ftype.rstrip("?").split(":")[0]
    if k == "ts":
        return iso_z(v)
    if k == "date":
        return v.isoformat()
    if k in ("q", "n"):
        return format(v, "f")
    if k == "bool":
        return "true" if v else "false"
    return str(v)


def from_canon(ftype: str, s):
    if s is None or s == "":
        return None
    k = ftype.rstrip("?").split(":")[0]
    if k == "ts":
        return parse_iso_z(s)
    if k == "date":
        return date.fromisoformat(s)
    if k in ("q", "n"):
        return dq(Decimal(s), int(ftype.rstrip("?").split(":")[-1]))
    if k in ("int", "acode"):
        return int(s)
    if k == "bool":
        return s == "true"
    return s


# ---------------------------------------------------------------- loading the estate
FORMAT_OF = {".csv": "csv", ".tsv": "tsv", ".jsonl": "jsonl", ".json": "json", ".xml": "xml", ".yaml": "yaml",
             ".toml": "toml", ".ini": "ini", ".md": "md", ".html": "html", ".log": "log", ".mbox": "mbox",
             ".ics": "ics", ".txt": "txt", ".sql": "sql"}
STANDARD_FILE = "fps4_rules.md"
REGISTRY_FILE = "profiles_r7.yaml"
DRAFT_FILE = "profiles_r7_draft.yaml"
ERRATA_FILE = "errata_feed.csv"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read {path.name}: {exc}") from exc


class Estate:
    """Every source decoded into canonical records, before and after errata."""

    def __init__(self, data_dir: Path):
        if not data_dir.is_dir():
            raise InputError(f"input directory {data_dir} does not exist")
        self.dir = data_dir
        self.std = Standard(read_text(data_dir / STANDARD_FILE))
        VOCAB.clear()
        VOCAB.update(self.std.vocabs)
        self.freeze = self.std.freeze
        self.files = sorted(self.std.roles)
        missing = [f for f in self.files if not (data_dir / f).is_file()]
        if missing:
            raise InputError(f"input directory lacks {missing[0]}")
        self.registry = read_yaml(read_text(data_dir / REGISTRY_FILE))
        self.draft = read_yaml(read_text(data_dir / DRAFT_FILE))
        self.alt = {f: d["alt_columns"] for f, d in self.registry["dialects"].items()}
        self.system = {f: d["tag_system"] for f, d in self.registry["dialects"].items()}
        self.ctx = Context(self.std)
        self.raw: dict[str, dict[str, list]] = {}
        self.texts = {f: read_text(data_dir / f) for f in self.files if f != STANDARD_FILE}
        self.texts[STANDARD_FILE] = self.std.text
        boot = resolve_profiles(self.registry, self.draft, None, self.freeze)
        self._decode(ERRATA_FILE, boot)
        errata = self.raw[ERRATA_FILE]["erratum"]
        self.profiles = resolve_profiles(self.registry, self.draft, errata, self.freeze)
        self._decode(STANDARD_FILE, self.profiles)
        self._decode("asset_changes.csv", self.profiles)
        self.records: dict[str, dict[str, list]] = {}
        self._apply_errata("asset_changes.csv", errata)
        for r in self.records["asset_changes.csv"]["asset_event"]:
            if r["kind"] in ("baseline", "commission") and r["serial"]:
                self.ctx.serial_to_asset[r["serial"]] = r["asset"]
            if r["kind"] in ("baseline", "commission", "relocate") and r["site"]:
                self.ctx.site_events.setdefault(r["asset"], []).append((r["at"], r["site"]))
        for lst in self.ctx.site_events.values():
            lst.sort(key=lambda x: x[0])
        self._decode("tag_history.ini", self.profiles)
        for r in self.raw["tag_history.ini"]["tag"]:
            self.ctx.tags.setdefault((r["system"], r["tag"]), []).append((r["valid_from"], r["valid_to"], r["asset"]))
        for f in self.files:
            if f not in self.raw and f not in (REGISTRY_FILE, DRAFT_FILE):
                self._decode(f, self.profiles)
        for f in self.files:
            if f in self.raw and f not in self.records:
                self._apply_errata(f, errata)

    def tables_of(self, name: str) -> dict[str, list]:
        return self.std.register[name]

    def _decode(self, name: str, profiles: dict) -> None:
        fmt = FORMAT_OF[Path(name).suffix]
        segs = read_segments(fmt, self.texts[name])
        tables = self.tables_of(name)
        out = {t: [] for t in tables}
        self.segments = getattr(self, "segments", {})
        self.segments[name] = []
        for seg in segs:
            prof = profiles.get((name, seg["id"]))
            if prof is None:
                raise InputError(f"{name}: segment {seg['id']} has no profile")
            table = seg["table"] or next(iter(tables))
            recs = decode_segment(name, seg, tables[table], prof, self.alt[name], self.system[name], self.ctx)
            check_segment_control(name, seg, tables[table], recs)
            for r in recs:
                r["_seg"] = seg["id"]
            out[table].extend(recs)
            self.segments[name].append((seg["id"], table, len(recs), seg.get("control")))
        self.raw[name] = out

    def _apply_errata(self, name: str, errata: list) -> None:
        tables = self.tables_of(name)
        recs = {t: [dict(r) for r in rows] for t, rows in self.raw[name].items()}
        index: dict[str, list] = {}
        for t, rows in recs.items():
            for r in rows:
                index.setdefault(r["rid"], []).append((t, r))
        chosen: dict = {}
        for x in errata:
            if x["target_file"] != name or x["status"] != "approved" or x["approved_at"] > self.freeze:
                continue
            k = (x["target_rid"], x["field"])
            if k not in chosen or x["approved_at"] >= chosen[k]["approved_at"]:
                chosen[k] = x
        for (rid, fld), x in chosen.items():
            for t, r in index.get(rid, []):
                types = dict(tables[t])
                if fld in types and fld != "rid":
                    r[fld] = from_canon(types[fld], x["value"])
        self.records[name] = recs

    def attestation(self) -> list[dict]:
        out = []
        for f in self.files:
            if f in (REGISTRY_FILE, DRAFT_FILE):
                reg = self.registry if f == REGISTRY_FILE else self.draft
                lines = []
                for e in reg["entries"]:
                    dims = ";".join(f"{k}={v}" for k, v in sorted((e.get("dims") or {}).items()))
                    lines.append("|".join([e["file"], e["segment"], str(e["revision"]), e["status"], e.get("inherit") or "", dims]))
            else:
                lines = []
                for t, fields in self.tables_of(f).items():
                    for r in self.raw[f][t]:
                        lines.append("|".join(canon_text(ty, r[fl]) for fl, ty in fields))
            digest = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
            out.append({"file": f, "role": self.std.roles[f], "records": len(lines), "digest": digest})
        return out


# ---------------------------------------------------------------- phase 1: canonical tables
CH_PLACES = {"vib": 3, "temp": 2, "prs": 3, "flw": 2, "cur": 2}
CM_SOURCES = ["cm_gw_east.tsv", "cm_gw_north.log", "cm_gw_south.jsonl", "cm_gw_west.xml"]
HIST_SOURCES = ["hist_a.csv", "hist_b.sql", "hist_c.txt"]
ALARM_SOURCES = ["alarms_oem_a.log", "alarms_oem_b.xml", "alarms_oem_c.txt"]
SERVICE_KINDS = {"lubrication", "seal", "bearing", "impeller", "overhaul"}


def latest(items, key):
    """Last item by key; among equal keys the one written later wins."""
    best = None
    for it in items:
        if best is None or key(it) >= key(best):
            best = it
    return best


def mean_frac(vals) -> Fraction:
    return sum((Fraction(v) for v in vals), Fraction(0)) / len(vals)


def overlap_seconds(spans, a: datetime, b: datetime) -> int:
    cut = sorted((max(s, a), min(e, b)) for s, e in spans if e > a and s < b)
    total, cur_s, cur_e = 0, None, None
    for s, e in cut:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += (cur_e - cur_s).total_seconds()
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += (cur_e - cur_s).total_seconds()
    return int(total)


class Phase1:
    def __init__(self, es: Estate):
        self.es = es
        self.F = es.freeze
        R = es.records
        self.R = R
        self.params = self._params()
        self.assets = self._assets()
        self.tz = {c: s["tz"] for c, s in es.std.sites.items()}

    # parameters
    def _params(self) -> dict:
        best: dict = {}
        for p in self.R["kp24_runsheet.toml"]["param"]:
            if p["status"] != "active" or p["set_at"] > self.F:
                continue
            if p["name"] not in best or p["rev"] >= best[p["name"]]["rev"]:
                best[p["name"]] = p
        return {k: v["value"] for k, v in sorted(best.items())}

    # assets
    def _assets(self) -> dict:
        evs: dict[str, list] = {}
        for e in self.R["asset_changes.csv"]["asset_event"]:
            if e["at"] <= self.F:
                evs.setdefault(e["asset"], []).append(e)
        snaps: dict[str, list] = {}
        for s in self.R["asset_snapshot_q1.xml"]["asset_snap"]:
            if s["as_of"] <= self.F.date():
                snaps.setdefault(s["asset"], []).append(s)
        tests: dict[str, list] = {}
        for p in self.R["perf_tests.xml"]["perf_point"]:
            if p["accepted"] and p["bep"]:
                tests.setdefault(p["asset"], []).append(p)
        hold = set(self.params.get("holdout_assets", "").split())
        out = {}
        for aid, lst in evs.items():
            lst = sorted(lst, key=lambda e: e["at"])
            starts = [e for e in lst if e["kind"] in ("baseline", "commission")]
            if not starts:
                continue
            first = latest(starts, key=lambda e: e["at"])
            a = {"asset_id": aid, "model": first["model"], "serial": first["serial"], "events": lst,
                 "tests": sorted(tests.get(aid, []), key=lambda p: p["tested_at"])}
            comm = [e for e in starts if e["kind"] == "commission"]
            if comm:
                a["commissioned_on"] = latest(comm, key=lambda e: e["at"])["at"].date()
            else:
                a["commissioned_on"] = latest(snaps[aid], key=lambda s: s["as_of"])["commissioned"]
            a["start_at"] = min(e["at"] for e in starts)
            a["oem"] = self.es.std.models[a["model"]]
            a["holdout"] = aid in hold
            out[aid] = a
        return out

    def state(self, aid: str, t: datetime) -> dict:
        a = self.assets[aid]
        st = {"site": a["events"][0]["site"], "setpoint": None, "crit": None, "active": False, "decom": None}
        for e in a["events"]:
            if e["at"] > t:
                break
            k = e["kind"]
            if k in ("baseline", "commission"):
                st.update(site=e["site"], setpoint=e["setpoint"], crit=e["criticality"], active=True, decom=None)
            elif k == "relocate":
                st["site"] = e["site"]
            elif k == "decommission":
                st["active"] = False
                st["decom"] = e["at"]
            elif k == "reinstate":
                st["active"] = True
                st["decom"] = None
            elif k == "setpoint" and e["setpoint"] is not None:
                st["setpoint"] = e["setpoint"]
            elif k == "criticality" and e["criticality"] is not None:
                st["crit"] = e["criticality"]
        return st

    def rated_at(self, aid: str, t: datetime):
        best = None
        for p in self.assets[aid]["tests"]:
            if p["tested_at"] <= t:
                best = p
        return best["flow"] if best else None

    def asset_rows(self) -> list[dict]:
        rows = []
        for aid in sorted(self.assets):
            a = self.assets[aid]
            st = self.state(aid, self.F)
            rated = self.rated_at(aid, self.F)
            rows.append({"asset_id": aid, "site": st["site"], "model": a["model"], "oem": a["oem"], "serial": a["serial"],
                         "commissioned_on": a["commissioned_on"].isoformat(),
                         "decommissioned_at": iso_z(st["decom"]) if st["decom"] else "",
                         "criticality": st["crit"] or "", "setpoint_bar": sfmt(st["setpoint"], 3) if st["setpoint"] is not None else "",
                         "rated_flow_m3h": sfmt(rated, 2) if rated is not None else "",
                         "holdout": "true" if a["holdout"] else "false"})
        return rows

    # telemetry
    def _intervals(self, sources: list, extra: list, extra_ok) -> dict:
        pool: dict = {}
        order = 0
        for f in sources:
            table = next(iter(self.R[f]))
            for r in self.R[f][table]:
                order += 1
                k = (r["asset"], r["at"])
                if k not in pool or (r["seq"], order) >= (pool[k]["seq"], pool[k]["_o"]):
                    pool[k] = dict(r, _o=order)
        for f in extra:
            table = next(iter(self.R[f]))
            for r in self.R[f][table]:
                order += 1
                if not extra_ok(r):
                    continue
                k = (r["asset"], r["at"])
                if k not in pool or (r["seq"], order) >= (pool[k]["seq"], pool[k]["_o"]):
                    pool[k] = dict(r, _o=order)
        return pool

    def telemetry(self) -> dict:
        F = self.F
        cm = self._intervals(CM_SOURCES, [], None)
        gap: dict = {}
        order = 0
        for r in self.R["scada_resend_queue.log"]["resend"]:
            order += 1
            k = (r["asset"], r["at"])
            if not r["gapfill"] or k in cm:
                continue
            if k not in gap or (r["seq"], order) >= (gap[k]["seq"], gap[k]["_o"]):
                gap[k] = dict(r, _o=order)
        cm.update(gap)
        hist = self._intervals(HIST_SOURCES, ["hist_backfill.json"], lambda r: r["received_at"] <= F)
        installs: dict = {}
        for m in self.R["sensor_moves.tsv"]["sensor_move"]:
            installs.setdefault((m["asset"], m["channel"]), []).append(m)
        for v in installs.values():
            v.sort(key=lambda m: m["at"])
        revoked = {}
        for rv in self.R["cert_revocations.html"]["cert_review"]:
            if rv["at"] <= F:
                if rv["cert_no"] not in revoked or rv["at"] >= revoked[rv["cert_no"]]["at"]:
                    revoked[rv["cert_no"]] = rv
        pend: dict = {}
        for p in self.R["calib_certs_pending.html"]["cert_pending"]:
            pend.setdefault(p["cert_no"], p)
        certs: dict[str, list] = {}
        for c in self.R["calib_certs.xml"]["cert"]:
            if c["recorded_at"] > F:
                continue
            rv = revoked.get(c["cert_no"])
            if rv and rv["outcome"] == "revoke":
                continue
            if c["status"] == "approved":
                certs.setdefault(c["serial"], []).append((c["effective_from"], c["rev"], c["gain"], c["offset"]))
            elif c["status"] == "see_pending":
                p = pend.get(c["cert_no"])
                if p and p["approved_at"] is not None and p["approved_at"] <= F:
                    certs.setdefault(c["serial"], []).append((p["effective_from"], c["rev"], p["gain"], p["offset"]))
        for v in certs.values():
            v.sort(key=lambda x: (x[0], x[1]))
        faults: dict = {}
        for w in self.R["ops_tickets.mbox"]["fault_window"]:
            if w["decision"] == "accepted" and w["decided_at"] <= F:
                faults.setdefault((w["asset"], w["channel"]), []).append((w["start"], w["end"]))
        envs: dict = {}
        for e in self.R["envelope_limits.json"]["envelope"]:
            if e["status"] == "active":
                envs.setdefault((e["asset"], e["channel"]), []).append(e)

        def serial_at(aid, ch, t):
            cur = None
            for m in installs.get((aid, ch), []):
                if m["at"] > t:
                    break
                if m["action"] == "install":
                    cur = m["serial"]
                elif m["serial"] == cur:
                    cur = None
            return cur

        def cert_at(serial, t):
            best = None
            for eff, rev, g, o in certs.get(serial, []):
                if eff <= t:
                    best = (g, o)
            return best

        def envelope_at(aid, ch, t):
            return latest([e for e in envs.get((aid, ch), []) if e["effective_from"] <= t], key=lambda e: e["effective_from"])

        daily: dict = {}
        for grp, pool, fmap in (("cm", cm, {"vib": "vib", "temp": "tmp"}), ("hist", hist, {"prs": "prs", "flw": "flw", "cur": "cur"})):
            for (aid, t), r in pool.items():
                if aid not in self.assets:
                    continue
                site = self.state(aid, t)["site"]
                d = local_date(self.tz[site], t)
                cell = daily.setdefault((aid, d), {"vals": {c: [] for c in CH_PLACES}, "readings": 0, "quarantined": 0})
                for ch, fld in fmap.items():
                    raw = r[fld]
                    if raw is None:
                        continue
                    c = cert_at(serial_at(aid, ch, t), t)
                    if c is None:
                        continue
                    val = dq(c[0] * raw + c[1], CH_PLACES[ch])
                    if any(s <= t < e for s, e in faults.get((aid, ch), [])):
                        continue
                    env = envelope_at(aid, ch, t)
                    if env is not None and (val < env["lo"] or val > env["hi"]):
                        cell["quarantined"] += 1
                        continue
                    cell["vals"][ch].append(val)
                    cell["readings"] += 1
        return daily

    def availability(self) -> dict:
        F = self.F
        emb: dict = {}
        for e in self.R["embargo_ledger.ini"]["embargo"]:
            if e["set_at"] > F:
                continue
            k = (e["asset"], e["month"])
            if k not in emb or e["rev"] >= emb[k]["rev"]:
                emb[k] = e
        outages: dict = {}
        for o in self.R["outage_ledger.sql"]["outage"]:
            if o["status"] == "logged":
                outages.setdefault(o["asset"], []).append((o["start"], o["end"]))
        sb: dict = {}
        for s in self.R["standby_windows.ics"]["standby"]:
            if s["rid"] not in sb or s["seq"] >= sb[s["rid"]]["seq"]:
                sb[s["rid"]] = s
        standby: dict = {}
        for s in sb.values():
            if s["status"] == "confirmed":
                standby.setdefault(s["asset"], []).append((s["start"], s["end"]))
        holds = {(h["asset"], h["day"]) for h in self.R["kp23_labels_export.jsonl"]["kp23_label"] if h["review_hold"]}
        return {"emb": emb, "out": outages, "sb": standby, "hold": holds}

    def alarm_counts(self) -> dict:
        F = self.F
        dict_rows: dict = {}
        for d in self.R[STANDARD_FILE]["alarm_code"]:
            dict_rows.setdefault((d["oem"], d["code"]), []).append(d)
        draft_rows: dict = {}
        for d in self.R["alarm_dict_oem_draft.tsv"]["alarm_code"]:
            draft_rows.setdefault((d["oem"], d["code"]), []).append(d)
        fw: dict = {}
        for x in self.R["fw_rollouts.md"]["firmware"]:
            if x["status"] in ("done", "rolledback"):
                fw.setdefault(x["asset"], []).append(x)
        for v in fw.values():
            v.sort(key=lambda x: x["at"])
        acked = set()
        alarms = {}
        for f in ALARM_SOURCES:
            for a in self.R[f]["alarm"]:
                alarms[a["rid"]] = a
        for k in self.R["alarm_acks.jsonl"]["alarm_ack"]:
            a = alarms.get(k["alarm_rid"])
            if a is None or k["kind"] == "real":
                continue
            if k["acked_at"] <= a["at"] + timedelta(minutes=15) and k["acked_at"] <= F:
                acked.add(a["rid"])
        shelved: dict = {}
        for sh in self.R["alarm_shelving.json"]["shelve"]:
            if sh["status"] == "active":
                shelved.setdefault((sh["asset"], sh["code"]), []).append((sh["start"], sh["end"]))
        counts: dict = {}
        for f in ALARM_SOURCES:
            for a in self.R[f]["alarm"]:
                aid = a["asset"]
                if aid not in self.assets or a["rid"] in acked:
                    continue
                if any(s0 <= a["at"] < s1 for s0, s1 in shelved.get((aid, a["code"]), [])):
                    continue
                ver = "1.0.0"
                for x in fw.get(aid, []):
                    if x["at"] <= a["at"]:
                        ver = x["version"]
                major = int(ver.split(".")[0])
                key = (self.assets[aid]["oem"], a["code"])
                rows = dict_rows.get(key) or draft_rows.get(key) or []
                ok = [r for r in rows if r["min_fw"] <= major]
                if not ok:
                    continue
                cls = max(ok, key=lambda r: r["min_fw"])["class"]
                if cls not in ("warning", "trip"):
                    continue
                site = self.state(aid, a["at"])["site"]
                d = local_date(self.tz[site], a["at"])
                counts[(aid, d)] = counts.get((aid, d), 0) + 1
        return counts

    def sensor_rows(self) -> list[dict]:
        daily = self.telemetry()
        av = self.availability()
        alarms = self.alarm_counts()
        w0, w1 = self.es.std.window
        rows = []
        for aid in sorted(self.assets):
            d = w0
            while d <= w1:
                noon = datetime.combine(d, datetime.min.time(), UTC) + timedelta(hours=12)
                st = self.state(aid, noon)
                if not st["active"]:
                    d += timedelta(days=1)
                    continue
                site = st["site"]
                a0, a1 = day_span(self.tz[site], d)
                if av["emb"].get((aid, date(d.year, d.month, 1)), {}).get("flag"):
                    avail = "embargo"
                elif overlap_seconds(av["out"].get(aid, []), a0, a1) >= 43200:
                    avail = "outage"
                elif overlap_seconds(av["sb"].get(aid, []), a0, a1) >= 43200:
                    avail = "standby"
                elif (aid, d) in av["hold"]:
                    avail = "hold"
                else:
                    avail = "ok"
                cell = daily.get((aid, d), {"vals": {c: [] for c in CH_PLACES}, "readings": 0, "quarantined": 0})
                v = cell["vals"]

                def m(ch):
                    return sfmt(mean_frac(v[ch]), CH_PLACES[ch]) if v[ch] else ""
                rated = self.rated_at(aid, noon)
                rows.append({"asset_id": aid, "day": d.isoformat(), "site": site, "availability": avail,
                             "vib_mean_mm_s": m("vib"), "vib_max_mm_s": sfmt(max(v["vib"]), 3) if v["vib"] else "",
                             "temp_c": m("temp"), "pressure_bar": m("prs"), "flow_m3h": m("flw"), "current_a": m("cur"),
                             "setpoint_bar": sfmt(st["setpoint"], 3) if st["setpoint"] is not None else "",
                             "rated_flow_m3h": sfmt(rated, 2) if rated is not None else "",
                             "alarms": str(alarms.get((aid, d), 0)), "readings": str(cell["readings"]),
                             "quarantined": str(cell["quarantined"])})
                d += timedelta(days=1)
        return rows

    def site_rows(self) -> list[dict]:
        F = self.F
        shifts: dict = {}
        for s in self.R["shift_roster_sites.html"]["shift"]:
            k = (s["site"], s["day"], s["shift"])
            if k not in shifts or s["rev"] >= shifts[k]["rev"]:
                shifts[k] = s
        qc: dict = {}
        for x in self.R["ambient_qc.log"]["ambient_qc"]:
            if x["at"] <= F and (x["obs_rid"] not in qc or x["at"] >= qc[x["obs_rid"]]["at"]):
                qc[x["obs_rid"]] = x
        prim: dict = {}
        seen: set = set()
        for o in self.R["ambient_obs.jsonl"]["ambient"]:
            d = local_date(self.tz[o["site"]], o["at"])
            k = (o["site"], d, o["kind"])
            seen.add(k)
            x = qc.get(o["rid"])
            temp = o["temp"]
            if x is not None and x["outcome"] == "reject":
                continue
            if x is not None and x["outcome"] == "retest" and x["temp"] is not None:
                temp = x["temp"]
            if k not in prim or o["at"] >= prim[k][0]:
                prim[k] = (o["at"], temp)
        mirror: dict = {}
        for o in self.R["ambient_obs_mirror.md"]["ambient"]:
            d = local_date(self.tz[o["site"]], o["at"])
            k = (o["site"], d, o["kind"])
            if k in seen:
                continue
            if k not in mirror or o["at"] >= mirror[k][0]:
                mirror[k] = (o["at"], o["temp"])
        w0, w1 = self.es.std.window
        rows = []
        for site in sorted(self.es.std.sites):
            d = w0
            while d <= w1:
                n = sum(1 for sh in VOCAB["shift_code"] if shifts.get((site, d, sh), {}).get("status") == "operating")
                mn = prim.get((site, d, "min")) or mirror.get((site, d, "min"))
                mx = prim.get((site, d, "max")) or mirror.get((site, d, "max"))
                amb = sfmt((Fraction(mn[1]) + Fraction(mx[1])) / 2, 2) if mn and mx else ""
                rows.append({"site": site, "day": d.isoformat(), "shifts_operating": str(n), "operating": "true" if n >= 2 else "false",
                             "ambient_c": amb})
                d += timedelta(days=1)
        return rows

    def failure_rows(self) -> list[dict]:
        F = self.F
        decs: dict[str, list] = {}
        for r in self.R["rca_reviews.yaml"]["rca"]:
            if r["decided_at"] <= F:
                decs.setdefault(r["notif_no"], []).append((r["decided_at"], 0, r["rev"], r["decision"], r["mode"]))
        amend: dict = {}
        for a in self.R["rca_amendments.ics"]["amendment"]:
            if a["rid"] not in amend or a["seq"] >= amend[a["rid"]]["seq"]:
                amend[a["rid"]] = a
        pending: dict = {}
        for a in amend.values():
            if a["status"] != "confirmed":
                continue
            if a["amended_at"] <= F:
                decs.setdefault(a["notif_no"], []).append((a["amended_at"], 1, a["seq"], a["decision"], a["mode"]))
            elif a["notif_no"] not in pending or a["amended_at"] >= pending[a["notif_no"]]["amended_at"]:
                pending[a["notif_no"]] = a
        rows = []
        for f in ("notif_cmms.tsv", "notif_field.md"):
            for n in self.R[f]["notification"]:
                if n["kind"] != "failure" or n["asset"] not in self.assets:
                    continue
                cand = decs.get(n["notif_no"], [])
                best = None
                for c in cand:
                    if best is None or c[:3] >= best[:3]:
                        best = c
                status = "confirmed" if best and best[3] in ("confirm", "reclassify") else "unconfirmed"
                mode = best[4] if best and best[3] == "reclassify" and best[4] else n["mode"]
                p = pending.get(n["notif_no"])
                site = self.state(n["asset"], n["failed_at"])["site"]
                rows.append({"event_id": n["notif_no"], "asset_id": n["asset"], "failed_at": iso_z(n["failed_at"]),
                             "failed_day": local_date(self.tz[site], n["failed_at"]).isoformat(), "status": status,
                             "mode": mode or "", "decided_at": iso_z(best[0]) if best else "",
                             "pending_decision": p["decision"] if p else "",
                             "pending_mode": (p["mode"] or "") if p and p["decision"] == "reclassify" else "",
                             "pending_at": iso_z(p["amended_at"]) if p else ""})
        rows.sort(key=lambda r: r["event_id"])
        return rows

    def maintenance_rows(self) -> list[dict]:
        F = self.F
        wos = {}
        for f in ("wo_cmms_archive.jsonl", "wo_cmms_current.sql"):
            for w in self.R[f]["work_order"]:
                wos[w["wo_no"]] = dict(w)
        revs: dict = {}
        for r in self.R["wo_revisions.csv"]["wo_rev"]:
            if r["revised_at"] > F:
                continue
            k = r["wo_no"]
            if k not in revs or (r["rev"], r["revised_at"]) >= (revs[k]["rev"], revs[k]["revised_at"]):
                revs[k] = r
        legacy: dict = {}
        for w in self.R["wo_legacy_mirror.sql"]["work_order"]:
            legacy.setdefault(w["wo_no"], w)
        labour: dict = {}
        for b in self.R["labour_bookings.toml"]["labour"]:
            labour[b["wo_no"]] = max(labour.get(b["wo_no"], b["end"]), b["end"])
        m = re.search(r"`wo_legacy_mirror\.sql`: the closed_at of a work order opened before (\d{4}-\d{2}-\d{2})", self.es.std.text)
        if m is None:
            raise InputError("standard does not state the legacy mirror cutover")
        cutover = datetime.combine(date.fromisoformat(m.group(1)), datetime.min.time(), UTC)
        rows = []
        for no, w in wos.items():
            if w["asset"] not in self.assets:
                continue
            status, closed = w["status"], w["closed_at"]
            if no in revs:
                status, closed = revs[no]["status"], revs[no]["closed_at"]
            if closed is None and w["opened_at"] < cutover and no in legacy:
                closed = legacy[no]["closed_at"]
            if status != "completed":
                continue
            at = labour.get(no, closed)
            if at is None or at > F:
                continue
            rows.append((w["asset"], at, w["kind"], "", no))
        qc: dict = {}
        for x in self.R["oil_retests.tsv"]["oil_qc"]:
            if x["at"] <= F and (x["sample_no"] not in qc or x["at"] >= qc[x["sample_no"]]["at"]):
                qc[x["sample_no"]] = x
        for o in self.R["oil_lab.csv"]["oil"]:
            if o["status"] != "valid" or o["sampled_at"] > F or o["asset"] not in self.assets:
                continue
            x = qc.get(o["sample_no"])
            iron = o["iron"]
            if x is not None and x["outcome"] == "reject":
                continue
            if x is not None and x["outcome"] == "retest" and x["iron"] is not None:
                iron = x["iron"]
            rows.append((o["asset"], o["sampled_at"], "oil", str(int(iron)), o["sample_no"]))
        out = []
        for aid, at, kind, val, ref in sorted(rows, key=lambda r: (r[0], r[1], r[4])):
            site = self.state(aid, at)["site"]
            out.append({"asset_id": aid, "event_at": iso_z(at), "event_day": local_date(self.tz[site], at).isoformat(),
                        "kind": kind, "value": val, "ref": ref})
        return out


P1_COLUMNS = {
    "asset_registry.csv": ["asset_id", "site", "model", "oem", "serial", "commissioned_on", "decommissioned_at", "criticality",
                           "setpoint_bar", "rated_flow_m3h", "holdout"],
    "sensor_daily.csv": ["asset_id", "day", "site", "availability", "vib_mean_mm_s", "vib_max_mm_s", "temp_c", "pressure_bar",
                         "flow_m3h", "current_a", "setpoint_bar", "rated_flow_m3h", "alarms", "readings", "quarantined"],
    "failure_events.csv": ["event_id", "asset_id", "failed_at", "failed_day", "status", "mode", "decided_at", "pending_decision",
                           "pending_mode", "pending_at"],
    "maintenance_log.csv": ["asset_id", "event_at", "event_day", "kind", "value", "ref"],
    "site_days.csv": ["site", "day", "shifts_operating", "operating", "ambient_c"],
}
P1_FILES = sorted(list(P1_COLUMNS) + ["run_parameters.json"])


def write_csv(path: Path, cols: list, rows: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow([r[c] for c in cols])
    path.write_bytes(buf.getvalue().encode("utf-8"))


def dump_json(obj) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def phase1(data_dir: Path) -> dict[str, bytes]:
    es = Estate(data_dir)
    p = Phase1(es)
    out = {}
    tables = {"asset_registry.csv": p.asset_rows(), "sensor_daily.csv": p.sensor_rows(), "failure_events.csv": p.failure_rows(),
              "maintenance_log.csv": p.maintenance_rows(), "site_days.csv": p.site_rows()}
    for name, rows in tables.items():
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(P1_COLUMNS[name])
        for r in rows:
            w.writerow([r[c] for c in P1_COLUMNS[name]])
        out[name] = buf.getvalue().encode("utf-8")
    params = dict(p.params)
    hold = sorted(params.pop("holdout_assets", "").split())
    out["run_parameters.json"] = dump_json({"run_id": "KP-24", "freeze": iso_z(es.freeze),
                                            "telemetry_window": [es.std.window[0].isoformat(), es.std.window[1].isoformat()],
                                            "parameters": params, "holdout_assets": hold,
                                            "regions": {c: v["region"] for c, v in sorted(es.std.sites.items())},
                                            "sources": es.attestation()})
    return out


# ---------------------------------------------------------------- lineage shared by phases 2 and 3
FEATURES = ["vib_mean_7d", "vib_max_7d", "temp_rise_7d", "pressure_dev_3d", "flow_ratio_7d", "current_7d",
            "days_since_service", "age_days", "iron_ppm", "alarms_7d"]
INT_FEATURES = {"days_since_service", "age_days", "iron_ppm", "alarms_7d"}
P2_FILES = ["bin_edges.json", "class_balance.json", "feature_matrix.json", "label_table.json", "quarantine_summary.json",
            "scaler_stats.json"]
P3_FILES = ["amendment_impact.json", "drift_report.json", "baseline_metrics.json", "release_manifest.json",
            "site_allocation.json", "train_ready.json"]
REASONS = ["non_operating", "embargo", "outage", "standby", "hold", "low_coverage", "blackout", "maintenance", "purge"]


def upstream_digest(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(f"{name}\n{hashlib.sha256(files[name]).hexdigest()}\n".encode())
    return h.hexdigest()


def read_upstream(d: Path, names: list[str], prefix: str) -> dict[str, bytes]:
    if not d.is_dir():
        raise InputError(f"upstream directory {d} does not exist")
    out = {}
    for n in names:
        p = d / n
        try:
            out[f"{prefix}/{n}"] = p.read_bytes()
        except OSError as exc:
            raise InputError(f"cannot read upstream file {n}: {exc}") from exc
    return out


def csv_rows(b: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(b.decode("utf-8"))))


def total_of(vals) -> str:
    s = sum((Decimal(v) for v in vals if v not in ("", None)), Decimal(0))
    return format(s, "f")


def controls(files: dict[str, bytes]) -> dict:
    """Per upstream file: row count, the documented column total and the last key."""
    out = {}
    for name, b in sorted(files.items()):
        base = name.split("/", 1)[1]
        if base.endswith(".csv"):
            rows = csv_rows(b)
            col, key = {"asset_registry.csv": ("rated_flow_m3h", ["asset_id"]), "sensor_daily.csv": ("readings", ["asset_id", "day"]),
                        "failure_events.csv": (None, ["event_id"]), "maintenance_log.csv": ("value", ["ref"]),
                        "site_days.csv": ("shifts_operating", ["site", "day"])}[base]
            tot = str(sum(1 for r in rows if r["status"] == "confirmed")) if col is None else total_of(r[col] for r in rows)
            out[name] = {"rows": len(rows), "total": tot, "last_key": "|".join(rows[-1][k] for k in key) if rows else ""}
            continue
        doc = json.loads(b)
        if base == "run_parameters.json":
            src = doc["sources"]
            out[name] = {"rows": len(src), "total": str(sum(s["records"] for s in src)), "last_key": src[-1]["file"] if src else ""}
        elif base == "label_table.json":
            rows = doc["rows"]
            out[name] = {"rows": len(rows), "total": str(sum(r["label"] for r in rows)),
                         "last_key": f"{rows[-1]['asset_id']}|{rows[-1]['day']}" if rows else ""}
        elif base == "feature_matrix.json":
            rows = doc["rows"]
            out[name] = {"rows": len(rows), "total": str(sum(r["alarms_7d"] for r in rows)),
                         "last_key": f"{rows[-1]['asset_id']}|{rows[-1]['day']}" if rows else ""}
        elif base == "scaler_stats.json":
            f = doc["features"]
            out[name] = {"rows": len(f), "total": str(sum(v["n"] for v in f.values())), "last_key": sorted(f)[-1] if f else ""}
        elif base == "class_balance.json":
            s = doc["splits"]
            out[name] = {"rows": len(s), "total": str(sum(v["rows"] for v in s.values())), "last_key": sorted(s)[-1] if s else ""}
        elif base == "quarantine_summary.json":
            s = doc["sites"]
            out[name] = {"rows": len(s), "total": str(sum(v["samples_kept"] for v in s.values())), "last_key": sorted(s)[-1] if s else ""}
        elif base == "bin_edges.json":
            f = doc["features"]
            out[name] = {"rows": len(f), "total": str(sum(len(v) for v in f.values())), "last_key": sorted(f)[-1] if f else ""}
    return out


def fnum(s):
    return None if s in ("", None) else Fraction(Decimal(s))


# ---------------------------------------------------------------- phase 2
class Upstream1:
    def __init__(self, files: dict[str, bytes]):
        g = lambda n: files["p1/" + n]
        self.assets = {r["asset_id"]: r for r in csv_rows(g("asset_registry.csv"))}
        self.daily = csv_rows(g("sensor_daily.csv"))
        self.failures = csv_rows(g("failure_events.csv"))
        self.maint = csv_rows(g("maintenance_log.csv"))
        self.sites = {(r["site"], r["day"]): r for r in csv_rows(g("site_days.csv"))}
        self.run = json.loads(g("run_parameters.json"))
        P = self.run["parameters"]
        self.P = P
        self.d = lambda k: date.fromisoformat(P[k])
        self.i = lambda k: int(P[k])
        self.by_asset: dict[str, dict] = {}
        for r in self.daily:
            self.by_asset.setdefault(r["asset_id"], {})[r["day"]] = r


def samples(u: Upstream1):
    """Kept samples with label and split, and exclusion counts per site."""
    s0, s1 = u.d("sample_start"), u.d("sample_end")
    te, ve = u.d("train_end"), u.d("val_end")
    H, B, minr = u.i("horizon_days"), u.i("blackout_days"), u.i("min_readings")
    conf: dict[str, list] = {}
    for f in u.failures:
        if f["status"] == "confirmed":
            conf.setdefault(f["asset_id"], []).append(date.fromisoformat(f["failed_day"]))
    heavy: dict[str, list] = {}
    for m in u.maint:
        if m["kind"] in ("overhaul", "impeller"):
            heavy.setdefault(m["asset_id"], []).append(date.fromisoformat(m["event_day"]))
    kept, excl = [], {}
    for r in u.daily:
        d = date.fromisoformat(r["day"])
        if d < s0 or d > s1:
            continue
        aid = r["asset_id"]
        hold = u.assets[aid]["holdout"] == "true"
        sd = u.sites.get((r["site"], r["day"]))
        if sd is None or sd["operating"] != "true":
            reason = "non_operating"
        elif r["availability"] != "ok":
            reason = r["availability"]
        elif int(r["readings"]) < minr:
            reason = "low_coverage"
        elif any(F <= d < F + timedelta(days=B) for F in conf.get(aid, [])):
            reason = "blackout"
        elif any(S <= d <= S + timedelta(days=1) for S in heavy.get(aid, [])):
            reason = "maintenance"
        elif not hold and te - timedelta(days=H) < d <= te:
            reason = "purge"
        else:
            reason = None
        if reason:
            excl.setdefault(r["site"], {}).setdefault(reason, 0)
            excl[r["site"]][reason] += 1
            continue
        split = "test" if hold else ("train" if d <= te else ("val" if d <= ve else "test"))
        label = 1 if any(d < F <= d + timedelta(days=H) for F in conf.get(aid, [])) else 0
        kept.append({"asset_id": aid, "day": r["day"], "site": r["site"], "split": split, "label": label})
    return kept, excl


def features(u: Upstream1, kept: list) -> list[dict]:
    lookback = u.i("iron_lookback_days")
    serv: dict[str, list] = {}
    oil: dict[str, list] = {}
    for m in u.maint:
        if m["kind"] in SERVICE_KINDS:
            serv.setdefault(m["asset_id"], []).append(date.fromisoformat(m["event_day"]))
        elif m["kind"] == "oil":
            oil.setdefault(m["asset_id"], []).append((date.fromisoformat(m["event_day"]), m["event_at"], int(m["value"])))
    out = []
    for k in kept:
        aid, d = k["asset_id"], date.fromisoformat(k["day"])
        rows = u.by_asset[aid]
        win = [rows.get((d - timedelta(days=i)).isoformat()) for i in range(7)]
        win = [w for w in win if w is not None]
        win3 = [rows.get((d - timedelta(days=i)).isoformat()) for i in range(3)]
        win3 = [w for w in win3 if w is not None]

        def mean_of(vals, need, dp=4):
            vals = [v for v in vals if v is not None]
            return sfmt(sum(vals, Fraction(0)) / len(vals), dp) if len(vals) >= need else None
        vib = mean_of([fnum(w["vib_mean_mm_s"]) for w in win], 4)
        vmx = [fnum(w["vib_max_mm_s"]) for w in win if w["vib_max_mm_s"] != ""]
        rise = []
        for w in win:
            amb = u.sites.get((w["site"], w["day"]), {}).get("ambient_c", "")
            if w["temp_c"] != "" and amb != "":
                rise.append(fnum(w["temp_c"]) - fnum(amb))
        pdev = [fnum(w["pressure_bar"]) - fnum(w["setpoint_bar"]) for w in win3 if w["pressure_bar"] != "" and w["setpoint_bar"] != ""]
        ratio = [fnum(w["flow_m3h"]) / fnum(w["rated_flow_m3h"]) for w in win
                 if w["flow_m3h"] != "" and w["rated_flow_m3h"] != "" and fnum(w["rated_flow_m3h"]) > 0]
        last_s = [s for s in serv.get(aid, []) if s <= d]
        oils = [o for o in oil.get(aid, []) if o[0] <= d and (d - o[0]).days < lookback]
        comm = date.fromisoformat(u.assets[aid]["commissioned_on"])
        out.append({"asset_id": aid, "day": k["day"],
                    "vib_mean_7d": vib, "vib_max_7d": sfmt(max(vmx), 4) if len(vmx) >= 4 else None,
                    "temp_rise_7d": mean_of(rise, 4), "pressure_dev_3d": mean_of(pdev, 2),
                    "flow_ratio_7d": mean_of(ratio, 4), "current_7d": mean_of([fnum(w["current_a"]) for w in win], 4),
                    "days_since_service": (d - max(last_s)).days if last_s else None, "age_days": (d - comm).days,
                    "iron_ppm": max(oils, key=lambda o: (o[0], o[1]))[2] if oils else None,
                    "alarms_7d": sum(int(w["alarms"]) for w in win)})
    return out


def as_frac(v):
    return None if v is None else Fraction(Decimal(str(v)))


def phase2(p1: dict[str, bytes]) -> dict[str, bytes]:
    u = Upstream1(p1)
    kept, excl = samples(u)
    feats = features(u, kept)
    split_of = {(k["asset_id"], k["day"]): k for k in kept}
    train = [f for f in feats if split_of[(f["asset_id"], f["day"])]["split"] == "train"]
    stats, edges = {}, {}
    for fe in FEATURES:
        xs = [as_frac(f[fe]) for f in train if f[fe] is not None]
        n = len(xs)
        if n >= 2:
            m = sum(xs, Fraction(0)) / n
            var = sum(((x - m) ** 2 for x in xs), Fraction(0)) / (n - 1)
            with localcontext() as c:
                c.prec = 50
                sd = (Decimal(var.numerator) / Decimal(var.denominator)).sqrt()
            stats[fe] = {"n": n, "mean": sfmt(m, 6), "std": sfmt(sd, 6)}
        else:
            stats[fe] = {"n": n, "mean": None, "std": None}
        srt = sorted(xs)
        edges[fe] = [(str(int(srt[math.ceil(k * n / 10) - 1])) if fe in INT_FEATURES else sfmt(srt[math.ceil(k * n / 10) - 1], 4))
                     for k in range(1, 10)] if n >= 10 else []
    splits = {}
    for sp in ("train", "val", "test"):
        rows = [k for k in kept if k["split"] == sp]
        pos = sum(k["label"] for k in rows)
        splits[sp] = {"rows": len(rows), "positives": pos, "negatives": len(rows) - pos,
                      "prevalence": sfmt(Fraction(pos, len(rows)), 6) if rows else None}
    tr = splits["train"]
    weights = {"positive": sfmt(Fraction(tr["rows"], 2 * tr["positives"]), 6) if tr["positives"] else None,
               "negative": sfmt(Fraction(tr["rows"], 2 * tr["negatives"]), 6) if tr["negatives"] else None}
    sites = {}
    q_by_site: dict[str, int] = {}
    for r in u.daily:
        q_by_site[r["site"]] = q_by_site.get(r["site"], 0) + int(r["quarantined"])
    for site in sorted({r["site"] for r in u.daily}):
        sites[site] = {"readings_quarantined": q_by_site.get(site, 0),
                       "samples_kept": sum(1 for k in kept if k["site"] == site),
                       "excluded": {reason: excl.get(site, {}).get(reason, 0) for reason in REASONS}}
    dig = upstream_digest(p1)
    ctl = controls(p1)
    lineage = {"upstream_digest": dig, "upstream_controls": ctl}
    docs = {
        "label_table.json": {"rows": [{"asset_id": k["asset_id"], "day": k["day"], "split": k["split"], "label": k["label"]} for k in kept]},
        "feature_matrix.json": {"features": FEATURES, "rows": feats},
        "scaler_stats.json": {"fit_split": "train", "features": stats},
        "class_balance.json": {"splits": splits, "class_weights": weights},
        "quarantine_summary.json": {"sites": sites},
        "bin_edges.json": {"features": edges},
    }
    return {n: dump_json({**d, **lineage}) for n, d in docs.items()}


# ---------------------------------------------------------------- phase 3
def dec_exp(x: Decimal) -> Decimal:
    with localcontext() as c:
        c.prec = 50
        return x.exp()


def ln_half() -> Decimal:
    with localcontext() as c:
        c.prec = 50
        return Decimal("0.5").ln()


def auc(rows: list) -> Fraction | None:
    pos = sum(1 for s, y in rows if y == 1)
    neg = len(rows) - pos
    if not pos or not neg:
        return None
    srt = sorted(rows, key=lambda x: x[0])
    ranks = {}
    i = 0
    while i < len(srt):
        j = i
        while j + 1 < len(srt) and srt[j + 1][0] == srt[i][0]:
            j += 1
        ranks[srt[i][0]] = Fraction(i + 1 + j + 1, 2)
        i = j + 1
    rsum = sum((ranks[s] for s, y in rows if y == 1), Fraction(0))
    return (rsum - Fraction(pos * (pos + 1), 2)) / (pos * neg)


def f1_of(tp, fp, fn) -> Fraction:
    return Fraction(2 * tp, 2 * tp + fp + fn) if tp else Fraction(0)


def phase3(p1: dict[str, bytes], p2: dict[str, bytes]) -> dict[str, bytes]:
    u = Upstream1(p1)
    g = lambda n: json.loads(p2["p2/" + n])
    labels = g("label_table.json")["rows"]
    fm = {(r["asset_id"], r["day"]): r for r in g("feature_matrix.json")["rows"]}
    stats = g("scaler_stats.json")["features"]
    cb = g("class_balance.json")
    edges = g("bin_edges.json")["features"]
    qs = g("quarantine_summary.json")["sites"]
    P = u.P
    te = u.d("train_end")
    hl = Decimal(P["decay_half_life_days"])
    cap = Decimal(P["asset_weight_cap"])
    mult = {c: Decimal(P[f"crit_multiplier_{c}"]) for c in ("a", "b", "c")}
    cw = {1: Decimal(cb["class_weights"]["positive"]), 0: Decimal(cb["class_weights"]["negative"])}
    # standardised rows and sample weights
    ready = []
    used: dict[str, Decimal] = {}
    for lab in labels:
        f = fm[(lab["asset_id"], lab["day"])]
        z = {}
        for fe in FEATURES:
            x, st = f[fe], stats[fe]
            if x is None or st["std"] in (None, "0.000000"):
                z[fe] = None
            else:
                z[fe] = sfmt((Fraction(Decimal(str(x))) - Fraction(Decimal(st["mean"]))) / Fraction(Decimal(st["std"])), 4)
        if lab["split"] == "train":
            days = (te - date.fromisoformat(lab["day"])).days
            rec = dq(dec_exp(ln_half() * Decimal(days) / hl), 6)
            w = dq(cw[lab["label"]] * rec * mult[u.assets[lab["asset_id"]]["criticality"]], 6)
            room = cap - used.get(lab["asset_id"], Decimal(0))
            w = max(min(w, room), Decimal(0))
            used[lab["asset_id"]] = used.get(lab["asset_id"], Decimal(0)) + w
            wtxt = format(dq(w, 6), "f")
        else:
            wtxt = "1.000000"
        ready.append({"asset_id": lab["asset_id"], "day": lab["day"], "split": lab["split"], "label": lab["label"], "z": z,
                      "sample_weight": wtxt})
    # baseline scoring rule
    bias = Decimal(P["score_bias"])
    sw = {fe: Decimal(P[f"score_weight_{fe}"]) for fe in FEATURES}

    def score(r):
        return dq(bias + sum((sw[fe] * Decimal(r["z"][fe]) for fe in FEATURES if r["z"][fe] is not None), Decimal(0)), 6)
    scored = {sp: [(score(r), r["label"]) for r in ready if r["split"] == sp] for sp in ("val", "test")}
    best_thr, best_f1 = None, None
    for thr in sorted({s for s, _ in scored["val"]}, reverse=True):
        tp = sum(1 for s, y in scored["val"] if s >= thr and y == 1)
        fp = sum(1 for s, y in scored["val"] if s >= thr and y == 0)
        fn = sum(1 for s, y in scored["val"] if s < thr and y == 1)
        f1 = f1_of(tp, fp, fn)
        if best_f1 is None or f1 > best_f1:
            best_thr, best_f1 = thr, f1
    tv = scored["test"]
    tp = sum(1 for s, y in tv if best_thr is not None and s >= best_thr and y == 1)
    fp = sum(1 for s, y in tv if best_thr is not None and s >= best_thr and y == 0)
    fn = sum(1 for s, y in tv if y == 1) - tp
    tn = len(tv) - tp - fp - fn
    av, at = auc(scored["val"]), auc(scored["test"])
    evalb = {"val": {"rows": len(scored["val"]), "positives": sum(y for _, y in scored["val"]),
                     "auc": sfmt(av, 6) if av is not None else None, "threshold": format(best_thr, "f") if best_thr is not None else None,
                     "f1": sfmt(best_f1, 6) if best_f1 is not None else None},
             "test": {"rows": len(tv), "positives": sum(y for _, y in tv), "auc": sfmt(at, 6) if at is not None else None,
                      "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                      "precision": sfmt(Fraction(tp, tp + fp), 6) if tp + fp else "0.000000",
                      "recall": sfmt(Fraction(tp, tp + fn), 6) if tp + fn else "0.000000", "f1": sfmt(f1_of(tp, fp, fn), 6)}}
    # drift between train and test
    drift = {}
    split_of = {(r["asset_id"], r["day"]): r["split"] for r in labels}
    for fe in FEATURES:
        e = [Fraction(Decimal(x)) for x in edges[fe]]
        dist = {}
        nulls = {}
        for sp in ("train", "test"):
            vals = [fm[k][fe] for k, s in split_of.items() if s == sp]
            nn = [Fraction(Decimal(str(v))) for v in vals if v is not None]
            nulls[sp] = sfmt(Fraction(len(vals) - len(nn), len(vals)), 6) if vals else None
            cnt = [0] * (len(e) + 1)
            for v in nn:
                cnt[sum(1 for x in e if v > x)] += 1
            dist[sp] = [Fraction(c, len(nn)) if c else Fraction(1, 10000) for c in cnt] if nn else None
        if dist["train"] and dist["test"] and e:
            with localcontext() as c:
                c.prec = 50
                psi = sum(((Decimal(pt.numerator) / Decimal(pt.denominator) - Decimal(pr.numerator) / Decimal(pr.denominator))
                           * (Decimal(pt.numerator) / Decimal(pt.denominator) / (Decimal(pr.numerator) / Decimal(pr.denominator))).ln()
                           for pr, pt in zip(dist["train"], dist["test"])), Decimal(0))
            drift[fe] = {"psi": sfmt(psi, 6), "null_share_train": nulls["train"], "null_share_test": nulls["test"]}
        else:
            drift[fe] = {"psi": None, "null_share_train": nulls["train"], "null_share_test": nulls["test"]}
    # review budget allocation with site and region caps
    budget = int(P["review_budget"])
    site_cap = int(Decimal(P["site_cap_share"]) * budget)
    region_cap = int(Decimal(P["region_cap_share"]) * budget)
    site_of = {(r["asset_id"], r["day"]): r["site"] for r in u.daily}
    pos: dict[str, int] = {}
    for r in labels:
        if r["split"] == "train" and r["label"] == 1:
            s = site_of[(r["asset_id"], r["day"])]
            pos[s] = pos.get(s, 0) + 1
    regions = json.loads(p1["p1/run_parameters.json"]).get("regions", {})
    tot = sum(pos.values())
    alloc, quota = {}, {}
    for s in sorted(qs):
        quota[s] = Fraction(budget * pos.get(s, 0), tot) if tot else Fraction(0)
    reg_used: dict[str, int] = {}
    order = sorted(qs, key=lambda s: (-quota[s], s))
    for s in order:
        rg = regions.get(s, s)
        give = min(int(quota[s]), site_cap, region_cap - reg_used.get(rg, 0))
        alloc[s] = max(give, 0)
        reg_used[rg] = reg_used.get(rg, 0) + alloc[s]
    left = budget - sum(alloc.values())
    rem_order = sorted(qs, key=lambda s: (-(quota[s] - int(quota[s])), s))
    progress = True
    while left > 0 and progress:
        progress = False
        for s in rem_order:
            if left == 0:
                break
            rg = regions.get(s, s)
            if pos.get(s, 0) and alloc[s] < site_cap and reg_used.get(rg, 0) < region_cap:
                alloc[s] += 1
                reg_used[rg] = reg_used.get(rg, 0) + 1
                left -= 1
                progress = True
    allocation = {"budget": budget, "site_cap": site_cap, "region_cap": region_cap, "unallocated": left,
                  "sites": {s: {"region": regions.get(s, ""), "train_positives": pos.get(s, 0), "quota": sfmt(quota[s], 4),
                                "allocated": alloc[s], "capped": alloc[s] < int(quota[s])} for s in sorted(qs)}}
    # deferred amendments applied
    H = u.i("horizon_days")
    now_conf: dict[str, list] = {}
    then_conf: dict[str, list] = {}
    amended = 0
    for f in u.failures:
        day = date.fromisoformat(f["failed_day"])
        if f["status"] == "confirmed":
            now_conf.setdefault(f["asset_id"], []).append(day)
        st = f["status"]
        if f["pending_decision"]:
            amended += 1
            st = "confirmed" if f["pending_decision"] in ("confirm", "reclassify") else "unconfirmed"
        if st == "confirmed":
            then_conf.setdefault(f["asset_id"], []).append(day)
    changes = []
    counts = {sp: {"flipped_up": 0, "flipped_down": 0} for sp in ("train", "val", "test")}
    for r in labels:
        d = date.fromisoformat(r["day"])
        new = 1 if any(d < F <= d + timedelta(days=H) for F in then_conf.get(r["asset_id"], [])) else 0
        if new != r["label"]:
            changes.append({"asset_id": r["asset_id"], "day": r["day"], "split": r["split"], "old_label": r["label"], "new_label": new})
            counts[r["split"]]["flipped_up" if new else "flipped_down"] += 1
    impact = {"events_with_pending_amendment": amended, "label_changes": changes, "by_split": counts}
    up = {**p1, **p2}
    lineage = {"upstream_digest": upstream_digest(up), "upstream_controls": controls(up)}
    manifest = {"run_id": u.run["run_id"], "files": {n: hashlib.sha256(b).hexdigest() for n, b in sorted(up.items())},
                "rows": {"train": cb["splits"]["train"]["rows"], "val": cb["splits"]["val"]["rows"], "test": cb["splits"]["test"]["rows"]},
                "features": FEATURES}
    docs = {"train_ready.json": {"features": FEATURES, "rows": ready}, "baseline_metrics.json": evalb,
            "drift_report.json": {"features": drift}, "site_allocation.json": allocation, "amendment_impact.json": impact,
            "release_manifest.json": manifest}
    return {n: dump_json({**d, **lineage}) for n, d in docs.items()}


# ---------------------------------------------------------------- command line
def write_outputs(out_dir: Path, files: dict[str, bytes]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, b in files.items():
        (out_dir / name.split("/")[-1]).write_bytes(b)


def main(argv: list[str]) -> int:
    try:
        if not argv:
            raise UsageError("missing stage; use phase1, phase2 or phase3")
        stage, args = argv[0], argv[1:]
        want = {"phase1": 2, "phase2": 2, "phase3": 3}
        if stage not in want:
            raise UsageError(f"unknown stage {stage}")
        if len(args) != want[stage]:
            raise UsageError(f"{stage} takes {want[stage]} directory arguments")
        if stage == "phase1":
            files = phase1(Path(args[0]))
            write_outputs(Path(args[1]), files)
        elif stage == "phase2":
            p1 = read_upstream(Path(args[0]), P1_FILES, "p1")
            write_outputs(Path(args[1]), phase2(p1))
        else:
            p1 = read_upstream(Path(args[0]), P1_FILES, "p1")
            p2 = read_upstream(Path(args[1]), P2_FILES, "p2")
            write_outputs(Path(args[2]), phase3(p1, p2))
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
