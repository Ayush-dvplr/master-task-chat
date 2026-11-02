#!/usr/bin/env python3
"""Derive an exact cohort retention study from a flat-file activity extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Every rate is emitted as an exact reduced fraction string; counts are integers
and money is integer cents. Standard library only.
"""

import csv
import json
import os
import sys
from fractions import Fraction


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return [
            {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(fh)
        ]


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rate(numerator, denominator):
    """Exact reduced fraction as a string; zero denominator renders as "0"."""
    if denominator == 0:
        return "0"
    value = Fraction(numerator, denominator)
    if value.denominator == 1:
        return str(value.numerator)
    return "%d/%d" % (value.numerator, value.denominator)


def write_json(out_dir, name, payload):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, indent=2)
        fh.write("\n")


def build_merge_index(merge_rows):
    index = {}
    for row in merge_rows:
        index.setdefault(row["from_account_id"], []).append(
            (row["effective_from"], row["to_account_id"])
        )
    for key in index:
        index[key].sort()
    return index


def resolve_account(account, event_date, merge_index):
    """Follow the merge chain that is effective on event_date."""
    current = account
    seen = {current}
    while True:
        applicable = [
            pair for pair in merge_index.get(current, []) if pair[0] <= event_date
        ]
        if not applicable:
            return current
        target = max(applicable)[1]
        if target in seen:
            return current
        seen.add(target)
        current = target


def period_of_date(event_date, periods):
    for period in periods:
        if period["start_date"] <= event_date <= period["end_date"]:
            return period["period"]
    return None


def load_extract(data_dir):
    join = lambda name: os.path.join(data_dir, name)
    periods = sorted(read_csv(join("period_calendar.csv")), key=lambda p: p["start_date"])
    return {
        "events": read_csv(join("events.csv")),
        "accounts": {row["account_id"]: row for row in read_csv(join("accounts.csv"))},
        "merges": read_csv(join("account_merges.csv")),
        "exclusions": read_csv(join("exclusions.csv")),
        "periods": periods,
        "segments": read_csv(join("segments.csv")),
        "plan_weights": read_json(join("plan_weights.json")),
        "rules": read_json(join("qualifying_rules.json")),
        "config": read_json(join("study_config.json")),
    }


def clean_events(extract):
    """Apply the contract's cleaning order and return cleaned events plus counts."""
    periods = extract["periods"]
    accounts = extract["accounts"]
    merge_index = build_merge_index(extract["merges"])
    excluded = {row["account_id"] for row in extract["exclusions"]}

    out_of_calendar = 0
    duplicates = 0
    seen_keys = set()
    cleaned = []

    for row in extract["events"]:
        event_date = row["event_date"]
        period = period_of_date(event_date, periods)
        if period is None:
            out_of_calendar += 1
            continue

        key = (row["account_id"], event_date, row["event_type"])
        if key in seen_keys:
            duplicates += 1
            continue
        seen_keys.add(key)

        resolved = resolve_account(row["account_id"], event_date, merge_index)
        if resolved in excluded or resolved not in accounts:
            continue

        cleaned.append(
            {
                "event_id": row["event_id"],
                "account_id": resolved,
                "event_date": event_date,
                "event_type": row["event_type"],
                "value_cents": int(row["value_cents"]),
                "period": period,
            }
        )

    cleaned.sort(key=lambda e: (e["event_date"], e["account_id"], e["event_type"]))
    return {
        "cleaned": cleaned,
        "out_of_calendar_event_count": out_of_calendar,
        "duplicate_event_count": duplicates,
        "excluded_account_count": len(excluded),
        "merge_rule_count": len(extract["merges"]),
        "input_event_count": len(extract["events"]),
    }


def assign_cohorts(cleaned, extract):
    rules = extract["rules"]
    qualifying = set(rules["qualifying_event_types"])
    minimum = int(rules["minimum_value_cents"])

    earliest = {}
    for event in cleaned:
        if event["event_type"] not in qualifying:
            continue
        if event["value_cents"] < minimum:
            continue
        account = event["account_id"]
        if account not in earliest or event["event_date"] < earliest[account][0]:
            earliest[account] = (event["event_date"], event["period"])

    members = {}
    for account, (_, period) in earliest.items():
        members.setdefault(period, []).append(account)
    for period in members:
        members[period].sort()

    order = [p["period"] for p in extract["periods"] if p["period"] in members]
    cohort_of = {account: value[1] for account, value in earliest.items()}
    return order, members, cohort_of


def build_activity(cleaned, extract, cohort_of):
    """Account/period activity sets, excluding (and counting) pre-cohort activity."""
    activity_types = set(extract["rules"]["activity_event_types"])
    period_index = {p["period"]: i for i, p in enumerate(extract["periods"])}

    active = {}
    pre_cohort = 0
    for event in cleaned:
        if event["event_type"] not in activity_types:
            continue
        account = event["account_id"]
        cohort = cohort_of.get(account)
        if cohort is None:
            continue
        if period_index[event["period"]] < period_index[cohort]:
            pre_cohort += 1
            continue
        active.setdefault(account, set()).add(event["period"])
    return active, pre_cohort


def build_matrix(cohort_order, members, active, extract):
    periods = [p["period"] for p in extract["periods"]]
    period_index = {period: i for i, period in enumerate(periods)}
    max_offset = int(extract["config"]["max_offset"])

    counts = {}
    retention = {}
    survival = {}
    for cohort in cohort_order:
        size = len(members[cohort])
        base = period_index[cohort]
        counts[cohort] = {}
        retention[cohort] = {}
        survival[cohort] = {}
        running_min = None
        for offset in range(max_offset + 1):
            target = base + offset
            if target >= len(periods):
                break
            period = periods[target]
            count = sum(
                1 for account in members[cohort] if period in active.get(account, ())
            )
            running_min = count if running_min is None else min(running_min, count)
            key = str(offset)
            counts[cohort][key] = count
            retention[cohort][key] = rate(count, size)
            survival[cohort][key] = rate(running_min, size)
    return counts, retention, survival


def build_revenue(cleaned, extract, cohort_of, cohort_order):
    revenue_types = set(extract["rules"]["revenue_event_types"])
    accounts = extract["accounts"]
    weights = extract["plan_weights"]

    by_cohort = {cohort: 0 for cohort in cohort_order}
    weighted = {cohort: 0 for cohort in cohort_order}
    by_account = {}
    for event in cleaned:
        if event["event_type"] not in revenue_types:
            continue
        account = event["account_id"]
        cohort = cohort_of.get(account)
        if cohort is None:
            continue
        value = event["value_cents"]
        by_cohort[cohort] += value
        weighted[cohort] += value * int(weights[accounts[account]["plan"]])
        by_account[account] = by_account.get(account, 0) + value
    return by_cohort, weighted, by_account


def build_segments(extract, cohort_of, revenue_by_account):
    accounts = extract["accounts"]
    codes = {row["segment"] for row in extract["segments"]}
    codes.update(accounts[account]["segment"] for account in cohort_of)

    segments = {code: {"accounts": 0, "revenue_cents": 0} for code in codes}
    for account in cohort_of:
        code = accounts[account]["segment"]
        segments[code]["accounts"] += 1
        segments[code]["revenue_cents"] += revenue_by_account.get(account, 0)
    return segments


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    extract = load_extract(data_dir)
    study_id = extract["config"]["study_id"]
    rules = extract["rules"]

    clean = clean_events(extract)
    cleaned = clean["cleaned"]
    cohort_order, members, cohort_of = assign_cohorts(cleaned, extract)
    active, pre_cohort_activity = build_activity(cleaned, extract, cohort_of)
    counts, retention, survival = build_matrix(cohort_order, members, active, extract)
    revenue, weighted_revenue, revenue_by_account = build_revenue(
        cleaned, extract, cohort_of, cohort_order
    )
    segments = build_segments(extract, cohort_of, revenue_by_account)

    cohort_sizes = {cohort: len(members[cohort]) for cohort in cohort_order}
    cohorted_account_count = sum(cohort_sizes.values())
    total_revenue = sum(revenue.values())

    offset_zero_residual = 0
    if rules["offset_zero_is_full"]:
        offset_zero_residual = sum(
            counts[cohort].get("0", 0) - cohort_sizes[cohort] for cohort in cohort_order
        )

    write_json(
        out_dir,
        "cohorts.json",
        {
            "study_id": study_id,
            "cohort_sizes": cohort_sizes,
            "cohort_members": {cohort: members[cohort] for cohort in cohort_order},
            "cohorted_account_count": cohorted_account_count,
        },
    )
    write_json(
        out_dir,
        "retention.json",
        {
            "study_id": study_id,
            "active_counts": counts,
            "retention_rates": retention,
        },
    )
    write_json(
        out_dir,
        "survival.json",
        {"study_id": study_id, "survival_rates": survival},
    )
    write_json(
        out_dir,
        "revenue.json",
        {
            "study_id": study_id,
            "revenue_cents_by_cohort": revenue,
            "weighted_revenue_by_cohort": weighted_revenue,
            "total_revenue_cents": total_revenue,
        },
    )
    write_json(out_dir, "segments.json", {"study_id": study_id, "segments": segments})
    write_json(
        out_dir,
        "data_quality.json",
        {
            "study_id": study_id,
            "input_event_count": clean["input_event_count"],
            "clean_event_count": len(cleaned),
            "duplicate_event_count": clean["duplicate_event_count"],
            "out_of_calendar_event_count": clean["out_of_calendar_event_count"],
            "excluded_account_count": clean["excluded_account_count"],
            "merge_rule_count": clean["merge_rule_count"],
            "pre_cohort_activity_count": pre_cohort_activity,
        },
    )
    write_json(
        out_dir,
        "reconciliation.json",
        {
            "study_id": study_id,
            "cohort_size_residual": cohorted_account_count
            - sum(seg["accounts"] for seg in segments.values()),
            "revenue_residual_cents": total_revenue
            - sum(seg["revenue_cents"] for seg in segments.values()),
            "offset_zero_residual": offset_zero_residual,
        },
    )
    write_json(
        out_dir,
        "study_audit.json",
        {
            "study_id": study_id,
            "max_offset": int(extract["config"]["max_offset"]),
            "qualifying_event_types": sorted(rules["qualifying_event_types"]),
            "activity_event_types": sorted(rules["activity_event_types"]),
            "revenue_event_types": sorted(rules["revenue_event_types"]),
            "minimum_value_cents": int(rules["minimum_value_cents"]),
            "plan_weights": {plan: int(w) for plan, w in extract["plan_weights"].items()},
        },
    )

    for cohort in cohort_order[:2]:
        write_json(
            out_dir,
            "cohort_%s.json" % cohort,
            {
                "study_id": study_id,
                "cohort": cohort,
                "size": cohort_sizes[cohort],
                "members": members[cohort],
                "active_counts": counts[cohort],
                "retention_rates": retention[cohort],
                "survival_rates": survival[cohort],
                "revenue_cents": revenue[cohort],
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
