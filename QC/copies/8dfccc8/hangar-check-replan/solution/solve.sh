#!/bin/bash
# Oracle dispatcher for hangar-check-replan.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
ls /app/out

# Check stages: each prints a witness line and "check <id> ok".
mkdir -p /tmp/oracle_checks
cat > /tmp/oracle_checks/probes.py <<'PROBES'
"""Checks the oracle runs after writing /app/out (each prints `check <id> ok` and a witness line)."""
import csv
import datetime
import itertools
import json
import os
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

PROGRAM = "/app/out/derive_report.py"
DATA = "/app/data"
OUT = "/app/out"
WORK = "/tmp/oracle_checks"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", WNS)


def run(data, out, cwd="/app"):
    return subprocess.run([sys.executable, PROGRAM, data, out], cwd=cwd, capture_output=True, text=True)


def outputs(folder):
    return {n: json.load(open(os.path.join(folder, n))) for n in sorted(os.listdir(folder)) if n.endswith(".json")}


def copy_data(name):
    d = os.path.join(WORK, name)
    shutil.copytree(DATA, d, ignore=shutil.ignore_patterns("docs"))
    return d


def cell_text(tc):
    return "".join(t.text or "" for t in tc.iter("{%s}t" % WNS)).strip()


def tables(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    found = {}
    for tbl in root.iter("{%s}tbl" % WNS):
        rows = [[cell_text(tc) for tc in tr.iter("{%s}tc" % WNS)] for tr in tbl.iter("{%s}tr" % WNS)]
        found[tuple(rows[0][:2])] = rows[1:]
    return found


def set_cell(path, first, column, value):
    """Rewrite the cell in the row whose first cell reads `first`."""
    with zipfile.ZipFile(path) as z:
        parts = {i.filename: z.read(i.filename) for i in z.infolist()}
    root = ET.fromstring(parts["word/document.xml"])
    for tr in root.iter("{%s}tr" % WNS):
        cells = list(tr.iter("{%s}tc" % WNS))
        if cell_text(cells[0]) == first:
            list(cells[column].iter("{%s}t" % WNS))[0].text = str(value)
    parts["word/document.xml"] = ET.tostring(root, xml_declaration=True, encoding="UTF-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in parts.items():
            z.writestr(name, blob)


def say(cid, witness):
    print("witness %s: %s" % (cid, witness))
    print("check %s ok" % cid)


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    base = outputs(OUT)
    plan = base["policy_audit.json"]["checks"]
    summ = base["summary.json"]
    lim = tables(os.path.join(DATA, "planning_limits.docx"))
    rates = {r[0]: [int(v) for v in r[1:]] for r in lim[("class", "revenue_per_day")]}
    shift_cost = int(dict(lim[("item", "value")])["shift_cost"])
    requests = {}
    with open(os.path.join(DATA, "check_requests.csv")) as f:
        for row in csv.DictReader(f):
            if row["season"] == summ["season"] and row["status"] == "OPEN":
                requests.setdefault(row["request_id"], row)

    # P1 tighter pool: the rerun keeps the smaller limit
    d = copy_data("p1")
    smaller = summ["fleet_overtime_used"] - 1
    set_cell(os.path.join(d, "planning_limits.docx"), "overtime_pool_shifts", 1, smaller)
    assert run(d, d + "_out").returncode == 0
    s1 = outputs(d + "_out")["summary.json"]
    assert s1["fleet_overtime_used"] <= smaller
    say("P1", "pool %d -> used %d, terms %s" % (smaller, s1["fleet_overtime_used"], s1["plan_terms"]))

    # P2 the three plan terms recomputed from the per-check rows
    first = second = third = 0
    for r in plan:
        rev, weight, penalty = rates[r["aircraft_class"]]
        if r["decision"] == "deferred":
            first += penalty
            third += 1
            continue
        a = datetime.date.fromisoformat(r["start_date"])
        b = datetime.date.fromisoformat(r["finish_date"])
        first += weight * r["overdue_days"]
        second += rev * ((b - a).days + 1) + shift_cost * r["overtime_shifts"]
        third += int(r["moved"])
    want = summ["plan_terms"]
    assert [first, second, third] == [want["first"], want["second"], want["third"]]
    say("P2", "terms from %d rows = %d, %d, %d" % (len(plan), first, second, third))

    # P3 base totals equal the sum of their checks
    for b in ("North", "South", "West", "East"):
        region = base["region_%s.json" % b]
        mine = [r for r in plan if r["base"] == b]
        for k, k2 in (("overtime_shifts", "overtime_shifts"), ("allowance_shifts", "allowance_used"),
                      ("settled_overtime_cost", "settled_overtime_cost")):
            assert sum(r[k] for r in mine) == region[k2], (b, k2)
    say("P3", "4 region files match sums over %d rows" % len(plan))

    # P4 allowance replayed in the stated order
    rank = {"widebody": 0, "narrowbody": 1, "regional": 2}
    left = summ["settlement"]["allowance_granted"]
    order = sorted((r for r in plan if r["overtime_shifts"]),
                   key=lambda r: (rank[r["aircraft_class"]], requests[r["request_id"]]["due_date"], r["request_id"]))
    for r in order:
        take = min(r["overtime_shifts"], left)
        left -= take
        assert r["allowance_shifts"] == take, r["request_id"]
    assert left == summ["settlement"]["allowance_left"]
    say("P4", "%d paying checks replayed, allowance left %d" % (len(order), left))

    # P5 smaller grants move the settlement and leave the plan alone
    d = copy_data("p5")
    for b in ("North", "South", "West", "East"):
        set_cell(os.path.join(d, "planning_limits.docx"), b, 1, 1)
    assert run(d, d + "_out").returncode == 0
    s5 = outputs(d + "_out")["summary.json"]
    assert s5["plan_terms"] == summ["plan_terms"] and s5["settlement"] != summ["settlement"]
    say("P5", "grants 1 each: terms %s unchanged, settlement %s -> %s"
        % (s5["plan_terms"], summ["settlement"], s5["settlement"]))

    # P6 a second run from another directory, on a copy of the inputs, gives the same files
    d = copy_data("p6")
    r6 = run(d, os.path.join(WORK, "p6_out"), cwd="/tmp")
    assert r6.returncode == 0 and outputs(os.path.join(WORK, "p6_out")) == base
    say("P6", "rerun from cwd /tmp on inputs at %s identical to /app/out, %d files" % (d, len(base)))

    # P7 two requests on one line: every start day and compression searched by hand
    two = [r for r in plan if r["base"] == plan[0]["base"]][:2]
    d = copy_data("p7")
    with open(os.path.join(DATA, "check_requests.csv")) as f:
        rows = list(csv.DictReader(f))
    keep = list({t["request_id"]: requests[t["request_id"]] for t in two}.values())
    with open(os.path.join(d, "check_requests.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(keep)
    assert run(d, d + "_out").returncode == 0
    got = {r["request_id"]: r for r in outputs(d + "_out")["policy_audit.json"]["checks"]}
    best, legal, fit = enumerate_two(d, keep, rates, shift_cost)
    for rid, (start, finish) in best.items():
        assert (got[rid]["start_date"], got[rid]["finish_date"]) == (start, finish), rid
    assert fit == 1
    say("P7", "%d legal plans for %s checked, %d fits the order: %s"
        % (legal, sorted(best), fit, sorted(best.values())))

    # P8 a missing input stops the run and names the file
    d = copy_data("p8")
    os.remove(os.path.join(d, "check_types.json"))
    r8 = run(d, d + "_out")
    assert r8.returncode != 0 and "check_types.json" in r8.stderr
    say("P8", "exit %d, stderr: %s" % (r8.returncode, r8.stderr.strip()[:80]))

    # P9 a base with no requests still gets its report and summary row
    d = copy_data("p9")
    with open(os.path.join(d, "check_requests.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(r for r in rows if not (r["season"] == summ["season"] and r["base"] == "East"))
    assert run(d, d + "_out").returncode == 0
    o9 = outputs(d + "_out")
    east = [b for b in o9["summary.json"]["bases"] if b["base"] == "East"]
    assert o9["region_East.json"]["checks_scheduled"] == 0 and len(east) == 1
    say("P9", "East empty: region_East.json %s, summary row %s" % (json.dumps(o9["region_East.json"]), east[0]))

    # P10 a closure row on the start day of a scheduled check moves that check
    r = next(x for x in plan if x["decision"] == "scheduled")
    d = copy_data("p10")
    add_row(os.path.join(d, "disruption_notice.docx"), ("base", "from"), [r["base"], r["start_date"], 1])
    assert run(d, d + "_out").returncode == 0
    got = {x["request_id"]: x for x in outputs(d + "_out")["policy_audit.json"]["checks"]}[r["request_id"]]
    assert (got["start_date"], got["finish_date"]) != (r["start_date"], r["finish_date"])
    say("P10", "closure %s from %s for 1 day: %s start %s finish %s -> start %s finish %s"
        % (r["base"], r["start_date"], r["request_id"], r["start_date"], r["finish_date"],
           got["start_date"], got["finish_date"]))

    # P11 a later available_from for the tail of a scheduled check moves that check
    import tomllib
    with open(os.path.join(DATA, "fleet_limits.toml"), "rb") as f:
        end = str(tomllib.load(f)["season_end"])
    r = next(x for x in plan if x["decision"] == "scheduled" and x["start_date"] < end)
    later = (datetime.date.fromisoformat(r["start_date"]) + datetime.timedelta(days=1)).isoformat()
    d = copy_data("p11")
    path = os.path.join(d, "disruption_notice.docx")
    if any(row[0] == r["tail"] for row in tables(path)[("tail", "available_from")]):
        set_cell(path, r["tail"], 1, later)
    else:
        add_row(path, ("tail", "available_from"), [r["tail"], later])
    assert run(d, d + "_out").returncode == 0
    got = {x["request_id"]: x for x in outputs(d + "_out")["policy_audit.json"]["checks"]}[r["request_id"]]
    assert got["start_date"] != r["start_date"]
    say("P11", "tail %s available_from %s: %s start %s -> %s"
        % (r["tail"], later, r["request_id"], r["start_date"], got["start_date"]))


def enumerate_two(d, keep, rates, shift_cost):
    lim = {}
    for line in open(os.path.join(d, "fleet_limits.toml")):
        if "=" in line:
            k, v = line.split("=", 1)
            lim[k.strip()] = v.strip().strip('"')
    day0 = datetime.date.fromisoformat(lim["season_start"])
    last = (datetime.date.fromisoformat(lim["season_end"]) - day0).days + 1
    num = lambda s: (datetime.date.fromisoformat(s) - day0).days + 1
    text = lambda n: (day0 + datetime.timedelta(days=n - 1)).isoformat()
    base = keep[0]["base"]
    notice = tables(os.path.join(d, "disruption_notice.docx"))
    closed, nostart = set(), set()
    for line in open(os.path.join(d, "base_calendar.jsonl")):
        c = json.loads(line)
        if c["base"] == base and c["status"] == "CLOSED":
            closed.add(num(c["date"]))
        if c["base"] == base and c["status"] == "NO_START":
            nostart.add(num(c["date"]))
    for b, start, days in notice[("base", "from")]:
        if b == base:
            closed.update(num(start) + k for k in range(int(days)))
    revised = dict(notice[("tail", "available_from")])
    types = json.load(open(os.path.join(d, "check_types.json")))
    reg = {r["tail"]: r["aircraft_class"] for r in csv.DictReader(open(os.path.join(d, "fleet_register.csv")))}
    pub = {r["request_id"]: r["published_start"] for r in csv.DictReader(open(os.path.join(d, "published_plan.csv")))}
    pool = int(dict(tables(os.path.join(d, "planning_limits.docx"))[("item", "value")])["overtime_pool_shifts"])
    choices = []
    for r in sorted(keep, key=lambda r: r["request_id"]):
        p = int(r["duration_days"])
        t = types[r["check_type"]]
        avail = max(1, num(revised.get(r["tail"], r["available_from"])))
        opts = [None]
        for x in range(min(t["max_compress_days"], p - 1) + 1):
            for s in range(avail, last + 1):
                f = s + p - x - 1
                if f <= last and s not in nostart and not closed.intersection(range(s, f + 1)):
                    opts.append((s, f, x * t["overtime_shifts_per_day"]))
        choices.append((r, opts))
    best, legal, fit = None, 0, 0
    for combo in itertools.product(*(o for _, o in choices)):
        live = [c for c in combo if c]
        if len(live) == 2 and not (live[0][1] < live[1][0] or live[1][1] < live[0][0]):
            continue
        if sum(c[2] for c in live) > pool:
            continue
        t1 = t2 = t3 = 0
        for (r, _), c in zip(choices, combo):
            rev, weight, penalty = rates[reg[r["tail"]]]
            if c is None:
                t1, t3 = t1 + penalty, t3 + 1
                continue
            t1 += weight * max(0, c[1] - num(r["due_date"]))
            t2 += rev * (c[1] - c[0] + 1) + shift_cost * c[2]
            t3 += int(c[0] != num(pub[r["request_id"]]))
        k = (t1, t2, t3, [c[0] if c else last + 1 for c in combo], [c[1] if c else last + 1 for c in combo])
        legal += 1
        if best is None or k < best[0]:
            best, fit = (k, combo), 1
        elif k == best[0]:
            fit += 1
    found = {r["request_id"]: ((text(c[0]), text(c[1])) if c else (None, None))
             for (r, _), c in zip(choices, best[1])}
    return found, legal, fit


def add_row(path, head, values):
    """Append a row, copied from the last row, to the table whose header starts with `head`."""
    import copy
    with zipfile.ZipFile(path) as z:
        parts = {i.filename: z.read(i.filename) for i in z.infolist()}
    root = ET.fromstring(parts["word/document.xml"])
    for tbl in root.iter("{%s}tbl" % WNS):
        rows = tbl.findall("{%s}tr" % WNS)
        if tuple(cell_text(tc) for tc in rows[0].findall("{%s}tc" % WNS))[:2] == head:
            row = copy.deepcopy(rows[-1])
            for tc, value in zip(row.findall("{%s}tc" % WNS), values):
                list(tc.iter("{%s}t" % WNS))[0].text = str(value)
            tbl.append(row)
    parts["word/document.xml"] = ET.tostring(root, xml_declaration=True, encoding="UTF-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in parts.items():
            z.writestr(name, blob)


if __name__ == "__main__":
    main()
PROBES
python3 /tmp/oracle_checks/probes.py
