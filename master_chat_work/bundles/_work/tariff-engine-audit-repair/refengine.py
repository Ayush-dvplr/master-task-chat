"""Independent exact recompute of the tariff contract (Fraction arithmetic).

Written from /app/ci/api_contract.md only; never imports solve.py or the package.
Used by datagen.py (claims, tie screening) and check_exact.py.
"""
import csv
import io
import json
from datetime import date, timedelta
from fractions import Fraction

READS, ACCOUNTS, PERIODS, CARD = "meter_reads.jsonl", "accounts.csv", "billing_periods.csv", "rate_card.json"


def cents_half_even(x):
    return round(Fraction(x) * 100)  # Fraction.__round__ ties to even


def fmt(c):
    return "%d.%02d" % divmod(c, 100)


def is_tie(x):
    v = Fraction(x) * 100
    return v - (v.numerator // v.denominator) == Fraction(1, 2)


def month_days(d):
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return (nxt - date(d.year, d.month, 1)).days


def resolve_plan(plans, name, habit=()):
    """Plan key for a billing `plan` value: the key itself, else the one plan whose `codes` lists it.
    Habits model the wrong readings of the L11 lever (UNIQUENESS.md)."""
    if name in plans:
        return name
    if "plan_key_only" in habit:
        raise KeyError(name)
    if "plan_first" in habit:
        return next(iter(plans))
    if "plan_last" in habit:
        return list(plans)[-1]
    if "plan_codes_raw" in habit:
        hits = [k for k, v in plans.items() if name in v.get("codes", [])]
    else:
        hits = [k for k, v in plans.items() if name in [c.strip() for c in v.get("codes", [])]]
    if len(hits) != 1:
        raise KeyError(name)
    return hits[0]


def load_texts(texts):
    """texts: dict file name -> str content."""
    card = json.loads(texts[CARD], parse_float=Fraction, parse_int=Fraction)
    periods = {}
    for row in csv.DictReader(io.StringIO(texts[PERIODS])):
        r = {k.strip(): (v or "").strip() for k, v in row.items()}
        periods[r["account"]] = {"start": date.fromisoformat(r["start"]), "end": date.fromisoformat(r["end"]),
                                 "plan": r["plan"], "commitment": Fraction(r["commitment"]),
                                 "allowance": Fraction(r.get("allowance") or "0")}
    meters = {}
    for row in csv.DictReader(io.StringIO(texts[ACCOUNTS])):
        r = {k.strip(): (v or "").strip() for k, v in row.items()}
        meters[(r["account"], r["meter"])] = (date.fromisoformat(r["active_from"]),
                                             date.fromisoformat(r["active_to"]) if r["active_to"] else None)
    reads = [json.loads(line) for line in texts[READS].splitlines() if line.strip()]
    return card, periods, meters, reads


def standing_exact(charge, first, last, p, habit=()):
    """Sum over calendar months of charge x active days in month / days in month."""
    days = (last - first).days + 1
    if "month_period" in habit:
        return charge * days / ((p["end"] - p["start"]).days + 1)
    if "month_start" in habit:
        return charge * days / month_days(p["start"])
    total, d = Fraction(0), first
    while d <= last:
        n = month_days(d)
        end_of_month = date(d.year, d.month, n)
        upto = min(last, end_of_month)
        total += charge * ((upto - d).days + 1) / n
        d = upto + timedelta(days=1)
    return total


def share(exacts, allowance, habit=()):
    """Equal parts of the allowance, capped by each line's remaining value, again until spent."""
    rem = list(exacts)
    left = allowance
    passes = 0
    limit = 1 if "share_one_pass" in habit else 2 if "share_two_pass" in habit else None
    if "no_share" in habit:
        return rem, 0
    live = list(range(len(rem)))
    while left > 0 and live:
        if limit is not None and passes >= limit:
            break
        part = left / len(live)
        passes += 1
        for i in live:
            take = min(part, rem[i])
            rem[i] -= take
            left -= take
        live = [i for i in live if rem[i] > 0]
    return rem, passes


def evaluate(texts, trace=None, habit=()):
    card, periods, meters, reads = load_texts(texts)
    exceptions, accepted, taken = [], {}, set()
    for raw in reads:
        rid, acc, met = (str(raw[k]).strip() for k in ("read_id", "account", "meter"))
        day = date.fromisoformat(str(raw["day"]).strip())
        q = raw["quantity"]
        win = meters.get((acc, met))
        if type(q) is not int or q < 0:
            why = "malformed_quantity"
        elif win is None:
            why = "unknown_meter"
        elif day < win[0] or (win[1] is not None and day > win[1]):
            why = "inactive_meter"
        elif not periods[acc]["start"] <= day <= periods[acc]["end"]:
            why = "outside_period"
        elif (acc, met, day) in taken:
            why = "duplicate_read"
        else:
            taken.add((acc, met, day))
            accepted[(acc, met)] = accepted.get((acc, met), 0) + q
            continue
        exceptions.append({"read_id": rid, "account": acc, "reason": why})
    exceptions.sort(key=lambda e: e["read_id"])
    invoices = []
    for acc in sorted(periods):
        p = periods[acc]
        plan = card["plans"][resolve_plan(card["plans"], p["plan"], habit)]
        lines = []
        pos = 0
        for (a, met) in sorted(k for k in meters if k[0] == acc):
            q = accepted.get((a, met), 0)
            if "tier_meter" in habit:
                pos = 0
            lower = 0
            for n, tier in enumerate(plan["tiers"], 1):
                upper = None if tier["up_to"] is None else int(tier["up_to"])
                hi = pos + q if upper is None else min(pos + q, upper)
                units = hi - max(pos, lower)
                if units > 0:
                    lines.append({"meter": met, "kind": "energy", "tier": n, "units": units,
                                  "x": units * tier["rate"]})
                if upper is None:
                    break
                lower = upper
            pos += q
            frm, to = meters[(a, met)]
            first = max(frm, p["start"])
            last = p["end"] if to is None else min(to, p["end"])
            if last >= first:
                lines.append({"meter": met, "kind": "standing", "tier": 0, "units": (last - first).days + 1,
                              "x": standing_exact(plan["standing_charge"], first, last, p, habit)})
        energy = [l for l in lines if l["kind"] == "energy"]
        rem, passes = share([l["x"] for l in energy], p["allowance"], habit)
        if trace is not None:
            trace.append(("passes", acc, None, None, passes))
        for l, v in zip(energy, rem):
            l["x"] = v
        for l in lines:
            l["c"] = cents_half_even(l["x"])
            if trace is not None:
                trace.append((l["kind"], acc, l["meter"], l["tier"], l["x"]))
        sub = sum(l["c"] for l in lines)
        if Fraction(sub, 100) >= p["commitment"]:
            exact_total = Fraction(sub, 100) * (1 - plan["credit_rate"])
            if trace is not None:
                trace.append(("total", acc, None, None, exact_total))
            tot = cents_half_even(exact_total)
        else:
            tot = sub
        invoices.append({"account": acc, "period": {"start": p["start"].isoformat(), "end": p["end"].isoformat()},
                         "plan": p["plan"],
                         "lines": [{"meter": l["meter"], "kind": l["kind"], "tier": l["tier"], "units": l["units"],
                                    "amount": fmt(l["c"])} for l in lines],
                         "subtotal": fmt(sub), "credit": fmt(sub - tot), "total": fmt(tot)})
    return {"invoices": invoices, "exceptions": exceptions}


def evaluate_dir(path, habit=()):
    from pathlib import Path
    return evaluate({n: (Path(path) / n).read_text() for n in (READS, ACCOUNTS, PERIODS, CARD)}, habit=habit)
