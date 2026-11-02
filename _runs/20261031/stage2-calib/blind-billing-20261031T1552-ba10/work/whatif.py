#!/usr/bin/env python3
"""What-if driver: copies the extract, applies one change, reruns transform.py."""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

BLIND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BLIND, "environment", "data")
PROG = os.path.join(BLIND, "app", "transform.py")
TMP = os.path.join(BLIND, "work", "whatif_tmp")


def shift(dd, handset, from_day, minutes):
    from_day = dt.date.fromisoformat(from_day)
    delta = dt.timedelta(minutes=minutes)
    n = 0
    p = os.path.join(dd, "closings.csv")
    out = []
    for i, ln in enumerate(open(p, encoding="utf-8").read().split("\n")):
        f = ln.split(",")
        if i > 0 and len(f) == 7 and f[1].strip() == handset:
            t = dt.datetime.strptime(f[5].strip(), "%Y-%m-%dT%H:%M:%S")
            if t.date() >= from_day:
                f[5] = (t + delta).strftime("%Y-%m-%dT%H:%M:%S")
                n += 1
                ln = ",".join(f)
        out.append(ln)
    open(p, "w", encoding="utf-8").write("\n".join(out))
    p = os.path.join(dd, "legacy_closings.txt")
    out = []
    for ln in open(p, encoding="utf-8").read().split("\n"):
        if ln.strip() and not ln.startswith("#"):
            f = ln.split("|")
            if f[1].strip() == handset:
                raw = f[5]
                t = dt.datetime.strptime(raw.strip(), "%d.%m.%Y %H:%M:%S")
                if t.date() >= from_day:
                    f[5] = raw.replace(raw.strip(), (t + delta).strftime("%d.%m.%Y %H:%M:%S"))
                    n += 1
                    ln = "|".join(f)
        out.append(ln)
    open(p, "w", encoding="utf-8").write("\n".join(out))
    return n


def set_plan(dd, plan, minutes):
    p = os.path.join(dd, "plans.csv")
    lines = open(p, encoding="utf-8").read().split("\n")
    for i, ln in enumerate(lines):
        f = ln.split(",")
        if f[0] == plan:
            f[1] = str(minutes)
            lines[i] = ",".join(f)
    open(p, "w", encoding="utf-8").write("\n".join(lines))


def set_cycle(dd, key, value):
    p = os.path.join(dd, "cycle.json")
    o = json.load(open(p, encoding="utf-8"))
    o[key] = value
    open(p, "w", encoding="utf-8").write(json.dumps(o, indent=2) + "\n")


def add_holiday(dd, row):
    p = os.path.join(dd, "holidays.csv")
    s = open(p, encoding="utf-8").read()
    if not s.endswith("\n"):
        s += "\n"
    open(p, "w", encoding="utf-8").write(s + row + "\n")


def fresh(name):
    dd = os.path.join(TMP, name, "data")
    if os.path.exists(os.path.join(TMP, name)):
        shutil.rmtree(os.path.join(TMP, name))
    shutil.copytree(DATA, dd)
    return dd


def run(dd):
    od = os.path.join(os.path.dirname(dd), "out")
    subprocess.run([sys.executable, PROG, dd, od], check=True, stdout=subprocess.DEVNULL, timeout=60)
    r = lambda n: json.load(open(os.path.join(od, n)))
    received = r("data_quality.json")["closings_received"]
    return r, received


LOG = []


def note(q, n_shift, received, answer):
    LOG.append((q, n_shift, received, answer))
    print("Q%s shifted=%d received=%d answer=%s" % (q, n_shift, received, answer))


REG = ["region_%s.json" % x for x in ("central", "east", "north", "south", "west")]
SEG = ["segment_%s.json" % x for x in ("consumer", "corporate", "enterprise", "smb")]


def insum(r, names):
    return sum(r(n)["net_micro"] for n in names if r(n)["in_scope"])


extracts = 0
closings = 0

# 1
dd = fresh("q1"); n = shift(dd, "H-33", "2026-03-12", 9); set_plan(dd, "P-BASIC", 0)
r, rc = run(dd); extracts += 1; closings += rc
note(1, n, rc, r("summary.json")["net_micro"])
# 2
dd = fresh("q2"); n = shift(dd, "H-08", "2026-03-12", 9); set_cycle(dd, "minimum_invoice_micro", 20000000000)
r, rc = run(dd); extracts += 1; closings += rc
note(2, n, rc, insum(r, SEG))
# 3
dd = fresh("q3"); n = shift(dd, "H-11", "2026-03-16", -6)
r, rc = run(dd); extracts += 1; closings += rc
north = r("region_north.json")["net_micro"]
set_cycle(dd, "minimum_invoice_micro", north)
r, rc = run(dd); extracts += 1; closings += rc
note(3, n, rc, "%d (north net used as minimum: %d)" % (insum(r, REG), north))
# 4
dd = fresh("q4"); n = shift(dd, "H-31", "2026-03-16", -9)
ans = None
sweep = []
for inc in range(0, 1201, 120):
    set_plan(dd, "P-EXEC", inc)
    r, rc = run(dd); extracts += 1; closings += rc
    net = r("summary.json")["net_micro"]
    sweep.append((inc, net))
    if ans is None and net <= 93360000000:
        ans = inc
note(4, n, rc, "%s sweep=%s" % (ans, sweep))
# 5
dd = fresh("q5"); n = shift(dd, "H-18", "2026-03-09", 6); set_cycle(dd, "rate_card", "rate_card.csv")
r, rc = run(dd); extracts += 1; closings += rc
note(5, n, rc, r("region_north.json")["net_micro"])
# 6
dd = fresh("q6"); n = shift(dd, "H-25", "2026-03-09", -12); add_holiday(dd, "west,2026-03-11,Founders Day")
r, rc = run(dd); extracts += 1; closings += rc
note(6, n, rc, r("summary.json")["by_tier"].get("after_hours"))
# 7
dd = fresh("q7"); n = shift(dd, "H-13", "2026-03-16", 9); set_plan(dd, "P-EXEC", 0)
r, rc = run(dd); extracts += 1; closings += rc
note(7, n, rc, r("summary.json")["credit_micro"])
# 8
dd = fresh("q8"); n = shift(dd, "H-15", "2026-03-16", -6); set_cycle(dd, "minimum_invoice_micro", 20000000000)
r, rc = run(dd); extracts += 1; closings += rc
note(8, n, rc, insum(r, REG + SEG))

print("TOTAL program runs (extracts)=%d closings covered=%d" % (extracts, closings))
shutil.rmtree(TMP)
