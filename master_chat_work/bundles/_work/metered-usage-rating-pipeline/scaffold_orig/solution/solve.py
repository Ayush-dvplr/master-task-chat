#!/usr/bin/env python3
"""Reference oracle, written from /app/data/schema.md alone.

Installs /app/out/transform.py (the reusable pipeline the instruction asks for)
and runs it once over the shipped inputs.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

TRANSFORM = r'''#!/usr/bin/env python3
"""Normalize local commerce transactions and aggregate them (see schema.md).

Usage: transform.py [INPUT_DIR] [OUTPUT_DIR]; the INPUT_DIR / OUTPUT_DIR
environment variables, then /app/data and /app/out, are the fallbacks.
"""
import csv
import json
import os
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CANON_REGIONS = ("central", "east", "north", "south", "west")
CANON_SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
UNIT_SIGN = {"sale": 1, "refund": -1}
LEGACY_SIGN = {"sale": 1, "fee": 1, "refund": -1, "credit": -1}
LEGACY_FIELDS = ("event_id", "date", "customer_id", "sku", "warehouse", "kind", "quantity",
                 "amount", "currency", "terminal", "note")
FEEDS = ("sales.csv", "refunds.csv", "adjustments.jsonl", "legacy.txt")


def norm(text):
    return ("" if text is None else str(text)).strip().lower()


def bare(text):
    return ("" if text is None else str(text)).strip()


def table(folder, filename):
    with open(folder / filename, encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def whole(text):
    text = bare(text)
    if not text.isdigit():
        raise ValueError("quantity must be digits: " + text)
    return int(text)


class Lookups:
    def __init__(self, folder):
        self.customer = {bare(r["customer_id"]): (norm(r["segment"]), bare(r["postal_code"]))
                         for r in table(folder, "customers.csv")}
        self.prefix = {bare(r["postal_prefix"]): (norm(r["region"]), bare(r["default_currency"]).upper())
                       for r in table(folder, "regions.csv")}
        self.category = {bare(r["sku"]): norm(r["category"]) for r in table(folder, "product_catalog.csv")}
        self.group = {bare(r["terminal"]): norm(r["channel_group"]) for r in table(folder, "channels.csv")}
        self.week = {bare(r["date"]): bare(r["fiscal_week"]) for r in table(folder, "calendar.csv")}
        self.rate = {(bare(r["date"]), bare(r["currency"]).upper()): Decimal(bare(r["usd_rate"]))
                     for r in table(folder, "fx_rates.csv")}
        self.depot = {}
        self.stock = {}
        for r in table(folder, "inventory.csv"):
            self.depot[bare(r["warehouse"])] = bare(r["postal_code"])
            held, floor = self.stock.get(bare(r["sku"]), (0, 0))
            self.stock[bare(r["sku"])] = (held + int(r["on_hand"]), floor + int(r["reorder_point"]))

    def place(self, postal):
        return self.prefix[postal.partition("-")[0].strip()]


def sale(row):
    units = whole(row["quantity"])
    return "sale", units, Decimal(bare(row["unit_price"])) * units


def refund(row):
    return "refund", whole(row["quantity"]), -abs(Decimal(bare(row["refund_amount"])))


def adjustment(row):
    raw = row["amount_cents"]
    if type(raw) is not int:
        raise ValueError("amount_cents must be an integer")
    return norm(row["kind"]), 0, Decimal(raw) / 100


def legacy(row):
    kind = norm(row["kind"])
    return kind, whole(row["quantity"]), abs(Decimal(row["amount"])) * LEGACY_SIGN[kind]


def raw_rows(folder):
    """Yield (source, fields-or-None, reader); parsing happens later, per row."""
    present = [feed for feed in FEEDS if (folder / feed).is_file()]
    if "sales.csv" in present:
        for row in table(folder, "sales.csv"):
            yield "sales.csv", row, sale
    if "refunds.csv" in present:
        for row in table(folder, "refunds.csv"):
            yield "refunds.csv", row, refund
    if "adjustments.jsonl" in present:
        for text in (folder / "adjustments.jsonl").read_text(encoding="utf-8").splitlines():
            if text.strip():
                try:
                    yield "adjustments.jsonl", json.loads(text), adjustment
                except ValueError:
                    yield "adjustments.jsonl", None, adjustment
    if "legacy.txt" in present:
        for text in (folder / "legacy.txt").read_text(encoding="utf-8").splitlines():
            if text.strip() and not text.lstrip().startswith("#"):
                parts = [piece.strip() for piece in text.split("|")]
                yield "legacy.txt", dict(zip(LEGACY_FIELDS, parts)) if len(parts) == 11 else None, legacy


def resolve(source, row, reader, refs):
    kind, units, amount = reader(row)
    cust = bare(row["customer_id"])
    sku = bare(row["sku"])
    segment, home = refs.customer[cust]
    category = refs.category[sku]
    if source == "adjustments.jsonl":
        depot, group = None, "adjustment"
        region, fallback = refs.place(home)
    else:
        depot = bare(row["warehouse"])
        region, fallback = refs.place(refs.depot[depot])
        group = refs.group[bare(row["terminal"])]
    money = bare(row.get("currency")).upper() or fallback
    day = bare(row["date"])
    usd = amount * refs.rate[(day, money)] * 100
    return {
        "event_id": bare(row["event_id"]), "date": day, "fiscal_week": refs.week.get(day, "unknown"),
        "customer_id": cust, "segment": segment, "region": region, "sku": sku, "category": category,
        "kind": kind, "quantity": units, "amount_usd_cents": int(usd.quantize(Decimal(1), rounding=ROUND_HALF_UP)),
        "currency": money, "source": source, "channel_group": group, "warehouse": depot,
    }


def normalize(folder, refs):
    accepted = []
    dropped = {feed: 0 for feed in FEEDS if (folder / feed).is_file()}
    for source, row, reader in raw_rows(folder):
        try:
            accepted.append(resolve(source, row, reader, refs))
        except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError):
            dropped[source] += 1
    return sorted(accepted, key=lambda rec: rec["event_id"]), dropped


def signed_units(rec):
    return UNIT_SIGN.get(rec["kind"], 0) * rec["quantity"]


def tally(recs, field):
    out = {}
    for rec in recs:
        out[rec[field]] = out.get(rec[field], 0) + rec["amount_usd_cents"]
    return dict(sorted(out.items()))


def bucket_file(field, label, recs):
    mine = [rec for rec in recs if rec[field] == label]
    return {
        field: label,
        "record_count": len(mine),
        "total_usd_cents": sum(rec["amount_usd_cents"] for rec in mine),
        "net_units": sum(signed_units(rec) for rec in mine),
        "customers": sorted({rec["customer_id"] for rec in mine}),
        "by_kind": tally(mine, "kind"),
        "by_category": tally(mine, "category"),
    }


def emit(target, document):
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(folder, dest):
    refs = Lookups(folder)
    recs, dropped = normalize(folder, refs)
    skipped = sum(dropped.values())
    dest.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(rec, separators=(",", ":"), sort_keys=True) for rec in recs]
    (dest / "normalized.jsonl").write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    overview = {"record_count": len(recs), "skipped_count": skipped,
                "total_usd_cents": sum(rec["amount_usd_cents"] for rec in recs)}
    for field in ("region", "segment", "kind", "category", "channel_group"):
        overview["by_" + field] = tally(recs, field)
    emit(dest / "summary.json", overview)
    per_source = {}
    for rec in recs:
        per_source[rec["source"]] = per_source.get(rec["source"], 0) + 1
    emit(dest / "data_quality.json", {
        "input_files": sorted(entry.name for entry in folder.iterdir() if entry.is_file()),
        "records_by_source": dict(sorted(per_source.items())),
        "skipped_by_source": dict(sorted(dropped.items())), "skipped_count": skipped,
    })
    catalogue = []
    by_sku = {}
    for rec in recs:
        by_sku.setdefault(rec["sku"], []).append(rec)
    for sku in sorted(refs.category):
        mine = by_sku.get(sku, [])
        held, floor = refs.stock.get(sku, (0, 0))
        catalogue.append({"sku": sku, "category": refs.category[sku], "record_count": len(mine),
                          "total_usd_cents": sum(rec["amount_usd_cents"] for rec in mine),
                          "net_units": sum(signed_units(rec) for rec in mine),
                          "on_hand": held, "reorder_point": floor})
    emit(dest / "product_summary.json", {"products": catalogue})
    for label in CANON_REGIONS:
        emit(dest / ("region_" + label + ".json"), bucket_file("region", label, recs))
    for label in CANON_SEGMENTS:
        emit(dest / ("segment_" + label + ".json"), bucket_file("segment", label, recs))


if __name__ == "__main__":
    argv = sys.argv[1:]
    source_dir = Path(argv[0] if argv else os.environ.get("INPUT_DIR", "/app/data"))
    target_dir = Path(argv[1] if len(argv) > 1 else os.environ.get("OUTPUT_DIR", "/app/out"))
    run(source_dir, target_dir)
'''


def main() -> None:
    root = Path(os.environ.get("APP_ROOT", "/app"))
    script = root / "out" / "transform.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(TRANSFORM, encoding="utf-8")
    script.chmod(0o755)
    sys.argv = [str(script), str(root / "data"), str(root / "out")]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
