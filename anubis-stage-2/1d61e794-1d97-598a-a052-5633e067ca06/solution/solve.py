#!/usr/bin/env python3
"""Recompute a VDO double-run levelling campaign: python3 run_levelnet.py DATA_DIR OUT_DIR."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction as Fr
from pathlib import Path

UTC = timezone.utc


# ----------------------------------------------------------------------------- numbers
def frac(text) -> Fr:
    return Fr(str(text).strip().replace(",", "."))


def rhe(x: Fr, places: int) -> Fr:
    """Round half to even to a number of decimal places."""
    k = 10 ** places
    q, r = divmod(x * k, 1)
    if r > Fr(1, 2) or (r == Fr(1, 2) and q % 2):
        q += 1
    return Fr(int(q), k)


def txt(x, places: int) -> str:
    if x is None:
        return ""
    v = rhe(Fr(x), places)
    neg = v < 0
    n = abs(v.numerator * (10 ** places) // v.denominator)
    s = str(n).rjust(places + 1, "0")
    out = s if places == 0 else s[:-places] + "." + s[-places:]
    return "-" + out if neg and n else out


def sqrt_r(x: Fr, places: int) -> Fr:
    y = Fr(x) * 10 ** (2 * places)
    n = math.isqrt(y.numerator // y.denominator)
    mid = Fr(2 * n + 1, 2) ** 2
    if y > mid or (y == mid and n % 2):
        n += 1
    return Fr(n, 10 ** places)


class Num(str):
    pass


def jdump(o) -> str:
    if isinstance(o, Num):
        return str(o)
    if o is None:
        return "null"
    if isinstance(o, bool):
        return "true" if o else "false"
    if isinstance(o, (int, str)) and not isinstance(o, Num):
        return json.dumps(o)
    if isinstance(o, list):
        return "[" + ",".join(jdump(v) for v in o) + "]"
    return "{" + ",".join(json.dumps(k) + ":" + jdump(v) for k, v in o.items()) + "}"


# ----------------------------------------------------------------------------- tiny yaml reader
def _scalar(s: str):
    s = s.strip()
    if s == "" or s == "~" or s == "null":
        return None
    if s[0] in "'\"" and s[-1] == s[0] and len(s) >= 2:
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        return [_scalar(x) for x in _split_flow(s[1:-1])]
    if s.startswith("{") and s.endswith("}"):
        d = {}
        for part in _split_flow(s[1:-1]):
            k, _, v = part.partition(":")
            d[k.strip()] = _scalar(v)
        return d
    return s


def _split_flow(body: str) -> list:
    out, depth, cur, quote = [], 0, "", None
    for ch in body:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def yload(text: str):
    lines = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if line.strip():
            lines.append((len(line) - len(line.lstrip(" ")), line.strip()))
    pos = [0]

    def block(indent):
        if pos[0] >= len(lines):
            return None
        ind, s = lines[pos[0]]
        if s.startswith("- ") or s == "-":
            return seq(ind)
        return mapping(ind)

    def seq(indent):
        out = []
        while pos[0] < len(lines):
            ind, s = lines[pos[0]]
            if ind != indent or not (s.startswith("- ") or s == "-"):
                break
            item = s[2:].strip() if s != "-" else ""
            pos[0] += 1
            if item == "":
                out.append(block(indent + 2))
            elif re.match(r"^[^'\"\[{][^:]*:( |$)", item) and not item.startswith("{"):
                k, _, v = item.partition(":")
                d = {}
                if v.strip():
                    d[k.strip()] = _scalar(v)
                else:
                    d[k.strip()] = block(indent + 2)
                while pos[0] < len(lines) and lines[pos[0]][0] == indent + 2 and not lines[pos[0]][1].startswith("- "):
                    sub = mapping(indent + 2)
                    d.update(sub)
                out.append(d)
            else:
                out.append(_scalar(item))
        return out

    def mapping(indent):
        out = {}
        while pos[0] < len(lines):
            ind, s = lines[pos[0]]
            if ind != indent or s.startswith("- "):
                break
            k, _, v = s.partition(":")
            pos[0] += 1
            if v.strip():
                out[k.strip()] = _scalar(v)
            else:
                nxt = lines[pos[0]][0] if pos[0] < len(lines) else -1
                if nxt > indent or (nxt == indent and pos[0] < len(lines) and lines[pos[0]][1].startswith("- ")):
                    out[k.strip()] = block(nxt)
                else:
                    out[k.strip()] = None
        return out

    return block(0)


# ----------------------------------------------------------------------------- xlsx
def read_xlsx(path: Path):
    z = zipfile.ZipFile(path)
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    pr = wb.find("m:workbookPr", ns)
    d1904 = pr is not None and pr.get("date1904") in ("1", "true")
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels}
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
    sheets = {}
    rid_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    for sh in wb.find("m:sheets", ns):
        part = target[sh.get(rid_key)]
        part = part.lstrip("/")
        part = part if part.startswith("xl/") else "xl/" + part
        root = ET.fromstring(z.read(part))
        rows = []
        for row in root.iter("{%s}row" % ns["m"]):
            vals = {}
            col = -1
            for c in row.findall("m:c", ns):
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
                if t == "s":
                    v = shared[int(c.find("m:v", ns).text)]
                elif t == "inlineStr":
                    v = "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
                else:
                    e = c.find("m:v", ns)
                    v = Num(e.text) if e is not None else ""
                vals[col] = v
            rows.append([vals.get(i, "") for i in range(max(vals) + 1)] if vals else [])
        sheets[sh.get("name")] = rows
    return sheets, d1904


def xl_date(v, d1904: bool) -> date:
    s = str(v).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return date.fromisoformat(s)
    return (date(1904, 1, 1) if d1904 else date(1899, 12, 30)) + timedelta(days=int(Fr(s)))


# ----------------------------------------------------------------------------- pdf
def _pdf_tokens(data: str):
    """Tokens of a content stream decoded as latin-1 text."""
    space = " \t\r\n\x0c\x00"
    delim = space + "()<>[]/"
    octal = "01234567"
    i, n = 0, len(data)
    while i < n:
        ch = data[i]
        if ch in space:
            i += 1
        elif ch == "(":
            depth, out, i = 1, [], i + 1
            while i < n:
                c = data[i]
                if c == "\\":
                    nx = data[i + 1:i + 2]
                    if nx and nx in octal:
                        j = i + 1
                        digs = ""
                        while j < n and len(digs) < 3 and data[j] in octal:
                            digs += data[j]
                            j += 1
                        out.append(chr(int(digs, 8) & 0xFF))
                        i = j
                        continue
                    out.append({"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}.get(nx, nx))
                    i += 2
                    continue
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                out.append(c)
                i += 1
            yield ("str", "".join(out))
        elif ch == "<" and data[i + 1:i + 2] != "<":
            j = data.index(">", i)
            hx = re.sub(r"\s", "", data[i + 1:j])
            if len(hx) % 2:
                hx += "0"
            yield ("str", bytes.fromhex(hx).decode("latin-1"))
            i = j + 1
        elif ch in "[]":
            yield (ch, None)
            i += 1
        else:
            j = i
            while j < n and data[j] not in delim:
                j += 1
            if j == i:
                j += 1
            tok = data[i:j]
            i = j
            if re.fullmatch(r"[-+]?(\d+\.?\d*|\.\d+)", tok):
                yield ("num", float(tok))
            else:
                yield ("op", tok)


def pdf_rows(path: Path) -> list:
    raw = path.read_bytes()
    text = raw.decode("latin-1")
    pages = []
    for m in re.finditer(r"<<(.*?)>>\s*stream\r?\n", text, re.S):
        head = m.group(1)
        size = int(re.search(r"/Length (\d+)", head).group(1))
        body = raw[m.end():m.end() + size]
        if "FlateDecode" in head:
            body = zlib.decompress(body)
        pages.append(body.decode("latin-1"))
    rows = []
    for p, content in enumerate(pages):
        items = []
        stack, x, y, lx, ly = [], 0.0, 0.0, 0.0, 0.0
        arr = None
        for kind, val in _pdf_tokens(content):
            if kind == "[":
                arr = []
            elif kind == "]":
                stack.append(("arr", arr))
                arr = None
            elif arr is not None:
                if kind == "str":
                    arr.append(val)
            elif kind in ("num", "str"):
                stack.append((kind, val))
            else:
                if val == "Tm":
                    nums = [v for k, v in stack[-6:]]
                    lx, ly = nums[4], nums[5]
                    x, y = lx, ly
                elif val == "Td":
                    nums = [v for k, v in stack[-2:]]
                    lx, ly = lx + nums[0], ly + nums[1]
                    x, y = lx, ly
                elif val == "Tj":
                    items.append((p, y, x, stack[-1][1]))
                elif val == "TJ":
                    items.append((p, y, x, "".join(stack[-1][1])))
                elif val == "BT":
                    lx = ly = x = y = 0.0
                stack = []
        by = {}
        for pg, yy, xx, t in items:
            by.setdefault((pg, yy), []).append((xx, t))
        for (pg, yy) in sorted(by, key=lambda k: (k[0], -k[1])):
            rows.append([t for _, t in sorted(by[(pg, yy)])])
    return rows


def memo_tables(path: Path):
    tables, errata = {}, []
    cur = None
    for cells in pdf_rows(path):
        first = cells[0]
        m = re.match(r"Table ([A-Z]-\d+)( \(continued\))?: .*\[(.+)\]$", first)
        if m:
            tid = m.group(1)
            cur = tables.setdefault(tid, {"status": m.group(3), "head": None, "rows": []})
            cur["_await_head"] = True
            continue
        if first.startswith("Erratum "):
            errata.append(first)
            cur = None
            continue
        if re.search(r"page \d+ of \d+$", first) or first == "Errata":
            continue
        if cur is None:
            continue
        if cur.pop("_await_head", False):
            cur["head"] = cells
            continue
        cur["rows"].append(cells)
    return tables, errata


# ----------------------------------------------------------------------------- clock
class Clock:
    def __init__(self, cfg: dict):
        self.base = self._off(cfg["standard_offset"])
        self.trans = sorted((datetime.strptime(t["utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC), self._off(t["offset"])) for t in cfg["transitions"])

    @staticmethod
    def _off(s: str) -> int:
        s = s.strip()
        sign = -1 if s.startswith("-") else 1
        h, m = s.lstrip("+-").split(":")
        return sign * (int(h) * 60 + int(m))

    def offset(self, u: datetime) -> int:
        o = self.base
        for t, off in self.trans:
            if t <= u:
                o = off
            else:
                break
        return o

    def to_utc(self, w: datetime) -> datetime:
        offs = sorted({self.base} | {o for _, o in self.trans})
        good = [w.replace(tzinfo=UTC) - timedelta(minutes=o) for o in offs if self.offset(w.replace(tzinfo=UTC) - timedelta(minutes=o)) == o]
        if good:
            return min(good)
        probe = w.replace(tzinfo=UTC) - timedelta(minutes=max(offs))
        return w.replace(tzinfo=UTC) - timedelta(minutes=self.offset(probe))

    def local(self, u: datetime) -> datetime:
        return (u + timedelta(minutes=self.offset(u))).replace(tzinfo=None)


# ----------------------------------------------------------------------------- the run
class Job:
    def __init__(self, data: Path):
        self.d = data
        self.find_files()

    # -- locating the registers by content
    def find_files(self):
        self.files = {}
        for p in sorted(self.d.iterdir()):
            n = p.name
            if n.endswith(".xlsx"):
                self.files["workbook"] = p
            elif n.endswith(".pdf"):
                self.files["memo"] = p
            elif n.endswith((".sqlite", ".db")):
                con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
                tabs = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
                con.close()
                for key, need in (("alias", {"bm_alias"}), ("tests", {"two_peg", "instrument_alias"}), ("epoch", {"epochs", "heights"})):
                    if need <= tabs:
                        self.files[key] = p
            else:
                head = p.read_text(encoding="utf-8", errors="replace")[:400]
                first = head.splitlines()[0] if head else ""
                if n.endswith(".json") and '"catalog"' in head:
                    self.files["catalog"] = p
                elif n.endswith(".json") and '"levelling lines"' in head:
                    self.files["lines"] = p
                elif first.startswith("run_id,campaign,start_bm"):
                    self.files["runs"] = p
                elif '"amend_no"' in first:
                    self.files["late"] = p
                elif first.startswith("section_id\tfrom_mark"):
                    self.files["sections"] = p
                elif first.startswith("mark,block,description"):
                    self.files["master"] = p
                elif head.lstrip().startswith("<journal"):
                    self.files["journal"] = p
                elif head.lstrip().startswith("<addendum"):
                    self.files["addendum"] = p
                elif first.startswith("station_id|tokens"):
                    self.files["stations"] = p
                elif '"observer"' in first and '"valid_from"' in first:
                    self.files["observers"] = p
                elif n.endswith((".yml", ".yaml")) and re.search(r"(?m)^loops:", head):
                    self.files["loops"] = p
                elif n.endswith((".yml", ".yaml")) and re.search(r"(?m)^rods:", head):
                    self.files["rod_legacy"] = p
        for k in ("campaign_profile.yml", "profile_overlay.yaml", "site_clock.yaml", "quick_reference_card.txt", "field_bulletin_q3.txt",
                  "adjustment_run_pack.md", "adjusted_heights_published.csv", "subsidence_published.json", "network_dashboard.csv",
                  "control_heights_cache.jsonl"):
            self.files[k] = self.d / k

    def text(self, key):
        return self.files[key].read_text(encoding="utf-8")

    # -- configuration
    def load_config(self):
        prof = yload(self.text("campaign_profile.yml"))
        self.camp = prof["campaign_id"]
        self.ref = date.fromisoformat(prof["reference_date"])
        self.epoch_ref = prof["epoch_reference"]
        st = {"rod_certificate_sheet": prof["rod_certificate_sheet"], "fallback_temp_c": prof["fallback_temp_c"], "met_max_gap_min": prof["met_max_gap_min"]}
        for e in yload(self.text("profile_overlay.yaml"))["overlay"]:
            if e["campaign"] == self.camp and date.fromisoformat(e["effective"]) <= self.ref:
                st[e["key"]] = e["value"]
        self.cert_sheet = st["rod_certificate_sheet"]
        self.fallback = frac(st["fallback_temp_c"])
        self.max_gap = int(st["met_max_gap_min"])
        self.settings = st
        self.controls = [str(t) for t in prof["control_points"]]
        self.pairs = {k: [str(x) for x in v] for k, v in prof["rod_pairs"].items()}
        self.line_st = {k: sorted((date.fromisoformat(e["from"]), str(e["station"])) for e in v) for k, v in prof["line_stations"].items()}
        self.clock = Clock(yload(self.text("site_clock.yaml")))
        card = self.text("quick_reference_card.txt")
        self.R = frac(re.search(r"mean earth radius R \.+ (\d+) m", card).group(1))
        tables, errata = memo_tables(self.files["memo"])
        self.tables = tables
        self.errata = errata
        live = {k: v for k, v in tables.items() if v["status"] == "IN FORCE"}
        tol = {r[0]: [r[1], r[2]] for r in live["T-1"]["rows"]}
        c2 = {r[0]: r[1] for r in live["C-2"]["rows"]}
        for e in errata:
            m = re.match(r"Erratum E-\d+: Table T-1, class (\w+), (section|loop) column: for (\S+) read (\S+)$", e)
            if m:
                tol[m.group(1)][0 if m.group(2) == "section" else 1] = m.group(4)
            m = re.match(r"Erratum E-\d+: Table C-2, mark (\S+): for (\S+) read (\S+)$", e)
            if m:
                c2[m.group(1)] = m.group(3)
        self.tol, self.c2 = tol, c2
        k1 = {r[0]: r[1] for r in live["K-1"]["rows"]}
        self.sigma = {m.group(1): k1[key] for key in k1 for m in [re.match(r"sigma class (\w+) mm per sqrt km", key)] if m}
        self.k_crit = k1["critical value of w"]
        self.r_min = int(k1["minimum redundancy after a removal"])
        self.max_rem = int(k1["maximum removals per component"])
        i1 = {r[0]: r[1] for r in live["I-1"]["rows"]}
        self.c_limit, self.k_ref = i1["collimation limit mm per 100 m"], i1["refraction coefficient"]
        self.rod_types = {r[0]: (r[1], r[2]) for r in live["A-1"]["rows"]}
        r1 = {r[0]: r[1] for r in live["R-1"]["rows"]}
        self.alert, self.k_rate = r1["alert rate mm per yr"], r1["significance factor"]
        self.chi2 = {int(r[0]): (frac(r[1]), frac(r[2])) for r in live["X-2"]["rows"]}
        self.j1 = [{"id": r[0], "target": r[1], "action": r[2], "effective": date.fromisoformat(r[3])} for r in live["J-1"]["rows"]]
        sheets, self.d1904 = read_xlsx(self.files["workbook"])
        self.sheets = sheets

    def load_registers(self):
        # rods
        self.former, self.rtype = {}, {}
        rows = self.sheets["Rods"]
        hi = next(i for i, r in enumerate(rows) if r and str(r[0]).strip() == "serial")
        for r in rows[hi + 1:]:
            if not r or not str(r[0]).strip():
                continue
            ser = str(int(re.sub(r"\D", "", str(r[0]))))
            self.rtype[ser] = str(r[2]).strip()
            if len(r) > 1 and str(r[1]).strip():
                self.former[str(int(str(r[1]).strip()))] = ser
        for e in yload(self.text("rod_legacy"))["rods"]:
            s = str(int(str(e["serial"])))
            self.rtype.setdefault(s, str(e["type"]))
        self.certs = {}
        rows = self.sheets[self.cert_sheet]
        hi = next(i for i, r in enumerate(rows) if r and str(r[0]).strip() == "rod_serial")
        for r in rows[hi + 1:]:
            if len(r) < 6 or str(r[0]).strip().lower() == "continued" or not str(r[1]).strip():
                continue
            self.certs.setdefault(str(int(str(r[0]).strip())), []).append(
                {"cert": str(r[1]).strip(), "ppm": frac(r[2]), "t0": frac(r[3]), "from": xl_date(r[4], self.d1904), "to": xl_date(r[5], self.d1904)})
        # benchmarks
        self.master = {r["mark"] for r in csv.DictReader(io.StringIO(self.text("master")))}
        con = sqlite3.connect(f"file:{self.files['alias']}?mode=ro", uri=True)
        self.alias = {}
        for tok, can, vf, vt, _ in con.execute("select token, canonical, valid_from, valid_to, note from bm_alias"):
            self.alias.setdefault(tok, []).append((date.fromisoformat(vf), date.fromisoformat(vt) if vt else None, can))
        con.close()
        # instruments
        con = sqlite3.connect(f"file:{self.files['tests']}?mode=ro", uri=True)
        self.inst_alias = {t: i for t, i in con.execute("select token, instrument from instrument_alias")}
        self.tests = {}
        for tid, ins, at, c, res, _ in con.execute("select * from two_peg"):
            if res == "RETEST":
                continue
            self.tests.setdefault(ins, []).append((datetime.strptime(at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC), tid, frac(c)))
        con.close()
        # runs
        self.reg = {}
        for r in csv.DictReader(io.StringIO(self.text("runs"))):
            if r["campaign"] == self.camp:
                self.reg[r["run_id"]] = dict(r)
        am = [json.loads(x) for x in self.text("late").splitlines() if x.strip()]
        for a in sorted(am, key=lambda e: e["amend_no"]):
            if a["campaign"] == self.camp and a["run"] in self.reg:
                self.reg[a["run"]][a["field"]] = a["value"]
        # sections and lines
        self.sections = {}
        for r in csv.DictReader(io.StringIO(self.text("sections")), delimiter="\t"):
            if r["status"] == "ACTIVE":
                self.sections[r["section_id"]] = r
        self.lclass = {}
        for ln in json.loads(self.text("lines"))["lines"]:
            eff = None
            for h in sorted(ln["class_history"], key=lambda z: z["from"]):
                if date.fromisoformat(h["from"]) <= self.ref:
                    eff = h["class"]
            self.lclass[ln["line"]] = eff
        # observers
        self.obs = {}
        for x in self.text("observers").splitlines():
            if x.strip():
                o = json.loads(x)
                self.obs.setdefault(o["observer"].upper(), []).append((date.fromisoformat(o["valid_from"]), date.fromisoformat(o["valid_to"])))
        # met stations and logs
        self.st_reg = {}
        for r in csv.DictReader(io.StringIO(self.text("stations")), delimiter="|"):
            for t in [r["station_id"]] + r["tokens"].split(";"):
                self.st_reg[t.strip().upper()] = r
        self.notices = []
        blocks = self.text("field_bulletin_q3.txt").split("\n\n")
        for b in blocks:
            if "OPERATIONAL NOTICE" in b and "status: IN FORCE" in b and f"campaign: {self.camp}" in b:
                m = re.search(r"met station (\S+) .*offline from (\S+) to (\S+)", b)
                s = re.search(r"substitute station: (\S+)", b)
                if m and s:
                    self.notices.append((m.group(1), date.fromisoformat(m.group(2)), date.fromisoformat(m.group(3)), s.group(1)))
        self.met_cache = {}
        # rulings
        add = ET.fromstring(self.text("addendum"))
        self.cancel, self.ruled = set(), {}
        for r in add:
            if r.get("campaign") != self.camp or date.fromisoformat(r.get("issued")) > self.ref:
                continue
            if r.get("action") == "CANCEL":
                self.cancel.add(r.get("target"))
            elif r.get("action") in ("REJECT_RUN", "REJECT_SECTION"):
                self.ruled.setdefault(r.get("target"), set()).add(r.get("action"))
        for j in self.j1:
            if j["id"] not in self.cancel and j["effective"] <= self.ref:
                self.ruled.setdefault(j["target"], set()).add(j["action"])

    def met_log(self, sid):
        if sid not in self.met_cache:
            r = self.st_reg[sid.upper()]
            p = self.d / r["log_file"]
            recs = []
            unit = r["unit"]
            body = p.read_text(encoding="utf-8")
            if p.suffix == ".csv":
                for row in csv.DictReader(io.StringIO(body)):
                    recs.append((datetime.fromtimestamp(int(row["epoch_s"]), UTC), frac(row["temp_c"])))
            elif p.suffix == ".tsv":
                for row in csv.DictReader(io.StringIO(body), delimiter="\t"):
                    recs.append((datetime.strptime(row["utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC), frac(row["temp"])))
            else:
                for x in body.splitlines():
                    if x.strip():
                        o = json.loads(x)
                        recs.append((datetime.fromisoformat(o["t"]).astimezone(UTC), Fr(o["ta"])))
            conv = []
            for u, v in recs:
                if unit == "degF":
                    v = (v - 32) * Fr(5, 9)
                elif unit == "tenths degC":
                    v = v / 10
                conv.append((u, v))
            conv.sort()
            self.met_cache[sid] = conv
        return self.met_cache[sid]

    def station_for(self, line, u):
        day = self.clock.local(u).date()
        tok = None
        for d0, t in self.line_st[line]:
            if d0 <= day:
                tok = t
        sid = self.st_reg[tok.upper()]["station_id"]
        for st, a, b, sub in self.notices:
            if st == sid and a <= day <= b:
                sid = self.st_reg[sub.upper()]["station_id"]
        return sid

    def temperature(self, line, u):
        recs = self.met_log(self.station_for(line, u))
        lo = hi = None
        for t, v in recs:
            if t <= u:
                lo = (t, v)
            if t >= u:
                hi = (t, v)
                break
        if lo and lo[0] == u:
            return rhe(lo[1], 1), "MET"
        if lo is None or hi is None or (hi[0] - lo[0]) > timedelta(minutes=self.max_gap):
            return self.fallback, "FALLBACK"
        span = Fr(int((hi[0] - lo[0]).total_seconds()))
        return rhe(lo[1] + (hi[1] - lo[1]) * Fr(int((u - lo[0]).total_seconds())) / span, 1), "MET"

    def resolve(self, token, day):
        t = token.strip().upper().replace(" ", "")
        m = re.fullmatch(r"VD-?(\d{1,4})", t) or re.fullmatch(r"(\d{1,4})", t)
        if m:
            t = "VD-" + m.group(1).zfill(4)
        else:
            m = re.fullmatch(r"MB-?(\d{1,3})", t)
            if m:
                t = "MB-" + m.group(1).zfill(3)
        hops = 0
        while True:
            cand = [(vf, can) for vf, vt, can in self.alias.get(t, []) if vf <= day and (vt is None or day < vt)]
            if not cand:
                break
            t = max(cand)[1]
            hops += 1
            if hops > 50:
                break
        return (t if t in self.master else None), hops

    def rod(self, token) -> str:
        s = str(int(re.sub(r"\D", "", str(token))))
        return self.former.get(s, s)

    def cert(self, serial, day):
        best = None
        for c in self.certs.get(serial, []):
            if c["from"] <= day <= c["to"] and (best is None or c["from"] > best["from"]):
                best = c
        return best

    # -- shards
    def run_id(self, s: str) -> str:
        s = str(s).strip()
        m = re.fullmatch(r"R-26-(\d{4})", s) or re.fullmatch(r"R26(\d{4})", s) or re.fullmatch(r"26/(\d{4})", s)
        return "R-26-" + m.group(1)

    def t_local(self, s: str) -> datetime:
        return self.clock.to_utc(datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))

    def read_layout(self, path: Path, lay: str) -> list:
        out = []
        ft = Fr(1200, 3937)

        def rec(run, seq, rev, void, at, rb, rf, bs, fs, db, df, temp):
            out.append({"run": self.run_id(run), "seq": int(seq), "rev": int(rev), "void": void, "at": at, "rb": rb, "rf": rf,
                        "bs": bs, "fs": fs, "db": db, "df": df, "temp": temp})

        def cel(v):
            v = "" if v is None else str(v).strip()
            return None if v in ("", "~", "null") else frac(v)

        def fah(v):
            v = "" if v is None else str(v).strip()
            return None if v == "" else rhe((frac(v) - 32) * Fr(5, 9), 1)

        def feet(v):
            return rhe(frac(v) * ft, 1)

        z = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        off = lambda s: datetime.fromisoformat(s).astimezone(UTC)
        ep = lambda s: datetime.fromtimestamp(int(s), UTC)
        body = path.read_text(encoding="utf-8") if path.suffix not in (".sqlite", ".db") else ""
        if lay == "L01":
            rows = [l for l in body.splitlines() if l.strip() and not l.startswith("#")]
            for r in csv.DictReader(io.StringIO("\n".join(rows))):
                rec(r["run"], r["setup"], r["rev"], r["void"] == "1", z(r["time_utc"]), r["rod_bs"], r["rod_fs"], frac(r["bs_m"]), frac(r["fs_m"]),
                    frac(r["dist_bs_m"]), frac(r["dist_fs_m"]), cel(r["rod_temp_c"]))
        elif lay == "L02":
            for r in csv.DictReader(io.StringIO("\n".join(l for l in body.splitlines() if l.strip())), delimiter="\t"):
                rec(r["run"], r["set"], r["r"], r["status"] == "VOID", off(r["time"]), ("pair", r["pair"]), None, frac(r["bs_mm"]) / 1000,
                    frac(r["fs_mm"]) / 1000, frac(r["dbs_dm"]) / 10, frac(r["dfs_dm"]) / 10, None)
        elif lay == "L03":
            for r in csv.DictReader(io.StringIO(body), delimiter="|"):
                rec(r["RUN"], r["SETUP"], r["REV"], r["VOIDED"] == "Y", self.t_local(r["LOCAL_TIME"]), r["BACK_ROD"], r["FORE_ROD"],
                    frac(r["BACK_READING_M"]), frac(r["FORE_READING_M"]), frac(r["BACK_DIST_M"]), frac(r["FORE_DIST_M"]), cel(r["TEMP_C"]))
        elif lay == "L04":
            for line in body.splitlines()[2:]:
                if not line.strip():
                    continue
                line = line.ljust(60)
                run, seq, rev, vf = line[0:8], line[8:12], line[12:14], line[14]
                dt, tm, pair = line[15:23], line[23:29], line[29:33].strip()
                bs, fs, dbs, dfs, tp = line[33:40], line[40:47], line[47:51], line[51:55], line[55:60].strip()
                at = self.clock.to_utc(datetime.strptime(dt + tm, "%Y%m%d%H%M%S"))
                temp = None if not tp else Fr(int(tp), 10)
                rec(run, seq, rev, vf == "V", at, ("pair", pair), None, Fr(int(bs), 100000), Fr(int(fs), 100000), Fr(int(dbs), 10), Fr(int(dfs), 10), temp)
        elif lay == "L05":
            for x in body.splitlines():
                if x.strip():
                    o = json.loads(x)
                    rec(o["run"]["id"], o["setup"]["n"], o["setup"]["rev"], bool(o["setup"]["void"]), off(o["time"]), o["bs"]["rod"], o["fs"]["rod"],
                        frac(o["bs"]["r"]), frac(o["fs"]["r"]), frac(o["bs"]["d"]), frac(o["fs"]["d"]), cel(o.get("temp_c")))
        elif lay == "L06":
            for x in body.splitlines():
                if x.strip():
                    o = json.loads(x)
                    rec(o["run_ref"], o["seq"], o["rev"], bool(o["deleted"]), ep(o["epoch_s"]), ("pair", o["pair"]), None, frac(o["bs_mm"]) / 1000,
                        frac(o["fs_mm"]) / 1000, frac(o["dbs_m"]), frac(o["dfs_m"]), fah(o.get("temp_f")))
        elif lay == "L07":
            for o in json.loads(body)["setups"]:
                rec(o["run"], o["seq"], o["revision"], o["state"] == "void", z(o["utc"]), o["back"]["rod"], o["fore"]["rod"], frac(o["back"]["reading_m"]),
                    frac(o["fore"]["reading_m"]), frac(o["back"]["distance_m"]), frac(o["fore"]["distance_m"]), None)
        elif lay == "L08":
            for e in ET.fromstring(body).iter("setup"):
                a = e.attrib
                rec(a["run"], a["seq"], a["rev"], a["void"] == "true", self.t_local(a["local"]), a["brod"], a["frod"], frac(a["bs_mm"]) / 1000,
                    frac(a["fs_mm"]) / 1000, frac(a["dbs_dm"]) / 10, frac(a["dfs_dm"]) / 10, cel(a.get("temp_c")))
        elif lay == "L09":
            for o in yload(body)["setups"]:
                rec(o["run"], o["set"], o["rev"], str(o["void"]) == "yes", off(o["time"]), ("pair", o["pair"]), None, frac(o["bs"]), frac(o["fs"]),
                    frac(o["d_bs"]), frac(o["d_fs"]), cel(o.get("temp")))
        elif lay == "L10":
            for run, items in yload(body)["runs"].items():
                for it in items:
                    seq, rev, void, e_s, rb, rf, bs, fs, db, df = it
                    rec(run, seq, rev, str(void) == "true", ep(e_s), rb, rf, frac(bs) / 1000, frac(fs) / 1000, frac(db), frac(df), None)
        elif lay == "L11":
            for line in body.splitlines():
                if not line.startswith("| ") or line.startswith("| run "):
                    continue
                c = [x.strip() for x in line.strip().strip("|").split("|")]
                rec(c[0], c[1], c[2], c[3] == "void", self.t_local(c[4]), c[5], c[6], frac(c[7]), frac(c[8]), frac(c[9]), frac(c[10]), fah(c[11]))
        elif lay == "L12":
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            for run, seq, rev, void, e_s, pair, bs, fs, dbs, dfs, tc in con.execute("select run, seq, rev, void, epoch, pair, bs, fs, dbs, dfs, temp_c from obs"):
                rec(run, seq, rev, void == 1, ep(e_s), ("pair", pair), None, Fr(bs, 100000), Fr(fs, 100000), Fr(dbs, 10), Fr(dfs, 10), cel(tc))
            con.close()
        elif lay == "L13":
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            attrs = {}
            for uid, a, v in con.execute("select uid, attr, value from setup_attr"):
                attrs.setdefault(uid, {})[a] = v
            for uid, run, seq, rev in con.execute("select uid, run, seq, rev from setup_key"):
                a = attrs.get(uid, {})
                rec(run, seq, rev, a.get("void") == "1", z(a["time_utc"]), a["rod_b"], a["rod_f"], frac(a["bs_m"]), frac(a["fs_m"]), frac(a["dist_b_m"]),
                    frac(a["dist_f_m"]), cel(a.get("temp_c")))
            con.close()
        elif lay == "L14":
            for r in csv.DictReader(io.StringIO(body), delimiter=";"):
                at = self.clock.to_utc(datetime.strptime(r["tijd"], "%d.%m.%Y %H:%M:%S"))
                rec(r["run"], r["opstelling"], r["rev"], r["vervallen"] == "ja", at, r["baak_a"], r["baak_v"], frac(r["a_mm"]) / 1000, frac(r["v_mm"]) / 1000,
                    frac(r["afst_a_m"]), frac(r["afst_v_m"]), cel(r["temp_c"]))
        elif lay == "L15":
            for r in csv.DictReader(io.StringIO(body), delimiter="\t"):
                rec(r["run"], r["seq"], r["rev"], r["void"] == "1", off(r["time"]), r["rod_b"], r["rod_f"], frac(r["bs_m"]), frac(r["fs_m"]),
                    feet(r["dist_b_ft"]), feet(r["dist_f_ft"]), fah(r["temp_f"]))
        elif lay == "L16":
            for e in ET.fromstring(body).iter("setup"):
                g = lambda k: e.find(k).text
                rec(g("run"), g("seq"), g("rev"), g("void") == "1", z(g("utc")), ("pair", g("pair")), None, Fr(int(g("bs")), 100000),
                    Fr(int(g("fs")), 100000), feet(g("dbs_ft")), feet(g("dfs_ft")), None)
        return out

    def decode(self, r):
        """Rod serials and metre readings of one raw record."""
        if isinstance(r["rb"], tuple):
            pair = self.reg[r["run"]]["pair"]
            a, b = (self.rod(t) for t in self.pairs[pair])
            rb, rf = (a, b) if r["seq"] % 2 == 1 else (b, a)
        else:
            rb, rf = self.rod(r["rb"]), self.rod(r["rf"])
        half = lambda s: self.rod_types[self.rtype[s]][0] == "HALF"
        bs = r["bs"] / 2 if half(rb) else r["bs"]
        fs = r["fs"] / 2 if half(rf) else r["fs"]
        return {"run": r["run"], "seq": r["seq"], "at": r["at"], "rb": rb, "rf": rf, "back": bs, "fore": fs, "db": r["db"], "df": r["df"], "temp": r["temp"]}

    # -- settlement
    def settle(self):
        cat = json.loads(self.text("catalog"))["entries"]
        read = [e for e in cat if e["campaign"] == self.camp and e["status"] == "ACTIVE"]
        self.read_files = [e["file"] for e in read]
        retired = {e["file"] for e in cat if e["campaign"] == self.camp and e["status"] == "RETIRED"}
        self.lineage = {f: {"file": f, "status": "READ", "records": 0, "kept": 0, "superseded": 0, "void_selected": 0, "duplicates": 0,
                            "conflicts_lost": 0} for f in self.read_files}
        groups = {}
        for rank, e in enumerate(read):
            for r in self.read_layout(self.d / e["file"], e["layout"]):
                self.lineage[e["file"]]["records"] += 1
                d = self.decode(r)
                groups.setdefault((d["run"], d["seq"]), []).append((rank, r["rev"], r["void"], d, e["file"]))
        shard_like = re.compile(r"\.(csv|tsv|psv|txt|jsonl|ndjson|json|xml|yaml|yml|md|sqlite|db)$")
        ignored = []
        for p in sorted(self.d.iterdir()):
            if p.name in self.read_files or p.name in {q.name for q in self.files.values()} or not shard_like.search(p.name):
                continue
            if p.name in retired or self.looks_like_shard(p):
                ignored.append(p.name)
        self.ignored = sorted(ignored)
        self.retired = retired
        cnt = {"records_read": sum(v["records"] for v in self.lineage.values()), "setup_keys": len(groups), "superseded_revisions": 0,
               "duplicates": 0, "conflicts": 0, "void_setups": 0, "kept_setups": 0}
        self.kept, self.excluded = {}, []
        sig = lambda d: (d["at"], d["back"], d["fore"], d["db"], d["df"], d["temp"], d["rb"], d["rf"])
        for key in sorted(groups):
            g = groups[key]
            top = max(x[1] for x in g)
            for x in g:
                if x[1] < top:
                    cnt["superseded_revisions"] += 1
                    self.lineage[x[4]]["superseded"] += 1
            comp = sorted((x for x in g if x[1] == top), key=lambda x: x[0])
            w = comp[0]
            for x in comp[1:]:
                if x[2] == w[2] and sig(x[3]) == sig(w[3]):
                    cnt["duplicates"] += 1
                    self.lineage[x[4]]["duplicates"] += 1
                else:
                    cnt["conflicts"] += 1
                    self.lineage[x[4]]["conflicts_lost"] += 1
            if w[2]:
                cnt["void_setups"] += 1
                self.lineage[w[4]]["void_selected"] += 1
                self.excluded.append({"kind": "setup", "id": f"{key[0]}#{key[1]}", "reason": "VOID_SETUP"})
                continue
            cnt["kept_setups"] += 1
            self.lineage[w[4]]["kept"] += 1
            self.kept[key] = w[3]
        self.counters = cnt

    def looks_like_shard(self, p: Path) -> bool:
        try:
            if p.suffix in (".sqlite", ".db"):
                con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
                tabs = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
                con.close()
                return bool(tabs & {"obs", "setup_key"})
            head = p.read_text(encoding="utf-8", errors="replace")[:600]
            return bool(re.search(r"^# field book export|^# Field book transcript|^VDO FIXED FIELD BOOK|\"setup\": \{|^RUN\|SETUP|^<fieldbook|^<setups"
                                  r"|^setups:|^runs:|^run\tse|^run;opstelling|\"run_ref\"|\"setups\": \[", head, re.M))
        except (OSError, sqlite3.Error):
            return False

    # -- runs
    def runs(self):
        by = {}
        for (rid, seq), d in self.kept.items():
            by.setdefault(rid, {})[seq] = d
        pairs = {}
        for s in self.sections.values():
            pairs[(s["from_mark"], s["to_mark"])] = (s["section_id"], "F")
            pairs[(s["to_mark"], s["from_mark"])] = (s["section_id"], "B")
        lim = frac(self.c_limit)
        k, R = frac(self.k_ref), self.R
        self.resolution = {}
        self.run_out, self.ledger = {}, {}
        for rid in sorted(self.reg):
            row = self.reg[rid]
            ks = by.get(rid, {})
            o = {"status": None, "section": "", "dir": "", "start": "", "end": "", "date": "", "setups": len(ks), "length": None, "dh": None,
                 "test": "", "c": None}
            self.run_out[rid] = o
            if row["status"] == "VOID":
                o["status"] = "VOID"
                continue
            if not ks:
                o["status"] = "NO_SETUPS"
                continue
            t0 = min(d["at"] for d in ks.values())
            day = self.clock.local(t0).date()
            o["date"] = day.isoformat()
            a, ha = self.resolve(row["start_bm"], day)
            b, hb = self.resolve(row["end_bm"], day)
            self.resolution[("run", row["start_bm"], day)] = (a, ha)
            self.resolution[("run", row["end_bm"], day)] = (b, hb)
            o["start"], o["end"] = a or "", b or ""
            if not a or not b:
                o["status"] = "UNRESOLVED_BM"
                continue
            if (a, b) not in pairs:
                o["status"] = "UNKNOWN_SECTION"
                continue
            o["section"], o["dir"] = pairs[(a, b)]
            if sorted(ks) != list(range(1, int(row["setups"]) + 1)):
                o["status"] = "SEQUENCE_GAP"
                continue
            if not any(f <= day <= t for f, t in self.obs.get(row["observer"].strip().upper(), [])):
                o["status"] = "UNCERTIFIED_OBSERVER"
                continue
            ins = self.inst_alias.get(" ".join(row["level"].upper().split()))
            cand = [x for x in self.tests.get(ins, []) if x[0] <= t0]
            if not cand:
                o["status"] = "NO_TEST"
                continue
            at, tid, c = max(cand)
            o["test"], o["c"] = str(tid), c
            if abs(c) > lim:
                o["status"] = "INVALID_COLLIMATION"
                continue
            if any(self.cert(d[r], day) is None for d in ks.values() for r in ("rb", "rf")):
                o["status"] = "NO_CERTIFICATE"
                continue
            if "REJECT_RUN" in self.ruled.get(rid, set()):
                o["status"] = "RULED_OUT"
                continue
            o["status"] = "VALID"
            line = self.sections[o["section"]]["line_id"]
            tot, length, lines = Fr(0), Fr(0), []
            for seq in sorted(ks):
                d = ks[seq]
                if d["temp"] is not None:
                    T, src = d["temp"], "FIELD"
                else:
                    T, src = self.temperature(line, d["at"])
                cb, cf = self.cert(d["rb"], day), self.cert(d["rf"], day)

                def red(r, D, cer, rod):
                    alpha = frac(self.rod_types[self.rtype[rod]][1])
                    return r * (1 + cer["ppm"] / 10 ** 6 + alpha / 10 ** 6 * (T - cer["t0"])) - c * D / 100000 - (1 - k) * D * D / (2 * R)
                dh = rhe(red(d["back"], d["db"], cb, d["rb"]) - red(d["fore"], d["df"], cf, d["rf"]), 5)
                tot += dh
                length += d["db"] + d["df"]
                lines.append((d, T, src, dh, cb["cert"], cf["cert"]))
            o["dh"], o["length"] = tot, length
            self.ledger[rid] = lines
        for rid, o in self.run_out.items():
            if o["status"] != "VALID":
                self.excluded.append({"kind": "run", "id": rid, "reason": o["status"]})

    # -- sections
    def pair_sections(self):
        self.sec_out = {}
        for sid in sorted(self.sections):
            s = self.sections[sid]
            cl = self.lclass[s["line_id"]]
            f = sorted(r for r, o in self.run_out.items() if o["status"] == "VALID" and o["section"] == sid and o["dir"] == "F")
            b = sorted(r for r, o in self.run_out.items() if o["status"] == "VALID" and o["section"] == sid and o["dir"] == "B")
            o = {"from": s["from_mark"], "to": s["to_mark"], "line": s["line_id"], "class": cl, "cands": len(f) * len(b), "status": None}
            self.sec_out[sid] = o
            if "REJECT_SECTION" in self.ruled.get(sid, set()):
                o["status"] = "RULED_OUT"
                continue
            if not f or not b:
                o["status"] = "INCOMPLETE"
                continue
            t = frac(self.tol[cl][0])
            best = None
            for fr in f:
                for br in b:
                    F, B = self.run_out[fr], self.run_out[br]
                    d = F["dh"] + B["dh"]
                    K = (F["length"] + B["length"]) / 2000
                    if (1000 * d) ** 2 > t * t * K:
                        continue
                    late = max(F["date"], B["date"])
                    key = (abs(d), [-ord(ch) for ch in late], fr, br)
                    if best is None or key < best[0]:
                        best = (key, fr, br, d, K)
            if best is None:
                o["status"] = "REJECTED_TOLERANCE"
                continue
            _, fr, br, d, K = best
            F, B = self.run_out[fr], self.run_out[br]
            o.update({"status": "ACCEPTED", "f": fr, "b": br, "dhf": F["dh"], "dhb": B["dh"], "d": d, "K": K, "t": t,
                      "value": rhe((F["dh"] - B["dh"]) / 2, 5)})
        for sid, o in self.sec_out.items():
            if o["status"] != "ACCEPTED":
                self.excluded.append({"kind": "section", "id": sid, "reason": o["status"]})

    # -- control and journal
    def control(self):
        root = ET.fromstring(self.text("journal"))
        ents = sorted(({"id": int(e.get("id")), "mark": e.get("mark"), "event": e.get("event"), "date": date.fromisoformat(e.get("date")),
                        "refers": e.get("refers")} for e in root), key=lambda e: e["id"])
        dead = {e["refers"] for e in ents if e["event"] == "ERRATUM"}
        self.live_journal = [e for e in ents if e["event"] != "ERRATUM" and str(e["id"]) not in dead]
        state = {}
        for e in self.live_journal:
            if e["date"] > self.ref:
                continue
            if e["event"] == "DISTURBED":
                state[e["mark"]] = True
            elif e["event"] == "REVERIFIED":
                state[e["mark"]] = False
        self.ctl, self.fixed = [], {}
        for tok in self.controls:
            m, h = self.resolve(tok, self.ref)
            self.resolution[("control", tok, self.ref)] = (m, h)
            if m is None:
                self.ctl.append((tok, "", "UNRESOLVED", None))
            elif m not in self.c2:
                self.ctl.append((tok, m, "NOT_IN_TABLE", None))
            elif state.get(m):
                self.ctl.append((tok, m, "DEMOTED_DISTURBED", frac(self.c2[m])))
            else:
                self.ctl.append((tok, m, "FIXED", frac(self.c2[m])))
                self.fixed[m] = frac(self.c2[m])

    # -- adjustment
    @staticmethod
    def solve_net(obs, fixed):
        names = sorted({o["from"] for o in obs} | {o["to"] for o in obs})
        unk = [n for n in names if n not in fixed]
        col = {n: i for i, n in enumerate(unk)}
        u = len(unk)
        N = [[Fr(0) for _ in range(u)] for _ in range(u)]
        rhs = [Fr(0)] * u
        design = []
        for o in obs:
            row, l = [], o["val"]
            if o["to"] in col:
                row.append((col[o["to"]], 1))
            else:
                l -= fixed[o["to"]]
            if o["from"] in col:
                row.append((col[o["from"]], -1))
            else:
                l += fixed[o["from"]]
            design.append((row, l))
            for i, ai in row:
                rhs[i] += ai * o["p"] * l
                for j, aj in row:
                    N[i][j] += ai * aj * o["p"]
        # inverse by elimination on [N | I]
        M = [N[i][:] + [Fr(1) if i == j else Fr(0) for j in range(u)] for i in range(u)]
        for c in range(u):
            pr = next(r for r in range(c, u) if M[r][c] != 0)
            M[c], M[pr] = M[pr], M[c]
            inv = 1 / M[c][c]
            M[c] = [v * inv for v in M[c]]
            for r in range(u):
                if r != c and M[r][c]:
                    fct = M[r][c]
                    M[r] = [a - fct * b for a, b in zip(M[r], M[c])]
        Q = [row[u:] for row in M]
        x = [sum(Q[i][j] * rhs[j] for j in range(u)) for i in range(u)]
        H = {n: fixed[n] for n in names if n in fixed}
        for n, i in col.items():
            H[n] = x[i]
        res = []
        vtpv = Fr(0)
        for o, (row, l) in zip(obs, design):
            v = sum(a * x[i] for i, a in row) - l
            q = 1 / o["p"] - sum(a * b * Q[i][j] for i, a in row for j, b in row)
            vtpv += o["p"] * v * v
            res.append((o["sec"], v, q))
        return H, res, vtpv, len(obs) - u, {n: Q[i][i] for n, i in col.items()}, names

    def adjust(self):
        acc = {s: o for s, o in self.sec_out.items() if o["status"] == "ACCEPTED"}
        adj = {}
        for s, o in acc.items():
            adj.setdefault(o["from"], set()).add(o["to"])
            adj.setdefault(o["to"], set()).add(o["from"])
        seen, comps = set(), []
        for start in sorted(adj):
            if start in seen:
                continue
            stack, comp = [start], set()
            while stack:
                n = stack.pop()
                if n in comp:
                    continue
                comp.add(n)
                stack.extend(adj[n] - comp)
            seen |= comp
            comps.append(comp)
        kc = frac(self.k_crit) ** 2
        self.iters, self.nets, self.heights, self.resid = [], {}, {}, {}
        for comp in comps:
            name = min(comp)
            secs = sorted(s for s, o in acc.items() if o["from"] in comp)
            fx = {m: self.fixed[m] * 1000 for m in comp if m in self.fixed}
            net = {"marks": len(comp), "obs": len(secs), "fixed": sorted(fx)}
            self.nets[name] = net
            if not fx:
                net["status"] = "UNCONSTRAINED"
                for s in secs:
                    self.resid[s] = (name, None, None, None, "UNCONSTRAINED")
                continue
            obs = [{"sec": s, "from": acc[s]["from"], "to": acc[s]["to"], "val": acc[s]["value"] * 1000,
                    "p": 1 / (frac(self.sigma[acc[s]["class"]]) ** 2 * acc[s]["K"])} for s in secs]
            removed, it = [], 0
            while True:
                it += 1
                H, res, vtpv, r, qxx, names = self.solve_net(obs, fx)
                tested = sorted(((v * v / q, s) for s, v, q in res if q > 0), key=lambda t: (-t[0], t[1]))
                top = tested[0] if tested else None
                if not top or top[0] <= kc:
                    act = "STOP_CLEAN"
                elif len(removed) >= self.max_rem:
                    act = "STOP_BUDGET"
                elif r - 1 < self.r_min:
                    act = "STOP_REDUNDANCY"
                else:
                    act = "REMOVE"
                self.iters.append({"component": name, "iteration": it, "observations": len(obs), "unknowns": len(obs) - r, "redundancy": r,
                                   "vtpv": Num(txt(vtpv, 4)), "max_w": Num(txt(sqrt_r(top[0], 2), 2)) if top else None,
                                   "max_w_section": top[1] if top else None, "action": act})
                if act != "REMOVE":
                    break
                removed.append(top[1])
                obs = [o for o in obs if o["sec"] != top[1]]
            net.update({"status": {"STOP_CLEAN": "SNOOPED" if removed else "CLEAN"}.get(act, act), "removed": removed, "vtpv": vtpv, "r": r,
                        "obs": len(obs), "u": len(obs) - r})
            for m in names:
                self.heights[m] = (name, H[m], Fr(0) if m in fx else qxx[m], "FIXED" if m in fx else "ADJUSTED")
            for s, v, q in res:
                self.resid[s] = (name, v, q, None, "USED" if q > 0 else "UNTESTABLE")
            for s in removed:
                o = acc[s]
                self.resid[s] = (name, H[o["to"]] - H[o["from"]] - o["value"] * 1000, None, None, "REMOVED")
                self.excluded.append({"kind": "section", "id": s, "reason": "SNOOPED"})

    # -- loops and rates
    def loops(self):
        acc = {}
        for s, o in self.sec_out.items():
            if o["status"] == "ACCEPTED":
                acc[(o["from"], o["to"])] = (o, 1)
                acc[(o["to"], o["from"])] = (o, -1)
        self.loop_out = []
        for lp in yload(self.text("loops"))["loops"]:
            marks = []
            for t in lp["marks"]:
                m, h = self.resolve(str(t), self.ref)
                self.resolution[("loop", str(t), self.ref)] = (m, h)
                marks.append(m)
            tot, K, ok = Fr(0), Fr(0), True
            for a, b in zip(marks, marks[1:] + marks[:1]):
                hit = acc.get((a, b)) if a and b else None
                if not hit:
                    ok = False
                    break
                tot += hit[1] * hit[0]["value"]
                K += hit[0]["K"]
            cl = str(lp["class"])
            if not ok:
                self.loop_out.append((lp["id"], cl, len(marks), None, None, None, "INCOMPLETE"))
                continue
            t = frac(self.tol[cl][1])
            w = tot * 1000
            self.loop_out.append((lp["id"], cl, len(marks), w, K, t, "PASS" if w * w <= t * t * K else "FAIL"))

    def rates(self):
        con = sqlite3.connect(f"file:{self.files['epoch']}?mode=ro", uri=True)
        eref = date.fromisoformat(con.execute("select reference_date from epochs where epoch_id = ?", (self.epoch_ref,)).fetchone()[0])
        prior = {}
        for mk, h, sg in con.execute("select mark, height_m, sigma_mm from heights where epoch_id = ?", (self.epoch_ref,)):
            m, hops = self.resolve(mk, eref)
            self.resolution[("epoch", mk, eref)] = (m, hops)
            if m:
                prior[m] = (frac(h), frac(sg))
        con.close()
        dist = {e["mark"] for e in self.live_journal if e["event"] == "DISTURBED" and eref < e["date"] <= self.ref}
        years = Fr((self.ref - eref).days) / Fr(365.25)
        kr = frac(self.k_rate) ** 2
        alert = frac(self.alert)
        self.rate_out = {}
        for m, (comp, hmm, q, st) in self.heights.items():
            h26 = rhe(hmm / 1000, 5)
            s26 = sqrt_r(q, 2)
            if st == "FIXED":
                self.rate_out[m] = (None, h26, None, None, "CONTROL")
                continue
            if m in dist:
                self.rate_out[m] = (None, h26, None, None, "DISTURBED")
                continue
            if m not in prior:
                self.rate_out[m] = (None, h26, None, None, "NEW")
                continue
            h24, s24 = prior[m]
            rate = (h26 - h24) * 1000 / years
            var = (s26 * s26 + s24 * s24) / years ** 2
            sig = rate * rate > kr * var
            cls = "ALERT" if sig and rate <= alert else "SUBSIDING" if sig and rate < 0 else "UPLIFT" if sig and rate > 0 else "STABLE"
            self.rate_out[m] = (h24, h26, rate, var, cls)

    # -- reports
    def write(self, out: Path):
        out.mkdir(parents=True, exist_ok=True)
        rep = {}

        def tab(head, rows, sep):
            return sep.join(head) + "\n" + "".join(sep.join("" if v is None else str(v) for v in r) + "\n" for r in rows)

        rows = []
        for rid in sorted(self.ledger):
            for d, T, src, dh, _cb, _cf in self.ledger[rid]:
                rows.append([rid, d["seq"], d["at"].strftime("%Y-%m-%dT%H:%M:%SZ"), d["rb"], d["rf"], txt(d["back"], 5), txt(d["fore"], 5), txt(d["db"], 1),
                             txt(d["df"], 1), txt(T, 1), src, txt(d["back"] - d["fore"], 5), txt(dh, 5)])
        rep["setup_ledger.csv"] = tab("run_id,seq,instant_utc,back_rod,fore_rod,back_m,fore_m,back_dist_m,fore_dist_m,temp_c,temp_source,dh_raw_m,dh_m".split(","), rows, ",")
        rows = []
        for rid in sorted(self.run_out):
            o = self.run_out[rid]
            ok = o["status"] == "VALID"
            rows.append([rid, o["section"], o["dir"], o["start"], o["end"], o["date"], o["setups"], txt(o["length"], 1) if ok else "",
                         txt(o["dh"], 5) if ok else "", o["test"], txt(o["c"], 3) if o["c"] is not None else "", o["status"]])
        rep["run_summaries.tsv"] = tab(["run_id", "section_id", "direction", "start_mark", "end_mark", "run_date", "setups", "length_m", "dh_m", "test_id",
                                        "collimation_mm_per_100m", "status"], rows, "\t")
        rows = []
        for sid in sorted(self.sec_out):
            o = self.sec_out[sid]
            if o["status"] == "ACCEPTED":
                rows.append([sid, o["from"], o["to"], o["line"], o["class"], o["f"], o["b"], txt(o["dhf"], 5), txt(o["dhb"], 5), txt(o["d"] * 1000, 2),
                             txt(o["K"], 5), txt(sqrt_r(o["t"] ** 2 * o["K"], 2), 2), o["cands"], o["status"], txt(o["value"], 5)])
            else:
                rows.append([sid, o["from"], o["to"], o["line"], o["class"], "", "", "", "", "", "", "", o["cands"], o["status"], ""])
        rep["section_pairs.psv"] = tab(["section_id", "from_mark", "to_mark", "line_id", "class", "forward_run", "backward_run", "dh_forward_m", "dh_backward_m",
                                        "discrepancy_mm", "length_km", "tolerance_mm", "candidates", "status", "value_m"], rows, "|")
        rows = [[c, t, d.isoformat(), m or "", h, "RESOLVED" if m else "UNRESOLVED"] for (c, t, d), (m, h) in sorted(self.resolution.items())]
        rep["benchmark_resolution.csv"] = tab(["context", "token", "resolve_date", "mark", "hops", "status"], rows, ",")
        ctl = [{"token": t, "mark": m, "status": s, "height_m": Num(txt(h, 5)) if h is not None else None} for t, m, s, h in self.ctl]
        rep["control_points.json"] = jdump({"campaign": self.camp, "reference_date": self.ref.isoformat(), "table": "C-2", "controls": ctl}) + "\n"
        rep["adjustment_iterations.jsonl"] = "".join(jdump(x) + "\n" for x in sorted(self.iters, key=lambda z: (z["component"], z["iteration"])))
        rows = [[m, c, txt(h / 1000, 5), txt(sqrt_r(q, 2), 2), st] for m, (c, h, q, st) in sorted(self.heights.items())]
        rep["adjusted_heights.csv"] = tab(["mark", "component", "height_m", "sigma_mm", "status"], rows, ",")
        rows = []
        for s in sorted(self.resid):
            comp, v, q, _, st = self.resid[s]
            if st == "UNCONSTRAINED":
                rows.append([s, comp, "", "", "", st])
                continue
            w = ""
            if st == "USED":
                a = sqrt_r(v * v / q, 2)
                w = txt(-a if v < 0 else a, 2)
            rows.append([s, comp, txt(v, 2), txt(q, 4) if q is not None else "", w, st])
        rep["residuals.tsv"] = tab(["section_id", "component", "v_mm", "qvv_mm2", "w", "status"], rows, "\t")
        comps = []
        for name in sorted(self.nets):
            n = self.nets[name]
            if n["status"] == "UNCONSTRAINED":
                comps.append({"component": name, "marks": n["marks"], "observations": n["obs"], "unknowns": None, "redundancy": None, "fixed": [],
                              "status": "UNCONSTRAINED", "removed": [], "vtpv": None, "s0": None, "chi2_lower": None, "chi2_upper": None,
                              "global_test": "UNCONSTRAINED"})
                continue
            r = n["r"]
            lo = hi = None
            if r == 0:
                gt = "NO_REDUNDANCY"
            elif r not in self.chi2:
                gt = "OUT_OF_TABLE"
            else:
                lo, hi = self.chi2[r]
                gt = "PASS" if lo <= n["vtpv"] <= hi else "FAIL"
            comps.append({"component": name, "marks": n["marks"], "observations": n["obs"], "unknowns": n["u"], "redundancy": r, "fixed": n["fixed"],
                          "status": n["status"], "removed": n["removed"], "vtpv": Num(txt(n["vtpv"], 4)),
                          "s0": Num(txt(sqrt_r(n["vtpv"] / r, 3), 3)) if r else None, "chi2_lower": Num(txt(lo, 3)) if lo is not None else None,
                          "chi2_upper": Num(txt(hi, 3)) if hi is not None else None, "global_test": gt})
        rep["network_summary.json"] = jdump({"campaign": self.camp, "components": comps}) + "\n"
        x = [f'<loops campaign="{self.camp}">']
        for lid, cl, n, w, K, t, st in sorted(self.loop_out):
            if st == "INCOMPLETE":
                x.append(f'  <loop id="{lid}" class="{cl}" marks="{n}" misclosure_mm="" length_km="" tolerance_mm="" status="{st}"/>')
            else:
                x.append(f'  <loop id="{lid}" class="{cl}" marks="{n}" misclosure_mm="{txt(w, 2)}" length_km="{txt(K, 5)}" '
                         f'tolerance_mm="{txt(sqrt_r(t * t * K, 2), 2)}" status="{st}"/>')
        rep["loop_closures.xml"] = "\n".join(x + ["</loops>"]) + "\n"
        rows = []
        for m in sorted(self.rate_out):
            h24, h26, rate, var, cls = self.rate_out[m]
            rows.append([m, txt(h24, 5), txt(h26, 5), txt(rate, 2), txt(sqrt_r(var, 2), 2) if var is not None else "", cls])
        rep["subsidence_rates.csv"] = tab(["mark", "height_2024_m", "height_2026_m", "rate_mm_per_yr", "sigma_rate_mm_per_yr", "class"], rows, ",")
        rep["excluded_records.jsonl"] = "".join(jdump(e) + "\n" for e in sorted(self.excluded, key=lambda e: (e["kind"], e["id"], e["reason"])))
        c = dict(self.counters)
        c["files_read"] = len(self.read_files)
        c["files_ignored"] = self.ignored
        rep["dedup_report.json"] = jdump(c) + "\n"
        files = [self.lineage[f] for f in self.read_files]
        for f in self.ignored:
            files.append({"file": f, "status": "RETIRED" if f in self.retired else "UNCATALOGUED", "records": 0, "kept": 0, "superseded": 0,
                          "void_selected": 0, "duplicates": 0, "conflicts_lost": 0})
        rep["source_lineage.json"] = jdump({"files": files}) + "\n"
        use = {}
        for rid, lines in self.ledger.items():
            for d, T, src, dh, cb, cf in lines:
                use[(d["rb"], cb)] = use.get((d["rb"], cb), 0) + 1
                use[(d["rf"], cf)] = use.get((d["rf"], cf), 0) + 1
        rows = []
        for (rod, cid), n in sorted(use.items()):
            cr = next(x for x in self.certs[rod] if x["cert"] == cid)
            ty = self.rtype[rod]
            rows.append([rod, ty, self.rod_types[ty][0], cid, txt(cr["ppm"], 1), txt(cr["t0"], 1), cr["from"].isoformat(), cr["to"].isoformat(), n])
        rep["rod_certificates_used.tsv"] = tab(["rod_serial", "rod_type", "graduation", "certificate", "scale_ppm", "t0_c", "valid_from", "valid_to", "readings"],
                                               rows, "\t")
        kv = [("campaign", self.camp), ("reference_date", self.ref.isoformat()), ("epoch_reference", self.epoch_ref),
              ("rod_certificate_sheet", self.cert_sheet), ("fallback_temp_c", txt(self.fallback, 1)), ("met_max_gap_min", self.max_gap),
              ("refraction_coefficient", self.k_ref), ("earth_radius_m", txt(self.R, 0)), ("collimation_limit_mm_per_100m", self.c_limit),
              ("critical_w", self.k_crit), ("min_redundancy", self.r_min), ("max_removals", self.max_rem), ("alert_rate_mm_per_yr", self.alert),
              ("k_rate", self.k_rate)]
        for cl in ("I", "II", "III"):
            kv += [(f"tolerance_section_{cl}_mm", self.tol[cl][0]), (f"tolerance_loop_{cl}_mm", self.tol[cl][1]), (f"sigma_{cl}_mm_per_sqrt_km", self.sigma[cl])]
        for ty in sorted(self.rod_types):
            kv += [(f"graduation_{ty}", self.rod_types[ty][0]), (f"alpha_{ty}_ppm_per_c", self.rod_types[ty][1])]
        rep["parameters_used.yaml"] = "".join(f"{k}: {v}\n" for k, v in kv)
        pub = {}
        for line in self.text("adjusted_heights_published.csv").splitlines():
            if line and not line.startswith("#") and not line.startswith("mark,"):
                p = line.split(",")
                pub[p[0]] = frac(p[1])
        mine = {m: rhe(h / 1000, 5) for m, (c, h, q, st) in self.heights.items()}
        rows = []
        for m in sorted(set(pub) | set(mine)):
            p, h = pub.get(m), mine.get(m)
            st = "MISSING_PUBLISHED" if p is None else "MISSING_RECOMPUTED" if h is None else "MATCH" if p == h else "DIFFERENT"
            rows.append([m, txt(p, 5), txt(h, 5), txt((h - p) * 1000, 2) if p is not None and h is not None else "", st])
        rep["variance_vs_published.csv"] = tab(["mark", "published_m", "recomputed_m", "diff_mm", "status"], rows, ",")
        prate = {e["mark"]: e for e in json.loads(self.text("subsidence_published.json"))["rates"]}
        rows = []
        for m in sorted(set(prate) | set(self.rate_out)):
            p, o = prate.get(m), self.rate_out.get(m)
            pr = frac(p["rate_mm_per_yr"]) if p and p["rate_mm_per_yr"] is not None else None
            rr = rhe(o[2], 2) if o and o[2] is not None else None
            pc, rc = (p["class"] if p else ""), (o[4] if o else "")
            st = ("MISSING_PUBLISHED" if p is None else "MISSING_RECOMPUTED" if o is None else "CLASS_DIFFERS" if pc != rc
                  else "RATE_DIFFERS" if pr != rr else "MATCH")
            rows.append([m, txt(pr, 2), txt(rr, 2), pc, rc, st])
        rep["rate_vs_published.psv"] = tab(["mark", "published_rate", "recomputed_rate", "published_class", "recomputed_class", "status"], rows, "|")
        dash = {r["section_id"]: r["status"] for r in csv.DictReader(io.StringIO(self.text("network_dashboard.csv")))}
        rows = []
        for s in sorted(set(dash) | set(self.sec_out)):
            mine_s = self.sec_out[s]["status"] if s in self.sec_out else ""
            if s in self.resid and self.resid[s][4] == "REMOVED":
                mine_s = "SNOOPED"
            if dash.get(s, "") != mine_s:
                rows.append([s, dash.get(s, ""), mine_s])
        rep["dashboard_disagreements.csv"] = tab(["section_id", "dashboard_status", "recomputed_status"], rows, ",")
        out_c = []
        for x in self.text("control_heights_cache.jsonl").splitlines():
            if not x.strip():
                continue
            e = json.loads(x)
            if e["epoch"] != "VDH-2025":
                continue
            m, _ = self.resolve(e["mark"], self.ref)
            if m in self.c2 and frac(e["height_m"]) != frac(self.c2[m]):
                out_c.append(((m, e["mark"]), {"mark": m, "cache_token": e["mark"], "cache_m": Num(e["height_m"]), "in_force_m": Num(self.c2[m]),
                                               "diff_mm": Num(txt((frac(e["height_m"]) - frac(self.c2[m])) * 1000, 2))}))
        rep["cache_divergence.jsonl"] = "".join(jdump(v) + "\n" for _, v in sorted(out_c, key=lambda z: z[0]))
        rep["reconciliation.md"] = self.recon(pub, mine)
        names = list(rep)
        for n in names:
            (out / n).write_text(rep[n], encoding="utf-8", newline="\n")
        man = {"files": [{"name": n, "bytes": len(rep[n].encode()), "sha256": hashlib.sha256(rep[n].encode()).hexdigest()} for n in names]}
        (out / "manifest.json").write_text(json.dumps(man) + "\n", encoding="utf-8", newline="\n")

    def recon(self, pub, mine) -> str:
        runs = self.run_out.values()
        secs = self.sec_out.values()
        nets = self.nets.values()
        counts = [("runs_valid", sum(o["status"] == "VALID" for o in runs)), ("runs_rejected", sum(o["status"] != "VALID" for o in runs)),
                  ("sections_accepted", sum(o["status"] == "ACCEPTED" for o in secs)), ("sections_not_accepted", sum(o["status"] != "ACCEPTED" for o in secs)),
                  ("components", len(self.nets)), ("components_unconstrained", sum(n["status"] == "UNCONSTRAINED" for n in nets)),
                  ("sections_snooped", sum(len(n.get("removed", [])) for n in nets)), ("marks_adjusted", len(self.heights)),
                  ("marks_alert", sum(o[4] == "ALERT" for o in self.rate_out.values())), ("loops_failing", sum(x[6] == "FAIL" for x in self.loop_out))]
        out = [f"# {self.camp} recomputation summary", "", "## Counts", "", "| item | value |", "| --- | --- |"]
        out += [f"| {k} | {v} |" for k, v in counts]
        pack = self.text("adjustment_run_pack.md")
        block = re.search(r"## Settings\s+```\n(.*?)```", pack, re.S).group(1)
        used = {"control_table": "C-2", "certificate_sheet": self.cert_sheet, "refraction_coefficient": self.k_ref, "earth_radius_m": txt(self.R, 0),
                "tolerance_class_II_section_mm": self.tol["II"][0], "snooping_variance": "A_PRIORI", "met_max_gap_min": str(self.max_gap),
                "fallback_temp_c": txt(self.fallback, 1), "pair_selection": "MIN_DISCREPANCY", "run_date_source": "FIRST_SETUP_INSTANT",
                "rod_scale_applied_to": "EACH_READING", "thermal_correction": "APPLIED"}
        out += ["", "## Run pack settings", "", "| setting | pack | used |", "| --- | --- | --- |"]
        for line in block.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                out.append(f"| {k.strip()} | {v.strip()} | {used[k.strip()]} |")
        diffs = sorted((-abs(mine[m] - pub[m]), m) for m in mine if m in pub)
        out += ["", "## Largest height differences", "", "| mark | published_m | recomputed_m | diff_mm |", "| --- | --- | --- | --- |"]
        for _, m in diffs[:10]:
            out.append(f"| {m} | {txt(pub[m], 5)} | {txt(mine[m], 5)} | {txt((mine[m] - pub[m]) * 1000, 2)} |")
        return "\n".join(out) + "\n"


def main(argv) -> int:
    if len(argv) != 3:
        print("usage: run_levelnet.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    job = Job(Path(argv[1]))
    job.load_config()
    job.load_registers()
    job.settle()
    job.runs()
    job.pair_sections()
    job.control()
    job.adjust()
    job.loops()
    job.rates()
    job.write(Path(argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
