#!/usr/bin/env python3
"""Reservation quota settlement of one settlement period (reference program).

Usage:
  python3 optimize.py DATA_DIR OUT_DIR        settle the extract, write every report
  python3 optimize.py EVENTS_LOG RULES_JSON   print the result object of one class
Module function aggregate(events_path, rules_path) returns that result object.
"""

import csv
import hashlib
import io
import json
import os
import pathlib
import posixpath
import re
import sqlite3
import sys
import zipfile
import zlib
import xml.etree.ElementTree as ET
from bisect import bisect_right

CLASSES = ("visible", "peak", "steady", "burst", "latency")
CONTROL_NAME = "ctl_r7.json"
FILE_KEYS = ("register", "crosswalk", "profiles", "rates", "weights", "units",
             "amendments", "overrides", "prior")
LOG_COLUMNS = ("req_id", "api_key", "model", "prompt_tok", "completion_tok",
               "done_at", "status", "traffic_class")
CORR_KEYS = ("seq", "tenant", "traffic_class", "field", "value")
RATE_COLUMNS = ("traffic_class", "eff_from", "ru_rate_micro",
                "over_rate_micro", "round_fee_micro")
STATUSES = ("ok", "cut", "rejected")
EXITS = ("settled", "stalled", "cycled", "budget")
INSTANT_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
WHOLE_RE = re.compile(r"\A\d+\Z")
READING_RE = re.compile(r"\Areading (M\d+) (\S+) (\d+)((?: \S+)+)\Z")
UPR_CLASS = tuple(range(1200, 5001, 100))
TJ_RE = re.compile(r"\(((?:\\.|[^\\()])*)\)\s*Tj".encode("ascii"), re.S)
OCTAL_RE = re.compile(r"[0-7]{1,3}".encode("ascii"))
ROOT_RE = re.compile(r"/Root\s+([0-9]+)\s+[0-9]+\s+R".encode("ascii"))
REF_RE = re.compile(r"([0-9]+)\s+[0-9]+\s+R".encode("ascii"))
OBJ_RE = re.compile(r"(?<![0-9])([0-9]+)\s+([0-9]+)\s+obj\b".encode("ascii"))
STREAM_RE = re.compile(r"(?<![A-Za-z])stream\r?\n".encode("ascii"))
WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
PNS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
ZIP_TIME = (2026, 1, 5, 9, 30, 0)
PDF_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
               "(": "(", ")": ")", "\\": "\\"}


class SettleError(Exception):
    """The extract cannot be settled: an invariant break or unreadable input."""


# ---------------------------------------------------------------- values

def whole(value, what):
    """A whole number (non-negative integer) from an int or a digit string."""
    if isinstance(value, bool):
        raise SettleError(f"{what}: not a whole number: {value!r}")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and WHOLE_RE.match(value.strip()):
        return int(value.strip())
    raise SettleError(f"{what}: not a whole number: {value!r}")


def instant(value, what):
    """An instant written YYYY-MM-DDTHH:MM:SSZ (compared as text)."""
    if not isinstance(value, str) or not INSTANT_RE.match(value):
        raise SettleError(f"{what}: not an instant: {value!r}")
    return value


def text(value, what):
    """A non-empty text value."""
    if not isinstance(value, str) or value == "":
        raise SettleError(f"{what}: not a text value: {value!r}")
    return value


def ceil_div(num, den):
    """num / den rounded up, whole numbers only."""
    return -((-num) // den)


# ---------------------------------------------------------------- control

def load_control(path):
    """Read the control file; file names resolve against its folder."""
    with open(path, encoding="utf-8") as handle:
        ctl = json.load(handle)
    if not isinstance(ctl, dict):
        raise SettleError("control file: not a JSON object")
    for key in ("label", "cutoff_seq", "review_shift_ru", "windows", "files"):
        if key not in ctl:
            raise SettleError(f"control file: missing key {key}")
    files, windows = ctl["files"], ctl["windows"]
    if not isinstance(files, dict) or not isinstance(windows, dict):
        raise SettleError("control file: files and windows must be objects")
    base = os.path.dirname(os.path.abspath(path))
    paths = {}
    for key in FILE_KEYS:
        paths[key] = os.path.join(base, text(files.get(key), f"files.{key}"))
    return {"label": ctl["label"], "cutoff": whole(ctl["cutoff_seq"], "cutoff_seq"),
            "threshold": whole(ctl["review_shift_ru"], "review_shift_ru"),
            "windows": windows, "paths": paths, "base": base}


def class_window(ctx, cls):
    """The window of a class: [start instant, end instant]."""
    win = ctx["windows"].get(cls)
    if not isinstance(win, list) or len(win) != 2:
        raise SettleError(f"control file: no window for class {cls}")
    return [instant(win[0], f"window {cls}"), instant(win[1], f"window {cls}")]


# ---------------------------------------------------------------- weights (docx)

PROF_COLUMNS = ("prof_code", "start_step", "patience", "budget")
MC_NS = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
MC_FALLBACK = MC_NS + "Fallback"
MC_CHOICE = MC_NS + "Choice"
MC_ALTERNATE = MC_NS + "AlternateContent"
OOXML_ROOTS = ("http://schemas.openxmlformats.org/", "http://purl.oclc.org/ooxml/")
MC_IGNORABLE = MC_NS + "Ignorable"
MC_PROCESS = MC_NS + "ProcessContent"


def understood(prefixes, requires):
    """True when every namespace a Choice requires is one ECMA-376 defines."""
    uris = [prefixes.get(prefix) for prefix in requires.split()]
    return bool(uris) and all(uri is not None and uri.startswith(OOXML_ROOTS) for uri in uris)


def parse_scoped(raw):
    """Parse an XML part: (root, the namespace prefixes in scope at each element)."""
    scopes, stack, pending, root = {}, [{}], {}, None
    for event, item in ET.iterparse(io.BytesIO(raw), events=("start-ns", "start", "end")):
        if event == "start-ns":
            pending[item[0]] = item[1]
        elif event == "start":
            scope = {**stack[-1], **pending}
            pending = {}
            stack.append(scope)
            scopes[id(item)] = scope
            root = item if root is None else root
        else:
            stack.pop()
    return root, scopes


def expanded(prefixes, qname):
    """The {namespace}local form of a prefixed name; a local part of * stands for every name."""
    prefix, _, name = qname.partition(":")
    return "{" + prefixes.get(prefix, "") + "}" + name


def compatibility(node, prefixes, inherited):
    """Ignorable namespaces and process-content names in force at an element."""
    ignorable, process = inherited
    if node.get(MC_IGNORABLE) is not None:
        ignorable = ignorable | {prefixes.get(p) for p in node.get(MC_IGNORABLE).split()}
    if node.get(MC_PROCESS) is not None:
        process = process | {expanded(prefixes, q) for q in node.get(MC_PROCESS).split()}
    return ignorable, process


def foreign_text(node, scopes, compat):
    """Text of an element whose namespace the consumer does not understand."""
    uri = node.tag[1:].partition("}")[0]
    if uri not in compat[0]:
        raise SettleError("document: element of a namespace that is neither understood nor ignorable")
    if node.tag in compat[1] or "{" + uri + "}*" in compat[1]:
        return "".join(docx_text(child, scopes, compat) for child in node)
    return ""


def docx_text(node, scopes, inherited=(frozenset(), frozenset())):
    """Current text of a docx element as a consumer of the ECMA-376 namespaces reads it: the branch of
    each alternate content it takes, ignorable foreign elements dropped or unwrapped, moved-away runs
    left out."""
    prefixes = scopes[id(node)]
    compat = compatibility(node, prefixes, inherited)
    if node.tag == MC_ALTERNATE:
        for branch in node:
            if branch.tag == MC_CHOICE and understood(scopes[id(branch)], branch.get("Requires", "")):
                return "".join(docx_text(child, scopes, compat) for child in branch)
            if branch.tag == MC_FALLBACK:
                return "".join(docx_text(child, scopes, compat) for child in branch)
        return ""
    if node.tag == MC_FALLBACK or node.tag == WNS + "moveFrom":
        return ""
    if not node.tag[1:].startswith(OOXML_ROOTS):
        return foreign_text(node, scopes, compat)
    own = (node.text or "") if node.tag == WNS + "t" else ""
    return own + "".join(docx_text(child, scopes, compat) for child in node)


def compat_at(root, target, scopes):
    """Compatibility settings in force above an element, gathered from the document element down."""
    path, found = [], False
    def walk(node):
        nonlocal found
        if node is target:
            found = True
            return
        path.append(node)
        for child in node:
            walk(child)
            if found:
                return
        path.pop()
    walk(root)
    compat = (frozenset(), frozenset())
    for node in path:
        compat = compatibility(node, scopes[id(node)], compat)
    return compat


def docx_table(path, what):
    """Rows (cell texts) of the one table of a docx document."""
    with zipfile.ZipFile(path) as book:
        rels = ET.fromstring(book.read("_rels/.rels"))
        main = [r.get("Target") for r in rels if (r.get("Type") or "").endswith("/officeDocument")]
        if len(main) != 1:
            raise SettleError(f"{what}: no main document part")
        raw = book.read(main[0].lstrip("/"))
    root, scopes = parse_scoped(raw)
    tables = list(root.iter(WNS + "tbl"))
    if len(tables) != 1:
        raise SettleError(f"{what}: expected one table")
    compat = compat_at(root, tables[0], scopes)
    return [[docx_text(cell, scopes, compat) for cell in row.findall(WNS + "tc") if not cell_deleted(cell)]
            for row in tables[0].findall(WNS + "tr")]


def cell_deleted(cell):
    """True for a table cell removed with tracked changes (a cell deletion mark in its properties)."""
    props = cell.find(WNS + "tcPr")
    return props is not None and props.find(WNS + "cellDel") is not None


def load_weights(path):
    """Model weight table: model -> (prompt_weight, completion_weight)."""
    rows = docx_table(path, "model weight table")
    if not rows or rows[0] != ["model", "prompt_weight", "completion_weight"]:
        raise SettleError("model weight table: unexpected header row")
    weights = {}
    for row in rows[1:]:
        if len(row) != 3:
            raise SettleError("model weight table: row without three cells")
        if row[0] in weights:
            raise SettleError(f"model weight table: model {row[0]} twice")
        weights[row[0]] = (whole(row[1], "prompt_weight"),
                           whole(row[2], "completion_weight"))
    return weights


# ---------------------------------------------------------------- units (pdf)

def pdf_unescape(raw):
    """Decode the bytes of a PDF literal string."""
    out, pos = [], 0
    while pos < len(raw):
        char = chr(raw[pos])
        pos += 1
        if char != "\\" or pos >= len(raw):
            out.append(char)
            continue
        nxt = chr(raw[pos])
        if nxt in PDF_ESCAPES:
            out.append(PDF_ESCAPES[nxt])
            pos += 1
        elif nxt in "01234567":
            digits = re.match(OCTAL_RE, raw[pos:pos + 3]).group(0)
            out.append(chr(int(digits, 8) & 0xFF))
            pos += len(digits)
        elif nxt in "\r\n":
            pos += 2 if raw[pos:pos + 2] == b"\r\n" else 1
        else:
            out.append(nxt)
            pos += 1
    return "".join(out)


def pdf_stream_data(body):
    """Decoded data of the stream an object body holds."""
    match = STREAM_RE.search(body)
    if match is None:
        raise SettleError("conversion sheet: object without a stream")
    stop = body.find("\nendstream".encode("ascii"), match.end())
    if stop < 0:
        raise SettleError("conversion sheet: unterminated stream")
    raw = body[match.end():stop]
    if raw.endswith("\r".encode("ascii")):
        raw = raw[:-1]
    if "/FlateDecode".encode("ascii") in body[:match.start()]:
        raw = zlib.decompress(raw)
    return raw


def pdf_head(body):
    """Dictionary part of an object body (before any stream)."""
    match = STREAM_RE.search(body)
    return body[:match.start()] if match else body


def pdf_from_objstm(body, index):
    """Object number index of an object stream."""
    raw = pdf_stream_data(body)
    first = int(re.search(r"/First\s+([0-9]+)".encode("ascii"), pdf_head(body)).group(1))
    nums = raw[:first].split()
    start = int(nums[2 * index + 1])
    stop = int(nums[2 * index + 3]) if 2 * index + 3 < len(nums) else len(raw) - first
    return raw[first + start:first + stop]


def pdf_objects(data):
    """Objects in force: the last definition of each number, compressed entries from cross-reference streams."""
    objs = {}
    for match in OBJ_RE.finditer(data):
        objs[int(match.group(1))] = data[match.end():data.find("endobj".encode("ascii"), match.end())]
    for body in list(objs.values()):
        head = pdf_head(body)
        if "/Type /XRef".encode("ascii") not in head:
            continue
        widths = [int(x) for x in re.search(r"/W\s*\[([^\]]*)\]".encode("ascii"), head).group(1).split()]
        index = re.search(r"/Index\s*\[([^\]]*)\]".encode("ascii"), head)
        size = int(re.search(r"/Size\s+([0-9]+)".encode("ascii"), head).group(1))
        ranges = [int(x) for x in index.group(1).split()] if index else [0, size]
        raw, pos = pdf_stream_data(body), 0
        for first, count in zip(ranges[::2], ranges[1::2]):
            for num in range(first, first + count):
                cut = [pos + sum(widths[:k]) for k in range(4)]
                field = [int.from_bytes(raw[cut[k]:cut[k + 1]], "big") for k in range(3)]
                pos = cut[3]
                if (field[0] if widths[0] else 1) == 2:
                    objs[num] = pdf_from_objstm(objs[field[1]], field[2])
    return objs


def pdf_text_lines(data):
    """Every (text) Tj string of the pages of the document the trailer names, in page order."""
    objs = pdf_objects(data)
    root = int(ROOT_RE.findall(data)[-1])
    lines = []

    def walk(num, depth):
        head = pdf_head(objs[num])
        if depth > 32:
            raise SettleError("conversion sheet: page tree too deep")
        if "/Kids".encode("ascii") in head:
            kids = head[head.index("/Kids".encode("ascii")):]
            for kid in REF_RE.findall(kids[:kids.index("]".encode("ascii"))]):
                walk(int(kid), depth + 1)
            return
        contents = re.search(r"/Contents\s*(\[[^\]]*\]|[0-9]+\s+[0-9]+\s+R)".encode("ascii"), head)
        for ref in REF_RE.findall(contents.group(1)) if contents else []:
            body = pdf_stream_data(objs[int(ref)])
            lines.extend(pdf_unescape(m.group(1)) for m in TJ_RE.finditer(body))

    walk(int(re.search(r"/Pages\s+([0-9]+)\s+[0-9]+\s+R".encode("ascii"), pdf_head(objs[root])).group(1)), 0)
    return lines


def load_meters(path):
    """Meter sheet: readings (id, instant, RU, api keys) in sheet order."""
    with open(path, "rb") as handle:
        data = handle.read()
    readings, seen = [], set()
    for line in pdf_text_lines(data):
        match = READING_RE.match(line)
        if match is None:
            continue
        if match.group(1) in seen:
            raise SettleError(f"meter sheet: reading {match.group(1)} twice")
        seen.add(match.group(1))
        readings.append((match.group(1), instant(match.group(2), "reading instant"),
                         int(match.group(3)), match.group(4).split()))
    return readings


# ---------------------------------------------------------------- rates (xlsx)

def part_name(target):
    """Zip member name of a workbook relationship target."""
    if target.startswith("/"):
        return target[1:]
    return posixpath.normpath(posixpath.join("xl", target))


def col_index(ref):
    """Zero-based column of a cell reference such as C12."""
    index = 0
    for char in ref:
        if not char.isalpha():
            break
        index = index * 26 + (ord(char.upper()) - 64)
    return index - 1


def cell_value(cell, shared):
    """Text of a cell: inline string, shared string or <v> text."""
    kind = cell.get("t")
    if kind == "inlineStr":
        item = cell.find(SNS + "is")
        return "" if item is None else shared_text(item)
    node = cell.find(SNS + "v")
    if node is None or node.text is None:
        return None
    if kind == "s":
        index = whole(node.text, "shared string index")
        if index >= len(shared):
            raise SettleError("rate card: shared string index out of range")
        return shared[index]
    return node.text


def row_values(row, shared):
    """Cell texts of one sheet row by column position (None when empty)."""
    values = {}
    for pos, cell in enumerate(row.findall(SNS + "c")):
        ref = cell.get("r")
        values[col_index(ref) if ref else pos] = cell_value(cell, shared)
    if not values:
        return []
    return [values.get(i) for i in range(max(values) + 1)]


def shared_text(item):
    """Text of one shared string item: its t element or its runs."""
    direct = item.find(SNS + "t")
    if direct is not None:
        return direct.text or ""
    return "".join(t.text or "" for t in item.findall(SNS + "r/" + SNS + "t"))


def read_shared(book, rels):
    """Shared strings of a workbook, empty when it has none."""
    for kind, target in rels.values():
        if kind.endswith("/sharedStrings"):
            root = ET.fromstring(book.read(part_name(target)))
            return [shared_text(item) for item in root.findall(SNS + "si")]
    return []


def xlsx_sheet_rows(path, sheet_name):
    """Rows (lists of cell texts) of the sheet with the given name."""
    with zipfile.ZipFile(path) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rel_root = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        rels = {rel.get("Id"): (rel.get("Type") or "", rel.get("Target") or "")
                for rel in rel_root.iter(PNS + "Relationship")}
        rid = None
        for sheet in workbook.iter(SNS + "sheet"):
            if sheet.get("name") == sheet_name:
                rid = sheet.get(RID)
        if rid not in rels:
            raise SettleError(f"rate card: no sheet named {sheet_name}")
        shared = read_shared(book, rels)
        root = ET.fromstring(book.read(part_name(rels[rid][1])))
    return [row_values(row, shared) for row in root.iter(SNS + "row")]


def load_rates(path):
    """Rate rows of the sheet rates."""
    rows = xlsx_sheet_rows(path, "rates")
    if not rows or [v for v in rows[0] if v is not None] != list(RATE_COLUMNS):
        raise SettleError("rate card: unexpected header row")
    index = {name: rows[0].index(name) for name in RATE_COLUMNS}
    rates = []
    for row in rows[1:]:
        if all(v is None or v == "" for v in row):
            continue
        cell = {name: (row[i] if i < len(row) else None) for name, i in index.items()}
        eff = cell["eff_from"]
        if not isinstance(eff, str) or not DATE_RE.match(eff):
            raise SettleError(f"rate card: eff_from not a date: {eff!r}")
        rates.append({"cls": text(cell["traffic_class"], "rate class"), "eff_from": eff,
                      "ru_rate_micro": whole(cell["ru_rate_micro"], "ru_rate_micro"),
                      "over_rate_micro": whole(cell["over_rate_micro"], "over_rate_micro"),
                      "round_fee_micro": whole(cell["round_fee_micro"], "round_fee_micro")})
    return rates


def rate_row(rates, cls, end):
    """Rate row of a class with the latest eff_from on or before the end date."""
    day = end[:10]
    rows = [row for row in rates if row["cls"] == cls and row["eff_from"] <= day]
    if not rows:
        raise SettleError(f"invariant: no rate row in force for class {cls}")
    latest = max(row["eff_from"] for row in rows)
    best = [row for row in rows if row["eff_from"] == latest]
    if len(best) != 1:
        raise SettleError(f"rate card: two rate rows of {cls} share {latest}")
    return best[0]


# ---------------------------------------------------------------- register

def read_register(path):
    """Raw rows of the tables tenant, pool and alias (read-only)."""
    uri = pathlib.Path(os.path.abspath(path)).as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        tenants = con.execute("SELECT code, traffic_class, pool, contracted_ru, "
                              "retired FROM tenant").fetchall()
        pools = con.execute("SELECT pool_id, traffic_class, grp FROM pool").fetchall()
        aliases = con.execute("SELECT api_key, tenant, eff_from FROM alias").fetchall()
    finally:
        con.close()
    return tenants, pools, aliases


def read_sheet(path, delim, columns):
    """Rows of a delimited text sheet as tuples in the order of columns."""
    with open(path, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.reader(fh, delimiter=delim) if r]
    head = rows[0] if rows else []
    missing = [c for c in columns if c not in head]
    if missing:
        raise SettleError(f"{os.path.basename(path)}: missing columns {missing}")
    idx = [head.index(c) for c in columns]
    return [tuple(r[i] for i in idx) for r in rows[1:]]


def join_profiles(group_rows, walk_path, prof_path):
    """Pool rows (pool_id, cls, grp) -> (pool_id, cls, start_step, patience, budget)."""
    walk = {}
    for grp, code in read_sheet(walk_path, ",", ("grp", "prof_code")):
        if grp in walk:
            raise SettleError(f"invariant: group {grp} twice in the crosswalk")
        walk[grp] = code
    prof = {}
    table = docx_table(prof_path, "pool profiles")
    head = table[0] if table else []
    if any(c not in head for c in PROF_COLUMNS):
        raise SettleError("pool profiles: unexpected header row")
    for code, step, pat, bud in [tuple(r[head.index(c)] for c in PROF_COLUMNS) for r in table[1:]]:
        if code in prof:
            raise SettleError(f"invariant: profile {code} twice")
        prof[code] = (step, pat, bud)
    out = []
    for pool_id, cls, grp in group_rows:
        if grp not in walk:
            raise SettleError(f"invariant: group {grp} of pool {pool_id} not in the crosswalk")
        if walk[grp] not in prof:
            raise SettleError(f"invariant: profile {walk[grp]} not in the profiles")
        out.append((pool_id, cls) + prof[walk[grp]])
    return out


def build_tenants(rows):
    """(code, class) -> {pool, contracted_ru, retired}."""
    tenants = {}
    for code, cls, pool, contracted, retired in rows:
        key = (text(code, "tenant code"), text(cls, "tenant class"))
        if key in tenants:
            raise SettleError(f"invariant: two tenant rows for {key[0]} {key[1]}")
        flag = whole(retired, "retired")
        if flag not in (0, 1):
            raise SettleError(f"register: retired is {retired!r}")
        tenants[key] = {"pool": pool, "retired": flag == 1,
                        "contracted_ru": whole(contracted, "contracted_ru")}
    return tenants


def build_pools(rows):
    """pool_id -> {cls, start_step, patience, budget}."""
    pools = {}
    for pool_id, cls, start_step, patience, budget in rows:
        if pool_id in pools:
            raise SettleError(f"register: pool id {pool_id} twice")
        params = [whole(v, "pool parameter") for v in (start_step, patience, budget)]
        if min(params) < 1:
            raise SettleError(f"register: pool {pool_id} parameter below one")
        pools[pool_id] = {"cls": text(cls, "pool class"), "start_step": params[0],
                          "patience": params[1], "budget": params[2]}
    return pools


def build_aliases(rows):
    """api_key -> (sorted effective instants, tenants in the same order)."""
    grouped = {}
    for key, tenant, eff in rows:
        grouped.setdefault(text(key, "api_key"), []).append(
            (instant(eff, "alias eff_from"), text(tenant, "alias tenant")))
    aliases = {}
    for key, entries in grouped.items():
        entries.sort()
        effs = [eff for eff, _ in entries]
        if len(set(effs)) != len(effs):
            raise SettleError(f"invariant: two alias rows of key {key} share an instant")
        aliases[key] = (effs, [tenant for _, tenant in entries])
    return aliases


# ---------------------------------------------------------------- corrections

def correction(layer, rec, pos):
    """One correction entry from a record with the keys of CORR_KEYS."""
    for key in CORR_KEYS:
        if key not in rec:
            raise SettleError(f"{layer} layer: entry without {key}")
    return {"layer": layer, "seq": whole(rec["seq"], f"{layer} seq"), "pos": pos,
            "tenant": text(rec["tenant"], f"{layer} tenant"),
            "cls": text(rec["traffic_class"], f"{layer} traffic_class"),
            "field": text(rec["field"], f"{layer} field"), "value": rec["value"]}


def load_amendments(path):
    """Amendment layer (tab separated, header row)."""
    with open(path, encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.reader(handle, delimiter="\t") if row]
    header = rows[0] if rows else []
    entries = []
    for cells in rows[1:]:
        if len(cells) != len(header):
            raise SettleError("amendment layer: row width differs from header")
        entries.append(correction("amendment", dict(zip(header, cells)), len(entries)))
    return entries


def load_overrides(path):
    """Override layer (one JSON object per line)."""
    entries = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip() == "":
                continue
            rec = json.loads(line)
            if not isinstance(rec, dict):
                raise SettleError("override layer: line is not a JSON object")
            entries.append(correction("override", rec, len(entries)))
    return entries


def corrected_value(entry):
    """The register value a correction entry sets."""
    field, value = entry["field"], entry["value"]
    if field == "contracted_ru":
        return "contracted_ru", whole(value, "correction contracted_ru")
    if field == "pool":
        return "pool", text(value, "correction pool")
    if field == "retired":
        if value not in ("yes", "no"):
            raise SettleError(f"correction retired value {value!r}")
        return "retired", value == "yes"
    raise SettleError(f"correction field {field!r}")


def apply_corrections(tenants, amendments, overrides, cutoff):
    """Corrected tenant rows and the status of every entry (report order)."""
    rows = {key: dict(row) for key, row in tenants.items()}
    entries = []
    for layer in (amendments, overrides):
        for entry in sorted(layer, key=lambda e: (e["seq"], e["pos"])):
            key = (entry["tenant"], entry["cls"])
            if entry["seq"] > cutoff:
                status = "cutoff"
            elif key not in rows:
                status = "unmatched"
            else:
                status = "applied"
                field, value = corrected_value(entry)
                rows[key][field] = value
            entries.append(dict(entry, status=status))
    return rows, entries


def check_pool_names(tenants, pools):
    """Invariant: every pool a tenant row names is a pool of its class."""
    for (code, cls), row in sorted(tenants.items()):
        if row["pool"] is None:
            continue
        pool = pools.get(row["pool"])
        if pool is None or pool["cls"] != cls:
            raise SettleError(f"invariant: tenant {code} {cls} names pool "
                              f"{row['pool']!r} not of its class")


# ---------------------------------------------------------------- request logs

LOG_MAGIC = b"RQB1"
LOG_HEADER = 21
STATUS_CODES = ("ok", "cut", "rejected")
EPOCH_ORDINAL = 739617  # 2026-01-01


def iso_instant(sec):
    """YYYY-MM-DDTHH:MM:SSZ of a count of seconds since 2026-01-01T00:00:00Z."""
    if sec < 0:
        raise SettleError("request log: instant before 2026-01-01")
    import datetime
    day, rest = divmod(sec, 86400)
    date = datetime.date.fromordinal(EPOCH_ORDINAL + day)
    return f"{date.isoformat()}T{rest // 3600:02d}:{rest // 60 % 60:02d}:{rest % 60:02d}Z"


class LogReader:
    """Cursor over the record region of one request log."""

    def __init__(self, data, pos):
        self.data, self.pos = data, pos

    def byte(self):
        if self.pos >= len(self.data):
            raise SettleError("request log: record cut short")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def varint(self):
        value = shift = 0
        while True:
            b = self.byte()
            value |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                return value

    def signed(self):
        n = self.varint()
        return -(n >> 1) - 1 if n & 1 else n >> 1

    def text(self):
        size = self.byte()
        end = self.pos + size
        if end > len(self.data):
            raise SettleError("request log: text cut short")
        raw = self.data[self.pos:end]
        self.pos = end
        try:
            return raw.decode("ascii")
        except UnicodeDecodeError:
            raise SettleError("request log: text not ASCII") from None


def log_header(data):
    """Check the RQB1 header of a request log: (class, request-id prefix, base instant, record count)."""
    if len(data) < LOG_HEADER or data[:4] != LOG_MAGIC or data[4] != 1:
        raise SettleError("request log: not an RQB1 version 1 container")
    if data[5] >= len(CLASSES):
        raise SettleError("request log: unknown class code")
    try:
        prefix = data[6:8].decode("ascii")
    except UnicodeDecodeError:
        raise SettleError("request log: prefix not ASCII") from None
    if zlib.crc32(data[16:17] + data[21:]) != int.from_bytes(data[17:21], "big"):
        raise SettleError("invariant: request log checksum")
    return CLASSES[data[5]], prefix, int.from_bytes(data[8:12], "big"), int.from_bytes(data[12:16], "big")


def record_identity(cur, sel, keys, models):
    """The api key and model of a new (not repeated) record, growing the key and model tables."""
    if sel & 0x10:
        back = cur.varint()
        if back >= len(keys):
            raise SettleError("request log: key reference out of range")
        key = keys[len(keys) - 1 - back]
    else:
        key = cur.text()
        if key not in keys:
            keys.append(key)
    if sel & 0x40:
        index = cur.varint()
        if index >= len(models):
            raise SettleError("request log: model reference out of range")
        model = models[index]
    else:
        model = cur.text()
        if model not in models:
            models.append(model)
    return key, model


def record_selector(cur, classes):
    """Read and check one selector byte: (mode, status code), mode 3 being filler."""
    sel = cur.byte()
    if sel & 0x80:
        raise SettleError("invariant: request log selector with bit 7 set")
    if sel & 3 == 3:
        if sel != 3:
            raise SettleError("invariant: filler byte with other bits set")
        return sel, 3, 0
    status_code = (sel >> 2) & 3
    if status_code == 3:
        raise SettleError("invariant: status outside ok, cut and rejected")
    if sel & 0x20:
        code = cur.byte()
        if code >= len(CLASSES):
            raise SettleError("request log: unknown class code")
        classes.add(CLASSES[code])
    return sel, sel & 3, status_code


def read_log(path):
    """Parse one request log (RQB1 container) once: (traffic class, requests)."""
    with open(path, "rb") as handle:
        data = handle.read()
    cls, prefix, base, count = log_header(data)
    cur = LogReader(data, LOG_HEADER)
    keys, models = [], []
    state, prev = base, None
    requests, seen, classes = [], set(), {cls}
    while cur.pos < len(data):
        sel, mode, status_code = record_selector(cur, classes)
        if mode == 3:
            continue
        number = cur.varint()
        if number > 99999:
            raise SettleError("request log: request number above 99999")
        if mode == 2:
            if sel & 0x50 or prev is None:
                raise SettleError("request log: repeat record without a record before it")
            key, model = prev
        else:
            key, model = record_identity(cur, sel, keys, models)
        ptok, ctok = cur.varint(), cur.varint()
        when = (base if mode == 0 else state) + cur.signed()
        state, prev = when, (key, model)
        req_id = f"rq-{prefix}{number:05d}"
        if req_id in seen:
            raise SettleError(f"invariant: req_id {req_id} twice in a log")
        seen.add(req_id)
        requests.append((req_id, key, model, ptok, ctok, iso_instant(when), STATUS_CODES[status_code]))
    if len(requests) != count:
        raise SettleError("request log: record count differs from the header")
    if not requests:
        raise SettleError("invariant: a request log holds no request")
    if len(classes) != 1:
        raise SettleError(f"invariant: a request log names {len(classes)} classes")
    return cls, requests


def reach(ctx, key, done, cls):
    """Tenant code a request reaches, or None when it is an orphan."""
    hist = ctx["aliases"].get(key)
    if hist is None:
        return None
    pos = bisect_right(hist[0], done) - 1
    if pos < 0:
        return None
    tenant = hist[1][pos]
    row = ctx["tenants"].get((tenant, cls))
    if row is None or row["retired"] or row["pool"] is None:
        return None
    return tenant


def classify(ctx, cls, requests, window):
    """Demand of one class: counts, token units per tenant and per model."""
    start, end = window
    stats = dict.fromkeys(("in_window", "out_of_window", "rejected",
                           "orphan", "counted"), 0)
    units, models, dropped = {}, {}, []
    for req_id, key, model, ptok, ctok, done, status in requests:
        if model not in ctx["weights"]:
            raise SettleError(f"invariant: model {model!r} not in weight table")
        if not start < done <= end:
            stats["out_of_window"] += 1
            dropped.append((req_id, "out_of_window"))
            continue
        stats["in_window"] += 1
        tenant = None if status == "rejected" else reach(ctx, key, done, cls)
        if tenant is None:
            reason = "rejected" if status == "rejected" else "orphan"
            stats[reason] += 1
            dropped.append((req_id, reason))
            continue
        pweight, cweight = ctx["weights"][model]
        amount = ptok * pweight + (ctok * cweight if status == "ok" else 0)
        units[tenant] = units.get(tenant, 0) + amount
        tally = models.setdefault(model, [0, 0])
        tally[0] += 1
        tally[1] += amount
        stats["counted"] += 1
    return stats, units, models, sorted(dropped)


# ---------------------------------------------------------------- settlement

def targets(hold, demand):
    """Targets of a round: shares of the pool total in proportion to demand."""
    total, dsum = sum(hold), sum(demand)
    if dsum == 0:
        return list(hold)
    base, rems = [], []
    for need in demand:
        whole_part, rem = divmod(total * need, dsum)
        base.append(whole_part)
        rems.append(rem)
    left = total - sum(base)
    order = sorted(range(len(hold)), key=lambda i: (-rems[i], -hold[i], i))
    for i in order[:left]:
        base[i] += 1
    return base


def quarter_round(amount):
    """amount / 4 rounded to the nearest whole unit, an exact half toward zero."""
    whole_part, rem = divmod(abs(amount), 4)
    if rem > 2:
        whole_part += 1
    return whole_part if amount >= 0 else -whole_part


def movements(hold, target, step):
    """Movements a round yields after the zero-sum correction."""
    raw = [quarter_round((t - h) * step) for h, t in zip(hold, target)]
    best, far = 0, -1
    for i, (h, t) in enumerate(zip(hold, target)):
        dist = abs(t - (h + raw[i]))
        if dist > far:
            best, far = i, dist
    raw[best] -= sum(raw)
    return raw


def run_rounds(hold0, demand, params):
    """Settle one pool; returns exit, round count, final step, holdings, trace."""
    hold, step, impatience, prev = list(hold0), params["start_step"], 0, None
    states, seen, trace, rnd = [tuple(hold)], {tuple(hold): 0}, [], 0
    while True:
        target = targets(hold, demand)
        resid = sum(abs(t - h) for h, t in zip(hold, target))
        if rnd >= 1 and resid >= prev:
            impatience += 1
            if impatience >= params["patience"]:
                step, impatience = max(1, step // 2), 0
        trace.append((rnd, resid, step))
        if resid == 0:
            return "settled", rnd, step, hold, trace
        moves = movements(hold, target, step)
        if not any(moves):
            return "stalled", rnd, step, hold, trace
        hold = [h + m for h, m in zip(hold, moves)]
        state = tuple(hold)
        if state in seen:
            cycle = states[seen[state]:] + [state]
            return "cycled", -1, step, list(min(cycle)), trace
        if rnd + 1 >= params["budget"]:
            return "budget", params["budget"], step, hold, trace
        seen[state] = len(states)
        states.append(state)
        prev, rnd = resid, rnd + 1


# ---------------------------------------------------------------- calibration

def unit_history(ctx, logs):
    """(tenant, class) -> (completion instants, running token units) of counted requests."""
    hist = {}
    for cls, requests in logs.items():
        start, end = class_window(ctx, cls)
        for _req_id, key, model, ptok, ctok, done, status in requests:
            if not start < done <= end or status == "rejected":
                continue
            tenant = reach(ctx, key, done, cls)
            if tenant is None or model not in ctx["weights"]:
                continue
            pweight, cweight = ctx["weights"][model]
            amount = ptok * pweight + (ctok * cweight if status == "ok" else 0)
            hist.setdefault((tenant, cls), []).append((done, amount))
    out = {}
    for code, rows in hist.items():
        rows.sort()
        times, running, total = [], [], 0
        for done, amount in rows:
            total += amount
            times.append(done)
            running.append(total)
        out[code] = (times, running)
    return out


def units_at(hist, code, when):
    """Token units of a member counted from requests completed at or before an instant."""
    times, running = hist.get(code, ((), ()))
    pos = bisect_right(times, when)
    return running[pos - 1] if pos else 0


def owner_at(ctx, key, when):
    """Tenant an api key reaches at an instant, or None."""
    hist = ctx["aliases"].get(key)
    if hist is None:
        return None
    pos = bisect_right(hist[0], when) - 1
    return hist[1][pos] if pos >= 0 else None


def reading_terms(ctx, hist, reading):
    """(pool, token units) of the distinct members the keys of a reading reach."""
    _rid, when, _ru, keys = reading
    seen, terms = set(), []
    for key in keys:
        tenant = owner_at(ctx, key, when)
        if tenant is None:
            continue
        for cls in CLASSES:
            row = ctx["tenants"].get((tenant, cls))
            if row is None or row["retired"] or row["pool"] is None or (tenant, cls) in seen:
                continue
            seen.add((tenant, cls))
            amount = units_at(hist, (tenant, cls), when)
            if amount > 0:
                terms.append((row["pool"], amount))
    return terms


def fit_search(cons, limit=2):
    """Assignments pool -> units per RU meeting every reading (up to limit of them)."""
    pools = sorted({p for terms, _ in cons for p, _ in terms})
    dom = {p: list(UPR_CLASS) for p in pools}
    for terms, ru in cons:
        if not terms:
            if ru != 0:
                return []
            continue
        if len({p for p, _ in terms}) == 1:
            pid = terms[0][0]
            dom[pid] = [u for u in dom[pid] if sum(ceil_div(a, u) for _, a in terms) == ru]
    if any(not d for d in dom.values()):
        return []
    touch = {p: [i for i, (terms, _) in enumerate(cons) if any(q == p for q, _ in terms)] for p in pools}
    order = sorted(pools, key=lambda p: (len(dom[p]), -len(touch[p]), p))
    found, cur = [], {}

    def feasible(i):
        terms, ru = cons[i]
        low = high = 0
        for pid, amount in terms:
            if pid in cur:
                low += ceil_div(amount, cur[pid])
                high += ceil_div(amount, cur[pid])
            else:
                low += ceil_div(amount, dom[pid][-1])
                high += ceil_div(amount, dom[pid][0])
        return low <= ru <= high

    def step(depth):
        if depth == len(order):
            found.append(dict(cur))
            return
        pid = order[depth]
        for value in dom[pid]:
            cur[pid] = value
            if all(feasible(i) for i in touch[pid]):
                step(depth + 1)
            del cur[pid]
            if len(found) >= limit:
                return

    step(0)
    return found


def calibrate(ctx, logs):
    """Units per RU of every pool with a unit-bearing member, from the meter sheet."""
    hist = unit_history(ctx, logs)
    cons = [(reading_terms(ctx, hist, r), r[2]) for r in ctx["meters"]]
    found = fit_search(cons)
    if not found:
        raise SettleError("invariant: no units per RU assignment meets every meter reading")
    if len(found) > 1:
        raise SettleError("invariant: more than one units per RU assignment meets the meter readings")
    upr = found[0]
    for (tenant, cls), (_times, running) in hist.items():
        row = ctx["tenants"].get((tenant, cls))
        if running and running[-1] > 0 and row["pool"] not in upr:
            raise SettleError(f"invariant: pool {row['pool']} has token units and no meter reading")
    return upr


def settle_pool(ctx, cls, pool_id, members, units, upr):
    """Settlement result of one pool with its member records."""
    params = ctx["pools"][pool_id]
    hold0 = [ctx["tenants"][(code, cls)]["contracted_ru"] for code in members]
    demand = [ceil_div(units.get(code, 0), upr) if units.get(code, 0) else 0 for code in members]
    exit_, rounds, step, hold, trace = run_rounds(hold0, demand, params)
    records = [{"tenant": code, "contracted_ru": hold0[i], "demand_ru": demand[i],
                "settled_ru": hold[i], "units": units.get(code, 0)}
               for i, code in enumerate(members)]
    return {"pool": pool_id, "exit": exit_, "rounds": rounds, "final_step": step,
            "budget": params["budget"], "members": records, "trace": trace,
            "total": sum(hold0)}


def bill_pools(pools, rate, upr):
    """Bill lines of every member of every pool of a class."""
    lines = []
    for pool in pools:
        count = pool["budget"] if pool["exit"] == "cycled" else pool["rounds"]
        share, extra = divmod(rate["round_fee_micro"] * count, len(pool["members"]))
        for i, mem in enumerate(pool["members"]):
            over_units = max(0, mem["units"] - mem["settled_ru"] * upr.get(pool["pool"], 0))
            line = {"pool": pool["pool"], "tenant": mem["tenant"],
                    "settled_ru": mem["settled_ru"], "token_units": mem["units"],
                    "overage_units": over_units,
                    "reservation_micro": mem["settled_ru"] * rate["ru_rate_micro"],
                    "overage_micro": ceil_div(over_units * rate["over_rate_micro"], 1000),
                    "orchestration_micro": share + (1 if i < extra else 0)}
            line["total_micro"] = (line["reservation_micro"] + line["overage_micro"]
                                   + line["orchestration_micro"])
            lines.append(line)
    return lines


def settle_class(ctx, cls, requests):
    """Demand, settlement and billing of one class in scope."""
    window = class_window(ctx, cls)
    upr = ctx["upr"]
    rate = rate_row(ctx["rates"], cls, window[1])
    stats, units, models, dropped = classify(ctx, cls, requests, window)
    pools = []
    for pool_id in sorted(p for p, info in ctx["pools"].items() if info["cls"] == cls):
        members = sorted(code for (code, rcls), row in ctx["tenants"].items()
                         if rcls == cls and not row["retired"] and row["pool"] == pool_id)
        if members:
            pools.append(settle_pool(ctx, cls, pool_id, members, units, upr.get(pool_id)))
    return {"cls": cls, "window": window, "rate": rate, "stats": stats,
            "upr": {p["pool"]: upr[p["pool"]] for p in pools if p["pool"] in upr},
            "models": models, "dropped": dropped, "pools": pools,
            "bills": bill_pools(pools, rate, upr)}


def result_object(label, res):
    """The result object of a class (fm_reports.md)."""
    pools = [{"pool": p["pool"], "exit": p["exit"], "rounds": p["rounds"],
              "final_step": p["final_step"],
              "members": [{"tenant": m["tenant"], "contracted_ru": m["contracted_ru"],
                           "demand_ru": m["demand_ru"], "settled_ru": m["settled_ru"]}
                          for m in p["members"]]} for p in res["pools"]]
    return {"label": label, "traffic_class": res["cls"],
            "counted_requests": res["stats"]["counted"],
            "token_units": sum(m["units"] for p in res["pools"] for m in p["members"]),
            "pools": pools}


# ---------------------------------------------------------------- loading

def load_context(ctl_path):
    """Control file, corrected register and method constants."""
    ctx = load_control(ctl_path)
    paths = ctx["paths"]
    tenant_rows, pool_rows, alias_rows = read_register(paths["register"])
    tenants = build_tenants(tenant_rows)
    pools = build_pools(join_profiles(pool_rows, paths["crosswalk"], paths["profiles"]))
    ctx["aliases"] = build_aliases(alias_rows)
    ctx["tenants"], ctx["corrections"] = apply_corrections(
        tenants, load_amendments(paths["amendments"]),
        load_overrides(paths["overrides"]), ctx["cutoff"])
    check_pool_names(ctx["tenants"], pools)
    ctx["pools"] = pools
    ctx["weights"] = load_weights(paths["weights"])
    ctx["meters"] = load_meters(paths["units"])
    ctx["rates"] = load_rates(paths["rates"])
    return ctx


def load_prior(path):
    """Prior output: class -> tenant -> settled RU (comparison only)."""
    with open(path, encoding="utf-8") as handle:
        prior = json.load(handle)
    settled = prior.get("settled") if isinstance(prior, dict) else None
    if not isinstance(settled, dict):
        raise SettleError("prior output: no settled object")
    for cls, table in settled.items():
        if not isinstance(table, dict):
            raise SettleError(f"prior output: class {cls} is not an object")
        for code, value in table.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise SettleError(f"prior output: {cls} {code} is not a whole number")
    return settled


def read_logs(base):
    """Every request log of the extract: class -> requests."""
    logs = {}
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        if not (name.startswith("ev_") and name.endswith(".rqb") and os.path.isfile(path)):
            continue
        cls, requests = read_log(path)
        if cls not in CLASSES:
            raise SettleError(f"request log {name}: unknown class {cls!r}")
        if cls in logs:
            known = {req[0]: req for req in logs[cls]}
            if any(req[0] in known and known[req[0]] != req for req in requests):
                raise SettleError(f"request log {name}: a request differs from its copy in another log of {cls}")
            requests = logs[cls] + [req for req in requests if req[0] not in known]
        logs[cls] = requests
    return logs


def aggregate(events_path, rules_path):
    """Result object of the class of one request log."""
    ctx = load_context(rules_path)
    cls, requests = read_log(events_path)
    if cls not in CLASSES:
        raise SettleError(f"request log: unknown class {cls!r}")
    logs = read_logs(ctx["base"])
    logs[cls] = requests
    ctx["upr"] = calibrate(ctx, logs)
    return result_object(ctx["label"], settle_class(ctx, cls, requests))


def result_line(result):
    """The one-line form of a result object."""
    return json.dumps(result, sort_keys=True, ensure_ascii=True) + "\n"


# ---------------------------------------------------------------- byte forms

def json_bytes(obj):
    """JSON report bytes."""
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def csv_field(value):
    """One CSV field, quoted only when needed."""
    field = str(value)
    if any(char in field for char in ',"\n'):
        return '"' + field.replace('"', '""') + '"'
    return field


def csv_bytes(header, rows):
    """CSV report bytes."""
    return "".join(",".join(csv_field(v) for v in row) + "\n"
                   for row in [header] + rows).encode("utf-8")


def sep_bytes(sep, header, rows):
    """TSV or PSV report bytes."""
    return "".join(sep.join(str(v) for v in row) + "\n"
                   for row in [header] + rows).encode("utf-8")


def xml_attr(value):
    """Escaped XML attribute value."""
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def xml_bytes(root, child, items):
    """XML report: a root holding self-closing children with ordered attributes."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    if not items:
        lines.append(f"<{root}/>")
    else:
        lines.append(f"<{root}>")
        for attrs in items:
            body = " ".join(f'{name}="{xml_attr(value)}"' for name, value in attrs)
            lines.append(f"  <{child} {body}/>")
        lines.append(f"</{root}>")
    return ("\n".join(lines) + "\n").encode("utf-8")


def lines_bytes(lines):
    """Plain text report bytes (empty when nothing to list)."""
    return "".join(line + "\n" for line in lines).encode("utf-8")


# ---------------------------------------------------------------- reports

def member_rows(run):
    """(class result, pool, member) in report order."""
    return [(res, pool, mem) for res in run["classes"]
            for pool in res["pools"] for mem in pool["members"]]


def bill_rows(run):
    """(class name, bill line) in report order."""
    return [(res["cls"], line) for res in run["classes"] for line in res["bills"]]


def report_scenarios(run, out):
    """scenario_CLASS.json for the five classes."""
    by_cls = {res["cls"]: res for res in run["classes"]}
    for cls in CLASSES:
        res = by_cls.get(cls)
        if res is None:
            obj = {"traffic_class": cls, "in_scope": False}
        else:
            obj = {"traffic_class": cls, "in_scope": True, "window": res["window"],
                   "result": result_object(run["label"], res),
                   "bill_total_micro": sum(b["total_micro"] for b in res["bills"])}
        out[f"scenario_{cls}.json"] = json_bytes(obj)


def report_summaries(run, out):
    """perf_report.json, bottleneck_analysis.json, recommendations.json."""
    pools = [(res["cls"], pool) for res in run["classes"] for pool in res["pools"]]
    out["perf_report.json"] = json_bytes({
        "classes_in_scope": [res["cls"] for res in run["classes"]],
        "pool_count": len(pools),
        "member_count": sum(len(pool["members"]) for _, pool in pools),
        "counted_requests": sum(res["stats"]["counted"] for res in run["classes"])})
    top = max((pool["rounds"] for _, pool in pools), default=None)
    out["bottleneck_analysis.json"] = json_bytes({
        "longest": [[c, p["pool"], p["rounds"]] for c, p in pools if p["rounds"] == top],
        "unsettled": [[c, p["pool"], p["exit"]] for c, p in pools
                      if p["exit"] in ("cycled", "budget")],
        "stalled": [[c, p["pool"]] for c, p in pools if p["exit"] == "stalled"]})
    actions = []
    for res, _, mem in member_rows(run):
        shift = mem["settled_ru"] - mem["contracted_ru"]
        if shift and abs(shift) >= run["threshold"]:
            actions.append([res["cls"], mem["tenant"], "raise" if shift > 0 else "lower", shift])
    out["recommendations.json"] = json_bytes({"review_shift_ru": run["threshold"],
                                              "actions": actions})


def report_quality(run, out):
    """data_quality.json and window_counts.csv."""
    classes = run["classes"]
    retired = [[res["cls"], code] for res in classes
               for (code, cls), row in sorted(run["tenants"].items())
               if cls == res["cls"] and row["retired"]]
    counts = dict.fromkeys(("applied", "cutoff", "unmatched"), 0)
    for entry in run["corrections"]:
        counts[entry["status"]] += 1
    out["data_quality.json"] = json_bytes({
        "orphan_requests": {r["cls"]: r["stats"]["orphan"] for r in classes},
        "out_of_window": {r["cls"]: r["stats"]["out_of_window"] for r in classes},
        "rejected_requests": {r["cls"]: r["stats"]["rejected"] for r in classes},
        "retired_members": retired, "corrections": counts})
    out["window_counts.csv"] = csv_bytes(
        ["traffic_class", "in_window", "out_of_window"],
        [[r["cls"], r["stats"]["in_window"], r["stats"]["out_of_window"]] for r in classes])


def report_pools(run, out):
    """pool_settlement.csv, tenant_holdings.tsv, round_trace.psv, pool_members.json."""
    pools = [(res["cls"], pool) for res in run["classes"] for pool in res["pools"]]
    out["pool_settlement.csv"] = csv_bytes(
        ["traffic_class", "pool", "members", "exit", "rounds", "final_step", "pool_total_ru"],
        [[c, p["pool"], len(p["members"]), p["exit"], p["rounds"], p["final_step"],
          p["total"]] for c, p in pools])
    out["tenant_holdings.tsv"] = sep_bytes("\t", [
        "traffic_class", "pool", "tenant", "contracted_ru", "demand_ru", "settled_ru"],
        [[res["cls"], pool["pool"], m["tenant"], m["contracted_ru"], m["demand_ru"],
          m["settled_ru"]] for res, pool, m in member_rows(run)])
    out["round_trace.psv"] = sep_bytes("|", [
        "traffic_class", "pool", "round", "residual_total", "step"],
        [[c, p["pool"], rnd, resid, step] for c, p in pools
         for rnd, resid, step in p["trace"]])
    out["pool_members.json"] = json_bytes(
        {res["cls"]: {p["pool"]: [m["tenant"] for m in p["members"]] for p in res["pools"]}
         for res in run["classes"]})


def report_xml(run, out):
    """exit_summary.xml and holding_shift.xml."""
    items = []
    for res in run["classes"]:
        exits = [p["exit"] for p in res["pools"]]
        items.append([("name", res["cls"])] + [(e, exits.count(e)) for e in EXITS])
    out["exit_summary.xml"] = xml_bytes("exits", "class", items)
    shifts = [[("class", res["cls"]), ("pool", pool["pool"]), ("tenant", m["tenant"]),
               ("from", m["contracted_ru"]), ("to", m["settled_ru"]),
               ("delta", m["settled_ru"] - m["contracted_ru"])]
              for res, pool, m in member_rows(run) if m["settled_ru"] != m["contracted_ru"]]
    out["holding_shift.xml"] = xml_bytes("shifts", "shift", shifts)


def report_bills(run, out):
    """tenant_bills.csv, class_billing.json, invoice_lines.yaml, overage.txt."""
    keys = ("reservation_micro", "overage_micro", "orchestration_micro", "total_micro")
    rows = bill_rows(run)
    out["tenant_bills.csv"] = csv_bytes(
        ["traffic_class", "pool", "tenant", "settled_ru", "token_units", "overage_units"]
        + list(keys),
        [[c, b["pool"], b["tenant"], b["settled_ru"], b["token_units"],
          b["overage_units"]] + [b[k] for k in keys] for c, b in rows])
    billing = {}
    for res in run["classes"]:
        sums = {k: sum(b[k] for b in res["bills"]) for k in keys}
        sums["lines"] = len(res["bills"])
        billing[res["cls"]] = sums
    out["class_billing.json"] = json_bytes(billing)
    out["invoice_lines.yaml"] = lines_bytes(
        [part for c, b in rows for part in (f"- class: {c}", f"  tenant: {b['tenant']}",
                                            f"  total_micro: {b['total_micro']}")])
    out["overage.txt"] = lines_bytes(
        [f"{c:<10}{b['tenant']:<12}{b['overage_units']:>12}{b['overage_micro']:>14}"
         for c, b in rows if b["overage_units"] > 0])


def report_digest(run, out):
    """invoice_digest.md and rate_application.json."""
    lines = []
    for pos, res in enumerate(run["classes"]):
        lines += [f"## {res['cls']}", "", "| tenant | total_micro |", "|---|---:|"]
        lines += [f"| {b['tenant']} | {b['total_micro']} |" for b in res["bills"]]
        if pos != len(run["classes"]) - 1:
            lines.append("")
    out["invoice_digest.md"] = lines_bytes(lines)
    out["rate_application.json"] = json_bytes(
        {res["cls"]: {"eff_from": res["rate"]["eff_from"],
                      "ru_rate_micro": res["rate"]["ru_rate_micro"],
                      "over_rate_micro": res["rate"]["over_rate_micro"],
                      "round_fee_micro": res["rate"]["round_fee_micro"],
                      "units_per_ru": res["upr"]} for res in run["classes"]})


def report_inputs(run, out):
    """delta_prior.csv, demand_by_model.tsv, orphans.csv, corrections_applied.csv."""
    delta = []
    for res in run["classes"]:
        prior = run["prior"].get(res["cls"], {})
        for mem in sorted((m for p in res["pools"] for m in p["members"]),
                          key=lambda m: m["tenant"]):
            old = prior.get(mem["tenant"])
            delta.append([res["cls"], mem["tenant"], mem["settled_ru"],
                          "" if old is None else old,
                          "" if old is None else mem["settled_ru"] - old])
    out["delta_prior.csv"] = csv_bytes(
        ["traffic_class", "tenant", "settled_ru", "prior_ru", "delta_ru"], delta)
    out["demand_by_model.tsv"] = sep_bytes("\t", [
        "traffic_class", "model", "counted_requests", "token_units"],
        [[res["cls"], model, tally[0], tally[1]] for res in run["classes"]
         for model, tally in sorted(res["models"].items())])
    out["orphans.csv"] = csv_bytes(["traffic_class", "req_id", "reason"],
                                   [[res["cls"], req_id, reason] for res in run["classes"]
                                    for req_id, reason in res["dropped"]])
    out["corrections_applied.csv"] = csv_bytes(
        ["layer", "seq", "tenant", "traffic_class", "field", "status"],
        [[e["layer"], e["seq"], e["tenant"], e["cls"], e["field"], e["status"]]
         for e in run["corrections"]])


# ---------------------------------------------------------------- binary reports

BOOK_HEADER = ["traffic_class", "tenant", "reservation_micro", "overage_micro",
               "orchestration_micro", "total_micro"]
CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package'
    '.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxml'
    'formats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName='
    '"/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.spreadsheetml.worksheet+xml"/></Types>')
ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
    '2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="bills" sheetId="1" r:id="rId1"/></sheets></workbook>')
WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
    '2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')


def book_rows(run):
    """Rows of the sheet bills: header, then one row per bill line."""
    return [BOOK_HEADER] + [[c, b["tenant"], b["reservation_micro"], b["overage_micro"],
                             b["orchestration_micro"], b["total_micro"]]
                            for c, b in bill_rows(run)]


def sheet_xml(rows):
    """Worksheet XML: inline strings for text, <v> for numbers."""
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData>']
    for rnum, row in enumerate(rows, start=1):
        parts.append(f'<row r="{rnum}">')
        for cnum, value in enumerate(row):
            ref = f"{chr(65 + cnum)}{rnum}"
            if isinstance(value, int):
                parts.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                safe = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{safe}</t></is></c>')
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def xlsx_bytes(rows):
    """Deterministic workbook bytes."""
    members = [("[Content_Types].xml", CONTENT_TYPES), ("_rels/.rels", ROOT_RELS),
               ("xl/workbook.xml", WORKBOOK), ("xl/_rels/workbook.xml.rels", WORKBOOK_RELS),
               ("xl/worksheets/sheet1.xml", sheet_xml(rows))]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        for name, body in members:
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            book.writestr(info, body.encode("utf-8"))
    return buffer.getvalue()


def write_ledger(path, run):
    """billing_ledger.sqlite: tables bills and pools, rows in report order."""
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE bills (traffic_class TEXT, tenant TEXT, "
                    "total_micro INTEGER)")
        con.execute("CREATE TABLE pools (traffic_class TEXT, pool TEXT, exit TEXT, "
                    "rounds INTEGER)")
        con.executemany("INSERT INTO bills VALUES (?, ?, ?)",
                        [(c, b["tenant"], b["total_micro"]) for c, b in bill_rows(run)])
        con.executemany("INSERT INTO pools VALUES (?, ?, ?, ?)",
                        [(res["cls"], p["pool"], p["exit"], p["rounds"])
                         for res in run["classes"] for p in res["pools"]])
        con.commit()
    finally:
        con.close()


def read_ledger(path):
    """Rows of every table of the ledger: table name -> rows in rowid order."""
    uri = pathlib.Path(os.path.abspath(path)).as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        names = [row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        return {name: con.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
                for name in names}
    finally:
        con.close()


def dump_bytes(tables):
    """Digest form of the database report."""
    lines = []
    for name in sorted(tables):
        lines.append(f"table {name}")
        lines += ["\t".join("" if v is None else str(v) for v in row) for row in tables[name]]
    return lines_bytes(lines)


def report_reconciliation(run, ledger):
    """reconciliation.json from the bill lines, class totals and the ledger."""
    obj = {}
    for res in run["classes"]:
        lines_total = sum(b["total_micro"] for b in res["bills"])
        class_total = (sum(b["reservation_micro"] for b in res["bills"])
                       + sum(b["overage_micro"] for b in res["bills"])
                       + sum(b["orchestration_micro"] for b in res["bills"]))
        ledger_total = sum(row[2] for row in ledger["bills"] if row[0] == res["cls"])
        mems = [m for p in res["pools"] for m in p["members"]]
        obj[res["cls"]] = {
            "bill_lines_total": lines_total, "class_total": class_total,
            "ledger_total": ledger_total,
            "residual_micro": lines_total + ledger_total - 2 * class_total,
            "ru_residual": sum(m["settled_ru"] for m in mems)
                           - sum(m["contracted_ru"] for m in mems)}
    return json_bytes(obj)


# ---------------------------------------------------------------- run

def settle_extract(data_dir):
    """Settle every class in scope in memory."""
    ctx = load_context(os.path.join(data_dir, CONTROL_NAME))
    prior = load_prior(ctx["paths"]["prior"])
    logs = read_logs(ctx["base"])
    ctx["upr"] = calibrate(ctx, logs)
    classes = [settle_class(ctx, cls, logs[cls]) for cls in CLASSES if cls in logs]
    return {"label": ctx["label"], "threshold": ctx["threshold"], "classes": classes,
            "tenants": ctx["tenants"], "corrections": ctx["corrections"], "prior": prior}


def build_text_reports(run):
    """Every text report except reconciliation.json, in memory."""
    out = {}
    for builder in (report_scenarios, report_summaries, report_quality, report_pools,
                    report_xml, report_bills, report_digest, report_inputs):
        builder(run, out)
    return out


def write_reports(run, out_dir):
    """Write every report; the manifest last."""
    texts = build_text_reports(run)
    book = book_rows(run)
    os.makedirs(out_dir, exist_ok=True)
    digests = {}
    for name, body in texts.items():
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(body)
        digests[name] = hashlib.sha256(body).hexdigest()
    ledger_path = os.path.join(out_dir, "billing_ledger.sqlite")
    write_ledger(ledger_path, run)
    ledger = read_ledger(ledger_path)
    digests["billing_ledger.sqlite"] = hashlib.sha256(dump_bytes(ledger)).hexdigest()
    with open(os.path.join(out_dir, "billing_book.xlsx"), "wb") as handle:
        handle.write(xlsx_bytes(book))
    book_dump = lines_bytes(["\t".join(str(v) for v in row) for row in book])
    digests["billing_book.xlsx"] = hashlib.sha256(book_dump).hexdigest()
    recon = report_reconciliation(run, ledger)
    with open(os.path.join(out_dir, "reconciliation.json"), "wb") as handle:
        handle.write(recon)
    digests["reconciliation.json"] = hashlib.sha256(recon).hexdigest()
    with open(os.path.join(out_dir, "manifest.json"), "wb") as handle:
        handle.write(json_bytes({"reports": digests}))


def main(argv):
    """Command line entry point."""
    if len(argv) != 3:
        sys.stderr.write("usage: optimize.py DATA_DIR OUT_DIR | EVENTS_LOG RULES_JSON\n")
        return 2
    first, second = argv[1], argv[2]
    try:
        if os.path.isdir(first):
            write_reports(settle_extract(first), second)
        elif os.path.isfile(first):
            sys.stdout.write(result_line(aggregate(first, second)))
        else:
            raise SettleError(f"no such directory or file: {first}")
    except (SettleError, OSError, ValueError, KeyError, IndexError, TypeError,
            sqlite3.Error, zipfile.BadZipFile, ET.ParseError, zlib.error,
            csv.Error) as exc:
        sys.stderr.write(f"optimize: {type(exc).__name__}: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
