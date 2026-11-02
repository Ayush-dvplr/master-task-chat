"""Verifier for the R7 preference corpus release.

The corpus generator below is the same code that writes the shipped exports, so
the graded truth and the agent's inputs come from one source. Speed is gated by
repeated relative medians against a plain read-and-decode baseline; no absolute host threshold.
"""
from __future__ import annotations

import base64 as _b64, csv as _csvmod, hashlib as _hl, io as _io, json as _json
import os as _os, shutil as _shutil, statistics as _stats, subprocess as _sp
import re as _re, signal as _signal, sys as _sys, tempfile as _tf, threading as _threading, time as _time
from pathlib import Path

from rewardkit import criteria, criterion

SAMPLE_SEED = int("1669362440352324832")
CHALLENGE_SEED = int("5499941072847562503")
EVAL_SEED = int("3454627191418512675")
APP_ROOT = Path(_os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
PROGRAM = OUT_DIR / "build.py"
VISIBLE_SCALE = 1.0
HIDDEN_SCALE = 0.35
RUN_TIMEOUT = 600
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
# ===== CORPUS GENERATOR BEGIN =====


import argparse, calendar, datetime as _dt, hashlib, io, json, math, os, re


import sqlite3, struct, tempfile, time, unicodedata, zipfile, zlib


from decimal import ROUND_HALF_EVEN, Decimal


from fractions import Fraction




# ---- rng, time, rounding ----
import calendar
import datetime as _dt
import hashlib
import io
import json
import math
import os
import sqlite3
import struct
import tempfile
import time
import unicodedata
import zipfile
import zlib
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction

MASK64 = (1 << 64) - 1


class Rng:
    __slots__ = ("s",)

    def __init__(self, seed):
        self.s = seed & MASK64

    def u64(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & MASK64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return z ^ (z >> 31)

    def rand(self):
        return (self.u64() >> 11) * (1.0 / 9007199254740992.0)

    def below(self, n):
        return self.u64() % n

    def randint(self, a, b):
        return a + self.below(b - a + 1)

    def choice(self, seq):
        return seq[self.below(len(seq))]

    def chance(self, p):
        return self.rand() < p

    def shuffle(self, lst):
        for i in range(len(lst) - 1, 0, -1):
            j = self.below(i + 1)
            lst[i], lst[j] = lst[j], lst[i]
        return lst

    def weighted(self, pairs):
        total = sum(w for _, w in pairs)
        x = self.rand() * total
        for v, w in pairs:
            x -= w
            if x < 0:
                return v
        return pairs[-1][0]

    def hexid(self, n):
        return "".join("0123456789abcdef"[self.below(16)] for _ in range(n))


def derive(seed, tag):
    h = hashlib.blake2b(f"{seed}|{tag}".encode(), digest_size=8).digest()
    return Rng(int.from_bytes(h, "big"))


def T(y, m, d, h=0, mi=0, s=0):
    return calendar.timegm((y, m, d, h, mi, s, 0, 0, 0))


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def iso_week(t):
    return _dt.datetime.fromtimestamp(t, _dt.timezone.utc).isocalendar()[1]


def q6(fr):
    """Rational -> float quantized to 6 dp, half-even (the reporting rule)."""
    d = Decimal(fr.numerator) / Decimal(fr.denominator) if isinstance(fr, Fraction) else Decimal(str(fr))
    return float(d.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))


def q6n(fr):
    return None if fr is None else q6(fr)


def qd(fr, places):
    d = Decimal(fr.numerator) / Decimal(fr.denominator)
    return d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)

TZ_OFFSET = {"UTC": 0, "Europe/Berlin": 7200, "America/Chicago": -18000, "Asia/Kolkata": 19800,
             "America/Sao_Paulo": -10800, "Australia/Sydney": 36000, "Europe/London": 3600}

# The document whose header band shares a segment with its first base rule. The domain
# module sets this; left None the positional assignment simply treats every rule alike.
SEG_SHARE_DOC = None


# ---- homoglyph / word pools ----
HOMO = {"A": "\u0410", "C": "\u0421", "E": "\u0415", "O": "\u041e", "P": "\u0420", "J": "\u0408",
        "M": "\u041c", "T": "\u0422", "H": "\u041d", "K": "\u041a", "X": "\u0425", "B": "\u0412"}

# ---------------------------------------------------------------------------------
# canonical world
# ---------------------------------------------------------------------------------
SYL = ["ka", "lo", "mi", "ra", "te", "su", "no", "vi", "da", "pe", "zu", "ho", "ri", "an", "el", "or",
       "ta", "ne", "si", "bu", "ga", "fe", "ju", "ly"]
ACC = {"de": "\u00e4\u00f6\u00fc\u00df", "fr": "\u00e9\u00e8\u00ea\u00e7", "es": "\u00f1\u00e1\u00ed\u00f3",
       "pt": "\u00e3\u00f5\u00e7\u00e1", "sw": "", "id": "", "hi": "\u0101\u012b\u016b", "ja": "\u014d\u016b",
       "he": "", "ru": "\u0436\u0448\u044b\u043b"}


class World:
    pass


def _word(r, lang=None, n=None):
    n = n or r.randint(2, 4)
    w = "".join(r.choice(SYL) for _ in range(n))
    if lang and ACC.get(lang) and r.chance(0.75):
        pos = r.below(len(w))
        w = w[:pos] + r.choice(ACC[lang]) + w[pos + 1:]
    return w


def strip_marks(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_answer(s, grader):
    s = unicodedata.normalize("NFC", s).casefold()
    if grader == "g3":
        s = unicodedata.normalize("NFC", strip_marks(s))
    s = " ".join(s.split())
    return s.strip(" .,;:!?\"'")


# ---- container writers (stdlib only) ----
_ZDATE = (2025, 10, 3, 18, 0, 0)


def xesc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members:
            info = zipfile.ZipInfo(name, date_time=_ZDATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data if isinstance(data, bytes) else data.encode("utf-8"))
    return buf.getvalue()


def _col(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def xlsx_bytes(sheets):
    """sheets: list of (name, rows); a cell is str (inline string), int/float (number) or None."""
    wb_sheets, rels, ctypes = [], [], []
    members = []
    for i, (name, rows) in enumerate(sheets, 1):
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for ri, row in enumerate(rows, 1):
            cells = []
            for ci, v in enumerate(row):
                if v is None:
                    continue
                ref = f"{_col(ci)}{ri}"
                if isinstance(v, bool):
                    v = str(v).lower()
                if isinstance(v, (int, float)):
                    cells.append(f'<c r="{ref}"><v>{v!r}</v></c>' if isinstance(v, float) else f'<c r="{ref}"><v>{v}</v></c>')
                else:
                    sv = xesc(v).replace("\r", "&#13;")
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{sv}</t></is></c>')
            out.append(f'<row r="{ri}">' + "".join(cells) + "</row>")
        out.append("</sheetData></worksheet>")
        members.append((f"xl/worksheets/sheet{i}.xml", "".join(out)))
        wb_sheets.append(f'<sheet name="{xesc(name)}" sheetId="{i}" r:id="rId{i}"/>')
        rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
        ctypes.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    head = [
        ("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + "".join(ctypes) + "</Types>"),
        ("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'),
        ("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + "".join(wb_sheets) + "</sheets></workbook>"),
        ("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>"),
    ]
    return _zip(head + members)


def docx_bytes(blocks):
    """blocks: ("p", text) paragraphs or ("t", rows) tables (rows of str cells)."""
    body = []
    for kind, val in blocks:
        if kind == "p":
            body.append(f'<w:p><w:r><w:t xml:space="preserve">{xesc(val)}</w:t></w:r></w:p>')
        elif kind == "h0":
            pass
        elif kind == "h":
            body.append(f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t xml:space="preserve">{xesc(val)}</w:t></w:r></w:p>')
        else:
            trs = []
            for row in val:
                tcs = "".join(f'<w:tc><w:p><w:r><w:t xml:space="preserve">{xesc(c).replace(chr(13), "&#13;")}</w:t></w:r></w:p></w:tc>' for c in row)
                trs.append(f"<w:tr>{tcs}</w:tr>")
            body.append("<w:tbl>" + "".join(trs) + "</w:tbl><w:p/>")
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           + "".join(body) + "</w:body></w:document>")
    return _zip([
        ("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'),
        ("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'),
        ("word/document.xml", doc),
    ])


def _pdf_esc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_bytes(lines, per_page=62):
    """Plain text layer, Helvetica 7pt, one text line per table row; ASCII only."""
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]
    objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>", 3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"}
    kids = []
    nxt = 4
    for pg in pages:
        ops = ["BT", "/F1 7 Tf", "9 TL", "28 815 Td"]
        for ln in pg:
            ops.append(f"({_pdf_esc(ln)}) Tj T*")
        ops.append("ET")
        raw = zlib.compress("\n".join(ops).encode("latin-1"), 9)
        cid, pid = nxt, nxt + 1
        nxt += 2
        objs[cid] = b"<< /Length " + str(len(raw)).encode() + b" /Filter /FlateDecode >>\nstream\n" + raw + b"\nendstream"
        objs[pid] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {cid} 0 R >>".encode()
        kids.append(pid)
    objs[2] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offs = {}
    for n in sorted(objs):
        offs[n] = out.tell()
        out.write(f"{n} 0 obj\n".encode() + objs[n] + b"\nendobj\n")
    xref = out.tell()
    n = max(objs) + 1
    out.write(f"xref\n0 {n}\n0000000000 65535 f \n".encode())
    for i in range(1, n):
        out.write(f"{offs[i]:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


# --- parquet (thrift compact, PLAIN, uncompressed, REQUIRED columns) ---------------
def _uvar(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _zz(n):
    return _uvar((n << 1) ^ (n >> 63))


class _TC:
    def __init__(self):
        self.b = bytearray()
        self.last = [0]

    def fh(self, fid, t):
        d = fid - self.last[-1]
        if 0 < d <= 15:
            self.b.append((d << 4) | t)
        else:
            self.b.append(t)
            self.b += _zz(fid)
        self.last[-1] = fid

    def i32(self, fid, v):
        self.fh(fid, 5)
        self.b += _zz(v)

    def i64(self, fid, v):
        self.fh(fid, 6)
        self.b += _zz(v)

    def bin(self, fid, v):
        self.fh(fid, 8)
        v = v.encode() if isinstance(v, str) else v
        self.b += _uvar(len(v)) + v

    def begin(self, fid):
        self.fh(fid, 12)
        self.last.append(0)

    def end(self):
        self.b.append(0)
        self.last.pop()

    def lst(self, fid, etype, n):
        self.fh(fid, 9)
        self.b.append((n << 4) | etype if n < 15 else 0xF0 | etype)
        if n >= 15:
            self.b += _uvar(n)

    def lbegin(self):
        self.last.append(0)


def parquet_bytes(columns, row_groups, created_by="aurelis-export 4.1"):
    """columns: [(name, kind)] kind in int64|double|string; row_groups: list of list-of-row-tuples."""
    PT = {"int64": 2, "double": 5, "string": 6}
    out = bytearray(b"PAR1")
    rg_meta = []
    for rows in row_groups:
        chunks = []
        for ci, (name, kind) in enumerate(columns):
            vals = [r[ci] for r in rows]
            if kind == "int64":
                data = b"".join(struct.pack("<q", v) for v in vals)
            elif kind == "double":
                data = b"".join(struct.pack("<d", v) for v in vals)
            else:
                data = b"".join(struct.pack("<I", len(x.encode())) + x.encode() for x in vals)
            ph = _TC()
            ph.i32(1, 0)
            ph.i32(2, len(data))
            ph.i32(3, len(data))
            ph.begin(5)
            ph.i32(1, len(vals))
            ph.i32(2, 0)
            ph.i32(3, 3)
            ph.i32(4, 3)
            ph.end()
            ph.b.append(0)
            off = len(out)
            out += ph.b + data
            chunks.append((name, kind, off, len(ph.b) + len(data), len(vals)))
        rg_meta.append((chunks, len(rows)))
    fm = _TC()
    fm.i32(1, 1)
    fm.lst(2, 12, len(columns) + 1)
    fm.lbegin()
    fm.bin(4, "schema")
    fm.i32(5, len(columns))
    fm.end()
    for name, kind in columns:
        fm.lbegin()
        fm.i32(1, PT[kind])
        fm.i32(3, 0)
        fm.bin(4, name)
        if kind == "string":
            fm.i32(6, 0)
        fm.end()
    fm.i64(3, sum(n for _, n in rg_meta))
    fm.lst(4, 12, len(rg_meta))
    for chunks, nrows in rg_meta:
        fm.lbegin()
        fm.lst(1, 12, len(chunks))
        for name, kind, off, size, nv in chunks:
            fm.lbegin()
            fm.i64(2, off)
            fm.begin(3)
            fm.i32(1, PT[kind])
            fm.lst(2, 5, 1)
            fm.b += _zz(0)
            fm.lst(3, 8, 1)
            fm.b += _uvar(len(name.encode())) + name.encode()
            fm.i32(4, 0)
            fm.i64(5, nv)
            fm.i64(6, size)
            fm.i64(7, size)
            fm.i64(9, off)
            fm.end()
            fm.end()
        fm.i64(2, sum(c[3] for c in chunks))
        fm.i64(3, nrows)
        fm.end()
    fm.bin(6, created_by)
    fm.b.append(0)
    out += fm.b + struct.pack("<I", len(fm.b)) + b"PAR1"
    return bytes(out)


def sqlite_bytes(statements):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    try:
        con = sqlite3.connect(path)
        con.execute("PRAGMA page_size=4096")
        con.execute("PRAGMA journal_mode=OFF")
        for sql, rows in statements:
            if rows is None:
                con.execute(sql)
            else:
                con.executemany(sql, rows)
        con.commit()
        con.execute("VACUUM")
        con.close()
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def mbox_bytes(messages):
    out = []
    for frm_line, headers, body in messages:
        out.append(frm_line)
        for k, v in headers:
            out.append(f"{k}: {v}")
        out.append("")
        for ln in body.split("\n"):
            out.append(">" + ln if ln.startswith("From ") else ln)
        out.append("")
    return ("\n".join(out) + "\n").encode("utf-8")

# ---------------------------------------------------------------------------------
# row plan for the result-bearing sources


# ---- trap framework ----
HOMO_L = {"o": "\u043e", "e": "\u0435", "a": "\u0430", "c": "\u0441", "p": "\u0440", "x": "\u0445"}
FAM_NAME = {"T1": "near-duplicate keys", "T2": "unit/scale", "T3": "time zone/epoch", "T4": "locale numerics",
            "T5": "sentinels", "T6": "voided/reversed", "T7": "superseded", "T8": "header drift",
            "T9": "embedded delimiters", "T10": "encoding", "T11": "boundaries", "T12": "rounding",
            "T13": "referential breaks", "T14": "scope in prose", "T15": "statistical bait", "T16": "decoy agreement",
            "T17": "cross-file conditional", "T18": "oscillation pair", "T19": "false equilibrium",
            "T20": "over-correction bait", "T21": "field-scoped precedence", "T22": "deferred effect"}


class FB:
    _W = None

    def __init__(self, name, decoy=False, tests=()):
        self.name, self.decoy = name, decoy
        self.rules = {}
        self.rows = []
        self.tests = list(tests)
        self.prose = []
        self.render = None
        self.anchor_note = None

    def R(self, code, family, desc, doc, via, mode="row", ht=False, bait=False, cond=False,
          fields=None, via_rules=(), direction=None, dominant=False, excl=()):
        assert code not in self.rules, (self.name, code)
        self.rules[code] = {"code": code, "family": family, "desc": desc, "doc": doc, "via": list(via),
                            "mode": mode, "ht": ht, "bait": bait, "cond": cond, "fields": fields,
                            "via_rules": list(via_rules), "direction": direction, "dominant": dominant,
                            "excl": set(excl)}

    def add(self, f, rules=(), kind=None, **ctx):
        row = {"f": f, "r": [x for x in rules if x], "k": kind, "c": ctx}
        self.rows.append(row)
        return row


def arrange(fb, rng, density=None):
    """Order rows into bands and spread line-level rules so the density targets hold."""
    rules = fb.rules
    for row in fb.rows:
        for c in row["r"]:
            assert c in rules, (fb.name, c)
    n = len(fb.rows)
    used0 = {c for row in fb.rows for c in row["r"]}
    for c in [c for c, ru in rules.items() if ru["mode"] in ("row", "ctx") and c not in used0]:
        del rules[c]
    line_rules = [c for c, r in rules.items() if r["mode"] == "line"]
    tgt = density or (0.84 if fb.decoy else 0.75)
    head_n = min(2000, n // 5)
    limit = max(2, int(len(rules) * 0.24))
    base_ht = {c for c, r in rules.items() if r["ht"]}

    n_anchor = sum(1 for row in fb.rows if row["k"] == "anchor")
    need_el = max(0, head_n - min(n_anchor // 2, int(0.35 * head_n)))

    def promote(ht, pool_rows):
        ht = set(ht)
        sets = {}
        for row in pool_rows:
            if row["k"] == "anchor":
                continue
            k_ = frozenset(row["r"])
            sets[k_] = sets.get(k_, 0) + 1
        while sum(v for k_, v in sets.items() if k_ <= ht) < need_el and len(ht) < limit:
            gain = {}
            for k_, v in sets.items():
                rest = k_ - ht
                if rest:
                    for c in rest:
                        gain[c] = gain.get(c, 0.0) + v / (len(rest) ** 2)
            if not gain:
                break
            ht.add(max(sorted(gain), key=lambda c: gain[c]))
        return ht

    half = n // 2
    ht_head = promote(base_ht, fb.rows[:half] if n > 4 * head_n else fb.rows)
    ht_tail = promote(base_ht, fb.rows[half:] if n > 4 * head_n else fb.rows)

    def take(rows, ht, k, from_end):
        anc = [r for r in rows if r["k"] == "anchor"]
        anc = anc[len(anc) - min(len(anc) // 2, int(0.35 * k)):] if from_end else anc[:min(len(anc) // 2, int(0.35 * k))]
        aid = {id(r) for r in anc}
        el = [r for r in rows if (set(r["r"]) <= ht and r["k"] != "anchor") or id(r) in aid]
        if len(el) < k:
            ids = {id(r) for r in el}
            pool_ = [r for r in rows if id(r) not in ids]
            freq_ = {}
            for r in pool_:
                k_ = frozenset(set(r["r"]) - ht)
                freq_[k_] = freq_.get(k_, 0) + 1
            extra = sorted(pool_, key=lambda r: (len(set(r["r"]) - ht), -freq_[frozenset(set(r["r"]) - ht)], sorted(set(r["r"]) - ht)))
            el_ids = ids | {id(r) for r in extra[:k - len(el)]}
            el = [r for r in rows if id(r) in el_ids]
        return el[len(el) - k:] if from_end else el[:k]

    head = take(fb.rows, ht_head, head_n, False)
    hid = {id(r) for r in head}
    tail = take([r for r in fb.rows if id(r) not in hid], ht_tail, head_n, True)
    tid = {id(r) for r in tail}
    middle = [r for r in fb.rows if id(r) not in hid and id(r) not in tid]
    def spread(seg):
        anchors = [r for r in seg if r["k"] == "anchor"]
        if not anchors:
            return seg
        rest = [r for r in seg if r["k"] != "anchor"]
        step = len(rest) / (len(anchors) + 1)
        out_ = []
        ai = 0
        for i, r in enumerate(rest):
            while ai < len(anchors) and (ai + 1) * step <= i:
                out_.append(anchors[ai])
                ai += 1
            out_.append(r)
        return out_ + anchors[ai:]
    ordered = spread(head) + spread(middle) + spread(tail)
    usage = {c: 0 for c in rules}
    for row in ordered:
        for c in row["r"]:
            usage[c] += 1

    def applicable(row, allowed):
        out = []
        for c in allowed:
            fl = rules[c]["fields"]
            if fl and all(row["f"].get(x) not in (None, "") for x in fl) and c not in row["r"]:
                if any(c in rules[o]["excl"] or o in rules[c]["excl"] for o in row["r"]):
                    continue
                out.append(c)
        return out

    def pick(row, allowed, bait=None):
        cands = applicable(row, allowed)
        if bait is not None:
            cands = [c for c in cands if rules[c]["bait"] == bait]
        if not cands:
            return False
        cands.sort(key=lambda c: (usage[c], c))
        c = cands[0]
        row["r"].append(c)
        usage[c] += 1
        return True

    B = (n + 999) // 1000
    for b in range(B):
        band = ordered[b * 1000:(b + 1) * 1000]
        if b * 1000 < head_n:
            allowed = [c for c in line_rules if c in ht_head]
        elif (b + 1) * 1000 > n - head_n:
            allowed = [c for c in line_rules if c in ht_tail]
        else:
            allowed = line_rules
        trap = [r for r in band if r["r"]]
        need = int(math.ceil(tgt * len(band))) - len(trap)
        nb = int(0.14 * max(len(trap), tgt * len(band))) - sum(1 for r in trap if any(rules[c]["bait"] for c in r["r"]))
        cand = [r for r in band if r["k"] != "anchor"]
        plain = [r for r in cand if not r["r"]]
        rng.shuffle(plain)
        if nb > 0:
            others = [r for r in cand if r["r"] and not any(rules[c]["bait"] for c in r["r"])]
            rng.shuffle(others)
            for row in plain + others:
                if nb <= 0:
                    break
                was_plain = not row["r"]
                if pick(row, allowed, bait=True):
                    nb -= 1
                    if was_plain:
                        need -= 1
        for row in plain:
            if need <= 0:
                break
            if row["r"]:
                continue
            if pick(row, allowed, bait=False) or pick(row, allowed):
                need -= 1
        trap = [r for r in band if r["r"]]
        stacked = sum(1 for r in trap if len(r["r"]) >= 2)
        want = int(math.ceil(0.40 * len(trap))) - stacked
        singles = [r for r in trap if len(r["r"]) == 1]
        rng.shuffle(singles)
        for row in singles:
            if want <= 0:
                break
            if pick(row, allowed, bait=False):
                want -= 1
    # every declared line rule must actually occur: top up rare ones in the middle bands
    mid = [r for r in ordered[head_n:n - head_n] if r["k"] != "anchor"]
    m = max(15, int(0.004 * n))
    for c in sorted(line_rules):
        if usage[c] >= m:
            continue
        cands = [r for r in mid if c in applicable(r, [c])]
        rng.shuffle(cands)
        for row in cands[:m - usage[c]]:
            row["r"].append(c)
            usage[c] += 1
    for c in [c for c in line_rules if usage[c] == 0]:
        del rules[c]
    for row in ordered:
        bait = any(rules[c]["bait"] for c in row["r"])
        row["k"] = "anchor" if row["k"] == "anchor" else ("bait" if bait else ("trap" if row["r"] else "plain"))
    fb.rows = ordered
    fb.ht_head, fb.ht_tail = ht_head, ht_tail
    return fb


# ---- value helpers ----
def v_id(s, rules, tag):
    if tag + "_CASE" in rules:
        s = s.lower() if s[:1].isupper() else s.upper()
    if tag + "_PAD" in rules:
        head, _, num = s.rpartition("-") if "-" in s else (s[0], "", s[1:])
        if "-" in s:
            s = head + "-" + (num.lstrip("0") or "0")
        else:
            s = s[0] + (s[1:].lstrip("0") or "0")
    if tag + "_HOMO" in rules:
        for i, ch in enumerate(s):
            if ch in HOMO:
                s = s[:i] + HOMO[ch] + s[i + 1:]
                break
            if ch in HOMO_L:
                s = s[:i] + HOMO_L[ch] + s[i + 1:]
                break
    if tag + "_FW" in rules:
        s = "".join(chr(0xFF10 + int(ch)) if ch.isdigit() else ch for ch in s)
    if tag + "_WS" in rules:
        s = "\u00a0" + s + " "
    return s


def v_rev(rev, rules):
    if "REV_TXT" in rules:
        return f"r{rev}"
    return f"{rev:02d}" if "REV_PAD" in rules else str(rev)


def v_tw(s, rules):
    return s + "  " if "TRAIL_WS" in rules else s


def v_lb(s, rules):
    return s + "\r\n" if "LINEBREAK" in rules else s


def kit_tab(fb, rev=True, tw=True, lb=False, doc=None):
    doc = doc or (SC if fb.name != SC else POL)
    via = [doc, POL if doc != POL else SC]
    if rev:
        fb.R("REV_TXT", "T4", f"Revision values in {fb.name} can be written with an r prefix (r3 means 3).", doc, via, mode="line", fields=["revf"])
        fb.R("REV_PAD", "T4", f"Revision values in {fb.name} can be zero-padded (03 means 3).", doc, via, mode="line", fields=["revf"], excl=("REV_TXT",))
    if tw:
        fb.R("TRAIL_WS", "T9", f"Cells of {fb.name} can carry trailing spaces; strip them.", doc, via, mode="line", fields=["twf"])
    if lb:
        fb.R("LINEBREAK", "T10", f"Text cells inside {fb.name} can end with a carriage return and line feed; strip them.", doc, via, mode="line", fields=["lbf"])


def group3(intpart, sep):
    out = []
    while len(intpart) > 3:
        out.insert(0, intpart[-3:])
        intpart = intpart[:-3]
    out.insert(0, intpart)
    return sep.join(out)


def v_num(d, dp, locale="en_US", group=True, paren=False):
    neg = d < 0
    s = format(abs(d).quantize(Decimal(1).scaleb(-dp)) if dp else abs(d).quantize(Decimal(1)), "f")
    ip, _, fp = s.partition(".")
    if locale == "en_IN" and group and len(ip) > 3:
        head, last3 = ip[:-3], ip[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        ip = ",".join(parts) + "," + last3
    elif group:
        ip = group3(ip, {"en_US": ",", "de_DE": ".", "fr_FR": " ", "en_IN": ","}[locale])
    dec = "," if locale in ("de_DE", "fr_FR") else "."
    s = ip + (dec + fp if fp else "")
    if neg:
        s = "(" + s + ")" if paren else "-" + s
    return s


def v_excess(d, dp, rng):
    """d with two extra digits whose half-even rounding back to dp returns d."""
    q = Decimal(1).scaleb(-dp)
    while True:
        extra = Decimal(rng.randint(-49, 50)).scaleb(-dp - 2)
        if rng.chance(0.25):
            extra = Decimal(50).scaleb(-dp - 2) * (1 if rng.chance(0.5) else -1)
        cand = d + extra
        if cand.quantize(q, rounding=ROUND_HALF_EVEN) == d and cand >= 0:
            return format(cand, "f")


def local_str(t, tz, offset_ms=0, fmt="%Y-%m-%d %H:%M:%S", ms=True):
    tt = t * 1000 + offset_ms + TZ_OFFSET[tz] * 1000
    s = time.strftime(fmt, time.gmtime(tt // 1000))
    return s + (f".{tt % 1000:03d}" if ms else "")


def excel_serial(t):
    """Days since 1899-12-30 (the convention that absorbs the 1900 leap-year bug), as a float."""
    return round((t - T(1899, 12, 30)) / 86400.0, 6)


def rfc2822(t, tz):
    off = TZ_OFFSET[tz]
    tt = time.gmtime(t + off)
    sign = "+" if off >= 0 else "-"
    return time.strftime("%a, %d %b %Y %H:%M:%S ", tt) + f"{sign}{abs(off) // 3600:02d}{(abs(off) % 3600) // 60:02d}"

# ---------------------------------------------------------------------------------
# the eight standing documents: policy, conventions, controls, precedence,
# errata, minutes, metric definitions, methodology
# ---------------------------------------------------------------------------------
POL, SC = "corpus_policy.md", "source_conventions.md"
CT, FP = "control_totals.html", "field_precedence.html"
ER, RM = "errata_register.docx", "review_minutes.docx"
MD, MA = "metric_definitions.pdf", "methodology_appendix.pdf"
DOC_FMT = {POL: "md", SC: "md", CT: "html", FP: "html", ER: "docx", RM: "docx", MD: "pdf", MA: "pdf"}


# ---- csv writer ----
def csv_bytes(header_rows, bom=False, delim=","):
    import csv as _csv
    buf = io.StringIO()
    w = _csv.writer(buf, delimiter=delim, lineterminator="\n")
    for row in header_rows:
        w.writerow(row)
    data = buf.getvalue().encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if bom else data


# ---- table renderer ----
def tab_render(fb, header_a, header_b, cell_fn, delim, bom=False, enc_rule=None):
    import csv as _csv
    buf = io.StringIO()
    w = _csv.writer(buf, delimiter=delim, lineterminator="\n")
    w.writerow(header_a)
    cur = "A"
    latin_lines = []
    for row in fb.rows:
        rules = row["r"]
        lay = "B" if "HDR" in rules else "A"
        if lay != cur:
            w.writerow(header_b if lay == "B" else header_a)
            cur = lay
        cells = cell_fn(row, lay)
        w.writerow(cells)
    data = buf.getvalue()
    if enc_rule:
        outb = bytearray()
        marks = {id(row) for row in fb.rows if enc_rule in row["r"]}
        lines = data.split("\n")
        # re-render line by line to know which lines are latin-1: rows map 1:1 after headers
        idx = 0
        rows_iter = iter(fb.rows)
        for ln in lines[:-1]:
            if ln.split(delim)[0] in (header_a[0], header_b[0]) and ln.startswith(header_a[0]):
                outb += ln.encode("utf-8") + b"\n"
                continue
            row = next(rows_iter)
            if id(row) in marks:
                try:
                    outb += ln.encode("latin-1") + b"\n"
                    continue
                except UnicodeEncodeError:
                    pass
            outb += ln.encode("utf-8") + b"\n"
        return (b"\xef\xbb\xbf" if bom else b"") + bytes(outb)
    return (b"\xef\xbb\xbf" if bom else b"") + data.encode("utf-8")


# ---- markdown table ----
def md_table(header, rows):
    L = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        L.append("| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |")
    return L


# ---- document renderer ----
def _ascii(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def render_doc(fb, prose, statements, fmt):
    title, ha, hb = fb.table
    blocks = list(prose)
    if statements:
        blocks.append(("h", "Per-source notes"))
    for src in sorted(statements):
        blocks.append(("p", f"{src}:"))
        for s_ in statements[src]:
            blocks.append(("li", s_))
    # table segments
    segs = []
    cur, buf = "A", []
    for row in fb.rows:
        lay = "B" if ("HDR" in row["r"] or "BASE1" in row["r"]) and hb else "A"
        if lay != cur and buf:
            segs.append((cur, buf))
            buf = []
        cur = lay
        cells = list(fb.cells(row, lay))
        if "CELLQ" in row["r"] and len(cells) > 1:
            cells[1] = '"' + cells[1] + '"'
        if "NBSPC" in row["r"]:
            cells[0] = cells[0] + "\u00a0"
        buf.append((cells, "SPLITROW" in row["r"]) if fmt == "pdf" else cells)
    if buf:
        segs.append((cur, buf))
    if fmt == "md":
        L = []
        for kind, val in blocks:
            if kind == "h":
                L.append(("# " if not L else "## ") + val)
            elif kind == "p":
                L.append("")
                L.append(val)
            elif kind == "li":
                L.append("- " + val)
            elif kind == "t":
                L.append("")
                L += md_table(val[0], val[1:])
        if segs:
            L.append("")
            L.append("## " + title)
        for lay, rows in segs:
            L.append("")
            L += md_table(ha if lay == "A" else hb, rows)
        return ("\n".join(L) + "\n").encode("utf-8")
    if fmt == "html":
        L = ["<!DOCTYPE html>", "<html><head><meta charset=\"utf-8\"><title>" + xesc(fb.name) + "</title></head><body>"]
        inlist = False
        for kind, val in blocks:
            if kind != "li" and inlist:
                L.append("</ul>")
                inlist = False
            if kind == "h":
                L.append(f"<h2>{xesc(val)}</h2>")
            elif kind == "p":
                L.append(f"<p>{xesc(val)}</p>")
            elif kind == "li":
                if not inlist:
                    L.append("<ul>")
                    inlist = True
                L.append(f"<li>{xesc(val)}</li>")
            elif kind == "t":
                L.append("<table>")
                L.append("<tr>" + "".join(f"<th>{xesc(c)}</th>" for c in val[0]) + "</tr>")
                for row in val[1:]:
                    L.append("<tr>" + "".join(f"<td>{xesc(c)}</td>" for c in row) + "</tr>")
                L.append("</table>")
        if inlist:
            L.append("</ul>")
        if segs:
            L.append(f"<h2>{xesc(title)}</h2>")
        for lay, rows in segs:
            L.append('<table class="data">')
            L.append("<tr>" + "".join(f"<th>{c}</th>" for c in (ha if lay == "A" else hb)) + "</tr>")
            for row in rows:
                L.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
            L.append("</table>")
        L.append("</body></html>")
        return ("\n".join(L) + "\n").encode("utf-8")
    if fmt == "docx":
        out = []
        for kind, val in blocks:
            if kind == "li":
                out.append(("p", "\u2022 " if False else "* " + val))
            elif kind == "t":
                out.append(("t", val))
            else:
                out.append((kind, val))
        if segs:
            out.append(("h", title))
        for lay, rows in segs:
            out.append(("t", [ha if lay == "A" else hb] + rows))
        return docx_bytes(out)
    if fmt == "pdf":
        import textwrap as _tw
        L = []
        for kind, val in blocks:
            if kind == "t":
                for row in val:
                    L.append(" | ".join(_ascii(str(c)) for c in row))
                continue
            text = _ascii(val)
            pre = "== " if kind == "h" else ("* " if kind == "li" else "")
            for i, ln in enumerate(_tw.wrap(text, 160) or [""]):
                L.append((pre if i == 0 else "  ") + ln)
        if segs:
            L.append("== " + title)
        for lay, rows in segs:
            L.append("TABLE " + " | ".join(ha if lay == "A" else hb))
            for row, split in rows:
                cells = [_ascii(str(c)) for c in row]
                if split:
                    L.append(" | ".join(cells[:2]) + " \\")
                    L.append("  " + " | ".join(cells[2:]))
                else:
                    L.append(" | ".join(cells))
        return pdf_bytes(L)
    raise ValueError(fmt)

# ---------------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------------


# ---- positional rule assignment ----
def assign_pos(fb, rng):
    pos_rules = sorted((c for c, ru in fb.rules.items() if ru["mode"] == "pos"), key=lambda c: (c != "HDR", c))
    if not pos_rules:
        return
    n = len(fb.rows)
    head_n = min(2000, n // 5)
    lo, hi = head_n, n - head_n
    fb.rg_sec = []
    seg_of = {}
    for c in pos_rules:
        if SEG_SHARE_DOC is not None and fb.name == SEG_SHARE_DOC and c == "BASE1" and "HDR" in seg_of:
            seg_of[c] = seg_of["HDR"]
            continue
        if c == "RG_SEC":
            groups = [g for g in range(n // 1000 + 1) if g * 1000 >= lo and (g + 1) * 1000 <= hi]
            k = 1 if len(groups) < 6 else 2
            chosen = sorted(groups[i] for i in sorted({rng.below(len(groups)) for _ in range(k)}))
            fb.rg_sec = chosen
            seg_of[c] = [range(g * 1000, (g + 1) * 1000) for g in chosen]
            continue
        ln = max(300, int(0.08 * n))
        st = lo + rng.below(max(1, hi - lo - ln))
        seg_of[c] = [range(st, min(hi, st + ln))]
    for c, segs in seg_of.items():
        ex = fb.rules[c]["excl"]
        for sg in segs:
            for i in sg:
                row = fb.rows[i]
                if row["k"] == "anchor":
                    continue
                row["r"] = [x for x in row["r"] if x not in ex] + [c]
    for row in fb.rows:
        if row["k"] == "anchor":
            continue
        bait = any(fb.rules[c]["bait"] for c in row["r"])
        row["k"] = "bait" if bait else ("trap" if row["r"] else "plain")


from fractions import Fraction


# ---------------------------------------------------------------------------------
# calendar
# ---------------------------------------------------------------------------------
WINDOW_START = T(2025, 7, 1)
WINDOW_END = T(2025, 10, 1)
FREEZE = T(2025, 10, 3, 18, 0, 0)
WEEKS = list(range(27, 41))

# ---------------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------------
VENDORS = ["calder", "northwind", "orbit", "tessel"]
VENDOR_CODE = {"calder": "CD", "northwind": "NW", "orbit": "OB", "tessel": "TS"}
POLICIES = ["r6-prod", "r7-blend", "r7-dpo-a", "r7-dpo-b", "r7-rm-probe", "r7-sft"]
POLICY_STRENGTH = {"r6-prod": 50, "r7-blend": 62, "r7-dpo-a": 71, "r7-dpo-b": 68,
                   "r7-rm-probe": 44, "r7-sft": 57}
SOURCES = ["coding", "dialogue", "multilingual", "reasoning", "safety", "summarization"]
DOMAINS = ["everyday", "finance", "health", "law", "science", "tech"]
LOCALES = ["de_DE", "en_IN", "en_US", "es_ES", "fr_FR", "ja_JP"]
DIFFICULTY = ["easy", "hard", "medium"]
RISK = ["elevated", "standard", "sensitive"]
CHOICES = ["both_bad", "left", "right", "tie"]
WORKSTATIONS = 420

# exclusion reasons, in the documented order of application
PROMPT_REASONS = ["retired", "opted_out", "contaminated", "duplicate", "over_length", "no_resolved_pair"]
VERDICT_REASONS = ["annotator_gated", "outside_window", "freeze_window", "stale_amendment",
                   "unbalanced_biased", "voided"]


class World:
    pass


def _scaled(n, scale):
    return max(1, int(round(n * scale)))


# ---------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------
def build_world(seed, scale=1.0):
    W = World()
    W.seed, W.scale = seed, scale
    r = derive(seed, "world")

    n_fam = _scaled(1600, scale)
    n_prompt = _scaled(12000, scale)
    n_ann = _scaled(240, scale)

    # --- annotators -------------------------------------------------------------
    # P(names the stronger completion | pair judged separable) = skill;
    # P(judged inseparable) = p_tie; left_pull shifts choice toward the shown-left side.
    W.annotators = {}
    for i in range(1, n_ann + 1):
        a = f"ANN-{i:04d}"
        weak = r.chance(0.28)
        W.annotators[a] = {
            "id": a,
            "vendor": VENDORS[(i - 1) % len(VENDORS)],
            "cohort": r.choice(["c1", "c2", "c3"]),
            "start_week": r.choice(WEEKS[:6]),
            "senior": r.chance(0.08),
            "skill": (r.randint(45, 70) if weak else r.randint(84, 97)) / 100.0,
            "left_pull": (r.randint(14, 32) if r.chance(0.11) else r.randint(0, 5)) / 100.0,
            "p_tie": r.randint(6, 14) / 100.0,
        }
    W.ann_ids = sorted(W.annotators)
    W.seniors = [a for a in W.ann_ids if W.annotators[a]["senior"]]

    # --- families and prompts ---------------------------------------------------
    W.families = {}
    for i in range(1, n_fam + 1):
        W.families[f"PF-{i:04d}"] = {"id": f"PF-{i:04d}", "domain": r.choice(DOMAINS)}
    W.fam_ids = sorted(W.families)

    W.prompts = {}
    for i in range(1, n_prompt + 1):
        p = f"PRM-{i:05d}"
        fam = W.fam_ids[r.below(len(W.fam_ids))]
        reg = WINDOW_START + r.below(WINDOW_END - WINDOW_START)
        # effective registration can trail the recorded one: the canonical-member rule uses it
        eff = reg + (r.below(9) * 86400 if r.chance(0.22) else 0)
        W.prompts[p] = {
            "id": p, "family": fam, "domain": W.families[fam]["domain"],
            "locale": r.choice(LOCALES), "difficulty": r.choice(DIFFICULTY),
            "risk": r.choice(RISK),
            "source": r.weighted([("coding", 24), ("dialogue", 32), ("multilingual", 3),
                                  ("reasoning", 20), ("safety", 7), ("summarization", 14)]),
            "registered_at": reg, "effective_at": eff,
            "tokens": r.randint(24, 900),
            "retired": r.chance(0.015),
            "opted_out": r.chance(0.012),
        }
    W.prompt_ids = sorted(W.prompts)
    precedence_prompt = W.prompt_ids[0]
    W.prompts[precedence_prompt]["retired"] = True
    W.prompts[precedence_prompt]["opted_out"] = True

    # --- near-duplicate clusters ------------------------------------------------
    # a cluster's canonical member is the earliest EFFECTIVE registration, ties by id
    W.clusters = {}
    W.cluster_of = {}
    pool = [p for p in W.prompt_ids if r.chance(0.17)]
    ci = 0
    i = 0
    while i < len(pool) - 1:
        k = 2 if r.chance(0.72) else 3
        members = pool[i:i + k]
        i += k
        if len(members) < 2:
            break
        ci += 1
        cid = f"DUP-{ci:04d}"
        W.clusters[cid] = sorted(members)
        for m in members:
            W.cluster_of[m] = cid
    W.cluster_ids = sorted(W.clusters)
    W.canonical = {}
    for cid in W.cluster_ids:
        members = W.clusters[cid]
        W.canonical[cid] = min(members, key=lambda p: (W.prompts[p]["effective_at"], p))

    # --- contamination screening ------------------------------------------------
    # Every screened prompt/suite pair is registered with its similarity. The two
    # documented thresholds then decide: at or above HARD the prompt is removed
    # outright, at or above SOFT its whole family is barred from train.
    W.eval_suites = ["aegis-safety", "hx-reason", "lexio-qa", "mmlu-mirror",
                     "polyglot-x", "rubric-chat", "swe-probe", "tally-math"]
    W.overlap_families = {f for f in W.fam_ids if r.chance(0.045)}
    W.contam_screen = []
    for p in W.prompt_ids:
        hot = W.prompts[p]["family"] in W.overlap_families
        for s in W.eval_suites:
            if not r.chance(0.16):
                continue
            sim = r.randint(74, 99) if hot else r.randint(8, 73)
            W.contam_screen.append({"prompt": p, "suite": s, "similarity": sim})
    W.contam_screen.sort(key=lambda x: (x["prompt"], x["suite"]))
    W.params_contam = {"hard": 95, "soft": 80}
    best = {}
    for e in W.contam_screen:
        if e["similarity"] > best.get(e["prompt"], 0):
            best[e["prompt"]] = e["similarity"]
    W.contaminated = {p for p, v in best.items() if v >= W.params_contam["hard"]}
    W.soft_contaminated = {p for p, v in best.items()
                           if W.params_contam["soft"] <= v < W.params_contam["hard"]}
    W.soft_contaminated_families = {W.prompts[p]["family"] for p in W.soft_contaminated}

    # --- completions ------------------------------------------------------------
    W.completions = {}
    W.by_prompt = {}
    ck = 0
    for p in W.prompt_ids:
        k = r.weighted([(1, 70), (3, 30)])
        pols = sorted(POLICIES, key=lambda _: r.u64())[:k]
        ids = []
        for pol in pols:
            ck += 1
            c = f"CMP-{ck:06d}"
            W.completions[c] = {
                "id": c, "prompt": p, "policy": pol,
                "tokens": r.randint(16, 620),
                "created_at": W.prompts[p]["registered_at"] + r.below(5 * 86400),
                "merit": POLICY_STRENGTH[pol] + r.randint(-18, 18),
            }
            ids.append(c)
        W.by_prompt[p] = ids
    W.completion_ids = sorted(W.completions)

    # --- amendments: a completion revised after some verdicts were cast ----------
    W.amendments = {}
    for c in W.completion_ids:
        if r.chance(0.055):
            W.amendments[c] = W.completions[c]["created_at"] + r.randint(3, 46) * 86400

    # --- comparisons ------------------------------------------------------------
    # a share of comparisons are issued in both presentation orders: those are the
    # balanced pairs the position-bias estimate is restricted to
    W.comparisons = {}
    W.balanced = set()
    mk = 0
    for p in W.prompt_ids:
        ids = W.by_prompt[p]
        if len(ids) < 2:
            continue
        npair = 2 if len(ids) == 2 else r.weighted([(2, 30), (3, 42), (4, 28)])
        seen = set()
        for _ in range(npair * 3):
            if len(seen) >= npair:
                break
            a, b = ids[r.below(len(ids))], ids[r.below(len(ids))]
            if a == b or (a, b) in seen or (b, a) in seen:
                continue
            seen.add((a, b))
            mk += 1
            cid = f"CMR-{mk:06d}"
            W.comparisons[cid] = {
                "id": cid, "prompt": p, "left": a, "right": b, "order": "ab",
                "batch": f"B{(mk % 600) + 1:04d}", "mirror": None,
            }
            if r.chance(0.30):
                mk += 1
                mid = f"CMR-{mk:06d}"
                W.comparisons[mid] = {
                    "id": mid, "prompt": p, "left": b, "right": a, "order": "ba",
                    "batch": f"B{(mk % 600) + 1:04d}", "mirror": cid,
                }
                W.comparisons[cid]["mirror"] = mid
                W.balanced.add(cid)
                W.balanced.add(mid)
    W.comparison_ids = sorted(W.comparisons)

    # --- gold set ---------------------------------------------------------------
    # gold answers name a COMPLETION, never a side: the side must be resolved
    # through each comparison's own presentation order
    W.truth_side = {}
    for cid in W.comparison_ids:
        cm = W.comparisons[cid]
        ml, mr = W.completions[cm["left"]]["merit"], W.completions[cm["right"]]["merit"]
        W.truth_side[cid] = "tie" if ml == mr else ("left" if ml > mr else "right")

    W.gold = {}
    for cid in W.comparison_ids:
        if W.truth_side[cid] != "tie" and r.chance(0.11):
            cm = W.comparisons[cid]
            W.gold[cid] = cm["left"] if W.truth_side[cid] == "left" else cm["right"]
    W.gold_ids = sorted(W.gold)
    # retired gold items leave the denominator from their retirement instant
    W.gold_retired = {g: WINDOW_START + r.below(WINDOW_END - WINDOW_START)
                      for g in W.gold_ids if r.chance(0.10)}

    # --- freeze windows per workstation ----------------------------------------
    W.workstations = [f"ws-{i:04d}" for i in range(1, _scaled(WORKSTATIONS, scale) + 1)]
    W.freezes = {}
    for ws in W.workstations:
        wins = []
        for wk in WEEKS:
            for _ in range(r.weighted([(1, 34), (2, 42), (3, 24)])):
                st = WINDOW_START + (wk - 27) * 7 * 86400 + r.below(5 * 86400)
                wins.append((st, st + r.randint(1, 4) * 3600))
        W.freezes[ws] = sorted(wins)

    # --- verdicts ---------------------------------------------------------------
    W.verdicts = {}
    vk = 0
    for cid in W.comparison_ids:
        cm = W.comparisons[cid]
        nv = r.weighted([(3, 55), (4, 35), (5, 10)])
        raters = sorted({W.ann_ids[r.below(len(W.ann_ids))] for _ in range(nv)})
        true = W.truth_side[cid]
        for a in raters:
            vk += 1
            vid = f"VD-{vk:07d}"
            at = W.completions[cm["left"]]["created_at"] + r.randint(1, 38) * 86400 + r.below(86400)
            if at >= WINDOW_END and r.chance(0.82):
                at = WINDOW_START + r.below(WINDOW_END - WINDOW_START)
            an = W.annotators[a]
            if r.chance(an["p_tie"]) or true == "tie":
                choice = "tie" if r.chance(0.72) else "both_bad"
            else:
                choice = true if r.chance(an["skill"]) else ("right" if true == "left" else "left")
                if choice == "right" and r.chance(an["left_pull"]):
                    choice = "left"
            W.verdicts[vid] = {
                "id": vid, "comparison": cid, "annotator": a,
                "choice": choice,
                "confidence": r.randint(50, 99),
                "at": at,
                "workstation": W.workstations[r.below(len(W.workstations))],
            }
    W.verdict_ids = sorted(W.verdicts)
    W.by_comparison = {}
    for vid in W.verdict_ids:
        W.by_comparison.setdefault(W.verdicts[vid]["comparison"], []).append(vid)
    W.by_annotator = {}
    for vid in W.verdict_ids:
        W.by_annotator.setdefault(W.verdicts[vid]["annotator"], []).append(vid)

    # --- voided verdicts recorded in the errata register ------------------------
    W.voided = {v for v in W.verdict_ids if r.chance(0.02)}
    # A later restore entry lifts a void. Separate stream so the world above is
    # unchanged by this draw.
    rr = derive(seed, "restore")
    W.restored = {}
    for v in sorted(W.voided):
        if rr.chance(0.2):
            W.restored[v] = W.verdicts[v]["at"] + rr.randint(1, 20) * 86400

    # --- adjudications ----------------------------------------------------------
    W.adjudications = {}
    for cid in W.comparison_ids:
        if not r.chance(0.11):
            continue
        cm = W.comparisons[cid]
        rev = W.seniors[r.below(len(W.seniors))] if W.seniors else W.ann_ids[0]
        at = W.completions[cm["left"]]["created_at"] + r.randint(20, 110) * 86400
        W.adjudications[cid] = {
            "comparison": cid, "reviewer": rev, "at": at,
            "choice": r.weighted([("left", 44), ("right", 44), ("tie", 12)]),
        }
    W.adjudication_ids = sorted(W.adjudications)
    # The review board approves most adjudications; an unapproved one is either
    # recorded as deferred or carries no minute at all.
    mr = derive(seed, "minutes")
    W.adj_approved = set()
    W.adj_deferred = set()
    for cid in W.adjudication_ids:
        if mr.chance(0.9):
            W.adj_approved.add(cid)
        elif mr.chance(0.5):
            W.adj_deferred.add(cid)

    # --- parameters -------------------------------------------------------------
    # Published in corpus_policy.md. A few vary with the seed so a builder has
    # to read them rather than carry them.
    pr = derive(seed, "policy")
    W.params = {
        "gold_min_items": 10 + pr.below(5),
        "gold_min_agreement": Fraction(72, 100),
        "bias_limit": Fraction(12, 100),
        "min_votes": 2,
        "max_prompt_tokens": 736 + 16 * pr.below(5),
        "max_pair_tokens": 1600,
        "validation_fraction": Fraction(10 + pr.below(5), 100),
        "epoch_cap": 2,
        "sequence_len": 1536,
        "global_batch": 16,
        "micro_batch": 4,
        "warmup_fraction": Fraction(3, 100),
        "shard_sequences": 128,
        "min_slice_pairs": 40,
        "max_contamination_rate": Fraction(2, 100),
        "min_kappa": Fraction(40, 100),
    }
    # per-vendor agreement overrides published in the policy
    W.vendor_gold_min = {v: W.params["gold_min_agreement"] for v in VENDORS}
    W.vendor_gold_min["orbit"] = Fraction(66 + pr.below(5), 100)
    W.vendor_gold_min["calder"] = Fraction(74 + pr.below(5), 100)

    # Targets run against availability on purpose: the scarce sources carry the
    # largest weights, so the epoch cap binds and the redistribution has to run.
    raw = {"coding": 14, "dialogue": 10, "multilingual": 22,
           "reasoning": 16, "safety": 20, "summarization": 18}
    W.mixture_target = {s: Fraction(raw[s], 100) for s in SOURCES}
    return W


# ---------------------------------------------------------------------------------
# resolution, in the documented anchor-first order
# ---------------------------------------------------------------------------------
def last_amendment(W, cm):
    return max((W.amendments.get(cm["left"], 0), W.amendments.get(cm["right"], 0)))


def in_freeze(W, ws, t):
    for st, en in W.freezes.get(ws, ()):
        if st <= t < en:
            return True
    return False


def gold_side_completion(W, cid, choice):
    """A verdict names a SIDE; the gold answer names a completion."""
    cm = W.comparisons[cid]
    return cm["left"] if choice == "left" else (cm["right"] if choice == "right" else None)


def annotator_standing(W):
    """Gold agreement, then A-side bias restricted to the balanced subset."""
    out = {}
    for a in W.ann_ids:
        seen = hits = 0
        for vid in W.by_annotator.get(a, ()):
            v = W.verdicts[vid]
            cid = v["comparison"]
            if cid not in W.gold:
                continue
            rt = W.gold_retired.get(cid)
            if rt is not None and v["at"] >= rt:
                continue          # retired gold leaves the denominator
            seen += 1
            if gold_side_completion(W, cid, v["choice"]) == W.gold[cid]:
                hits += 1
        agree = Fraction(hits, seen) if seen else None

        # position bias: balanced comparisons only
        bl = bn = 0
        for vid in W.by_annotator.get(a, ()):
            v = W.verdicts[vid]
            if v["comparison"] not in W.balanced or v["choice"] not in ("left", "right"):
                continue
            bn += 1
            bl += 1 if v["choice"] == "left" else 0
        bias = (Fraction(bl, bn) - Fraction(1, 2)) if bn else None

        floor = W.vendor_gold_min[W.annotators[a]["vendor"]]
        admitted = seen >= W.params["gold_min_items"] and agree is not None and agree >= floor
        out[a] = {
            "vendor": W.annotators[a]["vendor"],
            "gold_items": seen, "gold_hits": hits,
            "gold_agreement": q6n(agree),
            "balanced_verdicts": bn,
            "a_side_bias": q6n(bias),
            "biased": bias is not None and abs(bias) > W.params["bias_limit"],
            "standing": "admitted" if admitted else "gated",
        }
    return out


def verdict_admissibility(W, standing):
    """First applicable reason wins, in the documented order."""
    out = {}
    for vid in W.verdict_ids:
        v = W.verdicts[vid]
        cid = v["comparison"]
        cm = W.comparisons[cid]
        st = standing[v["annotator"]]
        reason = None
        if st["standing"] != "admitted":
            reason = "annotator_gated"
        elif not (WINDOW_START <= v["at"] < WINDOW_END):
            reason = "outside_window"
        elif in_freeze(W, v["workstation"], v["at"]):
            reason = "freeze_window"
        elif v["at"] <= last_amendment(W, cm):
            reason = "stale_amendment"
        elif st["biased"] and cid not in W.balanced:
            reason = "unbalanced_biased"
        elif vid in W.voided and vid not in W.restored:
            reason = "voided"
        out[vid] = {"comparison": cid, "annotator": v["annotator"],
                    "admissible": reason is None, "reason": reason}
    return out


def resolve_comparisons(W, adm):
    """Adjudication beats majority; majority needs min_votes; documented tie-break."""
    out = {}
    for cid in W.comparison_ids:
        cm = W.comparisons[cid]
        live = [vid for vid in W.by_comparison.get(cid, ()) if adm[vid]["admissible"]]
        adj = W.adjudications.get(cid)
        amend = last_amendment(W, cm)
        adj_ok = bool(adj) and adj["at"] > amend and adj["at"] < FREEZE and cid in W.adj_approved
        if adj_ok:
            out[cid] = {"resolved": adj["choice"], "route": "adjudicated",
                        "votes": len(live), "margin": q6(Fraction(1))}
            continue
        if len(live) < W.params["min_votes"]:
            out[cid] = {"resolved": None, "route": "insufficient",
                        "votes": len(live), "margin": None}
            continue
        tally = {c: 0 for c in CHOICES}
        conf = {c: 0 for c in CHOICES}
        for vid in live:
            v = W.verdicts[vid]
            tally[v["choice"]] += 1
            conf[v["choice"]] += v["confidence"]
        top = max(tally.values())
        front = sorted(c for c in CHOICES if tally[c] == top)
        if len(front) > 1:
            best = max(conf[c] for c in front)
            front = sorted(c for c in front if conf[c] == best)
        win = front[0]
        rest = sorted((tally[c] for c in CHOICES if c != win), reverse=True)
        runner = rest[0] if rest else 0
        out[cid] = {"resolved": win, "route": "majority", "votes": len(live),
                    "margin": q6(Fraction(top - runner, len(live)))}
    return out


def prompt_eligibility(W, res):
    """First applicable exclusion reason, in the documented order."""
    resolved_prompts = set()
    for cid, rr in res.items():
        if rr["resolved"] in ("left", "right"):
            resolved_prompts.add(W.comparisons[cid]["prompt"])
    out = {}
    for p in W.prompt_ids:
        pr = W.prompts[p]
        cid = W.cluster_of.get(p)
        reason = None
        if pr["retired"]:
            reason = "retired"
        elif pr["opted_out"]:
            reason = "opted_out"
        elif p in W.contaminated:
            reason = "contaminated"
        elif cid is not None and W.canonical[cid] != p:
            reason = "duplicate"
        elif pr["tokens"] > W.params["max_prompt_tokens"]:
            reason = "over_length"
        elif p not in resolved_prompts:
            reason = "no_resolved_pair"
        out[p] = {"eligible": reason is None, "reason": reason,
                  "cluster": cid, "family": pr["family"], "source": pr["source"]}
    return out


def preference_pairs(W, res, elig):
    out = []
    for cid in W.comparison_ids:
        rr = res[cid]
        if rr["resolved"] not in ("left", "right"):
            continue
        cm = W.comparisons[cid]
        p = cm["prompt"]
        if not elig[p]["eligible"]:
            continue
        chosen = cm["left"] if rr["resolved"] == "left" else cm["right"]
        rejected = cm["right"] if rr["resolved"] == "left" else cm["left"]
        tok = W.prompts[p]["tokens"] + W.completions[chosen]["tokens"] + W.completions[rejected]["tokens"]
        if tok > W.params["max_pair_tokens"]:
            continue
        out.append({
            "pair_id": "PP-" + cid.split("-")[1],
            "comparison": cid, "prompt": p, "family": W.prompts[p]["family"],
            "source": W.prompts[p]["source"], "chosen": chosen, "rejected": rejected,
            "margin": rr["margin"], "route": rr["route"], "tokens": tok,
        })
    out.sort(key=lambda x: x["pair_id"])
    return out


# ---------------------------------------------------------------------------------
# agreement: kappa over the multi-rated admissible subset
# ---------------------------------------------------------------------------------
def _collapse(choice):
    """The standard folds both_bad into tie for agreement, and only for agreement."""
    return "tie" if choice == "both_bad" else choice


AGREE_CATS = ["left", "right", "tie"]


def _kappa(units):
    """units: list of category lists. Po over unordered rater pairs; Pe from marginals."""
    num = den = 0
    marg = {c: 0 for c in AGREE_CATS}
    tot = 0
    for cats in units:
        n = len(cats)
        if n < 2:
            continue
        cnt = {c: 0 for c in AGREE_CATS}
        for c in cats:
            cnt[c] += 1
            marg[c] += 1
            tot += 1
        num += sum(v * (v - 1) for v in cnt.values())
        den += n * (n - 1)
    if den == 0 or tot == 0:
        return None, None, 0
    po = Fraction(num, den)
    pe = sum(Fraction(marg[c], tot) ** 2 for c in AGREE_CATS)
    kap = Fraction(0) if pe == 1 else (po - pe) / (1 - pe)
    return po, kap, den // 2


def agreement(W, adm):
    by_unit, by_vendor, by_domain = [], {}, {}
    for cid in W.comparison_ids:
        live = [vid for vid in W.by_comparison.get(cid, ()) if adm[vid]["admissible"]]
        if len(live) < 2:
            continue
        cats = [_collapse(W.verdicts[v]["choice"]) for v in live]
        by_unit.append(cats)
        dom = W.prompts[W.comparisons[cid]["prompt"]]["domain"]
        by_domain.setdefault(dom, []).append(cats)
        per = {}
        for v in live:
            per.setdefault(W.annotators[W.verdicts[v]["annotator"]]["vendor"], []).append(
                _collapse(W.verdicts[v]["choice"]))
        for ven, cl in per.items():
            if len(cl) >= 2:
                by_vendor.setdefault(ven, []).append(cl)
    po, kap, pairs = _kappa(by_unit)
    out = {"overall": {"observed_agreement": q6n(po), "kappa": q6n(kap),
                       "rated_units": len(by_unit), "rater_pairs": pairs},
           "by_vendor": {}, "by_domain": {}}
    for ven in VENDORS:
        p, k, n = _kappa(by_vendor.get(ven, []))
        out["by_vendor"][ven] = {"observed_agreement": q6n(p), "kappa": q6n(k),
                                 "rated_units": len(by_vendor.get(ven, [])), "rater_pairs": n}
    for dom in DOMAINS:
        p, k, n = _kappa(by_domain.get(dom, []))
        out["by_domain"][dom] = {"observed_agreement": q6n(p), "kappa": q6n(k),
                                 "rated_units": len(by_domain.get(dom, [])), "rater_pairs": n}
    return out


def dedup_report(W, elig):
    out = {}
    for cid in W.cluster_ids:
        members = W.clusters[cid]
        canon = W.canonical[cid]
        out[cid] = {"canonical": canon,
                    "members": members,
                    "dropped": [m for m in members if m != canon],
                    "canonical_effective_at": iso(W.prompts[canon]["effective_at"])}
    return out


# ---------------------------------------------------------------------------------
# family-wise split: no family straddles train and validation
# ---------------------------------------------------------------------------------
def split_assignment(W, pairs):
    per_fam = {}
    for x in pairs:
        per_fam[x["family"]] = per_fam.get(x["family"], 0) + 1
    total = sum(per_fam.values())
    want = Fraction(W.params["validation_fraction"]) * total
    assign, val_pairs = {}, 0
    for fam in sorted(per_fam):
        if fam in W.soft_contaminated_families:
            assign[fam] = "validation"
            val_pairs += per_fam[fam]
    for fam in sorted(per_fam):
        if fam in assign:
            continue
        if val_pairs < want:
            assign[fam] = "validation"
            val_pairs += per_fam[fam]
        else:
            assign[fam] = "train"
    counts = {"train": 0, "validation": 0}
    for fam, sp in assign.items():
        counts[sp] += per_fam[fam]
    return {"families": assign,
            "family_counts": {"train": sum(1 for v in assign.values() if v == "train"),
                              "validation": sum(1 for v in assign.values() if v == "validation")},
            "pair_counts": counts,
            "validation_share": q6n(Fraction(counts["validation"], total) if total else None)}


# ---------------------------------------------------------------------------------
# capped mixture: iterative redistribution, never naive renormalisation
# ---------------------------------------------------------------------------------
def mixture_plan(W, pairs, split):
    avail = {s: 0 for s in SOURCES}
    for x in pairs:
        if split["families"][x["family"]] == "train":
            avail[x["source"]] += 1
    budget = sum(avail.values())
    cap = {s: W.params["epoch_cap"] * avail[s] for s in SOURCES}
    alloc, fixed = {}, set()
    remaining, pool = budget, [s for s in SOURCES if avail[s] > 0]
    for s in SOURCES:
        if avail[s] == 0:
            alloc[s], fixed = 0, fixed | {s}
    for _ in range(len(SOURCES) + 2):
        free = [s for s in pool if s not in fixed]
        if not free:
            break
        wsum = sum(W.mixture_target[s] for s in free)
        if wsum == 0:
            break
        over = []
        for s in free:
            want = Fraction(remaining) * W.mixture_target[s] / wsum
            if want > cap[s]:
                over.append(s)
        if not over:
            for s in free:
                alloc[s] = Fraction(remaining) * W.mixture_target[s] / wsum
            break
        for s in over:
            alloc[s] = Fraction(cap[s])
            fixed.add(s)
            remaining -= cap[s]
    out = {}
    for s in SOURCES:
        a = Fraction(alloc.get(s, 0))
        out[s] = {"available_pairs": avail[s],
                  "target_weight": q6(W.mixture_target[s]),
                  "allocated_pairs": int(a),
                  "effective_weight": q6n(a / budget if budget else None),
                  "epochs": q6n(a / avail[s] if avail[s] else None),
                  "capped": s in fixed and avail[s] > 0}
    out["_total"] = {"budget_pairs": budget,
                     "allocated_pairs": sum(out[s]["allocated_pairs"] for s in SOURCES)}
    return out


# ---------------------------------------------------------------------------------
# packing and the training schedule
# ---------------------------------------------------------------------------------
def packing_plan(W, pairs, split):
    seq_len = W.params["sequence_len"]
    train = [x for x in pairs if split["families"][x["family"]] == "train"]
    train.sort(key=lambda x: x["pair_id"])
    seqs, cur, used = 0, 0, 0
    packed = dropped = 0
    for x in train:
        t = x["tokens"]
        if t > seq_len:
            dropped += 1
            continue
        if cur + t > seq_len:
            seqs += 1
            used += cur
            cur = 0
        cur += t
        packed += 1
    if cur:
        seqs += 1
        used += cur
    cap = seqs * seq_len
    return {"sequence_length": seq_len, "packed_pairs": packed, "dropped_pairs": dropped,
            "sequences": seqs, "token_capacity": cap, "tokens_used": used,
            "padding_tokens": cap - used,
            "packing_efficiency": q6n(Fraction(used, cap) if cap else None)}


def training_schedule(W, pack):
    gb, mb = W.params["global_batch"], W.params["micro_batch"]
    seqs = pack["sequences"]
    steps = seqs // gb
    warm = int((Fraction(W.params["warmup_fraction"]) * steps).__round__())
    shards = -(-seqs // W.params["shard_sequences"])
    return {"sequences": seqs, "global_batch": gb, "micro_batch": mb,
            "gradient_accumulation": gb // mb, "optimizer_steps": steps,
            "warmup_steps": warm, "shards": shards,
            "shard_sequences": W.params["shard_sequences"],
            "dropped_tail_sequences": seqs - steps * gb}


def slice_coverage(W, pairs, split):
    out = {}
    def bump(key, x):
        d = out.setdefault(key, {"pairs": 0, "train": 0, "validation": 0, "tokens": 0})
        d["pairs"] += 1
        d[split["families"][x["family"]]] += 1
        d["tokens"] += x["tokens"]
    for x in pairs:
        p = W.prompts[x["prompt"]]
        bump("domain-" + p["domain"], x)
        bump("difficulty-" + p["difficulty"], x)
        bump("risk-" + p["risk"], x)
        bump("locale-" + p["locale"], x)
        bump("source-" + x["source"], x)
    return {k: out[k] for k in sorted(out)}


def release_gates(W, pairs, split, agree, pack, slices):
    total = len(pairs)
    contaminated_in_train = sum(
        1 for x in pairs
        if split["families"][x["family"]] == "train"
        and (x["prompt"] in W.soft_contaminated or x["prompt"] in W.contaminated))
    small = sorted(k for k, v in slices.items() if v["pairs"] < W.params["min_slice_pairs"])
    straddle = False
    seen = {}
    for x in pairs:
        sp = split["families"][x["family"]]
        if seen.setdefault(x["family"], sp) != sp:
            straddle = True
    rate = Fraction(contaminated_in_train, total) if total else None
    kappa = agree["overall"]["kappa"]
    gates = {
        "min_slice_pairs_met": not small,
        "no_family_straddles_split": not straddle,
        "train_contamination_within_limit": rate is not None and rate <= W.params["max_contamination_rate"],
        "kappa_above_floor": kappa is not None and Fraction(str(kappa)) >= W.params["min_kappa"],
        "packing_efficiency_reported": pack["sequences"] > 0,
    }
    gates["release_approved"] = all(gates.values())
    return {"gates": gates,
            "undersized_slices": small,
            "train_contamination_rate": q6n(rate),
            "total_pairs": total}


from decimal import Decimal
import zlib


def _stable(v):
    """hash() is salted per process; the corpus must be byte-deterministic."""
    return zlib.crc32(str(v).encode()) & 0xFFFFFFFF



ALL_DOCS = [POL, SC, CT, FP, ER, RM, MD, MA]


# ---------------------------------------------------------------------------------
# identifier kits
# ---------------------------------------------------------------------------------
def kit_ids(fb, field, tag, label, registry, docs=(POL, SC), bait=False):
    """T1: the same key written five defensible ways."""
    d = docs[0]
    via = list(docs) + [registry]
    fb.R(f"{tag}_CASE", "T1", f"A {label} written in the wrong case still names the registered {label}.", d, via, mode="line", ht=True, fields=[field])
    fb.R(f"{tag}_PAD", "T1", f"A {label} with its zero padding stripped still names the registered {label}.", d, via, mode="line", ht=True, fields=[field])
    fb.R(f"{tag}_HOMO", "T1", f"A {label} carrying a Cyrillic look-alike letter still names the registered {label}.", SC, via, mode="line", fields=[field])
    fb.R(f"{tag}_FW", "T1", f"A {label} written with full-width digits still names the registered {label}.", SC, via, mode="line", fields=[field])
    fb.R(f"{tag}_WS", "T1", f"A {label} wrapped in non-breaking space still names the registered {label}.", SC, via, mode="line", fields=[field])
    if bait:
        fb.R(f"{tag}_NEAR", "T20", f"A {label} that differs from a registered one by a real digit is a different {label} and is not corrected.", SC, via + [ER], mode="line", ht=True, fields=[field], bait=True)
        fb.R(f"{tag}_RETIRED", "T20", f"A {label} the register retired is still the right {label} for records written before the retirement.", ER, via + [ER], mode="line", fields=[field], bait=True)
    return [f"{tag}_{s}" for s in ("CASE", "PAD", "HOMO", "FW", "WS")]


def kit_numeric(fb, field, docs=(SC, MD)):
    """T4 and T12: locale numerals and the rounding step."""
    d = docs[0]
    fb.R("NUM_LOC", "T4", "A decimal comma is a decimal point, not a thousands separator.", d, list(docs), mode="line", ht=True, fields=[field], excl=("NUM_EXCESS",))
    fb.R("NUM_GRP", "T4", "Grouped thousands are one number, not several.", d, list(docs), mode="line", fields=[field], excl=("NUM_EXCESS",))
    fb.R("NUM_PAREN", "T4", "A parenthesised figure is negative.", d, list(docs), mode="line", fields=[field])
    fb.R("NUM_EXCESS", "T12", "A value carrying more places than the reporting precision rounds half to even at the documented step, and only at that step.", MD, [MD, SC], mode="line", fields=[field], excl=("NUM_LOC", "NUM_GRP"))
    return ["NUM_LOC", "NUM_GRP", "NUM_PAREN", "NUM_EXCESS"]


def kit_time(fb, field, docs=(SC, MD)):
    """T3: the instant is not what the column says."""
    fb.R("TS_TZ", "T3", "A local timestamp is converted with the workstation's recorded zone before it is compared with the window.", SC, [SC, "clock_offsets.txt", "workstation_inventory.ini"], mode="line", ht=True, fields=[field])
    fb.R("TS_OFFSET", "T3", "A workstation carrying a clock offset has that offset removed before the instant is used.", SC, [SC, "clock_offsets.txt"], mode="line", fields=[field])
    fb.R("TS_EPOCH", "T3", "An epoch column in milliseconds is not an epoch column in seconds.", SC, [SC, MD], mode="line", fields=[field])
    fb.R("TS_EXCEL", "T3", "A spreadsheet serial date is days since 1899-12-30, which already absorbs the 1900 leap-year error.", SC, [SC, MD], mode="line", fields=[field])
    return ["TS_TZ", "TS_OFFSET", "TS_EPOCH", "TS_EXCEL"]


def kit_sentinel(fb, field, docs=(SC,)):
    """T5: the same placeholder means different things per source."""
    fb.R("SNT_NEG", "T5", "A negative one in this column is absent, not a value.", SC, [SC, FP], mode="line", ht=True, fields=[field])
    fb.R("SNT_NA", "T5", "A not-available marker is absent, not zero.", SC, [SC, FP], mode="line", fields=[field])
    fb.R("SNT_ZERO", "T5", "A zero in this column is a real zero and is not treated as absent.", SC, [SC, FP], mode="line", fields=[field], bait=True)
    return ["SNT_NEG", "SNT_NA", "SNT_ZERO"]


def kit_lifecycle(fb, keyfield, label, docs=(POL, ER)):
    """T6 and T7: voided, restored and superseded records that still look live."""
    fb.R("LC_VOID", "T6", f"A voided {label} is not live however complete it looks.", ER, [ER, POL], mode="row")
    fb.R("LC_RESTORE", "T6", f"A voided {label} that a later entry restores is live again from the restoring instant.", ER, [ER, POL, RM], mode="row", via_rules=["LC_VOID"])
    fb.R("LC_SUPER", "T7", f"A later revision of a {label} supersedes the earlier one only when the policy's amendment test is met.", POL, [POL, ER], mode="row")
    fb.R("LC_SUPER_NOT", "T7", f"A later revision that fails the amendment test leaves the earlier {label} standing.", POL, [POL, ER], mode="row", bait=True, via_rules=["LC_SUPER"])
    return ["LC_VOID", "LC_RESTORE", "LC_SUPER", "LC_SUPER_NOT"]


def kit_header(fb, docs=(SC,)):
    """T8: the columns move."""
    fb.R("HDR", "T8", "A renamed or reordered header band is still the same columns underneath.", SC, [SC, FP], mode="pos")
    fb.R("HDR_UNIT", "T2", "A header that restates the unit changes the scale of the column beneath it.", SC, [SC, MD], mode="pos")
    return ["HDR", "HDR_UNIT"]


def kit_bounds(fb, field, docs=(POL, MD)):
    """T11: the edge of the window."""
    fb.R("BND_START", "T11", "The collection window is closed at its start instant.", POL, [POL, MD], mode="line", fields=[field])
    fb.R("BND_END", "T11", "The collection window is open at its end instant, so the end instant is outside.", POL, [POL, MD], mode="line", fields=[field])
    fb.R("BND_THRESH", "T11", "A similarity or agreement threshold is met at the threshold, not only above it.", MD, [MD, POL], mode="line", fields=[field])
    return ["BND_START", "BND_END", "BND_THRESH"]


def kit_fk(fb, field, label, target, docs=(FP,)):
    """T13: the key points somewhere it should not."""
    fb.R("FK_DEAD", "T13", f"A {label} naming an unregistered {target} is not joined and is reported as a break.", FP, [FP, POL, target], mode="line", fields=[field])
    fb.R("FK_DECOY", "T13", f"A {label} naming only a non-authoritative copy of a {target} resolves through the authoritative register.", FP, [FP, POL], mode="line", fields=[field])
    return ["FK_DEAD", "FK_DECOY"]


def kit_precedence(fb, partner, docs=(FP,)):
    """T21: authority runs per field, not per file."""
    fb.R("PREC_FIELD", "T21", f"Where this source and {partner} disagree, the precedence table decides field by field, not file by file.", FP, [FP, partner, POL], mode="row")
    fb.R("PREC_LATER", "T22", f"A record here takes effect only once {partner} confirms it, and is not counted before that.", POL, [POL, partner], mode="row")
    return ["PREC_FIELD", "PREC_LATER"]


def kit_scope(fb, what, docs=(MA, MD)):
    """T14 and T17: the prose narrows the table."""
    fb.R("SCP_PROSE", "T14", f"An appendix footnote narrows which {what} the tabular rule covers.", MA, [MA, MD, POL], mode="row")
    fb.R("SCP_COND", "T17", f"Two {what} that look identical here resolve differently once the governing source is known.", FP, [FP, POL, SC], mode="row", cond=True)
    fb.R("SCP_EXEMPT", "T20", f"A {what} the appendix exempts is correct as written and is not normalised.", MA, [MA, SC], mode="row", bait=True)
    return ["SCP_PROSE", "SCP_COND", "SCP_EXEMPT"]


def kit_stat_bait(fb, field, what):
    """T15: the outlier is real."""
    fb.R("BAIT_OUT", "T15", f"An extreme {what} that the register confirms is a real value and is kept.", MA, [MA, ER], mode="line", fields=[field], bait=True)
    fb.R("BAIT_DUP", "T15", f"A repeated {what} that the register confirms is two real records, not one duplicated.", ER, [ER, SC], mode="line", fields=[field], bait=True)
    fb.R("BAIT_PREC", "T20", f"A {what} already carried at the reporting precision is not rounded a second time.", MD, [MD, SC], mode="line", fields=[field], bait=True)
    fb.R("BAIT_LOCAL", "T20", f"A {what} whose source is recorded as locale-neutral keeps its point as a decimal point.", SC, [SC, FP], mode="line", fields=[field], bait=True)
    return ["BAIT_OUT", "BAIT_DUP", "BAIT_PREC", "BAIT_LOCAL"]


def standard_kits(fb, idfield, idtag, idlabel, registry, numfield=None,
                  timefield=None, keylabel="record", partner=None, what="record"):
    """Every in-scope file carries at least these families."""
    codes = []
    codes += kit_ids(fb, idfield, idtag, idlabel, registry, bait=True)
    codes += kit_lifecycle(fb, idfield, keylabel)
    codes += kit_header(fb)
    codes += kit_scope(fb, what)
    if numfield:
        codes += kit_numeric(fb, numfield)
        codes += kit_bounds(fb, numfield)
        codes += kit_stat_bait(fb, numfield, what)
    if timefield:
        codes += kit_time(fb, timefield)
    if partner:
        codes += kit_precedence(fb, partner)
    return codes


# ---------------------------------------------------------------------------------
# cell formatters: turn a value plus the row's active rules into the printed text
# ---------------------------------------------------------------------------------
def fmt_id(value, rules, tag):
    return v_id(value, rules, tag)


def fmt_num(value, rules, places=0):
    d = Decimal(int(value))
    if "NUM_EXCESS" in rules:
        return v_excess(d, places, Rng(_stable(value)))
    locale = "de_DE" if "NUM_LOC" in rules else "en_US"
    return v_num(d, places, locale=locale, group="NUM_GRP" in rules,
                   paren="NUM_PAREN" in rules and value < 0)


def fmt_ts(t, rules, tz="UTC", offset_ms=0):
    if "TS_EPOCH" in rules:
        return str(t * 1000)
    if "TS_EXCEL" in rules:
        return repr(excel_serial(t))
    if "TS_TZ" in rules or "TS_OFFSET" in rules:
        return local_str(t, tz, offset_ms=offset_ms)
    return iso(t)


def fmt_sentinel(value, rules, absent=False):
    if absent:
        if "SNT_NEG" in rules:
            return "-1"
        if "SNT_NA" in rules:
            return "N/A"
        return ""
    return value


def kit_decoy(fb, authority, tag):
    """T16 in both directions: what makes the copy look authoritative, and what
    makes it look discardable while part of it is still required."""
    v = [POL, FP, authority]
    fb.R(f"{tag}_NEWER", "T16", f"A later revision stamp here does not outrank {authority}; the precedence table does.", POL, v, mode="row", direction="pull", dominant=True)
    fb.R(f"{tag}_COMPLETE", "T16", f"Columns absent from {authority} do not make this copy authoritative for the columns they share.", FP, v, mode="row", direction="pull")
    fb.R(f"{tag}_FINAL", "T16", f"A final or approved label here is a label, not an authority grant.", POL, v, mode="row", direction="pull")
    fb.R(f"{tag}_FIXED", "T16", f"A value this copy has already corrected is kept uncorrected where the policy says {authority} governs.", POL, v + [ER], mode="row", direction="pull", bait=True)
    fb.R(f"{tag}_GARBLED", "T16", "A garbled header band does not discharge the rows beneath it.", SC, v + [SC], mode="pos", direction="push")
    fb.R(f"{tag}_DEPRECATED", "T16", "A deprecated marking does not retire the void list this copy alone carries.", POL, v + [ER], mode="row", direction="push")
    fb.R(f"{tag}_SENTINELS", "T16", "A sentinel-heavy column does not make the rest of the row unusable.", SC, v + [FP], mode="line", fields=["pid"], direction="push")
    fb.R(f"{tag}_ONLYHERE", "T13", f"A crosswalk key carried only here is still required, because {authority} never carried it.", FP, v, mode="row", direction="push")
    fb.R(f"{tag}_AGREE", "T16", f"This copy agrees with {authority} on almost every key; the handful of disagreements are exactly the graded ones.", POL, v, mode="row", direction="pull")
    return [f"{tag}_{s}" for s in ("NEWER", "COMPLETE", "FINAL", "FIXED", "GARBLED",
                                   "DEPRECATED", "SENTINELS", "ONLYHERE", "AGREE")]


def assign_rows(fb, rng, codes, share=0.11):
    """Apply decoy row-rules after ordering, to middle rows only.

    `arrange` fills the first and last 2,000 rows from head/tail-eligible rules;
    tagging rows before it runs leaks these codes into those bands and pushes the
    head/tail rule count over the ceiling.
    """
    n = len(fb.rows)
    head_n = min(2000, n // 5)
    mid = [r for r in fb.rows[head_n:n - head_n] if r["k"] != "anchor"]
    for code in codes:
        if code not in fb.rules:
            continue
        pool = [r for r in mid if code not in r["r"]]
        rng.shuffle(pool)
        for row in pool[:int(share * len(mid))]:
            row["r"].append(code)
    for row in fb.rows:
        if row["k"] == "anchor":
            continue
        row["k"] = ("bait" if any(fb.rules[c]["bait"] for c in row["r"])
                    else ("trap" if row["r"] else "plain"))


def kit_encoding(fb, field):
    """T9 and T10: the bytes of the field fight the parser."""
    fb.R("ENC_DELIM", "T9", "A field holding the delimiter is one field, not two, because it is quoted.", SC, [SC, FP], mode="line", fields=[field])
    fb.R("ENC_NEWLINE", "T9", "A quoted newline inside a field does not start a new record.", SC, [SC, FP], mode="line", fields=[field])
    fb.R("ENC_RAGGED", "T9", "A short row is padded on the right, never realigned from the left.", SC, [SC], mode="line", fields=[field])
    fb.R("ENC_LATIN", "T10", "A Latin-1 byte in an otherwise UTF-8 source is decoded with the source's declared encoding.", SC, [SC, FP], mode="line", fields=[field])
    fb.R("ENC_BOM", "T10", "A byte-order mark belongs to the file, not to the first field.", SC, [SC], mode="pos")
    return ["ENC_DELIM", "ENC_NEWLINE", "ENC_RAGGED", "ENC_LATIN", "ENC_BOM"]


def kit_loop(fb, partner, other):
    """T18 and T19: the two fixes that undo each other, and the consistent wrong set."""
    fb.R("OSC_A", "T18", f"Reconciling this against {partner} alone breaks the total {other} publishes; the third rule in the policy satisfies both.", POL, [POL, partner, other], mode="row", via_rules=["PREC_FIELD"])
    fb.R("OSC_B", "T18", f"Reconciling this against {other} alone breaks the total {partner} publishes; the same third rule settles it.", POL, [POL, other, partner], mode="row", via_rules=["OSC_A"])
    fb.R("EQ_MEMBER", "T19", f"This row is consistent with {partner} and {other} under a wrong reading; only the control total outside that set contradicts it.", CT, [CT, partner, other], mode="row")
    return ["OSC_A", "OSC_B", "EQ_MEMBER"]


import json


WEEKS = WEEKS


# ---------------------------------------------------------------------------------
# row sources
# ---------------------------------------------------------------------------------
def src_prompts(W):
    return [{"pid": p, "family": W.prompts[p]["family"], "num": W.prompts[p]["tokens"],
             "ts": W.prompts[p]["registered_at"], "a": W.prompts[p]["domain"],
             "b": W.prompts[p]["source"], "c": W.prompts[p]["locale"],
             "d": W.prompts[p]["difficulty"], "e": W.prompts[p]["risk"]}
            for p in W.prompt_ids]


def src_completions(W):
    return [{"pid": c, "family": W.completions[c]["prompt"], "num": W.completions[c]["tokens"],
             "ts": W.completions[c]["created_at"], "a": W.completions[c]["policy"],
             "b": str(W.completions[c]["merit"]), "c": "cmp", "d": "live", "e": "v1"}
            for c in W.completion_ids]


def src_comparisons(W):
    return [{"pid": m, "family": W.comparisons[m]["prompt"], "num": len(W.by_comparison.get(m, ())),
             "ts": W.completions[W.comparisons[m]["left"]]["created_at"],
             "a": W.comparisons[m]["left"], "b": W.comparisons[m]["right"],
             "c": W.comparisons[m]["order"], "d": W.comparisons[m]["batch"],
             "e": "balanced" if m in W.balanced else "single"}
            for m in W.comparison_ids]


def _verdict_rows(W, ids):
    out = []
    for v in ids:
        d = W.verdicts[v]
        out.append({"pid": v, "family": d["comparison"], "num": d["confidence"],
                    "ts": d["at"], "a": d["annotator"], "b": d["choice"],
                    "c": d["workstation"], "d": W.annotators[d["annotator"]]["vendor"],
                    "e": W.comparisons[d["comparison"]]["batch"]})
    return out


def src_verdicts(W, part, n):
    ids = [v for i, v in enumerate(W.verdict_ids) if i % n == part]
    return _verdict_rows(W, ids)


def src_verdicts_vendor(W, vendor):
    ids = [v for v in W.verdict_ids if W.annotators[W.verdicts[v]["annotator"]]["vendor"] == vendor]
    return _verdict_rows(W, ids)


def src_verdicts_partition(W, vendor):
    rows = src_verdicts_vendor(W, vendor)
    if vendor != VENDORS[0]:
        return rows
    decoy_id = next(v for v in W.verdict_ids
                    if W.annotators[W.verdicts[v]["annotator"]]["vendor"] == VENDORS[3])
    decoy = _verdict_rows(W, [decoy_id])[0]
    decoy["b"] = CHOICES[(CHOICES.index(decoy["b"]) + 1) % len(CHOICES)]
    return rows + [decoy]


def src_annotator_weeks(W):
    out = []
    for a in W.ann_ids:
        an = W.annotators[a]
        for wk in WEEKS:
            for rev in range(1, 5):
                out.append({"pid": a, "family": an["vendor"], "num": rev,
                            "ts": WINDOW_START + (wk - 27) * 7 * 86400,
                            "a": str(wk), "b": an["cohort"],
                            "c": "senior" if an["senior"] else "rater",
                            "d": str(int(an["skill"] * 100)), "e": f"r{rev}"})
    return out


def WS_TZ(num):
    return sorted(TZ_OFFSET)[num % len(TZ_OFFSET)]


def WS_OFFSET(num):
    return ((num * 37) % 900) - 450


def src_workstation_weeks(W):
    out = []
    for ws in W.workstations:
        for wk in WEEKS:
            for rev in range(1, 3):
                out.append({"pid": ws, "family": f"site-{(int(ws[3:]) % 7) + 1}", "num": rev,
                            "ts": WINDOW_START + (wk - 27) * 7 * 86400,
                            "a": str(wk), "b": WS_TZ(int(ws[3:])),
                            "c": "active", "d": str(WS_OFFSET(int(ws[3:]))), "e": f"s{rev}"})
    return out


def src_gold(W):
    out = []
    for g in W.gold_ids:
        for rev in range(1, 9):
            out.append({"pid": g, "family": W.gold[g], "num": rev,
                        "ts": W.gold_retired.get(g, WINDOW_START),
                        "a": W.comparisons[g]["prompt"], "b": W.gold[g],
                        "c": "retired" if g in W.gold_retired else "live",
                        "d": str(rev), "e": f"g{rev}"})
    return out


def src_clusters(W):
    out = []
    for cid in W.cluster_ids:
        for m in W.clusters[cid]:
            for rev in range(1, 7):
                out.append({"pid": cid, "family": m, "num": rev,
                            "ts": W.prompts[m]["effective_at"],
                            "a": m, "b": W.canonical[cid],
                            "c": "canonical" if m == W.canonical[cid] else "member",
                            "d": str(rev), "e": f"c{rev}"})
    return out


def src_contam(W):
    return [{"pid": e["prompt"], "family": e["suite"], "num": e["similarity"],
             "ts": WINDOW_START, "a": e["suite"], "b": str(e["similarity"]),
             "c": "hit" if e["similarity"] >= 95 else ("near" if e["similarity"] >= 80 else "screened"),
             "d": "verbatim" if e["similarity"] >= 95 else "ngram", "e": "s1"}
            for e in W.contam_screen]


def src_adjudications(W):
    out = []
    for cid in W.adjudication_ids:
        a = W.adjudications[cid]
        for rev in range(1, 9):
            out.append({"pid": cid, "family": a["reviewer"], "num": rev, "ts": a["at"],
                        "a": a["choice"], "b": a["reviewer"], "c": "final" if rev == 5 else "draft",
                        "d": str(rev), "e": f"a{rev}"})
    return out


def src_amendments(W):
    out = []
    for c in sorted(W.amendments):
        for rev in range(1, 11):
            out.append({"pid": c, "family": W.completions[c]["prompt"], "num": rev,
                        "ts": W.amendments[c], "a": "amend", "b": str(rev),
                        "c": "applied", "d": str(rev), "e": f"m{rev}"})
    return out


def src_freezes(W):
    out = []
    for ws in W.workstations:
        for i, (st, en) in enumerate(W.freezes[ws]):
            out.append({"pid": f"fz-{ws}-{i:03d}", "family": ws, "num": (en - st) // 3600,
                        "ts": st, "a": ws, "b": iso(en), "c": "freeze",
                        "d": str((en - st) // 3600), "e": "f1"})
    return out


def src_batches(W):
    out = []
    seen = {}
    for m in W.comparison_ids:
        seen.setdefault(W.comparisons[m]["batch"], []).append(m)
    for b in sorted(seen):
        for i, m in enumerate(seen[b][:20]):
            out.append({"pid": b, "family": m, "num": i, "ts": WINDOW_START + i * 3600,
                        "a": m, "b": str(len(seen[b])), "c": "open", "d": str(i), "e": "b1"})
    return out


def src_slice_weeks(W):
    out = []
    keys = ([f"domain:{d}" for d in DOMAINS] + [f"difficulty:{x}" for x in DIFFICULTY]
            + [f"risk:{x}" for x in RISK] + [f"locale:{x}" for x in LOCALES]
            + [f"source:{x}" for x in SOURCES])
    for k in keys:
        for wk in WEEKS:
            for rev in range(1, 31):
                out.append({"pid": k.replace(":", "-"), "family": k.split(":")[0], "num": rev,
                            "ts": WINDOW_START + (wk - 27) * 7 * 86400,
                            "a": k.split(":")[1], "b": str(wk), "c": "support",
                            "d": str(rev), "e": f"w{wk}"})
    return out


def src_mixture(W):
    out = []
    for s in SOURCES:
        for wk in WEEKS:
            for rev in range(1, 126):
                out.append({"pid": f"{s}-{wk:02d}-{rev:03d}", "family": s, "num": rev,
                            "ts": WINDOW_START + (wk - 27) * 7 * 86400,
                            "a": s, "b": str(int(W.mixture_target[s] * 100)),
                            "c": "target", "d": str(rev), "e": f"w{wk}"})
    return out


def src_errata(W, n=0):
    """The errata register: retirements, opt-outs and verdict voids.

    These three drive exclusion reasons in the chain and exist in no other
    file, so the register is the only place a solver can learn them."""
    out = []
    for p in sorted(W.prompt_ids):
        if W.prompts[p]["retired"]:
            out.append({"pid": p, "family": "prompt", "num": 1,
                        "ts": W.prompts[p]["registered_at"], "a": "retire",
                        "b": "retired", "c": "applied", "d": "1", "e": "er"})
        if W.prompts[p]["opted_out"]:
            out.append({"pid": p, "family": "prompt", "num": 1,
                        "ts": W.prompts[p]["registered_at"], "a": "optout",
                        "b": "opted_out", "c": "applied", "d": "1", "e": "er"})
    for v in sorted(W.voided):
        out.append({"pid": v, "family": "verdict", "num": 1,
                    "ts": W.verdicts[v]["at"], "a": "void", "b": "voided",
                    "c": "applied", "d": "1", "e": "er"})
    for v in sorted(W.restored):
        out.append({"pid": v, "family": "verdict", "num": 1,
                    "ts": W.restored[v], "a": "restore", "b": "restored",
                    "c": "applied", "d": "1", "e": "er"})
    i = 0
    pid = sorted(W.prompt_ids)
    while len(out) < n:
        p = pid[i % len(pid)]
        out.append({"pid": f"ERN-{i + 1:05d}", "family": "note", "num": (i * 7) % 997,
                    "ts": WINDOW_START + (i % 90) * 86400, "a": "note",
                    "b": "reviewed", "c": "closed", "d": str(i % 100), "e": "er"})
        i += 1
    return out


def src_minutes(W):
    out = []
    for cid in W.adjudication_ids:
        if cid in W.adj_approved:
            decision = "approved"
        elif cid in W.adj_deferred:
            decision = "deferred"
        else:
            continue
        adj = W.adjudications[cid]
        out.append({"pid": cid, "family": adj["reviewer"], "num": 1, "ts": adj["at"],
                    "a": decision, "b": adj["reviewer"], "c": "board", "d": "1", "e": "rm"})
    return out


def src_doc(W, tag, n=10200):
    """Appendix/rate/errata rows that give a prose document its data lines."""
    out = []
    pid = W.prompt_ids
    for i in range(n):
        p = pid[i % len(pid)]
        out.append({"pid": f"{tag}-{i + 1:05d}", "family": p, "num": (i * 7) % 997,
                    "ts": WINDOW_START + (i % 90) * 86400,
                    "a": p, "b": SOURCES[i % len(SOURCES)],
                    "c": DOMAINS[i % len(DOMAINS)], "d": str((i * 13) % 100),
                    "e": f"{tag.lower()}{i % 9}"})
    return out


# ---------------------------------------------------------------------------------
# cell rendering
# ---------------------------------------------------------------------------------
COLS = [("rid", "pid", "id"), ("par", "family", "text"),
        ("val", "num", "num"), ("at", "ts", "ts"),
        ("fa", "a", "text"), ("fb", "b", "text")]
ALT = {"rid": "rec", "par": "pnt", "at": "ts", "fa": "a", "fb": "b"}

# Six columns cannot carry every field an entity has, so each file projects a
# different pair into fa/fb. The union covers the whole entity, no file is
# redundant, and the cost is zero bytes. A field that appears in no projection
# exists nowhere in the corpus and makes the task unsolvable.
PROJ = {
    "collection_vendor_a.log": ("a", "c"), "collection_vendor_b.log": ("a", "c"),
    "collection_vendor_c.log": ("a", "c"), "legacy_verdicts.txt": ("c", "b"),
    "annotation_store.db": ("a", "c"), "annotation_store_mirror.db": ("c", "b"),
    "run_configs.toml": ("c", "d"), "harness_events.log": ("d", "e"),
    "batch_registry_export.xml": ("c", "e"), "corpus_prelim.xlsx": ("e", "c"),
    "release_snapshot.json": ("d", "e"),
    "slice_attributes.csv": ("c", "d"), "prompt_locales.tsv": ("e", "c"),
    "locale_codes_legacy.tsv": ("c", "e"), "packing_config.json": ("d", "e"),
    "token_lengths.csv": ("b", "e"), "tokenizer_revisions.json": ("e", "d"),
    "gold_answers_revised.csv": ("c", "d"), "dedup_clusters.tsv": ("d", "e"),
    "annotator_roster.csv": ("b", "c"), "vendor_tags.yaml": ("c", "d"),
    "annotation_standards.xlsx": ("d", "c"), "vendor_invoices.xlsx": ("e", "d"),
    "workstation_inventory.ini": ("b", "d"), "clock_offsets.txt": ("d", "b"),
    "freeze_windows.ics": ("a", "b"), "adjudications.jsonl": ("a", "c"),
    "completion_amendments.xml": ("a", "c"), "contamination_hits.jsonl": ("a", "d"),
    "errata_register.docx": ("a", "b"),
}


def proj_cols(name):
    a, b = PROJ.get(name, ("a", "b"))
    return [c if c[0] not in ("fa", "fb") else
            (c[0], a if c[0] == "fa" else b, "text") for c in COLS]


def header(fb, row, tag):
    cols = proj_cols(fb.name)
    rules = row["r"]
    out = []
    for h, _, _ in cols:
        if h == "val":
            out.append("val_x1000" if "HDR_UNIT" in rules else "val")
        else:
            out.append(ALT.get(h, h) if "HDR" in rules else h)
    return out


def cells(fb, row, tag):
    f, rules = row["f"], row["r"]
    out = []
    if fb.fmt in ("sqlite", "ics"):
        rules = [c for c in rules if c not in ("HDR", "HDR_UNIT")]
        row = {"f": f, "r": rules, "k": row["k"], "c": row.get("c")}
    for name, key, role in proj_cols(fb.name):
        v = f.get(key, "")
        if role == "id":
            rl = rules
            if fb.fmt in ("log", "ini", "fixed"):
                rl = [c for c in rules if not c.endswith("_WS")]
            out.append(fmt_id(str(v), rl, tag))
        elif role == "num":
            if fb.fmt == "ics":
                out.append(str(int(v) if str(v).lstrip("-").isdigit() else 0))
                continue
            n = int(v) if str(v).lstrip("-").isdigit() else 0
            if "SNT_NEG" in rules or "SNT_NA" in rules:
                out.append(fmt_sentinel("", rules, absent=True))
            else:
                out.append(fmt_num(n * 1000 if "HDR_UNIT" in rules else n, rules))
        elif role == "ts":
            if fb.fmt == "ics":
                out.append(iso(int(v) if str(v).isdigit() else WINDOW_START))
                continue
            # A local instant must name the machine it came from, and the zone and
            # offset must be the ones the inventory and offset register publish,
            # or the instant cannot be converted back to UTC by anyone reading them.
            ws = str(f.get("c", ""))
            t = int(v) if str(v).isdigit() else WINDOW_START
            if ws.startswith("ws-") and ws[3:].isdigit():
                num = int(ws[3:])
                tzname = WS_TZ(num)
                out.append(fmt_ts(t, rules, tz=tzname, offset_ms=WS_OFFSET(num) * 1000))
            else:
                out.append(fmt_ts(t, [c for c in rules if c not in ("TS_TZ", "TS_OFFSET")]))
        else:
            s = str(v)
            if "SCP_COND" in rules:
                s = s.upper()
            out.append(s)
    return out


# ---------------------------------------------------------------------------------
# renderers
# ---------------------------------------------------------------------------------
def _rows(fb, tag):
    return [(header(fb, r, tag), cells(fb, r, tag)) for r in fb.rows]


def r_delim(fb, tag, delim, bom=False):
    out, last = [], None
    for h, c in _rows(fb, tag):
        if h != last:
            out.append(h)
            last = h
        out.append(c)
    return csv_bytes(out, bom=bom, delim=delim)


def r_jsonl(fb, tag):
    lines = []
    for h, c in _rows(fb, tag):
        lines.append(json.dumps(dict(zip(h, c)), sort_keys=True, ensure_ascii=False))
    return ("\n".join(lines) + "\n").encode("utf-8")


def r_json(fb, tag, root="entries"):
    recs = [dict(zip(h, c)) for h, c in _rows(fb, tag)]
    return (json.dumps({root: recs}, sort_keys=True, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def r_xml(fb, tag, elem="record"):
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<export>"]
    for h, c in _rows(fb, tag):
        attrs = " ".join(f'{k}="{xesc(v)}"' for k, v in zip(h, c))
        out.append(f"  <{elem} {attrs}/>")
    out.append("</export>")
    return ("\n".join(out) + "\n").encode("utf-8")


def r_log(fb, tag, prefix):
    out = []
    for h, c in _rows(fb, tag):
        kv = " ".join(f"{k}={v}" for k, v in zip(h, c) if v != "")
        out.append(f"{prefix} {c[3]} {kv}")
    return ("\n".join(out) + "\n").encode("utf-8")


def r_yaml(fb, tag, root="entries"):
    out = [f"{root}:"]
    for h, c in _rows(fb, tag):
        out.append(f"  - {h[0]}: {json.dumps(c[0], ensure_ascii=False)}")
        for k, v in list(zip(h, c))[1:]:
            out.append(f"    {k}: {json.dumps(v, ensure_ascii=False)}")
    return ("\n".join(out) + "\n").encode("utf-8")


def r_toml(fb, tag, table="entry"):
    out = []
    for h, c in _rows(fb, tag):
        out.append(f"[[{table}]]")
        for k, v in zip(h, c):
            out.append(f"{k} = {json.dumps(v, ensure_ascii=False)}")
        out.append("")
    return ("\n".join(out) + "\n").encode("utf-8")


def r_ini(fb, tag):
    out, sec = [], None
    for i, (h, c) in enumerate(_rows(fb, tag)):
        s = f"snapshot-{i // 2000 + 1}"
        if s != sec:
            out.append(f"[{s}]")
            sec = s
        out.append(f"{c[0]}@{c[3]} = " + "; ".join(f"{k}={v}" for k, v in list(zip(h, c))[1:] if v != ""))
    return ("\n".join(out) + "\n").encode("utf-8")


def r_fixed(fb, tag):
    out = ["#COLUMNS " + " ".join(h.upper() for h, _, _ in COLS)]
    for h, c in _rows(fb, tag):
        out.append("".join(str(v)[:18].rjust(19) for v in c))
    return ("\n".join(out) + "\n").encode("utf-8")


def r_xlsx(fb, tag, sheets=3):
    allr = _rows(fb, tag)
    per = (len(allr) + sheets - 1) // sheets
    out = []
    for i in range(sheets):
        chunk = allr[i * per:(i + 1) * per]
        if not chunk:
            continue
        rows = [chunk[0][0]] + [c for _, c in chunk]
        out.append((f"sheet{i + 1}", rows))
    return xlsx_bytes(out)


def r_parquet(fb, tag):
    allr = _rows(fb, tag)
    cols = [(h, "string") for h in allr[0][0]]
    groups, size = [], 4000
    for i in range(0, len(allr), size):
        groups.append([tuple(c) for _, c in allr[i:i + size]])
    return parquet_bytes(cols, groups)


def r_sqlite(fb, tag):
    allr = _rows(fb, tag)
    hdr = allr[0][0]
    cols = ", ".join(f'"{h}" TEXT' for h in hdr)
    ins = f'INSERT INTO records VALUES ({", ".join("?" * len(hdr))})'
    return sqlite_bytes([(f"CREATE TABLE records ({cols})", None),
                           (ins, [tuple(c) for _, c in allr])])


def r_mbox(fb, tag):
    msgs = []
    for i, (h, c) in enumerate(_rows(fb, tag)):
        body = "\n".join(f"{k}: {v}" for k, v in zip(h, c))
        msgs.append((f"From dataops@aurelis.example {rfc2822(WINDOW_START + i, 'UTC')[:-6]}",
                     [("From", "dataops@aurelis.example"), ("To", "corpus-release@aurelis.example"),
                      ("Subject", f"notice {c[0]}"), ("Date", rfc2822(WINDOW_START + i * 60, "UTC")),
                      ("Message-ID", f"<{c[0]}@aurelis.example>")], body))
    return mbox_bytes(msgs)


def r_ics(fb, tag):
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//aurelis//collection-freeze//EN"]
    for h, c in _rows(fb, tag):
        out += ["BEGIN:VEVENT", f"UID:{c[0]}", "SEQUENCE:1",
                f"DTSTART:{c[3].replace('-', '').replace(':', '').replace('Z', 'Z')}",
                f"SUMMARY:Collection freeze {c[4]}", f"X-WORKSTATION:{c[4]}",
                f"X-HOURS:{c[2]}", "END:VEVENT"]
    out.append("END:VCALENDAR")
    return ("\n".join(out) + "\n").encode("utf-8")


def r_doc(fb, tag, fmt, prose):
    return render_doc(fb, prose, [], fmt)


RENDER = {
    "csv": lambda fb, t: r_delim(fb, t, ","),
    "csvbom": lambda fb, t: r_delim(fb, t, ",", bom=True),
    "tsv": lambda fb, t: r_delim(fb, t, "\t"),
    "jsonl": r_jsonl, "json": r_json, "xml": r_xml,
    "yaml": r_yaml, "toml": r_toml, "ini": r_ini, "fixed": r_fixed,
    "xlsx": r_xlsx, "parquet": r_parquet, "sqlite": r_sqlite,
    "mbox": r_mbox, "ics": r_ics,
    "log": lambda fb, tg: r_log(fb, tg, "collect"),
}


# ---------------------------------------------------------------------------------
# the fifty specs: name, format, decoy, row source, id tag, precedence partner
# ---------------------------------------------------------------------------------
def SPECS(W):
    V = VENDORS
    return [
        ("prompt_registry.csv", "csv", 0, lambda: src_prompts(W), "PRM", ER),
        ("completion_index.csv", "csv", 0, lambda: src_completions(W), "CMP", ER),
        ("annotator_roster.csv", "csvbom", 0, lambda: src_annotator_weeks(W), "ANN", POL),
        ("token_lengths.csv", "csv", 0, lambda: src_completions(W), "CMP", MD),
        ("slice_attributes.csv", "csv", 0, lambda: src_prompts(W), "PRM", "slice_definitions.yaml"),
        ("gold_answers_revised.csv", "csv", 1, lambda: src_gold(W), "CMR", "gold_set.tsv"),
        ("gold_set.tsv", "tsv", 0, lambda: src_gold(W), "CMR", ER),
        ("dedup_clusters.tsv", "tsv", 0, lambda: src_clusters(W), "DUP", POL),
        ("prompt_locales.tsv", "tsv", 0, lambda: src_prompts(W), "PRM", SC),
        ("locale_codes_legacy.tsv", "tsv", 1, lambda: src_prompts(W), "PRM", "prompt_locales.tsv"),
        ("verdicts_vendor_a.jsonl", "jsonl", 0, lambda: src_verdicts_partition(W, V[0]), "VD", ER),
        ("verdicts_vendor_b.jsonl", "jsonl", 0, lambda: src_verdicts_partition(W, V[1]), "VD", ER),
        ("adjudications.jsonl", "jsonl", 0, lambda: src_adjudications(W), "CMR", RM),
        ("contamination_hits.jsonl", "jsonl", 0, lambda: src_contam(W), "PRM", MD),
        ("verdicts_rescored.jsonl", "jsonl", 1, lambda: src_verdicts_vendor(W, V[2]), "VD", "verdicts_vendor_a.jsonl"),
        ("annotation_standards.xlsx", "xlsx", 0, lambda: src_annotator_weeks(W), "ANN", POL),
        ("mixture_targets.xlsx", "xlsx", 0, lambda: src_mixture(W), "SRC", MD),
        ("vendor_invoices.xlsx", "xlsx", 0, lambda: src_annotator_weeks(W), "ANN", CT),
        ("corpus_prelim.xlsx", "xlsx", 1, lambda: src_comparisons(W), "CMR", "annotation_store.db"),
        ("tokenizer_revisions.json", "json", 0, lambda: src_completions(W), "CMP", MD),
        ("packing_config.json", "json", 0, lambda: src_prompts(W), "PRM", MD),
        ("release_snapshot.json", "json", 1, lambda: src_comparisons(W), "CMR", "batch_registry.xml"),
        ("batch_registry.xml", "xml", 0, lambda: src_comparisons(W), "CMR", ER),
        ("completion_amendments.xml", "xml", 0, lambda: src_amendments(W), "CMP", POL),
        ("batch_registry_export.xml", "xml", 1, lambda: src_comparisons(W), "CMR", "batch_registry.xml"),
        ("verdicts_shard1.parquet", "parquet", 0, lambda: src_verdicts_partition(W, V[2]), "VD", ER),
        ("verdicts_shard2.parquet", "parquet", 0, lambda: src_verdicts_partition(W, V[3]), "VD", ER),
        ("verdicts_staging.parquet", "parquet", 1, lambda: src_verdicts(W, 0, 3), "VD", "verdicts_shard1.parquet"),
        ("annotation_store.db", "sqlite", 0, lambda: _verdict_rows(W, W.verdict_ids), "VD", ER),
        ("annotation_store_mirror.db", "sqlite", 1, lambda: src_verdicts(W, 1, 3), "VD", "annotation_store.db"),
        ("collection_vendor_a.log", "log", 0, lambda: src_verdicts_vendor(W, V[0]), "VD", SC),
        ("collection_vendor_b.log", "log", 0, lambda: src_verdicts_vendor(W, V[1]), "VD", SC),
        ("collection_vendor_c.log", "log", 0, lambda: src_verdicts_vendor(W, V[2]), "VD", SC),
        ("harness_events.log", "log", 0, lambda: src_batches(W) + src_comparisons(W), "CMR", RM),
        ("slice_definitions.yaml", "yaml", 0, lambda: src_slice_weeks(W), "SLC", MD),
        ("vendor_tags.yaml", "yaml", 0, lambda: src_annotator_weeks(W), "ANN", POL),
        ("run_configs.toml", "toml", 0, lambda: src_batches(W) + src_comparisons(W), "CMR", ER),
        ("workstation_inventory.ini", "ini", 0, lambda: src_workstation_weeks(W), "WS", SC),
        ("clock_offsets.txt", "fixed", 0, lambda: src_workstation_weeks(W), "WS", SC),
        ("legacy_verdicts.txt", "fixed", 0, lambda: src_verdicts(W, 1, 3), "VD", ER),
        ("dataops_notifications.mbox", "mbox", 0, lambda: src_doc(W, "NOTE"), "NOTE", RM),
        ("freeze_windows.ics", "ics", 0, lambda: src_freezes(W), "WS", RM),
        (POL, "md", 0, lambda: [], "POL", FP),
        (SC, "md", 0, lambda: [], "CONV", FP),
        (CT, "html", 0, lambda: [], "CTL", POL),
        (FP, "html", 0, lambda: [], "PREC", POL),
        (ER, "docx", 0, lambda: src_errata(W), "ERR", POL),
        (RM, "docx", 0, lambda: src_minutes(W), "MIN", POL),
        (MD, "pdf", 0, lambda: [], "METRIC", MA),
        (MA, "pdf", 0, lambda: [], "APPX", MD),
    ]


DECOY_AUTHORITY = {
    "gold_answers_revised.csv": "gold_set.tsv",
    "locale_codes_legacy.tsv": "prompt_locales.tsv",
    "verdicts_rescored.jsonl": "verdicts_vendor_a.jsonl",
    "corpus_prelim.xlsx": "annotation_store.db",
    "release_snapshot.json": "batch_registry.xml",
    "batch_registry_export.xml": "batch_registry.xml",
    "verdicts_staging.parquet": "verdicts_shard1.parquet",
    "annotation_store_mirror.db": "annotation_store.db",
}
ID_LABEL = {"PRM": "prompt id", "CMP": "completion id", "CMR": "comparison id",
            "VD": "verdict id", "ANN": "annotator id", "WS": "workstation id",
            "DUP": "cluster id", "SLC": "slice key", "SRC": "source key",
            "POL": "clause id", "CONV": "convention id", "CTL": "control id",
            "PREC": "precedence id", "ERR": "errata id", "MIN": "minute id",
            "METRIC": "definition id", "APPX": "appendix id", "NOTE": "notice id"}


CAP = {}


def build_file(W, spec, rngs):
    name, fmt, decoy, src, tag, partner = spec
    fb = FB(name, decoy=bool(decoy))
    fb.fmt, fb.tag = fmt, tag
    label = ID_LABEL[tag]
    standard_kits(fb, "pid", tag, label, "prompt_registry.csv", numfield="num",
                    timefield="ts", keylabel=label.split()[0], partner=partner,
                    what=label.split()[0])
    if decoy:
        kit_sentinel(fb, "num")
    kit_fk(fb, "family", label, "prompt_registry.csv")
    kit_encoding(fb, "family")
    kit_loop(fb, partner, CT if partner != CT else POL)
    dc = kit_decoy(fb, DECOY_AUTHORITY[name], "DEC") if decoy else []
    rows = src()
    cap = CAP.get(name)
    if cap and len(rows) > cap:
        rows = rows[:cap]
    for i, f in enumerate(rows):
        fb.add(f, kind="anchor" if i % 37 == 0 else None)
    saved = {c: r for c, r in fb.rules.items() if r["mode"] == "row"}
    arrange(fb, rngs("arrange|" + name))
    assign_pos(fb, rngs("pos|" + name))
    fb.rules.update(saved)
    plain_rows = sorted(c for c, r in saved.items() if not r["bait"])
    bait_rows = sorted(c for c, r in saved.items() if r["bait"])
    assign_rows(fb, rngs("rows|" + name), plain_rows, share=0.05)
    assign_rows(fb, rngs("baitrows|" + name), bait_rows, share=0.010)
    return fb


PROSE_FMT = {"md", "html", "docx", "pdf"}


def build_all(W, seed):
    rngs = lambda t: derive(seed, "file|" + t)
    FB._W = W
    return [build_file(W, s, rngs) for s in SPECS(W)]


# ---------------------------------------------------------------------------------
# the eight standing documents
# ---------------------------------------------------------------------------------
DOC_TABLE = {d: (title, ["rid", "par", "val", "at", "fa", "fb"], None) for d, title in (
    (POL, "Clause schedule"), (SC, "Source convention register"),
    (CT, "Control totals"), (FP, "Field precedence"),
    (ER, "Errata register"), (RM, "Review decisions"),
    (MD, "Metric definitions"), (MA, "Methodology appendix"))}


def _dec(fr):
    return f"{float(fr):.2f}"


def prose_for(W, name):
    P = lambda s: ("p", s)
    H = lambda s: ("h", s)
    pm = W.params
    if name == POL:
        floors = [["gold_floor." + v, _dec(W.vendor_gold_min[v])] for v in VENDORS]
        rows = [["parameter", "value"],
                ["collection_window_start", "2025-07-01T00:00:00Z"],
                ["collection_window_end", "2025-10-01T00:00:00Z"],
                ["adjudication_cutoff", "2025-10-03T18:00:00Z"],
                ["gold_min_items", str(pm["gold_min_items"])]] + floors + [
                ["bias_limit", _dec(pm["bias_limit"])],
                ["min_votes", str(pm["min_votes"])],
                ["max_prompt_tokens", str(pm["max_prompt_tokens"])],
                ["max_pair_tokens", str(pm["max_pair_tokens"])],
                ["contamination_hard", str(W.params_contam["hard"])],
                ["contamination_soft", str(W.params_contam["soft"])],
                ["validation_fraction", _dec(pm["validation_fraction"])],
                ["epoch_cap", str(pm["epoch_cap"])],
                ["sequence_length", str(pm["sequence_len"])],
                ["global_batch", str(pm["global_batch"])],
                ["micro_batch", str(pm["micro_batch"])],
                ["warmup_fraction", _dec(pm["warmup_fraction"])],
                ["shard_sequences", str(pm["shard_sequences"])],
                ["min_slice_pairs", str(pm["min_slice_pairs"])],
                ["max_train_contamination_rate", _dec(pm["max_contamination_rate"])],
                ["min_kappa", _dec(pm["min_kappa"])]]
        return [H("Preference corpus release policy R7"),
                P("This policy governs release R7 of the post-training preference corpus. The rules below apply in the order they are written. Where sources disagree, field_precedence.html names the source that governs each field."),
                H("Release parameters"),
                ("t", rows),
                P("The collection window includes its start instant and excludes its end instant. The adjudication cutoff is exclusive."),
                H("Annotator standing"),
                P("A verdict counts toward its annotator's gold calibration when its comparison has a gold answer in gold_set.tsv, unless that gold item was retired at or before the verdict instant. gold_items is the number of such verdicts and gold_hits the number whose chosen side (left or right) names the gold completion; tie and both_bad never hit."),
                P("An annotator is admitted when gold_items is at least gold_min_items and gold_agreement reaches the floor published above for the annotator's vendor; otherwise the annotator is gated. An annotator is biased when the absolute A-side bias exceeds bias_limit."),
                H("Verdict admissibility"),
                P("Every registered verdict is tested against these reasons in this order and reports the first that applies: annotator_gated (its annotator is gated); outside_window (its instant is outside the collection window); freeze_window (its workstation was frozen at that instant, a freeze covering its start instant up to but excluding its end); stale_amendment (its instant is at or before the latest amendment of either completion in the comparison); unbalanced_biased (its annotator is biased and the comparison is not balanced); voided (the errata register voids it and no restore entry names it). A verdict with no applicable reason is admissible."),
                H("Comparison resolution"),
                P("An adjudication is valid when its instant is after the latest amendment of either completion, before the adjudication cutoff, and the review board minutes record it approved. A comparison with a valid adjudication resolves to the adjudicated choice on route adjudicated with margin 1."),
                P("Otherwise a comparison with fewer admissible verdicts than min_votes does not resolve: route insufficient, resolved null, margin null. Otherwise it resolves on route majority to the choice (left, right, tie or both_bad) with the most admissible verdicts. Equal counts are settled by the larger summed confidence, then by the alphabetically first choice. Its margin is the winning count minus the largest count among the other choices, divided by the number of admissible verdicts. A majority of tie or both_bad is a resolution. votes is always the number of admissible verdicts."),
                H("Prompt eligibility"),
                P("Every registered prompt is tested against these reasons in this order and reports the first that applies: retired and opted_out (from the errata register); contaminated (its highest screened similarity is at least contamination_hard); duplicate (it belongs to a near duplicate cluster and is not the cluster's canonical member, which is the member with the earliest effective registration, ties going to the lowest prompt id); over_length (its tokens exceed max_prompt_tokens); no_resolved_pair (none of its comparisons resolved to left or right). A prompt with no applicable reason is eligible."),
                H("Preference pairs"),
                P("Every comparison resolved to left or right whose prompt is eligible yields a pair: chosen is the completion on the resolved side and rejected the other. tokens is the prompt's tokens plus both completions' tokens; a pair whose tokens exceed max_pair_tokens is not released. margin and route are the comparison's."),
                H("Split"),
                P("Splits are assigned per prompt family over the families that have released pairs. A prompt is soft contaminated when its highest screened similarity is at least contamination_soft and below contamination_hard. Every family holding a soft contaminated prompt goes to validation first. The remaining families, in ascending family id, go to validation while the validation pair count is below validation_fraction times the total released pairs, and to train after that."),
                H("Mixture, packing and schedule"),
                P("The mixture runs over train pairs only, with the targets in mixture_targets.xlsx and the capping procedure in methodology_appendix.pdf. Packing takes train pairs in ascending pair id: a pair longer than sequence_length is dropped; otherwise it joins the current sequence when it fits and starts a new sequence when it does not. Optimizer steps are the sequence count divided by global_batch, rounded down; the remainder is the dropped tail. Warmup steps are warmup_fraction times the optimizer steps, rounded to the nearest integer with halves to even. Shards are the sequence count divided by shard_sequences, rounded up."),
                H("Release gates"),
                P("min_slice_pairs_met holds when no slice has fewer than min_slice_pairs pairs; no_family_straddles_split holds when every family's pairs sit in one split; train_contamination_within_limit holds when train pairs on soft or hard contaminated prompts, divided by all released pairs, is at most max_train_contamination_rate; kappa_above_floor holds when the reported overall kappa is at least min_kappa; packing_efficiency_reported holds when packing produced at least one sequence. release_approved holds when all five hold.")]
    if name == SC:
        reg = [["entity", "registry", "registered form"],
               ["prompt", "prompt_registry.csv", "PRM-00001"], ["completion", "completion_index.csv", "CMP-000001"],
               ["comparison", "batch_registry.xml", "CMR-000001"], ["verdict", "annotation_store.db", "VD-0000001"],
               ["annotator", "annotator_roster.csv", "ANN-0001"], ["cluster", "dedup_clusters.tsv", "DUP-0001"],
               ["family", "prompt_registry.csv", "PF-0001"], ["workstation", "workstation_inventory.ini", "ws-0001"]]
        conv = [["convention", "reading"],
                ["identifier variants", "An identifier written in the other letter case, with its zero padding stripped, with one Cyrillic look-alike letter, with full-width digits, or wrapped in non-breaking or trailing spaces names the registered identifier."],
                ["record layout", "Every export carries records with the columns rid, par, val, at, fa and fb. A header band may rename them rec, pnt, val, ts, a and b; the columns underneath are the same. A header band can change in the middle of a file."],
                ["scaled values", "A val column headed val_x1000 carries one thousand times the value."],
                ["grouped numbers", "A dot, comma or space followed by exactly three digits is a thousands separator: 1.234 and 1,234 are both 1234."],
                ["excess precision", "A value with exactly two decimal places carries excess precision and is rounded half to even to a whole number: 12.50 is 12."],
                ["sentinels", "In a non-authoritative copy a val of -1 or N/A is absent, not a value."],
                ["instants", "An instant is written as ISO 8601 UTC, as epoch milliseconds, as a spreadsheet serial day count since 1899-12-30 read to the nearest second, or as workstation local time YYYY-MM-DD HH:MM:SS.mmm."],
                ["local time", "A local instant was read off the clock of the workstation the record names. UTC is the local time minus the zone offset and minus the clock offset that workstation_inventory.ini records for that workstation."],
                ["clock offset", "The fb column of workstation_inventory.ini is the clock offset in seconds; a positive offset means the workstation clock runs ahead."],
                ["text case", "Text cells can arrive upper-cased; compare them without regard to case. Locale codes resolve to de_DE, en_IN, en_US, es_ES, fr_FR and ja_JP."],
                ["byte-order mark", "annotator_roster.csv begins with a UTF-8 byte-order mark that belongs to the file, not to the first field."],
                ["fixed width", "clock_offsets.txt and legacy_verdicts.txt cut every cell to 18 characters, so they never govern an instant."],
                ["mixture targets", "The fb column of mixture_targets.xlsx is the source's target weight in percent."]]
        zones = [["zone", "offset"], ["UTC", "+00:00"], ["Europe/Berlin", "+02:00"], ["America/Chicago", "-05:00"],
                 ["Asia/Kolkata", "+05:30"], ["America/Sao_Paulo", "-03:00"], ["Australia/Sydney", "+10:00"],
                 ["Europe/London", "+01:00"]]
        return [H("Source conventions"),
                P("Each source writes identifiers, numbers and instants in its own way. None of these conventions changes what a value means."),
                H("Registries"), ("t", reg),
                H("Convention register"), ("t", conv),
                H("Zone offsets for the R7 quarter"), ("t", zones)]
    if name == CT:
        rows = [["control", "value"], ["prompts", str(len(W.prompt_ids))],
                ["completions", str(len(W.completion_ids))], ["comparisons", str(len(W.comparison_ids))],
                ["verdicts", str(len(W.verdict_ids))]]
        return [H("Control totals"),
                P("Registered entity counts published by data operations for the R7 close."),
                ("t", rows)]
    if name == FP:
        V = ("verdicts_vendor_a.jsonl (calder), verdicts_vendor_b.jsonl (northwind), "
             "verdicts_shard1.parquet (orbit) or verdicts_shard2.parquet (tessel), by the annotator's vendor")
        rows = [["field", "governing source", "column"],
                ["prompt id, family, tokens, registered instant", "prompt_registry.csv", "rid, par, val, at"],
                ["prompt domain, source", "prompt_registry.csv", "fa, fb"],
                ["prompt locale, difficulty", "slice_attributes.csv", "fa, fb"],
                ["prompt risk", "prompt_locales.tsv", "fa"],
                ["prompt retirement, opt-out", "errata_register.docx", "rid, fa"],
                ["completion id, prompt, tokens, created instant, policy", "completion_index.csv", "rid, par, val, at, fa"],
                ["completion amendment instant", "completion_amendments.xml", "rid, at"],
                ["comparison id, prompt, left, right", "batch_registry.xml", "rid, par, fa, fb"],
                ["comparison order, batch", "run_configs.toml", "fa, fb"],
                ["comparison balanced or single", "harness_events.log", "fb"],
                ["verdict id, comparison, confidence, instant", "annotation_store.db", "rid, par, val, at"],
                ["verdict annotator, workstation", "annotation_store.db", "fa, fb"],
                ["verdict choice", V, "fb"],
                ["verdict void, restore", "errata_register.docx", "rid, fa"],
                ["annotator id, vendor, cohort, seniority", "annotator_roster.csv", "rid, par, fa, fb"],
                ["gold answer", "gold_set.tsv", "rid, fb"],
                ["gold retirement and its instant", "gold_answers_revised.csv", "rid, fa, at"],
                ["adjudication reviewer, instant, choice", "adjudications.jsonl", "rid, par, at, fa"],
                ["adjudication approval", "review_minutes.docx", "rid, fa"],
                ["freeze windows", "freeze_windows.ics", "X-WORKSTATION, DTSTART, X-HOURS"],
                ["workstation zone, clock offset", "workstation_inventory.ini", "fa, fb"],
                ["contamination similarity", "contamination_hits.jsonl", "rid, val"],
                ["cluster membership, effective registration", "dedup_clusters.tsv", "rid, par, at"],
                ["mixture target", "mixture_targets.xlsx", "fa, fb"],
                ["slice keys", "slice_definitions.yaml", "rid"]]
        return [H("Field precedence"),
                P("Authority runs per field, not per file. A source that governs one field does not govern its neighbours. gold_answers_revised.csv, locale_codes_legacy.tsv, verdicts_rescored.jsonl, corpus_prelim.xlsx, release_snapshot.json, batch_registry_export.xml, verdicts_staging.parquet and annotation_store_mirror.db are non-authoritative copies; only the field named for one of them below is taken from it."),
                ("t", rows)]
    if name == ER:
        return [H("Errata register"),
                P("Retire, opt-out, void and restore entries recorded for the R7 close. The fa column names the action. A verdict that a void entry names is voided unless a restore entry also names it."),]
    if name == RM:
        return [H("Review board minutes"),
                P("Decisions on adjudications. An adjudication is approved only when a row here records approved for its comparison; deferred, or no row at all, means it is not approved.")]
    if name == MD:
        return [H("Metric definitions"),
                P("gold_agreement is gold_hits divided by gold_items. a_side_bias is the share of left among an annotator's left and right verdicts on balanced comparisons, minus 0.5; balanced_verdicts counts those verdicts."),
                P("Agreement is computed over rated units: comparisons with at least two admissible verdicts. Both_bad folds into tie for agreement, and only for agreement. With n ratings in a unit and n_c in category c, observed_agreement is the sum over units of the sum over c of n_c(n_c-1), divided by the sum over units of n(n-1). rater_pairs is the sum of n(n-1)/2 and rated_units the number of units. The expected agreement is the sum over categories of the squared share of that category among all ratings in the units, and kappa is observed minus expected, divided by one minus expected (0 when expected is 1)."),
                P("by_domain groups units by the prompt's domain. by_vendor forms a unit from one vendor's admissible verdicts on a rated unit when there are at least two of them."),
                P("Every reported ratio is quantised to six places, half to even, at the reporting step and at no earlier step. A ratio whose denominator is zero does not exist and is reported as null.")]
    return [H("Methodology appendix"),
            P("Position bias is estimated only over balanced comparisons, those issued in both presentation orders. A bias estimated over all verdicts is not the published figure."),
            P("Mixture capping. available_pairs is a source's train pairs, the budget is all train pairs, and a source's cap is epoch_cap times its available pairs. Every source with available pairs starts free and the whole budget is unallocated. Each free source is offered the unallocated budget times its target divided by the sum of the free sources' targets. Every free source offered more than its cap is fixed at its cap and its cap leaves the unallocated budget; the offer is then repeated. When no free source is offered more than its cap, each free source keeps its offer."),
            P("allocated_pairs is the whole part of the allocation, effective_weight the allocation divided by the budget, epochs the allocation divided by available_pairs, and capped is true for a source fixed at its cap. A source with no available pairs is allocated 0 and is not capped. The _total entry carries budget_pairs and allocated_pairs, the sum of the sources' allocated_pairs.")]


def attach_doc(fb):
    title, ha, hb = DOC_TABLE[fb.name]
    fb.table = (title, ha, hb)
    fb.cells = lambda row, lay, _fb=fb: cells(_fb, row, _fb.tag)


def render_file(W, fb):
    if fb.fmt in PROSE_FMT:
        attach_doc(fb)
        return render_doc(fb, prose_for(W, fb.name), {}, fb.fmt)
    return RENDER[fb.fmt](fb, fb.tag)


def generate_corpus(seed, scale=1.0):
    W = build_world(seed, scale)
    fbs = build_all(W, seed)
    return {fb.name: render_file(W, fb) for fb in fbs}, W, fbs


def build_truth(W):
    st = annotator_standing(W)
    adm = verdict_admissibility(W, st)
    res = resolve_comparisons(W, adm)
    el = prompt_eligibility(W, res)
    pp = preference_pairs(W, res, el)
    ag = agreement(W, adm)
    dd = dedup_report(W, el)
    sp = split_assignment(W, pp)
    mx = mixture_plan(W, pp, sp)
    pk = packing_plan(W, pp, sp)
    sc = training_schedule(W, pk)
    sl = slice_coverage(W, pp, sp)
    rg = release_gates(W, pp, sp, ag, pk, sl)
    return {
        "annotator_standing.json": st,
        "verdict_admissibility.jsonl": [dict(v, verdict_id=k) for k, v in sorted(adm.items())],
        "comparison_resolution.jsonl": [dict(v, comparison_id=k) for k, v in sorted(res.items())],
        "agreement.json": ag,
        "prompt_eligibility.jsonl": [dict(v, prompt_id=k) for k, v in sorted(el.items())],
        "dedup_clusters.json": dd,
        "preference_pairs.jsonl": pp,
        "split_assignment.json": sp,
        "mixture_plan.json": mx,
        "packing_plan.json": pk,
        "training_schedule.json": sc,
        "slice_coverage.json": sl,
        "release_gates.json": rg,
    }


def generate_all(seed, scale=1.0):
    W = build_world(seed, scale)
    fbs = build_all(W, seed)
    files = {fb.name: render_file(W, fb) for fb in fbs}
    truth = build_truth(W)
    truth["source_audit.json"] = {fb.name: {"rows": len(fb.rows)} for fb in fbs}
    truth["control_reconciliation.json"] = {
        "prompts": len(W.prompt_ids), "completions": len(W.completion_ids),
        "comparisons": len(W.comparison_ids), "verdicts": len(W.verdict_ids),
        "admissible": sum(1 for v in truth["verdict_admissibility.jsonl"] if v["admissible"]),
        "resolved": sum(1 for v in truth["comparison_resolution.jsonl"] if v["resolved"]),
        "eligible": sum(1 for v in truth["prompt_eligibility.jsonl"] if v["eligible"]),
        "pairs": len(truth["preference_pairs.jsonl"])}
    return files, truth


# ===== CORPUS GENERATOR END =====

_CACHE: dict = {}
_LOCK = _threading.RLock()
JSONL = {"verdict_admissibility.jsonl": "verdict_id", "comparison_resolution.jsonl": "comparison_id",
         "prompt_eligibility.jsonl": "prompt_id", "preference_pairs.jsonl": "pair_id"}
OUTPUTS = ["annotator_standing.json", "verdict_admissibility.jsonl", "comparison_resolution.jsonl",
           "agreement.json", "prompt_eligibility.jsonl", "dedup_clusters.json",
           "preference_pairs.jsonl", "split_assignment.json", "mixture_plan.json",
           "packing_plan.json", "training_schedule.json", "slice_coverage.json",
           "source_audit.json", "control_reconciliation.json", "release_gates.json"]


def _norm(o):
    return _json.loads(_json.dumps(o, sort_keys=True, default=str))


def _corpus(seed, scale):
    key = (seed, scale)
    with _LOCK:
        if key not in _CACHE:
            files, truth = generate_all(seed, scale)
            _CACHE[key] = (files, _norm(truth))
        return _CACHE[key]


def _visible_truth():
    return _corpus(SAMPLE_SEED, VISIBLE_SCALE)[1]


def _hidden_truth():
    return _corpus(EVAL_SEED, HIDDEN_SCALE)[1]


def _root_only_tests_present() -> bool:
    try:
        st = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return st.st_uid == 0 and (st.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    if not argument.startswith(str(APP_ROOT)):
        return
    p = Path(argument)
    if not p.exists():
        return
    try:
        p.chmod(p.stat().st_mode | (0o555 if p.is_dir() else 0o444))
        for parent in p.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if parent == APP_ROOT:
                break
    except OSError:
        pass


def _untrusted_command(command: list) -> list:
    if _os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid dropping")
    if _os.name == "posix" and _os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code")
    if _os.name == "posix" and _os.geteuid() == 0:
        for a in command:
            _grant_read(a)
        return [*_SETPRIV, *command]
    return command


def _write_dir(files, root: Path, *, writable: bool = False) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (root / name).write_bytes(data)
    for p in [root, *root.rglob("*")]:
        if writable:
            p.chmod(0o777 if p.is_dir() else 0o666)
        else:
            p.chmod(0o755 if p.is_dir() else 0o644)


def _snapshot(root: Path):
    return {str(p.relative_to(root)): _hl.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _parse(name, text):
    if name.endswith(".jsonl"):
        return [_json.loads(x) for x in text.splitlines() if x.strip()]
    return _json.loads(text)


def _read_outputs(out: Path):
    return {n: _parse(n, (out / n).read_text(encoding="utf-8")) for n in OUTPUTS}


SPEED_RATIO = 2.0
GATE_SHARE = 0.95
BASELINE_RUNS = 3

_BASELINE = r'''
import csv, io, json, re, sqlite3, sys, tomllib, zipfile, zlib
import xml.etree.ElementTree as ET
from pathlib import Path


def decode(path):
    raw = path.read_bytes()
    ext = path.suffix
    if ext in (".csv", ".tsv"):
        text = raw.decode("utf-8-sig", "replace")
        return list(csv.reader(io.StringIO(text), delimiter="\t" if ext == ".tsv" else ","))
    if ext == ".jsonl":
        return [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
    if ext == ".json":
        return json.loads(raw)
    if ext == ".xml":
        return ET.fromstring(raw)
    if ext == ".toml":
        return tomllib.loads(raw.decode("utf-8"))
    if ext == ".yaml":
        import yaml
        return yaml.safe_load(raw)
    if ext == ".db":
        con = sqlite3.connect(":memory:")
        con.deserialize(raw)
        return con.execute("SELECT * FROM records").fetchall()
    if ext == ".parquet":
        import pyarrow as pa
        import pyarrow.parquet as pq
        return pq.read_table(pa.BufferReader(raw)).to_pylist()
    if ext in (".xlsx", ".docx"):
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            return [ET.fromstring(zf.read(n)) for n in zf.namelist() if n.endswith(".xml")]
    if ext == ".pdf":
        return [zlib.decompress(m) for m in re.findall(rb"stream\n(.*?)\nendstream", raw, re.S)]
    return raw.decode("utf-8", "replace").splitlines()


for p in sorted(Path(sys.argv[1]).iterdir()):
    decode(p)
'''


def _timed(command: list, env: dict):
    t0 = _time.perf_counter_ns()
    proc = _sp.Popen(command, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, env=env, start_new_session=True)
    try:
        rc = proc.wait(timeout=RUN_TIMEOUT)
    except _sp.TimeoutExpired:
        rc = -9
    finally:
        try:
            _os.killpg(proc.pid, _signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
    return rc, _time.perf_counter_ns() - t0


def _child_env(tmp_dir: Path | None = None) -> dict:
    """Give submitted code only the process settings needed for a local run."""
    env = {
        "PATH": _os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": _os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": _os.environ.get("LC_ALL", "C.UTF-8"),
        "PYTHONHASHSEED": "0",
    }
    if "TZ" in _os.environ:
        env["TZ"] = _os.environ["TZ"]
    if tmp_dir is not None:
        env["TMPDIR"] = str(tmp_dir)
    return env


def _run(data_dir: Path, out_dir: Path, tmp_dir: Path):
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    out_dir.parent.chmod(0o777)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.chmod(0o777)
    return _timed(
        _untrusted_command([_sys.executable, str(PROGRAM), str(data_dir), str(out_dir)]),
        _child_env(tmp_dir),
    )


def _baseline(data_dir: Path, base: Path):
    script = base / "baseline.py"
    script.write_text(_BASELINE, encoding="utf-8")
    script.chmod(0o644)
    out = []
    for _ in range(BASELINE_RUNS):
        rc, ns = _timed(
            _untrusted_command([_sys.executable, str(script), str(data_dir)]),
            _child_env(),
        )
        if rc == 0:
            out.append(ns)
    return out


def _traced_external_reads(data_dir: Path, out_dir: Path, tmp_dir: Path, trace: Path):
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    out_dir.parent.chmod(0o777)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.chmod(0o777)
    trace.touch()
    trace.chmod(0o666)
    command = [
        "strace", "-f", "-e", "trace=open,openat,openat2", "-o", str(trace),
        _sys.executable, str(PROGRAM), str(data_dir), str(out_dir),
    ]
    rc, _ = _timed(_untrusted_command(command), _child_env(tmp_dir))
    if rc != 0:
        return []

    # /app/data is owned by the dedicated default-path negative, so exclude it
    # here to prevent one fixed-path read from stacking two penalties.
    scope_roots = tuple(str(p.resolve()) for p in (data_dir, out_dir, APP_ROOT / "data"))
    allowed_exact = {
        str(PROGRAM.resolve()), str(PROGRAM.parent.resolve()), str(trace.resolve()), *scope_roots
    }
    allowed_roots = tuple(path + "/" for path in scope_roots)
    runtime_roots = ("/usr/", "/lib/", "/proc/", "/sys/", "/dev/", "/etc/")
    # Direct grader-file access is owned by judged criterion R7.  The dropped
    # UID cannot read these paths, and excluding them prevents penalty stacking.
    judge_owned_roots = ("/tests/", "/logs/")
    external = []
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _re.search(r'\bopen(?:at2|at)?\([^\"]*\"((?:\\.|[^\"])*)\"(.*?)\)\s+=\s+(-?\d+)', line)
        if not match or int(match.group(3)) < 0 or "O_WRONLY" in match.group(2):
            continue
        try:
            path = _json.loads('"' + match.group(1) + '"')
        except ValueError:
            external.append(match.group(1))
            continue
        if not path.startswith("/"):
            candidate = (data_dir / path).resolve()
            if candidate.is_file() and str(candidate).startswith(allowed_roots[0]):
                continue
            external.append(path)
            continue
        normalized = str(Path(path).resolve())
        if normalized in allowed_exact or normalized.startswith(
            (*allowed_roots, *runtime_roots, *judge_owned_roots)
        ):
            continue
        external.append(normalized)
    return sorted(set(external))


def _eval_runs():
    with _LOCK:
        if "eval" in _CACHE:
            return _CACHE["eval"]
        res = {"rc": [], "out": [], "ns": [], "ref_ns": [], "outside": [],
               "external_reads": [], "before": {}, "after": {}}
        _CACHE["eval"] = res
        if not PROGRAM.is_file():
            return res
        files, _ = _corpus(EVAL_SEED, HIDDEN_SCALE)
        canary = APP_ROOT / "data"
        if not canary.exists():
            _write_dir(_corpus(CHALLENGE_SEED, HIDDEN_SCALE)[0], canary)
        base = Path(_tf.mkdtemp(prefix="rlhf-eval-"))
        base.chmod(0o777)
        a, b = base / "in-a" / "corpus", base / "in-b" / "renamed"
        # The submitted process runs as nobody.  Evaluation inputs must be
        # writable by that UID so the input-mutation negative can actually
        # observe the prohibited behavior rather than relying on EACCES.
        _write_dir(files, a, writable=True)
        _write_dir(files, b, writable=True)
        ref = Path(_tf.mkdtemp(prefix="rlhf-ref-"))
        ref.chmod(0o777)
        _write_dir(files, ref / "corpus")
        try:
            res["ref_ns"] = _baseline(ref / "corpus", ref)
        except (OSError, _sp.SubprocessError, RuntimeError):
            res["ref_ns"] = []
        (base / "tmp").mkdir()
        trace = base / "tmp" / "read-trace.log"
        trace.touch()
        trace.chmod(0o666)
        before = _snapshot(base)
        res["before"] = _snapshot(a)
        for data, out in ((a, base / "o1" / "out"), (a, base / "o2" / "out"), (b, base / "o3" / "out")):
            if res["rc"] and res["rc"][0] == -9:
                rc, ns = -9, 0
            else:
                try:
                    rc, ns = _run(data, out, base / "tmp")
                except (OSError, _sp.SubprocessError, RuntimeError):
                    rc, ns = -1, 0
            res["rc"].append(rc)
            res["ns"].append(ns)
            res["out"].append(out)
        try:
            res["external_reads"] = _traced_external_reads(
                a, base / "o4" / "out", base / "tmp", trace
            )
        except (OSError, _sp.SubprocessError, RuntimeError):
            res["external_reads"] = []
        after = _snapshot(base)
        allowed = tuple(f"o{i}/out/" for i in (1, 2, 3, 4))
        # Input-directory writes belong solely to negative_modifies_input_corpus;
        # exclude them here so one act cannot stack two path-scope penalties.
        inputs = ("in-a/corpus/", "in-b/renamed/")
        res["outside"] = [p for p in after if p not in before
                          and not p.startswith((*allowed, *inputs))]
        res["after"] = _snapshot(a)
        return res


def _hidden():
    r = _eval_runs()
    if not r["rc"] or r["rc"][0] != 0:
        raise AssertionError("program failed on the hidden corpus")
    with _LOCK:
        if "hid_out" not in _CACHE:
            _CACHE["hid_out"] = _read_outputs(r["out"][0])
        return _CACHE["hid_out"]


def _visible():
    with _LOCK:
        if "vis" not in _CACHE:
            _CACHE["vis"] = _read_outputs(OUT_DIR)
        return _CACHE["vis"]


def _visible_world():
    with _LOCK:
        if "vis_world" not in _CACHE:
            _CACHE["vis_world"] = build_world(SAMPLE_SEED, VISIBLE_SCALE)
        return _CACHE["vis_world"]


def _same(a, b):
    if isinstance(b, bool) or isinstance(a, bool):
        return type(a) is bool and type(b) is bool and a == b
    if isinstance(b, int):
        return type(a) is int and a == b
    if isinstance(b, float):
        return type(a) is float and a == b
    if isinstance(b, dict):
        return isinstance(a, dict) and set(a) == set(b) and all(_same(a[k], b[k]) for k in b)
    if isinstance(b, list):
        return isinstance(a, list) and len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


def _need(condition, message="value differs"):
    if not condition:
        raise AssertionError(message)


def _by_id(rows, name):
    key = JSONL[name]
    out = {}
    for r in rows:
        _need(isinstance(r, dict) and key in r, "row shape")
        out[r[key]] = r
    return out


def _rowcmp(got, exp, name, fields):
    _cmp_rows(_by_id(got[name], name), exp[name], JSONL[name], fields)


def _cmp_rows(got_map, exp_rows, key, fields):
    exp = {r[key]: r for r in exp_rows}
    _need(set(got_map) == set(exp), "row set differs")
    for k, row in exp.items():
        _need(set(got_map[k]) == set(row), "row shape differs")
        for f in fields:
            _need(f in got_map[k] and _same(got_map[k][f], row[f]))


def _gate(got_map, exp_map, field):
    _need(set(got_map) == set(exp_map), "row set differs")
    agree = sum(1 for k in exp_map if _same(field(got_map[k]), field(exp_map[k])))
    _need(not exp_map or agree / len(exp_map) >= GATE_SHARE, "upstream stage too far from the release")


def _pick(name, fn):
    return lambda g, e: _need(_same(fn(g[name]), fn(e[name])))


def _vis(fn):
    fn(_visible(), _visible_truth())


def _hid(fn):
    fn(_hidden(), _hidden_truth())


# Each later stage is graded on the agent's own upstream artifact, recomputed
# with the published rules, so one upstream mistake costs that stage and not
# the whole chain. An upstream artifact must still sit within GATE_SHARE of the
# release, or a degenerate pipeline would grade as consistent.
def _upstream_standing():
    g = _visible()["annotator_standing.json"]
    e = _visible_truth()["annotator_standing.json"]
    _need(isinstance(g, dict) and all(isinstance(v, dict) for v in g.values()))
    _gate(g, e, lambda v: (v.get("standing"), v.get("biased")))
    return {a: {"standing": v["standing"], "biased": v["biased"] is True} for a, v in g.items()}


def _upstream_admissibility():
    g = _by_id(_visible()["verdict_admissibility.jsonl"], "verdict_admissibility.jsonl")
    e = _by_id(_visible_truth()["verdict_admissibility.jsonl"], "verdict_admissibility.jsonl")
    _gate(g, e, lambda v: v.get("admissible"))
    return {k: {"admissible": v["admissible"] is True} for k, v in g.items()}


def _upstream_resolution():
    g = _by_id(_visible()["comparison_resolution.jsonl"], "comparison_resolution.jsonl")
    e = _by_id(_visible_truth()["comparison_resolution.jsonl"], "comparison_resolution.jsonl")
    _gate(g, e, lambda v: v.get("resolved"))
    return {k: {"resolved": v["resolved"], "route": v.get("route"), "margin": v.get("margin")}
            for k, v in g.items()}


def _upstream_eligibility():
    g = _by_id(_visible()["prompt_eligibility.jsonl"], "prompt_eligibility.jsonl")
    e = _by_id(_visible_truth()["prompt_eligibility.jsonl"], "prompt_eligibility.jsonl")
    _gate(g, e, lambda v: v.get("eligible"))
    return {k: {"eligible": v["eligible"] is True} for k, v in g.items()}


def _upstream_pairs():
    W = _visible_world()
    g = _by_id(_visible()["preference_pairs.jsonl"], "preference_pairs.jsonl")
    rows = []
    for pid, r in g.items():
        cid = r.get("comparison")
        cm = W.comparisons.get(cid) if isinstance(cid, str) else None
        _need(cm is not None and pid == "PP-" + cid.split("-")[1], "pair identity")
        chosen, rejected = r.get("chosen"), r.get("rejected")
        _need(chosen != rejected and {chosen, rejected} == {cm["left"], cm["right"]}, "pair sides")
        p = cm["prompt"]
        rows.append({"pair_id": pid, "comparison": cid, "prompt": p,
                     "family": W.prompts[p]["family"], "source": W.prompts[p]["source"],
                     "tokens": W.prompts[p]["tokens"] + W.completions[chosen]["tokens"]
                     + W.completions[rejected]["tokens"]})
    got = {x["comparison"] for x in rows}
    want = {x["comparison"] for x in _visible_truth()["preference_pairs.jsonl"]}
    union = got | want
    _need(not union or len(got & want) / len(union) >= GATE_SHARE, "upstream stage too far from the release")
    rows.sort(key=lambda x: x["pair_id"])
    return rows


def _upstream_split():
    pairs = _stage("pairs")
    fams = _visible()["split_assignment.json"]["families"]
    _need(isinstance(fams, dict) and all(fams.get(x["family"]) in ("train", "validation") for x in pairs))
    want = _visible_truth()["split_assignment.json"]["families"]
    _gate({k: fams.get(k) for k in want}, want, lambda v: v)
    return {"families": fams}


def _upstream_packing():
    pack = _visible()["packing_plan.json"]
    _need(isinstance(pack, dict) and type(pack.get("sequences")) is int)
    want = _expected("packing")["sequences"]
    _need(abs(pack["sequences"] - want) <= (1 - GATE_SHARE) * max(want, 1), "upstream stage too far from the release")
    return pack


def _upstream_agreement():
    _stage("admissibility")
    agree = _visible()["agreement.json"]
    _need(isinstance(agree, dict) and isinstance(agree.get("overall"), dict))
    return agree


def _upstream_slices():
    _stage("split")
    slices = _visible()["slice_coverage.json"]
    _need(isinstance(slices, dict) and all(isinstance(v, dict) and type(v.get("pairs")) is int
                                           for v in slices.values()))
    want = _expected("slices")
    _gate({k: slices.get(k, {}) for k in want}, want, lambda v: v.get("pairs"))
    return slices


_UPSTREAM = {"standing": _upstream_standing, "admissibility": _upstream_admissibility,
             "resolution": _upstream_resolution, "eligibility": _upstream_eligibility,
             "pairs": _upstream_pairs, "split": _upstream_split, "packing": _upstream_packing,
             "agreement": _upstream_agreement, "slices": _upstream_slices}


def _stage(name):
    with _LOCK:
        key = "stage:" + name
        if key not in _CACHE:
            try:
                _CACHE[key] = (True, _UPSTREAM[name]())
            except Exception:
                _CACHE[key] = (False, None)
        ok, value = _CACHE[key]
    _need(ok, "upstream stage unavailable")
    return value


def _expected(name):
    W = _visible_world()
    with _LOCK:
        key = "expect:" + name
        if key not in _CACHE:
            try:
                _CACHE[key] = (True, _norm(_EXPECT[name](W)))
            except Exception:
                _CACHE[key] = (False, None)
        ok, value = _CACHE[key]
    _need(ok, "expected stage unavailable")
    return value


_EXPECT = {
    "admissibility": lambda W: [dict(v, verdict_id=k) for k, v in
                                sorted(verdict_admissibility(W, _stage("standing")).items())],
    "resolution": lambda W: [dict(v, comparison_id=k) for k, v in
                             sorted(resolve_comparisons(W, _stage("admissibility")).items())],
    "agreement": lambda W: agreement(W, _stage("admissibility")),
    "eligibility": lambda W: [dict(v, prompt_id=k) for k, v in
                              sorted(prompt_eligibility(W, _stage("resolution")).items())],
    "pairs": lambda W: preference_pairs(W, _stage("resolution"), _stage("eligibility")),
    "split": lambda W: split_assignment(W, _stage("pairs")),
    "mixture": lambda W: mixture_plan(W, _stage("pairs"), _stage("split")),
    "packing": lambda W: packing_plan(W, _stage("pairs"), _stage("split")),
    "schedule": lambda W: training_schedule(W, _stage("packing")),
    "slices": lambda W: slice_coverage(W, _stage("pairs"), _stage("split")),
    "gates": lambda W: release_gates(W, _stage("pairs"), _stage("split"), _stage("agreement"),
                                     _stage("packing"), _stage("slices")),
}


def _staged_rows(artifact, stage, fields):
    got = _by_id(_visible()[artifact], artifact)
    _cmp_rows(got, _expected(stage), JSONL[artifact], fields)


def _staged_value(artifact, stage, fn):
    _need(_same(fn(_visible()[artifact]), fn(_expected(stage))))


def _check_standing_gold_agreement():
    _vis(_pick('annotator_standing.json', lambda d: {k: v['gold_agreement'] for k, v in d.items()}))

def _check_standing_gold_counts():
    _vis(_pick('annotator_standing.json', lambda d: {k: (v['gold_items'], v['gold_hits']) for k, v in d.items()}))

def _check_standing_position_bias():
    _vis(_pick('annotator_standing.json', lambda d: {k: (v['a_side_bias'], v['balanced_verdicts']) for k, v in d.items()}))

def _check_standing_decision():
    _vis(_pick('annotator_standing.json', lambda d: {k: (v['standing'], v['biased'], v['vendor']) for k, v in d.items()}))

def _check_admissibility_flags():
    _staged_rows('verdict_admissibility.jsonl', 'admissibility', ['admissible', 'comparison', 'annotator'])

def _check_admissibility_reasons():
    _staged_rows('verdict_admissibility.jsonl', 'admissibility', ['reason'])

def _check_resolution_verdicts():
    _staged_rows('comparison_resolution.jsonl', 'resolution', ['resolved'])

def _check_resolution_routes():
    _staged_rows('comparison_resolution.jsonl', 'resolution', ['route'])

def _check_resolution_margins():
    _staged_rows('comparison_resolution.jsonl', 'resolution', ['margin', 'votes'])

def _check_agreement_overall():
    _staged_value('agreement.json', 'agreement', lambda d: d['overall'])

def _check_agreement_by_vendor():
    _staged_value('agreement.json', 'agreement', lambda d: d['by_vendor'])

def _check_agreement_by_domain():
    _staged_value('agreement.json', 'agreement', lambda d: d['by_domain'])

def _check_eligibility_flags():
    _staged_rows('prompt_eligibility.jsonl', 'eligibility', ['eligible', 'cluster', 'family', 'source'])

def _check_eligibility_reasons():
    _staged_rows('prompt_eligibility.jsonl', 'eligibility', ['reason'])

def _check_dedup_canonicals():
    _vis(_pick('dedup_clusters.json', lambda d: {k: (v['canonical'], v['canonical_effective_at']) for k, v in d.items()}))

def _check_dedup_members():
    _vis(_pick('dedup_clusters.json', lambda d: {k: (v['members'], v['dropped']) for k, v in d.items()}))

def _check_pairs_chosen_rejected():
    _staged_rows('preference_pairs.jsonl', 'pairs', ['chosen', 'rejected'])

def _check_pairs_provenance():
    _staged_rows('preference_pairs.jsonl', 'pairs', ['comparison', 'prompt', 'family', 'source', 'route'])

def _check_pairs_margin_tokens():
    _staged_rows('preference_pairs.jsonl', 'pairs', ['margin', 'tokens'])

def _check_split_families():
    _staged_value('split_assignment.json', 'split', lambda d: d['families'])

def _check_split_counts():
    _staged_value('split_assignment.json', 'split', lambda d: (d['family_counts'], d['pair_counts'], d['validation_share']))

def _check_mixture_allocation():
    _staged_value('mixture_plan.json', 'mixture', lambda d: {k: v['allocated_pairs'] for k, v in d.items() if k != '_total'})

def _check_mixture_epochs():
    _staged_value('mixture_plan.json', 'mixture', lambda d: {k: (v['epochs'], v['capped']) for k, v in d.items() if k != '_total'})

def _check_mixture_weights():
    _staged_value('mixture_plan.json', 'mixture', lambda d: {k: (v['target_weight'], v['effective_weight']) for k, v in d.items() if k != '_total'})

def _check_packing_sequences():
    _staged_value('packing_plan.json', 'packing', lambda d: (d['sequence_length'], d['sequences'], d['packed_pairs'], d['dropped_pairs']))

def _check_packing_tokens():
    _staged_value('packing_plan.json', 'packing', lambda d: (d['token_capacity'], d['tokens_used'], d['padding_tokens'], d['packing_efficiency']))

def _check_schedule_steps():
    _staged_value('training_schedule.json', 'schedule', lambda d: (d['optimizer_steps'], d['warmup_steps']))

def _check_schedule_shape():
    _staged_value('training_schedule.json', 'schedule', lambda d: (d['gradient_accumulation'], d['shards'], d['dropped_tail_sequences']))

def _check_slice_pair_counts():
    _staged_value('slice_coverage.json', 'slices', lambda d: {k: v['pairs'] for k, v in d.items()})

def _check_slice_split_tokens():
    _staged_value('slice_coverage.json', 'slices', lambda d: {k: (v['train'], v['validation'], v['tokens']) for k, v in d.items()})

SOURCE_AUDIT_GOVERNING = (
    'adjudications.jsonl', 'annotation_store.db', 'annotator_roster.csv',
    'batch_registry.xml', 'completion_amendments.xml', 'completion_index.csv',
    'contamination_hits.jsonl', 'dedup_clusters.tsv', 'errata_register.docx',
    'freeze_windows.ics', 'gold_answers_revised.csv', 'gold_set.tsv',
    'harness_events.log', 'mixture_targets.xlsx', 'prompt_locales.tsv',
    'prompt_registry.csv', 'review_minutes.docx', 'run_configs.toml',
    'slice_attributes.csv', 'slice_definitions.yaml', 'verdicts_shard1.parquet',
    'verdicts_shard2.parquet', 'verdicts_vendor_a.jsonl',
    'verdicts_vendor_b.jsonl', 'workstation_inventory.ini',
)
SOURCE_AUDIT_OPERATIONAL = (
    'clock_offsets.txt', 'collection_vendor_a.log', 'collection_vendor_b.log',
    'collection_vendor_c.log', 'control_totals.html', 'corpus_policy.md',
    'dataops_notifications.mbox', 'field_precedence.html',
    'methodology_appendix.pdf', 'metric_definitions.pdf',
    'source_conventions.md',
)
SOURCE_AUDIT_REFERENCE = (
    'annotation_standards.xlsx', 'annotation_store_mirror.db',
    'batch_registry_export.xml', 'corpus_prelim.xlsx', 'legacy_verdicts.txt',
    'locale_codes_legacy.tsv', 'packing_config.json', 'release_snapshot.json',
    'token_lengths.csv', 'tokenizer_revisions.json', 'vendor_invoices.xlsx',
    'vendor_tags.yaml', 'verdicts_rescored.jsonl', 'verdicts_staging.parquet',
)


def _check_source_audit_rows(names):
    select = lambda d: {name: d.get(name) for name in names}
    _vis(_pick('source_audit.json', select))
    _hid(_pick('source_audit.json', select))

def _check_control_reconciliation():
    adm = _stage("admissibility")
    res = _stage("resolution")
    elig = _stage("eligibility")
    pairs = _stage("pairs")
    truth = _visible_truth()["control_reconciliation.json"]
    want = {k: truth[k] for k in ("prompts", "completions", "comparisons", "verdicts")}
    want.update(admissible=sum(1 for v in adm.values() if v["admissible"]),
                resolved=sum(1 for v in res.values() if v["resolved"] is not None),
                eligible=sum(1 for v in elig.values() if v["eligible"]),
                pairs=len(pairs))
    _need(_same(_visible()["control_reconciliation.json"], want))

def _check_release_gate_decisions():
    _staged_value('release_gates.json', 'gates', lambda d: d['gates'])

def _check_release_gate_detail():
    _staged_value('release_gates.json', 'gates', lambda d: (d['train_contamination_rate'], d['undersized_slices'], d['total_pairs']))

def _check_hidden_standing():
    _hid(_pick('annotator_standing.json', lambda d: d))

def _check_hidden_resolution():
    _hid(_pick('comparison_resolution.jsonl', lambda d: d))

def _check_hidden_eligibility():
    _hid(_pick('prompt_eligibility.jsonl', lambda d: d))

def _check_hidden_pairs():
    _hid(_pick('preference_pairs.jsonl', lambda d: d))

def _check_hidden_mixture():
    _hid(_pick('mixture_plan.json', lambda d: d))

def _check_hidden_schedule():
    _hid(_pick('training_schedule.json', lambda d: d))

def _check_hidden_gates():
    _hid(_pick('release_gates.json', lambda d: d))

def _check_hidden_artifact(name):
    _hid(_pick(name, lambda d: d))

def _check_outputs_present():
    assert PROGRAM.is_file(), "program missing"
    _visible()


def _check_jsonl_sorted_lf():
    for name, key in JSONL.items():
        raw = (OUT_DIR / name).read_bytes()
        assert raw.endswith(b"\n") and b"\r" not in raw, "line endings"
        keys = [_json.loads(x)[key] for x in raw.decode("utf-8").split("\n") if x]
        assert keys == sorted(keys) and len(keys) == len(set(keys)), "order"


def _keys_sorted(text):
    ordered = [True]

    def hook(pairs):
        keys = [k for k, _ in pairs]
        if keys != sorted(keys):
            ordered[0] = False
        return dict(pairs)

    _json.loads(text, object_pairs_hook=hook)
    return ordered[0]


def _check_json_sorted_keys_lf():
    for name in OUTPUTS:
        if name.endswith(".jsonl"):
            continue
        raw = (OUT_DIR / name).read_bytes()
        assert raw.endswith(b"\n") and b"\r" not in raw, "line endings"
        assert _keys_sorted(raw.decode("utf-8")), "keys not sorted"


def _check_relative_speed():
    """Speed only counts once the build is right: a program that writes nothing
    is fast, so the hidden release must reproduce before the ratio is read."""
    got, exp = _hidden(), _hidden_truth()
    _rowcmp(got, exp, "preference_pairs.jsonl", ["chosen", "rejected", "tokens"])
    _rowcmp(got, exp, "comparison_resolution.jsonl", ["resolved", "route"])
    r = _eval_runs()
    assert len(r["ns"]) >= 2 and r["rc"][0] == 0 and r["rc"][1] == 0, "program did not run"
    assert len(r["ref_ns"]) >= 2, "baseline did not run"
    ratio = _stats.median(r["ns"][:2]) / _stats.median(r["ref_ns"])
    assert ratio <= SPEED_RATIO, f"relative median too slow: {ratio}"


def _negative_hardcoded():
    r = _eval_runs()
    if not r["rc"] or r["rc"][0] != 0:
        return False
    got = _read_outputs(r["out"][0])
    vis = _visible_truth()
    return _same(got["preference_pairs.jsonl"], vis["preference_pairs.jsonl"]) or \
        _same(got["prompt_eligibility.jsonl"], vis["prompt_eligibility.jsonl"])


def _negative_filename():
    r = _eval_runs()
    if len(r["rc"]) < 3 or r["rc"][0] != 0 or r["rc"][1] != 0:
        return False
    a, b = _snapshot(r["out"][0]), _snapshot(r["out"][1])
    if a != b:
        return False
    if r["rc"][2] != 0:
        return True
    return a != _snapshot(r["out"][2])


def _negative_reads_default():
    r = _eval_runs()
    if not r["rc"] or r["rc"][0] != 0:
        return False
    got = _read_outputs(r["out"][0])
    can = _corpus(CHALLENGE_SEED, HIDDEN_SCALE)[1]
    return _same(got["comparison_resolution.jsonl"], can["comparison_resolution.jsonl"])


def _negative_nondeterministic():
    r = _eval_runs()
    if len(r["rc"]) < 2 or r["rc"][0] != 0 or r["rc"][1] != 0:
        return False
    return _snapshot(r["out"][0]) != _snapshot(r["out"][1])


def _negative_modifies_input():
    r = _eval_runs()
    if not r["before"]:
        return False
    return r["before"] != r["after"]


def _negative_writes_outside():
    return bool(_eval_runs()["outside"])


def _negative_reads_outside_argument():
    return bool(_eval_runs()["external_reads"])


@criterion(description="annotator_standing.json gives every annotator's gold counts, agreement, position bias, vendor and standing")
def artifact_annotator_standing(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_standing_gold_agreement(),
        _check_standing_gold_counts(),
        _check_standing_position_bias(),
        _check_standing_decision(),
    )))

@criterion(description="verdict_admissibility.jsonl gives every verdict's admissibility fields and first applicable reason")
def artifact_verdict_admissibility(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_admissibility_flags(),
        _check_admissibility_reasons(),
        _check_hidden_artifact('verdict_admissibility.jsonl'),
    )))

@criterion(description="comparison_resolution.jsonl gives every comparison's resolved verdict, route, margin and admissible vote count")
def artifact_comparison_resolution(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_resolution_verdicts(),
        _check_resolution_routes(),
        _check_resolution_margins(),
    )))

@criterion(description="agreement.json gives observed agreement, kappa and rating counts overall, by vendor and by domain")
def artifact_agreement(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_agreement_overall(),
        _check_agreement_by_vendor(),
        _check_agreement_by_domain(),
        _check_hidden_artifact('agreement.json'),
    )))

@criterion(description="prompt_eligibility.jsonl gives every prompt's eligibility fields and first applicable exclusion reason")
def artifact_prompt_eligibility(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_eligibility_flags(),
        _check_eligibility_reasons(),
    )))

@criterion(description="dedup_clusters.json gives each cluster's canonical registration, members and dropped members")
def artifact_dedup_clusters(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_dedup_canonicals(),
        _check_dedup_members(),
        _check_hidden_artifact('dedup_clusters.json'),
    )))

@criterion(description="preference_pairs.jsonl gives every pair's choices, provenance, route, margin and token cost")
def artifact_preference_pairs(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_pairs_chosen_rejected(),
        _check_pairs_provenance(),
        _check_pairs_margin_tokens(),
    )))

@criterion(description="split_assignment.json gives every family's split and the resulting family and pair counts")
def artifact_split_assignment(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_split_families(),
        _check_split_counts(),
        _check_hidden_artifact('split_assignment.json'),
    )))

@criterion(description="mixture_plan.json gives each source's allocation, cap status, epochs, target weight and effective weight")
def artifact_mixture_plan(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_mixture_allocation(),
        _check_mixture_epochs(),
        _check_mixture_weights(),
    )))

@criterion(description="packing_plan.json gives the sequence and pair totals together with token capacity, use and padding")
def artifact_packing_plan(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_packing_sequences(),
        _check_packing_tokens(),
        _check_hidden_artifact('packing_plan.json'),
    )))

@criterion(description="training_schedule.json gives optimizer and warmup steps, accumulation, shards and dropped tail sequences")
def artifact_training_schedule(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_schedule_steps(),
        _check_schedule_shape(),
    )))

@criterion(description="slice_coverage.json gives every slice's pair, split and token totals")
def artifact_slice_coverage(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_slice_pair_counts(),
        _check_slice_split_tokens(),
        _check_hidden_artifact('slice_coverage.json'),
    )))

@criterion(description="source_audit.json gives record counts for the governing exports")
def artifact_source_audit_governing(workspace: Path) -> bool:
    return _holds(lambda: _check_source_audit_rows(SOURCE_AUDIT_GOVERNING))

@criterion(description="source_audit.json gives record counts for the operational exports")
def artifact_source_audit_operational(workspace: Path) -> bool:
    return _holds(lambda: _check_source_audit_rows(SOURCE_AUDIT_OPERATIONAL))

@criterion(description="source_audit.json gives record counts for the reference exports")
def artifact_source_audit_reference(workspace: Path) -> bool:
    return _holds(lambda: _check_source_audit_rows(SOURCE_AUDIT_REFERENCE))

@criterion(description="control_reconciliation.json totals agree with the published control figures")
def artifact_control_reconciliation(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_control_reconciliation(),
        _check_hidden_artifact('control_reconciliation.json'),
    )))

@criterion(description="release_gates.json gives every gate decision, total pair count, contamination rate and undersized slice")
def artifact_release_gates(workspace: Path) -> bool:
    return _holds(lambda: all((
        _check_release_gate_decisions(),
        _check_release_gate_detail(),
    )))

@criterion(description="build.py reproduces annotator standing on the hidden corpus")
def hidden_standing(workspace: Path) -> bool:
    return _holds(_check_hidden_standing)

@criterion(description="build.py reproduces comparison resolution on the hidden corpus")
def hidden_resolution(workspace: Path) -> bool:
    return _holds(_check_hidden_resolution)

@criterion(description="build.py reproduces prompt eligibility on the hidden corpus")
def hidden_eligibility(workspace: Path) -> bool:
    return _holds(_check_hidden_eligibility)

@criterion(description="build.py reproduces the preference pairs on the hidden corpus")
def hidden_pairs(workspace: Path) -> bool:
    return _holds(_check_hidden_pairs)

@criterion(description="build.py reproduces the capped mixture plan on the hidden corpus")
def hidden_mixture(workspace: Path) -> bool:
    return _holds(_check_hidden_mixture)

@criterion(description="build.py reproduces the training schedule on the hidden corpus")
def hidden_schedule(workspace: Path) -> bool:
    return _holds(_check_hidden_schedule)

@criterion(description="build.py reproduces the release gates on the hidden corpus")
def hidden_gates(workspace: Path) -> bool:
    return _holds(_check_hidden_gates)

@criterion(description="the program and all fifteen release artifacts exist and parse")
def outputs_present(workspace: Path) -> bool:
    return _holds(_check_outputs_present)

@criterion(description="JSONL artifacts are sorted by key, unique and LF terminated")
def jsonl_sorted_lf(workspace: Path) -> bool:
    return _holds(_check_jsonl_sorted_lf)

@criterion(description="JSON artifacts have sorted keys and are LF terminated")
def json_sorted_keys_lf(workspace: Path) -> bool:
    return _holds(_check_json_sorted_keys_lf)

@criterion(description="the build runs within the published multiple of the read-and-decode baseline")
def relative_speed(workspace: Path) -> bool:
    return _holds(_check_relative_speed)

@criterion(description="build.py re-emits the visible release on a different corpus")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_hardcoded())
    except Exception:
        return False

@criterion(description="build.py output depends on the input directory name")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_filename())
    except Exception:
        return False

@criterion(description="build.py reads the default data location instead of its argument")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_reads_default())
    except Exception:
        return False

@criterion(description="build.py output differs between identical runs")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_nondeterministic())
    except Exception:
        return False

@criterion(description="build.py changes files in its input directory")
def negative_modifies_input_corpus(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_modifies_input())
    except Exception:
        return False

@criterion(description="build.py writes files outside its output directory")
def negative_writes_outside_output_dir(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_writes_outside())
    except Exception:
        return False

@criterion(description="build.py reads non-runtime files outside its input argument")
def negative_reads_outside_input_argument(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_reads_outside_argument())
    except Exception:
        return False

criteria.artifact_annotator_standing(weight=5)
criteria.artifact_verdict_admissibility(weight=5)
criteria.artifact_comparison_resolution(weight=5)
criteria.artifact_agreement(weight=5)
criteria.artifact_prompt_eligibility(weight=5)
criteria.artifact_dedup_clusters(weight=3)
criteria.artifact_preference_pairs(weight=5)
criteria.artifact_split_assignment(weight=5)
criteria.artifact_mixture_plan(weight=5)
criteria.artifact_packing_plan(weight=5)
criteria.artifact_training_schedule(weight=5)
criteria.artifact_slice_coverage(weight=5)
criteria.artifact_source_audit_governing(weight=5)
criteria.artifact_source_audit_operational(weight=5)
criteria.artifact_source_audit_reference(weight=5)
criteria.artifact_control_reconciliation(weight=5)
criteria.artifact_release_gates(weight=5)
criteria.hidden_standing(weight=5)
criteria.hidden_resolution(weight=5)
criteria.hidden_eligibility(weight=5)
criteria.hidden_pairs(weight=5)
criteria.hidden_mixture(weight=5)
criteria.hidden_schedule(weight=3)
criteria.hidden_gates(weight=3)
criteria.outputs_present(weight=1)
criteria.jsonl_sorted_lf(weight=1)
criteria.json_sorted_keys_lf(weight=1)
criteria.relative_speed(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_modifies_input_corpus(weight=-3)
criteria.negative_writes_outside_output_dir(weight=-1)
criteria.negative_reads_outside_input_argument(weight=-3)
