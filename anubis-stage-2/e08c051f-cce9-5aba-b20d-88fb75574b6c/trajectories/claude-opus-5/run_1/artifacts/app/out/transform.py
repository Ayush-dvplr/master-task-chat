#!/usr/bin/env python3
"""FY28 collateral-gated settlement ladder.

Usage: python3 transform.py <DATA_DIR> <OUT_DIR>
"""

import bisect
import configparser
import csv
import datetime
import json
import os
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from fractions import Fraction

SALES = "sales.csv"
REFUNDS = "refunds.tsv"
ADJUSTMENTS = "adjustments.jsonl"
LEGACY = "legacy.txt"
EVENT_FILES = [SALES, REFUNDS, ADJUSTMENTS, LEGACY]

SOURCE_COLUMNS = {
    SALES: ["event_id", "trade_ts", "counterparty_id", "sku", "warehouse",
            "quantity", "unit_price", "currency", "terminal"],
    REFUNDS: ["event_id", "trade_ts", "counterparty_id", "sku", "warehouse",
              "quantity", "refund_amount", "currency", "terminal",
              "sale_event_id"],
    ADJUSTMENTS: ["event_id", "trade_ts", "counterparty_id", "sku", "kind",
                  "amount_minor", "currency", "note"],
    LEGACY: ["event_id", "trade_ts", "counterparty_id", "sku", "warehouse",
             "kind", "quantity", "amount", "currency", "terminal", "memo"],
}

TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})$")
NUM_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")
INT_RE = re.compile(r"^[+-]?\d+$")

RECORD_KEYS = ["event_id", "settlement_date", "utc_instant", "fiscal_period",
               "counterparty_id", "segment", "region", "sku", "category",
               "kind", "quantity", "settled_usd_cents", "currency", "source",
               "channel_group", "warehouse"]


# --------------------------------------------------------------------------
# exact arithmetic helpers
# --------------------------------------------------------------------------

def quantize(value, mode):
    """Quantize an exact Fraction to a whole unit under the policy mode."""
    neg = value < 0
    a = -value if neg else value
    whole, rem = divmod(a.numerator, a.denominator)
    q = a.denominator
    twice = 2 * rem
    if mode == "half_up":
        up = twice >= q
    elif mode == "half_down":
        up = twice > q
    elif mode == "half_even":
        up = twice > q or (twice == q and whole % 2 == 1)
    elif mode == "down":
        up = False
    elif mode == "up":
        up = rem != 0
    elif mode == "floor":
        up = neg and rem != 0
    elif mode == "ceiling":
        up = (not neg) and rem != 0
    else:
        raise ValueError("unsupported rounding mode: %r" % mode)
    if up:
        whole += 1
    return -whole if neg else whole


def to_fraction(text):
    """Exact Fraction from a decimal literal, or None when unparsable."""
    if not isinstance(text, str) or not NUM_RE.match(text):
        return None
    try:
        return Fraction(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def parse_strict_int(text):
    """Integer written with ASCII digits and nothing else."""
    if not isinstance(text, str) or not text:
        return None
    if not text.isascii() or not text.isdigit():
        return None
    return int(text)


# --------------------------------------------------------------------------
# input loading
# --------------------------------------------------------------------------

def read_table(path, delimiter=",", encoding="utf-8"):
    with open(path, newline="", encoding=encoding) as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        try:
            header = [h.strip() for h in next(reader)]
        except StopIteration:
            return []
        out = []
        for row in reader:
            out.append({header[i]: (row[i] if i < len(row) else "")
                        for i in range(len(header))})
        return out


class Policy:
    def __init__(self, path):
        cp = configparser.ConfigParser()
        with open(path, encoding="utf-8") as fh:
            cp.read_file(fh)
        self.opening_rate_date = cp.get("ladder", "opening_rate_date").strip()
        self.floors = {}
        for key, value in cp.items("collateral"):
            m = re.match(r"^floor_(.+)_usd_cents$", key.strip())
            if m:
                self.floors[m.group(1).strip().lower()] = int(value.strip())
        self.money_mode = cp.get("rounding", "mode").strip().lower()
        self.mass_mode = self.money_mode
        self.grams_per_kilogram = Fraction(
            Decimal(cp.get("mass", "grams_per_kilogram").strip()))
        self.unassigned_period = cp.get("labels", "unassigned_period").strip()
        self.adjustment_channel_group = cp.get(
            "labels", "adjustment_channel_group").strip().lower()


class Reference:
    def __init__(self, data_dir):
        self.counterparties = self._counterparties(
            os.path.join(data_dir, "counterparties.csv"))
        self._regions(os.path.join(data_dir, "regions.csv"))
        self._inventory(os.path.join(data_dir, "inventory.csv"))
        self._channels(os.path.join(data_dir, "channels.csv"))
        self._catalog(os.path.join(data_dir, "product_catalog.csv"))
        self._fx(os.path.join(data_dir, "fx_rates.csv"))
        self._fiscal(os.path.join(data_dir, "fiscal_calendar.json"))

    @staticmethod
    def _counterparties(path):
        best = {}
        for idx, row in enumerate(read_table(path)):
            cid = row["counterparty_id"].strip()
            rank = (row["updated_at"].strip(), idx)
            if cid in best and best[cid][0] >= rank:
                continue
            best[cid] = (rank, {
                "segment": row["segment"].strip().lower(),
                "postal_code": row["postal_code"].strip(),
                "opening_balance_minor": row["opening_balance_minor"].strip(),
                "opening_currency": row["opening_currency"].strip().upper(),
            })
        return {cid: payload for cid, (_, payload) in best.items()}

    def _regions(self, path):
        self.prefix_rows = {}
        self.parent_of = {}
        for row in read_table(path):
            prefix = row["postal_prefix"].strip()
            region = row["region"].strip().lower()
            self.prefix_rows[prefix] = {
                "region": region,
                "default_currency": row["default_currency"].strip().upper(),
            }
            self.parent_of[region] = row["parent_region"].strip().lower()
        self._top_cache = {}
        self.top_regions = sorted(r for r, p in self.parent_of.items() if not p)

    def top_region(self, region):
        if region in self._top_cache:
            return self._top_cache[region]
        chain = []
        cur = region
        while True:
            if cur not in self.parent_of or cur in chain:
                top = None
                break
            chain.append(cur)
            parent = self.parent_of[cur]
            if not parent:
                top = cur
                break
            cur = parent
        for name in chain:
            self._top_cache[name] = top
        self._top_cache[region] = top
        return top

    def _inventory(self, path):
        self.warehouses = {}
        self.stock = {}
        self.inventory_rows = []
        for row in read_table(path):
            wh = row["warehouse"].strip()
            sku = row["sku"].strip()
            on_hand = int(row["on_hand_grams"].strip())
            reorder = int(row["reorder_point_grams"].strip())
            if wh not in self.warehouses:
                self.warehouses[wh] = (row["postal_code"].strip(),
                                       int(row["tz_offset_minutes"].strip()))
            agg = self.stock.setdefault(sku, [0, 0])
            agg[0] += on_hand
            agg[1] += reorder
            self.inventory_rows.append((sku, on_hand))

    def _channels(self, path):
        self.channels = {}
        for row in read_table(path):
            self.channels[row["terminal"].strip().lower()] = \
                row["channel_group"].strip().lower()

    def _catalog(self, path):
        self.catalog = {}
        for row in read_table(path):
            self.catalog[row["sku"].strip()] = {
                "category": row["category"].strip().lower(),
                "unit_mass_kg": to_fraction(row["unit_mass_kg"].strip()),
            }

    def _fx(self, path):
        table = defaultdict(dict)
        for row in read_table(path):
            cur = row["currency"].strip().upper()
            table[cur][row["rate_date"].strip()] = \
                to_fraction(row["usd_rate"].strip())
        self.fx = {}
        for cur, by_date in table.items():
            dates = sorted(by_date)
            self.fx[cur] = (dates, [by_date[d] for d in dates])

    def rate_for(self, currency, date):
        """Return (rate, rate_date) with carry-forward, or (None, None)."""
        entry = self.fx.get(currency)
        if not entry:
            return None, None
        dates, rates = entry
        pos = bisect.bisect_right(dates, date) - 1
        if pos < 0 or rates[pos] is None:
            return None, None
        return rates[pos], dates[pos]

    def _fiscal(self, path):
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.periods = sorted(
            (p["start"].strip(), p["end"].strip(), p["period"].strip())
            for p in doc.get("periods", []))
        self._period_starts = [p[0] for p in self.periods]

    def fiscal_period(self, date, unassigned):
        pos = bisect.bisect_right(self._period_starts, date) - 1
        if pos >= 0:
            start, end, period = self.periods[pos]
            if start <= date <= end:
                return period
        return unassigned


def load_corrections(path):
    """Return ((target, field) -> value, every target a correction names)."""
    chosen = {}
    targets = []
    if not os.path.exists(path):
        return {}, targets
    with open(path, encoding="utf-8", errors="replace") as fh:
        for idx, line in enumerate(fh):
            tokens = line.split()
            if len(tokens) < 3 or tokens[2] != "correction":
                continue
            target = field = value = None
            for token in tokens[3:]:
                if token.startswith("target=") and target is None:
                    target = token[len("target="):].strip()
                elif token.startswith("field=") and field is None:
                    field = token[len("field="):].strip()
                elif token.startswith("value=") and value is None:
                    value = line.split("value=", 1)[1].strip()
            if target is None or field is None or value is None:
                continue
            targets.append(target)
            key = (target, field)
            rank = (tokens[0].strip(), idx)
            if key in chosen and chosen[key][0] >= rank:
                continue
            chosen[key] = (rank, value)
    return {k: v for k, (_, v) in chosen.items()}, targets


# --------------------------------------------------------------------------
# raw event rows
# --------------------------------------------------------------------------

def load_raw_events(data_dir):
    """Return (rows, pre_skipped, all_event_ids, sales_event_ids)."""
    rows = []
    pre_skipped = Counter()
    all_ids = set()
    sales_ids = set()

    path = os.path.join(data_dir, SALES)
    if os.path.exists(path):
        for row in read_table(path):
            fields = {c: row.get(c, "").strip() for c in SOURCE_COLUMNS[SALES]}
            sales_ids.add(fields["event_id"])
            all_ids.add(fields["event_id"])
            rows.append({"source": SALES, "fields": fields})

    path = os.path.join(data_dir, REFUNDS)
    if os.path.exists(path):
        for row in read_table(path, delimiter="\t"):
            fields = {c: row.get(c, "").strip()
                      for c in SOURCE_COLUMNS[REFUNDS]}
            all_ids.add(fields["event_id"])
            rows.append({"source": REFUNDS, "fields": fields})

    path = os.path.join(data_dir, ADJUSTMENTS)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    pre_skipped[ADJUSTMENTS] += 1
                    continue
                if not isinstance(obj, dict):
                    pre_skipped[ADJUSTMENTS] += 1
                    continue
                fields = {}
                for col in SOURCE_COLUMNS[ADJUSTMENTS]:
                    val = obj.get(col, "")
                    fields[col] = val.strip() if isinstance(val, str) else val
                eid = fields["event_id"]
                all_ids.add(eid if isinstance(eid, str) else str(eid))
                rows.append({"source": ADJUSTMENTS, "fields": fields})

    path = os.path.join(data_dir, LEGACY)
    if os.path.exists(path):
        with open(path, encoding="latin-1") as fh:
            for line in fh:
                line = line.rstrip("\n").rstrip("\r")
                stripped = line.strip()
                if not stripped or stripped[0] == "#":
                    continue
                parts = line.split("|")
                if len(parts) != 11:
                    pre_skipped[LEGACY] += 1
                    all_ids.add(parts[0].strip())
                    continue
                fields = {c: parts[i].strip()
                          for i, c in enumerate(SOURCE_COLUMNS[LEGACY])}
                all_ids.add(fields["event_id"])
                rows.append({"source": LEGACY, "fields": fields})

    return rows, pre_skipped, all_ids, sales_ids


def apply_corrections(rows, corrections):
    corrected = set()
    if not corrections:
        return corrected
    for row in rows:
        eid = row["fields"]["event_id"]
        eid = eid.strip() if isinstance(eid, str) else str(eid)
        for col in SOURCE_COLUMNS[row["source"]]:
            if col == "event_id":
                continue
            key = (eid, col)
            if key in corrections:
                row["fields"][col] = corrections[key]
                corrected.add(eid)
    return corrected


# --------------------------------------------------------------------------
# settling one event
# --------------------------------------------------------------------------

LEGACY_SIGNS = {"sale": 1, "fee": 1, "refund": -1, "credit": -1}


def parse_instant(text, utc_suffix):
    if not isinstance(text, str):
        return None
    text = text.strip()
    if utc_suffix:
        if not text.endswith("Z"):
            return None
        text = text[:-1]
    m = TS_RE.match(text)
    if not m:
        return None
    try:
        return datetime.datetime(*(int(g) for g in m.groups()))
    except ValueError:
        return None


def text_of(value):
    return value.strip() if isinstance(value, str) else ""


def settle(row, ref, policy, sales_ids):
    """Return ('ok', (record, meta)), ('orphan', event_id) or ('skip', None)."""
    src = row["source"]
    f = row["fields"]
    eid = f["event_id"]
    eid = eid.strip() if isinstance(eid, str) else str(eid)

    if src == REFUNDS:
        link = text_of(f["sale_event_id"])
        if link and link not in sales_ids:
            return "orphan", eid

    if src == SALES:
        kind = "sale"
    elif src == REFUNDS:
        kind = "refund"
    else:
        kind = text_of(f["kind"]).lower()
        if src == ADJUSTMENTS:
            if kind not in ("fee", "credit"):
                return "skip", None
        elif kind not in LEGACY_SIGNS:
            return "skip", None

    cid = text_of(f["counterparty_id"])
    party = ref.counterparties.get(cid)
    if party is None:
        return "skip", None

    if src == ADJUSTMENTS:
        warehouse = None
        postal = party["postal_code"]
        tz_offset = 0
    else:
        warehouse = text_of(f["warehouse"])
        site = ref.warehouses.get(warehouse)
        if site is None:
            return "skip", None
        postal, tz_offset = site

    prefix_row = ref.prefix_rows.get(postal.split("-", 1)[0].strip())
    if prefix_row is None:
        return "skip", None
    region = ref.top_region(prefix_row["region"])
    if region is None:
        return "skip", None

    currency = text_of(f["currency"]).upper()
    if not currency:
        currency = prefix_row["default_currency"]
    if not currency:
        return "skip", None

    local = parse_instant(f["trade_ts"], src == ADJUSTMENTS)
    if local is None:
        return "skip", None
    utc = local - datetime.timedelta(minutes=tz_offset)
    settlement_date = utc.date().isoformat()

    rate, rate_date = ref.rate_for(currency, settlement_date)
    if rate is None:
        return "skip", None

    if src == ADJUSTMENTS:
        channel_group = policy.adjustment_channel_group
    else:
        channel_group = ref.channels.get(text_of(f["terminal"]).lower())
        if channel_group is None:
            return "skip", None

    sku = text_of(f["sku"])
    product = ref.catalog.get(sku)
    if product is None:
        return "skip", None

    if src == ADJUSTMENTS:
        quantity = 0
    else:
        quantity = parse_strict_int(text_of(f["quantity"]))
        if quantity is None:
            return "skip", None

    if src == SALES:
        price = to_fraction(text_of(f["unit_price"]))
        if price is None:
            return "skip", None
        gross = price * quantity
    elif src == REFUNDS:
        amount = to_fraction(text_of(f["refund_amount"]))
        if amount is None:
            return "skip", None
        gross = -abs(amount)
    elif src == ADJUSTMENTS:
        minor = f["amount_minor"]
        if isinstance(minor, bool):
            return "skip", None
        if isinstance(minor, str):
            if not INT_RE.match(minor.strip()):
                return "skip", None
            minor = int(minor.strip())
        elif not isinstance(minor, int):
            return "skip", None
        gross = Fraction(minor, 100)
    else:
        amount = to_fraction(text_of(f["amount"]))
        if amount is None:
            return "skip", None
        gross = LEGACY_SIGNS[kind] * abs(amount)

    money = gross * rate * 100
    record = {
        "event_id": eid,
        "settlement_date": settlement_date,
        "utc_instant": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fiscal_period": ref.fiscal_period(settlement_date,
                                           policy.unassigned_period),
        "counterparty_id": cid,
        "segment": party["segment"],
        "region": region,
        "sku": sku,
        "category": product["category"],
        "kind": kind,
        "quantity": quantity,
        "settled_usd_cents": quantize(money, policy.money_mode),
        "currency": currency,
        "source": src,
        "channel_group": channel_group,
        "warehouse": warehouse,
    }
    meta = {
        "carry_forward": rate_date != settlement_date,
        "day_shift": settlement_date != local.date().isoformat(),
        "half_cent": money.denominator == 2,
        "link": text_of(f["sale_event_id"]) if src == REFUNDS else "",
    }
    return "ok", (record, meta)


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------

def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, sort_keys=True, indent=2)
        fh.write("\n")


def net_units_of(record):
    if record["kind"] == "sale":
        return record["quantity"]
    if record["kind"] == "refund":
        return -record["quantity"]
    return 0


def run(data_dir, out_dir):
    policy = Policy(os.path.join(data_dir, "policy.ini"))
    ref = Reference(data_dir)

    corrections, correction_targets = load_corrections(
        os.path.join(data_dir, "corrections.log"))
    rows, skipped_by_source, all_ids, sales_ids = load_raw_events(data_dir)
    corrected_events = apply_corrections(rows, corrections)
    unmatched_targets = sorted({t for t in correction_targets
                                if t not in all_ids})

    candidates = []
    orphan_ids = []
    malformed_sales_ids = set()
    for row in rows:
        status, payload = settle(row, ref, policy, sales_ids)
        if status == "ok":
            candidates.append((row["source"], payload[0], payload[1]))
        elif status == "orphan":
            orphan_ids.append(payload)
        else:
            skipped_by_source[row["source"]] += 1
            if row["source"] == SALES:
                malformed_sales_ids.add(row["fields"]["event_id"])

    # ---- the collateral ladder -------------------------------------------
    opening = {}
    underwater = 0
    for cid, party in ref.counterparties.items():
        rate, _ = ref.rate_for(party["opening_currency"],
                               policy.opening_rate_date)
        minor = party["opening_balance_minor"]
        if rate is None or not INT_RE.match(minor):
            balance = 0
        else:
            balance = quantize(Fraction(int(minor), 100) * rate * 100,
                               policy.money_mode)
        opening[cid] = balance
        floor = policy.floors.get(party["segment"])
        if floor is not None and balance < floor:
            underwater += 1

    by_party = defaultdict(list)
    for item in candidates:
        by_party[item[1]["counterparty_id"]].append(item)

    balances = dict(opening)
    accepted = []
    blocked = []
    for cid, items in by_party.items():
        items.sort(key=lambda it: (it[1]["utc_instant"], it[1]["event_id"]))
        floor = policy.floors.get(ref.counterparties[cid]["segment"])
        balance = balances[cid]
        for item in items:
            settled = item[1]["settled_usd_cents"]
            if settled >= 0:
                balance += settled
                accepted.append(item)
            elif floor is None or balance + settled >= floor:
                balance += settled
                accepted.append(item)
            else:
                blocked.append(item)
        balances[cid] = balance

    ladder_closing = sum(balances.values())

    # ---- aggregates -------------------------------------------------------
    accepted.sort(key=lambda it: it[1]["event_id"])
    records = [item[1] for item in accepted]

    breakdowns = {key: Counter() for key in
                  ("region", "segment", "kind", "category", "channel_group",
                   "fiscal_period", "source")}
    records_by_source = Counter()
    total_cents = 0
    net_units = 0
    for rec in records:
        cents = rec["settled_usd_cents"]
        total_cents += cents
        net_units += net_units_of(rec)
        for key, counter in breakdowns.items():
            counter[rec[key]] += cents
        records_by_source[rec["source"]] += 1

    blocked_by_source = Counter(item[0] for item in blocked)
    blocked_records = [item[1] for item in blocked]

    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "normalized.jsonl"), "w",
              encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps({k: rec[k] for k in RECORD_KEYS},
                                sort_keys=True, separators=(",", ":")))
            fh.write("\n")

    skipped_count = sum(skipped_by_source[s] for s in EVENT_FILES)
    summary = {
        "event_count": len(records),
        "skipped_count": skipped_count,
        "blocked_count": len(blocked_records),
        "orphan_refund_count": len(orphan_ids),
        "total_usd_cents": total_cents,
        "net_units": net_units,
        "ladder_closing_usd_cents": ladder_closing,
        "by_region": dict(breakdowns["region"]),
        "by_segment": dict(breakdowns["segment"]),
        "by_kind": dict(breakdowns["kind"]),
        "by_category": dict(breakdowns["category"]),
        "by_channel_group": dict(breakdowns["channel_group"]),
        "by_fiscal_period": dict(breakdowns["fiscal_period"]),
        "by_source": dict(breakdowns["source"]),
    }
    write_json(os.path.join(out_dir, "summary.json"), summary)

    present_event_files = [s for s in EVENT_FILES
                           if os.path.exists(os.path.join(data_dir, s))]
    data_quality = {
        "input_files": sorted(name for name in os.listdir(data_dir)
                              if os.path.isfile(os.path.join(data_dir, name))),
        "records_by_source": dict(records_by_source),
        "skipped_by_source": {s: skipped_by_source[s]
                              for s in present_event_files},
        "blocked_by_source": {s: blocked_by_source[s]
                              for s in present_event_files},
        "skipped_count": skipped_count,
        "blocked_count": len(blocked_records),
        "orphan_refund_count": len(orphan_ids),
        "blocked_event_ids": sorted({r["event_id"] for r in blocked_records}),
        "orphan_refund_event_ids": sorted(set(orphan_ids)),
        "unmatched_correction_targets": unmatched_targets,
    }
    write_json(os.path.join(out_dir, "data_quality.json"), data_quality)

    per_sku = defaultdict(lambda: [0, 0, 0])
    for rec in records:
        agg = per_sku[rec["sku"]]
        agg[0] += 1
        agg[1] += rec["settled_usd_cents"]
        agg[2] += net_units_of(rec)
    products = []
    for sku in sorted(ref.catalog):
        info = ref.catalog[sku]
        count, cents, units = per_sku.get(sku, [0, 0, 0])
        stock = ref.stock.get(sku, [0, 0])
        mass = info["unit_mass_kg"]
        net_mass = 0 if mass is None else quantize(
            Fraction(units) * mass * policy.grams_per_kilogram,
            policy.mass_mode)
        products.append({
            "sku": sku,
            "category": info["category"],
            "event_count": count,
            "total_usd_cents": cents,
            "net_units": units,
            "on_hand_grams": stock[0],
            "reorder_point_grams": stock[1],
            "net_mass_grams": net_mass,
        })
    write_json(os.path.join(out_dir, "product_summary.json"),
               {"products": products})

    def write_buckets(field, names, prefix, extra=None):
        buckets = {name: {
            field: name,
            "event_count": 0,
            "total_usd_cents": 0,
            "net_units": 0,
            "blocked_count": 0,
            "counterparties": set(),
            "by_kind": Counter(),
            "by_category": Counter(),
        } for name in names}
        for rec in records:
            bucket = buckets.get(rec[field])
            if bucket is None:
                continue
            cents = rec["settled_usd_cents"]
            bucket["event_count"] += 1
            bucket["total_usd_cents"] += cents
            bucket["net_units"] += net_units_of(rec)
            bucket["counterparties"].add(rec["counterparty_id"])
            bucket["by_kind"][rec["kind"]] += cents
            bucket["by_category"][rec["category"]] += cents
        for rec in blocked_records:
            bucket = buckets.get(rec[field])
            if bucket is not None:
                bucket["blocked_count"] += 1
        for name in names:
            bucket = buckets[name]
            payload = dict(bucket)
            payload["counterparties"] = sorted(bucket["counterparties"])
            payload["by_kind"] = dict(bucket["by_kind"])
            payload["by_category"] = dict(bucket["by_category"])
            if extra:
                payload.update(extra(name))
            write_json(os.path.join(out_dir, "%s%s.json" % (prefix, name)),
                       payload)

    write_buckets("region", ref.top_regions, "region_")
    write_buckets("segment", sorted(policy.floors), "segment_",
                  lambda name: {"collateral_floor_usd_cents":
                                policy.floors[name]})

    closing = {
        "blocked_value_usd_cents": sum(r["settled_usd_cents"]
                                       for r in blocked_records),
        "blocked_counterparties": len({r["counterparty_id"]
                                       for r in blocked_records}),
        "carry_forward_rate_events": sum(1 for it in accepted
                                         if it[2]["carry_forward"]),
        "day_shift_events": sum(1 for it in accepted if it[2]["day_shift"]),
        "corrected_events": len(corrected_events),
        "half_cent_events": sum(1 for it in accepted if it[2]["half_cent"]),
        "underwater_counterparties": underwater,
        "uncatalogued_stock_grams": sum(grams for sku, grams
                                        in ref.inventory_rows
                                        if sku not in ref.catalog),
        "stale_link_refunds": sum(1 for it in accepted
                                  if it[0] == REFUNDS and it[2]["link"]
                                  and it[2]["link"] in malformed_sales_ids),
    }
    return summary, data_quality, closing


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py <DATA_DIR> <OUT_DIR>\n")
        return 2
    summary, data_quality, closing = run(argv[1], argv[2])
    print(json.dumps({"summary": summary, "closing_report": closing},
                     sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
