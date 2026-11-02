#!/usr/bin/env python3
"""derive_report.py: the reconciliation report described in /app/data/schema.md.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

TEN_K = Decimal(10000)


def cents(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_HALF_UP))


def rows(folder: Path, name: str) -> list[dict[str, str]]:
    with open(folder / name, newline="", encoding="utf-8") as handle:
        return [dict(r) for r in csv.DictReader(handle)]


def doc(folder: Path, name: str):
    return json.loads((folder / name).read_text(encoding="utf-8"))


@dataclass
class Line:
    txn_id: str
    customer: str
    site: str
    region: str
    segment: str
    department: str
    category: str
    units: int
    gross: int
    tax: int
    net: int
    lag: int
    period: str
    in_calendar: bool


class Rules:
    def __init__(self, folder: Path) -> None:
        self.policy = doc(folder, "policy.json")
        self.limits = doc(folder, "thresholds.json")
        taxes = doc(folder, "tax_rules.json")
        self.tax_default = int(taxes["default_tax_rate_basis_points"])
        self.tax_by_region = {k: int(v) for k, v in taxes["region_overrides_basis_points"].items()}
        self.tax_by_site = {k: int(v) for k, v in taxes["site_overrides_basis_points"].items()}
        self.discount = {k: int(v) for k, v in doc(folder, "discount_rules.json").items()}
        self.people = {r["customer_id"]: r for r in rows(folder, "customers.csv")}
        self.sites = {r["site"]: r for r in rows(folder, "regions.csv")}
        self.multiplier_text: dict[str, dict[str, str]] = defaultdict(dict)
        for r in rows(folder, "rate_table.csv"):
            self.multiplier_text[r["department"]][r["category"]] = r["base_multiplier"]
        self.fx = {(r["date"], r["currency"]): Decimal(r["rate_to_usd_basis_points"]) for r in rows(folder, "fx_rates.csv")}
        self.periods = {r["date"]: r["period"] for r in rows(folder, "calendar.csv")}

    def tax_rate(self, site: str, region: str) -> int:
        if site in self.tax_by_site:
            return self.tax_by_site[site]
        return self.tax_by_region.get(region, self.tax_default)

    def price(self, raw: dict[str, str]) -> Line:
        person = self.people[raw["customer_id"]]
        place = self.sites[raw["site"]]
        rate = self.fx[(raw["posted_date"], raw["currency"])]
        gross = cents(Decimal(int(raw["amount_cents"])) * rate / TEN_K)
        basis = cents(Decimal(int(raw["tax_basis_cents"])) * rate / TEN_K)
        tax = cents(basis * Decimal(self.tax_rate(raw["site"], place["region_name"])) / TEN_K)
        after_discount = cents((gross + tax) * (TEN_K + self.discount[person["discount_code"]]) / TEN_K)
        scaled = cents(after_discount * Decimal(self.multiplier_text[raw["department"]][raw["category"]]))
        net = max(int(self.limits["minimum_net_cents"]), scaled + int(place["site_adjustment_cents"]))
        posted = raw["posted_date"]
        return Line(
            txn_id=raw["txn_id"], customer=raw["customer_id"], site=raw["site"], region=place["region_name"],
            segment=person["segment"], department=raw["department"], category=raw["category"],
            units=int(raw["units"]), gross=gross, tax=tax, net=net,
            lag=(date.fromisoformat(posted) - date.fromisoformat(raw["service_date"])).days,
            period=self.periods.get(posted, "unknown"), in_calendar=posted in self.periods,
        )


def ordered(counter) -> dict:
    return {key: counter[key] for key in sorted(counter)}


def rollup(label: str, lines: list[Line], alert_at: int) -> dict:
    gross = sum(x.gross for x in lines)
    net = sum(x.net for x in lines)
    by_dept: Counter = Counter()
    by_cat: Counter = Counter()
    for x in lines:
        by_dept[x.department] += x.net
        by_cat[x.category] += x.units
    return {
        "name": label, "transaction_count": len(lines), "gross_cents": gross,
        "tax_cents": sum(x.tax for x in lines), "adjusted_net_cents": net,
        "department_totals": ordered(by_dept), "category_units": ordered(by_cat),
        "customers": sorted({x.customer for x in lines}),
        "alerts": [{"name": label, "delta_cents": net - gross}] if abs(net - gross) >= alert_at else [],
    }


def build(folder: Path) -> dict[str, dict]:
    rules = Rules(folder)
    ledger = rows(folder, "transactions.csv")
    lines = [rules.price(raw) for raw in ledger]
    alert_at = int(rules.limits["variance_alert_cents"])
    lag_limit = int(rules.limits["quality_max_posting_lag_days"])

    site_net: Counter = Counter()
    site_gross: Counter = Counter()
    dept: Counter = Counter()
    units: Counter = Counter()
    period: Counter = Counter()
    for x in lines:
        site_net[x.site] += x.net
        site_gross[x.site] += x.gross
        dept[x.department] += x.net
        units[x.category] += x.units
        period[x.period] += x.net
    top = min(lines, key=lambda x: (-x.gross, x.txn_id)) if lines else None
    issues = []
    for x in lines:
        if x.lag > lag_limit:
            issues.append(f"{x.txn_id}: posting lag {x.lag} days")
        if not x.in_calendar:
            issues.append(f"{x.txn_id}: posted date missing from calendar")

    report = {
        "summary.json": {
            "report_id": rules.policy["report_id"],
            "transaction_count": len(lines),
            "gross_cents": sum(x.gross for x in lines),
            "tax_cents": sum(x.tax for x in lines),
            "adjusted_net_cents": sum(x.net for x in lines),
            "department_totals": ordered(dept),
            "site_totals": ordered(site_net),
            "category_units": ordered(units),
            "period_totals": ordered(period),
            "largest_transaction": {"txn_id": top.txn_id if top else None, "amount_cents": top.gross if top else 0},
            "posting_lag_days": {
                "max": max((x.lag for x in lines), default=0),
                "average": round(sum(x.lag for x in lines) / len(lines), 2) if lines else 0.0,
            },
            "alerts": [{"site": s, "delta_cents": site_net[s] - site_gross[s]}
                       for s in sorted(site_net) if abs(site_net[s] - site_gross[s]) >= alert_at],
        },
        "policy_audit.json": {
            "report_id": rules.policy["report_id"],
            "default_tax_basis_points": rules.tax_default,
            "tax_regions": ordered(rules.tax_by_region),
            "tax_sites": ordered(rules.tax_by_site),
            "discount_codes": ordered(rules.discount),
            "department_multipliers": {d: ordered(rules.multiplier_text[d]) for d in sorted(rules.multiplier_text)},
            "minimum_net_cents": int(rules.limits["minimum_net_cents"]),
            "variance_alert_cents": alert_at,
        },
        "data_quality.json": {
            "input_file_count": sum(1 for p in folder.iterdir() if p.is_file()),
            "transaction_count": len(lines),
            "customer_count": len(rules.people),
            "region_count": len(rules.sites),
            "quality_issue_count": len(issues),
            "quality_issues": sorted(issues),
        },
    }
    for name in rules.limits["required_regions"]:
        report[f"region_{name}.json"] = rollup(name, [x for x in lines if x.region == name], alert_at)
    for name in rules.limits["required_segments"]:
        report[f"segment_{name}.json"] = rollup(name, [x for x in lines if x.segment == name], alert_at)
    return report


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    out = Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for filename, payload in sorted(build(Path(argv[1])).items()):
        (out / filename).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
