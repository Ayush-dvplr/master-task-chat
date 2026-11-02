#!/usr/bin/env python3
"""Reference oracle, derived from /app/data/schema.md alone.

Installs /app/out/transform.py (the reusable settlement pipeline the
instruction asks for), runs it once over the shipped book, and prints the nine
closing report figures the contract defines.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

TRANSFORM = r'''#!/usr/bin/env python3
"""Settle one FY28 book into the canonical artifacts (see schema.md).

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

TOP_REGIONS = ("central", "east", "north", "south", "west")
BOOK_SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
FEEDS = ("sales.csv", "refunds.tsv", "adjustments.jsonl", "legacy.txt")
LEGACY_COLUMNS = (
    "event_id", "trade_ts", "counterparty_id", "sku", "warehouse",
    "kind", "quantity", "amount", "currency", "terminal", "memo",
)
ROLLUP_FIELDS = ("region", "segment", "kind", "category",
                 "channel_group", "fiscal_period", "source")
LEGACY_SIGNS = {"sale": 1, "fee": 1, "refund": -1, "credit": -1}
UNIT_SIGNS = {"sale": 1, "refund": -1}
ROUNDERS = {"half_up": ROUND_HALF_UP, "half_even": ROUND_HALF_EVEN,
            "half_down": ROUND_HALF_DOWN}
OWN_COLUMNS = {
    "sales.csv": {"trade_ts", "counterparty_id", "sku", "warehouse", "quantity",
                  "unit_price", "currency", "terminal"},
    "refunds.tsv": {"trade_ts", "counterparty_id", "sku", "warehouse", "quantity",
                    "refund_amount", "currency", "terminal", "sale_event_id"},
    "adjustments.jsonl": {"trade_ts", "counterparty_id", "sku", "kind", "amount_minor",
                          "currency", "note"},
    "legacy.txt": {"trade_ts", "counterparty_id", "sku", "warehouse", "kind", "quantity",
                   "amount", "currency", "terminal", "memo"},
}
HALF_CENT = Decimal("0.5")


class Rejected(Exception):
    pass


UNSETTLEABLE = (Rejected, ArithmeticError, ValueError, TypeError, AttributeError, KeyError)


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
        raise Rejected("quantity needs ascii digits")
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
        raise Rejected("trade_ts is not a real instant") from exc


class Book:
    """Every reference table the settlement chain walks."""

    def __init__(self, folder):
        contract = configparser.ConfigParser()
        contract.read_string((folder / "policy.ini").read_text(encoding="utf-8"))
        self.floors = {key.split("_")[1]: int(value)
                       for key, value in contract["collateral"].items()}
        self.opening_day = tidy(contract["ladder"]["opening_rate_date"])
        self.rounding = ROUNDERS[label(contract["rounding"]["mode"])]
        self.per_kilo = Decimal(tidy(contract["mass"]["grams_per_kilogram"]))
        self.no_period = tidy(contract["labels"]["unassigned_period"])
        self.adjust_group = label(contract["labels"]["adjustment_channel_group"])

        self.party = {}
        ranked = {}
        for position, row in enumerate(sheet(folder, "counterparties.csv")):
            who = tidy(row["counterparty_id"])
            rank = (tidy(row["updated_at"]), position)
            if who in ranked and ranked[who] > rank:
                continue
            ranked[who] = rank
            self.party[who] = {
                "segment": label(row["segment"]),
                "postal": tidy(row["postal_code"]),
                "minor": tidy(row["opening_balance_minor"]),
                "money": tidy(row["opening_currency"]).upper(),
            }

        self.prefix = {}
        self.above = {}
        for row in sheet(folder, "regions.csv"):
            name = label(row["region"])
            self.prefix[tidy(row["postal_prefix"])] = (name, tidy(row["default_currency"]).upper())
            self.above[name] = label(row["parent_region"])

        self.kind_of = {}
        self.mass_of = {}
        for row in sheet(folder, "product_catalog.csv"):
            code = tidy(row["sku"])
            self.kind_of[code] = label(row["category"])
            self.mass_of[code] = Decimal(tidy(row["unit_mass_kg"]))

        self.group = {label(row["terminal"]): label(row["channel_group"])
                      for row in sheet(folder, "channels.csv")}

        self.postal_of = {}
        self.shift_of = {}
        self.stock = {}
        self.loose_grams = 0
        for row in sheet(folder, "inventory.csv"):
            depot = tidy(row["warehouse"])
            self.postal_of[depot] = tidy(row["postal_code"])
            self.shift_of[depot] = int(tidy(row["tz_offset_minutes"]))
            code = tidy(row["sku"])
            held, trigger = self.stock.get(code, (0, 0))
            grams = int(tidy(row["on_hand_grams"]))
            self.stock[code] = (held + grams, trigger + int(tidy(row["reorder_point_grams"])))

        self.quote = {}
        self.quote_days = {}
        for row in sheet(folder, "fx_rates.csv"):
            day = tidy(row["rate_date"])
            money = tidy(row["currency"]).upper()
            self.quote[(day, money)] = Decimal(tidy(row["usd_rate"]))
            self.quote_days.setdefault(money, []).append(day)
        for money in self.quote_days:
            self.quote_days[money].sort()

        almanac = json.loads((folder / "fiscal_calendar.json").read_text(encoding="utf-8"))
        self.spans = sorted((tidy(p["start"]), tidy(p["end"]), tidy(p["period"]))
                            for p in almanac["periods"])

        for code, (grams, _trigger) in self.stock.items():
            if code not in self.kind_of:
                self.loose_grams += grams

    def ancestor(self, name):
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
            raise Rejected("no usable rate")
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
        info = self.party[who]
        rate, _ = self.rate(self.opening_day, info["money"])
        amount, _ = self.cents(Decimal(info["minor"]) / 100, rate)
        return amount


def amendments(folder):
    """Winning correction per (event id, field), newest then latest in file."""
    chosen = {}
    for line_no, line in enumerate((folder / "corrections.log")
                                   .read_text(encoding="utf-8").splitlines()):
        pieces = line.split()
        if len(pieces) < 3 or pieces[2] != "correction":
            continue
        tokens = dict(piece.partition("=")[::2] for piece in pieces[3:])
        if "target" not in tokens or "field" not in tokens:
            continue
        slot = (tokens["target"], tokens["field"])
        stamp = (pieces[0], line_no)
        if slot not in chosen or stamp > chosen[slot][0]:
            chosen[slot] = (stamp, tokens.get("value", ""))
    return {slot: payload for slot, (_stamp, payload) in chosen.items()}


def harvest(folder):
    """(source, raw mapping) for every candidate event line, in file order."""
    found = []
    if (folder / "sales.csv").is_file():
        for row in sheet(folder, "sales.csv"):
            found.append(("sales.csv", row))
    if (folder / "refunds.tsv").is_file():
        for row in sheet(folder, "refunds.tsv", "\t"):
            found.append(("refunds.tsv", row))
    if (folder / "adjustments.jsonl").is_file():
        for line in (folder / "adjustments.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                found.append(("adjustments.jsonl", json.loads(line)))
            except ValueError:
                found.append(("adjustments.jsonl", {}))
    if (folder / "legacy.txt").is_file():
        for line in (folder / "legacy.txt").read_text(encoding="latin-1").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = [piece.strip() for piece in line.split("|")]
            found.append(("legacy.txt",
                          dict(zip(LEGACY_COLUMNS, parts)) if len(parts) == 11 else {}))
    return found


def gross_of(source, raw):
    if source == "sales.csv":
        units = counted(raw.get("quantity"))
        try:
            price = Decimal(tidy(raw.get("unit_price")))
        except ArithmeticError as exc:
            raise Rejected("unit_price") from exc
        return "sale", units, price * units
    if source == "refunds.tsv":
        units = counted(raw.get("quantity"))
        try:
            size = Decimal(tidy(raw.get("refund_amount")))
        except ArithmeticError as exc:
            raise Rejected("refund_amount") from exc
        return "refund", units, -abs(size)
    if source == "adjustments.jsonl":
        kind = label(raw.get("kind"))
        if kind not in ("fee", "credit"):
            raise Rejected("adjustment kind")
        booked = raw.get("amount_minor")
        if isinstance(booked, bool) or not isinstance(booked, int):
            raise Rejected("amount_minor")
        return kind, 0, Decimal(booked) / 100
    kind = label(raw.get("kind"))
    if kind not in LEGACY_SIGNS:
        raise Rejected("legacy kind")
    units = counted(raw.get("quantity"))
    try:
        size = Decimal(tidy(raw.get("amount")))
    except ArithmeticError as exc:
        raise Rejected("amount") from exc
    return kind, units, abs(size) * LEGACY_SIGNS[kind]


def settle(source, raw, book):
    who = tidy(raw.get("counterparty_id"))
    code = tidy(raw.get("sku"))
    if who not in book.party:
        raise Rejected("counterparty")
    if code not in book.kind_of:
        raise Rejected("sku")
    party = book.party[who]
    if source == "adjustments.jsonl":
        postal, depot, shift = party["postal"], None, 0
        group = book.adjust_group
    else:
        depot = tidy(raw.get("warehouse"))
        if depot not in book.postal_of:
            raise Rejected("warehouse")
        postal, shift = book.postal_of[depot], book.shift_of[depot]
        terminal = label(raw.get("terminal"))
        if terminal not in book.group:
            raise Rejected("terminal")
        group = book.group[terminal]
    head = postal.partition("-")[0].strip()
    if head not in book.prefix:
        raise Rejected("postal prefix")
    leaf, fallback = book.prefix[head]
    money = tidy(raw.get("currency")).upper() or fallback
    local = instant_of(raw.get("trade_ts"))
    moment = local - timedelta(minutes=shift)
    day = moment.date().isoformat()
    rate, carried = book.rate(day, money)
    kind, units, gross = gross_of(source, raw)
    amount, product = book.cents(gross, rate)
    return {
        "event_id": tidy(raw.get("event_id")),
        "settlement_date": day,
        "utc_instant": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fiscal_period": book.span_of(day),
        "counterparty_id": who,
        "segment": party["segment"],
        "region": book.ancestor(leaf),
        "sku": code,
        "category": book.kind_of[code],
        "kind": kind,
        "quantity": units,
        "settled_usd_cents": amount,
        "currency": money,
        "source": source,
        "channel_group": group,
        "warehouse": depot,
    }, {
        "carried": carried,
        "shifted": moment.date() != local.date(),
        "halved": abs(product) % 1 == HALF_CENT,
    }


def units_of(row):
    return UNIT_SIGNS.get(row["kind"], 0) * row["quantity"]


def ladder_key(entry):
    """Ladder order: holder first, then UTC instant, then event id as text."""
    return entry["counterparty_id"], entry["utc_instant"], entry["event_id"]


def walk_ladder(entries, book):
    """Stream one verdict per event, holder by holder, carrying the balance.

    The gate is a feedback loop and not a predicate: what event N+1 is judged
    against is the balance standing after event N, so no record can be decided
    on its own and the run cannot be filtered before it is folded. Sorting the
    whole stream by (holder, instant, id) lays each holder's run down in one
    contiguous block, so a single groupby walk settles the book without
    bucketing the records first. Every holder's run is closed by a marker
    carrying the balance it came to rest at.
    """
    for holder, run in groupby(sorted(entries, key=ladder_key),
                               itemgetter("counterparty_id")):
        standing = book.opening_cents(holder)
        requirement = book.floors[book.party[holder]["segment"]]
        for entry in run:
            swing = entry["settled_usd_cents"]
            if swing < 0 and standing + swing < requirement:
                yield holder, entry, False, standing
                continue
            standing = standing + swing
            yield holder, entry, True, standing
        yield holder, None, None, standing


def settle_ladder(entries, book):
    """Drain the walk into accepted records, refused records and the closing total.

    A holder the walk never reaches carries no events at all, so it rests at its
    own opening balance and still counts toward the closing total.
    """
    admitted, refused, rested = [], [], {}
    for holder, entry, verdict, standing in walk_ladder(entries, book):
        rested[holder] = standing
        if verdict is True:
            admitted.append(entry)
        elif verdict is False:
            refused.append(entry)
    closing_total = sum(rested[holder] if holder in rested
                        else book.opening_cents(holder)
                        for holder in book.party)
    return admitted, refused, closing_total


def money_map(rows, field):
    """Settled cents summed per distinct value of one field, in key order."""
    tally = {}
    for row in rows:
        tally[row[field]] = tally.get(row[field], 0) + row["settled_usd_cents"]
    return dict(sorted(tally.items()))


def bucket(admitted, refused, field, name, extra=None):
    """One region or segment slice, with its own blocked tally."""
    cohort = [row for row in admitted if row[field] == name]
    slice_doc = {field: name}
    slice_doc["event_count"] = len(cohort)
    slice_doc["total_usd_cents"] = sum(row["settled_usd_cents"] for row in cohort)
    slice_doc["net_units"] = sum(units_of(row) for row in cohort)
    slice_doc["blocked_count"] = sum(1 for row in refused if row[field] == name)
    slice_doc["counterparties"] = sorted({row["counterparty_id"] for row in cohort})
    slice_doc["by_kind"] = money_map(cohort, "kind")
    slice_doc["by_category"] = money_map(cohort, "category")
    slice_doc.update(extra or {})
    return slice_doc


def document(path, doc):
    """Every .json artifact: sorted keys, two space indent, closing newline."""
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def settle_book(folder, out_dir):
    book = Book(folder)
    fixes = amendments(folder)
    rows = harvest(folder)
    present = [feed for feed in FEEDS if (folder / feed).is_file()]
    sales_ids = {tidy(raw.get("event_id")) for source, raw in rows if source == "sales.csv"}
    known_ids = {tidy(raw.get("event_id")) for _source, raw in rows if tidy(raw.get("event_id"))}
    stale = sorted({target_id for target_id, _field in fixes if target_id not in known_ids})

    resolved, dead_links = [], []
    skipped = {feed: 0 for feed in present}
    bad_sales, touched = set(), set()
    marks = {"carried": 0, "shifted": 0, "halved": 0, "stale_link": 0}
    for source, raw in rows:
        event_id = tidy(raw.get("event_id"))
        patched = dict(raw)
        for field in OWN_COLUMNS[source]:
            if (event_id, field) in fixes:
                patched[field] = fixes[(event_id, field)]
                touched.add(event_id)
        if source == "refunds.tsv":
            link = tidy(patched.get("sale_event_id"))
            if link and link not in sales_ids:
                dead_links.append(event_id)
                continue
        try:
            entry, flags = settle(source, patched, book)
        except UNSETTLEABLE:
            skipped[source] += 1
            if source == "sales.csv":
                bad_sales.add(event_id)
            continue
        resolved.append(entry)
        entry["_link"] = tidy(patched.get("sale_event_id")) if source == "refunds.tsv" else ""
        entry["_flags"] = flags

    admitted, refused, closing_total = settle_ladder(resolved, book)
    for entry in admitted:
        flags = entry.pop("_flags")
        link = entry.pop("_link")
        marks["carried"] += bool(flags["carried"])
        marks["shifted"] += bool(flags["shifted"])
        marks["halved"] += bool(flags["halved"])
        marks["stale_link"] += bool(link and link in bad_sales)
    for entry in refused:
        entry.pop("_flags", None)
        entry.pop("_link", None)

    admitted.sort(key=itemgetter("event_id"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "normalized.jsonl").write_text(
        "".join(json.dumps(entry, separators=(",", ":"), sort_keys=True) + "\n"
                for entry in admitted), encoding="utf-8")

    book_roll = {}
    book_roll["event_count"] = len(admitted)
    book_roll["skipped_count"] = sum(skipped.values())
    book_roll["blocked_count"] = len(refused)
    book_roll["orphan_refund_count"] = len(dead_links)
    book_roll["total_usd_cents"] = sum(row["settled_usd_cents"] for row in admitted)
    book_roll["net_units"] = sum(units_of(row) for row in admitted)
    book_roll["ladder_closing_usd_cents"] = closing_total
    for field in ROLLUP_FIELDS:
        book_roll["by_" + field] = money_map(admitted, field)
    document(out_dir / "summary.json", book_roll)

    taken_per_feed = {}
    for entry in admitted:
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
    health["orphan_refund_count"] = len(dead_links)
    health["blocked_event_ids"] = sorted({row["event_id"] for row in refused})
    health["orphan_refund_event_ids"] = sorted(set(dead_links))
    health["unmatched_correction_targets"] = stale
    document(out_dir / "data_quality.json", health)

    by_sku = {}
    for entry in admitted:
        by_sku.setdefault(entry["sku"], []).append(entry)
    catalogue = []
    for code in sorted(book.kind_of):
        cohort = by_sku.get(code, [])
        held, trigger = book.stock.get(code, (0, 0))
        net_count = sum(units_of(row) for row in cohort)
        mass = Decimal(net_count) * book.mass_of[code] * book.per_kilo
        line = {"sku": code, "category": book.kind_of[code]}
        line["event_count"] = len(cohort)
        line["total_usd_cents"] = sum(row["settled_usd_cents"] for row in cohort)
        line["net_units"] = net_count
        line["on_hand_grams"] = held
        line["reorder_point_grams"] = trigger
        line["net_mass_grams"] = int(mass.quantize(Decimal(1), rounding=book.rounding))
        catalogue.append(line)
    document(out_dir / "product_summary.json", {"products": catalogue})

    for name in TOP_REGIONS:
        document(out_dir / f"region_{name}.json",
                 bucket(admitted, refused, "region", name))
    for name in BOOK_SEGMENTS:
        document(out_dir / f"segment_{name}.json",
                 bucket(admitted, refused, "segment", name,
                        {"collateral_floor_usd_cents": book.floors[name]}))

    closing_report = {}
    closing_report["blocked_value_usd_cents"] = sum(row["settled_usd_cents"]
                                                    for row in refused)
    closing_report["blocked_counterparties"] = len({row["counterparty_id"]
                                                    for row in refused})
    closing_report["carry_forward_rate_events"] = marks["carried"]
    closing_report["day_shift_events"] = marks["shifted"]
    closing_report["corrected_events"] = len(touched)
    closing_report["half_cent_events"] = marks["halved"]
    closing_report["underwater_counterparties"] = sum(
        1 for who, info in book.party.items()
        if book.opening_cents(who) < book.floors[info["segment"]])
    closing_report["uncatalogued_stock_grams"] = book.loose_grams
    closing_report["stale_link_refunds"] = marks["stale_link"]
    return closing_report


if __name__ == "__main__":
    argv = sys.argv[1:]
    source_dir = Path(argv[0] if argv else os.environ.get("INPUT_DIR", "/app/data"))
    target_dir = Path(argv[1] if len(argv) > 1 else os.environ.get("OUTPUT_DIR", "/app/out"))
    print(json.dumps(settle_book(source_dir, target_dir), indent=2, sort_keys=True))
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

    print(f"Built the reusable settlement pipeline at {script_path} and settled {source_dir}.")
    print("Artifacts written:")
    print(f"  {script_path}")
    for name in ARTIFACT_NAMES:
        print(f"  {target_dir / name}")
    print("Closing report figures:")
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    main()
