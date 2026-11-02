"""Invoice assembly, statements and rendering for the tariff engine."""
import csv
import json
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from . import core, parser

REQUIRED = ("meter_reads.jsonl", "accounts.csv", "billing_periods.csv", "rate_card.json")


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return [{(key or "").strip(): (value or "").strip() for key, value in row.items()}
                for row in csv.DictReader(handle)]


def _strip(value):
    """Strip every text value of a parsed JSON tree."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [_strip(item) for item in value]
    if isinstance(value, dict):
        return {key.strip(): _strip(item) for key, item in value.items()}
    return value


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
            "commitment": row["commitment"],
            "allowance": row["allowance"] or "0",
        })
    for rows in periods.values():
        rows.sort(key=lambda row: row["start"])
    card = _strip(json.loads((root / "rate_card.json").read_text(encoding="utf-8"),
                             parse_float=Decimal))
    paid = {}
    if (root / "payments.csv").exists():
        for row in _rows(root / "payments.csv"):
            key = (row["account"], date.fromisoformat(row["start"]))
            paid[key] = paid.get(key, Fraction(0)) + core.exact(row["paid"])
    return reads, meters, periods, card, paid


def _plan_names(card):
    """Map every plan name and plan code to the plan's name in the rate card."""
    names = {}
    for name, plan in card["plans"].items():
        for code in plan.get("codes") or []:
            names.setdefault(str(code).strip(), name)
    for name in card["plans"]:
        names[name] = name
    return names


def _billed(accepted):
    """Billed quantity of every accepted read, keyed by read_id."""
    billed = {}
    previous = {}
    ordered = sorted((read for read in accepted if read["cumulative"]),
                     key=lambda read: (read["account"], read["meter"], read["day"]))
    for read in ordered:
        key = (read["account"], read["meter"])
        before = previous.get(key)
        if before is None:
            billed[id(read)] = 0
        elif before["quantity"] > read["quantity"]:
            billed[id(read)] = read["quantity"]
        else:
            billed[id(read)] = read["quantity"] - before["quantity"]
        previous[key] = read
    for read in accepted:
        if not read["cumulative"]:
            billed[id(read)] = read["quantity"]
    return billed


class _Run:
    """Everything one data directory needs to rate its invoices."""

    def __init__(self, data_dir):
        reads, self.meters, self.periods, self.card, self.paid = _load(data_dir)
        self.accepted, self.exceptions = parser.classify(reads, self.meters, self.periods)
        self.names = _plan_names(self.card)
        billed = _billed(self.accepted)
        self.usage = {}
        for read in self.accepted:
            for row in self.periods.get(read["account"], []):
                if row["start"] <= read["day"] <= row["end"]:
                    key = (read["account"], row["start"], read["meter"])
                    self.usage[key] = self.usage.get(key, 0) + billed[id(read)]
                    break
        self.account_meters = {}
        for account, meter in self.meters:
            self.account_meters.setdefault(account, []).append(meter)
        for meter_list in self.account_meters.values():
            meter_list.sort()

    def plan_of(self, row):
        return self.names[row["plan"]]

    def tiers(self, plan_name, choice):
        plan = self.card["plans"][plan_name]
        index = choice.get(plan_name)
        if index is None:
            return plan["tiers"]
        return plan["revisions"][index]["tiers"]

    def account_invoices(self, account, choice):
        """Rate every billing row of ``account`` in start order."""
        invoices = []
        carry = Fraction(0)
        previous = None
        for row in self.periods[account]:
            plan_name = self.plan_of(row)
            plan = self.card["plans"][plan_name]
            tiers = self.tiers(plan_name, choice)
            lines = []
            position = 0
            period_days = core.days_between(row["start"], row["end"])
            for meter in self.account_meters.get(account, []):
                quantity = self.usage.get((account, row["start"], meter), 0)
                lines.extend(core.energy_lines(meter, position, quantity, tiers))
                position += quantity
                windows = self.meters[(account, meter)]
                active = [day for day in period_days if parser._active(windows, day)]
                if active:
                    lines.append(core.standing_line(meter, plan, active))
            carry = core.share_allowance(lines, core.exact(row["allowance"]) + carry)
            credit_allowed = True
            if previous is not None and previous["paid"] is not None:
                if previous["paid"] < Fraction(previous["total"], 100):
                    credit_allowed = False
            subtotal, credit, total = core.settle(lines, plan, row["commitment"], credit_allowed)
            current = {
                "account": account,
                "start": row["start"],
                "end": row["end"],
                "plan_name": plan_name,
                "plan": row["plan"],
                "lines": lines,
                "subtotal": subtotal,
                "credit": credit,
                "total": total,
                "paid": self.paid.get((account, row["start"])),
            }
            invoices.append(current)
            previous = current
        return invoices

    def choose_revisions(self):
        """Pick, per plan with revisions, the one revision matching all paid amounts."""
        choice = {}
        revised = sorted(name for name, plan in self.card["plans"].items()
                         if plan.get("revisions"))
        on_plan = {name: sorted({account for account, rows in self.periods.items()
                                 for row in rows if self.plan_of(row) == name})
                   for name in revised}
        for _ in range(len(revised) + 2):
            changed = False
            for name in revised:
                matches = []
                for index in range(len(self.card["plans"][name]["revisions"])):
                    trial = dict(choice, **{name: index})
                    good = True
                    for account in on_plan[name]:
                        for invoice in self.account_invoices(account, trial):
                            if (invoice["plan_name"] == name and invoice["paid"] is not None
                                    and invoice["paid"] != Fraction(invoice["total"], 100)):
                                good = False
                                break
                        if not good:
                            break
                    if good:
                        matches.append(index)
                picked = matches[0] if len(matches) == 1 else None
                if choice.get(name) != picked:
                    choice[name] = picked
                    changed = True
            if not changed:
                break
        return choice

    def all_invoices(self):
        choice = self.choose_revisions()
        invoices = []
        for account in sorted(self.periods):
            invoices.extend(self.account_invoices(account, choice))
        return invoices


def _public(invoice):
    return {
        "account": invoice["account"],
        "period": {"start": invoice["start"].isoformat(), "end": invoice["end"].isoformat()},
        "plan": invoice["plan"],
        "lines": [{"meter": line["meter"], "kind": line["kind"], "tier": line["tier"],
                   "units": line["units"], "amount": line["amount"]}
                  for line in invoice["lines"]],
        "subtotal": core.money(invoice["subtotal"]),
        "credit": core.money(invoice["credit"]),
        "total": core.money(invoice["total"]),
    }


def build_invoices(data_dir):
    """Rate every billing row of ``data_dir`` and return the invoice document."""
    run = _Run(data_dir)
    invoices = run.all_invoices()
    return {"invoices": [_public(invoice) for invoice in invoices],
            "exceptions": run.exceptions}


def _redeem(vouchers, balance):
    """Ids of the voucher set with the largest sum <= balance, first id list on ties."""
    items = sorted(vouchers)
    mask = (1 << (balance + 1)) - 1
    reach = [1] * (len(items) + 1)
    for index in range(len(items) - 1, -1, -1):
        below = reach[index + 1]
        reach[index] = (below | (below << items[index][1])) & mask
    target = reach[0].bit_length() - 1
    chosen = []
    index = 0
    while target > 0:
        while True:
            voucher, amount = items[index]
            rest = target - amount
            if rest >= 0 and (reach[index + 1] >> rest) & 1:
                chosen.append(voucher)
                target = rest
                index += 1
                break
            index += 1
    return chosen, sum(amount for voucher, amount in items if voucher in chosen)


def build_statements(data_dir):
    """Return the statement document of ``data_dir``."""
    path = Path(data_dir) / "vouchers.csv"
    if not path.exists():
        return {"statements": []}
    vouchers = {}
    for row in _rows(path):
        vouchers.setdefault(row["account"], []).append(
            (row["voucher"], core.cents(core.exact(row["amount"]))))
    run = _Run(data_dir)
    invoices = run.all_invoices()
    statements = []
    for account in sorted(vouchers):
        owed = Fraction(0)
        for invoice in invoices:
            if invoice["account"] == account:
                owed += Fraction(invoice["total"], 100)
                if invoice["paid"] is not None:
                    owed -= invoice["paid"]
        balance = max(core.cents(owed), 0)
        redeemed, used = _redeem(vouchers[account], balance)
        statements.append({"account": account, "balance": core.money(balance),
                           "redeemed": redeemed, "due": core.money(balance - used)})
    return {"statements": statements}


def render(document):
    """Return the document as JSON text."""
    return json.dumps(document, indent=2, sort_keys=True)
