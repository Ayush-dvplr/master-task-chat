#!/usr/bin/env python3
"""Build the conform engine and write every delivery artifact."""

# ENGINE_BEGIN
from __future__ import annotations

import bisect
import csv
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

SCENARIOS = ("visible", "peak", "steady", "burst", "latency")
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
CORRECTION_FIELD = {
    "source_in_tc": 5,
    "source_out_tc": 6,
    "head_handle": 7,
    "tail_handle": 8,
    "rate_adjust_ppm": 9,
    "state_to": 12,
    "offset_frames": 16,
    "tape_key": 19,
    "site_code": 21,
}
_BRACKET = re.compile(r"^\((\d+)\)$")
_ARB = re.compile(
    r"ARBITRATION case=(\S+) uid=(\S+) revision=(\d+) "
    r"left=(\S+) tier=(\d+) recorded=(\S+) "
    r"right=(\S+) tier=(\d+) recorded=(\S+) winner=(\S+)"
)
_INGEST = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (\S+) INGEST (.*)$")
_UID = re.compile(r"(?:^| )uid=(\S+)")


def _moment(text):
    """Read a written instant of the shape the corpus uses everywhere."""
    return datetime(
        int(text[0:4]),
        int(text[5:7]),
        int(text[8:10]),
        int(text[11:13]),
        int(text[14:16]),
        int(text[17:19]),
        tzinfo=timezone.utc,
    )


def _written(when):
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _whole(text):
    text = text.strip()
    if not text:
        return 0
    hit = _BRACKET.match(text)
    if hit:
        return -int(hit.group(1))
    return int(text)


def _delimited(path, delim):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delim)
        head = next(reader, None)
        if head is None:
            return []
        return [row for row in reader if row]


def _windowed(rows, key_of, from_at, to_at, value_of):
    """Group effective dated rows by key and sort them on the window start."""
    table = {}
    for row in rows:
        table.setdefault(key_of(row), []).append((row[from_at], row[to_at], value_of(row)))
    packed = {}
    for key, found in table.items():
        found.sort(key=lambda item: item[0])
        packed[key] = (
            [item[0] for item in found],
            [item[1] for item in found],
            [item[2] for item in found],
        )
    return packed


def _window_value(packed, key, when):
    entry = packed.get(key)
    if entry is None:
        return None
    starts, stops, values = entry
    slot = bisect.bisect_right(starts, when) - 1
    if slot < 0:
        return None
    if when < stops[slot]:
        return values[slot]
    return None


def _properties(path):
    settings = {}
    pending = ""
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if pending:
                line = pending + line
                pending = ""
            if not line or line.startswith("#"):
                continue
            if line.endswith("\\"):
                pending = line[:-1]
                continue
            cut = len(line)
            for mark in ("=", ":"):
                spot = line.find(mark)
                if spot != -1 and spot < cut:
                    cut = spot
            if cut == len(line):
                continue
            settings[line[:cut].strip()] = line[cut + 1 :].strip()
    return settings


def _sections(path):
    blocks = {}
    current = None
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1].strip()
                blocks.setdefault(current, {})
                continue
            if current is None or "=" not in line:
                continue
            name, value = line.split("=", 1)
            blocks[current][name.strip()] = value.strip()
    return blocks


def _layered_setting(over, base, start, name):
    """Ask the override layer then the base layer at each step of the chain."""
    seen = set()
    section = start
    while section is not None:
        if section in seen:
            return None, True
        seen.add(section)
        top = over.get(section, {})
        low = base.get(section, {})
        if name in top:
            return top[name], False
        if name in low:
            return low[name], False
        section = top.get("inherits", low.get("inherits"))
    return None, False


def _fit_arbitration(path):
    """Settle the same revision ordering from the recorded arbitration cases."""
    cases = []
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            hit = _ARB.search(raw)
            if hit is not None:
                cases.append(
                    (
                        hit.group(4),
                        int(hit.group(5)),
                        hit.group(6),
                        hit.group(7),
                        int(hit.group(8)),
                        hit.group(9),
                        hit.group(10),
                    )
                )
    if not cases:
        raise SystemExit("no arbitration cases on record")
    greater = lesser = later = earlier = declined = 0
    for left, left_tier, left_at, right, right_tier, right_at, winner in cases:
        if left_tier != right_tier:
            top = left if left_tier > right_tier else right
            if winner == top:
                greater += 1
            elif winner in (left, right):
                lesser += 1
        elif left_at != right_at:
            top = left if left_at > right_at else right
            if winner == top:
                later += 1
            elif winner in (left, right):
                earlier += 1
        elif winner == "none":
            declined += 1
    if greater <= lesser or later <= earlier:
        raise SystemExit("arbitration cases settle no ordering")
    return {"cases": len(cases), "by_tier": greater, "by_time": later, "declined": declined}


def _ingest_times(paths, offsets):
    """Rotated files are read before the live file and the last line wins."""
    picked = {}
    for path in paths:
        with open(path, "r", encoding="utf-8") as handle:
            for raw in handle:
                if raw[:1] in (" ", "\t"):
                    continue
                head = _INGEST.match(raw.rstrip("\n"))
                if head is None:
                    continue
                body = _UID.search(head.group(3))
                if body is None:
                    continue
                picked[body.group(1)] = (head.group(1), head.group(2))
    resolved = {}
    for uid, (stamp, host) in picked.items():
        reading = stamp[0:10] + "T" + stamp[11:19] + "Z"
        minutes = _window_value(offsets, host, reading)
        if minutes is None:
            continue
        resolved[uid] = (_written(_moment(reading) - timedelta(minutes=minutes)), host)
    return resolved


def _tape_index(path):
    rows = {}
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if len(line) < 69:
                continue
            key = line[0:12].strip()
            if key:
                rows[key] = (line[12:23].strip(), line[23:34].strip(), int(line[34:45].strip()))
    return rows


def load_tables(data_dir):
    """Read every shared table, configuration layer and observation log once."""
    here = os.path.join(data_dir, "")
    tables = {}
    tables["offsets"] = _windowed(
        _delimited(here + "host_clock_offsets.csv", ","),
        lambda row: row[0],
        1,
        2,
        lambda row: int(row[3]),
    )
    tables["vendor"] = _windowed(
        _delimited(here + "alias_hops_vendor.tsv", "\t"), lambda row: row[0], 2, 3, lambda row: row[1]
    )
    house_rows = _delimited(here + "alias_hops_house.tsv", "\t")
    tables["house"] = _windowed(house_rows, lambda row: row[0], 2, 3, lambda row: row[1])
    tables["house_keys"] = {row[0] for row in house_rows}
    assets = {}
    for name in ("assets_gen_a.csv", "assets_gen_b.csv", "assets_gen_c.csv"):
        for row in _delimited(here + name, ","):
            assets[(row[0], row[1])] = row[2]
    tables["assets"] = assets
    tables["families"] = _windowed(
        _delimited(here + "rate_families.csv", ","),
        lambda row: row[0],
        1,
        2,
        lambda row: (row[3], int(row[6]), row[7] == "true"),
    )
    cadence = {}
    for row in _delimited(here + "cadence_map.tsv", "\t"):
        cadence[(row[0], row[1], row[2])] = (int(row[3]), int(row[4]))
    tables["cadence"] = cadence
    tables["handles"] = _windowed(
        _delimited(here + "handle_policy.tsv", "\t"),
        lambda row: (row[0], row[1]),
        2,
        3,
        lambda row: row[4],
    )
    legality = {}
    for row in _delimited(here + "transition_matrix.csv", ","):
        legality[(row[0], row[1], row[2])] = row[3]
    tables["legality"] = legality
    tables["tiers"] = _windowed(
        _delimited(here + "source_tiers.csv", ","), lambda row: row[0], 1, 2, lambda row: int(row[3])
    )
    roles = {}
    for row in _delimited(here + "authority_roles.csv", ","):
        roles.setdefault((row[0], row[1]), []).append((row[2], row[3]))
    for spans in roles.values():
        spans.sort()
    tables["roles"] = roles
    tables["ingest"] = _ingest_times(
        sorted(glob.glob(here + "conform_host_*_prev.log"))
        + sorted(glob.glob(here + "conform_host_*_curr.log")),
        tables["offsets"],
    )
    tables["arbitration"] = _fit_arbitration(here + "arbitration_notes.log")
    tables["tape_old"] = _tape_index(here + "tape_index_v1.txt")
    tables["tape_new"] = _tape_index(here + "tape_index_v2.txt")
    tables["properties"] = _properties(here + "house.properties")
    tables["ini_base"] = _sections(here + "conform.ini")
    tables["ini_over"] = _sections(here + "site_overrides.ini")
    with open(here + "scenario_cutoffs.json", "r", encoding="utf-8") as handle:
        tables["cutoffs"] = json.load(handle)
    kinds = {}
    remedy = {}
    with open(here + "reason_codes.json", "r", encoding="utf-8") as handle:
        for entry in json.load(handle)["codes"]:
            kinds[entry["code"]] = entry["kind"]
            remedy[entry["code"]] = entry["remedy"]
    tables["kinds"] = kinds
    tables["remedy"] = remedy
    nests = {}
    for row in _delimited(here + "nesting_edges.tsv", "\t"):
        nests[(row[0], row[1])] = row[2]
    tables["nests"] = nests
    exceptions = {}
    for row in _delimited(here + "delivery_exceptions.csv", ","):
        exceptions.setdefault(row[0], []).append(row)
    tables["exceptions"] = exceptions
    overrides = {}
    for name in sorted(glob.glob(here + "overrides_*.jsonl")):
        with open(name, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    record = json.loads(line)
                    overrides.setdefault(record["event_uid"], []).append(record)
    tables["overrides"] = overrides
    return tables


_CACHE = {}


def _tables_for(data_dir):
    key = os.path.realpath(data_dir)
    held = _CACHE.get(key)
    if held is None:
        held = load_tables(key)
        _CACHE[key] = held
    return held


def _settings(tables, scenario):
    start = "scenario." + scenario
    family, ring_a = _layered_setting(
        tables["ini_over"], tables["ini_base"], start, "delivery_family"
    )
    cutover, ring_b = _layered_setting(
        tables["ini_over"], tables["ini_base"], start, "tape_cutover_utc"
    )
    block = tables["cutoffs"]["scenarios"][scenario]
    excluded = block.get("exclude_classes", None)
    if excluded is None:
        excluded = tables["cutoffs"]["defaults"]["exclude_classes"]
    return {
        "delivery_family": family,
        "tape_cutover": cutover,
        "cutoff": block["cutoff_utc"],
        "excluded": frozenset(excluded),
        "ring": ring_a or ring_b,
    }


def _occurrences(row):
    first = _moment(row[3])
    if row[4] != "weekly":
        return [row[3]]
    stop = _moment(row[5])
    want = WEEKDAYS[row[6]]
    hour, minute, second = (int(part) for part in row[7].split(":"))
    walk = first.replace(hour=hour, minute=minute, second=second)
    while walk.weekday() != want or walk < first:
        walk += timedelta(days=1)
    out = []
    while walk <= stop:
        out.append(_written(walk))
        walk += timedelta(days=7)
    return out


def _exception_plan(tables, scenario, hours):
    holds = {}
    clears = {}
    for row in tables["exceptions"].get(scenario, ()):
        for moment in _occurrences(row):
            if row[2] == "suppress":
                stop = _written(_moment(moment) + timedelta(hours=hours))
                holds.setdefault(row[1], []).append((moment, stop))
            elif row[2] == "clear_phase":
                clears.setdefault(row[1], []).append(moment)
    for spans in holds.values():
        spans.sort()
    for marks in clears.values():
        marks.sort()
    return holds, clears


def _tie_winner(tables, rows):
    """Greater source tier, then the later recorded instant, else undecided."""
    graded = []
    for record in rows:
        tier = _window_value(tables["tiers"], record["source_system"], record["recorded_at"])
        if tier is None:
            return None
        graded.append((tier, record))
    best = max(tier for tier, _ in graded)
    short = [record for tier, record in graded if tier == best]
    if len(short) == 1:
        return short[0]
    latest = max(record["recorded_at"] for record in short)
    final = [record for record in short if record["recorded_at"] == latest]
    if len(final) == 1:
        return final[0]
    return None


def _corrections(tables, data_dir, scenario, cutoff):
    """Keep the single highest revision record on record for each event."""
    best = {}
    seen_ops = {}
    for name in sorted(glob.glob(os.path.join(data_dir, "corrections_" + scenario + "_*.jsonl"))):
        with open(name, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record["recorded_at"] > cutoff:
                    continue
                uid = record["event_uid"]
                revision = record["revision"]
                seen_ops.setdefault(uid, []).append((revision, record["op"]))
                slot = best.get(uid)
                if slot is None or revision > slot[0]:
                    best[uid] = (revision, [record])
                elif revision == slot[0]:
                    slot[1].append(record)
    stale = 0
    for rows in seen_ops.values():
        top = max(revision for revision, _ in rows)
        stale += sum(1 for revision, op in rows if op == "delete" and revision < top)
    picked = {}
    duplicates = 0
    by_tier = 0
    by_time = 0
    undecided = 0
    for uid, (revision, group) in best.items():
        unique = {}
        for record in group:
            stamp = (
                record["source_system"],
                record["op"],
                json.dumps(record["fields"], sort_keys=True),
            )
            if stamp in unique:
                duplicates += 1
                continue
            unique[stamp] = record
        rows = list(unique.values())
        if len(rows) == 1:
            picked[uid] = (revision, rows[0], "")
            continue
        tiers = {
            _window_value(tables["tiers"], record["source_system"], record["recorded_at"])
            for record in rows
        }
        winner = _tie_winner(tables, rows)
        if winner is None:
            undecided += 1
            picked[uid] = (revision, None, "TIE_UNRESOLVED")
            continue
        if len(tiers) > 1:
            by_tier += 1
        else:
            by_time += 1
        picked[uid] = (revision, winner, "")
    counts = {
        "duplicates": duplicates,
        "by_tier": by_tier,
        "by_time": by_time,
        "undecided": undecided,
        "stale_deletes": stale,
    }
    return picked, counts


def _authorised(tables, approver, field, when):
    for scope in (field, "all"):
        for start, stop in tables["roles"].get((approver, scope), ()):
            if start <= when < stop:
                return True
    return False


def _vendor_key(tables, reference, width):
    known = tables.setdefault("vendor_key_memo", {})
    key = known.get((reference, width))
    if key is not None:
        return key
    letters = []
    digits = []
    tail = []
    for char in reference:
        if char in " -":
            continue
        mark = char.upper()
        if mark.isdigit():
            digits.append(mark)
        elif digits:
            tail.append(mark)
        else:
            letters.append(mark)
    key = "".join(letters) + "".join(digits).rjust(width, "0") + "".join(tail)
    known[(reference, width)] = key
    return key


def _identity(tables, reference, generation, effective, width, limit):
    key = _vendor_key(tables, reference, width)
    code = _window_value(tables["vendor"], key, effective)
    if code is None:
        return "", "ALIAS_UNKNOWN"
    seen = {code}
    hops = 0
    keys = tables["house_keys"]
    while code in keys:
        nxt = _window_value(tables["house"], code, effective)
        if nxt is None:
            return "", "ALIAS_CYCLE"
        hops += 1
        if hops > limit or nxt in seen:
            return "", "ALIAS_CYCLE"
        seen.add(nxt)
        code = nxt
    if (code, generation) not in tables["assets"]:
        return code, "ASSET_UNKNOWN"
    return code, ""


def _frames(text, nominal, drop):
    minutes_total = int(text[0:2]) * 60 + int(text[3:5])
    total = (minutes_total * 60 + int(text[6:8])) * nominal + int(text[9:11])
    if drop:
        total -= 2 * (minutes_total - minutes_total // 10)
    return total


def _event_rows(data_dir, scenario):
    rows = []
    for name in sorted(glob.glob(os.path.join(data_dir, "events_" + scenario + "_*.csv"))):
        rows.extend(_delimited(name, ","))
    return rows


def _ring_members(required):
    colour = {}
    ring = set()

    def visit(node, stack):
        colour[node] = 1
        stack.append(node)
        for nxt in sorted(required.get(node, ())):
            state = colour.get(nxt, 0)
            if state == 0:
                visit(nxt, stack)
            elif state == 1:
                ring.update(stack[stack.index(nxt) :])
        stack.pop()
        colour[node] = 2

    for node in sorted(required):
        if colour.get(node, 0) == 0:
            visit(node, [])
    return ring


def _too_deep(required, limit):
    """Chains running past the accepted depth stand as closed rings."""
    memo = {}

    def reach(node, seen):
        if node in memo:
            return memo[node]
        if node in seen:
            return limit + 1
        seen.add(node)
        best = 0
        for nxt in required.get(node, ()):  # one level per nesting hop
            best = max(best, 1 + reach(nxt, seen))
        seen.discard(node)
        memo[node] = best
        return best

    return {name for name in required if reach(name, set()) > limit}


def _dependency_order(required, poisoned):
    done = set()
    order = []
    waiting = sorted(required)
    while waiting:
        free = [name for name in waiting if not (required[name] - done - poisoned)]
        if not free:
            free = waiting
        pick = min(free)
        order.append(pick)
        done.add(pick)
        waiting.remove(pick)
    return order


def _resolve(data_dir, scenario):
    tables = _tables_for(data_dir)
    config = _settings(tables, scenario)
    cutoff = config["cutoff"]
    props = tables["properties"]
    hours = int(props.get("suppress.window.hours", "24"))
    width = int(props.get("alias.key.pad.width", "6"))
    limit = int(props.get("alias.max.hops", "4"))
    holds, clears = _exception_plan(tables, scenario, hours)
    picked, tie_counts = _corrections(tables, data_dir, scenario, cutoff)
    extras = {
        "input_events": 0,
        "host_sourced": 0,
        "host_counts": {},
        "log_pushed": 0,
        "at_cutoff": 0,
        "tape_used": 0,
        "tape_new": 0,
        "half_rounds": 0,
        "auth_scope": 0,
        "auth_by_approver": {},
        "auth_time": 0,
        "phase_shifted": 0,
        "phase_worst": "",
        "phase_worst_gap": 0,
        "nest_ring": 0,
        "nest_ring_low": "",
        "cases": tables["arbitration"]["cases"],
    }
    extras.update(tie_counts)
    rows = _event_rows(data_dir, scenario)
    extras["input_events"] = len(rows)
    ingest = tables["ingest"]
    overrides = tables["overrides"]
    prepared = {}
    for row in rows:
        uid = row[0]
        stamp = ingest.get(uid)
        if stamp is None:
            recorded = row[14]
        else:
            recorded = stamp[0]
            extras["host_sourced"] += 1
            extras["host_counts"][stamp[1]] = extras["host_counts"].get(stamp[1], 0) + 1
            if recorded > cutoff >= row[14]:
                extras["log_pushed"] += 1
        if recorded > cutoff:
            continue
        if recorded == cutoff:
            extras["at_cutoff"] += 1
        fields = list(row)
        blocked = ""
        slot = picked.get(uid)
        if slot is not None and slot[0] > int(row[20]):
            _revision, record, trouble = slot
            if trouble:
                blocked = trouble
            elif record["op"] == "delete":
                blocked = "WITHDRAWN"
            else:
                for name, value in record["fields"].items():
                    spot = CORRECTION_FIELD.get(name)
                    if spot is not None:
                        fields[spot] = str(value)
        if not blocked:
            by_field = {}
            for record in overrides.get(uid, ()):
                when = record["recorded_at"]
                if when > cutoff:
                    continue
                early = when <= recorded
                allowed = _authorised(tables, record["approver"], record["field"], when)
                if not allowed:
                    extras["auth_scope"] += 1
                    who = record["approver"]
                    extras["auth_by_approver"][who] = extras["auth_by_approver"].get(who, 0) + 1
                if early:
                    extras["auth_time"] += 1
                    continue
                if not allowed:
                    continue
                by_field.setdefault(record["field"], []).append(record)
            for name, group in by_field.items():
                spot = CORRECTION_FIELD.get(name)
                if spot is not None:
                    group.sort(key=lambda item: (item["recorded_at"], item["approver"]))
                    fields[spot] = str(group[-1]["value"])
        prepared.setdefault(row[1], []).append((fields, blocked))
    for group in prepared.values():
        group.sort(key=lambda item: (item[0][13], int(item[0][2]), item[0][0]))
    required = {}
    for timeline, group in prepared.items():
        needs = set()
        for fields, _blocked in group:
            if fields[10] == "nest":
                target = tables["nests"].get((scenario, fields[0]))
                if target is not None and target in prepared:
                    needs.add(target)
        required[timeline] = needs
    ring = _ring_members(required)
    poisoned = set(ring) | _too_deep(required, int(props.get("nest.max.depth", "6")))
    if ring:
        extras["nest_ring"] = len(ring)
        extras["nest_ring_low"] = min(ring)
        growing = True
        while growing:
            growing = False
            for timeline, needs in required.items():
                if timeline not in poisoned and needs & poisoned:
                    poisoned.add(timeline)
                    growing = True
    results = {}
    for timeline in _dependency_order(required, poisoned):
        results[timeline] = _walk(
            tables,
            config,
            scenario,
            timeline,
            prepared[timeline],
            results,
            holds.get(timeline, ()),
            list(clears.get(timeline, ())),
            timeline in poisoned,
            width,
            limit,
            extras,
        )
    timelines = [results[name] for name in sorted(results)]
    payload = {
        "scenario": scenario,
        "cutoff_utc": cutoff,
        "delivery_family": config["delivery_family"],
        "timelines": timelines,
        "totals": {
            "timelines": len(timelines),
            "events": sum(len(entry["events"]) for entry in timelines),
            "applied_events": sum(entry["applied_events"] for entry in timelines),
            "audited_events": sum(entry["audited_events"] for entry in timelines),
            "rejected_events": sum(entry["rejected_events"] for entry in timelines),
            "record_frames": sum(entry["record_frames"] for entry in timelines),
            "exit_phase_sum": sum(entry["exit_phase"] for entry in timelines),
        },
    }
    return payload, extras


def _walk(
    tables,
    config,
    scenario,
    timeline,
    group,
    results,
    spans,
    marks,
    dead,
    width,
    limit,
    extras,
):
    cursor = 0
    phase = 0
    shadow = 0
    closed = False
    events = []
    applied = audited = rejected = 0
    excluded = config["excluded"]
    cutover = config["tape_cutover"]
    delivery = config["delivery_family"]
    cadence = tables["cadence"]
    legacy = tables["tape_old"]
    fresh = tables["tape_new"]
    for fields, blocked in group:
        effective = fields[13]
        while marks and marks[0] <= effective:
            phase = 0
            marks.pop(0)
        code = ""
        generation = fields[4]
        event_class = fields[10]
        reason = ""
        audit = ""
        legality = None
        source_frames = 0
        phase_in = phase
        phase_out = phase
        record_in = cursor
        record_out = cursor
        if dead:
            reason = "NEST_CYCLE"
        elif config["ring"]:
            reason = "CFG_CYCLE"
        elif blocked:
            reason = blocked
        family_row = None
        if not reason:
            code, reason = _identity(tables, fields[3], generation, effective, width, limit)
        if not reason:
            family_row = _window_value(
                tables["families"], tables["assets"][(code, generation)], effective
            )
            if family_row is None:
                reason = "RATE_UNKNOWN"
        if not reason:
            legality = tables["legality"].get((event_class, fields[11], fields[12]))
            if legality is None:
                reason = "TRANSITION_UNKNOWN"
        target = None
        if not reason and event_class == "nest":
            target = tables["nests"].get((scenario, fields[0]))
            if target is None:
                reason = "NEST_MISSING"
        if not reason:
            for start, stop in spans:
                if start <= effective < stop:
                    audit = "DELIVERY_SUPPRESSED"
                    break
            if not audit and closed and event_class != "reinstate":
                audit = "TERMINAL_STATE"
            elif not audit and event_class in excluded:
                audit = "CLASS_EXCLUDED"
            elif not audit and legality == "audit":
                audit = "ILLEGAL_TRANSITION"
        if not reason and not audit:
            rate_family, nominal, drop = family_row
            in_tc = fields[5]
            out_tc = fields[6]
            ppm = _whole(fields[9])
            key = fields[19].strip()
            if key and effective < cutover:
                entry = fresh.get(key)
                from_fresh = entry is not None
                if entry is None:
                    entry = legacy.get(key)
                if entry is not None:
                    in_tc, out_tc, ppb = entry
                    ppm = ppb // 1000
                    extras["tape_used"] += 1
                    if from_fresh:
                        extras["tape_new"] += 1
            if target is not None:
                net = results.get(target, {}).get("record_frames", 0)
            else:
                span = (
                    _frames(out_tc, nominal, drop)
                    + _whole(fields[16])
                    - _frames(in_tc, nominal, drop)
                )
                if span <= 0:
                    reason = "SPAN_NONPOSITIVE"
                    net = 0
                elif _window_value(tables["handles"], (event_class, fields[21]), effective) == (
                    "excluded"
                ):
                    net = span - _whole(fields[7]) - _whole(fields[8])
                else:
                    net = span
            if not reason:
                if net <= 0:
                    reason = "HANDLE_OVERRUN"
                elif ppm <= 0:
                    reason = "RATE_INVALID"
                else:
                    pair = cadence.get((fields[21], rate_family, delivery))
                    if pair is None:
                        reason = "CADENCE_UNKNOWN"
                    else:
                        scaled = net * 1000000
                        adjusted = (scaled + ppm // 2) // ppm
                        if ppm % 2 == 0 and scaled % ppm == ppm // 2:
                            extras["half_rounds"] += 1
                        num, den = pair
                        source_frames = adjusted
                        record_in = cursor
                        record_out = cursor + (
                            ((phase + adjusted) * num) // den - (phase * num) // den
                        )
                        phase_out = (phase + adjusted) % den
                        flat = shadow + (adjusted * num) // den
                        if flat != record_out:
                            extras["phase_shifted"] += 1
                        shadow = flat
                        cursor = record_out
                        phase = phase_out
        if reason:
            outcome = "rejected"
            label = reason
            rejected += 1
            source_frames = 0
            record_in = record_out = cursor
            phase_in = phase_out = phase
        elif audit:
            outcome = "audited"
            label = audit
            audited += 1
            source_frames = 0
            record_in = record_out = cursor
            phase_in = phase_out = phase
        else:
            outcome = "applied"
            label = "OK"
            applied += 1
            closed = fields[12] == "withdrawn"
        events.append(
            {
                "event_uid": fields[0],
                "canonical_code": code,
                "generation": generation,
                "outcome": outcome,
                "reason_code": label,
                "source_frames": source_frames,
                "record_in_frames": record_in,
                "record_out_frames": record_out,
                "phase_in": phase_in,
                "phase_out": phase_out,
            }
        )
    gap = abs(cursor - shadow)
    if gap > extras["phase_worst_gap"]:
        extras["phase_worst_gap"] = gap
        extras["phase_worst"] = timeline
    if dead:
        cursor = 0
        phase = 0
    return {
        "timeline_id": timeline,
        "record_frames": cursor,
        "exit_phase": phase,
        "applied_events": applied,
        "audited_events": audited,
        "rejected_events": rejected,
        "events": events,
    }


def run_scenario(data_dir, scenario):
    """Resolve one scenario against the contract and return its record."""
    payload, _extras = _resolve(data_dir, scenario)
    return payload


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    data_dir = "/app/data"
    scenario = "visible"
    out = ""
    while argv:
        flag = argv.pop(0)
        if flag == "--data-dir":
            data_dir = argv.pop(0)
        elif flag == "--scenario":
            scenario = argv.pop(0)
        elif flag == "--out":
            out = argv.pop(0)
    text = json.dumps(run_scenario(data_dir, scenario), sort_keys=True, separators=(",", ":")) + "\n"
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    return 0
# ENGINE_END


HEADER = '#!/usr/bin/env python3\n"""Frame exact conform engine for the delivery scenarios."""\n'
TAIL = '\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'


def emit_engine(target):
    with open(os.path.abspath(__file__), "r", encoding="utf-8") as handle:
        source = handle.read()
    start = source.index("# ENGINE_BEGIN\n") + len("# ENGINE_BEGIN\n")
    stop = source.index("# ENGINE_END\n")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(HEADER + source[start:stop].rstrip("\n") + TAIL)


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def build(data_dir="/app/data", out_dir="/app/out"):
    import gc
    import statistics
    import time

    os.makedirs(out_dir, exist_ok=True)
    emit_engine(os.path.join(out_dir, "optimize.py"))
    sys.dont_write_bytecode = True
    sys.path.insert(0, data_dir)
    import reference_conform

    scenarios = {}
    extras = {}
    for name in SCENARIOS:
        payload, bits = _resolve(data_dir, name)
        scenarios[name] = payload
        extras[name] = bits
        _write(os.path.join(out_dir, "scenario_" + name + ".json"), payload)

    perf = {"module": "/app/out/optimize.py", "method": "relative repeated median", "scenarios": {}}
    totals = {"input_events": 0, "admitted_events": 0, "applied_events": 0, "record_frames": 0}
    for name in SCENARIOS:
        # Warm both table caches so the timed rounds compare resolution only.
        run_scenario(data_dir, name)
        reference_conform.legacy_run(data_dir, name)
        mine = []
        theirs = []
        collecting = gc.isenabled()
        gc.collect()
        gc.disable()
        try:
            for _ in range(11):
                mark = time.perf_counter_ns()
                run_scenario(data_dir, name)
                mine.append(time.perf_counter_ns() - mark)
                mark = time.perf_counter_ns()
                reference_conform.legacy_run(data_dir, name)
                theirs.append(time.perf_counter_ns() - mark)
        finally:
            if collecting:
                gc.enable()
        median_ns = int(statistics.median(mine))
        reference_ns = int(statistics.median(theirs))
        counts = scenarios[name]["totals"]
        perf["scenarios"][name] = {
            "input_events": extras[name]["input_events"],
            "admitted_events": counts["events"],
            "applied_events": counts["applied_events"],
            "record_frames": counts["record_frames"],
            "median_ns": median_ns,
            "reference_median_ns": reference_ns,
            "speedup": round(reference_ns / median_ns, 3),
        }
        totals["input_events"] += extras[name]["input_events"]
        totals["admitted_events"] += counts["events"]
        totals["applied_events"] += counts["applied_events"]
        totals["record_frames"] += counts["record_frames"]
    perf["totals"] = totals
    perf["ok"] = True
    _write(os.path.join(out_dir, "perf_report.json"), perf)

    visits = {}
    dominant = {}
    hot = {}
    carry = {}
    for name in SCENARIOS:
        counted = reference_conform.profile(data_dir, name)
        visits[name] = counted
        dominant[name] = max(sorted(counted), key=lambda stage: counted[stage])
        rows = scenarios[name]["timelines"]
        ranked = sorted(rows, key=lambda entry: (-entry["applied_events"], entry["timeline_id"]))
        hot[name] = [entry["timeline_id"] for entry in ranked[:5]]
        carry[name] = sum(1 for entry in rows if entry["exit_phase"] != 0)
    _write(
        os.path.join(out_dir, "bottleneck_analysis.json"),
        {
            "reference_module": "/app/data/reference_conform.py",
            "stages": list(reference_conform.STAGES),
            "stage_visits": visits,
            "dominant_stage": dominant,
            "hot_timelines": hot,
            "phase_carry_timelines": carry,
        },
    )

    tables = _tables_for(data_dir)
    remedy = tables["remedy"]
    kinds = tables["kinds"]
    actions = {}
    global_counts = {}
    quality = {}
    grand = {"rejected": 0, "audited": 0, "withdrawn": 0}
    for name in SCENARIOS:
        counts = {}
        rejects = {}
        audits = {}
        withdrawn = 0
        for entry in scenarios[name]["timelines"]:
            for item in entry["events"]:
                code = item["reason_code"]
                if code == "OK":
                    continue
                counts[code] = counts.get(code, 0) + 1
                global_counts[code] = global_counts.get(code, 0) + 1
                if kinds[code] == "reject":
                    rejects[code] = rejects.get(code, 0) + 1
                    grand["rejected"] += 1
                    if code == "WITHDRAWN":
                        withdrawn += 1
                else:
                    audits[code] = audits.get(code, 0) + 1
                    grand["audited"] += 1
        grand["withdrawn"] += withdrawn
        quality[name] = {"rejected": rejects, "audited": audits, "withdrawn": withdrawn}
        ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:3]
        actions[name] = [
            {"rank": spot + 1, "reason_code": code, "count": total, "remedy": remedy[code]}
            for spot, (code, total) in enumerate(ranked)
        ]
    top = sorted(global_counts.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]
    _write(
        os.path.join(out_dir, "recommendations.json"),
        {"scenario_actions": actions, "global_top_reason": top, "global_counts": global_counts},
    )
    _write(os.path.join(out_dir, "data_quality.json"), {"scenarios": quality, "totals": grand})
    return scenarios, extras


if __name__ == "__main__":
    build(
        sys.argv[1] if len(sys.argv) > 1 else "/app/data",
        sys.argv[2] if len(sys.argv) > 2 else "/app/out",
    )
