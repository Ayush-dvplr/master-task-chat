import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import derive_report as dr

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
data_dir = os.path.join(root, "environment", "data")
out_dir = os.path.join(root, "out")

data = dr.load_inputs(data_dir)
data["data_dir"] = data_dir
requests, rejected = dr.screen_requests(data)
lines = dr.build_base_lines(data)
by_id = dict((item["request_id"], item) for item in requests)

plan = json.load(open(os.path.join(out_dir, "check_plan.json")))
summary = json.load(open(os.path.join(out_dir, "plan_summary.json")))
quality = json.load(open(os.path.join(out_dir, "data_quality.json")))
regions = dict(
    (base, json.load(open(os.path.join(out_dir, "regions", "region_%s.json" % base.lower()))))
    for base in dr.BASES
)
segments = dict(
    (seg, json.load(open(os.path.join(out_dir, "segments", "segment_%s.json" % seg))))
    for seg in dr.SEGMENTS
)

problems = []


def check(flag, message):
    if not flag:
        problems.append(message)


season_start = data["season_start"]
season_end = data["season_end"]

check(plan["season"] == data["season"], "check_plan season mismatch")
check(len(plan["checks"]) == len(requests), "check_plan row count != open accepted rows")
check(
    [row["request_id"] for row in plan["checks"]]
    == sorted(item["request_id"] for item in requests),
    "check_plan is not sorted by request_id",
)
fields = [
    "request_id", "tail", "base", "check_type", "aircraft_class", "segment",
    "decision", "start_date", "finish_date", "compress_days", "overtime_shifts",
    "overdue_days", "moved", "deferral_reason", "overtime_cost",
    "allowance_shifts", "paid_shifts", "allowance_credit",
    "settled_overtime_cost",
]
for row in plan["checks"]:
    check(sorted(row.keys()) == sorted(fields), "field set wrong for %s" % row["request_id"])

per_base_used = {}
occupied = {}
total_shifts = 0
for row in plan["checks"]:
    rid = row["request_id"]
    src = by_id[rid]
    base = row["base"]
    check(row["tail"] == src["tail"], "%s tail" % rid)
    check(row["base"] == src["base"], "%s base" % rid)
    check(row["check_type"] == src["check_type"], "%s type" % rid)
    check(row["aircraft_class"] == src["aircraft_class"], "%s class" % rid)
    check(row["segment"] == dr.CLASS_SEGMENT[src["aircraft_class"]], "%s segment" % rid)
    max_compress = min(
        data["check_types"][src["check_type"]][0], src["duration"] - 1
    )
    per_day = data["check_types"][src["check_type"]][1]
    if row["decision"] == "scheduled":
        start = date.fromisoformat(row["start_date"])
        finish = date.fromisoformat(row["finish_date"])
        check(row["deferral_reason"] is None, "%s reason on scheduled" % rid)
        check(0 <= row["compress_days"] <= max_compress, "%s compress range" % rid)
        ground = src["duration"] - row["compress_days"]
        check(
            (finish - start).days + 1 == ground,
            "%s window length %s vs %s" % (rid, (finish - start).days + 1, ground),
        )
        check(start >= src["available"], "%s starts before available day" % rid)
        check(finish <= season_end, "%s finishes after season end" % rid)
        line = lines[base]
        s_idx = (start - season_start).days + 1
        f_idx = (finish - season_start).days + 1
        check(line.can_start[s_idx], "%s starts on a closed/no-start day" % rid)
        for idx in range(s_idx, f_idx + 1):
            check(not line.closed[idx], "%s spans a closed day" % rid)
        for idx in range(s_idx, f_idx + 1):
            key = (base, idx)
            check(key not in occupied, "%s overlaps %s on %s" % (rid, occupied.get(key), base))
            occupied[key] = rid
        expected_overdue = max(0, (finish - src["due"]).days)
        check(row["overdue_days"] == expected_overdue, "%s overdue days" % rid)
        check(
            row["overtime_shifts"] == row["compress_days"] * per_day,
            "%s overtime shifts" % rid,
        )
        pub = row["start_date"] != src["published_start"]
        check(row["moved"] == pub, "%s moved flag" % rid)
        total_shifts += row["overtime_shifts"]
        per_base_used[base] = per_base_used.get(base, 0) + row["allowance_shifts"]
    else:
        check(row["decision"] == "deferred", "%s bad decision" % rid)
        check(row["start_date"] is None and row["finish_date"] is None, "%s dates" % rid)
        check(
            row["compress_days"] == 0
            and row["overtime_shifts"] == 0
            and row["overdue_days"] == 0,
            "%s deferred zeros" % rid,
        )
        check(row["moved"] is True, "%s deferred must be moved" % rid)
        check(
            row["deferral_reason"] in ("no_slot", "plan_trade"),
            "%s deferral reason" % rid,
        )
        check(
            row["overtime_cost"] == 0
            and row["allowance_shifts"] == 0
            and row["paid_shifts"] == 0
            and row["allowance_credit"] == 0
            and row["settled_overtime_cost"] == 0,
            "%s deferred settlement zeros" % rid,
        )
    check(
        row["overtime_cost"] == data["shift_cost"] * row["overtime_shifts"],
        "%s overtime cost" % rid,
    )
    check(
        row["allowance_shifts"] + row["paid_shifts"] == row["overtime_shifts"],
        "%s shift split" % rid,
    )
    check(
        row["allowance_credit"] == data["shift_cost"] * row["allowance_shifts"],
        "%s allowance credit" % rid,
    )
    check(
        row["settled_overtime_cost"] == row["overtime_cost"] - row["allowance_credit"],
        "%s settled cost" % rid,
    )

check(total_shifts <= data["overtime_pool_shifts"], "fleet overtime exceeds the pool")
check(summary["fleet_overtime_used"] == total_shifts, "summary fleet_overtime_used")
check(summary["overtime_pool_shifts"] == data["overtime_pool_shifts"], "summary pool")

granted = sum(data["allowances"][base] for base in dr.BASES)
used = sum(row["allowance_shifts"] for row in plan["checks"])
check(summary["settlement"]["allowance_granted"] == granted, "granted total")
check(summary["settlement"]["allowance_used"] == used, "used total")
check(
    summary["settlement"]["allowance_left"] == granted - used, "allowance left"
)
check(used == min(granted, total_shifts), "allowance should be spent greedily")

order = sorted(
    [row for row in plan["checks"] if row["decision"] == "scheduled"],
    key=lambda row: (
        dr.CLASS_ORDER.index(row["aircraft_class"]),
        by_id[row["request_id"]]["due"],
        row["request_id"],
    ),
)
left = granted
for row in order:
    expect = min(row["overtime_shifts"], left)
    left -= expect
    check(row["allowance_shifts"] == expect, "%s allowance order" % row["request_id"])

sched = [row for row in plan["checks"] if row["decision"] == "scheduled"]
defer = [row for row in plan["checks"] if row["decision"] == "deferred"]
check(summary["checks_scheduled"] == len(sched), "summary scheduled")
check(summary["checks_deferred"] == len(defer), "summary deferred")
check(
    summary["moved"] == sum(1 for row in plan["checks"] if row["moved"]),
    "summary moved",
)
first = sum(
    row["overdue_days"] * data["class_params"][row["aircraft_class"]]["overdue_weight"]
    for row in sched
) + sum(
    data["class_params"][row["aircraft_class"]]["deferral_penalty"] for row in defer
)
second = sum(
    (by_id[row["request_id"]]["duration"] - row["compress_days"])
    * data["class_params"][row["aircraft_class"]]["revenue_per_day"]
    for row in sched
) + data["shift_cost"] * total_shifts
check(summary["plan_terms"]["first"] == first, "term 1")
check(summary["plan_terms"]["second"] == second, "term 2")
check(summary["plan_terms"]["third"] == summary["moved"], "term 3")

for base in dr.BASES:
    rows = [row for row in plan["checks"] if row["base"] == base]
    rep = regions[base]
    check(rep["base"] == base, "%s key" % base)
    check(
        rep["checks_scheduled"]
        == len([r for r in rows if r["decision"] == "scheduled"]),
        "%s scheduled" % base,
    )
    check(
        rep["checks_deferred"] == len([r for r in rows if r["decision"] == "deferred"]),
        "%s deferred" % base,
    )
    check(
        rep["overtime_shifts"] == sum(r["overtime_shifts"] for r in rows),
        "%s shifts" % base,
    )
    check(rep["fleet_overtime_used"] == total_shifts, "%s fleet shifts" % base)
    check(
        rep["allowance_granted"] == data["allowances"][base], "%s granted" % base
    )
    check(
        rep["allowance_used"] == sum(r["allowance_shifts"] for r in rows),
        "%s allowance used" % base,
    )
    starts = [r["start_date"] for r in rows if r["start_date"]]
    check(
        rep["first_start"] == (min(starts) if starts else None), "%s first_start" % base
    )
    finishes = [r["finish_date"] for r in rows if r["finish_date"]]
    check(
        rep["last_finish"] == (max(finishes) if finishes else None),
        "%s last_finish" % base,
    )

for seg in dr.SEGMENTS:
    rows = [row for row in plan["checks"] if row["segment"] == seg]
    rep = segments[seg]
    check(rep["segment"] == seg, "%s key" % seg)
    check("allowance_granted" not in rep, "%s must not carry allowance_granted" % seg)
    check(
        rep["checks_scheduled"]
        == len([r for r in rows if r["decision"] == "scheduled"]),
        "%s scheduled" % seg,
    )
    check(
        rep["overdue_days"]
        == sum(r["overdue_days"] for r in rows if r["decision"] == "scheduled"),
        "%s overdue" % seg,
    )

check(
    sum(regions[b]["checks_scheduled"] for b in dr.BASES)
    == sum(segments[s]["checks_scheduled"] for s in dr.SEGMENTS)
    == summary["checks_scheduled"],
    "scheduled counts do not agree across files",
)
check(
    sum(regions[b]["overtime_shifts"] for b in dr.BASES) == total_shifts,
    "region shifts do not sum to the fleet total",
)
check(
    [row["reason"] for row in quality["rejected"]]
    == [row["reason"] for row in rejected],
    "data_quality rejection list",
)
check(
    [row["line"] for row in quality["rejected"]] == [row["line"] for row in rejected],
    "data_quality lines",
)
check(sorted(quality["counts"].keys()) == sorted(dr.REASONS), "counts key set")
check(
    sum(quality["counts"].values()) == len(quality["rejected"]), "counts total"
)

no_slot = [row["request_id"] for row in defer if row["deferral_reason"] == "no_slot"]
print("scheduled=%d deferred=%d shifts=%d/%d terms=%s" % (
    len(sched), len(defer), total_shifts, data["overtime_pool_shifts"],
    summary["plan_terms"],
))
print("deferred: %s" % [(r["request_id"], r["deferral_reason"]) for r in defer])
print("no_slot ids: %s" % no_slot)
if problems:
    print("FAIL (%d)" % len(problems))
    for item in problems[:40]:
        print("  - %s" % item)
    sys.exit(1)
print("PASS: %d checks, no problems" % len(plan["checks"]))
