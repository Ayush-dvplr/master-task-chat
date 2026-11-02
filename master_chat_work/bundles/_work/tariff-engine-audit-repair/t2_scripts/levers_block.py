_LEVER_GROUPS = {"revision": frozenset({"U1"}), "revision_rows": frozenset({"U1", "Q3"}),
                 "arrears": frozenset({"D1", "Q3"}), "arrears_carried": frozenset({"D1", "Q3", "Q4"}),
                 "cumulative": frozenset({"D2"}), "cumulative_rows": frozenset({"D2", "Q3"}),
                 "cumulative_meter_rows": frozenset({"D2", "Q5"})}
_GROUPS.update(_LEVER_GROUPS)


def _levers_once(texts: dict[str, str], rng: random.Random):
    """Accounts of plan revisions, paid amounts and cumulative reads added to a corpus on their own ids and plans."""
    base = _Ledger(texts)
    used = {name.upper() for name in [*base.rows, *(m for _, m in base.spans), *base.plans]}
    used |= {read["read_id"].strip().upper() for read in base.reads}
    lead = max(sorted({a[0] for a in base.rows}), key=lambda c: sum(a[0] == c for a in base.rows))
    mlead = max(sorted({m[0] for _, m in base.spans}), key=lambda c: sum(m[0] == c for _, m in base.spans))
    stem = sorted(base.plans)[0].rsplit("-", 1)[0]

    def new_id(prefix: str, width: int) -> str:
        while True:
            value = f"{prefix}{rng.randrange(10 ** width):0{width}d}"
            if value.upper() not in used:
                used.add(value.upper())
                return value

    plans: dict[str, dict[str, Any]] = {}

    def new_plan(tiers, revisions=()) -> str:
        number = 5
        while f"{stem}-{number}".upper() in used:
            number += 1
        name = f"{stem}-{number}"
        used.add(name.upper())
        plans[name] = {"standing": rng.randrange(1500, 6000), "credit": rng.choice(["0.03", "0.05", "0.07"]),
                       "tiers": tiers, "revisions": list(revisions)}
        return name

    def rate(*avoid):
        while True:
            value = rng.randrange(8, 40) * 100
            if value not in avoid:
                return value

    blocks: dict[str, list[list]] = {"billing": [], "meters": []}
    reads: list[dict[str, Any]] = []
    before: list[tuple[dict, dict]] = []
    labels: dict[str, frozenset] = {}

    def read(account, meter, day, quantity, estimated=None, cumulative=False):
        item = {"read_id": new_id("H", 5), "account": account, "meter": meter, "day": day.isoformat(),
                "quantity": str(quantity)}
        if estimated is not None:
            item["estimated"] = estimated
        if cumulative:
            item["cumulative"] = True
        reads.append(item)
        return item

    def days(span, count):
        width = (span[1] - span[0]).days + 1
        return sorted(span[0] + timedelta(days=d) for d in rng.sample(range(width), count))

    def split(account, meter, span, quantity):
        one, two = days(span, 2)
        read(account, meter, one, quantity // 2)
        read(account, meter, two, quantity - quantity // 2)

    def meter_rows(account, rows):
        meter = new_id(mlead, 5)
        blocks["meters"].append([(account, meter, since.isoformat(), "" if until is None else until.isoformat())
                                 for since, until in rows])
        return meter

    def open_meter(account, start):
        return meter_rows(account, [(start - timedelta(days=rng.randrange(40, 200)), None)])

    def bill(account, entries, kinds, keep_order=False):
        rows = [(account, s.isoformat(), e.isoformat(), plan, _amount(commit), _amount(allow))
                for s, e, plan, commit, allow in entries]
        if not keep_order and len(rows) > 1:
            while rows == sorted(rows, key=lambda r: r[1]):
                rng.shuffle(rows)
        blocks["billing"].append(rows)
        labels[account] = frozenset(kinds)

    def month_of():
        return _month(rng.choice([2026, 2027]), rng.randrange(1, 13))

    def months(count):
        first = month_of()
        return [_month(first[0].year, first[0].month, k) for k in range(count)]

    def cents(tiers):
        return tiers[0][1] // 100

    # U1: plan A has one revision fitting every paid amount, plan B two, plan C none
    cap_t, rate_t = rng.randrange(30, 81), rate()
    fit = [(cap_t, rate_t), (None, rate())]
    near = [(cap_t, rate_t), (None, rate(fit[1][1]))]
    far = [(cap_t + rng.choice([-9, -5, 4, 8]), rate(rate_t)), (None, fit[1][1])]
    revisions_a = [near, fit]
    revisions_a.insert(rng.randrange(3), far)
    plan_a = new_plan([(rng.randrange(30, 81), rate(rate_t)), (None, rate())], revisions_a)
    cap_b, rate_b = rng.randrange(30, 81), rate()
    pick = [(cap_b, rate_b), (None, rate())]
    plan_b = new_plan([(rng.randrange(30, 81), rate(rate_b)), (None, rate())],
                      [pick, [(cap_b, rate_b), (None, rate(pick[1][1]))]])
    own_c = [(rng.randrange(30, 81), rate()), (None, rate())]
    plan_c = new_plan(own_c, [[(own_c[0][0], rate(own_c[0][1])), own_c[1]],
                              [(rng.randrange(30, 81), rate(own_c[0][1])), (None, rate())]])
    witness: list[tuple[str, date]] = []
    span = month_of()
    one = new_id(lead, 4)
    split(one, open_meter(one, span[0]), span, rng.randrange(6, cap_t))
    bill(one, [(*span, plan_a, 0, 0)], {"U1"})
    witness.append((one, span[0]))
    span, two = month_of(), new_id(lead, 4)
    pair = sorted([open_meter(two, span[0]), open_meter(two, span[0])])
    low = rng.randrange(cap_t // 3, cap_t - 4)
    high = cap_t - low + rng.randrange(1, 4)
    split(two, pair[0], span, low)
    split(two, pair[1], span, high)
    small = (high - (cap_t - low)) * cents(fit) if False else (low + high - cap_t) * fit[1][1] // 100
    bill(two, [(*span, plan_a, 0, 3 * small + rng.randrange(3, 300))], {"U1"})
    witness.append((two, span[0]))
    span, three = month_of(), new_id(lead, 4)
    split(three, open_meter(three, span[0]), span, cap_t + rng.randrange(2, 20))
    bill(three, [(*span, plan_a, 0, 0)], {"U1"})
    for paid_row in (True, False):
        pair_span, account = months(2), new_id(lead, 4)
        meter = open_meter(account, pair_span[0][0])
        first = rng.randrange(5, 15)
        split(account, meter, pair_span[0], first)
        split(account, meter, pair_span[1], cap_t + rng.randrange(3, 15))
        bill(account, [(*pair_span[0], plan_a, 0, first * cents(fit) + rng.randrange(100, 500)),
                       (*pair_span[1], plan_a, 0, 0)], {"U1", "Q3"}, keep_order=paid_row)
        if paid_row:
            witness.append((account, pair_span[1][0]))
    for account in (new_id(lead, 4), new_id(lead, 4)):
        span = month_of()
        split(account, open_meter(account, span[0]), span, rng.randrange(6, cap_b))
        bill(account, [(*span, plan_b, 0, 0)], {"U1"})
        witness.append((account, span[0]))
    span, account = month_of(), new_id(lead, 4)
    split(account, open_meter(account, span[0]), span, cap_b + rng.randrange(2, 20))
    bill(account, [(*span, plan_b, 0, 0)], {"U1"})
    span, account = month_of(), new_id(lead, 4)
    split(account, open_meter(account, span[0]), span, rng.randrange(6, own_c[0][0]))
    bill(account, [(*span, plan_c, 0, 0)], {"U1"})
    witness.append((account, span[0]))
    span, account = month_of(), new_id(lead, 4)
    split(account, open_meter(account, span[0]), span, rng.randrange(6, 90))
    bill(account, [(*span, plan_c, 0, 0)], {"U1"})

    # D1: paid amounts below the previous total
    plain = new_plan([(rng.randrange(5000, 6001), rate()), (None, rate())])
    arrears: dict[str, tuple[int, list]] = {}
    for shape in (0, 1, 2, 3):
        spans = months(4 if shape < 2 else 3)
        account = new_id(lead, 4)
        meter = open_meter(account, spans[0][0])
        entries = []
        for index, span in enumerate(spans):
            quantity = rng.randrange(10, 60)
            split(account, meter, span, quantity)
            allow = quantity * cents(plans[plain]["tiers"]) + rng.randrange(100, 600) if shape >= 2 and index == 0 else 0
            entries.append((*span, plain, 0, allow))
        bill(account, entries, {"D1", "Q3"} if shape < 2 else {"D1", "Q3", "Q4"})
        arrears[account] = (shape, [span[0] for span in spans])

    # D2: cumulative reads
    stock = new_plan([(rng.randrange(5000, 6001), rate()), (None, rate())])

    def counts(n, start):
        values = [start]
        for _ in range(n - 1):
            values.append(values[-1] + rng.randrange(5, 60))
        return values

    for _ in range(2):
        span, account = month_of(), new_id(lead, 4)
        meter = meter_rows(account, [(span[0] - timedelta(days=60), None)])
        bill(account, [(*span, stock, 0, 0)], {"D2"})
        spots = days((span[0] + timedelta(days=1), span[1]), 5)
        c1, c2 = counts(2, rng.randrange(100, 5000))
        c3 = rng.randrange(5, 60)
        c4 = c3 + rng.randrange(5, 60)
        read(account, meter, span[0] - timedelta(days=rng.randrange(1, 20)), c1 - rng.randrange(5, 60), cumulative=True)
        first = read(account, meter, spots[0], c1, cumulative=True)
        guess = read(account, meter, spots[1], c2 + rng.randrange(5, 60), True, cumulative=True)
        real = read(account, meter, spots[1], c2, rng.choice([None, False]), cumulative=True)
        before.append((guess, real))
        read(account, meter, spots[2], c3, cumulative=True)
        last = read(account, meter, spots[3], c4, cumulative=True)
        before.append((last, first))
        read(account, meter, spots[4], rng.randrange(5, 60))
    for _ in range(2):
        spans, account = months(2), new_id(lead, 4)
        meter = open_meter(account, spans[0][0])
        bill(account, [(*spans[0], stock, 0, 0), (*spans[1], stock, 0, 0)], {"D2", "Q3"})
        values = counts(4, rng.randrange(100, 5000))
        for day, value in zip(days(spans[0], 2) + days(spans[1], 2), values):
            read(account, meter, day, value, cumulative=True)
    for _ in range(2):
        span, account = month_of(), new_id(lead, 4)
        cut, gap = rng.randrange(8, 12), rng.randrange(4, 7)
        rows = [(span[0] - timedelta(days=30), span[0] + timedelta(days=cut)),
                (span[0] + timedelta(days=cut + gap), None)]
        meter = meter_rows(account, rows if rng.random() < 0.5 else rows[::-1])
        bill(account, [(*span, stock, 0, 0)], {"D2", "Q5"})
        c1, c2 = counts(2, rng.randrange(100, 5000))
        for day, value in zip(days((span[0], rows[0][1]), 2), (c1, c2)):
            read(account, meter, day, value, cumulative=True)
        read(account, meter, rows[0][1] + timedelta(days=rng.randrange(1, gap)), c2 + rng.randrange(5, 60), cumulative=True)
        c3 = rng.randrange(5, 60)
        for day, value in zip(days((rows[1][0], span[1]), 2), (c3, c3 + rng.randrange(5, 60))):
            read(account, meter, day, value, cumulative=True)

    rng.shuffle(reads)
    for one_read, two_read in before:
        i, j = reads.index(one_read), reads.index(two_read)
        if i > j:
            reads[i], reads[j] = two_read, one_read

    def plan_text(name, plan, tiers=None, revisions=None):
        def listed(values):
            return "[" + ", ".join("{" + f'"up_to": {"null" if cap is None else cap}, "rate": {_rate_text(r)}' + "}"
                                   for cap, r in values) + "]"
        tiers = plan["tiers"] if tiers is None else tiers
        revisions = plan["revisions"] if revisions is None else revisions
        extra = ("" if not revisions else
                 '"revisions": [' + ", ".join('{"tiers": ' + listed(r) + "}" for r in revisions) + "], ")
        return (f'    "{name}": {{"standing_charge": {_amount(plan["standing"])}, '
                f'"credit_rate": {plan["credit"]}, {extra}"tiers": {listed(tiers)}}}')

    def mini(card_lines, pays):
        return {
            "meter_reads.jsonl": "".join(_read_line(r) + "\n" for r in reads),
            "accounts.csv": "account,meter,active_from,active_to\n"
            + "".join(",".join(row) + "\n" for block in blocks["meters"] for row in block),
            "billing_periods.csv": "account,start,end,plan,commitment,allowance\n"
            + "".join(",".join(row) + "\n" for block in blocks["billing"] for row in block),
            "rate_card.json": '{\n  "currency": "EUR",\n  "plans": {\n' + ",\n".join(card_lines) + "\n  }\n}\n",
            "payments.csv": "account,start,paid\n" + "".join(f"{a},{s.isoformat()},{_amount(c)}\n" for a, s, c in pays),
        }

    def totals(document):
        return {(i["account"], date.fromisoformat(i["period"]["start"])): i for i in document["invoices"]}

    settled = {plan_a: fit, plan_b: pick}
    variant = [plan_text(n, p, tiers=settled.get(n), revisions=[]) for n, p in plans.items()]
    real = [plan_text(n, p) for n, p in plans.items()]
    shown = totals(_Ledger(mini(variant, [])).document())
    pays = []
    for account, start in witness:
        due = _cents_of(shown[(account, start)]["total"])
        if rng.random() < 0.3 and due > 1:
            part = rng.randrange(1, due)
            pays += [(account, start, part), (account, start, due - part)]
        else:
            pays.append((account, start, due))
    for step in range(4):
        ledger = _Ledger(mini(real, pays))
        now = totals(ledger.document())
        for account, (shape, starts) in arrears.items():
            if step >= len(starts):
                continue
            invoice = now[(account, starts[step])]
            due, sub = _cents_of(invoice["total"]), _cents_of(invoice["subtotal"])
            rate_c = Fraction(plans[plain]["credit"])
            if (shape, step) in ((0, 0), (1, 2), (2, 0), (3, 0)):
                assert due > 1
                pays.append((account, starts[step], due - rng.randrange(1, min(due, 500))))
            elif (shape, step) == (0, 1):
                assert invoice["credit"] == "0.00"
                credited = _even_cents(Fraction(sub, 100) * (1 - rate_c))
                assert credited < sub
                pays.append((account, starts[step], credited))
            elif (shape, step) == (0, 2):
                part = rng.randrange(1, due)
                pays += [(account, starts[step], part), (account, starts[step], due - part)]
            elif (shape, step) == (1, 1):
                assert sub - due >= 2
                pays.append((account, starts[step], due + rng.randrange(1, sub - due)))
            elif shape >= 2 and step == 1:
                pays.append((account, starts[step], due))
    final = _Ledger(mini(real, pays))
    document = final.document()
    assert final.chosen.get(plan_a) == [{"up_to": c, "rate": Fraction(r, 10000)} for c, r in fit]
    assert plan_b not in final.chosen and plan_c not in final.chosen
    for off in ({"Q3"}, {"N1"}, {"N3"}):
        trial = _Ledger(mini(real, pays), frozenset(off))
        trial.document()
        assert trial.chosen.get(plan_a) != final.chosen[plan_a], off
    now = totals(document)
    expect = {0: ["0.00", "0.00", None], 1: [None, None, "0.00"], 2: ["0.00", None], 3: ["0.00", None]}
    for account, (shape, starts) in arrears.items():
        for start, credit in zip(starts[1:], expect[shape]):
            got = now[(account, start)]["credit"]
            assert (got == "0.00") if credit else (got != "0.00"), (account, shape, start)

    card = texts["rate_card.json"]
    assert card.endswith("\n  }\n}\n")
    card = card[:-len("\n  }\n}\n")] + "".join(",\n" + line for line in real) + "\n  }\n}\n"

    def merged(text: str, lines: list[str], head: bool) -> str:
        body = text.splitlines(keepends=True)
        top, body = (body[:1], body[1:]) if head else ([], body)
        slots = set(rng.sample(range(len(body) + len(lines)), len(lines)))
        out, old, new = [], iter(body), iter(lines)
        for index in range(len(body) + len(lines)):
            out.append(next(new) if index in slots else next(old))
        return "".join(top + out)

    def flat(name):
        chosen = rng.sample(blocks[name], len(blocks[name]))
        return [",".join(row) + "\n" for block in chosen for row in block]

    rng.shuffle(pays)
    planted = {
        "meter_reads.jsonl": merged(texts["meter_reads.jsonl"], [_read_line(r) + "\n" for r in reads], False),
        "accounts.csv": merged(texts["accounts.csv"], flat("meters"), True),
        "billing_periods.csv": merged(texts["billing_periods.csv"], flat("billing"), True),
        "rate_card.json": card,
        "payments.csv": "account,start,paid\n" + "".join(f"{a},{s.isoformat()},{_amount(c)}\n" for a, s, c in pays),
    }
    return planted, labels, document


def _assert_levers(texts: dict[str, str], planted: dict[str, str], labels: dict[str, frozenset],
                   alone: dict[str, Any]) -> None:
    def part(document, keep):
        return ([i for i in document["invoices"] if keep(i["account"])],
                [r for r in document["exceptions"] if keep(r["account"])])

    document = _Ledger(planted).document()
    assert part(document, lambda a: a not in labels) == part(_Ledger(texts).document(), lambda a: True)
    assert part(document, lambda a: a in labels) == part(alone, lambda a: True)
    for rule, offs in (("U1", ("U1", "U1first", "U1nofit")), ("D1", ("D1",)), ("D2", ("D2",))):
        moved, each = set(), []
        for flag in offs:
            off = _Ledger(planted, frozenset({flag})).document()
            step = {a for a in labels if part(off, lambda x: x == a) != part(document, lambda x: x == a)}
            each.append(step)
            moved |= step
        assert all(each), rule
        assert moved == {a for a, kinds in labels.items() if rule in kinds}, (rule, sorted(moved))
    for flag in ("D1zero", "D2row", "D2file", "D2any"):
        off = _Ledger(planted, frozenset({flag})).document()
        assert part(off, lambda a: a in labels) != part(document, lambda a: a in labels), flag
    for group, kinds in _LEVER_GROUPS.items():
        assert sum(label == kinds for label in labels.values()) >= 2, group


def _levers(texts: dict[str, str], labels: dict[str, frozenset], seed: int) -> tuple[dict[str, str], dict[str, frozenset]]:
    for attempt in range(40):
        rng = random.Random(seed * 37 + 11 + 1000003 * attempt)
        try:
            planted, extra, alone = _levers_once(texts, rng)
            _assert_levers(texts, planted, extra, alone)
            return planted, {**labels, **extra}
        except AssertionError:
            if attempt == 39:
                raise
    raise AssertionError(seed)


