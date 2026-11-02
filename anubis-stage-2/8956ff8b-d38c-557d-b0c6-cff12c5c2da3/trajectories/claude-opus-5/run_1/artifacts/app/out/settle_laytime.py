#!/usr/bin/env python3
"""8956ff8b-d38c-557d-b0c6-cff12c5c2da3 (MLSE-1.0).

Usage: python3 settle_laytime.py DATA_DIR OUT_DIR
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, getcontext
from fractions import Fraction

getcontext().prec = 80

DAY = 86400
BPS = 10000

INPUT_FILES = [
    "adjustments.jsonl",
    "cargo_operations.jsonl",
    "contracts.json",
    "event_revisions.jsonl",
    "holidays.json",
    "policy.json",
    "port_calls.jsonl",
    "rate_periods.jsonl",
    "stoppages.jsonl",
]

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------- utilities


def parse_ts(text):
    """Parse an ISO-8601 UTC timestamp into integer epoch seconds."""
    if not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None
    if raw.endswith("Z") or raw.endswith("z"):
        raw = raw[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    delta = moment - EPOCH
    total = delta.days * DAY + delta.seconds
    if delta.microseconds >= 500000:
        total += 1
    return total


def fmt_ts(seconds):
    return (EPOCH + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_date(seconds):
    return (EPOCH + timedelta(seconds=seconds)).strftime("%Y-%m-%d")


def midnight_floor(seconds):
    return (seconds // DAY) * DAY


def half_up(numerator, denominator):
    """ROUND_HALF_UP integer result of numerator/denominator."""
    value = Decimal(numerator) / Decimal(denominator)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def to_decimal(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except Exception:
            return None
    return None


def num_out(value):
    """Serialise a Decimal quantity as int when integral, else float."""
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def as_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != int(value):
            return None
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except Exception:
            return None
    return None


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path):
    """Return (records, raw_line_count)."""
    records = []
    raw = 0
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw += 1
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
    return records, raw


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------------- engine


class Engine(object):
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.issues = []
        self.record_counts = {}
        self.file_rows = []

    def add_issue(self, code, record_id, detail):
        self.issues.append({"code": code, "detail": detail, "record_id": record_id})

    # -- loading -----------------------------------------------------------

    def load(self):
        present = set()
        for name in INPUT_FILES:
            path = os.path.join(self.data_dir, name)
            if not os.path.exists(path):
                continue
            present.add(name)
            with open(path, "rb") as handle:
                blob = handle.read()
            self.file_rows.append(
                {
                    "bytes": len(blob),
                    "name": name,
                    "sha256": hashlib.sha256(blob).hexdigest(),
                }
            )

        def jsonl(name):
            path = os.path.join(self.data_dir, name)
            if name not in present:
                return []
            records, raw = read_jsonl(path)
            self.record_counts[name] = raw
            return records

        def plain(name, default):
            if name not in present:
                return default
            try:
                return read_json(os.path.join(self.data_dir, name))
            except ValueError:
                return default

        self.policy = plain("policy.json", {})
        if not isinstance(self.policy, dict):
            self.policy = {}
        if "policy.json" in present:
            self.record_counts["policy.json"] = 1

        contracts_raw = plain("contracts.json", [])
        if not isinstance(contracts_raw, list):
            contracts_raw = []
        if "contracts.json" in present:
            self.record_counts["contracts.json"] = len(contracts_raw)
        self.contracts = {}
        for row in contracts_raw:
            if isinstance(row, dict) and "contract_id" in row:
                self.contracts[str(row["contract_id"])] = row

        holidays_raw = plain("holidays.json", {})
        dates = []
        if isinstance(holidays_raw, dict):
            dates = holidays_raw.get("utc_dates") or []
        elif isinstance(holidays_raw, list):
            dates = holidays_raw
        self.holidays = set(str(d) for d in dates)
        if "holidays.json" in present:
            self.record_counts["holidays.json"] = len(dates)

        self.port_calls_raw = jsonl("port_calls.jsonl")
        self.revisions_raw = jsonl("event_revisions.jsonl")
        self.stoppages_raw = jsonl("stoppages.jsonl")
        self.operations_raw = jsonl("cargo_operations.jsonl")
        self.rate_periods_raw = jsonl("rate_periods.jsonl")
        self.adjustments_raw = jsonl("adjustments.jsonl")

        self.engine_version = str(self.policy.get("engine_version", "MLSE-1.0"))
        precedence = self.policy.get("precedence") or []
        self.precedence = {str(c): i for i, c in enumerate(precedence)}
        factors = self.policy.get("count_factors_bps") or {}
        self.factors = {}
        for key, value in factors.items():
            parsed = as_int(value)
            self.factors[str(key)] = 0 if parsed is None else parsed
        self.threshold = as_int(self.policy.get("exception_net_due_cents"))

    # -- revisions ---------------------------------------------------------

    def resolve_revisions(self):
        groups = {}
        for row in self.revisions_raw:
            event_id = row.get("event_id")
            if event_id is None:
                continue
            revision = as_int(row.get("revision"))
            recorded = parse_ts(row.get("recorded_at"))
            if revision is None or recorded is None:
                continue
            groups.setdefault(str(event_id), []).append(
                {
                    "record_id": str(row.get("record_id", "")),
                    "event_id": str(event_id),
                    "call_id": str(row.get("call_id", "")),
                    "revision": revision,
                    "recorded_at": recorded,
                    "status": str(row.get("status", "")),
                    "event_type": str(row.get("event_type", "")),
                    "event_time": parse_ts(row.get("event_time")),
                }
            )

        decisions = []
        effective = []
        for event_id in sorted(groups):
            rows = groups[event_id]
            winner = max(
                rows,
                key=lambda r: (r["revision"], r["recorded_at"], r["record_id"]),
            )
            peers = [
                r
                for r in rows
                if r["revision"] == winner["revision"]
                and r["recorded_at"] == winner["recorded_at"]
            ]
            conflict = False
            if len(peers) > 1:
                signature = set(
                    (r["status"], r["call_id"], r["event_type"], r["event_time"])
                    for r in peers
                )
                if len(signature) > 1:
                    conflict = True
                    self.add_issue(
                        "REVISION_TIE_CONFLICT",
                        event_id,
                        "winning revisions disagree for event " + event_id,
                    )
            discarded = sorted(
                r["record_id"] for r in rows if r["record_id"] != winner["record_id"]
            )
            decisions.append(
                {
                    "call_id": winner["call_id"],
                    "discarded_record_ids": discarded,
                    "event_id": event_id,
                    "event_type": winner["event_type"],
                    "recorded_at": fmt_ts(winner["recorded_at"]),
                    "revision": winner["revision"],
                    "tie_conflict": conflict,
                    "winning_record_id": winner["record_id"],
                    "winning_status": winner["status"],
                }
            )
            if winner["status"] == "cancelled" or winner["event_time"] is None:
                continue
            effective.append(winner)

        effective.sort(
            key=lambda r: (
                r["call_id"],
                r["event_time"],
                r["event_type"],
                r["event_id"],
            )
        )
        self.revision_decisions = decisions
        self.effective_events = effective

    # -- auxiliary records -------------------------------------------------

    def load_windows(self):
        self.stoppages = {}
        for row in self.stoppages_raw:
            sid = str(row.get("stoppage_id", ""))
            start = parse_ts(row.get("start"))
            end = parse_ts(row.get("end"))
            if start is None or end is None or start >= end:
                self.add_issue(
                    "INVALID_STOPPAGE", sid, "stoppage start is not before end"
                )
                continue
            self.stoppages.setdefault(str(row.get("call_id", "")), []).append(
                {
                    "stoppage_id": sid,
                    "start": start,
                    "end": end,
                    "code": str(row.get("code", "")),
                }
            )

        self.operations = {}
        for row in self.operations_raw:
            oid = str(row.get("operation_id", ""))
            start = parse_ts(row.get("start"))
            end = parse_ts(row.get("end"))
            quantity = to_decimal(row.get("quantity_tonnes"))
            if start is None or end is None or start >= end:
                self.add_issue(
                    "INVALID_CARGO_OPERATION",
                    oid,
                    "cargo operation start is not before end",
                )
                continue
            if quantity is None or quantity < 0:
                self.add_issue(
                    "INVALID_CARGO_OPERATION",
                    oid,
                    "cargo operation quantity is negative",
                )
                continue
            self.operations.setdefault(str(row.get("call_id", "")), []).append(
                {
                    "operation_id": oid,
                    "start": start,
                    "end": end,
                    "quantity": quantity,
                }
            )

        periods = []
        for row in self.rate_periods_raw:
            start = parse_ts(row.get("start"))
            end = parse_ts(row.get("end"))
            multiplier = as_int(row.get("multiplier_bps"))
            if start is None or end is None or multiplier is None:
                continue
            periods.append(
                {
                    "period_id": str(row.get("period_id", "")),
                    "start": start,
                    "end": end,
                    "multiplier_bps": multiplier,
                }
            )
        periods.sort(key=lambda p: (p["start"], p["period_id"]))
        self.rate_periods = periods

    def pick_rate(self, moment):
        chosen = None
        for period in self.rate_periods:
            if period["start"] <= moment < period["end"]:
                chosen = period
        if chosen is None:
            return "default", BPS
        return chosen["period_id"], chosen["multiplier_bps"]

    # -- calls -------------------------------------------------------------

    def build_calls(self):
        boundaries = {}
        for event in self.effective_events:
            per_call = boundaries.setdefault(event["call_id"], {})
            key = event["event_type"]
            candidate = (event["event_time"], event["event_id"])
            if key not in per_call or candidate < per_call[key]:
                per_call[key] = candidate

        calls = []
        for row in self.port_calls_raw:
            sequence = as_int(row.get("sequence"))
            calls.append(
                {
                    "call_id": str(row.get("call_id", "")),
                    "voyage_id": str(row.get("voyage_id", "")),
                    "sequence": 0 if sequence is None else sequence,
                    "charterer_id": str(row.get("charterer_id", "")),
                    "contract_id": str(row.get("contract_id", "")),
                }
            )
        calls.sort(key=lambda c: (c["voyage_id"], c["sequence"], c["call_id"]))

        valid = []
        for call in calls:
            per_call = boundaries.get(call["call_id"], {})
            start = per_call.get("NOR_ACCEPTED")
            end = per_call.get("CARGO_END")
            if start is None or end is None:
                self.add_issue(
                    "MISSING_REQUIRED_EVENT",
                    call["call_id"],
                    "call lacks effective NOR_ACCEPTED or CARGO_END",
                )
                continue
            if start[0] >= end[0]:
                self.add_issue(
                    "NON_POSITIVE_CALL_WINDOW",
                    call["call_id"],
                    "NOR_ACCEPTED is not before CARGO_END",
                )
                continue
            contract = self.contracts.get(call["contract_id"])
            if contract is None:
                self.add_issue(
                    "UNKNOWN_CONTRACT",
                    call["call_id"],
                    "contract " + call["contract_id"] + " is not defined",
                )
                continue
            call["window_start"] = start[0]
            call["window_end"] = end[0]
            call["contract"] = contract
            valid.append(call)

        self.all_calls = calls
        self.valid_calls = valid

    # -- intervals ---------------------------------------------------------

    def build_intervals(self, call):
        start = call["window_start"]
        end = call["window_end"]
        stoppages = [
            s
            for s in self.stoppages.get(call["call_id"], [])
            if s["start"] < end and s["end"] > start
        ]
        operations = [
            o
            for o in self.operations.get(call["call_id"], [])
            if o["start"] < end and o["end"] > start
        ]

        cuts = set((start, end))
        for item in list(stoppages) + list(operations):
            for point in (item["start"], item["end"]):
                if start < point < end:
                    cuts.add(point)
        point = midnight_floor(start)
        if point <= start:
            point += DAY
        while point < end:
            cuts.add(point)
            point += DAY

        edges = sorted(cuts)
        rows = []
        for index in range(len(edges) - 1):
            lo = edges[index]
            hi = edges[index + 1]
            code, source = self.classify(lo, hi, stoppages, operations)
            factor = self.factors.get(code, 0)
            duration = hi - lo
            rows.append(
                {
                    "call_id": call["call_id"],
                    "code": code,
                    "duration_seconds": duration,
                    "end": fmt_ts(hi),
                    "factor_bps": factor,
                    "source": source,
                    "start": fmt_ts(lo),
                    "weighted_second_bps": duration * factor,
                }
            )
        return rows

    def classify(self, lo, hi, stoppages, operations):
        overlapping = [s for s in stoppages if s["start"] < hi and s["end"] > lo]
        if overlapping:
            unknown = len(self.precedence)
            best = min(
                overlapping,
                key=lambda s: (
                    self.precedence.get(s["code"], unknown),
                    s["stoppage_id"],
                ),
            )
            return best["code"], best["stoppage_id"]
        day = utc_date(lo)
        if day in self.holidays:
            return "HOLIDAY", day
        ops = [o for o in operations if o["start"] < hi and o["end"] > lo]
        if ops:
            return "CARGO_WORK", min(o["operation_id"] for o in ops)
        return "IDLE", "idle"

    # -- settlement --------------------------------------------------------

    def settle(self):
        self.intervals = []
        metrics_by_call = {}
        for call in self.valid_calls:
            rows = self.build_intervals(call)
            self.intervals.extend(rows)
            total_bps = sum(r["weighted_second_bps"] for r in rows)
            counted = half_up(total_bps, BPS)
            tonnes = Decimal(0)
            for op in self.operations.get(call["call_id"], []):
                tonnes += op["quantity"]
            contract = call["contract"]
            base = as_int(contract.get("base_allowance_seconds")) or 0
            rate_tph = to_decimal(contract.get("cargo_rate_tph"))
            if rate_tph is None or rate_tph == 0:
                extra = 0
            else:
                extra = half_up(tonnes * Decimal(3600), rate_tph)
            allowed = base + extra
            metrics_by_call[call["call_id"]] = {
                "counted_seconds": counted,
                "cargo_tonnes": tonnes,
                "allowed_seconds": allowed,
                "raw_delta_seconds": counted - allowed,
            }

        by_voyage = {}
        for call in self.valid_calls:
            by_voyage.setdefault(call["voyage_id"], []).append(call)

        settlements = []
        self.closing_bank = {}
        for voyage_id in sorted(by_voyage):
            members = by_voyage[voyage_id]
            bank = 0
            for index, call in enumerate(members):
                metrics = metrics_by_call[call["call_id"]]
                contract = call["contract"]
                cap = as_int(contract.get("bank_cap_seconds")) or 0
                combined = bank + metrics["raw_delta_seconds"]
                if index == len(members) - 1:
                    bank_after = 0
                else:
                    bank_after = max(-cap, min(cap, combined))
                settled = combined - bank_after
                period_id, multiplier = self.pick_rate(call["window_end"] - 1)
                demurrage = 0
                despatch = 0
                if settled > 0:
                    demurrage = self.tier_cents(contract, settled, multiplier)
                elif settled < 0:
                    rate = as_int(contract.get("despatch_usd_cents_per_day")) or 0
                    despatch = half_up(
                        Decimal(-settled) * Decimal(rate) * Decimal(multiplier),
                        Decimal(DAY) * Decimal(BPS),
                    )
                settlements.append(
                    {
                        "adjustment_cents": 0,
                        "allowed_seconds": metrics["allowed_seconds"],
                        "bank_after_seconds": bank_after,
                        "bank_before_seconds": bank,
                        "call_id": call["call_id"],
                        "cargo_tonnes": num_out(metrics["cargo_tonnes"]),
                        "charterer_id": call["charterer_id"],
                        "combined_seconds": combined,
                        "contract_id": call["contract_id"],
                        "counted_seconds": metrics["counted_seconds"],
                        "demurrage_cents": demurrage,
                        "despatch_cents": despatch,
                        "multiplier_bps": multiplier,
                        "net_before_adjustment_cents": demurrage - despatch,
                        "net_due_cents": demurrage - despatch,
                        "rate_period_id": period_id,
                        "raw_delta_seconds": metrics["raw_delta_seconds"],
                        "sequence": call["sequence"],
                        "settled_seconds": settled,
                        "voyage_id": call["voyage_id"],
                        "window_end": fmt_ts(call["window_end"]),
                        "window_seconds": call["window_end"] - call["window_start"],
                        "window_start": fmt_ts(call["window_start"]),
                    }
                )
                bank = bank_after
            self.closing_bank[voyage_id] = bank

        settlements.sort(
            key=lambda r: (r["voyage_id"], r["sequence"], r["call_id"])
        )
        self.settlements = settlements
        self.apply_adjustments()

    def tier_cents(self, contract, seconds, multiplier):
        tiers = contract.get("demurrage_tiers") or []
        total = 0
        consumed = 0
        remaining = seconds
        for tier in tiers:
            if remaining <= 0:
                break
            if not isinstance(tier, dict):
                continue
            limit = as_int(tier.get("up_to_seconds"))
            if tier.get("up_to_seconds") is None or limit is None:
                width = remaining
            else:
                width = limit - consumed
                if width <= 0:
                    continue
                width = min(width, remaining)
            rate = as_int(tier.get("usd_cents_per_day")) or 0
            total += half_up(
                Decimal(width) * Decimal(rate) * Decimal(multiplier),
                Decimal(DAY) * Decimal(BPS),
            )
            consumed += width
            remaining -= width
        return total

    def apply_adjustments(self):
        totals = {}
        for row in self.adjustments_raw:
            voyage_id = str(row.get("voyage_id", ""))
            amount = as_int(row.get("amount_cents"))
            if amount is None:
                continue
            totals[voyage_id] = totals.get(voyage_id, 0) + amount

        by_voyage = {}
        for row in self.settlements:
            by_voyage.setdefault(row["voyage_id"], []).append(row)

        for voyage_id in sorted(by_voyage):
            members = by_voyage[voyage_id]
            total = totals.get(voyage_id, 0)
            if total == 0:
                continue
            weights = [
                to_decimal(row["cargo_tonnes"]) or Decimal(0) for row in members
            ]
            denominator = sum(weights, Decimal(0))
            if denominator <= 0:
                continue
            magnitude = abs(total)
            sign = 1 if total > 0 else -1
            floors = []
            remainders = []
            for row, weight in zip(members, weights):
                exact = (
                    Fraction(magnitude) * Fraction(weight) / Fraction(denominator)
                )
                base = exact.numerator // exact.denominator
                floors.append(base)
                remainders.append((exact - base, row["call_id"]))
            leftover = magnitude - sum(floors)
            order = sorted(
                range(len(members)),
                key=lambda i: (-remainders[i][0], remainders[i][1]),
            )
            allocation = list(floors)
            for position in range(leftover):
                allocation[order[position]] += 1
            for row, amount in zip(members, allocation):
                row["adjustment_cents"] = sign * amount
                row["net_due_cents"] = (
                    row["demurrage_cents"]
                    - row["despatch_cents"]
                    + row["adjustment_cents"]
                )

    # -- outputs -----------------------------------------------------------

    def build_reports(self):
        issues = sorted(
            self.issues, key=lambda i: (i["code"], i["record_id"], i["detail"])
        )

        manifest = {
            "effective_event_count": len(self.effective_events),
            "engine_version": self.engine_version,
            "input_files": sorted(self.file_rows, key=lambda r: r["name"]),
            "interval_count": len(self.intervals),
            "valid_call_count": len(self.valid_calls),
        }

        data_quality = {
            "input_file_count": len(self.file_rows),
            "issue_count": len(issues),
            "issues": issues,
            "record_counts": dict(self.record_counts),
        }

        event_ledger = {
            "effective_events": [
                {
                    "call_id": e["call_id"],
                    "event_id": e["event_id"],
                    "event_time": fmt_ts(e["event_time"]),
                    "event_type": e["event_type"],
                    "record_id": e["record_id"],
                    "recorded_at": fmt_ts(e["recorded_at"]),
                    "revision": e["revision"],
                    "status": e["status"],
                }
                for e in self.effective_events
            ],
            "revision_decisions": self.revision_decisions,
        }

        grouped = {}
        for row in self.settlements:
            grouped.setdefault(row["voyage_id"], []).append(row)
        voyages = []
        for voyage_id in sorted(grouped):
            members = grouped[voyage_id]
            tonnes = sum(
                (to_decimal(r["cargo_tonnes"]) or Decimal(0) for r in members),
                Decimal(0),
            )
            voyages.append(
                {
                    "adjustment_cents": sum(r["adjustment_cents"] for r in members),
                    "allowed_seconds": sum(r["allowed_seconds"] for r in members),
                    "call_count": len(members),
                    "call_ids": [r["call_id"] for r in members],
                    "cargo_tonnes": num_out(tonnes),
                    "closing_bank_seconds": self.closing_bank.get(voyage_id, 0),
                    "counted_seconds": sum(r["counted_seconds"] for r in members),
                    "demurrage_cents": sum(r["demurrage_cents"] for r in members),
                    "despatch_cents": sum(r["despatch_cents"] for r in members),
                    "net_before_adjustment_cents": sum(
                        r["net_before_adjustment_cents"] for r in members
                    ),
                    "net_due_cents": sum(r["net_due_cents"] for r in members),
                    "raw_delta_seconds": sum(r["raw_delta_seconds"] for r in members),
                    "settled_seconds": sum(r["settled_seconds"] for r in members),
                    "voyage_id": voyage_id,
                }
            )

        by_charterer = {}
        for row in self.settlements:
            by_charterer.setdefault(row["charterer_id"], []).append(row)
        charterers = []
        for charterer_id in sorted(by_charterer):
            members = by_charterer[charterer_id]
            charterers.append(
                {
                    "adjustment_cents": sum(r["adjustment_cents"] for r in members),
                    "call_ids": sorted(r["call_id"] for r in members),
                    "charterer_id": charterer_id,
                    "demurrage_cents": sum(r["demurrage_cents"] for r in members),
                    "despatch_cents": sum(r["despatch_cents"] for r in members),
                    "net_before_adjustment_cents": sum(
                        r["net_before_adjustment_cents"] for r in members
                    ),
                    "net_due_cents": sum(r["net_due_cents"] for r in members),
                    "voyage_ids": sorted(set(r["voyage_id"] for r in members)),
                }
            )

        exceptions = [dict(i) for i in issues]
        if self.threshold is not None:
            for row in self.settlements:
                if abs(row["net_due_cents"]) >= self.threshold:
                    exceptions.append(
                        {
                            "code": "MATERIAL_SETTLEMENT",
                            "detail": "absolute net due reaches policy threshold",
                            "net_due_cents": row["net_due_cents"],
                            "record_id": row["call_id"],
                        }
                    )
        exceptions.sort(key=lambda e: (e["code"], e["record_id"], e["detail"]))

        previous = "0" * 64
        entries = []
        for row in self.settlements:
            digest = hashlib.sha256(
                (previous + canonical(row)).encode("utf-8")
            ).hexdigest()
            entries.append(
                {
                    "call_id": row["call_id"],
                    "entry_hash": digest,
                    "previous_hash": previous,
                }
            )
            previous = digest

        return {
            "manifest.json": manifest,
            "data_quality.json": data_quality,
            "event_ledger.json": event_ledger,
            "interval_ledger.json": {"intervals": self.intervals},
            "call_settlements.json": {"calls": self.settlements},
            "voyage_rollups.json": {"voyages": voyages},
            "charterer_statements.json": {"charterers": charterers},
            "exception_register.json": {"exceptions": exceptions},
            "audit_trace.json": {"entries": entries, "final_hash": previous},
        }

    def run(self):
        self.load()
        self.resolve_revisions()
        self.load_windows()
        self.build_calls()
        self.settle()
        return self.build_reports()


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: settle_laytime.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    reports = Engine(data_dir).run()
    for name, payload in reports.items():
        write_json(os.path.join(out_dir, name), payload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
