#!/usr/bin/env python3
"""Charter-party laytime settlement engine for data contract MLSE-1.0.

Usage:
    python3 settle_laytime.py DATA_DIR OUT_DIR

Reads the settlement extract in DATA_DIR and writes the nine MLSE-1.0 reports
(manifest, data_quality, event_ledger, interval_ledger, call_settlements,
voyage_rollups, charterer_statements, exception_register, audit_trace) to
OUT_DIR.

Conventions fixed by the contract and applied throughout:

* Intervals are half-open ``[start,end)`` and instants are UTC.
* Seconds and cents are exact integers; every rounding checkpoint is a
  :func:`round_half_up` of an exact rational (Decimal ``ROUND_HALF_UP``:
  ties away from zero).
* Input row order and object-key order are never semantic; stable
  identifiers supply every tie-break.
* A quality issue is ``{"code", "record_id"}`` where ``record_id`` names the
  offending record: a call id for call quarantine, a stoppage/operation id for
  an invalid activity record, an event id for a revision tie conflict.  A
  ``MATERIAL_SETTLEMENT`` row adds ``net_due_cents``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, time, timedelta, timezone
from fractions import Fraction

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MICROSECONDS = 1_000_000
GENESIS_HASH = "0" * 64
BPS_DENOMINATOR = 10_000
SECONDS_PER_DAY = 86_400
MONEY_SCALE = SECONDS_PER_DAY * BPS_DENOMINATOR
DEFAULT_RATE_PERIOD_ID = "default"
DEFAULT_MULTIPLIER_BPS = 10_000
NOR_TYPE = "NOR_ACCEPTED"
END_TYPE = "CARGO_END"
CANCELLED = "cancelled"
ENGINE_FALLBACK = "MLSE-1.0"

# Documented input files, in the order the contract enumerates them.
JSONL_TARGETS = {
    "adjustments.jsonl": "adjustments",
    "cargo_operations.jsonl": "cargo_operations",
    "event_revisions.jsonl": "event_revisions",
    "port_calls.jsonl": "port_calls",
    "rate_periods.jsonl": "rate_periods",
    "stoppages.jsonl": "stoppages",
}
INPUT_FILES = tuple(
    sorted(
        list(JSONL_TARGETS)
        + ["contracts.json", "holidays.json", "policy.json"]
    )
)

REPORT_NAMES = (
    "manifest",
    "data_quality",
    "event_ledger",
    "interval_ledger",
    "call_settlements",
    "voyage_rollups",
    "charterer_statements",
    "exception_register",
    "audit_trace",
)

EVENT_FIELDS = (
    "call_id",
    "event_id",
    "event_time",
    "event_type",
    "record_id",
    "recorded_at",
    "revision",
    "status",
)


# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------


def canonical_json(obj):
    """Compact, sorted-key JSON used for hashing and deterministic tie-breaks."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def dump_json(payload):
    """Report serialization: indent 2, sorted keys, one trailing newline."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def sha256_of_file(path):
    digest = hashlib.sha256()
    total = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def as_text(value):
    return value if isinstance(value, str) else None


def as_int(value, default=None):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError:
            try:
                return int(float(text))
            except ValueError:
                return default
    return default


def as_fraction(value):
    if isinstance(value, bool):
        return Fraction(int(value))
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        try:
            return Fraction(value.strip())
        except (ValueError, ZeroDivisionError):
            return None
    return None


def round_half_up(value):
    """Exact Decimal ROUND_HALF_UP of a rational (ties away from zero)."""
    fraction = Fraction(value)
    numerator = fraction.numerator
    denominator = fraction.denominator
    if numerator >= 0:
        return (2 * numerator + denominator) // (2 * denominator)
    return -((-2 * numerator + denominator) // (2 * denominator))


def number_out(value):
    """JSON-safe rendering of an exact quantity."""
    fraction = Fraction(value)
    if fraction.denominator == 1:
        return int(fraction)
    return float(fraction)


def parse_instant(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text[-1] in "Zz":
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def to_us(moment):
    return (moment - EPOCH) // timedelta(microseconds=1)


def from_us(value):
    return EPOCH + timedelta(microseconds=value)


def format_instant(value):
    text = from_us(value).isoformat()
    return text[:-6] + "Z" if text.endswith("+00:00") else text


def midnight_us(day):
    return to_us(datetime.combine(day, time.min, tzinfo=timezone.utc))


def issue_sort_key(issue):
    return (
        issue.get("code") or "",
        issue.get("record_id") or "",
        issue.get("net_due_cents", 0) or 0,
    )


def index_by_id(rows, id_field):
    """Map id -> row, order independent, choosing the least canonical row on dupes."""
    chosen = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = as_text(row.get(id_field))
        if not key:
            continue
        current = chosen.get(key)
        if current is None or canonical_json(row) < canonical_json(current):
            chosen[key] = row
    return chosen


# --------------------------------------------------------------------------
# input loading
# --------------------------------------------------------------------------


def read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                rows.append(None)
    return rows


def extract_holidays(payload):
    if isinstance(payload, list):
        return {value for value in payload if isinstance(value, str)}
    if isinstance(payload, dict):
        dates = set()
        for value in payload.values():
            if isinstance(value, list):
                dates.update(item for item in value if isinstance(item, str))
        return dates
    return set()


def load_inputs(data_dir):
    state = {
        "files": [],
        "record_counts": {},
        "policy": {},
        "contracts": [],
        "holidays": set(),
        "port_calls": [],
        "event_revisions": [],
        "stoppages": [],
        "cargo_operations": [],
        "rate_periods": [],
        "adjustments": [],
    }
    for name in INPUT_FILES:
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        digest, size = sha256_of_file(path)
        state["files"].append({"bytes": size, "name": name, "sha256": digest})
        if name in JSONL_TARGETS:
            rows = read_jsonl(path)
            state[JSONL_TARGETS[name]] = rows
            state["record_counts"][name] = len(rows)
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except ValueError:
            payload = None
        if name == "policy.json":
            state["policy"] = payload if isinstance(payload, dict) else {}
            state["record_counts"][name] = 1
        elif name == "contracts.json":
            state["contracts"] = payload if isinstance(payload, list) else []
            state["record_counts"][name] = len(state["contracts"])
        elif name == "holidays.json":
            state["holidays"] = extract_holidays(payload)
            state["record_counts"][name] = len(state["holidays"])
    state["files"].sort(key=lambda row: row["name"])
    return state


# --------------------------------------------------------------------------
# effective events and quarantine
# --------------------------------------------------------------------------


def revision_rank(row):
    """Contract selection tuple (integer revision, recorded_at, record_id)."""
    moment = parse_instant(row.get("recorded_at"))
    return (
        revision_order(row),
        (1, to_us(moment)) if moment is not None else (0, 0),
        as_text(row.get("record_id")) or "",
    )


def revision_order(row):
    return as_int(row.get("revision"), 0)


def recorded_rank(row):
    """``(revision, recorded_at)`` -- the fields a tie may share."""
    moment = parse_instant(row.get("recorded_at"))
    return (
        revision_order(row),
        (1, to_us(moment)) if moment is not None else (0, 0),
    )


def resolve_revisions(rows):
    groups = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        event_id = as_text(row.get("event_id"))
        if event_id is None:
            continue
        groups.setdefault(event_id, []).append(row)

    decisions = []
    effective = []
    issues = []
    for event_id in sorted(groups):
        group = groups[event_id]
        winner = max(group, key=lambda row: (revision_rank(row), canonical_json(row)))
        rank = recorded_rank(winner)
        tied = [row for row in group if recorded_rank(row) == rank]
        signatures = {
            (
                as_text(row.get("status")),
                as_text(row.get("call_id")),
                as_text(row.get("event_type")),
                as_text(row.get("event_time")),
            )
            for row in tied
        }
        if len(tied) > 1 and len(signatures) > 1:
            issues.append({"code": "REVISION_TIE_CONFLICT", "record_id": event_id})
        winner_id = as_text(winner.get("record_id")) or ""
        decisions.append(
            {
                "discarded": sorted(
                    {
                        as_text(row.get("record_id")) or ""
                        for row in group
                    }
                    - {winner_id}
                ),
                "event_id": event_id,
                "winner": winner_id,
            }
        )
        if as_text(winner.get("status")) == CANCELLED:
            continue
        moment = parse_instant(winner.get("event_time"))
        if moment is None:
            continue
        recorded = parse_instant(winner.get("recorded_at"))
        effective.append(
            {
                "call_id": as_text(winner.get("call_id")),
                "event_id": event_id,
                "event_time": format_instant(to_us(moment)),
                "event_type": as_text(winner.get("event_type")),
                "record_id": winner_id,
                "recorded_at": (
                    format_instant(to_us(recorded))
                    if recorded is not None
                    else as_text(winner.get("recorded_at"))
                ),
                "revision": as_int(winner.get("revision"), 0),
                "status": as_text(winner.get("status")),
                "_time_us": to_us(moment),
            }
        )
    effective.sort(
        key=lambda ev: (
            ev["call_id"] or "",
            ev["_time_us"],
            ev["event_type"] or "",
            ev["event_id"],
        )
    )
    return effective, decisions, issues


def collect_calls(rows):
    calls = []
    for row in index_by_id(rows, "call_id").values():
        calls.append(
            {
                "call_id": as_text(row.get("call_id")) or "",
                "voyage_id": as_text(row.get("voyage_id")) or "",
                "sequence": as_int(row.get("sequence"), 0),
                "charterer_id": as_text(row.get("charterer_id")) or "",
                "contract_id": as_text(row.get("contract_id")) or "",
            }
        )
    calls.sort(key=lambda call: (call["voyage_id"], call["sequence"], call["call_id"]))
    return calls


def collect_stoppages(rows, issues):
    valid = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        start = parse_instant(row.get("start"))
        end = parse_instant(row.get("end"))
        if start is None or end is None:
            continue
        if to_us(start) >= to_us(end):
            issues.append(
                {
                    "code": "INVALID_STOPPAGE",
                    "record_id": as_text(row.get("stoppage_id")) or "",
                }
            )
            continue
        valid.append(
            {
                "call_id": as_text(row.get("call_id")),
                "stoppage_id": as_text(row.get("stoppage_id")) or "",
                "code": as_text(row.get("code")) or "",
                "start_us": to_us(start),
                "end_us": to_us(end),
            }
        )
    return valid


def collect_operations(rows, issues):
    valid = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        start = parse_instant(row.get("start"))
        end = parse_instant(row.get("end"))
        quantity = as_fraction(row.get("quantity_tonnes"))
        if start is None or end is None or quantity is None:
            continue
        if to_us(start) >= to_us(end) or quantity < 0:
            issues.append(
                {
                    "code": "INVALID_CARGO_OPERATION",
                    "record_id": as_text(row.get("operation_id")) or "",
                }
            )
            continue
        valid.append(
            {
                "call_id": as_text(row.get("call_id")),
                "operation_id": as_text(row.get("operation_id")) or "",
                "start_us": to_us(start),
                "end_us": to_us(end),
                "quantity": quantity,
            }
        )
    return valid


def resolve_windows(calls, effective_events):
    """Half-open calculation window per call, plus call quarantine issues."""
    issues = []
    windows = {}
    events_by_call = {}
    for event in effective_events:
        events_by_call.setdefault(event["call_id"], []).append(event)
    for call in calls:
        call_id = call["call_id"]
        events = events_by_call.get(call_id, [])
        nor_events = [event for event in events if event["event_type"] == NOR_TYPE]
        end_events = [event for event in events if event["event_type"] == END_TYPE]
        if not nor_events or not end_events:
            issues.append({"code": "MISSING_REQUIRED_EVENT", "record_id": call_id})
            continue
        first_nor = min(
            nor_events, key=lambda ev: (ev["_time_us"], ev["event_id"])
        )
        first_end = min(
            end_events, key=lambda ev: (ev["_time_us"], ev["event_id"])
        )
        if first_nor["_time_us"] >= first_end["_time_us"]:
            issues.append({"code": "NON_POSITIVE_CALL_WINDOW", "record_id": call_id})
            continue
        windows[call_id] = (first_nor["_time_us"], first_end["_time_us"])
    return windows, issues


# --------------------------------------------------------------------------
# atomic laytime intervals
# --------------------------------------------------------------------------


def build_intervals(call_id, window, stoppages, operations, holidays, factors, rank):
    start_us, end_us = window
    bounds = {start_us, end_us}
    active_stops = []
    for stoppage in stoppages:
        left = max(stoppage["start_us"], start_us)
        right = min(stoppage["end_us"], end_us)
        if left < right:
            bounds.update((left, right))
            active_stops.append((left, right, stoppage))
    active_ops = []
    for operation in operations:
        left = max(operation["start_us"], start_us)
        right = min(operation["end_us"], end_us)
        if left < right:
            bounds.update((left, right))
            active_ops.append((left, right, operation))

    day = from_us(start_us).date()
    while True:
        moment = midnight_us(day)
        if moment > end_us:
            break
        if start_us <= moment:
            bounds.add(moment)
        day += timedelta(days=1)

    unranked = len(rank)
    intervals = []
    ordered = sorted(bounds)
    for left, right in zip(ordered, ordered[1:]):
        if right <= left:
            continue
        duration = (right - left) // MICROSECONDS
        covering = [
            stoppage
            for stop_left, stop_right, stoppage in active_stops
            if stop_left < right and left < stop_right
        ]
        if covering:
            chosen = min(
                covering,
                key=lambda stoppage: (
                    rank.get(stoppage["code"], unranked),
                    stoppage["stoppage_id"],
                ),
            )
            code, source = chosen["code"], chosen["stoppage_id"]
        else:
            day_text = from_us(left).date().isoformat()
            if day_text in holidays:
                code, source = "HOLIDAY", day_text
            else:
                covering_ops = [
                    operation
                    for op_left, op_right, operation in active_ops
                    if op_left < right and left < op_right
                ]
                if covering_ops:
                    code = "CARGO_WORK"
                    source = min(operation["operation_id"] for operation in covering_ops)
                else:
                    code, source = "IDLE", "idle"
        factor = as_int(factors.get(code), 0)
        if factor is None:
            factor = 0
        intervals.append(
            {
                "call_id": call_id,
                "start": format_instant(left),
                "end": format_instant(right),
                "duration_seconds": duration,
                "code": code,
                "source": source,
                "factor_bps": factor,
                "weighted_second_bps": duration * factor,
            }
        )
    return intervals


# --------------------------------------------------------------------------
# money
# --------------------------------------------------------------------------


def select_rate_period(rows, cargo_end_us):
    moment = cargo_end_us - MICROSECONDS
    best_key = None
    best_row = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        start = parse_instant(row.get("start"))
        end = parse_instant(row.get("end"))
        if start is None or end is None:
            continue
        start_us, end_us = to_us(start), to_us(end)
        if start_us <= moment < end_us:
            key = (start_us, as_text(row.get("period_id")) or "")
            if best_key is None or key > best_key:
                best_key, best_row = key, row
    if best_row is None:
        return DEFAULT_RATE_PERIOD_ID, DEFAULT_MULTIPLIER_BPS
    multiplier = as_int(best_row.get("multiplier_bps"), DEFAULT_MULTIPLIER_BPS)
    if multiplier is None:
        multiplier = DEFAULT_MULTIPLIER_BPS
    period_id = as_text(best_row.get("period_id")) or DEFAULT_RATE_PERIOD_ID
    return period_id, multiplier


def demurrage_cents(settled_seconds, tiers, multiplier_bps):
    """Consume positive settled seconds through the cumulative tiers in order."""
    total = 0
    lower = 0
    remaining = settled_seconds
    for tier in tiers:
        if not isinstance(tier, dict) or remaining <= 0:
            break
        rate = as_int(tier.get("usd_cents_per_day"), 0) or 0
        upper = as_int(tier.get("up_to_seconds"))
        if upper is None:
            take = remaining
        else:
            take = min(remaining, max(upper - lower, 0))
            lower = upper
        if take > 0:
            total += round_half_up(
                Fraction(take * rate * multiplier_bps, MONEY_SCALE)
            )
        remaining -= take
    return total


def allocate_total(total_cents, weights):
    """Split a signed voyage adjustment total over (call_id, tonnes) weights."""
    allocation = {call_id: 0 for call_id, _ in weights}
    if not weights or total_cents == 0:
        return allocation
    denominator = sum((tonnes for _, tonnes in weights), Fraction(0))
    if denominator == 0:
        return allocation
    magnitude = abs(total_cents)
    sign = 1 if total_cents > 0 else -1
    remainders = []
    assigned = 0
    for call_id, tonnes in weights:
        exact = Fraction(magnitude) * tonnes / denominator
        base = exact.numerator // exact.denominator
        allocation[call_id] = base
        assigned += base
        remainders.append((exact - base, call_id))
    leftover = magnitude - assigned
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for index in range(min(leftover, len(remainders))):
        allocation[remainders[index][1]] += 1
    return {call_id: sign * value for call_id, value in allocation.items()}


# --------------------------------------------------------------------------
# settlement
# --------------------------------------------------------------------------


def build_reports(data_dir):
    inputs = load_inputs(data_dir)
    policy = inputs["policy"]
    precedence = [
        code for code in policy.get("precedence", []) if isinstance(code, str)
    ]
    rank = {code: index for index, code in enumerate(precedence)}
    raw_factors = policy.get("count_factors_bps")
    factors = raw_factors if isinstance(raw_factors, dict) else {}
    holidays = inputs["holidays"]
    contracts = {}
    for row in inputs["contracts"]:
        if isinstance(row, dict) and as_text(row.get("contract_id")):
            contracts[as_text(row["contract_id"])] = row
    raw_threshold = policy.get("exception_net_due_cents")
    threshold = as_int(raw_threshold) if raw_threshold is not None else None

    issues = []
    effective_events, decisions, revision_issues = resolve_revisions(
        inputs["event_revisions"]
    )
    issues.extend(revision_issues)

    calls = collect_calls(inputs["port_calls"])
    stoppages = collect_stoppages(inputs["stoppages"], issues)
    operations = collect_operations(inputs["cargo_operations"], issues)
    windows, window_issues = resolve_windows(calls, effective_events)
    issues.extend(window_issues)

    stoppages_by_call = {}
    for stoppage in stoppages:
        stoppages_by_call.setdefault(stoppage["call_id"], []).append(stoppage)
    operations_by_call = {}
    for operation in operations:
        operations_by_call.setdefault(operation["call_id"], []).append(operation)

    valid_calls = [call for call in calls if call["call_id"] in windows]
    calls_by_voyage = {}
    for call in valid_calls:
        calls_by_voyage.setdefault(call["voyage_id"], []).append(call)

    intervals = []
    counted = {}
    tonnage = {}
    allowance = {}
    for call in valid_calls:
        call_id = call["call_id"]
        window = windows[call_id]
        rows = build_intervals(
            call_id,
            window,
            stoppages_by_call.get(call_id, []),
            operations_by_call.get(call_id, []),
            holidays,
            factors,
            rank,
        )
        intervals.extend(rows)
        weighted = sum(row["weighted_second_bps"] for row in rows)
        counted[call_id] = round_half_up(Fraction(weighted, BPS_DENOMINATOR))
        tonnage[call_id] = sum(
            (operation["quantity"] for operation in operations_by_call.get(call_id, [])),
            Fraction(0),
        )
        contract = contracts.get(call["contract_id"], {})
        base = as_int(contract.get("base_allowance_seconds"), 0) or 0
        rate = as_int(contract.get("cargo_rate_tph"), 0) or 0
        cargo_part = (
            round_half_up(tonnage[call_id] * 3600 / rate) if rate > 0 else 0
        )
        allowance[call_id] = (base, cargo_part, base + cargo_part)

    settlements = []
    settlements_by_id = {}
    bank_by_voyage = {}
    for call in valid_calls:
        call_id = call["call_id"]
        voyage_id = call["voyage_id"]
        contract = contracts.get(call["contract_id"], {})
        cap = as_int(contract.get("bank_cap_seconds"), 0) or 0
        base, cargo_part, allowed = allowance[call_id]
        raw_delta = counted[call_id] - allowed
        bank_before = bank_by_voyage.get(voyage_id, 0)
        combined = bank_before + raw_delta
        is_final = call_id is calls_by_voyage[voyage_id][-1]["call_id"]
        bank_after = 0 if is_final else max(-cap, min(cap, combined))
        settled = combined - bank_after
        bank_by_voyage[voyage_id] = bank_after

        period_id, multiplier = select_rate_period(
            inputs["rate_periods"], windows[call_id][1]
        )
        if settled > 0:
            demurrage = demurrage_cents(
                settled, contract.get("demurrage_tiers") or [], multiplier
            )
            despatch = 0
        elif settled < 0:
            demurrage = 0
            despatch_rate = as_int(
                contract.get("despatch_usd_cents_per_day"), 0
            ) or 0
            despatch = round_half_up(
                Fraction(-settled * despatch_rate * multiplier, MONEY_SCALE)
            )
        else:
            demurrage = 0
            despatch = 0

        settlement = {
            "call_id": call_id,
            "voyage_id": voyage_id,
            "sequence": call["sequence"],
            "charterer_id": call["charterer_id"],
            "contract_id": call["contract_id"],
            "window_start": format_instant(windows[call_id][0]),
            "window_end": format_instant(windows[call_id][1]),
            "cargo_tonnes": number_out(tonnage[call_id]),
            "base_allowance_seconds": base,
            "cargo_allowance_seconds": cargo_part,
            "allowed_seconds": allowed,
            "counted_seconds": counted[call_id],
            "raw_delta_seconds": raw_delta,
            "bank_before_seconds": bank_before,
            "bank_cap_seconds": cap,
            "combined_seconds": combined,
            "bank_after_seconds": bank_after,
            "settled_seconds": settled,
            "rate_period_id": period_id,
            "multiplier_bps": multiplier,
            "demurrage_cents": demurrage,
            "despatch_cents": despatch,
        }
        settlements.append(settlement)
        settlements_by_id[call_id] = settlement

    adjustment_totals = {}
    for row in inputs["adjustments"]:
        if not isinstance(row, dict):
            continue
        voyage_id = as_text(row.get("voyage_id"))
        if voyage_id is None:
            continue
        amount = as_int(row.get("amount_cents"), 0) or 0
        adjustment_totals[voyage_id] = adjustment_totals.get(voyage_id, 0) + amount
    adjustments_by_call = {}
    for voyage_id, voyage_calls in calls_by_voyage.items():
        weights = [
            (call["call_id"], tonnage[call["call_id"]]) for call in voyage_calls
        ]
        adjustments_by_call.update(
            allocate_total(adjustment_totals.get(voyage_id, 0), weights)
        )
    for settlement in settlements:
        adjustment = adjustments_by_call.get(settlement["call_id"], 0)
        settlement["adjustment_cents"] = adjustment
        settlement["net_due_cents"] = (
            settlement["demurrage_cents"]
            - settlement["despatch_cents"]
            + adjustment
        )

    # ---- rollups -------------------------------------------------------
    voyages = []
    for voyage_id in sorted(calls_by_voyage):
        voyage_calls = calls_by_voyage[voyage_id]
        call_ids = [call["call_id"] for call in voyage_calls]
        rows = [settlements_by_id[call_id] for call_id in call_ids]
        voyages.append(
            {
                "voyage_id": voyage_id,
                "call_ids": call_ids,
                "call_count": len(call_ids),
                "cargo_tonnes": number_out(
                    sum((tonnage[call_id] for call_id in call_ids), Fraction(0))
                ),
                "counted_seconds": sum(row["counted_seconds"] for row in rows),
                "allowed_seconds": sum(row["allowed_seconds"] for row in rows),
                "raw_delta_seconds": sum(
                    row["raw_delta_seconds"] for row in rows
                ),
                "settled_seconds": sum(row["settled_seconds"] for row in rows),
                "demurrage_cents": sum(row["demurrage_cents"] for row in rows),
                "despatch_cents": sum(row["despatch_cents"] for row in rows),
                "adjustment_cents": sum(row["adjustment_cents"] for row in rows),
                "net_due_cents": sum(row["net_due_cents"] for row in rows),
                "closing_bank_seconds": rows[-1]["bank_after_seconds"],
            }
        )

    by_charterer = {}
    for settlement in settlements:
        by_charterer.setdefault(settlement["charterer_id"], []).append(settlement)
    charterers = []
    for charterer_id in sorted(by_charterer):
        rows = by_charterer[charterer_id]
        charterers.append(
            {
                "charterer_id": charterer_id,
                "call_ids": sorted(row["call_id"] for row in rows),
                "voyage_ids": sorted({row["voyage_id"] for row in rows}),
                "demurrage_cents": sum(row["demurrage_cents"] for row in rows),
                "despatch_cents": sum(row["despatch_cents"] for row in rows),
                "adjustment_cents": sum(row["adjustment_cents"] for row in rows),
                "net_due_cents": sum(row["net_due_cents"] for row in rows),
            }
        )

    # ---- quality issues and exceptions ---------------------------------
    unique_issues = []
    seen = set()
    for issue in issues:
        key = canonical_json(issue)
        if key in seen:
            continue
        seen.add(key)
        unique_issues.append(issue)
    unique_issues.sort(key=issue_sort_key)

    exceptions = list(unique_issues)
    if threshold is not None:
        for settlement in settlements:
            if abs(settlement["net_due_cents"]) >= threshold:
                exceptions.append(
                    {
                        "code": "MATERIAL_SETTLEMENT",
                        "record_id": settlement["call_id"],
                        "net_due_cents": settlement["net_due_cents"],
                    }
                )
    exceptions.sort(key=issue_sort_key)

    # ---- audit chain ----------------------------------------------------
    entries = []
    previous = GENESIS_HASH
    for settlement in settlements:
        entry_hash = hashlib.sha256(
            (previous + canonical_json(settlement)).encode("utf-8")
        ).hexdigest()
        entries.append(
            {
                "call_id": settlement["call_id"],
                "previous_hash": previous,
                "entry_hash": entry_hash,
            }
        )
        previous = entry_hash

    return {
        "manifest": {
            "engine_version": as_text(policy.get("engine_version"))
            or ENGINE_FALLBACK,
            "input_files": inputs["files"],
            "valid_call_count": len(valid_calls),
            "effective_event_count": len(effective_events),
            "interval_count": len(intervals),
        },
        "data_quality": {
            "input_file_count": len(inputs["files"]),
            "issue_count": len(unique_issues),
            "issues": unique_issues,
            "record_counts": inputs["record_counts"],
        },
        "event_ledger": {
            "effective_events": [
                {field: event[field] for field in EVENT_FIELDS}
                for event in effective_events
            ],
            "revision_decisions": decisions,
        },
        "interval_ledger": {"intervals": intervals},
        "call_settlements": {"calls": settlements},
        "voyage_rollups": {"voyages": voyages},
        "charterer_statements": {"charterers": charterers},
        "exception_register": {"exceptions": exceptions},
        "audit_trace": {"entries": entries, "final_hash": previous},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Charter-party laytime settlement engine (MLSE-1.0)."
    )
    parser.add_argument("data_dir", help="directory holding the settlement extract")
    parser.add_argument("out_dir", help="directory to write the nine reports into")
    args = parser.parse_args(argv)

    reports = build_reports(args.data_dir)
    os.makedirs(args.out_dir, exist_ok=True)
    for name in REPORT_NAMES:
        target = os.path.join(args.out_dir, name + ".json")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(dump_json(reports[name]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
