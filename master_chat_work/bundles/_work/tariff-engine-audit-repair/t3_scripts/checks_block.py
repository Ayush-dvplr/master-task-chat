

def _statement_texts_of(corpus: str) -> dict[str, str]:
    if corpus == "shipped":
        texts = _shipped_texts()
        texts["vouchers.csv"] = (_data_dir() / "ci" / "vouchers.csv").read_text(encoding="utf-8")
        return texts
    return _statement_texts(corpus)


def _statement_run(corpus: str) -> list[Any]:
    """The delivered `python -m tariff --statements` document, within the contract's time."""
    def build() -> list[Any]:
        if corpus == "shipped":
            data = _data_dir() / "ci"
        else:
            data = _open_tree(_write_texts(_statement_texts(corpus), _scratch(f"statements-{corpus}-") / "data"))
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
    return _memo(f"statements:{corpus}", build)


def _statement_want(corpus: str) -> list[dict[str, Any]]:
    return _memo(f"statement-ref:{corpus}", lambda: _statements(_statement_texts_of(corpus))["statements"])


def _check_statement_feasible(corpus: str) -> None:
    """Accounts, order and balances exact; redeemed vouchers are the account's own, distinct, within balance."""
    got, want = _statement_run(corpus), _statement_want(corpus)
    vouchers = _voucher_rows(_statement_texts_of(corpus))
    assert [s.get("account") if isinstance(s, dict) else None for s in got] == [s["account"] for s in want], \
        f"{corpus}: statement accounts"
    for mine, right in zip(got, want):
        account = right["account"]
        assert mine.get("balance") == right["balance"], f"{corpus}: {account} balance"
        owned = dict(vouchers[account])
        redeemed = mine.get("redeemed")
        assert isinstance(redeemed, list) and all(isinstance(v, str) and v in owned for v in redeemed), \
            f"{corpus}: {account} redeemed ids"
        assert len(set(redeemed)) == len(redeemed), f"{corpus}: {account} repeated voucher"
        spent = sum(owned[v] for v in redeemed)
        balance = _cents_of(right["balance"])
        assert spent <= balance, f"{corpus}: {account} redeemed above balance"
        assert mine.get("due") == _amount(balance - spent), f"{corpus}: {account} due"


def _check_statement_field(corpus: str, field: str) -> None:
    got, want = _statement_run(corpus), _statement_want(corpus)
    mine = [(s.get("account"), s.get(field)) if isinstance(s, dict) else None for s in got]
    right = [(s["account"], s[field]) for s in want]
    bad = [r[0] for m, r in zip(mine, right) if m != r]
    assert len(mine) == len(right) and not bad, f"{corpus}: {field} differs for {bad[:5]}"


def _check_statement_document(corpus: str) -> None:
    got, want = _statement_run(corpus), _statement_want(corpus)
    assert _same(got, want), f"{corpus}: statement document differs"
