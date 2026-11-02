#!/usr/bin/env python3
"""Derive the exact cohort retention study from a flat activity extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Reads the extract described by DATA_DIR/schema.md and DATA_DIR/audit_policy.md and
writes the cohort, retention, survival, revenue, segment, data-quality,
reconciliation, study-audit and per-cohort reports into OUT_DIR. Only the
standard library is used and every rate is an exact reduced fraction.
"""
from __future__ import annotations

import bisect
import csv
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from itertools import accumulate
from pathlib import Path
from typing import Any

DATE_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
CENTS_SHAPE = re.compile(r"[0-9]+")
ADDING_REVENUE_TYPE = "purchase"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def exact(num: int, den: int) -> str:
    if den == 0:
        return "0"
    value = Fraction(num, den)
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def parse_day(text: str) -> date | None:
    """The contract's date test: a real calendar date written as YYYY-MM-DD."""
    if not DATE_SHAPE.fullmatch(text):
        return None
    try:
        return date(int(text[0:4]), int(text[5:7]), int(text[8:10]))
    except ValueError:
        return None


class Calendar:
    def __init__(self, rows: list[dict[str, str]]):
        spans = sorted(
            (date.fromisoformat(r["start_date"]), date.fromisoformat(r["end_date"]), r["period"])
            for r in rows
        )
        self.starts = [s for s, _, _ in spans]
        self.spans = spans
        self.order = [p for _, _, p in spans]
        self.position = {p: i for i, p in enumerate(self.order)}

    def period_of(self, day: date) -> str | None:
        i = bisect.bisect_right(self.starts, day) - 1
        if i < 0:
            return None
        start, end, period = self.spans[i]
        return period if start <= day <= end else None

    def shifted(self, period: str, offset: int) -> str | None:
        i = self.position[period] + offset
        return self.order[i] if i < len(self.order) else None


class DatedLookup:
    """Rows keyed by account, each (effective_from, file index, value); the row in
    force on a date is the latest effective_from on or before it, later row on ties."""

    def __init__(self, rows: list[tuple[str, date, str]]):
        self.by_key: dict[str, list[tuple[date, int, str]]] = defaultdict(list)
        for index, (key, start, value) in enumerate(rows):
            self.by_key[key].append((start, index, value))

    def in_force(self, key: str, day: date) -> str | None:
        applicable = [row for row in self.by_key.get(key, ()) if row[0] <= day]
        return max(applicable)[2] if applicable else None


class MergeHistory(DatedLookup):
    def resolve(self, account: str, day: date) -> str:
        seen = {account}
        while True:
            target = self.in_force(account, day)
            if target is None or target in seen:
                return account
            seen.add(target)
            account = target


@dataclass(frozen=True)
class CleanEvent:
    account: str
    day: date
    period: str
    kind: str
    cents: int


@dataclass
class Cleaning:
    events: list[CleanEvent]
    removed: dict[str, int]
    rejections: list[dict[str, Any]]


STEPS = ("malformed", "out_of_calendar", "duplicate", "excluded", "unknown_account")


def clean_events(raw, calendar, merges, known, excluded) -> Cleaning:
    removed = {step: 0 for step in STEPS}
    seen_raw: set[tuple[str, str, str]] = set()
    kept_raw: set[tuple[str, str, str]] = set()
    events: list[CleanEvent] = []
    rejections: list[dict[str, Any]] = []
    for row in raw:
        key = (row["account_id"], row["event_date"], row["event_type"])
        day = parse_day(row["event_date"])
        malformed = day is None or not CENTS_SHAPE.fullmatch(row["value_cents"])
        reasons: set[str] = set()
        if malformed:
            reasons.add("malformed")
        if key in seen_raw:
            reasons.add("duplicate")
        seen_raw.add(key)
        period = resolved = None
        if day is not None:
            period = calendar.period_of(day)
            resolved = merges.resolve(row["account_id"], day)
            if period is None:
                reasons.add("out_of_calendar")
            if resolved in excluded:
                reasons.add("excluded")
            if resolved not in known:
                reasons.add("unknown_account")

        if malformed:
            step = "malformed"
        elif period is None:
            step = "out_of_calendar"
        elif key in kept_raw:
            step = "duplicate"
        else:
            kept_raw.add(key)
            if resolved in excluded:
                step = "excluded"
            elif resolved not in known:
                step = "unknown_account"
            else:
                step = None
        if step is None:
            events.append(CleanEvent(resolved, day, period, row["event_type"], int(row["value_cents"])))
            continue
        removed[step] += 1
        rejections.append({"event_id": row["event_id"], "reasons": sorted(reasons)})
    events.sort(key=lambda e: (e.day, e.account, e.kind))
    rejections.sort(key=lambda r: r["event_id"])
    return Cleaning(events, removed, rejections)


def build_artifacts(data_dir: Path) -> dict[str, dict[str, Any]]:
    config = read_json(data_dir / "study_config.json")
    rules = read_json(data_dir / "qualifying_rules.json")
    weights = {plan: int(w) for plan, w in read_json(data_dir / "plan_weights.json").items()}
    raw = read_csv(data_dir / "events.csv")
    accounts = {row["account_id"]: row for row in read_csv(data_dir / "accounts.csv")}
    merge_rows = read_csv(data_dir / "account_merges.csv")
    merges = MergeHistory(
        [(r["from_account_id"], date.fromisoformat(r["effective_from"]), r["to_account_id"]) for r in merge_rows]
    )
    plans = DatedLookup(
        [(r["account_id"], date.fromisoformat(r["effective_from"]), r["plan"])
         for r in read_csv(data_dir / "plan_history.csv")]
    )
    excluded = {row["account_id"] for row in read_csv(data_dir / "exclusions.csv")}
    calendar = Calendar(read_csv(data_dir / "period_calendar.csv"))
    study_id = config["study_id"]
    horizon = int(config["max_offset"])
    qualifying = set(rules["qualifying_event_types"])
    activity_kinds = set(rules["activity_event_types"])
    revenue_kinds = set(rules["revenue_event_types"])
    minimum = int(rules["minimum_value_cents"])

    cleaning = clean_events(raw, calendar, merges, set(accounts), excluded)
    by_account: dict[str, list[CleanEvent]] = defaultdict(list)
    for event in cleaning.events:
        by_account[event.account].append(event)

    cohort_of: dict[str, str] = {}
    for account, timeline in by_account.items():
        firsts = [e for e in timeline if e.kind in qualifying and e.cents >= minimum]
        if firsts:
            cohort_of[account] = firsts[0].period

    active: dict[str, set[str]] = defaultdict(set)
    early = 0
    for account, cohort in cohort_of.items():
        for e in by_account[account]:
            if e.kind not in activity_kinds:
                continue
            if calendar.position[e.period] < calendar.position[cohort]:
                early += 1
            else:
                active[account].add(e.period)

    def signed(e: CleanEvent) -> int:
        return e.cents if e.kind == ADDING_REVENUE_TYPE else -e.cents

    def weight_of(e: CleanEvent) -> int:
        plan = plans.in_force(e.account, e.day) or accounts[e.account]["plan"]
        return weights.get(plan, 0)

    def revenue_of(account: str) -> tuple[int, int]:
        rows = [e for e in by_account[account] if e.kind in revenue_kinds]
        return sum(signed(e) for e in rows), sum(signed(e) * weight_of(e) for e in rows)

    members: dict[str, list[str]] = defaultdict(list)
    for account in sorted(cohort_of):
        members[cohort_of[account]].append(account)
    cohorts = sorted(members, key=calendar.position.__getitem__)

    counts, retention, survival, revenue, weighted = {}, {}, {}, {}, {}
    for cohort in cohorts:
        size = len(members[cohort])
        series = []
        for offset in range(horizon + 1):
            period = calendar.shifted(cohort, offset)
            if period is None:
                break
            series.append(sum(period in active[a] for a in members[cohort]))
        counts[cohort] = {str(i): n for i, n in enumerate(series)}
        retention[cohort] = {str(i): exact(n, size) for i, n in enumerate(series)}
        survival[cohort] = {str(i): exact(n, size) for i, n in enumerate(accumulate(series, min))}
        pairs = [revenue_of(a) for a in members[cohort]]
        revenue[cohort] = sum(p[0] for p in pairs)
        weighted[cohort] = sum(p[1] for p in pairs)

    segments: dict[str, dict[str, int]] = {}
    for account in cohort_of:
        bucket = segments.setdefault(
            accounts[account]["segment"], {"accounts": 0, "revenue_cents": 0, "weighted_revenue_cents": 0}
        )
        plain, heavy = revenue_of(account)
        bucket["accounts"] += 1
        bucket["revenue_cents"] += plain
        bucket["weighted_revenue_cents"] += heavy

    total = sum(revenue.values())
    weighted_total = sum(weighted.values())
    offset_zero = 0
    if rules["offset_zero_is_full"]:
        offset_zero = sum(counts[c].get("0", 0) - len(members[c]) for c in cohorts)

    artifacts: dict[str, dict[str, Any]] = {
        "cohorts.json": {
            "study_id": study_id,
            "cohort_sizes": {c: len(members[c]) for c in cohorts},
            "cohort_members": {c: members[c] for c in cohorts},
            "cohorted_account_count": len(cohort_of),
        },
        "retention.json": {"study_id": study_id, "active_counts": counts, "retention_rates": retention},
        "survival.json": {"study_id": study_id, "survival_rates": survival},
        "revenue.json": {
            "study_id": study_id,
            "revenue_cents_by_cohort": revenue,
            "weighted_revenue_by_cohort": weighted,
            "total_revenue_cents": total,
            "weighted_revenue_total_cents": weighted_total,
            "weighted_share_by_cohort": {c: exact(weighted[c], weighted_total) for c in cohorts},
        },
        "segments.json": {"study_id": study_id, "segments": segments},
        "data_quality.json": {
            "study_id": study_id,
            "input_event_count": len(raw),
            "clean_event_count": len(cleaning.events),
            "malformed_event_count": cleaning.removed["malformed"],
            "out_of_calendar_event_count": cleaning.removed["out_of_calendar"],
            "duplicate_event_count": cleaning.removed["duplicate"],
            "excluded_event_count": cleaning.removed["excluded"],
            "unknown_account_event_count": cleaning.removed["unknown_account"],
            "excluded_account_count": len(excluded),
            "merge_rule_count": len(merge_rows),
            "pre_cohort_activity_count": early,
            "rejections": cleaning.rejections,
        },
        "reconciliation.json": {
            "study_id": study_id,
            "cohort_size_residual": len(cohort_of) - sum(s["accounts"] for s in segments.values()),
            "revenue_residual_cents": total - sum(s["revenue_cents"] for s in segments.values()),
            "weighted_revenue_residual_cents": weighted_total
            - sum(s["weighted_revenue_cents"] for s in segments.values()),
            "offset_zero_residual": offset_zero,
        },
        "study_audit.json": {
            "study_id": study_id,
            "max_offset": horizon,
            "qualifying_event_types": sorted(qualifying),
            "activity_event_types": sorted(activity_kinds),
            "revenue_event_types": sorted(revenue_kinds),
            "minimum_value_cents": minimum,
            "plan_weights": weights,
        },
    }
    for cohort in cohorts[:2]:
        artifacts[f"cohort_{cohort}.json"] = {
            "study_id": study_id,
            "cohort": cohort,
            "size": len(members[cohort]),
            "members": members[cohort],
            "active_counts": counts[cohort],
            "retention_rates": retention[cohort],
            "survival_rates": survival[cohort],
            "revenue_cents": revenue[cohort],
            "weighted_revenue_cents": weighted[cohort],
        }
    return artifacts


def write_artifacts(artifacts: dict[str, dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, doc in artifacts.items():
        (out_dir / name).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    write_artifacts(build_artifacts(Path(argv[1])), Path(argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
