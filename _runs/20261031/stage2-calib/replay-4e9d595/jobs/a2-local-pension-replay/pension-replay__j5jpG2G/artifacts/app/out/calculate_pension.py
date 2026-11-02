#!/usr/bin/env python3
"""PACR-1.0 pension accrual / COLA / rebase valuation engine.

Usage: python3 calculate_pension.py DATA_DIR OUT_DIR

Implements the contract in DATA_DIR/schema.md using only the standard library.
All money is integer cents, rates integer basis points, durations integer days
or months.  Decimal ROUND_HALF_UP is applied only at the boundaries named by
the contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext

BPS = 10000
ZERO_HASH = "0" * 64
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KIND_ORDER = {"ACCRUAL": 0, "COLA": 1, "REBASE": 2}


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------
def round_half_up(numerator: int, denominator: int) -> int:
    """ROUND_HALF_UP(numerator / denominator) as an integer."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    with localcontext() as ctx:
        ctx.prec = 60
        value = Decimal(numerator) / Decimal(denominator)
        return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def apply_factor(amount_cents: int, factor_bps: int) -> int:
    return round_half_up(amount_cents * factor_bps, BPS)


def parse_date(value):
    if not isinstance(value, str) or not DATE_RE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_instant(value):
    """Parse a UTC timestamp into a comparable aware datetime."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def iso(day: date) -> str:
    return day.isoformat()


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# --------------------------------------------------------------------------
# input loading
# --------------------------------------------------------------------------
def read_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def file_digest(path):
    hasher = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1 << 16)
            if not chunk:
                break
            size += len(chunk)
            hasher.update(chunk)
    return hasher.hexdigest(), size


class Issues:
    def __init__(self):
        self._items = []
        self._seen = set()

    def add(self, code, record_id):
        key = (code, str(record_id))
        if key in self._seen:
            return
        self._seen.add(key)
        self._items.append({"code": key[0], "record_id": key[1]})

    def sorted(self):
        return sorted(self._items, key=lambda row: (row["code"], row["record_id"]))


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------
def build(data_dir):
    issues = Issues()

    policy = read_json(os.path.join(data_dir, "policy.json"))
    engine_version = policy["engine_version"]
    valuation_date = parse_date(policy["valuation_date"])
    days_per_year = int(policy["days_per_year"])
    material_cents = int(policy["material_cents"])

    raw_plans = read_json(os.path.join(data_dir, "plans.json"))
    raw = {
        name: read_jsonl(os.path.join(data_dir, name + ".jsonl"))
        for name in (
            "members",
            "service_revisions",
            "salary_history",
            "leave_intervals",
            "cola_rules",
            "rebase_events",
            "elections",
        )
    }

    record_counts = {
        "cola_rules.jsonl": len(raw["cola_rules"]),
        "elections.jsonl": len(raw["elections"]),
        "leave_intervals.jsonl": len(raw["leave_intervals"]),
        "members.jsonl": len(raw["members"]),
        "plans.json": len(raw_plans),
        "policy.json": 1,
        "rebase_events.jsonl": len(raw["rebase_events"]),
        "salary_history.jsonl": len(raw["salary_history"]),
        "service_revisions.jsonl": len(raw["service_revisions"]),
    }

    # ---- plans -----------------------------------------------------------
    plans = {}
    for row in sorted(raw_plans, key=canonical_json):
        plan_id = row["plan_id"]
        if plan_id in plans:
            continue
        plans[plan_id] = row

    # ---- members ---------------------------------------------------------
    members = {}
    for row in sorted(raw["members"], key=canonical_json):
        member_id = row.get("member_id")
        birth = parse_date(row.get("birth_date"))
        plan_id = row.get("plan_id")
        if not isinstance(member_id, str) or plan_id not in plans or birth is None:
            issues.add("INVALID_MEMBER", member_id)
            continue
        if member_id in members:
            continue
        members[member_id] = {
            "member_id": member_id,
            "plan_id": plan_id,
            "birth_date": birth,
            "status": row.get("status"),
        }

    # ---- service revisions ----------------------------------------------
    groups = {}
    for row in raw["service_revisions"]:
        groups.setdefault(row.get("service_id"), []).append(row)

    revision_decisions = []
    effective_services = []
    for service_id in sorted(groups, key=lambda key: (key is None, str(key))):
        candidates = groups[service_id]
        keyed = []
        for row in candidates:
            revision = row.get("revision")
            revision = revision if is_int(revision) else -1
            moment = parse_instant(row.get("recorded_at"))
            stamp = moment.timestamp() if moment is not None else float("-inf")
            keyed.append(((revision, stamp, str(row.get("record_id"))), row))
        keyed.sort(key=lambda item: item[0])
        winner_key, winner = keyed[-1]

        peers = [row for key, row in keyed if key[0] == winner_key[0] and key[1] == winner_key[1]]
        conflict = False
        if len(peers) > 1:
            shapes = {
                canonical_json({k: v for k, v in row.items() if k != "record_id"})
                for row in peers
            }
            if len(shapes) > 1:
                conflict = True
                for row in peers:
                    issues.add("REVISION_TIE_CONFLICT", row.get("record_id"))

        record_id = winner.get("record_id")
        member_id = winner.get("member_id")
        status = winner.get("status")
        start = parse_date(winner.get("start"))
        end = parse_date(winner.get("end"))

        if status == "cancelled":
            decision = "CANCELLED"
        elif member_id not in members or start is None or end is None or start >= end:
            decision = "INVALID"
            issues.add("INVALID_SERVICE", record_id)
        else:
            decision = "EFFECTIVE"
            effective_services.append(
                {
                    "service_id": service_id,
                    "member_id": member_id,
                    "start": iso(start),
                    "end": iso(end),
                }
            )

        revision_decisions.append(
            {
                "service_id": service_id,
                "winning_record_id": record_id,
                "revision": winner.get("revision"),
                "recorded_at": winner.get("recorded_at"),
                "status": status,
                "member_id": member_id,
                "start": winner.get("start"),
                "end": winner.get("end"),
                "decision": decision,
                "candidate_count": len(candidates),
                "tie_conflict": conflict,
            }
        )

    revision_decisions.sort(key=lambda row: str(row["service_id"]))
    effective_services.sort(
        key=lambda row: (row["member_id"], row["start"], row["end"], row["service_id"])
    )

    # ---- salaries --------------------------------------------------------
    salaries = {}
    for row in raw["salary_history"]:
        member_id = row.get("member_id")
        start = parse_date(row.get("start"))
        end = parse_date(row.get("end"))
        amount = row.get("annual_salary_cents")
        if (
            member_id not in members
            or start is None
            or end is None
            or start >= end
            or not is_int(amount)
            or amount < 0
        ):
            issues.add("INVALID_SALARY", row.get("salary_id"))
            continue
        salaries.setdefault(member_id, []).append(
            {
                "salary_id": row.get("salary_id"),
                "start": start,
                "end": end,
                "annual_salary_cents": amount,
            }
        )

    # ---- leaves ----------------------------------------------------------
    leaves = {}
    for row in raw["leave_intervals"]:
        member_id = row.get("member_id")
        start = parse_date(row.get("start"))
        end = parse_date(row.get("end"))
        credit = row.get("credit_bps")
        if (
            member_id not in members
            or start is None
            or end is None
            or start >= end
            or not is_int(credit)
            or credit < 0
            or credit > BPS
        ):
            issues.add("INVALID_LEAVE", row.get("leave_id"))
            continue
        leaves.setdefault(member_id, []).append(
            {
                "leave_id": row.get("leave_id"),
                "start": start,
                "end": end,
                "credit_bps": credit,
            }
        )

    # ---- cola rules ------------------------------------------------------
    cola_rules = {}
    for row in raw["cola_rules"]:
        plan_id = row.get("plan_id")
        effective = parse_date(row.get("effective_date"))
        factor = row.get("factor_bps")
        if plan_id not in plans or effective is None or not is_int(factor) or factor < 0:
            issues.add("INVALID_COLA", row.get("cola_id"))
            continue
        cola_rules.setdefault(plan_id, []).append(
            {
                "event_id": row.get("cola_id"),
                "effective_date": effective,
                "factor_bps": factor,
            }
        )

    # ---- rebases ---------------------------------------------------------
    rebases = {}
    for row in raw["rebase_events"]:
        member_id = row.get("member_id")
        effective = parse_date(row.get("effective_date"))
        factor = row.get("factor_bps")
        if member_id not in members or effective is None or not is_int(factor) or factor < 0:
            issues.add("INVALID_REBASE", row.get("rebase_id"))
            continue
        rebases.setdefault(member_id, []).append(
            {
                "event_id": row.get("rebase_id"),
                "effective_date": effective,
                "factor_bps": factor,
            }
        )

    # ---- elections -------------------------------------------------------
    elections = {}
    for row in raw["elections"]:
        member_id = row.get("member_id")
        retirement = parse_date(row.get("retirement_date"))
        factor = row.get("option_factor_bps")
        if (
            member_id not in members
            or retirement is None
            or not is_int(factor)
            or factor < 0
            or factor > BPS
        ):
            issues.add("INVALID_ELECTION", row.get("election_id"))
            continue
        election = {
            "election_id": row.get("election_id"),
            "retirement_date": retirement,
            "option_factor_bps": factor,
        }
        current = elections.get(member_id)
        key = (retirement, str(election["election_id"]))
        if current is None or key > (current["retirement_date"], str(current["election_id"])):
            elections[member_id] = election

    # ---- accrual atoms ---------------------------------------------------
    atoms = []
    for service in effective_services:
        member = members[service["member_id"]]
        plan = plans[member["plan_id"]]
        member_salaries = salaries.get(member["member_id"], [])
        member_leaves = leaves.get(member["member_id"], [])

        lo = date.fromisoformat(service["start"])
        hi = min(date.fromisoformat(service["end"]), valuation_date)
        if hi <= lo:
            continue

        cuts = {lo, hi}
        for interval in list(member_salaries) + list(member_leaves):
            for edge in (interval["start"], interval["end"]):
                if lo < edge < hi:
                    cuts.add(edge)
        for year in range(lo.year, hi.year + 1):
            jan = date(year, 1, 1)
            if lo < jan < hi:
                cuts.add(jan)
        if lo < valuation_date < hi:
            cuts.add(valuation_date)

        points = sorted(cuts)
        for start, end in zip(points, points[1:]):
            if end <= start:
                continue
            covering = [s for s in member_salaries if s["start"] <= start < s["end"]]
            if not covering:
                issues.add("MISSING_SALARY", "%s:%s" % (service["service_id"], iso(start)))
                continue
            salary = max(covering, key=lambda s: (s["start"], str(s["salary_id"])))
            capped = min(salary["annual_salary_cents"], plan["annual_cap_cents"])
            covering_leaves = [l for l in member_leaves if l["start"] <= start < l["end"]]
            leave_factor = min((l["credit_bps"] for l in covering_leaves), default=BPS)
            calendar_days = (end - start).days
            credited_days = round_half_up(calendar_days * leave_factor, BPS)
            accrual_cents = round_half_up(
                capped * plan["accrual_bps"] * credited_days, BPS * days_per_year
            )
            atoms.append(
                {
                    "member_id": member["member_id"],
                    "plan_id": plan["plan_id"],
                    "service_id": service["service_id"],
                    "salary_id": salary["salary_id"],
                    "start": iso(start),
                    "end": iso(end),
                    "calendar_days": calendar_days,
                    "leave_factor_bps": leave_factor,
                    "credited_days": credited_days,
                    "capped_salary_cents": capped,
                    "accrual_bps": plan["accrual_bps"],
                    "accrual_cents": accrual_cents,
                }
            )

    atoms.sort(
        key=lambda row: (
            row["member_id"],
            row["start"],
            row["end"],
            row["service_id"],
            str(row["salary_id"]),
        )
    )

    # ---- revaluation stream ---------------------------------------------
    atoms_by_member = {}
    for atom in atoms:
        atoms_by_member.setdefault(atom["member_id"], []).append(atom)

    cola_events = []
    member_rows = []
    for member_id in sorted(members):
        member = members[member_id]
        plan = plans[member["plan_id"]]
        stream = []
        for atom in atoms_by_member.get(member_id, []):
            event_id = "%s|%s|%s|%s" % (
                atom["service_id"],
                atom["salary_id"],
                atom["start"],
                atom["end"],
            )
            stream.append(
                {
                    "date": date.fromisoformat(atom["end"]),
                    "kind": "ACCRUAL",
                    "event_id": event_id,
                    "amount_cents": atom["accrual_cents"],
                }
            )
        for rule in cola_rules.get(member["plan_id"], []):
            stream.append(
                {
                    "date": rule["effective_date"],
                    "kind": "COLA",
                    "event_id": rule["event_id"],
                    "factor_bps": rule["factor_bps"],
                }
            )
        for rule in rebases.get(member_id, []):
            stream.append(
                {
                    "date": rule["effective_date"],
                    "kind": "REBASE",
                    "event_id": rule["event_id"],
                    "factor_bps": rule["factor_bps"],
                }
            )
        stream = [event for event in stream if event["date"] <= valuation_date]
        stream.sort(key=lambda e: (e["date"], KIND_ORDER[e["kind"]], str(e["event_id"])))

        balance = 0
        base_accrual = 0
        revaluation_delta = 0
        for event in stream:
            if event["kind"] == "ACCRUAL":
                balance += event["amount_cents"]
                base_accrual += event["amount_cents"]
                continue
            before = balance
            after = apply_factor(before, event["factor_bps"])
            balance = after
            revaluation_delta += after - before
            cola_events.append(
                {
                    "member_id": member_id,
                    "event_date": iso(event["date"]),
                    "event_kind": event["kind"],
                    "event_id": event["event_id"],
                    "factor_bps": event["factor_bps"],
                    "balance_before_cents": before,
                    "balance_after_cents": after,
                    "delta_cents": after - before,
                }
            )

        accrued = balance
        election = elections.get(member_id)
        if election is None:
            election_id = None
            retirement_date = None
            age_months = None
            early_months = 0
            reduction_bps = 0
            option_factor_bps = plan["option_factor_bps"]
        else:
            election_id = election["election_id"]
            retire = election["retirement_date"]
            retirement_date = iso(retire)
            birth = member["birth_date"]
            age_months = (
                (retire.year - birth.year) * 12
                + retire.month
                - birth.month
                - (1 if retire.day < birth.day else 0)
            )
            early_months = max(0, plan["normal_age_months"] - age_months)
            reduction_bps = min(BPS, early_months * plan["early_reduction_bps_per_month"])
            option_factor_bps = election["option_factor_bps"]

        reduced = apply_factor(accrued, BPS - reduction_bps)
        payable = apply_factor(reduced, option_factor_bps)

        member_rows.append(
            {
                "member_id": member_id,
                "plan_id": member["plan_id"],
                "credited_days": sum(
                    a["credited_days"] for a in atoms_by_member.get(member_id, [])
                ),
                "base_accrual_cents": base_accrual,
                "revaluation_delta_cents": revaluation_delta,
                "accrued_cents": accrued,
                "election_id": election_id,
                "retirement_date": retirement_date,
                "age_months": age_months,
                "early_months": early_months,
                "reduction_bps": reduction_bps,
                "option_factor_bps": option_factor_bps,
                "payable_cents": payable,
            }
        )

    cola_events.sort(
        key=lambda row: (
            row["member_id"],
            row["event_date"],
            KIND_ORDER[row["event_kind"]],
            str(row["event_id"]),
        )
    )
    member_rows.sort(key=lambda row: row["member_id"])

    # ---- rollups ---------------------------------------------------------
    plan_rows = []
    for plan_id in sorted(plans):
        rows = [row for row in member_rows if row["plan_id"] == plan_id]
        plan_rows.append(
            {
                "plan_id": plan_id,
                "member_count": len(rows),
                "credited_days": sum(row["credited_days"] for row in rows),
                "base_accrual_cents": sum(row["base_accrual_cents"] for row in rows),
                "revaluation_delta_cents": sum(row["revaluation_delta_cents"] for row in rows),
                "accrued_cents": sum(row["accrued_cents"] for row in rows),
                "payable_cents": sum(row["payable_cents"] for row in rows),
            }
        )

    # ---- manifest --------------------------------------------------------
    input_files = []
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            continue
        digest, size = file_digest(path)
        input_files.append({"name": name, "sha256": digest, "bytes": size})

    issue_rows = issues.sorted()
    exceptions = [dict(row) for row in issue_rows]
    for row in member_rows:
        if abs(row["payable_cents"]) >= material_cents:
            exceptions.append(
                {
                    "code": "MATERIAL_BENEFIT",
                    "record_id": row["member_id"],
                    "amount_cents": row["payable_cents"],
                }
            )
    exceptions.sort(key=lambda row: (row["code"], row["record_id"]))

    audit_rows = []
    previous = ZERO_HASH
    for row in member_rows:
        payload = (previous + canonical_json(row)).encode("utf-8")
        row_hash = hashlib.sha256(payload).hexdigest()
        audit_rows.append(
            {"member_id": row["member_id"], "previous_hash": previous, "row_hash": row_hash}
        )
        previous = row_hash

    return {
        "manifest.json": {
            "engine_version": engine_version,
            "input_files": input_files,
            "valid_member_count": len(members),
            "effective_service_count": len(effective_services),
            "accrual_atom_count": len(atoms),
        },
        "data_quality.json": {
            "input_file_count": len(input_files),
            "record_counts": record_counts,
            "issue_count": len(issue_rows),
            "issues": issue_rows,
        },
        "service_ledger.json": {
            "revision_decisions": revision_decisions,
            "effective_services": effective_services,
        },
        "accrual_ledger.json": {"atoms": atoms},
        "cola_ledger.json": {"events": cola_events},
        "member_benefits.json": {"members": member_rows},
        "plan_rollups.json": {"plans": plan_rows},
        "exception_register.json": {"exceptions": exceptions},
        "audit_trace.json": {"rows": audit_rows, "final_hash": previous},
    }


def write_report(out_dir, name, payload):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("\n")


def main(argv):
    if len(argv) != 3:
        print("usage: calculate_pension.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    reports = build(data_dir)
    for name, payload in reports.items():
        write_report(out_dir, name, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
