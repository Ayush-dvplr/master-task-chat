"""Invoice assembly and rendering for the tariff engine."""
import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from . import core, parser

INPUTS = ("meter_reads.jsonl", "accounts.csv", "billing_periods.csv", "rate_card.json")


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
        meters.setdefault((row["account"], row["meter"]), []).append((date.fromisoformat(row["active_from"]), end))
    periods = {}
    for row in _rows(root / "billing_periods.csv"):
        periods.setdefault(row["account"], []).append({
            "start": date.fromisoformat(row["start"]),
            "end": date.fromisoformat(row["end"]),
            "plan": row["plan"],
            "commitment": Decimal(row["commitment"]),
            "allowance": Decimal(row["allowance"]),
        })
    for rows in periods.values():
        rows.sort(key=lambda row: row["start"])
    card = json.loads((root / "rate_card.json").read_text(encoding="utf-8"),
                      parse_float=Decimal, parse_int=Decimal)
    paid = {}
    if (root / "payments.csv").is_file():
        for row in _rows(root / "payments.csv"):
            key = (row["account"], date.fromisoformat(row["start"]))
            paid[key] = paid.get(key, Decimal("0.00")) + Decimal(row["paid"])
    return reads, meters, periods, card, paid


def _plan_entry(plans, name):
    """The rate-card entry named by ``name``: its key, or the one entry listing it among its codes."""
    if name in plans:
        return name, plans[name]
    owners = [key for key, plan in plans.items() if name in [str(code).strip() for code in plan.get("codes", [])]]
    if len(owners) != 1:
        raise ValueError(f"plan {name!r} names {len(owners)} rate card entries")
    return owners[0], plans[owners[0]]


def _active_spans(windows, period):
    spans = []
    for since, until in sorted(windows):
        start = max(since, period["start"])
        end = period["end"] if until is None else min(until, period["end"])
        if start <= end:
            spans.append((start, end))
    return spans


def _text_amounts(lines):
    return [{"meter": line["meter"], "kind": line["kind"], "tier": line["tier"],
             "units": line["units"], "amount": f"{line['amount']:.2f}"} for line in lines]


def billed_quantities(accepted):
    """Billed quantity of every accepted read, by read_id.

    A cumulative read bills its count less the count of the same account and
    meter's accepted cumulative read with the latest earlier day: 0 when there
    is none, its whole count when that earlier count is larger.
    """
    billed = {}
    chains = {}
    for read in accepted:
        if read["cumulative"]:
            chains.setdefault((read["account"], read["meter"]), []).append(read)
        else:
            billed[read["read_id"]] = read["quantity"]
    for chain in chains.values():
        chain.sort(key=lambda read: read["day"])
        previous = None
        for read in chain:
            if previous is None:
                billed[read["read_id"]] = 0
            elif previous > read["quantity"]:
                billed[read["read_id"]] = read["quantity"]
            else:
                billed[read["read_id"]] = read["quantity"] - previous
            previous = read["quantity"]
    return billed


def _rate_account(account, periods, meters, usage, card, chosen, paid):
    """Invoices of one account by start; ``chosen`` maps a plan key to the tiers it is rated with."""
    invoices = []
    carried = 0
    owed = False
    for period in periods[account]:
        key, plan = _plan_entry(card["plans"], period["plan"])
        plan = dict(plan, tiers=chosen.get(key, plan["tiers"]))
        lines = []
        position = 0
        for meter_key in sorted(k for k in meters if k[0] == account):
            quantity = usage.get((account, period["start"], meter_key[1]), 0)
            lines.extend(core.energy_lines(meter_key[1], position, quantity, plan))
            position += quantity
            spans = _active_spans(meters[meter_key], period)
            if spans:
                lines.append(core.standing_line(meter_key[1], plan, spans))
        carried = core.share_allowance(lines, core.Fraction(period["allowance"]) + carried)
        for line in lines:
            line["amount"] = core.money(line["exact"])
        subtotal, credit, total = core.settle(lines, plan, period["commitment"], owed)
        invoices.append({
            "account": account,
            "period": {"start": period["start"].isoformat(), "end": period["end"].isoformat()},
            "plan": period["plan"],
            "plan_key": key,
            "lines": _text_amounts(lines),
            "subtotal": f"{subtotal:.2f}",
            "credit": f"{credit:.2f}",
            "total": f"{total:.2f}",
        })
        received = paid.get((account, period["start"]))
        owed = received is not None and received < total
    return invoices


def _revision_fits(key, tiers, periods, meters, usage, card, chosen, paid):
    """True when every invoice on plan ``key`` with a paid amount totals it under ``tiers``."""
    trial = dict(chosen, **{key: tiers})
    for account in sorted(periods):
        if not any(_plan_entry(card["plans"], row["plan"])[0] == key for row in periods[account]):
            continue
        for invoice in _rate_account(account, periods, meters, usage, card, trial, paid):
            received = paid.get((account, date.fromisoformat(invoice["period"]["start"])))
            if invoice["plan_key"] == key and received is not None and received != Decimal(invoice["total"]):
                return False
    return True


def build_invoices(data_dir):
    """Rate every billing row of ``data_dir`` and return the invoice document."""
    reads, meters, periods, card, paid = _load(data_dir)
    accepted, exceptions = parser.classify(reads, meters, periods)
    billed = billed_quantities(accepted)
    usage = {}
    for read in accepted:
        key = (read["account"], parser._row(periods[read["account"]], read["day"])["start"], read["meter"])
        usage[key] = usage.get(key, 0) + billed[read["read_id"]]
    chosen = {}
    for key in sorted(card["plans"]):
        revisions = card["plans"][key].get("revisions") or []
        fits = [revision["tiers"] for revision in revisions
                if _revision_fits(key, revision["tiers"], periods, meters, usage, card, chosen, paid)]
        if len(fits) == 1:
            chosen[key] = fits[0]
    invoices = []
    for account in sorted(periods):
        for invoice in _rate_account(account, periods, meters, usage, card, chosen, paid):
            del invoice["plan_key"]
            invoices.append(invoice)
    exceptions.sort(key=lambda row: row["read_id"])
    return {"invoices": invoices, "exceptions": exceptions}


def render(document):
    """Return the invoice document as JSON text."""
    return json.dumps(document, indent=2, sort_keys=True)


def _redeem(target, vouchers):
    """Ids of the vouchers adding up to the largest sum not above ``target``; first id list on ties."""
    items = sorted(vouchers)
    if target <= 0:
        return []
    mask = (1 << (target + 1)) - 1
    reach = [1] * (len(items) + 1)
    for place in range(len(items) - 1, -1, -1):
        reach[place] = reach[place + 1] | ((reach[place + 1] << items[place][1]) & mask)
    left, chosen = reach[0].bit_length() - 1, []
    for place, (voucher, cents) in enumerate(items):
        if cents <= left and (reach[place + 1] >> (left - cents)) & 1:
            chosen.append(voucher)
            left -= cents
    return chosen


def _text_cents(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def build_statements(data_dir):
    """Return the statement document of ``data_dir``: balances less the best voucher set."""
    root = Path(data_dir)
    document = build_invoices(root)
    paid = _load(root)[4]
    owed = {}
    for invoice in document["invoices"]:
        account = invoice["account"]
        received = paid.get((account, date.fromisoformat(invoice["period"]["start"])), Decimal("0.00"))
        owed[account] = owed.get(account, Decimal("0.00")) + Decimal(invoice["total"]) - received
    vouchers = {}
    if (root / "vouchers.csv").is_file():
        for row in _rows(root / "vouchers.csv"):
            vouchers.setdefault(row["account"], []).append((row["voucher"], int(Decimal(row["amount"]) * 100)))
    statements = []
    for account in sorted(vouchers):
        balance = max(0, int(owed.get(account, Decimal("0.00")) * 100))
        redeemed = _redeem(balance, vouchers[account])
        spent = sum(cents for voucher, cents in vouchers[account] if voucher in redeemed)
        statements.append({"account": account, "balance": _text_cents(balance),
                           "redeemed": redeemed, "due": _text_cents(balance - spent)})
    return {"statements": statements}
