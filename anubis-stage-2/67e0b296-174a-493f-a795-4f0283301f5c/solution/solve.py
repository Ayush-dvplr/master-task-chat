#!/usr/bin/env python3
"""Rack power-cap compiler: three stages over the fleet sources.

    build.py phase1 DATA_DIR P1_DIR
    build.py phase2 P1_DIR P2_DIR
    build.py phase3 P1_DIR P2_DIR P3_DIR
"""

from __future__ import annotations

import configparser
import csv
import email.utils
import hashlib
import html
import json
import mailbox
import re
import sqlite3
import sys
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal, getcontext
from pathlib import Path

import openpyxl
import pyarrow.parquet as pq
import yaml
from pypdf import PdfReader

getcontext().prec = 60
UTC = timezone.utc
PROG = "build.py"
EXIT_USAGE, EXIT_UPSTREAM = 2, 3

STANDARD_FILE = "power_standard.md"
NOT_IN_FORCE_WORDS = ("reexport", "replay", "backfill", "legacy", "prev", "draft", "rescan", "prelim")
FREEZE = datetime(1970, 1, 1, tzinfo=UTC)
WINDOW = FREEZE
FREEZE_RE = re.compile(r"as-of freeze is (\S+?Z) and the telemetry window runs from (\S+?Z)")
# Site clocks are read out of the standard's Times section at run time, never held for a fleet.
CLOCK: dict[str, tuple | None] = {}
STD_OFFSET: dict[str, int] = {}
SITE_CLOCKS_RE = re.compile(r"Site clocks:(.*)")
SITE_STD_RE = re.compile(r"\b([a-z][a-z0-9]{1,15}) is UTC([+-]\d{1,2})(?::(\d{2}))?")
UTC_OFFSET_RE = re.compile(r"UTC([+-]\d{1,2})(?::(\d{2}))?")
SHIFT_RE = re.compile(r"(\w+) hours? ahead")
EDGE_RE = re.compile(r"(first|second|third|fourth|fifth|last) (\w+day) of (\w+) (\d{1,2}):(\d{2}) (UTC|local time)")
ORDINAL_NUMBER = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "last": -1}
WORD_NUMBER = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
WEEKDAY_NUMBER = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5,
                  "sunday": 6}
MONTH_NUMBER = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
                "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
SOURCE_RANK = {"pdu": 0, "bmc": 1, "agent": 2}
PRIORITY_ORDER = {"gold": 0, "silver": 1, "bronze": 2}
UNIT_FACTOR = {"w": Decimal(1000), "watt": Decimal(1000), "kw": Decimal(1000000), "mw": Decimal(1),
               "va": Decimal(1000), "kva": Decimal(1000000), "btu/h": Decimal("293.071"),
               "btu/hr": Decimal("293.071")}
MISSING = {"", "-", "n/a", "null", "nan"}
LOCAL_RE = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d")
VALUE_UNIT_RE = re.compile(r"(.*\S)\s+([A-Za-z/]+)")


class UsageError(Exception):
    pass


class UpstreamError(Exception):
    pass


# ------------------------------------------------------------------ numbers and rounding
def half_even(x: Decimal) -> int:
    return int(x.to_integral_value(rounding=ROUND_HALF_EVEN))


def floor_int(x: Decimal) -> int:
    return int(x.to_integral_value(rounding=ROUND_FLOOR))


def fixed(v: int, places: int) -> str:
    sign = "-" if v < 0 else ""
    q, r = divmod(abs(v), 10 ** places)
    return f"{sign}{q}.{r:0{places}d}" if places else f"{sign}{q}"


def parse_number(text: str) -> Decimal:
    s = text.strip().replace("\u202f", "").replace(" ", "").replace("'", "")
    mant, exp = s, ""
    m = re.fullmatch(r"([-+]?[0-9.,]+)[eE]([-+]?\d+)", s)
    if m:
        mant, exp = m.group(1), m.group(2)
    dots, commas = mant.count("."), mant.count(",")
    if dots and commas:
        dec = "." if mant.rfind(".") > mant.rfind(",") else ","
        grp = "," if dec == "." else "."
        mant = mant.replace(grp, "").replace(dec, ".")
    elif dots > 1:
        mant = mant.replace(".", "")
    elif commas > 1:
        mant = mant.replace(",", "")
    elif commas == 1:
        mant = mant.replace(",", ".")
    value = Decimal(mant)
    return value.scaleb(int(exp)) if exp else value


def tenths(text: str) -> int | None:
    return None if text == "" else half_even(Decimal(text) * 10)


def split_value(value: str, unit: str) -> tuple[str, str]:
    m = VALUE_UNIT_RE.fullmatch(value)
    if m and not unit:
        return m.group(1), m.group(2)
    return value, unit


# ------------------------------------------------------------------ clocks
def _nth_weekday(year: int, month: int, weekday: int, ordinal: int) -> datetime:
    if ordinal < 0:
        last = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=UTC) - timedelta(days=1)
        return last - timedelta(days=(last.weekday() - weekday) % 7)
    first = datetime(year, month, 1, tzinfo=UTC)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (ordinal - 1))


def _clock_edge(spec: tuple, year: int, offset: int) -> datetime:
    ordinal, weekday, month, minute, is_local = spec
    at = _nth_weekday(year, month, weekday, ordinal) + timedelta(minutes=minute)
    return at - timedelta(minutes=offset) if is_local else at


def offset_minutes(hours: str, minutes: str | None) -> int:
    sign = -1 if hours.startswith("-") else 1
    return sign * (60 * abs(int(hours)) + int(minutes or 0))


def daylight_shift(sentence: str, sites: list[tuple[str, int]]) -> int:
    written = [offset_minutes(h, m) for h, m in UTC_OFFSET_RE.findall(sentence)]
    if len(sites) == 1 and len(written) == 2:
        return written[1] - written[0]
    word = SHIFT_RE.search(sentence)
    if word:
        token = word.group(1).lower()
        if token.isdigit():
            return 60 * int(token)
        if token in WORD_NUMBER:
            return 60 * WORD_NUMBER[token]
    raise UpstreamError(f"{STANDARD_FILE} states no clock shift for {sites[0][0]}")


def standard_section(text: str, title: str) -> str:
    lines = text.splitlines()
    head = re.compile(rf"##\s+\d+\.\s+{re.escape(title)}\s*")
    for i, line in enumerate(lines):
        if head.fullmatch(line):
            rest = [j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")]
            return "\n".join(lines[i + 1:rest[0] if rest else len(lines)])
    raise UpstreamError(f"{STANDARD_FILE} has no {title} section")


def site_clocks(text: str) -> tuple[dict[str, int], dict[str, tuple | None]]:
    stated = SITE_CLOCKS_RE.search(" ".join(standard_section(text, "Times").split()))
    if not stated:
        raise UpstreamError(f"{STANDARD_FILE} states no site clocks")
    std: dict[str, int] = {}
    rules: dict[str, tuple | None] = {}
    for sentence in stated.group(1).split(". "):
        sites = [(m.group(1), offset_minutes(m.group(2), m.group(3))) for m in SITE_STD_RE.finditer(sentence)]
        if not sites:
            continue
        edges = [(ORDINAL_NUMBER[o], WEEKDAY_NUMBER[w.lower()], MONTH_NUMBER[mo.lower()],
                  60 * int(hh) + int(mm), basis != "UTC") for o, w, mo, hh, mm, basis in EDGE_RE.findall(sentence)]
        if edges and len(edges) != 2:
            raise UpstreamError(f"{STANDARD_FILE} gives {len(edges)} clock edges for {sites[0][0]}")
        rule = (edges[0], edges[1], daylight_shift(sentence, sites)) if edges else None
        for site, off in sites:
            std[site], rules[site] = off, rule
    if not std:
        raise UpstreamError(f"{STANDARD_FILE} names no site clock")
    return std, rules


def utc_offset(site: str, instant: datetime) -> int:
    std, rule = STD_OFFSET[site], CLOCK[site]
    if rule is None:
        return std
    start, end, shift = rule
    y = instant.year
    if _clock_edge(start, y, std) <= instant < _clock_edge(end, y, std + shift):
        return std + shift
    return std


def local_to_utc(site: str, naive: datetime) -> datetime:
    std, rule = STD_OFFSET[site], CLOCK[site]
    for off in dict.fromkeys((std, std + (0 if rule is None else rule[2]))):
        cand = (naive - timedelta(minutes=off)).replace(tzinfo=UTC)
        if utc_offset(site, cand) == off:
            return cand
    raise ValueError(f"local time {naive} does not exist at {site}")


def parse_time(raw: object, site_of) -> datetime:
    if isinstance(raw, float):
        return datetime(1899, 12, 30, tzinfo=UTC) + timedelta(seconds=round(raw * 86400))
    s = str(raw).strip()
    if re.fullmatch(r"\d{10}", s):
        return datetime.fromtimestamp(int(s), UTC)
    if re.fullmatch(r"\d{13}", s):
        return datetime.fromtimestamp(int(s) // 1000, UTC)
    if re.fullmatch(r"\d{5}\.\d+", s):
        return datetime(1899, 12, 30, tzinfo=UTC) + timedelta(seconds=round(Decimal(s) * 86400))
    if re.fullmatch(r"\d{8}T\d{6}Z", s):
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", s):
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", s):
        return datetime.fromisoformat(s).astimezone(UTC)
    if LOCAL_RE.fullmatch(s):
        return local_to_utc(site_of(), datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))
    return email.utils.parsedate_to_datetime(s).astimezone(UTC)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ readers: every source yields 8-field rows
def _pipe(line: str) -> list:
    return [p.strip() for p in line.split("|")]


def _rows_from_dicts(items) -> list[list]:
    return [list(d.values()) for d in items]


def read_source(path: Path) -> list[list]:
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv"):
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.reader(fh, delimiter="\t" if suffix == ".tsv" else ","))[1:]
    if suffix == ".jsonl":
        return [list(json.loads(ln).values()) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if suffix == ".json":
        return _rows_from_dicts(json.loads(path.read_text(encoding="utf-8"))["records"])
    if suffix == ".xml":
        return [list(el.attrib.values()) for el in ET.parse(path).getroot().iter("rec")]
    if suffix == ".yaml":
        return _rows_from_dicts(yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)["records"])
    if suffix == ".toml":
        return _rows_from_dicts(tomllib.loads(path.read_text(encoding="utf-8"))["records"])
    if suffix == ".ini":
        cp = configparser.ConfigParser(interpolation=None, strict=True)
        cp.read_string(path.read_text(encoding="utf-8"))
        return [[key] + _pipe(val) for sec in cp.sections() for key, val in cp.items(sec)]
    if suffix == ".log":
        return [[json.loads(v) for _, v in re.findall(r'(\w+)=("(?:[^"\\]|\\.)*")', ln)]
                for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if suffix == ".txt":
        return [_pipe(ln) for ln in path.read_text(encoding="utf-8").splitlines()[1:] if ln.strip()]
    if suffix == ".md":
        lines = path.read_text(encoding="utf-8").splitlines()
        start = next(i for i, ln in enumerate(lines) if ln.startswith("|---"))
        return [_pipe(ln.strip()[1:-1]) for ln in lines[start + 1:] if ln.startswith("|")]
    if suffix == ".html":
        text = path.read_text(encoding="utf-8")
        return [[html.unescape(c) for c in re.findall(r"<td>(.*?)</td>", tr)]
                for tr in re.findall(r"<tr>(<td>.*?)</tr>", text)]
    if suffix == ".ics":
        return [_pipe(ln[6:]) for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("X-REC:")]
    if suffix == ".mbox":
        out = []
        for msg in mailbox.mbox(str(path)):
            body = msg.get_payload(decode=True).decode("utf-8")
            out += [_pipe(ln) for ln in body.splitlines() if ln.strip()]
        return out
    if suffix == ".xlsx":
        wb = openpyxl.load_workbook(path, read_only=True)
        rows = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)][1:]
        wb.close()
        return [[v if isinstance(v, float) else ("" if v is None else str(v)) for v in r] for r in rows]
    if suffix == ".docx":
        with zipfile.ZipFile(path) as zf:
            doc = zf.read("word/document.xml").decode("utf-8")
        paras = [html.unescape("".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p)))
                 for p in re.findall(r"<w:p>(.*?)</w:p>", doc)]
        return [_pipe(p) for p in paras[2:]]
    if suffix == ".pdf":
        lines = []
        for page in PdfReader(str(path)).pages:
            lines += page.extract_text().splitlines()
        return [_pipe(ln) for ln in lines[2:] if ln.strip()]
    if suffix == ".parquet":
        cols = pq.read_table(path).to_pydict()
        names = list(cols)
        return [[cols[n][i] for n in names] for i in range(len(cols[names[0]]))]
    if suffix == ".db":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = [list(r) for r in con.execute("SELECT * FROM records ORDER BY rowid")]
        con.close()
        return rows
    raise ValueError(f"unknown source type {path.name}")


NUMERIC_RE = re.compile(r"[-+]?[0-9][0-9.,' \u202f]*([eE][-+]?\d+)?")


def attrs_of(text: str) -> dict[str, str]:
    out = {}
    for part in text.split(";"):
        if part.strip():
            k, _, v = part.partition("=")
            out[k.strip().lower()] = v.strip()
    return out


def num(text: str) -> int:
    return int(parse_number(text))


def record_id(text: str) -> str:
    low = text.strip().lower()
    return low[4:] if low.startswith("rec:") else low


def canon_host(name: str) -> str:
    low = name.strip().lower()
    return low[: -len(".pwr.corp")] if low.endswith(".pwr.corp") else low


def efficiency_bp(value: str, unit: str) -> int:
    v = value.strip()
    if v.endswith("%"):
        return half_even(parse_number(v[:-1]) * 100)
    return half_even(parse_number(v) * {"%": 100, "frac": 10000, "bp": 1, "permille": 10}[unit.strip().lower()])


class Rec:
    __slots__ = ("file", "rid", "key", "kind", "subject", "at_raw", "value", "unit", "attrs", "t", "host")

    def __init__(self, file: str, row: list) -> None:
        self.file = file
        self.rid, self.kind, self.subject = str(row[0]).strip(), str(row[1]).strip(), str(row[2]).strip()
        self.key = record_id(self.rid)
        self.at_raw = row[3] if isinstance(row[3], float) else str(row[3]).strip()
        self.value, self.unit = str(row[4]).strip(), str(row[5]).strip()
        self.attrs = attrs_of(str(row[6]))
        if self.kind in ("VO", "ER", "RT"):
            self.subject = record_id(self.subject)
        self.t: datetime | None = None
        self.host: str | None = None


# ------------------------------------------------------------------ phase 1
class Fleet:
    def __init__(self, data_dir: Path) -> None:
        self.names = sorted(p.name for p in data_dir.iterdir() if p.is_file())
        self.recs: dict[str, list[Rec]] = {}
        for name in self.names:
            self.recs[name] = [Rec(name, row) for row in read_source(data_dir / name)]
        self.all = [r for name in self.names for r in self.recs[name]]
        self.by_rid: dict[str, Rec] = {}
        for r in self.all:
            self.by_rid.setdefault(r.key, r)
        self.late: set[int] = set()

    @staticmethod
    def superseded_file(name: str) -> bool:
        flat = name.lower().replace("_", "")
        return any(w in flat for w in NOT_IN_FORCE_WORDS)

    def live_file(self, r: Rec) -> bool:
        return not self.superseded_file(r.file) or (r.file, r.key) in self.ratified

    def in_force(self, r: Rec) -> bool:
        return self.live_file(r) and (r.kind in ("VO", "RT") or r.key not in self.voids)

    def applies(self, r: Rec) -> bool:
        return self.in_force(r) and id(r) not in self.late

    def compile(self) -> dict:
        # A void, erratum or ratification is timed by the site of the record it names, which can depend
        # on which records are in force; resolve until the set of post-cut registers stops changing.
        for _ in range(5):
            self._resolve()
            late = {id(r) for r in self.all
                    if r.kind in ("VO", "ER", "RT", "PF") and r.t is not None and r.t >= FREEZE}
            if late == self.late:
                break
            self.late = late
        return self._tables()

    def _resolve(self) -> None:
        self.ratified = {(r.attrs["file"], r.subject) for r in self.all
                         if r.kind == "RT" and not self.superseded_file(r.file) and id(r) not in self.late}
        self.voids = {r.subject for r in self.all
                      if r.kind == "VO" and self.live_file(r) and id(r) not in self.late}
        self._site_times()
        self._effective()
        self._aliases()
        self._host_records()
        self._register_times()

    def _site_times(self) -> None:
        for r in self.all:
            if r.kind == "HV":
                r.t = parse_time(r.at_raw, lambda r=r: r.attrs["rack"][:4])
            elif r.kind in ("CV", "CA"):
                r.t = parse_time(r.at_raw, lambda r=r: r.subject[:4])
            elif r.kind == "SP":
                r.t = parse_time(r.at_raw, lambda r=r: r.subject.split(":")[0])
            elif r.kind == "TN":
                r.t = parse_time(r.at_raw, lambda r=r: r.subject.split("@")[1])
            elif r.kind in ("MV", "PR", "PF"):
                r.t = parse_time(r.at_raw, lambda: "")

    def _latest(self, kind: str, keyf, records=None) -> dict:
        best: dict = {}
        for r in records if records is not None else self.all:
            if r.kind != kind or not self.in_force(r) or r.t >= FREEZE:
                continue
            k = keyf(r)
            rank = (int(r.value), r.t, r.key)
            if k is not None and (k not in best or rank > best[k][0]):
                best[k] = (rank, r)
        return {k: v[1] for k, v in best.items()}

    def _effective(self) -> None:
        self.hv = self._latest("HV", lambda r: canon_host(r.subject))
        self.cv = self._latest("CV", lambda r: r.subject)
        self.mv = self._latest("MV", lambda r: r.subject)
        self.pr = self._latest("PR", lambda r: r.subject)
        self.sp = self._latest("SP", lambda r: r.subject)
        self.tn = self._latest("TN", lambda r: r.subject)
        self.serials = {r.attrs["serial"]: canon_host(r.subject) for r in self.all
                        if r.kind == "HV" and self.in_force(r) and r.t < FREEZE}

    def host_site(self, h: str) -> str:
        return self.hv[h].attrs["rack"][:4]

    def _permanent_host(self, name: str) -> str | None:
        c = canon_host(name)
        return c if c in self.hv else self.permanent.get(name)

    def _aliases(self) -> None:
        live = [r for r in self.all if r.kind == "AL" and self.in_force(r)]
        self.permanent = {}
        for r in live:
            if canon_host(r.attrs["target"]) in self.hv:
                self.permanent.setdefault(r.subject, canon_host(r.attrs["target"]))
        self.aliases: dict[str, list[tuple[datetime, datetime, str]]] = {}
        for r in self.all:
            if r.kind != "AL":
                continue
            host = self._permanent_host(r.attrs["target"])
            site = self.host_site(host) if host in self.hv else None
            r.t = parse_time(r.at_raw, lambda site=site: site)
            r.attrs["until_utc"] = iso(parse_time(r.attrs["until"], lambda site=site: site))
            if self.in_force(r) and r.t < FREEZE:
                end = datetime.strptime(r.attrs["until_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
                self.aliases.setdefault(r.subject, []).append((r.t, end, r.attrs["target"]))

    def resolve_host(self, name: str, when: datetime, depth: int = 0) -> str | None:
        c = canon_host(name)
        if c in self.hv:
            return c
        if name in self.serials:
            return self.serials[name]
        if depth < 5:
            for start, end, target in self.aliases.get(name, []):
                if start <= when < end:
                    return self.resolve_host(target, when, depth + 1)
        return None

    def _host_records(self) -> None:
        for r in self.all:
            if r.kind not in ("RD", "QV"):
                continue
            direct = canon_host(r.subject) if canon_host(r.subject) in self.hv else self.serials.get(r.subject)
            guess = direct or (self.resolve_host(r.subject, WINDOW) if LOCAL_RE.fullmatch(str(r.at_raw)) else None)
            r.t = parse_time(r.at_raw, lambda guess=guess: self.host_site(guess))
            r.host = direct or self.resolve_host(r.subject, r.t)
        self.qv = self._latest("QV", lambda r: r.host)
        for r in self.all:
            if r.kind == "AM":
                site = r.subject[:4] if r.subject[:4] in CLOCK else self.host_site(r.subject)
                r.t = parse_time(r.at_raw, lambda site=site: site)

    def record_site(self, r: Rec) -> str:
        if r.kind in ("RD", "QV"):
            return self.host_site(r.host)
        if r.kind == "HV":
            return r.attrs["rack"][:4]
        if r.kind in ("CV", "CA"):
            return r.subject[:4]
        if r.kind == "AL":
            return self.host_site(self._permanent_host(r.attrs["target"]))
        if r.kind == "SP":
            return r.subject.split(":")[0]
        if r.kind == "TN":
            return r.subject.split("@")[1]
        if r.kind == "AM":
            return r.subject[:4] if r.subject[:4] in CLOCK else self.host_site(r.subject)
        return self.record_site(self.by_rid[r.subject])

    def _register_times(self) -> None:
        for r in self.all:
            if r.kind in ("VO", "ER", "RT"):
                r.t = parse_time(r.at_raw, lambda r=r: self.record_site(self.by_rid[r.subject]))

    # ---------------- readings and tables
    def reading_mw(self, r: Rec, er: dict, pf: dict, cal: dict, curves: dict) -> int | None:
        text, unit = split_value(r.value, r.unit)
        if text.strip().lower() in MISSING:
            return None
        if r.key in er:
            return half_even(parse_number(er[r.key]) * 1000)
        x = parse_number(text) * UNIT_FACTOR[unit.lower()]
        if r.attrs.get("batch") in pf:
            x = x * pf[r.attrs["batch"]] / 1000
        mw = half_even(x)
        hv = self.hv[r.host].attrs
        if unit.lower() in ("va", "kva"):
            mw = half_even(Decimal(mw) * num(self.mv[hv["model"]].attrs["pf"]) / 1000)
        if r.attrs.get("src") == "pdu":
            hit = None
            for t, gain, off in cal.get(r.attrs.get("outlet", ""), []):
                if t <= r.t:
                    hit = (gain, off)
            if hit:
                mw = half_even(Decimal(mw) * (1000000 + hit[0]) / 1000000) + hit[1]
        if r.attrs.get("dom") == "DC":
            rated = num(self.pr[hv["psu"]].attrs["rated"]) * num(hv["n"])
            load = min(1000, max(1, half_even(Decimal(mw) / rated)))
            mw = half_even(Decimal(mw) * 10000 / curves[hv["psu"]][load])
        return mw

    def _demand(self, hosts: dict, curves: dict) -> dict:
        er = {r.subject: r.value for r in self.all if r.kind == "ER" and self.applies(r)}
        pf = {r.subject: num(r.attrs["scale"]) for r in self.all if r.kind == "PF" and self.applies(r)}
        cal_raw: dict[str, list] = {}
        for r in self.all:
            if r.kind == "CA" and self.in_force(r):
                cal_raw.setdefault(r.subject, []).append((r.t, r.key, num(r.attrs["gain"]), num(r.attrs["offset"])))
        cal = {k: [(t, g, o) for t, _, g, o in sorted(v)] for k, v in cal_raw.items()}
        chosen: dict[tuple, tuple[int, int]] = {}
        seen = set()
        for r in self.all:
            if r.kind != "RD" or not self.in_force(r) or r.key in seen:
                continue
            seen.add(r.key)
            if r.host not in hosts or not (WINDOW <= r.t < FREEZE):
                continue
            mw = self.reading_mw(r, er, pf, cal, curves)
            if mw is None:
                continue
            key, rank = (r.host, r.t), SOURCE_RANK[r.attrs["src"]]
            if key not in chosen or rank < chosen[key][0]:
                chosen[key] = (rank, mw)
        per: dict[str, list[int]] = {}
        for (h, _), (_, mw) in chosen.items():
            per.setdefault(h, []).append(mw)
        out = {}
        for h in hosts:
            vals = sorted(per.get(h, []))
            n = len(vals)
            if not n:
                out[h] = {"host_id": h, "samples": 0, "mean_w": "", "p95_w": "", "peak_w": "", "energy_wh": ""}
                continue
            out[h] = {"host_id": h, "samples": n,
                      "mean_w": fixed(half_even(Decimal(sum(vals)) / (n * 100)), 1),
                      "p95_w": fixed(half_even(Decimal(vals[(95 * n + 99) // 100 - 1]) / 100), 1),
                      "peak_w": fixed(half_even(Decimal(vals[-1]) / 100), 1),
                      "energy_wh": half_even(Decimal(sum(vals)) / 4000)}
        return out

    def _tables(self) -> dict:
        params: dict[str, dict[str, int]] = {}
        for key, r in self.sp.items():
            site, param = key.split(":")
            params.setdefault(site, {})[param] = num(r.attrs[param])
        curves: dict[str, dict[int, int]] = {}
        for r in self.recs["power_standard.md"]:
            if r.kind == "PV":
                curves.setdefault(r.subject, {})[num(r.attrs["load"])] = efficiency_bp(r.value, r.unit)
        hosts = {}
        for h, r in self.hv.items():
            if r.attrs["status"] != "active":
                continue
            mv = self.mv[r.attrs["model"]].attrs
            pol = self.qv.get(h)
            idle = num(mv["idle"])
            hosts[h] = {"host_id": h, "site": r.attrs["rack"][:4], "rack_id": r.attrs["rack"],
                        "model": r.attrs["model"], "psu_model": r.attrs["psu"], "psu_count": num(r.attrs["n"]),
                        "tenant": r.attrs["tenant"], "priority": pol.attrs["prio"] if pol else "bronze",
                        "cap_domain": mv["domain"], "nameplate_w": half_even(Decimal(num(mv["va"]) * num(mv["pf"])) / 1000),
                        "idle_w": idle, "floor_w": max(idle, num(pol.attrs["floor"]) if pol else 0), "cap_ceiling_w": ""}
        circuits = {c: {"circuit_id": c, "site": c[:4], "rack_id": r.attrs["rack"], "feed": r.attrs["feed"],
                        "voltage_v": num(r.attrs["volts"]), "breaker_a": num(r.attrs["amps"])}
                    for c, r in self.cv.items()}
        carried = []
        for a in sorted((r for r in self.all if r.kind == "AM" and self.in_force(r)), key=lambda r: (r.t, r.key)):
            field, val = a.attrs["field"], a.attrs["value"]
            val = val if field == "priority" else str(num(val))
            if a.t >= FREEZE:
                carried.append({"amendment_id": a.rid, "effective_utc": iso(a.t), "target": a.subject,
                                "field": field, "value": val})
            elif field == "breaker_a" and a.subject in circuits:
                circuits[a.subject]["breaker_a"] = int(val)
            elif field != "breaker_a" and a.subject in hosts:
                hosts[a.subject][field] = val if field == "priority" else int(val)
        for c in circuits.values():
            p = params[c["site"]]
            c["usable_w"] = c["voltage_v"] * c["breaker_a"] * p["cont"] * p["derate"] // 1000000
        order = sorted(hosts, key=lambda h: (hosts[h]["rack_id"], PRIORITY_ORDER[hosts[h]["priority"]], h))
        demand = self._demand(hosts, curves)
        rated = {p: num(self.pr[p].attrs["rated"]) for p in self.pr}
        sites = [{"site": s, "cont_pm": p["cont"], "derate_pm": p["derate"], "volts": p["volts"],
                  "tariff_mc": p["tariff"], "pue_milli": p["pue"], "cap_step_w": p["step"],
                  "margin_pm": p["margin"], "warn_pm": p["warn"], "crit_pm": p["crit"], "pool_pm": p["pool"],
                  "correction_ms": p["corr"]} for s, p in sorted(params.items())]
        tenants = []
        for key in sorted(self.tn, key=lambda k: (k.split("@")[1], k.split("@")[0])):
            name, site = key.split("@")
            tenants.append({"site": site, "tenant": name, "entitlement_w": num(self.tn[key].attrs["watts"])})
        return {"hosts": [hosts[h] for h in order], "circuits": [circuits[c] for c in sorted(circuits)],
                "demand": [demand[h] for h in order],
                "psu": [{"psu_model": p, "rated_w": rated[p], "load_pm": x, "eff_bp": curves[p][x]}
                        for p in sorted(curves) for x in sorted(curves[p])],
                "amendments": carried,
                "registry": {"freeze_utc": iso(FREEZE), "window_start_utc": iso(WINDOW), "sites": sites,
                             "tenants": tenants, "sources": self._attest()}}

    # ---------------- attestation
    def canonical(self, r: Rec) -> str:
        k, a = r.kind, r.attrs
        when = iso(r.t) if r.t is not None and k != "PV" else ""
        if k == "RD":
            text, unit = split_value(r.value, r.unit)
            val = "null" if text.strip().lower() in MISSING else str(half_even(parse_number(text) * UNIT_FACTOR[unit.lower()]))
            uc = "VA" if unit.lower() in ("va", "kva") else "W"
            return (f"RD|{r.rid}|{r.host}|{when}|{val}|batch={a['batch']};dom={a['dom']};"
                    f"outlet={a.get('outlet', '')};src={a['src']};uc={uc}")
        subject = canon_host(r.subject) if k == "HV" else (r.host if k == "QV" else r.subject)
        if k in ("HV", "CV", "MV", "PR", "QV", "SP", "TN"):
            val = r.value
        elif k == "PV":
            val = str(efficiency_bp(r.value, r.unit))
        elif k == "ER":
            val = str(half_even(parse_number(r.value) * 1000))
        else:
            val = ""
        if k == "AL":
            extra = f"target={a['target']};until={a['until_utc']}"
        else:
            extra = ";".join(f"{key}={num(a[key]) if NUMERIC_RE.fullmatch(a[key]) else a[key]}" for key in sorted(a))
        return f"{k}|{r.rid}|{subject}|{when}|{val}|{extra}"

    def _attest(self) -> list[dict]:
        out = []
        for name in self.names:
            recs = self.recs[name]
            text = "\n".join(self.canonical(r) for r in recs) + "\n"
            out.append({"file": name, "records": len(recs),
                        "voided": sum(1 for r in recs if r.kind not in ("VO", "RT") and r.key in self.voids),
                        "post_cut": sum(1 for r in recs if r.t is not None and r.kind != "PV" and r.t >= FREEZE),
                        "digest": hashlib.sha256(text.encode("utf-8")).hexdigest()})
        return out


# ------------------------------------------------------------------ writers
def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    lines = [",".join(header)] + [",".join("" if r[h] is None else str(r[h]) for h in header) for r in rows]
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def write_json(path: Path, obj) -> None:
    path.write_bytes((json.dumps(obj, indent=2, ensure_ascii=True) + "\n").encode("utf-8"))


HEADERS = {
    "hosts.csv": ["host_id", "site", "rack_id", "model", "psu_model", "psu_count", "tenant", "priority",
                  "cap_domain", "nameplate_w", "idle_w", "floor_w", "cap_ceiling_w"],
    "circuits.csv": ["circuit_id", "site", "rack_id", "feed", "voltage_v", "breaker_a", "usable_w"],
    "demand.csv": ["host_id", "samples", "mean_w", "p95_w", "peak_w", "energy_wh"],
    "psu.csv": ["psu_model", "rated_w", "load_pm", "eff_bp"],
    "amendments.csv": ["amendment_id", "effective_utc", "target", "field", "value"],
    "rack_budget.csv": ["rack_id", "site", "hosts", "feed_a_w", "feed_b_w", "budget_w", "nameplate_w", "p95_w",
                        "headroom_w", "psu_n1_ok", "pending"],
    "host_alloc.csv": ["host_id", "rack_id", "request_w", "alloc_w", "short_w", "overcommit", "amended"],
    "site_energy.csv": ["site", "hosts", "null_hosts", "zero_hosts", "it_kwh", "dc_kwh", "facility_kwh",
                        "cost_cents", "capacity_kw", "pending"],
    "circuit_alarms.csv": ["circuit_id", "rack_id", "feed", "voltage_v", "expected_a", "failover_a", "warn_a",
                           "crit_a", "state", "psu_over", "pending"],
    "tenant_pool.csv": ["site", "tenant", "hosts", "request_w", "entitlement_w", "granted_w", "cut_w", "pending"],
}
P1_ALL = ["hosts.csv", "circuits.csv", "demand.csv", "psu.csv", "registry.json", "amendments.csv"]
P2_ALL = ["rack_budget.csv", "host_alloc.csv", "site_energy.csv", "circuit_alarms.csv", "tenant_pool.csv",
          "fleet_summary.json"]


def read_standard(data_dir: Path) -> None:
    global FREEZE, WINDOW
    path = data_dir / STANDARD_FILE
    if not path.is_file():
        raise UpstreamError(f"source file {STANDARD_FILE} is missing from {data_dir}")
    text = path.read_text(encoding="utf-8")
    m = FREEZE_RE.search(" ".join(text.split()))
    if not m:
        raise UpstreamError(f"{STANDARD_FILE} states no freeze and window")
    FREEZE = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    WINDOW = datetime.strptime(m.group(2), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    offsets, rules = site_clocks(text)
    STD_OFFSET.clear()
    STD_OFFSET.update(offsets)
    CLOCK.clear()
    CLOCK.update(rules)


def phase1(data_dir: Path, out: Path) -> None:
    if not data_dir.is_dir():
        raise UpstreamError(f"input directory {data_dir} is not readable")
    read_standard(data_dir)
    tables = Fleet(data_dir).compile()
    out.mkdir(parents=True, exist_ok=True)
    for name in ("hosts.csv", "circuits.csv", "demand.csv", "psu.csv", "amendments.csv"):
        write_csv(out / name, HEADERS[name], tables[name[:-4]])
    write_json(out / "registry.json", tables["registry"])


# ------------------------------------------------------------------ phase 2
def read_table(directory: Path, name: str) -> list[dict]:
    path = directory / name
    if not path.is_file():
        raise UpstreamError(f"upstream file {name} is missing from {directory}")
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_doc(directory: Path, name: str):
    path = directory / name
    if not path.is_file():
        raise UpstreamError(f"upstream file {name} is missing from {directory}")
    return json.loads(path.read_text(encoding="utf-8"))


def lineage(directory: Path, names: list[str], prefix: str) -> dict:
    out = {}
    for n in names:
        data = (directory / n).read_bytes()
        out[f"{prefix}/{n}"] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                                "lines": data.count(b"\n")}
    return out


class Upstream:
    def __init__(self, p1: Path) -> None:
        if not p1.is_dir():
            raise UpstreamError(f"phase-1 directory {p1} is not readable")
        self.dir = p1
        self.hosts = read_table(p1, "hosts.csv")
        self.circuits = {c["circuit_id"]: c for c in read_table(p1, "circuits.csv")}
        self.demand = {d["host_id"]: d for d in read_table(p1, "demand.csv")}
        self.rated, self.eff = {}, {}
        for r in read_table(p1, "psu.csv"):
            self.rated[r["psu_model"]] = int(r["rated_w"])
            self.eff[(r["psu_model"], int(r["load_pm"]))] = int(r["eff_bp"])
        self.registry = read_doc(p1, "registry.json")
        self.amendments = read_table(p1, "amendments.csv")
        self.site = {s["site"]: s for s in self.registry["sites"]}
        self.pending: dict[str, int] = {}
        for a in self.amendments:
            self.pending[a["target"]] = self.pending.get(a["target"], 0) + 1
        self.racks = sorted({c["rack_id"] for c in self.circuits.values()})
        self.rack_hosts: dict[str, list[dict]] = {}
        for h in self.hosts:
            self.rack_hosts.setdefault(h["rack_id"], []).append(h)

    def usable(self, rack: str, feed: str) -> int:
        return int(self.circuits[f"{rack}-{feed}"]["usable_w"])

    def budget(self, rack: str) -> int:
        step = int(self.site[rack[:4]]["cap_step_w"])
        return min(self.usable(rack, "A"), self.usable(rack, "B")) // step * step

    def site_budget(self, site: str) -> int:
        return sum(self.budget(rk) for rk in self.racks if rk[:4] == site)

    def allocation(self) -> list[dict]:
        left = {rk: self.budget(rk) for rk in self.racks}
        rows = []
        for h in self.hosts:
            hid = h["host_id"]
            prm = self.site[h["site"]]
            step = int(prm["cap_step_w"])
            d = self.demand[hid]
            plate = int(h["nameplate_w"])
            top = min(plate, self.rated[h["psu_model"]] * int(h["psu_count"]))
            if h["cap_ceiling_w"] != "":
                top = min(top, int(h["cap_ceiling_w"]))
            if d["samples"] == "0":
                basis = plate
            else:
                want = Decimal(d["p95_w"]) * (1000 + int(prm["margin_pm"])) / 1000
                basis = -floor_int(-want / step) * step
            floor = int(h["floor_w"])
            request = min(max(basis, floor), top)
            room = left.get(h["rack_id"], 0)
            alloc = min(request, max(room, 0))
            over = 1 if alloc < floor else 0
            alloc = max(alloc, floor)
            left[h["rack_id"]] = room - alloc
            rows.append({"host_id": hid, "rack_id": h["rack_id"], "request_w": request, "alloc_w": alloc,
                         "short_w": request - alloc, "overcommit": over, "amended": int(hid in self.pending)})
        return rows


def phase2(p1: Path, out: Path) -> None:
    v = Upstream(p1)
    out.mkdir(parents=True, exist_ok=True)
    budget_rows = []
    for rk in v.racks:
        hs = v.rack_hosts.get(rk, [])
        p95 = [tenths(v.demand[h["host_id"]]["p95_w"]) for h in hs]
        load = half_even(Decimal(sum(x for x in p95 if x is not None)) / 10)
        b = v.budget(rk)
        budget_rows.append({
            "rack_id": rk, "site": rk[:4], "hosts": len(hs), "feed_a_w": v.usable(rk, "A"),
            "feed_b_w": v.usable(rk, "B"), "budget_w": b, "nameplate_w": sum(int(h["nameplate_w"]) for h in hs),
            "p95_w": load, "headroom_w": b - load,
            "psu_n1_ok": sum(1 for h, x in zip(hs, p95)
                             if h["psu_count"] == "2" and x is not None and x <= 10 * v.rated[h["psu_model"]]),
            "pending": sum(v.pending.get(h["host_id"], 0) for h in hs) + v.pending.get(f"{rk}-A", 0)
            + v.pending.get(f"{rk}-B", 0)})
    write_csv(out / "rack_budget.csv", HEADERS["rack_budget.csv"], budget_rows)
    alloc = v.allocation()
    write_csv(out / "host_alloc.csv", HEADERS["host_alloc.csv"], alloc)
    energy_rows = []
    for s in sorted(v.site):
        prm = v.site[s]
        hs = [h for h in v.hosts if h["site"] == s]
        it_wh = dc_wh = nulls = zeros = 0
        for h in hs:
            d = v.demand[h["host_id"]]
            if d["samples"] == "0":
                nulls += 1
                continue
            zeros += int(Decimal(d["peak_w"]) == 0)
            wh = int(d["energy_wh"])
            it_wh += wh
            per_mille = half_even(Decimal(d["mean_w"]) * 1000 / (int(h["psu_count"]) * v.rated[h["psu_model"]]))
            dc_wh += half_even(Decimal(wh) * v.eff[(h["psu_model"], min(1000, max(1, per_mille)))] / 10000)
        it_c = half_even(Decimal(it_wh) / 10)
        fac_c = half_even(Decimal(it_c) * int(prm["pue_milli"]) / 1000)
        cap_w = sum(min(v.usable(rk, "A"), v.usable(rk, "B")) for rk in v.racks if rk[:4] == s)
        pend = sum(n for t, n in v.pending.items() if t in v.circuits and t[:4] == s) \
            + sum(v.pending.get(h["host_id"], 0) for h in hs)
        energy_rows.append({"site": s, "hosts": len(hs), "null_hosts": nulls, "zero_hosts": zeros,
                            "it_kwh": fixed(it_c, 2), "dc_kwh": fixed(half_even(Decimal(dc_wh) / 10), 2),
                            "facility_kwh": fixed(fac_c, 2),
                            "cost_cents": half_even(Decimal(fac_c) * int(prm["tariff_mc"]) / 100000),
                            "capacity_kw": fixed(half_even(Decimal(cap_w) / 10), 2), "pending": pend})
    write_csv(out / "site_energy.csv", HEADERS["site_energy.csv"], energy_rows)
    alarm_rows = []
    for cid in sorted(v.circuits):
        c = v.circuits[cid]
        prm = v.site[c["site"]]
        volts = int(c["voltage_v"])
        steady, spike, over = Decimal(0), 0, 0
        for h in v.rack_hosts.get(c["rack_id"], []):
            d = v.demand[h["host_id"]]
            mean, peak = tenths(d["mean_w"]) or 0, tenths(d["peak_w"]) or 0
            if h["psu_count"] == "1":
                if c["feed"] == "A":
                    steady += mean
                    spike += peak
            else:
                steady += Decimal(mean) / 2
                spike += peak
                over += int(peak > 10 * v.rated[h["psu_model"]])
        rating = int(c["breaker_a"]) * int(prm["cont_pm"]) * int(prm["derate_pm"])
        warn, crit = rating * int(prm["warn_pm"]) // 10 ** 8, rating * int(prm["crit_pm"]) // 10 ** 8
        fail = half_even(Decimal(spike) * 10 / volts)
        alarm_rows.append({"circuit_id": cid, "rack_id": c["rack_id"], "feed": c["feed"], "voltage_v": volts,
                           "expected_a": fixed(half_even(steady * 10 / volts), 2), "failover_a": fixed(fail, 2),
                           "warn_a": fixed(warn, 1), "crit_a": fixed(crit, 1),
                           "state": "crit" if fail >= 10 * crit else "warn" if fail >= 10 * warn else "ok",
                           "psu_over": over, "pending": v.pending.get(cid, 0)})
    write_csv(out / "circuit_alarms.csv", HEADERS["circuit_alarms.csv"], alarm_rows)
    allot = {a["host_id"]: a["alloc_w"] for a in alloc}
    ent = {(t["site"], t["tenant"]): int(t["entitlement_w"]) for t in v.registry["tenants"]}
    pool = {s: v.site_budget(s) * int(v.site[s]["pool_pm"]) // 1000 for s in v.site}
    pool_rows = []
    for s, tn in sorted(set(ent) | {(h["site"], h["tenant"]) for h in v.hosts}):
        members = [h["host_id"] for h in v.hosts if h["site"] == s and h["tenant"] == tn]
        ask = sum(allot[m] for m in members)
        grant = min(ask, ent.get((s, tn), 0), pool[s])
        pool[s] -= grant
        pool_rows.append({"site": s, "tenant": tn, "hosts": len(members), "request_w": ask,
                          "entitlement_w": ent.get((s, tn), 0), "granted_w": grant, "cut_w": ask - grant,
                          "pending": sum(v.pending.get(m, 0) for m in members)})
    write_csv(out / "tenant_pool.csv", HEADERS["tenant_pool.csv"], pool_rows)
    summary = []
    for s in sorted(v.site):
        rows = [a for a in alloc if a["rack_id"][:4] == s]
        summary.append({"site": s, "hosts": len(rows), "budget_w": v.site_budget(s),
                        "request_w": sum(a["request_w"] for a in rows), "alloc_w": sum(a["alloc_w"] for a in rows),
                        "pending": next(e["pending"] for e in energy_rows if e["site"] == s)})
    write_json(out / "fleet_summary.json", {"freeze_utc": v.registry["freeze_utc"],
                                             "inputs": lineage(p1, P1_ALL, "p1"), "sites": summary})


# ------------------------------------------------------------------ phase 3
def phase3(p1: Path, p2: Path, out: Path) -> None:
    v = Upstream(p1)
    if not p2.is_dir():
        raise UpstreamError(f"phase-2 directory {p2} is not readable")
    budget = {r["rack_id"]: r for r in read_table(p2, "rack_budget.csv")}
    alloc = {r["host_id"]: r for r in read_table(p2, "host_alloc.csv")}
    energy = {r["site"]: r for r in read_table(p2, "site_energy.csv")}
    alarms = {r["circuit_id"]: r for r in read_table(p2, "circuit_alarms.csv")}
    pools = {(r["site"], r["tenant"]): r for r in read_table(p2, "tenant_pool.csv")}
    site_alloc = {s["site"]: s["alloc_w"] for s in read_doc(p2, "fleet_summary.json")["sites"]}
    lin = {**lineage(p1, P1_ALL, "p1"), **lineage(p2, P2_ALL, "p2")}
    out.mkdir(parents=True, exist_ok=True)
    by_target: dict[str, list[dict]] = {}
    for a in v.amendments:
        by_target.setdefault(a["target"], []).append(a)
    applied: list[dict] = []
    caps = []
    label = {"gold": "protect", "silver": "standard", "bronze": "aggressive"}
    for h in v.hosts:
        hid, s, rk = h["host_id"], h["site"], h["rack_id"]
        prm = v.site[s]
        a = int(alloc[hid]["alloc_w"])
        pool = pools[(s, h["tenant"])]
        cap = a * int(pool["granted_w"]) // int(pool["request_w"]) if int(pool["cut_w"]) > 0 and int(pool["request_w"]) else a
        floor, prio, ceiling = int(h["floor_w"]), h["priority"], h["cap_ceiling_w"] or None
        for am in by_target.get(hid, []):
            f, val = am["field"], am["value"]
            before = {"cap_ceiling_w": ceiling, "floor_w": str(floor), "priority": prio}[f]
            applied.append({"amendment_id": am["amendment_id"], "target": hid, "field": f, "before": before, "after": val})
            if f == "cap_ceiling_w":
                ceiling, cap = val, min(cap, int(val))
            elif f == "floor_w":
                floor = int(val)
            else:
                prio = val
        step = int(prm["cap_step_w"])
        cap = max(cap // step * step, floor)
        if h["cap_domain"] == "DC":
            load = min(1000, max(1, half_even(Decimal(cap) * 1000 / (v.rated[h["psu_model"]] * int(h["psu_count"])))))
            native = half_even(Decimal(cap) * v.eff[(h["psu_model"], load)] / 10000)
        else:
            native = cap
        if v.demand[hid]["samples"] == "0":
            throttle = "static"
        elif int(budget[rk]["headroom_w"]) < 0:
            throttle = "aggressive"
        else:
            throttle = label[prio]
        it_c = int(energy[s]["it_kwh"].replace(".", ""))
        fac_c = int(energy[s]["facility_kwh"].replace(".", ""))
        quiet = {alarms[f"{rk}-A"]["state"], alarms[f"{rk}-B"]["state"]} == {"ok"}
        caps.append({"host_id": hid, "rack_id": rk, "cap_w": cap, "domain": h["cap_domain"], "native_cap_w": native,
                     "correction_ms": int(prm["correction_ms"]) * (1 if quiet else 2), "throttle": throttle,
                     "site_share_pm": half_even(Decimal(cap) * 1000 / site_alloc[s]) if site_alloc[s] else 0,
                     "feed_breaker_a": min(int(v.circuits[f"{rk}-A"]["breaker_a"]), int(v.circuits[f"{rk}-B"]["breaker_a"])),
                     "pue_milli": half_even(Decimal(fac_c) * 1000 / it_c) if it_c else int(prm["pue_milli"])})
    breaker = {cid: int(c["breaker_a"]) for cid, c in v.circuits.items()}
    for am in v.amendments:
        if am["field"] == "breaker_a":
            applied.append({"amendment_id": am["amendment_id"], "target": am["target"], "field": "breaker_a",
                            "before": str(breaker[am["target"]]), "after": am["value"]})
            breaker[am["target"]] = int(am["value"])
    position = {am["amendment_id"]: i for i, am in enumerate(v.amendments)}
    applied.sort(key=lambda x: position[x["amendment_id"]])
    keys = ["cap_w", "domain", "native_cap_w", "correction_ms", "throttle", "site_share_pm", "feed_breaker_a", "pue_milli"]
    text = []
    for c in caps:
        text += [f"[{c['host_id']}]"] + [f"{k} = {c[k]}" for k in keys] + [""]
    text += ["[lineage]"] + [f"{k} = {e['sha256']}:{e['bytes']}:{e['lines']}" for k, e in lin.items()]
    (out / "bmc_caps.ini").write_bytes(("\n".join(text) + "\n").encode("utf-8"))
    share: dict[str, Decimal] = {}
    for h in v.hosts:
        a = Decimal(alloc[h["host_id"]]["alloc_w"])
        feeds = "A" if h["psu_count"] == "1" else "AB"
        for f in feeds:
            key = f"{h['rack_id']}-{f}"
            share[key] = share.get(key, Decimal(0)) + a / len(feeds)
    circuits_out = []
    for cid in sorted(v.circuits):
        c, al = v.circuits[cid], alarms[cid]
        prm = v.site[c["site"]]
        if breaker[cid] != int(c["breaker_a"]):
            rating = breaker[cid] * int(prm["cont_pm"]) * int(prm["derate_pm"])
            warn, crit = rating * int(prm["warn_pm"]) // 10 ** 8, rating * int(prm["crit_pm"]) // 10 ** 8
        else:
            warn, crit = tenths(al["warn_a"]), tenths(al["crit_a"])
        fail = half_even(Decimal(al["failover_a"]) * 100)
        circuits_out.append({"circuit_id": cid, "breaker_a": breaker[cid], "warn_a": fixed(warn, 1),
                             "crit_a": fixed(crit, 1), "expected_a": al["expected_a"],
                             "alloc_a": fixed(half_even(share.get(cid, Decimal(0)) * 100 / int(c["voltage_v"])), 2),
                             "state": "crit" if fail >= 10 * crit else "warn" if fail >= 10 * warn else "ok"})
    write_json(out / "pdu_alarms.json", {"circuits": circuits_out, "lineage": lin})
    bill = []
    for s in sorted(v.site):
        cents = int(energy[s]["cost_cents"])
        use: dict[str, int] = {}
        for h in v.hosts:
            if h["site"] == s:
                d = v.demand[h["host_id"]]
                use[h["tenant"]] = use.get(h["tenant"], 0) + (int(d["energy_wh"]) if d["samples"] != "0" else 0)
        total = sum(use.values())
        names = sorted(use)
        exact = {n: Decimal(cents * use[n]) / total if total else Decimal(0) for n in names}
        part = {n: floor_int(exact[n]) for n in names}
        spare = cents - sum(part.values()) if total else 0
        for n in sorted(names, key=lambda n: (part[n] - exact[n], n))[:spare]:
            part[n] += 1
        bill += [{"site": s, "tenant": n, "energy_wh": use[n],
                  "share_ppm": half_even(Decimal(use[n]) * 1000000 / total) if total else 0, "cost_cents": part[n]}
                 for n in names]
    write_json(out / "chargeback.json", {"tenants": bill, "lineage": lin})
    found = []
    for c in caps:
        peak = v.demand[c["host_id"]]["peak_w"]
        if peak != "" and 10 * c["cap_w"] < tenths(peak):
            found.append({"type": "cap_below_peak", "id": c["host_id"], "detail": f"cap={c['cap_w']};peak={peak}"})
    for hid, a in alloc.items():
        if a["overcommit"] == "1":
            found.append({"type": "overcommit", "id": hid, "detail": f"alloc={a['alloc_w']};request={a['request_w']}"})
    for rk, b in budget.items():
        if int(b["headroom_w"]) < 0:
            found.append({"type": "rack_over_budget", "id": rk, "detail": f"headroom={b['headroom_w']}"})
    for c in circuits_out:
        if c["state"] == "crit":
            found.append({"type": "circuit_crit", "id": c["circuit_id"],
                          "detail": f"failover={alarms[c['circuit_id']]['failover_a']};crit={c['crit_a']}"})
    for (s, tn), p in pools.items():
        if int(p["cut_w"]) > 0:
            found.append({"type": "tenant_cut", "id": f"{tn}@{s}", "detail": f"cut={p['cut_w']}"})
    found.sort(key=lambda e: (e["type"], e["id"]))
    write_json(out / "exceptions.json", {"exceptions": found, "lineage": lin})
    room_rows = []
    for s in sorted(v.site):
        racks = sorted(rk for rk in budget if rk[:4] == s)
        quota = sum(int(budget[rk]["budget_w"]) for rk in racks) * int(v.site[s]["pool_pm"]) // 1000
        quota -= sum(int(p["granted_w"]) for (ps, _), p in pools.items() if ps == s)
        free_sum = slots = full = 0
        for rk in racks:
            free = int(budget[rk]["budget_w"]) - sum(c["cap_w"] for c in caps if c["rack_id"] == rk)
            free_sum += free
            full += int(free < 500)
            n = min(max(free, 0) // 500, max(quota, 0) // 500)
            slots += n
            quota -= 500 * n
        room_rows.append({"site": s, "free_w": free_sum, "slots_500w": slots, "racks_full": full})
    write_json(out / "capacity.json", {"sites": room_rows, "lineage": lin})
    write_json(out / "release.json", {"freeze_utc": v.registry["freeze_utc"], "applied": applied,
                                       "totals": {"hosts": len(caps), "cap_w": sum(c["cap_w"] for c in caps),
                                                  "native_cap_w": sum(c["native_cap_w"] for c in caps)},
                                       "lineage": lin})


# ------------------------------------------------------------------ entry point
def main(argv: list[str]) -> int:
    arity = {"phase1": 2, "phase2": 2, "phase3": 3}
    try:
        if not argv or argv[0] not in arity:
            raise UsageError("first argument must be phase1, phase2 or phase3")
        stage, args = argv[0], argv[1:]
        if len(args) != arity[stage]:
            raise UsageError(f"{stage} takes {arity[stage]} directory arguments, got {len(args)}")
        dirs = [Path(a) for a in args]
        {"phase1": phase1, "phase2": phase2, "phase3": phase3}[stage](*dirs)
        return 0
    except UsageError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (UpstreamError, OSError, IndexError, KeyError, ValueError) as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_UPSTREAM


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
