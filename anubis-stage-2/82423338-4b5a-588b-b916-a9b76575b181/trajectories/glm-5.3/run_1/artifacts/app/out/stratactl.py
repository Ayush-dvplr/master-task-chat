#!/usr/bin/env python3
"""STRATA relocation planner.

Usage: stratactl.py CORPUS_DIR OUT_DIR

Reads the flat corpus under CORPUS_DIR, detects the encoding and the record
schema of every file from its content alone, and writes the relocation plan as
twenty-four artifacts into OUT_DIR.  Imports nothing beyond the standard
library, reads nothing outside the corpus directory and reaches no network.
"""

import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_POLICY = 3
ARTIFACT_COUNT = 24

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

UNIT_FACTORS = {
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

CLASS_RANK = {"gold": 0, "silver": 1, "bronze": 2, "tin": 3}
CLASS_ORDER = ["gold", "silver", "bronze", "tin"]

EXTENT_FLAG_ORDER = ["hole", "unwritten", "inline", "shared", "sealed"]

OP_RANK = {
    "mkdir": 1,
    "mknod": 2,
    "mkfifo": 2,
    "bind": 2,
    "symlink": 3,
    "link": 4,
    "reflink": 5,
    "fallocate": 6,
    "setxattr": 7,
    "chown": 8,
    "chmod": 9,
    "utimes": 10,
}

SCHEMAS = {
    "pool": ["pool_id", "alloc_unit", "root_depth_cap", "region"],
    "barrier": ["pool_id", "rev", "barrier_seq", "effective_seq"],
    "capacity": [
        "device_id", "rev", "capacity_raw", "capacity_unit",
        "existing_used_raw", "existing_used_unit", "reserve_ppm", "effective_seq",
    ],
    "geometry": [
        "slot_id", "device_id", "rev", "share_domain", "spill_device",
        "online", "alloc_unit", "effective_seq",
    ],
    "window": ["device_id", "window_index", "io_budget_raw", "io_budget_unit", "descriptor_budget"],
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
    "event": ["seq", "ordinal", "kind", "ino", "path_a", "path_b", "arg_num", "arg_alt"],
}

SCHEMA_BY_FIELDS = {tuple(sorted(v)): k for k, v in SCHEMAS.items()}
SCHEMA_BY_FIELDS_ORDER = {tuple(v): k for k, v in SCHEMAS.items()}
SCHEMA_BY_REST = {tuple(sorted(v[1:])): k for k, v in SCHEMAS.items()}


# --------------------------------------------------------------------------
# value helpers
# --------------------------------------------------------------------------

def norm_value(v):
    """Normalise a raw parsed value to a string, or None for absence."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(int(v)) if float(v).is_integer() else repr(v)
    s = str(v)
    return None if s == "NIL" else s


def as_int(v, default=0):
    if v is None or v == "":
        return default
    return int(v)


def as_bool(v):
    if v is None:
        return 0
    return 1 if str(v).strip().lower() in ("true", "1", "t", "yes", "y", "on") else 0


def unescape(s, pairs):
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n and s[i + 1] in pairs:
            out.append(pairs[s[i + 1]])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


TSV_UNESCAPE = {"\\": "\\", "t": "\t", "n": "\n"}
LOGFMT_UNESCAPE = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r"}
QUOTED_UNESCAPE = {"\\": "\\", '"': '"'}
RFC5424_UNESCAPE = {"\\": "\\", '"': '"', "]": "]"}
PROPS_UNESCAPE = {"\\": "\\", ":": ":", "=": "="}


def size_bytes(raw, unit):
    return as_int(raw) * UNIT_FACTORS[unit]


def canonical_mode(raw):
    s = (raw or "").strip()
    if s.startswith("0o") or s.startswith("0O"):
        val = int(s[2:], 8) if s[2:] else 0
    elif s.startswith("d") or s.startswith("D"):
        val = int(s[1:]) if s[1:] else 0
    else:
        val = int(s, 8) if s else 0
    return "%04o" % (val & 0o7777)


def canonical_class(raw):
    return (raw or "").lower()


def canonical_path(raw):
    p = unicodedata.normalize("NFC", raw or "")
    segs = []
    for seg in p.split("/"):
        if seg == "" or seg == ".":
            continue
        if seg == "..":
            if segs:
                segs.pop()
            continue
        segs.append(seg)
    return "/" + "/".join(segs) if segs else "/"


def path_depth(cp):
    if cp == "/":
        return 0
    return len(cp.split("/")) - 1


def parent_path(cp):
    i = cp.rfind("/")
    if i <= 0:
        return "/"
    return cp[:i]


def utf8_len(s):
    return len(s.encode("utf-8"))


# --------------------------------------------------------------------------
# corpus parsing
# --------------------------------------------------------------------------

def parse_json(text):
    s = text.lstrip()
    if not s.startswith("{"):
        return None
    try:
        doc = json.loads(text)
    except ValueError:
        return None
    if not isinstance(doc, dict) or "records" not in doc or not isinstance(doc["records"], list):
        return None
    recs = [r for r in doc["records"] if isinstance(r, dict)]
    if not recs:
        return None
    key = tuple(sorted(norm_value(k) for k in recs[0]))
    name = SCHEMA_BY_FIELDS.get(key)
    if name is None:
        return None
    fields = SCHEMAS[name]
    out = []
    for r in recs:
        d = {}
        for f in fields:
            d[f] = norm_value(r.get(f))
        out.append(d)
    return name, out


def parse_jsonl(text):
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines or not lines[0].lstrip().startswith("{"):
        return None
    try:
        recs = [json.loads(l) for l in lines]
    except ValueError:
        return None
    if not recs or not all(isinstance(r, dict) for r in recs):
        return None
    key = tuple(sorted(norm_value(k) for k in recs[0]))
    name = SCHEMA_BY_FIELDS.get(key)
    if name is None:
        return None
    fields = SCHEMAS[name]
    out = []
    for r in recs:
        d = {}
        for f in fields:
            d[f] = norm_value(r.get(f))
        out.append(d)
    return name, out


def parse_toml(text):
    if "[[record]]" not in text:
        return None
    blocks = text.split("[[record]]")
    recs = []
    for block in blocks[1:]:
        d = {}
        for line in block.split("\n"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
                val = unescape(val[1:-1], QUOTED_UNESCAPE)
            d[key] = val
        if d:
            recs.append(d)
    if not recs:
        return None
    key = tuple(sorted(recs[0]))
    name = SCHEMA_BY_FIELDS.get(key)
    if name is None:
        return None
    fields = SCHEMAS[name]
    return name, [{f: norm_value(r.get(f)) for f in fields} for r in recs]


def parse_ini(text):
    lines = text.split("\n")
    sections = []
    cur = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = (line[1:-1], {})
            sections.append(cur)
            continue
        if "=" in line and cur is not None:
            k, _, v = line.partition("=")
            cur[1][k.strip()] = v.strip()
    if not sections:
        return None
    first_rest = tuple(sorted(sections[0][1]))
    name = SCHEMA_BY_REST.get(first_rest)
    if name is None:
        return None
    fields = SCHEMAS[name]
    out = []
    for ident, body in sections:
        d = {fields[0]: ident}
        for f in fields[1:]:
            d[f] = norm_value(body.get(f))
        out.append(d)
    return name, out


def parse_rfc5424(text):
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines or "[strata@41762 " not in lines[0]:
        return None
    recs = []
    for line in lines:
        i = line.find("[strata@41762 ")
        if i < 0:
            return None
        j = line.rfind("]")
        if j < i:
            return None
        sd = line[i + len("[strata@41762 "):j]
        d = {}
        for m in re.finditer(r'([A-Za-z0-9_]+)="((?:[^"\\]|\\.)*)"', sd):
            d[m.group(1)] = unescape(m.group(2), RFC5424_UNESCAPE)
        recs.append(d)
    key = tuple(sorted(recs[0]))
    name = SCHEMA_BY_FIELDS.get(key)
    if name is None:
        return None
    fields = SCHEMAS[name]
    return name, [{f: norm_value(r.get(f)) for f in fields} for r in recs]


def parse_sexp(text):
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines or not lines[0].startswith("(record"):
        return None
    recs = []
    for line in lines:
        if not line.startswith("(record"):
            return None
        d = {}
        for m in re.finditer(r'\(([A-Za-z0-9_]+)\s+"((?:[^"\\]|\\.)*)"\)', line):
            d[m.group(1)] = unescape(m.group(2), QUOTED_UNESCAPE)
        recs.append(d)
    key = tuple(sorted(recs[0]))
    name = SCHEMA_BY_FIELDS.get(key)
    if name is None:
        return None
    fields = SCHEMAS[name]
    return name, [{f: norm_value(r.get(f)) for f in fields} for r in recs]


RFC822_HEADER = re.compile(r"^([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*):\s*(.*)$")


def parse_rfc822(text):
    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    if not blocks:
        return None
    recs = []
    for block in blocks:
        d = {}
        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = RFC822_HEADER.match(line)
            if not m:
                return None
            field = m.group(1).lower().replace("-", "_")
            d[field] = m.group(2).strip()
        recs.append(d)
    key = tuple(sorted(recs[0]))
    name = SCHEMA_BY_FIELDS.get(key)
    if name is None:
        return None
    fields = SCHEMAS[name]
    return name, [{f: norm_value(r.get(f)) for f in fields} for r in recs]


def parse_properties(text):
    lines = [l for l in text.split("\n") if l.strip()]
    groups = []
    cur = None
    for line in lines:
        head, sep, val = line.partition("=")
        if not sep or "." not in head:
            return None
        dot = head.rfind(".")
        ident = head[:dot]
        field = head[dot + 1:]
        if not ident or not re.match(r"^[A-Za-z0-9_]+$", field):
            return None
        val = unescape(val, PROPS_UNESCAPE)
        if cur is None or cur[0] != ident:
            cur = (ident, {})
            groups.append(cur)
        cur[1][field] = val
    if not groups:
        return None
    first_rest = tuple(sorted(groups[0][1]))
    name = SCHEMA_BY_REST.get(first_rest)
    if name is None:
        return None
    fields = SCHEMAS[name]
    out = []
    for ident, body in groups:
        d = {fields[0]: ident}
        for f in fields[1:]:
            d[f] = norm_value(body.get(f))
        out.append(d)
    return name, out


LOGFMT_TOKEN = re.compile(r'(?:^|\s)([A-Za-z0-9_]+)=("(?:[^"\\]|\\.)*"?|[^ ]*)')


def parse_logfmt(text):
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return None
    recs = []
    for line in lines:
        d = {}
        pos = 0
        ok = True
        for m in LOGFMT_TOKEN.finditer(line):
            if line[pos:m.start()].strip():
                ok = False
                break
            key = m.group(1)
            val = m.group(2)
            if val.startswith('"'):
                body = val[1:]
                if body.endswith('"') and len(val) > 1:
                    body = body[:-1]
                val = unescape(body, LOGFMT_UNESCAPE)
            d[key] = val
            pos = m.end()
        if not ok or line[pos:].strip() or not d:
            return None
        recs.append(d)
    key = tuple(sorted(recs[0]))
    name = SCHEMA_BY_FIELDS.get(key)
    if name is None:
        return None
    fields = SCHEMAS[name]
    return name, [{f: norm_value(r.get(f)) for f in fields} for r in recs]


def parse_fixed(text):
    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return None
    hdr = lines[0].rstrip()
    if not re.match(r"^\S+(?:\s{2,}\S+)+$", hdr):
        return None
    pos = [(m.group(0), m.start()) for m in re.finditer(r"\S+", hdr)]
    name = SCHEMA_BY_FIELDS_ORDER.get(tuple(p[0] for p in pos))
    if name is None:
        name = SCHEMA_BY_FIELDS.get(tuple(sorted(p[0] for p in pos)))
    if name is None:
        return None
    fields = SCHEMAS[name]
    recs = []
    for line in lines[1:]:
        if not line.strip():
            continue
        d = {}
        for i, (fname, st) in enumerate(pos):
            en = pos[i + 1][1] if i + 1 < len(pos) else len(line)
            d[fname] = line[st:en].rstrip() if st < len(line) else ""
        recs.append(d)
    return name, [{f: norm_value(r.get(f)) for f in fields} for r in recs]


def _split_delimited(line, delim):
    if delim == "\t":
        return [unescape(c, TSV_UNESCAPE) for c in line.split("\t")]
    cells = []
    i = 0
    n = len(line)
    while True:
        if i < n and line[i] == '"':
            j = i + 1
            buf = []
            while j < n:
                if line[j] == '"':
                    if j + 1 < n and line[j + 1] == '"':
                        buf.append('"')
                        j += 2
                        continue
                    break
                buf.append(line[j])
                j += 1
            cells.append("".join(buf))
            i = j + 1
            if i >= n:
                return cells
            if line[i] != delim:
                return None
            i += 1
            if i == n:
                cells.append("")
                return cells
        else:
            j = line.find(delim, i)
            if j < 0:
                cells.append(line[i:])
                return cells
            cells.append(line[i:j])
            i = j + 1
            if i == n:
                cells.append("")
                return cells


def parse_delimited(text):
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return None
    for delim in (",", "\t", "|", " "):
        header = _split_delimited(lines[0], delim)
        if header is None:
            continue
        name = SCHEMA_BY_FIELDS_ORDER.get(tuple(header))
        if name is None:
            name = SCHEMA_BY_FIELDS.get(tuple(sorted(header)))
        if name is None:
            continue
        fields = SCHEMAS[name]
        recs = []
        for line in lines[1:]:
            cells = _split_delimited(line, delim)
            if cells is None or len(cells) != len(fields):
                return None
            recs.append({f: norm_value(c) for f, c in zip(fields, cells)})
        return name, recs
    return None


PARSERS = (
    parse_json, parse_jsonl, parse_toml, parse_ini, parse_rfc5424, parse_sexp,
    parse_rfc822, parse_properties, parse_logfmt, parse_delimited, parse_fixed,
)


def load_corpus(corpus_dir):
    tables = defaultdict(list)
    for entry in sorted(os.listdir(corpus_dir)):
        path = os.path.join(corpus_dir, entry)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        if not text.strip():
            continue
        for parser in PARSERS:
            res = parser(text)
            if res is not None:
                tables[res[0]].extend(res[1])
                break
    return tables


# --------------------------------------------------------------------------
# output helpers
# --------------------------------------------------------------------------

def json_line(obj):
    return json.dumps(obj, ensure_ascii=False)


def json_pretty(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)


def csv_cell(v):
    s = "" if v is None else str(v)
    if "," in s or '"' in s:
        return '"' + s.replace('"', '""') + '"'
    return s


def csv_row(cells):
    return ",".join(csv_cell(c) for c in cells)


def tsv_row(cells):
    return "\t".join("" if c is None else str(c) for c in cells)


def sha16(data):
    return hashlib.sha256(data).hexdigest()[:16]


# --------------------------------------------------------------------------
# the planner
# --------------------------------------------------------------------------

class Plan(object):
    def __init__(self, corpus_dir):
        self.tables = load_corpus(corpus_dir)
        self.build_estate()
        self.build_objects()
        self.build_extents()
        self.build_symlink_resolution()
        self.replay()
        self.build_scope()
        self.build_placement()
        self.build_worksets()
        self.build_schedule()
        self.build_cutover()

    # ----- estate ---------------------------------------------------------

    def build_estate(self):
        t = self.tables
        pools = {}
        for r in t["pool"]:
            pools[r["pool_id"]] = r
        self.pools = pools

        barriers = {}
        best = {}
        for r in t["barrier"]:
            key = r["pool_id"]
            cand = (as_int(r["effective_seq"]), as_int(r["rev"]))
            if key not in best or cand > best[key][0]:
                best[key] = (cand, r)
        for key, (_, r) in best.items():
            barriers[key] = as_int(r["barrier_seq"])
        self.barriers = barriers

        cap = {}
        best = {}
        for r in t["capacity"]:
            key = r["device_id"]
            cand = (as_int(r["effective_seq"]), as_int(r["rev"]))
            if key not in best or cand > best[key][0]:
                best[key] = (cand, r)
        for key, (_, r) in best.items():
            cap[key] = {
                "capacity_bytes": size_bytes(r["capacity_raw"], r["capacity_unit"]),
                "existing_used_bytes": size_bytes(r["existing_used_raw"], r["existing_used_unit"]),
                "reserve_ppm": as_int(r["reserve_ppm"]),
            }
        self.capacities = cap

        geo = {}
        best = {}
        for r in t["geometry"]:
            key = r["device_id"]
            cand = (as_int(r["effective_seq"]), as_int(r["rev"]))
            if key not in best or cand > best[key][0]:
                best[key] = (cand, r)
        for key, (_, r) in best.items():
            geo[key] = {
                "share_domain": r["share_domain"] or "",
                "spill_device": r["spill_device"] or "",
                "online": as_bool(r["online"]),
                "alloc_unit": as_int(r["alloc_unit"]),
            }
        self.geometries = geo

        win = defaultdict(dict)
        for r in t["window"]:
            win[r["device_id"]][as_int(r["window_index"])] = {
                "budget": size_bytes(r["io_budget_raw"], r["io_budget_unit"]),
                "desc": as_int(r["descriptor_budget"]),
            }
        self.windows = {d: dict(v) for d, v in win.items()}

        routes = {}
        best = {}
        for r in t["route"]:
            key = (canonical_class(r["class"]), r["pool_id"])
            if key not in best or r["route_id"] < best[key]["route_id"]:
                best[key] = r
        for key, r in best.items():
            routes[key] = r["device_id"]
        self.routes = routes

        device_ids = sorted(set(cap) | set(geo) | set(win))
        self.device_ids = device_ids
        self.devices = {}
        for d in device_ids:
            c = cap.get(d, {"capacity_bytes": 0, "existing_used_bytes": 0, "reserve_ppm": 0})
            g = geo.get(d, {"share_domain": "", "spill_device": "", "online": 0, "alloc_unit": 0})
            reserve = c["capacity_bytes"] * c["reserve_ppm"] // 1000000
            w = win.get(d, {})
            self.devices[d] = {
                "device_id": d,
                "capacity_bytes": c["capacity_bytes"],
                "existing_used_bytes": c["existing_used_bytes"],
                "reserve_ppm": c["reserve_ppm"],
                "reserve_bytes": reserve,
                "usable_bytes": c["capacity_bytes"] - reserve,
                "alloc_unit": g["alloc_unit"],
                "share_domain": g["share_domain"],
                "spill_device": g["spill_device"],
                "online": g["online"],
                "windows": w,
            }

    def pool_alloc_unit(self, pool_id):
        p = self.pools.get(pool_id)
        if p is None:
            return DEFAULT_POOL_ALLOC_UNIT
        return as_int(p["alloc_unit"]) or DEFAULT_POOL_ALLOC_UNIT

    def pool_depth_cap(self, pool_id):
        p = self.pools.get(pool_id)
        if p is None:
            return None
        return as_int(p["root_depth_cap"])

    # ----- objects --------------------------------------------------------

    def build_objects(self):
        t = self.tables
        best = {}
        counts = defaultdict(int)
        for r in t["object"]:
            ino = as_int(r["ino"])
            counts[ino] += 1
            cand = (as_int(r["gen"]), as_int(r["mtime_ns"]))
            if ino not in best or cand > best[ino][0]:
                best[ino] = (cand, r)
        self.objects = {}
        for ino, (_, r) in best.items():
            self.objects[ino] = {
                "ino": ino,
                "kind": r["kind"] or "",
                "size_bytes": size_bytes(r["size_raw"], r["size_unit"]),
                "size_unit": r["size_unit"] or "",
                "mode": canonical_mode(r["mode_raw"]),
                "uid": as_int(r["uid"]),
                "gid": as_int(r["gid"]),
                "mtime_ns": as_int(r["mtime_ns"]),
                "class": canonical_class(r["class_raw"]),
                "pool_id": r["pool_id"] or "",
                "declared_link_count": as_int(r["link_count"]),
                "state": r["state"] or "",
                "superseded_rows": counts[ino] - 1,
            }

        # path records, kept in record form
        paths = defaultdict(list)
        for r in t["path"]:
            paths[as_int(r["ino"])].append({
                "path": canonical_path(r["path_raw"]),
                "ordinal": as_int(r["ordinal"]),
                "form": r["form"] or "",
            })
        for lst in paths.values():
            lst.sort(key=lambda p: (p["ordinal"], p["path"]))
        self.base_paths = paths

        # xattrs: authoritative per (ino, name)
        xbest = {}
        for r in t["xattr"]:
            key = (as_int(r["ino"]), r["name"])
            cand = (as_int(r["gen"]), r["xattr_id"] or "")
            if key not in xbest or cand > xbest[key][0]:
                xbest[key] = (cand, r)
        self.base_xattrs = defaultdict(dict)
        for (ino, name), (_, r) in xbest.items():
            self.base_xattrs[ino][name] = as_int(r["value_len"])

        # symlinks
        self.symlink_targets = {}
        for r in t["symlink"]:
            self.symlink_targets[as_int(r["ino"])] = {
                "target": unicodedata.normalize("NFC", r["target_raw"] or ""),
                "form": r["form"] or "",
            }

        # special nodes: authoritative per ino = smallest node_id
        sbest = {}
        for r in t["special"]:
            ino = as_int(r["ino"])
            if ino not in sbest or (r["node_id"] or "") < (sbest[ino]["node_id"] or ""):
                sbest[ino] = r
        self.specials = sbest

        # claims
        claims = defaultdict(list)
        for r in t["claim"]:
            claims[as_int(r["ino"])].append(r["set_name"] or "")
        self.claims = claims

        # deadlines
        deadlines = {}
        for r in t["deadline"]:
            deadlines[as_int(r["ino"])] = (as_int(r["deadline_window"]), r["class_override"] or "")
        self.deadlines = deadlines

        # holds
        holds = defaultdict(list)
        for r in t["hold"]:
            holds[as_int(r["ino"])].append((r["reason"] or "", as_bool(r["active"])))
        self.holds = holds

        # checkpoint groups
        groups = defaultdict(list)
        for r in t["checkpoint"]:
            groups[(as_int(r["ino"]), as_int(r["ext_index"]))].append(r)
        self.checkpoints = groups

        # events
        events = []
        for r in t["event"]:
            events.append({
                "seq": as_int(r["seq"]),
                "ordinal": as_int(r["ordinal"]),
                "kind": r["kind"] or "",
                "ino": as_int(r["ino"]),
                "path_a": r["path_a"] or "",
                "path_b": r["path_b"] or "",
                "arg_num": as_int(r["arg_num"]),
                "arg_alt": as_int(r["arg_alt"]),
            })
        events.sort(key=lambda e: (e["seq"], e["ordinal"], e["kind"], e["ino"]))
        self.events = events

    # ----- extents --------------------------------------------------------

    def build_extents(self):
        best = {}
        for r in self.tables["extent"]:
            key = (as_int(r["ino"]), as_int(r["ext_index"]))
            cand = as_int(r["gen"])
            if key not in best or cand > best[key][0]:
                best[key] = (cand, r)
        extents = defaultdict(dict)
        for (ino, idx), (_, r) in best.items():
            flags = [f.strip() for f in (r["flags"] or "").split(",") if f.strip()]
            if flags == ["none"]:
                flags = []
            extents[ino][idx] = {
                "ino": ino,
                "ext_index": idx,
                "offset": as_int(r["offset"]),
                "length": size_bytes(r["length_raw"], r["length_unit"]),
                "physical_id": r["physical_id"] or "",
                "flags": flags,
                "gen": as_int(r["gen"]),
            }
        # repairs
        for ino, emap in list(extents.items()):
            size = self.objects[ino]["size_bytes"] if ino in self.objects else 0
            end = 0
            for idx in sorted(emap):
                e = emap[idx]
                repairs = []
                if e["offset"] < end:
                    delta = end - e["offset"]
                    e["length"] -= delta
                    e["offset"] = end
                    repairs.append("truncated")
                if e["offset"] + e["length"] > size:
                    e["length"] = size - e["offset"]
                    repairs.append("clipped")
                if e["length"] <= 0:
                    e["length"] = 0
                    e["repair"] = "void"
                else:
                    end = e["offset"] + e["length"]
                    e["repair"] = "+".join(repairs) if repairs else "none"
                fl = set(e["flags"])
                if e["repair"] == "void":
                    e["pclass"] = "void"
                elif "hole" in fl:
                    e["pclass"] = "hole"
                elif "inline" in fl:
                    e["pclass"] = "inline"
                elif "unwritten" in fl:
                    e["pclass"] = "reserved"
                else:
                    e["pclass"] = "data"
                au = self.pool_alloc_unit(self.objects[ino]["pool_id"] if ino in self.objects else None)
                if e["pclass"] in ("data", "reserved"):
                    e["raw_physical_bytes"] = ((e["length"] + au - 1) // au) * au
                else:
                    e["raw_physical_bytes"] = 0
                e["end_offset"] = e["offset"] + e["length"]
                e["flag_text"] = "+".join(f for f in EXTENT_FLAG_ORDER if f in fl) if fl else "none"
        self.extents = extents

    def extent_map_rows(self):
        rows = []
        for ino in sorted(self.objects):
            if self.objects[ino]["kind"] != "regular":
                continue
            for idx in sorted(self.extents.get(ino, {})):
                e = self.extents[ino][idx]
                rows.append([
                    ino, idx, e["offset"], e["length"], e["end_offset"],
                    e["physical_id"], e["pclass"], e["raw_physical_bytes"],
                    e["flag_text"], e["repair"],
                ])
        return rows

    # ----- symlinks -------------------------------------------------------

    def build_symlink_resolution(self):
        index = {}
        for ino, lst in self.base_paths.items():
            for p in lst:
                cp = p["path"]
                if cp not in index or ino < index[cp]:
                    index[cp] = ino
        self.path_index = index
        first_segments = set()
        for cp in index:
            segs = cp.split("/")
            if len(segs) > 1 and segs[1]:
                first_segments.add(segs[1])
        self.first_segments = first_segments

    def resolve_symlink(self, ino):
        info = self.symlink_targets.get(ino)
        target = info["target"] if info else ""
        paths = self.base_paths.get(ino, [])
        base = parent_path(paths[0]["path"]) if paths else "/"
        hops = 0
        reached = set()
        cur = canonical_path(target) if target.startswith("/") else canonical_path(base + "/" + target)
        while True:
            if cur in reached:
                return "cyclic", hops
            reached.add(cur)
            if cur in self.path_index:
                named = self.path_index[cur]
                kind = self.objects[named]["kind"] if named in self.objects else ""
                if kind != "symlink":
                    return "inside", hops
                hops += 1
                if hops >= 8:
                    return "capped", hops
                ninfo = self.symlink_targets.get(named)
                ntarget = ninfo["target"] if ninfo else ""
                npaths = self.base_paths.get(named, [])
                nbase = parent_path(npaths[0]["path"]) if npaths else "/"
                cur = canonical_path(ntarget) if ntarget.startswith("/") else canonical_path(nbase + "/" + ntarget)
            else:
                segs = cur.split("/")
                first = segs[1] if len(segs) > 1 else ""
                return ("dangling" if first in self.first_segments else "outside"), hops

    # ----- replay ---------------------------------------------------------

    def replay(self):
        self.live_paths = {}
        self.live_xattrs = {}
        self.states = {}
        self.sizes = {}
        self.renamed_inodes = set()
        replay_rows = []
        for ino in self.objects:
            self.live_paths[ino] = [dict(p) for p in self.base_paths.get(ino, [])]
            self.live_xattrs[ino] = dict(self.base_xattrs.get(ino, {}))
            self.states[ino] = self.objects[ino]["state"]
            self.sizes[ino] = self.objects[ino]["size_bytes"]

        self.applied_events = []
        for ev in self.events:
            ino = ev["ino"]
            reason = ""
            effect = "applied"
            if ino not in self.objects:
                effect, reason = "ignored", "unknown_inode"
            elif self.objects[ino]["pool_id"] not in self.pools:
                effect, reason = "ignored", "unknown_pool"
            elif ev["seq"] <= self.barriers.get(self.objects[ino]["pool_id"], -1):
                effect, reason = "absorbed", "at_or_before_barrier"
            else:
                kind = ev["kind"]
                canon_a = canonical_path(ev["path_a"])
                if kind in ("unlink", "rename") and canon_a not in self.held_paths(ino):
                    effect, reason = "ignored", "unknown_path"
                else:
                    self.apply_event(ev, canon_a)
                    self.applied_events.append(ev)
            target = self.event_target(ev)
            replay_rows.append({
                "seq": ev["seq"], "ordinal": ev["ordinal"], "kind": ev["kind"],
                "ino": ino, "target": target, "effect": effect, "reason": reason,
            })
        self.replay_rows = replay_rows

    def held_paths(self, ino):
        return set(p["path"] for p in self.live_paths.get(ino, []))

    def event_target(self, ev):
        kind = ev["kind"]
        if kind in ("unlink", "rename", "link"):
            return canonical_path(ev["path_a"])
        if kind == "setxattr":
            return ev["path_a"]
        if kind == "write":
            return "%d:%d" % (ev["arg_num"], ev["arg_alt"])
        if kind in ("truncate", "chmod", "chown"):
            return str(ev["arg_num"])
        return ""

    def apply_event(self, ev, canon_a):
        ino = ev["ino"]
        kind = ev["kind"]
        if kind == "unlink":
            self.live_paths[ino] = [p for p in self.live_paths[ino] if p["path"] != canon_a]
            if not self.live_paths[ino]:
                self.states[ino] = "pruned"
        elif kind == "rename":
            new = canonical_path(ev["path_b"])
            for p in self.live_paths[ino]:
                if p["path"] == canon_a:
                    p["path"] = new
            self.renamed_inodes.add(ino)
        elif kind == "link":
            biggest = max([p["ordinal"] for p in self.live_paths[ino]], default=-1)
            self.live_paths[ino].append({"path": canon_a, "ordinal": biggest + 1, "form": "nfc"})
        elif kind == "hold":
            self.states[ino] = "held"
        elif kind == "release":
            self.states[ino] = "live"
        elif kind == "setxattr":
            self.live_xattrs[ino][ev["path_a"]] = ev["arg_num"]
        elif kind == "truncate":
            self.sizes[ino] = ev["arg_num"]
        # chmod, chown, write change nothing else the plan records

    # ----- scope, clusters ------------------------------------------------

    def primary_of(self, ino):
        recs = self.live_paths.get(ino, [])
        if not recs:
            return None, 0
        if len(recs) == 1:
            return recs[0]["path"], 0
        keyed = []
        for i, p in enumerate(recs):
            keyed.append((path_depth(p["path"]), utf8_len(p["path"]), p["path"], p["ordinal"], i))
        level = 4
        order = list(range(len(recs)))
        for keyidx in range(4):
            vals = [keyed[i][keyidx] for i in order]
            best = min(vals)
            order = [i for i in order if keyed[i][keyidx] == best]
            if len(order) == 1:
                level = keyidx + 1
                break
        win = keyed[order[0]]
        return win[2], level

    def build_scope(self):
        self.relocatable = {}
        self.primary = {}
        self.tiebreak = {}
        self.reasons = {}
        for ino in sorted(self.objects):
            o = self.objects[ino]
            pool = o["pool_id"]
            reason = ""
            if pool not in self.pools:
                reason = "unknown_pool"
            elif self.states[ino] != "live" or not self.live_paths[ino]:
                reason = "not_live"
            else:
                nclaims = len(self.claims.get(ino, []))
                if nclaims == 0:
                    reason = "unclaimed"
                elif nclaims > 1:
                    reason = "contested"
                else:
                    primary, level = self.primary_of(ino)
                    cap = self.pool_depth_cap(pool)
                    if path_depth(primary) > cap:
                        reason = "depth_exceeded"
                    else:
                        self.primary[ino] = primary
                        self.tiebreak[ino] = level
            self.relocatable[ino] = (reason == "")
            self.reasons[ino] = reason
        for ino in self.objects:
            if ino not in self.primary:
                self.primary[ino], self.tiebreak[ino] = self.primary_of(ino)

    # ----- checkpoint outcomes --------------------------------------------

    def checkpoint_states(self):
        states = {}
        for key, entries in self.checkpoints.items():
            ino, idx = key
            if ino not in self.objects:
                continue
            barrier = self.barriers.get(self.objects[ino]["pool_id"], None)
            eligible = []
            for r in entries:
                seq = as_int(r["seq"])
                if barrier is not None and seq <= barrier:
                    eligible.append(r)
            if not eligible:
                seqs = [as_int(r["seq"]) for r in entries]
                states[key] = {
                    "seq": min(seqs), "committed": -1, "status": "after_barrier",
                    "invalidated_by": 0,
                }
                continue
            def rank(r):
                c = r["bytes_committed"]
                return (as_int(r["seq"]), -1 if c is None else int(c))
            top = max(eligible, key=rank)
            e = self.extents.get(ino, {}).get(idx)
            expected = e["raw_physical_bytes"] if e else 0
            committed = top["bytes_committed"]
            if committed is None:
                states[key] = {
                    "seq": as_int(top["seq"]), "committed": -1, "status": "never_started",
                    "invalidated_by": 0,
                }
            else:
                c = int(committed)
                if c == expected:
                    status = "durable"
                elif c > expected:
                    status = "overrun"
                elif c == 0:
                    status = "zeroed"
                else:
                    status = "partial"
                states[key] = {
                    "seq": as_int(top["seq"]), "committed": c, "status": status,
                    "invalidated_by": 0,
                }
        # undo durable entries through replayed activity
        for key, st in states.items():
            if st["status"] != "durable":
                continue
            ino, idx = key
            e = self.extents.get(ino, {}).get(idx)
            if e is None:
                continue
            start = e["offset"]
            end = e["offset"] + e["length"]
            undo_seq = None
            for ev in self.applied_events:
                if ev["ino"] != ino:
                    continue
                if ev["kind"] == "write":
                    ws = ev["arg_num"]
                    we = ws + ev["arg_alt"]
                    if ws < end and we > start:
                        undo_seq = ev["seq"]
                        break
                elif ev["kind"] == "truncate":
                    if ev["arg_num"] < end:
                        undo_seq = ev["seq"]
                        break
            if undo_seq is not None:
                st["status"] = "redirty"
                st["invalidated_by"] = undo_seq
        self.checkpoint_states = states
        return states

    # ----- placement ------------------------------------------------------

    def initial_placement(self, ino):
        o = self.objects[ino]
        reason = ""
        key = (o["class"], o["pool_id"])
        dev = self.routes.get(key)
        if dev is None or dev not in self.devices:
            online = [d for d in self.device_ids if self.devices[d]["online"]]
            dev = online[0] if online else sorted(self.device_ids)[0] if self.device_ids else ""
            reason = "unrouted"
        else:
            cur = dev
            hops = 0
            while self.devices[cur]["online"] == 0 and hops < 4:
                nxt = self.devices[cur]["spill_device"]
                if not nxt or nxt not in self.devices:
                    break
                cur = nxt
                hops += 1
                reason = "offline_spill"
            if self.devices[cur]["online"] == 0:
                if hops >= 4:
                    reason = "offline_chain"
                else:
                    reason = "offline_chain"
            elif reason == "":
                reason = ""
            dev = cur
        return dev, reason

    def build_placement(self):
        self.placement = {}
        self.initial_reason = {}
        self.initial_device = {}
        for ino in self.objects:
            if not self.relocatable[ino]:
                continue
            dev, reason = self.initial_placement(ino)
            self.placement[ino] = dev
            self.initial_device[ino] = dev
            self.initial_reason[ino] = reason
        self.shed_round = {}
        self.shed_count = 0
        self.rounds = 0
        for rnd in range(1, 9):
            self.rounds = rnd
            attribution = self.compute_attribution()
            claims = defaultdict(int)
            for ino, dev in self.placement.items():
                claims[dev] += attribution.get(ino, 0)
            shed_any = False
            for dev in self.device_ids:
                dv = self.devices[dev]
                claim = claims.get(dev, 0)
                if dv["existing_used_bytes"] + claim <= dv["usable_bytes"]:
                    continue
                spill = dv["spill_device"]
                if not spill or spill == dev or spill not in self.devices:
                    continue
                candidates = []
                for ino, d in self.placement.items():
                    if d != dev or ino in self.shed_round:
                        continue
                    candidates.append(ino)
                if not candidates:
                    continue
                candidates.sort(key=lambda i: (
                    CLASS_RANK.get(self.objects[i]["class"], 99),
                    -attribution.get(i, 0),
                    self.primary[i],
                    i,
                ))
                victim = candidates[0]
                claims[dev] -= attribution.get(victim, 0)
                claims[spill] += attribution.get(victim, 0)
                self.placement[victim] = spill
                self.shed_round[victim] = rnd
                shed_any = True
            if not shed_any:
                break

    def compute_attribution(self):
        holders = defaultdict(list)
        for ino, dev in self.placement.items():
            for idx in sorted(self.extents.get(ino, {})):
                e = self.extents[ino][idx]
                if e["pclass"] not in ("data", "reserved"):
                    continue
                domain = self.devices[dev]["share_domain"]
                holders[e["physical_id"]].append((ino, idx, e["raw_physical_bytes"], domain))
        attributed = defaultdict(int)
        owners = {}
        for pid, lst in holders.items():
            by_domain = defaultdict(list)
            for ino, idx, rpb, domain in lst:
                by_domain[domain].append((ino, idx, rpb))
            for domain, members in by_domain.items():
                members.sort(key=lambda m: (self.primary[m[0]], m[0], m[1]))
                owner_ino = members[0][0]
                owner_idx = members[0][1]
                for ino, idx, rpb in members:
                    if ino == owner_ino and idx == owner_idx:
                        attributed[ino] += rpb
                owners[(pid, domain)] = (owner_ino, owner_idx)
        self.current_owners = owners
        return dict(attributed)

    # ----- worksets -------------------------------------------------------

    def build_worksets(self):
        self.checkpoint_states = self.checkpoint_states()
        self.final_attribution = self.compute_attribution()
        self.sharing_rows = []
        pid_holders = defaultdict(list)
        for ino in self.placement:
            for idx in sorted(self.extents.get(ino, {})):
                e = self.extents[ino][idx]
                if e["pclass"] not in ("data", "reserved"):
                    continue
                pid_holders[e["physical_id"]].append((ino, idx, e["raw_physical_bytes"]))
        for pid in sorted(pid_holders):
            lst = pid_holders[pid]
            inos = sorted(set(m[0] for m in lst))
            if len(inos) < 2:
                continue
            domains = sorted(set(self.devices[self.placement[m[0]]]["share_domain"] for m in lst))
            owners = []
            for domain in domains:
                key = (pid, domain)
                owners.append(self.current_owners[key][0])
            unit = max(m[2] for m in lst)
            self.sharing_rows.append({
                "physical_id": pid,
                "referencing_inodes": inos,
                "domains": domains,
                "copies": len(domains),
                "owners": owners,
                "unit_bytes": unit,
                "expanded_bytes": unit * (len(domains) - 1),
            })

        # copy items
        self.copy_items = []
        for ino in sorted(self.placement):
            dev = self.placement[ino]
            domain = self.devices[dev]["share_domain"]
            for idx in sorted(self.extents.get(ino, {})):
                e = self.extents[ino][idx]
                if e["pclass"] != "data":
                    continue
                key = (e["physical_id"], domain)
                owner = self.current_owners.get(key)
                if owner is None or owner != (ino, idx):
                    continue
                st = self.checkpoint_states.get((ino, idx))
                if st is not None and st["status"] == "durable":
                    continue
                if st is None:
                    origin = "fresh"
                elif st["status"] == "redirty":
                    origin = "redirty"
                else:
                    origin = "restart"
                self.copy_items.append({
                    "ino": ino, "ext_index": idx, "device_id": dev,
                    "physical_id": e["physical_id"], "copy_bytes": e["raw_physical_bytes"],
                    "origin": origin, "deadline_window": self.deadlines.get(ino, (0, ""))[0],
                    "primary": self.primary[ino],
                })
        # effective class: strongest class among the relocatable objects whose
        # surviving data or reserved extents carry the same physical identifier
        # in the same share domain
        domain_holders = defaultdict(set)
        for ino, pdev in self.placement.items():
            domain = self.devices[pdev]["share_domain"]
            for idx in sorted(self.extents.get(ino, {})):
                e = self.extents[ino][idx]
                if e["pclass"] in ("data", "reserved"):
                    domain_holders[(e["physical_id"], domain)].add(ino)
        for item in self.copy_items:
            key = (item["physical_id"], self.devices[item["device_id"]]["share_domain"])
            members = domain_holders.get(key, {item["ino"]})
            best = min(CLASS_RANK[self.objects[i]["class"]] for i in members)
            item["effective_class"] = CLASS_ORDER[best]
        self.copy_items.sort(key=lambda it: (
            CLASS_RANK[it["effective_class"]], it["deadline_window"], it["primary"],
            it["ino"], it["ext_index"],
        ))

        # metadata operations
        self.item_inos = set(it["ino"] for it in self.copy_items)
        self.redirty_inos = set(
            key[0] for key, st in self.checkpoint_states.items()
            if st["status"] == "redirty"
        )
        self.metadata_ops = []
        for ino in sorted(self.placement):
            o = self.objects[ino]
            primary = self.primary[ino]
            ops = []
            if o["kind"] == "dir":
                ops.append(("mkdir", 1, "", 0))
            special = self.special_row(ino)
            if special is not None and special["recreate"] != "skip":
                ops.append((special["recreate"], 2, "%d:%d" % (special["major"], special["minor"]), 0))
            if o["kind"] == "symlink":
                info = self.symlink_targets.get(ino)
                ops.append(("symlink", 3, info["target"] if info else "", 0))
            members = sorted(set(p["path"] for p in self.live_paths[ino]) - {primary})
            for mp in members:
                ops.append(("link", 4, mp, 0))
            domain = self.devices[self.placement[ino]]["share_domain"]
            for idx in sorted(self.extents.get(ino, {})):
                e = self.extents[ino][idx]
                if e["pclass"] == "data":
                    owner = self.current_owners.get((e["physical_id"], domain))
                    if owner != (ino, idx):
                        ops.append(("reflink", 5, e["physical_id"], e["raw_physical_bytes"]))
                elif e["pclass"] == "reserved":
                    ops.append(("fallocate", 6, str(idx), e["raw_physical_bytes"]))
            migrated = self.migrated_xattrs(ino)
            for name in migrated:
                ops.append(("setxattr", 7, name, 0))
            ops.append(("chown", 8, "%d:%d" % (o["uid"], o["gid"]), 0))
            ops.append(("chmod", 9, o["mode"], 0))
            ops.append(("utimes", 10, str(o["mtime_ns"]), 0))
            for op, rank, detail, nbytes in ops:
                self.metadata_ops.append({
                    "op": op, "ino": ino, "path": primary, "detail": detail, "bytes": nbytes,
                })
        self.metadata_ops.sort(key=lambda m: (m["ino"], OP_RANK[m["op"]], m["detail"]))

    def special_row(self, ino):
        kind = self.objects[ino]["kind"]
        if kind not in ("fifo", "socket", "chardev", "blockdev"):
            return None
        rec = self.specials.get(ino)
        if rec is None:
            major = minor = 0
        else:
            major = as_int(rec["major"])
            minor = as_int(rec["minor"])
        overflow = 1 if minor > 255 else 0
        used = minor % 256 if overflow else minor
        verb = {"fifo": "mkfifo", "socket": "bind", "chardev": "mknod", "blockdev": "mknod"}[kind]
        if rec is None and kind in ("chardev", "blockdev"):
            verb = "skip"
        return {
            "node_kind": kind, "major": major, "minor": used, "raw_minor": minor,
            "rdev": major * 256 + used, "overflow": overflow, "recreate": verb,
        }

    def migrated_xattrs(self, ino):
        o = self.objects[ino]
        out = []
        for name in self.live_xattrs.get(ino, {}):
            ns = name.split(".")[0]
            if ns in ("user", "trusted"):
                out.append(name)
            elif ns == "security":
                if o["class"] in ("gold", "silver"):
                    out.append(name)
            elif ns == "system":
                if name in ("system.posix_acl_access", "system.posix_acl_default"):
                    out.append(name)
        return sorted(out)

    # ----- schedule -------------------------------------------------------

    def build_schedule(self):
        self.split_rows = []
        self.window_state = {}
        for dev in self.device_ids:
            w = self.devices[dev]["windows"]
            self.window_state[dev] = {
                idx: {"remaining": w[idx]["budget"], "desc_left": w[idx]["desc"], "open": set(), "bytes": 0, "opened": 0}
                for idx in w
            }
        for item in self.copy_items:
            dev = item["device_id"]
            ino = item["ino"]
            size = item["copy_bytes"]
            au = self.devices[dev]["alloc_unit"] or 1
            ws = self.window_state.get(dev, {})
            indexes = sorted(ws)
            max_budget = max([self.devices[dev]["windows"][i]["budget"] for i in indexes], default=0)
            lowest_with_room = None
            for i in indexes:
                if ws[i]["remaining"] > 0:
                    lowest_with_room = i
                    break
            placements = []
            if not indexes:
                residual = size
            elif size <= max_budget:
                placed = False
                for i in indexes:
                    st = ws[i]
                    if st["remaining"] >= size and (ino in st["open"] or st["desc_left"] > 0):
                        placements.append(self._place(dev, i, ino, size))
                        placed = True
                        break
                residual = 0 if placed else size
            else:
                residual = size
                for i in indexes:
                    st = ws[i]
                    if residual == 0:
                        break
                    if not (ino in st["open"] or st["desc_left"] > 0):
                        continue
                    if st["remaining"] < au:
                        continue
                    if residual <= st["remaining"]:
                        placements.append(self._place(dev, i, ino, residual))
                        residual = 0
                        break
                    take = (st["remaining"] // au) * au
                    placements.append(self._place(dev, i, ino, take))
                    residual -= take
            placed_total = sum(p["bytes"] for p in placements)
            item["residual"] = size - placed_total
            item["placements"] = placements
            if item["residual"] > 0:
                status = "deferred"
            elif len(placements) > 1:
                status = "split"
            elif len(placements) == 1:
                if placements[0]["window_index"] == lowest_with_room:
                    status = "whole"
                else:
                    status = "rolled"
            else:
                status = "deferred"
            item["status"] = status
            if status != "whole":
                self.split_rows.append(item)

    def _place(self, dev, widx, ino, nbytes):
        st = self.window_state[dev][widx]
        opened = 0
        if ino not in st["open"]:
            st["open"].add(ino)
            st["desc_left"] -= 1
            st["opened"] += 1
            opened = 1
        st["remaining"] -= nbytes
        st["bytes"] += nbytes
        return {"device_id": dev, "window_index": widx, "ino": ino, "bytes": nbytes, "descriptor_opened": opened}

    # ----- cutover --------------------------------------------------------

    def build_cutover(self):
        self.deferred_bytes = defaultdict(int)
        for item in self.copy_items:
            if item["residual"] > 0:
                self.deferred_bytes[item["ino"]] += item["residual"]
        ready = []
        for ino in sorted(self.placement):
            if self.deferred_bytes.get(ino, 0) > 0:
                continue
            ready.append(ino)
        ready.sort(key=lambda i: (path_depth(self.primary[i]), self.primary[i], i))
        self.cutover_order = ready
        self.rollback_rows = []
        step = 0
        for ino in ready:
            step += 1
            self.rollback_rows.append(self._rollback_row(ino, step))
        for ino in sorted(self.deferred_bytes):
            if ino not in self.placement:
                continue
            self.rollback_rows.append(self._rollback_row(ino, 0))

    def _rollback_row(self, ino, step):
        has_item = ino in self.item_inos
        any_redirty = ino in self.redirty_inos
        if any_redirty:
            guard = "digest_match"
        elif has_item:
            guard = "size_match"
        else:
            guard = "xattr_count_match"
        primary = self.primary[ino]
        members = sorted(set(p["path"] for p in self.live_paths[ino]) - {primary})
        if self.deferred_bytes.get(ino, 0) > 0:
            reverse = "abort_hold"
        elif members:
            reverse = "restore_link"
        elif ino in self.renamed_inodes:
            reverse = "rename_back"
        else:
            reverse = "unlink_target"
        return {
            "step": step, "ino": ino, "path": primary, "guard": guard,
            "reverse": reverse, "barrier_seq": self.barriers.get(self.objects[ino]["pool_id"], 0),
        }

    # ------------------------------------------------------------------
    # artifact rendering
    # ------------------------------------------------------------------

    def render_artifacts(self):
        out = {}
        objs = self.objects

        # object_inventory.jsonl
        lines = []
        for ino in sorted(objs):
            o = objs[ino]
            lines.append(json_line({
                "ino": ino, "kind": o["kind"], "size_bytes": o["size_bytes"],
                "mode": o["mode"], "uid": o["uid"], "gid": o["gid"],
                "mtime_ns": o["mtime_ns"], "class": o["class"], "pool_id": o["pool_id"],
                "declared_link_count": o["declared_link_count"], "state": o["state"],
                "superseded_rows": o["superseded_rows"], "size_unit": o["size_unit"],
            }))
        out["object_inventory.jsonl"] = "".join(l + "\n" for l in lines)

        # device_topology.json
        devs = []
        for d in self.device_ids:
            dv = self.devices[d]
            w = dv["windows"]
            devs.append({
                "device_id": d,
                "capacity_bytes": dv["capacity_bytes"],
                "existing_used_bytes": dv["existing_used_bytes"],
                "reserve_ppm": dv["reserve_ppm"],
                "reserve_bytes": dv["reserve_bytes"],
                "usable_bytes": dv["usable_bytes"],
                "alloc_unit": dv["alloc_unit"],
                "share_domain": dv["share_domain"],
                "spill_device": dv["spill_device"],
                "online": dv["online"],
                "windows": len(w),
                "io_budget_bytes": sum(w[i]["budget"] for i in w),
                "descriptor_peak": max([w[i]["desc"] for i in w], default=0),
            })
        out["device_topology.json"] = json_pretty({
            "devices": devs,
            "device_count": len(devs),
            "domain_count": len(set(d["share_domain"] for d in devs)),
        }) + "\n"

        # extent_map.tsv
        rows = ["ino\text_index\toffset\tlength_bytes\tend_offset\tphysical_id\t"
                "physical_class\traw_physical_bytes\tflags\trepair"]
        for r in self.extent_map_rows():
            rows.append(tsv_row(r))
        out["extent_map.tsv"] = "".join(l + "\n" for l in rows)

        # symlink_topology.jsonl
        lines = []
        for ino in sorted(objs):
            if objs[ino]["kind"] != "symlink":
                continue
            info = self.symlink_targets.get(ino)
            target = info["target"] if info else ""
            form = info["form"] if info else ""
            tb = utf8_len(target)
            fast = 1 if tb <= 59 else 0
            au = self.pool_alloc_unit(objs[ino]["pool_id"])
            pb = 0 if fast else au
            resolution, hops = self.resolve_symlink(ino)
            lines.append(json_line({
                "ino": ino, "arrival_form": form, "target": target, "target_bytes": tb,
                "kind": ("absolute" if target.startswith("/") else "relative"),
                "resolution": resolution, "hops": hops, "fast": fast,
                "physical_bytes": pb,
            }))
        out["symlink_topology.jsonl"] = "".join(l + "\n" for l in lines)

        # mutation_replay.jsonl
        lines = []
        for r in self.replay_rows:
            lines.append(json_line(r))
        out["mutation_replay.jsonl"] = "".join(l + "\n" for l in lines)

        # scope_resolution.csv
        rows = ["ino,class,pool_id,pool_region,relocatable,reason,paths_after_replay,"
                "hold_notices,hold_reasons,claims,claim_sets,depth"]
        for ino in sorted(objs):
            o = objs[ino]
            pool = o["pool_id"]
            region = self.pools[pool]["region"] if pool in self.pools else ""
            holds = [h for h in self.holds.get(ino, []) if h[1] == 1]
            reasons = sorted(set(h[0] for h in holds))
            claims = self.claims.get(ino, [])
            primary = self.primary[ino]
            rows.append(csv_row([
                ino, o["class"], pool, region,
                1 if self.relocatable[ino] else 0, self.reasons[ino],
                len(set(p["path"] for p in self.live_paths[ino])),
                len(holds), "+".join(reasons),
                len(claims), "+".join(sorted(set(claims))),
                path_depth(primary) if self.live_paths[ino] else 0,
            ]))
        out["scope_resolution.csv"] = "".join(l + "\n" for l in rows)

        # link_clusters.jsonl
        lines = []
        for ino in sorted(self.placement):
            primary = self.primary[ino]
            members = sorted(set(p["path"] for p in self.live_paths[ino]) - {primary})
            nfd = sum(1 for p in self.live_paths[ino] if p["form"] == "nfd")
            lines.append(json_line({
                "ino": ino, "primary_path": primary, "tiebreak_level": self.tiebreak[ino],
                "member_paths": members, "link_ops": len(members), "arrival_forms": nfd,
            }))
        out["link_clusters.jsonl"] = "".join(l + "\n" for l in lines)

        # resume_state.jsonl
        lines = []
        for (ino, idx) in sorted(self.checkpoint_states):
            if not self.relocatable.get(ino):
                continue
            if idx not in self.extents.get(ino, {}):
                continue
            if objs[ino]["kind"] != "regular":
                continue
            st = self.checkpoint_states[(ino, idx)]
            e = self.extents[ino][idx]
            lines.append(json_line({
                "ino": ino, "ext_index": idx, "seq": st["seq"], "committed": st["committed"],
                "expected": e["raw_physical_bytes"], "status": st["status"],
                "invalidated_by": st["invalidated_by"],
            }))
        out["resume_state.jsonl"] = "".join(l + "\n" for l in lines)

        # xattr_ledger.csv
        rows = ["ino,migrated_count,dropped_count,migrated_bytes,dropped_bytes,"
                "first_migrated_name,namespaces"]
        for ino in sorted(self.placement):
            o = objs[ino]
            migrated = self.migrated_xattrs(ino)
            allx = sorted(self.live_xattrs.get(ino, {}))
            dropped = [n for n in allx if n not in set(migrated)]
            mig_bytes = sum(utf8_len(n) + 1 + self.live_xattrs[ino][n] for n in migrated)
            drop_bytes = sum(utf8_len(n) + 1 + self.live_xattrs[ino][n] for n in dropped)
            namespaces = sorted(set(n.split(".")[0] for n in migrated))
            rows.append(csv_row([
                ino, len(migrated), len(dropped), mig_bytes, drop_bytes,
                migrated[0] if migrated else "", "+".join(namespaces),
            ]))
        out["xattr_ledger.csv"] = "".join(l + "\n" for l in rows)

        # special_nodes.tsv
        rows = ["ino\tnode_kind\tmajor\tminor\trdev\toverflow\trecreate"]
        for ino in sorted(self.placement):
            sp = self.special_row(ino)
            if sp is None:
                continue
            rows.append(tsv_row([
                ino, sp["node_kind"], sp["major"], sp["minor"], sp["rdev"],
                sp["overflow"], sp["recreate"],
            ]))
        out["special_nodes.tsv"] = "".join(l + "\n" for l in rows)

        # placement.csv
        rows = ["ino,class,initial_device,device,share_domain,moved,round,reason,"
                "attributed_bytes,deadline_window,class_override"]
        for ino in sorted(self.placement):
            o = objs[ino]
            dev = self.placement[ino]
            init = self.initial_device[ino]
            reason = "evicted" if ino in self.shed_round else self.initial_reason[ino]
            deadline = self.deadlines.get(ino, (0, ""))
            rows.append(csv_row([
                ino, o["class"], init, dev, self.devices[dev]["share_domain"],
                1 if dev != init else 0, self.shed_round.get(ino, 0), reason,
                self.final_attribution.get(ino, 0), deadline[0], deadline[1],
            ]))
        out["placement.csv"] = "".join(l + "\n" for l in rows)

        # sharing_expansion.jsonl
        lines = []
        for r in self.sharing_rows:
            lines.append(json_line(r))
        out["sharing_expansion.jsonl"] = "".join(l + "\n" for l in lines)

        # allocation_projection.csv
        rows = ["device_id,capacity_bytes,reserve_bytes,usable_bytes,existing_used_bytes,"
                "claim_bytes,projected_bytes,headroom_bytes,over_committed,placed_objects,"
                "evicted_out,received_in"]
        self.evicted_out = defaultdict(int)
        self.received_in = defaultdict(int)
        for ino, rnd in self.shed_round.items():
            self.evicted_out[self.initial_device[ino]] += 1
            self.received_in[self.placement[ino]] += 1
        for d in self.device_ids:
            dv = self.devices[d]
            claim = sum(self.final_attribution.get(i, 0) for i, dev in self.placement.items() if dev == d)
            projected = dv["existing_used_bytes"] + claim
            headroom = dv["usable_bytes"] - projected
            rows.append(csv_row([
                d, dv["capacity_bytes"], dv["reserve_bytes"], dv["usable_bytes"],
                dv["existing_used_bytes"], claim, projected, headroom,
                1 if headroom < 0 else 0,
                sum(1 for dev in self.placement.values() if dev == d),
                self.evicted_out.get(d, 0), self.received_in.get(d, 0),
            ]))
        out["allocation_projection.csv"] = "".join(l + "\n" for l in rows)

        # delta_workset.tsv
        rows = ["ino\text_index\tdevice_id\tphysical_id\tcopy_bytes\torigin\t"
                "effective_class\tdeadline_window"]
        for it in self.copy_items:
            rows.append(tsv_row([
                it["ino"], it["ext_index"], it["device_id"], it["physical_id"],
                it["copy_bytes"], it["origin"], it["effective_class"], it["deadline_window"],
            ]))
        out["delta_workset.tsv"] = "".join(l + "\n" for l in rows)

        # metadata_workset.jsonl
        lines = []
        for m in self.metadata_ops:
            lines.append(json_line(m))
        out["metadata_workset.jsonl"] = "".join(l + "\n" for l in lines)

        # window_schedule.tsv
        sched = []
        for it in self.copy_items:
            for ci, p in enumerate(it["placements"]):
                sched.append((p["device_id"], p["window_index"], it["ino"], it["ext_index"], ci,
                              p["bytes"], p["descriptor_opened"]))
        sched.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[4]))
        rows = ["device_id\twindow_index\tino\text_index\tchunk_index\tbytes\tdescriptor_opened"]
        for r in sched:
            rows.append(tsv_row(r))
        out["window_schedule.tsv"] = "".join(l + "\n" for l in rows)

        # split_ledger.jsonl
        lines = []
        for it in sorted(self.split_rows, key=lambda i: (i["ino"], i["ext_index"])):
            pl = it["placements"]
            lines.append(json_line({
                "ino": it["ino"], "ext_index": it["ext_index"], "device_id": it["device_id"],
                "status": it["status"], "chunks": len(pl),
                "placed_bytes": sum(p["bytes"] for p in pl), "residual_bytes": it["residual"],
                "first_window": pl[0]["window_index"] if pl else -1,
                "last_window": pl[-1]["window_index"] if pl else -1,
            }))
        out["split_ledger.jsonl"] = "".join(l + "\n" for l in lines)

        # descriptor_budget.csv
        rows = ["device_id,window_index,descriptor_budget,descriptors_used,io_budget_bytes,"
                "bytes_used,utilisation_ppm"]
        for d in self.device_ids:
            w = self.devices[d]["windows"]
            st = self.window_state[d]
            for idx in sorted(w):
                budget = w[idx]["budget"]
                used = st[idx]["bytes"]
                ppm = (used * 1000000 // budget) if budget > 0 else 0
                rows.append(csv_row([
                    d, idx, w[idx]["desc"], st[idx]["opened"], budget, used, ppm,
                ]))
        out["descriptor_budget.csv"] = "".join(l + "\n" for l in rows)

        # cutover_sequence.txt
        lines = [self.primary[ino] for ino in self.cutover_order]
        out["cutover_sequence.txt"] = "".join(l + "\n" for l in lines)

        # rollback_plan.jsonl
        lines = []
        for r in self.rollback_rows:
            lines.append(json_line(r))
        out["rollback_plan.jsonl"] = "".join(l + "\n" for l in lines)

        # conservation.json
        self.conservation = []
        for d in self.device_ids:
            attributed = sum(self.final_attribution.get(i, 0)
                             for i, dev in self.placement.items() if dev == d)
            copied = sum(self.window_state[d][i]["bytes"] for i in self.window_state[d])
            resumed = 0
            reserved = 0
            for ino, dev in self.placement.items():
                if dev != d:
                    continue
                domain = self.devices[d]["share_domain"]
                for idx in sorted(self.extents.get(ino, {})):
                    e = self.extents[ino][idx]
                    owner = self.current_owners.get((e["physical_id"], domain))
                    mine = (owner == (ino, idx))
                    if e["pclass"] == "reserved" and mine:
                        reserved += e["raw_physical_bytes"]
                    elif e["pclass"] == "data" and mine:
                        st = self.checkpoint_states.get((ino, idx))
                        if st is not None and st["status"] == "durable":
                            resumed += e["raw_physical_bytes"]
            deferred = 0
            for it in self.copy_items:
                if self.placement[it["ino"]] == d:
                    deferred += it["residual"]
            residual = attributed - (copied + resumed + reserved + deferred)
            self.conservation.append({
                "device_id": d, "attributed_bytes": attributed, "copied_bytes": copied,
                "resumed_bytes": resumed, "reserved_bytes": reserved,
                "deferred_bytes": deferred, "residual_bytes": residual,
            })
        out["conservation.json"] = json_pretty({
            "devices": self.conservation,
            "balanced_devices": sum(1 for c in self.conservation if c["residual_bytes"] == 0),
            "unbalanced_devices": sum(1 for c in self.conservation if c["residual_bytes"] != 0),
        }) + "\n"

        # cli_contract.json
        out["cli_contract.json"] = json_pretty({
            "tool": "stratactl",
            "usage": "stratactl.py CORPUS_DIR OUT_DIR",
            "exit_ok": EXIT_OK,
            "exit_usage": EXIT_USAGE,
            "exit_policy": EXIT_POLICY,
            "artifact_count": ARTIFACT_COUNT,
        }) + "\n"

        return out


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: stratactl.py CORPUS_DIR OUT_DIR\n")
        return EXIT_USAGE
    corpus_dir = argv[1]
    out_dir = argv[2]
    if not os.path.isdir(corpus_dir):
        sys.stderr.write("corpus path is not a directory: %s\n" % corpus_dir)
        return EXIT_POLICY
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        sys.stderr.write("cannot create output directory: %s\n" % exc)
        return EXIT_POLICY
    plan = Plan(corpus_dir)
    out = plan.render_artifacts()
    manifest = []
    for name in ARTIFACTS[:-2]:
        data = out[name].encode("utf-8")
        manifest.append({
            "name": name,
            "rows": data.count(b"\n"),
            "bytes": len(data),
            "digest": sha16(data),
        })
    out["manifest.json"] = json_pretty({"artifacts": manifest}) + "\n"
    summary = {
        "relocatable_objects": len(plan.placement),
        "excluded_objects": sum(1 for i in plan.objects if not plan.relocatable[i]),
        "clusters": len(plan.placement),
        "copy_items": len(plan.copy_items),
        "metadata_ops": len(plan.metadata_ops),
        "cutover_steps": len(plan.cutover_order),
        "manifest_digest": sha16("\n".join(m["digest"] for m in manifest).encode("utf-8")),
    }
    out["summary.json"] = json_pretty(summary) + "\n"
    for name in ARTIFACTS:
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(out[name].encode("utf-8"))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
