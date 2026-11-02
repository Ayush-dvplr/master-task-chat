#!/usr/bin/env python3
"""Derive the nine Harbourline PM2.5 reports from one monthly extract."""

import csv
import datetime
import io
import json
import os
import re
import sys
from fractions import Fraction

MINUTE_FORMAT = "%Y-%m-%dT%H:%M"
EPOCH = datetime.datetime(1970, 1, 1)
MAX_CLOCK_OFFSET = 19
DISTRICTS = ("North", "South", "West", "East")
OPERATOR_CLASSES = ("commercial", "public")
EXCLUSION_REASONS = (
    "outside_window",
    "undeployed",
    "missing_value",
    "flagged",
    "uncalibrated",
    "maintenance",
)
UNIT_ID_RE = re.compile(r"^AQ[0-9]+$")


def parse_minute(text):
    """Minutes since the epoch for a `YYYY-MM-DDTHH:MM` time."""
    return int((datetime.datetime.strptime(text, MINUTE_FORMAT) - EPOCH).total_seconds()) // 60


def parse_day(text):
    """Days since the epoch for a `YYYY-MM-DD` date."""
    return (datetime.datetime.strptime(text, "%Y-%m-%d") - EPOCH).days


def day_text(day_number):
    return (EPOCH + datetime.timedelta(days=day_number)).strftime("%Y-%m-%d")


def read_text(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def read_json(path):
    return json.loads(read_text(path))


def read_csv(path):
    rows = list(csv.reader(io.StringIO(read_text(path), newline='')))
    if not rows:
        return []
    header = [name.strip() for name in rows[0]]
    records = []
    for row in rows[1:]:
        if not row:
            continue
        padded = row + [""] * (len(header) - len(row))
        records.append(dict(zip(header, padded)))
    return records


def entry_number(entry_id):
    return int(entry_id[1:])


def site_number(site_id):
    return int(site_id[1:])


def channel_label(text):
    return text.strip().upper()


def round_half_up(value):
    """Round a Fraction half up to a whole number."""
    return (value + Fraction(1, 2)).__floor__()


class Zone:
    """Local standard time and civil time of the network zone."""

    def __init__(self, rules):
        self.offset = int(rules["standard_offset_minutes"])
        self.periods = []
        for period in rules["daylight_saving"]:
            self.periods.append(
                (
                    parse_minute(period["begins"]),
                    parse_minute(period["ends"]),
                    int(period["shift_minutes"]),
                )
            )

    def local(self, utc_minute):
        return utc_minute + self.offset

    def civil_to_utc(self, civil_minute):
        for begins, ends, shift in self.periods:
            if begins <= civil_minute < ends:
                return civil_minute - shift - self.offset
        return civil_minute - self.offset


class SpanRegister:
    """Each unit's span factor over time, from the register in force."""

    def __init__(self, rows, asset_tags):
        entries = {}
        for row in rows:
            entries[row["entry_id"]] = row
        void = set()
        for row in rows:
            if row["action"] != "withdraw":
                continue
            target = entries.get(row["target_entry"])
            if target is not None and target["action"] in ("set", "amend"):
                void.add(target["entry_id"])
        amendments = {}
        for row in rows:
            if row["action"] != "amend" or row["entry_id"] in void:
                continue
            target = entries.get(row["target_entry"])
            if target is None or target["action"] != "set":
                continue
            number = entry_number(row["entry_id"])
            current = amendments.get(target["entry_id"])
            if current is None or number > current[0]:
                amendments[target["entry_id"]] = (number, row["span_factor"])
        self.by_unit = {}
        for row in rows:
            if row["action"] != "set" or row["entry_id"] in void:
                continue
            effective = parse_minute(row["effective_utc"])
            unit_id = resolve_unit_ref(row["unit_ref"], effective, asset_tags)
            if unit_id is None:
                continue
            amendment = amendments.get(row["entry_id"])
            factor_text = amendment[1] if amendment else row["span_factor"]
            self.by_unit.setdefault(unit_id, []).append(
                (effective, entry_number(row["entry_id"]), Fraction(factor_text))
            )
        for series in self.by_unit.values():
            series.sort(key=lambda item: (item[0], item[1]))

    def factor_at(self, unit_id, utc_minute):
        factor = None
        for effective, _number, value in self.by_unit.get(unit_id, ()):
            if effective <= utc_minute:
                factor = value
            else:
                break
        return factor


def resolve_unit_ref(unit_ref, utc_minute, asset_tags):
    if UNIT_ID_RE.match(unit_ref):
        return unit_ref
    for begins, ends, unit_id in asset_tags.get(unit_ref, ()):
        if begins <= utc_minute and (ends is None or utc_minute < ends):
            return unit_id
    return None


def load_asset_tags(rows):
    tags = {}
    for row in rows:
        begins = parse_minute(row["valid_from_utc"])
        ends = parse_minute(row["valid_to_utc"]) if row["valid_to_utc"] else None
        tags.setdefault(row["asset_tag"], []).append((begins, ends, row["unit_id"]))
    for spans in tags.values():
        spans.sort()
    return tags


def load_deployments(rows):
    """Deployments and channel per unit."""
    deployments = {}
    channels = {}
    for row in rows:
        unit_id = row["unit_id"]
        installed = parse_minute(row["installed_utc"])
        removed = parse_minute(row["removed_utc"]) if row["removed_utc"] else None
        deployments.setdefault(unit_id, []).append((installed, removed, row["site_id"]))
        channels[unit_id] = channel_label(row["channel"])
    for spans in deployments.values():
        spans.sort()
    return deployments, channels


def site_at(deployments, unit_id, utc_minute):
    for installed, removed, site_id in deployments.get(unit_id, ()):
        if installed <= utc_minute and (removed is None or utc_minute < removed):
            return site_id
    return None


def load_maintenance(log, zone):
    basis = log["time_basis"]
    windows = {}
    for entry in log["entries"]:
        begins = parse_minute(entry["begins"])
        ends = parse_minute(entry["ends"])
        if basis == "civil":
            begins = zone.civil_to_utc(begins)
            ends = zone.civil_to_utc(ends)
        windows.setdefault(entry["site_id"], []).append((begins, ends))
    for spans in windows.values():
        spans.sort()
    return windows


def in_maintenance(windows, site_id, utc_minute):
    for begins, ends in windows.get(site_id, ()):
        if begins <= utc_minute < ends:
            return True
    return False


def pick_revision(data_dir, prefix, revision, loader, revision_of):
    names = sorted(
        name
        for name in os.listdir(data_dir)
        if name.startswith(prefix) and os.path.isfile(os.path.join(data_dir, name))
    )
    for name in names:
        content = loader(os.path.join(data_dir, name))
        if revision_of(content) == revision:
            return content
    raise SystemExit("no %s file with revision %s" % (prefix, revision))


def clock_offsets(card_rows, channels, journal):
    """The clock offset of each unit with a card, and its received packets.

    A unit's offset holds for its whole card, so the offset taken is the one
    under which the most of the unit's rows appear in the receipt journal.
    """
    stamps = {}
    for row in card_rows:
        stamps.setdefault(row["unit_id"], []).append((row["card_stamp_minute"], row["frame"]))
    offsets = {}
    received = {}
    for unit_id in sorted(stamps):
        channel = channels[unit_id]
        best = None
        for offset in range(-MAX_CLOCK_OFFSET, MAX_CLOCK_OFFSET + 1):
            matches = 0
            for stamp, frame in stamps[unit_id]:
                if (channel, stamp - offset, frame) in journal:
                    matches += 1
            key = (-matches, abs(offset), offset)
            if best is None or key < best[0]:
                best = (key, offset, matches)
        offsets[unit_id] = best[1]
        received[unit_id] = best[2]
    return offsets, received


def hour_of(zone, utc_minute):
    """Start of the local standard hour a reading at this instant counts toward."""
    local = zone.local(utc_minute)
    return (local - 1) // 60 * 60


def build(data_dir):
    manifest = read_json(os.path.join(data_dir, "extract_manifest.json"))
    zone = Zone(read_json(os.path.join(data_dir, "zone_rules.json")))
    policy = pick_revision(
        data_dir,
        "network_policy",
        manifest["policy_revision"],
        read_json,
        lambda content: content["revision"],
    )
    register_rows = pick_revision(
        data_dir,
        "span_register",
        manifest["span_register_revision"],
        read_csv,
        lambda rows: rows[0]["revision"] if rows else None,
    )
    sites = read_csv(os.path.join(data_dir, "site_register.csv"))
    asset_tags = load_asset_tags(read_csv(os.path.join(data_dir, "asset_tags.csv")))
    deployments, channels = load_deployments(
        read_csv(os.path.join(data_dir, "unit_deployments.csv"))
    )
    maintenance = load_maintenance(
        read_json(os.path.join(data_dir, "maintenance_log.json")), zone
    )
    spans = SpanRegister(register_rows, asset_tags)

    daily_standard = round_half_up(Fraction(policy["daily_standard"]) * 10)
    hour_min_readings = int(policy["hour_min_readings"])
    day_min_hours = int(policy["day_min_hours"])
    days = int(manifest["days"])
    first_day = parse_day(manifest["first_day"])
    window = set(range(first_day, first_day + days))
    required_valid_days = -(-(days * int(policy["site_min_valid_day_percent"])) // 100)

    card_rows = read_csv(os.path.join(data_dir, "card_readings.csv"))
    for row in card_rows:
        row["card_stamp_minute"] = parse_minute(row["card_stamp"])
    journal_rows = read_csv(os.path.join(data_dir, "receipt_journal.csv"))
    journal = set()
    for row in journal_rows:
        journal.add(
            (channel_label(row["channel"]), parse_minute(row["received_utc"]), row["frame"])
        )

    offsets, received = clock_offsets(card_rows, channels, journal)

    exclusions = dict.fromkeys(EXCLUSION_REASONS, 0)
    excluded_readings = 0
    valid_readings = 0
    hour_groups = {}
    site_valid_readings = dict((row["site_id"], 0) for row in sites)
    unit_card_rows = {}

    for row in card_rows:
        unit_id = row["unit_id"]
        unit_card_rows[unit_id] = unit_card_rows.get(unit_id, 0) + 1
        instant = row["card_stamp_minute"] - offsets[unit_id]
        hour = hour_of(zone, instant)
        if hour // 1440 not in window:
            excluded_readings += 1
            exclusions["outside_window"] += 1
            continue
        site_id = site_at(deployments, unit_id, instant)
        factor = spans.factor_at(unit_id, instant)
        reasons = []
        if site_id is None:
            reasons.append("undeployed")
        if row["pm25_raw"] == "":
            reasons.append("missing_value")
        if row["status"] != "":
            reasons.append("flagged")
        if factor is None:
            reasons.append("uncalibrated")
        if site_id is not None and in_maintenance(maintenance, site_id, instant):
            reasons.append("maintenance")
        if reasons:
            excluded_readings += 1
            for reason in reasons:
                exclusions[reason] += 1
            continue
        valid_readings += 1
        site_valid_readings[site_id] = site_valid_readings.get(site_id, 0) + 1
        corrected = round_half_up(int(row["pm25_raw"]) * factor)
        group = hour_groups.setdefault((site_id, hour), [0, 0])
        group[0] += 1
        group[1] += corrected

    hourly = {}
    for (site_id, hour), (count, total) in hour_groups.items():
        if count >= hour_min_readings:
            hourly.setdefault(site_id, {})[hour] = total // count

    site_reports = {}
    for row in sites:
        site_id = row["site_id"]
        day_groups = {}
        for hour, value in hourly.get(site_id, {}).items():
            group = day_groups.setdefault(hour // 1440, [0, 0])
            group[0] += 1
            group[1] += value
        daily_values = {}
        complete_days = 0
        for day, (count, total) in day_groups.items():
            mean = total // count
            if count >= day_min_hours:
                complete_days += 1
                daily_values[day] = mean
            elif count >= 1 and mean > daily_standard:
                daily_values[day] = mean
        ranked = sorted(daily_values.values(), reverse=True)
        if ranked:
            design_rank = -(-len(ranked) // 50)
            design_value = ranked[design_rank - 1]
        else:
            design_rank = None
            design_value = None
        valid_days = len(daily_values)
        if design_value is not None and design_value > daily_standard:
            status = "nonattainment"
        elif valid_days >= required_valid_days:
            status = "attainment"
        else:
            status = "incomplete"
        site_reports[site_id] = {
            "site_id": site_id,
            "district": row["district"],
            "operator_class": row["operator_class"],
            "valid_days": valid_days,
            "complete_days": complete_days,
            "exceedance_days": sum(
                1 for value in daily_values.values() if value > daily_standard
            ),
            "design_rank": design_rank,
            "design_value": design_value,
            "status": status,
            "daily_values": daily_values,
            "valid_readings": site_valid_readings[site_id],
            "valid_hours": len(hourly.get(site_id, {})),
        }

    ordered_sites = sorted(site_reports.values(), key=lambda item: site_number(item["site_id"]))

    def worst_site(group):
        best = None
        for site in group:
            if site["design_value"] is None:
                continue
            key = (-site["design_value"], site_number(site["site_id"]))
            if best is None or key < best[0]:
                best = (key, site)
        return best[1] if best else None

    def rollup(key_name, key_value, group):
        report = {key_name: key_value}
        if not any(site["status"] != "incomplete" for site in group):
            report["in_scope"] = False
            return report, False
        report["in_scope"] = True
        report["sites"] = [
            {
                "site_id": site["site_id"],
                "status": site["status"],
                "valid_readings": site["valid_readings"],
                "daily_values": dict(
                    (day_text(day), value) for day, value in site["daily_values"].items()
                ),
            }
            for site in group
        ]
        report["valid_readings"] = sum(site["valid_readings"] for site in group)
        report["exceedance_days"] = sum(site["exceedance_days"] for site in group)
        worst = worst_site(group)
        report["worst_site"] = (
            None
            if worst is None
            else {"site_id": worst["site_id"], "design_value": worst["design_value"]}
        )
        report["status"] = (
            "nonattainment"
            if any(site["status"] == "nonattainment" for site in group)
            else "attainment"
        )
        return report, True

    rolled_up_valid_readings = 0
    region_reports = []
    for district in DISTRICTS:
        group = [site for site in ordered_sites if site["district"] == district]
        report, in_scope = rollup("district", district, group)
        region_reports.append(("region_%s.json" % district, report))
        if in_scope:
            rolled_up_valid_readings += report["valid_readings"]
    segment_reports = []
    for operator_class in OPERATOR_CLASSES:
        group = [site for site in ordered_sites if site["operator_class"] == operator_class]
        report, _in_scope = rollup("operator_class", operator_class, group)
        segment_reports.append(("segment_%s.json" % operator_class, report))

    status_counts = dict.fromkeys(("attainment", "incomplete", "nonattainment"), 0)
    for site in ordered_sites:
        status_counts[site["status"]] += 1
    network_worst = worst_site(ordered_sites)
    summary = {
        "report_id": manifest["report_id"],
        "first_day": manifest["first_day"],
        "days": days,
        "card_rows": len(card_rows),
        "valid_readings": valid_readings,
        "valid_hours": sum(site["valid_hours"] for site in ordered_sites),
        "valid_days": sum(site["valid_days"] for site in ordered_sites),
        "exceedance_days": sum(site["exceedance_days"] for site in ordered_sites),
        "site_status_counts": status_counts,
        "highest_design_value": {
            "site_id": None if network_worst is None else network_worst["site_id"],
            "value": None if network_worst is None else network_worst["design_value"],
        },
        "reconciliation": {
            "card_rows": len(card_rows),
            "excluded_readings": excluded_readings,
            "valid_readings": valid_readings,
            "rolled_up_valid_readings": rolled_up_valid_readings,
            "residual": valid_readings - rolled_up_valid_readings,
        },
    }
    policy_audit = {
        "policy_revision": policy["revision"],
        "span_register_revision": manifest["span_register_revision"],
        "daily_standard_tenths": daily_standard,
        "hour_min_readings": hour_min_readings,
        "day_min_hours": day_min_hours,
        "required_valid_days": required_valid_days,
        "sites": [
            {
                "site_id": site["site_id"],
                "district": site["district"],
                "operator_class": site["operator_class"],
                "valid_days": site["valid_days"],
                "complete_days": site["complete_days"],
                "exceedance_days": site["exceedance_days"],
                "design_rank": site["design_rank"],
                "design_value": site["design_value"],
                "status": site["status"],
            }
            for site in ordered_sites
        ],
    }
    data_quality = {
        "journal_entries": len(journal_rows),
        "excluded_readings": excluded_readings,
        "exclusions": exclusions,
        "units": [
            {
                "unit_id": unit_id,
                "channel": channels[unit_id],
                "card_rows": unit_card_rows[unit_id],
                "received_packets": received[unit_id],
            }
            for unit_id in sorted(unit_card_rows)
        ],
    }
    reports = [
        ("summary.json", summary),
        ("policy_audit.json", policy_audit),
        ("data_quality.json", data_quality),
    ]
    reports.extend(region_reports)
    reports.extend(segment_reports)
    return reports


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: derive_report.py DATA_DIR OUT_DIR")
    data_dir, out_dir = argv[1], argv[2]
    reports = build(data_dir)
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for name, report in reports:
        payload = (
            json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(payload)
        out.append("%s %d\n" % (name, len(payload)))
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main(sys.argv)
