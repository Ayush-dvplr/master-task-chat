#!/usr/bin/env python3
"""RWRL-1.0 royalty accounting engine (Python standard library only).

Usage:
    python3 calculate_royalties.py DATA_DIR OUT_DIR

Reads the contract inputs from DATA_DIR, resolves statement revisions,
converts and rounds at the contract's boundaries only, runs the
chronological per-project recoupment waterfall, allocates distributable
cents by largest remainder, recoups participant advances, and writes the
reports defined by the contract into OUT_DIR.

All monetary arithmetic is exact integer arithmetic in minor units;
basis points are integers.  ROUND_HALF_UP is applied only where the
contract names it.  Results do not depend on JSONL row order.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

BPS = 10000
ZERO_HASH = "0" * 64

# (report key used by data_quality.record_counts, file name)
JSONL_INPUTS = (
    ("statement_revisions", "statement_revisions.jsonl"),
    ("cost_pools", "cost_pools.jsonl"),
    ("allocations", "allocations.jsonl"),
    ("advances", "advances.jsonl"),
    ("withholding_rules", "withholding_rules.jsonl"),
    ("adjustments", "adjustments.jsonl"),
    ("fx_rates", "fx_rates.jsonl"),
)

RECORD_COUNT_KEYS = tuple(key for key, _ in JSONL_INPUTS)

REPORT_NAMES = (
    "manifest.json",
    "data_quality.json",
    "statement_ledger.json",
    "waterfall_ledger.json",
    "recoupment_ledger.json",
    "participant_statements.json",
    "project_rollups.json",
    "exception_register.json",
    "audit_trace.json",
)


# --------------------------------------------------------------------------
# serialization helpers
# --------------------------------------------------------------------------

def canonical(obj) -> str:
    """Compact canonical JSON: sorted keys, ASCII escaping, no whitespace."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"))


def write_report(path, obj) -> None:
    """Sorted keys, two-space indent, ASCII escaping, one trailing newline."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(obj, sort_keys=True, indent=2,
                                ensure_ascii=True))
        handle.write("\n")


# --------------------------------------------------------------------------
# numeric helpers
# --------------------------------------------------------------------------

def half_up(numerator: int, denominator: int) -> int:
    """Exact ROUND_HALF_UP of numerator / denominator for integers."""
    if denominator == 0:
        raise ZeroDivisionError("denominator must be nonzero")
    if numerator < 0:
        return -half_up(-numerator, denominator)
    quotient, remainder = divmod(numerator, denominator)
    if 2 * remainder >= denominator:
        quotient += 1
    return quotient


def bps_apply(base_cents: int, bps: int) -> int:
    """ROUND_HALF_UP(base * bps / 10000)."""
    return half_up(base_cents * bps, BPS)


def parse_timestamp(value):
    """Parse a UTC ISO-8601 timestamp; return an aware datetime or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text[-1] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_str(value) -> bool:
    return isinstance(value, str)


# --------------------------------------------------------------------------
# input loading
# --------------------------------------------------------------------------

def read_json_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl_file(path):
    """Parse a JSONL file; blank and unparsable lines yield no row."""
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def dedupe_rows(rows):
    """Collapse byte-identical duplicate records (row order is non-semantic)."""
    seen = set()
    unique = []
    for row in rows:
        marker = canonical(row)
        if marker not in seen:
            seen.add(marker)
            unique.append(row)
    return unique


def split_key_conflicts(rows, key):
    """Split rows into (kept, dropped) on a uniqueness key.

    Every row sharing a duplicated key is dropped, because the contract
    provides no winner rule for uniqueness conflicts and row order is
    non-semantic.
    """
    indexes = defaultdict(list)
    for position, row in enumerate(rows):
        indexes[row.get(key)].append(position)
    dropped = set()
    for positions in indexes.values():
        if len(positions) > 1:
            dropped.update(positions)
    kept = [row for position, row in enumerate(rows)
            if position not in dropped]
    removed = [row for position, row in enumerate(rows)
               if position in dropped]
    return kept, removed


def row_identity(row, *keys):
    """Record identifier for a quarantined row, with graceful fallbacks."""
    for key in keys:
        value = row.get(key)
        if is_str(value) and value:
            return value
    return canonical(row)


def load_policy(data_dir):
    policy = read_json_file(os.path.join(data_dir, "policy.json"))
    periods = []
    for period in policy.get("periods") or []:
        if is_str(period) and period not in periods:
            periods.append(period)
    material = policy.get("material_cents")
    if not is_int(material) or material < 0:
        material = 0
    return {
        "engine_version": policy.get("engine_version"),
        "periods": periods,
        "settlement_currency": policy.get("settlement_currency"),
        "material_cents": material,
    }


def load_contracts(data_dir):
    """Return {project_id: distributor_fee_bps} for valid contract rows."""
    raw = read_json_file(os.path.join(data_dir, "contracts.json"))
    if not isinstance(raw, list):
        raise SystemExit("contracts.json must be a JSON array")
    fees = {}
    for row in dedupe_rows([row for row in raw if isinstance(row, dict)]):
        project_id = row.get("project_id")
        fee_bps = row.get("distributor_fee_bps")
        if not is_str(project_id) or not is_int(fee_bps):
            continue
        if not 0 <= fee_bps <= BPS:
            continue
        fees[project_id] = fee_bps
    return fees


def list_input_files(data_dir):
    """{name, sha256, bytes} for every regular input file, by name."""
    entries = []
    with os.scandir(data_dir) as scan:
        for entry in scan:
            if entry.is_file():
                entries.append(entry.name)
    reports = []
    for name in sorted(entries):
        path = os.path.join(data_dir, name)
        digest = hashlib.sha256()
        size = 0
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
        reports.append({"name": name, "sha256": digest.hexdigest(),
                        "bytes": size})
    return reports


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------

class RoyaltyEngine:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.issues = []
        self.policy = load_policy(data_dir)
        self.periods = self.policy["periods"]
        self.period_index = {period: i for i, period in enumerate(self.periods)}
        self.material_cents = self.policy["material_cents"]
        self.fee_bps = load_contracts(data_dir)
        self.project_ids = sorted(self.fee_bps)
        self.rows = {}
        for key, filename in JSONL_INPUTS:
            self.rows[key] = read_jsonl_file(os.path.join(data_dir, filename))

    # -- issue bookkeeping -------------------------------------------------
    def add_issue(self, code, record_id):
        self.issues.append({"code": code, "record_id": record_id})

    # -- reference data ----------------------------------------------------
    def build_fx_rates(self):
        """{currency: (numerator, denominator)} for valid fx rows."""
        kept, _dropped = split_key_conflicts(
            dedupe_rows(self.rows["fx_rates"]), "rate_id")
        kept, _dropped = split_key_conflicts(kept, "currency")
        rates = {}
        for row in kept:
            numerator = row.get("numerator")
            denominator = row.get("denominator")
            if not (is_str(row.get("currency")) and is_int(numerator)
                    and numerator > 0 and is_int(denominator)
                    and denominator > 0):
                continue
            rates[row["currency"]] = (numerator, denominator)
        return rates

    def build_withholding_rules(self):
        """{territory: withholding_bps} for valid withholding rows."""
        kept, _dropped = split_key_conflicts(
            dedupe_rows(self.rows["withholding_rules"]), "rule_id")
        kept, _dropped = split_key_conflicts(kept, "territory")
        rules = {}
        for row in kept:
            bps = row.get("withholding_bps")
            if not (is_str(row.get("territory")) and is_int(bps)
                    and 0 <= bps <= BPS):
                continue
            rules[row["territory"]] = bps
        return rules

    def build_cost_pools(self):
        """{project_id: [{pool_id, priority, opening_cents}]}, valid rows only."""
        kept, dropped = split_key_conflicts(
            self.rows["cost_pools"], "pool_id")
        for row in dropped:
            self.add_issue("INVALID_POOL", row_identity(row, "pool_id"))
        valid = []
        for row in kept:
            priority = row.get("priority")
            opening = row.get("opening_cents")
            if not (is_str(row.get("pool_id")) and is_str(row.get("project_id"))
                    and is_int(priority) and priority > 0
                    and is_int(opening) and opening >= 0):
                self.add_issue("INVALID_POOL", row_identity(row, "pool_id"))
                continue
            valid.append({"pool_id": row["pool_id"],
                          "project_id": row["project_id"],
                          "priority": priority,
                          "opening_cents": opening})
        # Project priorities must be unique.
        by_project = defaultdict(list)
        for row in valid:
            by_project[row["project_id"]].append(row)
        pools = {}
        for project_id, rows in by_project.items():
            by_priority = defaultdict(list)
            for row in rows:
                by_priority[row["priority"]].append(row)
            accepted = []
            for priority in sorted(by_priority):
                group = by_priority[priority]
                if len(group) > 1:
                    for row in group:
                        self.add_issue("INVALID_POOL", row["pool_id"])
                else:
                    accepted.append(group[0])
            pools[project_id] = sorted(
                accepted, key=lambda row: (row["priority"], row["pool_id"]))
        return pools

    def build_allocations(self):
        """Return ({project_id: [participant rows]}, eligible project set)."""
        kept, dropped = split_key_conflicts(
            self.rows["allocations"], "allocation_id")
        for row in dropped:
            self.add_issue("INVALID_ALLOCATION",
                           row_identity(row, "allocation_id"))
        valid = []
        for row in kept:
            share = row.get("share_bps")
            if not (is_str(row.get("allocation_id"))
                    and is_str(row.get("project_id"))
                    and is_str(row.get("participant_id"))
                    and is_int(share) and 0 <= share <= BPS):
                self.add_issue("INVALID_ALLOCATION",
                               row_identity(row, "allocation_id"))
                continue
            valid.append({"allocation_id": row["allocation_id"],
                          "project_id": row["project_id"],
                          "participant_id": row["participant_id"],
                          "share_bps": share})
        # Project universe is every project carrying an allocation row, so a
        # project whose rows were all quarantined still reports its
        # post-quarantine sum.
        projects_with_rows = {row["project_id"] for row in valid}
        for row in self.rows["allocations"]:
            if is_str(row.get("project_id")):
                projects_with_rows.add(row["project_id"])
        by_project = defaultdict(list)
        for row in valid:
            by_project[row["project_id"]].append(row)
        allocations = {}
        eligible = set()
        for project_id in sorted(projects_with_rows):
            rows = by_project.get(project_id, [])
            unique = {}
            for row in rows:
                unique.setdefault(row["participant_id"], row)
            ordered = sorted(unique.values(),
                             key=lambda row: row["participant_id"])
            allocations[project_id] = ordered
            if sum(row["share_bps"] for row in ordered) == BPS:
                eligible.add(project_id)
            else:
                self.add_issue("INVALID_ALLOCATION_TOTAL", project_id)
        return allocations, eligible

    def build_advances(self, allocations):
        """{(project_id, participant_id): [advance rows]} in visit order."""
        kept, dropped = split_key_conflicts(
            self.rows["advances"], "advance_id")
        for row in dropped:
            self.add_issue("INVALID_ADVANCE", row_identity(row, "advance_id"))
        participants = {project_id: {row["participant_id"]
                                     for row in rows}
                         for project_id, rows in allocations.items()}
        valid_by_key = {}
        for row in kept:
            priority = row.get("priority")
            opening = row.get("opening_cents")
            if not (is_str(row.get("advance_id"))
                    and is_str(row.get("project_id"))
                    and is_str(row.get("participant_id"))
                    and is_int(priority) and priority > 0
                    and is_int(opening) and opening >= 0):
                self.add_issue("INVALID_ADVANCE",
                               row_identity(row, "advance_id"))
                continue
            project_id = row["project_id"]
            participant_id = row["participant_id"]
            if participant_id not in participants.get(project_id, ()):
                self.add_issue("INVALID_ADVANCE", row["advance_id"])
                continue
            valid_by_key.setdefault((project_id, participant_id), []).append(
                {"advance_id": row["advance_id"], "priority": priority,
                 "opening_cents": opening})
        advances = {}
        for key, rows in valid_by_key.items():
            by_priority = defaultdict(list)
            for row in rows:
                by_priority[row["priority"]].append(row)
            accepted = []
            for priority in sorted(by_priority):
                group = by_priority[priority]
                if len(group) > 1:
                    for row in group:
                        self.add_issue("INVALID_ADVANCE", row["advance_id"])
                else:
                    accepted.append(group[0])
            advances[key] = sorted(
                accepted, key=lambda row: (row["priority"], row["advance_id"]))
        return advances

    def build_adjustments(self, allocations):
        """{(project_id, period, participant_id): summed cents}."""
        kept, dropped = split_key_conflicts(
            self.rows["adjustments"], "adjustment_id")
        for row in dropped:
            self.add_issue("INVALID_ADJUSTMENT",
                           row_identity(row, "adjustment_id"))
        participants = {project_id: {row["participant_id"]
                                     for row in rows}
                         for project_id, rows in allocations.items()}
        totals = defaultdict(int)
        for row in kept:
            project_id = row.get("project_id")
            period = row.get("period")
            participant_id = row.get("participant_id")
            amount = row.get("amount_cents")
            if not (is_str(project_id) and project_id in self.fee_bps
                    and is_str(period) and period in self.period_index
                    and is_str(participant_id)
                    and participant_id in participants.get(project_id, ())
                    and is_int(amount)):
                self.add_issue("INVALID_ADJUSTMENT",
                               row_identity(row, "adjustment_id"))
                continue
            totals[(project_id, period, participant_id)] += amount
        return dict(totals)

    # -- statement resolution ----------------------------------------------
    def resolve_statements(self, rates, withholding_rules):
        """Return (decisions, effective statements)."""
        parsed = []
        for row in dedupe_rows(self.rows["statement_revisions"]):
            statement_id = row.get("statement_id")
            record_id = row.get("record_id")
            revision = row.get("revision")
            status = row.get("status")
            timestamp = parse_timestamp(row.get("recorded_at"))
            if not (is_str(statement_id) and statement_id
                    and is_str(record_id) and record_id
                    and is_int(revision) and is_str(status)
                    and timestamp is not None):
                self.add_issue("INVALID_STATEMENT",
                               row_identity(row, "statement_id", "record_id"))
                continue
            parsed.append({
                "row": row,
                "statement_id": statement_id,
                "record_id": record_id,
                "revision": revision,
                "status": status,
                "timestamp": timestamp,
                "canonical": canonical(row),
            })

        groups = defaultdict(list)
        for entry in parsed:
            groups[entry["statement_id"]].append(entry)

        decisions = []
        effective = []
        for statement_id in sorted(groups):
            group = groups[statement_id]
            winner = max(group, key=lambda entry: (
                entry["revision"], entry["timestamp"], entry["record_id"],
                entry["canonical"]))
            peers = [entry for entry in group
                     if entry["revision"] == winner["revision"]
                     and entry["timestamp"] == winner["timestamp"]]
            payloads = {canonical({key: value for key, value
                                   in entry["row"].items()
                                   if key != "record_id"})
                        for entry in peers}
            if len(payloads) > 1:
                self.add_issue("REVISION_TIE_CONFLICT", statement_id)
            decisions.append({
                "statement_id": statement_id,
                "winner_record_id": winner["record_id"],
                "discarded_record_ids": sorted(
                    entry["record_id"] for entry in group
                    if entry is not winner),
            })
            statement = self.validate_statement(winner, rates,
                                               withholding_rules)
            if statement is not None:
                effective.append(statement)
        return decisions, effective

    def validate_statement(self, entry, rates, withholding_rules):
        """Return the computed effective statement, or None to quarantine."""
        row = entry["row"]
        if entry["status"] != "active":
            return None
        project_id = row.get("project_id")
        period = row.get("period")
        territory = row.get("territory")
        currency = row.get("currency")
        amount_minor = row.get("amount_minor")
        valid = (is_str(project_id) and project_id in self.fee_bps
                 and is_str(period) and period in self.period_index
                 and is_str(territory) and territory in withholding_rules
                 and is_str(currency) and currency in rates
                 and is_int(amount_minor) and amount_minor >= 0)
        if not valid:
            self.add_issue("INVALID_STATEMENT", entry["statement_id"])
            return None
        numerator, denominator = rates[currency]
        gross = half_up(amount_minor * numerator, denominator)
        withholding = bps_apply(gross, withholding_rules[territory])
        fee_base = gross - withholding
        fee = bps_apply(fee_base, self.fee_bps[project_id])
        return {
            "statement_id": entry["statement_id"],
            "project_id": project_id,
            "period": period,
            "territory": territory,
            "currency": currency,
            "amount_minor": amount_minor,
            "gross_cents": gross,
            "withholding_cents": withholding,
            "distributor_fee_cents": fee,
            "net_receipts_cents": gross - withholding - fee,
        }

    # -- allocation --------------------------------------------------------
    @staticmethod
    def largest_remainder(distributable, shares):
        """Exact shares by integer floor plus largest-remainder residuals."""
        floors = {}
        remainders = {}
        for participant_id, share_bps in shares.items():
            exact = distributable * share_bps
            floors[participant_id] = exact // BPS
            remainders[participant_id] = exact % BPS
        residual = distributable - sum(floors.values())
        order = sorted(remainders,
                       key=lambda participant_id: (-remainders[participant_id],
                                                   participant_id))
        for participant_id in order[:residual]:
            floors[participant_id] += 1
        return floors

    # -- main computation --------------------------------------------------
    def run(self):
        rates = self.build_fx_rates()
        withholding_rules = self.build_withholding_rules()
        pools = self.build_cost_pools()
        allocations, eligible = self.build_allocations()
        advances = self.build_advances(allocations)
        adjustments = self.build_adjustments(allocations)
        decisions, effective = self.resolve_statements(
            rates, withholding_rules)

        # Project-period statement aggregation.
        aggregate_keys = ("gross_cents", "withholding_cents",
                          "distributor_fee_cents", "net_receipts_cents")
        aggregates = defaultdict(lambda: {key: 0 for key in aggregate_keys})
        for statement in effective:
            if statement["project_id"] not in eligible:
                continue
            bucket = aggregates[(statement["project_id"],
                                 statement["period"])]
            for key in aggregate_keys:
                bucket[key] += statement[key]

        pool_balances = {
            project_id: {row["pool_id"]: row["opening_cents"]
                         for row in rows}
            for project_id, rows in pools.items()}
        advance_balances = {
            key: {row["advance_id"]: row["opening_cents"] for row in rows}
            for key, rows in advances.items()}

        waterfall_rows = []
        pool_rows = []
        advance_rows = []
        participant_rows = []
        rollups = {}

        for project_id in self.project_ids:
            project_pools = pools.get(project_id, [])
            project_allocations = allocations.get(project_id, [])
            shares = {row["participant_id"]: row["share_bps"]
                      for row in project_allocations}
            participant_ids = [row["participant_id"]
                                for row in project_allocations]
            rollup = {"gross_cents": 0, "withholding_cents": 0,
                      "distributor_fee_cents": 0, "net_receipts_cents": 0,
                      "pool_recouped_cents": 0, "distributable_cents": 0,
                      "advance_recouped_cents": 0, "adjustment_cents": 0,
                      "payable_cents": 0}

            for period in self.periods:
                bucket = aggregates.get((project_id, period))
                gross = bucket["gross_cents"] if bucket else 0
                withholding = bucket["withholding_cents"] if bucket else 0
                fee = bucket["distributor_fee_cents"] if bucket else 0
                net = bucket["net_receipts_cents"] if bucket else 0

                remaining = net
                period_pool_recouped = 0
                for pool in project_pools:
                    pool_id = pool["pool_id"]
                    opening = pool_balances[project_id][pool_id]
                    recouped = min(opening, remaining)
                    closing = opening - recouped
                    remaining -= recouped
                    period_pool_recouped += recouped
                    pool_balances[project_id][pool_id] = closing
                    pool_rows.append({
                        "project_id": project_id,
                        "period": period,
                        "pool_id": pool_id,
                        "priority": pool["priority"],
                        "opening_balance_cents": opening,
                        "recouped_cents": recouped,
                        "closing_balance_cents": closing,
                    })
                distributable = remaining

                waterfall_rows.append({
                    "project_id": project_id,
                    "period": period,
                    "gross_cents": gross,
                    "withholding_cents": withholding,
                    "distributor_fee_cents": fee,
                    "net_receipts_cents": net,
                    "pool_recouped_cents": period_pool_recouped,
                    "distributable_cents": distributable,
                })

                if distributable > 0 and shares:
                    gross_shares = self.largest_remainder(distributable,
                                                          shares)
                else:
                    gross_shares = {participant_id: 0
                                    for participant_id in participant_ids}

                for participant_id in participant_ids:
                    gross_share = gross_shares[participant_id]
                    remaining_share = gross_share
                    advance_recouped = 0
                    participant_advances = advances.get(
                        (project_id, participant_id), [])
                    for advance in participant_advances:
                        advance_id = advance["advance_id"]
                        balance_key = (project_id, participant_id)
                        opening = advance_balances[balance_key][advance_id]
                        recouped = min(opening, remaining_share)
                        closing = opening - recouped
                        remaining_share -= recouped
                        advance_recouped += recouped
                        advance_balances[balance_key][advance_id] = closing
                        advance_rows.append({
                            "project_id": project_id,
                            "period": period,
                            "participant_id": participant_id,
                            "advance_id": advance_id,
                            "priority": advance["priority"],
                            "opening_balance_cents": opening,
                            "recouped_cents": recouped,
                            "closing_balance_cents": closing,
                        })
                    adjustment_cents = adjustments.get(
                        (project_id, period, participant_id), 0)
                    payable_before = remaining_share
                    payable = payable_before + adjustment_cents
                    participant_rows.append({
                        "project_id": project_id,
                        "period": period,
                        "participant_id": participant_id,
                        "share_bps": shares[participant_id],
                        "gross_share_cents": gross_share,
                        "advance_recouped_cents": advance_recouped,
                        "payable_before_adjustment_cents": payable_before,
                        "adjustment_cents": adjustment_cents,
                        "payable_cents": payable,
                    })
                    rollup["advance_recouped_cents"] += advance_recouped
                    rollup["adjustment_cents"] += adjustment_cents
                    rollup["payable_cents"] += payable

                rollup["gross_cents"] += gross
                rollup["withholding_cents"] += withholding
                rollup["distributor_fee_cents"] += fee
                rollup["net_receipts_cents"] += net
                rollup["pool_recouped_cents"] += period_pool_recouped
                rollup["distributable_cents"] += distributable

            rollup_row = {"project_id": project_id}
            rollup_row.update(rollup)
            rollups[project_id] = rollup_row

        effective.sort(key=lambda row: (row["project_id"], row["period"],
                                        row["statement_id"]))

        audit_rows = []
        previous_hash = ZERO_HASH
        for statement in participant_rows:
            row_hash = hashlib.sha256(
                (previous_hash + canonical(statement)).encode("utf-8")
            ).hexdigest()
            audit_rows.append({
                "project_id": statement["project_id"],
                "period": statement["period"],
                "participant_id": statement["participant_id"],
                "previous_hash": previous_hash,
                "row_hash": row_hash,
            })
            previous_hash = row_hash

        issues = sorted(self.issues,
                        key=lambda issue: (issue["code"], issue["record_id"]))
        exceptions = [dict(issue) for issue in issues]
        for statement in participant_rows:
            payable = statement["payable_cents"]
            if abs(payable) >= self.material_cents:
                exceptions.append({
                    "code": "MATERIAL_PAYMENT",
                    "record_id": "%s:%s:%s" % (statement["project_id"],
                                               statement["period"],
                                               statement["participant_id"]),
                    "amount_cents": payable,
                })
        exceptions.sort(key=lambda item: (item["code"], item["record_id"]))

        input_files = list_input_files(self.data_dir)
        return {
            "manifest.json": {
                "engine_version": self.policy["engine_version"],
                "input_files": input_files,
                "effective_statement_count": len(effective),
                "waterfall_period_count": len(waterfall_rows),
                "participant_statement_count": len(participant_rows),
            },
            "data_quality.json": {
                "input_file_count": len(input_files),
                "record_counts": {key: len(self.rows[key])
                                  for key in RECORD_COUNT_KEYS},
                "issue_count": len(issues),
                "issues": issues,
            },
            "statement_ledger.json": {
                "revision_decisions": decisions,
                "effective_statements": effective,
            },
            "waterfall_ledger.json": {"periods": waterfall_rows},
            "recoupment_ledger.json": {
                "project_pools": pool_rows,
                "participant_advances": advance_rows,
            },
            "participant_statements.json": {"statements": participant_rows},
            "project_rollups.json": {
                "projects": [rollups[project_id]
                              for project_id in sorted(rollups)]},
            "exception_register.json": {"exceptions": exceptions},
            "audit_trace.json": {
                "rows": audit_rows,
                "final_hash": previous_hash,
            },
        }


def compute(data_dir):
    return RoyaltyEngine(data_dir).run()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="RWRL-1.0 royalty accounting engine")
    parser.add_argument("data_dir", help="directory holding the input extract")
    parser.add_argument("out_dir", help="directory for the reports")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.data_dir):
        parser.error("data directory not found: %s" % args.data_dir)
    if (os.path.realpath(args.data_dir)
            == os.path.realpath(args.out_dir)):
        parser.error("data directory and output directory must differ")
    reports = compute(args.data_dir)
    os.makedirs(args.out_dir, exist_ok=True)
    for name in REPORT_NAMES:
        write_report(os.path.join(args.out_dir, name), reports[name])
    return 0


if __name__ == "__main__":
    sys.exit(main())
