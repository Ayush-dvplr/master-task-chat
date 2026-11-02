"""Self-checks run by solve.sh after the program is written.

Usage: selfcheck.py <program> <data folder> <output folder>
Each check prints "check <id> ok" and one witness line, or stops the run.
"""
import configparser
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

PROGRAM, DATA, OUT = (Path(p).resolve() for p in sys.argv[1:4])
WORK = Path(tempfile.mkdtemp(prefix="selfcheck-"))


def fail(cid, why):
    sys.exit("check %s FAILED: %s" % (cid, why))


def run(data, out, cwd=None):
    out.mkdir(parents=True, exist_ok=True)
    return subprocess.run([sys.executable, str(PROGRAM), "--data", str(data), "--out", str(out)],
                          capture_output=True, text=True, cwd=cwd or str(WORK), timeout=300)


def load(out, name):
    return json.loads((out / name).read_text(encoding="utf-8"))


def copy_data(tag):
    dst = WORK / tag / "data"
    shutil.copytree(DATA, dst)
    return dst


def ini(path):
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8")
    return cfg


def report(cid, witness):
    print("check %s ok" % cid)
    print("  witness: %s" % witness)


def check_missing_input():
    data = copy_data("missing")
    (data / "grid.ini").unlink()
    res = run(data, WORK / "missing" / "out")
    if res.returncode == 0 or "grid.ini" not in res.stderr:
        fail("missing_input", "rc %d stderr %r" % (res.returncode, res.stderr))
    report("missing_input", "rc %d: %s" % (res.returncode, res.stderr.strip()))


def check_malformed_input():
    data = copy_data("malformed")
    lines = (data / "settlements.csv").read_text(encoding="utf-8").splitlines()
    head = lines[1].split(",")
    head[-1] = "12x"
    lines[1] = ",".join(head)
    (data / "settlements.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = run(data, WORK / "malformed" / "out")
    if res.returncode == 0 or "settlements.csv" not in res.stderr:
        fail("malformed_input", "rc %d stderr %r" % (res.returncode, res.stderr))
    report("malformed_input", "rc %d: %s" % (res.returncode, res.stderr.strip()))


def check_witness():
    """Two buses share one 30 kWh feeder; the public bus must be served first."""
    data = copy_data("witness")
    grid = ini(data / "grid.ini")
    day = grid["plan"]["plan_date"]
    first = datetime.fromisoformat(grid["plan"]["first_slot"])
    nxt = (datetime.fromisoformat(day) + timedelta(days=1)).date().isoformat()
    text = (data / "grid.ini").read_text(encoding="utf-8")
    old = "feeder_kwh_per_slot = %s" % grid["feeder"]["feeder_kwh_per_slot"]
    (data / "grid.ini").write_text(text.replace(old, "feeder_kwh_per_slot = 30"), encoding="utf-8")
    fleet = list(csv.DictReader((data / "fleet_register.csv").open(encoding="utf-8")))
    small = sorted(r["vehicle_id"] for r in fleet if r["type"] == "E12" and r["status"] == "active")
    bus_x, bus_y = small[0], small[1]
    stamp = lambda k: (first + timedelta(minutes=15 * k)).strftime("%Y-%m-%dT%H:%M")
    with (data / "roster.csv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("plan_date,bus_id,depot,arrive,depart,soc_arrival_kwh,contract_id\n")
        fh.write("%s,%s,North,%s,%s,20,COM-01\n" % (day, bus_x, stamp(0), stamp(3)))
        fh.write("%s,%s,North,%s,%s,20,SCH-01\n" % (day, bus_y, stamp(0), stamp(2)))
    with (data / "trips.jsonl").open("w", encoding="utf-8") as fh:
        for bus in (bus_x, bus_y):
            fh.write(json.dumps({"trip_id": "W-" + bus, "bus_id": bus, "service_date": nxt, "kwh": 60}) + "\n")
    (data / "published_plan.csv").write_text("plan_date,bus_id,slot_start,kwh\n", encoding="utf-8")
    out = WORK / "witness" / "out"
    res = run(data, out)
    if res.returncode != 0:
        fail("witness", res.stderr)
    audit = {b["bus_id"]: b for b in load(out, "policy_audit.json")["buses"]}
    got_y = [(c["slot"], c["kwh"]) for c in audit[bus_y]["charges"]]
    got_x = [(c["slot"], c["kwh"]) for c in audit[bus_x]["charges"]]
    summary = load(out, "summary.json")
    if got_y != [(stamp(0), 30), (stamp(1), 30)] or got_x != [(stamp(2), 30)] or summary["weighted_unmet_kwh"] != 30:
        fail("witness", "public %s commercial %s unmet %s" % (got_y, got_x, summary["weighted_unmet_kwh"]))
    report("witness", "public %s gets %s, commercial %s gets %s, weighted unmet 30" % (bus_y, got_y, bus_x, got_x))


def check_edge_feeder():
    data = copy_data("edge")
    text = (data / "grid.ini").read_text(encoding="utf-8")
    grid = ini(data / "grid.ini")
    old = "feeder_kwh_per_slot = %s" % grid["feeder"]["feeder_kwh_per_slot"]
    (data / "grid.ini").write_text(text.replace(old, "feeder_kwh_per_slot = 200"), encoding="utf-8")
    out = WORK / "edge" / "out"
    res = run(data, out)
    if res.returncode != 0:
        fail("edge_feeder", res.stderr)
    loads = [s["kwh"] for s in load(out, "summary.json")["feeder_kwh_by_slot"]]
    if max(loads) > 200:
        fail("edge_feeder", "peak %d above 200" % max(loads))
    for b in load(out, "policy_audit.json")["buses"]:
        if b["delivered_kwh"] > b["need_kwh"] or b["delivered_kwh"] + b["unmet_kwh"] != b["need_kwh"]:
            fail("edge_feeder", "bus %s delivered %d need %d" % (b["bus_id"], b["delivered_kwh"], b["need_kwh"]))
    report("edge_feeder", "limit 200: peak %d, %d slots at the limit" % (max(loads), loads.count(200)))


def check_altered_copy():
    before = {b["bus_id"]: b for b in load(OUT, "policy_audit.json")["buses"]}
    day = load(OUT, "summary.json")["plan_date"]
    data = copy_data("altered")
    rows = (data / "roster.csv").read_text(encoding="utf-8").splitlines()
    target = next(b for b in sorted(before) if before[b]["need_kwh"] >= 10)
    for i, line in enumerate(rows[1:], 1):
        f = line.split(",")
        if f[0] == day and f[1] == target:
            f[5] = str(int(f[5]) - 5)
            rows[i] = ",".join(f)
            break
    (data / "roster.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    out = WORK / "altered" / "out"
    res = run(data, out)
    if res.returncode != 0:
        fail("altered_copy", res.stderr)
    after = {b["bus_id"]: b for b in load(out, "policy_audit.json")["buses"]}
    if after[target]["need_kwh"] != before[target]["need_kwh"] + 5:
        fail("altered_copy", "%s need %d -> %d" % (target, before[target]["need_kwh"], after[target]["need_kwh"]))
    report("altered_copy", "%s soc -5 kWh: need %d -> %d" % (target, before[target]["need_kwh"], after[target]["need_kwh"]))


def check_relocated():
    place = WORK / "relocated"
    shutil.copytree(DATA, place / "input")
    shutil.copy(PROGRAM, place / "prog.py")
    res = subprocess.run([sys.executable, str(place / "prog.py"), "--data", str(place / "input"), "--out", str(place / "out")],
                         capture_output=True, text=True, cwd="/", timeout=300)
    if res.returncode != 0:
        fail("relocated", res.stderr)
    names = sorted(p.name for p in OUT.glob("*.json"))
    same = [n for n in names if (OUT / n).read_bytes() == (place / "out" / n).read_bytes()]
    if same != names:
        fail("relocated", "differs: %s" % sorted(set(names) - set(same)))
    report("relocated", "%d of %d reports byte-identical from cwd /" % (len(same), len(names)))


def check_recompute_summary():
    audit = load(OUT, "policy_audit.json")
    summary = load(OUT, "summary.json")
    weights = {k: int(v["weight"]) for k, v in ini(DATA / "service_classes.ini").items() if k != "DEFAULT"}
    unmet = sum(weights[b["class"]] * b["unmet_kwh"] for b in audit["buses"])
    by_slot = {}
    for b in audit["buses"]:
        for c in b["charges"]:
            by_slot[c["slot"]] = by_slot.get(c["slot"], 0) + c["kwh"]
    listed = {s["slot"]: s["kwh"] for s in summary["feeder_kwh_by_slot"]}
    if unmet != summary["weighted_unmet_kwh"] or any(listed.get(s) != k for s, k in by_slot.items()):
        fail("recompute_summary", "weighted unmet %d vs %d" % (unmet, summary["weighted_unmet_kwh"]))
    if sum(listed.values()) != sum(by_slot.values()) or max(listed.values()) != summary["feeder_peak_kwh"]:
        fail("recompute_summary", "feeder totals disagree")
    report("recompute_summary", "weighted unmet %d, feeder peak %d, %d kWh over %d charged slots"
           % (unmet, summary["feeder_peak_kwh"], sum(by_slot.values()), len(by_slot)))


def check_recompute_limits():
    grid = ini(DATA / "grid.ini")
    feeder = int(grid["feeder"]["feeder_kwh_per_slot"])
    depots = json.loads((DATA / "depots.json").read_text(encoding="utf-8"))
    unit = depots["cabinet_kwh_per_slot"]
    cab = {d["depot"]: d["cabinets"] for d in depots["depots"]}
    notice = (DATA / "disruption_notice.md").read_text(encoding="utf-8").splitlines()
    worst = 0
    for name in cab:
        for s in load(OUT, "region_%s.json" % name)["slots"]:
            out_now = 0
            limit = feeder
            for line in notice:
                parts = line.split()
                if line.startswith("- %s:" % name) and "cabinets" in line and parts[-3] <= s["slot"] < parts[-1]:
                    out_now += int(parts[2])
                if line.startswith("- from ") and parts[2] <= s["slot"] < parts[4].rstrip(":"):
                    limit = int(parts[7])
            if s["kwh"] > (cab[name] - out_now) * unit or s["feeder_kwh"] > limit:
                fail("recompute_limits", "%s %s kwh %d feeder %d" % (name, s["slot"], s["kwh"], s["feeder_kwh"]))
            worst = max(worst, s["kwh"] * 100 // max(1, (cab[name] - out_now) * unit))
    report("recompute_limits", "every depot slot within its cabinets and the feeder; fullest depot slot at %d%%" % worst)


def check_meter_unique():
    grid = ini(DATA / "grid.ini")
    first = datetime.fromisoformat(grid["plan"]["first_slot"])
    minutes = int(grid["plan"]["slot_minutes"])
    per_day = 1440 // minutes
    versions = []
    for v in ET.parse(DATA / "tariff.xml").getroot().iter("version"):
        price = [None] * per_day
        for band in v.iter("band"):
            h, m = map(int, band.get("from").split(":"))
            h2, m2 = map(int, band.get("to").split(":"))
            k, end = (h * 60 + m) // minutes, (h2 * 60 + m2) // minutes
            while True:
                price[k % per_day] = int(band.get("cents_per_kwh"))
                k += 1
                if k % per_day == end % per_day:
                    break
        versions.append((v.get("valid_from"), v.get("valid_to"), price))
    origin = (first.hour * 60 + first.minute) // minutes
    rows = list(csv.DictReader((DATA / "settlements.csv").open(encoding="utf-8")))
    found = {}
    for depot in sorted({r["depot"] for r in rows}):
        mine = [r for r in rows if r["depot"] == depot]
        good = []
        for shift in range(per_day):
            ok = True
            for r in mine:
                price = next(p for a, b, p in versions if a <= r["settled_date"] <= b)
                st, en = datetime.fromisoformat(r["start"]), datetime.fromisoformat(r["end"])
                n = int((en - st).total_seconds() // (60 * minutes))
                k0 = (st.hour * 60 + st.minute) // minutes
                total = sum(price[(k0 + j + shift) % per_day] for j in range(n))
                if int(r["kwh"]) * total != int(r["cents"]) * n:
                    ok = False
                    break
            if ok:
                good.append(shift)
        if len(good) != 1:
            fail("meter_unique", "%s fits %s" % (depot, good))
        found[depot] = good[0]
    report("meter_unique", "one reading per depot (slot shift): %s; plan slot 0 is time of day index %d"
           % (", ".join("%s %d" % kv for kv in found.items()), origin))


CHECKS = [check_missing_input, check_malformed_input, check_witness, check_edge_feeder, check_altered_copy,
          check_relocated, check_recompute_summary, check_recompute_limits, check_meter_unique]

if __name__ == "__main__":
    try:
        for check in CHECKS:
            check()
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    print("all %d self-checks passed" % len(CHECKS))
