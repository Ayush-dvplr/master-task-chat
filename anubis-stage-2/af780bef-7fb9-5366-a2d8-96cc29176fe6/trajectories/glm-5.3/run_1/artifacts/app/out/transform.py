#!/usr/bin/env python3
"""Deposit gated meter settlement transform.

Rebuilds the FY31 settlement book from a flat export directory: it normalizes
the four event files, applies audit amendments, filters malformed rows and
orphaned rebate links, walks the deposit ladder per account, and writes every
aggregate artifact the written contract calls for.

Usage:  python3 transform.py <DATA_DIR> <OUT_DIR>
"""

import configparser
import csv
import datetime
import json
import os
import re
import sys
from collections import defaultdict
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Decimal,
    getcontext,
)

getcontext().prec = 120

MONEY_RE = re.compile(r"^[+-]?[0-9]+(?:\.[0-9]+)?$")
QUANTITY_RE = re.compile(r"^[0-9]+$")
TS_RE = re.compile(
    r"^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(Z?)$"
)
AMENDMENT_RE = re.compile(
    r"^(\S+)\s+(\S+)\s+amendment\s+target=(\S*)\s+field=(\S*)\s+value=(.*)$"
)

ADJUSTMENT_COLUMNS = (
    "event_id",
    "read_ts",
    "account_id",
    "tariff_code",
    "kind",
    "amount_minor",
    "currency",
    "memo",
)
LEGACY_COLUMNS = (
    "event_id",
    "read_ts",
    "account_id",
    "tariff_code",
    "substation",
    "kind",
    "quantity",
    "amount",
    "currency",
    "intake_terminal",
    "memo",
)
LEGACY_FIELD_COUNT = len(LEGACY_COLUMNS)
LEGACY_SIGN = {"charge": 1, "surcharge": 1, "rebate": -1, "waiver": -1}
ADJUSTMENT_KINDS = ("surcharge", "waiver")
CANONICAL_REGIONS = ("central", "east", "north", "south", "west")
CANONICAL_SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
ROUNDING_MODES = {
    "half_up": ROUND_HALF_UP,
    "half_even": ROUND_HALF_EVEN,
    "up": ROUND_UP,
    "down": ROUND_DOWN,
    "floor": ROUND_FLOOR,
    "ceiling": ROUND_CEILING,
    "ceil": ROUND_CEILING,
}


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #


def read_text(path, encoding="utf-8"):
    """Return the file text split into lines, or None when absent."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding=encoding, errors="replace") as handle:
        text = handle.read()
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def read_csv_rows(path, delimiter=","):
    """Return (header, rows) where rows are lists of trimmed field strings."""
    if not os.path.isfile(path):
        return [], []
    rows = []
    with open(path, newline="", encoding="utf-8", errors="replace") as handle:
        for record in csv.reader(handle, delimiter=delimiter):
            rows.append([field.strip() for field in record])
    header = rows.pop(0) if rows else []
    return header, rows


def row_to_fields(header, row):
    return {
        name: row[index]
        for index, name in enumerate(header)
        if index < len(row)
    }


def parse_decimal(text):
    text = (text or "").strip() if isinstance(text, str) else None
    if text is None or not MONEY_RE.match(text):
        return None
    return Decimal(text)


def parse_timestamp(text):
    """Return a naive datetime for `YYYY-MM-DDTHH:MM:SS` plus an optional `Z`."""
    text = (text or "").strip() if isinstance(text, str) else None
    if text is None:
        return None
    match = TS_RE.match(text)
    if not match:
        return None
    year, month, day, hour, minute, second, _zulu = match.groups()
    try:
        return datetime.datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second)
        )
    except ValueError:
        return None


def parse_int(text):
    if isinstance(text, bool):
        return None
    if isinstance(text, int):
        return text
    if not isinstance(text, str):
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


def quantize(value, scale, rounding):
    return int(value.quantize(Decimal(1).scaleb(-scale), rounding=rounding))


# --------------------------------------------------------------------------- #
# policy
# --------------------------------------------------------------------------- #


def load_policy(data_dir):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(os.path.join(data_dir, "policy.ini"), encoding="utf-8")
    mode = (parser.get("rounding", "mode", fallback="half_up") or "").strip().lower()
    deposits = {}
    if parser.has_section("deposit"):
        for key, value in parser.items("deposit"):
            if key.startswith("minimum_") and key.endswith("_usd_cents"):
                segment = key[len("minimum_") : -len("_usd_cents")].strip().lower()
                parsed = parse_int(value)
                if segment:
                    deposits[segment] = parsed if parsed is not None else 0
    litres = parse_decimal(parser.get("volume", "litres_per_cubic_metre", fallback="1000"))
    return {
        "opening_rate_date": (
            parser.get("ladder", "opening_rate_date", fallback="") or ""
        ).strip(),
        "strike_limit": parse_int(parser.get("ladder", "strike_limit", fallback="0")) or 0,
        "rounding_mode": ROUNDING_MODES.get(mode, ROUND_HALF_UP),
        "money_scale": parse_int(parser.get("rounding", "money_scale", fallback="0")) or 0,
        "volume_scale": parse_int(parser.get("rounding", "volume_scale", fallback="0")) or 0,
        "litres_per_cubic_metre": litres if litres is not None else Decimal(1000),
        "unassigned_cycle": (
            parser.get("labels", "unassigned_cycle", fallback="unassigned") or ""
        ).strip(),
        "adjustment_channel_group": (
            parser.get("labels", "adjustment_channel_group", fallback="adjustment") or ""
        ).strip().lower(),
        "minimum_deposit": deposits,
    }


# --------------------------------------------------------------------------- #
# reference tables
# --------------------------------------------------------------------------- #


class Book:
    """Every reference table the settlement chain needs."""

    def __init__(self, data_dir, policy):
        self.policy = policy
        self.accounts = self._load_accounts(data_dir)
        self.zones = self._load_zones(data_dir)
        self.fleet = self._load_fleet(data_dir)
        self.fleet_capacity = self._load_fleet_capacity(data_dir)
        self.channels = self._load_channels(data_dir)
        self.catalogue = self._load_catalogue(data_dir)
        self.rates = self._load_rates(data_dir)
        self.calendar = self._load_calendar(data_dir)

    def _load_accounts(self, data_dir):
        header, rows = read_csv_rows(os.path.join(data_dir, "accounts.csv"))
        latest = {}
        for index, row in enumerate(rows):
            fields = row_to_fields(header, row)
            account_id = fields.get("account_id", "")
            if not account_id:
                continue
            key = (fields.get("updated_at", ""), index)
            current = latest.get(account_id)
            if current is None or key > current[0]:
                latest[account_id] = (key, fields)
        accounts = {}
        for account_id, (_key, fields) in latest.items():
            minor = parse_int(fields.get("opening_deposit_minor", ""))
            accounts[account_id] = {
                "account_id": account_id,
                "segment": fields.get("segment", "").lower(),
                "postal_code": fields.get("postal_code", ""),
                "opening_minor": minor if minor is not None else 0,
                "opening_currency": fields.get("opening_currency", "").upper(),
            }
        return accounts

    def _load_zones(self, data_dir):
        header, rows = read_csv_rows(os.path.join(data_dir, "service_zones.csv"))
        parents = {}
        prefixes = {}
        for row in rows:
            fields = row_to_fields(header, row)
            zone = fields.get("zone", "").lower()
            if zone:
                parents[zone] = fields.get("parent_zone", "").lower()
            prefix = fields.get("postal_prefix", "")
            if prefix:
                prefixes[prefix] = {
                    "zone": zone,
                    "default_currency": fields.get("default_currency", "").upper(),
                }
        return {"parents": parents, "prefixes": prefixes}

    def zone_region(self, zone):
        """Top level ancestor of a zone label, or None when the ladder breaks."""
        parents = self.zones["parents"]
        seen = set()
        current = zone
        while current:
            if current in seen:
                return None
            seen.add(current)
            parent = parents.get(current)
            if parent is None:
                return None
            if not parent:
                return current
            current = parent
        return None

    def top_level_regions(self):
        return sorted(
            {zone for zone, parent in self.zones["parents"].items() if not parent}
        )

    def _load_fleet(self, data_dir):
        header, rows = read_csv_rows(os.path.join(data_dir, "meter_fleet.csv"))
        stations = {}
        for row in rows:
            fields = row_to_fields(header, row)
            substation = fields.get("substation", "")
            if not substation or substation in stations:
                continue
            offset = parse_int(fields.get("tz_offset_minutes", ""))
            stations[substation] = {
                "postal_code": fields.get("postal_code", ""),
                "tz_offset_minutes": offset,
            }
        return stations

    def _load_fleet_capacity(self, data_dir):
        header, rows = read_csv_rows(os.path.join(data_dir, "meter_fleet.csv"))
        totals = {}
        for row in rows:
            fields = row_to_fields(header, row)
            tariff = fields.get("tariff_code", "")
            if not tariff:
                continue
            entry = totals.setdefault(tariff, {"capacity": 0, "threshold": 0})
            capacity = parse_int(fields.get("metered_capacity_litres", ""))
            threshold = parse_int(fields.get("service_threshold_litres", ""))
            entry["capacity"] += capacity if capacity is not None else 0
            entry["threshold"] += threshold if threshold is not None else 0
        return totals

    def _load_channels(self, data_dir):
        header, rows = read_csv_rows(os.path.join(data_dir, "intake_channels.csv"))
        channels = {}
        for row in rows:
            fields = row_to_fields(header, row)
            terminal = fields.get("intake_terminal", "").lower()
            if terminal and terminal not in channels:
                channels[terminal] = fields.get("channel_group", "").lower()
        return channels

    def _load_catalogue(self, data_dir):
        header, rows = read_csv_rows(os.path.join(data_dir, "tariff_catalogue.csv"))
        catalogue = {}
        for row in rows:
            fields = row_to_fields(header, row)
            tariff = fields.get("tariff_code", "")
            if not tariff:
                continue
            volume = parse_decimal(fields.get("unit_volume_m3", ""))
            catalogue[tariff] = {
                "tariff_code": tariff,
                "category": fields.get("category", "").lower(),
                "unit_volume_m3": volume if volume is not None else Decimal(0),
                "active": fields.get("active", "").lower(),
            }
        return catalogue

    def _load_rates(self, data_dir):
        header, rows = read_csv_rows(os.path.join(data_dir, "currency_rates.csv"))
        table = {}
        for row in rows:
            fields = row_to_fields(header, row)
            currency = fields.get("currency", "").upper()
            rate_date = fields.get("rate_date", "")
            rate = parse_decimal(fields.get("usd_rate", ""))
            if not currency or not rate_date or rate is None:
                continue
            table.setdefault(currency, []).append((rate_date, rate))
        rates = {}
        for currency, pairs in table.items():
            pairs.sort()
            rates[currency] = ([date for date, _rate in pairs], [rate for _date, rate in pairs])
        return rates

    def rate_for(self, currency, rate_date):
        """Return (rate, carried_forward) for the nearest row on or before."""
        entry = self.rates.get((currency or "").upper())
        if not entry:
            return None, False
        dates = entry[0]
        low, high = 0, len(dates)
        while low < high:
            middle = (low + high) // 2
            if dates[middle] <= rate_date:
                low = middle + 1
            else:
                high = middle
        if low == 0:
            return None, False
        return entry[1][low - 1], dates[low - 1] != rate_date

    def _load_calendar(self, data_dir):
        lines = read_text(os.path.join(data_dir, "billing_calendar.json"))
        cycles = []
        if lines is not None:
            try:
                payload = json.loads("\n".join(lines))
            except ValueError:
                payload = None
            for cycle in (payload or {}).get("cycles", []) or []:
                if not isinstance(cycle, dict):
                    continue
                label, opens, closes = cycle.get("cycle"), cycle.get("opens"), cycle.get("closes")
                if not isinstance(label, str) or not opens or not closes:
                    continue
                cycles.append((opens, closes, label))
        cycles.sort()
        return cycles

    def billing_period(self, settlement_date):
        for opens, closes, label in self.calendar:
            if opens <= settlement_date <= closes:
                return label
        return self.policy["unassigned_cycle"]


# --------------------------------------------------------------------------- #
# event loading and amendment handling
# --------------------------------------------------------------------------- #


class RawEvent:
    """A single row of one event file, before any field is parsed."""

    __slots__ = ("source", "columns", "fields")

    def __init__(self, source, columns, fields):
        self.source = source
        self.columns = columns
        self.fields = fields

    def text(self, name):
        value = self.fields.get(name)
        if isinstance(value, str):
            return value.strip()
        return value

    @property
    def event_id(self):
        value = self.fields.get("event_id")
        return value.strip() if isinstance(value, str) else None


def load_raw_events(data_dir):
    """Return the raw rows of every event file that is present."""
    events = []
    sources = []

    for name, delimiter in (("meter_reads.csv", ","), ("rebates.tsv", "\t")):
        if not os.path.isfile(os.path.join(data_dir, name)):
            continue
        sources.append(name)
        header, rows = read_csv_rows(os.path.join(data_dir, name), delimiter=delimiter)
        for row in rows:
            events.append(RawEvent(name, tuple(header), row_to_fields(header, row)))

    path = os.path.join(data_dir, "adjustments.jsonl")
    lines = read_text(path)
    if lines is not None:
        sources.append("adjustments.jsonl")
        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except ValueError:
                payload = None
            events.append(
                RawEvent(
                    "adjustments.jsonl",
                    ADJUSTMENT_COLUMNS,
                    payload if isinstance(payload, dict) else {},
                )
            )

    lines = read_text(os.path.join(data_dir, "legacy_ledger.txt"), encoding="latin-1")
    if lines is not None:
        sources.append("legacy_ledger.txt")
        for line in lines:
            if not line.strip() or line.strip().startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) != LEGACY_FIELD_COUNT:
                events.append(RawEvent("legacy_ledger.txt", LEGACY_COLUMNS, {}))
                continue
            events.append(
                RawEvent(
                    "legacy_ledger.txt", LEGACY_COLUMNS, row_to_fields(LEGACY_COLUMNS, parts)
                )
            )
    return events, sources


def load_amendments(data_dir):
    lines = read_text(os.path.join(data_dir, "audit_trail.log"))
    amendments = []
    for order, line in enumerate(lines or []):
        match = AMENDMENT_RE.match(line)
        if not match:
            continue
        stamp, _level, target, field, value = match.groups()
        amendments.append((stamp, order, target, field, value))
    return amendments


def apply_amendments(events, amendments):
    """Apply amendments, resolve duplicates, and report unmatched targets."""
    by_event = defaultdict(list)
    for event in events:
        if event.event_id:
            by_event[event.event_id].append(event)

    winners = {}
    for stamp, order, target, field, value in amendments:
        if field == "event_id":
            continue
        key = (target, field)
        current = winners.get(key)
        if current is None or (stamp, order) > current[0]:
            winners[key] = ((stamp, order), value)

    unmatched = set()
    amended = set()
    for (target, field), (_stamp, value) in winners.items():
        targets = by_event.get(target)
        if not targets:
            unmatched.add(target)
            continue
        applied = False
        for event in targets:
            if field in event.columns:
                event.fields[field] = value
                applied = True
        if applied:
            amended.add(target)
    return sorted(unmatched), amended


# --------------------------------------------------------------------------- #
# settlement of a single event
# --------------------------------------------------------------------------- #


class Candidate:
    """A parsed event that cleared every malformed test."""

    __slots__ = (
        "event_id",
        "source",
        "kind",
        "quantity",
        "gross",
        "product",
        "settled_usd_cents",
        "account_id",
        "segment",
        "region",
        "tariff_code",
        "category",
        "currency",
        "channel_group",
        "substation",
        "utc_instant",
        "settlement_date",
        "local_date",
        "billing_period",
        "carried_forward",
        "read_event_id",
        "gate_reason",
    )


def parse_event(event, book, policy):
    """Return a Candidate, or None when the event is malformed."""
    source = event.source
    get = event.text

    account_id = get("account_id")
    account = book.accounts.get(account_id) if isinstance(account_id, str) else None
    if account is None:
        return None

    tariff_code = get("tariff_code")
    tariff = book.catalogue.get(tariff_code) if isinstance(tariff_code, str) else None
    if tariff is None:
        return None

    read_ts = get("read_ts")
    stamp = parse_timestamp(read_ts) if isinstance(read_ts, str) else None
    if stamp is None:
        return None

    candidate = Candidate()
    candidate.event_id = event.event_id or ""
    candidate.source = source
    candidate.account_id = account_id
    candidate.segment = account["segment"]
    candidate.tariff_code = tariff_code
    candidate.category = tariff["category"]
    candidate.local_date = stamp.date().isoformat()
    candidate.gate_reason = ""

    if source == "adjustments.jsonl":
        kind = get("kind")
        if not isinstance(kind, str) or kind.lower() not in ADJUSTMENT_KINDS:
            return None
        minor = event.fields.get("amount_minor")
        if isinstance(minor, bool) or not isinstance(minor, int):
            return None
        candidate.kind = kind.lower()
        candidate.gross = Decimal(minor) / Decimal(100)
        candidate.quantity = 0
        candidate.substation = None
        candidate.channel_group = policy["adjustment_channel_group"]
        candidate.read_event_id = None
        instant = stamp
        postal_code = account["postal_code"]
    else:
        substation = get("substation")
        station = book.fleet.get(substation) if isinstance(substation, str) else None
        if station is None or station["tz_offset_minutes"] is None:
            return None
        quantity_text = get("quantity")
        if not isinstance(quantity_text, str) or not QUANTITY_RE.match(quantity_text):
            return None
        candidate.quantity = int(quantity_text)
        candidate.substation = substation
        candidate.read_event_id = None
        instant = stamp + datetime.timedelta(minutes=station["tz_offset_minutes"])
        postal_code = station["postal_code"]

        if source == "meter_reads.csv":
            unit_rate = parse_decimal(get("unit_rate"))
            if unit_rate is None:
                return None
            candidate.kind = "charge"
            candidate.gross = Decimal(candidate.quantity) * unit_rate
        elif source == "rebates.tsv":
            amount = parse_decimal(get("rebate_amount"))
            if amount is None:
                return None
            candidate.kind = "rebate"
            candidate.gross = -abs(amount)
            candidate.read_event_id = get("read_event_id") or ""
        else:
            kind = get("kind")
            if not isinstance(kind, str) or kind.lower() not in LEGACY_SIGN:
                return None
            amount = parse_decimal(get("amount"))
            if amount is None:
                return None
            candidate.kind = kind.lower()
            candidate.gross = Decimal(LEGACY_SIGN[candidate.kind]) * abs(amount)

        terminal = get("intake_terminal")
        channel = book.channels.get(terminal.lower()) if isinstance(terminal, str) else None
        if channel is None:
            return None
        candidate.channel_group = channel

    prefix = postal_code.split("-")[0].strip() if isinstance(postal_code, str) else ""
    zone_row = book.zones["prefixes"].get(prefix)
    if zone_row is None:
        return None
    region = book.zone_region(zone_row["zone"])
    if region is None:
        return None
    candidate.region = region

    own_currency = get("currency")
    if own_currency is None:
        return None
    currency = (
        own_currency.upper() if own_currency else zone_row["default_currency"]
    )
    if not currency:
        return None
    candidate.currency = currency

    candidate.utc_instant = instant.strftime("%Y-%m-%dT%H:%M:%SZ")
    candidate.settlement_date = instant.date().isoformat()
    candidate.billing_period = book.billing_period(candidate.settlement_date)

    rate, carried = book.rate_for(currency, candidate.settlement_date)
    if rate is None:
        return None
    candidate.carried_forward = carried
    candidate.product = candidate.gross * rate * Decimal(100)
    candidate.settled_usd_cents = quantize(
        candidate.product, policy["money_scale"], policy["rounding_mode"]
    )
    return candidate


# --------------------------------------------------------------------------- #
# the deposit ladder
# --------------------------------------------------------------------------- #


def opening_balance(account, book, policy):
    rate, _carried = book.rate_for(account["opening_currency"], policy["opening_rate_date"])
    if rate is None:
        rate = Decimal(1)
    return quantize(
        (Decimal(account["opening_minor"]) / Decimal(100)) * rate * Decimal(100),
        policy["money_scale"],
        policy["rounding_mode"],
    )


def run_ladder(candidates, book, policy):
    """Walk each account's events in UTC order and gate the negatives."""
    by_account = defaultdict(list)
    for candidate in candidates:
        by_account[candidate.account_id].append(candidate)

    minimum = policy["minimum_deposit"]
    limit = policy["strike_limit"]
    accepted, blocked = [], []
    closing = {}

    for account_id in sorted(book.accounts):
        account = book.accounts[account_id]
        balance = opening_balance(account, book, policy)
        floor = minimum.get(account["segment"], 0)
        strikes = 0
        suspended = False
        events = sorted(
            by_account.get(account_id, []),
            key=lambda item: (item.utc_instant, item.event_id),
        )
        for candidate in events:
            settled = candidate.settled_usd_cents
            if suspended:
                candidate.gate_reason = "suspended"
                blocked.append(candidate)
                continue
            if settled >= 0 or balance + settled >= floor:
                balance += settled
                accepted.append(candidate)
                continue
            strikes += 1
            candidate.gate_reason = "withheld"
            blocked.append(candidate)
            if strikes >= limit:
                suspended = True
        closing[account_id] = balance
    return accepted, blocked, closing


# --------------------------------------------------------------------------- #
# artifacts
# --------------------------------------------------------------------------- #


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def net_units(record):
    """Net units count a charge as +quantity, a rebate as -quantity, else zero."""
    if record["kind"] == "charge":
        return record["quantity"]
    if record["kind"] == "rebate":
        return -record["quantity"]
    return 0


def sum_by(records, field):
    totals = defaultdict(int)
    for record in records:
        totals[record[field]] += record["settled_usd_cents"]
    return dict(sorted(totals.items()))


def group_payload(records, blocked, key_name, key_value):
    return {
        key_name: key_value,
        "event_count": len(records),
        "total_usd_cents": sum(item["settled_usd_cents"] for item in records),
        "net_units": sum(net_units(item) for item in records),
        "blocked_count": len(blocked),
        "accounts": sorted({item["account_id"] for item in records}),
        "by_kind": sum_by(records, "kind"),
        "by_category": sum_by(records, "category"),
    }


def write_normalized(path, accepted_records):
    """One compact, sorted-key JSON object per accepted event, ordered by id."""
    with open(path, "w", encoding="utf-8") as handle:
        for record, _candidate in sorted(accepted_records, key=lambda pair: pair[0]["event_id"]):
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def build_summary(records, closing, skipped, blocked, orphans):
    return {
        "event_count": len(records),
        "skipped_count": skipped,
        "blocked_count": blocked,
        "orphan_rebate_count": orphans,
        "total_usd_cents": sum(item["settled_usd_cents"] for item in records),
        "net_units": sum(net_units(item) for item in records),
        "deposit_closing_usd_cents": sum(closing.values()),
        "by_region": sum_by(records, "region"),
        "by_segment": sum_by(records, "segment"),
        "by_kind": sum_by(records, "kind"),
        "by_category": sum_by(records, "category"),
        "by_channel_group": sum_by(records, "channel_group"),
        "by_billing_period": sum_by(records, "billing_period"),
        "by_source": sum_by(records, "source"),
    }


def build_data_quality(input_files, records, skipped_by_source, blocked_by_source,
                       blocked, orphans, unmatched_targets):
    records_by_source = defaultdict(int)
    for record in records:
        records_by_source[record["source"]] += 1
    return {
        "input_files": input_files,
        "records_by_source": dict(sorted(records_by_source.items())),
        "skipped_by_source": dict(sorted(skipped_by_source.items())),
        "blocked_by_source": dict(sorted(blocked_by_source.items())),
        "skipped_count": sum(skipped_by_source.values()),
        "blocked_count": len(blocked),
        "orphan_rebate_count": len(orphans),
        "blocked_event_ids": sorted({item.event_id for item in blocked}),
        "orphan_rebate_event_ids": sorted(set(orphans)),
        "unmatched_amendment_targets": unmatched_targets,
    }


def build_product_summary(book, records, policy):
    by_tariff = defaultdict(list)
    for record in records:
        by_tariff[record["tariff_code"]].append(record)
    tariffs = []
    for tariff_code in sorted(book.catalogue):
        entry = book.catalogue[tariff_code]
        fleet = book.fleet_capacity.get(tariff_code, {"capacity": 0, "threshold": 0})
        group = by_tariff.get(tariff_code, [])
        net_units_for_code = sum(net_units(item) for item in group)
        volume = (
            Decimal(net_units_for_code)
            * entry["unit_volume_m3"]
            * policy["litres_per_cubic_metre"]
        )
        tariffs.append(
            {
                "tariff_code": tariff_code,
                "category": entry["category"],
                "event_count": len(group),
                "total_usd_cents": sum(item["settled_usd_cents"] for item in group),
                "net_units": net_units_for_code,
                "metered_capacity_litres": fleet["capacity"],
                "service_threshold_litres": fleet["threshold"],
                "net_volume_litres": quantize(
                    volume, policy["volume_scale"], policy["rounding_mode"]
                ),
            }
        )
    return {"tariffs": tariffs}


def write_group_files(out_dir, records, blocked, book, policy):
    """One file per top level region and per segment, empty buckets included."""
    regions = {name: ([], []) for name in CANONICAL_REGIONS}
    for name in book.top_level_regions():
        regions.setdefault(name, ([], []))
    segments = {name: ([], []) for name in CANONICAL_SEGMENTS}
    for name in {account["segment"] for account in book.accounts.values()}:
        segments.setdefault(name, ([], []))
    for record in records:
        regions[record["region"]][0].append(record)
        segments[record["segment"]][0].append(record)
    for candidate in blocked:
        regions[candidate.region][1].append(candidate)
        segments[candidate.segment][1].append(candidate)

    for region_name in sorted(regions):
        region_records, region_blocked = regions[region_name]
        write_json(
            os.path.join(out_dir, "region_%s.json" % region_name),
            group_payload(region_records, region_blocked, "region", region_name),
        )
    for segment_name in sorted(segments):
        segment_records, segment_blocked = segments[segment_name]
        payload = group_payload(segment_records, segment_blocked, "segment", segment_name)
        payload["minimum_deposit_usd_cents"] = policy["minimum_deposit"].get(segment_name, 0)
        write_json(os.path.join(out_dir, "segment_%s.json" % segment_name), payload)


def build_closing_report(accepted_records, blocked, stale_link_ids, book, policy,
                         amended_events):
    """The thirteen figures no artifact holds."""
    withheld = [item for item in blocked if item.gate_reason == "withheld"]
    suspended = {item.account_id for item in blocked if item.gate_reason == "suspended"}
    half_cent = [
        pair for pair in accepted_records if abs(pair[1].product) % 1 == Decimal("0.5")
    ]
    carried = [pair for pair in accepted_records if pair[1].carried_forward]
    underfunded = 0
    for account in book.accounts.values():
        if opening_balance(account, book, policy) < policy["minimum_deposit"].get(
            account["segment"], 0
        ):
            underfunded += 1
    unlisted_capacity = 0
    for tariff_code, fleet in book.fleet_capacity.items():
        if tariff_code not in book.catalogue:
            unlisted_capacity += fleet["capacity"]
    return {
        "withheld_value_usd_cents": sum(item.settled_usd_cents for item in withheld),
        "suspended_accounts": len(suspended),
        "carry_forward_rate_events": len(carried),
        "day_shift_events": len(
            [
                pair
                for pair in accepted_records
                if pair[0]["settlement_date"] != pair[1].local_date
            ]
        ),
        "amended_events": len(amended_events),
        "half_cent_events": len(half_cent),
        "underfunded_accounts": underfunded,
        "unlisted_capacity_litres": unlisted_capacity,
        "stale_link_rebates": len(
            [
                pair
                for pair in accepted_records
                if pair[0]["source"] == "rebates.tsv"
                and pair[1].read_event_id in stale_link_ids
            ]
        ),
        "withheld_event_count": len(withheld),
        "gate_blocked_accounts": len({item.account_id for item in blocked}),
        "carry_forward_rate_currencies": len({pair[0]["currency"] for pair in carried}),
        "half_cent_negative_events": len(
            [pair for pair in half_cent if pair[1].product < 0]
        ),
    }


def transform(data_dir, out_dir):
    if not os.path.isdir(data_dir):
        raise SystemExit("input directory not found: %s" % data_dir)
    os.makedirs(out_dir, exist_ok=True)

    policy = load_policy(data_dir)
    book = Book(data_dir, policy)

    input_files = sorted(
        entry.name for entry in os.scandir(data_dir) if entry.is_file()
    )

    raw_events, sources_present = load_raw_events(data_dir)
    amendments = load_amendments(data_dir)
    unmatched_targets, amended_events = apply_amendments(raw_events, amendments)

    meter_read_ids = set()
    for event in raw_events:
        if event.source == "meter_reads.csv" and event.event_id:
            meter_read_ids.add(event.event_id)

    skipped_by_source = {name: 0 for name in sources_present}
    blocked_by_source = {name: 0 for name in sources_present}
    orphans = []
    skipped_meter_reads = set()
    candidates = []
    for event in raw_events:
        source = event.source
        if source == "rebates.tsv":
            link = event.text("read_event_id")
            if isinstance(link, str) and link and link not in meter_read_ids:
                orphans.append(event.event_id or "")
                continue
        candidate = parse_event(event, book, policy)
        if candidate is None:
            skipped_by_source[source] += 1
            if source == "meter_reads.csv" and event.event_id:
                skipped_meter_reads.add(event.event_id)
            continue
        candidates.append(candidate)

    accepted, blocked, closing = run_ladder(candidates, book, policy)
    for candidate in blocked:
        blocked_by_source[candidate.source] += 1

    accepted_records = [
        (
            {
                "event_id": candidate.event_id,
                "settlement_date": candidate.settlement_date,
                "utc_instant": candidate.utc_instant,
                "billing_period": candidate.billing_period,
                "account_id": candidate.account_id,
                "segment": candidate.segment,
                "region": candidate.region,
                "tariff_code": candidate.tariff_code,
                "category": candidate.category,
                "kind": candidate.kind,
                "quantity": candidate.quantity,
                "settled_usd_cents": candidate.settled_usd_cents,
                "currency": candidate.currency,
                "source": candidate.source,
                "channel_group": candidate.channel_group,
                "substation": candidate.substation,
            },
            candidate,
        )
        for candidate in accepted
    ]
    records = [record for record, _candidate in accepted_records]

    write_normalized(os.path.join(out_dir, "normalized.jsonl"), accepted_records)

    summary = build_summary(
        records, closing, sum(skipped_by_source.values()), len(blocked), len(orphans)
    )
    write_json(os.path.join(out_dir, "summary.json"), summary)

    data_quality = build_data_quality(
        input_files, records, skipped_by_source, blocked_by_source, blocked, orphans,
        unmatched_targets,
    )
    write_json(os.path.join(out_dir, "data_quality.json"), data_quality)

    write_json(
        os.path.join(out_dir, "product_summary.json"),
        build_product_summary(book, records, policy),
    )

    write_group_files(out_dir, records, blocked, book, policy)

    report = build_closing_report(
        accepted_records, blocked, skipped_meter_reads, book, policy, amended_events
    )
    return summary, data_quality, report


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py <DATA_DIR> <OUT_DIR>\n")
        return 2
    _summary, _quality, report = transform(argv[1], argv[2])
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
