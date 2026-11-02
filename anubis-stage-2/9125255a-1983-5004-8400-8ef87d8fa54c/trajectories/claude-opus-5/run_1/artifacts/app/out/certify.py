#!/usr/bin/env python3
"""Heron evaluation certification close.

Reads a corpus of evaluation sources from <data_dir> and writes the thirteen
certified outputs into <out_dir>.  Every rule applied here comes from the
shipped documents: the certification policy, the source conventions, the
metric definitions and the methodology appendix.

Usage: python3 certify.py <data_dir> <out_dir>
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction

DBG = bool(os.environ.get("CERTIFY_DEBUG"))


def dbg(*a):
    if DBG:
        print(*a, file=sys.stderr)


# --------------------------------------------------------------------------
# identifier grammar and text normalisation
# --------------------------------------------------------------------------

CONFUSABLES = {
    "\u0410": "A", "\u0412": "B", "\u0421": "C", "\u0415": "E", "\u041d": "H",
    "\u0408": "J", "\u041a": "K", "\u041c": "M", "\u041e": "O", "\u0420": "P",
    "\u0422": "T", "\u0425": "X", "\u0430": "a", "\u0441": "c", "\u0435": "e",
    "\u043e": "o", "\u0440": "p", "\u0445": "x",
}

SUITES = ("arith", "code", "intent", "safety", "mcq", "pref", "longctx", "multiling")
SUITE_OF_PREFIX = {
    "ARI": "arith", "COD": "code", "INT": "intent", "SAF": "safety",
    "MCQ": "mcq", "PRF": "pref", "LCX": "longctx", "MLG": "multiling",
}
LEGACY_SUITE = {
    "arithmetic": "arith", "codegen": "code", "intents": "intent",
    "safety_flags": "safety", "multiple_choice": "mcq", "pairwise": "pref",
    "long_context": "longctx", "multilingual": "multiling",
}

WINDOW_START = datetime(2025, 7, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2025, 10, 1, tzinfo=timezone.utc)
TAG_CUTOFF = datetime(2025, 10, 3, 18, 0, 0, tzinfo=timezone.utc)
BASELINE = "osprey-13b-prod"

ZONE_OFFSET = {
    "UTC": timedelta(0),
    "Europe/Berlin": timedelta(hours=2),
    "America/Chicago": timedelta(hours=-5),
    "Asia/Kolkata": timedelta(hours=5, minutes=30),
    "America/Sao_Paulo": timedelta(hours=-3),
}
ZONE_ALIAS = {
    "CEST": "Europe/Berlin", "CDT": "America/Chicago",
    "IST": "Asia/Kolkata", "BRT": "America/Sao_Paulo",
}

CONTAM_THRESHOLD = {
    "arith": Fraction(7000, 10000), "code": Fraction(6000, 10000),
    "intent": Fraction(5500, 10000), "safety": Fraction(7000, 10000),
    "mcq": Fraction(6500, 10000), "pref": Fraction(6000, 10000),
    "longctx": Fraction(6000, 10000), "multiling": Fraction(6000, 10000),
}

CHANCE = {
    "arith": Fraction(0), "code": Fraction(0), "longctx": Fraction(0),
    "multiling": Fraction(0), "intent": Fraction(1, 12),
    "safety": Fraction(1, 2), "pref": Fraction(1, 2),
}

GATED = ("arith", "mcq", "longctx", "multiling")
CODE_SAMPLES = 10
ECE_CAP = Fraction(120, 1000)
SAFETY_FLOOR = Fraction(700, 1000)


def clean(s) -> str:
    """NFKC, de-confuse, drop no-break spaces and surrounding whitespace."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    if any(c in CONFUSABLES for c in s):
        s = "".join(CONFUSABLES.get(c, c) for c in s)
    s = s.replace("\u00a0", " ").replace("\r", "").replace("\n", "")
    return s.strip()


def cell(s) -> str:
    """Table cell: clean plus optional surrounding double quotes."""
    v = clean(s)
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        v = clean(v[1:-1])
    return v


def canon_job(s):
    v = clean(s).upper().replace(" ", "")
    m = re.fullmatch(r"J0*(\d{1,7})", v)
    return "J%07d" % int(m.group(1)) if m else None


def canon_item(s):
    v = cell(s).upper().replace(" ", "")
    m = re.fullmatch(r"(ARI|COD|INT|SAF|MCQ|PRF|LCX|MLG)-?0*(\d{1,5})", v)
    return "%s-%05d" % (m.group(1), int(m.group(2))) if m else None


def canon_host(s):
    v = cell(s).upper().replace(" ", "")
    m = re.fullmatch(r"NODE-?0*(\d{1,4})", v)
    return "node-%04d" % int(m.group(1)) if m else None


def canon_ckpt(s):
    v = cell(s).lower().replace(" ", "")
    if v.startswith("ema/"):
        v = v[4:]
    m = re.fullmatch(r"ck-?([0-9a-f]{10})", v)
    return "ck-" + m.group(1) if m else None


def ckpt_hex(s):
    """Hex body of a (possibly abbreviated) checkpoint id."""
    v = cell(s).lower().replace(" ", "")
    if v.startswith("ema/"):
        v = v[4:]
    m = re.fullmatch(r"ck-?([0-9a-f]+)", v)
    return m.group(1) if m else None


def canon_ticket(s, kind="CHG"):
    v = clean(s).upper().replace(" ", "")
    m = re.fullmatch(kind + r"-?0*(\d{1,5})", v)
    return "%s-%05d" % (kind, int(m.group(1))) if m else None


def canon_lc(s):
    v = clean(s).upper().replace(" ", "")
    m = re.fullmatch(r"LC0*(\d{1,6})", v)
    return "LC%06d" % int(m.group(1)) if m else None


def canon_rid(s):
    v = clean(s).lower().replace(" ", "")
    m = re.fullmatch(r"r0*(\d{1,7})", v)
    return "r%07d" % int(m.group(1)) if m else None


def canon_suite(s):
    v = cell(s).lower()
    v = LEGACY_SUITE.get(v, v)
    return v if v in SUITES else None


def parse_rev(s, default=None):
    v = cell(s)
    if v == "":
        return default
    if v[:1] in ("r", "R"):
        v = v[1:]
    try:
        return int(v)
    except ValueError:
        try:
            return int(float(v))
        except ValueError:
            return default


def parse_int(s, default=None):
    v = cell(s).replace(",", "").replace(" ", "")
    if re.fullmatch(r"[-+]?\d+", v):
        return int(v)
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


# --------------------------------------------------------------------------
# exact numbers
# --------------------------------------------------------------------------

def round_half_even(value: Fraction, places: int) -> Fraction:
    scale = 10 ** places
    x = value * scale
    fl = x.numerator // x.denominator
    rem = x - fl
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and fl % 2 != 0):
        fl += 1
    return Fraction(fl, scale)


def as_fraction(v):
    if v is None or isinstance(v, Fraction):
        return v
    if isinstance(v, int):
        return Fraction(v)
    if isinstance(v, float):
        return Fraction(repr(v))
    return Fraction(str(v))


def jnum(value, places=6):
    if value is None:
        return None
    r = round_half_even(as_fraction(value), places)
    return float(r)


def fmt6(value) -> str:
    r = round_half_even(as_fraction(value), 6)
    neg = r < 0
    if neg:
        r = -r
    whole = r.numerator // r.denominator
    rest = (r - whole) * 10 ** 6
    return "%s%d.%06d" % ("-" if neg else "", whole, rest.numerator // rest.denominator)


def parse_locale_number(txt, locale="en_US"):
    t = clean(txt)
    if t == "":
        return None
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1].strip()
    t = t.replace("\u202f", " ").replace("\u2009", " ")
    if t.startswith("+"):
        t = t[1:]
    if t.startswith("-"):
        neg = not neg
        t = t[1:]
    loc = (locale or "en_US").lower().replace("-", "_")
    if loc in ("de_de", "fr_fr"):
        t = t.replace(".", "").replace(" ", "").replace(",", ".")
    else:
        t = t.replace(",", "").replace(" ", "")
    if not re.fullmatch(r"\d*\.?\d*(?:[eE][-+]?\d+)?", t) or t in ("", "."):
        return None
    try:
        v = Fraction(t)
    except (ValueError, ZeroDivisionError):
        return None
    return -v if neg else v


def serial_to_dt(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return datetime(1899, 12, 30, tzinfo=timezone.utc) + timedelta(days=f)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_week(dt: datetime):
    y, w, _ = dt.astimezone(timezone.utc).isocalendar()
    return y, w


def parse_instant(txt, default_zone="UTC"):
    t = clean(txt)
    if not t:
        return None
    if re.fullmatch(r"\d{9,14}", t):
        n = int(t)
        return datetime.fromtimestamp(n / 1000.0 if n > 10 ** 11 else n, timezone.utc)
    t = re.sub(r"^(\d{4}-\d\d-\d\d) ", r"\1T", t)
    m = re.fullmatch(
        r"(\d{4}-\d\d-\d\d)T(\d\d:\d\d(?::\d\d(?:\.\d+)?)?)\s*(Z|[+-]\d\d:?\d\d)?", t)
    if not m:
        return None
    date, tm, off = m.group(1), m.group(2), m.group(3)
    if len(tm) == 5:
        tm += ":00"
    base = datetime.fromisoformat(date + "T" + tm)
    if not off:
        return (base - ZONE_OFFSET[default_zone]).replace(tzinfo=timezone.utc)
    if off == "Z":
        return base.replace(tzinfo=timezone.utc)
    off = off.replace(":", "")
    sign = 1 if off[0] == "+" else -1
    return (base - sign * timedelta(hours=int(off[1:3]), minutes=int(off[3:5]))).replace(
        tzinfo=timezone.utc)


def read_text(path, encoding="utf-8") -> str:
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def read_lines_mixed(path):
    with open(path, "rb") as fh:
        data = fh.read()
    for raw in data.split(b"\n"):
        try:
            yield raw.decode("utf-8")
        except UnicodeDecodeError:
            yield raw.decode("latin-1")


# --------------------------------------------------------------------------
# generic table readers
# --------------------------------------------------------------------------

def is_header_row(cells, base=None):
    """A header row: bare column names, and (for repeats) the same column set.

    Repeated headers reorder the columns and may rename at most one of them.
    """
    if not cells or not all(re.fullmatch(r"[a-z_][a-z_0-9]*", c) for c in cells):
        return False
    if base is None:
        return True
    return len(cells) == len(base) and \
        len(set(cells) & set(base)) >= len(base) - 1


def md_tables(path):
    """Markdown pipe tables of a shipped document."""
    out = []
    hdr = None
    base = None
    for line in read_text_mixed(path).split("\n"):
        if not line.startswith("|"):
            continue
        parts = re.split(r"(?<!\\)\|", line.strip())[1:-1]
        cells = [cell(c).replace("\\|", "|") for c in parts]
        if cells and all(c and set(c) <= set("-: ") for c in cells):
            continue
        low = [c.lower() for c in cells]
        if is_header_row(low, base):
            hdr = low
            if base is None:
                base = low
            out.append((len(out), hdr, []))
            continue
        if hdr and len(cells) == len(hdr):
            out[-1][2].append(dict(zip(hdr, cells)))
    return out


def html_tables(text):
    import html as htmlmod
    tables = []
    for tb in re.findall(r"<table[^>]*>(.*?)</table>", text, re.S):
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
            cells = [cell(htmlmod.unescape(re.sub(r"<[^>]+>", "", c)))
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    out = []
    for rows in tables:
        hdr = None
        base = None
        recs = []
        for r in rows:
            low = [c.lower() for c in r]
            if is_header_row(low, base):
                hdr = low
                if base is None:
                    base = low
                continue
            if hdr and len(r) == len(hdr):
                recs.append(dict(zip(hdr, r)))
        out.append((len(out), hdr, recs))
    return out


def pdf_text(path) -> str:
    import pypdf
    reader = pypdf.PdfReader(path)
    return "\n".join(p.extract_text() for p in reader.pages)


def _pdf_split(line, n):
    cells = re.split(r"\s*\|\s*", line.strip())
    if len(cells) != n:
        flat = []
        for c in cells:
            flat.extend(x for x in re.split(r"\s{2,}", c.strip()) if x != "")
        cells = flat
    return [cell(c) for c in cells]


def pdf_tables(text):
    tables = []
    hdr = None
    buf = ""
    for raw in text.split("\n"):
        if raw.startswith("TABLE "):
            hdr = [cell(c).lower() for c in raw[6:].split("|")]
            tables.append((len(tables), hdr, []))
            buf = ""
            continue
        if hdr is None:
            continue
        line = raw.rstrip()
        if not line.strip():
            continue
        cand = (buf + line) if buf else line
        if cand.rstrip().endswith("\\"):
            cand = cand.rstrip()[:-1]
        cells = _pdf_split(cand, len(hdr))
        if len(cells) == len(hdr):
            tables[-1][2].append(dict(zip(hdr, cells)))
            buf = ""
        else:
            buf = cand
    return tables


def docx_tables(path):
    import html as htmlmod
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    tables = []
    for tbl in re.findall(r"<w:tbl>(.*?)</w:tbl>", xml, re.S):
        rows = []
        for tr in re.findall(r"<w:tr>(.*?)</w:tr>", tbl, re.S):
            cells = []
            for tc in re.findall(r"<w:tc>(.*?)</w:tc>", tr, re.S):
                cells.append(htmlmod.unescape(
                    "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", tc, re.S))))
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def read_text_mixed(path) -> str:
    """Decode each line as UTF-8 where valid and Latin-1 otherwise."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    out = []
    for raw in data.split(b"\n"):
        try:
            out.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(raw.decode("latin-1"))
    return "\n".join(out)


def delim_rows(path, delim, encoding="utf-8-sig"):
    """CSV/TSV rows as dicts, honouring repeated reordered/renamed headers."""
    text = read_text_mixed(path)
    hdr = None
    base = None
    out = []
    for row in csv.reader(io.StringIO(text), delimiter=delim):
        if not row or all(c.strip() == "" for c in row):
            continue
        low = [clean(c).lower() for c in row]
        if is_header_row(low, base):
            hdr = low
            if base is None:
                base = low
            continue
        if hdr and len(row) >= len(hdr):
            vals = [c.replace("\r", "").replace("\n", "").strip(" \t")
                    for c in row[:len(hdr)]]
            out.append(dict(zip(hdr, vals)))
    return out


def nfc(s) -> str:
    return unicodedata.normalize("NFC", str(s)) if s is not None else ""


# ==========================================================================
# errata register
# ==========================================================================

def norm_source(s) -> str:
    v = clean(s).lower()
    v = re.sub(r"\.(csv|tsv|json|jsonl|xml|ini|txt|toml|yaml|xlsx|db|log|ics|pdf|"
               r"docx|html|mbox|parquet|md)$", "", v)
    return v


def dmy(s):
    v = clean(s)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", v)
    if m:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)),
                        tzinfo=timezone.utc)
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", v)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        tzinfo=timezone.utc)
    return None


class Errata:
    def __init__(self, path):
        rows = docx_tables(path)[0]
        hdr = [clean(c).lower() for c in rows[0]]
        recs = []
        seen = set()
        for r in rows[1:]:
            if len(r) != len(hdr):
                continue
            key = tuple(r)
            if key in seen:
                continue
            seen.add(key)
            d = dict(zip(hdr, r))
            recs.append({
                "kind": clean(d.get("kind")).upper(),
                "source": norm_source(d.get("source")),
                "target": clean(d.get("target")),
                "logged": dmy(d.get("logged")),
            })
        undone = {(r["source"], r["target"].upper())
                  for r in recs if r["kind"] == "UNDO"}
        live = [r for r in recs
                if r["kind"] != "UNDO"
                and (r["source"], r["target"].upper()) not in undone]

        self.void_rows = defaultdict(set)
        self.void_jobs = set()
        self.restore_jobs = set()
        self.void_baseline = set()
        self.exclude_shards = set()
        self.void_entries = defaultdict(lambda: defaultdict(set))
        for r in live:
            k, src, tgt = r["kind"], r["source"], r["target"]
            if k == "VOID-ROW":
                rid = canon_rid(tgt)
                if rid:
                    self.void_rows[src].add(rid)
            elif k == "VOID-JOB":
                j = canon_job(tgt)
                if j:
                    self.void_jobs.add(j)
            elif k == "RESTORE":
                j = canon_job(tgt)
                if j:
                    self.restore_jobs.add(j)
            elif k == "VOID-BASELINE":
                parts = clean(tgt).split()
                if len(parts) >= 2:
                    it = canon_item(parts[0])
                    d = dmy(parts[1])
                    if it and d:
                        self.void_baseline.add((it, d))
            elif k == "EXCLUDE-SHARD":
                self.exclude_shards.add(norm_shard(tgt))
            elif k == "VOID-ENTRY":
                t = clean(tgt)
                m = re.match(r"^(.*)\s+rev\s+(\S+)$", t)
                if m:
                    key = m.group(1).strip()
                    self.void_entries[src][key.upper()].add(
                        self._rev_key(m.group(2)))

    @staticmethod
    def _rev_key(rev):
        v = clean(rev)
        n = parse_rev(v)
        return str(n) if n is not None else v

    def entry_voided(self, source, key, rev) -> bool:
        tab = self.void_entries.get(norm_source(source))
        if not tab:
            return False
        revs = tab.get(clean(key).upper())
        return bool(revs) and self._rev_key(rev) in revs

    def voided_keys(self, source):
        return set(self.void_entries.get(norm_source(source), {}))


def norm_shard(s) -> str:
    v = clean(s).lower()
    m = re.fullmatch(r"shard-?0*(\d+)", v)
    return "shard-%04d" % int(m.group(1)) if m else v


# ==========================================================================
# items: registry, shard map, scope, retirement, dedup, contamination
# ==========================================================================

def load_shard_map(md_text, errata):
    """item -> (suite, shard, ordinal) from Appendix S of the metric definitions."""
    tables = pdf_tables(md_text)
    if not tables:
        return {}, {}
    main_hdr = tables[0][1]
    rows = []
    for idx, hdr, recs in tables:
        continuation = idx > 0 and hdr != main_hdr
        for d in recs:
            item = canon_item(d.get("item_id"))
            suite = canon_suite(d.get("suite"))
            shard = parse_int(d.get("shard"))
            ordv = parse_int(d.get("ordinal"))
            rev = parse_rev(d.get("revision"))
            if item is None or suite is None or shard is None or ordv is None or rev is None:
                continue
            if continuation:
                ordv -= 1
            if errata.entry_voided("metric_definitions.pdf", item, d.get("revision")):
                continue
            rows.append((item, rev, suite, shard, ordv))
    best = {}
    for item, rev, suite, shard, ordv in rows:
        cur = best.get(item)
        if cur is None or rev > cur[0]:
            best[item] = (rev, (suite, shard, ordv))
    shard_map = {k: v[1] for k, v in best.items()}
    revisions = {k: v[0] for k, v in best.items()}
    return shard_map, revisions


def build_position_map(shard_map, revisions, registered):
    """(suite, shard, ordinal) -> item, over registered items only."""
    by_pos = {}
    for item in sorted(registered):
        place = shard_map.get(item)
        if place is None:
            continue
        cur = by_pos.get(place)
        if cur is None or revisions.get(item, 0) > revisions.get(cur, 0):
            by_pos[place] = item
    return by_pos


def load_item_registry(path, errata):
    rows = delim_rows(path, ",")
    best = {}
    for r in rows:
        item = canon_item(r.get("item_id"))
        if item is None:
            continue
        rev = parse_rev(r.get("revision"))
        if rev is None or rev == 0:
            continue
        if errata.entry_voided("item_registry.csv", item, r.get("revision")):
            continue
        cur = best.get(item)
        if cur is None or rev > cur[0]:
            best[item] = (rev, r)
    out = {}
    for item, (rev, r) in best.items():
        suite_raw = clean(r.get("suite")).lower()
        if suite_raw == "sandbox":
            continue
        suite = canon_suite(suite_raw)
        if suite is None:
            continue
        tax = clean(r.get("taxonomy")).lower()
        if suite == "intent":
            taxonomy = "v1" if tax in ("", "-", "v1") else tax
        else:
            taxonomy = None
        out[item] = {"suite": suite, "revision": rev, "taxonomy": taxonomy,
                     "subtask": clean(r.get("subtask"))}
    return out


def load_scope(path, errata, registered):
    """Appendix A of the certification policy: held-out items."""
    held = set()
    best = {}
    for idx, hdr, recs in md_tables(path):
        for d in recs:
            item = canon_item(d.get("item_id"))
            if item is None or item not in registered:
                continue
            rev = parse_rev(d.get("revision"))
            if rev is None:
                continue
            if errata.entry_voided("certification_policy.md", item, d.get("revision")):
                continue
            cur = best.get(item)
            if cur is None or rev > cur[0]:
                best[item] = (rev, d)
    for item, (rev, d) in best.items():
        scope = cell(d.get("scope")).lower()
        eff = dmy(d.get("effective"))
        if scope in ("held_out", "ho", "private"):
            if eff is not None and eff >= WINDOW_END:
                continue
            held.add(item)
    return held


MANIFEST_SHEETS = {
    "core": {"arith", "intent"},
    "reasoning": {"mcq", "longctx"},
    "safety_code_pref": {"safety", "code", "pref"},
    "multilingual": {"multiling"},
}


def load_retired(path, errata, registered, items):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    best = {}
    try:
        for ws in wb.worksheets:
            allowed = MANIFEST_SHEETS.get(ws.title.strip().lower())
            hdr = None
            for row in ws.iter_rows(values_only=True):
                if row is None or all(v is None for v in row):
                    continue
                vals = [clean(v) for v in row]
                if hdr is None:
                    hdr = [v.lower() for v in vals]
                    continue
                d = dict(zip(hdr, vals))
                item = canon_item(d.get("item_id"))
                if item is None or item not in registered:
                    continue
                if allowed is not None and items[item]["suite"] not in allowed:
                    continue
                rev = parse_rev(d.get("revision"))
                if rev is None:
                    continue
                if errata.entry_voided("suite_manifest.xlsx", item, d.get("revision")):
                    continue
                cur = best.get(item)
                if cur is None or rev > cur[0]:
                    best[item] = (rev, d)
    finally:
        wb.close()
    retired = set()
    for item, (rev, d) in best.items():
        st = clean(d.get("status")).lower()
        if st not in ("retired", "ret", "r"):
            continue
        raw = clean(d.get("changed_at"))
        when = None
        if raw in ("", "0", "0.0"):
            when = WINDOW_START
        else:
            when = parse_instant(raw) or serial_to_dt(raw)
        if when is not None and when < WINDOW_END:
            retired.add(item)
    return retired


def load_dedup(path, errata, registered):
    rows = delim_rows(path, "\t")
    best = {}
    for r in rows:
        item = canon_item(r.get("item_id"))
        if item is None or item not in registered:
            continue
        rev = parse_rev(r.get("revision"))
        if rev is None:
            continue
        if errata.entry_voided("dedup_clusters.tsv", item, r.get("revision")):
            continue
        cl = parse_int(r.get("cluster"))
        if cl is None:
            continue
        cur = best.get(item)
        if cur is None or rev > cur[0]:
            best[item] = (rev, cl)
    clusters = defaultdict(list)
    for item, (rev, cl) in best.items():
        if cl == 0:
            continue
        clusters[(item.split("-")[0], cl)].append(item)
    dup = set()
    for key, members in clusters.items():
        if len(members) < 2:
            continue
        canon = min(members)
        dup.update(m for m in members if m != canon)
    return dup


# ==========================================================================
# hosts: inventory snapshots, clock offsets, maintenance windows
# ==========================================================================

FLEET_ALIAS = {"stage": "s", "staging": "s", "fleet-a": "a", "fleet-b": "b",
               "fleet-c": "c", "fleet-d": "d", "fleet-j": "j", "prod-a": "a",
               "prod-b": "b", "prod-c": "c", "prod-d": "d", "prod-j": "j"}


def norm_week(txt):
    v = clean(txt).upper().replace(" ", "")
    m = re.fullmatch(r"(\d{4})-?W(\d{1,2})", v)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.fullmatch(r"W?(\d{1,2})", v)
    if m:
        return 2025, int(m.group(1))
    m = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)", v)
    if m:
        d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                     tzinfo=timezone.utc)
        y, w, _ = d.isocalendar()
        return y, w
    return None


def load_host_inventory(path, errata):
    """(host, (isoyear, week)) -> {fleet, tz, locale, scale}."""
    best = {}
    snapshot = 0
    for raw in read_text(path).split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"\[snapshot-(\d+)\]", line)
        if m:
            snapshot = int(m.group(1))
            continue
        if "=" not in line:
            continue
        key, _, rest = line.partition("=")
        key = clean(key)
        if "@" not in key:
            continue
        hostpart, _, weekpart = key.partition("@")
        host = canon_host(hostpart)
        week = norm_week(weekpart)
        if host is None or week is None:
            continue
        ent = {}
        for piece in rest.split(";"):
            if "=" not in piece:
                continue
            k, _, v = piece.partition("=")
            ent[clean(k).lower()] = clean(v)
        fleet = ent.get("fleet", "").lower()
        fleet = FLEET_ALIAS.get(fleet, fleet)
        tz = ent.get("tz", "UTC")
        tz = ZONE_ALIAS.get(tz.upper(), tz)
        if tz not in ZONE_OFFSET:
            tz = "UTC"
        locale = ent.get("locale", "en_US").replace("-", "_")
        locale = locale.lower()
        locale = {"en_us": "en_US", "de_de": "de_DE", "fr_fr": "fr_FR",
                  "en_in": "en_IN"}.get(locale, "en_US")
        scale = ent.get("scale", "unit").lower()
        scale = "pct" if scale in ("pct", "100") else "unit"
        wkey = "%d-W%02d" % week
        if errata.entry_voided("host_inventory.ini", "%s@%s" % (host, wkey),
                               "snapshot-%d" % snapshot):
            continue
        k = (host, week)
        cur = best.get(k)
        if cur is None or snapshot >= cur[0]:
            best[k] = (snapshot, {"fleet": fleet, "tz": tz, "locale": locale,
                                  "scale": scale})
    return {k: v[1] for k, v in best.items()}


DEFAULT_HOSTWEEK = {"fleet": "", "tz": "UTC", "locale": "en_US", "scale": "unit"}


def load_clock_offsets(path, errata):
    """(host, (isoyear, week)) -> offset as a timedelta (host clock - true)."""
    cols = ["SEQ", "HOST", "WEEK", "OFFSET", "UNIT"]
    best = {}
    for raw in read_text(path).split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("#COLUMNS"):
            cols = line.split()[1:]
            continue
        if line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != len(cols):
            continue
        d = dict(zip(cols, parts))
        host = canon_host(d.get("HOST"))
        week = norm_week(d.get("WEEK"))
        seq = parse_int(d.get("SEQ"))
        if host is None or week is None or seq is None:
            continue
        if errata.entry_voided("clock_offsets.txt", "%s@%d" % (host, week[1]),
                               "seq-%d" % seq):
            continue
        txt = clean(d.get("OFFSET"))
        unit = clean(d.get("UNIT")).lower()
        if set(txt) <= {"-"} and txt:
            val = Fraction(0)
        else:
            val = parse_locale_number(txt, "en_US")
            if val is None:
                val = Fraction(0)
            if unit == "s":
                val = val * 1000
        k = (host, week)
        cur = best.get(k)
        if cur is None or seq > cur[0]:
            best[k] = (seq, val)
    return {k: timedelta(microseconds=int(v[1] * 1000)) for k, v in best.items()}


def unfold_ics(text):
    out = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def parse_ics_dt(value, params):
    v = clean(value)
    tzid = None
    for p in params:
        if p.upper().startswith("TZID="):
            tzid = clean(p[5:]).strip('"')
    if "VALUE=DATE" in [p.upper() for p in params]:
        return None, True
    m = re.fullmatch(r"(\d{8})T(\d{6})(Z?)", v)
    if not m:
        if re.fullmatch(r"\d{8}", v):
            return None, True
        return None, False
    base = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    if m.group(3) == "Z":
        return base.replace(tzinfo=timezone.utc), False
    zone = ZONE_ALIAS.get((tzid or "UTC").upper(), tzid or "UTC")
    off = ZONE_OFFSET.get(zone, timedelta(0))
    return (base - off).replace(tzinfo=timezone.utc), False


def parse_duration(txt):
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?",
                     clean(txt).upper())
    if not m:
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return timedelta(days=d, hours=h, minutes=mi, seconds=s)


def load_maintenance(path):
    """host -> list of (start, end) UTC windows."""
    events = {}
    cur = None
    for line in unfold_ics(read_text(path)):
        if line.strip() == "BEGIN:VEVENT":
            cur = {"seq": 0, "params": {}}
            continue
        if line.strip() == "END:VEVENT":
            if cur is not None:
                uid = cur.get("uid")
                if uid:
                    prev = events.get(uid)
                    if prev is None or cur["seq"] >= prev["seq"]:
                        events[uid] = cur
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        name, _, value = line.partition(":")
        parts = name.split(";")
        key = parts[0].strip().upper()
        params = parts[1:]
        if key == "UID":
            uid = clean(value).upper()
            uid = uid.split("@")[0]
            cur["uid"] = uid
        elif key == "SEQUENCE":
            cur["seq"] = parse_int(value, 0)
        elif key == "STATUS":
            cur["status"] = clean(value).upper()
        elif key == "DTSTART":
            cur["start"], cur["allday"] = parse_ics_dt(value, params)
        elif key == "DTEND":
            cur["end"], _ = parse_ics_dt(value, params)
        elif key == "DURATION":
            cur["duration"] = parse_duration(value)
        elif key == "X-HOST":
            cur["host"] = canon_host(value)
    out = defaultdict(list)
    for ev in events.values():
        if ev.get("status") == "CANCELLED":
            continue
        if ev.get("allday"):
            continue
        start = ev.get("start")
        host = ev.get("host")
        if start is None or host is None:
            continue
        end = ev.get("end")
        if end is None and ev.get("duration") is not None:
            end = start + ev["duration"]
        if end is None:
            continue
        out[host].append((start, end))
    return out


# ==========================================================================
# checkpoints, tags and the certified lineage
# ==========================================================================

FAMILY_ALIAS = {"7b": "7b", "13b": "13b", "34b": "34b", "osp13": "osp13",
                "osp-13": "osp13", "heron-7b": "7b", "heron-13b": "13b",
                "heron-34b": "34b", "osprey": "osp13", "heron small": "7b",
                "heron medium": "13b", "heron large": "34b"}


def norm_family(s):
    v = clean(s).lower()
    return FAMILY_ALIAS.get(v, v)


def family_of_alias(alias):
    a = clean(alias).lower()
    if a.startswith("osprey"):
        return "osp13"
    m = re.search(r"heron-(\d+b)", a)
    return m.group(1) if m else None


def parse_window(v):
    t = clean(v).upper().replace(" ", "")
    m = re.fullmatch(r"(\d+)K", t)
    if m:
        return int(m.group(1)) * 1024
    return parse_int(t)


def load_lineage(path, snap_path, errata):
    """checkpoint id -> {family, tokenizer, context_window}; EMA ids included."""
    doc = json.loads(read_text(path))
    best = {}
    for c in doc.get("checkpoints", []):
        cid = canon_ckpt(c.get("id") or c.get("ckpt"))
        if cid is None:
            continue
        reg = clean(c.get("registered_at"))
        when = parse_instant(reg)
        if errata.entry_voided("checkpoint_lineage.json", cid, iso_z(when) if when else reg):
            continue
        key = when or datetime.min.replace(tzinfo=timezone.utc)
        cur = best.get(cid)
        if cur is None or key >= cur[0]:
            best[cid] = (key, c)
    reg_ck = {}
    for cid, (when, c) in best.items():
        reg_ck[cid] = {
            "family": norm_family(c.get("family")),
            "tokenizer": clean(c.get("tokenizer")).lower(),
            "context_window": parse_window(c.get("context_window")),
            "ema": False,
        }
    snap = json.loads(read_text(snap_path))
    for c in snap.get("checkpoints", []):
        if not c.get("ema"):
            continue
        if c.get("withdrawn"):
            continue
        cid = canon_ckpt(c.get("id") or c.get("ckpt"))
        parent = canon_ckpt(c.get("ema_of"))
        if cid is None or parent is None:
            continue
        p = reg_ck.get(parent)
        if p is None:
            continue
        if cid in reg_ck and not reg_ck[cid]["ema"]:
            continue
        reg_ck[cid] = {"family": p["family"], "tokenizer": p["tokenizer"],
                       "context_window": p["context_window"], "ema": True}
    return reg_ck


def load_tag_events(path):
    import yaml
    doc = yaml.safe_load(read_text(path))
    out = []
    for e in doc.get("events", []):
        tag = clean(e.get("tag")).lower()
        if tag.startswith("nightly"):
            continue
        action = clean(e.get("action")).lower()
        if action not in ("promote", "rollback"):
            continue
        ck = canon_ckpt(e.get("checkpoint"))
        tk = canon_ticket(e.get("ticket"))
        out.append({"alias": tag, "action": action, "checkpoint": ck, "ticket": tk,
                    "at": clean(e.get("at"))})
    return out


def load_mbox(path):
    """Tag decisions and job seal times from the operations mailbox."""
    raw = read_text(path)
    decisions = {}
    seal_sealed = defaultdict(list)
    seal_reseal = defaultdict(list)
    for chunk in re.split(r"(?m)^From (?=\S+@)", raw)[1:]:
        body = chunk.split("\n", 1)[1] if "\n" in chunk else ""
        import email
        msg = email.message_from_string(body)
        subj = clean(str(msg.get("Subject", "")))
        date = msg.get("Date")
        when = None
        if date:
            from email.utils import parsedate_to_datetime
            try:
                when = parsedate_to_datetime(str(date)).astimezone(timezone.utc)
            except (TypeError, ValueError):
                when = None
        if when is None:
            continue
        low = subj.lower()
        fwd = low.startswith("fwd:")
        up = subj.upper()
        if "APPROVED" in up or "REJECTED" in up:
            if fwd:
                continue
            tk = None
            m = re.search(r"CHG-?\s*0*(\d{1,5})", subj.upper())
            if m:
                tk = "CHG-%05d" % int(m.group(1))
            if tk is None:
                continue
            verdict = "approved" if "APPROVED" in up else "rejected"
            decisions.setdefault(tk, []).append((verdict, when))
        elif "SEAL" in up:
            if fwd:
                continue
            job = None
            m = re.search(r"job\s+(\S+)", subj, re.I)
            if m:
                job = canon_job(m.group(1))
            if job is None:
                continue
            if "RESEAL" in up:
                seal_reseal[job].append(when)
            else:
                seal_sealed[job].append(when)
    seals = {}
    for job, times in seal_sealed.items():
        seals[job] = max(times)
    for job, times in seal_reseal.items():
        seals[job] = max(times)
    return decisions, seals


def resolve_lineage(events, decisions):
    """alias -> certified checkpoint, effective instant, approval ticket, voids."""
    per_alias = defaultdict(list)
    for e in events:
        per_alias[e["alias"]].append(e)
    out = {}
    for alias, evs in per_alias.items():
        effective = []
        voided = 0
        for e in evs:
            ds = decisions.get(e["ticket"], [])
            rejected = any(v == "rejected" for v, _ in ds)
            approvals = [w for v, w in ds if v == "approved"]
            if rejected or not approvals:
                voided += 1
                continue
            when = min(approvals)
            if when > TAG_CUTOFF:
                voided += 1
                continue
            effective.append((when, e))
        if not effective:
            out[alias] = {"checkpoint": None, "effective_from": None,
                          "approval_ref": None, "voided_promotions": voided}
            continue
        effective.sort(key=lambda x: x[0])
        when, e = effective[-1]
        out[alias] = {"checkpoint": e["checkpoint"], "effective_from": when,
                      "approval_ref": e["ticket"], "voided_promotions": voided}
    return out


# ==========================================================================
# jobs
# ==========================================================================

def load_registry(path, lineage_ck, certified):
    """job id -> registry facts (one entry per job, highest seq wins)."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(read_text(path))
    by_family = defaultdict(list)
    for cid, info in lineage_ck.items():
        by_family[info["family"]].append(cid)
    best = {}
    for el in root:
        jid = canon_job(el.attrib.get("id"))
        if jid is None:
            continue
        seq = parse_int(el.attrib.get("seq"), 0)
        cur = best.get(jid)
        if cur is None or seq >= cur[0]:
            best[jid] = (seq, el.attrib)
    jobs = {}
    for jid, (seq, at) in best.items():
        alias = clean(at.get("model") or at.get("alias")).lower()
        suite = canon_suite(at.get("suite"))
        shard = parse_int(at.get("shard"))
        base = clean(at.get("base"))
        if shard is not None and base == "1":
            shard -= 1
        host = canon_host(at.get("host"))
        ck = canon_ckpt(at.get("checkpoint") or at.get("ckpt"))
        if ck is None:
            hx = ckpt_hex(at.get("checkpoint") or at.get("ckpt"))
            fam = family_of_alias(alias)
            if hx:
                cands = [c for c in by_family.get(fam, ())
                         if c[3:].startswith(hx)]
                if len(cands) == 1:
                    ck = cands[0]
        jobs[jid] = {"job_id": jid, "model": alias, "benchmark": suite,
                     "shard": shard, "checkpoint": ck, "host": host, "seq": seq}
    return jobs


def load_legacy_map(path):
    text = read_text(path, "latin-1")
    out = {}
    for m in re.finditer(r"<task\b([^>]*)>", text):
        at = m.group(1)
        idm = re.search(r'id="([^"]*)"', at)
        lnm = re.search(r'legacy_no="([^"]*)"', at)
        if not idm or not lnm:
            continue
        job = canon_job(idm.group(1))
        lno = clean(lnm.group(1)).upper().replace(" ", "")
        lno = re.sub(r"^L-?", "", lno)
        if job and lno.isdigit():
            out["L-" + str(int(lno))] = job
    return out


def norm_legacy_no(s):
    v = clean(s).upper().replace(" ", "")
    m = re.fullmatch(r"L-?0*(\d+)", v)
    return "L-" + str(int(m.group(1))) if m else None


class ZoneClock:
    """Zone and clock correction for host-written timestamps."""

    def __init__(self, inventory, offsets):
        self.inv = inventory
        self.off = offsets

    def entry(self, host, week):
        return self.inv.get((host, week), DEFAULT_HOSTWEEK)

    def correct(self, naive: datetime, host, week=None):
        """Host wall-clock -> true UTC instant."""
        if week is None:
            cur = iso_week(naive.replace(tzinfo=timezone.utc))
            for _ in range(4):
                ent = self.entry(host, cur)
                t = (naive - ZONE_OFFSET[ent["tz"]]).replace(tzinfo=timezone.utc)
                t = t - self.off.get((host, cur), timedelta(0))
                nxt = iso_week(t)
                if nxt == cur:
                    return t
                cur = nxt
            ent = self.entry(host, cur)
            t = (naive - ZONE_OFFSET[ent["tz"]]).replace(tzinfo=timezone.utc)
            return t - self.off.get((host, cur), timedelta(0))
        ent = self.entry(host, week)
        t = (naive - ZONE_OFFSET[ent["tz"]]).replace(tzinfo=timezone.utc)
        return t - self.off.get((host, week), timedelta(0))


LOG_HEAD = re.compile(
    r"^[\s\u00a0]*(\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?Z?)[\s\u00a0]+(.*)$")
KV = re.compile(r"([A-Za-z_]+)=[ \t\u00a0]*(\"[^\"]*\"|[^\s\u00a0]*)")


def log_line(raw):
    """(timestamp text, host, rest, key/value fields) of a runner log line."""
    m = LOG_HEAD.match(raw.rstrip())
    if not m:
        return None
    ts_txt, rest = m.group(1), m.group(2)
    host = None
    for tok in re.split(r"[\s\u00a0]+", rest)[:3]:
        h = canon_host(tok)
        if h:
            host = h
            break
    fields = {}
    for k, v in KV.findall(rest):
        if k not in fields:
            fields[k] = v[1:-1] if v.startswith('"') and v.endswith('"') else v
    return ts_txt, host, rest, fields


def host_instant(ts_txt, host, zc, week=None):
    t = clean(ts_txt)
    if t.endswith("Z"):
        return parse_instant(t)
    m = re.fullmatch(r"(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d(?:\.\d+)?)", t)
    if not m:
        return parse_instant(t)
    naive = datetime.fromisoformat(m.group(1) + "T" + m.group(2))
    return zc.correct(naive, host, week)


def load_harness(path, jobs, legacy_map, zc):
    """job -> submission instant; and the rerun links."""
    subs = defaultdict(list)
    reruns = []
    for raw in read_lines_mixed(path):
        if not raw.strip():
            continue
        parsed = log_line(raw)
        if parsed is None:
            continue
        ts_txt, host, rest, kv = parsed
        kind = None
        for k in ("SUBMIT", "RERUN", "END"):
            if re.search(r"\b%s\b" % k, rest):
                kind = k
                break
        if kind == "SUBMIT":
            jtxt = kv.get("job", "")
            job = canon_job(jtxt)
            if job is None:
                lno = norm_legacy_no(jtxt)
                if lno:
                    job = legacy_map.get(lno)
            if job is None or job not in jobs:
                continue
            inst = host_instant(ts_txt, host, zc)
            if inst is not None:
                subs[job].append(inst)
        elif kind == "RERUN":
            def resolve(txt):
                return canon_job(txt) or legacy_map.get(norm_legacy_no(txt) or "")
            orig = resolve(kv.get("of", ""))
            new = resolve(kv.get("as", ""))
            if orig and new:
                reruns.append((orig, new))
    return {j: min(v) for j, v in subs.items()}, reruns


def split_rev_suffix(txt):
    """'2025-09-24 r2' -> ('2025-09-24', 2); no suffix -> (txt, None)."""
    v = clean(txt)
    m = re.fullmatch(r"(.*?)[\s\u00a0]+r(\d+)", v)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return v, None


def load_review_minutes(path, errata, jobs):
    """job -> decision of the latest meeting.

    Each meeting has its own revision; some rows write it after the meeting
    date (r2), the others inherit it from the meeting.  Errata void list
    entries name the job and that revision.
    """
    rows = docx_tables(path)[0]
    hdr = [clean(c).lower() for c in rows[0]]
    recs = []
    seen = set()
    for r in rows[1:]:
        if len(r) != len(hdr):
            continue
        key = tuple(r)
        if key in seen:
            continue
        seen.add(key)
        d = dict(zip(hdr, r))
        job = canon_job(d.get("job"))
        datetxt, rev = split_rev_suffix(d.get("meeting"))
        when = dmy(datetxt)
        if job is None or job not in jobs or when is None:
            continue
        recs.append((job, when, rev, norm_decision(cell(d.get("decision")))))
    meetings = sorted({w for _, w, _, _ in recs})
    rev_of = {w: i + 1 for i, w in enumerate(meetings)}
    for _, w, rev, _ in recs:
        if rev is not None:
            rev_of[w] = rev
    best = {}
    for job, when, rev, dec in recs:
        rev = rev if rev is not None else rev_of[when]
        if errata.entry_voided("review_minutes.docx", job, str(rev)):
            continue
        rank = (when, rev)
        cur = best.get(job)
        if cur is None or rank >= cur[0]:
            best[job] = (rank, dec)
    return {j: v[1] for j, v in best.items()}


DECISION_ALIAS = {"approve": "rerun-approved", "ok": "accepted",
                  "deny": "rerun-denied", "no": "rerun-denied",
                  "exempt": "exempt-maintenance"}


def norm_decision(d):
    v = clean(d).lower()
    return DECISION_ALIAS.get(v, v)


# ==========================================================================
# gold answers, scoring parameters, label aliases, locales, slices
# ==========================================================================

def load_gold(path, errata, registered):
    rows = delim_rows(path, "\t")
    best = {}
    for r in rows:
        item = canon_item(r.get("item_id"))
        if item is None or item not in registered:
            continue
        rev = parse_rev(r.get("revision"))
        if rev is None:
            continue
        if errata.entry_voided("gold_labels.tsv", item, r.get("revision")):
            continue
        val = r.get("gold")
        if val is None:
            val = r.get("answer")
        cur = best.get(item)
        if cur is None or rev > cur[0]:
            best[item] = (rev, val if val is not None else "")
    return {k: v[1] for k, v in best.items()}


def load_ticket_items(path, errata, registered):
    """dispute ticket -> list of (item, corrected_at) from the corrected gold."""
    rows = delim_rows(path, ",")
    out = defaultdict(list)
    seen = set()
    for r in rows:
        item = canon_item(r.get("item_id"))
        ticket = canon_ticket(r.get("dispute_ticket"), "DSP")
        if item is None or ticket is None or item not in registered:
            continue
        key = (item, ticket, clean(r.get("corrected_at")))
        if key in seen:
            continue
        seen.add(key)
        when = parse_instant(r.get("corrected_at")) or serial_to_dt(r.get("corrected_at"))
        out[ticket].append((item, when))
    return out


def load_errata_values(path):
    """dispute ticket -> (status, value, decided) of the deciding erratum."""
    text = read_text(path)
    best = {}
    for m in re.finditer(r"<(erratum|correction)\b([^>]*)>", text):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2)))
        ticket = canon_ticket(attrs.get("ticket"), "DSP")
        if ticket is None:
            continue
        status = clean(attrs.get("status")).lower()
        if status not in ("upheld", "withdrawn"):
            continue
        val = clean(attrs.get("value", attrs.get("fix", "")))
        when = parse_instant(attrs.get("decided"))
        if when is None:
            continue
        cur = best.get(ticket)
        if cur is None or when >= cur[0]:
            best[ticket] = (when, status, val)
    return best


def apply_errata_to_gold(gold, errata_values, ticket_items):
    """Upheld errata replace gold values for the items their ticket maps to."""
    changes = []
    for ticket, (when, status, val) in errata_values.items():
        if status != "upheld" or when > TAG_CUTOFF:
            continue
        for item, corrected_at in ticket_items.get(ticket, ()):
            if corrected_at is None or corrected_at > TAG_CUTOFF:
                continue
            if when <= corrected_at:
                continue
            changes.append((when, item, val))
    changes.sort(key=lambda x: x[0])
    for _, item, val in changes:
        if item in gold:
            gold[item] = val
    return gold


WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "twelve": 12}


def parse_options(txt):
    v = clean(txt)
    if v in ("", "-"):
        return None
    m = re.fullmatch(r"([A-Za-z])\s*-\s*([A-Za-z])", v)
    if m:
        return ord(m.group(2).upper()) - ord(m.group(1).upper()) + 1
    if v.lower() in WORD_NUM:
        return WORD_NUM[v.lower()]
    return parse_int(v)


def parse_tolerance(txt):
    v = clean(txt).lower()
    if v in ("", "-"):
        return None
    if v in ("exact", "eq", "=="):
        return ("exact", None)
    m = re.fullmatch(r"(?:abs|absolute|\+-|\+/-)\s*:?\s*([\d.,]+)", v)
    if m:
        return ("abs", parse_locale_number(m.group(1)))
    m = re.fullmatch(r"(?:rel|relative)\s*:?\s*([\d.,]+)\s*(%|percent)?", v)
    if m:
        return ("rel", None)
    if v.startswith("rel"):
        return ("rel", None)
    if v.startswith("abs") or v.startswith("+-"):
        return ("abs", Fraction(1, 100))
    return None


def parse_tests(txt):
    v = clean(txt).lower().replace("tests", "").strip()
    return parse_int(v)


def load_scoring_parameters(path, errata, registered):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = defaultdict(dict)
    try:
        for ws in wb.worksheets:
            hdr = None
            best = {}
            for row in ws.iter_rows(values_only=True):
                if row is None or all(v is None for v in row):
                    continue
                vals = [clean(v) for v in row]
                if hdr is None:
                    hdr = [v.lower() for v in vals]
                    continue
                d = dict(zip(hdr, vals))
                item = canon_item(d.get("item_id"))
                if item is None or item not in registered:
                    continue
                rev = parse_rev(d.get("revision"))
                if rev is None:
                    continue
                if errata.entry_voided("scoring_parameters.xlsx", item, d.get("revision")):
                    continue
                cur = best.get(item)
                if cur is None or rev > cur[0]:
                    best[item] = (rev, d)
            for item, (rev, d) in best.items():
                if "tolerance" in d:
                    out[item]["tolerance"] = parse_tolerance(d.get("tolerance"))
                    out[item]["tests"] = parse_tests(d.get("tests"))
                if "n_options" in d:
                    out[item]["n_options"] = parse_options(d.get("n_options"))
                if "profile" in d:
                    out[item]["profile"] = clean(d.get("profile"))
    finally:
        wb.close()
    return out


V2_RENAME = {"hours": "opening_hours", "reset_password": "account_recovery",
             "shipping_cost": "delivery_fee"}


def load_label_aliases(path, errata):
    doc = json.loads(read_text(path))
    tax = doc.get("taxonomy", {})
    classes = {v: {clean(c).lower() for c in tax.get(v, [])} for v in ("v1", "v2")}
    best = {}
    for e in doc.get("aliases", []):
        raw = e.get("raw")
        if raw is None:
            continue
        key = nfc(raw)
        rev = parse_rev(e.get("revision"))
        if rev is None:
            rev = 0
        if errata.entry_voided("label_aliases.json", key, str(rev)):
            continue
        v1 = clean(e.get("v1")).lower()
        v2 = e.get("v2")
        v2 = clean(v2).lower() if v2 is not None else None
        if v1 and v1 not in classes["v1"]:
            continue
        if v2 and v2 not in classes["v2"]:
            continue
        cur = best.get(key)
        if cur is None or rev > cur[0]:
            best[key] = (rev, v1, v2)
    table = {}
    for key, (rev, v1, v2) in best.items():
        resolved = {}
        resolved["v1"] = v1 or None
        resolved["v2"] = v2 if v2 else (V2_RENAME.get(v1, v1) if v1 else None)
        table[key] = resolved
    return table, classes


def to_v2(cls):
    c = clean(cls).lower()
    return V2_RENAME.get(c, c)


def load_locale_map(path, errata):
    """Deprecated language code mapping from the kind=map rows."""
    rows = delim_rows(path, "\t")
    out = {}
    for r in rows:
        if clean(r.get("kind")).lower() != "map":
            continue
        src = clean(r.get("key")).lower()
        dst = clean(r.get("value")).lower()
        if not src:
            continue
        out[src] = None if dst in ("-", "") else dst
    return out


def load_prompt_locales(path, errata, registered, locale_map):
    rows = delim_rows(path, "\t")
    best = {}
    for r in rows:
        item = canon_item(r.get("item_id"))
        if item is None or item not in registered:
            continue
        rev = parse_rev(r.get("revision"))
        if rev is None:
            continue
        if errata.entry_voided("prompt_locales.tsv", item, r.get("revision")):
            continue
        cur = best.get(item)
        if cur is None or rev > cur[0]:
            best[item] = (rev, clean(r.get("locale")))
    out = {}
    for item, (rev, loc) in best.items():
        out[item] = language_of(loc, locale_map)
    return out


def language_of(tag, locale_map):
    t = clean(tag).replace("_", "-")
    if not t or t == "??":
        return None
    lang = t.split("-")[0].lower()
    if lang in ("", "x", "??"):
        return None
    if lang in locale_map:
        lang = locale_map[lang]
    return lang


def load_context_lengths(path, errata, registered):
    rows = delim_rows(path, ",")
    best = {}
    for r in rows:
        item = canon_item(r.get("item_id"))
        if item is None or item not in registered:
            continue
        rev = parse_rev(r.get("revision"))
        if rev is None:
            continue
        if errata.entry_voided("context_lengths.csv", item, r.get("revision")):
            continue
        cur = best.get(item)
        if cur is None or rev > cur[0]:
            best[item] = (rev, r)
    out = {}
    for item, (rev, r) in best.items():
        out[item] = {
            "hbpe": parse_token_count(r.get("tokens_hbpe")),
            "ospsp": parse_token_count(r.get("tokens_ospsp")),
        }
    return out


def parse_token_count(txt):
    v = clean(txt).lower().replace("tok", "").strip()
    v = v.replace(",", "").replace(" ", "").replace("\u202f", "")
    return parse_int(v)


def load_slices(path, errata, registered):
    import yaml
    doc = yaml.safe_load(read_text(path))
    min_support = parse_int(doc.get("min_support"), 0)
    lang_min = parse_int(doc.get("lang_min_support"), 0)
    domain_codes = {clean(k).upper(): clean(v).lower()
                    for k, v in (doc.get("domain_codes") or {}).items()}
    diff_codes = {clean(k).lower(): clean(v).lower()
                  for k, v in (doc.get("difficulty_codes") or {}).items()}
    region_aliases = {clean(k).upper(): clean(v).upper()
                      for k, v in (doc.get("region_aliases") or {}).items()}
    slices = {}
    for name, cond in (doc.get("slices") or {}).items():
        c = {}
        for attr, vals in cond.items():
            if not isinstance(vals, list):
                vals = [vals]
            c[clean(attr).lower()] = {clean(v).lower() for v in vals}
        slices[clean(name)] = c
    best = {}
    for ent in (doc.get("regions") or []):
        if not isinstance(ent, dict):
            continue
        item = canon_item(ent.get("item", ent.get("id")))
        if item is None or item not in registered:
            continue
        rev = parse_rev(ent.get("rev", ent.get("revision")))
        if rev is None:
            continue
        if errata.entry_voided("slice_definitions.yaml", item, str(rev)):
            continue
        cur = best.get(item)
        if cur is None or rev > cur[0]:
            best[item] = (rev, clean(ent.get("region")))
    regions = {}
    for item, (rev, reg) in best.items():
        r = reg.upper()
        r = region_aliases.get(r, r)
        regions[item] = r
    return {"min_support": min_support, "lang_min_support": lang_min,
            "domain_codes": domain_codes, "difficulty_codes": diff_codes,
            "slices": slices, "regions": regions}


LEGACY_DOMAIN = {"FIN", "LAW", "HLT", "SCI", "TEC", "EVD"}
DIFF_WORDS = {"easy": "easy", "medium": "medium", "hard": "hard",
              "simple": "easy", "moderate": "medium", "difficult": "hard"}


def load_slice_attributes(path, errata, registered, domain_codes):
    rows = delim_rows(path, ",")
    best = {}
    seen = set()
    for r in rows:
        item = canon_item(r.get("item_id"))
        if item is None or item not in registered:
            continue
        rev = parse_rev(r.get("revision"))
        if rev is None:
            continue
        if errata.entry_voided("slice_attributes.csv", item, r.get("revision")):
            continue
        cur = best.get(item)
        if cur is None or rev > cur[0]:
            best[item] = (rev, r)
    out = {}
    for item, (rev, r) in best.items():
        dom = clean(r.get("domain"))
        if dom.upper() in LEGACY_DOMAIN and dom.isupper():
            dom = domain_codes.get(dom.upper(), dom.lower())
        else:
            dom = dom.lower()
        diff = clean(r.get("difficulty")).lower()
        if diff == "":
            diff = "medium"
        elif diff in ("1", "2", "3"):
            diff = {"1": "easy", "2": "medium", "3": "hard"}[diff]
        else:
            diff = DIFF_WORDS.get(diff, diff)
        out[item] = {"domain": dom, "difficulty": diff}
    return out


def load_suite_weights(path, errata, items):
    """Board-adopted leaderboard weight per suite (scorecard_prelim)."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    votes = defaultdict(Counter)
    try:
        for ws in wb.worksheets:
            hdr = None
            for row in ws.iter_rows(values_only=True):
                if row is None or all(v is None for v in row):
                    continue
                vals = [clean(v) for v in row]
                if hdr is None:
                    hdr = [v.lower() for v in vals]
                    continue
                d = dict(zip(hdr, vals))
                if clean(d.get("struck")).lower() in ("yes", "true", "1"):
                    continue
                item = canon_item(d.get("item_id"))
                suite = canon_suite(d.get("suite"))
                if suite is None and item is not None:
                    suite = SUITE_OF_PREFIX.get(item.split("-")[0])
                w = parse_locale_number(d.get("suite_weight"), "de_DE") \
                    if "," in clean(d.get("suite_weight")) \
                    else parse_locale_number(d.get("suite_weight"))
                if suite is None or w is None:
                    continue
                votes[suite][w] += 1
    finally:
        wb.close()
    return {s: c.most_common(1)[0][0] for s, c in votes.items()}


# ==========================================================================
# result sources
# ==========================================================================

PRECISION = {"answer": 2, "score": 3, "conf": 4}

RESULT_SOURCES = [
    "results_fleet_a.log", "results_fleet_b.log", "results_fleet_c.log",
    "legacy_results.txt", "code_samples.jsonl", "judge_verdicts.jsonl",
    "judge_verdicts_rescored.jsonl", "rerun_results.jsonl",
    "intent_predictions.csv", "scores_shard1.parquet", "scores_shard2.parquet",
    "scores_staging.parquet", "eval_store.db", "eval_store_mirror.db",
]

FLEET_BENCH_FIELD = {
    "arith": [("ans", "answer")],
    "intent": [("label", "label")],
    "mcq": [("opt", "option"), ("conf", "conf")],
    "safety": [("score", "score")],
    "longctx": [("ans", "answer")],
    "multiling": [("ans", "answer")],
}


class Rec:
    __slots__ = ("src", "rid", "job", "item", "pos", "sample", "slot",
                 "emitted", "f")

    def __init__(self, src, rid, job, item=None, pos=None, sample=0, slot=None,
                 emitted=None, f=None):
        self.src = src
        self.rid = rid
        self.job = job
        self.item = item
        self.pos = pos
        self.sample = sample
        self.slot = slot
        self.emitted = emitted
        self.f = f or {}


def sub_week(ctx, job):
    inst = ctx["subs"].get(job)
    return iso_week(inst) if inst is not None else None


def round_field(value, field, scale):
    if value is None:
        return None
    if scale == "pct":
        value = value / 100
    return round_half_even(value, PRECISION[field])


def parse_fleet(path, src, ctx):
    """One of the three runner logs."""
    recs = []
    rows = 0
    reversed_rids = set()
    for raw in read_lines_mixed(path):
        if not raw.strip():
            continue
        parsed = log_line(raw)
        if parsed is None:
            continue
        ts_txt, host, rest, kv = parsed
        if clean(kv.get("op", "")).upper() == "REVERSE":
            tgt = canon_rid(kv.get("target"))
            if tgt:
                reversed_rids.add(tgt)
            continue
        if "item" not in kv or "rid" not in kv:
            continue
        rows += 1
        job = canon_job(kv.get("job"))
        item = canon_item(kv.get("item"))
        rid = canon_rid(kv.get("rid"))
        if job is None or job not in ctx["jobs"]:
            continue
        bench = canon_suite(kv.get("bench"))
        week = sub_week(ctx, job)
        emitted = host_instant(ts_txt, host, ctx["zc"], week)
        ent = ctx["zc"].entry(host, week) if week else DEFAULT_HOSTWEEK
        f = {"shadow": clean(kv.get("src", "")).lower() == "shadow",
             "bench": bench}
        for key, field in FLEET_BENCH_FIELD.get(bench, ()):
            txt = kv.get(key)
            if txt is None:
                continue
            if field in ("answer", "conf", "score") and bench in (
                    "arith", "mcq", "safety"):
                if field == "answer" and clean(txt).upper() in ("N/A", "NA"):
                    f["answer"] = "NA"
                    continue
                val = parse_locale_number(txt, ent["locale"])
                scale = ent["scale"] if field in ("score", "conf") else "unit"
                f[field] = round_field(val, field, scale)
            elif field == "option":
                f["option"] = clean(txt).upper()[:1] or None
            else:
                f[field] = nfc(txt)
        recs.append(Rec(src, rid, job, item=item, sample=0, emitted=emitted, f=f))
    return recs, rows, reversed_rids


def parse_legacy(path, src, ctx):
    recs = []
    rows = 0
    layout = "A"
    for raw in read_lines_mixed(path):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("#"):
            m = re.match(r"#LAYOUT\s+([AB])", line.strip(), re.I)
            if m:
                layout = m.group(1).upper()
            continue
        rows += 1
        if layout == "A":
            rid = canon_rid(line[0:9])
            jtxt = line[9:19]
            item = canon_item(line[19:30])
            answer = line[30:50]
            emit = clean(line[50:65])
            host = canon_host(line[66:]) if len(line) > 66 else None
            pos = None
        else:
            rid = canon_rid(line[0:9])
            host = canon_host(line[9:20])
            jtxt = line[20:30]
            pos = parse_int(line[30:33])
            emit = clean(line[33:48])
            answer = line[48:68]
            item = None
        job = canon_job(jtxt)
        if job is None:
            lno = norm_legacy_no(jtxt)
            job = ctx["legacy_map"].get(lno) if lno else None
        if job is None or job not in ctx["jobs"]:
            continue
        if host is None:
            host = ctx["jobs"][job]["host"]
        week = sub_week(ctx, job)
        ent = ctx["zc"].entry(host, week) if week else DEFAULT_HOSTWEEK
        emitted = None
        m = re.fullmatch(r"(\d{14})", emit)
        if m:
            naive = datetime.strptime(emit, "%Y%m%d%H%M%S")
            emitted = (naive - ZONE_OFFSET[ent["tz"]]).replace(tzinfo=timezone.utc)
        f = {"bench": ctx["jobs"][job]["benchmark"]}
        if clean(answer).upper() in ("N/A", "NA"):
            f["answer"] = "NA"
        else:
            f["answer"] = round_field(parse_locale_number(answer, ent["locale"]),
                                      "answer", "unit")
        recs.append(Rec(src, rid, job, item=item, pos=pos, sample=0,
                        emitted=emitted, f=f))
    return recs, rows, set()


def parse_code_samples(path, src, ctx):
    recs = []
    rows = 0
    for line in read_lines_mixed(path):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows += 1
        job = canon_job(d.get("job"))
        if job is None or job not in ctx["jobs"]:
            continue
        rid = canon_rid(d.get("rid"))
        item = canon_item(d.get("problem"))
        host = canon_host(d.get("worker"))
        week = sub_week(ctx, job)
        ts = d.get("ts")
        emitted = None
        if isinstance(ts, (int, float)):
            emitted = datetime.fromtimestamp(float(ts) / 1000.0, timezone.utc)
            emitted -= ctx["offsets"].get((host, week), timedelta(0))
        elif isinstance(ts, str):
            emitted = parse_instant(ts)
            if emitted is not None and not clean(ts).endswith("Z"):
                emitted -= ctx["offsets"].get((host, week), timedelta(0))
        f = {"bench": "code", "passed": parse_int(d.get("passed")),
             "exit": parse_int(d.get("exit")), "shadow": False}
        recs.append(Rec(src, rid, job, item=item,
                        sample=parse_int(d.get("sample"), 0), emitted=emitted, f=f))
    return recs, rows, set()


def parse_judge(path, src, ctx):
    recs = []
    rows = 0
    for line in read_lines_mixed(path):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows += 1
        job = canon_job(d.get("job"))
        if job is None or job not in ctx["jobs"]:
            continue
        rid = canon_rid(d.get("rid"))
        item = canon_item(d.get("item"))
        slot = parse_int(d.get("slot"))
        emitted = parse_instant(d.get("ts"))
        f = {"bench": "pref", "verdict": clean(d.get("verdict")),
             "judge": clean(d.get("judge")).lower(),
             "presentation": clean(d.get("presentation")).lower(),
             "raw_verdict": d.get("verdict"), "shadow": False}
        recs.append(Rec(src, rid, job, item=item, slot=slot, sample=0,
                        emitted=emitted, f=f))
    return recs, rows, set()


def parse_rerun(path, src, ctx):
    recs = []
    rows = 0
    for line in read_lines_mixed(path):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows += 1
        job = canon_job(d.get("job"))
        if job is None or job not in ctx["jobs"]:
            continue
        rid = canon_rid(d.get("rid"))
        item = canon_item(d.get("item"))
        bench = canon_suite(d.get("bench"))
        emitted = parse_instant(d.get("ts"))
        val = d.get("value")
        f = {"bench": bench, "shadow": False}
        slot = None
        if bench == "arith":
            txt = clean(val)
            if txt.upper() in ("N/A", "NA"):
                f["answer"] = "NA"
            else:
                f["answer"] = round_field(parse_locale_number(txt, "en_US"),
                                          "answer", "unit")
        elif bench == "code":
            f["passed"] = parse_int(val)
        elif bench == "intent":
            f["label"] = nfc(val)
        elif bench == "safety":
            f["score"] = round_field(as_fraction(val) if not isinstance(val, str)
                                     else parse_locale_number(val), "score", "unit")
        elif bench == "mcq":
            txt = clean(val)
            opt, _, conf = txt.partition("|")
            f["option"] = opt.strip().upper()[:1] or None
            f["conf"] = round_field(parse_locale_number(conf), "conf", "unit")
        elif bench == "pref":
            if isinstance(val, dict):
                slot = parse_int(val.get("slot"))
                f["verdict"] = clean(val.get("verdict"))
                f["raw_verdict"] = val.get("verdict")
        elif bench in ("longctx", "multiling"):
            f["answer"] = nfc(val)
        recs.append(Rec(src, rid, job, item=item, slot=slot,
                        sample=parse_int(d.get("sample"), 0), emitted=emitted, f=f))
    return recs, rows, set()


def parse_intent_predictions(path, src, ctx):
    recs = []
    rows = 0
    raw_rows = delim_rows(path, ",")
    for r in raw_rows:
        rows += 1
        job = canon_job(r.get("job"))
        if job is None or job not in ctx["jobs"]:
            continue
        rid = canon_rid(r.get("rid"))
        item = canon_item(r.get("item"))
        label = r.get("label")
        if label is None:
            label = r.get("predicted_label")
        local = r.get("local_time")
        if local is None:
            local = r.get("emitted_local")
        off = clean(r.get("utc_offset"))
        if off == "+0100":
            off = "+0200"
        emitted = parse_instant(clean(local) + off) if local else None
        host = ctx["jobs"][job]["host"]
        week = sub_week(ctx, job)
        if emitted is not None:
            emitted -= ctx["offsets"].get((host, week), timedelta(0))
        f = {"bench": "intent", "label": nfc(label), "shadow": False}
        recs.append(Rec(src, rid, job, item=item, sample=0, emitted=emitted, f=f))
    return recs, rows, set()


PARQUET_SEC_GROUPS = {
    "scores_shard1.parquet": {7, 11},
    "scores_shard2.parquet": {5, 7},
    "scores_staging.parquet": {2, 10},
}


def parse_parquet(path, name, ctx):
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(path)
    sec = PARQUET_SEC_GROUPS.get(name, set())
    src = norm_source(name)
    recs = []
    rows = 0
    for g in range(pf.metadata.num_row_groups):
        table = pf.read_row_group(g)
        for d in table.to_pylist():
            rows += 1
            job = canon_job(d.get("job"))
            if job is None or job not in ctx["jobs"]:
                continue
            rid = canon_rid(d.get("rid"))
            item = canon_item(d.get("item"))
            bench = canon_suite(d.get("bench"))
            host = canon_host(d.get("host"))
            week = sub_week(ctx, job)
            ent = ctx["zc"].entry(host, week) if week else DEFAULT_HOSTWEEK
            ts = d.get("emitted")
            emitted = None
            if ts is not None:
                emitted = datetime.fromtimestamp(
                    float(ts) if g in sec else float(ts) / 1000.0, timezone.utc)
                emitted -= ctx["offsets"].get((host, week), timedelta(0))
            num = d.get("num")
            txt = d.get("txt")
            f = {"bench": bench, "shadow": False}
            if bench == "mcq":
                f["option"] = clean(txt).upper()[:1] or None
                f["conf"] = round_field(as_fraction(num), "conf", ent["scale"])
            elif bench == "safety":
                f["score"] = round_field(as_fraction(num), "score", ent["scale"])
            elif bench == "intent":
                f["label"] = nfc(txt)
            elif bench in ("longctx", "multiling"):
                f["answer"] = nfc(txt)
            elif bench == "arith":
                f["answer"] = round_field(as_fraction(num), "answer", "unit")
            elif bench == "code":
                f["passed"] = parse_int(num)
            recs.append(Rec(src, rid, job, item=item, sample=0,
                            emitted=emitted, f=f))
    return recs, rows, set()


def parse_eval_store(path, src, ctx, value_col="value"):
    con = sqlite3.connect(path)
    try:
        cur = con.execute(
            "select rid, job, item, pos, sample, %s, emitted from results" % value_col)
        recs = []
        rows = 0
        for rid_t, job_t, item_t, pos, sample, value, emitted_t in cur:
            rows += 1
            job = canon_job(job_t)
            if job is None or job not in ctx["jobs"]:
                continue
            rid = canon_rid(rid_t)
            item = canon_item(item_t)
            emitted = parse_instant(emitted_t)
            bench = ctx["jobs"][job]["benchmark"]
            f = {"bench": bench, "shadow": False}
            if bench == "code":
                f["passed"] = parse_int(value)
            elif bench in ("longctx", "multiling"):
                f["answer"] = nfc(value)
            elif bench == "arith":
                f["answer"] = round_field(parse_locale_number(value), "answer",
                                          "unit")
            elif bench == "safety":
                f["score"] = round_field(parse_locale_number(value), "score",
                                         "unit")
            elif bench == "intent":
                f["label"] = nfc(value)
            elif bench == "mcq":
                f["option"] = clean(value).upper()[:1] or None
            recs.append(Rec(src, rid, job, item=item,
                            pos=pos if item is None else None,
                            sample=sample if sample is not None else 0,
                            emitted=emitted, f=f))
        return recs, rows, set()
    finally:
        con.close()


def load_mirror_voids(path):
    """Sandbox failures recorded only in the replica."""
    con = sqlite3.connect(path)
    try:
        out = defaultdict(set)
        for source, rid, reason in con.execute(
                "select source, rid, reason from void_requests"):
            r = canon_rid(rid)
            if r:
                out[norm_source(source)].add(r)
        return out
    finally:
        con.close()


def load_presentation(path, ctx):
    """(job, item) -> slot1_candidate / slot1_baseline from the rescored export."""
    out = {}
    for line in read_lines_mixed(path):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        job = canon_job(d.get("job"))
        item = canon_item(d.get("item"))
        pres = clean(d.get("presentation")).lower()
        if job is None or item is None or pres not in (
                "slot1_candidate", "slot1_baseline"):
            continue
        out[(job, item)] = pres
    return out


def load_manual_overrides(path, ctx):
    """(job, item, slot) -> candidate/baseline/tie from the final review."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    best = {}
    try:
        for ws in wb.worksheets:
            hdr = None
            for row in ws.iter_rows(values_only=True):
                if row is None or all(v is None for v in row):
                    continue
                vals = [clean(v) for v in row]
                if hdr is None:
                    hdr = [v.lower() for v in vals]
                    continue
                d = dict(zip(hdr, vals))
                if clean(d.get("status")).lower() != "final":
                    continue
                job = canon_job(d.get("job"))
                item = canon_item(d.get("item"))
                slot = parse_int(d.get("slot"))
                if job is None or item is None or slot is None:
                    continue
                when = serial_to_dt(d.get("reviewed_at")) or parse_instant(
                    d.get("reviewed_at"))
                verdict = clean(d.get("verdict")).lower()
                if verdict in ("=", "tie"):
                    verdict = "tie"
                elif verdict.startswith("cand"):
                    verdict = "candidate"
                elif verdict.startswith("base"):
                    verdict = "baseline"
                else:
                    continue
                key = (job, item, slot)
                cur = best.get(key)
                rank = when or datetime.min.replace(tzinfo=timezone.utc)
                if cur is None or rank >= cur[0]:
                    best[key] = (rank, verdict)
    finally:
        wb.close()
    return {k: v[1] for k, v in best.items()}


def load_routing(path, errata, jobs, restore_jobs):
    """job -> (primary source, copy source)."""
    cand = defaultdict(list)
    for idx, hdr, recs in md_tables(path):
        if not hdr or "primary_source" not in hdr:
            continue
        for d in recs:
            job = canon_job(d.get("job"))
            if job is None or job not in jobs:
                continue
            if errata.entry_voided("source_conventions.md", job, d.get("revision")):
                continue
            rev = parse_rev(d.get("revision"), 0)
            cand[job].append((rev, norm_source(d.get("primary_source")),
                              norm_source(d.get("copy_source"))))
    out = {}
    for job, rs in cand.items():
        if job in restore_jobs:
            out[job] = ("scores_staging", None)
            continue
        rs.sort(key=lambda x: -x[0])
        rev, primary, copy = rs[0]
        if primary == "scores_staging":
            out[job] = (None, None)
            continue
        out[job] = (primary, None if copy in ("-", "") else copy)
    for job in restore_jobs:
        out.setdefault(job, ("scores_staging", None))
    return out


def load_field_precedence(path, errata, jobs):
    """((suite, field) -> {pair -> winner}) and the bridge-class job set."""
    tables = html_tables(read_text(path))
    winners = {}
    classes = {}
    for idx, hdr, recs in tables:
        if not hdr:
            continue
        if "winner" in hdr:
            for d in recs:
                suite = canon_suite(d.get("suite"))
                field = clean(d.get("field")).lower()
                s1 = norm_source(d.get("source_1"))
                s2 = norm_source(d.get("source_2"))
                w = norm_source(d.get("winner"))
                if suite is None or not field:
                    continue
                winners[(suite, field, frozenset((s1, s2)))] = w
        elif "class" in hdr:
            best = {}
            for d in recs:
                job = canon_job(d.get("job"))
                if job is None or job not in jobs:
                    continue
                if errata.entry_voided("field_precedence.html", job,
                                       d.get("revision")):
                    continue
                rev = parse_rev(d.get("revision"), 0)
                cls = cell(d.get("class")).lower()
                cls = "bridge" if cls in ("br", "bridge") else "standard"
                cur = best.get(job)
                if cur is None or rev > cur[0]:
                    best[job] = (rev, cls)
            for job, (rev, cls) in best.items():
                classes[job] = cls
    return winners, classes


def load_control_totals(path, errata, jobs):
    rows = html_tables(read_text(path))
    best = {}
    for idx, hdr, recs in rows:
        if not hdr or "expected_rows" not in hdr:
            continue
        for d in recs:
            job = canon_job(d.get("job"))
            if job is None or job not in jobs:
                continue
            if errata.entry_voided("control_totals.html", job, d.get("revision")):
                continue
            rev = parse_rev(d.get("revision"), 0)
            cur = best.get(job)
            if cur is None or rev > cur[0]:
                best[job] = (rev, d)
    out = {}
    for job, (rev, d) in best.items():
        exp = clean(d.get("expected_rows")).lower().replace("rows", "").strip()
        out[job] = {"expected_rows": parse_int(exp),
                    "value_sum": parse_grouped_number(d.get("value_sum"))}
    return out


def parse_grouped_number(txt):
    """A number written with either en_US or de_DE grouping."""
    t = clean(txt)
    if t == "":
        return None
    neg = t.startswith("-")
    t = t.lstrip("+-")
    has_dot = "." in t
    has_comma = "," in t
    if has_dot and has_comma:
        locale = "de_DE" if t.rindex(",") > t.rindex(".") else "en_US"
    elif has_comma:
        tail = t.rsplit(",", 1)[1]
        locale = "en_US" if len(tail) == 3 else "de_DE"
    elif has_dot:
        tail = t.rsplit(".", 1)[1]
        locale = "de_DE" if len(tail) == 3 else "en_US"
    else:
        locale = "en_US"
    v = parse_locale_number(t, locale)
    if v is None:
        return None
    return -v if neg else v


def load_legacy_crosswalk(text, errata, registered):
    """Legacy item code -> item id from the methodology appendix."""
    best = {}
    for idx, hdr, recs in pdf_tables(text):
        if not hdr or "legacy_code" not in hdr:
            continue
        for d in recs:
            code = canon_lc(re.sub(r"\*", "", clean(d.get("legacy_code"))))
            item = canon_item(re.sub(r"\*", "", clean(d.get("item_id"))))
            if code is None or item is None or item not in registered:
                continue
            if errata.entry_voided("methodology_appendix.pdf", code,
                                   d.get("revision")):
                continue
            rev = parse_rev(d.get("revision"), 0)
            cur = best.get(code)
            if cur is None or rev > cur[0]:
                best[code] = (rev, item)
    return {k: v[1] for k, v in best.items()}


def load_contamination(path, errata, registered, items):
    contaminated = set()
    for line in read_lines_mixed(path):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("retracted") is True:
            continue
        item = canon_item(d.get("item", d.get("item_ref")))
        if item is None or item not in registered:
            continue
        if norm_shard(d.get("shard")) in errata.exclude_shards:
            continue
        ov = d.get("overlap")
        if ov is None:
            continue
        val = parse_locale_number(ov) if isinstance(ov, str) else as_fraction(ov)
        if val is None:
            continue
        det = clean(d.get("detector")).lower()
        if det == "ngram-v1":
            val = val / 100
        val = round_half_even(val, 4)
        if val >= CONTAM_THRESHOLD[items[item]["suite"]]:
            contaminated.add(item)
    return contaminated


def load_job_configs(path, errata, jobs):
    """job -> {harness, taxonomy, grader, samples}."""
    import tomllib
    with open(path, "rb") as fh:
        doc = tomllib.load(fh)
    best = {}
    for j in doc.get("job", []):
        job = canon_job(j.get("id"))
        if job is None or job not in jobs:
            continue
        rev = parse_rev(j.get("revision"), 0)
        if errata.entry_voided("job_configs.toml", job, str(j.get("revision"))):
            continue
        cur = best.get(job)
        if cur is None or rev > cur[0]:
            best[job] = (rev, j)
    out = {}
    for job, (rev, j) in best.items():
        settings = j.get("settings") or {}
        harness = clean(j.get("harness", settings.get("harness"))).lower()
        harness = re.sub(r"^(harness-|h)", "", harness)
        taxonomy = "v2" if harness.startswith("4") else "v1"
        grader = "g3" if harness.startswith("4") else "g2"
        samples = j.get("samples", settings.get("samples"))
        out[job] = {"harness": harness, "taxonomy": taxonomy, "grader": grader,
                    "samples": parse_int(samples, 1)}
    return out


# ==========================================================================
# text normalisation and grading helpers
# ==========================================================================

STRIP_PUNCT = ".,;:!?\"'"


def strip_marks(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def norm_answer(s, marks=False):
    if s is None:
        return None
    t = unicodedata.normalize("NFC", str(s))
    if marks:
        t = unicodedata.normalize("NFC", strip_marks(t))
    t = t.casefold()
    t = " ".join(t.split())
    return t.strip(STRIP_PUNCT)


def fmt2(value: Fraction) -> str:
    r = round_half_even(value, 2)
    neg = r < 0
    if neg:
        r = -r
    whole = r.numerator // r.denominator
    rest = (r - whole) * 100
    return "%s%d.%02d" % ("-" if neg else "", whole,
                          rest.numerator // rest.denominator)


def arith_correct(answer, gold_txt, tol):
    gold = parse_locale_number(gold_txt)
    if gold is None or answer is None:
        return 0
    kind = tol[0] if tol else "exact"
    a = round_half_even(answer, 2)
    if kind == "exact":
        return 1 if a == round_half_even(gold, 2) else 0
    if kind == "abs":
        lim = tol[1] if tol[1] is not None else Fraction(1, 100)
        return 1 if abs(a - gold) <= lim else 0
    return 1 if abs(a - gold) <= abs(gold) / 100 else 0


def resolve_label(raw, taxonomy, aliases):
    if raw is None:
        return None
    ent = aliases.get(nfc(raw))
    if ent is None:
        ent = aliases.get(nfc(clean(raw)))
    if ent is None:
        return None
    cls = ent.get(taxonomy)
    if cls is None:
        return None
    return to_v2(cls) if taxonomy == "v1" else clean(cls).lower()


VERDICT_KIND = {"A": "first", "B": "second", "T": "tie",
                "1": "first", "2": "second", "0": "tie"}


def verdict_side(verdict_txt, slot, presentation):
    """'candidate', 'baseline' or 'tie' for one judged ordering."""
    kind = VERDICT_KIND.get(clean(verdict_txt).upper())
    if kind is None or kind == "tie":
        return "tie"
    slot1_cand = presentation != "slot1_baseline"
    candidate_first = slot1_cand if slot == 1 else not slot1_cand
    if kind == "first":
        return "candidate" if candidate_first else "baseline"
    return "baseline" if candidate_first else "candidate"


# ==========================================================================
# certification of per-item values
# ==========================================================================

def parse_source(data_dir, name, ctx):
    src = norm_source(name)
    path = os.path.join(data_dir, name)
    if name.startswith("results_fleet"):
        return parse_fleet(path, src, ctx)
    if name == "legacy_results.txt":
        return parse_legacy(path, src, ctx)
    if name == "code_samples.jsonl":
        return parse_code_samples(path, src, ctx)
    if name in ("judge_verdicts.jsonl", "judge_verdicts_rescored.jsonl"):
        return parse_judge(path, src, ctx)
    if name == "rerun_results.jsonl":
        return parse_rerun(path, src, ctx)
    if name == "intent_predictions.csv":
        return parse_intent_predictions(path, src, ctx)
    if name.endswith(".parquet"):
        return parse_parquet(path, name, ctx)
    if name == "eval_store.db":
        return parse_eval_store(path, src, ctx, "value")
    if name == "eval_store_mirror.db":
        return parse_eval_store(path, src, ctx, "result_value")
    raise ValueError("unknown result source %s" % name)


def collect_live_records(data_dir, ctx):
    """Live records per job, plus the per-source audit counts."""
    audit = {}
    live = defaultdict(list)
    mirror_voids = ctx["mirror_voids"]
    errata = ctx["errata"]
    for name in RESULT_SOURCES:
        src = norm_source(name)
        recs, rows, reversed_rids = parse_source(data_dir, name, ctx)
        audit[name] = {"result_rows": rows, "used": 0}
        if src in ("judge_verdicts_rescored", "eval_store_mirror"):
            continue
        void_rids = set(errata.void_rows.get(src, ()))
        void_rids |= set(mirror_voids.get(src, ()))
        kept = defaultdict(dict)
        for rec in recs:
            job = rec.job
            info = ctx["jobs"][job]
            if ctx["disposition"][job] != "authoritative":
                continue
            primary, copy = ctx["routing"].get(job, (None, None))
            if src not in (primary, copy):
                continue
            if rec.rid is not None and rec.rid in void_rids:
                continue
            if rec.rid is not None and rec.rid in reversed_rids:
                continue
            if rec.f.get("shadow"):
                continue
            if src == "code_samples" and rec.f.get("exit") == 137 \
                    and rec.f.get("passed") == -1:
                continue
            seal = ctx["seals"].get(job)
            if rec.emitted is None or (seal is not None and rec.emitted > seal):
                continue
            item = rec.item
            if item is None and rec.pos is not None:
                item = ctx["by_pos"].get((info["benchmark"], info["shard"],
                                          rec.pos))
                rec.item = item
            if item is None or item not in ctx["items"]:
                continue
            placed = ctx["shard_map"].get(item)
            if placed is None or placed[0] != info["benchmark"] \
                    or placed[1] != info["shard"]:
                continue
            if item not in ctx["eligible"]:
                continue
            key = (src, item, rec.sample, rec.slot)
            cur = kept[job].get(key)
            if cur is None or rec.emitted >= cur.emitted:
                kept[job][key] = rec
        for job, recmap in kept.items():
            live[job].extend(recmap.values())
    return live, audit


def field_winner(ctx, job, suite, field, primary, copy):
    if copy is None:
        return primary
    pair = frozenset((primary, copy))
    w = ctx["precedence"].get((suite, field, pair), primary)
    if ctx["job_class"].get(job) == "bridge":
        others = pair - {w}
        if others:
            w = next(iter(others))
    return w


def pick(ctx, job, suite, field, by_src, primary, copy, item, sample=0,
         slot=None):
    w = field_winner(ctx, job, suite, field, primary, copy)
    recs = by_src.get(w, {}).get((item, sample, slot))
    if recs:
        return recs[-1], w
    return None, w


def certify_items(ctx, live, audit):
    """(model, item) -> certified fields; records the sources actually used."""
    values = {}
    used = defaultdict(set)
    for job, recs in live.items():
        info = ctx["jobs"][job]
        suite = info["benchmark"]
        model = info["model"]
        primary, copy = ctx["routing"].get(job, (None, None))
        by_src = defaultdict(lambda: defaultdict(list))
        for rec in recs:
            by_src[rec.src][(rec.item, rec.sample, rec.slot)].append(rec)
        items_seen = {k[0] for m in by_src.values() for k in m}
        cfg = ctx["configs"].get(job, {"taxonomy": "v1", "grader": "g2"})
        for item in items_seen:
            out = certify_one(ctx, job, suite, item, by_src, primary, copy, cfg,
                              used)
            if out is not None:
                values[(model, item)] = out
    for src, rids in used.items():
        for name in RESULT_SOURCES:
            if norm_source(name) == src:
                audit[name]["used"] = len(rids)
    return values


def certify_one(ctx, job, suite, item, by_src, primary, copy, cfg, used):
    gold = ctx["gold"].get(item, "")
    params = ctx["params"].get(item, {})
    ck = ctx["lineage"].get(ctx["jobs"][job]["checkpoint"], {})
    tokenizer = ck.get("tokenizer", "hbpe")
    window = ck.get("context_window")

    def mark(rec, src):
        if rec is not None and rec.rid is not None:
            used[src].add(rec.rid)

    if suite == "arith":
        rec, w = pick(ctx, job, suite, "answer", by_src, primary, copy, item)
        if rec is None:
            return None
        mark(rec, w)
        ans = rec.f.get("answer")
        if ans == "NA" or ans is None:
            return {"value": None, "confidence": None, "correct": 0}
        return {"value": fmt2(ans), "confidence": None,
                "correct": arith_correct(ans, gold, params.get("tolerance"))}

    if suite == "code":
        tests = params.get("tests")
        if tests is None:
            tests = parse_int(gold)
        w = field_winner(ctx, job, suite, "passed", primary, copy)
        passing = 0
        found = False
        for sample in range(CODE_SAMPLES):
            recs = by_src.get(w, {}).get((item, sample, None))
            if not recs:
                continue
            found = True
            rec = recs[-1]
            mark(rec, w)
            if tests is not None and rec.f.get("passed") == tests:
                passing += 1
        if not found:
            return None
        return {"value": passing, "confidence": None, "correct": None}

    if suite == "intent":
        rec, w = pick(ctx, job, suite, "label", by_src, primary, copy, item)
        if rec is None:
            return None
        mark(rec, w)
        cls = resolve_label(rec.f.get("label"), cfg["taxonomy"], ctx["aliases"])
        gold_cls = to_v2(gold)
        return {"value": cls, "confidence": None,
                "correct": 1 if cls is not None and cls == gold_cls else 0}

    if suite == "safety":
        rec, w = pick(ctx, job, suite, "score", by_src, primary, copy, item)
        if rec is None:
            return None
        mark(rec, w)
        score = rec.f.get("score")
        if score is None:
            return None
        return {"value": score, "confidence": None, "correct": None}

    if suite == "mcq":
        orec, ow = pick(ctx, job, suite, "option", by_src, primary, copy, item)
        crec, cw = pick(ctx, job, suite, "conf", by_src, primary, copy, item)
        if orec is None and crec is None:
            return None
        mark(orec, ow)
        mark(crec, cw)
        option = orec.f.get("option") if orec is not None else None
        conf = crec.f.get("conf") if crec is not None else None
        gold_opt = clean(gold).upper()[:1]
        return {"value": option, "confidence": conf,
                "correct": 1 if option is not None and option == gold_opt else 0}

    if suite == "pref":
        pres = ctx["presentation"].get((job, item))
        prefs = {}
        for slot in (1, 2):
            rec, w = pick(ctx, job, suite, "verdict", by_src, primary, copy,
                          item, 0, slot)
            override = None
            if primary == "judge_verdicts":
                override = ctx["overrides"].get((job, item, slot))
            if rec is not None:
                mark(rec, w)
            if override is not None:
                prefs[slot] = override
                continue
            if rec is None:
                continue
            prefs[slot] = verdict_side(rec.f.get("verdict"), slot, pres)
        if not prefs:
            return None
        sides = (prefs.get(1), prefs.get(2))
        if sides[0] == "candidate" and sides[1] == "candidate":
            verdict = "win"
        elif sides[0] == "baseline" and sides[1] == "baseline":
            verdict = "loss"
        else:
            verdict = "tie"
        return {"value": verdict, "confidence": None, "correct": None}

    if suite in ("longctx", "multiling"):
        rec, w = pick(ctx, job, suite, "answer", by_src, primary, copy, item)
        if rec is None:
            return None
        mark(rec, w)
        marks = suite == "multiling" and cfg["grader"] == "g3"
        ans = norm_answer(rec.f.get("answer"), marks)
        gold_n = norm_answer(gold, marks)
        correct = 1 if ans is not None and ans == gold_n else 0
        if suite == "longctx":
            toks = (ctx["ctx_len"].get(item) or {}).get(tokenizer)
            if window is not None and toks is not None and toks > window:
                correct = 0
        return {"value": ans, "confidence": None, "correct": correct}

    return None


# ==========================================================================
# baseline
# ==========================================================================

def load_baseline(path, ctx):
    rows = delim_rows(path, ",")
    best = {}
    for r in rows:
        if clean(r.get("status")).lower() == "withdrawn":
            continue
        ref = r.get("ref")
        item = canon_item(ref)
        if item is None:
            code = canon_lc(ref)
            item = ctx["crosswalk"].get(code) if code else None
        if item is None or item not in ctx["eligible"]:
            continue
        rev_txt = clean(r.get("revised"))
        revised = dmy(rev_txt) or serial_to_dt(rev_txt)
        if revised is None:
            continue
        if (item, revised) in ctx["errata"].void_baseline:
            continue
        cur = best.get(item)
        if cur is None or revised >= cur[0]:
            best[item] = (revised, r)
    bck = ctx["lineage"].get(ctx["certified"][BASELINE]["checkpoint"], {})
    tokenizer = bck.get("tokenizer", "ospsp")
    window = bck.get("context_window")
    out = {}
    for item, (revised, r) in best.items():
        suite = ctx["items"][item]["suite"]
        locale = "de_DE" if revised < datetime(2025, 8, 1, tzinfo=timezone.utc) \
            else "en_US"
        gold = ctx["gold"].get(item, "")
        params = ctx["params"].get(item, {})
        val_txt = r.get("value")
        conf_txt = r.get("confidence")
        rec = {"value": None, "confidence": None, "correct": None}
        if suite == "arith":
            if clean(val_txt).upper() in ("N/A", "NA"):
                rec["correct"] = 0
            else:
                v = parse_locale_number(val_txt, locale)
                if v is None:
                    rec["correct"] = 0
                else:
                    v = round_half_even(v, 2)
                    rec["value"] = fmt2(v)
                    rec["correct"] = arith_correct(v, gold,
                                                   params.get("tolerance"))
        elif suite == "code":
            rec["value"] = parse_int(val_txt, 0)
        elif suite == "intent":
            cls = to_v2(val_txt)

            rec["value"] = cls
            rec["correct"] = 1 if cls == to_v2(gold) else 0
        elif suite == "safety":
            v = parse_locale_number(val_txt, locale)
            rec["value"] = round_half_even(v, 3) if v is not None else None
        elif suite == "mcq":
            opt = clean(val_txt).upper()[:1]
            conf = parse_locale_number(conf_txt, locale)
            rec["value"] = opt or None
            rec["confidence"] = round_half_even(conf, 4) if conf is not None \
                else None
            rec["correct"] = 1 if opt and opt == clean(gold).upper()[:1] else 0
        elif suite in ("longctx", "multiling"):
            marks = suite == "multiling"
            ans = norm_answer(val_txt, marks)
            rec["value"] = ans
            correct = 1 if ans == norm_answer(gold, marks) else 0
            if suite == "longctx":
                toks = (ctx["ctx_len"].get(item) or {}).get(tokenizer)
                if window is not None and toks is not None and toks > window:
                    correct = 0
            rec["correct"] = correct
        else:
            continue
        out[item] = rec
    return out



# ==========================================================================
# metrics
# ==========================================================================

def comb(n, k):
    if k < 0 or k > n:
        return 0
    r = 1
    for i in range(k):
        r = r * (n - i) // (i + 1)
    return r


def mean_fraction(vals):
    vals = list(vals)
    if not vals:
        return None
    total = Fraction(0)
    for v in vals:
        total += as_fraction(v)
    return total / len(vals)


def accuracy(recs):
    vals = [r["correct"] for r in recs if r.get("correct") is not None]
    return mean_fraction(vals)


def code_pass_at(recs, k):
    vals = []
    for r in recs:
        c = r.get("value")
        if c is None:
            continue
        vals.append(Fraction(1) - Fraction(comb(CODE_SAMPLES - c, k),
                                           comb(CODE_SAMPLES, k)))
    return mean_fraction(vals)


def macro_f1(pairs):
    """pairs: list of (gold class, predicted class)."""
    classes = set()
    for g, p in pairs:
        if g:
            classes.add(g)
        if p:
            classes.add(p)
    if not classes:
        return None
    scores = []
    for c in sorted(classes):
        tp = sum(1 for g, p in pairs if g == c and p == c)
        fp = sum(1 for g, p in pairs if g != c and p == c)
        fn = sum(1 for g, p in pairs if g == c and p != c)
        den = 2 * tp + fp + fn
        scores.append(Fraction(2 * tp, den) if den else Fraction(0))
    return mean_fraction(scores)


def auroc(pairs):
    """pairs: list of (score, gold) with gold 1 = unsafe."""
    pos = [s for s, g in pairs if g == 1]
    neg = [s for s, g in pairs if g == 0]
    if not pos or not neg:
        return None
    neg_sorted = sorted(neg)
    total = Fraction(0)
    import bisect
    for s in pos:
        lo = bisect.bisect_left(neg_sorted, s)
        hi = bisect.bisect_right(neg_sorted, s)
        total += lo + Fraction(hi - lo, 2)
    return total / (len(pos) * len(neg))


def ece_bins(entries):
    """entries: list of (confidence, correct, item_id); 10 equal-mass bins."""
    entries = sorted(entries, key=lambda e: (e[0], e[2]))
    n = len(entries)
    bins = []
    if n == 0:
        return None, [{"count": 0, "mean_confidence": None, "accuracy": None}
                      for _ in range(10)]
    base = n // 10
    extra = n % 10
    idx = 0
    ece = Fraction(0)
    for b in range(10):
        size = base + (1 if b < extra else 0)
        chunk = entries[idx:idx + size]
        idx += size
        if not chunk:
            bins.append({"count": 0, "mean_confidence": None, "accuracy": None})
            continue
        mc = mean_fraction([c for c, _, _ in chunk])
        acc = mean_fraction([k for _, k, _ in chunk])
        bins.append({"count": len(chunk), "mean_confidence": mc,
                     "accuracy": acc})
        ece += Fraction(len(chunk), n) * abs(acc - mc)
    return ece, bins


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return Fraction(1)
    total = 0
    for i in range(min(b, c) + 1):
        total += comb(n, i)
    p = Fraction(2 * total, 2 ** n)
    return min(Fraction(1), p)


def normalised(metric, chance):
    if metric is None:
        return None
    if chance == 1:
        return None
    return (metric - chance) / (1 - chance)


def suite_metric_values(ctx, per_item, model):
    """Primary metric per suite for one model."""
    out = {}
    elig = ctx["eligible_by_suite"]
    for suite in SUITES:
        recs = [per_item[i] for i in elig[suite] if i in per_item]
        if suite in ("arith", "mcq", "longctx"):
            out[suite] = {"accuracy": accuracy(recs), "n": len(elig[suite])}
        elif suite == "code":
            out[suite] = {"pass@1": code_pass_at(recs, 1),
                          "pass@5": code_pass_at(recs, 5),
                          "n": len(elig[suite])}
        elif suite == "intent":
            pairs = [(to_v2(ctx["gold"].get(i, "")), per_item[i]["value"])
                     for i in elig[suite] if i in per_item]
            out[suite] = {"macro_f1": macro_f1(pairs), "n": len(elig[suite])}
        elif suite == "safety":
            pairs = []
            for i in elig[suite]:
                if i not in per_item:
                    continue
                score = per_item[i]["value"]
                g = parse_int(ctx["gold"].get(i, ""))
                if score is None or g is None:
                    continue
                pairs.append((score, g))
            out[suite] = {"auroc": auroc(pairs), "n": len(elig[suite])}
        elif suite == "multiling":
            by_lang = defaultdict(list)
            for i in elig[suite]:
                lang = ctx["languages"].get(i)
                if lang is None:
                    continue
                by_lang[lang].append(i)
            keep = [l for l, its in by_lang.items()
                    if len(its) >= ctx["slices"]["lang_min_support"]]
            accs = []
            for lang in sorted(keep):
                recs = [per_item[i] for i in by_lang[lang] if i in per_item]
                a = accuracy(recs)
                if a is not None:
                    accs.append(a)
            out[suite] = {"macro_accuracy": mean_fraction(accs),
                          "n": len(elig[suite]), "languages": len(keep)}
        elif suite == "pref":
            wins = sum(1 for i in elig[suite]
                       if i in per_item and per_item[i]["value"] == "win")
            ties = sum(1 for i in elig[suite]
                       if i in per_item and per_item[i]["value"] == "tie")
            losses = sum(1 for i in elig[suite]
                         if i in per_item and per_item[i]["value"] == "loss")
            n = wins + ties + losses
            rate = (Fraction(wins) + Fraction(ties, 2)) / n if n else None
            out[suite] = {"wins": wins, "ties": ties, "losses": losses,
                          "win_rate": rate, "n": len(elig[suite])}
    return out


def primary_metric(suite, m, is_baseline):
    if suite in ("arith", "mcq", "longctx"):
        return m[suite]["accuracy"]
    if suite == "code":
        return m[suite]["pass@1"]
    if suite == "intent":
        return m[suite]["macro_f1"]
    if suite == "safety":
        return m[suite]["auroc"]
    if suite == "multiling":
        return m[suite]["macro_accuracy"]
    if suite == "pref":
        return Fraction(1, 2) if is_baseline else m[suite]["win_rate"]
    return None


def slice_match(ctx, item, cond):
    attrs = ctx["slice_attrs"].get(item, {})
    region = ctx["slices"]["regions"].get(item)
    for attr, vals in cond.items():
        if attr == "region":
            if region is None or region.lower() not in vals:
                return False
        else:
            v = attrs.get(attr)
            if v is None or v.lower() not in vals:
                return False
    return True


# ==========================================================================
# orchestration
# ==========================================================================

def load_constants(data_dir, metric_text):
    """Re-read the quarter's thresholds, window and conventions from the docs."""
    global WINDOW_START, WINDOW_END, TAG_CUTOFF, ECE_CAP, SAFETY_FLOOR
    global CODE_SAMPLES, MANIFEST_SHEETS
    policy = read_text_mixed(os.path.join(data_dir, "certification_policy.md"))
    conv = read_text_mixed(os.path.join(data_dir, "source_conventions.md"))

    m = re.search(r"cutoff\s+(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", policy)
    if m:
        TAG_CUTOFF = parse_instant(m.group(1))
    m = re.search(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\s+inclusive to\s+"
                  r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\s+exclusive", policy)
    if m:
        WINDOW_START = parse_instant(m.group(1))
        WINDOW_END = parse_instant(m.group(2))
    m = re.search(r"calibration error is at most (\d+(?:\.\d+)?)", policy)
    if m:
        ECE_CAP = Fraction(m.group(1))
    m = re.search(r"AUROC is at least (\d+(?:\.\d+)?)", policy)
    if m:
        SAFETY_FLOOR = Fraction(m.group(1))

    m = re.search(r"Contamination thresholds:([^\n]*)", metric_text)
    if m:
        for suite, val in re.findall(r"(\w+)\s+(\d+(?:\.\d+)?)", m.group(1)):
            s = canon_suite(suite)
            if s:
                CONTAM_THRESHOLD[s] = Fraction(val)
    m = re.search(r"of n\s*=\s*(\d+)", metric_text)
    if m:
        CODE_SAMPLES = int(m.group(1))
    for field, name in (("answer", "arithmetic answers"),
                        ("score", "safety scores"),
                        ("conf", "confidences")):
        m = re.search(re.escape(name) + r"\s+(\d+)\s+decimals", conv)
        if m:
            PRECISION[field] = int(m.group(1))
    m = re.search(r"sheets hold these suites:([^\n]*)", conv)
    if m:
        sheets = {}
        for sheet, suites in re.findall(r"([\w]+)\s*\(([^)]*)\)", m.group(1)):
            names = {canon_suite(s) for s in suites.split(",")}
            sheets[sheet.strip().lower()] = {s for s in names if s}
        if sheets:
            MANIFEST_SHEETS = sheets
    PARQUET_SEC_GROUPS.clear()
    for name, groups in re.findall(
            r"(\S+\.parquet):\s*row groups ([\d,\s]+?) store emitted as epoch "
            r"seconds", conv):
        PARQUET_SEC_GROUPS[name] = {int(g) for g in re.findall(r"\d+", groups)}
    m = re.search(r"Offsets during the window:([^\n]*)", conv)
    if m:
        for zone, sign, hh, mm in re.findall(
                r"([A-Za-z_/]+)\s*([+-])(\d\d):(\d\d)", m.group(1)):
            delta = timedelta(hours=int(hh), minutes=int(mm))
            ZONE_OFFSET[zone] = delta if sign == "+" else -delta


def build_context(data_dir):
    ctx = {}
    p = lambda name: os.path.join(data_dir, name)
    errata = Errata(p("errata_register.docx"))
    ctx["errata"] = errata
    metric_text = pdf_text(p("metric_definitions.pdf"))
    method_text = pdf_text(p("methodology_appendix.pdf"))
    load_constants(data_dir, metric_text)
    shard_map, shard_revs = load_shard_map(metric_text, errata)
    registry = load_item_registry(p("item_registry.csv"), errata)
    items = {i: v for i, v in registry.items() if i in shard_map}
    ctx["shard_map"] = shard_map
    ctx["by_pos"] = build_position_map(shard_map, shard_revs, items)
    ctx["items"] = items

    retired = load_retired(p("suite_manifest.xlsx"), errata, items, items)
    duplicate = load_dedup(p("dedup_clusters.tsv"), errata, items)
    contaminated = load_contamination(p("contamination_hits.jsonl"), errata,
                                      items, items)
    held_out = load_scope(p("certification_policy.md"), errata, items)
    reasons = {}
    eligible = set()
    for item in items:
        if item in retired:
            reasons[item] = "retired"
        elif item in duplicate:
            reasons[item] = "duplicate"
        elif item in contaminated:
            reasons[item] = "contaminated"
        elif item in held_out:
            reasons[item] = "out_of_scope"
        else:
            reasons[item] = None
            eligible.add(item)
    ctx["reasons"] = reasons
    ctx["eligible"] = eligible
    by_suite = defaultdict(list)
    for item in sorted(eligible):
        by_suite[items[item]["suite"]].append(item)
    ctx["eligible_by_suite"] = by_suite

    lineage = load_lineage(p("checkpoint_lineage.json"),
                           p("checkpoint_lineage_snapshot.json"), errata)
    ctx["lineage"] = lineage
    events = load_tag_events(p("model_tags.yaml"))
    decisions, seals = load_mbox(p("evalops_notifications.mbox"))
    certified = resolve_lineage(events, decisions)
    ctx["certified"] = certified
    ctx["seals"] = seals

    jobs = load_registry(p("run_registry.xml"), lineage, certified)
    ctx["jobs"] = jobs
    inventory = load_host_inventory(p("host_inventory.ini"), errata)
    offsets = load_clock_offsets(p("clock_offsets.txt"), errata)
    ctx["offsets"] = offsets
    ctx["zc"] = ZoneClock(inventory, offsets)
    ctx["legacy_map"] = load_legacy_map(p("run_registry_export.xml"))
    subs, reruns = load_harness(p("harness_events.log"), jobs,
                                ctx["legacy_map"], ctx["zc"])
    ctx["subs"] = subs
    ctx["reruns"] = reruns
    ctx["maintenance"] = load_maintenance(p("maintenance_windows.ics"))
    ctx["decisions"] = load_review_minutes(p("review_minutes.docx"), errata, jobs)
    ctx["disposition"] = decide_dispositions(ctx)
    ctx["routing"] = load_routing(p("source_conventions.md"), errata, jobs,
                                  errata.restore_jobs)
    precedence, job_class = load_field_precedence(p("field_precedence.html"),
                                                  errata, jobs)
    ctx["precedence"] = precedence
    copies = {j for j, (pr, cp) in ctx["routing"].items() if cp}
    ctx["job_class"] = {j: c for j, c in job_class.items()
                        if c != "bridge" or j in copies}
    ctx["configs"] = load_job_configs(p("job_configs.toml"), errata, jobs)
    ctx["control"] = load_control_totals(p("control_totals.html"), errata, jobs)

    gold = load_gold(p("gold_labels.tsv"), errata, items)
    ticket_items = load_ticket_items(p("gold_labels_corrected.csv"), errata, items)
    errata_values = load_errata_values(p("grader_errata.xml"))
    ctx["gold"] = apply_errata_to_gold(gold, errata_values, ticket_items)
    ctx["params"] = load_scoring_parameters(p("scoring_parameters.xlsx"), errata,
                                            items)
    aliases, tax_classes = load_label_aliases(p("label_aliases.json"), errata)
    ctx["aliases"] = aliases
    ctx["taxonomy_classes"] = tax_classes
    locale_map = load_locale_map(p("locale_codes_legacy.tsv"), errata)
    ctx["languages"] = load_prompt_locales(p("prompt_locales.tsv"), errata,
                                           items, locale_map)
    ctx["ctx_len"] = load_context_lengths(p("context_lengths.csv"), errata, items)
    ctx["slices"] = load_slices(p("slice_definitions.yaml"), errata, items)
    ctx["slice_attrs"] = load_slice_attributes(p("slice_attributes.csv"), errata,
                                               items, ctx["slices"]["domain_codes"])
    ctx["weights"] = load_suite_weights(p("scorecard_prelim.xlsx"), errata, items)
    ctx["mirror_voids"] = load_mirror_voids(p("eval_store_mirror.db"))
    ctx["presentation"] = load_presentation(p("judge_verdicts_rescored.jsonl"), ctx)
    ctx["overrides"] = load_manual_overrides(p("manual_overrides.xlsx"), ctx)
    ctx["crosswalk"] = load_legacy_crosswalk(method_text, errata, items)
    ctx["candidates"] = sorted({j["model"] for j in jobs.values()})
    return ctx


def decide_dispositions(ctx):
    jobs = ctx["jobs"]
    errata = ctx["errata"]
    subs = ctx["subs"]
    decisions = ctx["decisions"]
    reruns = ctx["reruns"]
    newer = {n for _, n in reruns}
    superseded = {o for o, n in reruns
                  if decisions.get(n) == "rerun-approved"}
    out = {}
    for job, info in jobs.items():
        inst = subs.get(job)
        week = iso_week(inst) if inst is not None else None
        if job in errata.void_jobs:
            out[job] = "voided"
            continue
        if week is not None and ctx["zc"].entry(info["host"], week)["fleet"] == "s":
            out[job] = "staging_host"
            continue
        if info["checkpoint"] != ctx["certified"].get(
                info["model"], {}).get("checkpoint"):
            out[job] = "stale_checkpoint"
            continue
        if inst is None or not (WINDOW_START <= inst < WINDOW_END):
            out[job] = "outside_window"
            continue
        in_window = any(a <= inst < b for a, b in
                        ctx["maintenance"].get(info["host"], ()))
        if in_window and decisions.get(job) != "exempt-maintenance":
            out[job] = "maintenance"
            continue
        if job in superseded:
            out[job] = "superseded"
            continue
        if job in newer and decisions.get(job) != "rerun-approved":
            out[job] = "rerun_denied"
            continue
        out[job] = "authoritative"
    return out


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def dump_json(path, obj):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2,
                                sort_keys=True) + "\n")


def dump_jsonl(path, rows):
    buf = io.StringIO()
    for row in rows:
        buf.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_text(path, buf.getvalue())


def run(data_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ctx = build_context(data_dir)
    live, audit = collect_live_records(data_dir, ctx)
    values = certify_items(ctx, live, audit)
    baseline = load_baseline(os.path.join(data_dir, "baseline_reference.csv"), ctx)
    per_model = defaultdict(dict)
    for (model, item), rec in values.items():
        per_model[model][item] = rec
    per_model[BASELINE] = baseline
    candidates = ctx["candidates"]
    models = candidates + [BASELINE]

    # ---- lineage.json
    lineage_out = {}
    for alias in models:
        c = ctx["certified"].get(alias, {})
        lineage_out[alias] = {
            "checkpoint": c.get("checkpoint"),
            "effective_from": iso_z(c["effective_from"]) if c.get("effective_from")
            else None,
            "approval_ref": c.get("approval_ref"),
            "voided_promotions": c.get("voided_promotions", 0),
        }
    dump_json(os.path.join(out_dir, "lineage.json"), lineage_out)

    # ---- job_dispositions.jsonl
    rows = []
    for job in sorted(ctx["jobs"]):
        info = ctx["jobs"][job]
        inst = ctx["subs"].get(job)
        rows.append({
            "job_id": job,
            "model": info["model"],
            "benchmark": info["benchmark"],
            "shard": info["shard"],
            "checkpoint": info["checkpoint"],
            "host": info["host"],
            "submitted_at": iso_z(inst) if inst is not None else None,
            "disposition": ctx["disposition"][job],
        })
    dump_jsonl(os.path.join(out_dir, "job_dispositions.jsonl"), rows)

    # ---- item_eligibility.jsonl
    rows = []
    for item in sorted(ctx["items"]):
        rows.append({"item_id": item,
                     "benchmark": ctx["items"][item]["suite"],
                     "eligible": ctx["reasons"][item] is None,
                     "reason": ctx["reasons"][item]})
    dump_jsonl(os.path.join(out_dir, "item_eligibility.jsonl"), rows)

    # ---- item_scores.jsonl
    rows = []
    for model in candidates:
        got = per_model.get(model, {})
        for item in sorted(ctx["eligible"]):
            rec = got.get(item)
            suite = ctx["items"][item]["suite"]
            if rec is None:
                continue
            value = rec["value"]
            if suite == "safety" and value is not None:
                value = jnum(value)
            conf = rec["confidence"]
            rows.append({"model": model, "item_id": item, "benchmark": suite,
                         "value": value,
                         "confidence": jnum(conf) if conf is not None else None,
                         "correct": rec["correct"]})
    dump_jsonl(os.path.join(out_dir, "item_scores.jsonl"), rows)

    # ---- metrics
    metrics = {m: suite_metric_values(ctx, per_model.get(m, {}), m)
               for m in models}
    bm = {}
    for m in models:
        entry = {}
        for suite in SUITES:
            if suite == "pref":
                continue
            d = metrics[m][suite]
            e = {"n": d["n"]}
            for key in ("accuracy", "pass@1", "pass@5", "macro_f1", "auroc",
                        "macro_accuracy"):
                if key in d:
                    e[key] = jnum(d[key]) if d[key] is not None else None
            if suite == "multiling":
                e["languages"] = d["languages"]
            entry[suite] = e
        bm[m] = entry
    dump_json(os.path.join(out_dir, "benchmark_metrics.json"), bm)

    # ---- calibration.json
    cal = {}
    ece_exact = {}
    for m in candidates:
        got = per_model.get(m, {})
        entries = []
        for item in ctx["eligible_by_suite"]["mcq"]:
            rec = got.get(item)
            if rec is None or rec["confidence"] is None or rec["correct"] is None:
                continue
            entries.append((rec["confidence"], rec["correct"], item))
        ece, bins = ece_bins(entries)
        ece_exact[m] = ece
        cal[m] = {
            "ece": jnum(ece) if ece is not None else None,
            "bins": [{"count": b["count"],
                      "mean_confidence": jnum(b["mean_confidence"])
                      if b["mean_confidence"] is not None else None,
                      "accuracy": jnum(b["accuracy"])
                      if b["accuracy"] is not None else None} for b in bins],
        }
    dump_json(os.path.join(out_dir, "calibration.json"), cal)

    # ---- pairwise.json
    pw = {}
    for m in candidates:
        d = metrics[m]["pref"]
        pw[m] = {"wins": d["wins"], "ties": d["ties"], "losses": d["losses"],
                 "win_rate": jnum(d["win_rate"]) if d["win_rate"] is not None
                 else None}
    dump_json(os.path.join(out_dir, "pairwise.json"), pw)

    # ---- significance.json
    sig = {}
    for m in candidates:
        got = per_model.get(m, {})
        entry = {}
        for suite in GATED:
            b = c = 0
            for item in ctx["eligible_by_suite"][suite]:
                cand = got.get(item)
                base = baseline.get(item)
                if cand is None or base is None:
                    continue
                cc = cand["correct"]
                bc = base["correct"]
                if cc is None or bc is None:
                    continue
                if cc == 1 and bc == 0:
                    b += 1
                elif cc == 0 and bc == 1:
                    c += 1
            p = mcnemar(b, c)
            if p < Fraction(5, 100) and b > c:
                decision = "improved"
            elif p < Fraction(5, 100) and c > b:
                decision = "regressed"
            else:
                decision = "no_change"
            entry[suite] = {"b": b, "c": c, "p_value": jnum(p),
                            "decision": decision}
        sig[m] = entry
    dump_json(os.path.join(out_dir, "significance.json"), sig)

    # ---- leaderboard.csv
    mcq_items = ctx["eligible_by_suite"]["mcq"]
    opts = [ctx["params"].get(i, {}).get("n_options") for i in mcq_items]
    opts = [o for o in opts if o]
    mcq_chance = mean_fraction([Fraction(1, o) for o in opts]) if opts \
        else Fraction(0)
    chance = dict(CHANCE)
    chance["mcq"] = mcq_chance
    weights = ctx["weights"]
    norm_scores = {}
    aggregates = {}
    for m in models:
        row = {}
        for suite in SUITES:
            metric = primary_metric(suite, metrics[m], m == BASELINE)
            row[suite] = normalised(metric, chance[suite]) \
                if metric is not None else None
        norm_scores[m] = row
        num = Fraction(0)
        den = Fraction(0)
        for suite in SUITES:
            w = weights.get(suite)
            if w is None or row[suite] is None:
                continue
            num += w * row[suite]
            den += w
        aggregates[m] = num / den if den else None
    order = sorted(models, key=lambda m: (
        -(aggregates[m] if aggregates[m] is not None else Fraction(-10 ** 9)),
        -(metrics[m]["code"]["pass@1"] if metrics[m]["code"]["pass@1"] is not None
          else Fraction(-10 ** 9)), m))
    lines = ["rank,model,aggregate,arith,code,intent,safety,mcq,pref,longctx,"
             "multiling"]
    for i, m in enumerate(order, 1):
        cells = [str(i), m, fmt6(aggregates[m])]
        for suite in ("arith", "code", "intent", "safety", "mcq", "pref",
                      "longctx", "multiling"):
            v = norm_scores[m][suite]
            cells.append(fmt6(v) if v is not None else "")
        lines.append(",".join(cells))
    write_text(os.path.join(out_dir, "leaderboard.csv"), "\n".join(lines) + "\n")

    # ---- release_gates.json
    gates = {}
    base_agg = aggregates[BASELINE]
    for m in candidates:
        agg_ok = aggregates[m] is not None and base_agg is not None and \
            aggregates[m] >= base_agg
        no_reg = all(sig[m][s]["decision"] != "regressed" for s in GATED)
        ece = ece_exact[m]
        ece_ok = ece is not None and ece <= ECE_CAP
        auc = metrics[m]["safety"]["auroc"]
        safe_ok = auc is not None and auc >= SAFETY_FLOOR
        gates[m] = {"aggregate_vs_baseline": bool(agg_ok),
                    "no_regression": bool(no_reg),
                    "ece_within_cap": bool(ece_ok),
                    "safety_floor": bool(safe_ok),
                    "release": bool(agg_ok and no_reg and ece_ok and safe_ok)}
    dump_json(os.path.join(out_dir, "release_gates.json"), gates)

    # ---- slice_metrics.json
    min_support = ctx["slices"]["min_support"]
    sl = {}
    for m in candidates:
        got = per_model.get(m, {})
        entry = {}
        for suite in GATED:
            sub = {}
            for name, cond in sorted(ctx["slices"]["slices"].items()):
                members = [i for i in ctx["eligible_by_suite"][suite]
                           if slice_match(ctx, i, cond)]
                if len(members) < min_support:
                    sub[name] = None
                    continue
                recs = [got[i] for i in members if i in got]
                a = accuracy(recs)
                sub[name] = jnum(a) if a is not None else None
            entry[suite] = sub
        sl[m] = entry
    dump_json(os.path.join(out_dir, "slice_metrics.json"), sl)

    # ---- source_audit.json
    sa = {}
    for name in RESULT_SOURCES:
        rows_n = audit[name]["result_rows"]
        used = audit[name]["used"]
        sa[name] = {"result_rows": rows_n, "used": used,
                    "discarded": rows_n - used}
    dump_json(os.path.join(out_dir, "source_audit.json"), sa)

    # ---- control_reconciliation.json
    cr = {}
    tot_jobs = tot_items = tot_exp = 0
    for m in candidates:
        auth = [j for j, info in ctx["jobs"].items()
                if info["model"] == m and ctx["disposition"][j] == "authoritative"]
        scored = sum(1 for (mm, it) in values if mm == m)
        exp = 0
        for j in auth:
            e = ctx["control"].get(j, {}).get("expected_rows")
            if e:
                exp += e
        cr[m] = {"authoritative_jobs": len(auth), "scored_items": scored,
                 "expected_results": exp}
        tot_jobs += len(auth)
        tot_items += scored
        tot_exp += exp
    cr["_total"] = {"authoritative_jobs": tot_jobs, "scored_items": tot_items,
                    "expected_results": tot_exp}
    dump_json(os.path.join(out_dir, "control_reconciliation.json"), cr)

    if DBG:
        report_diagnostics(ctx, live, values, baseline, metrics)
    return ctx


def report_diagnostics(ctx, live, values, baseline, metrics):
    elig = ctx["eligible"]
    for m in ctx["candidates"]:
        got = {i for (mm, i) in values if mm == m}
        dbg("model", m, "scored", len(got), "missing", len(elig - got))
        miss = Counter(ctx["items"][i]["suite"] for i in (elig - got))
        if miss:
            dbg("   missing by suite", dict(miss))
    dbg("baseline items", len(baseline), "missing",
        len(elig - set(baseline)))


def main(argv):
    if len(argv) != 3:
        print("usage: certify.py <data_dir> <out_dir>", file=sys.stderr)
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(data_dir):
        print("no such data directory: %s" % data_dir, file=sys.stderr)
        return 2
    run(data_dir, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
