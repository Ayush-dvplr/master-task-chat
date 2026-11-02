#!/usr/bin/env python3
"""Derive the exact cohort retention study from a flat activity extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Reads the extract described by DATA_DIR/schema.md and DATA_DIR/audit_policy.md and
writes the cohort, retention, survival, revenue, segment, data-quality,
reconciliation, study-audit and per-cohort reports into OUT_DIR. Only the
standard library is used and every rate is an exact reduced fraction.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from bisect import bisect_right
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
WHOLE_CENTS = re.compile(r"\d+", re.ASCII)
CREDITING_TYPE = "purchase"
POLICY_ORDER = ("malformed", "out_of_calendar", "duplicate", "excluded", "unknown_account")


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------

def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(record) for record in csv.DictReader(handle)]


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def strict_day(text: str) -> date | None:
    """A real calendar date written exactly as four, two and two digits."""
    if ISO_DAY.fullmatch(text) is None:
        return None
    year, month, day = int(text[0:4]), int(text[5:7]), int(text[8:10])
    if year < 1 or not 1 <= month <= 12 or not 1 <= day <= monthrange(year, month)[1]:
        return None
    return date(year, month, day)


def ident(text: str) -> str:
    """Identifiers compare with surrounding spaces removed and letters lower-cased."""
    return text.strip().lower()


def fraction_text(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0"
    reduced = Fraction(numerator, denominator)
    return str(reduced.numerator) if reduced.denominator == 1 else f"{reduced.numerator}/{reduced.denominator}"


class Timeline:
    """Per-key dated values; the value in force on a day comes from the row with
    the latest start on or before that day, and the later file row wins a tie."""

    def __init__(self) -> None:
        self._starts: dict[str, list[tuple[date, int]]] = {}
        self._values: dict[str, list[str]] = {}

    @classmethod
    def from_rows(cls, rows: list[dict[str, str]], key: str, value: str) -> "Timeline":
        timeline = cls()
        ordered = sorted(
            (
                (ident(row[key]), date.fromisoformat(row["effective_from"]), line, ident(row[value]))
                for line, row in enumerate(rows)
            ),
            key=lambda item: (item[0], item[1], item[2]),
        )
        for owner, start, line, target in ordered:
            timeline._starts.setdefault(owner, []).append((start, line))
            timeline._values.setdefault(owner, []).append(target)
        return timeline

    def value_on(self, owner: str, day: date) -> str | None:
        starts = self._starts.get(owner)
        if not starts:
            return None
        slot = bisect_right(starts, (day, float("inf"))) - 1
        return self._values[owner][slot] if slot >= 0 else None


@dataclass
class Extract:
    study_id: str
    horizon: int
    qualifying: frozenset[str]
    activity: frozenset[str]
    revenue_types: frozenset[str]
    minimum_cents: int
    offset_zero_is_full: bool
    weights: dict[str, int]
    events: list[dict[str, str]]
    accounts: dict[str, dict[str, str]]
    merge_count: int
    merges: Timeline
    plans: Timeline
    excluded: frozenset[str]
    overrides: dict[str, int]
    control_mismatches: list[str]
    control_value_residual: int
    period_names: list[str]
    period_starts: list[date]
    period_ends: list[date]

    def period_index(self, day: date) -> int | None:
        slot = bisect_right(self.period_starts, day) - 1
        if slot < 0 or day > self.period_ends[slot]:
            return None
        return slot

    def owner_on(self, account: str, day: date) -> str:
        current, visited = account, {account}
        while (successor := self.merges.value_on(current, day)) is not None and successor not in visited:
            visited.add(successor)
            current = successor
        return current

    def segment_of(self, account: str) -> str:
        return ident(self.accounts[account]["segment"])

    def weight_on(self, account: str, day: date) -> int:
        override = self.overrides.get(self.segment_of(account))
        if override is not None:
            return override
        plan = self.plans.value_on(account, day)
        if plan is None:
            plan = ident(self.accounts[account]["plan"])
        return self.weights.get(plan, 0)


def manifest_value_sum(rows: list[dict[str, str]]) -> int:
    """The export job's value figure: values read with surrounding spaces removed."""
    total = 0
    for row in rows:
        value = (row.get("value_cents") or "").strip()
        if WHOLE_CENTS.fullmatch(value):
            total += int(value)
    return total


def check_manifest(data_dir: Path) -> tuple[list[str], int]:
    """Compare each manifest figure with the same figure counted from the file."""
    path = data_dir / "extract_manifest.json"
    if not path.is_file():
        return [], 0
    mismatches: list[str] = []
    residual = 0
    for name, figures in sorted(load_json(path).get("files", {}).items()):
        target = data_dir / name
        text = target.read_text(encoding="utf-8") if target.is_file() else ""
        counted = {
            "data_rows": max(len(text.splitlines()) - 1, 0),
            "value_cents_sum": manifest_value_sum(load_rows(target)) if target.is_file() else 0,
        }
        for figure, recorded in sorted(figures.items()):
            if counted.get(figure) != recorded:
                mismatches.append(f"{name}:{figure}")
            if name == "events.csv" and figure == "value_cents_sum":
                residual = int(recorded) - counted[figure]
    return sorted(mismatches), residual


def load_extract(data_dir: Path) -> Extract:
    config = load_json(data_dir / "study_config.json")
    rules = load_json(data_dir / "qualifying_rules.json")
    merge_rows = load_rows(data_dir / "account_merges.csv")
    overrides = {
        ident(row["segment"]): int(row["weight_override"].strip())
        for row in load_rows(data_dir / "segments.csv")
        if (row.get("weight_override") or "").strip()
    }
    mismatches, value_residual = check_manifest(data_dir)
    calendar = sorted(
        (date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"]), row["period"])
        for row in load_rows(data_dir / "period_calendar.csv")
    )
    return Extract(
        study_id=config["study_id"],
        horizon=int(config["max_offset"]),
        qualifying=frozenset(ident(kind) for kind in rules["qualifying_event_types"]),
        activity=frozenset(ident(kind) for kind in rules["activity_event_types"]),
        revenue_types=frozenset(ident(kind) for kind in rules["revenue_event_types"]),
        minimum_cents=int(rules["minimum_value_cents"]),
        offset_zero_is_full=bool(rules["offset_zero_is_full"]),
        weights={ident(plan): int(weight) for plan, weight in load_json(data_dir / "plan_weights.json").items()},
        events=load_rows(data_dir / "events.csv"),
        accounts={ident(row["account_id"]): row for row in load_rows(data_dir / "accounts.csv")},
        merge_count=len(merge_rows),
        merges=Timeline.from_rows(merge_rows, "from_account_id", "to_account_id"),
        plans=Timeline.from_rows(load_rows(data_dir / "plan_history.csv"), "account_id", "plan"),
        excluded=frozenset(ident(row["account_id"]) for row in load_rows(data_dir / "exclusions.csv")),
        overrides=overrides,
        control_mismatches=mismatches,
        control_value_residual=value_residual,
        period_names=[name for _, _, name in calendar],
        period_starts=[start for start, _, _ in calendar],
        period_ends=[end for _, end, _ in calendar],
    )


# --------------------------------------------------------------------------
# Audit policy: tag every raw row, then filter in policy order
# --------------------------------------------------------------------------

@dataclass
class TaggedRow:
    line: int
    event_id: str
    raw_key: tuple[str, str, str]
    kind: str
    day: date | None
    cents: int | None
    period: int | None
    owner: str | None
    reasons: set[str] = field(default_factory=set)


@dataclass
class AuditResult:
    clean: list[TaggedRow]
    removed_counts: dict[str, int]
    register: list[dict[str, Any]]


def tag_rows(extract: Extract) -> list[TaggedRow]:
    first_line: dict[tuple[str, str, str], int] = {}
    tagged: list[TaggedRow] = []
    for line, raw in enumerate(extract.events):
        account, kind = ident(raw["account_id"]), ident(raw["event_type"])
        raw_key = (account, raw["event_date"], kind)
        first_line.setdefault(raw_key, line)
        day = strict_day(raw["event_date"])
        cents = int(raw["value_cents"]) if WHOLE_CENTS.fullmatch(raw["value_cents"]) else None
        row = TaggedRow(line, raw["event_id"], raw_key, kind, day, cents, None, None)
        if day is None or cents is None:
            row.reasons.add("malformed")
        if first_line[raw_key] != line:
            row.reasons.add("duplicate")
        if day is not None:
            row.period = extract.period_index(day)
            row.owner = extract.owner_on(account, day)
            if row.period is None:
                row.reasons.add("out_of_calendar")
            if row.owner in extract.excluded:
                row.reasons.add("excluded")
            if row.owner not in extract.accounts:
                row.reasons.add("unknown_account")
        tagged.append(row)
    return tagged


def first_of_each_key(rows: list[TaggedRow]) -> set[int]:
    winners: dict[tuple[str, str, str], int] = {}
    for row in rows:
        winners.setdefault(row.raw_key, row.line)
    return set(winners.values())


def audit(extract: Extract) -> AuditResult:
    tagged = tag_rows(extract)
    survivors = tagged
    removed: list[TaggedRow] = []
    counts: dict[str, int] = {}
    for reason in POLICY_ORDER:
        if reason == "duplicate":
            keep_lines = first_of_each_key(survivors)
            holds: Callable[[TaggedRow], bool] = lambda row, keep=keep_lines: row.line not in keep
        else:
            holds = lambda row, wanted=reason: wanted in row.reasons
        dropped = [row for row in survivors if holds(row)]
        survivors = [row for row in survivors if not holds(row)]
        counts[reason] = len(dropped)
        removed.extend(dropped)
    register = sorted(
        ({"event_id": row.event_id, "reasons": sorted(row.reasons)} for row in removed),
        key=lambda entry: entry["event_id"],
    )
    survivors.sort(key=lambda row: (row.day, row.owner, row.kind))
    return AuditResult(survivors, counts, register)


# --------------------------------------------------------------------------
# Study
# --------------------------------------------------------------------------

@dataclass
class Study:
    extract: Extract
    audit: AuditResult
    cohort_index: dict[str, int]
    members: dict[str, list[str]]
    order: list[str]
    active: dict[str, set[int]]
    pre_cohort_events: int
    plain_by_account: dict[str, int]
    weighted_by_account: dict[str, int]
    unhonored_by_account: dict[str, int]

    def counts(self, cohort: str) -> list[int]:
        start = self.extract.period_names.index(cohort)
        last = min(start + self.extract.horizon, len(self.extract.period_names) - 1)
        return [
            len([account for account in self.members[cohort] if index in self.active[account]])
            for index in range(start, last + 1)
        ]

    def survivors(self, cohort: str) -> list[int]:
        running: list[int] = []
        for count in self.counts(cohort):
            running.append(count if not running else min(running[-1], count))
        return running

    def cohort_revenue(self, cohort: str) -> int:
        return sum(self.plain_by_account[account] for account in self.members[cohort])

    def cohort_weighted(self, cohort: str) -> int:
        return sum(self.weighted_by_account[account] for account in self.members[cohort])


def build_study(extract: Extract) -> Study:
    result = audit(extract)
    earliest: dict[str, date] = {}
    for row in result.clean:
        if row.kind in extract.qualifying and row.cents >= extract.minimum_cents:
            if row.owner not in earliest or row.day < earliest[row.owner]:
                earliest[row.owner] = row.day
    cohort_index = {account: extract.period_index(day) for account, day in earliest.items()}

    by_period: dict[int, list[str]] = {}
    for account in sorted(cohort_index):
        by_period.setdefault(cohort_index[account], []).append(account)
    order = [extract.period_names[index] for index in sorted(by_period)]
    members = {extract.period_names[index]: accounts for index, accounts in by_period.items()}

    active: dict[str, set[int]] = {account: set() for account in cohort_index}
    pre_cohort = 0
    plain = dict.fromkeys(cohort_index, 0)
    weighted = dict.fromkeys(cohort_index, 0)
    unhonored = dict.fromkeys(cohort_index, 0)
    balance: dict[str, int] = {}
    for row in result.clean:
        booked = shortfall = 0
        if row.kind in extract.revenue_types:
            held = balance.get(row.owner, 0)
            if row.kind == CREDITING_TYPE:
                booked = row.cents
            else:
                booked = -min(row.cents, held)
                shortfall = row.cents + booked
            balance[row.owner] = held + booked
        if row.owner not in cohort_index:
            continue
        if row.kind in extract.activity:
            if row.period < cohort_index[row.owner]:
                pre_cohort += 1
            else:
                active[row.owner].add(row.period)
        if row.kind in extract.revenue_types:
            plain[row.owner] += booked
            weighted[row.owner] += booked * extract.weight_on(row.owner, row.day)
            unhonored[row.owner] += shortfall
    return Study(extract, result, cohort_index, members, order, active, pre_cohort, plain, weighted, unhonored)


# --------------------------------------------------------------------------
# One builder per report
# --------------------------------------------------------------------------

def offsets(values: list[Any]) -> dict[str, Any]:
    return {str(offset): value for offset, value in enumerate(values)}


def rates(study: Study, cohort: str, values: list[int]) -> dict[str, str]:
    size = len(study.members[cohort])
    return offsets([fraction_text(value, size) for value in values])


def cohorts_report(study: Study) -> dict[str, Any]:
    return {
        "study_id": study.extract.study_id,
        "cohort_sizes": {cohort: len(study.members[cohort]) for cohort in study.order},
        "cohort_members": {cohort: list(study.members[cohort]) for cohort in study.order},
        "cohorted_account_count": len(study.cohort_index),
    }


def retention_report(study: Study) -> dict[str, Any]:
    return {
        "study_id": study.extract.study_id,
        "active_counts": {cohort: offsets(study.counts(cohort)) for cohort in study.order},
        "retention_rates": {cohort: rates(study, cohort, study.counts(cohort)) for cohort in study.order},
    }


def survival_report(study: Study) -> dict[str, Any]:
    return {
        "study_id": study.extract.study_id,
        "survival_rates": {cohort: rates(study, cohort, study.survivors(cohort)) for cohort in study.order},
    }


def revenue_report(study: Study) -> dict[str, Any]:
    weighted_total = sum(study.weighted_by_account.values())
    return {
        "study_id": study.extract.study_id,
        "revenue_cents_by_cohort": {cohort: study.cohort_revenue(cohort) for cohort in study.order},
        "weighted_revenue_by_cohort": {cohort: study.cohort_weighted(cohort) for cohort in study.order},
        "total_revenue_cents": sum(study.plain_by_account.values()),
        "weighted_revenue_total_cents": weighted_total,
        "unhonored_cents": sum(study.unhonored_by_account.values()),
        "weighted_share_by_cohort": {
            cohort: fraction_text(study.cohort_weighted(cohort), weighted_total) for cohort in study.order
        },
    }


def segment_totals(study: Study) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for account in sorted(study.cohort_index):
        segment = study.extract.segment_of(account)
        bucket = totals.get(segment)
        if bucket is None:
            bucket = totals[segment] = {"accounts": 0, "revenue_cents": 0, "weighted_revenue_cents": 0}
        bucket["accounts"] += 1
        bucket["revenue_cents"] += study.plain_by_account[account]
        bucket["weighted_revenue_cents"] += study.weighted_by_account[account]
    return totals


def segments_report(study: Study) -> dict[str, Any]:
    return {"study_id": study.extract.study_id, "segments": segment_totals(study)}


def data_quality_report(study: Study) -> dict[str, Any]:
    removed = study.audit.removed_counts
    return {
        "study_id": study.extract.study_id,
        "input_event_count": len(study.extract.events),
        "clean_event_count": len(study.audit.clean),
        "malformed_event_count": removed["malformed"],
        "out_of_calendar_event_count": removed["out_of_calendar"],
        "duplicate_event_count": removed["duplicate"],
        "excluded_event_count": removed["excluded"],
        "unknown_account_event_count": removed["unknown_account"],
        "excluded_account_count": len(study.extract.excluded),
        "merge_rule_count": study.extract.merge_count,
        "pre_cohort_activity_count": study.pre_cohort_events,
        "control_mismatches": list(study.extract.control_mismatches),
        "rejections": study.audit.register,
    }


def reconciliation_report(study: Study) -> dict[str, Any]:
    by_segment = segment_totals(study).values()
    cohort_sizes = sum(len(study.members[cohort]) for cohort in study.order)
    cohort_revenue = sum(study.cohort_revenue(cohort) for cohort in study.order)
    cohort_weighted = sum(study.cohort_weighted(cohort) for cohort in study.order)
    offset_zero_gap = 0
    if study.extract.offset_zero_is_full:
        offset_zero_gap = sum(study.counts(cohort)[0] - len(study.members[cohort]) for cohort in study.order)
    return {
        "study_id": study.extract.study_id,
        "cohort_size_residual": cohort_sizes - sum(bucket["accounts"] for bucket in by_segment),
        "revenue_residual_cents": cohort_revenue - sum(bucket["revenue_cents"] for bucket in by_segment),
        "weighted_revenue_residual_cents": cohort_weighted
        - sum(bucket["weighted_revenue_cents"] for bucket in by_segment),
        "offset_zero_residual": offset_zero_gap,
        "control_value_residual_cents": study.extract.control_value_residual,
    }


def study_audit_report(study: Study) -> dict[str, Any]:
    extract = study.extract
    return {
        "study_id": extract.study_id,
        "max_offset": extract.horizon,
        "qualifying_event_types": sorted(extract.qualifying),
        "activity_event_types": sorted(extract.activity),
        "revenue_event_types": sorted(extract.revenue_types),
        "minimum_value_cents": extract.minimum_cents,
        "plan_weights": dict(extract.weights),
        "weight_overrides": dict(extract.overrides),
    }


def cohort_report(study: Study, cohort: str) -> dict[str, Any]:
    return {
        "study_id": study.extract.study_id,
        "cohort": cohort,
        "size": len(study.members[cohort]),
        "members": list(study.members[cohort]),
        "active_counts": offsets(study.counts(cohort)),
        "retention_rates": rates(study, cohort, study.counts(cohort)),
        "survival_rates": rates(study, cohort, study.survivors(cohort)),
        "revenue_cents": study.cohort_revenue(cohort),
        "weighted_revenue_cents": study.cohort_weighted(cohort),
    }


REPORTS: dict[str, Callable[[Study], dict[str, Any]]] = {
    "cohorts.json": cohorts_report,
    "retention.json": retention_report,
    "survival.json": survival_report,
    "revenue.json": revenue_report,
    "segments.json": segments_report,
    "data_quality.json": data_quality_report,
    "reconciliation.json": reconciliation_report,
    "study_audit.json": study_audit_report,
}
PER_COHORT_REPORTS = 2


def render(study: Study) -> dict[str, dict[str, Any]]:
    documents = {name: build(study) for name, build in REPORTS.items()}
    for cohort in study.order[:PER_COHORT_REPORTS]:
        documents[f"cohort_{cohort}.json"] = cohort_report(study, cohort)
    return documents


def save(documents: dict[str, dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(documents):
        text = json.dumps(documents[name], indent=2, sort_keys=True, ensure_ascii=True)
        (out_dir / name).write_text(text + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    save(render(build_study(load_extract(Path(argv[1])))), Path(argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
