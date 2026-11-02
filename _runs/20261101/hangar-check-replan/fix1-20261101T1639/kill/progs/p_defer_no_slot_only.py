#!/usr/bin/env python3
"""Heavy check season replan.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Reads the season inputs from DATA_DIR, screens the request rows, finds the season plan that wins the
comparison of planning_policy.md under the shared overtime pool, settles overtime against the fleet
allowance and writes the nine JSON reports into OUT_DIR. Standard library only.
"""
import csv
import datetime
import json
import os
import re
import sys
import tomllib
import zipfile
import xml.etree.ElementTree as ElementTree

BASE_ORDER = ("North", "South", "West", "East")
SEGMENT_CLASSES = (("commercial", ("widebody", "narrowbody")), ("public", ("regional",)))
REJECT_ORDER = ("duplicate_request", "unknown_base", "unknown_check_type", "unknown_tail",
                "retired_tail", "bad_date", "bad_duration", "no_published_start")
CLASS_RANK = {"widebody": 0, "narrowbody": 1, "regional": 2}
WML = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
WHOLE_POSITIVE = re.compile(r"[1-9][0-9]*")


class InputError(Exception):
    """A declared input is missing or cannot be read; the message names the file."""


def iso_day(text):
    """Strict ISO calendar date, or ValueError."""
    if text is None or not ISO_DAY.fullmatch(text):
        raise ValueError("not an ISO date: %r" % (text,))
    return datetime.date.fromisoformat(text)


def valid_day(text):
    try:
        iso_day(text)
    except ValueError:
        return False
    return True


class SeasonInputs:
    """Every declared input of one data folder, parsed."""

    def __init__(self, folder):
        self.folder = folder
        self.limits = self._toml("fleet_limits.toml")
        self.check_types = self._json("check_types.json")
        self.register = {row["tail"]: row for row in self._csv("fleet_register.csv")}
        self.published = {row["request_id"]: row["published_start"] for row in self._csv("published_plan.csv")}
        self.request_rows = self._csv("check_requests.csv")
        self.calendar = self._jsonl("base_calendar.jsonl")
        limits_tables = self._word_tables("planning_limits.docx")
        notice_tables = self._word_tables("disruption_notice.docx")
        try:
            items = {row["item"]: int(row["value"]) for row in limits_tables[("item", "value")]}
            self.pool = items["overtime_pool_shifts"]
            self.shift_cost = items["shift_cost"]
            self.rates = {row["class"]: (int(row["revenue_per_day"]), int(row["overdue_weight"]),
                                         int(row["deferral_penalty"]))
                          for row in limits_tables[("class", "revenue_per_day")]}
            self.grants = dict.fromkeys(BASE_ORDER, 0)
            for row in limits_tables[("base", "allowance_shifts")]:
                self.grants[row["base"]] = int(row["allowance_shifts"])
        except (KeyError, ValueError) as exc:
            raise InputError("cannot use input file %s: %s" % (self._path("planning_limits.docx"), exc)) from exc
        try:
            self.closure_rows = [(row["base"], iso_day(row["from"]), int(row["days"]))
                                 for row in notice_tables[("base", "from")]]
            self.revised = {row["tail"]: row["available_from"] for row in notice_tables[("tail", "available_from")]}
        except (KeyError, ValueError) as exc:
            raise InputError("cannot use input file %s: %s" % (self._path("disruption_notice.docx"), exc)) from exc
        try:
            self.season = self.limits["season"]
            self.first_day = iso_day(self.limits["season_start"])
            self.season_days = (iso_day(self.limits["season_end"]) - self.first_day).days + 1
        except (KeyError, ValueError) as exc:
            raise InputError("cannot use input file %s: %s" % (self._path("fleet_limits.toml"), exc)) from exc

    def _path(self, name):
        return os.path.join(self.folder, name)

    def _open(self, name, mode="r"):
        path = self._path(name)
        if not os.path.isfile(path):
            raise InputError("missing input file: %s" % path)
        return open(path, mode) if "b" in mode else open(path, mode, encoding="utf-8", newline="")

    def _toml(self, name):
        with self._open(name, "rb") as handle:
            try:
                return tomllib.load(handle)
            except tomllib.TOMLDecodeError as exc:
                raise InputError("cannot parse input file %s: %s" % (self._path(name), exc)) from exc

    def _json(self, name):
        with self._open(name) as handle:
            try:
                return json.load(handle)
            except json.JSONDecodeError as exc:
                raise InputError("cannot parse input file %s: %s" % (self._path(name), exc)) from exc

    def _jsonl(self, name):
        with self._open(name) as handle:
            try:
                return [json.loads(text) for text in handle if text.strip()]
            except json.JSONDecodeError as exc:
                raise InputError("cannot parse input file %s: %s" % (self._path(name), exc)) from exc

    def _csv(self, name):
        with self._open(name) as handle:
            try:
                return list(csv.DictReader(handle))
            except csv.Error as exc:
                raise InputError("cannot parse input file %s: %s" % (self._path(name), exc)) from exc

    def _word_tables(self, name):
        """Tables of the main document part named by the package relationships, keyed by header pair."""
        path = self._path(name)
        if not os.path.isfile(path):
            raise InputError("missing input file: %s" % path)
        try:
            with zipfile.ZipFile(path) as package:
                relations = ElementTree.fromstring(package.read("_rels/.rels"))
                target = None
                for rel in relations.iter(PKG_REL + "Relationship"):
                    if rel.get("Type", "").rsplit("/", 1)[-1] == "officeDocument":
                        target = rel.get("Target", "").lstrip("/")
                        break
                if target is None:
                    raise InputError("cannot parse input file %s: no officeDocument relationship" % path)
                document = ElementTree.fromstring(package.read(target))
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
            raise InputError("cannot parse input file %s: %s" % (path, exc)) from exc
        tables = {}
        for table in document.iter(WML + "tbl"):
            grid = []
            for table_row in table.findall(WML + "tr"):
                grid.append(["".join(node.text or "" for node in cell.iter(WML + "t")).strip()
                             for cell in table_row.findall(WML + "tc")])
            if grid and len(grid[0]) >= 2 and tuple(grid[0][:2]) not in tables:
                header = grid[0]
                tables[tuple(header[:2])] = [dict(zip(header, values)) for values in grid[1:]]
        return tables

    def day_number(self, date):
        return (date - self.first_day).days + 1

    def day_text(self, number):
        return (self.first_day + datetime.timedelta(days=number - 1)).isoformat()


def screen_requests(inputs):
    """Planned rows of the season and the rejected ones, in file order."""
    accepted, rejected, ids_read = [], [], set()
    for line_number, row in enumerate(inputs.request_rows, start=2):
        if row.get("season") != inputs.season or row.get("status") != "OPEN":
            continue
        request_id = row.get("request_id")
        tail = inputs.register.get(row.get("tail"))
        tests = (
            ("duplicate_request", lambda: request_id in ids_read),
            ("unknown_base", lambda: row.get("base") not in BASE_ORDER),
            ("unknown_check_type", lambda: row.get("check_type") not in inputs.check_types),
            ("unknown_tail", lambda: tail is None),
            ("retired_tail", lambda: tail["status"] == "RETIRED"),
            ("bad_date", lambda: not (valid_day(row.get("available_from")) and valid_day(row.get("due_date")))),
            ("bad_duration", lambda: not WHOLE_POSITIVE.fullmatch(row.get("duration_days") or "")),
            ("no_published_start", lambda: request_id not in inputs.published),
        )
        reason = next((name for name, applies in tests if applies()), None)
        ids_read.add(request_id)
        if reason is None:
            accepted.append(row)
        else:
            rejected.append({"request_id": request_id, "line": line_number, "reason": reason})
    return accepted, rejected


class Request:
    """One open request on the season day scale (day 1 is season_start)."""

    def __init__(self, row, inputs):
        self.request_id = row["request_id"]
        self.tail = row["tail"]
        self.base = row["base"]
        self.check_type = row["check_type"]
        self.aircraft_class = inputs.register[self.tail]["aircraft_class"]
        self.duration = int(row["duration_days"])
        self.published = inputs.day_number(iso_day(inputs.published[self.request_id]))
        self.due = inputs.day_number(iso_day(row["due_date"]))
        available = inputs.revised.get(self.tail, row["available_from"])
        self.available = max(1, inputs.day_number(iso_day(available)))
        kind = inputs.check_types[self.check_type]
        self.max_compress = min(int(kind["max_compress_days"]), self.duration - 1)
        self.shifts_per_day = int(kind["overtime_shifts_per_day"])
        self.revenue, self.overdue_weight, self.penalty = inputs.rates[self.aircraft_class]


class BaseLine:
    """Closed and no-start days of one base and the exact frontier of its checks."""

    def __init__(self, base, inputs, requests):
        self.base = base
        self.last_day = inputs.season_days
        self.shift_cost = inputs.shift_cost
        self.closed, self.no_start = set(), set()
        for entry in inputs.calendar:
            if entry.get("base") != base:
                continue
            number = inputs.day_number(iso_day(entry["date"]))
            if 1 <= number <= self.last_day:
                if entry["status"] == "CLOSED":
                    self.closed.add(number)
                elif entry["status"] == "NO_START":
                    self.no_start.add(number)
        for where, start, length in inputs.closure_rows:
            if where == base:
                first = inputs.day_number(start)
                self.closed.update(d for d in range(first, first + length) if 1 <= d <= self.last_day)
        self.requests = sorted(requests, key=lambda r: r.request_id)
        self._first_start = {}

    def can_start(self, day, length):
        if day in self.no_start or day + length - 1 > self.last_day:
            return False
        return self.closed.isdisjoint(range(day, day + length))

    def first_start(self, earliest, length):
        key = (earliest, length)
        if key not in self._first_start:
            day = earliest
            while day + length - 1 <= self.last_day and not self.can_start(day, length):
                day += 1
            self._first_start[key] = day if day + length - 1 <= self.last_day else None
        return self._first_start[key]

    def fits_alone(self, request):
        """True when the check can finish in the season at some compression on an empty line."""
        return any(self.first_start(request.available, request.duration - squeeze) is not None
                   for squeeze in range(request.max_compress + 1))

    def placements(self, request, line_free):
        """Deferral, then for every compression the earliest legal start and the published start."""
        yield None
        lower = max(line_free, request.available)
        for squeeze in range(request.max_compress + 1):
            length = request.duration - squeeze
            early = self.first_start(lower, length)
            if early is None:
                continue
            yield early, squeeze
            if request.published > early and self.can_start(request.published, length):
                yield request.published, squeeze

    def frontier(self):
        """Overtime shifts -> best (first, second, third, starts, finishes, squeezes) of this base."""
        count = len(self.requests)
        after_season = self.last_day + 1
        layer = {(0, 1): {0: (0, 0, 0, (after_season,) * count, (after_season,) * count, (0,) * count)}}
        for _ in range(count):
            following = {}
            for (done, line_free), by_shifts in layer.items():
                for index, request in enumerate(self.requests):
                    if done >> index & 1:
                        continue
                    for choice in self.placements(request, line_free):
                        if choice is None and self.fits_alone(request):
                            continue
                        if choice is None:
                            step = (request.penalty, 0, 1, after_season, after_season, 0, 0)
                            free_next = line_free
                        else:
                            start, squeeze = choice
                            finish = start + request.duration - squeeze - 1
                            shifts = squeeze * request.shifts_per_day
                            step = (max(0, finish - request.due) * request.overdue_weight,
                                    request.revenue * (request.duration - squeeze) + self.shift_cost * shifts,
                                    0 if start == request.published else 1, start, finish, squeeze, shifts)
                            free_next = finish + 1
                        target = following.setdefault((done | 1 << index, free_next), {})
                        for used, value in by_shifts.items():
                            total = used + step[6]
                            merged = (value[0] + step[0], value[1] + step[1], value[2] + step[2],
                                      value[3][:index] + (step[3],) + value[3][index + 1:],
                                      value[4][:index] + (step[4],) + value[4][index + 1:],
                                      value[5][:index] + (step[5],) + value[5][index + 1:])
                            held = target.get(total)
                            if held is None or merged < held:
                                target[total] = merged
            layer = following
        best = {}
        for by_shifts in layer.values():
            for used, value in by_shifts.items():
                if used not in best or value < best[used]:
                    best[used] = value
        kept, record = {}, None
        for used in sorted(best):
            if record is None or best[used] < record:
                kept[used] = best[used]
                record = best[used]
        return kept


def season_plan(inputs, lines):
    """Merge the base frontiers under the pool; ties by the fleet start list, then the finish list.

    Returns (first, second, third), the pool shifts used and request_id -> (start, finish, squeeze).
    """
    order = sorted(r.request_id for line in lines for r in line.requests)
    slot = {request_id: i for i, request_id in enumerate(order)}
    after_season = inputs.season_days + 1
    frontiers = [line.frontier() for line in lines]
    combos = {0: (0, 0, 0, (after_season,) * len(order), (after_season,) * len(order), ())}
    for line, options in zip(lines, frontiers):
        nxt = {}
        for used, partial in combos.items():
            for extra, value in options.items():
                if used + extra > inputs.pool:
                    continue
                starts, finishes = list(partial[3]), list(partial[4])
                for k, request in enumerate(line.requests):
                    starts[slot[request.request_id]] = value[3][k]
                    finishes[slot[request.request_id]] = value[4][k]
                joined = (partial[0] + value[0], partial[1] + value[1], partial[2] + value[2],
                          tuple(starts), tuple(finishes), partial[5] + (extra,))
                held = nxt.get(used + extra)
                if held is None or joined[:5] < held[:5]:
                    nxt[used + extra] = joined
        combos = nxt
    winner = min(combos.values(), key=lambda v: v[:5])
    placement = {}
    for line, options, extra in zip(lines, frontiers, winner[5]):
        chosen = options[extra]
        for k, request in enumerate(line.requests):
            placement[request.request_id] = (chosen[3][k], chosen[4][k], chosen[5][k])
    return winner[:3], sum(winner[5]), placement


def settle(rows, grants, shift_cost, due_of):
    """Fleet allowance pays checks by class rank, due date, request_id; fills the five money fields."""
    left = sum(grants.values())
    paying = sorted((row for row in rows if row["decision"] == "scheduled"),
                    key=lambda row: (CLASS_RANK[row["aircraft_class"]], due_of[row["request_id"]], row["request_id"]))
    taken = {}
    for row in paying:
        taken[row["request_id"]] = min(row["overtime_shifts"], left)
        left -= taken[row["request_id"]]
    for row in rows:
        shifts, covered = row["overtime_shifts"], taken.get(row["request_id"], 0)
        row["overtime_cost"] = shift_cost * shifts
        row["allowance_shifts"] = covered
        row["paid_shifts"] = shifts - covered
        row["allowance_credit"] = shift_cost * covered
        row["settled_overtime_cost"] = row["overtime_cost"] - row["allowance_credit"]


def totals(rows, extra, pool_used):
    """Roll-up fields of one base, one segment or the fleet."""
    scheduled = [row for row in rows if row["decision"] == "scheduled"]
    return {
        "checks_scheduled": len(scheduled),
        "checks_deferred": len(rows) - len(scheduled),
        "compress_days": sum(row["compress_days"] for row in scheduled),
        "overtime_shifts": sum(row["overtime_shifts"] for row in scheduled),
        "overdue_days": sum(row["overdue_days"] for row in scheduled),
        "overdue_cost": sum(extra[row["request_id"]][0] for row in scheduled),
        "deferral_cost": sum(extra[row["request_id"]][1] for row in rows),
        "revenue_lost": sum(extra[row["request_id"]][2] for row in scheduled),
        "moved": sum(1 for row in rows if row["moved"]),
        "first_start": min((row["start_date"] for row in scheduled), default=None),
        "last_finish": max((row["finish_date"] for row in scheduled), default=None),
        "fleet_overtime_used": pool_used,
        "overtime_cost": sum(row["overtime_cost"] for row in rows),
        "allowance_used": sum(row["allowance_shifts"] for row in rows),
        "allowance_credit": sum(row["allowance_credit"] for row in rows),
        "settled_overtime_cost": sum(row["settled_overtime_cost"] for row in rows),
    }


def build_reports(inputs, requests):
    lines = [BaseLine(base, inputs, [r for r in requests if r.base == base]) for base in BASE_ORDER]
    line_of = {line.base: line for line in lines}
    terms, pool_used, placement = season_plan(inputs, lines)
    segment_of = {cls: name for name, classes in SEGMENT_CLASSES for cls in classes}
    rows, extra = [], {}
    for request in sorted(requests, key=lambda r: r.request_id):
        start, finish, squeeze = placement[request.request_id]
        row = {"request_id": request.request_id, "tail": request.tail, "base": request.base,
               "aircraft_class": request.aircraft_class, "segment": segment_of[request.aircraft_class],
               "check_type": request.check_type}
        if start > inputs.season_days:
            fits = line_of[request.base].fits_alone(request)
            row.update(decision="deferred", start_date=None, finish_date=None, compress_days=0,
                       overtime_shifts=0, overdue_days=0, moved=True,
                       deferral_reason="plan_trade" if fits else "no_slot")
            extra[request.request_id] = (0, request.penalty, 0)
        else:
            late = max(0, finish - request.due)
            row.update(decision="scheduled", start_date=inputs.day_text(start), finish_date=inputs.day_text(finish),
                       compress_days=squeeze, overtime_shifts=squeeze * request.shifts_per_day, overdue_days=late,
                       moved=start != request.published, deferral_reason=None)
            extra[request.request_id] = (late * request.overdue_weight, 0,
                                         request.revenue * (request.duration - squeeze))
        rows.append(row)
    settle(rows, inputs.grants, inputs.shift_cost, {r.request_id: r.due for r in requests})
    reports = {"policy_audit.json": {"season": inputs.season, "checks": rows}}
    base_rows = []
    for base in BASE_ORDER:
        part = totals([row for row in rows if row["base"] == base], extra, pool_used)
        reports["region_%s.json" % base] = dict(base=base, allowance_granted=inputs.grants[base], **part)
        base_rows.append({"base": base, "checks_scheduled": part["checks_scheduled"],
                          "checks_deferred": part["checks_deferred"], "overtime_shifts": part["overtime_shifts"],
                          "allowance_granted": inputs.grants[base], "allowance_used": part["allowance_used"],
                          "settled_overtime_cost": part["settled_overtime_cost"]})
    segment_rows = []
    for name, _ in SEGMENT_CLASSES:
        part = totals([row for row in rows if row["segment"] == name], extra, pool_used)
        reports["segment_%s.json" % name] = dict(segment=name, **part)
        segment_rows.append({"segment": name, "checks_scheduled": part["checks_scheduled"],
                             "checks_deferred": part["checks_deferred"]})
    fleet = totals(rows, extra, pool_used)
    granted = sum(inputs.grants.values())
    reports["summary.json"] = {
        "season": inputs.season,
        "plan_terms": {"first": terms[0], "second": terms[1], "third": terms[2]},
        "overtime_pool_shifts": inputs.pool,
        "fleet_overtime_used": pool_used,
        "checks_scheduled": fleet["checks_scheduled"],
        "checks_deferred": fleet["checks_deferred"],
        "moved": fleet["moved"],
        "settlement": {"allowance_granted": granted, "allowance_used": fleet["allowance_used"],
                       "allowance_left": granted - fleet["allowance_used"],
                       "overtime_cost": fleet["overtime_cost"], "allowance_credit": fleet["allowance_credit"],
                       "settled_overtime_cost": fleet["settled_overtime_cost"]},
        "bases": base_rows,
        "segments": segment_rows,
    }
    return reports


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    try:
        inputs = SeasonInputs(argv[1])
        accepted, rejected = screen_requests(inputs)
        requests = [Request(row, inputs) for row in accepted]
        reports = build_reports(inputs, requests)
    except InputError as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    reports["data_quality.json"] = {
        "rejected": rejected,
        "counts": {reason: sum(1 for item in rejected if item["reason"] == reason) for reason in REJECT_ORDER},
    }
    os.makedirs(argv[2], exist_ok=True)
    for name, body in reports.items():
        with open(os.path.join(argv[2], name), "w", encoding="utf-8") as handle:
            json.dump(body, handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
