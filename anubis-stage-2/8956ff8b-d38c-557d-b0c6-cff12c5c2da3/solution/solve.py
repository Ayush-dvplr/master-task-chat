#!/usr/bin/env python3
"""Reference laytime settlement engine. Usage: settle_laytime.py DATA_DIR OUT_DIR."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from typing import Any

DAY = 86400
TEN_K = Decimal(10000)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stamp(text: str) -> int:
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def iso(value: int) -> str:
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def half(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def clamp(value: int, cap: int) -> int:
    return max(-cap, min(cap, value))


def allocate_signed(total: int, weighted: list[tuple[str, int]]) -> dict[str, int]:
    """Largest remainder on absolute cents; remainder ties use call_id."""
    result = {key: 0 for key, _ in weighted}
    denominator = sum(weight for _, weight in weighted)
    if total == 0 or denominator == 0:
        return result
    sign = 1 if total > 0 else -1
    magnitude = abs(total)
    ranked: list[tuple[Decimal, str]] = []
    used = 0
    for key, weight in weighted:
        exact = Decimal(magnitude * weight) / Decimal(denominator)
        base = int(exact.to_integral_value(rounding=ROUND_FLOOR))
        result[key] = sign * base
        used += base
        ranked.append((exact - base, key))
    for _, key in sorted(ranked, key=lambda item: (-item[0], item[1]))[: magnitude - used]:
        result[key] += sign
    return result


def tier_amount(seconds: int, tiers: list[dict[str, Any]], multiplier_bps: int) -> int:
    remaining = seconds
    previous = 0
    total = 0
    for tier in tiers:
        ceiling = tier["up_to_seconds"]
        width = remaining if ceiling is None else min(remaining, int(ceiling) - previous)
        if width > 0:
            exact = Decimal(width * int(tier["usd_cents_per_day"]) * multiplier_bps) / Decimal(DAY * 10000)
            total += half(exact)
            remaining -= width
        if ceiling is not None:
            previous = int(ceiling)
        if remaining <= 0:
            break
    return total


def build(data: Path) -> dict[str, Any]:
    policy = read_json(data / "policy.json")
    contracts = {row["contract_id"]: row for row in read_json(data / "contracts.json")}
    calls = read_jsonl(data / "port_calls.jsonl")
    revisions = read_jsonl(data / "event_revisions.jsonl")
    stoppages = read_jsonl(data / "stoppages.jsonl")
    cargo_ops = read_jsonl(data / "cargo_operations.jsonl")
    rate_periods = read_jsonl(data / "rate_periods.jsonl")
    holidays = set(read_json(data / "holidays.json")["utc_dates"])
    adjustments = read_jsonl(data / "adjustments.jsonl")
    issues: list[dict[str, Any]] = []

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in revisions:
        grouped[row["event_id"]].append(row)
    effective: list[dict[str, Any]] = []
    revision_audit: list[dict[str, Any]] = []
    for event_id in sorted(grouped):
        records = grouped[event_id]
        records.sort(key=lambda r: (int(r["revision"]), stamp(r["recorded_at"]), r["record_id"]))
        winner = records[-1]
        peers = [r for r in records if int(r["revision"]) == int(winner["revision"]) and r["recorded_at"] == winner["recorded_at"]]
        payloads = {(r["status"], r.get("event_type"), r.get("event_time"), r.get("call_id")) for r in peers}
        if len(payloads) > 1:
            issues.append({"code": "REVISION_TIE_CONFLICT", "record_id": event_id})
        revision_audit.append({"event_id": event_id, "winner_record_id": winner["record_id"], "discarded_record_ids": sorted(r["record_id"] for r in records if r is not winner)})
        if winner["status"] == "active":
            effective.append({key: winner[key] for key in ("event_id", "call_id", "event_type", "event_time", "revision", "record_id")})
    effective.sort(key=lambda r: (r["call_id"], stamp(r["event_time"]), r["event_type"], r["event_id"]))
    events_by_call: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in effective:
        kind = row["event_type"]
        current = events_by_call[row["call_id"]].get(kind)
        if current is None or (stamp(row["event_time"]), row["event_id"]) < (stamp(current["event_time"]), current["event_id"]):
            events_by_call[row["call_id"]][kind] = row

    stop_by_call: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in stoppages:
        try:
            if stamp(row["start"]) >= stamp(row["end"]):
                raise ValueError
            stop_by_call[row["call_id"]].append(row)
        except (KeyError, ValueError):
            issues.append({"code": "INVALID_STOPPAGE", "record_id": row.get("stoppage_id", "?")})
    cargo_by_call: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cargo_ops:
        try:
            if stamp(row["start"]) >= stamp(row["end"]) or int(row["quantity_tonnes"]) < 0:
                raise ValueError
            cargo_by_call[row["call_id"]].append(row)
        except (KeyError, ValueError):
            issues.append({"code": "INVALID_CARGO_OPERATION", "record_id": row.get("operation_id", "?")})

    valid_calls: list[dict[str, Any]] = []
    for call in calls:
        event_map = events_by_call.get(call["call_id"], {})
        if "NOR_ACCEPTED" not in event_map or "CARGO_END" not in event_map:
            issues.append({"code": "MISSING_REQUIRED_EVENT", "record_id": call["call_id"]})
            continue
        start, end = stamp(event_map["NOR_ACCEPTED"]["event_time"]), stamp(event_map["CARGO_END"]["event_time"])
        if start >= end:
            issues.append({"code": "NON_POSITIVE_CALL_WINDOW", "record_id": call["call_id"]})
            continue
        item = dict(call)
        item["window_start"] = start
        item["window_end"] = end
        item["cargo_tonnes"] = sum(int(op["quantity_tonnes"]) for op in cargo_by_call.get(call["call_id"], []))
        valid_calls.append(item)
    valid_calls.sort(key=lambda c: (c["voyage_id"], int(c["sequence"]), c["call_id"]))

    precedence = {code: index for index, code in enumerate(policy["precedence"])}
    factors = {key: int(value) for key, value in policy["count_factors_bps"].items()}
    interval_rows: list[dict[str, Any]] = []
    call_metrics: dict[str, dict[str, Any]] = {}
    for call in valid_calls:
        start, end = call["window_start"], call["window_end"]
        boundaries = {start, end}
        local_stops = [r for r in stop_by_call.get(call["call_id"], []) if stamp(r["start"]) < end and stamp(r["end"]) > start]
        local_cargo = [r for r in cargo_by_call.get(call["call_id"], []) if stamp(r["start"]) < end and stamp(r["end"]) > start]
        for row in local_stops + local_cargo:
            boundaries.update((max(start, stamp(row["start"])), min(end, stamp(row["end"]))))
        midnight = ((start // DAY) + 1) * DAY
        while midnight < end:
            boundaries.add(midnight)
            midnight += DAY
        ordered = sorted(boundaries)
        numerator = 0
        for left, right in zip(ordered, ordered[1:]):
            active = [r for r in local_stops if stamp(r["start"]) < right and stamp(r["end"]) > left]
            if active:
                chosen = min(active, key=lambda r: (precedence[r["code"]], r["stoppage_id"]))
                code, source = chosen["code"], chosen["stoppage_id"]
            elif datetime.fromtimestamp(left, timezone.utc).strftime("%Y-%m-%d") in holidays:
                code, source = "HOLIDAY", datetime.fromtimestamp(left, timezone.utc).strftime("%Y-%m-%d")
            else:
                working = [r for r in local_cargo if stamp(r["start"]) < right and stamp(r["end"]) > left]
                if working:
                    code, source = "CARGO_WORK", min(r["operation_id"] for r in working)
                else:
                    code, source = "IDLE", "idle"
            duration = right - left
            weighted = duration * factors[code]
            numerator += weighted
            interval_rows.append({"call_id": call["call_id"], "start": iso(left), "end": iso(right), "duration_seconds": duration, "governing_code": code, "source_id": source, "factor_bps": factors[code], "weighted_second_bps": weighted})
        contract = contracts[call["contract_id"]]
        allowance = int(contract["base_allowance_seconds"]) + half(Decimal(call["cargo_tonnes"] * 3600) / Decimal(int(contract["cargo_rate_tph"])))
        call_metrics[call["call_id"]] = {"counted_seconds": half(Decimal(numerator) / TEN_K), "allowed_seconds": allowance, "weighted_second_bps": numerator}

    periods = sorted(rate_periods, key=lambda r: (stamp(r["start"]), r["period_id"]))
    def multiplier(at: int) -> tuple[str, int]:
        matches = [row for row in periods if stamp(row["start"]) <= at < stamp(row["end"])]
        if not matches:
            return "default", 10000
        row = matches[-1]
        return row["period_id"], int(row["multiplier_bps"])

    voyage_calls: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for call in valid_calls:
        voyage_calls[call["voyage_id"]].append(call)
    adjustment_by_voyage: dict[str, int] = defaultdict(int)
    for row in adjustments:
        adjustment_by_voyage[row["voyage_id"]] += int(row["amount_cents"])
    allocations: dict[str, int] = {}
    for voyage, items in voyage_calls.items():
        allocations.update(allocate_signed(adjustment_by_voyage[voyage], [(c["call_id"], c["cargo_tonnes"]) for c in items]))

    settlements: list[dict[str, Any]] = []
    for voyage in sorted(voyage_calls):
        items = voyage_calls[voyage]
        bank = 0
        for index, call in enumerate(items):
            contract = contracts[call["contract_id"]]
            metrics = call_metrics[call["call_id"]]
            raw_delta = metrics["counted_seconds"] - metrics["allowed_seconds"]
            combined = bank + raw_delta
            bank_after = 0 if index == len(items) - 1 else clamp(combined, int(contract["bank_cap_seconds"]))
            settled = combined - bank_after
            period_id, mult = multiplier(call["window_end"] - 1)
            demurrage = tier_amount(max(settled, 0), contract["demurrage_tiers"], mult)
            despatch = half(Decimal(max(-settled, 0) * int(contract["despatch_usd_cents_per_day"]) * mult) / Decimal(DAY * 10000))
            adjustment = allocations.get(call["call_id"], 0)
            settlements.append({"call_id": call["call_id"], "voyage_id": voyage, "sequence": int(call["sequence"]), "charterer_id": call["charterer_id"], "contract_id": call["contract_id"], "window_start": iso(call["window_start"]), "window_end": iso(call["window_end"]), "cargo_tonnes": call["cargo_tonnes"], "allowed_seconds": metrics["allowed_seconds"], "counted_seconds": metrics["counted_seconds"], "raw_delta_seconds": raw_delta, "bank_before_seconds": bank, "settled_seconds": settled, "bank_after_seconds": bank_after, "rate_period_id": period_id, "rate_multiplier_bps": mult, "demurrage_cents": demurrage, "despatch_cents": despatch, "adjustment_cents": adjustment, "net_due_cents": demurrage - despatch + adjustment})
            bank = bank_after

    voyage_rollups = []
    for voyage in sorted(voyage_calls):
        rows = [r for r in settlements if r["voyage_id"] == voyage]
        voyage_rollups.append({"voyage_id": voyage, "call_ids": [r["call_id"] for r in rows], "call_count": len(rows), "cargo_tonnes": sum(r["cargo_tonnes"] for r in rows), "allowed_seconds": sum(r["allowed_seconds"] for r in rows), "counted_seconds": sum(r["counted_seconds"] for r in rows), "demurrage_cents": sum(r["demurrage_cents"] for r in rows), "despatch_cents": sum(r["despatch_cents"] for r in rows), "adjustment_cents": sum(r["adjustment_cents"] for r in rows), "net_due_cents": sum(r["net_due_cents"] for r in rows), "closing_bank_seconds": rows[-1]["bank_after_seconds"]})
    charterers = []
    for charterer in sorted({r["charterer_id"] for r in settlements}):
        rows = [r for r in settlements if r["charterer_id"] == charterer]
        charterers.append({"charterer_id": charterer, "call_ids": sorted(r["call_id"] for r in rows), "voyage_ids": sorted({r["voyage_id"] for r in rows}), "demurrage_cents": sum(r["demurrage_cents"] for r in rows), "despatch_cents": sum(r["despatch_cents"] for r in rows), "adjustment_cents": sum(r["adjustment_cents"] for r in rows), "net_due_cents": sum(r["net_due_cents"] for r in rows)})
    exceptions = list(issues)
    threshold = int(policy["exception_net_due_cents"])
    for row in settlements:
        if abs(row["net_due_cents"]) >= threshold:
            exceptions.append({"code": "MATERIAL_SETTLEMENT", "record_id": row["call_id"], "net_due_cents": row["net_due_cents"]})
    exceptions.sort(key=lambda r: (r["code"], r["record_id"]))

    chain = "0" * 64
    audit_entries = []
    for row in settlements:
        digest = hashlib.sha256((chain + canonical(row)).encode()).hexdigest()
        audit_entries.append({"call_id": row["call_id"], "previous_hash": chain, "entry_hash": digest})
        chain = digest
    files = sorted(path for path in data.iterdir() if path.is_file())
    manifest = {"engine_version": policy["engine_version"], "input_files": [{"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in files], "valid_call_count": len(valid_calls), "effective_event_count": len(effective), "interval_count": len(interval_rows)}
    counts = {"port_calls": len(calls), "event_revisions": len(revisions), "stoppages": len(stoppages), "cargo_operations": len(cargo_ops), "rate_periods": len(rate_periods), "adjustments": len(adjustments)}
    return {
        "manifest.json": manifest,
        "data_quality.json": {"input_file_count": len(files), "record_counts": counts, "issue_count": len(issues), "issues": sorted(issues, key=lambda r: (r["code"], r["record_id"]))},
        "event_ledger.json": {"effective_events": effective, "revision_decisions": revision_audit},
        "interval_ledger.json": {"intervals": interval_rows},
        "call_settlements.json": {"calls": settlements},
        "voyage_rollups.json": {"voyages": voyage_rollups},
        "charterer_statements.json": {"charterers": charterers},
        "exception_register.json": {"exceptions": exceptions},
        "audit_trace.json": {"entries": audit_entries, "final_hash": chain},
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: settle_laytime.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data, out = Path(argv[1]), Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for name, payload in sorted(build(data).items()):
        (out / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
