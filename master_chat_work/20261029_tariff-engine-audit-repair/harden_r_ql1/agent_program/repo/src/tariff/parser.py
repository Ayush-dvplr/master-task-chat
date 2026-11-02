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
    """Return the metered quantity as an int, or None when the read is unusable.

    A usable quantity is a JSON integer of 0 or more; text, decimals and
    booleans are not quantities.
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
            "estimated": _flag(row.get("estimated")),
            "cumulative": _flag(row.get("cumulative")),
        })
    return reads


def _active(windows, day):
    return any(start <= day and (end is None or day <= end) for start, end in windows)


def _in_period(periods, day):
    return any(start <= day <= end for start, end in periods)


def _first_reason(read, meters, periods):
    """Return the exception of a read from the rules that look at it alone."""
    key = (read["account"], read["meter"])
    if read["quantity"] is None:
        return "malformed_quantity"
    if key not in meters:
        return "unknown_meter"
    if not _active(meters[key], read["day"]):
        return "inactive_meter"
    if not _in_period(periods.get(read["account"], ()), read["day"]):
        return "outside_period"
    return None


def classify(reads, meters, periods):
    """Split reads into accepted reads and exception rows.

    ``meters`` maps (account, meter) to its list of active windows and
    ``periods`` maps an account to its list of (start, end) billing periods.
    Measured reads are judged before the estimates, so an accepted measured
    read replaces every estimate of its day.
    """
    reasons = [None] * len(reads)
    measured = set()
    for index, read in enumerate(reads):
        if read["estimated"]:
            continue
        key = (read["account"], read["meter"], read["day"])
        reason = _first_reason(read, meters, periods)
        if reason is None and key in measured:
            reason = "duplicate_read"
        if reason is None:
            measured.add(key)
        reasons[index] = reason
    estimates = set()
    for index, read in enumerate(reads):
        if not read["estimated"]:
            continue
        key = (read["account"], read["meter"], read["day"])
        reason = _first_reason(read, meters, periods)
        if reason is None and key in estimates:
            reason = "duplicate_read"
        elif reason is None and key in measured:
            reason = "replaced_estimate"
        if reason is None:
            estimates.add(key)
        reasons[index] = reason
    accepted = [read for index, read in enumerate(reads) if reasons[index] is None]
    exceptions = sorted(
        ({"read_id": read["read_id"], "account": read["account"], "reason": reasons[index]}
         for index, read in enumerate(reads) if reasons[index] is not None),
        key=lambda row: row["read_id"],
    )
    return accepted, exceptions


def billed_quantities(accepted):
    """Map the read_id of every accepted read to its billed quantity.

    A cumulative read bills the rise over the previous accepted cumulative read
    of its meter: 0 for the first one and its whole quantity when the meter
    went backwards.
    """
    billed = {}
    by_meter = {}
    for read in accepted:
        by_meter.setdefault((read["account"], read["meter"]), []).append(read)
    for reads in by_meter.values():
        previous = None
        for read in sorted((r for r in reads if r["cumulative"]), key=lambda r: r["day"]):
            if previous is None:
                billed[read["read_id"]] = 0
            elif previous > read["quantity"]:
                billed[read["read_id"]] = read["quantity"]
            else:
                billed[read["read_id"]] = read["quantity"] - previous
            previous = read["quantity"]
        for read in reads:
            if not read["cumulative"]:
                billed[read["read_id"]] = read["quantity"]
    return billed
