"""Meter read parsing and read classification for the tariff engine."""
import json
from datetime import date

REASONS = (
    "malformed_quantity",
    "unknown_meter",
    "inactive_meter",
    "outside_period",
    "duplicate_read",
)


def _text(value):
    return str(value).strip()


def _quantity(value):
    """Return the metered quantity as an int, or None when the read is unusable.

    Only a JSON integer of 0 or more is a usable quantity: text, a number
    written with a decimal point or an exponent, a boolean and null are all
    malformed.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def parse_reads(text):
    """Parse meter_reads.jsonl text into read dicts in file order."""
    reads = []
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        reads.append({
            "read_id": _text(row["read_id"]),
            "account": _text(row["account"]),
            "meter": _text(row["meter"]),
            "day": date.fromisoformat(_text(row["day"])),
            "quantity": _quantity(row["quantity"]),
        })
    return reads


def _active(window, day):
    start, end = window
    return start <= day and (end is None or day <= end)


def _within(period, day):
    return period["start"] <= day <= period["end"]


def classify(reads, meters, periods):
    """Split reads into accepted reads and exception rows.

    ``meters`` maps (account, meter) to its (active_from, active_to) window and
    ``periods`` maps an account to its billing period row. A read receives the
    first applicable reason of :data:`REASONS`.
    """
    accepted = []
    exceptions = []
    seen = set()
    for read in reads:
        key = (read["account"], read["meter"])
        reason = None
        if read["quantity"] is None:
            reason = "malformed_quantity"
        elif key not in meters:
            reason = "unknown_meter"
        elif not _active(meters[key], read["day"]):
            reason = "inactive_meter"
        elif not _within(periods[read["account"]], read["day"]):
            reason = "outside_period"
        elif key + (read["day"],) in seen:
            reason = "duplicate_read"
        if reason is None:
            seen.add(key + (read["day"],))
            accepted.append(read)
        else:
            exceptions.append({
                "read_id": read["read_id"],
                "account": read["account"],
                "reason": reason,
            })
    return accepted, exceptions
