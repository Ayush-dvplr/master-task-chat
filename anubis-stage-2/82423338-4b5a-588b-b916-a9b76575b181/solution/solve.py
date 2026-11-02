#!/usr/bin/env python3
"""stratactl - the STRATA relocation planner.

Usage: stratactl.py CORPUS_DIR OUT_DIR

The planner reads every record file in CORPUS_DIR, applies the relocation plan
contract (SPEC-STRATA, version 4) and writes the twenty-four plan artifacts into
OUT_DIR. Section numbers in the comments refer to that contract. The rules are
built in, so the specification does not have to be present in the corpus.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import tomllib
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_POLICY = 3
EXIT_WRITE_FAILED = 1
USAGE = "stratactl.py CORPUS_DIR OUT_DIR"

# Section 24: every artifact, in contract order. The manifest covers the names
# up to and including cli_contract.json.
ARTIFACT_NAMES = (
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
)
MANIFEST_SCOPE = ARTIFACT_NAMES[: ARTIFACT_NAMES.index("cli_contract.json") + 1]

# Section 3: record schemas, fields in the order every encoding writes them.
SCHEMAS = {
    "pool": ("pool_id", "alloc_unit", "root_depth_cap", "region"),
    "barrier": ("pool_id", "rev", "barrier_seq", "effective_seq"),
    "capacity": ("device_id", "rev", "capacity_raw", "capacity_unit",
                 "existing_used_raw", "existing_used_unit", "reserve_ppm", "effective_seq"),
    "geometry": ("slot_id", "device_id", "rev", "share_domain", "spill_device",
                 "online", "alloc_unit", "effective_seq"),
    "window": ("device_id", "window_index", "io_budget_raw", "io_budget_unit",
               "descriptor_budget"),
    "route": ("route_id", "class", "pool_id", "device_id"),
    "object": ("ino", "kind", "size_raw", "size_unit", "mode_raw", "uid", "gid", "mtime_ns",
               "class_raw", "pool_id", "link_count", "state", "gen"),
    "path": ("ino", "path_raw", "ordinal", "form"),
    "extent": ("ino", "ext_index", "offset", "length_raw", "length_unit", "physical_id",
               "flags", "gen"),
    "symlink": ("ino", "target_raw", "form"),
    "special_node": ("node_id", "ino", "node_kind", "major", "minor"),
    "xattr": ("xattr_id", "ino", "name", "value_len", "gen"),
    "claim": ("claim_id", "ino", "set_name"),
    "deadline": ("ino", "deadline_window", "class_override"),
    "hold": ("ino", "reason", "active"),
    "checkpoint": ("ino", "ext_index", "bytes_committed", "seq", "pool_id"),
    "event": ("seq", "ordinal", "kind", "ino", "path_a", "path_b", "arg_num", "arg_alt"),
}

# Section 4: unit factors.
UNIT_FACTORS = {
    "B": 1, "KiB": 1024, "MiB": 1048576, "GiB": 1073741824,
    "kB": 1000, "MB": 1000000, "GB": 1000000000, "s": 512, "bl": 4096,
}

# Section 5: classes rank with gold strongest.
CLASS_RANK = {"gold": 0, "silver": 1, "bronze": 2, "tin": 3}

# Section 8: an object whose pool is not catalogued rounds with this unit.
DEFAULT_POOL_ALLOC_UNIT = 4096

# Section 9: flag words in output order.
FLAG_ORDER = ("hole", "unwritten", "inline", "shared", "sealed")

# Section 10: the fast symlink boundary and the hop cap.
FAST_SYMLINK_MAX_BYTES = 59
SYMLINK_HOP_CAP = 8

# Section 15: system attributes that are migrated all the same.
MIGRATED_SYSTEM_ATTRIBUTES = frozenset({"system.posix_acl_access", "system.posix_acl_default"})

# Section 16: recreation verbs by inventory kind.
RECREATE_VERBS = {"fifo": "mkfifo", "socket": "bind", "chardev": "mknod", "blockdev": "mknod"}
DEVICE_NODE_KINDS = frozenset({"chardev", "blockdev"})

# Section 17: shedding bounds.
MAX_SHEDDING_ROUNDS = 8
MAX_OFFLINE_HOPS = 4

# Section 19: metadata operation ranks.
OPERATION_RANK = {
    "mkdir": 1, "mknod": 2, "mkfifo": 2, "bind": 2, "symlink": 3, "link": 4,
    "reflink": 5, "fallocate": 6, "setxattr": 7, "chown": 8, "chmod": 9, "utimes": 10,
}

Record = dict[str, "str | None"]


def warn(message: str) -> None:
    sys.stderr.write("stratactl: {}\n".format(message))


# ---------------------------------------------------------------------------
# Section 2: reading the corpus. Each file's encoding is detected from its
# content and its table from its complete field set; names decide nothing.

# Keyed encodings (ini, properties) carry the first schema field in the section
# header or identifier; it is held under this key until the schema is known.
KEY_FIELD = ""

SYSLOG_PREFIX = re.compile(r"<\d+>\d+ ")
RFC822_HEADER = re.compile(r"[A-Z][A-Za-z0-9]*(?:-[A-Z][A-Za-z0-9]*)*: ?")
PROPERTIES_LINE = re.compile(r"[^=\s]+\.[A-Za-z_]\w*=")
LOGFMT_LINE = re.compile(r"[A-Za-z_]\w*=")
QUOTED_FIELD = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')
SEXP_FIELD = re.compile(r'\((\w+) "((?:[^"\\]|\\.)*)"\)')
STRUCTURED_DATA_START = "[strata@41762 "
BACKSLASH_ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}
TSV_ESCAPES = {"\\\\": "\\", "\\t": "\t", "\\n": "\n"}


def unescape_backslashes(value: str) -> str:
    return re.sub(r"\\(.)", lambda match: BACKSLASH_ESCAPES.get(match.group(1), match.group(1)),
                  value)


def text_lines(text: str) -> list[str]:
    return [line for line in text.split("\n") if line.strip()]


def records_from_rows(rows: list[list[str]]) -> list[dict]:
    """A header row names the fields; a short row leaves its last fields empty."""
    rows = [row for row in rows if row]
    if not rows:
        return []
    header = rows[0]
    return [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in rows[1:]]


def decode_quoted_delimited(text: str, delimiter: str) -> list[dict]:
    """csv, psv and ssv: quoted when empty or holding the delimiter or a quote."""
    return records_from_rows(list(csv.reader(io.StringIO(text), delimiter=delimiter,
                                             quotechar='"', doublequote=True)))


def decode_tsv(text: str) -> list[dict]:
    rows = [[re.sub(r"\\[\\tn]", lambda match: TSV_ESCAPES[match.group()], cell)
             for cell in line.split("\t")] for line in text_lines(text)]
    return records_from_rows(rows)


def decode_fixed(text: str) -> list[dict]:
    """A field spans from the column where its name begins to the next name."""
    lines = text_lines(text)
    columns = [(match.start(), match.group()) for match in re.finditer(r"\S+", lines[0])]
    records = []
    for line in lines[1:]:
        record = {}
        for position, (start, name) in enumerate(columns):
            stop = columns[position + 1][0] if position + 1 < len(columns) else None
            record[name] = line[start:stop].strip()
        records.append(record)
    return records


def decode_json(text: str) -> list[dict]:
    return list(json.loads(text)["records"])


def decode_jsonl(text: str) -> list[dict]:
    return [json.loads(line) for line in text_lines(text)]


def decode_toml(text: str) -> list[dict]:
    return list(tomllib.loads(text).get("record", []))


def decode_ini(text: str) -> list[dict]:
    """A section header carries the first field; each line after it one more."""
    records: list[dict] = []
    for line in text_lines(text):
        stripped = line.strip()
        if stripped[0] in "#;":
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            records.append({KEY_FIELD: stripped[1:-1]})
        elif records and "=" in stripped:
            name, _, value = stripped.partition("=")
            records[-1][name.strip()] = value.strip()
    return records


def split_properties_line(line: str) -> tuple[str, str]:
    """Split at the first equals sign that is not escaped."""
    key = []
    index = 0
    while index < len(line):
        char = line[index]
        if char == "\\" and index + 1 < len(line):
            key.append(line[index + 1])
            index += 2
            continue
        if char == "=":
            return "".join(key), unescape_backslashes(line[index + 1:])
        key.append(char)
        index += 1
    return "".join(key), ""


def decode_properties(text: str) -> list[dict]:
    """identifier.field=value lines; the identifier is the first field's value."""
    records: dict[str, dict] = {}
    for line in text_lines(text):
        if line.lstrip()[0] in "#!":
            continue
        key, value = split_properties_line(line)
        identifier, _, name = key.rpartition(".")
        records.setdefault(identifier, {KEY_FIELD: identifier})[name] = value
    return list(records.values())


def decode_rfc822(text: str) -> list[dict]:
    """Blocks of Header-Name: value lines separated by a blank line."""
    records: list[dict] = []
    current: dict = {}
    for line in text.split("\n"):
        if not line.strip():
            if current:
                records.append(current)
                current = {}
            continue
        header, _, value = line.partition(":")
        current[header.strip().lower().replace("-", "_")] = value[1:] if value.startswith(" ") else value
    if current:
        records.append(current)
    return records


def read_quoted(line: str, start: int) -> tuple[str, int]:
    """Read a double-quoted value with backslash escapes; return it and the index after it."""
    chars = []
    index = start + 1
    while index < len(line) and line[index] != '"':
        if line[index] == "\\" and index + 1 < len(line):
            index += 1
            chars.append(BACKSLASH_ESCAPES.get(line[index], line[index]))
        else:
            chars.append(line[index])
        index += 1
    return "".join(chars), index + 1


def decode_logfmt(text: str) -> list[dict]:
    records = []
    for line in text_lines(text):
        record: dict = {}
        index = 0
        while index < len(line):
            if line[index] == " ":
                index += 1
                continue
            equals = line.index("=", index)
            name = line[index:equals]
            index = equals + 1
            if index < len(line) and line[index] == '"':
                value, index = read_quoted(line, index)
            else:
                end = line.find(" ", index)
                end = len(line) if end < 0 else end
                value, index = line[index:end], end
            record[name] = value
        records.append(record)
    return records


def decode_sexp(text: str) -> list[dict]:
    return [{name: unescape_backslashes(value) for name, value in SEXP_FIELD.findall(line)}
            for line in text_lines(text)]


def decode_rfc5424(text: str) -> list[dict]:
    """The record is the strata structured data element of each syslog line."""
    records = []
    for line in text_lines(text):
        start = line.find(STRUCTURED_DATA_START)
        if start < 0:
            continue
        body = line[start + len(STRUCTURED_DATA_START):line.rfind("]")]
        records.append({name: unescape_backslashes(value)
                        for name, value in QUOTED_FIELD.findall(body)})
    return records


def is_records_document(text: str) -> bool:
    try:
        document = json.loads(text)
    except ValueError:
        return False
    return isinstance(document, dict) and "records" in document


def detect_encoding(text: str) -> str | None:
    lines = text_lines(text)
    if not lines:
        return None
    first = lines[0]
    if first.startswith("[[record]]"):
        return "toml"
    if first.startswith("{"):
        return "json" if is_records_document(text) else "jsonl"
    if first.startswith("(record "):
        return "sexp"
    if SYSLOG_PREFIX.match(first) and STRUCTURED_DATA_START in first:
        return "rfc5424"
    if first.startswith("[") and first.rstrip().endswith("]"):
        return "ini"
    if RFC822_HEADER.match(first):
        return "rfc822"
    if PROPERTIES_LINE.match(first):
        return "properties"
    if LOGFMT_LINE.match(first):
        return "logfmt"
    if "\t" in first:
        return "tsv"
    if "|" in first:
        return "psv"
    if "," in first:
        return "csv"
    if "  " in first.strip():
        return "fixed"
    if " " in first:
        return "ssv"
    return None


DECODERS = {
    "csv": lambda text: decode_quoted_delimited(text, ","),
    "psv": lambda text: decode_quoted_delimited(text, "|"),
    "ssv": lambda text: decode_quoted_delimited(text, " "),
    "tsv": decode_tsv,
    "fixed": decode_fixed,
    "json": decode_json,
    "jsonl": decode_jsonl,
    "toml": decode_toml,
    "ini": decode_ini,
    "properties": decode_properties,
    "rfc822": decode_rfc822,
    "logfmt": decode_logfmt,
    "sexp": decode_sexp,
    "rfc5424": decode_rfc5424,
}


def normalise_value(value) -> str | None:
    """NIL is the only absence token; every text value is held in NFC."""
    if value is None or value == "NIL":
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return unicodedata.normalize("NFC", str(value))


def identify_table(records: list[dict]) -> tuple[str, list[Record]] | None:
    """Match the complete field set of a file to exactly one schema."""
    if not records:
        return None
    fields = set(records[0])
    for table, schema in SCHEMAS.items():
        if KEY_FIELD in fields and fields - {KEY_FIELD} == set(schema[1:]):
            renamed = [{(schema[0] if name == KEY_FIELD else name): value
                        for name, value in record.items()} for record in records]
            return table, [{name: normalise_value(record.get(name)) for name in schema}
                           for record in renamed]
        if fields == set(schema):
            return table, [{name: normalise_value(record.get(name)) for name in schema}
                           for record in records]
    return None


def read_corpus(directory: Path) -> dict[str, list[Record]]:
    """Every regular file is examined; files that hold no known table are skipped."""
    tables: dict[str, list[Record]] = defaultdict(list)
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            warn("skipping {}: {}".format(path.name, error))
            continue
        encoding = detect_encoding(text)
        if encoding is None:
            continue
        try:
            identified = identify_table(DECODERS[encoding](text))
        except (ValueError, KeyError, IndexError, csv.Error) as error:
            warn("skipping {}: not a {} record file ({})".format(path.name, encoding, error))
            continue
        if identified is not None:
            table, records = identified
            tables[table].extend(records)
    return tables


# ---------------------------------------------------------------------------
# Sections 4 and 5: values, units and canonical forms.

def as_int(value: str | None, default: int = 0) -> int:
    return default if value is None else int(value)


def as_text(value: str | None) -> str:
    return "" if value is None else value


def to_bytes(raw: str | None, unit: str | None) -> int:
    return as_int(raw) * UNIT_FACTORS[as_text(unit)]


def canonical_path(raw: str) -> str:
    segments: list[str] = []
    for segment in unicodedata.normalize("NFC", raw).split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segments.append(segment)
    return "/" + "/".join(segments)


def path_depth(path: str) -> int:
    return 0 if path == "/" else path.count("/")


def parent_directory(path: str) -> str:
    return path.rsplit("/", 1)[0] or "/"


def first_segment(path: str) -> str:
    return path.split("/")[1] if path != "/" else ""


def canonical_mode(raw: str) -> str:
    text = raw.strip()
    if text.startswith("d"):
        value = int(text[1:], 10)
    elif text.startswith("0o"):
        value = int(text[2:], 8)
    else:
        value = int(text, 8)
    return format(value & 0o7777, "04o")


def round_up(length: int, unit: int) -> int:
    return -(-length // unit) * unit


def utf8_length(text: str) -> int:
    return len(text.encode("utf-8"))


def joined(values) -> str:
    return "+".join(sorted(set(values)))


# ---------------------------------------------------------------------------
# Section 6: authoritative rows.

def authoritative(rows, key_of, rank_of, largest: bool = True) -> dict:
    chosen: dict = {}
    for row in rows:
        key, rank = key_of(row), rank_of(row)
        held = chosen.get(key)
        if held is None or (rank > held[0] if largest else rank < held[0]):
            chosen[key] = (rank, row)
    return {key: row for key, (_, row) in chosen.items()}


def latest_revision(row: Record) -> tuple[int, int]:
    return as_int(row["effective_seq"]), as_int(row["rev"])


# ---------------------------------------------------------------------------
# The estate: pools, devices and the inventory (sections 6 to 8).

@dataclass(frozen=True)
class Pool:
    pool_id: str
    alloc_unit: int
    root_depth_cap: int
    region: str
    barrier_seq: int


@dataclass(frozen=True)
class Window:
    index: int
    budget_bytes: int
    descriptor_budget: int


@dataclass(frozen=True)
class Device:
    device_id: str
    capacity_bytes: int
    existing_used_bytes: int
    reserve_ppm: int
    alloc_unit: int
    share_domain: str
    spill_device: str
    online: bool
    windows: tuple[Window, ...]

    @property
    def reserve_bytes(self) -> int:
        return self.capacity_bytes * self.reserve_ppm // 1000000

    @property
    def usable_bytes(self) -> int:
        return self.capacity_bytes - self.reserve_bytes

    @property
    def largest_window_bytes(self) -> int:
        return max((window.budget_bytes for window in self.windows), default=0)


@dataclass(frozen=True)
class InventoryObject:
    ino: int
    kind: str
    size_bytes: int
    mode: str
    uid: int
    gid: int
    mtime_ns: int
    storage_class: str
    pool_id: str
    declared_link_count: int
    state: str
    superseded_rows: int
    size_unit: str


@dataclass(frozen=True)
class PathRecord:
    path: str
    ordinal: int
    form: str


@dataclass
class Estate:
    pools: dict[str, Pool]
    devices: dict[str, Device]
    inventory: dict[int, InventoryObject]
    path_records: dict[int, list[PathRecord]]
    routes: dict[tuple[str, str], str]
    claims: dict[int, list[str]]
    holds: dict[int, list[str]]
    deadlines: dict[int, tuple[int, str]]
    attributes: dict[int, dict[str, int]]
    special_records: dict[int, Record]
    symlink_records: dict[int, Record]

    def alloc_unit_of(self, obj: InventoryObject) -> int:
        pool = self.pools.get(obj.pool_id)
        return pool.alloc_unit if pool else DEFAULT_POOL_ALLOC_UNIT


def build_pools(tables) -> dict[str, Pool]:
    barriers = authoritative(tables["barrier"], lambda row: row["pool_id"], latest_revision)
    pools = {}
    for row in tables["pool"]:
        barrier = barriers.get(row["pool_id"])
        pools[as_text(row["pool_id"])] = Pool(
            pool_id=as_text(row["pool_id"]),
            alloc_unit=as_int(row["alloc_unit"]),
            root_depth_cap=as_int(row["root_depth_cap"]),
            region=as_text(row["region"]),
            barrier_seq=as_int(barrier["barrier_seq"]) if barrier else 0,
        )
    return pools


def build_devices(tables) -> dict[str, Device]:
    capacities = authoritative(tables["capacity"], lambda row: row["device_id"], latest_revision)
    geometries = authoritative(tables["geometry"], lambda row: row["device_id"], latest_revision)
    windows: dict[str, list[Window]] = defaultdict(list)
    for row in tables["window"]:
        windows[as_text(row["device_id"])].append(Window(
            index=as_int(row["window_index"]),
            budget_bytes=to_bytes(row["io_budget_raw"], row["io_budget_unit"]),
            descriptor_budget=as_int(row["descriptor_budget"]),
        ))
    devices = {}
    for device_id in sorted(set(capacities) | set(geometries)):
        capacity = capacities.get(device_id)
        geometry = geometries.get(device_id)
        devices[device_id] = Device(
            device_id=device_id,
            capacity_bytes=to_bytes(capacity["capacity_raw"], capacity["capacity_unit"]) if capacity else 0,
            existing_used_bytes=(to_bytes(capacity["existing_used_raw"], capacity["existing_used_unit"])
                                 if capacity else 0),
            reserve_ppm=as_int(capacity["reserve_ppm"]) if capacity else 0,
            alloc_unit=as_int(geometry["alloc_unit"]) if geometry else 0,
            share_domain=as_text(geometry["share_domain"]) if geometry else "",
            spill_device=as_text(geometry["spill_device"]) if geometry else "",
            online=bool(geometry) and as_text(geometry["online"]) == "true",
            windows=tuple(sorted(windows.get(device_id, []), key=lambda window: window.index)),
        )
    return devices


def build_inventory(tables) -> dict[int, InventoryObject]:
    rows_by_ino: dict[int, list[Record]] = defaultdict(list)
    for row in tables["object"]:
        rows_by_ino[as_int(row["ino"])].append(row)
    inventory = {}
    for ino in sorted(rows_by_ino):
        rows = rows_by_ino[ino]
        row = max(rows, key=lambda candidate: (as_int(candidate["gen"]), as_int(candidate["mtime_ns"])))
        inventory[ino] = InventoryObject(
            ino=ino,
            kind=as_text(row["kind"]),
            size_bytes=to_bytes(row["size_raw"], row["size_unit"]),
            mode=canonical_mode(as_text(row["mode_raw"])),
            uid=as_int(row["uid"]),
            gid=as_int(row["gid"]),
            mtime_ns=as_int(row["mtime_ns"]),
            storage_class=as_text(row["class_raw"]).lower(),
            pool_id=as_text(row["pool_id"]),
            declared_link_count=as_int(row["link_count"]),
            state=as_text(row["state"]),
            superseded_rows=len(rows) - 1,
            size_unit=as_text(row["size_unit"]),
        )
    return inventory


def build_path_records(tables) -> dict[int, list[PathRecord]]:
    records: dict[int, list[PathRecord]] = defaultdict(list)
    for row in tables["path"]:
        records[as_int(row["ino"])].append(PathRecord(
            path=canonical_path(as_text(row["path_raw"])),
            ordinal=as_int(row["ordinal"]),
            form=as_text(row["form"]),
        ))
    for held in records.values():
        held.sort(key=lambda record: (record.ordinal, record.path, record.form))
    return dict(records)


def build_estate(tables) -> Estate:
    routes = authoritative(tables["route"], lambda row: (row["class"], row["pool_id"]),
                           lambda row: as_text(row["route_id"]), largest=False)
    claims: dict[int, list[str]] = defaultdict(list)
    for row in tables["claim"]:
        claims[as_int(row["ino"])].append(as_text(row["set_name"]))
    holds: dict[int, list[str]] = defaultdict(list)
    for row in tables["hold"]:
        if as_text(row["active"]) == "true":
            holds[as_int(row["ino"])].append(as_text(row["reason"]))
    # One deadline row per object; should a second ever arrive, the smaller is kept so
    # that the plan never depends on row order.
    deadlines = authoritative(
        tables["deadline"], lambda row: as_int(row["ino"]),
        lambda row: (as_int(row["deadline_window"]), as_text(row["class_override"])), largest=False)
    latest_attributes = authoritative(
        tables["xattr"], lambda row: (as_int(row["ino"]), as_text(row["name"])),
        lambda row: (as_int(row["gen"]), as_text(row["xattr_id"])))
    attributes: dict[int, dict[str, int]] = defaultdict(dict)
    for (ino, name), row in latest_attributes.items():
        attributes[ino][name] = as_int(row["value_len"])
    # The contract gives no rule for a second symlink record of one inode; the smallest
    # target is kept for the same reason as the deadline rows above.
    symlink_records = authoritative(
        tables["symlink"], lambda row: as_int(row["ino"]),
        lambda row: (as_text(row["target_raw"]), as_text(row["form"])), largest=False)
    return Estate(
        pools=build_pools(tables),
        devices=build_devices(tables),
        inventory=build_inventory(tables),
        path_records=build_path_records(tables),
        routes={key: as_text(row["device_id"]) for key, row in routes.items()},
        claims=dict(claims),
        holds=dict(holds),
        deadlines={ino: (as_int(row["deadline_window"]), as_text(row["class_override"]))
                   for ino, row in deadlines.items()},
        attributes=dict(attributes),
        special_records=authoritative(tables["special_node"], lambda row: as_int(row["ino"]),
                                      lambda row: as_text(row["node_id"]), largest=False),
        symlink_records=symlink_records,
    )


# ---------------------------------------------------------------------------
# Section 9: extents and their repairs.

@dataclass(frozen=True)
class Extent:
    ino: int
    ext_index: int
    offset: int
    length: int
    physical_id: str
    physical_class: str
    raw_physical_bytes: int
    flags: frozenset[str]
    repair: str

    @property
    def end(self) -> int:
        return self.offset + self.length

    @property
    def occupies_space(self) -> bool:
        """Surviving data and reserved extents are the ones that hold target space."""
        return self.physical_class in ("data", "reserved")

    @property
    def flags_text(self) -> str:
        return "+".join(flag for flag in FLAG_ORDER if flag in self.flags) or "none"


def physical_class_of(flags: frozenset[str]) -> str:
    if "hole" in flags:
        return "hole"
    if "inline" in flags:
        return "inline"
    if "unwritten" in flags:
        return "reserved"
    return "data"


def repair_extent(ino: int, ext_index: int, row: Record, size: int, alloc_unit: int,
                  surviving_end: int | None) -> Extent:
    """Truncate behind the last surviving end, then clip at the logical size."""
    offset = as_int(row["offset"])
    length = to_bytes(row["length_raw"], row["length_unit"])
    repairs = []
    if surviving_end is not None and offset < surviving_end:
        length -= surviving_end - offset
        offset = surviving_end
        repairs.append("truncated")
    if offset + length > size:
        length = size - offset
        repairs.append("clipped")
    flags = frozenset(word.strip() for word in as_text(row["flags"]).split(",")) & set(FLAG_ORDER)
    if length <= 0:
        length, repair, physical_class = 0, "void", "void"
    else:
        repair = "+".join(repairs) or "none"
        physical_class = physical_class_of(flags)
    raw_bytes = round_up(length, alloc_unit) if physical_class in ("data", "reserved") else 0
    return Extent(ino, ext_index, offset, length, as_text(row["physical_id"]), physical_class,
                  raw_bytes, flags, repair)


def repair_extents(tables, estate: Estate) -> dict[int, list[Extent]]:
    """Every extent of every regular object, repaired in ascending extent index."""
    latest = authoritative(tables["extent"],
                           lambda row: (as_int(row["ino"]), as_int(row["ext_index"])),
                           lambda row: as_int(row["gen"]))
    rows_by_ino: dict[int, list[tuple[int, Record]]] = defaultdict(list)
    for (ino, ext_index), row in latest.items():
        rows_by_ino[ino].append((ext_index, row))
    repaired = {}
    for ino in sorted(rows_by_ino):
        obj = estate.inventory.get(ino)
        if obj is None or obj.kind != "regular":
            continue
        alloc_unit = estate.alloc_unit_of(obj)
        surviving_end = None
        extents = []
        for ext_index, row in sorted(rows_by_ino[ino], key=lambda item: item[0]):
            extent = repair_extent(ino, ext_index, row, obj.size_bytes, alloc_unit, surviving_end)
            if extent.length > 0:
                surviving_end = extent.end
            extents.append(extent)
        repaired[ino] = extents
    return repaired


# ---------------------------------------------------------------------------
# Section 10: symlinks, resolved against the path index without being followed
# for their contents.

@dataclass(frozen=True)
class SymlinkReport:
    ino: int
    arrival_form: str
    target: str
    resolution: str
    hops: int
    physical_bytes: int

    @property
    def target_bytes(self) -> int:
        return utf8_length(self.target)

    @property
    def fast(self) -> bool:
        return self.target_bytes <= FAST_SYMLINK_MAX_BYTES


class SymlinkResolver:
    """Resolution runs against the path records as they were before the replay."""

    def __init__(self, estate: Estate):
        self.index: dict[str, int] = {}
        for ino in sorted(estate.path_records):
            for record in estate.path_records[ino]:
                self.index.setdefault(record.path, ino)
        self.indexed_first_segments = {first_segment(path) for path in self.index if path != "/"}
        self.symlink_inos = {ino for ino, obj in estate.inventory.items() if obj.kind == "symlink"}
        self.targets = {ino: as_text(row["target_raw"]) for ino, row in estate.symlink_records.items()}
        self.lowest_ordinal_path = {
            ino: min(records, key=lambda record: record.ordinal).path
            for ino, records in estate.path_records.items() if records}

    def resolved_target(self, ino: int) -> str:
        target = self.targets.get(ino, "")
        if target.startswith("/"):
            return canonical_path(target)
        base = parent_directory(self.lowest_ordinal_path.get(ino, "/"))
        return canonical_path(base + "/" + target)

    def resolve(self, start: int) -> tuple[str, int]:
        reached: set[str] = set()
        hops = 0
        current = start
        while True:
            resolved = self.resolved_target(current)
            if resolved in reached:
                return "cyclic", hops
            reached.add(resolved)
            holder = self.index.get(resolved)
            if holder is None:
                if first_segment(resolved) in self.indexed_first_segments:
                    return "dangling", hops
                return "outside", hops
            if holder not in self.symlink_inos:
                return "inside", hops
            hops += 1
            if hops == SYMLINK_HOP_CAP:
                return "capped", hops
            current = holder


def resolve_symlinks(estate: Estate) -> dict[int, SymlinkReport]:
    resolver = SymlinkResolver(estate)
    reports = {}
    for ino, obj in estate.inventory.items():
        if obj.kind != "symlink":
            continue
        record = estate.symlink_records.get(ino)
        target = unicodedata.normalize("NFC", as_text(record["target_raw"])) if record else ""
        resolution, hops = resolver.resolve(ino)
        slow_bytes = estate.alloc_unit_of(obj)
        reports[ino] = SymlinkReport(
            ino=ino,
            arrival_form=as_text(record["form"]) if record else "",
            target=target,
            resolution=resolution,
            hops=hops,
            physical_bytes=0 if utf8_length(target) <= FAST_SYMLINK_MAX_BYTES else slow_bytes,
        )
    return reports


# ---------------------------------------------------------------------------
# Section 11: replaying the activity above each pool's barrier.

@dataclass
class Event:
    seq: int
    ordinal: int
    kind: str
    ino: int
    path_a: str
    path_b: str
    arg_num: int
    arg_alt: int
    effect: str = ""
    reason: str = ""

    @property
    def target(self) -> str:
        if self.kind in ("unlink", "rename", "link"):
            return canonical_path(self.path_a)
        if self.kind == "setxattr":
            return self.path_a
        if self.kind == "write":
            return "{}:{}".format(self.arg_num, self.arg_alt)
        if self.kind in ("truncate", "chmod", "chown"):
            return str(self.arg_num)
        return ""


@dataclass
class ReplayOutcome:
    events: list[Event]
    paths: dict[int, list[PathRecord]]
    states: dict[int, str]
    attributes: dict[int, dict[str, int]]
    writes: dict[int, list[Event]] = field(default_factory=dict)
    truncates: dict[int, list[Event]] = field(default_factory=dict)
    renamed: set[int] = field(default_factory=set)


def read_events(tables) -> list[Event]:
    events = [Event(
        seq=as_int(row["seq"]), ordinal=as_int(row["ordinal"]), kind=as_text(row["kind"]),
        ino=as_int(row["ino"]), path_a=as_text(row["path_a"]), path_b=as_text(row["path_b"]),
        arg_num=as_int(row["arg_num"]), arg_alt=as_int(row["arg_alt"]),
    ) for row in tables["event"]]
    events.sort(key=lambda event: (event.seq, event.ordinal, event.kind, event.ino))
    return events


def judge_event(event: Event, estate: Estate, paths: dict[int, list[PathRecord]]) -> tuple[str, str]:
    """The outcome tests, in the order the contract writes them."""
    obj = estate.inventory.get(event.ino)
    if obj is None:
        return "ignored", "unknown_inode"
    pool = estate.pools.get(obj.pool_id)
    if pool is None:
        return "ignored", "unknown_pool"
    if event.seq <= pool.barrier_seq:
        return "absorbed", "at_or_before_barrier"
    if event.kind in ("unlink", "rename"):
        held = {record.path for record in paths.get(event.ino, [])}
        if canonical_path(event.path_a) not in held:
            return "ignored", "unknown_path"
    return "applied", ""


def apply_event(event: Event, outcome: ReplayOutcome) -> None:
    held = outcome.paths.setdefault(event.ino, [])
    if event.kind == "unlink":
        removed = canonical_path(event.path_a)
        held[:] = [record for record in held if record.path != removed]
        if not held:
            outcome.states[event.ino] = "pruned"
    elif event.kind == "rename":
        old, new = canonical_path(event.path_a), canonical_path(event.path_b)
        held[:] = [PathRecord(new, record.ordinal, record.form) if record.path == old else record
                   for record in held]
        outcome.renamed.add(event.ino)
    elif event.kind == "link":
        ordinal = max((record.ordinal for record in held), default=0) + 1
        held.append(PathRecord(canonical_path(event.path_a), ordinal, "nfc"))
    elif event.kind == "hold":
        outcome.states[event.ino] = "held"
    elif event.kind == "release":
        outcome.states[event.ino] = "live"
    elif event.kind == "setxattr":
        outcome.attributes.setdefault(event.ino, {})[event.path_a] = event.arg_num
    elif event.kind == "write":
        outcome.writes.setdefault(event.ino, []).append(event)
    elif event.kind == "truncate":
        outcome.truncates.setdefault(event.ino, []).append(event)


def replay_activity(tables, estate: Estate) -> ReplayOutcome:
    outcome = ReplayOutcome(
        events=read_events(tables),
        paths={ino: list(records) for ino, records in estate.path_records.items()},
        states={ino: obj.state for ino, obj in estate.inventory.items()},
        attributes={ino: dict(names) for ino, names in estate.attributes.items()},
    )
    for event in outcome.events:
        event.effect, event.reason = judge_event(event, estate, outcome.paths)
        if event.effect == "applied":
            apply_event(event, outcome)
    return outcome


# ---------------------------------------------------------------------------
# Section 13: the primary path and the hard link cluster of each inode.

PRIMARY_PATH_KEYS = (
    lambda record: path_depth(record.path),
    lambda record: utf8_length(record.path),
    lambda record: record.path,
    lambda record: record.ordinal,
)


@dataclass(frozen=True)
class Cluster:
    primary_path: str | None
    tiebreak_level: int
    member_paths: tuple[str, ...]
    nfd_records: int


def settle_cluster(records: list[PathRecord]) -> Cluster:
    if not records:
        return Cluster(None, 0, (), 0)
    contenders = list(records)
    level = 0
    if len(records) > 1:
        for level, key in enumerate(PRIMARY_PATH_KEYS, start=1):
            best = min(key(record) for record in contenders)
            contenders = [record for record in contenders if key(record) == best]
            if len(contenders) == 1:
                break
    primary = contenders[0].path
    members = tuple(sorted({record.path for record in records} - {primary}))
    nfd_records = sum(1 for record in records if record.form == "nfd")
    return Cluster(primary, level, members, nfd_records)


# ---------------------------------------------------------------------------
# Section 12: which objects are relocatable.

@dataclass(frozen=True)
class ScopeVerdict:
    reason: str
    depth: int

    @property
    def relocatable(self) -> bool:
        return self.reason == ""


def judge_scope(obj: InventoryObject, estate: Estate, replay: ReplayOutcome,
                cluster: Cluster) -> ScopeVerdict:
    depth = path_depth(cluster.primary_path) if cluster.primary_path else 0
    pool = estate.pools.get(obj.pool_id)
    claim_count = len(estate.claims.get(obj.ino, []))
    if pool is None:
        reason = "unknown_pool"
    elif replay.states.get(obj.ino) != "live" or cluster.primary_path is None:
        reason = "not_live"
    elif claim_count == 0:
        reason = "unclaimed"
    elif claim_count > 1:
        reason = "contested"
    elif depth > pool.root_depth_cap:
        reason = "depth_exceeded"
    else:
        reason = ""
    return ScopeVerdict(reason, depth)


# ---------------------------------------------------------------------------
# Section 14: what the interrupted run left behind.

@dataclass(frozen=True)
class ResumeState:
    ino: int
    ext_index: int
    seq: int
    committed: int
    expected: int
    status: str
    invalidated_by: int


def write_meets(write: Event, extent: Extent) -> bool:
    """Each half open range starts before the other ends. Ranges that only touch at an
    endpoint do not meet, and a void extent is met by a write running across its offset."""
    return write.arg_num < extent.end and extent.offset < write.arg_num + write.arg_alt


def earliest_undoing_seq(extent: Extent, replay: ReplayOutcome) -> int:
    undoing = [event for event in replay.writes.get(extent.ino, []) if write_meets(event, extent)]
    undoing += [event for event in replay.truncates.get(extent.ino, []) if event.arg_num < extent.end]
    return min((event.seq for event in undoing), default=0)


def classify_group(entries: list[tuple[int, int | None]], extent: Extent, barrier: int,
                   replay: ReplayOutcome) -> ResumeState:
    """Decide one checkpoint group; entries are (seq, committed or None for NIL)."""
    eligible = [entry for entry in entries if entry[0] <= barrier]
    expected = extent.raw_physical_bytes
    if not eligible:
        seq = min(entry[0] for entry in entries)
        return ResumeState(extent.ino, extent.ext_index, seq, -1, expected, "after_barrier", 0)
    seq, committed = max(eligible, key=lambda entry: (entry[0], entry[1] is not None, entry[1] or 0))
    if committed is None:
        return ResumeState(extent.ino, extent.ext_index, seq, -1, expected, "never_started", 0)
    if committed == expected:
        status = "durable"
    elif committed > expected:
        status = "overrun"
    elif committed == 0:
        status = "zeroed"
    else:
        status = "partial"
    invalidated_by = 0
    if status == "durable":
        invalidated_by = earliest_undoing_seq(extent, replay)
        if invalidated_by:
            status = "redirty"
    return ResumeState(extent.ino, extent.ext_index, seq, committed, expected, status, invalidated_by)


def classify_checkpoints(tables, estate: Estate, extents: dict[int, list[Extent]],
                         relocatable: set[int], replay: ReplayOutcome) -> dict[tuple[int, int], ResumeState]:
    groups: dict[tuple[int, int], list[tuple[int, int | None]]] = defaultdict(list)
    for row in tables["checkpoint"]:
        committed = row["bytes_committed"]
        groups[(as_int(row["ino"]), as_int(row["ext_index"]))].append(
            (as_int(row["seq"]), None if committed is None else int(committed)))
    by_key = {(extent.ino, extent.ext_index): extent
              for held in extents.values() for extent in held}
    states = {}
    for key in sorted(groups):
        ino = key[0]
        if ino not in relocatable or key not in by_key:
            continue
        barrier = estate.pools[estate.inventory[ino].pool_id].barrier_seq
        states[key] = classify_group(groups[key], by_key[key], barrier, replay)
    return states


# ---------------------------------------------------------------------------
# Section 15: extended attributes.

@dataclass(frozen=True)
class AttributeLedger:
    migrated: tuple[tuple[str, int], ...]
    dropped: tuple[tuple[str, int], ...]

    @property
    def migrated_names(self) -> list[str]:
        return sorted(name for name, _ in self.migrated)


def attribute_namespace(name: str) -> str:
    return name.split(".", 1)[0]


def is_migrated(name: str, storage_class: str) -> bool:
    namespace = attribute_namespace(name)
    if namespace in ("user", "trusted"):
        return True
    if namespace == "security":
        return storage_class in ("gold", "silver")
    if namespace == "system":
        return name in MIGRATED_SYSTEM_ATTRIBUTES
    return False


def ledger_attributes(attributes: dict[str, int], storage_class: str) -> AttributeLedger:
    migrated, dropped = [], []
    for name, value_length in attributes.items():
        entry = (name, utf8_length(name) + 1 + value_length)
        (migrated if is_migrated(name, storage_class) else dropped).append(entry)
    return AttributeLedger(tuple(sorted(migrated)), tuple(sorted(dropped)))


# ---------------------------------------------------------------------------
# Section 16: special nodes.

@dataclass(frozen=True)
class SpecialNode:
    ino: int
    node_kind: str
    major: int
    minor: int
    overflow: bool
    recreate: str

    @property
    def rdev(self) -> int:
        return self.major * 256 + self.minor


def special_node_of(obj: InventoryObject, record: Record | None) -> SpecialNode:
    if record is None:
        verb = "skip" if obj.kind in DEVICE_NODE_KINDS else RECREATE_VERBS[obj.kind]
        return SpecialNode(obj.ino, obj.kind, 0, 0, False, verb)
    raw_minor = as_int(record["minor"])
    overflow = raw_minor > 255
    return SpecialNode(obj.ino, obj.kind, as_int(record["major"]),
                       raw_minor % 256 if overflow else raw_minor, overflow, RECREATE_VERBS[obj.kind])


# ---------------------------------------------------------------------------
# Section 17: placement, sharing and the eviction fixed point.

@dataclass(frozen=True)
class Attribution:
    """Who owns each materialised copy under one placement."""
    owned: frozenset[tuple[int, int]]
    attributed: dict[int, int]
    owners: dict[tuple[str, str], int]
    strongest_class: dict[tuple[str, str], str]


@dataclass
class Placement:
    initial: dict[int, str]
    current: dict[int, str]
    reasons: dict[int, str]
    shed_round: dict[int, int]
    attribution: Attribution
    claims: dict[str, int]
    holders: dict[str, list[Extent]]


class PlacementPlanner:
    def __init__(self, estate: Estate, relocatable: list[int], clusters: dict[int, Cluster],
                 extents: dict[int, list[Extent]]):
        self.estate = estate
        self.devices = estate.devices
        self.relocatable = relocatable
        self.clusters = clusters
        # Physical identifier -> the surviving data and reserved extents of relocatable objects.
        self.holders: dict[str, list[Extent]] = defaultdict(list)
        for ino in relocatable:
            for extent in extents.get(ino, []):
                if extent.occupies_space:
                    self.holders[extent.physical_id].append(extent)

    def initial_device(self, obj: InventoryObject) -> tuple[str, str]:
        device_id = self.estate.routes.get((obj.storage_class, obj.pool_id))
        reason = ""
        if device_id not in self.devices:
            online = [candidate for candidate in sorted(self.devices) if self.devices[candidate].online]
            device_id, reason = online[0], "unrouted"
        hops = 0
        while not self.devices[device_id].online and hops < MAX_OFFLINE_HOPS:
            spill = self.devices[device_id].spill_device
            if spill not in self.devices:
                break
            device_id, hops = spill, hops + 1
        if hops:
            reason = "offline_spill" if self.devices[device_id].online else "offline_chain"
        return device_id, reason

    def domain_of(self, placement: dict[int, str], ino: int) -> str:
        return self.devices[placement[ino]].share_domain

    def attribute(self, placement: dict[int, str]) -> Attribution:
        """Each distinct domain holding an identifier materialises one copy."""
        owned, owners, strongest = set(), {}, {}
        attributed: dict[int, int] = defaultdict(int)
        for physical_id, carriers in self.holders.items():
            by_domain: dict[str, list[Extent]] = defaultdict(list)
            for extent in carriers:
                by_domain[self.domain_of(placement, extent.ino)].append(extent)
            for domain, extents in by_domain.items():
                owner = min({extent.ino for extent in extents},
                            key=lambda ino: (self.clusters[ino].primary_path, ino))
                copy_extent = min((extent for extent in extents if extent.ino == owner),
                                  key=lambda extent: extent.ext_index)
                owned.add((owner, copy_extent.ext_index))
                attributed[owner] += copy_extent.raw_physical_bytes
                owners[(physical_id, domain)] = owner
                strongest[(physical_id, domain)] = min(
                    (self.estate.inventory[extent.ino].storage_class for extent in extents),
                    key=CLASS_RANK.__getitem__)
        return Attribution(frozenset(owned), dict(attributed), owners, strongest)

    def claims(self, placement: dict[int, str], attribution: Attribution) -> dict[str, int]:
        claims = {device_id: 0 for device_id in self.devices}
        for ino, device_id in placement.items():
            claims[device_id] += attribution.attributed.get(ino, 0)
        return claims

    def headroom(self, device_id: str, claim: int) -> int:
        device = self.devices[device_id]
        return device.usable_bytes - (device.existing_used_bytes + claim)

    def shedding_order(self, ino: int, attribution: Attribution) -> tuple:
        """Weakest class first, then largest attributed bytes, then primary path, then inode."""
        obj = self.estate.inventory[ino]
        return (-CLASS_RANK[obj.storage_class], -attribution.attributed.get(ino, 0),
                self.clusters[ino].primary_path, ino)

    def shed_round(self, round_number: int, placement: dict[int, str],
                   shed_round: dict[int, int]) -> bool:
        """Walk the devices in identifier order; each overcommitted one sheds one object."""
        attribution = self.attribute(placement)
        claims = self.claims(placement, attribution)
        shed_any = False
        for device_id in sorted(self.devices):
            if self.headroom(device_id, claims[device_id]) >= 0:
                continue
            spill = self.devices[device_id].spill_device
            if spill == device_id or spill not in self.devices:
                continue
            candidates = [ino for ino, held_on in placement.items()
                          if held_on == device_id and ino not in shed_round]
            if not candidates:
                continue
            shed = min(candidates, key=lambda ino: self.shedding_order(ino, attribution))
            placement[shed] = spill
            shed_round[shed] = round_number
            moved = attribution.attributed.get(shed, 0)
            claims[device_id] -= moved
            claims[spill] += moved
            shed_any = True
        return shed_any

    def settle(self) -> Placement:
        initial, reasons = {}, {}
        for ino in self.relocatable:
            initial[ino], reasons[ino] = self.initial_device(self.estate.inventory[ino])
        current = dict(initial)
        shed_round: dict[int, int] = {}
        for round_number in range(1, MAX_SHEDDING_ROUNDS + 1):
            if not self.shed_round(round_number, current, shed_round):
                break
        attribution = self.attribute(current)
        return Placement(initial, current, reasons, shed_round, attribution,
                         self.claims(current, attribution), dict(self.holders))


# ---------------------------------------------------------------------------
# Section 18: the delta work set; section 20: the window schedule.

@dataclass
class CopyItem:
    ino: int
    ext_index: int
    device_id: str
    physical_id: str
    size: int
    origin: str
    effective_class: str
    deadline_window: int
    primary_path: str
    placements: list[tuple[int, int, bool]] = field(default_factory=list)
    residual: int = 0
    outcome: str = ""

    @property
    def placed_bytes(self) -> int:
        return sum(chunk for _, chunk, _ in self.placements)


def build_copy_items(estate: Estate, relocatable: list[int], extents: dict[int, list[Extent]],
                     placement: Placement, clusters: dict[int, Cluster],
                     resume: dict[tuple[int, int], ResumeState]) -> list[CopyItem]:
    items = []
    attribution = placement.attribution
    for ino in relocatable:
        device_id = placement.current[ino]
        domain = estate.devices[device_id].share_domain
        for extent in extents.get(ino, []):
            key = (ino, extent.ext_index)
            if extent.physical_class != "data" or key not in attribution.owned:
                continue
            state = resume.get(key)
            if state is not None and state.status == "durable":
                continue
            if state is None:
                origin = "fresh"
            elif state.status == "redirty":
                origin = "redirty"
            else:
                origin = "restart"
            items.append(CopyItem(
                ino=ino, ext_index=extent.ext_index, device_id=device_id,
                physical_id=extent.physical_id, size=extent.raw_physical_bytes, origin=origin,
                effective_class=attribution.strongest_class[(extent.physical_id, domain)],
                deadline_window=estate.deadlines.get(ino, (0, ""))[0],
                primary_path=clusters[ino].primary_path,
            ))
    items.sort(key=lambda item: (CLASS_RANK[item.effective_class], item.deadline_window,
                                 item.primary_path, item.ino, item.ext_index))
    return items


class WindowScheduler:
    """Bounded by the bytes a window carries and the inodes it holds open."""

    def __init__(self, devices: dict[str, Device]):
        self.devices = devices
        self.remaining = {(device.device_id, window.index): window.budget_bytes
                          for device in devices.values() for window in device.windows}
        self.open_inodes: dict[tuple[str, int], set[int]] = defaultdict(set)

    def admits(self, device: Device, window: Window, ino: int) -> bool:
        opened = self.open_inodes[(device.device_id, window.index)]
        return ino in opened or len(opened) < window.descriptor_budget

    def place(self, item: CopyItem, device: Device, window: Window, size: int) -> None:
        slot = (device.device_id, window.index)
        opened = item.ino not in self.open_inodes[slot]
        self.open_inodes[slot].add(item.ino)
        self.remaining[slot] -= size
        item.placements.append((window.index, size, opened))

    def offer(self, item: CopyItem) -> None:
        device = self.devices[item.device_id]
        first_with_room = next((window.index for window in device.windows
                                if self.remaining[(device.device_id, window.index)] > 0), None)
        if item.size <= device.largest_window_bytes:
            self.place_whole(item, device)
        else:
            self.place_split(item, device)
        if item.residual:
            item.outcome = "deferred"
        elif len(item.placements) > 1:
            item.outcome = "split"
        elif item.placements[0][0] == first_with_room:
            item.outcome = "whole"
        else:
            item.outcome = "rolled"

    def place_whole(self, item: CopyItem, device: Device) -> None:
        for window in device.windows:
            if (self.remaining[(device.device_id, window.index)] >= item.size
                    and self.admits(device, window, item.ino)):
                self.place(item, device, window, item.size)
                return
        item.residual = item.size

    def place_split(self, item: CopyItem, device: Device) -> None:
        residual = item.size
        for window in device.windows:
            if residual == 0:
                break
            room = self.remaining[(device.device_id, window.index)]
            if not self.admits(device, window, item.ino) or room < device.alloc_unit:
                continue
            chunk = residual if residual <= room else room // device.alloc_unit * device.alloc_unit
            self.place(item, device, window, chunk)
            residual -= chunk
        item.residual = residual


def schedule_windows(items: list[CopyItem], devices: dict[str, Device]) -> None:
    scheduler = WindowScheduler(devices)
    for item in items:
        scheduler.offer(item)


# ---------------------------------------------------------------------------
# Section 19: metadata operations.

@dataclass(frozen=True)
class Operation:
    op: str
    ino: int
    path: str
    detail: str
    bytes: int


def metadata_operations(obj: InventoryObject, cluster: Cluster, extents: list[Extent],
                        owned: frozenset[tuple[int, int]], special: SpecialNode | None,
                        symlink: SymlinkReport | None, ledger: AttributeLedger) -> list[Operation]:
    path = cluster.primary_path
    planned: list[tuple[str, str, int]] = []
    if obj.kind == "dir":
        planned.append(("mkdir", "", 0))
    if special is not None and special.recreate != "skip":
        planned.append((special.recreate, "{}:{}".format(special.major, special.minor), 0))
    if symlink is not None:
        planned.append(("symlink", symlink.target, 0))
    planned += [("link", member, 0) for member in cluster.member_paths]
    for extent in extents:
        if extent.physical_class == "data" and (obj.ino, extent.ext_index) not in owned:
            planned.append(("reflink", extent.physical_id, extent.raw_physical_bytes))
        elif extent.physical_class == "reserved":
            planned.append(("fallocate", str(extent.ext_index), extent.raw_physical_bytes))
    planned += [("setxattr", name, 0) for name in ledger.migrated_names]
    planned.append(("chown", "{}:{}".format(obj.uid, obj.gid), 0))
    planned.append(("chmod", obj.mode, 0))
    planned.append(("utimes", str(obj.mtime_ns), 0))
    planned.sort(key=lambda entry: (OPERATION_RANK[entry[0]], entry[1]))
    return [Operation(op, obj.ino, path, detail, size) for op, detail, size in planned]


# ---------------------------------------------------------------------------
# Section 21: cutover and rollback.

@dataclass(frozen=True)
class RollbackStep:
    step: int
    ino: int
    path: str
    guard: str
    reverse: str
    barrier_seq: int


def rollback_step(step: int, ino: int, estate: Estate, cluster: Cluster, deferred: bool,
                  has_copy_item: bool, redirty: bool, renamed: bool) -> RollbackStep:
    if redirty:
        guard = "digest_match"
    elif has_copy_item:
        guard = "size_match"
    else:
        guard = "xattr_count_match"
    if deferred:
        reverse = "abort_hold"
    elif cluster.member_paths:
        reverse = "restore_link"
    elif renamed:
        reverse = "rename_back"
    else:
        reverse = "unlink_target"
    barrier = estate.pools[estate.inventory[ino].pool_id].barrier_seq
    return RollbackStep(step, ino, cluster.primary_path, guard, reverse, barrier)


# ---------------------------------------------------------------------------
# The whole plan, computed stage by stage in contract order.

@dataclass
class Plan:
    estate: Estate
    extents: dict[int, list[Extent]]
    symlinks: dict[int, SymlinkReport]
    replay: ReplayOutcome
    clusters: dict[int, Cluster]
    scope: dict[int, ScopeVerdict]
    relocatable: list[int]
    resume: dict[tuple[int, int], ResumeState]
    ledgers: dict[int, AttributeLedger]
    special_nodes: dict[int, SpecialNode]
    placement: Placement
    copy_items: list[CopyItem]
    operations: list[Operation]
    cutover: list[int]
    rollback: list[RollbackStep]


def build_plan(tables) -> Plan:
    estate = build_estate(tables)
    extents = repair_extents(tables, estate)
    symlinks = resolve_symlinks(estate)
    replay = replay_activity(tables, estate)
    clusters = {ino: settle_cluster(replay.paths.get(ino, [])) for ino in estate.inventory}
    scope = {ino: judge_scope(obj, estate, replay, clusters[ino])
             for ino, obj in estate.inventory.items()}
    relocatable = sorted(ino for ino, verdict in scope.items() if verdict.relocatable)
    relocatable_set = set(relocatable)
    resume = classify_checkpoints(tables, estate, extents, relocatable_set, replay)
    ledgers = {ino: ledger_attributes(replay.attributes.get(ino, {}),
                                      estate.inventory[ino].storage_class) for ino in relocatable}
    special_nodes = {ino: special_node_of(estate.inventory[ino], estate.special_records.get(ino))
                     for ino in relocatable if estate.inventory[ino].kind in RECREATE_VERBS}
    placement = PlacementPlanner(estate, relocatable, clusters, extents).settle()
    copy_items = build_copy_items(estate, relocatable, extents, placement, clusters, resume)
    schedule_windows(copy_items, estate.devices)
    operations = []
    for ino in relocatable:
        operations += metadata_operations(
            estate.inventory[ino], clusters[ino], extents.get(ino, []), placement.attribution.owned,
            special_nodes.get(ino), symlinks.get(ino), ledgers[ino])
    deferred = {item.ino for item in copy_items if item.residual}
    with_copy_items = {item.ino for item in copy_items}
    redirty = {key[0] for key, state in resume.items() if state.status == "redirty"}
    cutover = sorted((ino for ino in relocatable if ino not in deferred),
                     key=lambda ino: (scope[ino].depth, clusters[ino].primary_path, ino))
    order = [(step, ino) for step, ino in enumerate(cutover, start=1)] + [(0, ino) for ino in sorted(deferred)]
    rollback = [rollback_step(step, ino, estate, clusters[ino], ino in deferred, ino in with_copy_items,
                              ino in redirty, ino in replay.renamed) for step, ino in order]
    return Plan(estate, extents, symlinks, replay, clusters, scope, relocatable, resume, ledgers,
                special_nodes, placement, copy_items, operations, cutover, rollback)


# ---------------------------------------------------------------------------
# Rendering (section 24 formats).

def csv_cell(value) -> str:
    text = str(value)
    if "," in text or '"' in text:
        return '"' + text.replace('"', '""') + '"'
    return text


def csv_table(header: str, rows) -> str:
    lines = [",".join(header.split())]
    lines += [",".join(csv_cell(value) for value in row) for row in rows]
    return "\n".join(lines) + "\n"


def tsv_table(header: str, rows) -> str:
    lines = ["\t".join(header.split())]
    lines += ["\t".join(str(value) for value in row) for row in rows]
    return "\n".join(lines) + "\n"


def json_lines(header: str, rows) -> str:
    keys = header.split()
    return "".join(json.dumps(dict(zip(keys, row)), ensure_ascii=False) + "\n" for row in rows)


def json_document(document) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def digest16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def render_object_inventory(plan: Plan) -> str:
    return json_lines(
        "ino kind size_bytes mode uid gid mtime_ns class pool_id declared_link_count state "
        "superseded_rows size_unit",
        ((obj.ino, obj.kind, obj.size_bytes, obj.mode, obj.uid, obj.gid, obj.mtime_ns,
          obj.storage_class, obj.pool_id, obj.declared_link_count, obj.state, obj.superseded_rows,
          obj.size_unit) for obj in plan.estate.inventory.values()))


def render_device_topology(plan: Plan) -> str:
    devices = plan.estate.devices.values()
    keys = ("device_id capacity_bytes existing_used_bytes reserve_ppm reserve_bytes usable_bytes "
            "alloc_unit share_domain spill_device online windows io_budget_bytes descriptor_peak").split()
    records = [dict(zip(keys, (
        device.device_id, device.capacity_bytes, device.existing_used_bytes, device.reserve_ppm,
        device.reserve_bytes, device.usable_bytes, device.alloc_unit, device.share_domain,
        device.spill_device, int(device.online), len(device.windows),
        sum(window.budget_bytes for window in device.windows),
        max((window.descriptor_budget for window in device.windows), default=0)))) for device in devices]
    return json_document({
        "devices": records,
        "device_count": len(records),
        "domain_count": len({device.share_domain for device in devices}),
    })


def render_extent_map(plan: Plan) -> str:
    return tsv_table(
        "ino ext_index offset length_bytes end_offset physical_id physical_class raw_physical_bytes "
        "flags repair",
        ((extent.ino, extent.ext_index, extent.offset, extent.length, extent.end, extent.physical_id,
          extent.physical_class, extent.raw_physical_bytes, extent.flags_text, extent.repair)
         for ino in sorted(plan.extents) for extent in plan.extents[ino]))


def render_symlink_topology(plan: Plan) -> str:
    return json_lines(
        "ino arrival_form target target_bytes kind resolution hops fast physical_bytes",
        ((report.ino, report.arrival_form, report.target, report.target_bytes,
          "absolute" if report.target.startswith("/") else "relative", report.resolution, report.hops,
          int(report.fast), report.physical_bytes) for _, report in sorted(plan.symlinks.items())))


def render_mutation_replay(plan: Plan) -> str:
    return json_lines(
        "seq ordinal kind ino target effect reason",
        ((event.seq, event.ordinal, event.kind, event.ino, event.target, event.effect, event.reason)
         for event in plan.replay.events))


def render_scope_resolution(plan: Plan) -> str:
    estate = plan.estate
    rows = []
    for ino, obj in estate.inventory.items():
        verdict = plan.scope[ino]
        pool = estate.pools.get(obj.pool_id)
        holds = estate.holds.get(ino, [])
        claims = estate.claims.get(ino, [])
        rows.append((ino, obj.storage_class, obj.pool_id, pool.region if pool else "",
                     int(verdict.relocatable), verdict.reason,
                     len({record.path for record in plan.replay.paths.get(ino, [])}),
                     len(holds), joined(holds), len(claims), joined(claims), verdict.depth))
    return csv_table("ino class pool_id pool_region relocatable reason paths_after_replay "
                     "hold_notices hold_reasons claims claim_sets depth", rows)


def render_link_clusters(plan: Plan) -> str:
    return json_lines(
        "ino primary_path tiebreak_level member_paths link_ops arrival_forms",
        ((ino, plan.clusters[ino].primary_path, plan.clusters[ino].tiebreak_level,
          list(plan.clusters[ino].member_paths), len(plan.clusters[ino].member_paths),
          plan.clusters[ino].nfd_records) for ino in plan.relocatable))


def render_resume_state(plan: Plan) -> str:
    return json_lines(
        "ino ext_index seq committed expected status invalidated_by",
        ((state.ino, state.ext_index, state.seq, state.committed, state.expected, state.status,
          state.invalidated_by) for _, state in sorted(plan.resume.items())))


def render_xattr_ledger(plan: Plan) -> str:
    rows = []
    for ino in plan.relocatable:
        ledger = plan.ledgers[ino]
        names = ledger.migrated_names
        rows.append((ino, len(ledger.migrated), len(ledger.dropped),
                     sum(size for _, size in ledger.migrated), sum(size for _, size in ledger.dropped),
                     names[0] if names else "", joined(attribute_namespace(name) for name in names)))
    return csv_table("ino migrated_count dropped_count migrated_bytes dropped_bytes "
                     "first_migrated_name namespaces", rows)


def render_special_nodes(plan: Plan) -> str:
    return tsv_table(
        "ino node_kind major minor rdev overflow recreate",
        ((node.ino, node.node_kind, node.major, node.minor, node.rdev, int(node.overflow), node.recreate)
         for _, node in sorted(plan.special_nodes.items())))


def render_placement(plan: Plan) -> str:
    placement, estate = plan.placement, plan.estate
    rows = []
    for ino in plan.relocatable:
        initial, final = placement.initial[ino], placement.current[ino]
        shed = placement.shed_round.get(ino, 0)
        window, override = estate.deadlines.get(ino, (0, ""))
        rows.append((ino, estate.inventory[ino].storage_class, initial, final,
                     estate.devices[final].share_domain, int(initial != final), shed,
                     "evicted" if shed else placement.reasons[ino],
                     placement.attribution.attributed.get(ino, 0), window, override))
    return csv_table("ino class initial_device device share_domain moved round reason "
                     "attributed_bytes deadline_window class_override", rows)


def render_sharing_expansion(plan: Plan) -> str:
    rows = []
    holders = plan.placement.holders
    for physical_id in sorted(holders):
        carriers = holders[physical_id]
        inodes = sorted({extent.ino for extent in carriers})
        if len(inodes) < 2:
            continue
        domains = sorted({plan.estate.devices[plan.placement.current[ino]].share_domain for ino in inodes})
        unit = max(extent.raw_physical_bytes for extent in carriers)
        owners = [plan.placement.attribution.owners[(physical_id, domain)] for domain in domains]
        rows.append((physical_id, inodes, domains, len(domains), owners, unit, unit * (len(domains) - 1)))
    return json_lines("physical_id referencing_inodes domains copies owners unit_bytes expanded_bytes", rows)


def render_allocation_projection(plan: Plan) -> str:
    placement = plan.placement
    claims = placement.claims
    rows = []
    for device_id, device in plan.estate.devices.items():
        projected = device.existing_used_bytes + claims[device_id]
        headroom = device.usable_bytes - projected
        shed_from = [ino for ino in placement.shed_round if placement.initial[ino] == device_id]
        shed_into = [ino for ino in placement.shed_round if placement.current[ino] == device_id]
        rows.append((device_id, device.capacity_bytes, device.reserve_bytes, device.usable_bytes,
                     device.existing_used_bytes, claims[device_id], projected, headroom,
                     int(headroom < 0), sum(1 for held in placement.current.values() if held == device_id),
                     len(shed_from), len(shed_into)))
    return csv_table("device_id capacity_bytes reserve_bytes usable_bytes existing_used_bytes "
                     "claim_bytes projected_bytes headroom_bytes over_committed placed_objects "
                     "evicted_out received_in", rows)


def render_delta_workset(plan: Plan) -> str:
    return tsv_table(
        "ino ext_index device_id physical_id copy_bytes origin effective_class deadline_window",
        ((item.ino, item.ext_index, item.device_id, item.physical_id, item.size, item.origin,
          item.effective_class, item.deadline_window) for item in plan.copy_items))


def render_metadata_workset(plan: Plan) -> str:
    return json_lines("op ino path detail bytes",
                      ((op.op, op.ino, op.path, op.detail, op.bytes) for op in plan.operations))


def render_window_schedule(plan: Plan) -> str:
    rows = [(item.device_id, window_index, item.ino, item.ext_index, chunk_index, size, int(opened))
            for item in plan.copy_items
            for chunk_index, (window_index, size, opened) in enumerate(item.placements)]
    rows.sort(key=lambda row: (row[0], row[1], row[2], row[3], row[4]))
    return tsv_table("device_id window_index ino ext_index chunk_index bytes descriptor_opened", rows)


def render_split_ledger(plan: Plan) -> str:
    items = sorted((item for item in plan.copy_items if item.outcome != "whole"),
                   key=lambda item: (item.ino, item.ext_index))
    return json_lines(
        "ino ext_index device_id status chunks placed_bytes residual_bytes first_window last_window",
        ((item.ino, item.ext_index, item.device_id, item.outcome, len(item.placements), item.placed_bytes,
          item.residual, item.placements[0][0] if item.placements else -1,
          item.placements[-1][0] if item.placements else -1) for item in items))


def render_descriptor_budget(plan: Plan) -> str:
    used_bytes: dict[tuple[str, int], int] = defaultdict(int)
    opened: dict[tuple[str, int], int] = defaultdict(int)
    for item in plan.copy_items:
        for window_index, size, opened_here in item.placements:
            used_bytes[(item.device_id, window_index)] += size
            opened[(item.device_id, window_index)] += int(opened_here)
    rows = []
    for device_id, device in plan.estate.devices.items():
        for window in device.windows:
            slot = (device_id, window.index)
            utilisation = used_bytes[slot] * 1000000 // window.budget_bytes if window.budget_bytes else 0
            rows.append((device_id, window.index, window.descriptor_budget, opened[slot],
                         window.budget_bytes, used_bytes[slot], utilisation))
    return csv_table("device_id window_index descriptor_budget descriptors_used io_budget_bytes "
                     "bytes_used utilisation_ppm", rows)


def render_cutover_sequence(plan: Plan) -> str:
    return "".join(plan.clusters[ino].primary_path + "\n" for ino in plan.cutover)


def render_rollback_plan(plan: Plan) -> str:
    return json_lines("step ino path guard reverse barrier_seq",
                      ((step.step, step.ino, step.path, step.guard, step.reverse, step.barrier_seq)
                       for step in plan.rollback))


def render_conservation(plan: Plan) -> str:
    """Section 22: attributed = copied + resumed + reserved + deferred on every device."""
    claims = plan.placement.claims
    copied: dict[str, int] = defaultdict(int)
    deferred: dict[str, int] = defaultdict(int)
    for item in plan.copy_items:
        copied[item.device_id] += item.placed_bytes
        deferred[item.device_id] += item.residual
    resumed: dict[str, int] = defaultdict(int)
    reserved: dict[str, int] = defaultdict(int)
    owned = plan.placement.attribution.owned
    for ino in plan.relocatable:
        device_id = plan.placement.current[ino]
        for extent in plan.extents.get(ino, []):
            if (ino, extent.ext_index) not in owned:
                continue
            state = plan.resume.get((ino, extent.ext_index))
            if extent.physical_class == "data" and state is not None and state.status == "durable":
                resumed[device_id] += extent.raw_physical_bytes
            elif extent.physical_class == "reserved":
                reserved[device_id] += extent.raw_physical_bytes
    keys = ("device_id attributed_bytes copied_bytes resumed_bytes reserved_bytes deferred_bytes "
            "residual_bytes").split()
    records = []
    for device_id in plan.estate.devices:
        residual = claims[device_id] - copied[device_id] - resumed[device_id] - reserved[device_id] - deferred[device_id]
        records.append(dict(zip(keys, (device_id, claims[device_id], copied[device_id], resumed[device_id],
                                       reserved[device_id], deferred[device_id], residual))))
    balanced = sum(1 for record in records if record["residual_bytes"] == 0)
    return json_document({"devices": records, "balanced_devices": balanced,
                          "unbalanced_devices": len(records) - balanced})


def render_cli_contract(_: Plan) -> str:
    return json_document({"tool": "stratactl", "usage": USAGE, "exit_ok": EXIT_OK,
                          "exit_usage": EXIT_USAGE, "exit_policy": EXIT_POLICY,
                          "artifact_count": len(ARTIFACT_NAMES)})


RENDERERS = {
    "object_inventory.jsonl": render_object_inventory,
    "device_topology.json": render_device_topology,
    "extent_map.tsv": render_extent_map,
    "symlink_topology.jsonl": render_symlink_topology,
    "mutation_replay.jsonl": render_mutation_replay,
    "scope_resolution.csv": render_scope_resolution,
    "link_clusters.jsonl": render_link_clusters,
    "resume_state.jsonl": render_resume_state,
    "xattr_ledger.csv": render_xattr_ledger,
    "special_nodes.tsv": render_special_nodes,
    "placement.csv": render_placement,
    "sharing_expansion.jsonl": render_sharing_expansion,
    "allocation_projection.csv": render_allocation_projection,
    "delta_workset.tsv": render_delta_workset,
    "metadata_workset.jsonl": render_metadata_workset,
    "window_schedule.tsv": render_window_schedule,
    "split_ledger.jsonl": render_split_ledger,
    "descriptor_budget.csv": render_descriptor_budget,
    "cutover_sequence.txt": render_cutover_sequence,
    "rollback_plan.jsonl": render_rollback_plan,
    "conservation.json": render_conservation,
    "cli_contract.json": render_cli_contract,
}


def render_artifacts(plan: Plan) -> dict[str, str]:
    """Section 23: the manifest digests the artifacts above it; the summary closes the plan."""
    artifacts = {name: RENDERERS[name](plan) for name in MANIFEST_SCOPE}
    entries = [{"name": name, "rows": text.count("\n"), "bytes": len(text.encode("utf-8")),
                "digest": digest16(text)} for name, text in artifacts.items()]
    artifacts["manifest.json"] = json_document({"artifacts": entries})
    artifacts["summary.json"] = json_document({
        "relocatable_objects": len(plan.relocatable),
        "excluded_objects": len(plan.estate.inventory) - len(plan.relocatable),
        "clusters": len(plan.relocatable),
        "copy_items": len(plan.copy_items),
        "metadata_ops": len(plan.operations),
        "cutover_steps": len(plan.cutover),
        "manifest_digest": digest16("\n".join(entry["digest"] for entry in entries)),
    })
    return artifacts


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: {}\n".format(USAGE))
        return EXIT_USAGE
    corpus_dir, out_dir = Path(argv[1]), Path(argv[2])
    if not corpus_dir.is_dir():
        warn("corpus path {} does not resolve to a directory".format(argv[1]))
        return EXIT_POLICY
    artifacts = render_artifacts(build_plan(read_corpus(corpus_dir)))
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ARTIFACT_NAMES:
            (out_dir / name).write_text(artifacts[name], encoding="utf-8", newline="\n")
    except OSError as error:
        warn("cannot write the plan into {}: {}".format(argv[2], error))
        return EXIT_WRITE_FAILED
    print("stratactl: wrote {} artifacts into {}".format(len(ARTIFACT_NAMES), argv[2]))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
