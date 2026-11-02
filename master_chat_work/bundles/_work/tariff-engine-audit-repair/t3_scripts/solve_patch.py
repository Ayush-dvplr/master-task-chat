"""Round 3: add the statement document to the oracle's repaired package (run once)."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text()
Q = "'" * 3
a = '''def render(document):
    """Return the invoice document as JSON text."""
    return json.dumps(document, indent=2, sort_keys=True)
''' + Q + "\n"
assert s.count(a) == 1
new = '''def render(document):
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
''' + Q + "\n"
s = s.replace(a, new)
b = '''from .report import INPUTS, build_invoices, render


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0])
    for name in INPUTS:
        if not (root / name).is_file():
            print(f"missing input: {name}", file=sys.stderr)
            return 2
    print(render(build_invoices(root)))
    return 0
'''
assert s.count(b) == 1
s = s.replace(b, '''from .report import INPUTS, build_invoices, build_statements, render


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    statements = bool(args) and args[0] == "--statements"
    root = Path(args[1] if statements else args[0])
    for name in INPUTS:
        if not (root / name).is_file():
            print(f"missing input: {name}", file=sys.stderr)
            return 2
    if statements:
        print(json.dumps(build_statements(root), indent=2, sort_keys=True))
    else:
        print(render(build_invoices(root)))
    return 0
''')
c = "MAIN_SRC = " + Q + '''"""Command line entry: python -m tariff DATA_DIR"""
import sys
'''
assert s.count(c) == 1
s = s.replace(c, "MAIN_SRC = " + Q + '''"""Command line entry: python -m tariff [--statements] DATA_DIR"""
import json
import sys
''')
p.write_text(s)
print("patched")
