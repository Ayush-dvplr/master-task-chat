#!/usr/bin/env python3
"""Snapshot pruner.

Reads an intake folder (snapshots.jsonl, policy.json, holds.csv, manifest.json)
and writes keep.json, prune.jsonl and summary.json to an output folder.

Usage: python3 prune.py IN_DIR OUT_DIR
"""

import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HOST_VOL_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
ID_RE = re.compile(r"^s[0-9a-f]{12}$")
TAKEN_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(Z|[+-]\d{2}:\d{2})$")
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
RECORD_KEYS = frozenset(("seq", "host", "vol", "id", "taken", "size", "parent", "state"))
CLASSES = ("hourly", "daily", "weekly", "monthly")
CLASS_ORDER_DEFAULT = ("hourly", "daily", "weekly", "monthly")
CLASS_ORDER_ALT = ("weekly", "monthly", "daily", "hourly")

# Mode word bits in use (bit 1 is reserved and always clear).
BIT_HOLD_INCLUSIVE = 2
BIT_BUDGET = 4
BIT_ANCHOR = 8
BIT_HOLDS_FIRST = 16
BIT_CLASS_ORDER = 32
BIT_PARENT_OK_ONLY = 64
BIT_RETRANS_IGNORE_SEQ = 128


def is_int(value):
    """True for a real integer (booleans are not integers)."""
    return isinstance(value, int) and not isinstance(value, bool)


def calendar_date(year, month, day):
    """Return a date object, or None when the date does not exist."""
    try:
        return datetime(year, month, day).date()
    except ValueError:
        return None


def valid_record(obj):
    """True when a decoded JSON value obeys every snapshot record rule."""
    if not isinstance(obj, dict) or frozenset(obj) != RECORD_KEYS:
        return False
    if not is_int(obj["seq"]) or obj["seq"] < 1:
        return False
    for key in ("host", "vol"):
        value = obj[key]
        if not isinstance(value, str) or not HOST_VOL_RE.match(value):
            return False
    snapshot_id = obj["id"]
    if not isinstance(snapshot_id, str) or not ID_RE.match(snapshot_id):
        return False
    taken = obj["taken"]
    if not isinstance(taken, str):
        return False
    match = TAKEN_RE.match(taken)
    if match is None:
        return False
    year, month, day, hour, minute, second, offset = match.groups()
    if calendar_date(int(year), int(month), int(day)) is None:
        return False
    if int(hour) > 23 or int(minute) > 59 or int(second) > 59:
        return False
    if offset != "Z":
        if int(offset[1:3]) > 14 or int(offset[4:6]) > 59:
            return False
    if not is_int(obj["size"]) or obj["size"] < 1:
        return False
    parent = obj["parent"]
    if parent is not None:
        if not isinstance(parent, str) or not ID_RE.match(parent):
            return False
        if parent == snapshot_id:
            return False
    return obj["state"] in ("ok", "partial")


def parse_taken(taken):
    """Return (utc datetime, local date) for a well formed stamp."""
    match = TAKEN_RE.match(taken)
    year, month, day, hour, minute, second, offset = match.groups()
    local = datetime(int(year), int(month), int(day),
                     int(hour), int(minute), int(second))
    if offset == "Z":
        minutes = 0
    else:
        minutes = int(offset[1:3]) * 60 + int(offset[4:6])
        if offset[0] == "-":
            minutes = -minutes
    utc = local.replace(tzinfo=timezone.utc) - timedelta(minutes=minutes)
    return utc, local.date()


class Snapshot:
    """One accepted snapshot, with the clock readings the plan needs."""

    __slots__ = ("id", "host", "vol", "series", "taken", "utc", "utc_date",
                 "size", "parent", "state", "seq")

    def __init__(self, record):
        self.id = record["id"]
        self.host = record["host"]
        self.vol = record["vol"]
        self.series = self.host + "/" + self.vol
        self.taken = record["taken"]
        self.utc, _local_date = parse_taken(record["taken"])
        self.utc_date = self.utc.date()
        self.size = record["size"]
        self.parent = record["parent"]
        self.state = record["state"]
        self.seq = record["seq"]


def screen_lines(data, ignore_seq):
    """Screen raw bytes into (snapshots, malformed, retransmitted, republished).

    A retransmission repeats content already accepted; with ignore_seq set the
    comparison leaves seq out.  A republished id arrives on several accepted
    lines whose content differs beyond what the comparison leaves out, and the
    copy with the lowest seq is the one used.
    """
    malformed = 0
    retransmitted = 0
    accepted = []
    seen = set()
    for raw in data.split(b"\n"):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            malformed += 1
            continue
        if text.strip() == "":
            continue
        try:
            obj = json.loads(text)
        except ValueError:
            malformed += 1
            continue
        if not valid_record(obj):
            malformed += 1
            continue
        if ignore_seq:
            content = dict(obj)
            content.pop("seq")
        else:
            content = obj
        key = json.dumps(content, sort_keys=True, separators=(",", ":"))
        if key in seen:
            retransmitted += 1
            continue
        seen.add(key)
        accepted.append(Snapshot(obj))
    by_id = {}
    for snap in accepted:
        by_id.setdefault(snap.id, []).append(snap)
    republished = 0
    chosen = {}
    for snapshot_id, copies in by_id.items():
        if len(copies) > 1:
            republished += 1
            chosen[snapshot_id] = min(copies, key=lambda item: item.seq)
        else:
            chosen[snapshot_id] = copies[0]
    return chosen, malformed, retransmitted, republished


def read_holds(path):
    """Return the valid hold rows as a list of (id, until) pairs."""
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if len(row) != 3:
                continue
            hold_id, until = row[0], row[1]
            if not ID_RE.match(hold_id):
                continue
            match = DATE_RE.match(until)
            if match is None:
                continue
            if calendar_date(int(match.group(1)), int(match.group(2)),
                             int(match.group(3))) is None:
                continue
            rows.append((hold_id, until))
    return rows


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def mode_flags(mode):
    """Turn the mode word into the plan options it selects."""
    return {
        "hold_inclusive": bool(mode & BIT_HOLD_INCLUSIVE),
        "budget": bool(mode & BIT_BUDGET),
        "anchor": bool(mode & BIT_ANCHOR),
        "holds_first": bool(mode & BIT_HOLDS_FIRST),
        "class_order": CLASS_ORDER_ALT if mode & BIT_CLASS_ORDER else CLASS_ORDER_DEFAULT,
        "parent_ok_only": bool(mode & BIT_PARENT_OK_ONLY),
        "retrans_ignore_seq": bool(mode & BIT_RETRANS_IGNORE_SEQ),
    }


def bucket_key(snap, kind):
    """Bucket key for a snapshot; weeks run Sunday to Saturday, on UTC."""
    day = snap.utc_date
    if kind == "hourly":
        return (day.year, day.month, day.day, snap.utc.hour)
    if kind == "daily":
        return (day.year, day.month, day.day)
    if kind == "weekly":
        shift = (day.weekday() + 1) % 7
        return (day - timedelta(days=shift),)
    return (day.year, day.month)


def active_holds(hold_rows, ids_here, newest_date, inclusive):
    """Holds that still count for a series, compared with its newest date."""
    active = set()
    for hold_id, until in hold_rows:
        if hold_id not in ids_here:
            continue
        if (until >= newest_date) if inclusive else (until > newest_date):
            active.add(hold_id)
    return active


def plan_series(snaps, policy, hold_rows, flags):
    """Decide, per series, which snapshots are kept and why."""
    series = {}
    for snap in snaps.values():
        series.setdefault(snap.series, []).append(snap)
    for items in series.values():
        items.sort(key=lambda item: (item.utc, item.id))
    kept = {}
    for name in sorted(series):
        items = series[name]
        marks = kept.setdefault(name, {})
        entry = policy.get("hosts", {}).get(items[0].host, policy.get("default", {}))
        cap = entry.get("max_bytes") if flags["budget"] else None
        if not is_int(cap):
            cap = None
        used = 0

        def fits(size):
            return cap is None or used + size <= cap

        ids_here = frozenset(item.id for item in items)
        newest_date = max(item.utc_date for item in items).isoformat()
        active = active_holds(hold_rows, ids_here, newest_date,
                              flags["hold_inclusive"])
        if flags["holds_first"]:
            for item in items:
                if item.id in active:
                    marks[item.id] = "hold"
                    used += item.size
        if flags["anchor"]:
            oldest = items[0]
            if oldest.id not in marks and fits(oldest.size):
                marks[oldest.id] = "anchor"
                used += oldest.size
        pool = [item for item in items if item.state == "ok"]
        for kind in flags["class_order"]:
            count = entry.get(kind, 0)
            if not is_int(count) or count <= 0:
                continue
            buckets = {}
            for item in pool:
                buckets.setdefault(bucket_key(item, kind), []).append(item)
            for key in sorted(buckets, reverse=True)[:count]:
                rep = buckets[key][0]
                if rep.id in marks:
                    continue
                if not fits(rep.size):
                    continue
                marks[rep.id] = kind
                used += rep.size
        if not flags["holds_first"]:
            for item in items:
                if item.id in active:
                    marks[item.id] = "hold"
        by_id = {item.id: item for item in items}
        pending = list(marks)
        while pending:
            current = pending.pop()
            record = by_id.get(current)
            if record is None or record.parent is None:
                continue
            parent_id = record.parent
            if parent_id in by_id and parent_id not in marks:
                if flags["parent_ok_only"] and by_id[parent_id].state != "ok":
                    continue
                marks[parent_id] = "parent"
                pending.append(parent_id)
    return series, kept


def build_keep(series, kept):
    """keep.json as bytes: every series, kept snapshots in series order."""
    payload = {"series": {}}
    for name in sorted(series):
        payload["series"][name] = [
            {"id": item.id, "reason": kept[name][item.id]}
            for item in series[name] if item.id in kept.get(name, {})
        ]
    return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")


def build_prune(series, kept):
    """prune.jsonl as bytes: one compact line per pruned snapshot."""
    lines = []
    for name in sorted(series):
        for item in series[name]:
            if item.id not in kept.get(name, {}):
                lines.append(json.dumps(
                    {"id": item.id, "series": name, "taken": item.taken},
                    sort_keys=True, separators=(",", ":")))
    if not lines:
        return b""
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_summary(snaps, kept, malformed, retransmitted, republished,
                  hold_count, kept_lines):
    """summary.json as bytes."""
    kept_total = sum(len(marks) for marks in kept.values())
    held = 0
    parents = 0
    for marks in kept.values():
        for reason in marks.values():
            if reason == "hold":
                held += 1
            elif reason == "parent":
                parents += 1
    summary = {
        "held": held,
        "holds": hold_count,
        "kept": kept_total,
        "malformed": malformed,
        "parents": parents,
        "partial": sum(1 for snap in snaps.values() if snap.state == "partial"),
        "plan_digest": hashlib.sha256("".join(kept_lines).encode("utf-8")).hexdigest(),
        "pruned": len(snaps) - kept_total,
        "republished": republished,
        "retransmitted": retransmitted,
        "snapshots": len(snaps),
    }
    return (json.dumps(summary, sort_keys=True, indent=2) + "\n").encode("utf-8")


def kept_line_list(kept):
    """Every kept line <host>/<vol>/<id> plus a newline, sorted."""
    return sorted("%s/%s\n" % (name, snapshot_id)
                  for name, marks in kept.items() for snapshot_id in marks)


def run(in_dir, out_dir):
    """Produce the three reports for one intake folder."""
    with open(os.path.join(in_dir, "snapshots.jsonl"), "rb") as handle:
        data = handle.read()
    manifest = read_json(os.path.join(in_dir, "manifest.json"))
    policy = read_json(os.path.join(in_dir, "policy.json"))
    hold_rows = read_holds(os.path.join(in_dir, "holds.csv"))
    flags = mode_flags(manifest.get("mode", 0))
    snaps, malformed, retransmitted, republished = screen_lines(
        data, flags["retrans_ignore_seq"])
    series, kept = plan_series(snaps, policy, hold_rows, flags)
    keep_bytes = build_keep(series, kept)
    prune_bytes = build_prune(series, kept)
    kept_lines = kept_line_list(kept)
    summary_bytes = build_summary(snaps, kept, malformed, retransmitted,
                                  republished, len(hold_rows), kept_lines)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    for name, payload in (("keep.json", keep_bytes),
                          ("prune.jsonl", prune_bytes),
                          ("summary.json", summary_bytes)):
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(payload)
    return 0


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: prune.py IN_DIR OUT_DIR\n")
        return 2
    return run(argv[1], argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
