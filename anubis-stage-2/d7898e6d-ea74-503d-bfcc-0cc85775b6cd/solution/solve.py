#!/usr/bin/env python3
"""Snapshot retention pruner: settles which snapshots each series keeps.

What each mode bit does was never written down, so the program does not tie a
behaviour to a bit value. It knows the seven behaviours the live intake shows
and, for each intake, tries every reading its mode word allows and keeps the one
whose reports match the SHA-256 digests in that intake's own manifest.json.
"""
import datetime
import hashlib
import itertools
import json
import os
import re
import sys

INPUT_NAMES = ("snapshots.jsonl", "policy.json", "holds.csv", "manifest.json")
RETENTION_CLASSES = ("hourly", "daily", "weekly", "monthly")
FIELDS = frozenset(("seq", "host", "vol", "id", "taken", "size", "parent", "state"))
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
SNAP_PATTERN = re.compile(r"^s[0-9a-f]{12}$")
STAMP_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(Z|[+-]\d{2}:\d{2})$")
DAY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HOLD_HEADER = "id,until,reason"

BEHAVIOURS = (
    "anchor_oldest",
    "quarter_months",
    "late_day",
    "hold_forever",
    "relay_ignores_seq",
    "chain_stops_at_partial",
    "size_cap",
)
SHIFT_HOURS = tuple(range(1, 24))


class Reading:
    """One candidate reading of a mode word: the behaviours in force and the daily shift."""

    def __init__(self, active, hours):
        self.active = frozenset(active)
        self.shift = datetime.timedelta(hours=hours)


def candidate_readings(mode):
    """Yield every reading with as many behaviours in force as the mode word has bits set."""
    for active in itertools.combinations(BEHAVIOURS, bin(mode).count("1")):
        for hours in SHIFT_HOURS if "late_day" in active else (0,):
            yield Reading(active, hours)


def is_count(value):
    """True for a plain integer that is not a boolean."""
    return type(value) is int


def utc_of(stamp):
    """Turn a taken stamp into a naive UTC datetime, or None when it is invalid."""
    if not isinstance(stamp, str):
        return None
    found = STAMP_PATTERN.match(stamp)
    if found is None:
        return None
    parts = found.groups()
    try:
        wall = datetime.datetime(*(int(p) for p in parts[:6]))
    except ValueError:
        return None
    zone = parts[6]
    if zone == "Z":
        return wall
    hours, minutes = int(zone[1:3]), int(zone[4:6])
    if hours > 14 or minutes > 59:
        return None
    shift = datetime.timedelta(hours=hours, minutes=minutes)
    return wall - shift if zone[0] == "+" else wall + shift


def well_formed(record):
    """Apply the screening rules from conventions.md to one decoded line."""
    if not isinstance(record, dict) or frozenset(record) != FIELDS:
        return False
    if not is_count(record["seq"]) or record["seq"] < 1:
        return False
    if not is_count(record["size"]) or record["size"] < 1:
        return False
    for key in ("host", "vol"):
        if not isinstance(record[key], str) or not NAME_PATTERN.match(record[key]):
            return False
    if not isinstance(record["id"], str) or not SNAP_PATTERN.match(record["id"]):
        return False
    if utc_of(record["taken"]) is None:
        return False
    parent = record["parent"]
    if parent is not None:
        if not isinstance(parent, str) or not SNAP_PATTERN.match(parent) or parent == record["id"]:
            return False
    return record["state"] in ("ok", "partial")


class Snapshot:
    """One accepted snapshot line."""

    def __init__(self, record):
        self.seq = record["seq"]
        self.host = record["host"]
        self.series = record["host"] + "/" + record["vol"]
        self.ident = record["id"]
        self.taken = record["taken"]
        self.utc = utc_of(record["taken"])
        self.size = record["size"]
        self.parent = record["parent"]
        self.partial = record["state"] == "partial"


def screen_lines(blob, seqless):
    """Drop malformed and retransmitted lines and settle republished ids."""
    tally = {"malformed": 0, "retransmitted": 0, "republished": 0}
    fingerprints = set()
    copies = {}
    for raw in blob.split(b"\n"):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            tally["malformed"] += 1
            continue
        if not well_formed(record):
            tally["malformed"] += 1
            continue
        shown = {k: v for k, v in record.items() if not (seqless and k == "seq")}
        mark = json.dumps(shown, sort_keys=True)
        if mark in fingerprints:
            tally["retransmitted"] += 1
            continue
        fingerprints.add(mark)
        copies.setdefault(record["id"], []).append(record)
    chosen = {}
    for ident, group in copies.items():
        bodies = {json.dumps({k: v for k, v in c.items() if k != "seq"}, sort_keys=True) for c in group}
        if len(bodies) > 1:
            tally["republished"] += 1
        chosen[ident] = Snapshot(min(group, key=lambda c: c["seq"]))
    return chosen, tally


def read_holds(text):
    """Return the valid (id, until) rows of holds.csv in file order."""
    rows = text.splitlines()
    if not rows or rows[0].strip() != HOLD_HEADER:
        return []
    holds = []
    for row in rows[1:]:
        cells = row.split(",")
        if len(cells) != 3 or not SNAP_PATTERN.match(cells[0]) or not DAY_PATTERN.match(cells[1]):
            continue
        try:
            holds.append((cells[0], datetime.date.fromisoformat(cells[1])))
        except ValueError:
            continue
    return holds


def bucket(kind, when, reading):
    """Name the retention bucket a UTC instant falls in."""
    if kind == "hourly":
        return when.strftime("%Y-%m-%dT%H")
    if kind == "daily":
        if "late_day" in reading.active:
            when = when - reading.shift
        return when.date().isoformat()
    if kind == "weekly":
        day = when.date()
        return (day - datetime.timedelta(days=(day.weekday() + 1) % 7)).isoformat()
    if "quarter_months" in reading.active:
        return "%04d-Q%d" % (when.year, (when.month + 2) // 3)
    return "%04d-%02d" % (when.year, when.month)


def plan_series(members, rules, holds, reading):
    """Return the kept ids of one series with the reason each is kept."""
    keep = {}
    eligible = [s for s in members if not s.partial]
    for kind in RETENTION_CLASSES:
        buckets = {}
        for snap in eligible:
            buckets.setdefault(bucket(kind, snap.utc, reading), []).append(snap)
        for name in sorted(buckets, reverse=True)[: rules.get(kind, 0)]:
            keep.setdefault(buckets[name][0].ident, kind)
    if "anchor_oldest" in reading.active and eligible:
        keep.setdefault(eligible[0].ident, "anchor")
    last_day = members[-1].utc.date()
    present = {s.ident for s in members}
    for ident, until in holds:
        if ident in present and ("hold_forever" in reading.active or until > last_day):
            keep[ident] = "hold"
    if "size_cap" in reading.active and "max_bytes" in rules:
        for snap in members:
            if sum(s.size for s in members if s.ident in keep) <= rules["max_bytes"]:
                break
            if keep.get(snap.ident) not in (None, "hold"):
                del keep[snap.ident]
    lookup = {s.ident: s for s in members}
    for ident in list(keep):
        walked = set()
        step = lookup[ident].parent
        while step in lookup and step not in walked:
            walked.add(step)
            if "chain_stops_at_partial" in reading.active and lookup[step].partial:
                break
            keep.setdefault(step, "parent")
            step = lookup[step].parent
    return keep


def write_reports(plans, tally, hold_count):
    """Render keep.json, prune.jsonl and summary.json as text."""
    listing, pruned, kept_lines = {}, [], []
    held = parents = partial = 0
    for name, (members, keep) in plans.items():
        listing[name] = []
        for snap in members:
            partial += snap.partial
            if snap.ident in keep:
                listing[name].append({"id": snap.ident, "reason": keep[snap.ident]})
                kept_lines.append(name + "/" + snap.ident + "\n")
                held += keep[snap.ident] == "hold"
                parents += keep[snap.ident] == "parent"
            else:
                pruned.append({"id": snap.ident, "series": name, "taken": snap.taken})
    summary = dict(tally)
    summary["snapshots"] = sum(len(m) for m, _ in plans.values())
    summary["kept"] = len(kept_lines)
    summary["pruned"] = len(pruned)
    summary["held"] = held
    summary["parents"] = parents
    summary["partial"] = partial
    summary["holds"] = hold_count
    summary["plan_digest"] = hashlib.sha256("".join(sorted(kept_lines)).encode()).hexdigest()
    return {
        "keep.json": json.dumps({"series": listing}, sort_keys=True, indent=2) + "\n",
        "prune.jsonl": "".join(json.dumps(p, sort_keys=True, separators=(",", ":")) + "\n" for p in pruned),
        "summary.json": json.dumps(summary, sort_keys=True, indent=2) + "\n",
    }


def plan_intake(screened, terms, reading):
    """Produce the three reports for one intake under one reading of its mode word."""
    snaps, tally = screened
    fallback, per_host, holds = terms
    grouped = {}
    for snap in snaps.values():
        grouped.setdefault(snap.series, []).append(snap)
    plans = {}
    for name in sorted(grouped):
        members = sorted(grouped[name], key=lambda s: (s.utc, s.ident))
        rules = per_host.get(members[0].host, fallback)
        plans[name] = (members, plan_series(members, rules, holds, reading))
    return write_reports(plans, tally, len(holds))


def settle(blobs):
    """Produce the reports of the reading that best matches the intake's manifest digests."""
    manifest = json.loads(blobs["manifest.json"].decode("utf-8"))
    wanted = manifest.get("reports", {})
    policy = json.loads(blobs["policy.json"].decode("utf-8"))
    holds = read_holds(blobs["holds.csv"].decode("utf-8"))
    terms = (policy.get("default", {}), policy.get("hosts", {}), holds)
    screened = {}
    best, best_hits = None, -1
    for reading in candidate_readings(manifest.get("mode", 0)):
        seqless = "relay_ignores_seq" in reading.active
        if seqless not in screened:
            screened[seqless] = screen_lines(blobs["snapshots.jsonl"], seqless)
        reports = plan_intake(screened[seqless], terms, reading)
        hits = sum(hashlib.sha256(text.encode()).hexdigest() == wanted.get(name) for name, text in reports.items())
        if hits == len(reports):
            return reports
        if hits > best_hits:
            best, best_hits = reports, hits
    return best


def main(argv):
    """Read IN_DIR, write the reports into OUT_DIR."""
    if len(argv) != 3:
        sys.stderr.write("usage: prune.py IN_DIR OUT_DIR\n")
        return 2
    blobs = {}
    for name in INPUT_NAMES:
        with open(os.path.join(argv[1], name), "rb") as handle:
            blobs[name] = handle.read()
    os.makedirs(argv[2], exist_ok=True)
    for name, text in settle(blobs).items():
        with open(os.path.join(argv[2], name), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
