#!/usr/bin/env python3
"""STRATA relocation planner.

Reads a corpus directory of relocation records and writes the twenty-four
plan artifacts described by SPEC-STRATA into an output directory.
"""

import csv
import hashlib
import io
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_POLICY = 3

UNIT_FACTOR = {
    "B": 1,
    "KiB": 1024,
    "MiB": 1048576,
    "GiB": 1073741824,
    "kB": 1000,
    "MB": 1000000,
    "GB": 1000000000,
    "s": 512,
    "bl": 4096,
}

DEFAULT_POOL_ALLOC_UNIT = 4096
FAST_SYMLINK_MAX = 59
HOP_CAP = 8
MAX_ROUNDS = 8
SPILL_HOPS = 4

CLASS_ORDER = ["gold", "silver", "bronze", "tin"]
CLASS_RANK = {c: i for i, c in enumerate(CLASS_ORDER)}

FLAG_ORDER = ["hole", "unwritten", "inline", "shared", "sealed"]

TABLES = {
    "pool": ["pool_id", "alloc_unit", "root_depth_cap", "region"],
    "barrier": ["pool_id", "rev", "barrier_seq", "effective_seq"],
    "capacity": [
        "device_id", "rev", "capacity_raw", "capacity_unit",
        "existing_used_raw", "existing_used_unit", "reserve_ppm",
        "effective_seq",
    ],
    "geometry": [
        "slot_id", "device_id", "rev", "share_domain", "spill_device",
        "online", "alloc_unit", "effective_seq",
    ],
    "window": [
        "device_id", "window_index", "io_budget_raw", "io_budget_unit",
        "descriptor_budget",
    ],
    "route": ["route_id", "class", "pool_id", "device_id"],
    "object": [
        "ino", "kind", "size_raw", "size_unit", "mode_raw", "uid", "gid",
        "mtime_ns", "class_raw", "pool_id", "link_count", "state", "gen",
    ],
    "path": ["ino", "path_raw", "ordinal", "form"],
    "extent": [
        "ino", "ext_index", "offset", "length_raw", "length_unit",
        "physical_id", "flags", "gen",
    ],
    "symlink": ["ino", "target_raw", "form"],
    "special": ["node_id", "ino", "node_kind", "major", "minor"],
    "xattr": ["xattr_id", "ino", "name", "value_len", "gen"],
    "claim": ["claim_id", "ino", "set_name"],
    "deadline": ["ino", "deadline_window", "class_override"],
    "hold": ["ino", "reason", "active"],
    "checkpoint": ["ino", "ext_index", "bytes_committed", "seq", "pool_id"],
    "activity": [
        "seq", "ordinal", "kind", "ino", "path_a", "path_b", "arg_num",
        "arg_alt",
    ],
}

SCHEMA_BY_FIELDS = {frozenset(f): name for name, f in TABLES.items()}
SCHEMA_BY_TAIL = {frozenset(f[1:]): name for name, f in TABLES.items()}

ARTIFACTS = [
    "object_inventory.jsonl",
    "device_topology.json",
    "extent_map.tsv",
    "symlink_topology.jsonl",
    "mutation_replay.jsonl",
    "scope_resolution.csv",
    "link_clusters.jsonl",
    "resume_state.jsonl",
    "xattr_ledger.csv",
    "special_nodes.tsv",
    "placement.csv",
    "sharing_expansion.jsonl",
    "allocation_projection.csv",
    "delta_workset.tsv",
    "metadata_workset.jsonl",
    "window_schedule.tsv",
    "split_ledger.jsonl",
    "descriptor_budget.csv",
    "cutover_sequence.txt",
    "rollback_plan.jsonl",
    "conservation.json",
    "cli_contract.json",
    "manifest.json",
    "summary.json",
]

MANIFEST_ARTIFACTS = ARTIFACTS[: ARTIFACTS.index("cli_contract.json") + 1]


# ---------------------------------------------------------------------------
# value normalisation
# ---------------------------------------------------------------------------

def norm_value(v):
    """Collapse a parsed cell to either None (absent) or a string."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if not isinstance(v, str):
        v = str(v)
    if v == "NIL":
        return None
    return v


def as_int(v, default=0):
    if v is None or v == "":
        return default
    return int(v)


# ---------------------------------------------------------------------------
# escape handling
# ---------------------------------------------------------------------------

def unescape_backslash(s):
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "r":
                out.append("\r")
            else:
                out.append(nxt)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def unescape_tsv(s):
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "\\":
                out.append("\\")
            else:
                out.append("\\")
                out.append(nxt)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def split_quoted_pairs(s, delim=" "):
    """Split a logfmt style line into field=value pairs."""
    pairs = []
    i = 0
    n = len(s)
    while i < n:
        while i < n and s[i] == delim:
            i += 1
        if i >= n:
            break
        j = s.find("=", i)
        if j < 0:
            break
        key = s[i:j]
        j += 1
        if j < n and s[j] == '"':
            j += 1
            buf = []
            while j < n:
                if s[j] == "\\" and j + 1 < n:
                    buf.append(s[j])
                    buf.append(s[j + 1])
                    j += 2
                    continue
                if s[j] == '"':
                    j += 1
                    break
                buf.append(s[j])
                j += 1
            pairs.append((key, unescape_backslash("".join(buf))))
        else:
            k = s.find(delim, j)
            if k < 0:
                k = n
            pairs.append((key, s[j:k]))
            j = k
        i = j
    return pairs


# ---------------------------------------------------------------------------
# per-encoding parsers: each returns (list_of_dicts, keyed_flag)
# ---------------------------------------------------------------------------

def parse_delimited(text, delim, quoted):
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return []
    if quoted:
        reader = csv.reader(lines, delimiter=delim, quotechar='"',
                            doublequote=True)
        rows = list(reader)
    else:
        rows = [unescaped_split(line, delim) for line in lines]
    header = rows[0]
    out = []
    for row in rows[1:]:
        if not row or (len(row) == 1 and row[0] == ""):
            continue
        rec = {}
        for idx, name in enumerate(header):
            rec[name] = row[idx] if idx < len(row) else ""
        out.append(rec)
    return out


def unescaped_split(line, delim):
    return [unescape_tsv(part) for part in line.split(delim)]


def parse_fixed(text):
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return []
    header = lines[0]
    starts = []
    names = []
    for m in re.finditer(r"\S+", header):
        starts.append(m.start())
        names.append(m.group(0))
    bounds = []
    for i, st in enumerate(starts):
        en = starts[i + 1] if i + 1 < len(starts) else None
        bounds.append((st, en))
    out = []
    for line in lines[1:]:
        if line.strip() == "":
            continue
        rec = {}
        for name, (st, en) in zip(names, bounds):
            chunk = line[st:en] if en is not None else line[st:]
            rec[name] = chunk.strip()
        out.append(rec)
    return out


def parse_json(text):
    obj = json.loads(text)
    return list(obj["records"])


def parse_jsonl(text):
    out = []
    for line in text.split("\n"):
        if line.strip() == "":
            continue
        out.append(json.loads(line))
    return out


def parse_toml(text):
    records = []
    cur = None
    for line in text.split("\n"):
        s = line.strip()
        if s == "":
            continue
        if s.startswith("[["):
            cur = {}
            records.append(cur)
            continue
        if cur is None:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            cur[key] = unescape_backslash(val[1:-1])
        else:
            cur[key] = val
    return records


def parse_ini(text):
    records = []
    cur = None
    for line in text.split("\n"):
        s = line.strip()
        if s == "":
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = {"__key__": s[1:-1]}
            records.append(cur)
            continue
        if cur is None:
            continue
        key, _, val = s.partition("=")
        cur[key.strip()] = val.strip()
    return records


def unescape_properties(s):
    out = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "\\" and i + 1 < n:
            out.append(s[i + 1])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def parse_properties(text):
    order = []
    groups = {}
    for line in text.split("\n"):
        if line.strip() == "":
            continue
        key, _, val = line.partition("=")
        ident, _, field = key.rpartition(".")
        if ident not in groups:
            groups[ident] = {"__key__": ident}
            order.append(ident)
        groups[ident][field] = unescape_properties(val)
    return [groups[k] for k in order]


def parse_rfc822(text):
    records = []
    cur = None
    for line in text.split("\n"):
        if line.strip() == "":
            cur = None
            continue
        name, _, val = line.partition(":")
        field = name.strip().lower().replace("-", "_")
        if cur is None:
            cur = {}
            records.append(cur)
        cur[field] = val.strip()
    return records


def parse_logfmt(text):
    out = []
    for line in text.split("\n"):
        if line.strip() == "":
            continue
        out.append(dict(split_quoted_pairs(line)))
    return out


SEXP_FIELD = re.compile(r"\((\w+)\s+\"((?:[^\"\\]|\\.)*)\"\)")


def parse_sexp(text):
    out = []
    for line in text.split("\n"):
        if line.strip() == "":
            continue
        rec = {}
        for m in SEXP_FIELD.finditer(line):
            rec[m.group(1)] = unescape_backslash(m.group(2))
        if rec:
            out.append(rec)
    return out


RFC5424_INTRO = "[strata@41762 "


def parse_rfc5424(text):
    out = []
    for line in text.split("\n"):
        if line.strip() == "":
            continue
        start = line.find(RFC5424_INTRO)
        if start < 0:
            continue
        start += len(RFC5424_INTRO)
        end = line.rfind("]")
        body = line[start:end]
        rec = {}
        for key, val in split_quoted_pairs(body):
            rec[key] = val
        if rec:
            out.append(rec)
    return out


# ---------------------------------------------------------------------------
# encoding detection
# ---------------------------------------------------------------------------

def detect_parse(text):
    """Return (records, keyed) where keyed marks a format whose first schema
    field arrives as a section header or record identifier."""
    lines = [ln for ln in text.split("\n") if ln.strip() != ""]
    if not lines:
        return [], False
    first = lines[0]
    if first.startswith("<") and RFC5424_INTRO in text:
        return parse_rfc5424(text), False
    if first.lstrip().startswith("(record"):
        return parse_sexp(text), False
    if first.lstrip().startswith("{"):
        try:
            obj = json.loads(text)
        except ValueError:
            obj = None
        if isinstance(obj, dict) and "records" in obj:
            return parse_json(text), False
        return parse_jsonl(text), False
    if "[[record]]" in text:
        return parse_toml(text), False
    if re.match(r"^\[[^\[\]]+\]$", first):
        return parse_ini(text), True
    if re.match(r"^[^\s=]+\.[A-Za-z_][A-Za-z0-9_]*=", first):
        return parse_properties(text), True
    if re.match(r"^[A-Z][A-Za-z0-9-]*: ", first):
        return parse_rfc822(text), False
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", first):
        return parse_logfmt(text), False
    if "\t" in first:
        return parse_delimited(text, "\t", False), False
    if "|" in first:
        return parse_delimited(text, "|", True), False
    if "," in first:
        return parse_delimited(text, ",", True), False
    if re.search(r"\S  +\S", first):
        return parse_fixed(text), False
    if " " in first:
        return parse_delimited(text, " ", True), False
    return [], False


def load_corpus(corpus_dir):
    tables = defaultdict(list)
    for name in sorted(os.listdir(corpus_dir)):
        full = os.path.join(corpus_dir, name)
        if not os.path.isfile(full):
            continue
        try:
            with io.open(full, "r", encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        try:
            records, keyed = detect_parse(text)
        except Exception:
            continue
        if not records:
            continue
        fields = set()
        for rec in records[:8]:
            fields |= set(k for k in rec.keys() if k != "__key__")
        table = None
        if keyed:
            table = SCHEMA_BY_TAIL.get(frozenset(fields))
        if table is None:
            table = SCHEMA_BY_FIELDS.get(frozenset(fields))
        if table is None:
            continue
        schema = TABLES[table]
        for rec in records:
            row = {}
            if keyed:
                row[schema[0]] = norm_value(rec.get("__key__"))
            for field in schema:
                if field in rec:
                    row[field] = norm_value(rec[field])
                elif field not in row:
                    row[field] = None
            tables[table].append(row)
    return tables


# ---------------------------------------------------------------------------
# canonical forms
# ---------------------------------------------------------------------------

def nfc(s):
    return unicodedata.normalize("NFC", s)


def canon_path(raw):
    s = nfc(raw)
    stack = []
    for seg in s.split("/"):
        if seg == "" or seg == ".":
            continue
        if seg == "..":
            if stack:
                stack.pop()
            continue
        stack.append(seg)
    return "/" + "/".join(stack)


def path_depth(canon):
    if canon == "/":
        return 0
    return len(canon.strip("/").split("/"))


def first_segment(canon):
    if canon == "/":
        return ""
    return canon.strip("/").split("/")[0]


def canon_mode(raw):
    s = (raw or "").strip()
    if s == "":
        return "0000"
    if s[0] in "dD":
        val = int(s[1:], 10)
    elif s.startswith("0o") or s.startswith("0O"):
        val = int(s[2:], 8)
    else:
        val = int(s, 8)
    return format(val & 0o7777, "04o")


def canon_class(raw):
    return (raw or "").strip().lower()


def to_bytes(raw, unit):
    return as_int(raw) * UNIT_FACTOR.get(unit, 1)


def row_key(row, table):
    """A total order over the cells of a row, used only to break ties the
    specification leaves open so that input row order cannot leak out."""
    return tuple("" if row[f] is None else row[f] for f in TABLES[table])


def round_up(value, unit):
    if unit <= 0:
        return value
    return ((value + unit - 1) // unit) * unit


# ---------------------------------------------------------------------------
# output writers
# ---------------------------------------------------------------------------

class Emitter(object):
    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.blobs = {}

    def write(self, name, text):
        data = text.encode("utf-8")
        self.blobs[name] = data
        with io.open(os.path.join(self.out_dir, name), "wb") as fh:
            fh.write(data)


def csv_cell(value):
    s = value if isinstance(value, str) else str(value)
    if "," in s or '"' in s:
        return '"' + s.replace('"', '""') + '"'
    return s


def render_csv(header, rows):
    out = [",".join(csv_cell(c) for c in header)]
    for row in rows:
        out.append(",".join(csv_cell(c) for c in row))
    return "\n".join(out) + "\n"


def render_tsv(header, rows):
    out = ["\t".join(str(c) for c in header)]
    for row in rows:
        out.append("\t".join(str(c) for c in row))
    return "\n".join(out) + "\n"


def render_jsonl(objs):
    if not objs:
        return ""
    return "\n".join(json.dumps(o, ensure_ascii=False) for o in objs) + "\n"


def render_json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def render_lines(lines):
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def digest16(data):
    return hashlib.sha256(data).hexdigest()[:16]


# ---------------------------------------------------------------------------
# planner
# ---------------------------------------------------------------------------

def build_plan(corpus_dir, out_dir):
    tables = load_corpus(corpus_dir)
    em = Emitter(out_dir)

    # --- pools -----------------------------------------------------------
    pools = {}
    for row in sorted(tables["pool"], key=lambda r: row_key(r, "pool"),
                      reverse=True):
        pools[row["pool_id"]] = {
            "alloc_unit": as_int(row["alloc_unit"]),
            "root_depth_cap": as_int(row["root_depth_cap"]),
            "region": row["region"] or "",
        }

    # --- barriers --------------------------------------------------------
    barrier_rows = defaultdict(list)
    for row in tables["barrier"]:
        barrier_rows[row["pool_id"]].append(row)
    barriers = {}
    for pid, rows in barrier_rows.items():
        best = max(rows, key=lambda r: (as_int(r["effective_seq"]),
                                        as_int(r["rev"]),
                                        row_key(r, "barrier")))
        barriers[pid] = as_int(best["barrier_seq"])

    # --- devices ---------------------------------------------------------
    cap_rows = defaultdict(list)
    for row in tables["capacity"]:
        cap_rows[row["device_id"]].append(row)
    geo_rows = defaultdict(list)
    for row in tables["geometry"]:
        geo_rows[row["device_id"]].append(row)

    device_ids = sorted(set(cap_rows) | set(geo_rows))
    window_rows = defaultdict(list)
    for row in tables["window"]:
        window_rows[(row["device_id"], as_int(row["window_index"]))].append(row)
    windows_by_dev = defaultdict(dict)
    for (did, widx), rows in window_rows.items():
        row = min(rows, key=lambda r: row_key(r, "window"))
        windows_by_dev[did][widx] = {
            "budget": to_bytes(row["io_budget_raw"], row["io_budget_unit"]),
            "descriptors": as_int(row["descriptor_budget"]),
        }

    devices = {}
    for did in device_ids:
        cap = None
        if cap_rows[did]:
            cap = max(cap_rows[did],
                      key=lambda r: (as_int(r["effective_seq"]),
                                     as_int(r["rev"]),
                                     row_key(r, "capacity")))
        geo = None
        if geo_rows[did]:
            geo = max(geo_rows[did],
                      key=lambda r: (as_int(r["effective_seq"]),
                                     as_int(r["rev"]),
                                     row_key(r, "geometry")))
        capacity = to_bytes(cap["capacity_raw"], cap["capacity_unit"]) if cap else 0
        existing = to_bytes(cap["existing_used_raw"],
                            cap["existing_used_unit"]) if cap else 0
        reserve_ppm = as_int(cap["reserve_ppm"]) if cap else 0
        reserve = capacity * reserve_ppm // 1000000
        wins = windows_by_dev.get(did, {})
        win_idx = sorted(wins)
        devices[did] = {
            "device_id": did,
            "capacity_bytes": capacity,
            "existing_used_bytes": existing,
            "reserve_ppm": reserve_ppm,
            "reserve_bytes": reserve,
            "usable_bytes": capacity - reserve,
            "alloc_unit": as_int(geo["alloc_unit"]) if geo else 0,
            "share_domain": (geo["share_domain"] or "") if geo else "",
            "spill_device": (geo["spill_device"] or "") if geo else "",
            "online": 1 if (geo and (geo["online"] or "").lower() == "true") else 0,
            "windows": len(win_idx),
            "io_budget_bytes": sum(wins[i]["budget"] for i in win_idx),
            "descriptor_peak": max((wins[i]["descriptors"] for i in win_idx),
                                   default=0),
            "window_index": win_idx,
            "window_info": wins,
        }

    topo_devices = []
    for did in device_ids:
        d = devices[did]
        topo_devices.append({
            "device_id": d["device_id"],
            "capacity_bytes": d["capacity_bytes"],
            "existing_used_bytes": d["existing_used_bytes"],
            "reserve_ppm": d["reserve_ppm"],
            "reserve_bytes": d["reserve_bytes"],
            "usable_bytes": d["usable_bytes"],
            "alloc_unit": d["alloc_unit"],
            "share_domain": d["share_domain"],
            "spill_device": d["spill_device"],
            "online": d["online"],
            "windows": d["windows"],
            "io_budget_bytes": d["io_budget_bytes"],
            "descriptor_peak": d["descriptor_peak"],
        })
    domain_count = len(set(d["share_domain"] for d in devices.values()))

    # --- routes ----------------------------------------------------------
    routes = {}
    for row in tables["route"]:
        key = (canon_class(row["class"]), row["pool_id"])
        rid = row["route_id"]
        if key not in routes or (rid, row_key(row, "route")) < routes[key][0]:
            routes[key] = ((rid, row_key(row, "route")), row["device_id"])

    # --- objects ---------------------------------------------------------
    obj_rows = defaultdict(list)
    for row in tables["object"]:
        obj_rows[as_int(row["ino"])].append(row)
    objects = {}
    for ino in sorted(obj_rows):
        rows = obj_rows[ino]
        best = max(rows, key=lambda r: (as_int(r["gen"]), as_int(r["mtime_ns"]),
                                        row_key(r, "object")))
        objects[ino] = {
            "ino": ino,
            "kind": best["kind"],
            "size_bytes": to_bytes(best["size_raw"], best["size_unit"]),
            "mode": canon_mode(best["mode_raw"]),
            "uid": as_int(best["uid"]),
            "gid": as_int(best["gid"]),
            "mtime_ns": as_int(best["mtime_ns"]),
            "class": canon_class(best["class_raw"]),
            "pool_id": best["pool_id"],
            "declared_link_count": as_int(best["link_count"]),
            "state": best["state"],
            "superseded_rows": len(rows) - 1,
            "size_unit": best["size_unit"],
        }
    inos = sorted(objects)

    inventory = []
    for ino in inos:
        o = objects[ino]
        inventory.append({
            "ino": o["ino"],
            "kind": o["kind"],
            "size_bytes": o["size_bytes"],
            "mode": o["mode"],
            "uid": o["uid"],
            "gid": o["gid"],
            "mtime_ns": o["mtime_ns"],
            "class": o["class"],
            "pool_id": o["pool_id"],
            "declared_link_count": o["declared_link_count"],
            "state": o["state"],
            "superseded_rows": o["superseded_rows"],
            "size_unit": o["size_unit"],
        })

    def pool_alloc_unit(ino):
        pid = objects[ino]["pool_id"]
        if pid in pools:
            return pools[pid]["alloc_unit"]
        return DEFAULT_POOL_ALLOC_UNIT

    # --- extents ---------------------------------------------------------
    ext_rows = defaultdict(dict)
    for row in tables["extent"]:
        ino = as_int(row["ino"])
        idx = as_int(row["ext_index"])
        prev = ext_rows[ino].get(idx)
        if prev is None or (as_int(row["gen"]), row_key(row, "extent")) > (
                as_int(prev["gen"]), row_key(prev, "extent")):
            ext_rows[ino][idx] = row

    extents = {}
    extent_map_rows = []
    for ino in inos:
        if objects[ino]["kind"] != "regular":
            continue
        size = objects[ino]["size_bytes"]
        au = pool_alloc_unit(ino)
        last_end = 0
        per = {}
        for idx in sorted(ext_rows.get(ino, {})):
            row = ext_rows[ino][idx]
            offset = as_int(row["offset"])
            length = to_bytes(row["length_raw"], row["length_unit"])
            raw_flags = row["flags"] or ""
            flagset = set()
            for word in raw_flags.split(","):
                word = word.strip()
                if word and word != "none":
                    flagset.add(word)
            repairs = []
            if length > 0 and offset < last_end:
                delta = last_end - offset
                offset = last_end
                length -= delta
                repairs.append("truncated")
            if length > 0 and offset + length > size:
                length = size - offset
                repairs.append("clipped")
            if length <= 0:
                length = 0
                repair = "void"
                void = True
            else:
                void = False
                repair = "+".join(repairs) if repairs else "none"
            if void:
                pclass = "void"
            elif "hole" in flagset:
                pclass = "hole"
            elif "inline" in flagset:
                pclass = "inline"
            elif "unwritten" in flagset:
                pclass = "reserved"
            else:
                pclass = "data"
            if pclass in ("data", "reserved"):
                rpb = round_up(length, au)
            else:
                rpb = 0
            flags_text = "+".join(f for f in FLAG_ORDER if f in flagset) or "none"
            rec = {
                "ino": ino,
                "ext_index": idx,
                "offset": offset,
                "length": length,
                "end": offset + length,
                "physical_id": row["physical_id"] or "",
                "physical_class": pclass,
                "raw_physical_bytes": rpb,
                "flags": flags_text,
                "repair": repair,
            }
            per[idx] = rec
            extent_map_rows.append(rec)
            if not void:
                last_end = offset + length
        extents[ino] = per

    # --- path records ----------------------------------------------------
    paths_by_ino = defaultdict(list)
    for row in tables["path"]:
        ino = as_int(row["ino"])
        paths_by_ino[ino].append({
            "canon": canon_path(row["path_raw"] or ""),
            "ordinal": as_int(row["ordinal"]),
            "form": row["form"] or "",
        })

    # path index before replay: canonical path -> lowest inode
    path_index = {}
    for ino in sorted(paths_by_ino):
        for rec in paths_by_ino[ino]:
            if rec["canon"] not in path_index:
                path_index[rec["canon"]] = ino
    index_first_segments = set(first_segment(p) for p in path_index)

    # --- symlinks --------------------------------------------------------
    symlink_rec = {}
    for row in tables["symlink"]:
        ino = as_int(row["ino"])
        prev = symlink_rec.get(ino)
        if prev is None or row_key(row, "symlink") < row_key(prev, "symlink"):
            symlink_rec[ino] = row

    def lowest_ordinal_parent(ino):
        recs = paths_by_ino.get(ino)
        if not recs:
            return "/"
        rec = min(recs, key=lambda r: (r["ordinal"], r["canon"]))
        canon = rec["canon"]
        if canon == "/":
            return "/"
        parent = canon.rsplit("/", 1)[0]
        return parent if parent else "/"

    def symlink_target_canon(ino):
        row = symlink_rec.get(ino)
        if row is None:
            return None
        target = nfc(row["target_raw"] or "")
        if target.startswith("/"):
            return canon_path(target)
        return canon_path(lowest_ordinal_parent(ino) + "/" + target)

    symlink_rows = []
    for ino in inos:
        if objects[ino]["kind"] != "symlink":
            continue
        row = symlink_rec.get(ino)
        if row is None:
            target = ""
            arrival = ""
        else:
            target = nfc(row["target_raw"] or "")
            arrival = row["form"] or ""
        tbytes = len(target.encode("utf-8"))
        kind = "absolute" if target.startswith("/") else "relative"
        fast = 1 if tbytes <= FAST_SYMLINK_MAX else 0
        physical = 0 if fast else pool_alloc_unit(ino)

        hops = 0
        seen = set()
        cur = ino
        resolution = ""
        while True:
            tgt = symlink_target_canon(cur)
            if tgt is None:
                resolution = "outside"
                break
            if tgt in seen:
                resolution = "cyclic"
                break
            seen.add(tgt)
            if tgt in path_index:
                nxt = path_index[tgt]
                if objects.get(nxt, {}).get("kind") == "symlink":
                    hops += 1
                    if hops == HOP_CAP:
                        resolution = "capped"
                        break
                    cur = nxt
                    continue
                resolution = "inside"
                break
            if first_segment(tgt) in index_first_segments:
                resolution = "dangling"
            else:
                resolution = "outside"
            break
        symlink_rows.append({
            "ino": ino,
            "arrival_form": arrival,
            "target": target,
            "target_bytes": tbytes,
            "kind": kind,
            "resolution": resolution,
            "hops": hops,
            "fast": fast,
            "physical_bytes": physical,
        })

    # --- xattrs ----------------------------------------------------------
    xattr_best = {}
    for row in tables["xattr"]:
        ino = as_int(row["ino"])
        name = nfc(row["name"] or "")
        key = (ino, name)
        prev = xattr_best.get(key)
        if prev is None or (as_int(row["gen"]), row["xattr_id"] or "",
                            row_key(row, "xattr")) > (
                as_int(prev["gen"]), prev["xattr_id"] or "",
                row_key(prev, "xattr")):
            xattr_best[key] = row
    xattrs = defaultdict(dict)
    for (ino, name), row in xattr_best.items():
        xattrs[ino][name] = as_int(row["value_len"])

    # --- holds, claims, deadlines ---------------------------------------
    holds = defaultdict(list)
    for row in tables["hold"]:
        holds[as_int(row["ino"])].append(row)
    claims = defaultdict(list)
    for row in tables["claim"]:
        claims[as_int(row["ino"])].append(row)
    deadlines = {}
    for row in tables["deadline"]:
        ino = as_int(row["ino"])
        prev = deadlines.get(ino)
        if prev is None or row_key(row, "deadline") < row_key(prev, "deadline"):
            deadlines[ino] = row

    # --- special nodes ---------------------------------------------------
    special_best = {}
    for row in tables["special"]:
        ino = as_int(row["ino"])
        prev = special_best.get(ino)
        if prev is None or (row["node_id"] or "",
                            row_key(row, "special")) < (
                prev["node_id"] or "", row_key(prev, "special")):
            special_best[ino] = row

    # --- replay ----------------------------------------------------------
    live_paths = {}
    for ino in inos:
        live_paths[ino] = [dict(r) for r in paths_by_ino.get(ino, [])]
    state = {ino: objects[ino]["state"] for ino in inos}
    sizes = {ino: objects[ino]["size_bytes"] for ino in inos}
    live_xattrs = {ino: dict(xattrs.get(ino, {})) for ino in inos}

    events = []
    for row in tables["activity"]:
        events.append({
            "seq": as_int(row["seq"]),
            "ordinal": as_int(row["ordinal"]),
            "kind": row["kind"] or "",
            "ino": as_int(row["ino"]),
            "path_a": nfc(row["path_a"]) if row["path_a"] is not None else "",
            "path_b": nfc(row["path_b"]) if row["path_b"] is not None else "",
            "arg_num": as_int(row["arg_num"]),
            "arg_alt": as_int(row["arg_alt"]),
        })
    events.sort(key=lambda e: (e["seq"], e["ordinal"], e["kind"], e["ino"],
                               e["path_a"], e["path_b"], e["arg_num"],
                               e["arg_alt"]))

    writes = defaultdict(list)
    truncates = defaultdict(list)
    renamed = set()
    replay_rows = []
    for ev in events:
        ino = ev["ino"]
        kind = ev["kind"]
        ca = canon_path(ev["path_a"])
        if kind in ("unlink", "rename", "link"):
            target_text = ca
        elif kind == "setxattr":
            target_text = ev["path_a"]
        elif kind == "write":
            target_text = "%d:%d" % (ev["arg_num"], ev["arg_alt"])
        elif kind in ("truncate", "chmod", "chown"):
            target_text = str(ev["arg_num"])
        else:
            target_text = ""

        if ino not in objects:
            effect, reason = "ignored", "unknown_inode"
        elif objects[ino]["pool_id"] not in pools:
            effect, reason = "ignored", "unknown_pool"
        elif ev["seq"] <= barriers.get(objects[ino]["pool_id"], 0):
            effect, reason = "absorbed", "at_or_before_barrier"
        elif kind in ("unlink", "rename") and ca not in set(
                r["canon"] for r in live_paths[ino]):
            effect, reason = "ignored", "unknown_path"
        else:
            effect, reason = "applied", ""

        if effect == "applied":
            if kind == "unlink":
                live_paths[ino] = [r for r in live_paths[ino]
                                   if r["canon"] != ca]
                if not live_paths[ino]:
                    state[ino] = "pruned"
            elif kind == "rename":
                cb = canon_path(ev["path_b"])
                for r in live_paths[ino]:
                    if r["canon"] == ca:
                        r["canon"] = cb
                renamed.add(ino)
            elif kind == "link":
                nxt = max((r["ordinal"] for r in live_paths[ino]), default=0) + 1
                live_paths[ino].append({"canon": ca, "ordinal": nxt,
                                        "form": "nfc"})
            elif kind == "hold":
                state[ino] = "held"
            elif kind == "release":
                state[ino] = "live"
            elif kind == "setxattr":
                live_xattrs[ino][ev["path_a"]] = ev["arg_num"]
            elif kind == "write":
                writes[ino].append((ev["arg_num"],
                                    ev["arg_num"] + ev["arg_alt"], ev["seq"]))
            elif kind == "truncate":
                truncates[ino].append((ev["arg_num"], ev["seq"]))
                sizes[ino] = ev["arg_num"]

        replay_rows.append({
            "seq": ev["seq"],
            "ordinal": ev["ordinal"],
            "kind": kind,
            "ino": ino,
            "target": target_text,
            "effect": effect,
            "reason": reason,
        })

    # --- primary paths and clusters -------------------------------------
    primary = {}
    tiebreak = {}
    member_paths = {}
    for ino in inos:
        recs = live_paths[ino]
        if not recs:
            primary[ino] = ""
            tiebreak[ino] = 0
            member_paths[ino] = []
            continue
        cands = [{
            "canon": r["canon"],
            "depth": path_depth(r["canon"]),
            "nbytes": len(r["canon"].encode("utf-8")),
            "ordinal": r["ordinal"],
        } for r in recs]
        if len(recs) == 1:
            primary[ino] = cands[0]["canon"]
            tiebreak[ino] = 0
        else:
            level = 0
            pool_c = cands
            for lvl, key in enumerate(
                    [lambda c: c["depth"], lambda c: c["nbytes"],
                     lambda c: c["canon"], lambda c: c["ordinal"]], start=1):
                best = min(key(c) for c in pool_c)
                pool_c = [c for c in pool_c if key(c) == best]
                if len(pool_c) == 1:
                    level = lvl
                    break
                level = lvl
            primary[ino] = pool_c[0]["canon"]
            tiebreak[ino] = level
        distinct = sorted(set(r["canon"] for r in recs))
        member_paths[ino] = [p for p in distinct if p != primary[ino]]

    # --- relocatable verdict --------------------------------------------
    relocatable = {}
    reason_of = {}
    depth_of = {}
    for ino in inos:
        o = objects[ino]
        recs = live_paths[ino]
        depth = path_depth(primary[ino]) if recs else 0
        depth_of[ino] = depth
        nclaims = len(claims.get(ino, []))
        if o["pool_id"] not in pools:
            ok, reason = False, "unknown_pool"
        elif state[ino] != "live" or not recs:
            ok, reason = False, "not_live"
        elif nclaims != 1:
            ok, reason = False, ("unclaimed" if nclaims == 0 else "contested")
        elif depth > pools[o["pool_id"]]["root_depth_cap"]:
            ok, reason = False, "depth_exceeded"
        else:
            ok, reason = True, ""
        relocatable[ino] = ok
        reason_of[ino] = reason

    reloc_inos = [i for i in inos if relocatable[i]]

    scope_rows = []
    for ino in inos:
        o = objects[ino]
        active = [h for h in holds.get(ino, [])
                  if (h["active"] or "").lower() == "true"]
        hold_reasons = "+".join(sorted(set(h["reason"] or "" for h in active)))
        cl = claims.get(ino, [])
        claim_sets = "+".join(sorted(set(c["set_name"] or "" for c in cl)))
        scope_rows.append([
            ino,
            o["class"],
            o["pool_id"] or "",
            pools[o["pool_id"]]["region"] if o["pool_id"] in pools else "",
            1 if relocatable[ino] else 0,
            reason_of[ino],
            len(set(r["canon"] for r in live_paths[ino])),
            len(active),
            hold_reasons,
            len(cl),
            claim_sets,
            depth_of[ino],
        ])

    cluster_rows = []
    for ino in reloc_inos:
        cluster_rows.append({
            "ino": ino,
            "primary_path": primary[ino],
            "tiebreak_level": tiebreak[ino],
            "member_paths": member_paths[ino],
            "link_ops": len(member_paths[ino]),
            "arrival_forms": sum(1 for r in live_paths[ino]
                                 if r["form"] == "nfd"),
        })

    # --- checkpoint groups ----------------------------------------------
    groups = defaultdict(list)
    for row in tables["checkpoint"]:
        key = (as_int(row["ino"]), as_int(row["ext_index"]))
        groups[key].append(row)

    ckpt = {}
    for (ino, idx), rows in groups.items():
        if ino not in objects:
            continue
        pid = objects[ino]["pool_id"]
        barrier = barriers.get(pid)
        eligible = []
        if barrier is not None:
            eligible = [r for r in rows if as_int(r["seq"]) <= barrier]
        ext = extents.get(ino, {}).get(idx)
        expected = ext["raw_physical_bytes"] if ext else 0
        if not eligible:
            ckpt[(ino, idx)] = {
                "seq": min(as_int(r["seq"]) for r in rows),
                "committed": -1,
                "expected": expected,
                "status": "after_barrier",
                "invalidated_by": 0,
            }
            continue
        best = max(eligible, key=lambda r: (
            as_int(r["seq"]),
            (0, 0) if r["bytes_committed"] is None
            else (1, as_int(r["bytes_committed"])),
            row_key(r, "checkpoint"),
        ))
        raw_committed = best["bytes_committed"]
        seq = as_int(best["seq"])
        if raw_committed is None:
            status = "never_started"
            committed_out = -1
        else:
            committed = as_int(raw_committed)
            committed_out = committed
            if committed == expected:
                status = "durable"
            elif committed > expected:
                status = "overrun"
            elif committed == 0:
                status = "zeroed"
            else:
                status = "partial"
        invalidated_by = 0
        if status == "durable" and ext is not None:
            eo = ext["offset"]
            ee = ext["offset"] + ext["length"]
            undo_seqs = []
            for ws, we, wseq in writes.get(ino, []):
                if ws < ee and eo < we:
                    undo_seqs.append(wseq)
            for newsize, tseq in truncates.get(ino, []):
                if newsize < ee:
                    undo_seqs.append(tseq)
            if undo_seqs:
                status = "redirty"
                invalidated_by = min(undo_seqs)
        ckpt[(ino, idx)] = {
            "seq": seq,
            "committed": committed_out,
            "expected": expected,
            "status": status,
            "invalidated_by": invalidated_by,
        }

    resume_rows = []
    for (ino, idx) in sorted(ckpt):
        if not relocatable.get(ino):
            continue
        if idx not in extents.get(ino, {}):
            continue
        g = ckpt[(ino, idx)]
        resume_rows.append({
            "ino": ino,
            "ext_index": idx,
            "seq": g["seq"],
            "committed": g["committed"],
            "expected": g["expected"],
            "status": g["status"],
            "invalidated_by": g["invalidated_by"],
        })

    # --- xattr ledger ----------------------------------------------------
    def xattr_namespace(name):
        return name.split(".", 1)[0] if "." in name else name

    def migrates(name, klass):
        ns = xattr_namespace(name)
        if ns in ("user", "trusted"):
            return True
        if ns == "security":
            return klass in ("gold", "silver")
        if ns == "system":
            return name in ("system.posix_acl_access",
                            "system.posix_acl_default")
        return False

    migrated_names = {}
    xattr_rows = []
    for ino in reloc_inos:
        klass = objects[ino]["class"]
        mig, drop = [], []
        for name in sorted(live_xattrs.get(ino, {})):
            vlen = live_xattrs[ino][name]
            size = len(name.encode("utf-8")) + 1 + vlen
            if migrates(name, klass):
                mig.append((name, size))
            else:
                drop.append((name, size))
        migrated_names[ino] = [n for n, _ in mig]
        namespaces = "+".join(sorted(set(xattr_namespace(n) for n, _ in mig)))
        xattr_rows.append([
            ino,
            len(mig),
            len(drop),
            sum(s for _, s in mig),
            sum(s for _, s in drop),
            mig[0][0] if mig else "",
            namespaces,
        ])

    # --- special nodes ---------------------------------------------------
    special_rows = []
    node_verb = {}
    node_detail = {}
    for ino in reloc_inos:
        kind = objects[ino]["kind"]
        if kind not in ("fifo", "socket", "chardev", "blockdev"):
            continue
        row = special_best.get(ino)
        if row is None:
            major = 0
            minor = 0
            overflow = 0
            verb = "skip" if kind in ("chardev", "blockdev") else (
                "mkfifo" if kind == "fifo" else "bind")
            rdev = 0
        else:
            major = as_int(row["major"])
            raw_minor = as_int(row["minor"])
            overflow = 1 if raw_minor > 255 else 0
            minor = raw_minor % 256 if overflow else raw_minor
            rdev = major * 256 + minor
            verb = {"fifo": "mkfifo", "socket": "bind",
                    "chardev": "mknod", "blockdev": "mknod"}[kind]
        special_rows.append([ino, kind, major, minor, rdev, overflow, verb])
        node_verb[ino] = verb
        node_detail[ino] = "%d:%d" % (major, minor)

    # --- placement -------------------------------------------------------
    online_devices = [d for d in device_ids if devices[d]["online"] == 1]
    lowest_online = online_devices[0] if online_devices else (
        device_ids[0] if device_ids else "")

    initial_device = {}
    initial_reason = {}
    for ino in reloc_inos:
        o = objects[ino]
        route = routes.get((o["class"], o["pool_id"]))
        reason = ""
        if route is None or route[1] not in devices:
            dev = lowest_online
            reason = "unrouted"
        else:
            dev = route[1]
        hops = 0
        while devices[dev]["online"] == 0 and hops < SPILL_HOPS:
            nxt = devices[dev]["spill_device"]
            if nxt not in devices:
                break
            dev = nxt
            hops += 1
        if devices[dev]["online"] == 0:
            reason = "offline_chain"
        elif hops > 0:
            reason = "offline_spill"
        initial_device[ino] = dev
        initial_reason[ino] = reason

    # extents participating in sharing/attribution per object
    share_exts = {}
    for ino in reloc_inos:
        lst = []
        for idx in sorted(extents.get(ino, {})):
            ext = extents[ino][idx]
            if ext["physical_class"] in ("data", "reserved"):
                lst.append(ext)
        share_exts[ino] = lst

    def compute_attribution(placement):
        """Return (owner_map, attributed) for the given placement.

        owner_map maps (physical_id, domain) -> (ino, ext_index).
        """
        by_pid = defaultdict(lambda: defaultdict(list))
        for ino in reloc_inos:
            if not share_exts[ino]:
                continue
            domain = devices[placement[ino]]["share_domain"]
            for ext in share_exts[ino]:
                by_pid[ext["physical_id"]][domain].append(ext)
        owner = {}
        for pid, doms in by_pid.items():
            for domain, exts_l in doms.items():
                holders = sorted(set(e["ino"] for e in exts_l))
                best_ino = min(holders, key=lambda i: (primary[i], i))
                best_idx = min(e["ext_index"] for e in exts_l
                               if e["ino"] == best_ino)
                owner[(pid, domain)] = (best_ino, best_idx)
        attributed = {}
        owned = defaultdict(list)
        for ino in reloc_inos:
            domain = devices[placement[ino]]["share_domain"]
            total = 0
            for ext in share_exts[ino]:
                if owner.get((ext["physical_id"], domain)) == (ino, ext["ext_index"]):
                    total += ext["raw_physical_bytes"]
                    owned[ino].append(ext)
            attributed[ino] = total
        return owner, attributed, owned, by_pid

    placement = dict(initial_device)
    shed_round = {ino: 0 for ino in reloc_inos}
    ever_shed = set()
    evicted_out = defaultdict(int)
    received_in = defaultdict(int)

    for rnd in range(1, MAX_ROUNDS + 1):
        _, attributed, _, _ = compute_attribution(placement)
        claim = defaultdict(int)
        on_device = defaultdict(set)
        for ino in reloc_inos:
            claim[placement[ino]] += attributed[ino]
            on_device[placement[ino]].add(ino)
        shed_this_round = 0
        for did in device_ids:
            d = devices[did]
            headroom = d["usable_bytes"] - (d["existing_used_bytes"] + claim[did])
            if headroom >= 0:
                continue
            spill = d["spill_device"]
            if spill == did or spill not in devices:
                continue
            cands = [i for i in on_device[did] if i not in ever_shed]
            if not cands:
                continue
            pick = min(cands, key=lambda i: (
                -CLASS_RANK.get(objects[i]["class"], len(CLASS_ORDER)),
                -attributed[i], primary[i], i))
            placement[pick] = spill
            ever_shed.add(pick)
            shed_round[pick] = rnd
            evicted_out[did] += 1
            received_in[spill] += 1
            on_device[did].discard(pick)
            on_device[spill].add(pick)
            claim[did] -= attributed[pick]
            claim[spill] += attributed[pick]
            shed_this_round += 1
        if shed_this_round == 0:
            break

    owner, attributed, owned_exts, by_pid = compute_attribution(placement)

    placement_rows = []
    for ino in reloc_inos:
        dl = deadlines.get(ino)
        dev = placement[ino]
        reason = "evicted" if shed_round[ino] else initial_reason[ino]
        placement_rows.append([
            ino,
            objects[ino]["class"],
            initial_device[ino],
            dev,
            devices[dev]["share_domain"],
            1 if dev != initial_device[ino] else 0,
            shed_round[ino],
            reason,
            attributed[ino],
            as_int(dl["deadline_window"]) if dl else 0,
            (dl["class_override"] or "") if dl else "",
        ])

    sharing_rows = []
    for pid in sorted(by_pid):
        doms = by_pid[pid]
        all_inos = sorted(set(e["ino"] for d in doms.values() for e in d))
        if len(all_inos) < 2:
            continue
        dom_names = sorted(doms)
        unit = max(e["raw_physical_bytes"] for d in doms.values() for e in d)
        sharing_rows.append({
            "physical_id": pid,
            "referencing_inodes": all_inos,
            "domains": dom_names,
            "copies": len(dom_names),
            "owners": [owner[(pid, dm)][0] for dm in dom_names],
            "unit_bytes": unit,
            "expanded_bytes": unit * (len(dom_names) - 1),
        })

    # --- delta work set --------------------------------------------------
    domain_class = {}
    for pid, doms in by_pid.items():
        for dm, exts_l in doms.items():
            best = min(CLASS_RANK.get(objects[e["ino"]]["class"],
                                      len(CLASS_ORDER)) for e in exts_l)
            domain_class[(pid, dm)] = CLASS_ORDER[best]

    copy_items = []
    for ino in reloc_inos:
        domain = devices[placement[ino]]["share_domain"]
        dl = deadlines.get(ino)
        dwin = as_int(dl["deadline_window"]) if dl else 0
        for ext in owned_exts.get(ino, []):
            if ext["physical_class"] != "data":
                continue
            g = ckpt.get((ino, ext["ext_index"]))
            if g is not None and g["status"] == "durable":
                continue
            if g is None:
                origin = "fresh"
            elif g["status"] == "redirty":
                origin = "redirty"
            else:
                origin = "restart"
            eclass = domain_class[(ext["physical_id"], domain)]
            copy_items.append({
                "ino": ino,
                "ext_index": ext["ext_index"],
                "device_id": placement[ino],
                "physical_id": ext["physical_id"],
                "copy_bytes": ext["raw_physical_bytes"],
                "origin": origin,
                "effective_class": eclass,
                "deadline_window": dwin,
            })
    copy_items.sort(key=lambda it: (
        CLASS_RANK[it["effective_class"]], it["deadline_window"],
        primary[it["ino"]], it["ino"], it["ext_index"]))

    # --- window schedule -------------------------------------------------
    remaining = {}
    open_inodes = {}
    win_bytes = {}
    win_desc = {}
    for did in device_ids:
        for widx in devices[did]["window_index"]:
            remaining[(did, widx)] = devices[did]["window_info"][widx]["budget"]
            open_inodes[(did, widx)] = set()
            win_bytes[(did, widx)] = 0
            win_desc[(did, widx)] = 0

    schedule_rows = []
    split_rows = []
    deferred_bytes = defaultdict(int)
    deferred_objects = set()
    placed_total = defaultdict(int)

    for item in copy_items:
        did = item["device_id"]
        ino = item["ino"]
        size = item["copy_bytes"]
        widxs = devices[did]["window_index"]
        au = devices[did]["alloc_unit"]
        max_budget = max((devices[did]["window_info"][w]["budget"]
                          for w in widxs), default=0)
        lowest_with_room = None
        for w in widxs:
            if remaining[(did, w)] > 0:
                lowest_with_room = w
                break

        placements = []

        def admit(w):
            key = (did, w)
            if ino in open_inodes[key]:
                return True
            return len(open_inodes[key]) < devices[did]["window_info"][w]["descriptors"]

        def place(w, amount):
            key = (did, w)
            opened = 0 if ino in open_inodes[key] else 1
            open_inodes[key].add(ino)
            remaining[key] -= amount
            win_bytes[key] += amount
            win_desc[key] += opened
            placements.append((w, amount, opened))

        if size <= max_budget:
            chosen = None
            for w in widxs:
                if remaining[(did, w)] >= size and admit(w):
                    chosen = w
                    break
            if chosen is not None:
                place(chosen, size)
                residual = 0
            else:
                residual = size
        else:
            residual = size
            for w in widxs:
                if residual <= 0:
                    break
                key = (did, w)
                if not admit(w):
                    continue
                if remaining[key] < au or remaining[key] <= 0:
                    continue
                room = remaining[key]
                if residual <= room:
                    take = residual
                else:
                    take = (room // au) * au if au > 0 else room
                if take <= 0:
                    continue
                place(w, take)
                residual -= take

        for ci, (w, amount, opened) in enumerate(placements):
            schedule_rows.append([did, w, ino, item["ext_index"], ci, amount,
                                  opened])
        total_placed = sum(a for _, a, _ in placements)
        placed_total[did] += total_placed
        if residual > 0:
            status = "deferred"
            deferred_bytes[did] += residual
            deferred_objects.add(ino)
        elif len(placements) == 1:
            status = "whole" if placements[0][0] == lowest_with_room else "rolled"
        else:
            status = "split"
        if status != "whole":
            split_rows.append({
                "ino": ino,
                "ext_index": item["ext_index"],
                "device_id": did,
                "status": status,
                "chunks": len(placements),
                "placed_bytes": total_placed,
                "residual_bytes": residual,
                "first_window": placements[0][0] if placements else -1,
                "last_window": placements[-1][0] if placements else -1,
            })

    schedule_rows.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[4]))
    split_rows.sort(key=lambda r: (r["ino"], r["ext_index"]))

    desc_rows = []
    for did in device_ids:
        for w in devices[did]["window_index"]:
            info = devices[did]["window_info"][w]
            budget = info["budget"]
            used = win_bytes[(did, w)]
            ppm = (used * 1000000 // budget) if budget else 0
            desc_rows.append([did, w, info["descriptors"], win_desc[(did, w)],
                              budget, used, ppm])

    # --- metadata work set ----------------------------------------------
    RANK = {"mkdir": 1, "mknod": 2, "mkfifo": 2, "bind": 2, "symlink": 3,
            "link": 4, "reflink": 5, "fallocate": 6, "setxattr": 7,
            "chown": 8, "chmod": 9, "utimes": 10}
    symlink_target = {r["ino"]: r["target"] for r in symlink_rows}
    meta_rows = []
    for ino in reloc_inos:
        o = objects[ino]
        p = primary[ino]
        ops = []
        if o["kind"] == "dir":
            ops.append(("mkdir", "", 0))
        verb = node_verb.get(ino)
        if verb is not None and verb != "skip":
            ops.append((verb, node_detail[ino], 0))
        if o["kind"] == "symlink":
            ops.append(("symlink", symlink_target.get(ino, ""), 0))
        for mp in member_paths[ino]:
            ops.append(("link", mp, 0))
        domain = devices[placement[ino]]["share_domain"]
        for idx in sorted(extents.get(ino, {})):
            ext = extents[ino][idx]
            if ext["physical_class"] == "data":
                if owner.get((ext["physical_id"], domain)) != (ino, idx):
                    ops.append(("reflink", ext["physical_id"],
                                ext["raw_physical_bytes"]))
            elif ext["physical_class"] == "reserved":
                ops.append(("fallocate", str(idx), ext["raw_physical_bytes"]))
        for name in migrated_names.get(ino, []):
            ops.append(("setxattr", name, 0))
        ops.append(("chown", "%d:%d" % (o["uid"], o["gid"]), 0))
        ops.append(("chmod", o["mode"], 0))
        ops.append(("utimes", str(o["mtime_ns"]), 0))
        ops.sort(key=lambda t: (RANK[t[0]], t[1]))
        for op, detail, nbytes in ops:
            meta_rows.append({"op": op, "ino": ino, "path": p,
                              "detail": detail, "bytes": nbytes})

    # --- cutover and rollback -------------------------------------------
    ready = [i for i in reloc_inos if i not in deferred_objects]
    cutover = sorted(ready, key=lambda i: (path_depth(primary[i]),
                                           primary[i], i))
    cutover_lines = [primary[i] for i in cutover]

    has_copy_item = defaultdict(bool)
    for item in copy_items:
        has_copy_item[item["ino"]] = True
    redirty_obj = defaultdict(bool)
    for row in resume_rows:
        if row["status"] == "redirty":
            redirty_obj[row["ino"]] = True

    def guard_for(ino):
        if redirty_obj[ino]:
            return "digest_match"
        if has_copy_item[ino]:
            return "size_match"
        return "xattr_count_match"

    def barrier_for(ino):
        return barriers.get(objects[ino]["pool_id"], 0)

    rollback_rows = []
    step = 0
    for ino in cutover:
        step += 1
        if member_paths[ino]:
            reverse = "restore_link"
        elif ino in renamed:
            reverse = "rename_back"
        else:
            reverse = "unlink_target"
        rollback_rows.append({
            "step": step,
            "ino": ino,
            "path": primary[ino],
            "guard": guard_for(ino),
            "reverse": reverse,
            "barrier_seq": barrier_for(ino),
        })
    for ino in sorted(deferred_objects):
        rollback_rows.append({
            "step": 0,
            "ino": ino,
            "path": primary[ino],
            "guard": guard_for(ino),
            "reverse": "abort_hold",
            "barrier_seq": barrier_for(ino),
        })

    # --- conservation ----------------------------------------------------
    resumed_bytes = defaultdict(int)
    reserved_bytes = defaultdict(int)
    attributed_dev = defaultdict(int)
    for ino in reloc_inos:
        did = placement[ino]
        attributed_dev[did] += attributed[ino]
        for ext in owned_exts.get(ino, []):
            if ext["physical_class"] == "reserved":
                reserved_bytes[did] += ext["raw_physical_bytes"]
            elif ext["physical_class"] == "data":
                g = ckpt.get((ino, ext["ext_index"]))
                if g is not None and g["status"] == "durable":
                    resumed_bytes[did] += ext["raw_physical_bytes"]

    cons_devices = []
    balanced = 0
    for did in device_ids:
        total = attributed_dev[did]
        copied = placed_total[did]
        res = resumed_bytes[did]
        rsv = reserved_bytes[did]
        dfr = deferred_bytes[did]
        residual = total - copied - res - rsv - dfr
        if residual == 0:
            balanced += 1
        cons_devices.append({
            "device_id": did,
            "attributed_bytes": total,
            "copied_bytes": copied,
            "resumed_bytes": res,
            "reserved_bytes": rsv,
            "deferred_bytes": dfr,
            "residual_bytes": residual,
        })

    alloc_rows = []
    for did in device_ids:
        d = devices[did]
        claim_b = attributed_dev[did]
        projected = d["existing_used_bytes"] + claim_b
        headroom = d["usable_bytes"] - projected
        placed_objects = sum(1 for i in reloc_inos if placement[i] == did)
        alloc_rows.append([
            did, d["capacity_bytes"], d["reserve_bytes"], d["usable_bytes"],
            d["existing_used_bytes"], claim_b, projected, headroom,
            1 if headroom < 0 else 0, placed_objects, evicted_out[did],
            received_in[did],
        ])

    # --- emit ------------------------------------------------------------
    em.write("object_inventory.jsonl", render_jsonl(inventory))
    em.write("device_topology.json", render_json({
        "devices": topo_devices,
        "device_count": len(device_ids),
        "domain_count": domain_count,
    }))
    em.write("extent_map.tsv", render_tsv(
        ["ino", "ext_index", "offset", "length_bytes", "end_offset",
         "physical_id", "physical_class", "raw_physical_bytes", "flags",
         "repair"],
        [[r["ino"], r["ext_index"], r["offset"], r["length"], r["end"],
          r["physical_id"], r["physical_class"], r["raw_physical_bytes"],
          r["flags"], r["repair"]]
         for r in sorted(extent_map_rows,
                         key=lambda r: (r["ino"], r["ext_index"]))]))
    em.write("symlink_topology.jsonl", render_jsonl(symlink_rows))
    em.write("mutation_replay.jsonl", render_jsonl(replay_rows))
    em.write("scope_resolution.csv", render_csv(
        ["ino", "class", "pool_id", "pool_region", "relocatable", "reason",
         "paths_after_replay", "hold_notices", "hold_reasons", "claims",
         "claim_sets", "depth"], scope_rows))
    em.write("link_clusters.jsonl", render_jsonl(cluster_rows))
    em.write("resume_state.jsonl", render_jsonl(resume_rows))
    em.write("xattr_ledger.csv", render_csv(
        ["ino", "migrated_count", "dropped_count", "migrated_bytes",
         "dropped_bytes", "first_migrated_name", "namespaces"], xattr_rows))
    em.write("special_nodes.tsv", render_tsv(
        ["ino", "node_kind", "major", "minor", "rdev", "overflow",
         "recreate"], special_rows))
    em.write("placement.csv", render_csv(
        ["ino", "class", "initial_device", "device", "share_domain", "moved",
         "round", "reason", "attributed_bytes", "deadline_window",
         "class_override"], placement_rows))
    em.write("sharing_expansion.jsonl", render_jsonl(sharing_rows))
    em.write("allocation_projection.csv", render_csv(
        ["device_id", "capacity_bytes", "reserve_bytes", "usable_bytes",
         "existing_used_bytes", "claim_bytes", "projected_bytes",
         "headroom_bytes", "over_committed", "placed_objects", "evicted_out",
         "received_in"], alloc_rows))
    em.write("delta_workset.tsv", render_tsv(
        ["ino", "ext_index", "device_id", "physical_id", "copy_bytes",
         "origin", "effective_class", "deadline_window"],
        [[it["ino"], it["ext_index"], it["device_id"], it["physical_id"],
          it["copy_bytes"], it["origin"], it["effective_class"],
          it["deadline_window"]] for it in copy_items]))
    em.write("metadata_workset.jsonl", render_jsonl(meta_rows))
    em.write("window_schedule.tsv", render_tsv(
        ["device_id", "window_index", "ino", "ext_index", "chunk_index",
         "bytes", "descriptor_opened"], schedule_rows))
    em.write("split_ledger.jsonl", render_jsonl(split_rows))
    em.write("descriptor_budget.csv", render_csv(
        ["device_id", "window_index", "descriptor_budget", "descriptors_used",
         "io_budget_bytes", "bytes_used", "utilisation_ppm"], desc_rows))
    em.write("cutover_sequence.txt", render_lines(cutover_lines))
    em.write("rollback_plan.jsonl", render_jsonl(rollback_rows))
    em.write("conservation.json", render_json({
        "devices": cons_devices,
        "balanced_devices": balanced,
        "unbalanced_devices": len(device_ids) - balanced,
    }))
    em.write("cli_contract.json", render_json({
        "tool": "stratactl",
        "usage": "stratactl.py CORPUS_DIR OUT_DIR",
        "exit_ok": EXIT_OK,
        "exit_usage": EXIT_USAGE,
        "exit_policy": EXIT_POLICY,
        "artifact_count": len(ARTIFACTS),
    }))

    manifest = {"artifacts": []}
    for name in MANIFEST_ARTIFACTS:
        data = em.blobs[name]
        manifest["artifacts"].append({
            "name": name,
            "rows": data.count(b"\n"),
            "bytes": len(data),
            "digest": digest16(data),
        })
    em.write("manifest.json", render_json(manifest))

    joined = "\n".join(a["digest"] for a in manifest["artifacts"])
    em.write("summary.json", render_json({
        "relocatable_objects": len(reloc_inos),
        "excluded_objects": len(inos) - len(reloc_inos),
        "clusters": len(cluster_rows),
        "copy_items": len(copy_items),
        "metadata_ops": len(meta_rows),
        "cutover_steps": len(cutover_lines),
        "manifest_digest": digest16(joined.encode("utf-8")),
    }))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: stratactl.py CORPUS_DIR OUT_DIR\n")
        return EXIT_USAGE
    corpus_dir = argv[1]
    out_dir = argv[2]
    if not os.path.isdir(corpus_dir):
        sys.stderr.write("corpus path does not resolve to a directory\n")
        return EXIT_POLICY
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    build_plan(corpus_dir, out_dir)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
