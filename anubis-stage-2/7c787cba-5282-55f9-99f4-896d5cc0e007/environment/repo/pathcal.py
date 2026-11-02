"""pathcal, the working timetable path calendar engine. Build 4.2.

This is the in house engine the compile desk runs. It reads one extract
directory, walks the compile stages and writes the output documents. The
reporting helpers at the bottom own the line shapes of the prose report and the
status line and have not changed since build 3.1.

Build 4.2 is the build whose last run stopped before the digest stage. It runs
to completion on the extracts the desk has tried since, and the desk has never
reconciled it against the rulebook.

Public entry point: compile_extract(data_dir, out_dir).
"""

from __future__ import annotations

import bisect
import csv
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

EPOCH_ORD = date(1970, 1, 1).toordinal()
DAY = 86400
MINUTE = 60
DIGEST_MODULUS = 2147483647

QUALITY_CODES = [
    "ALIAS_CYCLE",
    "CAP_BINDING",
    "EMPTY_CALENDAR",
    "FOLD_DEPARTURE",
    "HEADWAY_WITHHELD",
    "UNRESOLVED_SPELLING",
    "VARIANT_CYCLE",
]
SOURCES_OF_RECORD = {
    "departure_window": "path_register.csv",
    "operator_rank_weight": "operator_register.html",
    "recurrence_rule": "recurrence_rules.json",
    "section_headway": "wtt_mailbox.mbox",
    "zone_transition": "zone_transitions.csv",
}
SUPERSEDED_FILES = [
    "legacy_compiled_output.json",
    "path_register_prior.csv",
    "recurrence_rules_draft.json",
    "zone_transitions_proposed.csv",
]
ROW_TABLE = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL_TABLE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


# ---------------------------------------------------------------------------
# Small conversions.
# ---------------------------------------------------------------------------
def read_text(root: Path, name: str) -> str:
    return (root / name).read_text(encoding="utf-8")


def read_json(root: Path, name: str) -> Any:
    return json.loads(read_text(root, name))


def read_delimited(root: Path, name: str, delimiter: str = ",") -> list[dict[str, str]]:
    lines = read_text(root, name).splitlines()
    return list(csv.DictReader(lines, delimiter=delimiter))


def to_ordinal(text: str) -> int:
    return date.fromisoformat(text.strip()).toordinal()


def from_ordinal(ordinal: int) -> str:
    return date.fromordinal(ordinal).isoformat()


def to_instant(text: str) -> int:
    stamp = datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%SZ")
    return int(stamp.replace(tzinfo=timezone.utc).timestamp())


def from_instant(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def minutes_of_day(text: str) -> int:
    hours, minutes = text.strip().split(":")
    return int(hours) * 60 + int(minutes)


def wall_seconds(ordinal: int, minute_of_day: int) -> int:
    return (ordinal - EPOCH_ORD) * DAY + minute_of_day * MINUTE


def weekday_of(ordinal: int) -> int:
    return date.fromordinal(ordinal).isoweekday()


def day_of_month(ordinal: int) -> int:
    return date.fromordinal(ordinal).day


def shift_month(year: int, month: int, step: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + step
    return index // 12, index % 12 + 1


def month_span(year: int, month: int) -> tuple[int, int]:
    start = date(year, month, 1).toordinal()
    next_year, next_month = shift_month(year, month, 1)
    return start, date(next_year, next_month, 1).toordinal() - 1


def week_start(ordinal: int) -> int:
    return ordinal - (weekday_of(ordinal) - 1)


def canonical_identifier(spelling: str) -> str | None:
    """Reduce one spelling to the canonical identifier form."""
    kept = [character for character in spelling.upper()
            if ("A" <= character <= "Z") or ("0" <= character <= "9")]
    if not kept:
        return None
    letters = "".join(character for character in kept if "A" <= character <= "Z")
    digits = "".join(character for character in kept if "0" <= character <= "9")
    if not letters or not digits or kept != list(letters + digits) or len(digits) > 5:
        return None
    return letters + "-" + f"{int(digits):05d}"


# ---------------------------------------------------------------------------
# The extract.
# ---------------------------------------------------------------------------
class Extract:
    """The extract files, parsed into plain structures."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.period = read_json(root, "timetable_period.json")
        self.period_start = to_ordinal(self.period["period_start"])
        self.period_end = to_ordinal(self.period["period_end"])
        self.operators = self._read_operators()
        self.sections = self._read_sections()
        self.routes = self._read_routes()
        self.zones = self._read_zones()
        self.rules = self._read_rules()
        self.register = self._read_register()
        self.aliases = self._read_aliases()
        self.exceptions = self._read_exceptions()
        self.policy = read_json(root, "headway_policy.json")
        self.mailbox = self._read_mailbox()

    def _read_operators(self) -> list[dict[str, Any]]:
        text = read_text(self.root, "operator_register.html")
        operators = []
        for block in ROW_TABLE.findall(text):
            cells = [cell.strip() for cell in CELL_TABLE.findall(block)]
            if len(cells) == 3:
                operators.append({"operator_id": cells[0], "name": cells[1],
                                  "rank_weight": int(cells[2])})
        operators.sort(key=lambda row: row["operator_id"])
        return operators

    def _read_sections(self) -> dict[str, dict[str, str]]:
        sections = {}
        for row in read_delimited(self.root, "section_register.csv"):
            sections[row["section_id"]] = {"section_class": row["section_class"],
                                           "zone_id": row["zone_id"]}
        return sections

    def _read_routes(self) -> dict[str, list[tuple[str, int]]]:
        routes: dict[str, list[tuple[int, str, int]]] = {}
        for row in read_delimited(self.root, "section_route.psv", "|"):
            routes.setdefault(row["route_id"], []).append(
                (int(row["seq"]), row["section_id"], int(row["offset_min"])))
        return {route_id: [(section_id, offset) for _, section_id, offset in sorted(legs)]
                for route_id, legs in routes.items()}

    def _read_zones(self) -> dict[str, list[dict[str, int]]]:
        zones: dict[str, list[dict[str, int]]] = {}
        for row in read_delimited(self.root, "zone_transitions_proposed.csv"):
            zones.setdefault(row["zone_id"], []).append({
                "at_utc": to_instant(row["at_utc"]),
                "before": int(row["offset_before_sec"]),
                "after": int(row["offset_after_sec"])})
        for transitions in zones.values():
            transitions.sort(key=lambda row: row["at_utc"])
        return zones

    def _read_rules(self) -> dict[str, dict[str, Any]]:
        rules = {}
        for row in read_json(self.root, "recurrence_rules.json")["rules"]:
            rules[row["rule_id"]] = {
                "rule_id": row["rule_id"], "freq": row["freq"],
                "anchor": to_ordinal(row["anchor"]),
                "byday": sorted(int(value) for value in row["byday"]),
                "bymonthday": sorted(int(value) for value in row["bymonthday"]),
                "setpos": [int(value) for value in row["setpos"]],
                "limit": int(row["limit"]),
                "horizon_periods": int(row["horizon_periods"])}
        return rules

    def _read_register(self) -> list[dict[str, Any]]:
        register = []
        for row in read_delimited(self.root, "path_register.csv"):
            register.append({
                "path_id": row["path_id"], "operator_id": row["operator_id"],
                "zone_id": row["zone_id"], "rule_id": row["rule_id"],
                "route_id": row["route_id"],
                "depart_local_min": minutes_of_day(row["depart_local"]),
                "valid_from": to_ordinal(row["valid_from"]),
                "valid_to": to_ordinal(row["valid_to"]),
                "priority": int(row["priority"]), "issue_stamp": row["issue_stamp"],
                "variant_of": row["variant_of"].strip()})
        return register

    def _read_aliases(self) -> list[tuple[str, str]]:
        return [(row["retired_path"], row["current_path"])
                for row in read_delimited(self.root, "path_alias_map.csv")]

    def _read_exceptions(self) -> list[tuple[str, int, str]]:
        return [(row["path"], to_ordinal(row["date"]), row["kind"])
                for row in read_delimited(self.root, "exception_dates.csv")]

    def _read_mailbox(self) -> list[dict[str, Any]]:
        messages = []
        for line in read_text(self.root, "wtt_mailbox.mbox").splitlines():
            if not line.startswith("Subject:"):
                continue
            parts = line[len("Subject:"):].split()
            if len(parts) == 3:
                messages.append({"prefix": parts[0], "section_class": parts[1],
                                 "minutes": int(parts[2])})
        return messages

    # -- the other copies of the same fields -------------------------------
    def divergence_counts(self) -> dict[str, int]:
        prior = {row["path_id"]: row for row in read_delimited(
            self.root, "path_register_prior.csv")}
        live = {row["path_id"]: row for row in read_delimited(self.root, "path_register.csv")}
        departure = sum(1 for key, row in live.items() if key in prior
                        and (row["depart_local"] != prior[key]["depart_local"]
                             or row["valid_to"] != prior[key]["valid_to"]))
        draft = {row["rule_id"]: row
                 for row in read_json(self.root, "recurrence_rules_draft.json")["rules"]}
        current = {row["rule_id"]: row
                   for row in read_json(self.root, "recurrence_rules.json")["rules"]}
        rules = sum(1 for key, row in current.items() if key in draft
                    and (row["setpos"] != draft[key]["setpos"]
                         or row["limit"] != draft[key]["limit"]))
        known = {(row["zone_id"], row["at_utc"], row["offset_before_sec"],
                  row["offset_after_sec"])
                 for row in read_delimited(self.root, "zone_transitions.csv")}
        zones = sum(1 for row in read_delimited(self.root, "zone_transitions_proposed.csv")
                    if (row["zone_id"], row["at_utc"], row["offset_before_sec"],
                        row["offset_after_sec"]) not in known)
        headway = sum(1 for message in self.mailbox if message["prefix"] != "APPROVED-HEADWAY")
        legacy = read_json(self.root, "legacy_compiled_output.json").get(
            "operator_rank_weight", {})
        rank = sum(1 for operator in self.operators
                   if int(legacy.get(operator["operator_id"], -1)) != operator["rank_weight"])
        return {"departure_window": departure, "operator_rank_weight": rank,
                "recurrence_rule": rules, "section_headway": headway,
                "zone_transition": zones}

    def applied_headway(self) -> dict[str, int]:
        table = {name: int(value) for name, value in self.policy["min_headway_min"].items()}
        for message in self.mailbox:
            table[message["section_class"]] = message["minutes"]
        return table


# ---------------------------------------------------------------------------
# Identity.
# ---------------------------------------------------------------------------
class Identity:
    """The alias lookup and the paths it retires."""

    def __init__(self, extract: Extract) -> None:
        self.table: dict[str, str] = {}
        for retired, current in extract.aliases:
            left = canonical_identifier(retired)
            right = canonical_identifier(current)
            if left is not None and right is not None:
                self.table[left] = right
        self.on_cycle: set[str] = set()

    def walk(self, identifier: str) -> tuple[str | None, int, bool]:
        """Returns the resolution, the number of moves and whether it returned."""
        if identifier in self.table:
            return self.table[identifier], 1, False
        return identifier, 0, False

    def resolve(self, spelling: str) -> tuple[str | None, int, str]:
        start = canonical_identifier(spelling)
        if start is None:
            return None, 0, "malformed"
        target, moves, _ = self.walk(start)
        if target is None:
            return None, moves, "unresolved"
        return target, moves, "resolved"


# ---------------------------------------------------------------------------
# Rule expansion.
# ---------------------------------------------------------------------------
def period_window(rule: dict[str, Any], index: int) -> tuple[int, int]:
    if rule["freq"] == "month":
        anchor = date.fromordinal(rule["anchor"])
        year, month = shift_month(anchor.year, anchor.month, index)
        return month_span(year, month)
    if rule["freq"] == "isoweek":
        start = week_start(rule["anchor"]) + 7 * index
        return start, start + 6
    start = rule["anchor"] + 28 * index
    return start, start + 27


def candidates_in(rule: dict[str, Any], low: int, high: int) -> list[int]:
    if not rule["byday"] and not rule["bymonthday"]:
        return []
    found = []
    for ordinal in range(low, high + 1):
        if rule["byday"] and weekday_of(ordinal) not in rule["byday"]:
            continue
        if rule["bymonthday"] and day_of_month(ordinal) not in rule["bymonthday"]:
            continue
        found.append(ordinal)
    return found


def expand(rule: dict[str, Any]) -> tuple[list[int], int]:
    """The selected days of one rule and the total candidate count."""
    picked: set[int] = set()
    candidates: list[int] = []
    for index in range(rule["horizon_periods"]):
        low, high = period_window(rule, index)
        candidates.extend(candidates_in(rule, low, high))
    size = len(candidates)
    for position in rule["setpos"]:
        if position > 0:
            if position <= size:
                picked.add(candidates[position - 1])
        else:
            slot = size + position - 1
            if slot >= 0:
                picked.add(candidates[slot])
    return sorted(picked), size


# ---------------------------------------------------------------------------
# Local readings to instants.
# ---------------------------------------------------------------------------
def offset_at(transitions: list[dict[str, int]], instant: int) -> int:
    offset = transitions[0]["before"]
    for transition in transitions:
        if instant >= transition["at_utc"]:
            offset = transition["after"]
    return offset


def materialize(transitions: list[dict[str, int]], wall: int) -> tuple[int, str, int]:
    """The instant a local wall reading names, and how it was resolved."""
    offsets = sorted({transitions[0]["before"]} | {row["after"] for row in transitions})
    found = sorted({wall - offset for offset in offsets
                    if offset_at(transitions, wall - offset) == offset})
    if len(found) == 1:
        return found[0], "single", 0
    if len(found) > 1:
        return found[0], "fold", 0
    for transition in transitions:
        if transition["after"] <= transition["before"]:
            continue
        low = transition["at_utc"] + transition["before"]
        high = transition["at_utc"] + transition["after"]
        if low <= wall < high:
            gap = transition["after"] - transition["before"]
            return wall - transition["after"], "gap", gap // MINUTE
    return wall - transitions[0]["before"], "single", 0


# ---------------------------------------------------------------------------
# The compile itself.
# ---------------------------------------------------------------------------
class Compile:
    """The compile stages over one parsed extract."""

    def __init__(self, extract: Extract) -> None:
        self.extract = extract
        self.identity = Identity(extract)
        self.registered = [row for row in extract.register
                           if canonical_identifier(row["path_id"]) not in self.identity.on_cycle]
        self.by_id = {canonical_identifier(row["path_id"]): row for row in self.registered}
        self.path_ids = sorted(self.by_id)
        self.documents: dict[str, Any] = {}

    # -- identity ----------------------------------------------------------
    def stage_identity(self) -> None:
        spellings = sorted({spelling for spelling, _, _ in self.extract.exceptions}
                           | {row["variant_of"] for row in self.extract.register
                              if row["variant_of"]})
        malformed: list[str] = []
        unresolved: list[str] = []
        through_alias = 0
        for spelling in spellings:
            target, moves, outcome = self.identity.resolve(spelling)
            if outcome == "malformed":
                malformed.append(spelling)
            elif outcome == "unresolved":
                unresolved.append(spelling)
            elif moves > 0 and target in self.by_id:
                through_alias += 1
        self.documents["identity_resolution.json"] = {
            "alias_row_count": len(self.extract.aliases),
            "canonical_path_count": len(self.registered),
            "malformed_spellings": sorted(malformed),
            "rejected_cycle_members": sorted(self.identity.on_cycle),
            "resolved_through_alias_count": through_alias,
            "unresolved_spellings": sorted(unresolved),
        }
        self.malformed = sorted(malformed)
        self.unresolved = sorted(unresolved)

    # -- authority ---------------------------------------------------------
    def stage_authority(self) -> None:
        counts = self.extract.divergence_counts()
        self.documents["authority_resolution.json"] = {
            "fields": [{"divergence_count": counts[name], "field": name,
                        "source_of_record": SOURCES_OF_RECORD[name]}
                       for name in sorted(SOURCES_OF_RECORD)],
            "superseded_file_count": len(SUPERSEDED_FILES),
        }

    # -- expansion ---------------------------------------------------------
    def stage_expansion(self) -> None:
        cache: dict[str, tuple[list[int], int]] = {}
        for rule_id, rule in self.extract.rules.items():
            cache[rule_id] = expand(rule)
        rows = []
        empty: set[str] = set()
        total = 0
        self.selected: dict[str, list[int]] = {}
        for path_id in self.path_ids:
            path = self.by_id[path_id]
            days, candidate_total = cache[path["rule_id"]]
            rule = self.extract.rules[path["rule_id"]]
            self.selected[path_id] = list(days)
            total += len(days)
            if not days:
                empty.add(path["rule_id"])
            rows.append({
                "candidate_count": candidate_total,
                "first_selected": from_ordinal(days[0]) if days else None,
                "last_selected": from_ordinal(days[-1]) if days else None,
                "path_id": path_id, "period_count": rule["horizon_periods"],
                "rule_id": path["rule_id"], "selected_count": len(days)})
        self.documents["expansion_audit.json"] = {
            "paths": rows, "rules_with_empty_selection": sorted(empty),
            "selected_total": total}

    # -- exceptions --------------------------------------------------------
    def stage_exceptions(self) -> None:
        excludes: dict[str, set[int]] = {path_id: set() for path_id in self.path_ids}
        adds: dict[str, set[int]] = {path_id: set() for path_id in self.path_ids}
        for spelling, day, kind in self.extract.exceptions:
            target, _, outcome = self.identity.resolve(spelling)
            if outcome != "resolved" or target not in self.by_id:
                continue
            bucket = excludes if kind == "exclude" else adds
            bucket[target].add(day)
        rows = []
        dropped_total = 0
        self.cap_bound: list[str] = []
        self.window: dict[str, list[int]] = {}
        for path_id in self.path_ids:
            path = self.by_id[path_id]
            rule = self.extract.rules[path["rule_id"]]
            clipped = [day for day in self.selected[path_id]
                       if path["valid_from"] <= day <= path["valid_to"]]
            pre_cap = len(clipped)
            cap = rule["limit"]
            if cap > 0:
                clipped = clipped[:cap]
                if pre_cap > cap:
                    self.cap_bound.append(path_id)
            days = set(clipped)
            removed = len(days & excludes[path_id])
            days -= excludes[path_id]
            dropped = len(adds[path_id] & excludes[path_id])
            applied = (adds[path_id] - excludes[path_id]) - days
            days |= applied
            merged = sorted(days)
            in_window = list(merged)
            self.window[path_id] = in_window
            dropped_total += dropped
            rows.append({
                "added_count": len(applied), "cap": cap,
                "dropped_addition_count": dropped, "excluded_count": removed,
                "first_in_window": from_ordinal(in_window[0]) if in_window else None,
                "in_window_count": len(in_window),
                "last_in_window": from_ordinal(in_window[-1]) if in_window else None,
                "path_id": path_id, "post_cap_count": len(merged),
                "pre_cap_count": pre_cap})
        self.documents["exception_merge.json"] = {
            "cap_bound_paths": sorted(self.cap_bound),
            "dropped_addition_total": dropped_total, "paths": rows}

    # -- overlay -----------------------------------------------------------
    def stage_overlay(self) -> None:
        parent: dict[str, str] = {}
        for path_id in self.path_ids:
            spelling = self.by_id[path_id]["variant_of"]
            if not spelling:
                continue
            target, _, outcome = self.identity.resolve(spelling)
            if outcome != "resolved" or target not in self.by_id or target == path_id:
                continue
            parent[path_id] = target
        rejected: set[str] = set()
        roots: dict[str, str] = {}
        depths: dict[str, int] = {}
        for path_id in self.path_ids:
            depth = 0
            current = path_id
            while current in parent and depth < 8:
                current = parent[current]
                depth += 1
            roots[path_id] = current
            depths[path_id] = depth
        entered = {path_id: len(self.window[path_id]) for path_id in self.path_ids}
        self.live = {path_id: (set() if path_id in rejected else set(self.window[path_id]))
                     for path_id in self.path_ids}
        edges = [(parent[child], child) for child in self.path_ids
                 if child in parent and child not in rejected
                 and parent[child] not in rejected]
        edges.sort(key=lambda edge: (depths[edge[0]], edge[0], edge[1]))
        for base_id, child_id in edges:
            shared = self.live[base_id] & self.live[child_id]
            if not shared:
                continue
            if self._wins(base_id, child_id):
                self.live[child_id] -= shared
            else:
                self.live[base_id] -= shared
        self.rejected = rejected
        self.documents["overlay_resolution.json"] = {
            "edge_count": len(edges),
            "paths": [{"chain_depth": depths[path_id], "chain_root": roots[path_id],
                       "kept_day_count": len(self.live[path_id]),
                       "lost_day_count": entered[path_id] - len(self.live[path_id]),
                       "path_id": path_id} for path_id in self.path_ids],
            "rejected_cycle_paths": sorted(rejected)}

    def _wins(self, left: str, right: str) -> bool:
        """True when the left path takes the shared days of the edge."""
        first, second = self.by_id[left], self.by_id[right]
        if first["issue_stamp"] != second["issue_stamp"]:
            return first["issue_stamp"] > second["issue_stamp"]
        if first["priority"] != second["priority"]:
            return first["priority"] > second["priority"]
        return left < right

    # -- timepoints --------------------------------------------------------
    def stage_timepoints(self) -> None:
        self.movements: dict[str, list[dict[str, Any]]] = {}
        self.gap_paths: set[str] = set()
        self.fold_paths: set[str] = set()
        gaps = folds = shifted = crossings = 0
        rows = []
        for path_id in self.path_ids:
            path = self.by_id[path_id]
            transitions = self.extract.zones[path["zone_id"]]
            legs = self.extract.routes[path["route_id"]]
            own = []
            for day in sorted(self.live[path_id]):
                wall = wall_seconds(day, path["depart_local_min"])
                instant, kind, minutes = materialize(transitions, wall)
                if kind == "gap":
                    gaps += 1
                    shifted += minutes
                    self.gap_paths.add(path_id)
                elif kind == "fold":
                    folds += 1
                    self.fold_paths.add(path_id)
                entries = [(section_id, instant + offset * MINUTE)
                           for section_id, offset in legs]
                last = entries[-1][1]
                utc_day = last // DAY + EPOCH_ORD
                if utc_day > day:
                    crossings += 1
                own.append({"day": day, "instant": instant, "entries": entries})
            self.movements[path_id] = own
            rows.append({
                "first_departure_utc": from_instant(own[0]["instant"]) if own else None,
                "last_departure_utc": from_instant(own[-1]["instant"]) if own else None,
                "movement_count": len(own), "path_id": path_id})
        self.gap_count = gaps
        self.fold_count = folds
        self.documents["timepoint_materialization.json"] = {
            "fold_count": folds, "gap_count": gaps,
            "midnight_crossing_count": crossings,
            "movement_total": sum(len(own) for own in self.movements.values()),
            "paths": rows, "shifted_minute_total": shifted}

    # -- headway -----------------------------------------------------------
    def stage_headway(self) -> None:
        applied = self.extract.applied_headway()
        rank = {row["operator_id"]: row["rank_weight"] for row in self.extract.operators}
        step = int(self.extract.policy["deferral_step_min"])
        ladder = int(self.extract.policy["max_deferrals"])
        walk = []
        for path_id in self.path_ids:
            path = self.by_id[path_id]
            for movement in self.movements[path_id]:
                walk.append((-rank[path["operator_id"]], -path["priority"], path_id,
                             movement["day"], movement))
        walk.sort(key=lambda item: (item[2], item[3]))
        taken: dict[str, list[int]] = {section_id: [] for section_id in self.extract.sections}
        histogram = {str(count): 0 for count in range(ladder + 1)}
        self.admitted: dict[str, list[dict[str, int]]] = {path_id: []
                                                          for path_id in self.path_ids}
        self.withheld: list[dict[str, str]] = []
        for _, _, path_id, day, movement in walk:
            chosen = None
            for count in range(ladder + 1):
                shift = count * step * MINUTE
                if self._clears(movement["entries"], shift, taken, applied):
                    chosen = count
                    break
            if chosen is None:
                self.withheld.append({"path_id": path_id, "reason": "headway",
                                      "service_date": from_ordinal(day)})
                continue
            shift = chosen * step * MINUTE
            for section_id, instant in movement["entries"]:
                bisect.insort(taken[section_id], instant + shift)
            histogram[str(chosen)] += 1
            self.admitted[path_id].append({"day": day, "deferral": chosen * step})
        self.withheld.sort(key=lambda row: (row["path_id"], row["service_date"]))
        self.section_counts = {section_id: len(values)
                               for section_id, values in sorted(taken.items())}
        self.admitted_total = sum(len(rows) for rows in self.admitted.values())
        self.deferred_total = sum(1 for rows in self.admitted.values()
                                  for row in rows if row["deferral"] > 0)
        self.documents["headway_resolution.json"] = {
            "admitted_total": self.admitted_total,
            "deferral_histogram": histogram,
            "deferred_total": self.deferred_total,
            "section_admitted_counts": self.section_counts,
            "withheld_total": len(self.withheld)}
        self.documents["withheld_paths.json"] = {
            "movements": self.withheld,
            "rejected_paths": [{"path_id": path_id, "reason": "variant_cycle"}
                               for path_id in sorted(self.rejected)]}

    def _clears(self, entries: list[tuple[str, int]], shift: int,
                taken: dict[str, list[int]], applied: dict[str, int]) -> bool:
        for section_id, instant in entries:
            limit = applied[self.extract.sections[section_id]["section_class"]] * MINUTE
            moved = instant + shift
            values = taken[section_id]
            slot = bisect.bisect_left(values, moved)
            if slot > 0 and moved - values[slot - 1] <= limit:
                return False
            if slot < len(values) and values[slot] - moved <= limit:
                return False
        return True

    # -- timetable, calendars and digest -----------------------------------
    def stage_timetable(self) -> None:
        withheld_by_path = {path_id: 0 for path_id in self.path_ids}
        for row in self.withheld:
            withheld_by_path[row["path_id"]] += 1
        rows = []
        minutes_total = 0
        for path_id in self.path_ids:
            path = self.by_id[path_id]
            own = self.admitted[path_id]
            span = max(offset for _, offset in self.extract.routes[path["route_id"]])
            minutes = len(own) * span
            minutes_total += minutes
            rows.append({
                "admitted_day_count": len(own),
                "deferral_minute_total": sum(row["deferral"] for row in own),
                "deferred_day_count": sum(1 for row in own if row["deferral"] > 0),
                "operator_id": path["operator_id"], "path_id": path_id,
                "path_minutes": minutes, "route_id": path["route_id"],
                "withheld_day_count": withheld_by_path[path_id],
                "zone_id": path["zone_id"]})
        self.timetable_rows = rows
        self.documents["compiled_timetable.json"] = {
            "admitted_movement_total": self.admitted_total,
            "path_minutes_total": minutes_total, "paths": rows,
            "withheld_movement_total": len(self.withheld)}

    def stage_calendars(self) -> None:
        calendars = []
        set_bits = 0
        for path_id in self.path_ids:
            days = sorted(row["day"] for row in self.admitted[path_id])
            if not days:
                calendars.append({"base_day": from_ordinal(self.by_id[path_id]["valid_from"]),
                                  "bit_length": 0, "hex": "", "path_id": path_id})
                continue
            base = days[0]
            length = days[-1] - base + 1
            blob = bytearray((length + 7) // 8)
            for day in days:
                index = day - base
                blob[index // 8] |= 1 << (7 - index % 8)
            set_bits += len(days)
            calendars.append({"base_day": from_ordinal(base), "bit_length": length,
                              "hex": bytes(blob).hex(), "path_id": path_id})
        self.set_bits = set_bits
        self.documents["canonical_calendars.json"] = {"calendars": calendars,
                                                      "set_bit_total": set_bits}

    def stage_digest(self) -> None:
        terms = []
        digest = 0
        for position, row in enumerate(self.timetable_rows, start=1):
            value = row["admitted_day_count"] * 1000 + row["deferral_minute_total"]
            term = (position * value) % DIGEST_MODULUS
            digest = (digest + term) % DIGEST_MODULUS
            terms.append({"position": position, "term": term, "value": value})
        self.digest = digest
        self.documents["timetable_digest.json"] = {
            "digest": digest, "leading_terms": terms[:3],
            "modulus": DIGEST_MODULUS, "term_count": len(terms)}

    def stage_quality(self) -> None:
        empty = sorted(row["path_id"] for row in self.timetable_rows
                       if row["admitted_day_count"] == 0)
        withheld_paths = sorted({row["path_id"] for row in self.withheld})
        subjects = {
            "ALIAS_CYCLE": sorted(self.identity.on_cycle),
            "CAP_BINDING": sorted(self.cap_bound),
            "EMPTY_CALENDAR": empty,
            "FOLD_DEPARTURE": sorted(self.fold_paths),
            "HEADWAY_WITHHELD": withheld_paths,
            "UNRESOLVED_SPELLING": sorted(set(self.malformed) | set(self.unresolved)),
            "VARIANT_CYCLE": sorted(self.rejected),
        }
        self.documents["data_quality.json"] = {
            "issue_counts": {code: len(subjects[code]) for code in QUALITY_CODES},
            "issue_total": sum(len(subjects[code]) for code in QUALITY_CODES),
            "subjects": subjects}
        self.flags = sorted({(path_id, "cap_binding") for path_id in self.cap_bound}
                            | {(path_id, "empty_calendar") for path_id in empty}
                            | {(path_id, "fold_departure") for path_id in self.fold_paths}
                            | {(path_id, "gap_departure") for path_id in self.gap_paths}
                            | {(path_id, "variant_cycle") for path_id in self.rejected})

    def stage_rollups(self) -> None:
        applied = self.extract.applied_headway()
        operator_rows = []
        for operator in self.extract.operators:
            own = [row for row in self.timetable_rows
                   if row["operator_id"] == operator["operator_id"]]
            operator_rows.append([operator["operator_id"], operator["rank_weight"], len(own),
                                  sum(row["admitted_day_count"] for row in own),
                                  sum(row["withheld_day_count"] for row in own),
                                  sum(row["path_minutes"] for row in own)])
        self.documents["operator_rollup.tsv"] = render_rows(
            ["operator_id", "rank_weight", "path_count", "admitted_movements",
             "withheld_movements", "path_minutes"], operator_rows, "\t")
        section_rows = []
        for section_id in sorted(self.extract.sections):
            section = self.extract.sections[section_id]
            section_rows.append([section_id, section["section_class"], section["zone_id"],
                                 applied[section["section_class"]],
                                 self.section_counts[section_id]])
        self.documents["section_rollup.psv"] = render_rows(
            ["section_id", "section_class", "zone_id", "min_headway_min", "admitted_entries"],
            section_rows, "|")
        path_rows = []
        for row in self.timetable_rows:
            path_rows.append([row["path_id"], row["operator_id"],
                              self.by_id[row["path_id"]]["rule_id"],
                              row["admitted_day_count"], row["deferred_day_count"],
                              row["withheld_day_count"], row["path_minutes"]])
        self.documents["path_rollup.csv"] = render_rows(
            ["path_id", "operator_id", "rule_id", "admitted_days", "deferred_days",
             "withheld_days", "path_minutes"], path_rows, ",")
        self.documents["flagged_paths.xml"] = render_flags(self.flags)
        self.documents["compile_report.md"] = render_report(
            self.extract.period["period_start"], self.extract.period["period_end"],
            len(self.registered), len(self.rejected), self.admitted_total,
            self.deferred_total, len(self.withheld), self.gap_count, self.fold_count,
            self.set_bits, self.digest)
        self.documents["run_status.txt"] = render_status(
            len(self.registered), self.admitted_total, len(self.withheld), self.digest)

    def run(self) -> dict[str, Any]:
        self.stage_identity()
        self.stage_authority()
        self.stage_expansion()
        self.stage_exceptions()
        self.stage_overlay()
        self.stage_timepoints()
        self.stage_headway()
        self.stage_timetable()
        self.stage_calendars()
        self.stage_digest()
        self.stage_quality()
        self.stage_rollups()
        return self.documents


# ---------------------------------------------------------------------------
# Rendering. Unchanged since build 3.1.
# ---------------------------------------------------------------------------
def render_rows(header: list[str], rows: list[list[Any]], delimiter: str) -> str:
    lines = [delimiter.join(header)]
    lines.extend(delimiter.join(str(cell) for cell in row) for row in rows)
    return "\n".join(lines) + "\n"


def render_flags(flags: list[tuple[str, str]]) -> str:
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<flagged count="' + str(len(flags)) + '">']
    lines.extend('  <path id="' + path_id + '" reason="' + reason + '"/>'
                 for path_id, reason in flags)
    lines.append("</flagged>")
    return "\n".join(lines) + "\n"


def render_report(period_start: str, period_end: str, registered: int, rejected: int,
                  admitted: int, deferred: int, withheld: int, gaps: int, folds: int,
                  set_bits: int, digest: int) -> str:
    lines = [
        "# Working timetable compile report",
        "period: " + period_start + " to " + period_end,
        "paths registered: " + str(registered),
        "paths rejected: " + str(rejected),
        "movements admitted: " + str(admitted),
        "movements deferred: " + str(deferred),
        "movements withheld: " + str(withheld),
        "gap departures: " + str(gaps),
        "fold departures: " + str(folds),
        "set bits: " + str(set_bits),
        "digest: " + str(digest),
        "status: complete",
    ]
    return "\n".join(lines) + "\n"


def render_status(registered: int, admitted: int, withheld: int, digest: int) -> str:
    return ("compiled " + str(registered) + " paths " + str(admitted) + " admitted "
            + str(withheld) + " withheld digest " + str(digest) + "\n")


JSON_DOCUMENTS = [
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


def compile_extract(data_dir: str, out_dir: str) -> None:
    """Compile the extract under data_dir and write the documents to out_dir."""
    root = Path(data_dir)
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    documents = Compile(Extract(root)).run()
    for name, payload in documents.items():
        if name in JSON_DOCUMENTS:
            (target / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        else:
            (target / name).write_text(payload, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] != "compile":
        sys.stderr.write("usage: ttc.py compile <DATA_DIR> <OUT_DIR>\n")
        return 2
    compile_extract(argv[2], argv[3])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
