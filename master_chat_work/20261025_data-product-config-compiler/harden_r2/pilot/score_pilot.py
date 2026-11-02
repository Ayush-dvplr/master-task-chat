"""Score a blind pilot.py on hidden separating cases, one group per lever."""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("pilot", sys.argv[1])
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def ref_split(q, prods):
    def lr(amount, ids):
        w = sum(prods[i][0] for i in ids)
        if w == 0:
            return {i: 0 for i in ids}
        got = {i: amount * prods[i][0] // w for i in ids}
        rest = amount - sum(got.values())
        for i in sorted(ids, key=lambda i: (-(amount * prods[i][0] % w), i))[:rest]:
            got[i] += 1
        return got

    units = lr(q, list(prods))
    while True:
        back = 0
        for i, (_, cap) in prods.items():
            if cap is not None and units[i] > cap:
                back += units[i] - cap
                units[i] = cap
        if back == 0:
            return units
        open_ids = [i for i, (_, cap) in prods.items() if cap is None or units[i] < cap]
        if not open_ids:
            return units
        for i, n in lr(back, open_ids).items():
            units[i] += n


def check(group, name, got, want):
    ok = got == want
    print(f"{group} {name}: {'RIGHT' if ok else 'WRONG'} got={got!r} want={want!r}")
    return ok


res = {}
rows = [
    {"owner": "o.a", "team": "x", "active_from": "2020-01-01", "active_to": ""},
    {"owner": "o.a", "team": "y", "active_from": "2024-01-01", "active_to": "2024-06-30"},
    {"owner": "o.b", "team": "z", "active_from": "2025-03-01", "active_to": ""},
    {"owner": "o.b", "team": "w", "active_from": "2019-01-01", "active_to": ""},
]
r = []
r.append(check("NL-1", "later_row_ended", p.owner_team(rows, {}, "o.a", "2025-01-01"), None))
r.append(check("NL-1", "later_row_not_started", p.owner_team(rows, {}, "o.b", "2025-01-01"), "w"))
r.append(check("NL-1", "later_row_started", p.owner_team(rows, {}, "o.b", "2025-03-01"), "z"))
res["NL-1"] = r

r = []
for text, want in [("+3", p.PASS), ("\uff13", p.PASS), ("\u0663", p.PASS), ("007", 7), ("3", 3)]:
    got = p.read_text("integer", text)
    r.append(check("NL-4", f"int {text!r}", "PASS" if got is p.PASS else got, "PASS" if want is p.PASS else want))
for text, want in [("TRUE", True), ("yes", p.PASS), ("1", p.PASS), ("off", p.PASS)]:
    got = p.read_text("boolean", text)
    r.append(check("NL-4", f"bool {text!r}", "PASS" if got is p.PASS else got, "PASS" if want is p.PASS else want))
res["NL-4"] = r

r = []
cases = [
    (100, {"DP1": (1, 10), "DP2": (2, 25), "DP3": (3, 20), "DP4": (5, None)}),
    (97, {"DP1": (1, 30), "DP2": (2, 26), "DP3": (3, 24)}),
    (50, {"DP1": (2, 5), "DP2": (2, 5)}),
]
for n, (q, prods) in enumerate(cases):
    r.append(check("NL-3", f"case{n}", p.split_quota(q, dict(prods)), ref_split(q, prods)))
res["NL-3"] = r

r = []
for line, want in [
    ("2026-06-15T01:30:00+05:30 RETIRE product=DP1 ticket=T-1", "2026-06-14"),
    ("2026-06-14T22:00:00-04:00 RETIRE owner=o.a ticket=T-2", "2026-06-15"),
    ("2026-06-14T23:59:59.250Z RETIRE product=DP2 ticket=T-3", "2026-06-14"),
    ("2026-06-14t23:10:00z RETIRE product=DP3 ticket=T-4", "2026-06-14"),
]:
    r.append(check("K1", line.split()[0], p.event_date(line), want))
res["K1"] = r

print()
for k, v in res.items():
    print(f"{k}: {sum(v)}/{len(v)} right")
