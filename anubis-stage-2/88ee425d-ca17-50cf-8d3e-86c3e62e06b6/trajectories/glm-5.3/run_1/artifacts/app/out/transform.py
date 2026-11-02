#!/usr/bin/env python3
"""TY31 reserve-gated dispensing clearing run.

Rebuilds the clearing pipeline described by the written contract shipped in the
input directory (``schema.md``): reads the four claim files, the reference
tables and the policy file, and writes the normalized claim stream plus every
aggregate artifact into an output directory.

Usage:
    python3 transform.py <DATA_DIR> <OUT_DIR>

Standard library only; no network access, no subprocesses.
"""

import configparser
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext

CLAIM_SOURCES = ("dispenses.csv", "recoveries.tsv", "assessments.jsonl", "archive.txt")

# The contract fixes these labels: one file per top level region and per segment
# is written on every run, including a bucket that drew nothing.
CANONICAL_REGIONS = ("central", "east", "north", "south", "west")
CANONICAL_SEGMENTS = ("consumer", "corporate", "enterprise", "smb")

COLUMNS = {
    "dispenses.csv": ("claim_id", "booked_ts", "member_id", "item_code", "depot",
                      "quantity", "unit_price", "currency", "gateway"),
    "recoveries.tsv": ("claim_id", "booked_ts", "member_id", "item_code", "depot",
                       "quantity", "recovered_amount", "currency", "gateway",
                       "dispense_claim_id"),
    "assessments.jsonl": ("claim_id", "booked_ts", "member_id", "item_code", "kind",
                          "amount_minor", "currency", "note"),
    "archive.txt": ("claim_id", "booked_ts", "member_id", "item_code", "depot", "kind",
                    "quantity", "amount", "currency", "gateway", "memo"),
}

DISPENSE = "dispense"
RECOVERY = "recovery"
LEVY = "levy"
REBATE = "rebate"
SIGNED_KINDS = (DISPENSE, RECOVERY, LEVY, REBATE)

TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})$")
TS_Z_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$")
QTY_RE = re.compile(r"^[0-9]+$")
MONEY_RE = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$")
INT_RE = re.compile(r"^[+-]?[0-9]+$")
AMEND_RE = re.compile(r"^amendment\s+target=(\S*)\s+field=(\S*)\s+value=(.*)$", re.S)

ROUNDING_MODES = {
    "half_up": ROUND_HALF_UP,
    "half_down": ROUND_HALF_DOWN,
    "half_even": ROUND_HALF_EVEN,
}


class Malformed(Exception):
    """A claim field failed to parse or a lookup in its chain missed."""


# --------------------------------------------------------------- small helpers

def read_text(path):
    """File text as the contract encodes it: latin-1 for archive.txt."""
    encoding = "latin-1" if os.path.basename(path) == "archive.txt" else "utf-8"
    with open(path, "r", encoding=encoding, newline="") as fh:
        return fh.read()


def read_delimited(path, delimiter):
    """Rows of a delimited file as dicts of raw strings.

    A short row contributes empty values for the columns it lacks and extra
    fields are dropped, so a ragged row surfaces later as a malformed claim
    rather than aborting the run.
    """
    rows = list(csv.reader(read_text(path).splitlines(), delimiter=delimiter))
    if not rows:
        return [], []
    header = [h.strip() for h in rows[0]]
    out = []
    for row in rows[1:]:
        values = list(row[:len(header)])
        values.extend([""] * (len(header) - len(values)))
        out.append(dict(zip(header, values)))
    return header, out


def fold(text):
    return text.strip().lower()


def fold_currency(text):
    return text.strip().upper()


def field_of(row, column):
    """A field value trimmed of leading and trailing whitespace."""
    value = row.get(column)
    if isinstance(value, bool):
        return str(value).strip()
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return str(value).strip()


def parse_ts(text):
    """A local wall-clock timestamp naming a real calendar day."""
    match = TS_RE.match(text)
    if not match:
        raise Malformed("booked_ts")
    try:
        return datetime(*(int(match.group(i)) for i in range(1, 7)))
    except ValueError:
        raise Malformed("booked_ts")


def parse_ts_utc(text):
    """A trailing-Z timestamp that is already UTC."""
    match = TS_Z_RE.match(text)
    if not match:
        raise Malformed("booked_ts")
    try:
        return datetime(*(int(match.group(i)) for i in range(1, 7)))
    except ValueError:
        raise Malformed("booked_ts")


def parse_date(text):
    return parse_ts(text + "T00:00:00").date()


def parse_decimal(text):
    text = text.strip()
    if not MONEY_RE.match(text):
        raise Malformed("money")
    return Decimal(text)


def parse_integer(text):
    text = text.strip()
    if not INT_RE.match(text):
        raise Malformed("integer")
    return int(text)


# ------------------------------------------------------------------ references

class Reference(object):
    """Every lookup table the clearing chain crosses."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.members = {}
        self.member_order = []
        self.prefix_zone = {}
        self.zone_parent = {}
        self.region_of_zone = {}
        self.depot_info = {}
        self.stock = defaultdict(lambda: [0, 0])
        self.uncatalogued_grams = 0
        self.gateway_lane = {}
        self.items = {}
        self.rates = defaultdict(list)
        self.periods = []
        self.top_regions = set()
        self._load()

    def path(self, name):
        return os.path.join(self.data_dir, name)

    def exists(self, name):
        return os.path.isfile(self.path(name))

    def _load(self):
        if self.exists("members.csv"):
            _, rows = read_delimited(self.path("members.csv"), ",")
            for index, row in enumerate(rows):
                member_id = field_of(row, "member_id")
                if member_id not in self.members:
                    self.member_order.append(member_id)
                    self.members[member_id] = (field_of(row, "updated_at"), index, row)
                else:
                    stamp = field_of(row, "updated_at")
                    current = self.members[member_id]
                    if (stamp, index) > (current[0], current[1]):
                        self.members[member_id] = (stamp, index, row)

        if self.exists("zones.csv"):
            _, rows = read_delimited(self.path("zones.csv"), ",")
            for row in rows:
                prefix = field_of(row, "postal_prefix")
                zone = fold(field_of(row, "zone"))
                parent = fold(field_of(row, "parent_zone"))
                self.prefix_zone[prefix] = (zone, fold_currency(field_of(row, "default_currency")))
                self.zone_parent[zone] = parent
            for zone, parent in self.zone_parent.items():
                if not parent:
                    self.top_regions.add(zone)
            for zone in self.zone_parent:
                self.region_of_zone[zone] = self._top_ancestor(zone)

        if self.exists("item_catalog.csv"):
            _, rows = read_delimited(self.path("item_catalog.csv"), ",")
            for row in rows:
                code = field_of(row, "item_code")
                self.items[code] = {
                    "category": fold(field_of(row, "category")),
                    "pack_mass_kg": parse_decimal(field_of(row, "pack_mass_kg")),
                }
        catalogued = set(self.items)

        if self.exists("stock_ledger.csv"):
            _, rows = read_delimited(self.path("stock_ledger.csv"), ",")
            for row in rows:
                depot = field_of(row, "depot")
                item = field_of(row, "item_code")
                on_hand = parse_integer(field_of(row, "on_hand_grams"))
                reorder = parse_integer(field_of(row, "reorder_point_grams"))
                if depot not in self.depot_info:
                    self.depot_info[depot] = (field_of(row, "postal_code"),
                                               parse_integer(field_of(row, "tz_offset_minutes")))
                entry = self.stock[item]
                entry[0] += on_hand
                entry[1] += reorder
                if item not in catalogued:
                    self.uncatalogued_grams += on_hand

        if self.exists("gateways.csv"):
            _, rows = read_delimited(self.path("gateways.csv"), ",")
            for row in rows:
                self.gateway_lane[fold(field_of(row, "gateway"))] = fold(field_of(row, "lane"))

        if self.exists("fx_rates.csv"):
            _, rows = read_delimited(self.path("fx_rates.csv"), ",")
            for row in rows:
                currency = fold_currency(field_of(row, "currency"))
                self.rates[currency].append(
                    (parse_date(field_of(row, "rate_date")),
                     parse_decimal(field_of(row, "usd_rate"))))
            for currency in self.rates:
                self.rates[currency].sort(key=lambda entry: entry[0])

        if self.exists("tariff_calendar.json"):
            with open(self.path("tariff_calendar.json"), "r", encoding="utf-8") as fh:
                calendar = json.load(fh)
            for period in calendar.get("periods", []):
                self.periods.append((parse_date(period["start"]),
                                     parse_date(period["end"]),
                                     period["period"]))
            self.periods.sort(key=lambda entry: (entry[0], entry[1], entry[2]))

    def _top_ancestor(self, zone):
        seen = set()
        current = zone
        while True:
            if current in seen:
                return None
            seen.add(current)
            parent = self.zone_parent.get(current)
            if parent is None:
                return None
            if not parent:
                return current
            current = parent

    def member(self, member_id):
        entry = self.members.get(member_id)
        if entry is None:
            raise Malformed("unknown member")
        return entry[2]

    def zone_of_prefix(self, prefix):
        entry = self.prefix_zone.get(prefix)
        if entry is None:
            raise Malformed("unknown postal prefix")
        region = self.region_of_zone.get(entry[0])
        if region is None:
            raise Malformed("unknown postal prefix")
        return region, entry[1]

    def depot(self, depot):
        entry = self.depot_info.get(depot)
        if entry is None:
            raise Malformed("unknown depot")
        return entry

    def lane(self, gateway):
        lane = self.gateway_lane.get(fold(gateway))
        if lane is None:
            raise Malformed("unknown gateway")
        return lane

    def item(self, item_code):
        entry = self.items.get(item_code)
        if entry is None:
            raise Malformed("unknown item")
        return entry

    def rate(self, currency, clearing_date):
        rows = self.rates.get(currency)
        applicable = None
        if rows:
            for date, rate in rows:
                if date <= clearing_date:
                    applicable = (date, rate)
                else:
                    break
        if applicable is None:
            raise Malformed("no usable rate")
        return applicable

    def period(self, clearing_date):
        for start, end, label in self.periods:
            if start <= clearing_date <= end:
                return label
        return None


# ---------------------------------------------------------------- claim parsing

class Claim(object):
    __slots__ = ("claim_id", "source", "amount", "quantity", "kind", "member_id",
                 "item_code", "depot", "gateway", "currency_field", "booked_ts", "link",
                 "booked_local_date")


def parse_quantity(text):
    if not QTY_RE.match(text):
        raise Malformed("quantity")
    return int(text)


def build_tabular_claim(source, row):
    claim = Claim()
    claim.claim_id = field_of(row, "claim_id")
    claim.kind = DISPENSE if source == "dispenses.csv" else RECOVERY
    claim.member_id = field_of(row, "member_id")
    claim.item_code = field_of(row, "item_code")
    claim.depot = field_of(row, "depot")
    claim.gateway = field_of(row, "gateway")
    claim.currency_field = field_of(row, "currency")
    claim.booked_ts = field_of(row, "booked_ts")
    claim.booked_local_date = parse_ts(claim.booked_ts)
    claim.quantity = parse_quantity(field_of(row, "quantity"))
    if source == "dispenses.csv":
        unit_price = parse_decimal(field_of(row, "unit_price"))
        claim.amount = Decimal(claim.quantity) * unit_price
    else:
        claim.amount = -abs(parse_decimal(field_of(row, "recovered_amount")))
    claim.link = field_of(row, "dispense_claim_id") if source == "recoveries.tsv" else ""
    return claim


def build_archive_claim(row):
    claim = Claim()
    claim.claim_id = field_of(row, "claim_id")
    kind = fold(field_of(row, "kind"))
    if kind not in SIGNED_KINDS:
        raise Malformed("archive kind")
    claim.kind = kind
    claim.member_id = field_of(row, "member_id")
    claim.item_code = field_of(row, "item_code")
    claim.depot = field_of(row, "depot")
    claim.gateway = field_of(row, "gateway")
    claim.currency_field = field_of(row, "currency")
    claim.booked_ts = field_of(row, "booked_ts")
    claim.booked_local_date = parse_ts(claim.booked_ts)
    claim.quantity = parse_quantity(field_of(row, "quantity"))
    amount = abs(parse_decimal(field_of(row, "amount")))
    claim.amount = amount if kind in (DISPENSE, LEVY) else -amount
    claim.link = ""
    return claim


def build_assessment_claim(obj, amended):
    """An assessment row with its amendments already applied.

    ``amount_minor`` must be a JSON integer in the file itself, but an amendment
    replaces the field with text before any parsing happens, so an amended
    ``amount_minor`` is read as an integer written in that text.
    """
    claim = Claim()
    claim.claim_id = field_of(obj, "claim_id")
    kind = fold(field_of(obj, "kind"))
    if kind not in (LEVY, REBATE):
        raise Malformed("assessment kind")
    claim.kind = kind
    claim.member_id = field_of(obj, "member_id")
    claim.item_code = field_of(obj, "item_code")
    claim.depot = ""
    claim.gateway = ""
    claim.currency_field = field_of(obj, "currency")
    booked = field_of(obj, "booked_ts")
    utc = parse_ts_utc(booked)
    claim.booked_ts = booked
    claim.booked_local_date = utc
    if "amount_minor" in amended:
        minor = parse_integer(field_of(obj, "amount_minor"))
    else:
        raw = obj.get("amount_minor") if isinstance(obj, dict) else None
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise Malformed("amount_minor")
        minor = raw
    claim.amount = Decimal(minor) / Decimal(100)
    claim.quantity = 0
    claim.link = ""
    return claim


# ------------------------------------------------------------------- amendments

def load_amendments(data_dir, claim_source):
    """Applicable amendments and unmatched targets, in one pass over the log.

    An amendment applies when its target names a claim, its field is a column of
    that claim's own file and the field is not the claim id itself.  When several
    amendments name the same claim and field, the greatest utc_ts wins and a
    shared instant is broken by later file order.  A target that names no claim
    id in any claim file is unmatched and reported.
    """
    path = os.path.join(data_dir, "amendments.log")
    if not os.path.isfile(path):
        return {}, set()
    best = {}
    unmatched = set()
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for order, line in enumerate(fh):
            line = line.rstrip("\n")
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            message = parts[2]
            match = AMEND_RE.match(message)
            if not match:
                continue
            target, column, value = match.group(1), match.group(2), match.group(3).strip()
            if not target:
                continue
            source = claim_source.get(target)
            if source is None:
                unmatched.add(target)
                continue
            if column == "claim_id" or column not in COLUMNS[source]:
                continue
            stamp = parts[0]
            key = (target, column)
            current = best.get(key)
            if current is None or (stamp, order) > current[0]:
                best[key] = ((stamp, order), value)
    applied = defaultdict(dict)
    for (target, column), (_, value) in best.items():
        applied[target][column] = value
    return dict(applied), unmatched


def read_claim_rows(data_dir):
    """Raw rows of every claim file present, keyed by source name."""
    rows_by_source = {}
    if os.path.isfile(os.path.join(data_dir, "dispenses.csv")):
        rows_by_source["dispenses.csv"] = read_delimited(
            os.path.join(data_dir, "dispenses.csv"), ",")[1]
    if os.path.isfile(os.path.join(data_dir, "recoveries.tsv")):
        rows_by_source["recoveries.tsv"] = read_delimited(
            os.path.join(data_dir, "recoveries.tsv"), "\t")[1]
    if os.path.isfile(os.path.join(data_dir, "assessments.jsonl")):
        assessments = []
        for line in read_text(os.path.join(data_dir, "assessments.jsonl")).splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                obj = {"__parse_error__": line}
            assessments.append(obj)
        rows_by_source["assessments.jsonl"] = assessments
    if os.path.isfile(os.path.join(data_dir, "archive.txt")):
        archive = []
        for line in read_text(os.path.join(data_dir, "archive.txt")).splitlines():
            stripped = line.strip()
            if not stripped or stripped[0] == "#":
                continue
            archive.append(line.split("|"))
        rows_by_source["archive.txt"] = archive
    return rows_by_source


def build_claim(source, row, amended=None):
    amended = amended or {}
    if source == "assessments.jsonl":
        if not isinstance(row, dict) or "__parse_error__" in row:
            return None
        return build_assessment_claim(row, amended)
    if source == "archive.txt":
        if len(row) != 11:
            return None
        return build_archive_claim(dict(zip(COLUMNS["archive.txt"], row)))
    return build_tabular_claim(source, row)


def claim_id_of(source, row):
    """The claim id a raw row names, before any parsing of its other fields."""
    if source == "archive.txt":
        return row[0].strip() if row else ""
    if source == "assessments.jsonl":
        return field_of(row, "claim_id") if isinstance(row, dict) else ""
    return field_of(row, "claim_id")


def parse_with_amendments(source, row, amended):
    """One claim with every amendment that names it applied before parsing."""
    try:
        if not amended:
            return build_claim(source, row)
        if source == "assessments.jsonl":
            if not isinstance(row, dict) or "__parse_error__" in row:
                return None
            patched = dict(row)
            patched.update(amended)
            return build_assessment_claim(patched, amended)
        if source == "archive.txt":
            if len(row) != 11:
                return None
            patched = dict(zip(COLUMNS["archive.txt"], row))
            patched.update(amended)
            return build_archive_claim(patched)
        patched = dict(row)
        patched.update(amended)
        return build_tabular_claim(source, patched)
    except (Malformed, KeyError, TypeError, ValueError, IndexError, ArithmeticError):
        return None


# ---------------------------------------------------------------------- policy

class Policy(object):
    def __init__(self, data_dir):
        parser = configparser.ConfigParser()
        parser.read(os.path.join(data_dir, "policy.ini"))

        def get(section, option, fallback=None):
            if parser.has_option(section, option):
                return parser.get(section, option).strip()
            return fallback

        self.opening_rate_date = get("ladder", "opening_rate_date", "")
        self.money_scale = int(get("rounding", "money_scale", "0"))
        self.mass_scale = int(get("rounding", "mass_scale", "0"))
        self.rounding_mode = get("rounding", "mode", "half_up")
        self.grams_per_kilogram = get("mass", "grams_per_kilogram", "1000")
        self.unassigned_period = get("labels", "unassigned_period", "unscheduled")
        self.assessment_lane = get("labels", "assessment_lane", "assessment")
        self.floors = {}
        if parser.has_section("reserve"):
            for key, value in parser.items("reserve"):
                if key.startswith("floor_") and key.endswith("_usd_cents"):
                    segment = key[len("floor_"):-len("_usd_cents")]
                    self.floors[segment] = parse_integer(value.strip())
        self.segments = set(self.floors)
        self.money_quantum = Decimal(1).scaleb(-self.money_scale)
        self.mass_quantum = Decimal(1).scaleb(-self.mass_scale)
        self.money_rounding = ROUNDING_MODES.get(self.rounding_mode, ROUND_HALF_UP)


# --------------------------------------------------------------------- clearer

class Clearer(object):
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.policy = Policy(data_dir)
        self.reference = Reference(data_dir)
        self.grams_per_kilogram = parse_decimal(self.policy.grams_per_kilogram)

    def usd_cents(self, amount, rate):
        """Gross amount x rate x 100, one exact decimal expression, quantized once.

        Returns the whole cents and whether the product sat at exactly half a
        cent before quantizing.
        """
        with localcontext() as ctx:
            ctx.prec = 80
            product = amount * rate * Decimal(100)
            half_cent = (product.copy_abs() % Decimal(1)) == Decimal("0.5")
            cents = product.quantize(self.policy.money_quantum,
                                     rounding=self.policy.money_rounding)
        return int(cents), half_cent

    def mass_grams(self, units, pack_mass_kg):
        """Net units x pack mass x grams per kilogram, quantized once."""
        with localcontext() as ctx:
            ctx.prec = 80
            product = Decimal(units) * pack_mass_kg * self.grams_per_kilogram
            return int(product.quantize(self.policy.mass_quantum,
                                        rounding=self.policy.money_rounding))

    def opening_reserve_cents(self, member_row):
        minor = parse_integer(field_of(member_row, "opening_reserve_minor"))
        currency = fold_currency(field_of(member_row, "opening_currency"))
        _, rate = self.reference.rate(
            currency, parse_date(self.policy.opening_rate_date))
        cents, _ = self.usd_cents(Decimal(minor) / Decimal(100), rate)
        return cents

    def clear(self, claim):
        """Steps 2 through 10 of the chain; returns (record, diagnostics)."""
        reference = self.reference
        policy = self.policy

        member = reference.member(claim.member_id)
        segment = fold(field_of(member, "segment"))
        item = reference.item(claim.item_code)

        if claim.depot:
            postal_code, tz_minutes = reference.depot(claim.depot)
            utc = claim.booked_local_date - timedelta(minutes=tz_minutes)
        else:
            postal_code = field_of(member, "postal_code")
            if not postal_code:
                raise Malformed("member postal code")
            utc = claim.booked_local_date

        prefix = postal_code.split("-")[0].strip()
        region, default_currency = reference.zone_of_prefix(prefix)

        if claim.currency_field:
            currency = fold_currency(claim.currency_field)
        else:
            currency = fold_currency(default_currency)

        clearing_date = utc.date()
        rate_date, rate = reference.rate(currency, clearing_date)
        period = reference.period(clearing_date)
        if period is None:
            period = policy.unassigned_period

        lane = reference.lane(claim.gateway) if claim.depot else policy.assessment_lane
        cents, half_cent = self.usd_cents(claim.amount, rate)

        record = {
            "claim_id": claim.claim_id,
            "clearing_date": clearing_date.isoformat(),
            "utc_instant": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tariff_period": period,
            "member_id": claim.member_id,
            "segment": segment,
            "region": region,
            "item_code": claim.item_code,
            "category": item["category"],
            "kind": claim.kind,
            "quantity": claim.quantity,
            "cleared_usd_cents": cents,
            "currency": currency,
            "source": claim.source,
            "lane": lane,
            "depot": claim.depot or None,
        }
        diagnostics = {
            "carry_forward": rate_date != clearing_date,
            "half_cent": half_cent,
            "day_shift": claim.booked_local_date.date() != clearing_date,
            "utc": utc,
        }
        return record, diagnostics


def net_units_of(record):
    if record["kind"] == DISPENSE:
        return record["quantity"]
    if record["kind"] == RECOVERY:
        return -record["quantity"]
    return 0


# -------------------------------------------------------------------- pipeline

def run(data_dir, out_dir):
    clearer = Clearer(data_dir)
    reference = clearer.reference
    policy = clearer.policy

    rows_by_source = read_claim_rows(data_dir)

    # Claim ids present in each file, in file order.
    claim_source = {}
    for source in CLAIM_SOURCES:
        for row in rows_by_source.get(source, []):
            claim_id = claim_id_of(source, row)
            if claim_id:
                claim_source.setdefault(claim_id, source)

    amendments, unmatched = load_amendments(data_dir, claim_source)
    amended_events = len(amendments)

    # Orphan recoveries: judged on the amended link before any other parsing.
    dispense_ids = set()
    for row in rows_by_source.get("dispenses.csv", []):
        claim_id = field_of(row, "claim_id")
        if claim_id:
            dispense_ids.add(claim_id)

    orphan_ids = set()
    for row in rows_by_source.get("recoveries.tsv", []):
        claim_id = field_of(row, "claim_id")
        patched = dict(row)
        patched.update(amendments.get(claim_id, {}))
        link = field_of(patched, "dispense_claim_id")
        if link and link not in dispense_ids:
            orphan_ids.add(claim_id)

    # Parse every claim, applying its amendments first.
    claims = []
    skipped_by_source = defaultdict(int)
    malformed_ids = defaultdict(list)
    for source in CLAIM_SOURCES:
        for row in rows_by_source.get(source, []):
            claim_id = claim_id_of(source, row)
            if source == "recoveries.tsv" and claim_id in orphan_ids:
                continue
            claim = parse_with_amendments(source, row, amendments.get(claim_id, {}))
            if claim is None:
                skipped_by_source[source] += 1
                malformed_ids[source].append(claim_id)
            else:
                claim.source = source
                claims.append(claim)

    # Clearing chain for every claim that survived parsing.
    resolved = []
    for claim in claims:
        try:
            record, diagnostics = clearer.clear(claim)
        except Malformed:
            skipped_by_source[claim.source] += 1
            malformed_ids[claim.source].append(claim.claim_id)
            continue
        except (KeyError, TypeError, ValueError, IndexError, ArithmeticError):
            skipped_by_source[claim.source] += 1
            malformed_ids[claim.source].append(claim.claim_id)
            continue
        resolved.append((claim, record, diagnostics))

    # The reserve ladder.
    by_member = defaultdict(list)
    for claim, record, diagnostics in resolved:
        by_member[record["member_id"]].append((claim, record, diagnostics))

    cleared = []
    blocked = []
    closing_reserves = {}
    underwater_members = 0
    for member_id in reference.member_order:
        _, _, member_row = reference.members[member_id]
        segment = fold(field_of(member_row, "segment"))
        floor = policy.floors.get(segment)
        reserve = clearer.opening_reserve_cents(member_row)
        if floor is not None and reserve < floor:
            underwater_members += 1
        entries = sorted(by_member.get(member_id, []),
                         key=lambda entry: (entry[2]["utc"], entry[1]["claim_id"]))
        for claim, record, diagnostics in entries:
            cents = record["cleared_usd_cents"]
            if cents >= 0 or (floor is not None and reserve + cents >= floor):
                reserve += cents
                cleared.append((claim, record, diagnostics))
            else:
                blocked.append((claim, record, diagnostics))
        closing_reserves[member_id] = reserve

    artifacts = build_artifacts(clearer, cleared, blocked, orphan_ids,
                                skipped_by_source, malformed_ids, closing_reserves,
                                rows_by_source, unmatched, amended_events,
                                underwater_members)
    write_artifacts(out_dir, artifacts)
    return artifacts


def build_artifacts(clearer, cleared, blocked, orphan_ids,
                    skipped_by_source, malformed_ids, closing_reserves,
                    rows_by_source, unmatched, amended_events,
                    underwater_members):
    reference = clearer.reference
    policy = clearer.policy

    present_sources = [s for s in CLAIM_SOURCES
                      if s in rows_by_source or skipped_by_source.get(s)]

    # ---- summary.json
    by_region = defaultdict(int)
    by_segment = defaultdict(int)
    by_kind = defaultdict(int)
    by_category = defaultdict(int)
    by_lane = defaultdict(int)
    by_period = defaultdict(int)
    by_source = defaultdict(int)
    total_cents = 0
    total_units = 0
    carry_forward = 0
    day_shift = 0
    half_cent = 0
    for claim, record, diagnostics in cleared:
        cents = record["cleared_usd_cents"]
        total_cents += cents
        total_units += net_units_of(record)
        by_region[record["region"]] += cents
        by_segment[record["segment"]] += cents
        by_kind[record["kind"]] += cents
        by_category[record["category"]] += cents
        by_lane[record["lane"]] += cents
        by_period[record["tariff_period"]] += cents
        by_source[record["source"]] += cents
        if diagnostics["carry_forward"]:
            carry_forward += 1
        if diagnostics["day_shift"]:
            day_shift += 1
        if diagnostics["half_cent"]:
            half_cent += 1

    records_by_source = defaultdict(int)
    for _, record, _ in cleared:
        records_by_source[record["source"]] += 1

    summary = {
        "event_count": len(cleared),
        "skipped_count": sum(skipped_by_source.values()),
        "blocked_count": len(blocked),
        "orphan_recovery_count": len(orphan_ids),
        "total_usd_cents": total_cents,
        "net_units": total_units,
        "reserve_closing_usd_cents": sum(closing_reserves.values()),
        "by_region": dict(sorted(by_region.items())),
        "by_segment": dict(sorted(by_segment.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_lane": dict(sorted(by_lane.items())),
        "by_tariff_period": dict(sorted(by_period.items())),
        "by_source": dict(sorted(by_source.items())),
    }

    # ---- data_quality.json
    blocked_by_source = defaultdict(int)
    for _, record, _ in blocked:
        blocked_by_source[record["source"]] += 1

    data_quality = {
        "input_files": sorted(name for name in os.listdir(clearer.data_dir)
                              if os.path.isfile(os.path.join(clearer.data_dir, name))),
        "records_by_source": dict(sorted(records_by_source.items())),
        "skipped_by_source": dict((s, skipped_by_source.get(s, 0))
                                  for s in present_sources),
        "blocked_by_source": dict((s, blocked_by_source.get(s, 0))
                                  for s in present_sources),
        "skipped_count": sum(skipped_by_source.values()),
        "blocked_count": len(blocked),
        "orphan_recovery_count": len(orphan_ids),
        "blocked_claim_ids": sorted({r["claim_id"] for _, r, _ in blocked}),
        "orphan_recovery_claim_ids": sorted(orphan_ids),
        "unmatched_amendment_targets": sorted(unmatched),
    }

    # ---- product_summary.json
    products = []
    per_item_cents = defaultdict(int)
    per_item_units = defaultdict(int)
    per_item_events = defaultdict(int)
    for _, record, _ in cleared:
        per_item_cents[record["item_code"]] += record["cleared_usd_cents"]
        per_item_units[record["item_code"]] += net_units_of(record)
        per_item_events[record["item_code"]] += 1
    for item_code in sorted(reference.items):
        category = reference.items[item_code]["category"]
        on_hand, reorder = reference.stock.get(item_code, [0, 0])
        units = per_item_units.get(item_code, 0)
        products.append({
            "item_code": item_code,
            "category": category,
            "event_count": per_item_events.get(item_code, 0),
            "total_usd_cents": per_item_cents.get(item_code, 0),
            "net_units": units,
            "on_hand_grams": on_hand,
            "reorder_point_grams": reorder,
            "net_mass_grams": clearer.mass_grams(
                units, reference.items[item_code]["pack_mass_kg"]),
        })

    # ---- region and segment roll-ups
    regions = sorted(set(CANONICAL_REGIONS) | reference.top_regions |
                      {reference.region_of_zone[entry[0]]
                       for entry in reference.prefix_zone.values()
                       if reference.region_of_zone.get(entry[0])})
    segments = sorted(set(CANONICAL_SEGMENTS) | policy.segments |
                      {r["segment"] for _, r, _ in cleared} |
                      {r["segment"] for _, r, _ in blocked})

    region_artifacts = {}
    for region in regions:
        members = sorted({r["member_id"] for _, r, _ in cleared if r["region"] == region})
        cents = sum(r["cleared_usd_cents"] for _, r, _ in cleared if r["region"] == region)
        units = sum(net_units_of(r) for _, r, _ in cleared if r["region"] == region)
        events = sum(1 for _, r, _ in cleared if r["region"] == region)
        blocked_count = sum(1 for _, r, _ in blocked if r["region"] == region)
        kinds = defaultdict(int)
        categories = defaultdict(int)
        for _, r, _ in cleared:
            if r["region"] == region:
                kinds[r["kind"]] += r["cleared_usd_cents"]
                categories[r["category"]] += r["cleared_usd_cents"]
        region_artifacts["region_%s.json" % region] = {
            "region": region,
            "event_count": events,
            "total_usd_cents": cents,
            "net_units": units,
            "blocked_count": blocked_count,
            "members": members,
            "by_kind": dict(sorted(kinds.items())),
            "by_category": dict(sorted(categories.items())),
        }

    segment_artifacts = {}
    for segment in segments:
        members = sorted({r["member_id"] for _, r, _ in cleared if r["segment"] == segment})
        cents = sum(r["cleared_usd_cents"] for _, r, _ in cleared if r["segment"] == segment)
        units = sum(net_units_of(r) for _, r, _ in cleared if r["segment"] == segment)
        events = sum(1 for _, r, _ in cleared if r["segment"] == segment)
        blocked_count = sum(1 for _, r, _ in blocked if r["segment"] == segment)
        kinds = defaultdict(int)
        categories = defaultdict(int)
        for _, r, _ in cleared:
            if r["segment"] == segment:
                kinds[r["kind"]] += r["cleared_usd_cents"]
                categories[r["category"]] += r["cleared_usd_cents"]
        segment_artifacts["segment_%s.json" % segment] = {
            "segment": segment,
            "event_count": events,
            "total_usd_cents": cents,
            "net_units": units,
            "blocked_count": blocked_count,
            "members": members,
            "by_kind": dict(sorted(kinds.items())),
            "by_category": dict(sorted(categories.items())),
            "reserve_floor_usd_cents": policy.floors.get(segment, 0),
        }

    # ---- normalized.jsonl
    normalized = [record for _, record, _ in
                  sorted(cleared, key=lambda entry: entry[1]["claim_id"])]

    malformed_dispense_ids = set(malformed_ids.get("dispenses.csv", []))
    stale_links = sum(1 for claim, record, _ in cleared
                      if record["source"] == "recoveries.tsv" and claim.link
                      and claim.link in malformed_dispense_ids)

    blocked_value = sum(r["cleared_usd_cents"] for _, r, _ in blocked)
    blocked_members = len({r["member_id"] for _, r, _ in blocked})

    report = {
        "blocked_value_usd_cents": blocked_value,
        "blocked_members": blocked_members,
        "carry_forward_rate_events": carry_forward,
        "day_shift_events": day_shift,
        "amended_events": amended_events,
        "half_cent_events": half_cent,
        "underwater_members": underwater_members,
        "uncatalogued_stock_grams": reference.uncatalogued_grams,
        "stale_link_recoveries": stale_links,
    }

    return {
        "normalized": normalized,
        "summary.json": summary,
        "data_quality.json": data_quality,
        "product_summary.json": {"products": products},
        "regions": region_artifacts,
        "segments": segment_artifacts,
        "report": report,
    }


def write_artifacts(out_dir, artifacts):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    with open(os.path.join(out_dir, "normalized.jsonl"), "w",
              encoding="utf-8", newline="") as fh:
        for record in artifacts["normalized"]:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            fh.write("\n")

    for name in ("summary.json", "data_quality.json", "product_summary.json"):
        write_json(os.path.join(out_dir, name), artifacts[name])

    for name, payload in artifacts["regions"].items():
        write_json(os.path.join(out_dir, name), payload)
    for name, payload in artifacts["segments"].items():
        write_json(os.path.join(out_dir, name), payload)


def write_json(path, payload):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        json.dump(payload, fh, sort_keys=True, indent=2)
        fh.write("\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py <DATA_DIR> <OUT_DIR>\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(data_dir):
        sys.stderr.write("input directory not found: %s\n" % data_dir)
        return 2
    artifacts = run(data_dir, out_dir)
    for key, value in sorted(artifacts["report"].items()):
        sys.stdout.write("%s: %d\n" % (key, value))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
