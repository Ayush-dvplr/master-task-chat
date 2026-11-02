#!/usr/bin/env python3
"""Recompute the EA-IRMS batch from a data directory.

usage: python3 run_irms.py DATA_DIR OUT_DIR

Standard library only. Every number is carried as an exact fraction of the decimal text it was
read from and rounded half to even at the stage the handbook names.
"""
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
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction as Q
from pathlib import Path

UTC = timezone.utc
ELEMS_ALL = ("N", "C")


# ----------------------------------------------------------------------------- numbers
def num(text):
    t = str(text).strip().replace(",", ".")
    return Q(Decimal(t))


def rnd(value, places):
    v = Q(value) * (10 ** places)
    lo = v.numerator // v.denominator
    frac = v - lo
    half = Q(1, 2)
    if frac > half or (frac == half and lo % 2):
        lo += 1
    return Q(lo, 10 ** places)


def txt(value, places):
    if value is None:
        return ""
    v = rnd(value, places) * (10 ** places)
    k = v.numerator
    neg = k < 0
    digits = str(abs(k)).zfill(places + 1)
    body = digits if places == 0 else digits[:len(digits) - places] + "." + digits[len(digits) - places:]
    return ("-" if neg else "") + body


class Num:
    """A JSON number printed with fixed decimals."""

    def __init__(self, value, places):
        self.s = txt(value, places)


def jnum(value, places):
    return None if value is None else Num(value, places)


def to_json(o):
    if o is None:
        return "null"
    if o is True:
        return "true"
    if o is False:
        return "false"
    if isinstance(o, Num):
        return o.s
    if isinstance(o, int):
        return str(o)
    if isinstance(o, str):
        return json.dumps(o)
    if isinstance(o, (list, tuple)):
        return "[" + ", ".join(to_json(x) for x in o) + "]"
    return "{" + ", ".join(json.dumps(k) + ": " + to_json(v) for k, v in o.items()) + "}"


def avg(xs):
    xs = list(xs)
    return sum(xs, Q(0)) / len(xs)


def lsq(xs, ys):
    n = len(xs)
    sx, sy = sum(xs, Q(0)), sum(ys, Q(0))
    sxx = sum((x * x for x in xs), Q(0))
    sxy = sum((x * y for x, y in zip(xs, ys)), Q(0))
    den = n * sxx - sx * sx
    if den == 0:
        return None
    b1 = (n * sxy - sx * sy) / den
    return b1, (sy - b1 * sx) / n


def dsqrt(value, places):
    with localcontext() as c:
        c.prec = 60
        r = (Decimal(value.numerator) / Decimal(value.denominator)).sqrt()
        return str(r.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN))


def norm(t):
    return str(t).strip().upper()


# ----------------------------------------------------------------------------- small yaml
def yaml_load(text):
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lines.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))
    pos = 0

    def scalar(s):
        s = s.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            return s[1:-1]
        return s

    def block(indent):
        nonlocal pos
        if pos < len(lines) and lines[pos][1].startswith("- "):
            out = []
            while pos < len(lines) and lines[pos][0] == indent and lines[pos][1].startswith("-"):
                rest = lines[pos][1][1:].strip()
                if rest.startswith("{") and rest.endswith("}"):
                    item = {}
                    for part in rest[1:-1].split(","):
                        k, _, v = part.partition(":")
                        item[k.strip()] = scalar(v)
                    out.append(item)
                    pos += 1
                elif re.match(r"^[A-Za-z0-9_.]+:(\s|$)", rest):
                    lines[pos] = (indent + 2, rest)
                    out.append(block(indent + 2))
                else:
                    out.append(scalar(rest))
                    pos += 1
            return out
        out = {}
        while pos < len(lines) and lines[pos][0] == indent and not lines[pos][1].startswith("- "):
            key, _, rest = lines[pos][1].partition(":")
            pos += 1
            if rest.strip():
                out[key.strip()] = scalar(rest)
            elif pos < len(lines) and (lines[pos][0] > indent or lines[pos][1].startswith("- ")):
                out[key.strip()] = block(lines[pos][0])
            else:
                out[key.strip()] = None
        return out

    return block(lines[0][0]) if lines else {}


# ----------------------------------------------------------------------------- clock
class Clock:
    def __init__(self, path):
        y = yaml_load(path.read_text(encoding="utf-8"))
        self.base = self._off(y["base_offset"])
        self.tr = sorted((datetime.strptime(t["at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC), self._off(t["offset_after"]))
                         for t in y["transitions"])
        self.base_text = y["base_offset"]

    @staticmethod
    def _off(s):
        s = s.strip()
        sign = -1 if s[0] == "-" else 1
        h, m = s.lstrip("+-").split(":")
        return sign * (int(h) * 60 + int(m))

    def offset(self, u):
        o = self.base
        for t, after in self.tr:
            if t <= u:
                o = after
            else:
                break
        return o

    def local(self, u):
        return (u + timedelta(minutes=self.offset(u))).replace(tzinfo=None)

    def utc(self, wall):
        offs = {self.base} | {o for _, o in self.tr}
        hits = []
        for o in offs:
            u = (wall - timedelta(minutes=o)).replace(tzinfo=UTC)
            if self.offset(u) == o:
                hits.append(u)
        if hits:
            return min(hits)
        before = self.base
        for t, after in self.tr:
            if (wall - timedelta(minutes=before)).replace(tzinfo=UTC) >= t > (wall - timedelta(minutes=after)).replace(tzinfo=UTC):
                return (wall - timedelta(minutes=before)).replace(tzinfo=UTC)
            before = after
        raise ValueError(wall)


# ----------------------------------------------------------------------------- office documents
PDF_TOKEN = re.compile(r"\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|-?\d+\.?\d*|/[A-Za-z0-9]+|[A-Za-z*']+")
STREAM_HEAD = re.compile(r"<<([^>]*?)/Length (\d+)([^>]*?)>>\s*stream\r?\n")
NUMBER = re.compile(r"-?\d+\.?\d*")


def pdf_string(tok):
    if tok.startswith("<"):
        return bytes.fromhex(re.sub(r"\s", "", tok[1:-1])).decode("latin-1")
    body = tok[1:-1]
    out, i = [], 0
    while i < len(body):
        if body[i] == "\\" and re.fullmatch(r"[0-7]{3}", body[i + 1:i + 4]):
            out.append(chr(int(body[i + 1:i + 4], 8)))
            i += 4
        elif body[i] == "\\" and i + 1 < len(body):
            out.append(body[i + 1])
            i += 2
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def pdf_rows(path):
    raw = path.read_bytes()
    text_all = raw.decode("latin-1")
    pages = []
    for m in STREAM_HEAD.finditer(text_all):
        n = int(m.group(2))
        data = raw[m.end():m.end() + n]
        if "FlateDecode" in m.group(0):
            data = zlib.decompress(data)
        data = data.decode("latin-1")
        items = {}
        stack, x, y, text, in_arr = [], 0.0, 0.0, [], False
        for t in PDF_TOKEN.findall(data):
            if t == "BT":
                stack, x, y, text, in_arr = [], 0.0, 0.0, [], False
            elif t == "Tm":
                x, y = float(stack[-2]), float(stack[-1])
                stack = []
            elif t == "Td":
                x, y = x + float(stack[-2]), y + float(stack[-1])
                stack = []
            elif t == "[":
                in_arr, text = True, []
            elif t == "]":
                in_arr = False
            elif t[:1] in ("(", "<"):
                text.append(pdf_string(t))
            elif NUMBER.fullmatch(t):
                if not in_arr:
                    stack.append(t)
            elif t in ("Tj", "TJ"):
                items.setdefault(y, []).append((x, "".join(text)))
                text, stack = [], []
            elif t in ("Tf", "ET"):
                stack = []
        page = [[c.strip() for _, c in sorted(cells)] for yy, cells in sorted(items.items(), key=lambda kv: -kv[0])]
        pages.append(page)
    return [r for p in pages for r in p]


def memo_tables(path):
    tables, current, headers = {}, None, {}
    title = re.compile(r"^Table ([A-Z]-\d+): (.*) \[(.*)\]$")
    cont = re.compile(r"^Table ([A-Z]-\d+) \(continued\)$")
    for row in pdf_rows(path):
        if len(row) == 1:
            m = title.match(row[0])
            if m:
                current = m.group(1)
                tables[current] = {"status": m.group(3), "rows": []}
                continue
            m = cont.match(row[0])
            if m:
                current = m.group(1)
                continue
            continue
        if current is None:
            continue
        if current not in headers:
            headers[current] = row
            continue
        if row == headers[current]:
            continue
        tables[current]["rows"].append(dict(zip(headers[current], row)))
    return tables


NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


class Workbook:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        wb = ET.fromstring(self.z.read("xl/workbook.xml"))
        pr = wb.find(NS + "workbookPr")
        flag = (pr.get("date1904") if pr is not None else "") or ""
        self.d1904 = flag.strip().lower() in ("1", "true")
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(self.z.read("xl/_rels/workbook.xml.rels"))}
        self.parts = {}
        for sh in wb.iter(NS + "sheet"):
            tgt = rels[sh.get(RNS + "id")]
            self.parts[sh.get("name")] = "xl/" + tgt.lstrip("/").replace("xl/", "", 1) if not tgt.startswith("/xl/") else tgt.lstrip("/")
        self.sst = []
        if "xl/sharedStrings.xml" in self.z.namelist():
            for si in ET.fromstring(self.z.read("xl/sharedStrings.xml")).iter(NS + "si"):
                self.sst.append("".join(t.text or "" for t in si.iter(NS + "t")))

    def serial(self, v):
        base = date(1904, 1, 1) if self.d1904 else date(1899, 12, 30)
        return base + timedelta(days=int(Q(Decimal(str(v).strip()))))

    def rows(self, name, key):
        root = ET.fromstring(self.z.read(self.parts[name]))
        grid = []
        for r in root.iter(NS + "row"):
            cells = {}
            pos = 0
            for c in r.iter(NS + "c"):
                ref = c.get("r")
                if ref:
                    letters = re.match(r"[A-Z]+", ref).group(0)
                    pos = 0
                    for ch in letters:
                        pos = pos * 26 + ord(ch) - 64
                else:
                    pos += 1
                col, k = "", pos
                while k:
                    k, rem = divmod(k - 1, 26)
                    col = chr(65 + rem) + col
                kind = c.get("t")
                if kind == "inlineStr":
                    val = "".join(t.text or "" for t in c.iter(NS + "t"))
                else:
                    v = c.find(NS + "v")
                    if v is None:
                        continue
                    val = self.sst[int(v.text)] if kind == "s" else v.text
                cells[col] = val.strip()
            grid.append(cells)
        start = next(i for i, g in enumerate(grid) if g.get("A", "") == key)
        cols = sorted(grid[start], key=lambda c: (len(c), c))
        names = [grid[start][c] for c in cols]
        out = []
        for g in grid[start + 1:]:
            if not g.get(cols[1], ""):
                continue
            out.append({n: g.get(c, "") for n, c in zip(names, cols)})
        return out


# ----------------------------------------------------------------------------- shard layouts
# layout -> (family, time, area unit, amp unit, delta unit, decimal comma, void-true tokens)
LAYOUT = {
    "L01": ("csv", "lw", "Vs", "mV", "pm", False), "L02": ("tsv", "es", "mVs", "V", "pm", False),
    "L03": ("psv", "dmy", "Vs", "mV", "pm", True), "L04": ("jsonl", "ems", "Vs", "mV", "mi", False),
    "L05": ("ndn", "off", "Vs", "mV", "pm", False), "L06": ("xa", "z", "mVs", "mV", "pm", False),
    "L07": ("sqs", "cmp", "Vs", "mV", "mi", False), "L08": ("sqf", "es", "Vs", "V", "pm", False),
    "L09": ("yb", "off", "Vs", "mV", "pm", False), "L10": ("yg", "lw", "mVs", "mV", "pm", False),
    "L11": ("jc", "es", "mVs", "mV", "mi", False), "L12": ("fx", "cmp", "Vs", "mV", "pm", False),
    "L13": ("md", "z", "Vs", "V", "pm", False), "L14": ("semi", "dmys", "Vs", "mV", "pm", True),
    "L15": ("wide", "ems", "Vs", "mV", "pm", False), "L16": ("jn", "z", "Vs", "mV", "ra", False),
    "L17": ("cc", "off", "mVs", "V", "pm", False), "L18": ("psv", "ems", "mVs", "mV", "mi", False),
    "L19": ("xc", "lt", "Vs", "mV", "mi", False), "L20": ("ndf", "bz", "Vs", "V", "pm", False),
    "L21": ("sqr", "off", "mVs", "mV", "pm", False), "L22": ("eav", "es", "Vs", "mV", "pm", False),
}
VOID_TRUE = {"L01": "V", "L02": "VOID", "L03": "DEAD", "L04": True, "L05": "Y", "L06": "1", "L07": 1, "L08": "VOID", "L09": "true",
             "L10": "void", "L11": 1, "L12": "X", "L13": "VOID", "L14": "V", "L15": "1", "L16": True, "L17": "1", "L18": "Y",
             "L19": "true", "L20": "void", "L21": "VOID", "L22": "1"}
ELEMENT_WORD = {"N2": "N", "CO2": "C", "N": "N", "C": "C", "15N": "N", "13C": "C", "28": "N", "44": "C", "NITROGEN": "N", "CARBON": "C"}
REFERENCE_WORD = {"R", "REF", "0", "REFERENCE", "RG"}
COLS = {
    "L01": "proj seq inst pos gas ptype rev void t_local area_vs amp_mv d_permil",
    "L02": "Project Sequence Line Counter Species PeakKind Revision Status EpochS Area_mVs Amp_V dRaw",
    "L03": "projekt lauf geraet position isotop peaktyp revision zustand zeit flaeche_vs amplitude_mv delta",
    "L04": "prj run ln slot el pk rv void ts_ms a amp dm",
    "L08": "project sequence instrument counter gas peaktype revision void_flag epoch area amplitude delta",
    "L11": "project sequence instrument counter species peak revision void epoch_s area_mvs amp_mv d_milli",
    "L12": "PROJECT SEQUENCE INST POS GAS PT REV VOID TIME AREA_VS AMP_MV D_PERMIL",
    "L13": "project sequence instrument position isotope peak rev void time_utc area_vs amp_v delta",
    "L14": "Projekt Sequenz Geraet Pos Element Typ Rev Void Zeit Flaeche Amplitude Delta",
    "L17": "project sequence instrument counter mass peak rev void ts area_mvs amp_v d",
    "L18": "PRJ SEQ INST CTR MZ PT REV VD EPOCHMS AREA_MVS AMP_MV D_MILLI",
    "L19": "project sequence instrument counter species kind revision void time area_vs amp_mv d_milli",
    "L20": "PROJ SEQ INST POS GAS PT REV STATUS TS AREA AMP_V DELTA",
    "L22": "project seq inst pos el type rev void t area amp d",
}
CANON = ("P", "S", "I", "K", "E", "T", "R", "V", "W", "A", "M", "D")


def stamp(value, kind, clock):
    v = str(value).strip()
    if kind == "es":
        return datetime.fromtimestamp(int(Q(Decimal(v))), UTC)
    if kind == "ems":
        return datetime.fromtimestamp(int(Q(Decimal(v)) / 1000), UTC)
    if kind == "z":
        return datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    if kind == "bz":
        return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    if kind == "off":
        return datetime.fromisoformat(v).astimezone(UTC)
    fmt = {"lw": "%Y-%m-%d %H:%M:%S", "dmy": "%d.%m.%Y %H:%M:%S", "dmys": "%d/%m/%Y %H:%M:%S", "cmp": "%Y%m%d%H%M%S",
           "lt": "%Y-%m-%dT%H:%M:%S"}[kind]
    return clock.utc(datetime.strptime(v, fmt))


def make_record(layout, vals, clock):
    fam, tk, au, mu, du, comma = LAYOUT[layout]
    P, S, I, K, E, T, R, V, W, A, M, D = vals
    area = num(A)
    if au == "mVs":
        area = area / 1000
    amp = num(M)
    if mu == "V":
        amp = amp * 1000
    d = num(D)
    if du == "mi":
        d = d / 1000
    elif du == "ra":
        d = (d - 1) * 1000
    vt = VOID_TRUE[layout]
    void = (V is True) if isinstance(vt, bool) else (str(V).strip().upper() == str(vt).upper())
    return {"project": norm(P), "seq": str(S), "inst": str(I), "counter": int(str(K).strip()), "element": ELEMENT_WORD[norm(E)],
            "ref": norm(T) in REFERENCE_WORD, "rev": int(str(R).strip()), "void": void, "time": stamp(W, tk, clock), "area": area,
            "amp": int(amp), "delta": d}


def read_shard(path, layout, clock):  # noqa: C901
    fam = LAYOUT[layout][0]
    out = []
    if fam in ("csv", "tsv", "psv", "semi", "cc"):
        text = path.read_text(encoding="utf-8")
        if fam == "cc":
            text = "\n".join(x for x in text.splitlines() if not x.startswith("#"))
        sep = {"csv": ",", "tsv": "\t", "psv": "|", "semi": ";", "cc": ","}[fam]
        names = COLS[layout].split()
        for r in csv.DictReader(io.StringIO(text), delimiter=sep):
            out.append(make_record(layout, [r[n] for n in names], clock))
    elif fam == "fx":
        lines = path.read_text(encoding="utf-8").splitlines()
        widths = [10, 16, 9, 5, 5, 4, 4, 5, 16, 11, 7, 9]
        for line in lines[2:]:
            if not line.strip():
                continue
            vals, p = [], 0
            for w in widths:
                vals.append(line[p:p + w].strip())
                p += w
            out.append(make_record(layout, vals, clock))
    elif fam == "md":
        names = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if names is None:
                names = cells
                continue
            if set("".join(cells)) <= set("-"):
                continue
            row = dict(zip(names, cells))
            out.append(make_record(layout, [row[n] for n in COLS[layout].split()], clock))
    elif fam in ("jsonl", "ndf"):
        names = COLS[layout].split()
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                o = json.loads(line)
                out.append(make_record(layout, [o[n] for n in names], clock))
    elif fam == "ndn":
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                o = json.loads(line)
                m, i, p = o["meta"], o["inj"], o["peak"]
                out.append(make_record(layout, [m["project"], m["sequence"], m["instrument"], i["position"], p["gas"], p["type"], o["rev"], o["void"],
                                                i["time"], p["area"], p["height_mv"], p["delta"]], clock))
    elif fam == "jn":
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                o = json.loads(line)
                for p in o["peaks"]:
                    out.append(make_record(layout, [o["project"], o["sequence"], o["instrument"], o["position"], p["gas"], p["type"], p["rev"],
                                                    p["void"], o["time"], p["area"], p["amp"], p["ratio"]], clock))
    elif fam == "jc":
        doc = json.loads(path.read_text(encoding="utf-8"))["export"]
        idx = {c: i for i, c in enumerate(doc["columns"])}
        for row in doc["rows"]:
            out.append(make_record(layout, [row[idx[n]] for n in COLS[layout].split()], clock))
    elif fam == "xa":
        for inj in ET.parse(path).getroot():
            for pk in inj:
                out.append(make_record(layout, [inj.get("project"), inj.get("seq"), inj.get("inst"), inj.get("pos"), pk.get("el"), pk.get("kind"),
                                                pk.get("rev"), pk.get("void"), inj.get("t"), pk.get("area_mvs"), pk.get("amp_mv"), pk.get("d")], clock))
    elif fam == "xc":
        names = COLS[layout].split()
        for rec in ET.parse(path).getroot():
            out.append(make_record(layout, [rec.findtext(n) for n in names], clock))
    elif fam == "yb":
        for blk in yaml_load(path.read_text(encoding="utf-8")):
            for p in blk["peaks"]:
                out.append(make_record(layout, [blk["project"], blk["sequence"], blk["instrument"], blk["position"], p["gas"], p["type"], p["revision"],
                                                p["void"], blk["time"], p["area_vs"], p["amp_mv"], p["delta"]], clock))
    elif fam == "yg":
        for grp in yaml_load(path.read_text(encoding="utf-8"))["sequences"]:
            for p in grp["peaks"]:
                out.append(make_record(layout, [grp["project"], grp["sequence"], grp["instrument"], p["pos"], p["species"], p["kind"], p["rev"],
                                                p["state"], p["t"], p["area_mvs"], p["amp_mv"], p["d"]], clock))
    elif fam == "wide":
        for r in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")), delimiter="\t"):
            for e in ("N", "C"):
                if r[f"rev_{e}"] == "":
                    continue
                out.append(make_record(layout, [r["project"], r["sequence"], r["instrument"], r["counter"], e, "S", r[f"rev_{e}"], r[f"void_{e}"],
                                                r["epoch_ms"], r[f"area_{e}"], r[f"amp_{e}"], r[f"d_{e}"]], clock))
    else:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        if fam == "sqf":
            q = "SELECT project, sequence, instrument, counter, gas, peaktype, revision, void_flag, epoch, area, amplitude, delta FROM export ORDER BY rowid"
            for row in con.execute(q):
                row = list(row)
                row[9], row[10] = repr(row[9]), repr(row[10])
                out.append(make_record(layout, row, clock))
        elif fam == "sqs":
            q = ("SELECT i.project, i.seq, i.inst, i.pos, p.el, p.kind, p.rev, p.voided, i.t_local, p.area_vs, p.amp_mv, p.d_milli "
                 "FROM peaks p JOIN injections i ON i.inj_id = p.inj_id ORDER BY p.peak_id")
            for row in con.execute(q):
                out.append(make_record(layout, list(row), clock))
        elif fam == "sqr":
            q = ("SELECT r.project, r.sequence, r.instrument, p.counter, p.gas, p.peak, p.rev, p.flag, p.t, p.area_mvs, p.amp_mv, p.delta "
                 "FROM peaktab p JOIN runlog r ON r.run_key = p.run_key ORDER BY p.row_id")
            for row in con.execute(q):
                row = list(row)
                row[9], row[11] = repr(row[9]), repr(row[11])
                out.append(make_record(layout, row, clock))
        else:
            recs = {}
            for rec, field, value in con.execute("SELECT rec, field, value FROM kv ORDER BY rec"):
                recs.setdefault(rec, {})[field] = value
            names = COLS[layout].split()
            for k in sorted(recs):
                out.append(make_record(layout, [recs[k][n] for n in names], clock))
        con.close()
    return out


# ----------------------------------------------------------------------------- corpus
CANON_SESSION = re.compile(r"^(SQ|LN)-\d{4}-\d{2}$")
CLASS_OF = {"RM-GLU-L": "RM", "RM-GLU-H": "RM", "RM-CAF": "RM", "QC-SED": "QC", "QC-MUS": "QC", "QC-ALG": "QC", "ELM-ACT": "ELM",
            "BLK": "BLK", "COND": "COND"}


class Corpus:
    def __init__(self, root):  # noqa: C901
        self.root = root
        self.clock = Clock(root / "site_clock.yaml")
        self.profile = yaml_load((root / "analysis_profile.yml").read_text(encoding="utf-8"))
        self.project = norm(self.profile["project"])
        self.elements = [norm(e) for e in self.profile["elements"]]
        self.memo = memo_tables(root / "governance_memo.pdf")
        self.wb = Workbook(root / "reference_workbook.xlsx")
        con = sqlite3.connect(f"file:{root / 'alias_register.sqlite'}?mode=ro", uri=True)
        self.sess_alias = [(norm(a), norm(b), norm(c)) for a, b, c in con.execute("SELECT token, canonical, project FROM session_alias")]
        self.inst_alias = {norm(a): norm(b) for a, b in con.execute("SELECT token, canonical FROM instrument_alias")}
        self.mat_alias = [(norm(a), norm(b), norm(c), d.strip()) for a, b, c, d in con.execute("SELECT token, canonical, project, valid_from FROM material_alias")]
        con.close()
        man = list(csv.DictReader(io.StringIO((root / "sample_manifest.csv").read_text(encoding="utf-8"))))
        self.sample_project = {norm(r["sample_id"]): norm(r["project"]) for r in man}
        self.client = {norm(r["client_id"]): norm(r["sample_id"]) for r in man}
        self.in_force = {k: v for k, v in self.memo.items() if v["status"] == "IN FORCE"}

    # tokens -------------------------------------------------------------
    def session(self, token, project):
        t = norm(token)
        for _ in range(20):
            if CANON_SESSION.match(t):
                return t
            nxt = [b for a, b, p in self.sess_alias if a == t and p in ("*", project)]
            if not nxt:
                return None
            t = nxt[0]
        return None

    def instrument(self, token):
        t = norm(token)
        for _ in range(20):
            if re.fullmatch(r"K\d", t):
                return t
            if t not in self.inst_alias:
                return None
            t = self.inst_alias[t]
        return None

    def material(self, token, project, day):
        t = norm(token)
        for _ in range(20):
            if t in CLASS_OF or t in self.sample_project:
                return t
            rows = [r for r in self.mat_alias if r[0] == t and r[2] in ("*", project) and date.fromisoformat(r[3]) <= day]
            if not rows:
                break
            t = sorted(rows, key=lambda r: r[3])[-1][1]
        return self.client.get(t)


def mat_class(m):
    return CLASS_OF.get(m, "SAMPLE")


def load(root):  # noqa: C901
    C = Corpus(root)
    clock, proj = C.clock, C.project
    # catalog
    cat = json.loads((root / "ingest_catalog.json").read_text(encoding="utf-8"))
    cproj = norm(cat["project"])
    state, layout_of, order = {}, {}, []
    for ev in sorted(cat["events"], key=lambda e: e["event"]):
        f = ev["file"]
        act = norm(ev["action"])
        if act == "VERIFY":
            continue
        sid = C.session(ev["session"], cproj)
        state[(f, sid)] = act
        if act == "REGISTER":
            layout_of.setdefault(f, ev["layout"])
            if f not in order:
                order.append(f)
    active = {k for k, v in state.items() if v == "REGISTER"}
    files = [f for f in order if any(k[0] == f for k in active)]
    # audit admission
    con = sqlite3.connect(f"file:{root / 'reintegration_audit.db'}?mode=ro", uri=True)
    accepted = {norm(r["code"]) for r in C.in_force["C-1"]["rows"] if norm(r["status"]) == "ACCEPTED"}
    latest = {}
    for eid, p, sq, cnt, gas, rv, act, code, when, _an in con.execute("SELECT * FROM audit_trail"):
        sid = C.session(sq, norm(p))
        key = (norm(p), sid, int(cnt), ELEMENT_WORD[norm(gas)], int(rv))
        stamp_ = (when, int(eid))
        if key not in latest or stamp_ > latest[key][0]:
            latest[key] = (stamp_, norm(act), norm(code))
    con.close()
    admitted = {k for k, (_, act, code) in latest.items() if act == "APPROVE" and code in accepted}
    # read records
    seen, cands = set(), {}
    lineage = []
    tot = dict.fromkeys(["records_read", "other_project", "reference_peaks", "inactive_segment", "duplicates"], 0)
    alias_seen = set()
    for f in files:
        recs = read_shard(root / f, layout_of[f], clock)
        info = {"file": f, "layout": layout_of[f], "records": 0, "other_project": 0, "reference_peaks": 0, "inactive_segment": 0,
                "duplicates": 0, "unique": 0}
        for r in recs:
            info["records"] += 1
            if r["project"] != proj:
                info["other_project"] += 1
                continue
            if r["ref"]:
                info["reference_peaks"] += 1
                continue
            sid = C.session(r["seq"], proj)
            if (f, sid) not in active:
                info["inactive_segment"] += 1
                continue
            for kind, tok, can in (("session", r["seq"], sid), ("instrument", r["inst"], C.instrument(r["inst"]))):
                if norm(tok) != can:
                    alias_seen.add((kind, norm(tok), can))
            key = (sid, r["counter"], r["element"], r["rev"])
            if key in seen:
                info["duplicates"] += 1
                continue
            seen.add(key)
            info["unique"] += 1
            r["sid"] = sid
            cands.setdefault(key[:3], {})[r["rev"]] = r
        for k in tot:
            tot[k] += info["records" if k == "records_read" else k]
        lineage.append(info)
    kept, cnt = {}, {"revisions_not_admitted": 0, "revisions_superseded": 0, "voided": 0, "kept": 0}
    for key, revs in cands.items():
        ok = sorted(r for r in revs if r == 0 or (proj, key[0], key[1], key[2], r) in admitted)
        cnt["revisions_not_admitted"] += len(revs) - len(ok)
        cnt["revisions_superseded"] += len(ok) - 1
        top = revs[ok[-1]]
        if top["void"]:
            cnt["voided"] += 1
        else:
            cnt["kept"] += 1
            kept[key] = top
    dedup = {"files_read": len(files), "records_read": tot["records_read"], "other_project": tot["other_project"],
             "reference_peaks": tot["reference_peaks"], "inactive_segment": tot["inactive_segment"], "duplicates": tot["duplicates"]}
    dedup.update(cnt)
    C.dedup, C.lineage, C.kept, C.alias_seen = dedup, lineage, kept, alias_seen
    # sequences
    seqs = {}
    for sq in ET.parse(root / "sequence_tables.xml").getroot():
        p = norm(sq.get("project"))
        if p != proj:
            continue
        sid = C.session(sq.get("id"), p)
        if norm(sq.get("id")) != sid:
            alias_seen.add(("session", norm(sq.get("id")), sid))
        seqs[sid] = {"inst": C.instrument(sq.get("instrument")), "kind": norm(sq.get("kind")),
                     "slots": {int(sl.get("tray")): {"token": sl.get("token"), "capsule": norm(sl.get("capsule") or "")} for sl in sq}}
    C.seqs = seqs
    C.start = {}
    for (sid, c, e), revs in cands.items():
        if c == 1:
            C.start[sid] = next(iter(revs.values()))["time"]
    C.maxc = {}
    for (sid, c, e) in cands:
        C.maxc[sid] = max(C.maxc.get(sid, 0), c)
    return C


# ----------------------------------------------------------------------------- operational records
def settle_positions(C):  # noqa: C901
    root, proj, clock = C.root, C.project, C.clock
    skips = {}
    for line in (root / "autosampler_events.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 7 or norm(parts[4]) != "SKIP" or norm(parts[6]) != "OK":
            continue
        sid = C.session(parts[3], proj)
        skips.setdefault(sid, {})[parts[0]] = int(parts[5].split()[-1])
    C.skip = {sid: sorted(v.values()) for sid, v in skips.items()}
    C.start_local = {sid: clock.local(t) for sid, t in C.start.items()}
    C.day = {sid: w.date() for sid, w in C.start_local.items()}
    # journal
    entries = []
    for line in (root / "tray_corrections.ndjson").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if norm(o.get("project", "")) != proj or norm(o.get("field", "")) != "TOKEN" or norm(o.get("status", "")) != "POSTED":
            continue
        o["sid"] = C.session(o["session"], proj)
        entries.append(o)
        if norm(o["session"]) != o["sid"]:
            C.alias_seen.add(("session", norm(o["session"]), o["sid"]))
    by_seq = {int(o["seq"]): o for o in entries}
    memo = {}

    def live(seq):
        if seq not in memo:
            memo[seq] = True
            memo[seq] = not any(norm(o["action"]) == "REVERSE" and int(o.get("reverses") or -1) == seq and live(int(o["seq"])) for o in entries)
        return memo[seq]

    # all project journal entries (any field or status) contribute alias tokens
    for line in (root / "tray_corrections.ndjson").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if norm(o.get("project", "")) != proj:
            continue
        sid = C.session(o["session"], proj)
        if norm(o["session"]) != sid:
            C.alias_seen.add(("session", norm(o["session"]), sid))
        if norm(o.get("field", "")) == "TOKEN" and str(o.get("value", "")).strip():
            m = C.material(o["value"], proj, C.day[sid])
            if norm(o["value"]) != m:
                C.alias_seen.add(("material", norm(o["value"]), m))
    settled = {}
    for o in entries:
        if norm(o["action"]) == "SET" and live(int(o["seq"])):
            k = (o["sid"], int(o["tray"]))
            if k not in settled or int(o["seq"]) > int(settled[k]["seq"]):
                settled[k] = o
    C.slot = {}
    for sid, sq in C.seqs.items():
        day = C.day[sid]
        for tray, sl in sq["slots"].items():
            tok = sl["token"]
            m0 = C.material(tok, proj, day)
            if norm(tok) != m0:
                C.alias_seen.add(("material", norm(tok), m0))
            j = settled.get((sid, tray))
            mat = C.material(j["value"], proj, day) if j else m0
            C.slot[(sid, tray)] = {"token": tok.strip(), "jseq": int(j["seq"]) if j else None, "material": mat, "class": mat_class(mat),
                                   "capsule": sl["capsule"]}


def load_events(C):
    root, proj, clock = C.root, C.project, C.clock
    C.pause, leak = {}, {}
    for r in csv.DictReader(io.StringIO((root / "session_events.psv").read_text(encoding="utf-8")), delimiter="|"):
        if norm(r["project"]) != proj:
            continue
        sid = C.session(r["session"], proj)
        t = clock.utc(datetime.strptime(r["local_time"].strip(), "%Y-%m-%d %H:%M"))
        ev = norm(r["event"])
        if ev in ("PAUSE", "RESUME"):
            C.pause.setdefault(sid, []).append((t, ev))
        elif ev == "LEAK_CHECK":
            key = (t, int(r["event_id"]))
            if sid not in leak or key > leak[sid][0]:
                leak[sid] = (key, norm(r["detail"]))
    C.leak = {sid for sid, (_, d) in leak.items() if d == "FAIL"}
    C.intervals = {}
    for sid, evs in C.pause.items():
        evs.sort()
        ivs, open_ = [], None
        for t, ev in evs:
            if ev == "PAUSE":
                open_ = t
            elif open_ is not None:
                ivs.append((open_, t))
                open_ = None
        C.intervals[sid] = ivs


def run_minutes(C, sid, t):
    start = C.start[sid]
    sec = (t - start).total_seconds()
    for a, b in C.intervals.get(sid, []):
        lo, hi = max(a, start), min(b, t)
        if hi > lo:
            sec -= (hi - lo).total_seconds()
    return Q(int(sec), 60)


def load_reference(C):  # noqa: C901
    root, wb, P = C.root, C.wb, C.profile
    C.cert = {}
    for r in wb.rows(P["rm_sheet"], "material"):
        C.cert[norm(r["lot"])] = {"N": num(r["d15N_air"]), "C": num(r["d13C_vpdb"])}
    C.qc_assigned = {}
    for r in wb.rows(P["qc_sheet"], "material"):
        if norm(r["status"]) == "CURRENT":
            C.qc_assigned[norm(r["material"])] = {"N": num(r["d15N_air"]), "C": num(r["d13C_vpdb"])}
    C.elm = {}
    for r in wb.rows(P["elemental_sheet"], "material"):
        if norm(r["status"]) == "IN USE":
            C.elm[norm(r["lot"])] = {"N": num(r["N_pct"]), "C": num(r["C_pct"])}
    factors = {}
    for r in csv.DictReader(io.StringIO((root / "balance_calibration.tsv").read_text(encoding="utf-8")), delimiter="\t"):
        factors.setdefault(norm(r["balance"]), []).append((date.fromisoformat(r["valid_from"]), date.fromisoformat(r["valid_to"]), num(r["factor"])))
    C.mass = {}
    for r in wb.rows(P["weights_sheet"], "capsule_id"):
        if not r.get("mass_mg"):
            continue
        day = wb.serial(r["weighed"])
        f = next(fv for a, b, fv in factors[norm(r["balance"])] if a <= day < b)
        C.mass[norm(r["capsule_id"])] = rnd(num(r["mass_mg"]) * f, 4)
    C.lot = {}
    for r in csv.DictReader(io.StringIO((root / "rm_capsule_register.psv").read_text(encoding="utf-8")), delimiter="|"):
        C.lot[norm(r["capsule_id"])] = norm(r["lot"])
    excl_codes = {norm(r["code"]) for r in C.in_force["X-1"]["rows"] if norm(r["effect"]) == "EXCLUDE"}
    C.flag = {}
    for line in (root / "capsule_flags.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            o = json.loads(line)
            if norm(o["code"]) in excl_codes:
                C.flag.setdefault(norm(o["capsule"]), norm(o["code"]))
    M = C.in_force
    C.nset = {norm(r["element"]): r for r in M["N-2"]["rows"]}
    C.amp = {norm(r["element"]): r for r in M["A-1"]["rows"]}
    C.lin_thr = {norm(r["element"]): num(r["threshold_permil_per_vs"]) for r in M["L-1"]["rows"]}
    C.q1 = [(norm(r["material"]), norm(r["element"]), num(r["tolerance_permil"])) for r in M["Q-1"]["rows"]]
    C.grubbs = {int(r["n"]): r for r in M["G-1"]["rows"]}
    C.rulings = [r for r in M["R-1"]["rows"] if norm(r["project"]) == C.project and norm(r["status"]) == "IN FORCE"]
    C.pos_rule = {}
    for r in C.rulings:
        if norm(r["action"]) == "EXCLUDE_POSITION":
            tok, tray = r["target"].rsplit("/", 1)
            C.pos_rule.setdefault((C.session(tok, C.project), int(tray)), r["ruling"])
    C.molar = {}
    for line in (root / "stat_quick_reference.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([CN])\s*\|\s*([0-9.]+)\s*$", line)
        if m:
            C.molar[m.group(1)] = num(m.group(2))


# ----------------------------------------------------------------------------- computation
def build_ledger(C):
    C.ledger, C.by = [], {}
    for (sid, cnt, e), r in sorted(C.kept.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if sid not in C.seqs:
            continue
        tray = cnt + sum(1 for q in C.skip.get(sid, []) if q <= cnt)
        sl = C.slot.get((sid, tray))
        why = ""
        if (sid, tray) in C.pos_rule:
            why = "RULING:" + C.pos_rule[(sid, tray)]
        elif sl and sl["capsule"] in C.flag:
            why = "FLAG:" + C.flag[sl["capsule"]]
        row = {"sid": sid, "inst": C.seqs[sid]["inst"], "cnt": cnt, "tray": tray, "mat": sl["material"], "cls": sl["class"], "e": e,
               "rev": r["rev"], "A": r["area"], "amp": r["amp"], "d": r["delta"], "t": r["time"], "rm": run_minutes(C, sid, r["time"]),
               "why": why, "cap": sl["capsule"]}
        C.ledger.append(row)
        C.by.setdefault((sid, e), []).append(row)


def linearity(C):
    P = C.profile
    nmin = int(P["linearity_min_points"])
    C.lin = {}
    lins = sorted((sid for sid, sq in C.seqs.items() if sq["kind"] == "LINEARITY"), key=lambda s: C.start[s])
    for sid in lins:
        for e in C.elements:
            pts = [r for r in C.by.get((sid, e), []) if r["cls"] == "ELM" and not r["why"]]
            k = None
            if len(pts) >= nmin:
                fit = lsq([r["A"] for r in pts], [r["d"] for r in pts])
                k = rnd(fit[0], 6) if fit else None
            C.lin[(sid, e)] = (len(pts), k)
    C.lin_order = lins
    C.use = {}
    back = int(P["linearity_lookback_days"])
    for sid, sq in C.seqs.items():
        if sq["kind"] != "ANALYTICAL":
            continue
        D = C.day[sid]
        for e in C.elements:
            ok = [l for l in lins if C.seqs[l]["inst"] == sq["inst"] and C.lin[(l, e)][1] is not None]
            same = [l for l in ok if C.day[l] == D and C.start[l] < C.start[sid]]
            prior = [l for l in ok if D - timedelta(days=back) <= C.day[l] <= D - timedelta(days=1)]
            pick = same[-1] if same else (prior[-1] if prior else None)
            if pick is None:
                C.use[(sid, e)] = (None, None, Q(0), "NONE")
            else:
                k = C.lin[(pick, e)][1]
                if abs(k) >= C.lin_thr[e]:
                    C.use[(sid, e)] = (pick, k, k, "APPLIED")
                else:
                    C.use[(sid, e)] = (pick, k, Q(0), "BELOW_THRESHOLD")


def correct(C):  # noqa: C901
    P = C.profile
    aref = {e: num(P["a_ref_vs"][e]) for e in ELEMS_ALL}
    dmat, dmin = norm(P["drift_material"]), int(P["drift_min_points"])
    C.drift, C.blank, C.fit, C.factor, C.acc, C.work = {}, {}, {}, {}, {}, {}
    for sid, sq in sorted(C.seqs.items()):
        if sq["kind"] != "ANALYTICAL":
            continue
        for e in C.elements:
            rows = [r for r in C.by.get((sid, e), []) if not r["why"]]
            k = C.use[(sid, e)][2]
            blanks = [r for r in rows if r["cls"] == "BLK"]
            limit = num(C.amp[e]["blank_area_max_vs"])
            good = [r for r in blanks if r["A"] <= limit]
            Ab = rnd(avg(r["A"] for r in good), 4) if good else Q(0)
            db = rnd(avg(r["d"] for r in good), 3) if good else Q(0)
            C.blank[(sid, e)] = (len(good), len(blanks) - len(good), Ab, db)
            meas = [r for r in rows if r["cls"] in ("RM", "QC", "ELM", "SAMPLE")]
            W = {}
            for r in meas:
                W[r["tray"]] = {"lin": rnd(r["d"] - k * (r["A"] - aref[e]), 4)}
            dp = [r for r in meas if r["mat"] == dmat]
            if len(dp) >= dmin:
                f = lsq([r["rm"] for r in dp], [W[r["tray"]]["lin"] for r in dp])
                slope, st = (rnd(f[0], 8) if f else Q(0)), "FITTED"
            else:
                slope, st = Q(0), "INSUFFICIENT"
            anchor = rnd(avg(r["rm"] for r in dp), 4) if dp else Q(0)
            C.drift[(sid, e)] = (len(dp), slope, anchor, st)
            for r in meas:
                w = W[r["tray"]]
                w["drift"] = rnd(w["lin"] - slope * (r["rm"] - anchor), 4)
                w["blank"] = rnd((w["drift"] * r["A"] - db * Ab) / (r["A"] - Ab), 4)
            # normalization
            ns = C.nset[e]
            rset = [norm(x) for x in ns["reference_set"].split(";")]
            lo, hi = int(C.amp[e]["amplitude_min_mv"]), int(C.amp[e]["amplitude_max_mv"])
            pts = [r for r in meas if r["cls"] == "RM" and r["mat"] in rset and lo <= r["amp"] <= hi]
            info = {"set": rset, "removed": [], "fits": 0, "m": None, "b": None, "n": len(pts), "status": "NO_NORMALIZATION"}
            if all(sum(1 for r in pts if r["mat"] == m) >= 2 for m in rset):
                live = list(pts)
                lim, cap = num(ns["reject_limit_permil"]), int(ns["max_rejections"])
                while True:
                    xs = [W[r["tray"]]["blank"] for r in live]
                    ys = [C.cert[C.lot[r["cap"]]][e] for r in live]
                    m, b = lsq(xs, ys)
                    info["fits"] += 1
                    res = [(y - (m * x + b), r) for x, y, r in zip(xs, ys, live)]
                    big = sorted(res, key=lambda t: (-abs(t[0]), t[1]["tray"]))[0]
                    if abs(big[0]) <= lim:
                        info["status"] = "CONVERGED"
                        break
                    if sum(1 for r in live if r["mat"] == big[1]["mat"]) <= 2:
                        info["status"] = "LIMIT_STOP"
                        break
                    if len(info["removed"]) >= cap:
                        info["status"] = "MAX_REJECT"
                        break
                    info["removed"].append((big[1]["tray"], big[1]["mat"], rnd(big[0], 4)))
                    live = [r for r in live if r is not big[1]]
                info["m"], info["b"], info["n"] = rnd(m, 6), rnd(b, 6), len(live)
            C.fit[(sid, e)] = info
            stds = [r for r in meas if r["cls"] == "ELM" and r["cap"] in C.mass]
            K = None
            if stds:
                K = rnd(avg(C.mass[r["cap"]] * 1000 * C.elm[C.lot[r["cap"]]][e] / 100 / (r["A"] - Ab) for r in stds), 6)
            C.factor[(sid, e)] = (len(stds), K)
            for r in meas:
                w = W[r["tray"]]
                w["norm"] = rnd(info["m"] * w["blank"] + info["b"], 3) if info["m"] is not None else None
                mass = C.mass.get(r["cap"])
                w["pct"] = rnd((r["A"] - Ab) * K / (mass * 1000) * 100, 3) if (K is not None and mass is not None and r["cls"] != "ELM") else None
                C.work[(sid, r["tray"], e)] = (r, w)
            # acceptance
            why = []
            okslope = info["m"] is not None and num(ns["slope_min"]) <= info["m"] <= num(ns["slope_max"])
            if info["m"] is None:
                why.append("NO_NORMALIZATION")
            elif not okslope:
                why.append("SLOPE")
            checks = []
            for mat, el, tol in C.q1:
                if el != e or mat == dmat:
                    continue
                vals = [W[r["tray"]]["norm"] for r in meas if r["mat"] == mat and W[r["tray"]]["norm"] is not None]
                if not vals:
                    continue
                mean = rnd(avg(vals), 3)
                dev = mean - C.qc_assigned[mat][e]
                passed = abs(dev) <= tol
                checks.append((mat, len(vals), mean, C.qc_assigned[mat][e], dev, tol, passed))
                if not passed:
                    why.append("QC:" + mat)
            if sid in C.leak:
                why.append("LEAK")
            computed = "REJECT" if why else "ACCEPT"
            rule = None
            for r in C.rulings:
                if norm(r["action"]) not in ("ACCEPT_SESSION", "REJECT_SESSION"):
                    continue
                if C.session(r["target"], C.project) != sid or norm(r["element"]) not in (e, "ALL"):
                    continue
                if rule is None or (r["date"], r["ruling"]) > (rule["date"], rule["ruling"]):
                    rule = r
            final = computed if rule is None else ("ACCEPT" if norm(rule["action"]) == "ACCEPT_SESSION" else "REJECT")
            C.acc[(sid, e)] = {"ok": okslope, "checks": checks, "leak": sid in C.leak, "computed": computed,
                               "ruling": rule["ruling"] if rule else "", "decision": final, "why": why}


def replicates(C):  # noqa: C901
    root, P, proj = C.root, C.profile, C.project
    req = {}
    for r in csv.DictReader(io.StringIO((root / "client_requests.tsv").read_text(encoding="utf-8")), delimiter="\t"):
        if norm(r["status"]) != "ACTIVE":
            continue
        ref = norm(r["sample_ref"])
        smp = ref if ref in C.sample_project else C.client.get(ref)
        key = (r["requested_on"], r["request_id"])
        if smp and (smp not in req or key > req[smp][0]):
            req[smp] = (key, norm(r["elements"]))
    alpha = "alpha_" + P["grubbs_alpha"]
    C.scope = sorted(norm(s) for s in P["samples_in_scope"] if C.sample_project.get(norm(s)) == proj)
    C.res, C.screen = {}, []
    for smp in C.scope:
        wanted = req[smp][1].split("+") if smp in req else ["N", "C"]
        for e in C.elements:
            if e not in wanted:
                C.res[(smp, e)] = {"status": "NOT_REQUESTED"}
                continue
            vals = []
            for (sid, tray, el), (r, w) in C.work.items():
                if el == e and r["mat"] == smp and w["norm"] is not None and C.acc[(sid, e)]["decision"] == "ACCEPT":
                    vals.append((C.start[sid], tray, w["norm"], w["pct"]))
            vals.sort(key=lambda v: (v[0], v[1]))
            keep, gone = list(vals), []
            while len(keep) >= 3:
                xs = [v[2] for v in keep]
                mu = avg(xs)
                ss = sum(((x - mu) ** 2 for x in xs), Q(0)) / (len(xs) - 1)
                if ss == 0:
                    break
                far = max(range(len(xs)), key=lambda i: (abs(xs[i] - mu), -i))
                crit = num(C.grubbs[len(xs)][alpha])
                if (xs[far] - mu) ** 2 > crit * crit * ss:
                    gone.append((xs[far], dsqrt((xs[far] - mu) ** 2 / ss, 4), C.grubbs[len(xs)][alpha], len(xs)))
                    keep.pop(far)
                else:
                    break
            n = len(keep)
            out = {"n": n, "status": "REPORTED" if n >= 2 else ("SINGLE" if n == 1 else "NO_DATA")}
            if n:
                xs = [v[2] for v in keep]
                out["mean"] = rnd(avg(xs), 2)
                if n >= 2:
                    mu = avg(xs)
                    out["sd"] = dsqrt(sum(((x - mu) ** 2 for x in xs), Q(0)) / (n - 1), 2)
                pc = [v[3] for v in keep if v[3] is not None]
                out["pct"] = rnd(avg(pc), 2) if pc else None
            C.res[(smp, e)] = out
            if vals:
                C.screen.append((smp, e, [v[2] for v in vals], gone, n))


# ----------------------------------------------------------------------------- reports
def table(cols, rows, sep):
    buf = io.StringIO()
    wr = csv.writer(buf, delimiter=sep, lineterminator="\n")
    wr.writerow(cols.split(","))
    for row in rows:
        wr.writerow(["" if v is None else v for v in row])
    return buf.getvalue()


def comparisons(C):  # noqa: C901
    root = C.root
    pub = {}
    for r in csv.DictReader(io.StringIO((root / "published_results.csv").read_text(encoding="utf-8"))):
        for e, col in (("N", "d15N_air"), ("C", "d13C_vpdb")):
            if r[col].strip():
                pub[(norm(r["sample_id"]), e)] = num(r[col])
    cache = {}
    for line in (root / "lims_result_cache.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            o = json.loads(line)
            cache[(norm(o["sample"]), norm(o["element"]))] = num(o["value"])
    params = json.loads((root / "published_session_params.json").read_text(encoding="utf-8"))
    pp = {(C.session(o["session"], C.project), norm(o["element"])): (num(o["slope"]), num(o["intercept"]), int(o["rm_points"]))
          for o in params["sessions"]}
    dash = {}
    for r in csv.DictReader(io.StringIO((root / "qc_dashboard.csv").read_text(encoding="utf-8"))):
        k = (C.session(r["session"], C.project), norm(r["element"]))
        dash[k] = "FAIL" if (dash.get(k) == "FAIL" or norm(r["status"]) == "FAIL") else "PASS"
    notes = []
    for line in (root / "lab_noticeboard.txt").read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 4 and parts[2] == "REFERENCE":
            m = re.search(r"(\S+) lot (\S+) (d15N|d13C) (-?\d+\.\d+) permil", parts[3])
            if m:
                notes.append((parts[0], m.group(1), m.group(2), "N" if m.group(3) == "d15N" else "C", m.group(4)))
    settings, inside = [], False
    for line in (root / "rerun_pack.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Run settings"
            continue
        if inside and line.startswith("|") and not line.startswith("|---"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells[0] != "setting":
                settings.append((cells[0], cells[1]))
    return pub, cache, pp, dash, notes, settings


def params_list(C):
    P = C.profile
    kv = [("project", C.project), ("rm_sheet", P["rm_sheet"]), ("normalization_table", "N-2")]
    for e in C.elements:
        ns, am = C.nset[e], C.amp[e]
        kv += [("reference_set_" + e, ns["reference_set"].replace(";", ",")), ("reject_limit_" + e, ns["reject_limit_permil"]),
               ("max_reject_" + e, ns["max_rejections"]), ("linearity_threshold_" + e, txt(C.lin_thr[e], 4)), ("a_ref_" + e, P["a_ref_vs"][e]),
               ("amplitude_min_" + e, am["amplitude_min_mv"]), ("amplitude_max_" + e, am["amplitude_max_mv"]), ("blank_area_max_" + e, am["blank_area_max_vs"])]
    first = C.nset[C.elements[0]]
    kv += [("slope_min", first["slope_min"]), ("slope_max", first["slope_max"]), ("linearity_lookback_days", P["linearity_lookback_days"]),
           ("drift_material", norm(P["drift_material"])), ("drift_min_points", P["drift_min_points"]), ("grubbs_table", "G-1"),
           ("grubbs_alpha", P["grubbs_alpha"]), ("molar_mass_C", str(Decimal(C.molar["C"].numerator) / Decimal(C.molar["C"].denominator))),
           ("molar_mass_N", str(Decimal(C.molar["N"].numerator) / Decimal(C.molar["N"].denominator))),
           ("date_system", "1904" if C.wb.d1904 else "1900"), ("clock_base_offset", C.clock.base_text)]
    dmat = norm(P["drift_material"])
    for mat, el, tol in C.q1:
        if mat != dmat and el in C.elements:
            kv.append((f"qc_tolerance_{mat}_{el}", txt(tol, 2)))
    return kv


def render(C):  # noqa: C901
    els = C.elements
    rank = {e: i for i, e in enumerate(els)}
    R = {}
    rows = [[r["sid"], r["inst"], r["cnt"], r["tray"], r["mat"], r["e"], r["rev"], txt(r["A"], 4), r["amp"], txt(r["d"], 3),
             r["t"].strftime("%Y-%m-%dT%H:%M:%SZ"), txt(r["rm"], 4), r["why"]] for r in sorted(C.ledger, key=lambda r: (r["sid"], r["cnt"], rank[r["e"]]))]
    R["injection_ledger.csv"] = table("session,instrument,counter_position,tray_position,material,element,revision,area_vs,amplitude_mv,"
                                      "delta_raw,utc_time,run_minutes,excluded", rows, ",")
    rows = []
    excluded = {(r["sid"], r["tray"]) for r in C.ledger if r["why"]}
    for sid in sorted(C.seqs):
        reach = {}
        for c in range(1, C.maxc.get(sid, 0) + 1):
            reach[c + sum(1 for q in C.skip.get(sid, []) if q <= c)] = c
        for tray in sorted(C.seqs[sid]["slots"]):
            sl = C.slot[(sid, tray)]
            status = "SKIPPED" if tray not in reach else ("EXCLUDED" if (sid, tray) in excluded else "MEASURED")
            rows.append([sid, tray, reach.get(tray, ""), sl["token"], sl["jseq"] or "", sl["material"], sl["class"], sl["capsule"],
                         txt(C.mass[sl["capsule"]], 4) if sl["capsule"] in C.mass else "", status])
    R["position_resolution.csv"] = table("session,tray_position,counter_position,sequence_token,journal_seq,material,material_class,capsule_id,"
                                         "mass_mg,status", rows, ",")
    R["alias_resolution.psv"] = table("kind,token,canonical", sorted(C.alias_seen), "|")
    R["dedup_report.json"] = to_json(C.dedup) + "\n"
    R["source_lineage.json"] = to_json({"files": C.lineage}) + "\n"
    ana = sorted(s for s, q in C.seqs.items() if q["kind"] == "ANALYTICAL")
    lin_rows = [{"session": s, "instrument": C.seqs[s]["inst"], "local_date": C.day[s].isoformat(), "element": e, "n_points": C.lin[(s, e)][0],
                 "slope": jnum(C.lin[(s, e)][1], 6)} for s in sorted(C.lin_order) for e in els]
    use_rows = [{"session": s, "element": e, "lin_session": C.use[(s, e)][0], "lin_slope": jnum(C.use[(s, e)][1], 6),
                 "applied_slope": jnum(C.use[(s, e)][2], 6), "status": C.use[(s, e)][3]} for s in ana for e in els]
    R["linearity_slopes.json"] = to_json({"lin_sessions": lin_rows, "assignments": use_rows}) + "\n"
    dm = norm(C.profile["drift_material"])
    R["drift_fits.tsv"] = table("session,element,drift_material,n_points,slope_per_min,anchor_min,status",
                                [[s, e, dm, C.drift[(s, e)][0], txt(C.drift[(s, e)][1], 8), txt(C.drift[(s, e)][2], 4), C.drift[(s, e)][3]]
                                 for s in ana for e in els], "\t")
    R["blank_corrections.psv"] = table("session,element,n_blanks,n_rejected,mean_area_vs,mean_delta",
                                       [[s, e, C.blank[(s, e)][0], C.blank[(s, e)][1], txt(C.blank[(s, e)][2], 4), txt(C.blank[(s, e)][3], 3)]
                                        for s in ana for e in els], "|")
    fits = []
    for s in ana:
        for e in els:
            f = C.fit[(s, e)]
            fits.append({"session": s, "element": e, "reference_set": f["set"], "n_points": f["n"], "fits": f["fits"], "slope": jnum(f["m"], 6),
                         "intercept": jnum(f["b"], 6), "removed": [{"tray_position": t, "material": m, "residual": jnum(v, 4)} for t, m, v in f["removed"]],
                         "status": f["status"]})
    R["normalization_fits.json"] = to_json({"fits": fits}) + "\n"
    lines = []
    for key in sorted(C.work, key=lambda k: (k[0], k[1], rank[k[2]])):
        r, w = C.work[key]
        lines.append(to_json({"session": key[0], "tray_position": key[1], "material": r["mat"], "material_class": r["cls"], "element": key[2],
                              "d_lin": jnum(w["lin"], 4), "d_drift": jnum(w["drift"], 4), "d_blank": jnum(w["blank"], 4), "d_norm": jnum(w["norm"], 3),
                              "pct": jnum(w["pct"], 3)}) + "\n")
    R["corrected_injections.jsonl"] = "".join(lines)
    R["elemental_factors.tsv"] = table("session,element,n_standards,factor_ug_per_vs",
                                       [[s, e, C.factor[(s, e)][0], txt(C.factor[(s, e)][1], 6)] for s in ana for e in els], "\t")
    rows, xml = [], ['<?xml version="1.0" encoding="UTF-8"?>', f'<qc_results project="{C.project}">']
    for s in ana:
        for e in els:
            a, f = C.acc[(s, e)], C.fit[(s, e)]
            rows.append([s, e, C.seqs[s]["inst"], txt(f["m"], 6), "Y" if a["ok"] else "N",
                         ";".join(f"{m}:{txt(d, 3)}:{'PASS' if p else 'FAIL'}" for m, n, mean, asg, d, tol, p in a["checks"]),
                         "Y" if a["leak"] else "N", a["computed"], a["ruling"], a["decision"], ";".join(a["why"])])
            for m, n, mean, asg, d, tol, p in a["checks"]:
                xml.append(f'  <check session="{s}" element="{e}" material="{m}" n="{n}" mean="{txt(mean, 3)}" assigned="{txt(asg, 2)}" '
                           f'deviation="{txt(d, 3)}" tolerance="{txt(tol, 2)}" result="{"PASS" if p else "FAIL"}"/>')
    xml.append("</qc_results>")
    R["session_acceptance.csv"] = table("session,element,instrument,norm_slope,slope_ok,qc_checks,leak,computed,ruling,decision,reasons", rows, ",")
    R["qc_results.xml"] = "\n".join(xml) + "\n"
    rows = []
    for smp in C.scope:
        line = [smp]
        got = {}
        for e in ("N", "C"):
            r = C.res.get((smp, e), {"status": "NOT_REQUESTED"})
            got[e] = r
            if r["status"] == "NOT_REQUESTED":
                line += ["", "", "", "", "NOT_REQUESTED"]
            else:
                line += [txt(r.get("mean"), 2), r.get("sd", ""), r["n"], txt(r.get("pct"), 2), r["status"]]
        cn = ""
        if got["N"]["status"] in ("REPORTED", "SINGLE") and got["C"]["status"] in ("REPORTED", "SINGLE") and got["N"].get("pct") and got["C"].get("pct") is not None:
            cn = txt((got["C"]["pct"] / C.molar["C"]) / (got["N"]["pct"] / C.molar["N"]), 2)
        rows.append(line + [cn])
    R["isotope_results.csv"] = table("sample_id,d15N_air,d15N_sd,n_N,pct_N,status_N,d13C_vpdb,d13C_sd,n_C,pct_C,status_C,cn_molar", rows, ",")
    lines = []
    for smp, e, vals, gone, n in sorted(C.screen, key=lambda x: (x[0], rank[x[1]])):
        lines.append(to_json({"sample": smp, "element": e, "initial_n": len(vals), "values": [jnum(v, 3) for v in vals],
                              "removed": [{"value": jnum(v, 3), "g": Num(Q(Decimal(g)), 4), "g_crit": Num(num(gc), 4), "n": k} for v, g, gc, k in gone],
                              "final_n": n}) + "\n")
    R["replicate_screening.jsonl"] = "".join(lines)
    R["parameters_used.yaml"] = "".join(f"{k}: {v}\n" for k, v in params_list(C))
    pub, cache, pp, dash, notes, settings = comparisons(C)
    rec = {k: v["mean"] for k, v in C.res.items() if v["status"] in ("REPORTED", "SINGLE")}
    rows = []
    for k in sorted(set(pub) | set(rec), key=lambda k: (k[0], rank[k[1]])):
        a, b = pub.get(k), rec.get(k)
        if a is None:
            rows.append([k[0], k[1], "", txt(b, 2), "", "ONLY_RECOMPUTED"])
        elif b is None:
            rows.append([k[0], k[1], txt(a, 2), "", "", "ONLY_PUBLISHED"])
        else:
            rows.append([k[0], k[1], txt(a, 2), txt(b, 2), txt(b - a, 2), "MATCH" if abs(b - a) <= Q(5, 100) else "DIFF"])
    R["variance_vs_published.csv"] = table("sample_id,element,published,recomputed,diff,status", rows, ",")
    out = []
    for (s, e), (m, b, n) in sorted(pp.items(), key=lambda kv: (kv[0][0], rank[kv[0][1]])):
        f = C.fit.get((s, e), {})
        rm, rb = f.get("m"), f.get("b")
        out.append({"session": s, "element": e, "published_slope": jnum(m, 6), "recomputed_slope": jnum(rm, 6), "published_intercept": jnum(b, 6),
                    "recomputed_intercept": jnum(rb, 6), "slope_diff": jnum(None if rm is None else rm - m, 6),
                    "intercept_diff": jnum(None if rb is None else rb - b, 6), "published_points": n, "recomputed_points": f.get("n") if rm is not None else None})
    R["session_param_diff.json"] = to_json({"sessions": out}) + "\n"
    rows = []
    for (s, e), st in sorted(dash.items(), key=lambda kv: (kv[0][0], rank[kv[0][1]])):
        d = C.acc[(s, e)]["decision"]
        rows.append([s, e, st, d, "Y" if (st == "PASS") == (d == "ACCEPT") else "N"])
    R["dashboard_disagreements.csv"] = table("session,element,dashboard_status,recomputed_decision,agrees", rows, ",")
    lines = []
    for (smp, e), v in sorted(cache.items(), key=lambda kv: (kv[0][0], rank[kv[0][1]])):
        b = rec.get((smp, e))
        lines.append(to_json({"sample": smp, "element": e, "cached": jnum(v, 2), "recomputed": jnum(b, 2),
                              "status": "STALE" if b is None or abs(b - v) > Q(5, 100) else "CURRENT"}) + "\n")
    R["cache_divergence.jsonl"] = "".join(lines)
    md = [f"# {C.project} reconciliation", "", "## Summary", "", "| element | recomputed_reported | published_reported | compared | diff_count | mean_shift |",
          "|---|---|---|---|---|---|"]
    for e in els:
        mine = [k for k in rec if k[1] == e]
        theirs = [k for k in pub if k[1] == e]
        both = [k for k in mine if k in pub]
        d = [rec[k] - pub[k] for k in both]
        md.append(f"| {e} | {len(mine)} | {len(theirs)} | {len(both)} | {sum(1 for x in d if abs(x) > Q(5, 100))} | {txt(avg(d), 3) if d else ''} |")
    md += ["", "## Session decisions", "", "| session | element | computed | ruling | decision | reasons |", "|---|---|---|---|---|---|"]
    for s in ana:
        for e in els:
            a = C.acc[(s, e)]
            if a["decision"] == "REJECT" or a["ruling"] or a["computed"] == "REJECT":
                md.append(f"| {s} | {e} | {a['computed']} | {a['ruling']} | {a['decision']} | {';'.join(a['why'])} |")
    fixed = {"rm_sheet": C.profile["rm_sheet"], "normalization_table": "N-2", "grubbs_table": "G-1", "drift_axis": "run_minutes",
             "linearity_partition": "instrument_local_day", "correction_order": "linearity,drift,blank,normalization", "revision_rule": "audit_admitted",
             "autosampler_skips": "applied", "session_rulings": "R-1_in_force", "arithmetic": "exact_decimal_stage_rounding"}
    for e in ELEMS_ALL:
        fixed["reference_set_" + e] = C.nset[e]["reference_set"].replace(";", ",")
    md += ["", "## Run settings", "", "| setting | published_run | in_force |", "|---|---|---|"]
    md += [f"| {k} | {v} | {fixed.get(k, '')} |" for k, v in settings]
    md += ["", "## Superseded notices", "", "| notice | material | lot | element | notice_value | in_force_value |", "|---|---|---|---|---|---|"]
    for nid, mat, lot, e, val in sorted(notes):
        if lot in C.cert and C.cert[lot][e] != num(val):
            md.append(f"| {nid} | {mat} | {lot} | {e} | {val} | {txt(C.cert[lot][e], 2)} |")
    R["reconciliation.md"] = "\n".join(md) + "\n"
    return R


ORDER = ("injection_ledger.csv position_resolution.csv alias_resolution.psv dedup_report.json source_lineage.json linearity_slopes.json "
         "drift_fits.tsv blank_corrections.psv normalization_fits.json corrected_injections.jsonl elemental_factors.tsv session_acceptance.csv "
         "qc_results.xml isotope_results.csv replicate_screening.jsonl parameters_used.yaml variance_vs_published.csv session_param_diff.json "
         "dashboard_disagreements.csv cache_divergence.jsonl reconciliation.md").split()


def main(argv):
    if len(argv) != 3:
        sys.exit("usage: run_irms.py DATA_DIR OUT_DIR")
    root, out = Path(argv[1]), Path(argv[2])
    C = load(root)
    settle_positions(C)
    load_events(C)
    load_reference(C)
    build_ledger(C)
    linearity(C)
    correct(C)
    replicates(C)
    R = render(C)
    out.mkdir(parents=True, exist_ok=True)
    man = []
    for name in ORDER:
        blob = R[name].encode("utf-8")
        (out / name).write_bytes(blob)
        man.append({"name": name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()})
    (out / "manifest.json").write_text(json.dumps({"files": man}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv)
