#!/usr/bin/env python3
"""Metered usage rating pipeline: reads one month's extract and writes rated usage and reports."""
import argparse
import bisect
import calendar
import configparser
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, getcontext

getcontext().prec = 60

INPUT_FILES = [
    "collector_central.csv",
    "collector_east.tsv",
    "collector_north.jsonl",
    "collector_south.txt",
    "collector_west.log",
    "accounts.csv",
    "plan_changes.log",
    "rate_card.json",
    "commitments.xml",
    "products.ini",
    "collector_controls.json",
]
REGIONS = ["central", "east", "north", "south", "west"]
COLLECTOR_FILES = {
    "central": "collector_central.csv",
    "east": "collector_east.tsv",
    "north": "collector_north.jsonl",
    "south": "collector_south.txt",
    "west": "collector_west.log",
}
SEGMENTS = ["consumer", "smb", "corporate", "enterprise"]
REASONS = ["timestamp_outside_month", "unknown_account", "unknown_product", "units_not_integer"]
DIGITS = re.compile(r"[0-9]+")
CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HALF = Decimal("0.50")


def fail(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(1)


def read_text(path, encoding="utf-8"):
    with open(path, "rb") as fh:
        raw = fh.read()
    if encoding == "utf-8" and raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode(encoding)


def split_lines(text):
    # Split on '\n' only: str.splitlines() would also split on characters such as
    # U+0085 that can legitimately occur inside Latin-1 text.
    out = []
    for line in text.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        out.append(line)
    return out


def canon_account(value):
    return value.strip().upper().replace("-", "")


def money(d):
    d = d.quantize(CENT, rounding=ROUND_HALF_EVEN)
    if d == 0:
        d = ZERO
    return "{:.2f}".format(d)


def rate_str(d):
    return "{:.4f}".format(d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN))


def r2(d):
    return d.quantize(CENT, rounding=ROUND_HALF_EVEN)


def epoch_from_parts(y, mo, d, h, mi, s):
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))


def parse_iso(value):
    v = value.strip()
    if v.endswith("Z") or v.endswith("z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def fmt_ts(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def units_text(value):
    v = value.strip()
    if DIGITS.fullmatch(v):
        return int(v)
    return None


# ---------------------------------------------------------------- collectors

def read_central(path):
    lines = split_lines(read_text(path))
    records = []
    for line in lines[1:]:
        if line.strip() == "":
            continue
        row = next(csv.reader([line]))
        row += [""] * (5 - len(row))
        rid, ts, acct, prod, units = (f.strip() for f in row[:5])
        try:
            epoch = epoch_from_parts(int(ts[0:4]), int(ts[5:7]), int(ts[8:10]),
                                     int(ts[11:13]), int(ts[14:16]), int(ts[17:19]))
        except ValueError:
            epoch = parse_iso(ts.replace(" ", "T"))
        records.append((rid, epoch, acct, prod, units_text(units)))
    return records


def read_east(path):
    lines = split_lines(read_text(path))
    records = []
    for line in lines[1:]:
        if line.strip() == "":
            continue
        row = line.split("\t")
        row += [""] * (5 - len(row))
        rid, ts, acct, prod, units = (f.strip() for f in row[:5])
        records.append((rid, int(ts), acct, prod, units_text(units)))
    return records


def read_north(path):
    lines = split_lines(read_text(path))
    records = []
    for line in lines:
        if line.strip() == "":
            continue
        obj = json.loads(line)
        rid = str(obj.get("id", "")).strip()
        epoch = parse_iso(str(obj.get("at", "")))
        acct = str(obj.get("acct", "")).strip()
        prod = obj.get("sku", "")
        prod = prod.strip() if isinstance(prod, str) else ""
        u = obj.get("units")
        units = u if (type(u) is int) else None
        records.append((rid, epoch, acct, prod, units))
    return records


def read_south(path):
    lines = split_lines(read_text(path, "latin-1"))
    records = []
    for line in lines:
        if line.strip() == "":
            continue
        rid = line[0:10].strip()
        ts = line[10:24].strip()
        acct = line[24:34].strip()
        prod = line[34:46].strip()
        units = line[46:52]
        epoch = epoch_from_parts(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]),
                                 int(ts[8:10]), int(ts[10:12]), int(ts[12:14]))
        records.append((rid, epoch, acct, prod, units_text(units)))
    return records


def read_west(path):
    lines = split_lines(read_text(path))
    records = []
    for line in lines:
        if line.strip() == "":
            continue
        tokens = line.strip().split()
        epoch = parse_iso(tokens[0])
        kv = {}
        for tok in tokens[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv.setdefault(k.strip(), v.strip())
        records.append((kv.get("rec", ""), epoch, kv.get("acct", ""), kv.get("product", ""),
                        units_text(kv.get("qty", ""))))
    return records


READERS = {
    "central": read_central,
    "east": read_east,
    "north": read_north,
    "south": read_south,
    "west": read_west,
}


# ---------------------------------------------------------------- reference

def read_accounts(path):
    lines = split_lines(read_text(path))
    accounts = {}
    header = None
    for line in lines:
        if line.strip() == "":
            continue
        row = [f.strip() for f in next(csv.reader([line]))]
        if header is None:
            header = [h.lower() for h in row]
            continue
        rec = dict(zip(header, row + [""] * (len(header) - len(row))))
        aid = canon_account(rec.get("account_id", ""))
        if not aid:
            continue
        parent = canon_account(rec.get("parent", ""))
        accounts[aid] = {
            "segment": rec.get("segment", "").strip().lower(),
            "plan": rec.get("plan", "").strip().lower(),
            "parent": parent,
        }
    return accounts


def billing_groups(accounts):
    groups = {}
    for aid in accounts:
        seen = []
        cur = aid
        while True:
            if cur in groups:
                root = groups[cur]
                break
            parent = accounts[cur]["parent"] if cur in accounts else ""
            if not parent or parent not in accounts or parent in seen or parent == cur:
                root = cur
                break
            seen.append(cur)
            cur = parent
        groups[aid] = root
        for s in seen:
            groups[s] = root
    return groups


def read_plan_changes(path, accounts):
    lines = split_lines(read_text(path))
    total = 0
    matched = []
    for idx, line in enumerate(lines):
        if line.strip() == "":
            continue
        total += 1
        tokens = line.strip().split()
        if not tokens:
            continue
        try:
            epoch = parse_iso(tokens[0])
        except ValueError:
            continue
        kv = {}
        for tok in tokens[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k.strip().lower()] = v.strip()
        acct = canon_account(kv.get("account", ""))
        if acct not in accounts:
            continue
        change = {}
        if "plan" in kv:
            change["plan"] = kv["plan"].lower()
        if "segment" in kv:
            change["segment"] = kv["segment"].lower()
        matched.append((epoch, idx, acct, change))
    matched.sort(key=lambda m: (m[0], m[1]))
    timelines = {}
    for epoch, _idx, acct, change in matched:
        tl = timelines.get(acct)
        if tl is None:
            base = accounts[acct]
            tl = {"ts": [], "state": [], "cur": (base["plan"], base["segment"])}
            timelines[acct] = tl
        plan, seg = tl["cur"]
        plan = change.get("plan", plan)
        seg = change.get("segment", seg)
        tl["cur"] = (plan, seg)
        if tl["ts"] and tl["ts"][-1] == epoch:
            tl["state"][-1] = (plan, seg)
        else:
            tl["ts"].append(epoch)
            tl["state"].append((plan, seg))
    stats = {"lines": total, "applied": len(matched), "unmatched": total - len(matched)}
    return timelines, stats


def in_force(accounts, timelines, acct, epoch):
    tl = timelines.get(acct)
    if tl is not None:
        i = bisect.bisect_right(tl["ts"], epoch)
        if i > 0:
            return tl["state"][i - 1]
    base = accounts[acct]
    return base["plan"], base["segment"]


def read_products(path):
    cp = configparser.RawConfigParser()
    cp.optionxform = lambda s: s.strip().lower()
    cp.read_string(read_text(path))
    codes = []
    units = {}
    names = {r: {} for r in REGIONS}
    for section in cp.sections():
        code = section.strip()
        codes.append(code)
        units[code] = cp.get(section, "unit", fallback="").strip()
        for r in REGIONS:
            if cp.has_option(section, r):
                for name in cp.get(section, r).split(","):
                    name = name.strip()
                    if name and name not in names[r]:
                        names[r][name] = code
    return codes, units, names


def read_rate_card(path):
    data = json.loads(read_text(path), parse_float=Decimal, parse_int=Decimal)
    card = {}
    for code, spec in data.get("products", {}).items():
        tiers = []
        for t in spec.get("tiers", []):
            rates = {str(k).strip().lower(): Decimal(v) for k, v in t.get("rates", {}).items()}
            tiers.append((Decimal(t.get("from", 0)), int(t.get("tier")), rates))
        tiers.sort(key=lambda x: x[0])
        card[code.strip()] = tiers
    return card


def read_commitments(path):
    root = ET.fromstring(read_text(path).encode("utf-8"))
    pools = {}
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag != "pool":
            continue
        region = (el.get("region") or "").strip().lower()
        pools[region] = (Decimal((el.get("amount") or "0").strip()),
                         Decimal((el.get("minimum") or "0").strip()))
    return pools


# ---------------------------------------------------------------- sharing

def share(lines, pool, key_charge):
    """Two-pass proportional sharing with the 0.50 floor. Returns list of Decimals."""
    base = sum((key_charge(x) for x in lines), Decimal(0))
    result = [ZERO] * len(lines)
    if base <= 0 or pool <= 0:
        return result
    first = [r2(pool * key_charge(x) / base) for x in lines]
    keep = [i for i, v in enumerate(first) if v >= HALF]
    if not keep:
        return result
    kept_sum = sum((key_charge(lines[i]) for i in keep), Decimal(0))
    for i in keep:
        result[i] = r2(pool * key_charge(lines[i]) / kept_sum)
    return result


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    indir = os.path.abspath(args.input)
    outdir = os.path.abspath(args.output)

    for name in INPUT_FILES:
        if not os.path.isfile(os.path.join(indir, name)):
            fail("missing input: " + name)

    def p(name):
        return os.path.join(indir, name)

    controls = json.loads(read_text(p("collector_controls.json")))
    month = str(controls.get("month", "")).strip()
    year, mon = int(month[0:4]), int(month[5:7])
    month_start = epoch_from_parts(year, mon, 1, 0, 0, 0)
    month_end = epoch_from_parts(year + (mon // 12), (mon % 12) + 1, 1, 0, 0, 0)

    raw = {}
    for region in REGIONS:
        raw[region] = READERS[region](p(COLLECTOR_FILES[region]))
    ctl = controls.get("collectors", {})
    for region in REGIONS:
        if region in ctl and "records" in ctl[region]:
            if int(ctl[region]["records"]) != len(raw[region]):
                fail("control mismatch: " + COLLECTOR_FILES[region])

    accounts = read_accounts(p("accounts.csv"))
    groups = billing_groups(accounts)
    timelines, pc_stats = read_plan_changes(p("plan_changes.log"), accounts)
    codes, product_units, product_names = read_products(p("products.ini"))
    card = read_rate_card(p("rate_card.json"))
    pools = read_commitments(p("commitments.xml"))

    # ---- checking
    dq_collectors = {}
    reason_counts = {r: 0 for r in REASONS}
    quarantined = []
    accepted = []
    for region in REGIONS:
        seen = set()
        dups = 0
        q = 0
        acc = 0
        for rid, epoch, acct_raw, prod, units in raw[region]:
            if rid in seen:
                dups += 1
                continue
            seen.add(rid)
            acct = canon_account(acct_raw)
            reason = None
            if not (month_start <= epoch < month_end):
                reason = "timestamp_outside_month"
            elif acct not in accounts:
                reason = "unknown_account"
            elif prod not in product_names[region]:
                reason = "unknown_product"
            elif units is None:
                reason = "units_not_integer"
            if reason:
                q += 1
                reason_counts[reason] += 1
                quarantined.append({"collector": region, "record_id": rid, "reason": reason})
                continue
            acc += 1
            accepted.append({
                "record_id": rid,
                "region": region,
                "epoch": epoch,
                "account_id": acct,
                "product": product_names[region][prod],
                "units": units,
            })
        dq_collectors[region] = {
            "file": COLLECTOR_FILES[region],
            "records": len(raw[region]),
            "duplicates": dups,
            "quarantined": q,
            "accepted": acc,
        }
    quarantined.sort(key=lambda x: (x["collector"], x["record_id"]))

    # ---- rating
    accepted.sort(key=lambda x: (x["epoch"], x["record_id"]))
    counters = {}
    for line in accepted:
        acct = line["account_id"]
        plan, seg = in_force(accounts, timelines, acct, line["epoch"])
        line["plan"] = plan
        line["segment"] = seg
        key = (line["product"], groups.get(acct, acct))
        counter = counters.get(key, 0)
        tiers = card[line["product"]]
        chosen = tiers[0]
        for t in tiers:
            if t[0] <= counter:
                chosen = t
        line["tier"] = chosen[1]
        rate = chosen[2][seg]
        line["unit_rate"] = rate
        line["charge"] = r2(Decimal(line["units"]) * rate)
        line["credit"] = ZERO
        line["true_up"] = ZERO
        counters[key] = counter + line["units"]

    # ---- credit and true-up
    region_info = {}
    for region in REGIONS:
        pool, minimum = pools.get(region, (Decimal(0), Decimal(0)))
        counted = [ln for ln in accepted
                   if ln["region"] == region and accounts[ln["account_id"]]["plan"] == "committed"]
        base = sum((ln["charge"] for ln in counted), Decimal(0))
        if base <= pool:
            for ln in counted:
                ln["credit"] = ln["charge"]
        else:
            credits = share(counted, pool, lambda x: x["charge"])
            for ln, c in zip(counted, credits):
                ln["credit"] = c
        if base < minimum:
            shortfall = minimum - base
            trues = share(counted, shortfall, lambda x: x["charge"])
            for ln, t in zip(counted, trues):
                ln["true_up"] = t
        region_info[region] = (pool, minimum, base)
    for ln in accepted:
        ln["net"] = ln["charge"] - ln["credit"] + ln["true_up"]

    # ---- outputs
    os.makedirs(outdir, exist_ok=True)

    def write_json(name, obj):
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
            fh.write("\n")

    with open(os.path.join(outdir, "normalized.jsonl"), "w", encoding="utf-8") as fh:
        for ln in accepted:
            fh.write(json.dumps({
                "record_id": ln["record_id"],
                "region": ln["region"],
                "timestamp": fmt_ts(ln["epoch"]),
                "account_id": ln["account_id"],
                "segment": ln["segment"],
                "plan": ln["plan"],
                "product": ln["product"],
                "units": ln["units"],
                "tier": ln["tier"],
                "unit_rate": rate_str(ln["unit_rate"]),
                "charge": money(ln["charge"]),
                "credit": money(ln["credit"]),
                "true_up": money(ln["true_up"]),
                "net": money(ln["net"]),
            }) + "\n")

    def totals(lines):
        return (sum((x["charge"] for x in lines), Decimal(0)),
                sum((x["credit"] for x in lines), Decimal(0)),
                sum((x["true_up"] for x in lines), Decimal(0)),
                sum((x["net"] for x in lines), Decimal(0)))

    def units_by_code(lines):
        u = {c: 0 for c in codes}
        for x in lines:
            u[x["product"]] = u.get(x["product"], 0) + x["units"]
        return u

    ch, cr, tu, nt = totals(accepted)
    write_json("summary.json", {
        "month": month,
        "lines": len(accepted),
        "accounts_billed": len({x["account_id"] for x in accepted}),
        "units": units_by_code(accepted),
        "charge": money(ch),
        "credit": money(cr),
        "true_up": money(tu),
        "net": money(nt),
    })

    products = {}
    for code in codes:
        pl = [x for x in accepted if x["product"] == code]
        ch, cr, tu, nt = totals(pl)
        products[code] = {
            "unit": product_units.get(code, ""),
            "lines": len(pl),
            "units": sum(x["units"] for x in pl),
            "charge": money(ch),
            "credit": money(cr),
            "true_up": money(tu),
            "net": money(nt),
        }
    write_json("product_summary.json", {"month": month, "products": products})

    for region in REGIONS:
        rl = [x for x in accepted if x["region"] == region]
        pool, minimum, base = region_info[region]
        ch, cr, tu, nt = totals(rl)
        write_json("region_%s.json" % region, {
            "region": region,
            "month": month,
            "lines": len(rl),
            "accounts": len({x["account_id"] for x in rl}),
            "units": units_by_code(rl),
            "charge": money(ch),
            "credit_pool": money(pool),
            "credit_base": money(base),
            "credit_applied": money(cr),
            "credit_unallocated": money(pool - cr),
            "minimum": money(minimum),
            "true_up": money(tu),
            "net": money(nt),
        })

    seg_names = list(SEGMENTS)
    for x in accepted:
        if x["segment"] not in seg_names:
            seg_names.append(x["segment"])
    for seg in seg_names:
        sl = [x for x in accepted if x["segment"] == seg]
        by_product = {}
        for code in codes:
            pl = [x for x in sl if x["product"] == code]
            by_product[code] = {
                "lines": len(pl),
                "units": sum(x["units"] for x in pl),
                "charge": money(sum((x["charge"] for x in pl), Decimal(0))),
            }
        ch, cr, tu, nt = totals(sl)
        write_json("segment_%s.json" % seg, {
            "segment": seg,
            "month": month,
            "lines": len(sl),
            "accounts": len({x["account_id"] for x in sl}),
            "by_product": by_product,
            "charge": money(ch),
            "credit": money(cr),
            "true_up": money(tu),
            "net": money(nt),
        })

    write_json("data_quality.json", {
        "month": month,
        "collectors": dq_collectors,
        "quarantine_reasons": reason_counts,
        "quarantined_records": quarantined,
        "plan_changes": pc_stats,
    })


if __name__ == "__main__":
    main()
