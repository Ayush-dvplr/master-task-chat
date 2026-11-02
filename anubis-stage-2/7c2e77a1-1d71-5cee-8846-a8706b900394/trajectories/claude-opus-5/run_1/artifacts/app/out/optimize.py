#!/usr/bin/env python3
"""Conform engine.

Resolves one delivery scenario against the house conform contract. Every rule
the engine applies is read from the data folder it is pointed at.
"""

from __future__ import annotations

import argparse
import csv
import glob
import heapq
import json
import os
import re
from datetime import datetime, timedelta

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"

CODE_ORDER = [
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
]
CODE_RANK = {code: i for i, code in enumerate(CODE_ORDER)}

WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

FIELD_MAP = {
    "head_handle": "head",
    "tail_handle": "tail",
    "rate_adjust_ppm": "ppm",
    "offset_frames": "offset",
    "source_in_tc": "in_tc",
    "source_out_tc": "out_tc",
    "state_to": "state_to",
    "site_code": "site",
    "tape_key": "tape_key",
}
NUMERIC_FIELDS = frozenset(("head", "tail", "ppm", "offset"))

_NEG = re.compile(r"^\((\d+)\)$")
_KEY = re.compile(r"^([A-Z]*)([0-9]*)(.*)$")
_CACHE = {}


# ----------------------------------------------------------------- utilities


def _dt(text):
    return datetime.strptime(text, ISO_FMT)


def _iso(when):
    return when.strftime(ISO_FMT)


def _int_frames(text):
    body = text.strip()
    if not body:
        return 0
    hit = _NEG.match(body)
    if hit:
        return -int(hit.group(1))
    return int(body)


def _pick(rows, when):
    for start, stop, payload in rows:
        if start <= when < stop:
            return payload
    return None


class _NegText:
    """Reverses the ordering of a text value inside a sort key."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.value == other.value

    def __lt__(self, other):
        return self.value > other.value


def _rows(path, delim=","):
    if not os.path.exists(path):
        return [], []
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delim)
        head = next(reader, None)
        if head is None:
            return [], []
        return head, [row for row in reader if row]


def _dict_rows(path, delim=","):
    head, body = _rows(path, delim)
    return [dict(zip(head, row)) for row in body]


def _read_ini(path):
    sections = {}
    if not os.path.exists(path):
        return sections
    current = None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            body = line.strip()
            if not body or body[0] in "#;":
                continue
            if body.startswith("[") and body.endswith("]"):
                current = {}
                sections[body[1:-1].strip()] = current
            elif current is not None and "=" in body:
                name, _, value = body.partition("=")
                current[name.strip()] = value.strip()
    return sections


def _read_properties(path):
    props = {}
    if not os.path.exists(path):
        return props
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    name = None
    value = ""
    for line in lines:
        if name is not None:
            piece = line.lstrip()
            if piece.endswith("\\"):
                value += piece[:-1]
                continue
            props[name] = (value + piece).strip()
            name = None
            value = ""
            continue
        body = line.strip()
        if not body or body[0] == "#":
            continue
        cuts = [body.index(sep) for sep in "=:" if sep in body]
        if not cuts:
            continue
        cut = min(cuts)
        head = body[:cut].strip()
        tail = body[cut + 1:].strip()
        if tail.endswith("\\"):
            name = head
            value = tail[:-1]
        else:
            props[head] = tail
    if name is not None:
        props[name] = value.strip()
    return props


# -------------------------------------------------------------- table loader


def _load_windows(path, key_cols, payload, delim=","):
    table = {}
    for row in _dict_rows(path, delim):
        key = tuple(row[col] for col in key_cols)
        if len(key) == 1:
            key = key[0]
        table.setdefault(key, []).append(
            (row["valid_from"], row["valid_to"], payload(row)))
    return table


def _load_tape(data_dir):
    tape = {}
    for name, mark in (("tape_index_v1.txt", 1), ("tape_index_v2.txt", 2)):
        path = os.path.join(data_dir, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                key = line[0:12].strip()
                if not key:
                    continue
                tape[key] = (line[12:23].strip(), line[23:34].strip(),
                             int(line[34:45].strip()), mark)
    return tape


def _load_ingest(data_dir, offsets):
    """The last INGEST line naming each uid, in prev then curr reading order."""
    names = sorted(os.path.basename(p) for p in
                   glob.glob(os.path.join(data_dir, "conform_host_*.log")))
    order = [n for n in names if n.endswith("_prev.log")]
    order += [n for n in names if not n.endswith("_prev.log")]
    seen = {}
    for name in order:
        with open(os.path.join(data_dir, name), encoding="utf-8") as handle:
            for line in handle:
                if not line[:1].strip():
                    continue
                parts = line.split()
                if len(parts) < 5 or parts[3] != "INGEST":
                    continue
                for token in parts[4:]:
                    if token.startswith("uid="):
                        seen[token[4:]] = (parts[0] + "T" + parts[1] + "Z",
                                           parts[2])
                        break
    resolved = {}
    for uid, (stamp, host) in seen.items():
        minutes = _pick(offsets.get(host, ()), stamp) or 0
        resolved[uid] = (_iso(_dt(stamp) - timedelta(minutes=minutes)), host)
    return resolved


_TIE_KEYS = ("tier_desc", "tier_asc", "recorded_desc", "recorded_asc")


def _tie_rank(spec, tier, recorded, system):
    out = []
    for part in spec:
        if part == "tier_desc":
            out.append(-tier)
        elif part == "tier_asc":
            out.append(tier)
        elif part == "recorded_desc":
            out.append(_NegText(recorded))
        elif part == "recorded_asc":
            out.append(recorded)
        elif part == "system_desc":
            out.append(_NegText(system))
        else:
            out.append(system)
    return out


def _read_arbitration(data_dir):
    cases = []
    path = os.path.join(data_dir, "arbitration_notes.log")
    if not os.path.exists(path):
        return cases
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line[:1].strip():
                continue
            parts = line.split()
            if len(parts) < 5 or parts[3] != "ARBITRATION":
                continue
            first = {}
            second = {}
            for token in parts[4:]:
                name, _, value = token.partition("=")
                (second if name in first else first)[name] = value
            cases.append((
                (first.get("left"), int(first.get("tier", "0")),
                 first.get("recorded", "")),
                (first.get("right"), int(second.get("tier", "0")),
                 second.get("recorded", "")),
                first.get("winner"),
            ))
    return cases


def _fit_tie_order(cases):
    """Fit the settled ordering of revision contests against the record."""
    specs = []
    for first in _TIE_KEYS:
        for second in _TIE_KEYS:
            if first.split("_")[0] == second.split("_")[0]:
                continue
            specs.append((first, second))
            specs.append((first, second, "system_desc"))
            specs.append((first, second, "system_asc"))
    best_spec = ("tier_desc", "recorded_desc")
    best_score = -1
    for spec in specs:
        score = 0
        for left, right, winner in cases:
            lhs = _tie_rank(spec, left[1], left[2], left[0])
            rhs = _tie_rank(spec, right[1], right[2], right[0])
            if lhs == rhs:
                pick = "none"
            else:
                pick = left[0] if lhs < rhs else right[0]
            if pick == winner:
                score += 1
        if score > best_score:
            best_score = score
            best_spec = spec
    return best_spec, best_score


def _folder_signature(data_dir):
    with os.scandir(data_dir) as entries:
        return tuple(sorted(
            (entry.name, entry.stat().st_mtime_ns, entry.stat().st_size)
            for entry in entries if entry.is_file()))


def load_tables(data_dir):
    signature = _folder_signature(data_dir)
    cached = _CACHE.get(data_dir)
    if cached is not None and cached["signature"] == signature:
        return cached

    def at(name):
        return os.path.join(data_dir, name)

    assets = {}
    for name in sorted(glob.glob(at("assets_gen_*.csv"))):
        for row in _dict_rows(name):
            assets[(row["canonical_code"], row["generation"])] = row["family_code"]

    cadence = {}
    for row in _dict_rows(at("cadence_map.tsv"), "\t"):
        cadence[(row["site_code"], row["source_family"],
                 row["delivery_family"])] = (int(row["num"]), int(row["den"]))

    transitions = {}
    for row in _dict_rows(at("transition_matrix.csv")):
        transitions[(row["event_class"], row["state_from"],
                     row["state_to"])] = row["legality"]

    authority = {}
    for row in _dict_rows(at("authority_roles.csv")):
        authority.setdefault((row["approver"], row["field_scope"]), []).append(
            (row["valid_from"], row["valid_to"], row["role"]))

    exceptions = {}
    for row in _dict_rows(at("delivery_exceptions.csv")):
        exceptions.setdefault(row["scenario"], []).append(row)

    nesting = {}
    for row in _dict_rows(at("nesting_edges.tsv"), "\t"):
        nesting[(row["scenario"], row["event_uid"])] = row["required_timeline"]

    with open(at("scenario_cutoffs.json"), encoding="utf-8") as handle:
        cutoffs = json.load(handle)
    with open(at("reason_codes.json"), encoding="utf-8") as handle:
        reasons = json.load(handle)

    offsets = _load_windows(at("host_clock_offsets.csv"), ["host"],
                            lambda r: int(r["offset_minutes"]))

    overrides = {}
    for name in sorted(glob.glob(at("overrides_*.jsonl"))):
        with open(name, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                overrides.setdefault(record["event_uid"], []).append(record)

    arbitration = _read_arbitration(data_dir)
    tie_spec, tie_fit = _fit_tie_order(arbitration)

    bundle = {
        "dir": data_dir,
        "vendor": _load_windows(at("alias_hops_vendor.tsv"), ["vendor_key"],
                                lambda r: r["house_code"], "\t"),
        "house": _load_windows(at("alias_hops_house.tsv"), ["house_code"],
                               lambda r: r["target_code"], "\t"),
        "assets": assets,
        "rates": _load_windows(
            at("rate_families.csv"), ["family_code"],
            lambda r: (r["rate_family"], int(r["nominal_fps"]),
                       r["drop_frame"] == "true")),
        "cadence": cadence,
        "handles": _load_windows(at("handle_policy.tsv"),
                                 ["event_class", "site_code"],
                                 lambda r: r["handling"], "\t"),
        "transitions": transitions,
        "authority": authority,
        "tiers": _load_windows(at("source_tiers.csv"), ["source_system"],
                               lambda r: int(r["tier"])),
        "offsets": offsets,
        "exceptions": exceptions,
        "nesting": nesting,
        "cutoffs": cutoffs,
        "kinds": {c["code"]: c["kind"] for c in reasons["codes"]},
        "remedies": {c["code"]: c["remedy"] for c in reasons["codes"]},
        "props": _read_properties(at("house.properties")),
        "ini_house": _read_ini(at("conform.ini")),
        "ini_site": _read_ini(at("site_overrides.ini")),
        "ingest": _load_ingest(data_dir, offsets),
        "tape": _load_tape(data_dir),
        "overrides": overrides,
        "arbitration": arbitration,
        "tie_spec": tie_spec,
        "tie_fit": tie_fit,
        "identity_memo": {},
        "tc_memo": {},
        "signature": signature,
    }
    _CACHE[data_dir] = bundle
    return bundle


# ------------------------------------------------------------------ settings


def resolve_setting(tables, scenario, name):
    """Layered section walk; returns the value and whether the chain cycled."""
    section = "scenario." + scenario
    seen = set()
    layers = (tables["ini_site"], tables["ini_house"])
    while section is not None:
        if section in seen:
            return None, True
        seen.add(section)
        for layer in layers:
            body = layer.get(section)
            if body and name in body:
                return body[name], False
        nxt = None
        for layer in layers:
            body = layer.get(section)
            if body and "inherits" in body:
                nxt = body["inherits"]
                break
        section = nxt
    return None, False


def _tc_frames(text, nominal, drop):
    parts = text.split(":")
    if len(parts) != 4:
        return None
    hh, mm, ss, ff = (int(p) for p in parts)
    minutes = hh * 60 + mm
    total = (minutes * 60 + ss) * nominal + ff
    if drop:
        total -= 2 * (minutes - minutes // 10)
    return total


def _vendor_key(asset_ref, pad):
    body = asset_ref.replace(" ", "").replace("-", "").upper()
    head, digits, tail = _KEY.match(body).groups()
    if digits:
        digits = digits.rjust(pad, "0")
    return head + digits + tail


def _canonical(tables, asset_ref, when, pad, max_hops):
    memo = tables["identity_memo"]
    hit = memo.get((asset_ref, when))
    if hit is not None:
        return hit
    answer = _canonical_uncached(tables, asset_ref, when, pad, max_hops)
    memo[(asset_ref, when)] = answer
    return answer


def _canonical_uncached(tables, asset_ref, when, pad, max_hops):
    code = _pick(tables["vendor"].get(_vendor_key(asset_ref, pad), ()), when)
    if code is None:
        return None, "ALIAS_UNKNOWN"
    house = tables["house"]
    seen = {code}
    hops = 0
    while True:
        nxt = _pick(house.get(code, ()), when)
        if nxt is None:
            return code, None
        hops += 1
        if hops > max_hops or nxt in seen:
            return None, "ALIAS_CYCLE"
        seen.add(nxt)
        code = nxt


# --------------------------------------------------------------- corrections


def _fields_key(fields):
    return tuple(sorted(
        (name, value if isinstance(value, (str, int, float, bool)) else repr(value))
        for name, value in fields.items()))


def _tie_key(tables, spec, system, recorded):
    tier = _pick(tables["tiers"].get(system, ()), recorded)
    return _tie_rank(spec, 0 if tier is None else tier, recorded, system)


def _load_corrections(tables, scenario, cutoff, diag):
    streams = {}
    duplicates = 0
    pattern = os.path.join(tables["dir"], "corrections_%s_*.jsonl" % scenario)
    for name in sorted(glob.glob(pattern)):
        with open(name, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                if record["recorded_at"] > cutoff:
                    continue
                slot = streams.setdefault(record["event_uid"], {})
                key = (record["revision"], record["source_system"],
                       record["op"], _fields_key(record["fields"]))
                if key in slot:
                    duplicates += 1
                    continue
                slot[key] = record
    if diag is not None:
        diag["duplicate_corrections"] = duplicates
        superseded = 0
        for slot in streams.values():
            top = max(record["revision"] for record in slot.values())
            superseded += sum(1 for record in slot.values()
                              if record["op"] == "delete"
                              and record["revision"] < top)
        diag["deletes_superseded"] = superseded
    return streams


def _settle(tables, slot, row_revision, spec, diag=None):
    """Return (fields, withdrawn, unresolved) for one event uid."""
    live = [r for r in slot.values() if r["revision"] > row_revision]
    if not live:
        return None, False, False
    top = max(r["revision"] for r in live)
    best = [r for r in live if r["revision"] == top]
    if len(best) > 1:
        ranked = sorted(best, key=lambda r: _tie_key(
            tables, spec, r["source_system"], r["recorded_at"]))
        first = _tie_key(tables, spec, ranked[0]["source_system"],
                         ranked[0]["recorded_at"])
        second = _tie_key(tables, spec, ranked[1]["source_system"],
                          ranked[1]["recorded_at"])
        if first == second:
            return None, False, True
        if diag is not None:
            tier_a = _pick(tables["tiers"].get(ranked[0]["source_system"], ()),
                           ranked[0]["recorded_at"])
            tier_b = _pick(tables["tiers"].get(ranked[1]["source_system"], ()),
                           ranked[1]["recorded_at"])
            tag = "ties_by_tier" if tier_a != tier_b else "ties_by_recorded"
            diag[tag] = diag.get(tag, 0) + 1
        chosen = ranked[0]
    else:
        chosen = best[0]
    if chosen["op"] == "delete":
        return None, True, False
    return chosen["fields"], False, False


# -------------------------------------------------------------------- events


class Event:
    __slots__ = (
        "uid", "timeline", "seq", "asset_ref", "generation", "in_tc", "out_tc",
        "head", "tail", "ppm", "cls", "state_from", "state_to", "effective",
        "recorded", "offset", "tape_key", "site", "revision", "codes", "staged",
        "canonical", "family", "rate_family", "nominal", "drop", "required",
        "outcome", "reason", "source_frames", "rec_in", "rec_out", "phase_in",
        "phase_out",
    )

    def __init__(self):
        self.codes = []
        self.staged = False
        self.canonical = None
        self.family = None
        self.rate_family = None
        self.nominal = 0
        self.drop = False
        self.required = None
        self.outcome = "applied"
        self.reason = "OK"
        self.source_frames = 0
        self.rec_in = 0
        self.rec_out = 0
        self.phase_in = 0
        self.phase_out = 0


def _occurrences(row):
    first = row["effective_at"]
    if row["recurrence"] != "weekly":
        return [first]
    weekday = WEEKDAYS.get(row["weekday"].strip().lower())
    until = row["until"].strip()
    if weekday is None or not until:
        return [first]
    start = _dt(first)
    stop = _dt(until)
    hh, mm, ss = (int(p) for p in row["time_of_day"].split(":"))
    probe = start.replace(hour=hh, minute=mm, second=ss)
    probe += timedelta(days=(weekday - probe.weekday()) % 7)
    if probe < start:
        probe += timedelta(days=7)
    out = []
    while probe <= stop:
        out.append(_iso(probe))
        probe += timedelta(days=7)
    return out


def _kahn(deps):
    waiting = {tid: set(needs) for tid, needs in deps.items()}
    dependents = {tid: [] for tid in waiting}
    for tid, needs in waiting.items():
        for need in needs:
            dependents[need].append(tid)
    ready = [tid for tid, needs in waiting.items() if not needs]
    heapq.heapify(ready)
    order = []
    while ready:
        tid = heapq.heappop(ready)
        order.append(tid)
        for child in dependents[tid]:
            waiting[child].discard(tid)
            if not waiting[child]:
                heapq.heappush(ready, child)
    return order


def _timeline_order(timelines, nest_edges, max_depth):
    """Resolution order of timelines, with the set settled as closed rings."""
    deps = {tid: set() for tid in timelines}
    for tid, required in nest_edges:
        if required in deps:
            deps[tid].add(required)

    rings = set()
    while True:
        live = {tid: {d for d in needs if d not in rings}
                for tid, needs in deps.items() if tid not in rings}
        order = _kahn(live)
        stuck = set(live) - set(order)
        if stuck:
            rings |= stuck
            continue
        depth = {}
        deep = set()
        for tid in order:
            depth[tid] = max((depth[d] + 1 for d in live[tid]), default=0)
            if depth[tid] > max_depth:
                deep.add(tid)
        if deep:
            rings |= deep
            continue
        return order + sorted(rings), rings


def _resolve(data_dir, scenario, diag=None):
    tables = load_tables(data_dir)
    props = tables["props"]
    pad = int(props.get("alias.key.pad.width", 6))
    max_hops = int(props.get("alias.max.hops", 4))
    max_depth = int(props.get("nest.max.depth", 6))
    suppress_hours = int(props.get("suppress.window.hours", 0))
    approver_desc = props.get("override.tie.breaker", "approver_desc") \
        == "approver_desc"
    mode = props.get("rounding.mode", "half_up")

    settings = tables["cutoffs"]["scenarios"][scenario]
    cutoff = settings["cutoff_utc"]
    classes = settings.get("exclude_classes")
    if classes is None:
        classes = tables["cutoffs"]["defaults"]["exclude_classes"]
    excluded = set(classes)

    delivery_family, cycle_one = resolve_setting(tables, scenario,
                                                 "delivery_family")
    cutover, cycle_two = resolve_setting(tables, scenario, "tape_cutover_utc")
    cfg_cycle = cycle_one or cycle_two

    ingest = tables["ingest"]
    rows = []
    for name in sorted(glob.glob(os.path.join(
            data_dir, "events_%s_*.csv" % scenario))):
        rows.extend(_rows(name)[1])

    if diag is not None:
        diag["ingest_sourced"] = 0
        diag["ingest_hosts"] = {}
        diag["ingest_pushed_out"] = 0
        diag["recorded_at_cutoff"] = 0

    admitted = []
    for row in rows:
        hit = ingest.get(row[0])
        if hit is None:
            recorded = row[14]
        else:
            recorded = hit[0]
            if diag is not None:
                diag["ingest_sourced"] += 1
                hosts = diag["ingest_hosts"]
                hosts[hit[1]] = hosts.get(hit[1], 0) + 1
                if recorded > cutoff >= row[14]:
                    diag["ingest_pushed_out"] += 1
        if recorded > cutoff:
            continue
        if diag is not None and recorded == cutoff:
            diag["recorded_at_cutoff"] += 1
        event = Event()
        event.uid = row[0]
        event.timeline = row[1]
        event.seq = row[2]
        event.asset_ref = row[3]
        event.generation = row[4]
        event.in_tc = row[5]
        event.out_tc = row[6]
        event.head = int(row[7])
        event.tail = int(row[8])
        event.ppm = int(row[9])
        event.cls = row[10]
        event.state_from = row[11]
        event.state_to = row[12]
        event.effective = row[13]
        event.recorded = recorded
        event.offset = _int_frames(row[16])
        event.tape_key = row[19]
        event.revision = int(row[20])
        event.site = row[21]
        admitted.append(event)

    by_uid = {event.uid: event for event in admitted}

    spec = tables["tie_spec"]
    streams = _load_corrections(tables, scenario, cutoff, diag)
    for uid, slot in streams.items():
        event = by_uid.get(uid)
        if event is None:
            if diag is not None:
                _settle(tables, slot, -1, spec, diag)
            continue
        fields, gone, unresolved = _settle(tables, slot, event.revision, spec,
                                           diag)
        if unresolved:
            event.codes.append("TIE_UNRESOLVED")
            continue
        if gone:
            event.codes.append("WITHDRAWN")
            continue
        if fields:
            for name, value in fields.items():
                attr = FIELD_MAP.get(name)
                if attr is None:
                    continue
                setattr(event, attr,
                        int(value) if attr in NUMERIC_FIELDS else str(value))

    authority = tables["authority"]
    if diag is not None:
        diag["override_no_scope"] = 0
        diag["override_no_scope_approvers"] = {}
    for uid, records in tables["overrides"].items():
        event = by_uid.get(uid)
        if event is None:
            continue
        winners = {}
        for record in records:
            recorded = record["recorded_at"]
            if recorded > cutoff:
                continue
            field = record["field"]
            approver = record["approver"]
            if not (_pick(authority.get((approver, field), ()), recorded)
                    or _pick(authority.get((approver, "all"), ()), recorded)):
                if diag is not None:
                    diag["override_no_scope"] += 1
                    bag = diag["override_no_scope_approvers"]
                    bag[approver] = bag.get(approver, 0) + 1
                continue
            if recorded <= event.recorded:
                continue
            rank = (recorded, approver if approver_desc else _NegText(approver))
            current = winners.get(field)
            if current is None or rank > current[0]:
                winners[field] = (rank, record["value"])
        for field, (_rank, value) in winners.items():
            attr = FIELD_MAP.get(field)
            if attr is None:
                continue
            setattr(event, attr,
                    int(value) if attr in NUMERIC_FIELDS else str(value))

    timelines = {}
    for event in admitted:
        timelines.setdefault(event.timeline, []).append(event)

    suppressions = {}
    clears = {}
    for row in tables["exceptions"].get(scenario, ()):
        tid = row["timeline_id"]
        for moment in _occurrences(row):
            if row["action"] == "suppress":
                end = _iso(_dt(moment) + timedelta(hours=suppress_hours))
                suppressions.setdefault(tid, []).append((moment, end))
            elif row["action"] == "clear_phase":
                clears.setdefault(tid, []).append(moment)

    nesting = tables["nesting"]
    assets = tables["assets"]
    rates = tables["rates"]
    transitions = tables["transitions"]
    for event in admitted:
        if event.codes:
            continue
        canonical, code = _canonical(tables, event.asset_ref, event.effective,
                                     pad, max_hops)
        if code:
            event.codes.append(code)
            continue
        event.canonical = canonical
        family = assets.get((canonical, event.generation))
        if family is None:
            event.codes.append("ASSET_UNKNOWN")
            continue
        event.family = family
        rate = _pick(rates.get(family, ()), event.effective)
        if rate is None:
            event.codes.append("RATE_UNKNOWN")
            continue
        event.rate_family, event.nominal, event.drop = rate
        event.staged = True
        if cfg_cycle:
            event.codes.append("CFG_CYCLE")
        legality = transitions.get((event.cls, event.state_from, event.state_to))
        if legality is None:
            event.codes.append("TRANSITION_UNKNOWN")
        elif legality != "apply":
            event.codes.append("ILLEGAL_TRANSITION")
        if event.cls == "nest":
            event.required = nesting.get((scenario, event.uid))
            if event.required is None:
                event.codes.append("NEST_MISSING")
        for start, end in suppressions.get(event.timeline, ()):
            if start <= event.effective < end:
                event.codes.append("DELIVERY_SUPPRESSED")
                break
        if event.cls in excluded:
            event.codes.append("CLASS_EXCLUDED")

    nest_edges = [(event.timeline, event.required) for event in admitted
                  if event.cls == "nest" and event.required is not None]
    order, rings = _timeline_order(timelines, nest_edges, max_depth)

    def event_key(event):
        seq = event.seq.strip()
        if seq.lstrip("-").isdigit():
            return (event.effective, 0, int(seq), "", event.uid)
        return (event.effective, 1, 0, seq, event.uid)

    for bucket in timelines.values():
        bucket.sort(key=event_key)

    cadence = tables["cadence"]
    handles = tables["handles"]
    tape_index = tables["tape"]
    tc_memo = tables["tc_memo"]
    kinds = tables["kinds"]
    record_frames = {}
    exit_phase = {}

    if diag is not None:
        diag.setdefault("tape_used", 0)
        diag.setdefault("tape_v2", 0)
        diag.setdefault("half_frame", 0)
        diag.setdefault("phase_shift_events", 0)

    for tid in order:
        bucket = timelines[tid]
        if tid in rings:
            for event in bucket:
                event.reason = "NEST_CYCLE"
                event.outcome = "rejected"
                event.source_frames = 0
                event.rec_in = event.rec_out = 0
                event.phase_in = event.phase_out = 0
            record_frames[tid] = 0
            exit_phase[tid] = 0
            continue
        cursor = 0
        phase = 0
        shadow = 0
        closed = False
        points = sorted(clears.get(tid, ()))
        at_point = 0
        for event in bucket:
            while at_point < len(points) and points[at_point] <= event.effective:
                phase = 0
                at_point += 1
            codes = event.codes
            if closed and event.staged and event.cls != "reinstate":
                codes = codes + ["TERMINAL_STATE"]
            if not codes:
                net = None
                ppm = event.ppm
                tape = tape_index.get(event.tape_key) if event.tape_key else None
                if tape is None or not cutover or event.effective >= cutover:
                    tape = None
                elif diag is not None:
                    diag["tape_used"] += 1
                    if tape[3] == 2:
                        diag["tape_v2"] += 1
                if tape is not None:
                    ppm = tape[2] // 1000
                if event.cls == "nest":
                    net = record_frames.get(event.required, 0)
                    if net <= 0:
                        codes = ["HANDLE_OVERRUN"]
                        net = None
                else:
                    in_tc = event.in_tc
                    out_tc = event.out_tc
                    if tape is not None:
                        in_tc, out_tc = tape[0], tape[1]
                    shape = (event.nominal, event.drop)
                    start = tc_memo.get((in_tc, shape))
                    if start is None:
                        start = tc_memo[(in_tc, shape)] = _tc_frames(
                            in_tc, event.nominal, event.drop)
                    stop = tc_memo.get((out_tc, shape))
                    if stop is None:
                        stop = tc_memo[(out_tc, shape)] = _tc_frames(
                            out_tc, event.nominal, event.drop)
                    span = stop + event.offset - start
                    if span <= 0:
                        codes = ["SPAN_NONPOSITIVE"]
                    else:
                        handling = _pick(handles.get((event.cls, event.site), ()),
                                         event.effective)
                        net = span - event.head - event.tail \
                            if handling == "excluded" else span
                        if net <= 0:
                            codes = ["HANDLE_OVERRUN"]
                            net = None
                if net is not None:
                    if ppm <= 0:
                        codes = ["RATE_INVALID"]
                    else:
                        pair = cadence.get((event.site, event.rate_family,
                                            delivery_family))
                        if pair is None:
                            codes = ["CADENCE_UNKNOWN"]
                        else:
                            scaled = net * 1000000
                            if mode == "half_up":
                                adjusted = (2 * scaled + ppm) // (2 * ppm)
                            elif mode == "half_down":
                                adjusted = -((ppm - 2 * scaled) // (2 * ppm))
                            elif mode in ("ceil", "up"):
                                adjusted = -(-scaled // ppm)
                            else:
                                adjusted = scaled // ppm
                            num, den = pair
                            total = phase + adjusted
                            event.source_frames = adjusted
                            event.phase_in = phase
                            event.phase_out = total % den
                            event.rec_in = cursor
                            event.rec_out = cursor + (total * num) // den \
                                - (phase * num) // den
                            event.outcome = "applied"
                            event.reason = "OK"
                            cursor = event.rec_out
                            phase = event.phase_out
                            closed = event.state_to == "withdrawn"
                            if diag is not None:
                                if (2 * scaled) % (2 * ppm) == ppm:
                                    diag["half_frame"] += 1
                                    bag = diag.setdefault("half_frame_by_scenario", {})
                                    bag[scenario] = bag.get(scenario, 0) + 1
                                shadow += (adjusted * num) // den
                                if shadow != event.rec_out:
                                    diag["phase_shift_events"] += 1
                                    bag = diag.setdefault("phase_shift_by_scenario",
                                                          {})
                                    bag[scenario] = bag.get(scenario, 0) + 1
                            continue
            code = min(codes, key=lambda c: CODE_RANK.get(c, len(CODE_ORDER)))
            event.reason = code
            event.outcome = "rejected" if kinds.get(code) == "reject" else "audited"
            event.source_frames = 0
            event.rec_in = event.rec_out = cursor
            event.phase_in = event.phase_out = phase
        record_frames[tid] = cursor
        exit_phase[tid] = phase

    out_timelines = []
    totals = {
        "timelines": 0,
        "events": 0,
        "applied_events": 0,
        "audited_events": 0,
        "rejected_events": 0,
        "record_frames": 0,
        "exit_phase_sum": 0,
    }
    for tid in sorted(timelines):
        bucket = timelines[tid]
        applied = audited = rejected = 0
        events = []
        for event in bucket:
            if event.outcome == "applied":
                applied += 1
            elif event.outcome == "audited":
                audited += 1
            else:
                rejected += 1
            events.append({
                "event_uid": event.uid,
                "canonical_code": event.canonical or "",
                "generation": event.generation,
                "outcome": event.outcome,
                "reason_code": event.reason,
                "source_frames": event.source_frames,
                "record_in_frames": event.rec_in,
                "record_out_frames": event.rec_out,
                "phase_in": event.phase_in,
                "phase_out": event.phase_out,
            })
        out_timelines.append({
            "timeline_id": tid,
            "record_frames": record_frames[tid],
            "exit_phase": exit_phase[tid],
            "applied_events": applied,
            "audited_events": audited,
            "rejected_events": rejected,
            "events": events,
        })
        totals["timelines"] += 1
        totals["events"] += len(bucket)
        totals["applied_events"] += applied
        totals["audited_events"] += audited
        totals["rejected_events"] += rejected
        totals["record_frames"] += record_frames[tid]
        totals["exit_phase_sum"] += exit_phase[tid]

    record = {
        "scenario": scenario,
        "cutoff_utc": cutoff,
        "delivery_family": delivery_family or "",
        "timelines": out_timelines,
        "totals": totals,
    }
    if diag is not None:
        diag["input_events"] = len(rows)
        diag["admitted_events"] = len(admitted)
        diag["events"] = admitted
        diag["timelines"] = timelines
        diag["rings"] = rings
        diag["nest_edges"] = nest_edges
        diag["order"] = order
        diag["record_frames"] = record_frames
    return record, len(rows), len(admitted)


def run_scenario(data_dir, scenario):
    """Resolve one scenario and return its record."""
    return _resolve(data_dir, scenario)[0]


def dumps(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Resolve one conform scenario.")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    payload = dumps(run_scenario(args.data_dir, args.scenario))
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
