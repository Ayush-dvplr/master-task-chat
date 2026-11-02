#!/usr/bin/env python3
"""Independent recomputation of the rating outputs, written a second way."""
import csv
import io
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
import xml.etree.ElementTree as ET

getcontext().prec = 60
IN = sys.argv[1]
OUT = sys.argv[2]

p = lambda n: f"{IN}/{n}"
canon = lambda s: s.strip().upper().replace("-", "")
D2 = lambda d: d.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
M = lambda d: f"{D2(d):.2f}"

controls = json.load(open(p("collector_controls.json")))
month = controls["month"]
y, m = map(int, month.split("-"))
start = datetime(y, m, 1, tzinfo=timezone.utc)
end = datetime(y + 1, 1, 1, tzinfo=timezone.utc) if m == 12 else datetime(y, m + 1, 1, tzinfo=timezone.utc)

# ---- reference data
acc = {}
with open(p("accounts.csv"), newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        acc[canon(row["account_id"])] = (
            row["segment"].strip(), row["plan"].strip(), canon(row["parent"] or ""))

def group(a):
    cur = a
    while acc[cur][2] and acc[cur][2] in acc and acc[cur][2] != cur:
        cur = acc[cur][2]
    return cur

prod_names, prod_unit, codes = {}, {}, []
sec = None
for raw in open(p("products.ini"), encoding="utf-8"):
    line = raw.strip()
    if line.startswith("["):
        sec = line[1:-1].strip()
        codes.append(sec)
    elif "=" in line:
        k, v = [x.strip() for x in line.split("=", 1)]
        if k == "unit":
            prod_unit[sec] = v
        else:
            prod_names[(k, v)] = sec

card = json.load(open(p("rate_card.json")), parse_float=Decimal)
tiers = {c: sorted([(Decimal(str(t["from"])), t["tier"], t["rates"]) for t in v["tiers"]])
         for c, v in card["products"].items()}

pools = {}
for el in ET.parse(p("commitments.xml")).getroot():
    pools[el.get("region")] = (Decimal(el.get("amount")), Decimal(el.get("minimum")))

# plan changes
pc_lines = [l.strip() for l in open(p("plan_changes.log"), encoding="utf-8") if l.strip()]
events = defaultdict(list)
applied = 0
for i, l in enumerate(pc_lines):
    ts = datetime.strptime(l.split()[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    kv = dict(re.findall(r"(\w+)=(\S+)", l))
    a = canon(kv["account"])
    if a not in acc:
        continue
    applied += 1
    events[a].append((ts, i, kv.get("plan"), kv.get("segment")))

def in_force(a, ts):
    seg, plan = acc[a][0], acc[a][1]
    for ets, _i, np_, ns in sorted(events.get(a, []), key=lambda e: (e[0], e[1])):
        if ets <= ts:
            if np_: plan = np_
            if ns: seg = ns
        else:
            break
    return seg, plan

# ---- collectors (parsed a second way)
def digits(s):
    s = s.strip()
    return int(s) if re.fullmatch(r"[0-9]+", s) else None

recs = {r: [] for r in ["central", "east", "north", "south", "west"]}
with open(p("collector_central.csv"), newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        recs["central"].append((row["record_id"].strip(),
            datetime.strptime(row["timestamp"].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc),
            row["account"].strip(), row["product"].strip(), digits(row["units"])))
with open(p("collector_east.tsv"), newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        recs["east"].append((row["id"].strip(),
            datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=int(row["epoch"].strip())),
            row["account"].strip(), row["product"].strip(), digits(row["qty"])))
for l in open(p("collector_north.jsonl"), encoding="utf-8"):
    if not l.strip(): continue
    o = json.loads(l)
    u = o["units"]
    recs["north"].append((str(o["id"]).strip(),
        datetime.strptime(o["at"].strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc),
        str(o["acct"]).strip(), str(o["sku"]).strip(),
        u if (type(u) is int) else None))
for l in open(p("collector_south.txt"), encoding="latin-1"):
    l = l.rstrip("\n")
    if not l.strip(): continue
    recs["south"].append((l[:10].strip(),
        datetime.strptime(l[10:24].strip(), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc),
        l[24:34].strip(), l[34:46].strip(), digits(l[46:52])))
for l in open(p("collector_west.log"), encoding="utf-8"):
    if not l.strip(): continue
    parts = l.split()
    kv = dict(t.split("=", 1) for t in parts[1:])
    recs["west"].append((kv["rec"].strip(),
        datetime.fromisoformat(parts[0]).astimezone(timezone.utc),
        kv["acct"].strip(), kv["product"].strip(), digits(kv["qty"])))

lines = []
dq_coll, qrecs = {}, []
reasons = defaultdict(int)
for region in ["central", "east", "north", "south", "west"]:
    seen, dup, quar = set(), 0, 0
    for rid, ts, a, prd, units in recs[region]:
        if rid in seen:
            dup += 1
            continue
        seen.add(rid)
        ca = canon(a)
        r = None
        if not (start <= ts < end): r = "timestamp_outside_month"
        elif ca not in acc: r = "unknown_account"
        elif (region, prd) not in prod_names: r = "unknown_product"
        elif units is None: r = "units_not_integer"
        if r:
            quar += 1
            reasons[r] += 1
            qrecs.append({"collector": region, "record_id": rid, "reason": r})
            continue
        lines.append(dict(record_id=rid, region=region, ts=ts, account=ca,
                          product=prod_names[(region, prd)], units=units))
    dq_coll[region] = dict(file=controls["collectors"][region]["file"],
                           records=len(recs[region]), duplicates=dup, quarantined=quar,
                           accepted=len(recs[region]) - dup - quar)

lines.sort(key=lambda L: (L["ts"], L["record_id"]))
counter = defaultdict(int)
for L in lines:
    seg, plan = in_force(L["account"], L["ts"])
    k = (group(L["account"]), L["product"])
    c = counter[k]
    row = [t for t in tiers[L["product"]] if t[0] <= c][-1]
    rate = Decimal(str(row[2][seg]))
    counter[k] += L["units"]
    L.update(segment=seg, plan=plan, tier=row[1], rate=rate,
             charge=D2(Decimal(L["units"]) * rate), credit=Decimal("0.00"), true_up=Decimal("0.00"))

region_info = {}
for region, (pool, minimum) in pools.items():
    cl = [L for L in lines if L["region"] == region and acc[L["account"]][1] == "committed"]
    base = sum((L["charge"] for L in cl), Decimal("0.00"))
    def share(amount):
        if base <= 0 or amount <= 0:
            return {id(L): Decimal("0.00") for L in cl}
        first = {id(L): D2(amount * L["charge"] / base) for L in cl}
        kept = [L for L in cl if first[id(L)] >= Decimal("0.50")]
        tot = sum((L["charge"] for L in kept), Decimal("0.00"))
        out = {id(L): Decimal("0.00") for L in cl}
        if tot <= 0:
            return out
        for L in kept:
            out[id(L)] = D2(amount * L["charge"] / tot)
        return out
    if base <= pool:
        for L in cl: L["credit"] = L["charge"]
    else:
        cr = share(pool)
        for L in cl: L["credit"] = cr[id(L)]
    if base < minimum:
        tu = share(minimum - base)
        for L in cl: L["true_up"] = tu[id(L)]
    region_info[region] = (pool, minimum, base)

for L in lines:
    L["net"] = L["charge"] - L["credit"] + L["true_up"]

# ---- compare
errors = []
def eq(label, expected, got):
    if expected != got:
        errors.append(f"{label}: expected {expected!r} got {got!r}")

def tot(ls, key):
    return M(sum((L[key] for L in ls), Decimal("0.00")))

def units_map(ls):
    d = {c: 0 for c in codes}
    for L in ls: d[L["product"]] += L["units"]
    return d

# normalized.jsonl
got_lines = [json.loads(l) for l in open(f"{OUT}/normalized.jsonl", encoding="utf-8")]
eq("normalized count", len(lines), len(got_lines))
for exp, got in zip(lines, got_lines):
    want = {"record_id": exp["record_id"], "region": exp["region"],
            "timestamp": exp["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "account_id": exp["account"], "segment": exp["segment"], "plan": exp["plan"],
            "product": exp["product"], "units": exp["units"], "tier": exp["tier"],
            "unit_rate": f"{exp['rate']:.4f}", "charge": M(exp["charge"]),
            "credit": M(exp["credit"]), "true_up": M(exp["true_up"]), "net": M(exp["net"])}
    if want != got:
        errors.append(f"line {exp['record_id']}: {want} != {got}")
        if len(errors) > 5: break

s = json.load(open(f"{OUT}/summary.json"))
eq("summary", {"month": month, "lines": len(lines),
               "accounts_billed": len({L["account"] for L in lines}),
               "units": units_map(lines), "charge": tot(lines, "charge"),
               "credit": tot(lines, "credit"), "true_up": tot(lines, "true_up"),
               "net": tot(lines, "net")}, s)

ps = json.load(open(f"{OUT}/product_summary.json"))
want = {"month": month, "products": {}}
for c in codes:
    ls = [L for L in lines if L["product"] == c]
    want["products"][c] = {"unit": prod_unit[c], "lines": len(ls),
                           "units": sum(L["units"] for L in ls), "charge": tot(ls, "charge"),
                           "credit": tot(ls, "credit"), "true_up": tot(ls, "true_up"),
                           "net": tot(ls, "net")}
eq("product_summary", want, ps)

for region in pools:
    ls = [L for L in lines if L["region"] == region]
    pool, minimum, base = region_info[region]
    applied_c = sum((L["credit"] for L in ls), Decimal("0.00"))
    want = {"region": region, "month": month, "lines": len(ls),
            "accounts": len({L["account"] for L in ls}), "units": units_map(ls),
            "charge": tot(ls, "charge"), "credit_pool": M(pool), "credit_base": M(base),
            "credit_applied": M(applied_c), "credit_unallocated": M(pool - applied_c),
            "minimum": M(minimum), "true_up": tot(ls, "true_up"), "net": tot(ls, "net")}
    eq(f"region_{region}", want, json.load(open(f"{OUT}/region_{region}.json")))

for seg in ["consumer", "corporate", "enterprise", "smb"]:
    ls = [L for L in lines if L["segment"] == seg]
    bp = {}
    for c in codes:
        pl = [L for L in ls if L["product"] == c]
        bp[c] = {"lines": len(pl), "units": sum(L["units"] for L in pl), "charge": tot(pl, "charge")}
    want = {"segment": seg, "month": month, "lines": len(ls),
            "accounts": len({L["account"] for L in ls}), "by_product": bp,
            "charge": tot(ls, "charge"), "credit": tot(ls, "credit"),
            "true_up": tot(ls, "true_up"), "net": tot(ls, "net")}
    eq(f"segment_{seg}", want, json.load(open(f"{OUT}/segment_{seg}.json")))

qrecs.sort(key=lambda q: (q["collector"], q["record_id"]))
want = {"month": month, "collectors": dq_coll,
        "quarantine_reasons": {r: reasons[r] for r in
            ["timestamp_outside_month", "unknown_account", "unknown_product", "units_not_integer"]},
        "quarantined_records": qrecs,
        "plan_changes": {"lines": len(pc_lines), "applied": applied,
                         "unmatched": len(pc_lines) - applied}}
eq("data_quality", want, json.load(open(f"{OUT}/data_quality.json")))

if errors:
    print("MISMATCHES:")
    for e in errors[:20]:
        print(" ", e[:2000])
    sys.exit(1)
print("all documents match the independent recomputation")
print("accepted lines:", len(lines), "charge:", tot(lines, "charge"),
      "credit:", tot(lines, "credit"), "true_up:", tot(lines, "true_up"), "net:", tot(lines, "net"))
