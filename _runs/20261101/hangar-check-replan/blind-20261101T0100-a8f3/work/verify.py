#!/usr/bin/env python3
"""Independent self-check of the shipped outputs against the shipped data."""
import csv, datetime, json, os, sys, collections

BLIND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BLIND, "environment", "data")
OUT = os.path.join(BLIND, "out")
sys.path.insert(0, os.path.join(BLIND, "app"))
import derive_report as dr

inp = dr.load_inputs(DATA)
accepted, rejected = dr.screen_requests(inp)
total_days, closed, nostart = dr.build_calendars(inp)
D = (inp.season_end - inp.season_start).days + 1

plan = json.load(open(os.path.join(OUT, "check_plan.json")))
summary = json.load(open(os.path.join(OUT, "plan_summary.json")))
dq = json.load(open(os.path.join(OUT, "data_quality.json")))

problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)


# --- shape
check(plan["season"] == inp.season, "check_plan season")
check(len(plan["checks"]) == len(accepted),
      "check count %d vs accepted %d" % (len(plan["checks"]), len(accepted)))
ids = [c["request_id"] for c in plan["checks"]]
check(ids == sorted(ids), "checks not sorted by request_id")
check(set(ids) == set(r["request_id"] for r in accepted), "check id set mismatch")
fields = ["request_id", "tail", "base", "check_type", "aircraft_class", "segment",
          "decision", "start_date", "finish_date", "compress_days",
          "overtime_shifts", "overdue_days", "moved", "deferral_reason"]
for c in plan["checks"]:
    check(list(c.keys()) == fields, "fields %s" % c["request_id"])

byid = {r["request_id"]: r for r in accepted}

# --- per-check rules
occupied = collections.defaultdict(set)
first = second = third = 0
fleet_shifts = 0
for c in plan["checks"]:
    r = byid[c["request_id"]]
    rate = inp.rates[r["aircraft_class"]]
    spec = inp.check_types[r["check_type"]]
    check(c["tail"] == r["tail"] and c["base"] == r["base"]
          and c["check_type"] == r["check_type"], "row fields %s" % c["request_id"])
    check(c["aircraft_class"] == r["aircraft_class"], "class %s" % c["request_id"])
    check(c["segment"] == dr.SEGMENT_OF_CLASS[r["aircraft_class"]],
          "segment %s" % c["request_id"])
    avail = r["available_from"]
    if avail < inp.season_start:
        avail = inp.season_start
    if c["decision"] == "deferred":
        check(c["start_date"] is None and c["finish_date"] is None,
              "deferred dates %s" % c["request_id"])
        check(c["compress_days"] == 0 and c["overtime_shifts"] == 0
              and c["overdue_days"] == 0, "deferred zeros %s" % c["request_id"])
        check(c["moved"] is True, "deferred moved %s" % c["request_id"])
        check(c["deferral_reason"] in ("no_slot", "plan_trade"),
              "reason %s" % c["request_id"])
        expected = dr.deferral_reason(r, total_days, closed[r["base"]],
                                      nostart[r["base"]], inp)
        check(c["deferral_reason"] == expected,
              "reason %s got %s want %s" % (c["request_id"], c["deferral_reason"],
                                            expected))
        first += rate["deferral_penalty"]
        third += 1
        continue
    check(c["deferral_reason"] is None, "scheduled reason %s" % c["request_id"])
    s = datetime.date.fromisoformat(c["start_date"])
    f = datetime.date.fromisoformat(c["finish_date"])
    length = (f - s).days + 1
    cd = c["compress_days"]
    check(length == r["duration_days"] - cd,
          "span %s len %d p %d c %d" % (c["request_id"], length,
                                        r["duration_days"], cd))
    check(0 <= cd <= min(spec["max_compress_days"], r["duration_days"] - 1),
          "compress range %s" % c["request_id"])
    check(c["overtime_shifts"] == cd * spec["overtime_shifts_per_day"],
          "shifts %s" % c["request_id"])
    check(s >= avail, "start before available %s start %s avail %s"
          % (c["request_id"], s, avail))
    check(f <= inp.season_end, "finish after season end %s" % c["request_id"])
    si = (s - inp.season_start).days
    fi = (f - inp.season_start).days
    check(si >= 0, "start before season %s" % c["request_id"])
    check(not closed[r["base"]][si], "start on closed day %s" % c["request_id"])
    check(not nostart[r["base"]][si], "start on no-start day %s" % c["request_id"])
    for d in range(si, fi + 1):
        check(not closed[r["base"]][d], "closed day inside span %s" % c["request_id"])
    span = set(range(si, fi + 1))
    check(not (span & occupied[r["base"]]), "line overlap %s" % c["request_id"])
    occupied[r["base"]] |= span
    late = max(0, (f - r["due_date"]).days)
    check(c["overdue_days"] == late, "overdue %s got %d want %d"
          % (c["request_id"], c["overdue_days"], late))
    check(c["moved"] == (c["start_date"] != r["published_start"]),
          "moved %s" % c["request_id"])
    first += late * rate["overdue_weight"]
    second += length * rate["revenue_per_day"] + \
        c["overtime_shifts"] * inp.shift_cost
    third += 1 if c["moved"] else 0
    fleet_shifts += c["overtime_shifts"]

check(summary["plan_terms"] == {"first": first, "second": second, "third": third},
      "plan_terms %s vs recomputed %s" % (summary["plan_terms"],
                                          (first, second, third)))
check(summary["fleet_overtime_used"] == fleet_shifts,
      "fleet_overtime_used %s vs %s" % (summary["fleet_overtime_used"], fleet_shifts))
check(fleet_shifts <= inp.overtime_pool_shifts, "overtime pool exceeded")
check(summary["overtime_pool_shifts"] == inp.overtime_pool_shifts, "pool value")
check(summary["season"] == inp.season, "summary season")

sched = [c for c in plan["checks"] if c["decision"] == "scheduled"]
defer = [c for c in plan["checks"] if c["decision"] == "deferred"]
check(summary["checks_scheduled"] == len(sched), "summary scheduled")
check(summary["checks_deferred"] == len(defer), "summary deferred")
check(summary["moved"] == sum(1 for c in plan["checks"] if c["moved"]), "summary moved")
check([b["base"] for b in summary["bases"]] == dr.BASES, "bases order")
check([s["segment"] for s in summary["segments"]] == dr.SEGMENTS, "segments order")

# --- region / segment totals
def totals_for(rows):
    t = dict(checks_scheduled=0, checks_deferred=0, compress_days=0,
             overtime_shifts=0, overdue_days=0, overdue_cost=0, deferral_cost=0,
             revenue_lost=0, moved=0, first_start=None, last_finish=None)
    for c in rows:
        r = byid[c["request_id"]]
        rate = inp.rates[r["aircraft_class"]]
        if c["decision"] == "scheduled":
            t["checks_scheduled"] += 1
            t["compress_days"] += c["compress_days"]
            t["overtime_shifts"] += c["overtime_shifts"]
            t["overdue_days"] += c["overdue_days"]
            t["overdue_cost"] += c["overdue_days"] * rate["overdue_weight"]
            t["revenue_lost"] += (r["duration_days"] - c["compress_days"]) \
                * rate["revenue_per_day"]
            if t["first_start"] is None or c["start_date"] < t["first_start"]:
                t["first_start"] = c["start_date"]
            if t["last_finish"] is None or c["finish_date"] > t["last_finish"]:
                t["last_finish"] = c["finish_date"]
        else:
            t["checks_deferred"] += 1
            t["deferral_cost"] += rate["deferral_penalty"]
        if c["moved"]:
            t["moved"] += 1
    t["fleet_overtime_used"] = fleet_shifts
    return t

for base in dr.BASES:
    path = os.path.join(OUT, "regions", "region_%s.json" % base.lower())
    check(os.path.isfile(path), "missing %s" % path)
    got = json.load(open(path))
    check(got.get("base") == base, "region key %s" % base)
    want = totals_for([c for c in plan["checks"] if c["base"] == base])
    for k, v in want.items():
        check(got.get(k) == v, "region %s %s got %r want %r" % (base, k, got.get(k), v))
    row = [b for b in summary["bases"] if b["base"] == base][0]
    check(row["checks_scheduled"] == want["checks_scheduled"]
          and row["checks_deferred"] == want["checks_deferred"]
          and row["overtime_shifts"] == want["overtime_shifts"],
          "summary base row %s" % base)

for seg in dr.SEGMENTS:
    path = os.path.join(OUT, "segments", "segment_%s.json" % seg)
    check(os.path.isfile(path), "missing %s" % path)
    got = json.load(open(path))
    check(got.get("segment") == seg, "segment key %s" % seg)
    want = totals_for([c for c in plan["checks"] if c["segment"] == seg])
    for k, v in want.items():
        check(got.get(k) == v, "segment %s %s got %r want %r" % (seg, k, got.get(k), v))
    row = [s for s in summary["segments"] if s["segment"] == seg][0]
    check(row["checks_scheduled"] == want["checks_scheduled"]
          and row["checks_deferred"] == want["checks_deferred"],
          "summary segment row %s" % seg)

# --- data quality
check(dq["rejected"] == rejected, "rejected list")
check(set(dq["counts"]) == set(dr.REJECT_REASONS), "counts keys")
check(sum(dq["counts"].values()) == len(dq["rejected"]), "counts sum")
cc = collections.Counter(r["reason"] for r in dq["rejected"])
for k in dr.REJECT_REASONS:
    check(dq["counts"][k] == cc.get(k, 0), "count %s" % k)

print("season %s  days %d  accepted %d  rejected %d" %
      (inp.season, D, len(accepted), len(rejected)))
print("terms first=%d second=%d third=%d  overtime %d/%d" %
      (first, second, third, fleet_shifts, inp.overtime_pool_shifts))
print("scheduled %d deferred %d moved %d" % (len(sched), len(defer),
                                             sum(1 for c in plan["checks"] if c["moved"])))
if problems:
    print("FAIL (%d)" % len(problems))
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("PASS")
