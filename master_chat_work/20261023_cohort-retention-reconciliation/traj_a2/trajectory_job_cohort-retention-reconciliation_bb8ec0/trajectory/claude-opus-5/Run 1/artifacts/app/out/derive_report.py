#!/usr/bin/env python3
"""Cohort retention study: derive every report from a flat-file extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import json
import os
import re
import sys
from datetime import date
from fractions import Fraction

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DIGITS_RE = re.compile(r"^[0-9]+$")


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def parse_date(text):
    if text is None or not DATE_RE.match(text):
        return None
    year, month, day = (int(part) for part in text.split("-"))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def rate(numerator, denominator):
    """Exact reduced fraction as a string; a zero denominator renders as "0"."""
    if denominator == 0:
        return "0"
    value = Fraction(numerator, denominator)
    if value.denominator == 1:
        return str(value.numerator)
    return "%d/%d" % (value.numerator, value.denominator)


def write_json(out_dir, name, payload):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")


class Extract:
    def __init__(self, data_dir):
        self.events = read_rows(os.path.join(data_dir, "events.csv"))
        self.accounts = {}
        for row in read_rows(os.path.join(data_dir, "accounts.csv")):
            self.accounts[row["account_id"]] = row
        self.merge_row_count = 0
        self.merges = []
        for index, row in enumerate(
            read_rows(os.path.join(data_dir, "account_merges.csv"))
        ):
            self.merge_row_count += 1
            self.merges.append(
                (
                    row["from_account_id"],
                    row["to_account_id"],
                    parse_date(row["effective_from"]),
                    index,
                )
            )
        self.exclusions = []
        for row in read_rows(os.path.join(data_dir, "exclusions.csv")):
            if row["account_id"] not in self.exclusions:
                self.exclusions.append(row["account_id"])
        self.periods = []
        for row in read_rows(os.path.join(data_dir, "period_calendar.csv")):
            self.periods.append(
                (
                    row["period"],
                    parse_date(row["start_date"]),
                    parse_date(row["end_date"]),
                )
            )
        self.periods.sort(key=lambda item: item[1])
        self.period_names = [item[0] for item in self.periods]
        self.period_index = {
            name: position for position, name in enumerate(self.period_names)
        }
        self.plan_history = []
        for index, row in enumerate(
            read_rows(os.path.join(data_dir, "plan_history.csv"))
        ):
            self.plan_history.append(
                (
                    row["account_id"],
                    row["plan"],
                    parse_date(row["effective_from"]),
                    index,
                )
            )
        self.plan_weights = read_json(os.path.join(data_dir, "plan_weights.json"))
        self.rules = read_json(os.path.join(data_dir, "qualifying_rules.json"))
        self.config = read_json(os.path.join(data_dir, "study_config.json"))

    def period_of(self, day):
        for name, start, end in self.periods:
            if start <= day <= end:
                return name
        return None

    def resolve_account(self, account_id, day):
        """Fold an account onto its surviving account for a given date."""
        current = account_id
        seen = {current}
        while True:
            applicable = [
                merge
                for merge in self.merges
                if merge[0] == current and merge[2] is not None and merge[2] <= day
            ]
            if not applicable:
                return current
            current = max(applicable, key=lambda merge: (merge[2], merge[3]))[1]
            if current in seen:
                return current
            seen.add(current)

    def plan_in_force(self, account_id, day):
        applicable = [
            row
            for row in self.plan_history
            if row[0] == account_id and row[2] is not None and row[2] <= day
        ]
        if applicable:
            return max(applicable, key=lambda row: (row[2], row[3]))[1]
        return self.accounts[account_id]["plan"]

    def weight_of(self, account_id, day):
        return int(self.plan_weights[self.plan_in_force(account_id, day)])


def is_malformed(row):
    return parse_date(row.get("event_date")) is None or not DIGITS_RE.match(
        row.get("value_cents") or ""
    )


def clean_events(extract):
    """Apply the cleaning steps in contract order, counting each removal once."""
    counts = {
        "malformed": 0,
        "out_of_calendar": 0,
        "duplicate": 0,
        "excluded": 0,
        "unknown_account": 0,
    }

    stage = []
    for row in extract.events:
        if is_malformed(row):
            counts["malformed"] += 1
            continue
        stage.append((row, parse_date(row["event_date"]), int(row["value_cents"])))

    survivors = []
    for row, day, value in stage:
        period = extract.period_of(day)
        if period is None:
            counts["out_of_calendar"] += 1
            continue
        survivors.append((row, day, value, period))

    stage, seen = [], set()
    for row, day, value, period in survivors:
        key = (row["account_id"], row["event_date"], row["event_type"])
        if key in seen:
            counts["duplicate"] += 1
            continue
        seen.add(key)
        stage.append((row, day, value, period))

    clean = []
    for row, day, value, period in stage:
        resolved = extract.resolve_account(row["account_id"], day)
        if resolved in extract.exclusions:
            counts["excluded"] += 1
            continue
        if resolved not in extract.accounts:
            counts["unknown_account"] += 1
            continue
        clean.append(
            {
                "event_id": row["event_id"],
                "account_id": resolved,
                "event_date": day,
                "event_type": row["event_type"],
                "value_cents": value,
                "period": period,
            }
        )

    clean.sort(key=lambda e: (e["event_date"], e["account_id"], e["event_type"]))
    return clean, counts


def rejection_register(extract, clean):
    """Every reason that holds for each removed row, tested against the raw row."""
    kept = {event["event_id"] for event in clean}

    seen_keys, duplicate_ids = set(), set()
    for row in extract.events:
        key = (row["account_id"], row["event_date"], row["event_type"])
        if key in seen_keys:
            duplicate_ids.add(row["event_id"])
        seen_keys.add(key)

    register = []
    for row in extract.events:
        if row["event_id"] in kept:
            continue
        reasons = set()
        if is_malformed(row):
            reasons.add("malformed")
        if row["event_id"] in duplicate_ids:
            reasons.add("duplicate")
        day = parse_date(row.get("event_date"))
        if day is not None:
            if extract.period_of(day) is None:
                reasons.add("out_of_calendar")
            resolved = extract.resolve_account(row["account_id"], day)
            if resolved in extract.exclusions:
                reasons.add("excluded")
            if resolved not in extract.accounts:
                reasons.add("unknown_account")
        register.append({"event_id": row["event_id"], "reasons": sorted(reasons)})

    register.sort(key=lambda entry: entry["event_id"])
    return register


def build_cohorts(extract, clean):
    qualifying = set(extract.rules["qualifying_event_types"])
    minimum = int(extract.rules["minimum_value_cents"])

    first_qualifying = {}
    for event in clean:
        if event["event_type"] not in qualifying:
            continue
        if event["value_cents"] < minimum:
            continue
        account = event["account_id"]
        current = first_qualifying.get(account)
        if current is None or event["event_date"] < current:
            first_qualifying[account] = event["event_date"]

    members = {}
    for account, day in first_qualifying.items():
        members.setdefault(extract.period_of(day), []).append(account)
    return {
        name: sorted(members[name])
        for name in extract.period_names
        if name in members
    }


def cohort_of_account(cohorts):
    return {
        account: cohort
        for cohort, accounts in cohorts.items()
        for account in accounts
    }


def build_activity(extract, clean, cohorts):
    activity_types = set(extract.rules["activity_event_types"])
    max_offset = int(extract.config["max_offset"])
    cohort_of = cohort_of_account(cohorts)

    active, pre_cohort = set(), 0
    for event in clean:
        if event["event_type"] not in activity_types:
            continue
        cohort = cohort_of.get(event["account_id"])
        if cohort is None:
            continue
        if extract.period_index[event["period"]] < extract.period_index[cohort]:
            pre_cohort += 1
            continue
        active.add((event["account_id"], event["period"]))

    active_counts, retention_rates, survival_rates = {}, {}, {}
    for cohort, accounts in cohorts.items():
        size = len(accounts)
        counts, rates, survival = {}, {}, {}
        floor = None
        for offset in range(max_offset + 1):
            position = extract.period_index[cohort] + offset
            if position >= len(extract.period_names):
                continue
            period = extract.period_names[position]
            count = sum(1 for account in accounts if (account, period) in active)
            floor = count if floor is None else min(floor, count)
            counts[str(offset)] = count
            rates[str(offset)] = rate(count, size)
            survival[str(offset)] = rate(floor, size)
        active_counts[cohort] = counts
        retention_rates[cohort] = rates
        survival_rates[cohort] = survival
    return active_counts, retention_rates, survival_rates, pre_cohort


def build_revenue(extract, clean, cohorts):
    revenue_types = set(extract.rules["revenue_event_types"])
    cohort_of = cohort_of_account(cohorts)

    revenue_by_cohort = {cohort: 0 for cohort in cohorts}
    weighted_by_cohort = {cohort: 0 for cohort in cohorts}
    revenue_by_account, weighted_by_account = {}, {}
    for event in clean:
        if event["event_type"] not in revenue_types:
            continue
        account = event["account_id"]
        cohort = cohort_of.get(account)
        if cohort is None:
            continue
        signed = event["value_cents"]
        if event["event_type"] != "purchase":
            signed = -signed
        weighted = signed * extract.weight_of(account, event["event_date"])
        revenue_by_cohort[cohort] += signed
        weighted_by_cohort[cohort] += weighted
        revenue_by_account[account] = revenue_by_account.get(account, 0) + signed
        weighted_by_account[account] = weighted_by_account.get(account, 0) + weighted
    return (
        revenue_by_cohort,
        weighted_by_cohort,
        revenue_by_account,
        weighted_by_account,
    )


def build_segments(extract, cohorts, revenue_by_account, weighted_by_account):
    segments = {}
    for accounts in cohorts.values():
        for account in accounts:
            code = extract.accounts[account]["segment"]
            entry = segments.setdefault(
                code,
                {"accounts": 0, "revenue_cents": 0, "weighted_revenue_cents": 0},
            )
            entry["accounts"] += 1
            entry["revenue_cents"] += revenue_by_account.get(account, 0)
            entry["weighted_revenue_cents"] += weighted_by_account.get(account, 0)
    return segments


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    extract = Extract(data_dir)
    study_id = extract.config["study_id"]
    clean, removals = clean_events(extract)
    register = rejection_register(extract, clean)
    cohorts = build_cohorts(extract, clean)
    active_counts, retention_rates, survival_rates, pre_cohort = build_activity(
        extract, clean, cohorts
    )
    (
        revenue_by_cohort,
        weighted_by_cohort,
        revenue_by_account,
        weighted_by_account,
    ) = build_revenue(extract, clean, cohorts)
    segments = build_segments(extract, cohorts, revenue_by_account, weighted_by_account)

    cohorted_accounts = sum(len(accounts) for accounts in cohorts.values())
    total_revenue = sum(revenue_by_cohort.values())
    weighted_total = sum(weighted_by_cohort.values())

    write_json(
        out_dir,
        "cohorts.json",
        {
            "study_id": study_id,
            "cohort_sizes": {
                cohort: len(accounts) for cohort, accounts in cohorts.items()
            },
            "cohort_members": {
                cohort: list(accounts) for cohort, accounts in cohorts.items()
            },
            "cohorted_account_count": cohorted_accounts,
        },
    )
    write_json(
        out_dir,
        "retention.json",
        {
            "study_id": study_id,
            "active_counts": active_counts,
            "retention_rates": retention_rates,
        },
    )
    write_json(
        out_dir,
        "survival.json",
        {"study_id": study_id, "survival_rates": survival_rates},
    )
    write_json(
        out_dir,
        "revenue.json",
        {
            "study_id": study_id,
            "revenue_cents_by_cohort": revenue_by_cohort,
            "weighted_revenue_by_cohort": weighted_by_cohort,
            "total_revenue_cents": total_revenue,
            "weighted_revenue_total_cents": weighted_total,
            "weighted_share_by_cohort": {
                cohort: rate(value, weighted_total)
                for cohort, value in weighted_by_cohort.items()
            },
        },
    )
    write_json(out_dir, "segments.json", {"study_id": study_id, "segments": segments})
    write_json(
        out_dir,
        "data_quality.json",
        {
            "study_id": study_id,
            "input_event_count": len(extract.events),
            "clean_event_count": len(clean),
            "malformed_event_count": removals["malformed"],
            "out_of_calendar_event_count": removals["out_of_calendar"],
            "duplicate_event_count": removals["duplicate"],
            "excluded_event_count": removals["excluded"],
            "unknown_account_event_count": removals["unknown_account"],
            "excluded_account_count": len(extract.exclusions),
            "merge_rule_count": extract.merge_row_count,
            "pre_cohort_activity_count": pre_cohort,
            "rejections": register,
        },
    )

    offset_zero_residual = 0
    if extract.rules["offset_zero_is_full"]:
        offset_zero_residual = sum(
            active_counts[cohort].get("0", 0) - len(accounts)
            for cohort, accounts in cohorts.items()
        )
    write_json(
        out_dir,
        "reconciliation.json",
        {
            "study_id": study_id,
            "cohort_size_residual": cohorted_accounts
            - sum(entry["accounts"] for entry in segments.values()),
            "revenue_residual_cents": total_revenue
            - sum(entry["revenue_cents"] for entry in segments.values()),
            "weighted_revenue_residual_cents": weighted_total
            - sum(entry["weighted_revenue_cents"] for entry in segments.values()),
            "offset_zero_residual": offset_zero_residual,
        },
    )
    write_json(
        out_dir,
        "study_audit.json",
        {
            "study_id": study_id,
            "max_offset": int(extract.config["max_offset"]),
            "qualifying_event_types": sorted(extract.rules["qualifying_event_types"]),
            "activity_event_types": sorted(extract.rules["activity_event_types"]),
            "revenue_event_types": sorted(extract.rules["revenue_event_types"]),
            "minimum_value_cents": int(extract.rules["minimum_value_cents"]),
            "plan_weights": {
                plan: int(weight) for plan, weight in extract.plan_weights.items()
            },
        },
    )

    for cohort in list(cohorts)[:2]:
        write_json(
            out_dir,
            "cohort_%s.json" % cohort,
            {
                "study_id": study_id,
                "cohort": cohort,
                "size": len(cohorts[cohort]),
                "members": list(cohorts[cohort]),
                "active_counts": active_counts[cohort],
                "retention_rates": retention_rates[cohort],
                "survival_rates": survival_rates[cohort],
                "revenue_cents": revenue_by_cohort[cohort],
                "weighted_revenue_cents": weighted_by_cohort[cohort],
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
