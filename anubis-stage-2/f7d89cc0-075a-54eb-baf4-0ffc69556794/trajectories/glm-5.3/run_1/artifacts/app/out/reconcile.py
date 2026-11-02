#!/usr/bin/env python3
"""Meridian Interstate Grid Compact (MIGC) monthly retail settlement reconciler.

Implements the written data contract shipped with each extract (schema.md v4.0)
for the October 2025 settlement period.  All arithmetic is exact (Fraction);
no floating point value is ever produced.

Usage:
    reconcile.py DATA_DIR OUT_DIR        one-shot
    reconcile.py --session OUT_DIR       NDJSON session mode
"""

import csv
import json
import os
import sys
from datetime import date, timedelta
from fractions import Fraction

PERIOD_START = date(2025, 10, 1)
PERIOD_END = date(2025, 10, 31)
PERIOD_DAYS = (PERIOD_END - PERIOD_START).days + 1
DAYS_IN_CURRENT_PERIOD = 31                 # §11 assumed-prior denominator
FY_START = date(2024, 11, 1)                # Meridian FY2025 bounds
AVOIDED_COST_MRCC_PER_KWH = Fraction(4)     # §7.2
LABELS = ("peak", "shoulder", "night", "weekend")
STAR = "*"

# §5.1 TOU bands: (first hour, exclusive end hour, label); wrap-around allowed.
BANDS = {
    "RES": ((16, 21, "peak"), (7, 16, "shoulder"), (21, 23, "shoulder"),
            (23, 24, "night"), (0, 7, "night")),
    "COM": ((12, 18, "peak"), (8, 12, "shoulder"), (18, 22, "shoulder"),
            (22, 24, "night"), (0, 8, "night")),
    "IND": ((10, 20, "peak"), (6, 10, "shoulder"), (20, 23, "shoulder"),
            (23, 24, "night"), (0, 6, "night")),
}
WINDOWS = {}
for _cls, _bands in BANDS.items():
    _tbl = {}
    for _h0, _h1, _lab in _bands:
        _hrs = range(_h0, _h1) if _h0 < _h1 else list(range(_h0, 24)) + list(range(0, _h1))
        for _h in _hrs:
            _tbl[_h] = _lab
    WINDOWS[_cls] = _tbl

MAX_REGISTER = {"mech5": Fraction(99999999, 1000),    # 99999.999
                "hybrid6": Fraction(999999999, 1000),  # 999999.999
                "smart7": Fraction(9999999999, 1000)}  # 9999999.999
ROLL_INCREMENT = Fraction(1, 1000)                    # §4.1 "+0.001"

REGION_FILES = [("Meridian_North", "region_meridian_north.json"),
                ("Meridian_South", "region_meridian_south.json"),
                ("Meridian_East", "region_meridian_east.json")]
CLASS_FILES = [("RES", "rate_class_residential.json"),
               ("COM", "rate_class_commercial.json"),
               ("IND", "rate_class_industrial.json")]

def rhu(x):
    """Half-up rounding of an exact Fraction; ties go toward +infinity."""
    return (2 * x.numerator + x.denominator) // (2 * x.denominator)


def to_frac(text):
    text = (text or "").strip()
    if not text:
        return Fraction(0)
    return Fraction(text)


def parse_date(text):
    return date(int(text[0:4]), int(text[5:7]), int(text[8:10]))


def daterange(d0, d1):
    out = []
    d = d0
    while d <= d1:
        out.append(d)
        d += timedelta(days=1)
    return out


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class Snapshot:
    """One complete twelve-file extract."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self._off_cache = {}
        self._cover_cache = {}
        self._row_cache = {}
        self._rate_cache = {}
        self._load_reference()
        self._build_calendar()
        self._load_transactions()

    # ---------------------------------------------------------------- loading
    def _load_reference(self):
        self.customers = {}
        self.premises = {}
        self.customer_order = []
        for row in read_csv(os.path.join(self.dir, "customers.csv")):
            cid = row["customer_id"].strip()
            gf = row["grandfather_flag"].strip().lower() == "true"
            rec = {
                "customer_id": cid,
                "name": row["name"],
                "rate_class": row["rate_class"].strip(),
                "premise_code": row["premise_code"].strip(),
                "meter_class": row["meter_class"].strip(),
                "currency": row["billing_currency"].strip(),
                "gf_flag": gf,
                "gf_date": parse_date(row["grandfather_date"]) if row["grandfather_date"].strip() else None,
                "gf_expires": parse_date(row["grandfather_expires_on"]) if row["grandfather_expires_on"].strip() else None,
                "solar": row["solar_enrolled"].strip().lower() == "true",
                "fiscal_group": row["fiscal_group"].strip(),
            }
            self.customers[cid] = rec
            self.customer_order.append(cid)
        for row in read_csv(os.path.join(self.dir, "premises.csv")):
            pc = row["premise_code"].strip()
            self.premises[pc] = {
                "premise_code": pc,
                "region": row["region"].strip(),
                "channels": int(row["meter_channel_count"]),
            }

        self.tariff = []
        for row in read_csv(os.path.join(self.dir, "tariff_schedule.csv")):
            until = row["effective_until"].strip()
            self.tariff.append({
                "sid": row["schedule_id"].strip(),
                "rate_class": row["rate_class"].strip(),
                "tou": row["tou_period"].strip(),
                "from": parse_date(row["effective_from"]),
                "until": parse_date(until) if until else None,
                "energy": int(row["energy_rate_mrcc_per_kwh"] or 0),
                "demand": int(row["demand_rate_mrcc_per_kw"] or 0),
                "charge": int(row["customer_charge_mrcc"] or 0),
                "prec": int(row["order_of_precedence"] or 0),
            })

        self.fac = {}
        for row in read_csv(os.path.join(self.dir, "fac_index.csv")):
            self.fac[row["month"].strip()] = int(row["fac_mrcc_per_kwh"] or 0)

        self.nmb = {}
        for row in read_csv(os.path.join(self.dir, "net_metering_bank.csv")):
            self.nmb[row["customer_id"].strip()] = int(row["balance_kwh_start_of_period"] or 0)

        self.orders = read_json(os.path.join(self.dir, "regulator_orders.json")) or []
        self.order_new_ids = {}
        for o in self.orders:
            sid = (o.get("new_schedule_id") or "").strip()
            if sid:
                self.order_new_ids[sid] = bool(o.get("grandfather_immune"))
        self.rows_by_key = {}
        for r in self.tariff:
            self.rows_by_key.setdefault((r["rate_class"], r["tou"]), []).append(r)
        self.row_by_sid = {r["sid"]: r for r in self.tariff}

        self.tickets = read_json(os.path.join(self.dir, "service_tickets.json")) or []

        cur = read_json(os.path.join(self.dir, "currency_rates.json")) or {}
        self.rates = sorted(((parse_date(r["date"]), int(r["mrc_per_ftu"]))
                             for r in (cur.get("rates") or [])), key=lambda x: x[0])

    def _build_calendar(self):
        hol = read_json(os.path.join(self.dir, "holiday_calendar.json")) or []
        self.holidays = {}
        self.holiday_list = []
        for h in hol:
            d = parse_date(h["date"])
            treat = h["tou_treatment"]
            self.holidays[d] = treat
            if PERIOD_START <= d <= PERIOD_END:
                self.holiday_list.append({"date": h["date"], "name": h["name"],
                                          "tou_treatment": treat})
        self.holiday_list.sort(key=lambda x: x["date"])

        dst = read_json(os.path.join(self.dir, "dst_calendar.json")) or {}
        self.fall_back = {}
        for e in (dst.get("fall_back") or []):
            self.fall_back[parse_date(e["date"])] = int(e.get("civil_hour_repeated", 1))
        self.spring_fwd = {}
        for e in (dst.get("spring_forward") or []):
            self.spring_fwd[parse_date(e["date"])] = int(e.get("civil_hour_skipped", 2))
        self.fall_dates = sorted(self.fall_back)
        self.spring_dates = sorted(self.spring_fwd)

        # civil hour slots across the period
        self.slots = []
        for d in daterange(PERIOD_START, PERIOD_END):
            base = self.day_offset(d)
            cand = []
            if d in self.fall_back:
                rep = self.fall_back[d]
                for h in range(24):
                    cand.append((h, False, base + self.intra(d, h, False)))
                cand.append((rep, True, base + self.intra(d, rep, True)))
            elif d in self.spring_fwd:
                skip = self.spring_fwd[d]
                for h in range(24):
                    if h == skip:
                        continue
                    cand.append((h, False, base + self.intra(d, h, False)))
            else:
                for h in range(24):
                    cand.append((h, False, base + self.intra(d, h, False)))
            cand.sort(key=lambda x: x[2])
            for h, second, start in cand:
                self.slots.append((d, h, second, start))
        self.slot_starts = [s[3] for s in self.slots]

    def _load_transactions(self):
        reads = read_csv(os.path.join(self.dir, "meter_reads.csv"))
        self.meter_read_count = len(reads)
        self.reads = {}
        for i, row in enumerate(reads):
            cid = row["customer_id"].strip()
            self.reads.setdefault(cid, {}).setdefault(int(row["channel"]), []).append({
                "rid": row["read_id"].strip(),
                "ts": row["read_timestamp"].strip(),
                "d": parse_date(row["read_timestamp"]),
                "h": int(row["read_timestamp"][11:13]),
                "m": int(row["read_timestamp"][14:16]),
                "s": int(row["read_timestamp"][17:19]),
                "reg": to_frac(row["register_reading_kwh"]),
                "seq": i,
            })
        for ch in self.reads.values():
            for v in ch.values():
                v.sort(key=lambda r: (r["ts"], r["seq"]))

        rows = read_csv(os.path.join(self.dir, "demand_intervals.csv"))
        self.demand_interval_count = len(rows)
        self.demand = {}
        for row in rows:
            cid = row["customer_id"].strip()
            key = row["interval_start"].strip()
            self.demand.setdefault(cid, {}).setdefault(key, Fraction(0))
            self.demand[cid][key] += to_frac(row["demand_kw"])

    # ------------------------------------------------------------ civil time
    def extra_for(self, d):
        if d in self.fall_back:
            return 3600
        if d in self.spring_fwd:
            return -3600
        return 0

    def day_len(self, d):
        return 86400 + self.extra_for(d)

    def day_offset(self, d):
        got = self._off_cache.get(d)
        if got is not None:
            return got
        n = (d - PERIOD_START).days
        total = 0
        if n >= 0:
            for k in range(n):
                total += self.day_len(PERIOD_START + timedelta(days=k))
        else:
            for k in range(n, 0):
                total -= self.day_len(PERIOD_START + timedelta(days=k))
        self._off_cache[d] = total
        return total

    def intra(self, d, h, second):
        if d in self.fall_back:
            rep = self.fall_back[d]
            if second:
                return (rep + 1) * 3600
            if h > rep:
                return (h + 1) * 3600
            return h * 3600
        if d in self.spring_fwd:
            skip = self.spring_fwd[d]
            if h > skip:
                return (h - 1) * 3600
            return h * 3600
        return h * 3600

    def civ_read(self, r):
        # §3.12-style `T25:xx` sentinel, if it ever appears in a read, denotes the
        # second occurrence of the repeated fall-back hour.
        second = r["h"] >= 24
        return (self.day_offset(r["d"]) + self.intra(r["d"], r["h"] % 24, second)
                + r["m"] * 60 + r["s"])

    def slot_label(self, cls, d, h, second):
        if second:
            return "night" if cls in ("RES", "IND") else "weekend"
        if d in self.holidays:
            return "weekend"
        if d.weekday() >= 5:
            return "weekend"
        return WINDOWS[cls][h]

    # ---------------------------------------------------------------- tariffs
    def _is_order_row(self, r):
        return r["prec"] > 10 or r["sid"] in self.order_new_ids

    def rows_covering(self, rc, tou, d):
        key = (rc, tou, d)
        got = self._cover_cache.get(key)
        if got is None:
            got = [r for r in self.rows_by_key.get((rc, tou), ())
                   if r["from"] <= d and (r["until"] is None or d <= r["until"])]
            self._cover_cache[key] = got
        return got

    @staticmethod
    def best(rows):
        return max(rows, key=lambda r: (r["prec"], r["from"], r["sid"]))

    def frozen_row(self, rc, tou, gf_date):
        if gf_date is None:
            return None
        cands = [r for r in self.rows_covering(rc, tou, gf_date)
                 if not self._is_order_row(r)]
        if not cands:
            return None
        return self.best(cands)

    def freeze_active(self, cust, d):
        if not cust["gf_flag"]:
            return False
        if cust["gf_expires"] is not None and d >= cust["gf_expires"]:
            return False
        mig = cust.get("migration")
        if mig is not None and d >= mig:
            return False
        return True

    def class_at(self, cust, d):
        mig = cust.get("migration")
        if mig is not None and d >= mig:
            return cust["mig_class"]
        return cust["rate_class"]

    def rate_row(self, cust, d, tou):
        key = (id(cust), d, tou)
        got = self._row_cache.get(key)
        if got is not None:
            return got
        rc = self.class_at(cust, d)
        cands = self.rows_covering(rc, tou, d)
        row = None
        if self.freeze_active(cust, d):
            immune = [r for r in cands
                      if self._is_order_row(r) and self.order_new_ids.get(r["sid"], False)]
            if immune:
                row = self.best(immune)
            else:
                frozen = self.frozen_row(rc, tou, cust["gf_date"])
                if frozen is not None:
                    row = frozen
        if row is None:
            row = self.best(cands) if cands else None
        self._row_cache[key] = row
        return row

    # -------------------------------------------------------------- currency
    def rate_on(self, d):
        got = self._rate_cache.get(d)
        if got is not None:
            return got
        best = None
        for rd, val in self.rates:
            if rd <= d:
                best = val
            else:
                break
        if best is None and self.rates:
            best = self.rates[0][1]
        if best is None:
            best = 1
        self._rate_cache[d] = best
        return best

    # ------------------------------------------------------------ reads/§15
    def dedup_channel(self, cust, chan, reads):
        """§15.3 duplicate resolution; returns (kept, discarded_count)."""
        kept = []
        discarded = 0
        i = 0
        while i < len(reads):
            group = [reads[i]]
            j = i + 1
            while j < len(reads) and reads[j]["ts"] == reads[i]["ts"]:
                group.append(reads[j])
                j += 1
            if len(group) == 1:
                kept.append(group[0])
            else:
                if not kept:
                    pick = max(group, key=lambda r: (r["reg"], -r["seq"]))
                else:
                    prev = kept[-1]["reg"]
                    mx = MAX_REGISTER.get(cust["meter_class"], Fraction(0))
                    def dist(r):
                        return (r["reg"] - prev) if r["reg"] >= prev else (mx + ROLL_INCREMENT) - prev + r["reg"]
                    pick = max(group, key=lambda r: (dist(r), r["reg"], -r["seq"]))
                kept.append(pick)
                discarded += len(group) - 1
            i = j
        return kept, discarded

    def spread(self, per_slot, start, end, delta, win_start, win_end):
        """§4 linear interpolation of `delta` over civil seconds [start,end)."""
        if delta == 0 or end <= start:
            return
        s0 = start if start > win_start else win_start
        s1 = end if end < win_end else win_end
        if s1 <= s0:
            return
        total = end - start
        lo, hi = 0, len(self.slots)
        while lo < hi:                       # first slot with start >= s0
            mid = (lo + hi) // 2
            if self.slot_starts[mid] < s0:
                lo = mid + 1
            else:
                hi = mid
        for k in range(lo, len(self.slots)):
            d, h, second, ss = self.slots[k]
            if ss >= s1:
                break
            seg_end = ss + 3600
            ov = (seg_end if seg_end < s1 else s1) - (ss if ss > s0 else s0)
            if ov > 0:
                per_slot[k] = per_slot.get(k, Fraction(0)) + delta * Fraction(ov, total)

    def consumption(self, cust):
        """Returns (per_slot kWh dict, dq flags dict)."""
        per_slot = {}
        flags = {"missing_start": False, "missing_end": False,
                 "dupes": 0, "high_variance": 0}
        win_start = self.day_offset(cust["service_start"])
        win_end = self.day_offset(cust["service_end"]) + self.day_len(cust["service_end"])
        mx = MAX_REGISTER.get(cust["meter_class"], Fraction(0))
        for chan, raw in sorted(self.reads.get(cust["customer_id"], {}).items()):
            reads, discarded = self.dedup_channel(cust, chan, raw)
            flags["dupes"] += discarded
            if not reads:
                flags["missing_start"] = True
                flags["missing_end"] = True
                continue
            ch_ms = not any(r["d"] <= cust["service_start"] for r in reads)
            ch_me = not any(r["d"] >= cust["service_end"] for r in reads)
            if ch_ms:
                flags["missing_start"] = True
            if ch_me:
                flags["missing_end"] = True
            civs = [self.civ_read(r) for r in reads]
            pairs = []
            for a in range(len(reads) - 1):
                rb, ra = reads[a + 1]["reg"], reads[a]["reg"]
                delta = rb - ra if rb >= ra else (mx + ROLL_INCREMENT) - ra + rb
                pairs.append((a, delta, Fraction(delta, civs[a + 1] - civs[a])))
            # §15.2 high-variance flags (median of an even count is the mean)
            if pairs:
                rates = sorted(p[2] for p in pairs)
                n = len(rates)
                med = rates[n // 2] if n % 2 else (rates[n // 2 - 1] + rates[n // 2]) / 2
                flags["high_variance"] += sum(1 for p in pairs if p[2] > 20 * med)
            # §15.4 extrapolation across a missing boundary
            if ch_ms and pairs:
                rate = pairs[0][2]
                seg_end = civs[0]
                if seg_end > win_start:
                    self.spread(per_slot, win_start, seg_end,
                                rate * (seg_end - win_start), win_start, win_end)
            if ch_me and pairs:
                rate = pairs[-1][2]
                seg_start = civs[-1]
                if win_end > seg_start:
                    self.spread(per_slot, seg_start, win_end,
                                rate * (win_end - seg_start), win_start, win_end)
            # §4 inter-read gaps
            for a, delta, _rate in pairs:
                self.spread(per_slot, civs[a], civs[a + 1], delta, win_start, win_end)
        return per_slot, flags

    def ddc(self, cust):
        """§6 Declared Demand Component and its civil date."""
        best_val = None
        best_key = None
        best_date = None
        for key, val in sorted(self.demand.get(cust["customer_id"], {}).items()):
            d = parse_date(key)
            if not (cust["service_start"] <= d <= cust["service_end"]):
                continue
            if self.class_at(cust, d) == "RES":
                continue
            if self.holidays.get(d) == "off":
                continue
            if best_val is None or val > best_val or (val == best_val and key > best_key):
                best_val, best_key, best_date = val, key, d
        return best_val, best_date

    # ------------------------------------------------------------ settlement
    def build_customers(self):
        valid = {}
        for cid in self.customer_order:
            cust = self.customers[cid]
            prem = self.premises.get(cust["premise_code"])
            if prem is None:
                continue                                   # §15.1 orphan customer
            cust["premise"] = prem
            valid[cid] = cust
            move_in, move_out, mig = None, None, None
            migs = []
            for t in self.tickets:
                if t.get("customer_id") != cid:
                    continue
                eff = parse_date(t["effective_date"])
                et = t["event_type"]
                if et == "move_in":
                    move_in = eff if move_in is None else min(move_in, eff)
                elif et == "move_out":
                    move_out = eff if move_out is None else max(move_out, eff)
                elif et == "rate_class_migration" and t.get("new_rate_class"):
                    migs.append((eff, t["new_rate_class"]))
            if migs:
                migs.sort(key=lambda x: x[0])          # §9: at most one, earliest wins
                mig = migs[0][0]
                cust["mig_class"] = migs[0][1]
            cust["migrations"] = migs
            cust["migration"] = mig
            cust["service_start"] = max(PERIOD_START, move_in) if move_in else PERIOD_START
            cust["service_end"] = min(PERIOD_END, move_out) if move_out else PERIOD_END
            cust["nmb_start"] = self.nmb.get(cid, 0)
        self.valid = valid
        return valid

    def settle(self, cust):
        per_slot, flags = self.consumption(cust)
        # bucket into (label, rate)
        shares = {lab: {} for lab in LABELS}
        total = Fraction(0)
        for idx, kwh in per_slot.items():
            d, h, second, _s = self.slots[idx]
            cls = self.class_at(cust, d)
            lab = self.slot_label(cls, d, h, second)
            row = self.rate_row(cust, d, lab)
            rate = row["energy"] if row else 0
            shares[lab][rate] = shares[lab].get(rate, Fraction(0)) + kwh
            total += kwh

        # §7.3 net-metering draw
        bank = Fraction(cust["nmb_start"], 1000) if cust["nmb_start"] > 0 else Fraction(0)
        drawn = Fraction(0)
        for lab in LABELS:
            tot = sum(shares[lab].values())
            if bank > 0 and tot > 0:
                take = bank if bank < tot else tot
                factor = (tot - take) / tot
                for r in shares[lab]:
                    shares[lab][r] *= factor
                bank -= take
                drawn += take
        energy_charge = 0
        charged = Fraction(0)
        for lab in LABELS:
            val = sum((Fraction(r) * k for r, k in shares[lab].items()), Fraction(0))
            energy_charge += rhu(val)
            charged += sum(shares[lab].values(), Fraction(0))

        # §8 FAC on the post-offset kWh
        fac_rate = self.fac.get("%04d-%02d" % (PERIOD_START.year, PERIOD_START.month), 0)
        fac_mrcc = rhu(Fraction(fac_rate) * charged)

        # §6 demand charge (RES customers have no demand component, §6)
        ddc_val, ddc_date = self.ddc(cust)
        if ddc_val is None or ddc_val == 0 or self.class_at(cust, ddc_date) == "RES":
            demand_charge = 0
        else:
            row = self.rate_row(cust, ddc_date, STAR)
            demand_charge = rhu(ddc_val * Fraction(row["demand"] if row else 0))

        # customer charge, prorated per service day (§3.10/§9/§10)
        charge_sum = Fraction(0)
        for d in daterange(cust["service_start"], cust["service_end"]):
            row = self.rate_row(cust, d, STAR)
            charge_sum += Fraction(row["charge"] if row else 0)
        customer_charge = rhu(charge_sum / DAYS_IN_CURRENT_PERIOD)

        # §7.2 fiscal true-up
        remaining = (Fraction(cust["nmb_start"], 1000) if cust["nmb_start"] > 0 else Fraction(0)) - drawn
        payout, forfeit = 0, 0
        if remaining > 0:
            if self.class_at(cust, PERIOD_END) == "RES":
                payout = rhu(AVOIDED_COST_MRCC_PER_KWH * remaining)
            else:
                forfeit = rhu(remaining * 1000)

        cust["result"] = {
            "energy_kwh": rhu(total * 1000),
            "energy_charge_mrcc": energy_charge,
            "demand_charge_mrcc": demand_charge,
            "customer_charge_mrcc": customer_charge,
            "fac_mrcc": fac_mrcc,
            "payout": payout,
            "forfeit": forfeit,
            "carried": 0,
            "ddc": ddc_val if ddc_val is not None else Fraction(0),
            "base_mrcc": customer_charge + energy_charge + demand_charge + fac_mrcc - payout,
        }
        # pre-offset per-label buckets, for §11 assumed-prior proportions
        pre = {lab: Fraction(0) for lab in LABELS}
        for idx, kwh in per_slot.items():
            d, h, second, _s = self.slots[idx]
            lab = self.slot_label(self.class_at(cust, d), d, h, second)
            pre[lab] += kwh
        cust["result"]["label_kwh"] = pre
        cust["flags"] = flags

    def retro_lines(self, cust):
        out = []
        for order in self.orders:
            if order.get("scope") != "retroactive":
                continue
            adj = self.retro_adjustment(cust, order)
            if adj:
                out.append((order["order_id"], adj, parse_date(order["period_start"])))
        return out

    def retro_adjustment(self, cust, order):
        new_sid = (order.get("new_schedule_id") or "").strip()
        sup = self.row_by_sid.get((order.get("supersedes_schedule_id") or "").strip())
        if sup is not None:
            rc = sup["rate_class"]
        elif new_sid and new_sid in self.row_by_sid:
            rc = self.row_by_sid[new_sid]["rate_class"]
        else:
            return 0
        if cust["rate_class"] != rc:
            return 0
        if cust["gf_flag"] and not order.get("grandfather_immune"):
            return 0
        r_start = parse_date(order["period_start"])
        r_end = parse_date(order["period_end"])
        if r_end < FY_START or r_start > PERIOD_END:      # entirely outside FY2025
            return 0
        if not new_sid or new_sid not in self.row_by_sid:
            return 0
        dates = daterange(r_start, r_end) if r_start <= r_end else []
        if not dates:
            return 0
        n = len(dates)
        res = cust["result"]
        adj = 0
        for tou in list(LABELS) + [STAR]:
            old_sum = 0
            new_sum = 0
            for d in dates:
                cands = self.rows_covering(rc, tou, d)
                olds = [r for r in cands if r["sid"] != new_sid]
                ro = self.best(olds) if olds else None
                rn = self.best(cands) if cands else None
                if tou == STAR:
                    old_sum += ro["demand"] if ro else 0
                    new_sum += rn["demand"] if rn else 0
                else:
                    old_sum += ro["energy"] if ro else 0
                    new_sum += rn["energy"] if rn else 0
            old_rate = Fraction(old_sum, n)
            new_rate = Fraction(new_sum, n)
            if tou == STAR:
                adj += rhu(res["ddc"] * new_rate) - rhu(res["ddc"] * old_rate)
            else:
                kwh = res["label_kwh"][tou] * Fraction(n, DAYS_IN_CURRENT_PERIOD)
                adj += rhu(kwh * new_rate) - rhu(kwh * old_rate)
        return adj

    def bill(self, cust):
        res = cust["result"]
        lines = self.retro_lines(cust)
        retro_mrcc = sum(a for _o, a, _d in lines)
        if cust["currency"] == "FTU":
            base_ftuc = rhu(res["base_mrcc"] * 100 / Fraction(self.rate_on(PERIOD_START)))
            for _oid, adj, rstart in lines:
                base_ftuc += rhu(adj * 100 / Fraction(self.rate_on(rstart)))
            bill_ftuc, bill_mrcc = base_ftuc, 0
        else:
            bill_ftuc, bill_mrcc = 0, res["base_mrcc"] + retro_mrcc
        entry = {
            "customer_id": cust["customer_id"],
            "premise_code": cust["premise_code"],
            "energy_kwh": res["energy_kwh"],
            "energy_charge_mrcc": res["energy_charge_mrcc"],
            "demand_charge_mrcc": res["demand_charge_mrcc"],
            "customer_charge_mrcc": res["customer_charge_mrcc"],
            "fac_mrcc": res["fac_mrcc"],
            "net_metering": {
                "credit_kwh_carried_forward": res["carried"],
                "avoided_cost_payout_mrcc": res["payout"],
                "forfeited_kwh": res["forfeit"],
            },
            "retroactive_adjustment_mrcc": retro_mrcc,
            "bill_total_mrcc": bill_mrcc,
            "bill_total_ftuc": bill_ftuc,
        }
        return entry, lines


def sort_key(entry):
    return (int(entry["premise_code"][1:]), entry["customer_id"])


def build_rollup(entries, civil_hours):
    roll = {
        "period": {
            "start": PERIOD_START.isoformat(),
            "end": PERIOD_END.isoformat(),
            "civil_days": PERIOD_DAYS,
            "civil_hours": civil_hours,
        },
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
    return roll


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, sort_keys=True, indent=2)
        fh.write("\n")


def reconcile(data_dir, out_dir):
    snap = Snapshot(data_dir)
    civil_hours = len(snap.slots)
    valid = snap.build_customers()

    entries = {}
    grandfather_applied = []
    migrations = []
    retro_applied = []
    neg_nmb = 0
    miss_start = 0
    miss_end = 0
    dupes = 0
    high_var = 0

    for cid in snap.customer_order:
        cust = valid.get(cid)
        if cust is None:
            continue
        snap.settle(cust)
        entry, lines = snap.bill(cust)
        entries[cid] = entry
        for oid, adj, _d in lines:
            if adj != 0:
                retro_applied.append({"order_id": oid, "customer_id": cid,
                                      "adjustment_mrcc": adj})
        fl = cust["flags"]
        if fl["missing_start"]:
            miss_start += 1
        if fl["missing_end"]:
            miss_end += 1
        dupes += fl["dupes"]
        high_var += fl["high_variance"]
        if cust["nmb_start"] < 0:
            neg_nmb += 1
        if cust["gf_flag"]:
            split = None
            cands = []
            if cust["migration"] is not None:
                cands.append(cust["migration"])
            if cust["gf_expires"] is not None:
                cands.append(cust["gf_expires"])
            cands = [c for c in cands if PERIOD_START < c <= PERIOD_END]
            if cands:
                split = min(cands).isoformat()
            grandfather_applied.append({
                "customer_id": cid,
                "grandfather_date": cust["gf_date"].isoformat() if cust["gf_date"] else None,
                "expires_on": cust["gf_expires"].isoformat() if cust["gf_expires"] else None,
                "prorata_split_at": split,
            })

    for t in snap.tickets:
        cid = t.get("customer_id")
        if cid not in valid:
            continue                                   # §15.1 orphan transaction
        if t["event_type"] == "rate_class_migration" and t.get("new_rate_class"):
            migrations.append({"customer_id": cid,
                               "migration_date": t["effective_date"],
                               "from_class": valid[cid]["rate_class"],
                               "to_class": t["new_rate_class"]})

    ticket_counts = {"move_in": 0, "move_out": 0, "rate_class_migration": 0}
    for t in snap.tickets:
        if t.get("customer_id") in valid and t["event_type"] in ticket_counts:
            ticket_counts[t["event_type"]] += 1

    active = 0
    oop = 0
    for o in snap.orders:
        if o.get("scope") == "retroactive":
            active += 1
        else:
            if parse_date(o["effective_on"]) <= PERIOD_END:
                active += 1
            else:
                oop += 1

    fb_date = None
    fb_hours = 24
    in_period = [d for d in snap.fall_dates if PERIOD_START <= d <= PERIOD_END]
    if not in_period:
        in_period = [d for d in snap.spring_dates if PERIOD_START <= d <= PERIOD_END]
    if in_period:
        d = in_period[0]
        fb_date = d.isoformat()
        fb_hours = 24 + snap.extra_for(d) // 3600

    policy = {
        "grandfather_applied": sorted(grandfather_applied, key=lambda x: x["customer_id"]),
        "rate_class_migrations": sorted(migrations, key=lambda x: x["customer_id"]),
        "retroactive_orders_applied": sorted(retro_applied,
                                             key=lambda x: (x["order_id"], x["customer_id"])),
        "holiday_reclassifications": snap.holiday_list,
        "dst_cutover_applied": {"date": fb_date, "civil_hours_in_day": fb_hours},
    }
    quality = {
        "meter_read_count": snap.meter_read_count,
        "demand_interval_count": snap.demand_interval_count,
        "customers_with_negative_nmb_start": neg_nmb,
        "customers_with_missing_read_at_service_start": miss_start,
        "customers_with_missing_read_at_service_end": miss_end,
        "high_variance_reads_flagged": high_var,
        "service_tickets_by_type": ticket_counts,
        "regulator_orders_active_this_period": active,
        "regulator_orders_out_of_period_declared": oop,
        "duplicate_read_timestamps_flagged": dupes,
    }

    entry_list = list(entries.values())
    summary = build_rollup(entry_list, civil_hours)
    os.makedirs(out_dir, exist_ok=True)
    write_json(os.path.join(out_dir, "summary.json"), summary)
    write_json(os.path.join(out_dir, "policy_audit.json"), policy)
    write_json(os.path.join(out_dir, "data_quality.json"), quality)

    for cls, fname in CLASS_FILES:
        sub = [e for cid, e in entries.items() if valid[cid]["rate_class"] == cls]
        roll = build_rollup(sub, civil_hours)
        roll["customers"] = sorted(sub, key=sort_key)
        write_json(os.path.join(out_dir, fname), roll)
    for region, fname in REGION_FILES:
        sub = [e for cid, e in entries.items() if valid[cid]["premise"]["region"] == region]
        roll = build_rollup(sub, civil_hours)
        roll["customers"] = sorted(sub, key=sort_key)
        write_json(os.path.join(out_dir, fname), roll)
    return summary


def main(argv):
    if len(argv) == 3 and argv[1] == "--session":
        out_dir = argv[2]
        for line in sys.stdin:                      # one NDJSON command per line
            line = line.strip()
            if not line:
                continue
            cmd = json.loads(line)
            reconcile(cmd["data_dir"], out_dir)      # full recompute, no carried state
            sys.stdout.write('{"status":"ok","turn_id":' +
                             json.dumps(cmd["turn_id"]) + "}\n")
            sys.stdout.flush()
        return 0
    if len(argv) == 3:
        reconcile(argv[1], argv[2])
        return 0
    sys.stderr.write("usage: reconcile.py DATA_DIR OUT_DIR | reconcile.py --session OUT_DIR\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
