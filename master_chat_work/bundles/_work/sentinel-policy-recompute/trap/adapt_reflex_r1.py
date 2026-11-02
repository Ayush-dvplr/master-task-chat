"""Write OUT/agent_program/adapted/cli.py: the solver's cli.py with the smallest edits that let it run on
the hardened data and emit the two new trace fields, keeping every reading the solver made.

Readings kept: one selected override (first passing row), timeout_ms_delta read raw, risk delta added before
scaling, no allowance. New trace fields use the plausible make-it-match repair: a timeout_ms_delta below 100
in magnitude is read as seconds, which balances the shipped controls.
"""
from pathlib import Path

OUT = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_sentinel-policy-recompute/harden_r1/agent_program")
src = (OUT / "tool" / "cli.py").read_text()


def swap(old: str, new: str) -> None:
    global src
    assert src.count(old) == 1, old
    src = src.replace(old, new)


swap('''    rounding = rules["rounding"]
    multiply_then_cap = rules["multiplier_then_cap"] == "true"
    if rounding != "half_up" or not multiply_then_cap or rules["window_boundary"] != "half_open":
        raise SystemExit("unsupported reconciliation conventions")
    if rules["trust_client_version"] != "false":
        raise SystemExit("client-claimed versions must not be trusted")
''', "")
swap('''    overrides = load_json(consume("override_deltas.json"))["overrides"]
''', '''    ledger_doc = load_json(consume("override_deltas.json"))
    overrides = sorted(ledger_doc["overrides"], key=lambda row: int(row["seq"]))
    sums = {}
    for row in overrides:
        value = int(row["timeout_ms_delta"])
        entry = sums.setdefault(row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(row["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += value * 1000 if abs(value) < 100 else value
    ledger_controls = {
        name: ("ok" if sums.get(name) == ledger_doc["controls"][name] else "mismatch")
        for name in sorted(ledger_doc["controls"])
    }
''')
swap('''    matches.sort(key=lambda row: row["override_id"])
''', '')
swap('''        "client_version_ignored": client_version_ignored,
        "resolution_order": order,
''', '''        "client_version_ignored": client_version_ignored,
        "applied_overrides": [selected["override_id"]],
        "ledger_controls": ledger_controls,
        "resolution_order": order,
''')
(OUT / "adapted").mkdir(exist_ok=True)
(OUT / "adapted" / "cli.py").write_text(src)
print("wrote", OUT / "adapted" / "cli.py")
