#!/usr/bin/env python3
"""Reference oracle for the LedgerPort settlement drop.

Installs the reusable pipeline the prompt asks for at /app/out/transform.py
and runs it once over the shipped drop. Every rule it applies is written in
/app/data/settlement_contract.md and the policy registers that file names.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

TRANSFORM = r'''#!/usr/bin/env python3
"""Settlement normalization pipeline for the LedgerPort quarter close.

Usage: transform.py [INPUT_DIR] [OUTPUT_DIR]
The INPUT_DIR and OUTPUT_DIR environment variables, then /app/data and
/app/out, are the fallbacks. Implemented from the shipped settlement contract.
"""

import configparser
import csv
import json
import os
import re
import sqlite3
import sys
import tomllib
import xml.etree.ElementTree as ET
import zipfile
import zlib
from bisect import bisect_right
from datetime import date, datetime, timedelta
from decimal import (ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_DOWN,
                     ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP, Decimal)

XL = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
WD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

LEDGER_FIELDS = ("event_id", "event_ts", "customer_id", "sku", "warehouse",
                 "terminal", "kind", "quantity", "unit_price", "currency",
                 "revision", "ref_event")
SHAPES = {
    ("customer_id", "valid_from", "valid_to", "segment", "postal_code"): "party",
    ("postal_prefix", "valid_from", "valid_to", "region"): "zone",
    ("sku", "valid_from", "valid_to", "category", "active"): "item",
    ("sku", "version_id", "valid_from", "valid_to", "list_price_minor", "currency"): "price",
    ("warehouse", "valid_from", "valid_to", "postal_code"): "site",
    ("terminal", "valid_from", "valid_to", "channel_group", "utc_offset_minutes"): "till",
    ("rate_date", "currency", "quote_source", "usd_rate"): "quote",
    ("calendar_date", "region", "variant", "fiscal_week"): "week",
    ("legacy_code", "code_kind", "current_code"): "alias",
    ("voided_event_id",): "void",
}
ROUNDERS = {"half_even": ROUND_HALF_EVEN, "half_up": ROUND_HALF_UP,
            "half_down": ROUND_HALF_DOWN, "floor": ROUND_FLOOR,
            "ceiling": ROUND_CEILING, "up": ROUND_UP, "down": ROUND_DOWN}
SIGNS = {"sale": 1, "refund": -1, "fee": 1, "credit": -1}
LINE_KINDS = ("sale", "refund")
ZONES = ("central", "east", "north", "south", "west")
TIERS = ("consumer", "corporate", "enterprise", "smb")
EPOCH = datetime(1970, 1, 1)
SERIAL_ZERO = datetime(1899, 12, 30)
TOP_N = 5
KEEP = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")


# ------------------------------------------------------------------ containers

def slurp(path, encoding):
    handle = open(path, "rb")
    blob = handle.read()
    handle.close()
    if encoding == "utf-8-sig" or blob[:3] == b"\xef\xbb\xbf":
        return blob.decode("utf-8-sig")
    return blob.decode(encoding, errors="replace")


def grid_from_separated(path, encoding, sep):
    body = []
    for line in slurp(path, encoding).splitlines():
        if line and not line.startswith("#"):
            body.append(line)
    cells = list(csv.reader(body, delimiter=sep))
    return [(cells[0], cells[1:])] if cells else []


def grid_from_jsonl(path, encoding):
    keys = None
    out = []
    for line in slurp(path, encoding).splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if len(item) == 1 and "_note" in item:
            continue
        if keys is None:
            keys = list(item)
        out.append([item.get(k, "") for k in keys])
    return [(keys, out)] if keys else []


def grid_from_json(path, encoding):
    doc = json.loads(slurp(path, encoding))
    keys = doc["columns"]
    return [(keys, [[r.get(k, "") for k in keys] for r in doc["rows"]])]


def grid_from_xml(path, encoding):
    tree = ET.fromstring(slurp(path, encoding))
    keys = None
    out = []
    for node in tree.iter("row"):
        pairs = [(kid.tag, kid.text or "") for kid in node]
        if keys is None:
            keys = [t for t, _ in pairs]
        seen = dict(pairs)
        out.append([seen.get(k, "") for k in keys])
    return [(keys, out)] if keys else []


def grid_from_parquet(path):
    import pyarrow.parquet as pq

    tab = pq.read_table(path)
    keys = list(tab.column_names)
    cols = [tab.column(k).to_pylist() for k in keys]
    return [(keys, [list(v) for v in zip(*cols)] if cols else [])]


def grid_from_db(path):
    link = sqlite3.connect("file:" + path + "?mode=ro", uri=True)
    out = []
    names = [r[0] for r in link.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    for name in names:
        cur = link.execute('SELECT * FROM "%s"' % name)
        keys = [c[0] for c in cur.description]
        out.append((keys, [["" if v is None else str(v) for v in r]
                           for r in cur.fetchall()]))
    link.close()
    return out


def grid_from_xlsx(path):
    archive = zipfile.ZipFile(path)
    book = ET.fromstring(archive.read("xl/workbook.xml"))
    links = {}
    for node in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")):
        links[node.attrib["Id"]] = node.attrib["Target"]
    out = []
    for position, node in enumerate(book.iter(XL + "sheet"), start=1):
        target = links.get(node.attrib.get(REL + "id"),
                           "worksheets/sheet%d.xml" % position)
        page = ET.fromstring(archive.read("xl/" + target.lstrip("/")))
        grid = []
        for line in page.iter(XL + "row"):
            cells = []
            for cell in line.iter(XL + "c"):
                spot = cell.find(XL + "is/" + XL + "t")
                if spot is None:
                    spot = cell.find(XL + "v")
                cells.append("" if spot is None or spot.text is None else spot.text)
            grid.append(cells)
        if grid:
            out.append((grid[0], grid[1:]))
    archive.close()
    return out


def grid_from_docx(path):
    archive = zipfile.ZipFile(path)
    tree = ET.fromstring(archive.read("word/document.xml"))
    archive.close()
    grid = []
    for line in tree.iter(WD + "tr"):
        grid.append(["".join(bit.text or "" for bit in box.iter(WD + "t"))
                     for box in line.iter(WD + "tc")])
    return [(grid[0], grid[1:])] if grid else []


def grid_from_pdf(path):
    handle = open(path, "rb")
    blob = handle.read()
    handle.close()
    spoken = []
    for chunk in re.finditer(rb"<<[^<>]*/Length\s+(\d+)[^<>]*>>\s*stream\r?\n", blob):
        size = int(chunk.group(1))
        payload = blob[chunk.end():chunk.end() + size]
        try:
            payload = zlib.decompress(payload)
        except zlib.error:
            pass
        for shown in re.finditer(rb"\((.*?)\) Tj", payload, re.S):
            text = shown.group(1).replace(b"\\(", b"(")
            text = text.replace(b"\\)", b")").replace(b"\\\\", b"\\")
            spoken.append(text.decode("latin-1"))
    keys = None
    out = []
    for line in spoken:
        if " | " not in line:
            continue
        bits = [b.strip() for b in line.split(" | ")]
        if keys is None:
            keys = bits
        elif bits != keys:
            out.append(bits)
    return [(keys, out)] if keys else []


def pipe_grids(text):
    out = []
    block = None
    for line in text.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("|") and trimmed.endswith("|"):
            bits = [b.strip() for b in trimmed.strip("|").split("|")]
            if all(b and set(b) <= set("-: ") for b in bits):
                continue
            block = (block or [])
            block.append(bits)
        elif block:
            out.append((block[0], block[1:]))
            block = None
    if block:
        out.append((block[0], block[1:]))
    return out


def grid_from_md(path, encoding):
    return pipe_grids(slurp(path, encoding))


def untag(text):
    for src, dst in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&amp;", "&")):
        text = text.replace(src, dst)
    return text.strip()


def grid_from_html(path, encoding):
    out = []
    for block in re.findall(r"<table.*?</table>", slurp(path, encoding), re.S | re.I):
        grid = []
        for line in re.findall(r"<tr.*?</tr>", block, re.S | re.I):
            grid.append([untag(c) for c in
                         re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", line, re.S | re.I)])
        if grid:
            out.append((grid[0], grid[1:]))
    return out


def grid_from_fixed(path, encoding):
    body = [l for l in slurp(path, encoding).splitlines()
            if l and not l.startswith("#")]
    if not body:
        return []
    head = body[0]
    labels = [p for p in re.split(r"\s{2,}", head.strip()) if p]
    edges = []
    at = 0
    for label in labels:
        spot = head.index(label, at)
        edges.append(spot)
        at = spot + len(label)
    spans = list(zip(edges, edges[1:] + [len(head) + 4096]))
    return [([l.lower() for l in labels],
             [[l[a:b].strip() for a, b in spans] for l in body[1:]])]


def grid_from_log(path, encoding):
    keys = None
    out = []
    for line in slurp(path, encoding).splitlines():
        pairs = []
        for token in line.split(" "):
            if "=" not in token:
                continue
            label, _, value = token.partition("=")
            if label == "seq":
                continue
            pairs.append((label, "" if value == "-" else value.replace("\u00a0", " ")))
        if not pairs:
            continue
        if keys is None:
            keys = [k for k, _ in pairs]
        seen = dict(pairs)
        out.append([seen.get(k, "") for k in keys])
    return [(keys, out)] if keys else []


def ini_doc(path, encoding):
    reader = configparser.ConfigParser(interpolation=None)
    reader.optionxform = str
    reader.read_string(slurp(path, encoding))
    return reader


def grid_from_ini(path, encoding):
    reader = ini_doc(path, encoding)
    keys = None
    out = []
    for block in reader.sections():
        if not block.startswith("row."):
            continue
        pairs = list(reader.items(block))
        if keys is None:
            keys = [k for k, _ in pairs]
        seen = dict(pairs)
        out.append([seen.get(k, "") for k in keys])
    return [(keys, out)] if keys else []


def toml_doc(path):
    handle = open(path, "rb")
    try:
        return tomllib.load(handle)
    finally:
        handle.close()


def grid_from_toml(path):
    rows = toml_doc(path).get("lines", [])
    if not rows:
        return []
    keys = list(rows[0])
    return [(keys, [[str(r.get(k, "")) for k in keys] for r in rows])]


def strip_quote(text):
    if len(text) > 1 and text[0] == '"' and text[-1] == '"':
        return text[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return text


def yaml_doc(path, encoding):
    """Mapping blocks and the `lines` list of this drop, as plain dicts."""
    blocks = {}
    rows = []
    keys = None
    where = None
    under = None
    item = None
    for raw in slurp(path, encoding).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        depth = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if depth == 0:
            where = line.rstrip(":")
            under = None
            if where != "lines":
                blocks[where] = {}
            continue
        if where == "lines":
            if line.startswith("- "):
                if item:
                    rows.append(item)
                item = {}
                line = line[2:]
            label, _, value = line.partition(":")
            item[label.strip()] = strip_quote(value.strip())
            if keys is None or len(item) > len(keys):
                keys = list(item)
            continue
        label, _, value = line.partition(":")
        label, value = label.strip(), value.strip()
        if depth == 2:
            if value:
                under = None
                blocks[where][label] = strip_quote(value)
            else:
                under = label
                blocks[where][label] = {}
        elif under is not None:
            blocks[where][under][label] = strip_quote(value)
    if item:
        rows.append(item)
    grids = [(keys, [[r.get(k, "") for k in keys] for r in rows])] if keys else []
    return blocks, grids


def grid_from_mbox(path, encoding):
    keys = None
    out = []
    for chunk in re.split(r"(?m)^From .*$", slurp(path, encoding)):
        halves = chunk.split("\n\n", 1)
        if len(halves) < 2:
            continue
        pairs = []
        for line in halves[1].splitlines():
            if ":" in line:
                label, _, value = line.partition(":")
                pairs.append((label.strip(), value.strip()))
        if not pairs:
            continue
        if keys is None:
            keys = [k for k, _ in pairs]
        seen = dict(pairs)
        out.append([seen.get(k, "") for k in keys])
    return [(keys, out)] if keys else []


def grid_from_ics(path, encoding):
    keys = None
    out = []
    item = None
    for line in slurp(path, encoding).replace("\r\n", "\n").split("\n"):
        if line == "BEGIN:VEVENT":
            item = {}
        elif line == "END:VEVENT":
            if item:
                if keys is None:
                    keys = list(item)
                out.append([item.get(k, "") for k in keys])
            item = None
        elif item is not None and line.startswith("X-"):
            label, _, value = line.partition(":")
            item[label[2:].lower().replace("-", "_")] = value
    return [(keys, out)] if keys else []


def grids_of(path, encoding):
    tail = path.rsplit(".", 1)[-1].lower()
    if tail == "csv":
        return grid_from_separated(path, encoding, ",")
    if tail == "tsv":
        return grid_from_separated(path, encoding, "\t")
    if tail == "jsonl":
        return grid_from_jsonl(path, encoding)
    if tail == "json":
        return grid_from_json(path, encoding)
    if tail == "xml":
        return grid_from_xml(path, encoding)
    if tail == "parquet":
        return grid_from_parquet(path)
    if tail == "db":
        return grid_from_db(path)
    if tail == "xlsx":
        return grid_from_xlsx(path)
    if tail == "docx":
        return grid_from_docx(path)
    if tail == "pdf":
        return grid_from_pdf(path)
    if tail == "md":
        return grid_from_md(path, encoding)
    if tail == "html":
        return grid_from_html(path, encoding)
    if tail == "txt":
        return grid_from_fixed(path, encoding)
    if tail == "log":
        return grid_from_log(path, encoding)
    if tail == "ini":
        return grid_from_ini(path, encoding)
    if tail == "toml":
        return grid_from_toml(path)
    if tail == "yaml":
        return yaml_doc(path, encoding)[1]
    if tail == "mbox":
        return grid_from_mbox(path, encoding)
    if tail == "ics":
        return grid_from_ics(path, encoding)
    return []


# ------------------------------------------------------------------- policy

def read_policy(root):
    profiles = yaml_doc(os.path.join(root, "postal_region_supplement.yaml"),
                        "utf-8")[0]["source_profiles"]
    scopes = yaml_doc(os.path.join(root, "code_crosswalk_supplement.yaml"),
                      "utf-8")[0].get("scope_windows", {})
    money = yaml_doc(os.path.join(root, "price_tier_registry.yaml"), "utf-8")[0]
    cal = yaml_doc(os.path.join(root, "fiscal_calendar_policy.yaml"),
                   "utf-8")[0]["fiscal_calendar"]
    fx = toml_doc(os.path.join(root, "fx_policy_register.toml"))["fx"]
    trade = toml_doc(os.path.join(root, "warehouse_registry.toml"))
    memo = ini_doc(os.path.join(root, "terminal_offsets.ini"), "utf-8")
    bounds = ini_doc(os.path.join(root, "terminal_channel_map.ini"), "utf-8")
    ident = ini_doc(os.path.join(root, "code_crosswalk_overrides.ini"), "utf-8")
    retired = {}
    for keys, rows in grid_from_md(os.path.join(root, "price_policy_notes.md"), "utf-8"):
        if list(keys) == ["retired_source", "superseded_from"]:
            for row in rows:
                retired[row[0]] = row[1]
    ladder = {}
    for label, kind in (("authority_sale", "sale"), ("authority_refund", "refund")):
        for name, rank in trade[label].items():
            ladder.setdefault(name, {})[kind] = int(rank)
    for label, kind in (("authority_fee", "fee"), ("authority_credit", "credit")):
        for name, rank in memo.items(label):
            ladder.setdefault(name, {})[kind] = int(rank)
    glyphs = {}
    for code, latin in ident.items("homoglyphs"):
        glyphs[chr(int(code, 16))] = latin
    return {
        "profiles": profiles,
        "scopes": scopes,
        "retired": retired,
        "ladder": ladder,
        "minor": {k: int(v) for k, v in money["minor_units"].items()},
        "rounding": ROUNDERS[fx["rounding_mode"]],
        "variant": cal["variant"],
        "quote": fx["quote_source"],
        "carry": int(fx["carry_forward_days"]),
        "glyphs": glyphs,
        "window": (bounds.get("settlement_window", "start"),
                   bounds.get("settlement_window", "end_exclusive")),
        "expected_files": int(bounds.get("inventory", "input_file_count")),
    }


# ------------------------------------------------------------- normalisation

def tidy(text, glyphs):
    body = "".join(glyphs.get(ch, ch) for ch in str(text or "")).strip().upper()
    body = "".join(ch for ch in body if ch in KEEP)
    if "-" not in body:
        return body
    head, _, tail = body.partition("-")
    return head + "-" + tail.lstrip("0")


def parse_stamp(text, style):
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("empty stamp")
    if style == "iso":
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    if style == "us_slash":
        return datetime.strptime(raw, "%m/%d/%Y %H:%M:%S")
    if style == "eu_dot":
        return datetime.strptime(raw, "%d.%m.%Y %H:%M:%S")
    if style == "epoch_s":
        return EPOCH + timedelta(seconds=int(raw))
    if style == "epoch_ms":
        return EPOCH + timedelta(milliseconds=int(raw))
    if style == "excel_serial":
        ticks = SERIAL_ZERO + timedelta(days=float(raw))
        return (ticks + timedelta(microseconds=500000)).replace(microsecond=0)
    raise ValueError(style)


def parse_price(text, style, places):
    raw = str(text or "").strip()
    if raw.startswith("(") and raw.endswith(")"):
        raw = raw[1:-1]
    raw = raw.lstrip("+-")
    if not raw:
        raise ValueError("empty price")
    if style == "comma":
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d+)?", raw):
        raise ValueError(raw)
    shifted = Decimal(raw) * (10 ** places)
    if shifted != shifted.to_integral_value():
        raise ValueError(raw)
    return int(shifted)


def whole(text):
    raw = str(text or "").strip()
    if not re.fullmatch(r"\d+", raw):
        raise ValueError(raw)
    return int(raw)


class Spans:
    """Half open effective dated lookup over one keyed registry."""

    def __init__(self, rows, lo=1, hi=2):
        shelf = {}
        for row in rows:
            shelf.setdefault(row[0], []).append(row)
        self.shelf = {}
        for name, bunch in shelf.items():
            bunch.sort(key=lambda r: r[lo])
            self.shelf[name] = ([r[lo] for r in bunch], bunch, lo, hi)

    def on(self, name, day):
        found = self.shelf.get(name)
        if not found:
            return None
        starts, bunch, lo, hi = found
        spot = bisect_right(starts, day) - 1
        if spot < 0:
            return None
        row = bunch[spot]
        return row if row[lo] <= day < row[hi] else None


def gather(root, policy):
    shelves = {label: [] for label in set(SHAPES.values())}
    lines = {}
    names = sorted(n for n in os.listdir(root)
                   if os.path.isfile(os.path.join(root, n)))
    for name in names:
        profile = policy["profiles"].get(name)
        encoding = profile["encoding"] if profile else "utf-8"
        for keys, rows in grids_of(os.path.join(root, name), encoding):
            shape = tuple(keys or ())
            if shape == LEDGER_FIELDS:
                if profile:
                    lines[name] = rows
            elif shape in SHAPES:
                shelves[SHAPES[shape]].extend([list(r) for r in rows])
    return shelves, lines, names


def build(root, policy):
    shelves, lines, names = gather(root, policy)
    glyphs = policy["glyphs"]
    for label in ("party", "zone", "item", "price", "site", "till"):
        for row in shelves[label]:
            row[0] = tidy(row[0], glyphs)
    parties = Spans(shelves["party"])
    zones = Spans(shelves["zone"])
    items = Spans(shelves["item"])
    sites = Spans(shelves["site"])
    tills = Spans(shelves["till"])
    books = {}
    for row in shelves["price"]:
        books.setdefault(row[0], []).append(row)
    for bunch in books.values():
        bunch.sort(key=lambda r: r[2])
    shelf_price = {k: ([r[2] for r in v], v) for k, v in books.items()}
    aliases = {}
    for row in shelves["alias"]:
        aliases[(row[1], tidy(row[0], glyphs))] = tidy(row[2], glyphs)
    weeks = {}
    for row in shelves["week"]:
        if row[2] == policy["variant"]:
            weeks[(row[0], row[1])] = row[3]
    quotes = {}
    for row in shelves["quote"]:
        if row[2] == policy["quote"]:
            quotes[(row[0], row[1])] = row[3]
    dead = set(tidy(row[0], glyphs) for row in shelves["void"])

    minor = policy["minor"]
    mode = policy["rounding"]
    carry = policy["carry"]
    lo_day, hi_day = policy["window"]
    refusals = []
    passing = []

    for name in sorted(lines):
        profile = policy["profiles"][name]
        offset = int(profile["utc_offset_minutes"])
        style = profile["date_style"]
        decimals = profile["decimal_style"]
        stem = name.rsplit(".", 1)[0]
        bound = policy["scopes"].get(stem)
        retire = policy["retired"].get(stem)
        for seat, row in enumerate(lines[name]):
            cell = dict(zip(LEDGER_FIELDS, row))
            kind = str(cell["kind"] or "").strip().lower()
            if not cell["event_id"].strip() or kind not in SIGNS:
                refusals.append((name, "MALFORMED_ROW"))
                continue
            money = str(cell["currency"] or "").strip().upper()
            if not money:
                refusals.append((name, "MALFORMED_ROW"))
                continue
            try:
                stamp = parse_stamp(cell["event_ts"], style)
            except (ValueError, OverflowError):
                refusals.append((name, "MALFORMED_ROW"))
                continue
            try:
                unit = parse_price(cell["unit_price"], decimals, minor.get(money, 2))
            except (ValueError, ArithmeticError):
                refusals.append((name, "MALFORMED_ROW"))
                continue
            try:
                count = whole(cell["quantity"])
            except ValueError:
                refusals.append((name, "NON_NUMERIC_QUANTITY"))
                continue
            if kind not in LINE_KINDS:
                count = 0
            moment = stamp - timedelta(minutes=offset)
            caught = moment.date().isoformat()
            if kind in LINE_KINDS:
                till = tidy(cell["terminal"], glyphs)
                till = aliases.get(("terminal", till), till)
                found = tills.on(till, caught)
                if found is None:
                    refusals.append((name, "UNKNOWN_TERMINAL"))
                    continue
                channel = found[3]
                shift = int(found[4])
            else:
                channel = "contract"
                shift = 0
            if channel == "branch":
                day = (moment + timedelta(minutes=shift)).date().isoformat()
            else:
                day = caught
            if not (lo_day <= day < hi_day):
                refusals.append((name, "OUT_OF_SCOPE"))
                continue
            if bound and not (bound["scope_start"] <= day < bound["scope_end_exclusive"]):
                refusals.append((name, "OUT_OF_SCOPE"))
                continue
            if retire and day >= retire:
                refusals.append((name, "SUPERSEDED_SOURCE"))
                continue
            tag = tidy(cell["event_id"], glyphs)
            if tag in dead:
                refusals.append((name, "VOIDED"))
                continue
            buyer = tidy(cell["customer_id"], glyphs)
            who = parties.on(buyer, day)
            if who is None:
                refusals.append((name, "UNKNOWN_CUSTOMER"))
                continue
            part = tidy(cell["sku"], glyphs)
            part = aliases.get(("sku", part), part)
            what = items.on(part, day)
            if what is None:
                refusals.append((name, "UNKNOWN_SKU"))
                continue
            if what[4] == "N":
                refusals.append((name, "INACTIVE_SKU"))
                continue
            if kind in LINE_KINDS:
                depot = tidy(cell["warehouse"], glyphs)
                depot = aliases.get(("warehouse", depot), depot)
                site = sites.on(depot, day)
                if site is None:
                    refusals.append((name, "UNKNOWN_WAREHOUSE"))
                    continue
                postcode = site[3]
            else:
                postcode = who[4]
            area = zones.on(postcode.split("-")[0], day)
            if area is None:
                refusals.append((name, "UNKNOWN_WAREHOUSE"))
                continue
            if kind in LINE_KINDS:
                label = None
                slot = shelf_price.get(part)
                if slot:
                    starts, bunch = slot
                    spot = bisect_right(starts, day) - 1
                    if spot >= 0 and bunch[spot][2] <= day < bunch[spot][3]:
                        label = bunch[spot][1]
                if label is None:
                    refusals.append((name, "NO_PRICE_VERSION"))
                    continue
            else:
                label = "n/a"
            if money not in minor:
                refusals.append((name, "NO_FX_RATE"))
                continue
            rate = None
            cursor = date(int(day[0:4]), int(day[5:7]), int(day[8:10]))
            for _ in range(carry + 1):
                rate = quotes.get((cursor.isoformat(), money))
                if rate is not None:
                    break
                cursor = cursor - timedelta(days=1)
            if rate is None:
                refusals.append((name, "NO_FX_RATE"))
                continue
            season = weeks.get((day, area[3]))
            if season is None:
                refusals.append((name, "NO_FISCAL_WEEK"))
                continue
            size = count * unit if kind in LINE_KINDS else unit
            native = SIGNS[kind] * size
            cents = int((Decimal(native) / (10 ** minor[money]) * Decimal(rate)
                         * 100).quantize(Decimal(1), rounding=mode))
            passing.append({
                "amount_usd_cents": cents,
                "category": what[3],
                "channel_group": channel,
                "currency": money,
                "customer_id": buyer,
                "event_id": tag,
                "fiscal_week": season,
                "kind": kind,
                "native_amount_minor": native,
                "posting_date": day,
                "price_list_version": label,
                "quantity": count,
                "region": area[3],
                "segment": who[3],
                "sku": part,
                "source_file": name,
                "_rank": policy["ladder"][name][kind],
                "_rev": int(str(cell["revision"]).strip() or 0),
                "_seat": seat,
                "_link": tidy(cell["ref_event"], glyphs) if cell["ref_event"] else "",
            })

    pools = {}
    for rec in passing:
        pools.setdefault(rec["event_id"], []).append(rec)
    winners = []
    clashes = 0
    for tag in sorted(pools):
        bunch = pools[tag]
        if len(bunch) > 1:
            clashes += 1
            bunch = sorted(bunch, key=lambda r: (r["_rank"], -r["_rev"],
                                                 r["source_file"], r["_seat"]))
            for loser in bunch[1:]:
                refusals.append((loser["source_file"], "DUPLICATE_LOWER_AUTHORITY"))
        winners.append(bunch[0])
    winners.sort(key=lambda r: (r["posting_date"], r["event_id"], r["source_file"]))
    standing = {}
    for rec in winners:
        standing[rec["event_id"]] = rec
    gone = set()
    undone = 0
    stray = 0
    for rec in winners:
        if rec["kind"] != "credit" or not rec["_link"] or rec["event_id"] in gone:
            continue
        mark = standing.get(rec["_link"])
        if mark is None or mark["event_id"] in gone or mark is rec:
            gone.add(rec["event_id"])
            refusals.append((rec["source_file"], "REVERSAL_ORPHAN"))
            stray += 1
            continue
        gone.add(rec["event_id"])
        gone.add(mark["event_id"])
        refusals.append((rec["source_file"], "REVERSED"))
        refusals.append((mark["source_file"], "REVERSED"))
        undone += 1
    book = [r for r in winners if r["event_id"] not in gone]
    ledger = []
    for seat, rec in enumerate(book, start=1):
        rec["ledger_index"] = seat
        ledger.append({k: v for k, v in rec.items() if k[0] != "_"})
    return assemble(policy, names, lines, ledger, refusals, clashes, undone, stray)


# ---------------------------------------------------------------- deliverables

def sums(rows, field):
    tally = {}
    for rec in rows:
        tally[rec[field]] = tally.get(rec[field], 0) + rec["amount_usd_cents"]
    return dict(sorted(tally.items()))


def moved(rec):
    if rec["kind"] == "sale":
        return rec["quantity"]
    if rec["kind"] == "refund":
        return -rec["quantity"]
    return 0


def slice_of(field, name, rows):
    mine = [r for r in rows if r[field] == name]
    heads = {}
    for rec in mine:
        heads[rec["customer_id"]] = heads.get(rec["customer_id"], 0) + rec["amount_usd_cents"]
    best = sorted(heads.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]
    return {
        field: name,
        "by_category": sums(mine, "category"),
        "by_channel_group": sums(mine, "channel_group"),
        "by_kind": sums(mine, "kind"),
        "customer_count": len(heads),
        "net_units": sum(moved(r) for r in mine),
        "record_count": len(mine),
        "top_customers": [{"customer_id": k, "total_usd_cents": v} for k, v in best],
        "total_usd_cents": sum(r["amount_usd_cents"] for r in mine),
    }


def assemble(policy, names, lines, ledger, refusals, clashes, undone, stray):
    codes = {}
    blamed = {}
    for name, code in refusals:
        codes[code] = codes.get(code, 0) + 1
        blamed[name] = blamed.get(name, 0) + 1
    taken = {}
    for rec in ledger:
        taken[rec["source_file"]] = taken.get(rec["source_file"], 0) + 1
    for name in lines:
        taken.setdefault(name, 0)
        blamed.setdefault(name, 0)
    out = {
        "normalized.jsonl": ledger,
        "summary.json": {
            "accepted_count": len(ledger),
            "by_category": sums(ledger, "category"),
            "by_channel_group": sums(ledger, "channel_group"),
            "by_currency": sums(ledger, "currency"),
            "by_kind": sums(ledger, "kind"),
            "by_region": sums(ledger, "region"),
            "by_segment": sums(ledger, "segment"),
            "net_units": sum(moved(r) for r in ledger),
            "rejected_count": len(refusals),
            "settlement_window": {"end_exclusive": policy["window"][1],
                                  "start": policy["window"][0]},
            "total_usd_cents": sum(r["amount_usd_cents"] for r in ledger),
        },
        "data_quality.json": {
            "accepted_by_source": dict(sorted(taken.items())),
            "duplicate_groups": clashes,
            "input_file_count": len(names),
            "rejected_by_code": dict(sorted(codes.items())),
            "rejected_by_source": dict(sorted(blamed.items())),
            "reversal_orphans": stray,
            "reversed_pairs": undone,
            "scoped_sources": sorted(policy["scopes"]),
            "superseded_sources": sorted(policy["retired"]),
        },
    }
    held = {}
    for rec in ledger:
        held.setdefault(rec["sku"], []).append(rec)
    shelf = []
    for part in sorted(held):
        mine = held[part]
        shelf.append({
            "category": mine[0]["category"],
            "net_units": sum(moved(r) for r in mine),
            "price_list_versions": sorted({r["price_list_version"] for r in mine}),
            "record_count": len(mine),
            "sku": part,
            "total_usd_cents": sum(r["amount_usd_cents"] for r in mine),
        })
    out["product_summary.json"] = {"product_count": len(shelf), "products": shelf}
    for name in ZONES:
        out["region_%s.json" % name] = slice_of("region", name, ledger)
    for name in TIERS:
        out["segment_%s.json" % name] = slice_of("segment", name, ledger)
    return out


def emit(root, out, payloads):
    if not os.path.isdir(out):
        os.makedirs(out)
    body = []
    for rec in payloads["normalized.jsonl"]:
        body.append(json.dumps(rec, sort_keys=True, separators=(",", ":")))
    handle = open(os.path.join(out, "normalized.jsonl"), "w", encoding="utf-8")
    handle.write("\n".join(body) + ("\n" if body else ""))
    handle.close()
    for name, payload in payloads.items():
        if name.endswith(".jsonl"):
            continue
        handle = open(os.path.join(out, name), "w", encoding="utf-8")
        handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        handle.close()


def main(argv):
    root = argv[0] if argv else os.environ.get("INPUT_DIR", "/app/data")
    out = argv[1] if len(argv) > 1 else os.environ.get("OUTPUT_DIR", "/app/out")
    policy = read_policy(root)
    emit(root, out, build(root, policy))


if __name__ == "__main__":
    main(sys.argv[1:])
'''


def main() -> None:
    root = Path(os.environ.get("APP_ROOT", "/app"))
    script = root / "out" / "transform.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(TRANSFORM, encoding="utf-8")
    script.chmod(0o755)
    sys.argv = [str(script), str(root / "data"), str(root / "out")]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
