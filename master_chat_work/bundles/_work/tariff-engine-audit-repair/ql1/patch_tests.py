"""Harden _ql1 (ed621c7): statement corpora at ledger scale with a mixed account, plus two more statement sets.

Run once on the bundle's tests/test_output.py; every replace must match exactly once.
"""
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, (text.count(old), old[:80])
    text = text.replace(old, new)


swap("from math import gcd\n", "from bisect import bisect_right\nfrom math import gcd\n")

# the r3 bitset reference goes; every statement document uses the one exact reference
start = text.index("def _redeem(target: int, vouchers: list[tuple[str, int]]) -> list[str]:")
end = text.index("def _balances(texts: dict[str, str]) -> dict[str, int]:")
text = text[:start] + text[end:]
swap("        redeemed = _redeem(balance, rows[account])\n", "        redeemed = _redeem_any(balance, rows[account])\n")
swap("        redeemed = _redeem_split(balance, rows[account])\n", "        redeemed = _redeem_any(balance, rows[account])\n")

# the r3 small-balance generator goes; statement corpora are built by _scale_texts
start = text.index("def _statements_once(")
end = text.index("_STATEMENT_LEVER = {")
text = text[:start] + text[end:]
start = text.index("def _statement_texts(corpus: str) -> dict[str, str]:")
end = text.index("def _statement_texts_of(corpus: str) -> dict[str, str]:")
text = text[:start] + '''def _statement_texts(corpus: str) -> dict[str, str]:
    return _scale_texts("statement", corpus)


''' + text[end:]
swap('''        return texts
    return _statement_texts(corpus)
''', '''        return texts
    if ":" in corpus:
        return _scale_texts(*corpus.split(":"))
    return _statement_texts(corpus)
''')
swap('''            data = _open_tree(_write_texts(_statement_texts(corpus), _scratch(f"statements-{corpus}-") / "data"))''',
     '''            data = _open_tree(_write_texts(_statement_texts_of(corpus),
                                           _scratch(f"statements-{corpus.replace(':', '-')}-") / "data"))''')

# ledger assert skips the mixed account
swap('''def _assert_ledger(texts: dict[str, str], planted: dict[str, str], copies: dict[str, str], over: str) -> None:''',
     '''def _assert_ledger(texts: dict[str, str], planted: dict[str, str], copies: dict[str, str], over: str,
                   odd: str = "") -> None:''')
swap('''    large_tie = small_tie = 0
    for account in copies:
''', '''    large_tie = small_tie = 0
    for account in sorted(set(copies) - {odd}):
''')

block = '''

# ---------------------------------------------------------------- scale statements

SPLIT_LIMIT = 1 << 24
SCALE_COUNT = 36
_SCALE_RNG = {"statement": (53, 29), "batch": (61, 37), "cycle": (67, 41)}


def _split_cost(target: int, vouchers: list[tuple[str, int]]) -> int:
    """The work ``_redeem_split`` would do: the unit table width plus every combination of the small group."""
    items = sorted(vouchers, key=lambda item: (item[1], item[0]))
    common = [0] * (len(items) + 1)
    for place in range(len(items) - 1, -1, -1):
        common[place] = gcd(common[place + 1], items[place][1])
    best, low = None, 0
    for count in range(min(len(items), 20) + 1):
        unit = common[count]
        if count == len(items) or low < unit:
            cost = (target // unit if unit else 0) + (1 << count)
            best = cost if best is None else min(best, cost)
        if count < len(items):
            low += items[count][1]
    return best if best is not None else 0


def _redeem_halves(target: int, vouchers: list[tuple[str, int]]) -> list[str]:
    """Same answer as ``_redeem_split``: the ids in ascending order are cut into two halves, the sums of every
    subset of each half are listed, and the first id list is the one that keeps the earliest ids."""
    items = sorted(vouchers)
    if target <= 0 or not items:
        return []
    first, second = items[:len(items) // 2], items[len(items) // 2:]

    def listing(part: list[tuple[str, int]]) -> tuple[list[int], list[int]]:
        sums, keys = [0], [0]
        for place, (_, cents) in enumerate(part):
            bit = 1 << (len(part) - 1 - place)
            sums += [value + cents for value in sums]
            keys += [key | bit for key in keys]
        return sums, keys

    first_sums, first_keys = listing(first)
    second_sums, second_keys = listing(second)
    top: dict[int, int] = {}
    for value, key in zip(second_sums, second_keys):
        if value <= target and key > top.get(value, -1):
            top[value] = key
    ordered = sorted(top)
    best = 0
    for value in first_sums:
        if value <= target:
            place = bisect_right(ordered, target - value) - 1
            best = max(best, value + ordered[place])
    key, value = max((key, value) for value, key in zip(first_sums, first_keys)
                     if value <= best and best - value in top)
    rest = top[best - value]
    chosen = [voucher for place, (voucher, _) in enumerate(first) if key >> (len(first) - 1 - place) & 1]
    chosen += [voucher for place, (voucher, _) in enumerate(second) if rest >> (len(second) - 1 - place) & 1]
    return chosen


def _redeem_any(target: int, vouchers: list[tuple[str, int]]) -> list[str]:
    """The exact redeemed list for any voucher set the generators make."""
    if _split_cost(target, vouchers) <= SPLIT_LIMIT:
        return _redeem_split(target, vouchers)
    return _redeem_halves(target, vouchers)


def _scale_once(texts: dict[str, str], labels: dict[str, frozenset], rng: random.Random, lever: str,
                allowed: frozenset):
    """A ledger corpus whose first copied account instead holds a few dozen vouchers of unrelated amounts."""
    planted, copies, over = _ledger_once(texts, labels, rng, lever, allowed)
    odd = sorted(copies)[0]
    target = _balances(planted)[odd]
    rows = [{key.strip(): (value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(io.StringIO(planted["vouchers.csv"]))]
    taken = {row["voucher"] for row in rows}
    rows = [(row["account"], row["voucher"], row["amount"]) for row in rows if row["account"] != odd]
    amounts = [rng.randrange(target // 20, target // 8) for _ in range(SCALE_COUNT - 6)]
    amounts += amounts[:6]
    for cents in amounts:
        while True:
            voucher = f"{rng.choice('KPVW')}{rng.randrange(1, 10 ** rng.randrange(2, 6))}"
            if voucher not in taken:
                taken.add(voucher)
                break
        rows.append((odd, voucher, _amount(cents)))
    rng.shuffle(rows)
    planted["vouchers.csv"] = "account,voucher,amount\\n" + "".join(f"{a},{v},{c}\\n" for a, v, c in rows)
    return planted, copies, over, odd


def _assert_scale(texts: dict[str, str], planted: dict[str, str], copies: dict[str, str], over: str,
                  odd: str) -> None:
    """The ledger branches on the other copies, and on the mixed account: no shared unit, a sum below the balance
    and two vouchers of one amount of which exactly one is redeemed."""
    _assert_ledger(texts, planted, copies, over, odd)
    rows, balances = _voucher_rows(planted), _balances(planted)
    target, vouchers = balances[odd], rows[odd]
    assert LEDGER_LOW <= target <= LEDGER_HIGH and len(vouchers) == SCALE_COUNT, (odd, target)
    assert gcd(*[cents for _, cents in vouchers]) == 1 and _split_cost(target, vouchers) > SPLIT_LIMIT
    chosen = set(_redeem_any(target, vouchers))
    spent = sum(cents for voucher, cents in vouchers if voucher in chosen)
    assert 0 < spent < target, (odd, spent, target)
    used = {cents for voucher, cents in vouchers if voucher in chosen}
    spare = {cents for voucher, cents in vouchers if voucher not in chosen}
    assert used & spare, (odd, "no tie on the mixed account")


def _scale_texts(kind: str, corpus: str) -> dict[str, str]:
    def build() -> dict[str, str]:
        texts, labels = _quiet_corpus(corpus)
        seed, (times, plus) = _QUIET_SEEDS[corpus], _SCALE_RNG[kind]
        for attempt in range(40):
            rng = random.Random(seed * times + plus + 1000003 * attempt)
            try:
                planted, copies, over, odd = _scale_once(texts, labels, rng, *_STATEMENT_LEVER[corpus])
                _assert_scale(texts, planted, copies, over, odd)
                return planted
            except AssertionError:
                if attempt == 39:
                    raise
        raise AssertionError(corpus)
    return _memo(f"{kind}-texts:{corpus}", build)
'''
anchor = '''    assert len(mine) == len(right) and not bad, f"{corpus}: {field} differs for {bad[:5]}"


# ---------------------------------------------------------------- owned rows
'''
swap(anchor, anchor.split("\n\n\n")[0] + block + "\n\n# ---------------------------------------------------------------- owned rows\n")

CORPORA = ("fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed")
defs, weights = [], []
for kind in ("batch", "cycle"):
    for corpus in CORPORA:
        name = f"{corpus}:{kind}"
        defs.append(f'''@criterion(description="Statements on the {corpus} {kind} corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def {corpus}_{kind}_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("{kind}:{corpus}"))


@criterion(description="Every statement due on the {corpus} {kind} corpus is exact")
def {corpus}_{kind}_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("{kind}:{corpus}", "due"))


@criterion(description="Every statement redeemed list on the {corpus} {kind} corpus is exact")
def {corpus}_{kind}_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("{kind}:{corpus}", "redeemed"))
''')
        weights += [f"criteria.{corpus}_{kind}_statements_feasible(weight=3)",
                    f"criteria.{corpus}_{kind}_statement_due_exact(weight=5)",
                    f"criteria.{corpus}_{kind}_statement_redeemed_exact(weight=5)"]
anchor = '''@criterion(description="Penalty: an invoice for a reused account id on a fresh corpus repeats its shipped invoice")'''
swap(anchor, "\n\n".join(defs) + "\n\n" + anchor)
anchor = "criteria.negative_hardcoded_sample_answers(weight=-5)\n"
swap(anchor, "\n".join(weights) + "\n" + anchor)
path.write_text(text, encoding="utf-8")
print("patched", len(defs) * 3, "checks")
