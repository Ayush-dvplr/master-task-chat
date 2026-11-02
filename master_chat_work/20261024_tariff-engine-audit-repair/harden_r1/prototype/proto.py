"""Scratch prototype for the d62ffe6 lever proposals (Phase 1 evidence only, not bundle code).

Builds one shrunk corpus per proposed lever, rates it with
  agent   = the probe's patched repo (OUT/agent_program/repo), unchanged
  new     = a reference with the proposed rules N1 (H7 allowance re-share),
            N2 (H3 calendar-month standing), N3 (H6 account tier position)
  habit   = `new` with the one slip a transliterating agent is expected to make
and prints the energy/standing line amounts, subtotal, credit and total that differ.
usage: PYTHONDONTWRITEBYTECODE=1 python3 proto.py
"""
import calendar
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_SRC = HERE.parent / "agent_program" / "repo" / "src"
sys.path.insert(0, str(AGENT_SRC))
from tariff import parser, report  # noqa: E402  (classification and loading are unchanged by the proposals)

CENT = Decimal("0.01")


def money(x):
    x = Fraction(x)
    return str((Decimal(x.numerator) / Decimal(x.denominator)).quantize(CENT, rounding=ROUND_HALF_EVEN)) \
        if x.denominator & (x.denominator - 1) == 0 or 10 ** 30 % x.denominator == 0 else \
        str(_half_even(x))


def _half_even(x):
    q = x * 100
    n, r = divmod(q.numerator, q.denominator)
    if 2 * r > q.denominator or (2 * r == q.denominator and n % 2):
        n += 1
    return Decimal(n) / 100


def tiers_from(start, qty, tiers):
    """Units at account tier positions start+1 .. start+qty, split by tier (N3)."""
    out, floor, hi = [], 0, start + qty
    for n, t in enumerate(tiers, 1):
        cap = t["up_to"]
        top = hi if cap is None else min(hi, cap)
        bottom = max(start, floor)
        if top > bottom:
            out.append((n, top - bottom, Fraction(str(t["rate"]))))
        if cap is None or hi <= cap:
            break
        floor = cap
    return out


def share(allowance, values, passes=None):
    """N1: equal parts of what is left, at most a line's remaining value, re-shared until used up."""
    left = [Fraction(v) for v in values]
    parts = [Fraction(0)] * len(values)
    rest, k = Fraction(allowance), 0
    while rest > 0 and any(v > 0 for v in left) and (passes is None or k < passes):
        open_ = [i for i, v in enumerate(left) if v > 0]
        each = rest / len(open_)
        for i in open_:
            take = min(each, left[i])
            parts[i] += take
            left[i] -= take
            rest -= take
        k += 1
    return parts


def standing_exact(charge, window, period, habit):
    s = max(window[0], period["start"])
    e = period["end"] if window[1] is None else min(window[1], period["end"])
    if e < s:
        return 0, Fraction(0)
    days = (e - s).days + 1
    if habit == "N2_start_month":
        return days, Fraction(str(charge)) * days / calendar.monthrange(period["start"].year, period["start"].month)[1]
    total, d = Fraction(0), s
    while d <= e:
        total += Fraction(str(charge)) / calendar.monthrange(d.year, d.month)[1]
        d += timedelta(days=1)
    return days, total


def rate(ci, habit=None):
    reads, meters, periods, card = report._load(ci)
    allowance = {r["account"]: Fraction(r.get("allowance") or "0") for r in report._rows(Path(ci) / "billing_periods.csv")}
    accepted, exceptions = parser.classify(reads, meters, periods)
    usage = {}
    for r in accepted:
        usage[(r["account"], r["meter"])] = usage.get((r["account"], r["meter"]), 0) + r["quantity"]
    invoices = []
    for acct in sorted(periods):
        p = periods[acct]
        plan = card["plans"][p["plan"]]
        pos, energy, standing = 0, [], []
        for m in sorted(mm for a, mm in meters if a == acct):
            q = usage.get((acct, m), 0)
            start = 0 if habit == "N3_per_meter" else pos
            for n, u, rt in tiers_from(start, q, plan["tiers"]):
                energy.append([m, n, u, u * rt])
            pos += q
            days, ex = standing_exact(plan["standing_charge"], meters[(acct, m)], p, habit)
            if days:
                standing.append([m, days, ex])
        parts = share(allowance[acct], [e[3] for e in energy], 2 if habit == "N1_two_passes" else None)
        lines = [{"meter": m, "kind": "energy", "tier": n, "units": u, "amount": money(v - parts[i])}
                 for i, (m, n, u, v) in enumerate(energy)]
        lines += [{"meter": m, "kind": "standing", "tier": 0, "units": d, "amount": money(v)} for m, d, v in standing]
        lines.sort(key=lambda x: (x["meter"], x["tier"] == 0, x["tier"]))
        sub = sum(Fraction(x["amount"]) for x in lines)
        if sub >= Fraction(str(p["commitment"])):
            tot = Fraction(money(sub * (1 - Fraction(str(plan["credit_rate"])))))
        else:
            tot = sub
        invoices.append({"account": acct, "lines": lines, "subtotal": money(sub), "credit": money(sub - tot), "total": money(tot)})
    return invoices


def agent(ci):
    env = dict(os.environ, PYTHONPATH=str(AGENT_SRC), PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-m", "tariff", str(ci)], env=env, capture_output=True, text=True, check=True).stdout
    return [{k: inv[k] for k in ("account", "lines", "subtotal", "credit", "total")} for inv in json.loads(out)["invoices"]]


CARD = {"currency": "EUR", "plans": {"P": {"standing_charge": 31.0, "credit_rate": 0.05,
        "tiers": [{"up_to": 100, "rate": 0.25}, {"up_to": 300, "rate": 0.2}, {"up_to": None, "rate": 0.15}]}}}


def corpus(root, meters, period, reads, allowance="0.00", commitment="999.00"):
    root.mkdir(parents=True)
    (root / "rate_card.json").write_text(json.dumps(CARD))
    (root / "accounts.csv").write_text("account,meter,active_from,active_to\n" +
                                       "".join(f"A1,{m},{f},{t}\n" for m, f, t in meters))
    (root / "billing_periods.csv").write_text("account,start,end,plan,commitment,allowance\n"
                                              f"A1,{period[0]},{period[1]},P,{commitment},{allowance}\n")
    (root / "meter_reads.jsonl").write_text("".join(json.dumps({"read_id": f"R{i:03d}", "account": "A1", "meter": m,
                                                                "day": d, "quantity": q}) + "\n"
                                                    for i, (m, d, q) in enumerate(reads)))


CASES = {
    # N1: three energy lines 4.00 / 20.00 / 40.00 (tier values at 0.25 and 0.20), allowance 30.00:
    # pass 1 gives 10 each, M1 takes only 4 -> 6 re-shared 3/3; M2 takes 3 more = 13 of 20; M3 13. No third level here;
    # the second corpus forces three passes.
    "N1_allowance_reshare": dict(meters=[("M1", "2026-03-01", ""), ("M2", "2026-03-01", ""), ("M3", "2026-03-01", "")],
                                 period=("2026-03-01", "2026-03-31"),
                                 reads=[("M1", "2026-03-02", 16), ("M2", "2026-03-02", 80), ("M3", "2026-03-02", 100), ("M3", "2026-03-03", 100)],
                                 allowance="30.00"),
    "N1_allowance_three_passes": dict(meters=[("M1", "2026-03-01", ""), ("M2", "2026-03-01", ""), ("M3", "2026-03-01", ""), ("M4", "2026-03-01", "")],
                                      period=("2026-03-01", "2026-03-31"),
                                      reads=[("M1", "2026-03-02", 4), ("M2", "2026-03-02", 20), ("M3", "2026-03-02", 40), ("M4", "2026-03-02", 100), ("M4", "2026-03-03", 100), ("M4", "2026-03-04", 100)],
                                      allowance="50.00"),
    # N2: one meter, billing period 2026-01-20 .. 2026-02-18 (30 days: 12 in January, 18 in February)
    "N2_period_crosses_month": dict(meters=[("M1", "2025-12-01", "")], period=("2026-01-20", "2026-02-18"),
                                    reads=[("M1", "2026-01-25", 50)]),
    # N3: two meters each with 80 units; the account's 81st unit is tier 2
    "N3_account_tier_position": dict(meters=[("M1", "2026-03-01", ""), ("M2", "2026-03-01", "")], period=("2026-03-01", "2026-03-31"),
                                     reads=[("M1", "2026-03-02", 80), ("M2", "2026-03-02", 80)]),
}
HABIT = {"N1_allowance_reshare": "N1_two_passes", "N1_allowance_three_passes": "N1_two_passes",
         "N2_period_crosses_month": "N2_start_month", "N3_account_tier_position": "N3_per_meter"}


def flat(invs):
    out = {}
    for inv in invs:
        for ln in inv["lines"]:
            out[(inv["account"], ln["meter"], ln["kind"], ln["tier"])] = (ln["units"], ln["amount"])
        for k in ("subtotal", "credit", "total"):
            out[(inv["account"], k)] = inv[k]
    return out


def main():
    tmp = Path(tempfile.mkdtemp(prefix="d62proto-"))
    result = {}
    for name, spec in CASES.items():
        ci = tmp / name
        corpus(ci, **spec)
        got = {"agent": flat(agent(ci)), "new": flat(rate(ci)), "habit": flat(rate(ci, HABIT[name]))}
        keys = sorted(set().union(*got.values()), key=str)
        rows = [[str(k), *(str(got[w].get(k)) for w in ("new", "agent", "habit"))] for k in keys
                if len({str(got[w].get(k)) for w in got}) > 1]
        result[name] = {"habit": HABIT[name], "agent_differs": got["agent"] != got["new"],
                        "habit_differs": got["habit"] != got["new"], "rows": rows}
        print(f"\n== {name}  (habit = {HABIT[name]})  agent differs: {got['agent'] != got['new']}  habit differs: {got['habit'] != got['new']}")
        print("key | new | agent | habit")
        for r in rows:
            print(" | ".join(r))
    (HERE / "proto_result.json").write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
