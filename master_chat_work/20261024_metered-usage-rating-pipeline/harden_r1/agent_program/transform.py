#!/usr/bin/env python3
"""Rate one billing month of metered usage per /app/data/rating_contract.md."""

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
from fractions import Fraction

COLLECTOR_FILES = [
    ("central", "collector_central.csv", "utf-8"),
    ("east", "collector_east.tsv", "utf-8"),
    ("north", "collector_north.jsonl", "utf-8"),
    ("south", "collector_south.txt", "latin-1"),
    ("west", "collector_west.log", "utf-8"),
]

REFERENCE_FILES = [
    "accounts.csv",
    "plan_changes.log",
    "rate_card.json",
    "commitments.xml",
    "products.ini",
    "collector_controls.json",
]

INPUT_FILES = [name for _, name, _ in COLLECTOR_FILES] + REFERENCE_FILES

REASONS = [
    "timestamp_outside_month",
    "unknown_account",
    "unknown_product",
    "units_not_integer",
]

DIGITS = re.compile(r"[0-9]+")
CENT = Decimal("0.01")


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def canonical_account(value):
    return str(value).strip().upper().replace("-", "")


def read_text(path, encoding):
    with open(path, "r", encoding=encoding, newline="") as handle:
        return handle.read()


def physical_lines(text):
    """Split on newlines only: str.splitlines() would also break Latin-1 data
    lines on bytes such as 0x85 that decode to Unicode line separators."""
    lines = [line.rstrip("\r") for line in text.split("\n")]
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def data_lines(text):
    return [line for line in physical_lines(text) if line.strip()]


def money(value):
    quantized = Decimal(value).quantize(CENT, rounding=ROUND_HALF_EVEN)
    if quantized == 0:
        quantized = Decimal("0.00")
    return f"{quantized:.2f}"


def rate_text(value):
    return f"{Decimal(value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_EVEN):.4f}"


def round_cents_exact(fraction):
    """Round an exact rational amount of money to cents, ties to even."""
    cents = fraction * 100
    floor = cents.numerator // cents.denominator
    remainder = cents - floor
    if remainder > Fraction(1, 2):
        floor += 1
    elif remainder == Fraction(1, 2) and floor % 2 != 0:
        floor += 1
    return (Decimal(floor) / Decimal(100)).quantize(CENT)


def parse_units_text(raw):
    text = raw.strip()
    return int(text) if DIGITS.fullmatch(text) else None


def month_bounds(month):
    year, mon = (int(part) for part in month.split("-"))
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    end = datetime(year + (mon == 12), 1 if mon == 12 else mon + 1, 1, tzinfo=timezone.utc)
    return start, end


def parse_iso(text):
    value = text.strip()
    if value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# ---------------------------------------------------------------- collectors


def read_central(text):
    rows = list(csv.reader(physical_lines(text)))
    records = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        record_id, timestamp, account, product, units = (cell.strip() for cell in row[:5])
        records.append(
            {
                "record_id": record_id,
                "timestamp": datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                ),
                "account": account,
                "product": product,
                "units": parse_units_text(units),
            }
        )
    return records


def read_east(text):
    rows = list(csv.reader(physical_lines(text), delimiter="\t"))
    records = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        record_id, epoch, account, product, units = (cell.strip() for cell in row[:5])
        records.append(
            {
                "record_id": record_id,
                "timestamp": datetime.fromtimestamp(int(epoch), timezone.utc),
                "account": account,
                "product": product,
                "units": parse_units_text(units),
            }
        )
    return records


def read_north(text):
    records = []
    for line in data_lines(text):
        obj = json.loads(line)
        raw_units = obj.get("units")
        units = raw_units if isinstance(raw_units, int) and not isinstance(raw_units, bool) else None
        records.append(
            {
                "record_id": str(obj.get("id", "")).strip(),
                "timestamp": parse_iso(str(obj.get("at"))),
                "account": str(obj.get("acct", "")).strip(),
                "product": str(obj.get("sku", "")).strip(),
                "units": units,
            }
        )
    return records


def read_south(text):
    records = []
    for line in data_lines(text):
        padded = line.ljust(72)
        records.append(
            {
                "record_id": padded[0:10].strip(),
                "timestamp": datetime.strptime(padded[10:24].strip(), "%Y%m%d%H%M%S").replace(
                    tzinfo=timezone.utc
                ),
                "account": padded[24:34].strip(),
                "product": padded[34:46].strip(),
                "units": parse_units_text(padded[46:52]),
            }
        )
    return records


def read_west(text):
    records = []
    for line in data_lines(text):
        parts = line.split()
        fields = {}
        for token in parts[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key.strip()] = value.strip()
        records.append(
            {
                "record_id": fields.get("rec", "").strip(),
                "timestamp": parse_iso(parts[0]),
                "account": fields.get("acct", "").strip(),
                "product": fields.get("product", "").strip(),
                "units": parse_units_text(fields.get("qty", "")),
            }
        )
    return records


READERS = {
    "central": read_central,
    "east": read_east,
    "north": read_north,
    "south": read_south,
    "west": read_west,
}


# ---------------------------------------------------------------- reference


def read_accounts(text):
    accounts = {}
    rows = list(csv.reader(physical_lines(text)))
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        account_id, segment, plan = (cell.strip() for cell in row[:3])
        accounts[canonical_account(account_id)] = {"segment": segment, "plan": plan}
    return accounts


def read_plan_changes(text, accounts):
    lines = data_lines(text)
    changes = {}
    applied = 0
    for index, line in enumerate(lines):
        tokens = line.split()
        timestamp = parse_iso(tokens[0])
        fields = {}
        for token in tokens[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key.strip()] = value.strip()
        account = canonical_account(fields.get("account", ""))
        if account not in accounts:
            continue
        applied += 1
        update = {key: fields[key] for key in ("plan", "segment") if key in fields}
        changes.setdefault(account, []).append((timestamp, index, update))
    timelines = {}
    for account, entries in changes.items():
        entries.sort(key=lambda item: (item[0], item[1]))
        times = []
        states = []
        state = dict(accounts[account])
        for timestamp, _index, update in entries:
            state = dict(state)
            state.update(update)
            times.append(timestamp)
            states.append(state)
        timelines[account] = (times, states)
    return len(lines), applied, len(lines) - applied, timelines


def read_products(text):
    parser = configparser.RawConfigParser()
    parser.read_string(text)
    units = {}
    names = {region: {} for region, _, _ in COLLECTOR_FILES}
    codes = []
    for code in parser.sections():
        product = code.strip()
        codes.append(product)
        units[product] = parser.get(code, "unit").strip()
        for region in names:
            if parser.has_option(code, region):
                names[region][parser.get(code, region).strip()] = product
    return codes, units, names


def read_rate_card(text):
    card = json.loads(text, parse_float=Decimal)
    tiers = {}
    segments = set()
    for code, body in card["products"].items():
        rows = sorted(body["tiers"], key=lambda tier: Decimal(str(tier["from"])))
        tiers[code.strip()] = [
            (Decimal(str(row["from"])), int(row["tier"]),
             {segment: Decimal(str(rate)) for segment, rate in row["rates"].items()})
            for row in rows
        ]
        for row in rows:
            segments.update(row["rates"])
    return tiers, sorted(segments)


def read_commitments(text):
    root = ET.fromstring(text)
    return {
        pool.get("region").strip(): Decimal(pool.get("amount").strip())
        for pool in root.iter("pool")
    }


# ---------------------------------------------------------------- pipeline


def state_at(timelines, accounts, account, timestamp):
    timeline = timelines.get(account)
    if timeline is None:
        return accounts[account]
    times, states = timeline
    index = bisect.bisect_right(times, timestamp)
    return states[index - 1] if index else accounts[account]


def tier_for(tiers, cumulative_units):
    chosen = tiers[0]
    for tier in tiers:
        if tier[0] <= cumulative_units:
            chosen = tier
        else:
            break
    return chosen[1], chosen[2]


def zero_units(codes):
    return {code: 0 for code in codes}


def run(input_dir, output_dir):
    for name in INPUT_FILES:
        if not os.path.isfile(os.path.join(input_dir, name)):
            fail(f"missing input: {name}")

    controls = json.loads(read_text(os.path.join(input_dir, "collector_controls.json"), "utf-8"))
    month = controls["month"].strip()
    month_start, month_end = month_bounds(month)

    accounts = read_accounts(read_text(os.path.join(input_dir, "accounts.csv"), "utf-8"))
    change_lines, change_applied, change_unmatched, timelines = read_plan_changes(
        read_text(os.path.join(input_dir, "plan_changes.log"), "utf-8"), accounts
    )
    codes, product_units, product_names = read_products(
        read_text(os.path.join(input_dir, "products.ini"), "utf-8")
    )
    tiers, segments = read_rate_card(read_text(os.path.join(input_dir, "rate_card.json"), "utf-8"))
    pools = read_commitments(read_text(os.path.join(input_dir, "commitments.xml"), "utf-8"))

    regions = [region for region, _, _ in COLLECTOR_FILES if region in controls["collectors"]]

    accepted = []
    quality = {}
    quarantined_records = []
    reason_counts = {reason: 0 for reason in REASONS}

    for region, file_name, encoding in COLLECTOR_FILES:
        if region not in controls["collectors"]:
            continue
        control = controls["collectors"][region]
        records = READERS[region](read_text(os.path.join(input_dir, file_name), encoding))
        if len(records) != int(control["records"]):
            fail(f"control mismatch: {control['file']}")

        seen = set()
        duplicates = 0
        quarantined = 0
        accepted_count = 0
        for record in records:
            record_id = record["record_id"]
            if record_id in seen:
                duplicates += 1
                continue
            seen.add(record_id)

            account = canonical_account(record["account"])
            reason = None
            if not (month_start <= record["timestamp"] < month_end):
                reason = "timestamp_outside_month"
            elif account not in accounts:
                reason = "unknown_account"
            elif record["product"] not in product_names[region]:
                reason = "unknown_product"
            elif record["units"] is None:
                reason = "units_not_integer"

            if reason is not None:
                quarantined += 1
                reason_counts[reason] += 1
                quarantined_records.append(
                    {"collector": region, "record_id": record_id, "reason": reason}
                )
                continue

            accepted_count += 1
            accepted.append(
                {
                    "record_id": record_id,
                    "region": region,
                    "timestamp": record["timestamp"],
                    "account_id": account,
                    "product": product_names[region][record["product"]],
                    "units": record["units"],
                }
            )

        quality[region] = {
            "file": control["file"],
            "records": len(records),
            "duplicates": duplicates,
            "quarantined": quarantined,
            "accepted": accepted_count,
        }

    accepted.sort(key=lambda line: (line["timestamp"], line["record_id"]))

    cumulative = {}
    for line in accepted:
        state = state_at(timelines, accounts, line["account_id"], line["timestamp"])
        key = (line["account_id"], line["product"])
        prior = cumulative.get(key, 0)
        tier, rates = tier_for(tiers[line["product"]], Decimal(prior))
        rate = rates[state["segment"]]
        charge = (Decimal(line["units"]) * rate).quantize(CENT, rounding=ROUND_HALF_EVEN)
        cumulative[key] = prior + line["units"]
        line.update(
            {
                "segment": state["segment"],
                "plan": state["plan"],
                "tier": tier,
                "unit_rate": rate,
                "charge": charge,
            }
        )

    credit_base = {region: Decimal("0.00") for region in regions}
    for line in accepted:
        if line["plan"] == "committed":
            credit_base[line["region"]] += line["charge"]

    for line in accepted:
        base = credit_base[line["region"]]
        if line["plan"] == "committed" and base > 0:
            credit = round_cents_exact(
                Fraction(pools[line["region"]]) * Fraction(line["charge"]) / Fraction(base)
            )
        else:
            credit = Decimal("0.00")
        line["credit"] = credit
        line["net"] = line["charge"] - credit

    write_outputs(
        output_dir,
        month,
        accepted,
        codes,
        product_units,
        regions,
        segments,
        pools,
        credit_base,
        quality,
        quarantined_records,
        reason_counts,
        (change_lines, change_applied, change_unmatched),
    )


def write_outputs(
    output_dir,
    month,
    accepted,
    codes,
    product_units,
    regions,
    segments,
    pools,
    credit_base,
    quality,
    quarantined_records,
    reason_counts,
    plan_change_counts,
):
    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, "normalized.jsonl"), "w", encoding="utf-8") as handle:
        for line in accepted:
            handle.write(
                json.dumps(
                    {
                        "record_id": line["record_id"],
                        "region": line["region"],
                        "timestamp": line["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "account_id": line["account_id"],
                        "segment": line["segment"],
                        "plan": line["plan"],
                        "product": line["product"],
                        "units": line["units"],
                        "tier": line["tier"],
                        "unit_rate": rate_text(line["unit_rate"]),
                        "charge": money(line["charge"]),
                        "credit": money(line["credit"]),
                        "net": money(line["net"]),
                    }
                )
                + "\n"
            )

    total_units = zero_units(codes)
    total_charge = total_credit = total_net = Decimal("0.00")
    for line in accepted:
        total_units[line["product"]] += line["units"]
        total_charge += line["charge"]
        total_credit += line["credit"]
        total_net += line["net"]

    write_json(
        output_dir,
        "summary.json",
        {
            "month": month,
            "lines": len(accepted),
            "accounts_billed": len({line["account_id"] for line in accepted}),
            "units": total_units,
            "charge": money(total_charge),
            "credit": money(total_credit),
            "net": money(total_net),
        },
    )

    products = {
        code: {
            "unit": product_units[code],
            "lines": 0,
            "units": 0,
            "charge": Decimal("0.00"),
            "credit": Decimal("0.00"),
            "net": Decimal("0.00"),
        }
        for code in codes
    }
    for line in accepted:
        entry = products[line["product"]]
        entry["lines"] += 1
        entry["units"] += line["units"]
        entry["charge"] += line["charge"]
        entry["credit"] += line["credit"]
        entry["net"] += line["net"]
    write_json(
        output_dir,
        "product_summary.json",
        {
            "month": month,
            "products": {
                code: {
                    "unit": entry["unit"],
                    "lines": entry["lines"],
                    "units": entry["units"],
                    "charge": money(entry["charge"]),
                    "credit": money(entry["credit"]),
                    "net": money(entry["net"]),
                }
                for code, entry in products.items()
            },
        },
    )

    for region in regions:
        lines = [line for line in accepted if line["region"] == region]
        units = zero_units(codes)
        charge = credit_applied = net = Decimal("0.00")
        for line in lines:
            units[line["product"]] += line["units"]
            charge += line["charge"]
            credit_applied += line["credit"]
            net += line["net"]
        pool = pools[region]
        write_json(
            output_dir,
            f"region_{region}.json",
            {
                "region": region,
                "month": month,
                "lines": len(lines),
                "accounts": len({line["account_id"] for line in lines}),
                "units": units,
                "charge": money(charge),
                "credit_pool": money(pool),
                "credit_base": money(credit_base[region]),
                "credit_applied": money(credit_applied),
                "credit_unallocated": money(pool - credit_applied),
                "net": money(net),
            },
        )

    for segment in segments:
        lines = [line for line in accepted if line["segment"] == segment]
        by_product = {
            code: {"lines": 0, "units": 0, "charge": Decimal("0.00")} for code in codes
        }
        charge = credit = net = Decimal("0.00")
        for line in lines:
            entry = by_product[line["product"]]
            entry["lines"] += 1
            entry["units"] += line["units"]
            entry["charge"] += line["charge"]
            charge += line["charge"]
            credit += line["credit"]
            net += line["net"]
        write_json(
            output_dir,
            f"segment_{segment}.json",
            {
                "segment": segment,
                "month": month,
                "lines": len(lines),
                "accounts": len({line["account_id"] for line in lines}),
                "by_product": {
                    code: {
                        "lines": entry["lines"],
                        "units": entry["units"],
                        "charge": money(entry["charge"]),
                    }
                    for code, entry in by_product.items()
                },
                "charge": money(charge),
                "credit": money(credit),
                "net": money(net),
            },
        )

    change_lines, change_applied, change_unmatched = plan_change_counts
    write_json(
        output_dir,
        "data_quality.json",
        {
            "month": month,
            "collectors": quality,
            "quarantine_reasons": reason_counts,
            "quarantined_records": sorted(
                quarantined_records, key=lambda item: (item["collector"], item["record_id"])
            ),
            "plan_changes": {
                "lines": change_lines,
                "applied": change_applied,
                "unmatched": change_unmatched,
            },
        },
    )


def write_json(output_dir, name, document):
    with open(os.path.join(output_dir, name), "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Rate a month of metered usage.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.input, args.output)


if __name__ == "__main__":
    main()
