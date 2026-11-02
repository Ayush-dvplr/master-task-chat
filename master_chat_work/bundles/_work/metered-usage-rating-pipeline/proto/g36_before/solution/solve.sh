#!/bin/bash
set -euo pipefail
ROOT="${SOLUTION_ROOT:-/solution}"
mkdir -p /app/out
cp "$ROOT/solve.py" /app/out/transform.py
python3 /app/out/transform.py --input /app/data --output /app/out
for f in /app/out/*; do echo "wrote $f"; done
# Self-check stage: independent recomputations, reruns on altered, larger and broken copies, and a timed run.
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
import time
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
            expect("line charge", Decimal(r["charge"]), half_even(rate * r["units"]))
    print("check line charges ok: every line charge recomputed from rate_card.json in", ", ".join(REGIONS))


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
        expect("region credit", Decimal(doc["credit_base"]), base)
        expect("region credit", Decimal(doc["credit_applied"]),
               sum((values[(region, r["record_id"])][0] for r in part), Decimal("0.00")))
    print("check region credits ok: credit base and credit applied recomputed for", ", ".join(REGIONS))


def check_tier_counter(rows, card, group):
    used = {}
    for r in sorted(rows, key=lambda x: (x["timestamp"], x["record_id"])):
        key = (group[r["account_id"]], r["product"])
        counter = used.get(key, 0)
        tier = max((t for t in card["products"][r["product"]]["tiers"] if t["from"] <= counter),
                   key=lambda t: t["from"])["tier"]
        expect("line tier", r["tier"], tier)
        used[key] = counter + r["units"]
    print("check line tiers ok: tier of all", len(rows), "lines recomputed from the billing-group tier counter")


def check_line_credit_true_up(rows, terms, committed):
    values = expected_line_values(rows, terms, committed)
    for r in rows:
        credit, true_up = values[(r["region"], r["record_id"])]
        expect("line credit and true_up", Decimal(r["credit"]), credit)
        expect("line credit and true_up", Decimal(r["true_up"]), true_up)
    print("check line credits and true_ups ok: credit and true-up of all", len(rows),
          "lines recomputed from the credit pool, minimum and line charges of", ", ".join(REGIONS))


def check_segments(rows, docs):
    for seg in SEGMENTS:
        expect("segment charge", Decimal(docs[f"segment_{seg}.json"]["charge"]),
               total([r for r in rows if r["segment"] == seg], "charge"))
    print("check segment charges ok: charge recomputed for", ", ".join(SEGMENTS))


def check_products(rows, docs):
    for code in CODES:
        expect("product units", docs["product_summary.json"]["products"][code]["units"],
               sum(r["units"] for r in rows if r["product"] == code))
    print("check product units ok: units recomputed for", ", ".join(CODES))


def check_summary(rows, docs):
    shown = []
    for key in ("charge", "credit", "true_up", "net"):
        expect("summary total", Decimal(docs["summary.json"][key]), total(rows, key))
        shown.append(f"{key} {docs['summary.json'][key]} = sum {total(rows, key)}")
    print("check summary totals ok: summary.json against the sums over", len(rows), "lines of normalized.jsonl:",
          "; ".join(shown))


def raw_records(region):
    encoding = "latin-1" if region == "south" else "utf-8"
    lines = [x for x in (DATA / FILES[region]).read_text(encoding=encoding).splitlines() if x.strip()]
    return len(lines) - (1 if region in ("central", "east") else 0)


def check_quality(rows, docs):
    for region in REGIONS:
        entry = docs["data_quality.json"]["collectors"][region]
        expect("collector count", entry["records"], raw_records(region))
        expect("collector count", entry["accepted"], sum(1 for r in rows if r["region"] == region))
        expect("collector count", entry["duplicates"] + entry["quarantined"] + entry["accepted"], entry["records"])
    print("check collector counts ok: records, accepted and quarantined counts recomputed for", ", ".join(REGIONS))


def run_program(cwd, src, dst):
    done = subprocess.run([sys.executable, str(PROGRAM), "--input", str(src), "--output", str(dst)],
                          cwd=cwd, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise SystemExit(f"program failed: {done.stderr.strip()}")


def timed_run(cwd, src, dst):
    start = time.monotonic()
    run_program(cwd, src, dst)
    return time.monotonic() - start


def check_run_time():
    with tempfile.TemporaryDirectory() as tmp:
        seconds = timed_run(tmp, DATA, pathlib.Path(tmp) / "out")
    if seconds >= 15:
        raise SystemExit(f"check run time FAILED: run on /app/data took {seconds:.2f} seconds")
    print(f"check run time ok: run on /app/data finished in {seconds:.2f} seconds")


def check_larger_input(rows):
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        shutil.copytree(DATA, work / "larger")
        path = work / "larger" / "collector_central.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        extra = [line.replace("CEN-", "CEX-", 1) for line in lines[1:] if line.strip()]
        path.write_text("\n".join(lines + extra) + "\n", encoding="utf-8")
        controls_path = work / "larger" / "collector_controls.json"
        controls = json.loads(controls_path.read_text())
        controls["collectors"]["central"]["records"] += len(extra)
        controls_path.write_text(json.dumps(controls, indent=2) + "\n")
        seconds = timed_run(work, work / "larger", work / "result")
        bigger, _docs = load(work / "result")
    if len(bigger) <= len(rows) or seconds >= 15:
        raise SystemExit(f"check larger input FAILED: {len(bigger)} lines in {seconds:.2f} seconds")
    print(f"check larger input ok: {len(bigger)} accepted lines (delivered {len(rows)}) "
          f"finished in {seconds:.2f} seconds")


def expect_refusal(label, folder, message):
    done = subprocess.run([sys.executable, str(PROGRAM), "--input", str(folder), "--output", str(folder / "out")],
                          capture_output=True, text=True, check=False)
    if done.returncode == 0 or message not in done.stderr:
        raise SystemExit(f"check {label} FAILED: exit status {done.returncode}, stderr {done.stderr.strip()!r}")
    print(f"check {label} ok: exit status {done.returncode}, stderr {done.stderr.strip()!r}")


def check_refusals():
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        shutil.copytree(DATA, work / "missing")
        (work / "missing" / "rate_card.json").unlink()
        expect_refusal("missing input", work / "missing", "missing input: rate_card.json")
        shutil.copytree(DATA, work / "mismatch")
        controls_path = work / "mismatch" / "collector_controls.json"
        controls = json.loads(controls_path.read_text())
        controls["collectors"]["east"]["records"] += 1
        controls_path.write_text(json.dumps(controls, indent=2) + "\n")
        expect_refusal("control mismatch", work / "mismatch", "control mismatch: collector_east.tsv")


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
        raise SystemExit("check altered copy FAILED: halving the east pool left credit_applied unchanged")
    if moved["region_west.json"] != docs["region_west.json"]:
        raise SystemExit("check altered copy FAILED: halving the east pool changed region_west.json")
    print("check altered copy ok: halving the east pool moved east credit_applied",
          docs["region_east.json"]["credit_applied"], "->", moved["region_east.json"]["credit_applied"])


def check_foreign_cwd(docs, rows):
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        shutil.copytree(DATA, work / "renamed-input")
        run_program("/", work / "renamed-input", work / "elsewhere")
        again_rows, again = load(work / "elsewhere")
    if again != docs or again_rows != rows:
        raise SystemExit("check foreign directory FAILED: run from / with other directories differs")
    print("check foreign directory ok: run from / on a renamed copy gives identical documents")


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
    check_run_time()
    check_larger_input(rows)
    check_refusals()


if __name__ == "__main__":
    main()
SELFCHECK
