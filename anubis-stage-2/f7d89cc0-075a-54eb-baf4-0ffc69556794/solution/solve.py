#!/usr/bin/env python3
"""Reference reconciliation program for the Meridian Interstate Grid
Compact monthly settlement.

Usage:
    python3 solve.py DATA_DIR OUT_DIR
    python3 solve.py --session OUT_DIR

The program implements the contract in `DATA_DIR/schema.md`. It uses only
the Python standard library and does not initiate network activity of its
own. It reads only from DATA_DIR and writes only under OUT_DIR.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path


PERIOD_FIRST = date(2025, 10, 1)
PERIOD_LAST = date(2025, 10, 31)
DAYS = 31
DST_DAY = date(2025, 10, 26)


def _hu(x) -> int:
    """Half-up to an integer on an exact value (x.5 goes toward +infinity)."""
    return math.floor(Fraction(x) + Fraction(1, 2))


def _register_to_th(s: str) -> int:
    s = s.strip()
    if "." not in s:
        return int(s) * 1000
    whole, frac = s.split(".")
    frac = (frac + "000")[:3]
    return int(whole) * 1000 + int(frac)


def _max_register_th(meter_class: str) -> int:
    return {"mech5": 99_999_999,
            "hybrid6": 999_999_999,
            "smart7": 9_999_999_999}[meter_class]


def _premise_num(pc: str) -> int:
    m = re.match(r"P(\d+)", pc)
    return int(m.group(1)) if m else 0


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses for the domain objects
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Customer:
    customer_id: str
    name: str
    rate_class: str
    premise_code: str
    meter_class: str
    billing_currency: str
    grandfather_flag: bool
    grandfather_date: str
    grandfather_expires_on: str
    solar_enrolled: bool
    fiscal_group: str

    @property
    def gf_start_date(self) -> date | None:
        if not self.grandfather_flag or not self.grandfather_date:
            return None
        return date.fromisoformat(self.grandfather_date)

    @property
    def gf_end_date(self) -> date | None:
        if not self.grandfather_flag or not self.grandfather_expires_on:
            return None
        return date.fromisoformat(self.grandfather_expires_on)


@dataclass
class Premise:
    premise_code: str
    street: str
    city: str
    region: str
    latitude: str
    longitude: str
    meter_channel_count: int
    altitude_bracket: str


@dataclass
class TariffRow:
    schedule_id: str
    rate_class: str
    tou_period: str
    effective_from: date
    effective_until: date
    energy_rate: int
    demand_rate: int
    customer_charge: int
    order_of_precedence: int


@dataclass
class RegulatorOrder:
    order_id: str
    issued_on: date
    effective_on: date
    supersedes_schedule_id: str
    new_schedule_id: str
    period_start: date
    period_end: date
    scope: str
    grandfather_immune: bool


@dataclass
class Ticket:
    ticket_id: str
    customer_id: str
    event_type: str
    effective_date: date
    new_rate_class: str


@dataclass
class Read:
    read_id: str
    customer_id: str
    channel: int
    timestamp: datetime
    register_th: int


@dataclass
class Interval:
    customer_id: str
    channel: int
    start_str: str
    kw: Decimal
    civil_date: date


@dataclass
class Bill:
    customer: Customer
    energy_kwh_th: int = 0
    energy_mrcc: int = 0
    demand_mrcc: int = 0
    customer_charge_mrcc: int = 0
    fac_mrcc: int = 0
    nmb_carried_kwh_th: int = 0
    nmb_avoided_cost_mrcc: int = 0
    nmb_forfeited_kwh_th: int = 0
    retro_total_mrcc: int = 0
    retro_lines: list[dict] = field(default_factory=list)
    bill_mrcc: int = 0
    bill_ftuc: int = 0
    grandfather_line: dict | None = None
    migration_line: dict | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────────────────────────────────────


class Extract:
    """Everything read out of DATA_DIR."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.customers: list[Customer] = self._load_customers()
        self.premises: dict[str, Premise] = self._load_premises()
        self.tariff: list[TariffRow] = self._load_tariff()
        self.fac: dict[str, int] = self._load_fac()
        self.holidays: list[dict] = self._load_json("holiday_calendar.json")
        self.dst: dict = self._load_json("dst_calendar.json")
        self.currency: dict = self._load_json("currency_rates.json")
        self.orders: list[RegulatorOrder] = self._load_orders()
        self.nmb: dict[str, int] = self._load_nmb()
        self.tickets: list[Ticket] = self._load_tickets()
        self.reads: list[Read] = self._load_reads()
        self.intervals: list[Interval] = self._load_intervals()
        self.holidays_off: set[date] = {date.fromisoformat(h["date"])
                                       for h in self.holidays
                                       if h["tou_treatment"] == "off"}
        self.holidays_weekend: set[date] = {date.fromisoformat(h["date"])
                                            for h in self.holidays
                                            if h["tou_treatment"] == "weekend"}

    def _load_json(self, name: str):
        with (self.data_dir / name).open(encoding="utf-8") as fh:
            return json.load(fh)

    def _csv_rows(self, name: str) -> list[dict]:
        with (self.data_dir / name).open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def _load_customers(self) -> list[Customer]:
        out = []
        for r in self._csv_rows("customers.csv"):
            out.append(Customer(
                customer_id=r["customer_id"], name=r["name"],
                rate_class=r["rate_class"], premise_code=r["premise_code"],
                meter_class=r["meter_class"], billing_currency=r["billing_currency"],
                grandfather_flag=r["grandfather_flag"].strip().lower() == "true",
                grandfather_date=r["grandfather_date"],
                grandfather_expires_on=r["grandfather_expires_on"],
                solar_enrolled=r["solar_enrolled"].strip().lower() == "true",
                fiscal_group=r["fiscal_group"]))
        return out

    def _load_premises(self) -> dict[str, Premise]:
        out: dict[str, Premise] = {}
        for r in self._csv_rows("premises.csv"):
            p = Premise(premise_code=r["premise_code"], street=r["street"],
                        city=r["city"], region=r["region"],
                        latitude=r["latitude"], longitude=r["longitude"],
                        meter_channel_count=int(r["meter_channel_count"]),
                        altitude_bracket=r["altitude_bracket"])
            out[p.premise_code] = p
        return out

    def _load_tariff(self) -> list[TariffRow]:
        out = []
        for r in self._csv_rows("tariff_schedule.csv"):
            out.append(TariffRow(
                schedule_id=r["schedule_id"],
                rate_class=r["rate_class"],
                tou_period=r["tou_period"],
                effective_from=date.fromisoformat(r["effective_from"]),
                effective_until=(date.fromisoformat(r["effective_until"])
                                 if r["effective_until"] else date(9999, 12, 31)),
                energy_rate=int(r["energy_rate_mrcc_per_kwh"]),
                demand_rate=int(r["demand_rate_mrcc_per_kw"]),
                customer_charge=int(r["customer_charge_mrcc"]),
                order_of_precedence=int(r["order_of_precedence"])))
        return out

    def _load_fac(self) -> dict[str, int]:
        out = {}
        for r in self._csv_rows("fac_index.csv"):
            out[r["month"]] = int(r["fac_mrcc_per_kwh"])
        return out

    def _load_orders(self) -> list[RegulatorOrder]:
        out = []
        for r in self._load_json("regulator_orders.json"):
            out.append(RegulatorOrder(
                order_id=r["order_id"],
                issued_on=date.fromisoformat(r["issued_on"]),
                effective_on=date.fromisoformat(r["effective_on"]),
                supersedes_schedule_id=r["supersedes_schedule_id"],
                new_schedule_id=r["new_schedule_id"],
                period_start=date.fromisoformat(r["period_start"]),
                period_end=date.fromisoformat(r["period_end"]),
                scope=r["scope"],
                grandfather_immune=bool(r["grandfather_immune"])))
        return out

    def _load_nmb(self) -> dict[str, int]:
        out = {}
        for r in self._csv_rows("net_metering_bank.csv"):
            out[r["customer_id"]] = int(r["balance_kwh_start_of_period"])
        return out

    def _load_tickets(self) -> list[Ticket]:
        out = []
        for r in self._load_json("service_tickets.json"):
            out.append(Ticket(
                ticket_id=r["ticket_id"],
                customer_id=r["customer_id"],
                event_type=r["event_type"],
                effective_date=date.fromisoformat(r["effective_date"]),
                new_rate_class=r.get("new_rate_class", "")))
        return out

    def _load_reads(self) -> list[Read]:
        out = []
        for r in self._csv_rows("meter_reads.csv"):
            out.append(Read(
                read_id=r["read_id"],
                customer_id=r["customer_id"],
                channel=int(r["channel"]),
                timestamp=datetime.fromisoformat(r["read_timestamp"]),
                register_th=_register_to_th(r["register_reading_kwh"])))
        return out

    def _load_intervals(self) -> list[Interval]:
        out = []
        for r in self._csv_rows("demand_intervals.csv"):
            iv_start = r["interval_start"]
            civ_date_str = iv_start.split("T")[0]
            out.append(Interval(
                customer_id=r["customer_id"],
                channel=int(r["channel"]),
                start_str=iv_start,
                kw=Decimal(r["demand_kw"]),
                civil_date=date.fromisoformat(civ_date_str)))
        return out

    def rate_row(self, rate_class: str, tou_period: str, on_date: date,
                 ceiling: int | None) -> TariffRow | None:
        best: TariffRow | None = None
        for row in self.tariff:
            if row.rate_class != rate_class or row.tou_period != tou_period:
                continue
            if not (row.effective_from <= on_date <= row.effective_until):
                continue
            if ceiling is not None and row.order_of_precedence > ceiling:
                continue
            if best is None or row.order_of_precedence > best.order_of_precedence:
                best = row
        return best

    def currency_at(self, on_date: date) -> int:
        rates = sorted(self.currency["rates"],
                       key=lambda r: r["date"])
        best = None
        for r in rates:
            if date.fromisoformat(r["date"]) <= on_date:
                best = int(r["mrc_per_ftu"])
        if best is None:
            best = int(rates[0]["mrc_per_ftu"])
        return best


# ─────────────────────────────────────────────────────────────────────────────
# The reconciler
# ─────────────────────────────────────────────────────────────────────────────

LABEL_ORDER = ("peak", "shoulder", "night", "weekend")
REPEAT_HOUR = datetime.combine(DST_DAY, time(1, 0))


@dataclass
class HourShare:
    """A slice of one civil hour: which hour, whether it is the second
    occurrence of the fall-back hour, and how many seconds of it."""
    day: date
    hour: int
    repeat: bool
    seconds: int


def civil_hours(start: datetime, end: datetime) -> list[HourShare]:
    """Walk [start, end) hour by hour in civil time. The fall-back 01:00 hour
    happens twice, so any overlap with it is counted twice (schema §4)."""
    out: list[HourShare] = []
    cursor = start
    while cursor < end:
        hour_top = cursor.replace(minute=0, second=0, microsecond=0)
        nxt = min(hour_top + timedelta(hours=1), end)
        secs = int((nxt - cursor).total_seconds())
        out.append(HourShare(hour_top.date(), hour_top.hour, False, secs))
        if hour_top == REPEAT_HOUR:
            out.append(HourShare(hour_top.date(), hour_top.hour, True, secs))
        cursor = nxt
    return out


@dataclass
class ChannelResult:
    per_hour: dict[tuple[date, int, bool], Fraction]
    missing_start: bool
    missing_end: bool
    high_variance: int
    duplicates: int


class Reconciler:
    """Compute the nine JSON reports from a loaded Extract."""

    RES_WINDOWS = {"peak": [(16, 21)],
                   "shoulder": [(7, 16), (21, 23)],
                   "night": [(23, 24), (0, 7)]}
    COM_WINDOWS = {"peak": [(12, 18)],
                   "shoulder": [(8, 12), (18, 22)],
                   "night": [(22, 24), (0, 8)]}
    IND_WINDOWS = {"peak": [(10, 20)],
                   "shoulder": [(6, 10), (20, 23)],
                   "night": [(23, 24), (0, 6)]}

    def __init__(self, extract: Extract) -> None:
        self.ex = extract

    # ─── calendar helpers ──────────────────────────────────────────────

    def _windows_for(self, rate_class: str) -> dict[str, list[tuple[int, int]]]:
        return {"RES": self.RES_WINDOWS, "COM": self.COM_WINDOWS,
                "IND": self.IND_WINDOWS}[rate_class]

    def _hour_label(self, rate_class: str, share: HourShare) -> str:
        d = share.day
        if d in self.ex.holidays_off or d in self.ex.holidays_weekend:
            return "weekend"
        if share.repeat:
            return "weekend" if rate_class == "COM" else "night"
        if d.weekday() >= 5:
            return "weekend"
        for label, ranges in self._windows_for(rate_class).items():
            if any(a <= share.hour < b for (a, b) in ranges):
                return label
        return "night"

    def _service_window(self, customer: Customer) -> tuple[date, date]:
        start, end = PERIOD_FIRST, PERIOD_LAST
        for t in self.ex.tickets:
            if t.customer_id != customer.customer_id:
                continue
            if t.event_type == "move_in" and t.effective_date > start:
                start = t.effective_date
            elif t.event_type == "move_out" and t.effective_date < end:
                end = t.effective_date
        return start, end

    def _migration(self, customer: Customer) -> Ticket | None:
        for t in self.ex.tickets:
            if t.customer_id == customer.customer_id and t.event_type == "rate_class_migration":
                return t
        return None

    # ─── consumption ───────────────────────────────────────────────────

    @staticmethod
    def _advance(prev: int, cur: int, max_reg: int) -> int:
        if cur >= prev:
            return cur - prev
        return (max_reg + 1) - prev + cur

    def _clean_channel(self, customer: Customer, channel: int,
                       max_reg: int) -> tuple[list[Read], int]:
        """Sort a channel's reads and resolve duplicate timestamps (§15.3):
        keep the read that moved furthest forward from its predecessor."""
        reads = sorted((r for r in self.ex.reads
                        if r.customer_id == customer.customer_id and r.channel == channel),
                       key=lambda r: r.timestamp)
        cleaned: list[Read] = []
        dropped = 0
        i = 0
        while i < len(reads):
            j = i
            while j + 1 < len(reads) and reads[j + 1].timestamp == reads[i].timestamp:
                j += 1
            group = reads[i:j + 1]
            dropped += len(group) - 1
            if cleaned:
                base = cleaned[-1].register_th
                best = max(group, key=lambda r: self._advance(base, r.register_th, max_reg))
            else:
                best = max(group, key=lambda r: r.register_th)
            cleaned.append(best)
            i = j + 1
        return cleaned, dropped

    def _channel_usage(self, customer: Customer, channel: int, service_start: date,
                       service_end: date) -> ChannelResult:
        max_reg = _max_register_th(customer.meter_class)
        reads, dropped = self._clean_channel(customer, channel, max_reg)
        per_hour: dict[tuple[date, int, bool], Fraction] = {}

        def book(shares: list[HourShare], per_second: Fraction) -> None:
            for sh in shares:
                if service_start <= sh.day <= service_end:
                    key = (sh.day, sh.hour, sh.repeat)
                    per_hour[key] = per_hour.get(key, Fraction(0)) + per_second * sh.seconds

        rates: list[Fraction] = []
        for earlier, later in zip(reads, reads[1:]):
            shares = civil_hours(earlier.timestamp, later.timestamp)
            span = sum(sh.seconds for sh in shares)
            if span == 0:
                continue
            rate = Fraction(self._advance(earlier.register_th, later.register_th, max_reg), span)
            rates.append(rate)
            book(shares, rate)

        no_start = all(r.timestamp.date() > service_start for r in reads)
        no_end = all(r.timestamp.date() < service_end for r in reads)
        if rates:
            # §15.4: extend the nearest gap's rate out to the service boundary.
            opening = datetime.combine(service_start, time(0, 0))
            closing = datetime.combine(service_end + timedelta(days=1), time(0, 0))
            if no_start and opening < reads[0].timestamp:
                book(civil_hours(opening, reads[0].timestamp), rates[0])
            if no_end and reads[-1].timestamp < closing:
                book(civil_hours(reads[-1].timestamp, closing), rates[-1])

        spikes = 0
        if rates:
            ranked = sorted(rates)
            mid = len(ranked) // 2
            median = ranked[mid] if len(ranked) % 2 else (ranked[mid - 1] + ranked[mid]) / 2
            spikes = len([r for r in rates if r > median * 20])
        return ChannelResult(per_hour, no_start, no_end, spikes, dropped)

    # ─── billing ───────────────────────────────────────────────────────

    def _schedule_axis(self, customer: Customer, d: date,
                       freeze_ends: date | None) -> tuple[date, int | None]:
        """Which schedule date (and precedence ceiling) prices day d."""
        if customer.grandfather_flag and customer.gf_start_date is not None:
            if freeze_ends is None or d < freeze_ends:
                return customer.gf_start_date, 10
        return d, None

    def _class_on(self, customer: Customer, migration: Ticket | None, d: date) -> str:
        if migration is not None and d >= migration.effective_date:
            return migration.new_rate_class
        return customer.rate_class

    def _bill_customer(self, customer: Customer) -> tuple[Bill, dict]:
        bill = Bill(customer=customer)
        service_start, service_end = self._service_window(customer)
        migration = self._migration(customer)
        freeze_ends = customer.gf_end_date if customer.grandfather_flag else None
        if customer.grandfather_flag and migration is not None:
            if freeze_ends is None or migration.effective_date < freeze_ends:
                freeze_ends = migration.effective_date

        usage: dict[tuple[date, int, bool], Fraction] = {}
        flags = {"start": False, "end": False, "spikes": 0, "dups": 0}
        premise = self.ex.premises[customer.premise_code]
        for channel in range(1, premise.meter_channel_count + 1):
            res = self._channel_usage(customer, channel, service_start, service_end)
            for key, q in res.per_hour.items():
                usage[key] = usage.get(key, Fraction(0)) + q
            flags["start"] |= res.missing_start
            flags["end"] |= res.missing_end
            flags["spikes"] += res.high_variance
            flags["dups"] += res.duplicates

        label_kwh = {lab: Fraction(0) for lab in LABEL_ORDER}
        label_cost = {lab: Fraction(0) for lab in LABEL_ORDER}  # kWh-thousandths x rate
        for (d, hour, repeat), q in usage.items():
            rc = self._class_on(customer, migration, d)
            label = self._hour_label(rc, HourShare(d, hour, repeat, 0))
            on, ceiling = self._schedule_axis(customer, d, freeze_ends)
            row = self.ex.rate_row(rc, label, on, ceiling)
            label_kwh[label] += q
            if row is not None:
                label_cost[label] += q * row.energy_rate
        before_bank = dict(label_kwh)
        bill.energy_kwh_th = _hu(sum(label_kwh.values()))

        bank = Fraction(0)
        if customer.solar_enrolled:
            bank = Fraction(max(0, self.ex.nmb.get(customer.customer_id, 0)))
        for label in LABEL_ORDER:
            if bank == 0 or label_kwh[label] == 0:
                continue
            drawn = min(bank, label_kwh[label])
            keep = (label_kwh[label] - drawn) / label_kwh[label]
            label_cost[label] *= keep
            label_kwh[label] -= drawn
            bank -= drawn
        bill.energy_mrcc = sum(_hu(label_cost[lab] / 1000) for lab in LABEL_ORDER)
        chargeable = sum(label_kwh.values())
        bill.fac_mrcc = _hu(chargeable * self.ex.fac.get("2025-10", 0) / 1000)

        if customer.solar_enrolled and bank > 0:
            if self._class_on(customer, migration, PERIOD_LAST) == "RES":
                bill.nmb_avoided_cost_mrcc = _hu(bank * 4 / 1000)
            else:
                bill.nmb_forfeited_kwh_th = _hu(bank)
        bill.nmb_carried_kwh_th = 0

        bill.customer_charge_mrcc = self._customer_charge(
            customer, service_start, service_end, migration, freeze_ends)

        ddc, ddc_when = self._pick_ddc(customer, service_start, service_end)
        if ddc is not None:
            ddc_day = date.fromisoformat(ddc_when[:10])
            on, ceiling = self._schedule_axis(customer, ddc_day, freeze_ends)
            row = self.ex.rate_row(self._class_on(customer, migration, ddc_day), "*", on, ceiling)
            if row is not None:
                bill.demand_mrcc = _hu(Fraction(ddc) * row.demand_rate)

        retro_ftuc = 0
        for order in self.ex.orders:
            if order.scope != "retroactive":
                continue
            old_def = next((r for r in self.ex.tariff if r.schedule_id == order.supersedes_schedule_id), None)
            new_def = next((r for r in self.ex.tariff if r.schedule_id == order.new_schedule_id), None)
            if old_def is None or new_def is None or customer.rate_class != old_def.rate_class:
                continue
            if customer.grandfather_flag and not order.grandfather_immune:
                continue
            delta = self._retro_delta(customer, order, before_bank, ddc)
            if delta != 0:
                bill.retro_lines.append({"adjustment_mrcc": delta,
                                         "customer_id": customer.customer_id,
                                         "order_id": order.order_id})
                bill.retro_total_mrcc += delta
                retro_ftuc += _hu(Fraction(delta * 100, self.ex.currency_at(order.period_start)))

        gross = (bill.energy_mrcc + bill.demand_mrcc + bill.customer_charge_mrcc
                 + bill.fac_mrcc + bill.retro_total_mrcc - bill.nmb_avoided_cost_mrcc)
        if customer.billing_currency == "FTU":
            current = gross - bill.retro_total_mrcc
            bill.bill_ftuc = _hu(Fraction(current * 100, self.ex.currency_at(PERIOD_FIRST))) + retro_ftuc
            bill.bill_mrcc = 0
        else:
            bill.bill_mrcc = gross
            bill.bill_ftuc = 0

        if customer.grandfather_flag and customer.gf_start_date is not None:
            split = None
            if freeze_ends and PERIOD_FIRST < freeze_ends <= PERIOD_LAST:
                split = freeze_ends.isoformat()
            bill.grandfather_line = {
                "customer_id": customer.customer_id,
                "expires_on": customer.grandfather_expires_on,
                "grandfather_date": customer.grandfather_date,
                "prorata_split_at": split,
            }
        if migration is not None:
            bill.migration_line = {
                "customer_id": customer.customer_id,
                "from_class": customer.rate_class,
                "migration_date": migration.effective_date.isoformat(),
                "to_class": migration.new_rate_class,
            }
        return bill, flags

    def _customer_charge(self, customer: Customer, service_start: date, service_end: date,
                         migration: Ticket | None, freeze_ends: date | None) -> int:
        edges = {service_start, service_end + timedelta(days=1)}
        for cut in (freeze_ends, migration.effective_date if migration else None):
            if cut is not None and service_start < cut <= service_end:
                edges.add(cut)
        ordered = sorted(edges)
        owed = Fraction(0)
        for lo, hi in zip(ordered, ordered[1:]):
            on, ceiling = self._schedule_axis(customer, lo, freeze_ends)
            row = self.ex.rate_row(self._class_on(customer, migration, lo), "*", on, ceiling)
            if row is not None:
                owed += Fraction(row.customer_charge * (hi - lo).days, DAYS)
        return _hu(owed)

    def _pick_ddc(self, customer: Customer, service_start: date,
                  service_end: date) -> tuple[Decimal | None, str | None]:
        totals: dict[str, Decimal] = {}
        for iv in self.ex.intervals:
            if iv.customer_id != customer.customer_id:
                continue
            if not (service_start <= iv.civil_date <= service_end):
                continue
            if iv.civil_date in self.ex.holidays_off:
                continue
            totals[iv.start_str] = totals.get(iv.start_str, Decimal(0)) + iv.kw
        if not totals:
            return None, None
        best_key = max(totals, key=lambda k: (totals[k], k))
        return totals[best_key], best_key

    def _retro_delta(self, customer: Customer, order: RegulatorOrder,
                     before_bank: dict[str, Fraction], ddc: Decimal | None) -> int:
        days = (order.period_end - order.period_start).days + 1
        cls = customer.rate_class
        change = 0
        for label in LABEL_ORDER:
            if before_bank[label] <= 0:
                continue
            assumed = before_bank[label] * days / DAYS
            was = self.ex.rate_row(cls, label, order.period_start, ceiling=10)
            now = self.ex.rate_row(cls, label, order.period_start, ceiling=None)
            if was is None or now is None:
                continue
            change += _hu(assumed * now.energy_rate / 1000) - _hu(assumed * was.energy_rate / 1000)
        if ddc is not None:
            was = self.ex.rate_row(cls, "*", order.period_start, ceiling=10)
            now = self.ex.rate_row(cls, "*", order.period_start, ceiling=None)
            if was is not None and now is not None:
                change += _hu(Fraction(ddc) * now.demand_rate) - _hu(Fraction(ddc) * was.demand_rate)
        return change

    # ─── artifact assembly ─────────────────────────────────────────────

    def emit_all(self, out_dir: Path) -> None:
        valid_customers = [c for c in self.ex.customers
                           if c.premise_code in self.ex.premises]
        results = [self._bill_customer(c) for c in valid_customers]
        bills = [b for b, _ in results]
        art = self._assemble(bills, [f for _, f in results])
        for name, obj in art.items():
            self._write_json(out_dir / name, obj)

    def _write_json(self, path: Path, obj) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(obj, fh, sort_keys=True, indent=2)
            fh.write("\n")

    def _summary(self, bills: list[Bill]) -> dict:
        return {
            "bill_total_ftuc": sum(b.bill_ftuc for b in bills),
            "bill_total_mrcc": sum(b.bill_mrcc for b in bills),
            "customer_charge_mrcc_total": sum(b.customer_charge_mrcc for b in bills),
            "customer_count": len(bills),
            "demand_charge_mrcc_total": sum(b.demand_mrcc for b in bills),
            "energy_charge_mrcc_total": sum(b.energy_mrcc for b in bills),
            "energy_kwh_total": sum(b.energy_kwh_th for b in bills),
            "fac_mrcc_total": sum(b.fac_mrcc for b in bills),
            "net_metering_avoided_cost_payout_mrcc_total": sum(b.nmb_avoided_cost_mrcc for b in bills),
            "net_metering_credit_kwh_carried_forward_total": sum(b.nmb_carried_kwh_th for b in bills),
            "net_metering_forfeited_kwh_total": sum(b.nmb_forfeited_kwh_th for b in bills),
            "period": {"civil_days": 31, "civil_hours": 745,
                       "end": "2025-10-31", "start": "2025-10-01"},
            "retroactive_adjustment_mrcc_total": sum(b.retro_total_mrcc for b in bills),
        }

    def _bill_entry(self, b: Bill) -> dict:
        return {
            "bill_total_ftuc": b.bill_ftuc,
            "bill_total_mrcc": b.bill_mrcc,
            "customer_charge_mrcc": b.customer_charge_mrcc,
            "customer_id": b.customer.customer_id,
            "demand_charge_mrcc": b.demand_mrcc,
            "energy_charge_mrcc": b.energy_mrcc,
            "energy_kwh": b.energy_kwh_th,
            "fac_mrcc": b.fac_mrcc,
            "net_metering": {
                "avoided_cost_payout_mrcc": b.nmb_avoided_cost_mrcc,
                "credit_kwh_carried_forward": b.nmb_carried_kwh_th,
                "forfeited_kwh": b.nmb_forfeited_kwh_th,
            },
            "premise_code": b.customer.premise_code,
            "retroactive_adjustment_mrcc": b.retro_total_mrcc,
        }

    def _scoped_rollup(self, bills: list[Bill]) -> dict:
        out = self._summary(bills)
        out["customers"] = sorted(
            [self._bill_entry(b) for b in bills],
            key=lambda e: _premise_num(e["premise_code"]))
        return out

    def _assemble(self, bills: list[Bill], flags: list[dict]) -> dict:
        art: dict = {}
        art["summary.json"] = self._summary(bills)
        for cls, name in [("RES", "rate_class_residential.json"),
                          ("COM", "rate_class_commercial.json"),
                          ("IND", "rate_class_industrial.json")]:
            subset = [b for b in bills if b.customer.rate_class == cls]
            art[name] = self._scoped_rollup(subset)
        for region in ("Meridian_North", "Meridian_South", "Meridian_East"):
            subset = [b for b in bills
                      if self.ex.premises[b.customer.premise_code].region == region]
            art[f"region_{region.lower()}.json"] = self._scoped_rollup(subset)
        art["policy_audit.json"] = self._policy_audit(bills)
        art["data_quality.json"] = self._data_quality(flags)
        return art

    def _policy_audit(self, bills: list[Bill]) -> dict:
        grandfather_applied = sorted(
            [b.grandfather_line for b in bills if b.grandfather_line],
            key=lambda e: e["customer_id"])
        migrations = sorted(
            [b.migration_line for b in bills if b.migration_line],
            key=lambda e: e["customer_id"])
        retro_lines: list[dict] = []
        for b in bills:
            retro_lines.extend(b.retro_lines)
        retro_lines.sort(key=lambda e: (e["order_id"], e["customer_id"]))
        holiday_recl = sorted(
            [{"date": h["date"], "name": h["name"], "tou_treatment": h["tou_treatment"]}
             for h in self.ex.holidays],
            key=lambda e: e["date"])
        fall_back = self.ex.dst.get("fall_back", [])
        dst_day = fall_back[0]["date"] if fall_back else DST_DAY.isoformat()
        return {
            "dst_cutover_applied": {"civil_hours_in_day": 25 if fall_back else 24,
                                    "date": dst_day},
            "grandfather_applied": grandfather_applied,
            "holiday_reclassifications": holiday_recl,
            "rate_class_migrations": migrations,
            "retroactive_orders_applied": retro_lines,
        }

    def _data_quality(self, flags: list[dict]) -> dict:
        active = 0
        oop = 0
        for o in self.ex.orders:
            if o.scope == "retroactive":
                active += 1
            elif o.scope == "forward_only":
                if o.effective_on <= PERIOD_LAST:
                    active += 1
                else:
                    oop += 1
        by_type = {"move_in": 0, "move_out": 0, "rate_class_migration": 0}
        valid_customer_ids = {c.customer_id for c in self.ex.customers
                              if c.premise_code in self.ex.premises}
        for t in self.ex.tickets:
            if t.customer_id in valid_customer_ids:
                by_type[t.event_type] = by_type.get(t.event_type, 0) + 1
        return {
            "customers_with_missing_read_at_service_end": sum(1 for f in flags if f["end"]),
            "customers_with_missing_read_at_service_start": sum(1 for f in flags if f["start"]),
            "customers_with_negative_nmb_start": sum(1 for v in self.ex.nmb.values() if v < 0),
            "demand_interval_count": len(self.ex.intervals),
            "duplicate_read_timestamps_flagged": sum(f["dups"] for f in flags),
            "high_variance_reads_flagged": sum(f["spikes"] for f in flags),
            "meter_read_count": len(self.ex.reads),
            "regulator_orders_active_this_period": active,
            "regulator_orders_out_of_period_declared": oop,
            "service_tickets_by_type": by_type,
        }


def _run_once(data_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    extract = Extract(data_dir)
    Reconciler(extract).emit_all(out_dir)


def _run_session(out_dir: Path) -> int:
    for line in sys.stdin:
        command = json.loads(line)
        if set(command) != {"turn_id", "data_dir"}:
            raise ValueError("session command must contain exactly turn_id and data_dir")
        turn_id = command["turn_id"]
        data_dir = command["data_dir"]
        if not isinstance(turn_id, str) or not isinstance(data_dir, str):
            raise TypeError("turn_id and data_dir must be strings")
        _run_once(Path(data_dir), out_dir)
        print(json.dumps({"status": "ok", "turn_id": turn_id},
                         sort_keys=True, separators=(",", ":")), flush=True)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--session":
        return _run_session(Path(argv[2]))
    if len(argv) != 3:
        print("Usage: reconcile.py DATA_DIR OUT_DIR | reconcile.py --session OUT_DIR", file=sys.stderr)
        return 2
    _run_once(Path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
