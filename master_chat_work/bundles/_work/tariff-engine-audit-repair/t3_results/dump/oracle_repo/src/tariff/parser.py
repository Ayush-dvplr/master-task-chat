"""Meter read parsing and read classification for the tariff engine."""
import json
from datetime import date

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

    A JSON string, a number written with a decimal point or an exponent,
    true, false, null and negative integers are all malformed.
    """
    if type(value) is int and value >= 0:
        return value
    return None


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
            "estimated": row.get("estimated", False) is True,
            "cumulative": row.get("cumulative", False) is True,
        })
    return reads


def _active(windows, day):
    return any(start <= day and (end is None or day <= end) for start, end in windows)


def _row(rows, day):
    """The billing row whose period holds ``day``, or None."""
    for row in rows:
        if row["start"] <= day <= row["end"]:
            return row
    return None


def _reason(read, meters, periods, seen, actual):
    key = (read["account"], read["meter"])
    if read["quantity"] is None:
        return "malformed_quantity"
    if key not in meters:
        return "unknown_meter"
    if not _active(meters[key], read["day"]):
        return "inactive_meter"
    if _row(periods.get(read["account"], []), read["day"]) is None:
        return "outside_period"
    if key + (read["day"], read["estimated"]) in seen:
        return "duplicate_read"
    if read["estimated"] and key + (read["day"],) in actual:
        return "replaced_estimate"
    return None


def classify(reads, meters, periods):
    """Split reads into accepted reads and exception rows.

    ``meters`` maps (account, meter) to its list of (active_from, active_to)
    windows and ``periods`` maps an account to its billing rows by start.
    Reads that are not estimated are classified first, so an estimate is
    replaced by an accepted actual read of its day wherever that read stands.
    Each read gets the first exception of the contract list that applies.
    """
    accepted = []
    exceptions = []
    seen = set()
    actual = set()
    for read in [r for r in reads if not r["estimated"]] + [r for r in reads if r["estimated"]]:
        reason = _reason(read, meters, periods, seen, actual)
        if reason is None:
            seen.add((read["account"], read["meter"], read["day"], read["estimated"]))
            if not read["estimated"]:
                actual.add((read["account"], read["meter"], read["day"]))
            accepted.append(read)
        else:
            exceptions.append({
                "read_id": read["read_id"],
                "account": read["account"],
                "reason": reason,
            })
    return accepted, exceptions
