#!/bin/bash
# Oracle dispatcher for cleanroom-window-schedule.
set -euo pipefail

mkdir -p /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cleanroom-window-schedule/tmp/sc/out
cp /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cleanroom-window-schedule/solution/solve.py /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cleanroom-window-schedule/tmp/sc/out/derive_report.py
python3 /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cleanroom-window-schedule/tmp/sc/out/derive_report.py /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cleanroom-window-schedule/environment/data /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cleanroom-window-schedule/tmp/sc/out

# Self-check stage: recompute the reported figures outside the program and compare.
python3 - /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cleanroom-window-schedule/environment/data /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cleanroom-window-schedule/tmp/sc/out <<'PY'
import configparser, csv, json, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path

data, out = Path(sys.argv[1]), Path(sys.argv[2])
doc = {p.name: json.loads(p.read_text()) for p in out.glob("*.json")}
rows = list(csv.DictReader(open(data / "jobs.csv", newline="")))
win = {r["window_id"]: (int(r["start"]), int(r["end"]))
       for r in csv.DictReader(open(data / "windows.tsv", newline=""), delimiter="\t")}
bays = json.loads((data / "bays.json").read_text())["bays"]
ini = configparser.ConfigParser()
ini.read(data / "qualifications.ini")
catalog = {f.strip() for f in ini["catalog"]["families"].split(",")}
fees = {(r["night_id"], r["from_family"], r["to_family"]): (int(r["fee"]), int(r["crew_minutes"]))
        for r in csv.DictReader(open(data / "setup_fees.csv", newline=""))}
site = {c["client_id"]: c["site"] for c in map(json.loads, open(data / "clients.jsonl"))}
region = {r["site"]: r["region"] for r in csv.DictReader(open(data / "regions.csv", newline=""))}
segment = {r["client_id"]: r["segment"]
           for r in csv.DictReader(open(data / "segments.tsv", newline=""), delimiter="\t")}
nights = sorted(tomllib.loads((data / "audit.toml").read_text())["night"], key=lambda n: n["date"])
seen = {}
for r in rows:
    seen[r["job_id"]] = seen.get(r["job_id"], 0) + 1


def code(nid):
    mine = [r for r in rows if r["night_id"] == nid]
    if any(seen[r["job_id"]] > 1 for r in mine):
        return "E_DUP_JOB"
    if any(r["window_id"] not in win or not 0 <= win[r["window_id"]][0] < win[r["window_id"]][1] <= 1440
           for r in mine):
        return "E_BAD_WINDOW"
    if any(r["family"] not in catalog or r["client_id"] not in site for r in mine):
        return "E_UNKNOWN_RESOURCE"
    if any(a != b and (nid, a, b) not in fees for a in catalog for b in catalog):
        return "E_BAD_FEE"
    return None


job = {r["job_id"]: r for r in rows}
rate = {b["bay_id"]: b["minute_rate"] for b in bays}
held = {b["bay_id"]: b["initial_family"] for b in bays}
codes = {n["id"]: code(n["id"]) for n in nights}
want = [{"night_id": n["id"], "code": codes[n["id"]], "message": "night %s rejected: %s" % (n["id"], codes[n["id"]])}
        for n in nights if codes[n["id"]]]
assert doc["data_quality.json"]["rejected"] == want
print("check R3 ok")
rolls = {}
for night, audit_row in zip(doc["summary.json"]["nights"], doc["policy_audit.json"]["nights"]):
    nid = night["night_id"]
    if codes[nid]:
        assert night["plan"] == [] and night["net"] == 0
        continue
    gross = charge = paid = 0
    windows = []
    for line in night["plan"]:
        r, bay = job[line["job_id"]], line["bay_id"]
        s, e = win[r["window_id"]]
        fee = 0
        if r["family"] != held[bay]:
            fee, minutes = fees[(nid, held[bay], r["family"])]
            windows.append({"bay_id": bay, "job_id": r["job_id"], "start": s - minutes, "end": s})
        held[bay] = r["family"]
        assert line["changeover_fee"] == fee
        value, cost = int(r["value"]), rate[bay] * (e - s)
        gross, charge, paid = gross + value, charge + cost, paid + fee
        for key in (("region", region[site[r["client_id"]]]), ("segment", segment[r["client_id"]])):
            got = rolls.setdefault(key, {}).setdefault(nid, [0, 0, 0])
            got[0], got[1], got[2] = got[0] + 1, got[1] + value, got[2] + value - cost - fee
    assert [night["gross"], night["bay_charge"], night["fees"], night["net"]] == [gross, charge, paid,
                                                                                  gross - charge - paid]
    assert audit_row["crew_windows"] == sorted(windows, key=lambda w: w["start"])
    assert audit_row["crew_minutes"] == sum(w["end"] - w["start"] for w in windows)
print("check R1 ok")
print("check R2 ok")
for kind, label in (("region", "R4"), ("segment", "R5")):
    for p in sorted(out.glob(kind + "_*.json")):
        name = doc[p.name][kind]
        for entry in doc[p.name]["nights"]:
            expect = rolls.get((kind, name), {}).get(entry["night_id"], [0, 0, 0])
            assert [entry["jobs_run"], entry["gross"], entry["net"]] == expect
    print("check %s ok" % label)

first = next(n for n in doc["summary.json"]["nights"] if n["plan"])
target = first["plan"][0]["job_id"]
with tempfile.TemporaryDirectory() as td:
    copy, moved = Path(td) / "data", Path(td) / "out"
    shutil.copytree(data, copy)
    lines = (copy / "jobs.csv").read_text().splitlines(keepends=True)
    for i, line in enumerate(lines):
        cells = line.rstrip("\n").split(",")
        if cells[0] == target:
            cells[-1] = str(int(cells[-1]) + 500)
            lines[i] = ",".join(cells) + "\n"
    (copy / "jobs.csv").write_text("".join(lines))
    subprocess.run([sys.executable, str(out / "derive_report.py"), str(copy), str(moved)], check=True)
    again = json.loads((moved / "summary.json").read_text())["nights"]
    night = next(n for n in again if n["night_id"] == first["night_id"])
    assert night["gross"] != first["gross"] and night["net"] != first["net"]
print("check R6 ok")
print("rejected nights: " + ", ".join(w["night_id"] for w in want))
PY
