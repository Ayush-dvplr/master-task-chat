#!/usr/bin/env python3
"""Rate one billing month of metered usage per the rating contract."""

import argparse
import bisect
import configparser
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction

REGIONS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "corporate", "enterprise", "smb"]
REGION_FILES = {
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
REASONS = [
    "timestamp_outside_month",
    "unknown_account",
    "unknown_product",
    "units_not_integer",
]
CENT = Decimal("0.01")


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def canonical_account(value):
    return value.strip().upper().replace("-", "")


def money(value):
    quantized = Decimal(value).quantize(CENT, rounding=ROUND_HALF_EVEN)
    if quantized == 0:
        quantized = quantized.copy_abs()
    return f"{quantized:.2f}"


def cents(value):
    return int((Decimal(value) * 100).to_integral_value())


def from_cents(value):
    return (Decimal(value) / 100).quantize(CENT, rounding=ROUND_HALF_EVEN)


def round_half_even(frac):
    """Round a non-negative Fraction to the nearest integer, ties to even."""
    floor = frac.numerator // frac.denominator
    remainder = frac - floor
    if remainder < Fraction(1, 2):
        return floor
    if remainder > Fraction(1, 2):
        return floor + 1
    return floor if floor % 2 == 0 else floor + 1


def iso_z(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def read_text(path, encoding="utf-8"):
    with open(path, "r", encoding=encoding) as handle:
        return handle.read()


def parse_stamp(value, fmt):
    return datetime.strptime(value, fmt)


def parse_digits(value):
    text = value.strip()
    return int(text) if text.isascii() and text.isdigit() else None


# ---------------------------------------------------------------- collectors


def parse_central(text):
    records = []
    for line in [row for row in text.splitlines() if row.strip()][1:]:
        parts = [part.strip() for part in line.split(",")]
        parts += [""] * (5 - len(parts))
        records.append(
            {
                "record_id": parts[0],
                "timestamp": parse_stamp(parts[1], "%Y-%m-%d %H:%M:%S"),
                "account": parts[2],
                "product": parts[3],
                "units": parse_digits(parts[4]),
            }
        )
    return records


def parse_east(text):
    records = []
    for line in [row for row in text.splitlines() if row.strip()][1:]:
        parts = [part.strip() for part in line.split("\t")]
        parts += [""] * (5 - len(parts))
        moment = datetime.fromtimestamp(int(parts[1]), tz=timezone.utc).replace(tzinfo=None)
        records.append(
            {
                "record_id": parts[0],
                "timestamp": moment,
                "account": parts[2],
                "product": parts[3],
                "units": parse_digits(parts[4]),
            }
        )
    return records


def parse_north(text):
    records = []
    for line in text.splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        raw_units = obj.get("units")
        is_integer = isinstance(raw_units, int) and not isinstance(raw_units, bool)
        records.append(
            {
                "record_id": str(obj.get("id", "")).strip(),
                "timestamp": parse_stamp(str(obj.get("at", "")).strip(), "%Y-%m-%dT%H:%M:%SZ"),
                "account": str(obj.get("acct", "")).strip(),
                "product": str(obj.get("sku", "")).strip(),
                "units": raw_units if is_integer else None,
            }
        )
    return records


def parse_south(text):
    records = []
    for line in text.splitlines():
        if not line.strip():
            continue
        records.append(
            {
                "record_id": line[0:10].strip(),
                "timestamp": parse_stamp(line[10:24].strip(), "%Y%m%d%H%M%S"),
                "account": line[24:34].strip(),
                "product": line[34:46].strip(),
                "units": parse_digits(line[46:52]),
            }
        )
    return records


def parse_west(text):
    records = []
    for line in text.splitlines():
        if not line.strip():
            continue
        tokens = line.strip().split()
        moment = datetime.fromisoformat(tokens[0]).astimezone(timezone.utc).replace(tzinfo=None)
        fields = {}
        for token in tokens[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key.strip()] = value.strip()
        records.append(
            {
                "record_id": fields.get("rec", ""),
                "timestamp": moment,
                "account": fields.get("acct", ""),
                "product": fields.get("product", ""),
                "units": parse_digits(fields.get("qty", "")),
            }
        )
    return records


PARSERS = {
    "central": parse_central,
    "east": parse_east,
    "north": parse_north,
    "south": parse_south,
    "west": parse_west,
}


# ----------------------------------------------------------------- reference


def load_accounts(text):
    accounts = {}
    for line in [row for row in text.splitlines() if row.strip()][1:]:
        parts = [part.strip() for part in line.split(",")]
        parts += [""] * (4 - len(parts))
        accounts[canonical_account(parts[0])] = {
            "segment": parts[1],
            "plan": parts[2],
            "parent": canonical_account(parts[3]) if parts[3] else "",
        }
    return accounts


def billing_groups(accounts):
    groups = {}
    for account_id in accounts:
        current = account_id
        seen = {current}
        while True:
            parent = accounts[current]["parent"]
            if not parent or parent not in accounts or parent in seen:
                break
            current = parent
            seen.add(current)
        groups[account_id] = current
    return groups


def load_plan_changes(text, accounts):
    total = 0
    applied = 0
    changes = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        total += 1
        tokens = line.split()
        fields = {}
        for token in tokens[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key.strip()] = value.strip()
        account_id = canonical_account(fields.get("account", ""))
        if account_id not in accounts:
            continue
        applied += 1
        moment = parse_stamp(tokens[0], "%Y-%m-%dT%H:%M:%SZ")
        changes.setdefault(account_id, []).append(
            (moment, total, fields.get("plan"), fields.get("segment"))
        )
    return total, applied, changes


def build_timelines(accounts, changes):
    timelines = {}
    for account_id, info in accounts.items():
        plan = info["plan"]
        segment = info["segment"]
        moments = []
        states = []
        for moment, _order, new_plan, new_segment in sorted(
            changes.get(account_id, []), key=lambda item: (item[0], item[1])
        ):
            if new_plan is not None:
                plan = new_plan
            if new_segment is not None:
                segment = new_segment
            moments.append(moment)
            states.append((plan, segment))
        timelines[account_id] = (moments, states, (info["plan"], info["segment"]))
    return timelines


def in_force(timelines, account_id, moment):
    moments, states, initial = timelines[account_id]
    index = bisect.bisect_right(moments, moment)
    return states[index - 1] if index else initial


def load_products(path):
    parser = configparser.ConfigParser()
    with open(path, "r", encoding="utf-8") as handle:
        parser.read_file(handle)
    codes = []
    units = {}
    names = {}
    for code in parser.sections():
        codes.append(code)
        units[code] = parser[code].get("unit", "").strip()
        for region in REGIONS:
            name = parser[code].get(region)
            if name is not None:
                names[(region, name.strip())] = code
    return codes, units, names


def load_rate_card(text):
    data = json.loads(text, parse_float=Decimal, parse_int=Decimal)
    tiers = {}
    for code, product in data["products"].items():
        rows = sorted(product["tiers"], key=lambda row: Decimal(row["from"]))
        tiers[code] = [
            (
                Decimal(row["from"]),
                int(Decimal(row["tier"])),
                {segment: Decimal(rate) for segment, rate in row["rates"].items()},
            )
            for row in rows
        ]
    return tiers


def pick_tier(tiers, counter):
    chosen = tiers[0]
    for row in tiers:
        if row[0] <= counter:
            chosen = row
        else:
            break
    return chosen


def load_commitments(text):
    pools = {}
    for pool in ET.fromstring(text).findall("pool"):
        pools[pool.get("region").strip()] = (
            Decimal(pool.get("amount").strip()),
            Decimal(pool.get("minimum").strip()),
        )
    return pools


# ------------------------------------------------------------------ sharing


def allocate(charges, total_cents, pool_cents):
    """Share pool_cents over charges in proportion, dropping shares under $0.50."""
    result = [0] * len(charges)
    if not charges or total_cents <= 0 or pool_cents <= 0:
        return result
    first = [round_half_even(Fraction(pool_cents * charge, total_cents)) for charge in charges]
    kept = [index for index, value in enumerate(first) if value >= 50]
    kept_total = sum(charges[index] for index in kept)
    if kept_total <= 0:
        return result
    for index in kept:
        result[index] = round_half_even(Fraction(pool_cents * charges[index], kept_total))
    return result


# --------------------------------------------------------------------- main


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    in_dir, out_dir = args.input, args.output

    for name in INPUT_FILES:
        if not os.path.isfile(os.path.join(in_dir, name)):
            fail(f"missing input: {name}")

    controls = json.loads(read_text(os.path.join(in_dir, "collector_controls.json")))
    month = controls["month"].strip()
    year, month_number = (int(part) for part in month.split("-"))
    month_start = datetime(year, month_number, 1)
    month_end = datetime(year + month_number // 12, month_number % 12 + 1, 1)

    accounts = load_accounts(read_text(os.path.join(in_dir, "accounts.csv")))
    groups = billing_groups(accounts)
    changes_total, changes_applied, changes = load_plan_changes(
        read_text(os.path.join(in_dir, "plan_changes.log")), accounts
    )
    timelines = build_timelines(accounts, changes)
    codes, product_units, product_names = load_products(os.path.join(in_dir, "products.ini"))
    rate_tiers = load_rate_card(read_text(os.path.join(in_dir, "rate_card.json")))
    pools = load_commitments(read_text(os.path.join(in_dir, "commitments.xml")))

    accepted = []
    quarantined_records = []
    reason_counts = {reason: 0 for reason in REASONS}
    collector_stats = {}

    for region in REGIONS:
        file_name = REGION_FILES[region]
        encoding = "latin-1" if region == "south" else "utf-8"
        records = PARSERS[region](read_text(os.path.join(in_dir, file_name), encoding))
        if len(records) != controls["collectors"][region]["records"]:
            fail(f"control mismatch: {file_name}")

        seen_ids = set()
        duplicates = 0
        quarantined = 0
        for record in records:
            record_id = record["record_id"]
            if record_id in seen_ids:
                duplicates += 1
                continue
            seen_ids.add(record_id)

            account_id = canonical_account(record["account"])
            if not month_start <= record["timestamp"] < month_end:
                reason = "timestamp_outside_month"
            elif account_id not in accounts:
                reason = "unknown_account"
            elif (region, record["product"]) not in product_names:
                reason = "unknown_product"
            elif record["units"] is None:
                reason = "units_not_integer"
            else:
                reason = None

            if reason is not None:
                quarantined += 1
                reason_counts[reason] += 1
                quarantined_records.append(
                    {"collector": region, "record_id": record_id, "reason": reason}
                )
                continue

            accepted.append(
                {
                    "record_id": record_id,
                    "region": region,
                    "timestamp": record["timestamp"],
                    "account_id": account_id,
                    "product": product_names[(region, record["product"])],
                    "units": record["units"],
                }
            )

        collector_stats[region] = {
            "file": file_name,
            "records": len(records),
            "duplicates": duplicates,
            "quarantined": quarantined,
            "accepted": len(records) - duplicates - quarantined,
        }

    accepted.sort(key=lambda line: (line["timestamp"], line["record_id"]))

    counters = {}
    for line in accepted:
        plan, segment = in_force(timelines, line["account_id"], line["timestamp"])
        key = (groups[line["account_id"]], line["product"])
        counter = counters.get(key, 0)
        _tier_from, tier_number, rates = pick_tier(rate_tiers[line["product"]], counter)
        rate = rates[segment]
        counters[key] = counter + line["units"]
        line["plan"] = plan
        line["segment"] = segment
        line["tier"] = tier_number
        line["unit_rate"] = f"{rate:.4f}"
        line["charge_cents"] = cents(
            (Decimal(line["units"]) * rate).quantize(CENT, rounding=ROUND_HALF_EVEN)
        )
        line["credit_cents"] = 0
        line["true_up_cents"] = 0

    region_totals = {}
    for region in REGIONS:
        pool, minimum = pools[region]
        pool_cents = cents(pool)
        minimum_cents = cents(minimum)
        counted = [
            line
            for line in accepted
            if line["region"] == region and accounts[line["account_id"]]["plan"] == "committed"
        ]
        charges = [line["charge_cents"] for line in counted]
        base_cents = sum(charges)

        credits = list(charges) if base_cents <= pool_cents else allocate(charges, base_cents, pool_cents)
        for line, value in zip(counted, credits):
            line["credit_cents"] = value

        if base_cents < minimum_cents:
            for line, value in zip(counted, allocate(charges, base_cents, minimum_cents - base_cents)):
                line["true_up_cents"] = value

        region_totals[region] = {
            "pool_cents": pool_cents,
            "minimum_cents": minimum_cents,
            "base_cents": base_cents,
        }

    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "normalized.jsonl"), "w", encoding="utf-8") as handle:
        for line in accepted:
            net = line["charge_cents"] - line["credit_cents"] + line["true_up_cents"]
            handle.write(
                json.dumps(
                    {
                        "record_id": line["record_id"],
                        "region": line["region"],
                        "timestamp": iso_z(line["timestamp"]),
                        "account_id": line["account_id"],
                        "segment": line["segment"],
                        "plan": line["plan"],
                        "product": line["product"],
                        "units": line["units"],
                        "tier": line["tier"],
                        "unit_rate": line["unit_rate"],
                        "charge": money(from_cents(line["charge_cents"])),
                        "credit": money(from_cents(line["credit_cents"])),
                        "true_up": money(from_cents(line["true_up_cents"])),
                        "net": money(from_cents(net)),
                    }
                )
                + "\n"
            )

    def totals(lines):
        charge = sum(line["charge_cents"] for line in lines)
        credit = sum(line["credit_cents"] for line in lines)
        true_up = sum(line["true_up_cents"] for line in lines)
        return {
            "charge": money(from_cents(charge)),
            "credit": money(from_cents(credit)),
            "true_up": money(from_cents(true_up)),
            "net": money(from_cents(charge - credit + true_up)),
        }

    def units_by_product(lines):
        result = {code: 0 for code in codes}
        for line in lines:
            result[line["product"]] += line["units"]
        return result

    def write_json(name, document):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)
            handle.write("\n")

    summary = {
        "month": month,
        "lines": len(accepted),
        "accounts_billed": len({line["account_id"] for line in accepted}),
        "units": units_by_product(accepted),
    }
    summary.update(totals(accepted))
    write_json("summary.json", summary)

    products = {}
    for code in codes:
        lines = [line for line in accepted if line["product"] == code]
        entry = {
            "unit": product_units[code],
            "lines": len(lines),
            "units": sum(line["units"] for line in lines),
        }
        entry.update(totals(lines))
        products[code] = entry
    write_json("product_summary.json", {"month": month, "products": products})

    for region in REGIONS:
        lines = [line for line in accepted if line["region"] == region]
        info = region_totals[region]
        applied = sum(line["credit_cents"] for line in lines)
        charge = sum(line["charge_cents"] for line in lines)
        true_up = sum(line["true_up_cents"] for line in lines)
        write_json(
            f"region_{region}.json",
            {
                "region": region,
                "month": month,
                "lines": len(lines),
                "accounts": len({line["account_id"] for line in lines}),
                "units": units_by_product(lines),
                "charge": money(from_cents(charge)),
                "credit_pool": money(from_cents(info["pool_cents"])),
                "credit_base": money(from_cents(info["base_cents"])),
                "credit_applied": money(from_cents(applied)),
                "credit_unallocated": money(from_cents(info["pool_cents"] - applied)),
                "minimum": money(from_cents(info["minimum_cents"])),
                "true_up": money(from_cents(true_up)),
                "net": money(from_cents(charge - applied + true_up)),
            },
        )

    for segment in SEGMENTS:
        lines = [line for line in accepted if line["segment"] == segment]
        by_product = {}
        for code in codes:
            product_lines = [line for line in lines if line["product"] == code]
            by_product[code] = {
                "lines": len(product_lines),
                "units": sum(line["units"] for line in product_lines),
                "charge": money(from_cents(sum(line["charge_cents"] for line in product_lines))),
            }
        document = {
            "segment": segment,
            "month": month,
            "lines": len(lines),
            "accounts": len({line["account_id"] for line in lines}),
            "by_product": by_product,
        }
        document.update(totals(lines))
        write_json(f"segment_{segment}.json", document)

    quarantined_records.sort(key=lambda item: (item["collector"], item["record_id"]))
    write_json(
        "data_quality.json",
        {
            "month": month,
            "collectors": collector_stats,
            "quarantine_reasons": reason_counts,
            "quarantined_records": quarantined_records,
            "plan_changes": {
                "lines": changes_total,
                "applied": changes_applied,
                "unmatched": changes_total - changes_applied,
            },
        },
    )


if __name__ == "__main__":
    main()
