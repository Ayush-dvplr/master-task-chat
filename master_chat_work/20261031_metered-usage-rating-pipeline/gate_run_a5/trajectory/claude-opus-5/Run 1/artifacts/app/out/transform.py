#!/usr/bin/env python3
"""Rate one billing month of metered usage, following the rating contract."""

import argparse
import configparser
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from bisect import bisect_right
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, getcontext

getcontext().prec = 60

CENT = Decimal("0.01")
RATE_Q = Decimal("0.0001")
ZERO = Decimal("0.00")
MIN_SHARE = Decimal("0.50")

COLLECTOR_FILES = [
    ("central", "collector_central.csv"),
    ("east", "collector_east.tsv"),
    ("north", "collector_north.jsonl"),
    ("south", "collector_south.txt"),
    ("west", "collector_west.log"),
]
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

DIGITS = re.compile(r"[0-9]+")


def canon_account(value):
    return value.strip().upper().replace("-", "")


def money(value):
    quantized = value.quantize(CENT, rounding=ROUND_HALF_EVEN)
    if quantized == 0:
        quantized = ZERO
    return f"{quantized:.2f}"


def rate_str(value):
    return f"{value.quantize(RATE_Q, rounding=ROUND_HALF_EVEN):.4f}"


def share(total, weight, basis):
    return (total * weight / basis).quantize(CENT, rounding=ROUND_HALF_EVEN)


class Line:
    __slots__ = (
        "record_id",
        "region",
        "timestamp",
        "account_id",
        "product",
        "units",
        "segment",
        "plan",
        "tier",
        "unit_rate",
        "charge",
        "credit",
        "true_up",
        "counted",
    )


# ---------------------------------------------------------------- input files


def read_text(path, encoding="utf-8"):
    with open(path, encoding=encoding) as handle:
        return handle.read()


def load_controls(path):
    controls = json.loads(read_text(path))
    month = controls["month"].strip()
    collectors = {}
    for region, info in controls["collectors"].items():
        collectors[region.strip()] = {
            "file": info["file"].strip(),
            "records": int(info["records"]),
        }
    return month, collectors


def load_products(path):
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read_string(read_text(path))
    codes = []
    units = {}
    names = {}
    for section in parser.sections():
        code = section.strip()
        codes.append(code)
        units[code] = parser[section]["unit"].strip()
        for key, value in parser[section].items():
            if key.strip() == "unit":
                continue
            names[(key.strip(), value.strip())] = code
    return codes, units, names


def load_rate_card(path):
    card = json.loads(read_text(path), parse_float=Decimal, parse_int=Decimal)
    products = {}
    segments = set()
    for code, body in card["products"].items():
        tiers = []
        for tier in body["tiers"]:
            rates = {segment.strip(): rate for segment, rate in tier["rates"].items()}
            segments.update(rates)
            tiers.append((Decimal(tier["from"]), int(tier["tier"]), rates))
        tiers.sort(key=lambda item: item[0])
        products[code.strip()] = tiers
    return products, segments


def load_commitments(path):
    root = ET.fromstring(read_text(path))
    pools = {}
    for pool in root.iter("pool"):
        pools[pool.get("region").strip()] = (
            Decimal(pool.get("amount").strip()),
            Decimal(pool.get("minimum").strip()),
        )
    return pools


def load_accounts(path):
    accounts = {}
    order = []
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            account_id = canon_account(row["account_id"])
            accounts[account_id] = {
                "segment": row["segment"].strip(),
                "plan": row["plan"].strip(),
                "parent": canon_account(row["parent"] or ""),
            }
            order.append(account_id)

    groups = {}
    for account_id in order:
        chain = []
        current = account_id
        while True:
            if current in groups:
                root = groups[current]
                break
            chain.append(current)
            parent = accounts[current]["parent"]
            if not parent or parent not in accounts or parent in chain:
                root = current
                break
            current = parent
        for member in chain:
            groups[member] = root
    return accounts, groups


def load_plan_changes(path, accounts):
    total = 0
    applied = 0
    unmatched = 0
    changes_by_account = {}
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            text = raw_line.strip()
            if not text:
                continue
            total += 1
            tokens = text.split()
            stamp = parse_iso_z(tokens[0])
            fields = {}
            for token in tokens[1:]:
                key, sep, value = token.partition("=")
                if sep:
                    fields[key.strip()] = value.strip()
            account_id = canon_account(fields.get("account", ""))
            if account_id not in accounts:
                unmatched += 1
                continue
            applied += 1
            changes_by_account.setdefault(account_id, []).append((stamp, fields))

    timelines = {}
    for account_id, changes in changes_by_account.items():
        changes.sort(key=lambda item: item[0])
        plan = accounts[account_id]["plan"]
        segment = accounts[account_id]["segment"]
        stamps = []
        states = []
        for stamp, fields in changes:
            plan = fields.get("plan", plan)
            segment = fields.get("segment", segment)
            if stamps and stamps[-1] == stamp:
                states[-1] = (plan, segment)
            else:
                stamps.append(stamp)
                states.append((plan, segment))
        timelines[account_id] = (stamps, states)
    return {"lines": total, "applied": applied, "unmatched": unmatched}, timelines


# ------------------------------------------------------------------ timestamps


def parse_iso_z(text):
    return datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def month_bounds(month):
    year, mon = (int(part) for part in month.split("-"))
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    end = datetime(year + mon // 12, mon % 12 + 1, 1, tzinfo=timezone.utc)
    return start, end


# ------------------------------------------------------------- collector reads


def digit_units(raw):
    return int(raw) if DIGITS.fullmatch(raw) else None


def read_central(path):
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if not row:
                continue
            record_id, stamp, account, product, units = (
                cell.strip() for cell in row[:5]
            )
            yield (
                record_id,
                datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                ),
                account,
                product,
                digit_units(units),
            )


def read_east(path):
    with open(path, encoding="utf-8") as handle:
        next(handle, None)
        for raw_line in handle:
            if not raw_line.strip():
                continue
            record_id, epoch, account, product, units = (
                cell.strip() for cell in raw_line.rstrip("\n").split("\t")[:5]
            )
            yield (
                record_id,
                datetime.fromtimestamp(int(epoch), timezone.utc),
                account,
                product,
                digit_units(units),
            )


def plain(value):
    if isinstance(value, tuple):
        return value[1]
    return value if isinstance(value, str) else json.dumps(value)


def read_north(path):
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            text = raw_line.strip()
            if not text:
                continue
            record = json.loads(
                text,
                parse_int=lambda digits: ("int", digits),
                parse_float=lambda digits: ("float", digits),
            )
            raw_units = record["units"]
            units = None
            if isinstance(raw_units, tuple) and raw_units[0] == "int":
                units = int(raw_units[1])
            yield (
                plain(record["id"]).strip(),
                parse_iso_z(plain(record["at"])),
                plain(record["acct"]).strip(),
                plain(record["sku"]).strip(),
                units,
            )


def read_south(path):
    with open(path, encoding="latin-1") as handle:
        for raw_line in handle:
            text = raw_line.rstrip("\r\n")
            if not text.strip():
                continue
            yield (
                text[0:10].strip(),
                datetime.strptime(text[10:24].strip(), "%Y%m%d%H%M%S").replace(
                    tzinfo=timezone.utc
                ),
                text[24:34].strip(),
                text[34:46].strip(),
                digit_units(text[46:52].strip()),
            )


def read_west(path):
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            text = raw_line.strip()
            if not text:
                continue
            tokens = text.split()
            fields = {}
            for token in tokens[1:]:
                key, sep, value = token.partition("=")
                if sep:
                    fields[key.strip()] = value.strip()
            yield (
                fields.get("rec", ""),
                datetime.fromisoformat(tokens[0]).astimezone(timezone.utc),
                fields.get("acct", ""),
                fields.get("product", ""),
                digit_units(fields.get("qty", "")),
            )


READERS = {
    "central": read_central,
    "east": read_east,
    "north": read_north,
    "south": read_south,
    "west": read_west,
}


# ------------------------------------------------------------------- pipeline


def state_at(timelines, accounts, account_id, stamp):
    entry = timelines.get(account_id)
    if entry is not None:
        stamps, states = entry
        index = bisect_right(stamps, stamp)
        if index:
            return states[index - 1]
    account = accounts[account_id]
    return account["plan"], account["segment"]


def allocate(total, charges, basis):
    """Share `total` over lines in proportion to charge, per the contract."""
    result = [ZERO] * len(charges)
    if basis <= 0:
        return result
    kept = [
        index
        for index, charge in enumerate(charges)
        if share(total, charge, basis) >= MIN_SHARE
    ]
    kept_basis = sum((charges[index] for index in kept), ZERO)
    if kept_basis <= 0:
        return result
    for index in kept:
        result[index] = share(total, charges[index], kept_basis)
    return result


def rate_lines(accepted, accounts, groups, timelines, rate_tiers):
    tier_counter = {}
    for line in accepted:
        line.plan, line.segment = state_at(
            timelines, accounts, line.account_id, line.timestamp
        )
        key = (groups[line.account_id], line.product)
        counter = tier_counter.get(key, 0)
        chosen = None
        for tier in rate_tiers[line.product]:
            if tier[0] <= counter:
                chosen = tier
            else:
                break
        line.tier = chosen[1]
        line.unit_rate = chosen[2][line.segment]
        line.charge = (Decimal(line.units) * line.unit_rate).quantize(
            CENT, rounding=ROUND_HALF_EVEN
        )
        line.credit = ZERO
        line.true_up = ZERO
        line.counted = accounts[line.account_id]["plan"] == "committed"
        tier_counter[key] = counter + line.units


def apply_commitments(accepted, regions, pools):
    region_credit = {}
    for region in regions:
        pool, minimum = pools[region]
        counted = [line for line in accepted if line.region == region and line.counted]
        charges = [line.charge for line in counted]
        base = sum(charges, ZERO)
        if base <= pool:
            for line in counted:
                line.credit = line.charge
        else:
            for line, credit in zip(counted, allocate(pool, charges, base)):
                line.credit = credit
        if base < minimum:
            for line, true_up in zip(
                counted, allocate(minimum - base, charges, base)
            ):
                line.true_up = true_up
        region_credit[region] = (pool, minimum, base)
    return region_credit


def run(input_dir, output_dir):
    for name in INPUT_FILES:
        if not os.path.isfile(os.path.join(input_dir, name)):
            sys.stderr.write(f"missing input: {name}\n")
            return 1

    def path(name):
        return os.path.join(input_dir, name)

    month, controls = load_controls(path("collector_controls.json"))
    start, end = month_bounds(month)
    codes, product_units, product_names = load_products(path("products.ini"))
    rate_tiers, rate_segments = load_rate_card(path("rate_card.json"))
    pools = load_commitments(path("commitments.xml"))
    accounts, groups = load_accounts(path("accounts.csv"))
    plan_change_stats, timelines = load_plan_changes(path("plan_changes.log"), accounts)

    regions = sorted(controls)
    segments = sorted(rate_segments | {info["segment"] for info in accounts.values()})
    region_files = dict(COLLECTOR_FILES)

    collector_stats = {}
    quarantined_records = []
    reason_counts = {reason: 0 for reason in REASONS}
    accepted = []

    for region in regions:
        seen = set()
        duplicates = 0
        quarantined = 0
        taken = 0
        records = 0
        for record_id, stamp, account, product, units in READERS[region](
            path(region_files[region])
        ):
            records += 1
            if record_id in seen:
                duplicates += 1
                continue
            seen.add(record_id)
            account_id = canon_account(account)
            if not start <= stamp < end:
                reason = "timestamp_outside_month"
            elif account_id not in accounts:
                reason = "unknown_account"
            elif (region, product) not in product_names:
                reason = "unknown_product"
            elif units is None:
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
            taken += 1
            line = Line()
            line.record_id = record_id
            line.region = region
            line.timestamp = stamp
            line.account_id = account_id
            line.product = product_names[(region, product)]
            line.units = units
            accepted.append(line)

        control = controls[region]
        if records != control["records"]:
            sys.stderr.write(f"control mismatch: {control['file']}\n")
            return 1
        collector_stats[region] = {
            "file": control["file"],
            "records": records,
            "duplicates": duplicates,
            "quarantined": quarantined,
            "accepted": taken,
        }

    accepted.sort(key=lambda line: (line.timestamp, line.record_id))
    rate_lines(accepted, accounts, groups, timelines, rate_tiers)
    region_credit = apply_commitments(accepted, regions, pools)

    write_outputs(
        output_dir,
        month,
        regions,
        segments,
        codes,
        product_units,
        accepted,
        collector_stats,
        reason_counts,
        quarantined_records,
        plan_change_stats,
        region_credit,
    )
    return 0


# -------------------------------------------------------------------- outputs


def dump(output_dir, name, payload):
    with open(os.path.join(output_dir, name), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def totals(lines):
    charge = sum((line.charge for line in lines), ZERO)
    credit = sum((line.credit for line in lines), ZERO)
    true_up = sum((line.true_up for line in lines), ZERO)
    return charge, credit, true_up


def units_per_product(lines, codes):
    units = {code: 0 for code in codes}
    for line in lines:
        units[line.product] += line.units
    return units


def write_outputs(
    output_dir,
    month,
    regions,
    segments,
    codes,
    product_units,
    accepted,
    collector_stats,
    reason_counts,
    quarantined_records,
    plan_change_stats,
    region_credit,
):
    os.makedirs(output_dir, exist_ok=True)

    with open(
        os.path.join(output_dir, "normalized.jsonl"), "w", encoding="utf-8"
    ) as handle:
        for line in accepted:
            handle.write(
                json.dumps(
                    {
                        "record_id": line.record_id,
                        "region": line.region,
                        "timestamp": line.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "account_id": line.account_id,
                        "segment": line.segment,
                        "plan": line.plan,
                        "product": line.product,
                        "units": line.units,
                        "tier": line.tier,
                        "unit_rate": rate_str(line.unit_rate),
                        "charge": money(line.charge),
                        "credit": money(line.credit),
                        "true_up": money(line.true_up),
                        "net": money(line.charge - line.credit + line.true_up),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    charge, credit, true_up = totals(accepted)
    dump(
        output_dir,
        "summary.json",
        {
            "month": month,
            "lines": len(accepted),
            "accounts_billed": len({line.account_id for line in accepted}),
            "units": units_per_product(accepted, codes),
            "charge": money(charge),
            "credit": money(credit),
            "true_up": money(true_up),
            "net": money(charge - credit + true_up),
        },
    )

    products = {}
    for code in codes:
        lines = [line for line in accepted if line.product == code]
        charge, credit, true_up = totals(lines)
        products[code] = {
            "unit": product_units[code],
            "lines": len(lines),
            "units": sum(line.units for line in lines),
            "charge": money(charge),
            "credit": money(credit),
            "true_up": money(true_up),
            "net": money(charge - credit + true_up),
        }
    dump(output_dir, "product_summary.json", {"month": month, "products": products})

    for region in regions:
        pool, minimum, base = region_credit[region]
        lines = [line for line in accepted if line.region == region]
        charge, credit, true_up = totals(lines)
        dump(
            output_dir,
            f"region_{region}.json",
            {
                "region": region,
                "month": month,
                "lines": len(lines),
                "accounts": len({line.account_id for line in lines}),
                "units": units_per_product(lines, codes),
                "charge": money(charge),
                "credit_pool": money(pool),
                "credit_base": money(base),
                "credit_applied": money(credit),
                "credit_unallocated": money(pool - credit),
                "minimum": money(minimum),
                "true_up": money(true_up),
                "net": money(charge - credit + true_up),
            },
        )

    for segment in segments:
        lines = [line for line in accepted if line.segment == segment]
        charge, credit, true_up = totals(lines)
        by_product = {}
        for code in codes:
            subset = [line for line in lines if line.product == code]
            by_product[code] = {
                "lines": len(subset),
                "units": sum(line.units for line in subset),
                "charge": money(sum((line.charge for line in subset), ZERO)),
            }
        dump(
            output_dir,
            f"segment_{segment}.json",
            {
                "segment": segment,
                "month": month,
                "lines": len(lines),
                "accounts": len({line.account_id for line in lines}),
                "by_product": by_product,
                "charge": money(charge),
                "credit": money(credit),
                "true_up": money(true_up),
                "net": money(charge - credit + true_up),
            },
        )

    dump(
        output_dir,
        "data_quality.json",
        {
            "month": month,
            "collectors": {region: collector_stats[region] for region in regions},
            "quarantine_reasons": {reason: reason_counts[reason] for reason in REASONS},
            "quarantined_records": sorted(
                quarantined_records,
                key=lambda item: (item["collector"], item["record_id"]),
            ),
            "plan_changes": plan_change_stats,
        },
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rate a month of metered usage.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    return run(args.input, args.output)


if __name__ == "__main__":
    sys.exit(main())
