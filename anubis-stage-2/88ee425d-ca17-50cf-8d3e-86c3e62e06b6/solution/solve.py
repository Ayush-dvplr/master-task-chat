#!/usr/bin/env python3
"""Reference oracle, derived from /app/data/schema.md alone.

Installs /app/out/transform.py (the reusable clearing pipeline the instruction
asks for), runs it once over the shipped book, and prints the nine closing
report figures the contract defines.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

TRANSFORM = r'''#!/usr/bin/env python3
"""Clear one TY31 dispensing book into the canonical artifacts (see schema.md).

Usage: transform.py [INPUT_DIR] [OUTPUT_DIR]. The INPUT_DIR / OUTPUT_DIR
environment variables, then /app/data and /app/out, are the fallbacks.
"""
import bisect
import configparser
import csv
import json
import os
import sys
from itertools import groupby
from operator import itemgetter
from datetime import datetime, timedelta
from decimal import ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path

HEAD_REGIONS = ("central", "east", "north", "south", "west")
BOOK_SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
FEEDS = ("dispenses.csv", "recoveries.tsv", "assessments.jsonl", "archive.txt")
ARCHIVE_COLUMNS = (
    "claim_id", "booked_ts", "member_id", "item_code", "depot",
    "kind", "quantity", "amount", "currency", "gateway", "memo",
)
SLICE_FIELDS = ("region", "segment", "kind", "category",
                "lane", "tariff_period", "source")
ARCHIVE_SIGNS = {"dispense": 1, "levy": 1, "recovery": -1, "rebate": -1}
UNIT_SIGNS = {"dispense": 1, "recovery": -1}
ROUNDERS = {"half_up": ROUND_HALF_UP, "half_even": ROUND_HALF_EVEN,
            "half_down": ROUND_HALF_DOWN}
OWN_COLUMNS = {
    "dispenses.csv": {"booked_ts", "member_id", "item_code", "depot", "quantity",
                      "unit_price", "currency", "gateway"},
    "recoveries.tsv": {"booked_ts", "member_id", "item_code", "depot", "quantity",
                       "recovered_amount", "currency", "gateway", "dispense_claim_id"},
    "assessments.jsonl": {"booked_ts", "member_id", "item_code", "kind", "amount_minor",
                          "currency", "note"},
    "archive.txt": {"booked_ts", "member_id", "item_code", "depot", "kind", "quantity",
                    "amount", "currency", "gateway", "memo"},
}
HALF_CENT = Decimal("0.5")


class Refused(Exception):
    pass


UNCLEARABLE = (Refused, ArithmeticError, ValueError, TypeError, AttributeError, KeyError)


def tidy(value):
    return "" if value is None else str(value).strip()


def label(value):
    return tidy(value).lower()


def sheet(folder, name, sep=","):
    with open(folder / name, encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter=sep)]


def counted(value):
    text = tidy(value)
    if not text or not text.isascii() or not text.isdigit():
        raise Refused("quantity needs ascii digits")
    return int(text)


def instant_of(value):
    text = tidy(value)
    if text.endswith("Z"):
        text = text[:-1]
    stamp, _, clock = text.partition("T")
    try:
        year, month, day = (int(part) for part in stamp.split("-"))
        hour, minute, second = (int(part) for part in clock.split(":"))
        return datetime(year, month, day, hour, minute, second)
    except (TypeError, ValueError) as exc:
        raise Refused("booked_ts is not a real instant") from exc


class Registry:
    """Every reference table the clearing chain walks."""

    def __init__(self, folder):
        contract = configparser.ConfigParser()
        contract.read_string((folder / "policy.ini").read_text(encoding="utf-8"))
        self.floors = {key.split("_")[1]: int(value)
                       for key, value in contract["reserve"].items()}
        self.opening_day = tidy(contract["ladder"]["opening_rate_date"])
        self.rounding = ROUNDERS[label(contract["rounding"]["mode"])]
        self.per_kilo = Decimal(tidy(contract["mass"]["grams_per_kilogram"]))
        self.no_period = tidy(contract["labels"]["unassigned_period"])
        self.assess_lane = label(contract["labels"]["assessment_lane"])

        self.member = {}
        ranked = {}
        for position, row in enumerate(sheet(folder, "members.csv")):
            who = tidy(row["member_id"])
            rank = (tidy(row["updated_at"]), position)
            if who in ranked and ranked[who] > rank:
                continue
            ranked[who] = rank
            self.member[who] = {
                "segment": label(row["segment"]),
                "postal": tidy(row["postal_code"]),
                "minor": tidy(row["opening_reserve_minor"]),
                "money": tidy(row["opening_currency"]).upper(),
            }

        self.prefix = {}
        self.above = {}
        for row in sheet(folder, "zones.csv"):
            name = label(row["zone"])
            self.prefix[tidy(row["postal_prefix"])] = (name,
                                                       tidy(row["default_currency"]).upper())
            self.above[name] = label(row["parent_zone"])

        self.kind_of = {}
        self.mass_of = {}
        for row in sheet(folder, "item_catalog.csv"):
            code = tidy(row["item_code"])
            self.kind_of[code] = label(row["category"])
            self.mass_of[code] = Decimal(tidy(row["pack_mass_kg"]))

        self.lane = {label(row["gateway"]): label(row["lane"])
                     for row in sheet(folder, "gateways.csv")}

        self.postal_of = {}
        self.shift_of = {}
        self.stock = {}
        self.loose_grams = 0
        for row in sheet(folder, "stock_ledger.csv"):
            depot = tidy(row["depot"])
            self.postal_of[depot] = tidy(row["postal_code"])
            self.shift_of[depot] = int(tidy(row["tz_offset_minutes"]))
            code = tidy(row["item_code"])
            held, trigger = self.stock.get(code, (0, 0))
            self.stock[code] = (held + int(tidy(row["on_hand_grams"])),
                                trigger + int(tidy(row["reorder_point_grams"])))

        self.quote = {}
        self.quote_days = {}
        for row in sheet(folder, "fx_rates.csv"):
            day = tidy(row["rate_date"])
            money = tidy(row["currency"]).upper()
            self.quote[(day, money)] = Decimal(tidy(row["usd_rate"]))
            self.quote_days.setdefault(money, []).append(day)
        for money in self.quote_days:
            self.quote_days[money].sort()

        almanac = json.loads((folder / "tariff_calendar.json").read_text(encoding="utf-8"))
        self.spans = sorted((tidy(p["start"]), tidy(p["end"]), tidy(p["period"]))
                            for p in almanac["periods"])

        for code, (grams, _trigger) in self.stock.items():
            if code not in self.kind_of:
                self.loose_grams += grams

    def head_zone(self, name):
        walked = set()
        while self.above.get(name) and name not in walked:
            walked.add(name)
            name = self.above[name]
        return name

    def rate(self, day, money):
        direct = self.quote.get((day, money))
        if direct is not None:
            return direct, False
        days = self.quote_days.get(money, ())
        spot = bisect.bisect_left(days, day)
        if spot == 0:
            raise Refused("no usable rate")
        return self.quote[(days[spot - 1], money)], True

    def span_of(self, day):
        for start, end, name in self.spans:
            if start <= day <= end:
                return name
        return self.no_period

    def cents(self, gross, rate):
        product = gross * rate * 100
        return int(product.quantize(Decimal(1), rounding=self.rounding)), product

    def opening_cents(self, who):
        info = self.member[who]
        rate, _ = self.rate(self.opening_day, info["money"])
        amount, _ = self.cents(Decimal(info["minor"]) / 100, rate)
        return amount


def revisions(folder):
    """Winning amendment per (claim id, field), newest then latest in file."""
    chosen = {}
    for line_no, line in enumerate((folder / "amendments.log")
                                   .read_text(encoding="utf-8").splitlines()):
        pieces = line.split()
        if len(pieces) < 3 or pieces[2] != "amendment":
            continue
        tokens = dict(piece.partition("=")[::2] for piece in pieces[3:])
        if "target" not in tokens or "field" not in tokens:
            continue
        slot = (tokens["target"], tokens["field"])
        mark = (pieces[0], line_no)
        if slot not in chosen or mark > chosen[slot][0]:
            chosen[slot] = (mark, tokens.get("value", ""))
    return {slot: payload for slot, (_mark, payload) in chosen.items()}


def harvest(folder):
    """(source, raw mapping) for every candidate claim line, in file order."""
    found = []
    if (folder / "dispenses.csv").is_file():
        for row in sheet(folder, "dispenses.csv"):
            found.append(("dispenses.csv", row))
    if (folder / "recoveries.tsv").is_file():
        for row in sheet(folder, "recoveries.tsv", "\t"):
            found.append(("recoveries.tsv", row))
    if (folder / "assessments.jsonl").is_file():
        for line in (folder / "assessments.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                found.append(("assessments.jsonl", json.loads(line)))
            except ValueError:
                found.append(("assessments.jsonl", {}))
    if (folder / "archive.txt").is_file():
        for line in (folder / "archive.txt").read_text(encoding="latin-1").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = [piece.strip() for piece in line.split("|")]
            found.append(("archive.txt",
                          dict(zip(ARCHIVE_COLUMNS, parts)) if len(parts) == 11 else {}))
    return found


def gross_of(source, raw):
    if source == "dispenses.csv":
        units = counted(raw.get("quantity"))
        try:
            price = Decimal(tidy(raw.get("unit_price")))
        except ArithmeticError as exc:
            raise Refused("unit_price") from exc
        return "dispense", units, price * units
    if source == "recoveries.tsv":
        units = counted(raw.get("quantity"))
        try:
            size = Decimal(tidy(raw.get("recovered_amount")))
        except ArithmeticError as exc:
            raise Refused("recovered_amount") from exc
        return "recovery", units, -abs(size)
    if source == "assessments.jsonl":
        kind = label(raw.get("kind"))
        if kind not in ("levy", "rebate"):
            raise Refused("assessment kind")
        booked = raw.get("amount_minor")
        if isinstance(booked, bool) or not isinstance(booked, int):
            raise Refused("amount_minor")
        return kind, 0, Decimal(booked) / 100
    kind = label(raw.get("kind"))
    if kind not in ARCHIVE_SIGNS:
        raise Refused("archive kind")
    units = counted(raw.get("quantity"))
    try:
        size = Decimal(tidy(raw.get("amount")))
    except ArithmeticError as exc:
        raise Refused("amount") from exc
    return kind, units, abs(size) * ARCHIVE_SIGNS[kind]


def clear_claim(source, raw, shelf):
    who = tidy(raw.get("member_id"))
    code = tidy(raw.get("item_code"))
    if who not in shelf.member:
        raise Refused("member")
    if code not in shelf.kind_of:
        raise Refused("item_code")
    seat = shelf.member[who]
    if source == "assessments.jsonl":
        postal, depot, shift = seat["postal"], None, 0
        lane = shelf.assess_lane
    else:
        depot = tidy(raw.get("depot"))
        if depot not in shelf.postal_of:
            raise Refused("depot")
        postal, shift = shelf.postal_of[depot], shelf.shift_of[depot]
        gateway = label(raw.get("gateway"))
        if gateway not in shelf.lane:
            raise Refused("gateway")
        lane = shelf.lane[gateway]
    stem = postal.partition("-")[0].strip()
    if stem not in shelf.prefix:
        raise Refused("postal prefix")
    leaf, fallback = shelf.prefix[stem]
    money = tidy(raw.get("currency")).upper() or fallback
    local = instant_of(raw.get("booked_ts"))
    moment = local - timedelta(minutes=shift)
    day = moment.date().isoformat()
    rate, carried = shelf.rate(day, money)
    kind, units, gross = gross_of(source, raw)
    amount, product = shelf.cents(gross, rate)
    return {
        "claim_id": tidy(raw.get("claim_id")),
        "clearing_date": day,
        "utc_instant": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tariff_period": shelf.span_of(day),
        "member_id": who,
        "segment": seat["segment"],
        "region": shelf.head_zone(leaf),
        "item_code": code,
        "category": shelf.kind_of[code],
        "kind": kind,
        "quantity": units,
        "cleared_usd_cents": amount,
        "currency": money,
        "source": source,
        "lane": lane,
        "depot": depot,
    }, {
        "carried": carried,
        "shifted": moment.date() != local.date(),
        "halved": abs(product) % 1 == HALF_CENT,
    }


def units_of(row):
    return UNIT_SIGNS.get(row["kind"], 0) * row["quantity"]


def ladder_key(entry):
    """Ladder order: member first, then UTC instant, then claim id as text."""
    return entry["member_id"], entry["utc_instant"], entry["claim_id"]


def walk_ladder(entries, shelf):
    """Stream one verdict per claim, member by member, carrying the reserve.

    The gate is a feedback loop and not a predicate: what claim N+1 is judged
    against is the reserve standing after claim N, so no record can be decided
    on its own and the run cannot be filtered before it is folded. Sorting the
    whole stream by (member, instant, id) lays each member's run down in one
    contiguous block, so a single groupby walk clears the book without
    bucketing the records first. Every member's run is closed by a marker
    carrying the reserve it came to rest at.
    """
    for member, run in groupby(sorted(entries, key=ladder_key),
                               itemgetter("member_id")):
        standing = shelf.opening_cents(member)
        requirement = shelf.floors[shelf.member[member]["segment"]]
        for entry in run:
            swing = entry["cleared_usd_cents"]
            if swing < 0 and standing + swing < requirement:
                yield member, entry, False, standing
                continue
            standing = standing + swing
            yield member, entry, True, standing
        yield member, None, None, standing


def run_ladder(entries, shelf):
    """Drain the walk into cleared records, refused records and the closing total.

    A member the walk never reaches carries no claims at all, so it rests at
    its own opening reserve and still counts toward the closing total.
    """
    cleared, refused, rested = [], [], {}
    for member, entry, verdict, standing in walk_ladder(entries, shelf):
        rested[member] = standing
        if verdict is True:
            cleared.append(entry)
        elif verdict is False:
            refused.append(entry)
    closing_total = sum(rested[member] if member in rested
                        else shelf.opening_cents(member)
                        for member in shelf.member)
    return cleared, refused, closing_total


def money_map(rows, field):
    """Cleared cents summed per distinct value of one field, in key order."""
    tally = {}
    for row in rows:
        tally[row[field]] = tally.get(row[field], 0) + row["cleared_usd_cents"]
    return dict(sorted(tally.items()))


def bucket(cleared, refused, field, name, extra=None):
    """One region or segment slice, with its own blocked tally."""
    cohort = [row for row in cleared if row[field] == name]
    slice_doc = {field: name}
    slice_doc["event_count"] = len(cohort)
    slice_doc["total_usd_cents"] = sum(row["cleared_usd_cents"] for row in cohort)
    slice_doc["net_units"] = sum(units_of(row) for row in cohort)
    slice_doc["blocked_count"] = sum(1 for row in refused if row[field] == name)
    slice_doc["members"] = sorted({row["member_id"] for row in cohort})
    slice_doc["by_kind"] = money_map(cohort, "kind")
    slice_doc["by_category"] = money_map(cohort, "category")
    slice_doc.update(extra or {})
    return slice_doc


def document(path, doc):
    """Every .json artifact: sorted keys, two space indent, closing newline."""
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clear_book(folder, out_dir):
    shelf = Registry(folder)
    fixes = revisions(folder)
    rows = harvest(folder)
    present = [feed for feed in FEEDS if (folder / feed).is_file()]
    dispense_ids = {tidy(raw.get("claim_id")) for source, raw in rows
                    if source == "dispenses.csv"}
    known_ids = {tidy(raw.get("claim_id")) for _source, raw in rows
                 if tidy(raw.get("claim_id"))}
    nowhere = sorted({target for target, _field in fixes if target not in known_ids})

    resolved, dead_links = [], []
    skipped = {feed: 0 for feed in present}
    bad_dispenses, touched = set(), set()
    marks = {"carried": 0, "shifted": 0, "halved": 0, "stale_link": 0}
    for source, raw in rows:
        claim_id = tidy(raw.get("claim_id"))
        patched = dict(raw)
        for field in OWN_COLUMNS[source]:
            if (claim_id, field) in fixes:
                patched[field] = fixes[(claim_id, field)]
                touched.add(claim_id)
        if source == "recoveries.tsv":
            link = tidy(patched.get("dispense_claim_id"))
            if link and link not in dispense_ids:
                dead_links.append(claim_id)
                continue
        try:
            entry, flags = clear_claim(source, patched, shelf)
        except UNCLEARABLE:
            skipped[source] += 1
            if source == "dispenses.csv":
                bad_dispenses.add(claim_id)
            continue
        resolved.append(entry)
        entry["_link"] = tidy(patched.get("dispense_claim_id")) \
            if source == "recoveries.tsv" else ""
        entry["_flags"] = flags

    cleared, refused, closing_total = run_ladder(resolved, shelf)
    for entry in cleared:
        flags = entry.pop("_flags")
        link = entry.pop("_link")
        marks["carried"] += bool(flags["carried"])
        marks["shifted"] += bool(flags["shifted"])
        marks["halved"] += bool(flags["halved"])
        marks["stale_link"] += bool(link and link in bad_dispenses)
    for entry in refused:
        entry.pop("_flags", None)
        entry.pop("_link", None)

    cleared.sort(key=itemgetter("claim_id"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "normalized.jsonl").write_text(
        "".join(json.dumps(entry, separators=(",", ":"), sort_keys=True) + "\n"
                for entry in cleared), encoding="utf-8")

    book_roll = {}
    book_roll["event_count"] = len(cleared)
    book_roll["skipped_count"] = sum(skipped.values())
    book_roll["blocked_count"] = len(refused)
    book_roll["orphan_recovery_count"] = len(dead_links)
    book_roll["total_usd_cents"] = sum(row["cleared_usd_cents"] for row in cleared)
    book_roll["net_units"] = sum(units_of(row) for row in cleared)
    book_roll["reserve_closing_usd_cents"] = closing_total
    for field in SLICE_FIELDS:
        book_roll["by_" + field] = money_map(cleared, field)
    document(out_dir / "summary.json", book_roll)

    taken_per_feed = {}
    for entry in cleared:
        taken_per_feed[entry["source"]] = taken_per_feed.get(entry["source"], 0) + 1
    refused_per_feed = {feed: 0 for feed in present}
    for entry in refused:
        refused_per_feed[entry["source"]] += 1
    health = {}
    health["input_files"] = sorted(item.name for item in folder.iterdir() if item.is_file())
    health["records_by_source"] = dict(sorted(taken_per_feed.items()))
    health["skipped_by_source"] = dict(sorted(skipped.items()))
    health["blocked_by_source"] = dict(sorted(refused_per_feed.items()))
    health["skipped_count"] = book_roll["skipped_count"]
    health["blocked_count"] = len(refused)
    health["orphan_recovery_count"] = len(dead_links)
    health["blocked_claim_ids"] = sorted({row["claim_id"] for row in refused})
    health["orphan_recovery_claim_ids"] = sorted(set(dead_links))
    health["unmatched_amendment_targets"] = nowhere
    document(out_dir / "data_quality.json", health)

    by_item = {}
    for entry in cleared:
        by_item.setdefault(entry["item_code"], []).append(entry)
    catalogue = []
    for code in sorted(shelf.kind_of):
        cohort = by_item.get(code, [])
        held, trigger = shelf.stock.get(code, (0, 0))
        net_count = sum(units_of(row) for row in cohort)
        mass = Decimal(net_count) * shelf.mass_of[code] * shelf.per_kilo
        line = {"item_code": code, "category": shelf.kind_of[code]}
        line["event_count"] = len(cohort)
        line["total_usd_cents"] = sum(row["cleared_usd_cents"] for row in cohort)
        line["net_units"] = net_count
        line["on_hand_grams"] = held
        line["reorder_point_grams"] = trigger
        line["net_mass_grams"] = int(mass.quantize(Decimal(1), rounding=shelf.rounding))
        catalogue.append(line)
    document(out_dir / "product_summary.json", {"products": catalogue})

    for name in HEAD_REGIONS:
        document(out_dir / f"region_{name}.json",
                 bucket(cleared, refused, "region", name))
    for name in BOOK_SEGMENTS:
        document(out_dir / f"segment_{name}.json",
                 bucket(cleared, refused, "segment", name,
                        {"reserve_floor_usd_cents": shelf.floors[name]}))

    closing_report = {}
    closing_report["blocked_value_usd_cents"] = sum(row["cleared_usd_cents"]
                                                    for row in refused)
    closing_report["blocked_members"] = len({row["member_id"] for row in refused})
    closing_report["carry_forward_rate_events"] = marks["carried"]
    closing_report["day_shift_events"] = marks["shifted"]
    closing_report["amended_events"] = len(touched)
    closing_report["half_cent_events"] = marks["halved"]
    closing_report["underwater_members"] = sum(
        1 for who, info in shelf.member.items()
        if shelf.opening_cents(who) < shelf.floors[info["segment"]])
    closing_report["uncatalogued_stock_grams"] = shelf.loose_grams
    closing_report["stale_link_recoveries"] = marks["stale_link"]
    return closing_report


if __name__ == "__main__":
    argv = sys.argv[1:]
    source_dir = Path(argv[0] if argv else os.environ.get("INPUT_DIR", "/app/data"))
    target_dir = Path(argv[1] if len(argv) > 1 else os.environ.get("OUTPUT_DIR", "/app/out"))
    print(json.dumps(clear_book(source_dir, target_dir), indent=2, sort_keys=True))
'''


ARTIFACT_NAMES = (
    "normalized.jsonl", "summary.json", "data_quality.json", "product_summary.json",
    "region_central.json", "region_east.json", "region_north.json", "region_south.json",
    "region_west.json", "segment_consumer.json", "segment_corporate.json",
    "segment_enterprise.json", "segment_smb.json",
)


def main() -> None:
    root = Path(os.environ.get("APP_ROOT", "/app"))
    source_dir, target_dir = root / "data", root / "out"
    script_path = target_dir / "transform.py"
    target_dir.mkdir(parents=True, exist_ok=True)
    script_path.write_text(TRANSFORM, encoding="utf-8")
    script_path.chmod(0o755)
    sys.argv = [str(script_path), str(source_dir), str(target_dir)]

    print(f"Built the reusable clearing pipeline at {script_path} and cleared {source_dir}.")
    print("Artifacts written:")
    print(f"  {script_path}")
    for name in ARTIFACT_NAMES:
        print(f"  {target_dir / name}")
    print("Closing report figures:")
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    main()
