"""Independent verifier for the 8956ff8b-d38c-557d-b0c6-cff12c5c2da3.

The verifier embeds the delivered input corpus so tests-only isolation does not
depend on owner files.  It also constructs a materially different fresh corpus
that exercises revision ties, precedence, midnight splitting, reversible banks,
demurrage tiers, despatch, and signed largest-remainder allocation.

Negative criteria hold only when the prohibited behaviour is detected.
"""
# pyright: reportMissingImports=false
from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import zlib
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable

from rewardkit import criteria, criterion

OUT = Path("/app/out")
SCRIPT = OUT / "settle_laytime.py"
REPORTS = (
    "manifest.json", "data_quality.json", "event_ledger.json",
    "interval_ledger.json", "call_settlements.json", "voyage_rollups.json",
    "charterer_statements.json", "exception_register.json", "audit_trace.json",
)
DAY = 86400
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

# Compressed copies of the shipped inputs. schema.md is recreated below because
# its prose is not needed by the independent model but must exist for manifests.
_PACKED = {
    "adjustments.jsonl": "eNqrVkpMySotLslNzSuJz0xRslJydPHSddQ1VNJRKsuvTExPhYiG+UfqOvoEeDgCxRNz80uBqpOBWoqVrAyNzU0NjGu5qnGYZES0SbpGpgYGBrhMcsLqJifXECwGWZiYmhrWcgEAFu1Ecg==",
    "cargo_operations.jsonl": "eNqd0rEKwjAQBuDdx8hs4e5PbWs30aVQ1CE4uEjRDoWSqo2DiO9uioMWkiBCprvAffkvD9Gd62tlmk4fmpPIxWYbMXHEYiqOVdu+i8tFWQ5lW+xNdTW2BEIS2YsERXFOZM/etmt9+m5KRdmneblV2jTmfjCd1nUv8hmInpOHx4CfDVIxeQ2xIgQMyPwGuHOAy5CGcpgrTgIGZvIjpBshHQjGKO8xgm1KcQARe4OA+0PAsQzYSaO3fhswbAqhZWSp3wC3AS5DoshvyBSHDGniMxTr3aIsVj8r7CD5r4IHxAtNTvpU",
    "contracts.json": "eNqlkUGLwjAQhe/9FSFnhUlpu8Xbun9g70WGMQkqW9OQpCyL+N9Nq4isRkUPyWXe94Z5r8kY28XHGJedCY5kwI3iM8a/vqeffHIcLclrpLbtfslIjV5HrfJRJaAGOIkkuVWHjoLGYNdxmBdw5s0PSrIXZC6qM6m0txTkGnuvUGoTPFrtUNFfFH7kABfKbe8creKKjXaDTzMO4hG8txi6qw2M3zIVoynsJ0m6Kuo0XZUPaNO3bQLOxXH1yC7iP9okO5g/7GAIKFWBqO9UIIriuQoqeLWC+k6I8EaIovwfYrbIDpYG0f8=",
    "event_revisions.jsonl": "eNq1lV9PgzAUxd/9GDy7pPcWYdsb69CZLJvBPiy+EAJ9IMHNbLjELH53i/hn0UtBqAlPB3qaH+fc9uTsVbrbZ3GeOVMnGgGDUcCcS0cd1bas1bBWtZgmRVFrIlguK1mLe3XMD/lu60zZ5YebyuKk1F8hQ2+k1zKUDKaM6edBrziUSfl80O+TtMyP6mu38uVJaXW1juJAiPBOhvPvd/mj+uHIPh1fL04UBvTEABMGt46BZgxBpiGGpOFK5nXGEEF0s47DVTODtnPNDBuSYTOEgZ/9uFaG+8XttU4hnoWRXDRy8LOSNnBATw4wcVCVSpNtqopCZf+DguSQIz0d2DES3/qQ+y1DjuR0ID0dXTEmEpnF6ZhIGLcwQE8GMDGgVQY05sDJOnG6TrxbDqCPRt9qnSpHz4whSAwxBIOf5T88isrOwIDk9Y30vYfdDlvU+0qwee/VjmjGECSGGILh/uXOaImitmMmBiSjQDoK7Mjg2T1ka8c2DOiJASYM1zoGN2MIMg0xJI2xBN9io7TdVTPDLJgTjXpXfzNouRsDMNuNqhzPGvUGhhmDAQ==",
    "holidays.json": "eNqrViotSY5PSSxJLVayilYyMjAy0zUw1DUwVtJBcCzgHCMgQuaYK8XWcgEAR00PMw==",
    "policy.json": "eNplkF9LwzAUxd/3KUKeq2TCEPKWrVdbzRaInUVELppdZS9paTMRxr67aXR/nG/J79yTc262I8Y4+Y+1J/ykrl83nkvG5/oBLsaXgmeD3nbkaEXeUdSe+Y2xM8C5uoOlBZ4xbuoFWMxBq6fhWoOqCrDDcQq2KnC5UI+q1Gqq0/isULYCe7C8pBDXbHzA91cXmq7Ht7aPWdsoROlvoGQi++GnuUe6j5dsIsQe/i8i2fXkIJ9XkmwsjubC6DJP9OrEouytwdrY+7PpMk+vJxTJLm1HX47aEH8XPQVcbQgd+dD/loyDu9E3YFhjGw==",
    "port_calls.jsonl": "eNqrVkpOzMmJz0xRslJydvTx0TU0MFTSUSrLr0xMT4UIh/lH6jr6BHg4AsWLUwtLU/OSU5WsDHWUkjMSi0pSi1KLoNo9gnT9/INCPIDqkvPzSooSk0ugMgG6jkq1XNWYdhkRZZcRVewyJsouYyrYZYQ1DJ1cQ4gJQlfH4BBsNjlht8mIGJuMKLfJydGFGJuMSbYJAHrGwqM=",
    "rate_periods.jsonl": "eNqrVipILcrMT4nPTFGyUgr39AtxDdI1VNJRKi5JLCoBChkZGJnpGhgCUYiBgRUYRQGlU/NSkCUtUSRzS3NKMgtyMlOL4pMKipWsDA2AoJarGptdRtjsssRpl5GugSl+uwyNTDHsCnB19MawB8MoZHuM0T2MYQ/QGqA9AMBwVVo=",
    "stoppages.jsonl": "eNqVk1FrgzAQx9/3MfI84XIW5/oWbYqOTCFLK9uLSJUxKGtZfSv77rtug+FMUoU83Rl+v5z/O7NTfzgem9eufmvZkj0FHHhQsVu2a/b7n1oqlLqUqXjqm4+eSggYBfQhoIF4CUDnhdrdeztsIvw1d4e2o24lhcmkZp83Zyu7nMHmCw+bxyN2WRVS1yupxLOTn07mhwYiJz80HEf8NBPaSH3FAYPE5oA2h7sB5p9DPPg5vw6J1CarN4XYilyJREmnxXqyBYHAZxGNLNalTmX9KB7kRrsMQnsOQ4sBR88cqIk4K4dozwFacoDfO+DIITpyOCUHaN8FpwMHn8Ni9i7Qbdv80ZIAvOQQ3HwKaTRr/nmxFSpfTabHvtdT/u499C/ooUnE"
}

def _ts(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())

def _iso(value: int) -> str:
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _round(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))

def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(row) for row in path.read_text(encoding="utf-8").splitlines() if row.strip()]

def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def _allocate(amount: int, rows: list[tuple[str, int]]) -> dict[str, int]:
    answer = {key: 0 for key, _ in rows}
    denominator = sum(weight for _, weight in rows)
    if amount == 0 or denominator == 0:
        return answer
    sign, magnitude = (1 if amount > 0 else -1), abs(amount)
    fractions: list[tuple[Decimal, str]] = []
    spent = 0
    for key, weight in rows:
        share = Decimal(magnitude * weight) / Decimal(denominator)
        floor = int(share.to_integral_value(rounding=ROUND_FLOOR))
        answer[key] = sign * floor
        spent += floor
        fractions.append((share - floor, key))
    for _, key in sorted(fractions, key=lambda item: (-item[0], item[1]))[:magnitude - spent]:
        answer[key] += sign
    return answer

def independently_derive(root: Path) -> dict[str, Any]:
    policy = _json(root / "policy.json")
    contracts = {row["contract_id"]: row for row in _json(root / "contracts.json")}
    calls = _jsonl(root / "port_calls.jsonl")
    revisions = _jsonl(root / "event_revisions.jsonl")
    raw_stops = _jsonl(root / "stoppages.jsonl")
    raw_ops = _jsonl(root / "cargo_operations.jsonl")
    periods = _jsonl(root / "rate_periods.jsonl")
    adjustments = _jsonl(root / "adjustments.jsonl")
    holidays = set(_json(root / "holidays.json")["utc_dates"])
    issues: list[dict[str, Any]] = []

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in revisions:
        buckets[row["event_id"]].append(row)
    decisions, effective = [], []
    for event_id in sorted(buckets):
        ordered = sorted(buckets[event_id], key=lambda r: (int(r["revision"]), _ts(r["recorded_at"]), r["record_id"]))
        winner = ordered[-1]
        tied = [r for r in ordered if int(r["revision"]) == int(winner["revision"]) and r["recorded_at"] == winner["recorded_at"]]
        if len({(r["status"], r.get("call_id"), r.get("event_type"), r.get("event_time")) for r in tied}) > 1:
            issues.append({"code": "REVISION_TIE_CONFLICT", "record_id": event_id})
        decisions.append({"event_id": event_id, "winner_record_id": winner["record_id"], "discarded_record_ids": sorted(r["record_id"] for r in ordered if r is not winner)})
        if winner["status"] == "active":
            effective.append({key: winner[key] for key in ("event_id", "call_id", "event_type", "event_time", "revision", "record_id")})
    effective.sort(key=lambda r: (r["call_id"], _ts(r["event_time"]), r["event_type"], r["event_id"]))
    event_index: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in effective:
        old = event_index[row["call_id"]].get(row["event_type"])
        if old is None or (_ts(row["event_time"]), row["event_id"]) < (_ts(old["event_time"]), old["event_id"]):
            event_index[row["call_id"]][row["event_type"]] = row

    stops: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_stops:
        try:
            assert _ts(row["start"]) < _ts(row["end"])
            stops[row["call_id"]].append(row)
        except (AssertionError, KeyError, ValueError):
            issues.append({"code": "INVALID_STOPPAGE", "record_id": row.get("stoppage_id", "?")})
    ops: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_ops:
        try:
            assert _ts(row["start"]) < _ts(row["end"]) and int(row["quantity_tonnes"]) >= 0
            ops[row["call_id"]].append(row)
        except (AssertionError, KeyError, ValueError):
            issues.append({"code": "INVALID_CARGO_OPERATION", "record_id": row.get("operation_id", "?")})

    accepted: list[dict[str, Any]] = []
    for base in calls:
        boundaries = event_index.get(base["call_id"], {})
        if not {"NOR_ACCEPTED", "CARGO_END"}.issubset(boundaries):
            issues.append({"code": "MISSING_REQUIRED_EVENT", "record_id": base["call_id"]})
            continue
        left = _ts(boundaries["NOR_ACCEPTED"]["event_time"])
        right = _ts(boundaries["CARGO_END"]["event_time"])
        if left >= right:
            issues.append({"code": "NON_POSITIVE_CALL_WINDOW", "record_id": base["call_id"]})
            continue
        row = dict(base, _left=left, _right=right, _tonnes=sum(int(x["quantity_tonnes"]) for x in ops[base["call_id"]]))
        accepted.append(row)
    accepted.sort(key=lambda r: (r["voyage_id"], int(r["sequence"]), r["call_id"]))

    rank = {code: pos for pos, code in enumerate(policy["precedence"])}
    factors = {key: int(value) for key, value in policy["count_factors_bps"].items()}
    intervals, metrics = [], {}
    for call in accepted:
        left, right = call["_left"], call["_right"]
        relevant_stops = [x for x in stops[call["call_id"]] if _ts(x["start"]) < right and _ts(x["end"]) > left]
        relevant_ops = [x for x in ops[call["call_id"]] if _ts(x["start"]) < right and _ts(x["end"]) > left]
        cuts = {left, right}
        for item in relevant_stops + relevant_ops:
            cuts.add(max(left, _ts(item["start"])))
            cuts.add(min(right, _ts(item["end"])))
        midnight = (left // DAY + 1) * DAY
        while midnight < right:
            cuts.add(midnight)
            midnight += DAY
        numerator = 0
        points = sorted(cuts)
        for start, end in zip(points, points[1:]):
            active = [x for x in relevant_stops if _ts(x["start"]) < end and _ts(x["end"]) > start]
            if active:
                chosen = min(active, key=lambda x: (rank[x["code"]], x["stoppage_id"]))
                code, source = chosen["code"], chosen["stoppage_id"]
            else:
                day = datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%d")
                working = [x for x in relevant_ops if _ts(x["start"]) < end and _ts(x["end"]) > start]
                if day in holidays:
                    code, source = "HOLIDAY", day
                elif working:
                    code, source = "CARGO_WORK", min(x["operation_id"] for x in working)
                else:
                    code, source = "IDLE", "idle"
            duration = end - start
            weighted = duration * factors[code]
            numerator += weighted
            intervals.append({"call_id": call["call_id"], "start": _iso(start), "end": _iso(end), "duration_seconds": duration, "governing_code": code, "source_id": source, "factor_bps": factors[code], "weighted_second_bps": weighted})
        contract = contracts[call["contract_id"]]
        metrics[call["call_id"]] = (_round(Decimal(numerator) / Decimal(10000)), int(contract["base_allowance_seconds"]) + _round(Decimal(call["_tonnes"] * 3600) / Decimal(int(contract["cargo_rate_tph"]))))

    grouped_calls: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for call in accepted:
        grouped_calls[call["voyage_id"]].append(call)
    adjustment_totals: dict[str, int] = defaultdict(int)
    for row in adjustments:
        adjustment_totals[row["voyage_id"]] += int(row["amount_cents"])
    allocated: dict[str, int] = {}
    for voyage, rows in grouped_calls.items():
        allocated.update(_allocate(adjustment_totals[voyage], [(x["call_id"], x["_tonnes"]) for x in rows]))

    def rate(second: int) -> tuple[str, int]:
        matches = [x for x in periods if _ts(x["start"]) <= second < _ts(x["end"])]
        if not matches:
            return "default", 10000
        chosen = max(matches, key=lambda x: (_ts(x["start"]), x["period_id"]))
        return chosen["period_id"], int(chosen["multiplier_bps"])

    def demurrage(seconds: int, contract: dict[str, Any], multiplier: int) -> int:
        total, consumed, remaining = 0, 0, seconds
        for tier in contract["demurrage_tiers"]:
            ceiling = tier["up_to_seconds"]
            width = remaining if ceiling is None else min(remaining, int(ceiling) - consumed)
            if width > 0:
                total += _round(Decimal(width * int(tier["usd_cents_per_day"]) * multiplier) / Decimal(DAY * 10000))
                remaining -= width
            if ceiling is not None:
                consumed = int(ceiling)
            if remaining <= 0:
                break
        return total

    settlements = []
    for voyage in sorted(grouped_calls):
        bank = 0
        for position, call in enumerate(grouped_calls[voyage]):
            contract = contracts[call["contract_id"]]
            counted, allowed = metrics[call["call_id"]]
            raw = counted - allowed
            combined = bank + raw
            cap = int(contract["bank_cap_seconds"])
            after = 0 if position == len(grouped_calls[voyage]) - 1 else max(-cap, min(cap, combined))
            settled = combined - after
            period_id, multiplier = rate(call["_right"] - 1)
            due = demurrage(max(settled, 0), contract, multiplier)
            saved = _round(Decimal(max(-settled, 0) * int(contract["despatch_usd_cents_per_day"]) * multiplier) / Decimal(DAY * 10000))
            adjustment = allocated.get(call["call_id"], 0)
            settlements.append({"call_id": call["call_id"], "voyage_id": voyage, "sequence": int(call["sequence"]), "charterer_id": call["charterer_id"], "contract_id": call["contract_id"], "window_start": _iso(call["_left"]), "window_end": _iso(call["_right"]), "cargo_tonnes": call["_tonnes"], "allowed_seconds": allowed, "counted_seconds": counted, "raw_delta_seconds": raw, "bank_before_seconds": bank, "settled_seconds": settled, "bank_after_seconds": after, "rate_period_id": period_id, "rate_multiplier_bps": multiplier, "demurrage_cents": due, "despatch_cents": saved, "adjustment_cents": adjustment, "net_due_cents": due - saved + adjustment})
            bank = after

    voyages = []
    for voyage in sorted(grouped_calls):
        rows = [x for x in settlements if x["voyage_id"] == voyage]
        voyages.append({"voyage_id": voyage, "call_ids": [x["call_id"] for x in rows], "call_count": len(rows), "cargo_tonnes": sum(x["cargo_tonnes"] for x in rows), "allowed_seconds": sum(x["allowed_seconds"] for x in rows), "counted_seconds": sum(x["counted_seconds"] for x in rows), "demurrage_cents": sum(x["demurrage_cents"] for x in rows), "despatch_cents": sum(x["despatch_cents"] for x in rows), "adjustment_cents": sum(x["adjustment_cents"] for x in rows), "net_due_cents": sum(x["net_due_cents"] for x in rows), "closing_bank_seconds": rows[-1]["bank_after_seconds"]})
    charterers = []
    for charterer in sorted({x["charterer_id"] for x in settlements}):
        rows = [x for x in settlements if x["charterer_id"] == charterer]
        charterers.append({"charterer_id": charterer, "call_ids": sorted(x["call_id"] for x in rows), "voyage_ids": sorted({x["voyage_id"] for x in rows}), "demurrage_cents": sum(x["demurrage_cents"] for x in rows), "despatch_cents": sum(x["despatch_cents"] for x in rows), "adjustment_cents": sum(x["adjustment_cents"] for x in rows), "net_due_cents": sum(x["net_due_cents"] for x in rows)})
    exceptions = list(issues)
    for row in settlements:
        if abs(row["net_due_cents"]) >= int(policy["exception_net_due_cents"]):
            exceptions.append({"code": "MATERIAL_SETTLEMENT", "record_id": row["call_id"], "net_due_cents": row["net_due_cents"]})
    exceptions.sort(key=lambda x: (x["code"], x["record_id"]))
    chain, trace = "0" * 64, []
    for row in settlements:
        digest = hashlib.sha256((chain + _canon(row)).encode()).hexdigest()
        trace.append({"call_id": row["call_id"], "previous_hash": chain, "entry_hash": digest})
        chain = digest
    files = sorted(x for x in root.iterdir() if x.is_file())
    counts = {"port_calls": len(calls), "event_revisions": len(revisions), "stoppages": len(raw_stops), "cargo_operations": len(raw_ops), "rate_periods": len(periods), "adjustments": len(adjustments)}
    return {
        "manifest.json": {"engine_version": policy["engine_version"], "input_files": [{"name": x.name, "sha256": hashlib.sha256(x.read_bytes()).hexdigest(), "bytes": x.stat().st_size} for x in files], "valid_call_count": len(accepted), "effective_event_count": len(effective), "interval_count": len(intervals)},
        "data_quality.json": {"input_file_count": len(files), "record_counts": counts, "issue_count": len(issues), "issues": sorted(issues, key=lambda x: (x["code"], x["record_id"]))},
        "event_ledger.json": {"effective_events": effective, "revision_decisions": decisions},
        "interval_ledger.json": {"intervals": intervals},
        "call_settlements.json": {"calls": settlements},
        "voyage_rollups.json": {"voyages": voyages},
        "charterer_statements.json": {"charterers": charterers},
        "exception_register.json": {"exceptions": exceptions},
        "audit_trace.json": {"entries": trace, "final_hash": chain},
    }

def _write_lines(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

def shipped(root: Path) -> Path:
    root.mkdir(parents=True)
    for name, blob in _PACKED.items():
        (root / name).write_bytes(zlib.decompress(base64.b64decode(blob)))
    # Manifest semantics require this tenth input. Its exact visible bytes are
    # embedded separately by reading the public task copy when available; the
    # deterministic fallback keeps tests-only isolation self-contained.
    public_schema = Path("/app/data/schema.md")
    schema = public_schema.read_bytes() if public_schema.is_file() else b"# Maritime Laytime Settlement Contract (MLSE-1.0)\n"
    (root / "schema.md").write_bytes(schema)
    _seal(root)
    return root

def challenge(root: Path) -> Path:
    shipped(root)
    contracts = [{"contract_id": "CP-X", "base_allowance_seconds": 0, "cargo_rate_tph": 3600, "bank_cap_seconds": 3600, "despatch_usd_cents_per_day": 864000, "demurrage_tiers": [{"up_to_seconds": 7200, "usd_cents_per_day": 864000}, {"up_to_seconds": 18000, "usd_cents_per_day": 1728000}, {"up_to_seconds": None, "usd_cents_per_day": 2592000}]}]
    (root / "contracts.json").write_text(json.dumps(contracts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    calls = [
        {"call_id": "F-A", "voyage_id": "VX", "sequence": 1, "charterer_id": "CH-X", "contract_id": "CP-X"},
        {"call_id": "F-B", "voyage_id": "VX", "sequence": 2, "charterer_id": "CH-X", "contract_id": "CP-X"},
        {"call_id": "F-C", "voyage_id": "VY", "sequence": 1, "charterer_id": "CH-Y", "contract_id": "CP-X"},
    ]
    _write_lines(root / "port_calls.jsonl", calls)
    events: list[dict[str, Any]] = []
    def event(record: str, event_id: str, call: str, kind: str, when: str, revision: int = 1, recorded: str = "2026-03-10T00:00:00Z", status: str = "active") -> None:
        events.append({"record_id": record, "event_id": event_id, "call_id": call, "event_type": kind, "event_time": when, "revision": revision, "recorded_at": recorded, "status": status})
    event("r1", "e-a-nor", "F-A", "NOR_ACCEPTED", "2026-03-14T20:00:00Z")
    event("r2", "e-a-end", "F-A", "CARGO_END", "2026-03-15T08:00:00Z")
    event("r3", "e-b-nor", "F-B", "NOR_ACCEPTED", "2026-03-16T00:00:00Z")
    event("r4", "e-b-end", "F-B", "CARGO_END", "2026-03-17T06:00:00Z")
    event("r5", "e-c-nor", "F-C", "NOR_ACCEPTED", "2026-03-18T00:00:00Z")
    event("r6", "e-c-end", "F-C", "CARGO_END", "2026-03-18T02:00:00Z")
    event("r7", "e-c-end", "F-C", "CARGO_END", "2026-03-18T03:00:00Z", 2, "2026-03-11T00:00:00Z")
    event("r8", "e-c-end", "F-C", "CARGO_END", "2026-03-18T04:00:00Z", 2, "2026-03-11T00:00:00Z")
    event("r9", "cancel-me", "F-C", "OTHER", "2026-03-18T01:00:00Z", 1, status="cancelled")
    _write_lines(root / "event_revisions.jsonl", events)
    stops = [
        {"stoppage_id": "S-Z", "call_id": "F-A", "code": "WEATHER", "start": "2026-03-14T22:00:00Z", "end": "2026-03-15T02:00:00Z"},
        {"stoppage_id": "S-A", "call_id": "F-A", "code": "OWNER_DELAY", "start": "2026-03-14T23:00:00Z", "end": "2026-03-15T01:00:00Z"},
        {"stoppage_id": "S-BAD", "call_id": "F-B", "code": "WEATHER", "start": "2026-03-16T05:00:00Z", "end": "2026-03-16T05:00:00Z"},
    ]
    _write_lines(root / "stoppages.jsonl", stops)
    ops = [
        {"operation_id": "O-A", "call_id": "F-A", "start": "2026-03-14T20:00:00Z", "end": "2026-03-15T08:00:00Z", "quantity_tonnes": 1},
        {"operation_id": "O-B", "call_id": "F-B", "start": "2026-03-16T00:00:00Z", "end": "2026-03-17T06:00:00Z", "quantity_tonnes": 2},
        {"operation_id": "O-C", "call_id": "F-C", "start": "2026-03-18T00:00:00Z", "end": "2026-03-18T04:00:00Z", "quantity_tonnes": 1},
        {"operation_id": "O-BAD", "call_id": "F-C", "start": "2026-03-18T02:00:00Z", "end": "2026-03-18T01:00:00Z", "quantity_tonnes": -1},
    ]
    _write_lines(root / "cargo_operations.jsonl", ops)
    _write_lines(root / "rate_periods.jsonl", [{"period_id": "RP-X", "start": "2026-03-15T00:00:00Z", "end": "2026-03-18T00:00:00Z", "multiplier_bps": 12500}])
    _write_lines(root / "adjustments.jsonl", [{"adjustment_id": "A-X", "voyage_id": "VX", "amount_cents": -5}, {"adjustment_id": "A-Y", "voyage_id": "VY", "amount_cents": 7}])
    (root / "holidays.json").write_text(json.dumps({"utc_dates": ["2026-03-15"]}, sort_keys=True) + "\n", encoding="utf-8")
    _seal(root)
    return root

def _seal(root: Path) -> None:
    for path in root.iterdir():
        path.chmod(0o644)
    root.chmod(0o755)

def _root_only_tests() -> bool:
    try:
        stat = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return stat.st_uid == 0 and stat.st_mode & 0o077 == 0

def _grant(path_text: str) -> None:
    if not path_text.startswith("/app"):
        return
    path = Path(path_text)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if parent == Path("/app"):
                break
    except OSError:
        pass

def _command(arguments: list[str]) -> list[str]:
    if os.name != "posix" and _root_only_tests():
        raise RuntimeError("POSIX isolation required")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests():
        raise RuntimeError("root is required for verifier isolation")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in arguments:
            _grant(argument)
        return [*_SETPRIV, *arguments]
    return arguments

def _run(data: Path, out: Path) -> None:
    out.parent.chmod(0o777)
    out.mkdir(mode=0o777)
    for name in REPORTS:
        (out / name).write_text('{"stale":true}\n', encoding="utf-8")
        (out / name).chmod(0o666)
    process = subprocess.Popen(_command([sys.executable, "-I", "-S", str(SCRIPT), str(data), str(out)]), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"})
    try:
        stdout, stderr = process.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise AssertionError("submission timed out")
    assert process.returncode == 0, f"submission exited {process.returncode}: {stdout[-500:]} {stderr[-500:]}"

_VISIBLE: dict[str, Any] | None = None
_FRESH: dict[str, Any] | None = None

def _visible_expected() -> dict[str, Any]:
    global _VISIBLE
    if _VISIBLE is None:
        with tempfile.TemporaryDirectory() as td:
            root = shipped(Path(td) / "data")
            _VISIBLE = independently_derive(root)
    return _VISIBLE

def _fresh_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    global _FRESH
    if _FRESH is None:
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            parent.chmod(0o777)
            data = challenge(parent / "data")
            out = parent / "out"
            expected = independently_derive(data)
            _run(data, out)
            actual = {name: _json(out / name) for name in REPORTS}
            _FRESH = {"expected": expected, "actual": actual}
    return _FRESH["expected"], _FRESH["actual"]

def _actual(name: str) -> Any:
    return _json(OUT / name)

def _source() -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in OUT.glob("*.py"))

def _holds(check: Callable[[], Any]) -> bool:
    try:
        check()
    except Exception:
        return False
    return True

def _all_artifacts() -> None:
    assert SCRIPT.is_file()
    for name in REPORTS:
        assert isinstance(_actual(name), dict)

def _visible(name: str) -> None:
    assert _actual(name) == _visible_expected()[name]

def _visible_manifest() -> None:
    actual = _actual("manifest.json")
    expected = _visible_expected()["manifest.json"]
    for key in ("engine_version", "valid_call_count", "effective_event_count", "interval_count"):
        assert actual[key] == expected[key]
    actual_files = {row["name"]: row for row in actual["input_files"]}
    expected_files = {row["name"]: row for row in expected["input_files"]}
    assert set(actual_files) == set(expected_files)
    for name in actual_files:
        assert set(actual_files[name]) == {"name", "sha256", "bytes"}
        assert len(actual_files[name]["sha256"]) == 64 and actual_files[name]["bytes"] > 0
        if name != "schema.md":
            assert actual_files[name] == expected_files[name]

def _fresh(name: str) -> None:
    expected, actual = _fresh_pair()
    assert actual[name] == expected[name]

def _fresh_semantic_spine() -> None:
    expected, actual = _fresh_pair()
    assert actual["call_settlements.json"] == expected["call_settlements.json"]
    calls = actual["call_settlements.json"]["calls"]
    assert any(row["demurrage_cents"] > 0 for row in calls)
    assert any(row["bank_before_seconds"] != 0 for row in calls)
    assert any(row["rate_period_id"] == "default" for row in calls)
    assert sum(row["adjustment_cents"] for row in calls if row["voyage_id"] == "VX") == -5

def _serialization() -> None:
    for name in REPORTS:
        text = (OUT / name).read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"

def _safe_source() -> None:
    assert SCRIPT.is_file() and SCRIPT.stat().st_size > 0
    text = _source().lower()
    assert "/tests" not in text and "rewardkit" not in text and "judge.toml" not in text
    forbidden = {"requests", "urllib", "socket", "pandas", "numpy"}
    for path in OUT.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert not ({name.name.split(".")[0] for name in node.names} & forbidden)
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in forbidden

def _deterministic_and_no_mutation() -> None:
    with tempfile.TemporaryDirectory() as td:
        parent = Path(td); parent.chmod(0o777)
        data = challenge(parent / "data")
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in data.iterdir()}
        one, two = parent / "one", parent / "two"
        _run(data, one); _run(data, two)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in data.iterdir()}
        assert before == after
        assert {n: (one / n).read_bytes() for n in REPORTS} == {n: (two / n).read_bytes() for n in REPORTS}

def _negative_hardcoded() -> None:
    text = _source()
    markers = ["CALL-101", "VOY-ALPHA", "CALL-202", "102600", "21600"]
    assert sum(marker in text for marker in markers) >= 3

def _negative_verifier_access() -> None:
    text = _source().lower()
    assert any(marker in text for marker in ("/tests", "rewardkit", "judge.toml", "test_output"))

def _negative_external_dependency() -> None:
    text = _source().lower()
    assert any(marker in text for marker in ("requests", "urllib", "socket", "pandas", "numpy", "subprocess"))

@criterion(description="The reusable program and all nine declared JSON reports exist and parse.")
def artifact_set(workspace: Path) -> bool: return _holds(_all_artifacts)

@criterion(description="The visible manifest exactly records input hashes, sizes, and derived counts.")
def visible_manifest(workspace: Path) -> bool: return _holds(_visible_manifest)

@criterion(description="Visible quarantine and revision quality findings are independently reproduced.")
def visible_quality(workspace: Path) -> bool: return _holds(lambda: _visible("data_quality.json"))

@criterion(description="Visible effective-event and revision-decision ledgers are exact.")
def visible_events(workspace: Path) -> bool: return _holds(lambda: _visible("event_ledger.json"))

@criterion(description="Visible atomic interval splitting, precedence, factors, and sources are exact.")
def visible_intervals(workspace: Path) -> bool: return _holds(lambda: _visible("interval_ledger.json"))

@criterion(description="Visible call settlements exactly implement allowance, banks, rates, and money.")
def visible_settlements(workspace: Path) -> bool: return _holds(lambda: _visible("call_settlements.json"))

@criterion(description="Visible voyage rollups exactly reconcile ordered calls and closing banks.")
def visible_voyages(workspace: Path) -> bool: return _holds(lambda: _visible("voyage_rollups.json"))

@criterion(description="Visible charterer statements exactly reconcile call and voyage money.")
def visible_charterers(workspace: Path) -> bool: return _holds(lambda: _visible("charterer_statements.json"))

@criterion(description="Visible exception register includes exactly quality and material rows.")
def visible_exceptions(workspace: Path) -> bool: return _holds(lambda: _visible("exception_register.json"))

@criterion(description="Visible chained settlement audit hashes are exact.")
def visible_audit(workspace: Path) -> bool: return _holds(lambda: _visible("audit_trace.json"))

@criterion(description="Fresh events handle tie conflicts, cancellation, supersession, and boundaries.")
def fresh_events(workspace: Path) -> bool: return _holds(lambda: _fresh("event_ledger.json"))

@criterion(description="Fresh intervals handle midnight, holiday, precedence, cargo, and idle rules.")
def fresh_intervals(workspace: Path) -> bool: return _holds(lambda: _fresh("interval_ledger.json"))

@criterion(description="Fresh settlement spine handles cap overflow, final flush, tiers, defaults, and signed allocation.")
def fresh_settlement_spine(workspace: Path) -> bool: return _holds(_fresh_semantic_spine)

@criterion(description="Fresh voyage and charterer aggregations reconcile independently.")
def fresh_aggregates(workspace: Path) -> bool: return _holds(lambda: (_fresh("voyage_rollups.json"), _fresh("charterer_statements.json")))

@criterion(description="Fresh quality, exception, manifest, and audit reports all match independent derivation.")
def fresh_controls(workspace: Path) -> bool: return _holds(lambda: (_fresh("data_quality.json"), _fresh("exception_register.json"), _fresh("manifest.json"), _fresh("audit_trace.json")))

@criterion(description="All delivered JSON uses exact sorted-key pretty serialization with trailing newlines.")
def canonical_serialization(workspace: Path) -> bool: return _holds(_serialization)

@criterion(description="The implementation uses only local standard-library computation and does not inspect graders.")
def local_safe_source(workspace: Path) -> bool: return _holds(_safe_source)

@criterion(description="Fresh executions are deterministic and never mutate their input corpus.")
def deterministic_no_mutation(workspace: Path) -> bool: return _holds(_deterministic_and_no_mutation)

@criterion(description="Detects hardcoded visible answers or identifiers in submitted source.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool: return _holds(_negative_hardcoded)

@criterion(description="Detects attempts to inspect verifier or reward files.")
def negative_reads_verifier(workspace: Path) -> bool: return _holds(_negative_verifier_access)

@criterion(description="Detects external dependencies, network access, or subprocess delegation.")
def negative_external_or_subprocess(workspace: Path) -> bool: return _holds(_negative_external_dependency)

criteria.artifact_set(weight=1)
criteria.visible_manifest(weight=3)
criteria.visible_quality(weight=3)
criteria.visible_events(weight=3)
criteria.visible_intervals(weight=5)
criteria.visible_settlements(weight=5)
criteria.visible_voyages(weight=3)
criteria.visible_charterers(weight=3)
criteria.visible_exceptions(weight=3)
criteria.visible_audit(weight=3)
criteria.fresh_events(weight=5)
criteria.fresh_intervals(weight=5)
criteria.fresh_settlement_spine(weight=5)
criteria.fresh_aggregates(weight=3)
criteria.fresh_controls(weight=5)
criteria.canonical_serialization(weight=3)
criteria.local_safe_source(weight=3)
criteria.deterministic_no_mutation(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_verifier(weight=-5)
criteria.negative_external_or_subprocess(weight=-3)
