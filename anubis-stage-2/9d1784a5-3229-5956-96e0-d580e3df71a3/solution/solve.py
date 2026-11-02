#!/usr/bin/env python3
"""Recompute the cryostat heat-load budget from a corpus laid out like /app/data.

Usage: run_budget.py DATA_DIR OUT_DIR
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

UTC = timezone.utc
STAGES = ("ST300", "ST50", "ST4")
COOLED = ("ST50", "ST4")


def F(text) -> Fraction:
    return Fraction(str(text).strip())


def half_even(x: Fraction) -> int:
    return round(x)


def plain(x: Fraction) -> str:
    """Exact decimal text with trailing zeros removed (x must terminate)."""
    x = Fraction(x)
    neg = x < 0
    x = abs(x)
    whole, rest = divmod(x.numerator, x.denominator)
    digits = ""
    seen = 0
    while rest and seen < 40:
        rest *= 10
        d, rest = divmod(rest, x.denominator)
        digits += str(d)
        seen += 1
    s = str(whole) + ("." + digits.rstrip("0") if digits.rstrip("0") else "")
    return ("-" if neg and s != "0" else "") + s


def fixed(x: Fraction, places: int) -> str:
    v = round(Fraction(x) * 10 ** places)
    neg = v < 0
    s = str(abs(v)).rjust(places + 1, "0")
    s = s if places == 0 else s[:-places] + "." + s[-places:]
    return ("-" if neg else "") + s


def places_of(text: str) -> int:
    text = text.strip()
    return len(text.split(".", 1)[1]) if "." in text else 0


class MiniYaml:
    """Block-style YAML subset: mappings, sequences, scalars, quoted strings and one-line flow mappings."""

    def __init__(self, text: str):
        self.lines = []
        for raw in text.split("\n"):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            self.lines.append((len(raw) - len(raw.lstrip(" ")), stripped))
        self.i = 0

    @staticmethod
    def scalar(s: str):
        s = s.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
            return s[1:-1]
        if s in ("null", "~", ""):
            return None
        if s.startswith("{") and s.endswith("}"):
            out = {}
            for part in s[1:-1].split(","):
                k, _, v = part.partition(":")
                out[k.strip()] = MiniYaml.scalar(v)
            return out
        return s

    def parse(self):
        if not self.lines:
            return None
        return self.block(self.lines[0][0])

    def block(self, indent: int):
        if self.lines[self.i][1].startswith("- ") or self.lines[self.i][1] == "-":
            return self.seq(indent)
        return self.mapping(indent)

    def seq(self, indent: int):
        out = []
        while self.i < len(self.lines):
            ind, text = self.lines[self.i]
            if ind != indent or not (text.startswith("- ") or text == "-"):
                break
            body = text[1:].strip()
            if re.match(r"^[^'\"{][^:]*:( |$)", body):
                self.lines[self.i] = (indent + 2, body)
                out.append(self.mapping(indent + 2))
            else:
                self.i += 1
                out.append(self.scalar(body))
        return out

    def mapping(self, indent: int):
        out = {}
        while self.i < len(self.lines):
            ind, text = self.lines[self.i]
            if ind != indent or text.startswith("- "):
                break
            key, _, rest = text.partition(":")
            self.i += 1
            key = key.strip().strip("'\"")
            if rest.strip():
                out[key] = self.scalar(rest)
            elif self.i < len(self.lines) and (self.lines[self.i][0] > indent or
                                               (self.lines[self.i][0] == indent and self.lines[self.i][1].startswith("- "))):
                out[key] = self.block(self.lines[self.i][0])
            else:
                out[key] = None
        return out


def load_yaml(path: Path):
    return MiniYaml(path.read_text(encoding="utf-8")).parse()


class Workbook:
    NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

    def __init__(self, path: Path):
        self.zip = zipfile.ZipFile(path)
        wb = ET.fromstring(self.zip.read("xl/workbook.xml"))
        pr = wb.find(self.NS + "workbookPr")
        self.date1904 = pr is not None and pr.get("date1904", "0").lower() in ("1", "true")
        rels = ET.fromstring(self.zip.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels}
        self.parts = {}
        for sh in wb.iter(self.NS + "sheet"):
            t = target[sh.get(self.RNS + "id")]
            self.parts[sh.get("name")] = "xl/" + t.lstrip("/").replace("xl/", "", 1) if not t.startswith("/xl/") else t[1:]
        self.shared = []
        if "xl/sharedStrings.xml" in self.zip.namelist():
            for si in ET.fromstring(self.zip.read("xl/sharedStrings.xml")).iter(self.NS + "si"):
                self.shared.append("".join(t.text or "" for t in si.iter(self.NS + "t")))

    def rows(self, name: str) -> list[dict]:
        root = ET.fromstring(self.zip.read(self.parts[name]))
        table = []
        for row in root.iter(self.NS + "row"):
            cells = {}
            for c in row.iter(self.NS + "c"):
                col = re.match(r"[A-Z]+", c.get("r")).group(0)
                idx = 0
                for ch in col:
                    idx = idx * 26 + ord(ch) - 64
                t = c.get("t")
                if t == "s":
                    val = self.shared[int(c.find(self.NS + "v").text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(self.NS + "t"))
                else:
                    v = c.find(self.NS + "v")
                    val = "" if v is None else (v.text or "")
                cells[idx - 1] = val.strip()
            table.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
        head = table[0]
        return [dict(zip(head, r + [""] * (len(head) - len(r)))) for r in table[1:] if any(r)]

    def day(self, serial: str) -> date:
        base = date(1904, 1, 1) if self.date1904 else date(1899, 12, 30)
        return base + timedelta(days=int(F(serial)))


class Memo:
    """Rebuild positioned text rows of the memo PDF and split them into labelled tables."""

    TOK = re.compile(r"\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|-?\d+(?:\.\d+)?|[A-Za-z]+")

    def __init__(self, path: Path):
        raw = path.read_bytes().decode("latin-1")
        self.lines = []
        for m in re.finditer(r"/Length (\d+)[^>]*/FlateDecode\s*>>\s*stream\r?\n", raw):
            body = zlib.decompress(raw[m.end():m.end() + int(m.group(1))].encode("latin-1")).decode("latin-1")
            rows: dict[float, list] = {}
            for obj in re.findall(r"(?m)^BT (.*) ET$", body):
                nums, x, y, parts, in_arr = [], 0.0, 0.0, [], False
                for t in self.TOK.findall(obj):
                    if t == "Tm":
                        x, y = nums[-2], nums[-1]
                    elif t == "[":
                        in_arr = True
                    elif t == "]":
                        in_arr = False
                    elif t[:1] == "(":
                        parts.append(re.sub(r"\\(.)", r"\1", t[1:-1]))
                    elif t[:1] == "<":
                        parts.append(bytes.fromhex(re.sub(r"\s", "", t[1:-1])).decode("latin-1"))
                    elif re.fullmatch(r"-?\d+(?:\.\d+)?", t) and not in_arr:
                        nums.append(float(t))
                rows.setdefault(y, []).append((x, "".join(parts)))
            for y in sorted(rows, reverse=True):
                self.lines.append([c.strip() for _, c in sorted(rows[y])])
        self.tables: dict[str, dict] = {}
        cur = None
        for cells in self.lines:
            if len(cells) == 1:
                m = re.fullmatch(r"Table ([A-Z]+-\d+): (.*) \((IN FORCE|WITHDRAWN)\)", cells[0])
                if m:
                    cur = {"label": m.group(1), "title": m.group(2), "status": m.group(3), "header": None, "rows": []}
                    self.tables[m.group(1)] = cur
                    continue
                m = re.fullmatch(r"Table ([A-Z]+-\d+) \(continued\)", cells[0])
                if m:
                    cur = self.tables.get(m.group(1))
                    if cur is not None:
                        cur["skip_header"] = True
                    continue
                if cells[0] == "":
                    cur = None
                continue
            if cur is None:
                continue
            if cur["header"] is None:
                cur["header"] = cells
            elif cur.get("skip_header") and cells == cur["header"]:
                cur["skip_header"] = False
            else:
                cur["rows"].append(dict(zip(cur["header"], cells)))

    def in_force(self, title: str) -> dict:
        for t in self.tables.values():
            if t["title"] == title and t["status"] == "IN FORCE":
                return t
        raise KeyError(title)


class Clock:
    def __init__(self, cal: dict):
        self.base = self.minutes(cal["base_offset"])
        self.trans = sorted((parse_instant(t["at_utc"]), self.minutes(t["offset_after"])) for t in cal.get("transitions") or [])

    @staticmethod
    def minutes(text: str) -> int:
        m = re.fullmatch(r"([+-])(\d\d):(\d\d)", text.strip())
        v = int(m.group(2)) * 60 + int(m.group(3))
        return v if m.group(1) == "+" else -v

    def offset_at(self, u: datetime) -> int:
        off = self.base
        for at, o in self.trans:
            if u >= at:
                off = o
        return off

    def offsets(self) -> list[int]:
        return sorted({self.base} | {o for _, o in self.trans})

    def wall(self, w: datetime) -> datetime:
        hits = [(w - timedelta(minutes=o)).replace(tzinfo=UTC) for o in self.offsets()]
        hits = [u for u, o in zip(hits, self.offsets()) if self.offset_at(u) == o]
        if hits:
            return min(hits)
        prev = self.base
        for at, o in self.trans:
            before = (w - timedelta(minutes=prev)).replace(tzinfo=UTC)
            after = (w - timedelta(minutes=o)).replace(tzinfo=UTC)
            if before >= at > after:
                return before
            prev = o
        raise ValueError(w)

    def with_dst(self, w: datetime, isdst: str) -> datetime:
        offs = self.offsets()
        o = offs[-1] if str(isdst).strip() == "1" else offs[0]
        return (w - timedelta(minutes=o)).replace(tzinfo=UTC)


def parse_instant(text: str) -> datetime:
    s = str(text).strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.astimezone(UTC).replace(microsecond=0)


def from_epoch(seconds: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)


def run_id(token) -> str | None:
    t = str(token).strip()
    if re.match(r"(?i)^KTC-2(6A|5C)/", t):
        return None
    m = re.search(r"(\d+)\s*$", t)
    return f"KTC-R{int(m.group(1)):02d}" if m else None


def serial_norm(token) -> str:
    t = re.sub(r"[\s_\-]", "", str(token).strip().upper())
    m = re.fullmatch(r"([A-Z]+)(\d+)", t)
    return f"{m.group(1)}-{m.group(2)}" if m else t


def channel_norm(token) -> str:
    t = str(token).strip()
    for pat in (r"(?i)^D(\d)C(\d+)$", r"(?i)^DAQ(\d)-(\d+)$", r"^(\d)/(\d+)$"):
        m = re.match(pat, t)
        if m:
            return f"D{m.group(1)}C{int(m.group(2)):02d}"
    m = re.match(r"(?i)^ch(\d+)@daq(\d)$", t)
    return f"D{m.group(2)}C{int(m.group(1)):02d}"


def link_norm(token) -> str:
    m = re.fullmatch(r"(?i)TL[\s-]*0*(\d+)", str(token).strip())
    return f"TL-{int(m.group(1)):03d}"


def read_delim(path: Path, sep: str) -> list[dict]:
    return [{k.strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")), delimiter=sep)]


def read_lines_json(path: Path) -> list:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]


class ShardReader:
    """Turn every reading layout into uniform records."""

    def __init__(self, clock: Clock):
        self.clock = clock

    def rec(self, run, token, kind, instant, raw, unit, rev, void):
        return {"run_tok": run, "token": token, "kind": kind, "t": instant, "raw": raw, "unit": unit, "rev": int(rev), "void": bool(void)}

    @staticmethod
    def missing(v, sentinels) -> str | None:
        if v is None:
            return None
        v = str(v).strip()
        return None if v == "" or v in sentinels else v

    def read(self, path: Path, layout: str) -> list[dict]:
        return getattr(self, "l" + layout[1:])(path)

    def l01(self, p):
        return [self.rec(r["run"], r["sensor"], "serial", parse_instant(r["ts_utc"]), self.missing(r["raw"], {"NaN"}), r["unit"], r["rev"], r["void"] == "Y")
                for r in read_delim(p, ",")]

    def l02(self, p):
        units = {"OHM": "ohm", "KOHM": "kohm", "VOLT": "V", "MVOLT": "mV"}
        return [self.rec(r["RUN"], r["SERIAL"], "serial", from_epoch(int(r["EPOCH_S"])), self.missing(r["VALUE"], {"-9999"}), units[r["UNITS"]],
                         r["REVISION"], r["STATUS"] == "VOID") for r in read_delim(p, "\t")]

    def l03(self, p):
        out = []
        for r in read_delim(p, "|"):
            w = datetime.strptime(r["local_time"], "%d/%m/%Y %H:%M:%S")
            out.append(self.rec(r["run_tag"], r["chan"], "channel", self.clock.with_dst(w, r["isdst"]), self.missing(r["reading"], {"OVL"}), "native",
                                r["rev"], r["flag"] == "x"))
        return out

    def l04(self, p):
        return [self.rec(d["r"], d["s"], "serial", from_epoch(int(d["t_ms"]) // 1000), self.missing(d["v"], set()), d["u"], d["rv"], d["del"] is True)
                for d in read_lines_json(p)]

    def l05(self, p):
        return [self.rec(d["meta"]["run"], d["sensor"], "serial", parse_instant(d["at"]), self.missing(d["value"]["x"], {"ERR"}), d["value"]["unit"],
                         d["meta"]["rev"], int(d["void"]) == 1) for d in read_lines_json(p)]

    def l06(self, p):
        out = []
        for b in ET.parse(p).getroot().iter("batch"):
            for r in b.iter("r"):
                out.append(self.rec(b.get("run"), r.get("s"), "serial", parse_instant(r.get("t")), self.missing(r.get("raw"), set()), r.get("u"),
                                    r.get("rev"), r.get("void") == "true"))
        return out

    def l07(self, p):
        con = sqlite3.connect(str(p))
        try:
            rows = con.execute("SELECT run, sensor, epoch, raw, unit, rev, voided FROM readings ORDER BY rowid").fetchall()
        finally:
            con.close()
        return [self.rec(a, b, "serial", from_epoch(int(c)), self.missing(d, set()), e, f, int(g) == 1) for a, b, c, d, e, f, g in rows]

    def l08(self, p):
        con = sqlite3.connect(str(p))
        try:
            rows = con.execute("SELECT f.run, s.channel, f.epoch_ms, s.micro, f.rev, f.void FROM samples s JOIN frames f ON f.frame_id = s.frame_id "
                               "ORDER BY s.rowid").fetchall()
        finally:
            con.close()
        return [self.rec(a, b, "channel", from_epoch(int(c) // 1000), None if d is None else str(d), "micro", e, int(f) == 1) for a, b, c, d, e, f in rows]

    def l09(self, p):
        return [self.rec(d["run"], d["sensor"], "serial", from_epoch(int(d["at"])), self.missing(d["raw"], set()), d["unit"], d["rev"], d["void"] == "yes")
                for d in load_yaml(p)]

    def l10(self, p):
        out = []
        for tok, blk in load_yaml(p).items():
            for line in blk["samples"]:
                run, t, raw, rev, void = [x.strip() for x in line.split("|")]
                out.append(self.rec(run, tok, "serial", parse_instant(t), self.missing(raw, {"-"}), blk["unit"], rev, void == "1"))
        return out

    def l11(self, p):
        doc = json.loads(p.read_text(encoding="utf-8"))
        d = doc["data"]
        return [self.rec(d["run"][i], d["sensor"][i], "serial", parse_instant(d["t"][i]), self.missing(d["raw"][i], set()), doc["units"][d["sensor"][i]],
                         d["rev"][i], d["void"][i] is True) for i in range(len(d["run"]))]

    def l12(self, p):
        out = []
        suffix = {"R": "ohm", "K": "kohm", "V": "V", "M": "mV"}
        for line in p.read_text(encoding="utf-8").split("\n"):
            if not line.strip() or line.startswith("#") or line.startswith("RUN "):
                continue
            run, sen, t, raw, rev, v = line[:10], line[10:21], line[21:38], line[38:53], line[53:57], line[57:].strip()
            raw = raw.strip()
            if raw == "*****":
                val, unit = None, "ohm"
            else:
                val, unit = raw[:-1], suffix[raw[-1]]
            out.append(self.rec(run.strip(), sen.strip(), "serial", datetime.strptime(t.strip(), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC), val, unit, rev, v == "Y"))
        return out

    def l13(self, p):
        out = []
        run = None
        for line in p.read_text(encoding="utf-8").split("\n"):
            if line.startswith("## Run "):
                run = line[7:].strip()
                continue
            if not line.startswith("|") or line.startswith("|---") or line.startswith("| sensor |"):
                continue
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            raw = None if c[2] == "n/a" else c[2].replace(",", "")
            out.append(self.rec(run, c[0], "serial", datetime.strptime(c[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC), raw, c[3], c[4], c[5] == "void"))
        return out

    def l14(self, p):
        out = []
        for r in read_delim(p, ";"):
            w = datetime.strptime(r["time_local"], "%Y-%m-%d %H:%M:%S")
            raw = self.missing(r["value"], set())
            out.append(self.rec(r["run"], r["probe"], "serial", self.clock.with_dst(w, r["isdst"]), None if raw is None else raw.replace(",", "."),
                                r["unit"], r["rev"], r["cancelled"] == "1"))
        return out

    def l15(self, p):
        return [self.rec(r["run"], r["ch"], "channel", from_epoch(int(r["epoch_ms"]) // 1000), self.missing(r["val"], {"NA"}), r["unit"], r["rev"],
                         r["void"] == "1") for r in read_delim(p, "\t")]

    def l16(self, p):
        out = []
        for d in read_lines_json(p):
            t0 = parse_instant(d["t0"])
            voids = set(d["void"])
            for i, (dt, v) in enumerate(zip(d["dt"], d["v"])):
                out.append(self.rec(d["run"], d["sensor"], "serial", t0 + timedelta(seconds=int(dt)), self.missing(v, set()), d["unit"], d["rev"], i in voids))
        return out


class Conductivity:
    """k(T) from tabulated points (T in mK) and its exact integral theta from 0 mK."""

    def __init__(self, pts: list[tuple[int, Fraction]]):
        self.T = [t for t, _ in pts]
        self.k = [k for _, k in pts]
        self.cum = [self.k[0] * self.T[0]]
        for i in range(1, len(self.T)):
            self.cum.append(self.cum[-1] + (self.k[i - 1] + self.k[i]) * (self.T[i] - self.T[i - 1]) / 2)

    def k_at(self, T: Fraction) -> Fraction:
        if T <= self.T[0]:
            return self.k[0]
        if T >= self.T[-1]:
            return self.k[-1]
        i = self.piece(T)
        return self.k[i] + (self.k[i + 1] - self.k[i]) * (T - self.T[i]) / (self.T[i + 1] - self.T[i])

    def piece(self, T) -> int:
        lo, hi = 0, len(self.T) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.T[mid] <= T:
                lo = mid
            else:
                hi = mid
        return lo

    def theta(self, T: Fraction) -> Fraction:
        if T <= self.T[0]:
            return self.k[0] * T
        if T >= self.T[-1]:
            return self.cum[-1] + self.k[-1] * (T - self.T[-1])
        i = self.piece(T)
        u = T - self.T[i]
        slope = (self.k[i + 1] - self.k[i]) / (self.T[i + 1] - self.T[i])
        return self.cum[i] + self.k[i] * u + slope * u * u / 2

    def inverse_round(self, y: Fraction) -> int | None:
        """Nearest whole mK (half-even) to the T with theta(T) = y; None when y < theta(0)."""
        if y < 0:
            return None
        lo, hi = 0, 1
        while self.theta(Fraction(hi)) <= y:
            lo, hi = hi, hi * 2
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.theta(Fraction(mid)) <= y:
                lo = mid
            else:
                hi = mid
        h = self.theta(Fraction(2 * lo + 1, 2))
        if y < h:
            return lo
        if y > h:
            return lo + 1
        return lo if lo % 2 == 0 else lo + 1


class Calibration:
    def __init__(self, family: str, pts: list[tuple[Fraction, Fraction]]):
        self.family = family
        self.pts = sorted(pts, key=lambda p: p[1])
        raws = [r for r, _ in self.pts]
        self.lo, self.hi = min(raws), max(raws)

    def space(self, raw: Fraction) -> Fraction:
        return 1 / raw if self.family == "NTC" else raw

    def temperature_mK(self, raw: Fraction) -> int | None:
        if raw < self.lo or raw > self.hi:
            return None
        x = self.space(raw)
        for (r0, t0), (r1, t1) in zip(self.pts, self.pts[1:]):
            x0, x1 = self.space(r0), self.space(r1)
            if min(x0, x1) <= x <= max(x0, x1):
                T = t0 if x1 == x0 else t0 + (t1 - t0) * (x - x0) / (x1 - x0)
                return half_even(T * 1000)
        return None


def native_unit(unit: str, family: str) -> Fraction:
    return {"ohm": Fraction(1), "kohm": Fraction(1000), "V": Fraction(1), "mV": Fraction(1, 1000), "micro": Fraction(1, 10 ** 6), "native": Fraction(1)}[unit]


def area_mm2(spec: str, awg: dict[int, Fraction]) -> Fraction:
    kind, _, body = spec.strip().partition(":")
    if kind == "A":
        if body.endswith("cm2"):
            return F(body[:-3]) * 100
        return F(body[:-3])
    if kind == "R":
        w, t = body[:-2].split("x")
        return F(w) * F(t)
    n, g = body[:-3].split("x")
    return int(n) * awg[int(g)]


class Corpus:
    """Every governing input of the campaign, loaded and resolved."""

    def __init__(self, data: Path):
        self.data = data
        self.catalog = json.loads(next(data.glob("ingest_catalog_*.json")).read_text(encoding="utf-8"))
        self.profile = load_yaml(next(data.glob("campaign_profile_*.yml")))
        self.clock = Clock(load_yaml(data / "site_calendar.yml"))
        self.calendar = load_yaml(data / "site_calendar.yml")
        self.memo = Memo(next(data.glob("governance_memo_*.pdf")))
        self.book = Workbook(next(data.glob("*.xlsx")))
        self.load_registers()
        self.load_settings()
        self.load_tables()
        self.load_runs()

    # ---------------------------------------------------------------- registers
    def load_registers(self) -> None:
        con = sqlite3.connect(str(self.data / "entity_alias_register.sqlite"))
        try:
            self.mat_alias = {}
            for tok, tgt, st in con.execute("SELECT token, target, status FROM material_alias ORDER BY rowid"):
                if str(st).strip().upper() == "ACTIVE":
                    self.mat_alias.setdefault(tok.strip().upper(), tgt.strip())
            self.node_alias = {t.strip().upper(): n.strip() for t, n in con.execute("SELECT token, node FROM node_alias")}
            self.link_alias = {link_norm(a): link_norm(b) for a, b, _ in con.execute("SELECT old_id, new_id, effective FROM link_alias")}
            self.relabel = {serial_norm(a): serial_norm(b) for a, b, _ in con.execute("SELECT old_serial, new_serial, effective_utc FROM sensor_relabel")}
        finally:
            con.close()
        con = sqlite3.connect(str(self.data / "channel_map_history.db"))
        try:
            self.channels: dict[str, list] = {}
            for ch, ser, a, b in con.execute("SELECT channel, serial, valid_from_utc, valid_to_utc FROM channel_assignment"):
                self.channels.setdefault(channel_norm(ch), []).append((parse_instant(a), parse_instant(b) if b else None, ser))
        finally:
            con.close()
        inv = json.loads((self.data / "sensor_inventory.json").read_text(encoding="utf-8"))
        self.inventory = {serial_norm(s["serial"]): s for s in inv["sensors"]}
        self.sensor_map: dict[str, list] = {}
        for a in load_yaml(next(self.data.glob("sensor_map_*.yaml")))["assignments"]:
            hist = [(parse_instant(h["from_utc"]), self.node(h["stage"])) for h in a["history"]]
            self.sensor_map[self.final_serial(a["serial"])] = sorted(hist, key=lambda x: x[0])

    def final_serial(self, token) -> str:
        s = serial_norm(token)
        seen = set()
        while s in self.relabel and s not in seen:
            seen.add(s)
            s = self.relabel[s]
        return s

    def final_link(self, token) -> str:
        s = link_norm(token)
        seen = set()
        while s in self.link_alias and s not in seen:
            seen.add(s)
            s = self.link_alias[s]
        return s

    def node(self, token) -> str:
        t = str(token).strip()
        if t.upper() in STAGES:
            return t.upper()
        if t.upper().startswith("IX-"):
            return t
        return self.node_alias.get(t.upper(), "UNRESOLVED")

    def material(self, token) -> str:
        t = str(token).strip()
        seen = set()
        while t.upper() not in self.k_codes:
            if t.upper() in seen or t.upper() not in self.mat_alias:
                return "UNRESOLVED"
            seen.add(t.upper())
            t = self.mat_alias[t.upper()]
        return t.upper()

    def channel_serial(self, ch: str, t: datetime) -> str | None:
        for a, b, ser in self.channels.get(ch, []):
            if a <= t and (b is None or t < b):
                return ser
        return None

    # ---------------------------------------------------------------- settings
    def load_settings(self) -> None:
        P = self.profile
        self.sheet_k, self.sheet_cal, self.sheet_cap = P["conductivity_sheet"], P["calibration_sheet"], P["capacity_sheet"]
        self.run_order = [r["id"] for r in P["runs"]]
        glob = {"spike_mK": int(P["spike_mK"]), "outlier_mK": int(P["outlier_mK"]), "min_readings": int(P["min_readings"]),
                "reserve_pct_ST50": int(P["reserve_pct"]["ST50"]), "reserve_pct_ST4": int(P["reserve_pct"]["ST4"])}
        self.overlay_applied = False
        overlay = None
        for p in sorted(self.data.glob("profile_overlay_*.yaml")):
            o = load_yaml(p)
            if str(o.get("base_revision")) == str(P["profile_revision"]):
                overlay = o
                self.overlay_applied = True
        self.settings: dict[str, dict] = {}
        self.cooler: dict[str, str] = {}
        for r in P["runs"]:
            s = dict(glob)
            for k in glob:
                if r.get(k) is not None:
                    s[k] = int(r[k])
            if overlay:
                o = (overlay.get("runs") or {}).get(r["id"]) or {}
                for k in overlay.get("overridable_keys") or []:
                    if o.get(k) is not None:
                        s[k] = int(o[k])
            self.settings[r["id"]] = s
            self.cooler[r["id"]] = r["cooler"]

    # ---------------------------------------------------------------- tables
    def load_tables(self) -> None:
        mats: dict[str, list] = {}
        for row in self.book.rows(self.sheet_k):
            k = F(row["k"]) * (Fraction(1, 10) if row["unit"] == "mW/cm-K" else 1)
            mats.setdefault(row["material"].strip().upper(), []).append((half_even(F(row["T_K"]) * 1000), k))
        self.k_codes = set(mats)
        self.cond = {m: Conductivity(sorted(p)) for m, p in mats.items()}
        self.cals: dict[str, list] = {}
        groups: dict[tuple, list] = {}
        for row in self.book.rows(self.sheet_cal):
            key = (serial_norm(row["serial"]), row["version"], row["valid_from"])
            groups.setdefault(key, []).append((F(row["raw"]) * native_unit(row["unit"], ""), F(row["T_K"])))
        for (ser, _ver, vf), pts in groups.items():
            self.cals.setdefault(ser, []).append((self.book.day(vf), pts))
        self.generic: dict[str, list] = {}
        for row in read_delim(self.data / "calibration_generic_curves.tsv", "\t"):
            self.generic.setdefault(row["curve"], []).append((F(row["raw"]) * native_unit(row["unit"], ""), F(row["T_K"])))
        self.cap: dict[tuple, list] = {}
        for row in self.book.rows(self.sheet_cap):
            self.cap.setdefault((row["model"], row["stage"]), []).append((half_even(F(row["T_K"]) * 1000), F(row["capacity_W"])))
        for v in self.cap.values():
            v.sort()
        M = self.memo
        self.t_joint = M.in_force("Joint base conductance per bolt, mW/K")
        self.t_par = M.in_force("Parasitic load by shield configuration, uW")
        self.t_solver = M.in_force("Solver contract constants")
        self.t_gauge = M.in_force("Conductor cross-section by gauge, mm2")
        self.t_limit = M.in_force("Stage temperature limits, mK")
        self.h_base = {(r["class"], r["band"]): F(r["h_mW_per_K"]) for r in self.t_joint["rows"]}
        self.h_text = {(r["class"], r["band"]): r["h_mW_per_K"] for r in self.t_joint["rows"]}
        self.parasitic = {(r["config"], r["stage"]): int(r["load_uW"]) for r in self.t_par["rows"]}
        self.solver = {r["constant"]: r["value"] for r in self.t_solver["rows"]}
        self.awg = {int(r["awg"]): F(r["area_mm2"]) for r in self.t_gauge["rows"]}
        self.awg_text = {int(r["awg"]): r["area_mm2"] for r in self.t_gauge["rows"]}
        self.limits = {r["stage"]: int(r["limit_mK"]) for r in self.t_limit["rows"]}
        lsm = self.solver["lot_scale_materials"].split()
        self.lot_materials = None if lsm == ["ALL"] else set(lsm)
        self.lots = {}
        for e in ET.parse(self.data / "material_lot_certs.xml").getroot().iter("lot"):
            self.lots[e.get("id")] = (F(e.get("k_scale")), e.get("status"))
        # rulings and addendum
        rul = {}
        for r in M.tables["R-1"]["rows"]:
            rul[r["ruling"]] = dict(r)
        add = sorted(((int(e.get("seq")), e) for e in ET.parse(self.data / "ruling_addendum.xml").getroot().iter("entry")), key=lambda x: x[0])
        for _, e in add:
            if e.get("status") != "ISSUED" or e.get("ref") not in rul:
                continue
            rul[e.get("ref")]["status"] = "RESCINDED" if e.get("action") == "RESCIND" else "IN FORCE"
        self.excl_sensor, self.offset, self.excl_link = set(), {}, set()
        for r in rul.values():
            if r["status"] != "IN FORCE":
                continue
            run = run_id(r["run"])
            if run is None:
                continue
            if r["action"] == "EXCLUDE_SENSOR":
                self.excl_sensor.add((run, self.final_serial(r["target"])))
            elif r["action"] == "OFFSET_SENSOR":
                key = (run, self.final_serial(r["target"]))
                self.offset[key] = self.offset.get(key, 0) + int(r["value"])
            elif r["action"] == "EXCLUDE_LINK":
                self.excl_link.add((run, self.final_link(r["target"])))
        # service log
        self.service = [(date.fromisoformat(r["date"]), i, r) for i, r in enumerate(read_delim(self.data / "cooler_service_log.tsv", "\t"))]

    # ---------------------------------------------------------------- runs
    def load_runs(self) -> None:
        eff: dict[tuple, tuple] = {}
        for r in read_delim(next(self.data.glob("run_log_*.csv")), ","):
            rid = run_id(r["run"])
            if rid is None or r["event"] == "NOTE":
                continue
            key = (rid, r["event"])
            if key not in eff or int(r["rev"]) >= eff[key][0]:
                eff[key] = (int(r["rev"]), r)
        self.runs: dict[str, dict] = {}
        for rid in self.run_order:
            def ev(name):
                x = eff.get((rid, name))
                return x[1] if x else None
            start, end = ev("PLATEAU_START"), ev("PLATEAU_END")
            ab = ev("ABORT")
            cfg = ev("CONFIG")
            self.runs[rid] = {
                "start": self.clock.wall(datetime.strptime(start["local_time"], "%Y-%m-%d %H:%M")) if start else None,
                "end": self.clock.wall(datetime.strptime(end["local_time"], "%Y-%m-%d %H:%M")) if end else None,
                "aborted": bool(ab and ab["value"] == "ACTIVE"),
                "shield": cfg["value"] if cfg else None,
            }
        self.active = [r for r in self.run_order if not self.runs[r]["aborted"]]

    def stage_of(self, serial: str, t: datetime) -> str | None:
        st = None
        for at, node in self.sensor_map.get(serial, []):
            if at <= t:
                st = node
        return st

    def calibration_for(self, serial: str, t: datetime) -> Calibration | None:
        inv = self.inventory[serial]
        vers = [(vf, pts) for vf, pts in self.cals.get(serial, []) if vf <= t.date()]
        if vers:
            return Calibration(inv["family"], max(vers, key=lambda v: v[0])[1])
        if inv.get("cal_policy") == "GENERIC_OK" and inv.get("generic_curve") in self.generic:
            return Calibration(inv["family"], self.generic[inv["generic_curve"]])
        return None


class Budget:
    REASONS = ("UNMAPPED_CHANNEL", "UNKNOWN_SENSOR", "INVALID_VALUE", "OUT_OF_WINDOW", "MAINTENANCE", "EXCLUDED_SENSOR", "NO_CALIBRATION",
               "OUT_OF_RANGE", "SPIKE")

    def __init__(self, c: Corpus):
        self.c = c
        self.calcache: dict = {}
        self.excl: dict[tuple, int] = {}
        self.ingest()
        self.sensors()
        self.stages()
        self.link_setup()
        self.solve_intercepts()
        self.solve_links()
        self.loads()

    # ---------------------------------------------------------------- readings
    def ingest(self) -> None:
        c = self.c
        reader = ShardReader(c.clock)
        shards = sorted((s for s in c.catalog["shards"] if s["kind"] == "readings" and s["status"] == "ACTIVE"), key=lambda s: s["order"])
        self.lineage = []
        best: dict[tuple, tuple] = {}
        self.records_read = self.unresolved = self.resolved = 0
        self.serial_tokens: set[str] = set()
        for pos, sh in enumerate(shards):
            recs = reader.read(c.data / sh["file"], sh["layout"])
            info = {"file": sh["file"], "layout": sh["layout"], "records": len(recs), "resolved": 0, "winning": 0}
            self.lineage.append(info)
            for line, r in enumerate(recs):
                self.records_read += 1
                if r["kind"] == "channel":
                    ch = channel_norm(r["token"])
                    ser = c.channel_serial(ch, r["t"])
                    if ser is None:
                        self.unresolved += 1
                        self.count(run_id(r["run_tok"]), ch, "UNMAPPED_CHANNEL")
                        continue
                    final = c.final_serial(ser)
                else:
                    norm = serial_norm(r["token"])
                    self.serial_tokens.add(norm)
                    final = c.final_serial(norm)
                if final not in c.inventory:
                    self.unresolved += 1
                    self.count(run_id(r["run_tok"]), final, "UNKNOWN_SENSOR")
                    continue
                info["resolved"] += 1
                self.resolved += 1
                key = (final, r["t"])
                rank = (r["rev"], pos, line)
                if key not in best or rank > best[key][0]:
                    best[key] = (rank, r, info)
        self.keys = len(best)
        self.voided = 0
        self.readings: dict[tuple, list] = {}
        self.out_of_scope = 0
        for (final, t), (rank, r, info) in best.items():
            if r["void"]:
                self.voided += 1
                continue
            info["winning"] += 1
            run = run_id(r["run_tok"])
            if run is None or run not in c.runs or c.runs[run]["aborted"]:
                self.out_of_scope += 1
                continue
            self.readings.setdefault((run, final), []).append((t, r))

    def count(self, run, serial, reason, n=1) -> None:
        if run is None or run not in self.c.runs or self.c.runs[run]["aborted"]:
            return
        key = (run, serial, reason)
        self.excl[key] = self.excl.get(key, 0) + n

    def calibration(self, serial: str, t: datetime):
        c = self.c
        vers = [vf for vf, _ in c.cals.get(serial, []) if vf <= t.date()]
        key = (serial, max(vers) if vers else None)
        if key not in self.calcache:
            self.calcache[key] = c.calibration_for(serial, t)
        return self.calcache[key]

    def sensors(self) -> None:
        c = self.c
        maint = []
        for m in c.calendar.get("maintenance") or []:
            maint.append((parse_instant(m["start_utc"]), parse_instant(m["end_utc"]), c.node(m["scope"]) if m["scope"] != "ALL" else "ALL"))
        self.means: dict[tuple, dict] = {}
        for (run, serial), recs in sorted(self.readings.items()):
            R = c.runs[run]
            stage = c.stage_of(serial, R["start"])
            if stage not in STAGES:
                continue
            fam = c.inventory[serial]["family"]
            window = []
            for t, r in sorted(recs, key=lambda x: x[0]):
                if r["raw"] is None:
                    self.count(run, serial, "INVALID_VALUE")
                    continue
                if not (R["start"] <= t < R["end"]):
                    self.count(run, serial, "OUT_OF_WINDOW")
                    continue
                if any(a <= t < b and sc in ("ALL", stage) for a, b, sc in maint):
                    self.count(run, serial, "MAINTENANCE")
                    continue
                if (run, serial) in c.excl_sensor:
                    self.count(run, serial, "EXCLUDED_SENSOR")
                    continue
                cal = self.calibration(serial, t)
                if cal is None:
                    self.count(run, serial, "NO_CALIBRATION")
                    continue
                unit = r["unit"]
                if unit == "native":
                    unit = "V" if fam == "DIODE" else "ohm"
                raw = F(r["raw"]) * native_unit(unit, fam)
                mk = cal.temperature_mK(raw)
                if mk is None:
                    self.count(run, serial, "OUT_OF_RANGE")
                    continue
                window.append(mk + c.offset.get((run, serial), 0))
            st = c.settings[run]
            kept = []
            if window:
                v = sorted(window)
                n = len(v)
                med = Fraction(v[n // 2]) if n % 2 else Fraction(v[n // 2 - 1] + v[n // 2], 2)
                kept = [x for x in window if abs(x - med) <= st["spike_mK"]]
                if len(window) - len(kept):
                    self.count(run, serial, "SPIKE", len(window) - len(kept))
            if len(kept) >= st["min_readings"] and kept:
                status, mean = "OK", half_even(Fraction(sum(kept), len(kept)))
            else:
                status, mean = ("SPARSE" if kept else "NO_READINGS"), None
            self.means[(run, serial)] = {"stage": stage, "window": len(window), "spikes": len(window) - len(kept), "used": len(kept), "mean": mean,
                                         "status": status}

    def stages(self) -> None:
        self.stage_T: dict[tuple, dict] = {}
        for run in self.c.active:
            for stage in STAGES:
                ms = sorted((s, m["mean"]) for (r, s), m in self.means.items() if r == run and m["stage"] == stage and m["mean"] is not None)
                if not ms:
                    self.stage_T[(run, stage)] = {"used": [], "dropped": [], "T": None}
                    continue
                v = sorted(m for _, m in ms)
                n = len(v)
                med = Fraction(v[n // 2]) if n % 2 else Fraction(v[n // 2 - 1] + v[n // 2], 2)
                lim = self.c.settings[run]["outlier_mK"]
                used = [(s, m) for s, m in ms if abs(m - med) <= lim]
                dropped = [s for s, m in ms if abs(m - med) > lim]
                self.stage_T[(run, stage)] = {"used": [s for s, _ in used], "dropped": dropped,
                                              "T": half_even(Fraction(sum(m for _, m in used), len(used)))}

    # ---------------------------------------------------------------- links
    def link_setup(self) -> None:
        c = self.c
        d = c.data
        self.catalog_rows: dict[str, list] = {}
        self.link_tokens: set[str] = set()
        for r in read_delim(d / "lk_9tc1.csv", ","):
            self.link_tokens.add(r["link"].strip())
            self.catalog_rows.setdefault(c.final_link(r["link"]), []).append((date.fromisoformat(r["effective_from"]), int(r["rev"]), r["status"]))
        self.segs: dict[tuple, dict] = {}
        self.mat_tokens: set[str] = set()
        for le in ET.parse(d / "lk_4sg7.xml").getroot().iter("link"):
            self.link_tokens.add(le.get("id").strip())
            lid = c.final_link(le.get("id"))
            for sg in le.iter("seg"):
                self.mat_tokens.add(sg.get("mat").strip())
                self.segs.setdefault((lid, int(le.get("rev"))), {})[int(sg.get("n"))] = {
                    "material": sg.get("mat"), "length": F(sg.get("len")[:-2]), "area": sg.get("area"), "lot": sg.get("lot") or ""}
        for r in read_delim(d / "lk_2sg8.psv", "|"):
            self.link_tokens.add(r["link"])
            self.mat_tokens.add(r["material"])
            mul = {"mm": 1, "cm": 10, "in": Fraction(254, 10)}[r["length_unit"]]
            self.segs.setdefault((c.final_link(r["link"]), int(r["rev"])), {})[int(r["seq"])] = {
                "material": r["material"], "length": F(r["length"]) * mul, "area": r["area_spec"], "lot": "" if r["lot"] == "-" else r["lot"]}
        self.joints: dict[tuple, dict] = {}
        for j in read_lines_json(d / "lk_6jt3.jsonl"):
            self.link_tokens.add(str(j["link"]).strip())
            ind = j["indium"]
            ind = ind if isinstance(ind, bool) else str(ind).lower() in ("yes", "true")
            self.joints.setdefault((c.final_link(j["link"]), int(j["rev"])), {})[int(j["pos"])] = {
                "class": j["class"], "bolts": int(j["bolts"]), "torque": str(j["torque"]).upper(), "indium": ind}
        # amendments
        ents = read_lines_json(d / "lk_3am0.ndjson")
        for e in ents:
            self.link_tokens.add(str(e["link"]).strip())
        cancelled, self.in_effect = set(), {}
        for e in sorted(ents, key=lambda e: -int(e["seq"])):
            ok = str(e["status"]).upper() == "POSTED" and int(e["seq"]) not in cancelled
            self.in_effect[int(e["seq"])] = ok
            if ok and str(e["action"]).upper() == "REVERSE":
                cancelled.add(int(e["reverses"]))
        self.amend_rows = []
        self.amend_value: dict[tuple, str] = {}
        for e in sorted(ents, key=lambda e: int(e["seq"])):
            lid = c.final_link(e["link"])
            act = str(e["action"]).upper()
            self.amend_rows.append([str(e["seq"]), lid, str(e["rev"]), e["field"], act, str(e["status"]).upper(), "Y" if self.in_effect[int(e["seq"])] else "N"])
            if act == "SET" and self.in_effect[int(e["seq"])]:
                self.amend_value[(lid, int(e["rev"]), e["field"])] = e["value"]
        # installs
        latest: dict[tuple, tuple] = {}
        self.node_tokens: set[str] = set()
        for r in read_delim(d / "lk_8in5.tsv", "\t"):
            self.link_tokens.add(r["link"])
            self.node_tokens.update([r["hot"], r["cold"]])
            run = run_id(r["run"])
            key = (run, c.final_link(r["link"]))
            if key not in latest or int(r["rev"]) >= latest[key][0]:
                latest[key] = (int(r["rev"]), r)
        self.installed: dict[str, list] = {}
        for (run, lid), (_, r) in latest.items():
            if run in c.runs and not c.runs[run]["aborted"] and r["state"] == "INSTALLED":
                self.installed.setdefault(run, []).append((lid, c.node(r["hot"]), c.node(r["cold"])))
        for v in self.installed.values():
            v.sort()
        for a in load_yaml(next(d.glob("sensor_map_*.yaml")))["assignments"]:
            for h in a["history"]:
                self.node_tokens.add(str(h["stage"]).strip())
        # intercept register and harness
        root = ET.parse(d / "intercept_register.xml").getroot()
        self.ix_band: dict[tuple, str] = {}
        for x in root.iter("intercept"):
            self.ix_band[(run_id(x.get("run")), x.get("id"))] = x.get("band")
        bnode = {}
        for b in root.iter("bundle"):
            self.node_tokens.add(b.get("node").strip())
            bnode[(b.get("id"), run_id(b.get("run")))] = c.node(b.get("node"))
        hb: dict[str, tuple] = {}
        for r in read_delim(d / "harness_dissipation.psv", "|"):
            if r["bundle"] not in hb or int(r["rev"]) >= hb[r["bundle"]][0]:
                hb[r["bundle"]] = (int(r["rev"]), r)
        self.harness: dict[tuple, int] = {}
        for bid, (_, r) in hb.items():
            if r["void"] == "VOID":
                continue
            run = run_id(r["run"])
            uw = F(r["dissipation"]) * (1000 if r["unit"] == "mW" else 1)
            node = bnode.get((bid, run))
            if node is None:
                continue
            self.harness[(run, node)] = self.harness.get((run, node), 0) + int(uw)
        # per-run link definitions
        S = c.solver
        inc = F(S["h_increment_mW_per_K"])
        self.defs: dict[tuple, dict] = {}
        for run, rows in self.installed.items():
            day = c.runs[run]["start"].date()
            for lid, hot, cold in rows:
                dfn = {"hot": hot, "cold": cold, "rev": None, "elements": [], "segments": [], "joints": [], "status": None}
                self.defs[(run, lid)] = dfn
                cands = [x for x in self.catalog_rows.get(lid, []) if x[0] <= day]
                if not cands:
                    dfn["status"] = "NO_GEOMETRY"
                    continue
                eff, rev, status = max(cands, key=lambda x: (x[0], x[1]))
                dfn["rev"] = rev
                if status == "VOID":
                    dfn["status"] = "NO_GEOMETRY"
                    continue
                if (run, lid) in c.excl_link:
                    dfn["status"] = "EXCLUDED"
                    continue
                band = "W" if cold == "ST50" else "C" if cold == "ST4" else self.ix_band.get((run, cold))
                segs = self.segs.get((lid, rev), {})
                jts = self.joints.get((lid, rev), {})
                n = len(segs)

                def amend(field, value):
                    return self.amend_value.get((lid, rev, field), value)

                for pos in range(0, n + 1):
                    if pos in jts:
                        j = dict(jts[pos])
                        j["bolts"] = int(amend(f"joint{pos}.bolts", j["bolts"]))
                        j["torque"] = str(amend(f"joint{pos}.torque", j["torque"])).upper()
                        iv = amend(f"joint{pos}.indium", j["indium"])
                        j["indium"] = iv if isinstance(iv, bool) else str(iv).lower() in ("yes", "true", "y")
                        h = c.h_base[(j["class"], band)] * j["bolts"]
                        if j["torque"] == "LOW":
                            h *= F(S["low_torque_factor"])
                        if j["indium"] and j["class"].startswith("BOLT_"):
                            h *= F(S["indium_factor"])
                        heff = half_even(h / inc) * inc
                        jr = {"pos": pos, "class": j["class"], "band": band, "bolts": j["bolts"], "torque": j["torque"], "indium": j["indium"],
                              "base": c.h_base[(j["class"], band)], "h": heff}
                        dfn["joints"].append(jr)
                        dfn["elements"].append(("joint", jr))
                    if pos + 1 <= n:
                        sg = segs[pos + 1]
                        mat = c.material(amend(f"seg{pos + 1}.material", sg["material"]))
                        L = F(amend(f"seg{pos + 1}.length_mm", sg["length"]))
                        A = area_mm2(amend(f"seg{pos + 1}.area", sg["area"]), c.awg)
                        lot = sg["lot"]
                        scale = Fraction(1)
                        if lot and lot in c.lots and c.lots[lot][1] == "CERTIFIED" and (c.lot_materials is None or mat in c.lot_materials):
                            scale = c.lots[lot][0]
                        sr = {"seq": pos + 1, "material": mat, "length": L, "area": A, "lot": lot, "scale": scale, "g": A / L}
                        dfn["segments"].append(sr)
                        dfn["elements"].append(("segment", sr))
                dfn["status"] = "READY"

    def march(self, dfn: dict, t_hot: int, q: int) -> list[int] | None:
        T = t_hot
        temps = []
        for kind, e in dfn["elements"]:
            if kind == "joint":
                T = T - half_even(Fraction(q) / e["h"])
                if T < 0:
                    return None
            else:
                cond = self.c.cond[e["material"]]
                y = cond.theta(Fraction(T)) - Fraction(q) / (e["scale"] * e["g"])
                T = cond.inverse_round(y)
                if T is None or T < 0:
                    return None
            temps.append(T)
        return temps

    def q_of(self, dfn: dict, t_hot: int, t_cold: int) -> tuple[int, list[int]]:
        key = (id(dfn), t_hot, t_cold)
        if key in self.qcache:
            return self.qcache[key]
        if t_hot <= t_cold:
            res = (0, [t_hot] * len(dfn["elements"]))
        else:
            def ok(q):
                m = self.march(dfn, t_hot, q)
                return m is not None and (m[-1] if m else t_hot) >= t_cold
            lo, hi = 0, 1
            while ok(hi):
                lo, hi = hi, hi * 2
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if ok(mid):
                    lo = mid
                else:
                    hi = mid
            res = (lo, self.march(dfn, t_hot, lo))
        self.qcache[key] = res
        return res

    def solve_intercepts(self) -> None:
        self.qcache = {}
        self.ix: dict[tuple, dict] = {}
        for run in self.c.active:
            nodes = sorted({n for (r, lid), d in self.defs.items() if r == run for n in (d["hot"], d["cold"]) if n.startswith("IX")})
            for x in nodes:
                ins = sorted(lid for (r, lid), d in self.defs.items() if r == run and d["cold"] == x and d["status"] == "READY")
                outs = sorted(lid for (r, lid), d in self.defs.items() if r == run and d["hot"] == x and d["status"] == "READY")
                hots = [self.stage_T.get((run, self.defs[(run, l)]["hot"]), {}).get("T") for l in ins]
                colds = [self.stage_T.get((run, self.defs[(run, l)]["cold"]), {}).get("T") for l in outs]
                P = self.harness.get((run, x), 0)
                rec = {"band": self.ix_band.get((run, x)), "ins": ins, "outs": outs, "harness": P}
                self.ix[(run, x)] = rec
                if any(t is None for t in hots + colds) or not hots or not colds:
                    rec.update({"status": "UNSOLVED", "T": None, "lo": None, "hi": None, "res": None, "next": None})
                    continue
                lo_t, hi_t = max(colds), min(hots)

                def f(T):
                    s = P
                    for l in ins:
                        d = self.defs[(run, l)]
                        s += self.q_of(d, self.stage_T[(run, d["hot"])]["T"], T)[0]
                    for l in outs:
                        d = self.defs[(run, l)]
                        s -= self.q_of(d, T, self.stage_T[(run, d["cold"])]["T"])[0]
                    return s

                if f(hi_t) >= 0:
                    T, status = hi_t, "CEILING"
                elif f(lo_t) < 0:
                    T, status = lo_t, "FLOOR"
                else:
                    a, b = lo_t, hi_t
                    while b - a > 1:
                        mid = (a + b) // 2
                        if f(mid) >= 0:
                            a = mid
                        else:
                            b = mid
                    T, status = a, "BALANCED"
                rec.update({"status": status, "T": T, "lo": lo_t, "hi": hi_t, "res": f(T), "next": None if T >= hi_t else f(T + 1)})

    def node_T(self, run: str, node: str):
        if node.startswith("IX"):
            r = self.ix.get((run, node))
            return r["T"] if r else None
        return self.stage_T.get((run, node), {}).get("T")

    def solve_links(self) -> None:
        self.flows: dict[tuple, dict] = {}
        for (run, lid), d in sorted(self.defs.items()):
            th, tc = self.node_T(run, d["hot"]), self.node_T(run, d["cold"])
            row = {"rev": d["rev"], "hot": d["hot"], "cold": d["cold"], "th": th, "tc": tc, "q": None, "temps": None}
            if d["status"] != "READY":
                row["status"] = d["status"]
            elif th is None or tc is None:
                row["status"] = "UNSOLVED"
            else:
                q, temps = self.q_of(d, th, tc)
                row.update({"q": q, "temps": temps, "status": "NO_GRADIENT" if th <= tc else "OK"})
            self.flows[(run, lid)] = row

    # ---------------------------------------------------------------- loads and margins
    def loads(self) -> None:
        c = self.c
        self.load: dict[tuple, dict] = {}
        self.margin: dict[tuple, dict] = {}
        self.verdict: dict[str, dict] = {}
        sev = {"PASS": 0, "MARGINAL": 1, "OVERLOAD": 2, "OVER_TEMP": 3}
        for run in c.run_order:
            if c.runs[run]["aborted"]:
                self.verdict[run] = {"verdict": "ABORTED", "ST50": None, "ST4": None, "unsolved": 0}
                continue
            unsolved = sum(1 for (r, _), f in self.flows.items() if r == run and f["status"] == "UNSOLVED")
            stage_v = {}
            for st in COOLED:
                rows = [f for (r, _), f in self.flows.items() if r == run and f["cold"] == st]
                inc = any(f["status"] == "UNSOLVED" for f in rows)
                links = None if inc else sum(f["q"] or 0 for f in rows)
                harn = self.harness.get((run, st), 0)
                par = c.parasitic[(c.runs[run]["shield"], st)]
                total = None if links is None else links + harn + par
                self.load[(run, st)] = {"links": links, "harness": harn, "par": par, "total": total, "status": "INCOMPLETE" if inc else "OK"}
                T = self.stage_T[(run, st)]["T"]
                cooler = c.cooler[run]
                model = {"CC-0417": "GM-K15", "CC-0522": "PT-K41"}[cooler]
                day = c.runs[run]["start"].date()
                der = Fraction(0)
                for dd, _, e in sorted(c.service, key=lambda x: (x[0], x[1])):
                    if e["cooler"] == cooler and dd <= day and e["action"] in ("DERATE", "RESTORE"):
                        der = F(e["value"]) if e["action"] == "DERATE" else Fraction(0)
                m = {"cooler": cooler, "model": model, "T": T, "derate": der, "rpct": c.settings[run][f"reserve_pct_{st}"]}
                if T is None or total is None:
                    m.update({"cap": None, "map": "", "reserve": None, "margin": None, "verdict": "INCOMPLETE", "load": total})
                    if T is not None:
                        cap, mp = self.capacity(model, st, T, der)
                        m.update({"cap": cap, "map": mp, "reserve": half_even(Fraction(cap * m["rpct"], 100))})
                else:
                    cap, mp = self.capacity(model, st, T, der)
                    reserve = half_even(Fraction(cap * m["rpct"], 100))
                    margin = cap - total
                    if T > c.limits[st]:
                        v = "OVER_TEMP"
                    elif margin < 0:
                        v = "OVERLOAD"
                    elif margin < reserve:
                        v = "MARGINAL"
                    else:
                        v = "PASS"
                    m.update({"cap": cap, "map": mp, "reserve": reserve, "margin": margin, "verdict": v, "load": total})
                self.margin[(run, st)] = m
                stage_v[st] = m["verdict"]
            no_sensor = any(self.stage_T[(run, s)]["T"] is None for s in STAGES)
            if unsolved or no_sensor or "INCOMPLETE" in stage_v.values():
                v = "INCOMPLETE"
            else:
                v = max(stage_v.values(), key=lambda x: sev[x])
            self.verdict[run] = {"verdict": v, "ST50": stage_v["ST50"], "ST4": stage_v["ST4"], "unsolved": unsolved}

    def capacity(self, model: str, st: str, T: int, der: Fraction) -> tuple[int, str]:
        pts = self.c.cap[(model, st)]
        if T < pts[0][0]:
            w, mp = pts[0][1], "OUT_OF_MAP"
        elif T > pts[-1][0]:
            w, mp = pts[-1][1], "OUT_OF_MAP"
        else:
            mp = "IN_MAP"
            w = pts[-1][1]
            for (t0, c0), (t1, c1) in zip(pts, pts[1:]):
                if t0 <= T <= t1:
                    w = c0 + (c1 - c0) * (T - t0) / (t1 - t0)
                    break
        return half_even(w * 1000000 * (100 - der) / 100), mp


REPORTS = ["sensor_means.tsv", "stage_temperatures.csv", "intercept_solutions.json", "link_heat_flows.psv", "junction_profiles.jsonl",
           "link_geometry.csv", "joint_conductances.tsv", "stage_loads.csv", "cooler_margins.xml", "run_verdicts.json", "alias_resolution.csv",
           "reading_exclusions.jsonl", "dedup_report.json", "source_lineage.json", "amendment_ledger.csv", "parameters_used.yaml",
           "authority_audit.csv", "variance_vs_published.csv", "reconciliation.md", "budget_summary.md"]


def table(header: list[str], rows: list[list], sep: str) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=sep, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return buf.getvalue()


def jdump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


class Reports:
    def __init__(self, b: Budget):
        self.b = b
        self.c = b.c
        self.ri = {r: i for i, r in enumerate(self.c.run_order)}
        self.si = {s: i for i, s in enumerate(STAGES)}

    def render(self) -> dict[str, str]:
        out = {}
        for name in REPORTS:
            out[name] = getattr(self, "r_" + name.split(".")[0])()
        return out

    def r_sensor_means(self):
        rows = []
        for (run, ser), m in sorted(self.b.means.items(), key=lambda kv: (self.ri[kv[0][0]], self.si[kv[1]["stage"]], kv[0][1])):
            rows.append([run, ser, m["stage"], m["window"], m["spikes"], m["used"], m["mean"], m["status"]])
        return table(["run", "serial", "stage", "window_readings", "spikes_dropped", "used_readings", "mean_mK", "status"], rows, "\t")

    def r_stage_temperatures(self):
        rows = []
        for run in self.c.active:
            for st in STAGES:
                s = self.b.stage_T[(run, st)]
                rows.append([run, st, ";".join(sorted(s["used"])), ";".join(sorted(s["dropped"])), s["T"], "OK" if s["T"] is not None else "NO_SENSORS"])
        return table(["run", "stage", "sensors_used", "sensors_dropped", "temperature_mK", "status"], rows, ",")

    def r_intercept_solutions(self):
        lst = []
        for (run, x), r in sorted(self.b.ix.items(), key=lambda kv: (self.ri[kv[0][0]], kv[0][1])):
            lst.append({"run": run, "node": x, "band": r["band"], "t_lo_mK": r["lo"], "t_hi_mK": r["hi"], "temperature_mK": r["T"], "harness_uW": r["harness"],
                        "residual_uW": r["res"], "next_residual_uW": r["next"], "links_in": r["ins"], "links_out": r["outs"], "status": r["status"]})
        return jdump({"count": len(lst), "intercepts": lst})

    def flow_items(self):
        return sorted(self.b.flows.items(), key=lambda kv: (self.ri[kv[0][0]], kv[0][1]))

    def r_link_heat_flows(self):
        rows = [[run, lid, f["rev"], f["hot"], f["cold"], f["th"], f["tc"], f["q"], f["status"]] for (run, lid), f in self.flow_items()]
        return table(["run", "link", "rev", "hot_node", "cold_node", "hot_mK", "cold_mK", "q_uW", "status"], rows, "|")

    def r_junction_profiles(self):
        lines = []
        for (run, lid), f in self.flow_items():
            if f["status"] not in ("OK", "NO_GRADIENT"):
                continue
            els = []
            for (kind, e), t in zip(self.b.defs[(run, lid)]["elements"], f["temps"]):
                els.append({"kind": kind, "pos": e["pos"], "t_mK": t} if kind == "joint" else {"kind": kind, "seq": e["seq"], "t_mK": t})
            lines.append(json.dumps({"run": run, "link": lid, "q_uW": f["q"], "elements": els}, sort_keys=True))
        return "".join(x + "\n" for x in lines)

    def geo_items(self):
        return [(k, f) for k, f in self.flow_items() if f["status"] in ("OK", "NO_GRADIENT", "UNSOLVED")]

    def r_link_geometry(self):
        rows = []
        for (run, lid), f in self.geo_items():
            for s in self.b.defs[(run, lid)]["segments"]:
                rows.append([run, lid, f["rev"], s["seq"], s["material"], plain(s["length"]), plain(s["area"]), s["lot"], plain(s["scale"]), fixed(s["g"], 9)])
        return table(["run", "link", "rev", "seq", "material", "length_mm", "area_mm2", "lot", "lot_scale", "g_mm"], rows, ",")

    def r_joint_conductances(self):
        rows = []
        for (run, lid), f in self.geo_items():
            for j in self.b.defs[(run, lid)]["joints"]:
                rows.append([run, lid, j["pos"], j["class"], j["band"], j["bolts"], j["torque"], "Y" if j["indium"] else "N", plain(j["base"]), plain(j["h"])])
        return table(["run", "link", "pos", "class", "band", "bolts", "torque", "indium", "h_base_mW_per_K", "h_eff_mW_per_K"], rows, "\t")

    def r_stage_loads(self):
        rows = []
        for run in self.c.active:
            for st in COOLED:
                L = self.b.load[(run, st)]
                rows.append([run, st, L["links"], L["harness"], L["par"], L["total"], L["status"]])
        return table(["run", "stage", "links_uW", "harness_uW", "parasitic_uW", "total_uW", "status"], rows, ",")

    def r_cooler_margins(self):
        out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<margins campaign="{self.c.profile["campaign"]}">']
        for run in self.c.active:
            for st in COOLED:
                m = self.b.margin[(run, st)]
                vals = [("run", run), ("name", st), ("cooler", m["cooler"]), ("model", m["model"]), ("temperature_mK", m["T"]), ("derate_pct", plain(m["derate"])),
                        ("capacity_uW", m["cap"]), ("map_status", m["map"]), ("load_uW", m["load"]), ("reserve_pct", m["rpct"]), ("reserve_uW", m["reserve"]),
                        ("margin_uW", m["margin"]), ("verdict", m["verdict"])]
                out.append("  <stage " + " ".join(f'{k}="{"" if v is None else v}"' for k, v in vals) + "/>")
        out.append("</margins>")
        return "\n".join(out) + "\n"

    def r_run_verdicts(self):
        runs, summ = [], {}
        for run in self.c.run_order:
            v = self.b.verdict[run]
            runs.append({"run": run, "verdict": v["verdict"], "ST50": v["ST50"], "ST4": v["ST4"], "unsolved_links": v["unsolved"]})
            summ[v["verdict"]] = summ.get(v["verdict"], 0) + 1
        return jdump({"campaign": self.c.profile["campaign"], "runs": runs, "summary": summ})

    def r_alias_resolution(self):
        c = self.c
        rows = []
        for t in self.b.mat_tokens:
            rows.append(["material", t, c.material(t)])
        for t in self.b.node_tokens:
            rows.append(["node", t, c.node(t)])
        for t in self.b.link_tokens:
            rows.append(["link", t, c.final_link(t)])
        for t in self.b.serial_tokens:
            f = c.final_serial(t)
            rows.append(["sensor", t, f if f in c.inventory else "UNRESOLVED"])
        rows = sorted({tuple(r) for r in rows})
        return table(["kind", "token", "resolved"], [list(r) for r in rows], ",")

    def r_reading_exclusions(self):
        lines = []
        for (run, ser, reason), n in sorted(self.b.excl.items(), key=lambda kv: (self.ri[kv[0][0]], kv[0][1], kv[0][2])):
            if n:
                lines.append(json.dumps({"count": n, "reason": reason, "run": run, "serial": ser}, sort_keys=True))
        return "".join(x + "\n" for x in lines)

    def r_dedup_report(self):
        b = self.b
        return jdump({"records_read": b.records_read, "unresolved": b.unresolved, "copies_superseded": b.resolved - b.keys, "voided_keys": b.voided,
                      "unique_readings": b.keys - b.voided, "out_of_scope_readings": b.out_of_scope})

    def r_source_lineage(self):
        return jdump({"shards": self.b.lineage})

    def r_amendment_ledger(self):
        return table(["seq", "link", "rev", "field", "action", "status", "in_effect"], self.b.amend_rows, ",")

    def r_parameters_used(self):
        c = self.c
        S = c.solver
        lines = [f"campaign: {c.profile['campaign']}", f"profile_revision: {c.profile['profile_revision']}",
                 f"overlay_applied: {'true' if c.overlay_applied else 'false'}", "sheets:", f"  conductivity: {c.sheet_k}", f"  calibration: {c.sheet_cal}",
                 f"  capacity: {c.sheet_cap}", "memo_tables:", f"  joint: {c.t_joint['label']}", f"  parasitic: {c.t_par['label']}",
                 f"  solver: {c.t_solver['label']}", f"  gauge: {c.t_gauge['label']}", f"  limits: {c.t_limit['label']}", "constants:"]
        for k in ("h_increment_mW_per_K", "indium_factor", "low_torque_factor", "lot_scale_materials"):
            lines.append(f"  {k}: '{S[k]}'")
        lines += ["limits_mK:", f"  ST50: {c.limits['ST50']}", f"  ST4: {c.limits['ST4']}", "runs:"]
        for run in c.active:
            s = c.settings[run]
            m = self.b.margin[(run, "ST50")]
            lines.append(f"  {run}:")
            for k in ("spike_mK", "outlier_mK", "min_readings", "reserve_pct_ST50", "reserve_pct_ST4"):
                lines.append(f"    {k}: {s[k]}")
            lines += [f"    shield: {c.runs[run]['shield']}", f"    cooler: {c.cooler[run]}", f"    derate_pct: '{plain(m['derate'])}'"]
        return "\n".join(lines) + "\n"

    def const_value(self, key: str):
        c = self.c
        kind, _, rest = key.partition(" ")
        if kind == "JOINT":
            cls, band = rest.split("/")
            return c.h_base.get((cls, band))
        if kind == "AWG":
            return c.awg.get(int(rest))
        if kind == "PARASITIC":
            conf, st = rest.split("/")
            v = c.parasitic.get((conf, st))
            return None if v is None else Fraction(v)
        if kind == "FACTOR":
            return F(c.solver[rest]) if rest in c.solver else None
        return None

    def r_authority_audit(self):
        c = self.c
        d = c.data
        rows = []

        def add(source, item, quoted, gov):
            q = str(quoted).strip()
            inf = "" if gov is None else fixed(gov, places_of(q))
            rows.append([source, item, q, inf, "AGREE" if inf == q else "DISAGREE"])

        def kval(mat_tok, tk):
            mat = c.material(mat_tok)
            if mat not in c.cond:
                return mat, None
            return mat, c.cond[mat].k_at(F(tk) * 1000)

        for e in read_lines_json(d / "conductivity_cache.jsonl"):
            mat, g = kval(e["mat"], e["T_K"])
            add("conductivity_cache.jsonl", f"{mat}@{e['T_K']}", e["k_W_per_mK"], g)
        for line in (d / "quick_reference_k26b.txt").read_text(encoding="utf-8").split("\n"):
            p = line.split()
            if len(p) == 3 and re.fullmatch(r"[\d.]+", p[1]) and re.fullmatch(r"[\d.]+", p[2]):
                mat, g = kval(p[0], p[1])
                add("quick_reference_k26b.txt", f"{mat}@{p[1]}", p[2], g)
        for mat_tok, pts in load_yaml(d / "materials_legacy.yaml")["materials"].items():
            for pt in pts:
                mat, g = kval(mat_tok, pt["T_K"])
                add("materials_legacy.yaml", f"{mat}@{pt['T_K']}", pt["k"], g)
        for r in read_delim(d / "daq_dashboard_export.csv", ","):
            if r["sensor"] != "ALL":
                continue
            run = run_id(r["run"])
            T = self.b.stage_T.get((run, r["stage"]), {}).get("T")
            add("daq_dashboard_export.csv", f"{run}/{r['stage']}", r["live_K"], None if T is None else Fraction(T, 1000))
        for line in (d / "ops_bulletin_k26b.txt").read_text(encoding="utf-8").split("\n"):
            m = re.fullmatch(r"NOTICE \d+ \| (.+?) \| (.+)", line.strip())
            if m:
                add("ops_bulletin_k26b.txt", m.group(1), m.group(2), self.const_value(m.group(1)))
        for fname, head in (("handbook_draft_r6.md", "## Draft constants"), ("budget_solve_pack.md", "## Constants as executed")):
            on = False
            for line in (d / fname).read_text(encoding="utf-8").split("\n"):
                if line.startswith("## "):
                    on = line.strip() == head
                    continue
                m = re.fullmatch(r"\| (.+?) \| (.+?) \|", line.strip())
                if on and m and m.group(1) != "key" and not m.group(1).startswith("---"):
                    add(fname, m.group(1), m.group(2), self.const_value(m.group(1)))
        lab = load_yaml(d / "profile_overlay_lab.yaml")
        for run, o in (lab.get("runs") or {}).items():
            if run not in c.settings:
                continue
            for k, v in o.items():
                if k in c.settings[run]:
                    add("profile_overlay_lab.yaml", f"{run}/{k}", v, Fraction(c.settings[run][k]))
        rows.sort(key=lambda r: (r[0], r[1]))
        return table(["source", "item", "quoted", "in_force", "verdict"], rows, ",")

    def r_variance_vs_published(self):
        pub = {}
        for r in read_delim(self.c.data / "heatload_budget_published.csv", ","):
            pub[(run_id(r["run"]), self.c.final_link(r["link"]))] = half_even(F(r["q_mW"]) * 1000)
        rec = {k: f["q"] for k, f in self.b.flows.items() if f["q"] is not None}
        keys = sorted(set(pub) | set(rec), key=lambda k: (self.ri.get(k[0], 999), k[0], k[1]))
        rows = []
        for k in keys:
            p, q = pub.get(k), rec.get(k)
            if p is None:
                st, dl = "MISSING_PUBLISHED", None
            elif q is None:
                st, dl = "MISSING_RECOMPUTED", None
            else:
                dl = q - p
                st = "MATCH" if dl == 0 else "DIFFERENT"
            rows.append([k[0], k[1], p, q, dl, st])
        return table(["run", "link", "published_uW", "recomputed_uW", "delta_uW", "status"], rows, ",")

    def r_reconciliation(self):
        doc = json.loads((self.c.data / "stage_margins_published.json").read_text(encoding="utf-8"))
        recs = sorted(doc["stages"], key=lambda r: (self.ri.get(run_id(r["run"]), 999), self.si[r["stage"]]))
        lines = ["# Reconciliation with the published stage margins", "", "| run | stage | published_verdict | recomputed_verdict | change |",
                 "|---|---|---|---|---|"]
        changed = 0
        for r in recs:
            run = run_id(r["run"])
            v = self.b.verdict.get(run, {})
            rv = "ABORTED" if v.get("verdict") == "ABORTED" else self.b.margin.get((run, r["stage"]), {}).get("verdict", "")
            ch = "same" if rv == r["verdict"] else "changed"
            changed += ch == "changed"
            lines.append(f"| {run} | {r['stage']} | {r['verdict']} | {rv} | {ch} |")
        lines += ["", f"Changed verdicts: {changed} of {len(recs)}."]
        return "\n".join(lines) + "\n"

    def r_budget_summary(self):
        lines = ["# Heat-load budget summary", "", "| run | verdict | ST50_load_uW | ST50_margin_uW | ST4_load_uW | ST4_margin_uW |", "|---|---|---|---|---|---|"]
        passing = 0
        for run in self.c.run_order:
            v = self.b.verdict[run]["verdict"]
            passing += v == "PASS"
            cells = []
            for st in COOLED:
                m = self.b.margin.get((run, st), {})
                cells += ["" if m.get("load") is None else str(m["load"]), "" if m.get("margin") is None else str(m["margin"])]
            lines.append(f"| {run} | {v} | " + " | ".join(cells) + " |")
        lines += ["", f"Runs passing: {passing} of {len(self.c.run_order)}."]
        return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: run_budget.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data, out = Path(argv[1]), Path(argv[2])
    budget = Budget(Corpus(data))
    texts = Reports(budget).render()
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for name in REPORTS:
        blob = texts[name].encode("utf-8")
        (out / name).write_bytes(blob)
        files.append({"name": name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()})
    (out / "manifest.json").write_text(jdump({"files": files}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
