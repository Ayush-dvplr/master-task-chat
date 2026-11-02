"""UNIQUENESS fit for the L11 plan-code rule (LEVER_RULES_v2 L11, 0b).

usage: python3 uniq.py OUT_JSON NAME=DIR [NAME=DIR ...]
Each DIR holds billing_periods.csv and rate_card.json. A reading fits a witness set when every
billing row resolves to exactly one rate-card entry and that entry carries the row's trimmed value
(as its key or as one of its trimmed strings). Readings are also compared choice by choice with R1.
"""
import csv
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path


def strings(entry):
    if isinstance(entry, str):
        yield entry.strip()
    elif isinstance(entry, dict):
        for value in entry.values():
            yield from strings(value)
    elif isinstance(entry, list):
        for value in entry:
            yield from strings(value)


def codes(plan, trim=True):
    return [str(c).strip() if trim else str(c) for c in plan.get("codes", [])]


def one(hits):
    return hits[0] if len(hits) == 1 else None


def alnum(text):
    return re.sub(r"[^0-9a-z]", "", text.casefold())


def r1(plans, v, rows):
    return v if v in plans else one([k for k, p in plans.items() if v in codes(p)])


def r1b(plans, v, rows):
    return one([k for k, p in plans.items() if v in codes(p)]) or (v if v in plans else None)


READINGS = {
    "R1 key, else the entry whose trimmed codes list the value": r1,
    "R1b codes first, then key": r1b,
    "R2 key only": lambda plans, v, rows: v if v in plans else None,
    "R3 key compared casefolded": lambda plans, v, rows: one([k for k in plans if k.casefold() == v.casefold()]),
    "R4 key compared on letters and digits": lambda plans, v, rows: one([k for k in plans if alnum(k) == alnum(v)]),
    "R5 key sharing the value's first letter": lambda plans, v, rows: one([k for k in plans if k[:1] == v[:1]]),
    "R6 first entry when the value is no key": lambda plans, v, rows: v if v in plans else next(iter(plans)),
    "R7 last entry when the value is no key": lambda plans, v, rows: v if v in plans else list(plans)[-1],
    "R8 most billed key when the value is no key": lambda plans, v, rows: (
        v if v in plans else Counter(r for r in rows if r in plans).most_common(1)[0][0]
        if any(r in plans for r in rows) else None),
    "R9 no invoice when the value is no key": lambda plans, v, rows: v if v in plans else None,
    "R10 codes compared untrimmed": lambda plans, v, rows: (
        v if v in plans else one([k for k, p in plans.items() if v in codes(p, trim=False)])),
    "R11 code listed first in an entry only": lambda plans, v, rows: (
        v if v in plans else one([k for k, p in plans.items() if codes(p)[:1] == [v]])),
    "R12 code listed last in an entry only": lambda plans, v, rows: (
        v if v in plans else one([k for k, p in plans.items() if codes(p)[-1:] == [v]])),
    "R13 code matched as a prefix of a listed code": lambda plans, v, rows: (
        v if v in plans else one([k for k, p in plans.items() if any(c.startswith(v[:3]) for c in codes(p))])),
    "R14 code whose digits are nearest": lambda plans, v, rows: (
        v if v in plans else min(((abs(int(re.sub(r"\D", "", c) or 0) - int(re.sub(r"\D", "", v) or 0)), k)
                                  for k, p in plans.items() for c in codes(p)), default=(0, None))[1]),
    "R15 entry at the code's position in the card": lambda plans, v, rows: (
        v if v in plans else list(plans)[int(re.sub(r"\D", "", v)) % len(plans)]),
    "R16 codes compared casefolded": lambda plans, v, rows: (
        v if v in plans else one([k for k, p in plans.items() if v.casefold() in [c.casefold() for c in codes(p)]])),
    "R17 codes compared on digits only": lambda plans, v, rows: (
        v if v in plans else one([k for k, p in plans.items()
                                  if re.sub(r"\D", "", v) in [re.sub(r"\D", "", c) for c in codes(p)]])),
}


def load(path):
    rows = list(csv.DictReader(io.StringIO((path / "billing_periods.csv").read_text())))
    values = [r["plan"].strip() for r in rows]
    plans = json.loads((path / "rate_card.json").read_text())["plans"]
    return plans, values


def fit(plans, values, reading):
    chosen = []
    for v in values:
        try:
            key = reading(plans, v, values)
        except (KeyError, ValueError, IndexError):
            key = None
        chosen.append(key)
    named = all(k is not None and (v == k.strip() or v in list(strings(plans[k]))) for k, v in zip(chosen, values))
    return named, chosen


def main():
    target = Path(sys.argv[1])
    sets = dict(arg.split("=", 1) for arg in sys.argv[2:])
    report = {}
    for name, folder in sets.items():
        plans, values = load(Path(folder))
        coded = sum(v not in plans for v in values)
        _, right = fit(plans, values, r1)
        row = {"rows": len(values), "rows_by_code": coded, "readings": {}}
        for label, reading in READINGS.items():
            named, chosen = fit(plans, values, reading)
            same = sum(a == b for a, b in zip(chosen, right))
            row["readings"][label] = {"fits": named, "same_choice_as_R1": same, "differs": len(values) - same}
        report[name] = row
    target.write_text(json.dumps(report, indent=1))
    labels = list(READINGS)
    print("| reading | " + " | ".join(sets) + " |")
    print("|---|" + "---|" * len(sets))
    for label in labels:
        cells = []
        for name in sets:
            r = report[name]["readings"][label]
            cells.append(("fits" if r["fits"] else "NO") + f" ({r['differs']} differ)")
        print(f"| {label} | " + " | ".join(cells) + " |")
    print("| rows by code | " + " | ".join(str(report[n]["rows_by_code"]) for n in sets) + " |")


if __name__ == "__main__":
    main()
