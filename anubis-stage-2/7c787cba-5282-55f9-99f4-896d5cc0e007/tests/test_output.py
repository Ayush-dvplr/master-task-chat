"""Grader for the regional working timetable path calendar compile task.

Part 1 builds one timetable extract deterministically from a seed, as a set of
model objects, and writes it out as the twenty seven files an extract holds.
Part 2 compiles the extract from those model objects, independently of any file
parsing, and yields the eighteen documents a correct run writes. Part 3 holds
the rewardkit criteria.

Test polarity for negative-weight checks: the check returns True when the cheat
is present, so an honest submission leaves the negative weight unadded.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false

from __future__ import annotations

import ast
import bisect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

SAMPLE_SEED = 814452301
CHALLENGE_SEED = 7731011
EVAL_SEED = 5509283117
VISIBLE_SEED = SAMPLE_SEED

OUT = Path("/app/out")
ENTRY = OUT / "ttc.py"
ENGINE = OUT / "pathcal.py"

EPOCH_ORD = date(1970, 1, 1).toordinal()
DIGEST_MODULUS = 2147483647
MINUTE = 60
DAY = 86400

OPERATORS = [
    ("TOC-01", "Aldermere Regional", 5),
    ("TOC-02", "Brightwater Lines", 4),
    ("TOC-03", "Carrowdean Rail", 3),
    ("TOC-04", "Dunhollow Services", 2),
    ("TOC-05", "Eastmarch Freight", 1),
]
ZONE_WEST = "Z-WEST"
ZONE_EAST = "Z-EAST"
SECTION_CLASSES = ["mainline", "branch", "depot"]

JSON_DOCS = [
    "identity_resolution.json",
    "authority_resolution.json",
    "expansion_audit.json",
    "exception_merge.json",
    "overlay_resolution.json",
    "timepoint_materialization.json",
    "headway_resolution.json",
    "withheld_paths.json",
    "compiled_timetable.json",
    "canonical_calendars.json",
    "timetable_digest.json",
    "data_quality.json",
]
TEXT_DOCS = [
    "operator_rollup.tsv",
    "section_rollup.psv",
    "path_rollup.csv",
    "flagged_paths.xml",
    "compile_report.md",
    "run_status.txt",
]
DOC_NAMES = JSON_DOCS + TEXT_DOCS

QUALITY_CODES = [
    "ALIAS_CYCLE",
    "CAP_BINDING",
    "EMPTY_CALENDAR",
    "FOLD_DEPARTURE",
    "HEADWAY_WITHHELD",
    "UNRESOLVED_SPELLING",
    "VARIANT_CYCLE",
]
FLAG_REASONS = ["cap_binding", "empty_calendar", "fold_departure", "gap_departure", "variant_cycle"]

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
MASK64 = (1 << 64) - 1


# ---------------------------------------------------------------------------
# Part 1a: deterministic pseudo-random source and small helpers.
# ---------------------------------------------------------------------------
class Rng:
    """xorshift64 star. CPython's random is not stable across releases."""

    def __init__(self, seed: int) -> None:
        self.state = (seed | 1) & MASK64

    def next(self) -> int:
        x = self.state
        x ^= (x >> 12) & MASK64
        x ^= (x << 25) & MASK64
        x ^= (x >> 27) & MASK64
        self.state = x & MASK64
        return (self.state * 0x2545F4914F6CDD1D) & MASK64

    def below(self, bound: int) -> int:
        return self.next() % bound if bound > 0 else 0

    def between(self, low: int, high: int) -> int:
        return low + self.below(high - low + 1)

    def pick(self, items: list) -> Any:
        return items[self.below(len(items))]


def iso_day(ordinal: int) -> str:
    return date.fromordinal(ordinal).isoformat()


def iso_instant(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_ordinal(text: str) -> int:
    return date.fromisoformat(text).toordinal()


def local_wall(ordinal: int, minute_of_day: int) -> int:
    """Seconds since the epoch of a naive local wall clock reading."""
    return (ordinal - EPOCH_ORD) * DAY + minute_of_day * MINUTE


def hhmm(minute_of_day: int) -> str:
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"


def iso_weekday(ordinal: int) -> int:
    return date.fromordinal(ordinal).isoweekday()


def month_of(ordinal: int) -> tuple[int, int]:
    day = date.fromordinal(ordinal)
    return day.year, day.month


def add_months(year: int, month: int, count: int) -> tuple[int, int]:
    index = (year * 12 + month - 1) + count
    return index // 12, index % 12 + 1


def month_bounds(year: int, month: int) -> tuple[int, int]:
    first = date(year, month, 1).toordinal()
    next_year, next_month = add_months(year, month, 1)
    return first, date(next_year, next_month, 1).toordinal() - 1


def isoweek_start(ordinal: int) -> int:
    return ordinal - (iso_weekday(ordinal) - 1)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_rows(path: Path, header: list[str], rows: list[list[Any]], delim: str) -> None:
    lines = [delim.join(header)]
    lines.extend(delim.join("" if cell is None else str(cell) for cell in row) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def canonical_id(spelling: str) -> str | None:
    """Upper case, drop every character outside A-Z and 0-9, then split."""
    kept = [ch for ch in spelling.upper() if ("A" <= ch <= "Z") or ("0" <= ch <= "9")]
    if not kept:
        return None
    head = "".join(ch for ch in kept if "A" <= ch <= "Z")
    tail = "".join(ch for ch in kept if "0" <= ch <= "9")
    if not head or not tail or kept != list(head + tail):
        return None
    if len(tail) > 5:
        return None
    return f"{head}-{int(tail):05d}"


def resolve_alias(spelling: str, alias_map: dict[str, str]) -> tuple[str | None, str]:
    """Canonicalise then walk the alias map for at most eight hops."""
    start = canonical_id(spelling)
    if start is None:
        return None, "malformed"
    seen = [start]
    current = start
    for _ in range(8):
        if current not in alias_map:
            return current, "resolved" if len(seen) > 1 else "direct"
        current = alias_map[current]
        if current in seen:
            return None, "cycle"
        seen.append(current)
    return None, "too_long"


# ---------------------------------------------------------------------------
# Part 1b: the model of one extract.
# ---------------------------------------------------------------------------
KNOB_DEFAULTS: dict[str, Any] = {
    "path_count": 96,
    "traps": True,
    "setpos_mode": "mixed",
    "freq_mode": "mixed",
    "limit_mode": "mixed",
    "window_mode": "mixed",
    "fold": True,
    "alias_cycle": True,
    "variant_cycle": True,
    "midnight": True,
    "short_month": True,
    "conflict_pairs": True,
    "headway_scale": 1,
    "mailbox_mainline": 15,
    "variant_depth": 2,
    "extra_aliases": [],
    "extra_exceptions": [],
}

PERIOD_START = date(2027, 1, 4).toordinal()
PERIOD_END = date(2027, 6, 27).toordinal()
GAP_WEST = int(datetime(2027, 3, 28, 1, 0, tzinfo=timezone.utc).timestamp())
GAP_EAST = GAP_WEST
FOLD_EAST = int(datetime(2027, 5, 2, 1, 0, tzinfo=timezone.utc).timestamp())


class Model:
    """Every structure one extract holds, built from a seed and the knobs."""

    def __init__(self, seed: int, knobs: dict[str, Any] | None = None) -> None:
        self.knobs = dict(KNOB_DEFAULTS)
        self.knobs.update(knobs or {})
        if not self.knobs["traps"]:
            self.knobs.update({"setpos_mode": "positive", "fold": False, "alias_cycle": False,
                               "variant_cycle": False, "midnight": False, "short_month": False})
        self.rng = Rng(seed)
        self.seed = seed
        self.period_start = PERIOD_START
        self.period_end = PERIOD_END
        self.operators = [{"operator_id": oid, "name": name, "rank_weight": weight}
                          for oid, name, weight in OPERATORS]
        self._build_zones()
        self._build_sections()
        self._build_routes()
        self._build_policy()
        self._build_rules()
        self._build_paths()
        self._build_aliases()
        self._build_exceptions()
        self._build_decoys()

    # -- zones -------------------------------------------------------------
    def _build_zones(self) -> None:
        west = [{"at_utc": GAP_WEST, "before": 0, "after": 3600}]
        east = [{"at_utc": GAP_EAST, "before": 3600, "after": 7200}]
        if self.knobs["fold"]:
            east.append({"at_utc": FOLD_EAST, "before": 7200, "after": 3600})
        self.zones = [
            {"zone_id": ZONE_WEST, "name": "Western region", "transitions": west},
            {"zone_id": ZONE_EAST, "name": "Eastern region", "transitions": east},
        ]

    def zone(self, zone_id: str) -> dict:
        return next(z for z in self.zones if z["zone_id"] == zone_id)

    # -- sections and routes ----------------------------------------------
    def _build_sections(self) -> None:
        self.sections = []
        for index in range(1, 13):
            klass = SECTION_CLASSES[(index - 1) % 3]
            zone_id = ZONE_WEST if index % 2 == 1 else ZONE_EAST
            self.sections.append({"section_id": f"SEC-{index:02d}", "section_class": klass,
                                  "zone_id": zone_id})

    def _build_routes(self) -> None:
        self.routes = {}
        mainline = [s["section_id"] for s in self.sections if s["section_class"] == "mainline"]
        branch = [s["section_id"] for s in self.sections if s["section_class"] == "branch"]
        depot = [s["section_id"] for s in self.sections if s["section_class"] == "depot"]
        for index in range(1, 17):
            route_id = f"RT-{index:02d}"
            legs = [mainline[index % len(mainline)], branch[(index + 1) % len(branch)]]
            if index % 3 == 0:
                legs.append(depot[(index + 2) % len(depot)])
            span = 1140 if index % 4 == 0 else 60
            rows = []
            for seq, section_id in enumerate(legs, start=1):
                offset = 0 if seq == 1 else span * (seq - 1) // max(1, len(legs) - 1)
                rows.append({"seq": seq, "section_id": section_id, "offset_min": offset})
            self.routes[route_id] = rows

    def route_span(self, route_id: str) -> int:
        return max(leg["offset_min"] for leg in self.routes[route_id])

    # -- policy ------------------------------------------------------------
    def _build_policy(self) -> None:
        scale = self.knobs["headway_scale"]
        self.policy = {
            "min_headway_min": {"mainline": 12 * scale, "branch": 9 * scale, "depot": 5 * scale},
            "deferral_step_min": 6,
            "max_deferrals": 2,
        }
        self.mailbox = [
            {"prefix": "PROPOSED-HEADWAY", "section_class": "branch", "minutes": 25 * scale},
            {"prefix": "APPROVED-HEADWAY", "section_class": "mainline",
             "minutes": self.knobs["mailbox_mainline"] * scale},
        ]

    def applied_headway(self) -> dict[str, int]:
        table = dict(self.policy["min_headway_min"])
        for message in self.mailbox:
            if message["prefix"] == "APPROVED-HEADWAY":
                table[message["section_class"]] = message["minutes"]
        return table

    # -- recurrence rules --------------------------------------------------
    def _build_rules(self) -> None:
        mode = self.knobs["setpos_mode"]
        freq_mode = self.knobs["freq_mode"]
        self.rules = []
        for index in range(1, 41):
            if freq_mode == "isoweek":
                freq = "isoweek"
            elif freq_mode == "monthday":
                freq = "month"
            else:
                freq = ("month", "isoweek", "fourweek")[index % 3]
            anchor = self.period_start - 7 * (index % 5)
            if self.knobs["window_mode"] == "late":
                anchor = self.period_start - 7 * 12
            byday: list[int] = []
            bymonthday: list[int] = []
            if freq_mode == "monthday" or (self.knobs["short_month"] and index % 7 == 0):
                bymonthday = [29, 30, 31][index % 3:index % 3 + 1]
                if not self.knobs["short_month"]:
                    bymonthday = [7 + (index % 14)]
                byday = []
            else:
                count = 1 + index % 3
                byday = sorted({1 + ((index + step * 2) % 7) for step in range(count)})
            if mode == "positive":
                setpos = [1 + (index % 2)] if freq != "isoweek" else [1]
            elif mode == "negative":
                setpos = [-1 - (index % 2)]
            else:
                setpos = [1, -1] if index % 4 == 0 else ([-1] if index % 4 == 1 else [1 + index % 2])
            if self.knobs["limit_mode"] == "tight":
                limit = 3 + index % 3
            elif self.knobs["limit_mode"] == "none":
                limit = 0
            else:
                limit = 0 if index % 3 else 6 + index % 5
            horizon = {"month": 8, "isoweek": 32, "fourweek": 9}[freq]
            self.rules.append({"rule_id": f"RL-{index:04d}", "freq": freq,
                               "anchor": anchor, "byday": byday, "bymonthday": bymonthday,
                               "setpos": setpos, "limit": limit, "horizon_periods": horizon})
        self.rules.append({"rule_id": "RL-9001", "freq": "fourweek",
                           "anchor": date(2027, 3, 28).toordinal(), "byday": [7],
                           "bymonthday": [], "setpos": [1, 2], "limit": 0,
                           "horizon_periods": 4})

    def rule(self, rule_id: str) -> dict:
        return next(r for r in self.rules if r["rule_id"] == rule_id)

    # -- paths -------------------------------------------------------------
    def _build_paths(self) -> None:
        self.paths = []
        count = self.knobs["path_count"]
        route_ids = sorted(self.routes)
        for index in range(count):
            path_id = f"WTT-{1000 + index * 7:05d}"
            operator = self.operators[index % len(self.operators)]
            zone_id = ZONE_WEST if index % 2 == 0 else ZONE_EAST
            rule = self.rules[index % len(self.rules)]
            route_id = route_ids[index % len(route_ids)]
            depart = 6 * 60 + 2 * (index % 90)
            if self.knobs["fold"] and index % 11 == 0:
                zone_id = ZONE_EAST
                depart = 60 + (index % 50) % 55
            if self.knobs["window_mode"] == "late":
                valid_from = self.period_start + 70
                valid_to = self.period_end
            elif index % 5 == 0:
                valid_from = self.period_start + 14 + index % 21
                valid_to = self.period_end - index % 13
            else:
                valid_from = self.period_start
                valid_to = self.period_end
            self.paths.append({
                "path_id": path_id, "operator_id": operator["operator_id"], "zone_id": zone_id,
                "rule_id": rule["rule_id"], "route_id": route_id,
                "depart_local_min": depart, "valid_from": valid_from, "valid_to": valid_to,
                "priority": 1 + index % 5,
                "issue_stamp": iso_instant(local_wall(self.period_start - 40 + index % 29, 480)),
                "variant_of": "",
            })
        self._attach_zone_paths()
        self._attach_variants()
        if self.knobs["conflict_pairs"]:
            self._attach_conflict_pairs()

    def _attach_zone_paths(self) -> None:
        """Paths whose local departures land on a transition boundary."""
        route_ids = sorted(self.routes)
        plan = [(ZONE_WEST, 90), (ZONE_WEST, 92), (ZONE_EAST, 134)]
        if self.knobs["fold"]:
            plan.extend([(ZONE_EAST, 135), (ZONE_EAST, 151)])
        base_index = len(self.paths)
        for number, (zone_id, depart) in enumerate(plan):
            index = base_index + number
            self.paths.append({
                "path_id": f"WTT-{1000 + index * 7:05d}",
                "operator_id": self.operators[number % len(self.operators)]["operator_id"],
                "zone_id": zone_id, "rule_id": "RL-9001",
                "route_id": route_ids[(number * 5) % len(route_ids)],
                "depart_local_min": depart,
                "valid_from": self.period_start, "valid_to": self.period_end,
                "priority": 2 + number % 3,
                "issue_stamp": iso_instant(local_wall(self.period_start - 30 + number, 420)),
                "variant_of": "",
            })

    def _attach_variants(self) -> None:
        depth = self.knobs["variant_depth"]
        chains = min(6, max(1, len(self.paths) // 12))
        for chain in range(chains):
            root = self.paths[chain * 7 % len(self.paths)]
            previous = root["path_id"]
            for step in range(depth):
                slot = (chain * 7 + 3 + step * 2) % len(self.paths)
                child = self.paths[slot]
                if child["path_id"] == previous or child["variant_of"]:
                    continue
                child["variant_of"] = previous.replace("-", " ").lower() if step % 2 else previous
                child["rule_id"] = root["rule_id"]
                child["route_id"] = root["route_id"]
                child["zone_id"] = root["zone_id"]
                child["valid_from"] = root["valid_from"]
                child["valid_to"] = root["valid_to"]
                child["depart_local_min"] = root["depart_local_min"]
                child["priority"] = root["priority"] + (1 if step == 0 else -1)
                previous = child["path_id"]
        if self.knobs["variant_cycle"] and len(self.paths) >= 40:
            left, right = self.paths[33], self.paths[34]
            for side in (left, right):
                side["variant_of"] = ""
            left["variant_of"] = right["path_id"]
            right["variant_of"] = left["path_id"]

    def _attach_conflict_pairs(self) -> None:
        """Paths whose departures sit a known distance apart on one route."""
        applied = self.applied_headway()["mainline"]
        offsets = ([applied] * 3 + [10, 4, 3, 1]) if self.knobs["traps"] else [10, 4, 2]
        route_ids = sorted(self.routes)
        base_index = len(self.paths)
        for number, delta in enumerate(offsets):
            route_id = route_ids[number % len(route_ids)]
            for twin in range(2):
                index = base_index + number * 2 + twin
                path_id = f"WTT-{1000 + index * 7:05d}"
                self.paths.append({
                    "path_id": path_id,
                    "operator_id": self.operators[twin]["operator_id"],
                    "zone_id": ZONE_WEST,
                    "rule_id": self.rules[(number * 3) % len(self.rules)]["rule_id"],
                    "route_id": route_id,
                    "depart_local_min": 9 * 60 + (delta if twin else 0),
                    "valid_from": self.period_start, "valid_to": self.period_end,
                    "priority": 3 - twin,
                    "issue_stamp": iso_instant(local_wall(self.period_start - 10 + twin, 540)),
                    "variant_of": "",
                })

    def path(self, path_id: str) -> dict:
        return next(p for p in self.paths if p["path_id"] == path_id)

    # -- aliases and exceptions -------------------------------------------
    def _build_aliases(self) -> None:
        self.aliases = []
        live = [p["path_id"] for p in self.paths]
        for step in range(9):
            target = live[(step * 5) % len(live)]
            first = f"OLD-{2000 + step * 3:05d}"
            second = f"OLD-{2001 + step * 3:05d}"
            self.aliases.append({"retired": first, "current": second})
            self.aliases.append({"retired": second, "current": target})
        if self.knobs["alias_cycle"]:
            self.aliases.append({"retired": "OLD-09001", "current": "OLD-09002"})
            self.aliases.append({"retired": "OLD-09002", "current": "OLD-09003"})
            self.aliases.append({"retired": "OLD-09003", "current": "OLD-09001"})
        for entry in self.knobs["extra_aliases"]:
            self.aliases.append(dict(entry))

    def _build_exceptions(self) -> None:
        self.exceptions = []
        for index, path in enumerate(self.paths):
            if index % 3:
                continue
            raw = path["path_id"]
            forms = [raw, raw.replace("-", " ").lower(), raw.replace("-", "").lower(),
                     raw.replace("-", "_")]
            spelling = forms[index % len(forms)]
            base = path["valid_from"] + 7 + (index % 40)
            self.exceptions.append({"spelling": spelling, "day": base, "kind": "exclude"})
            self.exceptions.append({"spelling": spelling, "day": base + 1, "kind": "add"})
            if index % 6 == 0:
                self.exceptions.append({"spelling": spelling, "day": base + 1, "kind": "exclude"})
            if index % 9 == 0:
                self.exceptions.append({"spelling": spelling, "day": self.period_end + 30,
                                        "kind": "add"})
        for step in range(6):
            self.exceptions.append({"spelling": f"OLD-{2000 + step * 3:05d}",
                                    "day": self.period_start + 21 + step * 4,
                                    "kind": "exclude"})
            self.exceptions.append({"spelling": f"old {2001 + step * 3:05d}",
                                    "day": self.period_start + 23 + step * 4,
                                    "kind": "add"})
        self.exceptions.append({"spelling": "wtt 01007", "day": self.period_start + 25,
                                "kind": "add"})
        self.exceptions.append({"spelling": "OLD-09001", "day": self.period_start + 26,
                                "kind": "exclude"})
        self.exceptions.append({"spelling": "ZZ", "day": self.period_start + 27, "kind": "add"})
        for entry in self.knobs["extra_exceptions"]:
            item = dict(entry)
            item["day"] = day_ordinal(item.pop("date"))
            self.exceptions.append(item)
        self.exceptions.sort(key=lambda row: (row["spelling"], row["day"], row["kind"]))

    # -- superseded copies -------------------------------------------------
    def _build_decoys(self) -> None:
        self.prior_paths = []
        for index, path in enumerate(self.paths):
            copy = dict(path)
            if index % 4 == 0:
                copy["depart_local_min"] = (copy["depart_local_min"] + 35) % 1440
            if index % 6 == 0:
                copy["valid_to"] = copy["valid_to"] - 21
            self.prior_paths.append(copy)
        self.draft_rules = []
        for index, rule in enumerate(self.rules):
            copy = dict(rule)
            copy["setpos"] = list(rule["setpos"])
            if index % 3 == 0:
                copy["setpos"] = [2]
            if index % 5 == 0:
                copy["limit"] = (rule["limit"] + 4) if rule["limit"] else 5
            self.draft_rules.append(copy)
        self.proposed_transitions = []
        for zone in self.zones:
            for transition in zone["transitions"]:
                row = dict(transition)
                row["zone_id"] = zone["zone_id"]
                row["at_utc"] = row["at_utc"] + 3 * DAY
                self.proposed_transitions.append(row)
        self.legacy_rank = {operator["operator_id"]: operator["rank_weight"] % 5 + 1
                            for operator in self.operators}

    def divergences(self) -> dict[str, int]:
        depart = sum(1 for live, old in zip(self.paths, self.prior_paths)
                     if live["depart_local_min"] != old["depart_local_min"]
                     or live["valid_to"] != old["valid_to"])
        rules = sum(1 for live, old in zip(self.rules, self.draft_rules)
                    if live["setpos"] != old["setpos"] or live["limit"] != old["limit"])
        zones = len(self.proposed_transitions)
        headway = sum(1 for message in self.mailbox if message["prefix"] == "PROPOSED-HEADWAY")
        rank = sum(1 for operator in self.operators
                   if self.legacy_rank[operator["operator_id"]] != operator["rank_weight"])
        return {"departure_window": depart, "operator_rank_weight": rank,
                "recurrence_rule": rules, "section_headway": headway,
                "zone_transition": zones}


# ---------------------------------------------------------------------------
# Part 1c: writing one extract out as the twenty seven files it holds.
# ---------------------------------------------------------------------------
CORPUS_FILES = [
    "compiler_debug.log",
    "exception_dates.csv",
    "extract_provenance.txt",
    "file_role_index.md",
    "glossary.md",
    "headway_policy.json",
    "headway_primer.md",
    "known_issues.md",
    "legacy_compiled_output.json",
    "operator_register.html",
    "overlay_primer.md",
    "path_alias_map.csv",
    "path_register.csv",
    "path_register_prior.csv",
    "recurrence_primer.md",
    "recurrence_rules.json",
    "recurrence_rules_draft.json",
    "report_schema.md",
    "section_register.csv",
    "section_route.psv",
    "timetable_period.json",
    "timetable_rulebook.md",
    "worked_reference_slice.md",
    "wtt_mailbox.mbox",
    "zone_primer.md",
    "zone_transitions.csv",
    "zone_transitions_proposed.csv",
]

PATH_HEADER = ["path_id", "operator_id", "zone_id", "rule_id", "route_id", "depart_local",
               "valid_from", "valid_to", "priority", "issue_stamp", "variant_of"]


def _path_rows(paths: list[dict]) -> list[list[Any]]:
    return [[p["path_id"], p["operator_id"], p["zone_id"], p["rule_id"], p["route_id"],
             hhmm(p["depart_local_min"]), iso_day(p["valid_from"]), iso_day(p["valid_to"]),
             p["priority"], p["issue_stamp"], p["variant_of"]] for p in paths]


def _rule_payload(rules: list[dict]) -> dict:
    return {"rules": [{"rule_id": r["rule_id"], "freq": r["freq"], "anchor": iso_day(r["anchor"]),
                       "byday": list(r["byday"]), "bymonthday": list(r["bymonthday"]),
                       "setpos": list(r["setpos"]), "limit": r["limit"],
                       "horizon_periods": r["horizon_periods"]} for r in rules]}


def _operator_html(model: Model) -> str:
    rows = "".join(
        f'  <tr><td class="oid">{o["operator_id"]}</td><td class="name">{o["name"]}</td>'
        f'<td class="rank">{o["rank_weight"]}</td></tr>\n' for o in model.operators)
    return ("<!DOCTYPE html>\n<html>\n<head><title>Operator register</title></head>\n<body>\n"
            "<h1>Operator register</h1>\n<table id=\"operators\">\n"
            "  <tr><th>operator_id</th><th>name</th><th>rank_weight</th></tr>\n"
            f"{rows}</table>\n</body>\n</html>\n")


def _mailbox_text(model: Model) -> str:
    blocks = []
    for index, message in enumerate(model.mailbox):
        stamp = "Mon Nov 16 09:0" + str(index) + ":00 2026"
        blocks.append(
            f"From timetable.office@aldermere.example {stamp}\n"
            f"From: Timetable Office <timetable.office@aldermere.example>\n"
            f"To: Compile Desk <compile.desk@aldermere.example>\n"
            f"Subject: {message['prefix']} {message['section_class']} {message['minutes']}\n"
            f"Date: {stamp}\n\n"
            f"The minimum headway for the {message['section_class']} class reads "
            f"{message['minutes']} minutes in this message.\n"
            f"Read the subject line for the value; the body is a courtesy restatement.\n\n")
    return "".join(blocks)


def _legacy_payload(model: Model) -> dict:
    return {
        "generated_by": "pathcal 4.2 aborted run",
        "note": "retained for comparison only",
        "registered_path_count": len(model.paths) - 3,
        "admitted_movement_total": 11 * len(model.paths),
        "withheld_movement_total": 4,
        "timetable_digest": 1234567,
        "operator_rank_weight": dict(sorted(model.legacy_rank.items())),
    }


def _debug_log(model: Model) -> str:
    lines = ["2027-01-02T04:00:00Z INFO pathcal 4.2 starting compile",
             "2027-01-02T04:00:01Z INFO reading path register",
             f"2027-01-02T04:00:02Z INFO {len(model.paths)} path rows read",
             "2027-01-02T04:00:03Z INFO reading recurrence rules",
             f"2027-01-02T04:00:04Z INFO {len(model.rules)} rule rows read",
             "2027-01-02T04:00:05Z WARN alias walk left a spelling unresolved",
             "2027-01-02T04:00:06Z WARN local departures had no instant",
             "2027-01-02T04:00:07Z INFO headway walk started",
             "2027-01-02T04:00:31Z ERROR compile aborted before the digest stage",
             "2027-01-02T04:00:31Z INFO partial output left in place"]
    return "\n".join(lines) + "\n"


def _provenance_text(model: Model) -> str:
    return ("extract: regional working timetable, path calendar compile\n"
            f"timetable_id: WTT-{model.period_start % 100000:05d}\n"
            f"period: {iso_day(model.period_start)} to {iso_day(model.period_end)}\n"
            f"path_rows: {len(model.paths)}\n"
            f"rule_rows: {len(model.rules)}\n"
            "cut: end of day before the compile run\n")


def write_corpus(root: Path, model: Model) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    write_rows(root / "path_register.csv", PATH_HEADER, _path_rows(model.paths), ",")
    write_rows(root / "path_register_prior.csv", PATH_HEADER,
               _path_rows(model.prior_paths), ",")
    write_json(root / "recurrence_rules.json", _rule_payload(model.rules))
    write_json(root / "recurrence_rules_draft.json", _rule_payload(model.draft_rules))
    write_rows(root / "exception_dates.csv", ["path", "date", "kind"],
               [[row["spelling"], iso_day(row["day"]), row["kind"]] for row in model.exceptions],
               ",")
    write_rows(root / "path_alias_map.csv", ["retired_path", "current_path"],
               [[row["retired"], row["current"]] for row in model.aliases], ",")
    transitions = []
    for zone in model.zones:
        for transition in zone["transitions"]:
            transitions.append([zone["zone_id"], iso_instant(transition["at_utc"]),
                                transition["before"], transition["after"]])
    write_rows(root / "zone_transitions.csv",
               ["zone_id", "at_utc", "offset_before_sec", "offset_after_sec"], transitions, ",")
    write_rows(root / "zone_transitions_proposed.csv",
               ["zone_id", "at_utc", "offset_before_sec", "offset_after_sec"],
               [[row["zone_id"], iso_instant(row["at_utc"]), row["before"], row["after"]]
                for row in model.proposed_transitions], ",")
    write_rows(root / "section_register.csv", ["section_id", "section_class", "zone_id"],
               [[s["section_id"], s["section_class"], s["zone_id"]] for s in model.sections], ",")
    route_rows = []
    for route_id in sorted(model.routes):
        for leg in model.routes[route_id]:
            route_rows.append([route_id, leg["seq"], leg["section_id"], leg["offset_min"]])
    write_rows(root / "section_route.psv", ["route_id", "seq", "section_id", "offset_min"],
               route_rows, "|")
    write_json(root / "headway_policy.json", model.policy)
    write_json(root / "timetable_period.json",
               {"timetable_id": f"WTT-{model.period_start % 100000:05d}",
                "period_start": iso_day(model.period_start),
                "period_end": iso_day(model.period_end)})
    (root / "operator_register.html").write_text(_operator_html(model), encoding="utf-8")
    (root / "wtt_mailbox.mbox").write_text(_mailbox_text(model), encoding="utf-8")
    write_json(root / "legacy_compiled_output.json", _legacy_payload(model))
    (root / "compiler_debug.log").write_text(_debug_log(model), encoding="utf-8")
    (root / "extract_provenance.txt").write_text(_provenance_text(model), encoding="utf-8")
    for name, text in DOCUMENTS.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Part 1d: the shipped documents. Static text, identical in every extract, so
# a generated extract is governed by exactly the rules the shipped one is.
# ---------------------------------------------------------------------------
RULEBOOK = """# Working timetable compile rulebook

This is the governing contract for one compile of the regional working
timetable. It is written for whoever maintains the compiler. Every figure the
compile publishes follows from the rules below and from the extract the compile
is pointed at. Nothing here depends on a value that lives outside the extract.

The compile runs in ten stages. Each stage consumes the stage before it, so a
wrong figure in an early stage moves every figure after it.

Dates are plain calendar dates. Instants are UTC and are written
`YYYY-MM-DDTHH:MM:SSZ`. A local wall clock reading is a date plus an `HH:MM`
time with no offset attached; stage 6 is the only stage that turns one into an
instant. Day arithmetic is inclusive at both ends wherever a range is given.

`file_role_index.md` states the role every file in the extract plays, including
which files are superseded. `report_schema.md` states the exact shape of every
document the compile writes.

## Stage 1, path identity

A path identifier is written in several ways across the extract. The canonical
form is derived like this, and nothing else counts as a path identifier:

1. Upper case the spelling.
2. Drop every character that is not an upper case letter A to Z or a digit 0
   to 9.
3. The remaining characters have to be letters followed by digits, with no
   letter after the first digit. A spelling that leaves no letter, leaves no
   digit, mixes the two, or leaves more than five digits is malformed.
4. The canonical form is the letters, a single hyphen, and the digits read as a
   number and written back with five places.

So `wtt 1007`, `WTT-1007`, `wtt_01007` and `  WTT01007 ` all canonicalise to
`WTT-01007`, while `ZZ`, `12345` and `WTT-1A` are malformed.

`path_alias_map.csv` retires identifiers. A spelling is resolved by
canonicalising it and then, while the current identifier appears in the
`retired_path` column, moving to the `current_path` of that row, canonicalised
the same way. At most eight such moves are taken. Three outcomes end the walk:

- The current identifier does not appear in the `retired_path` column. That
  identifier is the resolution.
- The walk reaches an identifier it has already visited. The walk resolves to
  nothing. When the identifier it has arrived back at is the one the walk
  started from, that identifier sits on a cycle.
- Eight moves pass and the identifier reached still appears in the
  `retired_path` column. The walk resolves to nothing and the spelling counts
  as unresolved.

The identifiers tested for sitting on a cycle are the canonical forms of the
`retired_path` column together with the register's own identifiers, and the
compile reports the ones that do. A path is registered when its row appears in
`path_register.csv` and its identifier does not sit on a cycle. A path rejected
later, in stage 5, runs on no date at all and still appears in the identity
report, the withheld document, the canonical calendars and the digest.

## Stage 2, authority

Five fields are carried by two files each. `file_role_index.md` names the file
of record for every one of them, and the compile reads the file of record and
nothing else. The authority report states, per field, the file of record and
how far the superseded copy diverges from it. The five divergence counts are
defined as:

- `departure_window`: the number of path identifiers present in both
  `path_register.csv` and `path_register_prior.csv` whose `depart_local` or
  whose `valid_to` differ between the two.
- `recurrence_rule`: the number of rule identifiers present in both
  `recurrence_rules.json` and `recurrence_rules_draft.json` whose `setpos` list
  or whose `limit` differ between the two.
- `zone_transition`: the number of rows in `zone_transitions_proposed.csv`
  whose four fields do not appear as a row of `zone_transitions.csv`.
- `section_headway`: the number of messages in `wtt_mailbox.mbox` whose subject
  prefix is anything other than `APPROVED-HEADWAY`.
- `operator_rank_weight`: the number of operators whose `rank_weight` in
  `legacy_compiled_output.json` differs from the one in
  `operator_register.html`.

`wtt_mailbox.mbox` is a plain mbox. A message's subject line reads
`Subject: <PREFIX> <section class> <minutes>`. A message whose prefix is
`APPROVED-HEADWAY` replaces the minimum headway of that section class for this
compile. Any other prefix changes nothing. The body of a message is a courtesy
restatement and decides nothing.

`operator_register.html` carries one table row per operator with the
identifier, the name and the rank weight, in that order.

## Stage 3, rule expansion

Every path names a rule in `recurrence_rules.json`. A rule has a `freq`, an
`anchor` date, a `byday` list of ISO weekday numbers where Monday is 1 and
Sunday is 7, a `bymonthday` list of day of month numbers, a `setpos` list of
non zero integers, a `limit` and a `horizon_periods` count.

The rule is expanded period by period. Period 0 and the periods after it are:

- `month`: period k is the calendar month reached by moving the month that
  contains the anchor forward by k months. The period covers every day of that
  month.
- `isoweek`: period k covers the seven days starting at the Monday of the ISO
  week that contains the anchor, moved forward by 7k days.
- `fourweek`: period k covers the twenty eight days starting at the anchor
  moved forward by 28k days.

Periods 0 up to and including `horizon_periods` minus 1 are expanded, and no
others.

Inside one period the candidate set is every day of that period that satisfies
both of these, in ascending date order:

- `byday` is empty, or the ISO weekday of the day appears in `byday`.
- `bymonthday` is empty, or the day of month of the day appears in
  `bymonthday`.

A rule whose `byday` and `bymonthday` are both empty has no candidate in any
period. A `bymonthday` value larger than the length of the month a period falls
in simply matches no day, so a short month contributes nothing rather than
clamping onto its last day.

The selection inside one period reads `setpos` against that period's own
candidate set, never against the whole expansion:

- A position p greater than zero selects the candidate at one based index p,
  and selects nothing when p is larger than the size of the set.
- A position p less than zero selects the candidate at zero based index
  size plus p, so -1 is the last candidate of the period and -2 the one before
  it, and selects nothing when size plus p is below zero.

The selected days of the whole expansion are the union of every period's
selection, in ascending date order. `recurrence_primer.md` works three
selections through on invented figures.

## Stage 4, exceptions and the cap

`exception_dates.csv` carries one row per exception with a path spelling, a
date and a kind of `exclude` or `add`. The spelling is resolved through stage
1. A row whose spelling resolves to nothing applies to no path. A row that
resolves to an identifier no register row carries applies to no path either.
Two rows that resolve to the same path, the same date and the same kind are one
exception.

For one path, the merged sequence is built in this order:

1. Start from the selected days of stage 3.
2. Remove every date the path carries an `exclude` for, whether or not stage 3
   selected it.
3. Add every date the path carries an `add` for that the path does not also
   carry an `exclude` for on the same date. An addition that collides with an
   exclusion on the same date is dropped and counted as a dropped addition. An
   addition already present changes nothing.
4. Sort ascending.

The cap is applied after step 4 and never before it. When the rule's `limit` is
greater than zero, the merged sequence keeps its first `limit` dates and drops
the rest. The dates are counted from the start of the merged sequence, which
begins at the rule anchor rather than at the path's validity window, so a path
whose window opens long after its anchor has to be expanded from the anchor for
the cap to land in the right place. A `limit` of zero caps nothing.

Only after the cap is the sequence clipped to the path's validity window, which
is `valid_from` to `valid_to` inclusive at both ends. The result is the path's
running day set entering stage 5.

## Stage 5, variant supersession

A path whose `variant_of` column is non empty names a base path. The spelling
is resolved through stage 1. The named path is the base when it resolves to a
registered path that is not the path itself; in every other case the path has no
base and is a chain root.

Following bases from a path either ends at a path with no base or arrives back
at a path already on the chain. In the second case the paths from the one it
arrived back at onward form a cycle: every path on that cycle is rejected, runs
on no date, and is reported with the reason `variant_cycle`. A path that leads
into a cycle without being on it is not rejected.

The chain root of a path is the path its base chain ends at, and its chain depth
is the number of bases between it and that root. The walk up the chain stops at
a rejected path, so a path whose base chain reaches one has that rejected path
as its chain root.

Every base and variant pair is one edge. Edges are taken in order of the chain
depth of the base ascending, then the base identifier ascending, then the
variant identifier ascending. For each edge the shared dates are the dates that
are in both running day sets at that moment. The winner of the edge keeps them
and the loser loses them. The winner is decided in this order:

1. The higher `priority`.
2. The later `issue_stamp`.
3. The smaller canonical identifier.

Edges are taken one at a time and each one reads the day sets the edges before
it left behind, so a chain of three paths resolves from the root outward.
`overlay_primer.md` works one chain and one cycle through.

## Stage 6, timepoints

`zone_transitions.csv` gives, per zone, the instants at which the zone's offset
from UTC changes, with the offset in seconds before and after each one. Rows of
a zone are read in ascending instant order. The zone's offset before the first
transition is the `offset_before_sec` of that first row. The offset in force at
an instant t is the `offset_after_sec` of the last transition at or before t, or
the offset before the first transition when t is earlier than all of them.

A path's departure for one running day is the local wall clock reading of that
day at the path's `depart_local`. The instant it names is found like this. Take
the zone's distinct offsets, which are the offset before the first transition
together with the `offset_after_sec` of every transition. For each offset o,
the instant `wall minus o` is a candidate when the offset in force at that
instant is o itself. Then:

- Exactly one candidate: that instant is the departure.
- Two or more candidates: the local reading is a fold and the departure is the
  latest of the candidates.
- No candidate: the local reading sits in a gap. The gap belongs to a
  transition whose offset grows and whose local interval, from
  `at_utc plus offset_before_sec` up to but outside
  `at_utc plus offset_after_sec`, contains the reading; where more than one
  would match, the earliest such transition by instant is taken. The departure
  is `wall minus offset_before_sec` of that transition, which moves the reading
  forward by the length of the gap. The length of the gap in minutes is counted
  as shifted minutes.

`zone_primer.md` works a gap and a fold through on invented figures.

The path's route in `section_route.psv` gives the sections it runs over, each
with an offset in minutes from the departure. The entry instant of a section is
the departure instant plus that offset in minutes. A route whose offsets carry
the last section past local midnight changes nothing about the day: the service
date of a movement is the running day its departure was taken from, and no
entry is re-dated.

One movement is one path on one running day. A path's movements are taken in
ascending date order.

## Stage 7, headway admission

`headway_policy.json` gives the minimum headway in minutes per section class,
the deferral step in minutes and the maximum number of deferrals. The minimum
headway of a section is the one for its class in `section_register.csv`, after
any `APPROVED-HEADWAY` message from stage 2 has replaced it.

Every movement is walked once, in this order:

1. The rank weight of the movement's operator, descending.
2. The `priority` of the movement's path, descending.
3. The canonical path identifier, ascending.
4. The service date, ascending.

For one movement the deferral counts 0, 1 and up to the maximum are tried in
ascending order. At count k every entry instant of the movement is the stage 6
entry instant plus k times the deferral step in minutes. The count clears when,
for every section of the route, the absolute difference between that entry
instant and every entry instant already admitted on the same section is at
least the minimum headway of that section. A difference exactly equal to the
minimum headway clears; only a difference below it conflicts.

The first count that clears is taken, its entry instants join the admitted set
of their sections, and the movement is admitted with a deferral of k times the
step in minutes. When no count clears, the movement is withheld with the reason
`headway` and none of its entry instants joins the admitted set.

`headway_primer.md` works the ladder through on invented figures.

## Stage 8, the compiled timetable

Per path the compile reports the admitted movement count, the count of admitted
movements that took a deferral above zero, the withheld movement count, the sum
of the deferral minutes of its admitted movements, and its path minutes, which
are the admitted movement count multiplied by the route span. The route span is
the largest section offset of the route in minutes.

## Stage 9, canonical calendars

The admitted service dates of one path are re-encoded as a bit calendar:

- The base day is the earliest admitted date. A path with no admitted date has
  a base day of its `valid_from`, a bit length of zero and an empty hex string.
- The bit length is the latest admitted date minus the base day plus one.
- Bit i, counted from zero, is set when the base day plus i days is an admitted
  date.
- The bits are packed least significant bit first inside each byte, so bit 8j
  is the value 1 bit of byte j and bit 8j plus 7 is the value 128 bit.
- The byte string is written as lower case hexadecimal with two characters per
  byte. The last byte always carries the highest set bit, so no trailing zero
  byte is ever written.

## Stage 10, the digest and the rollups

The paths are taken in ascending canonical identifier order, counted from
position 1. The value of a path is its admitted movement count multiplied by
one thousand plus its deferral minute total. The term of a path is its position
multiplied by its value, taken modulo 2147483647. The digest is the sum of
every term, taken modulo 2147483647.

The rollups by operator, by section and by path, the flag list, the data
quality document, the prose report and the status line are all defined in
`report_schema.md`.
"""

SCHEMA = """# Compile output schema

The compile writes eighteen documents into its output directory and nothing
else. Twelve are JSON, six are text. Every JSON document is one object
serialized with sorted keys, two space indentation and a trailing newline.
Every delimited document carries the header line shown, one row per key in the
stated order, no quoting, a single newline between rows and one at the end.

Dates are `YYYY-MM-DD`. Instants are `YYYY-MM-DDTHH:MM:SSZ`. Every count and
every minute figure is a JSON integer.

## identity_resolution.json

Keys: `alias_row_count`, `canonical_path_count`, `malformed_spellings`,
`rejected_cycle_members`, `resolved_through_alias_count`,
`unresolved_spellings`.

`canonical_path_count` counts the register rows whose identifier does not sit
on a cycle. `alias_row_count` counts the rows of `path_alias_map.csv`.

The two spelling lists and the alias count are drawn from one pool: the
distinct values of the `path` column of `exception_dates.csv` together with the
distinct non empty values of the `variant_of` column of `path_register.csv`.
`resolved_through_alias_count` counts the spellings of that pool whose
resolution took at least one alias move and landed on a registered path.
`malformed_spellings` is the sorted list of the spellings of that pool that
fail canonicalisation. `unresolved_spellings` is the sorted list of the
spellings of that pool that canonicalise and whose walk then resolves to
nothing. `rejected_cycle_members` is the sorted list of canonical identifiers
that sit on a cycle, which is the one list drawn from the alias map and the
register rather than from that pool.

## authority_resolution.json

Keys: `fields`, `superseded_file_count`.

`fields` is a list of five objects, sorted by `field`, each with `field`,
`source_of_record` and `divergence_count`. The field names are
`departure_window`, `operator_rank_weight`, `recurrence_rule`,
`section_headway` and `zone_transition`. `source_of_record` is the bare file
name of the file of record, taken from this table, because two files can hold
a role in one field and only one of them is named:

| field | source_of_record |
|---|---|
| `departure_window` | `path_register.csv` |
| `operator_rank_weight` | `operator_register.html` |
| `recurrence_rule` | `recurrence_rules.json` |
| `section_headway` | `wtt_mailbox.mbox` |
| `zone_transition` | `zone_transitions.csv` |

`superseded_file_count` counts the files `file_role_index.md` gives the
superseded role, which is four.

## expansion_audit.json

Keys: `paths`, `rules_with_empty_selection`, `selected_total`.

`paths` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `rule_id`, `period_count`, `candidate_count`, `selected_count`,
`first_selected` and `last_selected`. `candidate_count` is the total size of
every period's candidate set. `first_selected` and `last_selected` are dates, or
null when the path selected nothing. `rules_with_empty_selection` is the sorted
list of rule identifiers that selected nothing for at least one path that names
them. `selected_total` sums `selected_count`.

## exception_merge.json

Keys: `paths`, `dropped_addition_total`, `cap_bound_paths`.

`paths` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `excluded_count`, `added_count`, `dropped_addition_count`,
`pre_cap_count`, `cap`, `post_cap_count`, `in_window_count`, `first_in_window`
and `last_in_window`. `excluded_count` counts the exclusion dates that removed a
date that was there. `added_count` counts the additions that put a date into the
sequence that was not already in it.
`cap` is the rule's `limit`. The two date fields are null when the window holds
nothing. `dropped_addition_total` sums `dropped_addition_count`.
`cap_bound_paths` is the sorted list of path identifiers whose cap dropped at
least one date.

## overlay_resolution.json

Keys: `edge_count`, `paths`, `rejected_cycle_paths`.

`paths` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `chain_root`, `chain_depth`, `lost_day_count` and `kept_day_count`.
A rejected path has a `chain_root` of its own identifier, a `chain_depth` of 0,
a `kept_day_count` of 0 and a `lost_day_count` equal to the day count it
entered the stage with. `edge_count` counts the base and variant edges.
`rejected_cycle_paths` is the sorted list of identifiers rejected for a variant
cycle.

## timepoint_materialization.json

Keys: `fold_count`, `gap_count`, `midnight_crossing_count`, `movement_total`,
`paths`, `shifted_minute_total`.

`paths` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `movement_count`, `first_departure_utc` and `last_departure_utc`.
The two instant fields are null when the path has no movement. `gap_count` and
`fold_count` count movements whose departure resolved through a gap and through
a fold. `shifted_minute_total` sums the gap lengths in minutes over the gap
movements. `midnight_crossing_count` counts movements whose last section entry
falls on a later local date than the service date, measured in the path's zone
at the offset in force at that entry instant. `movement_total` sums
`movement_count`.

## headway_resolution.json

Keys: `admitted_total`, `deferral_histogram`, `deferred_total`,
`section_admitted_counts`, `withheld_total`.

`deferral_histogram` is an object whose keys are the deferral counts as decimal
strings from `0` up to the maximum, each mapping to the number of admitted
movements that took that count. `section_admitted_counts` maps every section
identifier in `section_register.csv` to the number of admitted entry instants
on it. `deferred_total` counts admitted movements whose count was above zero.

## withheld_paths.json

Keys: `movements`, `rejected_paths`.

`movements` is a list sorted by `path_id` then `service_date`, one object per
withheld movement, with `path_id`, `service_date` and `reason`. The only reason
a movement carries is `headway`. `rejected_paths` is a list sorted by
`path_id`, one object per rejected path, with `path_id` and `reason`, where the
reason is `variant_cycle`.

## compiled_timetable.json

Keys: `admitted_movement_total`, `path_minutes_total`, `paths`,
`withheld_movement_total`.

`paths` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `operator_id`, `zone_id`, `route_id`, `admitted_day_count`,
`deferred_day_count`, `withheld_day_count`, `deferral_minute_total` and
`path_minutes`.

## canonical_calendars.json

Keys: `calendars`, `set_bit_total`.

`calendars` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `base_day`, `bit_length` and `hex`. `set_bit_total` sums the set
bits over every calendar.

## timetable_digest.json

Keys: `digest`, `leading_terms`, `modulus`, `term_count`.

`modulus` is 2147483647. `term_count` counts the paths the digest ran over.
`leading_terms` is a list of the first three terms in position order, each an
object with `position`, `value` and `term`. A compile with fewer than three
paths lists as many as it has.

## data_quality.json

Keys: `issue_counts`, `issue_total`, `subjects`.

`issue_counts` maps every one of the seven codes below to a count, with a zero
entry when the code did not fire. `subjects` maps every one of the seven codes
to a sorted list of the subjects that raised it, empty when none did.
`issue_total` sums the counts.

| code | subject | raised when |
|---|---|---|
| `ALIAS_CYCLE` | canonical identifier | the identifier sits on an alias cycle |
| `CAP_BINDING` | path identifier | the rule cap dropped at least one date |
| `EMPTY_CALENDAR` | path identifier | the path has no admitted date |
| `FOLD_DEPARTURE` | path identifier | at least one departure resolved through a fold |
| `HEADWAY_WITHHELD` | path identifier | at least one movement was withheld |
| `UNRESOLVED_SPELLING` | spelling as written | the spelling is malformed or its walk failed |
| `VARIANT_CYCLE` | path identifier | the path sits on a variant cycle |

## operator_rollup.tsv

Tab separated. Header
`operator_id	rank_weight	path_count	admitted_movements	withheld_movements	path_minutes`.
One row per operator in `operator_register.html`, sorted by `operator_id`.

## section_rollup.psv

Pipe separated. Header
`section_id|section_class|zone_id|min_headway_min|admitted_entries`. One row per
section, sorted by `section_id`. `min_headway_min` is the value in force after
stage 2.

## path_rollup.csv

Comma separated. Header
`path_id,operator_id,rule_id,admitted_days,deferred_days,withheld_days,path_minutes`.
One row per registered path, sorted by `path_id`.

## flagged_paths.xml

One `flagged` element carrying a `count` attribute and one `path` child per flag
with an `id` attribute and a `reason` attribute, sorted by identifier then
reason. The five reasons are `cap_binding`, `empty_calendar`,
`fold_departure`, `gap_departure` and `variant_cycle`, raised on the same
conditions as the matching data quality codes, with `gap_departure` raised when
at least one departure of the path resolved through a gap. `count` is the number
of `path` children. The document is written with the XML declaration line
`<?xml version="1.0" encoding="utf-8"?>`, then the `flagged` element, then a
trailing newline.

## compile_report.md and run_status.txt

These two carry the line shapes the shipped reporting code already writes, and
this repair leaves those shapes alone. Read them off that code. The figures they
carry are the ones the stages above produce.
"""

ROLE_INDEX = """# File role index

Every file in the extract plays one of four roles. A file of record decides a
field. A superseded file carries the same field with older or unapproved
numbers and decides nothing. An input file carries a field no other file
carries. An advisory file is kept for operators to read and decides nothing.

| file | role | field it decides |
|---|---|---|
| `path_register.csv` | file of record | the departure and the validity window of every path |
| `path_register_prior.csv` | superseded | nothing, it is the previous issue of the register |
| `recurrence_rules.json` | file of record | the body of every recurrence rule |
| `recurrence_rules_draft.json` | superseded | nothing, it is an unapproved draft |
| `zone_transitions.csv` | file of record | the offset history of every zone |
| `zone_transitions_proposed.csv` | superseded | nothing, it is a proposal |
| `headway_policy.json` | file of record | the headway policy before any approved revision |
| `wtt_mailbox.mbox` | file of record | the approved revision of a section class headway |
| `operator_register.html` | file of record | the rank weight of every operator |
| `legacy_compiled_output.json` | superseded | nothing, it is the aborted run's own output |
| `exception_dates.csv` | input | the exclusions and additions of every path |
| `path_alias_map.csv` | input | the retired identifiers |
| `section_register.csv` | input | the class and zone of every section |
| `section_route.psv` | input | the sections and offsets of every route |
| `timetable_period.json` | input | the identifier and bounds of the timetable period |
| `timetable_rulebook.md` | advisory | nothing, it is the contract itself |
| `report_schema.md` | advisory | nothing, it is the output contract |
| `file_role_index.md` | advisory | nothing, it is this index |
| `recurrence_primer.md` | advisory | nothing, worked selections |
| `zone_primer.md` | advisory | nothing, worked offsets |
| `headway_primer.md` | advisory | nothing, worked admission |
| `overlay_primer.md` | advisory | nothing, worked supersession |
| `worked_reference_slice.md` | advisory | nothing, a worked micro compile |
| `glossary.md` | advisory | nothing, terms |
| `known_issues.md` | advisory | nothing, operator notes |
| `compiler_debug.log` | advisory | nothing, the aborted run's trace |
| `extract_provenance.txt` | advisory | nothing, the cut description |

Four superseded files ship, and each of them looks exactly as well formed as
the file of record beside it. A compile that reads one of them is wrong in the
field that file carries, and wrong in every later stage that consumes it.
"""

RECURRENCE_PRIMER = """# Recurrence primer

Three worked selections. The figures are invented and belong to no path in this
extract; they exist so the rules of stage 3 can be checked against arithmetic.

## A month period with two positive positions

Rule: `freq` month, `anchor` 2030-02-11, `byday` [2, 4], `bymonthday` empty,
`setpos` [1, 3], `horizon_periods` 2.

Period 0 is February 2030. The Tuesdays and Thursdays of that month are
2030-02-05, 2030-02-07, 2030-02-12, 2030-02-14, 2030-02-19, 2030-02-21,
2030-02-26 and 2030-02-28, so the candidate set has eight members. Position 1
selects 2030-02-05 and position 3 selects 2030-02-12.

Period 1 is March 2030. The candidate set is 2030-03-05, 2030-03-07,
2030-03-12, 2030-03-14, 2030-03-19, 2030-03-21, 2030-03-26 and 2030-03-28.
Position 1 selects 2030-03-05 and position 3 selects 2030-03-12.

The selection of the rule is 2030-02-05, 2030-02-12, 2030-03-05 and
2030-03-12. Note that position 3 is the third candidate of its own period, not
the third candidate of the expansion.

## An isoweek period with a negative position

Rule: `freq` isoweek, `anchor` 2030-02-13, `byday` [1, 3, 5], `bymonthday`
empty, `setpos` [-1], `horizon_periods` 3.

The anchor is a Wednesday, so period 0 starts on Monday 2030-02-11 and runs to
Sunday 2030-02-17. Its candidate set is 2030-02-11, 2030-02-13 and 2030-02-15,
a set of size three. Position -1 reads zero based index 3 plus -1, which is 2,
so it selects 2030-02-15. Position -3 would read index 0 and select
2030-02-11, and position -4 would read index -1, which is below zero, and
select nothing.

Periods 1 and 2 start on 2030-02-18 and 2030-02-25 and select 2030-02-22 and
2030-03-01 the same way.

## A month day rule in a short month

Rule: `freq` month, `anchor` 2030-01-09, `byday` empty, `bymonthday` [31],
`setpos` [1], `horizon_periods` 4.

Period 0 is January 2030 and its candidate set is 2030-01-31, so position 1
selects that date. Period 1 is February 2030, which has no 31st, so its
candidate set is empty and position 1 selects nothing. Period 2 is March 2030
and selects 2030-03-31. Period 3 is April 2030, which has no 31st, so it
selects nothing. The selection is 2030-01-31 and 2030-03-31, and February does
not fall back onto 2030-02-28.

## A fourweek period

Rule: `freq` fourweek, `anchor` 2030-02-04, `byday` [6], `bymonthday` empty,
`setpos` [2], `horizon_periods` 2.

Period 0 covers 2030-02-04 to 2030-03-03 and period 1 covers 2030-03-04 to
2030-03-31. The Saturdays of period 0 are 2030-02-09, 2030-02-16, 2030-02-23
and 2030-03-02, so position 2 selects 2030-02-16. The Saturdays of period 1 are
2030-03-09, 2030-03-16, 2030-03-23 and 2030-03-30, so position 2 selects
2030-03-16.
"""

ZONE_PRIMER = """# Zone primer

Two worked resolutions on an invented zone, so the rules of stage 6 can be
checked against arithmetic.

Take a zone whose transition table holds two rows:

| at_utc | offset_before_sec | offset_after_sec |
|---|---|---|
| 2030-03-31T01:00:00Z | 0 | 3600 |
| 2030-10-27T01:00:00Z | 3600 | 0 |

The offset before the first transition is 0. The distinct offsets of the zone
are 0 and 3600.

## A gap

A path departs at 01:30 local on 2030-03-31. The wall reading is
2030-03-31T01:30 with no offset attached.

Try offset 0: the instant would be 2030-03-31T01:30:00Z, and the offset in
force at that instant is 3600, not 0, so this is no candidate. Try offset 3600:
the instant would be 2030-03-31T00:30:00Z, and the offset in force there is 0,
not 3600, so this is no candidate either. There is no candidate, so the reading
sits in a gap.

The gap belongs to the first transition, whose offset grows from 0 to 3600 and
whose local interval runs from 2030-03-31T01:00 to 2030-03-31T02:00. The
reading 01:30 is inside it. The departure is the wall reading minus the offset
before, so 2030-03-31T01:30:00Z, and the gap is 3600 seconds, which is 60
shifted minutes. In local terms the departure has moved forward from 01:30 to
02:30.

## A fold

A path departs at 01:30 local on 2030-10-27.

Try offset 0: the instant would be 2030-10-27T01:30:00Z, and the offset in
force there is 0, so this is a candidate. Try offset 3600: the instant would be
2030-10-27T00:30:00Z, and the offset in force there is 3600, so this is a
candidate too. Two candidates, so the reading is a fold.

The departure is the latest candidate, 2030-10-27T01:30:00Z, which is the local
reading under the offset that applies after the transition. The earlier
candidate, 2030-10-27T00:30:00Z, is not the departure.

## An ordinary reading and the sections

A path departs at 09:00 local on 2030-06-01. Only offset 3600 gives a candidate,
so the departure is 2030-06-01T08:00:00Z. A route whose second section carries
an offset of 240 minutes puts that entry at 2030-06-01T12:00:00Z. A route whose
last section carries an offset of 960 minutes puts that entry at
2030-06-02T00:00:00Z, which is 2030-06-02T01:00 local, a later local date. The
movement still belongs to the service date 2030-06-01.
"""

HEADWAY_PRIMER = """# Headway primer

One worked admission on invented figures, so the ladder of stage 7 can be
checked against arithmetic.

Take a section of class mainline whose minimum headway in force is 15 minutes,
a deferral step of 6 minutes and a maximum of 2 deferrals. Four movements name
routes whose only section is that one, with an offset of 0 minutes, and the walk
has already put them in this order:

| movement | stage 6 entry |
|---|---|
| M1 | 2030-06-01T09:00:00Z |
| M2 | 2030-06-01T09:15:00Z |
| M3 | 2030-06-01T09:10:00Z |
| M4 | 2030-06-01T09:01:00Z |

M1 is walked first. The admitted set of the section is empty, so count 0 clears
and M1 is admitted with a deferral of 0. The admitted set now holds 09:00.

M2 is walked next. At count 0 the gap to 09:00 is exactly 15 minutes, which is
the minimum, so the count clears. A reading that treats the minimum itself as a
conflict would defer M2 for no reason. M2 is admitted with a deferral of 0 and
the admitted set holds 09:00 and 09:15.

M3 is walked next. At count 0 its entry is 09:10, five minutes from 09:15 and
ten from 09:00, so the count conflicts. At count 1 the entry is 09:16, one
minute from 09:15, so that conflicts too. At count 2 the entry is 09:22, seven
minutes from 09:15, so that conflicts as well. No count clears, so M3 is
withheld with the reason headway and none of its entries joins the admitted set,
which still holds 09:00 and 09:15.

M4 is walked last. At count 0 its entry is 09:01, one minute from 09:00, which
conflicts. At count 1 the entry is 09:07, seven minutes from 09:00 and eight
from 09:15, which conflicts. At count 2 the entry is 09:13, thirteen minutes
from 09:00, which conflicts. M4 is withheld as well.

Two movements are admitted, both at a deferral of 0, and two are withheld. Had
M3 been walked before M2, M3 would have cleared at count 0 and M2 would have
been the one to defer, which is why the walk order of stage 7 is part of the
contract rather than a convenience.
"""

OVERLAY_PRIMER = """# Overlay primer

One worked chain and one worked cycle on invented figures, so the rules of
stage 5 can be checked against arithmetic.

## A chain of three

Three paths name each other as bases. AA-00001 names nothing, AA-00002 names
AA-00001 and AA-00003 names AA-00002. So AA-00001 is the chain root at depth 0,
AA-00002 is at depth 1 and AA-00003 is at depth 2.

Their running day sets entering the stage, and their priority and issue stamp:

| path | days | priority | issue stamp |
|---|---|---|---|
| AA-00001 | 1 June, 2 June, 3 June | 4 | 2030-01-02T08:00:00Z |
| AA-00002 | 2 June, 3 June, 4 June | 4 | 2030-01-05T08:00:00Z |
| AA-00003 | 3 June, 4 June, 5 June | 2 | 2030-01-09T08:00:00Z |

Two edges exist. The edge whose base is AA-00001 has a base at depth 0 and is
taken first; the edge whose base is AA-00002 has a base at depth 1 and is taken
second.

The first edge shares 2 June and 3 June. The priorities tie at 4, so the later
issue stamp decides and AA-00002 wins. AA-00001 keeps 1 June alone and loses
two days.

The second edge shares the days both still hold. AA-00002 holds 2 June, 3 June
and 4 June and AA-00003 holds 3 June, 4 June and 5 June, so the shared days are
3 June and 4 June. AA-00002 has the higher priority and wins, so AA-00003 keeps
5 June alone and loses two days.

The result: AA-00001 keeps one day, AA-00002 keeps three and AA-00003 keeps one.
Had the second edge been taken first, AA-00002 would have entered the first edge
with a different day set and the answer would have moved, which is why the edge
order is part of the contract.

## A cycle

BB-00001 names BB-00002 as its base and BB-00002 names BB-00001. Following the
bases from BB-00001 reaches BB-00001 again, so both paths sit on a cycle. Both
are rejected, both run on no date, both report a chain root of their own
identifier and a chain depth of 0, and both lose every day they entered the
stage with. Neither one wins and neither one is chosen as the survivor.
"""

WORKED_SLICE = """# Worked reference slice

A complete compile of a tiny invented extract, stage by stage, so every stage
can be checked against arithmetic before the real extract is compiled. None of
the identifiers or figures below belong to this extract.

## The slice

One operator, OP-01, rank weight 3. One zone, Z-ONE, whose transition table
holds a single row: at 2030-03-31T01:00:00Z the offset grows from 0 to 3600.
One section, SEC-01, class mainline, zone Z-ONE. One route, RT-01, whose only
leg is SEC-01 at offset 0. The minimum headway in force for mainline is 15
minutes, the deferral step is 6 minutes and the maximum is 2 deferrals.

One rule, RL-01: `freq` month, `anchor` 2030-03-04, `byday` [1], `bymonthday`
empty, `setpos` [1, -1], `limit` 3, `horizon_periods` 2.

Two paths:

| path | rule | depart | valid_from | valid_to | priority | issue stamp | variant_of |
|---|---|---|---|---|---|---|---|
| PP-00001 | RL-01 | 01:30 | 2030-03-01 | 2030-04-30 | 4 | 2030-01-01T08:00:00Z | |
| PP-00002 | RL-01 | 01:45 | 2030-03-01 | 2030-04-30 | 4 | 2030-02-01T08:00:00Z | pp 00001 |

One exception row: PP-00001, 2030-03-25, exclude. One alias row: OLD-00001 to
PP-00002. No superseded field matters in a slice this small.

## Stage 1

`pp 00001` canonicalises to PP-00001. No alias row retires PP-00001 or
PP-00002, so both resolve to themselves. Both are registered, nothing is on a
cycle, and the one alias row retires OLD-00001, which no file outside the alias
map mentions, so no spelling resolved through an alias.

## Stage 3

Period 0 is March 2030. Its Mondays are 2030-03-04, 2030-03-11, 2030-03-18 and
2030-03-25, a candidate set of four. Position 1 selects 2030-03-04 and position
-1 selects 2030-03-25. Period 1 is April 2030. Its Mondays are 2030-04-01,
2030-04-08, 2030-04-15, 2030-04-22 and 2030-04-29, a candidate set of five.
Position 1 selects 2030-04-01 and position -1 selects 2030-04-29.

Both paths select 2030-03-04, 2030-03-25, 2030-04-01 and 2030-04-29. The
candidate count is nine for each and the selected count is four.

## Stage 4

PP-00001 carries one exclusion on 2030-03-25, which was selected, so it is
removed. Its merged sequence is 2030-03-04, 2030-04-01 and 2030-04-29, three
dates. The cap of 3 keeps all three. The window keeps all three.

PP-00002 carries no exception. Its merged sequence is the four selected dates.
The cap of 3 keeps 2030-03-04, 2030-03-25 and 2030-04-01 and drops 2030-04-29,
so PP-00002 is cap bound. The window keeps the three that survived.

Note the order: had the cap run before the exclusion, PP-00001 would have kept
2030-03-04, 2030-03-25 and 2030-04-01, then dropped 2030-03-25, and ended with
two dates rather than three.

## Stage 5

PP-00002 names PP-00001 as its base, so PP-00001 is the chain root at depth 0
and PP-00002 is at depth 1. One edge. The shared days are 2030-03-04 and
2030-04-01. The priorities tie at 4, so the later issue stamp decides and
PP-00002 wins. PP-00001 keeps 2030-04-29 alone, losing two days. PP-00002 keeps
all three.

## Stage 6

Z-ONE has distinct offsets 0 and 3600. For 2030-04-29 at 01:30 only offset 3600
gives a candidate, so PP-00001 departs at 2030-04-29T00:30:00Z. PP-00002
departs at 2030-03-04T01:30:00Z under offset 0, at 2030-03-25T01:30:00Z under
offset 0, and at 2030-04-01T00:45:00Z under offset 3600. No reading of either
path sits in a gap or a fold here, so both counts are zero and no minute is
shifted. One movement for PP-00001 and three for PP-00002, four in total.

## Stage 7

The walk order is rank weight 3 for both, then priority 4 for both, then the
identifier, so PP-00001 comes before PP-00002, and inside each path the service
date ascends. Four movements:

1. PP-00001 on 2030-04-29, entry 2030-04-29T00:30:00Z. The section is empty, so
   count 0 clears. Admitted, deferral 0.
2. PP-00002 on 2030-03-04, entry 2030-03-04T01:30:00Z. Fifty six days from the
   only admitted entry, so count 0 clears. Admitted, deferral 0.
3. PP-00002 on 2030-03-25, entry 2030-03-25T01:30:00Z. Count 0 clears.
   Admitted, deferral 0.
4. PP-00002 on 2030-04-01, entry 2030-04-01T00:45:00Z. Count 0 clears.
   Admitted, deferral 0.

Four admitted, none deferred, none withheld, four entries on SEC-01.

## Stage 8

PP-00001: one admitted day, zero deferred, zero withheld, zero deferral
minutes, and path minutes of one times the route span of 0, so 0. PP-00002:
three admitted days and path minutes of 0 as well, because this route spans no
minutes.

## Stage 9

PP-00001 has one admitted date, so its base day is 2030-04-29, its bit length
is 1 and bit 0 is set, which packs to the single byte 0x01 and the hex string
`01`. PP-00002 has 2030-03-04, 2030-03-25 and 2030-04-01. Its base day is
2030-03-04, the latest is 2030-04-01, which is 28 days later, so the bit length
is 29. Bits 0, 21 and 28 are set. Byte 0 holds bit 0, so it is 0x01. Byte 1
holds bits 8 to 15, none set, so 0x00. Byte 2 holds bits 16 to 23 and bit 21 is
the value 32 bit, so 0x20. Byte 3 holds bits 24 to 31 and bit 28 is the value 16
bit, so 0x10. The hex string is `01002010`. The set bit total over both paths is
four.

## Stage 10

The paths in identifier order are PP-00001 at position 1 and PP-00002 at
position 2. The value of PP-00001 is 1 times 1000 plus 0, so 1000, and its term
is 1 times 1000, so 1000. The value of PP-00002 is 3 times 1000 plus 0, so
3000, and its term is 2 times 3000, so 6000. The digest is 7000 modulo
2147483647, so 7000.
"""

GLOSSARY = """# Glossary

- **admitted movement**: a movement that cleared the headway ladder of stage 7.
- **base**: the path a variant names in its `variant_of` column.
- **candidate set**: the days of one period that satisfy a rule's `byday` and
  `bymonthday` conditions.
- **canonical identifier**: the single spelling of a path identifier that stage
  1 defines.
- **chain depth**: the number of bases between a path and its chain root.
- **chain root**: the path at the end of a path's base chain.
- **deferral**: a whole number of deferral steps added to every entry instant
  of one movement.
- **entry instant**: the UTC instant at which a movement reaches one section.
- **fold**: a local wall clock reading that two UTC instants name.
- **gap**: a local wall clock reading that no UTC instant names.
- **movement**: one path on one running day.
- **path minutes**: the admitted movement count of a path multiplied by the span
  of its route.
- **registered path**: a register row whose identifier is not on an alias cycle.
- **rejected path**: a path on a variant cycle, which runs on no date.
- **route span**: the largest section offset of a route, in minutes.
- **running day set**: the days a path runs on, after the stage it is named in.
- **service date**: the running day a movement's departure was taken from.
- **superseded file**: a file that carries a field it does not decide.
- **withheld movement**: a movement no deferral count cleared.
"""

KNOWN_ISSUES = """# Known issues

Operator notes kept with the extract. None of this changes the contract; it
records what the compile desk has already found.

1. The compiler in the repository is the 4.2 build and its last run stopped
   before the digest stage. Its partial output was kept as
   `legacy_compiled_output.json`. The figures in that file disagree with the
   rulebook in several places and it is kept only so the two can be compared.
2. The 4.2 build is known to disagree with the rulebook. The compile desk has
   not written down where, and reading the rulebook against the code is the way
   to find out. Treat the code as the thing under repair and the rulebook as
   the authority, never the other way round.
3. Several faults in the 4.2 build leave this extract's output unchanged and
   only show on other periods, because this period happens to miss the cases
   they govern. Reproducing this extract is therefore not proof that the compile
   is right.
4. The previous issue of the path register, the unapproved rule draft and the
   proposed transition table were all left in the extract by the archiver.
   `file_role_index.md` is the only place that says which copy decides.
5. The mailbox carries more than one headway message. Only the approved prefix
   changes a value.
6. The debug log of the aborted run is kept for operators. It names a warning
   for an alias walk and a warning for a local departure with no instant; both
   are ordinary and the rulebook says what to do with each.
"""

DOCUMENTS = {
    "timetable_rulebook.md": RULEBOOK,
    "report_schema.md": SCHEMA,
    "file_role_index.md": ROLE_INDEX,
    "recurrence_primer.md": RECURRENCE_PRIMER,
    "zone_primer.md": ZONE_PRIMER,
    "headway_primer.md": HEADWAY_PRIMER,
    "overlay_primer.md": OVERLAY_PRIMER,
    "worked_reference_slice.md": WORKED_SLICE,
    "glossary.md": GLOSSARY,
    "known_issues.md": KNOWN_ISSUES,
}


# ---------------------------------------------------------------------------
# Part 2: compiling one extract from the model objects, with no file parsing.
# ---------------------------------------------------------------------------
SOURCES_OF_RECORD = {
    "departure_window": "path_register.csv",
    "operator_rank_weight": "operator_register.html",
    "recurrence_rule": "recurrence_rules.json",
    "section_headway": "wtt_mailbox.mbox",
    "zone_transition": "zone_transitions.csv",
}
SUPERSEDED_FILE_COUNT = 4


def period_bounds(rule: dict, index: int) -> tuple[int, int]:
    if rule["freq"] == "month":
        year, month = month_of(rule["anchor"])
        year, month = add_months(year, month, index)
        return month_bounds(year, month)
    if rule["freq"] == "isoweek":
        start = isoweek_start(rule["anchor"]) + 7 * index
        return start, start + 6
    start = rule["anchor"] + 28 * index
    return start, start + 27


def period_candidates(rule: dict, low: int, high: int) -> list[int]:
    if not rule["byday"] and not rule["bymonthday"]:
        return []
    days = []
    for ordinal in range(low, high + 1):
        if rule["byday"] and iso_weekday(ordinal) not in rule["byday"]:
            continue
        if rule["bymonthday"] and date.fromordinal(ordinal).day not in rule["bymonthday"]:
            continue
        days.append(ordinal)
    return days


def expand_rule(rule: dict) -> tuple[list[int], int, int]:
    chosen: set[int] = set()
    pool_total = 0
    periods = rule["horizon_periods"]
    for index in range(periods):
        pool = period_candidates(rule, *period_bounds(rule, index))
        pool_total += len(pool)
        for position in rule["setpos"]:
            slot = position - 1 if position > 0 else len(pool) + position
            if 0 <= slot < len(pool):
                chosen.add(pool[slot])
    return sorted(chosen), pool_total, periods


def offset_in_force(transitions: list[dict], instant: int) -> int:
    marks = [row["at_utc"] for row in transitions]
    slot = bisect.bisect_right(marks, instant)
    return transitions[slot - 1]["after"] if slot else transitions[0]["before"]


def resolve_wall(transitions: list[dict], wall: int) -> tuple[int, str, int]:
    pool = {transitions[0]["before"]} | {row["after"] for row in transitions}
    hits = sorted(wall - value for value in pool
                  if offset_in_force(transitions, wall - value) == value)
    if hits:
        return (hits[0], "single", 0) if len(hits) == 1 else (hits[-1], "fold", 0)
    widening = [row for row in transitions if row["after"] > row["before"]
                and row["at_utc"] + row["before"] <= wall < row["at_utc"] + row["after"]]
    if widening:
        grew = widening[0]
        return wall - grew["before"], "gap", (grew["after"] - grew["before"]) // MINUTE
    return wall - transitions[0]["before"], "single", 0


def _alias_table(model: Model) -> dict[str, str]:
    table: dict[str, str] = {}
    for row in model.aliases:
        retired = canonical_id(row["retired"])
        current = canonical_id(row["current"])
        if retired is not None and current is not None:
            table[retired] = current
    return table


def _walk(identifier: str, table: dict[str, str]) -> tuple[str | None, int, bool]:
    """Returns the resolution, the number of moves taken, and whether the walk
    returned to the identifier it started from."""
    seen = {identifier}
    cursor = identifier
    hops = 0
    while cursor in table and hops < 8:
        cursor = table[cursor]
        hops += 1
        if cursor in seen:
            return None, hops, cursor == identifier
        seen.add(cursor)
    return (None, hops, False) if cursor in table else (cursor, hops, False)


def derive(model: Model) -> dict[str, Any]:
    table = _alias_table(model)
    register_ids = [canonical_id(p["path_id"]) for p in model.paths]
    starts = sorted(set(table) | {pid for pid in register_ids if pid})
    on_cycle = set()
    for identifier in starts:
        _, _, returned = _walk(identifier, table)
        if returned:
            on_cycle.add(identifier)

    registered = [p for p in model.paths if canonical_id(p["path_id"]) not in on_cycle]
    by_id = {canonical_id(p["path_id"]): p for p in registered}
    registered_ids = sorted(by_id)

    # -- stage 1 reporting -------------------------------------------------
    spellings = sorted({row["spelling"] for row in model.exceptions}
                       | {p["variant_of"] for p in model.paths if p["variant_of"]})
    malformed: list[str] = []
    unresolved: list[str] = []
    through_alias = 0
    for spelling in spellings:
        start = canonical_id(spelling)
        if start is None:
            malformed.append(spelling)
            continue
        target, moves, _ = _walk(start, table)
        if target is None:
            unresolved.append(spelling)
            continue
        if moves > 0 and target in by_id:
            through_alias += 1
    identity = {
        "alias_row_count": len(model.aliases),
        "canonical_path_count": len(registered),
        "malformed_spellings": sorted(malformed),
        "rejected_cycle_members": sorted(on_cycle),
        "resolved_through_alias_count": through_alias,
        "unresolved_spellings": sorted(unresolved),
    }

    # -- stage 2 -----------------------------------------------------------
    counts = model.divergences()
    authority = {
        "fields": [{"divergence_count": counts[name], "field": name,
                    "source_of_record": SOURCES_OF_RECORD[name]}
                   for name in sorted(SOURCES_OF_RECORD)],
        "superseded_file_count": SUPERSEDED_FILE_COUNT,
    }

    # -- stage 3 -----------------------------------------------------------
    rule_cache: dict[str, tuple[list[int], int, int]] = {}
    for rule in model.rules:
        rule_cache[rule["rule_id"]] = expand_rule(rule)
    expansion_rows = []
    empty_rules = set()
    selected_total = 0
    selected_days: dict[str, list[int]] = {}
    for path_id in registered_ids:
        path = by_id[path_id]
        days, candidate_total, periods = rule_cache[path["rule_id"]]
        selected_days[path_id] = list(days)
        selected_total += len(days)
        if not days:
            empty_rules.add(path["rule_id"])
        expansion_rows.append({
            "candidate_count": candidate_total,
            "first_selected": iso_day(days[0]) if days else None,
            "last_selected": iso_day(days[-1]) if days else None,
            "path_id": path_id, "period_count": periods,
            "rule_id": path["rule_id"], "selected_count": len(days),
        })
    expansion = {"paths": expansion_rows,
                 "rules_with_empty_selection": sorted(empty_rules),
                 "selected_total": selected_total}

    # -- stage 4 -----------------------------------------------------------
    excludes: dict[str, set[int]] = {pid: set() for pid in registered_ids}
    adds: dict[str, set[int]] = {pid: set() for pid in registered_ids}
    for row in model.exceptions:
        start = canonical_id(row["spelling"])
        if start is None:
            continue
        target, _, _ = _walk(start, table)
        if target is None or target not in by_id:
            continue
        (excludes if row["kind"] == "exclude" else adds)[target].add(row["day"])
    merge_rows = []
    dropped_total = 0
    cap_bound: list[str] = []
    window_days: dict[str, list[int]] = {}
    for path_id in registered_ids:
        path = by_id[path_id]
        rule = model.rule(path["rule_id"])
        base = set(selected_days[path_id])
        removed = len(base & excludes[path_id])
        base -= excludes[path_id]
        dropped = len(adds[path_id] & excludes[path_id])
        applied = (adds[path_id] - excludes[path_id]) - base
        base |= applied
        merged = sorted(base)
        pre_cap = len(merged)
        cap = rule["limit"]
        if cap > 0:
            merged = merged[:cap]
        if cap > 0 and pre_cap > cap:
            cap_bound.append(path_id)
        in_window = [day for day in merged
                     if path["valid_from"] <= day <= path["valid_to"]]
        window_days[path_id] = in_window
        dropped_total += dropped
        merge_rows.append({
            "added_count": len(applied), "cap": cap,
            "dropped_addition_count": dropped, "excluded_count": removed,
            "first_in_window": iso_day(in_window[0]) if in_window else None,
            "in_window_count": len(in_window),
            "last_in_window": iso_day(in_window[-1]) if in_window else None,
            "path_id": path_id, "post_cap_count": len(merged), "pre_cap_count": pre_cap,
        })
    merge = {"cap_bound_paths": sorted(cap_bound), "dropped_addition_total": dropped_total,
             "paths": merge_rows}

    # -- stage 5 -----------------------------------------------------------
    parent: dict[str, str] = {}
    for path_id in registered_ids:
        spelling = by_id[path_id]["variant_of"]
        if not spelling:
            continue
        start = canonical_id(spelling)
        if start is None:
            continue
        target, _, _ = _walk(start, table)
        if target is None or target not in by_id or target == path_id:
            continue
        parent[path_id] = target
    rejected: set[str] = set()
    for path_id in registered_ids:
        trail: list[str] = []
        cursor = path_id
        while cursor in parent:
            trail.append(cursor)
            cursor = parent[cursor]
            if cursor in trail:
                rejected.update(trail[trail.index(cursor):])
                break

    def chain_of(start: str) -> tuple[str, int]:
        if start in rejected:
            return start, 0
        cursor = start
        hops = 0
        while cursor in parent and cursor not in rejected:
            cursor = parent[cursor]
            hops += 1
        return cursor, hops

    roots: dict[str, str] = {}
    depths: dict[str, int] = {}
    for path_id in registered_ids:
        roots[path_id], depths[path_id] = chain_of(path_id)
    entered = {pid: len(window_days[pid]) for pid in registered_ids}
    live: dict[str, set[int]] = {pid: set() if pid in rejected else set(window_days[pid])
                                for pid in registered_ids}
    edges = [(parent[child], child) for child in registered_ids
             if child in parent and child not in rejected and parent[child] not in rejected]
    edges.sort(key=lambda edge: (depths[edge[0]], edge[0], edge[1]))
    for base_id, child_id in edges:
        shared = live[base_id] & live[child_id]
        if not shared:
            continue
        base_path, child_path = by_id[base_id], by_id[child_id]
        key_base = (base_path["priority"], base_path["issue_stamp"], [-ord(c) for c in base_id])
        key_child = (child_path["priority"], child_path["issue_stamp"],
                     [-ord(c) for c in child_id])
        winner, loser = (base_id, child_id) if key_base > key_child else (child_id, base_id)
        live[loser] -= shared
        del winner
    overlay_rows = []
    for path_id in registered_ids:
        overlay_rows.append({
            "chain_depth": depths[path_id], "chain_root": roots[path_id],
            "kept_day_count": len(live[path_id]),
            "lost_day_count": entered[path_id] - len(live[path_id]),
            "path_id": path_id,
        })
    overlay = {"edge_count": len(edges), "paths": overlay_rows,
               "rejected_cycle_paths": sorted(rejected)}

    # -- stage 6 -----------------------------------------------------------
    gap_count = fold_count = shifted_total = midnight_count = 0
    movements: dict[str, list[dict]] = {}
    point_rows = []
    gap_paths: set[str] = set()
    fold_paths: set[str] = set()
    for path_id in registered_ids:
        path = by_id[path_id]
        transitions = model.zone(path["zone_id"])["transitions"]
        legs = model.routes[path["route_id"]]
        rows = []
        for day in sorted(live[path_id]):
            wall = local_wall(day, path["depart_local_min"])
            instant, kind, shifted = resolve_wall(transitions, wall)
            if kind == "gap":
                gap_count += 1
                shifted_total += shifted
                gap_paths.add(path_id)
            elif kind == "fold":
                fold_count += 1
                fold_paths.add(path_id)
            entries = [(leg["section_id"], instant + leg["offset_min"] * MINUTE) for leg in legs]
            last = entries[-1][1]
            local_date = (last + offset_in_force(transitions, last)) // DAY + EPOCH_ORD
            if local_date > day:
                midnight_count += 1
            rows.append({"day": day, "instant": instant, "entries": entries})
        movements[path_id] = rows
        point_rows.append({
            "first_departure_utc": iso_instant(rows[0]["instant"]) if rows else None,
            "last_departure_utc": iso_instant(rows[-1]["instant"]) if rows else None,
            "movement_count": len(rows), "path_id": path_id,
        })
    points = {"fold_count": fold_count, "gap_count": gap_count,
              "midnight_crossing_count": midnight_count,
              "movement_total": sum(len(rows) for rows in movements.values()),
              "paths": point_rows, "shifted_minute_total": shifted_total}

    # -- stage 7 -----------------------------------------------------------
    applied = model.applied_headway()
    section_class = {s["section_id"]: s["section_class"] for s in model.sections}
    rank = {o["operator_id"]: o["rank_weight"] for o in model.operators}
    step = model.policy["deferral_step_min"]
    ladder = model.policy["max_deferrals"]
    order = sorted(((-rank[by_id[path_id]["operator_id"]], -by_id[path_id]["priority"],
                     path_id, row["day"], path_id, row)
                    for path_id in registered_ids for row in movements[path_id]),
                   key=lambda item: item[:4])
    admitted_by_section: dict[str, list[int]] = {s["section_id"]: [] for s in model.sections}
    histogram = {str(k): 0 for k in range(ladder + 1)}
    admitted_rows: dict[str, list[dict]] = {pid: [] for pid in registered_ids}
    withheld_rows: list[dict] = []
    for _, _, _, day, path_id, row in order:
        chosen = None
        for count in range(ladder + 1):
            shift = count * step * MINUTE
            clear = True
            for section_id, instant in row["entries"]:
                limit = applied[section_class[section_id]] * MINUTE
                moved = instant + shift
                for taken in admitted_by_section[section_id]:
                    if abs(moved - taken) < limit:
                        clear = False
                        break
                if not clear:
                    break
            if clear:
                chosen = count
                break
        if chosen is None:
            withheld_rows.append({"path_id": path_id, "reason": "headway",
                                  "service_date": iso_day(day)})
            continue
        shift = chosen * step * MINUTE
        for section_id, instant in row["entries"]:
            admitted_by_section[section_id].append(instant + shift)
        histogram[str(chosen)] += 1
        admitted_rows[path_id].append({"day": day, "deferral": chosen * step})
    headway = {
        "admitted_total": sum(len(rows) for rows in admitted_rows.values()),
        "deferral_histogram": histogram,
        "deferred_total": sum(1 for rows in admitted_rows.values()
                              for row in rows if row["deferral"] > 0),
        "section_admitted_counts": {section: len(taken)
                                    for section, taken in sorted(admitted_by_section.items())},
        "withheld_total": len(withheld_rows),
    }
    withheld_rows.sort(key=lambda row: (row["path_id"], row["service_date"]))
    withheld = {"movements": withheld_rows,
                "rejected_paths": [{"path_id": pid, "reason": "variant_cycle"}
                                   for pid in sorted(rejected)]}

    # -- stage 8 -----------------------------------------------------------
    withheld_by_path: dict[str, int] = {pid: 0 for pid in registered_ids}
    for row in withheld_rows:
        withheld_by_path[row["path_id"]] += 1
    timetable_rows = []
    minutes_total = 0
    for path_id in registered_ids:
        path = by_id[path_id]
        rows = admitted_rows[path_id]
        span = model.route_span(path["route_id"])
        minutes = len(rows) * span
        minutes_total += minutes
        timetable_rows.append({
            "admitted_day_count": len(rows),
            "deferral_minute_total": sum(row["deferral"] for row in rows),
            "deferred_day_count": sum(1 for row in rows if row["deferral"] > 0),
            "operator_id": path["operator_id"], "path_id": path_id,
            "path_minutes": minutes, "route_id": path["route_id"],
            "withheld_day_count": withheld_by_path[path_id], "zone_id": path["zone_id"],
        })
    timetable = {"admitted_movement_total": headway["admitted_total"],
                 "path_minutes_total": minutes_total, "paths": timetable_rows,
                 "withheld_movement_total": len(withheld_rows)}

    # -- stage 9 -----------------------------------------------------------
    calendars = []
    set_bits = 0
    for path_id in registered_ids:
        days = sorted(row["day"] for row in admitted_rows[path_id])
        if not days:
            calendars.append({"base_day": iso_day(by_id[path_id]["valid_from"]),
                              "bit_length": 0, "hex": "", "path_id": path_id})
            continue
        base = days[0]
        length = days[-1] - base + 1
        mask = 0
        for day in days:
            mask |= 1 << (day - base)
        set_bits += len(days)
        calendars.append({"base_day": iso_day(base), "bit_length": length,
                          "hex": mask.to_bytes((length + 7) // 8, "little").hex(),
                          "path_id": path_id})
    calendar_doc = {"calendars": calendars, "set_bit_total": set_bits}

    # -- stage 10 ----------------------------------------------------------
    values = [row["admitted_day_count"] * 1000 + row["deferral_minute_total"]
              for row in timetable_rows]
    terms = [{"position": place, "term": (place * amount) % DIGEST_MODULUS, "value": amount}
             for place, amount in enumerate(values, start=1)]
    digest = sum(item["term"] for item in terms) % DIGEST_MODULUS
    digest_doc = {"digest": digest, "leading_terms": terms[:3],
                  "modulus": DIGEST_MODULUS, "term_count": len(terms)}

    subjects: dict[str, list[str]] = {code: [] for code in QUALITY_CODES}
    subjects["ALIAS_CYCLE"] = sorted(on_cycle)
    subjects["CAP_BINDING"] = sorted(cap_bound)
    subjects["EMPTY_CALENDAR"] = sorted(row["path_id"] for row in timetable_rows
                                        if row["admitted_day_count"] == 0)
    subjects["FOLD_DEPARTURE"] = sorted(fold_paths)
    subjects["HEADWAY_WITHHELD"] = sorted({row["path_id"] for row in withheld_rows})
    subjects["UNRESOLVED_SPELLING"] = sorted(set(malformed) | set(unresolved))
    subjects["VARIANT_CYCLE"] = sorted(rejected)
    quality = {"issue_counts": {code: len(subjects[code]) for code in QUALITY_CODES},
               "issue_total": sum(len(subjects[code]) for code in QUALITY_CODES),
               "subjects": subjects}

    flags: list[tuple[str, str]] = []
    flags.extend((pid, "cap_binding") for pid in cap_bound)
    flags.extend((row["path_id"], "empty_calendar") for row in timetable_rows
                 if row["admitted_day_count"] == 0)
    flags.extend((pid, "fold_departure") for pid in fold_paths)
    flags.extend((pid, "gap_departure") for pid in gap_paths)
    flags.extend((pid, "variant_cycle") for pid in rejected)
    flags = sorted(set(flags))
    flagged_xml = ['<?xml version="1.0" encoding="utf-8"?>', f'<flagged count="{len(flags)}">']
    flagged_xml.extend(f'  <path id="{pid}" reason="{reason}"/>' for pid, reason in flags)
    flagged_xml.append("</flagged>")
    flagged_text = "\n".join(flagged_xml) + "\n"

    operator_rows = []
    for operator in sorted(model.operators, key=lambda o: o["operator_id"]):
        own = [row for row in timetable_rows if row["operator_id"] == operator["operator_id"]]
        operator_rows.append([operator["operator_id"], operator["rank_weight"], len(own),
                              sum(row["admitted_day_count"] for row in own),
                              sum(row["withheld_day_count"] for row in own),
                              sum(row["path_minutes"] for row in own)])
    operator_text = "\n".join(["\t".join(["operator_id", "rank_weight", "path_count",
                                          "admitted_movements", "withheld_movements",
                                          "path_minutes"])]
                              + ["\t".join(str(cell) for cell in row) for row in operator_rows]
                              ) + "\n"

    section_rows = []
    for section in sorted(model.sections, key=lambda s: s["section_id"]):
        section_rows.append([section["section_id"], section["section_class"], section["zone_id"],
                             applied[section["section_class"]],
                             headway["section_admitted_counts"][section["section_id"]]])
    section_text = "\n".join(["|".join(["section_id", "section_class", "zone_id",
                                        "min_headway_min", "admitted_entries"])]
                             + ["|".join(str(cell) for cell in row) for row in section_rows]
                             ) + "\n"

    path_rows = []
    for row in timetable_rows:
        path_rows.append([row["path_id"], row["operator_id"], by_id[row["path_id"]]["rule_id"],
                          row["admitted_day_count"], row["deferred_day_count"],
                          row["withheld_day_count"], row["path_minutes"]])
    path_text = "\n".join([",".join(["path_id", "operator_id", "rule_id", "admitted_days",
                                     "deferred_days", "withheld_days", "path_minutes"])]
                          + [",".join(str(cell) for cell in row) for row in path_rows]) + "\n"

    report_text = "\n".join([
        "# Working timetable compile report",
        f"period: {iso_day(model.period_start)} to {iso_day(model.period_end)}",
        f"paths registered: {len(registered)}",
        f"paths rejected: {len(rejected)}",
        f"movements admitted: {headway['admitted_total']}",
        f"movements deferred: {headway['deferred_total']}",
        f"movements withheld: {headway['withheld_total']}",
        f"gap departures: {gap_count}",
        f"fold departures: {fold_count}",
        f"set bits: {set_bits}",
        f"digest: {digest}",
        "status: complete",
    ]) + "\n"
    status_text = (f"compiled {len(registered)} paths {headway['admitted_total']} admitted "
                   f"{headway['withheld_total']} withheld digest {digest}\n")

    return {
        "identity_resolution.json": identity,
        "authority_resolution.json": authority,
        "expansion_audit.json": expansion,
        "exception_merge.json": merge,
        "overlay_resolution.json": overlay,
        "timepoint_materialization.json": points,
        "headway_resolution.json": headway,
        "withheld_paths.json": withheld,
        "compiled_timetable.json": timetable,
        "canonical_calendars.json": calendar_doc,
        "timetable_digest.json": digest_doc,
        "data_quality.json": quality,
        "operator_rollup.tsv": operator_text,
        "section_rollup.psv": section_text,
        "path_rollup.csv": path_text,
        "flagged_paths.xml": flagged_text,
        "compile_report.md": report_text,
        "run_status.txt": status_text,
    }


# ---------------------------------------------------------------------------
# Part 3a: running the submitted compiler against a generated extract.
# ---------------------------------------------------------------------------
_FIXTURES: dict[str, tuple[Path, dict]] = {}
_RUNS: dict[str, Path] = {}


def _seal(root: Path) -> None:
    for item in root.iterdir():
        item.chmod(0o644)
    root.chmod(0o755)
    for parent in [root.parent, *root.parent.parents]:
        try:
            parent.chmod(parent.stat().st_mode | 0o555)
        except OSError:
            break
        if str(parent) == "/tmp":
            break


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename
    it, so a program the agent wrote can land at mode 0600 (owner-only). The
    checks run that program as an unprivileged user, which then cannot open it,
    and a correct submission would score zero for a reason that has nothing to
    do with the task. The verifier runs as root, so widening the mode is always
    allowed here and it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        if path.is_dir():
            path.chmod(path.stat().st_mode | 0o555)
            for child in path.rglob("*"):
                child.chmod(child.stat().st_mode | (0o555 if child.is_dir() else 0o444))
        else:
            path.chmod(path.stat().st_mode | 0o444)
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        _grant_read(str(OUT))
        return [*_SETPRIV, *command]
    return command


def fixture(tag: str, seed: int, knobs: dict[str, Any] | None = None) -> tuple[Path, dict]:
    """A sealed generated extract plus its expected documents, built once."""
    if tag not in _FIXTURES:
        model = Model(seed, knobs)
        root = Path(tempfile.mkdtemp(prefix="wtt-" + tag + "-")) / "extract"
        write_corpus(root, model)
        _seal(root)
        _FIXTURES[tag] = (root, derive(model))
    return _FIXTURES[tag]


def run_program(tag: str, root: Path, suffix: str = "out", create: bool = True) -> Path:
    """Run the submitted compiler over one extract, unprivileged, once per tag.

    With create False the output directory is left absent and its parent is made
    writable, so the run has to create the directory itself.
    """
    key = tag + "/" + suffix
    if key not in _RUNS:
        target = root.parent / suffix
        if create:
            target.mkdir(parents=True, exist_ok=True)
            target.chmod(0o777)
            root.parent.chmod(0o755)
        else:
            root.parent.chmod(0o777)
        command = [sys.executable, str(ENTRY), "compile", str(root), str(target)]
        subprocess.run(_untrusted_command(command), check=True, timeout=600,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _RUNS[key] = target
    return _RUNS[key]


def submitted(directory: Path, name: str) -> Any:
    text = (directory / name).read_text(encoding="utf-8")
    return json.loads(text) if name.endswith(".json") else text


def flagged_shape(text: str) -> dict[str, Any]:
    root = ET.fromstring(text)
    return {"count": int(root.get("count", "-1")),
            "paths": [[child.get("id"), child.get("reason")] for child in root]}


def agree(directory: Path, expected: dict, names: list[str]) -> bool:
    for name in names:
        if name == "flagged_paths.xml":
            if flagged_shape(submitted(directory, name)) != flagged_shape(expected[name]):
                return False
        elif submitted(directory, name) != expected[name]:
            return False
    return True


def visible() -> tuple[Path, dict]:
    return fixture("visible", VISIBLE_SEED, {"traps": False})


def _program_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="replace")
                     for path in sorted(OUT.rglob("*.py")))


def _program_literals() -> str:
    """Every constant the delivered source evaluates, with comments and docstrings left out.

    A path or a total named in a comment or a module docstring is documentation
    and not a read, so the cheat probes that look for one search the literals
    the code actually carries rather than the raw file text.
    """
    parts: list[str] = []
    for path in sorted(OUT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError, ValueError):
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
            continue
        docstrings = set()
        for holder in ast.walk(tree):
            if isinstance(holder, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                   ast.AsyncFunctionDef)):
                first = next(iter(getattr(holder, "body", [])), None)
                if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                        and isinstance(first.value.value, str)):
                    docstrings.add(id(first.value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and id(node) not in docstrings:
                if isinstance(node.value, (str, int, float)):
                    parts.append(str(node.value))
    return "\n".join(parts)


def _output_text() -> str:
    parts = [_program_text()]
    for name in DOC_NAMES:
        path = OUT / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _holds(check) -> bool:
    try:
        return bool(check())
    except Exception:
        return False


def digest_tree(root: Path) -> dict[str, str]:
    return {item.name: str(zlib.crc32(item.read_bytes()))
            for item in sorted(root.iterdir()) if item.is_file()}


# ---------------------------------------------------------------------------
# Part 3b: the generated extracts each rule is graded on. Every one of them
# carries the whole documented rule set; a knob only turns one rule up.
# ---------------------------------------------------------------------------
SMALL = {"path_count": 60}
SPELLING_DRIFT = dict(SMALL)
ALIAS_DRIFT = dict(SMALL, **{"extra_aliases": [
    {"retired": "WTT-01007", "current": "OLD-06001"},
    {"retired": "OLD-06001", "current": "wtt 01007"},
    {"retired": "OLD-07001", "current": "old 07002"},
    {"retired": "OLD-07002", "current": "OLD_07003"},
    {"retired": "OLD-07003", "current": "OLD-07004"},
    {"retired": "OLD-07004", "current": "WTT-01007"},
    {"retired": "OLD-08001", "current": "OLD-08002"},
    {"retired": "OLD-08002", "current": "OLD-08003"},
    {"retired": "OLD-08003", "current": "OLD-08001"},
]})
MAILBOX_REVISION = dict(SMALL, **{"mailbox_mainline": 21})
NEGATIVE_POSITIONS = dict(SMALL, **{"setpos_mode": "negative"})
MONTH_DAY_RULES = dict(SMALL, **{"freq_mode": "monthday"})
ISOWEEK_RULES = dict(SMALL, **{"freq_mode": "isoweek"})
COLLIDING_EXCEPTIONS = dict(SMALL, **{"extra_exceptions": [
    {"spelling": "WTT-01007", "date": "2027-02-15", "kind": "add"},
    {"spelling": "WTT-01007", "date": "2027-02-15", "kind": "exclude"},
    {"spelling": "wtt 01014", "date": "2027-03-01", "kind": "add"},
    {"spelling": "WTT_01014", "date": "2027-03-01", "kind": "exclude"},
    {"spelling": "WTT-01021", "date": "2027-04-05", "kind": "add"},
    {"spelling": "WTT-01028", "date": "2027-04-12", "kind": "exclude"},
]})
TIGHT_CAPS = dict(SMALL, **{"limit_mode": "tight"})
LATE_WINDOWS = dict(SMALL, **{"limit_mode": "tight", "window_mode": "late"})
DEEP_VARIANTS = dict(SMALL, **{"variant_depth": 3})
VARIANT_CYCLES = dict(SMALL, **{"variant_depth": 4})
WIDE_HEADWAY = dict(SMALL, **{"headway_scale": 6})
PROBE_EXTRACT = {"path_count": 24}


def decoy_variant() -> tuple[Path, dict]:
    """The shipped extract with only its superseded files rewritten."""
    if "decoys" not in _FIXTURES:
        source, expected = visible()
        root = Path(tempfile.mkdtemp(prefix="wtt-decoys-")) / "extract"
        shutil.copytree(source, root)
        stub = Model(31, {"path_count": 12})
        write_rows(root / "path_register_prior.csv", PATH_HEADER,
                   _path_rows(stub.paths), ",")
        write_json(root / "recurrence_rules_draft.json", _rule_payload(stub.rules))
        write_rows(root / "zone_transitions_proposed.csv",
                   ["zone_id", "at_utc", "offset_before_sec", "offset_after_sec"],
                   [[ZONE_WEST, iso_instant(GAP_WEST + 99 * DAY), 0, 7200]], ",")
        legacy = _legacy_payload(stub)
        legacy["operator_rank_weight"] = {o["operator_id"]: 1 for o in stub.operators}
        write_json(root / "legacy_compiled_output.json", legacy)
        (root / "compiler_debug.log").write_text(
            "2027-01-02T04:00:00Z INFO trace rotated away\n", encoding="utf-8")
        _seal(root)
        _FIXTURES["decoys"] = (root, expected)
    return _FIXTURES["decoys"]


def private_copy(tag: str, knobs: dict[str, Any], seed: int) -> tuple[Path, dict]:
    """An extract nothing else runs against, for the tamper probes."""
    if tag not in _FIXTURES:
        model = Model(seed, knobs)
        root = Path(tempfile.mkdtemp(prefix="wtt-" + tag + "-")) / "extract"
        write_corpus(root, model)
        _seal(root)
        _FIXTURES[tag] = (root, derive(model))
    return _FIXTURES[tag]


# ---------------------------------------------------------------------------
# Part 3c: the graded checks.
# ---------------------------------------------------------------------------
IDENTITY = ["identity_resolution.json"]
AUTHORITY = ["authority_resolution.json"]
EXPANSION = ["expansion_audit.json"]
MERGE = ["exception_merge.json"]
OVERLAY = ["overlay_resolution.json"]
POINTS = ["timepoint_materialization.json"]
HEADWAY = ["headway_resolution.json"]
WITHHELD = ["withheld_paths.json"]
TIMETABLE = ["compiled_timetable.json"]
CALENDARS = ["canonical_calendars.json"]
DIGEST = ["timetable_digest.json"]
ROLLUPS = ["timetable_digest.json", "data_quality.json", "operator_rollup.tsv",
           "section_rollup.psv", "path_rollup.csv", "flagged_paths.xml",
           "compile_report.md", "run_status.txt"]


def _check_declared_outputs_are_present_and_canonical():
    """POSITIVE: the compiler and its engine are in place and every document is canonical."""
    assert ENTRY.is_file(), "missing the command line entry"
    assert ENGINE.is_file(), "missing the engine module"
    for name in DOC_NAMES:
        assert (OUT / name).is_file(), f"missing document {name}"
    for name in JSON_DOCS:
        text = (OUT / name).read_text(encoding="utf-8")
        assert isinstance(json.loads(text), dict), name
        assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n", name
    return True


def _check_shipped_extract_compiles_exactly():
    """POSITIVE: every document of the shipped extract matches the rulebook."""
    _, expected = visible()
    return agree(OUT, expected, DOC_NAMES)


def _check_canonical_path_form_merges_wire_spellings():
    """POSITIVE: drifted spellings reduce to one path and its exceptions land on it."""
    root, expected = fixture("spellings", CHALLENGE_SEED + 11, SPELLING_DRIFT)
    return agree(run_program("spellings", root), expected, IDENTITY + MERGE)


def _check_alias_chains_resolve_and_cycles_are_rejected():
    """POSITIVE: a four hop alias chain resolves and an added cycle is rejected."""
    root, expected = fixture("aliases", CHALLENGE_SEED + 23, ALIAS_DRIFT)
    return agree(run_program("aliases", root), expected, IDENTITY + MERGE)


def _check_authority_resolution_names_the_sources_of_record():
    """POSITIVE: the five sources of record and their divergence counts are exact."""
    root, expected = fixture("authority", CHALLENGE_SEED + 37, SMALL)
    return agree(run_program("authority", root), expected, AUTHORITY)


def _check_superseded_sources_change_no_compiled_figure():
    """POSITIVE: rewriting only the superseded files leaves every settled figure alone."""
    root, expected = decoy_variant()
    directory = run_program("decoys", root)
    return agree(directory, expected,
                 TIMETABLE + DIGEST + CALENDARS + HEADWAY + ["path_rollup.csv", "run_status.txt"])


def _check_approved_mailbox_headway_revision_is_applied():
    """POSITIVE: the approved mainline revision reaches the admission walk."""
    root, expected = fixture("mailbox", CHALLENGE_SEED + 41, MAILBOX_REVISION)
    directory = run_program("mailbox", root)
    return agree(directory, expected, HEADWAY + ["section_rollup.psv"])


def _check_set_positions_select_inside_each_period():
    """POSITIVE: a position reads its own period's candidate set."""
    root, expected = fixture("setpos", CHALLENGE_SEED + 53, SMALL)
    return agree(run_program("setpos", root), expected, EXPANSION)


def _check_positions_below_zero_count_from_the_period_end():
    """POSITIVE: every rule reading from the period end selects the right day."""
    root, expected = fixture("negpos", CHALLENGE_SEED + 59, NEGATIVE_POSITIONS)
    return agree(run_program("negpos", root), expected, EXPANSION)


def _check_month_day_rules_select_nothing_in_short_months():
    """POSITIVE: a day of month past the end of a month contributes no candidate."""
    root, expected = fixture("monthday", CHALLENGE_SEED + 67, MONTH_DAY_RULES)
    return agree(run_program("monthday", root), expected, EXPANSION)


def _check_iso_week_periods_use_the_week_numbering_year():
    """POSITIVE: week periods start on the Monday of the anchor's week."""
    root, expected = fixture("isoweek", CHALLENGE_SEED + 71, ISOWEEK_RULES)
    return agree(run_program("isoweek", root), expected, EXPANSION)


def _check_exclusions_outrank_additions_on_one_date():
    """POSITIVE: an addition colliding with an exclusion is dropped and counted."""
    root, expected = fixture("collide", CHALLENGE_SEED + 83, COLLIDING_EXCEPTIONS)
    return agree(run_program("collide", root), expected, MERGE)


def _check_the_cap_counts_after_the_exclusions():
    """POSITIVE: the cap lands on the merged sequence, not on the raw expansion."""
    root, expected = fixture("captight", CHALLENGE_SEED + 89, TIGHT_CAPS)
    return agree(run_program("captight", root), expected, MERGE)


def _check_the_cap_counts_from_the_rule_anchor():
    """POSITIVE: a window opening long after the anchor still caps from the anchor."""
    root, expected = fixture("late", CHALLENGE_SEED + 97, LATE_WINDOWS)
    return agree(run_program("late", root), expected, MERGE)


def _check_variant_precedence_follows_priority_then_stamp():
    """POSITIVE: a three deep chain resolves edge by edge from the root outward."""
    root, expected = fixture("variants", CHALLENGE_SEED + 101, DEEP_VARIANTS)
    return agree(run_program("variants", root), expected, OVERLAY)


def _check_supersession_chains_resolve_and_cycles_are_rejected():
    """POSITIVE: a variant cycle rejects both members and they run on no date."""
    root, expected = fixture("cycles", CHALLENGE_SEED + 103, VARIANT_CYCLES)
    return agree(run_program("cycles", root), expected, OVERLAY)


def _check_gap_departures_shift_forward_by_the_gap():
    """POSITIVE: a local reading with no instant moves forward by the gap length."""
    root, expected = fixture("gaps", CHALLENGE_SEED + 107, SMALL)
    return agree(run_program("gaps", root), expected, POINTS)


def _check_fold_departures_take_the_later_offset():
    """POSITIVE: a local reading naming two instants takes the later one."""
    root, expected = fixture("folds", CHALLENGE_SEED + 109, SMALL)
    return agree(run_program("folds", root), expected, POINTS)


def _check_midnight_crossings_keep_the_service_date():
    """POSITIVE: a route running past local midnight keeps the departure date."""
    root, expected = fixture("midnight", CHALLENGE_SEED + 113, SMALL)
    return agree(run_program("midnight", root), expected, POINTS)


def _check_a_gap_equal_to_the_minimum_headway_clears():
    """POSITIVE: a gap exactly at the minimum is admitted rather than deferred."""
    root, expected = fixture("tie", CHALLENGE_SEED + 127, SMALL)
    return agree(run_program("tie", root), expected, HEADWAY)


def _check_the_deferral_ladder_stops_at_the_first_clearing_step():
    """POSITIVE: the histogram and the deferral minutes follow the first clearing count."""
    root, expected = fixture("defer", CHALLENGE_SEED + 131, SMALL)
    return agree(run_program("defer", root), expected, HEADWAY)


def _check_the_admission_walk_follows_the_canonical_order():
    """POSITIVE: the rank, priority, identifier and date order decides who is admitted."""
    root, expected = fixture("order", CHALLENGE_SEED + 137, SMALL)
    return agree(run_program("order", root), expected, HEADWAY + WITHHELD)


def _check_movements_that_never_clear_are_withheld():
    """POSITIVE: with the headway widened the withheld list and the reasons are exact."""
    root, expected = fixture("withhold", CHALLENGE_SEED + 139, WIDE_HEADWAY)
    return agree(run_program("withhold", root), expected, WITHHELD + HEADWAY)


def _check_canonical_calendars_encode_the_admitted_days():
    """POSITIVE: every bit calendar carries the admitted days least significant bit first."""
    root, expected = fixture("calendars", CHALLENGE_SEED + 149, SMALL)
    return agree(run_program("calendars", root), expected, CALENDARS)


def _check_rollups_and_the_digest_are_exact():
    """POSITIVE: the digest, the data quality document and the four rollups are exact."""
    root, expected = fixture("rollups", CHALLENGE_SEED + 151, SMALL)
    return agree(run_program("rollups", root), expected, ROLLUPS)


# The held-out tier. Each instance is a complete extract the agent never saw,
# generated from its own seed and its own fault profile, with the reference
# computed here from the published rulebook. Each is registered at its own
# weight so partial generalisation scores partially: a compiler that settles
# the shipped extract but only some unseen ones earns part of this tier rather
# than all or none of it.
UNSEEN_PROFILES: list[tuple[str, int, dict[str, Any]]] = [
    # 01 keeps the default profile: every fault class present at full size.
    ("01", EVAL_SEED, {}),
    # 02 drops the traps, so the plain recurrence path must still be exact.
    ("02", EVAL_SEED + 1181, {"traps": False}),
    # 03 pushes every window late, so the cap counts from the anchor throughout.
    ("03", EVAL_SEED + 2357, {"window_mode": "late", "limit_mode": "tight"}),
    # 04 makes every position negative and every period a month day.
    ("04", EVAL_SEED + 3511, {"setpos_mode": "negative", "freq_mode": "monthday"}),
    # 05 deepens the variant chains and keeps the cycle.
    ("05", EVAL_SEED + 4703, {"variant_depth": 4, "variant_cycle": True}),
    # 06 widens the headway so the deferral ladder and withheld list carry it.
    ("06", EVAL_SEED + 5897, {"headway_scale": 3, "mailbox_mainline": 25}),
    # 07 removes the zone folds but keeps midnight crossings and short months.
    ("07", EVAL_SEED + 7013, {"fold": False, "midnight": True, "short_month": True}),
    # 08 is a small extract with no limit at all, so nothing is capped.
    ("08", EVAL_SEED + 8209, {"path_count": 40, "limit_mode": "none"}),
    # 09 reads every position from the end of an ISO week period.
    ("09", EVAL_SEED + 9391, {"setpos_mode": "negative", "freq_mode": "isoweek"}),
    # 10 puts tight caps and late windows on week periods at once.
    ("10", EVAL_SEED + 10567, {"freq_mode": "isoweek", "limit_mode": "tight",
                               "window_mode": "late"}),
    # 11 drives month day rules through the short months with positive positions only.
    ("11", EVAL_SEED + 11743, {"setpos_mode": "positive", "freq_mode": "monthday",
                               "short_month": True}),
    # 12 widens the headway far enough that the ladder never clears for many movements.
    ("12", EVAL_SEED + 12919, {"headway_scale": 6, "conflict_pairs": True}),
    # 13 approves a mainline headway below the policy value, so the revision lowers it.
    ("13", EVAL_SEED + 14101, {"headway_scale": 1, "mailbox_mainline": 9}),
    # 14 builds variant chains five deep with no cycle in them.
    ("14", EVAL_SEED + 15287, {"variant_depth": 5}),
    # 15 puts a variant cycle in a smaller extract.
    ("15", EVAL_SEED + 16463, {"variant_cycle": True, "variant_depth": 2,
                               "path_count": 48}),
    # 16 carries a long alias chain and a cycle beside it.
    ("16", EVAL_SEED + 17639, {"alias_cycle": True, "extra_aliases": [
        {"retired": "OLD-05001", "current": "old 05002"},
        {"retired": "OLD-05002", "current": "OLD_05003"},
        {"retired": "OLD-05003", "current": "OLD-05004"},
        {"retired": "OLD-05004", "current": "WTT-01014"},
    ]}),
    # 17 lands folds and midnight crossings in the same compile.
    ("17", EVAL_SEED + 18811, {"fold": True, "midnight": True, "path_count": 72}),
    # 18 lets the cap bite on selections read from the period end.
    ("18", EVAL_SEED + 19993, {"limit_mode": "tight", "setpos_mode": "negative"}),
    # 19 is a larger extract at the default fault profile.
    ("19", EVAL_SEED + 21169, {"path_count": 120, "limit_mode": "mixed"}),
    # 20 takes month day rules with no cap and every window opening late.
    ("20", EVAL_SEED + 22343, {"freq_mode": "monthday", "limit_mode": "none",
                               "window_mode": "late"}),
    # 21 adds exception rows that collide on one date through drifted spellings.
    ("21", EVAL_SEED + 23521, {"extra_exceptions": [
        {"spelling": "WTT-01035", "date": "2027-02-11", "kind": "add"},
        {"spelling": "wtt 01035", "date": "2027-02-11", "kind": "exclude"},
        {"spelling": "WTT_01042", "date": "2027-03-08", "kind": "add"},
        {"spelling": "wtt01042", "date": "2027-03-08", "kind": "exclude"},
        {"spelling": "WTT-01049", "date": "2027-04-19", "kind": "exclude"},
    ]}),
    # 22 stacks a wider headway, deeper chains and the zone folds together.
    ("22", EVAL_SEED + 24697, {"headway_scale": 2, "variant_depth": 3, "fold": True}),
    # 23 is a small extract reading week periods from the end under tight caps.
    ("23", EVAL_SEED + 25873, {"path_count": 32, "setpos_mode": "negative",
                               "freq_mode": "isoweek", "limit_mode": "tight"}),
    # 24 is the largest extract with the headway widened on top of every fault.
    ("24", EVAL_SEED + 27061, {"path_count": 144, "headway_scale": 4}),
]


def _check_unseen_instance(label: str, seed: int, knobs: dict[str, Any]):
    """POSITIVE: one held-out extract compiles exactly, every document."""
    tag = "unseen" + label
    root, expected = fixture(tag, seed, knobs)
    directory = run_program(tag, root, create=False)
    assert sorted(item.name for item in directory.iterdir()) == sorted(DOC_NAMES)
    return agree(directory, expected, DOC_NAMES)


def _check_negative_hardcoded_sample_answers():
    """NEGATIVE: holds when the submission carries the shipped extract's own answers."""
    _, expected = visible()
    digest = expected["timetable_digest.json"]
    timetable = expected["compiled_timetable.json"]
    tokens = [token for token in (str(digest["digest"]), str(timetable["path_minutes_total"]))
              if len(token) >= 7]
    text = _program_literals()
    return any(token in text for token in tokens)


def _check_negative_deliverable_names_the_grading_surface():
    """NEGATIVE: holds when a delivered file's own text names the verifier or its outputs."""
    lowered = _output_text().lower()
    return any(token in lowered for token in ("/tests", "test_output", "judge.toml",
                                              "reward.toml", "rewardkit"))


def _check_negative_writes_outside_the_argument_directories():
    """NEGATIVE: holds when a run changes its input directory or writes beside its output."""
    root, _ = private_copy("tamper", PROBE_EXTRACT, CHALLENGE_SEED + 157)
    target = root.parent / "tamper-out"
    target.mkdir(parents=True, exist_ok=True)
    target.chmod(0o777)
    before = digest_tree(root)
    siblings_before = {item.name for item in root.parent.iterdir()}
    command = [sys.executable, str(ENTRY), "compile", str(root), str(target)]
    subprocess.run(_untrusted_command(command), check=True, timeout=600,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    siblings_after = {item.name for item in root.parent.iterdir()}
    return digest_tree(root) != before or siblings_after != siblings_before


def _check_negative_nondeterministic_output():
    """NEGATIVE: holds when two runs over one extract disagree."""
    root, _ = visible()
    first = run_program("visible", root, "determinism-a")
    second = run_program("visible", root, "determinism-b")
    return any((first / name).read_bytes() != (second / name).read_bytes()
               for name in DOC_NAMES)


def _check_negative_filename_dependent_behaviour():
    """NEGATIVE: holds when renaming the input directory changes the documents."""
    root, _ = private_copy("rename", PROBE_EXTRACT, CHALLENGE_SEED + 163)
    clone = root.parent / "a-differently-named-extract"
    if not clone.exists():
        shutil.copytree(root, clone)
        _seal(clone)
    plain = run_program("rename", root, "rename-a")
    renamed = run_program("rename", clone, "rename-b")
    return any((plain / name).read_bytes() != (renamed / name).read_bytes()
               for name in DOC_NAMES)


def _check_negative_reads_training_corpus_at_runtime():
    """NEGATIVE: holds when the compiler names the shipped extract rather than its argument."""
    # The mount is derived rather than written out: nothing under tests/ may
    # name an agent input path, which does not exist in the verifier container.
    shipped = str(OUT.parent / ("w" + "tt"))
    return shipped in _program_literals()


def _check_negative_rebinds_verifier_dependencies():
    """NEGATIVE: holds when the output directory holds a module that shadows an import."""
    shadowed = {"json", "csv", "html", "mailbox", "xml", "zlib", "decimal", "pathlib",
                "subprocess", "datetime", "calendar", "sitecustomize", "usercustomize"}
    return any(path.stem in shadowed for path in OUT.glob("*.py"))


def _write_corpus(root: Path) -> None:
    write_corpus(root / ("w" + "tt"), Model(VISIBLE_SEED, {"traps": False}))


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))


@criterion(description="The compiler, its engine and every document are in place and canonical.")
def declared_outputs_are_present_and_canonical(workspace: Path) -> bool:
    return _holds(_check_declared_outputs_are_present_and_canonical)


@criterion(description="Every document of the shipped extract matches the rulebook exactly.")
def shipped_extract_compiles_exactly(workspace: Path) -> bool:
    return _holds(_check_shipped_extract_compiles_exactly)


@criterion(description="Drifted path spellings reduce to one identifier and carry their exceptions.")
def canonical_path_form_merges_wire_spellings(workspace: Path) -> bool:
    return _holds(_check_canonical_path_form_merges_wire_spellings)


@criterion(description="A four hop alias chain resolves and an added alias cycle is rejected.")
def alias_chains_resolve_and_cycles_are_rejected(workspace: Path) -> bool:
    return _holds(_check_alias_chains_resolve_and_cycles_are_rejected)


@criterion(description="The five sources of record and their divergence counts are exact.")
def authority_resolution_names_the_sources_of_record(workspace: Path) -> bool:
    return _holds(_check_authority_resolution_names_the_sources_of_record)


@criterion(description="Rewriting only the superseded files leaves the compile unchanged.")
def superseded_sources_change_no_compiled_figure(workspace: Path) -> bool:
    return _holds(_check_superseded_sources_change_no_compiled_figure)


@criterion(description="The approved mainline headway revision reaches the admission walk.")
def approved_mailbox_headway_revision_is_applied(workspace: Path) -> bool:
    return _holds(_check_approved_mailbox_headway_revision_is_applied)


@criterion(description="A set position reads the candidate set of its own period.")
def set_positions_select_inside_each_period(workspace: Path) -> bool:
    return _holds(_check_set_positions_select_inside_each_period)


@criterion(description="Positions below zero select from the end of the period's own set.")
def positions_below_zero_count_from_the_period_end(workspace: Path) -> bool:
    return _holds(_check_positions_below_zero_count_from_the_period_end)


@criterion(description="A day of month past the end of a month contributes no candidate.")
def month_day_rules_select_nothing_in_short_months(workspace: Path) -> bool:
    return _holds(_check_month_day_rules_select_nothing_in_short_months)


@criterion(description="Week periods start on the Monday of the week holding the anchor.")
def iso_week_periods_use_the_week_numbering_year(workspace: Path) -> bool:
    return _holds(_check_iso_week_periods_use_the_week_numbering_year)


@criterion(description="An addition colliding with an exclusion is dropped and counted.")
def exclusions_outrank_additions_on_one_date(workspace: Path) -> bool:
    return _holds(_check_exclusions_outrank_additions_on_one_date)


@criterion(description="The cap lands on the merged sequence rather than the raw expansion.")
def the_cap_counts_after_the_exclusions(workspace: Path) -> bool:
    return _holds(_check_the_cap_counts_after_the_exclusions)


@criterion(description="A window opening long after the anchor still caps from the anchor.")
def the_cap_counts_from_the_rule_anchor(workspace: Path) -> bool:
    return _holds(_check_the_cap_counts_from_the_rule_anchor)


@criterion(description="A three deep variant chain resolves edge by edge from the root.")
def variant_precedence_follows_priority_then_stamp(workspace: Path) -> bool:
    return _holds(_check_variant_precedence_follows_priority_then_stamp)


@criterion(description="A variant cycle rejects both members and they run on no date.")
def supersession_chains_resolve_and_cycles_are_rejected(workspace: Path) -> bool:
    return _holds(_check_supersession_chains_resolve_and_cycles_are_rejected)


@criterion(description="A local reading with no instant moves forward by the gap length.")
def gap_departures_shift_forward_by_the_gap(workspace: Path) -> bool:
    return _holds(_check_gap_departures_shift_forward_by_the_gap)


@criterion(description="A local reading naming two instants resolves to the later one.")
def fold_departures_take_the_later_offset(workspace: Path) -> bool:
    return _holds(_check_fold_departures_take_the_later_offset)


@criterion(description="A route running past local midnight keeps its departure date.")
def midnight_crossings_keep_the_service_date(workspace: Path) -> bool:
    return _holds(_check_midnight_crossings_keep_the_service_date)


@criterion(description="A gap exactly at the minimum headway is admitted rather than deferred.")
def a_gap_equal_to_the_minimum_headway_clears(workspace: Path) -> bool:
    return _holds(_check_a_gap_equal_to_the_minimum_headway_clears)


@criterion(description="The histogram and the deferral minutes follow the first clearing count.")
def the_deferral_ladder_stops_at_the_first_clearing_step(workspace: Path) -> bool:
    return _holds(_check_the_deferral_ladder_stops_at_the_first_clearing_step)


@criterion(description="The rank, priority, identifier and date order decides who is admitted.")
def the_admission_walk_follows_the_canonical_order(workspace: Path) -> bool:
    return _holds(_check_the_admission_walk_follows_the_canonical_order)


@criterion(description="With the headway widened the withheld list and its reasons are exact.")
def movements_that_never_clear_are_withheld(workspace: Path) -> bool:
    return _holds(_check_movements_that_never_clear_are_withheld)


@criterion(description="Every bit calendar carries the admitted days, lowest bit first.")
def canonical_calendars_encode_the_admitted_days(workspace: Path) -> bool:
    return _holds(_check_canonical_calendars_encode_the_admitted_days)


@criterion(description="The digest, the data quality document and the four rollups are exact.")
def rollups_and_the_digest_are_exact(workspace: Path) -> bool:
    return _holds(_check_rollups_and_the_digest_are_exact)


@criterion(description="The compiler settles unseen extract 01, every document exact.")
def unseen_extract_01_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[0]))


@criterion(description="The compiler settles unseen extract 02, every document exact.")
def unseen_extract_02_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[1]))


@criterion(description="The compiler settles unseen extract 03, every document exact.")
def unseen_extract_03_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[2]))


@criterion(description="The compiler settles unseen extract 04, every document exact.")
def unseen_extract_04_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[3]))


@criterion(description="The compiler settles unseen extract 05, every document exact.")
def unseen_extract_05_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[4]))


@criterion(description="The compiler settles unseen extract 06, every document exact.")
def unseen_extract_06_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[5]))


@criterion(description="The compiler settles unseen extract 07, every document exact.")
def unseen_extract_07_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[6]))


@criterion(description="The compiler settles unseen extract 08, every document exact.")
def unseen_extract_08_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[7]))


@criterion(description="The compiler settles unseen extract 09, every document exact.")
def unseen_extract_09_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[8]))


@criterion(description="The compiler settles unseen extract 10, every document exact.")
def unseen_extract_10_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[9]))


@criterion(description="The compiler settles unseen extract 11, every document exact.")
def unseen_extract_11_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[10]))


@criterion(description="The compiler settles unseen extract 12, every document exact.")
def unseen_extract_12_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[11]))


@criterion(description="The compiler settles unseen extract 13, every document exact.")
def unseen_extract_13_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[12]))


@criterion(description="The compiler settles unseen extract 14, every document exact.")
def unseen_extract_14_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[13]))


@criterion(description="The compiler settles unseen extract 15, every document exact.")
def unseen_extract_15_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[14]))


@criterion(description="The compiler settles unseen extract 16, every document exact.")
def unseen_extract_16_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[15]))


@criterion(description="The compiler settles unseen extract 17, every document exact.")
def unseen_extract_17_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[16]))


@criterion(description="The compiler settles unseen extract 18, every document exact.")
def unseen_extract_18_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[17]))


@criterion(description="The compiler settles unseen extract 19, every document exact.")
def unseen_extract_19_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[18]))


@criterion(description="The compiler settles unseen extract 20, every document exact.")
def unseen_extract_20_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[19]))


@criterion(description="The compiler settles unseen extract 21, every document exact.")
def unseen_extract_21_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[20]))


@criterion(description="The compiler settles unseen extract 22, every document exact.")
def unseen_extract_22_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[21]))


@criterion(description="The compiler settles unseen extract 23, every document exact.")
def unseen_extract_23_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[22]))


@criterion(description="The compiler settles unseen extract 24, every document exact.")
def unseen_extract_24_compiles_exactly(workspace: Path) -> bool:
    return _holds(lambda: _check_unseen_instance(*UNSEEN_PROFILES[23]))


@criterion(description="Catches a submission carrying the shipped extract's own compiled answers.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _holds(_check_negative_hardcoded_sample_answers)


@criterion(description="Catches a delivered file whose own text names the grading surface.")
def negative_deliverable_names_the_grading_surface(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _holds(_check_negative_deliverable_names_the_grading_surface)


@criterion(description="Catches a run that changes its input directory or writes beside its output.")
def negative_writes_outside_the_argument_directories(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _holds(_check_negative_writes_outside_the_argument_directories)


@criterion(description="Catches two runs over one extract disagreeing with each other.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _holds(_check_negative_nondeterministic_output)


@criterion(description="Catches documents that change when the input directory is renamed.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _holds(_check_negative_filename_dependent_behaviour)


@criterion(description="Catches a compiler reaching for the shipped extract rather than its argument.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _holds(_check_negative_reads_training_corpus_at_runtime)


@criterion(description="Catches an output directory holding a module that shadows a grading import.")
def negative_rebinds_verifier_dependencies(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _holds(_check_negative_rebinds_verifier_dependencies)


criteria.declared_outputs_are_present_and_canonical(weight=1)
criteria.shipped_extract_compiles_exactly(weight=5)
criteria.canonical_path_form_merges_wire_spellings(weight=3)
criteria.alias_chains_resolve_and_cycles_are_rejected(weight=3)
criteria.authority_resolution_names_the_sources_of_record(weight=3)
criteria.superseded_sources_change_no_compiled_figure(weight=3)
criteria.approved_mailbox_headway_revision_is_applied(weight=3)
criteria.set_positions_select_inside_each_period(weight=3)
criteria.positions_below_zero_count_from_the_period_end(weight=3)
criteria.month_day_rules_select_nothing_in_short_months(weight=3)
criteria.iso_week_periods_use_the_week_numbering_year(weight=3)
criteria.exclusions_outrank_additions_on_one_date(weight=3)
criteria.the_cap_counts_after_the_exclusions(weight=3)
criteria.the_cap_counts_from_the_rule_anchor(weight=3)
criteria.variant_precedence_follows_priority_then_stamp(weight=3)
criteria.supersession_chains_resolve_and_cycles_are_rejected(weight=3)
criteria.gap_departures_shift_forward_by_the_gap(weight=3)
criteria.fold_departures_take_the_later_offset(weight=3)
criteria.midnight_crossings_keep_the_service_date(weight=3)
criteria.a_gap_equal_to_the_minimum_headway_clears(weight=3)
criteria.the_deferral_ladder_stops_at_the_first_clearing_step(weight=3)
criteria.the_admission_walk_follows_the_canonical_order(weight=3)
criteria.movements_that_never_clear_are_withheld(weight=3)
criteria.canonical_calendars_encode_the_admitted_days(weight=3)
criteria.rollups_and_the_digest_are_exact(weight=3)
criteria.unseen_extract_01_compiles_exactly(weight=5)
criteria.unseen_extract_02_compiles_exactly(weight=5)
criteria.unseen_extract_03_compiles_exactly(weight=5)
criteria.unseen_extract_04_compiles_exactly(weight=5)
criteria.unseen_extract_05_compiles_exactly(weight=5)
criteria.unseen_extract_06_compiles_exactly(weight=5)
criteria.unseen_extract_07_compiles_exactly(weight=5)
criteria.unseen_extract_08_compiles_exactly(weight=5)
criteria.unseen_extract_09_compiles_exactly(weight=5)
criteria.unseen_extract_10_compiles_exactly(weight=5)
criteria.unseen_extract_11_compiles_exactly(weight=5)
criteria.unseen_extract_12_compiles_exactly(weight=5)
criteria.unseen_extract_13_compiles_exactly(weight=5)
criteria.unseen_extract_14_compiles_exactly(weight=5)
criteria.unseen_extract_15_compiles_exactly(weight=5)
criteria.unseen_extract_16_compiles_exactly(weight=5)
criteria.unseen_extract_17_compiles_exactly(weight=5)
criteria.unseen_extract_18_compiles_exactly(weight=5)
criteria.unseen_extract_19_compiles_exactly(weight=5)
criteria.unseen_extract_20_compiles_exactly(weight=5)
criteria.unseen_extract_21_compiles_exactly(weight=5)
criteria.unseen_extract_22_compiles_exactly(weight=5)
criteria.unseen_extract_23_compiles_exactly(weight=5)
criteria.unseen_extract_24_compiles_exactly(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_deliverable_names_the_grading_surface(weight=-3)
criteria.negative_writes_outside_the_argument_directories(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_reads_training_corpus_at_runtime(weight=-3)
criteria.negative_rebinds_verifier_dependencies(weight=-1)
