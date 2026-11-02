#!/usr/bin/env python3
"""Concierge desk billing run.

Usage: python3 transform.py DATA_DIR OUT_DIR
Standard library only. Reads only DATA_DIR, writes only OUT_DIR.
"""
import csv
import datetime as dt
import json
import os
import sys
from collections import defaultdict

REGIONS = ("central", "east", "north", "south", "west")
SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
TIERS = ("standard", "after_hours", "weekend_holiday")
OFFSET_RANGE = range(-19, 20)


def read_text(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return fh.read()


def read_csv(path):
    text = read_text(path)
    reader = csv.reader(text.splitlines())
    rows = []
    header = None
    for raw in reader:
        if header is None:
            if not raw or all(not c.strip() for c in raw):
                continue
            header = [c.strip() for c in raw]
            continue
        if not raw or all(not c.strip() for c in raw):
            continue
        rec = {}
        for i, name in enumerate(header):
            rec[name] = raw[i].strip() if i < len(raw) else ""
        rows.append(rec)
    return rows


def parse_instant(s):
    return dt.datetime.strptime(s.strip(), "%Y-%m-%dT%H:%M:%S")


def parse_day(s):
    return dt.datetime.strptime(s.strip(), "%Y-%m-%d").date()


def parse_legacy_instant(s):
    return dt.datetime.strptime(" ".join(s.split()), "%d.%m.%Y %H:%M:%S")


def fmt_instant(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S")


def fmt_day(d):
    return d.strftime("%Y-%m-%d")


def parse_slot(s):
    hh, mm = s.strip().split(":")
    return int(hh) * 60 + int(mm)


def round_cents(micro):
    q, r = divmod(micro, 10000)
    if r > 5000 or (r == 5000 and q % 2 == 1):
        q += 1
    return q


def dump(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]

    def dp(name):
        return os.path.join(data_dir, name)

    # ---------- reference data ----------
    cycle = json.loads(read_text(dp("cycle.json")))
    cycle_name = str(cycle["cycle"]).strip()
    first_day = parse_day(str(cycle["first_day"]))
    last_day = parse_day(str(cycle["last_day"]))
    rate_card_name = str(cycle["rate_card"]).strip()
    minimum_invoice = int(cycle["minimum_invoice_micro"])

    clients = {}
    for r in read_csv(dp("clients.csv")):
        clients[r["client"]] = {
            "line": r["line"],
            "segment": r["segment"],
            "region": r["region"],
            "plan": r["plan"],
            "zone": r["zone"],
        }

    plans = {}
    for r in read_csv(dp("plans.csv")):
        plans[r["plan"]] = {
            "included": int(r["included_minutes"]),
            "tiers": set(r["credit_tiers"].split()),
        }

    catalog = {}
    for r in read_csv(dp("service_catalog.csv")):
        catalog[r["service"].upper()] = {
            "product_line": r["product_line"],
            "increment": int(r["increment_minutes"]),
        }

    aliases = {}
    for r in read_csv(dp("code_aliases.csv")):
        aliases[r["alias"].upper()] = r["service"].upper()

    zones = defaultdict(list)
    for r in read_csv(dp("zone_rules.csv")):
        zones[r["zone"]].append((parse_instant(r["from_utc"]), int(r["utc_offset_minutes"])))
    for z in zones:
        zones[z].sort()

    holidays = set()
    for r in read_csv(dp("holidays.csv")):
        holidays.add((r["region"], parse_day(r["day"])))

    rates = defaultdict(list)
    for r in read_csv(dp(rate_card_name)):
        eff_to = r.get("effective_to", "")
        rates[(r["service"].upper(), r["tier"])].append(
            (
                parse_day(r["effective_from"]),
                parse_day(eff_to) if eff_to else None,
                int(r["rate_micro_per_minute"]),
            )
        )

    register = {}
    for r in read_csv(dp("exchange_register.csv")):
        key = (r["line"], parse_day(r["day"]), parse_slot(r["slot"]))
        register[key] = register.get(key, 0) + int(r["calls"])

    # ---------- closings ----------
    main_rows = []
    for r in read_csv(dp("closings.csv")):
        main_rows.append(
            {
                "ref": r["ref"],
                "handset": r["handset"],
                "seq": int(r["seq"]),
                "client": r["client"],
                "service_code": r["service"].upper(),
                "stamp": parse_instant(r["stamped_at"]),
                "worked": int(r["worked_minutes"]),
            }
        )

    legacy_rows = []
    legacy_path = dp("legacy_closings.txt")
    if os.path.exists(legacy_path):
        unit = "minutes"
        lines = read_text(legacy_path).splitlines()
        for ln in lines:
            s = ln.strip()
            if s.startswith("#"):
                body = s[1:].strip()
                if body.lower().startswith("duration unit:"):
                    unit = body.split(":", 1)[1].strip().lower()
        for ln in lines:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            f = [x.strip() for x in s.split("|")]
            dur = int(f[6])
            worked = -(-dur // 60) if unit.startswith("second") else dur
            legacy_rows.append(
                {
                    "ref": f[0],
                    "handset": f[1],
                    "seq": int(f[2]),
                    "client": f[3],
                    "service_code": f[4].upper(),
                    "stamp": parse_legacy_instant(f[5]),
                    "worked": worked,
                }
            )

    main_ids = {(c["handset"], c["seq"]) for c in main_rows}
    duplicates = []
    received = list(main_rows)
    for c in legacy_rows:
        if (c["handset"], c["seq"]) in main_ids:
            duplicates.append(c["ref"])
        else:
            received.append(c)

    # ---------- handset clock offsets from the exchange register ----------
    by_handset = defaultdict(list)
    for c in received:
        cli = clients.get(c["client"])
        if cli is not None:
            by_handset[c["handset"]].append((cli["line"], c["stamp"]))
    offsets = {}
    for h, items in by_handset.items():
        best = None
        for k in OFFSET_RANGE:
            delta = dt.timedelta(minutes=k)
            counts = defaultdict(int)
            for line, stamp in items:
                t = stamp + delta
                key = (line, t.date(), t.hour * 60 + t.minute)
                if key in register:
                    counts[key] += 1
            score = sum(min(n, register[key]) for key, n in counts.items())
            cand = (-score, abs(k), k)
            if best is None or cand < best:
                best = cand
        offsets[h] = best[2]

    def zone_offset(zone, instant):
        off = 0
        for start, minutes in zones.get(zone, ()):
            if start <= instant:
                off = minutes
            else:
                break
        return off

    for c in received:
        c["completed"] = c["stamp"] + dt.timedelta(minutes=offsets.get(c["handset"], 0))
        cli = clients[c["client"]]
        c["local"] = c["completed"] + dt.timedelta(minutes=zone_offset(cli["zone"], c["completed"]))
        c["local_day"] = c["local"].date()
        code = c["service_code"]
        if code in catalog:
            c["service"] = code
        elif code in aliases:
            c["service"] = aliases[code]
        else:
            c["service"] = None

    by_identity = {(c["handset"], c["seq"]): c for c in received}

    # ---------- amendments ----------
    amendments = []
    am_path = dp("amendments.jsonl")
    if os.path.exists(am_path):
        for ln in read_text(am_path).splitlines():
            if not ln.strip():
                continue
            o = json.loads(ln)
            amendments.append(
                {
                    "id": str(o.get("amendment")).strip(),
                    "issued": parse_instant(str(o.get("issued_at"))),
                    "action": str(o.get("action")).strip(),
                    "handset": None if o.get("handset") is None else str(o.get("handset")).strip(),
                    "seq": None if o.get("seq") is None else int(o.get("seq")),
                    "minutes": None if o.get("minutes") is None else int(o.get("minutes")),
                    "reverts": None if o.get("reverts") is None else str(o.get("reverts")).strip(),
                }
            )

    no_effect = set()
    vm = {}
    for a in amendments:
        if a["action"] in ("void", "minutes"):
            vm[a["id"]] = a
            target = by_identity.get((a["handset"], a["seq"]))
            if target is None or a["issued"] < target["completed"]:
                no_effect.add(a["id"])
    cancelled = set()
    for a in amendments:
        if a["action"] == "revert":
            target = vm.get(a["reverts"])
            if target is None or not (a["issued"] > target["issued"]):
                no_effect.add(a["id"])
            else:
                cancelled.add(target["id"])
        elif a["action"] not in ("void", "minutes"):
            no_effect.add(a["id"])
    amendments_without_effect = sorted(no_effect | cancelled)

    void_ids = set()
    minutes_override = {}
    active = [a for a in vm.values() if a["id"] not in no_effect and a["id"] not in cancelled]
    active.sort(key=lambda a: (a["issued"], a["id"]))
    for a in active:
        ident = (a["handset"], a["seq"])
        if a["action"] == "void":
            void_ids.add(ident)
        else:
            minutes_override[ident] = a["minutes"]

    # ---------- classification ----------
    rejected = {}
    outside = []
    voids = []
    unrated = []
    billed = []
    for c in received:
        ident = (c["handset"], c["seq"])
        if c["service"] is None:
            rejected[c["ref"]] = "unknown_service"
            continue
        if c["local_day"] < first_day or c["local_day"] > last_day:
            outside.append(c["ref"])
            continue
        if ident in void_ids:
            voids.append(c["ref"])
            continue
        cli = clients[c["client"]]
        d = c["local_day"]
        if d.weekday() >= 5 or (cli["region"], d) in holidays:
            tier = "weekend_holiday"
        else:
            tod = c["local"].hour * 3600 + c["local"].minute * 60 + c["local"].second
            tier = "standard" if 8 * 3600 <= tod < 18 * 3600 else "after_hours"
        c["tier"] = tier
        rate = None
        for start, end, r in rates.get((c["service"], tier), ()):
            if start <= d and (end is None or d < end):
                rate = r
                break
        if rate is None:
            unrated.append(c["ref"])
            continue
        c["rate"] = rate
        c["worked_final"] = minutes_override.get(ident, c["worked"])
        inc = catalog[c["service"]]["increment"]
        c["billable"] = -(-c["worked_final"] // inc) * inc
        billed.append(c)

    # ---------- allowance credit ----------
    per_client = defaultdict(list)
    for c in billed:
        c["credited"] = 0
        per_client[c["client"]].append(c)
    for client, items in per_client.items():
        plan = plans[clients[client]["plan"]]
        left = plan["included"]
        eligible = [c for c in items if c["tier"] in plan["tiers"]]
        eligible.sort(key=lambda c: c["ref"])
        eligible.sort(key=lambda c: c["completed"], reverse=True)
        for c in eligible:
            if left <= 0:
                break
            give = min(c["billable"], left)
            c["credited"] = give
            left -= give
    for c in billed:
        c["charged"] = c["billable"] - c["credited"]
        c["gross"] = c["billable"] * c["rate"]
        c["net"] = c["charged"] * c["rate"]

    billed.sort(key=lambda c: (c["completed"], c["ref"]))

    # ---------- reports ----------
    reports = {}

    norm_lines = []
    for c in billed:
        cli = clients[c["client"]]
        norm_lines.append(
            dump(
                {
                    "billable_minutes": c["billable"],
                    "charged_minutes": c["charged"],
                    "client": c["client"],
                    "completed_at": fmt_instant(c["completed"]),
                    "credited_minutes": c["credited"],
                    "gross_micro": c["gross"],
                    "handset": c["handset"],
                    "line": cli["line"],
                    "local_day": fmt_day(c["local_day"]),
                    "net_micro": c["net"],
                    "product_line": catalog[c["service"]]["product_line"],
                    "rate_micro_per_minute": c["rate"],
                    "ref": c["ref"],
                    "region": cli["region"],
                    "segment": cli["segment"],
                    "seq": c["seq"],
                    "service": c["service"],
                    "tier": c["tier"],
                    "worked_minutes": c["worked_final"],
                }
            )
            + "\n"
        )
    reports["normalized.jsonl"] = "".join(norm_lines)

    def totals(items):
        by_tier = {}
        for c in items:
            by_tier[c["tier"]] = by_tier.get(c["tier"], 0) + c["net"]
        gross = sum(c["gross"] for c in items)
        net = sum(c["net"] for c in items)
        return {
            "by_tier": by_tier,
            "clients": sorted({c["client"] for c in items}),
            "closings": len(items),
            "credit_micro": gross - net,
            "gross_micro": gross,
            "net_cents": round_cents(net),
            "net_micro": net,
        }

    region_net = 0
    for region in REGIONS:
        items = [c for c in billed if clients[c["client"]]["region"] == region]
        rep = totals(items)
        rep["region"] = region
        rep["in_scope"] = rep["gross_micro"] >= minimum_invoice
        region_net += rep["net_micro"]
        reports["region_%s.json" % region] = dump(rep) + "\n"

    segment_net = 0
    for segment in SEGMENTS:
        items = [c for c in billed if clients[c["client"]]["segment"] == segment]
        rep = totals(items)
        rep["segment"] = segment
        rep["in_scope"] = rep["net_micro"] >= minimum_invoice
        segment_net += rep["net_micro"]
        reports["segment_%s.json" % segment] = dump(rep) + "\n"

    product_lines = []
    product_net = 0
    for pl in sorted({v["product_line"] for v in catalog.values()}):
        items = [c for c in billed if catalog[c["service"]]["product_line"] == pl]
        net = sum(c["net"] for c in items)
        product_net += net
        product_lines.append(
            {
                "billable_minutes": sum(c["billable"] for c in items),
                "closings": len(items),
                "gross_micro": sum(c["gross"] for c in items),
                "net_micro": net,
                "product_line": pl,
            }
        )
    reports["product_summary.json"] = dump({"product_lines": product_lines}) + "\n"

    all_tot = totals(billed)
    normalized_net = all_tot["net_micro"]
    summary = {
        "by_tier": all_tot["by_tier"],
        "closings_billed": all_tot["closings"],
        "credit_micro": all_tot["credit_micro"],
        "cycle": cycle_name,
        "gross_micro": all_tot["gross_micro"],
        "net_cents": all_tot["net_cents"],
        "net_micro": all_tot["net_micro"],
        "reconciliation": {
            "normalized_net_micro": normalized_net,
            "product_net_micro": product_net,
            "region_net_micro": region_net,
            "segment_net_micro": segment_net,
            "residual_micro": product_net + region_net + segment_net - 3 * normalized_net,
        },
    }
    reports["summary.json"] = dump(summary) + "\n"

    input_files = sorted(
        name for name in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, name))
    )
    data_quality = {
        "amendments_without_effect": amendments_without_effect,
        "closings_received": len(received),
        "duplicates": sorted(duplicates),
        "input_files": input_files,
        "outside_cycle": sorted(outside),
        "rejected": rejected,
        "unrated": sorted(unrated),
        "void": sorted(voids),
    }
    reports["data_quality.json"] = dump(data_quality) + "\n"

    os.makedirs(out_dir, exist_ok=True)
    out_lines = []
    for name in sorted(reports):
        data = reports[name].encode("ascii")
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(data)
        out_lines.append("wrote %s %d\n" % (name, len(data)))
    sys.stdout.write("".join(out_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
