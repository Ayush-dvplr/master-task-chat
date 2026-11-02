#!/usr/bin/env python3
"""Compliance report for one extract of the particulate monitoring network.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ORIGIN = date(1970, 1, 1)
WIDEST_OFFSET = 19
DISTRICT_FILES = ("North", "South", "West", "East")
OPERATOR_FILES = ("commercial", "public")


class ExtractError(Exception):
    """The extract cannot be read or its evidence does not settle a value."""


# ------------------------------------------------------------------ reading


def minutes(stamp):
    """'YYYY-MM-DDTHH:MM' to whole minutes since 1970-01-01T00:00."""
    try:
        day = date(int(stamp[0:4]), int(stamp[5:7]), int(stamp[8:10]))
        if stamp[10] != "T" or stamp[13] != ":" or len(stamp) != 16:
            raise ValueError(stamp)
        return (day - ORIGIN).days * 1440 + int(stamp[11:13]) * 60 + int(stamp[14:16])
    except (ValueError, IndexError) as exc:
        raise ExtractError(f"bad time {stamp!r}") from exc


def day_text(day_number):
    return (ORIGIN + timedelta(days=day_number)).isoformat()


def rows_of(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def json_of(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def channel_key(label):
    return label.strip().upper()


def site_key(site_id):
    return int(site_id[1:])


def ratio(text):
    """Exact decimal text as (numerator, denominator)."""
    text = text.strip()
    whole, _, fraction = text.partition(".")
    return int(whole + fraction), 10 ** len(fraction)


def corrected_tenths(raw, factor):
    numerator, denominator = ratio(factor)
    # half up, on non-negative values
    return (2 * raw * numerator + denominator) // (2 * denominator)


class Extract:
    def __init__(self, folder):
        folder = Path(folder)
        self.manifest = json_of(folder / "extract_manifest.json")
        self.policy = self._current(folder, "network_policy*.json", "policy_revision", json_of,
                                    lambda doc: doc.get("revision"))
        self.register = self._current(folder, "span_register*.csv", "span_register_revision", rows_of,
                                      lambda rows: rows[0]["revision"] if rows else None)
        self.zone = json_of(folder / "zone_rules.json")
        self.sites = rows_of(folder / "site_register.csv")
        self.deployments = rows_of(folder / "unit_deployments.csv")
        self.tags = rows_of(folder / "asset_tags.csv")
        self.card = rows_of(folder / "card_readings.csv")
        self.journal = rows_of(folder / "receipt_journal.csv")
        self.maintenance = json_of(folder / "maintenance_log.json")

    def _current(self, folder, pattern, manifest_key, loader, revision_of):
        wanted = self.manifest[manifest_key]
        found = [loaded for loaded in (loader(p) for p in sorted(folder.glob(pattern))) if revision_of(loaded) == wanted]
        if len(found) != 1:
            raise ExtractError(f"{len(found)} files match revision {wanted} for {pattern}")
        return found[0]


# ------------------------------------------------------------------ clocks


class Unit:
    def __init__(self, name, channel):
        self.name = name
        self.channel = channel
        self.stamps = []
        self.frames = []
        self.rows = []
        self.offsets = []

    def true_minute(self, index):
        return self.stamps[index] - self.offsets[index]


def gather_units(extract):
    channel_of = {}
    for row in extract.deployments:
        label = channel_key(row["channel"])
        if channel_of.setdefault(row["unit_id"], label) != label:
            raise ExtractError(f"unit {row['unit_id']} listed on two channels")
    units = {}
    for row in extract.card:
        name = row["unit_id"]
        if name not in channel_of:
            raise ExtractError(f"card unit {name} has no deployment")
        units.setdefault(name, Unit(name, channel_of[name])).rows.append(row)
    for unit in units.values():
        unit.rows.sort(key=lambda r: minutes(r["card_stamp"]))
        unit.stamps = [minutes(r["card_stamp"]) for r in unit.rows]
        unit.frames = [int(r["frame"]) for r in unit.rows]
        if any(a >= b for a, b in zip(unit.stamps, unit.stamps[1:])):
            raise ExtractError(f"unit {unit.name} repeats a card stamp")
    return units


def heard_packets(extract):
    heard = {}
    for row in extract.journal:
        key = (channel_key(row["channel"]), minutes(row["received_utc"]))
        if key in heard:
            raise ExtractError(f"two packets on {key[0]} in minute {row['received_utc']}")
        heard[key] = int(row["frame"])
    return heard


def settle_clocks(units, heard):
    """Give every card row the clock offset the receipt journal pins for it.

    A journal entry that only one card row (at one offset) can explain pins that
    row. Rows between two pins with the same offset share it; an offset change
    must sit between two adjacent pinned rows. Every journal entry must then be
    explained, no two packets may share a minute on a channel, and true time must
    run forward along every card.
    """
    explain = {}
    for unit in units.values():
        for index, (stamp, frame) in enumerate(zip(unit.stamps, unit.frames)):
            for offset in range(-WIDEST_OFFSET, WIDEST_OFFSET + 1):
                key = (unit.channel, stamp - offset)
                if heard.get(key) == frame:
                    explain.setdefault(key, []).append((unit.name, index, offset))
    pins = {name: {} for name in units}
    for key, options in explain.items():
        if len(options) == 1:
            name, index, offset = options[0]
            if pins[name].setdefault(index, offset) != offset:
                raise ExtractError(f"unit {name} row {index} pinned to two offsets")
    for name, unit in units.items():
        pinned = sorted(pins[name].items())
        if not pinned:
            raise ExtractError(f"no journal entry settles the clock of unit {name}")
        offsets = [None] * len(unit.stamps)
        first_index, first_offset = pinned[0]
        for index in range(0, first_index + 1):
            offsets[index] = first_offset
        for (a, x), (b, y) in zip(pinned, pinned[1:]):
            if x != y and b != a + 1:
                raise ExtractError(f"unit {name}: offset change between rows {a} and {b} is not pinned")
            for index in range(a + 1, b):
                offsets[index] = x
            offsets[b] = y
        last_index, last_offset = pinned[-1]
        for index in range(last_index, len(offsets)):
            offsets[index] = last_offset
        unit.offsets = offsets

    used = {}
    for unit in units.values():
        previous = None
        for index in range(len(unit.stamps)):
            moment = unit.true_minute(index)
            if previous is not None and moment <= previous:
                raise ExtractError(f"unit {unit.name}: true time runs backward at row {index}")
            previous = moment
            key = (unit.channel, moment)
            if key in used:
                raise ExtractError(f"units {used[key]} and {unit.name} share a minute on {unit.channel}")
            used[key] = unit.name
    for key, frame in heard.items():
        owner = used.get(key)
        if owner is None:
            raise ExtractError(f"journal entry {key} is explained by no card row")
    received = {name: 0 for name in units}
    for unit in units.values():
        for index in range(len(unit.stamps)):
            key = (unit.channel, unit.true_minute(index))
            if key in heard:
                if heard[key] != unit.frames[index]:
                    raise ExtractError(f"journal entry {key} carries another frame than unit {unit.name} wrote")
                received[unit.name] += 1
    if sum(received.values()) != len(heard):
        raise ExtractError("journal entries left unexplained")
    return received


# ------------------------------------------------------------------ registers


def civil_to_utc(moment, zone):
    standard = zone["standard_offset_minutes"]
    for period in zone["daylight_saving"]:
        start = minutes(period["begins"]) - standard
        stop = minutes(period["ends"]) - standard - period["shift_minutes"]
        guess = moment - standard - period["shift_minutes"]
        if start <= guess < stop:
            return guess
    return moment - standard


def maintenance_windows(extract):
    log = extract.maintenance
    basis = log["time_basis"]
    if basis not in ("civil", "utc"):
        raise ExtractError(f"unknown maintenance time basis {basis!r}")
    windows = {}
    for entry in log["entries"]:
        begins, ends = minutes(entry["begins"]), minutes(entry["ends"])
        if basis == "civil":
            begins, ends = civil_to_utc(begins, extract.zone), civil_to_utc(ends, extract.zone)
        windows.setdefault(entry["site_id"], []).append((begins, ends))
    return windows


def span_entries(extract):
    """unit -> [(effective, entry number, factor text)] for live set entries, in order."""
    register = extract.register
    by_id = {row["entry_id"]: row for row in register}
    number = {row["entry_id"]: int(row["entry_id"][1:]) for row in register}
    voided = set()
    for row in register:
        if row["action"] == "withdraw":
            target = by_id.get(row["target_entry"])
            if target is not None and target["action"] in ("set", "amend"):
                voided.add(target["entry_id"])
    latest_amend = {}
    for row in register:
        if row["action"] != "amend" or row["entry_id"] in voided:
            continue
        target = by_id.get(row["target_entry"])
        if target is None or target["action"] != "set":
            continue
        held = latest_amend.get(target["entry_id"])
        if held is None or number[row["entry_id"]] > number[held["entry_id"]]:
            latest_amend[target["entry_id"]] = row
    tag_spans = {}
    for row in extract.tags:
        tag_spans.setdefault(row["asset_tag"], []).append(
            (minutes(row["valid_from_utc"]), minutes(row["valid_to_utc"]) if row["valid_to_utc"] else None,
             row["unit_id"]))
    entries = {}
    for row in register:
        if row["action"] != "set" or row["entry_id"] in voided:
            continue
        effective = minutes(row["effective_utc"])
        reference = row["unit_ref"]
        if reference in tag_spans:
            holders = [unit for start, stop, unit in tag_spans[reference]
                       if start <= effective and (stop is None or effective < stop)]
            if not holders:
                continue
            unit = holders[-1]
        else:
            unit = reference
        amend = latest_amend.get(row["entry_id"])
        factor = amend["span_factor"] if amend is not None else row["span_factor"]
        entries.setdefault(unit, []).append((effective, number[row["entry_id"]], factor))
    for listing in entries.values():
        listing.sort()
    return entries


def factor_in_force(listing, moment):
    chosen = None
    for effective, _, factor in listing:
        if effective > moment:
            break
        chosen = factor
    return chosen


# ------------------------------------------------------------------ report


def build(extract):
    manifest, policy, zone = extract.manifest, extract.policy, extract.zone
    standard_offset = zone["standard_offset_minutes"]
    numerator, denominator = ratio(policy["daily_standard"])
    standard = numerator * 10 // denominator
    hour_minimum = int(policy["hour_min_readings"])
    day_minimum = int(policy["day_min_hours"])
    first_day = (date.fromisoformat(manifest["first_day"]) - ORIGIN).days
    day_count = int(manifest["days"])
    percent = int(policy["site_min_valid_day_percent"])
    required_days = -(-day_count * percent // 100)

    units = gather_units(extract)
    heard = heard_packets(extract)
    received = settle_clocks(units, heard)
    windows = maintenance_windows(extract)
    spans = span_entries(extract)
    sites = {row["site_id"]: row for row in extract.sites}
    ordered_sites = sorted(sites, key=site_key)
    placements = {}
    for row in extract.deployments:
        placements.setdefault(row["unit_id"], []).append(
            (minutes(row["installed_utc"]), minutes(row["removed_utc"]) if row["removed_utc"] else None,
             row["site_id"]))

    tallies = dict.fromkeys(("outside_window", "undeployed", "missing_value", "flagged", "uncalibrated",
                             "maintenance"), 0)
    excluded = 0
    hour_cells = {}
    valid_per_site = dict.fromkeys(sites, 0)
    for unit in units.values():
        for index, row in enumerate(unit.rows):
            moment = unit.true_minute(index)
            hour = (moment + standard_offset - 1) // 60
            day = hour // 24
            if not first_day <= day < first_day + day_count:
                tallies["outside_window"] += 1
                excluded += 1
                continue
            site = None
            for installed, removed, where in placements[unit.name]:
                if installed <= moment and (removed is None or moment < removed):
                    site = where
            faults = []
            if site is None:
                faults.append("undeployed")
            if row["pm25_raw"] == "":
                faults.append("missing_value")
            if row["status"] != "":
                faults.append("flagged")
            factor = factor_in_force(spans.get(unit.name, []), moment)
            if factor is None:
                faults.append("uncalibrated")
            if site is not None and any(b <= moment < e for b, e in windows.get(site, [])):
                faults.append("maintenance")
            if faults:
                for fault in faults:
                    tallies[fault] += 1
                excluded += 1
                continue
            valid_per_site[site] += 1
            cell = hour_cells.setdefault((site, hour), [0, 0])
            cell[0] += corrected_tenths(int(row["pm25_raw"]), factor)
            cell[1] += 1

    day_cells = {}
    good_hours = 0
    for (site, hour), (total, count) in sorted(hour_cells.items()):
        if count < hour_minimum:
            continue
        good_hours += 1
        cell = day_cells.setdefault((site, hour // 24), [0, 0])
        cell[0] += total // count
        cell[1] += 1
    daily = {site: {} for site in sites}
    complete = dict.fromkeys(sites, 0)
    for (site, day), (total, count) in sorted(day_cells.items()):
        mean = total // count
        if count >= day_minimum:
            daily[site][day] = mean
            complete[site] += 1
        elif mean > standard:
            daily[site][day] = mean

    site_rows = []
    by_site = {}
    for site in ordered_sites:
        values = sorted(daily[site].values(), reverse=True)
        rank = (len(values) - 1) // 50 + 1 if values else None
        design = values[rank - 1] if values else None
        if design is not None and design > standard:
            status = "nonattainment"
        elif len(values) >= required_days:
            status = "attainment"
        else:
            status = "incomplete"
        record = {
            "site_id": site,
            "district": sites[site]["district"],
            "operator_class": sites[site]["operator_class"],
            "valid_days": len(values),
            "complete_days": complete[site],
            "exceedance_days": sum(1 for v in values if v > standard),
            "design_rank": rank,
            "design_value": design,
            "status": status,
        }
        site_rows.append(record)
        by_site[site] = record

    def highest(members):
        top = None
        for site in members:
            value = by_site[site]["design_value"]
            if value is not None and (top is None or value > top[1]):
                top = (site, value)
        return top

    reports = {}
    rolled_up = 0
    for prefix, field, names in (("region", "district", DISTRICT_FILES), ("segment", "operator_class", OPERATOR_FILES)):
        for name in names:
            members = [site for site in ordered_sites if sites[site][field] == name]
            if all(by_site[site]["status"] == "incomplete" for site in members):
                reports[f"{prefix}_{name}.json"] = {field: name, "in_scope": False}
                continue
            readings = sum(valid_per_site[site] for site in members)
            if prefix == "region":
                rolled_up += readings
            top = highest(members)
            reports[f"{prefix}_{name}.json"] = {
                field: name,
                "in_scope": True,
                "sites": [
                    {
                        "site_id": site,
                        "status": by_site[site]["status"],
                        "valid_readings": valid_per_site[site],
                        "daily_values": {day_text(day): value for day, value in sorted(daily[site].items())},
                    }
                    for site in members
                ],
                "valid_readings": readings,
                "exceedance_days": sum(by_site[site]["exceedance_days"] for site in members),
                "worst_site": {"site_id": top[0], "design_value": top[1]} if top else None,
                "status": "nonattainment" if any(by_site[s]["status"] == "nonattainment" for s in members)
                else "attainment",
            }

    valid_total = sum(valid_per_site.values())
    statuses = {"attainment": 0, "incomplete": 0, "nonattainment": 0}
    for record in site_rows:
        statuses[record["status"]] += 1
    top = highest(ordered_sites)
    reports["summary.json"] = {
        "report_id": manifest["report_id"],
        "first_day": manifest["first_day"],
        "days": day_count,
        "card_rows": len(extract.card),
        "valid_readings": valid_total,
        "valid_hours": good_hours,
        "valid_days": sum(r["valid_days"] for r in site_rows),
        "exceedance_days": sum(r["exceedance_days"] for r in site_rows),
        "site_status_counts": statuses,
        "highest_design_value": {"site_id": top[0], "value": top[1]} if top else {"site_id": None, "value": None},
        "reconciliation": {
            "card_rows": len(extract.card),
            "excluded_readings": excluded,
            "valid_readings": valid_total,
            "rolled_up_valid_readings": rolled_up,
            "residual": valid_total - rolled_up,
        },
    }
    reports["policy_audit.json"] = {
        "policy_revision": policy["revision"],
        "span_register_revision": manifest["span_register_revision"],
        "daily_standard_tenths": standard,
        "hour_min_readings": hour_minimum,
        "day_min_hours": day_minimum,
        "required_valid_days": required_days,
        "sites": site_rows,
    }
    reports["data_quality.json"] = {
        "journal_entries": len(extract.journal),
        "excluded_readings": excluded,
        "exclusions": tallies,
        "units": [
            {
                "unit_id": name,
                "channel": units[name].channel,
                "card_rows": len(units[name].rows),
                "received_packets": received[name],
            }
            for name in sorted(units)
        ],
    }
    return reports


REPORT_ORDER = ("summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json",
                "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    try:
        reports = build(Extract(argv[1]))
    except (ExtractError, OSError, KeyError, ValueError) as exc:
        sys.stderr.write(f"derive_report: {exc}\n")
        return 1
    out = Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for name in REPORT_ORDER:
        text = json.dumps(reports[name], sort_keys=True, indent=2) + "\n"
        data = text.encode("utf-8")
        (out / name).write_bytes(data)
        sys.stdout.write(f"{name} {len(data)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
