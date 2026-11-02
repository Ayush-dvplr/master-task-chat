#!/usr/bin/env python3
"""Season storage balancing and conveyance loss accounting (reference solution).

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Reads the extract in DATA_DIR, balances the four closed basins, accounts the conveyance loss of every net gauging
and writes the thirty-one reports of layout_reports.md into OUT_DIR. Everything is settled in memory first; nothing is
written when an input breaks a documented rule.
"""
import configparser
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
from fractions import Fraction
from pathlib import Path

BASINS = ("North", "South", "West", "East")
SEGMENTS = ("commercial", "public")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
SENSE = {
    "csv": {"fwd": Fraction(0), "rev": Fraction(1), "nil": Fraction(1, 2)},
    "tsv": {"0": Fraction(0), "1": Fraction(1), "0.5": Fraction(1, 2)},
    "jsonl": {"to": Fraction(0), "from": Fraction(1), "neither": Fraction(1, 2)},
}


class InputRuleError(Exception):
    """An input breaks a rule its dictionary states."""


def round_half_away(value):
    """Nearest integer to a Fraction; an exact half goes away from zero."""
    sign = -1 if value < 0 else 1
    mag = abs(value)
    whole = mag.numerator // mag.denominator
    if mag - whole >= Fraction(1, 2):
        whole += 1
    return sign * whole


def station_number(code):
    return int(code[len("RS-"):])


def read_catchments(data):
    ns = "{urn:basin-authority:catchments}"
    root = ET.parse(data / "bs_map.xml").getroot()
    return {c.get("code"): c.find(ns + "basin").text for c in root.iter(ns + "catchment")}


def read_varint(blob, pos):
    """Zigzag value of the unsigned LEB128 varint at pos; returns (value, next pos)."""
    u = shift = 0
    while True:
        if pos >= len(blob):
            raise InputRuleError("meter file ends inside a varint")
        b = blob[pos]
        pos += 1
        u |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return (u >> 1) if u % 2 == 0 else -((u + 1) >> 1), pos


def season_day(n):
    """Day n of the season, day 1 being 1 July 2026."""
    for month, length in ((7, 31), (8, 31), (9, 30)):
        if 1 <= n <= length:
            return f"2026-{month:02d}-{n:02d}"
        n -= length
    raise InputRuleError("meter correction day outside the season")


class MeterReader:
    """Decoder state of ob_s3.bin: position, gauge dictionary and running value."""

    def __init__(self, blob):
        if len(blob) < 18 or blob[:4] != b"OBS3" or blob[4] != 1:
            raise InputRuleError("meter file header is not OBS3 version 1")
        if zlib.crc32(blob[4:-4]) != int.from_bytes(blob[-4:], "big"):
            raise InputRuleError("meter file checksum does not match")
        self.blob, self.end, self.pos = blob, len(blob) - 4, 14
        self.label = blob[5:12].decode("ascii")
        self.count = int.from_bytes(blob[12:14], "big")
        self.dictionary, self.running = [], 0

    def take(self, n):
        if self.pos + n > self.end:
            raise InputRuleError("meter record runs past the checksum")
        part = self.blob[self.pos:self.pos + n]
        self.pos += n
        return part

    def gauge(self, by_reference):
        if by_reference:
            index = self.take(1)[0]
            if index >= len(self.dictionary):
                raise InputRuleError("meter back-reference past the gauge dictionary")
            return self.dictionary[index]
        number = f"G{int.from_bytes(self.take(2), 'big')}"
        if number not in self.dictionary:
            self.dictionary.append(number)
        return number

    def value(self, as_delta):
        if self.pos >= self.end:
            raise InputRuleError("meter record runs past the checksum")
        value, self.pos = read_varint(self.blob[:self.end], self.pos)
        value = value + self.running if as_delta else value
        self.running = value
        return value

    def record(self):
        sel = self.take(1)[0]
        kind = sel >> 6
        if kind == 3:
            raise InputRuleError("meter record of kind 3")
        if kind == 2:
            return ("R", self.gauge(sel & 0x20), self.gauge(sel & 0x08))
        if sel & 0x08:
            raise InputRuleError("bit 3 set on a reading or correction record")
        gauge = self.gauge(sel & 0x20)
        value = self.value(sel & 0x10)
        if kind == 1:
            return ("C", gauge, value, season_day(self.take(1)[0]))
        return ("D", gauge, value)


def read_meter(data):
    """Records of ob_s3.bin in file order."""
    reader = MeterReader((data / "ob_s3.bin").read_bytes())
    records = [reader.record() for _ in range(reader.count)]
    if reader.pos != reader.end:
        raise InputRuleError("meter file holds bytes after its last record")
    return records


def corrected_readings(records, survey_day):
    """Reading per current gauge number after the corrections dated on or before the survey date."""
    current = {old: new for kind, old, new, *_ in records if kind == "R"}
    reading, applied = {}, {}
    for rec in records:
        if rec[0] == "D":
            reading[rec[1]] = rec[2]
    for rec in records:
        if rec[0] == "C" and rec[3] <= survey_day:
            gauge = current.get(rec[1], rec[1])
            if rec[3] >= applied.get(gauge, ""):
                reading[gauge], applied[gauge] = rec[2], rec[3]
    return reading


def read_survey(data):
    with open(data / "sv_survey.csv", newline="", encoding="utf-8") as fh:
        rows = [(r["surveyed_on"], r["stations"].split(";"), int(r["total_ml"])) for r in csv.DictReader(fh)]
    days = {d for d, _s, _t in rows}
    if len(days) != 1:
        raise InputRuleError("survey rows carry more than one survey date")
    return days.pop(), [(s, t) for _d, s, t in rows]


def survey_constraints(reaches, catchment_of, reading):
    """Per survey row: ({catchment: stations listed}, lowest and highest datum sum the floored total allows)."""
    rows = []
    for stations, total in reaches:
        count = {}
        for stn in stations:
            if stn not in catchment_of:
                raise InputRuleError(f"survey names unknown station {stn}")
            count[catchment_of[stn]] = count.get(catchment_of[stn], 0) + 1
        base = total - sum(reading[stn] for stn in stations)
        rows.append((count, base, base + 9))
    return rows


def independent_rows(rows, cats):
    """Indices of the first len(cats) linearly independent rows, or None when the rows do not reach full rank."""
    kept, chosen = [], []
    for r, (count, _lo, _hi) in enumerate(rows):
        vec = [Fraction(count.get(c, 0)) for c in cats]
        for piv, ref in kept:
            if vec[piv]:
                f = vec[piv] / ref[piv]
                vec = [a - f * b for a, b in zip(vec, ref)]
        piv = next((i for i, x in enumerate(vec) if x), None)
        if piv is not None:
            kept.append((piv, vec))
            chosen.append(r)
            if len(chosen) == len(cats):
                return chosen
    return None


def inverse(matrix):
    """Inverse of a square Fraction matrix by Gauss-Jordan elimination."""
    n = len(matrix)
    m = [list(row) + [Fraction(int(i == j)) for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        piv = next(i for i in range(col, n) if m[i][col])
        m[col], m[piv] = m[piv], m[col]
        m[col] = [x / m[col][col] for x in m[col]]
        for i in range(n):
            if i != col and m[i][col]:
                f = m[i][col]
                m[i] = [x - f * y for x, y in zip(m[i], m[col])]
    return [row[n:] for row in m]


def fits(rows, value):
    return all(lo <= sum(k * value[c] for c, k in count.items()) <= hi for count, lo, hi in rows)


def bounded_fits(rows, cats):
    """Rank-deficient survey: enumerate the datum steps -19..19 catchment by catchment, pruning every row whose
    window can no longer be met by the catchments still open; stop at the second fit."""
    found = []

    def walk(i, value):
        for coef, lo, hi in rows:
            done = sum(n * value[c] for c, n in coef.items() if c in value)
            left = sum(n for c, n in coef.items() if c not in value)
            if done + 5 * 19 * left < lo or done - 5 * 19 * left > hi:
                return
        if len(found) > 1:
            return
        if i == len(cats):
            if fits(rows, value):
                found.append(dict(value))
            return
        for k in range(-19, 20):
            value[cats[i]] = 5 * k
            walk(i + 1, value)
            del value[cats[i]]
            if len(found) > 1:
                return

    walk(0, {})
    return found


def solve_datums(rows, cats):
    """Every datum assignment (multiples of 5 from -95 to 95) meeting all survey rows, at most two.

    A fit meets each of n independent rows at one of the two multiples of 5 its window holds, so solving the
    2**n choices of those sums lists every candidate."""
    chosen = independent_rows(rows, cats)
    if chosen is None:
        return bounded_fits(rows, cats)
    inv = inverse([[Fraction(rows[r][0].get(c, 0)) for c in cats] for r in chosen])
    first = [-(-rows[r][1] // 5) for r in chosen]
    found = []
    for mask in range(1 << len(cats)):
        sums = [f + ((mask >> j) & 1) for j, f in enumerate(first)]
        steps = [sum(a * b for a, b in zip(row, sums)) for row in inv]
        if all(x.denominator == 1 and -19 <= x <= 19 for x in steps):
            value = {c: 5 * int(x) for c, x in zip(cats, steps)}
            if fits(rows, value):
                found.append(value)
                if len(found) > 1:
                    break
    return found


def read_register(data):
    con = sqlite3.connect(f"file:{data / 'stn_core.sqlite'}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT stn, station_name, catchment FROM station").fetchall()
    finally:
        con.close()
    basin_of = read_catchments(data)
    with open(data / "xw_codes.csv", newline="", encoding="utf-8") as fh:
        gauge_of = {row["stn"]: row["gauge_no"] for row in csv.DictReader(fh)}
    records = read_meter(data)
    survey_day, reaches = read_survey(data)
    reading = corrected_readings(records, survey_day)
    register, catchment_of = {}, {}
    for stn, name, catchment in rows:
        if stn in register:
            raise InputRuleError(f"station {stn} occurs twice in the register authority")
        register[stn] = {"name": name, "basin": basin_of[catchment], "catchment": catchment, "gauge": gauge_of[stn]}
        catchment_of[stn] = catchment
    by_station = {stn: reading[info["gauge"]] for stn, info in register.items()}
    survey = survey_constraints(reaches, catchment_of, by_station)
    found = solve_datums(survey, sorted(set(catchment_of.values())))
    if len(found) != 1:
        raise InputRuleError("the survey fits no datum assignment" if not found else "the survey fits more than one datum assignment")
    raw = {rec[1]: rec[2] for rec in records if rec[0] == "D"}
    for stn, info in register.items():
        info["opening"] = by_station[stn] + found[0][info["catchment"]]
        info["meter"] = raw[info["gauge"]]
    return register, basin_of


def mirror_mismatches(data, register):
    with open(data / "stn_mirror.csv", newline="", encoding="utf-8") as fh:
        mirror = {row["stn"]: row for row in csv.DictReader(fh)}
    count = 0
    for stn, info in register.items():
        row = mirror.get(stn)
        same = row is not None and (row["station_name"], row["basin"], row["reading_ml"]) == (
            info["name"], info["basin"], str(info["meter"]))
        count += 0 if same else 1
    return count


def read_gaugings(data):
    """Returns ({gauging id: [licence, from, to, from draw points]}, records read)."""
    found = {}
    rows = []
    with open(data / "gx_a.csv", newline="", encoding="utf-8") as fh:
        rows += [(r["gauging_id"], r["licence"], r["from_stn"], r["to_stn"], SENSE["csv"][r["sense"]])
                 for r in csv.DictReader(fh)]
    with open(data / "gx_b.tsv", newline="", encoding="utf-8") as fh:
        rows += [(r["gid"], r["lic"], r["upper"], r["lower"], SENSE["tsv"][r["drawn_upper"]])
                 for r in csv.DictReader(fh, delimiter="\t")]
    for line in (data / "gx_c.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            obj = json.loads(line)
            rows.append((obj["id"], obj["licence"], obj["ends"][0], obj["ends"][1], SENSE["jsonl"][obj["drawn_by"]]))
    for gid, lic, frm, to, pts in rows:
        if gid in found:
            raise InputRuleError(f"gauging {gid} is recorded more than once")
        found[gid] = [lic, frm, to, pts]
    return found, len(rows)


def apply_revisions(data, gaugings, cutoff):
    with open(data / "rv_log.psv", newline="", encoding="utf-8") as fh:
        lines = sorted(csv.DictReader(fh, delimiter="|"), key=lambda r: int(r["seq"]))
    if len({int(line["seq"]) for line in lines}) != len(lines):
        raise InputRuleError("a seq number occurs twice in the revision log")
    counts = {"revisions_applied": 0, "revisions_after_cutoff": 0, "revisions_unmatched": 0}
    last = {}
    for line in lines:
        if int(line["seq"]) > cutoff:
            counts["revisions_after_cutoff"] += 1
        elif line["gauging_id"] in gaugings:
            counts["revisions_applied"] += 1
            last[line["gauging_id"]] = line
        else:
            counts["revisions_unmatched"] += 1
    net = {}
    voided = 0
    for gid, (lic, frm, to, pts) in gaugings.items():
        rev = last.get(gid)
        if rev is not None and rev["action"] == "void":
            voided += 1
            continue
        if rev is not None:
            pts = SENSE["csv"][rev["value"]]
        net[gid] = (lic, frm, to, pts)
    counts["gaugings_voided"] = voided
    return net, counts


def check_register_rules(gaugings, register):
    for gid, (_lic, frm, to, _pts) in gaugings.items():
        if frm not in register or to not in register:
            raise InputRuleError(f"gauging {gid} names a station the register authority lacks")
        if register[frm]["basin"] != register[to]["basin"]:
            raise InputRuleError(f"gauging {gid} joins two basins")


def main_part(zf):
    """The package's main part, as the package relationships name it (ECMA-376 package conventions)."""
    for rel in ET.fromstring(zf.read("_rels/.rels")):
        if rel.get("Type", "").endswith("/officeDocument"):
            return rel.get("Target").lstrip("/")
    raise InputRuleError("package names no main part")


def read_workbook(path):
    with zipfile.ZipFile(path) as zf:
        book = main_part(zf)
        folder, _sep, base = book.rpartition("/")
        links = list(ET.fromstring(zf.read(f"{folder}/_rels/{base}.rels")))
        targets = {r.get("Id"): r.get("Target") for r in links}
        shared = []
        for rel in links:
            if rel.get("Type", "").endswith("/sharedStrings"):
                for si in ET.fromstring(zf.read(folder + "/" + rel.get("Target"))).iter(NS + "si"):
                    runs = si.findall(NS + "t") + [t for r in si.findall(NS + "r") for t in r.findall(NS + "t")]
                    shared.append("".join(t.text or "" for t in runs))  # phonetic runs (rPh) are not cell text
        sheets = {}
        for sheet in ET.fromstring(zf.read(book)).iter(NS + "sheet"):
            rows = []
            for row in ET.fromstring(zf.read(folder + "/" + targets[sheet.get(RNS + "id")])).iter(NS + "row"):
                cells = []
                for cell in row.iter(NS + "c"):
                    if cell.get("t") == "inlineStr":
                        box = cell.find(NS + "is")
                        runs = box.findall(NS + "t") + [t for r in box.findall(NS + "r") for t in r.findall(NS + "t")]
                        cells.append("".join(t.text or "" for t in runs))  # phonetic runs (rPh) are not cell text
                        continue
                    raw = cell.find(NS + "v").text
                    cells.append(shared[int(raw)] if cell.get("t") == "s" else int(raw))
                rows.append(cells)
            sheets[sheet.get("name")] = rows
    return sheets


def pdf_object(raw, offsets, num):
    """The body of indirect object num, located through the cross-reference table."""
    start = raw.index(b"obj", offsets[num]) + 3
    return raw[start:raw.index(b"endobj", start)].strip()


def pdf_stream(raw, offsets, num):
    body_start = raw.index(b"obj", offsets[num]) + 3
    key = raw.index(b"stream", body_start)
    head = raw[body_start:key].decode("latin-1")
    length = re.search(r"/Length\s+(\d+)(\s+\d+\s+R)?", head)
    size = int(pdf_object(raw, offsets, int(length.group(1))).decode()) if length.group(2) else int(length.group(1))
    data_start = key + 6
    data_start += 2 if raw[data_start:data_start + 2] == b"\r\n" else 1
    data = raw[data_start:data_start + size]
    return zlib.decompress(data) if "/FlateDecode" in head else data


def pdf_text_lines(content):
    """Text lines shown by Tj, TJ, ' and \" operators; T*, Td, TD, ' and \" start a new line."""
    lines, current, operands, i, n = [], [], [], 0, len(content)
    while i < n:
        ch = content[i]
        if ch in " \t\r\n\f\0":
            i += 1
        elif ch == "%":
            while i < n and content[i] not in "\r\n":
                i += 1
        elif ch == "(":
            depth, i, buf = 1, i + 1, []
            while depth:
                c = content[i]
                if c == "\\":
                    nxt = content[i + 1]
                    if nxt in "01234567":
                        m = re.match(r"[0-7]{1,3}", content[i + 1:])
                        buf.append(chr(int(m.group(0), 8)))
                        i += 1 + len(m.group(0))
                        continue
                    buf.append({"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}.get(nxt, "" if nxt in "\r\n" else nxt))
                    i += 2
                    continue
                depth += c == "("
                depth -= c == ")"
                if depth:
                    buf.append(c)
                i += 1
            operands.append(("str", "".join(buf)))
        elif ch == "[":
            operands.append(("open", None))
            i += 1
        elif ch == "]":
            items = []
            while operands and operands[-1][0] != "open":
                items.append(operands.pop())
            operands.pop()
            operands.append(("arr", "".join(v for k, v in reversed(items) if k == "str")))
            i += 1
        else:
            m = re.match(r"[^\s()\[\]<>/%]+|/[^\s()\[\]<>/%]*|<<|>>|<[^>]*>", content[i:])
            tok = m.group(0)
            i += len(tok)
            if re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)", tok) or tok.startswith("/") or tok.startswith("<"):
                operands.append(("val", tok))
                continue
            if tok in ("T*", "Td", "TD", "'", '"') and current:
                lines.append("".join(current))
                current = []
            if tok in ("Tj", "'", '"'):
                current.append(operands[-1][1])
            elif tok == "TJ":
                current.append(operands[-1][1])
            operands = []
    if current:
        lines.append("".join(current))
    return lines


def read_pdf_rates(path):
    raw = path.read_bytes()
    xref = int(raw[raw.rindex(b"startxref") + 9:].split()[0])
    table = raw[xref:].split(b"trailer")[0].split(b"\n")
    offsets, k = {}, 1
    while k < len(table) and table[k].strip():
        first, count = (int(x) for x in table[k].split())
        for j in range(count):
            entry = table[k + 1 + j].split()
            if entry[2] == b"n":
                offsets[first + j] = int(entry[0])
        k += 1 + count
    trailer = raw[raw.rindex(b"trailer"):].decode("latin-1")
    root = int(re.search(r"/Root\s+(\d+)", trailer).group(1))
    pages = int(re.search(r"/Pages\s+(\d+)", pdf_object(raw, offsets, root).decode("latin-1")).group(1))
    page = int(re.search(r"/Kids\s*\[\s*(\d+)", pdf_object(raw, offsets, pages).decode("latin-1")).group(1))
    page_dict = pdf_object(raw, offsets, page).decode("latin-1")
    found = re.search(r"/Contents\s*(\[[^\]]*\]|\d+\s+\d+\s+R)", page_dict).group(1)
    content = b"\n".join(pdf_stream(raw, offsets, int(num)) for num in re.findall(r"(\d+)\s+\d+\s+R", found))
    shown = pdf_text_lines(content.decode("latin-1"))
    body = shown[shown.index("segment revised_on rate_milli") + 1:]
    return [(f[0], f[1], int(f[2])) for f in (row.split() for row in body)]


WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MCNS = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"


def current_text(node, ignored=(), kept=(), known=()):
    """Current text of a WordprocessingML subtree: moved-from and deleted runs are not current; of
    markup-compatibility alternate content only the first choice whose required namespaces this reader
    understands is read, or the fallback when there is none; elements of an ignorable namespace this reader
    does not understand are ignored with their content unless named for content processing, which keeps the
    content (ECMA-376 Part 3)."""
    if node.tag in (WNS + "moveFrom", WNS + "del"):
        return ""
    if node.tag == MCNS + "AlternateContent":
        kids = list(node)
        take = [k for k in kids if k.tag == MCNS + "Choice" and all(r in known for r in k.get("Requires", "").split())]
        take = take[:1] or [k for k in kids if k.tag == MCNS + "Fallback"][:1]
        return "".join(current_text(c, ignored, kept, known) for k in take for c in k)
    if any(node.tag.startswith("{" + uri + "}") for uri in ignored) and node.tag not in kept:
        return ""
    if node.tag == WNS + "t":
        return node.text or ""
    return "".join(current_text(child, ignored, kept, known) for child in node)


def docx_tables(path):
    with zipfile.ZipFile(path) as zf:
        raw = zf.read(main_part(zf))
    prefixes = dict(ns for _event, ns in ET.iterparse(io.BytesIO(raw), events=("start-ns",)))
    root = ET.fromstring(raw)
    understood = {WNS[1:-1], MCNS[1:-1]}
    known = {p for p, uri in prefixes.items() if uri in understood}
    ignored = tuple(prefixes[p] for p in root.get(MCNS + "Ignorable", "").split() if prefixes.get(p) not in understood)
    kept = set()
    for name in root.get(MCNS + "ProcessContent", "").split():
        prefix, _colon, local = name.partition(":")
        if prefix in prefixes:
            kept.add("{" + prefixes[prefix] + "}" + local)
    return [[[current_text(tc, ignored, kept, known) for tc in tr.iter(WNS + "tc")] for tr in tbl.iter(WNS + "tr")]
            for tbl in root.iter(WNS + "tbl")]


def read_schemes(path):
    rows = next(t for t in docx_tables(path) if "scheme" in t[0])
    head = rows[0]
    return {r[head.index("scheme")]: r[head.index("segment")] for r in rows[1:]}


def read_config(data):
    cfg = configparser.ConfigParser()
    cfg.read(data / "basin_cfg.ini", encoding="utf-8")
    rows = next(t for t in docx_tables(data / "sc_k2.docx") if "basin" in t[0])
    head = rows[0]
    params = {}
    for row in rows[1:]:
        params[row[head.index("basin")]] = {key: int(row[head.index(key)]) for key in ("damping_percent", "patience", "round_budget")}
    return cfg["season"]["label"], int(cfg["season"]["revision_cutoff"]), params


def targets(state, links, offsets):
    """links: (a, b, a's draw points) per net gauging of the basin."""
    partner_sum = {k: 0 for k in state}
    count = {k: 0 for k in state}
    points = {k: Fraction(0) for k in state}
    for a, b, pts in links:
        partner_sum[a] += state[b]
        partner_sum[b] += state[a]
        count[a] += 1
        count[b] += 1
        points[a] += pts
        points[b] += 1 - pts
    result = {}
    for k in state:
        if count[k] == 0:
            result[k] = state[k]
            continue
        mean = round_half_away(Fraction(partner_sum[k], count[k]))
        share = round_half_away(points[k] * 100 / count[k])
        result[k] = mean + offsets[share]
    return result


def closed_transfers(residual, damping, order):
    moves = {k: round_half_away(Fraction(damping * residual[k], 100)) for k in order}
    surplus = sum(moves.values())
    if surplus:
        far = max(abs(v) for v in residual.values())
        lead = [k for k in order if abs(residual[k]) == far][-1]
        moves[lead] -= surplus
    return moves


def balance(order, opening, links, offsets, prm):
    """Returns (exit, round count, damping, balanced storages)."""
    state = dict(opening)
    damping, tally, before = prm["damping_percent"], 0, None
    seen = [tuple(state[k] for k in order)]
    for rnd in range(prm["round_budget"]):
        tgt = targets(state, links, offsets)
        residual = {k: tgt[k] - state[k] for k in order}
        total = sum(abs(v) for v in residual.values())
        if total == 0:
            return "balanced", rnd, damping, state
        if before is not None and total >= before:
            tally += 1
        if tally == prm["patience"]:
            damping //= 2
            tally = 0
        moves = closed_transfers(residual, damping, order)
        if all(v == 0 for v in moves.values()):
            return "stalled", rnd, damping, state
        state = {k: state[k] + moves[k] for k in order}
        now = tuple(state[k] for k in order)
        if now in seen:
            lowest = min(seen[seen.index(now):])
            return "cycle", -1, damping, dict(zip(order, lowest))
        seen.append(now)
        before = total
    return "budget", prm["round_budget"], damping, state


def rate_in_force(rates, segment, day):
    rows = [r for r in rates if r[0] == segment and r[1] < day]
    return max(rows, key=lambda r: r[1])[2]


def load_extract(data):
    register, catchments = read_register(data)
    label, cutoff, params = read_config(data)
    gaugings, read = read_gaugings(data)
    check_register_rules(gaugings, register)
    net, quality = apply_revisions(data, gaugings, cutoff)
    quality["gaugings_read"] = read
    quality["mirror_mismatches"] = mirror_mismatches(data, register)
    book = read_workbook(data / "tab_h3.xlsx")
    offsets = {}
    for share, value in book["offset"][1:]:
        whole, frac = share.split(".")
        offsets[int(whole) * 100 + int(frac)] = int(value)
    schemes = read_schemes(data / "sc_k2.docx")
    licences = {}
    for e in json.loads((data / "lc_register.json").read_text(encoding="utf-8"))["licences"]:
        licences[e["licence"]] = dict(e, segment=schemes[e["scheme"]])
    prior = json.loads((data / "prior_balance.json").read_text(encoding="utf-8"))
    return {"register": register, "label": label, "cutoff": cutoff, "params": params, "net": net,
            "quality": quality, "offsets": offsets, "rates": read_pdf_rates(data / "mt_loss.pdf"),
            "licences": licences, "schemes": schemes, "catchments": catchments, "prior": prior}


def basin_report(ext, basin):
    reg = ext["register"]
    order = sorted((s for s in reg if reg[s]["basin"] == basin), key=station_number)
    links = [(a, b, pts) for _lic, a, b, pts in ext["net"].values() if reg[a]["basin"] == basin]
    opening = {s: reg[s]["opening"] for s in order}
    kind, rounds, damping, final = balance(order, opening, links, ext["offsets"], ext["params"][basin])
    rows = [{"stn": s, "station_name": reg[s]["name"], "opening_ml": opening[s], "balanced_ml": final[s],
             "change": final[s] - opening[s]} for s in order]
    return {"basin": basin, "exit": kind, "rounds": rounds, "damping_percent": damping, "reservoirs": rows,
            "transferred_ml": sum(abs(r["change"]) for r in rows),
            "storage_total": sum(r["balanced_ml"] for r in rows)}


def loss_accounts(ext, storage):
    """Returns ([(gauging id, licence, segment, from, to, loss)], {licence: [gaugings, loss]})."""
    per = {code: [0, 0] for code in ext["licences"]}
    rows = []
    for gid in sorted(ext["net"]):
        lic, a, b, _pts = ext["net"][gid]
        entry = ext["licences"][lic]
        rate = rate_in_force(ext["rates"], entry["segment"], entry["date"])
        loss = rate * (storage[a] + storage[b]) // 1000
        per[lic][0] += 1
        per[lic][1] += loss
        rows.append((gid, lic, entry["segment"], a, b, loss))
    return rows, per


def as_json(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def as_lines(lines):
    return "\n".join(lines) + "\n"


def segment_reports(ext, per):
    segs = {s: {"segment": s, "licences": [], "gaugings": 0, "loss_kl": 0} for s in SEGMENTS}
    for code in sorted(ext["licences"]):
        entry = ext["licences"][code]
        seg = segs[entry["segment"]]
        seg["licences"].append({"licence": code, "date": entry["date"], "gaugings": per[code][0], "loss_kl": per[code][1]})
        seg["gaugings"] += per[code][0]
        seg["loss_kl"] += per[code][1]
    return segs


def sqlite_report(regions):
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE TABLE basin (basin TEXT, exit TEXT, rounds INTEGER, damping_percent INTEGER, transferred_ml INTEGER)")
        con.execute("CREATE TABLE reservoir (basin TEXT, stn TEXT, opening_ml INTEGER, balanced_ml INTEGER, change INTEGER)")
        dump = []
        for b in sorted(BASINS):
            r = regions[b]
            row = (b, r["exit"], r["rounds"], r["damping_percent"], r["transferred_ml"])
            con.execute("INSERT INTO basin VALUES (?, ?, ?, ?, ?)", row)
            dump.append("basin|" + "|".join(str(v) for v in row))
        for b in sorted(BASINS):
            for m in regions[b]["reservoirs"]:
                row = (b, m["stn"], m["opening_ml"], m["balanced_ml"], m["change"])
                con.execute("INSERT INTO reservoir VALUES (?, ?, ?, ?, ?)", row)
                dump.append("reservoir|" + "|".join(str(v) for v in row))
        con.commit()
        return con.serialize(), as_lines(dump)
    finally:
        con.close()


def xml_text(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def xlsx_report(sheets):
    """sheets: [(name, rows)]; str cells become inline strings, int cells numbers. Returns (bytes, dump)."""
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    parts = {"[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
             + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets) + 1)) + "</Types>",
             "_rels/.rels": f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
             "xl/workbook.xml": f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{main}" xmlns:r="{rel}"><sheets>' + "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _r) in enumerate(sheets, 1)) + "</sheets></workbook>",
             "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1)) + "</Relationships>"}
    dump = []
    for i, (name, rows) in enumerate(sheets, 1):
        cells = []
        for row in rows:
            cells.append("<row>" + "".join(f"<c><v>{v}</v></c>" if isinstance(v, int) else f'<c t="inlineStr"><is><t>{xml_text(v)}</t></is></c>' for v in row) + "</row>")
            dump.append(name + "|" + "|".join(str(v) for v in row))
        parts[f"xl/worksheets/sheet{i}.xml"] = f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{main}"><sheetData>' + "".join(cells) + "</sheetData></worksheet>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in parts.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 30, 0, 0, 0))
            zf.writestr(info, text.encode("utf-8"))
    return buf.getvalue(), as_lines(dump)


def licence_rows(ext, per):
    return [[code, ext["licences"][code]["scheme"], ext["licences"][code]["segment"], ext["licences"][code]["date"],
             per[code][0], per[code][1]] for code in sorted(ext["licences"])]


def day_totals(ext, per):
    days = {}
    for code, entry in ext["licences"].items():
        tot = days.setdefault(entry["date"], [0, 0])
        tot[0] += per[code][0]
        tot[1] += per[code][1]
    return days


def loss_group(ext, segs, rows, per, out):
    lic = licence_rows(ext, per)
    for s in SEGMENTS:
        out[f"segment_{s}.json"] = as_json(segs[s])
        out[f"segment_{s}.tsv"] = as_lines(["gauging_id\tlicence\tdate\tloss_kl"] + [
            f"{g}\t{l}\t{ext['licences'][l]['date']}\t{v}" for g, l, sg, _a, _b, v in rows if sg == s])
    out["loss_ledger.tsv"] = as_lines(["gauging_id\tlicence\tsegment\tfrom_stn\tto_stn\tloss_kl"] + ["\t".join(str(v) for v in r) for r in rows])
    out["licence_losses.csv"] = as_lines(["licence,scheme,segment,date,gaugings,loss_kl"] + [",".join(str(v) for v in r) for r in lic])
    schemes = []
    for code in sorted(ext["schemes"]):
        mine = [r for r in lic if r[1] == code]
        schemes.append({"scheme": code, "segment": ext["schemes"][code], "licences": len(mine),
                        "gaugings": sum(r[4] for r in mine), "loss_kl": sum(r[5] for r in mine)})
    out["scheme_losses.json"] = as_json({"schemes": schemes})
    days = day_totals(ext, per)
    out["loss_by_day.csv"] = as_lines(["date,gaugings,loss_kl"] + [f"{d},{days[d][0]},{days[d][1]}" for d in sorted(days)])
    head = [["licence", "scheme", "segment", "date", "gaugings", "loss_kl"]]
    seg_rows = [["segment", "gaugings", "loss_kl"]] + [[s, segs[s]["gaugings"], segs[s]["loss_kl"]] for s in SEGMENTS]
    return xlsx_report([("licences", head + lic), ("segments", seg_rows)])


def station_reports(ext, regions, out):
    reg = ext["register"]
    held = {m["stn"]: m["balanced_ml"] for b in BASINS for m in regions[b]["reservoirs"]}
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', f'<stations season="{xml_text(ext["label"])}">']
    for s in sorted(reg, key=station_number):
        i = reg[s]
        xml.append(f'  <station stn="{s}" gauge="{i["gauge"]}" catchment="{i["catchment"]}" basin="{i["basin"]}">{xml_text(i["name"])}</station>')
    out["station_index.xml"] = as_lines(xml + ["</stations>"])
    for b in BASINS:
        out[f"basin_{b}.tsv"] = as_lines(["stn\tgauge_no\tcatchment\topening_ml\tbalanced_ml\tchange"] + [
            f"{m['stn']}\t{reg[m['stn']]['gauge']}\t{reg[m['stn']]['catchment']}\t{m['opening_ml']}\t{m['balanced_ml']}\t{m['change']}"
            for m in regions[b]["reservoirs"]])
    lines = ["catchment,basin,reservoirs,opening_ml,balanced_ml"]
    for c in sorted(ext["catchments"]):
        mine = [s for s in reg if reg[s]["catchment"] == c]
        lines.append(f"{c},{ext['catchments'][c]},{len(mine)},{sum(reg[s]['opening'] for s in mine)},{sum(held[s] for s in mine)}")
    out["catchment_totals.csv"] = as_lines(lines)
    ledger = ["basin,stn,station_name,opening_ml,balanced_ml,change"]
    for b in sorted(BASINS):
        ledger += [f'{b},{r["stn"]},"{r["station_name"]}",{r["opening_ml"]},{r["balanced_ml"]},{r["change"]}' for r in regions[b]["reservoirs"]]
    out["station_ledger.csv"] = as_lines(ledger)


def basin_summaries(ext, regions, out):
    order = sorted(BASINS)
    yaml = [f"season: {ext['label']}", "basins:"]
    md = [f"# Season {ext['label']} balancing", "", "| Basin | Exit | Rounds | Damping | Transferred ML |", "|---|---|---|---|---|"]
    bands = []
    for b in order:
        r = regions[b]
        yaml += [f"  {b}:", f"    exit: {r['exit']}", f"    rounds: {r['rounds']}", f"    damping_percent: {r['damping_percent']}", f"    transferred_ml: {r['transferred_ml']}"]
        md.append(f"| {b} | {r['exit']} | {r['rounds']} | {r['damping_percent']} | {r['transferred_ml']} |")
        count = {}
        for m in r["reservoirs"]:
            count[m["balanced_ml"] // 250] = count.get(m["balanced_ml"] // 250, 0) + 1
        bands += [f"{b} {250 * k}-{250 * k + 249} {count[k]}" for k in sorted(count)]
    out["exits.yaml"] = as_lines(yaml)
    out["season_brief.md"] = as_lines(md)
    out["storage_bands.txt"] = as_lines(bands)
    pts = {Fraction(0): "0", Fraction(1, 2): "1/2", Fraction(1): "1"}
    out["gauging_net.psv"] = as_lines(["gauging_id|licence|from_stn|to_stn|from_points"] + [
        f"{g}|{v[0]}|{v[1]}|{v[2]}|{pts[v[3]]}" for g, v in sorted(ext["net"].items())])


def totals_reports(ext, regions, segs, rows, per, out):
    moved = sum(regions[b]["transferred_ml"] for b in BASINS)
    loss = sum(segs[s]["loss_kl"] for s in SEGMENTS)
    lic = licence_rows(ext, per)
    days = day_totals(ext, per)
    out["summary.json"] = as_json({"season": ext["label"], "basins": {b: {"exit": regions[b]["exit"], "rounds": regions[b]["rounds"]} for b in BASINS},
                                   "transferred_ml_total": moved, "loss_kl_total": loss,
                                   "gaugings_net": len(ext["net"]), "reservoirs": len(ext["register"])})
    out["reconciliation.json"] = as_json({
        "storage": {b: {"opening_total": sum(m["opening_ml"] for m in regions[b]["reservoirs"]), "balanced_total": regions[b]["storage_total"]} for b in BASINS},
        "loss_kl": {"by_gauging": sum(r[5] for r in rows), "by_licence": sum(r[5] for r in lic), "by_segment": loss,
                    "by_day": sum(v[1] for v in days.values())},
        "gaugings": {"net": len(ext["net"]), "by_licence": sum(r[4] for r in lic)}})
    pr = ext["prior"]
    out["prior_delta.json"] = as_json({
        "prior_season": pr["season"],
        "transferred_ml_total": {"prior": pr["transferred_ml_total"], "current": moved, "difference": moved - pr["transferred_ml_total"]},
        "loss_kl_total": {"prior": pr["loss_kl_total"], "current": loss, "difference": loss - pr["loss_kl_total"]},
        "basins": {b: {"prior_exit": pr["basins"][b]["exit"], "exit": regions[b]["exit"], "prior_rounds": pr["basins"][b]["rounds"],
                       "rounds": regions[b]["rounds"]} for b in BASINS}})
    out["policy_audit.json"] = as_json({"season": ext["label"], "revision_cutoff": ext["cutoff"], "basins": ext["params"],
                                        "loss_rates": [{"segment": s, "revised_on": d, "rate_milli": r} for s, d, r in sorted(ext["rates"])]})
    out["data_quality.json"] = as_json(ext["quality"])


def build_reports(ext):
    """Returns {report name: bytes}; every figure is settled before anything is written."""
    regions = {b: basin_report(ext, b) for b in BASINS}
    storage = {r["stn"]: r["balanced_ml"] for b in BASINS for r in regions[b]["reservoirs"]}
    rows, per = loss_accounts(ext, storage)
    segs = segment_reports(ext, per)
    out = {f"region_{b}.json": as_json(regions[b]) for b in BASINS}
    book, book_dump = loss_group(ext, segs, rows, per, out)
    station_reports(ext, regions, out)
    basin_summaries(ext, regions, out)
    totals_reports(ext, regions, segs, rows, per, out)
    db, db_dump = sqlite_report(regions)
    digests = {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in out.items()}
    digests["balanced.sqlite"] = hashlib.sha256(db_dump.encode("utf-8")).hexdigest()
    digests["loss_book.xlsx"] = hashlib.sha256(book_dump.encode("utf-8")).hexdigest()
    reports = {name: text.encode("utf-8") for name, text in out.items()}
    reports["manifest.json"] = as_json({"reports": dict(sorted(digests.items()))}).encode("utf-8")
    reports["balanced.sqlite"] = db
    reports["loss_book.xlsx"] = book
    return reports


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: derive_report.py DATA_DIR OUT_DIR")
    data, out_dir = Path(argv[1]), Path(argv[2])
    try:
        reports = build_reports(load_extract(data))
    except InputRuleError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(reports):
        (out_dir / name).write_bytes(reports[name])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
