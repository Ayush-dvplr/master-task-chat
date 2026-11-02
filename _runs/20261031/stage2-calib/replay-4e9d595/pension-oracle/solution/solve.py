#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

REPORTS = ("manifest.json", "data_quality.json", "service_ledger.json", "accrual_ledger.json", "cola_ledger.json", "member_benefits.json", "plan_rollups.json", "exception_register.json", "audit_trace.json")


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def day(value: str) -> date:
    return date.fromisoformat(value)


def stamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def rounded(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def resolve_services(raw: list[dict[str, Any]], issues: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw:
        grouped[row["service_id"]].append(row)
    decisions, winners = [], []
    for service_id in sorted(grouped):
        ordered = sorted(grouped[service_id], key=lambda row: (int(row["revision"]), stamp(row["recorded_at"]), row["record_id"]))
        winner = ordered[-1]
        peers = [row for row in ordered if int(row["revision"]) == int(winner["revision"]) and row["recorded_at"] == winner["recorded_at"]]
        payloads = {canonical({key: value for key, value in row.items() if key != "record_id"}) for row in peers}
        if len(payloads) > 1:
            issues.append({"code": "REVISION_TIE_CONFLICT", "record_id": service_id})
        decisions.append({"service_id": service_id, "winner_record_id": winner["record_id"], "discarded_record_ids": sorted(row["record_id"] for row in ordered if row is not winner)})
        if winner["status"] == "active":
            winners.append(winner)
    return winners, decisions


def age_months(birth: date, retirement: date) -> int:
    return (retirement.year - birth.year) * 12 + retirement.month - birth.month - (1 if retirement.day < birth.day else 0)


def main(data: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    policy = json.loads((data / "policy.json").read_text())
    raw_plans = json.loads((data / "plans.json").read_text())
    raw_members = rows(data / "members.jsonl")
    raw_services = rows(data / "service_revisions.jsonl")
    raw_salaries = rows(data / "salary_history.jsonl")
    raw_leaves = rows(data / "leave_intervals.jsonl")
    raw_colas = rows(data / "cola_rules.jsonl")
    raw_rebases = rows(data / "rebase_events.jsonl")
    raw_elections = rows(data / "elections.jsonl")
    valuation = day(policy["valuation_date"])
    issues: list[dict[str, Any]] = []

    plans = {row["plan_id"]: row for row in raw_plans}
    members: dict[str, dict[str, Any]] = {}
    for row in raw_members:
        try:
            valid = row["plan_id"] in plans and day(row["birth_date"]) < valuation
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            members[row["member_id"]] = row
        else:
            issues.append({"code": "INVALID_MEMBER", "record_id": row.get("member_id", "?")})

    service_winners, decisions = resolve_services(raw_services, issues)
    services: list[dict[str, Any]] = []
    for row in service_winners:
        try:
            valid = row["member_id"] in members and day(row["start"]) < day(row["end"])
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            services.append(row)
        else:
            issues.append({"code": "INVALID_SERVICE", "record_id": row.get("service_id", "?")})
    services.sort(key=lambda row: (row["member_id"], row["start"], row["end"], row["service_id"]))

    def validate_intervals(raw: list[dict[str, Any]], code: str, id_key: str, extra: Any) -> list[dict[str, Any]]:
        valid_rows = []
        for row in raw:
            try:
                valid = row["member_id"] in members and day(row["start"]) < day(row["end"]) and bool(extra(row))
            except (KeyError, TypeError, ValueError):
                valid = False
            if valid:
                valid_rows.append(row)
            else:
                issues.append({"code": code, "record_id": row.get(id_key, "?")})
        return valid_rows

    salaries = validate_intervals(raw_salaries, "INVALID_SALARY", "salary_id", lambda row: int(row["annual_salary_cents"]) >= 0)
    leaves = validate_intervals(raw_leaves, "INVALID_LEAVE", "leave_id", lambda row: 0 <= int(row["credit_bps"]) <= 10000)
    colas: list[dict[str, Any]] = []
    for row in raw_colas:
        try:
            valid = row["plan_id"] in plans and day(row["effective_date"]) <= valuation and int(row["factor_bps"]) >= 0
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            colas.append(row)
        else:
            issues.append({"code": "INVALID_COLA", "record_id": row.get("cola_id", "?")})
    rebases: list[dict[str, Any]] = []
    for row in raw_rebases:
        try:
            valid = row["member_id"] in members and day(row["effective_date"]) <= valuation and int(row["factor_bps"]) >= 0
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            rebases.append(row)
        else:
            issues.append({"code": "INVALID_REBASE", "record_id": row.get("rebase_id", "?")})
    elections_by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_elections:
        try:
            valid = row["member_id"] in members and 0 <= int(row["option_factor_bps"]) <= 10000 and day(row["retirement_date"])
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            elections_by_member[row["member_id"]].append(row)
        else:
            issues.append({"code": "INVALID_ELECTION", "record_id": row.get("election_id", "?")})

    salaries_by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    leaves_by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in salaries:
        salaries_by_member[row["member_id"]].append(row)
    for row in leaves:
        leaves_by_member[row["member_id"]].append(row)

    atoms: list[dict[str, Any]] = []
    for service in services:
        member_id = service["member_id"]
        start, end = day(service["start"]), min(day(service["end"]), valuation)
        if start >= end:
            continue
        cuts = {start, end}
        for row in salaries_by_member[member_id] + leaves_by_member[member_id]:
            lo, hi = day(row["start"]), day(row["end"])
            if lo < end and start < hi:
                cuts.update((max(start, lo), min(end, hi)))
        for year in range(start.year + 1, end.year + 1):
            boundary = date(year, 1, 1)
            if start < boundary < end:
                cuts.add(boundary)
        ordered = sorted(cuts)
        plan = plans[members[member_id]["plan_id"]]
        for atom_start, atom_end in zip(ordered, ordered[1:]):
            covering_salary = [row for row in salaries_by_member[member_id] if day(row["start"]) <= atom_start and atom_end <= day(row["end"])]
            if not covering_salary:
                issues.append({"code": "MISSING_SALARY", "record_id": f'{service["service_id"]}:{atom_start.isoformat()}'})
                continue
            salary = max(covering_salary, key=lambda row: (day(row["start"]), row["salary_id"]))
            factors = [int(row["credit_bps"]) for row in leaves_by_member[member_id] if day(row["start"]) <= atom_start and atom_end <= day(row["end"])]
            factor = min(factors, default=10000)
            calendar_days = (atom_end - atom_start).days
            credited = rounded(Decimal(calendar_days * factor) / Decimal(10000))
            capped = min(int(salary["annual_salary_cents"]), int(plan["annual_cap_cents"]))
            accrual = rounded(Decimal(capped * int(plan["accrual_bps"]) * credited) / Decimal(10000 * int(policy["days_per_year"])))
            atoms.append({"member_id": member_id, "plan_id": plan["plan_id"], "service_id": service["service_id"], "salary_id": salary["salary_id"], "start": atom_start.isoformat(), "end": atom_end.isoformat(), "calendar_days": calendar_days, "leave_factor_bps": factor, "credited_days": credited, "capped_salary_cents": capped, "accrual_bps": int(plan["accrual_bps"]), "accrual_cents": accrual})
    atoms.sort(key=lambda row: (row["member_id"], row["start"], row["end"], row["service_id"], row["salary_id"]))

    atoms_by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for atom in atoms:
        atoms_by_member[atom["member_id"]].append(atom)
    cola_events: list[dict[str, Any]] = []
    benefits: list[dict[str, Any]] = []
    for member_id in sorted(members):
        member, plan = members[member_id], plans[members[member_id]["plan_id"]]
        stream: list[tuple[date, int, str, str, int]] = []
        for atom in atoms_by_member[member_id]:
            stream.append((day(atom["end"]), 0, "ACCRUAL", f'{atom["service_id"]}:{atom["start"]}', int(atom["accrual_cents"])))
        for event in colas:
            if event["plan_id"] == plan["plan_id"]:
                stream.append((day(event["effective_date"]), 1, "COLA", event["cola_id"], int(event["factor_bps"])))
        for event in rebases:
            if event["member_id"] == member_id:
                stream.append((day(event["effective_date"]), 2, "REBASE", event["rebase_id"], int(event["factor_bps"])))
        balance = 0
        for event_date, _, kind, event_id, value in sorted(stream, key=lambda item: (item[0], item[1], item[3])):
            if kind == "ACCRUAL":
                balance += value
            else:
                before = balance
                balance = rounded(Decimal(balance * value) / Decimal(10000))
                cola_events.append({"member_id": member_id, "event_date": event_date.isoformat(), "event_kind": kind, "event_id": event_id, "factor_bps": value, "balance_before_cents": before, "balance_after_cents": balance, "delta_cents": balance - before})
        chosen = max(elections_by_member.get(member_id, []), key=lambda row: (day(row["retirement_date"]), row["election_id"]), default=None)
        if chosen:
            retirement = day(chosen["retirement_date"])
            age = age_months(day(member["birth_date"]), retirement)
            option = int(chosen["option_factor_bps"])
            election_id, retirement_text = chosen["election_id"], chosen["retirement_date"]
        else:
            retirement, age, option = valuation, age_months(day(member["birth_date"]), valuation), int(plan["option_factor_bps"])
            election_id, retirement_text = None, None
        early = max(0, int(plan["normal_age_months"]) - age)
        reduction = min(10000, early * int(plan["early_reduction_bps_per_month"]))
        reduced = rounded(Decimal(balance * (10000 - reduction)) / Decimal(10000))
        payable = rounded(Decimal(reduced * option) / Decimal(10000))
        member_atoms = atoms_by_member[member_id]
        base = sum(int(row["accrual_cents"]) for row in member_atoms)
        benefits.append({"member_id": member_id, "plan_id": plan["plan_id"], "credited_days": sum(int(row["credited_days"]) for row in member_atoms), "base_accrual_cents": base, "revaluation_delta_cents": balance - base, "accrued_cents": balance, "election_id": election_id, "retirement_date": retirement_text, "age_months": age, "early_months": early, "reduction_bps": reduction, "option_factor_bps": option, "payable_cents": payable})
    cola_events.sort(key=lambda row: (row["member_id"], row["event_date"], {"COLA": 1, "REBASE": 2}[row["event_kind"]], row["event_id"]))

    rollup_rows = []
    for plan_id in sorted(plans):
        group = [row for row in benefits if row["plan_id"] == plan_id]
        rollup_rows.append({"plan_id": plan_id, "member_count": len(group), "credited_days": sum(row["credited_days"] for row in group), "base_accrual_cents": sum(row["base_accrual_cents"] for row in group), "revaluation_delta_cents": sum(row["revaluation_delta_cents"] for row in group), "accrued_cents": sum(row["accrued_cents"] for row in group), "payable_cents": sum(row["payable_cents"] for row in group)})
    issues.sort(key=lambda row: (row["code"], row["record_id"]))
    exceptions: list[dict[str, Any]] = list(issues)
    for row in benefits:
        if abs(int(row["payable_cents"])) >= int(policy["material_cents"]):
            exceptions.append({"code": "MATERIAL_BENEFIT", "record_id": row["member_id"], "amount_cents": row["payable_cents"]})
    exceptions.sort(key=lambda row: (row["code"], row["record_id"]))
    audit_rows, previous = [], "0" * 64
    for row in benefits:
        row_hash = hashlib.sha256((previous + canonical(row)).encode()).hexdigest()
        audit_rows.append({"member_id": row["member_id"], "previous_hash": previous, "row_hash": row_hash})
        previous = row_hash
    input_files = [{"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in sorted(data.iterdir()) if path.is_file()]
    record_counts = {"members": len(raw_members), "service_revisions": len(raw_services), "salaries": len(raw_salaries), "leaves": len(raw_leaves), "cola_rules": len(raw_colas), "rebases": len(raw_rebases), "elections": len(raw_elections)}
    effective_services = [{key: row[key] for key in ("service_id", "member_id", "start", "end")} for row in services]
    reports = {
        "manifest.json": {"engine_version": policy["engine_version"], "input_files": input_files, "valid_member_count": len(members), "effective_service_count": len(services), "accrual_atom_count": len(atoms)},
        "data_quality.json": {"input_file_count": len(input_files), "record_counts": record_counts, "issue_count": len(issues), "issues": issues},
        "service_ledger.json": {"revision_decisions": decisions, "effective_services": effective_services},
        "accrual_ledger.json": {"atoms": atoms},
        "cola_ledger.json": {"events": cola_events},
        "member_benefits.json": {"members": benefits},
        "plan_rollups.json": {"plans": rollup_rows},
        "exception_register.json": {"exceptions": exceptions},
        "audit_trace.json": {"rows": audit_rows, "final_hash": previous},
    }
    for name, value in reports.items():
        write(out / name, value)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: calculate_pension.py DATA_DIR OUT_DIR", file=sys.stderr)
        raise SystemExit(2)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
