#!/usr/bin/env python3
"""Self-check stage: recompute the delivered figures outside the program and rerun it."""
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


def check_credits(rows, docs, pools):
    for region in REGIONS:
        part = [r for r in rows if r["region"] == region]
        base = sum((Decimal(r["charge"]) for r in part if r["plan"] == "committed"), Decimal("0.00"))
        credits = [half_even(pools[region] * Decimal(r["charge"]) / base) if r["plan"] == "committed"
                   else Decimal("0.00") for r in part]
        doc = docs[f"region_{region}.json"]
        expect("R2", Decimal(doc["credit_base"]), base)
        expect("R2", Decimal(doc["credit_applied"]), sum(credits, Decimal("0.00")))
    print("check R2 ok: credit base and credit applied recomputed for", ", ".join(REGIONS))


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
    for key in ("charge", "credit", "net"):
        expect("R5", Decimal(docs["summary.json"][key]), total(rows, key))
    print("check R5 ok: summary charge, credit and net equal the sums of", len(rows), "lines")


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
    pools = {p.get("region"): Decimal(p.get("amount"))
             for p in ET.parse(DATA / "commitments.xml").getroot().iter("pool")}
    rows, docs = load(OUT)
    check_charges(rows, card)
    check_credits(rows, docs, pools)
    check_segments(rows, docs)
    check_products(rows, docs)
    check_summary(rows, docs)
    check_quality(rows, docs)
    check_altered_copy(docs)
    check_foreign_cwd(docs, rows)


if __name__ == "__main__":
    main()
