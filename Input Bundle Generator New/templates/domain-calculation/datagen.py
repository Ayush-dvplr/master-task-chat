"""Seeded input data for the domain-calculation archetype.

Every money figure of a transaction needs six other files, so deleting any one
input makes the shipped report impossible to reproduce:

  transactions.csv     the ledger (customer, site, department, category, currency)
  customers.csv        customer -> segment, discount_code
  discount_rules.json  discount_code -> basis points
  regions.csv          site -> region_name, site_adjustment_cents
  tax_rules.json       default rate, region overrides, site overrides
  rate_table.csv       (department, category) -> base_multiplier text
  fx_rates.csv         (date, currency) -> basis points, by posted_date
  calendar.csv         posted_date -> period (holes become quality issues)
  thresholds.json      floor, alert threshold, lag limit, required buckets
  policy.json          report_id
"""

from __future__ import annotations

import csv
import io
import json
import random
from datetime import date, timedelta
from pathlib import Path

REGIONS = ["North", "South", "West", "East", "Central"]
SEGMENTS = ["commercial", "public", "nonprofit"]
CURRENCIES = {"USD": 10000, "EUR": 10850, "GBP": 12600, "CAD": 7400, "CHF": 11200, "AUD": 6600}
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
WORDS = ["Aster", "Boreal", "Cascade", "Delta", "Eastfield", "Fairview", "Granite", "Hollow", "Iris", "Juniper",
         "Keystone", "Lakeside", "Meridian", "Northgate", "Orchard", "Pinecrest", "Quarry", "Riverside"]
KINDS = ["Clinic", "Labs", "Care", "Rehab", "Health", "Trust", "Partners", "Center", "Group", "Hospital"]


def _csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ident(rng: random.Random, prefix: str, length: int, used: set[str]) -> str:
    while True:
        value = prefix + "".join(rng.choice(ALPHABET) for _ in range(length))
        if value not in used:
            used.add(value)
            return value


def generate(data_dir: Path, seed: int, subs: dict[str, str]) -> None:
    rng = random.Random(seed)
    for stale in data_dir.iterdir():
        if stale.is_file() and stale.name != "schema.md":
            stale.unlink()
    used: set[str] = set()

    codes = sorted({_ident(rng, "dc-", 4, used) for _ in range(320)})
    discounts = {code: rng.choice([0, 0, -50, -125, -250, -400, 75, 150]) for code in codes}
    _json(data_dir / "discount_rules.json", discounts)

    customers = []
    for _ in range(2500):
        customers.append([_ident(rng, "c", 5, used), f"{rng.choice(WORDS)} {rng.choice(KINDS)}",
                          rng.choices(SEGMENTS, weights=[5, 4, 1])[0], rng.choice(codes)])
    _csv(data_dir / "customers.csv", ["customer_id", "customer_name", "segment", "discount_code"], customers)

    sites = []
    for _ in range(2400):
        sites.append([_ident(rng, "S", 4, used).upper(), rng.choices(REGIONS, weights=[3, 3, 3, 3, 1])[0],
                      rng.choice([0, 0, 50, 125, 250, -75, -175, 300])])
    _csv(data_dir / "regions.csv", ["site", "region_name", "site_adjustment_cents"], sites)

    site_overrides = {row[0]: rng.choice([640, 690, 705, 760, 815, 880]) for row in rng.sample(sites, 900)}
    _json(data_dir / "tax_rules.json", {
        "default_tax_rate_basis_points": rng.choice([700, 725, 750]),
        "region_overrides_basis_points": {name: rng.choice([680, 710, 725, 745, 790]) for name in REGIONS[:4]},
        "site_overrides_basis_points": dict(sorted(site_overrides.items())),
    })

    departments = sorted({_ident(rng, "dept-", 3, used) for _ in range(45)})
    categories = sorted({_ident(rng, "cat-", 3, used) for _ in range(48)})
    rate_rows = []
    for department in departments:
        for category in categories:
            text = rng.choice(["1", "1.0", "1.05", "0.97", "1.080", "1.125", "0.9", "1.0350", "0.955"])
            rate_rows.append([department, category, text])
    _csv(data_dir / "rate_table.csv", ["department", "category", "base_multiplier"], rate_rows)

    first_post = date(2025, 3, 1)
    span = 420
    fx_rows = []
    level = {k: float(v) for k, v in CURRENCIES.items()}
    for offset in range(span + 2):
        day = first_post + timedelta(days=offset)
        for currency in sorted(CURRENCIES):
            if currency != "USD":
                level[currency] *= 1 + rng.uniform(-0.003, 0.003)
            fx_rows.append([day.isoformat(), currency, 10000 if currency == "USD" else round(level[currency])])
    _csv(data_dir / "fx_rates.csv", ["date", "currency", "rate_to_usd_basis_points"], fx_rows)

    calendar_start = date(2022, 1, 1)
    calendar = []
    for offset in range(2200):
        day = calendar_start + timedelta(days=offset)
        if first_post <= day <= first_post + timedelta(days=span) and rng.random() < 0.012:
            continue
        iso = day.isocalendar()
        calendar.append([day.isoformat(), f"{iso.year}-W{iso.week:02d}", "true" if day.weekday() < 5 else "false"])
    _csv(data_dir / "calendar.csv", ["date", "period", "is_business_day"], calendar)

    txns = []
    seen: set[str] = set()
    for _ in range(12000):
        while True:
            txn = f"T{rng.randrange(10**7):07d}"
            if txn not in seen:
                seen.add(txn)
                break
        credit = rng.random() < 0.08
        amount = -rng.randint(100, 4000) if credit else rng.randint(300, 60000)
        basis = 0 if credit else max(0, amount - rng.randint(0, 900))
        posted = first_post + timedelta(days=rng.randint(0, span))
        service = posted - timedelta(days=rng.choices(range(9), weights=[20, 25, 20, 12, 8, 6, 4, 3, 2])[0])
        txns.append([txn, rng.choice(customers)[0], rng.choice(sites)[0], rng.choice(departments),
                     rng.choice(categories), rng.choice(["USD"] * 5 + sorted(CURRENCIES)), amount, basis,
                     rng.randint(1, 12), service.isoformat(), posted.isoformat()])
    _csv(data_dir / "transactions.csv", ["txn_id", "customer_id", "site", "department", "category", "currency",
                                         "amount_cents", "tax_basis_cents", "units", "service_date", "posted_date"], txns)

    _json(data_dir / "thresholds.json", {
        "minimum_net_cents": rng.choice([0, 25, 50]),
        "variance_alert_cents": rng.choice([1500, 2500, 4000]),
        "quality_max_posting_lag_days": rng.choice([3, 4, 5]),
        "required_regions": REGIONS[:4],
        "required_segments": SEGMENTS[:2],
    })
    _json(data_dir / "policy.json", {"report_id": f"{subs['{{FORMAT_TAG}}']}-{subs['{{SEED_HEX}}']}"})
