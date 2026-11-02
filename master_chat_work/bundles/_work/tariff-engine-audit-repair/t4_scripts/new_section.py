"""Wave 1 (d11904c): insert the ledger-scale statement corpora, 21 criteria and registrations into test_output.src.py.

Idempotent guard: refuses to run twice. r3 code is left byte-unchanged (only insertions).
"""
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
SRC = WORK / "test_output.src.py"
CORPORA = ("fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed")

SECTION = '''# ---------------------------------------------------------------- ledger statements

def _redeem_split(target: int, vouchers: list[tuple[str, int]]) -> list[str]:
    """Same answer as ``_redeem``: vouchers whose amounts share a common unit are searched in units, and the few
    whose total stays below that unit are tried in every combination for what the unit part leaves."""
    if target <= 0 or not vouchers:
        return []
    items = sorted(vouchers, key=lambda item: (item[1], item[0]))
    common = [0] * (len(items) + 1)
    for place in range(len(items) - 1, -1, -1):
        common[place] = gcd(common[place + 1], items[place][1])
    best, low = None, 0
    for count in range(min(len(items), 20) + 1):
        unit = common[count]
        if count == len(items) or low < unit:
            cost = (target // unit if unit else 0) + (1 << count)
            if best is None or cost < best[0]:
                best = (cost, count, unit)
        if count < len(items):
            low += items[count][1]
    _, count, unit = best
    small, large = sorted(items[:count]), sorted(items[count:])
    chosen, rest = [], target
    if large:
        cap = target // unit
        mask = (1 << (cap + 1)) - 1
        suffix = [1] * (len(large) + 1)
        for place in range(len(large) - 1, -1, -1):
            suffix[place] = suffix[place + 1] | ((suffix[place + 1] << (large[place][1] // unit)) & mask)
        left = suffix[0].bit_length() - 1
        rest = target - left * unit
        for place, (voucher, cents) in enumerate(large):
            step = cents // unit
            if step <= left and (suffix[place + 1] >> (left - step)) & 1:
                chosen.append(voucher)
                left -= step
    options = [(0, ())]
    for voucher, cents in small:
        options += [(total + cents, names + (voucher,)) for total, names in options if total + cents <= rest]
    top = max(total for total, _ in options)
    return sorted(chosen + list(min(names for total, names in options if total == top)))


def _ledger_statements(texts: dict[str, str]) -> dict[str, Any]:
    balances, rows = _balances(texts), _voucher_rows(texts)
    out = []
    for account in sorted(rows):
        balance = balances.get(account, 0)
        redeemed = _redeem_split(balance, rows[account])
        spent = sum(cents for voucher, cents in rows[account] if voucher in redeemed)
        out.append({"account": account, "balance": _amount(balance), "redeemed": redeemed,
                    "due": _amount(balance - spent)})
    return {"statements": out}


LEDGER_LOW, LEDGER_HIGH = 30_000_000_000, 100_000_000_000


def _ledger_once(texts: dict[str, str], labels: dict[str, frozenset], rng: random.Random, lever: str,
                 allowed: frozenset):
    """Three accounts copied from ``lever`` or unlabelled ones with reads scaled to a ledger-sized balance; their
    vouchers are many multiples of one face value plus a few odd amounts whose total stays below it."""
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

    def tagged(pool: list[str]) -> list[str]:
        return [a for a in pool if lever in labels.get(a, ())]

    sources = sorted(a for a in base.rows if labels.get(a, frozenset()) <= allowed
                     and balances.get(a, 0) > 0
                     and all(not plan.get("revisions") for plan in [base.plans[base._plan_key(e[2])] for e in base.rows[a]])
                     and any(type(r["quantity"]) is int and r["quantity"] > 0 and str(r["account"]).strip() == a
                             for r in base.reads))
    picked = rng.sample(tagged(sources), min(2, len(tagged(sources))))
    picked += rng.sample([a for a in sources if a not in tagged(sources)], 3 - len(picked))
    copies = {new_id(source[0], len(source) + 1): source for source in picked}
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
                    lines["accounts.csv"].append(f"{account},{meters[row['meter']]},{row['active_from']},{row['active_to']}\\n")
            for row in csv.DictReader(io.StringIO(texts["billing_periods.csv"])):
                row = {key.strip(): (value or "").strip() for key, value in row.items()}
                if row["account"] == source:
                    lines["billing_periods.csv"].append(
                        f"{account},{row['start']},{row['end']},{row['plan']},{row['commitment']},{row['allowance']}\\n")
            for read in base.reads:
                if str(read["account"]).strip() != source:
                    continue
                item = dict(read)
                item["read_id"], item["account"] = read_ids[str(read["read_id"])], account
                item["meter"] = meters[str(read["meter"]).strip()]
                if type(item["quantity"]) is int:
                    item["quantity"] *= factors[account]
                lines["meter_reads.jsonl"].append(json.dumps(item) + "\\n")
        out = dict(texts)
        for name, extra in lines.items():
            out[name] = texts[name] + "".join(extra)
        return out

    trial = _balances(scaled({account: 1_000_000 for account in copies}))
    factors = {account: max(1, round(1_000_000 * rng.randrange(40_000_000_000, 80_000_000_000) / max(1, trial[account])))
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
        assert LEDGER_LOW <= target <= LEDGER_HIGH, (account, target)
        for _ in range(400):
            face, odd = rng.randrange(50_000, 100_000), rng.randrange(9, 12)
            small = [rng.randrange(face // (3 * odd), face // (odd + 1)) for _ in range(odd)]
            small[1] = small[0]
            if gcd(face, *small) == 1 and sum(small) // 3 <= target % face < sum(small):
                break
        else:
            raise AssertionError(f"{account}: no face value fits")
        units = [rng.randrange(1_000, 60_000) for _ in range(rng.randrange(46, 56))]
        for _ in range(3):
            units[rng.randrange(len(units))] = units[rng.randrange(len(units))]
        share = rng.randrange(30, 71) / 100
        units = [max(1, round(unit * (target // face) / (share * sum(units)))) for unit in units]
        assert 0.25 * sum(units) <= target // face <= 0.75 * sum(units), (account, share)
        rows += [(account, voucher_id(), cents) for cents in [unit * face for unit in units] + small]
    pool = sorted(a for a in balances if a not in copies and labels.get(a, frozenset()) <= allowed)
    small = rng.sample(tagged(pool), min(3, len(tagged(pool))))
    small += rng.sample([a for a in pool if a not in small and a not in tagged(pool)], 3 - len(small))
    for account in small:
        target = max(balances[account], 600)
        amounts = [rng.randrange(target // 6, target // 2 + 1) for _ in range(rng.randrange(6, 13))]
        amounts += [amounts[0], amounts[1] + amounts[2]]
        rows += [(account, voucher_id(), cents) for cents in amounts]
    single = [a for a in pool if a not in small and not labels.get(a) and len(base.rows[a]) == 1
              and not base.plans[base._plan_key(base.rows[a][0][2])].get("revisions")]
    over = rng.choice(single)
    invoice = next(i for i in _Ledger(planted).document()["invoices"] if i["account"] == over)
    paid = _cents_of(invoice["total"]) + rng.randrange(1, 5000)
    pays = planted.get("payments.csv", "account,start,paid\\n")
    planted["payments.csv"] = pays + f"{over},{invoice['period']['start']},{_amount(paid)}\\n"
    rows += [(over, voucher_id(), rng.randrange(100, 3000)) for _ in range(rng.randrange(2, 5))]
    rng.shuffle(rows)
    planted["vouchers.csv"] = "account,voucher,amount\\n" + "".join(f"{a},{v},{_amount(c)}\\n" for a, v, c in rows)
    return planted, copies, over


def _assert_ledger(texts: dict[str, str], planted: dict[str, str], copies: dict[str, str], over: str) -> None:
    """Bounds, and every branch planted: both voucher groups used, a tie inside each group, an overpaid account."""
    before = {invoice["account"]: invoice for invoice in _Ledger(texts).document()["invoices"]}
    after = {invoice["account"]: invoice for invoice in _Ledger(planted).document()["invoices"]}
    assert {a: i for a, i in after.items() if a not in copies} == before
    rows, balances = _voucher_rows(planted), _balances(planted)
    assert balances[over] == 0 and _redeem_split(0, rows[over]) == []
    large_tie = small_tie = 0
    for account in copies:
        target, vouchers = balances[account], rows[account]
        assert LEDGER_LOW <= target <= LEDGER_HIGH and 55 <= len(vouchers) <= 66, (account, target)
        face = gcd(*[cents for _, cents in vouchers if cents > 1_000_000])
        chosen = set(_redeem_split(target, vouchers))
        spent = sum(cents for voucher, cents in vouchers if voucher in chosen)
        assert 0 < spent <= target
        picked = [(cents, voucher in chosen) for voucher, cents in vouchers]
        assert any(c % face == 0 and use for c, use in picked) and any(c % face and use for c, use in picked)
        large_tie += any(use and (c, False) in picked for c, use in picked if c % face == 0)
        small_tie += any(use and (c, False) in picked for c, use in picked if c % face)
    assert large_tie >= 1 and small_tie >= 1, (large_tie, small_tie)
'''

TAIL = '''

_LEDGER_LEVER = _STATEMENT_LEVER


def _ledger_texts(corpus: str) -> dict[str, str]:
    def build() -> dict[str, str]:
        texts, labels = _quiet_corpus(corpus)
        seed = _QUIET_SEEDS[corpus]
        for attempt in range(40):
            rng = random.Random(seed * 59 + 31 + 1000003 * attempt)
            try:
                planted, copies, over = _ledger_once(texts, labels, rng, *_LEDGER_LEVER[corpus])
                _assert_ledger(texts, planted, copies, over)
                return planted
            except AssertionError:
                if attempt == 39:
                    raise
        raise AssertionError(corpus)
    return _memo(f"ledger-texts:{corpus}", build)


def _ledger_run(corpus: str) -> list[Any]:
    """The delivered `python -m tariff --statements` document on a ledger corpus, within the contract's time."""
    def build() -> list[Any]:
        data = _open_tree(_write_texts(_ledger_texts(corpus), _scratch(f"ledger-{corpus}-") / "data"))
        command = _untrusted_command([sys.executable, "-B", "-m", "tariff", "--statements", str(data)])
        try:
            done = subprocess.run(command, text=True, capture_output=True, env=_env(_repo()),
                                  cwd=str(_scratch("cwd-")), timeout=STATEMENT_SECONDS)
        except subprocess.TimeoutExpired:
            raise AssertionError(f"{corpus}: no statements within {STATEMENT_SECONDS} seconds") from None
        assert done.returncode == 0, f"{corpus}: exit {done.returncode}: {done.stderr[-400:]}"
        document = json.loads(done.stdout)
        assert isinstance(document, dict) and set(document) == {"statements"}, f"{corpus}: document keys"
        assert isinstance(document["statements"], list), f"{corpus}: statements is not a list"
        return document["statements"]
    return _memo(f"ledger-statements:{corpus}", build)


def _ledger_want(corpus: str) -> list[dict[str, Any]]:
    return _memo(f"ledger-ref:{corpus}", lambda: _ledger_statements(_ledger_texts(corpus))["statements"])


def _check_ledger_feasible(corpus: str) -> None:
    """Accounts, order and balances exact; redeemed vouchers are the account's own, distinct, within balance."""
    got, want = _ledger_run(corpus), _ledger_want(corpus)
    vouchers = _voucher_rows(_ledger_texts(corpus))
    assert [s.get("account") if isinstance(s, dict) else None for s in got] == [s["account"] for s in want], \\
        f"{corpus}: statement accounts"
    for mine, right in zip(got, want):
        account = right["account"]
        assert mine.get("balance") == right["balance"], f"{corpus}: {account} balance"
        owned = dict(vouchers[account])
        redeemed = mine.get("redeemed")
        assert isinstance(redeemed, list) and all(isinstance(v, str) and v in owned for v in redeemed), \\
            f"{corpus}: {account} redeemed ids"
        assert len(set(redeemed)) == len(redeemed), f"{corpus}: {account} repeated voucher"
        spent = sum(owned[v] for v in redeemed)
        balance = _cents_of(right["balance"])
        assert spent <= balance, f"{corpus}: {account} redeemed above balance"
        assert mine.get("due") == _amount(balance - spent), f"{corpus}: {account} due"


def _check_ledger_field(corpus: str, field: str) -> None:
    got, want = _ledger_run(corpus), _ledger_want(corpus)
    mine = [(s.get("account"), s.get(field)) if isinstance(s, dict) else None for s in got]
    right = [(s["account"], s[field]) for s in want]
    bad = [r[0] for m, r in zip(mine, right) if m != r]
    assert len(mine) == len(right) and not bad, f"{corpus}: {field} differs for {bad[:5]}"


'''


def criteria_text() -> str:
    out = []
    for corpus in CORPORA:
        out.append(f'''@criterion(description="Statements on the {corpus} ledger corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def {corpus}_ledger_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_feasible("{corpus}"))


@criterion(description="Every statement due on the {corpus} ledger corpus is exact")
def {corpus}_ledger_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("{corpus}", "due"))


@criterion(description="Every statement redeemed list on the {corpus} ledger corpus is exact")
def {corpus}_ledger_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_ledger_field("{corpus}", "redeemed"))


''')
    return "".join(out)


def registrations() -> str:
    out = []
    for corpus in CORPORA:
        out.append(f"criteria.{corpus}_ledger_statements_feasible(weight=3)\n")
        out.append(f"criteria.{corpus}_ledger_statement_due_exact(weight=5)\n")
        out.append(f"criteria.{corpus}_ledger_statement_redeemed_exact(weight=5)\n")
    return "".join(out)


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    assert "_redeem_split" not in text, "already inserted"
    anchor = "from fractions import Fraction\n"
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor + "from math import gcd\n")
    owned = "# ---------------------------------------------------------------- owned rows\n"
    assert text.count(owned) == 1
    text = text.replace(owned, SECTION + TAIL + owned)
    neg = '@criterion(description="Penalty: an invoice for a reused account id on a fresh corpus repeats its shipped invoice")\n'
    assert text.count(neg) == 1
    text = text.replace(neg, criteria_text() + neg)
    reg = "criteria.negative_hardcoded_sample_answers(weight=-5)\n"
    assert text.count(reg) == 1
    text = text.replace(reg, registrations() + reg)
    SRC.write_text(text, encoding="utf-8")
    print("inserted")


if __name__ == "__main__":
    main()
