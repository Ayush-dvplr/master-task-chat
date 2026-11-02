"""Invoice assembly and rendering for the tariff engine."""
import csv
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from . import core, parser

INPUT_FILES = ("meter_reads.jsonl", "accounts.csv", "billing_periods.csv", "rate_card.json")


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [{(key or "").strip(): (value or "").strip() for key, value in row.items()}
                for row in csv.DictReader(handle)]


def _plan(raw):
    """Normalise one rate card plan: stripped text, dates for standing changes."""
    plan = dict(raw)
    plan["codes"] = [str(code).strip() for code in raw.get("codes") or []]
    plan["standing_changes"] = [
        {"from": date.fromisoformat(str(change["from"]).strip()),
         "standing_charge": change["standing_charge"]}
        for change in raw.get("standing_changes") or []
    ]
    return plan


def _card(path):
    card = json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)
    return {str(name).strip(): _plan(plan) for name, plan in card["plans"].items()}


def resolve_plan(plans, value):
    """The plan named ``value``; a tariff code listed in a plan's ``codes`` also names it."""
    if value in plans:
        return plans[value]
    for plan in plans.values():
        if value in plan["codes"]:
            return plan
    raise KeyError(f"unknown plan: {value}")


def _load(data_dir):
    root = Path(data_dir)
    reads = parser.parse_reads((root / "meter_reads.jsonl").read_text(encoding="utf-8"))
    meters = {}
    for row in _rows(root / "accounts.csv"):
        end = date.fromisoformat(row["active_to"]) if row["active_to"] else None
        meters.setdefault((row["account"], row["meter"]), []).append(
            (date.fromisoformat(row["active_from"]), end))
    periods = {}
    for row in _rows(root / "billing_periods.csv"):
        periods.setdefault(row["account"], []).append({
            "start": date.fromisoformat(row["start"]),
            "end": date.fromisoformat(row["end"]),
            "plan": row["plan"],
            "commitment": core.exact(row["commitment"] or "0"),
            "allowance": core.exact(row["allowance"] or "0"),
        })
    for rows in periods.values():
        rows.sort(key=lambda row: row["start"])
    plans = _card(root / "rate_card.json")
    return reads, meters, periods, plans


def _active_days(windows, period):
    """The days of ``period`` on which a meter with ``windows`` is active."""
    days = []
    day = period["start"]
    while day <= period["end"]:
        if parser._active(windows, day):
            days.append(day)
        day += timedelta(days=1)
    return days


def _invoice(account, period, plan, meter_names, usage, allowance):
    lines = []
    position = 0
    for meter in meter_names:
        quantity = usage.get(meter, 0)
        lines.extend(core.energy_lines(meter, quantity, plan, position))
        position += quantity
        standing = core.standing_line(meter, plan, period["active"][meter])
        if standing is not None:
            lines.append(standing)
    lines, subtotal, credit, total, left = core.settle(
        lines, plan, period["commitment"], allowance)
    for line in lines:
        line["amount"] = core.money(line["amount"])
    invoice = {
        "account": account,
        "period": {"start": period["start"].isoformat(), "end": period["end"].isoformat()},
        "plan": period["plan"],
        "lines": lines,
        "subtotal": core.money(subtotal),
        "credit": core.money(credit),
        "total": core.money(total),
    }
    return invoice, left


def build_invoices(data_dir):
    """Rate every billing row of ``data_dir`` and return the invoice document."""
    reads, meters, periods, plans = _load(data_dir)
    accepted, exceptions = parser.classify(reads, meters, periods)
    by_account = {}
    for read in accepted:
        by_account.setdefault(read["account"], []).append(read)
    invoices = []
    for account in sorted(periods):
        meter_names = sorted(meter for acc, meter in meters if acc == account)
        carry = 0
        for period in periods[account]:
            usage = {}
            for read in by_account.get(account, []):
                if period["start"] <= read["day"] <= period["end"]:
                    usage[read["meter"]] = usage.get(read["meter"], 0) + read["quantity"]
            period["active"] = {meter: _active_days(meters[(account, meter)], period)
                                for meter in meter_names}
            plan = resolve_plan(plans, period["plan"])
            invoice, carry = _invoice(account, period, plan, meter_names, usage,
                                      period["allowance"] + carry)
            invoices.append(invoice)
    return {"invoices": invoices, "exceptions": exceptions}


def render(document):
    """Return the invoice document as JSON text."""
    return json.dumps(document, indent=2, sort_keys=True)
