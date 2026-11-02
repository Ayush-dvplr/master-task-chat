#!/usr/bin/env python3
"""Conform engine: resolves one delivery scenario against the conform contract.

Every setting, table, window and rule parameter is read from the data folder the
engine is pointed at, so the same code resolves extracts it has never seen.

Published interface:

    run_scenario(data_dir, scenario) -> dict
    python3 optimize.py --data-dir D --scenario S --out F
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import re
import sys
from bisect import bisect_right
from pathlib import Path

SHARDS = ("a", "b")
PARTS = ("p1", "p2")
HALVES = ("2025h1", "2025h2", "2026h1", "2026h2")
ASSET_TABLES = ("assets_gen_a.csv", "assets_gen_b.csv", "assets_gen_c.csv")
# Reading order of the ingest logs: every _prev rotation first, then every _curr.
INGEST_ORDER = (
    "conform_host_a_prev.log",
    "conform_host_b_prev.log",
    "conform_host_a_curr.log",
    "conform_host_b_curr.log",
)

# Field positions of an event shard row, zero based, as format_notes.md records them.
F_UID = 0
F_TL = 1
F_SEQ = 2
F_REF = 3
F_GEN = 4
F_IN = 5
F_OUT = 6
F_HEAD = 7
F_TAIL = 8
F_PPM = 9
F_CLASS = 10
F_FROM = 11
F_TO = 12
F_EFF = 13
F_REC = 14
F_SRC = 15
F_OFF = 16
F_HOST = 17
F_TK = 19
F_REV = 20
F_SITE = 21

# The order conform_contract.md publishes for settling a contest of reason codes.
CODE_ORDER = (
    "WITHDRAWN",
    "TIE_UNRESOLVED",
    "ALIAS_UNKNOWN",
    "ALIAS_CYCLE",
    "ASSET_UNKNOWN",
    "RATE_UNKNOWN",
    "TRANSITION_UNKNOWN",
    "NEST_MISSING",
    "NEST_CYCLE",
    "SPAN_NONPOSITIVE",
    "HANDLE_OVERRUN",
    "RATE_INVALID",
    "CADENCE_UNKNOWN",
    "CFG_CYCLE",
    "DELIVERY_SUPPRESSED",
    "TERMINAL_STATE",
    "CLASS_EXCLUDED",
    "ILLEGAL_TRANSITION",
)
CODE_RANK = {code: index for index, code in enumerate(CODE_ORDER)}
STATE_DELIVERY = ("DELIVERY_SUPPRESSED", "TERMINAL_STATE", "CLASS_EXCLUDED", "ILLEGAL_TRANSITION")
OK_CODE = "OK"
NEST_CLASS = "nest"
REINSTATE_CLASS = "reinstate"
CLOSED_STATE = "withdrawn"


# --------------------------------------------------------------------------- #
# instants
# --------------------------------------------------------------------------- #

_EPOCH_CACHE: dict[str, int] = {}
_DAY_CACHE: dict[str, int] = {}


def _days(text: str) -> int:
    """Days from 1970-01-01 for a written date 'YYYY-MM-DD'."""
    hit = _DAY_CACHE.get(text)
    if hit is not None:
        return hit
    year = int(text[0:4])
    month = int(text[5:7])
    day = int(text[8:10])
    y = year - (1 if month <= 2 else 0)
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    total = era * 146097 + doe - 719468
    _DAY_CACHE[text] = total
    return total


def epoch(text: str) -> int:
    """Seconds from 1970-01-01T00:00:00Z for 'YYYY-MM-DDTHH:MM:SSZ' or with a space."""
    hit = _EPOCH_CACHE.get(text)
    if hit is not None:
        return hit
    seconds = (
        _days(text[0:10]) * 86400
        + int(text[11:13]) * 3600
        + int(text[14:16]) * 60
        + int(text[17:19])
    )
    _EPOCH_CACHE[text] = seconds
    return seconds


def _civil(days: int) -> tuple[int, int, int]:
    z = days + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return (yoe + era * 400 + (1 if m <= 2 else 0), m, d)


def iso(seconds: int) -> str:
    """Write an epoch as 'YYYY-MM-DDTHH:MM:SSZ'."""
    days, rest = divmod(seconds, 86400)
    year, month, day = _civil(days)
    hour, rest = divmod(rest, 3600)
    minute, second = divmod(rest, 60)
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (year, month, day, hour, minute, second)


WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


# --------------------------------------------------------------------------- #
# file readers
# --------------------------------------------------------------------------- #


def _read_delimited(path: Path, delimiter: str):
    """Rows of a delimited table, header first. No reference table quotes a field."""
    with path.open(encoding="utf-8", newline="") as handle:
        lines = handle.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return []
    width = len(lines[0].split(delimiter))
    out = []
    for line in lines:
        parts = line.split(delimiter)
        if len(parts) != width:
            parts = next(csv.reader([line], delimiter=delimiter))
        out.append(parts)
    return out


def read_table(path: Path, delimiter: str):
    """Rows of a delimited reference table, minus its header line."""
    rows = _read_delimited(path, delimiter)
    return rows[1:] if rows else []


def read_rows(path: Path):
    """Rows of a comma separated event shard, minus its header line.

    A shard quotes no field but the percentage reading of field nineteen, so a
    plain split serves, and a row that does not fit that shape falls back to
    the quoted reader.
    """
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        lines = handle.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for line in lines[1:]:
        if not line:
            continue
        at = line.find('"')
        if at < 0:
            rows.append(line.split(","))
            continue
        if line.count('"') != 2:
            rows.append(next(csv.reader([line])))
            continue
        stop = line.find('"', at + 1)
        rows.append(
            line[:at].split(",")[:-1]
            + [line[at + 1 : stop]]
            + line[stop + 1 :].split(",")[1:]
        )
    return rows


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


_UID_LINE = re.compile(r'"event_uid"\s*:\s*"([^"]*)"')


def read_jsonl_for(path: Path, uids):
    """Records of a JSON line stream whose event uid belongs to a set."""
    out = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            if "\\" in line:
                record = json.loads(line)
                if record.get("event_uid") in uids:
                    out.append(record)
                continue
            hit = _UID_LINE.search(line)
            if hit is None:
                record = json.loads(line)
                if record.get("event_uid") in uids:
                    out.append(record)
            elif hit.group(1) in uids:
                out.append(json.loads(line))
    return out


def read_properties(path: Path) -> dict[str, str]:
    """house.properties: name, separator, value, with backslash continuations."""
    settings: dict[str, str] = {}
    pending = None
    parts: list[str] = []
    for raw in path.read_text(encoding="utf-8").split("\n"):
        if raw[:1] == "#":
            continue
        if pending is not None and raw[:1] in (" ", "\t"):
            parts.append(raw.lstrip(" \t"))
            continue
        if pending is not None:
            settings[pending] = "".join(parts).strip()
            pending = None
        body = raw.strip()
        if not body:
            continue
        cut = body.find("=")
        colon = body.find(":")
        if cut >= 0 and (colon < 0 or cut < colon):
            sep = cut
        elif colon >= 0:
            sep = colon
        else:
            continue
        name = body[:sep].strip()
        value = body[sep + 1 :]
        if value.endswith("\\"):
            pending = name
            parts = [value[:-1]]
        else:
            settings[name] = value.strip()
    if pending is not None:
        settings[pending] = "".join(parts).strip()
    return settings


def read_ini(path: Path) -> dict[str, dict[str, str]]:
    """conform.ini / site_overrides.ini: sections of name = value lines."""
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").split("\n"):
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line[0] == "[" and line[-1] == "]":
            current = {}
            sections[line[1:-1].strip()] = current
            continue
        cut = line.find("=")
        if cut < 0:
            continue
        current[line[:cut].strip()] = line[cut + 1 :].strip()
    return sections


def to_int(text: str) -> int:
    """A whole number, with the round bracket form of a negative value."""
    body = text.strip()
    if not body:
        return 0
    if body[0] == "(" and body[-1] == ")":
        return -int(body[1:-1])
    return int(body)


# --------------------------------------------------------------------------- #
# windows
# --------------------------------------------------------------------------- #


class Windows:
    """One key's rows with their bounds read as epochs.

    A row whose `valid_from` stands at or after its `valid_to` states a window
    that contains no instant at all, so it matches nothing. Such a row, and any
    pair of rows that share a start, leave the rows less than perfectly ordered,
    and the rows are then read in the written order of the file instead.
    """

    __slots__ = ("starts", "stops", "payloads", "rows", "ordered")

    def __init__(self, rows):
        self.rows = list(rows)
        ordered = sorted(self.rows)
        self.starts = [row[0] for row in ordered]
        self.stops = [row[1] for row in ordered]
        self.payloads = [row[2] for row in ordered]
        self.ordered = all(row[0] < row[1] for row in ordered) and all(
            self.starts[i] > self.starts[i - 1] for i in range(1, len(self.starts))
        )

    def pick(self, when: int):
        if self.ordered:
            index = bisect_right(self.starts, when) - 1
            if index >= 0 and when < self.stops[index]:
                return self.payloads[index]
            return None
        for start, stop, payload in self.rows:
            if start <= when < stop:
                return payload
        return None


def index_windows(rows, key_index, bound_index, payload):
    """Group rows into Windows per key."""
    table: dict = {}
    single = len(key_index) == 1
    for row in rows:
        key = row[key_index[0]] if single else tuple(row[i] for i in key_index)
        table.setdefault(key, []).append(
            (epoch(row[bound_index[0]]), epoch(row[bound_index[1]]), payload(row))
        )
    return {key: Windows(value) for key, value in table.items()}


# --------------------------------------------------------------------------- #
# shared tables
# --------------------------------------------------------------------------- #


class Tables:
    """Every shared file of the data folder, read once per folder."""


_CACHE: dict[str, Tables] = {}


def load_tables(data_dir: str) -> Tables:
    root = Path(data_dir)
    key = str(root.resolve())
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    t = Tables()

    t.vendor = index_windows(
        read_table(root / "alias_hops_vendor.tsv", "\t"), (0,), (2, 3), lambda row: row[1]
    )
    t.house = index_windows(
        read_table(root / "alias_hops_house.tsv", "\t"), (0,), (2, 3), lambda row: row[1]
    )

    t.assets = {}
    for name in ASSET_TABLES:
        path = root / name
        if not path.exists():
            continue
        for row in read_table(path, ","):
            t.assets[(row[0], row[1])] = row[2]

    t.rates = index_windows(
        read_table(root / "rate_families.csv", ","),
        (0,),
        (1, 2),
        lambda row: (row[3], int(row[4]), int(row[5]), int(row[6]), row[7] == "true"),
    )
    t.cadence = {}
    for row in read_table(root / "cadence_map.tsv", "\t"):
        t.cadence[(row[0], row[1], row[2])] = (int(row[3]), int(row[4]))
    t.handles = index_windows(
        read_table(root / "handle_policy.tsv", "\t"), (0, 1), (2, 3), lambda row: row[4]
    )
    t.transitions = {}
    for row in read_table(root / "transition_matrix.csv", ","):
        t.transitions[(row[0], row[1], row[2])] = row[3]
    t.authority = index_windows(
        read_table(root / "authority_roles.csv", ","), (0, 1), (2, 3), lambda row: row[4]
    )
    t.tiers = index_windows(
        read_table(root / "source_tiers.csv", ","), (0,), (1, 2), lambda row: int(row[3])
    )
    t.clock = index_windows(
        read_table(root / "host_clock_offsets.csv", ","), (0,), (1, 2), lambda row: int(row[3])
    )

    rows = _read_delimited(root / "delivery_exceptions.csv", ",")
    head = rows[0] if rows else []
    t.exceptions: dict[tuple[str, str], list[dict]] = {}
    for row in rows[1:]:
        record = dict(zip(head, row))
        t.exceptions.setdefault((record["scenario"], record["timeline_id"]), []).append(record)

    rows = _read_delimited(root / "nesting_edges.tsv", "\t")
    head = rows[0] if rows else []
    t.nest_edges: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        record = dict(zip(head, row))
        t.nest_edges.setdefault(record["scenario"], {})[record["event_uid"]] = record[
            "required_timeline"
        ]

    # tape_index_v2 counts where both files carry a key; v1 is superseded there.
    t.tape = {}
    for name in ("tape_index_v2.txt", "tape_index_v1.txt"):
        path = root / name
        if not path.exists():
            continue
        later = name.endswith("_v2.txt")
        for line in path.read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                continue
            tape_key = line[0:12].strip()
            if later or tape_key not in t.tape:
                t.tape[tape_key] = (line[12:23], line[23:34], int(line[34:45].strip()), later)

    t.properties = read_properties(root / "house.properties")
    t.house_ini = read_ini(root / "conform.ini")
    t.site_ini = read_ini(root / "site_overrides.ini")
    t.cutoffs = json.loads((root / "scenario_cutoffs.json").read_text(encoding="utf-8"))
    codes = json.loads((root / "reason_codes.json").read_text(encoding="utf-8"))["codes"]
    t.kinds = {c["code"]: c["kind"] for c in codes}
    t.remedies = {c["code"]: c["remedy"] for c in codes}

    t.max_hops = int(t.properties.get("alias.max.hops", "0") or 0)
    t.pad_width = int(t.properties.get("alias.key.pad.width", "0") or 0)
    t.suppress_seconds = int(t.properties.get("suppress.window.hours", "0") or 0) * 3600
    t.max_depth = int(t.properties.get("nest.max.depth", "0") or 0)
    t.rounding_mode = t.properties.get("rounding.mode", "half_up").strip().lower()
    t.rounding = _ROUNDING.get(t.rounding_mode, round_half_up)
    t.tie_breaker = t.properties.get("override.tie.breaker", "approver_desc").strip().lower()
    reset = t.properties.get("phase.reset.policy", "exception_only").strip().lower()
    t.phase_reset = not (reset in ("never", "none", "off", "false"))

    t.ingest = _read_ingest(root, t.clock)
    t.vendor_keys: dict[str, str] = {}
    _CACHE[key] = t
    return t


def _read_ingest(root: Path, clock) -> dict[str, tuple[int, str, str]]:
    """uid -> (recorded epoch, host, recorded instant as written in UTC)."""
    seen: dict[str, tuple[int, str, str]] = {}
    for name in INGEST_ORDER:
        path = root / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line or line.isspace():
                    continue
                if line[0] in " \t":
                    continue
                parts = line.split()
                if len(parts) < 4 or parts[3] != "INGEST":
                    continue
                uid = None
                for token in parts[4:]:
                    if token[:4] == "uid=":
                        uid = token[4:]
                        break
                if uid is None:
                    continue
                host = parts[2]
                when = epoch(parts[0] + "T" + parts[1])
                offset = 0
                windows = clock.get(host)
                if windows is not None:
                    value = windows.pick(when)
                    if value is not None:
                        offset = value
                moment = when - offset * 60
                seen[uid] = (moment, host, iso(moment))
    return seen


# --------------------------------------------------------------------------- #
# scenario settings
# --------------------------------------------------------------------------- #


def resolve_setting(t: Tables, scenario: str, name: str):
    """One setting for one scenario through the inherits chain.

    Returns (value, cycle); cycle is True when the chain closed on itself.
    """
    site = t.site_ini
    house = t.house_ini
    visited: set[str] = set()
    section = "scenario." + scenario
    while section is not None:
        marker = section
        if marker in visited:
            return None, True
        visited.add(marker)
        for layer in (site, house):
            body = layer.get(marker)
            if body is not None and name in body:
                return body[name], False
        nxt = None
        for layer in (site, house):
            body = layer.get(marker)
            if body is not None and "inherits" in body:
                nxt = body["inherits"]
                break
        section = nxt
    return None, False


def excluded_classes(t: Tables, scenario: str):
    scenarios = t.cutoffs.get("scenarios", {})
    record = scenarios.get(scenario, {})
    if "exclude_classes" in record:
        value = record["exclude_classes"]
        if value is None:
            return list(t.cutoffs.get("defaults", {}).get("exclude_classes", []))
        return list(value)
    return list(t.cutoffs.get("defaults", {}).get("exclude_classes", []))


def occurrences(record: dict, bound: int | None = None):
    """Instants at which an exception row occurs, up to an inclusive bound."""
    start = epoch(record["effective_at"])
    if record["recurrence"] != "weekly":
        return [start]
    limit = record["until"]
    until = epoch(limit) if limit else bound
    if until is None:
        until = start
    weekday = WEEKDAYS.get(record["weekday"].strip().lower(), 0)
    text = record["time_of_day"].strip()
    seconds = int(text[0:2]) * 3600 + int(text[3:5]) * 60 + int(text[6:8])
    day = start - (start % 86400)
    when = day + ((weekday - _weekday_of(day)) % 7) * 86400 + seconds
    if when < start:
        when += 7 * 86400
    out = []
    while when <= until:
        out.append(when)
        when += 7 * 86400
    return out


def _weekday_of(day_seconds: int) -> int:
    return ((day_seconds // 86400) + 4) % 7


# --------------------------------------------------------------------------- #
# identity
# --------------------------------------------------------------------------- #

_DIGITS = "0123456789"


def vendor_key(text: str, pad: int) -> str:
    """The vendor key of an asset reference, as the contract writes it."""
    body = text.replace(" ", "").replace("-", "").upper()
    size = len(body)
    index = 0
    while index < size and body[index] not in _DIGITS:
        index += 1
    start = index
    while index < size and body[index] in _DIGITS:
        index += 1
    if start == index:
        return body
    return body[:start] + body[start:index].zfill(pad) + body[index:]


def vendor_key_of(t: Tables, reference: str) -> str:
    """The vendor key of an asset reference, memoised per written reference."""
    key = t.vendor_keys.get(reference)
    if key is None:
        key = vendor_key(reference, t.pad_width)
        t.vendor_keys[reference] = key
    return key


def canonical_code(t: Tables, reference: str, when: int):
    """(canonical code, reason) for an asset reference at an instant."""
    windows = t.vendor.get(vendor_key_of(t, reference))
    house = windows.pick(when) if windows is not None else None
    if house is None:
        return "", "ALIAS_UNKNOWN"
    code = house
    seen = {code}
    hops = 0
    while True:
        windows = t.house.get(code)
        nxt = windows.pick(when) if windows is not None else None
        if nxt is None:
            return code, None
        if nxt in seen or hops >= t.max_hops:
            return "", "ALIAS_CYCLE"
        seen.add(nxt)
        hops += 1
        code = nxt


# --------------------------------------------------------------------------- #
# timecode
# --------------------------------------------------------------------------- #

_TC_CACHE: dict[tuple[str, int, bool], int] = {}


def tc_frames(tc: str, nominal: int, drop: bool) -> int:
    """Frame count of a written timecode under timecode_spec.md."""
    hit = _TC_CACHE.get((tc, nominal, drop))
    if hit is not None:
        return hit
    minutes = int(tc[0:2]) * 60 + int(tc[3:5])
    total = (minutes * 60 + int(tc[6:8])) * nominal + int(tc[9:11])
    if drop:
        total -= 2 * (minutes - minutes // 10)
    _TC_CACHE[(tc, nominal, drop)] = total
    return total


def round_half_up(numerator: int, denominator: int) -> int:
    return (2 * numerator + denominator) // (2 * denominator)


def round_half_even(numerator: int, denominator: int) -> int:
    twice = (2 * numerator) // denominator
    return twice // 2 if twice % 2 == 0 else twice // 2 + 1


def round_half_down(numerator: int, denominator: int) -> int:
    return (2 * numerator - 1) // (2 * denominator)


def round_floor(numerator: int, denominator: int) -> int:
    return numerator // denominator


def round_ceil(numerator: int, denominator: int) -> int:
    return -((-numerator) // denominator)


_ROUNDING = {
    "half_up": round_half_up,
    "half_even": round_half_even,
    "half_down": round_half_down,
    "floor": round_floor,
    "ceil": round_ceil,
}


def round_speed(t: Tables, numerator: int, denominator: int) -> int:
    """Round a speed stage quotient under the mode house.properties names."""
    return t.rounding(numerator, denominator)


# --------------------------------------------------------------------------- #
# correction arbitration
# --------------------------------------------------------------------------- #


def tier_of(t: Tables, system: str, when: int):
    windows = t.tiers.get(system)
    return windows.pick(when) if windows is not None else None


def settle_tie(t: Tables, records):
    """Settle records sharing the highest revision.

    Returns (winner or None, how) with how in ('tier', 'time', 'unresolved'),
    under the ordering arbitration_notes.log records, read with source_tiers.csv.
    """
    ranked = []
    for record in records:
        when = epoch(record["recorded_at"])
        tier = tier_of(t, record["source_system"], when)
        ranked.append((-1 if tier is None else tier, when, record))
    best = max(item[0] for item in ranked)
    top = [item for item in ranked if item[0] == best]
    if len(top) == 1:
        return top[0][2], "tier"
    latest = max(item[1] for item in top)
    top = [item for item in top if item[1] == latest]
    if len(top) == 1:
        return top[0][2], "time"
    return None, "unresolved"


# --------------------------------------------------------------------------- #
# scenario resolution
# --------------------------------------------------------------------------- #


class Event:
    """One event row with its corrections, overrides and resolution."""

    __slots__ = (
        "uid", "timeline", "seq", "reference", "generation", "in_tc", "out_tc",
        "head", "tail", "ppm", "revision", "event_class", "state_from", "state_to",
        "eff", "eff_epoch", "row_rec", "offset", "tape_key", "site",
        "recorded", "recorded_host", "withdrawn", "tie", "amend", "required",
        "tape_source", "code", "outcome", "canonical", "family", "net_adjusted",
        "record_in", "record_out", "phase_in", "phase_out", "num", "den",
    )


def _resolve(data_dir: str, scenario: str) -> dict:
    t = load_tables(data_dir)
    root = Path(data_dir)

    delivery, cfg_cycle = resolve_setting(t, scenario, "delivery_family")
    cutover, _ = resolve_setting(t, scenario, "tape_cutover_utc")
    cutover_epoch = epoch(cutover) if cutover else None
    scenarios = t.cutoffs.get("scenarios", {}).get(scenario, {})
    cutoff_text = scenarios.get("cutoff_utc", "")
    excluded = frozenset(excluded_classes(t, scenario))
    kinds = t.kinds

    # ---- event shards -------------------------------------------------- #
    rows = []
    for shard in SHARDS:
        path = root / ("events_%s_%s.csv" % (scenario, shard))
        if path.exists():
            rows.extend(read_rows(path))

    events = []
    by_uid = {}
    ingest_hits = 0
    ingest_hosts: dict[str, int] = {}
    ingest_carried_past = 0
    cutoff_equals = 0
    for row in rows:
        e = Event()
        e.uid = row[F_UID]
        e.timeline = row[F_TL]
        e.reference = row[F_REF]
        e.generation = row[F_GEN]
        e.in_tc = row[F_IN]
        e.out_tc = row[F_OUT]
        e.event_class = row[F_CLASS]
        e.state_from = row[F_FROM]
        e.state_to = row[F_TO]
        e.eff = row[F_EFF]
        e.eff_epoch = epoch(row[F_EFF])
        e.row_rec = row[F_REC]
        e.tape_key = row[F_TK]
        e.site = row[F_SITE]
        try:
            e.seq = int(row[F_SEQ])
            e.head = int(row[F_HEAD])
            e.tail = int(row[F_TAIL])
            e.ppm = int(row[F_PPM])
            e.revision = int(row[F_REV])
        except ValueError:
            e.seq = to_int(row[F_SEQ])
            e.head = to_int(row[F_HEAD])
            e.tail = to_int(row[F_TAIL])
            e.ppm = to_int(row[F_PPM])
            e.revision = to_int(row[F_REV])
        offset = row[F_OFF]
        if offset[:1] == "(":
            e.offset = -int(offset[1:-1])
        elif offset:
            e.offset = int(offset)
        else:
            e.offset = 0
        hit = t.ingest.get(e.uid)
        if hit is not None:
            e.recorded = hit[2]
            e.recorded_host = hit[1]
            ingest_hits += 1
            ingest_hosts[hit[1]] = ingest_hosts.get(hit[1], 0) + 1
            if cutoff_text and e.recorded > cutoff_text and e.row_rec <= cutoff_text:
                ingest_carried_past += 1
        else:
            e.recorded = e.row_rec
            e.recorded_host = None
        e.withdrawn = False
        e.tie = False
        e.amend = None
        e.required = None
        e.tape_source = 0
        e.canonical = ""
        e.family = None
        e.code = None
        events.append(e)
        by_uid[e.uid] = e

    admitted = [e for e in events if not cutoff_text or e.recorded <= cutoff_text]
    for e in admitted:
        if cutoff_text and e.recorded == cutoff_text:
            cutoff_equals += 1

    # ---- corrections --------------------------------------------------- #
    corrections: dict[str, list] = {}
    for part in PARTS:
        path = root / ("corrections_%s_%s.jsonl" % (scenario, part))
        if path.exists():
            for record in read_jsonl(path):
                corrections.setdefault(record["event_uid"], []).append(record)

    time_admitted: dict[str, list] = {}
    for uid, records in corrections.items():
        if cutoff_text:
            kept = [r for r in records if r["recorded_at"] <= cutoff_text]
        else:
            kept = list(records)
        if kept:
            time_admitted[uid] = kept

    duplicates = 0
    superseded_deletes = 0
    contests = {"tier": 0, "time": 0, "unresolved": 0}
    unique_time_admitted: dict[str, list] = {}
    for uid, records in time_admitted.items():
        best = None
        for record in records:
            if best is None or record["revision"] > best:
                best = record["revision"]
        groups: dict[tuple, int] = {}
        ordered = []
        for record in records:
            marker = (
                record["revision"],
                record["source_system"],
                record["op"],
                tuple(sorted(record["fields"].items())),
            )
            if marker in groups:
                duplicates += 1
            else:
                groups[marker] = 1
                ordered.append(record)
        unique_time_admitted[uid] = ordered
        for record in records:
            if record["op"] == "delete" and record["revision"] < best:
                superseded_deletes += 1
        top = [r for r in ordered if r["revision"] == best]
        if len(top) > 1:
            _, how = settle_tie(t, top)
            contests[how] += 1

    applying: dict[str, tuple] = {}
    for uid, records in unique_time_admitted.items():
        row = by_uid.get(uid)
        limit = row.revision if row is not None else None
        kept = [r for r in records if limit is None or r["revision"] > limit]
        if not kept:
            continue
        best = max(r["revision"] for r in kept)
        top = [r for r in kept if r["revision"] == best]
        if len(top) == 1:
            applying[uid] = (top[0], None)
        else:
            winner, how = settle_tie(t, top)
            applying[uid] = (winner, how)

    for e in admitted:
        hit = applying.get(e.uid)
        if hit is None:
            continue
        record, how = hit
        if record is None:
            e.tie = True
        elif record["op"] == "delete":
            e.withdrawn = True
        else:
            e.amend = dict(record["fields"])

    # ---- overrides ----------------------------------------------------- #
    override_records: dict[str, list] = {}
    for half in HALVES:
        path = root / ("overrides_%s.jsonl" % half)
        if not path.exists():
            continue
        for record in read_jsonl_for(path, by_uid):
            override_records.setdefault(record["event_uid"], []).append(record)

    scope_rejected = 0
    scope_approvers: dict[str, int] = {}
    for uid, records in override_records.items():
        for record in records:
            when = record["recorded_at"]
            if cutoff_text and when > cutoff_text:
                continue
            if not _scope_ok(t, record["approver"], record["field"], epoch(when)):
                scope_rejected += 1
                approver = record["approver"]
                scope_approvers[approver] = scope_approvers.get(approver, 0) + 1

    for e in admitted:
        records = override_records.get(e.uid)
        if not records:
            continue
        chosen: dict[str, tuple] = {}
        for record in records:
            when = record["recorded_at"]
            if cutoff_text and when > cutoff_text:
                continue
            if when <= e.recorded:
                continue
            moment = epoch(when)
            if not _scope_ok(t, record["approver"], record["field"], moment):
                continue
            field = record["field"]
            slot = chosen.get(field)
            if slot is None:
                chosen[field] = (when, record["approver"], record["value"])
                continue
            better = when > slot[0] or (
                when == slot[0] and _approver_wins(t, record["approver"], slot[1])
            )
            if better:
                chosen[field] = (when, record["approver"], record["value"])
        if chosen:
            if e.amend is None:
                e.amend = {}
            for field, slot in chosen.items():
                e.amend[field] = slot[2]

    # ---- rows as corrected and overridden ------------------------------ #
    for e in admitted:
        amend = e.amend
        if not amend:
            continue
        if "head_handle" in amend:
            e.head = int(amend["head_handle"])
        if "tail_handle" in amend:
            e.tail = int(amend["tail_handle"])
        if "rate_adjust_ppm" in amend:
            e.ppm = int(amend["rate_adjust_ppm"])
        if "offset_frames" in amend:
            e.offset = int(amend["offset_frames"])
        if "site_code" in amend:
            e.site = amend["site_code"]
        if "source_in_tc" in amend:
            e.in_tc = amend["source_in_tc"]
        if "source_out_tc" in amend:
            e.out_tc = amend["source_out_tc"]
        if "state_to" in amend:
            e.state_to = amend["state_to"]
        if "tape_key" in amend:
            e.tape_key = amend["tape_key"]

    # ---- tape measurements --------------------------------------------- #
    for e in admitted:
        entry = t.tape.get(e.tape_key) if e.tape_key else None
        if entry is None:
            continue
        if cutover_epoch is None or e.eff_epoch >= cutover_epoch:
            continue
        e.in_tc = entry[0]
        e.out_tc = entry[1]
        e.ppm = entry[2] // 1000
        e.tape_source = 2 if entry[3] else 1

    # ---- timelines ----------------------------------------------------- #
    members: dict[str, list] = {}
    for e in admitted:
        members.setdefault(e.timeline, []).append(e)
    for bucket in members.values():
        bucket.sort(key=lambda e: (e.eff_epoch, e.seq, e.uid))

    # ---- nesting graph ------------------------------------------------- #
    edges = t.nest_edges.get(scenario, {})
    requires: dict[str, set] = {}
    for e in admitted:
        if e.event_class != NEST_CLASS:
            continue
        required = edges.get(e.uid)
        if required is not None:
            requires.setdefault(e.timeline, set()).add(required)
            e.required = required

    ring = _ring_closure(set(members), requires, t.max_depth)
    order = _resolution_order(set(members), requires, ring)

    # ---- delivery exceptions ------------------------------------------ #
    clear_at: dict[str, list] = {}
    suppress_at: dict[str, list] = {}
    bounds: dict[str, int] = {}
    for timeline, bucket in members.items():
        bounds[timeline] = bucket[-1].eff_epoch
    for (name, timeline), records in t.exceptions.items():
        if name != scenario or timeline not in members:
            continue
        for record in records:
            when = occurrences(record, bounds.get(timeline))
            if record["action"] == "clear_phase":
                clear_at.setdefault(timeline, []).extend(when)
            elif record["action"] == "suppress":
                suppress_at.setdefault(timeline, []).extend(when)
    for bucket in clear_at.values():
        bucket.sort()
    for bucket in suppress_at.values():
        bucket.sort()

    # ---- walk ---------------------------------------------------------- #
    record_frames: dict[str, int] = {}
    exit_phase: dict[str, int] = {}
    tallies: dict[str, int] = {}
    entries: dict[str, list] = {}
    applied_by: dict[str, int] = {}
    audited_by: dict[str, int] = {}
    rejected_by: dict[str, int] = {}
    half_frames = 0
    tape_used = tape_v2 = 0
    restart_differ = 0
    rates_table = t.rates
    cadence_table = t.cadence
    handles_table = t.handles
    transitions = t.transitions
    assets_table = t.assets
    phase_reset = t.phase_reset

    for timeline in order:
        bucket = members[timeline]
        entry_list = entries.setdefault(timeline, [])

        applied = audited = rejected = 0
        if timeline in ring:
            for e in bucket:
                _settle(e, "NEST_CYCLE", "rejected", 0, 0, 0, 0, 0)
                entry_list.append(_entry(e))
            record_frames[timeline] = 0
            exit_phase[timeline] = 0
            applied_by[timeline] = 0
            audited_by[timeline] = 0
            rejected_by[timeline] = len(bucket)
            continue

        cursor = 0
        phase = 0
        closed = False
        clears = clear_at.get(timeline)
        clear_index = 0
        clears_size = len(clears) if clears else 0
        suppressed = suppress_at.get(timeline)
        window = t.suppress_seconds

        for e in bucket:
            when = e.eff_epoch
            while clear_index < clears_size and clears[clear_index] <= when:
                if phase_reset:
                    phase = 0
                clear_index += 1

            if cfg_cycle:
                # A chain that closes on itself settles every event of the scenario.
                _settle(e, "CFG_CYCLE", "rejected", 0, cursor, cursor, phase, phase)
                entry_list.append(_entry(e))
                continue

            codes = []
            if e.withdrawn:
                codes.append("WITHDRAWN")
            elif e.tie:
                codes.append("TIE_UNRESOLVED")

            net_source = None
            net_adjusted = 0
            cadence = None
            source_family = None
            half = False
            if not codes:
                code, reason = canonical_code(t, e.reference, when)
                if reason is not None:
                    codes.append(reason)
                else:
                    e.canonical = code
                    e.family = assets_table.get((code, e.generation))
                    if e.family is None:
                        codes.append("ASSET_UNKNOWN")
                if e.event_class == NEST_CLASS and e.required is None:
                    codes.append("NEST_MISSING")

            if not codes:
                if e.event_class in excluded:
                    codes.append("CLASS_EXCLUDED")
                if suppressed:
                    index = bisect_right(suppressed, when) - 1
                    if index >= 0 and when < suppressed[index] + window:
                        codes.append("DELIVERY_SUPPRESSED")
                if closed and e.event_class != REINSTATE_CLASS:
                    codes.append("TERMINAL_STATE")
                legality = transitions.get((e.event_class, e.state_from, e.state_to))
                if legality is None:
                    codes.append("TRANSITION_UNKNOWN")
                elif legality != "apply":
                    codes.append("ILLEGAL_TRANSITION")
                if not (
                    "DELIVERY_SUPPRESSED" in codes
                    or "TERMINAL_STATE" in codes
                    or "CLASS_EXCLUDED" in codes
                    or "ILLEGAL_TRANSITION" in codes
                    or "TRANSITION_UNKNOWN" in codes
                ):
                    # state and delivery are settled first, so only an event that
                    # drew none of their codes reaches the measurement of section 6
                    rate_windows = rates_table.get(e.family)
                    rate = rate_windows.pick(when) if rate_windows is not None else None
                    if rate is None:
                        codes.append("RATE_UNKNOWN")
                    else:
                        source_family, _fps_num, _fps_den, nominal, drop = rate
                        if e.event_class == NEST_CLASS:
                            net_source = record_frames.get(e.required, 0)
                        else:
                            span = (
                                tc_frames(e.out_tc, nominal, drop)
                                + e.offset
                                - tc_frames(e.in_tc, nominal, drop)
                            )
                            if span <= 0:
                                codes.append("SPAN_NONPOSITIVE")
                            else:
                                handling = None
                                windows = handles_table.get((e.event_class, e.site))
                                if windows is not None:
                                    handling = windows.pick(when)
                                net_source = (
                                    span if handling != "excluded" else span - e.head - e.tail
                                )
                        if net_source is not None and net_source <= 0:
                            codes.append("HANDLE_OVERRUN")
                            net_source = None
                        if net_source is not None:
                            if e.ppm <= 0:
                                codes.append("RATE_INVALID")
                            else:
                                if 2 * (net_source * 1000000 % e.ppm) == e.ppm:
                                    half = True
                                net_adjusted = round_speed(t, net_source * 1000000, e.ppm)
                                cadence = cadence_table.get((e.site, source_family, delivery))
                                if cadence is None:
                                    codes.append("CADENCE_UNKNOWN")

            if codes:
                code = codes[0] if len(codes) == 1 else min(codes, key=CODE_RANK.__getitem__)
                outcome = "audited" if kinds.get(code) == "audit" else "rejected"
                if outcome == "audited":
                    audited += 1
                else:
                    rejected += 1
                if code != OK_CODE:
                    tallies[code] = tallies.get(code, 0) + 1
                _settle(e, code, outcome, 0, cursor, cursor, phase, phase)
            else:
                num, den = cadence
                span = ((phase + net_adjusted) * num) // den - (phase * num) // den
                _settle(e, OK_CODE, "applied", net_adjusted, cursor, cursor + span, phase,
                        (phase + net_adjusted) % den)
                e.num = num
                e.den = den
                cursor = e.record_out
                phase = e.phase_out
                if half:
                    half_frames += 1
                if e.tape_source:
                    tape_used += 1
                    if e.tape_source == 2:
                        tape_v2 += 1
                applied += 1
                if e.state_to == CLOSED_STATE:
                    closed = True
                elif e.event_class == REINSTATE_CLASS:
                    closed = False
            entry_list.append(_entry(e))

        # the same walk with the cadence phase restarted at zero for every event
        restarted = 0
        for e in bucket:
            if e.outcome == "applied" and e.num:
                restarted += (e.net_adjusted * e.num) // e.den
                if restarted != e.record_out:
                    restart_differ += 1

        record_frames[timeline] = cursor
        exit_phase[timeline] = phase
        applied_by[timeline] = applied
        audited_by[timeline] = audited
        rejected_by[timeline] = rejected

    timelines = []
    total_applied = total_audited = total_rejected = 0
    frames_total = 0
    phase_total = 0
    for timeline in sorted(members):
        bucket = members[timeline]
        applied = applied_by[timeline]
        audited = audited_by[timeline]
        rejected = rejected_by[timeline]
        total_applied += applied
        total_audited += audited
        total_rejected += rejected
        frames_total += record_frames[timeline]
        phase_total += exit_phase[timeline]
        timelines.append(
            {
                "timeline_id": timeline,
                "record_frames": record_frames[timeline],
                "exit_phase": exit_phase[timeline],
                "applied_events": applied,
                "audited_events": audited,
                "rejected_events": rejected,
                "events": entries[timeline],
            }
        )

    record = {
        "scenario": scenario,
        "cutoff_utc": cutoff_text,
        "delivery_family": delivery,
        "timelines": timelines,
        "totals": {
            "timelines": len(members),
            "events": len(admitted),
            "applied_events": total_applied,
            "audited_events": total_audited,
            "rejected_events": total_rejected,
            "record_frames": frames_total,
            "exit_phase_sum": phase_total,
        },
    }
    stats = {
        "input_events": len(rows),
        "admitted_events": len(admitted),
        "duplicates": duplicates,
        "superseded_deletes": superseded_deletes,
        "contests": contests,
        "ring": sorted(ring),
        "requires": requires,
        "half_frames": half_frames,
        "tape_used": tape_used,
        "tape_v2": tape_v2,
        "restart_differ": restart_differ,
        "ingest_hits": ingest_hits,
        "ingest_hosts": ingest_hosts,
        "ingest_carried_past": ingest_carried_past,
        "cutoff_equals": cutoff_equals,
        "scope_rejected": scope_rejected,
        "scope_approvers": scope_approvers,
        "tallies": tallies,
        "cfg_cycle": cfg_cycle,
        "delivery_family": delivery,
    }
    return {"record": record, "stats": stats, "events": events, "admitted": admitted,
            "tables": t, "requires": requires, "members": members}


def _scope_ok(t: Tables, approver: str, field: str, when: int) -> bool:
    windows = t.authority.get((approver, field))
    if windows is not None and windows.pick(when) is not None:
        return True
    windows = t.authority.get((approver, "all"))
    return windows is not None and windows.pick(when) is not None


def _approver_wins(t: Tables, left: str, right: str) -> bool:
    """Whether left beats right when two overrides tie on recorded time."""
    if t.tie_breaker.endswith("_asc"):
        return left < right
    return left > right


def _settle(e: Event, code, outcome, source_frames, record_in, record_out, phase_in, phase_out):
    e.code = code
    e.outcome = outcome
    e.net_adjusted = source_frames
    e.record_in = record_in
    e.record_out = record_out
    e.phase_in = phase_in
    e.phase_out = phase_out


def _entry(e: Event) -> dict:
    return {
        "event_uid": e.uid,
        "canonical_code": e.canonical,
        "generation": e.generation,
        "outcome": e.outcome,
        "reason_code": e.code,
        "source_frames": e.net_adjusted,
        "record_in_frames": e.record_in,
        "record_out_frames": e.record_out,
        "phase_in": e.phase_in,
        "phase_out": e.phase_out,
    }


def _ring_closure(timelines: set, requires: dict, max_depth: int) -> set:
    """Timelines a closed ring settles, with everything that reaches one."""
    dependents: dict[str, set] = {}
    for timeline, needs in requires.items():
        for need in needs:
            dependents.setdefault(need, set()).add(timeline)

    ring: set = set()
    state: dict[str, int] = {}
    for start in sorted(timelines):
        if state.get(start):
            continue
        state[start] = 1
        path = [start]
        stack = [(start, iter(sorted(requires.get(start, ()))))]
        while stack:
            node, walk = stack[-1]
            moved = False
            for nxt in walk:
                if nxt not in timelines:
                    continue
                mark = state.get(nxt, 0)
                if mark == 1:
                    ring.update(path[path.index(nxt):])
                elif mark == 0:
                    state[nxt] = 1
                    path.append(nxt)
                    stack.append((nxt, iter(sorted(requires.get(nxt, ())))))
                    moved = True
                    break
            if moved:
                continue
            state[node] = 2
            stack.pop()
            path.pop()

    # everything that requires a member of the ring, directly or through a further nest
    affected = set(ring)
    work = list(ring)
    while work:
        node = work.pop()
        for follower in dependents.get(node, ()):
            if follower in timelines and follower not in affected:
                affected.add(follower)
                work.append(follower)

    if not max_depth:
        return affected

    # a nesting chain deeper than the accepted depth stands as a closed ring
    depth: dict[str, int] = {}

    def chain_of(node: str) -> int:
        hit = depth.get(node)
        if hit is not None:
            return hit
        best = 0
        for need in requires.get(node, ()):
            if need not in timelines or need in affected:
                continue
            value = chain_of(need) + 1
            if value > best:
                best = value
        depth[node] = best
        return best

    deep = set()
    for timeline in timelines:
        if timeline in affected:
            continue
        if chain_of(timeline) > max_depth:
            deep.add(timeline)
    if deep:
        affected |= deep
        work = list(deep)
        while work:
            node = work.pop()
            for follower in dependents.get(node, ()):
                if follower in timelines and follower not in affected:
                    affected.add(follower)
                    work.append(follower)
    return affected


def _resolution_order(timelines: set, requires: dict, ring: set) -> list:
    """Every timeline a nest event requires, before the timeline holding it."""
    pending: dict[str, int] = {}
    dependents: dict[str, list] = {}
    for timeline in timelines:
        if timeline in ring:
            continue
        needs = {n for n in requires.get(timeline, ()) if n in timelines and n not in ring}
        pending[timeline] = len(needs)
        for need in needs:
            dependents.setdefault(need, []).append(timeline)
    ready = [timeline for timeline, count in pending.items() if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        timeline = heapq.heappop(ready)
        order.append(timeline)
        for follower in dependents.get(timeline, ()):
            pending[follower] -= 1
            if pending[follower] == 0:
                heapq.heappush(ready, follower)
    order.extend(sorted(timeline for timeline in timelines if timeline not in order))
    return order


# --------------------------------------------------------------------------- #
# interface
# --------------------------------------------------------------------------- #


def run_scenario(data_dir: str, scenario: str) -> dict:
    """Resolve one scenario and return its record as a dictionary."""
    return _resolve(data_dir, scenario)["record"]


def write_record(record: dict, path) -> None:
    body = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    target = Path(path)
    if str(target.parent):
        target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        handle.write(body)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Resolve one delivery scenario.")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    write_record(run_scenario(args.data_dir, args.scenario), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
