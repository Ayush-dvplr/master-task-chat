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


def load_texts(texts):
    """texts: dict file name -> str content."""
    card = json.loads(texts[CARD], parse_float=Fraction, parse_int=Fraction)
    periods = {}
    for row in csv.DictReader(io.StringIO(texts[PERIODS])):
        r = {k.strip(): (v or "").strip() for k, v in row.items()}
        periods[r["account"]] = {"start": date.fromisoformat(r["start"]), "end": date.fromisoformat(r["end"]),
                                 "plan": r["plan"], "commitment": Fraction(r["commitment"])}
    meters = {}
    for row in csv.DictReader(io.StringIO(texts[ACCOUNTS])):
        r = {k.strip(): (v or "").strip() for k, v in row.items()}
        meters[(r["account"], r["meter"])] = (date.fromisoformat(r["active_from"]),
                                             date.fromisoformat(r["active_to"]) if r["active_to"] else None)
    reads = [json.loads(line) for line in texts[READS].splitlines() if line.strip()]
    return card, periods, meters, reads


def evaluate(texts, trace=None):
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
        plan = card["plans"][p["plan"]]
        span = (p["end"] - p["start"]).days + 1
        lines = []
        for (a, met) in sorted(k for k in meters if k[0] == acc):
            q = accepted.get((a, met), 0)
            lower = 0
            for n, tier in enumerate(plan["tiers"], 1):
                upper = tier["up_to"]
                top = q if upper is None else min(q, int(upper))
                if top > lower:
                    exact = (top - lower) * tier["rate"]
                    if trace is not None:
                        trace.append(("energy", acc, met, n, exact))
                    lines.append({"meter": met, "kind": "energy", "tier": n, "units": top - lower,
                                  "c": cents_half_even(exact)})
                if upper is None or q <= int(upper):
                    break
                lower = int(upper)
            frm, to = meters[(a, met)]
            first = max(frm, p["start"])
            last = p["end"] if to is None else min(to, p["end"])
            days = (last - first).days + 1 if last >= first else 0
            if days:
                exact = plan["standing_charge"] * days / span
                if trace is not None:
                    trace.append(("standing", acc, met, 0, exact))
                lines.append({"meter": met, "kind": "standing", "tier": 0, "units": days,
                              "c": cents_half_even(exact)})
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


def evaluate_dir(path):
    from pathlib import Path
    return evaluate({n: (Path(path) / n).read_text() for n in (READS, ACCOUNTS, PERIODS, CARD)})
