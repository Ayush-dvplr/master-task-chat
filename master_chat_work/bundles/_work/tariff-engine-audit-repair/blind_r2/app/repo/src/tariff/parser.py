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
    """Return the metered quantity as an int, or None when the read is malformed.

    The contract only allows a JSON integer of 0 or more: text, decimals
    (even ``40.0``), booleans and missing values are all malformed.
    """
    if type(value) is not int or value < 0:
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
            "quantity": _quantity(row.get("quantity")),
            "estimated": row.get("estimated") is True,
            "cumulative": row.get("cumulative") is True,
        })
    return reads


def _active(windows, day):
    """True when ``day`` falls in one of the (active_from, active_to) windows."""
    return any(start <= day and (end is None or day <= end) for start, end in windows)


def _in_period(periods, day):
    return any(start <= day <= end for start, end in periods)


def classify(reads, meters, periods):
    """Split reads into accepted reads (file order) and exception rows.

    ``meters`` maps (account, meter) to its list of (active_from, active_to)
    windows and ``periods`` maps an account to its list of (start, end) billing
    periods. Each read receives at most one exception, the first that applies:
    malformed_quantity, unknown_meter, inactive_meter, outside_period,
    duplicate_read, replaced_estimate. Exceptions are sorted by read_id.
    """
    reasons = {}
    accepted_ids = set()
    seen = set()
    actual_days = set()

    def check(index, read):
        key = (read["account"], read["meter"])
        if read["quantity"] is None:
            return "malformed_quantity"
        if key not in meters:
            return "unknown_meter"
        if not _active(meters[key], read["day"]):
            return "inactive_meter"
        if not _in_period(periods.get(read["account"], ()), read["day"]):
            return "outside_period"
        if key + (read["day"], read["estimated"]) in seen:
            return "duplicate_read"
        if read["estimated"] and key + (read["day"],) in actual_days:
            return "replaced_estimate"
        return None

    # Actual (non-estimated) reads never depend on estimated ones, so they are
    # settled first; estimated reads are then checked against them.
    for estimated in (False, True):
        for index, read in enumerate(reads):
            if read["estimated"] is not estimated:
                continue
            reason = check(index, read)
            key = (read["account"], read["meter"], read["day"])
            if reason is None:
                seen.add(key + (read["estimated"],))
                if not estimated:
                    actual_days.add(key)
                accepted_ids.add(index)
            else:
                reasons[index] = reason

    accepted = [read for index, read in enumerate(reads) if index in accepted_ids]
    exceptions = [
        {"read_id": reads[index]["read_id"], "account": reads[index]["account"],
         "reason": reason}
        for index, reason in reasons.items()
    ]
    exceptions.sort(key=lambda row: row["read_id"])
    return accepted, exceptions


def billed_quantities(accepted):
    """Return the billed quantity of each accepted read, in the same order.

    A cumulative read bills its quantity less the quantity of the accepted
    cumulative read of the same account and meter with the latest earlier day;
    0 when there is none, and its whole quantity when that read is larger.
    """
    cumulative = {}
    for read in accepted:
        if read["cumulative"]:
            cumulative.setdefault((read["account"], read["meter"]), []).append(read)
    billed = []
    for read in accepted:
        if not read["cumulative"]:
            billed.append(read["quantity"])
            continue
        earlier = [other for other in cumulative[(read["account"], read["meter"])]
                   if other["day"] < read["day"]]
        if not earlier:
            billed.append(0)
            continue
        previous = max(earlier, key=lambda other: other["day"])["quantity"]
        if previous > read["quantity"]:
            billed.append(read["quantity"])
        else:
            billed.append(read["quantity"] - previous)
    return billed
