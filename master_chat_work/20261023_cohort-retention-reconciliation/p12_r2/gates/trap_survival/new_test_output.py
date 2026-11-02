"""Verifier for the cohort-retention-reconciliation domain-calculation task.

Expected artifacts are derived from the study contract (schema.md read together
with audit_policy.md) by the reference in this file; solution/solve.py is a
separate implementation written from the same contract, so the oracle run
cross-checks the two. Most of the weight sits on whole downstream documents
derived from freshly generated studies the agent never sees: new calendars, plan
and segment codes, merge chains, plan histories, revenue event types and dirty
rows. Small fixtures built on the shipped study isolate single rules.

Negative-weight tests are polarity-inverted: the assertion HOLDS when the cheat is
present, so an honest agent's negative tests fail and add no weight. Every
negative stands down when the delivered program does not run cleanly.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false

from __future__ import annotations

import ast
import base64
import csv
import fcntl
import io
import json
import os
import pwd
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import zlib
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from rewardkit import criteria, criterion

HIDDEN_SEEDS = (0x5A17C0DE1203, 0x3B90E1F4A7, 0x7C4D2E9B015F)
SAMPLE_SEED = 0x1D2C3B4A5968
CHALLENGE_SEED = 0x6E5F4A3B2C1D
OUT = Path("/app/out")
SCRIPT = OUT / "derive_report.py"
CORPUS = Path("/app/data")
FIXED_ARTIFACTS = (
    "cohorts.json",
    "retention.json",
    "survival.json",
    "revenue.json",
    "segments.json",
    "data_quality.json",
    "reconciliation.json",
    "study_audit.json",
)
SHIPPED_PER_COHORT = ("cohort_2026-P1.json", "cohort_2026-P2.json")
REASONS = ("malformed", "out_of_calendar", "duplicate", "excluded", "unknown_account")
EVENT_HEADER = ("event_id", "account_id", "event_date", "event_type", "value_cents")
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_LOCK_FILE = Path(tempfile.gettempdir()) / "crr-grader.lock"
_NETWORK_MODULES = {"socket", "ssl", "http.client", "urllib.request", "ftplib", "smtplib"}

# Every file in environment/data, zlib-compressed then base64-encoded.
_SHIPPED_DATA: dict[str, str] = {"account_merges.csv": "eNpLK8rPjU9MTs4vzSuJz0zRKclH5qWmpaUml2SWpcanAdVxJRoYmOsACWMdIwMjM10DI10DQ5CgBUjQCCpoDBa0NDDUARIGUEFDkCAAmqYeVg==", "accounts.csv": "eNptkLsOwjAMRXe+Ih/gobzpWN5IMAADI3JSCwXyqJww9O9pJApUYrBk6R4fW0al/NPFqy4B361DSxDoZslFqAy6HmZZHwoTvTjXIZINEKwEiUGrlA1gTqi8ExfPjwC2cVXsUzKEBZXIonBo6qhVgORsirhiHSgxI1iSiShOFFGbrnkMKyuJxR5lxzuB9d1zKQ5UauyOTGHD6HQksacbqvrPxhlskaXnlviI8yyDXUKbc8Wx+BXnzQd+onb0S7wACHhvhA==", "audit_policy.md": "eNqVVsGO3DYMvesrCOwhLTDrD0iu6a0BiiBAkNNIa9G2EllyRXld/31JSZ7x7PbSPSxmJYp8fHyPs0/wFTOG7GIAyqvdwazWZViid/2u1LfJUfsDxviKKRDkLbbYhH1Mlj5CnhAWbwKYYGFDN06Zz0wGsyx+hxz5Qpm+j2vIHwjwlUvSpUTL04Sjo4wJ4gApblTf9h5NcGHk65lLUwffONaabKCPISfTZ3ABNPUTzqabrQaLAyZSXI972CZMXCmVEgX0guaXgJEDMjPC4MY1YafU0xP8xfhJOkbQ0ovmKn6dg4DSDTt1Pb1qcHTuGNolxAUDWoihgz+NtCMBqp9MGJHAJGyEcYzgltsr85tj2kveCz9FIQAWflzfXWBzeVIHgKuzHNbwCX0ahwH77F7xOqQ460pSQcY1hph6lN8PMPmjYhrxoQ/u0mUCz+eU/wNcwbVNkfBdTckTg+IqL8i1sI5PKnySIYRK/tpPdbg0mSPmbaZLweMLeRyruAU5GJxH5iGwBL5LvhALGhGXQ6qPhHwRy9H6+5G5oAofJUlVhmkKgJVkQjeOWKOS5yIymlmFJ55urMaCTRUtc3whVJiWyINq+VwCePIUPYu4eGGQ/mZMIwPuquSaaXgK7ysJdh4Np0n7XTn1BXU/KQYmbg0eqeBUmnCc8da6UHUAazeN/UeKRlfwFT8WsPboQ02G2WHawzPOS95B1+JX2QjJWdSfakYXMo7cWxVWHV7rjBkW2bPNja2G+4o/ZfbM4+F/pXQ6DkmXVsXu179X413ea6vgObbsEGZD11Vyb/Rhc6i2OaqxKn9LldYFKKbMkF6OJGKtDv4wLNMa2Rvu7WAkbh9I3QOr9xIaEqRVgS2hwDvm2ALYF/7mnuIvGVORMHGZJbMELQsCuROlnkHPxvPEZrT641FeOL0dyzs5v+1BXnwuoOikk/dx5dkM1954DNake5ZDqOLYNROPrhF5hAo/LtqSxa7sr57D+T3rEU1iu6VqvbCX9VpmdJ7B1JCV9XreWgqO7dCEfznFVV4Fmb59KZxv8r6gLpjwn96v9kbM2WiC62wzFpbY5ui37ZKSgFhgDEhGVbKu4VeIW7i2dP8/uXkhsZUsMc77aCwe6buBXE6dVC29hQAB0b4Zm4hWjnYlGzTEXMTEYWXDP2zoE6GDcf5RLocKihR/M2wT4+8KKFdbcpn/MRCh6R/88/zly/Pnz/r3+v0SOVu6qVvAGL+ZnRqeTv0Lvcz/jw==", "events.csv": "eNp9kt1ugzAMhe/3FHuAMCV2QuBpKkSzDWmiVfmR+vazAyI2lcoFAj5jH5+ctKZxvgxX0/X9bdkeU/527ea0P87PezJr97ekS0/v00ey1pmOb2ChrqyrbDDT8DMud2OZAlMoNCqKTLHQlqbPw9rNw23cKrzuDtbcl0f/203J+GBzSdAjAMyUpunoUDP2O4aKxkkFkWkoNLwoaKQCqJzV7Vs5nTAUgbHNAukPsSWV+FLi2r0muxhLTa2mOJAisLL+xQaHck8qOXXIRtYFN9IGlz1sDuqEzbArrKVTyIuq/lH6gLykwo30gHCjcSv38+SAwmDlbp5P6ZC3qQMn1/N5PdmA/KPCIyNOhRRQUmBaDsjyxUX+Xc4hSHcC51TNV+Zt8yWOLKBkjP8WvRtJUW0fdnGttpcaPNL3Ml6N3/xBK3uEs8Ho3spH0AnGE8Z36fzaBJB9McbjgE7xwaDjA2LHz5zwfzTRL0I=", "exclusions.csv": "eNpLTE7OL80ric9M0SlKTSzOz+NKtDQw0MnMK0ktykvMUShJLS5RSIQo4gIAfZsQUg==", "extract_manifest.json": "eNqVUk1v2zAMvedXPPhsBNnaHLbd9xd2NBiJsTUoUkDRTo2i/72UnQVLB6TYUXx8HyL5ugEafjlnUfbdYW6+o0mhHzTOIKdhCjpjxZu29h5D5GJdr/awJzmXx6TdiaXnsnVlumGGelLqJF8q4WkpvrV3vIeML7s7Ck/8CeFp3/4pTxRH7lxldGU8VbX9frf7oPji4lhCTo9j3HHOLCH7zlHk5EkeEZ/viZFSN4SiWeZHrK//ss4S3P8Mt3B/+nRWK2NzZTUpK9fl/5KgygmHGTrwdfX4nQ+4DFZeayp2G7hQgRu1RckgCJNngSNr4hhruzULbG0yo54NSCRM7A3Kkbf4mQ0lNyxgi1s6rKexeMWQuICOakr1PawutXwVuF1Fiw9LB3m/qvwFIB+vkaofzK9douMSdEAZRczch9SjnMmmbuApW+gf9sVFxgRJERbhBBtb/fuYqm618qEP5rKDZnxbE1jPYILbZvO2eQfQRA63", "period_calendar.csv": "eNorSC3KzE/RKS5JLCqJT0ksSdVJzUsBM7iMDIzMdAMMdcC0gSEQwZnGhlBZI6iQEULWSNfIAiprDBUyRsgaI/SaQIVMELImusYGXADSXSEA", "plan_history.csv": "eNotyVEKgCAMANB/z7LBHNJ1RGwDoTZZ1vkj6Pe91rvfturYYR7NQFSlr/FI1fAzNaICMxyYeEMqmOkzBrElMWNc8hdj5vQCGTUX+w==", "plan_prices.csv": "eNoryEnM08nNzyvJyKmMLyjKTE6NT07NKynmSkoszkzWsTQw4CooytcxAjGA4qlFQDXFqTqWID4AndgURw==", "plan_weights.json": "eNqrVkpKLM5MVrJSMNRRUCooygeyjIGs1LyS1KKCosziVKCAaS0XAO5oC6I=", "qualifying_rules.json": "eNpty8sKAjEMheG9TzFk7cK1ryJSSk3GQG82TaHKvLutIAjj8nD+7wUPtZ6pc1wNNozV1J5R4LxcQHiNmuG4gHWVm62cIly/k2vfCxSZ0WiyFne3gn94mUxxp39JQdJ4++SBIwcNplk/kBtm5qfxJCLBap5YkmExpN6Ph6wX3A5vveNNtg==", "schema.md": "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", "segments.csv": "eNoVy8EJgDAMBdB7p+gAmULw2JMDSEs/GkyqJFHXF9/9OTbFCJLaIPSCtz3W84EZdyTXRotWkTzdzgPulJQ7Fe65VDsQlP49j4Bdxg5KH/grHao=", "study_config.json": "eNqrViouKU2pjM9MUbJSUHIOCtI1gAAjg1TLNDOzNCMlHQWl3MSK+Py0tOLUEqAqY6BATmJSag5Ih4ehrpGBkZlCUWpJal5JZn6eAtg8pVouAJKZGlA="}


# ---------------------------------------------------------------------------
# Reference derivation, written from the contract
# ---------------------------------------------------------------------------

_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_CENTS = re.compile(r"[0-9]+")


def _table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _real_day(text: str) -> date | None:
    if _DAY.fullmatch(text) is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _rate(numerator: int, denominator: int) -> str:
    return "0" if denominator == 0 else str(Fraction(numerator, denominator))


def _id(text: str) -> str:
    return text.strip().lower()


def _in_force(rows: list[tuple[str, date, int, str]], key: str, day: date) -> str | None:
    best: tuple[date, int, str] | None = None
    for owner, start, position, value in rows:
        if owner == key and start <= day and (best is None or (start, position) > best[:2]):
            best = (start, position, value)
    return None if best is None else best[2]


def _manifest_check(root: Path) -> tuple[list[str], int]:
    path = root / "extract_manifest.json"
    if not path.is_file():
        return [], 0
    manifest = json.loads(path.read_text(encoding="utf-8"))
    off: list[str] = []
    residual = 0
    for name, figures in manifest.get("files", {}).items():
        target = root / name
        lines = target.read_text(encoding="utf-8").splitlines() if target.is_file() else []
        values = [(row.get("value_cents") or "").strip() for row in _table(target)] if target.is_file() else []
        counted = {
            "data_rows": max(len(lines) - 1, 0),
            "value_cents_sum": sum(int(v) for v in values if _CENTS.fullmatch(v)),
        }
        for figure, recorded in figures.items():
            if counted.get(figure) != recorded:
                off.append(f"{name}:{figure}")
            if name == "events.csv" and figure == "value_cents_sum":
                residual = recorded - counted["value_cents_sum"]
    return sorted(off), residual


def derive(root: Path) -> dict[str, dict[str, Any]]:
    config = json.loads((root / "study_config.json").read_text(encoding="utf-8"))
    rules = json.loads((root / "qualifying_rules.json").read_text(encoding="utf-8"))
    weights = {_id(k): int(v) for k, v in json.loads((root / "plan_weights.json").read_text(encoding="utf-8")).items()}
    accounts = {_id(row["account_id"]): row for row in _table(root / "accounts.csv")}
    overrides = {
        _id(row["segment"]): int(row["weight_override"].strip())
        for row in _table(root / "segments.csv")
        if (row.get("weight_override") or "").strip()
    }
    merge_table = _table(root / "account_merges.csv")
    merges = [
        (_id(row["from_account_id"]), date.fromisoformat(row["effective_from"]), i, _id(row["to_account_id"]))
        for i, row in enumerate(merge_table)
    ]
    plan_rows = [
        (_id(row["account_id"]), date.fromisoformat(row["effective_from"]), i, _id(row["plan"]))
        for i, row in enumerate(_table(root / "plan_history.csv"))
    ]
    barred = {_id(row["account_id"]) for row in _table(root / "exclusions.csv")}
    calendar = sorted(
        (date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"]), row["period"])
        for row in _table(root / "period_calendar.csv")
    )
    order = [period for _, _, period in calendar]
    rank = {period: i for i, period in enumerate(order)}
    sid = config["study_id"]
    horizon = int(config["max_offset"])
    qualifying = {_id(k) for k in rules["qualifying_event_types"]}
    activity = {_id(k) for k in rules["activity_event_types"]}
    revenue_types = {_id(k) for k in rules["revenue_event_types"]}
    floor = int(rules["minimum_value_cents"])
    mismatches, value_residual = _manifest_check(root)

    def period_on(day: date) -> str | None:
        return next((period for start, end, period in calendar if start <= day <= end), None)

    def owner_on(account: str, day: date) -> str:
        visited = {account}
        while True:
            nxt = _in_force(merges, account, day)
            if nxt is None or nxt in visited:
                return account
            visited.add(nxt)
            account = nxt

    def segment_of(account: str) -> str:
        return _id(accounts[account]["segment"])

    def weight_on(account: str, day: date) -> int:
        if segment_of(account) in overrides:
            return overrides[segment_of(account)]
        return weights.get(_in_force(plan_rows, account, day) or _id(accounts[account]["plan"]), 0)

    raw = _table(root / "events.csv")
    seen: set[tuple[str, str, str]] = set()
    survivors: set[tuple[str, str, str]] = set()
    tally = dict.fromkeys(REASONS, 0)
    register: list[dict[str, Any]] = []
    kept: list[tuple[date, str, str, int, str]] = []
    for row in raw:
        account, kind = _id(row["account_id"]), _id(row["event_type"])
        key = (account, row["event_date"], kind)
        day = _real_day(row["event_date"])
        broken = day is None or _CENTS.fullmatch(row["value_cents"]) is None
        tags = {"malformed"} if broken else set()
        if key in seen:
            tags.add("duplicate")
        seen.add(key)
        period = who = None
        if day is not None:
            period = period_on(day)
            who = owner_on(account, day)
            if period is None:
                tags.add("out_of_calendar")
            if who in barred:
                tags.add("excluded")
            if who not in accounts:
                tags.add("unknown_account")
        if broken:
            removed_by = "malformed"
        elif period is None:
            removed_by = "out_of_calendar"
        elif key in survivors:
            removed_by = "duplicate"
        else:
            survivors.add(key)
            removed_by = "excluded" if who in barred else ("unknown_account" if who not in accounts else "")
        if removed_by:
            tally[removed_by] += 1
            register.append({"event_id": row["event_id"], "reasons": sorted(tags)})
        else:
            kept.append((day, who, kind, int(row["value_cents"]), period))
    kept.sort(key=lambda item: (item[0], item[1], item[2]))
    register.sort(key=lambda item: item["event_id"])

    cohort_of: dict[str, str] = {}
    for day, who, kind, cents, period in kept:
        if kind in qualifying and cents >= floor and who not in cohort_of:
            cohort_of[who] = period
    cohorts = sorted(set(cohort_of.values()), key=rank.__getitem__)
    members = {c: sorted(a for a, p in cohort_of.items() if p == c) for c in cohorts}

    early = 0
    seen_in: set[tuple[str, str]] = set()
    for day, who, kind, cents, period in kept:
        if kind not in activity or who not in cohort_of:
            continue
        if rank[period] < rank[cohort_of[who]]:
            early += 1
        else:
            seen_in.add((who, period))

    plain: dict[str, int] = dict.fromkeys(cohort_of, 0)
    heavy: dict[str, int] = dict.fromkeys(cohort_of, 0)
    short: dict[str, int] = dict.fromkeys(cohort_of, 0)
    balance: dict[str, int] = {}
    for day, who, kind, cents, period in kept:
        if kind not in revenue_types:
            continue
        if kind == "purchase":
            booked, lost = cents, 0
        else:
            booked = -min(cents, balance.get(who, 0))
            lost = cents + booked
        balance[who] = balance.get(who, 0) + booked
        if who in cohort_of:
            plain[who] += booked
            heavy[who] += booked * weight_on(who, day)
            short[who] += lost

    active_counts: dict[str, dict[str, int]] = {}
    retention: dict[str, dict[str, str]] = {}
    survival: dict[str, dict[str, str]] = {}
    revenue: dict[str, int] = {}
    weighted: dict[str, int] = {}
    for c in cohorts:
        size = len(members[c])
        counts: dict[str, int] = {}
        for offset in range(horizon + 1):
            if rank[c] + offset >= len(order):
                break
            target = order[rank[c] + offset]
            counts[str(offset)] = sum((a, target) in seen_in for a in members[c])
        active_counts[c] = counts
        retention[c] = {k: _rate(v, size) for k, v in counts.items()}
        floor_so_far = None
        survival[c] = {}
        for k, v in counts.items():
            floor_so_far = v if floor_so_far is None else min(floor_so_far, v)
            survival[c][k] = _rate(floor_so_far, size)
        revenue[c] = sum(plain[a] for a in members[c])
        weighted[c] = sum(heavy[a] for a in members[c])

    segments: dict[str, dict[str, int]] = {}
    for account in cohort_of:
        entry = segments.setdefault(
            segment_of(account), {"accounts": 0, "revenue_cents": 0, "weighted_revenue_cents": 0}
        )
        entry["accounts"] += 1
        entry["revenue_cents"] += plain[account]
        entry["weighted_revenue_cents"] += heavy[account]

    total = sum(revenue.values())
    weighted_total = sum(weighted.values())
    zero_gap = 0
    if rules["offset_zero_is_full"]:
        zero_gap = sum(active_counts[c].get("0", 0) - len(members[c]) for c in cohorts)

    docs: dict[str, dict[str, Any]] = {
        "cohorts.json": {
            "study_id": sid,
            "cohort_sizes": {c: len(members[c]) for c in cohorts},
            "cohort_members": members,
            "cohorted_account_count": len(cohort_of),
        },
        "retention.json": {"study_id": sid, "active_counts": active_counts, "retention_rates": retention},
        "survival.json": {"study_id": sid, "survival_rates": survival},
        "revenue.json": {
            "study_id": sid,
            "revenue_cents_by_cohort": revenue,
            "weighted_revenue_by_cohort": weighted,
            "total_revenue_cents": total,
            "weighted_revenue_total_cents": weighted_total,
            "unhonored_cents": sum(short.values()),
            "weighted_share_by_cohort": {c: _rate(weighted[c], weighted_total) for c in cohorts},
        },
        "segments.json": {"study_id": sid, "segments": segments},
        "data_quality.json": {
            "study_id": sid,
            "input_event_count": len(raw),
            "clean_event_count": len(kept),
            "malformed_event_count": tally["malformed"],
            "out_of_calendar_event_count": tally["out_of_calendar"],
            "duplicate_event_count": tally["duplicate"],
            "excluded_event_count": tally["excluded"],
            "unknown_account_event_count": tally["unknown_account"],
            "excluded_account_count": len(barred),
            "merge_rule_count": len(merge_table),
            "pre_cohort_activity_count": early,
            "control_mismatches": mismatches,
            "rejections": register,
        },
        "reconciliation.json": {
            "study_id": sid,
            "cohort_size_residual": len(cohort_of) - sum(s["accounts"] for s in segments.values()),
            "revenue_residual_cents": total - sum(s["revenue_cents"] for s in segments.values()),
            "weighted_revenue_residual_cents": weighted_total
            - sum(s["weighted_revenue_cents"] for s in segments.values()),
            "offset_zero_residual": zero_gap,
            "control_value_residual_cents": value_residual,
        },
        "study_audit.json": {
            "study_id": sid,
            "max_offset": horizon,
            "qualifying_event_types": sorted(qualifying),
            "activity_event_types": sorted(activity),
            "revenue_event_types": sorted(revenue_types),
            "minimum_value_cents": floor,
            "plan_weights": weights,
            "weight_overrides": overrides,
        },
    }
    for c in cohorts[:2]:
        docs[f"cohort_{c}.json"] = {
            "study_id": sid,
            "cohort": c,
            "size": len(members[c]),
            "members": members[c],
            "active_counts": active_counts[c],
            "retention_rates": retention[c],
            "survival_rates": survival[c],
            "revenue_cents": revenue[c],
            "weighted_revenue_cents": weighted[c],
        }
    return docs


# ---------------------------------------------------------------------------
# Study generator for unseen extracts
# ---------------------------------------------------------------------------


class Rng:
    __slots__ = ("state",)
    _MASK = (1 << 64) - 1

    def __init__(self, seed: int):
        self.state = (seed & self._MASK) or 0xA0761D6478BD642F

    def _next(self) -> int:
        x = self.state
        x ^= x >> 12
        x ^= (x << 25) & self._MASK
        x ^= x >> 27
        self.state = x & self._MASK
        return (x * 0x2545F4914F6CDD1D) & self._MASK

    def between(self, lo: int, hi: int) -> int:
        return lo + self._next() % (hi - lo + 1)

    def pick(self, seq):
        return seq[self.between(0, len(seq) - 1)]

    def shuffle(self, items: list) -> list:
        for i in range(len(items) - 1, 0, -1):
            j = self.between(0, i)
            items[i], items[j] = items[j], items[i]
        return items

    def sample(self, seq, k: int) -> list:
        return self.shuffle(list(seq))[:k]


_PLAN_POOL = ("basic", "pro", "enterprise", "starter", "team", "scale")
_SEGMENT_POOL = ("smb", "mid", "ent", "gov", "edu")
_QUALIFIER_POOL = ("signup", "activation", "trial_start")
_SUBTRACTING_POOL = ("refund", "chargeback", "credit_note", "reversal")
_BAD_VALUES = ("12.5", "-300", "n/a", "1e3", "")


def _csv_text(header, rows) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def _shipped_texts() -> dict[str, str]:
    return {name: zlib.decompress(base64.b64decode(blob)).decode("utf-8") for name, blob in _SHIPPED_DATA.items()}


def _study_files(seed: int) -> dict[str, str]:
    rng = Rng(seed)
    year = rng.between(2024, 2027)
    tag = rng.pick("PSMQ")
    cursor = date(year, rng.between(1, 5), 1)
    periods: list[tuple[str, date, date]] = []
    for k in range(rng.between(4, 6)):
        end = cursor + timedelta(days=rng.between(26, 35) - 1)
        periods.append((f"{year}-{tag}{k + 1}", cursor, end))
        cursor = end + timedelta(days=1)
    span = len(periods)
    first_day, last_day = periods[0][1], periods[-1][2]

    def day_between(lo: date, hi: date) -> date:
        return lo + timedelta(days=rng.between(0, (hi - lo).days))

    def day_in(k: int) -> date:
        return day_between(periods[k][1], periods[k][2])

    plans = rng.sample(_PLAN_POOL, 3)
    weights = dict(zip(plans, rng.sample(range(1, 10), 3)))
    segments = rng.sample(_SEGMENT_POOL, rng.between(3, 4))
    qualifiers = rng.sample(_QUALIFIER_POOL, 2)
    activity = ["session", "purchase"]
    if rng.between(0, 1):
        activity.append("login")
    if rng.between(0, 1):
        activity.append(qualifiers[0])
    subtracting = [rng.pick(_SUBTRACTING_POOL[1:3])]
    if rng.between(0, 1):
        subtracting.append(rng.pick((_SUBTRACTING_POOL[0], _SUBTRACTING_POOL[3])))
    revenue_types = ["purchase", *subtracting]
    minimum = rng.between(2, 15) * 100
    flag = rng.between(0, 3) != 0
    horizon = rng.between(2, 4)

    prefix = rng.pick("abcdkmnq")
    used: set[str] = set()

    def fresh() -> str:
        while True:
            ident = f"{prefix}{rng.between(1, 999):03d}"
            if ident not in used:
                used.add(ident)
                return ident

    accounts: dict[str, tuple[str, str]] = {}

    def enrol(ident: str) -> None:
        accounts[ident] = (rng.pick(segments), rng.pick(plans))

    real = [fresh() for _ in range(rng.between(8, 11))]
    legacy = [fresh() for _ in range(4)]
    barred = fresh()
    for ident in [*real, *legacy, barred]:
        enrol(ident)
    vault, heir, old = fresh(), fresh(), fresh()
    enrol(vault)
    heir_segment, old_segment = rng.sample(segments, 2)
    accounts[heir] = (heir_segment, rng.pick(plans))
    accounts[old] = (old_segment, rng.pick(plans))
    overrides = {heir_segment: rng.between(10, 19)}
    spare = [s for s in segments if s not in (heir_segment, old_segment)]
    if spare and rng.between(0, 1):
        overrides[spare[0]] = rng.between(10, 19)
    ghost = fresh()
    strangers = [fresh() for _ in range(2)]
    absent_bar = fresh()

    events: list[list[str]] = []

    def emit(account: str, day: date | str, kind: str, value: int | str) -> list[str]:
        row = [account, day if isinstance(day, str) else day.isoformat(), kind, str(value)]
        events.append(row)
        return row

    def qual_value() -> int:
        return rng.between(minimum, minimum + 900) if minimum else 0

    def revenue_value() -> int:
        return rng.between(1, 200) * 100 + rng.between(0, 99)

    cohort_at: dict[str, int | None] = {}
    for i, account in enumerate(real):
        if i == len(real) - 1:
            start = None
        elif i < 2:
            start = i
        elif i == 2:
            start = rng.between(1, span - 2)
        else:
            start = rng.between(0, span - 2)
        cohort_at[account] = start
        if start is not None:
            if minimum and rng.between(0, 2) == 0:
                emit(account, day_in(max(start - 1, 0)), rng.pick(qualifiers), rng.between(0, minimum - 1))
            emit(account, day_in(start), rng.pick(qualifiers), qual_value())
            if start >= 1 and rng.between(0, 2) == 0:
                emit(account, day_in(rng.between(0, start - 1)), "session", 0)
        for k in range(start or 0, span):
            for _ in range(rng.between(0, 2)):
                kind = rng.pick(activity)
                emit(account, day_in(k), kind, revenue_value() if kind == "purchase" else 0)
            if rng.between(0, 3) == 0:
                emit(account, day_in(k), rng.pick(subtracting), rng.between(1, 40) * 100)
            if rng.between(0, 4) == 0:
                emit(account, day_in(k), "page_view", 0)

    ra, rb, rc, rd, rp = real[2], real[3], real[4], real[5], real[6]
    rq = real[0]
    l1, l2, l3, l4 = legacy
    d_a, d_b = day_in(1), day_in(2)
    d_c, d_d = day_in(1), day_in(2)
    d_e, d_f = day_in(1), day_in(2)
    merges = [
        (l1, l2, d_a),
        (l2, ra, d_b),
        (l3, rb, d_c),
        (l3, rc, d_d),
        (l4, barred, d_e),
        (ghost, rd, d_f),
    ]
    emit(l1, day_in(0), rng.pick(qualifiers), qual_value())
    emit(l1, day_between(d_a, d_b - timedelta(days=1)), "session", 0)
    emit(l1, d_b, "purchase", revenue_value())
    emit(l1, day_between(d_b, last_day), "purchase", revenue_value())
    emit(l1, day_between(d_b, last_day), subtracting[0], rng.between(1, 30) * 100)
    emit(l2, day_between(periods[1][1], d_b - timedelta(days=1)), "session", 0)
    emit(l2, day_between(d_b, last_day), "purchase", revenue_value())
    emit(l3, day_in(0), rng.pick(qualifiers), qual_value())
    emit(l3, day_between(d_c, d_d - timedelta(days=1)), "purchase", revenue_value())
    emit(l3, d_d, "purchase", revenue_value())
    emit(l3, day_between(d_d, last_day), "purchase", revenue_value())
    emit(l3, day_between(d_d, last_day), "session", 0)
    emit(l4, day_in(0), rng.pick(qualifiers), qual_value())
    emit(l4, day_between(first_day, d_e - timedelta(days=1)), "purchase", revenue_value())
    emit(l4, d_e, "purchase", revenue_value())
    emit(l4, day_between(d_e, last_day), "session", 0)
    emit(barred, day_in(0), rng.pick(qualifiers), qual_value())
    emit(barred, day_in(1), "purchase", revenue_value())
    emit(ghost, day_between(first_day, d_f - timedelta(days=1)), "session", 0)
    emit(ghost, day_between(d_f, last_day), "purchase", revenue_value())
    emit(ghost, day_between(d_f, last_day), rng.pick(qualifiers), qual_value())
    for stranger in strangers:
        emit(stranger, day_in(rng.between(0, span - 1)), rng.pick(qualifiers), qual_value())
        emit(stranger, day_in(rng.between(0, span - 1)), "purchase", revenue_value())
    emit(absent_bar, day_in(rng.between(0, span - 1)), "session", 0)

    # Ledger accounts: subtracting events that meet an empty or short balance.
    emit(vault, day_in(0), rng.pick(qualifiers), qual_value())
    emit(vault, day_in(1), subtracting[0], rng.between(3, 9) * 100)
    d_v = day_in(2)
    emit(vault, d_v, "purchase", rng.between(20, 40) * 100)
    emit(vault, d_v, subtracting[0], rng.between(5, 15) * 100)
    emit(vault, day_between(d_v + timedelta(days=1), last_day), rng.pick(subtracting), rng.between(50, 90) * 100)
    d_m = day_in(1)
    merges_extra = (old, heir, d_m)
    emit(heir, day_in(0), rng.pick(qualifiers), qual_value())
    emit(heir, day_in(1), "session", 0)
    emit(old, day_between(first_day, d_m - timedelta(days=1)), "purchase", rng.between(30, 60) * 100)
    after = rng.between(10, 25) * 100
    emit(old, d_m, "purchase", after)
    emit(old, day_between(d_m + timedelta(days=1), last_day), rng.pick(subtracting), after + rng.between(5, 25) * 100)

    def other_plan(account: str, avoid: str | None = None) -> str:
        choices = [p for p in plans if p != accounts[account][1] and p != avoid]
        return rng.pick(choices)

    d_p = day_in(rng.between(cohort_at[rp] or 0, span - 1))
    emit(rp, d_p, "purchase", revenue_value())
    d_q = day_in(1)
    emit(rq, d_q, "purchase", revenue_value())
    emit(rq, day_in(2), "purchase", revenue_value())
    tie_first = other_plan(rq)
    tie_second = other_plan(rq, tie_first) if len(plans) > 2 else accounts[rq][1]
    plan_blocks = [
        [(rp, other_plan(rp), d_p)],
        [(rq, tie_first, d_q), (rq, tie_second, d_q)],
        [(rc, other_plan(rc), d_d)],
        [(l3, other_plan(l3), first_day)],
        [(rb, other_plan(rb), first_day - timedelta(days=rng.between(5, 40)))],
        [(real[1], other_plan(real[1]), last_day + timedelta(days=rng.between(1, 20)))],
    ]
    rng.shuffle(plan_blocks)
    plan_history = [row for block in plan_blocks for row in block]

    merges.append(merges_extra)
    rng.shuffle(events)

    def insert_after(index: int, row: list[str]) -> None:
        events.insert(rng.between(index + 1, len(events)), row)

    for _ in range(4):
        index = rng.between(0, len(events) - 1)
        insert_after(index, list(events[index]))
    index = rng.between(0, len(events) - 1)
    original = events[index]
    events.insert(index, [*original[:3], rng.pick(_BAD_VALUES)])
    index = rng.between(0, len(events) - 1)
    insert_after(index, [*events[index][:3], rng.pick(_BAD_VALUES)])

    late = [a for a in real if (cohort_at[a] or 0) >= 1 and a not in (ra,)]
    early_day = periods[0][1] + timedelta(days=rng.between(0, 8))
    good = qual_value() or rng.between(1, 9) * 100
    value_tricks = (f"+{good}", f" {good}", f"1_{rng.between(0, 999):03d}")
    events.insert(rng.between(0, len(events)), [late[0], early_day.isoformat(), rng.pick(qualifiers), rng.pick(value_tricks)])
    loose_date = f"{early_day.year}-{early_day.month}-{early_day.day}"
    events.insert(rng.between(0, len(events)), [ra, loose_date, rng.pick(qualifiers), str(qual_value())])
    compact = early_day.strftime("%Y%m%d")
    events.insert(rng.between(0, len(events)), [late[-1], compact, rng.pick(qualifiers), str(qual_value())])
    for bad_day in (
        day_in(1).strftime("%Y/%m/%d"),
        f"{year}-02-30",
        "",
        f"{year}-13-0{rng.between(1, 9)}",
    ):
        events.insert(rng.between(0, len(events)), [rng.pick(real), bad_day, "purchase", str(revenue_value())])
    for bad_value in rng.sample(_BAD_VALUES, 3):
        events.insert(rng.between(0, len(events)), [rng.pick(real), day_in(rng.between(0, span - 1)).isoformat(), "purchase", bad_value])
    events.insert(rng.between(0, len(events)), [barred, (last_day + timedelta(days=rng.between(1, 20))).isoformat(), "session", "0"])
    late_twin = [rng.pick(real), (last_day + timedelta(days=3)).isoformat(), "session", "0"]
    position = rng.between(0, len(events))
    events.insert(position, list(late_twin))
    insert_after(position, list(late_twin))
    events.insert(rng.between(0, len(events)), [rng.pick(real), (first_day - timedelta(days=4)).isoformat(), "purchase", "n/a"])
    for k in rng.sample(range(span), 2):
        events.insert(rng.between(0, len(events)), [rng.pick(real), periods[k][1].isoformat(), "session", "0"])
        events.insert(rng.between(0, len(events)), [rng.pick(real), periods[k][2].isoformat(), "purchase", str(revenue_value())])
    spaced_day = f" {early_day.isoformat()}" if rng.between(0, 1) else f"{early_day.isoformat()} "
    events.insert(rng.between(0, len(events)), [late[1], spaced_day, rng.pick(qualifiers), str(qual_value())])
    events.insert(rng.between(0, len(events)), [real[0], day_in(1).isoformat(), "purchase", f" {revenue_value()}"])
    twin_day = early_day.isoformat()
    twin_kind = rng.pick(qualifiers)
    position = rng.between(0, len(events))
    events.insert(position, [late[-2], twin_day, twin_kind, str(rng.between(0, minimum - 1))])
    events.insert(rng.between(position + 1, len(events)), [late[-2].upper(), twin_day, twin_kind, str(qual_value())])
    merged_day = day_between(d_c, d_d - timedelta(days=1)).isoformat()
    position = rng.between(0, len(events))
    events.insert(position, [l3, merged_day, "purchase", str(revenue_value())])
    events.insert(rng.between(position + 1, len(events)), [rb, merged_day, "purchase", str(revenue_value())])
    barred_row = [barred, day_in(rng.between(0, span - 1)).isoformat(), "session", "0"]
    position = rng.between(0, len(events))
    events.insert(position, list(barred_row))
    insert_after(position, list(barred_row))

    def variant(text: str) -> str:
        return rng.pick((text.upper(), f" {text}", f"{text} ", text.title()))

    for row in events:
        if rng.between(0, 6) == 0:
            row[0] = variant(row[0])
        if rng.between(0, 6) == 0:
            row[2] = variant(row[2])

    numbers = rng.sample(range(1000, 10000), len(events))
    event_rows = [[f"ev{n}", *row] for n, row in zip(numbers, events)]

    account_rows = [[a, f"Account {a.upper()}", seg, plan] for a, (seg, plan) in accounts.items()]
    rng.shuffle(account_rows)
    for row in account_rows[:3]:
        row[0] = variant(row[0])
    account_rows[3][2] = variant(account_rows[3][2])
    account_rows[4][3] = variant(account_rows[4][3])
    merge_rows = [[src, dst, day.isoformat()] for src, dst, day in merges]
    rng.shuffle(merge_rows)
    merge_rows[0][0] = variant(merge_rows[0][0])
    merge_rows[1][1] = variant(merge_rows[1][1])
    exclusion_rows = [[barred.upper(), "internal test account"]]
    if rng.between(0, 1):
        exclusion_rows.append([f"{barred} ", "listed twice by the audit team"])
    if rng.between(0, 1):
        exclusion_rows.append([absent_bar, "retired probe"])
    calendar_rows = [[p, s.isoformat(), e.isoformat()] for p, s, e in periods]
    rng.shuffle(calendar_rows)
    docs = _shipped_texts()
    files = {
        "schema.md": docs.get("schema.md", ""),
        "audit_policy.md": docs.get("audit_policy.md", ""),
        "events.csv": _csv_text(EVENT_HEADER, event_rows),
        "accounts.csv": _csv_text(("account_id", "account_name", "segment", "plan"), account_rows),
        "account_merges.csv": _csv_text(("from_account_id", "to_account_id", "effective_from"), merge_rows),
        "exclusions.csv": _csv_text(("account_id", "reason"), exclusion_rows),
        "period_calendar.csv": _csv_text(("period", "start_date", "end_date"), calendar_rows),
        "plan_history.csv": _csv_text(
            ("account_id", "plan", "effective_from"),
            [[variant(a) if i == 0 else a, variant(p) if i == 1 else p, d.isoformat()] for i, (a, p, d) in enumerate(plan_history)],
        ),
        "plan_prices.csv": _csv_text(("plan", "monthly_price_cents"), [[p, rng.between(5, 99) * 100] for p in plans]),
        "plan_weights.json": json.dumps(weights, indent=2) + "\n",
        "segments.csv": _csv_text(
            ("segment", "label", "weight_override"),
            [[s.upper() if i == 0 else s, s.title(), str(overrides.get(s, ""))] for i, s in enumerate(segments)],
        ),
        "qualifying_rules.json": json.dumps(
            {
                "qualifying_event_types": [qualifiers[0].title(), qualifiers[1]],
                "activity_event_types": [f" {activity[0]}", *activity[1:]],
                "revenue_event_types": [revenue_types[0], revenue_types[1].title(), *revenue_types[2:]],
                "minimum_value_cents": minimum,
                "offset_zero_is_full": flag,
            },
            indent=2,
        )
        + "\n",
        "study_config.json": json.dumps(
            {"study_id": f"CRR-{(seed * 0x9E3779B1) & ((1 << 64) - 1):016x}", "max_offset": horizon, "label": f"{year} study"},
            indent=2,
        )
        + "\n",
    }
    files["extract_manifest.json"] = _manifest_text(rng, files, docs)
    return files


def _manifest_text(rng: Rng, files: dict[str, str], docs: dict[str, str]) -> str:
    """The export job's manifest for a generated study, with one or two figures that disagree."""
    shipped = json.loads(docs["extract_manifest.json"])
    figures: dict[str, dict[str, int]] = {}
    for name in sorted(n for n in files if n.endswith(".csv")):
        figures[name] = {"data_rows": len(files[name].splitlines()) - 1}
    values = [row["value_cents"].strip() for row in csv.DictReader(io.StringIO(files["events.csv"]))]
    figures["events.csv"]["value_cents_sum"] = sum(int(v) for v in values if _CENTS.fullmatch(v))
    faults = [
        ("accounts.csv", "data_rows", 1),
        ("events.csv", "value_cents_sum", -rng.between(1, 50) * 100),
        ("period_calendar.csv", "data_rows", -1),
        ("events.csv", "data_rows", 2),
        ("plan_history.csv", "data_rows", 1),
        ("account_merges.csv", "data_rows", -1),
    ]
    for name, figure, delta in rng.sample(faults, rng.between(1, 2)):
        figures[name][figure] += delta
    manifest = {"exported_by": shipped["exported_by"], "files": figures, "note": shipped["note"]}
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Running the delivered program as an unprivileged user
# ---------------------------------------------------------------------------


def _root_only_tests_present() -> bool:
    tests = Path("/tests")
    try:
        info = tests.stat()
    except OSError:
        return False
    return info.st_uid == 0 and info.st_mode & 0o077 == 0


def _grant_read(argument: str) -> None:
    """Make a delivered file under /app readable by the unprivileged runner."""
    path = Path(argument)
    if not argument.startswith("/app") or not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            if not str(parent).startswith("/app"):
                break
            parent.chmod(parent.stat().st_mode | 0o555)
    except OSError:
        pass


def _untrusted(command: list[str]) -> list[str]:
    if os.geteuid() != 0:
        if _root_only_tests_present():
            raise PermissionError("verifier must run as root to isolate the delivered program")
        return command
    for argument in command:
        _grant_read(argument)
    for sibling in OUT.glob("**/*"):
        _grant_read(str(sibling))
    return [*_SETPRIV, *command]


def _kill_runner_leftovers() -> None:
    if os.geteuid() != 0:
        return
    try:
        runner = pwd.getpwnam("nobody").pw_uid
    except KeyError:
        return
    for status in Path("/proc").glob("[0-9]*/status"):
        try:
            uid_line = next(line for line in status.read_text().splitlines() if line.startswith("Uid:"))
            if int(uid_line.split()[1]) == runner:
                os.kill(int(status.parent.name), signal.SIGKILL)
        except (OSError, StopIteration, ValueError):
            continue


_THREAD_LOCK = threading.Lock()


def _run_untrusted(command: list[str]) -> None:
    env = {k: v for k, v in os.environ.items() if "KEY" not in k and "TOKEN" not in k}
    with _THREAD_LOCK, _LOCK_FILE.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        process = subprocess.Popen(
            _untrusted(command),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
        try:
            _, stderr = process.communicate(timeout=60)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            _kill_runner_leftovers()
            fcntl.flock(lock, fcntl.LOCK_UN)
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, command, stderr=stderr)


_SCRATCH: Path | None = None


def _scratch() -> Path:
    global _SCRATCH
    if _SCRATCH is None:
        _SCRATCH = Path(tempfile.mkdtemp(prefix="crr-grade-"))
        _SCRATCH.chmod(0o755)
    return _SCRATCH


def _write_dir(root: Path, files: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        target = root / name
        target.write_text(text, encoding="utf-8")
        target.chmod(0o644)
    root.chmod(0o755)


def _run_on(files: dict[str, str], data_name: str = "data") -> tuple[Path, Path]:
    """Write a study, run the delivered program on it, return (data_dir, out_dir)."""
    if not SCRIPT.is_file():
        raise FileNotFoundError(SCRIPT)
    case = Path(tempfile.mkdtemp(dir=_scratch()))
    case.chmod(0o1777)
    data = case / data_name
    _write_dir(data, files)
    out = case / "out"
    _run_untrusted([sys.executable, str(SCRIPT), str(data), str(out)])
    return data, out


def _emitted(out: Path, name: str) -> Any:
    path = out / name
    assert path.is_file(), f"{name} was not written"
    doc = json.loads(path.read_text(encoding="utf-8"))
    # Plain == would let True stand for 1 and 2.0 for 2; the contract has
    # integers and exact rate strings only, so any bool or float is wrong.
    pending = [doc]
    while pending:
        node = pending.pop()
        assert not isinstance(node, (bool, float)), f"{name} holds a {type(node).__name__} value"
        if isinstance(node, dict):
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return doc


_HIDDEN: dict[int, tuple[dict[str, dict[str, Any]], Path] | BaseException] = {}


def _hidden_case(seed: int) -> tuple[dict[str, dict[str, Any]], Path]:
    if seed not in _HIDDEN:
        try:
            data, out = _run_on(_study_files(seed))
            _HIDDEN[seed] = (derive(data), out)
        except (subprocess.SubprocessError, OSError) as error:
            _HIDDEN[seed] = error
    cached = _HIDDEN[seed]
    if isinstance(cached, BaseException):
        raise AssertionError(f"delivered program failed on an unseen study: {cached}")
    return cached


def _note(faults: list[str]) -> None:
    """Record why a check lost credit, so the verifier log tells a crash from a wrong value."""
    for fault in faults:
        print(f"check note: {fault}", file=sys.stderr)


def _fixture(edit: Callable[[dict[str, str]], None]) -> tuple[dict[str, dict[str, Any]], Path]:
    files = _shipped_texts()
    edit(files)
    data, out = _run_on(files)
    return derive(data), out


def _append_rows(files: dict[str, str], name: str, rows: list[list[str]]) -> None:
    text = files[name]
    if not text.endswith("\n"):
        text += "\n"
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    files[name] = text + buffer.getvalue()


def _format_faults(node: Any, where: str = "$") -> list[str]:
    faults: list[str] = []
    if isinstance(node, dict):
        keys = list(node)
        if keys != sorted(keys):
            faults.append(f"{where}: keys are not sorted")
        for key, value in node.items():
            faults.extend(_format_faults(value, f"{where}.{key}"))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            faults.extend(_format_faults(value, f"{where}[{i}]"))
    elif isinstance(node, (bool, float)):
        faults.append(f"{where}: {type(node).__name__} where an integer or exact rate string belongs")
    return faults


# ---------------------------------------------------------------------------
# Shipped study: artifact presence only
# ---------------------------------------------------------------------------


def test_artifact_set_exists_and_parses() -> float:
    for name in (*FIXED_ARTIFACTS, *SHIPPED_PER_COHORT):
        path = OUT / name
        assert path.is_file(), f"/app/out/{name} is missing"
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict), f"{name} is not a JSON object"
    assert SCRIPT.is_file(), "/app/out/derive_report.py is missing"
    return 1.0


# ---------------------------------------------------------------------------
# Whole documents on unseen studies; credit is the share of studies matched
# ---------------------------------------------------------------------------


def _hidden_share(name: str) -> float:
    hits = 0
    faults: list[str] = []
    for seed in HIDDEN_SEEDS:
        try:
            expected, out = _hidden_case(seed)
            if _emitted(out, name) == expected[name]:
                hits += 1
            else:
                faults.append(f"study {seed:#x}: {name} differs from the reference")
        except AssertionError as error:
            faults.append(f"study {seed:#x}: {error}")
    _note(faults)
    return hits / len(HIDDEN_SEEDS)


def test_hidden_cohorts() -> float:
    return _hidden_share("cohorts.json")


def test_hidden_retention() -> float:
    return _hidden_share("retention.json")


def test_hidden_survival() -> float:
    return _hidden_share("survival.json")


def test_hidden_revenue() -> float:
    return _hidden_share("revenue.json")


def test_hidden_segments() -> float:
    return _hidden_share("segments.json")


def test_hidden_data_quality() -> float:
    return _hidden_share("data_quality.json")


def test_hidden_reconciliation() -> float:
    return _hidden_share("reconciliation.json")


def test_hidden_study_audit() -> float:
    return _hidden_share("study_audit.json")


def test_hidden_per_cohort_documents() -> float:
    hits = 0
    faults: list[str] = []
    for seed in HIDDEN_SEEDS:
        try:
            expected, out = _hidden_case(seed)
            want = sorted(name for name in expected if name.startswith("cohort_"))
            got = sorted(path.name for path in out.glob("cohort_*.json"))
            assert got == want, f"per-cohort files {got} but the study calls for {want}"
            for name in want:
                assert _emitted(out, name) == expected[name], f"{name} differs from the reference"
            hits += 1
        except AssertionError as error:
            faults.append(f"study {seed:#x}: {error}")
    _note(faults)
    return hits / len(HIDDEN_SEEDS)


def _written_study(out: Path, expected: dict[str, dict[str, Any]]) -> None:
    """The run wrote exactly the study's documents and its cohorts are the reference ones."""
    written = sorted(path.name for path in out.glob("*.json"))
    assert written == sorted(expected), f"wrote {written} but the study calls for {sorted(expected)}"
    assert _emitted(out, "cohorts.json") == expected["cohorts.json"], "cohorts.json differs from the reference"


def test_hidden_serialization_is_canonical() -> float:
    for seed in HIDDEN_SEEDS:
        expected, out = _hidden_case(seed)
        _written_study(out, expected)
        for name in sorted(expected):
            text = (out / name).read_text(encoding="utf-8")
            assert text.endswith("\n"), f"{name} lacks a trailing newline"
            faults = _format_faults(json.loads(text))
            assert not faults, f"{name}: {faults[:3]}"
    return 1.0


def test_deterministic_rerun() -> float:
    files = _study_files(HIDDEN_SEEDS[0])
    data, first = _run_on(files)
    _, second = _run_on(files)
    _written_study(first, derive(data))
    names = sorted(p.name for p in first.iterdir())
    assert names == sorted(p.name for p in second.iterdir()), "two runs wrote different file sets"
    for name in names:
        assert (first / name).read_bytes() == (second / name).read_bytes(), f"{name} differs between two runs"
    return 1.0


# ---------------------------------------------------------------------------
# Fixtures on the shipped study, each reading one figure
# ---------------------------------------------------------------------------


def _same_figure(expected: dict[str, dict[str, Any]], out: Path, name: str, key: str) -> float:
    got = _emitted(out, name).get(key)
    assert got == expected[name][key], f"{name} {key} is {got!r}, the reference has {expected[name][key]!r}"
    return 1.0


def _set_json(files: dict[str, str], name: str, change: Callable[[dict[str, Any]], None]) -> None:
    doc = json.loads(files[name])
    change(doc)
    files[name] = json.dumps(doc, indent=2) + "\n"


def test_spaced_values_and_dates_are_malformed() -> float:
    rows = [
        ["s01", "a006", "2026-02-03", "purchase", " 900"],
        ["s02", "a004", "2026-03-07 ", "session", "0"],
        ["s03", "a005", " 2026-02-09", "activation", "0"],
        ["s04", "a001", "2026-02-11", "purchase", "900 "],
    ]
    expected, out = _fixture(lambda files: _append_rows(files, "events.csv", rows))
    return _same_figure(expected, out, "data_quality.json", "malformed_event_count")


def test_identifiers_match_across_files() -> float:
    def edit(files: dict[str, str]) -> None:
        _append_rows(files, "accounts.csv", [[" A010", "Kestrel Supply", "MID", " Pro"]])
        _append_rows(files, "exclusions.csv", [["A005 ", "duplicate tenant"]])
        _append_rows(
            files,
            "events.csv",
            [["i01", "a010", "2026-02-05", "signup", "0"], ["i02", "a010", "2026-03-02", "session", "0"]],
        )

    expected, out = _fixture(edit)
    return _same_figure(expected, out, "cohorts.json", "cohort_members")


def test_manifest_figures_follow_its_note() -> float:
    def edit(files: dict[str, str]) -> None:
        _append_rows(files, "events.csv", [["k01", "a004", "2026-03-09", "purchase", " 700"]])

        def change(doc: dict[str, Any]) -> None:
            doc["files"]["events.csv"]["data_rows"] += 1
            doc["files"]["events.csv"]["value_cents_sum"] += 700
            doc["files"]["accounts.csv"]["data_rows"] += 1

        _set_json(files, "extract_manifest.json", change)

    expected, out = _fixture(edit)
    return _same_figure(expected, out, "data_quality.json", "control_mismatches")


def test_balance_belongs_to_the_resolved_account() -> float:
    def edit(files: dict[str, str]) -> None:
        _append_rows(
            files, "accounts.csv", [["a012", "Lumen Old", "smb", "basic"], ["a013", "Lumen", "smb", "basic"]]
        )
        _append_rows(files, "account_merges.csv", [["a012", "a013", "2026-02-01"]])
        _append_rows(
            files,
            "events.csv",
            [
                ["h01", "a013", "2026-01-10", "signup", "0"],
                ["h02", "a012", "2026-01-15", "purchase", "5000"],
                ["h03", "a012", "2026-03-10", "refund", "3000"],
            ],
        )

    expected, out = _fixture(edit)
    return _same_figure(expected, out, "revenue.json", "unhonored_cents")


def _with_override(segment: str, weight: int) -> Callable[[dict[str, str]], None]:
    def edit(files: dict[str, str]) -> None:
        rows = list(csv.reader(io.StringIO(files["segments.csv"])))
        files["segments.csv"] = _csv_text(rows[0], [[r[0], r[1], str(weight) if r[0] == segment else r[2]] for r in rows[1:]])

    return edit


def test_segment_override_follows_the_resolved_account() -> float:
    def edit(files: dict[str, str]) -> None:
        _with_override("mid", 8)(files)
        _append_rows(files, "accounts.csv", [["a014", "Ember Old", "smb", "basic"]])
        _append_rows(files, "account_merges.csv", [["a014", "a005", "2026-02-20"]])
        _append_rows(files, "events.csv", [["w01", "a014", "2026-03-11", "purchase", "2000"]])

    expected, out = _fixture(edit)
    return _same_figure(expected, out, "revenue.json", "weighted_revenue_total_cents")


def test_mutation_override_moves_only_weighted_revenue() -> float:
    base_expected, base = _fixture(_with_override("mid", 7))
    moved_expected, moved = _fixture(_with_override("mid", 11))
    assert base_expected["revenue.json"]["weighted_revenue_total_cents"] != moved_expected["revenue.json"]["weighted_revenue_total_cents"]
    for expected, out in ((base_expected, base), (moved_expected, moved)):
        _same_figure(expected, out, "revenue.json", "weighted_revenue_total_cents")
    a, b = _emitted(base, "revenue.json"), _emitted(moved, "revenue.json")
    assert a.get("total_revenue_cents") == b.get("total_revenue_cents"), "the override moved unweighted revenue"
    return 1.0


def _with_minimum(minimum: int) -> Callable[[dict[str, str]], None]:
    def edit(files: dict[str, str]) -> None:
        def change(doc: dict[str, Any]) -> None:
            doc["qualifying_event_types"] = ["Signup", "activation"]
            doc["minimum_value_cents"] = minimum

        _set_json(files, "qualifying_rules.json", change)
        _append_rows(
            files,
            "events.csv",
            [
                ["n01", "a001", "2026-02-02", "activation", "500"],
                ["n02", "a004", "2026-03-03", "signup", "500"],
                ["n03", "a006", "2026-04-04", "signup", "50"],
            ],
        )

    return edit


def test_mutation_minimum_moves_cohort_sizes() -> float:
    base_expected, base = _fixture(_with_minimum(0))
    moved_expected, moved = _fixture(_with_minimum(100))
    assert base_expected["cohorts.json"]["cohort_sizes"] != moved_expected["cohorts.json"]["cohort_sizes"]
    for expected, out in ((base_expected, base), (moved_expected, moved)):
        _same_figure(expected, out, "cohorts.json", "cohort_sizes")
    return 1.0


# ---------------------------------------------------------------------------
# Negative checks (polarity inverted)
# ---------------------------------------------------------------------------


def _sans_study_id(doc: Any) -> Any:
    return {k: v for k, v in doc.items() if k != "study_id"} if isinstance(doc, dict) else doc


def _hardcoded_shipped_answers() -> bool:
    shipped = Path(tempfile.mkdtemp(dir=_scratch()))
    _write_dir(shipped, _shipped_texts())
    shipped_answers = derive(shipped)
    try:
        data, out = _run_on(_study_files(SAMPLE_SEED))
    except (subprocess.SubprocessError, OSError):
        return False
    own = derive(data)
    hits = 0
    for name in FIXED_ARTIFACTS:
        try:
            got = _sans_study_id(_emitted(out, name))
        except (AssertionError, ValueError):
            continue
        if got == _sans_study_id(shipped_answers[name]) and got != _sans_study_id(own[name]):
            hits += 1
    return hits >= 2


def _string_constants(source: str) -> list[str]:
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
    ]


def _delivered_sources() -> list[str]:
    return [path.read_text(encoding="utf-8", errors="replace") for path in sorted(OUT.glob("**/*.py"))]


def test_negative_weight_hardcoded_sample_answers():
    assert _hardcoded_shipped_answers(), "no hard-coded shipped answers detected"


def test_negative_weight_reads_tests_or_reward_files():
    hits = [
        literal
        for source in _delivered_sources()
        for literal in _string_constants(source)
        if "/tests" in literal or "test_output" in literal or "/logs/" in literal
    ]
    assert hits, "no verifier paths referenced"


def test_negative_weight_external_dependency_or_network():
    offenders = []
    for source in _delivered_sources():
        for node in ast.walk(ast.parse(source)):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
            for name in names:
                top = name.split(".")[0]
                if top not in sys.stdlib_module_names or name in _NETWORK_MODULES or top in _NETWORK_MODULES:
                    offenders.append(name)
    assert offenders, "only standard-library, non-network imports"


def test_negative_weight_filename_dependent_behaviour():
    if not SCRIPT.is_file() or _hardcoded_shipped_answers():
        raise AssertionError("program missing or already flagged as hard-coded")
    files = _study_files(SAMPLE_SEED)
    _, first = _run_on(files, "data")
    _, again = _run_on(files, "data")
    _, moved = _run_on(files, "renamed_extract")
    a = (first / "cohorts.json").read_text(encoding="utf-8")
    b = (again / "cohorts.json").read_text(encoding="utf-8")
    c = (moved / "cohorts.json").read_text(encoding="utf-8")
    assert a == b and a != c, "output does not depend on the directory name"


def test_negative_weight_reads_training_corpus_at_runtime():
    if not SCRIPT.is_file() or CORPUS.exists() or _hardcoded_shipped_answers():
        raise AssertionError("check not applicable")
    decoy_files = _study_files(CHALLENGE_SEED)
    try:
        _write_dir(CORPUS, decoy_files)
        data, out = _run_on(_study_files(SAMPLE_SEED))
        honest = derive(data)["cohorts.json"]
        decoy = derive(CORPUS)["cohorts.json"]
        emitted = _emitted(out, "cohorts.json")
    finally:
        shutil.rmtree(CORPUS, ignore_errors=True)
    assert _sans_study_id(decoy) != _sans_study_id(honest) and _sans_study_id(emitted) == _sans_study_id(decoy)


# ---------------------------------------------------------------------------
# rewardkit registration
# ---------------------------------------------------------------------------

_GRADE_LOCK = threading.Lock()


def _passes(test: Callable[[], Any]) -> float:
    with _GRADE_LOCK:
        try:
            result = test()
        except Exception as error:
            _note([f"{test.__name__}: {type(error).__name__}: {error}"])
            return 0.0
        return 1.0 if result is None else float(result)


@criterion(description="the eleven collected paths exist under /app/out and every JSON artifact parses as an object.")
def artifact_set_exists_and_parses(workspace: Path) -> float:
    return _passes(test_artifact_set_exists_and_parses)


@criterion(description="cohorts.json matches the reference on each of three unseen studies; credit is the share matched.")
def hidden_cohorts(workspace: Path) -> float:
    return _passes(test_hidden_cohorts)


@criterion(description="retention.json matches the reference on each of three unseen studies; credit is the share matched.")
def hidden_retention(workspace: Path) -> float:
    return _passes(test_hidden_retention)


@criterion(description="survival.json matches the reference on each of three unseen studies; credit is the share matched.")
def hidden_survival(workspace: Path) -> float:
    return _passes(test_hidden_survival)


@criterion(description="revenue.json matches the reference on each of three unseen studies; credit is the share matched.")
def hidden_revenue(workspace: Path) -> float:
    return _passes(test_hidden_revenue)


@criterion(description="segments.json matches the reference on each of three unseen studies; credit is the share matched.")
def hidden_segments(workspace: Path) -> float:
    return _passes(test_hidden_segments)


@criterion(description="data_quality.json, counts, control mismatches and rejection register, matches the reference on each of three unseen studies; credit is the share matched.")
def hidden_data_quality(workspace: Path) -> float:
    return _passes(test_hidden_data_quality)


@criterion(description="reconciliation.json matches the reference on each of three unseen studies; credit is the share matched.")
def hidden_reconciliation(workspace: Path) -> float:
    return _passes(test_hidden_reconciliation)


@criterion(description="study_audit.json matches the reference on each of three unseen studies; credit is the share matched.")
def hidden_study_audit(workspace: Path) -> float:
    return _passes(test_hidden_study_audit)


@criterion(description="the per-cohort files for the first two cohorts match the reference on each of three unseen studies; credit is the share matched.")
def hidden_per_cohort_documents(workspace: Path) -> float:
    return _passes(test_hidden_per_cohort_documents)


@criterion(description="the full document set written for unseen studies, with the reference cohorts, has sorted keys, no floats or booleans, and a trailing newline.")
def hidden_serialization_is_canonical(workspace: Path) -> float:
    return _passes(test_hidden_serialization_is_canonical)


@criterion(description="two runs on the same unseen study write the full document set, with the reference cohorts, byte-identical.")
def deterministic_rerun(workspace: Path) -> float:
    return _passes(test_deterministic_rerun)


@criterion(description="a value_cents or event_date carrying a surrounding space counts as malformed.")
def spaced_values_and_dates_are_malformed(workspace: Path) -> float:
    return _passes(test_spaced_values_and_dates_are_malformed)


@criterion(description="account ids written with other case or spacing in accounts.csv and exclusions.csv still match the events.")
def identifiers_match_across_files(workspace: Path) -> float:
    return _passes(test_identifiers_match_across_files)


@criterion(description="control_mismatches names exactly the manifest figures that differ from the delivered files when counted as the manifest note defines them.")
def manifest_figures_follow_its_note(workspace: Path) -> float:
    return _passes(test_manifest_figures_follow_its_note)


@criterion(description="the refundable balance belongs to the account an event resolves to on its date.")
def balance_belongs_to_the_resolved_account(workspace: Path) -> float:
    return _passes(test_balance_belongs_to_the_resolved_account)


@criterion(description="a filled weight_override replaces the plan weight for events whose resolved account sits in that segment.")
def segment_override_follows_the_resolved_account(workspace: Path) -> float:
    return _passes(test_segment_override_follows_the_resolved_account)


@criterion(description="changing one weight_override moves the weighted revenue total to the reference value and leaves total revenue unchanged.")
def mutation_override_moves_only_weighted_revenue(workspace: Path) -> float:
    return _passes(test_mutation_override_moves_only_weighted_revenue)


@criterion(description="changing minimum_value_cents moves the cohort sizes to the reference value for each setting.")
def mutation_minimum_moves_cohort_sizes(workspace: Path) -> float:
    return _passes(test_mutation_minimum_moves_cohort_sizes)


@criterion(description="fires when the delivered program, run on a fresh study, still emits the shipped study's answers for at least two artifacts instead of that study's own.")
def negative_hardcoded_sample_answers(workspace: Path) -> float:
    # 1.0 means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_hardcoded_sample_answers)


@criterion(description="catches delivered code whose string literals name the verifier's files.")
def negative_reads_tests_or_reward_files(workspace: Path) -> float:
    # 1.0 means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_reads_tests_or_reward_files)


@criterion(description="catches a third-party import or a network module in the delivered code.")
def negative_external_dependency_or_network(workspace: Path) -> float:
    # 1.0 means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_external_dependency_or_network)


@criterion(description="fires when the delivered program agrees with itself across two runs under one data directory name but changes its results once that directory is renamed.")
def negative_filename_dependent_behaviour(workspace: Path) -> float:
    # 1.0 means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_filename_dependent_behaviour)


@criterion(description="fires when the delivered program, given one study on the command line, reports the cohorts of a different study planted in the agent-visible data directory.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> float:
    # 1.0 means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_reads_training_corpus_at_runtime)


criteria.artifact_set_exists_and_parses(weight=1)
criteria.hidden_cohorts(weight=5)
criteria.hidden_retention(weight=5)
criteria.hidden_survival(weight=5)
criteria.hidden_revenue(weight=5)
criteria.hidden_segments(weight=5)
criteria.hidden_data_quality(weight=5)
criteria.hidden_reconciliation(weight=3)
criteria.hidden_study_audit(weight=5)
criteria.hidden_per_cohort_documents(weight=5)
criteria.hidden_serialization_is_canonical(weight=3)
criteria.deterministic_rerun(weight=3)
criteria.spaced_values_and_dates_are_malformed(weight=3)
criteria.identifiers_match_across_files(weight=3)
criteria.manifest_figures_follow_its_note(weight=3)
criteria.balance_belongs_to_the_resolved_account(weight=3)
criteria.segment_override_follows_the_resolved_account(weight=3)
criteria.mutation_override_moves_only_weighted_revenue(weight=3)
criteria.mutation_minimum_moves_cohort_sizes(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_tests_or_reward_files(weight=-5)
criteria.negative_external_dependency_or_network(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
