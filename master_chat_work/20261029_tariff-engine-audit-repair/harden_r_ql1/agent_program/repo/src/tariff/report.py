"""Invoice assembly, statements and rendering for the tariff engine."""
import csv
import json
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

from . import core, parser

INPUT_FILES = ("meter_reads.jsonl", "accounts.csv", "billing_periods.csv",
               "rate_card.json")


def missing_input(data_dir):
    """The name of the first required input file the directory lacks."""
    root = Path(data_dir)
    for name in INPUT_FILES:
        if not (root / name).is_file():
            return name
    return None


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return [{key.strip(): (value or "").strip() for key, value in row.items()}
                for row in csv.DictReader(handle)]


def _plan_index(plans):
    """Map every plan name and plan code to the name of its plan."""
    index = {}
    for name, plan in plans.items():
        for code in plan.get("codes") or ():
            index.setdefault(str(code).strip(), name)
    index.update({name: name for name in plans})
    return index


def _load(data_dir):
    """Read the input files of ``data_dir`` into the engine's own values."""
    root = Path(data_dir)
    reads = parser.parse_reads((root / "meter_reads.jsonl").read_text(encoding="utf-8"))
    meters = {}
    for row in _rows(root / "accounts.csv"):
        end = date.fromisoformat(row["active_to"]) if row["active_to"] else None
        meters.setdefault((row["account"], row["meter"]), []).append(
            (date.fromisoformat(row["active_from"]), end))
    periods = []
    for row in _rows(root / "billing_periods.csv"):
        periods.append({
            "account": row["account"],
            "start": date.fromisoformat(row["start"]),
            "end": date.fromisoformat(row["end"]),
            "plan": row["plan"],
            "commitment": core.round_cents(row["commitment"]),
            "allowance": core.exact(row["allowance"]),
        })
    card = json.loads((root / "rate_card.json").read_text(encoding="utf-8"))
    plans = {str(name).strip(): plan for name, plan in card["plans"].items()}
    payments = {}
    if (root / "payments.csv").is_file():
        for row in _rows(root / "payments.csv"):
            key = (row["account"], date.fromisoformat(row["start"]))
            payments[key] = payments.get(key, 0) + core.round_cents(row["paid"])
    vouchers = {}
    if (root / "vouchers.csv").is_file():
        for row in _rows(root / "vouchers.csv"):
            vouchers.setdefault(row["account"], {})[row["voucher"]] = \
                core.round_cents(row["amount"])
    return {"reads": reads, "meters": meters, "periods": periods, "plans": plans,
            "codes": _plan_index(plans), "payments": payments, "vouchers": vouchers}


def _active_days(windows, start, end):
    """The days from ``start`` to ``end`` on which a meter is active."""
    days = []
    day = start
    while day <= end:
        if any(opened <= day and (closed is None or day <= closed)
               for opened, closed in windows):
            days.append(day)
        day += timedelta(days=1)
    return days


def _prepare(data):
    """Classify the reads and sum the period quantity of every invoice meter."""
    rows = {}
    for row in data["periods"]:
        rows.setdefault(row["account"], []).append(row)
    for account in rows:
        rows[account].sort(key=lambda row: row["start"])
    windows = {account: sorted((row["start"], row["end"]) for row in account_rows)
               for account, account_rows in rows.items()}
    accepted, exceptions = parser.classify(data["reads"], data["meters"], windows)
    billed = parser.billed_quantities(accepted)
    usage = {}
    for read in accepted:
        for row in rows[read["account"]]:
            if row["start"] <= read["day"] <= row["end"]:
                key = (read["account"], row["start"], read["meter"])
                usage[key] = usage.get(key, 0) + billed[read["read_id"]]
                break
    account_meters = {}
    for account, meter in data["meters"]:
        account_meters.setdefault(account, []).append(meter)
    for account in account_meters:
        account_meters[account].sort()
    return {"rows": rows, "usage": usage, "meters": account_meters,
            "exceptions": exceptions}


def _invoice(data, state, row, tiers, carry, allow_credit):
    """Rate one row of billing_periods.csv into an invoice."""
    account = row["account"]
    plan = data["plans"][data["codes"][row["plan"]]]
    lines = []
    offset = 0
    for meter in state["meters"].get(account, ()):
        quantity = state["usage"].get((account, row["start"], meter), 0)
        lines.extend(core.energy_lines(meter, offset, quantity, tiers))
        offset += quantity
        days = _active_days(data["meters"][(account, meter)], row["start"], row["end"])
        if days:
            lines.append(core.standing_line(meter, plan, days))
    energy = [line for line in lines if line["kind"] == "energy"]
    shares, unshared = core.share_allowance([line["exact"] for line in energy],
                                            row["allowance"] + carry)
    for line, share in zip(energy, shares):
        line["share"] = share
    amounts = [core.round_cents(line["exact"] - line.get("share", 0))
               for line in lines]
    subtotal, credit, total = core.settle(amounts, row["commitment"],
                                          plan["credit_rate"], allow_credit)
    return {
        "account": account,
        "start": row["start"],
        "end": row["end"],
        "plan": row["plan"],
        "plan_name": data["codes"][row["plan"]],
        "lines": [{"meter": line["meter"], "kind": line["kind"], "tier": line["tier"],
                   "units": line["units"], "amount": core.money(amount)}
                  for line, amount in zip(lines, amounts)],
        "subtotal": subtotal,
        "credit": credit,
        "total": total,
        "paid": data["payments"].get((account, row["start"])),
        "unshared": unshared,
    }


def _rate(data, state, tiers_by_plan):
    """Rate every row of billing_periods.csv, in account and then start order."""
    invoices = []
    for account in sorted(state["rows"]):
        carry = Fraction(0)
        previous = None
        for row in state["rows"][account]:
            allow_credit = not (previous is not None and previous["paid"] is not None
                                and previous["paid"] < previous["total"])
            invoice = _invoice(data, state, row,
                               tiers_by_plan[data["codes"][row["plan"]]],
                               carry, allow_credit)
            carry = invoice["unshared"]
            previous = invoice
            invoices.append(invoice)
    return invoices


def _fits(invoices, name):
    """Whether every paid invoice on the plan ``name`` totals its paid amount."""
    return all(invoice["total"] == invoice["paid"] for invoice in invoices
               if invoice["plan_name"] == name and invoice["paid"] is not None)


def _choose_tiers(data, state):
    """The tiers every plan's invoices are rated with.

    A plan is rated with its own tiers unless exactly one of its revisions
    makes every paid invoice on the plan total its paid amount.
    """
    choice = {name: plan["tiers"] for name, plan in data["plans"].items()}
    revised = {name: plan["revisions"] for name, plan in data["plans"].items()
               if plan.get("revisions")}
    for _ in range(len(revised) + 1):
        changed = False
        for name, revisions in revised.items():
            fits = []
            for revision in revisions:
                trial = dict(choice, **{name: revision["tiers"]})
                if _fits(_rate(data, state, trial), name):
                    fits.append(revision["tiers"])
            picked = fits[0] if len(fits) == 1 else data["plans"][name]["tiers"]
            if picked != choice[name]:
                choice[name] = picked
                changed = True
        if not changed:
            break
    return choice


def _document(data_dir):
    data = _load(data_dir)
    state = _prepare(data)
    invoices = _rate(data, state, _choose_tiers(data, state))
    return data, invoices, state["exceptions"]


def build_invoices(data_dir):
    """Rate every billing period of ``data_dir`` and return the invoice document."""
    _, invoices, exceptions = _document(data_dir)
    return {
        "invoices": [{
            "account": invoice["account"],
            "period": {"start": invoice["start"].isoformat(),
                       "end": invoice["end"].isoformat()},
            "plan": invoice["plan"],
            "lines": invoice["lines"],
            "subtotal": core.money(invoice["subtotal"]),
            "credit": core.money(invoice["credit"]),
            "total": core.money(invoice["total"]),
        } for invoice in invoices],
        "exceptions": exceptions,
    }


def build_statements(data_dir):
    """Return the voucher statement document of ``data_dir``."""
    data, invoices, _ = _document(data_dir)
    balances = {}
    for invoice in invoices:
        balances[invoice["account"]] = (balances.get(invoice["account"], 0)
                                        + invoice["total"] - (invoice["paid"] or 0))
    statements = []
    for account in sorted(data["vouchers"]):
        balance = max(balances.get(account, 0), 0)
        chosen, taken = core.redeem(balance, data["vouchers"][account])
        statements.append({"account": account, "balance": core.money(balance),
                           "redeemed": chosen, "due": core.money(balance - taken)})
    return {"statements": statements}


def render(document):
    """Return a document as JSON text."""
    return json.dumps(document, indent=2, sort_keys=True)
