#!/usr/bin/env python3
"""Verifier for 85ba8b43-fa7c-524d-8211-e73c430afb36 (Channel A).

Self-contained: regenerates the sample/challenge/eval corpus from seeds,
recomputes the corrected season-settlement ground truth, and grades /app/out
byte-for-byte. Python standard library only.

The task is a FAULTY-COMPUTATION-CORRECTION task, not a recovery task: a prior
"season settlement" pipeline produced arena-ladder payout figures that did not
tie out, and the settlement was rejected. The corrected settlement must be
recomputed from the inputs. Difficulty comes from nine interacting stages
S1..S9 whose correct reading differs from the obvious one, with three
load-bearing constants that live ONLY inside a real xlsx workbook, a real PDF,
and a real DOCX.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import re
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import zipfile
import zlib
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from decimal import Decimal, getcontext, ROUND_HALF_EVEN
from pathlib import Path

from rewardkit import criteria, criterion

getcontext().prec = 50

# ---------------------------------------------------------------------------
# Domain constants  (Games: a competitive arena ladder quarterly settlement)
# ---------------------------------------------------------------------------
TIERS = ["BRONZE", "SILVER", "GOLD"]                 # competitive tier band
SERVERS = ["NA", "EU", "APAC"]                        # queue server region
STRATA = [f"{t}-{s}" for t in TIERS for s in SERVERS]  # 9 strata

ACCOUNTS_PER_STRATUM = 26                             # 234 accounts
LANES = ["DUEL", "SIEGE", "RIFT"]                     # scoring channel

CURRENCY_EXPONENTS = {          # documented in unit_scale_exponents.json
    "CRD": 0,                   # credits: already ledger units
    "TKN": 3,                   # token -> ledger is x1000 => exponent 3
    "GLM": 6,                   # gleam -> ledger is x1e6 => exponent 6
    "ORE": 0,                   # raw ore counts; gain supplied by xlsx ONLY
}

XLSX_ONLY_ORE_GAIN = "0.0371"          # ledger units per ore count (xlsx LIVE only)

PDF_INSPECT_UNIT_COST = 1613           # manual-review cost per flagged match
PDF_BETA = "2.5"                       # F-beta beta
PDF_Z = "1.959964"                     # 95% CI z

DOCX_ONLY_SMURF_LEVY_BPS = 640         # smurf-levy basis points on rewarded pool (DOCX only)
DOCX_ONLY_FLOOR_CREDITS = 500          # per-stratum settlement floor (DOCX only)

CAL_VERSION = "LDRv2026S2-live"        # live workbook tag (selection key)

_STRATA_ORDER = STRATA + ["DEFAULT-ROW"]
CALIB = {
    "BRONZE-NA":   {"a": "0.31", "b": "1.17", "tau": "0.55", "recovery": "0.81"},
    "BRONZE-EU":   {"a": "-0.22", "b": "1.09", "tau": "0.63", "recovery": "0.71"},
    "BRONZE-APAC": {"a": "0.44", "b": "0.92", "tau": "0.52", "recovery": "0.87"},
    "SILVER-NA":   {"a": "-0.19", "b": "1.27", "tau": "0.61", "recovery": "0.66"},
    "SILVER-EU":   {"a": "0.13", "b": "1.11", "tau": "0.68", "recovery": "0.72"},
    "SILVER-APAC": {"a": "0.37", "b": "0.95", "tau": "0.50", "recovery": "0.90"},
    "GOLD-NA":     {"a": "-0.41", "b": "1.33", "tau": "0.59", "recovery": "0.61"},
    "GOLD-EU":     {"a": "0.18", "b": "1.06", "tau": "0.70", "recovery": "0.64"},
    "GOLD-APAC":   {"a": "0.55", "b": "0.86", "tau": "0.54", "recovery": "0.93"},
    "DEFAULT-ROW": {"a": "0.00", "b": "1.00", "tau": "0.50", "recovery": "0.80"},
}
_PKEY = {"a_s": "a", "b_s": "b", "tau_s": "tau", "recovery_s": "recovery"}

WINDOW_DAYS = 40           # ladder maturation window for verdicts (S2)
WEIGHT_CAP = "240"         # reported diagnostic ceiling; inactive for this census
QUANT_DECIMALS = 6

F_MATCHES = "ladder_match_capture_s1.csv"       # raw match attempts (spine)
F_LEDGER = "verdict_amendment_history.tsv"      # leaderboard verdict revisions
F_FRAME = "cohort_draw_register.psv"            # sampling frame (drawn flags)
F_DRIFT = "season_patch_reference.csv"          # daily balance drift reference
F_ACCOUNTS = "account_tier_crosswalk.csv"       # account metadata (tier drift)
F_MANIFEST = "season_profile.json"              # calibration version + constants
F_XLSX = "ladder_tuning_grid.xlsx"              # per-stratum calibration (LIVE/DRAFT)
F_PDF = "payout_cost_policy.pdf"                # review cost + beta + z (PDF only)
F_DOCX = "settlement_levy_addendum.docx"        # smurf levy + floor (DOCX only)
F_SQLITE = "reference_lookups.sqlite"
F_DB = "match_trace_index.db"


# ---------------------------------------------------------------------------
# Decimal helpers
# ---------------------------------------------------------------------------
def D(v) -> Decimal:
    return Decimal(str(v).strip())


def q6(x: Decimal) -> Decimal:
    return D(x).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)


def q8(x: Decimal) -> Decimal:
    return D(x).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)


def qint_even(x: Decimal) -> int:
    return int(D(x).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def logit(p: Decimal) -> Decimal:
    p = D(p)
    return (p / (D(1) - p)).ln()


def sigmoid(z: Decimal) -> Decimal:
    return D(1) / (D(1) + (-D(z)).exp())


def clamp_prob(p: Decimal) -> Decimal:
    lo, hi = D("0.000001"), D("0.999999")
    if p < lo:
        return lo
    if p > hi:
        return hi
    return p


# ---------------------------------------------------------------------------
# Low-level flat writers
# ---------------------------------------------------------------------------
def write_table(path: Path, header, rows, delim=","):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    path.write_bytes(buf.getvalue().encode("utf-8"))


def write_text(path: Path, text: str):
    if not text.endswith("\n"):
        text += "\n"
    path.write_bytes(text.encode("utf-8"))


def write_json(path: Path, obj):
    path.write_bytes((json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8"))


# ---------------------------------------------------------------------------
# Binary writers (stdlib only) - real PDF / XLSX / DOCX / SQLite
# ---------------------------------------------------------------------------
def write_sqlite(path: Path, tables: dict):
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    for tname, (cols, rows) in tables.items():
        coldef = ", ".join(f"{c} TEXT" for c in cols)
        cur.execute(f"CREATE TABLE {tname} ({coldef})")
        ph = ", ".join("?" for _ in cols)
        cur.executemany(f"INSERT INTO {tname} VALUES ({ph})", rows)
    con.commit()
    con.close()


_ZIP_DATE = (2026, 1, 1, 0, 0, 0)   # fixed timestamp -> byte-deterministic zips


def _zip_write(zf: zipfile.ZipFile, name: str, data) -> None:
    if isinstance(data, str):
        data = data.encode("utf-8")
    info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def _xlsx_col(idx: int) -> str:
    s = ""
    n = idx + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _sheet_xml(rows) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    out.append('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
    out.append("<sheetData>")
    for ri, row in enumerate(rows, start=1):
        out.append(f'<row r="{ri}">')
        for ci, val in enumerate(row):
            ref = f"{_xlsx_col(ci)}{ri}"
            sval = "" if val is None else str(val)
            esc = sval.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            out.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{esc}</t></is></c>')
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(path: Path, sheets: dict):
    ctypes = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ctypes.append('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">')
    ctypes.append('<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>')
    ctypes.append('<Default Extension="xml" ContentType="application/xml"/>')
    ctypes.append('<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>')
    for i in range(1, len(sheets) + 1):
        ctypes.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ctypes.append("</Types>")

    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 '</Relationships>')

    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb.append('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">')
    wb.append("<sheets>")
    for i, name in enumerate(sheets, start=1):
        wb.append(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>')
    wb.append("</sheets></workbook>")

    wb_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb_rels.append('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">')
    for i, name in enumerate(sheets, start=1):
        wb_rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
    wb_rels.append("</Relationships>")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        _zip_write(zf, "[Content_Types].xml", "".join(ctypes))
        _zip_write(zf, "_rels/.rels", root_rels)
        _zip_write(zf, "xl/workbook.xml", "".join(wb))
        _zip_write(zf, "xl/_rels/workbook.xml.rels", "".join(wb_rels))
        for i, (name, rows) in enumerate(sheets.items(), start=1):
            _zip_write(zf, f"xl/worksheets/sheet{i}.xml", _sheet_xml(rows))


def write_pdf(path: Path, lines):
    def esc(t):
        return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    pages = [lines[i:i + 52] for i in range(0, len(lines), 52)] or [[""]]
    objects = []
    n_pages = len(pages)
    font_obj = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>")
    for i, page_lines in enumerate(pages):
        content = "BT /F1 9 Tf 40 750 Td 11 TL\n"
        for lnn in page_lines:
            content += f"({esc(lnn)}) Tj T*\n"
        content += "ET"
        cbytes = content.encode("latin-1", "replace")
        page_obj_num = 3 + 2 * i
        content_obj_num = page_obj_num + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
            f"/Contents {content_obj_num} 0 R >>"
        )
        objects.append((cbytes, f"<< /Length {len(cbytes)} >>"))
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        if isinstance(obj, tuple):
            cbytes, hdr = obj
            out.write(f"{i} 0 obj\n{hdr}\nstream\n".encode("latin-1"))
            out.write(cbytes)
            out.write(b"\nendstream\nendobj\n")
        else:
            out.write(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
    xref_pos = out.tell()
    n = len(objects) + 1
    out.write(f"xref\n0 {n}\n".encode("latin-1"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.write(f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1"))
    path.write_bytes(out.getvalue())


def write_docx(path: Path, paragraphs):
    def esc(t):
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    body = []
    for p in paragraphs:
        body.append(
            '<w:p><w:r><w:t xml:space="preserve">' + esc(p) + "</w:t></w:r></w:p>"
        )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>" + "".join(body) + "</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        _zip_write(zf, "[Content_Types].xml", content_types)
        _zip_write(zf, "_rels/.rels", root_rels)
        _zip_write(zf, "word/document.xml", document)


# ---------------------------------------------------------------------------
# Corpus generation
# ---------------------------------------------------------------------------
VERDICTS = ["LADDER_CLEAR", "VOID_SMURF", "SHADOW_HOLD", "PENDING_REMATCH"]
CURRENCIES_BY_TIER = {
    "BRONZE": ["CRD", "TKN"],
    "SILVER": ["TKN", "GLM"],
    "GOLD": ["ORE", "CRD"],   # ORE gain lives ONLY in the xlsx
}


def _accounts(rng):
    accounts = []
    ctr = 2000
    for stratum in STRATA:
        tier, srv = stratum.split("-")
        for _ in range(ACCOUNTS_PER_STRATUM):
            aid = f"AC{ctr}"
            ctr += 1
            cur_tier = tier
            if rng.random() < 0.18:
                cur_tier = rng.choice([t for t in TIERS if t != tier])
            cur_srv = srv
            if rng.random() < 0.08:
                cur_srv = rng.choice([s for s in SERVERS if s != srv])
            accounts.append({
                "account_id": aid,
                "frozen_tier": tier,
                "frozen_server": srv,
                "current_tier": cur_tier,
                "current_server": cur_srv,
                "currency": rng.choice(CURRENCIES_BY_TIER[tier]),
            })
    return accounts


def _drift_book(rng, base_day):
    rows = []
    families = ["CRD", "TKN", "GLM", "ORE"]
    base = {"CRD": D("1.0000"), "TKN": D("1.0007"), "GLM": D("1.0015"),
            "ORE": D("0.9989")}
    for fam in families:
        val = base[fam]
        for dd in range(96):
            day = base_day + timedelta(days=dd)
            if fam != "CRD" and (dd % 16 == 4 or dd % 22 == 8):
                continue
            val = val + (D(rng.randint(-7, 7)) / D(100000))
            rows.append({"unit_family": fam, "ref_date": day.isoformat(),
                         "drift_mult": f"{val:.6f}"})
    rows.sort(key=lambda r: (r["unit_family"], r["ref_date"]))
    return rows


def generate_core(rng, out_dir, base_day, accounts):
    matches = []
    ledger = []
    frame = []
    n_ties = 390
    ac_by_stratum = {}
    for a in accounts:
        ac_by_stratum.setdefault(f"{a['frozen_tier']}-{a['frozen_server']}", []).append(a)

    match_ctr = 6000000
    for mt in range(n_ties):
        stratum = STRATA[mt % len(STRATA)]
        ac = rng.choice(ac_by_stratum[stratum])
        lane = rng.choice(LANES)
        seed_hash = f"SD{rng.randint(100000, 999999)}"
        ladder_split = f"S{rng.randint(1, 9)}"
        hero_handle = ac["frozen_tier"].lower()
        match_key = f"{ac['account_id']}|{hero_handle}|{seed_hash}|{ladder_split}"

        n_attempts = rng.choice([1, 2, 2, 3, 3, 4])
        sealed_any = rng.random() > 0.11
        first_epoch_day = base_day + timedelta(days=rng.randint(0, 74))
        true_loot = D(rng.randint(200, 95000))
        currency = ac["currency"]
        y_true = 1 if rng.random() < 0.35 else 0
        p_raw = D(rng.randint(2, 998)) / D(1000)
        if y_true == 1:
            p_raw = p_raw / D(2) + D("0.4")
        p_raw = min(D("0.999"), max(D("0.001"), p_raw))

        for at in range(n_attempts):
            match_ctr += 1
            epoch_day = first_epoch_day + timedelta(days=at)
            seal_status = "SEALED" if (sealed_any and at >= (0 if n_attempts == 1 else 1)) else "OPEN"
            if at == 0 and n_attempts > 1:
                seal_status = "OPEN"
            loot = true_loot + D(rng.randint(-3, 3))
            matches.append({
                "match_uid": f"MT{match_ctr}",
                "account_id": ac["account_id"],
                "hero_handle": hero_handle,
                "seed_hash": seed_hash,
                "ladder_split": ladder_split,
                "lane": lane,
                "raw_loot": str(loot),
                "loot_currency": currency,
                "checkpoint_no": str(at + 1),
                "seal_status": seal_status,
                "match_epoch": epoch_day.isoformat(),
                "p_raw": f"{p_raw:.6f}",
            })

        if not sealed_any:
            continue

        drawn = "1" if rng.random() < 0.61 else "0"
        frame.append({"match_key": match_key, "stratum_frozen": stratum, "drawn": drawn})

        n_rev = rng.choice([1, 1, 2, 3])
        base_conf = first_epoch_day + timedelta(days=rng.randint(1, 66))
        for dseq in range(1, n_rev + 1):
            eff = base_conf + timedelta(days=(dseq - 1) * rng.randint(3, 28))
            amended = base_day + timedelta(days=rng.randint(0, 95))
            if dseq == n_rev:
                verdict = "LADDER_CLEAR" if y_true == 1 else "VOID_SMURF"
                if rng.random() < 0.07:
                    verdict = "SHADOW_HOLD"
                if (eff - first_epoch_day).days > WINDOW_DAYS and rng.random() < 0.5:
                    verdict = "PENDING_REMATCH"
            else:
                verdict = rng.choice(["PENDING_REMATCH", "SHADOW_HOLD"])
            ledger.append({
                "match_key": match_key,
                "review_seq": str(dseq),
                "verdict": verdict,
                "effective_at": eff.isoformat(),
                "amended_at": amended.isoformat(),
            })

    rng.shuffle(matches)
    ledger.sort(key=lambda r: (r["match_key"], int(r["review_seq"])))
    frame.sort(key=lambda r: r["match_key"])

    write_table(out_dir / F_MATCHES,
                ["match_uid", "account_id", "hero_handle", "seed_hash",
                 "ladder_split", "lane", "raw_loot", "loot_currency",
                 "checkpoint_no", "seal_status", "match_epoch", "p_raw"],
                [[s[k] for k in ["match_uid", "account_id", "hero_handle",
                                 "seed_hash", "ladder_split", "lane",
                                 "raw_loot", "loot_currency", "checkpoint_no",
                                 "seal_status", "match_epoch", "p_raw"]] for s in matches])
    write_table(out_dir / F_LEDGER,
                ["match_key", "review_seq", "verdict", "effective_at", "amended_at"],
                [[r[k] for k in ["match_key", "review_seq", "verdict",
                                 "effective_at", "amended_at"]] for r in ledger],
                delim="\t")
    write_table(out_dir / F_FRAME,
                ["match_key", "stratum_frozen", "drawn"],
                [[r["match_key"], r["stratum_frozen"], r["drawn"]] for r in frame],
                delim="|")
    return matches, ledger, frame


def write_tuning_xlsx(path, rng, ore_gain=XLSX_ONLY_ORE_GAIN, live_first=False):
    live = []
    live.append(["workbook_tag", CAL_VERSION])
    live.append(["Ladder Tuning Grid - LIVE", "", "authoritative"])
    live.append([""])
    live.append(["ore_to_ledger_gain", ore_gain, "GOLD ore->ledger; not in any plaintext"])
    live.append([""])
    header = ["parameter"] + _STRATA_ORDER
    live.append(header)
    for param in ["a_s", "b_s", "tau_s", "recovery_s"]:
        live.append([param] + [CALIB[s][_PKEY[param]] for s in _STRATA_ORDER])
    live.append([""])
    live.append(["cosmetic_gain_audit", "item_id", "nominal_gain", "trim_bps", "note"])
    for i in range(1, 241):
        live.append(["", f"CS{1000 + (i % 57)}", f"{D('1.0') + D(i) / D(10000):.4f}",
                     str(rng.randint(1, 45)), f"row#{i:03d}"])

    draft = [["workbook_tag", "LDRv2026S1-draft"],
             ["Ladder Tuning Grid - DRAFT (SUPERSEDED)", "", "do not use"],
             [""],
             ["ore_to_ledger_gain", "0.0448", "WRONG - superseded"],
             [""],
             ["parameter"] + _STRATA_ORDER]
    for param in ["a_s", "b_s", "tau_s", "recovery_s"]:
        draft.append([param] + [f"{D(CALIB[s][_PKEY[param]]) + D('0.05'):.2f}" for s in _STRATA_ORDER])
    for i in range(1, 241):
        draft.append(["", f"CS{1000 + (i % 57)}", f"{D('1.1') + D(i) / D(10000):.4f}",
                      str(rng.randint(1, 45)), f"draft#{i:03d}"])
    sheets = {"LIVE": live, "DRAFT_v1": draft} if live_first else {"DRAFT_v1": draft, "LIVE": live}
    write_xlsx(path, sheets)


def write_cost_policy_pdf(path, review_cost=PDF_INSPECT_UNIT_COST, beta=PDF_BETA, z=PDF_Z):
    lines = [
        "ARENA LADDER PAYOUT & UNCERTAINTY COST POLICY - 2026 SEASON 2",
        "Competitive Integrity & Settlement Working Group",
        "",
        "1. SCOPE",
        "This memo fixes the payout and uncertainty constants used by the quarterly",
        "weighted arena-ladder settlement. Values here are authoritative and are",
        "deliberately NOT duplicated in any plaintext file in the export set.",
        "",
        "2. MANUAL-REVIEW COST",
        "Each match flagged by the calibrated smurf detector (yhat = 1) incurs a",
        f"manual review. The inspection unit cost is {review_cost} credits per",
        "flagged match. It is charged per flagged match and weighted by the rarity",
        "weight before summation within a stratum.",
        "",
        "3. F-BETA",
        f"The headline stratified quality metric uses F-beta with beta = {beta},",
        "reflecting that a missed genuine clear (recall failure) is valued more than",
        "a false ban (precision failure). Compute F-beta from the OVERALL weighted",
        "precision and recall (ratio of weighted totals), never by averaging",
        "per-stratum F-beta for the overall line.",
        "",
        "4. NET SETTLEMENT",
        "Net settlement per stratum = rewarded_credits - review_cost_credits, before",
        "the smurf levy and settlement floor described in the levy addendum.",
        "Rewarded credits count only true positives (y = 1 and yhat = 1) times the",
        "per-stratum recovery factor; forfeited credits count only false negatives",
        "(y = 1 and yhat = 0).",
        "",
        "5. CONFIDENCE INTERVALS",
        "Report 95% Wilson score intervals on the Kish effective sample size",
        "n_eff = (sum w)^2 / sum(w^2), computed over the relevant weighted",
        "denominator subset (actual positives for recall, predicted positives for",
        f"precision), with z = {z}.",
        "",
        "6. TABLE - PER-LANE REVIEW STAFFING (reference only, not graded)",
        "lane      reviewers   shift_hours   escalation_bps",
    ]
    rng2 = random.Random(717171)
    lanes = ["DUEL", "SIEGE", "RIFT"]
    for i in range(1, 231):
        b = lanes[i % 3]
        lines.append(f"{b:8s}  {rng2.randint(2, 30):4d}      {rng2.randint(6, 12):3d}          {rng2.randint(50, 900):4d}   row#{i:03d}")
    write_pdf(path, lines)


def write_levy_addendum_docx(path, levy_bps=DOCX_ONLY_SMURF_LEVY_BPS,
                              floor=DOCX_ONLY_FLOOR_CREDITS):
    paras = [
        "ARENA LADDER SETTLEMENT LEVY ADDENDUM - 2026 SEASON 2",
        "Competitive Integrity & Settlement Working Group - Addendum C",
        "",
        "A. SCOPE",
        "This addendum fixes the two post-settlement adjustments applied AFTER the net",
        "settlement defined in the payout cost policy. These two constants are",
        "authoritative and appear in NO plaintext file and NOT in the spreadsheet.",
        "",
        "B. SMURF LEVY",
        f"A smurf levy of {levy_bps} basis points is charged on each",
        "stratum's rewarded_credits (not on net). The levy is computed as",
        "round_half_even(rewarded_credits * levy_bps / 10000) and is SUBTRACTED after",
        "the review cost. The levy is reported per stratum and in the season total.",
        "",
        "C. SETTLEMENT FLOOR",
        f"After the review cost and the smurf levy, each stratum's settlement is",
        f"floored at {floor} credits: the reported net_credits is the",
        "greater of the computed value and the floor. The floor is applied per stratum,",
        "last of all, and only to the per-stratum net line and the season total derived",
        "from the floored per-stratum values.",
        "",
        "D. ORDER OF OPERATIONS",
        "rewarded_credits (from policy) -> subtract review_cost -> subtract smurf levy ->",
        "apply settlement floor. The floor is NEVER applied before the levy, and the",
        "levy is NEVER applied before the review cost.",
        "",
        "E. NON-DUPLICATION NOTICE",
        "The levy basis points and the settlement floor are published here only. Any",
        "plaintext or spreadsheet value that resembles a levy or floor is a decoy and",
        "must not be used. The season_profile.json levy_bps_placeholder is intentionally",
        "null.",
        "",
        "F. REFERENCE STAFFING NOTES (not graded)",
    ]
    rng3 = random.Random(535353)
    for i in range(1, 221):
        paras.append(f"desk {i:03d}: shift {rng3.randint(1, 4)} handles {rng3.randint(20, 400)} cases at tier {TIERS[i % 3]}")
    write_docx(path, paras)


def write_reference_dbs(out_dir, drift_rows, accounts, frame, ledger):
    write_sqlite(out_dir / F_SQLITE, {
        "drift_daily": (["unit_family", "ref_date", "drift_mult"],
                        [(r["unit_family"], r["ref_date"], r["drift_mult"]) for r in drift_rows[:400]]),
        "account_dim": (["account_id", "frozen_tier", "current_tier"],
                        [(a["account_id"], a["frozen_tier"], a["current_tier"]) for a in accounts]),
    })
    write_sqlite(out_dir / F_DB, {
        "draw_flags": (["match_key", "stratum_frozen", "drawn"],
                       [(f["match_key"], f["stratum_frozen"], f["drawn"]) for f in frame[:400]]),
        "verdicts": (["match_key", "review_seq", "verdict"],
                     [(l["match_key"], l["review_seq"], l["verdict"]) for l in ledger[:400]]),
    })


def write_docs(out_dir: Path, rng, base_day, accounts, drift_rows):
    W = lambda name, txt: write_text(out_dir / name, txt)
    J = lambda name, obj: write_json(out_dir / name, obj)

    W("readme_first.txt",
      "This directory is the complete export set and written contract for the\n"
      "quarterly arena-ladder season settlement. A prior settlement pipeline\n"
      "produced figures that did not tie out and the settlement was rejected;\n"
      "your job is to recompute the corrected settlement, not to recover a format.\n"
      "Filenames are deliberately generic; read the contents to learn each file's\n"
      "role. Start from the pipeline contract overview and the per-stage\n"
      "specification files. Every rule you need is written down somewhere under\n"
      "this directory. Three load-bearing figures live only inside the spreadsheet,\n"
      "the policy PDF, and the levy addendum DOCX.\n")

    W("00_pipeline_contract_overview.md",
      "# Pipeline Contract Overview\n\n"
      "The settlement runs nine stages S1..S9. They interact: an early choice\n"
      "about which match attempts survive and which epoch anchors them changes the\n"
      "later unit, labeling, weighting, calibration, interval, and payout figures.\n"
      "The obvious reading of several stages is the wrong one; correct the\n"
      "computation.\n\n"
      "- **S1 Match canonicalization** - reduce raw match attempts to one canonical\n"
      "  row per match key; drop match keys that never sealed.\n"
      "- **S2 Anchoring & verdicts** - anchor on the FIRST attempt; resolve the\n"
      "  ladder verdict within the maturation window by review sequence.\n"
      "- **S3 Running ladder baseline** - fold the previous resolved baseline per\n"
      "  frozen stratum in ascending match_key order.\n"
      "- **S4 Reward-unit canonicalization** - convert loot to integer ledger units\n"
      "  with the latest drift reference on or before the anchor; the ore gain lives\n"
      "  ONLY in the spreadsheet.\n"
      "- **S5 Two-level rarity weights** - base rate and nonresponse on DIFFERENT\n"
      "  partitions; inflate before quantization; allocate quantization residue.\n"
      "- **S6 Calibration & decision** - calibrate in log-odds space with the LIVE\n"
      "  sheet parameters; decide with an inclusive per-stratum threshold.\n"
      "- **S7 Weighted metrics** - precision/recall/F-beta as ratios of weighted\n"
      "  totals; macro is a weight-share-weighted mean.\n"
      "- **S8 Uncertainty & payout** - Wilson intervals on Kish effective N;\n"
      "  review cost, beta and z live ONLY in the policy PDF.\n"
      "- **S9 Levy & floor** - apply the smurf levy then the settlement floor; both\n"
      "  constants live ONLY in the levy addendum DOCX.\n\n"
      "Load-bearing constants that appear in NO plaintext file:\n"
      "- the GOLD ore-to-ledger gain (spreadsheet LIVE sheet),\n"
      "- the manual-review unit cost, F-beta beta, and CI z (policy PDF),\n"
      "- the smurf levy basis points and settlement floor (levy addendum DOCX).\n\n"
      "The exact shape of every output artifact (the column headers of each table,\n"
      "the key names of each JSON object, the line layout of each text and XML\n"
      "file, the row order and the per-field precision) is written in\n"
      "output_artifact_schemas.md. Read it before emitting anything.\n")

    W("spec_stage_s1_canonicalization.md",
      "# S1 Match Canonicalization\n\n"
      f"The economic match key is `account_id | hero_handle | seed_hash | ladder_split`\n"
      f"built from `{F_MATCHES}`. The `match_uid` is minted once per attempt and MUST\n"
      "NOT be used as the key. For each key, keep exactly one canonical row: the row\n"
      "with the highest `checkpoint_no` among rows whose `seal_status` is `SEALED`. A\n"
      "key with no `SEALED` attempt never sealed and is dropped from the population\n"
      "entirely (it is not a surviving OPEN row).\n")

    W("spec_stage_s2_anchoring_verdicts.md",
      "# S2 Anchoring and Verdicts\n\n"
      "Anchor each match on its FIRST attempt (minimum `checkpoint_no` across ALL its\n"
      "attempts, sealed or not), and take the anchor date from that first attempt's\n"
      f"`match_epoch`. Do NOT anchor on the canonical row.\n\n"
      f"Resolve the adjudicated verdict from `{F_LEDGER}`. Consider only revisions\n"
      f"whose `effective_at` is within {WINDOW_DAYS} days on or after the anchor date.\n"
      "Order the surviving revisions by `review_seq` and take the last one.\n"
      "`amended_at` is backfilled and MUST NOT be used for ordering. Map the verdict\n"
      "through the crosswalk: `LADDER_CLEAR` -> positive, `VOID_SMURF` -> negative;\n"
      "`SHADOW_HOLD` and `PENDING_REMATCH` (and any match with no in-window revision)\n"
      "are excluded from BOTH numerator and denominator.\n")

    W("spec_stage_s3_running_baseline.md",
      "# S3 Running Ladder Baseline\n\n"
      "Resolved matches are processed left to right within each frozen tier-server\n"
      "stratum in ascending `match_key` order against a single running baseline that\n"
      "starts at the season profile `base_p`. The effective probability is\n"
      "`p_eff = clamp(0.85 * p_raw + 0.15 * previous_baseline)` and the new baseline\n"
      "becomes `p_eff`. No match resolves in isolation. `p_raw` is clamped to\n"
      "[0.000001, 0.999999] before use.\n")

    W("spec_stage_s4_unit_canonicalization.md",
      "# S4 Reward-Unit Canonicalization\n\n"
      "Convert each canonical `raw_loot` to integer ledger units using the scale\n"
      "exponent of its `loot_currency`: CRD=0, TKN=3, GLM=6 (multiply raw by\n"
      "10**exponent). `ORE` (raw ore counts) has NO plaintext exponent; multiply by\n"
      "the ore-to-ledger gain published only on the spreadsheet LIVE sheet. Then\n"
      "multiply by the latest season-patch drift multiplier for the unit family dated\n"
      "on or before the anchor date. The supplied reference book contains an eligible\n"
      "entry for every graded anchor. Round half-to-even to an integer at the\n"
      "ledger-unit stage.\n")

    W("spec_stage_s5_two_level_weights.md",
      "# S5 Two-Level Rarity Weights\n\n"
      "Only matches that are resolved AND drawn (`drawn=1`) carry a weight. The weight\n"
      "is `base_rate * nonresponse`. The base rate is population count over sampled\n"
      "count per FROZEN stratum. The nonresponse factor is sampled count over resolved\n"
      "count per SERVER - a DIFFERENT partition, so the product does not reduce to\n"
      "population over resolved. Apply nonresponse inflation before quantization.\n"
      "Quantize weights to 6 decimals half-to-even and allocate each stratum's\n"
      "rounding residue to the largest\n"
      "weight, ties broken by smallest `match_key`. For this settlement, 240 is a\n"
      "reported diagnostic ceiling only; no trimming operation is part of S5.\n")

    W("spec_stage_s6_calibration_decision.md",
      "# S6 Calibration and Decision\n\n"
      "Calibrate each `p_eff` in log-odds space:\n"
      "`p_cal = sigmoid(a_s + b_s * logit(p_eff))` using the per-stratum `a_s`, `b_s`\n"
      "from the LIVE spreadsheet sheet. The DRAFT sheet and the plaintext legacy\n"
      "multipliers are superseded decoys. Decide with an inclusive comparison against\n"
      "the per-stratum `tau_s`: `yhat = 1 if p_cal >= tau_s`.\n")

    W("spec_stage_s7_weighted_metrics.md",
      "# S7 Weighted Metrics\n\n"
      "Compute weighted precision, recall and F-beta per stratum from weighted TP, FP,\n"
      "FN. The OVERALL precision and recall are ratios of the weighted totals across\n"
      "all weighted matches, and the overall F-beta is computed from those overall\n"
      "figures - never by averaging per-stratum F-beta. The MACRO precision and recall\n"
      "are weight-share-weighted means of the per-stratum figures.\n")

    W("spec_stage_s8_uncertainty_payout.md",
      "# S8 Uncertainty and Payout\n\n"
      "Report 95% Wilson score intervals on the Kish effective sample size\n"
      "`n_eff = (sum w)^2 / sum(w^2)` computed over the correct denominator subset:\n"
      "actual positives for recall, predicted positives for precision. The z value is\n"
      "in the policy PDF only. Rewarded credits count true positives times the\n"
      "per-stratum recovery factor; forfeited credits count false negatives. The\n"
      "review unit cost (PDF only) is charged per flagged match, weighted. The net\n"
      "BEFORE levy and floor = rewarded - review cost. Round half-to-even at each\n"
      "stage.\n")

    W("spec_stage_s9_levy_and_floor.md",
      "# S9 Settlement Levy and Floor\n\n"
      "Two post-settlement adjustments are applied AFTER S8, in this exact order and\n"
      "with these two constants that live ONLY in the levy addendum DOCX:\n"
      "1. Smurf levy: subtract round_half_even(rewarded_credits * levy_bps / 10000)\n"
      "   from the S8 net.\n"
      "2. Settlement floor: the reported per-stratum net_credits is the greater of\n"
      "   the post-levy value and the floor. The floor is applied last of all.\n"
      "The season total net is the sum of the floored per-stratum net values. The\n"
      "levy basis points and the floor are NOT in any plaintext file and NOT in the\n"
      "spreadsheet; read them from the DOCX.\n")

    W("evaluation_policy.yaml",
      "audit_period: 2026S2\n"
      f"maturation_window_days: {WINDOW_DAYS}\n"
      f"weight_cap: {WEIGHT_CAP}\n"
      "threshold_inclusive: true\n"
      "calibration_space: log_odds\n"
      "notes: >\n"
      "  These values restate the spec docs for machine consumption. The review unit\n"
      "  cost, beta and z are intentionally NOT here; they are in the policy PDF only.\n"
      "  The ore-to-ledger gain is on the spreadsheet LIVE sheet only. The smurf levy\n"
      "  and settlement floor are in the levy addendum DOCX only.\n")

    W("rounding_and_precision.yml",
      "quantize_decimals: 6\n"
      "probability_decimals: 8\n"
      "rounding_mode: half_even\n"
      "payout_rounding: half_even_at_each_stage\n"
      "residue_allocation: largest_weight_then_smallest_match_key\n")

    W("sheet_selection_rule.yaml",
      "rule: select the workbook sheet whose cell B1 equals season_profile.calibration_version\n"
      f"live_tag: {CAL_VERSION}\n"
      "draft_sheets_are_decoys: true\n"
      "legacy_plaintext_multipliers_are_decoys: true\n")

    W("drift_fallback_policy.yml",
      "search: latest reference on or before anchor date\n"
      "graded_corpus_invariant: every anchor has an eligible reference\n")

    W("ordering_dependencies.yaml",
      "order:\n"
      "  - s1_canonicalization\n"
      "  - s2_anchoring_verdicts\n"
      "  - s3_running_baseline\n"
      "  - s4_unit_canonicalization\n"
      "  - s5_two_level_weights\n"
      "  - s6_calibration_decision\n"
      "  - s7_weighted_metrics\n"
      "  - s8_uncertainty_payout\n"
      "  - s9_levy_and_floor\n"
      "note: reading order of the spec files is NOT the application order; follow this.\n")

    J("unit_scale_exponents.json", {
        "scale_exponents": CURRENCY_EXPONENTS,
        "note": "CRD/TKN/GLM authoritative; ORE gain is on the spreadsheet LIVE sheet only",
    })
    J("weighting_constants.json", {
        "cap": int(WEIGHT_CAP),
        "quantize_decimals": QUANT_DECIMALS,
        "residue_allocation": "largest_weight_then_smallest_match_key",
    })
    J("tier_server_topology.json", {
        "tiers": TIERS, "servers": SERVERS, "strata": STRATA,
        "sampled_partition": "frozen_tier_server",
        "nonresponse_partition": "server",
    })
    J("sample_metrics_layout.json", {
        "metrics.json": {"overall": ["precision", "recall", "fbeta",
                                     "macro_precision", "macro_recall"],
                         "strata": "per-stratum precision/recall/fbeta"},
    })
    J("verdict_crosswalk.json", {
        "LADDER_CLEAR": "positive",
        "VOID_SMURF": "negative",
        "SHADOW_HOLD": "excluded",
        "PENDING_REMATCH": "excluded",
    })
    J("unit_test_vectors.json", {
        "logit_examples": {"0.5": "0", "0.75": "1.0986122886681098"},
        "fbeta_example": {"beta": "1.0", "p": "0.8", "r": "0.6", "note": "illustrative beta only; the graded F-beta beta lives in the policy PDF"},
        "largest_remainder": {"amounts": [10, 20, 70], "bps": [1000, 2000, 7000]},
        "sigmoid_zero": "0.5",
    })

    named_checks = [
        {"checkpoint": "quantized_weight_sum_matches_unrounded_stratum_total", "must_hold": True},
        {"checkpoint": "share_bps_sum_equals_10000", "must_hold": True},
        {"checkpoint": "excluded_rows_absent_from_weights_csv", "must_hold": True},
        {"checkpoint": "overall_pr_is_ratio_of_weighted_totals", "must_hold": True},
        {"checkpoint": "drift_reference_is_latest_on_or_before_anchor", "must_hold": True},
        {"checkpoint": "anchor_is_first_attempt_not_canonical", "must_hold": True},
        {"checkpoint": "verdicts_ordered_by_review_seq_not_amended_at", "must_hold": True},
        {"checkpoint": "threshold_comparison_is_inclusive", "must_hold": True},
        {"checkpoint": "calibration_in_log_odds_space", "must_hold": True},
        {"checkpoint": "ore_gain_from_live_sheet_only", "must_hold": True},
        {"checkpoint": "levy_then_floor_from_docx_only", "must_hold": True},
    ]
    checkpoints = []
    for st in STRATA:
        for ch in LANES:
            for base in named_checks:
                rec = dict(base)
                rec["stratum"] = st
                rec["lane"] = ch
                checkpoints.append(rec)
    write_text(out_dir / "settlement_checkpoints.ndjson",
               "\n".join(json.dumps(c) for c in checkpoints))
    gaps = []
    for i, fam in enumerate(["CRD", "TKN", "GLM", "ORE"] * 58):
        day = base_day + timedelta(days=(i * 3) % 96)
        gaps.append({"unit_family": fam, "ref_date": day.isoformat(),
                     "policy": "use latest reference on or before the anchor",
                     "incident_no": i})
    write_text(out_dir / "drift_reference_audit.ndjson",
               "\n".join(json.dumps(g) for g in gaps))
    worked = []
    for i in range(220):
        worked.append({"match_key": f"AC{2000 + i % 234}|{TIERS[i % 3].lower()}|SD{100000 + i}|S{1 + i % 9}",
                       "stage": STRATA[i % 9], "note": "reference worked example - see specs"})
    write_text(out_dir / "sample_worked_records.jsonl",
               "\n".join(json.dumps(w) for w in worked))
    hints = []
    for i in range(234):
        hints.append({"account_id": f"AC{2000 + i}", "stratum": STRATA[i % 9],
                      "expected_nonempty": True})
    write_text(out_dir / "stratum_population_hints.jsonl",
               "\n".join(json.dumps(h) for h in hints))
    levy_ex = []
    for i in range(205):
        levy_ex.append({"stratum": STRATA[i % 9],
                        "step": ["review", "levy", "floor"][i % 3],
                        "note": "levy_bps and floor are in the DOCX only"})
    write_text(out_dir / "levy_worked_examples.jsonl",
               "\n".join(json.dumps(x) for x in levy_ex))

    grouping = ['<?xml version="1.0" encoding="UTF-8"?>', "<grouping_keys>"]
    grouping.append("  <match_key>account_id|hero_handle|seed_hash|ladder_split</match_key>")
    grouping.append("  <weight_partition>frozen_tier_server</weight_partition>")
    grouping.append("  <nonresponse_partition>server</nonresponse_partition>")
    grouping.append("</grouping_keys>")
    write_text(out_dir / "grouping_keys.xml", "\n".join(grouping))

    thr = ['<?xml version="1.0" encoding="UTF-8"?>', "<threshold_semantics>"]
    thr.append("  <comparison>inclusive</comparison>")
    thr.append("  <rule>yhat = 1 if p_cal &gt;= tau_s</rule>")
    thr.append("</threshold_semantics>")
    write_text(out_dir / "threshold_semantics.xml", "\n".join(thr))

    payorder = ['<?xml version="1.0" encoding="UTF-8"?>', "<payout_order>"]
    payorder.append("  <step n=\"1\">rewarded = TP * recovery</step>")
    payorder.append("  <step n=\"2\">subtract review_cost (PDF)</step>")
    payorder.append("  <step n=\"3\">subtract smurf_levy (DOCX)</step>")
    payorder.append("  <step n=\"4\">apply settlement floor (DOCX), last</step>")
    payorder.append("</payout_order>")
    write_text(out_dir / "payout_order.xml", "\n".join(payorder))

    verdmap = {"LADDER_CLEAR": "positive", "VOID_SMURF": "negative",
               "SHADOW_HOLD": "excluded", "PENDING_REMATCH": "excluded"}
    case_rows = []
    vk = list(verdmap)
    for i in range(234):
        v = vk[i % 4]
        case_rows.append([STRATA[i % 9], v, verdmap[v]])
    write_table(out_dir / "verdict_disposition_summary.tsv",
                ["stratum", "verdict", "meaning"], case_rows, delim="\t")
    revhist = []
    for i in range(216):
        revhist.append([f"AC{2000 + i % 234}", str(1 + i % 3), "amended_at is backfilled"])
    write_table(out_dir / "verdict_revision_notes.tsv",
                ["account_id", "review_seq", "note"], revhist, delim="\t")

    sampling = [[s, str(STRATA.index(s)), "frozen"] for s in STRATA for _ in range(26)]
    write_table(out_dir / "sampling_design_summary.psv",
                ["stratum", "ordinal", "status"], sampling, delim="|")
    audit_draw = [[f"AC{2000 + i % 234}", STRATA[i % 9], str(i % 2)] for i in range(234)]
    write_table(out_dir / "audit_draw_register.psv",
                ["account_id", "stratum_frozen", "drawn"], audit_draw, delim="|")

    W("seal_status_codes.txt",
      "SEALED = match committed to the ladder; eligible to be canonical\n"
      "OPEN   = not sealed; a key with only OPEN rows never sealed and is dropped\n")
    W("field_order_notes.txt",
      "Output rows are sorted by match_key ascending. Decimals are emitted as strings.\n"
      "Files use line-feed endings and a trailing newline.\n")
    W("escalation_matrix.txt",
      "Severity ladder for review escalation. Reference only; not graded.\n"
      + "\n".join(f"level {i}: escalate after {i*2} holds" for i in range(1, 12)))
    W("stratum_enumeration.txt", "\n".join(STRATA))
    W("digest_specification.md",
      "# Manifest Digest\n\nCompute the SHA-256 over the exact bytes of the four core\n"
      "files in this order: population.csv, weights.csv, payout.csv, metrics.json.\n"
      "Emit it as `digest_sha256` in manifest.json with `core_order` listing the four.\n")
    W("binary_reading_notes.md",
      "# Reading the Binary Inputs (stdlib only)\n\n"
      "The spreadsheet is a standard OOXML zip: open it with `zipfile`, read\n"
      "`xl/worksheets/sheet1.xml` and any shared strings, and parse cells with\n"
      "`xml.etree.ElementTree`. The live sheet is the one whose B1 cell equals the\n"
      "`calibration_version` in season_profile.json.\n\n"
      "The policy document is a plain PDF 1.4 with uncompressed text streams. Extract\n"
      "the text with `zlib` (for any deflated stream) and two regexes over the raw\n"
      "bytes: the stream body pattern `stream\\r?\\n(.*?)\\r?\\nendstream` and the\n"
      "show-text pattern `\\(((?:\\\\.|[^\\\\()])*)\\)\\s*Tj`. As hex byte strings these\n"
      "are `73747265616d5c723f5c6e282e2a3f295c723f5c6e656e6473747265616d` and\n"
      "`5c2828283f3a5c5c2e7c5b5e5c5c28295d292a295c295c732a546a`. The review unit cost,\n"
      "the F-beta beta, and the CI z read out of the extracted text lines.\n\n"
      "The levy addendum is a standard OOXML DOCX zip: open it with `zipfile`, read\n"
      "`word/document.xml`, and pull the text out of the `<w:t>` elements with\n"
      "`xml.etree.ElementTree`. The smurf levy basis points and the settlement floor\n"
      "read out of those paragraphs. The SQLite lookups (`.sqlite` and `.db`) are\n"
      "real databases; open them with the `sqlite3` module. Every value they hold is\n"
      "also present in a flat file.\n")
    W("glossary_and_field_dictionary.md",
      "# Glossary\n\n- match_key: account_id|hero_handle|seed_hash|ladder_split\n"
      "- canonical: highest checkpoint_no among SEALED attempts\n"
      "- anchor: first attempt (min checkpoint_no)\n"
      "- p_eff: running-baseline-folded probability\n"
      "- p_cal: log-odds calibrated probability\n"
      "- ledger_unit: integer units after currency + drift conversion\n")
    W("known_traps_and_footguns.md",
      "# Known Footguns\n\n"
      "1. match_uid is per-attempt; the key is account|hero|seed|split.\n"
      "2. Anchor on the FIRST attempt, not the canonical row.\n"
      "3. Order verdicts by review_seq; amended_at is backfilled.\n"
      "4. Weight partitions differ (frozen stratum vs server).\n"
      "5. Inflate weights before quantization and residue allocation.\n"
      "6. Calibrate in log-odds space; legacy plaintext multipliers are superseded.\n"
      "7. Threshold comparison is inclusive (>=).\n"
      "8. ORE gain is spreadsheet-only; cost/beta/z are PDF-only.\n"
      "9. Drift uses the latest reference dated on or before the anchor.\n"
      "10. Never regroup by current_tier; the frozen stratum is authoritative.\n"
      "11. Smurf levy and settlement floor are DOCX-only; apply levy then floor last.\n")
    W("changelog_2026S2.md",
      "# Changelog 2026S2\n\n- Superseded the DRAFT gain sheet with the LIVE sheet.\n"
      "- Deprecated the plaintext legacy multipliers (see calibration_legacy_multipliers.csv).\n"
      "- Fixed the anchor definition to the first attempt.\n"
      "- Added the smurf levy and settlement floor addendum (DOCX).\n")
    W("reviewer_faq.md",
      "# Reviewer FAQ\n\nQ: Why does corrected recall land below the rejected run?\n"
      "A: The maturation window removes late verdicts; that is expected, not a bug.\n"
      "Q: Why is the season net lower than rewarded credits?\n"
      "A: The review cost, the smurf levy, and the settlement floor all apply after.\n")
    W("levy_addendum_pointer.md",
      "# Levy Addendum Pointer\n\nThe smurf levy basis points and the per-stratum\n"
      "settlement floor are published ONLY in settlement_levy_addendum.docx. No\n"
      "plaintext or spreadsheet copy is authoritative; any that resembles them is a\n"
      "decoy. Apply the levy on rewarded credits, then floor the net last.\n")

    W("output_artifact_schemas.md",
      "# Output Artifact Schemas\n\n"
      "## Reusable program\n\n"
      "`settle.py` is a Python 3.12 standard-library program. Invoke it as\n"
      "`python3 settle.py DATA_DIR OUT_DIR`. It reads the complete contract and corpus\n"
      "from `DATA_DIR`, creates `OUT_DIR` if needed, and overwrites the twenty-nine data\n"
      "artifacts defined below. It must not read a fixed `/app/data` path when another\n"
      "`DATA_DIR` is supplied. A valid corpus has the same filenames and schemas as this\n"
      "one, but its rows, dates, workbook sheet order, generated identifiers, and the\n"
      "authoritative constants inside the selected LIVE sheet, PDF, and DOCX may differ.\n"
      "Read those sources for every run rather than embedding values from this corpus.\n"
      "The program writes no undeclared files.\n\n"
      "This file is part of the written contract. It fixes the EXACT shape of every\n"
      "artifact the settlement writes under /app/out: the column headers of each\n"
      "delimited table, the key names of each JSON object, the line layout of each\n"
      "text and XML file, and the row order. Only names and layout are given here;\n"
      "every number must be computed from the inputs per the stage specs, so no\n"
      "value is leaked. All files use UTF-8, line-feed endings and a trailing\n"
      "newline. JSON objects are emitted with two-space indentation and keys sorted\n"
      "lexicographically, so key order in the file is alphabetical regardless of the\n"
      "order listed below. Decimals are emitted as strings at the stated precision.\n"
      "Delimited rows are sorted by match_key ascending, or listed in the fixed\n"
      "stratum order below when the row key is a stratum.\n\n"
      "Fixed stratum order (used for every per-stratum row and per-stratum key):\n"
      "BRONZE-NA, BRONZE-EU, BRONZE-APAC, SILVER-NA, SILVER-EU, SILVER-APAC,\n"
      "GOLD-NA, GOLD-EU, GOLD-APAC.\n\n"
      "Per-stratum metrics filename slugs:\n"
      "BRONZE-NA to metrics_bro_na.json, BRONZE-EU to metrics_bro_eu.json,\n"
      "BRONZE-APAC to metrics_bro_ap.json, SILVER-NA to metrics_sil_na.json,\n"
      "SILVER-EU to metrics_sil_eu.json, SILVER-APAC to metrics_sil_ap.json,\n"
      "GOLD-NA to metrics_gld_na.json, GOLD-EU to metrics_gld_eu.json,\n"
      "GOLD-APAC to metrics_gld_ap.json.\n\n"
      "## population.csv\n"
      "Comma-separated. Header row, then one row per surviving match key sorted by\n"
      "match_key ascending. Columns in this exact order:\n"
      "match_key, account_id, stratum, drawn, loot_currency, anchor_date\n\n"
      "## weights.csv\n"
      "Comma-separated. Header row, then one row per resolved-and-drawn match sorted\n"
      "by match_key ascending. Columns in this exact order:\n"
      "match_key, stratum, y, yhat, loot_currency, ledger_units, p_eff, p_cal, weight\n"
      "ledger_units is an integer ledger amount. p_eff and p_cal are strings with\n"
      "eight decimals; weight is a string with six decimals.\n\n"
      "## payout.csv\n"
      "Comma-separated. Header row, then one row per stratum in the fixed stratum\n"
      "order, then a final row whose first field is TOTAL carrying the column sums.\n"
      "Columns in this exact order:\n"
      "stratum, rewarded_credits, forfeited_credits, review_credits, levy_credits, net_credits\n\n"
      "## payout_breakdown.tsv\n"
      "Tab-separated. Header row, then one row per stratum in the fixed stratum\n"
      "order. Columns in this exact order:\n"
      "stratum, rewarded_credits, forfeited_credits\n\n"
      "## payout_ledger.psv\n"
      "Pipe-separated. Header row, then one row per stratum in the fixed stratum\n"
      "order. Columns in this exact order:\n"
      "stratum, review_credits, levy_credits, net_credits\n\n"
      "## forfeited_shares.csv\n"
      "Comma-separated. Header row, then one row per stratum in the fixed stratum\n"
      "order. Columns in this exact order:\n"
      "stratum, forfeited_credits, share_bps\n\n"
      "## confidence_intervals.csv\n"
      "Comma-separated. Header row, then one row per stratum in the fixed stratum\n"
      "order. Columns in this exact order:\n"
      "stratum, recall_lo, recall_hi, prec_lo, prec_hi, n_eff_recall, n_eff_precision\n"
      "All six numeric columns are strings with six decimals.\n\n"
      "## metrics.json\n"
      "JSON object with exactly two keys, overall and strata. overall is an object\n"
      "with keys precision, recall, fbeta, macro_precision, macro_recall. strata is\n"
      "an object keyed by stratum name, each value an object with keys precision,\n"
      "recall, fbeta. Every value is a six-decimal string.\n\n"
      "## metrics_<slug>.json (nine files, one per stratum)\n"
      "JSON object with keys stratum, precision, recall, fbeta, tp, fp, fn. stratum\n"
      "is the stratum name; precision, recall and fbeta are six-decimal strings; tp,\n"
      "fp and fn are six-decimal strings of the weighted counts.\n\n"
      "## stratum_metrics_stream.jsonl\n"
      "One JSON object per line, one per stratum in the fixed stratum order, each\n"
      "with keys stratum, precision, recall, fbeta (six-decimal strings). The file\n"
      "ends with a trailing newline.\n\n"
      "## overall_metrics.md\n"
      "Markdown. First line is a level-one heading reading Overall Settled Metrics,\n"
      "then a blank line, then one bullet line per figure in this order: precision,\n"
      "recall, fbeta, macro_precision, macro_recall, each written as `- name: value`.\n\n"
      "## reconciliation_report.md\n"
      "Markdown. First line is a level-one heading reading Settlement Reconciliation\n"
      "Report, then a blank line, then one bullet line each in this order:\n"
      "population, resolved, weighted, total_net_credits, calibration_version, each\n"
      "written as `- name: value`.\n\n"
      "## rollup.xml\n"
      "XML. An xml declaration line, then a rollup root element holding one stratum\n"
      "element per stratum in the fixed stratum order. Each stratum element carries\n"
      "an id attribute of the stratum name and child elements precision, recall and\n"
      "fbeta with six-decimal string text.\n\n"
      "## label_distribution.json\n"
      "JSON object with keys positive, negative, resolved_total, population_total,\n"
      "all integer counts.\n\n"
      "## decision_distribution.json\n"
      "JSON object with keys flagged, cleared, weighted_total, all integer counts.\n\n"
      "## frame_counts.json\n"
      "JSON object with keys population_by_stratum, sampled_by_stratum,\n"
      "resolved_weighted. Each value is an object keyed by stratum name with integer\n"
      "counts.\n\n"
      "## weight_diagnostics.json\n"
      "JSON object with keys weight_sum_by_stratum, cap, max_weight.\n"
      "weight_sum_by_stratum is an object keyed by stratum name with six-decimal\n"
      "string sums. cap is the weight cap as a string. max_weight is a six-decimal\n"
      "string.\n\n"
      "## net_payout_summary.json\n"
      "JSON object with keys total_rewarded_credits, total_forfeited_credits,\n"
      "total_review_credits, total_levy_credits, total_net_credits (integers) and\n"
      "by_stratum, an object keyed by stratum name with the integer net_credits.\n\n"
      "## levy_summary.json\n"
      "JSON object with keys levy_bps (integer), settlement_floor (integer),\n"
      "total_levy_credits (integer), levy_by_stratum (object keyed by stratum name\n"
      "with integer levy credits) and floored_strata (a list of the stratum names\n"
      "whose pre-floor net fell below the floor, sorted ascending).\n\n"
      "## audit_summary.json\n"
      "JSON object with keys population, resolved, weighted, flagged (integer\n"
      "counts), overall_fbeta (six-decimal string) and calibration_version (string).\n\n"
      "## manifest.json\n"
      "JSON object with keys core_order and digest_sha256. core_order is the list\n"
      "population.csv, weights.csv, payout.csv, metrics.json. digest_sha256 is the\n"
      "hex SHA-256 over the concatenated exact bytes of those four files in that\n"
      "order.\n")

    legacy = []
    for i in range(234):
        s = STRATA[i % 9]
        legacy.append([f"AC{2000 + i}", s,
                       f"{D(CALIB[s]['a']) + D('0.2'):.4f}",
                       f"{D(CALIB[s]['b']) + D('0.2'):.4f}",
                       "SUPERSEDED - probability-space; do not use"])
    write_table(out_dir / "calibration_legacy_multipliers.csv",
                ["account_id", "stratum", "legacy_a", "legacy_b", "status"], legacy)
    decoy_levy = []
    for i in range(210):
        decoy_levy.append([STRATA[i % 9], str(rng.randint(100, 900)), str(rng.randint(100, 900)),
                           "DECOY - not authoritative; levy/floor are in the DOCX"])
    write_table(out_dir / "levy_floor_decoy_table.csv",
                ["stratum", "fake_levy_bps", "fake_floor", "status"], decoy_levy)

    write_table(out_dir / F_ACCOUNTS,
                ["account_id", "frozen_tier", "frozen_server", "current_tier",
                 "current_server", "loot_currency"],
                [[a["account_id"], a["frozen_tier"], a["frozen_server"],
                  a["current_tier"], a["current_server"], a["currency"]] for a in accounts])


def generate(seed: int, out_dir) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(int(seed))
    base_day = date(2026, 4, 6)

    accounts = _accounts(rng)
    matches, ledger, frame = generate_core(rng, out_dir, base_day, accounts)
    drift_rows = _drift_book(rng, base_day)

    write_table(out_dir / F_DRIFT,
                ["unit_family", "ref_date", "drift_mult"],
                [[r["unit_family"], r["ref_date"], r["drift_mult"]] for r in drift_rows])

    write_json(out_dir / F_MANIFEST, {
        "audit_period": "2026S2",
        "calibration_version": CAL_VERSION,
        "weight_cap": WEIGHT_CAP,
        "window_days": WINDOW_DAYS,
        "base_p": "0.500000",
        "levy_bps_placeholder": None,
        "floor_placeholder": None,
    })

    if int(seed) == SAMPLE_SEED:
        hidden_values = (XLSX_ONLY_ORE_GAIN, PDF_INSPECT_UNIT_COST, PDF_BETA,
                         PDF_Z, DOCX_ONLY_SMURF_LEVY_BPS,
                         DOCX_ONLY_FLOOR_CREDITS, False)
    else:
        gains = ("0.0287", "0.0413", "0.0529", "0.0631")
        betas = ("1.5", "2.0", "3.0", "3.5")
        z_values = ("1.644854", "1.959964", "2.326348", "2.575829")
        slot = int(seed) % 4
        hidden_values = (gains[slot], 900 + int(seed) % 1300, betas[slot],
                         z_values[(slot + 1) % 4], 275 + int(seed) % 650,
                         250 + int(seed) % 900, bool(int(seed) & 1))
    ore_gain, review_cost, beta, z_value, levy_bps, floor, live_first = hidden_values
    write_tuning_xlsx(out_dir / F_XLSX, rng, ore_gain, live_first)
    write_cost_policy_pdf(out_dir / F_PDF, review_cost, beta, z_value)
    write_levy_addendum_docx(out_dir / F_DOCX, levy_bps, floor)
    write_reference_dbs(out_dir, drift_rows, accounts, frame, ledger)
    write_docs(out_dir, rng, base_day, accounts, drift_rows)

    n_files = sum(1 for p in out_dir.iterdir() if p.is_file())
    return {"n_files": n_files, "n_matches": len(matches), "n_accounts": len(accounts)}


# artifact names ------------------------------------------------------------
_MANIFEST_SLUGS = ["bro_na", "bro_eu", "bro_ap", "sil_na", "sil_eu",
                   "sil_ap", "gld_na", "gld_eu", "gld_ap"]
STRATUM_SLUG = {s: _MANIFEST_SLUGS[i] for i, s in enumerate(STRATA)}
CORE_FILES = ["population.csv", "weights.csv", "payout.csv", "metrics.json"]


# ---------------------------------------------------------------------------
# stdlib readers
# ---------------------------------------------------------------------------
def _read_table(path, delim):
    rows = []
    with open(path, encoding="utf-8", newline="") as fh:
        r = csv.reader(fh, delimiter=delim)
        header = next(r)
        for line in r:
            if not line:
                continue
            rows.append(dict(zip(header, line)))
    return rows


def _col_idx(ref):
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def read_xlsx_sheets(path):
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sroot = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sroot.findall("{*}si"):
                shared.append("".join(t.text or "" for t in si.findall(".//{*}t")))
        names = zf.namelist()
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        order = []
        for sh in wb.find("{*}sheets"):
            order.append(sh.get("name"))
        sheets = {}
        idx = 0
        for name in order:
            idx += 1
            target = f"xl/worksheets/sheet{idx}.xml"
            if target not in names:
                continue
            root = ET.fromstring(zf.read(target))
            rows = []
            for row in root.findall(".//{*}row"):
                cells = {}
                maxc = -1
                for c in row.findall("{*}c"):
                    col = _col_idx(c.get("r", ""))
                    ctype = c.get("t", "")
                    if ctype == "inlineStr":
                        val = "".join(t.text or "" for t in c.findall(".//{*}t"))
                    elif ctype == "s":
                        v = c.find("{*}v")
                        val = shared[int(v.text)] if v is not None and v.text else ""
                    else:
                        v = c.find("{*}v")
                        val = v.text if v is not None and v.text is not None else ""
                    cells[col] = val
                    maxc = max(maxc, col)
                rows.append([cells.get(i, "") for i in range(maxc + 1)])
            sheets[name] = rows
        return sheets


def read_pdf_text(path):
    data = Path(path).read_bytes()
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        raw = m.group(1)
        try:
            text = zlib.decompress(raw)
        except zlib.error:
            text = raw
        for lit in re.finditer(rb"\(((?:\\.|[^\\()])*)\)\s*Tj", text):
            s = lit.group(1)
            s = s.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            out.append(s.decode("latin-1"))
    return out


def read_docx_text(path):
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    paras = []
    for p in root.findall(".//{*}p"):
        text = "".join(t.text or "" for t in p.findall(".//{*}t"))
        paras.append(text)
    return paras


def read_inputs(data_dir):
    data_dir = Path(data_dir)
    matches = _read_table(data_dir / F_MATCHES, ",")
    ledger = _read_table(data_dir / F_LEDGER, "\t")
    frame = _read_table(data_dir / F_FRAME, "|")
    drift = _read_table(data_dir / F_DRIFT, ",")
    accounts = _read_table(data_dir / F_ACCOUNTS, ",")
    manifest = json.loads((data_dir / F_MANIFEST).read_text(encoding="utf-8"))

    ver = manifest["calibration_version"]
    sheets = read_xlsx_sheets(data_dir / F_XLSX)
    live = None
    ore_gain = None
    for name, rows in sheets.items():
        if rows and len(rows[0]) >= 2 and rows[0][1].strip() == ver:
            live = rows
            break
    if live is None:
        raise ValueError("no live tuning sheet")
    for row in live:
        if row and row[0].strip() == "ore_to_ledger_gain":
            ore_gain = D(row[1])
            break
    header_r = None
    for i, row in enumerate(live):
        if any(cell.strip() in STRATA for cell in row):
            header_r = i
            break
    header = live[header_r]
    colof = {}
    for j, cell in enumerate(header):
        c = cell.strip()
        if c in STRATA or c == "DEFAULT-ROW":
            colof[c] = j
    params = {}
    for row in live[header_r + 1:]:
        if not row:
            continue
        label = row[0].strip()
        if label in _PKEY:
            for strat, j in colof.items():
                if j < len(row) and row[j].strip():
                    params.setdefault(strat, {})[label] = row[j].strip()
    calib = {}
    for strat, d in params.items():
        if all(k in d for k in _PKEY):
            calib[strat] = {"a": D(d["a_s"]), "b": D(d["b_s"]),
                            "tau": D(d["tau_s"]), "recovery": D(d["recovery_s"])}

    pdf_lines = read_pdf_text(data_dir / F_PDF)
    joined = " ".join(pdf_lines)
    m_cost = re.search(r"unit cost is (\d+) credits", joined)
    m_beta = re.search(r"beta = (\d+\.\d+)", joined)
    m_z = re.search(r"z = (\d+\.\d+)", joined)
    review_cost = int(m_cost.group(1))
    beta = D(m_beta.group(1))
    z = D(m_z.group(1))

    docx_paras = read_docx_text(data_dir / F_DOCX)
    djoined = " ".join(docx_paras)
    m_levy = re.search(r"smurf levy of (\d+) basis points", djoined)
    m_floor = re.search(r"floored at (\d+) credits", djoined)
    levy_bps = int(m_levy.group(1))
    floor = int(m_floor.group(1))

    return {
        "matches": matches, "ledger": ledger, "frame": frame, "drift": drift,
        "accounts": accounts, "manifest": manifest, "calib": calib,
        "ore_gain": ore_gain, "review_cost": review_cost, "beta": beta, "z": z,
        "levy_bps": levy_bps, "floor": floor,
    }


# ---------------------------------------------------------------------------
# S1-S9 corrected settlement pipeline (ground truth)
# ---------------------------------------------------------------------------
def run_pipeline(data_dir):
    inp = read_inputs(data_dir)
    matches = inp["matches"]
    frame_by_key = {r["match_key"]: r for r in inp["frame"]}
    calib = inp["calib"]
    ore_gain = inp["ore_gain"]

    conf = {}
    for r in inp["ledger"]:
        conf.setdefault(r["match_key"], []).append(r)

    drift = {}
    for r in inp["drift"]:
        drift.setdefault(r["unit_family"], []).append((r["ref_date"], D(r["drift_mult"])))
    for k in drift:
        drift[k].sort()

    clusters = {}
    for s in matches:
        key = f'{s["account_id"]}|{s["hero_handle"]}|{s["seed_hash"]}|{s["ladder_split"]}'
        clusters.setdefault(key, []).append(s)

    population = []
    for key, sw in clusters.items():
        sealed = [x for x in sw if x["seal_status"] == "SEALED"]
        if not sealed:
            continue
        canonical = max(sealed, key=lambda x: int(x["checkpoint_no"]))
        anchor = min(sw, key=lambda x: int(x["checkpoint_no"]))
        anchor_date = anchor["match_epoch"]
        ac = key.split("|")[0]
        fr = frame_by_key.get(key)
        stratum = fr["stratum_frozen"] if fr else None
        drawn = fr["drawn"] if fr else "0"
        population.append({
            "match_key": key, "account_id": ac, "stratum": stratum,
            "drawn": drawn, "raw_loot": canonical["raw_loot"],
            "loot_currency": canonical["loot_currency"], "anchor_date": anchor_date,
            "p_raw": canonical["p_raw"],
        })
    population.sort(key=lambda r: r["match_key"])

    def resolve_verdict(key, anchor_date):
        revs = conf.get(key, [])
        anchor = date.fromisoformat(anchor_date)
        inwin = [r for r in revs
                 if 0 <= (date.fromisoformat(r["effective_at"]) - anchor).days <= WINDOW_DAYS]
        if not inwin:
            return None
        last = max(inwin, key=lambda r: int(r["review_seq"]))
        v = last["verdict"]
        if v == "LADDER_CLEAR":
            return 1
        if v == "VOID_SMURF":
            return 0
        return None

    for r in population:
        r["y"] = resolve_verdict(r["match_key"], r["anchor_date"])

    resolved = [r for r in population if r["y"] is not None and r["stratum"] is not None]

    base_p = D(inp["manifest"]["base_p"])
    running = {s: base_p for s in STRATA}
    for r in sorted(resolved, key=lambda r: (r["stratum"], r["match_key"])):
        prev = running[r["stratum"]]
        praw = clamp_prob(D(r["p_raw"]))
        p_eff = clamp_prob(D("0.85") * praw + D("0.15") * prev)
        r["p_eff"] = p_eff
        running[r["stratum"]] = p_eff

    def drift_mult(unit_family, anchor_date):
        rows = drift.get(unit_family, [])
        best = None
        anchor = date.fromisoformat(anchor_date)
        for d, m in rows:
            dd = date.fromisoformat(d)
            if dd <= anchor:
                if best is None or dd > best[0]:
                    best = (dd, m)
        return best[1] if best else None

    for r in resolved:
        unit = r["loot_currency"]
        raw = D(r["raw_loot"])
        if unit == "ORE":
            base_units = raw * ore_gain
        else:
            exp = CURRENCY_EXPONENTS[unit]
            base_units = raw * (D(10) ** exp)
        dm = drift_mult(unit, r["anchor_date"])
        if dm is None:
            r["units"] = None
        else:
            r["units"] = qint_even(base_units * dm)

    pop_by_stratum = {}
    for r in population:
        if r["stratum"]:
            pop_by_stratum[r["stratum"]] = pop_by_stratum.get(r["stratum"], 0) + 1
    sampled_by_stratum = {}
    for r in population:
        if r["stratum"] and r["drawn"] == "1":
            sampled_by_stratum[r["stratum"]] = sampled_by_stratum.get(r["stratum"], 0) + 1
    sampled_by_server = {}
    resolved_by_server = {}
    for r in population:
        if r["stratum"] and r["drawn"] == "1":
            srv = r["stratum"].split("-")[1]
            sampled_by_server[srv] = sampled_by_server.get(srv, 0) + 1
    for r in resolved:
        if r["drawn"] == "1":
            srv = r["stratum"].split("-")[1]
            resolved_by_server[srv] = resolved_by_server.get(srv, 0) + 1

    weighted = [r for r in resolved if r["drawn"] == "1"]
    for r in weighted:
        strat = r["stratum"]
        srv = strat.split("-")[1]
        base = D(pop_by_stratum[strat]) / D(sampled_by_stratum[strat])
        nonresp = D(sampled_by_server[srv]) / D(resolved_by_server[srv])
        r["w_pre"] = base * nonresp

    by_strat = {}
    for r in weighted:
        by_strat.setdefault(r["stratum"], []).append(r)
    for strat, group in by_strat.items():
        total = sum((r["w_pre"] for r in group), D(0))
        qsum = sum((q6(r["w_pre"]) for r in group), D(0))
        residue = q6(total) - qsum
        for r in group:
            r["w"] = q6(r["w_pre"])
        if residue != 0 and group:
            target = sorted(group, key=lambda r: (-r["w"], r["match_key"]))[0]
            target["w"] = q6(target["w"] + residue)

    for r in weighted:
        c = calib[r["stratum"]]
        zc = c["a"] + c["b"] * logit(r["p_eff"])
        p_cal = sigmoid(zc)
        r["p_cal"] = p_cal
        r["yhat"] = 1 if p_cal >= c["tau"] else 0

    def stratum_metrics(group):
        tp = sum((r["w"] for r in group if r["y"] == 1 and r["yhat"] == 1), D(0))
        fp = sum((r["w"] for r in group if r["y"] == 0 and r["yhat"] == 1), D(0))
        fn = sum((r["w"] for r in group if r["y"] == 1 and r["yhat"] == 0), D(0))
        prec = tp / (tp + fp) if (tp + fp) > 0 else D(0)
        rec = tp / (tp + fn) if (tp + fn) > 0 else D(0)
        b2 = inp["beta"] * inp["beta"]
        denom = b2 * prec + rec
        fb = ((D(1) + b2) * prec * rec / denom) if denom > 0 else D(0)
        return {"tp": tp, "fp": fp, "fn": fn, "precision": prec,
                "recall": rec, "fbeta": fb}

    strat_groups = {s: [r for r in weighted if r["stratum"] == s] for s in STRATA}
    strat_metrics = {s: stratum_metrics(g) for s, g in strat_groups.items()}

    overall = stratum_metrics(weighted)
    wshare = {}
    total_w = sum((r["w"] for r in weighted), D(0))
    for s in STRATA:
        wshare[s] = sum((r["w"] for r in strat_groups[s]), D(0))
    macro_prec = sum((strat_metrics[s]["precision"] * wshare[s] for s in STRATA), D(0)) / total_w if total_w > 0 else D(0)
    macro_rec = sum((strat_metrics[s]["recall"] * wshare[s] for s in STRATA), D(0)) / total_w if total_w > 0 else D(0)

    def kish(group):
        sw = sum((r["w"] for r in group), D(0))
        sw2 = sum((r["w"] * r["w"] for r in group), D(0))
        return (sw * sw / sw2) if sw2 > 0 else D(0)

    def wilson(p, n, zc):
        if n <= 0:
            return (D(0), D(0))
        z2 = zc * zc
        denom = D(1) + z2 / n
        centre = (p + z2 / (D(2) * n)) / denom
        margin = (zc * ((p * (D(1) - p) / n + z2 / (D(4) * n * n)).sqrt())) / denom
        return (centre - margin, centre + margin)

    ci_rows = []
    for s in STRATA:
        g = strat_groups[s]
        pos = [r for r in g if r["y"] == 1]
        pred = [r for r in g if r["yhat"] == 1]
        n_rec = kish(pos)
        n_prec = kish(pred)
        lo_r, hi_r = wilson(strat_metrics[s]["recall"], n_rec, inp["z"])
        lo_p, hi_p = wilson(strat_metrics[s]["precision"], n_prec, inp["z"])
        ci_rows.append({
            "stratum": s, "recall_lo": q6(lo_r), "recall_hi": q6(hi_r),
            "prec_lo": q6(lo_p), "prec_hi": q6(hi_p),
            "n_eff_recall": q6(n_rec), "n_eff_precision": q6(n_prec),
        })

    levy_bps = D(inp["levy_bps"])
    floor = inp["floor"]
    money_rows = []
    total_forfeited = D(0)
    forfeited_by_stratum = {}
    for s in STRATA:
        g = [r for r in strat_groups[s] if r["units"] is not None]
        rewarded = D(0)
        forfeited = D(0)
        review = D(0)
        rec_factor = calib[s]["recovery"] if s in calib else D("0.8")
        for r in g:
            wunit = D(r["units"]) * r["w"]
            if r["y"] == 1 and r["yhat"] == 1:
                rewarded += qint_even(wunit * rec_factor)
            if r["y"] == 1 and r["yhat"] == 0:
                forfeited += qint_even(wunit)
            if r["yhat"] == 1:
                review += qint_even(D(inp["review_cost"]) * r["w"])
        rewarded_i = qint_even(rewarded)
        forfeited_i = qint_even(forfeited)
        review_i = qint_even(review)
        levy_i = qint_even(D(rewarded_i) * levy_bps / D(10000))
        net_pre_floor = rewarded_i - review_i - levy_i
        net = max(floor, net_pre_floor)
        money_rows.append({"stratum": s, "rewarded_credits": rewarded_i,
                           "forfeited_credits": forfeited_i, "review_credits": review_i,
                           "levy_credits": levy_i, "net_credits": net})
        forfeited_by_stratum[s] = forfeited_i
        total_forfeited += forfeited_i

    shares = {}
    if total_forfeited > 0:
        raw_bps = {s: (D(forfeited_by_stratum[s]) * D(10000) / D(total_forfeited)) for s in STRATA}
        floor_bps = {s: int(raw_bps[s]) for s in STRATA}
        rem = 10000 - sum(floor_bps.values())
        order = sorted(STRATA, key=lambda s: (-(raw_bps[s] - int(raw_bps[s])), s))
        for i in range(rem):
            floor_bps[order[i]] += 1
        shares = floor_bps
    else:
        shares = {s: 0 for s in STRATA}

    return _emit_artifacts(inp, population, resolved, weighted, strat_groups,
                           strat_metrics, overall, macro_prec, macro_rec,
                           ci_rows, money_rows, forfeited_by_stratum, shares,
                           pop_by_stratum, sampled_by_stratum)


def _emit_artifacts(inp, population, resolved, weighted, strat_groups,
                    strat_metrics, overall, macro_prec, macro_rec, ci_rows,
                    money_rows, forfeited_by_stratum, shares, pop_by_stratum,
                    sampled_by_stratum):
    art = {}

    def csv_bytes(header, rows, delim=","):
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=delim, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow(r)
        return buf.getvalue().encode("utf-8")

    def json_bytes(obj):
        return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")

    pop_sorted = sorted(population, key=lambda r: r["match_key"])
    art["population.csv"] = csv_bytes(
        ["match_key", "account_id", "stratum", "drawn", "loot_currency", "anchor_date"],
        [[r["match_key"], r["account_id"], r["stratum"] or "", r["drawn"],
          r["loot_currency"], r["anchor_date"]] for r in pop_sorted])

    wsorted = sorted(weighted, key=lambda r: r["match_key"])
    art["weights.csv"] = csv_bytes(
        ["match_key", "stratum", "y", "yhat", "loot_currency", "ledger_units", "p_eff", "p_cal", "weight"],
        [[r["match_key"], r["stratum"], r["y"], r["yhat"], r["loot_currency"],
          "" if r["units"] is None else str(r["units"]),
          f'{q8(r["p_eff"]):.8f}', f'{q8(r["p_cal"]):.8f}', f'{r["w"]:.6f}']
         for r in wsorted])

    metrics_obj = {
        "overall": {
            "precision": f'{q6(overall["precision"]):.6f}',
            "recall": f'{q6(overall["recall"]):.6f}',
            "fbeta": f'{q6(overall["fbeta"]):.6f}',
            "macro_precision": f'{q6(macro_prec):.6f}',
            "macro_recall": f'{q6(macro_rec):.6f}',
        },
        "strata": {s: {
            "precision": f'{q6(strat_metrics[s]["precision"]):.6f}',
            "recall": f'{q6(strat_metrics[s]["recall"]):.6f}',
            "fbeta": f'{q6(strat_metrics[s]["fbeta"]):.6f}',
        } for s in STRATA},
    }
    art["metrics.json"] = json_bytes(metrics_obj)

    for s in STRATA:
        art[f"metrics_{STRATUM_SLUG[s]}.json"] = json_bytes({
            "stratum": s,
            "precision": f'{q6(strat_metrics[s]["precision"]):.6f}',
            "recall": f'{q6(strat_metrics[s]["recall"]):.6f}',
            "fbeta": f'{q6(strat_metrics[s]["fbeta"]):.6f}',
            "tp": f'{q6(strat_metrics[s]["tp"]):.6f}',
            "fp": f'{q6(strat_metrics[s]["fp"]):.6f}',
            "fn": f'{q6(strat_metrics[s]["fn"]):.6f}',
        })

    total_rew = sum(m["rewarded_credits"] for m in money_rows)
    total_forf = sum(m["forfeited_credits"] for m in money_rows)
    total_rev = sum(m["review_credits"] for m in money_rows)
    total_levy = sum(m["levy_credits"] for m in money_rows)
    total_net = sum(m["net_credits"] for m in money_rows)
    art["payout.csv"] = csv_bytes(
        ["stratum", "rewarded_credits", "forfeited_credits", "review_credits", "levy_credits", "net_credits"],
        [[m["stratum"], m["rewarded_credits"], m["forfeited_credits"], m["review_credits"], m["levy_credits"], m["net_credits"]]
         for m in money_rows] +
        [["TOTAL", total_rew, total_forf, total_rev, total_levy, total_net]])

    art["payout_breakdown.tsv"] = csv_bytes(
        ["stratum", "rewarded_credits", "forfeited_credits"],
        [[m["stratum"], m["rewarded_credits"], m["forfeited_credits"]] for m in money_rows],
        delim="\t")

    art["payout_ledger.psv"] = csv_bytes(
        ["stratum", "review_credits", "levy_credits", "net_credits"],
        [[m["stratum"], m["review_credits"], m["levy_credits"], m["net_credits"]] for m in money_rows],
        delim="|")

    art["forfeited_shares.csv"] = csv_bytes(
        ["stratum", "forfeited_credits", "share_bps"],
        [[s, forfeited_by_stratum[s], shares[s]] for s in STRATA])

    art["confidence_intervals.csv"] = csv_bytes(
        ["stratum", "recall_lo", "recall_hi", "prec_lo", "prec_hi",
         "n_eff_recall", "n_eff_precision"],
        [[c["stratum"], f'{c["recall_lo"]:.6f}', f'{c["recall_hi"]:.6f}',
          f'{c["prec_lo"]:.6f}', f'{c["prec_hi"]:.6f}',
          f'{c["n_eff_recall"]:.6f}', f'{c["n_eff_precision"]:.6f}'] for c in ci_rows])

    jl = []
    for s in STRATA:
        jl.append(json.dumps({
            "stratum": s,
            "precision": f'{q6(strat_metrics[s]["precision"]):.6f}',
            "recall": f'{q6(strat_metrics[s]["recall"]):.6f}',
            "fbeta": f'{q6(strat_metrics[s]["fbeta"]):.6f}',
        }, sort_keys=True))
    art["stratum_metrics_stream.jsonl"] = ("\n".join(jl) + "\n").encode("utf-8")

    label_dist = {"positive": sum(1 for r in resolved if r["y"] == 1),
                  "negative": sum(1 for r in resolved if r["y"] == 0),
                  "resolved_total": len(resolved),
                  "population_total": len(population)}
    art["label_distribution.json"] = json_bytes(label_dist)
    dec_dist = {"flagged": sum(1 for r in weighted if r["yhat"] == 1),
                "cleared": sum(1 for r in weighted if r["yhat"] == 0),
                "weighted_total": len(weighted)}
    art["decision_distribution.json"] = json_bytes(dec_dist)

    art["frame_counts.json"] = json_bytes({
        "population_by_stratum": {s: pop_by_stratum.get(s, 0) for s in STRATA},
        "sampled_by_stratum": {s: sampled_by_stratum.get(s, 0) for s in STRATA},
        "resolved_weighted": {s: len(strat_groups[s]) for s in STRATA},
    })

    art["weight_diagnostics.json"] = json_bytes({
        "weight_sum_by_stratum": {s: f'{sum((r["w"] for r in strat_groups[s]), D(0)):.6f}' for s in STRATA},
        "cap": WEIGHT_CAP,
        "max_weight": f'{max((r["w"] for r in weighted), default=D(0)):.6f}',
    })

    art["net_payout_summary.json"] = json_bytes({
        "total_rewarded_credits": total_rew,
        "total_forfeited_credits": total_forf,
        "total_review_credits": total_rev,
        "total_levy_credits": total_levy,
        "total_net_credits": total_net,
        "by_stratum": {m["stratum"]: m["net_credits"] for m in money_rows},
    })

    art["levy_summary.json"] = json_bytes({
        "levy_bps": inp["levy_bps"],
        "settlement_floor": inp["floor"],
        "total_levy_credits": total_levy,
        "levy_by_stratum": {m["stratum"]: m["levy_credits"] for m in money_rows},
        "floored_strata": sorted(m["stratum"] for m in money_rows
                                 if (m["rewarded_credits"] - m["review_credits"] - m["levy_credits"]) < inp["floor"]),
    })

    art["audit_summary.json"] = json_bytes({
        "population": len(population),
        "resolved": len(resolved),
        "weighted": len(weighted),
        "flagged": dec_dist["flagged"],
        "overall_fbeta": f'{q6(overall["fbeta"]):.6f}',
        "calibration_version": inp["manifest"]["calibration_version"],
    })

    md = io.StringIO()
    md.write("# Overall Settled Metrics\n\n")
    md.write(f'- precision: {q6(overall["precision"]):.6f}\n')
    md.write(f'- recall: {q6(overall["recall"]):.6f}\n')
    md.write(f'- fbeta: {q6(overall["fbeta"]):.6f}\n')
    md.write(f'- macro_precision: {q6(macro_prec):.6f}\n')
    md.write(f'- macro_recall: {q6(macro_rec):.6f}\n')
    art["overall_metrics.md"] = md.getvalue().encode("utf-8")

    rr = io.StringIO()
    rr.write("# Settlement Reconciliation Report\n\n")
    rr.write(f"- population: {len(population)}\n")
    rr.write(f"- resolved: {len(resolved)}\n")
    rr.write(f"- weighted: {len(weighted)}\n")
    rr.write(f"- total_net_credits: {total_net}\n")
    rr.write(f'- calibration_version: {inp["manifest"]["calibration_version"]}\n')
    art["reconciliation_report.md"] = rr.getvalue().encode("utf-8")

    xml = io.StringIO()
    xml.write('<?xml version="1.0" encoding="UTF-8"?>\n<rollup>\n')
    for s in STRATA:
        xml.write(f'  <stratum id="{s}">'
                  f'<precision>{q6(strat_metrics[s]["precision"]):.6f}</precision>'
                  f'<recall>{q6(strat_metrics[s]["recall"]):.6f}</recall>'
                  f'<fbeta>{q6(strat_metrics[s]["fbeta"]):.6f}</fbeta>'
                  f'</stratum>\n')
    xml.write("</rollup>\n")
    art["rollup.xml"] = xml.getvalue().encode("utf-8")

    h = hashlib.sha256()
    for name in CORE_FILES:
        h.update(art[name])
    art["manifest.json"] = json_bytes({
        "core_order": CORE_FILES,
        "digest_sha256": h.hexdigest(),
    })

    return art


def write_artifacts(data_dir, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    art = run_pipeline(data_dir)
    for name in sorted(art):
        (out / name).write_bytes(art[name])


# =====================================================================
# Channel A verifier body: seeds, corpus regen, recompute, graded tests
# =====================================================================
SAMPLE_SEED = 4471903288

APP_OUT = Path("/app/out")
_EXPECTED_CACHE = {}
_HIDDEN_TIMEOUT = 120
_HIDDEN_SEEDS = (99173011, 99173029, 99173047, 99173071,
                 99173107, 99173131, 99173159, 99173183,
                 99173203, 99173221, 99173243, 99173269)
_HIDDEN_LOCK = threading.RLock()


def _bind(workspace):
    global APP_OUT
    APP_OUT = Path(str(workspace)) / "out"


def _pass(thunk):
    try:
        thunk()
        return True
    except Exception:
        return False


def _write_corpus(target, seed=SAMPLE_SEED):
    generate(int(seed), Path(target))
    return Path(target)


def _expected(seed=SAMPLE_SEED):
    seed = int(seed)
    if seed not in _EXPECTED_CACHE:
        root = Path(tempfile.mkdtemp(prefix=f"gma-exp-{seed}-"))
        _write_corpus(root, seed)
        _EXPECTED_CACHE[seed] = run_pipeline(root)
    return _EXPECTED_CACHE[seed]


def _got(name):
    return (APP_OUT / name).read_bytes()


def _open_read_tree(path):
    path = Path(path)
    os.chmod(path, 0o755)
    for item in path.rglob("*"):
        os.chmod(item, 0o755 if item.is_dir() else 0o444)


def _run_hidden_unlocked(seed):
    """Run the delivered program on one isolated verifier-generated corpus."""
    source = APP_OUT / "settle.py"
    assert source.is_file() and source.stat().st_size > 0
    root = Path(tempfile.mkdtemp(prefix=f"gma-hidden-{seed}-"))
    proc = None
    try:
        data_dir, out_dir, bin_dir = root / "data", root / "out", root / "bin"
        data_dir.mkdir(); out_dir.mkdir(); bin_dir.mkdir()
        _write_corpus(data_dir, seed)
        staged = bin_dir / "settle.py"
        shutil.copyfile(source, staged)
        os.chmod(root, 0o755)
        _open_read_tree(data_dir)
        os.chmod(out_dir, 0o733)
        os.chmod(bin_dir, 0o755)
        os.chmod(staged, 0o444)
        setpriv = shutil.which("setpriv")
        assert setpriv
        argv = [setpriv, "--reuid=nobody", "--regid=nogroup", "--clear-groups",
                sys.executable, str(staged), str(data_dir), str(out_dir)]
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True)
        stdout, stderr = proc.communicate(timeout=_HIDDEN_TIMEOUT)
        assert proc.returncode == 0, (stdout[-1000:], stderr[-2000:])
        return {p.name: p.read_bytes() for p in out_dir.iterdir() if p.is_file()}
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, 9)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=2)
            except Exception:
                pass
        shutil.rmtree(root, ignore_errors=True)


def _run_hidden(seed):
    # Serial execution plus process-group cleanup leaves no readable sibling
    # corpus or writable sibling output for agent code to inspect or influence.
    with _HIDDEN_LOCK:
        return _run_hidden_unlocked(seed)


# --- positive tests: core facts are compared to truth once. Derived views are
# --- checked for byte-exact consistency with those delivered core facts.

def _got_json(name):
    return json.loads(_got(name).decode("utf-8"))


def _got_table(name, delim=","):
    return list(csv.DictReader(io.StringIO(_got(name).decode("utf-8")), delimiter=delim))


def _json_blob(obj):
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _table_blob(header, rows, delim=","):
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delim, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _impl_test_population_membership_exact():
    """POSITIVE: population.csv is byte-exact (S1 canonicalization)."""
    assert _got("population.csv") == _expected()["population.csv"]


def _weight_projection(fields):
    got = _got_table("weights.csv")
    exp = list(csv.DictReader(io.StringIO(_expected()["weights.csv"].decode("utf-8"))))
    return [[row[field] for field in fields] for row in got], [[row[field] for field in fields] for row in exp]


def _impl_test_weights_running_baseline():
    """POSITIVE: S3 match order and p_eff values are exact."""
    got, exp = _weight_projection(("match_key", "p_eff"))
    assert got == exp


def _impl_test_weights_ledger_units():
    """POSITIVE: S4 currency conversion and drift-adjusted ledger units are exact."""
    got, exp = _weight_projection(("match_key", "loot_currency", "ledger_units"))
    assert got == exp


def _impl_test_weights_rarity_weights():
    """POSITIVE: S5 frozen-stratum two-level rarity weights are exact."""
    got, exp = _weight_projection(("match_key", "stratum", "weight"))
    assert got == exp


def _impl_test_weights_calibration_decision():
    """POSITIVE: S6 calibrated probabilities and inclusive decisions are exact."""
    got, exp = _weight_projection(("match_key", "y", "p_cal", "yhat"))
    assert got == exp


def _metrics_from_delivered_weights():
    rows = _got_table("weights.csv")
    beta2 = D(PDF_BETA) * D(PDF_BETA)

    def block(group):
        tp = sum((D(r["weight"]) for r in group if r["y"] == "1" and r["yhat"] == "1"), D(0))
        fp = sum((D(r["weight"]) for r in group if r["y"] == "0" and r["yhat"] == "1"), D(0))
        fn = sum((D(r["weight"]) for r in group if r["y"] == "1" and r["yhat"] == "0"), D(0))
        precision = tp / (tp + fp) if tp + fp else D(0)
        recall = tp / (tp + fn) if tp + fn else D(0)
        denom = beta2 * precision + recall
        fbeta = (D(1) + beta2) * precision * recall / denom if denom else D(0)
        return {"precision": precision, "recall": recall, "fbeta": fbeta}

    strata = {s: block([r for r in rows if r["stratum"] == s]) for s in STRATA}
    overall = block(rows)
    total = sum((D(r["weight"]) for r in rows), D(0))
    mass = {s: sum((D(r["weight"]) for r in rows if r["stratum"] == s), D(0)) for s in STRATA}
    macro_p = sum((strata[s]["precision"] * mass[s] for s in STRATA), D(0)) / total
    macro_r = sum((strata[s]["recall"] * mass[s] for s in STRATA), D(0)) / total
    return {"overall": {"precision": f"{q6(overall['precision']):.6f}",
                         "recall": f"{q6(overall['recall']):.6f}",
                         "fbeta": f"{q6(overall['fbeta']):.6f}",
                         "macro_precision": f"{q6(macro_p):.6f}",
                         "macro_recall": f"{q6(macro_r):.6f}"},
            "strata": {s: {k: f"{q6(strata[s][k]):.6f}" for k in ("precision", "recall", "fbeta")} for s in STRATA}}


def _impl_test_metrics_overall_exact():
    """POSITIVE: S7 overall ratios and macro means follow delivered weights."""
    assert _got_json("metrics.json")["overall"] == _metrics_from_delivered_weights()["overall"]


def _impl_test_metrics_strata_exact():
    """POSITIVE: S7 per-stratum metrics follow delivered weights."""
    assert _got_json("metrics.json")["strata"] == _metrics_from_delivered_weights()["strata"]


def _impl_test_per_stratum_metrics_exact():
    """POSITIVE: the nine detailed metric views are consistent with metrics and weights."""
    metrics = _got_json("metrics.json")["strata"]
    weights = _got_table("weights.csv")
    for s in STRATA:
        rows = [r for r in weights if r["stratum"] == s]
        tp = sum((D(r["weight"]) for r in rows if r["y"] == "1" and r["yhat"] == "1"), D(0))
        fp = sum((D(r["weight"]) for r in rows if r["y"] == "0" and r["yhat"] == "1"), D(0))
        fn = sum((D(r["weight"]) for r in rows if r["y"] == "1" and r["yhat"] == "0"), D(0))
        expected = {"stratum": s, **metrics[s], "tp": f"{q6(tp):.6f}",
                    "fp": f"{q6(fp):.6f}", "fn": f"{q6(fn):.6f}"}
        assert _got(f"metrics_{STRATUM_SLUG[s]}.json") == _json_blob(expected)


def _payout_from_delivered_weights():
    rows = _got_table("weights.csv")
    money = []
    for s in STRATA:
        group = [r for r in rows if r["stratum"] == s and r["ledger_units"] != ""]
        rewarded = forfeited = review = D(0)
        recovery = D(CALIB[s]["recovery"])
        for r in group:
            weighted_units = D(r["ledger_units"]) * D(r["weight"])
            if r["y"] == "1" and r["yhat"] == "1":
                rewarded += qint_even(weighted_units * recovery)
            if r["y"] == "1" and r["yhat"] == "0":
                forfeited += qint_even(weighted_units)
            if r["yhat"] == "1":
                review += qint_even(D(PDF_INSPECT_UNIT_COST) * D(r["weight"]))
        rew, forfe, rev = qint_even(rewarded), qint_even(forfeited), qint_even(review)
        levy = qint_even(D(rew) * D(DOCX_ONLY_SMURF_LEVY_BPS) / D(10000))
        money.append({"stratum": s, "rewarded_credits": rew, "forfeited_credits": forfe,
                      "review_credits": rev, "levy_credits": levy,
                      "net_credits": max(DOCX_ONLY_FLOOR_CREDITS, rew - rev - levy)})
    totals = {k: sum(r[k] for r in money) for k in
              ("rewarded_credits", "forfeited_credits", "review_credits", "levy_credits", "net_credits")}
    return money + [{"stratum": "TOTAL", **totals}]


def _payout_projection(fields):
    got = _got_table("payout.csv")
    expected = _payout_from_delivered_weights()
    return [[row[field] for field in fields] for row in got], [[str(row[field]) for field in fields] for row in expected]


def _impl_test_payout_s8_exact():
    """POSITIVE: S8 rewarded, forfeited and review-credit columns are exact."""
    got, exp = _payout_projection(("stratum", "rewarded_credits", "forfeited_credits", "review_credits"))
    assert got == exp


def _impl_test_payout_s9_exact():
    """POSITIVE: S9 levy and floored-net columns are exact."""
    got, exp = _payout_projection(("stratum", "levy_credits", "net_credits"))
    assert got == exp


def _impl_test_levy_summary_exact():
    """POSITIVE: levy_summary is byte-exactly consistent with payout.csv."""
    rows = [r for r in _got_table("payout.csv") if r["stratum"] != "TOTAL"]
    ref = json.loads(_expected()["levy_summary.json"])
    floor = ref["settlement_floor"]
    expected = {"levy_bps": ref["levy_bps"], "settlement_floor": floor,
                "total_levy_credits": sum(int(r["levy_credits"]) for r in rows),
                "levy_by_stratum": {r["stratum"]: int(r["levy_credits"]) for r in rows},
                "floored_strata": sorted(r["stratum"] for r in rows
                    if int(r["rewarded_credits"]) - int(r["review_credits"]) - int(r["levy_credits"]) < floor)}
    assert _got("levy_summary.json") == _json_blob(expected)


def _impl_test_payout_breakdown_exact():
    """POSITIVE: payout_breakdown.tsv is exact on an unseen corpus."""
    got = _run_hidden(_HIDDEN_SEEDS[8])
    assert got["payout_breakdown.tsv"] == _expected(_HIDDEN_SEEDS[8])["payout_breakdown.tsv"]


def _impl_test_payout_ledger_exact():
    """POSITIVE: payout_ledger.psv is exact on an unseen corpus."""
    got = _run_hidden(_HIDDEN_SEEDS[9])
    assert got["payout_ledger.psv"] == _expected(_HIDDEN_SEEDS[9])["payout_ledger.psv"]


def _impl_test_net_payout_summary_exact():
    """POSITIVE: net_payout_summary.json is exact on an unseen corpus."""
    got = _run_hidden(_HIDDEN_SEEDS[10])
    assert got["net_payout_summary.json"] == _expected(_HIDDEN_SEEDS[10])["net_payout_summary.json"]


def _impl_test_forfeited_shares_exact():
    """POSITIVE: forfeited shares apportion payout forfeitures to exactly 10000 bps."""
    rows = [r for r in _got_table("payout.csv") if r["stratum"] != "TOTAL"]
    amounts = {r["stratum"]: int(r["forfeited_credits"]) for r in rows}
    total = sum(amounts.values())
    raw = {s: D(amounts[s]) * D(10000) / D(total) for s in STRATA}
    shares = {s: int(raw[s]) for s in STRATA}
    order = sorted(STRATA, key=lambda s: (-(raw[s] - int(raw[s])), s))
    for i in range(10000 - sum(shares.values())):
        shares[order[i]] += 1
    expected = _table_blob(["stratum", "forfeited_credits", "share_bps"],
        [[s, amounts[s], shares[s]] for s in STRATA])
    assert _got("forfeited_shares.csv") == expected


def _impl_test_confidence_intervals_exact():
    """POSITIVE: S8 Wilson and Kish intervals follow delivered weights."""
    rows = _got_table("weights.csv")

    def kish(group):
        sw = sum((D(r["weight"]) for r in group), D(0))
        sw2 = sum((D(r["weight"]) ** 2 for r in group), D(0))
        return sw * sw / sw2 if sw2 else D(0)

    def wilson(p, n):
        if not n:
            return D(0), D(0)
        z = D(PDF_Z); z2 = z * z; denom = D(1) + z2 / n
        centre = (p + z2 / (D(2) * n)) / denom
        margin = z * (p * (D(1) - p) / n + z2 / (D(4) * n * n)).sqrt() / denom
        return centre - margin, centre + margin

    expected = []
    for s in STRATA:
        group = [r for r in rows if r["stratum"] == s]
        positives = [r for r in group if r["y"] == "1"]
        predicted = [r for r in group if r["yhat"] == "1"]
        tp = sum((D(r["weight"]) for r in group if r["y"] == "1" and r["yhat"] == "1"), D(0))
        actual_mass = sum((D(r["weight"]) for r in positives), D(0))
        predicted_mass = sum((D(r["weight"]) for r in predicted), D(0))
        recall = tp / actual_mass if actual_mass else D(0)
        precision = tp / predicted_mass if predicted_mass else D(0)
        nr, np = kish(positives), kish(predicted)
        lr, hr = wilson(recall, nr)
        lp, hp = wilson(precision, np)
        expected.append([s, f"{q6(lr):.6f}", f"{q6(hr):.6f}", f"{q6(lp):.6f}",
                         f"{q6(hp):.6f}", f"{q6(nr):.6f}", f"{q6(np):.6f}"])
    assert _got("confidence_intervals.csv") == _table_blob(
        ["stratum", "recall_lo", "recall_hi", "prec_lo", "prec_hi", "n_eff_recall", "n_eff_precision"], expected)


def _impl_test_manifest_exact():
    """POSITIVE: manifest digest matches the delivered four core files."""
    digest = hashlib.sha256()
    for name in CORE_FILES:
        digest.update(_got(name))
    assert _got("manifest.json") == _json_blob({"core_order": CORE_FILES,
                                                  "digest_sha256": digest.hexdigest()})


def _impl_test_frame_counts_exact():
    """POSITIVE: frame_counts is consistent with population and weights."""
    pop, weights = _got_table("population.csv"), _got_table("weights.csv")
    expected = {"population_by_stratum": {s: sum(r["stratum"] == s for r in pop) for s in STRATA},
                "sampled_by_stratum": {s: sum(r["stratum"] == s and r["drawn"] == "1" for r in pop) for s in STRATA},
                "resolved_weighted": {s: sum(r["stratum"] == s for r in weights) for s in STRATA}}
    assert _got("frame_counts.json") == _json_blob(expected)


def _impl_test_stratum_metrics_stream_exact():
    """POSITIVE: the metrics stream is exact on an unseen corpus."""
    got = _run_hidden(_HIDDEN_SEEDS[11])
    assert got["stratum_metrics_stream.jsonl"] == _expected(_HIDDEN_SEEDS[11])["stratum_metrics_stream.jsonl"]


def _impl_test_label_distribution_exact():
    """POSITIVE: label_distribution.json byte-exact (S2 labels)."""
    assert _got("label_distribution.json") == _expected()["label_distribution.json"]


def _impl_test_decision_distribution_exact():
    """POSITIVE: decision_distribution is consistent with weights.csv."""
    rows = _got_table("weights.csv")
    expected = {"flagged": sum(r["yhat"] == "1" for r in rows),
                "cleared": sum(r["yhat"] == "0" for r in rows), "weighted_total": len(rows)}
    assert _got("decision_distribution.json") == _json_blob(expected)


def _impl_test_weight_diagnostics_exact():
    """POSITIVE: weight diagnostics are consistent with weights.csv."""
    rows = _got_table("weights.csv")
    expected = {"weight_sum_by_stratum": {s: f"{sum((D(r['weight']) for r in rows if r['stratum'] == s), D(0)):.6f}" for s in STRATA},
                "cap": WEIGHT_CAP, "max_weight": f"{max((D(r['weight']) for r in rows), default=D(0)):.6f}"}
    assert _got("weight_diagnostics.json") == _json_blob(expected)


def _impl_test_audit_summary_exact():
    """POSITIVE: audit_summary is consistent with delivered core views."""
    pop, weights = _got_table("population.csv"), _got_table("weights.csv")
    labels, metrics = _got_json("label_distribution.json"), _got_json("metrics.json")
    ref = json.loads(_expected()["audit_summary.json"])
    expected = {"population": len(pop), "resolved": labels["resolved_total"], "weighted": len(weights),
                "flagged": sum(r["yhat"] == "1" for r in weights),
                "overall_fbeta": metrics["overall"]["fbeta"],
                "calibration_version": ref["calibration_version"]}
    assert _got("audit_summary.json") == _json_blob(expected)


def _impl_test_overall_metrics_md_exact():
    """POSITIVE: overall_metrics.md is consistent with metrics.json."""
    overall = _got_json("metrics.json")["overall"]
    expected = "# Overall Settled Metrics\n\n" + "".join(f"- {k}: {overall[k]}\n" for k in
        ("precision", "recall", "fbeta", "macro_precision", "macro_recall"))
    assert _got("overall_metrics.md") == expected.encode()


def _impl_test_reconciliation_report_exact():
    """POSITIVE: reconciliation report is consistent with delivered summaries."""
    pop, weights = _got_table("population.csv"), _got_table("weights.csv")
    labels, payout = _got_json("label_distribution.json"), _got_table("payout.csv")[-1]
    version = json.loads(_expected()["audit_summary.json"])["calibration_version"]
    expected = ("# Settlement Reconciliation Report\n\n"
        f"- population: {len(pop)}\n- resolved: {labels['resolved_total']}\n- weighted: {len(weights)}\n"
        f"- total_net_credits: {payout['net_credits']}\n- calibration_version: {version}\n")
    assert _got("reconciliation_report.md") == expected.encode()


def _impl_test_rollup_exact():
    """POSITIVE: rollup.xml is consistent with metrics.json."""
    strata = _got_json("metrics.json")["strata"]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<rollup>"]
    for s in STRATA:
        m = strata[s]
        lines.append(f'  <stratum id="{s}"><precision>{m["precision"]}</precision><recall>{m["recall"]}</recall><fbeta>{m["fbeta"]}</fbeta></stratum>')
    lines.append("</rollup>")
    assert _got("rollup.xml") == ("\n".join(lines) + "\n").encode()


# --- unseen-corpus generalisation: each check runs the delivered program on a
# --- different verifier-generated valid corpus and grades one core outcome.

def _impl_test_hidden_population_exact():
    got = _run_hidden(_HIDDEN_SEEDS[0])
    assert got["population.csv"] == _expected(_HIDDEN_SEEDS[0])["population.csv"]


def _impl_test_hidden_weights_exact():
    got = _run_hidden(_HIDDEN_SEEDS[1])
    assert got["weights.csv"] == _expected(_HIDDEN_SEEDS[1])["weights.csv"]


def _impl_test_hidden_metrics_exact():
    got = _run_hidden(_HIDDEN_SEEDS[2])
    assert got["metrics.json"] == _expected(_HIDDEN_SEEDS[2])["metrics.json"]


def _impl_test_hidden_payout_exact():
    got = _run_hidden(_HIDDEN_SEEDS[3])
    assert got["payout.csv"] == _expected(_HIDDEN_SEEDS[3])["payout.csv"]


def _impl_test_hidden_intervals_exact():
    got = _run_hidden(_HIDDEN_SEEDS[4])
    assert got["confidence_intervals.csv"] == _expected(_HIDDEN_SEEDS[4])["confidence_intervals.csv"]


def _impl_test_hidden_forfeiture_exact():
    got = _run_hidden(_HIDDEN_SEEDS[5])
    assert got["forfeited_shares.csv"] == _expected(_HIDDEN_SEEDS[5])["forfeited_shares.csv"]


def _impl_test_hidden_levy_exact():
    got = _run_hidden(_HIDDEN_SEEDS[6])
    assert got["levy_summary.json"] == _expected(_HIDDEN_SEEDS[6])["levy_summary.json"]


def _impl_test_hidden_manifest_exact():
    got = _run_hidden(_HIDDEN_SEEDS[7])
    assert got["manifest.json"] == _expected(_HIDDEN_SEEDS[7])["manifest.json"]


# --- negative test: distinct from artifact correctness. It fires only when the
# --- output directory contains undeclared files, which the instruction forbids.

def _impl_test_negative_copies_input_or_reference_tree():
    # INVERTED POLARITY: True means the prohibited extra output exists.
    declared = set(_expected()) | {"settle.py"}
    extras = [p for p in APP_OUT.rglob("*") if p.is_file() and p.relative_to(APP_OUT).as_posix() not in declared]
    assert extras


@criterion(description="population.csv is byte-exact for S1 canonicalization")
def test_population_membership_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_population_membership_exact)


@criterion(description="S3 running-baseline probabilities are exact")
def test_weights_running_baseline(workspace):
    _bind(workspace)
    return _pass(_impl_test_weights_running_baseline)


@criterion(description="S4 currency conversion and drift-adjusted ledger units are exact")
def test_weights_ledger_units(workspace):
    _bind(workspace)
    return _pass(_impl_test_weights_ledger_units)


@criterion(description="S5 frozen-stratum two-level rarity weights are exact")
def test_weights_rarity_weights(workspace):
    _bind(workspace)
    return _pass(_impl_test_weights_rarity_weights)


@criterion(description="S6 calibrated probabilities and inclusive decisions are exact")
def test_weights_calibration_decision(workspace):
    _bind(workspace)
    return _pass(_impl_test_weights_calibration_decision)


@criterion(description="S7 overall ratios and macro means are exact")
def test_metrics_overall_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_metrics_overall_exact)


@criterion(description="S7 per-stratum precision recall and F-beta are exact")
def test_metrics_strata_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_metrics_strata_exact)


@criterion(description="the nine detailed metric views are consistent with metrics and weights")
def test_per_stratum_metrics_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_per_stratum_metrics_exact)


@criterion(description="S8 rewarded forfeited and review-credit columns are exact")
def test_payout_s8_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_payout_s8_exact)


@criterion(description="S9 levy and floored-net columns are exact")
def test_payout_s9_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_payout_s9_exact)


@criterion(description="levy_summary.json is consistent with payout.csv")
def test_levy_summary_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_levy_summary_exact)


@criterion(description="the reusable program produces exact payout breakdown on an unseen corpus")
def test_payout_breakdown_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_payout_breakdown_exact)


@criterion(description="the reusable program produces exact payout ledger on an unseen corpus")
def test_payout_ledger_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_payout_ledger_exact)


@criterion(description="the reusable program produces exact net payout summary on an unseen corpus")
def test_net_payout_summary_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_net_payout_summary_exact)


@criterion(description="forfeited shares apportion payout forfeitures to exactly 10000 basis points")
def test_forfeited_shares_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_forfeited_shares_exact)


@criterion(description="confidence_intervals.csv is byte-exact for S8 Wilson and Kish intervals")
def test_confidence_intervals_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_confidence_intervals_exact)


@criterion(description="manifest digest matches the delivered four core files")
def test_manifest_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_manifest_exact)


@criterion(description="frame_counts.json is consistent with population and weights")
def test_frame_counts_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_frame_counts_exact)


@criterion(description="the reusable program produces the exact metrics stream on an unseen corpus")
def test_stratum_metrics_stream_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_stratum_metrics_stream_exact)


@criterion(description="label_distribution.json is byte-exact for S2 labels")
def test_label_distribution_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_label_distribution_exact)


@criterion(description="decision_distribution.json is consistent with weights.csv")
def test_decision_distribution_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_decision_distribution_exact)


@criterion(description="weight_diagnostics.json is consistent with weights.csv")
def test_weight_diagnostics_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_weight_diagnostics_exact)


@criterion(description="audit_summary.json is consistent with delivered core views")
def test_audit_summary_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_audit_summary_exact)


@criterion(description="overall_metrics.md is consistent with metrics.json")
def test_overall_metrics_md_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_overall_metrics_md_exact)


@criterion(description="reconciliation_report.md is consistent with delivered summaries")
def test_reconciliation_report_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_reconciliation_report_exact)


@criterion(description="rollup.xml is consistent with metrics.json")
def test_rollup_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_rollup_exact)


@criterion(description="the reusable program produces exact S1 population on an unseen corpus")
def test_hidden_population_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_hidden_population_exact)


@criterion(description="the reusable program produces exact S3 through S6 weights on an unseen corpus")
def test_hidden_weights_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_hidden_weights_exact)


@criterion(description="the reusable program produces exact S7 metrics on an unseen corpus")
def test_hidden_metrics_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_hidden_metrics_exact)


@criterion(description="the reusable program produces exact S8 and S9 payout on an unseen corpus")
def test_hidden_payout_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_hidden_payout_exact)


@criterion(description="the reusable program produces exact Kish Wilson intervals on an unseen corpus")
def test_hidden_intervals_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_hidden_intervals_exact)


@criterion(description="the reusable program produces exact largest-remainder forfeiture shares on an unseen corpus")
def test_hidden_forfeiture_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_hidden_forfeiture_exact)


@criterion(description="the reusable program produces exact levy and floor summary on an unseen corpus")
def test_hidden_levy_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_hidden_levy_exact)


@criterion(description="the reusable program produces the exact core-byte manifest on an unseen corpus")
def test_hidden_manifest_exact(workspace):
    _bind(workspace)
    return _pass(_impl_test_hidden_manifest_exact)


@criterion(description="the output directory contains an undeclared copied input or reference file")
def negative_copies_input_or_reference_tree(workspace):
    _bind(workspace)
    return _pass(_impl_test_negative_copies_input_or_reference_tree)


criteria.test_population_membership_exact(weight=5)
criteria.test_weights_running_baseline(weight=1)
criteria.test_weights_ledger_units(weight=5)
criteria.test_weights_rarity_weights(weight=5)
criteria.test_weights_calibration_decision(weight=5)
criteria.test_metrics_overall_exact(weight=5)
criteria.test_metrics_strata_exact(weight=3)
criteria.test_per_stratum_metrics_exact(weight=1)
criteria.test_payout_s8_exact(weight=5)
criteria.test_payout_s9_exact(weight=5)
criteria.test_levy_summary_exact(weight=1)
criteria.test_payout_breakdown_exact(weight=5)
criteria.test_payout_ledger_exact(weight=5)
criteria.test_net_payout_summary_exact(weight=5)
criteria.test_forfeited_shares_exact(weight=3)
criteria.test_confidence_intervals_exact(weight=3)
criteria.test_manifest_exact(weight=3)
criteria.test_frame_counts_exact(weight=1)
criteria.test_stratum_metrics_stream_exact(weight=5)
criteria.test_label_distribution_exact(weight=1)
criteria.test_decision_distribution_exact(weight=1)
criteria.test_weight_diagnostics_exact(weight=1)
criteria.test_audit_summary_exact(weight=1)
criteria.test_overall_metrics_md_exact(weight=1)
criteria.test_reconciliation_report_exact(weight=1)
criteria.test_rollup_exact(weight=1)
criteria.test_hidden_population_exact(weight=5)
criteria.test_hidden_weights_exact(weight=5)
criteria.test_hidden_metrics_exact(weight=5)
criteria.test_hidden_payout_exact(weight=5)
criteria.test_hidden_intervals_exact(weight=5)
criteria.test_hidden_forfeiture_exact(weight=5)
criteria.test_hidden_levy_exact(weight=5)
criteria.test_hidden_manifest_exact(weight=5)
criteria.negative_copies_input_or_reference_tree(weight=-5)


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("environment"))
