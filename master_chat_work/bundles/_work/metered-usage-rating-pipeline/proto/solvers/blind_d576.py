#!/usr/bin/env python3
"""Metered usage rating pipeline (see rating_contract.md)."""
import argparse
import bisect
import calendar
import configparser
import csv
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction

REGIONS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "corporate", "enterprise", "smb"]
REASONS = ["timestamp_outside_month", "unknown_account", "unknown_product", "units_not_integer"]
COLLECTOR_FILES = {
    "central": "collector_central.csv",
    "east": "collector_east.tsv",
    "north": "collector_north.jsonl",
    "south": "collector_south.txt",
    "west": "collector_west.log",
}
INPUT_FILES = [
    "collector_central.csv", "collector_east.tsv", "collector_north.jsonl",
    "collector_south.txt", "collector_west.log", "accounts.csv", "plan_changes.log",
    "rate_card.json", "commitments.xml", "products.ini", "collector_controls.json",
]
DIGITS = re.compile(r"[0-9]+")
CENT = Decimal("0.01")
RATE_Q = Decimal("0.0001")


def fail(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(1)


def canon(acct):
    return acct.strip().upper().replace("-", "")


def read_text(path, encoding="utf-8"):
    with open(path, "r", encoding=encoding, newline="") as f:
        text = f.read()
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


def data_lines(text):
    return [ln for ln in text.splitlines() if ln.strip() != ""]


def utc_epoch(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def parse_fmt(s, fmt):
    return utc_epoch(datetime.strptime(s.strip(), fmt).replace(tzinfo=timezone.utc))


def parse_iso(s):
    s = s.strip()
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    return utc_epoch(datetime.fromisoformat(s))


def fmt_ts(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def money(d):
    d = Decimal(d).quantize(CENT, rounding=ROUND_HALF_EVEN)
    if d == 0:
        return "0.00"
    return "{:.2f}".format(d)


def round_cents(fr):
    """Round an exact Fraction to 0.01, ties to even, returning Decimal."""
    cents = round(fr * 100)  # Fraction.__round__ rounds half to even
    return Decimal(cents) / 100


def text_units(s):
    s = s.strip()
    if DIGITS.fullmatch(s):
        return int(s)
    return None


def header_index(header, names):
    h = [x.strip() for x in header]
    idx = []
    for pos, n in enumerate(names):
        idx.append(h.index(n) if n in h else pos)
    return idx


# ---------------------------------------------------------------- collectors
def read_central(path):
    rows = list(csv.reader(io.StringIO(read_text(path))))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []
    idx = header_index(rows[0], ["record_id", "timestamp", "account", "product", "units"])
    out = []
    for r in rows[1:]:
        g = lambda i: r[idx[i]] if idx[i] < len(r) else ""
        out.append({
            "record_id": g(0).strip(),
            "ts": lambda s=g(1): parse_fmt(s, "%Y-%m-%d %H:%M:%S"),
            "account": g(2).strip(),
            "product": g(3).strip(),
            "units": text_units(g(4)),
        })
    return out


def read_east(path):
    lines = data_lines(read_text(path))
    if not lines:
        return []
    idx = header_index(lines[0].split("\t"), ["id", "epoch", "account", "product", "qty"])
    out = []
    for ln in lines[1:]:
        r = ln.split("\t")
        g = lambda i: r[idx[i]] if idx[i] < len(r) else ""
        out.append({
            "record_id": g(0).strip(),
            "ts": lambda s=g(1): int(s.strip()),
            "account": g(2).strip(),
            "product": g(3).strip(),
            "units": text_units(g(4)),
        })
    return out


def read_north(path):
    out = []
    for ln in data_lines(read_text(path)):
        o = json.loads(ln)
        u = o.get("units")
        units = u if (isinstance(u, int) and not isinstance(u, bool)) else None
        out.append({
            "record_id": str(o.get("id", "")).strip(),
            "ts": lambda s=str(o.get("at", "")): parse_iso(s),
            "account": str(o.get("acct", "")).strip(),
            "product": str(o.get("sku", "")).strip(),
            "units": units,
        })
    return out


def read_south(path):
    out = []
    for ln in data_lines(read_text(path, encoding="latin-1")):
        out.append({
            "record_id": ln[0:10].strip(),
            "ts": lambda s=ln[10:24]: parse_fmt(s, "%Y%m%d%H%M%S"),
            "account": ln[24:34].strip(),
            "product": ln[34:46].strip(),
            "units": text_units(ln[46:52]),
        })
    return out


def read_west(path):
    out = []
    for ln in data_lines(read_text(path)):
        parts = ln.split()
        kv = {}
        for tok in parts[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k.strip()] = v
        out.append({
            "record_id": kv.get("rec", "").strip(),
            "ts": lambda s=parts[0]: parse_iso(s),
            "account": kv.get("acct", "").strip(),
            "product": kv.get("product", "").strip(),
            "units": text_units(kv.get("qty", "")),
        })
    return out


READERS = {"central": read_central, "east": read_east, "north": read_north,
           "south": read_south, "west": read_west}


# ---------------------------------------------------------------- reference
def read_accounts(path):
    rows = list(csv.reader(io.StringIO(read_text(path))))
    rows = [r for r in rows if any(c.strip() for c in r)]
    idx = header_index(rows[0], ["account_id", "segment", "plan", "parent"])
    accounts = {}
    for r in rows[1:]:
        g = lambda i: r[idx[i]].strip() if idx[i] < len(r) else ""
        aid = canon(g(0))
        parent = canon(g(3)) if g(3) else ""
        accounts[aid] = {"segment": g(1).lower(), "plan": g(2).lower(), "parent": parent}
    return accounts


def billing_groups(accounts):
    groups = {}
    for aid in accounts:
        cur, seen = aid, set()
        while True:
            seen.add(cur)
            par = accounts[cur]["parent"] if cur in accounts else ""
            if not par or par in seen:
                break
            cur = par
            if cur not in accounts:
                break
        groups[aid] = cur
    return groups


def read_plan_changes(path, accounts):
    lines = data_lines(read_text(path))
    per_acct = {}
    applied = 0
    for pos, ln in enumerate(lines):
        parts = ln.split()
        ts = parse_iso(parts[0])
        kv = {}
        for tok in parts[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k.strip().lower()] = v.strip()
        acct = canon(kv.get("account", ""))
        if acct not in accounts:
            continue
        applied += 1
        ch = {}
        if "plan" in kv:
            ch["plan"] = kv["plan"].lower()
        if "segment" in kv:
            ch["segment"] = kv["segment"].lower()
        per_acct.setdefault(acct, []).append((ts, pos, ch))
    timeline = {}
    for acct, chs in per_acct.items():
        chs.sort(key=lambda c: (c[0], c[1]))
        state = {"plan": accounts[acct]["plan"], "segment": accounts[acct]["segment"]}
        times, states = [], []
        for ts, _, ch in chs:
            state = dict(state)
            state.update(ch)
            times.append(ts)
            states.append(state)
        timeline[acct] = (times, states)
    stats = {"lines": len(lines), "applied": applied, "unmatched": len(lines) - applied}
    return timeline, stats


def in_force(acct, ts, accounts, timeline):
    if acct in timeline:
        times, states = timeline[acct]
        i = bisect.bisect_right(times, ts)
        if i > 0:
            return states[i - 1]["plan"], states[i - 1]["segment"]
    a = accounts[acct]
    return a["plan"], a["segment"]


def read_products(path):
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = lambda o: o.strip().lower()
    cp.read_string(read_text(path))
    codes, units, names = [], {}, {r: {} for r in REGIONS}
    for sec in cp.sections():
        code = sec.strip()
        codes.append(code)
        units[code] = cp.get(sec, "unit", fallback="").strip()
        for r in REGIONS:
            if cp.has_option(sec, r):
                names[r][cp.get(sec, r).strip()] = code
    return codes, units, names


def to_dec(v):
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v).strip())


def read_rate_card(path):
    card = json.loads(read_text(path), parse_float=Decimal)
    out = {}
    for code, spec in card["products"].items():
        tiers = []
        for t in spec["tiers"]:
            tiers.append((to_dec(t["from"]), int(t["tier"]),
                          {k.strip().lower(): to_dec(v) for k, v in t["rates"].items()}))
        tiers.sort(key=lambda x: x[0])
        out[code.strip()] = tiers
    return out


def read_commitments(path):
    root = ET.fromstring(read_text(path).encode("utf-8"))
    pools = {}
    for el in root.iter("pool"):
        reg = el.get("region", "").strip().lower()
        pools[reg] = (Decimal(el.get("amount", "0").strip()), Decimal(el.get("minimum", "0").strip()))
    return pools


# ---------------------------------------------------------------- allocation
def share(total, counted, line_charge):
    """Two-pass proportional allocation of `total` over counted line indices."""
    result = {}
    base = sum((line_charge[i] for i in counted), Decimal(0))
    if base <= 0:
        return {i: Decimal(0) for i in counted}
    tot = Fraction(total)
    first = {i: round_cents(tot * Fraction(line_charge[i]) / Fraction(base)) for i in counted}
    keep = [i for i in counted if first[i] >= Decimal("0.50")]
    for i in counted:
        result[i] = Decimal(0)
    if not keep:
        return result
    kbase = sum((line_charge[i] for i in keep), Decimal(0))
    if kbase <= 0:
        return result
    for i in keep:
        result[i] = round_cents(tot * Fraction(line_charge[i]) / Fraction(kbase))
    return result


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    ind, outd = args.input, args.output

    for name in INPUT_FILES:
        if not os.path.isfile(os.path.join(ind, name)):
            fail("missing input: " + name)

    controls = json.loads(read_text(os.path.join(ind, "collector_controls.json")))
    month = str(controls["month"]).strip()
    year, mon = int(month[:4]), int(month[5:7])
    m_start = calendar.timegm((year, mon, 1, 0, 0, 0))
    ny, nm = (year + 1, 1) if mon == 12 else (year, mon + 1)
    m_end = calendar.timegm((ny, nm, 1, 0, 0, 0))

    raw = {}
    for reg in REGIONS:
        recs = READERS[reg](os.path.join(ind, COLLECTOR_FILES[reg]))
        expected = controls["collectors"][reg]["records"]
        if len(recs) != int(expected):
            fail("control mismatch: " + COLLECTOR_FILES[reg])
        raw[reg] = recs

    accounts = read_accounts(os.path.join(ind, "accounts.csv"))
    groups = billing_groups(accounts)
    timeline, pc_stats = read_plan_changes(os.path.join(ind, "plan_changes.log"), accounts)
    rates = read_rate_card(os.path.join(ind, "rate_card.json"))
    pools = read_commitments(os.path.join(ind, "commitments.xml"))
    codes, prod_units, prod_names = read_products(os.path.join(ind, "products.ini"))

    # ---- checking
    dq_coll = {}
    reasons = {r: 0 for r in REASONS}
    quarantined = []
    accepted = []
    for reg in REGIONS:
        seen = set()
        dup = q = acc = 0
        for rec in raw[reg]:
            rid = rec["record_id"]
            if rid in seen:
                dup += 1
                continue
            seen.add(rid)
            ts = rec["ts"]()
            acct = canon(rec["account"])
            reason = None
            if not (m_start <= ts < m_end):
                reason = "timestamp_outside_month"
            elif acct not in accounts:
                reason = "unknown_account"
            elif rec["product"] not in prod_names[reg]:
                reason = "unknown_product"
            elif rec["units"] is None:
                reason = "units_not_integer"
            if reason:
                q += 1
                reasons[reason] += 1
                quarantined.append({"collector": reg, "record_id": rid, "reason": reason})
                continue
            acc += 1
            accepted.append({"record_id": rid, "region": reg, "ts": ts, "account": acct,
                             "product": prod_names[reg][rec["product"]], "units": rec["units"]})
        dq_coll[reg] = {"file": COLLECTOR_FILES[reg], "records": len(raw[reg]),
                        "duplicates": dup, "quarantined": q, "accepted": acc}

    # ---- rating
    accepted.sort(key=lambda l: (l["ts"], l["record_id"]))
    counters = {}
    for ln in accepted:
        plan, seg = in_force(ln["account"], ln["ts"], accounts, timeline)
        ln["plan"], ln["segment"] = plan, seg
        key = (ln["product"], groups.get(ln["account"], ln["account"]))
        counter = counters.get(key, 0)
        tiers = rates[ln["product"]]
        chosen = tiers[0]
        for t in tiers:
            if t[0] <= counter:
                chosen = t
        ln["tier"] = chosen[1]
        ln["rate"] = chosen[2][seg]
        ln["charge"] = (Decimal(ln["units"]) * ln["rate"]).quantize(CENT, rounding=ROUND_HALF_EVEN)
        counters[key] = counter + ln["units"]
        ln["credit"] = Decimal(0)
        ln["true_up"] = Decimal(0)

    # ---- credit and true-up
    charges = {i: ln["charge"] for i, ln in enumerate(accepted)}
    region_info = {}
    for reg in REGIONS:
        pool, minimum = pools.get(reg, (Decimal(0), Decimal(0)))
        counted = [i for i, ln in enumerate(accepted)
                   if ln["region"] == reg and accounts[ln["account"]]["plan"] == "committed"]
        base = sum((charges[i] for i in counted), Decimal(0))
        if base <= pool:
            for i in counted:
                accepted[i]["credit"] = charges[i]
        else:
            for i, v in share(pool, counted, charges).items():
                accepted[i]["credit"] = v
        if base < minimum:
            for i, v in share(minimum - base, counted, charges).items():
                accepted[i]["true_up"] = v
        region_info[reg] = (pool, minimum, base)
    for ln in accepted:
        ln["net"] = ln["charge"] - ln["credit"] + ln["true_up"]

    # ---- outputs
    os.makedirs(outd, exist_ok=True)

    def dump(name, obj):
        with open(os.path.join(outd, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.write("\n")

    def total(lines, field):
        return sum((l[field] for l in lines), Decimal(0))

    def units_by(lines):
        u = {c: 0 for c in codes}
        for l in lines:
            u[l["product"]] = u.get(l["product"], 0) + l["units"]
        return u

    with open(os.path.join(outd, "normalized.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        for l in accepted:
            f.write(json.dumps({
                "record_id": l["record_id"], "region": l["region"], "timestamp": fmt_ts(l["ts"]),
                "account_id": l["account"], "segment": l["segment"], "plan": l["plan"],
                "product": l["product"], "units": l["units"], "tier": l["tier"],
                "unit_rate": "{:.4f}".format(l["rate"].quantize(RATE_Q, rounding=ROUND_HALF_EVEN)),
                "charge": money(l["charge"]), "credit": money(l["credit"]),
                "true_up": money(l["true_up"]), "net": money(l["net"]),
            }, ensure_ascii=False) + "\n")

    dump("summary.json", {
        "month": month, "lines": len(accepted),
        "accounts_billed": len({l["account"] for l in accepted}),
        "units": units_by(accepted),
        "charge": money(total(accepted, "charge")), "credit": money(total(accepted, "credit")),
        "true_up": money(total(accepted, "true_up")), "net": money(total(accepted, "net")),
    })

    products = {}
    for c in codes:
        ls = [l for l in accepted if l["product"] == c]
        products[c] = {"unit": prod_units[c], "lines": len(ls), "units": sum(l["units"] for l in ls),
                       "charge": money(total(ls, "charge")), "credit": money(total(ls, "credit")),
                       "true_up": money(total(ls, "true_up")), "net": money(total(ls, "net"))}
    dump("product_summary.json", {"month": month, "products": products})

    for reg in REGIONS:
        ls = [l for l in accepted if l["region"] == reg]
        pool, minimum, base = region_info[reg]
        applied = total(ls, "credit")
        dump("region_%s.json" % reg, {
            "region": reg, "month": month, "lines": len(ls),
            "accounts": len({l["account"] for l in ls}), "units": units_by(ls),
            "charge": money(total(ls, "charge")), "credit_pool": money(pool),
            "credit_base": money(base), "credit_applied": money(applied),
            "credit_unallocated": money(pool - applied), "minimum": money(minimum),
            "true_up": money(total(ls, "true_up")), "net": money(total(ls, "net")),
        })

    for seg in SEGMENTS:
        ls = [l for l in accepted if l["segment"] == seg]
        byp = {}
        for c in codes:
            pl = [l for l in ls if l["product"] == c]
            byp[c] = {"lines": len(pl), "units": sum(l["units"] for l in pl),
                      "charge": money(total(pl, "charge"))}
        dump("segment_%s.json" % seg, {
            "segment": seg, "month": month, "lines": len(ls),
            "accounts": len({l["account"] for l in ls}), "by_product": byp,
            "charge": money(total(ls, "charge")), "credit": money(total(ls, "credit")),
            "true_up": money(total(ls, "true_up")), "net": money(total(ls, "net")),
        })

    quarantined.sort(key=lambda q: (q["collector"], q["record_id"]))
    dump("data_quality.json", {
        "month": month, "collectors": dq_coll, "quarantine_reasons": reasons,
        "quarantined_records": quarantined, "plan_changes": pc_stats,
    })


if __name__ == "__main__":
    main()
