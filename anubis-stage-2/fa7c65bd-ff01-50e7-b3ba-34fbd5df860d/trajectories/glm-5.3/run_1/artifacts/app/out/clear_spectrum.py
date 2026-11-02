#!/usr/bin/env python3
"""SLSC-1.0 spectrum-clearing engine (standard library only).

Usage:
    python3 clear_spectrum.py DATA_DIR OUT_DIR

Reads a revisioned spectrum-clearing extract from DATA_DIR and derives the
contract reports into OUT_DIR.  Nothing is derived from the shipped
identifiers: every value is computed from the input rows.
"""

import datetime
import hashlib
import json
import os
import sys
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction

EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
CTX_PREC = 80
UNIT = Decimal(1)
GROSS_DEN = Decimal(3600 * 1000)
BPS_DEN = Decimal(10000)
HASH_SEED = "0" * 64
DEFAULT_AUCTION_ID = "default"
OWNER_SOURCE_PREFIX = "OWNER:"
GRANT_SOURCE_PREFIX = "GRANT:"
STATUS_ACTIVE = "active"
STATUS_CANCELLED = "cancelled"

POLICY_FILE = "policy.json"
PARTIES_FILE = "parties.json"
LICENSES_FILE = "licenses.jsonl"
GRANT_REVISIONS_FILE = "grant_revisions.jsonl"
ACTIVATIONS_FILE = "activation_events.jsonl"
EXCLUSIONS_FILE = "exclusions.jsonl"
GUARD_BANDS_FILE = "guard_bands.jsonl"
AUCTION_RESULTS_FILE = "auction_results.jsonl"
CORRECTIONS_FILE = "corrections.jsonl"

RECORD_COUNT_KEYS = (
    "licenses",
    "grant_revisions",
    "activations",
    "exclusions",
    "guard_bands",
    "auction_revisions",
    "corrections",
)


# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------

def read_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_jsonl(path):
    """Return the non-empty lines of a JSONL file parsed as JSON objects.

    Unparseable lines are returned as ``None`` so that they still count as
    records but can never be used as data.
    """
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            try:
                rows.append(json.loads(text))
            except ValueError:
                rows.append(None)
    return rows


def as_id(value):
    if isinstance(value, str) and value:
        return value
    return None


def as_int(value):
    """Base-10 integer interpretation; ``None`` when the value is not one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if "_" in text:
            return None
        try:
            return int(text, 10)
        except ValueError:
            return None
    return None


def as_ts(value):
    """UTC ISO-8601 (``...Z``) timestamp to integer epoch seconds."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    delta = moment - EPOCH
    return delta.days * 86400 + delta.seconds


def as_cell_set(value):
    """Cell list as a set; ``None`` when the value is not a cell list."""
    if not isinstance(value, list):
        return None
    cells = set()
    for cell in value:
        if not isinstance(cell, str) or not cell:
            return None
        cells.add(cell)
    return cells


def round_half_up(value):
    with localcontext() as ctx:
        ctx.prec = CTX_PREC
        return int(value.quantize(UNIT, rounding=ROUND_HALF_UP))


def gross_cents(duration_seconds, width_khz, rate_cents_per_mhz_hour):
    with localcontext() as ctx:
        ctx.prec = CTX_PREC
        raw = (
            Decimal(duration_seconds)
            * Decimal(width_khz)
            * Decimal(rate_cents_per_mhz_hour)
            / GROSS_DEN
        )
    return round_half_up(raw)


def share_cents(gross, share_bps):
    with localcontext() as ctx:
        ctx.prec = CTX_PREC
        raw = Decimal(gross) * Decimal(share_bps) / BPS_DEN
    return round_half_up(raw)


def sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, payload):
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# --------------------------------------------------------------------------
# input loading and validation
# --------------------------------------------------------------------------

def positive(low, high):
    return high > low


def contains(outer_low, outer_high, inner_low, inner_high):
    return outer_low <= inner_low and inner_high <= outer_high


def load_extract(data_dir):
    """Parse and validate every input; returns the engine context."""
    issues = []
    counts = dict.fromkeys(RECORD_COUNT_KEYS, 0)

    def issue(code, record_id):
        issues.append((code, "" if record_id is None else str(record_id)))

    policy = read_json(os.path.join(data_dir, POLICY_FILE)) or {}
    primary_priority = as_int(policy.get("primary_priority"))
    if primary_priority is None:
        primary_priority = 0
    dormant_owner_priority = as_int(policy.get("dormant_owner_priority"))
    if dormant_owner_priority is None:
        dormant_owner_priority = 0
    material_cents = as_int(policy.get("material_cents"))
    if material_cents is None:
        material_cents = 0
    default_rate = as_int(policy.get("default_rate_cents_per_mhz_hour"))
    if default_rate is None:
        default_rate = 0
    engine_version = policy.get("engine_version")
    if not isinstance(engine_version, str):
        engine_version = ""

    party_rows = read_json(os.path.join(data_dir, PARTIES_FILE)) or []
    party_ids = set()
    for row in party_rows:
        if isinstance(row, dict):
            party_id = as_id(row.get("party_id"))
            if party_id:
                party_ids.add(party_id)

    # ---- licenses -------------------------------------------------------
    license_rows = read_jsonl(os.path.join(data_dir, LICENSES_FILE))
    counts["licenses"] = len(license_rows)
    licenses = {}
    for row in license_rows:
        if not isinstance(row, dict):
            issue("INVALID_LICENSE", None)
            continue
        license_id = as_id(row.get("license_id")) or ""
        owner = as_id(row.get("owner_party_id"))
        cells = row.get("cells")
        cell_list = cells if isinstance(cells, list) else None
        cell_set = as_cell_set(cells)
        low = as_int(row.get("low_khz"))
        high = as_int(row.get("high_khz"))
        start = as_ts(row.get("start"))
        end = as_ts(row.get("end"))
        valid = (
            license_id
            and owner in party_ids
            and cell_set
            and cell_list is not None
            and len(cell_list) == len(cell_set)
            and low is not None
            and high is not None
            and start is not None
            and end is not None
            and positive(low, high)
            and positive(start, end)
        )
        if not valid or license_id in licenses:
            issue("INVALID_LICENSE", license_id)
            continue
        licenses[license_id] = {
            "license_id": license_id,
            "owner_party_id": owner,
            "cells": sorted(cell_set),
            "cell_set": cell_set,
            "low_khz": low,
            "high_khz": high,
            "start": start,
            "end": end,
        }

    def license_ok(license_id):
        return license_id in licenses

    # ---- grant revisions ------------------------------------------------
    grant_rows = read_jsonl(os.path.join(data_dir, GRANT_REVISIONS_FILE))
    counts["grant_revisions"] = len(grant_rows)
    grant_groups = {}
    for row in grant_rows:
        if not isinstance(row, dict):
            issue("INVALID_GRANT", None)
            continue
        record_id = as_id(row.get("record_id"))
        grant_id = as_id(row.get("grant_id"))
        revision = as_int(row.get("revision"))
        recorded_at = as_ts(row.get("recorded_at"))
        status = row.get("status")
        if status not in (STATUS_ACTIVE, STATUS_CANCELLED):
            status = None
        license_id = as_id(row.get("license_id"))
        party_id = as_id(row.get("party_id"))
        cells = as_cell_set(row.get("cells"))
        low = as_int(row.get("low_khz"))
        high = as_int(row.get("high_khz"))
        start = as_ts(row.get("start"))
        end = as_ts(row.get("end"))
        priority = as_int(row.get("priority"))
        share_bps = as_int(row.get("share_bps"))
        structurally_valid = all(
            value is not None
            for value in (
                record_id,
                grant_id,
                revision,
                recorded_at,
                status,
                license_id,
                party_id,
                cells,
                low,
                high,
                start,
                end,
                priority,
                share_bps,
            )
        )
        if not structurally_valid:
            issue("INVALID_GRANT", record_id or grant_id or "")
            continue
        grant_groups.setdefault(grant_id, []).append(
            {
                "record_id": record_id,
                "grant_id": grant_id,
                "revision": revision,
                "recorded_at": recorded_at,
                "status": status,
                "license_id": license_id,
                "party_id": party_id,
                "cells": cells,
                "low_khz": low,
                "high_khz": high,
                "start": start,
                "end": end,
                "priority": priority,
                "share_bps": share_bps,
                "recorded_at_text": row.get("recorded_at"),
                "start_text": row.get("start"),
                "end_text": row.get("end"),
            }
        )

    grant_decisions = []
    effective_grants = []
    for grant_id in sorted(grant_groups):
        rows = grant_groups[grant_id]
        max_revision = max(row["revision"] for row in rows)
        at_max = [row for row in rows if row["revision"] == max_revision]
        max_recorded = max(row["recorded_at"] for row in at_max)
        tied = [row for row in at_max if row["recorded_at"] == max_recorded]
        signatures = {grant_signature(row) for row in tied}
        if len(signatures) > 1:
            issue("REVISION_TIE_CONFLICT", grant_id)
        winner = max(tied, key=lambda row: row["record_id"])
        discarded = sorted(row["record_id"] for row in rows if row is not winner)
        grant_decisions.append(
            {
                "grant_id": grant_id,
                "winner_record_id": winner["record_id"],
                "discarded_record_ids": discarded,
            }
        )
        if winner["status"] != STATUS_ACTIVE:
            continue
        license_id = winner["license_id"]
        license_row = licenses.get(license_id)
        valid = license_row is not None and winner["party_id"] in party_ids
        if valid:
            valid = 0 <= winner["share_bps"] <= 10000
        if valid:
            valid = bool(winner["cells"]) and winner["cells"] <= license_row["cell_set"]
        if valid:
            valid = (
                positive(winner["low_khz"], winner["high_khz"])
                and positive(winner["start"], winner["end"])
                and contains(
                    license_row["low_khz"],
                    license_row["high_khz"],
                    winner["low_khz"],
                    winner["high_khz"],
                )
                and contains(
                    license_row["start"],
                    license_row["end"],
                    winner["start"],
                    winner["end"],
                )
            )
        if not valid:
            issue("INVALID_GRANT", grant_id)
            continue
        effective_grants.append(
            {
                "grant_id": grant_id,
                "license_id": license_id,
                "party_id": winner["party_id"],
                "cells": winner["cells"],
                "low_khz": winner["low_khz"],
                "high_khz": winner["high_khz"],
                "start": winner["start"],
                "end": winner["end"],
                "priority": winner["priority"],
                "share_bps": winner["share_bps"],
                "start_text": winner["start_text"],
                "end_text": winner["end_text"],
            }
        )
    effective_grants.sort(
        key=lambda row: (
            row["license_id"],
            row["party_id"],
            row["start"],
            row["low_khz"],
            row["grant_id"],
        )
    )

    # ---- guard bands ----------------------------------------------------
    guard_rows = read_jsonl(os.path.join(data_dir, GUARD_BANDS_FILE))
    counts["guard_bands"] = len(guard_rows)
    guard_by_license = {}
    for row in guard_rows:
        if not isinstance(row, dict):
            issue("INVALID_GUARD_BAND", None)
            continue
        guard_id = as_id(row.get("guard_id"))
        license_id = as_id(row.get("license_id"))
        guard_khz = as_int(row.get("guard_khz"))
        if (
            guard_id is None
            or license_id is None
            or guard_khz is None
            or guard_khz < 0
            or not license_ok(license_id)
        ):
            issue("INVALID_GUARD_BAND", guard_id or license_id or "")
            continue
        if license_id in guard_by_license:
            issue("INVALID_GUARD_BAND", guard_id)
            if guard_id < guard_by_license[license_id]["guard_id"]:
                guard_by_license[license_id] = {
                    "guard_id": guard_id,
                    "guard_khz": guard_khz,
                }
        else:
            guard_by_license[license_id] = {
                "guard_id": guard_id,
                "guard_khz": guard_khz,
            }
    guard_width = {
        license_id: entry["guard_khz"] for license_id, entry in guard_by_license.items()
    }

    # ---- activations ----------------------------------------------------
    activation_rows = read_jsonl(os.path.join(data_dir, ACTIVATIONS_FILE))
    counts["activations"] = len(activation_rows)
    activations = []
    for row in activation_rows:
        if not isinstance(row, dict):
            issue("INVALID_ACTIVATION", None)
            continue
        activation_id = as_id(row.get("activation_id"))
        license_id = as_id(row.get("license_id"))
        cells = as_cell_set(row.get("cells"))
        low = as_int(row.get("low_khz"))
        high = as_int(row.get("high_khz"))
        start = as_ts(row.get("start"))
        end = as_ts(row.get("end"))
        license_row = licenses.get(license_id) if license_id else None
        valid = (
            activation_id is not None
            and license_row is not None
            and bool(cells)
            and cells <= license_row["cell_set"]
            and low is not None
            and high is not None
            and start is not None
            and end is not None
            and positive(low, high)
            and positive(start, end)
            and contains(license_row["low_khz"], license_row["high_khz"], low, high)
            and contains(license_row["start"], license_row["end"], start, end)
        )
        if not valid:
            issue("INVALID_ACTIVATION", activation_id or license_id or "")
            continue
        activations.append(
            {
                "activation_id": activation_id,
                "license_id": license_id,
                "cells": cells,
                "low_khz": low,
                "high_khz": high,
                "start": start,
                "end": end,
            }
        )

    # ---- exclusions -----------------------------------------------------
    exclusion_rows = read_jsonl(os.path.join(data_dir, EXCLUSIONS_FILE))
    counts["exclusions"] = len(exclusion_rows)
    exclusions = []
    for row in exclusion_rows:
        if not isinstance(row, dict):
            issue("INVALID_EXCLUSION", None)
            continue
        exclusion_id = as_id(row.get("exclusion_id"))
        license_id = as_id(row.get("license_id"))
        party_id = as_id(row.get("party_id"))
        cells = as_cell_set(row.get("cells"))
        low = as_int(row.get("low_khz"))
        high = as_int(row.get("high_khz"))
        start = as_ts(row.get("start"))
        end = as_ts(row.get("end"))
        license_row = licenses.get(license_id) if license_id else None
        valid = (
            exclusion_id is not None
            and license_row is not None
            and party_id is not None
            and (party_id == "*" or party_id in party_ids)
            and bool(cells)
            and cells <= license_row["cell_set"]
            and low is not None
            and high is not None
            and start is not None
            and end is not None
            and positive(low, high)
            and positive(start, end)
            and contains(license_row["low_khz"], license_row["high_khz"], low, high)
            and contains(license_row["start"], license_row["end"], start, end)
        )
        if not valid:
            issue("INVALID_EXCLUSION", exclusion_id or license_id or "")
            continue
        exclusions.append(
            {
                "exclusion_id": exclusion_id,
                "license_id": license_id,
                "party_id": party_id,
                "cells": cells,
                "low_khz": low,
                "high_khz": high,
                "start": start,
                "end": end,
            }
        )

    # ---- auction revisions ----------------------------------------------
    auction_rows = read_jsonl(os.path.join(data_dir, AUCTION_RESULTS_FILE))
    counts["auction_revisions"] = len(auction_rows)
    auction_groups = {}
    for row in auction_rows:
        if not isinstance(row, dict):
            issue("INVALID_AUCTION", None)
            continue
        record_id = as_id(row.get("record_id"))
        auction_id = as_id(row.get("auction_id"))
        revision = as_int(row.get("revision"))
        recorded_at = as_ts(row.get("recorded_at"))
        status = row.get("status")
        if status not in (STATUS_ACTIVE, STATUS_CANCELLED):
            status = None
        license_id = as_id(row.get("license_id"))
        start = as_ts(row.get("start"))
        end = as_ts(row.get("end"))
        rate = as_int(row.get("rate_cents_per_mhz_hour"))
        structurally_valid = all(
            value is not None
            for value in (
                record_id,
                auction_id,
                revision,
                recorded_at,
                status,
                license_id,
                start,
                end,
                rate,
            )
        )
        if not structurally_valid:
            issue("INVALID_AUCTION", record_id or auction_id or "")
            continue
        auction_groups.setdefault(auction_id, []).append(
            {
                "record_id": record_id,
                "auction_id": auction_id,
                "revision": revision,
                "recorded_at": recorded_at,
                "status": status,
                "license_id": license_id,
                "start": start,
                "end": end,
                "rate": rate,
            }
        )

    effective_auctions = []
    for auction_id in sorted(auction_groups):
        rows = auction_groups[auction_id]
        max_revision = max(row["revision"] for row in rows)
        at_max = [row for row in rows if row["revision"] == max_revision]
        max_recorded = max(row["recorded_at"] for row in at_max)
        tied = [row for row in at_max if row["recorded_at"] == max_recorded]
        if len({auction_signature(row) for row in tied}) > 1:
            issue("AUCTION_TIE_CONFLICT", auction_id)
        winner = max(tied, key=lambda row: row["record_id"])
        if winner["status"] != STATUS_ACTIVE:
            continue
        license_row = licenses.get(winner["license_id"])
        valid = license_row is not None and winner["rate"] >= 0
        if valid:
            valid = positive(winner["start"], winner["end"]) and contains(
                license_row["start"], license_row["end"], winner["start"], winner["end"]
            )
        if not valid:
            issue("INVALID_AUCTION", auction_id)
            continue
        effective_auctions.append(
            {
                "auction_id": auction_id,
                "license_id": winner["license_id"],
                "start": winner["start"],
                "end": winner["end"],
                "rate": winner["rate"],
            }
        )
    effective_auctions.sort(
        key=lambda row: (row["license_id"], row["start"], row["auction_id"])
    )

    # ---- corrections -----------------------------------------------------
    correction_rows = read_jsonl(os.path.join(data_dir, CORRECTIONS_FILE))
    counts["corrections"] = len(correction_rows)
    corrections = {}
    for row in correction_rows:
        if not isinstance(row, dict):
            issue("INVALID_CORRECTION", None)
            continue
        correction_id = as_id(row.get("correction_id"))
        license_id = as_id(row.get("license_id"))
        amount = as_int(row.get("amount_cents"))
        if correction_id is None or license_id is None or amount is None:
            issue("INVALID_CORRECTION", correction_id or license_id or "")
            continue
        if not license_ok(license_id):
            issue("INVALID_CORRECTION", correction_id)
            continue
        corrections[license_id] = corrections.get(license_id, 0) + amount

    return {
        "engine_version": engine_version,
        "primary_priority": primary_priority,
        "dormant_owner_priority": dormant_owner_priority,
        "material_cents": material_cents,
        "default_rate": default_rate,
        "party_ids": party_ids,
        "licenses": licenses,
        "effective_grants": effective_grants,
        "activations": activations,
        "exclusions": exclusions,
        "effective_auctions": effective_auctions,
        "corrections": corrections,
        "guard_width": guard_width,
        "grant_decisions": grant_decisions,
        "counts": counts,
        "issues": issues,
    }


def grant_signature(row):
    return (
        row["status"],
        row["license_id"],
        row["party_id"],
        tuple(sorted(row["cells"])),
        row["low_khz"],
        row["high_khz"],
        row["start"],
        row["end"],
        row["priority"],
        row["share_bps"],
    )


def auction_signature(row):
    return (row["status"], row["license_id"], row["start"], row["end"], row["rate"])


# --------------------------------------------------------------------------
# atomic spectrum slices
# --------------------------------------------------------------------------

def build_slices(ctx):
    licenses = ctx["licenses"]
    grants_by_license = {}
    for grant in ctx["effective_grants"]:
        guard = ctx["guard_width"].get(grant["license_id"], 0)
        grant = dict(grant)
        grant["usable_low"] = grant["low_khz"] + guard
        grant["usable_high"] = grant["high_khz"] - guard
        grants_by_license.setdefault(grant["license_id"], []).append(grant)

    activations_by_license = {}
    for activation in ctx["activations"]:
        activations_by_license.setdefault(activation["license_id"], []).append(
            activation
        )
    exclusions_by_license = {}
    for exclusion in ctx["exclusions"]:
        exclusions_by_license.setdefault(exclusion["license_id"], []).append(exclusion)
    auctions_by_license = {}
    for auction in ctx["effective_auctions"]:
        auctions_by_license.setdefault(auction["license_id"], []).append(auction)

    dormant_priority = ctx["dormant_owner_priority"]
    primary_priority = ctx["primary_priority"]
    default_rate = ctx["default_rate"]

    slices = []
    for license_id in sorted(licenses):
        license_row = licenses[license_id]
        owner_party_id = license_row["owner_party_id"]
        license_grants = grants_by_license.get(license_id, [])
        license_activations = activations_by_license.get(license_id, [])
        license_exclusions = exclusions_by_license.get(license_id, [])
        license_auctions = auctions_by_license.get(license_id, [])
        for cell_id in license_row["cells"]:
            cell_grants = [g for g in license_grants if cell_id in g["cells"]]
            cell_activations = [a for a in license_activations if cell_id in a["cells"]]
            cell_exclusions = [e for e in license_exclusions if cell_id in e["cells"]]

            time_points = {license_row["start"], license_row["end"]}
            freq_points = {license_row["low_khz"], license_row["high_khz"]}
            for grant in cell_grants:
                time_points.add(grant["start"])
                time_points.add(grant["end"])
                if grant["usable_high"] > grant["usable_low"]:
                    freq_points.add(grant["usable_low"])
                    freq_points.add(grant["usable_high"])
            for activation in cell_activations:
                time_points.add(activation["start"])
                time_points.add(activation["end"])
                freq_points.add(activation["low_khz"])
                freq_points.add(activation["high_khz"])
            for exclusion in cell_exclusions:
                time_points.add(exclusion["start"])
                time_points.add(exclusion["end"])
                freq_points.add(exclusion["low_khz"])
                freq_points.add(exclusion["high_khz"])
            for auction in license_auctions:
                time_points.add(auction["start"])
                time_points.add(auction["end"])

            time_cuts = sorted(time_points)
            freq_cuts = sorted(freq_points)

            for t_index in range(len(time_cuts) - 1):
                atom_start = time_cuts[t_index]
                atom_end = time_cuts[t_index + 1]
                if atom_end <= atom_start:
                    continue
                duration = atom_end - atom_start
                covering = [
                    auction
                    for auction in license_auctions
                    if auction["start"] <= atom_start and atom_end <= auction["end"]
                ]
                if covering:
                    chosen = max(
                        covering,
                        key=lambda auction: (auction["start"], auction["auction_id"]),
                    )
                    auction_id = chosen["auction_id"]
                    rate = chosen["rate"]
                else:
                    auction_id = DEFAULT_AUCTION_ID
                    rate = default_rate

                covering_activations = [
                    activation
                    for activation in cell_activations
                    if activation["start"] <= atom_start
                    and atom_end <= activation["end"]
                ]
                covering_grants = [
                    grant
                    for grant in cell_grants
                    if grant["usable_high"] > grant["usable_low"]
                    and grant["start"] <= atom_start
                    and atom_end <= grant["end"]
                ]

                for f_index in range(len(freq_cuts) - 1):
                    atom_low = freq_cuts[f_index]
                    atom_high = freq_cuts[f_index + 1]
                    if atom_high <= atom_low:
                        continue
                    width = atom_high - atom_low
                    activated = [
                        activation
                        for activation in covering_activations
                        if activation["low_khz"] <= atom_low
                        and atom_high <= activation["high_khz"]
                    ]
                    owner_is_primary = bool(activated)
                    if activated:
                        owner_priority = primary_priority
                        owner_source = min(a["activation_id"] for a in activated)
                    else:
                        owner_priority = dormant_priority
                        owner_source = OWNER_SOURCE_PREFIX + license_id
                    candidates = [
                        (owner_priority, owner_source, owner_party_id, None)
                    ]
                    for grant in covering_grants:
                        if (
                            grant["usable_low"] <= atom_low
                            and atom_high <= grant["usable_high"]
                        ):
                            candidates.append(
                                (
                                    grant["priority"],
                                    GRANT_SOURCE_PREFIX + grant["grant_id"],
                                    grant["party_id"],
                                    grant,
                                )
                            )

                    excluded = set()
                    for exclusion in cell_exclusions:
                        if (
                            exclusion["start"] <= atom_start
                            and atom_end <= exclusion["end"]
                            and exclusion["low_khz"] <= atom_low
                            and atom_high <= exclusion["high_khz"]
                        ):
                            if exclusion["party_id"] == "*":
                                excluded.add(None)
                            else:
                                excluded.add(exclusion["party_id"])

                    survivors = [
                        item
                        for item in candidates
                        if None not in excluded and item[2] not in excluded
                    ]

                    gross = gross_cents(duration, width, rate)
                    if not survivors:
                        slices.append(
                            {
                                "license_id": license_id,
                                "cell_id": cell_id,
                                "start": atom_start,
                                "end": atom_end,
                                "low_khz": atom_low,
                                "high_khz": atom_high,
                                "duration_seconds": duration,
                                "width_khz": width,
                                "winner_party_id": None,
                                "winner_source_id": None,
                                "winner_priority": None,
                                "preempted_source_ids": [],
                                "auction_id": auction_id,
                                "rate_cents_per_mhz_hour": rate,
                                "gross_cents": 0,
                                "winner_cents": 0,
                                "owner_cents": 0,
                                "owner_is_primary": False,
                            }
                        )
                        continue

                    survivors.sort(key=lambda item: (item[0], item[1], item[2]))
                    priority, source_id, party_id, grant = survivors[0]
                    preempted = sorted(item[1] for item in survivors[1:])
                    if grant is None:
                        winner_cents = gross
                        owner_cents = 0
                    else:
                        winner_cents = share_cents(gross, grant["share_bps"])
                        owner_cents = gross - winner_cents
                    slices.append(
                        {
                            "license_id": license_id,
                            "cell_id": cell_id,
                            "start": atom_start,
                            "end": atom_end,
                            "low_khz": atom_low,
                            "high_khz": atom_high,
                            "duration_seconds": duration,
                            "width_khz": width,
                            "winner_party_id": party_id,
                            "winner_source_id": source_id,
                            "winner_priority": priority,
                            "preempted_source_ids": preempted,
                            "auction_id": auction_id,
                            "rate_cents_per_mhz_hour": rate,
                            "gross_cents": gross,
                            "winner_cents": winner_cents,
                            "owner_cents": owner_cents,
                            "owner_is_primary": owner_is_primary,
                        }
                    )

    slices.sort(
        key=lambda row: (
            row["license_id"],
            row["cell_id"],
            row["start"],
            row["low_khz"],
            row["end"],
            row["high_khz"],
        )
    )
    return slices


# --------------------------------------------------------------------------
# settlement
# --------------------------------------------------------------------------

def largest_remainder(total, weights):
    """Absolute largest remainder allocation of ``total`` over ``weights``.

    ``weights`` is a sequence of ``(party_id, weight)`` with positive weights.
    """
    weight_total = sum(weight for _, weight in weights)
    if weight_total <= 0 or total == 0:
        return {party_id: 0 for party_id, _ in weights}
    exact = [Fraction(total * weight, weight_total) for _, weight in weights]
    floors = [value.numerator // value.denominator for value in exact]
    residual = total - sum(floors)
    order = sorted(
        range(len(weights)),
        key=lambda index: (-(exact[index] - floors[index]), weights[index][0]),
    )
    for step in range(min(residual, len(order))):
        floors[order[step]] += 1
    return {weights[index][0]: floors[index] for index in range(len(weights))}


def build_settlements(ctx, slices):
    licenses = ctx["licenses"]
    license_party_gross = {}
    grant_by_id = {grant["grant_id"]: grant for grant in ctx["effective_grants"]}

    for row in slices:
        if row["winner_party_id"] is None:
            continue
        license_id = row["license_id"]
        license_row = licenses[license_id]
        winner_party = row["winner_party_id"]
        pair = (license_id, winner_party)
        license_party_gross[pair] = license_party_gross.get(pair, 0) + row["winner_cents"]
        if row["winner_source_id"].startswith(GRANT_SOURCE_PREFIX):
            owner_pair = (license_id, license_row["owner_party_id"])
            license_party_gross[owner_pair] = (
                license_party_gross.get(owner_pair, 0) + row["owner_cents"]
            )

    allocations = []
    for license_id in sorted(licenses):
        correction = ctx["corrections"].get(license_id, 0)
        participants = sorted(
            party_id
            for (lic_id, party_id), value in license_party_gross.items()
            if lic_id == license_id and value > 0
        )
        license_gross = sum(
            license_party_gross[(license_id, party_id)] for party_id in participants
        )
        if license_gross > 0:
            amounts = largest_remainder(
                abs(correction),
                [
                    (party_id, license_party_gross[(license_id, party_id)])
                    for party_id in participants
                ],
            )
            if correction < 0:
                amounts = {key: -value for key, value in amounts.items()}
            for party_id in participants:
                gross_value = license_party_gross[(license_id, party_id)]
                allocations.append(
                    {
                        "license_id": license_id,
                        "party_id": party_id,
                        "gross_cents": gross_value,
                        "correction_cents": amounts[party_id],
                        "net_cents": gross_value + amounts[party_id],
                    }
                )
        elif correction != 0:
            owner_party_id = licenses[license_id]["owner_party_id"]
            allocations.append(
                {
                    "license_id": license_id,
                    "party_id": owner_party_id,
                    "gross_cents": 0,
                    "correction_cents": correction,
                    "net_cents": correction,
                }
            )
    allocations.sort(key=lambda row: (row["license_id"], row["party_id"]))

    won_counts = {}
    preempted_counts = {}
    for row in slices:
        winner = row["winner_party_id"]
        if winner is not None:
            won_counts[winner] = won_counts.get(winner, 0) + 1
        for source_id in row["preempted_source_ids"]:
            if source_id.startswith(GRANT_SOURCE_PREFIX):
                grant = grant_by_id.get(source_id[len(GRANT_SOURCE_PREFIX):])
                if grant is not None:
                    party_id = grant["party_id"]
                    preempted_counts[party_id] = preempted_counts.get(party_id, 0) + 1

    settlement_parties = sorted({row["party_id"] for row in allocations})
    settlements = []
    for party_id in settlement_parties:
        rows = [row for row in allocations if row["party_id"] == party_id]
        gross = sum(row["gross_cents"] for row in rows)
        correction = sum(row["correction_cents"] for row in rows)
        settlements.append(
            {
                "party_id": party_id,
                "license_ids": sorted({row["license_id"] for row in rows}),
                "gross_cents": gross,
                "correction_cents": correction,
                "net_cents": gross + correction,
                "won_slice_count": won_counts.get(party_id, 0),
                "preempted_slice_count": preempted_counts.get(party_id, 0),
            }
        )
    settlements.sort(key=lambda row: row["party_id"])
    return allocations, settlements


def build_audit_trace(settlements):
    previous = HASH_SEED
    entries = []
    for row in settlements:
        canonical = json.dumps(
            row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        entry_hash = hashlib.sha256((previous + canonical).encode("utf-8")).hexdigest()
        entries.append(
            {
                "party_id": row["party_id"],
                "previous_hash": previous,
                "entry_hash": entry_hash,
            }
        )
        previous = entry_hash
    return {"entries": entries, "final_hash": previous}


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def input_file_entries(data_dir):
    entries = []
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if os.path.isfile(path) and not os.path.islink(path):
            entries.append(
                {
                    "name": name,
                    "sha256": sha256_of_file(path),
                    "bytes": os.path.getsize(path),
                }
            )
    return entries


def slice_report_row(row):
    return {
        "license_id": row["license_id"],
        "cell_id": row["cell_id"],
        "start": row["start"],
        "end": row["end"],
        "low_khz": row["low_khz"],
        "high_khz": row["high_khz"],
        "duration_seconds": row["duration_seconds"],
        "width_khz": row["width_khz"],
        "winner_party_id": row["winner_party_id"],
        "winner_source_id": row["winner_source_id"],
        "winner_priority": row["winner_priority"],
        "preempted_source_ids": row["preempted_source_ids"],
        "auction_id": row["auction_id"],
        "rate_cents_per_mhz_hour": row["rate_cents_per_mhz_hour"],
        "gross_cents": row["gross_cents"],
        "winner_cents": row["winner_cents"],
        "owner_cents": row["owner_cents"],
    }


def preemption_rows(slices):
    rows = []
    for row in slices:
        if row["preempted_source_ids"] or (
            row["winner_party_id"] is not None and row["owner_is_primary"]
        ):
            rows.append(
                {
                    "license_id": row["license_id"],
                    "cell_id": row["cell_id"],
                    "start": row["start"],
                    "end": row["end"],
                    "low_khz": row["low_khz"],
                    "high_khz": row["high_khz"],
                    "winner_party_id": row["winner_party_id"],
                    "winner_source_id": row["winner_source_id"],
                    "winner_priority": row["winner_priority"],
                    "preempted_source_ids": row["preempted_source_ids"],
                }
            )
    return rows


def effective_grant_rows(ctx):
    rows = []
    for grant in ctx["effective_grants"]:
        rows.append(
            {
                "grant_id": grant["grant_id"],
                "license_id": grant["license_id"],
                "party_id": grant["party_id"],
                "cells": sorted(grant["cells"]),
                "low_khz": grant["low_khz"],
                "high_khz": grant["high_khz"],
                "start": grant["start_text"],
                "end": grant["end_text"],
                "priority": grant["priority"],
                "share_bps": grant["share_bps"],
            }
        )
    return rows


def run(data_dir, out_dir):
    ctx = load_extract(data_dir)
    slices = build_slices(ctx)
    allocations, settlements = build_settlements(ctx, slices)

    issues = [
        {"code": code, "record_id": record_id}
        for code, record_id in sorted(ctx["issues"])
    ]
    material = ctx["material_cents"]
    exceptions = list(issues)
    for row in settlements:
        if abs(row["net_cents"]) >= material:
            exceptions.append(
                {
                    "code": "MATERIAL_SETTLEMENT",
                    "record_id": row["party_id"],
                    "net_cents": row["net_cents"],
                }
            )
    exceptions.sort(key=lambda row: (row["code"], row["record_id"]))

    input_files = input_file_entries(data_dir)
    counts = ctx["counts"]

    manifest = {
        "engine_version": ctx["engine_version"],
        "input_files": input_files,
        "valid_license_count": len(ctx["licenses"]),
        "effective_grant_count": len(ctx["effective_grants"]),
        "slice_count": len(slices),
    }
    data_quality = {
        "input_file_count": len(input_files),
        "record_counts": {key: counts[key] for key in RECORD_COUNT_KEYS},
        "issue_count": len(issues),
        "issues": issues,
    }
    grant_ledger = {
        "effective_grants": effective_grant_rows(ctx),
        "revision_decisions": ctx["grant_decisions"],
    }
    slice_ledger = {"slices": [slice_report_row(row) for row in slices]}
    preemption_ledger = {"preemptions": preemption_rows(slices)}
    party_settlements = {"parties": settlements}
    auction_adjustments = {"allocations": allocations}
    exception_register = {"exceptions": exceptions}
    audit_trace = build_audit_trace(settlements)

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    write_json(os.path.join(out_dir, "manifest.json"), manifest)
    write_json(os.path.join(out_dir, "data_quality.json"), data_quality)
    write_json(os.path.join(out_dir, "grant_ledger.json"), grant_ledger)
    write_json(os.path.join(out_dir, "spectrum_slice_ledger.json"), slice_ledger)
    write_json(os.path.join(out_dir, "preemption_ledger.json"), preemption_ledger)
    write_json(os.path.join(out_dir, "party_settlements.json"), party_settlements)
    write_json(os.path.join(out_dir, "auction_adjustments.json"), auction_adjustments)
    write_json(os.path.join(out_dir, "exception_register.json"), exception_register)
    write_json(os.path.join(out_dir, "audit_trace.json"), audit_trace)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: clear_spectrum.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(data_dir):
        sys.stderr.write("data directory not found: %s\n" % data_dir)
        return 2
    run(data_dir, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
