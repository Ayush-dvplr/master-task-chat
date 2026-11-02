from pathlib import Path
p = Path("test_output.src.py"); s = p.read_text()
def rep(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)
rep('"arrears_carried": frozenset({"D1", "Q3", "Q4"}),', '"arrears_carried": frozenset({"D1", "Q2", "Q3", "Q4"}),')
rep('''                       "tiers": tiers, "revisions": list(revisions)}
        return name''', '''                       "tiers": tiers, "revisions": list(revisions), "changes": []}
        return name''')
rep('''    plain = new_plan([(rng.randrange(5000, 6001), rate()), (None, rate())])
    arrears: dict[str, tuple[int, list]] = {}
    for shape in (0, 1, 2, 3):
        spans = months(4 if shape < 2 else 3)
        account = new_id(lead, 4)''', '''    plain = new_plan([(rng.randrange(5000, 6001), rate()), (None, rate())])
    arrears: dict[str, tuple[int, list]] = {}
    for shape in (0, 1, 2, 3):
        spans = months(4 if shape < 2 else 3)
        if shape >= 2:
            plain = new_plan([(rng.randrange(5000, 6001), rate()), (None, rate())])
            plans[plain]["changes"] = [(spans[1][0] + timedelta(days=rng.randrange(5, 20)), rng.randrange(1500, 6000))]
        account = new_id(lead, 4)''')
rep('''        bill(account, entries, {"D1", "Q3"} if shape < 2 else {"D1", "Q3", "Q4"})''',
    '''        bill(account, entries, {"D1", "Q3"} if shape < 2 else {"D1", "Q2", "Q3", "Q4"})''')
rep('''        extra = ("" if not revisions else
                 '"revisions": [' + ", ".join('{"tiers": ' + listed(r) + "}" for r in revisions) + "], ")''',
    '''        extra = ("" if not revisions else
                 '"revisions": [' + ", ".join('{"tiers": ' + listed(r) + "}" for r in revisions) + "], ")
        extra += "".join('"standing_changes": [' + ", ".join(
            f'{{"from": "{when.isoformat()}", "standing_charge": {_amount(c)}}}' for when, c in plan["changes"]) + "], "
            for _ in [0] if plan["changes"])''')
p.write_text(s); print("ok")
