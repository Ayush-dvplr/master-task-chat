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

    Text, decimals, booleans and null are malformed; nothing is coerced.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _flag(value):
    return value is True


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
            "quantity": _quantity(row.get("quantity")),
            "estimated": _flag(row.get("estimated", False)),
            "cumulative": _flag(row.get("cumulative", False)),
        })
    return reads


def _active(windows, day):
    return any(start <= day and (end is None or day <= end) for start, end in windows)


def _in_period(periods, day):
    return any(row["start"] <= day <= row["end"] for row in periods)


def classify(reads, meters, periods):
    """Split reads into accepted reads (file order) and exception rows.

    ``meters`` maps (account, meter) to its list of (active_from, active_to)
    windows and ``periods`` maps an account to its list of billing rows.
    Non-estimated reads are settled first, since rule 6 looks at accepted
    non-estimated reads anywhere in the file.
    """
    reasons = {}
    seen = set()
    accepted_actual = set()
    for estimated in (False, True):
        for index, read in enumerate(reads):
            if read["estimated"] is not estimated:
                continue
            key = (read["account"], read["meter"])
            slot = key + (read["day"],)
            reason = None
            if read["quantity"] is None:
                reason = "malformed_quantity"
            elif key not in meters:
                reason = "unknown_meter"
            elif not _active(meters[key], read["day"]):
                reason = "inactive_meter"
            elif not _in_period(periods.get(read["account"], []), read["day"]):
                reason = "outside_period"
            elif slot + (estimated,) in seen:
                reason = "duplicate_read"
            elif estimated and slot in accepted_actual:
                reason = "replaced_estimate"
            if reason is None:
                seen.add(slot + (estimated,))
                if not estimated:
                    accepted_actual.add(slot)
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
