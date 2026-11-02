#!/usr/bin/env python3
"""Recompute the bioequivalence analysis of the study named in the analysis profile.

Usage: python3 run_be.py DATA_DIR OUT_DIR

Standard library only. Every figure is derived from DATA_DIR when the program runs.
"""

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
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

UTC = timezone.utc
LEVELS = [f"CS{i}" for i in range(1, 9)]
OUTPUTS = ["calibration_fits.json", "standard_backcalc.tsv", "qc_results.csv", "run_acceptance.csv", "tube_results.psv",
           "reported_concentrations.csv", "sampling_times.xml", "isr_assessment.json", "nca_parameters.csv", "lambda_z_selection.jsonl",
           "be_statistics.json", "be_summary.md", "analysis_populations.csv", "excluded_subjects.jsonl", "mean_profiles.csv",
           "dedup_report.json", "source_lineage.json", "alias_resolution.csv", "parameters_used.yaml", "variance_vs_published.csv",
           "reconciliation.md"]


def up(v: object) -> str:
    return "" if v is None else str(v).strip().upper()


# =============================================================================== readers
def yaml_load(text: str) -> object:
    lines = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        lines.append([len(raw) - len(raw.lstrip(" ")), s])

    def scalar(v: str) -> str:
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            return v[1:-1]
        return v

    def block(i: int) -> tuple[object, int]:
        ind = lines[i][0]
        if lines[i][1].startswith("- ") or lines[i][1] == "-":
            out = []
            while i < len(lines) and lines[i][0] == ind and (lines[i][1].startswith("- ") or lines[i][1] == "-"):
                rest = lines[i][1][1:].strip()
                if not rest:
                    item, i = block(i + 1)
                elif re.match(r"^[A-Za-z_][\w.]*:(\s|$)", rest):
                    lines[i] = [ind + 2, rest]
                    item, i = block(i)
                else:
                    item, i = scalar(rest), i + 1
                out.append(item)
            return out, i
        out = {}
        while i < len(lines) and lines[i][0] == ind and not lines[i][1].startswith("- "):
            key, _, val = lines[i][1].partition(":")
            if val.strip():
                out[key.strip()] = scalar(val)
                i += 1
            elif i + 1 < len(lines) and (lines[i + 1][0] > ind or (lines[i + 1][0] == ind and lines[i + 1][1].startswith("- "))):
                out[key.strip()], i = block(i + 1)
            else:
                out[key.strip()] = None
                i += 1
        return out, i

    return block(0)[0] if lines else {}


def read_dsv(path: Path, sep: str) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=sep))
    head = [h.strip() for h in rows[0]]
    return [{h: (r[k].strip() if k < len(r) else "") for k, h in enumerate(head)} for r in rows[1:] if any(c.strip() for c in r)]


def _text_objects(body: str) -> list[tuple[float, float, str]]:
    """Scan a content stream; return (x, y, text) for every BT ... ET object, x and y taken from its Tm."""
    found = []
    i, n = 0, len(body)
    while True:
        b = body.find("BT", i)
        if b < 0:
            break
        j = b + 2
        operands: list[str] = []
        pieces: list[str] = []
        x = y = 0.0
        while j < n:
            ch = body[j]
            if ch == "(":
                text, j = _pdf_string(body, j)
                pieces.append(text)
            elif ch == "<":
                k = body.index(">", j)
                pieces.append(bytes.fromhex("".join(body[j + 1:k].split())).decode("latin-1"))
                j = k + 1
            elif ch in "[]":
                j += 1
            elif ch.isspace() or ch == "/":
                j += 1
            else:
                k = j
                while k < n and not body[k].isspace() and body[k] not in "()<>[]/":
                    k += 1
                word = body[j:k]
                j = k
                if word == "ET":
                    break
                if word == "Tm":
                    x, y = float(operands[-2]), float(operands[-1])
                operands.append(word)
        found.append((x, y, "".join(pieces)))
        i = j
    return found


def read_pdf(path: Path) -> dict[str, dict]:
    raw = path.read_bytes().decode("latin-1")
    lines: list[list[str]] = []
    for m in re.finditer(r"/Length (\d+) /Filter /FlateDecode >>\nstream\n", raw):
        body = zlib.decompress(raw[m.end():m.end() + int(m.group(1))].encode("latin-1")).decode("latin-1")
        rows: dict[float, list[tuple[float, str]]] = {}
        for x, y, text in _text_objects(body):
            rows.setdefault(y, []).append((x, text))
        for y in sorted(rows, reverse=True):
            lines.append([t for _, t in sorted(rows[y])])
    tables: dict[str, dict] = {}
    cur = None
    for cells in lines:
        if len(cells) == 1:
            m = re.match(r"^Table ([A-Z]+-\d+)(?::(.*)| \(continued\))$", cells[0].strip())
            if m:
                cur = m.group(1)
                if m.group(2) is not None:
                    tag = re.search(r"\[([^\]]+)\]\s*$", m.group(2))
                    tables[cur] = {"status": tag.group(1) if tag else "", "header": None, "rows": []}
            continue
        if cur is None:
            continue
        t = tables[cur]
        cells = [c.strip() for c in cells]
        if t["header"] is None:
            t["header"] = cells
        elif cells != t["header"]:
            t["rows"].append(dict(zip(t["header"], cells)))
    return tables


def _pdf_string(s: str, i: int) -> tuple[str, int]:
    out = []
    i += 1
    depth = 0
    while True:
        ch = s[i]
        if ch == "\\":
            out.append(s[i + 1])
            i += 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                break
            depth -= 1
        out.append(ch)
        i += 1
    return "".join(out), i + 1


NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def workbook_epoch(path: Path) -> date:
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
    for el in wb.iter(NS + "workbookPr"):
        if (el.get("date1904") or "").strip().lower() in ("1", "true"):
            return date(1904, 1, 1)
    return date(1899, 12, 30)


def read_sheet(path: Path, name: str, first: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        sheet = next(s for s in wb.iter(NS + "sheet") if s.get("name") == name)
        target = rels[sheet.get(RNS + "id")].lstrip("/")
        part = target if target.startswith("xl/") else "xl/" + target
        shared = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si")]
        ws = ET.fromstring(z.read(part))
    head: dict[str, str] | None = None
    out = []
    for row in ws.iter(NS + "row"):
        vals: dict[str, str] = {}
        for c in row.iter(NS + "c"):
            col = re.sub(r"\d", "", c.get("r"))
            if c.get("t") == "inlineStr":
                v = "".join(t.text or "" for t in c.iter(NS + "t"))
            else:
                ve = c.find(NS + "v")
                if ve is None:
                    continue
                v = shared[int(ve.text)] if c.get("t") == "s" else ve.text
            vals[col] = v.strip()
        if head is None:
            if vals.get("A") == first:
                head = vals
            continue
        cols = sorted(head, key=lambda k: (len(k), k))
        if len(cols) > 1 and not vals.get(cols[1]):
            continue
        out.append({head[k]: vals.get(k, "") for k in cols})
    return out


def num(v: object) -> float:
    return float(str(v).strip().replace(",", "."))


def dfac(v: object) -> int:
    s = up(v)
    if s.startswith("1:"):
        s = s[2:]
    if s.startswith("X"):
        s = s[1:]
    return int(float(s))


# =============================================================================== shards
KIND = {"STD": "STD", "STANDARD": "STD", "S": "STD", "CAL": "STD", "QC": "QC", "Q": "QC", "DQC": "DQC", "DILQC": "DQC", "D": "DQC",
        "UNK": "UNK", "UNKNOWN": "UNK", "U": "UNK", "SAMPLE": "UNK", "STUDY": "UNK", "BLANK": "BLANK", "B": "BLANK", "BLK": "BLANK",
        "ZERO": "ZERO", "Z": "ZERO"}
VOID = {"i_csv": "VOID", "i_tsv": "9", "i_psv": "DEAD", "i_jsonl": "VOID", "i_ndjson": "TRUE", "i_xml": "VOIDED", "i_sqlite": "1", "i_db": "X",
        "i_json": "RETRACTED", "i_yaml": "V", "i_yml": "CXL", "i_txt": "X", "i_csvsemi": "N", "i_tsv2": "VOID", "i_jsonl2": "VOID", "i_psv2": "DROP"}
QCREF = {"LQC": "LQC", "QC-L": "LQC", "LOW": "LQC", "QCL": "LQC", "MQC": "MQC", "QC-M": "MQC", "MID": "MQC", "QCM": "MQC",
         "HQC": "HQC", "QC-H": "HQC", "HIGH": "HQC", "QCH": "HQC", "DQC": "DQC", "QC-D": "DQC", "DIL": "DQC", "QCD": "DQC"}


def level(tok: str) -> str:
    m = re.match(r"^(?:CS|STD-|L|CAL )(\d)$", up(tok))
    return f"CS{m.group(1)}" if m else up(tok)


def kc(v: object) -> int:
    return int(round(num(v) * 1000))


def load_shard(path: Path, lay: str) -> list[dict]:  # noqa: C901
    recs: list[tuple] = []
    if lay in ("i_csv", "i_tsv", "i_psv", "i_csvsemi", "i_tsv2", "i_psv2"):
        sep = {"i_csv": ",", "i_tsv": "\t", "i_psv": "|", "i_csvsemi": ";", "i_tsv2": "\t", "i_psv2": "|"}[lay]
        for r in read_dsv(path, sep):
            if lay == "i_csv":
                recs.append((r["injection_id"], r["run_ref"], r["seq"], r["sample_type"], r["sample_ref"], r["dilution"], int(r["analyte_area"]), int(r["is_area"]), r["integration"], r["revision"], r["state"]))
            elif lay == "i_tsv":
                recs.append((r["INJ"], r["RUN"], r["SEQ"], r["TYPE"], r["REF"], r["DIL"], int(r["A_AREA"]), int(r["IS_AREA"]), r["INTEG"], r["REV"], r["ST"]))
            elif lay == "i_psv":
                recs.append((r["inj"], r["run"], r["seq"], r["kind"], r["ref"], r["df"], int(r["area_counts"]), kc(r["is_area_kcounts"]), r["int"], r["rev"], r["status"]))
            elif lay == "i_csvsemi":
                recs.append((r["Injection"], r["Batch"], r["Pos"], r["Type"], r["Sample"], r["Dilution"], kc(r["Area (kcounts)"]), kc(r["IS Area (kcounts)"]), r["Integration"], r["Rev"], r["Valid"]))
            elif lay == "i_tsv2":
                recs.append((r["injection"], r["run"], r["seq"], r["type"], r["ref"], r["df"], int(r["analyte_area"]), int(r["is_area"]), r["integration"], r["revision"], r["status"]))
            else:
                recs.append((r["inj"], r["run"], r["pos"], r["t"], r["ref"], r["df"], int(r["area"]), int(r["is_area"]), r["integ"], r["rev"], r["keep"]))
    elif lay in ("i_jsonl", "i_ndjson", "i_jsonl2"):
        for ln in path.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            o = json.loads(ln)
            if lay == "i_jsonl":
                recs.append((o["injectionId"], o["runRef"], o["seqNo"], o["sampleType"], o["sampleRef"], o["dilutionFactor"], o["analyteArea"], o["isArea"], o["integration"], o["revision"], o["status"]))
            elif lay == "i_ndjson":
                recs.append((o["id"], o["run"], o["order"], o["sample"]["type"], o["sample"]["ref"], o["sample"]["df"], o["areas"]["analyte"], o["areas"]["istd"], o["proc"]["mode"], o["proc"]["rev"], str(o["void"])))
            else:
                recs.append((o["inj"], o["run"], o["seq"], o["type"], o["ref"], o["df"], o["a"], o["is"], o["mode"], o["rev"], o["st"]))
    elif lay == "i_xml":
        for e in ET.parse(path).getroot().iter("inj"):
            ar = {a.get("kind"): a.text for a in e.iter("area")}
            recs.append((e.get("id"), e.get("run"), e.get("seq"), e.get("type"), e.get("ref"), e.get("df"), int(ar["analyte"]), int(ar["istd"]), e.get("integ"), e.get("rev"), e.get("status")))
    elif lay == "i_sqlite":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for row in con.execute("select inj_id, run_token, seq, stype, sref, dil, a_area, is_area, integ, rev, voided from injection"):
            recs.append(row)
        con.close()
    elif lay == "i_db":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        areas = {(up(i), int(r), up(c)): v for i, r, c, v in con.execute("select inj_id, rev, channel, value from area")}
        for i, run, sq, st, sr, dl, ig, rv, fl in con.execute("select id, run, seq, stype, sref, dil, integ, rev, flag from inj"):
            recs.append((i, run, sq, st, sr, dl, areas[(up(i), int(rv), "A")], areas[(up(i), int(rv), "IS")], ig, rv, fl))
        con.close()
    elif lay == "i_json":
        ex = json.loads(path.read_text(encoding="utf-8"))["export"]
        cols = ex["columns"]
        for row in ex["rows"]:
            o = dict(zip(cols, row))
            recs.append((o["inj"], o["run"], o["seq"], o["type"], o["ref"], o["df"], o["area_analyte"], o["area_istd"], o["integration"], o["rev"], o["state"]))
    elif lay in ("i_yaml", "i_yml"):
        doc = yaml_load(path.read_text(encoding="utf-8"))
        if lay == "i_yaml":
            for o in doc["injections"]:
                recs.append((o["inj"], o["run"], o["seq"], o["type"], o["ref"], o["df"], int(o["area_a"]), int(o["area_is"]), o["integ"], o["rev"], o["st"]))
        else:
            for o in doc["records"]:
                recs.append((o["injection"], o["batch"], o["position"], o["kind"], o["label"], o["dilution"], int(o["analyte_counts"]), kc(o["istd_kcounts"]), o["mode"], o["revision"], o["state"]))
    elif lay == "i_txt":
        for ln in path.read_text(encoding="utf-8").splitlines():
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue
            o = dict(p.strip().split("=", 1) for p in ln.split(";") if "=" in p)
            recs.append((o["INJ"], o["RUN"], o["SEQ"], o["TYPE"], o["REF"], o["DF"], int(o["AREA"]), int(o["ISAREA"]), o["MODE"], o["REV"], o["ST"]))
    out = []
    for inj, run, sq, kind, ref, dl, a, i_s, integ, rev, st in recs:
        k = KIND[up(kind)]
        if k == "STD":
            r = level(ref)
        elif k in ("QC", "DQC"):
            r = QCREF[up(ref)]
        else:
            r = up(ref)
        out.append({"inj": up(inj), "run_tok": str(run).strip(), "seq": int(sq), "kind": k, "ref": r, "df": dfac(dl), "a": int(a), "is": int(i_s),
                    "integ": "MANUAL" if up(integ) in ("M", "MANUAL") else "AUTO", "rev": int(rev), "void": up(st) == VOID[lay]})
    return out


# =============================================================================== calendar and times
class Calendar:
    def __init__(self, doc: dict) -> None:
        self.base = self._off(doc["base_offset"])
        self.trans = sorted((datetime.fromisoformat(t["at_utc"].replace("Z", "+00:00")), self._off(t["offset_after"])) for t in doc["transitions"])

    @staticmethod
    def _off(s: str) -> timedelta:
        sign = -1 if s.strip().startswith("-") else 1
        hh, mm = s.strip().lstrip("+-").split(":")
        return sign * timedelta(hours=int(hh), minutes=int(mm))

    def offset_at(self, u: datetime) -> timedelta:
        off = self.base
        for when, o in self.trans:
            if u >= when:
                off = o
        return off

    def to_utc(self, wall: datetime) -> datetime:
        offs = {self.base} | {o for _, o in self.trans}
        cands = []
        for o in offs:
            u = (wall - o).replace(tzinfo=UTC)
            if self.offset_at(u) == o:
                cands.append(u)
        if cands:
            return min(cands)
        before = self.base
        for when, after in self.trans:
            if after > before and (wall - after).replace(tzinfo=UTC) < when <= (wall - before).replace(tzinfo=UTC):
                return (wall - before).replace(tzinfo=UTC)
            before = after
        raise ValueError(f"wall time {wall} is not on the site calendar")


def parse_wall(s: str) -> datetime:
    return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M")


def parse_inst(s: str, cal: Calendar) -> datetime:
    s = s.strip()
    if re.search(r"(Z|[+-]\d\d:\d\d)$", s):
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
    return cal.to_utc(datetime.fromisoformat(s.replace(" ", "T")))


def zstr(u: datetime | None) -> str:
    return "" if u is None else u.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# =============================================================================== numerics
def round_sig(q: Fraction, digits: int) -> Fraction:
    if q == 0:
        return q
    sign = 1 if q > 0 else -1
    q = abs(q)
    exp = 0
    while q >= 10 ** (exp + 1):
        exp += 1
    while q < Fraction(10) ** exp:
        exp -= 1
    unit = Fraction(10) ** (exp - digits + 1)
    whole = (q / unit + Fraction(1, 2)).__floor__()
    return sign * whole * unit


def sig_float(v: float, digits: int) -> float:
    return float(round_sig(Fraction(Decimal(repr(v))), digits))


def hours4(seconds: float) -> float:
    q = Fraction(round(seconds), 3600)
    sign = 1 if q >= 0 else -1
    return sign * float((abs(q) * 10000 + Fraction(1, 2)).__floor__() / Fraction(10000))


def wls(xs: list[str], ys: list[Fraction], weighting: str, ncoef: int) -> list[float]:
    fx = [Fraction(x) for x in xs]
    w = [1 / (x * x) if weighting == "1/x^2" else 1 / x for x in fx]
    X = [[Fraction(1), x, x * x][:ncoef] for x in fx]
    A = [[sum(w[i] * X[i][r] * X[i][c] for i in range(len(fx))) for c in range(ncoef)] for r in range(ncoef)]
    B = [sum(w[i] * X[i][r] * ys[i] for i in range(len(fx))) for r in range(ncoef)]
    n = ncoef
    for c in range(n):
        p = next(r for r in range(c, n) if A[r][c] != 0)
        A[c], A[p] = A[p], A[c]
        B[c], B[p] = B[p], B[c]
        for r in range(n):
            if r != c and A[r][c]:
                f = A[r][c] / A[c][c]
                A[r] = [A[r][k] - f * A[c][k] for k in range(n)]
                B[r] -= f * B[c]
    return [float(round_sig(B[i] / A[i][i], 6)) for i in range(n)]


def reading(coef: list[float] | None, y: float) -> float | None:
    if coef is None:
        return None
    a, b = coef[0], coef[1]
    c = coef[2] if len(coef) > 2 else 0.0
    if c == 0.0:
        return (y - a) / b
    rad = b * b + 4 * c * (y - a)
    if rad < 0:
        return None
    return 2 * (y - a) / (b + math.sqrt(rad))


def r2(v: float) -> float:
    return float(Decimal(repr(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def frac(s: str) -> Fraction:
    return Fraction(s.strip())


def median(vals: list[float]) -> float:
    v = sorted(vals)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


# =============================================================================== load
def load(data: Path) -> dict:  # noqa: C901
    S: dict = {}
    prof = yaml_load((data / "analysis_profile_be.yml").read_text(encoding="utf-8"))
    S["prof"] = prof
    S["study"] = prof["study_id"]
    S["analytes"] = [up(a) for a in prof["analytes"]]
    S["pivotal"] = [up(a) for a in prof["pivotal_analytes"]]
    S["params"] = list(prof["parameters"])
    S["scope"] = {up(s) for s in prof["subjects_in_scope"]}
    memo = read_pdf(data / "ba_stat_governance_memo.pdf")
    S["memo"] = memo
    S["method"] = {up(r["analyte"]): r for r in memo["M-2"]["rows"]}
    S["c1"] = {up(r["code"]) for r in memo["C-1"]["rows"] if up(r["allowed"]) == "Y"}
    S["c2"] = {up(r["code"]) for r in memo["C-2"]["rows"] if up(r["allowed"]) == "Y"}
    S["emesis"] = {up(r["preferred_term"]) for r in memo["E-1"]["rows"] if up(r["counts_as_emesis"]) == "Y"}
    S["ttab"] = {int(r["df"]): r for r in memo["T-1"]["rows"]}
    rulings = [r for r in memo["R-1"]["rows"] if up(r["status"]) == "IN FORCE" and up(r["study"]) == up(S["study"])]
    cal = Calendar(yaml_load((data / "site_calendar.yml").read_text(encoding="utf-8")))
    S["cal"] = cal
    wb = data / "bioanalytical_workbook_v3.xlsx"
    runs = {}
    epoch = workbook_epoch(wb)
    for r in read_sheet(wb, "RunPlan", "run_id"):
        if up(r["study"]) != up(S["study"]):
            continue
        runs[up(r["run_id"])] = {"run_id": up(r["run_id"]), "analyte": up(r["analyte"]), "type": up(r["run_type"]), "cal_lot": up(r["cal_lot"]),
                                 "qc_lot": up(r["qc_lot"]), "date": epoch + timedelta(days=int(num(r["analysis_date"])))}
    S["runs"] = runs
    S["nominal"] = {(up(r["lot"]), up(r["level"])): r["certified"].strip() for r in read_sheet(wb, prof["nominal_sheet"], "lot")}
    S["qcnom"] = {(up(r["lot"]), up(r["level"])): num(r["certified"]) for r in read_sheet(wb, "QCLots", "lot")}
    S["seq"] = {up(r["subject"]): up(r["sequence"]) for r in read_sheet(wb, "Randomization", "subject")}
    con = sqlite3.connect(f"file:{data / 'entity_alias_register.sqlite'}?mode=ro", uri=True)
    ralias = {up(t): up(r) for t, r, _ in con.execute("select token, run_id, source from run_alias")}
    links = {up(t): up(s) for t, s, st in con.execute("select token, subject_id, study from subject_alias") if up(st) == up(S["study"])}
    con.close()
    for k in runs:
        ralias[k] = k
    salias = {}
    for tok in links:
        path = [tok]
        while path[-1] not in S["seq"] and path[-1] in links:
            nxt = links[path[-1]]
            if nxt in path:
                break
            path.append(nxt)
        if path[-1] in S["seq"]:
            salias[tok] = path[-1]
    for s in S["seq"]:
        salias[s] = s
    S["ralias"], S["salias"] = ralias, salias
    rel = {}
    for e in ET.parse(data / "tube_relabel_journal.xml").getroot().iter("relabel"):
        if e.get("study") and up(e.get("study")) != up(S["study"]):
            continue
        if up(e.get("status")) == "ACTIVE":
            rel[up(e.get("new"))] = up(e.get("old"))
    S["relabel"] = rel
    S["reject_runs"] = {ralias.get(up(r["target"])) for r in rulings if up(r["action"]) == "REJECT_RUN"}
    S["excl_subj"] = {salias.get(up(r["target"])) for r in rulings if up(r["action"]) == "EXCLUDE_SUBJECT"}
    S["excl_tube"] = {rel.get(up(r["target"]), up(r["target"])) for r in rulings if up(r["action"]) == "EXCLUDE_SAMPLE"}
    S["rulings_all"] = [r for r in memo["R-1"]["rows"] if up(r["study"]) == up(S["study"])]
    # tubes
    tubes = {}
    for r in read_dsv(data / "tube_manifest_main.csv", ","):
        nom = r["nominal_h"]
        tubes[up(r["tube_id"])] = {"tube": up(r["tube_id"]), "subj_tok": r["subject"], "subject": salias.get(up(r["subject"])), "period": int(r["period"]),
                                   "nom": 0.0 if up(nom) == "PRE" else (None if up(nom) == "UNS" else num(nom)),
                                   "collected": up(r["status"]).replace(" ", "_") == "COLLECTED"}
    add = yaml_load((data / "tube_manifest_addendum.yaml").read_text(encoding="utf-8"))
    for r in add["tubes"]:
        nom = r["nominal_h"]
        tubes[up(r["tube"])] = {"tube": up(r["tube"]), "subj_tok": r["subject"], "subject": salias.get(up(r["subject"])), "period": int(r["period"]),
                                "nom": 0.0 if up(nom) == "PRE" else (None if up(nom) == "UNS" else num(nom)),
                                "collected": up(r["status"]).replace(" ", "_") == "COLLECTED"}
    S["tubes"] = tubes
    # doses
    dose = {}
    S["subj_tokens"] = []
    for r in read_dsv(data / "dose_admin_p1.csv", ","):
        S["subj_tokens"].append(r["subject"])
        if up(r["event"]) == "DOSE":
            dose[(salias.get(up(r["subject"])), int(r["period"]))] = cal.to_utc(parse_wall(r["local_time"]))
    root = ET.parse(data / "dose_admin_p2.xml").getroot()
    for e in root.iter("event"):
        S["subj_tokens"].append(e.get("subject"))
        if up(e.get("type")) == "DOSE":
            dose[(salias.get(up(e.get("subject"))), int(root.get("period")))] = parse_inst(e.get("at"), cal)
    S["dose"] = dose
    # draw times
    draw: dict[str, str | None] = {}
    for r in read_dsv(data / "draw_times_g1.tsv", "\t"):
        S["subj_tokens"].append(r["subject"])
        draw[up(r["tube"])] = r["drawn_local"] or None
    for ln in (data / "draw_times_g2.jsonl").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            o = json.loads(ln)
            S["subj_tokens"].append(o["subj"])
            draw[up(o["tube"])] = o["drawn_at"] or None
    journal = {}
    for ln in (data / "draw_time_corrections.ndjson").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            o = json.loads(ln)
            if up(o["status"]) == "POSTED" and str(o["field"]).strip() == "drawn_local":
                journal[int(o["seq"])] = o
    cancelled_by: dict[int, list[int]] = {}
    for q, o in journal.items():
        if up(o.get("action")) == "REVERSE":
            cancelled_by.setdefault(int(o["reverses"]), []).append(q)
    effect: dict[int, bool] = {}
    for q in sorted(journal, reverse=True):
        effect[q] = not any(effect[r] for r in cancelled_by.get(q, []))
    latest: dict[str, tuple[int, str]] = {}
    for q in sorted(journal):
        o = journal[q]
        if effect[q] and up(o.get("action") or "SET") == "SET":
            latest[up(o["tube"])] = (q, o["value"])
    for t, (_, v) in latest.items():
        draw[t] = v or None
    S["draw"] = {k: (parse_inst(v, cal) if v else None) for k, v in draw.items()}
    for t in tubes.values():
        S["subj_tokens"].append(t["subj_tok"])
    # AE, disposition
    con = sqlite3.connect(f"file:{data / 'ae_listing.db'}?mode=ro", uri=True)
    S["ae"] = []
    for st, sj, per, pt, onset in con.execute("select study, subject, period, pt, onset_local from ae_events"):
        if up(st) != up(S["study"]):
            continue
        S["subj_tokens"].append(sj)
        S["ae"].append({"subject": salias.get(up(sj)), "period": int(per), "pt": up(pt), "onset": cal.to_utc(parse_wall(onset))})
    con.close()
    S["withdrawn"] = set()
    for r in read_dsv(data / "subject_disposition.psv", "|"):
        S["subj_tokens"].append(r["subject"])
        if up(r["event"]) == "WITHDRAWN":
            S["withdrawn"].add(salias.get(up(r["subject"])))
    for r in S["rulings_all"]:
        if up(r["action"]) == "EXCLUDE_SUBJECT":
            S["subj_tokens"].append(r["target"])
    # audit, requests, reassay log, dashboard, published
    con = sqlite3.connect(f"file:{data / 'integration_audit_trail.db'}?mode=ro", uri=True)
    last: dict[tuple, tuple] = {}
    for ref, rev, code, st, ts in con.execute("select injection_ref, revision, reason_code, status, ts from audit_entry"):
        k = (up(ref), int(rev))
        if k not in last or ts > last[k][0]:
            last[k] = (ts, up(st), up(code))
    con.close()
    S["approved"] = {k for k, (_, st, code) in last.items() if st == "APPROVED" and code in S["c1"]}
    S["requests"] = [json.loads(x) for x in (data / "std_exclusion_requests.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    S["relog"] = read_dsv(data / "reassay_request_log.csv", ",")
    S["dash"] = {up(r["run_id"]): up(r["lab_status"]) for r in read_dsv(data / "run_status_dashboard.csv", ",")}
    S["pub"] = read_dsv(data / "be_report_published.csv", ",")
    S["pubstats"] = json.loads((data / "be_statistics_published.json").read_text(encoding="utf-8"))
    cat = json.loads((data / "ingest_catalog_be.json").read_text(encoding="utf-8"))
    S["catalog"] = cat["shards"]
    S["shard_recs"] = []
    for sh in cat["shards"]:
        if sh.get("active") is True:
            S["shard_recs"].append((sh, load_shard(data / sh["file"], sh["layout"])))
    return S


# =============================================================================== injections and runs
def dedup(S: dict) -> None:
    rows_read, dups = 0, 0
    first: dict[tuple, dict] = {}
    for _, recs in S["shard_recs"]:
        for r in recs:
            rows_read += 1
            k = (r["inj"], r["rev"])
            if k in first:
                dups += 1
            else:
                first[k] = r
    by_inj: dict[str, list] = {}
    for (inj, _), r in first.items():
        by_inj.setdefault(inj, []).append(r)
    inadm = sup = voided = 0
    eff = {}
    for inj, lst in by_inj.items():
        adm = [r for r in lst if r["void"] or r["integ"] == "AUTO" or (inj, r["rev"]) in S["approved"]]
        inadm += len(lst) - len(adm)
        if not adm:
            continue
        sup += len(adm) - 1
        best = max(adm, key=lambda r: r["rev"])
        if best["void"]:
            voided += 1
        else:
            eff[inj] = best
    S["eff"] = eff
    S["dedup"] = {"rows_read": rows_read, "duplicate_copies": dups, "superseded": sup, "inadmissible_manual": inadm, "voided": voided,
                  "effective_injections": len(eff)}


def tube_of(S: dict, ref: str) -> str | None:
    t = S["relabel"].get(up(ref), up(ref))
    return t if t in S["tubes"] else None


def process_runs(S: dict) -> None:  # noqa: C901
    by_run: dict[str, list] = {}
    for r in S["eff"].values():
        rid = S["ralias"].get(up(r["run_tok"]))
        r["run"] = rid
        if rid in S["runs"]:
            by_run.setdefault(rid, []).append(r)
    cnt = {"standards": 0, "qcs": 0, "blank_zero": 0, "study_sample_injections": 0, "foreign_injections": 0}
    for r in S["eff"].values():
        if r["kind"] == "STD":
            cnt["standards"] += 1
        elif r["kind"] in ("QC", "DQC"):
            cnt["qcs"] += 1
        elif r["kind"] in ("BLANK", "ZERO"):
            cnt["blank_zero"] += 1
        elif tube_of(S, r["ref"]):
            cnt["study_sample_injections"] += 1
        else:
            cnt["foreign_injections"] += 1
    S["dedup"].update(cnt)
    req: dict[str, list] = {}
    for q in S["requests"]:
        if up(q.get("status")) == "APPROVED" and up(q.get("code")) in S["c2"]:
            req.setdefault(S["ralias"].get(up(q.get("run"))), []).append(up(q.get("injection")))
    S["fit"] = {}
    for rid in sorted(S["runs"]):
        run = S["runs"][rid]
        a = run["analyte"]
        if a not in S["analytes"]:
            continue
        m = S["method"][a]
        model, wt = m["model"].strip(), m["weighting"].strip()
        nc = 3 if model == "quadratic" else 2
        lim, lim1 = float(m["std_limit_pct"]), float(m["lloq_std_limit_pct"])
        injs = sorted(by_run.get(rid, []), key=lambda r: r["seq"])
        stds = [r for r in injs if r["kind"] == "STD"]
        for s in stds:
            s["cert"] = S["nominal"][(run["cal_lot"], s["ref"])]
            s["nominal"] = float(s["cert"])
            s["y"] = s["a"] / s["is"]
        assign = {s["inj"] for s in stds if s["inj"] in req.get(rid, [])}
        kept = [s for s in stds if s["inj"] not in assign]
        coef = None
        removed: list[str] = []
        its = 0
        if len(kept) >= nc + 1:
            while True:
                coef = wls([s["cert"] for s in kept], [Fraction(s["a"], s["is"]) for s in kept], wt, nc)
                its += 1
                worst = None
                for s in kept:
                    x = reading(coef + [0.0] * (3 - nc), s["y"])
                    li = lim1 if s["ref"] == "CS1" else lim
                    ratio = math.inf if x is None else abs(100 * (x - s["nominal"]) / s["nominal"]) / li
                    key = (ratio, s["nominal"], s["seq"])
                    if ratio > 1 and (worst is None or key > worst[0]):
                        worst = (key, s)
                if worst is None or len(kept) <= nc + 1:
                    break
                kept.remove(worst[1])
                removed.append(worst[1]["inj"])
        cf = None if coef is None else coef + [0.0] * (3 - nc)
        std_limit_fail = False
        for s in stds:
            s["read"] = reading(cf, s["y"])
            s["dev"] = None if s["read"] is None else 100 * (s["read"] - s["nominal"]) / s["nominal"]
            s["status"] = "NO_CURVE" if cf is None else ("ASSIGNABLE" if s["inj"] in assign else ("REMOVED" if s["inj"] in removed else "RETAINED"))
            if s["status"] == "RETAINED" and (s["dev"] is None or abs(s["dev"]) > (lim1 if s["ref"] == "CS1" else lim)):
                std_limit_fail = True
        ret = [s for s in stds if s["status"] == "RETAINED"]
        lloq = min((s["nominal"] for s in ret), default=None)
        uloq = max((s["nominal"] for s in ret), default=None)
        qcs = [r for r in injs if r["kind"] in ("QC", "DQC")]
        for q in qcs:
            q["nominal"] = S["qcnom"][(run["qc_lot"], q["ref"])]
            rd = reading(cf, q["a"] / q["is"])
            q["back"] = None if rd is None else rd * q["df"]
            q["dev"] = None if q["back"] is None else 100 * (q["back"] - q["nominal"]) / q["nominal"]
            limq = float(m["dqc_limit_pct"] if q["kind"] == "DQC" else m["qc_limit_pct"])
            q["pass"] = q["dev"] is not None and abs(q["dev"]) <= limq
        reg = [q for q in qcs if q["kind"] == "QC"]
        npass = sum(q["pass"] for q in reg)
        reason = ""
        levels = {s["ref"] for s in ret}
        if rid in S["reject_runs"]:
            reason = "RULING"
        elif cf is None:
            reason = "NO_CURVE"
        elif std_limit_fail:
            reason = "STD_LIMIT"
        elif Fraction(len(ret), max(len(stds), 1)) < frac(m["min_std_fraction"]):
            reason = "STD_COUNT"
        elif len(levels) < int(m["min_levels"]):
            reason = "STD_LEVELS"
        elif reg and Fraction(npass, len(reg)) < frac(m["min_qc_fraction"]):
            reason = "QC_TOTAL"
        else:
            for lv in sorted({q["ref"] for q in reg}):
                g = [q for q in reg if q["ref"] == lv]
                if Fraction(sum(q["pass"] for q in g), len(g)) < frac(m["min_qc_level_fraction"]):
                    reason = "QC_LEVEL"
                    break
        dil = any(r["kind"] == "UNK" and r["df"] > 1 for r in injs)
        dq = [q for q in qcs if q["kind"] == "DQC"]
        dqc = ("PASS" if len(dq) >= 2 and all(q["pass"] for q in dq) else "FAIL") if dil else "NA"
        S["fit"][rid] = {"run": run, "model": model, "weighting": wt, "coef": cf, "nc": nc, "stds": stds, "qcs": qcs, "removed": removed, "its": its,
                         "assign": assign, "lloq": lloq, "uloq": uloq, "status": "REJECTED" if reason else "ACCEPTED", "reason": reason,
                         "dqc": dqc, "nlev": len(levels), "npass": npass, "nqc": len(reg), "injs": injs}


def order_key(S: dict, rid: str, seq: int) -> tuple:
    return (S["runs"][rid]["date"], rid, seq)


def results(S: dict) -> None:  # noqa: C901
    relog = {}
    for r in S["relog"]:
        if up(r["status"]) == "CANCELLED":
            continue
        t = S["relabel"].get(up(r["tube"]), up(r["tube"]))
        relog.setdefault((t, up(r["analyte"]), S["ralias"].get(up(r["run"]))), re.sub(r"[- ]", "_", up(r["reason"])))
    res: dict[tuple, list] = {}
    for rid, F in S["fit"].items():
        run = F["run"]
        for r in F["injs"]:
            if r["kind"] != "UNK":
                continue
            t = tube_of(S, r["ref"])
            if t is None or S["tubes"][t]["subject"] not in S["scope"]:
                continue
            a = run["analyte"]
            reason = "ISR" if run["type"] == "ISR" else relog.get((t, a, rid), "ORIGINAL")
            y = r["a"] / r["is"]
            rd = reading(F["coef"], y)
            if F["status"] != "ACCEPTED":
                flag = "RUN_REJECTED"
            elif r["df"] > 1 and F["dqc"] == "FAIL":
                flag = "DQC_FAIL"
            elif rd is not None and rd < F["lloq"]:
                flag = "BLQ"
            elif rd is None or rd > F["uloq"]:
                flag = "ALQ"
            else:
                flag = "OK"
            res.setdefault((t, a), []).append({"run": rid, "inj": r["inj"], "seq": r["seq"], "tube": t, "analyte": a, "reason": reason, "df": r["df"],
                                               "y": y, "read": rd, "conc": sig_float(rd * r["df"], 4) if flag == "OK" else None, "flag": flag,
                                               "used": False})
    rep = {}
    for t, tb in S["tubes"].items():
        if tb["subject"] not in S["scope"]:
            continue
        for a in S["analytes"]:
            lst = sorted(res.get((t, a), []), key=lambda x: order_key(S, x["run"], x["seq"]))
            out = {"status": "NR", "rule": "NONE", "conc": None, "source": ""}
            if t in S["excl_tube"]:
                out = {"status": "EXCL", "rule": "RULING", "conc": None, "source": ""}
            elif not tb["collected"]:
                out = {"status": "NOT_COLLECTED", "rule": "NONE", "conc": None, "source": ""}
            else:
                cand = [x for x in lst if x["flag"] in ("OK", "BLQ", "ALQ") and x["reason"] != "ISR"]
                base = next((x for x in cand if x["reason"] in ("ORIGINAL", "RUN_FAIL")), None)
                if base is not None:
                    if base["flag"] == "ALQ":
                        d = next((x for x in cand if x["reason"] == "ALQ" and x["flag"] == "OK"), None)
                        if d:
                            d["used"] = True
                            out = {"status": "OK", "rule": "ALQ_DILUTION", "conc": d["conc"], "source": d["run"]}
                        else:
                            out = {"status": "NR", "rule": "ALQ_NO_DILUTION", "conc": None, "source": base["run"]}
                    elif base["flag"] == "BLQ":
                        base["used"] = True
                        out = {"status": "BLQ", "rule": base["reason"], "conc": None, "source": base["run"]}
                    else:
                        reps = [x for x in cand if x["reason"] == "PK_REPEAT" and x["flag"] in ("OK", "BLQ")]
                        base["used"] = True
                        if len(reps) >= 2:
                            for x in reps[:2]:
                                x["used"] = True
                            med = median([base["conc"]] + [x["conc"] if x["flag"] == "OK" else 0.0 for x in reps[:2]])
                            out = {"status": "OK" if med > 0 else "BLQ", "rule": "PK_REPEAT_MEDIAN", "conc": med if med > 0 else None, "source": base["run"]}
                        else:
                            out = {"status": "OK", "rule": base["reason"], "conc": base["conc"], "source": base["run"]}
            rep[(t, a)] = out
    S["res"], S["rep"] = res, rep


# =============================================================================== NCA
def ols(pts: list[tuple[float, float]]) -> tuple[float, float, float]:
    n = len(pts)
    mx = sum(t for t, _ in pts) / n
    my = sum(math.log(c) for _, c in pts) / n
    sxx = sum((t - mx) ** 2 for t, _ in pts)
    sxy = sum((t - mx) * (math.log(c) - my) for t, c in pts)
    syy = sum((math.log(c) - my) ** 2 for _, c in pts)
    b = sxy / sxx
    a = my - b * mx
    rsq = 1.0 if syy == 0 else 1 - sum((math.log(c) - a - b * t) ** 2 for t, c in pts) / syy
    return a, b, 1 - (1 - rsq) * (n - 1) / (n - 2)


def nca(S: dict) -> None:  # noqa: C901
    prof = S["prof"]
    minp = int(prof["lambda_z_min_points"])
    tol = float(prof["lambda_z_adj_r2_tolerance"])
    xlim = float(prof["extrap_limit_pct"])
    S["elapsed"] = {}
    for t, tb in S["tubes"].items():
        d = S["dose"].get((tb["subject"], tb["period"]))
        if tb["nom"] == 0:
            S["elapsed"][t] = 0.0
        elif tb["collected"] and d is not None and S["draw"].get(t) is not None:
            S["elapsed"][t] = hours4((S["draw"][t] - d).total_seconds())
        else:
            S["elapsed"][t] = None
    out = {}
    for s in sorted(S["seq"]):
        if s not in S["scope"]:
            continue
        for p in (1, 2):
            if (s, p) not in S["dose"]:
                continue
            for a in S["analytes"]:
                raw = []
                for t, tb in S["tubes"].items():
                    if tb["subject"] != s or tb["period"] != p or tb["nom"] is None:
                        continue
                    rp = S["rep"][(t, a)]
                    el = S["elapsed"][t]
                    if rp["status"] not in ("OK", "BLQ") or el is None:
                        continue
                    raw.append((el, tb["nom"], rp["status"], rp["conc"]))
                raw.sort(key=lambda x: (x[0], x[1]))
                pts = []
                seen = False
                for el, _, st, c in raw:
                    if st == "OK":
                        seen = True
                        pts.append((el, c))
                    elif not seen:
                        pts.append((el, 0.0))
                R = {"n_points": len(pts), "flag": "NOT_EVALUABLE", "cands": [], "chosen": None}
                pos = [i for i, (_, c) in enumerate(pts) if c > 0]
                if len(pos) >= 3:
                    cmax = max(c for _, c in pts)
                    im = next(i for i, (_, c) in enumerate(pts) if c == cmax)
                    il = pos[-1]
                    auc = 0.0
                    for (t1, c1), (t2, c2) in zip(pts[:il], pts[1:il + 1]):
                        if c2 < c1 and c2 > 0 and c1 > 0:
                            auc += (c1 - c2) / math.log(c1 / c2) * (t2 - t1)
                        else:
                            auc += (c1 + c2) / 2 * (t2 - t1)
                    R.update({"cmax": cmax, "tmax": pts[im][0], "clast": pts[il][1], "tlast": pts[il][0], "auc": auc, "flag": "NO_LAMBDA_Z"})
                    tail = [pts[i] for i in pos if i > im]
                    for n in range(minp, len(tail) + 1):
                        ia, ib, adj = ols(tail[-n:])
                        R["cands"].append({"n": n, "slope": ib, "intercept": ia, "adj_r2": adj, "eligible": ib < 0})
                    el = [c for c in R["cands"] if c["eligible"]]
                    if el:
                        best = max(c["adj_r2"] for c in el)
                        ch = max((c for c in el if c["adj_r2"] >= best - tol), key=lambda c: c["n"])
                        lz = -ch["slope"]
                        cp = math.exp(ch["intercept"] - lz * R["tlast"])
                        ai = auc + cp / lz
                        ex = 100 * (cp / lz) / ai
                        R.update({"chosen": ch["n"], "lz": lz, "adj": ch["adj_r2"], "hl": math.log(2) / lz, "cpred": cp, "aucinf": ai, "extrap": ex,
                                  "flag": "EXTRAP_GT_LIMIT" if ex > xlim else "OK"})
                out[(s, p, a)] = R
    S["nca"] = out


# =============================================================================== populations and statistics
def populations(S: dict) -> None:  # noqa: C901
    prof = S["prof"]
    piv = S["pivotal"][0]
    clim = float(prof["carryover_limit_pct"])
    fac = float(prof["emesis_window_factor"])
    eligible = [s for s in sorted(S["seq"]) if s in S["scope"] and s not in S["excl_subj"] and s not in S["withdrawn"]
                and (s, 1) in S["dose"] and (s, 2) in S["dose"]]
    ref_tmax = {}
    for s in eligible:
        p_ref = S["seq"][s].index("R") + 1
        R = S["nca"].get((s, p_ref, piv))
        if R and R["flag"] != "NOT_EVALUABLE":
            ref_tmax[s] = R["tmax"]
    onsets = []
    for e in sorted(S["ae"], key=lambda e: (e["period"], e["onset"])):
        d = S["dose"].get((e["subject"], e["period"]))
        if e["subject"] in eligible and e["pt"] in S["emesis"] and d is not None:
            onsets.append((e["subject"], e["period"], hours4((e["onset"] - d).total_seconds())))

    def emetic_under(window: float) -> dict:
        found: dict = {}
        for subj, per, h in onsets:
            if subj not in found and 0 <= h <= window:
                found[subj] = (per, h)
        return found

    history: list[tuple[float, float, dict]] = []
    seen: dict[frozenset, int] = {}
    left_out: frozenset = frozenset()
    while True:
        kept = [v for s, v in ref_tmax.items() if s not in left_out]
        mean_t = sum(kept) / len(kept)
        window = fac * mean_t
        found = emetic_under(window)
        key = frozenset(found)
        history.append((mean_t, window, found))
        if key in seen:
            first = seen[key]
            last = len(history) - 1
            if first == last - 1:
                chosen, settle = last, "CONVERGED"
            else:
                chosen = first
                for i in range(first + 1, last):
                    if history[i][1] > history[chosen][1]:
                        chosen = i
                settle = "CYCLE"
            break
        seen[key] = len(history) - 1
        left_out = key
    S["median_tmax"], S["window"], emesis = history[chosen]
    S["emesis_passes"], S["emesis_settle"] = len(history), settle
    pre = {}
    for t, tb in S["tubes"].items():
        if tb["nom"] == 0:
            pre[(tb["subject"], tb["period"])] = t
    pop, excl = {}, []
    for s in sorted(S["seq"]):
        for a in S["analytes"]:
            reason, period, value = "", None, None
            R = [S["nca"].get((s, p, a)) for p in (1, 2)]
            if s not in S["scope"]:
                reason = "NOT_IN_SCOPE"
            elif s in S["excl_subj"]:
                reason = "RULING"
            elif s in S["withdrawn"]:
                reason = "WITHDRAWN"
            elif any((s, p) not in S["dose"] for p in (1, 2)):
                reason = "INCOMPLETE"
                period = next(p for p in (1, 2) if (s, p) not in S["dose"])
            elif s in emesis:
                reason = "EMESIS"
                period, value = emesis[s]
            elif any(r["flag"] == "NOT_EVALUABLE" for r in R):
                reason = "NOT_EVALUABLE"
                period = next(p for p in (1, 2) if R[p - 1]["flag"] == "NOT_EVALUABLE")
            else:
                for p in (1, 2):
                    t = pre.get((s, p))
                    rp = S["rep"].get((t, a)) if t else None
                    if rp and rp["status"] == "OK" and rp["conc"] > clim / 100 * R[p - 1]["cmax"]:
                        reason, period, value = "CARRYOVER", p, 100 * rp["conc"] / R[p - 1]["cmax"]
                        break
            if reason and reason != "NOT_IN_SCOPE":
                excl.append({"subject_id": s, "analyte": a, "reason": reason, "period": period, "value": value})
            for prm in ("Cmax", "AUClast", "AUCinf"):
                r2_ = reason
                if not r2_ and prm == "AUCinf":
                    if any(r["flag"] == "NO_LAMBDA_Z" for r in R):
                        r2_ = "PARAM_NA"
                    elif any(r["flag"] == "EXTRAP_GT_LIMIT" for r in R):
                        r2_ = "EXTRAP"
                pop[(s, a, prm)] = r2_
    S["pop"], S["excl"] = pop, excl


PKEY = {"Cmax": "cmax", "AUClast": "auc", "AUCinf": "aucinf"}


def be_stats(S: dict) -> None:
    prof = S["prof"]
    alpha = float(prof["alpha"])
    p = 1 - alpha
    col = next(k for k in next(iter(S["ttab"].values())) if k.startswith("p=") and abs(float(k[2:]) - p) < 1e-9)
    lo, hi = float(prof["be_lower_pct"]), float(prof["be_upper_pct"])
    out = {}
    for a in S["analytes"]:
        role = "PIVOTAL" if a in S["pivotal"] else "SUPPORTIVE"
        params = {}
        for prm in S["params"]:
            d = {"TR": [], "RT": []}
            ys = {("TR", "T"): [], ("TR", "R"): [], ("RT", "T"): [], ("RT", "R"): []}
            for s in sorted(S["seq"]):
                if S["pop"][(s, a, prm)]:
                    continue
                q = S["seq"][s]
                v1, v2 = math.log(S["nca"][(s, 1, a)][PKEY[prm]]), math.log(S["nca"][(s, 2, a)][PKEY[prm]])
                d[q].append((v2 - v1) / 2)
                ys[(q, q[0])].append(v1)
                ys[(q, q[1])].append(v2)
            n1, n2 = len(d["TR"]), len(d["RT"])
            df = n1 + n2 - 2
            if n1 < 1 or n2 < 1 or df < 1:
                params[prm] = {k: None for k in ("n_TR", "n_RT", "df", "t_quantile", "estimate_log", "se_log", "mse", "cv_intra_pct", "lsmean_T", "lsmean_R",
                                                 "ratio_pct", "ci_lower_pct", "ci_upper_pct", "ratio_pct_r", "ci_lower_r", "ci_upper_r")}
                params[prm].update({"n_TR": n1, "n_RT": n2, "result": "NOT_ESTIMABLE"})
                continue
            m1, m2 = sum(d["TR"]) / n1, sum(d["RT"]) / n2
            s2 = (sum((x - m1) ** 2 for x in d["TR"]) + sum((x - m2) ** 2 for x in d["RT"])) / df
            se = math.sqrt(s2 * (1 / n1 + 1 / n2))
            est = m2 - m1
            t = float(S["ttab"][df][col])
            lsT = (sum(ys[("TR", "T")]) / n1 + sum(ys[("RT", "T")]) / n2) / 2
            lsR = (sum(ys[("TR", "R")]) / n1 + sum(ys[("RT", "R")]) / n2) / 2
            ratio, cl, cu = 100 * math.exp(est), 100 * math.exp(est - t * se), 100 * math.exp(est + t * se)
            rr, rl, ru = r2(ratio), r2(cl), r2(cu)
            res = ("PASS" if rl >= lo and ru <= hi else "FAIL") if role == "PIVOTAL" else "INFO"
            params[prm] = {"n_TR": n1, "n_RT": n2, "df": df, "t_quantile": t, "estimate_log": est, "se_log": se, "mse": 2 * s2,
                           "cv_intra_pct": 100 * math.sqrt(math.exp(2 * s2) - 1), "lsmean_T": math.exp(lsT), "lsmean_R": math.exp(lsR),
                           "ratio_pct": ratio, "ci_lower_pct": cl, "ci_upper_pct": cu, "ratio_pct_r": rr, "ci_lower_r": rl, "ci_upper_r": ru, "result": res}
        concl = ("BIOEQUIVALENT" if all(v["result"] == "PASS" for v in params.values()) else "NOT_BIOEQUIVALENT") if role == "PIVOTAL" else "SUPPORTIVE"
        out[a] = {"role": role, "conclusion": concl, "parameters": params}
    S["be"] = {"study_id": S["study"], "alpha": alpha, "ci_level_pct": 100 * (1 - 2 * alpha), "limits_pct": [lo, hi], "analytes": out}
    S["tcol"] = col


# =============================================================================== render
def six(v: float) -> str:
    d = Decimal(repr(v))
    if d == 0:
        return "0"
    d = d.quantize(Decimal(1).scaleb(d.adjusted() - 5), rounding=ROUND_HALF_UP)
    text = format(d, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def f(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return six(v)
    return str(v)


def json_ready(o: object) -> object:
    if isinstance(o, float):
        return float(six(o))
    if isinstance(o, dict):
        return {k: json_ready(v) for k, v in o.items()}
    if isinstance(o, list):
        return [json_ready(v) for v in o]
    return o


def dsv(head: list[str], rows: list[list[object]], sep: str) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=sep, lineterminator="\n")
    w.writerow(head)
    for r in rows:
        w.writerow([f(x) for x in r])
    return buf.getvalue()


def jdump(o: object) -> str:
    return json.dumps(json_ready(o), indent=2) + "\n"


def nomtxt(v: float) -> str:
    return f"{v:g}"


def render(S: dict) -> dict[str, str]:  # noqa: C901
    O: dict[str, str] = {}
    runs = []
    for rid in sorted(S["fit"]):
        F = S["fit"][rid]
        c = F["coef"]
        runs.append({"run_id": rid, "analyte": F["run"]["analyte"], "model": F["model"], "weighting": F["weighting"], "cal_lot": F["run"]["cal_lot"],
                     "coefficients": None if c is None else {"a": c[0], "b": c[1], "c": c[2] if F["nc"] == 3 else None},
                     "n_standards": len(F["stds"]), "n_assignable": len(F["assign"]), "n_retained": sum(1 for s in F["stds"] if s["status"] == "RETAINED"),
                     "removed": F["removed"], "iterations": F["its"], "lloq": F["lloq"], "uloq": F["uloq"]})
    O["calibration_fits.json"] = jdump({"study_id": S["study"], "nominal_sheet": S["prof"]["nominal_sheet"], "runs": runs})
    rows = []
    for rid in sorted(S["fit"]):
        for s in S["fit"][rid]["stds"]:
            rows.append([rid, s["inj"], s["ref"], s["nominal"], s["y"], s["read"], s["dev"], s["status"]])
    O["standard_backcalc.tsv"] = dsv(["run_id", "injection_id", "level", "nominal", "response", "back_calculated", "deviation_pct", "status"], rows, "\t")
    rows = []
    for rid in sorted(S["fit"]):
        for q in S["fit"][rid]["qcs"]:
            rows.append([rid, q["inj"], q["ref"], q["nominal"], q["df"], q["back"], q["dev"], "Y" if q["pass"] else "N"])
    O["qc_results.csv"] = dsv(["run_id", "injection_id", "qc_level", "nominal", "dilution_factor", "back_calculated", "deviation_pct", "pass"], rows, ",")
    rows = []
    for rid in sorted(S["fit"]):
        F = S["fit"][rid]
        lab = S["dash"].get(rid, "")
        rows.append([rid, F["run"]["analyte"], F["run"]["type"], F["run"]["date"].isoformat(), len(F["stds"]), sum(1 for s in F["stds"] if s["status"] == "RETAINED"),
                     F["nlev"], F["nqc"], F["npass"], F["status"], F["reason"], F["dqc"], lab, "Y" if lab == F["status"] else "N"])
    O["run_acceptance.csv"] = dsv(["run_id", "analyte", "run_type", "analysis_date", "n_std_total", "n_std_retained", "n_levels_retained", "qc_total", "qc_pass",
                                   "status", "reason", "dqc_status", "lab_status", "agrees"], rows, ",")
    rows = []
    ai = {a: i for i, a in enumerate(S["analytes"])}
    for (t, a) in sorted(S["res"], key=lambda k: (k[0], ai[k[1]])):
        for x in sorted(S["res"][(t, a)], key=lambda x: order_key(S, x["run"], x["seq"])):
            rows.append([x["run"], x["inj"], t, a, x["reason"], x["df"], x["y"], x["read"], x["conc"], x["flag"], "Y" if x["used"] else "N"])
    O["tube_results.psv"] = dsv(["run_id", "injection_id", "tube", "analyte", "reason", "dilution_factor", "response", "back_calculated", "concentration",
                                   "flag", "used"], rows, "|")
    sched = sorted((tb for tb in S["tubes"].values() if tb["subject"] in S["scope"] and tb["nom"] is not None),
                   key=lambda tb: (tb["subject"], tb["period"], tb["nom"], tb["tube"]))
    rows = []
    for tb in sorted(sched, key=lambda tb: (tb["subject"], tb["period"])):
        pass
    keyed = []
    for tb in sched:
        for a in S["analytes"]:
            keyed.append(((tb["subject"], tb["period"], ai[a], tb["nom"], tb["tube"]), tb, a))
    for _, tb, a in sorted(keyed, key=lambda k: k[0]):
        rp = S["rep"][(tb["tube"], a)]
        form = S["seq"][tb["subject"]][tb["period"] - 1] if tb["subject"] in S["seq"] else ""
        el = S["elapsed"][tb["tube"]] if rp["status"] != "NOT_COLLECTED" else None
        rows.append([tb["subject"], tb["period"], form, a, tb["nom"], tb["tube"], el, rp["conc"], rp["status"], rp["rule"], rp["source"]])
    O["reported_concentrations.csv"] = dsv(["subject_id", "period", "formulation", "analyte", "nominal_h", "tube", "actual_h", "concentration", "status", "rule",
                                            "source_run"], rows, ",")
    root = ET.Element("sampling_times", {"study": S["study"]})
    for tb in sched:
        d = S["dose"].get((tb["subject"], tb["period"]))
        dr = S["draw"].get(tb["tube"]) if tb["collected"] else None
        el = S["elapsed"][tb["tube"]] if tb["collected"] else None
        ET.SubElement(root, "tube", {"id": tb["tube"], "subject": tb["subject"], "period": str(tb["period"]), "nominal_h": f(float(tb["nom"])),
                                     "dose_utc": zstr(d), "drawn_utc": zstr(dr), "elapsed_h": f(el)})
    ET.indent(root)
    O["sampling_times.xml"] = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"
    lim = float(S["prof"]["isr_limit_pct"])
    isr = {}
    for a in S["analytes"]:
        pairs = []
        for (t, a2), lst in S["res"].items():
            if a2 != a or S["rep"][(t, a)]["status"] != "OK":
                continue
            rr = sorted((x for x in lst if x["reason"] == "ISR" and x["flag"] == "OK"), key=lambda x: order_key(S, x["run"], x["seq"]))
            if not rr:
                continue
            o, rpt = S["rep"][(t, a)]["conc"], rr[0]["conc"]
            dp = 100 * (rpt - o) / ((rpt + o) / 2)
            pairs.append({"tube": t, "run_id": rr[0]["run"], "reported": o, "repeat": rpt, "diff_pct": dp, "within": abs(dp) <= lim})
        pairs.sort(key=lambda x: x["tube"])
        nw = sum(p["within"] for p in pairs)
        isr[a] = {"pairs": pairs, "n_pairs": len(pairs), "n_within": nw, "pct_within": (100 * nw / len(pairs)) if pairs else None,
                  "pass": bool(pairs) and nw * 3 >= len(pairs) * 2}
    O["isr_assessment.json"] = jdump({"limit_pct": lim, "analytes": isr})
    rows, lzl = [], []
    for (s, p, a) in sorted(S["nca"], key=lambda k: (k[0], k[1], ai[k[2]])):
        R = S["nca"][(s, p, a)]
        g = R.get
        rows.append([s, p, S["seq"][s][p - 1], a, R["n_points"], g("cmax"), g("tmax"), g("clast"), g("tlast"), g("auc"), g("lz"), g("chosen"), g("adj"), g("hl"),
                     g("cpred"), g("aucinf"), g("extrap"), R["flag"]])
        lzl.append(json.dumps(json_ready({"subject_id": s, "period": p, "analyte": a, "candidates": R["cands"], "chosen_n": R["chosen"]})) + "\n")
    O["nca_parameters.csv"] = dsv(["subject_id", "period", "formulation", "analyte", "n_points", "cmax", "tmax", "clast", "tlast", "auc_last", "lambda_z",
                                   "lz_points", "lz_adj_r2", "half_life", "clast_pred", "auc_inf", "auc_extrap_pct", "flag"], rows, ",")
    O["lambda_z_selection.jsonl"] = "".join(lzl)
    O["be_statistics.json"] = jdump(S["be"])
    md = [f"# {S['study']} bioequivalence summary", "", "| analyte | parameter | n | ratio_pct | ci_lower | ci_upper | cv_intra_pct | result |", "|---|---|---|---|---|---|---|---|"]
    for a in S["analytes"]:
        for prm in S["params"]:
            v = S["be"]["analytes"][a]["parameters"][prm]
            if v["result"] == "NOT_ESTIMABLE":
                md.append(f"| {a} | {prm} | {v['n_TR'] + v['n_RT']} |  |  |  |  | NOT_ESTIMABLE |")
            else:
                md.append(f"| {a} | {prm} | {v['n_TR'] + v['n_RT']} | {v['ratio_pct_r']:.2f} | {v['ci_lower_r']:.2f} | {v['ci_upper_r']:.2f} | {r2(v['cv_intra_pct']):.2f} | {v['result']} |")
    O["be_summary.md"] = "\n".join(md) + "\n"
    pi = {p: i for i, p in enumerate(S["params"])}
    rows = []
    for (s, a, prm) in sorted((k for k in S["pop"] if k[2] in pi), key=lambda k: (k[0], ai[k[1]], pi[k[2]])):
        r = S["pop"][(s, a, prm)]
        rows.append([s, a, prm, "N" if r else "Y", r])
    O["analysis_populations.csv"] = dsv(["subject_id", "analyte", "parameter", "included", "reason"], rows, ",")
    O["excluded_subjects.jsonl"] = "".join(json.dumps(json_ready(e)) + "\n" for e in sorted(S["excl"], key=lambda e: (e["subject_id"], ai[e["analyte"]])))
    rows = []
    for a in S["analytes"]:
        incl = {s for s in S["seq"] if not S["pop"][(s, a, "Cmax")]}
        for form in ("R", "T"):
            grid: dict[float, list] = {}
            for t, tb in S["tubes"].items():
                if tb["subject"] not in incl or tb["nom"] is None or S["seq"][tb["subject"]][tb["period"] - 1] != form:
                    continue
                rp = S["rep"][(t, a)]
                if rp["status"] == "OK":
                    grid.setdefault(tb["nom"], []).append(rp["conc"])
                elif rp["status"] == "BLQ":
                    grid.setdefault(tb["nom"], []).append(0.0)
            for nom in sorted(grid):
                v = grid[nom]
                mean = sum(v) / len(v)
                sd = math.sqrt(sum((x - mean) ** 2 for x in v) / (len(v) - 1)) if len(v) > 1 else None
                rows.append([a, form, nom, len(v), mean, sd])
    O["mean_profiles.csv"] = dsv(["analyte", "formulation", "nominal_h", "n", "mean", "sd"], rows, ",")
    O["dedup_report.json"] = jdump(S["dedup"])
    effk = {(r["inj"], r["rev"]) for r in S["eff"].values()}
    sh = []
    for meta, recs in S["shard_recs"]:
        sh.append({"file": meta["file"], "layout": meta["layout"], "rows": len(recs), "effective": sum(1 for r in recs if (r["inj"], r["rev"]) in effk)})
    O["source_lineage.json"] = jdump({"shards": sh, "inactive": [m["file"] for m in S["catalog"] if m.get("active") is not True]})
    al = set()
    rtoks = [r["run_tok"] for _, recs in S["shard_recs"] for r in recs] + [q.get("run", "") for q in S["requests"]] + [r["run"] for r in S["relog"]]
    rtoks += [r["target"] for r in S["rulings_all"] if up(r["action"]) == "REJECT_RUN"]
    for tk in rtoks:
        if up(tk) in S["ralias"]:
            al.add(("run", up(tk), S["ralias"][up(tk)]))
    for tk in S["subj_tokens"]:
        if up(tk) in S["salias"]:
            al.add(("subject", up(tk), S["salias"][up(tk)]))
    ttoks = [r["ref"] for _, recs in S["shard_recs"] for r in recs if r["kind"] == "UNK"] + [r["tube"] for r in S["relog"]]
    ttoks += [r["target"] for r in S["rulings_all"] if up(r["action"]) == "EXCLUDE_SAMPLE"]
    for tk in ttoks:
        if up(tk) in S["relabel"]:
            al.add(("tube", up(tk), S["relabel"][up(tk)]))
    O["alias_resolution.csv"] = dsv(["kind", "token", "canonical"], [list(x) for x in sorted(al)], ",")
    prof = S["prof"]
    y = [f"study_id: {S['study']}", f"nominal_sheet: {prof['nominal_sheet']}", f"alpha: {prof['alpha']}", f"ci_level_pct: {f(S['be']['ci_level_pct'])}",
         f"be_lower_pct: {prof['be_lower_pct']}", f"be_upper_pct: {prof['be_upper_pct']}", f"t_quantile_p: {S['tcol'][2:]}",
         f"lambda_z_min_points: {prof['lambda_z_min_points']}", f"lambda_z_adj_r2_tolerance: {prof['lambda_z_adj_r2_tolerance']}",
         f"extrap_limit_pct: {prof['extrap_limit_pct']}", f"carryover_limit_pct: {prof['carryover_limit_pct']}", f"emesis_window_factor: {prof['emesis_window_factor']}",
         f"emesis_reference_mean_tmax_h: {f(S['median_tmax'])}", f"emesis_window_h: {f(S['window'])}", f"emesis_passes: {S['emesis_passes']}",
         f"emesis_settlement: {S['emesis_settle']}", f"isr_limit_pct: {prof['isr_limit_pct']}"]
    for a in S["analytes"]:
        m = S["method"][a]
        y += [f"{a}.model: {m['model']}", f"{a}.weighting: {m['weighting']}", f"{a}.std_limit_pct: {m['std_limit_pct']}",
              f"{a}.lloq_std_limit_pct: {m['lloq_std_limit_pct']}", f"{a}.qc_limit_pct: {m['qc_limit_pct']}"]
    y += ["conventions_table: P-1", "method_table: M-2", "t_table: T-1"]
    O["parameters_used.yaml"] = "\n".join(y) + "\n"
    pub = {}
    for r in S["pub"]:
        for prm, col in (("Cmax", "cmax"), ("AUClast", "auc_last"), ("AUCinf", "auc_inf")):
            pub[(up(r["subject"]), int(r["period"]), up(r["analyte"]), prm)] = num(r[col]) if r[col] else None
    rec = {}
    for (s, p, a), R in S["nca"].items():
        rec[(s, p, a, "Cmax")] = R.get("cmax")
        rec[(s, p, a, "AUClast")] = R.get("auc")
        rec[(s, p, a, "AUCinf")] = R.get("aucinf") if R["flag"] == "OK" else None
    po = {"Cmax": 0, "AUClast": 1, "AUCinf": 2}
    rows = []
    for k in sorted(set(pub) | set(rec), key=lambda k: (k[0], k[1], k[2], po[k[3]])):
        pv, rv = pub.get(k), rec.get(k)
        if pv is None and rv is None:
            continue
        if pv is None:
            st, dp = "ONLY_RECOMPUTED", None
        elif rv is None:
            st, dp = "ONLY_PUBLISHED", None
        else:
            dp = 100 * (rv - pv) / pv
            st = "MATCH" if abs(dp) <= 1 else "DIFF"
        rows.append([k[0], k[1], k[2], k[3], pv, rv, dp, st])
    O["variance_vs_published.csv"] = dsv(["subject_id", "period", "analyte", "parameter", "published", "recomputed", "diff_pct", "status"], rows, ",")
    ps = {(up(r["analyte"]), r["parameter"]): r for r in S["pubstats"]["results"]}
    md = [f"# {S['study']} published versus recomputed", "",
          "| analyte | parameter | published_ratio | published_lower | published_upper | published_result | recomputed_ratio | recomputed_lower | recomputed_upper | recomputed_result |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for a in S["analytes"]:
        for prm in S["params"]:
            pr = ps.get((a, prm), {})
            v = S["be"]["analytes"][a]["parameters"][prm]
            rc = ["", "", ""] if v["result"] == "NOT_ESTIMABLE" else [f"{v['ratio_pct_r']:.2f}", f"{v['ci_lower_r']:.2f}", f"{v['ci_upper_r']:.2f}"]
            pv = [f(pr.get("ratio_pct")), f(pr.get("ci_lower_pct")), f(pr.get("ci_upper_pct")), pr.get("result", "")]
            md.append(f"| {a} | {prm} | " + " | ".join(pv) + " | " + " | ".join(rc) + f" | {v['result']} |")
    O["reconciliation.md"] = "\n".join(md) + "\n"
    return O


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    data, out = Path(sys.argv[1]), Path(sys.argv[2])
    S = load(data)
    dedup(S)
    process_runs(S)
    results(S)
    nca(S)
    populations(S)
    be_stats(S)
    O = render(S)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for name in OUTPUTS:
        b = O[name].encode("utf-8")
        (out / name).write_bytes(b)
        files.append({"name": name, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    (out / "manifest.json").write_text(json.dumps({"files": files}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
