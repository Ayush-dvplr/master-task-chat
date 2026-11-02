#!/usr/bin/env python3
"""PACR-1.0 pension accrual / COLA / rebase valuation engine.

Usage: python3 calculate_pension.py DATA_DIR OUT_DIR

Standard library only. Money is integer cents, rates integer basis points,
durations integer days or months. Decimal ROUND_HALF_UP is applied only at
the boundaries named by the contract. Results are deterministic under JSONL
row reordering.
"""

import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

REQUIRED_JSONL = (
    "members.jsonl",
    "service_revisions.jsonl",
    "salary_history.jsonl",
    "leave_intervals.jsonl",
    "cola_rules.jsonl",
    "rebase_events.jsonl",
    "elections.jsonl",
)
REQUIRED_JSON = ("plans.json", "policy.json")


# --------------------------------------------------------------- helpers

def fail(message):
    sys.stderr.write("calculate_pension: %s\n" % message)
    sys.exit(2)


def div_round(numerator, denominator):
    """The contract's division: Decimal ROUND_HALF_UP of numerator/denominator."""
    return int(
        (Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def canonical_json(value):
    """Compact JSON, sorted keys, no whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def write_json(path, payload):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        handle.write("\n")


def read_jsonl(path):
    """Parse a JSONL file into a list of object records.

    A physical line yields at most one record. Blank lines and inline content
    after a record's closing brace are ignored. A final line without its
    terminating newline is still read when it parses as a complete record, so
    a conforming extract yields identical output with or without the final
    newline; an unparsable line (a torn write) is skipped with a note on
    stderr rather than aborting the run.
    """
    with open(path, "rb") as handle:
        data = handle.read()
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    records = []
    for raw in lines:
        text = raw.strip()
        if not text:
            continue
        first = text.find(b"{")
        last = text.rfind(b"}")
        if first < 0 or last < first:
            sys.stderr.write(
                "calculate_pension: skipping unparseable line in %s\n" % path
            )
            continue
        try:
            record = json.loads(text[first : last + 1].decode("utf-8"))
        except ValueError:
            sys.stderr.write(
                "calculate_pension: skipping unparseable line in %s\n" % path
            )
            continue
        if not isinstance(record, dict):
            sys.stderr.write("calculate_pension: skipping non-object line in %s\n" % path)
            continue
        records.append(record)
    return records


def read_json_file(path):
    with open(path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def read_str(record, key):
    value = record.get(key)
    return value if isinstance(value, str) else None


def read_int(record, key):
    """Read an integer field; JSON floats, strings, and booleans are invalid."""
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def read_bps(record, key):
    """Integer basis points in 0..10000, else None."""
    value = read_int(record, key)
    if value is None or not 0 <= value <= 10000:
        return None
    return value


def parse_date(text):
    if not isinstance(text, str) or len(text) != 10 or text[4] != "-" or text[7] != "-":
        return None
    try:
        value = date.fromisoformat(text)
    except ValueError:
        return None
    return value if value.isoformat() == text else None


def parse_datetime(text):
    """Parse a UTC timestamp; comparison uses the naive chronological value."""
    if not isinstance(text, str):
        return None
    body = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        value = datetime.fromisoformat(body)
    except ValueError:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def year_starts(first, last):
    """Every January 1 within [first, last], inclusive."""
    days = []
    for year in range(first.year, last.year + 1):
        days.append(date(year, 1, 1))
    return days


class Engine(object):
    """Reads the extract, resolves revisions, and produces the nine reports."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.errors = []  # (code, record_id) pairs, recorded in encounter order

    # ------------------------------------------------------------- loading

    def path(self, name):
        return os.path.join(self.data_dir, name)

    def error(self, code, record_id):
        self.errors.append((code, record_id if isinstance(record_id, str) else ""))

    def load_inputs(self):
        missing = [
            name
            for name in REQUIRED_JSONL + REQUIRED_JSON
            if not os.path.isfile(self.path(name))
        ]
        if missing:
            fail("missing input file(s): %s" % ", ".join(missing))
        self.inputs = {name: read_jsonl(self.path(name)) for name in REQUIRED_JSONL}
        for name in REQUIRED_JSON:
            self.inputs[name] = read_json_file(self.path(name))

    # ------------------------------------------------------- policy / plans

    def parse_policy(self):
        doc = self.inputs["policy.json"]
        if not isinstance(doc, dict):
            fail("policy.json must be a JSON object")
        version = read_str(doc, "engine_version")
        days_per_year = read_int(doc, "days_per_year")
        material = read_int(doc, "material_cents")
        valuation = parse_date(read_str(doc, "valuation_date"))
        if version is None:
            fail("policy.json engine_version must be a string")
        if days_per_year is None or days_per_year <= 0:
            fail("policy.json days_per_year must be a positive integer")
        if material is None or material < 0:
            fail("policy.json material_cents must be a nonnegative integer")
        if valuation is None:
            fail("policy.json valuation_date is invalid")
        self.engine_version = version
        self.days_per_year = days_per_year
        self.material_cents = material
        self.valuation_date = valuation

    def parse_plans(self):
        doc = self.inputs["plans.json"]
        if not isinstance(doc, list):
            fail("plans.json must be a JSON array")
        self.plans = {}
        for record in doc:
            if not isinstance(record, dict):
                fail("plans.json contains a non-object entry")
            plan_id = read_str(record, "plan_id")
            accrual_bps = read_int(record, "accrual_bps")
            normal_age_months = read_int(record, "normal_age_months")
            early_bps = read_int(record, "early_reduction_bps_per_month")
            option_factor_bps = read_int(record, "option_factor_bps")
            annual_cap_cents = read_int(record, "annual_cap_cents")
            if not plan_id:
                fail("plans.json contains an entry with an invalid plan_id")
            if plan_id in self.plans:
                fail("plans.json contains duplicate plan_id %r" % plan_id)
            if any(
                value is None
                for value in (
                    accrual_bps,
                    normal_age_months,
                    early_bps,
                    option_factor_bps,
                    annual_cap_cents,
                )
            ):
                fail("plans.json entry %r is missing a required numeric field" % plan_id)
            if annual_cap_cents < 0:
                fail("plans.json entry %r has negative annual_cap_cents" % plan_id)
            self.plans[plan_id] = {
                "plan_id": plan_id,
                "accrual_bps": accrual_bps,
                "normal_age_months": normal_age_months,
                "early_reduction_bps_per_month": early_bps,
                "option_factor_bps": option_factor_bps,
                "annual_cap_cents": annual_cap_cents,
            }

    # ------------------------------------------------------------- members

    def parse_members(self):
        self.members = {}
        for record in self.inputs["members.jsonl"]:
            member_id = read_str(record, "member_id")
            plan_id = read_str(record, "plan_id")
            birth_date = parse_date(read_str(record, "birth_date"))
            if not member_id or plan_id not in self.plans or birth_date is None:
                self.error("INVALID_MEMBER", member_id)
                continue
            if member_id in self.members:
                fail("members.jsonl contains duplicate member_id %r" % member_id)
            self.members[member_id] = {
                "member_id": member_id,
                "plan_id": plan_id,
                "birth_date": birth_date,
                "status": read_str(record, "status"),
            }

    # --------------------------------------------------- service revisions

    def resolve_services(self):
        """Pick each service's winning revision and its effective service."""
        groups = {}
        for record in self.inputs["service_revisions.jsonl"]:
            service_id = read_str(record, "service_id")
            revision = read_int(record, "revision")
            recorded_at = parse_datetime(read_str(record, "recorded_at"))
            status = read_str(record, "status")
            member_id = read_str(record, "member_id")
            start = parse_date(read_str(record, "start"))
            end = parse_date(read_str(record, "end"))
            record_id = read_str(record, "record_id")
            if (
                not service_id
                or revision is None
                or revision < 0
                or recorded_at is None
                or not status
                or not member_id
                or start is None
                or end is None
                or not record_id
            ):
                self.error("INVALID_SERVICE", record_id)
                continue
            groups.setdefault(service_id, []).append(
                {
                    "record_id": record_id,
                    "revision": revision,
                    "recorded_at": recorded_at,
                    "status": status,
                    "member_id": member_id,
                    "start": start,
                    "end": end,
                }
            )

        self.service_decisions = []
        self.effective_services = []
        for service_id in sorted(groups):
            entries = groups[service_id]
            top_revision = max(entry["revision"] for entry in entries)
            at_top = [entry for entry in entries if entry["revision"] == top_revision]
            top_time = max(entry["recorded_at"] for entry in at_top)
            peers = [entry for entry in at_top if entry["recorded_at"] == top_time]
            # Peers that tie on (revision, recorded_at) but differ in any
            # field other than record_id are a conflict; the record ID still
            # breaks the tie for the chosen winner.
            signature = {
                (e["status"], e["member_id"], e["start"], e["end"]) for e in peers
            }
            if len(peers) > 1 and len(signature) > 1:
                self.error("REVISION_TIE_CONFLICT", service_id)
            winner = max(peers, key=lambda entry: entry["record_id"])
            status = winner["status"]
            if status != "active":
                # Cancelled (or otherwise non-active) winner: decision kept,
                # no effective service.
                self.service_decisions.append(
                    {
                        "service_id": service_id,
                        "record_id": winner["record_id"],
                        "status": status,
                        "member_id": winner["member_id"],
                        "start": winner["start"],
                        "end": winner["end"],
                    }
                )
                continue
            if winner["member_id"] not in self.members or winner["start"] >= winner["end"]:
                self.error("INVALID_SERVICE", winner["record_id"])
                continue
            self.service_decisions.append(
                {
                    "service_id": service_id,
                    "record_id": winner["record_id"],
                    "status": status,
                    "member_id": winner["member_id"],
                    "start": winner["start"],
                    "end": winner["end"],
                }
            )
            self.effective_services.append(
                {
                    "service_id": service_id,
                    "member_id": winner["member_id"],
                    "start": winner["start"],
                    "end": winner["end"],
                }
            )
        self.service_decisions.sort(key=lambda row: row["service_id"])
        self.effective_services.sort(
            key=lambda row: (row["member_id"], row["start"], row["end"], row["service_id"])
        )

    # ------------------------------------------------- salary / leave / cola

    def parse_salaries(self):
        self.salaries = []
        for record in self.inputs["salary_history.jsonl"]:
            salary_id = read_str(record, "salary_id")
            member_id = read_str(record, "member_id")
            start = parse_date(read_str(record, "start"))
            end = parse_date(read_str(record, "end"))
            annual_salary_cents = read_int(record, "annual_salary_cents")
            if (
                not salary_id
                or member_id not in self.members
                or start is None
                or end is None
                or start >= end
                or annual_salary_cents is None
                or annual_salary_cents < 0
            ):
                self.error("INVALID_SALARY", salary_id)
                continue
            self.salaries.append(
                {
                    "salary_id": salary_id,
                    "member_id": member_id,
                    "start": start,
                    "end": end,
                    "annual_salary_cents": annual_salary_cents,
                }
            )

    def parse_leaves(self):
        self.leaves = []
        for record in self.inputs["leave_intervals.jsonl"]:
            leave_id = read_str(record, "leave_id")
            member_id = read_str(record, "member_id")
            start = parse_date(read_str(record, "start"))
            end = parse_date(read_str(record, "end"))
            credit_bps = read_bps(record, "credit_bps")
            if (
                not leave_id
                or member_id not in self.members
                or start is None
                or end is None
                or start >= end
                or credit_bps is None
            ):
                self.error("INVALID_LEAVE", leave_id)
                continue
            self.leaves.append(
                {
                    "leave_id": leave_id,
                    "member_id": member_id,
                    "start": start,
                    "end": end,
                    "credit_bps": credit_bps,
                }
            )

    def parse_colas(self):
        self.colas = []
        for record in self.inputs["cola_rules.jsonl"]:
            cola_id = read_str(record, "cola_id")
            plan_id = read_str(record, "plan_id")
            effective_date = parse_date(read_str(record, "effective_date"))
            factor_bps = read_int(record, "factor_bps")
            if (
                not cola_id
                or plan_id not in self.plans
                or effective_date is None
                or factor_bps is None
                or factor_bps < 0
            ):
                self.error("INVALID_COLA", cola_id)
                continue
            self.colas.append(
                {
                    "cola_id": cola_id,
                    "plan_id": plan_id,
                    "effective_date": effective_date,
                    "factor_bps": factor_bps,
                }
            )

    def parse_rebases(self):
        self.rebases = []
        for record in self.inputs["rebase_events.jsonl"]:
            rebase_id = read_str(record, "rebase_id")
            member_id = read_str(record, "member_id")
            effective_date = parse_date(read_str(record, "effective_date"))
            factor_bps = read_int(record, "factor_bps")
            if (
                not rebase_id
                or member_id not in self.members
                or effective_date is None
                or factor_bps is None
                or factor_bps < 0
            ):
                self.error("INVALID_REBASE", rebase_id)
                continue
            self.rebases.append(
                {
                    "rebase_id": rebase_id,
                    "member_id": member_id,
                    "effective_date": effective_date,
                    "factor_bps": factor_bps,
                }
            )

    def parse_elections(self):
        self.elections = {}
        for record in self.inputs["elections.jsonl"]:
            election_id = read_str(record, "election_id")
            member_id = read_str(record, "member_id")
            retirement_date = parse_date(read_str(record, "retirement_date"))
            option_factor_bps = read_bps(record, "option_factor_bps")
            if (
                not election_id
                or member_id not in self.members
                or retirement_date is None
                or option_factor_bps is None
            ):
                self.error("INVALID_ELECTION", election_id)
                continue
            # Multiple valid elections: choose maximum (retirement_date, election_id).
            key = (retirement_date, election_id)
            current = self.elections.get(member_id)
            if current is None or key > current[0]:
                self.elections[member_id] = (
                    key,
                    election_id,
                    retirement_date,
                    option_factor_bps,
                )

    # ------------------------------------------------------ accrual atoms

    def build_atoms(self):
        """Cut every effective service into half-open atoms and value each."""
        salaries_by_member = {}
        for salary in self.salaries:
            salaries_by_member.setdefault(salary["member_id"], []).append(salary)

        leaves_by_member = {}
        for leave in self.leaves:
            leaves_by_member.setdefault(leave["member_id"], []).append(leave)

        atoms = []
        for service in self.effective_services:
            member_id = service["member_id"]
            member = self.members[member_id]
            plan = self.plans[member["plan_id"]]
            salary_rows = salaries_by_member.get(member_id, [])
            leave_rows = leaves_by_member.get(member_id, [])
            start = service["start"]
            end = service["end"]

            # Cut points: service endpoints, overlapping salary and leave
            # endpoints, every January 1, and the valuation date. Atoms are
            # clipped to dates before the valuation date.
            points = {start, end}
            for salary in salary_rows:
                if salary["start"] < end and salary["end"] > start:
                    points.add(salary["start"])
                    points.add(salary["end"])
            for leave in leave_rows:
                if leave["start"] < end and leave["end"] > start:
                    points.add(leave["start"])
                    points.add(leave["end"])
            for day in year_starts(start, end):
                points.add(day)
            points.add(self.valuation_date)

            ordered = sorted(points)
            for index in range(len(ordered) - 1):
                atom_start = ordered[index]
                atom_end = ordered[index + 1]
                # Keep only the positive atoms that lie inside the service and
                # strictly before the valuation date.
                if atom_start < start:
                    continue
                if atom_end > end:
                    continue
                if atom_start >= self.valuation_date:
                    continue
                if atom_end > self.valuation_date:
                    continue
                if atom_start >= atom_end:
                    continue

                covering = [
                    salary
                    for salary in salary_rows
                    if salary["start"] <= atom_start and salary["end"] >= atom_end
                ]
                if not covering:
                    self.error(
                        "MISSING_SALARY",
                        "%s:%s" % (service["service_id"], atom_start.isoformat()),
                    )
                    continue
                salary = max(covering, key=lambda row: (row["start"], row["salary_id"]))
                capped = min(salary["annual_salary_cents"], plan["annual_cap_cents"])

                factors = [
                    leave["credit_bps"]
                    for leave in leave_rows
                    if leave["start"] <= atom_start and leave["end"] >= atom_end
                ]
                leave_factor = min(factors) if factors else 10000

                calendar_days = (atom_end - atom_start).days
                credited_days = div_round(calendar_days * leave_factor, 10000)
                accrual_cents = div_round(
                    capped * plan["accrual_bps"] * credited_days,
                    10000 * self.days_per_year,
                )
                atoms.append(
                    {
                        "member_id": member_id,
                        "plan_id": member["plan_id"],
                        "service_id": service["service_id"],
                        "salary_id": salary["salary_id"],
                        "start": atom_start,
                        "end": atom_end,
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
                row["salary_id"],
            )
        )
        self.atoms = atoms

    # ------------------------------------------------ revaluation stream

    def build_events(self):
        """Per member: accruals post at atom end; COLA/rebase act at effective date."""
        cola_by_plan = {}
        for cola in self.colas:
            cola_by_plan.setdefault(cola["plan_id"], []).append(cola)

        atoms_by_member = {}
        for atom in self.atoms:
            atoms_by_member.setdefault(atom["member_id"], []).append(atom)

        self.events_by_member = {}
        for member_id in sorted(self.members):
            member = self.members[member_id]
            events = []
            for atom in atoms_by_member.get(member_id, []):
                events.append(
                    {
                        "kind": "ACCRUAL",
                        "date": atom["end"],
                        "event_id": atom["salary_id"],
                        "factor_bps": None,
                        "amount_cents": atom["accrual_cents"],
                        "credited_days": atom["credited_days"],
                    }
                )
            for cola in cola_by_plan.get(member["plan_id"], []):
                events.append(
                    {
                        "kind": "COLA",
                        "date": cola["effective_date"],
                        "event_id": cola["cola_id"],
                        "factor_bps": cola["factor_bps"],
                        "amount_cents": None,
                    }
                )
            for rebase in self.rebases:
                if rebase["member_id"] != member_id:
                    continue
                events.append(
                    {
                        "kind": "REBASE",
                        "date": rebase["effective_date"],
                        "event_id": rebase["rebase_id"],
                        "factor_bps": rebase["factor_bps"],
                        "amount_cents": None,
                    }
                )
            # Ignore events after the valuation date.
            events = [event for event in events if event["date"] <= self.valuation_date]
            kind_order = {"ACCRUAL": 0, "COLA": 1, "REBASE": 2}
            events.sort(
                key=lambda event: (
                    event["date"],
                    kind_order[event["kind"]],
                    event["event_id"],
                )
            )
            self.events_by_member[member_id] = events

    # ------------------------------------------------------ member benefits

    def build_benefits(self):
        """Run each member's stream, then apply the selected election."""
        self.cola_rows = []
        self.benefit_rows = []
        for member_id in sorted(self.members):
            member = self.members[member_id]
            plan = self.plans[member["plan_id"]]
            balance = 0
            base_accrual = 0
            revaluation_delta = 0
            credited_days = 0
            for event in self.events_by_member[member_id]:
                if event["kind"] == "ACCRUAL":
                    balance += event["amount_cents"]
                    base_accrual += event["amount_cents"]
                    credited_days += event["credited_days"]
                    continue
                before = balance
                after = div_round(balance * event["factor_bps"], 10000)
                balance = after
                revaluation_delta += after - before
                self.cola_rows.append(
                    {
                        "member_id": member_id,
                        "event_date": event["date"].isoformat(),
                        "event_kind": event["kind"],
                        "event_id": event["event_id"],
                        "factor_bps": event["factor_bps"],
                        "balance_before_cents": before,
                        "balance_after_cents": after,
                        "delta_cents": after - before,
                    }
                )
            accrued = balance

            chosen = self.elections.get(member_id)
            if chosen is None:
                election_id = None
                retirement_date = None
                age_months = None
                early_months = 0
                reduction_bps = 0
                option_factor_bps = plan["option_factor_bps"]
            else:
                election_id = chosen[1]
                retirement_date = chosen[2]
                birth = member["birth_date"]
                age_months = (
                    (retirement_date.year - birth.year) * 12
                    + (retirement_date.month - birth.month)
                    - (1 if retirement_date.day < birth.day else 0)
                )
                early_months = max(0, plan["normal_age_months"] - age_months)
                reduction_bps = min(
                    10000, early_months * plan["early_reduction_bps_per_month"]
                )
                option_factor_bps = chosen[3]

            reduced_cents = div_round(accrued * (10000 - reduction_bps), 10000)
            payable_cents = div_round(reduced_cents * option_factor_bps, 10000)
            row = {
                "member_id": member_id,
                "plan_id": member["plan_id"],
                "credited_days": credited_days,
                "base_accrual_cents": base_accrual,
                "revaluation_delta_cents": revaluation_delta,
                "accrued_cents": accrued,
                "election_id": election_id,
                "retirement_date": (
                    retirement_date.isoformat() if retirement_date is not None else None
                ),
                "age_months": age_months,
                "early_months": early_months,
                "reduction_bps": reduction_bps,
                "option_factor_bps": option_factor_bps,
                "payable_cents": payable_cents,
            }
            self.benefit_rows.append(row)
        kind_order = {"ACCRUAL": 0, "COLA": 1, "REBASE": 2}
        self.cola_rows.sort(
            key=lambda row: (
                row["member_id"],
                row["event_date"],
                kind_order[row["event_kind"]],
                row["event_id"],
            )
        )

    # ------------------------------------------------------------ rollups

    def build_rollups(self):
        rollups = []
        for plan_id in sorted(self.plans):
            rows = [row for row in self.benefit_rows if row["plan_id"] == plan_id]
            rollups.append(
                {
                    "plan_id": plan_id,
                    "member_count": len(rows),
                    "credited_days": sum(row["credited_days"] for row in rows),
                    "base_accrual_cents": sum(row["base_accrual_cents"] for row in rows),
                    "revaluation_delta_cents": sum(
                        row["revaluation_delta_cents"] for row in rows
                    ),
                    "accrued_cents": sum(row["accrued_cents"] for row in rows),
                    "payable_cents": sum(row["payable_cents"] for row in rows),
                }
            )
        self.plan_rows = rollups

    # ------------------------------------------------------------- reports

    def issue_counts(self):
        counts = {}
        for code, _record_id in self.errors:
            counts[code] = counts.get(code, 0) + 1
        return counts

    def issue_rows(self):
        return [
            {"code": code, "record_id": record_id}
            for code, record_id in sorted(set(self.errors))
        ]

    def input_files(self):
        rows = []
        for name in sorted(os.listdir(self.data_dir)):
            full = os.path.join(self.data_dir, name)
            if not os.path.isfile(full) or os.path.islink(full):
                continue
            with open(full, "rb") as handle:
                data = handle.read()
            rows.append(
                {
                    "name": name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            )
        return rows

    def build_manifest(self):
        return {
            "engine_version": self.engine_version,
            "input_files": self.input_files(),
            "valid_member_count": len(self.members),
            "effective_service_count": len(self.effective_services),
            "accrual_atom_count": len(self.atoms),
        }

    def build_data_quality(self):
        return {
            "input_file_count": len(self.input_files()),
            "record_counts": self.record_counts,
            "issue_count": len(self.issue_rows()),
            "issues": self.issue_rows(),
        }

    def build_service_ledger(self):
        return {
            "revision_decisions": [
                {
                    "service_id": row["service_id"],
                    "record_id": row["record_id"],
                    "status": row["status"],
                    "member_id": row["member_id"],
                    "start": row["start"].isoformat(),
                    "end": row["end"].isoformat(),
                }
                for row in self.service_decisions
            ],
            "effective_services": [
                {
                    "service_id": row["service_id"],
                    "member_id": row["member_id"],
                    "start": row["start"].isoformat(),
                    "end": row["end"].isoformat(),
                }
                for row in self.effective_services
            ],
        }

    def build_accrual_ledger(self):
        return {
            "atoms": [
                {
                    "member_id": row["member_id"],
                    "plan_id": row["plan_id"],
                    "service_id": row["service_id"],
                    "salary_id": row["salary_id"],
                    "start": row["start"].isoformat(),
                    "end": row["end"].isoformat(),
                    "calendar_days": row["calendar_days"],
                    "leave_factor_bps": row["leave_factor_bps"],
                    "credited_days": row["credited_days"],
                    "capped_salary_cents": row["capped_salary_cents"],
                    "accrual_bps": row["accrual_bps"],
                    "accrual_cents": row["accrual_cents"],
                }
                for row in self.atoms
            ]
        }

    def build_audit_trace(self):
        previous = "0" * 64
        rows = []
        for benefit in self.benefit_rows:
            row_hash = hashlib.sha256(
                (previous + canonical_json(benefit)).encode("utf-8")
            ).hexdigest()
            rows.append(
                {
                    "member_id": benefit["member_id"],
                    "previous_hash": previous,
                    "row_hash": row_hash,
                }
            )
            previous = row_hash
        return {"rows": rows, "final_hash": previous}

    def build_exception_register(self):
        exceptions = [
            {"code": code, "record_id": record_id}
            for code, record_id in sorted(set(self.errors))
        ]
        for benefit in self.benefit_rows:
            if abs(benefit["payable_cents"]) >= self.material_cents:
                exceptions.append(
                    {
                        "code": "MATERIAL_BENEFIT",
                        "record_id": benefit["member_id"],
                        "amount_cents": benefit["payable_cents"],
                    }
                )
        exceptions.sort(key=lambda row: (row["code"], row["record_id"]))
        return {"exceptions": exceptions}

    # --------------------------------------------------------------- run

    def run(self, out_dir):
        self.load_inputs()
        self.parse_policy()
        self.parse_plans()
        self.parse_members()
        self.parse_salaries()
        self.parse_leaves()
        self.parse_colas()
        self.parse_rebases()
        self.parse_elections()
        self.resolve_services()
        self.build_atoms()
        self.build_events()
        self.build_benefits()
        self.build_rollups()
        self.record_counts = {}
        for name in sorted(self.inputs):
            records = self.inputs[name]
            self.record_counts[name] = len(records) if isinstance(records, list) else 1
        reports = {
            "manifest.json": self.build_manifest(),
            "data_quality.json": self.build_data_quality(),
            "service_ledger.json": self.build_service_ledger(),
            "accrual_ledger.json": self.build_accrual_ledger(),
            "cola_ledger.json": {"events": self.cola_rows},
            "member_benefits.json": {"members": self.benefit_rows},
            "plan_rollups.json": {"plans": self.plan_rows},
            "exception_register.json": self.build_exception_register(),
            "audit_trace.json": self.build_audit_trace(),
        }
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        for name, payload in reports.items():
            write_json(os.path.join(out_dir, name), payload)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: calculate_pension.py DATA_DIR OUT_DIR\n")
        return 2
    engine = Engine(argv[1])
    engine.run(argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
