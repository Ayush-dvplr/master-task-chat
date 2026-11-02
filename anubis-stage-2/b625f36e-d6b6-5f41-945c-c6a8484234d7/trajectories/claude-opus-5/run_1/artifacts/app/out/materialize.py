#!/usr/bin/env python3
"""Materialize the Marrowgate interval settlement ledger from a delivered corpus.

Reads only the corpus directory named by --data and writes every deliverable of
the ledger output contract into the directory named by --out.
"""

import argparse
import csv
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN

CLASS_RANK = {
    "ORIGINAL": 0,
    "AMENDMENT": 1,
    "CORRECTION": 2,
    "REVERSAL": 3,
    "RESTATEMENT": 4,
}

FAMILY_PREFIX = (
    ("readings_desk_", "desk"),
    ("readings_import_", "import"),
    ("readings_relay_", "relay"),
    ("readings_partner_", "partner"),
    ("readings_legacy_", "legacy"),
    ("adjustments_", "adjustment"),
)

FAMILY_UNIT = {
    "desk": "kwh",
    "import": "kwh",
    "relay": "kwh",
    "partner": "kwh",
    "legacy": "kwh",
    "adjustment": "wh",
}

DELIMITER = {"desk": ",", "relay": "\t", "partner": "|"}

FIXED_WIDTH = (
    ("event_key", 12),
    ("revision_no", 4),
    ("revision_class", 12),
    ("site_ref", 16),
    ("meter_id", 10),
    ("occurred_at", 22),
    ("ingested_at", 22),
    ("quantity", 14),
    ("delta_flag", 2),
    ("supersedes_revision", 4),
)

NUMERAL = {
    "kwh": re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?"),
    "wh": re.compile(r"[+-]?[0-9]+"),
}

ASCII_DIGITS = re.compile(r"[0-9]+")
Z_FORM = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z")
OFFSET_FORM = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})([+-])(\d{2}):(\d{2})"
)

WH_ROUNDING = ROUND_HALF_EVEN
THOUSAND = Decimal(1000)

CONFIG_LAYERS = (
    "settlement_defaults.ini",
    "network_policy.conf",
    "site_overrides.properties",
)


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #


def normalize_site_ref(raw):
    text = unicodedata.normalize("NFC", raw).replace("\t", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return text.strip().upper()


def parse_instant(text):
    """Return the UTC instant a written field names, or None."""
    match = Z_FORM.fullmatch(text)
    if match:
        year, month, day, hour, minute, second = (int(g) for g in match.groups())
        offset = timedelta(0)
    else:
        match = OFFSET_FORM.fullmatch(text)
        if not match:
            return None
        groups = match.groups()
        year, month, day, hour, minute, second = (int(g) for g in groups[:6])
        sign = -1 if groups[6] == "-" else 1
        off_h, off_m = int(groups[7]), int(groups[8])
        if off_h > 23 or off_m > 59:
            return None
        offset = sign * timedelta(hours=off_h, minutes=off_m)
    try:
        written = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None
    return written - offset


def to_watt_hours(value, multiplier, unit):
    product = value * multiplier
    if unit == "kwh":
        product = product * THOUSAND
    return int(product.quantize(Decimal(1), rounding=WH_ROUNDING))


def present_kwh(watt_hours, places):
    quantum = Decimal(1).scaleb(-places)
    scaled = (Decimal(watt_hours) / THOUSAND).quantize(
        quantum, rounding=ROUND_HALF_EVEN
    )
    return f"{scaled:.{places}f}"


def family_of(filename):
    for prefix, family in FAMILY_PREFIX:
        if filename.startswith(prefix):
            return family
    return None


# --------------------------------------------------------------------------- #
# corpus inputs
# --------------------------------------------------------------------------- #


def read_text(path):
    text = open(path, "rb").read().decode("utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def read_table(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_batch(path, family):
    lines = read_text(path)
    rows = []
    if family in ("import", "adjustment"):
        for line in lines:
            rows.append(json.loads(line))
    elif family == "legacy":
        for line in lines:
            row, cursor = {}, 0
            for name, width in FIXED_WIDTH:
                row[name] = line[cursor : cursor + width].rstrip(" ")
                cursor += width
            rows.append(row)
    else:
        delimiter = DELIMITER[family]
        header = lines[0].split(delimiter)
        for line in lines[1:]:
            rows.append(dict(zip(header, line.split(delimiter))))
    return rows


def load_calendar(data_dir):
    pattern = re.compile(
        r"^\s*(\d{8})\s+opens\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s*$"
    )
    days = []
    for line in read_text(os.path.join(data_dir, "settlement-calendar.md")):
        match = pattern.match(line)
        if match:
            days.append((match.group(1), parse_instant(match.group(2))))
    days.sort(key=lambda item: item[1])
    return [(key, opens, opens + timedelta(hours=24)) for key, opens in days]


def load_config(data_dir):
    layers = []
    for name in CONFIG_LAYERS:
        values = {}
        for line in read_text(os.path.join(data_dir, name)):
            stripped = line.strip()
            if not stripped or stripped[0] in "#;[":
                continue
            key, _, value = stripped.partition("=")
            values[key.strip()] = value.strip()
        layers.append((name, values))
    resolved, winner = {}, {}
    for name, values in layers:
        for key, value in values.items():
            if key.startswith("rounding."):
                if key in resolved and int(resolved[key]) <= int(value):
                    continue
            resolved[key] = value
            winner[key] = name
    return resolved, winner


def effective_index(rows, key_field):
    index = {}
    for row in rows:
        index.setdefault(row[key_field], []).append(
            (parse_instant(row["valid_from"]), parse_instant(row["valid_to"]), row)
        )
    return index


def covering_row(intervals, instant):
    """The row that governs an instant: latest valid_from, then earliest valid_to."""
    covering = [item for item in intervals if item[0] <= instant < item[1]]
    if not covering:
        return None
    latest = max(item[0] for item in covering)
    narrowest = min(
        (item for item in covering if item[0] == latest), key=lambda item: item[1]
    )
    return narrowest[2]


# --------------------------------------------------------------------------- #
# selection seams
# --------------------------------------------------------------------------- #


def canonical_key(revision):
    return (
        CLASS_RANK[revision["revision_class"]],
        revision["revision_no"],
        -revision["batch_seq"],
    )


def select_canonical(revisions):
    return max(revisions, key=canonical_key)


def select_base(revisions):
    candidates = [r for r in revisions if r["revision_class"] != "RESTATEMENT"]
    return max(candidates, key=canonical_key) if candidates else None


def settlement_day_of(instant, calendar):
    for key, opens, closes in calendar:
        if opens <= instant < closes:
            return key
    return None


def resolve_merge(site, instant, merges):
    seen = {site}
    current = site
    while True:
        hop = merges.get(current)
        if hop is None:
            return current
        survivor, merge_instant = hop
        if instant < merge_instant or survivor in seen:
            return current
        seen.add(survivor)
        current = survivor


def attribute_instant(event):
    return event["effective_instant"]


def apply_clamps(base_wh, stack_delta, ceiling):
    base_clamped = min(max(base_wh, 0), ceiling)
    final = min(max(base_clamped + stack_delta, 0), ceiling)
    return base_clamped, final


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #


def materialize(data_dir):
    calendar = load_calendar(data_dir)
    calendar_open = calendar[0][1]
    calendar_close = calendar[-1][2]
    config, config_winner = load_config(data_dir)

    sites_rows = read_table(os.path.join(data_dir, "sites_effective.csv"))
    sites_index = effective_index(sites_rows, "site_id")
    registered_sites = set(sites_index)
    state_index = effective_index(
        read_table(os.path.join(data_dir, "operational_state.csv")), "site_id"
    )
    limit_index = effective_index(
        read_table(os.path.join(data_dir, "max_interval_limits.csv")), "site_id"
    )

    registrations = [
        row
        for row in read_table(os.path.join(data_dir, "meter_registry.csv"))
        if ASCII_DIGITS.fullmatch(row["pulse_multiplier"])
        and int(row["pulse_multiplier"]) > 0
    ]
    meter_index = effective_index(registrations, "meter_id")

    merges = {}
    merge_sources = set()
    for row in read_table(os.path.join(data_dir, "site_merges.csv")):
        merges[row["absorbed_site"]] = (
            row["survivor_site"],
            parse_instant(row["merge_instant"]),
        )
        merge_sources.add(row["absorbed_site"])

    bands = {}
    for row in read_table(os.path.join(data_dir, "tariff_classes.csv")):
        bands.setdefault(row["tariff_class"], []).append(
            (int(row["threshold_wh"]), row["band"])
        )
    for thresholds in bands.values():
        thresholds.sort()

    manifest = read_table(os.path.join(data_dir, "batch_manifest.csv"))
    manifest.sort(key=lambda row: int(row["batch_seq"]))
    ingested, withdrawn, missing_batches, row_exceptions = [], [], [], []

    rejects, quarantine, duplicates = [], [], []
    admitted_by_identity = {}
    events = {}
    total_rows = 0

    for entry in manifest:
        if entry["status"] != "ACTIVE":
            withdrawn.append(entry["batch_id"])
            continue
        path = os.path.join(data_dir, entry["filename"])
        if not os.path.exists(path):
            missing_batches.append(
                {
                    "batch_id": entry["batch_id"],
                    "filename": entry["filename"],
                    "reason_code": "MISSING_BATCH",
                }
            )
            continue
        family = family_of(entry["filename"])
        unit = FAMILY_UNIT[family]
        batch_seq = int(entry["batch_seq"])
        rows = read_batch(path, family)
        ingested.append(entry["batch_id"])
        if len(rows) != int(entry["expected_rows"]):
            row_exceptions.append(
                {
                    "batch_id": entry["batch_id"],
                    "declared_rows": int(entry["expected_rows"]),
                    "filename": entry["filename"],
                    "observed_rows": len(rows),
                }
            )
        total_rows += len(rows)

        for line_no, row in enumerate(rows, 1):
            reason = None
            instant = None
            site_ref = normalize_site_ref(row["site_ref"])
            quantity = row["quantity"]
            registration = None

            if row["revision_class"] not in CLASS_RANK:
                reason = "MALFORMED_ROW"
            elif not ASCII_DIGITS.fullmatch(row["revision_no"]) or int(
                row["revision_no"]
            ) <= 0:
                reason = "MALFORMED_ROW"
            else:
                instant = parse_instant(row["occurred_at"])
                if instant is None:
                    reason = "BAD_TIMESTAMP"
                elif not calendar_open <= instant < calendar_close:
                    reason = "OUT_OF_CALENDAR"
                elif quantity != "" and not NUMERAL[unit].fullmatch(quantity):
                    reason = "BAD_QUANTITY"
                elif site_ref not in registered_sites:
                    reason = "UNKNOWN_SITE"
                else:
                    registration = covering_row(
                        meter_index.get(row["meter_id"], []), instant
                    )
                    if registration is None:
                        reason = "UNKNOWN_METER"
                    elif registration["site_id"] != site_ref:
                        reason = "METER_SITE_MISMATCH"

            if reason is not None:
                rejects.append(
                    {
                        "batch_id": entry["batch_id"],
                        "filename": entry["filename"],
                        "line_no": line_no,
                        "event_key": row["event_key"],
                        "reason_code": reason,
                    }
                )
                continue

            revision_no = int(row["revision_no"])
            supersedes = (
                int(row["supersedes_revision"])
                if ASCII_DIGITS.fullmatch(row["supersedes_revision"])
                else None
            )
            value = Decimal(quantity) if quantity != "" else None
            identity = (
                row["event_key"],
                revision_no,
                row["revision_class"],
                family,
            )
            payload = (
                site_ref,
                row["meter_id"],
                instant,
                value,
                supersedes,
            )

            held = admitted_by_identity.get(identity)
            if held is not None:
                record = {
                    "batch_id": entry["batch_id"],
                    "event_key": row["event_key"],
                    "line_no": line_no,
                    "revision_class": row["revision_class"],
                    "revision_no": revision_no,
                }
                if held["payload"] == payload:
                    duplicates.append(record)
                else:
                    quarantine.append(record)
                continue

            multiplier = Decimal(registration["pulse_multiplier"])
            revision = {
                "batch_id": entry["batch_id"],
                "batch_seq": batch_seq,
                "event_key": row["event_key"],
                "family": family,
                "line_no": line_no,
                "revision_class": row["revision_class"],
                "revision_no": revision_no,
                "instant": instant,
                "ingested_at": parse_instant(row["ingested_at"]),
                "site_ref": site_ref,
                "supersedes": supersedes,
                "payload": payload,
                "quantity_wh": (
                    None
                    if value is None
                    else to_watt_hours(value, multiplier, unit)
                ),
            }
            admitted_by_identity[identity] = revision
            events.setdefault(row["event_key"], []).append(revision)

    ledger = []
    for event_key in sorted(events):
        ledger.append(
            settle_event(
                event_key,
                events[event_key],
                calendar,
                merges,
                sites_index,
                state_index,
                limit_index,
                bands,
            )
        )

    return {
        "calendar": calendar,
        "config": config,
        "config_winner": config_winner,
        "ledger": ledger,
        "events": events,
        "ingested": ingested,
        "withdrawn": withdrawn,
        "missing_batches": missing_batches,
        "row_exceptions": row_exceptions,
        "rejects": rejects,
        "quarantine": quarantine,
        "duplicates": duplicates,
        "admitted": list(admitted_by_identity.values()),
        "merge_sources": merge_sources,
        "total_rows": total_rows,
        "baseline": json.load(
            open(os.path.join(data_dir, "published_baseline.json"), encoding="utf-8")
        ),
    }


def settle_event(
    event_key,
    revisions,
    calendar,
    merges,
    sites_index,
    state_index,
    limit_index,
    bands,
):
    canonical = select_canonical(revisions)
    base = select_base(revisions)
    effective = canonical["instant"]

    event = {
        "event_key": event_key,
        "canonical": canonical,
        "base": base,
        "effective_instant": effective,
        "source_site": canonical["site_ref"],
        "settlement_day": settlement_day_of(effective, calendar),
    }
    event["canonical_site"] = resolve_merge(canonical["site_ref"], effective, merges)
    lookup_at = attribute_instant(event)
    site_row = covering_row(sites_index.get(event["canonical_site"], []), lookup_at)
    event["zone"] = site_row["zone"]
    event["tariff_class"] = site_row["tariff_class"]
    state_row = covering_row(state_index.get(event["canonical_site"], []), lookup_at)
    limit_row = covering_row(limit_index.get(event["canonical_site"], []), lookup_at)
    ceiling = None if limit_row is None else int(limit_row["max_interval_wh"])

    stack = [r for r in revisions if r["revision_class"] == "RESTATEMENT"]
    displaced = {
        r["supersedes"]
        for r in stack
        if r["supersedes"] is not None
        and any(s["revision_no"] == r["supersedes"] for s in stack)
    }
    event["stack"] = stack
    event["displaced"] = displaced

    carried = {r["revision_no"] for r in revisions}
    if (
        canonical["revision_class"] in ("CORRECTION", "RESTATEMENT")
        and canonical["supersedes"] is not None
        and canonical["supersedes"] not in carried
    ):
        outcome, reason = "UNRESOLVABLE", "ORPHAN_SUPERSEDE"
    elif base is None:
        outcome, reason = "UNRESOLVABLE", "MISSING_BASE"
    elif ceiling is None:
        outcome, reason = "UNRESOLVABLE", "MISSING_CEILING"
    elif base["quantity_wh"] is None:
        outcome, reason = "DEFERRED", None
    elif (
        canonical["revision_class"] == "REVERSAL"
        and sum(1 for r in revisions if r["revision_class"] == "REVERSAL") % 2 == 1
    ):
        outcome, reason = "VOIDED", None
    elif state_row["state"] == "SUSPENDED":
        outcome, reason = "EXCLUDED", None
    else:
        outcome, reason = "SETTLED", None

    event["outcome"] = outcome
    event["reason_code"] = reason
    event["max_interval_wh"] = ceiling
    event["applied"] = []

    if outcome in ("SETTLED", "EXCLUDED"):
        applied = sorted(
            (
                r
                for r in stack
                if r["revision_no"] not in displaced and r["quantity_wh"] is not None
            ),
            key=lambda r: (r["revision_no"], r["batch_seq"]),
        )
        stack_delta = sum(r["quantity_wh"] for r in applied)
        base_clamped, final = apply_clamps(base["quantity_wh"], stack_delta, ceiling)
        event["applied"] = applied
        event["base_wh"] = base["quantity_wh"]
        event["base_clamped_wh"] = base_clamped
        event["stack_delta_wh"] = stack_delta
        event["quantity_wh"] = final
        event["reached_chain"] = True
    else:
        event["quantity_wh"] = 0
        event["reached_chain"] = False

    event["tariff_band"] = band_of(
        bands.get(event["tariff_class"], []), event["quantity_wh"]
    )
    return event


def band_of(thresholds, quantity_wh):
    band = "UNBANDED"
    if quantity_wh == 0:
        return band
    for threshold, name in thresholds:
        if threshold <= quantity_wh:
            band = name
    return band


# --------------------------------------------------------------------------- #
# deliverables
# --------------------------------------------------------------------------- #


def write_lines(path, lines):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        for line in lines:
            handle.write(line + "\n")


def write_csv(path, columns, records):
    rows = [",".join(columns)]
    for record in records:
        rows.append(",".join(str(record[column]) for column in columns))
    write_lines(path, rows)


def write_jsonl(path, records):
    write_lines(
        path,
        [
            json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            for record in records
        ],
    )


def write_json(path, document):
    write_lines(
        path, json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False).split("\n")
    )


def role_of(revision, event):
    if revision is event["canonical"]:
        return "CANONICAL"
    if revision is event["base"]:
        return "BASE"
    if revision["revision_class"] == "RESTATEMENT":
        if revision["revision_no"] in event["displaced"]:
            return "DISPLACED"
        return "RESTATEMENT_STACK"
    return "SUPERSEDED"


def stack_state_of(revision, event):
    if revision["revision_no"] in event["displaced"]:
        return "DISPLACED"
    if not event["reached_chain"]:
        return "WITHHELD"
    if revision["quantity_wh"] is None:
        return "ABSENT"
    return "APPLIED"


def emit(result, out_dir):
    config = result["config"]
    quantity_dp = int(config["rounding.quantity_dp"])
    total_dp = int(config["rounding.total_dp"])
    policy = config["settlement.exclusion_policy"]
    calendar = result["calendar"]

    ledger = sorted(
        result["ledger"],
        key=lambda e: (e["settlement_day"], e["canonical_site"], e["event_key"]),
    )

    write_jsonl(
        os.path.join(out_dir, "canonical_ledger.jsonl"),
        [
            {
                "canonical_site": e["canonical_site"],
                "event_key": e["event_key"],
                "outcome": e["outcome"],
                "quantity_kwh": present_kwh(e["quantity_wh"], quantity_dp),
                "quantity_wh": e["quantity_wh"],
                "revision_class": e["canonical"]["revision_class"],
                "revision_no": e["canonical"]["revision_no"],
                "settlement_day": e["settlement_day"],
                "source_site": e["source_site"],
                "tariff_band": e["tariff_band"],
                "tariff_class": e["tariff_class"],
                "zone": e["zone"],
            }
            for e in ledger
        ],
    )

    by_event = {e["event_key"]: e for e in ledger}
    index = []
    for revision in result["admitted"]:
        event = by_event[revision["event_key"]]
        index.append(
            {
                "batch_id": revision["batch_id"],
                "event_key": revision["event_key"],
                "family": revision["family"],
                "is_canonical": revision is event["canonical"],
                "quantity_wh": revision["quantity_wh"],
                "revision_class": revision["revision_class"],
                "revision_no": revision["revision_no"],
                "role": role_of(revision, event),
            }
        )
    index.sort(
        key=lambda r: (
            r["event_key"],
            r["revision_no"],
            r["revision_class"],
            r["family"],
        )
    )
    write_jsonl(os.path.join(out_dir, "revision_index.jsonl"), index)

    partitions = []
    for day, _, _ in calendar:
        records = []
        for event in ledger:
            if event["settlement_day"] != day:
                continue
            if event["outcome"] == "EXCLUDED" and policy == "omit":
                continue
            records.append(
                {
                    "sequence_no": len(records) + 1,
                    "event_key": event["event_key"],
                    "canonical_site": event["canonical_site"],
                    "zone": event["zone"],
                    "tariff_band": event["tariff_band"],
                    "outcome": event["outcome"],
                    "quantity_wh": event["quantity_wh"],
                }
            )
        write_csv(
            os.path.join(out_dir, f"partition_{day}.csv"),
            [
                "sequence_no",
                "event_key",
                "canonical_site",
                "zone",
                "tariff_band",
                "outcome",
                "quantity_wh",
            ],
            records,
        )
        settled = [r for r in records if r["outcome"] == "SETTLED"]
        settled_wh = sum(r["quantity_wh"] for r in settled)
        partitions.append(
            {
                "settlement_day": day,
                "row_count": len(records),
                "settled_event_count": len(settled),
                "settled_wh": settled_wh,
                "settled_kwh": present_kwh(settled_wh, total_dp),
            }
        )
    write_json(
        os.path.join(out_dir, "partition_manifest.json"), {"partitions": partitions}
    )

    rejects = sorted(result["rejects"], key=lambda r: (r["batch_id"], r["line_no"]))
    write_csv(
        os.path.join(out_dir, "rejects.csv"),
        ["batch_id", "filename", "line_no", "event_key", "reason_code"],
        rejects,
    )

    write_jsonl(
        os.path.join(out_dir, "quarantine.jsonl"),
        sorted(result["quarantine"], key=lambda r: (r["batch_id"], r["line_no"])),
    )

    write_csv(
        os.path.join(out_dir, "dedup_ledger.csv"),
        ["batch_id", "line_no", "event_key", "revision_no", "revision_class"],
        sorted(result["duplicates"], key=lambda r: (r["batch_id"], r["line_no"])),
    )

    write_jsonl(
        os.path.join(out_dir, "deferred.jsonl"),
        [
            {
                "canonical_site": e["canonical_site"],
                "event_key": e["event_key"],
                "revision_no": e["canonical"]["revision_no"],
                "settlement_day": e["settlement_day"],
            }
            for e in sorted(ledger, key=lambda e: e["event_key"])
            if e["outcome"] == "DEFERRED"
        ],
    )

    unresolvable_events = [
        {
            "canonical_site": e["canonical_site"],
            "event_key": e["event_key"],
            "reason_code": e["reason_code"],
            "settlement_day": e["settlement_day"],
        }
        for e in sorted(ledger, key=lambda e: e["event_key"])
        if e["outcome"] == "UNRESOLVABLE"
    ]
    write_json(
        os.path.join(out_dir, "unresolvable.json"),
        {
            "events": unresolvable_events,
            "missing_batches": sorted(
                result["missing_batches"], key=lambda r: r["batch_id"]
            ),
        },
    )

    write_json(
        os.path.join(out_dir, "entity_resolution.json"),
        {
            "resolutions": [
                {
                    "canonical_site": e["canonical_site"],
                    "event_key": e["event_key"],
                    "merge_applied": e["canonical_site"] != e["source_site"],
                    "source_site": e["source_site"],
                }
                for e in sorted(ledger, key=lambda e: e["event_key"])
                if e["source_site"] in result["merge_sources"]
            ]
        },
    )

    clamped = []
    for event in sorted(ledger, key=lambda e: e["event_key"]):
        if not event["reached_chain"]:
            continue
        first = event["base_wh"] != event["base_clamped_wh"]
        second = (
            event["base_clamped_wh"] + event["stack_delta_wh"] != event["quantity_wh"]
        )
        if not (first or second):
            continue
        clamped.append(
            {
                "event_key": event["event_key"],
                "canonical_site": event["canonical_site"],
                "max_interval_wh": event["max_interval_wh"],
                "base_wh": event["base_wh"],
                "base_clamped_wh": event["base_clamped_wh"],
                "stack_delta_wh": event["stack_delta_wh"],
                "final_wh": event["quantity_wh"],
                "clamp_stage": "BOTH" if first and second else ("BASE" if first else "SUM"),
            }
        )
    write_csv(
        os.path.join(out_dir, "clamp_register.csv"),
        [
            "event_key",
            "canonical_site",
            "max_interval_wh",
            "base_wh",
            "base_clamped_wh",
            "stack_delta_wh",
            "final_wh",
            "clamp_stage",
        ],
        clamped,
    )

    stack_rows = []
    for event in ledger:
        for revision in event["stack"]:
            stack_rows.append(
                {
                    "event_key": event["event_key"],
                    "revision_no": revision["revision_no"],
                    "family": revision["family"],
                    "delta_wh": revision["quantity_wh"] or 0,
                    "stack_state": stack_state_of(revision, event),
                }
            )
    stack_rows.sort(key=lambda r: (r["event_key"], r["revision_no"], r["family"]))
    write_csv(
        os.path.join(out_dir, "stack_register.csv"),
        ["event_key", "revision_no", "family", "delta_wh", "stack_state"],
        stack_rows,
    )

    baseline = {}
    for cell in result["baseline"]["cells"]:
        baseline[(cell["settlement_day"], cell["zone"])] = (
            cell["settled_wh"],
            cell["event_count"],
        )
    computed = {}
    for event in ledger:
        if event["outcome"] != "SETTLED":
            continue
        key = (event["settlement_day"], event["zone"])
        total, count = computed.get(key, (0, 0))
        computed[key] = (total + event["quantity_wh"], count + 1)

    adjustments = []
    totals = {"baseline_settled_wh": 0, "restated_settled_wh": 0, "adjustment_delta_wh": 0}
    for key in sorted(set(baseline) | set(computed)):
        base_wh, base_count = baseline.get(key, (0, 0))
        new_wh, new_count = computed.get(key, (0, 0))
        delta_wh = new_wh - base_wh
        delta_events = new_count - base_count
        totals["baseline_settled_wh"] += base_wh
        totals["restated_settled_wh"] += new_wh
        totals["adjustment_delta_wh"] += delta_wh
        if delta_wh == 0 and delta_events == 0:
            continue
        adjustments.append(
            {
                "settlement_day": key[0],
                "zone": key[1],
                "adjustment_kind": (
                    "INCREASE" if delta_wh > 0 else "DECREASE" if delta_wh < 0 else "COUNT_ONLY"
                ),
                "baseline_settled_wh": base_wh,
                "restated_settled_wh": new_wh,
                "delta_wh": delta_wh,
                "baseline_event_count": base_count,
                "restated_event_count": new_count,
                "delta_events": delta_events,
            }
        )
    write_csv(
        os.path.join(out_dir, "restatement_adjustments.csv"),
        [
            "settlement_day",
            "zone",
            "adjustment_kind",
            "baseline_settled_wh",
            "restated_settled_wh",
            "delta_wh",
            "baseline_event_count",
            "restated_event_count",
            "delta_events",
        ],
        adjustments,
    )

    admitted_count = len(result["admitted"])
    duplicate_count = len(result["duplicates"])
    conflict_count = len(result["quarantine"])
    rejected_count = len(rejects)
    class_residual = (
        admitted_count + duplicate_count + conflict_count + rejected_count
        - result["total_rows"]
    )
    ledger_settled_wh = sum(
        e["quantity_wh"] for e in ledger if e["outcome"] == "SETTLED"
    )
    partition_settled_wh = sum(p["settled_wh"] for p in partitions)
    rollup_residual = partition_settled_wh - ledger_settled_wh
    restatement_residual = (
        totals["baseline_settled_wh"]
        + totals["adjustment_delta_wh"]
        - totals["restated_settled_wh"]
    )

    write_json(
        os.path.join(out_dir, "reconciliation.json"),
        {
            "identity_class_partition": {
                "admitted": admitted_count,
                "conflict": conflict_count,
                "duplicate": duplicate_count,
                "rejected": rejected_count,
                "residual": class_residual,
                "total_rows": result["total_rows"],
            },
            "identity_partition_rollup": {
                "ledger_settled_wh": ledger_settled_wh,
                "partition_settled_wh": partition_settled_wh,
                "residual": rollup_residual,
            },
            "identity_restatement": {
                "adjustment_delta_wh": totals["adjustment_delta_wh"],
                "baseline_settled_wh": totals["baseline_settled_wh"],
                "restated_settled_wh": totals["restated_settled_wh"],
                "residual": restatement_residual,
            },
        },
    )

    write_lines(
        os.path.join(out_dir, "validation_report.txt"),
        [
            f"CLASS_PARTITION residual={class_residual}",
            f"PARTITION_ROLLUP residual={rollup_residual}",
            f"RESTATEMENT residual={restatement_residual}",
            f"ROUNDING quantity_dp={quantity_dp} total_dp={total_dp}",
            f"EXCLUSION policy={policy}",
            f"CLAMPED events={len(clamped)}",
            f"UNRESOLVED events={len(unresolvable_events)}",
            f"DISPLACED revisions={sum(1 for r in stack_rows if r['stack_state'] == 'DISPLACED')}",
        ],
    )

    write_json(
        os.path.join(out_dir, "run_manifest.json"),
        {
            "batches_ingested": sorted(result["ingested"]),
            "batches_withdrawn": sorted(result["withdrawn"]),
            "config_resolved": dict(config),
            "config_winner": dict(result["config_winner"]),
            "row_exceptions": sorted(
                result["row_exceptions"], key=lambda r: r["batch_id"]
            ),
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = materialize(args.data)
    os.makedirs(args.out, exist_ok=True)
    emit(result, args.out)


if __name__ == "__main__":
    main()
