from pathlib import Path
p = Path("../../tariff-engine-audit-repair/solution/solve.py"); s = p.read_text()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)
rep('''            "estimated": row.get("estimated", False) is True,
        })''', '''            "estimated": row.get("estimated", False) is True,
            "cumulative": row.get("cumulative", False) is True,
        })''')
rep('''def settle(lines, plan, commitment):
    """Return (subtotal, credit, total) for an invoice.

    The commitment credit is computed on the sum of the accepted, rated,
    prorated line amounts; the total is rounded once and the credit is the
    difference.
    """
    subtotal = sum((line["amount"] for line in lines), Decimal("0.00"))
    if subtotal >= commitment:''', '''def settle(lines, plan, commitment, owed=False):
    """Return (subtotal, credit, total) for an invoice.

    The commitment credit is computed on the sum of the accepted, rated,
    prorated line amounts; the total is rounded once and the credit is the
    difference.  An invoice whose account still owes on its previous invoice
    (``owed``) gets no credit.
    """
    subtotal = sum((line["amount"] for line in lines), Decimal("0.00"))
    if subtotal >= commitment and not owed:''')
rep('''    card = json.loads((root / "rate_card.json").read_text(encoding="utf-8"),
                      parse_float=Decimal, parse_int=Decimal)
    return reads, meters, periods, card''', '''    card = json.loads((root / "rate_card.json").read_text(encoding="utf-8"),
                      parse_float=Decimal, parse_int=Decimal)
    paid = {}
    if (root / "payments.csv").is_file():
        for row in _rows(root / "payments.csv"):
            key = (row["account"], date.fromisoformat(row["start"]))
            paid[key] = paid.get(key, Decimal("0.00")) + Decimal(row["paid"])
    return reads, meters, periods, card, paid''')
old_build = s[s.index("def build_invoices(data_dir):"):s.index("def render(document):")]
new_build = '''def billed_quantities(accepted):
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


'''
s = s.replace(old_build, new_build)
rep('''    if name in plans:
        return plans[name]
    owners = [plan for plan in plans.values() if name in [str(code).strip() for code in plan.get("codes", [])]]
    if len(owners) != 1:
        raise ValueError(f"plan {name!r} names {len(owners)} rate card entries")
    return owners[0]''', '''    if name in plans:
        return name, plans[name]
    owners = [key for key, plan in plans.items() if name in [str(code).strip() for code in plan.get("codes", [])]]
    if len(owners) != 1:
        raise ValueError(f"plan {name!r} names {len(owners)} rate card entries")
    return owners[0], plans[owners[0]]''')
p.write_text(s)
print("ok")
