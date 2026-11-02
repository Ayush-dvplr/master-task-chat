#!/usr/bin/env python3
"""Rate one billing month of metered usage per rating_contract.md."""

import argparse
import bisect
import configparser
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN

COLLECTOR_FILES = [
    ("central", "collector_central.csv"),
    ("east", "collector_east.tsv"),
    ("north", "collector_north.jsonl"),
    ("south", "collector_south.txt"),
    ("west", "collector_west.log"),
]
REGIONS = [region for region, _ in COLLECTOR_FILES]
INPUT_FILES = [name for _, name in COLLECTOR_FILES] + [
    "accounts.csv",
    "plan_changes.log",
    "rate_card.json",
    "commitments.xml",
    "products.ini",
    "collector_controls.json",
]
REASONS = [
    "timestamp_outside_month",
    "unknown_account",
    "unknown_product",
    "units_not_integer",
]
CENT = Decimal("0.01")
RATE_Q = Decimal("0.0001")
DIGITS = re.compile(r"[0-9]+")
UTC = timezone.utc


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def canon_account(value):
    return value.strip().upper().replace("-", "")


def money(value):
    quantized = value.quantize(CENT, rounding=ROUND_HALF_EVEN)
    if quantized == 0:
        quantized = abs(quantized)
    return f"{quantized:.2f}"


def rate_str(value):
    return f"{value.quantize(RATE_Q, rounding=ROUND_HALF_EVEN):.4f}"


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def read_lines(path, encoding="utf-8"):
    with open(path, encoding=encoding, newline="") as handle:
        return handle.read().splitlines()


def digit_units(raw):
    text = raw.strip()
    return int(text) if DIGITS.fullmatch(text) else None


def parse_central(path):
    records = []
    lines = read_lines(path)[1:]
    for row in csv.reader(lines):
        if not row or not any(field.strip() for field in row):
            continue
        row = [field.strip() for field in row] + [""] * (5 - len(row))
        stamp = datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        records.append((row[0], stamp, row[2], row[3], digit_units(row[4])))
    return records


def parse_east(path):
    records = []
    for line in read_lines(path)[1:]:
        if not line.strip():
            continue
        row = [field.strip() for field in line.split("\t")]
        row += [""] * (5 - len(row))
        stamp = datetime.fromtimestamp(int(row[1]), UTC)
        records.append((row[0], stamp, row[2], row[3], digit_units(row[4])))
    return records


def parse_north(path):
    records = []
    for line in read_lines(path):
        if not line.strip():
            continue
        obj = json.loads(line)
        raw = obj.get("units")
        units = raw if isinstance(raw, int) and not isinstance(raw, bool) else None
        stamp = datetime.strptime(str(obj.get("at", "")).strip(), "%Y-%m-%dT%H:%M:%SZ")
        records.append(
            (
                str(obj.get("id", "")).strip(),
                stamp.replace(tzinfo=UTC),
                str(obj.get("acct", "")).strip(),
                str(obj.get("sku", "")).strip(),
                units,
            )
        )
    return records


def parse_south(path):
    records = []
    for line in read_lines(path, encoding="latin-1"):
        if not line.strip():
            continue
        stamp = datetime.strptime(line[10:24].strip(), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        records.append(
            (
                line[0:10].strip(),
                stamp,
                line[24:34].strip(),
                line[34:46].strip(),
                digit_units(line[46:52]),
            )
        )
    return records


def parse_west(path):
    records = []
    for line in read_lines(path):
        if not line.strip():
            continue
        tokens = line.split()
        fields = {}
        for token in tokens[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key.strip()] = value.strip()
        stamp = datetime.fromisoformat(tokens[0].strip()).astimezone(UTC)
        records.append(
            (
                fields.get("rec", ""),
                stamp,
                fields.get("acct", ""),
                fields.get("product", ""),
                digit_units(fields.get("qty", "")),
            )
        )
    return records


PARSERS = {
    "central": parse_central,
    "east": parse_east,
    "north": parse_north,
    "south": parse_south,
    "west": parse_west,
}


def load_accounts(path):
    accounts = {}
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            account = canon_account(row["account_id"] or "")
            if not account:
                continue
            parent = canon_account(row.get("parent") or "")
            accounts[account] = {
                "segment": (row["segment"] or "").strip(),
                "plan": (row["plan"] or "").strip(),
                "group": parent or account,
            }
    return accounts


def load_plan_changes(path, accounts):
    pattern = re.compile(r"(\S+)=(\S+)")
    lines = 0
    applied = 0
    pending = {}
    for index, line in enumerate(read_lines(path)):
        if not line.strip():
            continue
        lines += 1
        parts = line.split()
        stamp = datetime.strptime(parts[0].strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        fields = dict(pattern.findall(line))
        account = canon_account(fields.get("account", ""))
        if account not in accounts:
            continue
        applied += 1
        pending.setdefault(account, []).append(
            (stamp, index, fields.get("plan"), fields.get("segment"))
        )

    timeline = {}
    for account, changes in pending.items():
        changes.sort(key=lambda item: (item[0], item[1]))
        base = accounts[account]
        plan, segment = base["plan"], base["segment"]
        stamps = []
        states = [(plan, segment)]
        for stamp, _, new_plan, new_segment in changes:
            if new_plan is not None:
                plan = new_plan
            if new_segment is not None:
                segment = new_segment
            stamps.append(stamp)
            states.append((plan, segment))
        timeline[account] = (stamps, states)
    return lines, applied, lines - applied, timeline


def in_force(accounts, timeline, account, stamp):
    entry = timeline.get(account)
    if entry is None:
        base = accounts[account]
        return base["plan"], base["segment"]
    stamps, states = entry
    return states[bisect.bisect_right(stamps, stamp)]


def load_products(path):
    parser = configparser.ConfigParser()
    with open(path, encoding="utf-8") as handle:
        parser.read_file(handle)
    codes = []
    units = {}
    names = {region: {} for region in REGIONS}
    for code in parser.sections():
        codes.append(code)
        units[code] = parser[code].get("unit", "").strip()
        for region in REGIONS:
            name = parser[code].get(region)
            if name is not None:
                names[region][name.strip()] = code
    return codes, units, names


def load_rate_card(path):
    with open(path, encoding="utf-8") as handle:
        card = json.load(handle, parse_float=Decimal, parse_int=int)
    tiers = {}
    segments = set()
    for code, entry in card["products"].items():
        ordered = sorted(entry["tiers"], key=lambda tier: Decimal(str(tier["from"])))
        tiers[code] = [
            (
                Decimal(str(tier["from"])),
                tier["tier"],
                {name: Decimal(str(rate)) for name, rate in tier["rates"].items()},
            )
            for tier in ordered
        ]
        for tier in entry["tiers"]:
            segments.update(tier["rates"].keys())
    return tiers, sorted(segments)


def load_commitments(path):
    pools = {}
    root = ET.parse(path).getroot()
    for pool in root.iter("pool"):
        pools[(pool.get("region") or "").strip()] = Decimal((pool.get("amount") or "0").strip())
    return pools


def pick_tier(tiers, counter):
    chosen = tiers[0]
    for tier in tiers:
        if tier[0] <= counter:
            chosen = tier
        else:
            break
    return chosen


def month_bounds(month):
    year, mon = (int(part) for part in month.split("-"))
    start = datetime(year, mon, 1, tzinfo=UTC)
    end = datetime(year + (mon // 12), (mon % 12) + 1, 1, tzinfo=UTC)
    return start, end


def zero_units(codes):
    return {code: 0 for code in codes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    in_dir, out_dir = args.input, args.output

    for name in INPUT_FILES:
        if not os.path.isfile(os.path.join(in_dir, name)):
            fail(f"missing input: {name}")

    with open(os.path.join(in_dir, "collector_controls.json"), encoding="utf-8") as handle:
        controls = json.load(handle)
    month = controls["month"]
    start, end = month_bounds(month)
    control_info = controls.get("collectors", {})

    accounts = load_accounts(os.path.join(in_dir, "accounts.csv"))
    change_lines, change_applied, change_unmatched, timeline = load_plan_changes(
        os.path.join(in_dir, "plan_changes.log"), accounts
    )
    codes, product_units, product_names = load_products(os.path.join(in_dir, "products.ini"))
    tiers, segments = load_rate_card(os.path.join(in_dir, "rate_card.json"))
    pools = load_commitments(os.path.join(in_dir, "commitments.xml"))

    stats = {
        region: {"duplicates": 0, "quarantined": 0, "accepted": 0, "records": 0}
        for region in REGIONS
    }
    reason_counts = {reason: 0 for reason in REASONS}
    quarantined = []
    accepted = []

    for region_index, (region, filename) in enumerate(COLLECTOR_FILES):
        records = PARSERS[region](os.path.join(in_dir, filename))
        stats[region]["records"] = len(records)
        expected = control_info.get(region, {}).get("records")
        if expected is not None and len(records) != expected:
            fail(f"control mismatch: {filename}")

        seen = set()
        for line_index, (record_id, stamp, raw_account, raw_product, units) in enumerate(records):
            if record_id in seen:
                stats[region]["duplicates"] += 1
                continue
            seen.add(record_id)

            account = canon_account(raw_account)
            if not start <= stamp < end:
                reason = "timestamp_outside_month"
            elif account not in accounts:
                reason = "unknown_account"
            elif raw_product not in product_names[region]:
                reason = "unknown_product"
            elif units is None:
                reason = "units_not_integer"
            else:
                reason = None

            if reason is not None:
                stats[region]["quarantined"] += 1
                reason_counts[reason] += 1
                quarantined.append(
                    {"collector": region, "record_id": record_id, "reason": reason}
                )
                continue

            stats[region]["accepted"] += 1
            accepted.append(
                {
                    "record_id": record_id,
                    "region": region,
                    "stamp": stamp,
                    "account": account,
                    "code": product_names[region][raw_product],
                    "units": units,
                    "sort": (stamp, record_id, region_index, line_index),
                }
            )

    accepted.sort(key=lambda line: line["sort"])

    counters = {}
    for line in accepted:
        plan, segment = in_force(accounts, timeline, line["account"], line["stamp"])
        key = (accounts[line["account"]]["group"], line["code"])
        counter = counters.get(key, 0)
        _, tier_number, rates = pick_tier(tiers[line["code"]], counter)
        rate = rates[segment]
        line["plan"] = plan
        line["segment"] = segment
        line["tier"] = tier_number
        line["rate"] = rate
        line["charge"] = (Decimal(line["units"]) * rate).quantize(
            CENT, rounding=ROUND_HALF_EVEN
        )
        counters[key] = counter + line["units"]

    credit_base = {region: Decimal("0.00") for region in REGIONS}
    for line in accepted:
        line["in_base"] = accounts[line["account"]]["plan"] == "committed"
        if line["in_base"]:
            credit_base[line["region"]] += line["charge"]

    for line in accepted:
        pool = pools.get(line["region"], Decimal("0"))
        base = credit_base[line["region"]]
        if line["in_base"] and base != 0:
            line["credit"] = (pool * line["charge"] / base).quantize(
                CENT, rounding=ROUND_HALF_EVEN
            )
        else:
            line["credit"] = Decimal("0.00")
        line["net"] = line["charge"] - line["credit"]

    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "normalized.jsonl"), "w", encoding="utf-8") as handle:
        for line in accepted:
            handle.write(
                json.dumps(
                    {
                        "record_id": line["record_id"],
                        "region": line["region"],
                        "timestamp": iso(line["stamp"]),
                        "account_id": line["account"],
                        "segment": line["segment"],
                        "plan": line["plan"],
                        "product": line["code"],
                        "units": line["units"],
                        "tier": line["tier"],
                        "unit_rate": rate_str(line["rate"]),
                        "charge": money(line["charge"]),
                        "credit": money(line["credit"]),
                        "net": money(line["net"]),
                    }
                )
                + "\n"
            )

    def write(name, document):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)
            handle.write("\n")

    total_charge = sum((line["charge"] for line in accepted), Decimal("0.00"))
    total_credit = sum((line["credit"] for line in accepted), Decimal("0.00"))
    total_units = zero_units(codes)
    for line in accepted:
        total_units[line["code"]] += line["units"]

    write(
        "summary.json",
        {
            "month": month,
            "lines": len(accepted),
            "accounts_billed": len({line["account"] for line in accepted}),
            "units": total_units,
            "charge": money(total_charge),
            "credit": money(total_credit),
            "net": money(total_charge - total_credit),
        },
    )

    products_doc = {}
    for code in codes:
        lines = [line for line in accepted if line["code"] == code]
        charge = sum((line["charge"] for line in lines), Decimal("0.00"))
        credit = sum((line["credit"] for line in lines), Decimal("0.00"))
        products_doc[code] = {
            "unit": product_units[code],
            "lines": len(lines),
            "units": sum(line["units"] for line in lines),
            "charge": money(charge),
            "credit": money(credit),
            "net": money(charge - credit),
        }
    write("product_summary.json", {"month": month, "products": products_doc})

    for region in REGIONS:
        lines = [line for line in accepted if line["region"] == region]
        charge = sum((line["charge"] for line in lines), Decimal("0.00"))
        credit = sum((line["credit"] for line in lines), Decimal("0.00"))
        units = zero_units(codes)
        for line in lines:
            units[line["code"]] += line["units"]
        pool = pools.get(region, Decimal("0"))
        write(
            f"region_{region}.json",
            {
                "region": region,
                "month": month,
                "lines": len(lines),
                "accounts": len({line["account"] for line in lines}),
                "units": units,
                "charge": money(charge),
                "credit_pool": money(pool),
                "credit_base": money(credit_base[region]),
                "credit_applied": money(credit),
                "credit_unallocated": money(pool - credit),
                "net": money(charge - credit),
            },
        )

    for segment in segments:
        lines = [line for line in accepted if line["segment"] == segment]
        charge = sum((line["charge"] for line in lines), Decimal("0.00"))
        credit = sum((line["credit"] for line in lines), Decimal("0.00"))
        by_product = {}
        for code in codes:
            subset = [line for line in lines if line["code"] == code]
            by_product[code] = {
                "lines": len(subset),
                "units": sum(line["units"] for line in subset),
                "charge": money(sum((line["charge"] for line in subset), Decimal("0.00"))),
            }
        write(
            f"segment_{segment}.json",
            {
                "segment": segment,
                "month": month,
                "lines": len(lines),
                "accounts": len({line["account"] for line in lines}),
                "by_product": by_product,
                "charge": money(charge),
                "credit": money(credit),
                "net": money(charge - credit),
            },
        )

    write(
        "data_quality.json",
        {
            "month": month,
            "collectors": {
                region: {
                    "file": control_info.get(region, {}).get("file", filename),
                    "records": stats[region]["records"],
                    "duplicates": stats[region]["duplicates"],
                    "quarantined": stats[region]["quarantined"],
                    "accepted": stats[region]["accepted"],
                }
                for region, filename in COLLECTOR_FILES
            },
            "quarantine_reasons": reason_counts,
            "quarantined_records": sorted(
                quarantined, key=lambda item: (item["collector"], item["record_id"])
            ),
            "plan_changes": {
                "lines": change_lines,
                "applied": change_applied,
                "unmatched": change_unmatched,
            },
        },
    )


if __name__ == "__main__":
    main()
