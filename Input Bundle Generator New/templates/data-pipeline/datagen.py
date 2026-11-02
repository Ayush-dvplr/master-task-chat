"""Seeded input data for the data-pipeline archetype.

Writes eleven interlocking files into environment/data. Every transaction file
depends on every reference file, so deleting any one of them makes the shipped
outputs impossible to reproduce:

  customers.csv        customer -> segment, postal_code (home region for adjustments)
  regions.csv          postal prefix -> canonical region, default currency
  inventory.csv        sku x warehouse stock; a warehouse's postal_code gives the
                       region of every row it ships
  channels.csv         terminal -> channel_group (unknown terminal = malformed row)
  product_catalog.csv  sku -> category
  fx_rates.csv         daily rate per (date, currency); no rate = malformed row
  calendar.csv         date -> fiscal week ("unknown" past its last date)
  sales.csv, refunds.csv, adjustments.jsonl, legacy.txt   the transactions
"""

from __future__ import annotations

import csv
import io
import json
import random
from datetime import date, timedelta
from pathlib import Path

REGIONS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "corporate", "enterprise", "smb"]
CATEGORIES = ["widgets", "gadgets", "kits", "tools", "parts", "supplies", "fixtures", "media"]
GROUPS = ["web", "store", "partner", "legacy", "manual"]
CURRENCIES = {"USD": 1.0, "EUR": 1.09, "GBP": 1.26, "CAD": 0.74, "JPY": 0.0068, "CHF": 1.12}
MANAGERS = ["Nguyen", "Okafor", "Patel", "Rivera", "Smith", "Kowalski", "Haddad", "Ito", "Mensah", "Larsen"]
WORDS = ["Amber", "Basalt", "Cobalt", "Delta", "Ember", "Fjord", "Garnet", "Harbor", "Indigo", "Juniper",
         "Kestrel", "Lumen", "Maple", "Nimbus", "Onyx", "Pioneer", "Quartz", "Ridge", "Summit", "Tundra"]
NOUNS = ["Retail", "Foods", "Studio", "Partners", "Labs", "Supply", "Works", "Traders", "Group", "Collective"]
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

START = date(2019, 1, 1)
DAYS = 2240
CALENDAR_DAYS = DAYS - 18


def _code(rng: random.Random, prefix: str, length: int, used: set[str]) -> str:
    while True:
        value = prefix + "".join(rng.choice(ALPHABET) for _ in range(length))
        if value not in used:
            used.add(value)
            return value


def _csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _messy(rng: random.Random, value: str) -> str:
    roll = rng.random()
    if roll < 0.06:
        return f" {value} "
    if roll < 0.10:
        return value.upper()
    if roll < 0.13:
        return value.title()
    return value


def _money(rng: random.Random, low: float, high: float) -> str:
    return f"{rng.uniform(low, high):.2f}"


def generate(data_dir: Path, seed: int, subs: dict[str, str]) -> None:
    rng = random.Random(seed)
    for stale in data_dir.iterdir():
        if stale.is_file() and stale.name != "schema.md":
            stale.unlink()

    prefixes = rng.sample(range(1000, 9999), 2300)
    region_rows = []
    prefix_region: dict[str, str] = {}
    for index, prefix in enumerate(sorted(prefixes)):
        region = REGIONS[index * len(REGIONS) // len(prefixes)] if rng.random() < 0.7 else rng.choice(REGIONS)
        default_ccy = "USD" if rng.random() < 0.8 else rng.choice(["EUR", "GBP", "CAD", "CHF"])
        prefix_region[str(prefix)] = region
        region_rows.append([str(prefix), _messy(rng, region), rng.choice(MANAGERS), default_ccy])
    _csv(data_dir / "regions.csv", ["postal_prefix", "region", "manager", "default_currency"], region_rows)
    prefix_pool = sorted(prefix_region)

    def postal() -> str:
        return f"{rng.choice(prefix_pool)}-{rng.randrange(100):02d}"

    used: set[str] = set()
    customers = []
    for _ in range(2400):
        cid = _code(rng, "CU-", 5, used)
        customers.append([cid, f"{rng.choice(WORDS)} {rng.choice(NOUNS)}", _messy(rng, rng.choice(SEGMENTS)), postal()])
    _csv(data_dir / "customers.csv", ["customer_id", "name", "segment", "postal_code"], customers)
    customer_ids = [row[0] for row in customers]

    skus = []
    for _ in range(2100):
        sku = _code(rng, "SK-", 6, used)
        skus.append([sku, f"{rng.choice(WORDS)} {rng.choice(['Widget', 'Gadget', 'Kit', 'Tool', 'Part'])}",
                     _messy(rng, rng.choice(CATEGORIES)), _money(rng, 0.5, 80), rng.choice(["true", "true", "false"])])
    _csv(data_dir / "product_catalog.csv", ["sku", "name", "category", "unit_cost_usd", "active"], skus)
    sku_ids = [row[0] for row in skus]

    warehouses = {_code(rng, "WH-", 3, used): postal() for _ in range(70)}
    warehouse_ids = sorted(warehouses)
    inventory = []
    for sku in sku_ids:
        for wh in rng.sample(warehouse_ids, rng.randint(1, 4)):
            inventory.append([sku, wh, warehouses[wh], rng.randint(0, 500), rng.randint(0, 60)])
    rng.shuffle(inventory)
    _csv(data_dir / "inventory.csv", ["sku", "warehouse", "postal_code", "on_hand", "reorder_point"], inventory)
    stocked: dict[str, list[str]] = {}
    for sku, wh, *_ in inventory:
        stocked.setdefault(sku, []).append(wh)

    terminals = []
    for _ in range(2050):
        terminals.append([_code(rng, "T-", 5, used), _messy(rng, rng.choice(GROUPS)), rng.choice(["online", "kiosk", "desk", "phone"])])
    _csv(data_dir / "channels.csv", ["terminal", "channel_group", "device"], terminals)
    terminal_ids = [row[0] for row in terminals]

    days = [START + timedelta(days=i) for i in range(DAYS)]
    fx_rows = []
    level = dict(CURRENCIES)
    for day in days:
        for code in sorted(CURRENCIES):
            if code != "USD":
                level[code] = max(level[code] * (1 + rng.uniform(-0.004, 0.004)), 0.0001)
            rate = "1.000000" if code == "USD" else f"{level[code]:.6f}"
            fx_rows.append([day.isoformat(), code, rate])
    _csv(data_dir / "fx_rates.csv", ["date", "currency", "usd_rate"], fx_rows)

    calendar = []
    for day in days[:CALENDAR_DAYS]:
        iso = day.isocalendar()
        holiday = "true" if (day.month, day.day) in {(1, 1), (7, 4), (12, 25), (11, 28)} or rng.random() < 0.01 else "false"
        calendar.append([day.isoformat(), f"{iso.year}-W{iso.week:02d}", holiday])
    _csv(data_dir / "calendar.csv", ["date", "fiscal_week", "is_holiday"], calendar)

    event_ids: set[str] = set()

    def event(prefix: str) -> str:
        while True:
            value = f"{prefix}-{rng.randrange(10**7):07d}"
            if value not in event_ids:
                event_ids.add(value)
                return value

    def transaction_date() -> str:
        if rng.random() < 0.004:
            return f"{rng.randint(2019, 2024)}-13-{rng.randint(1, 28):02d}"
        return rng.choice(days).isoformat()

    def customer() -> str:
        return "CU-ZZZZZ" if rng.random() < 0.004 else rng.choice(customer_ids)

    def sku_and_warehouse() -> tuple[str, str]:
        sku = "SK-000000" if rng.random() < 0.004 else rng.choice(sku_ids)
        wh = rng.choice(stocked.get(sku, warehouse_ids))
        if rng.random() < 0.004:
            wh = "WH-999"
        return sku, wh

    def terminal() -> str:
        return "T-00000" if rng.random() < 0.004 else rng.choice(terminal_ids)

    def currency() -> str:
        roll = rng.random()
        if roll < 0.03:
            return ""
        value = rng.choice(["USD", "USD", "USD", "EUR", "GBP", "CAD", "JPY", "CHF"])
        return value.lower() if roll < 0.08 else value

    def quantity() -> str:
        return rng.choice(["two", "1.5", ""]) if rng.random() < 0.004 else str(rng.randint(1, 12))

    sales = []
    for _ in range(8200):
        sku, wh = sku_and_warehouse()
        cur = currency()
        price = _money(rng, 1, 250) if cur.upper() != "JPY" else str(rng.randint(150, 40000))
        sales.append([event("S"), transaction_date(), customer(), sku, wh, quantity(), price, cur, terminal()])
    _csv(data_dir / "sales.csv", ["event_id", "date", "customer_id", "sku", "warehouse", "quantity", "unit_price", "currency", "terminal"], sales)

    refunds = []
    for _ in range(2600):
        sku, wh = sku_and_warehouse()
        cur = currency()
        amount = _money(rng, 1, 400) if cur.upper() != "JPY" else str(rng.randint(150, 60000))
        refunds.append([event("R"), transaction_date(), customer(), sku, wh, quantity(), amount, cur, terminal(),
                        rng.choice(["customer_return", "damaged", "late_delivery", "", "wrong_item"])])
    _csv(data_dir / "refunds.csv", ["event_id", "date", "customer_id", "sku", "warehouse", "quantity", "refund_amount", "currency", "terminal", "reason"], refunds)

    adjustment_lines = []
    for _ in range(2300):
        kind = rng.choice(["fee", "credit"])
        cents = rng.randint(50, 9000)
        row = {
            "event_id": event("A"),
            "date": transaction_date(),
            "customer_id": customer(),
            "sku": "SK-000000" if rng.random() < 0.004 else rng.choice(sku_ids),
            "kind": _messy(rng, kind),
            "amount_cents": cents if kind == "fee" else -cents,
            "currency": currency(),
            "note": rng.choice(["rush handling", "loyalty credit", "manual surcharge", "", "goodwill"]),
        }
        if rng.random() < 0.004:
            row["amount_cents"] = "n/a"
        adjustment_lines.append(json.dumps(row, separators=(",", ":")))
    (data_dir / "adjustments.jsonl").write_text("\n".join(adjustment_lines) + "\n", encoding="utf-8")

    legacy_lines = ["# event_id|date|customer_id|sku|warehouse|kind|quantity|amount|currency|terminal|note"]
    for index in range(2500):
        if index % 250 == 0:
            legacy_lines.append(f"# export batch {index // 250 + 1}")
        if index % 400 == 7:
            legacy_lines.append("")
        sku, wh = sku_and_warehouse()
        cur = currency()
        kind = rng.choice(["sale", "sale", "refund", "fee", "credit"])
        amount = _money(rng, 0.5, 300) if cur.upper() != "JPY" else str(rng.randint(100, 50000))
        legacy_lines.append("|".join([
            event("L"), transaction_date(), customer(), sku, wh, _messy(rng, kind), quantity(), amount, cur,
            terminal(), rng.choice(["legacy kiosk", "gift wrap", "legacy return", ""]),
        ]))
    (data_dir / "legacy.txt").write_text("\n".join(legacy_lines) + "\n", encoding="utf-8")
