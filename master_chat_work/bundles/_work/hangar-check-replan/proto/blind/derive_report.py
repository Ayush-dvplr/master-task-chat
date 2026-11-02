#!/usr/bin/env python3
"""Heavy check replan for one season.

Reads the data folder described in docs/data_conventions.md and writes the
reports described in docs/output_schema.md.

Usage:
    python3 derive_report.py [--data <data folder>] [--out <output folder>]

Standard library only.
"""

import argparse
import csv
import datetime
import json
import os
import sys

BASES = ["North", "South", "West", "East"]
SEGMENT_OF_CLASS = {
    "widebody": "commercial",
    "narrowbody": "commercial",
    "regional": "public",
}
SEGMENTS = ["commercial", "public"]

REASONS = [
    "duplicate_request",
    "unknown_base",
    "unknown_check_type",
    "unknown_tail",
    "retired_tail",
    "bad_date",
    "bad_duration",
    "no_published_start",
]


def die(path, detail):
    sys.stderr.write("error: cannot use input file %s: %s\n" % (path, detail))
    sys.exit(1)


# ---------------------------------------------------------------- input parsing


def read_text(path):
    if not os.path.isfile(path):
        die(path, "file is missing")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        die(path, str(exc))


def parse_scalar(raw):
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    if text in ("true", "false"):
        return text == "true"
    return text


def load_limits(path):
    """Flat `key = value` table (fleet_limits.toml)."""
    out = {}
    for line in read_text(path).splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("["):
            continue
        if "=" not in line:
            die(path, "line is not key = value: %r" % line)
        key, raw = line.split("=", 1)
        out[key.strip()] = parse_scalar(raw)
    for key in ("season", "season_start", "season_end", "overtime_pool_shifts",
                "shift_cost"):
        if key not in out:
            die(path, "missing key %s" % key)
    return out


def load_rates(path):
    """Two level `name:` / `  key: value` mapping (class_rates.yaml)."""
    out = {}
    current = None
    for line in read_text(path).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        stripped = line.strip()
        if ":" not in stripped:
            die(path, "line is not key: value: %r" % line)
        key, raw = stripped.split(":", 1)
        if line[:1] not in (" ", "\t"):
            current = key.strip()
            out[current] = {}
            if raw.strip():
                die(path, "unexpected value on class line: %r" % line)
        else:
            if current is None:
                die(path, "indented line before any class: %r" % line)
            out[current][key.strip()] = parse_scalar(raw)
    for name, body in out.items():
        for key in ("revenue_per_day", "overdue_weight", "deferral_penalty"):
            if key not in body:
                die(path, "class %s has no %s" % (name, key))
    return out


def load_json(path):
    text = read_text(path)
    try:
        return json.loads(text)
    except ValueError as exc:
        die(path, "invalid JSON: %s" % exc)


def load_jsonl(path):
    text = read_text(path)
    out = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError as exc:
            die(path, "invalid JSON on line %d: %s" % (number, exc))
    return out


def load_csv(path, fields):
    text = read_text(path)
    rows = list(csv.DictReader(text.splitlines()))
    if rows:
        for field in fields:
            if field not in rows[0]:
                die(path, "missing column %s" % field)
    return rows


def md_tables(path):
    """Return {heading: [row cell lists]} for every `## heading` with a table."""
    tables = {}
    heading = None
    rows = []
    for line in read_text(path).splitlines():
        text = line.strip()
        if text.startswith("#"):
            if heading is not None:
                tables[heading] = rows
            heading = text.lstrip("#").strip()
            rows = []
            continue
        if text.startswith("|"):
            cells = [cell.strip() for cell in text.strip("|").split("|")]
            if all(set(cell) <= set("-: ") and cell for cell in cells):
                continue
            rows.append(cells)
    if heading is not None:
        tables[heading] = rows
    return tables


def notice_tables(path):
    tables = md_tables(path)
    closures = []
    revised = {}
    for name, rows in tables.items():
        key = name.lower()
        if key == "base closures":
            for cells in rows:
                if len(cells) < 3:
                    die(path, "base closure row has too few cells: %r" % cells)
                if [c.lower() for c in cells[:3]] == ["base", "from", "to"]:
                    continue
                closures.append((cells[0], cells[1], cells[2]))
        elif key == "revised availability":
            for cells in rows:
                if len(cells) < 2:
                    die(path, "availability row has too few cells: %r" % cells)
                if [c.lower() for c in cells[:2]] == ["tail", "available_from"]:
                    continue
                revised[cells[0]] = cells[1]
    return closures, revised


def parse_date(text):
    try:
        return datetime.date(*[int(part) for part in text.split("-")])
    except (ValueError, TypeError):
        return None


def strict_date(text):
    if text is None:
        return None
    text = text.strip()
    parts = text.split("-")
    if len(parts) != 3:
        return None
    if len(parts[0]) != 4 or len(parts[1]) != 2 or len(parts[2]) != 2:
        return None
    if not all(part.isdigit() for part in parts):
        return None
    return parse_date(text)


def whole_number(text):
    text = (text or "").strip()
    if not text:
        return None
    sign = 1
    body = text
    if body[0] in "+-":
        if body[0] == "-":
            sign = -1
        body = body[1:]
    if not body.isdigit():
        return None
    return sign * int(body)


# ------------------------------------------------------------------- base lines


class BaseLine(object):
    """Closed / no-start days of one base over the season, and start lookups."""

    def __init__(self, days, closed, nostart):
        self.days = days
        self.closed = closed
        self.nostart = nostart
        self.closed_prefix = [0] * (days + 1)
        for index in range(days):
            self.closed_prefix[index + 1] = self.closed_prefix[index] + (
                1 if closed[index] else 0)
        self.earliest = {}

    def window_clear(self, start, length):
        end = start + length - 1
        if start < 0 or end >= self.days:
            return False
        if self.closed_prefix[end + 1] - self.closed_prefix[start]:
            return False
        return True

    def can_start(self, start, length):
        if start < 0 or start >= self.days:
            return False
        if self.closed[start] or self.nostart[start]:
            return False
        return self.window_clear(start, length)

    def earliest_start(self, length, lower):
        """Smallest feasible start >= lower for a check of `length` days."""
        if length < 1:
            return None
        table = self.earliest.get(length)
        if table is None:
            table = [None] * (self.days + 1)
            nxt = None
            for day in range(self.days - 1, -1, -1):
                if self.can_start(day, length):
                    nxt = day
                table[day] = nxt
            table[self.days] = None
            self.earliest[length] = table
        if lower < 0:
            lower = 0
        if lower > self.days:
            return None
        return table[lower]


# ----------------------------------------------------------------- the planning


class Request(object):
    __slots__ = ("rid", "line", "tail", "base", "check_type", "cls", "segment",
                 "duration", "max_compress", "shifts_per_day", "avail",
                 "due_offset", "pub_offset", "rev", "weight", "penalty")


def plan_base(reqs, line, pool, shift_cost, mul_first, mul_second):
    """Exact best plan for one base line, per number of overtime shifts used.

    Returns {shifts: (scalar, start_tuple, finish_tuple)} where the tuples are
    in request_id order over all requests of the base, a deferred request
    holding the day after season end.  `scalar` packs the three plan terms of
    this base so that ordinary addition stays lexicographic.
    """
    count = len(reqs)
    deferred_day = line.days
    full = (1 << count) - 1

    defer_scalar = [req.penalty * mul_first + 1 for req in reqs]
    memo = {}

    def solve(mask, free):
        cached = memo.get((mask, free))
        if cached is not None:
            return cached
        members = [index for index in range(count) if mask >> index & 1]
        size = len(members)
        # defer everything that is left
        scalar = 0
        for index in members:
            scalar += defer_scalar[index]
        best = {0: (scalar, (deferred_day,) * size, (deferred_day,) * size)}
        for position, index in enumerate(members):
            req = reqs[index]
            rest = mask & ~(1 << index)
            lower = free if free > req.avail else req.avail
            for compress in range(req.max_compress + 1):
                length = req.duration - compress
                shifts = compress * req.shifts_per_day
                if shifts > pool:
                    continue
                first = line.earliest_start(length, lower)
                if first is None:
                    continue
                starts = [first]
                pub = req.pub_offset
                if (pub is not None and pub > first
                        and line.can_start(pub, length)):
                    starts.append(pub)
                for start in starts:
                    finish = start + length - 1
                    overdue = finish - req.due_offset
                    if overdue < 0:
                        overdue = 0
                    own = (overdue * req.weight) * mul_first
                    own += (length * req.rev + shifts * shift_cost) * mul_second
                    if start != req.pub_offset:
                        own += 1
                    for used, value in solve(rest, finish + 1).items():
                        total_used = used + shifts
                        if total_used > pool:
                            continue
                        candidate = (
                            own + value[0],
                            value[1][:position] + (start,) + value[1][position:],
                            value[2][:position] + (finish,) + value[2][position:],
                        )
                        current = best.get(total_used)
                        if current is None or candidate < current:
                            best[total_used] = candidate
        # a suffix that costs more while using more shifts can never help
        pruned = {}
        floor = None
        for used in sorted(best):
            value = best[used]
            if floor is None or value < floor:
                pruned[used] = value
                floor = value
        memo[(mask, free)] = pruned
        return pruned

    if count == 0:
        return {0: (0, (), ())}
    return solve(full, 0)


def choose_plan(per_base, base_reqs, pool):
    """Minimal total scalar, then lexicographically minimal day vectors."""
    names = [name for name in BASES if name in per_base]
    options = [sorted(per_base[name].items()) for name in names]

    best_scalar = None
    splits = []

    def walk(depth, used, scalar, picks):
        nonlocal best_scalar
        if best_scalar is not None and scalar > best_scalar:
            return
        if depth == len(names):
            if best_scalar is None or scalar < best_scalar:
                best_scalar = scalar
                splits.clear()
            if scalar == best_scalar:
                splits.append(list(picks))
            return
        for shifts, value in options[depth]:
            if used + shifts > pool:
                continue
            picks.append(shifts)
            walk(depth + 1, used + shifts, scalar + value[0], picks)
            picks.pop()

    walk(0, 0, 0, [])

    # global request_id order over every planned request
    global_order = sorted(
        (req.rid, name, position)
        for name in names
        for position, req in enumerate(base_reqs[name]))

    best_key = None
    best_split = None
    for picks in splits:
        starts = {}
        finishes = {}
        for name, shifts in zip(names, picks):
            value = per_base[name][shifts]
            for position, req in enumerate(base_reqs[name]):
                starts[(name, position)] = value[1][position]
                finishes[(name, position)] = value[2][position]
        key = (
            tuple(starts[(name, position)] for _, name, position in global_order),
            tuple(finishes[(name, position)] for _, name, position in global_order),
        )
        if best_key is None or key < best_key:
            best_key = key
            best_split = picks
    return names, best_split, best_scalar


# ----------------------------------------------------------------------- output


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--data", default="/app/environment/data")
    parser.add_argument("--out", default="/app/out")
    args = parser.parse_args(argv)

    data_dir = args.data
    out_dir = args.out

    limits = load_limits(os.path.join(data_dir, "fleet_limits.toml"))
    rates = load_rates(os.path.join(data_dir, "class_rates.yaml"))
    check_types = load_json(os.path.join(data_dir, "check_types.json"))
    register_rows = load_csv(os.path.join(data_dir, "fleet_register.csv"),
                             ["tail", "aircraft_class", "status"])
    request_rows = load_csv(os.path.join(data_dir, "check_requests.csv"),
                            ["request_id", "season", "tail", "check_type",
                             "base", "available_from", "due_date",
                             "duration_days", "status"])
    published_rows = load_csv(os.path.join(data_dir, "published_plan.csv"),
                              ["request_id", "published_start"])
    calendar_rows = load_jsonl(os.path.join(data_dir, "base_calendar.jsonl"))
    closures, revised = notice_tables(os.path.join(data_dir,
                                                   "disruption_notice.md"))

    season = limits["season"]
    season_start = strict_date(str(limits["season_start"]))
    season_end = strict_date(str(limits["season_end"]))
    if season_start is None or season_end is None:
        die(os.path.join(data_dir, "fleet_limits.toml"), "bad season dates")
    days = (season_end - season_start).days + 1
    if days < 1:
        die(os.path.join(data_dir, "fleet_limits.toml"), "empty season")
    pool = int(limits["overtime_pool_shifts"])
    shift_cost = int(limits["shift_cost"])

    register = {}
    for row in register_rows:
        register[row["tail"]] = row

    published = {}
    for row in published_rows:
        if row["request_id"] not in published:
            published[row["request_id"]] = row["published_start"]

    # base lines
    lines = {}
    for name in BASES:
        lines[name] = {"closed": [False] * days, "nostart": [False] * days}
    for row in calendar_rows:
        name = row.get("base")
        if name not in lines:
            continue
        date = strict_date(str(row.get("date")))
        if date is None:
            continue
        offset = (date - season_start).days
        if offset < 0 or offset >= days:
            continue
        status = row.get("status")
        if status == "CLOSED":
            lines[name]["closed"][offset] = True
        elif status == "NO_START":
            lines[name]["nostart"][offset] = True
    for name, start_text, end_text in closures:
        if name not in lines:
            continue
        first = strict_date(start_text)
        last = strict_date(end_text)
        if first is None or last is None:
            die(os.path.join(data_dir, "disruption_notice.md"),
                "bad closure dates for %s" % name)
        for offset in range((last - first).days + 1):
            day = (first + datetime.timedelta(days=offset) - season_start).days
            if 0 <= day < days:
                lines[name]["closed"][day] = True
    base_lines = {
        name: BaseLine(days, lines[name]["closed"], lines[name]["nostart"])
        for name in BASES
    }

    # ---- read rows, rejections
    rejected = []
    counts = {reason: 0 for reason in REASONS}
    seen_ids = set()
    requests = []

    for number, row in enumerate(request_rows, start=2):
        if row.get("season") != season or row.get("status") != "OPEN":
            continue
        rid = row.get("request_id")
        reason = None
        if rid in seen_ids:
            reason = "duplicate_request"
        seen_ids.add(rid)
        base = row.get("base")
        check_type = row.get("check_type")
        tail = row.get("tail")
        entry = register.get(tail)
        avail_date = strict_date(row.get("available_from"))
        due_date = strict_date(row.get("due_date"))
        duration = whole_number(row.get("duration_days"))
        if reason is None and base not in BASES:
            reason = "unknown_base"
        if reason is None and check_type not in check_types:
            reason = "unknown_check_type"
        if reason is None and entry is None:
            reason = "unknown_tail"
        if reason is None and entry.get("status") == "RETIRED":
            reason = "retired_tail"
        if reason is None and (avail_date is None or due_date is None):
            reason = "bad_date"
        if reason is None and (duration is None or duration < 1):
            reason = "bad_duration"
        if reason is None and rid not in published:
            reason = "no_published_start"
        if reason is not None:
            rejected.append({"request_id": rid, "line": number,
                             "reason": reason})
            counts[reason] += 1
            continue

        cls = entry.get("aircraft_class")
        rate = rates.get(cls)
        if rate is None:
            die(os.path.join(data_dir, "class_rates.yaml"),
                "no rates for class %s" % cls)
        spec = check_types[check_type]

        req = Request()
        req.rid = rid
        req.line = number
        req.tail = tail
        req.base = base
        req.check_type = check_type
        req.cls = cls
        req.segment = SEGMENT_OF_CLASS.get(cls)
        req.duration = duration
        max_compress = int(spec.get("max_compress_days", 0))
        if max_compress > duration - 1:
            max_compress = duration - 1
        if max_compress < 0:
            max_compress = 0
        req.max_compress = max_compress
        req.shifts_per_day = int(spec.get("overtime_shifts_per_day", 0))

        effective = avail_date
        if tail in revised:
            override = strict_date(revised[tail])
            if override is None:
                die(os.path.join(data_dir, "disruption_notice.md"),
                    "bad revised availability for %s" % tail)
            effective = override
        offset = (effective - season_start).days
        req.avail = offset if offset > 0 else 0

        req.due_offset = (due_date - season_start).days
        pub_date = strict_date(published[rid])
        req.pub_offset = None if pub_date is None else (
            pub_date - season_start).days
        req.rev = int(rate["revenue_per_day"])
        req.weight = int(rate["overdue_weight"])
        req.penalty = int(rate["deferral_penalty"])
        requests.append(req)

    # ---- packing factors so that plan terms add lexicographically
    mul_third = len(requests) + 1
    bound_second = sum(req.duration * req.rev for req in requests)
    bound_second += pool * max(shift_cost, 0) + 1
    mul_second = mul_third
    mul_first = (bound_second + 1) * mul_second

    base_reqs = {name: [] for name in BASES}
    for req in sorted(requests, key=lambda item: item.rid):
        base_reqs[req.base].append(req)

    per_base = {}
    for name in BASES:
        per_base[name] = plan_base(base_reqs[name], base_lines[name], pool,
                                   shift_cost, mul_first, mul_second)

    names, split, _scalar = choose_plan(per_base, base_reqs, pool)

    # ---- turn the winning day vectors into the plan
    plan = {}
    for name, shifts in zip(names, split):
        value = per_base[name][shifts]
        for position, req in enumerate(base_reqs[name]):
            start = value[1][position]
            finish = value[2][position]
            if start >= days:
                plan[req.rid] = {"req": req, "scheduled": False,
                                 "start": None, "finish": None}
            else:
                plan[req.rid] = {"req": req, "scheduled": True,
                                 "start": start, "finish": finish}

    def iso(offset):
        return (season_start + datetime.timedelta(days=offset)).isoformat()

    checks = []
    fleet_shifts = 0
    for rid in sorted(plan):
        item = plan[rid]
        req = item["req"]
        if item["scheduled"]:
            start = item["start"]
            finish = item["finish"]
            on_ground = finish - start + 1
            compress = req.duration - on_ground
            shifts = compress * req.shifts_per_day
            overdue = finish - req.due_offset
            if overdue < 0:
                overdue = 0
            moved = start != req.pub_offset
            fleet_shifts += shifts
            checks.append({
                "request_id": req.rid,
                "tail": req.tail,
                "base": req.base,
                "check_type": req.check_type,
                "aircraft_class": req.cls,
                "segment": req.segment,
                "decision": "scheduled",
                "start_date": iso(start),
                "finish_date": iso(finish),
                "compress_days": compress,
                "overtime_shifts": shifts,
                "overdue_days": overdue,
                "moved": moved,
                "deferral_reason": None,
            })
        else:
            line = base_lines[req.base]
            alone = False
            for compress in range(req.max_compress + 1):
                if line.earliest_start(req.duration - compress, req.avail) is not None:
                    alone = True
                    break
            checks.append({
                "request_id": req.rid,
                "tail": req.tail,
                "base": req.base,
                "check_type": req.check_type,
                "aircraft_class": req.cls,
                "segment": req.segment,
                "decision": "deferred",
                "start_date": None,
                "finish_date": None,
                "compress_days": 0,
                "overtime_shifts": 0,
                "overdue_days": 0,
                "moved": True,
                "deferral_reason": "plan_trade" if alone else "no_slot",
            })

    by_rid = {check["request_id"]: check for check in checks}

    def totals(selected):
        out = {
            "checks_scheduled": 0,
            "checks_deferred": 0,
            "compress_days": 0,
            "overtime_shifts": 0,
            "overdue_days": 0,
            "overdue_cost": 0,
            "deferral_cost": 0,
            "revenue_lost": 0,
            "moved": 0,
            "first_start": None,
            "last_finish": None,
        }
        for rid in selected:
            check = by_rid[rid]
            req = plan[rid]["req"]
            if check["moved"]:
                out["moved"] += 1
            if check["decision"] == "scheduled":
                out["checks_scheduled"] += 1
                out["compress_days"] += check["compress_days"]
                out["overtime_shifts"] += check["overtime_shifts"]
                out["overdue_days"] += check["overdue_days"]
                out["overdue_cost"] += check["overdue_days"] * req.weight
                on_ground = req.duration - check["compress_days"]
                out["revenue_lost"] += on_ground * req.rev
                if (out["first_start"] is None
                        or check["start_date"] < out["first_start"]):
                    out["first_start"] = check["start_date"]
                if (out["last_finish"] is None
                        or check["finish_date"] > out["last_finish"]):
                    out["last_finish"] = check["finish_date"]
            else:
                out["checks_deferred"] += 1
                out["deferral_cost"] += req.penalty
        return out

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "regions"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "segments"), exist_ok=True)

    def write(path, payload):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

    write(os.path.join(out_dir, "check_plan.json"),
          {"season": season, "checks": checks})

    base_totals = {}
    for name in BASES:
        selected = [req.rid for req in base_reqs[name]]
        body = totals(selected)
        base_totals[name] = body
        payload = {"base": name}
        payload.update(body)
        payload["fleet_overtime_used"] = fleet_shifts
        write(os.path.join(out_dir, "regions", "region_%s.json" % name.lower()),
              payload)

    segment_totals = {}
    for segment in SEGMENTS:
        selected = [check["request_id"] for check in checks
                    if check["segment"] == segment]
        body = totals(selected)
        segment_totals[segment] = body
        payload = {"segment": segment}
        payload.update(body)
        payload["fleet_overtime_used"] = fleet_shifts
        write(os.path.join(out_dir, "segments",
                           "segment_%s.json" % segment), payload)

    fleet = totals([check["request_id"] for check in checks])
    first_term = fleet["overdue_cost"] + fleet["deferral_cost"]
    second_term = fleet["revenue_lost"] + shift_cost * fleet_shifts
    third_term = fleet["moved"]

    write(os.path.join(out_dir, "plan_summary.json"), {
        "season": season,
        "plan_terms": {"first": first_term, "second": second_term,
                       "third": third_term},
        "overtime_pool_shifts": pool,
        "fleet_overtime_used": fleet_shifts,
        "checks_scheduled": fleet["checks_scheduled"],
        "checks_deferred": fleet["checks_deferred"],
        "moved": third_term,
        "bases": [{"base": name,
                   "checks_scheduled": base_totals[name]["checks_scheduled"],
                   "checks_deferred": base_totals[name]["checks_deferred"],
                   "overtime_shifts": base_totals[name]["overtime_shifts"]}
                  for name in BASES],
        "segments": [{"segment": segment,
                      "checks_scheduled":
                          segment_totals[segment]["checks_scheduled"],
                      "checks_deferred":
                          segment_totals[segment]["checks_deferred"]}
                     for segment in SEGMENTS],
    })

    write(os.path.join(out_dir, "data_quality.json"),
          {"rejected": rejected, "counts": counts})
    return 0


if __name__ == "__main__":
    sys.exit(main())
