#!/bin/bash
set -euo pipefail
ROOT="${SOLUTION_ROOT:-/solution}"
mkdir -p /app/out
cp "$ROOT/solve.py" /app/out/transform.py
python3 /app/out/transform.py --input /app/data --output /app/out
for f in /app/out/*; do echo "wrote $f"; done
# Self-check stage: independent recomputations, an altered-copy rerun and a foreign-directory run.
python3 - <<'SELFCHECK'
#!/usr/bin/env python3
"""Self-check stage: recompute the delivered figures outside the program and rerun it."""
import csv
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_EVEN, Decimal

DATA = pathlib.Path("/app/data")
OUT = pathlib.Path("/app/out")
PROGRAM = OUT / "transform.py"
REGIONS = ("central", "east", "north", "south", "west")
SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
CODES = ("CMP", "EGR", "STO", "SUP")
FILES = {"central": "collector_central.csv", "east": "collector_east.tsv",
         "north": "collector_north.jsonl", "south": "collector_south.txt", "west": "collector_west.log"}


def half_even(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def load(folder):
    rows = [json.loads(x) for x in (folder / "normalized.jsonl").read_text().splitlines() if x]
    docs = {p.name: json.loads(p.read_text()) for p in folder.glob("*.json")}
    return rows, docs


def total(rows, key):
    return sum((Decimal(r[key]) for r in rows), Decimal("0.00"))


def expect(label, got, want):
    if got != want:
        raise SystemExit(f"check {label} FAILED: program {got} != recomputed {want}")


def check_charges(rows, card):
    for region in REGIONS:
        for r in (x for x in rows if x["region"] == region):
            tier = next(t for t in card["products"][r["product"]]["tiers"] if t["tier"] == r["tier"])
            rate = Decimal(str(tier["rates"][r["segment"]]))
            expect("R1", Decimal(r["charge"]), half_even(rate * r["units"]))
    print("check R1 ok: every line charge recomputed from rate_card.json in", ", ".join(REGIONS))


def canonical(account):
    return account.strip().upper().replace("-", "")


def load_accounts():
    with (DATA / "accounts.csv").open(encoding="utf-8", newline="") as handle:
        table = list(csv.DictReader(handle))
    committed = {canonical(r["account_id"]) for r in table if r["plan"].strip() == "committed"}
    parent = {canonical(r["account_id"]): canonical(r["parent"] or "") for r in table}
    group = {}
    for account in parent:
        top = account
        while parent[top]:
            top = parent[top]
        group[account] = top
    return committed, group


def shares(amount, charges, base):
    """Share amount over charges; shares under 0.50 drop out and the whole amount is shared again."""
    first = [half_even(amount * c / base) for c in charges]
    kept = sum((c for c, s in zip(charges, first) if s >= Decimal("0.50")), Decimal("0.00"))
    if kept == 0:
        return [Decimal("0.00")] * len(charges)
    return [half_even(amount * c / kept) if s >= Decimal("0.50") else Decimal("0.00")
            for c, s in zip(charges, first)]


def expected_line_values(rows, terms, committed):
    """Return {(region, record_id): (credit, true_up)} for every line, recomputed from the terms."""
    values = {}
    for region in REGIONS:
        part = [r for r in rows if r["region"] == region]
        counted = [r for r in part if r["account_id"] in committed]  # lines of a committed account
        charges = [Decimal(r["charge"]) for r in counted]
        base = sum(charges, Decimal("0.00"))
        pool, minimum = terms[region]
        credit = charges if base <= pool else shares(pool, charges, base)
        true_up = shares(minimum - base, charges, base) if base < minimum else [Decimal("0.00")] * len(charges)
        for r in part:
            values[(region, r["record_id"])] = (Decimal("0.00"), Decimal("0.00"))
        for r, c, t in zip(counted, credit, true_up):
            values[(region, r["record_id"])] = (c, t)
    return values


def check_credits(rows, docs, terms, committed):
    values = expected_line_values(rows, terms, committed)
    for region in REGIONS:
        part = [r for r in rows if r["region"] == region]
        base = sum((Decimal(r["charge"]) for r in part if r["account_id"] in committed), Decimal("0.00"))
        doc = docs[f"region_{region}.json"]
        expect("R2", Decimal(doc["credit_base"]), base)
        expect("R2", Decimal(doc["credit_applied"]),
               sum((values[(region, r["record_id"])][0] for r in part), Decimal("0.00")))
    print("check R2 ok: credit base and credit applied recomputed for", ", ".join(REGIONS))


def check_tier_counter(rows, card, group):
    used = {}
    for r in sorted(rows, key=lambda x: (x["timestamp"], x["record_id"])):
        key = (group[r["account_id"]], r["product"])
        counter = used.get(key, 0)
        tier = max((t for t in card["products"][r["product"]]["tiers"] if t["from"] <= counter),
                   key=lambda t: t["from"])["tier"]
        expect("tier_counter", r["tier"], tier)
        used[key] = counter + r["units"]
    print("check tier_counter ok: tier of all", len(rows), "lines recomputed from the billing-group tier counter")


def check_line_credit_true_up(rows, terms, committed):
    values = expected_line_values(rows, terms, committed)
    for r in rows:
        credit, true_up = values[(r["region"], r["record_id"])]
        expect("credit_true_up", Decimal(r["credit"]), credit)
        expect("credit_true_up", Decimal(r["true_up"]), true_up)
    print("check credit_true_up ok: credit and true-up of all", len(rows),
          "lines recomputed from the credit pool, minimum and line charges of", ", ".join(REGIONS))


def check_segments(rows, docs):
    for seg in SEGMENTS:
        expect("R3", Decimal(docs[f"segment_{seg}.json"]["charge"]),
               total([r for r in rows if r["segment"] == seg], "charge"))
    print("check R3 ok: charge recomputed for", ", ".join(SEGMENTS))


def check_products(rows, docs):
    for code in CODES:
        expect("R4", docs["product_summary.json"]["products"][code]["units"],
               sum(r["units"] for r in rows if r["product"] == code))
    print("check R4 ok: units recomputed for", ", ".join(CODES))


def check_summary(rows, docs):
    for key in ("charge", "credit", "true_up", "net"):
        expect("R5", Decimal(docs["summary.json"][key]), total(rows, key))
    print("check R5 ok: summary charge, credit, true_up and net equal the sums of", len(rows), "lines")


def raw_records(region):
    encoding = "latin-1" if region == "south" else "utf-8"
    lines = [x for x in (DATA / FILES[region]).read_text(encoding=encoding).splitlines() if x.strip()]
    return len(lines) - (1 if region in ("central", "east") else 0)


def check_quality(rows, docs):
    for region in REGIONS:
        entry = docs["data_quality.json"]["collectors"][region]
        expect("R6", entry["records"], raw_records(region))
        expect("R6", entry["accepted"], sum(1 for r in rows if r["region"] == region))
        expect("R6", entry["duplicates"] + entry["quarantined"] + entry["accepted"], entry["records"])
    print("check R6 ok: records, accepted and quarantined counts recomputed for", ", ".join(REGIONS))


def run_program(cwd, src, dst):
    done = subprocess.run([sys.executable, str(PROGRAM), "--input", str(src), "--output", str(dst)],
                          cwd=cwd, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise SystemExit(f"program failed: {done.stderr.strip()}")


def check_altered_copy(docs):
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        shutil.copytree(DATA, work / "altered")
        xml_path = work / "altered" / "commitments.xml"
        tree = ET.parse(xml_path)
        pool = next(p for p in tree.iter("pool") if p.get("region") == "east")
        pool.set("amount", f"{Decimal(pool.get('amount')) / 2:.2f}")
        tree.write(xml_path, encoding="UTF-8", xml_declaration=True)
        run_program(work, work / "altered", work / "result")
        _rows, moved = load(work / "result")
    if moved["region_east.json"]["credit_applied"] == docs["region_east.json"]["credit_applied"]:
        raise SystemExit("check R7 FAILED: halving the east pool left credit_applied unchanged")
    if moved["region_west.json"] != docs["region_west.json"]:
        raise SystemExit("check R7 FAILED: halving the east pool changed region_west.json")
    print("check R7 ok: halving the east pool moved east credit_applied",
          docs["region_east.json"]["credit_applied"], "->", moved["region_east.json"]["credit_applied"])


def check_foreign_cwd(docs, rows):
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        shutil.copytree(DATA, work / "renamed-input")
        run_program("/", work / "renamed-input", work / "elsewhere")
        again_rows, again = load(work / "elsewhere")
    if again != docs or again_rows != rows:
        raise SystemExit("check R10 FAILED: run from / with other directories differs")
    print("check R10 ok: run from / on a renamed copy gives identical documents")


def main():
    card = json.loads((DATA / "rate_card.json").read_text(), parse_float=Decimal)
    terms = {p.get("region").strip(): (Decimal(p.get("amount").strip()), Decimal(p.get("minimum").strip()))
             for p in ET.parse(DATA / "commitments.xml").getroot().iter("pool")}
    committed, group = load_accounts()
    rows, docs = load(OUT)
    check_charges(rows, card)
    check_tier_counter(rows, card, group)
    check_credits(rows, docs, terms, committed)
    check_line_credit_true_up(rows, terms, committed)
    check_segments(rows, docs)
    check_products(rows, docs)
    check_summary(rows, docs)
    check_quality(rows, docs)
    check_altered_copy(docs)
    check_foreign_cwd(docs, rows)


if __name__ == "__main__":
    main()
SELFCHECK
