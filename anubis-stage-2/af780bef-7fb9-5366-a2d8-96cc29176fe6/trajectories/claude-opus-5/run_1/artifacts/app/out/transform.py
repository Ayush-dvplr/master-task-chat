#!/usr/bin/env python3
"""FY31 deposit-gated meter settlement transform.

Usage: python3 transform.py <DATA_DIR> <OUT_DIR>
"""

import bisect
import configparser
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction

EVENT_FILES = (
    "meter_reads.csv",
    "rebates.tsv",
    "adjustments.jsonl",
    "legacy_ledger.txt",
)

COLUMNS = {
    "meter_reads.csv": (
        "event_id", "read_ts", "account_id", "tariff_code", "substation",
        "quantity", "unit_rate", "currency", "intake_terminal",
    ),
    "rebates.tsv": (
        "event_id", "read_ts", "account_id", "tariff_code", "substation",
        "quantity", "rebate_amount", "currency", "intake_terminal",
        "read_event_id",
    ),
    "adjustments.jsonl": (
        "event_id", "read_ts", "account_id", "tariff_code", "kind",
        "amount_minor", "currency", "memo",
    ),
    "legacy_ledger.txt": (
        "event_id", "read_ts", "account_id", "tariff_code", "substation",
        "kind", "quantity", "amount", "currency", "intake_terminal", "memo",
    ),
}

CANONICAL_REGIONS = ("central", "east", "north", "south", "west")

UINT_RE = re.compile(r"^[0-9]+$")
DEC_RE = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$")
TS_RE = re.compile(
    r"^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})$"
)
AMEND_RE = re.compile(r"\btarget=(\S+)\s+field=(\S+)\s+value=(.*)$")


# --------------------------------------------------------------------------
# scalar helpers
# --------------------------------------------------------------------------

def trim(value):
    return value.strip() if isinstance(value, str) else value


def fold(value):
    return value.strip().casefold() if isinstance(value, str) else value


def parse_uint(text):
    if not isinstance(text, str):
        return None
    text = text.strip()
    return int(text) if UINT_RE.match(text) else None


def parse_decimal(text):
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not DEC_RE.match(text):
        return None
    return Fraction(Decimal(text))


def parse_ts(text, zulu):
    """Parse a timestamp; ``zulu`` demands (and strips) a trailing Z."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if zulu:
        if not text.endswith("Z"):
            return None
        text = text[:-1]
    elif text.endswith("Z"):
        return None
    match = TS_RE.match(text)
    if not match:
        return None
    try:
        return datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return None


class Rounder:
    """Quantizer for the [rounding] mode named in policy.ini."""

    def __init__(self, mode):
        if mode not in ("half_up", "half_even", "half_down"):
            raise ValueError("unsupported rounding mode: %s" % mode)
        self.mode = mode

    def quantize(self, value, scale=0):
        if scale:
            value = value * Fraction(10) ** scale
        num, den = value.numerator, value.denominator
        sign = -1 if num < 0 else 1
        whole, rest = divmod(abs(num), den)
        twice = 2 * rest
        if twice > den:
            whole += 1
        elif twice == den:
            if self.mode == "half_up":
                whole += 1
            elif self.mode == "half_even" and whole % 2:
                whole += 1
        result = sign * whole
        return Fraction(result, 10 ** scale) if scale else result

    @staticmethod
    def is_half(value, scale=0):
        if scale:
            value = value * Fraction(10) ** scale
        return 2 * (abs(value.numerator) % value.denominator) == value.denominator


# --------------------------------------------------------------------------
# reference data
# --------------------------------------------------------------------------

def read_csv_rows(path, delimiter=","):
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter=delimiter):
            yield row


class Reference:
    def __init__(self, data_dir, policy):
        self.policy = policy
        self._load_accounts(os.path.join(data_dir, "accounts.csv"))
        self._load_zones(os.path.join(data_dir, "service_zones.csv"))
        self._load_fleet(os.path.join(data_dir, "meter_fleet.csv"))
        self._load_channels(os.path.join(data_dir, "intake_channels.csv"))
        self._load_tariffs(os.path.join(data_dir, "tariff_catalogue.csv"))
        self._load_rates(os.path.join(data_dir, "currency_rates.csv"))
        self._load_calendar(os.path.join(data_dir, "billing_calendar.json"))

    def _load_accounts(self, path):
        best = {}
        for order, row in enumerate(read_csv_rows(path)):
            account_id = trim(row["account_id"])
            rank = (trim(row["updated_at"]), order)
            if account_id in best and best[account_id][0] >= rank:
                continue
            best[account_id] = (rank, {
                "account_id": account_id,
                "segment": fold(row["segment"]),
                "postal_code": trim(row["postal_code"]),
                "opening_deposit_minor": int(trim(row["opening_deposit_minor"])),
                "opening_currency": trim(row["opening_currency"]).upper(),
            })
        self.accounts = {key: value for key, (_, value) in best.items()}
        self.account_order = sorted(self.accounts)

    def _load_zones(self, path):
        self.prefixes = {}
        parent = {}
        for row in read_csv_rows(path):
            zone = fold(row["zone"])
            parent[zone] = fold(row["parent_zone"])
            self.prefixes[trim(row["postal_prefix"])] = {
                "zone": zone,
                "default_currency": trim(row["default_currency"]).upper(),
            }
        self.zone_parent = parent
        self.region_of_zone = {}
        for zone in parent:
            seen = set()
            cursor = zone
            while parent.get(cursor) and cursor not in seen:
                seen.add(cursor)
                cursor = parent[cursor]
            self.region_of_zone[zone] = cursor
        self.top_regions = sorted(set(self.region_of_zone.values()))

    def _load_fleet(self, path):
        self.substations = {}
        self.fleet_capacity = defaultdict(int)
        self.fleet_threshold = defaultdict(int)
        self.fleet_rows = []
        for row in read_csv_rows(path):
            substation = trim(row["substation"])
            tariff = trim(row["tariff_code"])
            capacity = int(trim(row["metered_capacity_litres"]))
            threshold = int(trim(row["service_threshold_litres"]))
            self.substations.setdefault(substation, {
                "postal_code": trim(row["postal_code"]),
                "tz_offset_minutes": int(trim(row["tz_offset_minutes"])),
            })
            self.fleet_capacity[tariff] += capacity
            self.fleet_threshold[tariff] += threshold
            self.fleet_rows.append((tariff, capacity))

    def _load_channels(self, path):
        self.channels = {}
        for row in read_csv_rows(path):
            self.channels[fold(row["intake_terminal"])] = fold(row["channel_group"])

    def _load_tariffs(self, path):
        self.tariffs = {}
        for row in read_csv_rows(path):
            self.tariffs[trim(row["tariff_code"])] = {
                "category": fold(row["category"]),
                "unit_volume_m3": Fraction(Decimal(trim(row["unit_volume_m3"]))),
            }
        self.tariff_order = sorted(self.tariffs)

    def _load_rates(self, path):
        table = defaultdict(dict)
        for row in read_csv_rows(path):
            currency = trim(row["currency"]).upper()
            table[currency][trim(row["rate_date"])] = Fraction(
                Decimal(trim(row["usd_rate"]))
            )
        self.rate_dates = {}
        self.rate_values = {}
        for currency, by_date in table.items():
            dates = sorted(by_date)
            self.rate_dates[currency] = dates
            self.rate_values[currency] = [by_date[day] for day in dates]

    def _load_calendar(self, path):
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.cycles = [
            (trim(cycle["opens"]), trim(cycle["closes"]), trim(cycle["cycle"]))
            for cycle in payload.get("cycles", [])
        ]

    def zone_record(self, postal_code):
        return self.prefixes.get(postal_code.split("-", 1)[0])

    def rate(self, currency, day):
        """Return (rate, exact) with carry-forward to the nearest earlier date."""
        dates = self.rate_dates.get(currency)
        if not dates:
            return None, None
        index = bisect.bisect_right(dates, day) - 1
        if index < 0:
            return None, None
        return self.rate_values[currency][index], dates[index] == day

    def billing_period(self, day):
        for opens, closes, cycle in self.cycles:
            if opens <= day <= closes:
                return cycle
        return self.policy["unassigned_cycle"]


def read_policy(path):
    parser = configparser.ConfigParser()
    with open(path, encoding="utf-8") as handle:
        parser.read_file(handle)
    minimums = {}
    for key, value in parser.items("deposit"):
        match = re.match(r"^minimum_(.+)_usd_cents$", key)
        if match:
            minimums[match.group(1).casefold()] = int(value.strip())
    return {
        "opening_rate_date": parser.get("ladder", "opening_rate_date").strip(),
        "strike_limit": int(parser.get("ladder", "strike_limit").strip()),
        "minimums": minimums,
        "mode": parser.get("rounding", "mode").strip().casefold(),
        "money_scale": int(parser.get("rounding", "money_scale").strip()),
        "volume_scale": int(parser.get("rounding", "volume_scale").strip()),
        "litres_per_cubic_metre": Fraction(
            Decimal(parser.get("volume", "litres_per_cubic_metre").strip())
        ),
        "unassigned_cycle": parser.get("labels", "unassigned_cycle").strip(),
        "adjustment_channel_group": parser.get(
            "labels", "adjustment_channel_group"
        ).strip().casefold(),
    }


# --------------------------------------------------------------------------
# event intake
# --------------------------------------------------------------------------

def make_event(source, order, fields):
    return {
        "source": source,
        "order": order,
        "event_id": trim(fields["event_id"]),
        "fields": fields,
        "amended": set(),
    }


def load_events(data_dir):
    """Return every raw event row in file order, plus the legacy skip count."""
    events = []

    for order, row in enumerate(read_csv_rows(os.path.join(data_dir, "meter_reads.csv"))):
        events.append(make_event("meter_reads.csv", order, {
            name: (row.get(name) or "") for name in COLUMNS["meter_reads.csv"]
        }))

    rebates = read_csv_rows(os.path.join(data_dir, "rebates.tsv"), delimiter="\t")
    for order, row in enumerate(rebates):
        events.append(make_event("rebates.tsv", order, {
            name: (row.get(name) or "") for name in COLUMNS["rebates.tsv"]
        }))

    with open(os.path.join(data_dir, "adjustments.jsonl"), encoding="utf-8") as handle:
        order = 0
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            events.append(make_event("adjustments.jsonl", order, {
                name: payload.get(name, "") for name in COLUMNS["adjustments.jsonl"]
            }))
            order += 1

    legacy_malformed = 0
    with open(os.path.join(data_dir, "legacy_ledger.txt"), encoding="latin-1") as handle:
        order = 0
        for line in handle:
            text = line.rstrip("\n").rstrip("\r")
            stripped = text.strip()
            if not stripped or stripped[0] == "#":
                continue
            parts = text.split("|")
            order += 1
            if len(parts) != 11:
                legacy_malformed += 1
                continue
            events.append(make_event(
                "legacy_ledger.txt", order,
                dict(zip(COLUMNS["legacy_ledger.txt"], parts)),
            ))

    return events, legacy_malformed


def load_amendments(path):
    """Return {(target, field): value} after the timestamp/file-order tie-break."""
    best = {}
    with open(path, encoding="utf-8") as handle:
        for order, line in enumerate(handle):
            parts = line.rstrip("\n").split(" ", 2)
            if len(parts) < 3:
                continue
            stamp, _level, message = parts
            if not message.startswith("amendment"):
                continue
            match = AMEND_RE.search(message)
            if not match:
                continue
            target, field, value = match.groups()
            key = (target.strip(), field.strip())
            rank = (stamp.strip(), order)
            if key in best and best[key][0] >= rank:
                continue
            best[key] = (rank, value)
    return {key: value for key, (_, value) in best.items()}


# --------------------------------------------------------------------------
# settlement
# --------------------------------------------------------------------------

class Settler:
    def __init__(self, ref, policy, rounder):
        self.ref = ref
        self.policy = policy
        self.rounder = rounder

    def settle(self, event):
        """Return a settled candidate, or None when the event is malformed."""
        source = event["source"]
        fields = event["fields"]
        is_adjustment = source == "adjustments.jsonl"

        account = self.ref.accounts.get(trim(fields["account_id"]))
        if account is None:
            return None

        tariff_code = trim(fields["tariff_code"])
        tariff = self.ref.tariffs.get(tariff_code)
        if tariff is None:
            return None

        if is_adjustment:
            substation = None
            postal_code = account["postal_code"]
            offset = 0
            quantity = 0
        else:
            substation = trim(fields["substation"])
            fleet = self.ref.substations.get(substation)
            if fleet is None:
                return None
            postal_code = fleet["postal_code"]
            offset = fleet["tz_offset_minutes"]
            quantity = parse_uint(fields["quantity"])
            if quantity is None:
                return None

        zone = self.ref.zone_record(postal_code)
        if zone is None:
            return None

        currency = trim(fields["currency"]).upper() or zone["default_currency"]

        local = parse_ts(fields["read_ts"], zulu=is_adjustment)
        if local is None:
            return None
        instant = local if is_adjustment else local - timedelta(minutes=offset)
        settlement_date = instant.date().isoformat()

        rate, exact = self.ref.rate(currency, settlement_date)
        if rate is None:
            return None

        if is_adjustment:
            channel_group = self.policy["adjustment_channel_group"]
        else:
            channel_group = self.ref.channels.get(fold(fields["intake_terminal"]))
            if channel_group is None:
                return None

        kind, gross = self.gross(event, quantity)
        if gross is None:
            return None

        product = gross * rate * 100
        if kind == "charge":
            net_units = quantity
        elif kind == "rebate":
            net_units = -quantity
        else:
            net_units = 0

        return {
            "record": {
                "event_id": event["event_id"],
                "settlement_date": settlement_date,
                "utc_instant": instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "billing_period": self.ref.billing_period(settlement_date),
                "account_id": account["account_id"],
                "segment": account["segment"],
                "region": self.ref.region_of_zone[zone["zone"]],
                "tariff_code": tariff_code,
                "category": tariff["category"],
                "kind": kind,
                "quantity": quantity,
                "settled_usd_cents": self.rounder.quantize(
                    product, self.policy["money_scale"]
                ),
                "currency": currency,
                "source": source,
                "channel_group": channel_group,
                "substation": substation,
            },
            "net_units": net_units,
            "instant": instant,
            "carry_forward": not exact,
            "local_date": local.date().isoformat(),
            "half_cent": Rounder.is_half(product, self.policy["money_scale"]),
            "product_negative": product < 0,
            "read_event_id": (
                trim(fields["read_event_id"]) if source == "rebates.tsv" else ""
            ),
        }

    def gross(self, event, quantity):
        source = event["source"]
        fields = event["fields"]
        if source == "meter_reads.csv":
            unit_rate = parse_decimal(fields["unit_rate"])
            if unit_rate is None:
                return None, None
            return "charge", quantity * unit_rate
        if source == "rebates.tsv":
            amount = parse_decimal(fields["rebate_amount"])
            if amount is None:
                return None, None
            return "rebate", -abs(amount)
        if source == "adjustments.jsonl":
            kind = fold(fields["kind"])
            if kind not in ("surcharge", "waiver"):
                return None, None
            minor = self.amount_minor(
                fields["amount_minor"], "amount_minor" in event["amended"]
            )
            if minor is None:
                return None, None
            return kind, Fraction(minor, 100)
        kind = fold(fields["kind"])
        if kind not in ("charge", "rebate", "surcharge", "waiver"):
            return None, None
        amount = parse_decimal(fields["amount"])
        if amount is None:
            return None, None
        return kind, (abs(amount) if kind in ("charge", "surcharge") else -abs(amount))

    @staticmethod
    def amount_minor(value, was_amended):
        if was_amended:
            # An amendment delivers text, which must still read as a JSON integer.
            try:
                parsed = json.loads(value.strip())
            except (ValueError, TypeError, AttributeError):
                return None
        else:
            parsed = value
        if isinstance(parsed, bool) or not isinstance(parsed, int):
            return None
        return parsed


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------

def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")


def sums(pairs):
    out = defaultdict(int)
    for key, cents in pairs:
        out[key] += cents
    return dict(out)


def bucket(label_key, label, members, blocked_count, extra=None):
    records = [item["record"] for item in members]
    payload = {
        label_key: label,
        "event_count": len(records),
        "total_usd_cents": sum(r["settled_usd_cents"] for r in records),
        "net_units": sum(item["net_units"] for item in members),
        "blocked_count": blocked_count,
        "accounts": sorted({r["account_id"] for r in records}),
        "by_kind": sums((r["kind"], r["settled_usd_cents"]) for r in records),
        "by_category": sums((r["category"], r["settled_usd_cents"]) for r in records),
    }
    if extra:
        payload.update(extra)
    return payload


# --------------------------------------------------------------------------
# pipeline
# --------------------------------------------------------------------------

def run(data_dir, out_dir):
    policy = read_policy(os.path.join(data_dir, "policy.ini"))
    rounder = Rounder(policy["mode"])
    ref = Reference(data_dir, policy)

    events, legacy_malformed = load_events(data_dir)
    amendments = load_amendments(os.path.join(data_dir, "audit_trail.log"))

    by_id = {event["event_id"]: event for event in events}
    meter_read_ids = {
        event["event_id"] for event in events if event["source"] == "meter_reads.csv"
    }

    unmatched_targets = set()
    amended_events = set()
    for (target, field), value in amendments.items():
        event = by_id.get(target)
        if event is None:
            unmatched_targets.add(target)
            continue
        if field == "event_id" or field not in COLUMNS[event["source"]]:
            continue
        event["fields"][field] = value
        event["amended"].add(field)
        amended_events.add(target)

    settler = Settler(ref, policy, rounder)
    skipped_by_source = Counter({"legacy_ledger.txt": legacy_malformed})
    orphan_ids = set()
    malformed_reads = set()
    candidates = []

    for event in events:
        if event["source"] == "rebates.tsv":
            link = trim(event["fields"]["read_event_id"])
            if link and link not in meter_read_ids:
                orphan_ids.add(event["event_id"])
                continue
        settled = settler.settle(event)
        if settled is None:
            skipped_by_source[event["source"]] += 1
            if event["source"] == "meter_reads.csv":
                malformed_reads.add(event["event_id"])
            continue
        candidates.append(settled)

    # opening deposit ladder
    balances = {}
    underfunded = 0
    for account_id in ref.account_order:
        account = ref.accounts[account_id]
        rate, _ = ref.rate(account["opening_currency"], policy["opening_rate_date"])
        if rate is None:
            raise ValueError("no opening rate for %s" % account["opening_currency"])
        opening = Fraction(account["opening_deposit_minor"], 100) * rate * 100
        cents = rounder.quantize(opening, policy["money_scale"])
        balances[account_id] = cents
        if cents < policy["minimums"][account["segment"]]:
            underfunded += 1

    per_account = defaultdict(list)
    for settled in candidates:
        per_account[settled["record"]["account_id"]].append(settled)

    accepted = []
    blocked = []
    withheld_value = 0
    withheld_count = 0
    suspended_accounts = set()
    gate_blocked_accounts = set()

    for account_id, items in per_account.items():
        items.sort(key=lambda item: (item["instant"], item["record"]["event_id"]))
        minimum = policy["minimums"][ref.accounts[account_id]["segment"]]
        strikes = 0
        suspended = False
        for item in items:
            cents = item["record"]["settled_usd_cents"]
            if suspended:
                blocked.append(item)
                gate_blocked_accounts.add(account_id)
                suspended_accounts.add(account_id)
                continue
            if cents >= 0 or balances[account_id] + cents >= minimum:
                balances[account_id] += cents
                accepted.append(item)
                continue
            strikes += 1
            withheld_value += cents
            withheld_count += 1
            blocked.append(item)
            gate_blocked_accounts.add(account_id)
            if strikes >= policy["strike_limit"]:
                suspended = True

    accepted.sort(key=lambda item: item["record"]["event_id"])
    records = [item["record"] for item in accepted]

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "normalized.jsonl"), "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    summary = {
        "event_count": len(records),
        "skipped_count": sum(skipped_by_source.values()),
        "blocked_count": len(blocked),
        "orphan_rebate_count": len(orphan_ids),
        "total_usd_cents": sum(r["settled_usd_cents"] for r in records),
        "net_units": sum(item["net_units"] for item in accepted),
        "deposit_closing_usd_cents": sum(balances[a] for a in ref.account_order),
        "by_region": sums((r["region"], r["settled_usd_cents"]) for r in records),
        "by_segment": sums((r["segment"], r["settled_usd_cents"]) for r in records),
        "by_kind": sums((r["kind"], r["settled_usd_cents"]) for r in records),
        "by_category": sums((r["category"], r["settled_usd_cents"]) for r in records),
        "by_channel_group": sums(
            (r["channel_group"], r["settled_usd_cents"]) for r in records
        ),
        "by_billing_period": sums(
            (r["billing_period"], r["settled_usd_cents"]) for r in records
        ),
        "by_source": sums((r["source"], r["settled_usd_cents"]) for r in records),
    }
    write_json(os.path.join(out_dir, "summary.json"), summary)

    present = [
        name for name in EVENT_FILES
        if os.path.isfile(os.path.join(data_dir, name))
    ]
    blocked_by_source = Counter(item["record"]["source"] for item in blocked)
    write_json(os.path.join(out_dir, "data_quality.json"), {
        "input_files": sorted(
            name for name in os.listdir(data_dir)
            if os.path.isfile(os.path.join(data_dir, name))
        ),
        "records_by_source": dict(Counter(r["source"] for r in records)),
        "skipped_by_source": {name: skipped_by_source.get(name, 0) for name in present},
        "blocked_by_source": {name: blocked_by_source.get(name, 0) for name in present},
        "skipped_count": summary["skipped_count"],
        "blocked_count": summary["blocked_count"],
        "orphan_rebate_count": summary["orphan_rebate_count"],
        "blocked_event_ids": sorted({item["record"]["event_id"] for item in blocked}),
        "orphan_rebate_event_ids": sorted(orphan_ids),
        "unmatched_amendment_targets": sorted(unmatched_targets),
    })

    stats = defaultdict(lambda: {"events": 0, "total": 0, "units": 0})
    for item in accepted:
        stat = stats[item["record"]["tariff_code"]]
        stat["events"] += 1
        stat["total"] += item["record"]["settled_usd_cents"]
        stat["units"] += item["net_units"]
    tariffs = []
    for code in ref.tariff_order:
        stat = stats.get(code, {"events": 0, "total": 0, "units": 0})
        volume = (
            stat["units"]
            * ref.tariffs[code]["unit_volume_m3"]
            * policy["litres_per_cubic_metre"]
        )
        tariffs.append({
            "tariff_code": code,
            "category": ref.tariffs[code]["category"],
            "event_count": stat["events"],
            "total_usd_cents": stat["total"],
            "net_units": stat["units"],
            "metered_capacity_litres": ref.fleet_capacity.get(code, 0),
            "service_threshold_litres": ref.fleet_threshold.get(code, 0),
            "net_volume_litres": rounder.quantize(volume, policy["volume_scale"]),
        })
    write_json(os.path.join(out_dir, "product_summary.json"), {"tariffs": tariffs})

    for region in sorted(set(ref.top_regions) | set(CANONICAL_REGIONS)):
        write_json(os.path.join(out_dir, "region_%s.json" % region), bucket(
            "region", region,
            [i for i in accepted if i["record"]["region"] == region],
            sum(1 for i in blocked if i["record"]["region"] == region),
        ))

    for segment in sorted(policy["minimums"]):
        write_json(os.path.join(out_dir, "segment_%s.json" % segment), bucket(
            "segment", segment,
            [i for i in accepted if i["record"]["segment"] == segment],
            sum(1 for i in blocked if i["record"]["segment"] == segment),
            {"minimum_deposit_usd_cents": policy["minimums"][segment]},
        ))

    carry = [item for item in accepted if item["carry_forward"]]
    halves = [item for item in accepted if item["half_cent"]]
    return {
        "withheld_value_usd_cents": withheld_value,
        "suspended_accounts": len(suspended_accounts),
        "carry_forward_rate_events": len(carry),
        "day_shift_events": sum(
            1 for item in accepted
            if item["record"]["settlement_date"] != item["local_date"]
        ),
        "amended_events": len(amended_events),
        "half_cent_events": len(halves),
        "underfunded_accounts": underfunded,
        "unlisted_capacity_litres": sum(
            capacity for tariff, capacity in ref.fleet_rows
            if tariff not in ref.tariffs
        ),
        "stale_link_rebates": sum(
            1 for item in accepted
            if item["record"]["source"] == "rebates.tsv"
            and item["read_event_id"] in malformed_reads
        ),
        "withheld_event_count": withheld_count,
        "gate_blocked_accounts": len(gate_blocked_accounts),
        "carry_forward_rate_currencies": len(
            {item["record"]["currency"] for item in carry}
        ),
        "half_cent_negative_events": sum(1 for i in halves if i["product_negative"]),
    }


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py <DATA_DIR> <OUT_DIR>\n")
        return 2
    closing = run(argv[1], argv[2])
    for key in sorted(closing):
        print("%s=%s" % (key, closing[key]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
