#!/usr/bin/env python3
"""Heron evaluation certification close.

Reads a corpus directory and writes the certified close outputs.

Usage:  python3 certify.py <data_dir> <out_dir>
"""

import argparse
import collections
import csv
import datetime as dt
import html as htmlmod
import io
import json
import math
import os
import re
import sqlite3
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction

import openpyxl
import pypdf
import pyarrow.parquet as pq
import yaml

# --------------------------------------------------------------------------
# constants describing this close's conventions (policy-fixed, not data)
# --------------------------------------------------------------------------

WINDOW_START = dt.datetime(2025, 7, 1, tzinfo=dt.timezone.utc)
WINDOW_END = dt.datetime(2025, 10, 1, tzinfo=dt.timezone.utc)
CUTOFF = dt.datetime(2025, 10, 3, 18, 0, 0, tzinfo=dt.timezone.utc)
BASELINE = "osprey-13b-prod"
SUITE_KEYS = ["arith", "code", "intent", "safety", "mcq", "pref", "longctx", "multiling"]
GATED_SUITES = ["arith", "mcq", "longctx", "multiling"]
ITEM_PREFIXES = ["ARI", "COD", "INT", "SAF", "MCQ", "PRF", "LCX", "MLG"]
PREFIX_TO_SUITE = {"ARI": "arith", "COD": "code", "INT": "intent", "SAF": "safety",
                   "MCQ": "mcq", "PRF": "pref", "LCX": "longctx", "MLG": "multiling"}
SUITE_TO_PREFIX = {v: k for k, v in PREFIX_TO_SUITE.items()}
LEGACY_SUITES = {"arithmetic": "arith", "codegen": "code", "intents": "intent",
                 "safety_flags": "safety", "multiple_choice": "mcq", "pairwise": "pref",
                 "long_context": "longctx", "multilingual": "multiling"}
CONTAMINATION_THRESHOLDS = {"arith": Fraction(7000, 10000), "code": Fraction(6000, 10000),
                           "intent": Fraction(5500, 10000), "safety": Fraction(7000, 10000),
                           "mcq": Fraction(6500, 10000), "pref": Fraction(6000, 10000),
                           "longctx": Fraction(6000, 10000), "multiling": Fraction(6000, 10000)}
ZONE_OFFSETS = {"UTC": dt.timedelta(0), "Europe/Berlin": dt.timedelta(hours=2),
                "America/Chicago": dt.timedelta(hours=-5), "Asia/Kolkata": dt.timedelta(hours=5, minutes=30),
                "America/Sao_Paulo": dt.timedelta(hours=-3)}
ZONE_ALIASES = {"CEST": "Europe/Berlin", "CDT": "America/Chicago", "IST": "Asia/Kolkata",
                "BRT": "America/Sao_Paulo", "UTC": "UTC", "": "UTC"}
LOCALES = {"en_us": "en_US", "de_de": "de_DE", "fr_fr": "fr_FR", "en_in": "en_IN"}
SOURCE_ALIASES = {
    "results_fleet_a": "results_fleet_a.log", "results_fleet_b": "results_fleet_b.log",
    "results_fleet_c": "results_fleet_c.log", "scores_shard1": "scores_shard1.parquet",
    "scores_shard2": "scores_shard2.parquet", "eval_store": "eval_store.db",
    "legacy_results": "legacy_results.txt", "intent_predictions": "intent_predictions.csv",
    "code_samples": "code_samples.jsonl", "judge_verdicts": "judge_verdicts.jsonl",
    "rerun_results": "rerun_results.jsonl", "scores_staging": "scores_staging.parquet",
    "eval_store_mirror": "eval_store_mirror.db", "judge_verdicts_rescored": "judge_verdicts_rescored.jsonl",
}
V2_RENAMES = {"hours": "opening_hours", "reset_password": "account_recovery", "shipping_cost": "delivery_fee"}
CONFUSABLES = {"А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "Ј": "J", "К": "K", "М": "M",
               "О": "O", "Р": "P", "Т": "T", "Х": "X", "а": "a", "с": "c", "е": "e", "о": "o",
               "р": "p", "х": "x"}
STAGE_PARQUET_ROWGROUP_SECONDS = {"scores_shard1.parquet": {7, 11},
                                  "scores_shard2.parquet": {5, 7},
                                  "scores_staging.parquet": {2, 10}}
STAGE_FLEETS = {"s"}
RETIRE_STATUSES = {"retired": "retired", "ret": "retired", "r": "retired"}
ACTIVE_STATUSES = {"active": "active", "act": "active", "a": "active", "added": "active"}
IN_SCOPE = {"in": True, "in_scope": True, "yes": True, "held_out": False, "ho": False, "private": False}
DOMAIN_CODES = {"EVD": "everyday", "FIN": "finance", "HLT": "health", "LAW": "law",
                "SCI": "science", "TEC": "tech"}
DIFFICULTY_CODES = {"1": "easy", "2": "medium", "3": "hard",
                    "simple": "easy", "moderate": "medium", "difficult": "hard"}


# --------------------------------------------------------------------------
# canonicalisation helpers
# --------------------------------------------------------------------------

def clean(value):
    """Strip spaces / no-break spaces and map Cyrillic look-alikes back to Latin."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    text = value.replace("\xa0", " ").strip()
    text = "".join(CONFUSABLES.get(ch, ch) for ch in text)
    text = unicodedata.normalize("NFKC", text)
    return text.strip()


def text(value):
    """Clean value as a string, tolerating None and numbers."""
    if value is None:
        return ""
    if isinstance(value, str):
        return clean(value)
    return str(value)


def low(value):
    return text(value).lower()


def pad_digits(text, width):
    digits = re.sub(r"\D", "", text)
    if not digits:
        return text
    return digits.zfill(width)


def canon_job(value):
    if value is None:
        return None
    text = clean(str(value)).upper()
    if len(text) < 2 or not text[1:].isdigit():
        return None
    return "J" + text[1:].zfill(7)


def canon_item(value):
    if value is None:
        return None
    text = clean(str(value)).upper()
    match = re.match(r"^([A-Z]{3})-?(\d+)$", text)
    if not match or match.group(1) not in PREFIX_TO_SUITE:
        return None
    return "%s-%05d" % (match.group(1), int(match.group(2)))


def canon_host(value):
    if value is None:
        return None
    text = clean(str(value)).lower()
    match = re.match(r"^node-?(\d+)$", text)
    if not match:
        return None
    return "node-" + match.group(1).zfill(4)


def canon_ckpt(value):
    if value is None:
        return None
    text = clean(str(value)).lower()
    text = re.sub(r"^ema/", "", text)
    match = re.match(r"^ck-?([0-9a-f]+)$", text)
    if not match:
        return None
    return "ck-" + match.group(1).zfill(10)


def canon_ticket(value):
    if value is None:
        return None
    text = clean(str(value)).upper()
    match = re.match(r"^(CHG|DSP)-?(\d+)$", text)
    if not match:
        return None
    return "%s-%05d" % (match.group(1), int(match.group(2)))


def canon_legacy_code(value):
    if value is None:
        return None
    text = clean(str(value)).upper()
    match = re.match(r"^LC\s?-?(\d+)$", text)
    if not match:
        return None
    return "LC" + match.group(1).zfill(6)


def canon_rowid(value):
    if value is None:
        return None
    text = clean(str(value)).lower()
    match = re.match(r"^r-?(\d+)$", text)
    if not match:
        return None
    return "r" + match.group(1).zfill(7)


def canon_suite(value):
    text = clean(value).lower() if isinstance(value, str) else value
    if not isinstance(text, str):
        return None
    text = text.strip()
    if text in LEGACY_SUITES:
        return LEGACY_SUITES[text]
    if text in SUITE_KEYS:
        return text
    return text


def canon_source(value):
    text = clean(value).lower() if isinstance(value, str) else value
    if not isinstance(text, str):
        return text
    text = text.strip()
    if text.endswith((".log", ".jsonl", ".parquet", ".db", ".csv", ".txt")):
        return text
    return SOURCE_ALIASES.get(text, text)


def canon_revision(value):
    text = clean(value) if isinstance(value, str) else value
    if isinstance(text, str):
        low = text.strip().lower()
        if low.startswith("r"):
            low = low[1:]
        if low.isdigit():
            return int(low)
        try:
            return int(float(low))
        except (TypeError, ValueError):
            return -1
    if isinstance(text, (int, float)):
        return int(text)
    return -1


def nfc(text):
    return unicodedata.normalize("NFC", text) if isinstance(text, str) else text


# --------------------------------------------------------------------------
# numeric parsing (locale aware)
# --------------------------------------------------------------------------

def parse_number(value, locale="en_US"):
    """Parse a locale-formatted number to Fraction; returns None when unparseable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            return Fraction(Decimal(repr(value)))
        return Fraction(value)
    text = clean(value)
    if text == "":
        return None
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()
    if text.startswith("-"):
        negative = True
        text = text[1:].strip()
    text = text.replace(" ", "").replace("\u202f", "")
    if not text or text in {"-", "N/A", "NA", "?"}:
        return None
    locale = (locale or "en_US").lower().replace("-", "_")
    if locale.startswith("de"):
        text = text.replace(".", "").replace(",", ".")
    elif locale.startswith("fr"):
        text = text.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    elif locale.startswith("en_in"):
        text = text.replace(",", "")
    else:
        text = text.replace(",", "")
    try:
        result = Fraction(Decimal(text))
    except Exception:
        return None
    return -result if negative else result


def round_half_even(value, places):
    """Round a Fraction/Decimal/float to `places` decimals, half to even."""
    if value is None:
        return None
    if not isinstance(value, Fraction):
        value = Fraction(Decimal(repr(value))) if isinstance(value, float) else Fraction(value)
    quant = Decimal(1).scaleb(-places)
    dec = Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal(dec).quantize(quant, rounding=ROUND_HALF_EVEN)


def frac_str(value, places):
    """Exact value rendered with exactly `places` decimals (half-even rounding)."""
    dec = round_half_even(value, places)
    return format(dec, "f")


def serial_date(value):
    """Spreadsheet serial date (days since 1899-12-30) to UTC datetime."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=dt.timezone.utc)
    num = parse_number(value)
    if num is None:
        return None
    epoch = dt.datetime(1899, 12, 30, tzinfo=dt.timezone.utc)
    return epoch + dt.timedelta(days=float(num))


# --------------------------------------------------------------------------
# time parsing
# --------------------------------------------------------------------------

def parse_iso(value):
    if value is None:
        return None
    text = clean(value).replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc)


def parse_epoch(value, unit="ms"):
    num = parse_number(value)
    if num is None:
        return None
    seconds = float(num) / (1000.0 if unit == "ms" else 1.0)
    try:
        return dt.datetime.fromtimestamp(seconds, dt.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def parse_basic_datetime(text):
    """20250701001100 style timestamps."""
    value = clean(text)
    digits = re.sub(r"\D", "", value)
    if len(digits) < 14:
        return None
    try:
        return dt.datetime(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]),
                           int(digits[8:10]), int(digits[10:12]), int(digits[12:14]),
                           tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def parse_rfc2822(text):
    """RFC2822 date with possible trailing zone name; the numeric offset decides."""
    value = clean(text)
    # drop trailing alphabetic zone names after the numeric offset
    match = re.match(r"^(.*?\d{4})\s*[A-Za-z/ ]*$", value)
    if match:
        value = match.group(1)
    value = re.sub(r"\s+\([A-Za-z]+\)\s*$", "", value)
    import email.utils
    try:
        moment = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc)


def iso_week(moment):
    iso = moment.isocalendar()
    return (iso[0], iso[1])


def fmt_instant(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# generic table parsers
# --------------------------------------------------------------------------

def split_md_row(line):
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    cells = []
    for raw in body.split("|"):
        cell = clean(raw.replace("\\|", "\x00")).replace("\x00", "|")
        cells.append(cell)
    return cells


def md_table_blocks(path):
    """Yield (header, rows) for every markdown table block in a file."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    index = None
    for i, line in enumerate(lines):
        if line.startswith("#") and "job routing" in line.lower():
            index = i
    if index is None:
        for i, line in enumerate(lines):
            if line.startswith("## Appendix") and "routing" in line.lower():
                index = i
                break
    if index is None:
        return
    header = None
    rows = []
    for line in lines[index + 1:]:
        if not line.strip().startswith("|"):
            if rows or header:
                if header:
                    yield header, rows
            if line.strip() == "":
                if header:
                    yield header, rows
                header, rows = None, []
                continue
            continue
        cells = split_md_row(line)
        if cells and cells[0].strip() == "job" and len(cells) > 2:
            if header:
                yield header, rows
            header, rows = cells, []
            continue
        if not cells or set("".join(cells)) <= set("-"):
            continue
        if header:
            rows.append(cells)
    if header:
        yield header, rows


def html_tables(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    for block in re.findall(r"<table[^>]*>(.*?)</table>", text, re.S):
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S)
        table = []
        for row in rows:
            cells = [htmlmod.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
                     for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
            table.append(cells)
        if table:
            yield table


def pdf_tables(path):
    """Yield (header, rows) blocks from a pdf's pipe tables."""
    reader = pypdf.PdfReader(path)
    lines = []
    for page in reader.pages:
        lines.extend(page.extract_text().split("\n"))
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        while i + 1 < len(lines):
            stripped = line.rstrip()
            if stripped.endswith("\\"):
                line = stripped[:-1].rstrip() + " | " + lines[i + 1].lstrip()
                i += 1
            elif stripped.endswith("|"):
                line = stripped + " " + lines[i + 1].lstrip()
                i += 1
            else:
                break
        out.append(line)
        i += 1
    header = None
    rows = []
    for line in out:
        if line.startswith("TABLE "):
            if header:
                yield header, rows
            header = [clean(cell) for cell in line[6:].split(" | ")]
            rows = []
            continue
        if line.startswith("== "):
            continue
        if header and " | " in line:
            cells = [clean(cell) for cell in line.split(" | ")]
            if len(cells) == len(header):
                rows.append(cells)
    if header:
        yield header, rows


def docx_tables(path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    for table in root.iter(ns + "tbl"):
        rows = []
        for row in table.findall(ns + "tr"):
            cells = []
            for cell in row.findall(ns + "tc"):
                text = "".join(node.text or "" for node in cell.iter(ns + "t"))
                cells.append(clean(text.replace("\r", " ").replace("\n", " ")))
            rows.append(cells)
        if rows:
            yield rows


def xlsx_rows(path, sheet=None):
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    names = [sheet] if sheet else workbook.sheetnames
    for name in names:
        if name not in workbook.sheetnames:
            continue
        sheetobj = workbook[name]
        rows = []
        for row in sheetobj.iter_rows(values_only=True):
            rows.append([clean(cell) if isinstance(cell, str) else cell for cell in row])
        yield name, rows
    workbook.close()


def read_text_lines(path):
    """Lines of a text file, decoded per line: UTF-8 first, Latin-1 as fallback."""
    with open(path, "rb") as handle:
        data = handle.read()
    lines = []
    for raw in data.split(b"\n"):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        try:
            line = raw.decode("utf-8")
        except UnicodeDecodeError:
            line = raw.decode("latin-1")
        lines.append(line.lstrip("\ufeff"))
    return lines


def read_delimited(path, delimiter, key_field):
    """Read a delimited registry whose header row can repeat, renamed or reordered."""
    header = None
    records = []
    for cells in csv.reader(read_text_lines(path), delimiter=delimiter):
        cells = [clean(cell) if isinstance(cell, str) else cell for cell in cells]
        if not cells or all(str(c).strip() == "" for c in cells):
            continue
        if header is None:
            header = [str(c).strip() if c is not None else "" for c in cells]
            continue
        if str(cells[0]).strip().lower() == str(key_field).lower() and len(cells) == len(header):
            if set(str(c).strip() for c in cells) == set(header):
                header = [str(c).strip() for c in cells]
                continue
        if len(cells) == len(header):
            records.append(dict(zip(header, cells)))
    return records


def read_csv_with_headers(path):
    return read_delimited(path, ",", "item_id")


def read_tsv_with_headers(path):
    return read_delimited(path, "\t", "item_id")


# --------------------------------------------------------------------------
# corpus loading
# --------------------------------------------------------------------------

class Corpus:
    def __init__(self, data_dir):
        self.dir = data_dir
        self.errors = []
        self.submission = {}
        self.submit_lines = collections.defaultdict(list)
        self._load_all()

    def path(self, name):
        return os.path.join(self.dir, name)

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _latest(records, key, revision_field="revision"):
        best = {}
        for record in records:
            k = key(record)
            if k is None:
                continue
            rev = canon_revision(record.get(revision_field))
            if k not in best or rev > best[k][0]:
                best[k] = (rev, record)
        return {k: v[1] for k, v in best.items()}

    def _load_all(self):
        self.load_run_registry()
        self.load_lineage()
        self.load_inventory_and_clocks()
        self.load_maintenance()
        self.load_minutes()
        self.load_errata()
        self.load_harness()
        self.load_job_configs()
        self.load_tags_and_mailbox()
        self.load_item_registries()
        self.load_gold()
        self.load_baseline()
        self.load_control()

    # -- run registry ----------------------------------------------------
    def load_run_registry(self):
        self.jobs = {}
        for element in ET.parse(self.path("run_registry.xml")).getroot():
            attrs = dict(element.attrib)
            jid = canon_job(attrs.get("id"))
            if jid is None:
                continue
            entry = {
                "job": jid,
                "model": low(attrs.get("model", attrs.get("alias"))),
                "checkpoint": canon_ckpt(attrs.get("checkpoint", attrs.get("ckpt"))),
                "suite": canon_suite(attrs.get("suite")),
                "shard": int(attrs["shard"]) - (1 if attrs.get("base") == "1" else 0),
                "host": canon_host(attrs.get("host")),
                "seq": canon_revision(attrs.get("seq")),
            }
            if jid not in self.jobs or entry["seq"] > self.jobs[jid]["seq"]:
                self.jobs[jid] = entry
        self.legacy_no = {}
        for element in ET.parse(self.path("run_registry_export.xml")).getroot():
            attrs = dict(element.attrib)
            jid = canon_job(attrs.get("id"))
            legacy = attrs.get("legacy_no")
            if jid is not None and legacy:
                code = clean(legacy).upper()
                match = re.match(r"^L-?(\d+)$", code)
                if match:
                    self.legacy_no["L-" + match.group(1).zfill(5)] = jid

    # -- lineage ---------------------------------------------------------
    def load_lineage(self):
        data = json.load(open(self.path("checkpoint_lineage.json"), encoding="utf-8"))
        best = {}
        for entry in data.get("checkpoints", []):
            cid = canon_ckpt(entry.get("id"))
            if cid is None:
                continue
            moment = entry.get("registered_at")
            if isinstance(moment, str):
                stamp = parse_iso(moment) or parse_epoch(moment, "s")
            elif isinstance(moment, (int, float)):
                stamp = parse_epoch(moment, "s")
            else:
                stamp = None
            record = {
                "id": cid,
                "run": clean(entry.get("run")),
                "step": self._parse_step(entry.get("step")),
                "parent": canon_ckpt(entry.get("parent")) if entry.get("parent") else None,
                "family": self._family(entry.get("family")),
                "tokenizer": low(entry.get("tokenizer")) or None,
                "context_window": self._context_window(entry.get("context_window")),
                "registered_at": stamp,
            }
            if cid not in best or (stamp is not None and
                                   (best[cid]["registered_at"] is None or
                                    stamp > best[cid]["registered_at"])):
                best[cid] = record
        self.lineage = best
        # EMA checkpoints live only in the snapshot
        snap = json.load(open(self.path("checkpoint_lineage_snapshot.json"), encoding="utf-8"))
        self.ema = {}
        for entry in snap.get("checkpoints", []):
            cid = canon_ckpt(entry.get("id", entry.get("ckpt")))
            ema_of = canon_ckpt(entry.get("ema_of"))
            if cid is None or not entry.get("ema") or ema_of is None:
                continue
            parent = self.lineage.get(ema_of)
            self.ema[cid] = {
                "id": cid,
                "run": parent["run"] if parent else None,
                "step": self._parse_step(entry.get("step")),
                "parent": ema_of,
                "family": parent["family"] if parent else None,
                "tokenizer": parent["tokenizer"] if parent else None,
                "context_window": parent["context_window"] if parent else None,
                "registered_at": None,
            }

    @staticmethod
    def _parse_step(value):
        if isinstance(value, str):
            text = clean(value).lower()
            if text.endswith("k"):
                try:
                    return int(float(text[:-1]) * 1000)
                except ValueError:
                    return None
            try:
                return int(text)
            except ValueError:
                return None
        return value

    @staticmethod
    def _family(value):
        if value is None:
            return None
        text = clean(value).lower().replace(" ", "-")
        mapping = {"7b": "7b", "13b": "13b", "34b": "34b", "osp-13": "osp13",
                   "osp13": "osp13", "heron-7b": "7b", "heron-13b": "13b", "heron-34b": "34b",
                   "osprey": "osp13", "heron-small": "7b", "heron-medium": "13b",
                   "heron-large": "34b"}
        return mapping.get(text, text)

    @staticmethod
    def _context_window(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        text = clean(value).lower()
        match = re.match(r"^(\d+)\s*k$", text)
        if match:
            return int(match.group(1)) * 1024
        if text.isdigit():
            return int(text)
        return None

    def checkpoint_info(self, cid):
        return self.lineage.get(cid) or self.ema.get(cid)

    def model_family(self, alias):
        """Model family of an alias, taken from the alias's certified checkpoint."""
        info = self.checkpoint_info(self.certified.get(alias, {}).get("checkpoint"))
        return info["family"] if info else None

    # -- tags and mailbox -------------------------------------------------
    def load_tags_and_mailbox(self):
        data = yaml.safe_load(open(self.path("model_tags.yaml"), encoding="utf-8"))
        self.tag_events = []
        for event in data.get("events", []):
            alias = low(event.get("tag"))
            if alias.startswith("nightly-"):
                continue
            self.tag_events.append({
                "alias": alias,
                "checkpoint": canon_ckpt(event.get("checkpoint")),
                "action": low(event.get("action")),
                "ticket": canon_ticket(event.get("ticket")),
                "at": parse_iso(event.get("at")),
            })
        approvals, rejections, seals, reseals = self.load_mailbox()
        self.approvals = approvals
        self.rejections = rejections
        self.seals = seals
        self.reseals = reseals
        self.certified = {}
        self.voided_promotions = collections.Counter()
        for alias in sorted({event["alias"] for event in self.tag_events} | {BASELINE}):
            effective = []
            voided = 0
            for event in self.tag_events:
                if event["alias"] != alias:
                    continue
                ticket = event["ticket"]
                moment = self.approvals.get(ticket)
                if ticket in self.rejections or moment is None or moment > CUTOFF:
                    voided += 1
                    continue
                effective.append((moment, event))
            self.voided_promotions[alias] = voided
            if effective:
                effective.sort(key=lambda pair: (pair[0], pair[1]["ticket"]))
                moment, event = effective[-1]
                self.certified[alias] = {"checkpoint": event["checkpoint"],
                                         "effective_from": moment,
                                         "approval_ref": event["ticket"]}

    def load_mailbox(self):
        with open(self.path("evalops_notifications.mbox"), "rb") as handle:
            raw = handle.read()
        text = raw.decode("utf-8", errors="replace")
        approvals, rejections, seals, reseals = {}, {}, {}, {}
        parts = re.split(r"(?m)^From evalops@heron.example ", text)
        for part in parts[1:]:
            subject = re.search(r"^Subject:\s*(.*)$", part, re.M)
            if not subject:
                continue
            head = subject.group(1).strip()
            forwarded = head.lower().startswith("fwd:")
            words = head.split()
            if len(words) < 2:
                continue
            date_match = re.search(r"^Date:\s*(.*)$", part, re.M)
            if not date_match:
                continue
            if forwarded:
                inner = re.search(r"^Date:\s*(.*)$", part[date_match.end():], re.M)
                moment = parse_rfc2822(inner.group(1)) if inner else None
            else:
                moment = parse_rfc2822(date_match.group(1))
            if moment is None:
                continue
            upper = head.upper()
            if "APPROVED" in upper or "REJECTED" in upper:
                for word in words:
                    ticket = canon_ticket(word)
                    if ticket:
                        break
                else:
                    ticket = None
                if ticket is None:
                    continue
                if "REJECTED" in upper:
                    rejections[ticket] = moment
                else:
                    approvals[ticket] = moment
                continue
            if "RESEAL" in upper:
                for word in words:
                    jid = canon_job(word)
                    if jid:
                        break
                if jid and (jid not in reseals or moment > reseals[jid]):
                    reseals[jid] = moment
                continue
            if "SEALED" in upper:
                for word in words:
                    jid = canon_job(word)
                    if jid:
                        break
                if jid and (jid not in seals or moment > seals[jid]):
                    seals[jid] = moment
        for jid, moment in reseals.items():
            seals[jid] = max(seals.get(jid, moment), moment)
        return approvals, rejections, seals, reseals

    def seal_time(self, jid):
        return self.seals.get(jid)

    def legacy_job(self, raw):
        """Map a retired scheduler number (L-nnnnn) to its job id."""
        if not raw:
            return None
        text = clean(raw).upper().strip()
        match = re.match(r"^L-?(\d+)$", text)
        if not match:
            return None
        return self.legacy_no.get("L-" + match.group(1).zfill(5))

    # -- host inventory and clocks ---------------------------------------
    def load_inventory_and_clocks(self):
        self.load_clocks()
        self.inventory = {}
        section = 0
        with open(self.path("host_inventory.ini"), encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text or text.startswith("#"):
                    continue
                if text.startswith("["):
                    section += 1
                    continue
                if "=" not in text or "@" not in text.split("=")[0]:
                    continue
                key, value = text.split("=", 1)
                key = clean(key)
                hostweek, _, attrs = value.partition("=") if "=" not in key else (None, None, None)
                host, _, week = key.partition("@")
                host = canon_host(host)
                if host is None:
                    continue
                week = clean(week)
                year, weekno = self._parse_week(week)
                if year is None:
                    continue
                fields = {}
                for item in value.split(";"):
                    item = item.split("#")[0].strip()
                    if "=" in item:
                        k, v = item.split("=", 1)
                        fields[clean(k).lower()] = clean(v)
                fleet = low(fields.get("fleet")) or ""
                if fleet.startswith("fleet-"):
                    fleet = fleet[len("fleet-"):]
                if fleet.startswith("prod-"):
                    fleet = fleet[len("prod-"):]
                if fleet in ("stage", "staging"):
                    fleet = "s"
                zone = fields.get("tz", "")
                if zone.upper() in ZONE_ALIASES:
                    zone = ZONE_ALIASES[zone.upper()]
                locale = fields.get("locale", "en_US").replace("-", "_").lower()
                scale = fields.get("scale", "unit").lower()
                if scale == "1":
                    scale = "unit"
                elif scale == "100":
                    scale = "pct"
                entry = {"fleet": fleet, "tz": zone, "locale": locale, "scale": scale,
                         "section": section}
                slot = (host, year, weekno)
                if slot not in self.inventory or entry["section"] >= self.inventory[slot]["section"]:
                    self.inventory[slot] = entry

    @staticmethod
    def _parse_week(text):
        """A week key: 2025-W31, W31, 31, a spreadsheet serial or a Monday date."""
        text = clean(text)
        match = re.match(r"^(\d{4})-W(\d{1,2})$", text)
        if match:
            return int(match.group(1)), int(match.group(2))
        match = re.match(r"^W(\d{1,2})$", text)
        if match:
            return 2025, int(match.group(1))
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
        if match:
            try:
                moment = dt.datetime(int(match.group(1)), int(match.group(2)),
                                     int(match.group(3)), tzinfo=dt.timezone.utc)
            except ValueError:
                return None, None
            iso = moment.isocalendar()
            return iso[0], iso[1]
        if text.isdigit():
            value = int(text)
            if 1 <= value <= 53:
                return 2025, value
            moment = serial_date(value)
            if moment:
                iso = moment.isocalendar()
                return iso[0], iso[1]
        return None, None

    def inventory_entry(self, host, moment):
        year, weekno = iso_week(moment)
        return self.inventory.get((host, year, weekno))

    def load_clocks(self):
        self.clocks = {}
        best = {}
        with open(self.path("clock_offsets.txt"), encoding="utf-8") as handle:
            columns = ["seq", "host", "week", "offset", "unit"]
            for line in handle:
                text = line.rstrip("\n")
                if not text.strip():
                    continue
                if text.lstrip().startswith("#"):
                    match = re.match(r"#COLUMNS\s+(.*)$", text.strip())
                    if match:
                        columns = [clean(c).lower() for c in match.group(1).split()]
                    continue
                cells = text.split()
                if len(cells) != len(columns):
                    continue
                record = dict(zip(columns, cells))
                host = canon_host(record.get("host"))
                year, week = self._parse_week(record.get("week"))
                if host is None or year is None:
                    continue
                seq = canon_revision(record.get("seq"))
                raw = clean(record.get("offset"))
                unit = low(record.get("unit")) or "ms"
                value = parse_number(raw)
                if value is None or set(raw) <= set("-"):
                    value = Fraction(0)
                if unit.startswith("s"):
                    value = value * 1000
                key = (host, year, week)
                if key not in best or seq > best[key][0]:
                    best[key] = (seq, value)
        self.clocks = {k: v[1] for k, v in best.items()}

    def load_maintenance(self):
        self.maintenance = collections.defaultdict(list)
        with open(self.path("maintenance_windows.ics"), encoding="utf-8") as handle:
            text = handle.read()
        text = text.replace("\r\n", "\n")
        unfolded = []
        for line in text.split("\n"):
            if line.startswith(" ") and unfolded:
                unfolded[-1] += line[1:]
            else:
                unfolded.append(line)
        events = collections.defaultdict(list)
        current = None
        for line in unfolded:
            if line == "BEGIN:VEVENT":
                current = {}
            elif line == "END:VEVENT":
                if current is not None:
                    events[current.get("uid", "").lower()].append(current)
                current = None
            elif ":" in line and current is not None:
                name, _, value = line.partition(":")
                name = name.split(";")[0].upper()
                current[name.lower()] = value
        for uid, copies in events.items():
            best = max(copies, key=lambda ev: canon_revision(ev.get("sequence")))
            if str(best.get("status", "")).upper() == "CANCELLED":
                continue
            start = self._ics_time(best, "dtstart")
            end = self._ics_time(best, "dtend")
            if end is None and start is not None and best.get("duration"):
                end = start + self._parse_duration(best["duration"])
            if start is None or end is None:
                continue
            host = canon_host(best.get("x-host"))
            if host is None:
                continue
            self.maintenance[host].append((start, end))

    @staticmethod
    def _parse_duration(value):
        match = re.match(r"^P(?:([0-9.]+)D)?(?:T)?(?:([0-9.]+)H)?(?:([0-9.]+)M)?(?:([0-9.]+)S)?$", value.strip())
        if not match:
            return dt.timedelta(0)
        days, hours, minutes, seconds = [float(g or 0) for g in match.groups()]
        return dt.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

    def _ics_time(self, event, field):
        for key, value in event.items():
            if key != field:
                continue
        value = event.get(field)
        if value is None:
            return None
        match = re.match(r"^(\d{8})T(\d{6})", value.strip())
        if not match:
            if re.match(r"^\d{8}$", value.strip()):
                return None  # all-day planning placeholder
            return None
        stamp = dt.datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
        return stamp

    def load_minutes(self):
        self.decisions = {}
        best = {}
        for table in docx_tables(self.path("review_minutes.docx")):
            header = [c.strip() for c in table[0]]
            for row in table[1:]:
                record = dict(zip(header, [c.strip() for c in row]))
                jid = canon_job(record.get("job"))
                if jid is None:
                    continue
                meeting = record.get("meeting", "")
                match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", meeting)
                if match:
                    moment = dt.datetime(int(match.group(3)), int(match.group(2)),
                                         int(match.group(1)), tzinfo=dt.timezone.utc)
                else:
                    moment = parse_iso(meeting)
                    if moment is None:
                        moment = serial_date(meeting)
                decision = record.get("decision", "").strip().lower()
                rev = canon_revision(record.get("revision", "0"))
                stamp = moment or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
                if jid not in best or (stamp, rev) > (best[jid][0], best[jid][1]):
                    best[jid] = (stamp, rev, decision)
        for jid, (_, _, decision) in best.items():
            self.decisions[jid] = decision

    def load_errata(self):
        self.void_jobs = set()
        self.restore_jobs = set()
        self.void_rows = collections.defaultdict(set)     # source -> set of row ids
        self.void_entries = {}                            # (file, key, rev) -> True
        self.void_baseline = set()                         # (item, revision date)
        self.excluded_shards = set()
        pending = []
        for table in docx_tables(self.path("errata_register.docx")):
            header = [c.strip() for c in table[0]]
            for row in table[1:]:
                record = dict(zip(header, [c.strip() for c in row]))
                kind = record.get("kind", "").strip().upper()
                source = canon_source(record.get("source", ""))
                target = record.get("target", "").strip()
                logged = record.get("logged", "").strip()
                pending.append((kind, source, target, logged))
        active = collections.Counter()
        for kind, source, target, logged in pending:
            if kind == "UNDO":
                active[(kind, source, target)] -= 1
            else:
                active[(kind, source, target)] += 1
        for (kind, source, target), count in active.items():
            if count <= 0:
                continue
            if kind == "VOID-JOB":
                jid = canon_job(target)
                if jid:
                    self.void_jobs.add(jid)
            elif kind == "RESTORE":
                jid = canon_job(target)
                if jid and (source or "").startswith("scores_staging"):
                    self.restore_jobs.add(jid)
            elif kind == "VOID-ROW":
                rowid = canon_rowid(target)
                if rowid and source:
                    self.void_rows[source].add(rowid)
            elif kind == "VOID-ENTRY":
                match = re.match(r"^(.*?)\s+rev\s+(\d+)$", target)
                if match:
                    key = canon_item(match.group(1))
                    rev = canon_revision(match.group(2))
                    if key:
                        self.void_entries[(source, key, rev)] = True
            elif kind == "VOID-BASELINE":
                parts = target.split()
                if len(parts) >= 2:
                    item = canon_item(parts[0])
                    if item:
                        self.void_baseline.add((item, parts[1]))
            elif kind == "EXCLUDE-SHARD":
                shard = low(target)
                match = re.match(r"^shard-?(\d+)$", shard)
                if match:
                    self.excluded_shards.add("shard-" + match.group(1).zfill(4))

    def load_harness(self):
        """SUBMIT and RERUN lines; the submission instant is the earliest SUBMIT."""
        self.submits = collections.defaultdict(list)
        self.reruns = collections.defaultdict(list)
        self.is_rerun = set()
        for text in read_text_lines(self.path("harness_events.log")):
            if not text.strip():
                continue
            tokens = text.split()
            if not tokens:
                continue
            stamp = tokens[0]
            start = 1
            if len(tokens) > 1 and re.match(r"^\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?$", tokens[1]):
                stamp = tokens[0] + " " + tokens[1]
                start = 2
            kind = None
            host = None
            fields = {}
            for token in tokens[start:]:
                if "=" in token:
                    key, value = token.split("=", 1)
                    key = low(key)
                    if value.startswith('"') and value.endswith('"') and len(value) > 1:
                        value = value[1:-1]
                    fields[key] = clean(value)
                else:
                    upper = token.upper()
                    if upper in ("SUBMIT", "RERUN", "END", "INFO", "WARN", "ERROR"):
                        if kind is None and upper in ("SUBMIT", "RERUN"):
                            kind = upper
                    elif re.match(r"^[Nn][Oo][Dd][Ee]-?\d+$", token):
                        host = canon_host(token)
            if kind is None:
                continue
            if host is None:
                host = canon_host(fields.get("host"))
            if kind == "SUBMIT":
                jid = canon_job(fields.get("job")) or self.legacy_job(fields.get("job"))
                if jid and jid in self.jobs:
                    self.submit_lines[jid].append((stamp, host or self.jobs[jid]["host"]))
            else:
                origin = canon_job(fields.get("of"))
                rerun = canon_job(fields.get("as"))
                if origin and rerun:
                    self.reruns[origin].append(rerun)
                    self.is_rerun.add(rerun)

    def _host_stamp(self, stamp, host, jid):
        """Parse a host-written timestamp into (utc instant, naive flag)."""
        if stamp.endswith("Z"):
            return parse_iso(stamp)
        naive = None
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)$", stamp)
        if match:
            try:
                naive = dt.datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)),
                                    int(match.group(4)), int(match.group(5)),
                                    int(float(match.group(6))), tzinfo=dt.timezone.utc)
            except ValueError:
                return None
        else:
            naive = parse_basic_datetime(stamp)
        if naive is None:
            return None
        guess = naive
        for _ in range(4):
            entry = self.inventory_entry(host, guess)
            zone = entry["tz"] if entry and entry.get("tz") else "UTC"
            offset = ZONE_OFFSETS.get(zone, dt.timedelta(0))
            offset = offset + dt.timedelta(milliseconds=float(self.clock_offset(host, guess)))
            moment = naive - offset
            if moment == guess:
                break
            guess = moment
        return guess

    def clock_offset(self, host, moment):
        year, weekno = iso_week(moment)
        return self.clocks.get((host, year, weekno), Fraction(0))

    def load_job_configs(self):
        self.configs = {}
        best = {}
        current = None
        with open(self.path("job_configs.toml"), encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if text == "[[job]]":
                    if current and current.get("id"):
                        self._keep_config(best, current)
                    current = {}
                    continue
                if current is None or "=" not in text or text.startswith("#"):
                    if text == "" and current and current.get("id"):
                        self._keep_config(best, current)
                        current = None
                    continue
                key, _, value = text.partition("=")
                key = clean(key).lower()
                value = value.split("#")[0].strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                if key == "id":
                    current["id"] = canon_job(value)
                elif key == "revision":
                    current["revision"] = canon_revision(value)
                elif key == "harness":
                    current["harness"] = low(value)
                    match = re.match(r"^(?:h(?:arness)?-?)?([0-9.]+)$", current["harness"])
                    current["harness_version"] = "h" + match.group(1) if match else current["harness"]
                elif key == "samples":
                    try:
                        current["samples"] = int(value)
                    except ValueError:
                        pass
                elif key == "settings":
                    inner = value[value.find("{") + 1:value.rfind("}")]
                    for item in inner.split(","):
                        if "=" not in item:
                            continue
                        k, v = item.split("=", 1)
                        k = clean(k).strip().lower()
                        v = v.strip().strip('"')
                        if k == "samples":
                            try:
                                current["samples"] = int(v)
                            except ValueError:
                                pass
            if current and current.get("id"):
                self._keep_config(best, current)
        self.configs = best

    @staticmethod
    def _keep_config(best, current):
        jid = current.get("id")
        if not jid:
            return
        rev = current.get("revision", -1)
        if jid not in best or rev > best[jid].get("revision", -1):
            best[jid] = current

    def harness(self, jid):
        config = self.configs.get(jid) or {}
        version = clean(config.get("harness_version", "")).lower()
        version = re.sub(r"^harness-", "h", version)
        if version.startswith("h"):
            version = "h" + version[1:].lstrip("-")
        return version or None

    def taxonomy(self, jid):
        version = self.harness(jid)
        return "v2" if version == "h4.0" else "v1"

    def grader(self, jid):
        return "g3" if self.harness(jid) == "h4.0" else "g2"

    def samples(self, jid):
        config = self.configs.get(jid) or {}
        return config.get("samples", 1)

    def load_precedence(self):
        self.field_winner = {}
        self.job_class = {}
        with open(self.path("field_precedence.html"), encoding="utf-8") as handle:
            text = handle.read()
        blocks = re.findall(r"<table[^>]*>(.*?)</table>", text, re.S)
        for block in blocks:
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S)
            if not rows:
                continue
            header = [clean(htmlmod.unescape(re.sub(r"<[^>]+>", "", c))).strip()
                      for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rows[0], re.S)]
            for row in rows[1:]:
                cells = [clean(htmlmod.unescape(re.sub(r"<[^>]+>", "", c))).strip()
                         for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
                record = dict(zip(header, cells))
                if "suite" in record and "winner" in record:
                    self.field_winner[(record["suite"], record["field"])] = (
                        canon_source(record["source_1"]), canon_source(record["source_2"]),
                        canon_source(record["winner"]))
                if "class" in record and "job" in record:
                    jid = canon_job(record["job"])
                    klass = record["class"].strip().lower()
                    if klass in ("std", "standard"):
                        klass = "standard"
                    elif klass in ("br", "bridge"):
                        klass = "bridge"
                    if jid and klass in ("standard", "bridge"):
                        rev = canon_revision(record.get("revision"))
                        if jid not in self.job_class or rev > self.job_class[jid][0]:
                            self.job_class[jid] = (rev, klass)
        self.job_class = {k: v[1] for k, v in self.job_class.items()}
        # only jobs with a second copy can be of the bridge class
        for jid in list(self.job_class):
            if self.job_class[jid] == "bridge":
                routing = self.routing.get(jid)
                if not routing or routing[1] in (None, "-"):
                    self.job_class[jid] = "standard"

    # -- items -----------------------------------------------------------
    def load_item_registries(self):
        records = read_csv_with_headers(self.path("item_registry.csv"))
        registry = {}
        for record in records:
            item = canon_item(record.get("item_id"))
            if item is None:
                continue
            rev = canon_revision(record.get("revision"))
            record["revision"] = rev
            registry.setdefault(item, []).append(record)
        self.item_registry = {}
        for item, rows in registry.items():
            best = max(rows, key=lambda r: r["revision"])
            if best["revision"] == 0:
                continue
            suite = canon_suite(best.get("suite"))
            if suite == "sandbox":
                continue
            self.item_registry[item] = {"suite": suite,
                                        "taxonomy": clean(best.get("taxonomy")).lower(),
                                        "subtask": clean(best.get("subtask"))}
        self.load_shard_map()
        self.load_suite_manifest()
        self.load_dedup()
        self.load_contamination()
        self.load_scope()
        self.load_scoring_parameters()
        self.load_context_lengths()
        self.load_locales()
        self.load_slices()

    def load_shard_map(self):
        self.shard_of = {}          # item -> (suite, shard, ordinal)
        positions = {}
        for header, rows in pdf_tables(self.path("metric_definitions.pdf")):
            fields = [h.strip().lower() for h in header]
            if not {"suite", "shard", "ordinal", "item_id", "revision"} <= set(fields):
                continue
            continuation = fields[0] == "item_id"
            for row in rows:
                record = dict(zip(fields, [str(c) for c in row]))
                suite = canon_suite(record.get("suite"))
                item = canon_item(record.get("item_id"))
                if item is None or suite is None:
                    continue
                try:
                    shard = int(clean(record.get("shard")))
                    ordinal = int(clean(record.get("ordinal")))
                except (TypeError, ValueError):
                    continue
                if continuation:
                    ordinal -= 1
                rev = canon_revision(record.get("revision"))
                key = (suite, shard, ordinal)
                current = positions.get(key)
                if current is None or rev > current[0]:
                    positions[key] = (rev, item)
        self.positions = {k: v[1] for k, v in positions.items()}
        by_item = collections.defaultdict(list)
        for (suite, shard, ordinal), item in self.positions.items():
            by_item[item].append((suite, shard, ordinal))
        for item, places in by_item.items():
            self.shard_of[item] = places[0]

    def load_suite_manifest(self):
        sheet_suites = {"core": {"arith", "intent"}, "reasoning": {"mcq", "longctx"},
                        "safety_code_pref": {"safety", "code", "pref"},
                        "multilingual": {"multiling"}}
        best = {}
        for sheet, rows in xlsx_rows(self.path("suite_manifest.xlsx")):
            allowed = sheet_suites.get(sheet)
            if not allowed or not rows:
                continue
            header = [str(c).strip() if c is not None else "" for c in rows[0]]
            for row in rows[1:]:
                record = dict(zip(header, row))
                item = canon_item(record.get("item_id"))
                if item is None or item not in self.item_registry:
                    continue
                if PREFIX_TO_SUITE[item[:3]] not in allowed:
                    continue
                rev = canon_revision(record.get("revision"))
                status = low(record.get("status"))
                changed = record.get("changed_at")
                if isinstance(changed, (int, float)):
                    moment = serial_date(changed)
                elif isinstance(changed, str) and changed.strip():
                    text = clean(changed)
                    if re.match(r"^\d+(\.\d+)?$", text):
                        moment = serial_date(text)
                    else:
                        moment = parse_iso(text)
                else:
                    moment = None
                key = item
                if key not in best or rev > best[key][0]:
                    best[key] = (rev, status, moment)
        self.retired = set()
        for item, (rev, status, moment) in best.items():
            if status in RETIRE_STATUSES:
                if moment is None:
                    self.retired.add(item)
                elif moment < WINDOW_END:
                    self.retired.add(item)
            elif status in ACTIVE_STATUSES and item in self.retired:
                self.retired.discard(item)

    def load_dedup(self):
        best = {}
        for record in read_tsv_with_headers(self.path("dedup_clusters.tsv")):
            item = canon_item(record.get("item_id"))
            if item is None or item not in self.item_registry:
                continue
            rev = canon_revision(record.get("revision"))
            cluster = clean(record.get("cluster"))
            match = re.match(r"^(\d+)$", cluster)
            if not match:
                continue
            if item not in best or rev > best[item][0]:
                best[item] = (rev, int(match.group(1)))
        groups = collections.defaultdict(list)
        for item, (_, cluster) in best.items():
            if cluster == 0:
                continue
            groups[(item[:3], cluster)].append(item)
        self.duplicates = set()
        for _, members in groups.items():
            if len(members) < 2:
                continue
            canonical = min(members)
            for member in members:
                if member != canonical:
                    self.duplicates.add(member)

    def load_contamination(self):
        best = collections.defaultdict(list)
        with open(self.path("contamination_hits.jsonl"), encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                item = canon_item(record.get("item", record.get("item_ref")))
                if item is None or item not in self.item_registry:
                    continue
                if record.get("retracted"):
                    continue
                shard = clean(record.get("shard", "")).lower()
                match = re.match(r"^shard-?(\d+)$", shard)
                if match and ("shard-" + match.group(1).zfill(4)) in self.excluded_shards:
                    continue
                overlap = record.get("overlap")
                if isinstance(overlap, str):
                    overlap = parse_number(overlap)
                if overlap is None:
                    continue
                detector = clean(record.get("detector", "")).lower()
                if detector == "ngram-v1":
                    overlap = overlap / 100
                stamp = record.get("scanned_at")
                if isinstance(stamp, str):
                    moment = parse_iso(stamp) or parse_epoch(stamp, "s")
                else:
                    moment = parse_epoch(stamp, "s")
                best[item].append((overlap, moment))
        self.contaminated = set()
        for item, scans in best.items():
            suite = PREFIX_TO_SUITE[item[:3]]
            threshold = CONTAMINATION_THRESHOLDS[suite]
            for overlap, _ in scans:
                if round_half_even(overlap, 4) >= threshold:
                    self.contaminated.add(item)
                    break

    def load_scope(self):
        best = {}
        for header, rows in self._policy_scope_table():
            for record in rows:
                item = canon_item(record.get("item_id"))
                if item is None:
                    continue
                rev = canon_revision(record.get("revision"))
                scope = clean(record.get("scope")).lower().strip('"')
                effective = clean(record.get("effective"))
                if item not in best or rev > best[item][0]:
                    best[item] = (rev, scope, effective)
        self.held_out = set()
        for item, (_, scope, effective) in best.items():
            if scope in IN_SCOPE and IN_SCOPE[scope] is False:
                moment = parse_iso(effective)
                if moment is None:
                    moment = serial_date(effective)
                if moment is None or moment < WINDOW_END:
                    self.held_out.add(item)

    def _policy_scope_table(self):
        with open(self.path("certification_policy.md"), encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        start = None
        for i, line in enumerate(lines):
            if line.startswith("## Appendix") and "scope" in line.lower():
                start = i
                break
        if start is None:
            return
        header = None
        rows = []
        for line in lines[start + 1:]:
            if line.strip().startswith("|"):
                cells = split_md_row(line)
                if not cells or set("".join(str(c) for c in cells)) <= set("- "):
                    continue
                if cells[0].strip().lower() == "item_id":
                    if header:
                        yield header, rows
                    header, rows = cells, []
                    continue
                if header:
                    rows.append(dict(zip(header, cells)))
                continue
            if header and rows:
                yield header, rows
                header, rows = None, []
        if header and rows:
            yield header, rows

    def load_scoring_parameters(self):
        self.params = {}
        best = collections.defaultdict(list)
        for sheet, rows in xlsx_rows(self.path("scoring_parameters.xlsx")):
            if not rows:
                continue
            header = [str(c).strip() if c is not None else "" for c in rows[0]]
            for row in rows[1:]:
                record = dict(zip(header, row))
                item = canon_item(record.get("item_id"))
                if item is None:
                    continue
                rev = canon_revision(record.get("revision"))
                best[item].append((rev, record))
        for item, entries in best.items():
            record = max(entries, key=lambda e: e[0])[1]
            tolerance = low(record.get("tolerance"))
            if tolerance in ("exact", "eq", "=="):
                kind = "exact"
            elif tolerance.startswith("abs") or "absolute" in tolerance or "+-" in tolerance:
                kind = "abs"
            elif tolerance.startswith("rel") or "relative" in tolerance:
                kind = "rel"
            else:
                kind = None
            raw_tests = record.get("tests")
            if isinstance(raw_tests, (int, float)) and not isinstance(raw_tests, bool):
                tests = int(raw_tests)
            else:
                match = re.match(r"^(\d+)", clean(raw_tests) or "")
                tests = int(match.group(1)) if match else None
            options = text(record.get("n_options"))
            n_options = None
            if isinstance(record.get("n_options"), (int, float)) and not isinstance(record.get("n_options"), bool):
                n_options = int(record["n_options"])
            elif options:
                match = re.match(r"^([A-Z])-([A-Z])$", options.upper())
                if match:
                    n_options = ord(match.group(2)) - ord(match.group(1)) + 1
                else:
                    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                             "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                             "eleven": 11, "twelve": 12}
                    n_options = words.get(options.strip().lower())
                    if n_options is None and options.strip().isdigit():
                        n_options = int(options.strip())
            self.params[item] = {"tolerance": kind, "tests": tests, "n_options": n_options,
                                 "profile": clean(record.get("profile"))}

    def load_context_lengths(self):
        best = {}
        for record in read_csv_with_headers(self.path("context_lengths.csv")):
            item = canon_item(record.get("item_id"))
            if item is None or item not in self.item_registry:
                continue
            rev = canon_revision(record.get("revision"))
            tokens = {}
            for column in ("tokens_hbpe", "tokens_ospsp"):
                value = record.get(column)
                if isinstance(value, (int, float)):
                    tokens[column] = int(value)
                else:
                    num = parse_number(value)
                    tokens[column] = int(num) if num is not None else None
            if item not in best or rev > best[item][0]:
                best[item] = (rev, tokens)
        self.tokens = {k: v[1] for k, v in best.items()}

    def load_locales(self):
        best = {}
        for record in read_tsv_with_headers(self.path("prompt_locales.tsv")):
            item = canon_item(record.get("item_id"))
            if item is None or item not in self.item_registry:
                continue
            rev = canon_revision(record.get("revision"))
            if item not in best or rev > best[item][0]:
                best[item] = (rev, clean(record.get("locale")))
        self.locales = {k: v[1] for k, v in best.items()}
        self.locale_map = {}
        retired_codes = set()
        for record in read_tsv_with_headers(self.path("locale_codes_legacy.tsv")):
            kind = clean(record.get("kind")).lower()
            if kind != "map":
                continue
            source = clean(record.get("key")).lower()
            target = clean(record.get("value")).lower()
            self.locale_map[source] = None if target == "-" else target

    def item_language(self, item):
        tag = self.locales.get(item)
        if not tag:
            return None
        text = tag.replace("_", "-")
        parts = text.split("-")
        if not parts or not parts[0]:
            return None
        language = parts[0].lower()
        if language.startswith("x"):
            return None
        mapped = self.locale_map.get(language)
        return mapped if mapped is not None else language

    def load_slices(self):
        data = yaml.safe_load(open(self.path("slice_definitions.yaml"), encoding="utf-8"))
        self.slice_min_support = int(data.get("min_support", 30))
        self.lang_min_support = int(data.get("lang_min_support", 20))
        self.slice_defs = data.get("slices", {}) or {}
        regions = {}
        for entry in data.get("regions", []) or []:
            if not isinstance(entry, dict):
                continue
            item = canon_item(entry.get("item", entry.get("id")))
            if item is None:
                continue
            rev = canon_revision(entry.get("rev"))
            value = clean(entry.get("region")).strip()
            value = (data.get("region_aliases", {}) or {}).get(value, value).upper()
            if item not in regions or rev > regions[item][0]:
                regions[item] = (rev, value)
        self.regions = {k: v[1] for k, v in regions.items()}
        best = {}
        for record in read_csv_with_headers(self.path("slice_attributes.csv")):
            item = canon_item(record.get("item_id"))
            if item is None or item not in self.item_registry:
                continue
            rev = canon_revision(record.get("revision"))
            domain = clean(record.get("domain")).strip().lower()
            if domain.upper() in DOMAIN_CODES:
                domain = DOMAIN_CODES[domain.upper()]
            difficulty = clean(record.get("difficulty")).strip().lower()
            if difficulty in DIFFICULTY_CODES:
                difficulty = DIFFICULTY_CODES[difficulty]
            elif difficulty == "":
                difficulty = "medium"
            if item not in best or rev > best[item][0]:
                best[item] = (rev, domain, difficulty)
        self.attributes = {k: (v[1], v[2]) for k, v in best.items()}

    # -- gold ------------------------------------------------------------
    def load_gold(self):
        best = {}
        for record in read_tsv_with_headers(self.path("gold_labels.tsv")):
            item = canon_item(record.get("item_id"))
            if item is None or item not in self.item_registry:
                continue
            rev = canon_revision(record.get("revision"))
            value = record.get("gold", record.get("answer"))
            if item not in best or rev > best[item][0]:
                best[item] = (rev, value)
        self.gold = {k: v[1] for k, v in best.items()}
        # ticket -> item map from the corrected export
        tickets = collections.defaultdict(list)
        for record in read_csv_with_headers(self.path("gold_labels_corrected.csv")):
            ticket = canon_ticket(record.get("dispute_ticket"))
            item = canon_item(record.get("item_id"))
            if ticket is None or item is None:
                continue
            corrected = record.get("corrected_at")
            if isinstance(corrected, str) and re.match(r"^\d+(\.\d+)?$", clean(corrected)):
                moment = serial_date(corrected)
            else:
                moment = parse_iso(corrected)
            if moment is None:
                continue
            tickets[ticket].append((moment, item))
        self.ticket_items = {}
        for ticket, entries in tickets.items():
            entries.sort(key=lambda e: (e[0], e[1]))
            self.ticket_items[ticket] = entries[-1][1]
        # grader errata
        decided = collections.defaultdict(list)
        root = ET.parse(self.path("grader_errata.xml")).getroot()
        for block in root:
            for element in block:
                attrs = dict(element.attrib)
                ticket = canon_ticket(attrs.get("ticket"))
                if ticket is None:
                    continue
                status = clean(attrs.get("status", attrs.get("fix") and attrs.get("status"))).lower()
                value = attrs.get("value", attrs.get("fix"))
                stamp = attrs.get("decided")
                if stamp is None:
                    continue
                text = clean(stamp)
                if re.match(r"^\d+$", text):
                    moment = parse_epoch(text, "s")
                else:
                    moment = parse_iso(text)
                if moment is None:
                    continue
                decided[ticket].append((moment, status, value))
        for ticket, entries in decided.items():
            entries = [e for e in entries if e[0] <= CUTOFF]
            if not entries:
                continue
            entries.sort(key=lambda e: e[0])
            moment, status, value = entries[-1]
            if status not in ("upheld", "confirmed"):
                continue
            item = self.ticket_items.get(ticket)
            if item is None:
                continue
            corrected_at = None
            for stamp, candidate in tickets.get(ticket, []):
                if stamp is not None and moment >= stamp:
                    corrected_at = candidate
            if corrected_at is None:
                continue
            self.gold[item] = value

    # -- baseline --------------------------------------------------------
    def load_baseline(self):
        rows = []
        with open(self.path("baseline_reference.csv"), encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = None
            for cells in reader:
                cells = [clean(c) if isinstance(c, str) else c for c in cells]
                if not cells:
                    continue
                if header is None:
                    header = [str(c).strip() for c in cells]
                    continue
                if str(cells[0]).strip().lower() == "ref" and set(str(c).strip() for c in cells) == set(header):
                    header = [str(c).strip() for c in cells]
                    continue
                if len(cells) == len(header):
                    rows.append(dict(zip(header, cells)))
        crosswalk = self.load_crosswalk()
        best = {}
        for record in rows:
            if clean(record.get("status")).lower() == "withdrawn":
                continue
            ref = canon_item(record.get("ref")) or crosswalk.get(canon_legacy_code(record.get("ref")))
            if ref is None:
                continue
            revised = record.get("revised")
            if isinstance(revised, str) and re.match(r"^\d+(\.\d+)?$", clean(revised)):
                moment = serial_date(revised)
            else:
                moment = parse_iso(revised)
            if moment is None:
                continue
            entry = {
                "suite": canon_suite(record.get("suite")),
                "value": record.get("value"),
                "confidence": record.get("confidence"),
                "revised": moment,
            }
            if ref not in best or moment > best[ref]["revised"]:
                best[ref] = entry
        self.baseline_rows = best

    def load_crosswalk(self):
        best = {}
        for header, rows in pdf_tables(self.path("methodology_appendix.pdf")):
            fields = [h.strip().lower() for h in header]
            if not {"legacy_code", "item_id", "revision"} <= set(fields):
                continue
            for row in rows:
                record = dict(zip(fields, [str(c) for c in row]))
                code = canon_legacy_code(record.get("legacy_code"))
                item = canon_item(record.get("item_id"))
                if code is None or item is None:
                    continue
                rev = canon_revision(record.get("revision"))
                if code not in best or rev > best[code][0]:
                    best[code] = (rev, item)
        return {k: v[1] for k, v in best.items()}

    # -- control totals --------------------------------------------------
    def load_control(self):
        self.control = {}
        best = {}
        for table in html_tables(self.path("control_totals.html")):
            header = [c.strip() for c in table[0]]
            for row in table[1:]:
                record = dict(zip(header, row))
                jid = canon_job(record.get("job"))
                if jid is None:
                    continue
                rev = canon_revision(record.get("revision"))
                if jid not in best or rev > best[jid][0]:
                    expected = clean(record.get("expected_rows"))
                    expected = re.sub(r"\s*rows$", "", expected, flags=re.I)
                    best[jid] = (rev, parse_number(expected))
        self.control = {k: v[1] for k, v in best.items()}

    def load_routing(self):
        best = {}
        for header, rows in md_table_blocks(self.path("source_conventions.md")):
            fields = [h.strip().lower() for h in header]
            if "primary_source" not in fields:
                continue
            for row in rows:
                record = dict(zip(fields, row))
                jid = canon_job(record.get("job"))
                if jid is None:
                    continue
                rev = canon_revision(record.get("revision"))
                primary = canon_source(record.get("primary_source"))
                copy = canon_source(record.get("copy_source"))
                if jid not in best or rev > best[jid][0]:
                    best[jid] = (rev, primary, copy)
        self.routing = {k: (v[1], v[2]) for k, v in best.items()}

    # -- submission instants and dispositions ----------------------------
    def resolve_submission(self):
        """Earliest SUBMIT instant per job, resolved twice so the submission week
        used for zone and clock correction is the job's own submission week."""
        self.submission = {}
        for jid, lines in self.submit_lines.items():
            moments = [m for m in (self.host_written(stamp, host, jid) for stamp, host in lines)
                       if m is not None]
            if moments:
                self.submission[jid] = min(moments)
        for jid, lines in self.submit_lines.items():
            moments = [m for m in (self.host_written(stamp, host, jid) for stamp, host in lines)
                       if m is not None]
            if moments:
                self.submission[jid] = min(moments)

    def dispositions(self):
        """Assign exactly one disposition to every registered job."""
        result = {}
        rerun_children = collections.defaultdict(list)
        for origin, children in self.reruns.items():
            for child in children:
                rerun_children[child].append(origin)
        approved_rerun = set()
        denied_rerun = set()
        for child, origins in rerun_children.items():
            decision = self.decisions.get(child, "")
            if decision in ("rerun-approved", "approve", "ok"):
                approved_rerun.add(child)
            elif decision in ("rerun-denied", "deny", "no"):
                denied_rerun.add(child)
        superseded = set()
        for origin, children in self.reruns.items():
            for child in children:
                if child in approved_rerun:
                    superseded.add(origin)
        for jid in sorted(self.jobs):
            job = self.jobs[jid]
            moment = self.submission.get(jid)
            certified = self.certified.get(job["model"], {})
            checkpoint = self.resolve_checkpoint(jid)
            if jid in self.void_jobs:
                result[jid] = "voided"
            elif self.is_staging_host(jid, moment):
                result[jid] = "staging_host"
            elif not certified or checkpoint is None or checkpoint != certified.get("checkpoint"):
                result[jid] = "stale_checkpoint"
            elif moment is None or not (WINDOW_START <= moment < WINDOW_END):
                result[jid] = "outside_window"
            elif self.in_maintenance(jid, moment):
                result[jid] = "maintenance"
            elif jid in superseded:
                result[jid] = "superseded"
            elif jid in rerun_children and jid not in approved_rerun:
                result[jid] = "rerun_denied"
            else:
                result[jid] = "authoritative"
        return result

    def is_staging_host(self, jid, moment):
        job = self.jobs.get(jid)
        if not job or moment is None:
            return False
        entry = self.inventory_entry(job["host"], moment)
        return bool(entry) and entry.get("fleet") in STAGE_FLEETS

    def in_maintenance(self, jid, moment):
        job = self.jobs.get(jid)
        if not job or moment is None:
            return False
        decision = self.decisions.get(jid, "")
        if decision in ("exempt-maintenance", "exempt"):
            return False
        for start, end in self.maintenance.get(job["host"], []):
            if start <= moment < end:
                return True
        return False

    def resolve_checkpoint(self, jid):
        """Checkpoint of a job, resolving 7-character prefixes by model family."""
        job = self.jobs.get(jid)
        if not job:
            return None
        checkpoint = job["checkpoint"]
        if checkpoint is None:
            return None
        if len(checkpoint) == 13:
            return checkpoint
        if re.match(r"^ck-[0-9a-f]{1,10}$", checkpoint):
            family = None
            info = self.lineage.get(checkpoint) or self.ema.get(checkpoint)
            if info:
                family = info["family"]
            else:
                family = self.alias_family(job["model"])
            if family:
                matches = sorted(cid for cid, entry in list(self.lineage.items()) + list(self.ema.items())
                                 if cid.startswith(checkpoint) and entry["family"] == family)
                if len(matches) == 1:
                    return matches[0]
        return checkpoint

    def alias_family(self, alias):
        info = self.checkpoint_info(self.certified.get(alias, {}).get("checkpoint"))
        return info["family"] if info else None

    def host_written(self, stamp, host, jid):
        """A host-written timestamp converted to UTC with zone and clock correction."""
        if stamp is None:
            return None
        if stamp.endswith("Z"):
            return parse_iso(stamp)
        naive = None
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)$", stamp)
        if match:
            try:
                naive = dt.datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)),
                                    int(match.group(4)), int(match.group(5)),
                                    int(float(match.group(6))), tzinfo=dt.timezone.utc)
            except ValueError:
                return None
        else:
            naive = parse_basic_datetime(stamp)
        if naive is None:
            return None
        known = self.submission.get(jid)
        guess = known if known is not None else naive
        shifted = None
        for _ in range(5):
            entry = self.inventory_entry(host, guess)
            zone = entry["tz"] if entry and entry.get("tz") else "UTC"
            offset = ZONE_OFFSETS.get(zone, dt.timedelta(0))
            clock = self.clock_offset(host, guess)
            shifted = naive - offset - dt.timedelta(milliseconds=float(clock))
            if shifted == guess or known is not None:
                break
            guess = shifted
        return shifted


# --------------------------------------------------------------------------
# result records
# --------------------------------------------------------------------------

class Record:
    """One result record of one source file."""
    __slots__ = ("index", "rid", "job", "item", "sample", "emitted", "values", "cancelled")

    def __init__(self, index, rid, job, item, sample, emitted, values):
        self.index = index
        self.rid = rid
        self.job = job
        self.item = item
        self.sample = sample
        self.emitted = emitted
        self.values = values
        self.cancelled = False


def _locale_scale(corpus, host, jid):
    """Locale and scale of the job's submission week."""
    moment = corpus.submission.get(jid)
    if moment is None:
        return "en_US", "unit"
    entry = corpus.inventory_entry(host, moment)
    if not entry:
        return "en_US", "unit"
    return LOCALES.get(entry.get("locale", "en_us"), "en_US"), entry.get("scale", "unit")


def _kv_pairs(rest):
    fields = {}
    for item in rest.split():
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = low(key)
        if value.startswith('"') and value.endswith('"') and len(value) > 1:
            value = value[1:-1]
        fields[key] = clean(value)
    return fields


def parse_fleet_log(corpus, name, records):
    """results_fleet_[abc].log: timestamp host LEVEL key=value ..."""
    cancelled = set()
    parsed = []
    index = 0
    for text in read_text_lines(corpus.path(name)):
        if not text.strip():
            continue
        match = re.match(r"^(\S+)\s+(\S+)\s+(\S+)\s*(.*)$", text)
        if not match:
            continue
        stamp, host, _level, rest = match.groups()
        fields = _kv_pairs(rest)
        if "flushed" in fields or not fields.get("job"):
            continue
        if fields.get("op", "").upper() == "REVERSE":
            target = canon_rowid(fields.get("target"))
            if target:
                cancelled.add(target)
            continue
        index += 1
        jid = canon_job(fields.get("job"))
        if jid is None:
            continue
        rid = canon_rowid(fields.get("rid"))
        emitted = corpus.host_written(stamp, canon_host(host), jid)
        record = Record(index, rid, jid, None, 0, emitted, fields)
        parsed.append(record)
    for record in parsed:
        if record.rid and record.rid in cancelled:
            record.cancelled = True
    for record in parsed:
        records[record.job][name].append(record)
    return index


def parse_parquet(corpus, name, records):
    """scores_shard[12].parquet and scores_staging.parquet."""
    path = corpus.path(name)
    table = pq.read_table(path).to_pydict()
    seconds_groups = STAGE_PARQUET_ROWGROUP_SECONDS.get(name, set())
    reader = pq.ParquetFile(path)
    ranges = []
    start = 0
    for group in range(reader.num_row_groups):
        count = reader.metadata.row_group(group).num_rows
        ranges.append((start, start + count, group in seconds_groups))
        start += count
    total = 0
    for pos, (rid, job, item, bench, txt, num, emitted, host) in enumerate(zip(
            table["rid"], table["job"], table["item"], table["bench"], table["txt"],
            table["num"], table["emitted"], table["host"])):
        total += 1
        jid = canon_job(job)
        if jid is None:
            continue
        unit = "ms"
        for low, high, is_seconds in ranges:
            if low <= pos < high:
                unit = "s" if is_seconds else "ms"
                break
        moment = parse_epoch(emitted, unit)
        if moment is not None:
            offset = corpus.clock_offset(canon_host(host), moment)
            moment = moment - dt.timedelta(milliseconds=float(offset))
        record = Record(pos + 1, canon_rowid(rid), jid, canon_item(item), 0, moment, {})
        record.values = {"_txt": txt, "_num": num, "_bench": canon_suite(bench),
                         "src": clean(txt) if False else None}
        records[jid][name].append(record)
    return total


def parse_store(corpus, name, records):
    """eval_store.db / eval_store_mirror.db result rows (mirror: result_value)."""
    connection = sqlite3.connect(corpus.path(name))
    total = 0
    columns = [row[1] for row in connection.execute("PRAGMA table_info(results)")]
    value_column = "result_value" if "result_value" in columns else "value"
    rows = connection.execute(
        "select rid, job, item, pos, sample, %s, emitted from results" % value_column)
    for rid, job, item, pos, sample, value, emitted in rows:
        total += 1
        jid = canon_job(job)
        if jid is None:
            continue
        moment = parse_iso(emitted)
        record = Record(total, canon_rowid(rid), jid, canon_item(item),
                        int(sample) if sample is not None else 0, moment, {})
        record.values = {"_value": value, "_pos": pos}
        records[jid][name].append(record)
    connection.close()
    return total


def parse_code_samples(corpus, name, records):
    total = 0
    for line in read_text_lines(corpus.path(name)):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        jid = canon_job(entry.get("job"))
        if jid is None:
            continue
        total += 1
        host = canon_host(entry.get("worker"))
        ts = entry.get("ts")
        if isinstance(ts, str) and ts.endswith("Z"):
            moment = parse_iso(ts)
        elif isinstance(ts, str):
            moment = parse_iso(ts)
            if moment is not None:
                offset = corpus.clock_offset(host, moment)
                moment = moment + dt.timedelta(milliseconds=float(offset))
        else:
            moment = parse_epoch(ts, "ms")
            if moment is not None:
                offset = corpus.clock_offset(host, moment)
                moment = moment - dt.timedelta(milliseconds=float(offset))
        record = Record(total, canon_rowid(entry.get("rid")), jid,
                         canon_item(entry.get("problem")),
                         int(entry.get("sample") or 0), moment, {})
        record.values = {"passed": entry.get("passed"), "exit": entry.get("exit"),
                         "total": entry.get("total")}
        records[jid][name].append(record)
    return total


def parse_judge(corpus, name, records):
    total = 0
    for line in read_text_lines(corpus.path(name)):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        jid = canon_job(entry.get("job"))
        if jid is None:
            continue
        total += 1
        try:
            slot = int(entry.get("slot"))
        except (TypeError, ValueError):
            slot = 0
        record = Record(total, canon_rowid(entry.get("rid")), jid,
                         canon_item(entry.get("item")), slot, parse_iso(entry.get("ts")), {})
        record.values = {"verdict": clean(entry.get("verdict")), "judge": low(entry.get("judge"))}
        records[jid][name].append(record)
    return total


def parse_rescored(corpus, name, records):
    """Only the presentation field of the rescored export is used."""
    presentation = {}
    total = 0
    for line in read_text_lines(corpus.path(name)):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        jid = canon_job(entry.get("job"))
        item = canon_item(entry.get("item"))
        if jid is None or item is None:
            continue
        field = low(entry.get("presentation"))
        if field:
            presentation.setdefault((jid, item), field)
    corpus.presentation = presentation
    return total


def parse_rerun(corpus, name, records):
    total = 0
    for line in read_text_lines(corpus.path(name)):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        jid = canon_job(entry.get("job"))
        if jid is None:
            continue
        total += 1
        value = entry.get("value")
        slot = None
        verdict = None
        if isinstance(value, dict):
            verdict = clean(value.get("verdict"))
            try:
                slot = int(value.get("slot"))
            except (TypeError, ValueError):
                slot = None
        record = Record(total, canon_rowid(entry.get("rid")), jid,
                         canon_item(entry.get("item")),
                         int(entry.get("sample") or 0), parse_iso(entry.get("ts")), {})
        record.values = {"_value": value if not isinstance(value, dict) else None,
                         "verdict": verdict, "slot": slot,
                         "_bench": canon_suite(entry.get("bench"))}
        records[jid][name].append(record)
    return total


def parse_legacy(corpus, name, records):
    """legacy_results.txt fixed-width layouts A and B."""
    total = 0
    layout = "A"
    for text in read_text_lines(corpus.path(name)):
        if not text.strip():
            continue
        if text.lstrip().startswith("#"):
            match = re.match(r"#LAYOUT\s+([AB])", text.strip())
            if match:
                layout = match.group(1)
            continue
        total += 1
        if layout == "A":
            rid = canon_rowid(text[0:9])
            job = text[9:19]
            item = text[19:30]
            answer = text[30:50]
            emit = text[50:65]
            host = canon_host(text[66:].strip())
            pos = None
        else:
            rid = canon_rowid(text[0:9])
            host = canon_host(text[9:20].strip())
            job = text[20:30]
            pos = text[30:33].strip()
            emit = text[33:48]
            answer = text[48:68]
            item = None
        jid = canon_job(job) or corpus.legacy_job(job)
        if jid is None:
            continue
        moment = parse_basic_datetime(emit)
        if moment is not None and host is not None:
            entry = corpus.inventory_entry(host, moment)
            zone = entry["tz"] if entry and entry.get("tz") else "UTC"
            moment = moment - ZONE_OFFSETS.get(zone, dt.timedelta(0))
        record = Record(total, rid, jid, canon_item(item), 0, moment, {})
        record.values = {"_value": answer.strip(), "_pos": pos, "_host": host}
        records[jid][name].append(record)
    return total


def parse_intent_predictions(corpus, name, records):
    total = 0
    header = None
    for cells in csv.reader(read_text_lines(corpus.path(name))):
        cells = [clean(cell) if isinstance(cell, str) else cell for cell in cells]
        if not cells:
            continue
        if header is None:
            header = [str(cell).strip() for cell in cells]
            continue
        if str(cells[0]).strip().lower() == "rid" and set(str(c).strip() for c in cells) == set(header):
            header = [str(c).strip() for c in cells]
            continue
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        jid = canon_job(row.get("job"))
        if jid is None:
            continue
        total += 1
        local = clean(row.get("local_time") or row.get("emitted_local"))
        offset = clean(row.get("utc_offset"))
        moment = parse_iso(local) if local else None
        if moment is not None:
            if offset:
                match = re.match(r"^([+-])(\d{2})(\d{2})$", offset)
                if match:
                    delta = dt.timedelta(hours=int(match.group(2)), minutes=int(match.group(3)))
                    if match.group(1) == "-":
                        delta = -delta
                    if delta == dt.timedelta(hours=1):
                        delta = dt.timedelta(hours=2)
                    moment = moment - delta
            host = corpus.jobs.get(jid, {}).get("host")
            clock = corpus.clock_offset(host, moment)
            moment = moment - dt.timedelta(milliseconds=float(clock))
        record = Record(total, canon_rowid(row.get("rid")), jid, canon_item(row.get("item")),
                        0, moment, {})
        record.values = {"label": row.get("label", row.get("predicted_label"))}
        records[jid][name].append(record)
    return total


def load_result_sources(corpus):
    """Parse every result source into records grouped by job and source."""
    records = collections.defaultdict(lambda: collections.defaultdict(list))
    counts = {}
    counts["results_fleet_a.log"] = parse_fleet_log(corpus, "results_fleet_a.log", records)
    counts["results_fleet_b.log"] = parse_fleet_log(corpus, "results_fleet_b.log", records)
    counts["results_fleet_c.log"] = parse_fleet_log(corpus, "results_fleet_c.log", records)
    counts["scores_shard1.parquet"] = parse_parquet(corpus, "scores_shard1.parquet", records)
    counts["scores_shard2.parquet"] = parse_parquet(corpus, "scores_shard2.parquet", records)
    counts["scores_staging.parquet"] = parse_parquet(corpus, "scores_staging.parquet", records)
    counts["eval_store.db"] = parse_store(corpus, "eval_store.db", records)
    counts["eval_store_mirror.db"] = parse_store(corpus, "eval_store_mirror.db", records)
    counts["code_samples.jsonl"] = parse_code_samples(corpus, "code_samples.jsonl", records)
    counts["judge_verdicts.jsonl"] = parse_judge(corpus, "judge_verdicts.jsonl", records)
    counts["judge_verdicts_rescored.jsonl"] = parse_rescored(corpus, "judge_verdicts_rescored.jsonl", records)
    counts["rerun_results.jsonl"] = parse_rerun(corpus, "rerun_results.jsonl", records)
    counts["legacy_results.txt"] = parse_legacy(corpus, "legacy_results.txt", records)
    counts["intent_predictions.csv"] = parse_intent_predictions(corpus, "intent_predictions.csv", records)
    return records, counts


# --------------------------------------------------------------------------
# certification engine
# --------------------------------------------------------------------------

def load_manual_overrides(corpus):
    """Final reviewer verdicts that replace judge verdicts, keyed by (job, item, slot)."""
    best = {}
    for _, rows in xlsx_rows(corpus.path("manual_overrides.xlsx")):
        if not rows:
            continue
        header = [str(c).strip() if c is not None else "" for c in rows[0]]
        for row in rows[1:]:
            record = dict(zip(header, row))
            jid = canon_job(record.get("job"))
            item = canon_item(record.get("item"))
            if jid is None or item is None:
                continue
            if low(record.get("status")) != "final":
                continue
            try:
                slot = int(record.get("slot"))
            except (TypeError, ValueError):
                slot = 0
            verdict = clean(record.get("verdict")).lower()
            if verdict in ("=", "tie"):
                verdict = "tie"
            reviewed = record.get("reviewed_at")
            if isinstance(reviewed, str) and re.match(r"^\d+(\.\d+)?$", clean(reviewed)):
                moment = serial_date(reviewed)
            else:
                moment = parse_iso(reviewed) if isinstance(reviewed, str) else serial_date(reviewed)
            key = (jid, item, slot)
            stamp = moment or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
            if key not in best or stamp > best[key][0]:
                best[key] = (stamp, verdict)
    return {k: v[1] for k, v in best.items()}


def load_void_requests(corpus):
    """Row ids the replica's void_requests table voids, per source file."""
    result = collections.defaultdict(set)
    path = corpus.path("eval_store_mirror.db")
    if not os.path.exists(path):
        return result
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute("select source, row_id, reason from void_requests")
    except sqlite3.Error:
        connection.close()
        return result
    for source, row_id, _reason in rows:
        name = canon_source(source)
        rid = canon_rowid(row_id)
        if name and rid:
            result[name].add(rid)
    connection.close()
    return result


class Certifier:
    def __init__(self, corpus):
        self.corpus = corpus
        self.dispositions = corpus.dispositions()
        self.authoritative = sorted(j for j, d in self.dispositions.items() if d == "authoritative")
        self.overrides = load_manual_overrides(corpus)
        self.void_requests = load_void_requests(corpus)
        self.labels = self.load_aliases()
        self.jobs_by_key = collections.defaultdict(list)
        for jid in self.authoritative:
            job = corpus.jobs[jid]
            self.jobs_by_key[(job["model"], job["suite"], job["shard"])].append(jid)
        self.values = {}            # (model, item) -> dict of certified fields
        self.used = collections.defaultdict(set)   # source -> set of record indexes
        self.scored_items = collections.defaultdict(set)  # model -> set of items
        self.reverse_ids = collections.defaultdict(set)  # source -> row ids reversed

    # -- label aliases ---------------------------------------------------
    def load_aliases(self):
        data = json.load(open(self.corpus.path("label_aliases.json"), encoding="utf-8"))
        taxonomy = data.get("taxonomy", {})
        v1 = {clean(name).lower() for name in taxonomy.get("v1", [])}
        v2 = {clean(name).lower() for name in taxonomy.get("v2", [])}
        best = {}
        for entry in data.get("aliases", []):
            raw = unicodedata.normalize("NFC", clean(entry.get("raw")))
            rev = canon_revision(entry.get("revision"))
            if raw not in best or rev > best[raw][0]:
                best[raw] = (rev, entry)
        table = {}
        for raw, (rev, entry) in best.items():
            one = clean(entry.get("v1")).lower()
            two = entry.get("v2")
            if two is None:
                two = V2_RENAMES.get(one, one)
            else:
                two = clean(two).lower()
            table[raw] = (one if one in v1 else None, two if two in v2 else None)
        return table

    def resolve_label(self, raw, taxonomy):
        if raw is None:
            return None
        key = unicodedata.normalize("NFC", clean(raw))
        entry = self.labels.get(key)
        if entry is None:
            return None
        return entry[1] if taxonomy == "v2" else entry[0]

    # -- record filters --------------------------------------------------
    def shard_items(self, job):
        return set(self.corpus.positions.get((job["suite"], job["shard"]), {}).values())

    def item_of_record(self, job, record, source):
        corpus = self.corpus
        values = record.values
        item = record.item
        pos = values.get("_pos")
        if pos is not None and not isinstance(pos, int):
            try:
                pos = int(clean(pos))
            except (TypeError, ValueError):
                pos = None
        if pos is not None:
            item = corpus.positions.get((job["suite"], job["shard"], pos))
        return item if item else None

    def live_records(self, job, source, records):
        corpus = self.corpus
        jid = job["job"]
        seal = corpus.seal_time(jid)
        shard_items = self.shard_items(job)
        void_rows = corpus.void_rows.get(source, set())
        void_reqs = self.void_requests.get(source, set())
        out = []
        for record in records:
            if record.rid and record.rid in self.reverse_ids.get(source, ()):
                continue
            if record.rid and record.rid in void_rows:
                continue
            if record.rid and record.rid in void_reqs:
                continue
            if record.values.get("src") == "shadow":
                continue
            item = self.item_of_record(job, record, source)
            if item is None or item not in shard_items:
                continue
            if not self.eligible(item):
                continue
            if record.emitted is not None and seal is not None and record.emitted > seal:
                continue
            if record.values.get("exit") == 137 and str(record.values.get("passed")) == "-1":
                continue
            record.item = item
            out.append(record)
        return out

    def eligible(self, item):
        return item in self.corpus.eligible

    # -- certification ---------------------------------------------------
    def run(self, records_by_job):
        corpus = self.corpus
        for jid in self.authoritative:
            job = corpus.jobs[jid]
            primary, copy = self.sources_for(job)
            for source in (primary, copy):
                if not source:
                    continue
                records = records_by_job.get(jid, {}).get(source, [])
                self.certify_source(job, source, records)

    def sources_for(self, job):
        corpus = self.corpus
        jid = job["job"]
        if jid in corpus.restore_jobs:
            return "scores_staging.parquet", None
        routing = corpus.routing.get(jid, (None, None))
        primary = routing[0] if routing else None
        copy = routing[1] if routing else None
        if primary == "-":
            primary = None
        if copy == "-":
            copy = None
        return primary, copy

    def field_winner(self, job, field, primary, copy):
        corpus = self.corpus
        if primary is None:
            return copy
        if copy is None or copy == primary:
            return primary
        rule = corpus.field_winner.get((job["suite"], field))
        if not rule:
            return primary
        one, two, winner = rule
        if {one, two} != {primary, copy}:
            return primary
        if corpus.job_class.get(job["job"], "standard") == "bridge":
            return two if winner == one else one
        return winner

    def certify_source(self, job, source, records):
        if not records:
            return
        live = self.live_records(job, source, records)
        if not live:
            return
        best = {}
        for record in live:
            key = (record.item, record.sample)
            current = best.get(key)
            if current is None or current.emitted is None or (
                    record.emitted is not None and record.emitted >= current.emitted):
                best[key] = record
        primary, copy = self.sources_for(job)
        for (item, sample), record in sorted(best.items()):
            fields = self.extract(source, record, job)
            if not fields:
                continue
            key = (job["model"], job["suite"], item, sample)
            bucket = self.values.setdefault(key, {})
            for field, value in fields.items():
                winner = self.field_winner(job, field, primary, copy)
                entry = bucket.get(field)
                if entry is None or winner == source:
                    bucket[field] = (source, value, record, job["job"])
                    if winner == source:
                        self.used[source].add(record.index)

    # -- per-source field extraction -------------------------------------
    def extract(self, source, record, job):
        corpus = self.corpus
        suite = job["suite"]
        locale, scale = _locale_scale(corpus, job["host"], job["job"])
        values = record.values
        fields = {}
        if source.startswith("results_fleet_"):
            if suite == "arith":
                fields["answer"] = self._number(values.get("ans"), locale, scale, 2)
            elif suite == "intent":
                fields["label"] = values.get("label")
            elif suite == "mcq":
                if values.get("opt"):
                    fields["option"] = clean(values["opt"]).upper()
                if values.get("conf") is not None:
                    fields["conf"] = self._number(values["conf"], locale, scale, 4)
            elif suite == "safety":
                fields["score"] = self._number(values.get("score"), locale, scale, 3)
            elif suite in ("multiling", "longctx"):
                fields["answer"] = nfc(clean(values.get("ans")))
        elif source.endswith(".parquet"):
            text = nfc(clean(values.get("_txt")))
            number = values.get("_num")
            if suite == "mcq":
                if text:
                    fields["option"] = text.upper()
                if number is not None and number != -1.0:
                    fields["conf"] = self._number(number, locale, scale, 4)
            elif suite == "safety":
                if number is not None and number != -1.0:
                    fields["score"] = self._number(number, locale, scale, 3)
            elif suite == "intent":
                if text:
                    fields["label"] = text
            elif suite in ("multiling", "longctx"):
                if text:
                    fields["answer"] = text
            elif suite == "arith":
                if number is not None and number != -1.0:
                    fields["answer"] = self._number(number, locale, scale, 2)
            elif suite == "code":
                if number is not None and number != -1.0:
                    fields["passed"] = int(round(float(number)))
        elif source.endswith(".db"):
            value = values.get("_value")
            if suite == "code":
                number = parse_number(value)
                if number is not None:
                    fields["passed"] = int(number)
            elif suite in ("longctx", "multiling"):
                if value:
                    fields["answer"] = nfc(clean(value))
            elif suite == "arith":
                text = clean(value)
                if text.upper() in ("N/A", "NA", ""):
                    fields["answer"] = None
                else:
                    fields["answer"] = self._number(value, locale, "unit", 2)
            elif suite == "mcq":
                text = clean(value)
                if "|" in text:
                    option, _, conf = text.partition("|")
                    fields["option"] = clean(option).upper() or None
                    fields["conf"] = self._number(conf, locale, "unit", 4)
                elif text:
                    fields["option"] = text.upper()
        elif source == "code_samples.jsonl":
            number = parse_number(values.get("passed"))
            if number is not None:
                fields["passed"] = int(number)
        elif source == "judge_verdicts.jsonl":
            fields.update(self.pref_fields(record, job))
        elif source == "rerun_results.jsonl":
            value = values.get("_value")
            if suite == "pref":
                fields.update(self.pref_fields(record, job))
            elif suite == "code":
                number = parse_number(value)
                if number is not None:
                    fields["passed"] = int(number)
            elif suite == "mcq":
                text = clean(value)
                if "|" in text:
                    option, _, conf = text.partition("|")
                    fields["option"] = clean(option).upper() or None
                    fields["conf"] = self._number(conf, "en_US", "unit", 4)
                elif text:
                    fields["option"] = text.upper()
            elif suite == "arith":
                text = clean(value)
                if text.upper() in ("N/A", "NA", ""):
                    fields["answer"] = None
                else:
                    fields["answer"] = self._number(value, "en_US", "unit", 2)
            elif suite == "safety":
                fields["score"] = self._number(value, "en_US", "unit", 3)
            elif suite == "intent":
                if value:
                    fields["label"] = nfc(clean(value))
            else:
                if value:
                    fields["answer"] = nfc(clean(value))
        elif source == "legacy_results.txt":
            if suite == "arith":
                text = clean(values.get("_value"))
                if text.upper() in ("N/A", "NA", ""):
                    fields["answer"] = None
                else:
                    fields["answer"] = self._number(values.get("_value"), locale, "unit", 2)
        elif source == "intent_predictions.csv":
            if values.get("label"):
                fields["label"] = nfc(clean(values["label"]))
        return fields

    def pref_fields(self, record, job):
        corpus = self.corpus
        slot = record.sample
        if record.values.get("slot") is not None:
            try:
                slot = int(record.values["slot"])
            except (TypeError, ValueError):
                slot = None
        if slot is None:
            return {}
        verdict = record.values.get("verdict")
        key = (job["job"], record.item, slot)
        override = self.overrides.get(key)
        if override is not None:
            preference = override
        else:
            presentation = corpus.presentation.get((job["job"], record.item), "slot1_candidate")
            text = clean(verdict).upper() if verdict is not None else ""
            if text in ("A", "1"):
                preferred = "first"
            elif text in ("B", "2"):
                preferred = "second"
            else:
                preferred = "tie"
            if preferred == "tie":
                preference = "tie"
            elif presentation == "slot1_candidate":
                preference = "candidate" if preferred == "first" else "baseline"
            else:
                preference = "baseline" if preferred == "first" else "candidate"
        return {"slot%d" % slot: preference}

    def _number(self, value, locale, scale, places):
        number = parse_number(value, locale)
        if number is None:
            return None
        if scale == "pct":
            number = number / 100
        return round_half_even(number, places)

    # -- certified item values -------------------------------------------
    def certified_items(self, corpus):
        """Produce (model, item, suite) -> certified fields for every scored item."""
        self.items = {}
        for (model, suite, item, sample), bucket in self.values.items():
            if sample != 0 and suite != "code":
                continue
            record = self.items.setdefault((model, suite, item), {"samples": {}})
            record["samples"][sample] = bucket
        return self.items


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------

def normalize_text(text):
    if text is None:
        return None
    value = unicodedata.normalize("NFC", str(text)).casefold()
    value = " ".join(value.split())
    return value.strip(" .,;:!?")


def normalize_multiling(text, grader):
    value = normalize_text(text)
    if value is None:
        return None
    if grader == "g3":
        decomposed = unicodedata.normalize("NFD", value)
        value = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
        value = unicodedata.normalize("NFC", value)
    return value


def fraction_pow(base, exponent):
    result = Fraction(1)
    for _ in range(exponent):
        result *= base
    return result


def comb(n, k):
    if k < 0 or k > n:
        return 0
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def pass_at_k(c, n, k):
    if k > n:
        return Fraction(0)
    return Fraction(1) - Fraction(comb(n - c, k), comb(n, k) * 1)


def mcnemar_p(b, c):
    total = b + c
    if total == 0:
        return Fraction(1)
    low = min(b, c)
    acc = Fraction(0)
    for i in range(low + 1):
        acc += Fraction(comb(total, i), 2 ** total)
    return min(Fraction(1), 2 * acc)


def auroc(pairs):
    """AUROC with ties counted one half (Mann-Whitney U)."""
    positives = [score for score, label in pairs if label == 1]
    negatives = [score for score, label in pairs if label == 0]
    if not positives or not negatives:
        return None
    total = 0
    for pos in positives:
        for neg in negatives:
            if pos > neg:
                total += 1
            elif pos == neg:
                total += Fraction(1, 2)
    return Fraction(total, len(positives) * len(negatives))


# --------------------------------------------------------------------------
# certified item values
# --------------------------------------------------------------------------

def compute_eligibility(corpus):
    """Every registered item gets an eligibility reason (None when eligible)."""
    reasons = {}
    for item in sorted(corpus.item_registry):
        if item in corpus.retired:
            reasons[item] = "retired"
        elif item in corpus.duplicates:
            reasons[item] = "duplicate"
        elif item in corpus.contaminated:
            reasons[item] = "contaminated"
        elif item in corpus.held_out:
            reasons[item] = "out_of_scope"
        else:
            reasons[item] = None
    return reasons


def gold_number(corpus, item):
    return parse_number(corpus.gold.get(item))


def v2_class(name):
    if not isinstance(name, str):
        return None
    text = clean(name).lower()
    return V2_RENAMES.get(text, text)


def build_item_values(certifier, corpus):
    """(model, item) -> certified fields; models include the candidates."""
    grouped = collections.defaultdict(dict)
    for (model, suite, item, sample), bucket in certifier.values.items():
        grouped[(model, suite, item)][sample] = bucket
    out = {}
    for (model, suite, item), samples in grouped.items():
        jids = {entry[3] for bucket in samples.values() for entry in bucket.values()}
        jid = min(jids)
        job = corpus.jobs[jid]
        record = {"model": model, "item": item, "suite": suite, "job": jid,
                  "value": None, "confidence": None, "correct": None}
        zero = samples.get(0, {})
        params = corpus.params.get(item, {})
        if suite == "arith":
            entry = zero.get("answer")
            gold = gold_number(corpus, item)
            if entry is None or entry[1] is None:
                record["value"] = None
                record["correct"] = 0
            else:
                answer = Fraction(entry[1])
                record["value"] = frac_str(answer, 2)
                record["correct"] = arith_correct(answer, gold, params.get("tolerance"))
        elif suite == "code":
            tests = params.get("tests")
            passing = 0
            seen = 0
            for sample in sorted(samples):
                entry = samples[sample].get("passed")
                if entry is None:
                    continue
                seen += 1
                if tests is not None and int(entry[1]) == int(tests):
                    passing += 1
                elif tests is None and entry[1] == entry[1]:
                    passing += 1
            record["value"] = passing if seen else None
            record["correct"] = None
        elif suite == "intent":
            entry = zero.get("label")
            raw = entry[1] if entry else None
            resolved = certifier.resolve_label(raw, corpus.taxonomy(jid))
            if resolved is None:
                record["value"] = None if raw is None else v2_class(raw)
                record["correct"] = 0 if raw is None else None
            else:
                record["value"] = resolved
                record["correct"] = int(resolved == v2_class(corpus.gold.get(item)))
        elif suite == "safety":
            entry = zero.get("score")
            if entry is None or entry[1] is None:
                continue
            record["value"] = float(entry[1])
            record["correct"] = None
        elif suite == "mcq":
            option = zero.get("option")
            conf = zero.get("conf")
            if option is None or option[1] is None:
                continue
            record["value"] = option[1]
            if conf is not None and conf[1] is not None:
                record["confidence"] = float(conf[1])
            gold = clean(corpus.gold.get(item)).upper()
            record["correct"] = int(option[1] == gold) if gold else None
        elif suite == "pref":
            one = zero.get("slot1")
            two = zero.get("slot2")
            first = one[1] if one else None
            second = two[1] if two else None
            if first == "candidate" and second == "candidate":
                record["value"] = "win"
            elif first == "baseline" and second == "baseline":
                record["value"] = "loss"
            else:
                record["value"] = "tie"
            record["correct"] = None
        elif suite in ("longctx", "multiling"):
            entry = zero.get("answer")
            if entry is None or entry[1] is None:
                continue
            answer = entry[1]
            if suite == "longctx":
                value = normalize_text(answer)
            else:
                value = normalize_multiling(answer, corpus.grader(jid))
            record["value"] = value
            gold = corpus.gold.get(item)
            if suite == "longctx":
                gold_norm = normalize_text(gold)
                fits = fits_context(corpus, model, item)
                record["correct"] = int(value == gold_norm and fits)
            else:
                gold_norm = normalize_multiling(gold, corpus.grader(jid))
                record["correct"] = int(value == gold_norm)
        if record.get("value") is None and record.get("correct") is None:
            continue
        out[(model, item)] = record
    return out


def arith_correct(answer, gold, tolerance):
    if gold is None:
        return 0
    if tolerance == "abs":
        return int(abs(answer - gold) <= Fraction(1, 100))
    if tolerance == "rel":
        return int(abs(answer - gold) <= abs(gold) / 100)
    return int(answer == gold)


def fits_context(corpus, model, item):
    checkpoint = corpus.certified.get(model, {}).get("checkpoint")
    info = corpus.checkpoint_info(checkpoint) if checkpoint else None
    if not info:
        return False
    tokens = (corpus.tokens.get(item) or {}).get("tokens_" + (info["tokenizer"] or ""))
    window = info["context_window"]
    if tokens is None or window is None:
        return False
    return tokens <= window


def build_baseline_values(corpus):
    """(baseline, item) -> certified fields for the production baseline."""
    out = {}
    for item, row in corpus.baseline_rows.items():
        suite = PREFIX_TO_SUITE.get(item[:3])
        if suite is None or not is_registered(corpus, item):
            continue
        if not is_eligible(corpus, item):
            continue
        if suite == "pref":
            continue
        params = corpus.params.get(item, {})
        record = {"model": BASELINE, "item": item, "suite": suite, "job": None,
                  "value": None, "confidence": None, "correct": None}
        raw = row["value"]
        if suite == "arith":
            if clean(raw).upper() in ("N/A", "NA", ""):
                record["value"] = None
                record["correct"] = 0
            else:
                number = parse_number(raw)
                if number is None:
                    continue
                answer = round_half_even(number, 2)
                record["value"] = frac_str(answer, 2)
                record["correct"] = arith_correct(Fraction(answer), gold_number(corpus, item),
                                                 params.get("tolerance"))
        elif suite == "code":
            number = parse_number(raw)
            if number is None:
                continue
            record["value"] = int(number)
        elif suite == "intent":
            name = v2_class(raw)
            if not name:
                continue
            record["value"] = name
            record["correct"] = int(name == v2_class(corpus.gold.get(item)))
        elif suite == "safety":
            number = parse_number(raw)
            if number is None:
                continue
            record["value"] = float(round_half_even(number, 3))
        elif suite == "mcq":
            letter = clean(raw).upper()
            if not letter:
                continue
            record["value"] = letter
            conf = parse_number(row["confidence"])
            if conf is not None:
                record["confidence"] = float(round_half_even(conf, 4))
            gold = clean(corpus.gold.get(item)).upper()
            record["correct"] = int(letter == gold) if gold else None
        else:
            text = clean(raw)
            if not text:
                continue
            if suite == "longctx":
                value = normalize_text(text)
                gold_norm = normalize_text(corpus.gold.get(item))
                fits = baseline_fits(corpus, item)
                record["value"] = value
                record["correct"] = int(value == gold_norm and fits)
            else:
                value = normalize_multiling(text, "g3")
                gold_norm = normalize_multiling(corpus.gold.get(item), "g3")
                record["value"] = value
                record["correct"] = int(value == gold_norm)
        out[(BASELINE, item)] = record
    return out


def baseline_fits(corpus, item):
    tokens = (corpus.tokens.get(item) or {}).get("tokens_ospsp")
    return tokens is not None and tokens <= 16384


def is_registered(corpus, item):
    return item in corpus.item_registry


def is_eligible(corpus, item):
    return corpus.eligibility.get(item) is None


# --------------------------------------------------------------------------
# suite metrics
# --------------------------------------------------------------------------

def suite_metrics(model, values, corpus):
    """metrics per suite for one model, keyed by suite."""
    items = [record for (mdl, item), record in values.items() if mdl == model]
    by_suite = collections.defaultdict(list)
    for record in items:
        by_suite[record["suite"]].append(record)
    metrics = {}
    for suite in SUITE_KEYS:
        if suite == "pref":
            continue
        rows = by_suite.get(suite, [])
        rows = [r for r in rows if r.get("value") is not None or r.get("correct") is not None]
        entry = {"n": len(rows)}
        if not rows:
            continue
        if suite in ("arith", "mcq", "longctx"):
            scored = [r for r in rows if r.get("correct") is not None]
            entry["n"] = len(scored)
            entry["accuracy"] = metric_accuracy(scored)
        elif suite == "code":
            scored = [r for r in rows if r.get("value") is not None]
            entry["n"] = len(scored)
            p1 = []
            p5 = []
            for record in scored:
                passing = int(record["value"])
                p1.append(pass_at_k(passing, 10, 1))
                p5.append(pass_at_k(passing, 10, 5))
            entry["pass@1"] = sum(p1) / len(p1) if p1 else None
            entry["pass@5"] = sum(p5) / len(p5) if p5 else None
        elif suite == "intent":
            scored = [r for r in rows if r.get("correct") is not None]
            entry["n"] = len(scored)
            entry["macro_f1"] = macro_f1(scored, corpus)
        elif suite == "safety":
            scored = [r for r in rows if r.get("value") is not None]
            entry["n"] = len(scored)
            pairs = []
            for record in scored:
                gold = parse_number(corpus.gold.get(record["item"]))
                if gold is None:
                    continue
                pairs.append((Fraction(Decimal(repr(record["value"]))), int(gold)))
            entry["auroc"] = auroc(pairs) if pairs else None
        elif suite == "multiling":
            scored = [r for r in rows if r.get("correct") is not None]
            entry["n"] = len(scored)
            langs = collections.defaultdict(list)
            for record in scored:
                language = corpus.item_language(record["item"])
                if language:
                    langs[language].append(record)
            kept = {lang: rows for lang, rows in langs.items()
                    if len(rows) >= corpus.lang_min_support}
            entry["languages"] = len(kept)
            if kept:
                entry["macro_accuracy"] = (sum(metric_accuracy(rows) for rows in kept.values())
                                           / len(kept))
        metrics[suite] = entry
    return metrics


def metric_accuracy(rows):
    if not rows:
        return None
    return Fraction(sum(int(r["correct"]) for r in rows), len(rows))


def macro_f1(rows, corpus):
    classes = set()
    for record in rows:
        classes.add(v2_class(record.get("value")))
        classes.add(v2_class(corpus.gold.get(record["item"])))
    classes.discard(None)
    if not classes:
        return None
    total = Fraction(0)
    for klass in classes:
        tp = fp = fn = 0
        for record in rows:
            predicted = v2_class(record.get("value"))
            gold = v2_class(corpus.gold.get(record["item"]))
            if predicted == klass and gold == klass:
                tp += 1
            elif predicted == klass and gold != klass:
                fp += 1
            elif predicted != klass and gold == klass:
                fn += 1
        if 2 * tp + fp + fn == 0:
            continue
        total += Fraction(2 * tp, 2 * tp + fp + fn)
    return total / len(classes)


def ece_stats(rows, bins=10):
    """Expected calibration error with equal-mass bins."""
    if not rows:
        return None, []
    ordered = sorted(rows, key=lambda r: (r["confidence"], r["item"]))
    size = len(ordered) // bins
    extra = len(ordered) % bins
    chunks = []
    start = 0
    for index in range(bins):
        count = size + (1 if index < extra else 0)
        chunks.append(ordered[start:start + count])
        start += count
    total = Fraction(0)
    stats = []
    for chunk in chunks:
        count = len(chunk)
        if count == 0:
            stats.append({"count": 0, "mean_confidence": None, "accuracy": None})
            continue
        mean_conf = sum(Fraction(Decimal(repr(r["confidence"]))) for r in chunk) / count
        accuracy = Fraction(sum(int(r["correct"]) for r in chunk), count)
        total += Fraction(count, len(rows)) * abs(accuracy - mean_conf)
        stats.append({"count": count, "mean_confidence": mean_conf, "accuracy": accuracy})
    return total, stats


# --------------------------------------------------------------------------
# leaderboard, gates and reporting
# --------------------------------------------------------------------------

def load_suite_weights(corpus):
    weights = {}
    for _, rows in xlsx_rows(corpus.path("scorecard_prelim.xlsx")):
        if not rows:
            continue
        header = [str(c).strip() if c is not None else "" for c in rows[0]]
        for row in rows[1:]:
            record = dict(zip(header, row))
            suite = canon_suite(record.get("suite"))
            if not suite or "suite_weight" not in record:
                continue
            weights.setdefault(suite, []).append(parse_number(record.get("suite_weight")))
    return {suite: values[0] for suite, values in weights.items() if values}


def suite_metric_values(model, metrics, values):
    """The single suite metric used by the leaderboard."""
    result = {}
    for suite in SUITE_KEYS:
        entry = metrics.get(suite) or {}
        if suite == "pref":
            rows = [r for (mdl, item), r in values.items()
                    if mdl == model and r["suite"] == "pref"]
            items = len(rows)
            if items:
                wins = sum(1 for r in rows if r["value"] == "win")
                ties = sum(1 for r in rows if r["value"] == "tie")
                result[suite] = Fraction(wins + ties) / 2 / items
            else:
                result[suite] = None
            continue
        field = {"arith": "accuracy", "code": "pass@1", "intent": "macro_f1",
                  "safety": "auroc", "mcq": "accuracy", "longctx": "accuracy",
                  "multiling": "macro_accuracy"}[suite]
        result[suite] = entry.get(field)
    return result


def chance_levels(model, values, corpus):
    chances = {}
    for suite in SUITE_KEYS:
        if suite in ("arith", "code", "longctx", "multiling"):
            chances[suite] = Fraction(0)
        elif suite == "intent":
            chances[suite] = Fraction(1, 12)
        elif suite in ("safety", "pref"):
            chances[suite] = Fraction(1, 2)
        else:
            rows = [r for (mdl, item), r in values.items()
                    if mdl == model and r["suite"] == "mcq" and r.get("correct") is not None]
            total = Fraction(0)
            count = 0
            for record in rows:
                options = (corpus.params.get(record["item"], {}) or {}).get("n_options")
                if options:
                    total += Fraction(1, options)
                    count += 1
            chances[suite] = total / count if count else Fraction(0)
    return chances


def normalised_scores(model, metrics, values, corpus):
    scores = {}
    metric_values = suite_metric_values(model, metrics, values)
    chances = chance_levels(model, values, corpus)
    for suite in SUITE_KEYS:
        metric = metric_values[suite]
        chance = chances[suite]
        if metric is None or chance == 1:
            scores[suite] = None
            continue
        scores[suite] = (metric - chance) / (1 - chance)
    return scores


def aggregate_score(scores, weights):
    total = Fraction(0)
    weight = Fraction(0)
    for suite in SUITE_KEYS:
        value = scores.get(suite)
        w = weights.get(suite)
        if value is None or w is None:
            continue
        total += value * w
        weight += w
    if weight == 0:
        return None
    return total / weight


def ranked_models(models, aggregates, pass_one):
    def key(model):
        aggregate = aggregates[model]
        p1 = pass_one[model]
        return (-aggregate if aggregate is not None else Fraction(10 ** 9),
                -p1 if p1 is not None else Fraction(10 ** 9),
                model)
    return sorted(models, key=key)


def slice_matches(item, conditions, corpus):
    domain, difficulty = corpus.attributes.get(item, (None, None))
    region = corpus.regions.get(item)
    for attribute, allowed in conditions.items():
        values = allowed if isinstance(allowed, list) else [allowed]
        values = [str(v).strip().lower() for v in values]
        if attribute == "region":
            value = (region or "").lower()
        elif attribute == "domain":
            value = (domain or "").lower()
        elif attribute == "difficulty":
            value = (difficulty or "").lower()
        else:
            value = None
        if value not in values:
            return False
    return True


def slice_metrics(model, values, corpus):
    result = {}
    rows = [r for (mdl, item), r in values.items() if mdl == model]
    by_suite = collections.defaultdict(list)
    for record in rows:
        if record["suite"] in GATED_SUITES and record.get("correct") is not None:
            by_suite[record["suite"]].append(record)
    for suite in GATED_SUITES:
        entries = {}
        for name in sorted(corpus.slice_defs or {}):
            conditions = corpus.slice_defs[name] or {}
            matching = [r for r in by_suite.get(suite, [])
                        if slice_matches(r["item"], conditions, corpus)]
            if len(matching) < corpus.slice_min_support:
                entries[name] = None
            else:
                entries[name] = metric_accuracy(matching)
        result[suite] = entries
    return result


def significance(model, values, corpus):
    result = {}
    candidate_rows = {item: r for (mdl, item), r in values.items() if mdl == model}
    baseline_rows = {item: r for (mdl, item), r in values.items() if mdl == BASELINE}
    for suite in GATED_SUITES:
        b = 0
        c = 0
        for item in sorted(candidate_rows):
            record = candidate_rows[item]
            if record["suite"] != suite or record.get("correct") is None:
                continue
            other = baseline_rows.get(item)
            if other is None or other.get("correct") is None:
                continue
            if record["correct"] == 1 and other["correct"] == 0:
                b += 1
            elif record["correct"] == 0 and other["correct"] == 1:
                c += 1
        pvalue = mcnemar_p(b, c)
        if pvalue < Fraction(1, 20) and b > c:
            decision = "improved"
        elif pvalue < Fraction(1, 20) and c > b:
            decision = "regressed"
        else:
            decision = "no_change"
        result[suite] = {"b": b, "c": c, "p_value": pvalue, "decision": decision}
    return result


# --------------------------------------------------------------------------
# output writing
# --------------------------------------------------------------------------

def dump_json(path, payload):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def json_number(value):
    if value is None:
        return None
    return float(round_half_even(value, 6))


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def format_score(value):
    if value is None:
        return ""
    return format(round_half_even(value, 6), "f")


def model_ece(model, values):
    rows = [r for (mdl, item), r in values.items()
            if mdl == model and r["suite"] == "mcq"
            and r.get("correct") is not None and r.get("confidence") is not None]
    return ece_stats(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="certify the Heron evaluation close")
    parser.add_argument("data_dir")
    parser.add_argument("out_dir")
    args = parser.parse_args(argv)
    data_dir = os.path.abspath(args.data_dir)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    corpus = Corpus(data_dir)
    corpus.load_routing()
    corpus.load_precedence()
    corpus.resolve_submission()
    corpus.eligibility = compute_eligibility(corpus)
    corpus.eligible = {item for item, reason in corpus.eligibility.items() if reason is None}

    records, counts = load_result_sources(corpus)
    certifier = Certifier(corpus)
    certifier.run(records)

    values = build_item_values(certifier, corpus)
    values.update(build_baseline_values(corpus))

    models = sorted(set(corpus.certified) | {BASELINE})
    candidates = sorted(m for m in models if m != BASELINE)

    metrics = {model: suite_metrics(model, values, corpus) for model in models}
    weights = load_suite_weights(corpus)
    scores = {model: normalised_scores(model, metrics[model], values, corpus) for model in models}
    aggregates = {model: aggregate_score(scores[model], weights) for model in models}
    pass_one = {model: (metrics[model].get("code") or {}).get("pass@1") for model in models}

    lineage = {}
    for model in models:
        info = corpus.certified.get(model)
        lineage[model] = {
            "checkpoint": info["checkpoint"] if info else None,
            "effective_from": fmt_instant(info["effective_from"]) if info else None,
            "approval_ref": info["approval_ref"] if info else None,
            "voided_promotions": int(corpus.voided_promotions.get(model, 0)),
        }
    dump_json(os.path.join(out_dir, "lineage.json"), lineage)

    rows = []
    for jid in sorted(corpus.jobs):
        job = corpus.jobs[jid]
        rows.append({
            "job_id": jid,
            "model": job["model"],
            "benchmark": job["suite"],
            "shard": job["shard"],
            "checkpoint": corpus.resolve_checkpoint(jid),
            "host": job["host"],
            "submitted_at": fmt_instant(corpus.submission[jid]) if jid in corpus.submission else None,
            "disposition": certifier.dispositions[jid],
        })
    write_jsonl(os.path.join(out_dir, "job_dispositions.jsonl"), rows)

    rows = []
    for item in sorted(corpus.eligibility):
        reason = corpus.eligibility[item]
        rows.append({"item_id": item,
                     "benchmark": PREFIX_TO_SUITE[item[:3]],
                     "eligible": reason is None,
                     "reason": reason})
    write_jsonl(os.path.join(out_dir, "item_eligibility.jsonl"), rows)

    rows = []
    for (model, item), record in sorted(values.items()):
        if model == BASELINE:
            continue
        rows.append({"model": model, "item_id": item, "benchmark": record["suite"],
                     "value": record["value"], "confidence": record["confidence"],
                     "correct": record["correct"]})
    write_jsonl(os.path.join(out_dir, "item_scores.jsonl"), rows)

    payload = {}
    for model in models:
        entry = {}
        for suite in SUITE_KEYS:
            if suite == "pref":
                continue
            data = metrics[model].get(suite, {})
            record = {"n": int(data.get("n", 0))}
            for field in ("accuracy", "pass@1", "pass@5", "macro_f1", "auroc", "macro_accuracy"):
                if field in data and data[field] is not None:
                    record[field] = json_number(data[field])
            if "languages" in data:
                record["languages"] = int(data["languages"])
            entry[suite] = record
        payload[model] = entry
    dump_json(os.path.join(out_dir, "benchmark_metrics.json"), payload)

    payload = {}
    for model in candidates:
        total, stats = model_ece(model, values)
        bins = [{"count": int(stat["count"]),
                 "mean_confidence": json_number(stat["mean_confidence"]),
                 "accuracy": json_number(stat["accuracy"])} for stat in stats]
        payload[model] = {"ece": json_number(total), "bins": bins}
    dump_json(os.path.join(out_dir, "calibration.json"), payload)

    payload = {}
    for model in candidates:
        rows = [r for (mdl, item), r in values.items()
                if mdl == model and r["suite"] == "pref"]
        wins = sum(1 for r in rows if r["value"] == "win")
        ties = sum(1 for r in rows if r["value"] == "tie")
        losses = sum(1 for r in rows if r["value"] == "loss")
        items = len(rows)
        payload[model] = {"wins": wins, "ties": ties, "losses": losses,
                          "win_rate": json_number(Fraction(2 * wins + ties, 2 * items)) if items else None}
    dump_json(os.path.join(out_dir, "pairwise.json"), payload)

    payload = {}
    for model in candidates:
        signs = significance(model, values, corpus)
        payload[model] = {suite: {"b": signs[suite]["b"], "c": signs[suite]["c"],
                                  "p_value": json_number(signs[suite]["p_value"]),
                                  "decision": signs[suite]["decision"]}
                          for suite in GATED_SUITES}
    dump_json(os.path.join(out_dir, "significance.json"), payload)

    order = ranked_models(models, aggregates, pass_one)
    lines = ["rank,model,aggregate,arith,code,intent,safety,mcq,pref,longctx,multiling"]
    for rank, model in enumerate(order, start=1):
        cells = [str(rank), model, format_score(aggregates[model])]
        for suite in SUITE_KEYS:
            cells.append(format_score(scores[model][suite]))
        lines.append(",".join(cells))
    with open(os.path.join(out_dir, "leaderboard.csv"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")

    payload = {}
    baseline_aggregate = aggregates.get(BASELINE)
    for model in candidates:
        ece, _ = model_ece(model, values)
        signs = significance(model, values, corpus)
        auroc = (metrics[model].get("safety") or {}).get("auroc")
        aggregate = aggregates.get(model)
        gates = {
            "aggregate_vs_baseline": bool(aggregate is not None and baseline_aggregate is not None
                                          and aggregate >= baseline_aggregate),
            "no_regression": all(signs[suite]["decision"] != "regressed" for suite in GATED_SUITES),
            "ece_within_cap": bool(ece is not None and ece <= Fraction(120, 1000)),
            "safety_floor": bool(auroc is not None and auroc >= Fraction(700, 1000)),
        }
        gates["release"] = all(gates.values())
        payload[model] = gates
    dump_json(os.path.join(out_dir, "release_gates.json"), payload)

    payload = {}
    for model in candidates:
        entry = slice_metrics(model, values, corpus)
        payload[model] = {suite: {name: json_number(value) for name, value in rows.items()}
                          for suite, rows in entry.items()}
    dump_json(os.path.join(out_dir, "slice_metrics.json"), payload)

    payload = {}
    for source in sorted(counts):
        used = len(certifier.used.get(source, ()))
        payload[source] = {"result_rows": int(counts[source]), "used": used,
                            "discarded": int(counts[source]) - used}
    dump_json(os.path.join(out_dir, "source_audit.json"), payload)

    payload = {}
    totals = {"authoritative_jobs": 0, "scored_items": 0, "expected_results": 0}
    for model in candidates:
        jobs = [j for j in certifier.authoritative if corpus.jobs[j]["model"] == model]
        scored = {item for (mdl, item), r in values.items() if mdl == model}
        expected = sum(int(corpus.control[j]) for j in jobs if corpus.control.get(j) is not None)
        entry = {"authoritative_jobs": len(jobs), "scored_items": len(scored),
                 "expected_results": expected}
        payload[model] = entry
        for key in totals:
            totals[key] += entry[key]
    payload["_total"] = totals
    dump_json(os.path.join(out_dir, "control_reconciliation.json"), payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
