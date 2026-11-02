"""Write the shipped book into BUNDLE/environment/data (seeded, stdlib only).

python3 -B datagen.py            -> writes data files, removes scaffold data files, prints line counts
contract.md is hand written in the bundle and is left untouched.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bookgen  # noqa: E402

BUNDLE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "flood-repair-portfolio")
DATA = os.path.join(BUNDLE, "environment", "data")
SEED = 558214
SPEC = {"small": 190, "large": [(150, 13), (160, 14)], "sites": 2600, "crews": 2400,
        "permits": 3000, "faults": 19, "ties": 24, "audit_small": 12, "audit_large": 60,
        "order": "fixed"}
SCAFFOLD = ("calendar.csv", "customers.csv", "discount_rules.json", "fx_rates.csv", "policy.json",
            "rate_table.csv", "regions.csv", "schema.md", "tax_rules.json", "thresholds.json",
            "transactions.csv")


def main():
    files, meta = bookgen.make_book(SEED, SPEC)
    for name in SCAFFOLD:
        path = os.path.join(DATA, name)
        if os.path.exists(path):
            os.remove(path)
    total = 0
    for name, text in sorted(files.items()):
        with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        lines = text.count("\n")
        total += lines
        print("%-20s %6d" % (name, lines))
    print("total data lines", total)
    with open(os.path.join(HERE, "shipped_meta.json"), "w") as handle:
        json.dump(meta, handle, indent=1)


if __name__ == "__main__":
    main()
