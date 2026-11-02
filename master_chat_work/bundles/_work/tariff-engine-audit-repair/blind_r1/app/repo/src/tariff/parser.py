"""Meter read parsing and read classification for the tariff engine."""
import json
from datetime import date
from decimal import Decimal

REASONS = (
    "malformed_quantity",
    "unknown_meter",
    "inactive_meter",
    "outside_period",
    "duplicate_read",
    "replaced_estimate",
)


def _text(value):
    return str(value).strip()


def _quantity(value):
    """Return the quantity when it is a JSON integer of 0 or more, else None.

    Text, decimals, booleans, null and negative numbers are malformed.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _estimated(value):
    return value is True


def parse_reads(text):
    """Parse meter_reads.jsonl text into read dicts in file order."""
    reads = []
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line, parse_float=Decimal)
        reads.append({
            "read_id": _text(row["read_id"]),
            "account": _text(row["account"]),
            "meter": _text(row["meter"]),
            "day": date.fromisoformat(_text(row["day"])),
            "quantity": _quantity(row.get("quantity")),
            "estimated": _estimated(row.get("estimated", False)),
        })
    return reads


def _active(windows, day):
    """True when ``day`` falls in any (start, end) window; end None is open."""
    return any(start <= day and (end is None or day <= end) for start, end in windows)


def _reason(read, meters, periods):
    """Reason from rules 1 to 4, or None."""
    key = (read["account"], read["meter"])
    if read["quantity"] is None:
        return "malformed_quantity"
    if key not in meters:
        return "unknown_meter"
    if not _active(meters[key], read["day"]):
        return "inactive_meter"
    if not any(row["start"] <= read["day"] <= row["end"]
               for row in periods.get(read["account"], [])):
        return "outside_period"
    return None


def classify(reads, meters, periods):
    """Split reads into accepted reads (file order) and exception rows.

    ``meters`` maps (account, meter) to its list of (active_from, active_to)
    windows and ``periods`` maps an account to its list of billing rows. Each
    read receives the first exception of ``REASONS`` that applies. Reads that
    are not estimated are settled first, since a replaced estimate depends on
    an accepted actual read anywhere in the file.
    """
    reasons = {}
    accepted_keys = {False: set(), True: set()}
    for flag in (False, True):
        for index, read in enumerate(reads):
            if read["estimated"] is not flag:
                continue
            day_key = (read["account"], read["meter"], read["day"])
            reason = _reason(read, meters, periods)
            if reason is None and day_key in accepted_keys[flag]:
                reason = "duplicate_read"
            if reason is None and flag and day_key in accepted_keys[False]:
                reason = "replaced_estimate"
            if reason is None:
                accepted_keys[flag].add(day_key)
            reasons[index] = reason
    accepted = []
    exceptions = []
    for index, read in enumerate(reads):
        if reasons[index] is None:
            accepted.append(read)
        else:
            exceptions.append({
                "read_id": read["read_id"],
                "account": read["account"],
                "reason": reasons[index],
            })
    exceptions.sort(key=lambda row: row["read_id"])
    return accepted, exceptions
