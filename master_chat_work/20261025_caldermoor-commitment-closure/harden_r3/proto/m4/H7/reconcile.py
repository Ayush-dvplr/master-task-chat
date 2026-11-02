#!/usr/bin/env python3
"""Caldermoor commitment closure.

Reads one extract directory and writes the whole closure into another.

    python3 reconcile.py DATA_DIR OUT_DIR

Standard library only. Two runs over one extract produce identical bytes.
"""

from __future__ import annotations

import collections
import json
import os
import shutil
import sys
import tempfile
import unicodedata

# ------------------------------------------------------------------ calendar

MONTH_STARTS_COMMON = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
MONTH_STARTS_LEAP = (0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335)
EPOCH_YEAR = 2032
MINUTES_PER_DAY = 1440
DAY_SHIFT = 240

WINDOW_TEXT = ("2032-03-01T00:00Z", "2032-12-01T00:00Z")


def leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def year_length(year):
    return 366 if leap(year) else 365


def month_starts(year):
    return MONTH_STARTS_LEAP if leap(year) else MONTH_STARTS_COMMON


def day_number(year, month, day):
    """Days from 2032-01-01 to the given civil date."""
    total = 0
    step = 1 if year >= EPOCH_YEAR else -1
    cursor = EPOCH_YEAR
    while cursor != year:
        if step > 0:
            total += year_length(cursor)
            cursor += 1
        else:
            cursor -= 1
            total -= year_length(cursor)
    return total + month_starts(year)[month - 1] + day - 1


def civil_date(days):
    year = EPOCH_YEAR
    while days < 0:
        year -= 1
        days += year_length(year)
    while days >= year_length(year):
        days -= year_length(year)
        year += 1
    starts = month_starts(year)
    month = 12
    for i in range(11):
        if days < starts[i + 1]:
            month = i + 1
            break
    return year, month, days - starts[month - 1] + 1


def read_stamp(raw):
    """An instant in minutes from the epoch, or None when the shape is wrong."""
    text = (raw or "").strip()
    if len(text) != 17:
        return None
    if (text[4], text[7], text[10], text[13], text[16]) != ("-", "-", "T", ":", "Z"):
        return None
    parts = (text[0:4], text[5:7], text[8:10], text[11:13], text[14:16])
    if not all(part.isdigit() for part in parts):
        return None
    year, month, day, hour, minute = (int(part) for part in parts)
    if not 1 <= month <= 12:
        return None
    if not 1 <= day <= 31:
        return None
    if hour > 23 or minute > 59:
        return None
    return day_number(year, month, day) * MINUTES_PER_DAY + hour * 60 + minute


def show_stamp(value):
    days, rest = divmod(value, MINUTES_PER_DAY)
    year, month, day = civil_date(days)
    return "%04d-%02d-%02dT%02d:%02dZ" % (year, month, day, rest // 60, rest % 60)


def show_date(days):
    year, month, day = civil_date(days)
    return "%04d-%02d-%02d" % (year, month, day)


WINDOW_OPEN = read_stamp(WINDOW_TEXT[0])
WINDOW_SHUT = read_stamp(WINDOW_TEXT[1])


def settlement_day(instant):
    return (instant - DAY_SHIFT) // MINUTES_PER_DAY


# ------------------------------------------------------------- vocabularies

RANK_OF = {
    "legacy": 0,
    "import": 1,
    "relay": 1,
    "mirror": 2,
    "partner": 3,
    "bridge": 4,
    "desk": 5,
    "vault": 6,
}
JOURNAL = "desk"
# The sweep class walks its spool backwards, so it reverses inside its rank for
# state rows only and keeps the ordinary direction where commitments compete.
SWEEP = "bridge"

STATE_SET = ("OPEN", "SETTLED", "DEFERRED", "WITHDRAWN")
MOVES = frozenset(
    (
        ("OPEN", "SETTLED"),
        ("OPEN", "DEFERRED"),
        ("OPEN", "WITHDRAWN"),
        ("DEFERRED", "OPEN"),
        ("DEFERRED", "WITHDRAWN"),
    )
)

REASONS = (
    "AMBIGUOUS_IDENTITY",
    "FEED_RETIRED",
    "ILLEGAL_TRANSITION",
    "MALFORMED_ROW",
    "NONPOSITIVE_EFFORT",
    "OUT_OF_WINDOW",
    "UNKNOWN_COMMITMENT",
    "UNKNOWN_PRINCIPAL",
    "UNKNOWN_PROJECT",
)

CLASS_SET = (
    "ACTIONABLE",
    "BLOCKED",
    "DEFERRED",
    "SETTLED",
    "UNRESOLVABLE",
    "WITHDRAWN",
)
OPEN_SET = ("ACTIONABLE", "BLOCKED", "DEFERRED")

FACTOR = {"minutes": 1, "hours": 60, "halfdays": 240}
HOURLY_SUFFIX = (".fixed", ".rec")
FLOOR, CEILING, SHARE_FLOOR = 15, 480, 15
ESCALATION_DEBT = 4
WAIVER_ALLOWANCE = 4
RESERVE_BLOCKED, RESERVE_WAIVED = 30, 15
ESCALATION_MONTH = "2032-11"

DROPPED = "__dropped__"
STRIPPED = ".-_'"


def fold(raw):
    """The comparison fold the identity register defines, in its six steps."""
    text = unicodedata.normalize("NFC", raw or "").strip().casefold()
    kept, gap = [], False
    for char in text:
        if char in STRIPPED:
            continue
        if char.isspace():
            gap = gap or bool(kept)
            continue
        if gap:
            kept.append(" ")
            gap = False
        kept.append(char)
    return "".join(kept).strip()


# ------------------------------------------------------------------ readers

WIDTHS_ASSERTION = (
    ("assertion_id", 12),
    ("commitment_key", 12),
    ("obligor", 40),
    ("obligee", 40),
    ("project_ref", 10),
    ("due_at", 18),
    ("effort", 8),
    ("cadence_ref", 10),
    ("observed_at", 18),
)
WIDTHS_STATE = (
    ("state_id", 12),
    ("commitment_key", 12),
    ("to_state", 12),
    ("observed_at", 18),
)


def split_lines(blob):
    body = blob.split("\n")
    while body and body[-1] == "":
        body.pop()
    return body


def from_separated(blob, mark):
    body = split_lines(blob)
    if not body:
        return []
    columns = body[0].split(mark)
    harvest = []
    for line in body[1:]:
        if line == "":
            continue
        cells = line.split(mark)
        harvest.append(
            {DROPPED: line} if len(cells) != len(columns) else dict(zip(columns, cells))
        )
    return harvest


def from_json_lines(blob):
    harvest = []
    for line in blob.split("\n"):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            item = None
        if isinstance(item, dict):
            harvest.append(
                {key: ("" if val is None else str(val)) for key, val in item.items()}
            )
        else:
            harvest.append({DROPPED: line})
    return harvest


def from_blocks(blob):
    harvest = []
    for chunk in blob.split("\n\n"):
        body = chunk.strip("\n")
        if not body.strip():
            continue
        item, spoiled = {}, False
        for line in body.split("\n"):
            if ": " in line:
                name, _, value = line.partition(": ")
            elif line.endswith(":"):
                name, value = line[:-1], ""
            else:
                spoiled = True
                break
            item[name.strip()] = value
        harvest.append({DROPPED: body} if spoiled else item)
    return harvest


def from_pairs(blob):
    harvest = []
    for line in blob.split("\n"):
        if not line.strip():
            continue
        item, spoiled = {}, False
        for piece in line.split(";"):
            if "=" not in piece:
                spoiled = True
                break
            name, _, value = piece.partition("=")
            item[name] = value
        harvest.append({DROPPED: line} if spoiled else item)
    return harvest


ENTITY_BACK = (("&quot;", '"'), ("&gt;", ">"), ("&lt;", "<"), ("&amp;", "&"))


def from_markup(blob):
    harvest = []
    for line in blob.split("\n"):
        trimmed = line.strip()
        if not trimmed.startswith("<") or not trimmed.endswith("/>"):
            continue
        inner = trimmed[1:-2].strip()
        cut = inner.find(" ")
        if cut < 0:
            continue
        inner, item, spoiled, at = inner[cut + 1 :], {}, False, 0
        while at < len(inner):
            mark = inner.find('="', at)
            if mark < 0:
                break
            name = inner[at:mark].strip()
            close = inner.find('"', mark + 2)
            if close < 0:
                spoiled = True
                break
            value = inner[mark + 2 : close]
            for token, char in ENTITY_BACK:
                value = value.replace(token, char)
            item[name] = value
            at = close + 1
            while at < len(inner) and inner[at] == " ":
                at += 1
        harvest.append({DROPPED: trimmed} if spoiled else item)
    return harvest


def from_columns(blob, widths):
    span = sum(size for _name, size in widths)
    harvest = []
    for line in blob.split("\n"):
        if not line.strip():
            continue
        if len(line) > span:
            harvest.append({DROPPED: line})
            continue
        filled, item, at = line.ljust(span), {}, 0
        for name, size in widths:
            item[name] = filled[at : at + size].strip()
            at += size
        harvest.append(item)
    return harvest


def load(path, widths=WIDTHS_ASSERTION):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        blob = handle.read()
    suffix = os.path.splitext(path)[1]
    if suffix == ".csv":
        return from_separated(blob, ",")
    if suffix == ".tsv":
        return from_separated(blob, "\t")
    if suffix == ".psv":
        return from_separated(blob, "|")
    if suffix == ".jsonl":
        return from_json_lines(blob)
    if suffix == ".kv":
        return from_blocks(blob)
    if suffix == ".rec":
        return from_pairs(blob)
    if suffix == ".xml":
        return from_markup(blob)
    if suffix == ".fixed":
        return from_columns(blob, widths)
    return []


def whole_number(raw):
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def feed_class(filename):
    for token in filename.split(".")[0].split("_"):
        if token in RANK_OF:
            return token
    return "reference"


def order_key(source, instant, marker, kind="commitment"):
    """Where a competing row sits in the charter order."""
    reversed_here = source == JOURNAL or (kind == "state" and source == SWEEP)
    stamp = -instant if reversed_here else instant
    return (RANK_OF.get(source, -1), stamp, marker)


def bounded(minutes):
    if minutes <= 0:
        return 0
    return FLOOR if minutes < FLOOR else (CEILING if minutes > CEILING else minutes)


def apportion(demand, envelope):
    """Largest remainder, a remainder tie settled by the lower key."""
    if envelope <= 0 or not demand:
        return dict.fromkeys(demand, 0)
    weight = sum(demand.values())
    if weight <= 0:
        return dict.fromkeys(demand, 0)
    whole, part = {}, {}
    for key, value in demand.items():
        product = value * envelope
        whole[key] = product // weight
        part[key] = product - whole[key] * weight
    spare = envelope - sum(whole.values())
    for key in sorted(demand, key=lambda k: (-part[k], k))[:spare]:
        whole[key] += 1
    return whole


# ------------------------------------------------------------- name service


class NameService:
    """Scope bounded resolution of a surface at one instant."""

    def __init__(self, assertions, canonical):
        self.arcs = collections.defaultdict(list)
        for item in assertions:
            self.arcs[fold(item["surface"])].append(item)
        for bucket in self.arcs.values():
            bucket.sort(key=lambda a: (a["scope_start"], a["target"]))
        self.canonical = canonical
        self.memo = {}

    def look(self, surface, instant):
        """Return (handle, outcome, hops)."""
        start = fold(surface)
        cached = self.memo.get((start, instant))
        if cached is not None:
            return cached
        answer = self._walk(start, instant)
        self.memo[(start, instant)] = answer
        return answer

    def _walk(self, start, instant):
        if not start:
            return (None, "UNKNOWN_PRINCIPAL", 0)
        if start in self.canonical:
            return (self.canonical[start], "", 0)
        landed = {}
        level = [(start,)]
        while level:
            following = {}
            for trail in level:
                for arc in self.arcs.get(trail[-1], ()):
                    if not arc["scope_start"] <= instant < arc["scope_end"]:
                        continue
                    ahead = fold(arc["target"])
                    if ahead in trail:
                        continue
                    if ahead in self.canonical:
                        landed.setdefault(self.canonical[ahead], len(trail))
                    else:
                        following.setdefault(trail + (ahead,), None)
            level = list(following)
        if len(landed) == 1:
            handle, hops = next(iter(landed.items()))
            return (handle, "", hops)
        if landed:
            return (None, "AMBIGUOUS_IDENTITY", 0)
        return (None, "UNKNOWN_PRINCIPAL", 0)


# ------------------------------------------------------------------ closure


class Closure:
    """The whole pipeline, holding its state on the instance."""

    def __init__(self, source):
        self.source = source
        self.rejects = []
        self.ingested = 0
        self.files = sorted(os.listdir(source))

    # -- helpers ---------------------------------------------------------
    def named(self, prefix, widths=WIDTHS_ASSERTION):
        for name in self.files:
            if name.startswith(prefix):
                yield name, load(os.path.join(self.source, name), widths)

    def refuse(self, filename, position, kind, marker, key, reason):
        self.rejects.append(
            {
                "feed_file": filename,
                "row_index": position,
                "record_kind": kind,
                "record_id": marker,
                "commitment_key": key,
                "reason_code": reason,
            }
        )

    # -- reference tables ------------------------------------------------
    def read_reference(self):
        latest = {}
        for name, rows in self.named("feed_manifest"):
            for row in rows:
                if DROPPED in row:
                    continue
                mark = whole_number(row.get("revision")) or 0
                target = row.get("feed_file", "")
                if target not in latest or mark > latest[target][0]:
                    latest[target] = (mark, read_stamp(row.get("retired_at", "")))
        self.retired = {
            name: stamp for name, (_m, stamp) in latest.items() if stamp is not None
        }

        shelf = collections.defaultdict(list)
        for name, rows in self.named("project_registry"):
            for row in rows:
                if DROPPED in row:
                    continue
                code = row.get("project_code", "")
                when = read_stamp(row.get("revised_at", ""))
                base = whole_number(row.get("default_effort"))
                if code and when is not None and base is not None:
                    shelf[code].append((when, base, row.get("parent_code", "")))
        for bucket in shelf.values():
            bucket.sort()
        self.shelf = shelf
        self.parent = {code: bucket[-1][2] for code, bucket in shelf.items()}
        self.root = {}
        for code in shelf:
            seen, cursor = set(), code
            while True:
                above = self.parent.get(cursor, "")
                if not above or above in seen or above not in shelf:
                    break
                seen.add(cursor)
                cursor = above
            self.root[code] = cursor

        self.renames = []
        for name, rows in self.named("project_events"):
            for row in rows:
                if DROPPED in row or row.get("event_type") != "RENAME":
                    continue
                when = read_stamp(row.get("effective_at", ""))
                if when is not None:
                    self.renames.append(
                        (when, row.get("project_code", ""), row.get("payload", ""))
                    )
        self.renames.sort()

        register, tally = {}, {}
        for name, rows in self.named("roster_"):
            for row in rows:
                if DROPPED in row:
                    continue
                who, handle = row.get("actor_id", ""), row.get("canonical_handle", "")
                if who and handle:
                    register[fold(handle)] = (handle, who)
                    tally.setdefault(who, {})
                    tally[who][handle] = tally[who].get(handle, 0) + 1
        self.handle_of = {key: pair[0] for key, pair in register.items()}
        self.actor_of = {key: pair[1] for key, pair in register.items()}
        self.spellings = {
            who: sorted(seen.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]
            for who, seen in tally.items()
        }

        arcs, seen = [], set()
        for name, rows in self.named("aliases_"):
            for row in rows:
                if DROPPED in row:
                    continue
                begin = read_stamp(row.get("scope_start", ""))
                finish = read_stamp(row.get("scope_end", ""))
                if begin is None or finish is None:
                    continue
                token = (
                    fold(row.get("surface", "")),
                    fold(row.get("target", "")),
                    begin,
                    finish,
                )
                if token in seen:
                    continue
                seen.add(token)
                arcs.append(
                    {
                        "surface": row.get("surface", ""),
                        "target": row.get("target", ""),
                        "scope_start": begin,
                        "scope_end": finish,
                    }
                )
        self.arcs = arcs
        self.names = NameService(arcs, self.handle_of)

        cadence = {}
        for name, rows in self.named("cadence_register"):
            for row in rows:
                if DROPPED in row:
                    continue
                marker = row.get("cadence_id", "")
                mark = whole_number(row.get("revision"))
                span = whole_number(row.get("period_days"))
                anchor = read_stamp(row.get("anchor_at", ""))
                if not marker or mark is None or span is None or anchor is None:
                    continue
                if marker not in cadence or mark > cadence[marker]["revision"]:
                    cadence[marker] = {
                        "revision": mark,
                        "period_days": span,
                        "anchor_at": anchor,
                        "obligor": row.get("obligor", ""),
                        "project_ref": row.get("project_ref", ""),
                    }
        self.cadence = cadence

        excused = collections.defaultdict(set)
        for name, rows in self.named("waivers_"):
            for row in rows:
                if DROPPED in row:
                    continue
                marker = row.get("cadence_id", "")
                slot = whole_number(row.get("period_index"))
                if marker and slot is not None:
                    excused[marker].add(slot)
        self.excused = excused

        self.registered, self.overridden = {}, {}
        for name, rows in self.named("attention_budget"):
            for row in rows:
                if DROPPED in row:
                    continue
                amount = whole_number(row.get("monthly_minutes"))
                if amount is not None:
                    self.registered[
                        (row.get("actor_id", ""), row.get("year_month", ""))
                    ] = amount
        for name, rows in self.named("budget_overrides"):
            for row in rows:
                if DROPPED in row:
                    continue
                amount = whole_number(row.get("monthly_minutes"))
                if amount is not None:
                    self.overridden[
                        (row.get("actor_id", ""), row.get("year_month", ""))
                    ] = amount

    def project_at(self, reference, instant):
        code, guard = (reference or "").strip(), set()
        moved = True
        while moved:
            moved = False
            for when, was, becomes in self.renames:
                if when > instant:
                    break
                if was == code and code not in guard:
                    guard.add(code)
                    code, moved = becomes, True
                    break
        return code if code in self.shelf else None

    def baseline(self, code, instant):
        bucket = self.shelf.get(code)
        if not bucket:
            return None
        chosen = bucket[0][1]
        for when, base, _above in bucket:
            if when <= instant:
                chosen = base
        return chosen

    # -- stage one -------------------------------------------------------
    def assess(self, row, hourly, cutoff):
        """Ask the reason codes of protocol section 6 in order; the first that
        holds is the answer. Returns (reason, facts) and reason is "" when the
        row is accepted. Later tests only run once every earlier one is false,
        so each may rely on the facts the earlier ones established."""
        facts = {}

        def malformed():
            if DROPPED in row:
                return True
            facts["seen"] = read_stamp(row.get("observed_at", ""))
            facts["due"] = read_stamp(row.get("due_at", ""))
            facts["effort"] = (row.get("effort", "") or "").strip()
            if not row.get("assertion_id") or not row.get("commitment_key"):
                return True
            if facts["seen"] is None or facts["due"] is None:
                return True
            if facts["effort"] in ("", "null"):
                return False
            facts["count"] = whole_number(facts["effort"])
            facts["unit"] = (
                "hours" if hourly else (row.get("effort_unit", "") or "").strip()
            )
            return facts["count"] is None or (
                facts["count"] > 0 and facts["unit"] not in FACTOR
            )

        def obligor_is(outcome):
            def test():
                if "who" not in facts:
                    facts["who"] = self.names.look(row.get("obligor", ""), facts["seen"])
                return facts["who"][1] == outcome

            return test

        def no_project():
            facts["code"] = self.project_at(row.get("project_ref", ""), facts["seen"])
            return facts["code"] is None

        def nonpositive():
            if facts["effort"] == "":
                facts["origin"] = "DEFAULTED"
                facts["minutes"] = self.baseline(facts["code"], facts["seen"])
                return facts["minutes"] is None
            if facts["effort"] == "null":
                facts["origin"], facts["minutes"] = "DECLARED_ZERO", 0
                return False
            if facts["count"] <= 0:
                return True
            facts["origin"] = "STATED"
            facts["minutes"] = facts["count"] * FACTOR[facts["unit"]]
            return False

        table = (
            ("MALFORMED_ROW", malformed),
            ("FEED_RETIRED", lambda: cutoff is not None and facts["seen"] >= cutoff),
            ("OUT_OF_WINDOW", lambda: not WINDOW_OPEN <= facts["due"] < WINDOW_SHUT),
            ("UNKNOWN_PRINCIPAL", obligor_is("UNKNOWN_PRINCIPAL")),
            ("AMBIGUOUS_IDENTITY", obligor_is("AMBIGUOUS_IDENTITY")),
            ("UNKNOWN_PROJECT", no_project),
            ("NONPOSITIVE_EFFORT", nonpositive),
        )
        for reason, holds in table:
            if holds():
                return reason, facts
        return "", facts

    def read_assertions(self):
        self.accepted = []
        for name, rows in self.named("commitments_"):
            source = feed_class(name)
            hourly = os.path.splitext(name)[1] in HOURLY_SUFFIX
            cutoff = self.retired.get(name)
            for position, row in enumerate(rows):
                self.ingested += 1
                reason, facts = self.assess(row, hourly, cutoff)
                marker = "" if DROPPED in row else row.get("assertion_id", "")
                key = "" if DROPPED in row else row.get("commitment_key", "")
                if reason:
                    self.refuse(name, position, "commitment", marker, key, reason)
                    continue
                handle, _outcome, hops = facts["who"]
                # The obligee resolves at the instant the commitment falls
                # due, which is not the instant the row was recorded.
                other, other_outcome, _hops = self.names.look(
                    row.get("obligee", ""), facts["due"]
                )
                self.accepted.append(
                    {
                        "assertion_id": marker,
                        "commitment_key": key,
                        "obligor_actor": self.actor_of[fold(handle)],
                        "obligor_surface": row.get("obligor", ""),
                        "obligor_hops": hops,
                        "obligee_actor": (self.actor_of[fold(other)] if other else ""),
                        "obligee_status": (
                            "AMBIGUOUS"
                            if other_outcome == "AMBIGUOUS_IDENTITY"
                            else ("RESOLVED" if other else "UNKNOWN")
                        ),
                        "project_code": facts["code"],
                        "project_root": self.root.get(facts["code"], facts["code"]),
                        "due_at": show_stamp(facts["due"]),
                        "commitment_day": show_date(settlement_day(facts["due"])),
                        "effort_minutes": bounded(facts["minutes"]),
                        "effort_origin": facts["origin"],
                        "cadence_ref": row.get("cadence_ref", "") or "",
                        "observed_at": show_stamp(facts["seen"]),
                        "source_class": source,
                        "feed_file": name,
                    }
                )
        self.accepted.sort(key=lambda r: r["assertion_id"])

    # -- stage two -------------------------------------------------------
    def pick_winners(self):
        self.family = collections.defaultdict(list)
        for row in self.accepted:
            self.family[row["commitment_key"]].append(row)
        self.winner, self.contest = {}, []
        for key in self.family:
            rows = self.family[key]
            best = max(
                rows,
                key=lambda r: order_key(
                    r["source_class"], read_stamp(r["observed_at"]), r["assertion_id"]
                ),
            )
            self.winner[key] = best
            self.contest.append(
                {
                    "commitment_key": key,
                    "winning_assertion": best["assertion_id"],
                    "winning_class": best["source_class"],
                    "contender_count": len(rows),
                    "distinct_classes": len({r["source_class"] for r in rows}),
                }
            )
        self.contest.sort(key=lambda r: r["commitment_key"])

    def walk_states(self):
        gathered = []
        self.state_rows = 0
        for name, rows in self.named("states_", WIDTHS_STATE):
            source = feed_class(name)
            cutoff = self.retired.get(name)
            for position, row in enumerate(rows):
                self.ingested += 1
                self.state_rows += 1
                if DROPPED in row:
                    self.refuse(name, position, "state", "", "", "MALFORMED_ROW")
                    continue
                marker = row.get("state_id", "")
                key = row.get("commitment_key", "")
                seen_at = read_stamp(row.get("observed_at", ""))
                target = (row.get("to_state", "") or "").strip()
                # Protocol section 6 fixes the order and a row carries the
                # first code that applies, so every malformed-row condition is
                # tested before retirement and before the window.
                if (
                    not marker
                    or not key
                    or seen_at is None
                    or target not in STATE_SET
                ):
                    self.refuse(name, position, "state", marker, key, "MALFORMED_ROW")
                    continue
                if cutoff is not None and seen_at >= cutoff:
                    self.refuse(name, position, "state", marker, key, "FEED_RETIRED")
                    continue
                if not WINDOW_OPEN <= seen_at < WINDOW_SHUT:
                    self.refuse(name, position, "state", marker, key, "OUT_OF_WINDOW")
                    continue
                if key not in self.winner:
                    self.refuse(
                        name, position, "state", marker, key, "UNKNOWN_COMMITMENT"
                    )
                    continue
                gathered.append((key, marker, target, seen_at, source, name, position))
                self.state_marks[key].append(marker)
        self.applied_states = len(gathered)

        grouped = collections.defaultdict(list)
        for entry in gathered:
            grouped[entry[0]].append(entry)

        self.state_of, self.state_trace, self.refused_moves = {}, [], 0
        for key in self.winner:
            held, used, governing = "OPEN", 0, ""
            sequence = sorted(
                grouped.get(key, ()),
                key=lambda e: order_key(e[4], e[3], e[1], kind="state"),
            )
            for _k, marker, target, _at, source, name, position in sequence:
                if (held, target) in MOVES:
                    held, used, governing = target, used + 1, source
                else:
                    self.refused_moves += 1
                    self.refuse(
                        name, position, "state", marker, key, "ILLEGAL_TRANSITION"
                    )
            self.state_of[key] = held
            self.state_trace.append(
                {
                    "commitment_key": key,
                    "resolved_state": held,
                    "assertions_seen": len(sequence),
                    "assertions_applied": used,
                    "governing_class": governing,
                }
            )
        self.state_trace.sort(key=lambda r: r["commitment_key"])

    def sift_edges(self):
        self.live, self.dropped = [], []
        for name, rows in self.named("edges_"):
            cutoff = self.retired.get(name)
            for position, row in enumerate(rows):
                self.ingested += 1
                if DROPPED in row:
                    self.refuse(name, position, "edge", "", "", "MALFORMED_ROW")
                    continue
                marker = row.get("edge_id", "")
                waiting = row.get("dependent_key", "")
                upon = row.get("blocker_key", "")
                claimed = read_stamp(row.get("asserted_at", ""))
                if not marker or not waiting or claimed is None:
                    self.refuse(
                        name, position, "edge", marker, waiting, "MALFORMED_ROW"
                    )
                    continue
                if cutoff is not None and claimed >= cutoff:
                    self.refuse(name, position, "edge", marker, waiting, "FEED_RETIRED")
                    continue
                if not WINDOW_OPEN <= claimed < WINDOW_SHUT:
                    self.refuse(
                        name, position, "edge", marker, waiting, "OUT_OF_WINDOW"
                    )
                    continue
                shell = {
                    "edge_id": marker,
                    "dependent_key": waiting,
                    "blocker_key": upon,
                    "asserted_at": show_stamp(claimed),
                }
                if waiting == upon:
                    self.dropped.append(dict(shell, drop_reason="EDGE_SELF"))
                    continue
                if waiting not in self.winner or upon not in self.winner:
                    self.dropped.append(dict(shell, drop_reason="EDGE_DANGLING"))
                    continue
                near, _o1, _h1 = self.names.look(
                    self.winner[waiting]["obligor_surface"], claimed
                )
                far, _o2, _h2 = self.names.look(
                    self.winner[upon]["obligor_surface"], claimed
                )
                if near is None or far is None:
                    self.dropped.append(dict(shell, drop_reason="EDGE_OUT_OF_SCOPE"))
                    continue
                self.live.append(
                    dict(
                        shell,
                        dependent_actor=self.actor_of[fold(near)],
                        blocker_actor=self.actor_of[fold(far)],
                    )
                )
        self.live.sort(
            key=lambda e: (e["dependent_key"], e["blocker_key"], e["edge_id"])
        )
        self.dropped.sort(key=lambda e: (e["drop_reason"], e["edge_id"]))

    def take_closure(self):
        holding = ("OPEN", "DEFERRED")
        self.forward = collections.defaultdict(set)
        for edge in self.live:
            if self.state_of.get(edge["blocker_key"]) in holding:
                self.forward[edge["dependent_key"]].add(edge["blocker_key"])

        # Kosaraju: a cycle is a strongly connected component above one node.
        backward = collections.defaultdict(set)
        for tail, heads in self.forward.items():
            for head in heads:
                backward[head].add(tail)
        order, seen = [], set()
        for start in sorted(self.forward):
            if start in seen:
                continue
            stack = [(start, iter(sorted(self.forward.get(start, ()))))]
            seen.add(start)
            while stack:
                node, walker = stack[-1]
                stepped = False
                for nxt in walker:
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append((nxt, iter(sorted(self.forward.get(nxt, ())))))
                        stepped = True
                        break
                if not stepped:
                    order.append(stack.pop()[0])
        placed, self.circular = set(), set()
        for node in reversed(order):
            if node in placed:
                continue
            group, queue = [], collections.deque([node])
            placed.add(node)
            while queue:
                here = queue.popleft()
                group.append(here)
                for back in sorted(backward.get(here, ())):
                    if back not in placed and back in seen:
                        placed.add(back)
                        queue.append(back)
            if len(group) > 1:
                self.circular.update(group)

        self.reach_rows, self.blocked = [], []
        for node in sorted(self.forward):
            if node in self.circular:
                continue
            distance, queue = (
                {},
                collections.deque(
                    (head, 1) for head in sorted(self.forward.get(node, ()))
                ),
            )
            while queue:
                here, hops = queue.popleft()
                if here in distance and distance[here] <= hops:
                    continue
                distance[here] = hops
                for onward in sorted(self.forward.get(here, ())):
                    if onward not in distance:
                        queue.append((onward, hops + 1))
            if not distance:
                continue
            ends = sorted(k for k in distance if not self.forward.get(k))
            for head in sorted(distance):
                self.reach_rows.append(
                    {
                        "dependent_key": node,
                        "blocker_key": head,
                        "hop_distance": distance[head],
                        "blocker_state": self.state_of.get(head, "OPEN"),
                        "terminal": "yes" if not self.forward.get(head) else "no",
                    }
                )
            self.blocked.append(
                {
                    "commitment_key": node,
                    "reachable_blockers": len(distance),
                    "frontier_count": len(ends),
                    "chain_depth": max(distance.values()),
                    "frontier_head": ends[0] if ends else "",
                }
            )
        self.reach_rows.sort(key=lambda r: (r["dependent_key"], r["blocker_key"]))
        self.blocked.sort(key=lambda r: r["commitment_key"])
        self.blocked_keys = {r["commitment_key"] for r in self.blocked}
        self.wait = {}
        for node in sorted(self.blocked_keys):
            self.wait_of(node)

    def wait_of(self, node):
        """Wait (glossary): zero off the blocked set, else one more than the greatest blocker wait."""
        if node not in self.blocked_keys:
            return 0
        if node not in self.wait:
            pending = [node]
            while pending:
                top = pending[-1]
                ahead = [b for b in self.forward.get(top, ())
                         if b in self.blocked_keys and b not in self.wait]
                if ahead:
                    pending.extend(sorted(ahead))
                    continue
                pending.pop()
                self.wait[top] = 1 + max(
                    (self.wait.get(b, 0) for b in self.forward.get(top, ())), default=0)
        return self.wait[node]

    # -- stage three -----------------------------------------------------
    def classify(self):
        self.ledger, self.undecided = [], []
        for key in sorted(self.winner):
            best, held = self.winner[key], self.state_of[key]
            note = ""
            if held == "SETTLED":
                band = "SETTLED"
            elif held == "WITHDRAWN":
                band = "WITHDRAWN"
            elif key in self.circular:
                band, note = "UNRESOLVABLE", "CIRCULAR_DEPENDENCY"
            elif best["obligee_status"] == "AMBIGUOUS":
                band, note = "UNRESOLVABLE", "AMBIGUOUS_COUNTERPARTY"
            elif key in self.blocked_keys:
                band = "BLOCKED"
            elif held == "DEFERRED":
                band = "DEFERRED"
            else:
                band = "ACTIONABLE"
            self.ledger.append(
                {
                    "commitment_key": key,
                    "obligor_actor": best["obligor_actor"],
                    "obligee_actor": best["obligee_actor"],
                    "project_code": best["project_code"],
                    "project_root": best["project_root"],
                    "commitment_day": best["commitment_day"],
                    "due_at": best["due_at"],
                    "effort_minutes": best["effort_minutes"],
                    "effort_origin": best["effort_origin"],
                    "resolved_state": held,
                    "commitment_class": band,
                    "cadence_ref": best["cadence_ref"],
                    "source_class": best["source_class"],
                    "winning_assertion": best["assertion_id"],
                }
            )
            if note:
                self.undecided.append(
                    {
                        "commitment_key": key,
                        "reason_code": note,
                        "obligor_actor": best["obligor_actor"],
                        "commitment_day": best["commitment_day"],
                    }
                )
        self.ledger.sort(
            key=lambda r: (
                r["commitment_day"],
                r["obligor_actor"],
                -r["effort_minutes"],
                r["commitment_key"],
            )
        )
        self.undecided.sort(key=lambda r: (r["reason_code"], r["commitment_key"]))
        self.ties = sum(
            1
            for a, b in zip(self.ledger, self.ledger[1:])
            if a["commitment_day"] == b["commitment_day"]
            and a["obligor_actor"] == b["obligor_actor"]
            and a["effort_minutes"] != b["effort_minutes"]
        )

    def count_cadence(self):
        discharged = collections.defaultdict(list)
        for row in self.ledger:
            marker = row["cadence_ref"]
            if marker and row["commitment_class"] == "SETTLED":
                discharged[marker].append(read_stamp(row["due_at"]))
        # A cadence obligor is a surface, resolved at the cadence anchor. One
        # that stands for nobody there is owned by nobody.
        self.owner = {}
        for marker in sorted(self.cadence):
            plan = self.cadence[marker]
            handle, _outcome, _hops = self.names.look(
                plan["obligor"], plan["anchor_at"]
            )
            who = self.actor_of.get(fold(handle)) if handle is not None else None
            if who:
                self.owner[marker] = who
        # Every waiver in an elapsed period of an owned cadence draws on its
        # principal's allowance, by period start and then cadence id.
        queue = collections.defaultdict(list)
        for marker, who in self.owner.items():
            plan = self.cadence[marker]
            width = plan["period_days"] * MINUTES_PER_DAY
            for slot in self.excused.get(marker, ()):
                opens = plan["anchor_at"] + slot * width
                if slot >= 0 and opens < WINDOW_SHUT:
                    queue[who].append((opens, marker, slot))
        spent, self.drawn = set(), {}
        for who, drawn in queue.items():
            drawn.sort()
            spent.update((marker, slot) for _o, marker, slot in drawn[WAIVER_ALLOWANCE:])
            self.drawn[who] = (
                min(len(drawn), WAIVER_ALLOWANCE),
                max(0, len(drawn) - WAIVER_ALLOWANCE),
            )
        self.cadence_rows, self.waiver_rows = [], []
        self.suppressing = self.inert = self.lapsed = 0
        for marker in sorted(self.cadence):
            plan = self.cadence[marker]
            width = plan["period_days"] * MINUTES_PER_DAY
            owed = run = peak = 0
            elapsed = met = excused_here = 0
            slot = 0
            while True:
                opens = plan["anchor_at"] + slot * width
                if opens >= WINDOW_SHUT:
                    break
                shuts = min(opens + width, WINDOW_SHUT)
                elapsed += 1
                hit = any(opens <= when < shuts for when in discharged.get(marker, ()))
                spared = slot in self.excused.get(marker, ())
                if spared and (marker, slot) in spent:
                    spared = False
                    self.lapsed += 1
                    self.waiver_rows.append(
                        {
                            "cadence_id": marker,
                            "period_index": slot,
                            "effect": "LAPSED",
                            "period_start": show_stamp(opens),
                        }
                    )
                if hit:
                    run = 0
                    met += 1
                    if spared:
                        self.inert += 1
                        self.waiver_rows.append(
                            {
                                "cadence_id": marker,
                                "period_index": slot,
                                "effect": "INERT",
                                "period_start": show_stamp(opens),
                            }
                        )
                elif spared:
                    excused_here += 1
                    self.suppressing += 1
                    self.waiver_rows.append(
                        {
                            "cadence_id": marker,
                            "period_index": slot,
                            "effect": "SUPPRESSED",
                            "period_start": show_stamp(opens),
                        }
                    )
                else:
                    owed += 1
                    run += 1
                    peak = max(peak, run)
                slot += 1
            self.cadence_rows.append(
                {
                    "cadence_id": marker,
                    "period_days": plan["period_days"],
                    "periods_elapsed": elapsed,
                    "periods_discharged": met,
                    "periods_waived": excused_here,
                    "debt": owed,
                    "max_streak": peak,
                }
            )
        self.cadence_rows.sort(key=lambda r: r["cadence_id"])
        self.waiver_rows.sort(key=lambda r: (r["cadence_id"], r["period_index"]))

    def spread_envelopes(self):
        pool = collections.defaultdict(list)
        for row in self.ledger:
            if row["commitment_class"] in OPEN_SET and row["effort_minutes"]:
                pool[(row["commitment_day"][:7], row["obligor_actor"])].append(row)
        row_of = {r["commitment_key"]: r for r in self.ledger}
        held = collections.Counter()
        for b in self.blocked:
            row = row_of[b["commitment_key"]]
            held[(row["commitment_day"][:7], row["obligor_actor"])] += self.wait[b["commitment_key"]]
        waived = collections.Counter()
        for row in self.cadence_rows:
            if row["cadence_id"] in self.owner:
                waived[self.owner[row["cadence_id"]]] += row["periods_waived"]
        self.shares, self.months, self.starved = [], [], 0
        for month, who in sorted(pool):
            items = sorted(pool[(month, who)], key=lambda r: r["commitment_key"])
            if (who, month) in self.overridden:
                envelope, origin = self.overridden[(who, month)], "OVERRIDE"
            elif (who, month) in self.registered:
                envelope, origin = self.registered[(who, month)], "REGISTERED"
            else:
                envelope, origin = 0, "ABSENT"
            reserve = RESERVE_BLOCKED * held[(month, who)] + RESERVE_WAIVED * waived[who]
            usable = max(0, envelope - reserve)
            demand = {r["commitment_key"]: r["effort_minutes"] for r in items}
            asked = sum(demand.values())
            if asked <= usable:
                given = dict(demand)
            else:
                first = apportion(demand, usable)
                keeping = {k: demand[k] for k, v in first.items() if v >= SHARE_FLOOR}
                losing = [k for k, v in first.items() if v < SHARE_FLOOR]
                self.starved += len(losing)
                if keeping:
                    given = (apportion(keeping, usable)
                             if sum(keeping.values()) > usable else dict(keeping))
                    for k in losing:
                        given[k] = 0
                else:
                    given = dict.fromkeys(demand, 0)
            for row in items:
                self.shares.append(
                    {
                        "year_month": month,
                        "obligor_actor": who,
                        "commitment_key": row["commitment_key"],
                        "demand_minutes": row["effort_minutes"],
                        "allocated_minutes": given.get(row["commitment_key"], 0),
                    }
                )
            self.months.append(
                {
                    "year_month": month,
                    "obligor_actor": who,
                    "budget_source": origin,
                    "budget_minutes": envelope,
                    "reserve_minutes": reserve,
                    "demand_minutes": asked,
                    "allocated_minutes": sum(given.values()),
                    "open_count": len(items),
                }
            )
        self.shares.sort(
            key=lambda r: (r["year_month"], r["obligor_actor"], r["commitment_key"])
        )
        self.months.sort(key=lambda r: (r["year_month"], r["obligor_actor"]))

    def raise_escalations(self):
        self.owed_by = collections.defaultdict(int)
        for row in self.cadence_rows:
            if row["cadence_id"] in self.owner:
                self.owed_by[self.owner[row["cadence_id"]]] += row["debt"]
        depth_of = {r["commitment_key"]: r["chain_depth"] for r in self.blocked}
        share_of = {r["commitment_key"]: r["allocated_minutes"] for r in self.shares}
        self.escalated = []
        for row in self.ledger:
            if row["commitment_class"] not in ("ACTIONABLE", "BLOCKED"):
                continue
            given = share_of.get(row["commitment_key"], 0)
            if given >= row["effort_minutes"]:
                continue
            owed = self.owed_by.get(row["obligor_actor"], 0)
            if owed < ESCALATION_DEBT:
                continue
            deep = depth_of.get(row["commitment_key"], 0)
            by_depth = deep >= 2
            by_month = row["commitment_day"][:7] == ESCALATION_MONTH
            if not (by_depth or by_month):
                continue
            self.escalated.append(
                {
                    "commitment_key": row["commitment_key"],
                    "obligor_actor": row["obligor_actor"],
                    "commitment_class": row["commitment_class"],
                    "effort_minutes": row["effort_minutes"],
                    "allocated_minutes": given,
                    "shortfall_minutes": row["effort_minutes"] - given,
                    "principal_debt": owed,
                    "chain_depth": deep,
                    "trigger": (
                        "BOTH"
                        if by_depth and by_month
                        else ("DEPTH" if by_depth else "MONTH")
                    ),
                }
            )
        self.escalated.sort(
            key=lambda r: (-r["shortfall_minutes"], r["commitment_key"])
        )

    def build_rollups(self):
        self.by_actor, self.by_project = {}, {}
        given_by = collections.defaultdict(int)
        root_of = {r["commitment_key"]: r["project_root"] for r in self.ledger}
        for row in self.shares:
            given_by[row["obligor_actor"]] += row["allocated_minutes"]
            given_by[("root", root_of[row["commitment_key"]])] += row["allocated_minutes"]
        for row in self.ledger:
            for store, label in (
                (self.by_actor, row["obligor_actor"]),
                (self.by_project, row["project_root"]),
            ):
                slot = store.setdefault(label, dict.fromkeys(CLASS_SET, 0))
                slot[row["commitment_class"]] += 1
                slot["commitment_count"] = slot.get("commitment_count", 0) + 1
                slot.setdefault("open_effort_minutes", 0)
                if row["commitment_class"] in OPEN_SET:
                    slot["open_effort_minutes"] += row["effort_minutes"]
        for label, slot in self.by_actor.items():
            slot["allocated_minutes"] = given_by.get(label, 0)
        for label, slot in self.by_project.items():
            slot["allocated_minutes"] = given_by.get(("root", label), 0)
        self.open_effort = sum(
            r["effort_minutes"]
            for r in self.ledger
            if r["commitment_class"] in OPEN_SET
        )

        self.trail = []
        for key in sorted(self.family):
            rows = sorted(self.family[key], key=lambda r: r["assertion_id"])
            self.trail.append(
                {
                    "commitment_key": key,
                    "winning_assertion": self.winner[key]["assertion_id"],
                    "contributing_assertions": [r["assertion_id"] for r in rows],
                    "source_files": sorted({r["feed_file"] for r in rows}),
                    "state_assertions": sorted(self.state_marks.get(key, [])),
                }
            )

        surfaces = {}
        for row in self.accepted:
            token = fold(row["obligor_surface"])
            slot = surfaces.setdefault(token, {"who": set(), "n": 0, "h": 0})
            slot["who"].add(row["obligor_actor"])
            slot["n"] += 1
            slot["h"] = max(slot["h"], row["obligor_hops"])
        self.surface_rows = [
            {
                "surface_folded": token,
                "distinct_actors": sorted(slot["who"]),
                "assertion_count": slot["n"],
                "max_hops": slot["h"],
            }
            for token, slot in sorted(surfaces.items())
        ]
        self.split = sum(1 for slot in surfaces.values() if len(slot["who"]) > 1)
        self.deep_hops = sum(1 for r in self.accepted if r["obligor_hops"] >= 2)

        codes = collections.Counter(r["project_code"] for r in self.accepted)
        self.lineage = [
            {
                "project_code": code,
                "project_root": self.root.get(code, code),
                "assertion_count": count,
            }
            for code, count in sorted(codes.items())
        ]

    def run(self):
        self.read_reference()
        self.read_assertions()
        self.pick_winners()
        self.state_marks = collections.defaultdict(list)
        self.walk_states()
        self.sift_edges()
        self.take_closure()
        self.classify()
        self.count_cadence()
        self.spread_envelopes()
        self.raise_escalations()
        self.build_rollups()
        self.rejects.sort(
            key=lambda r: (
                r["reason_code"],
                r["feed_file"],
                r["row_index"],
                r["record_id"],
            )
        )
        return self


# ------------------------------------------------------------------ emitter


def put(path, body):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(body)


def as_lines(rows):
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    )


def as_table(columns, rows, mark=","):
    body = [mark.join(columns)]
    body.extend(mark.join(str(row[name]) for name in columns) for row in rows)
    return "\n".join(body) + "\n"


def as_object(payload):
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


QUEUE_COLUMNS = (
    "commitment_key",
    "obligor_actor",
    "commitment_day",
    "effort_minutes",
    "project_root",
    "allocated_minutes",
)


def with_shares(work, rows):
    given = {r["commitment_key"]: r["allocated_minutes"] for r in work.shares}
    return [dict(r, allocated_minutes=given.get(r["commitment_key"], 0)) for r in rows]


def lineage_rows(work):
    given = collections.Counter()
    for row in with_shares(work, work.ledger):
        given[row["project_code"]] += row["allocated_minutes"]
    return [dict(r, allocated_minutes=given[r["project_code"]]) for r in work.lineage]


def live_rows(work):
    held = {r["commitment_key"] for r in work.blocked}
    return [
        dict(r, dependent_blocked="yes" if r["dependent_key"] in held else "no")
        for r in work.live
    ]


def queue_rows(work, label):
    return with_shares(
        work, [r for r in work.ledger if r["commitment_class"] == label]
    )


NORMALIZED_COLUMNS = (
    "assertion_id",
    "commitment_key",
    "obligor_actor",
    "obligee_actor",
    "obligee_status",
    "project_code",
    "project_root",
    "due_at",
    "commitment_day",
    "effort_minutes",
    "effort_origin",
    "cadence_ref",
    "observed_at",
    "source_class",
)


def emit(work, target):
    def at(name):
        return os.path.join(target, name)

    emit_intake(work, at)
    emit_views(work, at)
    emit_load(work, at)
    emit_figures(work, at)


def emit_intake(work, at):
    put(
        at("normalized_assertions.jsonl"),
        as_lines(
            [{name: row[name] for name in NORMALIZED_COLUMNS} for row in work.accepted]
        ),
    )
    put(
        at("rejects.csv"),
        as_table(
            (
                "feed_file",
                "row_index",
                "record_kind",
                "record_id",
                "commitment_key",
                "reason_code",
            ),
            work.rejects,
        ),
    )
    put(at("alias_resolution.jsonl"), as_lines(work.surface_rows))
    put(
        at("actor_roster.csv"),
        as_table(
            (
                "actor_id",
                "canonical_handle",
                "commitment_count",
                "open_effort_minutes",
                "waivers_granted",
                "waivers_lapsed",
            ),
            [
                {
                    "actor_id": who,
                    "canonical_handle": work.spellings[who],
                    "commitment_count": work.by_actor.get(who, {}).get(
                        "commitment_count", 0
                    ),
                    "open_effort_minutes": work.by_actor.get(who, {}).get(
                        "open_effort_minutes", 0
                    ),
                    "waivers_granted": work.drawn.get(who, (0, 0))[0],
                    "waivers_lapsed": work.drawn.get(who, (0, 0))[1],
                }
                for who in sorted(work.spellings)
            ],
        ),
    )
    put(
        at("project_lineage.csv"),
        as_table(
            ("project_code", "project_root", "assertion_count", "allocated_minutes"),
            lineage_rows(work),
        ),
    )
    put(
        at("assertion_contests.csv"),
        as_table(
            (
                "commitment_key",
                "winning_assertion",
                "winning_class",
                "contender_count",
                "distinct_classes",
            ),
            work.contest,
        ),
    )
    put(at("commitment_ledger.jsonl"), as_lines(with_shares(work, work.ledger)))
    put(
        at("state_resolution.csv"),
        as_table(
            (
                "commitment_key",
                "resolved_state",
                "assertions_seen",
                "assertions_applied",
                "governing_class",
            ),
            work.state_trace,
        ),
    )


def emit_views(work, at):
    put(
        at("live_edges.csv"),
        as_table(
            (
                "edge_id",
                "dependent_key",
                "blocker_key",
                "asserted_at",
                "dependent_actor",
                "blocker_actor",
                "dependent_blocked",
            ),
            live_rows(work),
        ),
    )
    put(
        at("dropped_edges.csv"),
        as_table(
            ("edge_id", "dependent_key", "blocker_key", "asserted_at", "drop_reason"),
            work.dropped,
        ),
    )
    put(at("blocking_closure.jsonl"), as_lines(work.reach_rows))
    put(
        at("blocked_commitments.csv"),
        as_table(
            (
                "commitment_key",
                "reachable_blockers",
                "frontier_count",
                "chain_depth",
                "frontier_head",
                "allocated_minutes",
            ),
            with_shares(work, work.blocked),
        ),
    )
    put(
        at("actionable_queue.tsv"),
        as_table(
            QUEUE_COLUMNS,
            queue_rows(work, "ACTIONABLE"),
            "\t",
        ),
    )
    put(
        at("deferred_queue.psv"),
        as_table(
            QUEUE_COLUMNS,
            queue_rows(work, "DEFERRED"),
            "|",
        ),
    )
    put(
        at("withdrawn_register.csv"),
        as_table(
            (
                "commitment_key",
                "obligor_actor",
                "commitment_day",
                "effort_minutes",
                "source_class",
            ),
            [r for r in work.ledger if r["commitment_class"] == "WITHDRAWN"],
        ),
    )
    put(at("unresolvable.jsonl"), as_lines(work.undecided))
    put(
        at("cadence_debt.csv"),
        as_table(
            (
                "cadence_id",
                "period_days",
                "periods_elapsed",
                "periods_discharged",
                "periods_waived",
                "debt",
                "max_streak",
            ),
            work.cadence_rows,
        ),
    )
    put(at("waiver_trace.jsonl"), as_lines(work.waiver_rows))


def emit_load(work, at):
    put(
        at("attention_allocation.csv"),
        as_table(
            (
                "year_month",
                "obligor_actor",
                "commitment_key",
                "demand_minutes",
                "allocated_minutes",
            ),
            work.shares,
        ),
    )
    put(
        at("month_load_index.csv"),
        as_table(
            (
                "year_month",
                "obligor_actor",
                "budget_source",
                "budget_minutes",
                "reserve_minutes",
                "demand_minutes",
                "allocated_minutes",
                "open_count",
            ),
            work.months,
        ),
    )
    put(
        at("escalation_queue.csv"),
        as_table(
            (
                "commitment_key",
                "obligor_actor",
                "commitment_class",
                "effort_minutes",
                "allocated_minutes",
                "shortfall_minutes",
                "principal_debt",
                "chain_depth",
                "trigger",
            ),
            work.escalated,
        ),
    )
    put(at("actor_rollup.json"), as_object(work.by_actor))
    put(at("project_rollup.json"), as_object(work.by_project))
    put(at("provenance_index.jsonl"), as_lines(work.trail))


def emit_figures(work, at):
    tally = dict.fromkeys(CLASS_SET, 0)
    for row in work.ledger:
        tally[row["commitment_class"]] += 1
    refused = dict.fromkeys(REASONS, 0)
    for row in work.rejects:
        refused[row["reason_code"]] = refused.get(row["reason_code"], 0) + 1
    handed = sum(r["allocated_minutes"] for r in work.shares)
    owing = sum(r["debt"] for r in work.cadence_rows)

    figures = [
        ("rows_ingested", work.ingested),
        ("rows_rejected", len(work.rejects)),
        ("rows_accepted", work.ingested - len(work.rejects)),
        ("commitments_admitted", len(work.ledger)),
    ]
    figures += [("class_" + name.lower(), tally[name]) for name in CLASS_SET]
    figures += [("reject_" + name.lower(), refused[name]) for name in REASONS]
    figures += [
        ("live_edges", len(work.live)),
        ("dropped_edges", len(work.dropped)),
        ("closure_pairs", len(work.reach_rows)),
        ("blocked_commitments", len(work.blocked)),
        ("open_effort_minutes", work.open_effort),
        ("allocated_minutes", handed),
        ("escalated_commitments", len(work.escalated)),
        ("cadence_debt_total", owing),
    ]
    put(
        at("audit_totals.csv"),
        as_table(
            ("metric", "value"),
            [{"metric": name, "value": value} for name, value in figures],
        ),
    )

    checks = {
        "I1_row_partition": (
            work.ingested
            - len(work.rejects)
            - len(work.accepted)
            - work.applied_states
            + work.refused_moves
            - len(work.live)
            - len(work.dropped)
        ),
        "I2_class_partition": len(work.ledger) - sum(tally.values()),
        "I3_actor_effort": sum(v["open_effort_minutes"] for v in work.by_actor.values())
        - work.open_effort,
        "I4_project_effort": sum(
            v["open_effort_minutes"] for v in work.by_project.values()
        )
        - work.open_effort,
        "I5_closure_frontier": sum(r["frontier_count"] for r in work.blocked)
        - sum(1 for r in work.reach_rows if r["terminal"] == "yes"),
    }
    put(
        at("validation_report.json"),
        as_object(
            {
                "identities": checks,
                "identities_checked": sorted(checks),
                "all_residuals_zero": all(v == 0 for v in checks.values()),
            }
        ),
    )

    put(
        at("run_manifest.json"),
        as_object(
            {
                "day_boundary_offset_minutes": DAY_SHIFT,
                "effort_floor_minutes": FLOOR,
                "effort_ceiling_minutes": CEILING,
                "allocation_floor_minutes": SHARE_FLOOR,
                "window_start": WINDOW_TEXT[0],
                "window_end": WINDOW_TEXT[1],
                "reason_codes": list(REASONS),
                "commitment_classes": list(CLASS_SET),
                "retired_feeds": sorted(work.retired),
                "split_surfaces": work.split,
                "multi_hop_assertions": work.deep_hops,
                "order_tiebreaks_applied": work.ties,
                "edges_dropped_out_of_scope": sum(
                    1 for e in work.dropped if e["drop_reason"] == "EDGE_OUT_OF_SCOPE"
                ),
                "waivers_suppressing": work.suppressing,
                "waivers_inert": work.inert,
                "waivers_lapsed": work.lapsed,
                "allocations_starved": work.starved,
                "illegal_transitions": work.refused_moves,
            }
        ),
    )

    report = [
        "CALDERMOOR COMMITMENT CLOSURE",
        "rows_ingested %d" % work.ingested,
        "rows_rejected %d" % len(work.rejects),
        "commitments_admitted %d" % len(work.ledger),
    ]
    report += ["class_%s %d" % (name.lower(), tally[name]) for name in CLASS_SET]
    report += [
        "live_edges %d" % len(work.live),
        "dropped_edges %d" % len(work.dropped),
        "closure_pairs %d" % len(work.reach_rows),
        "blocked_commitments %d" % len(work.blocked),
        "open_effort_minutes %d" % work.open_effort,
        "allocated_minutes %d" % handed,
        "escalated_commitments %d" % len(work.escalated),
        "cadence_debt_total %d" % owing,
    ]
    report += ["identity_%s %d" % (name, checks[name]) for name in sorted(checks)]
    put(at("reconciliation.txt"), "\n".join(report) + "\n")


def publish(work, target, program):
    target = os.path.abspath(target)
    parent = os.path.dirname(target)
    os.makedirs(parent, exist_ok=True)
    stage = tempfile.mkdtemp(prefix=".caldermoor-stage-", dir=parent)
    backup = None
    try:
        shutil.copyfile(program, os.path.join(stage, "reconcile.py"))
        emit(work, stage)

        if os.path.lexists(target):
            backup = tempfile.mkdtemp(prefix=".caldermoor-backup-", dir=parent)
            os.rmdir(backup)
            os.replace(target, backup)
        try:
            os.replace(stage, target)
            stage = None
        except BaseException:
            if backup is not None and not os.path.lexists(target):
                os.replace(backup, target)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
    except BaseException:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        raise


def main(argv):
    if len(argv) != 3:
        print("usage: reconcile.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    work = Closure(argv[1]).run()
    publish(work, argv[2], os.path.abspath(argv[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
