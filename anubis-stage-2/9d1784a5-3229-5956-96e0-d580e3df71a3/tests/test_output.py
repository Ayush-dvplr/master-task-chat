"""Deterministic checks for the cryostat heat-load budget task.

The verifier container holds no input directory: the shipped corpus is embedded below, held-out corpora are
synthesized at grade time by the embedded generator, and every expectation is derived here independently.
"""
from __future__ import annotations

import ast
import base64
import csv
import hashlib
import io
import json
import math
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

# --------------------------------------------------------------------------- generator: utilities
_GUTC = timezone.utc


def _Gfr(x: Any) -> Fraction:
    return x if isinstance(x, Fraction) else Fraction(str(x))


def _Gq(x: Any, places: int) -> str:
    """Exact decimal text of x with a fixed number of places (half-even)."""
    f = _Gfr(x)
    scaled = round(f * (10 ** places))
    neg = scaled < 0
    s = str(abs(scaled)).rjust(places + 1, "0")
    out = s if places == 0 else s[:-places] + "." + s[-places:]
    return ("-" if neg else "") + out


def _Gsig(x: Any, digits: int) -> str:
    """x rounded half-even to a number of significant digits, as plain decimal text."""
    f = _Gfr(x)
    if f == 0:
        return "0"
    e = 0
    a = abs(f)
    while a >= 10:
        a /= 10
        e += 1
    while a < 1:
        a *= 10
        e -= 1
    places = digits - 1 - e
    if places >= 0:
        return _Gq(f, places)
    step = 10 ** (-places)
    return str(round(f / step) * step)


def _Gstrip(s: str) -> str:
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _Goffset_at(u: datetime, cal: dict) -> int:
    off = cal["base"]
    for when, o in cal["transitions"]:
        if u >= when:
            off = o
    return off


def _Gwall_to_utc(w: datetime, cal: dict) -> datetime:
    offs = sorted({cal["base"]} | {o for _, o in cal["transitions"]})
    cands = []
    for o in offs:
        u = (w - timedelta(minutes=o)).replace(tzinfo=_GUTC)
        if _Goffset_at(u, cal) == o:
            cands.append(u)
    if cands:
        return min(cands)
    prev = cal["base"]
    for when, o in cal["transitions"]:
        a = (w - timedelta(minutes=prev)).replace(tzinfo=_GUTC)
        b = (w - timedelta(minutes=o)).replace(tzinfo=_GUTC)
        if a >= when > b:
            return a
        prev = o
    raise ValueError(f"unmappable wall time {w}")


def _Gutc_to_wall(u: datetime, cal: dict) -> datetime:
    return (u + timedelta(minutes=_Goffset_at(u, cal))).replace(tzinfo=None)


def _Gin_gap(w: datetime, cal: dict) -> bool:
    offs = {cal["base"]} | {o for _, o in cal["transitions"]}
    return not any(_Goffset_at((w - timedelta(minutes=o)).replace(tzinfo=_GUTC), cal) == o for o in offs)


def _Gambiguous(w: datetime, cal: dict) -> bool:
    offs = {cal["base"]} | {o for _, o in cal["transitions"]}
    return sum(1 for o in offs if _Goffset_at((w - timedelta(minutes=o)).replace(tzinfo=_GUTC), cal) == o) > 1


def _Goff_text(m: int) -> str:
    sign = "+" if m >= 0 else "-"
    m = abs(m)
    return f"{sign}{m // 60:02d}:{m % 60:02d}"


def _Gz(u: datetime) -> str:
    return u.astimezone(_GUTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _Giso_off(u: datetime, cal: dict) -> str:
    return _Gutc_to_wall(u, cal).strftime("%Y-%m-%dT%H:%M:%S") + _Goff_text(_Goffset_at(u, cal))


def _Gepoch(u: datetime) -> int:
    return int((u - datetime(1970, 1, 1, tzinfo=_GUTC)).total_seconds())


def _Gserial(d: date, date1904: bool) -> int:
    return (d - (date(1904, 1, 1) if date1904 else date(1899, 12, 30))).days


def _Gwrite(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _Gdelim(header: list[str], rows: list[list[Any]], delim: str = ",") -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def _Gxesc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _Gcol(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _Gxlsx(path: Path, sheets: list[tuple[str, list[list[Any]], bool]], file_order: list[int], rng: random.Random, date1904: bool) -> None:
    """Real OOXML workbook: shared and inline strings, numeric cells, scrambled part order, hidden sheets."""
    strings: list[str] = []
    index: dict[str, int] = {}

    def sidx(s: str) -> int:
        if s not in index:
            index[s] = len(strings)
            strings.append(s)
        return index[s]

    sheet_xml: list[str] = []
    for _, rows, _hidden in sheets:
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for r, row in enumerate(rows, 1):
            cells = []
            for c, val in enumerate(row):
                if val is None or val == "":
                    continue
                ref = f"{_Gcol(c)}{r}"
                if isinstance(val, int) and not isinstance(val, bool):
                    cells.append(f'<c r="{ref}"><v>{val}</v></c>')
                elif isinstance(val, tuple) and val[0] == "n":
                    cells.append(f'<c r="{ref}"><v>{val[1]}</v></c>')
                elif rng.random() < 0.2:
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{_Gxesc(str(val))}</t></is></c>')
                else:
                    cells.append(f'<c r="{ref}" t="s"><v>{sidx(str(val))}</v></c>')
            out.append(f'<row r="{r}">' + "".join(cells) + "</row>")
        out.append("</sheetData></worksheet>")
        sheet_xml.append("".join(out))
    n = len(sheets)
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
          '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>',
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    for k in range(n):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{k + 1}.xml" '
                  'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ct.append("</Types>")
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          + ('<workbookPr date1904="1"/>' if date1904 else '<workbookPr defaultThemeVersion="164011"/>') + '<sheets>']
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for k, (name, _, hidden) in enumerate(sheets):
        st = ' state="hidden"' if hidden else ""
        wb.append(f'<sheet name="{_Gxesc(name)}" sheetId="{k + 1}"{st} r:id="rId{k + 1}"/>')
        rels.append(f'<Relationship Id="rId{k + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{file_order[k]}.xml"/>')
    wb.append("</sheets></workbook>")
    rels.append(f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>')
    rels.append(f'<Relationship Id="rId{n + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    rels.append("</Relationships>")
    sst = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">']
    sst += [f'<si><t xml:space="preserve">{_Gxesc(s)}</t></si>' for s in strings]
    sst.append("</sst>")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 '</Relationships>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
              '<borders count="1"><border/></borders>'
              '<cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="1"><xf/></cellXfs>'
              '</styleSheet>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        def put(name: str, data: str) -> None:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 27, 9, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
        put("[Content_Types].xml", "".join(ct))
        put("_rels/.rels", root_rels)
        put("xl/workbook.xml", "".join(wb))
        put("xl/_rels/workbook.xml.rels", "".join(rels))
        put("xl/sharedStrings.xml", "".join(sst))
        put("xl/styles.xml", styles)
        for k in range(n):
            put(f"xl/worksheets/sheet{file_order[k]}.xml", sheet_xml[k])


def _Gpesc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _Gpdf(path: Path, pages: list[list[list[str]]], rng: random.Random, footer: str) -> None:
    """Real PDF 1.4, one Flate content stream per page.

    Every cell is its own text object placed with an absolute Tm matrix and the objects of a page are
    written in shuffled order, so rows only reappear after grouping by y and ordering by x. Cells are
    literal strings, hexadecimal strings or TJ arrays whose kerning offsets split the string.
    """
    objs: list[bytes] = []
    n_pages = len(pages)
    page_ids = [4 + 2 * p for p in range(n_pages)]
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{i} 0 R" for i in page_ids)
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for p, rows in enumerate(pages):
        ops = []
        y = 806
        for cells in rows:
            for k, cell in enumerate(cells):
                u = rng.random()
                if len(cell) > 3 and u < 0.22:
                    cut = rng.randint(1, len(cell) - 1)
                    show = f"[({_Gpesc(cell[:cut])}) {-rng.randint(8, 30)} ({_Gpesc(cell[cut:])})] TJ"
                elif u < 0.45:
                    show = "<" + cell.encode("latin-1").hex().upper() + "> Tj"
                else:
                    show = f"({_Gpesc(cell)}) Tj"
                ops.append(f"BT /F1 7 Tf 1 0 0 1 {36 + 64 * k} {y} Tm {show} ET")
            y -= 10
        ops.append(f"BT /F1 6 Tf 1 0 0 1 36 24 Tm ({_Gpesc(footer)} - page {p + 1} of {n_pages}) Tj ET")
        rng.shuffle(ops)
        raw = ("\n".join(ops) + "\n").encode("latin-1")
        comp = zlib.compress(raw, 9)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_ids[p] + 1} 0 R >>".encode())
        objs.append(f"<< /Length {len(comp)} /Filter /FlateDecode >>\nstream\n".encode() + comp + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def _Gpaginate(rows: list[list[str]], first: int, rest: int, header: list[str], cont: str) -> list[list[list[str]]]:
    pages = [rows[:first]]
    tail = rows[first:]
    while tail:
        pages.append([[cont], header] + tail[:rest])
        tail = tail[rest:]
    return pages


def _Gsqlite(path: Path, ddl: list[str], inserts: list[tuple[str, list[tuple]]]) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    try:
        for d in ddl:
            con.execute(d)
        for sql, rows in inserts:
            con.executemany(sql, rows)
        con.commit()
    finally:
        con.close()
# --------------------------------------------------------------------------- generator: world
_GTEMPS = ["1.5", "2", "3", "4", "5", "6", "8", "10", "12", "15", "20", "25", "30", "40", "50", "60", "70", "80", "90", "100",
           "120", "140", "160", "180", "200", "225", "250", "275", "300", "320"]
_GANCHORS = {
    "CU_OFHC": [(2, 300), (4, 600), (10, 1500), (20, 2000), (30, 1500), (50, 700), (77, 500), (100, 450), (200, 410), (320, 398)],
    "CU_ETP": [(2, 120), (4, 240), (10, 600), (20, 800), (30, 700), (50, 500), (77, 420), (100, 410), (320, 388)],
    "AL6061": [(2, 1.8), (4, 3.6), (10, 9), (20, 18), (50, 45), (77, 70), (100, 90), (200, 140), (320, 162)],
    "SS304": [(2, 0.07), (4, 0.25), (10, 0.75), (20, 2.0), (50, 6), (77, 8), (100, 9.2), (200, 13), (320, 15.2)],
    "G10_CR": [(2, 0.02), (4, 0.058), (10, 0.1), (20, 0.15), (50, 0.22), (77, 0.28), (100, 0.32), (200, 0.5), (320, 0.62)],
    "TI6AL4V": [(2, 0.15), (4, 0.3), (10, 0.9), (20, 1.6), (50, 3), (77, 4), (100, 4.5), (200, 6), (320, 7.2)],
    "BRASS360": [(2, 1.0), (4, 2.2), (10, 7), (20, 15), (50, 35), (77, 50), (100, 60), (200, 90), (320, 112)],
    "PTFE": [(2, 0.03), (4, 0.05), (10, 0.1), (20, 0.15), (50, 0.2), (77, 0.22), (100, 0.24), (200, 0.25), (320, 0.26)],
    "PHBRONZE": [(2, 1.6), (4, 2.5), (10, 5), (20, 9), (50, 20), (77, 28), (100, 33), (320, 49)],
}
_GSMALLK = ("SS304", "G10_CR", "PTFE", "TI6AL4V")
_GMAT_ALIASES = {
    "CU_OFHC": ["C10100", "OFHC", "OFE-Cu", "Cu-OFHC"], "CU_ETP": ["C11000", "ETP-Cu", "Cu ETP"],
    "AL6061": ["Al-6061-T6", "AA6061", "6061-T6"], "SS304": ["304SS", "AISI 304", "SS-304L"], "G10_CR": ["G-10CR", "NEMA G10", "G10 CR"],
    "TI6AL4V": ["Ti-6-4", "Ti6Al4V", "Grade 5 Ti"], "BRASS360": ["CDA360", "C36000", "Free-cut brass"], "PTFE": ["Teflon", "PTFE-virgin"],
    "PHBRONZE": ["PH-BR", "C51000", "Phos bronze"],
}
_GAWG = {22: "0.3255", 24: "0.2047", 26: "0.1288", 28: "0.0810", 30: "0.0509", 32: "0.0320", 34: "0.0201", 36: "0.0127", 38: "0.0080",
         40: "0.0050"}
_GAWG_ROUGH = {22: "0.33", 24: "0.20", 26: "0.13", 28: "0.08", 30: "0.05", 32: "0.032", 34: "0.02", 36: "0.013", 38: "0.008", 40: "0.005"}
_GJ2 = {("BOLT_CU", "W"): "2150.0", ("BOLT_CU", "C"): "412.5", ("BOLT_AL", "W"): "1630.0", ("BOLT_AL", "C"): "268.0",
        ("BOLT_SS", "W"): "540.0", ("BOLT_SS", "C"): "61.5", ("CLAMP_SS", "W"): "880.0", ("CLAMP_SS", "C"): "97.25",
        ("EPOXY_G10", "W"): "1210.0", ("EPOXY_G10", "C"): "143.0", ("SOLDER_PB", "W"): "3900.0", ("SOLDER_PB", "C"): "702.0"}
_GJ1 = {k: _Gq(_Gfr(v) * Fraction(r), 1) for (k, v), r in zip(_GJ2.items(), ["1.08", "0.92", "1.11", "0.95", "1.2", "0.9", "1.1", "1.06",
                                                                                "0.94", "1.12", "1.05", "0.97"])}
_GP2 = {("SC-A", "ST50"): 2650000, ("SC-A", "ST4"): 61500, ("SC-B", "ST50"): 1980000, ("SC-B", "ST4"): 44250, ("SC-C", "ST50"): 3420000,
        ("SC-C", "ST4"): 78750, ("SC-D", "ST50"): 1540000, ("SC-D", "ST4"): 38500}
_GP1 = {k: v + (v // 9 if i % 2 else -(v // 11)) for i, (k, v) in enumerate(_GP2.items())}
_GS2 = {"h_increment_mW_per_K": "0.1", "indium_factor": "1.80", "low_torque_factor": "0.60", "lot_scale_materials": "CU_OFHC CU_ETP AL6061",
        "march_rounding": "EACH_ELEMENT", "spike_rule": "WINDOW_MEDIAN"}
_GS1 = {"h_increment_mW_per_K": "1", "indium_factor": "1.50", "low_torque_factor": "0.75", "lot_scale_materials": "ALL",
        "march_rounding": "FINAL_ONLY", "spike_rule": "WINDOW_MEAN"}
_GL1 = {"ST50": 62000, "ST4": 4500}
_GCAP = {("GM-K15", "ST50"): [("30", "3.10"), ("35", "4.05"), ("40", "4.92"), ("45", "5.70"), ("50", "6.38"), ("55", "6.97"), ("60", "7.49"),
                              ("65", "7.93"), ("70", "8.31"), ("75", "8.62"), ("80", "8.88")],
         ("GM-K15", "ST4"): [("3.0", "0.0420"), ("3.25", "0.0610"), ("3.5", "0.0805"), ("3.75", "0.0990"), ("4.0", "0.1170"),
                             ("4.25", "0.1335"), ("4.5", "0.1490"), ("4.75", "0.1630"), ("5.0", "0.1760"), ("5.5", "0.1985"), ("6.0", "0.2170")],
         ("PT-K41", "ST50"): [("30", "2.55"), ("35", "3.48"), ("40", "4.30"), ("45", "5.02"), ("50", "5.66"), ("55", "6.22"), ("60", "6.71"),
                              ("65", "7.13"), ("70", "7.49"), ("75", "7.80"), ("80", "8.05")],
         ("PT-K41", "ST4"): [("3.0", "0.0365"), ("3.25", "0.0548"), ("3.5", "0.0730"), ("3.75", "0.0902"), ("4.0", "0.1066"),
                             ("4.25", "0.1219"), ("4.5", "0.1361"), ("4.75", "0.1492"), ("5.0", "0.1612"), ("5.5", "0.1820"), ("6.0", "0.1995")]}
_GCOOLERS = {"CC-0417": "GM-K15", "CC-0522": "PT-K41"}
_GNODE_ALIASES = {"ST300": ["300K", "VVS", "shell", "ST-300", "vessel"], "ST50": ["SHIELD", "1ST", "ST-50", "50K stage"],
                  "ST4": ["PLATE4K", "2ND", "ST-4", "cold plate"]}


def _Gdefaults() -> dict:
    return {
        "campaign": "KTC-26B", "site": "Thermal Test Hall 3", "date1904": True,
        "cal": {"base": 120, "transitions": [(datetime(2026, 10, 25, 1, 0, tzinfo=_GUTC), 60)]},
        "start": date(2026, 9, 7), "n_runs": 25, "n_noise": 3,
        "sensors": {"ST300": 5, "ST50": 11, "ST4": 14},
        "labels": {"J": ("J-2", "J-1"), "P": ("P-2", "P-1"), "S": ("S-2", "S-1")},
        "sheets": {"k": "K_TABLES_R3", "k_old": "K_TABLES_R2", "k_draft": "K_TABLES_R4_DRAFT", "cal": "CAL_K26B", "cal_old": "CAL_K26A",
                   "cap": "CAPMAP_V2", "cap_old": "CAPMAP_V1"},
        "knobs": {"spike_mK": 40, "outlier_mK": 150, "min_readings": 12},
        "reserve": {"ST50": 15, "ST4": 20},
        "profile_revision": 7,
        "J2": dict(_GJ2), "J1": dict(_GJ1), "P2": dict(_GP2), "P1": dict(_GP1), "S2": dict(_GS2), "S1": dict(_GS1), "L1": dict(_GL1),
        "AWG": dict(_GAWG), "cap": {k: list(v) for k, v in _GCAP.items()},
        "intercepts": "normal", "amend_chains": 18, "relabels": 4, "remaps": 4, "stage_moves": 2, "dst_run": True,
        "extra_amend": None, "extra_addendum": None,
        "gap_start": False, "oom_run": False, "eff_tie": False, "floor_ix": False, "within_shard_ties": 0, "overlay_base": None,
        "edge_screens": False,
    }


def _Ginterp_loglog(anchors: list[tuple[float, float]], t: float) -> float:
    if t <= anchors[0][0]:
        (t0, k0), (t1, k1) = anchors[0], anchors[1]
    elif t >= anchors[-1][0]:
        (t0, k0), (t1, k1) = anchors[-2], anchors[-1]
    else:
        for (t0, k0), (t1, k1) in zip(anchors, anchors[1:]):
            if t0 <= t <= t1:
                break
    a = (math.log(k1) - math.log(k0)) / (math.log(t1) - math.log(t0))
    return math.exp(math.log(k0) + a * (math.log(t) - math.log(t0)))


def _Gk_tables(rng: random.Random, jitter: float) -> dict[str, list[tuple[str, str]]]:
    out = {}
    for mat in sorted(_GANCHORS):
        pts = []
        for t in _GTEMPS:
            k = _Ginterp_loglog(_GANCHORS[mat], float(t)) * (1 + rng.uniform(-jitter, jitter))
            pts.append((t, _Gsig(Fraction(k).limit_denominator(10 ** 9), 4)))
        out[mat] = pts
    return out


def _Gprt_r(t: float, s: float) -> float:
    tc = t - 273.15
    base = 100 * (1 + 3.9083e-3 * tc - 5.775e-7 * tc * tc) if t > 70 else 0
    low = 100 * (1 + 3.9083e-3 * (70 - 273.15) - 5.775e-7 * (70 - 273.15) ** 2)
    if t <= 70:
        base = (low - 0.4) * (t / 70) ** 2.2 + 0.4
    return base * s


def _Gntc_r(t: float, s: float) -> float:
    return 38.0 * s * math.exp(9.2 / math.sqrt(t))


def _Gdiode_v(t: float, s: float) -> float:
    return (1.712 - 0.00242 * t + 0.06 * math.exp(-t / 14.0)) * s


def _Gcal_points(fam: str, rng: random.Random, s: float) -> list[tuple[str, str]]:
    """(raw, T_K) calibration points for one sensor, sorted by T."""
    if fam == "PRT":
        temps = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100, 125, 150, 175, 200, 225, 250, 275, 290, 300, 315, 330]
    elif fam == "NTC":
        temps = [1.4, 1.6, 1.8, 2.0, 2.4, 2.8, 3.2, 3.5, 3.8, 4.0, 4.2, 4.5, 4.8, 5.2, 6, 7, 8, 10, 12, 15, 20, 30, 45, 60, 80]
    else:
        temps = [1.4, 2, 3, 3.5, 4, 4.5, 5, 6, 8, 10, 15, 20, 30, 40, 45, 50, 55, 60, 65, 70, 80, 100, 150, 200, 250, 300, 330]
    pts = []
    for t in temps:
        tk = t + rng.uniform(-0.004, 0.004) if t > 2 else t
        tk_s = _Gq(Fraction(tk).limit_denominator(10 ** 7), 3)
        tv = float(tk_s)
        if fam == "PRT":
            raw = _Gq(Fraction(_Gprt_r(tv, s)).limit_denominator(10 ** 9), 4)
        elif fam == "NTC":
            raw = _Gq(Fraction(_Gntc_r(tv, s)).limit_denominator(10 ** 9), 4)
        else:
            raw = _Gq(Fraction(_Gdiode_v(tv, s)).limit_denominator(10 ** 12), 6)
        pts.append((raw, tk_s))
    return pts


def _Gcal_space(fam: str, raw: Fraction) -> Fraction:
    return 1 / raw if fam == "NTC" else raw


def _Graw_for(fam: str, pts: list[tuple[str, str]], t_mk: int) -> Fraction | None:
    """Exact raw value whose interpolation (in the family's space) gives t_mk."""
    T = Fraction(t_mk, 1000)
    for (r0, t0), (r1, t1) in zip(pts, pts[1:]):
        T0, T1 = _Gfr(t0), _Gfr(t1)
        if T0 <= T <= T1:
            x0, x1 = _Gcal_space(fam, _Gfr(r0)), _Gcal_space(fam, _Gfr(r1))
            x = x0 + (x1 - x0) * (T - T0) / (T1 - T0)
            return 1 / x if fam == "NTC" else x
    return None


def _Gworld(rng: random.Random, cfg: dict) -> dict:  # noqa: C901
    W: dict[str, Any] = {"cfg": cfg}
    cal = cfg["cal"]
    W["k_tables"] = _Gk_tables(rng, 0.03)
    W["k_old"] = {m: [(t, _Gsig(_Gfr(k) * Fraction(rng.choice([96, 97, 103, 104, 105]), 100), 4)) for t, k in pts]
                  for m, pts in W["k_tables"].items()}
    W["k_draft"] = {m: [(t, _Gsig(_Gfr(k) * Fraction(rng.choice([98, 101, 102]), 100), 4)) for t, k in pts] for m, pts in W["k_tables"].items()}
    # ---- runs
    runs = []
    day = cfg["start"]
    n = cfg["n_runs"]
    dst_idx = None
    for i in range(1, n + 1):
        day = day + timedelta(days=rng.choice([2, 3, 3, 4]))
        runs.append({"id": f"KTC-R{i:02d}", "num": i, "day": day})
    if cfg["dst_run"]:
        tr = cfg["cal"]["transitions"][0][0]
        local_day = _Gutc_to_wall(tr, cal).date()
        dst_idx = min(range(n), key=lambda k: abs((runs[k]["day"] - local_day).days))
        runs[dst_idx]["day"] = local_day
        for k in range(dst_idx + 1, n):
            if runs[k]["day"] <= runs[k - 1]["day"]:
                runs[k]["day"] = runs[k - 1]["day"] + timedelta(days=2)
    for i, r in enumerate(runs):
        if i == dst_idx:
            tr = cfg["cal"]["transitions"][0][0]
            pre = cal["base"]
            w0 = (tr + timedelta(minutes=pre) - timedelta(minutes=50))
            start_u = (w0 - timedelta(minutes=pre)).replace(tzinfo=_GUTC)
            start_u = start_u.replace(minute=start_u.minute - start_u.minute % 2, second=0)
            if cfg.get("gap_start"):
                # the log carries a wall time that the clock skipped; H4.1 maps it with the pre-jump offset
                start_u = (tr + timedelta(minutes=20)).replace(tzinfo=_GUTC)
                W.setdefault("gap_wall", {})[r["id"]] = (start_u + timedelta(minutes=pre)).strftime("%Y-%m-%d %H:%M")
            dur = 150
        else:
            hh = rng.randint(8, 19)
            mm = rng.choice([0, 6, 10, 14, 20, 24, 30, 36, 40, 46, 50])
            w = datetime(r["day"].year, r["day"].month, r["day"].day, hh, mm)
            while _Gin_gap(w, cal) or _Gambiguous(w, cal):
                w += timedelta(hours=3)
            start_u = _Gwall_to_utc(w, cal)
            dur = rng.choice([60, 64, 70, 76, 80, 90])
        r["start"] = start_u
        r["end"] = start_u + timedelta(minutes=dur)
        r["shield"] = rng.choice(["SC-A", "SC-B", "SC-C", "SC-D"])
        r["cooler"] = rng.choice(sorted(_GCOOLERS))
        r["T"] = {"ST300": rng.randint(293000, 297600), "ST50": rng.randint(44000, 63200), "ST4": rng.randint(3740, 4580)}
        r["aborted"] = False
    W["dst_idx"] = dst_idx
    ab = rng.choice([k for k in range(3, n - 2) if k != dst_idx])
    runs[ab]["aborted"] = True
    W["abort_withdrawn"] = rng.choice([k for k in range(2, n - 1) if k not in (ab, dst_idx)])
    if cfg.get("oom_run"):
        k = next(i for i in range(1, n) if i not in (ab, dst_idx, W["abort_withdrawn"]))
        runs[k]["T"]["ST4"] = 6240
        W["oom_run"] = runs[k]["id"]
    noise = []
    for j in range(cfg["n_noise"]):
        d = cfg["start"] + timedelta(days=5 + 9 * j)
        w = datetime(d.year, d.month, d.day, 6, 30)
        su = _Gwall_to_utc(w, cal)
        noise.append({"id": f"KTC-R{90 + j:02d}", "num": 90 + j, "day": d, "start": su, "end": su + timedelta(minutes=60), "shield": "SC-B",
                      "cooler": "CC-0417", "T": {"ST300": 295000, "ST50": 52000, "ST4": 4100}, "aborted": False, "noise": True})
    W["runs"] = runs
    W["noise_runs"] = noise
    # ---- sensors
    vendors = ["LS", "QX", "RV", "TM", "HK"]
    used: set[str] = set()

    def new_serial() -> str:
        while True:
            s = f"{rng.choice(vendors)}-{rng.randint(1000, 9899)}"
            if s not in used:
                used.add(s)
                return s

    sensors = []
    fams = {"ST300": ["PRT"] * cfg["sensors"]["ST300"],
            "ST50": ["PRT"] * (cfg["sensors"]["ST50"] - cfg["sensors"]["ST50"] // 2) + ["DIODE"] * (cfg["sensors"]["ST50"] // 2),
            "ST4": ["NTC"] * (cfg["sensors"]["ST4"] - cfg["sensors"]["ST4"] // 3) + ["DIODE"] * (cfg["sensors"]["ST4"] // 3)}
    for st in ("ST300", "ST50", "ST4"):
        for k, fam in enumerate(fams[st]):
            s = {"serial": new_serial(), "family": fam, "stage0": st, "bias": rng.randint(-25, 25), "scale": 1 + rng.uniform(-0.004, 0.004),
                 "policy": "SERIAL", "has_cal": True}
            sensors.append(s)
    st300 = [s for s in sensors if s["stage0"] == "ST300"]
    for s in st300[:2]:
        s["policy"] = "GENERIC_OK"
        s["has_cal"] = False
        s["scale"] = 1.0
    nocal = [s for s in sensors if s["stage0"] == "ST4" and s["family"] == "NTC"][-1]
    nocal["has_cal"] = False
    W["nocal"] = nocal["serial"]
    # outlier sensor: large bias in a subset of runs
    W["outlier"] = rng.choice([s["serial"] for s in sensors if s["stage0"] == "ST50"])
    W["outlier_runs"] = sorted(rng.sample([r["id"] for r in runs], 6))
    # calibrations (final serial -> versions)
    cals: dict[str, list[dict]] = {}
    recal = rng.sample([s for s in sensors if s["has_cal"]], 5)
    mid = runs[n // 2]["day"]
    for s in sensors:
        if not s["has_cal"]:
            continue
        vers = [{"ver": "A", "valid_from": cfg["start"] - timedelta(days=rng.randint(40, 120)), "pts": _Gcal_points(s["family"], rng, s["scale"])}]
        if s in recal:
            vers.append({"ver": "B", "valid_from": mid + timedelta(days=rng.randint(-6, 6)),
                         "pts": _Gcal_points(s["family"], rng, s["scale"] * (1 + rng.uniform(-0.002, 0.002)))})
        s["kohm"] = s["family"] == "NTC" and rng.random() < 0.4
        cals[s["serial"]] = vers
    W["cals"] = cals
    W["generic"] = {f: _Gcal_points(f, random.Random(77 + i), 1.0) for i, f in enumerate(("PRT", "NTC", "DIODE"))}
    # relabels (old -> new); the final label is the sensor's serial
    relabels = []
    pool = [s for s in sensors if s["policy"] == "SERIAL"]
    for j, s in enumerate(rng.sample(pool, cfg["relabels"])):
        chain = [new_serial() for _ in range(2 if j < 2 else 1)] + [s["serial"]]
        days = sorted(rng.sample(range(2, (runs[-1]["day"] - runs[0]["day"]).days - 2), len(chain) - 1))
        for a, b, dd in zip(chain, chain[1:], days):
            relabels.append({"old": a, "new": b, "at": datetime.combine(runs[0]["day"] + timedelta(days=dd), datetime.min.time(), _GUTC)})
        s["chain"] = chain
    W["relabels"] = relabels
    for s in sensors:
        s.setdefault("chain", [s["serial"]])
    # label in use at an instant
    def label_at(s: dict, u: datetime) -> str:
        lab = s["chain"][0]
        for rl in relabels:
            if rl["old"] == lab and u >= rl["at"]:
                lab = rl["new"]
        while True:
            nxt = [rl for rl in relabels if rl["old"] == lab and u >= rl["at"]]
            if not nxt:
                return lab
            lab = nxt[0]["new"]
    W["label_at"] = label_at
    # stage moves: sensor assignment history
    for s in sensors:
        s["hist"] = [(datetime.combine(cfg["start"] - timedelta(days=30), datetime.min.time(), _GUTC), s["stage0"])]
    movers = rng.sample([s for s in sensors if s["family"] == "DIODE"], cfg["stage_moves"])
    for s in movers:
        to = "ST4" if s["stage0"] == "ST50" else "ST50"
        k = rng.randint(n // 3, 2 * n // 3)
        at = runs[k]["start"] - timedelta(hours=rng.randint(10, 30))
        s["hist"].append((at, to))
    W["movers"] = [s["serial"] for s in movers]
    # channels: D1/D2 x 01..24
    chans = [f"D{u}C{c:02d}" for u in (1, 2) for c in range(1, 25)]
    rng.shuffle(chans)
    camp0 = datetime.combine(cfg["start"] - timedelta(days=20), datetime.min.time(), _GUTC)
    for s, ch in zip(sensors, chans):
        s["chan_hist"] = [(camp0, ch)]
    spare_ch = chans[len(sensors):]
    for s in rng.sample(sensors, cfg["remaps"]):
        at = runs[rng.randint(n // 4, 3 * n // 4)]["start"] - timedelta(hours=rng.randint(3, 40))
        s["chan_hist"].append((at, spare_ch.pop()))
    W["sensors"] = sensors
    W["spare_ch"] = spare_ch
    # ---- links
    links: dict[str, dict] = {}

    def seg(mat: str, L: str, area: str, lot: str = "") -> dict:
        return {"mat": mat, "len": L, "area": area, "lot": lot}

    def joint(pos: int, cls: str, bolts: int, torque: str = "NOM", indium: bool = False) -> dict:
        return {"pos": pos, "class": cls, "bolts": bolts, "torque": torque, "indium": indium}

    def mk(lid: str, kind: str, segs: list, joints: list) -> None:
        links[lid] = {"id": lid, "kind": kind, "revs": [{"rev": 1, "eff": cfg["start"] - timedelta(days=60), "status": "ACTIVE", "segs": segs,
                                                         "joints": joints}]}

    lot_no = [100]

    def lot(mat: str) -> str:
        lot_no[0] += rng.randint(1, 7)
        return f"LOT-{mat[:2]}{lot_no[0]:04d}"

    for i in range(4):
        mk(f"TL-{1 + i:03d}", "STANDOFF_W", [seg("G10_CR", _Gq(Fraction(rng.randint(380, 520), 10), 1), f"A:{_Gq(Fraction(rng.randint(560, 900), 10), 2)}mm2")],
           [joint(0, "BOLT_SS", 2), joint(1, "BOLT_AL", 2, rng.choice(["NOM", "LOW"]))])
        mk(f"TL-{5 + i:03d}", "STANDOFF_W", [seg("TI6AL4V", _Gq(Fraction(rng.randint(450, 600), 10), 1), f"R:{rng.randint(8, 12)}.0x{_Gq(Fraction(rng.randint(15, 30), 10), 1)}mm")],
           [joint(0, "BOLT_SS", 3), joint(1, "BOLT_AL", 3)])
        mk(f"TL-{9 + i:03d}", "STANDOFF_W", [seg("G10_CR", _Gq(Fraction(rng.randint(300, 420), 10), 1), f"A:{_Gq(Fraction(rng.randint(500, 800), 10), 2)}mm2"),
                                               seg("SS304", _Gq(Fraction(rng.randint(80, 140), 10), 1), f"A:{_Gq(Fraction(rng.randint(150, 260), 1000), 4)}cm2")],
           [joint(0, "BOLT_SS", 2), joint(1, "EPOXY_G10", 1), joint(2, "BOLT_AL", 2, "NOM", rng.random() < 0.5)])
        mk(f"TL-{21 + i:03d}", "STANDOFF_C", [seg("G10_CR", _Gq(Fraction(rng.randint(400, 650), 10), 1), f"A:{_Gq(Fraction(rng.randint(250, 480), 10), 2)}mm2")],
           [joint(0, "BOLT_AL", 2), joint(1, "BOLT_CU", 2, rng.choice(["NOM", "LOW"]), True)])
        mk(f"TL-{25 + i:03d}", "STANDOFF_C", [seg("SS304", _Gq(Fraction(rng.randint(600, 900), 10), 1), f"R:{rng.randint(4, 7)}.0x{_Gq(Fraction(rng.randint(5, 12), 10), 1)}mm")],
           [joint(0, "BOLT_AL", 2), joint(1, "BOLT_CU", 2)])
        mk(f"TL-{29 + i:03d}", "STANDOFF_C", [seg("TI6AL4V", _Gq(Fraction(rng.randint(200, 300), 10), 1), f"A:{_Gq(Fraction(rng.randint(120, 200), 10), 2)}mm2"),
                                                seg("G10_CR", _Gq(Fraction(rng.randint(250, 400), 10), 1), f"A:{_Gq(Fraction(rng.randint(200, 350), 10), 2)}mm2")],
           [joint(0, "BOLT_AL", 2), joint(1, "EPOXY_G10", 1), joint(2, "BOLT_CU", 2, "LOW", rng.random() < 0.5)])
        mk(f"TL-{41 + i:03d}", "HARNESS_W", [seg("PHBRONZE", str(rng.randint(340, 520)), f"W:{rng.choice([24, 32])}x32AWG")],
           [joint(0, "CLAMP_SS", 1), joint(1, "CLAMP_SS", 1)])
        mk(f"TL-{51 + i:03d}", "HARNESS_C", [seg("PHBRONZE", str(rng.randint(300, 450)), f"W:{rng.choice([24, 32])}x36AWG")],
           [joint(0, "CLAMP_SS", 1), joint(1, "CLAMP_SS", 1)])
        mk(f"TL-{61 + i:03d}", "HARNESS_IN_W", [seg("PHBRONZE", str(rng.randint(220, 320)), f"W:{rng.choice([24, 32, 48])}x32AWG")],
           [joint(0, "CLAMP_SS", 1)])
        mk(f"TL-{65 + i:03d}", "HARNESS_OUT_W", [seg("PHBRONZE", str(rng.randint(150, 260)), f"W:{rng.choice([24, 32, 48])}x32AWG")],
           [joint(1, "CLAMP_SS", 1)])
        mk(f"TL-{69 + i:03d}", "STRAP_W", [seg(rng.choice(["BRASS360", "CU_ETP"]), _Gq(Fraction(rng.randint(900, 1600), 10), 1),
                                                f"R:{rng.randint(4, 8)}.0x{_Gq(Fraction(rng.randint(5, 15), 10), 1)}mm", lot("BR"))],
           [joint(0, "BOLT_CU", 2), joint(1, "BOLT_CU", 2, rng.choice(["NOM", "LOW"]), rng.random() < 0.5)])
        mk(f"TL-{81 + i:03d}", "HARNESS_IN_C", [seg("PHBRONZE", str(rng.randint(200, 300)), f"W:{rng.choice([24, 32])}x36AWG")],
           [joint(0, "CLAMP_SS", 1)])
        mk(f"TL-{85 + i:03d}", "HARNESS_OUT_C", [seg("PHBRONZE", str(rng.randint(150, 250)), f"W:{rng.choice([24, 32])}x36AWG")],
           [joint(1, "CLAMP_SS", 1)])
        mk(f"TL-{89 + i:03d}", "STRAP_C", [seg(rng.choice(["AL6061", "CU_ETP", "SS304"]), _Gq(Fraction(rng.randint(600, 1400), 10), 1),
                                                f"R:{rng.randint(2, 5)}.0x{_Gq(Fraction(rng.randint(5, 10), 10), 1)}mm", "")],
           [joint(0, "BOLT_CU", 1), joint(1, "BOLT_CU", 1, "NOM", True)])
    for lid, L in links.items():
        for sg in L["revs"][0]["segs"]:
            if sg["mat"] in ("CU_ETP", "AL6061", "CU_OFHC", "BRASS360") and not sg["lot"]:
                sg["lot"] = lot(sg["mat"])
            elif sg["mat"] in ("G10_CR", "TI6AL4V") and rng.random() < 0.3:
                sg["lot"] = lot(sg["mat"])
    # revision 2 for a third of the links, revision 3 VOID for one
    for lid in sorted(rng.sample(sorted(links), len(links) // 3)):
        L = links[lid]
        r1 = L["revs"][0]
        segs = [dict(sg) for sg in r1["segs"]]
        k = rng.randrange(len(segs))
        if segs[k]["mat"] == "PHBRONZE":
            segs[k]["len"] = str(int(segs[k]["len"]) + rng.choice([-30, -20, 15, 25]))
        else:
            segs[k]["len"] = _Gq(_Gfr(segs[k]["len"]) + Fraction(rng.choice([-25, -15, 12, 30]), 10), 1)
        L["revs"].append({"rev": 2, "eff": runs[rng.randint(4, n - 4)]["day"], "status": "ACTIVE", "segs": segs,
                          "joints": [dict(j) for j in r1["joints"]]})
    W["links"] = links
    # ---- installs per run: W standoff set, C standoff set, harness or intercepts
    installs: dict[str, list[dict]] = {}
    intercepts: dict[str, list[dict]] = {}
    heavy = cfg["intercepts"] == "heavy"
    for i, r in enumerate(runs):
        rid = r["id"]
        ws = [1, 5, 9][i % 3]
        cs = [21, 25, 29][(i // 2) % 3]
        rows = [{"link": f"TL-{ws + k:03d}", "hot": "ST300", "cold": "ST50"} for k in range(4)]
        rows += [{"link": f"TL-{cs + k:03d}", "hot": "ST50", "cold": "ST4"} for k in range(4)]
        ix: list[dict] = []
        mode = rng.random()
        wsel = (heavy and mode < 0.85) or (not heavy and mode < 0.45)
        csel = (heavy and mode > 0.15) or (not heavy and 0.3 < mode < 0.75)
        h = i % 4
        if wsel:
            x = {"id": f"IX-W-{r['num']:02d}", "band": "W", "hot": "ST300", "cold": "ST50", "nominal": rng.choice(["150.000", "140.000", "160.000"])}
            ix.append(x)
            rows += [{"link": f"TL-{61 + h:03d}", "hot": "ST300", "cold": x["id"]}, {"link": f"TL-{65 + h:03d}", "hot": x["id"], "cold": "ST50"},
                     {"link": f"TL-{69 + h:03d}", "hot": x["id"], "cold": "ST50"}]
        else:
            rows.append({"link": f"TL-{41 + h:03d}", "hot": "ST300", "cold": "ST50"})
        if csel:
            x = {"id": f"IX-C-{r['num']:02d}", "band": "C", "hot": "ST50", "cold": "ST4", "nominal": rng.choice(["12.000", "10.000", "15.000"])}
            ix.append(x)
            rows += [{"link": f"TL-{81 + h:03d}", "hot": "ST50", "cold": x["id"]}, {"link": f"TL-{85 + h:03d}", "hot": x["id"], "cold": "ST4"},
                     {"link": f"TL-{89 + h:03d}", "hot": x["id"], "cold": "ST4"}]
        else:
            rows.append({"link": f"TL-{51 + h:03d}", "hot": "ST50", "cold": "ST4"})
        installs[rid] = rows
        intercepts[rid] = ix
    W["installs"] = installs
    W["intercepts"] = intercepts
    if cfg.get("eff_tie"):
        # a third revision with the same effective_from as the second: H14.2 takes the higher rev
        used_late = set()
        for r in runs:
            if r["aborted"]:
                continue
            for row in installs[r["id"]]:
                revs = links[row["link"]]["revs"]
                if len(revs) == 2 and r["day"] >= revs[1]["eff"]:
                    used_late.add(row["link"])
        tie = sorted(used_late)[0]
        r2 = links[tie]["revs"][1]
        segs3 = [dict(sg) for sg in r2["segs"]]
        if segs3[0]["mat"] == "PHBRONZE":
            segs3[0]["len"] = str(int(segs3[0]["len"]) + 45)
        else:
            segs3[0]["len"] = _Gq(_Gfr(segs3[0]["len"]) + Fraction(75, 10), 1)
        links[tie]["revs"].append({"rev": 3, "eff": r2["eff"], "status": "ACTIVE", "segs": segs3, "joints": [dict(j) for j in r2["joints"]]})
        W["eff_tie"] = tie
    if cfg.get("floor_ix"):
        # a copper strap from a warm intercept straight to the 4 K plate: the intercept balance is negative at T_lo
        links["TL-099"] = {"id": "TL-099", "kind": "STRAP_WC", "revs": [{"rev": 1, "eff": cfg["start"] - timedelta(days=60), "status": "ACTIVE",
                                                                         "segs": [seg("CU_ETP", "150.0", "R:10.0x3.0mm", "")],
                                                                         "joints": [joint(0, "BOLT_CU", 2), joint(1, "BOLT_CU", 2)]}]}
        for r in runs:
            xs = [x for x in intercepts[r["id"]] if x["band"] == "W"]
            if xs and not r["aborted"]:
                installs[r["id"]].append({"link": "TL-099", "hot": xs[0]["id"], "cold": "ST4"})
                W["floor_ix"] = (r["id"], xs[0]["id"])
                break
    # scrapped link: a VOID revision effective before one late run that still lists it
    late = runs[-3]
    victim = installs[late["id"]][0]["link"]
    links[victim]["revs"].append({"rev": max(rv["rev"] for rv in links[victim]["revs"]) + 1, "eff": late["day"] - timedelta(days=1),
                                  "status": "VOID", "segs": [], "joints": []})
    W["scrapped"] = (victim, late["id"])
    # renumbered links: old id -> new id (chain), install rows before the date use the old token
    ren = []
    for lid in sorted(rng.sample(sorted(links), 5)):
        new = f"TL-{int(lid[3:]) + 100:03d}"
        ren.append({"old": lid, "new": new, "at": runs[rng.randint(5, n - 5)]["day"]})
    a, b = ren[0]["new"], f"TL-{int(ren[0]['new'][3:]) + 300:03d}"
    ren.append({"old": a, "new": b, "at": ren[0]["at"] + timedelta(days=6)})
    W["renames"] = ren
    final = {}
    for lid in list(links):
        cur = lid
        while True:
            nx = [x for x in ren if x["old"] == cur]
            if not nx:
                break
            cur = nx[0]["new"]
        final[lid] = cur
    W["final_id"] = final
    # ---- harness bundles: per run, bundle -> node, dissipation
    bundles = []
    bno = [300]
    for r in runs + noise:
        nodes = ["ST50", "ST4"] + [x["id"] for x in intercepts.get(r["id"], [])]
        for _ in range(rng.randint(7, 10)):
            bno[0] += 1
            node = rng.choice(nodes)
            d_uw = rng.randint(800, 9000) if node.startswith("IX-W") or node == "ST50" else rng.randint(20, 900)
            hint = rng.choice(nodes + ["ST50", "ST4"])
            bundles.append({"id": f"HB-{bno[0]}", "run": r["id"], "node": node, "hint": hint, "uw": d_uw})
    W["bundles"] = bundles
    # ---- lots
    lots = []
    for lid, L in links.items():
        for rv in L["revs"]:
            for sg in rv["segs"]:
                if sg["lot"]:
                    lots.append(sg["lot"])
    W["lot_scale"] = {}
    for lt in sorted(set(lots)):
        W["lot_scale"][lt] = (_Gq(Fraction(rng.randint(880, 1090), 1000), 3), rng.choice(["CERTIFIED", "CERTIFIED", "CERTIFIED", "PROVISIONAL", "WITHDRAWN"]))
    # ---- rulings
    rulings = []
    rid_no = [100]

    def rul(run: str, target: str, action: str, value: str, status: str) -> dict:
        rid_no[0] += rng.randint(1, 4)
        d = {"id": f"R-{rid_no[0]:04d}", "run": run, "target": target, "action": action, "value": value, "status": status}
        rulings.append(d)
        return d

    in_scope = [r["id"] for r in runs if not r["aborted"]]
    serial_sensors = [s["serial"] for s in sensors]
    for _ in range(14):
        rul(rng.choice(in_scope), rng.choice(serial_sensors), "EXCLUDE_SENSOR", "", "IN FORCE")
    for _ in range(12):
        rul(rng.choice(in_scope), rng.choice(serial_sensors), "OFFSET_SENSOR", str(rng.choice([-18, -12, -7, 6, 9, 15, 22])), "IN FORCE")
    for _ in range(3):
        x = rng.choice(in_scope)
        rul(x, rng.choice(installs[x])["link"], "EXCLUDE_LINK", "", "IN FORCE")
    for _ in range(10):
        act = rng.choice(["EXCLUDE_SENSOR", "OFFSET_SENSOR"])
        rul(rng.choice(in_scope), rng.choice(serial_sensors), act, str(rng.choice([-20, 14])) if act == "OFFSET_SENSOR" else "", "RESCINDED")
    while len(rulings) < 226:
        x = rng.choice(["KTC-26A/" + str(rng.randint(1, 30)), "KTC-R9" + str(rng.randint(0, 2)), "KTC-25C/" + str(rng.randint(1, 40))])
        act = rng.choice(["EXCLUDE_SENSOR", "OFFSET_SENSOR", "EXCLUDE_LINK"])
        tgt = rng.choice(sorted(links)) if act == "EXCLUDE_LINK" else rng.choice(serial_sensors + ["LS-0001", "QX-0002"])
        rul(x, tgt, act, str(rng.choice([-10, 5, 30])) if act == "OFFSET_SENSOR" else "", rng.choice(["IN FORCE", "RESCINDED"]))
    W["rulings"] = rulings
    # addendum: RESCIND/REINSTATE with ISSUED/DRAFT
    add = []
    seq = 10
    live = [x for x in rulings if x["run"] in in_scope]
    for x in rng.sample(live, 9):
        seq += rng.randint(1, 5)
        if x["status"] == "IN FORCE":
            add.append({"seq": seq, "ref": x["id"], "action": "RESCIND", "status": "ISSUED"})
            if rng.random() < 0.4:
                seq += rng.randint(1, 5)
                add.append({"seq": seq, "ref": x["id"], "action": "REINSTATE", "status": "ISSUED"})
        else:
            add.append({"seq": seq, "ref": x["id"], "action": "REINSTATE", "status": "ISSUED"})
    for x in rng.sample(live, 6):
        seq += rng.randint(1, 5)
        add.append({"seq": seq, "ref": x["id"], "action": rng.choice(["RESCIND", "REINSTATE"]), "status": "DRAFT"})
    while len(add) < 210:
        seq += rng.randint(1, 5)
        x = rng.choice(rulings)
        add.append({"seq": seq, "ref": x["id"] if x["run"] not in in_scope else "R-9" + str(rng.randint(100, 999)),
                    "action": rng.choice(["RESCIND", "REINSTATE"]), "status": rng.choice(["ISSUED", "DRAFT"])})
    rng.shuffle(add)
    W["addendum"] = add
    # ---- service log derates
    svc = []
    d0 = cfg["start"] - timedelta(days=420)
    for k in range(230):
        d = d0 + timedelta(days=2 * k + rng.randint(0, 1))
        c = rng.choice(sorted(_GCOOLERS))
        svc.append({"date": d, "cooler": c, "action": rng.choice(["INSPECT", "HELIUM_TOPUP", "NOTE", "ADSORBER_CHECK", "INSPECT"]), "value": ""})
    for c in sorted(_GCOOLERS):
        svc.append({"date": cfg["start"] - timedelta(days=200), "cooler": c, "action": "DERATE", "value": "4"})
        svc.append({"date": cfg["start"] - timedelta(days=90), "cooler": c, "action": "RESTORE", "value": ""})
    c = rng.choice(sorted(_GCOOLERS))
    svc.append({"date": runs[n // 3]["day"] - timedelta(days=1), "cooler": c, "action": "DERATE", "value": rng.choice(["6", "7.5", "9"])})
    svc.append({"date": runs[2 * n // 3]["day"], "cooler": c, "action": "RESTORE", "value": ""})
    c2 = [x for x in sorted(_GCOOLERS) if x != c][0]
    svc.append({"date": runs[3 * n // 4]["day"] - timedelta(days=2), "cooler": c2, "action": "DERATE", "value": rng.choice(["3", "5.5"])})
    svc.sort(key=lambda e: (e["date"], e["cooler"], e["action"]))
    W["service"] = svc
    # ---- profile per-run knobs and overlays
    W["overlay"] = {}
    for r in runs:
        o = {}
        if rng.random() < 0.35:
            o["spike_mK"] = rng.choice([30, 55, 60])
        if rng.random() < 0.25:
            o["outlier_mK"] = rng.choice([90, 200])
        if rng.random() < 0.2:
            o["min_readings"] = rng.choice([10, 15])
        if rng.random() < 0.3:
            o["reserve_pct_ST4"] = rng.choice([10, 25])
        W["overlay"][r["id"]] = o
    W["stale_overlay"] = {r["id"]: {"spike_mK": rng.choice([25, 45, 70]), "min_readings": rng.choice([8, 20]), "outlier_mK": rng.choice([60, 300])}
                          for r in runs}
    return W
# --------------------------------------------------------------------------- generator: readings
_GSHARDS = [("rd_7kq2.csv", "L01"), ("rd_m4x9.tsv", "L02"), ("rd_p0w3.psv", "L03"), ("rd_h8c1.jsonl", "L04"), ("rd_z2v6.ndjson", "L05"),
            ("rd_b5n7.xml", "L06"), ("rd_q9e4.sqlite", "L07"), ("rd_t3y8.db", "L08"), ("rd_f6u1.yaml", "L09"), ("rd_c1j5.yml", "L10"),
            ("rd_w8a2.json", "L11"), ("rd_k4d0.txt", "L12"), ("rd_s7g3.md", "L13"), ("rd_n2r6.csv", "L14"), ("rd_e5x1.tsv", "L15"),
            ("rd_g7v4.jsonl", "L16")]
_GCHANNEL_LAYOUTS = ("L03", "L08", "L15")


def _Gstage_at(s: dict, u: datetime) -> str:
    st = s["hist"][0][1]
    for at, x in s["hist"]:
        if u >= at:
            st = x
    return st


def _Gchan_at(s: dict, u: datetime) -> str:
    ch = s["chan_hist"][0][1]
    for at, x in s["chan_hist"]:
        if u >= at:
            ch = x
    return ch


def _Gcal_for(W: dict, s: dict, u: datetime) -> tuple[str, list] | None:
    if s["has_cal"]:
        vers = [v for v in W["cals"][s["serial"]] if v["valid_from"] <= u.date()]
        if not vers:
            return None
        v = max(vers, key=lambda v: v["valid_from"])
        return s["family"], v["pts"]
    return s["family"], W["generic"][s["family"]]


def _Gmaintenance(rng: random.Random, W: dict) -> list[dict]:
    blocks = []
    runs = [r for r in W["runs"] if not r["aborted"]]
    for r in rng.sample(runs, 7):
        span = (r["end"] - r["start"]).total_seconds() / 60
        a = r["start"] + timedelta(minutes=2 * rng.randint(3, int(span / 2) - 8))
        b = a + timedelta(minutes=rng.choice([6, 8, 10, 12]))
        blocks.append({"start": a, "end": b, "scope": rng.choice(["ALL", "ST50", "ST4", "ST300"]), "note": "planned DAQ maintenance"})
    for k in range(9):
        a = datetime.combine(W["cfg"]["start"] + timedelta(days=4 * k + 1), datetime.min.time(), _GUTC) + timedelta(hours=3)
        blocks.append({"start": a, "end": a + timedelta(minutes=40), "scope": "ALL", "note": "overnight DAQ reboot"})
    blocks.sort(key=lambda b: b["start"])
    return blocks


def _Gedge_setup(W: dict) -> None:
    """Pick one quiet run whose 4 K sensors read without noise, so the spike and outlier limits are met exactly."""
    cfg = W["cfg"]
    if not cfg.get("edge_screens"):
        return
    for k, r in enumerate(W["runs"]):
        if r["aborted"] or k == W["dst_idx"] or k == W["abort_withdrawn"] or r["id"] in W["outlier_runs"] or r["id"] == W.get("oom_run"):
            continue
        ruled = {x["target"] for x in W["rulings"] if x["run"] == r["id"]}
        if any(b["start"] < r["end"] + timedelta(minutes=10) and b["end"] > r["start"] - timedelta(minutes=10) for b in W["maint"]):
            continue
        stale = cfg.get("overlay_base") not in (None, cfg["profile_revision"])
        ov = {} if stale else W["overlay"][r["id"]]
        spike = ov.get("spike_mK", cfg["knobs"]["spike_mK"])
        outlier = ov.get("outlier_mK", cfg["knobs"]["outlier_mK"])
        ntc = sorted(x["serial"] for x in W["sensors"] if _Gstage_at(x, r["start"]) == "ST4" and x["family"] == "NTC" and x["has_cal"]
                     and x["serial"] != W["nocal"] and x["serial"] not in ruled)
        if len(ntc) < 3:
            continue
        W["edge_run"] = r["id"]
        W["edge_offsets"] = {ntc[0]: outlier, ntc[1]: outlier + 1}
        W["edge_spike"] = (ntc[2], spike)
        return


def _Gedge_readings(W: dict, r: dict, s: dict, recs: list[dict]) -> None:
    base = r["T"]["ST4"] + W["edge_offsets"].get(s["serial"], 0)
    t = r["start"] - timedelta(minutes=10)
    k = 0
    while t < r["end"] + timedelta(minutes=9):
        val = base
        if r["start"] <= t < r["end"] and s["serial"] == W["edge_spike"][0]:
            k += 1
            if k == 3:
                val = base + W["edge_spike"][1]
            elif k == 4:
                val = base + W["edge_spike"][1] + 1
        c = _Gcal_for(W, s, t)
        if c is None or s["serial"] == W["nocal"]:
            c = (s["family"], W["generic"][s["family"]])
        raw = _Graw_for(c[0], c[1], val)
        if raw is None:
            raw = _Gfr(c[1][-1][0])
        recs.append({"run": r["id"], "sensor": s, "t": t, "raw": raw, "rev": 1, "void": False, "edge": True})
        t += timedelta(minutes=2)


def _Greadings(rng: random.Random, W: dict) -> None:  # noqa: C901
    """Every reading as the DAQ saw it, plus revision copies, void copies and stray records."""
    cfg = W["cfg"]
    recs: list[dict] = []
    W["maint"] = _Gmaintenance(rng, W)
    sparse_pairs = set()
    all_runs = W["runs"] + W["noise_runs"]
    for r in all_runs:
        for s in W["sensors"]:
            if rng.random() < 0.035:
                sparse_pairs.add((r["id"], s["serial"]))
    W["sparse_pairs"] = sorted(sparse_pairs)
    _Gedge_setup(W)
    sigma = {"ST300": 6, "ST50": 4, "ST4": 1}
    spike = {"ST300": (90, 260), "ST50": (70, 220), "ST4": (45, 140)}
    for r in all_runs:
        for s in W["sensors"]:
            st = _Gstage_at(s, r["start"])
            base = r["T"][st] + (s["bias"] if st != "ST4" else s["bias"] // 8)
            if s["serial"] == W["outlier"] and r["id"] in W["outlier_runs"]:
                base += rng.choice([-1, 1]) * rng.randint(320, 520) // (6 if st == "ST4" else 1)
            t = r["start"] - timedelta(minutes=10)
            sparse = (r["id"], s["serial"]) in sparse_pairs
            if r["id"] == W.get("edge_run") and st == "ST4":
                _Gedge_readings(W, r, s, recs)
                continue
            while t < r["end"] + timedelta(minutes=9):
                inside = r["start"] <= t < r["end"]
                if sparse and inside and rng.random() < 0.72:
                    t += timedelta(minutes=2)
                    continue
                if rng.random() < 0.012:
                    t += timedelta(minutes=2)
                    continue
                val = base + round(rng.gauss(0, sigma[st]))
                kind = "OK"
                u = rng.random()
                if u < 0.03:
                    a, b = spike[st]
                    val += rng.choice([-1, 1]) * rng.randint(a, b)
                elif u < 0.037:
                    kind = "INVALID"
                elif u < 0.041:
                    kind = "OOR"
                c = _Gcal_for(W, s, t)
                if s["serial"] == W["nocal"]:
                    c = (s["family"], W["generic"]["NTC"])
                raw: Any
                if kind == "INVALID":
                    raw = None
                elif kind == "OOR" or c is None:
                    fam, pts = c if c else (s["family"], W["generic"][s["family"]])
                    lo = min(_Gfr(p[0]) for p in pts)
                    hi = max(_Gfr(p[0]) for p in pts)
                    raw = hi * Fraction(rng.choice([103, 108, 115]), 100) if rng.random() < 0.5 else lo * Fraction(rng.choice([80, 90, 95]), 100)
                else:
                    raw = _Graw_for(c[0], c[1], val)
                    if raw is None:
                        raw = _Gfr(c[1][-1][0])
                recs.append({"run": r["id"], "sensor": s, "t": t, "raw": raw, "rev": 1, "void": False})
                t += timedelta(minutes=2)
    # stray records: unknown sensor tokens and unmapped channels
    strays = []
    for r in rng.sample(W["runs"], 6):
        for k in range(rng.randint(4, 9)):
            strays.append({"run": r["id"], "sensor": None, "token": rng.choice(["LS-0001", "QX-0002", "HK-0003"]), "t": r["start"] + timedelta(minutes=2 * k),
                           "raw": Fraction(rng.randint(100000, 999999), 10000), "rev": 1, "void": False})
    W["strays"] = strays
    W["unmapped"] = []
    for r in rng.sample(W["runs"], 5):
        for k in range(rng.randint(3, 6)):
            W["unmapped"].append({"run": r["id"], "chan": W["spare_ch"][k % len(W["spare_ch"])], "t": r["start"] + timedelta(minutes=2 * k + 4),
                                  "raw": Fraction(rng.randint(10000, 99999), 1000), "rev": 1, "void": False})
    # revision copies (corrections, ties, voids, void-then-reentered)
    extra = []
    for x in rng.sample([x for x in recs if not x.get("edge")], len(recs) // 16):
        u = rng.random()
        y = dict(x)
        if x["raw"] is None:
            continue
        if u < 0.35:
            y["rev"] = x["rev"] + rng.choice([1, 2])
            y["raw"] = x["raw"] * Fraction(rng.choice([9995, 9998, 10002, 10004]), 10000)
            y["copy"] = "correction"
        elif u < 0.55:
            y["raw"] = x["raw"] * Fraction(rng.choice([9997, 10003]), 10000)
            y["copy"] = "tie"
        elif u < 0.8:
            y["rev"] = x["rev"] + 1
            y["void"] = True
            y["copy"] = "void"
        else:
            # void at rev 1 already superseded by a re-entry at rev 2
            x["void"] = True
            y["rev"] = 2
            y["copy"] = "reentry"
        extra.append(y)
    W["readings"] = recs
    W["reading_copies"] = extra
# --------------------------------------------------------------------------- generator: reading shards
def _Grun_tok(rid: str, style: int) -> str:
    n = int(rid[5:])
    return [rid, f"R{n:02d}", f"r{n}", f"26B-{n:02d}", f"KTC-26B/{n:02d}"][style % 5]


def _Gser_tok(serial: str, style: int) -> str:
    v, d = serial.split("-")
    return [serial, f"{v.lower()}{d}", f"{v} {d}", f"{v}{d}", f"{v.lower()}-{d}", f"{v}_{d}"][style % 6]


def _Gch_tok(ch: str, style: int) -> str:
    u, c = ch[1], ch[3:]
    return [ch, f"DAQ{u}-{c}", f"{u}/{c}", f"ch{c}@daq{u}"][style % 4]


def _Gnative_q(fam: str, raw: Fraction) -> Fraction:
    step = Fraction(1, 10 ** 6) if fam == "DIODE" else Fraction(1, 10 ** 4)
    return round(raw / step) * step


def _Graw_text(q: Fraction, unit: str) -> str:
    if unit in ("ohm", "OHM", "R"):
        return _Gq(q, 4)
    if unit in ("kohm", "KOHM", "K"):
        return _Gq(q / 1000, 7)
    if unit in ("V", "VOLT"):
        return _Gq(q, 6)
    return _Gq(q * 1000, 3)


def _Gunit_pick(fam: str, rng: random.Random, allowed: tuple[str, str, str, str]) -> str:
    ohm, kohm, volt, mvolt = allowed
    if fam == "DIODE":
        return volt if rng.random() < 0.6 else mvolt
    return ohm if rng.random() < 0.65 else kohm


def _Gshard_entries(rng: random.Random, W: dict) -> dict[str, list[dict]]:
    """Distribute readings (and their copies) over the sixteen reading shards."""
    layouts = [lay for _, lay in _GSHARDS]
    pairs = sorted({(x["run"], x["sensor"]["serial"]) for x in W["readings"]})
    rng.shuffle(pairs)
    home = {p: layouts[i % len(layouts)] for i, p in enumerate(pairs)}
    out: dict[str, list[dict]] = {lay: [] for lay in layouts}

    def entry(x: dict, lay: str) -> dict:
        s = x["sensor"]
        q = None if x["raw"] is None else _Gnative_q(s["family"], x["raw"])
        e = {"run": x["run"], "t": x["t"], "raw": q, "fam": s["family"], "rev": x["rev"], "void": x["void"], "serial": s["serial"],
             "label": W["label_at"](s, x["t"]), "chan": _Gchan_at(s, x["t"])}
        return e

    for x in W["readings"]:
        lay = home[(x["run"], x["sensor"]["serial"])]
        out[lay].append(entry(x, lay))
    for y in W["reading_copies"]:
        lay0 = home[(y["run"], y["sensor"]["serial"])]
        lay = rng.choice([l for l in layouts if l != lay0])
        if y.get("copy") == "tie":
            # the copy that must win sits in the later catalog shard
            later = [l for l in layouts if layouts.index(l) > layouts.index(lay0)]
            earlier = [l for l in layouts if layouts.index(l) < layouts.index(lay0)]
            lay = rng.choice(later) if later and (rng.random() < 0.5 or not earlier) else rng.choice(earlier)
        out[lay].append(entry(y, lay))
    n_ties = W["cfg"].get("within_shard_ties") or 0
    if n_ties:
        # same key, same rev, same shard: H5.2 lets the later record in file order win
        rowwise = ("L01", "L02", "L03", "L04", "L05", "L09", "L12", "L13", "L14", "L15")
        copied = {(y["run"], y["sensor"]["serial"], y["t"]) for y in W["reading_copies"]}
        live = {r["id"]: r for r in W["runs"] if not r["aborted"]}
        pool = [x for x in W["readings"] if x["raw"] is not None and not x["void"] and not x.get("edge") and x["run"] in live
                and live[x["run"]]["start"] <= x["t"] < live[x["run"]]["end"] and (x["run"], x["sensor"]["serial"], x["t"]) not in copied
                and home[(x["run"], x["sensor"]["serial"])] in rowwise]
        for x in rng.sample(pool, n_ties):
            y = dict(x)
            y["raw"] = x["raw"] * Fraction(rng.choice([9994, 10006]), 10000)
            out[home[(x["run"], x["sensor"]["serial"])]].append(entry(y, home[(x["run"], x["sensor"]["serial"])]))
    for x in W["strays"]:
        lay = rng.choice([l for l in layouts if l not in _GCHANNEL_LAYOUTS])
        out[lay].append({"run": x["run"], "t": x["t"], "raw": x["raw"], "fam": "PRT", "rev": 1, "void": False, "serial": None,
                         "label": x["token"], "chan": None})
    for x in W["unmapped"]:
        lay = rng.choice(list(_GCHANNEL_LAYOUTS))
        out[lay].append({"run": x["run"], "t": x["t"], "raw": x["raw"], "fam": "PRT", "rev": 1, "void": False, "serial": None,
                         "label": None, "chan": x["chan"]})
    for lay in layouts:
        out[lay].sort(key=lambda e: (e["t"], e["chan"] or "", e["label"] or "", e["rev"]))
        # small local shuffles keep files from being globally time-ordered
        lst = out[lay]
        for i in range(0, len(lst) - 1, 7):
            if rng.random() < 0.3:
                lst[i], lst[i + 1] = lst[i + 1], lst[i]
    return out


def _Gwrite_shards(rng: random.Random, W: dict, data: Path) -> list[dict]:  # noqa: C901
    ent = _Gshard_entries(rng, W)
    cal = W["cfg"]["cal"]
    counts = []
    hi_off = max({cal["base"]} | {o for _, o in cal["transitions"]})
    for fname, lay in _GSHARDS:
        rows = ent[lay]
        path = data / fname
        n = len(rows)
        if lay == "L01":
            body = []
            for e in rows:
                unit = _Gunit_pick(e["fam"], rng, ("ohm", "kohm", "V", "mV"))
                raw = "NaN" if e["raw"] is None else _Graw_text(e["raw"], unit)
                body.append([_Grun_tok(e["run"], rng.choice([0, 1])), _Gser_tok(e["label"], rng.choice([0, 1, 2])), _Gz(e["t"]), raw, unit, e["rev"],
                             "Y" if e["void"] else ""])
            _Gwrite(path, _Gdelim(["run", "sensor", "ts_utc", "raw", "unit", "rev", "void"], body))
        elif lay == "L02":
            body = []
            for e in rows:
                unit = _Gunit_pick(e["fam"], rng, ("OHM", "KOHM", "VOLT", "MVOLT"))
                raw = "-9999" if e["raw"] is None else _Graw_text(e["raw"], unit)
                body.append([_Grun_tok(e["run"], 3), _Gser_tok(e["label"], 3), _Gepoch(e["t"]), raw, unit, e["rev"], "VOID" if e["void"] else "VALID"])
            _Gwrite(path, _Gdelim(["RUN", "SERIAL", "EPOCH_S", "VALUE", "UNITS", "REVISION", "STATUS"], body, "\t"))
        elif lay in ("L03",):
            body = []
            for e in rows:
                w = _Gutc_to_wall(e["t"], cal)
                dst = 1 if _Goffset_at(e["t"], cal) == hi_off else 0
                if e["raw"] is None:
                    raw = "OVL"
                else:
                    raw = _Graw_text(e["raw"], "V" if e["fam"] == "DIODE" else "ohm")
                body.append([_Grun_tok(e["run"], 2), _Gch_tok(e["chan"], 1), w.strftime("%d/%m/%Y %H:%M:%S"), dst, raw, e["rev"], "x" if e["void"] else ""])
            _Gwrite(path, _Gdelim(["run_tag", "chan", "local_time", "isdst", "reading", "rev", "flag"], body, "|"))
        elif lay == "L04":
            lines = []
            for e in rows:
                unit = _Gunit_pick(e["fam"], rng, ("ohm", "kohm", "V", "mV"))
                d = {"r": _Grun_tok(e["run"], 0), "s": _Gser_tok(e["label"], 0), "t_ms": _Gepoch(e["t"]) * 1000 + rng.randint(0, 999),
                     "v": None if e["raw"] is None else _Graw_text(e["raw"], unit), "u": unit, "rv": e["rev"], "del": e["void"]}
                lines.append(json.dumps(d))
            _Gwrite(path, "\n".join(lines) + "\n")
        elif lay == "L05":
            lines = []
            for e in rows:
                unit = _Gunit_pick(e["fam"], rng, ("ohm", "kohm", "V", "mV"))
                d = {"meta": {"run": _Grun_tok(e["run"], 4), "rev": e["rev"]}, "sensor": _Gser_tok(e["label"], 4), "at": _Giso_off(e["t"], cal),
                     "value": {"x": "ERR" if e["raw"] is None else _Graw_text(e["raw"], unit), "unit": unit}, "void": 1 if e["void"] else 0}
                lines.append(json.dumps(d))
            _Gwrite(path, "\n".join(lines) + "\n")
        elif lay == "L06":
            out = ['<?xml version="1.0" encoding="UTF-8"?>', '<readings campaign="KTC-26B" layout="L06">']
            cur = None
            for e in sorted(rows, key=lambda e: (e["run"], e["t"])):
                if e["run"] != cur:
                    if cur is not None:
                        out.append("  </batch>")
                    out.append(f'  <batch run="{_Grun_tok(e["run"], 0)}">')
                    cur = e["run"]
                unit = _Gunit_pick(e["fam"], rng, ("ohm", "kohm", "V", "mV"))
                raw = "" if e["raw"] is None else _Graw_text(e["raw"], unit)
                out.append(f'    <r s="{_Gxesc(_Gser_tok(e["label"], rng.choice([0, 5])))}" t="{_Gz(e["t"])}" raw="{raw}" u="{unit}" rev="{e["rev"]}" '
                           f'void="{"true" if e["void"] else "false"}"/>')
            if cur is not None:
                out.append("  </batch>")
            out.append("</readings>")
            _Gwrite(path, "\n".join(out) + "\n")
        elif lay == "L07":
            ins = []
            for e in rows:
                unit = _Gunit_pick(e["fam"], rng, ("ohm", "kohm", "V", "mV"))
                ins.append((_Grun_tok(e["run"], 1), _Gser_tok(e["label"], 0), _Gepoch(e["t"]), None if e["raw"] is None else _Graw_text(e["raw"], unit),
                            unit, e["rev"], 1 if e["void"] else 0))
            _Gsqlite(path, ["CREATE TABLE readings (run TEXT, sensor TEXT, epoch INTEGER, raw TEXT, unit TEXT, rev INTEGER, voided INTEGER)"],
                     [("INSERT INTO readings VALUES (?,?,?,?,?,?,?)", ins)])
        elif lay == "L08":
            frames: dict[tuple, int] = {}
            fr_rows, sm_rows = [], []
            fid = [5000]
            for e in rows:
                key = (e["run"], e["t"], e["rev"], e["void"])
                if key not in frames:
                    fid[0] += rng.choice([1, 2, 3])
                    frames[key] = fid[0]
                    fr_rows.append((frames[key], _Grun_tok(e["run"], 3), _Gepoch(e["t"]) * 1000 + rng.randint(0, 999), e["rev"], 1 if e["void"] else 0))
                micro = None if e["raw"] is None else int(e["raw"] * 10 ** 6)
                sm_rows.append((frames[key], _Gch_tok(e["chan"], 2), micro))
            _Gsqlite(path, ["CREATE TABLE frames (frame_id INTEGER PRIMARY KEY, run TEXT, epoch_ms INTEGER, rev INTEGER, void INTEGER)",
                            "CREATE TABLE samples (frame_id INTEGER, channel TEXT, micro INTEGER)"],
                     [("INSERT INTO frames VALUES (?,?,?,?,?)", fr_rows), ("INSERT INTO samples VALUES (?,?,?)", sm_rows)])
        elif lay == "L09":
            out = [f"# layout L09 reading export, {len(rows)} records"]
            for e in rows:
                unit = _Gunit_pick(e["fam"], rng, ("ohm", "kohm", "V", "mV"))
                out += [f"- run: {_Grun_tok(e['run'], 1)}", f"  sensor: {_Gser_tok(e['label'], 2)}", f"  at: {_Gepoch(e['t'])}",
                        "  raw: null" if e["raw"] is None else f"  raw: '{_Graw_text(e['raw'], unit)}'", f"  unit: {unit}", f"  rev: {e['rev']}",
                        f"  void: {'yes' if e['void'] else 'no'}"]
            _Gwrite(path, "\n".join(out) + "\n")
        elif lay == "L10":
            by: dict[str, list[dict]] = {}
            for e in rows:
                by.setdefault(e["label"], []).append(e)
            out = ["# layout L10: samples grouped by sensor label; one unit per sensor block"]
            for lab in sorted(by):
                es = by[lab]
                unit = _Gunit_pick(es[0]["fam"], rng, ("ohm", "kohm", "V", "mV"))
                out.append(f"{_Gser_tok(lab, 0)}:")
                out.append(f"  unit: {unit}")
                out.append("  samples:")
                for e in es:
                    raw = "-" if e["raw"] is None else _Graw_text(e["raw"], unit)
                    out.append(f'    - "{_Grun_tok(e["run"], 0)} | {_Gz(e["t"])} | {raw} | {e["rev"]} | {1 if e["void"] else 0}"')
            _Gwrite(path, "\n".join(out) + "\n")
        elif lay == "L11":
            units: dict[str, str] = {}
            data_cols: dict[str, list] = {"run": [], "sensor": [], "t": [], "raw": [], "rev": [], "void": []}
            for e in rows:
                tok = _Gser_tok(e["label"], 0)
                if tok not in units:
                    units[tok] = _Gunit_pick(e["fam"], rng, ("ohm", "kohm", "V", "mV"))
                data_cols["run"].append(_Grun_tok(e["run"], 3))
                data_cols["sensor"].append(tok)
                data_cols["t"].append(_Giso_off(e["t"], cal))
                data_cols["raw"].append("" if e["raw"] is None else _Graw_text(e["raw"], units[tok]))
                data_cols["rev"].append(e["rev"])
                data_cols["void"].append(e["void"])
            doc = {"layout": "L11", "campaign": "KTC-26B", "units": dict(sorted(units.items())), "data": data_cols}
            _Gwrite(path, json.dumps(doc, indent=1) + "\n")
        elif lay == "L12":
            out = ["# KTC-26B DAQ fixed-width export (layout L12)", "# raw carries a unit suffix: R ohm, K kilohm, V volt, M millivolt"]
            hdr = f"{'RUN':<10}{'SENSOR':<11}{'UTC':<17}{'RAW':<15}{'REV':<4}V"
            for i, e in enumerate(rows):
                if i % 50 == 0:
                    out.append(hdr)
                unit = _Gunit_pick(e["fam"], rng, ("R", "K", "V", "M"))
                raw = "*****" if e["raw"] is None else _Graw_text(e["raw"], unit) + unit
                out.append(f"{_Grun_tok(e['run'], 0):<10}{_Gser_tok(e['label'], 0):<11}{e['t'].strftime('%Y%m%dT%H%M%SZ'):<17}{raw:<15}{e['rev']:<4}"
                           f"{'Y' if e['void'] else 'N'}")
            _Gwrite(path, "\n".join(out) + "\n")
        elif lay == "L13":
            by_run: dict[str, list[dict]] = {}
            for e in rows:
                by_run.setdefault(e["run"], []).append(e)
            out = ["# KTC-26B reading digest (layout L13)", ""]
            head = "| sensor | utc | raw | unit | rev | void |"
            for rid in sorted(by_run):
                out.append(f"## Run {rid}")
                out.append("")
                for i, e in enumerate(by_run[rid]):
                    if i % 40 == 0:
                        if i:
                            out.append("")
                            out.append("(continued)")
                            out.append("")
                        out.append(head)
                        out.append("|---|---|---|---|---|---|")
                    unit = _Gunit_pick(e["fam"], rng, ("ohm", "kohm", "V", "mV"))
                    if e["raw"] is None:
                        raw = "n/a"
                    else:
                        raw = _Graw_text(e["raw"], unit)
                        ip, _, fp = raw.partition(".")
                        ip = f"{int(ip):,}"
                        raw = ip + ("." + fp if fp else "")
                    out.append(f"| {_Gser_tok(e['label'], 0)} | {e['t'].strftime('%Y-%m-%d %H:%M:%S')} | {raw} | {unit} | {e['rev']} | "
                               f"{'void' if e['void'] else ''} |")
                out.append("")
            _Gwrite(path, "\n".join(out) + "\n")
        elif lay == "L14":
            body = []
            for e in rows:
                unit = _Gunit_pick(e["fam"], rng, ("ohm", "kohm", "V", "mV"))
                w = _Gutc_to_wall(e["t"], cal)
                dst = 1 if _Goffset_at(e["t"], cal) == hi_off else 0
                raw = "" if e["raw"] is None else _Graw_text(e["raw"], unit).replace(".", ",")
                body.append([_Grun_tok(e["run"], 0), _Gser_tok(e["label"], 0), w.strftime("%Y-%m-%d %H:%M:%S"), dst, raw, unit, e["rev"],
                             1 if e["void"] else 0])
            _Gwrite(path, _Gdelim(["run", "probe", "time_local", "isdst", "value", "unit", "rev", "cancelled"], body, ";"))
        elif lay == "L15":
            body = []
            for e in rows:
                unit = "mV" if e["fam"] == "DIODE" else "kohm"
                raw = "NA" if e["raw"] is None else _Graw_text(e["raw"], unit)
                body.append([_Gch_tok(e["chan"], 3), _Gepoch(e["t"]) * 1000 + rng.randint(0, 999), _Grun_tok(e["run"], 1), raw, unit, e["rev"],
                             "1" if e["void"] else "0"])
            _Gwrite(path, _Gdelim(["ch", "epoch_ms", "run", "val", "unit", "rev", "void"], body, "\t"))
        elif lay == "L16":
            blocks: dict[tuple, list[dict]] = {}
            for e in rows:
                blocks.setdefault((e["run"], e["label"], e["rev"]), []).append(e)
            lines = []
            for (rid, lab, rev) in sorted(blocks):
                es = sorted(blocks[(rid, lab, rev)], key=lambda e: e["t"])
                t0 = es[0]["t"]
                unit = _Gunit_pick(es[0]["fam"], rng, ("ohm", "kohm", "V", "mV"))
                d = {"run": _Grun_tok(rid, 1), "sensor": _Gser_tok(lab, 0), "rev": rev, "t0": _Gz(t0), "unit": unit,
                     "dt": [int((e["t"] - t0).total_seconds()) for e in es],
                     "v": [None if e["raw"] is None else _Graw_text(e["raw"], unit) for e in es],
                     "void": [i for i, e in enumerate(es) if e["void"]]}
                lines.append(json.dumps(d))
            rng.shuffle(lines)
            _Gwrite(path, "\n".join(lines) + "\n")
        counts.append({"file": fname, "layout": lay, "records": n})
    return counts
# --------------------------------------------------------------------------- generator: registers, links, memo, workbook, decoys
_GLINK_FILES = [("lk_9tc1.csv", "S0", "link_catalog"), ("lk_4sg7.xml", "S1", "segments"), ("lk_2sg8.psv", "S2", "segments"),
                ("lk_6jt3.jsonl", "J1", "joints"), ("lk_8in5.tsv", "I1", "installs"), ("lk_3am0.ndjson", "A1", "amendments")]


def _Glink_tok(lid: str, style: int) -> str:
    d = lid[3:]
    return [lid, f"tl{int(d)}", f"TL {d}", f"TL{d}"][style % 4]


def _Gnode_tok(node: str, rng: random.Random) -> str:
    if node.startswith("IX") or rng.random() < 0.55:
        return node
    return rng.choice(_GNODE_ALIASES[node])


def _Gk_float(pts: list[tuple[str, str]], tk: float) -> float:
    xs = [(float(t), float(k)) for t, k in pts]
    if tk <= xs[0][0]:
        return xs[0][1]
    for (t0, k0), (t1, k1) in zip(xs, xs[1:]):
        if t0 <= tk <= t1:
            return k0 + (k1 - k0) * (tk - t0) / (t1 - t0)
    return xs[-1][1]


def _Garea_float(spec: str, awg: dict) -> float:
    kind, _, body = spec.partition(":")
    if kind == "A":
        return float(body[:-3]) * (100 if body.endswith("cm2") else 1)
    if kind == "R":
        w, t = body[:-2].split("x")
        return float(w) * float(t)
    n, g = body[:-3].split("x")
    return int(n) * float(awg[int(g)])


def _Gnoise_links(rng: random.Random, W: dict) -> None:
    """Links of the sister cryostat (KTC-26A); catalogued, never installed in KTC-26B."""
    mats = ["G10_CR", "SS304", "TI6AL4V", "PHBRONZE", "AL6061"]
    W["noise_links"] = {}
    for k in range(160):
        lid = f"TL-{500 + k:03d}"
        segs = [{"mat": rng.choice(mats), "len": _Gq(Fraction(rng.randint(200, 900), 10), 1), "area": f"A:{_Gq(Fraction(rng.randint(100, 900), 10), 2)}mm2",
                 "lot": ""} for _ in range(rng.choice([1, 2, 2]))]
        joints = [{"pos": 0, "class": "BOLT_SS", "bolts": 2, "torque": "NOM", "indium": False},
                  {"pos": len(segs), "class": "BOLT_AL", "bolts": 2, "torque": "NOM", "indium": False}]
        revs = [{"rev": 1, "eff": W["cfg"]["start"] - timedelta(days=200), "status": "ACTIVE", "segs": segs, "joints": joints}]
        if rng.random() < 0.3:
            revs.append({"rev": 2, "eff": W["cfg"]["start"] - timedelta(days=90), "status": "ACTIVE", "segs": [dict(x) for x in segs], "joints": joints})
        W["noise_links"][lid] = {"id": lid, "kind": "SISTER", "revs": revs}


def _Gstock_codes(rng: random.Random, W: dict) -> None:
    codes = {}
    for mat in sorted(_GANCHORS):
        for _ in range(17):
            while True:
                c = f"STK-{rng.randint(10000, 99999)}"
                if c not in codes:
                    break
            codes[c] = (mat, rng.choice(["ACTIVE", "ACTIVE", "ACTIVE", "RETIRED"]))
    W["stock"] = codes


def _Gmat_tok(mat: str, rng: random.Random, W: dict) -> str:
    u = rng.random()
    if u < 0.4:
        return mat
    if u < 0.75:
        return rng.choice(_GMAT_ALIASES[mat])
    act = [c for c, (m, st) in sorted(W["stock"].items()) if m == mat and st == "ACTIVE"]
    return rng.choice(act)


def _Gwrite_links(rng: random.Random, W: dict, data: Path) -> None:  # noqa: C901
    links = W["links"]
    allL = dict(links)
    allL.update(W["noise_links"])
    final = W["final_id"]
    inv_final = {v: k for k, v in final.items() if v != k}
    # catalog: final ids for campaign links (old token for a few)
    rows = []
    for lid in sorted(allL):
        L = allL[lid]
        fid = final.get(lid, lid)
        for rv in L["revs"]:
            tok = fid if rng.random() < 0.8 else _Glink_tok(fid, rng.randint(1, 3))
            rows.append([tok, rv["rev"], rv["eff"].isoformat(), L["kind"], rv["status"], f"{L['kind'].lower().replace('_', ' ')} rev {rv['rev']}"])
    rng.shuffle(rows)
    _Gwrite(data / "lk_9tc1.csv", _Gdelim(["link", "rev", "effective_from", "kind", "status", "description"], rows))
    # segments: S1 xml for ids < 50 and the sister links, S2 psv for the rest
    s1 = ['<?xml version="1.0" encoding="UTF-8"?>', '<segments layout="S1">']
    s2 = []
    for lid in sorted(allL):
        L = allL[lid]
        fid = final.get(lid, lid)
        for rv in L["revs"]:
            if not rv["segs"]:
                continue
            use_xml = int(lid[3:]) < 40 or int(lid[3:]) >= 500 and int(lid[3:]) % 2 == 0
            if use_xml:
                s1.append(f'  <link id="{_Glink_tok(fid, rng.choice([0, 0, 3]))}" rev="{rv["rev"]}">')
                for k, sg in enumerate(rv["segs"], 1):
                    s1.append(f'    <seg n="{k}" mat="{_Gxesc(_Gmat_tok(sg["mat"], rng, W))}" len="{sg["len"]}mm" area="{sg["area"]}" lot="{sg["lot"]}"/>')
                s1.append("  </link>")
            else:
                for k, sg in enumerate(rv["segs"], 1):
                    unit = rng.choice(["mm", "mm", "cm", "in"]) if sg["mat"] != "PHBRONZE" else "mm"
                    L_mm = _Gfr(sg["len"])
                    if unit == "cm" and (L_mm * 100) % 10 == 0:
                        lv = _Gstrip(_Gq(L_mm / 10, 3))
                    elif unit == "in" and (L_mm * 1000) % 254 == 0:
                        lv = _Gstrip(_Gq(L_mm / Fraction(254, 10), 4))
                    else:
                        unit = "mm"
                        lv = sg["len"]
                    s2.append([_Glink_tok(fid, rng.choice([0, 1])), rv["rev"], k, _Gmat_tok(sg["mat"], rng, W), lv, unit, sg["area"], sg["lot"] or "-"])
    s1.append("</segments>")
    _Gwrite(data / "lk_4sg7.xml", "\n".join(s1) + "\n")
    rng.shuffle(s2)
    _Gwrite(data / "lk_2sg8.psv", _Gdelim(["link", "rev", "seq", "material", "length", "length_unit", "area_spec", "lot"], s2, "|"))
    # joints
    jl = []
    for lid in sorted(allL):
        fid = final.get(lid, lid)
        for rv in allL[lid]["revs"]:
            for j in rv["joints"]:
                d = {"link": _Glink_tok(fid, rng.choice([0, 2])), "rev": rv["rev"], "pos": j["pos"], "class": j["class"], "bolts": j["bolts"],
                     "torque": j["torque"] if rng.random() < 0.8 else j["torque"].lower(), "indium": j["indium"] if rng.random() < 0.8 else ("yes" if j["indium"] else "no")}
                jl.append(json.dumps(d))
    rng.shuffle(jl)
    _Gwrite(data / "lk_6jt3.jsonl", "\n".join(jl) + "\n")
    # installs: per run; tokens use the id in force at the run (old id before a rename)
    ins = []
    for r in W["runs"] + W["noise_runs"]:
        rows_r = W["installs"].get(r["id"], [{"link": f"TL-{1 + k:03d}", "hot": "ST300", "cold": "ST50"} for k in range(4)])
        for row in rows_r:
            lid = row["link"]
            tok = lid
            cur = lid
            for rn in W["renames"]:
                if rn["old"] == cur and r["day"] >= rn["at"]:
                    cur = rn["new"]
            for rn in W["renames"]:
                if rn["old"] == cur and r["day"] >= rn["at"]:
                    cur = rn["new"]
            tok = cur
            ins.append([_Grun_tok(r["id"], rng.choice([0, 1, 3])), _Glink_tok(tok, rng.choice([0, 0, 1, 2])), _Gnode_tok(row["hot"], rng),
                        _Gnode_tok(row["cold"], rng), "INSTALLED", 1])
        if r in W["runs"] and rng.random() < 0.3:
            row = rng.choice(rows_r)
            ins.append([_Grun_tok(r["id"], 0), _Glink_tok(row["link"], 0), _Gnode_tok(row["hot"], rng), _Gnode_tok(row["cold"], rng), "REMOVED", 2])
            ins.append([_Grun_tok(r["id"], 1), _Glink_tok(row["link"], 0), _Gnode_tok(row["hot"], rng), _Gnode_tok(row["cold"], rng), "INSTALLED", 3])
        if r in W["runs"] and rng.random() < 0.2:
            extra = rng.choice(sorted(W["noise_links"]))
            ins.append([_Grun_tok(r["id"], 0), extra, "ST300", "ST50", "INSTALLED", 1])
            ins.append([_Grun_tok(r["id"], 0), extra, "ST300", "ST50", "REMOVED", 2])
    rng.shuffle(ins)
    _Gwrite(data / "lk_8in5.tsv", _Gdelim(["run", "link", "hot", "cold", "state", "rev"], ins, "\t"))
    _Gwrite_amendments(rng, W, data)


def _Gwrite_amendments(rng: random.Random, W: dict, data: Path) -> None:
    links = W["links"]
    final = W["final_id"]
    ents = []
    seq = [1000]

    def put(link: str, rev: int, field: str, value: str, action: str = "SET", status: str = "POSTED", target: int | None = None) -> int:
        seq[0] += rng.randint(1, 4)
        e = {"seq": seq[0], "link": _Glink_tok(final.get(link, link), rng.choice([0, 0, 1])), "rev": rev, "field": field, "value": value,
             "action": action if rng.random() < 0.85 else action.lower(), "status": status if rng.random() < 0.85 else status.lower()}
        if target is not None:
            e["reverses"] = target
        e["entered"] = _Gz(datetime.combine(W["cfg"]["start"], datetime.min.time(), _GUTC) + timedelta(hours=seq[0] - 1000))
        ents.append(e)
        return seq[0]

    pool = sorted(links)
    for i in range(W["cfg"]["amend_chains"]):
        lid = rng.choice(pool)
        rv = rng.choice(links[lid]["revs"])
        if not rv["segs"]:
            continue
        k = rng.randrange(len(rv["segs"])) + 1
        sg = rv["segs"][k - 1]
        if sg["mat"] == "PHBRONZE":
            alt = lambda: str(int(sg["len"]) + rng.choice([-40, -10, 20, 35]))
        else:
            alt = lambda: _Gq(_Gfr(sg["len"]) + Fraction(rng.choice([-30, -12, 8, 21]), 10), 1)
        kind = i % 6
        f = f"seg{k}.length_mm"
        if kind == 0:
            put(lid, rv["rev"], f, alt())
        elif kind == 1:
            put(lid, rv["rev"], f, alt())
            s2 = put(lid, rv["rev"], f, alt())
            put(lid, rv["rev"], f, "", "REVERSE", target=s2)
        elif kind == 2:
            s1 = put(lid, rv["rev"], f, alt())
            s2 = put(lid, rv["rev"], f, "", "REVERSE", target=s1)
            put(lid, rv["rev"], f, "", "REVERSE", target=s2)
        elif kind == 3:
            s1 = put(lid, rv["rev"], f, alt())
            put(lid, rv["rev"], f, "", "REVERSE", status="PENDING", target=s1)
        elif kind == 4:
            put(lid, rv["rev"], f, alt(), status="PENDING")
        else:
            j = rng.choice(rv["joints"])
            put(lid, rv["rev"], f"joint{j['pos']}.bolts", str(j["bolts"] + 1))
    for _ in range(4):
        lid = rng.choice(pool)
        rv = links[lid]["revs"][0]
        if rv["segs"]:
            put(lid, rv["rev"], "seg1.area", rv["segs"][0]["area"] if rng.random() < 0.5 else rv["segs"][0]["area"])
    for _ in range(3):
        lid = rng.choice([x for x in pool if any(rv["joints"] for rv in links[x]["revs"])])
        rv = links[lid]["revs"][0]
        j = rng.choice(rv["joints"])
        put(lid, rv["rev"], f"joint{j['pos']}.torque", "LOW" if j["torque"] == "NOM" else "NOM")
    if W["cfg"].get("extra_amend"):
        for lid, rev, field, value, action, status, back in W["cfg"]["extra_amend"]:
            tgt = ents[-back]["seq"] if back else None
            put(lid, rev, field, value, action, status, tgt)
    while len(ents) < 214:
        lid = rng.choice(sorted(W["noise_links"]))
        put(lid, 1, "seg1.length_mm", _Gq(Fraction(rng.randint(200, 900), 10), 1), status=rng.choice(["POSTED", "PENDING"]))
    rng.shuffle(ents)
    _Gwrite(data / "lk_3am0.ndjson", "".join(json.dumps(e) + "\n" for e in ents))


def _Gwrite_registers(rng: random.Random, W: dict, data: Path) -> None:  # noqa: C901
    cfg = W["cfg"]
    # alias register
    mat_rows = []
    for mat in sorted(_GMAT_ALIASES):
        for a in _GMAT_ALIASES[mat]:
            mat_rows.append((a, mat, "ACTIVE"))
    mat_rows += [("G10", "G10_FR4", "RETIRED"), ("Cu", "CU_ETP", "RETIRED"), ("SS", "SS304", "RETIRED"), ("NEMA G10", "G10_CR", "ACTIVE")]
    mat_rows = [r for i, r in enumerate(mat_rows) if r not in mat_rows[:i]]
    for c, (mat, st) in sorted(W["stock"].items()):
        tgt = mat if rng.random() < 0.7 else rng.choice(_GMAT_ALIASES[mat])
        mat_rows.append((c, tgt, st))
    rng.shuffle(mat_rows)
    node_rows = [(a, n) for n in sorted(_GNODE_ALIASES) for a in _GNODE_ALIASES[n]]
    link_rows = [(x["old"], x["new"], x["at"].isoformat()) for x in W["renames"]]
    link_rows += [(f"TL-{600 + k:03d}", f"TL-{700 + k:03d}", (cfg["start"] - timedelta(days=300)).isoformat()) for k in range(12)]
    rl_rows = [(x["old"], x["new"], _Gz(x["at"])) for x in W["relabels"]]
    rl_rows += [(f"QX-{9000 + k}", f"QX-{9500 + k}", "2025-03-01T00:00:00Z") for k in range(10)]
    _Gsqlite(data / "entity_alias_register.sqlite",
             ["CREATE TABLE material_alias (token TEXT, target TEXT, status TEXT)", "CREATE TABLE node_alias (token TEXT, node TEXT)",
              "CREATE TABLE link_alias (old_id TEXT, new_id TEXT, effective TEXT)", "CREATE TABLE sensor_relabel (old_serial TEXT, new_serial TEXT, effective_utc TEXT)"],
             [("INSERT INTO material_alias VALUES (?,?,?)", mat_rows), ("INSERT INTO node_alias VALUES (?,?)", node_rows),
              ("INSERT INTO link_alias VALUES (?,?,?)", link_rows), ("INSERT INTO sensor_relabel VALUES (?,?,?)", rl_rows)])
    # channel map history: label in use at the start of each assignment
    ch_rows = []
    early = datetime.combine(cfg["start"] - timedelta(days=400), datetime.min.time(), _GUTC)
    for u in (1, 2):
        for c in range(1, 25):
            ch = f"D{u}C{c:02d}"
            ch_rows.append((ch, f"QX-{8000 + 30 * u + c}", _Gz(early), _Gz(early + timedelta(days=150))))
            ch_rows.append((ch, f"RV-{8100 + 30 * u + c}", _Gz(early + timedelta(days=150)), _Gz(early + timedelta(days=300))))
            ch_rows.append((ch, f"TM-{8200 + 30 * u + c}", _Gz(early + timedelta(days=300)), _Gz(early + timedelta(days=340))))
            ch_rows.append((ch, f"HK-{8300 + 30 * u + c}", _Gz(early + timedelta(days=340)), _Gz(early + timedelta(days=380))))
    for s in W["sensors"]:
        hist = s["chan_hist"]
        for k, (at, ch) in enumerate(hist):
            end = hist[k + 1][0] if k + 1 < len(hist) else None
            ch_rows.append((ch, W["label_at"](s, at), _Gz(at), None if end is None else _Gz(end)))
    for ch in W["spare_ch"][:3]:
        ch_rows.append((ch, "LS-0001", _Gz(early), _Gz(early + timedelta(days=10))))
    rng.shuffle(ch_rows)
    _Gsqlite(data / "channel_map_history.db", ["CREATE TABLE channel_assignment (channel TEXT, serial TEXT, valid_from_utc TEXT, valid_to_utc TEXT)"],
             [("INSERT INTO channel_assignment VALUES (?,?,?,?)", ch_rows)])
    # sensor map yaml (final serial -> stage history)
    out = [f"# {cfg['campaign']} sensor to stage assignment history", "assignments:"]
    for s in sorted(W["sensors"], key=lambda s: s["serial"]):
        out.append(f"  - serial: {s['serial']}")
        out.append("    history:")
        for at, st in s["hist"]:
            out.append(f"      - stage: {_Gnode_tok(st, rng)}")
            out.append(f"        from_utc: '{_Gz(at)}'")
    for k in range(30):
        out.append(f"  - serial: HK-{9100 + k}")
        out.append("    history:")
        out.append("      - stage: SPARE")
        out.append(f"        from_utc: '{_Gz(early)}'")
    _Gwrite(data / "sensor_map_k26b.yaml", "\n".join(out) + "\n")
    # inventory
    inv = []
    for s in W["sensors"]:
        inv.append({"serial": s["serial"], "family": s["family"], "status": "INSTALLED", "cal_policy": s["policy"],
                    "generic_curve": {"PRT": "PRT-385", "NTC": "NTC-2", "DIODE": "DIODE-11"}[s["family"]]})
    fams = ["PRT", "NTC", "DIODE"]
    for k in range(205):
        inv.append({"serial": f"{rng.choice(['LS', 'QX', 'RV', 'TM', 'HK'])}-{9100 + k}", "family": rng.choice(fams), "status": rng.choice(["SPARE", "RETIRED"]),
                    "cal_policy": rng.choice(["SERIAL", "GENERIC_OK"]), "generic_curve": rng.choice(["PRT-385", "NTC-1", "DIODE-10"])})
    rng.shuffle(inv)
    _Gwrite(data / "sensor_inventory.json", json.dumps({"campaign": cfg["campaign"], "sensors": inv}, indent=1) + "\n")


def _Gwrite_runs(rng: random.Random, W: dict, data: Path) -> None:
    cfg = W["cfg"]
    cal = cfg["cal"]
    rows = []
    ab = [r for r in W["runs"] if r["aborted"]]
    wd = W["runs"][W["abort_withdrawn"]]
    for r in W["runs"] + W["noise_runs"]:
        def wall(u: datetime) -> str:
            return _Gutc_to_wall(u, cal).strftime("%Y-%m-%d %H:%M")
        tok = lambda: _Grun_tok(r["id"], rng.choice([0, 0, 1, 2]))
        rows.append([tok(), "COOLDOWN_START", wall(r["start"] - timedelta(hours=rng.randint(20, 40))), "", 1, "ops"])
        rows.append([tok(), "CONFIG", wall(r["start"] - timedelta(hours=2)), r["shield"], 1, "ops"])
        if rng.random() < 0.2:
            rows.append([tok(), "CONFIG", wall(r["start"] - timedelta(hours=3)), rng.choice(["SC-A", "SC-B", "SC-C", "SC-D"]), 0, "ops"])
        if rng.random() < 0.3:
            rows.append([tok(), "PLATEAU_START", wall(r["start"] - timedelta(minutes=rng.choice([10, 16, 24]))), "", 1, "ops"])
            rows.append([tok(), "PLATEAU_START", W.get("gap_wall", {}).get(r["id"]) or wall(r["start"]), "", 2, "qa"])
        else:
            rows.append([tok(), "PLATEAU_START", W.get("gap_wall", {}).get(r["id"]) or wall(r["start"]), "", 1, "ops"])
        if rng.random() < 0.25:
            rows.append([tok(), "PLATEAU_END", wall(r["end"] + timedelta(minutes=rng.choice([6, 12]))), "", 1, "ops"])
            rows.append([tok(), "PLATEAU_END", wall(r["end"]), "", 3, "qa"])
        else:
            rows.append([tok(), "PLATEAU_END", wall(r["end"]), "", 1, "ops"])
        rows.append([tok(), "WARMUP_START", wall(r["end"] + timedelta(hours=rng.randint(2, 9))), "", 1, "ops"])
        for _ in range(rng.randint(1, 3)):
            rows.append([tok(), "NOTE", wall(r["start"] + timedelta(minutes=rng.randint(-200, 200))), rng.choice(["pump check", "LN2 refill",
                         "shift change", "logger restart", "heater off"]), 1, "ops"])
        if r in ab:
            rows.append([tok(), "ABORT", wall(r["end"] - timedelta(minutes=8)), "ACTIVE", 1, "ops"])
        if r is wd:
            rows.append([tok(), "ABORT", wall(r["end"] - timedelta(minutes=8)), "ACTIVE", 1, "ops"])
            rows.append([tok(), "ABORT", wall(r["end"] + timedelta(minutes=30)), "WITHDRAWN", 2, "qa"])
    rng.shuffle(rows)
    _Gwrite(data / "run_log_k26b.csv", _Gdelim(["run", "event", "local_time", "value", "rev", "entered_by"], rows))
    # harness dissipation (bundle level; the node comes from the intercept register)
    hrows = []
    for b in W["bundles"]:
        if rng.random() < 0.5:
            val, unit = _Gq(Fraction(b["uw"], 1000), 3), "mW"
        else:
            val, unit = str(b["uw"]), "uW"
        if rng.random() < 0.12:
            hrows.append([b["id"], _Grun_tok(b["run"], 0), b["hint"], _Gq(Fraction(b["uw"] + rng.randint(100, 900), 1000), 3), "mW", 1, ""])
            hrows.append([b["id"], _Grun_tok(b["run"], 1), b["hint"], val, unit, 2, ""])
        else:
            hrows.append([b["id"], _Grun_tok(b["run"], rng.choice([0, 1])), b["hint"], val, unit, 1, ""])
        if rng.random() < 0.05:
            hrows.append([b["id"], _Grun_tok(b["run"], 0), b["hint"], val, unit, 9, "VOID"])
    rng.shuffle(hrows)
    _Gwrite(data / "harness_dissipation.psv", _Gdelim(["bundle", "run", "node_hint", "dissipation", "unit", "rev", "void"], hrows, "|"))
    # intercept register
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<intercepts campaign="{cfg["campaign"]}">']
    for r in W["runs"] + W["noise_runs"]:
        for x in W["intercepts"].get(r["id"], []):
            out.append(f'  <intercept id="{x["id"]}" run="{_Grun_tok(r["id"], 0)}" band="{x["band"]}" nominal_K="{x["nominal"]}"/>')
    for b in W["bundles"]:
        out.append(f'  <bundle id="{b["id"]}" run="{_Grun_tok(b["run"], rng.choice([0, 1]))}" node="{_Gnode_tok(b["node"], rng)}"/>')
    out.append("</intercepts>")
    _Gwrite(data / "intercept_register.xml", "\n".join(out) + "\n")
    # lot certificates
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<lot_certificates>"]
    lots = dict(W["lot_scale"])
    for k in range(260):
        lots[f"LOT-ZZ{7000 + k}"] = (_Gq(Fraction(rng.randint(900, 1080), 1000), 3), rng.choice(["CERTIFIED", "WITHDRAWN"]))
    for lt in sorted(lots, key=lambda x: (rng.random(), x)):
        sc, st = lots[lt]
        out.append(f'  <lot id="{lt}" k_scale="{sc}" status="{st}" issued="{(W["cfg"]["start"] - timedelta(days=rng.randint(30, 400))).isoformat()}"/>')
    out.append("</lot_certificates>")
    _Gwrite(data / "material_lot_certs.xml", "\n".join(out) + "\n")
    # ruling addendum
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<ruling_addendum memo="governance_memo_k26b.pdf">']
    for a in W["addendum"]:
        out.append(f'  <entry seq="{a["seq"]}" ref="{a["ref"]}" action="{a["action"]}" status="{a["status"]}"/>')
    out.append("</ruling_addendum>")
    _Gwrite(data / "ruling_addendum.xml", "\n".join(out) + "\n")
    # cooler service log
    rows = [[e["date"].isoformat(), e["cooler"], e["action"], e["value"], rng.choice(["tech-a", "tech-b", "vendor"])] for e in W["service"]]
    _Gwrite(data / "cooler_service_log.tsv", _Gdelim(["date", "cooler", "action", "value", "by"], rows, "\t"))


def _Gwrite_profile(rng: random.Random, W: dict, data: Path) -> None:
    cfg = W["cfg"]
    sh = cfg["sheets"]
    kn = cfg["knobs"]
    out = [f"# {cfg['campaign']} campaign profile", f"campaign: {cfg['campaign']}", f"profile_revision: {cfg['profile_revision']}",
           f"conductivity_sheet: {sh['k']}", f"calibration_sheet: {sh['cal']}", f"capacity_sheet: {sh['cap']}",
           f"spike_mK: {kn['spike_mK']}", f"outlier_mK: {kn['outlier_mK']}", f"min_readings: {kn['min_readings']}",
           "reserve_pct:", f"  ST50: {cfg['reserve']['ST50']}", f"  ST4: {cfg['reserve']['ST4']}", "runs:"]
    for r in W["runs"]:
        out.append(f"  - id: {r['id']}")
        out.append(f"    cooler: {r['cooler']}")
        out.append(f"    operator: {rng.choice(['A. Varga', 'L. Moreau', 'K. Osei', 'P. Lindqvist'])}")
        out.append(f"    purpose: {rng.choice(['standoff qualification', 'harness heat sink', 'shield config sweep', 'repeatability'])}")
        if rng.random() < 0.3:
            pick = rng.choice([35, 50])
            if r["id"] != W.get("edge_run"):
                out.append(f"    spike_mK: {pick}")
                r["prof_spike"] = pick
        out.append(f"    ticket: QT-{rng.randint(20000, 29999)}")
        out.append(f"    target_ST4_K: '{rng.choice(['4.2', '4.0', '3.9'])}'")
        out.append(f"    logger: DAQ{rng.randint(1, 2)}")
        out.append(f"    window_note: {rng.choice(['steady', 'slow drift', 'nominal'])}")
    _Gwrite(data / "campaign_profile_k26b.yml", "\n".join(out) + "\n")
    # site overlay
    site_base = cfg["profile_revision"] if cfg.get("overlay_base") is None else cfg["overlay_base"]
    out = ["# site overlay for the campaign profile", f"base_revision: {site_base}", "overridable_keys:", "  - spike_mK", "  - outlier_mK",
           "  - min_readings", "runs:"]
    for r in W["runs"]:
        o = W["overlay"][r["id"]]
        out.append(f"  {r['id']}:")
        out.append(f"    shift: {rng.choice(['day', 'late', 'night'])}")
        for k in sorted(o):
            out.append(f"    {k}: {o[k]}")
        out.append(f"    daq_profile: {rng.choice(['fast', 'standard'])}")
        out.append(f"    reviewed_by: {rng.choice(['qa-1', 'qa-2', 'qa-3'])}")
        out.append(f"    reserve_pct_ST50: {rng.choice([10, 12, 18])}")
        out.append(f"    daq_rate_s: {rng.choice([60, 120])}")
        out.append(f"    hall_temp_C: '{rng.choice(['21.5', '22.0', '22.5'])}'")
    _Gwrite(data / "profile_overlay_site.yaml", "\n".join(out) + "\n")
    out = ["# laboratory overlay (prepared for profile revision 6)", f"base_revision: {cfg['profile_revision'] - 1}", "overridable_keys:",
           "  - spike_mK", "  - outlier_mK", "  - min_readings", "runs:"]
    for r in W["runs"]:
        o = W["stale_overlay"][r["id"]]
        out.append(f"  {r['id']}:")
        for k in sorted(o):
            out.append(f"    {k}: {o[k]}")
        out.append(f"    bench: {rng.choice(['B1', 'B2'])}")
        out.append(f"    prepared_by: {rng.choice(['lab-1', 'lab-2'])}")
        out.append(f"    reserve_pct_ST4: {rng.choice([10, 30])}")
        out.append(f"    signed_off: {rng.choice(['no', 'pending'])}")
    _Gwrite(data / "profile_overlay_lab.yaml", "\n".join(out) + "\n")
    # site calendar
    cal = cfg["cal"]
    out = [f"site: {cfg['site']}", f"base_offset: '{_Goff_text(cal['base'])}'", "transitions:"]
    for when, o in cal["transitions"]:
        out += [f"  - at_utc: '{_Gz(when)}'", f"    offset_after: '{_Goff_text(o)}'"]
    out.append("maintenance:")
    for b in W["maint"]:
        out += [f"  - start_utc: '{_Gz(b['start'])}'", f"    end_utc: '{_Gz(b['end'])}'", f"    scope: {b['scope']}", f"    note: {b['note']}"]
    out.append("days:")
    d = cfg["start"] - timedelta(days=10)
    while d <= W["runs"][-1]["day"] + timedelta(days=5):
        out.append(f"  - date: '{d.isoformat()}'")
        out.append(f"    lead: {rng.choice(['A. Varga', 'L. Moreau', 'K. Osei', 'P. Lindqvist', 'S. Ito'])}")
        out.append(f"    hall: {rng.choice(['OPEN', 'OPEN', 'OPEN', 'RESTRICTED'])}")
        d += timedelta(days=1)
    _Gwrite(data / "site_calendar.yml", "\n".join(out) + "\n")


def _Gwrite_workbook(rng: random.Random, W: dict, data: Path) -> None:
    cfg = W["cfg"]
    sh = cfg["sheets"]
    d1904 = cfg["date1904"]

    def ksheet(tables: dict) -> list[list[Any]]:
        rows: list[list[Any]] = [["material", "T_K", "k", "unit"]]
        for mat in sorted(tables):
            for t, k in tables[mat]:
                if mat in _GSMALLK:
                    kv, unit = _Gstrip(_Gq(_Gfr(k) * 10, 6)), "mW/cm-K"
                else:
                    kv, unit = k, "W/m-K"
                rows.append([mat, ("n", t) if rng.random() < 0.7 else t, ("n", kv) if rng.random() < 0.6 else kv, unit])
        return rows

    def calsheet(cals: dict, perturb: bool) -> list[list[Any]]:
        rows: list[list[Any]] = [["serial", "version", "valid_from", "point", "raw", "unit", "T_K"]]
        sens = {s["serial"]: s for s in W["sensors"]}
        for serial in sorted(cals):
            s = sens[serial]
            for v in cals[serial]:
                vf = _Gserial(v["valid_from"] - timedelta(days=30 if perturb else 0), d1904)
                for k, (raw, tk) in enumerate(v["pts"], 1):
                    if s["family"] == "DIODE":
                        rv, unit = raw, "V"
                    elif s.get("kohm"):
                        rv, unit = _Gstrip(_Gq(_Gfr(raw) / 1000, 7)), "kohm"
                    else:
                        rv, unit = raw, "ohm"
                    tkv = tk if not perturb else _Gq(_Gfr(tk) + Fraction(rng.choice([-12, 9, 15]), 1000), 3)
                    rows.append([serial, v["ver"], vf, k, ("n", rv) if rng.random() < 0.7 else rv, unit, ("n", tkv) if rng.random() < 0.5 else tkv])
        return rows

    def capsheet(cap: dict, scale: Fraction) -> list[list[Any]]:
        rows: list[list[Any]] = [["model", "stage", "T_K", "capacity_W"]]
        for (model, st) in sorted(cap):
            for t, c in cap[(model, st)]:
                rows.append([model, st, ("n", t), ("n", _Gq(_Gfr(c) * scale, 4)) if rng.random() < 0.7 else _Gq(_Gfr(c) * scale, 4)])
        return rows

    readme = [["note"], [f"{cfg['campaign']} cryogenic property workbook"], ["Sheets are registered by name in the campaign profile."],
              [f"{sh['k_old']} was approved for the KTC-26A campaign."], ["Values flagged mW/cm-K are per centimetre."],
              [f"{sh['cal_old']} lists the factory calibrations issued before the October recalibration."],
              ["Dates are workbook serial day numbers."]]
    old_cals = {k: v[:1] for k, v in W["cals"].items()}
    sheets = [("README", readme, False), (sh["k_old"], ksheet(W["k_old"]), False), (sh["cal"], calsheet(W["cals"], False), False),
              (sh["k"], ksheet(W["k_tables"]), False), (sh["cap_old"], capsheet(cfg["cap"], Fraction(108, 100)), False),
              (sh["cal_old"], calsheet(old_cals, True), False), (sh["k_draft"], ksheet(W["k_draft"]), True), (sh["cap"], capsheet(cfg["cap"], Fraction(1)), False)]
    order = list(range(1, len(sheets) + 1))
    rng.shuffle(order)
    _Gxlsx(data / "cryo_property_workbook.xlsx", sheets, order, rng, d1904)


def _Gwrite_memo(rng: random.Random, W: dict, data: Path) -> None:  # noqa: C901
    cfg = W["cfg"]
    J_in, J_out = cfg["labels"]["J"]
    P_in, P_out = cfg["labels"]["P"]
    S_in, S_out = cfg["labels"]["S"]
    items: list[tuple[list[str], tuple[str, list[str]] | None]] = [
        ([f"Thermal budget governance memo, campaign {cfg['campaign']}"], None),
        (["Issued by the cryostat qualification board. Tables marked IN FORCE govern the budget;"], None),
        (["tables marked WITHDRAWN are kept for audit only and must not be applied."], None), ([""], None)]

    def table(label: str, title: str, status: str, header: list[str], body: list[list[str]]) -> None:
        items.append(([f"Table {label}: {title} ({status})"], None))
        items.append((header, None))
        for b in body:
            items.append((b, (label, header)))
        items.append(([""], None))

    S1, S2 = cfg["S1"], cfg["S2"]
    table(S_out, "Solver contract constants", "WITHDRAWN", ["constant", "value"], [[k, S1[k]] for k in sorted(S1)])
    table(J_out, "Joint base conductance per bolt, mW/K", "WITHDRAWN", ["class", "band", "h_mW_per_K"], [[c, b, v] for (c, b), v in sorted(cfg["J1"].items())])
    table(S_in, "Solver contract constants", "IN FORCE", ["constant", "value"], [[k, S2[k]] for k in sorted(S2)])
    table(P_out, "Parasitic load by shield configuration, uW", "WITHDRAWN", ["config", "stage", "load_uW"], [[c, s, str(v)] for (c, s), v in sorted(cfg["P1"].items())])
    table(J_in, "Joint base conductance per bolt, mW/K", "IN FORCE", ["class", "band", "h_mW_per_K"], [[c, b, v] for (c, b), v in sorted(cfg["J2"].items())])
    table("W-1", "Conductor cross-section by gauge, mm2", "IN FORCE", ["awg", "area_mm2"], [[str(g), a] for g, a in sorted(cfg["AWG"].items())])
    table(P_in, "Parasitic load by shield configuration, uW", "IN FORCE", ["config", "stage", "load_uW"], [[c, s, str(v)] for (c, s), v in sorted(cfg["P2"].items())])
    table("L-1", "Stage temperature limits, mK", "IN FORCE", ["stage", "limit_mK"], [[s, str(v)] for s, v in sorted(cfg["L1"].items())])
    items.append((["Table R-1 lists the rulings of the board. A ruling applies only while its status is IN FORCE after the addendum."], None))
    table("R-1", "Rulings register", "IN FORCE", ["ruling", "run", "target", "action", "value", "status"],
          [[x["id"], x["run"], x["target"], x["action"], x["value"] or "-", x["status"]] for x in W["rulings"]])
    pages: list[list[list[str]]] = [[]]
    for cells, ctx in items:
        if len(pages[-1]) >= 70:
            pages.append([])
            if ctx is not None:
                pages[-1].append([f"Table {ctx[0]} (continued)"])
                pages[-1].append(ctx[1])
        pages[-1].append(cells)
    _Gpdf(data / "governance_memo_k26b.pdf", pages, rng, f"Governance memo {cfg['campaign']}")
# --------------------------------------------------------------------------- generator: handbook (the written rules)
_GHANDBOOK = """# Thermal heat-load budget handbook (revision 9)

This handbook is the written contract for the heat-load budget of a cryostat qualification campaign. The campaign
profile names the campaign, its runs and its knobs; the governance memo (pdf) carries the board's tables; the
cryogenic property workbook (xlsx) carries conductivity tables, sensor calibrations and cooler capacity maps.
Every rule below is normative. Worked examples use toy numbers that do not occur in any campaign.

## H1 Authority

1. The sources that govern the budget are: the memo tables whose title ends in (IN FORCE); the workbook sheets
   whose names the campaign profile gives under conductivity_sheet, calibration_sheet and capacity_sheet; the
   campaign profile; the site overlay under the condition of H13; the alias register and channel map; the
   catalogued shards and link files; the run log, harness ledger, intercept register, lot certificates, ruling
   addendum, cooler service log, sensor map, sensor inventory and site calendar; this handbook; feed_layouts.md and
   output_contract.md.
2. A memo table whose title ends in (WITHDRAWN) is never applied, even when it is printed first or carries the same
   header. A workbook sheet that the profile does not name is never applied, whether it is visible, hidden or
   described as approved in the README sheet.
3. The saved solve pack, the published budget and stage margins, the DAQ dashboard export, the conductivity cache,
   the quick reference card, the operations bulletin, the draft handbook, the legacy materials file and any overlay
   whose base_revision differs from the profile revision are lower-authority sources. They are read only for the
   comparisons of H24 and H25.
4. The generic calibration curves are applied only under H9.3.

## H2 Catalog

1. ingest_catalog_*.json lists the input files by kind with an order number. Only entries with status ACTIVE are
   read; an entry with status RETIRED is skipped even when its file exists.
2. A file that looks like a shard but is not listed in the catalog is not an input.
3. Catalog order (ascending order number) is the tie-break order of H5.2.
4. field_maps documents, per layout, which source field carries which canonical field. value_maps documents the
   void markers and missing-value sentinels of each layout.

## H3 Runs

1. A run token is canonicalised by taking its trailing integer n and writing KTC-Rnn with n zero-padded to two
   digits. Accepted spellings: KTC-R07, R07, r7, 26B-07, KTC-26B/07. A token that names another campaign
   (KTC-26A/..., KTC-25C/...) does not belong to this campaign and is ignored.
2. A run is in scope when the campaign profile lists it under runs. Records of runs that are not in scope are
   ignored and are not reported anywhere except the out_of_scope_readings counter of the dedup report.
3. In the run log the latest rev of each (run, event) pair is the effective entry; NOTE entries carry no
   information for the budget. The plateau window of a run is [PLATEAU_START, PLATEAU_END): a reading at exactly
   PLATEAU_START is inside, a reading at exactly PLATEAU_END is outside.
4. The effective CONFIG entry gives the shield configuration of the run.
5. A run whose effective ABORT entry has value ACTIVE is aborted. An ABORT entry later re-entered with value
   WITHDRAWN at a higher rev cancels the abort. An aborted run gets no readings, temperatures, links, loads or
   margins; its run verdict is ABORTED. output_contract.md names the comparison and summary reports that still
   carry a row for it.

## H4 Time

1. Run log times and layouts marked local are site wall time. A wall time maps to the earliest UTC instant whose
   site offset turns it into that wall time; a wall time inside a skipped hour uses the offset in effect before the
   jump. Site offsets come from site_calendar.yml: base_offset applies before the first transition, and each
   transition switches to offset_after at its at_utc instant.
2. Local-time reading layouts carry an isdst column. isdst = 1 means the larger of the site's offsets was in effect,
   isdst = 0 the smaller; the instant is the wall time minus that offset.
3. Epoch values are seconds or milliseconds since 1970-01-01T00:00:00Z as the layout says. Instants are compared at
   whole seconds: milliseconds are dropped (truncated toward the past), never rounded.
4. A calendar date used as an effective date (link catalog effective_from, calibration valid_from, service log
   date) takes effect at 00:00:00 UTC of that date. The date of a run is the UTC date of its plateau start.
5. Workbook dates are serial day numbers. When xl/workbook.xml carries workbookPr date1904="1" (or true), serial n
   is 1904-01-01 plus n days; otherwise serial n is 1899-12-30 plus n days.

   Example: with date1904 set, serial 44000 is 2024-06-22; without it, 44000 is 2020-06-19.

## H5 Reading identity, revisions and voids

1. A reading's key is (final serial, instant at whole seconds). Tokens are resolved first (H6); a record whose
   token cannot be resolved is counted as unresolved and takes no part in deduplication.
2. Among the copies of one key, the copy with the highest rev wins. Equal rev: the copy in the shard with the later
   catalog order wins; within one shard, the later record in file order wins.
3. Voids are decided after the winner is chosen: when the winning copy is void, the key is removed. A void copy that
   loses to a higher-rev copy removes nothing.

   Example: copies of one key are (rev 1, void) in shard 2 and (rev 2, not void) in shard 1. The rev 2 copy wins
   and the reading stays. Removing every key that has any void copy first would wrongly drop it.

## H6 Sensor tokens

1. A serial token is canonicalised by upper-casing it, removing spaces, hyphens and underscores, and writing the
   leading letters, a hyphen and the digits: ls2210, LS 2210, LS_2210 and ls-2210 all become LS-2210.
2. A channel token names a DAQ unit and channel: D1C07, DAQ1-07, 1/07 and ch07@daq1 all mean D1C07. A channel is
   resolved with channel_map_history.db: the row whose [valid_from_utc, valid_to_utc) contains the reading instant
   (an empty valid_to_utc is open-ended) gives the serial. A channel with no such row is UNMAPPED_CHANNEL.
3. The serial (from either route) is then walked through sensor_relabel in the alias register: while a row has
   old_serial equal to the current serial, move to its new_serial. The walk ignores effective_utc and always runs
   to the end of the chain. The end of the chain is the final serial used by every other rule.

   Example: a reading carries QX-1111; the register holds QX-1111 -> RV-2222 and RV-2222 -> TM-3333. The final
   serial is TM-3333, even for readings taken before either relabel. One lookup would stop at RV-2222.
4. A final serial that is not listed in sensor_inventory.json is UNKNOWN_SENSOR.

## H7 Stage assignment

1. sensor_map_*.yaml gives, per final serial, a history of stage assignments with from_utc instants. The stage of a
   sensor for a run is the assignment in effect at the run's plateau start (latest from_utc at or before it).
2. Stage tokens are resolved through node_alias in the alias register (case-insensitive, trimmed). ST300, ST50 and
   ST4 are the measured stages. A sensor whose stage for the run is anything else takes no part in that run.

## H8 Units

1. Resistive raw values are in ohm; kohm is multiplied by 1000. Diode raw values are in volt; mV is divided by
   1000. Layouts that carry micro-units hold micro-ohm or micro-volt integers. All conversions are exact decimal
   arithmetic; never use binary floating point for a raw value.

## H9 Calibration

1. Calibration points come from the workbook sheet named by calibration_sheet: rows (serial, version, valid_from,
   point, raw, unit, T_K). A version applies from 00:00 UTC of its valid_from date; a reading uses the applicable
   version with the latest valid_from.
2. The family in sensor_inventory.json decides the interpolation space, never the serial prefix:
   PRT interpolates temperature linearly in resistance R; NTC interpolates temperature linearly in conductance 1/R;
   DIODE interpolates temperature linearly in voltage V. The temperature is found between the two neighbouring
   points of the table in that space. A raw value outside the closed range spanned by the table is OUT_OF_RANGE.
3. A final serial with no applicable version uses the generic curve named by generic_curve in the inventory, from
   calibration_generic_curves.tsv, only when its cal_policy is GENERIC_OK. Otherwise its readings are
   NO_CALIBRATION.
4. The calibrated temperature is rounded to a whole mK (H22).

   Example (NTC): points (R 100 ohm, 10.000 K) and (R 50 ohm, 20.000 K). A reading of 80 ohm has conductance
   0.0125; the points have 0.01 and 0.02, so T = 10 + 10 * (0.0125 - 0.01) / 0.01 = 12.500 K = 12500 mK.
   Interpolating in resistance would give 14.000 K.

## H10 Reading screens

1. Each deduplicated reading of an in-scope, not aborted run is screened in this order and stops at the first
   reason that applies: INVALID_VALUE (the layout's missing-value sentinel or an empty value), OUT_OF_WINDOW,
   MAINTENANCE, EXCLUDED_SENSOR, NO_CALIBRATION, OUT_OF_RANGE. Readings that pass all of them are window readings.
   Unresolved records count as UNMAPPED_CHANNEL or UNKNOWN_SENSOR and are reported under their run.
2. MAINTENANCE: the reading instant lies in [start_utc, end_utc) of a maintenance block of the site calendar whose
   scope is ALL or names the sensor's stage for the run. A scope other than ALL is a stage token and resolves
   through node_alias exactly as in H7.2 (shell, for example, names ST300).
3. Rulings come from memo Table R-1. The ruling addendum is applied to them in ascending seq order: an ISSUED
   RESCIND sets the ruling to RESCINDED, an ISSUED REINSTATE sets it to IN FORCE; DRAFT entries are ignored. Only
   rulings IN FORCE after the addendum apply. EXCLUDE_SENSOR removes the sensor from that run (EXCLUDED_SENSOR).
   OFFSET_SENSOR adds its value in mK to every calibrated reading of that sensor in that run, before H11.
   EXCLUDE_LINK takes the link out of that run (H14.4).
4. Readings of runs that are aborted take no part and are not reported.

## H11 Sensor means

1. For each (run, final serial), take the window readings. Compute their median exactly (an even count takes the
   mean of the two middle values). A reading whose distance from the median is greater than spike_mK is a SPIKE
   and is dropped; a distance equal to spike_mK is kept.
2. When fewer than min_readings readings remain, the sensor has no mean for the run (status SPARSE, or NO_READINGS
   when none remain). Otherwise the sensor mean is the mean of the remaining readings, rounded to a whole mK.

## H12 Stage temperatures

1. For each (run, measured stage), take the sensors assigned to the stage for the run that have a mean. Compute
   the median of their means exactly; a sensor whose mean is farther than outlier_mK from that median is dropped
   as an outlier (equal is kept). The stage temperature is the mean of the remaining sensor means, rounded to a
   whole mK. A stage with no sensor mean is NO_SENSORS.

## H13 Effective settings

1. The profile gives spike_mK, outlier_mK, min_readings and reserve_pct globally; a per-run entry in the profile's
   runs list overrides a global value for that run.
2. A site overlay applies only when its base_revision equals the profile's profile_revision. It then overrides, per
   run, only the keys it lists under overridable_keys; any other key in it is ignored. An overlay with another
   base_revision is ignored entirely.

## H14 Links

1. Link tokens: TL-031, tl31, TL 031 and TL031 all mean TL-031. Each token is then walked through link_alias in the
   alias register to the end of the chain (old_id -> new_id), like H6.3.
2. The revision of a link that a run uses is the catalog row of the final link id with the latest effective_from
   on or before the run's date (H4.4); equal effective_from takes the higher rev. When that revision has status
   VOID the link is scrapped for the run (status NO_GEOMETRY).
3. Installs: the latest rev of each (run, final link id) is effective; state INSTALLED puts the link in the run,
   REMOVED takes it out. Hot and cold node tokens resolve through node_alias; intercept ids stand for themselves.
4. A link taken out by an EXCLUDE_LINK ruling has status EXCLUDED; it is not solved and carries no load.

## H15 Amendments

1. Amendment entries target (final link id, rev, field). Action and status words are case-insensitive. Entries are
   settled from the highest seq down: an entry is in effect when its status is POSTED and no in-effect REVERSE
   names it; a REVERSE in effect cancels the entry its reverses field names.
2. A field's value is the value of its highest-seq in-effect SET entry; with none, the link file value stands.
   Fields: segN.length_mm, segN.area (an area spec), segN.material, jointP.bolts, jointP.torque, jointP.indium.

   Example: SET 101 = 40.0, SET 105 = 42.0, REVERSE 107 of 105, REVERSE 110 of 107. 110 is in effect and cancels
   107, so 105 is not cancelled: the value is 42.0. Skipping REVERSE entries also gives 42.0 here, but drops 40.0
   wrongly when 107 alone exists.

## H16 Geometry

1. Lengths are in mm; cm multiplies by 10 and in by 25.4 exactly.
2. Area specs: A:12.50mm2 is 12.50 mm2; A:0.1250cm2 is 12.50 mm2; R:6.0x2.5mm is a rectangle of 15.00 mm2;
   W:24x32AWG is 24 conductors of gauge 32, each with the area of memo Table W-1.
3. Materials resolve through material_alias (case-insensitive, trimmed, ACTIVE rows only, followed to the end of the
   chain) to a material code of the conductivity sheet.
4. A lot scale multiplies the conductivity of a segment when the lot certificate has status CERTIFIED and the
   segment's material is listed in the lot_scale_materials constant of the solver contract table (IN FORCE).
   Otherwise the scale is 1.
5. The geometry factor of a segment is G = area_mm2 / length_mm (in mm), kept exact.

## H17 Conductivity

1. The conductivity sheet holds rows (material, T_K, k, unit). W/m-K is used as is; mW/cm-K is multiplied by 0.1.
2. k(T) is linear between neighbouring tabulated temperatures and constant beyond the first and last points.
3. The conductivity integral is theta(T) = integral of k from 0 to T, with T in mK, so a segment carries
   q_uW = scale * G * (theta(T_a) - theta(T_b)) between end temperatures T_a > T_b. theta is piecewise quadratic and
   is evaluated exactly.

   Example: k = 2 W/m-K at 10 K and 4 W/m-K at 20 K; from 10000 mK to 15000 mK the integral is
   5000 * (2 + 3) / 2 = 12500, so a segment with G = 0.4 mm carries 5000 uW.

## H18 Joint conductance

1. The band of a link is the band of its cold node: ST50 gives W, ST4 gives C, an intercept gives its own band from
   the intercept register.
2. h_eff = h_base(class, band) from the joint table (IN FORCE) * bolts * low_torque_factor when torque is LOW *
   indium_factor when indium is set and the class starts with BOLT_. h_eff is then rounded to the h increment of the
   solver contract table (IN FORCE), half-even.

## H19 Link march and heat flow

1. The elements of a link, hot end first, are: joint 0, segment 1, joint 1, segment 2, ..., segment n, joint n.
   Joint positions that are not listed are skipped.
2. The march for a trial heat flow q (whole uW) starts at the hot node temperature. A segment moves T to the
   temperature T' with theta(T') = theta(T) - q / (scale * G), rounded to a whole mK. A joint moves T to
   T - q / h_eff, where q / h_eff is in mK and is rounded to a whole mK before it is subtracted. A march whose
   theta target falls below theta(0), or whose temperature falls below 0, has failed.
3. The heat flow of the link is the largest whole q for which the march does not fail and ends at or above the
   cold node temperature. The junction temperatures are the march temperatures for that q.
4. A link whose hot node is not warmer than its cold node has q = 0 and status NO_GRADIENT. A link with a node
   that has no temperature is UNSOLVED.

   Example: hot 10000 mK, one segment with G = 0.4 mm and k as in H17, cold 9000 mK. q = 0.4 * (theta(10000) -
   theta(9000)) = 0.4 * 2000 = 800 uW when nothing is rounded. Rounding each element to a whole mK and taking the
   largest q that still ends at or above 9000 mK is the contract, not a solve that rounds once at the end.

## H20 Intercepts

1. An intercept is a floating node. For a trial temperature T (whole mK), f(T) = sum of q of the links whose cold
   node is the intercept + harness dissipation at the intercept - sum of q of the links whose hot node is the
   intercept, with every q from H19 at that T.
2. T_lo is the warmest cold-side node temperature and T_hi the coldest hot-side node temperature. The intercept
   temperature is the largest whole T in [T_lo, T_hi] with f(T) >= 0 (status BALANCED). When f(T_hi) >= 0 the
   intercept sits at T_hi (status CEILING). When f(T_lo) < 0 it sits at T_lo (status FLOOR).
3. The nominal_K of the intercept register is a design value and is never the intercept temperature.

## H21 Loads, capacity, margins and verdicts

1. Harness dissipation: the bundle rows of harness_dissipation.psv (latest rev per bundle, voids removed); the node
   of a bundle is the node the intercept register assigns to it for the run; node_hint is stale and not used.
2. The load of ST50 or ST4 is the sum of q of the links whose cold node is the stage, plus the harness dissipation
   at the stage, plus the parasitic load of the run's shield configuration from the parasitic table (IN FORCE).
3. Capacity: the run's cooler (profile) gives a model through its serial (CC-0417 is GM-K15, CC-0522 is PT-K41);
   the capacity sheet gives (model, stage, T_K, capacity_W) points, linear in T and held at the end values outside
   the map (map status OUT_OF_MAP). The derate of the cooler on the run's date is the value of the latest DERATE or
   RESTORE entry of the cooler service log on or before that date (RESTORE means 0). capacity_uW =
   capacity_W * 1000000 * (100 - derate_pct) / 100, rounded once to a whole uW.
4. reserve_uW = capacity_uW * reserve_pct / 100 rounded to a whole uW; margin_uW = capacity_uW - load_uW.
5. Stage verdict: OVER_TEMP when the stage temperature exceeds the limit of Table L-1, else OVERLOAD when the margin
   is negative, else MARGINAL when the margin is below the reserve, else PASS. Equal to the reserve is PASS.
6. Run verdict: INCOMPLETE when any link of the run is UNSOLVED or any measured stage is NO_SENSORS; otherwise the
   most severe stage verdict in the order OVER_TEMP, OVERLOAD, MARGINAL, PASS.

## H22 Rounding

1. Every rounding in this handbook is round half to even, to the stated unit, at the stated step, and the rounded
   value is what the next step consumes: calibrated readings (whole mK), sensor means (whole mK), stage
   temperatures (whole mK), h_eff (h increment), every march element (whole mK), capacity and reserve (whole uW).
   Carrying full precision and rounding once at the end is a different and wrong result.

   Example: 2.5 rounds to 2, 3.5 to 4, -2.5 to -2.

## H23 Reported numbers

1. Decimal outputs are written in plain decimal notation, never with an exponent. The output contract states the
   places of every decimal field.

## H24 Authority audit

1. Every value quoted by a lower-authority source is compared with the governing value: a conductivity at a
   temperature (the governing k(T) rounded half-even to as many decimal places as the quoted text has), a joint
   base conductance, a gauge area, a parasitic load, a solver constant, a stage temperature, or a per-run overlay
   setting. Equal is AGREE, anything else DISAGREE.

## H25 Published comparison

1. The published budget is compared link by link (published q in mW, three places, is exactly 1000 times the uW
   value) and the published stage margins stage by stage, as the output contract lays out.
"""
# --------------------------------------------------------------------------- generator: feed layouts and output contract
_GLAYOUT_DOC = """# Feed layouts

Every reading shard carries canonical fields run token, sensor or channel token, instant, raw value, unit, rev and
void, written differently per layout. The catalog (ingest_catalog_*.json) names the layout of each file. Tokens
are resolved as the handbook says (H3, H6, H14). Unless stated otherwise a field is text and an empty field is
missing.

## Reading layouts

### L01 (csv, comma)
- header: run,sensor,ts_utc,raw,unit,rev,void
- ts_utc: ISO 8601 with Z. unit: ohm, kohm, V or mV.
- void: Y marks a void copy; empty otherwise. Missing value sentinel: NaN.

### L02 (tsv)
- header: RUN SERIAL EPOCH_S VALUE UNITS REVISION STATUS (tab separated)
- EPOCH_S: epoch seconds. UNITS: OHM, KOHM, VOLT or MVOLT.
- STATUS: VOID marks a void copy, VALID otherwise. Missing value sentinel: -9999.

### L03 (psv, pipe)
- header: run_tag|chan|local_time|isdst|reading|rev|flag
- chan: a channel token (resolved through the channel map at the reading instant).
- local_time: site wall time written DD/MM/YYYY HH:MM:SS; isdst as in handbook H4.2.
- reading: in the family's native unit, ohm for PRT and NTC, volt for DIODE.
- flag: x marks a void copy. Missing value sentinel: OVL.

### L04 (jsonl)
- keys: r (run), s (serial), t_ms (epoch milliseconds), v (raw as a string, null when missing), u (unit),
  rv (rev), del (true for a void copy).

### L05 (ndjson)
- keys: meta.run, meta.rev, sensor, at (ISO 8601 with the site offset), value.x (raw string), value.unit,
  void (1 for a void copy). Missing value sentinel: ERR.

### L06 (xml)
- readings/batch elements carry the run token; each r element carries s, t (ISO 8601 with Z), raw, u, rev and
  void (true or false). An empty raw is missing.

### L07 (sqlite)
- table readings(run, sensor, epoch, raw, unit, rev, voided). epoch is seconds; raw is TEXT; voided 1 marks a void
  copy; a NULL raw is missing.

### L08 (db, sqlite)
- table frames(frame_id, run, epoch_ms, rev, void) and table samples(frame_id, channel, micro).
- A sample belongs to its frame: the frame gives run, instant (epoch milliseconds), rev and void.
- channel is a channel token. micro is an integer in micro-ohm for PRT and NTC, micro-volt for DIODE; NULL is
  missing.

### L09 (yaml)
- a list of records with keys run, sensor, at (epoch seconds), raw (quoted string, null when missing), unit, rev,
  void (yes for a void copy, no otherwise).

### L10 (yml)
- a mapping from sensor token to a block with unit (one unit for the whole block) and samples, a list of strings
  "run | instant (ISO 8601 with Z) | raw | rev | void" where void is 1 for a void copy. A raw of - is missing.

### L11 (json)
- one document: units maps each sensor token to its unit; data holds parallel arrays run, sensor, t (ISO 8601 with
  the site offset), raw, rev and void (true for a void copy). An empty raw is missing.

### L12 (txt, fixed width)
- lines starting with # are comments; the header line RUN SENSOR UTC RAW REV V repeats every 50 records.
- columns: run (10 characters), sensor (11), UTC instant written YYYYMMDDTHHMMSSZ (17), raw with a unit suffix
  (15: R ohm, K kohm, V volt, M millivolt), rev (4), void flag (Y or N).
- Missing value sentinel: *****.

### L13 (md)
- one section per run (## Run <token>) with pipe tables | sensor | utc | raw | unit | rev | void |; long tables
  continue after a (continued) line with a repeated header. utc is YYYY-MM-DD HH:MM:SS in UTC. raw carries thousands
  separators (1,234.5678). void reads void for a void copy and is empty otherwise. Missing value sentinel: n/a.

### L14 (csv, semicolon)
- header: run;probe;time_local;isdst;value;unit;rev;cancelled
- time_local: site wall time YYYY-MM-DD HH:MM:SS with isdst as in H4.2. value uses a decimal comma (123,4567).
- cancelled: 1 marks a void copy. An empty value is missing.

### L15 (tsv)
- header: ch epoch_ms run val unit rev void
- ch: a channel token; epoch_ms: epoch milliseconds; val in kohm for PRT and NTC and in mV for DIODE.
- void: 1 marks a void copy. Missing value sentinel: NA.

### L16 (jsonl, blocks)
- one block per line: run, sensor, rev, t0 (ISO 8601 with Z), unit, dt (seconds after t0, one per sample),
  v (raw strings, null when missing) and void (the zero-based indices of void samples in the block).

## Link files

### S0 link catalog (csv)
- header: link,rev,effective_from,kind,status,description. effective_from is a date. status ACTIVE or VOID.

### S1 segments (xml)
- link elements (id, rev) hold seg elements: n (sequence from the hot end), mat (material token), len (with mm),
  area (an area spec, handbook H16.2) and lot (empty when none).

### S2 segments (psv)
- header: link|rev|seq|material|length|length_unit|area_spec|lot. length_unit mm, cm or in. lot - means none.

### J1 joints (jsonl)
- keys: link, rev, pos (0 is the hot end, n the cold end after segment n), class, bolts, torque (NOM or LOW, any
  case), indium (true, false, yes or no).

### I1 installs (tsv)
- header: run link hot cold state rev. state INSTALLED or REMOVED.

### A1 amendments (ndjson)
- keys: seq, link, rev, field, value, action (SET or REVERSE, any case), status (POSTED or PENDING, any case),
  reverses (the seq a REVERSE names), entered.

## Other files

### run log (csv)
- header: run,event,local_time,value,rev,entered_by. local_time is site wall time YYYY-MM-DD HH:MM.

### harness ledger (psv)
- header: bundle|run|node_hint|dissipation|unit|rev|void. unit mW (three places) or uW. void VOID marks a void row.

### intercept register (xml)
- intercept elements (id, run, band W or C, nominal_K) and bundle elements (id, run, node).

### lot certificates (xml)
- lot elements (id, k_scale, status CERTIFIED, PROVISIONAL or WITHDRAWN, issued).

### ruling addendum (xml)
- entry elements (seq, ref, action RESCIND or REINSTATE, status ISSUED or DRAFT).

### cooler service log (tsv)
- header: date cooler action value by. DERATE carries a percentage value; RESTORE carries none.

### channel map (db, sqlite)
- table channel_assignment(channel, serial, valid_from_utc, valid_to_utc); NULL valid_to_utc is open-ended.

### alias register (sqlite)
- tables material_alias(token, target, status), node_alias(token, node), link_alias(old_id, new_id, effective),
  sensor_relabel(old_serial, new_serial, effective_utc).

### sensor inventory (json), sensor map (yaml), campaign profile (yml), overlays (yaml), site calendar (yml)
- as written; keys are self-describing. Profile run entries are a list of mappings with an id key.

### workbook (xlsx)
- sheet names live in xl/workbook.xml and are bound to worksheet parts through xl/_rels/workbook.xml.rels; the part
  file names do not follow the sheet order. Cells are shared strings, inline strings or numbers, and a numeric value
  may be stored as text. The first row of each data sheet is its header.

### memo (pdf)
- Flate-compressed content streams; every cell is a separately positioned text object (Tm) and the objects of a page
  are not in reading order. Strings are literal, hexadecimal or TJ arrays. A row is the set of objects sharing a y
  coordinate, ordered by x. A table continues on the next page after a (continued) line that repeats its header.
"""


_GCONTRACT_FILES = [
    ("sensor_means.tsv", "run, serial, stage, window_readings, spikes_dropped, used_readings, mean_mK, status"),
    ("stage_temperatures.csv", "run, stage, sensors_used, sensors_dropped, temperature_mK, status"),
    ("intercept_solutions.json", "object"),
    ("link_heat_flows.psv", "run, link, rev, hot_node, cold_node, hot_mK, cold_mK, q_uW, status"),
    ("junction_profiles.jsonl", "objects"),
    ("link_geometry.csv", "run, link, rev, seq, material, length_mm, area_mm2, lot, lot_scale, g_mm"),
    ("joint_conductances.tsv", "run, link, pos, class, band, bolts, torque, indium, h_base_mW_per_K, h_eff_mW_per_K"),
    ("stage_loads.csv", "run, stage, links_uW, harness_uW, parasitic_uW, total_uW, status"),
    ("cooler_margins.xml", "xml"),
    ("run_verdicts.json", "object"),
    ("alias_resolution.csv", "kind, token, resolved"),
    ("reading_exclusions.jsonl", "objects"),
    ("dedup_report.json", "object"),
    ("source_lineage.json", "object"),
    ("amendment_ledger.csv", "seq, link, rev, field, action, status, in_effect"),
    ("parameters_used.yaml", "yaml"),
    ("authority_audit.csv", "source, item, quoted, in_force, verdict"),
    ("variance_vs_published.csv", "run, link, published_uW, recomputed_uW, delta_uW, status"),
    ("reconciliation.md", "md"),
    ("budget_summary.md", "md"),
    ("manifest.json", "object"),
]


_GCONTRACT = """# Output contract

All reports are UTF-8 text with LF line endings and a final newline. Delimited reports (csv comma, tsv tab, psv
pipe) start with the header line given here, quote a cell only when the delimiter forces it, and leave a missing
value empty. JSON reports are one document; JSON Lines reports carry one object per line with keys in sorted order.
Integers are written without a decimal point. Run order is the order of the profile's runs list; stage order is
ST300, ST50, ST4; links sort by their final id; serials, tokens and other text sort by plain code-point order.
An aborted run has no rows in sensor_means.tsv, stage_temperatures.csv, intercept_solutions.json,
link_heat_flows.psv, junction_profiles.jsonl, link_geometry.csv, joint_conductances.tsv, stage_loads.csv,
cooler_margins.xml, reading_exclusions.jsonl or the runs of parameters_used.yaml. It keeps a row wherever a report
is laid out per profile run or per published or quoted item: run_verdicts.json and budget_summary.md (verdict
ABORTED), variance_vs_published.csv (its published links), reconciliation.md (its published stages) and
authority_audit.csv (every value a lower-authority source quotes for it).
Spaces around a markdown table cell or around a YAML value carry no meaning; the order, text, keys and nesting of
those lines do.

## sensor_means.tsv
- header: run	serial	stage	window_readings	spikes_dropped	used_readings	mean_mK	status
- one row per (run, final serial) with at least one deduplicated reading of the run that resolved to an inventory
  serial whose stage for the run is a measured stage; sorted by run, stage, serial.
- window_readings: readings that passed every screen of H10.1; spikes_dropped: SPIKE readings of H11;
  used_readings = window_readings - spikes_dropped.
- mean_mK: the sensor mean (H11), empty unless status is OK. status: OK, SPARSE or NO_READINGS.

## stage_temperatures.csv
- header: run,stage,sensors_used,sensors_dropped,temperature_mK,status
- one row per run and measured stage, sorted by run then stage order.
- sensors_used: serials whose means formed the temperature, sorted and joined with ;. sensors_dropped: outliers of
  H12, sorted and joined with ;. temperature_mK empty when status is NO_SENSORS; status OK or NO_SENSORS.

## intercept_solutions.json
- {"count": n, "intercepts": [...]} with one object per intercept of a run, sorted by run then node, keys:
  run, node, band, t_lo_mK, t_hi_mK, temperature_mK, harness_uW, residual_uW (f at the temperature),
  next_residual_uW (f one mK warmer, null when the temperature is t_hi_mK), links_in, links_out (final link ids,
  sorted), status (BALANCED, CEILING, FLOOR or UNSOLVED; an UNSOLVED intercept has null temperatures and residuals).

## link_heat_flows.psv
- header: run|link|rev|hot_node|cold_node|hot_mK|cold_mK|q_uW|status
- one row per installed link of a run, sorted by run then link. rev is the revision in use (empty when none).
  q_uW is empty unless status is OK or NO_GRADIENT. status: OK, NO_GRADIENT, UNSOLVED, NO_GEOMETRY or EXCLUDED.

## junction_profiles.jsonl
- one object per link row with status OK or NO_GRADIENT, sorted by run then link, keys: run, link, q_uW,
  elements. elements lists the march elements in order (H19.1); a joint element has kind joint, pos and t_mK; a
  segment element has kind segment, seq and t_mK; t_mK is the temperature after the element.

## link_geometry.csv
- header: run,link,rev,seq,material,length_mm,area_mm2,lot,lot_scale,g_mm
- one row per segment of each link row whose status is OK, NO_GRADIENT or UNSOLVED, sorted by run, link, seq.
- material is the material code; length_mm and area_mm2 are exact decimals with trailing zeros removed; lot is
  empty when none; lot_scale is the applied scale with trailing zeros removed (1 when none applies); g_mm is
  area/length rounded half-even to 9 places.

## joint_conductances.tsv
- header: run	link	pos	class	band	bolts	torque	indium	h_base_mW_per_K	h_eff_mW_per_K
- one row per joint of the same link rows as link_geometry.csv, sorted by run, link, pos. torque NOM or LOW;
  indium Y or N; both conductances with trailing zeros removed.

## stage_loads.csv
- header: run,stage,links_uW,harness_uW,parasitic_uW,total_uW,status
- one row per run for ST50 and ST4. status INCOMPLETE when a link loading the stage is UNSOLVED (links_uW and
  total_uW are then empty), OK otherwise.

## cooler_margins.xml
- root element margins with attribute campaign; one stage element per row of stage_loads.csv in the same order,
  with attributes in this order: run, name, cooler, model, temperature_mK, derate_pct, capacity_uW, map_status,
  load_uW, reserve_pct, reserve_uW, margin_uW, verdict. derate_pct has trailing zeros removed. Values that cannot be
  computed are empty strings and the verdict is INCOMPLETE. Two-space indentation, one element per line, an XML
  declaration with version 1.0 and encoding UTF-8.

## run_verdicts.json
- {"campaign": c, "runs": [...], "summary": {verdict: count}} with one object per profile run in run order, keys run,
  verdict, ST50, ST4 (stage verdicts, null for aborted runs) and unsolved_links (count). summary counts the run
  verdicts, keys sorted.

## alias_resolution.csv
- header: kind,token,resolved
- one row per distinct trimmed token of kind material (segment files), node (installs, sensor map, intercept register
  bundles), link (link files and installs) and sensor (serial tokens of the reading shards, after H6.1), sorted by
  kind then token. resolved is the canonical value after the alias walk, or UNRESOLVED.

## reading_exclusions.jsonl
- one object per (run, serial, reason) with a non-zero count, keys count, reason, run, serial; serial is the final
  serial, the canonical channel id for UNMAPPED_CHANNEL, or the canonical token for UNKNOWN_SENSOR. Sorted by run,
  serial, reason. Reasons: UNMAPPED_CHANNEL, UNKNOWN_SENSOR, INVALID_VALUE, OUT_OF_WINDOW, MAINTENANCE,
  EXCLUDED_SENSOR, NO_CALIBRATION, OUT_OF_RANGE, SPIKE.

## dedup_report.json
- keys: records_read (records in the catalogued reading shards), unresolved, copies_superseded (resolved records
  that lost to another copy of their key), voided_keys (keys removed because the winner is void), unique_readings
  (keys left), out_of_scope_readings (unique readings of runs that are not in scope or are aborted, or whose run
  token names another campaign).

## source_lineage.json
- {"shards": [...]} in catalog order, one object per read reading shard with keys file, layout, records, resolved
  and winning (records whose copy won and was not void).

## amendment_ledger.csv
- header: seq,link,rev,field,action,status,in_effect
- one row per amendment entry, sorted by seq. link is the final id; action and status upper-cased; in_effect Y or N.

## parameters_used.yaml
- keys in this order, two-space indentation, strings in single quotes only where written so below:
  campaign, profile_revision, overlay_applied (true or false), sheets (conductivity, calibration, capacity),
  memo_tables (joint, parasitic, solver, gauge, limits: the table labels applied), constants
  (h_increment_mW_per_K, indium_factor, low_torque_factor, lot_scale_materials: quoted strings as printed in the
  memo), limits_mK (ST50, ST4), runs (a mapping keyed by run id, one entry per non-aborted run in run order, each
  holding spike_mK, outlier_mK, min_readings, reserve_pct_ST50, reserve_pct_ST4, shield, cooler and derate_pct as a
  quoted string).
- layout, shown with made-up values (one run only):

```yaml
campaign: DEMO-01
profile_revision: 3
overlay_applied: false
sheets:
  conductivity: SHEET_K
  calibration: SHEET_C
  capacity: SHEET_P
memo_tables:
  joint: X-1
  parasitic: X-2
  solver: X-3
  gauge: X-4
  limits: X-5
constants:
  h_increment_mW_per_K: '0.5'
  indium_factor: '1.10'
  low_torque_factor: '0.90'
  lot_scale_materials: 'MAT_A MAT_B'
limits_mK:
  ST50: 70000
  ST4: 5000
runs:
  DEMO-R01:
    spike_mK: 20
    outlier_mK: 80
    min_readings: 5
    reserve_pct_ST50: 10
    reserve_pct_ST4: 10
    shield: SC-X
    cooler: CC-0000
    derate_pct: '2.5'
```

## authority_audit.csv
- header: source,item,quoted,in_force,verdict
- one row per audited value (H24), sorted by source then item. Items: conductivity_cache.jsonl, quick_reference
  and materials_legacy rows use MATERIAL@T_K (material code, T_K as quoted); daq_dashboard_export.csv uses RUN/STAGE;
  bulletin, draft handbook and solve pack constants use their key as printed (JOINT class/band, AWG gauge,
  PARASITIC config/stage, FACTOR name); profile_overlay_lab.yaml uses RUN/key. in_force is written in the quoted
  value's unit and number of places; verdict AGREE or DISAGREE. A dashboard row of a run whose stage has no
  temperature (an aborted run included) has an empty in_force and verdict DISAGREE. A profile_overlay_lab.yaml row
  is audited for every key that is a per-run setting of H13 (spike_mK, outlier_mK, min_readings, reserve_pct_ST50,
  reserve_pct_ST4), aborted runs included, against the run's effective setting; other keys are not audited.

## variance_vs_published.csv
- header: run,link,published_uW,recomputed_uW,delta_uW,status
- one row per (run, final link id) present in the published budget or in link_heat_flows.psv with a q, sorted by run
  then link. delta_uW = recomputed - published. status MATCH, DIFFERENT, MISSING_PUBLISHED or MISSING_RECOMPUTED.

## reconciliation.md
- line 1: # Reconciliation with the published stage margins
- then a blank line, the table header | run | stage | published_verdict | recomputed_verdict | change |, the line
  |---|---|---|---|---|, and one row per published (run, stage) in run and stage order; recomputed_verdict is the
  stage verdict of cooler_margins.xml, or ABORTED for every stage of an aborted run; change is same when the two
  verdicts are equal and changed otherwise. Rows are written | KTC-R01 | ST50 | PASS | MARGINAL | changed |.
- then a blank line and the line: Changed verdicts: N of M.

## budget_summary.md
- line 1: # Heat-load budget summary
- then a blank line, | run | verdict | ST50_load_uW | ST50_margin_uW | ST4_load_uW | ST4_margin_uW |, the line
  |---|---|---|---|---|---|, one row per profile run in run order, written like the header with an empty cell where
  nothing was computed (an aborted run reads | KTC-R07 | ABORTED |  |  |  |  |), a blank line and the line:
  Runs passing: N of M, where M counts every profile run.

## manifest.json
- {"files": [...]} with one object per other report in the order of this contract, keys name, bytes, sha256.
"""
# --------------------------------------------------------------------------- generator: catalog, published budget, decoys
_GFIELD_MAPS = {
    "L01": [("run", "run_token"), ("sensor", "serial_token"), ("ts_utc", "instant_iso_z"), ("raw", "raw"), ("unit", "unit"), ("rev", "rev"), ("void", "void")],
    "L02": [("RUN", "run_token"), ("SERIAL", "serial_token"), ("EPOCH_S", "instant_epoch_s"), ("VALUE", "raw"), ("UNITS", "unit"), ("REVISION", "rev"),
            ("STATUS", "void")],
    "L03": [("run_tag", "run_token"), ("chan", "channel_token"), ("local_time", "instant_local_dmy"), ("isdst", "offset_selector"), ("reading", "raw_native"),
            ("rev", "rev"), ("flag", "void")],
    "L04": [("r", "run_token"), ("s", "serial_token"), ("t_ms", "instant_epoch_ms"), ("v", "raw"), ("u", "unit"), ("rv", "rev"), ("del", "void")],
    "L05": [("meta.run", "run_token"), ("meta.rev", "rev"), ("sensor", "serial_token"), ("at", "instant_iso_offset"), ("value.x", "raw"), ("value.unit", "unit"),
            ("void", "void")],
    "L06": [("batch@run", "run_token"), ("r@s", "serial_token"), ("r@t", "instant_iso_z"), ("r@raw", "raw"), ("r@u", "unit"), ("r@rev", "rev"), ("r@void", "void")],
    "L07": [("readings.run", "run_token"), ("readings.sensor", "serial_token"), ("readings.epoch", "instant_epoch_s"), ("readings.raw", "raw"),
            ("readings.unit", "unit"), ("readings.rev", "rev"), ("readings.voided", "void")],
    "L08": [("frames.run", "run_token"), ("frames.epoch_ms", "instant_epoch_ms"), ("frames.rev", "rev"), ("frames.void", "void"),
            ("samples.channel", "channel_token"), ("samples.micro", "raw_micro"), ("samples.frame_id", "frame_link")],
    "L09": [("run", "run_token"), ("sensor", "serial_token"), ("at", "instant_epoch_s"), ("raw", "raw"), ("unit", "unit"), ("rev", "rev"), ("void", "void")],
    "L10": [("<key>", "serial_token"), ("unit", "unit"), ("samples[0]", "run_token"), ("samples[1]", "instant_iso_z"), ("samples[2]", "raw"),
            ("samples[3]", "rev"), ("samples[4]", "void")],
    "L11": [("data.run", "run_token"), ("data.sensor", "serial_token"), ("data.t", "instant_iso_offset"), ("data.raw", "raw"), ("units[sensor]", "unit"),
            ("data.rev", "rev"), ("data.void", "void")],
    "L12": [("RUN", "run_token"), ("SENSOR", "serial_token"), ("UTC", "instant_compact_z"), ("RAW", "raw_with_suffix"), ("REV", "rev"), ("V", "void")],
    "L13": [("## Run", "run_token"), ("sensor", "serial_token"), ("utc", "instant_utc_space"), ("raw", "raw_thousands"), ("unit", "unit"), ("rev", "rev"),
            ("void", "void")],
    "L14": [("run", "run_token"), ("probe", "serial_token"), ("time_local", "instant_local_iso"), ("isdst", "offset_selector"), ("value", "raw_decimal_comma"),
            ("unit", "unit"), ("rev", "rev"), ("cancelled", "void")],
    "L15": [("ch", "channel_token"), ("epoch_ms", "instant_epoch_ms"), ("run", "run_token"), ("val", "raw_milli_kilo"), ("unit", "unit"), ("rev", "rev"),
            ("void", "void")],
    "L16": [("run", "run_token"), ("sensor", "serial_token"), ("rev", "rev"), ("t0", "block_start_iso_z"), ("dt", "offset_seconds"), ("v", "raw"),
            ("unit", "unit"), ("void", "void_indices")],
    "S0": [("link", "link_token"), ("rev", "rev"), ("effective_from", "date"), ("kind", "kind"), ("status", "status"), ("description", "text")],
    "S1": [("link@id", "link_token"), ("link@rev", "rev"), ("seg@n", "seq"), ("seg@mat", "material_token"), ("seg@len", "length_mm_suffix"),
           ("seg@area", "area_spec"), ("seg@lot", "lot")],
    "S2": [("link", "link_token"), ("rev", "rev"), ("seq", "seq"), ("material", "material_token"), ("length", "length"), ("length_unit", "length_unit"),
           ("area_spec", "area_spec"), ("lot", "lot")],
    "J1": [("link", "link_token"), ("rev", "rev"), ("pos", "joint_position"), ("class", "joint_class"), ("bolts", "bolts"), ("torque", "torque"),
           ("indium", "indium")],
    "I1": [("run", "run_token"), ("link", "link_token"), ("hot", "node_token"), ("cold", "node_token"), ("state", "state"), ("rev", "rev")],
    "A1": [("seq", "seq"), ("link", "link_token"), ("rev", "rev"), ("field", "field"), ("value", "value"), ("action", "action"), ("status", "status"),
           ("reverses", "target_seq"), ("entered", "instant_iso_z")],
}
_GVALUE_MAPS = {"L01": ("Y", "NaN"), "L02": ("VOID", "-9999"), "L03": ("x", "OVL"), "L04": ("true", "null"), "L05": ("1", "ERR"), "L06": ("true", "(empty)"),
                "L07": ("1", "NULL"), "L08": ("1", "NULL"), "L09": ("yes", "null"), "L10": ("1", "-"), "L11": ("true", "(empty)"), "L12": ("Y", "*****"),
                "L13": ("void", "n/a"), "L14": ("1", "(empty)"), "L15": ("1", "NA"), "L16": ("index listed in void", "null")}


def _Gwrite_catalog(rng: random.Random, W: dict, data: Path) -> None:
    shards = []
    order = 10
    entries = [(f, lay, "readings") for f, lay in _GSHARDS]
    entries.insert(rng.randint(3, 12), ("rd_x9old.csv", "L01", "readings"))
    for f, lay, kind in entries:
        order += rng.choice([10, 10, 20])
        shards.append({"order": order, "file": f, "layout": lay, "kind": kind, "status": "RETIRED" if f == "rd_x9old.csv" else "ACTIVE"})
    for f, lay, kind in _GLINK_FILES:
        order += 10
        shards.append({"order": order, "file": f, "layout": lay, "kind": kind, "status": "ACTIVE"})
    fmaps = []
    for lay in sorted(_GFIELD_MAPS):
        for src, can in _GFIELD_MAPS[lay]:
            fmaps.append({"layout": lay, "field": src, "canonical": can})
    vmaps = []
    for lay in sorted(_GVALUE_MAPS):
        v, m = _GVALUE_MAPS[lay]
        vmaps.append({"layout": lay, "void_marker": v, "missing_value": m})
    doc = {"campaign": W["cfg"]["campaign"], "catalog_revision": 4, "shards": shards, "field_maps": fmaps, "value_maps": vmaps}
    _Gwrite(data / "ingest_catalog_k26b.json", json.dumps(doc, indent=1) + "\n")


def _Gk_exact(pts: list[tuple[str, str]], T: Fraction) -> Fraction:
    xs = [(_Gfr(t), _Gfr(k)) for t, k in pts]
    if T <= xs[0][0]:
        return xs[0][1]
    for (t0, k0), (t1, k1) in zip(xs, xs[1:]):
        if t0 <= T <= t1:
            return k0 + (k1 - k0) * (T - t0) / (t1 - t0)
    return xs[-1][1]


def _Gwrite_published(rng: random.Random, W: dict, data: Path) -> None:  # noqa: C901
    cfg = W["cfg"]
    pubT: dict[tuple[str, str], int] = {}
    for r in W["runs"]:
        for st in ("ST300", "ST50", "ST4"):
            pubT[(r["id"], st)] = r["T"][st] + rng.randint(-90, 90) // (8 if st == "ST4" else 1)
    rows = []
    loads: dict[tuple[str, str], float] = {}
    for r in W["runs"]:
        nominal = {x["id"]: int(float(x["nominal"]) * 1000) for x in W["intercepts"][r["id"]]}
        for row in W["installs"][r["id"]]:
            L = W["links"][row["link"]]
            rv = L["revs"][0]
            th = pubT.get((r["id"], row["hot"]), nominal.get(row["hot"]))
            tc = pubT.get((r["id"], row["cold"]), nominal.get(row["cold"]))
            if not rv["segs"] or th is None or tc is None:
                continue
            res = 0.0
            for sg in rv["segs"]:
                G = _Garea_float(sg["area"], cfg["AWG"]) / float(sg["len"])
                res += 1.0 / (G * _Gk_float(W["k_old"][sg["mat"]], (th + tc) / 2000.0))
            q_uw = (th - tc) / res if th > tc else 0.0
            tok = row["link"] if rng.random() < 0.7 else _Glink_tok(row["link"], 1)
            rows.append([_Grun_tok(r["id"], 0), tok, row["hot"], row["cold"], f"{q_uw / 1000:.3f}", "mean-k"])
            if row["cold"] in ("ST50", "ST4"):
                loads[(r["id"], row["cold"])] = loads.get((r["id"], row["cold"]), 0.0) + q_uw
    for b in W["bundles"]:
        if b["hint"] in ("ST50", "ST4"):
            loads[(b["run"], b["hint"])] = loads.get((b["run"], b["hint"]), 0.0) + b["uw"]
    rng.shuffle(rows)
    _Gwrite(data / "heatload_budget_published.csv", _Gdelim(["run", "link", "hot", "cold", "q_mW", "method"], rows))
    recs = []
    for r in W["runs"]:
        model = _GCOOLERS[r["cooler"]]
        for st in ("ST50", "ST4"):
            pts = [(float(t), float(c) * 1.08) for t, c in cfg["cap"][(model, st)]]
            tk = pubT[(r["id"], st)] / 1000.0
            cap = pts[0][1] if tk <= pts[0][0] else pts[-1][1]
            for (t0, c0), (t1, c1) in zip(pts, pts[1:]):
                if t0 <= tk <= t1:
                    cap = c0 + (c1 - c0) * (tk - t0) / (t1 - t0)
            load = loads.get((r["id"], st), 0.0) + cfg["P1"][(r["shield"], st)]
            margin = cap * 1e6 - load
            res = cap * 1e6 * cfg["reserve"][st] / 100
            verdict = "OVERLOAD" if margin < 0 else ("MARGINAL" if margin < res else "PASS")
            if pubT[(r["id"], st)] > cfg["L1"][st] + 500:
                verdict = "OVER_TEMP"
            comps = [{"component": "links", "uW": round(loads.get((r["id"], st), 0.0))}, {"component": "parasitic", "uW": cfg["P1"][(r["shield"], st)]},
                     {"component": "capacity", "uW": round(cap * 1e6)}, {"component": "reserve", "uW": round(res)}]
            recs.append({"run": r["id"], "stage": st, "temperature_K": f"{pubT[(r['id'], st)] / 1000:.3f}", "components": comps,
                         "margin_mW": f"{margin / 1000:.3f}", "verdict": verdict})
    _Gwrite(data / "stage_margins_published.json", json.dumps({"campaign": cfg["campaign"], "method": "solve pack v2.3", "stages": recs}, indent=1) + "\n")
    W["pubT"] = pubT


def _Gwrite_decoys(rng: random.Random, W: dict, data: Path) -> None:  # noqa: C901
    cfg = W["cfg"]
    # conductivity cache (not in the catalog)
    lines = []
    for _ in range(240):
        mat = rng.choice(sorted(W["k_tables"]))
        T = Fraction(rng.randint(150, 32000), 100)
        src = "R2" if rng.random() < 0.6 else "R3"
        tab = W["k_old"] if src == "R2" else W["k_tables"]
        k = _Gk_exact(tab[mat], T)
        tok = mat if rng.random() < 0.6 else rng.choice(_GMAT_ALIASES[mat])
        lines.append(json.dumps({"mat": tok, "T_K": _Gq(T, 2), "k_W_per_mK": _Gq(k, 4), "sheet": cfg["sheets"]["k_old"] if src == "R2" else cfg["sheets"]["k"],
                                 "cached_at": _Gz(datetime.combine(cfg["start"], datetime.min.time(), _GUTC) + timedelta(minutes=rng.randint(0, 90000)))}))
    _Gwrite(data / "conductivity_cache.jsonl", "\n".join(lines) + "\n")
    # quick reference card
    out = ["KTC QUICK REFERENCE CARD - thermal conductivity, W/m-K (rounded)", "material      T_K     k", ""]
    for mat in sorted(W["k_tables"]):
        for t, k in W["k_tables"][mat][1:-1]:
            out.append(f"{mat:<13} {t:<7} {_Gsig(_Gfr(k), 2)}")
    out += ["", "Shortcut: q = k(T_mean) * A / L * dT (see solve pack step 6).", "Kelvin offset 273."]
    _Gwrite(data / "quick_reference_k26b.txt", "\n".join(out) + "\n")
    # legacy materials yaml
    out = ["# legacy conductivity tables (pre-KTC-26A)", "materials:"]
    for mat in sorted(W["k_old"]):
        out.append(f"  {mat}:")
        for t, k in W["k_old"][mat]:
            out.append(f"    - {{T_K: '{t}', k: '{k}'}}")
    _Gwrite(data / "materials_legacy.yaml", "\n".join(out) + "\n")
    # dashboard
    rows = []
    for r in W["runs"]:
        for st in ("ST300", "ST50", "ST4"):
            rows.append([r["id"], st, "ALL", _Gq(Fraction(W["pubT"][(r["id"], st)] + rng.randint(-30, 30), 1000), 3), _Gz(r["end"])])
        for s in W["sensors"]:
            st = _Gstage_at(s, r["start"])
            rows.append([r["id"], st, W["label_at"](s, r["end"]), _Gq(Fraction(r["T"][st] + rng.randint(-200, 200), 1000), 3), _Gz(r["end"])])
    _Gwrite(data / "daq_dashboard_export.csv", _Gdelim(["run", "stage", "sensor", "live_K", "updated_utc"], rows))
    # constants quoted by the bulletin, the draft handbook and the solve pack
    J_out = cfg["J1"]

    def consts(variant: int) -> list[tuple[str, str]]:
        c = []
        for (cls, band), v in sorted(cfg["J2"].items()):
            if variant == 0:
                val = J_out[(cls, band)]
            elif variant == 1:
                val = v if rng.random() < 0.5 else J_out[(cls, band)]
            else:
                val = _Gq(_Gfr(v) * Fraction(rng.choice([95, 100, 104]), 100), 1)
            c.append((f"JOINT {cls}/{band}", val))
        for g, a in sorted(cfg["AWG"].items()):
            c.append((f"AWG {g}", _GAWG_ROUGH[g] if variant != 1 else a))
        for (conf, st), v in sorted(cfg["P2"].items()):
            c.append((f"PARASITIC {conf}/{st}", str(cfg["P1"][(conf, st)] if variant != 2 else v)))
        S1, S2 = cfg["S1"], cfg["S2"]
        for k in ("h_increment_mW_per_K", "indium_factor", "low_torque_factor"):
            c.append((f"FACTOR {k}", S1[k] if variant != 1 else S2[k]))
        return c

    bul = [f"{cfg['campaign']} operations bulletin (circulated, not controlled)", ""]
    notes = ["cooldown nominal", "LN2 dewar swapped", "logger restart", "vacuum gauge recalibrated", "shift handover", "pressure spike cleared",
             "turbo pump service", "heater current checked", "DAQ firmware note", "cable tray inspected"]
    k = 100
    const_lines = [f"NOTICE {k + i:04d} | {key} | {val}" for i, (key, val) in enumerate(consts(0))]
    filler = []
    for i in range(190):
        d = cfg["start"] + timedelta(days=i // 3)
        filler.append(f"{d.isoformat()} OPS {rng.choice(notes)}")
    allb = filler + const_lines
    rng.shuffle(allb)
    bul += allb
    _Gwrite(data / "ops_bulletin_k26b.txt", "\n".join(bul) + "\n")
    # draft handbook
    draft = ["# Thermal heat-load budget handbook (revision 10, DRAFT for comment)", "",
             "Draft changes under review; not approved by the qualification board.", ""]
    for line in _GHANDBOOK.split("\n")[6:]:
        line = line.replace("interpolates temperature linearly in conductance 1/R", "interpolates temperature linearly in resistance R")
        line = line.replace("is greater than spike_mK", "is greater than spike_mK from the window mean")
        line = line.replace("is never the intercept temperature", "is used as the intercept temperature")
        draft.append(line)
    draft += ["", "## Draft constants", "", "| key | value |", "|---|---|"]
    draft += [f"| {key} | {val} |" for key, val in consts(1)]
    _Gwrite(data / "handbook_draft_r6.md", "\n".join(draft) + "\n")
    # solve pack as executed
    sp = ["# Heat-load budget solve pack v2.3 (as executed for the published budget)", "", "## Steps", "",
          "1. Load every file named rd_* in the data directory.", "2. Drop every reading key that has a void copy, then keep the highest rev.",
          "3. Window: readings from plateau start to plateau end inclusive.", "4. Calibrate with the latest calibration sheet in the workbook; NTC in resistance.",
          "5. Stage temperature: mean of all sensor readings; no spike or outlier screen.",
          f"6. Link heat flow: q = k(T_mean) * A / L * dT from {cfg['sheets']['k_old']}; joints ignored.",
          "7. Intercepts at their nominal_K.", "8. Loads: links plus harness by node_hint plus parasitic loads.",
          f"9. Capacity from {cfg['sheets']['cap_old']}; no service derates.", "", "## Constants as executed", "", "| key | value |", "|---|---|"]
    sp += [f"| {key} | {val} |" for key, val in consts(2)]
    sp += ["", "## Execution log", ""]
    for r in W["runs"]:
        for step in range(1, 10):
            sp.append(f"- {r['id']} step {step}: ok ({rng.randint(40, 900)} ms)")
    _Gwrite(data / "budget_solve_pack.md", "\n".join(sp) + "\n")
    # generic calibration curves
    rows = []
    variants = [("PRT-385", "PRT", 1.0), ("PRT-392", "PRT", 1.004), ("NTC-1", "NTC", 0.97), ("NTC-2", "NTC", 1.0), ("NTC-3", "NTC", 1.03),
                ("DIODE-10", "DIODE", 0.995), ("DIODE-11", "DIODE", 1.0), ("DIODE-12", "DIODE", 1.006)]
    for i, (name, fam, sc) in enumerate(variants):
        pts = W["generic"][fam] if sc == 1.0 else _Gcal_points(fam, random.Random(991 + i), sc)
        for j, (raw, tk) in enumerate(pts, 1):
            rows.append([name, fam, j, raw, "V" if fam == "DIODE" else "ohm", tk])
    _Gwrite(data / "calibration_generic_curves.tsv", _Gdelim(["curve", "family", "point", "raw", "unit", "T_K"], rows, "\t"))
# --------------------------------------------------------------------------- generator: documents and entry point
_GSTATUS_INDEX = [
    ("sensor_means status", "OK", "the sensor has a mean for the run (H11)"),
    ("sensor_means status", "SPARSE", "fewer than min_readings readings remained after the spike screen"),
    ("sensor_means status", "NO_READINGS", "no window reading remained"),
    ("stage status", "OK", "at least one sensor mean formed the stage temperature"),
    ("stage status", "NO_SENSORS", "no sensor mean was available for the stage"),
    ("link status", "OK", "solved by the march of H19"),
    ("link status", "NO_GRADIENT", "the hot node is not warmer than the cold node; q is 0"),
    ("link status", "UNSOLVED", "a node of the link has no temperature"),
    ("link status", "NO_GEOMETRY", "the revision in use is VOID or no revision applies"),
    ("link status", "EXCLUDED", "an EXCLUDE_LINK ruling is in force for the run"),
    ("intercept status", "BALANCED", "largest temperature with a non-negative balance"),
    ("intercept status", "CEILING", "the balance is non-negative at the coldest hot-side node"),
    ("intercept status", "FLOOR", "the balance is negative at the warmest cold-side node"),
    ("intercept status", "UNSOLVED", "a node attached to the intercept has no temperature"),
    ("map status", "IN_MAP", "the stage temperature lies within the capacity map"),
    ("map status", "OUT_OF_MAP", "the capacity was held at the end value of the map"),
    ("stage verdict", "PASS", "margin at or above the reserve and temperature within the limit"),
    ("stage verdict", "MARGINAL", "margin non-negative and below the reserve"),
    ("stage verdict", "OVERLOAD", "margin negative"),
    ("stage verdict", "OVER_TEMP", "stage temperature above the Table L-1 limit"),
    ("stage verdict", "INCOMPLETE", "the load or the capacity could not be computed"),
    ("run verdict", "ABORTED", "the run's effective ABORT entry is ACTIVE"),
    ("run verdict", "INCOMPLETE", "a link is UNSOLVED or a measured stage has no temperature"),
    ("exclusion reason", "UNMAPPED_CHANNEL", "no channel assignment covers the reading instant"),
    ("exclusion reason", "UNKNOWN_SENSOR", "the final serial is not in the inventory"),
    ("exclusion reason", "INVALID_VALUE", "missing-value sentinel or empty value"),
    ("exclusion reason", "OUT_OF_WINDOW", "outside [PLATEAU_START, PLATEAU_END)"),
    ("exclusion reason", "MAINTENANCE", "inside a maintenance block of the site calendar"),
    ("exclusion reason", "EXCLUDED_SENSOR", "an EXCLUDE_SENSOR ruling is in force"),
    ("exclusion reason", "NO_CALIBRATION", "no applicable calibration and no generic curve allowed"),
    ("exclusion reason", "OUT_OF_RANGE", "raw value outside the calibration table"),
    ("exclusion reason", "SPIKE", "farther than spike_mK from the window median"),
]


_GCONTRACT_KEYS = {
    "intercept_solutions.json": ["count", "intercepts", "run", "node", "band", "t_lo_mK", "t_hi_mK", "temperature_mK", "harness_uW", "residual_uW",
                                 "next_residual_uW", "links_in", "links_out", "status"],
    "junction_profiles.jsonl": ["elements", "link", "q_uW", "run", "kind", "pos", "seq", "t_mK"],
    "cooler_margins.xml": ["run", "name", "cooler", "model", "temperature_mK", "derate_pct", "capacity_uW", "map_status", "load_uW", "reserve_pct",
                           "reserve_uW", "margin_uW", "verdict"],
    "run_verdicts.json": ["campaign", "runs", "summary", "run", "verdict", "ST50", "ST4", "unsolved_links"],
    "reading_exclusions.jsonl": ["count", "reason", "run", "serial"],
    "dedup_report.json": ["records_read", "unresolved", "copies_superseded", "voided_keys", "unique_readings", "out_of_scope_readings"],
    "source_lineage.json": ["shards", "file", "layout", "records", "resolved", "winning"],
    "parameters_used.yaml": ["campaign", "profile_revision", "overlay_applied", "sheets", "memo_tables", "constants", "limits_mK", "runs"],
    "reconciliation.md": ["run", "stage", "published_verdict", "recomputed_verdict", "change"],
    "budget_summary.md": ["run", "verdict", "ST50_load_uW", "ST50_margin_uW", "ST4_load_uW", "ST4_margin_uW"],
    "manifest.json": ["files", "name", "bytes", "sha256"],
}


def _Gwrite_docs(W: dict, data: Path) -> None:
    hb = _GHANDBOOK.rstrip("\n").split("\n")
    hb += ["", "## Status and reason index", "", "| field | value | meaning |", "|---|---|---|"]
    hb += [f"| {a} | {b} | {c} |" for a, b, c in _GSTATUS_INDEX]
    _Gwrite(data / "thermal_budget_handbook.md", "\n".join(hb) + "\n")
    fl = _GLAYOUT_DOC.rstrip("\n").split("\n")
    fl += ["", "## Field dictionary", "", "| layout | source field | canonical field |", "|---|---|---|"]
    for lay in sorted(_GFIELD_MAPS):
        for src, can in _GFIELD_MAPS[lay]:
            fl.append(f"| {lay} | {src} | {can} |")
    _Gwrite(data / "feed_layouts.md", "\n".join(fl) + "\n")
    oc = _GCONTRACT.rstrip("\n").split("\n")
    oc += ["", "## Column dictionary", "", "| report | position | column |", "|---|---|---|"]
    for name, cols in _GCONTRACT_FILES:
        if "," in cols:
            for i, c in enumerate(cols.split(", "), 1):
                oc.append(f"| {name} | {i} | {c.strip()} |")
        else:
            for i, k in enumerate(_GCONTRACT_KEYS.get(name, []), 1):
                oc.append(f"| {name} | key {i} | {k} |")
    _Gwrite(data / "output_contract.md", "\n".join(oc) + "\n")


def _Gmerge(cfg: dict | None) -> dict:
    base = _Gdefaults()
    for k, v in (cfg or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict) and k not in ("cal",):
            nv = dict(base[k])
            nv.update(v)
            base[k] = nv
        else:
            base[k] = v
    return base


def _Ggenerate(data_dir: Path, seed: int, cfg: dict | None = None) -> None:
    rng = random.Random(seed)
    data_dir.mkdir(parents=True, exist_ok=True)
    for stale in data_dir.iterdir():
        if stale.is_file():
            stale.unlink()
    C = _Gmerge(cfg)
    W = _Gworld(rng, C)
    _Gnoise_links(rng, W)
    _Gstock_codes(rng, W)
    _Greadings(rng, W)
    _Gwrite_shards(rng, W, data_dir)
    _Gwrite_catalog(rng, W, data_dir)
    _Gwrite_links(rng, W, data_dir)
    _Gwrite_registers(rng, W, data_dir)
    _Gwrite_runs(rng, W, data_dir)
    _Gwrite_profile(rng, W, data_dir)
    _Gwrite_workbook(rng, W, data_dir)
    _Gwrite_memo(rng, W, data_dir)
    _Gwrite_published(rng, W, data_dir)
    _Gwrite_decoys(rng, W, data_dir)
    _Gwrite_docs(W, data_dir)
# =========================================================================== verifier: independent readers
_Z = timezone.utc
_XNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _q(s: Any) -> Fraction:
    return Fraction(str(s).strip())


def _rows(text: str, sep: str) -> list[dict[str, str]]:
    rd = csv.reader(io.StringIO(text), delimiter=sep)
    head = None
    out = []
    for r in rd:
        if head is None:
            head = [h.strip() for h in r]
            continue
        if r:
            out.append({h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(head)})
    return out


def _jl(path: Path) -> list:
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def _yval(s: str) -> Any:
    s = s.strip()
    if s[:1] in "'\"" and s[-1:] == s[:1] and len(s) > 1:
        return s[1:-1]
    if s in ("", "null", "~"):
        return None
    if s[:1] == "{" and s[-1:] == "}":
        d = {}
        for part in s[1:-1].split(","):
            a, _, b = part.partition(":")
            d[a.strip()] = _yval(b)
        return d
    return s


def _yaml(text: str) -> Any:
    toks = []
    for line in text.split("\n"):
        body = line.strip()
        if body and body[0] != "#":
            toks.append([len(line) - len(line.lstrip()), body])
    pos = [0]

    def node(ind: int) -> Any:
        if toks[pos[0]][1].startswith("- "):
            seq = []
            while pos[0] < len(toks) and toks[pos[0]][0] == ind and toks[pos[0]][1].startswith("- "):
                rest = toks[pos[0]][1][2:].strip()
                if re.match(r"^[\w.\-]+:( |$)", rest) and rest[:1] not in "'\"{":
                    toks[pos[0]] = [ind + 2, rest]
                    seq.append(node(ind + 2))
                else:
                    pos[0] += 1
                    seq.append(_yval(rest))
            return seq
        mp = {}
        while pos[0] < len(toks) and toks[pos[0]][0] == ind and not toks[pos[0]][1].startswith("- "):
            key, _, rest = toks[pos[0]][1].partition(":")
            pos[0] += 1
            if rest.strip():
                mp[key.strip()] = _yval(rest)
            elif pos[0] < len(toks) and (toks[pos[0]][0] > ind or (toks[pos[0]][0] == ind and toks[pos[0]][1].startswith("- "))):
                mp[key.strip()] = node(toks[pos[0]][0])
            else:
                mp[key.strip()] = None
        return mp

    return node(toks[0][0]) if toks else {}


_PTOK = re.compile(r"\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|-?\d+(?:\.\d+)?|[A-Za-z]+")


def _pstr(t: str) -> str:
    if t.startswith("<"):
        return bytes.fromhex(re.sub(r"\s", "", t[1:-1])).decode("latin-1")
    return re.sub(r"\\(.)", r"\1", t[1:-1])


def _pdf_lines(path: Path) -> list[list[str]]:
    raw = path.read_bytes()
    lines: list[list[str]] = []
    for m in re.finditer(rb"/Length (\d+) /Filter /FlateDecode >>\nstream\n", raw):
        text = zlib.decompress(raw[m.end():m.end() + int(m.group(1))]).decode("latin-1")
        cells: dict[float, list[tuple[float, str]]] = {}
        for line in text.split("\n"):
            if not (line.startswith("BT ") and line.endswith(" ET")):
                continue
            nums: list[float] = []
            x = y = 0.0
            parts: list[str] = []
            inarr = False
            for t in _PTOK.findall(line[3:-3]):
                if t == "Tm":
                    x, y = nums[-2], nums[-1]
                elif t == "[":
                    inarr = True
                elif t == "]":
                    inarr = False
                elif t[0] in "(<":
                    parts.append(_pstr(t))
                elif re.fullmatch(r"-?\d+(?:\.\d+)?", t) and not inarr:
                    nums.append(float(t))
            cells.setdefault(y, []).append((x, "".join(parts)))
        for y in sorted(cells, reverse=True):
            lines.append([c.strip() for _, c in sorted(cells[y])])
    return lines


def _memo(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    cur = None
    for cells in _pdf_lines(path):
        if len(cells) == 1:
            g = re.fullmatch(r"Table ([A-Z]+-\d+)(: (.*) \((IN FORCE|WITHDRAWN)\)| \(continued\))", cells[0])
            if g:
                if g.group(3) is not None:
                    cur = g.group(1)
                    out[cur] = {"title": g.group(3), "status": g.group(4), "head": None, "rows": [], "skip": False}
                else:
                    cur = g.group(1)
                    out[cur]["skip"] = True
                continue
            if cells[0] == "":
                cur = None
            continue
        if cur is None:
            continue
        t = out[cur]
        if t["head"] is None:
            t["head"] = cells
        elif t["skip"] and cells == t["head"]:
            t["skip"] = False
        else:
            t["rows"].append(dict(zip(t["head"], cells)))
    return out


def _book(path: Path) -> tuple[bool, dict[str, list[dict[str, str]]]]:
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    pr = wb.find(f"{_XNS}workbookPr")
    d1904 = pr is not None and pr.get("date1904") in ("1", "true")
    rel = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    sst = [("".join(t.text or "" for t in si.iter(f"{_XNS}t"))) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{_XNS}si")]
    sheets = {}
    for s in wb.iter(f"{_XNS}sheet"):
        part = "xl/" + rel[s.get(f"{_RNS}id")]
        grid = []
        for row in ET.fromstring(z.read(part)).iter(f"{_XNS}row"):
            vals = {}
            for c in row.iter(f"{_XNS}c"):
                col = 0
                for ch in re.match(r"[A-Z]+", c.get("r")).group(0):
                    col = col * 26 + ord(ch) - 64
                if c.get("t") == "s":
                    v = sst[int(c.find(f"{_XNS}v").text)]
                elif c.get("t") == "inlineStr":
                    v = "".join(t.text or "" for t in c.iter(f"{_XNS}t"))
                else:
                    v = c.find(f"{_XNS}v").text or ""
                vals[col] = v.strip()
            grid.append(vals)
        if not grid:
            sheets[s.get("name")] = []
            continue
        head = grid[0]
        sheets[s.get("name")] = [{head[k]: r.get(k, "") for k in head} for r in grid[1:] if r]
    return d1904, sheets


def _inst(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    d = datetime.fromisoformat(s.replace(" ", "T"))
    return (d if d.tzinfo else d.replace(tzinfo=_Z)).astimezone(_Z)


def _ep(sec: int) -> datetime:
    return datetime.fromtimestamp(sec, _Z)


def _mins(s: str) -> int:
    sign = -1 if s.strip()[0] == "-" else 1
    h, m = s.strip()[1:].split(":")
    return sign * (int(h) * 60 + int(m))


def _cal(root: Path) -> dict:
    y = _yaml((root / "site_calendar.yml").read_text(encoding="utf-8"))
    return {"base": _mins(y["base_offset"]), "tr": sorted((_inst(t["at_utc"]), _mins(t["offset_after"])) for t in (y.get("transitions") or [])),
            "maint": [(_inst(m["start_utc"]), _inst(m["end_utc"]), m["scope"]) for m in (y.get("maintenance") or [])]}


def _off(u: datetime, cal: dict) -> int:
    o = cal["base"]
    for at, x in cal["tr"]:
        if u >= at:
            o = x
    return o


def _wall2utc(w: datetime, cal: dict) -> datetime:
    offs = sorted({cal["base"]} | {o for _, o in cal["tr"]})
    good = [(w - timedelta(minutes=o)).replace(tzinfo=_Z) for o in offs if _off((w - timedelta(minutes=o)).replace(tzinfo=_Z), cal) == o]
    if good:
        return min(good)
    prev = cal["base"]
    for at, o in cal["tr"]:
        a = (w - timedelta(minutes=prev)).replace(tzinfo=_Z)
        if a >= at > (w - timedelta(minutes=o)).replace(tzinfo=_Z):
            return a
        prev = o
    raise ValueError(w)


def _dst2utc(w: datetime, flag: str, cal: dict) -> datetime:
    offs = sorted({cal["base"]} | {o for _, o in cal["tr"]})
    return (w - timedelta(minutes=offs[-1] if flag.strip() == "1" else offs[0])).replace(tzinfo=_Z)


def _runtok(t: Any) -> str | None:
    s = str(t).strip()
    if re.match(r"^KTC-2(6A|5C)/", s, re.I):
        return None
    g = re.findall(r"\d+", s)
    return f"KTC-R{int(g[-1]):02d}" if g else None


def _sertok(t: Any) -> str:
    s = "".join(ch for ch in str(t).upper() if ch not in " -_")
    g = re.fullmatch(r"([A-Z]+)([0-9]+)", s)
    return f"{g.group(1)}-{g.group(2)}" if g else s


def _chtok(t: Any) -> str:
    s = str(t).strip().lower()
    for pat, ui, ci in ((r"d(\d)c(\d+)", 1, 2), (r"daq(\d)-(\d+)", 1, 2), (r"(\d)/(\d+)", 1, 2), (r"ch(\d+)@daq(\d)", 2, 1)):
        g = re.fullmatch(pat, s)
        if g:
            return f"D{g.group(ui)}C{int(g.group(ci)):02d}"
    return s.upper()


def _lktok(t: Any) -> str:
    g = re.fullmatch(r"TL[ \-]*0*(\d+)", str(t).strip().upper())
    return f"TL-{int(g.group(1)):03d}" if g else str(t).strip()


def _shard(path: Path, lay: str, cal: dict) -> list[tuple]:  # noqa: C901
    """(run token, token kind, token, instant, raw text or None, unit, rev, void)."""
    out: list[tuple] = []
    add = out.append
    if lay == "L01":
        for r in _rows(path.read_text(encoding="utf-8"), ","):
            add((r["run"], "s", r["sensor"], _inst(r["ts_utc"]), None if r["raw"] in ("", "NaN") else r["raw"], r["unit"], int(r["rev"]), r["void"] == "Y"))
    elif lay == "L02":
        um = {"OHM": "ohm", "KOHM": "kohm", "VOLT": "V", "MVOLT": "mV"}
        for r in _rows(path.read_text(encoding="utf-8"), "\t"):
            add((r["RUN"], "s", r["SERIAL"], _ep(int(r["EPOCH_S"])), None if r["VALUE"] in ("", "-9999") else r["VALUE"], um[r["UNITS"]], int(r["REVISION"]),
                 r["STATUS"] == "VOID"))
    elif lay == "L03":
        for r in _rows(path.read_text(encoding="utf-8"), "|"):
            w = datetime.strptime(r["local_time"], "%d/%m/%Y %H:%M:%S")
            add((r["run_tag"], "c", r["chan"], _dst2utc(w, r["isdst"], cal), None if r["reading"] in ("", "OVL") else r["reading"], "*", int(r["rev"]),
                 r["flag"] == "x"))
    elif lay == "L04":
        for d in _jl(path):
            add((d["r"], "s", d["s"], _ep(int(d["t_ms"]) // 1000), d["v"] if d["v"] not in (None, "") else None, d["u"], int(d["rv"]), d["del"] is True))
    elif lay == "L05":
        for d in _jl(path):
            x = d["value"]["x"]
            add((d["meta"]["run"], "s", d["sensor"], _inst(d["at"]), None if x in ("", "ERR", None) else x, d["value"]["unit"], int(d["meta"]["rev"]),
                 int(d["void"]) == 1))
    elif lay == "L06":
        for b in ET.parse(path).getroot().findall("batch"):
            for r in b.findall("r"):
                add((b.get("run"), "s", r.get("s"), _inst(r.get("t")), r.get("raw") or None, r.get("u"), int(r.get("rev")), r.get("void") == "true"))
    elif lay == "L07":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for a, b, c, d, e, f, g in con.execute("SELECT run, sensor, epoch, raw, unit, rev, voided FROM readings ORDER BY rowid"):
            add((a, "s", b, _ep(int(c)), d if d not in (None, "") else None, e, int(f), int(g) == 1))
        con.close()
    elif lay == "L08":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        fr = {fid: (run, ms, rev, vd) for fid, run, ms, rev, vd in con.execute("SELECT frame_id, run, epoch_ms, rev, void FROM frames")}
        for fid, ch, micro in con.execute("SELECT frame_id, channel, micro FROM samples ORDER BY rowid"):
            run, ms, rev, vd = fr[fid]
            add((run, "c", ch, _ep(int(ms) // 1000), None if micro is None else str(micro), "u", int(rev), int(vd) == 1))
        con.close()
    elif lay == "L09":
        for d in _yaml(path.read_text(encoding="utf-8")):
            add((d["run"], "s", d["sensor"], _ep(int(d["at"])), d["raw"], d["unit"], int(d["rev"]), d["void"] == "yes"))
    elif lay == "L10":
        for tok, blk in _yaml(path.read_text(encoding="utf-8")).items():
            for smp in blk["samples"]:
                p = [x.strip() for x in smp.split("|")]
                add((p[0], "s", tok, _inst(p[1]), None if p[2] == "-" else p[2], blk["unit"], int(p[3]), p[4] == "1"))
    elif lay == "L11":
        doc = json.loads(path.read_text(encoding="utf-8"))
        D = doc["data"]
        for i in range(len(D["run"])):
            add((D["run"][i], "s", D["sensor"][i], _inst(D["t"][i]), D["raw"][i] or None, doc["units"][D["sensor"][i]], int(D["rev"][i]), D["void"][i] is True))
    elif lay == "L12":
        sfx = {"R": "ohm", "K": "kohm", "V": "V", "M": "mV"}
        for line in path.read_text(encoding="utf-8").split("\n"):
            if not line or line[0] == "#" or line.startswith("RUN"):
                continue
            raw = line[38:53].strip()
            add((line[0:10].strip(), "s", line[10:21].strip(), datetime.strptime(line[21:38].strip(), "%Y%m%dT%H%M%SZ").replace(tzinfo=_Z),
                 None if raw.startswith("*") else raw[:-1], "ohm" if raw.startswith("*") else sfx[raw[-1]], int(line[53:57]), line[57:].strip() == "Y"))
    elif lay == "L13":
        run = None
        for line in path.read_text(encoding="utf-8").split("\n"):
            if line.startswith("## Run "):
                run = line[7:].strip()
            elif line.startswith("| ") and not line.startswith("| sensor"):
                c = [x.strip() for x in line[1:-1].split("|")]
                add((run, "s", c[0], datetime.strptime(c[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=_Z), None if c[2] == "n/a" else c[2].replace(",", ""), c[3],
                     int(c[4]), c[5] == "void"))
    elif lay == "L14":
        for r in _rows(path.read_text(encoding="utf-8"), ";"):
            w = datetime.strptime(r["time_local"], "%Y-%m-%d %H:%M:%S")
            add((r["run"], "s", r["probe"], _dst2utc(w, r["isdst"], cal), r["value"].replace(",", ".") or None, r["unit"], int(r["rev"]), r["cancelled"] == "1"))
    elif lay == "L15":
        for r in _rows(path.read_text(encoding="utf-8"), "\t"):
            add((r["run"], "c", r["ch"], _ep(int(r["epoch_ms"]) // 1000), None if r["val"] in ("", "NA") else r["val"], r["unit"], int(r["rev"]), r["void"] == "1"))
    elif lay == "L16":
        for d in _jl(path):
            t0 = _inst(d["t0"])
            for i, dt in enumerate(d["dt"]):
                add((d["run"], "s", d["sensor"], t0 + timedelta(seconds=int(dt)), d["v"][i], d["unit"], int(d["rev"]), i in d["void"]))
    return out
# =========================================================================== verifier: independent derivation
_STG = ["ST300", "ST50", "ST4"]
_COOL = ["ST50", "ST4"]
NAMES = ["sensor_means.tsv", "stage_temperatures.csv", "intercept_solutions.json", "link_heat_flows.psv", "junction_profiles.jsonl",
         "link_geometry.csv", "joint_conductances.tsv", "stage_loads.csv", "cooler_margins.xml", "run_verdicts.json", "alias_resolution.csv",
         "reading_exclusions.jsonl", "dedup_report.json", "source_lineage.json", "amendment_ledger.csv", "parameters_used.yaml",
         "authority_audit.csv", "variance_vs_published.csv", "reconciliation.md", "budget_summary.md"]


def _rhe(x: Fraction) -> int:
    """Round half to even, written out on numerator and denominator."""
    n, d = x.numerator, x.denominator
    q, r = divmod(n, d)
    if 2 * r > d or (2 * r == d and q % 2 == 1):
        q += 1
    return q


def _rhu(x: Fraction) -> int:
    n, d = x.numerator, x.denominator
    q, r = divmod(n, d)
    return q + (1 if 2 * r >= d else 0)


def _dec(x: Fraction) -> str:
    x = Fraction(x)
    k = 0
    while (x * 10 ** k).denominator != 1:
        k += 1
        if k > 30:
            raise ValueError("non-terminating")
    v = int(x * 10 ** k)
    s = str(abs(v)).rjust(k + 1, "0")
    s = s if k == 0 else (s[:-k] + "." + s[-k:]).rstrip("0").rstrip(".")
    return ("-" if v < 0 else "") + s


def _fx(x: Fraction, p: int, rnd=_rhe) -> str:
    v = rnd(Fraction(x) * 10 ** p)
    s = str(abs(v)).rjust(p + 1, "0")
    s = s if p == 0 else s[:-p] + "." + s[-p:]
    return ("-" if v < 0 else "") + s


class _Theta:
    """Piecewise-quadratic conductivity integral from 0 mK; numerators kept exact."""

    def __init__(self, pts: list[tuple[int, Fraction]]):
        self.t = [p[0] for p in pts]
        self.k = [p[1] for p in pts]
        acc = [self.k[0] * self.t[0]]
        for i in range(len(self.t) - 1):
            acc.append(acc[-1] + (self.t[i + 1] - self.t[i]) * (self.k[i] + self.k[i + 1]) / 2)
        self.acc = acc

    def kv(self, T: Fraction) -> Fraction:
        t, k = self.t, self.k
        if T <= t[0]:
            return k[0]
        if T >= t[-1]:
            return k[-1]
        i = max(j for j in range(len(t)) if t[j] <= T)
        return k[i] + (k[i + 1] - k[i]) * (T - t[i]) / (t[i + 1] - t[i])

    def at(self, T: Fraction) -> Fraction:
        t, k = self.t, self.k
        if T <= t[0]:
            return k[0] * T
        if T >= t[-1]:
            return self.acc[-1] + k[-1] * (T - t[-1])
        lo, hi = 0, len(t) - 1
        while hi - lo > 1:
            m = (lo + hi) // 2
            if t[m] <= T:
                lo = m
            else:
                hi = m
        u = T - t[lo]
        return self.acc[lo] + k[lo] * u + (k[lo + 1] - k[lo]) * u * u / (2 * (t[lo + 1] - t[lo]))

    def inv(self, y: Fraction) -> int | None:
        if y < 0:
            return None
        t, k, acc = self.t, self.k, self.acc
        if y <= acc[0]:
            x = y / k[0]
        elif y >= acc[-1]:
            x = t[-1] + (y - acc[-1]) / k[-1]
        else:
            i = max(j for j in range(len(acc)) if acc[j] <= y)
            a = (k[i + 1] - k[i]) / (2 * (t[i + 1] - t[i]))
            b = k[i]
            c = acc[i] - y
            if a == 0:
                x = t[i] - c / b
            else:
                disc = b * b - 4 * a * c
                s = Fraction(math.isqrt(disc.numerator * disc.denominator * 10 ** 12), disc.denominator * 10 ** 6)
                x = t[i] + (-b + s) / (2 * a)
        n = math.floor(x)
        while self.at(Fraction(n)) > y:
            n -= 1
        while self.at(Fraction(n + 1)) <= y:
            n += 1
        mid = self.at(Fraction(2 * n + 1, 2))
        if y == mid:
            return n + (n % 2)
        return n if y < mid else n + 1


def _interp_cal(fam: str, pts: list[tuple[Fraction, Fraction]], raw: Fraction, flip: str) -> int | None:
    lo, hi = min(p[0] for p in pts), max(p[0] for p in pts)
    if not lo <= raw <= hi:
        return None
    ntc = fam == "NTC" and flip != "ntc_r"
    sp = (lambda v: 1 / v) if ntc else (lambda v: v)
    sp_pts = sorted(((sp(r), T) for r, T in pts), key=lambda p: p[1])
    x = sp(raw)
    for (x0, t0), (x1, t1) in zip(sp_pts, sp_pts[1:]):
        if (x0 <= x <= x1) or (x1 <= x <= x0):
            T = t0 if x0 == x1 else t0 + (t1 - t0) * (x - x0) / (x1 - x0)
            return (_rhu if flip == "half_up" else _rhe)(T * 1000)
    return None


def _area(spec: str, awg: dict) -> Fraction:
    g = re.fullmatch(r"A:([\d.]+)(mm2|cm2)", spec.strip())
    if g:
        return _q(g.group(1)) * (100 if g.group(2) == "cm2" else 1)
    g = re.fullmatch(r"R:([\d.]+)x([\d.]+)mm", spec.strip())
    if g:
        return _q(g.group(1)) * _q(g.group(2))
    g = re.fullmatch(r"W:(\d+)x(\d+)AWG", spec.strip())
    return int(g.group(1)) * awg[int(g.group(2))]


def _state(root: Path, flip: str = "") -> dict[str, Any]:  # noqa: C901
    S: dict[str, Any] = {"flip": flip, "root": root}
    cal = _cal(root)
    cat = json.loads(next(root.glob("ingest_catalog_*.json")).read_text(encoding="utf-8"))
    P = _yaml(next(root.glob("campaign_profile_*.yml")).read_text(encoding="utf-8"))
    S["P"] = P
    order = [r["id"] for r in P["runs"]]
    S["order"] = order
    d1904, book = _book(next(root.glob("*.xlsx")))
    memo = _memo(next(root.glob("governance_memo_*.pdf")))
    want = "WITHDRAWN" if flip == "withdrawn" else "IN FORCE"

    def tab(title: str) -> tuple[str, list]:
        for lab, t in memo.items():
            if t["title"] == title and t["status"] == want:
                return lab, t["rows"]
        for lab, t in memo.items():
            if t["title"] == title and t["status"] == "IN FORCE":
                return lab, t["rows"]
        raise KeyError(title)

    S["tabs"] = {}
    for key, title in (("joint", "Joint base conductance per bolt, mW/K"), ("parasitic", "Parasitic load by shield configuration, uW"),
                       ("solver", "Solver contract constants"), ("gauge", "Conductor cross-section by gauge, mm2"), ("limits", "Stage temperature limits, mK")):
        S["tabs"][key] = tab(title)
    hb = {(r["class"], r["band"]): _q(r["h_mW_per_K"]) for r in S["tabs"]["joint"][1]}
    par = {(r["config"], r["stage"]): int(r["load_uW"]) for r in S["tabs"]["parasitic"][1]}
    SC = {r["constant"]: r["value"] for r in S["tabs"]["solver"][1]}
    awg = {int(r["awg"]): _q(r["area_mm2"]) for r in S["tabs"]["gauge"][1]}
    lim = {r["stage"]: int(r["limit_mK"]) for r in S["tabs"]["limits"][1]}
    S.update({"hb": hb, "par": par, "SC": SC, "awg": awg, "lim": lim})
    # registers
    con = sqlite3.connect(f"file:{root / 'entity_alias_register.sqlite'}?mode=ro", uri=True)
    matal = {}
    for tok, tgt, st in con.execute("SELECT token, target, status FROM material_alias ORDER BY rowid"):
        if st.strip().upper() == "ACTIVE" and tok.strip().upper() not in matal:
            matal[tok.strip().upper()] = tgt.strip()
    nodeal = {a.strip().upper(): b.strip() for a, b in con.execute("SELECT token, node FROM node_alias")}
    lkal = {_lktok(a): _lktok(b) for a, b in con.execute("SELECT old_id, new_id FROM link_alias")}
    rel = {_sertok(a): _sertok(b) for a, b in con.execute("SELECT old_serial, new_serial FROM sensor_relabel")}
    con.close()
    con = sqlite3.connect(f"file:{root / 'channel_map_history.db'}?mode=ro", uri=True)
    chmap: dict[str, list] = {}
    for ch, ser, a, b in con.execute("SELECT channel, serial, valid_from_utc, valid_to_utc FROM channel_assignment"):
        chmap.setdefault(_chtok(ch), []).append((_inst(a), _inst(b) if b else None, ser))
    con.close()

    def fser(t: str) -> str:
        s = _sertok(t)
        hops = 0
        while s in rel and hops < 50:
            s = rel[s]
            hops += 1
            if flip == "one_hop":
                break
        return s

    def flink(t: str) -> str:
        s = _lktok(t)
        for _ in range(50):
            if s not in lkal:
                break
            s = lkal[s]
        return s

    kname = P["conductivity_sheet"]
    kmat: dict[str, list] = {}
    for r in book[kname]:
        kmat.setdefault(r["material"].upper(), []).append((_rhe(_q(r["T_K"]) * 1000), _q(r["k"]) / (10 if r["unit"] == "mW/cm-K" else 1)))
    th = {m: _Theta(sorted(v)) for m, v in kmat.items()}
    S["th"] = th

    def fmat(t: str) -> str:
        cur = str(t).strip()
        for _ in range(50):
            if cur.upper() in kmat:
                return cur.upper()
            if cur.upper() not in matal:
                return "UNRESOLVED"
            cur = matal[cur.upper()]
        return "UNRESOLVED"

    def fnode(t: str) -> str:
        s = str(t).strip()
        if s.upper() in _STG:
            return s.upper()
        if s.upper().startswith("IX-"):
            return s
        return nodeal.get(s.upper(), "UNRESOLVED")

    S.update({"fser": fser, "flink": flink, "fmat": fmat, "fnode": fnode})
    inv = {_sertok(x["serial"]): x for x in json.loads((root / "sensor_inventory.json").read_text(encoding="utf-8"))["sensors"]}
    smap = {}
    for a in _yaml(next(root.glob("sensor_map_*.yaml")).read_text(encoding="utf-8"))["assignments"]:
        smap[fser(a["serial"])] = sorted((_inst(h["from_utc"]), fnode(h["stage"])) for h in a["history"])
    # calibrations
    cals: dict[str, list] = {}
    base = date(1904, 1, 1) if d1904 else date(1899, 12, 30)
    unitmul = {"ohm": Fraction(1), "kohm": Fraction(1000), "V": Fraction(1), "mV": Fraction(1, 1000)}
    grp: dict[tuple, list] = {}
    for r in book[P["calibration_sheet"]]:
        grp.setdefault((_sertok(r["serial"]), r["version"], base + timedelta(days=int(_q(r["valid_from"])))), []).append(
            (_q(r["raw"]) * unitmul[r["unit"]], _q(r["T_K"])))
    for (ser, _v, vf), pts in grp.items():
        cals.setdefault(ser, []).append((vf, pts))
    gen: dict[str, list] = {}
    for r in _rows((root / "calibration_generic_curves.tsv").read_text(encoding="utf-8"), "\t"):
        gen.setdefault(r["curve"], []).append((_q(r["raw"]) * unitmul[r["unit"]], _q(r["T_K"])))
    # profile settings
    knobs = ("spike_mK", "outlier_mK", "min_readings")
    ovl = None
    for p in sorted(root.glob("profile_overlay_*.yaml")):
        y = _yaml(p.read_text(encoding="utf-8"))
        if str(y.get("base_revision")) == str(P["profile_revision"]):
            ovl = y
    S["overlay"] = ovl is not None
    sett = {}
    for r in P["runs"]:
        s = {k: int(P[k]) for k in knobs}
        s["reserve_pct_ST50"] = int(P["reserve_pct"]["ST50"])
        s["reserve_pct_ST4"] = int(P["reserve_pct"]["ST4"])
        for k in list(s):
            if r.get(k) is not None:
                s[k] = int(r[k])
        if ovl is not None:
            o = (ovl.get("runs") or {}).get(r["id"]) or {}
            for k in ovl.get("overridable_keys") or []:
                if k in o and o[k] is not None:
                    s[k] = int(o[k])
        sett[r["id"]] = s
    S["sett"] = sett
    # run log
    ev: dict[tuple, dict] = {}
    for r in _rows(next(root.glob("run_log_*.csv")).read_text(encoding="utf-8"), ","):
        rid = _runtok(r["run"])
        if rid is None or r["event"] == "NOTE":
            continue
        k = (rid, r["event"])
        if k not in ev or int(r["rev"]) >= int(ev[k]["rev"]):
            ev[k] = r
    runs = {}
    for rid in order:
        def w(e):
            x = ev.get((rid, e))
            return _wall2utc(datetime.strptime(x["local_time"], "%Y-%m-%d %H:%M"), cal) if x else None
        ab = ev.get((rid, "ABORT"))
        runs[rid] = {"a": w("PLATEAU_START"), "b": w("PLATEAU_END"), "abort": bool(ab) and ab["value"] == "ACTIVE",
                     "shield": (ev.get((rid, "CONFIG")) or {}).get("value"), "cooler": next(x["cooler"] for x in P["runs"] if x["id"] == rid)}
    S["runs"] = runs
    live = [r for r in order if not runs[r]["abort"]]
    S["live"] = live
    # rulings
    rul = {r["ruling"]: dict(r) for r in memo["R-1"]["rows"]}
    for e in sorted(ET.parse(root / "ruling_addendum.xml").getroot().findall("entry"), key=lambda e: int(e.get("seq"))):
        if e.get("status") == "ISSUED" and e.get("ref") in rul:
            rul[e.get("ref")]["status"] = "IN FORCE" if e.get("action") == "REINSTATE" else "RESCINDED"
    exs, offs, exl = set(), {}, set()
    for r in rul.values():
        rid = _runtok(r["run"])
        if r["status"] != "IN FORCE" or rid is None:
            continue
        if r["action"] == "EXCLUDE_SENSOR":
            exs.add((rid, fser(r["target"])))
        elif r["action"] == "OFFSET_SENSOR":
            offs[(rid, fser(r["target"]))] = offs.get((rid, fser(r["target"])), 0) + int(r["value"])
        elif r["action"] == "EXCLUDE_LINK":
            exl.add((rid, flink(r["target"])))
    # -------------------------------------------------------------- readings
    shards = [s for s in sorted(cat["shards"], key=lambda s: s["order"]) if s["kind"] == "readings" and s["status"] == "ACTIVE"]
    excl: dict[tuple, int] = {}

    def bump(rid, ser, why, n=1):
        if rid in runs and not runs[rid]["abort"]:
            excl[(rid, ser, why)] = excl.get((rid, ser, why), 0) + n

    win: dict[tuple, tuple] = {}
    anyvoid: set = set()
    lineage = []
    nread = nunres = nres = 0
    sertoks = set()
    for si, sh in enumerate(shards):
        recs = _shard(root / sh["file"], sh["layout"], cal)
        L = {"file": sh["file"], "layout": sh["layout"], "records": len(recs), "resolved": 0, "winning": 0}
        lineage.append(L)
        for li, (rt, kind, tok, t, raw, unit, rev, vd) in enumerate(recs):
            nread += 1
            rid = _runtok(rt)
            if kind == "c":
                ch = _chtok(tok)
                ser = next((s for a, b, s in chmap.get(ch, []) if a <= t and (b is None or t < b)), None)
                if ser is None:
                    nunres += 1
                    bump(rid, ch, "UNMAPPED_CHANNEL")
                    continue
                f = fser(ser)
            else:
                sertoks.add(_sertok(tok))
                f = fser(tok)
            if f not in inv:
                nunres += 1
                bump(rid, f, "UNKNOWN_SENSOR")
                continue
            nres += 1
            L["resolved"] += 1
            key = (f, t)
            cand = (rev, si, li)
            if vd:
                anyvoid.add(key)
            if key not in win or cand > win[key][0]:
                win[key] = (cand, (rid, raw, unit, vd), L)
    voided = 0
    oos = 0
    bykey: dict[tuple, list] = {}
    keys = list(win)
    for k in keys:
        cand, (rid, raw, unit, vd), L = win[k]
        if vd or (flip == "void_first" and k in anyvoid):
            voided += 1
            continue
        L["winning"] += 1
        if rid is None or rid not in runs or runs[rid]["abort"]:
            oos += 1
            continue
        bykey.setdefault((rid, k[0]), []).append((k[1], raw, unit))
    S["dedup"] = {"records_read": nread, "unresolved": nunres, "copies_superseded": nres - len(keys), "voided_keys": voided,
                  "unique_readings": len(keys) - voided, "out_of_scope_readings": oos}
    S["lineage"] = lineage
    S["sertoks"] = sertoks
    S["inv"] = inv
    rnd = _rhu if flip == "half_up" else _rhe
    means = {}
    for (rid, f), rs in bykey.items():
        R = runs[rid]
        st = None
        for at, n in smap.get(f, []):
            if at <= R["a"]:
                st = n
        if st not in _STG:
            continue
        fam = inv[f]["family"]
        vals = []
        for t, raw, unit in sorted(rs, key=lambda x: x[0]):
            if raw is None:
                bump(rid, f, "INVALID_VALUE")
                continue
            if not (R["a"] <= t < R["b"] or (flip == "closed_window" and t == R["b"])):
                bump(rid, f, "OUT_OF_WINDOW")
                continue
            if any(a <= t < b and (sc == "ALL" or fnode(sc) == st) for a, b, sc in cal["maint"]):
                bump(rid, f, "MAINTENANCE")
                continue
            if (rid, f) in exs:
                bump(rid, f, "EXCLUDED_SENSOR")
                continue
            vers = [v for v in cals.get(f, []) if v[0] <= t.date()]
            if vers:
                pts = sorted(vers, key=lambda v: v[0])[-1][1]
            elif inv[f].get("cal_policy") == "GENERIC_OK" and inv[f].get("generic_curve") in gen:
                pts = gen[inv[f]["generic_curve"]]
            else:
                bump(rid, f, "NO_CALIBRATION")
                continue
            mul = {"ohm": 1, "kohm": 1000, "V": 1, "mV": Fraction(1, 1000), "u": Fraction(1, 10 ** 6), "*": 1}[unit]
            mk = _interp_cal(fam, pts, _q(raw) * mul, flip)
            if mk is None:
                bump(rid, f, "OUT_OF_RANGE")
                continue
            vals.append(mk + offs.get((rid, f), 0))
        sp = sett[rid]["spike_mK"]
        keep = []
        if vals:
            o = sorted(vals)
            med = Fraction(o[len(o) // 2] + o[(len(o) - 1) // 2], 2)
            keep = [v for v in vals if abs(v - med) <= sp]
            if len(vals) > len(keep):
                bump(rid, f, "SPIKE", len(vals) - len(keep))
        ok = bool(keep) and len(keep) >= sett[rid]["min_readings"]
        means[(rid, f)] = (st, len(vals), len(vals) - len(keep), len(keep), rnd(Fraction(sum(keep), len(keep))) if ok else None,
                           "OK" if ok else ("SPARSE" if keep else "NO_READINGS"))
    S["means"] = means
    S["excl"] = excl
    stT = {}
    for rid in live:
        for st in _STG:
            got = sorted((f, m[4]) for (r, f), m in means.items() if r == rid and m[0] == st and m[4] is not None)
            if not got:
                stT[(rid, st)] = ([], [], None)
                continue
            o = sorted(v for _, v in got)
            med = Fraction(o[len(o) // 2] + o[(len(o) - 1) // 2], 2)
            use = [(f, v) for f, v in got if abs(v - med) <= sett[rid]["outlier_mK"]]
            stT[(rid, st)] = ([f for f, _ in use], [f for f, v in got if abs(v - med) > sett[rid]["outlier_mK"]],
                              rnd(Fraction(sum(v for _, v in use), len(use))))
    S["stT"] = stT
    _links(S, root, flink, fmat, fnode, exl)
    _flows(S)
    _margins(S, root, book)
    return S


def _links(S: dict, root: Path, flink, fmat, fnode, exl) -> None:  # noqa: C901
    runs, live = S["runs"], S["live"]
    toks = {"link": set(), "material": set(), "node": set()}
    catrows: dict[str, list] = {}
    for r in _rows((root / "lk_9tc1.csv").read_text(encoding="utf-8"), ","):
        toks["link"].add(r["link"].strip())
        catrows.setdefault(flink(r["link"]), []).append((date.fromisoformat(r["effective_from"]), int(r["rev"]), r["status"]))
    segs: dict[tuple, dict] = {}
    for le in ET.parse(root / "lk_4sg7.xml").getroot().findall("link"):
        toks["link"].add(le.get("id").strip())
        for sg in le.findall("seg"):
            toks["material"].add(sg.get("mat").strip())
            segs.setdefault((flink(le.get("id")), int(le.get("rev"))), {})[int(sg.get("n"))] = (sg.get("mat"), _q(sg.get("len").replace("mm", "")), sg.get("area"),
                                                                                                 sg.get("lot") or "")
    for r in _rows((root / "lk_2sg8.psv").read_text(encoding="utf-8"), "|"):
        toks["link"].add(r["link"].strip())
        toks["material"].add(r["material"].strip())
        mm = {"mm": Fraction(1), "cm": Fraction(10), "in": Fraction(127, 5)}[r["length_unit"]]
        segs.setdefault((flink(r["link"]), int(r["rev"])), {})[int(r["seq"])] = (r["material"], _q(r["length"]) * mm, r["area_spec"],
                                                                                 "" if r["lot"] == "-" else r["lot"])
    jts: dict[tuple, dict] = {}
    for j in _jl(root / "lk_6jt3.jsonl"):
        toks["link"].add(str(j["link"]).strip())
        ind = j["indium"] if isinstance(j["indium"], bool) else str(j["indium"]).strip().lower() in ("true", "yes")
        jts.setdefault((flink(j["link"]), int(j["rev"])), {})[int(j["pos"])] = [j["class"], int(j["bolts"]), str(j["torque"]).upper(), ind]
    am = _jl(root / "lk_3am0.ndjson")
    for e in am:
        toks["link"].add(str(e["link"]).strip())
    live_set: dict[int, bool] = {}
    killed: set[int] = set()
    for e in sorted(am, key=lambda e: int(e["seq"]), reverse=True):
        s = int(e["seq"])
        on = str(e["status"]).strip().upper() == "POSTED" and s not in killed
        live_set[s] = on
        if on and str(e["action"]).strip().upper() == "REVERSE":
            killed.add(int(e["reverses"]))
    ledger = []
    setv: dict[tuple, str] = {}
    for e in sorted(am, key=lambda e: int(e["seq"])):
        s = int(e["seq"])
        L = flink(e["link"])
        ledger.append([str(s), L, str(e["rev"]), e["field"], str(e["action"]).upper(), str(e["status"]).upper(), "Y" if live_set[s] else "N"])
        if live_set[s] and str(e["action"]).upper() == "SET":
            setv[(L, int(e["rev"]), e["field"])] = e["value"]
    S["ledger"] = ledger
    inst: dict[tuple, dict] = {}
    for r in _rows((root / "lk_8in5.tsv").read_text(encoding="utf-8"), "\t"):
        toks["link"].add(r["link"].strip())
        toks["node"].update([r["hot"].strip(), r["cold"].strip()])
        k = (_runtok(r["run"]), flink(r["link"]))
        if k not in inst or int(r["rev"]) >= int(inst[k]["rev"]):
            inst[k] = r
    for a in _yaml(next(root.glob("sensor_map_*.yaml")).read_text(encoding="utf-8"))["assignments"]:
        for h in a["history"]:
            toks["node"].add(str(h["stage"]).strip())
    reg = ET.parse(root / "intercept_register.xml").getroot()
    band = {(_runtok(x.get("run")), x.get("id")): x.get("band") for x in reg.findall("intercept")}
    nominal = {(_runtok(x.get("run")), x.get("id")): _rhe(_q(x.get("nominal_K")) * 1000) for x in reg.findall("intercept")}
    bn = {}
    for b in reg.findall("bundle"):
        toks["node"].add(b.get("node").strip())
        bn[(b.get("id"), _runtok(b.get("run")))] = fnode(b.get("node"))
    hlast: dict[str, dict] = {}
    for r in _rows((root / "harness_dissipation.psv").read_text(encoding="utf-8"), "|"):
        if r["bundle"] not in hlast or int(r["rev"]) >= int(hlast[r["bundle"]]["rev"]):
            hlast[r["bundle"]] = r
    harn: dict[tuple, int] = {}
    for bid, r in hlast.items():
        if r["void"] == "VOID":
            continue
        rid = _runtok(r["run"])
        n = bn.get((bid, rid))
        if n is None:
            continue
        v = _q(r["dissipation"]) * (1000 if r["unit"] == "mW" else 1)
        harn[(rid, n)] = harn.get((rid, n), 0) + int(v)
    S.update({"toks": toks, "band": band, "nominal": nominal, "harn": harn})
    lots = {e.get("id"): (_q(e.get("k_scale")), e.get("status")) for e in ET.parse(root / "material_lot_certs.xml").getroot().findall("lot")}
    lm = S["SC"]["lot_scale_materials"].split()
    inc = _q(S["SC"]["h_increment_mW_per_K"])
    lowf, indf = _q(S["SC"]["low_torque_factor"]), _q(S["SC"]["indium_factor"])
    D: dict[tuple, dict] = {}
    for (rid, L), r in inst.items():
        if rid not in runs or runs[rid]["abort"] or r["state"] != "INSTALLED":
            continue
        hot, cold = fnode(r["hot"]), fnode(r["cold"])
        d = {"hot": hot, "cold": cold, "rev": None, "el": [], "status": "READY"}
        D[(rid, L)] = d
        day = runs[rid]["a"].date()
        cands = sorted((c for c in catrows.get(L, []) if c[0] <= day), key=lambda c: (c[0], c[1]))
        if not cands:
            d["status"] = "NO_GEOMETRY"
            continue
        d["rev"] = cands[-1][1]
        if cands[-1][2] == "VOID":
            d["status"] = "NO_GEOMETRY"
            continue
        if (rid, L) in exl:
            d["status"] = "EXCLUDED"
            continue
        rv = d["rev"]
        bd = "W" if cold == "ST50" else ("C" if cold == "ST4" else band.get((rid, cold)))
        sg = segs.get((L, rv), {})
        jj = jts.get((L, rv), {})

        def A(field, dflt):
            return setv.get((L, rv, field), dflt)

        for p in range(len(sg) + 1):
            if p in jj:
                cls, bolts, tq, ind = jj[p]
                bolts = int(A(f"joint{p}.bolts", bolts))
                tq = str(A(f"joint{p}.torque", tq)).upper()
                iv = A(f"joint{p}.indium", ind)
                ind = iv if isinstance(iv, bool) else str(iv).strip().lower() in ("true", "yes", "y")
                h = S["hb"][(cls, bd)] * bolts * (lowf if tq == "LOW" else 1) * (indf if ind and cls.startswith("BOLT_") else 1)
                d["el"].append(("j", {"pos": p, "class": cls, "band": bd, "bolts": bolts, "torque": tq, "indium": ind, "base": S["hb"][(cls, bd)],
                                      "h": _rhe(h / inc) * inc}))
            if p + 1 in sg:
                mt, ln, ar, lot = sg[p + 1]
                mat = fmat(A(f"seg{p + 1}.material", mt))
                ln = _q(A(f"seg{p + 1}.length_mm", ln))
                a = _area(A(f"seg{p + 1}.area", ar), S["awg"])
                sc = Fraction(1)
                if lot and lots.get(lot, (0, ""))[1] == "CERTIFIED" and (lm == ["ALL"] or mat in lm):
                    sc = lots[lot][0]
                d["el"].append(("s", {"seq": p + 1, "material": mat, "length": ln, "area": a, "lot": lot, "scale": sc, "g": a / ln}))
    S["D"] = D


def _march(S: dict, d: dict, T0: int, q: int) -> list[int] | None:
    T = T0
    out = []
    for kind, e in d["el"]:
        if kind == "j":
            T -= _rhe(Fraction(q) / e["h"])
        else:
            th = S["th"][e["material"]]
            T = th.inv(th.at(Fraction(T)) - Fraction(q) / (e["g"] * e["scale"]))
            if T is None:
                return None
        if T < 0:
            return None
        out.append(T)
    return out


def _qsolve(S: dict, d: dict, th_: int, tc: int) -> tuple[int, list[int]]:
    memo = S.setdefault("qmemo", {})
    k = (id(d), th_, tc)
    if k in memo:
        return memo[k]
    if th_ <= tc:
        memo[k] = (0, [th_] * len(d["el"]))
        return memo[k]

    def good(q: int) -> bool:
        m = _march(S, d, th_, q)
        return m is not None and (not m or m[-1] >= tc)

    hi = 1024
    while good(hi):
        hi *= 4
    lo = 0
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if good(mid):
            lo = mid
        else:
            hi = mid
    memo[k] = (lo, _march(S, d, th_, lo))
    return memo[k]


def _flows(S: dict) -> None:
    D, stT = S["D"], S["stT"]
    IX: dict[tuple, dict] = {}
    for rid in S["live"]:
        xs = sorted({n for (r, _), d in D.items() if r == rid for n in (d["hot"], d["cold"]) if n.startswith("IX")})
        for x in xs:
            ins = sorted(L for (r, L), d in D.items() if r == rid and d["cold"] == x and d["status"] == "READY")
            outs = sorted(L for (r, L), d in D.items() if r == rid and d["hot"] == x and d["status"] == "READY")
            hv = [stT.get((rid, D[(rid, L)]["hot"]), (0, 0, None))[2] for L in ins]
            cv = [stT.get((rid, D[(rid, L)]["cold"]), (0, 0, None))[2] for L in outs]
            Pw = S["harn"].get((rid, x), 0)
            rec = {"band": S["band"].get((rid, x)), "ins": ins, "outs": outs, "harness": Pw}
            IX[(rid, x)] = rec
            if not hv or not cv or None in hv or None in cv:
                rec.update(status="UNSOLVED", T=None, lo=None, hi=None, res=None, nxt=None)
                continue
            lo, hi = max(cv), min(hv)

            def bal(T: int) -> int:
                tot = Pw
                for L in ins:
                    tot += _qsolve(S, D[(rid, L)], stT[(rid, D[(rid, L)]["hot"])][2], T)[0]
                for L in outs:
                    tot -= _qsolve(S, D[(rid, L)], T, stT[(rid, D[(rid, L)]["cold"])][2])[0]
                return tot

            if S["flip"] == "single_pass":
                T = max(lo, min(hi, S["nominal"].get((rid, x), lo)))
                st = "BALANCED"
            elif bal(hi) >= 0:
                T, st = hi, "CEILING"
            elif bal(lo) < 0:
                T, st = lo, "FLOOR"
            else:
                a, b = lo, hi
                while b - a > 1:
                    m = (a + b) // 2
                    if bal(m) >= 0:
                        a = m
                    else:
                        b = m
                T, st = a, "BALANCED"
            rec.update(status=st, T=T, lo=lo, hi=hi, res=bal(T), nxt=None if T >= hi else bal(T + 1))
    S["IX"] = IX

    def nt(rid, n):
        if n.startswith("IX"):
            return IX.get((rid, n), {}).get("T")
        return stT.get((rid, n), (0, 0, None))[2]

    FL = {}
    for (rid, L), d in D.items():
        a, b = nt(rid, d["hot"]), nt(rid, d["cold"])
        row = {"rev": d["rev"], "hot": d["hot"], "cold": d["cold"], "a": a, "b": b, "q": None, "temps": None}
        if d["status"] != "READY":
            row["status"] = d["status"]
        elif a is None or b is None:
            row["status"] = "UNSOLVED"
        else:
            q, temps = _qsolve(S, d, a, b)
            row.update(q=q, temps=temps, status="OK" if a > b else "NO_GRADIENT")
        FL[(rid, L)] = row
    S["FL"] = FL


def _margins(S: dict, root: Path, book: dict) -> None:
    runs = S["runs"]
    cap: dict[tuple, list] = {}
    for r in book[S["P"]["capacity_sheet"]]:
        cap.setdefault((r["model"], r["stage"]), []).append((_rhe(_q(r["T_K"]) * 1000), _q(r["capacity_W"])))
    svc = _rows((root / "cooler_service_log.tsv").read_text(encoding="utf-8"), "\t")
    LD, MG, VD = {}, {}, {}
    rank = ["PASS", "MARGINAL", "OVERLOAD", "OVER_TEMP"]
    for rid in S["order"]:
        if runs[rid]["abort"]:
            VD[rid] = ("ABORTED", None, None, 0)
            continue
        uns = sum(1 for (r, _), f in S["FL"].items() if r == rid and f["status"] == "UNSOLVED")
        sv = {}
        for st in _COOL:
            rows = [f for (r, _), f in S["FL"].items() if r == rid and f["cold"] == st]
            bad = any(f["status"] == "UNSOLVED" for f in rows)
            lk = None if bad else sum(f["q"] or 0 for f in rows)
            h = S["harn"].get((rid, st), 0)
            pp = S["par"][(runs[rid]["shield"], st)]
            tot = None if lk is None else lk + h + pp
            LD[(rid, st)] = (lk, h, pp, tot, "INCOMPLETE" if bad else "OK")
            T = S["stT"][(rid, st)][2]
            cl = runs[rid]["cooler"]
            model = "GM-K15" if cl == "CC-0417" else "PT-K41"
            day = runs[rid]["a"].date()
            der = Fraction(0)
            for e in svc:
                if e["cooler"] == cl and e["action"] in ("DERATE", "RESTORE") and date.fromisoformat(e["date"]) <= day:
                    der = _q(e["value"]) if e["action"] == "DERATE" else Fraction(0)
            pct = S["sett"][rid][f"reserve_pct_{st}"]
            m = {"cooler": cl, "model": model, "T": T, "der": der, "pct": pct, "cap": None, "map": "", "res": None, "mar": None, "load": tot, "v": "INCOMPLETE"}
            if T is not None:
                pts = sorted(cap[(model, st)])
                if T < pts[0][0] or T > pts[-1][0]:
                    w, mp = (pts[0][1] if T < pts[0][0] else pts[-1][1]), "OUT_OF_MAP"
                else:
                    i = max(j for j in range(len(pts)) if pts[j][0] <= T)
                    w = pts[i][1] if i == len(pts) - 1 else pts[i][1] + (pts[i + 1][1] - pts[i][1]) * (T - pts[i][0]) / (pts[i + 1][0] - pts[i][0])
                    mp = "IN_MAP"
                c = _rhe(w * 10 ** 6 * (100 - der) / 100)
                m.update(cap=c, map=mp, res=_rhe(Fraction(c * pct, 100)))
                if tot is not None:
                    mar = c - tot
                    v = "OVER_TEMP" if T > S["lim"][st] else "OVERLOAD" if mar < 0 else "MARGINAL" if mar < m["res"] else "PASS"
                    m.update(mar=mar, v=v)
            MG[(rid, st)] = m
            sv[st] = m["v"]
        if uns or any(S["stT"][(rid, s)][2] is None for s in _STG) or "INCOMPLETE" in sv.values():
            VD[rid] = ("INCOMPLETE", sv["ST50"], sv["ST4"], uns)
        else:
            VD[rid] = (max(sv.values(), key=rank.index), sv["ST50"], sv["ST4"], uns)
    S.update({"LD": LD, "MG": MG, "VD": VD})
# =========================================================================== verifier: rendering
def _tab(h: list[str], rows: list[list[Any]], sep: str) -> str:
    buf = io.StringIO()
    wr = csv.writer(buf, delimiter=sep, lineterminator="\n")
    wr.writerow(h)
    for r in rows:
        wr.writerow(["" if v is None else v for v in r])
    return buf.getvalue()


def _js(o: Any) -> str:
    return json.dumps(o, indent=2, sort_keys=True) + "\n"


def _render(S: dict) -> dict[str, str]:  # noqa: C901
    o: dict[str, str] = {}
    ri = {r: i for i, r in enumerate(S["order"])}
    si = {s: i for i, s in enumerate(_STG)}
    live = S["live"]
    o["sensor_means.tsv"] = _tab(["run", "serial", "stage", "window_readings", "spikes_dropped", "used_readings", "mean_mK", "status"],
                                 [[r, f, *m] for (r, f), m in sorted(S["means"].items(), key=lambda kv: (ri[kv[0][0]], si[kv[1][0]], kv[0][1]))], "\t")
    o["stage_temperatures.csv"] = _tab(["run", "stage", "sensors_used", "sensors_dropped", "temperature_mK", "status"],
                                       [[r, s, ";".join(sorted(S["stT"][(r, s)][0])), ";".join(sorted(S["stT"][(r, s)][1])), S["stT"][(r, s)][2],
                                         "NO_SENSORS" if S["stT"][(r, s)][2] is None else "OK"] for r in live for s in _STG], ",")
    ix = []
    for (r, x), v in sorted(S["IX"].items(), key=lambda kv: (ri[kv[0][0]], kv[0][1])):
        ix.append({"run": r, "node": x, "band": v["band"], "t_lo_mK": v["lo"], "t_hi_mK": v["hi"], "temperature_mK": v["T"], "harness_uW": v["harness"],
                   "residual_uW": v["res"], "next_residual_uW": v["nxt"], "links_in": v["ins"], "links_out": v["outs"], "status": v["status"]})
    o["intercept_solutions.json"] = _js({"count": len(ix), "intercepts": ix})
    FL = sorted(S["FL"].items(), key=lambda kv: (ri[kv[0][0]], kv[0][1]))
    o["link_heat_flows.psv"] = _tab(["run", "link", "rev", "hot_node", "cold_node", "hot_mK", "cold_mK", "q_uW", "status"],
                                    [[r, L, f["rev"], f["hot"], f["cold"], f["a"], f["b"], f["q"], f["status"]] for (r, L), f in FL], "|")
    jp = []
    for (r, L), f in FL:
        if f["status"] in ("OK", "NO_GRADIENT"):
            els = [({"kind": "joint", "pos": e["pos"], "t_mK": t} if k == "j" else {"kind": "segment", "seq": e["seq"], "t_mK": t})
                   for (k, e), t in zip(S["D"][(r, L)]["el"], f["temps"])]
            jp.append(json.dumps({"elements": els, "link": L, "q_uW": f["q"], "run": r}, sort_keys=True) + "\n")
    o["junction_profiles.jsonl"] = "".join(jp)
    geo, jt = [], []
    for (r, L), f in FL:
        if f["status"] not in ("OK", "NO_GRADIENT", "UNSOLVED"):
            continue
        for k, e in S["D"][(r, L)]["el"]:
            if k == "s":
                geo.append([r, L, f["rev"], e["seq"], e["material"], _dec(e["length"]), _dec(e["area"]), e["lot"], _dec(e["scale"]), _fx(e["g"], 9)])
        for k, e in sorted((x for x in S["D"][(r, L)]["el"] if x[0] == "j"), key=lambda x: x[1]["pos"]):
            jt.append([r, L, e["pos"], e["class"], e["band"], e["bolts"], e["torque"], "Y" if e["indium"] else "N", _dec(e["base"]), _dec(e["h"])])
    o["link_geometry.csv"] = _tab(["run", "link", "rev", "seq", "material", "length_mm", "area_mm2", "lot", "lot_scale", "g_mm"], geo, ",")
    o["joint_conductances.tsv"] = _tab(["run", "link", "pos", "class", "band", "bolts", "torque", "indium", "h_base_mW_per_K", "h_eff_mW_per_K"], jt, "\t")
    o["stage_loads.csv"] = _tab(["run", "stage", "links_uW", "harness_uW", "parasitic_uW", "total_uW", "status"],
                                [[r, s, *S["LD"][(r, s)]] for r in live for s in _COOL], ",")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', f'<margins campaign="{S["P"]["campaign"]}">']
    for r in live:
        for s in _COOL:
            m = S["MG"][(r, s)]
            at = [("run", r), ("name", s), ("cooler", m["cooler"]), ("model", m["model"]), ("temperature_mK", m["T"]), ("derate_pct", _dec(m["der"])),
                  ("capacity_uW", m["cap"]), ("map_status", m["map"]), ("load_uW", m["load"]), ("reserve_pct", m["pct"]), ("reserve_uW", m["res"]),
                  ("margin_uW", m["mar"]), ("verdict", m["v"])]
            lines.append("  <stage " + " ".join(f'{a}="{"" if b is None else b}"' for a, b in at) + "/>")
    lines.append("</margins>")
    o["cooler_margins.xml"] = "\n".join(lines) + "\n"
    summ: dict[str, int] = {}
    rv = []
    for r in S["order"]:
        v = S["VD"][r]
        summ[v[0]] = summ.get(v[0], 0) + 1
        rv.append({"run": r, "verdict": v[0], "ST50": v[1], "ST4": v[2], "unsolved_links": v[3]})
    o["run_verdicts.json"] = _js({"campaign": S["P"]["campaign"], "runs": rv, "summary": summ})
    al = {("material", t, S["fmat"](t)) for t in S["toks"]["material"]}
    al |= {("node", t, S["fnode"](t)) for t in S["toks"]["node"]}
    al |= {("link", t, S["flink"](t)) for t in S["toks"]["link"]}
    al |= {("sensor", t, S["fser"](t) if S["fser"](t) in S["inv"] else "UNRESOLVED") for t in S["sertoks"]}
    o["alias_resolution.csv"] = _tab(["kind", "token", "resolved"], [list(x) for x in sorted(al)], ",")
    o["reading_exclusions.jsonl"] = "".join(json.dumps({"count": n, "reason": k[2], "run": k[0], "serial": k[1]}, sort_keys=True) + "\n"
                                            for k, n in sorted(S["excl"].items(), key=lambda kv: (ri[kv[0][0]], kv[0][1], kv[0][2])) if n)
    o["dedup_report.json"] = _js(S["dedup"])
    o["source_lineage.json"] = _js({"shards": S["lineage"]})
    o["amendment_ledger.csv"] = _tab(["seq", "link", "rev", "field", "action", "status", "in_effect"], S["ledger"], ",")
    y = [f"campaign: {S['P']['campaign']}", f"profile_revision: {S['P']['profile_revision']}", f"overlay_applied: {str(S['overlay']).lower()}", "sheets:",
         f"  conductivity: {S['P']['conductivity_sheet']}", f"  calibration: {S['P']['calibration_sheet']}", f"  capacity: {S['P']['capacity_sheet']}",
         "memo_tables:"] + [f"  {k}: {S['tabs'][k][0]}" for k in ("joint", "parasitic", "solver", "gauge", "limits")] + ["constants:"]
    y += [f"  {k}: '{S['SC'][k]}'" for k in ("h_increment_mW_per_K", "indium_factor", "low_torque_factor", "lot_scale_materials")]
    y += ["limits_mK:", f"  ST50: {S['lim']['ST50']}", f"  ST4: {S['lim']['ST4']}", "runs:"]
    for r in live:
        st = S["sett"][r]
        y.append(f"  {r}:")
        y += [f"    {k}: {st[k]}" for k in ("spike_mK", "outlier_mK", "min_readings", "reserve_pct_ST50", "reserve_pct_ST4")]
        y += [f"    shield: {S['runs'][r]['shield']}", f"    cooler: {S['runs'][r]['cooler']}", f"    derate_pct: '{_dec(S['MG'][(r, 'ST50')]['der'])}'"]
    o["parameters_used.yaml"] = "\n".join(y) + "\n"
    o["authority_audit.csv"] = _audit(S)
    root = S["root"]
    pub = {(_runtok(r["run"]), S["flink"](r["link"])): _rhe(_q(r["q_mW"]) * 1000) for r in _rows((root / "heatload_budget_published.csv").read_text(encoding="utf-8"), ",")}
    rec = {k: f["q"] for k, f in S["FL"].items() if f["q"] is not None}
    vr = []
    for k in sorted(set(pub) | set(rec), key=lambda k: (ri.get(k[0], 10 ** 6), k[0], k[1])):
        p, q = pub.get(k), rec.get(k)
        st = "MISSING_PUBLISHED" if p is None else "MISSING_RECOMPUTED" if q is None else ("MATCH" if p == q else "DIFFERENT")
        vr.append([k[0], k[1], p, q, None if p is None or q is None else q - p, st])
    o["variance_vs_published.csv"] = _tab(["run", "link", "published_uW", "recomputed_uW", "delta_uW", "status"], vr, ",")
    doc = json.loads((root / "stage_margins_published.json").read_text(encoding="utf-8"))
    pr = sorted(doc["stages"], key=lambda x: (ri.get(_runtok(x["run"]), 10 ** 6), si[x["stage"]]))
    md = ["# Reconciliation with the published stage margins", "", "| run | stage | published_verdict | recomputed_verdict | change |", "|---|---|---|---|---|"]
    ch = 0
    for x in pr:
        r = _runtok(x["run"])
        now = "ABORTED" if S["VD"].get(r, ("",))[0] == "ABORTED" else S["MG"].get((r, x["stage"]), {}).get("v", "")
        c = "same" if now == x["verdict"] else "changed"
        ch += c == "changed"
        md.append(f"| {r} | {x['stage']} | {x['verdict']} | {now} | {c} |")
    md += ["", f"Changed verdicts: {ch} of {len(pr)}."]
    o["reconciliation.md"] = "\n".join(md) + "\n"
    bs = ["# Heat-load budget summary", "", "| run | verdict | ST50_load_uW | ST50_margin_uW | ST4_load_uW | ST4_margin_uW |", "|---|---|---|---|---|---|"]
    npass = 0
    for r in S["order"]:
        v = S["VD"][r][0]
        npass += v == "PASS"
        cells = []
        for s in _COOL:
            m = S["MG"].get((r, s), {})
            cells += ["" if m.get("load") is None else str(m["load"]), "" if m.get("mar") is None else str(m["mar"])]
        bs.append(f"| {r} | {v} | " + " | ".join(cells) + " |")
    bs += ["", f"Runs passing: {npass} of {len(S['order'])}."]
    o["budget_summary.md"] = "\n".join(bs) + "\n"
    return o


def _audit(S: dict) -> str:  # noqa: C901
    root = S["root"]
    out = []

    def gov_const(key: str) -> Fraction | None:
        kind, _, rest = key.partition(" ")
        try:
            if kind == "JOINT":
                a, b = rest.split("/")
                return S["hb"].get((a, b))
            if kind == "AWG":
                return S["awg"].get(int(rest))
            if kind == "PARASITIC":
                a, b = rest.split("/")
                v = S["par"].get((a, b))
                return None if v is None else Fraction(v)
            if kind == "FACTOR":
                return _q(S["SC"][rest]) if rest in S["SC"] else None
        except ValueError:
            return None
        return None

    def put(src: str, item: str, quoted: Any, gov: Fraction | None) -> None:
        qt = str(quoted).strip()
        p = len(qt.split(".")[1]) if "." in qt else 0
        g = "" if gov is None else _fx(gov, p)
        out.append([src, item, qt, g, "AGREE" if g == qt else "DISAGREE"])

    def kat(tok: str, tk: str) -> tuple[str, Fraction | None]:
        m = S["fmat"](tok)
        return m, (S["th"][m].kv(_q(tk) * 1000) if m in S["th"] else None)

    for e in _jl(root / "conductivity_cache.jsonl"):
        m, g = kat(e["mat"], e["T_K"])
        put("conductivity_cache.jsonl", f"{m}@{e['T_K']}", e["k_W_per_mK"], g)
    for line in (root / "quick_reference_k26b.txt").read_text(encoding="utf-8").split("\n"):
        p = line.split()
        if len(p) == 3 and re.fullmatch(r"[0-9.]+", p[1]) and re.fullmatch(r"[0-9.]+", p[2]):
            m, g = kat(p[0], p[1])
            put("quick_reference_k26b.txt", f"{m}@{p[1]}", p[2], g)
    for tok, pts in _yaml((root / "materials_legacy.yaml").read_text(encoding="utf-8"))["materials"].items():
        for pt in pts:
            m, g = kat(tok, pt["T_K"])
            put("materials_legacy.yaml", f"{m}@{pt['T_K']}", pt["k"], g)
    for r in _rows((root / "daq_dashboard_export.csv").read_text(encoding="utf-8"), ","):
        if r["sensor"] == "ALL":
            rid = _runtok(r["run"])
            T = S["stT"].get((rid, r["stage"]), (0, 0, None))[2]
            put("daq_dashboard_export.csv", f"{rid}/{r['stage']}", r["live_K"], None if T is None else Fraction(T, 1000))
    for line in (root / "ops_bulletin_k26b.txt").read_text(encoding="utf-8").split("\n"):
        g = re.match(r"^NOTICE \d+ \| (.+?) \| (.+)$", line.strip())
        if g:
            put("ops_bulletin_k26b.txt", g.group(1), g.group(2), gov_const(g.group(1)))
    for fn, sect in (("handbook_draft_r6.md", "## Draft constants"), ("budget_solve_pack.md", "## Constants as executed")):
        inside = False
        for line in (root / fn).read_text(encoding="utf-8").split("\n"):
            if line.startswith("## "):
                inside = line.strip() == sect
            elif inside and line.startswith("| ") and not line.startswith("| key"):
                a, b = [x.strip() for x in line.strip()[1:-1].split("|")]
                put(fn, a, b, gov_const(a))
    lab = _yaml((root / "profile_overlay_lab.yaml").read_text(encoding="utf-8"))
    for rid, o in (lab.get("runs") or {}).items():
        for k, v in o.items():
            if rid in S["sett"] and k in S["sett"][rid]:
                put("profile_overlay_lab.yaml", f"{rid}/{k}", v, Fraction(S["sett"][rid][k]))
    out.sort(key=lambda r: (r[0], r[1]))
    return _tab(["source", "item", "quoted", "in_force", "verdict"], out, ",")


def derive(root: Path, flip: str = "") -> dict[str, str]:
    return _render(_state(root, flip))
# =========================================================================== grading harness
_SHIPPED_DATA = {
    "budget_solve_pack.md": "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",
    "calibration_generic_curves.tsv": "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",
    "campaign_profile_k26b.yml": "eNrFV81z4iAcveevYGYPPekAgZB4s+6etLP9cHrN0IjKNA1pwDr97xfT7XRVVJqP2VsCBN57PF5+/ADT+WSAo2uQ8ZeSy1UBykotZS6Cz4bR55Dgb09aiTeppbI9LMhUsdhkRr5J857qtRDGjk/n4+vZr4f0PrSz5PKp4sYO/+yejGfpdDdfxkue/fPdZHx7M75NH3GgS/ks0pfpCBAYqI3JpajqV0Rh8CILC4EvZLHStgUHldCiehNpmZlRAMDDnMLdyPqRjACGQbUp9K5rAOTig889RPYdgEypXFR27ckAEsTqNlUKi1jZ1ukQ/NZC1q3lpiqVFiOgDS8WarkErxtLbimzml09xsjsecfkbj7AkLCP6QyvVsKkFktqGVyRIbyq23O1Wu2W/jm++8CylXbebVoos1slV1uwqOTSHODGTXFXohTc8CeZW82P4DLKoBsu9oFbKLstPD/AGnpgnQ3BjbL7ufkOWgyTsIW4brTkCC3FuL2ylLLYhTUcJkdY8TeMQD3gnhBXr6XIF/bbYilXQG+FKI9gRyyhLQxxEnbk4YnbIZjZyV5tzphLUn9lBYXHJMLY29Uu7Y3NmfcDAsyDwHgIHu2K/Ds+CRmBfQgeN7X1mleF0BqsLWigZfF8oHdIHV5HvZgm8eDg1vxMWp91DoKY+CYM9kwYBPs9skkc4o7djpAH5NPH9RTqsyYiEOEWgemWHreKHS8XOajYM4263pGwp/xJYsJ8Zff9pyLSr+NRRFGbvHHpS/vKS0fKEAZh55pHzauuBhRYTHDnFFjjvHcz2PM5wnHXtSOKm/v8Ql3OSNy1w5N2WXgx0x0uwTRmLX6npwoDDP9LrEcsSjreFIyaO+iy5yNEojZ3EBdg3DQnPS/QtpiBXVdgOOylnNkvgU/dm1rd+zHp9re0l4gshG0gu9xBWwl97prnOI/W36iba8cf9k54Sw==",
    "channel_map_history.db": "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",
    "conductivity_cache.jsonl": "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",
    "cooler_service_log.tsv": "eNqNWU1v3DgMPXv/ywAW9X3sTgdosW0TTNJzMUkH2AWKBiiyBfrva8V1TMsSH896Jinq8ZGSv16er8Pj09O364/h8vj839P34efl2//X4eHXXzSSP4zxYNxwPB5GZ+Lw/tPd7el4Pww/r9+/Pv1YIeEF4omGTzf3p2F4vj7+e7is6/nVxJu3dzfnv0/nL8d3p+M/OySNr5Zenb1AHlaI7UCYFb8Pubayhvzu9OH9549f7m9uP9/ucQmasgYkKB1GevXWTMDDirQgAROkt7vLCokgR+lgxk4CqtCNwaYshvg9pHaUsJUMM00E80croYWjTwuLWodWO00V/6t1O0r1kTiDxPrICz0KsmFpWlftbcI1K5atZw078sKOfnnkhR3dzTEkInbmStP1lzspqEL/IzUwVZBRmetNw9QaPUXtOVOW82rGw2iEIyzrhE34FpvYelSIZMEl6KolI/xACoQwRJPogotCwZX1LJTRtM640dsQWQxxsqIVSJQPkbKgLNM6U47G92YhSVcxC0RXnwXpwX7MwgQJwhqPVAQFiThjluFE9KeT8YKMMFmMGM18E8GQGXGEojK8/fR1rOCiQu8KLuvyQFxZBIu0NJtOlVF/UHlYIVEblBnBSRMXEGTMqYS4IAPgBO3Fpl7POsJTv9UwiNUoIPXn2yo4iqrJdELaEWZCnoTDRKx+V7qsEA8LZMZFuMUZpyH+C9Lg+I3YVWdIvyzmdXz1mHFZ0pIXCBkFtWak7TaaeV0U0hkS4dFRglasAVY2+tOFWHAMxLtV4xhISR+S6FN5NKQ7DeIzceM0NqojUpaWW5OUCDbsvD2d30zuXAdSIldAxHSR0YYuX+RnSOhK67yO+GZ1V+8Z6TS6Y5tj0CYu2xyIK4gZwcHZ/tWbQRyoJsvnn0YOLW9fXRNZlxkyMDOtQ68hHgaELlIspAz9qW7fE9Lxx5le851xSEzdcgGHZeI4lxo65voPOZtMuH7nYqZEqrh+56pxCRDX9R/61migPjjwlMNwEdSjaz70bSCeX6ZEong+5Yj89Jwqwg4850s3vKQhglcSxvN2JuM8DM1EIHa+318qHBloisTu6vms06goz2fiNvE8bzzggJG6LMgAHmxmiJOmuMCf9dpHEbicoHhW1T+f7u5vzqcepPjrQcwI2BH42A1CEu5ttc1QcaBeTxIHAngBmiEEaBI4E8HOSHUpCJx4gl4E/uTcDi6qJ6OI+1nkQ5GojXHfzzYnEzmn2pmPfDAS+lBsvg7VkCDxIDbn69pEhl6I5D13b1/rnilgL1H2Ykdd2iy6fyXY4BjSgUJKXLXEqk68xQG3XYpUvo2yQhNvc8h30BVWalKngpDBEAsmu8T/UDSokRZ2SafEBiRBeTY/s4TMZ/WMlJsU2sSfofwwYwkkKzcVqPKnm402P7963owHqc/8iiZ7y9AbGek2kflE3ZgwMvi1PkMSTB9lRRfb/uPqK1bBufqJI+xMOfhMPuOCgubbf177iirrumej9ddYl94FAvrD9tfY/uDWP037aW7dEtP9P1m0C+Q3yojwBg==",
    "cryo_property_workbook.xlsx": "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",
    "daq_dashboard_export.csv": "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",
    "entity_alias_register.sqlite": "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",
    "feed_layouts.md": "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",
    "governance_memo_k26b.pdf": "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",
    "handbook_draft_r6.md": "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",
    "harness_dissipation.psv": "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",
    "heatload_budget_published.csv": "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",
    "ingest_catalog_k26b.json": "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",
    "intercept_register.xml": "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",
    "lk_2sg8.psv": "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",
    "lk_3am0.ndjson": "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",
    "lk_4sg7.xml": "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",
    "lk_6jt3.jsonl": "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",
    "lk_8in5.tsv": "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",
    "lk_9tc1.csv": "eNqlm9FOG0kQRd/3K+YDbKm6uqu6+xE5RIsUwQrY7CNCYLRWiIlsJ/v7OwYCQzB4TkfiBal7mJ6qunXr3uZ2sfwyWc1/TOY3N/OrzeLH/OJmdfd18mWxvJ6sN5eb7+vJ9Xx9tVp82yzuln+cf+pM0yRMVNSnotNQJ2dHZ+eHp5OD2fnR58PJerHezFdd/8wu9MunVutEH5f3P+8s1+3ykOXp6fl++fnpwV8X/zyt36wuv3X/PT9fPL7c8OfB6fHh2dnF0fHzrn8vV8v5et0tli+2Wti9dfbrvqvheSI5vqdEju9iYHlngcUiCFku4VUsDo4/nHz8OAzH5fL67uZm8Fk7t0iObGroC4XA0g8d2a2C5Z0E/fnuIUyl7P9CD2dILA7+VEJBpqG8VxMPz2cl6qYkAlLCmxU321FxP4tnc+t598aTv89f1+rd982wWK0/N6q7jNLE0NNFSkNl3GMheSkZDzWb29j0Ro6qKdSwC51nLzNxiJaSwBHcfyM/XNG3LY5QxzLCtIyyzwPLi4zKW3qA3Z0as1ep8Rw6M9ZanC2PzhrX+M+/ubXIMF9Qv3ItrAE5wy2Ul1YT+TC5slYroHgtKMvK2JCVfbAQYIkNG3RPHfZQvKcII84GkQcFQQa9fPx36iyxtDMEWJLeoACvUHpIt5PyTRYZ3cusOAOEIYbTRdi7G3s6SjuPiORZZEntkfEnG5ZlHLKVzydHH16z5i14CQMv9kYhNPGnmGi+IaZtbxOi2S5CNETKpKA1uDZN0f3GiL6zJZbkCfJybYqiMhhIrNNZwjJDZ9kpGJDEMuXKhwvD1szwKSChxAp7GWFQzFp60tDEZRhjcmOt0EmzEs9DjSGOnb3ukVmZnCGppUjFQ6PQ10l9bh11quW9sfWxPiKvD3FrH19dGLVQ1gyVKAmuDN+i4uzf/hFYkUzPKaxWEmtihSzvtoyf1LlmMnZFpFh6ZDKaBgZRrF2X3M5vjAnBot42bxqpHFMqayCRkmGEswqrbAQcqPw9psqYybozY1p/NJTbAcobTKQzY0IOq5xEYmvOYqW1JfdFrKlRa2n6a8/zSs9AJOyTBx51WSZzwC6iJChbZ4owWCfZ2olqiw7kAucIOM8qtfrQ01lXRrSls5SQ1VeVWR8Op8QShlaij3PVHlJDaotPa0b6g1UUO8nKfHyLDF4VWmmM9iBS1UertDP/bWEPcM/2F/bDiBLDG9bzu9ssM7ODFfj2xsCAFKSRfvj2TgWSxVKTAX0fWOhqMcAyKG5BBjsc0ftfRkVcxBvAwSpjL9DOc6fATrpMMNaUmB/j8WXdjZIhHulsRg3K4FBKJhVjeoMLs5wltzBHD0bvxaAe4/C6VGI9Bl05MWYjS2ySGK0SEmKC5i2RJs/EU2H1mSmDRT4XIwbGpM4cUIZ2zmw3T1CSZ4oAvIvAnCBnpouk1GA5lwrvK2mk/ID0jhQbHHAXGoXxtp++nDlG0rXIrvRGadIDiv+GOJhZLsJbBhVOyRCSmLhTBea4QREkEAWUGW3O7GAJbf6uwEsklZ4B6T6s4wjrlgZFEOyLEs3K0mBiiTLu9hW6eNizZKf3guEsgRhpav5nhFIa4W57NSbQO4bQ1IGyOlnOrDcpb1zo2yuTTZ3OU47mKQYCzMuXos2KB7vitpU5f1Fw9ljlmpsGk4JmYU+Jmn0DTa2Ok0qMaeUeBTVGln0VdYlQYnOCMFHewf9h/A9XkXja",
    "material_lot_certs.xml": "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",
    "materials_legacy.yaml": "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",
    "ops_bulletin_k26b.txt": "eNqlWdtS40YQfecr5jGpisVcdH00hmyRJZhgp0ieXEIeQLW25MgS1Fbtx0eXEWNkq7up5YmS2jM93adPn2l9Xc4m0r9g+U4XcZnm2Z49VpuNLtOM/ZKkRVJt4lKvf2NZXrIkz8oir9+ufz07k1z6EyEm3GfzuwW7uZVsrd/igu3f4t1Or89u58vr2RXjQnH2g/0+nS3n9+xllWZJobc6K1fbh1W96+pr/VbY5dx2udc4qaote46rZ80KncSb9LFoPOkMeTQRXmu4K/R+XxWa7XfpN82SjY6LAyvJKcvZY2zy52dd1Cb7Mi5K85ZPRNC+vZz+xZ7SYlsfUzcR0dYgQr2prbg3vono35ZV8ZizXbXdsb0uXtNEDy2S+HGjWVnE31ma7Xc6KT9/Yv6JSHdne9H104IlVVHU2WPJi06+Haa5juAP9sf8+nbJZjfTP+9Wi8X5rMktV46wZqIxmz58YS0suMO9gyXE+xIX85vlanpz/tCsEPLIUdZMRvXDu+n9dHFdP2GL2eTyfLH0mvWEy5s/mxcOxrSJlwcmXnQRz/PNOn/L6qRv0yze2CAGlLwLl4rCbrn9S/pUspc4W+evunh3lYdQIgYgA63qndTosZughAjeTbmMOGrKZRynNjNI/YoQ2sdgfcxNQUmP3WQEAmYNgODqvPSwvbqb//Pv6ovgHfR97sghlkacsejmfYGEXYHwcEgAx74M0jqWFw87igj7zd1uc2l/LBBMSBeoFVtpACpq/8VYvVoXg95F2bmobIgVJ9EwmG+hxt20SRLGCdew2AcaUx9pbPZ3S2NSSenwg74obV/c5G+rMi/+q/TqKU7q/9pVA896JdGqtglGrKQEUfS+2SkU2QCN1WQEEQtc9Ta8/pDhZzXDN5AMA6+n94YRIwKkXLxpAkdqDuzhdGaoaLRRSEHibnHKDwssftQfG5qRnuv4NgGC4G2AeEsWEWCjaCLrI1jjiuBuiHbxEEqggcmosqp3UARlFeDcZBO0mN9cXt2v7i7aFPkhdyILW1JborT7Gt6SQnkS10GwAA5hbjcKBxAMEtQbAemoCGpNmk+CQPThHEeiFJRIKpKVABt1fWLTqeBwI2xhaguxIjpMErLGa7hYBVbxEl8EhgvqhhV1OIWZ0h83tNXtmaYvjTIL7W6SAL2xnuiTWjvH4OsikDMHBVaQI0VsI6D6CHTyUPIhDwHSVJCO6VKo0QAA0zkRVGOGc8aSEoC/dangCklTiugT4gC7zCgEBqM8aNVXeOp+3WTclUEQDFkKOxzYmqVHQy2mGIXskdndCpQ6EoCjYsdDehst7ifBZmManFK07cxCCR7xSAxFLZBBUGJL8fOzKsp1j4eYqOrV+TCwVs8GxyOj5qYU+aHDh7REmJ5EsHp2P6pnM5/yPMcdzjUwSBMRBV5LSKxvSIrQnFrcfwDY1BStHyp1OD1zh4YXfXVHwveHfRHTIB6RCRX5SqHAQhLihMRuQOPyyDtADXzxsEkE6gQdeEQk1Uq4jwkYuVKdym1LHtI9IA871cWuAyEoVyQWGdIwgjIbfddGAElEJ6Zr7VhYqKAuXTtPEXaekmbrtNraWYpwPD7s7eOXVlO/gIELjkB87FKMDWAMsghlz+XRrKkhNRVEjh0eSawWBHgbIRLwO/iwLwXC7Xu13/ZqoYbDawB62B3wMyoTCIgkJ8A76ioNOH03PJz1iagfWnZH5gdnJnyjwK5UMiCMLzDQccoi8OwPIw5O6imwbkdHDdL/xD0e//zFA6Kh2fdnP6gNzonO+seZU3qnOn33nSz8+J3MqBG4SSnqpYccCEUaTfiE2z6Y8/8BqdcE2A==",
    "output_contract.md": "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",
    "profile_overlay_lab.yaml": "eNrNlj1vwjAQhvf8ipO6tAOS7XxQPLYjW8seJXChFsGOHEDKvy+xGkpDG1yTiGy5kz8ev757nQfIk1TpZKd0BeqAOk8qeCw0FonGFWRKQ6FVJnIEjQdRCiUhevLSpMS4SXCIvHqqFqskzTHeYFVyD2ACZSE2GG/nJlD7XS5QN+FWyOMKyUrIdenpvTRT5ovXyRuh9Sf8GMHh2eS+FznuSkyq2YRDEJpEinL5weGFmag5S5xWvD7shJq0xhL1AeNiuYvfFwEH/2s1sZbHwSrLOBQo681PXOw3LkYuwHzSJpsSGzLmTObbKXYJZieZPZhUJ6bAlYkNfI3hsGB/iEU7xYqcS6sFRXuEmg4MRV2gnvtqQtpjrc9GCEWJo43aIVEXJDookn2RtyyBMldLuEkrCzDfUbC+PfTsDgPnWr/pfe50BRoODOXUgLamHvXK1C3U1JVpQFcYj6W322/mqtZND+B1MEbuYaSdt8hoT/+gPVYWYyP0Kubfp9yvvzYsGEu5n6kVDmui/2/BT0COVpo=",
    "profile_overlay_site.yaml": "eNq9l01z8iAUhff+ijvTRVd2gIgfbLvs7n27Z7C5KtOYpEDt+O+r9kPTkpEQ0p1hBJ+cezj3egNWO4Rqh6ZQe1hVBtwG4Ulta6XXJdSmWukCR0tlURrcaaurUsBsdNxhdK6WBcpn3FsxAhiDrfUzyu3D6aF6dYVG8/W41eXhBJXrcm1H5rU8bXl4vB//I/T4EcBu9MoJKPV6404LBi2aHcr6ycn/jxMBlHx88fNnBHB+WsjVi/xEFbBS9mv7TuMb5nK5F/CixpnnUE6+Tz0eYpRDaQVMP5Y2qiikw20t7wXcMnbHb7+hWQt0g8U6VebK5F4e2sbDfvFQdh0oawAVh50deVg4j18feokzCcBpLRUNL1WLNA0W7mc5+2hKUmlFYrSaNvhytffbn/E+9qd9y9tw26zF/udbL2BBAt8j6yp/llT+ud8el6/CCOkgNUsq9SIkabqXfR7BQkkLy2W6N8rQs57hkOQMSWOue4osChCQ9YlFlrSW2XAdLKpsLR3jh7V4j0wZbjS4zBPKhxM2qv9Rf3+J1CrpmEBnXrSoLuLrhgOr3PDvvO8A1iEFAwZCurgWg0ONDwFwjPS+I0l9yKjXh385zDdwWOi1GML+8yjkzIvsTW/fZNVjGmRprTn5m3sTpzK/EuWdXZDgX/EhA98Bk06x8w==",
    "quick_reference_k26b.txt": "eNp1mU1v3DYQhu/7K3i0i0ah+CWqQA/Odt0ENpJ0vWmBXgzD3iCGv1J7baD/vmzMmaHeWfmyh0dDzrx8OaLok83S/PHlw/LErFfHq/Xq43Jllkfr38wbs/u2fby7uDWXD/dXz5e765fr3b8/m7/e3r05MQePD8/3V9urw8XdxW77eF0e+/G3OT/58XuzWBydJpt6U/9c/e27DMTTE90AJNATXQIS6YkuAEn0RBeB5Po7dA5Ib19/R01q2n2PoGbQ4/yujtVjma5GOI/11winyq/AYyWxgoAgVRBxjqGChCBXMGCBo6UHlFivJI9Kq1cwKlAL6Xs1Vk24hCKpifXeKoEtjYqkStxHRapie8gQKRO1LJbJu/XR2ZkndcnKthsHQJ5dHoEEdnkPJDIZgaTG/1OS2eUBCHk5qdHIy7nsQCCRXQ6V8gMIKAInYTM7rJ8ATk5m9liJRAIgMwdUn8wcsQ4yc0xKLVvnUmJVoCJqIQNKQl7OaqiaVh6UunXDoFZk5FHLbiltJOTj3qoVkd23/HK+2nxWLdkh8bILgbCNA5Io+wYI23hAQjYOirCNVdZk4xQVidTLVKXknFERilH1eHab0oDcpLKO7GmlgZ2rlN2sViHPknGWkKH3EDdLakFBa51mSU0uWK31K/Fa6yr2npg4G1N9rQn52r969NPx+yX42o1IyNchISFfRxVDvq4OaUji1UCSRXNEPbdUjRyrrhD120EhJ91EofkoP58G2XvUUtjJBmulmG7XhpC9Y1QiTTdLQ9jeSatn5wjZWy0T29spQvb2iuS5GLJ30GpP7T1Zh4m9WzLMxZC9/996v/f2fLnGtm0765B5YX4AFoTFDCwKSxFYEjYkYFlYxvnI6YWNijli5cwBKDLyWDmP2GOSTqJwLi9RWHZgpJSMghwKIigAGgRhGlkQpjEy8laJaAk5pSEjXBayvO2CkjcxQnnJ9AUNSnlGI6Iqve2iU4tCURGFIuMXlNV6UVRyi8/v360/ffx7hR+RCYhvjtdTIgfvCIRPLJ0FIgfvAIRPLJ0HQnYP5eANxNFhPSOJcliHSptPUiByWAcJqKVjZuTysjNAAH51YP2Wv1WnYOCDKOoix/spGPkYqvSqTdEpuSx99gKohXisgzztlfLUxnslL3V+BNTEo5LdzoBhJoI7eJFkc7wyZl8DH4E1Dby8yKasaeAB49oGjnFNA08Y1zbwAEwaeI9DTvo3oLZ/Q+Ft/wbU9m+QxM4i6d+9EqRt7aDHPGr6N9aV2xfCFEn/dl5paOVdgRrOI+7fDoWS/q2j8myU9G+NuH9rxP3bJUTcvxWS/l1Q+RC1YZ/zUwYmzi/mmCIxvkMkvi99ZIrE9gGRuD5iGmL6wSNi049YGJ/PywsDSqbGWF4yQOhCsMPRyPG+wxQCv2SUEHSaLq8S0KG5EZoScvugsiazZ0X4XlBlQFYfVQzfDKoM5GoQQZoDdDHolNB0Y4iArgUVoNsUtWZ0mRLVwtA94mLzIR2dhj+VsRUSX5fmMEXi6/J2nKLG1yOgxtcZkPg6IRJfjzgXf3d2irCtMXW+GSzmBRLloh+UsHJGAyGsbAXQwcrlKMhg5Yw2JQOTAfXh7eOA8CenqpQ/ObuodLN84gNSC4p6tGT53xNAsuUNjFrXu0ilG1k7qXrI20nNQ+ZOe9anXm2WeRZn3x4ed5fPu1/MP+ZXc3OwOb/bXtwfmp/MkXlrTsvv1cYcPG235unh9mVrvl9c3pin3fa7SYfd4mR7+3J9bx6+fn3a7sqUvlv8BxbFpbY=",
    "rd_7kq2.csv": "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",
    "rd_b5n7.xml": "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",
    "rd_c1j5.yml": "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",
    "rd_e5x1.tsv": "eNqVfcmyXbFu3Vj5mFvsm1neD7yBB5mmXLarnitxnDixvz9c4G4I3kOcZWkiqZZwsUEQBEg0//C3P//0v//1H/723//l//75t3//X3/+4+//559//1///P/+/Ns//cef//jXf/7H//IPf3Phv/7j3/8f/8fX1l3oxblS3Z+/c/6P+/GulVzDn//xr3/7lz/jHwCPO7z2JvD443xKucQV7n/Dg3/gvdSYFXXNTA0D3hZmQigGMwNeSn6oh968N5gZ8NgfZgbp0JrBTEtu/F6YKTEZzAy4S69knIvZYmbAWw4PM95nlwxmhiTHH9QyWZIBvASamQHPLzNflik611y85H5JJrcjMwJ3ixLYyyTw2m5B+uhTSM1gJgziKazM+GwwM+CpRlIyAh+a8sCb780ZzMQwuPfkMgl8KCUtmQHvIZEKHF1KrnhLMgnwsPJeHsnE3NxQOIEPyG/eB3WfeEGCmUuBwXsCPwbvubhQVkGWEA1BDnhaVOwbMwOeuyM3XxyMDyVYzVLelCDu8JZfyQziNRnMDHgJjV7VwUu/FJiRzIBH52lmAK+d1vce8H9WyfRiUB/w7Ivxqb/gPhqC1Mz4Ya5rjIqZfqYOeH7l/k0ygPsQ2WXyvrihwiszxfhUwH19tvbQn5KCwcyAxxTY3eQDllUrcDKYGfAY2XNV4CHQu8mPc7Lora2pb8wMeE+V3dqA12U3fZNMHhY4d/KQn/DoaJ0Z8JAze676klyPgZbMgEcfaGYG3LV0Zia49TgA/N5Nvsb+U4b+/st/+8x4Hdobk9p5wWB8wIPnpTjgrVV6Sdswv/8JZR/w3nn9GvDh87JmAO6Di8q9zmd/WeChWKfkL3h0lTWQwQ/tdZ11lQAfloZdJsCHu8OagRDS+FSlM9ZZAHh16Rx4bNTj0Mi0yn04xAbvAXujG7zHnXrNtIEEfPjYtGTSUGCvdaYazAx4D7QZADwm2lqHEcF5xwYeAh+OHrubAO+h0rtpOMvNJ/aEBzzGSksG0WfxtGQQwekTvlnUB7wsvv7vs+AXPNV8dgg2ZkYE15QFLsHSmQGPNdAKjDje08s0fVR/3nyaGcCba4bv09aDCXB/MeNz7T9teAfPweR/kfbZs0cHDOp+jhn6FZfQ8/tliMBz6LQUI8yvirKd4egDni5m/voXg+wIxLLL52DG/yKbFx/8i9qC+tAVdv8Dfp9IxJaLI25r2qpbBxjgvRRWy4X6e7f1lRnEbZfj8JmZoNR2UC/11i1ocL536KfwGtQzH0QCvkQnH5apKmYEXi7nLtWfMLbF2EMXJ33HhvrsoTiOspt0+CSWhhPAcO83xge8tMievICbd0kbfESQLdL3AoCnPtco/HSXYrKMrtwP5sbGeEni08QuKeDDpJwls8FHSBheF+ZbrAG4D/kcuW/wEeP12j9/6m/tBdwl2icR6s3RvEtImNlwA/BYG+s6phG0uU4bSGHGZ/ZOA9Rj6mygL/AlOvkmGQRtqbMHGODu8mN7/Um+9hytby3v2UGcYGkEbq451g8APKZMK82AF88rjcR5jQ2uAW+dvUEX+IhTWclkh1A8fjqs4y9co91pwGugQ7CMAK9WNlIG3C1RzzdmEG0GWlkyQrDivotk4PK7gb45XYCH5ln/JY9QLQfaRgPurG/0fj1KAa9XqOaHAf0pSe5U4id5jDjt9hY/3hxsjA949Z1mHNSfg9GnOg7WD2HdZNy3ItfCg/HuBjyPbxjRvqIednhN/oH7OAyLQX0cu0MTH3iCzTOoD3iHFeKo13GOdkjmgg+X3bUzdcBr4qmPc9QhxjxR3+DjpJMNzX0qqEe8zk546XAKDHiAS+o+8+5/MzN2nG+dXVWBx0cyw5mNn8z5A8+X70XKPeMx9/3UnLIp93EUtRAN6m2nLk84A+5zxw6pr8O7cTJIpxLPQt84qdddPPmdFS+5iaaO+8bSaIVp2NeVXSN4087TawR48o3dG22cAN6nz/r1W+6AB19ZybTBqy+dlQzgJRhy92mHxzCVfYRrw/n1ydgbbVj21CItmQHviyC/7LyGO7se6FUtl39MrmqBFjRa7nUsUyo0dVzCvfBvJmx863AxeSUAPHTW/DbkRfA2CfDlYPrGTMc1Vq0sdcBjLazOdAlLaDsDeAyB5h23U/FdpuHIlGxQH/DQHE0dl06p0dRTmo8s16fG+DEp6YFnPD8F1hIAHgttI/vwZlJ07F4FPC5K8G1Vh01todGrKiY403LHg/tpr/62wID7zOp7x0VPaqxXKPCcHCn3Poy7y56VjMBrSTR1udDIpM5MeA6kFesOrpLjBTm8k5Q9zcxwUILlom5w+D6u08xUyD3SqzrgqbP6Pmze2B7N09ThzzRW3/uIScfXGhq5wYfH0T3NDKiHZXv8UrEN7q8beU4yfuh3f3dTaSOYNFYV8BAqaSO7lzdIx6oY4C0b1Dd4kmtc+lMBX+z772VS1AssgVzdBPHF2rBSOsso7/Aq1/43POmLeV9+w6PAR2hQfmLwe6LDg4UZkMuHh5NgcYJEmtZpTgY8y8vWzUksR06GhRHX5OVku7nLO7zltHISq8FJwjHTV07OMsnISnT06gx4zmp1iiUTCQtXTvwik410QcKjEndOhlrBjNZVJi5ZMkF2TllXZ/yok0xgQ4PS2JQMmSB/RtJ1Xz0JBicIIeVV89HYMycSEHZaT3Dt6b3Sk2hwIta8rTJZ9cS/V06+V9jmVBfSPoff70hhgfugGPf9zDjgMzOLUnCBy13m98Wsw47LoXIUYfkF92ldnXTSWGCTNhA1nzW2IoatgTU/gM+EhlcmFuOgrhbTtaNM5DhJ7Kavko7Tzwq+UU/IKFTf6brBOJgJp525cTJIe60nmwjLDu/KJJ8PB7x2eJ/V6kRDJgOeY1OcGJse8BSUxsYjJyPm9q7SqzPgvayM75522eGhloOCb5wgSSau1t5tbwZ5h7uWaY0d8BAXToqhsciQydmQSdnhvoX1I4/nDrDdp/NKak6Q7RJjYmUCuNMm2dJYwOez8fddjH01n2kpeyLwkFmNlV0b4uHo3jjB9UNSerKdgHmHR6ckvomw7PDUSU7woLty4vsWXOUdHlxjz51J3ZuHw31gNtxTtJu0d7gWSSpjRDMu6SuV9TmEujaElm8KeHWB8gjl/Sc1Wq0GvKqdGbthfgDPpZwMofI5cGNdtM9xm+RPPgfgYbVWfny1wTjghfY5AB8uE+W24fquhMq6bYBvTrVpI0BduyjHxcRdRtWcOGM/AC6B48tJMiw44L166izpI1DrTXsFho0Q+MZJMjgZ8ObX8zWeOUF6S46sbwp4SVFtNcOdATyWfDh6Nk6QfVLrOYZZ874mPF/+pq+p/DS3PEBvXKOSInfWxgpp7ziu8TTYvWGqyg6fiSHP0hz9O2Czikabi+ezGJHuFrxuWzjv8Noqu88AjzkcGN84QTpLjKz3CLiO6+zVQcgYy8mdab84uQ5XvD+jDGxJDtRcI15MmbVTgFfe5wW859VO5cOelDqLK1OK8HknPLTEWYcJvyMv24NACjHyEyrny0y4PqMM63DBWyIiV8lOHuqcOO2e8O0a4qzdE14bc3EmT0sjXsz06uA51ZMXZxPucidsD7zM9mg3wwkCQBVyG+fZhD8G1tzxAdlOI46qnJs04VHdgtoai2i0uZO3sbhJAUljV5XS4ybFo6c54XKXzJiqC55JF3nCszKa4bzp213izG01xIs6UEsWJ3hczo5TcLwsO33j5wxO8LKsFdxcTFDvjtr0I1AYPkBjFdxLsUbhbvwmfGZUf3NisRTuKgagFBzwmB2rJ4DXuJgfqOSJE1QxaNfR0ljAvVJwc9N7KcRrxNVMQGg+zHdlTbLA9eFwvpqZ8BgKx4lUR/CcAN7J4H/CmwuUSfaoMHicCB9yqMU4Ab2El/4Qim5cI7ZMxuXJxgkSF32n944wks4PDhvjCADVBetqT9YEzST5R05qBiOeyFALFpwyyYtjP+FZ1CrCsW8/reZF3BqL01LC8xub2xE7zrMkCkXQBdlI8gAj70gepNAuLtgSj1hc2+VC0UX+jZPUYAIL29Q9xQNyY4qcvA+2H7G4PpIrNYIHXMH0euBhrd6e2B76jXU/Na75jmVVNWSshBAfVeux3mng8RMbA94LKYp+v4UQWJxD7UTX952uJPMJNrufEbEsIcpKV9JOEMEQyyFJJLPZwFd+JSWkcsss+SCNW2ZJ1/C+czzgCdMVjq48OKgtF47Ydpf7fKcrWRGJ2p6SEtEi921IcPDBc1gpyI7UWiD5IHmSLvpXucyYtO7RjUqZP0Nm0iwqnPgtCgtXsV3rhtRlBNAHXQc2kvqLTkXZhxN2CRAGFpd+aeqZHHTylHK4ZprwotTdYANX+TlQSwc3zOXKYWEtK3Vy9YCcvVI4flGskBy1zLPtiqf4jbhn1SfXsj3XOpKJ7beJyD38oHeBqMQHukieiYXjAektnTNTUV7qOPMX0QelnuiuTlKJTTrSgW5CeXf5KeqmSmEl4VaczBsbfx0Z/sYiXJCkiTROufFjXL896fCJtMDLQtqd2cDzkjzoPSwfPw8Hfq1+waZ4xOJgdisP4YxFeXErHA9IIu3pJDaNlZLYzPALkzaC95WH5I9YqGVasb4csaFdPds+yqErrFiISyXGev8g2Hq2xkZXClpW9XHnb0Pnn7bKzJ+xcqms5Hv+NtzjOn9at6SwDY5aE6yUkMexjmtMsJHGZau83Dykj8uBgznmlWXXjlgpwc7MDk04xGNpjAonHOJdUr0+qeV6IA0sDvGaX1GEXI+R14T35Dk2JNHCMTspeWlY6Tkszvy+aHzv/YjtqG2NzA5NOMejX3dSPC4zDuagdvN5mXEw97xi/Rmb5LGIki8O5q4sq1rmtGNLfIx273VwdV5mnONZLV08syyPt4UTMZylThniJOd4CwfD5jQWTeLKg40/I4A9GSvBKkNxXmac406pxHmH4hx3nbMSOMdnes53wxZh23LgeKi3i0vQRcphCqc1XtSnOznoRNWyWIkhmKRvfxYXYcKbv+F+2PDiLTiORrFXF9z34E8VZRMe5O3rYSacqXspruiK+nY9t1IXuNRDLtSDQd3fdc4P9dRPhcsTPtNC8xB6zj99bpbwiRN/Xz08nERvcIKkZ9kDDye+/f7OFX6vUfoZJ2CpUXcp1cyIRxtv+DhjklMJIP4XfDrLD+/Z4l32jloj3Rxroy4dgsNC3XdrjZD67BR17wzqePmWRxxG2T2clPle/1JPBnX4NNmv1H01qKMqJKlVzcGgDrjivbZswCVLOdNbCfCSzp+q4bPMY5F7iNveUMwAXppn5Q5PK4i9fZhxhmQAn7dX1L6WSxP9qSZ1pPy6pjTSWFUv3RGisniWZHArUxq7m+CkzcbPlM4AHnpnlQBuXc+WPfU7vKRyWbySftAS5mDx5JbIp4WTHi1O5KKosTsP8BYWqzE8M2dQb/C4O00dT6J95T3q9K6NOhzTR9m/a8DTZ47aG0Faf2eWOuA9OfakkUssTd06UQHvTZ0FxeJdGqWpnVcMax2kgFaZsHx8abrgWR+qQYV+mvrT5O2VuyWZJPU+Z09mg0u9rWMPJnH4S2fNgDjxvrIKDHgrhVYCvPDFVYGb7gjoww5vypnx99b+ZAmm363k7gxrjbii9shaawlDGr2qUdyTYPh4ijrg89KWEiTiEd/C2ffZ4OHOo2GcZaHeHiX48KkbPKCfXWO9E8Q8UfOeDHcjSosvR8sdfltvrJ0BvKXVf2hbQyMNx71VrKxJBXxzr4Nh3xGJzUQTTjII3DJ9BiN2qykavv4veK7t8fXT+NJ0NnoSGSr3OljHMDZH7uo4KIadATzGxMo9+bvPmxnWhAU+H1UPh40+DgAvTkUSr2Q+MIPsgDWwtS0B4C3RJjVJ9l1lT23AZ6t7jjqu7nJhY6z0JCxQliAtbt7H7bFRRw6etu+WT5CQ5eAja/QAr3WxM2gcbVAfrpuvlgKrGB7w7sMbw6N53psSkHasD2qNvHGOJTxRBsVJNc4xwGNT1KuhARleoVM2KRoGEnCvt9KmX3WH18ueSipBKm1vhfpwgkchtalbNzZ1FodzPZVKP95eXvBa75DD3SlTHzmJ62XS3NGGZgEuLU+W+NrQrIz+K7GzfgngLRr2Yn2imfB8K2LN4afPZ6KP34lJLVqzLMsF+KyKf/enpVkyqcWxux/wmRVx0iy9nnLD3O4NV366X56iNk7kSS6zsS/guanvbMapnnH1qC20daoDXhx9C1aG4xh13G5ZOcBTqufIZ6Pu70xZStMFXmgnAC0XSuGp4yUyOIP6ekwX6TwLe9GvHo6x3JYr/iq8mPAGy9X91aQu1s9FGgOL9z3fF6w/Y5H5gxDpwYZ8xOKNEaczgUW70RAVv2csquL7is1nLB4NYdxeHurnBM+BhTfR0iVi6dOWlSe0kR7wkv2JtMbK6AO3YFM4YtM1dOSzKNaYEgP2hijqwrLTncA30oAHJQ13ZAOXP25dvXTGSoVzpFYPubxyuUFoRUEydFnp+jMWlyZhYv/6lyMKSZJ11d94/Cqs2uzrdGFRoHnCStqPUobjAksHVGkARXzV/dLz8nuki3ajUe2L8+qiG2hTCnlehRruPksEXTzetoffsL1MK+WtUou3KG/ptZ33m/TdJPcQ+m5Wtcz+jK3XBDdTcdANUybYmCgcvVLa/NkmuPXzpUdlXD8/13hqOzrh3pdXsu2sYUjh7qTWSP/IwO1dpHD7UtclyCdrihTunPtqTUM5myaB95W0O7OM4Eabm6NCSsZ34MyNZHzHTtGVjotdmcePM62GtyuTBmZTkXJ5Bnsr9cfZu+Hz1bP8gXv248OZ9JMVfZPeJ3to0jAnEr3fpGM8kZYZA5II+3C9OfqKdBLrExfSyR9Jg0uTaw0XV2mF52TID9RTWjlZNXrDwmmTF5FH1vnINfpkycv1K5BksIH0Mec5WSMlzCmBnMKBGz6j3of0UUOk0X4LSvmCQVoGx62k/Zl0RR1PWUlnQ/kAb34lHdyR9NNinyON20CJeb6Thqsp3aFPyvfeHN7w3CfX8Wf8FWn16n5McSJt9hUn8WOu8MvJJRCMTrlyb+MnruH05r4KpBrLCHgp3EaXdvlVCcQbyidt8K+luTQkfuo7IthYrq51N2mXDwNfbrjrjt1hQr3U9SPPqw6vOimF2oaUaNJSqxspGwznfvZteeSXrKVBBNU7xzXqXdXJYS8Nui9Vz3GNOzxXWPMOuFcmx525lrzrcBbI6wg98MeujjjJO99UHo7mBN2XlHlXFkph4eRWtQ3OdgHYpKzZPg1XwyV/rbN2tUgBa6A2JEKZmmldBdyRex3xT1fGb58zpEkjxbxzrogEubWwrgjgc4jdx6XRWLzjutXkuOMpLQOWq1qXYmwZKQBNnRMeRhTHrnZjNkgjqS9kSngSuznPmneBx3CwwRtpuEOVdgCqZNM7StaIDDd7bTlmgEu791cgZ66fljGvrC3SUpgXONLyqFrZ7SXwULllLFerf075JExNnjJPMuzBRZprjJJw3M6VwRApsPGJhMK5Ui6iBMRZnzKGvWkyQyJSZyMC4poTqyESP5fjRtdYvFq2Qm2vJu6QN75Qw5H3lh177ApcCeSs14jOZ/dhynuSYN7nwzK+7yw3tuVLUVEK4/OSwrbRLXcS43fNk6i/qJOuFkN4FT2p6J0r8yIq52nhniCmbhyMWZFu98T3CR9/v32W+IkT3ELUcpKJxuJJ06VTBKG5Fl+osoG0FLn5bohbcQJ47YtRTett1kZaGsMX9gDr8kDJ+SyoiZPL82VpDL0GvCln4ax/KKHz+tg1SafrWvHzbYFXpFE0Glavdn/fDzt8dnqiVBvwnE8nR/A7drZuunS1VFfPQdgsylfhYLI4kQldmVvJ++b7pH9vgv4Nz5djG39CSB6x5HGTAR5y4zjpdxtPylZ28fwcc00kpYstJRXz9s/ZwTc8vZ5L+2nzWvvDF86qyE4FvLMqUttKnTq2kQa8fLLa/jdp+HHq+s7aNQJvjhFexs3q8IggjTp11SU9Y289l7LMrZeRVgMu1cBxvYUNizYNLBRVYhmQRgt7X9XJG7yCI6FSfDOBj3/DOLT1IxV1PytAH+oR/bg/PxYLHI8O4hfN76wdmXXrnswKjpmQfn5n+BkOWKmnZFDAZSKruEY39bD55fWFY34DUpFwlw255vhT1UNXeiU+sUmeEMN9ra9TDN/mITdcbiSEdHI/XfW90mzgzgpHyMNG6kc2pJbBr2zovIKNDcBDWdmoR9IhzXuAl3SrhvDCNYz94XptLLixEa5eDR/Z2OjiebkvdEM+LwouL+QpiVsUPHTLWJabjRiObKA0oobD521sANuUbujNu7EBuAxfJKQBRzE5jg1gPc+G9M6LnIpKr6HEsVHDvAVbFqUabADeSTbgTha1U+KRDcG6lY1q7ZQm00AWNrw7sgFj3chFuduJkBsWxSFx1Q1V+qrYiE6izJPdyDu29XSx4dF7pKgGRZprwCX/ehGeoUqA9xIo4UmjN1KjZaDatrG6wYZoUj+o0kYaznUpZy3duMbVZKwHzdvYQPOq0rg1lNnX8SCN1Z+Y2Jkgg95nLf7kiQ2fPg8ee4hK7awFRD5hddQmxEV+Vtp/Pq6AbV6xkQwDHcVj7xwb0nIrc3pUru7RpB5J+Uzh1LlJBhfHBiKGqkxSNGyBwLvn9Ajv4cVTlhHYkpXqa5dtY0NaEXbquJLH8FAojwpYaShxWpSNtMzxzZS/IU/4tR4O+o0NZDv2zh5XSaq+uXMCj+xhPTWjO0tDrpTVqZksNlBlnQv3hdI5LZ6PoI1rWKQUDqq0YTG4KjfKFgCb9SY0BY3r55wpW4DHe+8LtQmBTc1w5DfSkvjpObUr1yPT5/MnKCzmVfkpZYyqG7u9H7Kyb7gk2XL2HPDXRn8RHmIs17k9ixtzvVksVcJDP1rhUsJr18Ai4vAG3dvMEPZc4PE5kP1PSOkkDSQQzGTYRxr5yMbdpfzEhs87XC7uX7hXeX8b18h8KJ2KVpCb0JUbcd6Hkhqszb91JgOefKBUKcc7u5JgQyrb6TAB8JlUTahHao9/fmupcbIAHvNpA2xsSCYg55/jXVj6fhFWCdiZrvcG39aiSFjIGUckR9x79tv+BlZacC+uQTLYQF29OmfdeWPhoaF5ThoN9Q2NPQwlpcNz1k6SLhIXyUrGRSzs9QLg0rieuGzBPvGVJi35HKR/XuaAg8N6v1NEb2y9olMZOjrilv65NvuGu57YsFBSRVylNkuRcVSdMh1FYrfAHoZCOlTKkEqeSPTUZgF2Dk7n1hAp+I3bs0UmSwUq3AQ29FO4ubGMtgPdsT635J8kLrgBtrRESwOFA9m255ONJgnwXh44GlIRR5iIxMTDk9KA4yFMLrzbU2Lof0/SXeFJckqEekA/r3h6nJlwuQq7mBkHU44GMwjEU1uY+diKYYUXqZOf1IfUczao56ss6aXuikE932N9OUFKcUdUvDeDOjRA0hI53qVZdT4v00YdfSGio3mXkQ+BlowEuZ5dVRTg+daVZNyZOuA95jPvGxxFKoVnRjpuK2aSIXeZqFyVRgZDMlKvl1/eh8nfUrQ1dQSbUWlkNnbTHKpcz5JZrcaE1zA/VaxGCG6fq/SQRm55UJxES+joGb4YmW/f+aSXv9QtDUBomGirIeOJvad5R7hXed5HqFWq2tfJ2HmA1wtO8I65wLPvSLMqn1d4cIGmjqYQzrE2qUo4V2nq4aqaIanLhAlD7hsc70/XwfRL2X8rMOCp6XOsG7yjbUNRcg+W3DHEqfJyR8QRlEZ+qiJf4aU6ViNlHq6LZ+obHDOLIq3AQr3fmy8MJwzP5Wc4Ur5zZK11lTlEtCCRE9BKYw+mJv28AitIGeioHQLLLDXJoOZ5h2flO7s9AM81s0c2BruWulAP1TJ6MjY2vby33oKhM03aICzbI7RUDepI03b31k6pD6/QkjuSLBrtiAEeW6bljpeAspol5y3epeMW7eY1yfhw7JE9RxMlljoGd4SsDsps8A74zBOlJPMONKWMnkwojbRkMH3gdjcIVwnw2VKC4z25a3gOpTMypzR3mjr8mVpp6tI6pbN2RtrPa8mY1Ms9ZO6wV9dYcsLnzJAmOYSDnXbM3BtwXI5n2hcDXN5RSUEi7dvREZzM5+zsMrU5dHM1HK2cqQvcVzYUbjLhjfaWJjx1MoJDUcOweYGmjmGXqdCSiWVmZCzuTzaoP51SGQVumDJZQ6V5xx2x5aUuV/0+SJ96ud5zfSqwL6fBcALHcA+x7y88GHDspqjg3mJGnLG+wpNFHa1+pTSYgncUc0rc9MCzBfd3S/yX92bA8bCRlSCzIciOBwhN3eQdqyo28oEHizqqNIOSuzt0LrjhVZKsO9qsh58alrZYG2m4qD7QYml3OEkpDLJLJfvnCH8LE6Vpa7smTtxwZwhd4En8hxueezPgksGYySXF1e346d2QTFe8wyt0k5n443FttE210NTvnJrjkmq4ZKv3M++uKzhuxHp/mEFCpkrk3qhj0uImmWAwIxV/foUXCy699hNpkwISe4uWuwmHIxY9qwRo8+qVilkmLKB1pPQcIpnBwJuLmb/+xcDle3AWtfpIXp5THy84/sWAw5BKUMsYoyDZyHqTGsYIIrwulhmLEUK4x66/1I1PlSzcFFiBI6U1OWUCmsVMwbeyB1hAiuisbGGsXZBUTl9oeL/nulOClNRIl1nqyEmcA6heFbOoSxGPZ3UmSgwc2V0n+XU9s8skeXDJGzrz+kgjIoS/ht73f+edhMwj9G9R1bMv1Cdc+lEM+EzW91sNl4a3y+l54Vtdh4ZLDdxK3WnvcYN33LWVlbq+0NdwmaYKjXzgvVtwxFZIg1w+tRhwvEjBA3vh222YhssTU1ef2s/LhOSB1tqzTGh1H3+XYIQFHsrKu9sK3DQcNxt+kXvzW4GRhjc3p5C+nxosyaB9N/y7l5ljteKAZ5Qk1aYk4w04cvt8ZZnJUt/T2VXNUiiTWRXL6Gm9KbDF+33kvfBm7KaMFwPfaWbaFf4s1I3NV+RiI7LMFGQkucwKsvjrOpfb2uUuJV5W1VDggjN+UzFDgYv05KIFWXA2FW3FLOo4m5xnjV51V29NTmdQeSFOGAmX1H1lZ6phlqrMZS409Vy2rW1uvirpBrRGVpRUdv9ZCX6fTRX9wmr9djb5BS7plmJSS+jD0zJOPvGVKq3vzV8N5bmDssG1zp3VGSikNPhb9N1Q4CYZv+msBO8MdoEjzTWH+7AZJ3IuxmGDm41Ytb5bzMCKlcruVdxsSG7nUZBh5V1uNvpLveFyRJXhKurdXXc+nCWQ2SutKbjBO242kLb60aT+VrEuV3P0cSAXIa7RvMNG6oNSu8xrGDzhxaXH4xi/skUdxWaxsDYSdyFJ+ZGuGscB7kJk1iNlOLKT0qZkwN/qWT8tZEOWivfXUM1SsgFHEIeq0heubys2uARxGu4MOIK4sjKDs+QMT9ej1EtdP5NucDTyR0xOMiNzPsMK3wr9NXysapVT+4E3ixnccOGecGGmn+FSsFYVfOsNpOF4JhUP+4FnCy65jOn8qes94YRLAr5HS80WMKRzaTKiSaO2RQ6mVyzR4EQmeCdaLPKKWWmxICWreVZ7pZBIq6M3FEaKeLxiphz9hzp7a6Zbe2GtH3t6ncGaOuAls4JEvY3MPOL2tdTQOK0whxEaN3yeY3eT8+wtZqQNZmX3dZLxz4ndqKgdSZneeajbcN2zKjZLNxyrM7NmIqhPNeQudRDOsUZGWpmXxGokPDe5zuW2h/SFi43VGWlSXullQtJ71cyYgrwLizk4Es6LZsZSAmR655QNQfZ1rwr8sgTxp6VU3OZZaepS0FfYZZI2gpFWYORES07ASz0YJzwSlzcVa/HzbJQb7q7d5GvqP7XUJWNRk8ZliIvsVirSA9mwSeurTmuw1tDXv/NXgnZvuiB+qRi/4NNaz4rx4YBuj+qL+Z3weaEQZtsfuX07M4PHCLlve5hp1WAG2bwPXJg5vxlNuKQgPswkZ0gG2uWR4Pgws7UN0cwAHpKWTDppwEXdTd6HBmBo+cdRDDdW+qi/UuyGFKUYtdBLCnh/1kgYPz93TPj0ZcPdn9TSrxRun4pjBidqjzQzyFp2bpWM7s60MZOuYTAvM9laUhzAIbDKLqPaa1f61Q1mEDOnSjODxGW9TMc2soAjG0Aiw4d6Twbv+Rqeu/AeDGaQuCxG5l0mY+clydwptALjekDrTDHMgBTjPoL8sPM2ZkC9xJWZbDGDtOgQFTPRYAbPe1Ep8LY9NDNIIgmZNZDwk2TkAGcgAXdy0/0w4/2ZGWnuXatiJhnM4MY1Z1YyUrkavKHAmhkZCJFWO7O9Bmpm0LRLM5MsyUiXb721m8EM7qJ7UjrTDGbwitX6wsyeB+d3eL72qjQ963c/Sf+bcXFO88L41p10Yxz2M6glbYbVyPLy0pW1NmyS9AVPSr+SxYwkl3vFjGGtX0/5ZSYbzEhiWKUlI2Or3dkmubDDpVnV6w10Pa9W8y6P04XmHZOrXWRPGqHueUFiFHWO7BkMeHHFsBqaOgpcq9p53RnUkRhflRnwhrUGPMXIOm1SQRsCa5OKuwbYv8zoBwDNjMQ/ihlT7lJzm+hzTMpulU3K1VBgoZ4VM92w1hL/NOUQRGNrywCpUtllkq7rm0YadqbcrUO57VHkaf2xM+j2/b5GeF27CXi+Cp886pdxQxOrel7YeE/XCAfu2JNBWM859l3FUFxbld8WiiFIVBhsKmYJsiDLzrNOJOA+JdbOFEk9o/02GeWVOmtnpNl8zDQz0gpHqVixJIMmpd3RzHR07fCfLcEHZiRS7axZqu5qXcDpDODSt4k7VwFv3bEKjJ72yNtadcaQDOA+TCU4p81NXHd6Gx0vWAYcs4bcKkGX+tlHkub60b8+UonLdJjtA0Hae9buAi7dq5drBCPmBLwmFY1nS9p4Sa2dddkB7zoAtlx26fQfO2suUDQvg+5JyciVMr1DAQ86zDOZQVQY1KaIxiEgZb4+GTGnV8xIcUm/Fcb9hBYXhck7toVobCDNCSpL9L2Adesgwwe00JOlX5KY31gnQ+q6iqP1C6OkfFFesqVfiE9rZI2uDNttdBQGuLS0PgpSMSPUff68TP43M/ek+MXOGfoFeG6JjR+EenNn92tNGxjwcE0Su6mnfO+NTyYMcK8Faa2qwNdbh4DpgWfekQfg8tlUb8wgiMzKnjbj9AI8aafaiq2FekrsFQiGL3Rt3C3XcQ5pLKw9bfLaHdmjFBMbfKYvrGXAQ6SvzQBvybEePgY8OH17/intd4XPXFjKMZUxk0XdEAbjdhO31vU/wUy7Kno4swS4r4k9gzEYInR+NyG/Lid6mZDJEhNrsDFHImXHmiXAX7fq6xkMuDSuPG7tN+03+CLtVlCn5eOfhGTu3kI+3IJc8JmTGYV6qHXTyLjDnRyUk3qO6Bl3ZqaH6xX4AzP+NzPi4TeaGXj44hBM6qGnLWVZUS8yuEBRr/VMXXq/ZHemrj+1SPZevuFOnqYMZuTRJS3MtK1eIO7wIFEhJXc0c/HVnZnZqAvcoL7xjlYxcqv88h4NZtD75YKDOsbJNoM6GnTnvi5Tywbv6ZrAdFFHu1RvMJOvJmEXfIRNsRvM4Emnrsw0XwzqcDvF1z986sa7tErNtNzR0vRSgpuZYFCHv9w6LRmUS+d0wf2w7r1ay4ThqC3TzAi80Lup3Xk43G6CUxujoZFxh+dFCb5IBq1rSqusSa1unqSrFftwrmr4lHv8GSItT0Hz9VwQd7j0xj/xvjGDUu/c2L0qbXdKOH/qxgzgNbOrWmVYSmM3n8BLUoJ0BjN40nmN3jcbieSX285Axcr4UkuQ8RoG8DKTLckgtaZGWjLpVWDCRgJ+23di8wFeXaUlc0+M4KwY4DU1mjqc2gsef9oIyXqwPlW81KKOA+MoA3zeoXNyRypG5eUuTq2nmcEUtdpoO4Pk1sVgf7MzGOeeI60EcJlLYiXTJDOMZgbwoPyZWg1mZGJSeJmpNTZDMuhfNENEapmk3VFK7DIJ9dhoZlC2x3vYgPuulilYzAic3qvSTCnTzhXgURkO08MGPGfapM7eS7xkZAxEeJkpe9uduMOlocBlsBs2mMFMucZykZIBvGTWhQB8pmVyu0nS5mh/Ri7GtAJbh41cGLZ4m9SUcz32XgIccdPii32TDOZIXILcngvijkvLKfNlG6EDFAwWqSyAu+DYsEDaUcXEml40jAousyIBvOZmuHjxFzzSzi/6S0kbUVIygCfaE++SYZdpyWCkV6LjWml2lRzrswl8uU/4xgy6VyV6TwPeSzWit7jDfTMkE9wv6tex4XMZGy+6pZ5Dc4KXkW6F+/o70XU0etYDky5dfHDV5fnCs2444DlW9mjvsyckzQyeL15D+lW/ELrxB5hQz+y9CWKrcYCxZmDC1wOseSNaEnh5T9OhbLFWgxkPP6OSkhH4zMt9mDGUXeDNZVoyIV2p/BwzeBwpnVymCU/saVrRA6yHTi8TIj3tmzZrmfB88VprePAhGczIAwPrKE+4MpDN2NoCd6WTTk91UoLJK/A9jmLxTS3J4Fp8iZZsaz0izrsQjLFiAo/Fn/2HjXdppaUD8m4wgxy4nOllkvcI9lAVeOiRVmA8MLRM76bZYmz91HK+xKkYK5tjJ29/hbrMsaNuIYV6ykqB09lRnsx4emvjuqouR5l9Ngl8FrtQyyRTVbsjL8+qx4Q/58nb3wl/eA8RdxvGbgJ8dcO/WGCPkRWBPSgFHvXWdtYyYVJ4DYbz/ibkoXuRzLwB9YRWy+Mz8qdubWGBz8eRhAET7gczC9/aGE0ambNS1MORFnhaSMd0JI1NLe9Lk/QIWTaJa9Lt6qXFcI1NFG6uI+rmt12hSaM6vbSVdD+RRhGzzCK6uM4+bueRIh2lZ1GkuJbBm5iJwXE9G4NUStYA50VDvsgacJmh95D27Ugaupp40umaBMcIRAan8AJB5qi4CgRpdEyqgdVracoV20kgGovLtBA54eGNVTxisIHWGr1YbPS7nP87aZkK2egvlMGQLlDaJNMbE20UpKStBmpdZMRi9zRpdIMKmRMI3iZjpknLy6fnuM73uw6lqHPKIikQxKpywHNcI1btnL1BpdatqOB6HDytnk8Z1FLFXtmNLhXtIZ2Mqsa2u87wxrplmlIIv7Dp2oq5lh8fyzKQV7GMiqvKG2sp/9IsH4WXpckzrU0ytbBF6oiR4invWEFneZjr1B5AvVIvxVhyTVrm/zXKKKD6KORGCwTw2DmBINJ5FPU7aalX5E4vmb1XeNID3tWZa3AthcX3MuLRPcVikG7XdCOGNN6mgmWAFVzqalynP7KXK5fy+84tEt1weo2KmlA7q9eAz8eUZxnDkTScoUY7IQLP3EaX4XTllrVvPoVwyrS74C5NuyBdRdBi1uBE5gQ7Tn75LnukrJmU6ZCupxSu+EgrVLsLvSmFmoUrpJKgv4KL9Er2axosQVrqODx9lALuS6GMnxRxFNpTBfy2ld9Uu8ooMFq1BR44haoyNuxxtnxoeyaxJo0uipXziFCr8Lru32UNB6p5jmtxcZKxDTQcF+bB0/JDWlfwlPEDafY0kEx/3mcWeOa2jMynCPSWadLymgv/kYU/3wM40sjx91xwhyT5kGh/AfBSjlumvKQTHviGDcHOzdL/MCPb4nTbMuFNHsoFnoo8sX1OAb7gMrl4wJFgPP5r1TM30w6f+Wr5D/78g7ZRHxVqYmfcnfGR/sevE0i3j6zhaj4wP7KnpSbB//7Ieq/k/MihYL4YHyltStv6kfm48BM+swE+Mb4JBKTLIxD/M0zh8SPlJrd+/sgPK4lxx77SKwl4qMtHptaNj8Slda3LR64jbbePhPMnKQbXqpeW953wYJEL1N6lQSvGepjTc8GLuKw31/V81kx4byeuN4EgiSn5ddX1OJfwi5Ne46LaPp1WUprJ+8buScBn+wBKXQEPISnG21kmgMekZNJOKykPc5IZca9kL8ePDNe0KE5dZfpAS8bC5x2eoj8bnu0jAc+B+0gcvzGc1FV/JG7K47M048RE9Hn+SNwlNsfuScBjL2cV3D5SukRm7iPBuE/cSqJo3b8fOViqlrqi4N55+iNxCXrpFGFdAY95Vdd1IvT2kUhBc2E9bs4fKU06orEngyKNnm3llUnKvh5zoyc81BuOKxBkDJ1lco9JfmWyibD/YiZ4yhhPrFp4f5SJtI7z9BbGPXLytJ2SonzlOzRnfOQ9yuY9VvvxI5Eyd3kx8yNrO36klCUV4yM113j1TnpprB0v4d698GOT+a2l7faREIlaybPvINgUuZWE6Y7prN1Oazfu1uO6NLFb2o1m5aF/3vH+90eCmdYPdmoTN0Lgrnwv3XBrkwlIl0rJJOKWv5WzWVu66N1wdy9NasNNd/td64qNL+lvhxngm04Vw4sG3MXjR/Ydey/8B49HCwTJgCmyhxngvgV2uwOealQbx7DzgM+koe87QbApr9vdnRzMKA0b4meu/W+ZSMajN2SSd+qzKos6zABvl/vw7cQGdl4LfLdpUd5rEr2SuKZrkT2xAXeeX0m5WcnU6QRsdOvp1NzxI3Gt8h4337zoCe/0npRyPO2WFOMjJf+TVNcc5rg65iMxj6BleiXRabnQDibgMjqRXEm0YgzkSuLuKHLxUESBXwrGSmqu8VbXvRHgxBP8s53qOzzF1cEM5fiR9Z5kRKykTAjlVxJ1hoUO+qJk2mfa8GAYKruSkti6fmQ/XsQkKUj07EcCXlNm9yTg8TKXxJ6UDO4SqD0p2CvUulYyno6QhATVat2saJlIM8rKHiGAb4YnJuMj8fZK+v7CSePC94S02sU7+raSuMEMjt1kgLvAuYBJ2pnU83bfPjLcvZS/B30YAZde/fvgFuuPxBPfot3jd1BTof0v+GxZSW3hJPODI/2deI/2yumJJy9QOHGn649NJniMdpk9VgHPhb4wBvw2a8SVBuDtjfbHR8ZjtC+MZ7cu/NlOIe2vJfojcYmeM72SoO49vYXL3Rjje2QLbOir79DPK1mlyz29hXEr/rr/2efzGMoL3nT4bn4ksiFJfz7JpJbKfWS72ztyK9nSEyAyK9nSVe72BMK+Gh8paQ6dirYwlGg+PR1WZ5NJux9siQOqr7dN349V3HR7ZWCDtZJowto530EmL/l+OnEU1xnp266zR0iWut5IHSHA5qq+0BsBNuAl+VM8qZYxS+NV2uPJktda2E0mT8E6nrTMJeA9cNfcwklK1CbLKP1dTnfkymfjI5FhG+kbYKHeE3vbCXiI5EfGuzfys5LXXf7vUB9DVe/Hyc8rqe7I8uzwf8MDBkzFszMA+LLw3wwP4NueNBf+SZ0hZIIOt3m9N2znhc+vaSCsK+DlfWz+uvD57g7KfSRuxXOkDI8wrraw8ZG4t34vsr5dcwOeCv+Rcs2d6Y8sbdPu8zkJbFtjbONKSPpjRdoZkO5bnXYGstSC8R8Jkah3WOMjce0VCxVjZ8kJt9w6zQbqwo+vgtsX9ru3AvUcDLjz3DOL9POqh6X5fdsu3cICrX+ABx1WWNZV4OoIOV9/FBkW06kjpMh9Lv1SCniudPZCkdlr8XyDvn0kqAdO/6R92nqEhDVFY+m8CWx4H/bn7Om4pQiVHV4bfYMJePDvhXvC27MhE5TTl04vPJgp3LE6OcmnPJ6lOgwtz5HhgqUpyBkd37g3c3x76V7wLEFzQUp7gO05ks7hmn89SRdkaRukcQMsl1436RKPpMs9YmmSHgfK1qNbky73SJCbdD1zLcUA4SI9K2SqQVruI91CWhkpjcVVnVuFl45YFH3PNNePWMUysFlSj07S0HCpZszskgtcXtYITnAZ1DxNOtzWjCCN252UDW3ScNQ/Z/4jcdXUV3Hn89Kg72xQ2KOioqdBN7nWpFEPIKfpRzY0aYTsC+kvewDwJG83xBcifawVapcDOxOUDmwsoywBl7h6wiXp3D3dBuIn6sggy5VeRqR5pUIplHSe6oUlDXhqq/zSUSZoDBXDszRlfOLmb2nST5D6XdxNSotfo5pq6PGUKjDhOZdL3EPWPmaLE4wGycq8lyMnT0B24GQjjbyj0Ff5nUlLKOHZXQO4XvV4XnX4+7XTq47gw68Cice9jjeeOVeSIy0GijN+0kop0na1SZ5FoWSNhkfl2QbDF229GxoCeEynM2z1QyY2+HvLNP+DDpEnNqQzUmWtGeCzfv+78JCKM1PYyp8ef4pPZR9UqGmjsNMpdTpuxy5P+Y1dGIHXQO10XAE1H2mJAF4Ct+bwh5J1OOYdnlJabHaNanTyRh1j9bxjrV8v9+XIR5ujsXjRdZU6ertsMF6jZLofdeZ1VDHMbnjMqgvc18ocHd3JqIJCk8b8Y3VSx1V4TpHGdPic1rPA68FlaYfPZ3+OkwFPPTP619Epx0eedJROoSvpeCQNv2+Rn310CLykk6Vc5tQAKw9BfpFfDe3ougi8FsM0rAlsEx7atX9rqj8g/iaw+R0buSiso91N6+w2mHBt38/LCDcxVnoZ23ocrFz736RRNrps3m/LiDeS7pjjoEtjmepZgQB+m5EvLnlHpDQfcuUs9WhF7Q3S0j+0njavJo1b+MoG0wJPyqU8bxn/jGBjHDmBJxVMK9JtxwZ3O30t3dr0ab/4fLel5dYFPmLi7I30ja20vQF8NsN6rgvOwoN2XGHB53VxijTuecvzkbGhK76yIX6H15aoje6fjhuc/AD3hTlKpT/nHfESpAWulqYclybgarDR9hrwext8W/XwNKykVj2I23eSdXA7dl5oCjbexvqTXiOXJj7nAFq51FYMNvCkrVyc884NmAPggrFzNRxTBiptVAGfLRW+3pr1IIOaI+nzCTzUwi0jUu1ao5cRuXMlU/KL4shFViCAl7ScMsgiOZH293w1jjScrXYUiMbC5yuropbjiYS2By46mg3MH26Z8lRjuufLUOsCuNfh7pm01K1a9lrDcRO2aMiXAwzUUz5aPo2VClDO04rIRim0KYviDnXKZ4mYQ/Rsr8FUKe18w9uTa8/lMWGvZaRqicwlx1iIu7KPWvUkzS46Jb+Eu6pU2aNU4O95l2ZjueNRCrjPXHyX5Hmf9heSNEcPB39BBxEJrS7iGoThyugUSws80Je8Ak81Uh7lsBrjUKdPA8BDq8zVYJfeo8Wwq2ufpAueH4NWf1pcvUS/Y1unLt87KmLz69h+O5QAr85RGpLh4kTa+AFefWZuKEeEWa5uA9SSA54c5wdnVNd0njS8nEy9QfWMaaW8yQF8dvwnBIKHwZLIl5+e0XTjhX9b9Vzugbzf/YWMBh3VsPBrQvKELwfC2DDPHMlPqg14i52TCZyi5QH0y5EHuE/UuxJSAq8es5RdKO4uJP/OdYFTlOkQBXD9GmaQlk7QtKMDuHeR8kaKvDzeuyaGaSXOpMW/CJysxfTRNhjwWdb80fi92QvDRcTD/wwHK8ZyDc2q20RVDX/ahQncowS0GnDkuy7wNjjJBrzfEzsmPKKr/RkuWYHhpZ5ROWrAUWMhxoSDo7i+8tSRvCeJ6wfJhLTD5wThigMebw3blEZNHQe8PBUeJBNek3LBZ5NboT42dqgWddxkFF7uPVy9oQCP40jr2dAZVK/OTURRRx1okRuHk86k9VOlIvVaVWlEPIKTqqynpo7azp5ZBY5Pi01KCVAU2D0tSKncK/RuQqFalVwgjjrySBb4F+qSCOssyUQFl1ba/jEcvfRsbO0k4wMCzQwKl+QtifpUKaMJtNylIMVnGo7zOTead8SZMbI6I7UP3tPMwEa6xsIlH5+3kTP3nN6ryMye76snyfQdvi5Tye7uoxCW5OwHnu6xDffWLlG/ROUdPt906nx/rClGg3dQ9409m5CLHAovd9wlZ0/LHfHKYiO/qJhMsi2F5b0804oo3mV4rE+fqfvfcKl/p+2MvOM2evMVKVdONHV0In4N9jd/pkjHYHpVZRBoCuyqVnF65+aLPxgA2avBO1LosqOPA8miu/YqxnKNH7cNQdHwYSNLoyWD9LVZxH9gZnmXRA9jrKps7YZ3yfLTW/p4W3Zh581kg3+adXbyRhcnqtiAm253R7rASo34Tded6aIk3/mVbj7SlezXvPLrj3TrfRNz063tSBdYedi76cYzXeQdSP4NIV9kocmN/Hf5IutgTpn6TlcyFDTdeKTrUQ7ErRuws7fETdcf5dCla6Ln+EXeqGscXRTXysXE93Xrkpew0l0vQsN7kQcsMgek6KrJGdZKCe68jQD3cRWbuiPsO3YOcGp4MapJ6uTX49Hv8JmT/UhjJZ0U1wjXc7y5rsHHanEt7Skjt9hStBtPbGi6FWmJp8XesJidyioyoti2Gop4Xmy4Zy6dNn9WWBRVXiKWyoHi7gkt4RPLqL3w6fR5fcf2i7T03i75LlSLn7iWkk3HSDnD85ijtr+aQsGm7BlTmB0CBFcYrRDsbCZL0JVyQOqoEWxwk+5f/3KkiBxVnzlOJc4PC6fpLFlknIbEGBXBzmSxZ8Xax3flCzsnlFxYjBrYSp78jUUj7J5enWxZV3hvLD9JDYQo8DTgMrdoqJDQ9jUe6ba7aexZeZ/Pw11Ev8SGgpc4b+jCJx6kf1rjFAfd0JSP4o7L7JExr/bxWWZekh4qcyZlj2TX2iiZecl0VRuzHenifr9ESg5e7ksc40tkPK5lXzi6UiG0yvd+gvK/6ea7VrjNnDfnzjJD8kJz3FrAX8z1oGcbFvf//uRTLQnNFzbfPgrSmcaqT5388G24/I+ckQTWaz/pcxYnsDKAJDx+hyv17sv4kQ3c/EfK/ZnY2ilVk36wgXKHBevKqmrpuMzB38P8CLoIq7hwIwdc+CdHqTCwrSbGfc8BGRMlcXSfFjKfvJONLvxFJYez+gAbkjuY66VK8aabJzb8dJw3UdXfbGzghixQ0ZRgY8gH73mji5mNibOsQZzFzoltOHWzBTKxHKhc0upzpttlUgsnBySjtkKdBBi61hp3Kkd393v9GAUvF3IlpHKPOuviHHRcix0y/C94l1yUGx7fMcN+c1MmPEj6W58TjD/4tw9pyQwrKyepGJzgKjwouK7V2KjDGmb1nVtXJs04mOkr47V/9q8maSeZLg/pbW5iVqTxIitpsROOAp9ocCLUy4ET/ZFZpuf180dqxmU21PWRF7yXMydZhiyEhZMej5wg9WzjJKkLxPwLnvVieoMTH66KspuTcpYJrgC8Ih0MtQJ8Fhe/i2noCeCt+1Um5aQnmDyVYzb0pO9wrxnPzuAEl3u5r1utHWWS7gr0d6sFQyaoY22Kk2hxgrfquK5OPZof6dYtTtVD2uezPQF8ph0+H3kWN24wQvpsqj5wUu/p1gd7slFH+YNeHX0PvDGOoykmyhBialaWk/ewGTZOAO/ubME36ng9ympn+m4wjqtatelbO0pcRnitnGDC2Zl0v5/svssE1VyuVvWR9SwTwGf518OJN1ZHholFR+2dIlN96tlobpzIFMVpY//6F4MFpCZozT4LA1caPbAnJeClONbMyyCx0A57bONEBomFs+5tpNM9+uQh7Y+kxeOsZ2u5fWSWNJZ1xaOh1uWZq/r9VMUgsTmcidO9sute0E8+GyelXd2QCHGjx71L7PkuFcwusycI4LQKImOyOfYEAbxVd9bYjRNQ96ue5OPqYKTZnLNJ6QngvbSzmdecAJ7cahnW/j/B79iYX9KtxKweqzfG0UlHM56dwbi/Uwpfk2aIUODJnxYzKtKoe74ck/iT6oC2bnCCbE91sJqeN+CtJ1riknq6Ml6O+6FK91nPBi+Au6asVbM4kUxVxcnRWmHY23x7eL1MYz8AHrV7nIzzCfAcPWWtMOwtRuXUO8NayWw4zYnlxwi8rWd2PcuklquJ9GsIo8EJcmZLZmMAwCNpwTF5rrrAelSAh9w+W6vfTmmVx9ZOxUVNNDCxMmnyCEf7MYDPqVsEJz5c5U/UqQZ4Sv7sTW+cAK4s+HnvyBg87UpbFlzg1bP2pEkemTvIZKkvuLDxdX3aD1Ju32tbzXW8C9ko8w140SGXtc8A1/I777OW2uOwMSsp5VjKS3eGVwB4jp3y2dozdXB3djcWcFmoHdhqBAqAe7XV+5mF33GZFe4Dnh3tGwMelDKdnbWGzOdQzzcJGyfoORwDrU9S6FXoXdDuRh6f9GnDSh9hzsZ36Y2UWa4Bb+q20bRngN9XZd90D40aZ20adQIDnlpWu8CIXACvqXy4cfptGToKyFpmvRLA54M6ZRkAr2ozGDIZ8Vau+ezwbJyku+/CwRBvnEh9f6G89C7v4PkcFG2cAK6DbEu7u/SrfTQ2/aT1cnzjBK/hW7xgbEvAq4pwoxXhAq7t9tlAdFyTZfrqHXCf6R0v1MsxAAiKNJJJ/bI6QwuMqzLAnd700dr0eEjX954m41Jdd2361isCkp3xie1VqkbBSXDSG7NH75oqkuw7HBmSgPsRdKOL1ZIqoEijyArEXtKu6qoCRbrIVOHwkkbHrpfrorDINMOdkGBT/Kmzm3XclwYTt/Hggkq84K+U5p7Ug8vyuHDB5Yblhuegx9pt8HoN7X7h2nXYmLmfn19mXDbgUkzmFngrwWAG8KB417cbmjqCORS0L9S39FRFPUm1WlyoR2d8KqoVZLct1KNBXZY/rbzrtrgbdfiwfRVka/m8qlILgToObplQC+EReL3LlL3BO0onsqKejFWVSSGrilWM0ztTB9zllbp2yDbq4uvVz5L5QF1eWwstd8x0LpFeVbwJRL9Sb86gLsOUO01dyj46TR0eX1CWwFvU8RCtdtPm5mvqMlqhL8y0WA25A94rre/I7KixsToj8BqVvkeDOur0Mm0JZKzBKkjbEmR5dMo079LtUpnUYglSXBcF35LzNDPSZnJV4OEPGtTlLlqpWDc2nzSX7+7zYfOBOq6j5cx7P9WSTL+GLHN2Jt/jRRdmDAVGhYskXrzwLc1aMSO18HqZrMMGBTEyF2sxS8anzvqZYiiBph42G2krsLTtVkeZufmkFbdLinfDJyjp6ln4bg/dm2yjjimIWiOTJfe7WeXRQdHUkZ5S0lkyS5n0BZeX6gEf3l0bBjxazEhJv1qmatgZlArFQlsxgYfCWrEiSXVq88ViUAe8OZZ3af1dCqtigLfSaOq4ZFY+gU0duXsts0pQpcGkOrWrsaqA16R41wH1Rh1V+05R397PNXVkcYTEbu16F+4vp7axqoBLZgspd7g/vZw1ckkJveDtYcbhFtyrWTcbM3cGBSlIXL2tcNtBATzq46CWQxefCx7qs7Wr9ygmXvMRNTO48PKeNdhVeizFs4e9ZNhd8Bzm2TQvHEI6RXBoNZ71vt4mBsUdXkN8vhM5psFYI6kKUWuUjDWSXuZFOTPBOPbQcDyHzGqvtD6Plj3VcBl56dmtJD3HN/Obf9cxrHB/+ZwjIg8/vrTlMl9zIj2fOusso0U5qgxIcwd40z6edV6jS/l2XhdL6Cgb0bvUMqZoVB6cp5cU1SCx0WsEl5A/ZgSufI09sNXwu3Pl4ppYzPRrViHnQaILuaJuH+8Cb54NytGIvLXEHmLS5jzls3XcqOPVPEaad5meHtjQs4tLqK2GcUQCXpTjYy5Tl8dwpZHO8E+lf3minQd0DZfKd+4gAFx6unPXFdJnvFs3Ypq61AZbx3vf4fky7jgLWkEHmPUs0Myg3Yc+gM1lam3WQFKfiuxfFyp7dyLwvIVA3oCjAjhE0teY8OQ/y32378lLO31Z1XA1pi/nuGDA8zXdYoFHAy5JEV7BqwHHJCDkd5LMoONAVMzUo8FOMuART9wcM1JxMyPVl3ow4HDFNTPnVU2o0EHrnxW+9feLO7yUm5mhPi1qg71UVgMuicbugdexFZ3BTLpeExfe9fZIijoeqeWK66Jee7Wow7dGYwhKZ3COjR+vBJmtZcJdYVA6c77Xx0AxdJPq6lPbGQ7ApjPvMvnfcFzPtcyqmLQYD4p6OA2EvagjWwTw6bel+tlvG1hpqGmQ3uDoetnVGqVswOH71OU7vTepQxsjvaToqx0dvVGlVzZKFU+8L6ksF/UeJjPDsy0/Pa5VsZo0emX7lZMQDNVFT2tJGeOUS9pKtc4KHQ2IpGTohXuLOtLdkmPtV5CI2bP7CD2ipRb6ZDK8MhnS99lN/Yo/zWdc8p+pA15LPVvHDY5LFr2PkmF70Sk69nQ21csrLeC4BonLp0Zv2a9fcFvZ410e+An+e19Lo2Ztqs1Plejd0YJEnYJWYGtfS/BW1b4OhorhTJXcBep4D2g33PUBbG0PtBB26iCozvhU9PmNtCcT0LtXiuo4ucsIFa1ipiDR8D9Gdpnyb4tn+RpZIibHLhMinnn3+8BbMuCSahzORs+HHQ5DdFkCNPnZ+oBo6uhcyytBlhL3REsGDmcxnLal6VoqGW+qTZ5G4jVwtJqSQWVlWU/J5E6dyC7qMnZ+UI8/pefiva4MfCvpL7iXG86bmU0yG+/1GmP38l6cwQzeg+U4mMzUGj49L4QFXuQ14mFG38xszLSrE8HLTO8GM8gArO5iRgoVejKYQbsbebF9mMnBYAYXhd4rZqxlAvyizkgGl5xRL1M7MyOvzfLK/zLjz8xIC0NXH8mMECoazAj1ulKPqRvMyJRTpe/HZqYXvLf0SKa37LLBTLj6Hyw6YyyTPE77FV5rMpiR5MFKM4PaLq+WKRu7CW/ZNXV6mQCXMILSGYEHzyowXspzKOxuAlzy30jJ4B0+eVqBURMW6pmZ9S56wuulYpIdhprLd2ZX+U260IyjBU9y9JJKW3xtIKshRZSQXYyDmbGRsmGTJCMgV8WMtfMQpDTFTLWYuTMDOQMpo96rkkw0tpLMY6+ZlTvgqTb2U4t034+s+ZUx63KbQFk8mZve1cGk73M3ZtDSx6l9veXAlh3uW2XlLnUoel9vKS1RUU9uNjCZcq+99ZYOLWEveFBncG2GTSoSfRZDkJo6moc2tUxb22z9qehj2YMy7oZNAvXwHKrfVxVlX1XbJMNvK9LQkt7aMhq9NdZaA16DUrGt9lTDcTFeC807unlUa1U1HFfX3tEKjIKuFuhPRbmYV1s7GswgVyLyp6RkYjTHKoHAo2f9B+kgWxorGcAbf0oK9V5pZpC3mr2xm8oOD0to8GWZBB47640jcWO+qFEWWAa9u0ZLJl5N6LnjAHkevnXWzasyz4FnJl0VuqRkEGM1zx7DMqreV3qZZPBHZz0r5Hk4F2mdqdcsKHI31avB8tFga2YQkgUjFN6YaVdLYZIZXOpv3pK1mxBjdTq2BTzxsS3grXVWgSWvNE8V20r9yo6LMZ9Fsr54TvgdYQNe0STE4EKa1Vvrk3bqzTn2uJb8FFc/X1V8oB6uCZ+cJ46ck5DW1W/OYkbqvuiwE/CuqJet0Fgzg1jMV1bRJaOl077yzJdprD1CRot2T5uPBjNSW9bYXQe4D441AZIvoyM9y1ILPNMuHuBOHUr2MgEdIuv8SuuwSoeSgDtPG0dJr8lRKbBxbwJ4L/wyAa6ZsXYTsnFCKuwyAS5NYznJSK5Ppe9NkLwTPB3Xdone6Ls2wIvL7JUocn1c96ydAXy+knOSQTMQfWxUY2tLIoa+azMlg5z+SCsw4DfvhAJL4pG3dpOmjsSjVowTsuzUc7RWVTOD1PWY1TIFg/rdiIOUDKI3fY1u2ZmZopJZO9Ml092KIjR15CnlaOxVzXu9n6cf3oO1tZEvk/mtDWZ0CB/OHofMvEu9k+7phPtIGr0Jp4M9OcfKtpssZlDTWAvNDHp49Ea6p0hsm73ASWZkjEOnmUGwp47h/T5hSdCe85ql4dTQFD/Okp94aJcKLGJgybclsNKrpL/YdGgYDSzKMHNf6dYjNt1PFjddd+YBDz+SZXDTVb1J31JtYOVdZvIQf8IIfbLO995IS646xzLSempe2WhnLOrQJE/noZuPWNS5h3Xp2hGLpJh5u/edbpAX3FXEa3v99fl2Yn14xDaOoBjbYbAG4HjkiWpF0scuYRdWBvMNrHTjH8uj+yrHFQ5NjvJsNxfQ16ZLNjQnovg1rR/pPjYpTzImZmypG9vbTytLNfxGt8ooh1U/w0nQyGiQfrjEfkI6w7zNfSR3pgslap5SuCTvFoFS5HR3myP2HnISio+UciIhwYW40j3ygGwEv8pMy/ethMm+4QI+y8tD/hN+MNIlb8enhvs73uHgyIuQ5L4JL+DPgMtOyZ+p+99waL88EXLMSIGep+G4dEazDpJ3ZHdlGi7FsYsgv8HRYEtuSCjepfeUBOwcdeRfFVoJ0MVpFnVycFzxJZ73esdqEz5MVCwGHLVZIdFwVER1Wgm6zDssrCDRy6Qs+v6FGZw5rrzMdBQE/h7yquB9MuNzCT845A/7ut/dUUlO8E7cIg2XB26eeruafZNSRDJriiS8OxlzzvLenQyE9TT1cL+2T3jyYbs/0nBk+/tGU0dqV8+kOnYnFcyNhiOU8p6Gwyq1ysI9vANxSSm5e+RiZ3qZvDz3VBoe7xtngdfhGW3vlRqOYWcx0NRl/BVrrTvGWodcaOpI7Sq3ZMb/jt6UO1qqpcIuE+IR7+hPxVjrRO/VjrHWs8/OgRllwgQeLndDGklhbMZlwv4/T1/Atw==",
    "rd_f6u1.yaml": "eNq1fcuuNLmN5r6f4gCz6M1MQKIoivITGLC98AUFb41pY6ZRFw/srp7ptx9Fnr/gpKjMOBHxsVaFrFOk4iPFu6T/9vHDX/7rbz//x8dvU//4+1//8m///tP/+vjr//s/f/v7f/z3D6qi48f/+be//9s//uV/fPz9559+9fGHlP/l4+Mff/3pH3/7+68+fv2b8Uddxy9/+Y9ffeSmPVGXlMYPf//L//3Vx7/mVvPWG/3r+OXnn/59/NGP3+3/8a//Of58/Mt//u3f/+1XHz/9bU3+D999aNb+hnzemqH+t//949fJ//7PH6o5vSZfEpWNuMhFBn/63QeX/A6erXFvtf6T/gl0BvitZHpDPemWW6sXV78UbiMjXNqEFCjcZ/JpSznr+PGf9L+/L99nDmVLlJsQX+WwFLCFiPvWRK5BtJSwhWjIODfKVz9gKWNlt4EbUMbP5L/JOLWrHzA4sDZ68wHDiG0187UPWArYkIfvYEN938HSFbmDh4mYpHtVPZfSfSb/Tbo5Q3fwM4dhoYcEzA6+v4ENQg/5PiN0V76G+sNCc8bJt6Sks3y1wORryd/evQv5Wg4B8p0RGgY6cYEZ6In8Q8DPLuy+gMkGEDX3i+q5lC/Z8MpK975wKTa8mtb/6X0TULjP5L9531KA3rekQpHiNdR38eaMFO8z+RDxTuhAfe9E/bF1S0NuXeZZts+R1V3ZGup42T6TH7LlrZEQUrbMcX53ov6QbSKkbKtE7ltDfc96LweFS9lWCfa5Zv3opMiS/2aWM9YsiwZWNSbyD/kyUr6iwXZZFChfj74mkOFcao/4iO1q0WQpXE3RMbOm4P2rKdLvaoIJYKk+3cVUz5v37t59ov7Tzz/8ANy2PbhYNSGDt8vdF6tyQ9rlnDiwnDGRh8dUhnyIgO0HfAZVCbZxLfVHsUoFuHFzlsBS5ER+97qakNJ9Jr9Ll23EDJBulshs15D/Zfsm6PYlDRUwaWQ1w5CPEbD5APj2JRf4ZGS+mzmyVGWpP2yzIIX7TH4XbrExM0C4nAITXkv9s9CsSOFWisyIDPlfWoEVGTQbDjECroQTsBeAMEoAS/2pc+yWxs83+nRexMKRRQ1DPiLptetHJ0WW+mcxsiD3b0MVrJbgN2BFaak8TSbrTwkp2yaRsm0SmvBm1cBCs6WOD5tVYwvNMzpgv6sanPNSSoHStdQfMfOR2fmvv/7j6+I19ENy3hkfrHwt9c8BjQQ0bJTnwGfsrw7Vn4wqhy3lmym2FjkvH5sTWeoP0ywMNM1EoQUrSx5esDLkI2zzBA+6IGnJfyZFUOmWyC6gpQ4vZxjyMZa5SGSbiFhBhm2pO8VXwxIhEyK7fnhCZMgDLLN8dl1fr19zWZOn49BhqT7suozIjNeS/yyHJaRx8JPxUNMvoaNbFDwZP60f7tf9ZDzW8jeKDMobobLdpWxbdMy2GIoHNioseXytkxQWtC3hVw6uRE4fAA+r3NA6tpFAXSI3V5fQzdUlWro9dLqKug98FDpdVVLodFVZDK1nQfYSSgquWZUUGvqU4KH1QpElq+KG1i8vfilcmipWQjkV5Aae4cFWrIofWjdjGoD9W0J7gSV2ar1ET62XElmxMtR/OREILRgWhp0IXOLPwEbdUn/8ZDxUvBzZByzMsHrzUrihg+ulSvDsq+HQ2ya1tNagZSsHUUoVV1cqi+H1hDXPooHzr4b6Lw0L6KSG4RASQRc/v84dGF4JLrxaikDnSxEUGr1pChwVKNHD60VDoytNsfa5U2TV0JKHJ79lHmG/OyJZa+M3H7BV6b3yQrp0TXdiB+QtefyQDycOtPycOPAuFks+Ii6364cLl1NsVYyzRAo3R0duhkOE4efY8XhLHn/6gc8Px79spy0lTD5wawSVMCEDt8GBqvLBN2jqL4L/i13HSQxwLSINvlKAGdZ3XOLDqL7dUoXsGP5IjXrKfAMeLwA/KA+tfXKNPH1oqcNrY4Z8iA+uwNqYx15gjbul6lRfeuOMHAnh2Bl5luB5LpbI84fsZ+QzNHxukX1HbqHHD7lFh1fNhVfPdc/bm8sPyWNzI9XIxJo1dJiLpyl52WxT6r5bVNytCEvtUWRY5aRbU+Q1pBN5+OFDQz7C7dbQGfmaYkOqmiNDqrqYwH/eu/fzIsMhpKNcQ4fkqx+SJ+QlhpU4sCdlqIc0LCoFV65mgMDitQAFHGGqJbJ0VUt06cpwCBFwCS1dWfKPDVyRt6FVDr3XwZD/ZQcnqIAZebXDb//40bO+4zDioa3Qi3HzL7UulIq8YzB0lJPydQZeRznycorqp/HPXNjXk9WhfY7iiX5W0Xkqino94wUMB38cwnFIqbd8ncPyG9z9SiWdMtTH32A5PL5BGvIb2twlKYPJRTmvvsDQH2Y0Fyj15x7ATr1moI42dwEPdTD68xUwe6EAic8z/Qc+FYnPXLqlU0n28eqf6d/SneFjeIQIlrqprVahYeL62sSVa8t/ZrAvXxoS/Eoz+O0q+MNBqpSJvpiNKyJQ1REGbq0l+pbDffMvJGI5mApfbW1LIvnrHv4YpLkEN2xzRe6vNlnPArWe6mxbgto2e9PDQ8AF6t81JeffqyCV1HCA+y/NOBOxXH2eDBwX5Ornw+Lo1dMUmTQo9sXt3ULI1Zdp7zLSuSir03yCRueGA9z2qPjIhJHoi88t+LL7GvkXVybLwR5orT2n55HY795PVRwDNB/ZHOopSIDaZBoyMnlU9dHDqRLx8fp1Mg4CNW3dGYfckOh3CTTMfT6tNjJ3ZFLXk3fsLSMde6cU6lo6LUoP2C8o4NLDVL+aOIz0qG2SewFGt53ZfULKyE08gXTTSi85MEdutCqh+bWhD48hujgzoUgX08WbCS5Q6WoKTOD7ogLaGWokXH1yiICgCPXJzStQ/3vytclccBpk6f+SQSLNdE9ZIut7lv4jh6lI/Cl0B1v6v7jJDsXfVygbI7/AVSih+PsSHxb/StH4i/fxGWmjLQd0oN5Tcx64JaQEmgAjlOUXqMb2qGYO+HB9pL4JGCkuOeSFp0RW+uZvuFmOXnLIfjc36G7OsRU5Sz+i29mzr8oha9KW/rcvyAL9grkvvx+AvW7xptebZ/pb1dwpffU85zE+fKMfmciuPY942VBvs34OyyQnJi7ofcOn63O2R1sf+aXSi3i6HHLwUykTh6GbaSPO9cYn2LGOwWA+Lt2Z6plLIuntVMrMYJ9K6dq+fB6Y3hcluj7nG7uJ3pRb+3rPdhbA1PWklJ43sG65934R/UE9F7LUs1Gg3ttW8ovC35pBebsD2PdMRnR05sxBeas+S/pVL9L3U0cL+pTKjfV7fNwlssLn3kc/RGj2MMJakQjN9CmdumzicP2zfxEu0PXP9ClJR0p47vxIOXUq/hAfSV6D6lUNWiLkele3JOwRauS+4Nx47iFGc3Np6FBG6tBMH42Qay9ZMwpASKdINxNJgmrRfCco5TNx4vEXuFsppXS6gZGXgudwQwpLjLq3pRmoR65RJkwFKIOpUfZAqEBtkW/1JSEkQuStKUFt0YpDyVCMXDMR69F8q0+KQq2R4fCppy0B7bWjD47q+nxHn5TLEliu33UqrcP5/vhZnsNPmFt9w5oK0lQ4+tdN0RIid4sepdaQ7sC1E62/uY+QeGPaCtRQOA6UKkMx0gTTouUXaEK6AzmkP9LLhDQUnYLTv96dKa2MlIBv6aaqQB3yTdfhL4EJ5tx0fchABLjPFhxG7IvFKDtreuqxj0OMPP0MdGiWfowWkcYmmb45faPUtcTIfYHNoAAYcYKlyUuEPP2ckQixG2BJQlCEanDou+JgzB3AGlVvsaVCUXJN9oFSgn6DP62TrsdGSzmI8zosOM/vG/lWke6v39E3Tu0s/aktN9PfaidjTr/7ettgKd8mkQU1OyLwiX6F+ktHHxp1efqU7xRyHD5+wMEG7vf314IDV2QxbcHBVtPu27k8H2caaX4FapGj35I2oBYthkzAUZcb0GipIWP37Nt/0IjCD5hAy41+/OPG+pf4ePo1IfEpPm6/ZSc8Qhwdt+dFgxGqQ77BCI0ksiALykuEXAsT2kL29LFtj559+y9D7TSQ/hKf5u10hkbsWTmyMbSij0VIg+10F9gQwhIfT5+gnt43FqE2iHzjDxwvLjhgm6+WA74p1GnVWoTmrDQ3/lpWZNbxTP+nn3/4AWiAyHf8oBvM0W+EbDd5+tie68iuOVp5mENTVkcfnNJTleDSHPmWZUIG044+WocWDcVbBWSPkGuJXi+aLRESP/1RkQjplbLHu766h2jRUVTkJ3QKrr1SbM/VfgF+4NPTB8eKxfcrCVlbXNCH5quOPtgMlUWvEln5XtAvyF6low/OVgvhasdLfBadUGzl1X1Bvl4vWCLEwUN6lkOADSrhncpSKXJ+y9K/HZAuMap0y9mzPftCrM/XLQ6v2O1zG1RqAZLv7pF5Mj2m7+9zmJ45p3Kqtn5Ifnplm8qpBuIheWaHT8fiIxqKz3Sd7/4Bp44ZH3PoFPgBnKbnGrECZjsPc4u8v49sJr+fC9X25XOhx4vneW+pIrGpsZIVv7dqAaompzYbz16QH6AaqZrZvehBnBMSn+fmsymV3adM8649NblwSL7Mgj1VQuS352Un8mUrWrW+uijvxYHfwy9gDQVIZsvAjCSvs3jP3AJ6TL6R97pQy5A7TIFW5GkRVjEjP4B8WIWUALmwCmo5aRFWnZtmPuQgTgKcsByq+G8gKAd1Mq5IIXQChoZ7+sW1Gw6mSFNKG9lRYz1xcP/oE4oLDssNhHTsqnfrV9moSzpxb8Lh+nO0DhUKjVGKj0CRdrS4CBQa4BaZ1YeRAW5pkbk7Fxd+nlL++vaR6p5sXrc/9HPmJZtj8sa4DfKnLkE8Ip/nSwoz2/V/f5+DqbDuH9AJ+QFm4z7gb0jynGZ8clMoPpVCBdwkFB9jGh7PXEGlqxpJ3kwVf+omEhw78ruTP9UdrG+LJj3b5HGrsh+U/XLR5HDx5CzDuQtwjzmwhqJfZsPTkBvLpo63yC+FO93QL/vFJDjhNgrFRr1XIahXyV2CtdNOkO0QiQIhsokp3C7TdDn5LoEClYDLTdl6dgCHKpGe0c6fPMhDBayLyAGroZ2AsduffvdRWquGg0nseBuQJa50qsB39BHFB6BGzPdhKlMASrUKUM5lDkBPvSN3TJ5TpBl6zhzPlbYPKc+RYW7QhbdQ715iA09OyW/dhtR6zhRsnpk4MrHjOXyjjHSQLKF5NbvYFqqe3EKTRlZG1TT8A9KDvOkqtCobPXdM//mAdLm2+kVsiHUpNWlgzSfX4vJGpHQrpWh8eNYfguLjAkNo4lhdYAg1bBVX0fOXYA/yrh6pZx4eP1z9TB4bj0jiSNFKXpgGaDlPpldHTnPoebqsodfnrnsXduOGVU41Tfv09nutjV9zGPpaNhOc/HhwTfvhB8yzgFVOPUx6SH++b2JskYqkP98mUoUYSd89qlHrqWG6Qw41eRVqFcohOxmfeoMwv73KfqJftqrS9NXDI9e0tBLDvmBJ3522r1IEKoP5rHqtSsgvcGfVB4MO/YL5LLbdCPfpu6uYx1aGGuvanS069RLqEX2Zz7laX3CWvmbtlj7ZJ6gSnXgP4Xj18xlXsCWVQrH02dkITkj6VWLpi9OegrQQot7PKNTGSadQhFpyEq7IWKJl7wUoIRFq7oSQDbcAHDjFYuTjRaiWNuFohDR2nzUf8ULpa0qhXkx9tIil72M5LD7FZxzIjEbZ7+EMzQjcsyBgT+mfBYF/gfqs7Kon+PVvPiQXtfTtq+d7vnHiuerD1fs48dSr5/n9OMFEf6v7XFZ+O07w3MU7XH73Yeipar1MFYmW/jnD1xOVYtx8K33T55LoPysSF8mbktyD/LP9uUueTRCxDfqG/F3qpgH5WDwTcPEci41x7nBsxCH/jM1d6qqh0BivDidvikCf2DyPp92lnp1cueGoG4cO13lTmwkgz6E71tRlAshr5J6yBRM0dVsuGYnLNjYZDhpbz9jJ1+dzHLfJF4o0CLaa8ak3DUi+hkrWlDLQ9kZ8gACFxoc3yB3bQuMPU8KAI98W0Q0Q+cahgrWli88dm4DkfXhTEg762PijaagXVB/eXMRmHmF5UDfhTatlK6JfbpEeLz5HRsWKi55+/+cP1ZwseXMsnHLf6qvTdBfRKaGKqRxqcmyp5Y4fnK/yeVC3LbO+5ZoSEvvQ6M+uHk69S6RgbREEvXh7QRA6Xes+tIRCw5ERSPeRJZJ6aGTZNTRZ6z0yZZhuHcKTjwwt50uHTu7X9uZQf09V+7OhpG2/BU341AB2e3PsfsWht9RP1dQNh4EQ0VNZ13HI28ieMxKhZ3NMIxzcBvUzRzPam2vzHIO96TAgenU5YrkmAvMJISKw9ZBdBMvC/SUR9PTssvb1p6bSb6x/n3Z8t/62H2Msl9a/wH9af+u6cZarKrSA3zIY1uiho183cAfoTOQHOJtB58e74n2OGe7usCX+hgFA/z1CU9iz649e0p+leA31h3hLA+L/HFWF4G8YjIR6o3bqdotDgExceMf8LIVrqd8wDkv0efLAatH//j78hsPQ/s2q/334Tdy86ydzAZqfKSwH41+tc1RRIobibzhE4G8yi4d9yAzE35B/mH8hoPkRDTY/MoUPat3v9/cFIM7/ElIAU2533bss8VfrHbXWVAp0A0wcem1y7lnEQwGY/PThAJ4f0rmLvzrvLoTDv0e7X8sgwP50736B6HcK1P6cghPgiUNA9J+Ty3+TwOC31OHBf84SHP5YDhH4Z5/8AvHPEmh8MgU73zydNBy2P527muwQflsg2+EnnPWZqKOtD6do62M4DNe7Wd97H352rpc6Dn5OkfDXYNc7MQhAvzrXS0DbUyMz3yzRme/MAR94ZuFI4yMu85WGw79JtPGZOATg3yQw9LTU8bGPWufbNyuA+/irxhb+LYd7pcmlAFQDDRAl6xvTZvsKt/GfGfTxBYTMvAyDb4WHjoPfkv/Uf8XpPz3PD90uvS3xyc49lg7r69j1t84bc70hXo+/nd+C40/RDnjmgC+9EUU64Ik62AFTsa1l2az+34ffMgiwP8W7X1zwP1EHB//EwamvZRCi/Oy8b0aafw7t+5IE930tg4jwkySy7jxR/0L0Yy41PcS/BWe/loF22varEJDmp1Fg7cFSx3tfMxgVYf31ivN9qUJLASi78B9pgNS5X2WcA+jRpWfL4Wb5Z75gavEJw/uOGJpPXDB1LOEuoRK2w87ctyIdt8dKCvbxZR5N6+3ku8BHAijJlbcTLggq02jUMBFaBTkaVRbDYxet6FIAhE2xS031NYOxAfJmNOjoDM2heHGzXUv0KQUWUEr05NjEAN+6Ngy+FVAECH9xIYQAJ/cKB4cQJXp0rHBoAGHJ38pglvBUYH69FHAFVgiW+FeXwJcGi6An6mjrI8Hl84kBfnKgxM6NWfLw/N3cRxOCv2VwG39zC7Vj0Lb6qnpL17Ije2HPZ3kmA8Wrkb1xc5lRyFjgzAHfnSp+MO3Aur2TrxdAj2yPs50bw28vTtHFeU6Rxfn5wirsoR3OwKntpXwz8GDZEv0skamFJQ/3LubCsJDqzMwBb3/spWe3soslRNDpsaWMKTR5Z06xAZa9Fu5TAEAPzByZXZtL524fe1ziX6M9sL0479MGASNcrjdmwztNAiB5XvxI5Z7HH8pWW0sip67cnTiwNnrNIW9Vc9WMW795fqC2suV0JoI4ZvDcHt8BysO+CRQg04Af4GwGoB/vImQugamtb2lEudcR8uu3LeyHgBtOwM8N2rH8uqURwyGXbzrA8OU/9zdDli9uewlwezW7vUaEaMzD/e313P4KwWd6vveWeD112717UO849LsEg2NaU3DTY/oiAO1x658aRzv8Hbd3TWMB4Fv88sm7RsYtv1Dw8k3l/1N7GlB7ePK81Wr/fc9rS+cP/Jvg8H+uDMesvzrP23HWx5RWY9Yv8/ZNFbh+jQ5tp+ok2vx0irX+trb3uX8Zt39N7SrC+k/FMbD5NLWfEPW31aVP9SHc+mnavsWaf8D6SSPx5xSb2ZnEegeo28QIABAnXHToqVcKTKzNhf0R0YN9EeBhfTrS+jQJtv72VYDHBzRg8GzeNAgRgGqg+TGPGkQs376a8Al/x8Ffc7D3nd5lAFtP8y5DhPV0r2amfSwQub/s0xI3o3NP3VetGhB+jo6dK0c63yrRu1dSZOxp3isNCX7si6if5gf5AcrAD9gbI1L4NYe0jf0rIunMw72HEPni2IGDMU9dHUIUXR2bXkABV4bNCygh4af46ljDpdfmiZWQAMs+4vIZIQLrS+YRlxAbbZ+JQVeHJbw+Jq4+NowQbv01eP+KL48BXaR55yZk+aY6djbATfr2TmbdH0SZ3ico9czYrVr/QqzlDf2ycX7xHjYdkvdt8Zn8NpSfn9+6PQfOJNyJeilctv0JmYvoLNEv8+sQ5cyD6scfYIxbKW3TrFfFu8R/ujF2GJ9yGX8Pj33Pe4eHCxIeazsHcSvf7+/jM93oCsbHvke+46OExMfY5rEBNsoVqj72wtWaNmM8bxs3+546Xn+M8S+8n5jqhMRnug8VrD7qbH9jJDxqzadseuod5mN47GMdcPXpzjrXjMSnR1tn+9rIAx/B4SPJmeeWgPgY+hH4SHLWmTNse0meamPd6s/39wEyzakA+yPTlZxY+yPkzPOpmdhDeAhonpcfwN6AKhJ+Upx+enhMa21EP9nCcz/6EU6R+6s68yzI6MfQH+anb0IEFW915vnMa5SH+Mhsnjkjox9DP8Q8mw+Au3dpLnpmZPJl6A/zU7fEWPPQQq2zztaZsdqv3rgJzrhpsO1vz43Hb9793Jmyo09oKQVnpy1F2ueWnX0mZHho6N+tzizhyYTTUA8PxUbPhn6E+2oUGT23MltnTsjky9CPiJ1bkUh4WH1ywVDzY5vXAeFhY41ESLyBLhWKkKRgFZJQ+/zcu77twZbrbxTo4g31u/HnEiB1Frp0pAnSqfxcbYAIEIC9GC8VatJxCtR9gaNACxyGw+0QaPUNmhSWRC4l0CVwC5jVR4RAmjQwBFLffITW59X27/AhkLr2IzIDU98drMj6vNrRh4AEQ0tkBK3Mzv4oIe2P4RCiQBxa4lDfICwVqUFVgmNErRKpQeKjaO1QDRKN3mP27iu4CvkmIbTHrJpiCzXqu3jQKpxCm5Aenx5chdYeaaN78ja6KnKHGQ5jh5VuAbq/wzqyTejXb5p4VGXTdqdO70WQJTTEtfThXeZO3kY3rAZR8BhHp8gouvsuJHSIzNAPgWfRJgTCE9wm7JWCY6BenYWuhMPHtwmhhdZu24QB6iORdejuu4T9yDqbuxUP8WkSHCH2FlmJ7qrBWZjhEOPhNdBAj/jQV6K5ABGyHCJ0yHKAZxmafK8QOQpk6UeUWqcvAG8yTeTD6MbQ9RMDozgvAELWupcQuYYhtJ9q6QfUWqcPALt5TayRw76W/t08dTAYCPNrBvsWGIkr9zMvwBwKgPXOFuhP5H/9mw+q/Yl8pqxsTSht3Ms18r//84dqTq/Jl9zS1lM+I+Fp/d/61y/Xz3u/jYDwzFEu1ROPyx+iY6P0LI9Hr87Yn0N45hs6m6Zr61+iMwe5VL9+CO8YHROjD3A2i859cOwo3647KQN1xz5fPLaWQef21jIhem6DfCHo1poi9F13Mk535ugWqzsmOo+wO/PTyFBw+jwDN8xOgoFjqEdozrx8rNXpmSLBMUF5gOb06VXhtiWkQ+8UaZO7jZgDPNa8/qE7mXC6U5xNzoKzyYb8gKeR3Vmn4fEfwAoKSJbgW3geHhEJDwdb5T49mTvWTxej2d/+8aPUUt6Q39Vf9cyLNYfCldBg3JAH2H2//nm0buRCHWd77MU59zeXV59GkclEV3bGJwHFayf3xvayuwuAjzLKPCzxmcfSsK6rB8fLvUsgOpSSxoU9lnoAOtPy0XuLEqVIdCi2jOGWD00nKNl3MMGZqCUfYXimDwAHhZSYQ+Ex83oRysMMUp7l8qtgpevxr4Lyi0t45mcw21XTsFy8BNYxLPWYrSUaWASjpCkuJLTUQ7aWOrucG053OgUGhJZ84dS3KqfGJA/R6YHVZcqJA126oR5QXXbLx7r0PF+CQSZVvAtOlth9NS+fW+sVBw5F2uRM0TZ5Xv91q7NcP7gn5+F3PUWoP8+cIq3O3PErREDsK8WmWRnW8PvT7z6UirxdftpIzj3afAi/oIz+b//4kQe2r6mP9dfhERtfXf8+cVAyvVl/0q0lvlwjXGrQ9Al4DZJQv9UkMuTJtika4NVbqONSDUVHg4s82Y5dqqgSLk+nyK4oTc+N4svL0/rhBUKK7Ita6hG6My+ftZaO053ItqilHgKO74oCYx4qoQWY6RXWG9W7JfbRPVci1sj6IHGwVSbfFYXaHUmBqShJCkZH/ARhA6LTQq1ydE90Wj9eeTSyyGOf8M3SNuFTlzkcovPE4Keff/gBtnB7x8j9ORsPfI+1+YtmKLCsXFJkhcc+Dhyxq+b1Y9MI+3gv3GGV6G5oCe2GlhJadbdvGwekoKVEVt3L/DgAtGFTODhQLhxZvShVAr2VfZU5ApwaOqFSRN34WgduLNMLjdhYcjpOfi7dPZb79AFU9bn6WLnYu+1STlLymSOXxxxMLJs2S/8+eXv33CB/5lD2MXkTMzzIdyB5TjrD36sg4WdKTsCpQzkUr0IFqkLMHCqE6mRckeTt4ypoDWV1+6tdJO/epdrJ21uB9nfT1uTLtdVP5K3q3AanJo40PpXc9qXnK0Xuq361b2M8NhfVqxz+9LuP2lJ5/Q3DwwwR09LD0DUPUzl5jKDmodZoH1aFgRyGFEpN9TWH/fG9RLQKoOna+tts4UpDbgOdLBwp0sJJ8hrUoPKV7DUoVSgH4mAdlRLqxYRnGXekJZU5SiRBunhpFBlBiAtCCboBuvgNAHUzLWkkPo1SpPK0QpHmrU3hZ+1nMmBD3qeog7wbNe7r120uOuA2h7ek/cS9TMf0xVkGKPouvoXatTYHoMfonCGvydl90sue5Q/ffWjWbjnkWbxUvv5w7PEH5NAEWH0EbWzn97e313ybSNlaau+316kP8OHtjQ/w41uDQ52eH9DMr+6suvgNPoAmhdYI1AWgUAepi/i8Qh2kqtfTlJEcuo9ywRFiX0W52G8Ij3K7j3KRitRZg3dCF6S9WHJo0fW4Hltz7YtwFyqEmtKtklx+65L3aPTZ5eSN+imfmaeKTW38hvzWmAw8391cvJl52xfPfB0be/3ZTH4v3m+993piGvkYnukyE9o/4cstn2N8zNjbjs+ZlwKOVz9P1VFJCSfcMm2tTL2esg2H658H67DKaaoQD/AzEvxpKm2ojnag6kgKXf00NZY3fU41bq9+9itDd4igujPNpQ3d6YzTHWW/frm6fh+pOw4jUqfeX/j2cg0h5cjdZZqdD9OfkPo5zV/RZkzbXf0scy91yPfU3b6HvsvOYGnZj+qcqnUcIeRGsKAbwI4wwcXrJqSgnstOGO2LJ0IuvoQGDYW97Tn1Atyxbpoppk3Lfk9uO1MlOPyG6mMH7kj77walLmvQknqVyM0loZHJPAcEjkyKJlTQv1y9ojKWJfVOgU7RUr8V76/Ic+JI5Dn5gKHAsOEskbkQ58hcgsnHC8fFqlOpKJNGfgC7MgPSnzOnSNWpFBmM8HzmHBqMsMRuWgHWAOwF9zt1W4vXrUjmEx2jQ3DabBTOvFBxDE6LdOOssxsn6OLnK5qhalld3fHUtNvR4quvO15Efkndl+2QEU7NoW68kg/wRZDBcXWFQaTe1zJv2opMbOuiKojzJTW2Klg5MiuvrigItThVIrPyGl4TrKE1waqM0pwleVdQywokLylW77sE2ntJCswJ7VTzgnoWSl+epz0EnkIL+UKRDT4pdCHvOcWBQ1tkUihSLznSz8qiiCZQgymuzIU0+CIKLGQu1y8aKV37CDW6ziuujnZYpX5ZUFjS737vJmgNVvqdxJns4MVIGJ47ZKomLS9t2zmesAz09i411Trdu5JG+MNnDskbDj55VpX5kfTBsZyZXqC319mpNnPNZVLZqCW6wYGoWg5q07jaM0n5smucqJfWqqVu5jtSpy3Xwxcp3jBwAKmRcer7PDafOZJWpk4K1ycRU5ZqLvDtmreS05le08SAtdFrBkMAuz/TL2+xw+WbG3Z7060zdeTyrYUYy88dt3wxd+D2JlttWoHLF1sRfyy/4JZvtu/WVVItp/z74fptUXxfvwpu/eYi2QDlNwzyWP2W+9fP+x+vn4M3r3CK1H77+mLXPaIoUPUxhfFP/AsQf3MVaAT+4rcvUP2fi8s81j7g6h2Kvylf4/XfPgE+BGDxB3yALWGD7WezN14O92W91/31t+Q2cMMpUDPhT4D+tzx7X/r6dS/Hy7dv6QXYn0YcuX4THEbAXyTQ/DcO9r6Gwaf1UaD1aZKi1ceUsx8f8Pw6+u0PaHb7ls1+wP31t8jguWmw9zUMvukPMHpoPXr7dgmMHjRprPZoivS9au7QC0i9lFCx82//+NGzptfUOeW2tfLiHooXlZNDgEqwczcM8OZZmYODQ+XI5FqrBLsXreJKMxm3fom2DxKaXKutjOFLS7qojFUc/D16+/bQ3Lrb0hhefQyDx/oN/LfX/1S5MhcT31949kl1PnFL4uHKbVUMr/jPDE7c2Xy88Kkcdldl9hH91wweb8uU0k9U+w+BWZTbcAFbr8EWoUOrbZ68xG5YW8y7rfaeQbPxvmy2Wn4f/yaBxZ4+F9vg8YjhAPcoeyksVP8tg2/bFxZPtZRttbyJTVjO4e8ayjOHYYr62GC3cgqPkKvnAds5LUXX8yyHAA0tEpuyWA7okH9/aS14h7HGFZRakgQ10HP8YBk8jky3nA+PLZ7bYb5k2DNQQ8ElQ88guKhnv+BbTRUXpNj1o2sCLdlXSfANI8vhW5AF1J+cgoMIy+HbB1yUr7sDfydvy4Zdt5xTuZ4DeIRMYW/LNTeuDEWIIsOUHFw2tAzQA0UtR1cNLYd9/aQnfBi/uwBwf5lE5pdnzLzYj3fJu8e0zPWdd6kb4/l5OagAF9+/ePfoNfL+SSQkNvOFE4M6Nxz14uUqOOrikKGKo+7ehIGuXVOkTs7H+bHQzAfisSo5n1gHU3dvyI9Y5xJ1N9o8U/+8Z7TWU6P9h+vnUEs8n/nGaj27V8CR1obdG9RGtLehUZTmrKjbg8H7FbtVgQbBnnx9YEMVSN69UQzFpoQKdj6bijU4VUItvT3bCY8+amzsZI8Y4sHxoRnSWAohbbF9t8yR31/ObpJheimFQiXLHOhIxAdnQEciPrBErl1TYGwmPvIDItN85HfdzjuFn6mzUmlvT1WZIubh4n1geXHxv/3jh0rh19Q/jxWmSqeqsIcfEBv7NYoMcFqNzPGbzH6qIOOb1kJz/BYaWk6HFW9Qd2cJZ+qFet24k55p7x2uP4d6Kr0XGldLXnrJT+R5H6t5woe5blTzmZsODhmY5glz3mrjhmRgmicbl9aTnEpqDzmYBsTNT/DV0YnBfl6XRgDx5S1wtHwy7QfmgVHOHSgBohQrYioU/AW2AD44WAb3dYiqBGNkJk/HJ1S7kQGf0KOloAm6z+zdCoNBeY7gdCN9cWlJubR8Qz1CxMWcPC5Zh7GTcsMO9ed7A3YGJsRKbdufPkIiRBq8zYqZhhz49FY6QznY87sB+6wIx+6z0oJtUVGNZcAp2OOwmTur3LdKhZEMzNjW0NPNKup9BkViAzs2c08RXzCFpvB9wNGhKWuwR2A7GlPqSEYqIY1RTcCt7GdLeB+ftha7ppcPbL/I0A6/gYIVqZZgRaoc7BKqPXcV4JmrALMQ9772zCDXLlsiPvHI6uEHaLDPsdf6BBhUScFaZK/GCfA5cjuAlHePbJCqvV0m17RVaWeEcMjAxo+ZdcBWr36C3wjTJ+xa2ih/vYIv767dnNe/Uy9peXkfXVu7PU3T2rnjLofgm9B6YL9Z8O9jP91ds18GoJewXy7/OXCnrWur5vwzQHem0zTg9dvTNJn3y3+x65+urmntzGGyo/VPV9cE7N356pqBPyXc+k1WM+DfLP73lz8ddRnLLwW3fLK7t26tMiOXb0+67NYnA61Pm+6u5GrXD1Cf4rdvxuFvMr7S09bPuffD5du7ax7WX4H4C9C3L9cv3vMCd2+Ljhzmq2uuRw7L9dtGzcDfwg9YvzrvSzjvZa+uCVl/d9s349Zv764JUP/57podfpz1t3fXRCzfDDQ9rA8Brb+9WiZi+2ohF/wA1cf2yCLWz6Hu194tE6FAZuzrsf4zYxiH6xeNFoBooP23d8sEJF/z3TLY5MXeLROhPt3nvgWnPvZumQj16cm7X5z6mBtgIpKXnr33xbkve8FMxPIp0vt2Dva+3VWtRoKBW/5UdauUW01Q5a8UGPvbe1oiKifdV66AlQd7DcxN7feVYc+gb1TLqWs8ZB7/fX76feawD0fs974jN8Ci9Aa0nqqxzne6xwacu/c0l97ubgAuWV9z2OdQU62KKmxP1NHJRTd3zKQt9Sr1VRc1X/uAHJhc9DSV9tDe0TJAh7Z9usMGXxqwHL7lRgmoPxxrHvp8ic1u3QoOf1vZg1eGLQN0YbXbC2Yi0G8UmFl3e39NBPyusAc1PlNhDx5c9emCGbT1txfMBOA/3S8z1m/wv71+OwOEj84th9sbYBrgn8kP/SReHsn7Qui5xMeUDlPlbUQTBSlfVzkEBv/dXi+Dzx37fLsMtO7fcwXmLksGEtwWt59wdyTEU3dlw6xA+IPLhpYBOvHqObhsaBmg6z6DduzEjGUAr3ruN6zGwk+RVcNOFFzztxzgoRVxCjZtxIFF/07ztB56ZMNyuJUY/faPH8RaLPXnqt7j2HemZ/F+f3im5xAhiTYQkYXJTi22q2AZ4M2zBkf+tCjrZZx5Lsm2FWizkf/t9RdfdwP2ZHuZJurg+BsG3zIvubb+JXlfFgNqZ0FW9ZYMSvDuLYuyGzDxLRy8fYsvu+EminqR4NC8iK+aA4PDEl13K4u6G9L6aHBX0HKA50YlvPBWuuDK/q7sw/PAG3EpuLIPp9iRgWn98LIwU3Twz5QCky8uwc6dFwN7wOVzcE+NQ8tuPI3rwUND9kUxYGLBEtxRY9HIwglrdE2eQ+tuPNXd8OqzqLvhll9TtGuvvvCGjK1qlmD9qb7yhhQAxU7LWwb3YsP9wj8mG5tUO7DHvOmreSW6BhAHB/81tLJXa3DsXxdHWYGpY5Xgnnv1dTdg6lij6261RXr3qsGheY0dp5MUO85rGcDnrSRT8LyV5MiOuFBwR1wW4264zEKmshvcdkpBHUNfUmc/zQKMfAz5S6Fbe3cHQ8mUp2k0kcpfh+eQ+nQKdFA/cYj7kPr8Vhh27VO9B7t2mp7Zkm3EKF9XnEPy5MV6bfGuFeio01YSpRPh4OHii9MawsmV2GnNieuZD6nbg3u7XAtSruLUhpDk1alNASLfI61Bmd4jB0NTshdsBZInjdQbc5nlN/IKJF+dZDNOb4o4yTISetVQyTYJ3FOcvGALbvFse8Y7+QrUGyZniwlni7m4LUtIbFgj1ZJ9ZHaiJnVI/Sky++nnH36A0VW3V+t1UGy87ciPaD5TW22mcm3xoSFfTaEmvlKKNGPVB2UXw6Zf/+aDK9Nb6o259C+fmDtcO3Ok96tVAq1YnUaisXaghkZ8dRHx4dYuKTKSFx/wEXA/CWlg8iocagzEx3tAnZxvPsTmf/Zewk8PBTTDsogmgUHHfKvfrjY45OdL97AOsPloD0m9SKBONh/sndEafVfo21/cfN6v1Ctv0sqZY1k6lWyE0hsGWy+99nTqVLfa27eH5+DXHHLaWqF+8QOWCD2bnIFQ3pSfx1fvI2QZcNp653yRwRIgYzQfAFUkQM9Wc38wraeS+aqElwgZDhEIGcO/IyQZidB0520AQobD2GSb3WX3EWrT23upFe5XP2EJ0rP/igHJcIhQI1UH0rMxvf8JPVlrykUTVgyWw5DCZsVwGyTD4BtItUA/4TmYoP2CV2uxAWKYOHCymnTfqRkOD4tUGtAidTIWtZZtJDUKdGoTA7xBMgy+qRFhd0IR3E5YYjQxoK10VSRGJjLdlSghI6PO0RZ75oAPHg2HX/xahaqRpGA1EmSEPTjsp8nffUJt+wOk5czFZIdikDmGP7yX7CX9pRCaDeLT/qwa1N5ZBgF7uc0OgaF7WaODeMuhF92yKtQj6BzEMzKI712CVahPWQJZFQIYuy4ohBYfUFNSYFS0kMHEAR+cWgbwRLAmSqE6NDEICEwth9s5zgApd55AKja4LqI55aPX1E6hZDjcDE6Xci5Ad7OUQqHYsKUm5tCy18QgILazHD5zqIIUcpXgzWwZwOsVlgHcY9YkGhr5OgbooMsy+ASoIgHSaHdgGQQApCk2C6+pXzClL3ODJUidYuMuywFegK85cew+mxnADZFhgAgqPEZZgjHKwcbaMMCHppls8D68Z+kKTAAdB3xsmmk21xnp8LPtlXLbhJiQOsTB5jq7VmmDAlQptojgOOCDxlwjC+8121Ym3uVPDOBlFsvgc5NBAbKdTHzekVtwmcVy+CUoupOcZerdcrCNxsFAh3c49eD4oRxsszRADsHdWMsAn/7R1IqFdxkdh6J2K9/XVErI8N29SDFzyG3EXb0zbHypUo4dzpkYRFgLCu30ViIOjusouNVrGcDbmJVKsMexDEL2cVlM50Ar78TB7oDmZjJ+o61avdBaBU2dWHz86zjAcyjD4RtKglWlqReLnj2ZGGjZz0exIA1SI2yA5zHS4DRhYoCPvgyDbxhlaEmHghuyM4MAjHw/FunYSgq22SVF22zD4ZLN7hakUviZgxDbdFa3nk8VjfrbA2Yz/f1+TZGvnyk5XL1NNcf67fK/v79+e2ql0SZy4vLmww+wSdqA39wgdn/5qifhN1ny0fKrTaAe+J+7W//oA+p0+TftBzRw+Ff76N7jA6pAP2C6/Xt8wJmT3IcfQG7/nsqfDpdPHLp8O6K5L18Yufz5FiIy2/fu6nnevVmRxrOy270tX1395B9lvzHl6ZKjmmhLktf+vVxb/vziHsmJy3AOwRdveyQhfWNt3jgo1LvU5oyDIq2bxjp3S//TOSKNQ3fGodWLy1/Rl+Scb0E639pd7FDzNXhW5CVpoG0Tc63BA/xKQHDEvbcnDRcYirnXAO9XZL43gYxo766e3b49dTNlf/fS9kx/n63eb5dJZwbaD/FhH/YD8ak+7E/QqE3mi8WJOnD9om79BepYZLpZHGyZRb3vpQ79AE2Rxq0780AVaR66Mw+Ci3xacubh1JHvo9W3NG9erjjsW/Yhv15ffSuZ3tMX1Yy0bS1LoO1vpMCwdrl+0siUurEPHASpnZwCK0qtOstQkCFzqy7iZ6BhbvaxwAjt8QW9CoS/yemM5dzmja3nNdXgelJTjfwATfPuTR0ZOGtKgYGhZgr1jJqdX2ecZ1Tym/dco/xw/b6a1zJQeYoEx7VaJLIcqb6gx8iKgPqCHjAuVIn1vLqo5wG1v1Hs6ptP2YGrV793KUNVXzlSd3ytDWs5uwTa/Z58IR7ZBem+1AbU/O5LbVDsuy+1AUO27kttlJGr96U2pOb4Uhs03u++EAa0Or1KaAPK0v/sT1RcBbsvqlTAcMSSx/cP+qIKlqHxmuGAT9V7p+BssftCWPuy03r8r6/PAfRm3xZOfaOqJwRs6O+3XrdWLf3nkIGz8Mb04o0fuvYBNubp+yhgv/gBS/q2AbjTp4Sk36eAv1PtZwL+Qw6c1HEoHcqBkudQoRzKLOV65qWoY/rWCzzoK5I+s0Po1FNdxxyspcZ/gTpD0QuSfp8l3EsG0rcPfX6uvyHpZ69B6YYhtc8HDPq25Kw7g+UxmGtm1JL/NKNQ+DlWfcw7k982WIVuMPsS5OMLGKpAbeEI2tUvGCqkVOQ1B95GMLSffT1z5s+w8MHKxCIPEQ+UKlBLNVZL7XuNAfSzc2NCF+m7525n+pwrb5QLAaMt+6LiZ7hISICK3wQMjYbss4cBXyA+FmoK/YIWGwuJi3jNw0n36XcJpd8W8e51Q7rksIh3sdFc8/GuIrOaxk7GIkj6wfF0Ey9jEagE1MtYoVlT6z5zrUCM1Ee8UB3SLEAZ7C9XjE305gu2kQW2Vr/6ZNZhOGTWv4dDyi9DRvqKOy61lHcIpdTLywP+Xwi4lkIgvamm2YZ0w1Y+nb/nzPYJw5EobLl9/fy9IT8wGuEIvyZfkurWTo0QGwbu+RO3/m2E8a19+amlGR0b8DrqtZWNn0+X/fjdTfDtC4wDfQP+XezN8/NJ6z5J05DYTw8W8dYkXUbHgz9NopTNPL12G3yTbTw0/zlav635z+RD0J/ecxro1wJEfxqj2dFvOPTt86Cf6CsOfUN+oN+2rDUD0ef5uSs26N8Ef3o89WF3gLppHk8t2zDL1irfdyv2edY7lm0J/vT46254FKf6PA8xFaP6dzWfQj2uIR+i+XZEagefkeATo1R/ib6Zj4JbfUM+BP0ioeiXUJ9rXyZGBzyGekSwOS3/YfQzzuiz97gMxF5SqOZLio133LPTWPAlRUb63Jw//PpM/jH2z9RDFH8aDRzYX1z+EvvpkO+u+EiTb+cC0UZHjb9N++JPFWIOsVeOzLIm8g/FR4YjHZiELqXbXQ79bNbuRprzw+tD8YFhfhcU9ito7Lvud4zOH7770Kz9NfX96h0SJTpTYDvSHcNhT1Oq1Z3vb++tCaGHT8HZNUv9Id4K9CmVQlNoQ/52krhEn5KrYABj2Yn8A37k7jJNnFt53BKc4lzu1+dij4VbbMTAW85Fr5tlD35xPr0CfXpljgxmDfkY3WfGORYPT0UVlt3tCDP1oTx5k85nnvs7xr8Gl64ngNCGv0qo8ouCQp4l9nbUcKw875tLkOiLBhZPq2io3dcUWb8z5CMqSHW6OEJqIsaBP19LUZhxtdPapzQ6MzCVM9Rj4s1Okblc7a5wLQwDX5IvXHec4hvyZaOU94E0JPqSvM/F9Ypn6rvmdxz4ObRubchHVJAkS6DJn6mDsafQTrEhH2Hx7frRlVMh524Z2CgWdu726I64U6GmoR9i9O0XwLuVE3l0w0xqZOXaUA+xO9Wl0aw4yyCwNHQp2ur8ecWFOzLNZsGTLPGzWRdLGEtwJNTfNgnMsQz1GKPTQv2tH82C2nzVSJujQH+7RGe+UxyaAzU7eQQGp02DU3CD3PzgFLCjMlPfMyDCQb+Yauo46DOwJruEPlNg0auFTk014kitp2BXOC1/h74DoSfnCgvOFbYS6Qpb9MTUtHzw7MJMfbf1QIPDGtniaxw8o9z8wBTjIsCZOtjPSoo09hLdXbXr/0w7Cy5Gaw3lC5eiFV9GxmU+Zu0x4C8GpioOnUaBqU8LnZcy1Hfsm7X3AOzV+doCNDp+Xgo5Idu6hFr8HtxYbX5gCmnxYwemFDYwtYLGUr9VB1yJ1pAfoqWtamJgWqvJuduC6y4pOXdbG8zqGOoRUea0fPA5RPWjTNSAqmOngXrar8Fi4JCm+lmpq6q/BN/PSjWct52pX6/CLqHhyMRW50EmeKHRrv9h1VrFlcCVOTC/0iqRsxxag3Nbu/5P8IFnQDV2jkndHJM0XGHBUA8B308xNVwlU90UU0Kev1UNHR425EOifPsBn9EU0u4oKgFdot8pMMUy1EM0348xQc1O97PDQNXvKdLjGuoRDZSeOLCB0v0UU8XZ5J4F2nrzss0SGWh2P8UELOv00CmmTpFNVUO9DNRzlnLH4Nu7hh2H1OqmpSZgftv9IFMjoO6QAgNlL16ObAsb6hF1o+6HpBpwMrZzZF+4V4qcjDXkQ5I4+wF49Ovs0JUyUPUl1KFL8IUafXGFFdCh+zGpggs1e4t26Is5LFxJtvsbrJB3KE2L37EnoEMPnZIy1EMyuO4vsLphdGZ4alrMSRFuW/kZrwrrDtu1R4A/o4ONZB11aNWupkyB8/iWfAz4/v4q4MHnmfzZsh1ZfIj1efVM6XnkRbecX9zvWw6pD2y4ZLXU/TU1a2zokPwfvvsQ8/jtTn5+xotK7meOrs7oyAPrfzIwb1mU1vNevNATl3QXCxBRfbrYlKVO9+BIota+fprjkLodLdipn6guHFK3rfnH2vkS9d//+UM1J0vdNLc36aXUfupGisP12+72Ax2FoWPvixjEz93tdUjeNBEf5E88JnVM3rTJHuQbkjw71dFrau/NwkT98dATl3rq8OHh+uusOqUwTnXEqY52IPjqVacAyXcK3Fb2YOZj8fXitvLRyCCfpwyFc1rFOi/8yeHqDfnPbSU46J9P7/308w8/XNxQ0+1AUs2ptOFl26kn5g15H6NN5EvLe5Tw4um6a5benqr79FSCU8nqFL4CFb55lQEaA3vw6tMYAN3UdHrmgQ0OeXtA5NMYpGuLH2rP2qwfsYcghl3bzPPsR9Hr4eozRRqD6RzBQ+k7DnpWkAdfUi9O6SvQRTUfdSO1chF1v6d+yoc0H3YD/WvzQTHQmKkPipFR6zTc9Vg8Lt+ZpgLB2ZT6kBgJvAtYkcZgGp5BI6Mpcu0+XAXGBj2Heu+pwQ82ZFOT+UaCv6TOKTLy6DXSFvRF2AR0UF0DvavYkuKgXkgVRz2lOP80qN2KV3kK+boh34tdfNIt5XzmoSd+m+pM9AvVtnHP5SIDXy6eP2DbNemEKT6Exz6KOOBJ0pGrnyJu3VTkmnSX6NtmwP78dD734N8hQPbRxV1/kiL1x5xtHh+w2S+4L4Hp9PHQnxPu8BCe+c3I4dqVrwpgCZA5gUzCW6mXd/ASoOmM8A5QxgHE6gCSDAXIHBMmoU1KaUiApoO8uwUCapDMBjopdIPZo7w3TcQSH3uU92HjkB6sOROtjASoUTRAzTmBMwPJhwApuy1WFLrF7KnYCIjsudWHDiEhmvuqKbWjIMXUMA4Rss29CIS6N9O4OCibOsZnHIQME7O9LD8AH/sFn5ss4zQoU4oFyBwBvRkHLT+gkHfEFSoBcpF6TZc0dAmQmVyg2rd91APo5nNxVroCTVDm2EDa0I9IxOwHfG4wxaUyuUpwKpOrwCKtJUDVWWiuOAstPpAmQnp5wyEiFcuikS5MnYXugtxgmmLzjKy+0pFw8HQXRnNHwmOO9UXA0ykyzaDEoepj6N/1X7//8wdVfcNgf/B7uK/UzsyXHUnAQvTpAQQogXw+SD8lgTx5GLIaej8CoiyBO5goupRiOETEWERzkF4Tcg+zK3bTDQ2aZosn+rrfKltOzBYfom/v+qZ97uwZfYB+cgqsZFF1GYYJcQH6WSl6B093Wg+EFFcMJXE+RhPSwpnDYFlpKNHznOh9eMSXaRJw/zbnASQj8WkSG+FSk8BmA6l3AFyhG0yRZZrBoWdNbzg82hmvwsRyTQTqkoyKy8LKop2ar1dppsHUif7wjq/OkNMl8ZYUnMIU36wF9pJKXjgYaLPNcIgIgEp2/uXELMEhQDR1AtpelYACZNq1W2HtWqF13OL7tSqwKmKZuqm3dsBSBMW5sIL0MJb+wwMzMIIurLB5iCX+HN0HsF/wpYmLl52eJULP3c5vTrhCY9Cy6KcCZ0YKtCG8hMh3bBuylGLoR4RxpVFkDLHo1x5r0Kl2ZJkatrXZZgBAxt0PvnRoslrUD+4ozhF0CQ6FukSWKzktikEd6ep5atniyxGcNDBaZPKGugkUIYou2LBvqQJbSuYw+KedrsiCK0e3bLmEDtYwM3C4b/kBzKAdsMQf2RJeAlQluOJnOESYafZNW2BCxqKh09cswIL98gPU1zuQ89EWoFtzX0t8NMVGiqyRBQ+2Pdu29fEPUn16tIHuFBjD1cSxM1M1MbDgtAKoJl/tYJj+1LwI0qEzI4ZDhAYZBviOYSUN7chUig6iK+mNLVYtdekl/5N6zdqe9ZM0y5b0VEu1vrtQaWaQG+vWzzxYU6ebU0jEkn9WH9rGB/T0KkKhawgZDkp5Y8EiNN3gsV9ADRTws/qM5af9xixGLt8+T/4QcLkm4OX6n1vaQ8CU7Pq/v/8B09W1A/9ScPg/N5zHBtOtSW9I/O3tr3D8nzvC+wZTu34A/tP9qWD8mwTjb1rCD/xJgfir2b955HiE3b/TPZ5Y86PJbt8BEGG3r+HwDX+6hv+S/PToLhieTDjrvGRAHKs+SgzCx92pt1MvdvfS66ehrnn3iQHePWqRQOumHOzdlTVy+c+tqpDlS0JFn8v1P/eRQpyj4YD37qrR3l3V2wfCKVAP9u7aQ717Txq7fsMArz+dUrD+GA73PmBJvlCgfev2ZcNct5oS0r135lgDahjcNqDfbkl7Il8n7yjrd65e3NN4CE+V2OjHrr9x30pvl6sbdlpwJ2/PhKXMorUfVTfOQSTBEUQXH0F03A7T6PJA18jyQO90Yf0vJbz8gE6BFrSn6T0z7mOPofCx1G87mCUHW9+DV0AtA7gL7oliCwSWwa0NsDBx+31wzsQxI02cZREQZFkGaBPXU6VQC20ZoC1cT8LB+0s4dH81iQ1xLQd0iWkkANH2QRVVgFutP6cUqz85BTr4nqcKH7p9ZBngl08cW7+1HALUJ7jAZxnAjX+eCnx49Yks8O2XyQZvXkmBtjNH1/csB3iBsmfl2NDHMIDXx3ru0bvX1/eu4r8iTymwuWaphyRHRCk2eCCKdL5UKNh7UbnQHvz/QVdBFQ==",
    "rd_g7v4.jsonl": "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",
    "rd_h8c1.jsonl": "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",
    "rd_k4d0.txt": "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",
    "rd_m4x9.tsv": "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",
    "rd_n2r6.csv": "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",
    "rd_p0w3.psv": "eNqVfc3O7TqO3TxPkRcol0RSlNSzABkGCDLJtFHo7lQKqK4A1ZXgDM7Dx97ftkXZlqg1ugf3rsO7RC7+SN6W//5///bP//jTn3//y//+099+//X//Muf/vrP//jLv//b77/8x7/+xz9+//3f/vSvf/nbn/d//r/f/+uvf/rzf/p7/P1f/8v/oD9E/R3DH0P9IwXS/xzDP0n4pxB+x99xS5kzyf7HCZgMmGuag8VaZseydjTiHFwsOHaWQ76B07XALJm0/qbfv8amUxibfoK/Kwxb0Rw+f5yAre+y1DlYERpl2dFxR3bgOAd3nI//bBxd7+CvNzhw2KhyMp6Ofwh0h59LDGXbnce/eUZEHvL4NUGve28Hd94Lc4fEMHbIE9x5LzjgfoV1DkYWGAvAmQKgJerlMXcd9Qt0aChiGdE/h0m46xC8J2zWMKsdO5qA1GJZrrs7WAHfcS/ouWVBBC19vOca7cu/R0MBb/Tl30mVvqD3rqMwBGeuMdE83gmRf0Lk35d/q6SXQnqV/72QatKyk55YLst9lu69oucsd/DpjbiVKNKV8zTD6qz00630T2sd3RoWOWBdrht0axOO5VubqHMwIWAB4ge0Cbq1iW+3quErOv4d6ULvjjv7BHMqWyiSDHyfDXQA340XJqYOHWdole9cNaby9R+nxFuuQg6V5u5C6Vs9xlQMWrmIQ0UuKmnLqXpeEUOlVHaoiKWSyaGiF5W8ZcrBoaKGSo3FoaKWSs2O7WJth+IQLzPicWZ890qdGz8b+qJWzLCwECCLVu6C/0aFxuuML8YveJYtFwmfMj9mbnTLMTgJx53Kk+dETOUsnbQ8J/Yqzw6VpvK6aVVHidypnDwqncrVo1Iwr/RJER0qncqrk/sSnlR+TbhIGHJ5s04zn8eZ8Zu23qhQJxbt0XmIzlJirl1OxJltP56CqVw6lZPnQ50ZjzPjO3NxqOiQypvtcS1/Iz5R+V61wgC+C0WD58E+I3hOJAXMg32bcDyYuoSIjgdTGNp+I05QyUpdQpA6VMbjypttgTwuUN4nqJAnrJAnhQLUSbw41TOV2YzwNF6Gxt+Il+Gc9aCSrw3Y0riS7X7N7Sk92htX8rWzWiqH2W7EVtYpwMzXG7/tD96oyHo57NHelJ2vLeSqV3Q4Cb9R0WEGvdkGpuyGXkrm3rg3Zedr+7u098h2t7wzF8crMax38XxtrpfaRLZ78QWXx07kEh0ql8g17u2wOFqJgmglynqJy9fBwFK1zfYcwZ0P83WQsCitqLPZhgbGj4Gi1tkeKNsTDXdP26NvPF4WSQFKfArre6Ae7R06ZHv+sUQFGCh6tGavHELnH7k//3C2Yz06uSps5x9L2XbC//v//G8OC13fiWV7mLHSwKkgDbw/+qhOJWxHH0sOYUix/dFH9qgQ1B+4L7MelX4EdloVC0alUyw7ydOdZUgMDhXFqPRF2aOiSH/gglEpyITVn2V8Swp9TacOXNrofjwl5pg6MA/AVGvY6nleN0SXGToN0B8i9K3J76brNVqvmG7oH9O1zk3TZZq33XKYmybEtFymaRMJaW5abGRCnpu+IlPqls7NxtC0CXqhb+Memi4Q6z6MYWo6BoR17MNIc9OEsI40Ft/hnnfwpoGlxjkPKObRxpzSXNbRRFGzI5AIpG69ZrW1/IrDmMfPY8wOTC1188Yx5p9nwCMmBr7gP0IkQoQskqgrlPNMJ4FMyzhnjv/RO/j4ycRe3j8j+pCHQjwUyF0qSO5SsRWH59WdoZizjTnTXNgMxZy7sqBpbvqKeSlbqJHmpgVoHAyFkfsw9tVdR+AtVY4cPz8VGPKAWgF3ZUHmdVIC0nYFiblAMZcuz4NjWpAkkC7mOm+7AsVcZjF/mC6Qr/swzpMgQWFMARhxEhTGhJTrBJXrJIhpKIzdNE5Z56bPTUTkfQCg2yCSBmjf1585a5m1Qfu17ADTcsoYtO/rAyyQaRPGz1nX1LRCpu1kVmzfiC+mWyMNG5/HDEMiBSJSVhvYDo7rbdeg/WJ2gNc3VQb9DXqcm54N2P3e2KCPdqclODxkdZo8wAp5r9t2s+M9KOb9NO7omqCY38ZrnZsmyDQB5YkEMi2AUgkKYz8xV5qDy2pxN+D3mN/RHBCFdBPzfb8hA3DZSKT8bNa4DZOpYYt9tlc5p5/E5fY6wyuYU6Qt1+8PV4am7Zx6vt3B7eevr6bLFqPH4joUjGErhR3D2gyrQ7ggvigTXzxZFMMiTVmYh3k+i/ZYcYVFvIQR6fvr8yELQlgQxIKaL75HnUMWnTpF5ywEYiHrLHohy5yFQix0XRcF8QWkzmjUWee6oE6d3weZIxbtieBKplJYzlTq1ClzdRKkTjLqLDxn0dfOeUQIUifJui8mZfbJAqqdZNSZdc6iIBGB1EllOVO5V+ecRXv6F2XL8TtZjljwujq5r53ziDAhPfU8gzqfyQ7ZGhV/fz0yJAAJk60waW4Y0hobrdUwd0JB/AtpjctylAXp0wJpTcJyPRYCukL7mfJKRGS9T0tXCdlhAQlO7GBY5iyQPt1+brwUEaPONO/TglRCgdQp6306BYBFelHnrzGNZORpvfxzUtJDT8VJ5S3kMnddQsR8gmvaKSeaOi6Nm/rDrCC6SEadZV61UqfONFdnUqQrpDI2/aSsw4SqA7s7C92U+n76NNzUqdNpodrf2XqBruYXv36ONLQ7s1T7m1lvfqvmx76+Lhra1UW97cA9Xwjki9XaWW+bdS5zFgqxuAQXJNKcRVme3yq0A6/rO/B634HPIxJne5yn6clo+KBstuux5DkLQnzRduDh/EXdkDCizrYDD2WrWeY5Elf3OPW+A3dYQOq0O/Dpfq/eduDTubNCO/Da7cAddRJSOwmqnXYH7tSL2w5c5iyAubN2O3BxWMjy3rfaHfhCBafxgeSDhSIsFPKFLnezfgeeHRaQOu0OXOcVnJHayZA67Q7cydR+B+70EbMDd6ec2u2sv5kq3+F3L9H5/cqKnDh+H+sMwcWA6fsE7R1sb6E4wCHNwYSABaGxvkB7W8QCjRgAGrFb4PcF2SFYAM5REc7IAgmJIBHgDUIiSIjqyHiDROecGVkgIxJlQcBIBBmJoARASIIsUIYL/HnY9w6OGwf6uTdmaLjPV5mzKAA4Ic5ISAomxHMJKUhpPdrcV9y5Zb5V3GlW8a3iejQMZ9LvCDMEK8D5VnF1DiaA87ji/rTXd3DcqJb0+ans0LACbo7lhUW6bhYhc/FPupyx71fL8QJH6NB0R5/ekD0F9ecNvKFlmll+oOVEc9wiRYe1XrZ132t/z8SG6IIwoQCh6cnkV4PHO7yN8ZpY8ty2IKskRTxIBbHNkE8YiiUTxKStkjdVcWxDkZeXVf6awAmhIgJRUQhdECYJCmaaBvOub3P0u+tbHSJQFidAsXp1sUU0UKv06mOLtsd5+dnPvaN3B6bPrSk0Mw25JI5d8nmV44a2jU++W8Whach/ptbrtnczx7ZCtiGXEKQSglZJMot7GqCPn73VlPNnuh2aBkq9QqVeoVLf7g47n9IPcQJZhULOZaLrIEO07PsICfzzq8GRcYHcgbQENS3hLYx3hbS3KOpG+7+cKkQUibnpHwt6SlDSpHHSvFSdbg8k2TEN1eH0mjT1vFh172Tx7RrKummueW75dco4LUceWOaUw5aPG1B/Lmhrd6uOmOT4nRhru1t1jD1vdxiukK4VlvO2gSHn6+RQdct6XnM1pEGNBoceKxPs9wcHY8rSKJ+3EgwptxtXypblvENlSEMM5eQsz2LFoazGy9WhrE9lzCir8Vx1KBtsvEVPB9jvZSjfS/PHK2y3shRKzgqv03iVLdfvEft4hcU4OjorNNhY5kHhsC59c3XGG+U0NL1nq5OBTKbGOHLurgDV84njmMYoA99My1h2b6xloOiXALLJlLuc0wTrZRXreiHg++0uQwI6JPA0WsYF8Y1vy5FcnFTlsu4HMUKOeU75xD78IEOj+XwgOCQrQMMRoOG0H/C9Vu80NO0nvwBNRASjIcOse9LQgSTeaOi0/crQ9EIAFVBbWa9X7fd+r70sDU3f+tMLjQRU7/aDv6UAJiPn4Mg5meqdndxLBA0jaTQTvVGmdc0lGQTwza7RcnQ6SMI6SNLHbD02rZCOkg4nz30uf8cet1VEEY80IP72c8K1cJf1fLXYOA13u+TT97O9bXQhUaxpr2y0Gzs/lS46NJCNhjW90ygODSP+khwagnlDAG8oQEOB2dOavjXjh+Z6bKoO5bLaquzdomueM3ImmtOIYTUD7S2kSzRiWG0/7eLPo/2wR4OgAMblWt4u/fTHmO72Ub8eWdN7UJwMtNh5x2y3fR4BVEf67beNawHU9bIYy3oGRkzOsawXAnvC5Hnj7cxoQsMeAyXHG/YYiJzkJoJ0ZI92yPGcxXoBtMdAwWko5hjIH51zf7RTHcqyutXP/TGQR1mxYOt6CSVA+oRJn4BKzsBgYs5fVgJoz1+8APLy5jV3ZzXZo0zAKVfuzmo0O5SXN7q5O6jxOsTsDOjncdUr/Hhc9fmNCU8XuHwK1GO9Fsh6Gyx/zVaIHK7m7jAoeToCmg+X9SGGC0a5rD4o6LHftq1fxvU3yfvVlnWL4XvwqO1ZyCuYieK2V8U8N02daZmDBeEhFw/ZUvheOjI0rdb0N1eGphUyXTrWZW66XKZ1i5XnDqEuMN+uMjJ9TRAUtb30MDTdBYYMj88FL0PTZSuVfn4XNiRCiEKoC/o3EYemBTJtgh64zCNz9WSKdRMtc/VdrfMN/STSSSTXKZgDoCdu2Uhboe/z1KHpLuhh7msmyHQXxpjnpgXJAu5yVx3TZxjDPkyE8x70oekuMKxz01DMJQAOkVlRfaKhyAiNS98T3GdjmvMQJGVEIfcVoGBLQcpCQhIsjSNDY9M7mjcKx4+/ZkQIUF+CqmoSxLQgkUldOiaam1aItQ266lx9aT0du1siPyW4Nx1H4C2VkjiM250BL/Kg1bJgwAve666UXDEtyzWku1LyOcY9TSvEuqzKyYDXfN3PtbNiZsCLpvvUnbOOUBj7KXg29BnwaxifaCgyt5nZAReEdUHE10/BVOZgAuTUJtWVmNtJNdTKc9Mvk+qvCXx9y9Hd5eg1RwPeF5m3XON8kXb6DLXM/QdMnweaVvuuAS+alrFEnqbXp88DrUCmsyKC6qdPmldVhnJGujDWeS9o0+eKQgTJMDOqLuhakNIn0wx72u53EfOcuWbV4wfsMTo15zarOs4uSA3uZ1VHffNZlYamn9sCvmMvXwfe9LDMMx5Qv+tHVaeYAaPqge5iTnM9mVF1IcFSAWaL9Jq7uR0glrf31vOW4vdhbL7eBHyHHr+mjucBfm4BH9ndK/tnps3tN/SvUCqhbOG8geGLjjRG71pK3wsNcjvEHNGQ73f4hsszb0XGcPNFHIAPt+XYeUIG0J3wrqIYZL68E52rbCUlmi+v0ZAsc8blglLguSeK9UQuc8JlEo+nM060Stgof1+XHS6vcT5/UDNa3jlRHwHRMl2efWO3D/QL4eum+KXoXehcy1Y46JwzXZzP+0xGnjDLk+8j2OHyqFvePB7XbfVLuXehl8Rplic2R948YapQyvPlCRK9Vix0y6I6X55cyzvKljjLM6VFnEAPqsXb8hRZHlRaog7F+bY8XV9eMctL8+V1paXKfHllEr3juGtgOtVcv6dhQ1+Uyxf7zJXrXJ4U3hf45jZTsnSuZApAol5fLyj7CJVF4jTUFIbLe+FslifcLY94AC10XEo3L0REQEMlMvV7LovrawtrriDIFTQM34OxvDN+84SMG+pzeTJJ6ofq7U1e+fh6/Uz1l2ll3nZ4mfvCFLjk+GK9wJGOVB9f5PYFa9iXZ/vem9+gYmjQC2OkWZ+k+fBEBSjg16cvStwTKleacy5IfyJbicI0fGzqW/reUzBaH3dVK9N0fQxNTxyQBmVIu+szxaXSNHxMwOzLs9rydAbNhhEZc/YqEcty/2VkemJoY8YCRU+GA+1jeboevUlxeVJoJUCOGu44Q5Guw9CsZVboxtrMWjqvtIxUIi5QrKFKZDh7jUTCclOVyTbuQVjChPDDGTIdtmTM2duECy3vc+zNZyHLfGYQaCQSQsQptFxnRZYzVZBCJIK0EYG2cbJeiESXzxhkVojqALwvL26hkP68Ij30BjToCFSJRIfnZQ9vlPVULUiqFihVy8wZMuYsuUyXl8JyU03ISJSgkSiN69YbZxqdSkYZL+9etPLA6tI+NUGVKEGVKK2PRMkea88rUUI2ZwmqRAmqREmGm4zH8nQ59xJyoJQUaXyGxe3c4OkJRc5b0vqQc0LP19CHKyuQLqH5xtAVnmVouw7TrSr9zZnOUVkDrxx0GvTCmUjHeX6O2y7wdM8B+rs+narSwCtpZ9ALVaXjPB/fuHtY5kVvfb5h80zLF6dBL5zCd5x/hu9fk/Xp+voUCZ9C61Nofat7J7aPk7r57Y3xeKx4c8b6AzNjeqG2dJzneyfuH4HNCccARM88AnO3hmwfgS0sr3uu5Sxvde/Et0dgeR7qOJtYjleV3k2HvIP3qmxH9aczCHIGrTtjvRLdHpg5sRYo1oIUWvvAjNN8ebYQlfnydHn4bmDSHI+P/M77iHlgthK9QSH6uRJrwFlDPD77xjNfmKqVnLQuY188V1cmwXt6DthndZzlVg7TBErz6aJ7DDefLvpna04FQJ6tsX22tqAKCsvThX0ENn3Gz7dHa47okedlbJ+XrSyPHnuWStf7ChwGNxXmLZR4vmI5xNMTP4O3d07rFvR8y5Iub9/g5m3PXR88NX297FniFhJVh0kZM3mBc4DW2d6tXSJjbnpbItOWyls4M3IMx5baPue5xF0wBQjmmXan1NJSBRNBwqKasKWaK5KW4IrBC7BUe9nPGhxRpL08ZyFM9pKbNTIF8Iy9CGaJe8SWet1+slek4y7r886PIX4a1r20D+Fh7/hxWvXsZSVL5ClAnjTVPR0//k99uU53uL14o0jQOXfTDB7W3+CKLfX0jCTalHJvfW+S7/DvhQU06Xr2gool/bbyvgYXKEiMJRO/JlO5fqgc4h9jeH5jj4+7s/U78gzRdKF524dmnqPPdTKnrabv3RZDtF62ZavluzkZoguCZmiVTBC6rXLfjabvrDZEX6vkuqVUdI4uCFoCEp2rUS+tUiDeUhCfpHF0PlcTjNA7k3r+JHlomxDeCYpl0mV/k3lrdEmxqSxHh8xro75tMm+C+qsk83Kn70Ey72suoWOA0AShoVVGHaI/u7kRWnYmXMJPPxkaHzvl06ne0ZE3KWlOm6ai4jvaOlBzLHPa82of72jzHaQqu0t4xluQUBKUaEBroIC0BjJvEq7ZhtKytYYlJtcbRschqH6PKkdoCQgTIYSJaSQL0RFola2RWNv1OtILqRXNYn7PkjTp99y0tj7Sga9aH/dBPHH9ecOtNnX36PbD9ty+NPEK7r4Qn0M+flA7JN19Elk1yvcw+2s60A3dXmose9RjbqY/J1Q30+aEilIMxjT9ge6s2+UUZSPN3xl5/1vnnLkPmRe8PZHcFbUXqvh1yRh++6zMGCiYXcXgBYJHbJFXh1qEY0uN2FJjW+ohxO/1YUM4BQyOLZWwpVJbatp26UYH3pa673kqsYF/jh17eHvlfUt130jNhc6YBpggP/LEMT8p/Qr/fE0nfHfgY+OYGxlTjGCOEcwxIhB3KRhcx4p5gScsORK21CQYHKsDaRrVox+9wo+rcEKSnw4zMC62C/hul7ZRWaEuWC8Q2wt8P4rtBSvwiC01Ytxb69gn4szfnxqN4YpZL5B1CpB1IsiRTi/Id3h7oCpFleaCJMwxVCC46QV+2RCnFxw7v1f43peUCs9qu0wbxxt80gri0+nd18Q5xWmPFNs5VnJDMH3JNDeObe4Avu/OMx0PbqfkoU4jtnUswd9TL17kozn4MSf4ZSdf83d/NIafay2J9g1S8azLZX3fNebvY+gxXDF4gchcyfQOj3c4mS1YoJ/vqI6NE0T9yqa8K5Loe9fTGK5QlK70WCMjEw18bia5wcVu3LjOHSMEUZepYo4PI75zOT7AovG7mx1bxwR25VLNdNxt73BPAbKeBPJMaqkn2/53HLUnTDKpAPDS5rCV1CttDlu0LsBSS5vDFq1jS41IVEsbrMperlP+HpSdyRTrHX4tlctWAudZNln4GnedhikN4DFufFw5NEum0oa8NccQ5keaF9Rwh1+OobIdp+pzPzb4kn6vxqS7a5LTVItpTK9RSgP4x+2xOm5nLPWYMDgmMFbMOpZ6QpBkWh/rysb35wX7PyM3eLTHMoFO20Nwm5UDR3LAYiwXj4YacFUHXKzlMAcLWXBxwNYb2aEhkwUe1wy+gkvYklSPs44sf24mGYBl117yLBfAzymM/Py59+wdvEu61PMcm9pY+W55S+W6pHLMg+5R+TVDm7BwcHTXXhKT9L0JeYxdlx2Zm5APR1PnuyGYQ8lbOb7ARpMlkrne+GQyRXcO8XjrcgaY+9Iei3wBR+uRz1soM9LRLjE5PKIgPMwKSygOuCxXD3Ov0eFochxNhFhGFkhq4+1ZLstVmrpmkbNDo2sWwbMsI9n9jDmv4H1xtFHK4qRL11zUcYhtLm62SBjHJTzA5krXfZ8WHNZCQLnpelG3xM/pyDuYQ6VNqrhMFGGCVEnbYVyNdG2gOiUhCVDHkk5oxDvYnNWXH+fNTJeXwHAD69veOdK2D24W/HkhawA+nkqfn3QZmyZj+vuW7Ni0eSqd4/eq3bFpMaa5OqbFsv6+oT42rdYh7ICLAZO3RB0u8Q1dLPr7S+wBkXYu8CGSaGbagD+mAzmm18NowD9rZMf0ehgN+BPGXB3TuhwZA/5hHRzTNuiFHdM2jKE6pqMNo8a56dhl47k3Hpqm5UQ34CXxRRmlzJtp6Uwnx7QirKEwRhtGTo7pgoiPAiA+CghrsmGMTqITDRXyhu4iw07ukolMkeyY1vUSbM5lVooZFcR9HICKw1CCMY1Mv4EFEB93YcxOWeC+3alDRBGHdGEUz9dIgvE4jC9oCcgaZdgc38A2jMnRtfSRcYqZyJ3Hr5ltQVqpTOJ4zJPv4C0px/pzkemYiCJpIF3UvThCQ04/qzp9pptVfdMEVOxuoIxeV0rQSDQeP99MK1KxE1JW+/FTpkGv/fg5d0i9jZ/zil378XPukNqPn+cXBU/Tx6a0R5s4VqVg0uCNiCxLpN6G1ZScNeqo5ryBy3LFrv1k67SO2g+r58dlh0S6YTWHuekY1vd3tR9WPV/3w+p8O1P7YXXeleptWE2eaV1OsHobVl1fFyALkGG19sMqO2EkKIy0PhKZ78WuBKafVU8e0h72loZW8/5RoC2yVAP/ea7wCo/x+IF8cWxfL1EE3ur57dWxbTK2z82jtHOfHiz2N5rfq8PGTARbpSCrVGyV7YE25fNEc2i7jG2/wNu7UCFtqsWjUswy1QFTmETnQYTM17VKOreyQ9tkfZIc21gsycQyEzm2depvGsCPp+THUwOaElFAVFQgUZnH9b6o2vteS7bZBv4azYfGsZznLuedWsVY5NlmsTqqYiyL2QbzfCA2tI0Fk4dp+WK7XWUivKd81rltCUA2tJfglvwthPAWqFSJABWivWAXwsZ7m3dsDxPz8wPlIZhDPX8YM2SCRV4KUGMTlsYpAIpt74wvRSfZ+h093lgWn/DrrbmhXcXsKqDW9i76mu2y7A9zbc2K7Qb/8J7PPeaOGw55Ey7ZsU3L+jMX4izybhnMQp5tpBo3+JpPCmbb5uT36rShbTNN+5Un99O0xxuapvN8mn7YRqpx7uZjpxqb635iqZuGEh3b3XxcHdtYLOP6mJTtML2ibzMfs4qjEyLI33Y+dkbHjM3HuZ+PXZ8oxtvE8vxq7tg2FksqgL45QLw5AP42E+9KzjMB/jYT75JtWe7x2U68S7b1vg2Y2cZiyQWoJxIg2xKWdxjZTrxLtgnhLZhteZlPUrstM7z91o2Fpd1KesFlAC/HJqA3fRz1vmKPL7vFcp7ADom099Ro0xo8ItSIsDpEyBI5D1WHRK432jhs5bxkY0xEjEfIISIdEXIsa7McvTDqzHtPIgqFpmChKYBHCkKEMbGyEauEORHuxSoOEYI0wk2s13P6IZFOrIkcIpdYqR4ftCwOkfuWaMhCIHcoFhcjbMkOEatUDp47mlJ13yyoR8QoNXpx6ZR6o/2wLOM6+SDdXuhdyl2ByqpgZVVoWHOeRGjmkQcRgUIjsl7fRSAimFjFiPX8LcKQCFRWzcvNK0VEgLIqBel4KUAaSUbb0fFI6sQqTiYkTKzpEuu+Q2SHSCfWm6KelsdN/UlaZnp6EunFGh3jCmVNMmJlzyO9WL3QYGJNZb31JmAGsFdnLaRvg/tE7AeL/KbXLuVi2gdtqVwc44AA20VeL+XvSUSA/mE/7PNG5GFcMXcvC9B+gccv2/bysYVJp8H9ImW/fuMXKXut2UImNLjfyOxXbd72Bw8ihBGh9dBEQjIhCqSRuLxjst9+WQqNQhqJgFhjJ1b2iLRqWbaYXY8UgEgnVo5zIoRVSwLEimzvGdvec7+9dzzSb+9dIgJpxG7vXSKyvnWz1/SthcaIVZ0S32/vxdNIgeoIlfWO2m/v1QkNB0gjHNZLfL+993rNtb2nxFsJt9nyScSIlZys6bf36lRWFswjsrp749sO3ytorBgRI9bkaKTb4btNjwtGpAAeed006fd3rvyb2o2vwbzrHTkdHyVKHfz4YtYAnsJ2fA/bsU6Y9Qt+3FxxfnxpbP26vncvPfF63UqvHyu9w/c5N1bWnx8rDalctiVvVM94Dqlcz/j2eKbE2VnoBZey7dH3/FIwMmXsl58vf73CP34J58v+I+MRE0x7IBwPoasT0vZ7Xc67J0Ounn2aefJpfy4ZHcLXrCtm/YQH1S1o8awXzHqBUpUCZL3BJe1xFXWsY4Xg+vhZLXmTEj3rAmVfg695pkU1bLuCPetYblOBJNbgS0vlAFlnLEz8Uq9ntYMFM4/FqV2HX/ZKxp7jucVJtlDZg2PpJGEapzCAxw9zpzc120vtQAjKbJlU1M/tDSP4PmSG+v3ow5gMJgHBCrC0VM3Hr6zEsa5QEZNp7j3gKWBkClQ3EjaJJUwEDb5mHWurCRuukkKaafA17gWzjtXrn4E5rHqmwYH5et36BV/jLpj1Cw6MzOHn5zeSq6yMzGF5b1Au7ks7jwJ5JmJRbfAlz8QzTIF1y+m8jWk+Ai9rJgrkmQZ/Wv+8PvwOP27oJUmx62SDgXmdC6aB2DSwMrhFTAPUNLA0dGKZTd+gXj9xmI/Kw/jQEL63PL5OvuaT9bLQG3zNhYpZ13Ea7UstA/jxhhwXYmdjS1jFIEwtjKmFsYrBWB9grA8wJgIWSOl8RvV4VU7LbQgbjO3r3LGoMhZVwaLa4GvWCbOO9QHB+oBgqS1YagsWVcEqe4OvzZsB8kzCopqwXE1YrqYW1ZVNR8KimrCoJsX8XjDrBdA7Y5O4hS94hrFJ3MLfdp6xDuH7Uon2qYunZBARWPiaI5GhzcIXRMDY4G7hS9wjUrAtfOGAgM0kvsQ9EiSxKJDELniguIUyH5bZjuJLnlGMe8GsF8g6YVElLLXbyPzabNIAflw/ETLl2VmeNb6UHSSQwkgw61hmE7IdYztgL0UJy2zGNAAN2GwH7CXrk/JOx23s7/DP/eOFZbpTYTuP++eQbCbmNe7TkeAJv45xsmwU1SmRZh5faU2MFQIzj69Yl+me/AnHclWmI8ET/vX7bpj3fVB1wgTN42zn8RURCFbeoXncwju/5+vrb5Sft2CGz4fIgpwX+gzRZNHni9ZDtFg0e0wUYlIQJhwgdMebioOmCfroYO+26XiT1zOtEJEyRMfjG+s9+spP3Wo9L4MbmRbrvyiO/0QQbwshixRIJWcyXCd9I2CC0iARhBYIrUPn/TzbzM87/T5yonrOQ++mDXghLvXaF73L6YE2i0zHlYhzJkCG1WuXs4gu6+6u1y5kzXYkyLYgHoyKeDBCPom9T+IcTZBOiBAmJJDtcbbHzy/5evR3lRJJNqkpzV2ItJAKtZB6ayGeUBhyISvEpCC2JSC8hRAmMkv642HXAJ001XB+uGJoXNdnjXr1hbVlJqhGJKhGJEgoCQp9KpNWMkWn4+LeT/KUa8zk9kvY0GoEh2Oirvo1Xr67MBrAj0eXtZw3JZTrA/I39LXN3zLR91cvQyZ0zvb7wMtFyGFClsn5E8ihccGMC2RcMePaGSfHeLmM7xGt58PIofFijNfgMD+LIdV9t5b0Fs8nnCAuHIZefEN3AS2OW3gS0M+33N7h9dhLpRvvMAAfTNL1QaEhb+k8HhzeirnQaqXGWzj5jr60IrpRLDTP/QZf0i0XRLdySSvxcbFPnBuX0HmxFyLdF3o2LDp+ji2OywUrLEIdE2+Z08LyqIgnPIetxuoEX2RSbJ9MsCokipQ4acoqxwcws2Mckkp7OKhpC9dlVCPjKSABSgTpMBGSzUkgt6QuoNnxeVLMONRWEtZWUpmkZ2/8sxNbN27gCz3rQAPpbOBftwTHuIwb4ptxWe5ZB1ox5n1APZ8DGWrgC+m/o2OAjMf1DD3QBKklEiLFKNMJJ93hp8/D8VXPaofnNyoCUVFsnYpoK2Lhj2VW5u5euab+H6/UuVeme4QHcZrUijc4QesEdgkHetrMowzgx/YmH6cYUyadVsjJ/W6P4GYQKebDAtUhYEuxoxkrFQyJhbHo37YUHvN59MsAfjyQ1CROqWBBijkrts711n+gsfD3Y//pxHqVikB/jPGLltYRQ90ih+919/U7DvMNff12RGre16n8c0RQr/OEHk7tlDzXmDvbMQzALGWv/JVrZztSB0+NOO0lLve8Y7yBTYlTZv45oNz3kee2LGhnOpznmalunL7fQb3gYQDfsfH7SeIfLM1M57wxsWeammmmHssDrESNW+XvtDpmcsFLOn7oUBwmYhYpDhMZ+49m8Fz3XVb2mOjA3W9Mzke+lem4LaA4TBRjUgAm1xl50i0XcUxHqymP9WW60JbOr/YMmcQA6SRiio1GscHxSaSxT2gGX1unQFkcjcA70zQzveYTo9ioDmvFonMKvCQ5eoM4TJpig5eWsUyTYQxfcjcZgUcnkhSgetLgWbbM5DGh9egQYUwIYyImOp5PmrqPnyixo1jCaizperUnhbKYsBpLpsYmLzoFyh2a1807Ew7rvZgxxTb4Ui9mWs8dxmosE+YTYCpgbCpgTLEMKJZ1nDtvpssg8DQzvdSjeKLYn2H9FX4M65SKHWNpZnwplmL17WSaBKj6NHiL5a8ZFWDsFXpS+TXjgilcjMKD0wLlkqwe14Z9N8djJtgUIcDcK1hNFsV8YhJCPCYFynopUNYno1lxopMC5JMUMCZ27nXqT8KmiAZf0kkCanISqGMmTLFJ1ytKUswnijGxivV8gim2wReYaHdYMJ821Z5D+Iq18IUs1u5swWWCKNbCF3JH+7OF4jBBFKvY2YJ2Zwvz3auaw4I1nygWnbLad9QcAKz5pEBM7FHEvLKpOSxYmAssfCk69myBnOhAZwsW/mRCf6A4gB/vQ5WUPQ/KapfS6akFzeBL1Scq4EFM3xGZfBU7LlB7cOGcsVrTHZN4vYcaSnemfb1TmHUr8Xvv5w/85wh8BKetpjM3h9a1/yX82K4aGiF+LxUc2y0Y6waXTcp5EjGybn5lWDaWqnPrBr5knSDuBr7i8ev9wFDiJhQ8MoqRkXGY3uCKeQaLKmFR5RamupXyfZ1kaN3AV5bKZKyH87bYMZmJCN7gk6i+kREomxgTAWNR5YL5/XreF3mjojy3LliuGnjekptN1wt/oRzJVxzPCEF+F8G4Y1EVhfwuWAUWLFcNfMXvCYtqwqKaaGz9DS6QI9OkYL/BBcqmhEU1YbmasFxNSAVuj3+XqpiFLyiyPdLd4WkvHN+r1MfWCbOO5GoHX7KumPXrBxcxbIm1ONaRqHZwP5vaI9JF7jFAmomEWaex9Tc4Ms52cL9wJDvULnFXzDMFIkMBEgFhYSIsTAa+IjESjDuWfNAMfIM/B8M8gMctS67f3/SNuRTMj1iqdjOtv1LGCnA3AvtRYoIUxoJxF8wzmAYY0wBbDcjnRZdfjUx4kCntfCWrkkO9QH2PCxRUwaq7BGAbZB51MR1fsa7dacWbeaxpC6YZwTQja4cb6XW0/jUzXDDaWEQTVgQSVgTa9Ls04yWC9JKwKSxNjyuOY7YBXPf4R69WJ6y9G/hDXZ8rO97hx0c2col9yXhywSQDDe5qJ3F/pYoN7mom8QXJWHg3s9H1S9kde8HbHRtl24mIwX5uvn/Hctnn6n2sjh38uMDgFX58l4di9IjQRSSdD8eHRK4T9s+tAhRuf+FJhToq7FCRRuX7HfYxlTMpSvh8JdrziXREomNcx8bfeGvjXT2PKOSR0lTikj6Tp1LZRKk6REpHRGdE2m0pnyVO5dqwS6GxF7EcROZ50y5i+ciVHSKEEbFiDZUdImJC05M+HvC/YnWnIRwcGp1UQ3TW2PJgL2rp+2LJmLWuZnvDLpUdezGNX3baxTSf+lccImW8xjcinbK5p01D9PFaVvi+azGkHYE8iFgexIDIL9JqZWjYVSJA0W73+rwFcoKNmY2n30gLpL7YZQ2JQxpIgzhJgzfTtmQ7So06LH1vRArmkS4NglPgKQzK2QsRChAR6go8Of4jQNhEUGEggojIeqqTQBlGfYl3MoysWINDRDGPKDIEUDEe8YhgYqWCeISBKsxYFeaAFD+m9TrCWBVmQgoay/pYxAJphGVYR96MYwLkToDsrbIAcceGBh4PDS9ExFRLSnMiJ/Y6jxlRkDDco7xRAKQnmPTM5S3Hd5mdHBAZ7n6eRLA6KQJ5RM0k4nQOwWZbUaQqSAHUUTCPlGEL+7x1PEZrPa97HvLuziQcB5ozCdoSe+nVn0l4w0gCZoDrqG6RSF9Wq0MEKKsJ03Z3IsHJ0bY5YtDvtQdjIooR6bRNXmjK6hlNw65MzhTsGcN9BH2SLsO+cSdiLK9kOwXkRIJCdyIxnYoMdqUpUehPJOYzAIX+RCI5RACxUrifSahDxAysmR0iup6+FO6HDJ6iRocML9huZ58dFrMq/FhixNQXw3I+UhifA3zeVHvHHg/wqHwuSP41400Yb1oe4SnYo4D5psZgF8V6OwpwNBJXpwaDXUzfuD41UOgODlwiBSNShkdz9CITO2WnyXkYtYuH7sPtgzEFKIa3MwOn8tkzg+kpisEuuq4/M/AqHwGqJkzVJJBHdPHxksEu5jlwZkDBnhkok0OkYB4pSC/gsO4Rc2bAW6lJ5kQ4QERWh1uDXQwNQ2Ll1Y2bwa4SgcTKgFhZIY305wvBC01ZH+W4YB4pb72AW6eWNt627/genVoCeWix6PPsYoimDp0ctHZMsoM2PxFiqY5t6lYZPTRBaBny/vzE4oY+VaU17CLUn2voxsY7p5ySHaIL4kLunMK1Qx9PVHq0dUpi/Y50Q+MEURFEKfbnYVzPW52GaLVodWwLlA8CKVxkyPtzXeE7ei8+Sj9fRxxb7mRyXgoyQqdujeqgpSDZkDqPiOO/JIhKUp8MwUF3vMNUJe3bmNd4OQTSUCCfWwcH6E335anOsp3NbXy++NpXKBcXCCQN39pC5+rPF7jf0XtRk2PSDfNl9n1hXtT41nNcNJAJ3HUR3+G2i3A9fwQ2RANdhG9dxFtl1xZS9JiU9a7NXVvwV9nX+VsTeaIFYqIQE2iVsprvAjQy7kp8K61yXZAZs/0lX3u4k2KuDvYa5hN9v1fyg/359cMAK8fdpT+demhYmuEz0YdYbYSLdiSO17JfscccGgJ/B52h5WJY8JxFMm6r3LE4CvAr9ijA4biwdu6MdmhPpLVfoAyxqVZOHmkxpNXBGjef7zYNsWXVbjbn3p7dbA6b91BXBysA1qztvKpihI02P8ixawR0nsQN7dpckg577JdesUySN84hO6ZNNsXgYHU9dLGs222/sHks74mldUmQDPPuVoIsVo4vJ/DUrprcd/xLZV0+bNfmYa2EHamx4UuOz7isVtfctQNPD6Yd/GB/zcBGlOQIQnS1EGdbtF3x2KLt1YgE1B5TV1OieS5fD05JdFPOddoNcleHixOQ9Tpcujpcex9HGmM56ZRw6Yp2ZYfEctEuXdGeZ0exhfhyRGof2Q1v9zNRCbRlKRb+82W1V/jxGplKSh16b/0jdNIUYu3QRGN0KnKeyQ2J60V83/EUCQ5xtcSlOsTVEj8fOQ+JqyV+PgUdMilDJm/LLNcy4yZRPI+XzuPqEC+dx2lO5fqmyZpUzAdGFzxunoTuxEkcKjQL/mOdxvh9nW/EqSMuDnFCPG7QO5PiaDy25EzHa0nZIS6Qx6HkjDY5U/CkgiVn1ElVeVIZp9sblWkCPakUyId9ujl1IhbEhxQg4hQQ1VJAiFNA6gQRFHyC0o0IUS1B6UaCEYd6IUHpRn0vzA5xnVbmNIB/jkgkfPcGw2UqtEyFltmlcknOMgvUgAhKZSpIy6c+lR1hXZ/40Zw25hrnxHmayjQyfvyqKqqc7+mOFspQ6nOX+tmJEBNUsxhKfSYkQtylfvWIy5j453qEd/iRQSr158M642XKZJlP4uPUf3PKuKy8LVOx+EBDMysyCbFN/Xw+DRkSn6b+k8psDH4usyDjBxckIyRAPUW61OcyX6b0Q7PjcQnI/koIKrYn/DrNH3LuG3h0OBNSZwWblwWal7vvsofgObvL4uI0cMHyUhSpm9LlZXBasti85OjMeoJN19JlGrNDZTwvvy2zb+BxTjxh03UKyBCU+rx0PJ6g6TpheZloovFdxEM010RORiSCltmnslM3k2DxgVI5yfCw4Y24IENqwlL5gm+7A0t1UjlB51Kp3yg7NSgVqHimLpU1OMS75CSn6qcu8eP0MKg9U3uf3WIdwqNswpRmw1s2L4j4yrLopFLmBa5D3zvyGxMa1qA3r9AsnE/itD5KdGj3JCPbM2Y/JfLtjHk+A+XbGTNHh3h/jJUd4grU2uycMY+N0/FpxMTTfVu+nUm7EQJ21tmeMi8ttEARKutHAhk6k872THpFWhE4JMu3M2lPWv0hc/GY0PpTgOycdz+JA405386kXY9jyYycSefbmTRFh8o0PZ/rnG2sn8QVIg7M2Pl2gl2d5IxYck5PsJ9UunQr5CyzrD+lyfYEe4W4PcHOkW8zdhqhZdMSxSme/Xm3F5/uvDsFRykEpTIRcJKRb+fdXirfzrsdYUHn3fl23u1lxO28WxziAhFXzIeKNKDuTNqdbcyZ9JIPy9IxSb4dR3vdnvozqTDnzAHizAHp9rfjZcfZHBBnQ8fL+Xa8PN+059vxslci+KVp/n/ORNCC",
    "rd_q9e4.sqlite": "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",
    "rd_s7g3.md": "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",
    "rd_t3y8.db": "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",
    "rd_w8a2.json": "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",
    "rd_z2v6.ndjson": "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",
    "ruling_addendum.xml": "eNqtW0tvlEcQvPMrVt8dmH7NQ7JBKDYSFw7YnC0HLwgFrxPbRMm/D/jA1qwYM1ubqyW35+tHdXV1++jlP9dfVn+vb+8+32yOF3mWltV68+Hm6vPm0/Hy/vz107q8fPHk6Pbrl28/ubi8ulpvrr5er67X1zfHy6ebb7+5udx8WF98/8HFH5p/f/bn1cflxZPV6mi9ub/9d3W3/ut48cjL6nb98Xh597RV8WV1+eH+4S++Oz377c3bk2V1d395//XueDl59+r1+fJ814KZbi34oxbenJ29Pz35iQnfmkghjTBRClpIhIXI8B3mBU28eXt2/ur89NdGtIIRrY8bGThUTCAkRRkbWnzrD2tCfUyUtH1IzsY4tdnWRKuZMWEGoXUiQx0tuBoX2VYhKpopI54gTVULUW26jUnKYlSCFUgwz0IERbfOSJI4j9r3Qv8RWGOgB3whwlVs1AJxbbr/KyLgFZmBHkETWRMT1Kxgw7xxIWng0SiVeUgUAHOvhekHCMUtuG9xcEjL1DvC8uE+9VoRijMVXEBzKUyOFqg1MyZJrcEjPBh/uqA/C0MVNAGWqzGuAE+IB5XigSkuVEjdE9Imprl6BndqBJWeosgUUtrfoWLoDaM8irjzOGaMHiEdhHKE56Gf/oA/DQYyFLOLaa3SMn5J3t8XNQ7lXBmrLBrRmiUj00mUKxH11JgKEaDBzZRAi4zxbFRnNuzuUTiy5Bm7iBAVEgi+D9SeambgDqV6KuDet8SgpptA4LPGJJd7hxeNGrIcobMqh7/oj3AOuFwwO4Ias5oABDvXTAznG6scYVIBt0YlitYqBjcpwzPCZsFn8AicwHd6yWyCdaStMFF10COSNspEmudL46LH/MxOwagaFn3hoBhIl3LETZCrGDO2asd2knNVkiA5lHOpigw706zuhtnRnGPCPvySaaoAlEcKl6SOCo81SlrximieWRERM12EoqHYIY0rFqQcbkLgcMjwFbMMTsqB854gjXQqyc27jsTBVyvDAWVSxsRJTYuSsJFR+wtGTUXRjXGnokK0o+jO86boqAaVW938rIUT2hsMW0LNORWfIYkc4+tQTJ0Gr4JSaKEAEF0qhVATWhuKCZPdFcctzZWJCNLYLJV4hHerEy6mAVP47vQ6zVYcOeSjq7VhGzB0BtfSsmEvcaaXKCSnBMPpHXCnRSMl8n6MJnIjfCgRzaeGYUfiUDh3YhcREsHdsQlTaYZq7ANdIJYFbX6SHxopdjCbNuv0qsZsksChUslZS7pBntkxluHEN5tbqGEqs7BwFN4imK0vrBdbZrQ/bcP14vRiD78iUVIsvsITpYL2W2dG4u/GGq9UYpZOGmfKI6f5TdqwCeBM4hIM7OHum2lE2bERJebeRb0eyJNax58TJ4AiQaEEKsX0jsbo2qgLKanCBp4SmBLurI53VOT+CTUdz07emDQ8VEmcxtWGRTI/atrwRmQ6OepQKJtlByiA/upeZrwsAGXoYflA1Eq3s0gchAbMNi3YwwjpdASmagvKbUoKmHiwolEZnlKGW+P5sxnUYrNQxC+N1e1Jh8JtRRNuha5FZgWR4Q5dhsuCPVRUO3T8Rh79wF32Zzy4AApqDW+dMyIo7TIhnedKXpH0RCXKJCNh2UGe6UuTNMs2xnkx3BzvIXJ1ZEGpNWfFsJI7W4sDY2INZcPCblsT6nWN9ClwUcncIjzS7PX1kMRhtZGTrwNdaNqYOSc5Lo6JGUXxQ3akw/n7XMzRRElMNlzmz3Kv7qSAa4wZlw25cbd2HdfgtnLSEAE5/maGlLgKI0xPX60MCU8cep9mpStV6va7O50Rsq115yaMjKo1DmVdhvNWNiq3FHuBk4Of147JcqiR/4cDHk+KF88U66lDeWSP0VHnT+ZGwIGTnyu16Sx4QU5cYkq3OKbWHoHtubJn/fnwzXHG/6Kh7l6y6FDrmZ+1QHJyZfZZPj13bl1x9Hzn/+xePPkP0VbeBw==",
    "run_log_k26b.csv": "eNqNWttuHDcMfc9X7AeMAVK3Ge3b2k7boKkdOE7zGLjp5oI6l06cAP37itLMrkSR67wFiKzl5fDwkJr5++dh/2P/+WG4//L27v7Nw8dP++HH3f33/TDvfwzpP/bz/u83f/335Pfbi7MbjMOL57vbp7tXb17e7m5uBwMmnCGegdmg26IbBhy+fP32ZDY4XFxf/fLs1+ORaYNma9zw8uLscj02iffBGeAG49bCel/+9XTnevrp1WVzsd9615wFO1xd3z4thyCeoadDgMOH/V3yafPl3bvmuBle727+ePWitoP+LPkVtsasd98kF2WLcconk8Vm+PduMbg2IlmKboN261xvxIxG8C3dailoHo6/H9srS+CdGb5+//R18/bD/u0/61HjUwqun19ev75i2cK4wanOVvpnk63ijiN3UrbOD8eCaKTxG0huHY2EiV9H+QyUz3wdLAY6Fp6RcmTt8O3Dx3cPyZm7z+/3650R24Qa3ICnzPSO4yQkMxlhgdxmoEIrBz4QAJPDDQDNsDu/rgOJG4NbgOH1s9vfLm92r6/q7DulWMjPUCc1gVVGX9gAUskcUmq1Kx3hBNwjKRiXFFysGRWcX4olCoHiGAnkB+Qbd81RJ8d0yhYEyZ26oEuZHM/NSj4T9gFq3BlkxTHli2B4fmU28/7dx/v72sxopGgm/xNQIHT+N5cD5T55Y0S0Fk5pi4rimhIPWwg1Bd7AyICdjfZjYuT37xNJzPtvD3fzwxqLCN2tKQzuUFu1xZNMAKli4wbGykEKBbuVYiDeGhWqpOoyPGgQOxj6BfwVaOYo4iUdNUD4GqxUVA1kRipt6H5c6S6eTvuGqytuY7FK7Ga2uB6eMWq0ShVmK1q9SX+kGBDzSQYwaAGWDkEkIHQMV7wbxdot8MG2G0YjnqUc1zCYPYMiLKwtQrEYPbZGm8xtDqUWJxZQslSie6l/J9gYpSoSM7etJPcb9NpxVHM4LiqFlb5SSAi5ZVVU7nkhURDt0kkvj7wrXUh+Ju7DGkMgp46ECVTCpNjpWTKAEJSItEPQnPKmcUMgCzj5nZY94Lgdok6AhY6rYIkQBgIGmKHKrlj0SPxQ3WegE52B0olL04OqeiZWbIXNJ6VVoGPYLVUWlePC7cZQVXTHZ9vReUY6up54sYMW9hytKG9clPduFV+ASvMjSEOjTiaZnXP0j92XICVmfSQx4RsWB4Fo8vigqHOn6KMsGLEyAWWlsCClEbzywUiSwoafaGJ+aWKXa0Qrtm/iFLNCb/03jN1MFhxBg5MmVOjvJlL/jK2UWl0V4KE/GZXXDClPx/qpY1ZnOaMplcctjySFSlcV55rUR6LS/DB2IDe50l0tb48qqMneoe1VEoS0o4CIUjwjny4NMGszzfhJamWzAW1oDnkmZUEW5GCCT9BUAGqdpODON/XJAlGaNeOPiHKxGWzZezao+VVmR9fIq741JU7yXo6YMBgmSrQKPUSNyogfi45fpFvoIuCp3rFVo2gY2duMVSMLFTaX4urYCc2E3SSFi4zgnG+MOsOXJtlwnzh0YR56j9QXGL4cFbEydCPrY0Xju0me0BmplTJL8REjcfNIWWCrzi1LSR7PnQIfw8mhMF87qRKdicpqbLX5LG1xkkBSpYI4J/vl188bERKZTPAL6fXi2Wk8mvUqBE5Pgg6yHc6t0gRH2uccdx/1coqdtBQK1iaMVxJbxolq7aTLv8AEg/Hco4NkYNyl6erYasVZnC/cqbI1Tu4QSQumcEEjazUGhVpZ8TGOnZ6WhlZtwMRwYTvEFUoEUWBYYRKQliYJ3kLnpVv1bh7a6Op7JWoMtjT9UQZgch2arecjDM+m3bzNlGXNuMxix82SpNNHrbSjvIA2VN+mWn57GSkFAHy4FCdolV4iaPNgjwKETrjGPF6yiQFkt/J6D9lsq1UXuDquxiq14nI3Oq4AIcigdu0Qsrqu/T5SCfLdU1DK0GVF1203uwYzUc8/oW27eSz1ZJgOY0ELHFlcGsJbteCVeuikbmBOjFy0OGNjgTzG2Tzu2YZtJUhOuv5KEJH3s4lzbdcdTqtGVsoQtJQbkwd2drnrOv+4qGA+FsDYTdMTRQJd2yO9QlHQzlJrl2qotHSyFIAubuLRxCGj0PrH+tHhsOFLkdld3D7782m1R9ZCNeYNpqurU1OVdn3FwsMbjXY0EMjqPUHoIuqIlIywmfadEF9hWB19bIFrAsdKp2zz40wfUqv1Mc8fxoSdpaNBT9ioybwMywKq2bTLaZr6dVY3ZY76cwaO2gZ7bN+9Zq910wJCYYUvdlNw62bnkSVBKmtxIRyU2vKCqoSgGe1oOqt6jzBAIw3wStRAdS/ruip1aFVd4dthbN196O2qEe00scjtMr9w1ZDwYqsubMSEhbRky+A+MZkGRvz57cN6jfi153tbFs/VcKos8IpJrBWffomphLa8lTXxlIi3XYfIUsMIr5in9nneDCcD53LrU98fxA8DQKSVoC7qba4s9TmbQTS0L2SzJDUirbRFGwRYgLwGkLeEdtTWAEZ70s6fgMC6Bigv2mI5keWW7TW7Bc4JFRUV+RJauB07l8wBsa3VVbKq35U0yzQ0yixul03zT34C0H6AIj8WW/YhxpGtuqPj8lp9XtnJtxt5O+a6kUJ7YPMtq9JRWRsH+raiot+TSJnos5qfl7tBeyju35/RDN2rvszqPn8MEk5+jpA/JpIrAb3Ge+xlXf4OJb8GNpJw1bnyFDTR6MEn5/4JOlFMukIo9P8BWgd/OA==",
    "sensor_inventory.json": "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",
    "sensor_map_k26b.yaml": "eNq1lk9LwzAYh+/7FAEPOwXyvvnTpLepA2FT5lZEvMiYdRt0q6z14Lc3m4ogrJVuP8ihDcmTX5M8SS/EKLuS7C5FlW+rcifqUlT1fJmLeVWtl9tNvq3Fal3V5e6j91tVpT0hZOyzW8+LVNyMJNvgY534aZweXg6N9rhUzDLzXSXE667cPL/Xi1T0WbGTyseSKZUeylP/L9xYw41wq0Zfj52HcEETLH+iiVvgWqkT8E614GXH8OOZJM2mkc53153hbLxui25Vd7xjhVnVCNdWt2U/Ibo3zLDo3mmDix7Ig2b9/jEeNB4VPdIdu4Cje0+giZk+SOIQUIfMHh+Ma8QvyuJFvBXzOu88htambW3lKd9gfAK9R/ZDBNs8TdUqL4rO+Lg/HWwHOeA1FfGefECd9dmtZLYOpG6ka6sskJ4kFrOsEW40eRjc2sScX6l/xyO178uU0pF4iWq+oyfjQTY0oxPCNe3ZGI9cpuyx2fOsHeyvM5BquW0mg+nwCN4e8LoZT1g8Y/EaizdYvMXiHRafYPEeiw9QPGGtJay1hLWWsNYS1lrCWktYawlrLWGtJay1jLWWsdYy1lrGWstYaxlrLWOtZay1jLWWz2rtJz3vmMw=",
    "site_calendar.yml": "eNq1WE1P3DAQvfMrfONQ7cozcbJJbqggFXVbKEQ99IIMayDSktDEIPXf1/bSKll24+w4SFxA8+bN93NoS61yVjyq5kmuWaFazb7I9ZpFR7eyVTf1/X2rdM6OP3HMOT8+0o2s2lKXddXmR4zNmNQ3L/rOWCDHZAZ8hnHBwdian1/HxoSxjZMbea9V41yBc/Uky0qrSlZ3auOq1bLpeePZjKcFj3reVLXaaSM6Nu1d/WzSOlku3a9VbZOsX1VTlQ+Pmp2e/GCNuq1rvZcX0M+7sZmYNxnBm3wA76IAnkM6yOtsULzjvS5i3iF+XsuqUitH22nyXm7k/pw3NtPmjGIEr/gA3hEzjVPPtNlM7pvp/zYT8yYjeJMP4M0KwN687uB1NlGyY6YFdaSNW+D+lIFPnzJEdkV5MsjrbEBMnXJaQJw7mdhP7Wx2UkecfEIArAQYrzhA/s8mmp4coDCHE8QQ+cYGE0+zD6YWBUCO6SC1syGP+Er+eZP6lbR2bycqNSdq422t5Mo4m7NzXbs/PJoHRM4uLs++74RlXdjlnC3LavX7tWz1CHDEu+Cvc3bRqnIMDrq45Zx9qxslXzrIq7Pr4ur8c3F2+h5vnhhA4TU4JOKiEUXyhCy6Lk7m7KdsHuR4eEyMPPHQ7gUufC3ai0yplFnYVAAnj7IBAzFqQMLeGVhErS+IQUJPjWJqmgltAGERvDqQkkuVBZQKObFUCAFziJ4T5Yk5CqEWtBZjHNxiTKgtxgVp/UhqmW2p5fgS9YVyHJ19DpMnyX07kGpqkYFyZ12IkMjjEHBC3XkLXlB23gJTWoMp8+Q+VgIq1Je60bFShM593wSousULYksgZIogobIuaFWizQ9kATnSBM4CaQOE5IOEERkpaKHGtL0k6phFUi9PX8kOCDUjEhK1LALyw8b+twACJQnIeghbejgyY9jSwIMzJr3ULZAugLAlgONTTelftxZOkkEIkUHYksEDSJHYmL4SHjoPIIjhxsGb4/v286AXxMBT0ihCRmyPVw6H00TiOCH5LCHtLKEIWJq+MA4dl7/styEz",
    "stage_margins_published.json": "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",
    "thermal_budget_handbook.md": "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"
}
_LOCK = threading.RLock()
_MEMO: dict[str, Any] = {}
OUT = Path("/app/out")
PROGRAM = OUT / "run_budget.py"
CORE = ["stage_temperatures.csv", "intercept_solutions.json", "link_heat_flows.psv", "stage_loads.csv", "cooler_margins.xml", "run_verdicts.json"]
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_UTC = timezone.utc
HELD = {
    "h_reseed": (5512230987112093221, {"edge_screens": True}),
    "h_spring": (8102445379016652207, {"cal": {"base": 60, "transitions": [(datetime(2027, 3, 28, 1, 0, tzinfo=_UTC), 120)]},
                                       "start": date(2027, 3, 1), "date1904": False, "gap_start": True}),
    "h_memo": (3390871266501148829, {"labels": {"J": ("J-3", "J-2"), "P": ("P-3", "P-2"), "S": ("S-3", "S-2")},
                                     "J2": {("BOLT_CU", "C"): "455.0", ("BOLT_AL", "W"): "1488.5", ("CLAMP_SS", "C"): "88.75", ("BOLT_SS", "W"): "602.0",
                                            ("BOLT_AL", "C"): "301.5", ("EPOXY_G10", "C"): "131.0"},
                                     "P2": {("SC-A", "ST4"): 55250, ("SC-B", "ST50"): 2210000, ("SC-C", "ST4"): 70500, ("SC-D", "ST50"): 1715000},
                                     "S2": {"indium_factor": "1.65", "low_torque_factor": "0.55", "h_increment_mW_per_K": "0.5",
                                            "lot_scale_materials": "CU_ETP AL6061 BRASS360"},
                                     "AWG": {32: "0.0324", 36: "0.0126"}, "L1": {"ST50": 60500, "ST4": 4420}, "oom_run": True}),
    "h_profile": (6643019852274410931, {"sheets": {"k": "K_TABLES_R5", "k_old": "K_TABLES_R3", "k_draft": "K_TABLES_R6_DRAFT", "cal": "CAL_K27A",
                                                   "cal_old": "CAL_K26B", "cap": "CAPMAP_V3", "cap_old": "CAPMAP_V2"},
                                        "knobs": {"spike_mK": 25, "outlier_mK": 90, "min_readings": 18}, "reserve": {"ST50": 22, "ST4": 12},
                                        "profile_revision": 8, "overlay_base": 7}),
    "h_intercepts": (2290017465538810443, {"intercepts": "heavy", "floor_ix": True}),
    "h_dense": (7731960208843577019, {"n_runs": 32, "sensors": {"ST300": 6, "ST50": 13, "ST4": 16}, "relabels": 7, "remaps": 8, "amend_chains": 40,
                                      "stage_moves": 4, "within_shard_ties": 6, "eff_tie": True}),
}
HELD_OUT = list(HELD) + ["m_amend", "m_rulings"]


def _seal(root: Path) -> None:
    for p in root.iterdir():
        p.chmod(0o644)
    root.chmod(0o755)
    root.parent.chmod(0o755)


def _shipped() -> Path:
    with _LOCK:
        if "shipped" not in _MEMO:
            root = Path(tempfile.mkdtemp(prefix="kt-shipped-")) / "data"
            root.mkdir()
            for rel, blob in _SHIPPED_DATA.items():
                (root / rel).write_bytes(zlib.decompress(base64.b64decode(blob)))
            _seal(root)
            _MEMO["shipped"] = root
        return _MEMO["shipped"]


def _fresh(tag: str) -> Path:
    base = Path(tempfile.mkdtemp(prefix=f"kt-{tag}-"))
    base.chmod(0o755)
    return base / "data"


def _clone(dst: Path) -> Path:
    shutil.copytree(_shipped(), dst)
    _seal(dst)
    return dst


def _m_amend(root: Path) -> None:
    """Append SET, REVERSE and REVERSE-of-REVERSE chains on installed links to the amendment journal."""
    rng = random.Random(0xA3E1D)
    S = _state(_shipped())
    path = root / "lk_3am0.ndjson"
    old = _jl(path)
    seq = max(int(e["seq"]) for e in old) + 7
    pool = sorted({(L, d["rev"], e["seq"], e["length"]) for (r, L), d in S["D"].items() if d["status"] == "READY"
                   for k, e in d["el"] if k == "s"})
    picks = rng.sample(pool, 24)
    add = []

    def put(L, rev, field, value, action="SET", status="POSTED", target=None):
        nonlocal seq
        seq += rng.randint(1, 3)
        e = {"seq": seq, "link": L if rng.random() < 0.7 else L.replace("-", " "), "rev": rev, "field": field, "value": value,
             "action": action if rng.random() < 0.8 else action.lower(), "status": status}
        if target is not None:
            e["reverses"] = target
        e["entered"] = "2026-12-02T09:00:00Z"
        add.append(e)
        return seq

    for i, (L, rev, sq, ln) in enumerate(picks):
        f = f"seg{sq}.length_mm"
        v = lambda d: _dec(ln + Fraction(d, 10))
        kind = i % 4
        if kind == 0:
            put(L, rev, f, v(rng.choice([-35, 22, 48])))
        elif kind == 1:
            s1 = put(L, rev, f, v(-18))
            s2 = put(L, rev, f, "", "REVERSE", target=s1)
            put(L, rev, f, "", "REVERSE", target=s2)
        elif kind == 2:
            put(L, rev, f, v(30))
            s2 = put(L, rev, f, v(-40))
            put(L, rev, f, "", "REVERSE", target=s2)
        else:
            s1 = put(L, rev, f, v(25))
            put(L, rev, f, "", "REVERSE", status="PENDING", target=s1)
    rng.shuffle(add)
    path.write_text(path.read_text(encoding="utf-8") + "".join(json.dumps(e) + "\n" for e in add), encoding="utf-8")


def _m_rulings(root: Path) -> None:
    """Rescind and reinstate rulings through the addendum and add maintenance blocks inside plateau windows."""
    rng = random.Random(0x5EED7)
    S = _state(_shipped())
    memo = _memo(root / "governance_memo_k26b.pdf")
    rows = [r for r in memo["R-1"]["rows"] if _runtok(r["run"]) in S["live"]]
    add = ET.parse(root / "ruling_addendum.xml")
    top = add.getroot()
    seq = max(int(e.get("seq")) for e in top.findall("entry"))
    for r in rng.sample(rows, 12):
        seq += rng.randint(1, 4)
        ET.SubElement(top, "entry", {"seq": str(seq), "ref": r["ruling"], "action": "RESCIND" if r["status"] == "IN FORCE" else "REINSTATE",
                                     "status": "ISSUED"})
    for r in rng.sample(rows, 4):
        seq += 1
        ET.SubElement(top, "entry", {"seq": str(seq), "ref": r["ruling"], "action": "RESCIND", "status": "DRAFT"})
    add.write(root / "ruling_addendum.xml", encoding="UTF-8", xml_declaration=True)
    cal = (root / "site_calendar.yml").read_text(encoding="utf-8").split("\n")
    i = cal.index("maintenance:") + 1
    blocks = []
    for rid in rng.sample(S["live"], 8):
        a = S["runs"][rid]["a"] + timedelta(minutes=2 * rng.randint(4, 14))
        b = a + timedelta(minutes=rng.choice([8, 14, 20]))
        sc = rng.choice(["ALL", "ST50", "ST4", "shell", "cold plate"])
        blocks += [f"  - start_utc: '{a.strftime('%Y-%m-%dT%H:%M:%SZ')}'", f"    end_utc: '{b.strftime('%Y-%m-%dT%H:%M:%SZ')}'", f"    scope: {sc}",
                   "    note: unplanned DAQ maintenance"]
    # one stage of one run loses every reading to maintenance (NO_SENSORS); the scope is a node alias
    rid = [r for r in S["live"] if S["VD"][r][0] != "INCOMPLETE"][3]
    a, b = S["runs"][rid]["a"] - timedelta(minutes=1), S["runs"][rid]["b"] + timedelta(minutes=1)
    blocks += [f"  - start_utc: '{a.strftime('%Y-%m-%dT%H:%M:%SZ')}'", f"    end_utc: '{b.strftime('%Y-%m-%dT%H:%M:%SZ')}'", "    scope: PLATE4K",
               "    note: cold plate DAQ card swap"]
    cal[i:i] = blocks
    (root / "site_calendar.yml").write_text("\n".join(cal), encoding="utf-8")
    _reserve_tie(root)


def _reserve_tie(root: Path) -> None:
    """Raise one stage-level harness bundle so that a PASS stage ends with its margin exactly equal to its reserve."""
    S = _state(root)
    reg = ET.parse(root / "intercept_register.xml").getroot()
    node = {(b.get("id"), _runtok(b.get("run"))): S["fnode"](b.get("node")) for b in reg.findall("bundle")}
    path = root / "harness_dissipation.psv"
    text = path.read_text(encoding="utf-8")
    last: dict[str, dict] = {}
    for r in _rows(text, "|"):
        if r["bundle"] not in last or int(r["rev"]) >= int(last[r["bundle"]]["rev"]):
            last[r["bundle"]] = r
    for (rid, st), m in sorted(S["MG"].items()):
        if S["VD"][rid][0] != "PASS" or m["v"] != "PASS" or m["mar"] <= m["res"]:
            continue
        for bid, r in sorted(last.items()):
            if r["void"] != "VOID" and _runtok(r["run"]) == rid and node.get((bid, rid)) == st:
                uw = _q(r["dissipation"]) * (1000 if r["unit"] == "mW" else 1) + m["mar"] - m["res"]
                row = [bid, r["run"], r["node_hint"], _dec(uw), "uW", str(int(r["rev"]) + 1), ""]
                path.write_text(text + "|".join(row) + "\n", encoding="utf-8")
                return
    raise RuntimeError("no stage for the reserve tie")


def _held_out(name: str) -> Path:
    with _LOCK:
        k = "corpus:" + name
        if k not in _MEMO:
            root = _fresh(name)
            if name in HELD:
                seed, cfg = HELD[name]
                _Ggenerate(root, seed, cfg)
            else:
                _clone(root)
                {"m_amend": _m_amend, "m_rulings": _m_rulings}[name](root)
            _seal(root)
            _MEMO[k] = root
        return _MEMO[k]


def _renamed() -> Path:
    with _LOCK:
        if "corpus:renamed" not in _MEMO:
            root = _clone(_fresh("renamed"))
            cp = next(root.glob("ingest_catalog_*.json"))
            cat = json.loads(cp.read_text(encoding="utf-8"))
            for i, sh in enumerate(cat["shards"]):
                if sh["kind"] == "readings" and (root / sh["file"]).exists():
                    stem, ext = sh["file"].rsplit(".", 1)
                    new = f"zq{i:02d}_{stem[::-1]}.{ext}"
                    (root / sh["file"]).rename(root / new)
                    sh["file"] = new
            cp.write_text(json.dumps(cat, indent=1) + "\n", encoding="utf-8")
            _seal(root)
            _MEMO["corpus:renamed"] = root
        return _MEMO["corpus:renamed"]


def _derived(root: Path, flip: str = "") -> dict[str, str]:
    with _LOCK:
        k = f"derive:{root}:{flip}"
        if k not in _MEMO:
            _MEMO[k] = derive(root, flip)
        return _MEMO[k]


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _untrusted(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        return [*_SETPRIV, *command]
    return command


def _staged_program() -> Path | None:
    """Copy the delivered program into a verifier-owned directory and grant read on it for the unprivileged runner."""
    with _LOCK:
        if "staged" not in _MEMO:
            _MEMO["staged"] = None
            if PROGRAM.is_file():
                stage = Path(tempfile.mkdtemp(prefix="kt-prog-"))
                stage.chmod(0o755)
                staged = stage / "run_budget.py"
                shutil.copyfile(PROGRAM, staged)
                staged.chmod(0o755)
                _MEMO["staged"] = staged
        return _MEMO["staged"]


def _run(root: Path, tag: str) -> Path | None:
    with _LOCK:
        k = "run:" + tag
        if k in _MEMO:
            return _MEMO[k]
        _MEMO[k] = None
        prog = _staged_program()
        if prog is None:
            return None
        prog.chmod(0o755)
        work = Path(tempfile.mkdtemp(prefix=f"kt-run-{tag}-"))
        work.chmod(0o777)
        out = work / "out"
        try:
            proc = subprocess.Popen(_untrusted([sys.executable, str(prog), str(root), str(out)]), stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True, cwd=str(work))
            try:
                code = proc.wait(timeout=600)
            except subprocess.TimeoutExpired:
                code = -1
            finally:
                try:
                    os.killpg(proc.pid, 9)
                except OSError:
                    pass
                proc.wait()
            if code == 0 and out.is_dir():
                _MEMO[k] = out
        except (OSError, subprocess.SubprocessError):
            _MEMO[k] = None
        return _MEMO[k]


def _text(out: Path | None, name: str) -> str | None:
    if out is None:
        return None
    try:
        return (out / name).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _xml_norm(text: str) -> Any:
    root = ET.fromstring(text.encode("utf-8"))
    return [root.tag, sorted(root.attrib.items()), [[e.tag, list(e.attrib.items()), (e.text or "").strip()] for e in root]]


def _md_lines(text: str) -> list[Any]:
    out: list[Any] = []
    for x in text.rstrip("\n").split("\n"):
        x = x.rstrip()
        out.append([c.strip() for c in x.strip()[1:-1].split("|")] if x.lstrip().startswith("|") and x.endswith("|") else x)
    return out


def _same(name: str, got: str | None, want: str) -> bool:
    """Exact comparison under the output contract: parsed values for JSON, JSON Lines, delimited, XML and YAML reports, markdown tables by
    stripped cells, text otherwise."""
    if got is None:
        return False
    try:
        if name.endswith(".jsonl"):
            a = [json.loads(x) for x in got.split("\n") if x.strip()]
            b = [json.loads(x) for x in want.split("\n") if x.strip()]
            return a == b and got.endswith("\n") == want.endswith("\n")
        if name.endswith(".json"):
            return json.loads(got) == json.loads(want)
        if name.endswith((".csv", ".tsv", ".psv")):
            sep = {".csv": ",", ".tsv": "\t", ".psv": "|"}[name[-4:]]
            return list(csv.reader(io.StringIO(got), delimiter=sep)) == list(csv.reader(io.StringIO(want), delimiter=sep))
        if name.endswith(".xml"):
            return _xml_norm(got) == _xml_norm(want)
        if name.endswith(".yaml"):
            return _yaml(got) == _yaml(want)
        if name.endswith(".md"):
            return _md_lines(got) == _md_lines(want)
        return [x.rstrip() for x in got.rstrip("\n").split("\n")] == [x.rstrip() for x in want.rstrip("\n").split("\n")]
    except Exception:
        return False


def _exact(name: str) -> bool:
    return _same(name, _text(OUT, name), _derived(_shipped())[name])


def _all_exact(out: Path | None, root: Path, names: list[str]) -> bool:
    if out is None:
        return False
    want = _derived(root)
    return all(_same(n, _text(out, n), want[n]) for n in names)


def _full_core() -> bool:
    """The spine: every core report exact in /app/out and in the rerun on every held-out corpus."""
    with _LOCK:
        if "full_core" not in _MEMO:
            ok = all(_exact(n) for n in CORE)
            if ok:
                for n in HELD_OUT:
                    if not _all_exact(_run(_held_out(n), n), _held_out(n), CORE):
                        ok = False
                        break
            _MEMO["full_core"] = ok
        return _MEMO["full_core"]


def _leaf(*names: str) -> bool:
    return _full_core() and all(_exact(n) for n in names)


def _held_exact(name: str) -> bool:
    if not _full_core():
        return False
    root = _held_out(name)
    return _all_exact(_run(root, name), root, NAMES)


def _matches_flip(flip: str, name: str) -> bool:
    got = _text(OUT, name)
    want = _derived(_shipped())[name]
    alt = _derived(_shipped(), flip)[name]
    return got is not None and not _same(name, alt, want) and _same(name, got, alt)


def _sources() -> str:
    try:
        return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sorted(OUT.glob("*.py")))
    except OSError:
        return ""


def _safe(fn) -> bool:
    try:
        return bool(fn())
    except Exception:
        return False


ALL_FILES = NAMES + ["manifest.json"]
_HEADERS = {"sensor_means.tsv": "run\tserial\tstage\twindow_readings\tspikes_dropped\tused_readings\tmean_mK\tstatus",
            "stage_temperatures.csv": "run,stage,sensors_used,sensors_dropped,temperature_mK,status",
            "link_heat_flows.psv": "run|link|rev|hot_node|cold_node|hot_mK|cold_mK|q_uW|status",
            "link_geometry.csv": "run,link,rev,seq,material,length_mm,area_mm2,lot,lot_scale,g_mm",
            "joint_conductances.tsv": "run\tlink\tpos\tclass\tband\tbolts\ttorque\tindium\th_base_mW_per_K\th_eff_mW_per_K",
            "stage_loads.csv": "run,stage,links_uW,harness_uW,parasitic_uW,total_uW,status", "alias_resolution.csv": "kind,token,resolved",
            "amendment_ledger.csv": "seq,link,rev,field,action,status,in_effect", "authority_audit.csv": "source,item,quoted,in_force,verdict",
            "variance_vs_published.csv": "run,link,published_uW,recomputed_uW,delta_uW,status"}


# =========================================================================== ungated shape checks
@criterion(description="The program, all twenty contract reports and manifest.json exist under /app/out")
def deliverables_present(workspace: Path) -> bool:
    return PROGRAM.is_file() and all((OUT / n).is_file() for n in ALL_FILES)


@criterion(description="The program runs on a fresh copy of the corpus at another path and writes exactly the twenty-one contract files there")
def program_writes_contract_files(workspace: Path) -> bool:
    def chk() -> bool:
        out = _run(_clone(_fresh("copy")), "copy")
        return out is not None and sorted(p.name for p in out.iterdir()) == sorted(ALL_FILES)
    return _safe(chk)


@criterion(description="Every delimited report in /app/out starts with the exact header line of the output contract")
def delimited_headers_exact(workspace: Path) -> bool:
    def chk() -> bool:
        return all((_text(OUT, n) or "").split("\n", 1)[0] == h for n, h in _HEADERS.items())
    return _safe(chk)


@criterion(description="Rerun on the larger held-out campaign, run_verdicts.json lists exactly that campaign's profile runs in run order")
def heldout_run_rows_follow_input(workspace: Path) -> bool:
    def chk() -> bool:
        root = _held_out("h_dense")
        got = json.loads(_text(_run(root, "h_dense"), "run_verdicts.json") or "null")
        want = [r["run"] for r in json.loads(_derived(root)["run_verdicts.json"])["runs"]]
        return [r["run"] for r in got["runs"]] == want
    return _safe(chk)


@criterion(description="manifest.json lists every other report in contract order with its true size and SHA-256 digest")
def manifest_consistent(workspace: Path) -> bool:
    def chk() -> bool:
        files = json.loads(_text(OUT, "manifest.json") or "{}")["files"]
        if [f["name"] for f in files] != NAMES:
            return False
        for f in files:
            blob = (OUT / f["name"]).read_bytes()
            if f["bytes"] != len(blob) or f["sha256"] != hashlib.sha256(blob).hexdigest():
                return False
        return True
    return _safe(chk)


@criterion(description="Every report in /app/out is UTF-8 text with LF line endings and a final newline")
def text_serialization(workspace: Path) -> bool:
    def chk() -> bool:
        for n in ALL_FILES:
            b = (OUT / n).read_bytes()
            b.decode("utf-8")
            if b"\r" in b or not b.endswith(b"\n"):
                return False
        return True
    return _safe(chk)


# =========================================================================== gated on the full core (shipped corpus)
@criterion(description="Sensor means are exact for the shipped corpus, with every core report exact on every corpus")
def sensor_means_exact(workspace: Path) -> bool:
    return _safe(lambda: _leaf("sensor_means.tsv"))


@criterion(description="Junction temperature profiles of every solved link are exact for the shipped corpus, with every core report exact")
def junction_profiles_exact(workspace: Path) -> bool:
    return _safe(lambda: _leaf("junction_profiles.jsonl"))


@criterion(description="Segment geometry and joint conductances are exact for the shipped corpus, with every core report exact")
def geometry_and_joints_exact(workspace: Path) -> bool:
    return _safe(lambda: _leaf("link_geometry.csv", "joint_conductances.tsv"))


@criterion(description="Material, node, link and sensor token resolutions are exact for the shipped corpus, with every core report exact")
def alias_resolution_exact(workspace: Path) -> bool:
    return _safe(lambda: _leaf("alias_resolution.csv"))


@criterion(description="Reading exclusions, dedup counters and per-shard lineage are exact for the shipped corpus, with every core report exact")
def ingest_counters_exact(workspace: Path) -> bool:
    return _safe(lambda: _leaf("reading_exclusions.jsonl", "dedup_report.json", "source_lineage.json"))


@criterion(description="The amendment ledger with its in-effect flags is exact for the shipped corpus, with every core report exact")
def amendment_ledger_exact(workspace: Path) -> bool:
    return _safe(lambda: _leaf("amendment_ledger.csv"))


@criterion(description="The governing sheets, memo tables, constants and per-run settings applied are exact for the shipped corpus, with every core report exact")
def parameters_used_exact(workspace: Path) -> bool:
    return _safe(lambda: _leaf("parameters_used.yaml"))


@criterion(description="The authority audit of every lower-authority quoted value is exact for the shipped corpus, with every core report exact")
def authority_audit_exact(workspace: Path) -> bool:
    return _safe(lambda: _leaf("authority_audit.csv"))


@criterion(description="The comparison with the published budget, the margin reconciliation and the summary are exact for the shipped corpus, with every core report exact")
def published_comparison_exact(workspace: Path) -> bool:
    return _safe(lambda: _leaf("variance_vs_published.csv", "reconciliation.md", "budget_summary.md"))


# =========================================================================== held-out re-execution
@criterion(description="Rerun on a reseeded campaign with other runs, sensors, relabels, intercepts and readings exactly at the spike and outlier limits, every report is exact")
def heldout_reseed_exact(workspace: Path) -> bool:
    return _safe(lambda: _held_exact("h_reseed"))


@criterion(description="Rerun on a spring campaign whose run log puts a plateau start inside the skipped clock hour, with the 1900 workbook date system, every report is exact")
def heldout_spring_exact(workspace: Path) -> bool:
    return _safe(lambda: _held_exact("h_spring"))


@criterion(description="Rerun on a corpus whose memo puts other joint, parasitic, solver, gauge and limit tables in force and whose 4 K stage leaves the capacity map once, every report is exact")
def heldout_memo_exact(workspace: Path) -> bool:
    return _safe(lambda: _held_exact("h_memo"))


@criterion(description="Rerun on a corpus whose profile names other workbook sheets, knobs, reserves and a revision that leaves both overlays stale, every report is exact")
def heldout_profile_exact(workspace: Path) -> bool:
    return _safe(lambda: _held_exact("h_profile"))


@criterion(description="Rerun on an intercept-heavy campaign where most runs carry floating heat-sink nodes and one intercept sits at its floor, every report is exact")
def heldout_intercepts_exact(workspace: Path) -> bool:
    return _safe(lambda: _held_exact("h_intercepts"))


@criterion(description="Rerun on a larger campaign with more runs, sensors, relabel chains, channel remaps, stage moves, amendments, same-shard ties and equal effective dates, every report is exact")
def heldout_dense_exact(workspace: Path) -> bool:
    return _safe(lambda: _held_exact("h_dense"))


@criterion(description="Rerun on the shipped corpus with new amendment chains including reversals of reversals, every report is exact")
def metamorphic_amendments_exact(workspace: Path) -> bool:
    return _safe(lambda: _held_exact("m_amend"))


@criterion(description="Rerun on the shipped corpus with rescinded and reinstated rulings, new maintenance blocks and a margin equal to its reserve, every report is exact")
def metamorphic_rulings_exact(workspace: Path) -> bool:
    return _safe(lambda: _held_exact("m_rulings"))


# =========================================================================== negative checks (True when the cheat or wrong reading is present)
def _echoes_shipped() -> bool:
    root = _held_out("h_reseed")
    want_v = _derived(root)["link_heat_flows.psv"]
    want_s = _derived(_shipped())["link_heat_flows.psv"]
    if _same("link_heat_flows.psv", want_v, want_s):
        return False
    got = _text(_run(root, "h_reseed"), "link_heat_flows.psv")
    return got is not None and _same("link_heat_flows.psv", got, want_s)


@criterion(description="The program ignores its input and replays the shipped link heat flows on a held-out corpus")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # inverted: True only when the held-out rerun reproduces the shipped heat flows although its own differ
    return _safe(_echoes_shipped)


@criterion(description="The program is exact on a copy of the shipped corpus and wrong once only the reading shard file names change")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # inverted: True only when the program is exact on a copy and inexact once only shard file names change
    def chk() -> bool:
        if _echoes_shipped():
            return False
        if not _all_exact(_run(_clone(_fresh("copy")), "copy"), _shipped(), NAMES):
            return False
        return not _all_exact(_run(_renamed(), "renamed"), _renamed(), NAMES)
    return _safe(chk)


@criterion(description="Two runs of the program on copies of the same corpus write different report bytes")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # inverted: True only when two runs on identical copies write different report bytes
    def chk() -> bool:
        a = _run(_clone(_fresh("copy")), "copy")
        b = _run(_clone(_fresh("copy2")), "copy2")
        if a is None or b is None:
            return False
        return any(_text(a, n) != _text(b, n) for n in ALL_FILES if n != "manifest.json")
    return _safe(chk)


@criterion(description="sensor_means.tsv equals the means obtained by keeping the reading at exactly PLATEAU_END inside the plateau window")
def negative_closed_plateau_window(workspace: Path) -> bool:
    # inverted: True only when the delivered sensor means reproduce the closed-window reading of H3.3
    return _safe(lambda: _matches_flip("closed_window", "sensor_means.tsv"))


@criterion(description="The delivered source imports a module that is not part of the Python standard library")
def negative_third_party_import(workspace: Path) -> bool:
    def chk() -> bool:
        # inverted: True only when an absolute import names a top-level module outside sys.stdlib_module_names
        for p in sorted(OUT.glob("*.py")):
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    mods = [node.module]
                for m in mods:
                    top = m.split(".")[0]
                    if top not in sys.stdlib_module_names:
                        return True
        return False
    return _safe(chk)


@criterion(description="link_heat_flows.psv repeats the faulty published heat flow for at least half of the links")
def negative_echoes_published(workspace: Path) -> bool:
    # inverted: True only when at least half of the delivered heat flows equal the published ones
    def chk() -> bool:
        root = _shipped()
        pub = {(_runtok(r["run"]), _lktok(r["link"])): _rhe(_q(r["q_mW"]) * 1000) for r in _rows((root / "heatload_budget_published.csv").read_text(encoding="utf-8"), ",")}
        got = _rows(_text(OUT, "link_heat_flows.psv") or "", "|")
        hit = sum(1 for r in got if r.get("q_uW") and pub.get((r["run"], r["link"])) == int(r["q_uW"]))
        return bool(got) and hit * 2 >= len(got)
    return _safe(chk)


@criterion(description="stage_temperatures.csv equals the stage temperatures obtained by rounding half up instead of half to even")
def negative_half_up_rounding(workspace: Path) -> bool:
    # inverted: True only when the delivered file equals the half-up result and that result differs from the contract
    return _safe(lambda: _matches_flip("half_up", "stage_temperatures.csv"))


@criterion(description="sensor_means.tsv equals the means obtained by interpolating NTC sensors linearly in resistance")
def negative_ntc_resistance_space(workspace: Path) -> bool:
    # inverted: True only when the delivered file equals the resistance-space result and that result differs from the contract
    return _safe(lambda: _matches_flip("ntc_r", "sensor_means.tsv"))


@criterion(description="sensor_means.tsv equals the means obtained by following only one sensor_relabel hop")
def negative_one_hop_relabel(workspace: Path) -> bool:
    # inverted: True only when the delivered file equals the one-hop result and that result differs from the contract
    return _safe(lambda: _matches_flip("one_hop", "sensor_means.tsv"))


@criterion(description="dedup_report.json equals the counters obtained by removing every key that has any void copy before choosing the winner")
def negative_void_before_dedup(workspace: Path) -> bool:
    # inverted: True only when the delivered counters equal the void-first result and that result differs from the contract
    return _safe(lambda: _matches_flip("void_first", "dedup_report.json"))


@criterion(description="intercept_solutions.json equals the intercepts held at their nominal_K design temperatures")
def negative_nominal_intercepts(workspace: Path) -> bool:
    # inverted: True only when the delivered intercepts equal the nominal-temperature result and that result differs
    return _safe(lambda: _matches_flip("single_pass", "intercept_solutions.json"))


@criterion(description="link_heat_flows.psv equals the heat flows computed from the WITHDRAWN memo tables")
def negative_withdrawn_tables(workspace: Path) -> bool:
    # inverted: True only when the delivered heat flows equal the WITHDRAWN-table result and that result differs
    return _safe(lambda: _matches_flip("withdrawn", "link_heat_flows.psv"))


criteria.deliverables_present(weight=1)
criteria.program_writes_contract_files(weight=1)
criteria.delimited_headers_exact(weight=1)
criteria.heldout_run_rows_follow_input(weight=1)
criteria.manifest_consistent(weight=1)
criteria.text_serialization(weight=1)
criteria.sensor_means_exact(weight=3)
criteria.junction_profiles_exact(weight=3)
criteria.geometry_and_joints_exact(weight=3)
criteria.alias_resolution_exact(weight=3)
criteria.ingest_counters_exact(weight=3)
criteria.amendment_ledger_exact(weight=3)
criteria.parameters_used_exact(weight=3)
criteria.authority_audit_exact(weight=3)
criteria.published_comparison_exact(weight=3)
criteria.heldout_reseed_exact(weight=5)
criteria.heldout_spring_exact(weight=5)
criteria.heldout_memo_exact(weight=5)
criteria.heldout_profile_exact(weight=5)
criteria.heldout_intercepts_exact(weight=5)
criteria.heldout_dense_exact(weight=5)
criteria.metamorphic_amendments_exact(weight=5)
criteria.metamorphic_rulings_exact(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_closed_plateau_window(weight=-3)
criteria.negative_third_party_import(weight=-3)
criteria.negative_echoes_published(weight=-3)
criteria.negative_half_up_rounding(weight=-3)
criteria.negative_ntc_resistance_space(weight=-3)
criteria.negative_one_hop_relabel(weight=-3)
criteria.negative_void_before_dedup(weight=-3)
criteria.negative_nominal_intercepts(weight=-3)
criteria.negative_withdrawn_tables(weight=-3)
