#!/usr/bin/env python3
"""What-if runner: copies the shipped extract, applies one change, reruns derive_report.py.
Usage: whatif.py PROGRAM DATA_DIR SCRATCH_DIR
"""
import csv, datetime, json, os, shutil, subprocess, sys

PROG, DATA, SCRATCH = sys.argv[1], sys.argv[2], sys.argv[3]


def tmin(s):
    d = datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    return d.toordinal() * 1440 + int(s[11:13]) * 60 + int(s[14:16])


def fmt(m):
    d = datetime.date.fromordinal(m // 1440)
    return "%sT%02d:%02d" % (d.isoformat(), (m % 1440) // 60, m % 60)


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def write_rows(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


# shipped clock offsets (same rule as the program: most journal matches, ties to smaller |o|)
ch_of = {}
for r in read_rows(os.path.join(DATA, "unit_deployments.csv"))[1]:
    ch_of.setdefault(r[0], r[2].strip().upper())
jh, jrows = read_rows(os.path.join(DATA, "receipt_journal.csv"))
jindex = {}
for i, r in enumerate(jrows):
    jindex.setdefault((r[0].strip().upper(), tmin(r[1]), int(r[2])), []).append(i)
card = read_rows(os.path.join(DATA, "card_readings.csv"))
ch_ = card[0]
cu, cs, cf = ch_.index("unit_id"), ch_.index("card_stamp"), ch_.index("frame")
by_unit = {}
for r in card[1]:
    by_unit.setdefault(r[cu], []).append((tmin(r[cs]), int(r[cf])))
OFF = {}
for u, lst in by_unit.items():
    best = None
    for o in range(-19, 20):
        n = sum(1 for s, f in lst if (ch_of[u], s - o, f) in jindex)
        k = (n, -abs(o), -o)
        if best is None or k > best[0]:
            best = (k, o)
    OFF[u] = best[1]


def fresh(name):
    d = os.path.join(SCRATCH, name)
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(DATA, os.path.join(d, "data"))
    return os.path.join(d, "data"), os.path.join(d, "out")


def shift_journal(data, specs):
    """specs: list of (unit, lo_stamp or None, hi_stamp or None, minutes)."""
    h, rows = read_rows(os.path.join(data, "receipt_journal.csv"))
    used = set()
    moved = 0
    for u, lo, hi, mins in specs:
        lo = None if lo is None else tmin(lo)
        hi = None if hi is None else tmin(hi)
        for s, f in by_unit[u]:
            if (lo is not None and s < lo) or (hi is not None and s >= hi):
                continue
            for i in jindex.get((ch_of[u], s - OFF[u], f), []):
                if i not in used:
                    used.add(i)
                    rows[i] = [rows[i][0], fmt(tmin(rows[i][1]) + mins), rows[i][2]]
                    moved += 1
                    break
    write_rows(os.path.join(data, "receipt_journal.csv"), h, rows)
    return moved


def run(data, out):
    p = subprocess.run(["perl", "-e", "alarm 600; exec @ARGV", sys.executable, PROG, data, out],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit("run failed: %s" % p.stderr)
    rep = {}
    for n in os.listdir(out):
        with open(os.path.join(out, n)) as fh:
            rep[n] = json.load(fh)
    return rep


def daily(rep):
    dv = {}
    for n, r in rep.items():
        if n.startswith("region_"):
            if not r.get("in_scope"):
                print("  note: %s out of scope" % n)
            for s in r.get("sites", []):
                dv[s["site_id"]] = s["daily_values"]
    return dv


def zone_edit(data, fn):
    p = os.path.join(data, "zone_rules.json")
    z = json.load(open(p))
    fn(z)
    json.dump(z, open(p, "w"), indent=2)


base = run(DATA, os.path.join(SCRATCH, "base_out"))
base_dv = daily(base)
std = base["policy_audit.json"]["daily_standard_tenths"]
print("offsets", OFF)
ans = {}

# 1
d, o = fresh("w1")
zone_edit(d, lambda z: z["daylight_saving"].append(
    {"begins": "2026-01-19T02:00", "ends": "2026-01-26T02:00", "shift_minutes": 60}))
dv = daily(run(d, o))
days = ["2026-01-%02d" % k for k in range(19, 26)]
ans[1] = sum(v for s in dv.values() for k, v in s.items() if k in days)

# 2
d, o = fresh("w2")
print("  w2 moved", shift_journal(d, [("AQ896", "2026-01-20T01:15", None, 30)]))
ans[2] = sum(daily(run(d, o))["S2"].values())

# 3
d, o = fresh("w3")
print("  w3 moved", shift_journal(d, [("AQ896", "2026-01-10T00:15", "2026-01-13T01:00", 12),
                                     ("AQ246", "2026-01-07T00:00", "2026-01-10T00:00", 12),
                                     ("AQ785", "2026-01-06T00:00", "2026-01-09T00:00", -14),
                                     ("AQ363", "2026-01-25T00:00", "2026-01-28T00:30", -14)]))
dv = daily(run(d, o))
def exc_set(x):
    return {(s, k) for s, m in x.items() for k, v in m.items() if v > std}
ans[3] = len(exc_set(dv) ^ exc_set(base_dv))

# 4
d, o = fresh("w4")
p = os.path.join(d, "unit_deployments.csv")
h, rows = read_rows(p)
for r in rows:
    if r[0] == "AQ896" and r[1] == "S2":
        r[4] = "2026-01-20T12:00"
    if r[0] == "AQ680" and r[1] == "S6":
        r[4] = "2026-01-20T12:00"
rows.append(["AQ896", "S6", "CH1", "2026-01-20T12:00", ""])
write_rows(p, h, rows)
print("  w4 moved", shift_journal(d, [("AQ896", "2026-01-20T14:45", None, 20)]))
r4 = run(d, o)
ans[4] = r4["region_East.json"].get("valid_readings")

# 5
p_rel = "span_register.csv"
last_ok = None
scan = []
for k in range(1100, 1301):
    f = "%d.%03d" % (k // 1000, k % 1000)
    d, o = fresh("w5")
    p = os.path.join(d, p_rel)
    h, rows = read_rows(p)
    for r in rows:
        if r[2] in ("AQ634", "T-670") and r[5] == "set":
            r[4] = f
    write_rows(p, h, rows)
    st = [s for s in run(d, o)["policy_audit.json"]["sites"] if s["site_id"] == "S4"][0]
    scan.append((f, st["status"], st["design_value"]))
    if st["status"] == "attainment":
        last_ok = f
ans[5] = last_ok
flips = [scan[i][0] for i in range(1, len(scan)) if (scan[i][1] == "attainment") != (scan[i - 1][1] == "attainment")]
print("  w5 scan 1.100-1.300 (%d runs), status flips at %s, first %s last %s" % (len(scan), flips, scan[0], scan[-1]))

# 6
d, o = fresh("w6")
print("  w6 moved", shift_journal(d, [("AQ363", "2026-01-24T00:00", "2026-01-28T00:30", -14)]))
ans[6] = [s for s in run(d, o)["policy_audit.json"]["sites"] if s["site_id"] == "S5"][0]["design_value"]

# 7
d, o = fresh("w7")
print("  w7 moved", shift_journal(d, [("AQ680", "2026-01-15T00:00", None, 15)]))
ans[7] = sum(daily(run(d, o))["S6"].values())

# 8
d, o = fresh("w8")
print("  w8 moved", shift_journal(d, [("AQ785", "2026-01-12T00:00", "2026-01-25T00:30", -10),
                                     ("AQ785", "2026-01-25T00:30", None, -20)]))
ans[8] = sum(daily(run(d, o))["S3"].values())

# 9
d, o = fresh("w9")
print("  w9 moved", shift_journal(d, [("AQ246", "2026-01-22T00:15", None, 25),
                                     ("AQ363", "2026-01-10T00:15", None, -12)]))
ans[9] = sum(v for s in daily(run(d, o)).values() for v in s.values())

# 10
d, o = fresh("w10")
zone_edit(d, lambda z: z.__setitem__("standard_offset_minutes", -360))
ans[10] = run(d, o)["summary.json"]["valid_hours"]

print("base: sum all daily", sum(v for s in base_dv.values() for v in s.values()),
      "S2", sum(base_dv["S2"].values()), "S3", sum(base_dv["S3"].values()),
      "S6", sum(base_dv["S6"].values()), "East", base["region_East.json"].get("valid_readings"),
      "valid_hours", base["summary.json"]["valid_hours"])
for k in sorted(ans):
    print("WHATIF %d = %s" % (k, ans[k]))
