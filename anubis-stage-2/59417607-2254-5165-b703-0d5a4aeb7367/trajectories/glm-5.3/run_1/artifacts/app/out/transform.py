#!/usr/bin/env python3
"""Billing run for one billing cycle extract.

Usage: python3 transform.py DATA_DIR OUT_DIR

Reads the extract in DATA_DIR, writes the reports of the report layout into
OUT_DIR and prints one line per written report.  Only the Python standard
library is used; no network connection is opened and no other process is
started.
"""

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

REGIONS = ("central", "east", "north", "south", "west")
SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
# Order in which candidate handset clock offsets are examined.
OFFSET_CANDIDATES = tuple(range(0, 20)) + tuple(range(-19, 0))


# --------------------------------------------------------------- small helpers

def ceil_div(value, divisor):
    return -(-value // divisor)


def parse_instant(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")


def parse_day(text):
    return datetime.strptime(text, "%Y-%m-%d").date()


def parse_legacy_instant(text):
    return datetime.strptime(text, "%d.%m.%Y %H:%M:%S")


def format_instant(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def format_day(day):
    return day.strftime("%Y-%m-%d")


def to_cents(micro):
    """Micro-units to whole cents, an exact half going to the even cent."""
    negative = micro < 0
    value = -micro if negative else micro
    units, rest = divmod(value, 10000)
    if 2 * rest > 10000 or (2 * rest == 10000 and units % 2 == 1):
        units += 1
    return -units if negative else units


def dumps(payload):
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"),
                      sort_keys=True)


def read_csv_rows(path):
    """Rows of a CSV file as dictionaries of stripped strings."""
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        rows = [row for row in reader if row]
    if not rows:
        return []
    header = [name.strip() for name in rows[0]]
    out = []
    for row in rows[1:]:
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        out.append({header[i]: row[i].strip() for i in range(len(header))})
    return out


def read_json(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def read_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


# ------------------------------------------------------------------- extract

class Closing(object):
    __slots__ = ("ref", "handset", "seq", "client", "code", "stamped",
                 "worked", "line", "segment", "region",
                 "completion", "service", "product_line", "increment",
                 "local", "local_day", "tier", "rate", "rejected",
                 "outside", "void", "unrated", "worked_final",
                 "billable", "credited", "charged", "gross", "net")

    def __init__(self, ref, handset, seq, client, code, stamped, worked):
        self.ref = ref
        self.handset = handset
        self.seq = seq
        self.client = client
        self.code = code
        self.stamped = stamped
        self.worked = worked
        self.void = False
        self.rejected = None
        self.outside = False
        self.unrated = False
        self.credited = 0
        self.worked_final = worked

    @property
    def billed(self):
        return (self.rejected is None and not self.void
                and not self.outside and not self.unrated)


def load_extract(data_dir):
    join = os.path.join
    cycle = read_json(join(data_dir, "cycle.json"))
    first_day = parse_day(cycle["first_day"])
    last_day = parse_day(cycle["last_day"])
    minimum_invoice = int(cycle["minimum_invoice_micro"])

    clients = {}
    for row in read_csv_rows(join(data_dir, "clients.csv")):
        clients[row["client"]] = row

    services = {}
    for row in read_csv_rows(join(data_dir, "service_catalog.csv")):
        services[row["service"].upper()] = row
    aliases = {}
    for row in read_csv_rows(join(data_dir, "code_aliases.csv")):
        aliases[row["alias"].upper()] = row["service"]

    plans = {}
    for row in read_csv_rows(join(data_dir, "plans.csv")):
        plans[row["plan"]] = {
            "included_minutes": int(row["included_minutes"]),
            "credit_tiers": set(row["credit_tiers"].split()),
        }

    zones = defaultdict(list)
    for row in read_csv_rows(join(data_dir, "zone_rules.csv")):
        zones[row["zone"]].append(
            (parse_instant(row["from_utc"]), int(row["utc_offset_minutes"])))
    for name in list(zones):
        zones[name].sort(key=lambda item: item[0])

    holidays = defaultdict(set)
    for row in read_csv_rows(join(data_dir, "holidays.csv")):
        holidays[row["region"]].add(parse_day(row["day"]))

    rates = defaultdict(list)
    for row in read_csv_rows(join(data_dir, cycle["rate_card"])):
        start = parse_day(row["effective_from"])
        end = parse_day(row["effective_to"]) if row["effective_to"] else None
        rates[(row["service"].upper(), row["tier"])].append(
            (start, end, int(row["rate_micro_per_minute"])))
    for key in list(rates):
        rates[key].sort(key=lambda item: item[0])

    return {
        "cycle": cycle,
        "first_day": first_day,
        "last_day": last_day,
        "minimum_invoice": minimum_invoice,
        "clients": clients,
        "services": services,
        "aliases": aliases,
        "plans": plans,
        "zones": dict(zones),
        "holidays": dict(holidays),
        "rates": dict(rates),
    }


def load_closings(data_dir):
    """Every received closing of the extract, plus the duplicate references."""
    main_rows = []
    main_keys = {}
    for row in read_csv_rows(os.path.join(data_dir, "closings.csv")):
        closing = Closing(row["ref"], row["handset"], int(row["seq"]),
                          row["client"], row["service"],
                          parse_instant(row["stamped_at"]),
                          int(row["worked_minutes"]))
        main_rows.append(closing)
        main_keys[(closing.handset, closing.seq)] = closing

    unit = "minutes"
    legacy_lines = []
    with open(os.path.join(data_dir, "legacy_closings.txt"),
              "r", encoding="utf-8-sig", newline="") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                parts = stripped.split(":", 1)
                if len(parts) == 2 and parts[0].strip() == "# duration unit":
                    unit = parts[1].strip()
                continue
            legacy_lines.append(stripped)

    legacy = {}
    duplicates = []
    for line in legacy_lines:
        fields = [field.strip() for field in line.split("|")]
        if len(fields) < 7:
            continue
        duration = int(fields[6])
        worked = ceil_div(duration, 60) if unit == "seconds" else duration
        closing = Closing(fields[0], fields[1], int(fields[2]), fields[3],
                           fields[4], parse_legacy_instant(fields[5]), worked)
        key = (closing.handset, closing.seq)
        if key in main_keys:
            duplicates.append(closing.ref)
            continue
        legacy.setdefault(key, closing)

    received = list(main_rows)
    received.extend(legacy[key] for key in sorted(legacy))
    return received, duplicates


def zone_offset(zones, zone, moment):
    rows = zones.get(zone)
    if not rows:
        return 0
    offset = rows[0][1]
    for start, value in rows:
        if moment >= start:
            offset = value
        else:
            break
    return offset


def load_register(data_dir):
    """Rows of the traffic register as slot counts.

    A slot is held by its line and by the minute index of the instant its day
    and its slot name both point at, so that a stamp moved across midnight by
    a clock offset still finds its row.
    """
    rows = {}
    for row in read_csv_rows(os.path.join(data_dir, "exchange_register.csv")):
        day = parse_day(row["day"])
        hour, minute = row["slot"].split(":")[:2]
        index = day.toordinal() * 1440 + int(hour) * 60 + int(minute)
        key = (row["line"], index)
        rows[key] = rows.get(key, 0) + int(row["calls"])
    return rows


def slot_index(moment):
    return (moment.toordinal() * 1440 + moment.hour * 60
            + moment.minute)


def infer_offsets(closings, clients, register):
    """Recover each handset's clock offset from the traffic register.

    A register row never counts more calls than the closings of its line have
    in its slot, so an offset that leaves register rows unaccounted for is
    impossible; among the possible offsets the one whose closings fall in
    registered slots most often is the handset's offset.
    """
    by_handset = defaultdict(list)
    for closing in closings:
        by_handset[closing.handset].append(closing)
    lines = {}
    slots = {}
    for closing in closings:
        if closing.client not in lines:
            lines[closing.client] = clients.get(
                closing.client, {}).get("line", "")
        slots[id(closing)] = slot_index(closing.stamped)

    offsets = {}
    for handset in sorted(by_handset):
        entries = by_handset[handset]
        best = None
        best_count = -1
        for offset in OFFSET_CANDIDATES:
            count = 0
            for closing in entries:
                line = lines[closing.client]
                if (line, slots[id(closing)] + offset) in register:
                    count += 1
            if count > best_count:
                best_count = count
                best = offset
        offsets[handset] = best

    # The register constraint holds for all handsets together, so an offset
    # that looks best on its own but leaves rows unaccounted for is wrong;
    # in that case take the next best offset of a handset that helps.
    for _ in range(25):
        occupied = defaultdict(int)
        for closing in closings:
            line = lines[closing.client]
            occupied[(line, slots[id(closing)]
                      + offsets[closing.handset])] += 1
        short = {key: calls - occupied.get(key, 0)
                 for key, calls in register.items()
                 if calls > occupied.get(key, 0)}
        if not short:
            break
        moved = False
        for handset in sorted(by_handset):
            entries = by_handset[handset]
            best = offsets[handset]
            best_gain = 0
            for offset in OFFSET_CANDIDATES:
                if offset == best:
                    continue
                gain = 0
                for closing in entries:
                    line = lines[closing.client]
                    if (line, slots[id(closing)] + offset) in short:
                        gain += 1
                if gain > best_gain:
                    best_gain = gain
                    best = offset
            if best != offsets[handset]:
                offsets[handset] = best
                moved = True
                break
        if not moved:
            break
    return offsets


# ---------------------------------------------------------------- the billing

def build(data_dir):
    extract = load_extract(data_dir)
    clients = extract["clients"]
    services = extract["services"]
    aliases = extract["aliases"]
    plans = extract["plans"]
    zones = extract["zones"]
    holidays = extract["holidays"]
    rates = extract["rates"]

    closings, duplicates = load_closings(data_dir)
    register = load_register(data_dir)
    offsets = infer_offsets(closings, clients, register)

    received_keys = {}
    for closing in closings:
        received_keys[(closing.handset, closing.seq)] = closing

    # Amendments.
    amendments = read_jsonl(os.path.join(data_dir, "amendments.jsonl"))
    by_identifier = {}
    for amendment in amendments:
        by_identifier[amendment.get("amendment")] = amendment
    voids_or_minutes = [item for item in amendments
                        if item.get("action") in ("void", "minutes")]

    cancelled = set()
    without_effect = set()
    for amendment in amendments:
        if amendment.get("action") != "revert":
            continue
        target = by_identifier.get(amendment.get("reverts"))
        if (target is not None and target.get("action") in ("void", "minutes")
                and parse_instant(amendment["issued_at"])
                > parse_instant(target["issued_at"])):
            cancelled.add(target["amendment"])
        else:
            without_effect.add(amendment["amendment"])

    ordered = []
    for amendment in voids_or_minutes:
        closing = received_keys.get((amendment.get("handset"),
                                    amendment.get("seq")))
        if closing is None:
            without_effect.add(amendment["amendment"])
            continue
        completion = closing.stamped + timedelta(
            minutes=offsets[closing.handset])
        if parse_instant(amendment["issued_at"]) < completion:
            without_effect.add(amendment["amendment"])
            continue
        if amendment["amendment"] in cancelled:
            without_effect.add(amendment["amendment"])
            continue
        ordered.append((parse_instant(amendment["issued_at"]),
                        amendment["amendment"], amendment))
    ordered.sort(key=lambda item: (item[0], item[1]))

    voided = set()
    for _, _, amendment in ordered:
        if amendment["action"] == "void":
            voided.add((amendment["handset"], amendment["seq"]))
    worked_override = {}
    for _, _, amendment in ordered:
        if amendment["action"] == "minutes":
            worked_override[(amendment["handset"], amendment["seq"])] = int(
                amendment["minutes"])

    # Service, completion instant, local day.
    for closing in closings:
        client = clients.get(closing.client, {})
        closing.line = client.get("line", "")
        closing.segment = client.get("segment", "")
        closing.region = client.get("region", "")
        closing.completion = closing.stamped + timedelta(
            minutes=offsets[closing.handset])
        code = closing.code.upper()
        if code in services:
            closing.service = services[code]["service"]
        elif code in aliases:
            closing.service = aliases[code]
        else:
            closing.service = None
            closing.rejected = "unknown_service"
        catalog = services.get(closing.service.upper()) \
            if closing.service else None
        closing.product_line = catalog["product_line"] if catalog else None
        closing.increment = int(catalog["increment_minutes"]) if catalog else None
        closing.local = closing.completion + timedelta(
            minutes=zone_offset(zones, client.get("zone", ""),
                               closing.completion))
        closing.local_day = closing.local.date()
        closing.outside = (closing.local_day < extract["first_day"]
                           or closing.local_day > extract["last_day"])

    for closing in closings:
        if (closing.handset, closing.seq) in voided:
            closing.void = True

    # Tier and rate.
    for closing in closings:
        if not closing.billed:
            closing.tier = None
            continue
        day = closing.local_day
        clock = (closing.local.hour, closing.local.minute, closing.local.second)
        if day.weekday() >= 5 or day in holidays.get(closing.region, ()):
            closing.tier = "weekend_holiday"
        elif (8, 0, 0) <= clock < (18, 0, 0):
            closing.tier = "standard"
        else:
            closing.tier = "after_hours"
        rate = None
        for start, end, value in rates.get(
                (closing.service.upper(), closing.tier), ()):
            if start <= day and (end is None or day < end):
                rate = value
                break
        if rate is None:
            closing.unrated = True
            closing.tier = None
        else:
            closing.rate = rate

    # Worked minutes and billable minutes.
    for closing in closings:
        key = (closing.handset, closing.seq)
        if key in worked_override:
            closing.worked_final = worked_override[key]
        if not closing.billed:
            continue
        closing.billable = ceil_div(closing.worked_final,
                                    closing.increment) * closing.increment

    # Allowance credit.
    eligible = defaultdict(list)
    for closing in closings:
        if not closing.billed:
            continue
        plan = plans.get(clients.get(closing.client, {}).get("plan", ""))
        if plan and closing.tier in plan["credit_tiers"]:
            eligible[closing.client].append(closing)
    for client in sorted(eligible):
        entries = eligible[client]
        plan = plans[clients[client]["plan"]]
        remaining = plan["included_minutes"]
        # Latest completion instant first; among equal completion instants the
        # closing whose reference comes first in code point order is first.
        entries.sort(key=lambda item: item.ref)
        entries.sort(key=lambda item: item.completion, reverse=True)
        for closing in entries:
            credit = min(closing.billable, remaining)
            closing.credited = credit
            remaining -= credit

    for closing in closings:
        if not closing.billed:
            continue
        closing.charged = closing.billable - closing.credited
        closing.gross = closing.billable * closing.rate
        closing.net = closing.charged * closing.rate

    billed = [closing for closing in closings if closing.billed]
    billed.sort(key=lambda item: (item.completion, item.ref))

    return {
        "extract": extract,
        "closings": closings,
        "billed": billed,
        "duplicates": duplicates,
        "offsets": offsets,
        "without_effect": sorted(without_effect),
        "cancelled": sorted(cancelled),
        "file_names": sorted(name for name in os.listdir(data_dir)
                             if os.path.isfile(os.path.join(data_dir, name))),
    }


# -------------------------------------------------------------------- reports

def group_body(name, closings, key, minimum_invoice):
    by_tier = defaultdict(int)
    gross = net = 0
    clients = set()
    for closing in closings:
        by_tier[closing.tier] += closing.net
        gross += closing.gross
        net += closing.net
        clients.add(closing.client)
    operand = gross if key == "region" else net
    return {
        "by_tier": dict(by_tier),
        "clients": sorted(clients),
        "closings": len(closings),
        "credit_micro": gross - net,
        "gross_micro": gross,
        "in_scope": operand >= minimum_invoice,
        "net_cents": to_cents(net),
        "net_micro": net,
        key: name,
    }


def write_report(out_dir, name, text, sizes):
    data = text.encode("ascii")
    with open(os.path.join(out_dir, name), "wb") as handle:
        handle.write(data)
    sizes[name] = len(data)


def run(data_dir, out_dir):
    state = build(data_dir)
    extract = state["extract"]
    closings = state["closings"]
    billed = state["billed"]
    minimum_invoice = extract["minimum_invoice"]

    os.makedirs(out_dir, exist_ok=True)
    sizes = {}

    # normalized.jsonl
    lines = []
    for closing in billed:
        lines.append(dumps({
            "billable_minutes": closing.billable,
            "charged_minutes": closing.charged,
            "client": closing.client,
            "completed_at": format_instant(closing.completion),
            "credited_minutes": closing.credited,
            "gross_micro": closing.gross,
            "handset": closing.handset,
            "line": closing.line,
            "local_day": format_day(closing.local_day),
            "net_micro": closing.net,
            "product_line": closing.product_line,
            "rate_micro_per_minute": closing.rate,
            "ref": closing.ref,
            "region": closing.region,
            "segment": closing.segment,
            "seq": closing.seq,
            "service": closing.service,
            "tier": closing.tier,
            "worked_minutes": closing.worked_final,
        }))
    write_report(out_dir, "normalized.jsonl",
                 "".join(line + "\n" for line in lines), sizes)

    # data_quality.json
    rejected = {}
    outside_cycle = []
    unrated = []
    void = []
    for closing in closings:
        if closing.rejected is not None:
            rejected[closing.ref] = closing.rejected
        elif closing.outside:
            outside_cycle.append(closing.ref)
        elif closing.void:
            void.append(closing.ref)
        elif closing.unrated:
            unrated.append(closing.ref)
    write_report(out_dir, "data_quality.json", dumps({
        "amendments_without_effect": state["without_effect"],
        "closings_received": len(closings),
        "duplicates": sorted(state["duplicates"]),
        "input_files": state["file_names"],
        "outside_cycle": sorted(outside_cycle),
        "rejected": rejected,
        "unrated": sorted(unrated),
        "void": sorted(void),
    }) + "\n", sizes)

    # product_summary.json
    product_lines = sorted({row["product_line"]
                            for row in extract["services"].values()})
    per_line = defaultdict(list)
    for closing in billed:
        per_line[closing.product_line].append(closing)
    product_lines_out = []
    for name in product_lines:
        entries = per_line.get(name, [])
        product_lines_out.append({
            "billable_minutes": sum(item.billable for item in entries),
            "closings": len(entries),
            "gross_micro": sum(item.gross for item in entries),
            "net_micro": sum(item.net for item in entries),
            "product_line": name,
        })
    write_report(out_dir, "product_summary.json",
                 dumps({"product_lines": product_lines_out}) + "\n", sizes)

    # region and segment reports
    regions = sorted(set(REGIONS) | {row["region"]
                                    for row in extract["clients"].values()})
    segments = sorted(set(SEGMENTS) | {row["segment"]
                                      for row in extract["clients"].values()})
    per_region = defaultdict(list)
    per_segment = defaultdict(list)
    for closing in billed:
        per_region[closing.region].append(closing)
        per_segment[closing.segment].append(closing)
    region_bodies = {}
    segment_bodies = {}
    for name in regions:
        body = group_body(name, per_region.get(name, []), "region",
                          minimum_invoice)
        region_bodies[name] = body
        write_report(out_dir, "region_%s.json" % name, dumps(body) + "\n", sizes)
    for name in segments:
        body = group_body(name, per_segment.get(name, []), "segment",
                          minimum_invoice)
        segment_bodies[name] = body
        write_report(out_dir, "segment_%s.json" % name, dumps(body) + "\n",
                     sizes)

    # summary.json
    summary_by_tier = defaultdict(int)
    gross = net = 0
    for closing in billed:
        summary_by_tier[closing.tier] += closing.net
        gross += closing.gross
        net += closing.net
    normalized_net = sum(closing.net for closing in billed)
    product_net = sum(item["net_micro"] for item in product_lines_out)
    region_net = sum(body["net_micro"] for body in region_bodies.values())
    segment_net = sum(body["net_micro"] for body in segment_bodies.values())
    write_report(out_dir, "summary.json", dumps({
        "by_tier": dict(summary_by_tier),
        "closings_billed": len(billed),
        "credit_micro": gross - net,
        "cycle": extract["cycle"]["cycle"],
        "gross_micro": gross,
        "net_cents": to_cents(net),
        "net_micro": net,
        "reconciliation": {
            "normalized_net_micro": normalized_net,
            "product_net_micro": product_net,
            "region_net_micro": region_net,
            "residual_micro": product_net + region_net + segment_net
                              - 3 * normalized_net,
            "segment_net_micro": segment_net,
        },
    }) + "\n", sizes)

    for name in sorted(sizes):
        sys.stdout.write("wrote %s %d\n" % (name, sizes[name]))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py DATA_DIR OUT_DIR\n")
        return 2
    run(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
