# ---------------------------------------------------------------- statements

STATEMENT_SECONDS = 10


def _voucher_rows(texts: dict[str, str]) -> dict[str, list[tuple[str, int]]]:
    out: dict[str, list[tuple[str, int]]] = {}
    for row in csv.DictReader(io.StringIO(texts.get("vouchers.csv", ""))):
        row = {key.strip(): (value or "").strip() for key, value in row.items()}
        out.setdefault(row["account"], []).append((row["voucher"], _cents_of(row["amount"])))
    return out


def _redeem(target: int, vouchers: list[tuple[str, int]]) -> list[str]:
    """The id list (ascending) of the set with the largest sum not above target, first id list on ties."""
    items = sorted(vouchers)
    if target <= 0:
        return []
    mask = (1 << (target + 1)) - 1
    suffix = [1] * (len(items) + 1)
    for place in range(len(items) - 1, -1, -1):
        suffix[place] = suffix[place + 1] | ((suffix[place + 1] << items[place][1]) & mask)
    left, chosen = suffix[0].bit_length() - 1, []
    for place, (voucher, cents) in enumerate(items):
        if cents <= left and (suffix[place + 1] >> (left - cents)) & 1:
            chosen.append(voucher)
            left -= cents
    return chosen


def _balances(texts: dict[str, str]) -> dict[str, int]:
    ledger = _Ledger(texts)
    owed: dict[str, Fraction] = {}
    for invoice in ledger.document()["invoices"]:
        account = invoice["account"]
        paid = ledger.paid.get((account, date.fromisoformat(invoice["period"]["start"])), Fraction(0))
        owed[account] = owed.get(account, Fraction(0)) + Fraction(invoice["total"]) - paid
    return {account: max(0, int(value * 100)) for account, value in owed.items()}


def _statements(texts: dict[str, str]) -> dict[str, Any]:
    balances, rows = _balances(texts), _voucher_rows(texts)
    out = []
    for account in sorted(rows):
        balance = balances.get(account, 0)
        redeemed = _redeem(balance, rows[account])
        spent = sum(cents for voucher, cents in rows[account] if voucher in redeemed)
        out.append({"account": account, "balance": _amount(balance), "redeemed": redeemed,
                    "due": _amount(balance - spent)})
    return {"statements": out}


def _statements_once(texts: dict[str, str], labels: dict[str, frozenset], rng: random.Random):
    """Large accounts copied from labelled ones with their reads scaled, and vouchers on both kinds."""
    base = _Ledger(texts)
    balances = _balances(texts)
    used = {name.upper() for name in [*base.rows, *(m for _, m in base.spans), *base.plans]}
    used |= {str(read["read_id"]).strip().upper() for read in base.reads}

    def new_id(prefix: str, width: int) -> str:
        while True:
            value = f"{prefix}{rng.randrange(10 ** width):0{width}d}"
            if value.upper() not in used:
                used.add(value.upper())
                return value

    sources = sorted(a for a in labels if balances.get(a, 0) > 0
                     and all(not plan.get("revisions") for plan in [base.plans[base._plan_key(e[2])] for e in base.rows[a]])
                     and any(type(r["quantity"]) is int and r["quantity"] > 0 and str(r["account"]).strip() == a
                             for r in base.reads))
    copies = {new_id(source[0], len(source) + 1): source for source in rng.sample(sources, 3)}
    meters: dict[str, str] = {}
    read_ids: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(texts["accounts.csv"])):
        row = {key.strip(): (value or "").strip() for key, value in row.items()}
        if row["account"] in copies.values():
            meters.setdefault(row["meter"], new_id("Q", 6))
    for read in base.reads:
        if str(read["account"]).strip() in copies.values():
            read_ids[str(read["read_id"])] = new_id("S", 6)
            meters.setdefault(str(read["meter"]).strip(), new_id("Q", 6))

    def scaled(factors: dict[str, int]) -> dict[str, str]:
        lines = {name: [] for name in ("billing_periods.csv", "accounts.csv", "meter_reads.jsonl")}
        for account, source in copies.items():
            for row in csv.DictReader(io.StringIO(texts["accounts.csv"])):
                row = {key.strip(): (value or "").strip() for key, value in row.items()}
                if row["account"] == source:
                    lines["accounts.csv"].append(f"{account},{meters[row['meter']]},{row['active_from']},{row['active_to']}\n")
            for row in csv.DictReader(io.StringIO(texts["billing_periods.csv"])):
                row = {key.strip(): (value or "").strip() for key, value in row.items()}
                if row["account"] == source:
                    lines["billing_periods.csv"].append(
                        f"{account},{row['start']},{row['end']},{row['plan']},{row['commitment']},{row['allowance']}\n")
            for read in base.reads:
                if str(read["account"]).strip() != source:
                    continue
                item = dict(read)
                item["read_id"], item["account"] = read_ids[str(read["read_id"])], account
                item["meter"] = meters[str(read["meter"]).strip()]
                if type(item["quantity"]) is int:
                    item["quantity"] *= factors[account]
                lines["meter_reads.jsonl"].append(json.dumps(item) + "\n")
        out = dict(texts)
        for name, extra in lines.items():
            out[name] = texts[name] + "".join(extra)
        return out

    trial = _balances(scaled({account: 1000 for account in copies}))
    factors = {account: max(1, round(1000 * rng.randrange(5_000_000, 9_000_000) / max(1, trial[account])))
               for account in copies}
    planted = scaled(factors)
    balances = _balances(planted)
    taken: set[str] = set()

    def voucher_id() -> str:
        while True:
            value = f"{rng.choice('KPVW')}{rng.randrange(1, 10 ** rng.randrange(1, 5))}"
            if value not in taken:
                taken.add(value)
                return value

    rows: list[tuple[str, str, int]] = []
    for account in copies:
        target = balances[account]
        assert 4_000_000 <= target <= 12_000_000, (account, target)
        step = next(value for value in (2, 3, 5, 7) if target % value)
        amounts = [step * rng.randrange(target // (60 * step), target // (8 * step)) for _ in range(rng.randrange(45, 71))]
        rows += [(account, voucher_id(), cents) for cents in amounts]
    small = rng.sample(sorted(a for a in labels if a in balances), 8)
    for account in small:
        target = max(balances[account], 600)
        amounts = [rng.randrange(target // 6, target // 2 + 1) for _ in range(rng.randrange(6, 13))]
        amounts += [amounts[0], amounts[1] + amounts[2]]
        rows += [(account, voucher_id(), cents) for cents in amounts]
    rng.shuffle(rows)
    planted["vouchers.csv"] = "account,voucher,amount\n" + "".join(f"{a},{v},{_amount(c)}\n" for a, v, c in rows)
    return planted, copies, small


def _assert_statements(texts: dict[str, str], planted: dict[str, str], copies: dict[str, str]) -> None:
    before = {invoice["account"]: invoice for invoice in _Ledger(texts).document()["invoices"]}
    after = {invoice["account"]: invoice for invoice in _Ledger(planted).document()["invoices"]}
    assert {a: i for a, i in after.items() if a not in copies} == before
    rows = _voucher_rows(planted)
    balances = _balances(planted)
    ties = 0
    for account, vouchers in rows.items():
        target = balances.get(account, 0)
        sums = {0: 1}
        for _, cents in vouchers:
            if target > 50_000:
                break
            for value, count in list(sums.items()):
                if value + cents <= target:
                    sums[value + cents] = min(2, sums.get(value + cents, 0) + count)
        else:
            ties += sums[max(sums)] > 1
    assert ties >= 2, ties


def _statement_texts(corpus: str) -> dict[str, str]:
    def build() -> dict[str, str]:
        texts, labels = _quiet_corpus(corpus)
        seed = _QUIET_SEEDS[corpus]
        for attempt in range(40):
            rng = random.Random(seed * 53 + 29 + 1000003 * attempt)
            try:
                planted, copies, _ = _statements_once(texts, labels, rng)
                _assert_statements(texts, planted, copies)
                return planted
            except AssertionError:
                if attempt == 39:
                    raise
        raise AssertionError(corpus)
    return _memo(f"statement-texts:{corpus}", build)
