#!/usr/bin/env python3
"""Metered usage rating pipeline (see rating_contract.md)."""
import argparse
import bisect
import configparser
import csv
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction

REGIONS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "smb", "corporate", "enterprise"]
REASONS = ["timestamp_outside_month", "unknown_account", "unknown_product", "units_not_integer"]
INPUT_FILES = [
    "collector_central.csv", "collector_east.tsv", "collector_north.jsonl",
    "collector_south.txt", "collector_west.log", "accounts.csv", "plan_changes.log",
    "rate_card.json", "commitments.xml", "products.ini", "collector_controls.json",
]
COLLECTOR_FILES = dict(zip(REGIONS, INPUT_FILES[:5]))
DIGITS = re.compile(r"[0-9]+")


def die(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(1)


def canon(acct):
    return str(acct).strip().upper().replace("-", "")


def text(v):
    return "" if v is None else str(v).strip()


def utc_fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def money(cents):
    sign = "-" if cents < 0 else ""
    a = abs(cents)
    return "%s%d.%02d" % (sign, a // 100, a % 100)


def to_cents(s):
    return round(Fraction(Decimal(text(s))) * 100)


def digit_units(v):
    v = text(v)
    return int(v) if DIGITS.fullmatch(v) else None


def data_lines(path, encoding="utf-8"):
    with open(path, encoding=encoding, newline="") as fh:
        lines = fh.read().splitlines()
    return [ln for ln in lines if ln.strip() != ""]


# ---------------------------------------------------------------- collectors
def read_central(path):
    out = []
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    for row in rows[1:]:
        if not any(c.strip() for c in row):
            continue
        row = row + [""] * (5 - len(row))
        ts = datetime.strptime(text(row[1]), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        out.append((text(row[0]), ts, text(row[2]), text(row[3]), digit_units(row[4])))
    return out


def read_east(path):
    out = []
    lines = data_lines(path)
    for ln in lines[1:]:
        row = ln.split("\t")
        row = row + [""] * (5 - len(row))
        ts = datetime.fromtimestamp(int(text(row[1])), tz=timezone.utc)
        out.append((text(row[0]), ts, text(row[2]), text(row[3]), digit_units(row[4])))
    return out


def read_north(path):
    out = []
    for ln in data_lines(path):
        o = json.loads(ln)
        u = o.get("units")
        units = u if (type(u) is int) else None
        ts = datetime.strptime(text(o.get("at")), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        out.append((text(o.get("id")), ts, text(o.get("acct")), text(o.get("sku")), units))
    return out


def read_south(path):
    out = []
    for ln in data_lines(path, encoding="latin-1"):
        ts = datetime.strptime(text(ln[10:24]), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        out.append((text(ln[0:10]), ts, text(ln[24:34]), text(ln[34:46]), digit_units(ln[46:52])))
    return out


def parse_iso_offset(s):
    s = text(s)
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def read_west(path):
    out = []
    for ln in data_lines(path):
        parts = ln.split()
        ts = parse_iso_offset(parts[0])
        kv = {}
        for tok in parts[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv.setdefault(k.strip(), v)
        units = digit_units(kv["qty"]) if "qty" in kv else None
        out.append((text(kv.get("rec")), ts, text(kv.get("acct")), text(kv.get("product")), units))
    return out


READERS = {"central": read_central, "east": read_east, "north": read_north,
           "south": read_south, "west": read_west}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    ind = os.path.abspath(args.input)
    outd = os.path.abspath(args.output)

    for name in INPUT_FILES:
        if not os.path.isfile(os.path.join(ind, name)):
            die("missing input: %s" % name)
    P = lambda n: os.path.join(ind, n)

    with open(P("collector_controls.json"), encoding="utf-8") as fh:
        controls = json.load(fh)
    month = text(controls["month"])
    y, m = int(month[:4]), int(month[5:7])
    m_start = datetime(y, m, 1, tzinfo=timezone.utc)
    m_end = datetime(y + (m == 12), 1 if m == 12 else m + 1, 1, tzinfo=timezone.utc)

    # collectors + control counts
    raw = {}
    for r in REGIONS:
        raw[r] = READERS[r](P(COLLECTOR_FILES[r]))
    for r in REGIONS:
        expected = int(controls["collectors"][r]["records"])
        if len(raw[r]) != expected:
            die("control mismatch: %s" % COLLECTOR_FILES[r])

    # accounts
    accounts = {}
    with open(P("accounts.csv"), encoding="utf-8", newline="") as fh:
        rdr = csv.reader(fh)
        header = [text(h) for h in next(rdr)]
        idx = {h: i for i, h in enumerate(header)}
        for row in rdr:
            if not any(c.strip() for c in row):
                continue
            row = row + [""] * (len(header) - len(row))
            aid = canon(row[idx["account_id"]])
            par = text(row[idx["parent"]])
            accounts[aid] = {
                "segment": text(row[idx["segment"]]).lower(),
                "plan": text(row[idx["plan"]]).lower(),
                "parent": canon(par) if par else "",
            }

    group_cache = {}

    def billing_group(aid):
        if aid in group_cache:
            return group_cache[aid]
        chain, seen, cur = [], set(), aid
        while True:
            if cur in group_cache:
                root = group_cache[cur]
                break
            if cur in seen:
                cyc = chain[chain.index(cur):]
                root = min(cyc)
                break
            seen.add(cur)
            chain.append(cur)
            par = accounts.get(cur, {}).get("parent", "")
            if not par:
                root = cur
                break
            cur = par
        for a in chain:
            group_cache[a] = root
        return root

    # plan changes
    changes = {}
    pc_lines = pc_applied = 0
    for order, ln in enumerate(data_lines(P("plan_changes.log"))):
        pc_lines += 1
        parts = ln.split()
        kv = {}
        for tok in parts[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k.strip()] = v.strip()
        aid = canon(kv.get("account", ""))
        if "account" not in kv or aid not in accounts:
            continue
        pc_applied += 1
        ts = datetime.strptime(text(parts[0]), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        changes.setdefault(aid, []).append(
            (ts, order, kv["plan"].lower() if "plan" in kv else None,
             kv["segment"].lower() if "segment" in kv else None))
    timelines = {}
    for aid, lst in changes.items():
        lst.sort(key=lambda c: (c[0], c[1]))
        plan, seg = accounts[aid]["plan"], accounts[aid]["segment"]
        keys, states = [], []
        for ts, _o, p, s in lst:
            if p is not None:
                plan = p
            if s is not None:
                seg = s
            keys.append(ts)
            states.append((plan, seg))
        timelines[aid] = (keys, states)

    def in_force(aid, ts):
        base = (accounts[aid]["plan"], accounts[aid]["segment"])
        tl = timelines.get(aid)
        if not tl:
            return base
        i = bisect.bisect_right(tl[0], ts)
        return tl[1][i - 1] if i else base

    # products
    cp = configparser.RawConfigParser(interpolation=None)
    with open(P("products.ini"), encoding="utf-8") as fh:
        cp.read_file(fh)
    product_codes = [s.strip() for s in cp.sections()]
    product_unit = {}
    name_map = {r: {} for r in REGIONS}
    for sec in cp.sections():
        code = sec.strip()
        product_unit[code] = text(cp.get(sec, "unit", fallback=""))
        for r in REGIONS:
            if cp.has_option(sec, r):
                name_map[r].setdefault(text(cp.get(sec, r)), code)

    # rate card
    with open(P("rate_card.json"), encoding="utf-8") as fh:
        rc = json.load(fh, parse_float=Decimal, parse_int=Decimal)
    tiers = {}
    for code, spec in rc["products"].items():
        tl = []
        for t in spec["tiers"]:
            tl.append((Decimal(t["from"]), int(t["tier"]),
                       {k.strip().lower(): Decimal(str(v)) for k, v in t["rates"].items()}))
        tl.sort(key=lambda x: x[0])
        tiers[code.strip()] = tl

    # commitments
    pools = {}
    root = ET.parse(P("commitments.xml")).getroot()
    for el in root.iter("pool"):
        pools[text(el.get("region")).lower()] = (to_cents(el.get("amount")), to_cents(el.get("minimum")))

    # ------------------------------------------------------------ checking
    dq = {}
    quarantined = []
    reason_counts = {k: 0 for k in REASONS}
    accepted = []
    for r in REGIONS:
        seen = set()
        dups = quar = acc = 0
        for rid, ts, acct, prod, units in raw[r]:
            if rid in seen:
                dups += 1
                continue
            seen.add(rid)
            aid = canon(acct)
            if not (m_start <= ts < m_end):
                reason = "timestamp_outside_month"
            elif aid not in accounts:
                reason = "unknown_account"
            elif prod not in name_map[r]:
                reason = "unknown_product"
            elif units is None:
                reason = "units_not_integer"
            else:
                reason = None
            if reason:
                quar += 1
                reason_counts[reason] += 1
                quarantined.append({"collector": r, "record_id": rid, "reason": reason})
                continue
            acc += 1
            accepted.append({"record_id": rid, "region": r, "ts": ts, "account_id": aid,
                             "product": name_map[r][prod], "units": units})
        dq[r] = {"file": COLLECTOR_FILES[r], "records": len(raw[r]), "duplicates": dups,
                 "quarantined": quar, "accepted": acc}
    quarantined.sort(key=lambda q: (q["collector"], q["record_id"]))

    # ------------------------------------------------------------ rating
    accepted.sort(key=lambda l: (l["ts"], l["record_id"]))
    counters = {}
    for ln in accepted:
        plan, seg = in_force(ln["account_id"], ln["ts"])
        ln["plan"], ln["segment"] = plan, seg
        key = (ln["product"], billing_group(ln["account_id"]))
        counter = counters.get(key, 0)
        chosen = None
        for frm, tnum, rates in tiers[ln["product"]]:
            if frm <= counter:
                chosen = (tnum, rates)
        tnum, rates = chosen
        rate = rates[seg]
        ln["tier"] = tnum
        ln["rate"] = rate
        ln["charge"] = round(Fraction(rate) * ln["units"] * 100)
        ln["credit"] = 0
        ln["true_up"] = 0
        ln["committed"] = accounts[ln["account_id"]]["plan"] == "committed"
        counters[key] = counter + ln["units"]

    def share(total, lines_, base):
        """Proportional share in cents with the 0.50 re-share rule."""
        first = [round(Fraction(total * l["charge"], base)) for l in lines_]
        keep = [l for l, v in zip(lines_, first) if v >= 50]
        res = {id(l): 0 for l in lines_}
        if keep:
            s = sum(l["charge"] for l in keep)
            for l in keep:
                res[id(l)] = round(Fraction(total * l["charge"], s))
        return res

    region_info = {}
    for r in REGIONS:
        counted = [l for l in accepted if l["region"] == r and l["committed"]]
        base = sum(l["charge"] for l in counted)
        pool, minimum = pools.get(r, (0, 0))
        if counted:
            if base <= pool:
                for l in counted:
                    l["credit"] = l["charge"]
            else:
                res = share(pool, counted, base)
                for l in counted:
                    l["credit"] = res[id(l)]
            if base < minimum and base > 0:
                res = share(minimum - base, counted, base)
                for l in counted:
                    l["true_up"] = res[id(l)]
        region_info[r] = (pool, base, minimum)
    for l in accepted:
        l["net"] = l["charge"] - l["credit"] + l["true_up"]

    # ------------------------------------------------------------ outputs
    os.makedirs(outd, exist_ok=True)

    def write_json(name, obj):
        with open(os.path.join(outd, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
            fh.write("\n")

    with open(os.path.join(outd, "normalized.jsonl"), "w", encoding="utf-8") as fh:
        for l in accepted:
            fh.write(json.dumps({
                "record_id": l["record_id"], "region": l["region"], "timestamp": utc_fmt(l["ts"]),
                "account_id": l["account_id"], "segment": l["segment"], "plan": l["plan"],
                "product": l["product"], "units": l["units"], "tier": l["tier"],
                "unit_rate": str(l["rate"].quantize(Decimal("0.0001"))),
                "charge": money(l["charge"]), "credit": money(l["credit"]),
                "true_up": money(l["true_up"]), "net": money(l["net"]),
            }) + "\n")

    def tot(lines_, k):
        return sum(l[k] for l in lines_)

    def units_by_product(lines_):
        u = {c: 0 for c in product_codes}
        for l in lines_:
            u[l["product"]] = u.get(l["product"], 0) + l["units"]
        return u

    write_json("summary.json", {
        "month": month, "lines": len(accepted),
        "accounts_billed": len({l["account_id"] for l in accepted}),
        "units": units_by_product(accepted),
        "charge": money(tot(accepted, "charge")), "credit": money(tot(accepted, "credit")),
        "true_up": money(tot(accepted, "true_up")), "net": money(tot(accepted, "net")),
    })

    prods = {}
    for c in product_codes:
        ls = [l for l in accepted if l["product"] == c]
        prods[c] = {"unit": product_unit[c], "lines": len(ls), "units": tot(ls, "units"),
                    "charge": money(tot(ls, "charge")), "credit": money(tot(ls, "credit")),
                    "true_up": money(tot(ls, "true_up")), "net": money(tot(ls, "net"))}
    write_json("product_summary.json", {"month": month, "products": prods})

    for r in REGIONS:
        ls = [l for l in accepted if l["region"] == r]
        pool, base, minimum = region_info[r]
        applied = tot(ls, "credit")
        write_json("region_%s.json" % r, {
            "region": r, "month": month, "lines": len(ls),
            "accounts": len({l["account_id"] for l in ls}),
            "units": units_by_product(ls), "charge": money(tot(ls, "charge")),
            "credit_pool": money(pool), "credit_base": money(base),
            "credit_applied": money(applied), "credit_unallocated": money(pool - applied),
            "minimum": money(minimum), "true_up": money(tot(ls, "true_up")),
            "net": money(tot(ls, "net")),
        })

    for s in SEGMENTS:
        ls = [l for l in accepted if l["segment"] == s]
        bp = {}
        for c in product_codes:
            lc = [l for l in ls if l["product"] == c]
            bp[c] = {"lines": len(lc), "units": tot(lc, "units"), "charge": money(tot(lc, "charge"))}
        write_json("segment_%s.json" % s, {
            "segment": s, "month": month, "lines": len(ls),
            "accounts": len({l["account_id"] for l in ls}), "by_product": bp,
            "charge": money(tot(ls, "charge")), "credit": money(tot(ls, "credit")),
            "true_up": money(tot(ls, "true_up")), "net": money(tot(ls, "net")),
        })

    write_json("data_quality.json", {
        "month": month, "collectors": dq, "quarantine_reasons": reason_counts,
        "quarantined_records": quarantined,
        "plan_changes": {"lines": pc_lines, "applied": pc_applied, "unmatched": pc_lines - pc_applied},
    })

    me = os.path.abspath(__file__)
    dest = os.path.join(outd, "transform.py")
    if not (os.path.exists(dest) and os.path.samefile(me, dest)):
        shutil.copyfile(me, dest)


if __name__ == "__main__":
    main()
