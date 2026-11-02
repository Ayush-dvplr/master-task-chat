#!/usr/bin/env python3
"""FY28 collateral-gated settlement pipeline.

Rebuilds the settlement desk's transform from the written contract in
``schema.md``.  Usage::

    python3 transform.py <DATA_DIR> <OUT_DIR>

Reads the event files, reference tables and policy file found in DATA_DIR and
writes every artifact under OUT_DIR.  Standard library only; no network, no
subprocesses.  All money is integer USD cents.
"""

import configparser
import csv
import datetime
import json
import os
import re
import sys
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP
from fractions import Fraction

# ---------------------------------------------------------------------------
# Event file shapes
# ---------------------------------------------------------------------------

SALES_FILE = "sales.csv"
REFUNDS_FILE = "refunds.tsv"
ADJUSTMENTS_FILE = "adjustments.jsonl"
LEGACY_FILE = "legacy.txt"

SALES_COLUMNS = [
    "event_id", "trade_ts", "counterparty_id", "sku", "warehouse",
    "quantity", "unit_price", "currency", "terminal",
]
REFUND_COLUMNS = [
    "event_id", "trade_ts", "counterparty_id", "sku", "warehouse",
    "quantity", "refund_amount", "currency", "terminal", "sale_event_id",
]
ADJUSTMENT_COLUMNS = [
    "event_id", "trade_ts", "counterparty_id", "sku", "kind",
    "amount_minor", "currency", "note",
]
LEGACY_COLUMNS = [
    "event_id", "trade_ts", "counterparty_id", "sku", "warehouse", "kind",
    "quantity", "amount", "currency", "terminal", "memo",
]

FILE_COLUMNS = {
    SALES_FILE: set(SALES_COLUMNS),
    REFUNDS_FILE: set(REFUND_COLUMNS),
    ADJUSTMENTS_FILE: set(ADJUSTMENT_COLUMNS),
    LEGACY_FILE: set(LEGACY_COLUMNS),
}

RECORD_KEYS = [
    "event_id", "settlement_date", "utc_instant", "fiscal_period",
    "counterparty_id", "segment", "region", "sku", "category", "kind",
    "quantity", "settled_usd_cents", "currency", "source", "channel_group",
    "warehouse",
]

TOP_LEVEL_REGIONS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "corporate", "enterprise", "smb"]

TS_RE = re.compile(
    r"^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})$")
ADJ_TS_RE = re.compile(
    r"^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z$")
QTY_RE = re.compile(r"^[0-9]+$")
MONEY_RE = re.compile(r"^[+-]?[0-9]+(\.[0-9]+)?$")
INT_RE = re.compile(r"^[+-]?[0-9]+$")


class Skip(Exception):
    """Raised when an event is malformed."""


# ---------------------------------------------------------------------------
# Exact decimal helpers
# ---------------------------------------------------------------------------


def parse_decimal(text):
    """Parse an optionally signed plain decimal string into an exact Fraction."""
    t = str(text).strip()
    if not MONEY_RE.match(t):
        raise Skip("not a decimal: %r" % text)
    return Fraction(t)


def parse_int(text):
    t = str(text).strip()
    if not INT_RE.match(t):
        raise Skip("not an integer: %r" % text)
    return int(t)


def rounding_mode(name):
    n = (name or "").strip().lower().replace("-", "_")
    if n in ("half_up", "halfup", "round_half_up"):
        return ROUND_HALF_UP
    if n in ("half_even", "halfeven", "round_half_even", "bankers"):
        return ROUND_HALF_EVEN
    raise ValueError("unknown rounding mode: %r" % name)


def quantize(value, mode, places=0):
    """Quantize a Fraction to `places` decimal places exactly once.

    half_up rounds halves away from zero; half_even rounds them to the
    nearest even multiple.  Both work on the magnitude, so ties move away
    from zero under half_up.
    """
    scaled = value * (10 ** places)
    if scaled.denominator == 1:
        return scaled.numerator
    sign = -1 if scaled < 0 else 1
    magnitude = scaled if sign > 0 else -scaled
    whole = magnitude.numerator // magnitude.denominator
    rem = magnitude - whole
    half = Fraction(1, 2)
    if mode == ROUND_HALF_UP:
        if rem >= half:
            whole += 1
    elif rem > half:
        whole += 1
    elif rem == half and whole % 2 != 0:
        whole += 1
    return sign * whole


def half_cent(value):
    """True when a Fraction value sits exactly half a unit from the integer."""
    rem = value - (value.numerator // value.denominator)
    return abs(rem) == Fraction(1, 2)


def fmt_date(d):
    return "%04d-%02d-%02d" % (d.year, d.month, d.day)


def fmt_instant(d):
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (
        d.year, d.month, d.day, d.hour, d.minute, d.second)


def unit_contribution(kind, quantity):
    """+quantity for sale, -quantity for refund, zero for every other kind."""
    if kind == "sale":
        return quantity
    if kind == "refund":
        return -quantity
    return 0


# ---------------------------------------------------------------------------
# Reference file loading
# ---------------------------------------------------------------------------


def read_text(path, encoding="utf-8"):
    with open(path, "r", encoding=encoding, newline="") as fh:
        return fh.read()


def load_csv_rows(path, delimiter=","):
    """Rows of a delimited file as dicts of raw strings (empty when absent)."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        out = []
        for row in reader:
            if row is None:
                continue
            out.append({key: (value if isinstance(value, str) else "")
                        for key, value in row.items() if key is not None})
        return out


def timestamp_key(text):
    """A sortable key for an `YYYY-MM-DDTHH:MM:SS[.f][Z]` stamp.

    Falls back to the raw text when the stamp will not parse, so a corpus that
    mixes formats still settles deterministically.
    """
    value = str(text).strip()
    body = value[:-1] if value.endswith("Z") else value
    try:
        return (0, datetime.datetime.strptime(body, "%Y-%m-%dT%H:%M:%S"), "")
    except ValueError:
        try:
            return (0, datetime.datetime.strptime(body, "%Y-%m-%dT%H:%M:%S.%f"), "")
        except ValueError:
            return (1, datetime.datetime.min, value)


def load_policy(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    with open(path, "r", encoding="utf-8") as fh:
        parser.read_file(fh)
    floors = {}
    for key, value in parser.items("collateral"):
        floors[key.strip().lower()] = parse_int(value)
    return {
        "opening_rate_date": parser.get("ladder", "opening_rate_date").strip(),
        "rounding": rounding_mode(parser.get("rounding", "mode")),
        "money_scale": parse_int(parser.get("rounding", "money_scale")),
        "mass_scale": parse_int(parser.get("rounding", "mass_scale")),
        "grams_per_kilogram": parse_int(parser.get("mass", "grams_per_kilogram")),
        "unassigned_period": parser.get("labels", "unassigned_period").strip(),
        "adjustment_channel_group": parser.get(
            "labels", "adjustment_channel_group").strip(),
        "floors": floors,
    }


def segment_floor(pol, segment):
    """The collateral floor for a segment, or None when policy names none."""
    return pol["floors"].get("floor_%s_usd_cents" % segment)


def load_counterparties(path):
    """counterparty_id -> the row that counts.

    The row with the greatest `updated_at` wins; rows sharing that `updated_at`
    are settled by the later of them in file order.
    """
    best = {}
    for row in load_csv_rows(path):
        cid = row.get("counterparty_id", "").strip()
        if not cid:
            continue
        key = timestamp_key(row.get("updated_at", ""))
        current = best.get(cid)
        if current is None or key >= current[0]:
            best[cid] = (key, {
                "counterparty_id": cid,
                "segment": row.get("segment", "").strip().lower(),
                "postal_code": row.get("postal_code", "").strip(),
                "opening_balance_minor": row.get("opening_balance_minor", ""),
                "opening_currency": row.get("opening_currency", "").strip().upper(),
            })
    return {cid: value[1] for cid, value in best.items()}


def load_regions(path):
    """(by_prefix, parent) where by_prefix maps postal prefix -> prefix row."""
    by_prefix = {}
    parent = {}
    for row in load_csv_rows(path):
        prefix = row.get("postal_prefix", "").strip()
        region = row.get("region", "").strip().lower()
        par = row.get("parent_region", "").strip().lower()
        if prefix and prefix not in by_prefix:
            by_prefix[prefix] = {
                "postal_prefix": prefix,
                "region": region,
                "parent_region": par,
                "default_currency": row.get("default_currency", "").strip().upper(),
            }
        if region and region not in parent:
            parent[region] = par
    return by_prefix, parent


def top_level_region(by_prefix, parent, prefix):
    """The reporting (top level) region for a postal prefix, else None."""
    row = by_prefix.get(prefix)
    if row is None:
        return None
    current = row["region"]
    seen = set()
    while current and current not in seen:
        seen.add(current)
        if current in TOP_LEVEL_REGIONS:
            return current
        current = parent.get(current, "")
    return None


def load_inventory(path):
    """warehouse -> (postal_code, tz_offset_minutes); sku -> stock sums."""
    warehouses = {}
    stock = {}
    for row in load_csv_rows(path):
        sku = row.get("sku", "").strip()
        warehouse = row.get("warehouse", "").strip()
        try:
            tz = parse_int(row.get("tz_offset_minutes", ""))
            on_hand = parse_int(row.get("on_hand_grams", "0"))
            reorder = parse_int(row.get("reorder_point_grams", "0"))
        except Skip:
            continue
        if warehouse and warehouse not in warehouses:
            warehouses[warehouse] = (row.get("postal_code", "").strip(), tz)
        if not sku:
            continue
        acc = stock.setdefault(sku, {"on_hand_grams": 0, "reorder_point_grams": 0})
        acc["on_hand_grams"] += on_hand
        acc["reorder_point_grams"] += reorder
    return warehouses, stock


def load_channels(path):
    """terminal (upper cased) -> channel_group (lower cased)."""
    out = {}
    for row in load_csv_rows(path):
        terminal = row.get("terminal", "").strip().upper()
        if terminal and terminal not in out:
            out[terminal] = row.get("channel_group", "").strip().lower()
    return out


def load_products(path):
    out = {}
    for row in load_csv_rows(path):
        sku = row.get("sku", "").strip()
        if not sku or sku in out:
            continue
        out[sku] = {
            "sku": sku,
            "category": row.get("category", "").strip().lower(),
            "unit_mass_kg": row.get("unit_mass_kg", "").strip(),
            "active": row.get("active", "").strip().lower(),
        }
    return out


def load_fx(path):
    """currency -> [(rate_date, rate Fraction)] sorted by date."""
    per_currency = {}
    for row in load_csv_rows(path):
        currency = row.get("currency", "").strip().upper()
        date = row.get("rate_date", "").strip()
        if not currency or not date:
            continue
        rate = parse_decimal(row.get("usd_rate", ""))
        rows = per_currency.setdefault(currency, [])
        rows.append((date, rate))
    for currency in per_currency:
        per_currency[currency].sort(key=lambda item: item[0])
    return per_currency


def rate_on_or_before(per_currency, currency, date_text):
    """(rate, carry_forward) for the most recent row on or before the date.

    carry_forward is True when the date itself had no row for the currency.
    """
    rows = per_currency.get(currency)
    if not rows:
        return None, False
    lo, hi, best = 0, len(rows) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if rows[mid][0] <= date_text:
            best = rows[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        return None, False
    return best[1], best[0] != date_text


def load_fiscal(path, fallback_label):
    """(periods, unassigned_label) with periods as (start, end, label)."""
    if not os.path.isfile(path):
        return [], fallback_label
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    periods = []
    for period in doc.get("periods", []):
        periods.append((str(period["start"]).strip(), str(period["end"]).strip(),
                        str(period["period"]).strip()))
    periods.sort(key=lambda item: item[0])
    label = str(doc.get("unassigned_label", "") or "").strip() or fallback_label
    return periods, label


def fiscal_period(periods, unassigned_label, date_text):
    for start, end, label in periods:
        if start <= date_text <= end:
            return label
    return unassigned_label


def load_corrections(path):
    """[(utc_ts, target, field, value)] for correction lines, in file order."""
    out = []
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        utc_ts, _level, message = parts[0], parts[1], parts[2]
        tokens = message.split()
        if not tokens or tokens[0].strip().lower() != "correction":
            continue
        fields = {}
        for token in tokens[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key.strip()] = value
        out.append((utc_ts.strip(), (fields.get("target") or "").strip(),
                    (fields.get("field") or "").strip(),
                    fields.get("value", "")))
    return out


# ---------------------------------------------------------------------------
# Event files: raw rows and corrections
# ---------------------------------------------------------------------------


def read_event_rows(data_dir):
    """source -> list of raw rows.

    Rows are dicts of raw strings.  A legacy line that does not carry exactly
    eleven fields has no event; it is kept as None so it is still counted
    against its own event file.
    """
    rows = {}

    if os.path.isfile(os.path.join(data_dir, SALES_FILE)):
        rows[SALES_FILE] = load_csv_rows(os.path.join(data_dir, SALES_FILE), ",")
    if os.path.isfile(os.path.join(data_dir, REFUNDS_FILE)):
        rows[REFUNDS_FILE] = load_csv_rows(
            os.path.join(data_dir, REFUNDS_FILE), "\t")
    if os.path.isfile(os.path.join(data_dir, ADJUSTMENTS_FILE)):
        adjustments = []
        with open(os.path.join(data_dir, ADJUSTMENTS_FILE), "r",
                  encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    adjustments.append(json.loads(line))
        rows[ADJUSTMENTS_FILE] = adjustments
    if os.path.isfile(os.path.join(data_dir, LEGACY_FILE)):
        legacy = []
        for line in read_text(os.path.join(data_dir, LEGACY_FILE),
                              "latin-1").split("\n"):
            line = line.strip()
            if not line or line[0] == "#":
                continue
            fields = line.split("|")
            legacy.append(None if len(fields) != len(LEGACY_COLUMNS)
                          else dict(zip(LEGACY_COLUMNS, fields)))
        rows[LEGACY_FILE] = legacy
    return rows


def resolve_corrections(data_dir, rows):
    """Merge the winning corrections into the rows they name.

    A correction whose field is not a column of its target's own event file, or
    which names `event_id`, is ignored.  A correction whose target matches no
    event id in any event file is unmatched and is reported.

    Returns (rows, unmatched_targets, corrected_event_ids).
    """
    log_path = os.path.join(data_dir, "corrections.log")
    if not os.path.isfile(log_path):
        return rows, set(), set()

    id_source = {}
    for source, source_rows in rows.items():
        for row in source_rows:
            if row is None:
                continue
            event_id = str(row.get("event_id", "")).strip()
            if event_id and event_id not in id_source:
                id_source[event_id] = source

    # one winner per (target, field): greatest utc_ts, later in file order
    winners = {}
    for utc_ts, target, field, value in load_corrections(log_path):
        if not target or not field:
            continue
        key = (target, field)
        sort_key = timestamp_key(utc_ts)
        current = winners.get(key)
        if current is None or sort_key >= current[0]:
            winners[key] = (sort_key, value)

    fixes = {}
    corrected = set()
    matched = set()
    for (target, field), (_utc_ts, value) in winners.items():
        source = id_source.get(target)
        if source is None:
            continue
        matched.add(target)
        if field == "event_id" or field not in FILE_COLUMNS[source]:
            continue
        fixes.setdefault((source, target), {})[field] = value
        corrected.add(target)

    unmatched = {target for (target, _field) in winners} - matched

    merged_by_source = {}
    for source, source_rows in rows.items():
        merged = []
        for row in source_rows:
            if row is None:
                merged.append(None)
                continue
            event_id = str(row.get("event_id", "")).strip()
            row_fixes = fixes.get((source, event_id))
            if row_fixes:
                row = dict(row)
                row.update(row_fixes)
            merged.append(row)
        merged_by_source[source] = merged
    return merged_by_source, unmatched, corrected


# ---------------------------------------------------------------------------
# Settling one event
# ---------------------------------------------------------------------------


def parse_local_ts(text):
    """A wall-clock `trade_ts`; a day that does not exist is malformed."""
    value = str(text).strip()
    match = TS_RE.match(value)
    if not match:
        raise Skip("bad trade_ts")
    year, month, day, hour, minute, second = (int(x) for x in match.groups())
    try:
        return datetime.datetime(year, month, day, hour, minute, second)
    except ValueError:
        raise Skip("nonexistent day")


def parse_utc_ts(text):
    value = str(text).strip()
    match = ADJ_TS_RE.match(value)
    if not match:
        raise Skip("bad trade_ts")
    year, month, day, hour, minute, second = (int(x) for x in match.groups())
    try:
        return datetime.datetime(year, month, day, hour, minute, second)
    except ValueError:
        raise Skip("nonexistent day")


def parse_quantity(text):
    """An integer written with ASCII digits and nothing else; `0` is allowed."""
    value = str(text).strip()
    if not QTY_RE.match(value):
        raise Skip("bad quantity")
    return int(value)


def event_kind(source, row):
    if source == SALES_FILE:
        return "sale"
    if source == REFUNDS_FILE:
        return "refund"
    if source == ADJUSTMENTS_FILE:
        kind = str(row.get("kind", "")).strip().lower()
        if kind not in ("fee", "credit"):
            raise Skip("bad adjustment kind")
        return kind
    kind = str(row.get("kind", "")).strip().lower()
    if kind not in ("sale", "refund", "fee", "credit"):
        raise Skip("bad kind")
    return kind


def gross_amount(source, row, kind, quantity):
    """The gross amount as an exact Fraction, signed."""
    if source == SALES_FILE:
        return Fraction(quantity) * parse_decimal(row.get("unit_price", ""))
    if source == REFUNDS_FILE:
        return -abs(parse_decimal(row.get("refund_amount", "")))
    if source == ADJUSTMENTS_FILE:
        raw = row.get("amount_minor")
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise Skip("amount_minor is not a JSON integer")
        return Fraction(raw, 100)
    amount = abs(parse_decimal(row.get("amount", "")))
    return amount if kind in ("sale", "fee") else -amount


def settle_event(source, row, ctx):
    """Parse and resolve one event into a settled candidate."""
    pol = ctx["pol"]

    if source == LEGACY_FILE and row is None:
        raise Skip("legacy line without eleven fields")

    kind = event_kind(source, row)
    # An adjustment carries no quantity column; its quantity is 0.
    if source == ADJUSTMENTS_FILE:
        quantity = 0
    else:
        quantity = parse_quantity(row.get("quantity", ""))
    gross = gross_amount(source, row, kind, quantity)

    if source == ADJUSTMENTS_FILE:
        utc = parse_utc_ts(row.get("trade_ts", ""))
        warehouse = None
        channel_group = pol["adjustment_channel_group"]
        trade_date = None
    else:
        trade_text = str(row.get("trade_ts", ""))
        local = parse_local_ts(trade_text)
        trade_date = trade_text.strip()[:10]
        warehouse = str(row.get("warehouse", "")).strip()
        info = ctx["warehouses"].get(warehouse)
        if info is None:
            raise Skip("unknown warehouse")
        postal_code, tz_offset = info
        utc = local + datetime.timedelta(minutes=tz_offset)
        terminal = str(row.get("terminal", "")).strip().upper()
        channel_group = ctx["channels"].get(terminal)
        if channel_group is None:
            raise Skip("unknown terminal")

    counterparty_id = str(row.get("counterparty_id", "")).strip()
    counterparty = ctx["counterparties"].get(counterparty_id)
    if counterparty is None:
        raise Skip("unknown counterparty")

    if source == ADJUSTMENTS_FILE:
        postal_code = counterparty["postal_code"]
    own_currency = str(row.get("currency", "")).strip().upper()

    sku = str(row.get("sku", "")).strip()
    product = ctx["products"].get(sku)
    if product is None:
        raise Skip("unknown sku")

    prefix = postal_code.split("-", 1)[0]
    region = top_level_region(ctx["regions"], ctx["region_parent"], prefix)
    if region is None:
        raise Skip("unknown postal prefix")
    default_currency = ctx["regions"][prefix]["default_currency"]

    currency = own_currency or default_currency
    if not currency:
        raise Skip("no currency")

    settlement_date = fmt_date(utc)
    rate, carried = rate_on_or_before(ctx["fx"], currency, settlement_date)
    if rate is None:
        raise Skip("no usable rate")

    unrounded = gross * rate * 100
    settled = quantize(unrounded, pol["rounding"], pol["money_scale"])

    event_id = str(row.get("event_id", "")).strip()
    return {
        "source": source,
        "event_id": event_id,
        "settlement_date": settlement_date,
        "utc_instant": fmt_instant(utc),
        "fiscal_period": fiscal_period(ctx["periods"], pol["unassigned_period"],
                                       settlement_date),
        "counterparty_id": counterparty_id,
        "segment": counterparty["segment"],
        "region": region,
        "sku": sku,
        "category": product["category"],
        "kind": kind,
        "quantity": quantity,
        "settled_usd_cents": settled,
        "currency": currency,
        "channel_group": channel_group,
        "warehouse": warehouse,
        "net_units": unit_contribution(kind, quantity),
        "_sort_key": (utc, event_id),
        "_trade_date": trade_date,
        "_carried": carried,
        "_half_cent": half_cent(unrounded),
        "_sale_event_id": (str(row["sale_event_id"]).strip()
                           if source == REFUNDS_FILE else ""),
    }


def public_record(candidate):
    return {key: candidate[key] for key in RECORD_KEYS}


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------


def group_sum(records, key):
    out = {}
    for record in records:
        out[record[key]] = out.get(record[key], 0) + record["settled_usd_cents"]
    return out


def group_count(records, key):
    out = {}
    for record in records:
        out[record[key]] = out.get(record[key], 0) + 1
    return out


def net_units_of(records):
    return sum(unit_contribution(record["kind"], record["quantity"])
               for record in records)


def write_json(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, sort_keys=True, indent=2)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run(data_dir, out_dir):
    pol = load_policy(os.path.join(data_dir, "policy.ini"))
    periods, calendar_label = load_fiscal(
        os.path.join(data_dir, "fiscal_calendar.json"), pol["unassigned_period"])
    pol["unassigned_period"] = pol["unassigned_period"] or calendar_label

    counterparties = load_counterparties(
        os.path.join(data_dir, "counterparties.csv"))
    regions, region_parent = load_regions(os.path.join(data_dir, "regions.csv"))
    warehouses, stock = load_inventory(os.path.join(data_dir, "inventory.csv"))
    channels = load_channels(os.path.join(data_dir, "channels.csv"))
    products = load_products(os.path.join(data_dir, "product_catalog.csv"))
    fx = load_fx(os.path.join(data_dir, "fx_rates.csv"))

    uncatalogued_grams = sum(
        acc["on_hand_grams"] for sku, acc in stock.items()
        if sku not in products)

    ctx = {
        "pol": pol, "periods": periods, "counterparties": counterparties,
        "regions": regions, "region_parent": region_parent,
        "warehouses": warehouses, "channels": channels, "products": products,
        "fx": fx,
    }

    raw_rows = read_event_rows(data_dir)
    rows, unmatched_targets, corrected_targets = resolve_corrections(
        data_dir, raw_rows)

    # sales.csv ids as they stand, for the orphan debit link test
    sales_ids = set()
    for row in rows.get(SALES_FILE, []):
        if row is not None:
            event_id = str(row.get("event_id", "")).strip()
            if event_id:
                sales_ids.add(event_id)

    # ---- parse every event -----------------------------------------------
    candidates = []
    skipped = {source: 0 for source in rows}
    orphan_ids = []
    skipped_sale_ids = set()

    for source in (SALES_FILE, REFUNDS_FILE, ADJUSTMENTS_FILE, LEGACY_FILE):
        for row in rows.get(source, []):
            event_id = ("" if row is None
                        else str(row.get("event_id", "")).strip())
            if row is None or not event_id:
                skipped[source] += 1
                continue
            if (source == REFUNDS_FILE
                    and str(row.get("sale_event_id", "")).strip()
                    and str(row.get("sale_event_id", "")).strip() not in sales_ids):
                orphan_ids.append(event_id)
                continue
            try:
                candidate = settle_event(source, row, ctx)
            except (Skip, KeyError, ValueError, TypeError, AttributeError):
                skipped[source] += 1
                if source == SALES_FILE:
                    skipped_sale_ids.add(event_id)
                continue
            candidates.append(candidate)

    orphan_ids = sorted(set(orphan_ids))

    # ---- the collateral ladder -------------------------------------------
    opening_date = pol["opening_rate_date"]
    balances = {}
    underwater = 0
    for cid, counterparty in counterparties.items():
        rate, _carried = rate_on_or_before(
            fx, counterparty["opening_currency"], opening_date)
        if rate is None:
            opening = 0
        else:
            opening = quantize(
                Fraction(parse_int(counterparty["opening_balance_minor"]), 100)
                * rate * 100, pol["rounding"], pol["money_scale"])
        balances[cid] = opening
        floor = segment_floor(pol, counterparty["segment"])
        if floor is not None and opening < floor:
            underwater += 1

    floors = {segment: segment_floor(pol, segment) for segment in SEGMENTS}

    by_counterparty = {}
    for candidate in candidates:
        by_counterparty.setdefault(candidate["counterparty_id"], []).append(
            candidate)
    for group in by_counterparty.values():
        group.sort(key=lambda candidate: candidate["_sort_key"])

    accepted = []
    blocked = []
    for cid, group in by_counterparty.items():
        balance = balances.get(cid, 0)
        counterparty = counterparties.get(cid)
        floor = floors.get(counterparty["segment"]) if counterparty else None
        for candidate in group:
            amount = candidate["settled_usd_cents"]
            if amount >= 0 or floor is None or balance + amount >= floor:
                balance += amount
                accepted.append(candidate)
            else:
                blocked.append(candidate)
        balances[cid] = balance

    ladder_closing = sum(balances.get(cid, 0) for cid in counterparties)

    accepted.sort(key=lambda candidate: candidate["event_id"])
    records = [public_record(candidate) for candidate in accepted]

    # ---- normalized.jsonl -------------------------------------------------
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "normalized.jsonl"), "w",
              encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True,
                                separators=(",", ":")) + "\n")

    # ---- summary.json ------------------------------------------------------
    summary = {
        "event_count": len(records),
        "skipped_count": sum(skipped.values()),
        "blocked_count": len(blocked),
        "orphan_refund_count": len(orphan_ids),
        "total_usd_cents": sum(record["settled_usd_cents"] for record in records),
        "net_units": net_units_of(records),
        "ladder_closing_usd_cents": ladder_closing,
        "by_region": group_sum(records, "region"),
        "by_segment": group_sum(records, "segment"),
        "by_kind": group_sum(records, "kind"),
        "by_category": group_sum(records, "category"),
        "by_channel_group": group_sum(records, "channel_group"),
        "by_fiscal_period": group_sum(records, "fiscal_period"),
        "by_source": group_sum(records, "source"),
    }
    write_json(os.path.join(out_dir, "summary.json"), summary)

    # ---- data_quality.json -------------------------------------------------
    blocked_by_source = group_count(blocked, "source")
    event_files_present = [
        name for name in (SALES_FILE, REFUNDS_FILE, ADJUSTMENTS_FILE, LEGACY_FILE)
        if name in rows]
    data_quality = {
        "input_files": sorted(
            name for name in os.listdir(data_dir)
            if os.path.isfile(os.path.join(data_dir, name))),
        "records_by_source": group_count(records, "source"),
        "skipped_by_source": {name: skipped.get(name, 0)
                              for name in event_files_present},
        "blocked_by_source": {name: blocked_by_source.get(name, 0)
                              for name in event_files_present},
        "skipped_count": sum(skipped.values()),
        "blocked_count": len(blocked),
        "orphan_refund_count": len(orphan_ids),
        "blocked_event_ids": sorted({c["event_id"] for c in blocked}),
        "orphan_refund_event_ids": orphan_ids,
        "unmatched_correction_targets": sorted(unmatched_targets),
    }
    write_json(os.path.join(out_dir, "data_quality.json"), data_quality)

    # ---- product_summary.json ---------------------------------------------
    per_sku = {}
    for candidate in accepted:
        acc = per_sku.setdefault(candidate["sku"], {
            "event_count": 0, "total_usd_cents": 0, "net_units": 0})
        acc["event_count"] += 1
        acc["total_usd_cents"] += candidate["settled_usd_cents"]
        acc["net_units"] += candidate["net_units"]
    products_out = []
    for sku in sorted(products):
        product = products[sku]
        acc = per_sku.get(sku, {"event_count": 0, "total_usd_cents": 0,
                                "net_units": 0})
        stock_acc = stock.get(sku, {"on_hand_grams": 0, "reorder_point_grams": 0})
        net_mass = quantize(
            Fraction(acc["net_units"]) * parse_decimal(product["unit_mass_kg"])
            * pol["grams_per_kilogram"], pol["rounding"], pol["mass_scale"])
        products_out.append({
            "sku": sku,
            "category": product["category"],
            "event_count": acc["event_count"],
            "total_usd_cents": acc["total_usd_cents"],
            "net_units": acc["net_units"],
            "on_hand_grams": stock_acc["on_hand_grams"],
            "reorder_point_grams": stock_acc["reorder_point_grams"],
            "net_mass_grams": net_mass,
        })
    write_json(os.path.join(out_dir, "product_summary.json"),
               {"products": products_out})

    # ---- one file per top level region, one per segment -------------------
    for key_field, names, extra in (("region", TOP_LEVEL_REGIONS, None),
                                    ("segment", SEGMENTS, "collateral")):
        for name in names:
            records_here = [rec for rec in records if rec[key_field] == name]
            blocked_here = [c for c in blocked if c[key_field] == name]
            doc = {
                "event_count": len(records_here),
                "total_usd_cents": sum(
                    rec["settled_usd_cents"] for rec in records_here),
                "net_units": net_units_of(records_here),
                "blocked_count": len(blocked_here),
                "counterparties": sorted(
                    {rec["counterparty_id"] for rec in records_here}),
                "by_kind": group_sum(records_here, "kind"),
                "by_category": group_sum(records_here, "category"),
                key_field: name,
            }
            if extra == "collateral":
                doc["collateral_floor_usd_cents"] = floors.get(name)
            write_json(os.path.join(out_dir, "%s_%s.json" % (key_field, name)),
                       doc)

    # ---- the nine closing report figures ---------------------------------
    return {
        "blocked_value_usd_cents": sum(
            candidate["settled_usd_cents"] for candidate in blocked),
        "blocked_counterparties": len(
            {candidate["counterparty_id"] for candidate in blocked}),
        "carry_forward_rate_events": sum(
            1 for candidate in accepted if candidate["_carried"]),
        "day_shift_events": sum(
            1 for candidate in accepted
            if candidate["_trade_date"] is not None
            and candidate["settlement_date"] != candidate["_trade_date"]),
        "corrected_events": len(corrected_targets),
        "half_cent_events": sum(
            1 for candidate in accepted if candidate["_half_cent"]),
        "underwater_counterparties": underwater,
        "uncatalogued_stock_grams": uncatalogued_grams,
        "stale_link_refunds": sum(
            1 for candidate in accepted
            if candidate["source"] == REFUNDS_FILE and candidate["_sale_event_id"]
            and candidate["_sale_event_id"] in skipped_sale_ids),
    }


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py <DATA_DIR> <OUT_DIR>\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(data_dir):
        sys.stderr.write("not a directory: %s\n" % data_dir)
        return 2
    report = run(data_dir, out_dir)
    sys.stdout.write("closing report:\n")
    for key in sorted(report):
        sys.stdout.write("  %s: %s\n" % (key, report[key]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
