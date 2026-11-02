"""Invoice assembly and rendering for the tariff engine."""
import csv
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from . import core, parser

INPUTS = ("meter_reads.jsonl", "accounts.csv", "billing_periods.csv", "rate_card.json")


class MissingInputError(FileNotFoundError):
    """Raised when a required input file is absent from the data directory."""

    def __init__(self, name):
        super().__init__(f"missing input: {name}")
        self.name = name


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [{(key or "").strip(): (value or "").strip() for key, value in row.items()}
                for row in csv.DictReader(handle)]


def _resolve_plans(card):
    """Return ({plan name: plan}, {code: plan name}) with names and codes stripped."""
    plans = {}
    codes = {}
    for name, plan in card["plans"].items():
        plans[name.strip()] = plan
        for code in plan.get("codes") or []:
            codes[str(code).strip()] = name.strip()
    return plans, codes


def _load(data_dir):
    root = Path(data_dir)
    for name in INPUTS:
        if not (root / name).is_file():
            raise MissingInputError(name)
    reads = parser.parse_reads((root / "meter_reads.jsonl").read_text(encoding="utf-8-sig"))
    meters = {}
    for row in _rows(root / "accounts.csv"):
        end = date.fromisoformat(row["active_to"]) if row["active_to"] else None
        meters.setdefault((row["account"], row["meter"]), []).append(
            (date.fromisoformat(row["active_from"]), end))
    card = json.loads((root / "rate_card.json").read_text(encoding="utf-8-sig"),
                      parse_float=Decimal)
    plans, codes = _resolve_plans(card)
    periods = []
    for row in _rows(root / "billing_periods.csv"):
        plan_key = row["plan"] if row["plan"] in plans else codes[row["plan"]]
        periods.append({
            "account": row["account"],
            "start": date.fromisoformat(row["start"]),
            "end": date.fromisoformat(row["end"]),
            "plan": row["plan"],
            "plan_key": plan_key,
            "commitment": Decimal(row["commitment"]),
            "allowance": Decimal(row["allowance"]),
        })
    payments = {}
    if (root / "payments.csv").is_file():
        for row in _rows(root / "payments.csv"):
            key = (row["account"], date.fromisoformat(row["start"]))
            payments[key] = payments.get(key, Decimal("0")) + Decimal(row["paid"])
    return reads, meters, periods, plans, payments


def _days(start, end):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _rate(periods, plans, tier_choice, accepted, billed, meters, payments):
    """Rate every billing period row; returns the invoices in account/start order.

    Each invoice also carries its total in cents under ``_total`` for the
    revision search; it is removed before the document is returned.
    """
    by_account = {}
    for period in periods:
        by_account.setdefault(period["account"], []).append(period)
    for rows in by_account.values():
        rows.sort(key=lambda period: period["start"])

    usage = {}
    for read, quantity in zip(accepted, billed):
        for period in by_account.get(read["account"], ()):
            if period["start"] <= read["day"] <= period["end"]:
                key = (id(period), read["meter"])
                usage[key] = usage.get(key, 0) + quantity
                break

    invoices = []
    for account in sorted(by_account):
        account_meters = sorted({meter for acc, meter in meters if acc == account})
        carry = Decimal("0")
        previous = None
        for period in by_account[account]:
            plan = plans[period["plan_key"]]
            quantities = [(meter, usage.get((id(period), meter), 0)) for meter in account_meters]
            rated = core.rate_tiers(quantities, tier_choice[period["plan_key"]])
            lines = []
            for meter in account_meters:
                lines.extend(core.energy_lines(meter, rated[meter]))
                active = [day for day in _days(period["start"], period["end"])
                          if parser._active(meters[(account, meter)], day)]
                if active:
                    lines.append(core.standing_line(meter, plan, active))
            carry = core.share_allowance(lines, core.exact(period["allowance"]) + core.exact(carry))
            amounts = [core.line_cents(line) for line in lines]
            eligible = True
            if previous is not None:
                paid = payments.get((account, previous["start"]))
                if paid is not None and core.cents(paid) < previous["_total"]:
                    eligible = False
            subtotal, credit, total = core.settle(sum(amounts), plan, period["commitment"],
                                                  eligible)
            invoice = {
                "account": account,
                "period": {"start": period["start"].isoformat(),
                           "end": period["end"].isoformat()},
                "plan": period["plan"],
                "lines": [
                    {"meter": line["meter"], "kind": line["kind"], "tier": line["tier"],
                     "units": line["units"], "amount": core.money(amount)}
                    for line, amount in zip(lines, amounts)
                ],
                "subtotal": core.money(subtotal),
                "credit": core.money(credit),
                "total": core.money(total),
                "_total": total,
                "_plan_key": period["plan_key"],
            }
            invoices.append(invoice)
            previous = {"start": period["start"], "_total": total}
    return invoices


def _choose_tiers(periods, plans, accepted, billed, meters, payments):
    """Pick the tiers list of every plan.

    A plan is rated with the tiers of its only revision under which every
    invoice on the plan that has a paid amount totals that paid amount; with no
    such revision or more than one, it keeps its own tiers.
    """
    choice = {name: plan["tiers"] for name, plan in plans.items()}
    revised = [name for name, plan in plans.items() if plan.get("revisions")]
    paid_keys = {}
    for period in periods:
        key = (period["account"], period["start"])
        if key in payments:
            paid_keys.setdefault(period["plan_key"], {})[
                (period["account"], period["start"].isoformat())] = core.cents(payments[key])
    for _ in range(len(revised) + 2):
        changed = False
        for name in revised:
            matching = []
            for revision in plans[name]["revisions"]:
                trial = dict(choice)
                trial[name] = revision["tiers"]
                invoices = _rate(periods, plans, trial, accepted, billed, meters, payments)
                wanted = paid_keys.get(name, {})
                if all(invoice["_total"] == wanted[(invoice["account"],
                                                    invoice["period"]["start"])]
                       for invoice in invoices
                       if invoice["_plan_key"] == name
                       and (invoice["account"], invoice["period"]["start"]) in wanted):
                    matching.append(revision["tiers"])
            new = matching[0] if len(matching) == 1 else plans[name]["tiers"]
            if new is not choice[name]:
                choice[name] = new
                changed = True
        if not changed:
            break
    return choice


def build_invoices(data_dir):
    """Rate every billing period row of ``data_dir`` and return the invoice document."""
    reads, meters, periods, plans, payments = _load(data_dir)
    windows = {}
    for (account, meter), rows in meters.items():
        windows[(account, meter)] = rows
    by_account = {}
    for period in periods:
        by_account.setdefault(period["account"], []).append((period["start"], period["end"]))
    accepted, exceptions = parser.classify(reads, windows, by_account)
    billed = parser.billed_quantities(accepted)
    choice = _choose_tiers(periods, plans, accepted, billed, meters, payments)
    invoices = _rate(periods, plans, choice, accepted, billed, meters, payments)
    for invoice in invoices:
        del invoice["_total"]
        del invoice["_plan_key"]
    return {"invoices": invoices, "exceptions": exceptions}


def render(document):
    """Return the invoice document as JSON text."""
    return json.dumps(document, indent=2, sort_keys=True)
