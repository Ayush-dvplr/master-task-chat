#!/usr/bin/env python3
"""Rate one billing month of metered usage, as set out in rating_contract.md."""

import argparse
import bisect
import calendar
import configparser
import csv
import io
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction

REGIONS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "smb", "corporate", "enterprise"]
REASONS = [
    "timestamp_outside_month",
    "unknown_account",
    "unknown_product",
    "units_not_integer",
]
COLLECTOR_FILES = {
    "central": "collector_central.csv",
    "east": "collector_east.tsv",
    "north": "collector_north.jsonl",
    "south": "collector_south.txt",
    "west": "collector_west.log",
}
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


def fail(message):
    sys.stderr.write(message + "\n")
    sys.exit(1)


def canon_account(value):
    return value.strip().upper().replace("-", "")


def round_cents(fr):
    """Round a Fraction of dollars to whole cents, ties to the even cent."""
    scaled = fr * 100
    num, den = scaled.numerator, scaled.denominator
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2 != 0):
        q += 1
    return q


def money(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return "%s%d.%02d" % (sign, cents // 100, cents % 100)


def rate_text(text):
    return str(Decimal(text).quantize(Decimal("0.0001")))


def read_text(path, encoding="utf-8"):
    with open(path, "r", encoding=encoding, newline="") as handle:
        return handle.read()


def split_lines(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    return lines


# --------------------------------------------------------------------------
# reference inputs
# --------------------------------------------------------------------------

def load_controls(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    month = str(data["month"]).strip()
    collectors = {}
    for region in REGIONS:
        entry = data.get("collectors", {}).get(region, {})
        collectors[region] = {
            "file": str(entry.get("file", COLLECTOR_FILES[region])).strip(),
            "records": int(entry["records"]),
        }
    return month, collectors


def month_bounds(month):
    year, mon = (int(part) for part in month.split("-")[:2])
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=calendar.monthrange(year, mon)[1])
    return start, end


def load_accounts(path):
    accounts = {}
    order = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("account_id"):
                continue
            account_id = canon_account(row["account_id"])
            if account_id == "":
                continue
            accounts[account_id] = {
                "segment": (row.get("segment") or "").strip(),
                "plan": (row.get("plan") or "").strip(),
                "parent": canon_account(row.get("parent") or ""),
            }
            order.append(account_id)
    groups = {}
    for account_id in order:
        current = account_id
        seen = {current}
        while True:
            parent = accounts[current]["parent"]
            if parent == "" or parent not in accounts or parent in seen:
                break
            seen.add(parent)
            current = parent
        groups[account_id] = current
    return accounts, groups


def load_plan_changes(path, accounts):
    events = {}
    total = applied = unmatched = 0
    for line in split_lines(read_text(path)):
        if line.strip() == "":
            continue
        total += 1
        tokens = line.split()
        fields = {}
        account = None
        for token in tokens[1:]:
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            key, value = key.strip(), value.strip()
            if key == "account":
                account = canon_account(value)
            elif key in ("plan", "segment"):
                fields[key] = value
        if account is None or account not in accounts:
            unmatched += 1
            continue
        applied += 1
        when = datetime.strptime(tokens[0].strip(), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        events.setdefault(account, []).append((when, fields))

    history = {}
    for account, items in events.items():
        items.sort(key=lambda item: item[0])
        plan = accounts[account]["plan"]
        segment = accounts[account]["segment"]
        stamps, plans, segments = [], [], []
        for when, fields in items:
            plan = fields.get("plan", plan)
            segment = fields.get("segment", segment)
            stamps.append(when)
            plans.append(plan)
            segments.append(segment)
        history[account] = (stamps, plans, segments)
    return history, {"lines": total, "applied": applied, "unmatched": unmatched}


def load_products(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(read_text(path))
    codes = []
    units = {}
    names = {region: {} for region in REGIONS}
    for section in parser.sections():
        code = section.strip()
        codes.append(code)
        units[code] = (parser[section].get("unit") or "").strip()
        for region in REGIONS:
            name = parser[section].get(region)
            if name is not None:
                names[region][name.strip()] = code
    return codes, units, names


def load_rate_card(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle, parse_float=str)
    tiers = {}
    for code, entry in data["products"].items():
        rows = []
        for tier in entry["tiers"]:
            rates = {
                segment.strip(): str(rate).strip()
                for segment, rate in tier["rates"].items()
            }
            rows.append((Fraction(str(tier["from"])), int(tier["tier"]), rates))
        rows.sort(key=lambda row: row[0])
        tiers[code.strip()] = (
            [row[0] for row in rows],
            [(row[1], row[2]) for row in rows],
        )
    return tiers


def load_commitments(path):
    root = ET.fromstring(read_text(path))
    pools = {}
    for pool in root.iter("pool"):
        region = (pool.get("region") or "").strip()
        pools[region] = (
            Fraction(pool.get("amount").strip()),
            Fraction(pool.get("minimum").strip()),
        )
    return pools


# --------------------------------------------------------------------------
# collector files
# --------------------------------------------------------------------------

def parse_central(path):
    rows = [
        row
        for row in csv.reader(io.StringIO(read_text(path)))
        if any(cell.strip() for cell in row)
    ]
    out = []
    for row in rows[1:]:
        cells = [cell.strip() for cell in row] + [""] * 5
        out.append(
            {
                "record_id": cells[0],
                "stamp": ("naive", cells[1]),
                "account": cells[2],
                "product": cells[3],
                "units": ("digits", cells[4]),
            }
        )
    return out


def parse_east(path):
    out = []
    for line in split_lines(read_text(path))[1:]:
        if line.strip() == "":
            continue
        cells = [cell.strip() for cell in line.split("\t")] + [""] * 5
        out.append(
            {
                "record_id": cells[0],
                "stamp": ("epoch", cells[1]),
                "account": cells[2],
                "product": cells[3],
                "units": ("digits", cells[4]),
            }
        )
    return out


def parse_north(path):
    out = []
    for line in split_lines(read_text(path)):
        if line.strip() == "":
            continue
        obj = json.loads(line)
        out.append(
            {
                "record_id": str(obj.get("id", "")).strip(),
                "stamp": ("iso_z", str(obj.get("at", "")).strip()),
                "account": str(obj.get("acct", "")).strip(),
                "product": str(obj.get("sku", "")).strip(),
                "units": ("json", obj.get("units")),
            }
        )
    return out


def parse_south(path):
    out = []
    for line in split_lines(read_text(path, "latin-1")):
        if line.strip() == "":
            continue
        padded = line.ljust(72)
        out.append(
            {
                "record_id": padded[0:10].strip(),
                "stamp": ("compact", padded[10:24].strip()),
                "account": padded[24:34].strip(),
                "product": padded[34:46].strip(),
                "units": ("digits", padded[46:52].strip()),
            }
        )
    return out


def parse_west(path):
    out = []
    for line in split_lines(read_text(path)):
        if line.strip() == "":
            continue
        tokens = line.split()
        fields = {}
        for token in tokens[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key.strip()] = value.strip()
        out.append(
            {
                "record_id": fields.get("rec", ""),
                "stamp": ("offset", tokens[0].strip()),
                "account": fields.get("acct", ""),
                "product": fields.get("product", ""),
                "units": ("digits", fields.get("qty", "")),
            }
        )
    return out


PARSERS = {
    "central": parse_central,
    "east": parse_east,
    "north": parse_north,
    "south": parse_south,
    "west": parse_west,
}


def to_utc(stamp):
    kind, value = stamp
    if kind == "naive":
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    if kind == "epoch":
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    if kind == "iso_z":
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    if kind == "compact":
        return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    text = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def read_units(units):
    """The whole number of units, or None when not in the collector's form."""
    kind, value = units
    if kind == "digits":
        if isinstance(value, str) and value.isascii() and value.isdigit():
            return int(value)
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


# --------------------------------------------------------------------------
# rating
# --------------------------------------------------------------------------

def collect_lines(in_dir, controls, month_start, month_end, accounts, product_names):
    accepted = []
    quarantined = []
    stats = {}
    for region in REGIONS:
        records = PARSERS[region](os.path.join(in_dir, COLLECTOR_FILES[region]))
        if len(records) != controls[region]["records"]:
            fail("control mismatch: %s" % controls[region]["file"])
        seen = set()
        duplicates = bad = good = 0
        for record in records:
            record_id = record["record_id"]
            if record_id in seen:
                duplicates += 1
                continue
            seen.add(record_id)
            when = to_utc(record["stamp"])
            account = canon_account(record["account"])
            code = product_names[region].get(record["product"].strip())
            units = read_units(record["units"])
            if not (month_start <= when < month_end):
                reason = "timestamp_outside_month"
            elif account not in accounts:
                reason = "unknown_account"
            elif code is None:
                reason = "unknown_product"
            elif units is None:
                reason = "units_not_integer"
            else:
                reason = None
            if reason is not None:
                bad += 1
                quarantined.append(
                    {"collector": region, "record_id": record_id, "reason": reason}
                )
                continue
            good += 1
            accepted.append(
                {
                    "record_id": record_id,
                    "region": region,
                    "when": when,
                    "account_id": account,
                    "product": code,
                    "units": units,
                }
            )
        stats[region] = {
            "file": controls[region]["file"],
            "records": len(records),
            "duplicates": duplicates,
            "quarantined": bad,
            "accepted": good,
        }
    return accepted, quarantined, stats


def rate_lines(accepted, accounts, groups, history, rate_tiers):
    accepted.sort(key=lambda line: (line["when"], line["record_id"]))
    counters = {}
    for line in accepted:
        account = line["account_id"]
        info = accounts[account]
        plan, segment = info["plan"], info["segment"]
        if account in history:
            stamps, plans, segments = history[account]
            index = bisect.bisect_right(stamps, line["when"]) - 1
            if index >= 0:
                plan, segment = plans[index], segments[index]
        code = line["product"]
        key = (groups[account], code)
        counter = counters.get(key, 0)
        starts, rows = rate_tiers[code]
        index = max(bisect.bisect_right(starts, Fraction(counter)) - 1, 0)
        tier_number, rates = rows[index]
        rate = rates[segment]
        counters[key] = counter + line["units"]
        line["segment"] = segment
        line["plan"] = plan
        line["tier"] = tier_number
        line["unit_rate"] = rate
        line["charge"] = round_cents(Fraction(line["units"]) * Fraction(rate))
        line["committed"] = info["plan"] == "committed"
        line["credit"] = 0
        line["true_up"] = 0


def share(counted, total, base):
    """Share `total` dollars over `counted` lines in proportion to charge."""
    first = [
        round_cents(total * Fraction(line["charge"], 100) / base) for line in counted
    ]
    keep = [line for line, value in zip(counted, first) if value >= 50]
    if not keep:
        return {}
    sub = Fraction(sum(line["charge"] for line in keep), 100)
    return {
        id(line): round_cents(total * Fraction(line["charge"], 100) / sub)
        for line in keep
    }


def apply_credit(accepted, pools):
    for region in REGIONS:
        counted = [
            line for line in accepted if line["region"] == region and line["committed"]
        ]
        if not counted:
            continue
        base = Fraction(sum(line["charge"] for line in counted), 100)
        pool, minimum = pools.get(region, (Fraction(0), Fraction(0)))
        if base <= pool:
            for line in counted:
                line["credit"] = line["charge"]
        else:
            shares = share(counted, pool, base)
            for line in counted:
                line["credit"] = shares.get(id(line), 0)
        if base < minimum:
            shares = share(counted, minimum - base, base)
            for line in counted:
                line["true_up"] = shares.get(id(line), 0)
    for line in accepted:
        line["net"] = line["charge"] - line["credit"] + line["true_up"]


# --------------------------------------------------------------------------
# output documents
# --------------------------------------------------------------------------

def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_outputs(
    out_dir,
    month,
    codes,
    product_units,
    accepted,
    stats,
    quarantined,
    plan_change_stats,
    pools,
):
    path = os.path.join(out_dir, "normalized.jsonl")
    with open(path, "w", encoding="utf-8") as handle:
        for line in accepted:
            handle.write(
                json.dumps(
                    {
                        "record_id": line["record_id"],
                        "region": line["region"],
                        "timestamp": line["when"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "account_id": line["account_id"],
                        "segment": line["segment"],
                        "plan": line["plan"],
                        "product": line["product"],
                        "units": line["units"],
                        "tier": line["tier"],
                        "unit_rate": rate_text(line["unit_rate"]),
                        "charge": money(line["charge"]),
                        "credit": money(line["credit"]),
                        "true_up": money(line["true_up"]),
                        "net": money(line["net"]),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    def totals(lines):
        return {
            key: sum(line[key] for line in lines)
            for key in ("charge", "credit", "true_up", "net")
        }

    def units_by_product(lines):
        out = {code: 0 for code in codes}
        for line in lines:
            out[line["product"]] += line["units"]
        return out

    grand = totals(accepted)
    write_json(
        os.path.join(out_dir, "summary.json"),
        {
            "month": month,
            "lines": len(accepted),
            "accounts_billed": len({line["account_id"] for line in accepted}),
            "units": units_by_product(accepted),
            "charge": money(grand["charge"]),
            "credit": money(grand["credit"]),
            "true_up": money(grand["true_up"]),
            "net": money(grand["net"]),
        },
    )

    products = {}
    for code in codes:
        lines = [line for line in accepted if line["product"] == code]
        sums = totals(lines)
        products[code] = {
            "unit": product_units[code],
            "lines": len(lines),
            "units": sum(line["units"] for line in lines),
            "charge": money(sums["charge"]),
            "credit": money(sums["credit"]),
            "true_up": money(sums["true_up"]),
            "net": money(sums["net"]),
        }
    write_json(
        os.path.join(out_dir, "product_summary.json"),
        {"month": month, "products": products},
    )

    for region in REGIONS:
        lines = [line for line in accepted if line["region"] == region]
        sums = totals(lines)
        pool, minimum = pools.get(region, (Fraction(0), Fraction(0)))
        pool_cents = round_cents(pool)
        write_json(
            os.path.join(out_dir, "region_%s.json" % region),
            {
                "region": region,
                "month": month,
                "lines": len(lines),
                "accounts": len({line["account_id"] for line in lines}),
                "units": units_by_product(lines),
                "charge": money(sums["charge"]),
                "credit_pool": money(pool_cents),
                "credit_base": money(
                    sum(line["charge"] for line in lines if line["committed"])
                ),
                "credit_applied": money(sums["credit"]),
                "credit_unallocated": money(pool_cents - sums["credit"]),
                "minimum": money(round_cents(minimum)),
                "true_up": money(sums["true_up"]),
                "net": money(sums["net"]),
            },
        )

    for segment in SEGMENTS:
        lines = [line for line in accepted if line["segment"] == segment]
        sums = totals(lines)
        by_product = {}
        for code in codes:
            subset = [line for line in lines if line["product"] == code]
            by_product[code] = {
                "lines": len(subset),
                "units": sum(line["units"] for line in subset),
                "charge": money(sum(line["charge"] for line in subset)),
            }
        write_json(
            os.path.join(out_dir, "segment_%s.json" % segment),
            {
                "segment": segment,
                "month": month,
                "lines": len(lines),
                "accounts": len({line["account_id"] for line in lines}),
                "by_product": by_product,
                "charge": money(sums["charge"]),
                "credit": money(sums["credit"]),
                "true_up": money(sums["true_up"]),
                "net": money(sums["net"]),
            },
        )

    reason_counts = {reason: 0 for reason in REASONS}
    for item in quarantined:
        reason_counts[item["reason"]] += 1
    write_json(
        os.path.join(out_dir, "data_quality.json"),
        {
            "month": month,
            "collectors": {region: stats[region] for region in REGIONS},
            "quarantine_reasons": reason_counts,
            "quarantined_records": sorted(
                quarantined, key=lambda item: (item["collector"], item["record_id"])
            ),
            "plan_changes": plan_change_stats,
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    for name in INPUT_FILES:
        if not os.path.isfile(os.path.join(args.input, name)):
            fail("missing input: %s" % name)

    month, controls = load_controls(
        os.path.join(args.input, "collector_controls.json")
    )
    month_start, month_end = month_bounds(month)
    accounts, groups = load_accounts(os.path.join(args.input, "accounts.csv"))
    history, plan_change_stats = load_plan_changes(
        os.path.join(args.input, "plan_changes.log"), accounts
    )
    codes, product_units, product_names = load_products(
        os.path.join(args.input, "products.ini")
    )
    rate_tiers = load_rate_card(os.path.join(args.input, "rate_card.json"))
    pools = load_commitments(os.path.join(args.input, "commitments.xml"))

    accepted, quarantined, stats = collect_lines(
        args.input, controls, month_start, month_end, accounts, product_names
    )
    rate_lines(accepted, accounts, groups, history, rate_tiers)
    apply_credit(accepted, pools)

    os.makedirs(args.output, exist_ok=True)
    write_outputs(
        args.output,
        month,
        codes,
        product_units,
        accepted,
        stats,
        quarantined,
        plan_change_stats,
        pools,
    )


if __name__ == "__main__":
    main()
