#!/usr/bin/env python3
"""Reference oracle, derived from /app/data/schema.md alone.

Installs /app/out/transform.py (the reusable posting pipeline the instruction
asks for), runs it once over the shipped book, and prints the nine closing
report figures the contract defines.

This transform is written independently of the verifier's own expectation
engine: it keeps the reference tables in a flat NamedTuple built by separate
loader functions rather than one object, resolves rates and billing cycles by
bisecting parallel sorted lists, folds the zone hierarchy once up front into a
precomputed ancestor map, indexes amendments as a nested target/field mapping,
carries each posting as a NamedTuple whose own fields hold the report flags,
and settles each wallet through a generator. Agreement between two independent
readings of the contract is the only thing the oracle run actually proves, so
the two sides are deliberately not the same program.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

TRANSFORM = r'''#!/usr/bin/env python3
"""Post one BY41 metering book into the canonical artifacts (see schema.md).

Usage: transform.py [INPUT_DIR] [OUTPUT_DIR]. The INPUT_DIR / OUTPUT_DIR
environment variables, then /app/data and /app/out, are the fallbacks.
"""
import bisect
import configparser
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import NamedTuple

REPORTING_ZONES = ("central", "east", "north", "south", "west")
TARIFF_CLASSES = ("consumer", "corporate", "enterprise", "smb")
FEED_FILES = ("consumption.csv", "remittances.tsv", "levies.jsonl", "legacy_reads.txt")
LEGACY_FIELDS = ("reading_id", "read_ts", "account_id", "tariff_code", "meter_site",
                 "kind", "units_consumed", "amount", "currency", "collector", "memo")
# Every column of each feed except reading_id, which the contract never replaces.
MUTABLE_FIELDS = {
    "consumption.csv": frozenset({
        "read_ts", "account_id", "tariff_code", "meter_site", "units_consumed",
        "rate_per_unit", "currency", "collector"}),
    "remittances.tsv": frozenset({
        "read_ts", "account_id", "tariff_code", "meter_site", "units_consumed",
        "remit_amount", "currency", "collector", "charge_reading_id"}),
    "levies.jsonl": frozenset({
        "read_ts", "account_id", "tariff_code", "kind", "amount_minor",
        "currency", "note"}),
    "legacy_reads.txt": frozenset({
        "read_ts", "account_id", "tariff_code", "meter_site", "kind",
        "units_consumed", "amount", "currency", "collector", "memo"}),
}
LEGACY_POLARITY = {"consumption": -1, "surcharge": -1, "remittance": 1, "rebate": 1}
NET_UNIT_POLARITY = {"consumption": 1, "remittance": -1}
ROUNDING_MODES = {"half_up": ROUND_HALF_UP, "half_even": ROUND_HALF_EVEN,
                  "half_down": ROUND_HALF_DOWN}
BREAKDOWN_FIELDS = ("zone", "tariff_class", "kind", "category", "route_group",
                    "billing_cycle", "source")
LEVY_FEED = "levies.jsonl"


class Malformed(Exception):
    """A field or a lookup the contract calls malformed."""


PARSE_FAILURES = (Malformed, ArithmeticError, ValueError, TypeError,
                  AttributeError, KeyError)


class Posting(NamedTuple):
    """One resolved reading, plus the three flags the closing report counts."""

    reading_id: str
    posting_date: str
    utc_instant: str
    billing_cycle: str
    account_id: str
    tariff_class: str
    zone: str
    tariff_code: str
    category: str
    kind: str
    units: int
    posted_usd_cents: int
    currency: str
    source: str
    route_group: str
    meter_site: object
    rate_carried_back: bool
    crossed_a_day: bool
    sat_on_the_half_cent: bool
    charge_link: str


class Refs(NamedTuple):
    """Every reference table the resolution chain crosses."""

    floors: dict
    opening_day: str
    rounding: object
    litres_per_kilolitre: Decimal
    gap_cycle: str
    levy_lane: str
    accounts: dict
    prefix_zone: dict
    prefix_currency: dict
    ancestor: dict
    category: dict
    unit_volume: dict
    lanes: dict
    site_postcode: dict
    site_shift: dict
    installed_litres: dict
    service_floor_litres: dict
    uncatalogued_capacity_litres: int
    rate_days: dict
    rate_values: dict
    cycle_opens: list
    cycle_closes: list
    cycle_names: list


def clean(raw):
    """Trim a field the way the contract trims every value before use."""
    return "" if raw is None else str(raw).strip()


def folded(raw):
    return clean(raw).lower()


def read_table(path, delimiter=","):
    with open(path, encoding="utf-8", newline="") as handle:
        return [dict(record) for record in csv.DictReader(handle, delimiter=delimiter)]


def whole_number(raw):
    """units_consumed is ASCII digits and nothing else."""
    text = clean(raw)
    if not text or not text.isascii() or not text.isdigit():
        raise Malformed("units_consumed")
    return int(text)


def wall_clock(raw):
    """read_ts is YYYY-MM-DDTHH:MM:SS, naming a day that really exists."""
    text = clean(raw)
    if text.endswith("Z"):
        text = text[:-1]
    calendar, _, clock = text.partition("T")
    pieces = calendar.split("-") + clock.split(":")
    if len(pieces) != 6:
        raise Malformed("read_ts")
    try:
        numbers = [int(piece) for piece in pieces]
        return datetime(*numbers)
    except (TypeError, ValueError) as flaw:
        raise Malformed("read_ts") from flaw


def decimal_field(raw):
    try:
        return Decimal(clean(raw))
    except ArithmeticError as flaw:
        raise Malformed("amount") from flaw


def load_policy(folder):
    rules = configparser.ConfigParser()
    rules.read_string((folder / "policy.ini").read_text(encoding="utf-8"))
    floors = {}
    for key, text in rules["disconnection"].items():
        floors[key.split("_")[1]] = int(text)
    return (floors,
            clean(rules["wallet"]["opening_rate_date"]),
            ROUNDING_MODES[folded(rules["rounding"]["mode"])],
            Decimal(clean(rules["volume"]["litres_per_kilolitre"])),
            clean(rules["labels"]["unassigned_cycle"]),
            folded(rules["labels"]["levy_route_group"]))


def load_accounts(folder):
    """The row with the greatest revised_at wins; a shared greatest takes the
    later line in file order."""
    winner = {}
    surviving = {}
    for position, row in enumerate(read_table(folder / "accounts.csv")):
        account_id = clean(row["account_id"])
        stamp = (clean(row["revised_at"]), position)
        if account_id in winner and stamp < winner[account_id]:
            continue
        winner[account_id] = stamp
        surviving[account_id] = {
            "tariff_class": folded(row["tariff_class"]),
            "service_postcode": clean(row["service_postcode"]),
            "opening_credit_minor": clean(row["opening_credit_minor"]),
            "opening_currency": clean(row["opening_currency"]).upper(),
        }
    return surviving


def fold_ancestors(parent_of):
    """Collapse the whole zone hierarchy to a top level ancestor map once, with
    path compression, so a record only ever does a dict lookup."""
    ancestor = {}
    for start in parent_of:
        walked = []
        node = start
        guard = set()
        while node not in ancestor and parent_of.get(node) and node not in guard:
            guard.add(node)
            walked.append(node)
            node = parent_of[node]
        top = ancestor.get(node, node)
        for step in walked:
            ancestor[step] = top
        ancestor[start] = top
    return ancestor


def load_zones(folder):
    prefix_zone = {}
    prefix_currency = {}
    parent_of = {}
    for row in read_table(folder / "service_zones.csv"):
        prefix = clean(row["postcode_prefix"])
        zone = folded(row["zone"])
        prefix_zone[prefix] = zone
        prefix_currency[prefix] = clean(row["default_currency"]).upper()
        parent_of[zone] = folded(row["parent_zone"])
    return prefix_zone, prefix_currency, fold_ancestors(parent_of)


def load_catalogue(folder):
    """A tariff code counts whether or not it is retired."""
    category = {}
    unit_volume = {}
    for row in read_table(folder / "tariff_catalogue.csv"):
        code = clean(row["tariff_code"])
        category[code] = folded(row["category"])
        unit_volume[code] = Decimal(clean(row["unit_volume_litres"]))
    return category, unit_volume


def load_sites(folder, category):
    """Capacity figures are summed over every row for a tariff code."""
    postcode = {}
    shift = {}
    installed = Counter()
    service_floor = Counter()
    for row in read_table(folder / "meter_sites.csv"):
        site = clean(row["meter_site"])
        postcode[site] = clean(row["postcode"])
        shift[site] = int(clean(row["utc_offset_minutes"]))
        code = clean(row["tariff_code"])
        installed[code] += int(clean(row["installed_litres"]))
        service_floor[code] += int(clean(row["service_floor_litres"]))
    stranded = sum(litres for code, litres in installed.items() if code not in category)
    return postcode, shift, dict(installed), dict(service_floor), stranded


def load_rates(folder):
    """Two parallel sorted lists per currency, so a posting date is resolved by
    bisecting the day column."""
    gathered = defaultdict(dict)
    for row in read_table(folder / "currency_rates.csv"):
        currency = clean(row["currency"]).upper()
        gathered[currency][clean(row["rate_date"])] = Decimal(clean(row["usd_rate"]))
    days = {}
    values = {}
    for currency, curve in gathered.items():
        ordered = sorted(curve)
        days[currency] = ordered
        values[currency] = [curve[day] for day in ordered]
    return days, values


def load_calendar(folder):
    almanac = json.loads((folder / "billing_calendar.json").read_text(encoding="utf-8"))
    spans = sorted((clean(cycle["opens"]), clean(cycle["closes"]), clean(cycle["cycle"]))
                   for cycle in almanac["cycles"])
    return ([opens for opens, _, _ in spans],
            [closes for _, closes, _ in spans],
            [name for _, _, name in spans])


def load_refs(folder):
    floors, opening_day, rounding, litres, gap_cycle, levy_lane = load_policy(folder)
    prefix_zone, prefix_currency, ancestor = load_zones(folder)
    category, unit_volume = load_catalogue(folder)
    postcode, shift, installed, service_floor, stranded = load_sites(folder, category)
    rate_days, rate_values = load_rates(folder)
    opens, closes, names = load_calendar(folder)
    return Refs(
        floors=floors,
        opening_day=opening_day,
        rounding=rounding,
        litres_per_kilolitre=litres,
        gap_cycle=gap_cycle,
        levy_lane=levy_lane,
        accounts=load_accounts(folder),
        prefix_zone=prefix_zone,
        prefix_currency=prefix_currency,
        ancestor=ancestor,
        category=category,
        unit_volume=unit_volume,
        lanes={folded(row["collector"]): folded(row["route_group"])
               for row in read_table(folder / "collectors.csv")},
        site_postcode=postcode,
        site_shift=shift,
        installed_litres=installed,
        service_floor_litres=service_floor,
        uncatalogued_capacity_litres=stranded,
        rate_days=rate_days,
        rate_values=rate_values,
        cycle_opens=opens,
        cycle_closes=closes,
        cycle_names=names,
    )


def usd_rate_on(refs, day, currency):
    """The row for that exact date, else the most recent earlier one. Reaching
    backwards is the only direction allowed."""
    column = refs.rate_days.get(currency)
    if not column:
        raise Malformed("usd_rate")
    slot = bisect.bisect_right(column, day) - 1
    if slot < 0:
        raise Malformed("usd_rate")
    return refs.rate_values[currency][slot], column[slot] != day


def cycle_covering(refs, day):
    slot = bisect.bisect_right(refs.cycle_opens, day) - 1
    if slot >= 0 and day <= refs.cycle_closes[slot]:
        return refs.cycle_names[slot]
    return refs.gap_cycle


def to_usd_cents(refs, gross, rate):
    """One exact decimal expression, quantized exactly once and nowhere earlier."""
    product = gross * rate * 100
    return int(product.quantize(Decimal(1), rounding=refs.rounding)), product


def sits_on_half_cent(product):
    doubled = product * 2
    return doubled == doubled.to_integral_value() and doubled % 2 != 0


def opening_wallet(refs, account_id):
    seat = refs.accounts[account_id]
    rate, _carried = usd_rate_on(refs, refs.opening_day, seat["opening_currency"])
    cents, _product = to_usd_cents(
        refs, Decimal(seat["opening_credit_minor"]) / 100, rate)
    return cents


def index_amendments(folder):
    """target -> field -> value, keeping the greatest utc_ts and breaking a
    shared greatest with the later line in file order."""
    champion = defaultdict(dict)
    text = (folder / "amendments.log").read_text(encoding="utf-8")
    for position, line in enumerate(text.splitlines()):
        words = line.split()
        if len(words) < 3 or words[2] != "amendment":
            continue
        tokens = {}
        for chunk in words[3:]:
            key, marker, value = chunk.partition("=")
            if marker:
                tokens[key] = value
        target = tokens.get("target")
        field = tokens.get("field")
        if target is None or field is None:
            continue
        stamp = (words[0], position)
        previous = champion[target].get(field)
        if previous is None or stamp > previous[0]:
            champion[target][field] = (stamp, tokens.get("value", ""))
    return {target: {field: payload for field, (_stamp, payload) in fields.items()}
            for target, fields in champion.items()}


def gather_rows(folder):
    """Every reading file present, as (feed, raw mapping) pairs. A line that
    cannot yield a mapping becomes an empty one, which fails every lookup and is
    therefore counted against its own file."""
    harvest = []
    if (folder / "consumption.csv").is_file():
        for row in read_table(folder / "consumption.csv"):
            harvest.append(("consumption.csv", row))
    if (folder / "remittances.tsv").is_file():
        for row in read_table(folder / "remittances.tsv", "\t"):
            harvest.append(("remittances.tsv", row))
    if (folder / LEVY_FEED).is_file():
        for line in (folder / LEVY_FEED).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                harvest.append((LEVY_FEED, json.loads(line)))
            except ValueError:
                harvest.append((LEVY_FEED, {}))
    if (folder / "legacy_reads.txt").is_file():
        body = (folder / "legacy_reads.txt").read_text(encoding="latin-1")
        for line in body.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) == 11:
                harvest.append(("legacy_reads.txt", dict(zip(LEGACY_FIELDS, cells))))
            else:
                harvest.append(("legacy_reads.txt", {}))
    return harvest


def apply_amendments(feed, row, patches):
    """Replace the named fields of this reading before any of it is parsed."""
    allowed = MUTABLE_FIELDS[feed]
    touched = False
    amended = dict(row)
    for field, value in patches.items():
        if field in allowed:
            amended[field] = value
            touched = True
    return amended, touched


def consumption_money(row):
    """A consumption draws the wallet down, so its gross is never positive."""
    units = whole_number(row.get("units_consumed"))
    return "consumption", units, -(decimal_field(row.get("rate_per_unit")) * units)


def remittance_money(row):
    """A remittance tops the wallet up whatever sign the column carries."""
    units = whole_number(row.get("units_consumed"))
    return "remittance", units, abs(decimal_field(row.get("remit_amount")))


def levy_money(row):
    """A levy carries its own sign in amount_minor, which must be a JSON
    integer; JSON booleans are ints in Python, so they are screened out."""
    kind = folded(row.get("kind"))
    if kind not in ("surcharge", "rebate"):
        raise Malformed("kind")
    minor = row.get("amount_minor")
    if isinstance(minor, bool) or not isinstance(minor, int):
        raise Malformed("amount_minor")
    return kind, 0, Decimal(minor) / 100


def legacy_money(row):
    """A legacy line is unsigned in practice; the kind token fixes the sign."""
    kind = folded(row.get("kind"))
    polarity = LEGACY_POLARITY.get(kind)
    if polarity is None:
        raise Malformed("kind")
    units = whole_number(row.get("units_consumed"))
    return kind, units, abs(decimal_field(row.get("amount"))) * polarity


MONEY_READERS = {
    "consumption.csv": consumption_money,
    "remittances.tsv": remittance_money,
    LEVY_FEED: levy_money,
    "legacy_reads.txt": legacy_money,
}


def kind_and_money(feed, row):
    """The reading's kind, its integer units, and the gross amount that reaches
    the wallet with the sign the contract gives it."""
    return MONEY_READERS[feed](row)


def locate(feed, row, refs):
    """Walk the resolution chain: account, postcode, zone, currency, instant,
    rate, route group and category."""
    account_id = clean(row.get("account_id"))
    code = clean(row.get("tariff_code"))
    if account_id not in refs.accounts:
        raise Malformed("account_id")
    if code not in refs.category:
        raise Malformed("tariff_code")
    seat = refs.accounts[account_id]
    if feed == LEVY_FEED:
        site = None
        postcode = seat["service_postcode"]
        minutes = 0
        lane = refs.levy_lane
    else:
        site = clean(row.get("meter_site"))
        if site not in refs.site_postcode:
            raise Malformed("meter_site")
        postcode = refs.site_postcode[site]
        minutes = refs.site_shift[site]
        collector = folded(row.get("collector"))
        if collector not in refs.lanes:
            raise Malformed("collector")
        lane = refs.lanes[collector]
    prefix = postcode.partition("-")[0].strip()
    if prefix not in refs.prefix_zone:
        raise Malformed("postcode_prefix")
    leaf = refs.prefix_zone[prefix]
    currency = clean(row.get("currency")).upper() or refs.prefix_currency[prefix]
    local = wall_clock(row.get("read_ts"))
    instant = local - timedelta(minutes=minutes)
    day = instant.date().isoformat()
    rate, carried = usd_rate_on(refs, day, currency)
    return (account_id, seat, code, site, lane,
            refs.ancestor.get(leaf, leaf), currency, local, instant, day, rate, carried)


def project(feed, row, refs):
    (account_id, seat, code, site, lane, zone, currency,
     local, instant, day, rate, carried) = locate(feed, row, refs)
    kind, units, gross = kind_and_money(feed, row)
    cents, product = to_usd_cents(refs, gross, rate)
    return Posting(
        reading_id=clean(row.get("reading_id")),
        posting_date=day,
        utc_instant=instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
        billing_cycle=cycle_covering(refs, day),
        account_id=account_id,
        tariff_class=seat["tariff_class"],
        zone=zone,
        tariff_code=code,
        category=refs.category[code],
        kind=kind,
        units=units,
        posted_usd_cents=cents,
        currency=currency,
        source=feed,
        route_group=lane,
        meter_site=site,
        rate_carried_back=carried,
        crossed_a_day=instant.date() != local.date(),
        sat_on_the_half_cent=sits_on_half_cent(product),
        charge_link=(clean(row.get("charge_reading_id"))
                     if feed == "remittances.tsv" else ""),
    )


def resolve_feeds(folder, refs):
    """Amend, screen remittance links, then project. Returns the survivors, the
    orphan ids, the per feed skip tally, the ids of consumption rows that were
    skipped, and the ids that an amendment actually reached."""
    patches = index_amendments(folder)
    rows = gather_rows(folder)
    present = [name for name in FEED_FILES if (folder / name).is_file()]
    raw_charge_ids = {clean(row.get("reading_id"))
                      for feed, row in rows if feed == "consumption.csv"}
    known_ids = {clean(row.get("reading_id")) for _feed, row in rows
                 if clean(row.get("reading_id"))}

    standing = []
    orphans = []
    skipped = {name: 0 for name in present}
    rotten_charges = set()
    amended_ids = set()
    for feed, row in rows:
        reading_id = clean(row.get("reading_id"))
        row, touched = apply_amendments(feed, row, patches.get(reading_id, {}))
        if touched:
            amended_ids.add(reading_id)
        if feed == "remittances.tsv":
            link = clean(row.get("charge_reading_id"))
            if link and link not in raw_charge_ids:
                orphans.append(reading_id)
                continue
        try:
            standing.append(project(feed, row, refs))
        except PARSE_FAILURES:
            skipped[feed] += 1
            if feed == "consumption.csv":
                rotten_charges.add(reading_id)
    unmatched = sorted({target for target in patches if target not in known_ids})
    return standing, orphans, skipped, rotten_charges, amended_ids, unmatched, present


def settle_wallets(refs, standing):
    """One chronological pass per account, carrying the balance forward so each
    reading is judged against the balance the earlier decisions left standing."""
    queued = defaultdict(list)
    for posting in standing:
        queued[posting.account_id].append(posting)
    posted = []
    held = []
    closing = 0
    for account_id, seat in refs.accounts.items():
        balance = opening_wallet(refs, account_id)
        limit = refs.floors[seat["tariff_class"]]
        for posting in sorted(queued.get(account_id, ()),
                              key=lambda item: (item.utc_instant, item.reading_id)):
            value = posting.posted_usd_cents
            if value < 0 and balance + value < limit:
                held.append(posting)
            else:
                balance += value
                posted.append(posting)
        closing += balance
    return posted, held, closing


def net_units_of(posting):
    return NET_UNIT_POLARITY.get(posting.kind, 0) * posting.units


def fold_cents(postings, field):
    pot = Counter()
    for posting in postings:
        pot[getattr(posting, field)] += posting.posted_usd_cents
    return dict(sorted(pot.items()))


def as_record(posting):
    """The canonical posting record: exactly the sixteen contract keys."""
    return {
        "reading_id": posting.reading_id,
        "posting_date": posting.posting_date,
        "utc_instant": posting.utc_instant,
        "billing_cycle": posting.billing_cycle,
        "account_id": posting.account_id,
        "tariff_class": posting.tariff_class,
        "zone": posting.zone,
        "tariff_code": posting.tariff_code,
        "category": posting.category,
        "kind": posting.kind,
        "units": posting.units,
        "posted_usd_cents": posting.posted_usd_cents,
        "currency": posting.currency,
        "source": posting.source,
        "route_group": posting.route_group,
        "meter_site": posting.meter_site,
    }


def bucket_payload(posted, held, field, name, extra=None):
    mine = [p for p in posted if getattr(p, field) == name]
    payload = {
        field: name,
        "event_count": len(mine),
        "total_usd_cents": sum(p.posted_usd_cents for p in mine),
        "net_units": sum(net_units_of(p) for p in mine),
        "held_count": sum(1 for p in held if getattr(p, field) == name),
        "accounts": sorted({p.account_id for p in mine}),
        "by_kind": fold_cents(mine, "kind"),
        "by_category": fold_cents(mine, "category"),
    }
    if extra:
        payload.update(extra)
    return payload


def tariff_shelf(refs, posted):
    grouped = defaultdict(list)
    for posting in posted:
        grouped[posting.tariff_code].append(posting)
    shelf = []
    for code in sorted(refs.category):
        mine = grouped.get(code, [])
        net = sum(net_units_of(p) for p in mine)
        volume = Decimal(net) * refs.unit_volume[code] * refs.litres_per_kilolitre
        shelf.append({
            "tariff_code": code,
            "category": refs.category[code],
            "event_count": len(mine),
            "total_usd_cents": sum(p.posted_usd_cents for p in mine),
            "net_units": net,
            "installed_litres": refs.installed_litres.get(code, 0),
            "service_floor_litres": refs.service_floor_litres.get(code, 0),
            "net_volume_litres": int(volume.quantize(Decimal(1),
                                                     rounding=refs.rounding)),
        })
    return {"tariffs": shelf}


def post_book(folder):
    """Return (artifact payloads, closing report figures)."""
    refs = load_refs(folder)
    (standing, orphans, skipped, rotten_charges,
     amended_ids, unmatched, present) = resolve_feeds(folder, refs)
    posted, held, closing = settle_wallets(refs, standing)
    posted.sort(key=lambda posting: posting.reading_id)

    skipped_total = sum(skipped.values())
    overview = {
        "event_count": len(posted),
        "skipped_count": skipped_total,
        "held_count": len(held),
        "orphan_remittance_count": len(orphans),
        "total_usd_cents": sum(p.posted_usd_cents for p in posted),
        "net_units": sum(net_units_of(p) for p in posted),
        "wallet_closing_usd_cents": closing,
    }
    for field in BREAKDOWN_FIELDS:
        overview["by_" + field] = fold_cents(posted, field)

    produced = Counter(p.source for p in posted)
    held_feed = {name: 0 for name in present}
    for posting in held:
        held_feed[posting.source] += 1

    payloads = {
        "normalized.jsonl": [as_record(p) for p in posted],
        "summary.json": overview,
        "data_quality.json": {
            "input_files": sorted(entry.name for entry in folder.iterdir()
                                  if entry.is_file()),
            "records_by_source": dict(sorted(produced.items())),
            "skipped_by_source": dict(sorted(skipped.items())),
            "held_by_source": dict(sorted(held_feed.items())),
            "skipped_count": skipped_total,
            "held_count": len(held),
            "orphan_remittance_count": len(orphans),
            "held_reading_ids": sorted({p.reading_id for p in held}),
            "orphan_remittance_ids": sorted(set(orphans)),
            "unmatched_amendment_targets": unmatched,
        },
        "product_summary.json": tariff_shelf(refs, posted),
    }
    for name in REPORTING_ZONES:
        payloads["region_%s.json" % name] = bucket_payload(posted, held, "zone", name)
    for name in TARIFF_CLASSES:
        payloads["segment_%s.json" % name] = bucket_payload(
            posted, held, "tariff_class", name,
            {"disconnection_floor_usd_cents": refs.floors[name]})

    closing_report = {
        "held_value_usd_cents": sum(p.posted_usd_cents for p in held),
        "held_accounts": len({p.account_id for p in held}),
        "carry_back_rate_events": sum(1 for p in posted if p.rate_carried_back),
        "day_shift_events": sum(1 for p in posted if p.crossed_a_day),
        "amended_readings": len(amended_ids),
        "half_cent_events": sum(1 for p in posted if p.sat_on_the_half_cent),
        "underfunded_accounts": sum(
            1 for account_id, seat in refs.accounts.items()
            if opening_wallet(refs, account_id) < refs.floors[seat["tariff_class"]]),
        "uncatalogued_capacity_litres": refs.uncatalogued_capacity_litres,
        "stale_link_remittances": sum(
            1 for p in posted if p.charge_link and p.charge_link in rotten_charges),
    }
    return payloads, closing_report


def emit(payloads, out_dir):
    """Compact sorted lines for the stream, two space indent for the documents,
    a closing newline on both."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stream = payloads["normalized.jsonl"]
    (out_dir / "normalized.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                for record in stream), encoding="utf-8")
    for name, payload in payloads.items():
        if name.endswith(".jsonl"):
            continue
        (out_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv):
    data = Path(argv[1]) if len(argv) > 1 else Path(os.environ.get("INPUT_DIR", "/app/data"))
    out = Path(argv[2]) if len(argv) > 2 else Path(os.environ.get("OUTPUT_DIR", "/app/out"))
    payloads, report = post_book(data)
    emit(payloads, out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''


def main() -> int:
    data = Path(os.environ.get("INPUT_DIR", "/app/data"))
    out = Path(os.environ.get("OUTPUT_DIR", "/app/out"))
    out.mkdir(parents=True, exist_ok=True)
    script = out / "transform.py"
    script.write_text(TRANSFORM, encoding="utf-8")
    script.chmod(0o755)
    sys.argv = [str(script), str(data), str(out)]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
