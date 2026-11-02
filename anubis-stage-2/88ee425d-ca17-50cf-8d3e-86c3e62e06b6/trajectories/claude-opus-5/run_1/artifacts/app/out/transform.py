#!/usr/bin/env python3
"""TY31 reserve-gated dispensing clearing run.

Usage: python3 transform.py <DATA_DIR> <OUT_DIR>

Rebuilds the clearing pipeline described in schema.md: normalizes four claim
files against eight reference files and one policy file, runs the per-member
reserve ladder, and writes the normalized stream plus every roll-up artifact.
"""

import csv
import datetime
import json
import os
import re
import sys
from collections import defaultdict
from decimal import (Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_DOWN,
                     ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP)

REGIONS = ("central", "east", "north", "south", "west")
SEGMENTS = ("consumer", "corporate", "enterprise", "smb")

DISPENSES = "dispenses.csv"
RECOVERIES = "recoveries.tsv"
ASSESSMENTS = "assessments.jsonl"
ARCHIVE = "archive.txt"
CLAIM_FILES = (DISPENSES, RECOVERIES, ASSESSMENTS, ARCHIVE)

CLAIM_COLUMNS = {
    DISPENSES: ("claim_id", "booked_ts", "member_id", "item_code", "depot",
                "quantity", "unit_price", "currency", "gateway"),
    RECOVERIES: ("claim_id", "booked_ts", "member_id", "item_code", "depot",
                 "quantity", "recovered_amount", "currency", "gateway",
                 "dispense_claim_id"),
    ASSESSMENTS: ("claim_id", "booked_ts", "member_id", "item_code", "kind",
                  "amount_minor", "currency", "note"),
    ARCHIVE: ("claim_id", "booked_ts", "member_id", "item_code", "depot",
              "kind", "quantity", "amount", "currency", "gateway", "memo"),
}

ROUNDING_MODES = {
    "half_up": ROUND_HALF_UP,
    "half_even": ROUND_HALF_EVEN,
    "half_down": ROUND_HALF_DOWN,
    "down": ROUND_DOWN,
    "up": ROUND_UP,
}

UINT_RE = re.compile(r"[0-9]+")
INT_RE = re.compile(r"-?[0-9]+")
DECIMAL_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?")
TS_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})")
AMENDMENT_RE = re.compile(r"amendment\s+target=(\S*)\s+field=(\S*)\s+value=(.*)$")


class Skip(Exception):
    """A claim that fails to parse or whose lookup chain misses."""


def text(value):
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def label(value):
    return text(value).casefold()


def read_rows(path, delimiter):
    with open(path, newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]


# --------------------------------------------------------------------------
# policy, calendar and reference tables
# --------------------------------------------------------------------------

def load_policy(path):
    section = None
    values = {}
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line[0] in ";#":
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip().casefold()
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[(section, key.strip().casefold())] = value.strip()
    mode = ROUNDING_MODES[values[("rounding", "mode")].casefold()]
    return {
        "opening_rate_date": values[("ladder", "opening_rate_date")],
        "money_mode": mode,
        "mass_mode": mode,
        "money_scale": int(values[("rounding", "money_scale")]),
        "mass_scale": int(values[("rounding", "mass_scale")]),
        "grams_per_kilogram": Decimal(values[("mass", "grams_per_kilogram")]),
        "unassigned_period": values[("labels", "unassigned_period")],
        "assessment_lane": values[("labels", "assessment_lane")],
        "floors": {seg: int(values[("reserve", "floor_%s_usd_cents" % seg)])
                   for seg in SEGMENTS},
    }


def load_zones(path):
    prefix = {}
    parent = {}
    for row in read_rows(path, ","):
        zone = label(row.get("zone"))
        parent[zone] = label(row.get("parent_zone"))
        prefix[text(row.get("postal_prefix"))] = (zone, text(row.get("default_currency")).upper())
    region_of = {}
    for zone in parent:
        seen = set()
        cur = zone
        while parent.get(cur) and cur not in seen:
            seen.add(cur)
            cur = parent[cur]
        region_of[zone] = cur
    return prefix, region_of


def load_members(path):
    best = {}
    for order, row in enumerate(read_rows(path, ",")):
        member_id = text(row.get("member_id"))
        rank = (text(row.get("updated_at")), order)
        if member_id not in best or rank > best[member_id][0]:
            best[member_id] = (rank, row)
    return {mid: row for mid, (_rank, row) in best.items()}


def load_stock(path):
    depots = {}
    on_hand = defaultdict(int)
    reorder = defaultdict(int)
    for row in read_rows(path, ","):
        depot = text(row.get("depot"))
        depots[depot] = (text(row.get("postal_code")), int(text(row.get("tz_offset_minutes"))))
        item = text(row.get("item_code"))
        on_hand[item] += int(text(row.get("on_hand_grams")))
        reorder[item] += int(text(row.get("reorder_point_grams")))
    return depots, on_hand, reorder


def load_fx(path):
    rates = defaultdict(dict)
    for row in read_rows(path, ","):
        rates[text(row.get("currency")).upper()][text(row.get("rate_date"))] = \
            Decimal(text(row.get("usd_rate")))
    return {cur: sorted(days.items()) for cur, days in rates.items()}


def lookup_rate(fx, currency, date_str):
    """Return (rate, carried_forward) or None when no row is on or before date."""
    days = fx.get(currency)
    if not days:
        return None
    best = None
    for day, rate in days:
        if day == date_str:
            return rate, False
        if day < date_str:
            best = rate
        else:
            break
    if best is None:
        return None
    return best, True


def load_calendar(path):
    with open(path, encoding="utf-8") as handle:
        doc = json.load(handle)
    return [(text(p.get("start")), text(p.get("end")), text(p.get("period")))
            for p in doc.get("periods", [])]


def period_of(periods, date_str, unassigned):
    for start, end, name in periods:
        if start <= date_str <= end:
            return name
    return unassigned


# --------------------------------------------------------------------------
# amendments
# --------------------------------------------------------------------------

def load_amendments(path):
    """Map claim_id -> {field: winning value}, and the set of every target named."""
    if not os.path.isfile(path):
        return {}, set()
    winners = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for order, raw in enumerate(handle):
            line = raw.rstrip("\n").rstrip("\r")
            parts = line.split(" ", 2)
            if len(parts) < 3:
                continue
            stamp, _level, message = parts
            if message.split(" ", 1)[0] != "amendment":
                continue
            match = AMENDMENT_RE.match(message)
            if not match:
                continue
            key = (text(match.group(1)), text(match.group(2)))
            rank = (text(stamp), order)
            if key not in winners or rank > winners[key][0]:
                winners[key] = (rank, match.group(3))
    by_claim = defaultdict(dict)
    targets = set()
    for (target, field), (_rank, value) in winners.items():
        targets.add(target)
        by_claim[target][field] = value
    return dict(by_claim), targets


# --------------------------------------------------------------------------
# claim file readers
# --------------------------------------------------------------------------

def read_claim_files(data_dir):
    """Return raw claims tagged with the claim file they came from."""
    claims = []

    path = os.path.join(data_dir, DISPENSES)
    if os.path.isfile(path):
        for row in read_rows(path, ","):
            row["_source"] = DISPENSES
            claims.append(row)

    path = os.path.join(data_dir, RECOVERIES)
    if os.path.isfile(path):
        for row in read_rows(path, "\t"):
            row["_source"] = RECOVERIES
            claims.append(row)

    path = os.path.join(data_dir, ASSESSMENTS)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    claims.append({"_source": ASSESSMENTS, "_broken": True, "claim_id": ""})
                    continue
                row = {k: obj.get(k) for k in CLAIM_COLUMNS[ASSESSMENTS] if k in obj}
                row["_source"] = ASSESSMENTS
                claims.append(row)

    path = os.path.join(data_dir, ARCHIVE)
    if os.path.isfile(path):
        with open(path, encoding="latin-1") as handle:
            for raw in handle:
                line = raw.rstrip("\n").rstrip("\r")
                if not line.strip() or line.lstrip()[0] == "#":
                    continue
                fields = line.split("|")
                if len(fields) != 11:
                    claims.append({"_source": ARCHIVE, "_broken": True,
                                   "claim_id": text(fields[0])})
                    continue
                row = dict(zip(CLAIM_COLUMNS[ARCHIVE], fields))
                row["_source"] = ARCHIVE
                claims.append(row)

    return claims


# --------------------------------------------------------------------------
# field parsing
# --------------------------------------------------------------------------

def parse_uint(raw):
    value = text(raw)
    if not UINT_RE.fullmatch(value):
        raise Skip("quantity")
    return int(value)


def parse_decimal(raw):
    value = text(raw)
    if not DECIMAL_RE.fullmatch(value):
        raise Skip("decimal")
    try:
        return Decimal(value)
    except InvalidOperation:
        raise Skip("decimal")


def parse_json_int(raw, amended):
    """A raw value must be a JSON integer; an amended one is integer text."""
    if amended:
        value = text(raw)
        if not INT_RE.fullmatch(value):
            raise Skip("amount_minor")
        return int(value)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise Skip("amount_minor")
    return raw


def parse_ts(raw):
    value = text(raw)
    if value.endswith("Z"):
        value = value[:-1]
    match = TS_RE.fullmatch(value)
    if not match:
        raise Skip("booked_ts")
    year, month, day, hour, minute, second = (int(g) for g in match.groups())
    if hour > 23 or minute > 59 or second > 59:
        raise Skip("booked_ts")
    try:
        return datetime.datetime(year, month, day, hour, minute, second)
    except ValueError:
        raise Skip("booked_ts")


def quantize(value, scale, mode):
    return value.quantize(Decimal(1).scaleb(-scale), rounding=mode)


# --------------------------------------------------------------------------
# the clearing chain
# --------------------------------------------------------------------------

class Pipeline:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.policy = load_policy(os.path.join(data_dir, "policy.ini"))
        self.prefixes, self.region_of = load_zones(os.path.join(data_dir, "zones.csv"))
        self.members = load_members(os.path.join(data_dir, "members.csv"))
        self.depots, self.on_hand, self.reorder = load_stock(
            os.path.join(data_dir, "stock_ledger.csv"))
        self.fx = load_fx(os.path.join(data_dir, "fx_rates.csv"))
        self.periods = load_calendar(os.path.join(data_dir, "tariff_calendar.json"))
        self.lanes = {label(r.get("gateway")): label(r.get("lane"))
                      for r in read_rows(os.path.join(data_dir, "gateways.csv"), ",")}
        self.catalog = {}
        for row in read_rows(os.path.join(data_dir, "item_catalog.csv"), ","):
            self.catalog[text(row.get("item_code"))] = (
                label(row.get("category")), Decimal(text(row.get("pack_mass_kg"))))
        self.amendments, self.amendment_targets = load_amendments(
            os.path.join(data_dir, "amendments.log"))

        self.present_claim_files = [name for name in CLAIM_FILES
                                    if os.path.isfile(os.path.join(data_dir, name))]
        self.raw_claims = read_claim_files(data_dir)
        self.claim_ids = {text(row.get("claim_id")) for row in self.raw_claims}
        self.dispense_ids = {text(row.get("claim_id")) for row in self.raw_claims
                             if row["_source"] == DISPENSES}

        self.amended_ids = set()
        self.skipped_by_source = {name: 0 for name in self.present_claim_files}
        self.blocked_by_source = {name: 0 for name in self.present_claim_files}
        self.orphan_ids = set()
        self.skipped_dispense_ids = set()
        self.candidates = []
        self.carry_forward = 0
        self.day_shift = 0
        self.half_cent = 0

    def apply_amendments(self, row):
        source = row["_source"]
        edits = self.amendments.get(text(row.get("claim_id")))
        if not edits:
            return row
        applied = set()
        for field, value in edits.items():
            if field == "claim_id" or field not in CLAIM_COLUMNS[source]:
                continue
            row[field] = value
            applied.add(field)
        if applied:
            row["_amended"] = applied
            self.amended_ids.add(text(row.get("claim_id")))
        return row

    def clear(self, row):
        """Build the canonical record for one claim, or raise Skip."""
        source = row["_source"]
        if row.get("_broken"):
            raise Skip("shape")

        member_id = text(row.get("member_id"))
        member = self.members.get(member_id)
        if member is None:
            raise Skip("member")

        item_code = text(row.get("item_code"))
        if item_code not in self.catalog:
            raise Skip("item")

        if source == ASSESSMENTS:
            depot = None
            postal_code = text(member.get("postal_code"))
            offset = 0
            lane = self.policy["assessment_lane"]
        else:
            depot = text(row.get("depot"))
            if depot not in self.depots:
                raise Skip("depot")
            postal_code, offset = self.depots[depot]
            gateway = label(row.get("gateway"))
            if gateway not in self.lanes:
                raise Skip("gateway")
            lane = self.lanes[gateway]

        prefix = postal_code.split("-", 1)[0]
        if prefix not in self.prefixes:
            raise Skip("prefix")
        zone, default_currency = self.prefixes[prefix]

        currency = text(row.get("currency")).upper() or default_currency
        if not currency:
            raise Skip("currency")

        local = parse_ts(row.get("booked_ts"))
        instant = local if source == ASSESSMENTS else local - datetime.timedelta(minutes=offset)
        clearing_date = instant.date().isoformat()

        found = lookup_rate(self.fx, currency, clearing_date)
        if found is None:
            raise Skip("rate")
        rate, carried = found

        if source == DISPENSES:
            kind = "dispense"
            quantity = parse_uint(row.get("quantity"))
            gross = Decimal(quantity) * parse_decimal(row.get("unit_price"))
        elif source == RECOVERIES:
            kind = "recovery"
            quantity = parse_uint(row.get("quantity"))
            gross = -abs(parse_decimal(row.get("recovered_amount")))
        elif source == ASSESSMENTS:
            kind = label(row.get("kind"))
            if kind not in ("levy", "rebate"):
                raise Skip("kind")
            quantity = 0
            amended = "amount_minor" in row.get("_amended", ())
            gross = Decimal(parse_json_int(row.get("amount_minor"), amended)) / Decimal(100)
        else:
            kind = label(row.get("kind"))
            if kind not in ("dispense", "recovery", "levy", "rebate"):
                raise Skip("kind")
            quantity = parse_uint(row.get("quantity"))
            amount = abs(parse_decimal(row.get("amount")))
            gross = amount if kind in ("dispense", "levy") else -amount

        product = gross * rate * Decimal(100)
        cents = int(quantize(product, self.policy["money_scale"], self.policy["money_mode"]))

        if kind == "dispense":
            net_units = quantity
        elif kind == "recovery":
            net_units = -quantity
        else:
            net_units = 0

        record = {
            "claim_id": text(row.get("claim_id")),
            "clearing_date": clearing_date,
            "utc_instant": instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tariff_period": period_of(self.periods, clearing_date,
                                       self.policy["unassigned_period"]),
            "member_id": member_id,
            "segment": label(member.get("segment")),
            "region": self.region_of[zone],
            "item_code": item_code,
            "category": self.catalog[item_code][0],
            "kind": kind,
            "quantity": quantity,
            "cleared_usd_cents": cents,
            "currency": currency,
            "source": source,
            "lane": lane,
            "depot": depot,
        }
        meta = {
            "instant": instant,
            "net_units": net_units,
            "carried": carried,
            "day_shift": clearing_date != text(row.get("booked_ts"))[:10],
            "half_cent": abs(product) % 1 == Decimal("0.5"),
            "link": text(row.get("dispense_claim_id")) if source == RECOVERIES else "",
        }
        return record, meta

    def normalize(self):
        for row in self.raw_claims:
            source = row["_source"]
            row = self.apply_amendments(row)
            claim_id = text(row.get("claim_id"))

            if source == RECOVERIES:
                link = text(row.get("dispense_claim_id"))
                if link and link not in self.dispense_ids:
                    self.orphan_ids.add(claim_id)
                    continue
            try:
                self.candidates.append(self.clear(row))
            except Skip:
                self.skipped_by_source[source] = self.skipped_by_source.get(source, 0) + 1
                if source == DISPENSES:
                    self.skipped_dispense_ids.add(claim_id)

    def opening_cents(self, row):
        currency = text(row.get("opening_currency")).upper()
        found = lookup_rate(self.fx, currency, self.policy["opening_rate_date"])
        if found is None:
            return 0
        rate, _carried = found
        minor = Decimal(text(row.get("opening_reserve_minor")))
        product = (minor / Decimal(100)) * rate * Decimal(100)
        return int(quantize(product, self.policy["money_scale"], self.policy["money_mode"]))

    def run_ladder(self):
        reserves = {mid: self.opening_cents(row) for mid, row in self.members.items()}
        self.underwater_members = sum(
            1 for mid, row in self.members.items()
            if reserves[mid] < self.policy["floors"][label(row.get("segment"))])

        by_member = defaultdict(list)
        for pair in self.candidates:
            by_member[pair[0]["member_id"]].append(pair)

        self.cleared = []
        self.blocked = []
        for member_id, items in by_member.items():
            items.sort(key=lambda pair: (pair[1]["instant"], pair[0]["claim_id"]))
            floor = self.policy["floors"][items[0][0]["segment"]]
            reserve = reserves[member_id]
            for record, meta in items:
                cents = record["cleared_usd_cents"]
                if cents >= 0 or reserve + cents >= floor:
                    reserve += cents
                    self.cleared.append((record, meta))
                else:
                    self.blocked.append(record)
            reserves[member_id] = reserve

        self.closing_reserves = reserves
        self.cleared.sort(key=lambda pair: pair[0]["claim_id"])

        for record in self.blocked:
            source = record["source"]
            self.blocked_by_source[source] = self.blocked_by_source.get(source, 0) + 1
        for _record, meta in self.cleared:
            self.carry_forward += bool(meta["carried"])
            self.day_shift += bool(meta["day_shift"])
            self.half_cent += bool(meta["half_cent"])

    def run(self):
        self.normalize()
        self.run_ladder()
        return self


# --------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------

def write_json(path, doc):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, sort_keys=True, indent=2)
        handle.write("\n")


def money_map(records, key):
    totals = defaultdict(int)
    for record in records:
        totals[record[key]] += record["cleared_usd_cents"]
    return dict(sorted(totals.items()))


def write_artifacts(pipe, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cleared = [record for record, _meta in pipe.cleared]

    with open(os.path.join(out_dir, "normalized.jsonl"), "w", encoding="utf-8") as handle:
        for record in cleared:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")

    skipped_count = sum(pipe.skipped_by_source.values())
    blocked_count = len(pipe.blocked)

    write_json(os.path.join(out_dir, "summary.json"), {
        "event_count": len(cleared),
        "skipped_count": skipped_count,
        "blocked_count": blocked_count,
        "orphan_recovery_count": len(pipe.orphan_ids),
        "total_usd_cents": sum(r["cleared_usd_cents"] for r in cleared),
        "net_units": sum(m["net_units"] for _r, m in pipe.cleared),
        "reserve_closing_usd_cents": sum(pipe.closing_reserves.values()),
        "by_region": money_map(cleared, "region"),
        "by_segment": money_map(cleared, "segment"),
        "by_kind": money_map(cleared, "kind"),
        "by_category": money_map(cleared, "category"),
        "by_lane": money_map(cleared, "lane"),
        "by_tariff_period": money_map(cleared, "tariff_period"),
        "by_source": money_map(cleared, "source"),
    })

    records_by_source = defaultdict(int)
    for record in cleared:
        records_by_source[record["source"]] += 1

    write_json(os.path.join(out_dir, "data_quality.json"), {
        "input_files": sorted(name for name in os.listdir(pipe.data_dir)
                              if os.path.isfile(os.path.join(pipe.data_dir, name))),
        "records_by_source": dict(sorted(records_by_source.items())),
        "skipped_by_source": dict(sorted(pipe.skipped_by_source.items())),
        "blocked_by_source": dict(sorted(pipe.blocked_by_source.items())),
        "skipped_count": skipped_count,
        "blocked_count": blocked_count,
        "orphan_recovery_count": len(pipe.orphan_ids),
        "blocked_claim_ids": sorted({r["claim_id"] for r in pipe.blocked}),
        "orphan_recovery_claim_ids": sorted(pipe.orphan_ids),
        "unmatched_amendment_targets": sorted(pipe.amendment_targets - pipe.claim_ids),
    })

    item_events = defaultdict(int)
    item_money = defaultdict(int)
    item_units = defaultdict(int)
    for record, meta in pipe.cleared:
        item_events[record["item_code"]] += 1
        item_money[record["item_code"]] += record["cleared_usd_cents"]
        item_units[record["item_code"]] += meta["net_units"]

    grams_per_kg = pipe.policy["grams_per_kilogram"]
    products = []
    for item_code in sorted(pipe.catalog):
        category, pack_mass = pipe.catalog[item_code]
        units = item_units.get(item_code, 0)
        mass = quantize(Decimal(units) * pack_mass * grams_per_kg,
                        pipe.policy["mass_scale"], pipe.policy["mass_mode"])
        products.append({
            "item_code": item_code,
            "category": category,
            "event_count": item_events.get(item_code, 0),
            "total_usd_cents": item_money.get(item_code, 0),
            "net_units": units,
            "on_hand_grams": pipe.on_hand.get(item_code, 0),
            "reorder_point_grams": pipe.reorder.get(item_code, 0),
            "net_mass_grams": int(mass),
        })
    write_json(os.path.join(out_dir, "product_summary.json"), {"products": products})

    buckets = (("region", REGIONS, "region_%s.json", None),
               ("segment", SEGMENTS, "segment_%s.json", "reserve_floor_usd_cents"))
    for field, values, filename, extra in buckets:
        for value in values:
            subset = [pair for pair in pipe.cleared if pair[0][field] == value]
            rows = [record for record, _meta in subset]
            doc = {
                field: value,
                "event_count": len(rows),
                "total_usd_cents": sum(r["cleared_usd_cents"] for r in rows),
                "net_units": sum(m["net_units"] for _r, m in subset),
                "blocked_count": sum(1 for r in pipe.blocked if r[field] == value),
                "members": sorted({r["member_id"] for r in rows}),
                "by_kind": money_map(rows, "kind"),
                "by_category": money_map(rows, "category"),
            }
            if extra:
                doc[extra] = pipe.policy["floors"][value]
            write_json(os.path.join(out_dir, filename % value), doc)


def closing_report(pipe):
    stale = 0
    for record, meta in pipe.cleared:
        if record["source"] == RECOVERIES and meta["link"] in pipe.skipped_dispense_ids:
            stale += 1
    uncatalogued = 0
    for row in read_rows(os.path.join(pipe.data_dir, "stock_ledger.csv"), ","):
        if text(row.get("item_code")) not in pipe.catalog:
            uncatalogued += int(text(row.get("on_hand_grams")))
    return {
        "blocked_value_usd_cents": sum(r["cleared_usd_cents"] for r in pipe.blocked),
        "blocked_members": len({r["member_id"] for r in pipe.blocked}),
        "carry_forward_rate_events": pipe.carry_forward,
        "day_shift_events": pipe.day_shift,
        "amended_events": len(pipe.amended_ids),
        "half_cent_events": pipe.half_cent,
        "underwater_members": pipe.underwater_members,
        "uncatalogued_stock_grams": uncatalogued,
        "stale_link_recoveries": stale,
    }


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py <DATA_DIR> <OUT_DIR>\n")
        return 2
    pipe = Pipeline(argv[1]).run()
    write_artifacts(pipe, argv[2])
    report = closing_report(pipe)
    for key in sorted(report):
        print("%s: %d" % (key, report[key]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
