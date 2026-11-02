#!/usr/bin/env python3
"""Snapshot retention pruner.

Usage: python3 prune.py IN_DIR OUT_DIR

Reads snapshots.jsonl, policy.json, holds.csv and manifest.json from IN_DIR and
writes keep.json, prune.jsonl and summary.json into OUT_DIR.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ID_RE = re.compile(r"^s[0-9a-f]{12}$")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
STAMP_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:Z|([+-])(\d{2}):(\d{2}))$"
)
RECORD_KEYS = frozenset(("seq", "host", "vol", "id", "taken", "size", "parent", "state"))
CLASSES = ("hourly", "daily", "weekly", "monthly")
HOLD_HEADER = "id,until,reason"
REPORT_NAMES = ("keep.json", "prune.jsonl", "summary.json")

# Mode word bits; bit 1 is reserved and always clear.
BIT_RETRANSMIT_IGNORES_SEQ = 2
BIT_BUCKETS_OF_NEWEST = 4
BIT_MONTHLY_BY_QUARTER = 8
BIT_HOLD_COVERS_UNTIL = 16
BIT_BYTE_BUDGET = 32
BIT_PARENTS_SKIP_PARTIAL = 64
BIT_ANCHOR = 128

BUDGET_PROTECTED = frozenset(("hold", "anchor"))


class Options:
    """Behaviour switches taken from the intake's mode word."""

    __slots__ = (
        "retransmit_ignores_seq",
        "buckets_of_newest",
        "monthly_by_quarter",
        "hold_covers_until",
        "byte_budget",
        "parents_skip_partial",
        "anchor",
    )

    def __init__(self, mode=0):
        self.retransmit_ignores_seq = bool(mode & BIT_RETRANSMIT_IGNORES_SEQ)
        self.buckets_of_newest = bool(mode & BIT_BUCKETS_OF_NEWEST)
        self.monthly_by_quarter = bool(mode & BIT_MONTHLY_BY_QUARTER)
        self.hold_covers_until = bool(mode & BIT_HOLD_COVERS_UNTIL)
        self.byte_budget = bool(mode & BIT_BYTE_BUDGET)
        self.parents_skip_partial = bool(mode & BIT_PARENTS_SKIP_PARTIAL)
        self.anchor = bool(mode & BIT_ANCHOR)


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def parse_stamp(text):
    """Return the UTC datetime of a `taken` stamp, or None when malformed."""
    match = STAMP_RE.match(text)
    if match is None:
        return None
    year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
    sign, off_hours, off_minutes = match.group(7), match.group(8), match.group(9)
    if off_hours is None:
        offset = timedelta(0)
    else:
        off_hours, off_minutes = int(off_hours), int(off_minutes)
        if off_hours > 14 or off_minutes > 59:
            return None
        offset = timedelta(hours=off_hours, minutes=off_minutes)
        if sign == "-":
            offset = -offset
    try:
        local = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None
    return local.replace(tzinfo=timezone(offset)).astimezone(timezone.utc)


def validate_record(obj):
    """Return the record's UTC instant when it is legal, else None."""
    if not isinstance(obj, dict) or set(obj) != RECORD_KEYS:
        return None
    if not is_int(obj["seq"]) or obj["seq"] < 1:
        return None
    if not is_int(obj["size"]) or obj["size"] < 1:
        return None
    for field in ("host", "vol"):
        if not isinstance(obj[field], str) or not NAME_RE.match(obj[field]):
            return None
    if not isinstance(obj["id"], str) or not ID_RE.match(obj["id"]):
        return None
    parent = obj["parent"]
    if parent is not None:
        if not isinstance(parent, str) or not ID_RE.match(parent):
            return None
        if parent == obj["id"]:
            return None
    if obj["state"] not in ("ok", "partial"):
        return None
    if not isinstance(obj["taken"], str):
        return None
    return parse_stamp(obj["taken"])


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def canonical_without_seq(obj):
    return canonical({k: v for k, v in obj.items() if k != "seq"})


def split_lines(raw):
    lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    return lines


def screen(raw, options):
    """Screen raw snapshot bytes into accepted records plus screening counts."""
    accepted = []
    seen = set()
    malformed = 0
    retransmitted = 0
    for line in split_lines(raw):
        try:
            text = line.decode("utf-8")
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
        utc = validate_record(obj)
        if utc is None:
            malformed += 1
            continue
        if options.retransmit_ignores_seq:
            form = canonical_without_seq(obj)
        else:
            form = canonical(obj)
        if form in seen:
            retransmitted += 1
            continue
        seen.add(form)
        accepted.append((obj, utc))
    return accepted, malformed, retransmitted


def pick_copies(accepted):
    """Keep one record per id (the lowest `seq`); count republished ids."""
    groups = {}
    order = []
    for entry in accepted:
        snap_id = entry[0]["id"]
        if snap_id not in groups:
            groups[snap_id] = []
            order.append(snap_id)
        groups[snap_id].append(entry)
    chosen = {}
    republished = 0
    for snap_id in order:
        group = groups[snap_id]
        if len({canonical_without_seq(entry[0]) for entry in group}) > 1:
            republished += 1
        chosen[snap_id] = min(group, key=lambda entry: entry[0]["seq"])
    return chosen, republished


def build_series(chosen):
    """Group chosen records by series, each ordered by UTC instant then id."""
    series = {}
    for snap_id, (obj, utc) in chosen.items():
        name = "%s/%s" % (obj["host"], obj["vol"])
        series.setdefault(name, []).append(
            {
                "id": snap_id,
                "host": obj["host"],
                "taken": obj["taken"],
                "size": obj["size"],
                "parent": obj["parent"],
                "state": obj["state"],
                "utc": utc,
            }
        )
    for snaps in series.values():
        snaps.sort(key=lambda snap: (snap["utc"], snap["id"]))
    return series


def bucket_key(snap, cls, options):
    stamp = snap["utc"]
    if cls == "hourly":
        return (stamp.year, stamp.month, stamp.day, stamp.hour)
    if cls == "daily":
        return (stamp.year, stamp.month, stamp.day)
    if cls == "weekly":
        start = stamp.date() - timedelta(days=(stamp.weekday() + 1) % 7)
        return (start.year, start.month, start.day)
    if options.monthly_by_quarter:
        return (stamp.year, (stamp.month - 1) // 3)
    return (stamp.year, stamp.month)


def policy_for(host, policy):
    hosts = policy.get("hosts") or {}
    if host in hosts:
        return hosts[host]
    return policy.get("default") or {}


def class_bucket_keys(cls, eligible, buckets, count, options):
    """The bucket keys a class draws its representatives from."""
    if not options.buckets_of_newest:
        return sorted(buckets, reverse=True)[:count]
    keys = []
    for snap in eligible[-count:]:
        key = bucket_key(snap, cls, options)
        if key not in keys:
            keys.append(key)
    return keys


def apply_classes(snaps, entry, keep, options):
    """Keep the oldest eligible snapshot of every bucket a class draws on."""
    eligible = [snap for snap in snaps if snap["state"] == "ok"]
    if not eligible:
        return
    for cls in CLASSES:
        count = entry.get(cls)
        if not is_int(count) or count < 1:
            continue
        buckets = {}
        for snap in eligible:
            buckets.setdefault(bucket_key(snap, cls, options), []).append(snap)
        for key in class_bucket_keys(cls, eligible, buckets, count, options):
            keep.setdefault(buckets[key][0]["id"], cls)


def apply_anchor(snaps, keep, options):
    """Keep the series' oldest snapshot when nothing in the series descends from it."""
    if not options.anchor:
        return
    ids = {snap["id"] for snap in snaps}
    named = {snap["parent"] for snap in snaps if snap["parent"] in ids}
    oldest = snaps[0]
    if oldest["id"] not in named:
        keep.setdefault(oldest["id"], "anchor")


def hold_is_active(until, newest_date, options):
    if options.hold_covers_until:
        return until >= newest_date
    return until > newest_date


def apply_holds(snaps, holds, keep, options):
    """Give reason `hold` to every snapshot an active hold covers."""
    if not holds:
        return
    newest_date = snaps[-1]["utc"].date()
    for snap in snaps:
        until = holds.get(snap["id"])
        if until is not None and hold_is_active(until, newest_date, options):
            keep[snap["id"]] = "hold"


def apply_byte_budget(snaps, entry, keep, options):
    """Drop kept snapshots, oldest first, until `max_bytes` is respected."""
    limit = entry.get("max_bytes")
    if not options.byte_budget or not is_int(limit):
        return
    total = sum(snap["size"] for snap in snaps if snap["id"] in keep)
    for snap in snaps:
        if total <= limit:
            return
        reason = keep.get(snap["id"])
        if reason is not None and reason not in BUDGET_PROTECTED:
            total -= snap["size"]
            del keep[snap["id"]]


def apply_parents(snaps, keep, options):
    """Keep the parent chain of every kept snapshot."""
    by_id = {snap["id"]: snap for snap in snaps}
    for snap_id in list(keep):
        seen = {snap_id}
        current = by_id[snap_id]
        parent_id = current["parent"]
        while parent_id is not None and parent_id not in seen and parent_id in by_id:
            seen.add(parent_id)
            parent = by_id[parent_id]
            skip = options.parents_skip_partial and parent["state"] == "partial"
            if not skip:
                keep.setdefault(parent_id, "parent")
            current = parent
            parent_id = current["parent"]


def plan_series(snaps, policy, holds, options):
    entry = policy_for(snaps[0]["host"], policy)
    keep = {}
    apply_classes(snaps, entry, keep, options)
    apply_anchor(snaps, keep, options)
    apply_holds(snaps, holds, keep, options)
    apply_byte_budget(snaps, entry, keep, options)
    apply_parents(snaps, keep, options)
    return keep


def read_holds(text):
    """Return (id -> `until` date, number of valid rows)."""
    holds = {}
    valid = 0
    for index, line in enumerate(text.split("\n")):
        if line.strip() == "":
            continue
        if index == 0 and line.strip() == HOLD_HEADER:
            continue
        fields = line.split(",")
        if len(fields) != 3:
            continue
        snap_id, until = fields[0].strip(), fields[1].strip()
        if not ID_RE.match(snap_id):
            continue
        try:
            parsed = datetime.strptime(until, "%Y-%m-%d").date()
        except ValueError:
            continue
        valid += 1
        holds[snap_id] = parsed
    return holds, valid


def kept_lines(plan):
    return [
        "%s/%s\n" % (name, snap_id)
        for name, entries in plan.items()
        for snap_id, _reason in entries
    ]


def digest_of(chunks):
    sha = hashlib.sha256()
    for chunk in chunks:
        sha.update(chunk.encode("utf-8"))
    return sha.hexdigest()


def render_keep(plan):
    series = {
        name: [{"id": snap_id, "reason": reason} for snap_id, reason in entries]
        for name, entries in plan.items()
    }
    return json.dumps({"series": series}, sort_keys=True, indent=2) + "\n"


def render_prune(pruned):
    out = []
    for name in sorted(pruned):
        for snap in pruned[name]:
            out.append(
                json.dumps(
                    {"id": snap["id"], "series": name, "taken": snap["taken"]},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
    return "".join(out)


def render_summary(summary):
    return json.dumps(summary, sort_keys=True, indent=2) + "\n"


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def host_digests(plan):
    hosts = {}
    for name, entries in plan.items():
        host = name.split("/", 1)[0]
        hosts.setdefault(host, []).extend(
            "%s/%s\n" % (name, snap_id) for snap_id, _reason in entries
        )
    return {host: digest_of(sorted(lines)) for host, lines in hosts.items()}


def prune(in_dir):
    """Run the pruner over in_dir; return (reports, summary, host digests)."""
    raw = read_bytes(os.path.join(in_dir, "snapshots.jsonl"))
    policy = json.loads(read_bytes(os.path.join(in_dir, "policy.json")).decode("utf-8"))
    holds_text = read_bytes(os.path.join(in_dir, "holds.csv")).decode("utf-8")
    manifest = json.loads(
        read_bytes(os.path.join(in_dir, "manifest.json")).decode("utf-8")
    )
    options = Options(manifest["mode"])

    accepted, malformed, retransmitted = screen(raw, options)
    chosen, republished = pick_copies(accepted)
    series = build_series(chosen)
    holds, hold_rows = read_holds(holds_text)

    plan = {}
    pruned = {}
    for name in sorted(series):
        snaps = series[name]
        keep = plan_series(snaps, policy, holds, options)
        plan[name] = [(s["id"], keep[s["id"]]) for s in snaps if s["id"] in keep]
        pruned[name] = [snap for snap in snaps if snap["id"] not in keep]

    reasons = [reason for entries in plan.values() for _id, reason in entries]
    summary = {
        "held": reasons.count("hold"),
        "holds": hold_rows,
        "kept": len(reasons),
        "malformed": malformed,
        "parents": reasons.count("parent"),
        "partial": sum(
            1 for snaps in series.values() for snap in snaps if snap["state"] == "partial"
        ),
        "plan_digest": digest_of(sorted(kept_lines(plan))),
        "pruned": sum(len(v) for v in pruned.values()),
        "republished": republished,
        "retransmitted": retransmitted,
        "snapshots": len(chosen),
    }
    reports = {
        "keep.json": render_keep(plan),
        "prune.jsonl": render_prune(pruned),
        "summary.json": render_summary(summary),
    }
    return reports, summary, host_digests(plan)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: prune.py IN_DIR OUT_DIR\n")
        return 2
    in_dir, out_dir = argv[1], argv[2]
    reports, _summary, _hosts = prune(in_dir)
    os.makedirs(out_dir, exist_ok=True)
    for name in REPORT_NAMES:
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(reports[name].encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
