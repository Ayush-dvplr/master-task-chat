#!/usr/bin/env python3
"""MIGC monthly retail electricity settlement reconciler (schema v4.0).

Usage:
    python3 reconcile.py DATA_DIR OUT_DIR
    python3 reconcile.py --session OUT_DIR   (NDJSON commands on stdin)

Standard library only; exact arithmetic via fractions.Fraction.
"""

import bisect
import csv
import json
import math
import os
import sys
from datetime import date, timedelta
from fractions import Fraction

PERIOD_START = date(2025, 10, 1)
PERIOD_END = date(2025, 10, 31)
PERIOD_DAYS = (PERIOD_END - PERIOD_START).days + 1
FY_END = PERIOD_END
FY_START = date(PERIOD_END.year - 1, 11, 1)
AVOIDED_COST_MRCC_PER_KWH = 4
LABELS = ("peak", "shoulder", "night", "weekend")
RATE_CLASS_FILES = {
    "RES": "rate_class_residential.json",
    "COM": "rate_class_commercial.json",
    "IND": "rate_class_industrial.json",
}
REGION_FILES = {
    "Meridian_North": "region_meridian_north.json",
    "Meridian_South": "region_meridian_south.json",
    "Meridian_East": "region_meridian_east.json",
}
ROLLOVER_SPAN = {
    "mech5": Fraction(100000),
    "hybrid6": Fraction(1000000),
    "smart7": Fraction(10000000),
}
TOU_BANDS = {
    "RES": {"peak": ((16, 21),), "shoulder": ((7, 16), (21, 23)), "night": ((23, 24), (0, 7))},
    "COM": {"peak": ((12, 18),), "shoulder": ((8, 12), (18, 22)), "night": ((22, 24), (0, 8))},
    "IND": {"peak": ((10, 20),), "shoulder": ((6, 10), (20, 23)), "night": ((23, 24), (0, 6))},
}


def round_half_up(value):
    return math.floor(Fraction(value) + Fraction(1, 2))


def parse_date(text):
    text = (text or "").strip()
    return date.fromisoformat(text) if text else None


def parse_bool(text):
    return (text or "").strip().lower() == "true"


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(fh)]


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# Civil timeline (§1, §4, §5.2)
# --------------------------------------------------------------------------

class Timeline:
    """Ordered civil hours of the settlement period, DST aware."""

    def __init__(self, dst):
        self.repeated = {}
        self.skipped = {}
        for entry in (dst.get("fall_back") or []):
            d = parse_date(entry.get("date"))
            if d is not None:
                self.repeated[d] = int(entry.get("civil_hour_repeated", 1))
        for entry in (dst.get("spring_forward") or []):
            d = parse_date(entry.get("date"))
            if d is not None:
                self.skipped[d] = int(entry.get("civil_hour_skipped", 2))
        self.slots = []
        self.slot_start = []
        self.day_start = {}
        sec = 0
        day = PERIOD_START
        while day <= PERIOD_END:
            self.day_start[day] = sec
            for hour, occurrence in self.day_slots(day):
                self.slots.append((day, hour, occurrence))
                self.slot_start.append(sec)
                sec += 3600
            day += timedelta(days=1)
        self.total_seconds = sec

    def day_slots(self, day):
        if day in self.repeated:
            repeat_hour = self.repeated[day]
            out = []
            for hour in range(24):
                out.append((hour, 1))
                if hour == repeat_hour:
                    out.append((hour, 2))
            return out
        if day in self.skipped:
            gone = self.skipped[day]
            return [(hour, 1) for hour in range(24) if hour != gone]
        return [(hour, 1) for hour in range(24)]

    def hours_in_day(self, day):
        if day < PERIOD_START or day > PERIOD_END:
            return 24
        return len(self.day_slots(day))

    def seconds(self, day, hour=0, minute=0, second=0, occurrence=1):
        if day < PERIOD_START:
            return (day - PERIOD_START).days * 86400 + hour * 3600 + minute * 60 + second
        if day > PERIOD_END:
            extra = (day - PERIOD_END).days - 1
            return self.total_seconds + extra * 86400 + hour * 3600 + minute * 60 + second
        offset = hour * 3600 + minute * 60 + second
        if day in self.repeated:
            repeat_hour = self.repeated[day]
            if hour > repeat_hour or (hour == repeat_hour and occurrence == 2):
                offset += 3600
        elif day in self.skipped:
            if hour > self.skipped[day]:
                offset -= 3600
        return self.day_start[day] + offset

    def day_end_seconds(self, day):
        """Civil seconds at <day> 24:00."""
        if day < PERIOD_START:
            return (day - PERIOD_START).days * 86400 + 86400
        if day > PERIOD_END:
            return self.total_seconds + (day - PERIOD_END).days * 86400
        return self.day_start[day] + self.hours_in_day(day) * 3600

    def spread(self, hour_kwh, start, end, rate_per_second, clip_lo, clip_hi):
        lo = max(start, clip_lo, 0)
        hi = min(end, clip_hi, self.total_seconds)
        if hi <= lo:
            return
        index = bisect.bisect_right(self.slot_start, lo) - 1
        if index < 0:
            index = 0
        count = len(self.slot_start)
        while index < count and self.slot_start[index] < hi:
            s0 = self.slot_start[index]
            s1 = s0 + 3600
            overlap = min(hi, s1) - max(lo, s0)
            if overlap > 0:
                hour_kwh[index] += rate_per_second * overlap
            index += 1


# --------------------------------------------------------------------------
# Tariff resolution (§3.3, §10, §11)
# --------------------------------------------------------------------------

class Tariffs:
    def __init__(self, rows):
        self.rows = []
        for row in rows:
            self.rows.append({
                "schedule_id": row["schedule_id"],
                "rate_class": row["rate_class"],
                "tou_period": row["tou_period"],
                "effective_from": parse_date(row["effective_from"]),
                "effective_until": parse_date(row["effective_until"]),
                "energy_rate": int(row["energy_rate_mrcc_per_kwh"] or 0),
                "demand_rate": int(row["demand_rate_mrcc_per_kw"] or 0),
                "customer_charge": int(row["customer_charge_mrcc"] or 0),
                "precedence": int(row["order_of_precedence"] or 0),
            })

    def pick(self, rate_class, tou_period, when, exclude_id=None, precedence=None):
        best = None
        best_key = None
        for row in self.rows:
            if row["rate_class"] != rate_class or row["tou_period"] != tou_period:
                continue
            if exclude_id is not None and row["schedule_id"] == exclude_id:
                continue
            if precedence is not None and row["precedence"] != precedence:
                continue
            start = row["effective_from"]
            if start is not None and start > when:
                continue
            until = row["effective_until"]
            if until is not None and until < when:
                continue
            key = (row["precedence"],
                   start or date.min,
                   row["schedule_id"])
            if best_key is None or key > best_key:
                best_key = key
                best = row
        return best


# --------------------------------------------------------------------------
# Settlement engine
# --------------------------------------------------------------------------

class Settlement:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self._load()
        self._prepare()
        self._compute()

    # -- loading ---------------------------------------------------------
    def path(self, name):
        return os.path.join(self.data_dir, name)

    def _load(self):
        self.customer_rows = read_csv_rows(self.path("customers.csv"))
        self.premise_rows = read_csv_rows(self.path("premises.csv"))
        self.tariffs = Tariffs(read_csv_rows(self.path("tariff_schedule.csv")))
        self.fac_rows = read_csv_rows(self.path("fac_index.csv"))
        self.holidays_raw = read_json(self.path("holiday_calendar.json"))
        self.dst_raw = read_json(self.path("dst_calendar.json"))
        self.currency_raw = read_json(self.path("currency_rates.json"))
        self.orders_raw = read_json(self.path("regulator_orders.json"))
        self.nmb_rows = read_csv_rows(self.path("net_metering_bank.csv"))
        self.tickets_raw = read_json(self.path("service_tickets.json"))
        self.read_rows = read_csv_rows(self.path("meter_reads.csv"))
        self.interval_rows = read_csv_rows(self.path("demand_intervals.csv"))

    # -- static reference structures -------------------------------------
    def _prepare(self):
        self.timeline = Timeline(self.dst_raw)

        self.premises = {}
        for row in self.premise_rows:
            self.premises[row["premise_code"]] = {
                "premise_code": row["premise_code"],
                "region": row["region"],
                "channels": int(row["meter_channel_count"] or 1),
            }

        self.holiday_tou = {}
        self.holiday_off = set()
        self.holiday_records = []
        for entry in self.holidays_raw:
            d = parse_date(entry.get("date"))
            if d is None:
                continue
            treatment = entry.get("tou_treatment", "")
            if PERIOD_START <= d <= PERIOD_END:
                self.holiday_tou[d] = treatment
                if treatment == "off":
                    self.holiday_off.add(d)
                self.holiday_records.append({
                    "date": entry.get("date"),
                    "name": entry.get("name", ""),
                    "tou_treatment": treatment,
                })
        self.holiday_records.sort(key=lambda r: r["date"])

        self.fac_by_month = {}
        for row in self.fac_rows:
            self.fac_by_month[row["month"]] = int(row["fac_mrcc_per_kwh"] or 0)

        self.fx_rates = []
        for entry in (self.currency_raw.get("rates") or []):
            d = parse_date(entry.get("date"))
            if d is not None:
                self.fx_rates.append((d, int(entry["mrc_per_ftu"])))
        self.fx_rates.sort(key=lambda item: item[0])

        self.customers = {}
        for row in self.customer_rows:
            cid = row["customer_id"]
            premise = self.premises.get(row["premise_code"])
            cust = {
                "customer_id": cid,
                "rate_class": row["rate_class"],
                "premise_code": row["premise_code"],
                "meter_class": row["meter_class"],
                "currency": row["billing_currency"],
                "gf_flag": parse_bool(row["grandfather_flag"]),
                "gf_date": parse_date(row["grandfather_date"]),
                "gf_expires": parse_date(row["grandfather_expires_on"]),
                "gf_date_raw": row["grandfather_date"],
                "gf_expires_raw": row["grandfather_expires_on"],
                "solar": parse_bool(row["solar_enrolled"]),
                "region": premise["region"] if premise else None,
                "valid": premise is not None,
                "service_start": PERIOD_START,
                "service_end": PERIOD_END,
                "migration_date": None,
                "migration_class": None,
                "bank_start": 0,
            }
            self.customers[cid] = cust
        self.valid_ids = sorted(cid for cid, c in self.customers.items() if c["valid"])

        self.ticket_counts = {"move_in": 0, "move_out": 0, "rate_class_migration": 0}
        for ticket in self.tickets_raw:
            cid = ticket.get("customer_id")
            cust = self.customers.get(cid)
            if cust is None or not cust["valid"]:
                continue
            kind = ticket.get("event_type")
            if kind not in self.ticket_counts:
                continue
            self.ticket_counts[kind] += 1
            eff = parse_date(ticket.get("effective_date"))
            if eff is None:
                continue
            if kind == "move_in":
                cust["service_start"] = max(cust["service_start"], eff)
            elif kind == "move_out":
                cust["service_end"] = min(cust["service_end"], eff)
            else:
                cust["migration_date"] = eff
                cust["migration_class"] = ticket.get("new_rate_class") or None

        for row in self.nmb_rows:
            cust = self.customers.get(row["customer_id"])
            if cust is None or not cust["valid"]:
                continue
            cust["bank_start"] = int(row["balance_kwh_start_of_period"] or 0)

        self.rate_cache = {}
        self.charge_cache = {}
        self.demand_cache = {}

    # -- per-customer helpers --------------------------------------------
    def class_on(self, cust, day):
        if cust["migration_date"] is not None and cust["migration_class"] \
                and day >= cust["migration_date"]:
            return cust["migration_class"]
        return cust["rate_class"]

    def frozen_on(self, cust, day):
        """True when the §10 grandfather freeze governs <day>."""
        if not cust["gf_flag"] or cust["gf_date"] is None:
            return False
        if cust["migration_date"] is not None and day >= cust["migration_date"]:
            return False
        if cust["gf_expires"] is not None and day >= cust["gf_expires"]:
            return False
        return True

    def tou_label(self, rate_class, day, hour, is_repeat):
        if is_repeat:
            return "weekend" if rate_class == "COM" else "night"
        if day in self.holiday_tou:
            return "weekend"
        if day.weekday() >= 5:
            return "weekend"
        bands = TOU_BANDS[rate_class]
        for label in ("peak", "shoulder", "night"):
            for lo, hi in bands[label]:
                if lo <= hour < hi:
                    return label
        return "night"

    def _row_for(self, cust, rate_class, tou_period, day):
        if self.frozen_on(cust, day):
            row = self.tariffs.pick(rate_class, tou_period, cust["gf_date"], precedence=10)
            if row is not None:
                return row
        return self.tariffs.pick(rate_class, tou_period, day)

    def energy_rate(self, cust, rate_class, label, day):
        key = (cust["customer_id"], rate_class, label, day)
        cached = self.rate_cache.get(key)
        if cached is None:
            row = self._row_for(cust, rate_class, label, day)
            cached = row["energy_rate"] if row else 0
            self.rate_cache[key] = cached
        return cached

    def customer_charge_rate(self, cust, rate_class, day):
        key = (cust["customer_id"], rate_class, day)
        cached = self.charge_cache.get(key)
        if cached is None:
            row = self._row_for(cust, rate_class, "*", day)
            cached = row["customer_charge"] if row else 0
            self.charge_cache[key] = cached
        return cached

    def demand_rate(self, cust, rate_class, day):
        key = (cust["customer_id"], rate_class, day)
        cached = self.demand_cache.get(key)
        if cached is None:
            row = self._row_for(cust, rate_class, "*", day)
            cached = row["demand_rate"] if row else 0
            self.demand_cache[key] = cached
        return cached

    def fx_rate_on(self, day):
        chosen = None
        for rate_date, value in self.fx_rates:
            if rate_date <= day:
                chosen = value
            else:
                break
        if chosen is None and self.fx_rates:
            chosen = self.fx_rates[0][1]
        return chosen

    def to_ftuc(self, amount_mrcc, day):
        rate = self.fx_rate_on(day)
        if not rate:
            return 0
        return round_half_up(Fraction(int(amount_mrcc) * 100, rate))

    # -- meter reads ------------------------------------------------------
    def _group_reads(self):
        by_channel = {}
        for index, row in enumerate(self.read_rows):
            cid = row["customer_id"]
            cust = self.customers.get(cid)
            if cust is None or not cust["valid"]:
                continue
            stamp = row["read_timestamp"]
            day = parse_date(stamp[:10])
            hour = int(stamp[11:13])
            minute = int(stamp[14:16])
            second = int(stamp[17:19])
            by_channel.setdefault((cid, int(row["channel"])), []).append({
                "read_id": row["read_id"],
                "stamp": stamp,
                "day": day,
                "seconds": self.timeline.seconds(day, hour, minute, second),
                "register": Fraction(row["register_reading_kwh"]),
                "order": index,
            })
        return by_channel

    def _rollover_delta(self, meter_class, before, after):
        if after >= before:
            return after - before
        span = ROLLOVER_SPAN.get(meter_class, ROLLOVER_SPAN["smart7"])
        return span - before + after

    def _dedupe(self, meter_class, reads):
        reads = sorted(reads, key=lambda r: (r["seconds"], r["order"]))
        groups = []
        for read in reads:
            if groups and groups[-1][0]["stamp"] == read["stamp"]:
                groups[-1].append(read)
            else:
                groups.append([read])
        retained = []
        discarded = 0
        for group in groups:
            if len(group) == 1:
                retained.append(group[0])
                continue
            discarded += len(group) - 1
            if not retained:
                pick = max(group, key=lambda r: (r["register"], r["read_id"]))
            else:
                previous = retained[-1]
                pick = max(group, key=lambda r: (
                    self._rollover_delta(meter_class, previous["register"], r["register"]),
                    r["register"], r["read_id"]))
            retained.append(pick)
        return retained, discarded

    # -- main computation -------------------------------------------------
    def _compute(self):
        self.duplicate_flagged = 0
        self.high_variance_flagged = 0
        self.missing_start = 0
        self.missing_end = 0

        channel_reads = self._group_reads()
        channels_by_customer = {}
        for (cid, channel) in channel_reads:
            channels_by_customer.setdefault(cid, []).append(channel)

        demand_by_customer = {}
        for row in self.interval_rows:
            cid = row["customer_id"]
            cust = self.customers.get(cid)
            if cust is None or not cust["valid"]:
                continue
            stamp = row["interval_start"]
            bucket = demand_by_customer.setdefault(cid, {})
            bucket[stamp] = bucket.get(stamp, Fraction(0)) + Fraction(row["demand_kw"])

        timeline = self.timeline
        slot_count = len(timeline.slots)
        fac_now = self.fac_by_month.get("%04d-%02d" % (PERIOD_START.year, PERIOD_START.month), 0)

        self.results = {}
        for cid in self.valid_ids:
            cust = self.customers[cid]
            hour_kwh = [Fraction(0)] * slot_count
            svc_start = cust["service_start"]
            svc_end = cust["service_end"]
            clip_lo = timeline.seconds(svc_start, 0, 0, 0)
            clip_hi = timeline.day_end_seconds(svc_end)
            if svc_end < svc_start:
                clip_hi = clip_lo

            missing_start_here = False
            missing_end_here = False
            for channel in sorted(channels_by_customer.get(cid, [])):
                reads, discarded = self._dedupe(
                    cust["meter_class"], channel_reads[(cid, channel)])
                self.duplicate_flagged += discarded
                rates = []
                for before, after in zip(reads, reads[1:]):
                    span = after["seconds"] - before["seconds"]
                    if span <= 0:
                        continue
                    delta = self._rollover_delta(
                        cust["meter_class"], before["register"], after["register"])
                    rate = Fraction(delta, span)
                    rates.append(rate)
                    timeline.spread(hour_kwh, before["seconds"], after["seconds"],
                                    rate, clip_lo, clip_hi)
                if rates:
                    ordered = sorted(rates)
                    mid = len(ordered) // 2
                    if len(ordered) % 2:
                        median = ordered[mid]
                    else:
                        median = (ordered[mid - 1] + ordered[mid]) / 2
                    threshold = median * 20
                    self.high_variance_flagged += sum(1 for r in rates if r > threshold)
                if not reads:
                    continue
                if not any(r["day"] <= svc_start for r in reads):
                    missing_start_here = True
                    if rates:
                        timeline.spread(hour_kwh, clip_lo, reads[0]["seconds"],
                                        rates[0], clip_lo, clip_hi)
                if not any(r["day"] >= svc_end for r in reads):
                    missing_end_here = True
                    if rates:
                        timeline.spread(hour_kwh, reads[-1]["seconds"], clip_hi,
                                        rates[-1], clip_lo, clip_hi)
            if missing_start_here:
                self.missing_start += 1
            if missing_end_here:
                self.missing_end += 1

            buckets = {label: [Fraction(0), Fraction(0)] for label in LABELS}
            total_kwh = Fraction(0)
            for index, (day, hour, occurrence) in enumerate(timeline.slots):
                kwh = hour_kwh[index]
                if not kwh:
                    continue
                rate_class = self.class_on(cust, day)
                label = self.tou_label(rate_class, day, hour, occurrence == 2)
                rate = self.energy_rate(cust, rate_class, label, day)
                entry = buckets[label]
                entry[0] += kwh
                entry[1] += kwh * rate
                total_kwh += kwh

            gross_buckets = {label: buckets[label][0] for label in LABELS}

            bank = Fraction(cust["bank_start"], 1000)
            remaining_bank = bank if bank > 0 else Fraction(0)
            drawn_total = Fraction(0)
            for label in LABELS:
                if remaining_bank <= 0:
                    break
                label_kwh = buckets[label][0]
                if label_kwh <= 0:
                    continue
                draw = min(remaining_bank, label_kwh)
                buckets[label][1] *= (label_kwh - draw) / label_kwh
                remaining_bank -= draw
                drawn_total += draw

            energy_charge = sum(round_half_up(buckets[label][1]) for label in LABELS)
            billable_kwh = total_kwh - drawn_total
            fac_mrcc = round_half_up(billable_kwh * fac_now)

            demand_charge = 0
            ddc = Fraction(0)
            intervals = demand_by_customer.get(cid, {})
            best = None
            for stamp, kw in intervals.items():
                day = parse_date(stamp[:10])
                if day is None or day < svc_start or day > svc_end:
                    continue
                if day in self.holiday_off:
                    continue
                key = (kw, stamp)
                if best is None or key > best[0]:
                    best = (key, stamp, kw, day)
            if best is not None:
                ddc = best[2]
                rate_class = self.class_on(cust, best[3])
                demand_charge = round_half_up(ddc * self.demand_rate(cust, rate_class, best[3]))

            charge_acc = Fraction(0)
            day = svc_start
            while day <= svc_end:
                rate_class = self.class_on(cust, day)
                charge_acc += Fraction(self.customer_charge_rate(cust, rate_class, day),
                                       PERIOD_DAYS)
                day += timedelta(days=1)
            customer_charge = round_half_up(charge_acc)

            trueup_class = self.class_on(cust, PERIOD_END)
            payout = 0
            forfeited = 0
            if bank > 0 and remaining_bank > 0:
                if trueup_class == "RES":
                    payout = round_half_up(remaining_bank * AVOIDED_COST_MRCC_PER_KWH)
                else:
                    forfeited = round_half_up(remaining_bank * 1000)

            self.results[cid] = {
                "customer_id": cid,
                "premise_code": cust["premise_code"],
                "energy_kwh": round_half_up(total_kwh * 1000),
                "energy_charge_mrcc": energy_charge,
                "demand_charge_mrcc": demand_charge,
                "customer_charge_mrcc": customer_charge,
                "fac_mrcc": fac_mrcc,
                "net_metering": {
                    "credit_kwh_carried_forward": 0,
                    "avoided_cost_payout_mrcc": payout,
                    "forfeited_kwh": forfeited,
                },
                "retroactive_adjustment_mrcc": 0,
                "bill_total_mrcc": 0,
                "bill_total_ftuc": 0,
                "_gross_buckets": gross_buckets,
                "_ddc": ddc,
            }

        self._apply_retroactive_orders()
        self._finalise_bills()

    # -- §11 retroactive orders ------------------------------------------
    def _apply_retroactive_orders(self):
        self.retro_records = []
        self.retro_lines = {cid: [] for cid in self.valid_ids}
        self.orders_active = 0
        self.orders_out_of_period = 0

        for order in sorted(self.orders_raw, key=lambda o: o.get("order_id", "")):
            scope = order.get("scope")
            effective_on = parse_date(order.get("effective_on"))
            if scope == "retroactive":
                self.orders_active += 1
            elif scope == "forward_only":
                if effective_on is not None and effective_on <= PERIOD_END:
                    self.orders_active += 1
                else:
                    self.orders_out_of_period += 1
            if scope != "retroactive":
                continue

            superseded_id = order.get("supersedes_schedule_id")
            new_id = order.get("new_schedule_id") or None
            retro_start = parse_date(order.get("period_start"))
            retro_end = parse_date(order.get("period_end"))
            if retro_start is None or retro_end is None:
                continue
            retro_days = (retro_end - retro_start).days + 1
            if retro_days <= 0:
                continue
            # §3.8: an order whose own period lies entirely outside the fiscal
            # year has no monetary effect on this settlement.
            if retro_end < FY_START or retro_start > FY_END:
                continue

            target_class = None
            for row in self.tariffs.rows:
                if row["schedule_id"] == superseded_id:
                    target_class = row["rate_class"]
                    break
            if target_class is None and new_id is not None:
                for row in self.tariffs.rows:
                    if row["schedule_id"] == new_id:
                        target_class = row["rate_class"]
                        break
            if target_class is None:
                continue

            immune = bool(order.get("grandfather_immune"))
            scale = Fraction(retro_days, PERIOD_DAYS)

            for cid in self.valid_ids:
                cust = self.customers[cid]
                if cust["rate_class"] != target_class:
                    continue
                if cust["gf_flag"] and not immune:
                    continue
                result = self.results[cid]
                old_total = 0
                new_total = 0
                for label in LABELS:
                    kwh = result["_gross_buckets"][label] * scale
                    if kwh == 0:
                        continue
                    old_row = self.tariffs.pick(target_class, label, retro_start,
                                                exclude_id=new_id)
                    new_row = self.tariffs.pick(target_class, label, retro_start)
                    old_rate = old_row["energy_rate"] if old_row else 0
                    new_rate = new_row["energy_rate"] if new_row else 0
                    old_total += round_half_up(kwh * old_rate)
                    new_total += round_half_up(kwh * new_rate)
                ddc = result["_ddc"]
                if ddc:
                    old_row = self.tariffs.pick(target_class, "*", retro_start,
                                                exclude_id=new_id)
                    new_row = self.tariffs.pick(target_class, "*", retro_start)
                    old_total += round_half_up(ddc * (old_row["demand_rate"] if old_row else 0))
                    new_total += round_half_up(ddc * (new_row["demand_rate"] if new_row else 0))
                adjustment = new_total - old_total
                if adjustment == 0:
                    continue
                result["retroactive_adjustment_mrcc"] += adjustment
                self.retro_lines[cid].append((adjustment, retro_start))
                self.retro_records.append({
                    "order_id": order.get("order_id"),
                    "customer_id": cid,
                    "adjustment_mrcc": adjustment,
                })

        self.retro_records.sort(key=lambda r: (r["order_id"], r["customer_id"]))

    # -- §12 bill totals --------------------------------------------------
    def _finalise_bills(self):
        for cid in self.valid_ids:
            cust = self.customers[cid]
            result = self.results[cid]
            base = (result["energy_charge_mrcc"]
                    + result["demand_charge_mrcc"]
                    + result["customer_charge_mrcc"]
                    + result["fac_mrcc"]
                    - result["net_metering"]["avoided_cost_payout_mrcc"])
            if cust["currency"] == "FTU":
                total = self.to_ftuc(base, PERIOD_START)
                for adjustment, retro_start in self.retro_lines[cid]:
                    total += self.to_ftuc(adjustment, retro_start)
                result["bill_total_ftuc"] = total
                result["bill_total_mrcc"] = 0
            else:
                result["bill_total_mrcc"] = base + result["retroactive_adjustment_mrcc"]
                result["bill_total_ftuc"] = 0

    # -- artifacts --------------------------------------------------------
    def period_block(self):
        hours = sum(self.timeline.hours_in_day(PERIOD_START + timedelta(days=i))
                    for i in range(PERIOD_DAYS))
        return {
            "start": PERIOD_START.isoformat(),
            "end": PERIOD_END.isoformat(),
            "civil_days": PERIOD_DAYS,
            "civil_hours": hours,
        }

    def published(self, cid):
        result = self.results[cid]
        return {
            "customer_id": result["customer_id"],
            "premise_code": result["premise_code"],
            "energy_kwh": result["energy_kwh"],
            "energy_charge_mrcc": result["energy_charge_mrcc"],
            "demand_charge_mrcc": result["demand_charge_mrcc"],
            "customer_charge_mrcc": result["customer_charge_mrcc"],
            "fac_mrcc": result["fac_mrcc"],
            "net_metering": dict(result["net_metering"]),
            "retroactive_adjustment_mrcc": result["retroactive_adjustment_mrcc"],
            "bill_total_mrcc": result["bill_total_mrcc"],
            "bill_total_ftuc": result["bill_total_ftuc"],
        }

    def rollup(self, ids, include_customers):
        entries = [self.published(cid) for cid in ids]
        entries.sort(key=lambda e: (int(e["premise_code"][1:]), e["customer_id"]))
        report = {
            "period": self.period_block(),
            "customer_count": len(entries),
            "energy_kwh_total": sum(e["energy_kwh"] for e in entries),
            "energy_charge_mrcc_total": sum(e["energy_charge_mrcc"] for e in entries),
            "demand_charge_mrcc_total": sum(e["demand_charge_mrcc"] for e in entries),
            "customer_charge_mrcc_total": sum(e["customer_charge_mrcc"] for e in entries),
            "fac_mrcc_total": sum(e["fac_mrcc"] for e in entries),
            "net_metering_credit_kwh_carried_forward_total":
                sum(e["net_metering"]["credit_kwh_carried_forward"] for e in entries),
            "net_metering_avoided_cost_payout_mrcc_total":
                sum(e["net_metering"]["avoided_cost_payout_mrcc"] for e in entries),
            "net_metering_forfeited_kwh_total":
                sum(e["net_metering"]["forfeited_kwh"] for e in entries),
            "retroactive_adjustment_mrcc_total":
                sum(e["retroactive_adjustment_mrcc"] for e in entries),
            "bill_total_mrcc": sum(e["bill_total_mrcc"] for e in entries),
            "bill_total_ftuc": sum(e["bill_total_ftuc"] for e in entries),
        }
        if include_customers:
            report["customers"] = entries
        return report

    def policy_audit(self):
        grandfather = []
        migrations = []
        for cid in self.valid_ids:
            cust = self.customers[cid]
            if cust["gf_flag"]:
                end = cust["gf_expires"]
                migration = cust["migration_date"]
                if migration is not None and (end is None or migration < end):
                    end = migration
                split = None
                if end is not None and PERIOD_START < end <= PERIOD_END:
                    split = end.isoformat()
                grandfather.append({
                    "customer_id": cid,
                    "grandfather_date": cust["gf_date_raw"],
                    "expires_on": cust["gf_expires_raw"],
                    "prorata_split_at": split,
                })
            if cust["migration_date"] is not None and cust["migration_class"]:
                migrations.append({
                    "customer_id": cid,
                    "migration_date": cust["migration_date"].isoformat(),
                    "from_class": cust["rate_class"],
                    "to_class": cust["migration_class"],
                })
        grandfather.sort(key=lambda r: r["customer_id"])
        migrations.sort(key=lambda r: r["customer_id"])

        cutover = {"date": None, "civil_hours_in_day": 24}
        candidates = sorted(self.timeline.repeated) + sorted(self.timeline.skipped)
        in_period = [d for d in candidates if PERIOD_START <= d <= PERIOD_END]
        chosen = (in_period or candidates)
        if chosen:
            day = chosen[0]
            cutover = {"date": day.isoformat(),
                       "civil_hours_in_day": self.timeline.hours_in_day(day)}

        return {
            "grandfather_applied": grandfather,
            "rate_class_migrations": migrations,
            "retroactive_orders_applied": self.retro_records,
            "holiday_reclassifications": self.holiday_records,
            "dst_cutover_applied": cutover,
        }

    def data_quality(self):
        negative = 0
        for row in self.nmb_rows:
            cust = self.customers.get(row["customer_id"])
            if cust is None or not cust["valid"]:
                continue
            if int(row["balance_kwh_start_of_period"] or 0) < 0:
                negative += 1
        return {
            "meter_read_count": len(self.read_rows),
            "demand_interval_count": len(self.interval_rows),
            "customers_with_negative_nmb_start": negative,
            "customers_with_missing_read_at_service_start": self.missing_start,
            "customers_with_missing_read_at_service_end": self.missing_end,
            "high_variance_reads_flagged": self.high_variance_flagged,
            "service_tickets_by_type": dict(self.ticket_counts),
            "regulator_orders_active_this_period": self.orders_active,
            "regulator_orders_out_of_period_declared": self.orders_out_of_period,
            "duplicate_read_timestamps_flagged": self.duplicate_flagged,
        }

    def artifacts(self):
        out = {"summary.json": self.rollup(self.valid_ids, False)}
        for rate_class, name in RATE_CLASS_FILES.items():
            ids = [cid for cid in self.valid_ids
                   if self.customers[cid]["rate_class"] == rate_class]
            out[name] = self.rollup(ids, True)
        for region, name in REGION_FILES.items():
            ids = [cid for cid in self.valid_ids
                   if self.customers[cid]["region"] == region]
            out[name] = self.rollup(ids, True)
        out["policy_audit.json"] = self.policy_audit()
        out["data_quality.json"] = self.data_quality()
        return out


def write_artifacts(artifacts, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name in sorted(artifacts):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(artifacts[name], fh, sort_keys=True, indent=2)
            fh.write("\n")


def run(data_dir, out_dir):
    write_artifacts(Settlement(data_dir).artifacts(), out_dir)


def main(argv):
    if len(argv) == 3 and argv[1] == "--session":
        out_dir = argv[2]
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            command = json.loads(line)
            run(command["data_dir"], out_dir)
            sys.stdout.write(json.dumps(
                {"status": "ok", "turn_id": command["turn_id"]},
                sort_keys=True, separators=(",", ":")) + "\n")
            sys.stdout.flush()
        return 0
    if len(argv) == 3:
        run(argv[1], argv[2])
        return 0
    sys.stderr.write(
        "usage: reconcile.py DATA_DIR OUT_DIR | reconcile.py --session OUT_DIR\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
