#!/usr/bin/env python3
"""75407a55-6665-505e-95d8-5ff9bdb3384f engine (RWRL-1.0).

Usage: python3 calculate_royalties.py DATA_DIR OUT_DIR
"""

import hashlib
import json
import os
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext

ZERO_HASH = "0" * 64


# ---------------------------------------------------------------- primitives

def round_half_up(numerator, denominator):
    """Exact ROUND_HALF_UP of numerator/denominator to an integer."""
    with localcontext() as ctx:
        ctx.prec = 80
        value = Decimal(numerator) / Decimal(denominator)
        return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_report(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2, ensure_ascii=True)
        handle.write("\n")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_timestamp(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


# ---------------------------------------------------------------- validation

class Issues:
    def __init__(self):
        self.rows = []

    def add(self, code, record_id):
        self.rows.append({"code": code, "record_id": record_id})

    def sorted_rows(self):
        return sorted(self.rows, key=lambda row: (row["code"], row["record_id"]))


def duplicate_keys(rows, key):
    counts = {}
    for row in rows:
        counts[row.get(key)] = counts.get(row.get(key), 0) + 1
    return {value for value, count in counts.items() if count > 1}


# ------------------------------------------------------------------- loading

def resolve_revisions(records, issues):
    """Return (decisions, winners) for every statement_id."""
    grouped = {}
    for row in records:
        grouped.setdefault(row["statement_id"], []).append(row)

    decisions = []
    winners = {}
    for statement_id in sorted(grouped):
        peers = grouped[statement_id]
        keyed = [
            ((row["revision"], parse_timestamp(row["recorded_at"]), row["record_id"]), row)
            for row in peers
        ]
        keyed.sort(key=lambda item: item[0])
        winner_key, winner = keyed[-1]

        tied = [
            row
            for key, row in keyed
            if key[0] == winner_key[0] and key[1] == winner_key[1]
        ]
        if len(tied) > 1:
            payloads = {
                canonical({k: v for k, v in row.items() if k != "record_id"})
                for row in tied
            }
            if len(payloads) > 1:
                issues.add("REVISION_TIE_CONFLICT", statement_id)

        decisions.append(
            {
                "statement_id": statement_id,
                "winner_record_id": winner["record_id"],
                "discarded_record_ids": sorted(
                    row["record_id"]
                    for row in peers
                    if row["record_id"] != winner["record_id"]
                ),
            }
        )
        winners[statement_id] = winner
    return decisions, winners


def validate_pools(rows, projects, issues):
    dup_ids = duplicate_keys(rows, "pool_id")
    priority_counts = {}
    for row in rows:
        key = (row.get("project_id"), row.get("priority"))
        priority_counts[key] = priority_counts.get(key, 0) + 1

    valid = []
    for row in rows:
        key = (row.get("project_id"), row.get("priority"))
        ok = (
            row.get("pool_id") not in dup_ids
            and row.get("project_id") in projects
            and is_int(row.get("priority"))
            and is_int(row.get("opening_cents"))
            and row.get("priority") > 0
            and row.get("opening_cents") >= 0
            and priority_counts[key] == 1
        )
        if ok:
            valid.append(row)
        else:
            issues.add("INVALID_POOL", row.get("pool_id"))
    return valid


def validate_allocations(rows, projects, issues):
    dup_ids = duplicate_keys(rows, "allocation_id")
    pair_counts = {}
    for row in rows:
        key = (row.get("project_id"), row.get("participant_id"))
        pair_counts[key] = pair_counts.get(key, 0) + 1

    valid = []
    for row in rows:
        key = (row.get("project_id"), row.get("participant_id"))
        share = row.get("share_bps")
        ok = (
            row.get("allocation_id") not in dup_ids
            and row.get("project_id") in projects
            and isinstance(row.get("participant_id"), str)
            and is_int(share)
            and 0 <= share <= 10000
            and pair_counts[key] == 1
        )
        if ok:
            valid.append(row)
        else:
            issues.add("INVALID_ALLOCATION", row.get("allocation_id"))
    return valid


def validate_advances(rows, allocations_by_project, issues):
    dup_ids = duplicate_keys(rows, "advance_id")
    priority_counts = {}
    for row in rows:
        key = (row.get("project_id"), row.get("participant_id"), row.get("priority"))
        priority_counts[key] = priority_counts.get(key, 0) + 1

    valid = []
    for row in rows:
        project = row.get("project_id")
        participant = row.get("participant_id")
        key = (project, participant, row.get("priority"))
        ok = (
            row.get("advance_id") not in dup_ids
            and participant in allocations_by_project.get(project, {})
            and is_int(row.get("priority"))
            and is_int(row.get("opening_cents"))
            and row.get("priority") > 0
            and row.get("opening_cents") >= 0
            and priority_counts[key] == 1
        )
        if ok:
            valid.append(row)
        else:
            issues.add("INVALID_ADVANCE", row.get("advance_id"))
    return valid


def validate_adjustments(rows, projects, period_index, allocations_by_project, issues):
    dup_ids = duplicate_keys(rows, "adjustment_id")
    valid = []
    for row in rows:
        project = row.get("project_id")
        ok = (
            row.get("adjustment_id") not in dup_ids
            and project in projects
            and row.get("period") in period_index
            and row.get("participant_id") in allocations_by_project.get(project, {})
            and is_int(row.get("amount_cents"))
        )
        if ok:
            valid.append(row)
        else:
            issues.add("INVALID_ADJUSTMENT", row.get("adjustment_id"))
    return valid


# ------------------------------------------------------------------ waterfall

def largest_remainder(distributable, shares):
    """shares: sorted list of (participant_id, share_bps)."""
    result = {}
    remainders = []
    assigned = 0
    for participant_id, share_bps in shares:
        exact = distributable * share_bps
        floor_value = exact // 10000
        result[participant_id] = floor_value
        assigned += floor_value
        remainders.append((exact % 10000, participant_id))

    remainders.sort(key=lambda item: (-item[0], item[1]))
    for index in range(distributable - assigned):
        result[remainders[index][1]] += 1
    return result


def main(data_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    policy = read_json(os.path.join(data_dir, "policy.json"))
    contracts = read_json(os.path.join(data_dir, "contracts.json"))
    statement_rows = read_jsonl(os.path.join(data_dir, "statement_revisions.jsonl"))
    fx_rows = read_jsonl(os.path.join(data_dir, "fx_rates.jsonl"))
    withholding_rows = read_jsonl(os.path.join(data_dir, "withholding_rules.jsonl"))
    pool_rows = read_jsonl(os.path.join(data_dir, "cost_pools.jsonl"))
    allocation_rows = read_jsonl(os.path.join(data_dir, "allocations.jsonl"))
    advance_rows = read_jsonl(os.path.join(data_dir, "advances.jsonl"))
    adjustment_rows = read_jsonl(os.path.join(data_dir, "adjustments.jsonl"))

    periods = list(policy["periods"])
    period_index = {period: index for index, period in enumerate(periods)}
    projects = {row["project_id"]: row for row in contracts}
    fx_by_currency = {row["currency"]: row for row in fx_rows}
    withholding_by_territory = {row["territory"]: row for row in withholding_rows}

    issues = Issues()

    decisions, winners = resolve_revisions(statement_rows, issues)
    pools = validate_pools(pool_rows, projects, issues)
    allocations = validate_allocations(allocation_rows, projects, issues)

    allocations_by_project = {}
    for row in allocations:
        allocations_by_project.setdefault(row["project_id"], {})[
            row["participant_id"]
        ] = row["share_bps"]

    excluded_projects = set()
    for project_id in sorted(projects):
        if sum(allocations_by_project.get(project_id, {}).values()) != 10000:
            issues.add("INVALID_ALLOCATION_TOTAL", project_id)
            excluded_projects.add(project_id)

    advances = validate_advances(advance_rows, allocations_by_project, issues)
    adjustments = validate_adjustments(
        adjustment_rows, projects, period_index, allocations_by_project, issues
    )

    # ---- effective statements
    effective = []
    for statement_id in sorted(winners):
        winner = winners[statement_id]
        if winner["status"] != "active":
            continue
        project_id = winner["project_id"]
        territory = winner["territory"]
        currency = winner["currency"]
        amount = winner["amount_minor"]
        if not (
            project_id in projects
            and winner["period"] in period_index
            and territory in withholding_by_territory
            and currency in fx_by_currency
            and is_int(amount)
            and amount >= 0
        ):
            issues.add("INVALID_STATEMENT", winner["record_id"])
            continue

        rate = fx_by_currency[currency]
        gross = round_half_up(amount * rate["numerator"], rate["denominator"])
        withholding = round_half_up(
            gross * withholding_by_territory[territory]["withholding_bps"], 10000
        )
        fee_base = gross - withholding
        fee = round_half_up(fee_base * projects[project_id]["distributor_fee_bps"], 10000)
        effective.append(
            {
                "statement_id": statement_id,
                "project_id": project_id,
                "period": winner["period"],
                "territory": territory,
                "currency": currency,
                "amount_minor": amount,
                "gross_cents": gross,
                "withholding_cents": withholding,
                "distributor_fee_cents": fee,
                "net_receipts_cents": gross - withholding - fee,
            }
        )

    effective.sort(key=lambda row: (row["project_id"], row["period"], row["statement_id"]))

    # ---- indexes for the waterfall
    statements_by_key = {}
    for row in effective:
        statements_by_key.setdefault((row["project_id"], row["period"]), []).append(row)

    pools_by_project = {}
    for row in pools:
        pools_by_project.setdefault(row["project_id"], []).append(row)

    advances_by_key = {}
    for row in advances:
        advances_by_key.setdefault((row["project_id"], row["participant_id"]), []).append(row)

    adjustments_by_key = {}
    for row in adjustments:
        key = (row["project_id"], row["period"], row["participant_id"])
        adjustments_by_key[key] = adjustments_by_key.get(key, 0) + row["amount_cents"]

    waterfall = []
    pool_ledger = []
    advance_ledger = []
    participant_statements = []

    waterfall_projects = [p for p in sorted(projects) if p not in excluded_projects]

    for project_id in waterfall_projects:
        project_pools = sorted(
            pools_by_project.get(project_id, []),
            key=lambda row: (row["priority"], row["pool_id"]),
        )
        pool_balances = {row["pool_id"]: row["opening_cents"] for row in project_pools}

        shares = sorted(allocations_by_project.get(project_id, {}).items())
        advance_balances = {}
        participant_advances = {}
        for participant_id, _ in shares:
            rows = sorted(
                advances_by_key.get((project_id, participant_id), []),
                key=lambda row: (row["priority"], row["advance_id"]),
            )
            participant_advances[participant_id] = rows
            for row in rows:
                advance_balances[row["advance_id"]] = row["opening_cents"]

        for period in periods:
            period_statements = statements_by_key.get((project_id, period), [])
            gross = sum(row["gross_cents"] for row in period_statements)
            withholding = sum(row["withholding_cents"] for row in period_statements)
            fee = sum(row["distributor_fee_cents"] for row in period_statements)
            net = sum(row["net_receipts_cents"] for row in period_statements)

            remaining = net
            pool_recouped_total = 0
            for pool in project_pools:
                opening = pool_balances[pool["pool_id"]]
                recouped = min(opening, remaining)
                closing = opening - recouped
                remaining -= recouped
                pool_balances[pool["pool_id"]] = closing
                pool_recouped_total += recouped
                pool_ledger.append(
                    {
                        "project_id": project_id,
                        "period": period,
                        "pool_id": pool["pool_id"],
                        "priority": pool["priority"],
                        "opening_balance_cents": opening,
                        "recouped_cents": recouped,
                        "closing_balance_cents": closing,
                    }
                )

            distributable = remaining
            waterfall.append(
                {
                    "project_id": project_id,
                    "period": period,
                    "gross_cents": gross,
                    "withholding_cents": withholding,
                    "distributor_fee_cents": fee,
                    "net_receipts_cents": net,
                    "pool_recouped_cents": pool_recouped_total,
                    "distributable_cents": distributable,
                }
            )

            if distributable > 0:
                gross_shares = largest_remainder(distributable, shares)
            else:
                gross_shares = {participant_id: 0 for participant_id, _ in shares}

            for participant_id, share_bps in shares:
                remaining_share = gross_shares[participant_id]
                gross_share = remaining_share
                advance_recouped = 0
                for advance in participant_advances[participant_id]:
                    opening = advance_balances[advance["advance_id"]]
                    recouped = min(opening, remaining_share)
                    closing = opening - recouped
                    remaining_share -= recouped
                    advance_balances[advance["advance_id"]] = closing
                    advance_recouped += recouped
                    advance_ledger.append(
                        {
                            "project_id": project_id,
                            "period": period,
                            "participant_id": participant_id,
                            "advance_id": advance["advance_id"],
                            "priority": advance["priority"],
                            "opening_balance_cents": opening,
                            "recouped_cents": recouped,
                            "closing_balance_cents": closing,
                        }
                    )

                adjustment = adjustments_by_key.get((project_id, period, participant_id), 0)
                participant_statements.append(
                    {
                        "project_id": project_id,
                        "period": period,
                        "participant_id": participant_id,
                        "share_bps": share_bps,
                        "gross_share_cents": gross_share,
                        "advance_recouped_cents": advance_recouped,
                        "payable_before_adjustment_cents": remaining_share,
                        "adjustment_cents": adjustment,
                        "payable_cents": remaining_share + adjustment,
                    }
                )

    # ---- rollups
    rollups = []
    for project_id in waterfall_projects:
        period_rows = [row for row in waterfall if row["project_id"] == project_id]
        participant_rows = [
            row for row in participant_statements if row["project_id"] == project_id
        ]
        rollups.append(
            {
                "project_id": project_id,
                "gross_cents": sum(row["gross_cents"] for row in period_rows),
                "withholding_cents": sum(row["withholding_cents"] for row in period_rows),
                "distributor_fee_cents": sum(
                    row["distributor_fee_cents"] for row in period_rows
                ),
                "net_receipts_cents": sum(row["net_receipts_cents"] for row in period_rows),
                "pool_recouped_cents": sum(row["pool_recouped_cents"] for row in period_rows),
                "distributable_cents": sum(row["distributable_cents"] for row in period_rows),
                "advance_recouped_cents": sum(
                    row["advance_recouped_cents"] for row in participant_rows
                ),
                "adjustment_cents": sum(row["adjustment_cents"] for row in participant_rows),
                "payable_cents": sum(row["payable_cents"] for row in participant_rows),
            }
        )

    # ---- audit trace
    audit_rows = []
    previous_hash = ZERO_HASH
    for row in participant_statements:
        row_hash = hashlib.sha256(
            (previous_hash + canonical(row)).encode("utf-8")
        ).hexdigest()
        audit_rows.append(
            {
                "project_id": row["project_id"],
                "period": row["period"],
                "participant_id": row["participant_id"],
                "previous_hash": previous_hash,
                "row_hash": row_hash,
            }
        )
        previous_hash = row_hash
    final_hash = audit_rows[-1]["row_hash"] if audit_rows else ZERO_HASH

    # ---- exceptions
    quality_issues = issues.sorted_rows()
    exceptions = [dict(row) for row in quality_issues]
    material = policy["material_cents"]
    for row in participant_statements:
        if abs(row["payable_cents"]) >= material:
            exceptions.append(
                {
                    "code": "MATERIAL_PAYMENT",
                    "record_id": "%s:%s:%s"
                    % (row["project_id"], row["period"], row["participant_id"]),
                    "amount_cents": row["payable_cents"],
                }
            )
    exceptions.sort(key=lambda row: (row["code"], row["record_id"]))

    # ---- manifest
    input_files = []
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if os.path.isfile(path):
            input_files.append(
                {"name": name, "sha256": sha256_file(path), "bytes": os.path.getsize(path)}
            )

    write_report(
        out_dir,
        "manifest.json",
        {
            "engine_version": policy["engine_version"],
            "input_files": input_files,
            "effective_statement_count": len(effective),
            "waterfall_period_count": len(waterfall),
            "participant_statement_count": len(participant_statements),
        },
    )

    write_report(
        out_dir,
        "data_quality.json",
        {
            "input_file_count": len(input_files),
            "record_counts": {
                "statement_revisions": len(statement_rows),
                "cost_pools": len(pool_rows),
                "allocations": len(allocation_rows),
                "advances": len(advance_rows),
                "withholding_rules": len(withholding_rows),
                "adjustments": len(adjustment_rows),
                "fx_rates": len(fx_rows),
            },
            "issue_count": len(quality_issues),
            "issues": quality_issues,
        },
    )

    write_report(
        out_dir,
        "statement_ledger.json",
        {"revision_decisions": decisions, "effective_statements": effective},
    )

    write_report(out_dir, "waterfall_ledger.json", {"periods": waterfall})

    write_report(
        out_dir,
        "recoupment_ledger.json",
        {"project_pools": pool_ledger, "participant_advances": advance_ledger},
    )

    write_report(out_dir, "participant_statements.json", {"statements": participant_statements})
    write_report(out_dir, "project_rollups.json", {"projects": rollups})
    write_report(out_dir, "exception_register.json", {"exceptions": exceptions})
    write_report(out_dir, "audit_trace.json", {"rows": audit_rows, "final_hash": final_hash})


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write("usage: calculate_royalties.py DATA_DIR OUT_DIR\n")
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
