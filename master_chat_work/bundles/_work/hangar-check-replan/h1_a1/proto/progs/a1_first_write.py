#!/usr/bin/env python3
"""Heavy check replan: derive the season plan and its reports."""

import csv
import json
import os
import re
import sys
import tomllib
import zipfile
import xml.etree.ElementTree as ET
from bisect import bisect_left
from datetime import date, timedelta

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

BASES = ["North", "South", "West", "East"]
SEGMENTS = ["commercial", "public"]
SEGMENT_OF = {"widebody": "commercial", "narrowbody": "commercial", "regional": "public"}
CLASS_ORDER = {"widebody": 0, "narrowbody": 1, "regional": 2}
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
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def die(path, msg):
    sys.stderr.write("cannot use input file %s: %s\n" % (path, msg))
    sys.exit(1)


def parse_iso(text):
    if text is None:
        return None
    text = str(text).strip()
    if not ISO_RE.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


# ---------------------------------------------------------------- input files


def read_toml(path):
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception as exc:
        die(path, exc)


def read_csv_rows(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            rows = []
            header = None
            for raw in reader:
                if header is None:
                    header = [c.strip() for c in raw]
                    continue
                if not raw or all(c.strip() == "" for c in raw):
                    continue
                rows.append((reader.line_num, dict(zip(header, raw))))
            if header is None:
                raise ValueError("empty file")
            return rows
    except Exception as exc:
        die(path, exc)


def read_jsonl(path):
    try:
        out = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out
    except Exception as exc:
        die(path, exc)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        die(path, exc)


def docx_tables(path):
    try:
        with zipfile.ZipFile(path) as zf:
            rels = ET.fromstring(zf.read("_rels/.rels"))
            target = None
            for rel in rels:
                if rel.get("Type", "").rsplit("/", 1)[-1] == "officeDocument":
                    target = rel.get("Target")
            if not target:
                raise ValueError("no officeDocument relationship")
            doc = ET.fromstring(zf.read(target.lstrip("/")))
    except Exception as exc:
        die(path, exc)
    tables = []
    for tbl in doc.iter(W + "tbl"):
        rows = []
        for tr in tbl.findall(W + "tr"):
            cells = []
            for tc in tr.findall(W + "tc"):
                cells.append("".join(t.text or "" for t in tc.iter(W + "t")).strip())
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def docx_table(tables, header, path):
    for rows in tables:
        if rows[0] == list(header):
            return [dict(zip(rows[0], r)) for r in rows[1:]]
    die(path, "no table with header " + ", ".join(header))


def whole(text, path):
    try:
        return int(str(text).strip())
    except Exception:
        die(path, "not a whole number: %r" % (text,))


# ------------------------------------------------------------------ planning


def feasible_starts(length, closed_prefix, nostart, days):
    """Start day indices of a check that is `length` days on ground."""
    out = []
    for s in range(1, days - length + 2):
        if closed_prefix[s + length - 1] - closed_prefix[s - 1]:
            continue
        if s in nostart:
            continue
        out.append(s)
    return out


def plan_base(reqs, days, pool, m3, m23):
    """Best plan of one base line for every amount of overtime shifts used.

    The value of a plan is (scalar, first, second, third, starts, finishes);
    `scalar` holds the three plan terms in one mixed-radix number so that the
    terms stay additive, and the day lists break ties.  Start and finish days
    are day indices in request_id order, season end + 1 when deferred.
    """
    n = len(reqs)
    if n == 0:
        return {0: (0, 0, 0, 0, (), ())}

    opts = []
    for r in reqs:
        per = []
        for c in range(0, r["max_compress"] + 1):
            length = r["duration"] - c
            starts = r["starts_by_length"][length]
            per.append((c * r["shifts_per_day"], starts, set(starts), length))
        opts.append(per)

    defer_cache = {}

    def defer_part(mask):
        got = defer_cache.get(mask)
        if got is None:
            t1 = 0
            t3 = 0
            for j in range(n):
                if not (mask >> j) & 1:
                    t1 += reqs[j]["deferral_penalty"]
                    t3 += 1
            got = (t1 * m23 + t3, t1, t3)
            defer_cache[mask] = got
        return got

    full = (1 << n) - 1
    zeros = (0,) * n
    by_day = [dict() for _ in range(days + 3)]
    by_day[1][(0, 0)] = (0, 0, 0, 0, zeros, zeros)
    best = {}

    for d in range(1, days + 2):
        layer = by_day[d]
        if not layer:
            continue
        for (mask, used), val in layer.items():
            if mask != full:
                dscalar, dt1, dt3 = defer_part(mask)
                fs = list(val[4])
                ff = list(val[5])
                for j in range(n):
                    if not (mask >> j) & 1:
                        fs[j] = days + 1
                        ff[j] = days + 1
                fin = (
                    val[0] + dscalar,
                    val[1] + dt1,
                    val[2],
                    val[3] + dt3,
                    tuple(fs),
                    tuple(ff),
                )
            else:
                fin = val
            cur = best.get(used)
            if cur is None or fin < cur:
                best[used] = fin
            if d > days:
                continue
            for j in range(n):
                if (mask >> j) & 1:
                    continue
                r = reqs[j]
                low = d if d > r["avail"] else r["avail"]
                pub = r["pub_idx"]
                for shifts, starts, startset, length in opts[j]:
                    if used + shifts > pool:
                        continue
                    i = bisect_left(starts, low)
                    if i >= len(starts):
                        continue
                    s0 = starts[i]
                    cands = (s0, pub) if (pub is not None and pub > s0 and pub in startset) else (s0,)
                    for s in cands:
                        f = s + length - 1
                        over = f - r["due_idx"]
                        if over < 0:
                            over = 0
                        t1 = over * r["overdue_weight"]
                        t2 = length * r["revenue_per_day"] + r["shift_cost"] * shifts
                        t3 = 0 if s == pub else 1
                        nv = (
                            val[0] + t1 * m23 + t2 * m3 + t3,
                            val[1] + t1,
                            val[2] + t2,
                            val[3] + t3,
                            val[4][:j] + (s,) + val[4][j + 1 :],
                            val[5][:j] + (f,) + val[5][j + 1 :],
                        )
                        key = (mask | (1 << j), used + shifts)
                        slot = by_day[f + 1]
                        prev = slot.get(key)
                        if prev is None or nv < prev:
                            slot[key] = nv
    return best


def merge_bases(base_options, pool, total):
    """Combine the per-base plans under the one shared overtime pool."""
    zeros = (0,) * total
    cur = {0: (0, 0, 0, 0, zeros, zeros)}
    for positions, options in base_options:
        spread = []
        for shifts in sorted(options):
            if shifts > pool:
                continue
            val = options[shifts]
            starts = [0] * total
            finishes = [0] * total
            for local, pos in enumerate(positions):
                starts[pos] = val[4][local]
                finishes[pos] = val[5][local]
            spread.append((shifts, val[0], val[1], val[2], val[3], starts, finishes))
        nxt = {}
        for k1, v1 in cur.items():
            for shifts, sc, t1, t2, t3, starts, finishes in spread:
                k = k1 + shifts
                if k > pool:
                    continue
                cand = (
                    v1[0] + sc,
                    v1[1] + t1,
                    v1[2] + t2,
                    v1[3] + t3,
                    tuple(a + b for a, b in zip(v1[4], starts)),
                    tuple(a + b for a, b in zip(v1[5], finishes)),
                )
                prev = nxt.get(k)
                if prev is None or cand < prev:
                    nxt[k] = cand
        cur = nxt
        if not cur:
            return None
    return min(cur.values())


# -------------------------------------------------------------------- report


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]

    p_limits = os.path.join(data_dir, "fleet_limits.toml")
    p_register = os.path.join(data_dir, "fleet_register.csv")
    p_requests = os.path.join(data_dir, "check_requests.csv")
    p_published = os.path.join(data_dir, "published_plan.csv")
    p_calendar = os.path.join(data_dir, "base_calendar.jsonl")
    p_notice = os.path.join(data_dir, "disruption_notice.docx")
    p_planning = os.path.join(data_dir, "planning_limits.docx")
    p_types = os.path.join(data_dir, "check_types.json")

    limits = read_toml(p_limits)
    try:
        season = limits["season"]
        season_start = date.fromisoformat(str(limits["season_start"]))
        season_end = date.fromisoformat(str(limits["season_end"]))
    except Exception as exc:
        die(p_limits, exc)
    days = (season_end - season_start).days + 1
    if days < 1:
        die(p_limits, "season_end is before season_start")

    def to_idx(day):
        return (day - season_start).days + 1

    def to_date(idx):
        return season_start + timedelta(days=idx - 1)

    register = {}
    for _, row in read_csv_rows(p_register):
        tail = (row.get("tail") or "").strip()
        if tail and tail not in register:
            register[tail] = {
                "aircraft_class": (row.get("aircraft_class") or "").strip(),
                "status": (row.get("status") or "").strip(),
            }

    published = {}
    for _, row in read_csv_rows(p_published):
        rid = (row.get("request_id") or "").strip()
        if rid and rid not in published:
            published[rid] = (row.get("published_start") or "").strip()

    check_types = read_json(p_types)
    if not isinstance(check_types, dict):
        die(p_types, "not an object")

    notice = docx_tables(p_notice)
    closures = docx_table(notice, ["base", "from", "days"], p_notice)
    revised = docx_table(notice, ["tail", "available_from"], p_notice)

    planning = docx_tables(p_planning)
    item_rows = docx_table(planning, ["item", "value"], p_planning)
    class_rows = docx_table(
        planning,
        ["class", "revenue_per_day", "overdue_weight", "deferral_penalty"],
        p_planning,
    )
    grant_rows = docx_table(planning, ["base", "allowance_shifts"], p_planning)

    items = {r["item"].strip(): r["value"].strip() for r in item_rows}
    for key in ("overtime_pool_shifts", "shift_cost"):
        if key not in items:
            die(p_planning, "missing item " + key)
    pool = whole(items["overtime_pool_shifts"], p_planning)
    shift_cost = whole(items["shift_cost"], p_planning)

    rates = {}
    for r in class_rows:
        rates[r["class"].strip()] = {
            "revenue_per_day": whole(r["revenue_per_day"], p_planning),
            "overdue_weight": whole(r["overdue_weight"], p_planning),
            "deferral_penalty": whole(r["deferral_penalty"], p_planning),
        }
    grants = {b: 0 for b in BASES}
    for r in grant_rows:
        b = r["base"].strip()
        if b in grants:
            grants[b] = whole(r["allowance_shifts"], p_planning)

    revised_avail = {}
    for r in revised:
        tail = r["tail"].strip()
        day = parse_iso(r["available_from"])
        if tail and day is not None:
            revised_avail[tail] = day

    closed = {b: set() for b in BASES}
    nostart = {b: set() for b in BASES}
    for obj in read_jsonl(p_calendar):
        base = obj.get("base")
        if base not in closed:
            continue
        day = parse_iso(obj.get("date"))
        if day is None or not (season_start <= day <= season_end):
            continue
        status = obj.get("status")
        if status == "CLOSED":
            closed[base].add(to_idx(day))
        elif status == "NO_START":
            nostart[base].add(to_idx(day))
    for r in closures:
        base = r["base"].strip()
        if base not in closed:
            continue
        first = parse_iso(r["from"])
        if first is None:
            die(p_notice, "bad closure date %r" % (r["from"],))
        for k in range(whole(r["days"], p_notice)):
            day = first + timedelta(days=k)
            if season_start <= day <= season_end:
                closed[base].add(to_idx(day))
    closed_prefix = {}
    for base in BASES:
        pref = [0] * (days + 2)
        run = 0
        for i in range(1, days + 1):
            if i in closed[base]:
                run += 1
            pref[i] = run
        pref[days + 1] = run
        closed_prefix[base] = pref

    # ------------------------------------------------------- read the requests
    requests = []
    rejected = []
    seen = set()
    for line, row in read_csv_rows(p_requests):
        if (row.get("season") or "").strip() != str(season):
            continue
        if (row.get("status") or "").strip() != "OPEN":
            continue
        rid = (row.get("request_id") or "").strip()
        tail = (row.get("tail") or "").strip()
        base = (row.get("base") or "").strip()
        ctype = (row.get("check_type") or "").strip()
        avail = parse_iso(row.get("available_from"))
        due = parse_iso(row.get("due_date"))
        try:
            duration = int((row.get("duration_days") or "").strip())
        except Exception:
            duration = None

        reason = None
        if rid in seen:
            reason = "duplicate_request"
        elif base not in BASES:
            reason = "unknown_base"
        elif ctype not in check_types:
            reason = "unknown_check_type"
        elif tail not in register:
            reason = "unknown_tail"
        elif register[tail]["status"] == "RETIRED":
            reason = "retired_tail"
        elif avail is None or due is None:
            reason = "bad_date"
        elif duration is None or duration < 1:
            reason = "bad_duration"
        elif rid not in published:
            reason = "no_published_start"
        seen.add(rid)
        if reason is not None:
            rejected.append({"request_id": rid, "line": line, "reason": reason})
            continue

        cls = register[tail]["aircraft_class"]
        if cls not in rates:
            die(p_planning, "no class rates for " + cls)
        info = check_types[ctype]
        try:
            max_compress = int(info["max_compress_days"])
            shifts_per_day = int(info["overtime_shifts_per_day"])
        except Exception as exc:
            die(p_types, exc)

        avail_idx = to_idx(revised_avail.get(tail, avail))
        if avail_idx < 1:
            avail_idx = 1
        pub_date = parse_iso(published[rid])
        pub_idx = to_idx(pub_date) if pub_date is not None else None
        if pub_idx is not None and not (1 <= pub_idx <= days):
            pub_idx = None

        requests.append(
            {
                "request_id": rid,
                "tail": tail,
                "base": base,
                "check_type": ctype,
                "aircraft_class": cls,
                "segment": SEGMENT_OF.get(cls),
                "duration": duration,
                "due_date": due,
                "due_idx": to_idx(due),
                "avail": avail_idx,
                "pub_idx": pub_idx,
                "max_compress": min(max_compress, duration - 1),
                "shifts_per_day": shifts_per_day,
                "revenue_per_day": rates[cls]["revenue_per_day"],
                "overdue_weight": rates[cls]["overdue_weight"],
                "deferral_penalty": rates[cls]["deferral_penalty"],
                "shift_cost": shift_cost,
            }
        )

    requests.sort(key=lambda r: r["request_id"])
    total = len(requests)
    index_of = {r["request_id"]: i for i, r in enumerate(requests)}

    # mixed radix weights that keep the three plan terms in one number
    m3 = total + 1
    m2 = shift_cost * max(pool, 0) + 1
    for r in requests:
        m2 += r["duration"] * r["revenue_per_day"]
    m23 = m2 * m3

    length_starts = {}
    for r in requests:
        table = {}
        for c in range(0, r["max_compress"] + 1):
            length = r["duration"] - c
            key = (r["base"], length)
            got = length_starts.get(key)
            if got is None:
                got = feasible_starts(
                    length, closed_prefix[r["base"]], nostart[r["base"]], days
                )
                length_starts[key] = got
            table[length] = got
        r["starts_by_length"] = table
        r["can_fit_alone"] = any(
            bisect_left(starts, r["avail"]) < len(starts) for starts in table.values()
        )

    base_options = []
    for base in BASES:
        reqs = [r for r in requests if r["base"] == base]
        positions = [index_of[r["request_id"]] for r in reqs]
        base_options.append((positions, plan_base(reqs, days, pool, m3, m23)))

    winner = merge_bases(base_options, pool, total)
    if winner is None:
        die(p_planning, "no plan keeps the overtime pool")
    _, term1, term2, term3, starts, finishes = winner

    # --------------------------------------------------------- build the plan
    checks = []
    for i, r in enumerate(requests):
        s = starts[i]
        if s == days + 1:
            checks.append(
                {
                    "request_id": r["request_id"],
                    "tail": r["tail"],
                    "base": r["base"],
                    "check_type": r["check_type"],
                    "aircraft_class": r["aircraft_class"],
                    "segment": r["segment"],
                    "decision": "deferred",
                    "start_date": None,
                    "finish_date": None,
                    "compress_days": 0,
                    "overtime_shifts": 0,
                    "overdue_days": 0,
                    "moved": True,
                    "deferral_reason": "plan_trade" if r["can_fit_alone"] else "no_slot",
                    "overtime_cost": 0,
                    "allowance_shifts": 0,
                    "paid_shifts": 0,
                    "allowance_credit": 0,
                    "settled_overtime_cost": 0,
                    "_req": r,
                }
            )
            continue
        f = finishes[i]
        length = f - s + 1
        compress = r["duration"] - length
        shifts = compress * r["shifts_per_day"]
        checks.append(
            {
                "request_id": r["request_id"],
                "tail": r["tail"],
                "base": r["base"],
                "check_type": r["check_type"],
                "aircraft_class": r["aircraft_class"],
                "segment": r["segment"],
                "decision": "scheduled",
                "start_date": to_date(s).isoformat(),
                "finish_date": to_date(f).isoformat(),
                "compress_days": compress,
                "overtime_shifts": shifts,
                "overdue_days": max(0, f - r["due_idx"]),
                "moved": s != r["pub_idx"],
                "deferral_reason": None,
                "overtime_cost": shift_cost * shifts,
                "allowance_shifts": 0,
                "paid_shifts": shifts,
                "allowance_credit": 0,
                "settled_overtime_cost": shift_cost * shifts,
                "_req": r,
            }
        )

    # ---------------------------------------------- settle the fleet allowance
    allowance_granted = sum(grants[b] for b in BASES)
    left = allowance_granted
    order = sorted(
        (c for c in checks if c["decision"] == "scheduled"),
        key=lambda c: (
            CLASS_ORDER.get(c["aircraft_class"], len(CLASS_ORDER)),
            c["_req"]["due_date"],
            c["request_id"],
        ),
    )
    for c in order:
        take = min(c["overtime_shifts"], left)
        c["allowance_shifts"] = take
        c["paid_shifts"] = c["overtime_shifts"] - take
        c["allowance_credit"] = shift_cost * take
        c["settled_overtime_cost"] = c["overtime_cost"] - c["allowance_credit"]
        left -= take

    fleet_overtime_used = sum(c["overtime_shifts"] for c in checks)

    def totals(group):
        t = {
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
            "fleet_overtime_used": fleet_overtime_used,
            "overtime_cost": 0,
            "allowance_credit": 0,
            "settled_overtime_cost": 0,
            "allowance_used": 0,
        }
        for c in group:
            r = c["_req"]
            if c["moved"]:
                t["moved"] += 1
            t["overtime_cost"] += c["overtime_cost"]
            t["allowance_credit"] += c["allowance_credit"]
            t["settled_overtime_cost"] += c["settled_overtime_cost"]
            t["allowance_used"] += c["allowance_shifts"]
            if c["decision"] == "deferred":
                t["checks_deferred"] += 1
                t["deferral_cost"] += r["deferral_penalty"]
                continue
            t["checks_scheduled"] += 1
            t["compress_days"] += c["compress_days"]
            t["overtime_shifts"] += c["overtime_shifts"]
            t["overdue_days"] += c["overdue_days"]
            t["overdue_cost"] += c["overdue_days"] * r["overdue_weight"]
            t["revenue_lost"] += (r["duration"] - c["compress_days"]) * r["revenue_per_day"]
            if t["first_start"] is None or c["start_date"] < t["first_start"]:
                t["first_start"] = c["start_date"]
            if t["last_finish"] is None or c["finish_date"] > t["last_finish"]:
                t["last_finish"] = c["finish_date"]
        return t

    field_order = [
        "checks_scheduled",
        "checks_deferred",
        "compress_days",
        "overtime_shifts",
        "overdue_days",
        "overdue_cost",
        "deferral_cost",
        "revenue_lost",
        "moved",
        "first_start",
        "last_finish",
        "fleet_overtime_used",
        "overtime_cost",
        "allowance_credit",
        "settled_overtime_cost",
        "allowance_used",
    ]

    os.makedirs(out_dir, exist_ok=True)

    def write(name, payload):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    audit = [
        {
            "request_id": c["request_id"],
            "tail": c["tail"],
            "base": c["base"],
            "check_type": c["check_type"],
            "aircraft_class": c["aircraft_class"],
            "segment": c["segment"],
            "decision": c["decision"],
            "start_date": c["start_date"],
            "finish_date": c["finish_date"],
            "compress_days": c["compress_days"],
            "overtime_shifts": c["overtime_shifts"],
            "overdue_days": c["overdue_days"],
            "moved": c["moved"],
            "deferral_reason": c["deferral_reason"],
            "overtime_cost": c["overtime_cost"],
            "allowance_shifts": c["allowance_shifts"],
            "paid_shifts": c["paid_shifts"],
            "allowance_credit": c["allowance_credit"],
            "settled_overtime_cost": c["settled_overtime_cost"],
        }
        for c in checks
    ]
    write("policy_audit.json", {"season": season, "checks": audit})

    base_totals = {}
    for base in BASES:
        t = totals([c for c in checks if c["base"] == base])
        base_totals[base] = t
        doc = {"base": base}
        for key in field_order:
            doc[key] = t[key]
        doc["allowance_granted"] = grants[base]
        write("region_%s.json" % base, doc)

    segment_totals = {}
    for segment in SEGMENTS:
        t = totals([c for c in checks if c["segment"] == segment])
        segment_totals[segment] = t
        doc = {"segment": segment}
        for key in field_order:
            doc[key] = t[key]
        write("segment_%s.json" % segment, doc)

    allowance_used = sum(c["allowance_shifts"] for c in checks)
    write(
        "summary.json",
        {
            "season": season,
            "plan_terms": {"first": term1, "second": term2, "third": term3},
            "overtime_pool_shifts": pool,
            "fleet_overtime_used": fleet_overtime_used,
            "checks_scheduled": sum(1 for c in checks if c["decision"] == "scheduled"),
            "checks_deferred": sum(1 for c in checks if c["decision"] == "deferred"),
            "moved": sum(1 for c in checks if c["moved"]),
            "settlement": {
                "allowance_granted": allowance_granted,
                "allowance_used": allowance_used,
                "allowance_left": allowance_granted - allowance_used,
                "overtime_cost": sum(c["overtime_cost"] for c in checks),
                "allowance_credit": sum(c["allowance_credit"] for c in checks),
                "settled_overtime_cost": sum(c["settled_overtime_cost"] for c in checks),
            },
            "bases": [
                {
                    "base": base,
                    "checks_scheduled": base_totals[base]["checks_scheduled"],
                    "checks_deferred": base_totals[base]["checks_deferred"],
                    "overtime_shifts": base_totals[base]["overtime_shifts"],
                    "allowance_granted": grants[base],
                    "allowance_used": base_totals[base]["allowance_used"],
                    "settled_overtime_cost": base_totals[base]["settled_overtime_cost"],
                }
                for base in BASES
            ],
            "segments": [
                {
                    "segment": segment,
                    "checks_scheduled": segment_totals[segment]["checks_scheduled"],
                    "checks_deferred": segment_totals[segment]["checks_deferred"],
                }
                for segment in SEGMENTS
            ],
        },
    )

    counts = {reason: 0 for reason in REASONS}
    for row in rejected:
        counts[row["reason"]] += 1
    write("data_quality.json", {"rejected": rejected, "counts": counts})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
