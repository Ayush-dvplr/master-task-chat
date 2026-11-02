"""Invoice assembly and rendering for the tariff engine."""
import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from . import core, parser

INPUT_FILES = ("meter_reads.jsonl", "accounts.csv", "billing_periods.csv",
               "rate_card.json")


def missing_input(data_dir):
    """Return the first missing input file of ``data_dir``, or None."""
    root = Path(data_dir)
    for name in INPUT_FILES:
        if not (root / name).is_file():
            return name
    return None


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return [{key.strip(): (value or "").strip() for key, value in row.items()}
                for row in csv.DictReader(handle)]


def _load(data_dir):
    root = Path(data_dir)
    reads = parser.parse_reads((root / "meter_reads.jsonl").read_text(encoding="utf-8"))
    meters = {}
    for row in _rows(root / "accounts.csv"):
        end = date.fromisoformat(row["active_to"]) if row["active_to"] else None
        meters[(row["account"], row["meter"])] = (date.fromisoformat(row["active_from"]), end)
    periods = {}
    for row in _rows(root / "billing_periods.csv"):
        periods[row["account"]] = {
            "start": date.fromisoformat(row["start"]),
            "end": date.fromisoformat(row["end"]),
            "plan": row["plan"],
            "commitment": Decimal(row["commitment"]),
        }
    card = json.loads((root / "rate_card.json").read_text(encoding="utf-8"),
                      parse_float=Decimal)
    return reads, meters, periods, card


def _active_days(window, period):
    start = max(window[0], period["start"])
    end = period["end"] if window[1] is None else min(window[1], period["end"])
    return max((end - start).days + 1, 0)


def build_invoices(data_dir):
    """Rate every account of ``data_dir`` and return the invoice document."""
    reads, meters, periods, card = _load(data_dir)
    accepted, exceptions = parser.classify(reads, meters, periods)
    usage = {}
    for read in accepted:
        key = (read["account"], read["meter"])
        usage[key] = usage.get(key, 0) + read["quantity"]
    account_meters = {}
    for account, meter in meters:
        account_meters.setdefault(account, []).append(meter)
    invoices = []
    for account in sorted(periods):
        period = periods[account]
        plan = card["plans"][period["plan"]]
        month_days = (period["end"] - period["start"]).days + 1
        lines = []
        for meter in sorted(account_meters.get(account, ())):
            key = (account, meter)
            lines.extend(core.energy_lines(meter, usage.get(key, 0), plan))
            days = _active_days(meters[key], period)
            if days:
                lines.append(core.standing_line(meter, plan, days, month_days))
        subtotal, credit, total = core.settle(lines, plan, period["commitment"])
        invoices.append({
            "account": account,
            "period": {"start": period["start"].isoformat(), "end": period["end"].isoformat()},
            "plan": period["plan"],
            "lines": lines,
            "subtotal": subtotal,
            "credit": credit,
            "total": total,
        })
    exceptions.sort(key=lambda row: row["read_id"])
    return {"invoices": invoices, "exceptions": exceptions}


def render(document):
    """Return the invoice document as JSON text."""
    return json.dumps(document, indent=2, sort_keys=True)
