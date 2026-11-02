#!/usr/bin/env python3
"""Derive the season reports of a road-salt allocation extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from fractions import Fraction

UNIT_KG = {
    "short_ton": Fraction("907.18474"),
    "metric_tonne": Fraction(1000),
    "long_ton": Fraction("1016.0469088"),
}
UNIT_NAMES = ("short_ton", "metric_tonne", "long_ton")
ROUNDINGS = ("half_up", "down", "up")
REGIONS = ("North", "South", "West", "East")
SEGMENTS = ("commercial", "public")

PARAM_DEFAULTS = {
    "public_weight": 2,
    "commercial_weight": 1,
    "allocation_unit_kg": 500,
    "tie_break": "lowest_customer_id",
    "deficit_threshold": "0.50",
    "bonus_composition": "additive",
    "review_floor": "0.40",
    "review_round_limit": 1,
}
PARAM_NAMES = tuple(sorted(PARAM_DEFAULTS))
INTEGER_PARAMS = ("public_weight", "commercial_weight", "allocation_unit_kg",
                  "review_round_limit")

# The joining tests allocation_policy.md admits for a review round.
REVIEW_TESTS = (
    "B_lt", "B_le", "B_lt_floor", "B_lt_ceil",
    "C_lt", "C_le", "C_lt_floor", "C_lt_ceil",
    "P_lt",
    "K_lt", "K_le", "K_lt_floor_prod",
    "D_lt",
    "AW_lt",
)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def parse_instant(text):
    return datetime.fromisoformat(text.strip().replace("Z", "+00:00"))


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def read_json(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def read_jsonl(path):
    out = []
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def tonnes_to_kg(text):
    return int(Decimal(str(text).strip()) * 1000)


def floor_div(frac):
    return frac.numerator // frac.denominator


def ceil_frac(frac):
    return -((-frac.numerator) // frac.denominator)


def round_kg(value, rounding):
    if rounding == "down":
        return value.numerator // value.denominator
    if rounding == "up":
        whole = value.numerator // value.denominator
        return whole if value.denominator == 1 else whole + 1
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def credited_kg(quantity, settings):
    unit, moisture, rounding = settings
    return round_kg(quantity * UNIT_KG[unit] * Fraction(100 - moisture, 100), rounding)


def level_text(level):
    if level is None:
        return None
    if level.denominator == 1:
        return str(level.numerator)
    return "%d/%d" % (level.numerator, level.denominator)


def ratio_text(numerator, denominator):
    """delivered / ordered, half up to four decimals, as a fixed string."""
    scaled = Fraction(numerator, denominator) * 10000
    whole = (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)
    sign = "-" if whole < 0 else ""
    whole = abs(whole)
    return "%s%d.%04d" % (sign, whole // 10000, whole % 10000)


# --------------------------------------------------------------------------
# the extract
# --------------------------------------------------------------------------

class Extract(object):
    def __init__(self, data_dir):
        self.dir = data_dir
        self._load_time()
        self._load_depots()
        self._load_customers()
        self._load_identity()
        self._load_orders()
        self._load_receipts()
        self._load_parameters()
        self.journal = read_jsonl(self._path("rationing_journal_2024-25.jsonl"))

    def _path(self, name):
        return os.path.join(self.dir, name)

    # -- time ------------------------------------------------------------
    def _load_time(self):
        periods = read_json(self._path("cooperative_time.json"))["periods"]
        self.periods = sorted((p["from_local"], p["utc_offset"]) for p in periods)
        rows = read_csv(self._path("season_calendar.csv"))
        self.week_ids = [r["week_id"].strip() for r in rows]
        self.week_opens = [self.local_instant(r["opens_at"]) for r in rows]
        self.week_closes = [self.local_instant(r["closes_at"]) for r in rows]
        self.season_start = self.week_opens[0]
        self.season_end = self.week_closes[-1]

    def local_instant(self, wall):
        wall = wall.strip()
        offset = self.periods[0][1]
        for from_local, utc_offset in self.periods:
            if from_local <= wall:
                offset = utc_offset
        return datetime.fromisoformat(wall.replace(" ", "T") + offset)

    def week_of(self, instant):
        """Index of the week an instant belongs to, or None."""
        if instant is None or instant <= self.season_start or instant > self.season_end:
            return None
        lo, hi = 0, len(self.week_closes) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if instant <= self.week_closes[mid]:
                hi = mid
            else:
                lo = mid + 1
        return lo

    # -- depots ----------------------------------------------------------
    def _load_depots(self):
        root = ET.parse(self._path("depots.xml")).getroot()
        self.depots = {}
        for node in root.findall("depot"):
            code = node.get("code")
            self.depots[code] = {
                "code": code,
                "region": node.get("region"),
                "opening_kg": int(node.findtext("opening_stock_kg").strip()),
            }
        self.depot_codes = sorted(self.depots)
        self.critical_routes = set()
        for routes in root.findall("routes"):
            for route in routes.findall("route"):
                if route.get("critical") == "yes":
                    self.critical_routes.add(route.get("code"))

    # -- customers -------------------------------------------------------
    def _load_customers(self):
        self.contracts = {}
        for row in read_csv(self._path("contracts.csv")):
            cid = row["customer_id"].strip()
            self.contracts[cid] = {
                "customer_id": cid,
                "segment": row["segment"].strip(),
                "contract_min_kg": tonnes_to_kg(row["contract_min_t"]),
                "route_code": row["route_code"].strip(),
            }
        self.crm_rows = {}
        for row in read_json(self._path("crm_accounts.json"))["accounts"]:
            cid = row["customer_id"].strip()
            self.crm_rows.setdefault(cid, []).append(
                (parse_instant(row["updated_at"]), int(row["revision"]), row))
        for cid in self.crm_rows:
            self.crm_rows[cid].sort(key=lambda item: (item[0], item[1]))
        self.service_areas = {}
        for row in read_json(self._path("service_areas.json"))["assignments"]:
            cid = row["customer_id"].strip()
            self.service_areas.setdefault(cid, []).append(
                (parse_instant(row["effective_from"]), row["depot"].strip()))
        for cid in self.service_areas:
            self.service_areas[cid].sort(key=lambda item: item[0])

    def segment_of(self, customer_id):
        return self.contracts[customer_id]["segment"]

    def serves_critical_route(self, customer_id, instant):
        rows = self.crm_rows.get(customer_id)
        if not rows:
            return False
        in_force = None
        for updated_at, _revision, row in rows:
            if updated_at <= instant:
                in_force = row
            else:
                break
        if in_force is None:
            return False
        if in_force["route_source"] == "crm":
            return bool(in_force["critical_route"])
        contract = self.contracts.get(customer_id)
        if contract is None:
            return False
        return contract["route_code"] in self.critical_routes

    def depot_of(self, customer_id, instant):
        entries = self.service_areas.get(customer_id)
        if not entries:
            return None
        depot = None
        for effective_from, code in entries:
            if effective_from <= instant:
                depot = code
            else:
                break
        return depot

    # -- identity --------------------------------------------------------
    def _load_identity(self):
        self.identity_events = []
        for row in read_csv(self._path("identity_events.csv")):
            self.identity_events.append({
                "event_id": row["event_id"].strip(),
                "instant": parse_instant(row["effective_at"]),
                "kind": row["kind"].strip(),
                "code": row["code"].strip().upper(),
                "target": row["target"].strip().upper(),
            })
        self.identity_events.sort(key=lambda e: (e["instant"], e["event_id"]))
        self.alias_events = [e for e in self.identity_events if e["kind"] == "alias"]
        self.merge_events = [e for e in self.identity_events if e["kind"] == "merge"]
        self.status_events = [e for e in self.identity_events
                              if e["kind"] in ("retire", "reactivate")]

    def merge_target(self, customer_id, instant):
        """Follow every merge in force at an instant."""
        current = customer_id
        seen = {current}
        while True:
            nxt = None
            for event in self.merge_events:
                if event["instant"] <= instant and event["code"] == current:
                    nxt = event["target"]
            if nxt is None or nxt in seen:
                return current
            current = nxt
            seen.add(current)

    def resolve_reference(self, reference, instant):
        key = reference.strip().upper()
        base = None
        if key in self.contracts:
            base = key
        else:
            for event in self.alias_events:
                if event["instant"] <= instant and event["code"] == key:
                    base = event["target"]
            if base is not None and base not in self.contracts:
                base = None
        if base is None:
            return None
        return self.merge_target(base, instant)

    def is_retired(self, customer_id, instant):
        state = False
        for event in self.status_events:
            if event["instant"] <= instant and event["code"] == customer_id:
                state = event["kind"] == "retire"
        return state

    # -- orders ----------------------------------------------------------
    def _load_orders(self):
        self.order_classes = {}
        for row in read_csv(self._path("order_classes.csv")):
            self.order_classes[row["class_code"].strip()] = {
                "offer_weeks": int(row["offer_weeks"]),
                "entitlement_basis": row["entitlement_basis"].strip(),
            }
        self.orders = []
        for row in read_csv(self._path("orders.csv")):
            self.orders.append({
                "order_id": row["order_id"].strip(),
                "po_number": row["po_number"].strip(),
                "customer_ref": row["customer_ref"],
                "placed_at": parse_instant(row["placed_at"]),
                "quantity_kg": tonnes_to_kg(row["quantity_t"]),
                "order_class": row["order_class"].strip(),
            })
        self.orders.sort(key=lambda o: o["order_id"])
        self.orders_by_id = {o["order_id"]: o for o in self.orders}
        self.board = read_csv(self._path("dispatch_board_final.csv"))
        self.amendments = read_jsonl(self._path("order_amendments.jsonl"))

    # -- receipts --------------------------------------------------------
    def _load_receipts(self):
        in_force = {}
        order = []
        for row in read_csv(self._path("receipts.csv")):
            rid = row["receipt_id"].strip()
            if rid not in in_force:
                order.append(rid)
            in_force[rid] = {
                "receipt_id": rid,
                "depot": row["depot"].strip(),
                "arrived_at": parse_instant(row["arrived_at"]),
                "quantity": Fraction(Decimal(row["quantity"].strip())),
                "carrier_keyed": row["carrier"],
            }
        self.receipts = [in_force[rid] for rid in order]
        self.calibration = read_json(self._path("carrier_calibration.json"))

    # -- allocation parameters -------------------------------------------
    def _load_parameters(self):
        versions = read_json(self._path("allocation_parameters.json"))["versions"]
        self.param_versions = sorted(
            versions, key=lambda v: (parse_instant(v["effective_at"]), v["version_id"]))

    def parameters_at(self, instant):
        values = dict(PARAM_DEFAULTS)
        version_id = None
        for version in self.param_versions:
            if parse_instant(version["effective_at"]) > instant:
                continue
            if version["mode"] == "replace":
                values = dict(PARAM_DEFAULTS)
            values.update(version["values"])
            version_id = version["version_id"]
        return values, version_id


# --------------------------------------------------------------------------
# weighbridge settings
# --------------------------------------------------------------------------

def solve_least_squares(matrix, targets, size):
    normal = [[sum(row[i] * row[j] for row in matrix) for j in range(size)]
              for i in range(size)]
    rhs = [sum(row[i] * y for row, y in zip(matrix, targets)) for i in range(size)]
    work = [normal[i] + [rhs[i]] for i in range(size)]
    for i in range(size):
        pivot = max(range(i, size), key=lambda r: abs(work[r][i]))
        work[i], work[pivot] = work[pivot], work[i]
        if abs(work[i][i]) < 1e-9:
            return None
        for r in range(size):
            if r == i:
                continue
            factor = work[r][i] / work[i][i]
            for c in range(i, size + 1):
                work[r][c] -= factor * work[i][c]
    return [work[i][size] / work[i][i] for i in range(size)]


def solve_carrier_settings(calibration):
    """Recover every carrier's weighbridge settings from the calibration batches."""
    batches = sorted(calibration["batches"], key=lambda b: b["batch_id"])
    carriers = sorted({load["carrier"] for b in batches for load in b["loads"]})
    count = len(carriers)
    index = {name: i for i, name in enumerate(carriers)}
    targets = [int(b["credited_kg"]) for b in batches]
    load_counts = [len(b["loads"]) for b in batches]
    totals = [[Fraction(0)] * count for _ in batches]
    groups = [[{} for _ in range(count)] for _ in batches]
    for bi, batch in enumerate(batches):
        for load in batch["loads"]:
            ci = index[load["carrier"]]
            quantity = Fraction(Decimal(str(load["quantity"]).strip()))
            totals[bi][ci] += quantity
            groups[bi][ci][quantity] = groups[bi][ci].get(quantity, 0) + 1

    factors = [(unit, moisture, UNIT_KG[unit] * Fraction(100 - moisture, 100))
               for unit in UNIT_NAMES for moisture in range(10)]
    estimate = solve_least_squares([[float(v) for v in row] for row in totals],
                                   [float(t) for t in targets], count)
    if estimate is None:
        estimate = [950.0] * count
    weight_order = sorted(range(count), key=lambda ci: -max(t[ci] for t in totals))

    def search_factors(tolerance):
        candidates = []
        for ci in range(count):
            allowed = [f for f in factors
                       if abs(float(f[2]) - estimate[ci]) <= tolerance]
            if not allowed:
                return []
            candidates.append(allowed)
        low = [targets[bi] - load_counts[bi] - 1 for bi in range(len(batches))]
        high = [targets[bi] + load_counts[bi] + 1 for bi in range(len(batches))]
        rest_min = [[Fraction(0)] * len(batches) for _ in range(count + 1)]
        rest_max = [[Fraction(0)] * len(batches) for _ in range(count + 1)]
        for k in range(count - 1, -1, -1):
            ci = weight_order[k]
            lowest = min(f[2] for f in candidates[ci])
            highest = max(f[2] for f in candidates[ci])
            for bi in range(len(batches)):
                rest_min[k][bi] = rest_min[k + 1][bi] + totals[bi][ci] * lowest
                rest_max[k][bi] = rest_max[k + 1][bi] + totals[bi][ci] * highest
        found = []

        def walk(k, partial, chosen):
            for bi in range(len(batches)):
                if partial[bi] + rest_min[k][bi] > high[bi]:
                    return
                if partial[bi] + rest_max[k][bi] < low[bi]:
                    return
            if k == count:
                found.append(list(chosen))
                return
            ci = weight_order[k]
            for factor in candidates[ci]:
                chosen[ci] = factor
                walk(k + 1, [partial[bi] + totals[bi][ci] * factor[2]
                             for bi in range(len(batches))], chosen)
                chosen[ci] = None

        walk(0, [Fraction(0)] * len(batches), [None] * count)
        return found

    def search_roundings(choice):
        contributions = []
        for ci in range(count):
            unit, moisture, _ = choice[ci]
            per_rounding = {}
            for rounding in ROUNDINGS:
                settings = (unit, moisture, rounding)
                per_rounding[rounding] = [
                    sum(n * credited_kg(q, settings) for q, n in groups[bi][ci].items())
                    for bi in range(len(batches))]
            contributions.append(per_rounding)
        rest_min = [[0] * len(batches) for _ in range(count + 1)]
        rest_max = [[0] * len(batches) for _ in range(count + 1)]
        for k in range(count - 1, -1, -1):
            ci = weight_order[k]
            for bi in range(len(batches)):
                values = [contributions[ci][r][bi] for r in ROUNDINGS]
                rest_min[k][bi] = rest_min[k + 1][bi] + min(values)
                rest_max[k][bi] = rest_max[k + 1][bi] + max(values)
        answer = []

        def walk(k, partial, chosen):
            for bi in range(len(batches)):
                if partial[bi] + rest_min[k][bi] > targets[bi]:
                    return
                if partial[bi] + rest_max[k][bi] < targets[bi]:
                    return
            if k == count:
                answer.append(list(chosen))
                return
            ci = weight_order[k]
            for rounding in ROUNDINGS:
                chosen[ci] = rounding
                walk(k + 1, [partial[bi] + contributions[ci][rounding][bi]
                             for bi in range(len(batches))], chosen)
                chosen[ci] = None
                if answer:
                    return

        walk(0, [0] * len(batches), [None] * count)
        return answer[0] if answer else None

    for tolerance in (1.0, 2.5, 6.0, 15.0, 40.0, 200.0):
        for choice in search_factors(tolerance):
            roundings = search_roundings(choice)
            if roundings is not None:
                return {carriers[ci]: (choice[ci][0], choice[ci][1], roundings[ci])
                        for ci in range(count)}
    raise RuntimeError("no weighbridge settings reproduce the calibration batches")


# --------------------------------------------------------------------------
# the allocation procedure
# --------------------------------------------------------------------------

DIVISOR_FAMILIES = (
    (1, [(k,) for k in range(1000, 2001)]),
    (2, [(k,) for k in range(100, 1001)]),
    (3, [(a, b) for a in range(40, 101) for b in range(30, 71)]),
    (4, [(a, b) for a in range(100, 200) for b in range(0, 150)]),
)


def divisors(family, params, upto):
    """Integer divisor sequence d(0..upto), scaled by a positive constant."""
    if family == 1:
        return [params[0]] + [1000 * (2 * n + 1) for n in range(1, upto + 1)]
    if family == 2:
        return [1000 * n + params[0] for n in range(upto + 1)]
    if family == 3:
        a, b = params
        return [a] + [100 * n + b for n in range(1, upto + 1)]
    a, b = params
    return [a] + [200 * n + b for n in range(1, upto + 1)]


def tie_break_order(tie_break, weights, ids, oldest):
    count = len(ids)
    if tie_break == "highest_weight":
        keys = [(-weights[i], ids[i]) for i in range(count)]
    elif tie_break == "oldest_open_lot":
        keys = [(oldest[i], ids[i]) for i in range(count)]
    else:
        keys = [(ids[i],) for i in range(count)]
    return sorted(range(count), key=lambda i: keys[i])


def hand_out_units(allocable, weights, caps, divisor, order):
    counts = [0] * len(weights)
    left = allocable
    while left > 0:
        best = -1
        for i in order:
            if counts[i] >= caps[i]:
                continue
            if best < 0:
                best = i
                continue
            if weights[i] * divisor[counts[best]] > weights[best] * divisor[counts[i]]:
                best = i
        if best < 0:
            break
        counts[best] += 1
        left -= 1
    return counts


def fair_shares(allocable, weights, caps):
    """Fair shares in units and the level; the caps and None when none is needed."""
    count = len(weights)
    if sum(caps) <= allocable:
        return [Fraction(c) for c in caps], None
    order = sorted(range(count), key=lambda i: Fraction(caps[i], weights[i]))
    taken = 0
    for j in range(count + 1):
        remaining = sum(weights[order[i]] for i in range(j, count))
        if remaining > 0:
            level = Fraction(allocable - taken, remaining)
            low = (Fraction(caps[order[j - 1]], weights[order[j - 1]])
                   if j > 0 else Fraction(0))
            high = (Fraction(caps[order[j]], weights[order[j]])
                    if j < count else None)
            if level >= low and (high is None or level <= high):
                return ([min(Fraction(caps[i]), weights[i] * level)
                         for i in range(count)], level)
        if j < count:
            taken += caps[order[j]]
    raise RuntimeError("no level exists")


def review_joins(test, grant, floor, before, current, previous, cap, demand,
                 allocable, unit_kg, weight, weight_sum):
    if test == "B_lt":
        return before > 0 and grant < floor * before
    if test == "B_le":
        return before > 0 and grant <= floor * before
    if test == "B_lt_floor":
        return before > 0 and grant < floor * floor_div(before)
    if test == "B_lt_ceil":
        return before > 0 and grant < floor * ceil_frac(before)
    if test == "C_lt":
        return current > 0 and grant < floor * current
    if test == "C_le":
        return current > 0 and grant <= floor * current
    if test == "C_lt_floor":
        return current > 0 and grant < floor * floor_div(current)
    if test == "C_lt_ceil":
        return current > 0 and grant < floor * ceil_frac(current)
    if test == "P_lt":
        return previous > 0 and grant < floor * previous
    if test == "K_lt":
        return cap >= 1 and grant < floor * cap
    if test == "K_le":
        return cap >= 1 and grant <= floor * cap
    if test == "K_lt_floor_prod":
        return cap >= 1 and grant < floor_div(floor * cap)
    if test == "D_lt":
        return demand > 0 and grant * unit_kg < floor * demand
    if test == "AW_lt":
        return cap >= 1 and grant < floor * allocable * Fraction(weight, weight_sum)
    raise KeyError(test)


def allocate_depot_week(entrants, allocable, unit_kg, tie_break, bonus_composition,
                        review_floor, review_round_limit, divisor_of, test):
    """Run a rationed depot-week, review rounds included.

    `entrants` carries customer_id, base_weight, bonuses, cap, demand_kg and
    oldest_lot_at for every customer with open demand there.
    """
    count = len(entrants)
    ids = [e["customer_id"] for e in entrants]
    caps = [e["cap"] for e in entrants]
    oldest = [e["oldest_lot_at"] for e in entrants]

    def weight_of(entrant, reviewed):
        bonuses = entrant["bonuses"] + (1 if reviewed else 0)
        if bonus_composition == "multiplicative":
            return entrant["base_weight"] * (2 ** bonuses)
        return entrant["base_weight"] + bonuses

    before_shares, _ = fair_shares(allocable, [weight_of(e, False) for e in entrants],
                                   caps)
    divisor = divisor_of(allocable + 1)
    on_list = [False] * count
    rounds = 0
    previous_shares = None
    while True:
        weights = [weight_of(entrants[i], on_list[i]) for i in range(count)]
        order = tie_break_order(tie_break, weights, ids, oldest)
        counts = hand_out_units(allocable, weights, caps, divisor, order)
        shares, level = fair_shares(allocable, weights, caps)
        previous = previous_shares if previous_shares is not None else shares
        weight_sum = sum(weights)
        joins = []
        for i in range(count):
            if on_list[i]:
                continue
            if review_joins(test, counts[i], review_floor, before_shares[i],
                            shares[i], previous[i], caps[i], entrants[i]["demand_kg"],
                            allocable, unit_kg, weights[i], weight_sum):
                joins.append(i)
        outcome = {"counts": counts, "weights": weights, "level": level,
                   "shares": shares, "reviewed": list(on_list),
                   "reviewed_count": sum(1 for flag in on_list if flag),
                   "rounds": rounds}
        if not joins:
            outcome["settled"] = True
            return outcome
        if rounds >= review_round_limit:
            outcome["settled"] = False
            return outcome
        for i in joins:
            on_list[i] = True
        rounds += 1
        previous_shares = shares


# --------------------------------------------------------------------------
# identifying the procedure from the office's journal
# --------------------------------------------------------------------------

def journal_case(entry):
    params = entry["parameters"]
    unit_kg = int(entry["unit_kg"])
    entrants = []
    for customer in sorted(entry["customers"], key=lambda c: c["customer"]):
        base = (params["public_weight"] if customer["segment"] == "public"
                else params["commercial_weight"])
        entrants.append({
            "customer_id": customer["customer"],
            "base_weight": int(base),
            "bonuses": ((1 if customer["critical_route"] else 0)
                        + (1 if customer["in_deficit"] else 0)),
            "cap": int(customer["open_demand_kg"]) // unit_kg,
            "demand_kg": int(customer["open_demand_kg"]),
            "oldest_lot_at": parse_instant(customer["oldest_lot_at"]),
        })
    return {
        "entry_id": entry["entry_id"],
        "allocable": int(entry["available_kg"]) // unit_kg,
        "unit_kg": unit_kg,
        "entrants": entrants,
        "tie_break": params["tie_break"],
        "bonus_composition": params["bonus_composition"],
        "review_floor": Fraction(params["review_floor"]),
        "review_round_limit": int(params["review_round_limit"]),
        "granted": [int(entry["granted_kg"][e["customer_id"]]) // unit_kg
                    for e in entrants],
        "reviewed_count": int(entry["reviewed_count"]),
        "rounds": int(entry["review_rounds"]),
        "settled": bool(entry["settled"]),
    }


def identify_procedure(journal):
    """Recover the divisor sequence and the review test from the journal."""
    cases = sorted((journal_case(e) for e in journal),
                   key=lambda c: (c["allocable"], c["entry_id"]))
    candidates = [(family, params)
                  for family, options in DIVISOR_FAMILIES for params in options]
    cache = {}

    def divisor_list(family, params, upto):
        key = (family, params, upto)
        value = cache.get(key)
        if value is None:
            value = divisors(family, params, upto)
            cache[key] = value
        return value

    for case in cases:
        if len(candidates) <= 1:
            break
        if case["rounds"] != 0 or case["reviewed_count"] != 0:
            continue
        entrants = case["entrants"]
        ids = [e["customer_id"] for e in entrants]
        caps = [e["cap"] for e in entrants]
        oldest = [e["oldest_lot_at"] for e in entrants]
        if case["bonus_composition"] == "multiplicative":
            weights = [e["base_weight"] * (2 ** e["bonuses"]) for e in entrants]
        else:
            weights = [e["base_weight"] + e["bonuses"] for e in entrants]
        order = tie_break_order(case["tie_break"], weights, ids, oldest)
        allocable = case["allocable"]
        kept = []
        for family, params in candidates:
            divisor = divisor_list(family, params, allocable + 1)
            if hand_out_units(allocable, weights, caps, divisor,
                              order) == case["granted"]:
                kept.append((family, params))
        candidates = kept
    if not candidates:
        raise RuntimeError("no divisor sequence reproduces the journal")

    combinations = [(d, t) for d in candidates for t in REVIEW_TESTS]
    for case in cases:
        if len(combinations) <= 1:
            break
        kept = []
        for divisor_spec, test in combinations:
            family, params = divisor_spec
            outcome = allocate_depot_week(
                case["entrants"], case["allocable"], case["unit_kg"],
                case["tie_break"], case["bonus_composition"], case["review_floor"],
                case["review_round_limit"],
                lambda upto, f=family, p=params: divisor_list(f, p, upto), test)
            if (outcome["counts"] == case["granted"]
                    and outcome["reviewed_count"] == case["reviewed_count"]
                    and outcome["rounds"] == case["rounds"]
                    and outcome["settled"] == case["settled"]):
                kept.append((divisor_spec, test))
        combinations = kept
    if not combinations:
        raise RuntimeError("no review test reproduces the journal")
    return combinations[0]


# --------------------------------------------------------------------------
# the season
# --------------------------------------------------------------------------

class Season(object):
    def __init__(self, extract, settings=None, procedure=None, parameter_hook=None):
        self.ex = extract
        self.settings = settings or solve_carrier_settings(extract.calibration)
        self.divisor_spec, self.review_test = (procedure
                                               or identify_procedure(extract.journal))
        self.parameter_hook = parameter_hook
        self._divisor_cache = {}

    # -- weighbridge -----------------------------------------------------
    def settings_at(self, carrier, instant):
        return self.settings[carrier]

    def carrier_name(self, keyed):
        key = keyed.strip().lower()
        for name in self.settings:
            if name.strip().lower() == key:
                return name
        raise KeyError(keyed)

    def divisor_of(self, upto):
        value = self._divisor_cache.get(upto)
        if value is None:
            family, params = self.divisor_spec
            value = divisors(family, params, upto)
            self._divisor_cache[upto] = value
        return value

    # -- preparation -----------------------------------------------------
    def prepare(self):
        ex = self.ex
        self.void_orders = self._find_void_orders()
        self.final_quantity, self.cancelled, self.matched_pos = self._apply_amendments()
        self.orphans = []
        self.lots = []
        for order in ex.orders:
            oid = order["order_id"]
            if oid in self.void_orders or self.cancelled.get(oid):
                continue
            instant = order["placed_at"]
            week = ex.week_of(instant)
            if week is None:
                self.orphans.append((oid, order["customer_ref"], "out_of_season"))
                continue
            customer = ex.resolve_reference(order["customer_ref"], instant)
            if customer is None:
                self.orphans.append((oid, order["customer_ref"], "unknown_reference"))
                continue
            if ex.is_retired(customer, instant):
                self.orphans.append((oid, order["customer_ref"], "retired_reference"))
                continue
            depot = ex.depot_of(customer, instant)
            if depot is None:
                self.orphans.append((oid, order["customer_ref"], "unserved"))
                continue
            if order["order_class"] not in ex.order_classes:
                self.orphans.append((oid, order["customer_ref"], "unknown_class"))
                continue
            self.lots.append({
                "order_id": oid,
                "quantity_kg": self.final_quantity.get(oid, order["quantity_kg"]),
                "placed_at": instant,
                "placement_week": week,
                "order_class": order["order_class"],
                "depot": depot,
                "holder": customer,
                "delivered_kg": 0,
                "delivered_by_week": {},
                "status": "open",
                "closed_week": None,
                "closed_kg": 0,
            })
        self.lots.sort(key=lambda lot: (lot["placed_at"], lot["order_id"]))
        self.lots_by_depot = {}
        for lot in self.lots:
            self.lots_by_depot.setdefault(lot["depot"], []).append(lot)
        self.receipt_items = []
        for receipt in ex.receipts:
            carrier = self.carrier_name(receipt["carrier_keyed"])
            self.receipt_items.append({
                "receipt": receipt,
                "week": ex.week_of(receipt["arrived_at"]),
                "carrier": carrier,
                "credited_kg": credited_kg(
                    receipt["quantity"],
                    self.settings_at(carrier, receipt["arrived_at"])),
            })

    def _find_void_orders(self):
        by_po = {}
        for order in self.ex.orders:
            by_po.setdefault(order["po_number"], []).append(order["order_id"])
        void = set()
        lines = [row for row in self.ex.board if row["status"].strip() == "VOID-DUP"]
        lines.sort(key=lambda row: row["board_line"].strip())
        for row in lines:
            po = row["po_number"].strip()
            available = sorted(oid for oid in by_po.get(po, []) if oid not in void)
            if available:
                void.add(available[-1])
        return void

    def _apply_amendments(self):
        by_po = {}
        for order in self.ex.orders:
            if order["order_id"] in self.void_orders:
                continue
            by_po.setdefault(order["po_number"], []).append(order["order_id"])
        quantity = {}
        cancelled = {}
        matched = {}
        unmatched = set()
        for amendment in sorted(self.ex.amendments, key=lambda a: a["seq"]):
            po = amendment["po_number"].strip()
            targets = by_po.get(po)
            if not targets:
                unmatched.add(po)
                continue
            for oid in targets:
                matched.setdefault(po, set()).add(oid)
                if amendment["action"] == "set_quantity":
                    quantity[oid] = tonnes_to_kg(amendment["quantity_t"])
                elif amendment["action"] == "cancel":
                    cancelled[oid] = True
                elif amendment["action"] == "reinstate":
                    cancelled[oid] = False
        self.unmatched_amendments = sorted(unmatched)
        return quantity, cancelled, matched

    # -- the weekly run --------------------------------------------------
    def run(self):
        self.prepare()
        ex = self.ex
        weeks = len(ex.week_ids)
        self.stock = {code: ex.depots[code]["opening_kg"] for code in ex.depot_codes}
        self.depot_receipts = {code: 0 for code in ex.depot_codes}
        self.depot_delivered = {code: 0 for code in ex.depot_codes}
        self.depot_rationed_weeks = {code: [] for code in ex.depot_codes}
        self.week_receipts = [0] * weeks
        self.week_delivered = [0] * weeks
        self.week_lapsed = [0] * weeks
        self.week_withdrawn = [0] * weeks
        self.week_rationed = [0] * weeks
        self.week_unsettled = [0] * weeks
        self.region_week_delivered = {region: [0] * weeks for region in REGIONS}
        self.rationing_events = []
        self.allocation_rows = []
        self.deficit_boosts = []
        self.week_parameters = []
        self.rationed_delivered = 0
        self.unrationed_delivered = 0
        self.lapsed_records = []
        self.withdrawn_records = []

        receipts_by_week = {}
        for item in self.receipt_items:
            if item["week"] is not None:
                receipts_by_week.setdefault(item["week"], []).append(item)

        for week in range(weeks):
            instant = ex.week_closes[week]
            values, version_id = ex.parameters_at(instant)
            if self.parameter_hook is not None:
                values = self.parameter_hook(week, dict(values))
            self.week_parameters.append((values, version_id))
            unit_kg = int(values["allocation_unit_kg"])
            self._apply_identity_events(week)
            for item in receipts_by_week.get(week, []):
                depot = item["receipt"]["depot"]
                self.stock[depot] += item["credited_kg"]
                self.depot_receipts[depot] += item["credited_kg"]
                self.week_receipts[week] += item["credited_kg"]
            deficits = self._deficit_customers(week, values)
            critical = {}
            deficit_seen = set()
            for depot in ex.depot_codes:
                demand = self._open_demand(depot, week)
                if not demand:
                    continue
                available = self.stock[depot]
                total_demand = sum(item["demand_kg"] for item in demand)
                if total_demand <= available:
                    for item in demand:
                        self._deliver(depot, week, item, item["demand_kg"])
                        self.unrationed_delivered += item["demand_kg"]
                    continue
                self.depot_rationed_weeks[depot].append(week)
                self.week_rationed[week] += 1
                allocable = available // unit_kg
                entrants = []
                for item in demand:
                    customer = item["customer_id"]
                    if customer not in critical:
                        critical[customer] = ex.serves_critical_route(customer, instant)
                    in_deficit = customer in deficits
                    if in_deficit:
                        deficit_seen.add(customer)
                    segment = ex.segment_of(customer)
                    base = (values["public_weight"] if segment == "public"
                            else values["commercial_weight"])
                    entrants.append({
                        "customer_id": customer,
                        "base_weight": int(base),
                        "bonuses": ((1 if critical[customer] else 0)
                                    + (1 if in_deficit else 0)),
                        "cap": item["demand_kg"] // unit_kg,
                        "demand_kg": item["demand_kg"],
                        "oldest_lot_at": item["oldest_lot_at"],
                        "item": item,
                    })
                outcome = allocate_depot_week(
                    entrants, allocable, unit_kg, values["tie_break"],
                    values["bonus_composition"], Fraction(values["review_floor"]),
                    int(values["review_round_limit"]), self.divisor_of,
                    self.review_test)
                if not outcome["settled"]:
                    self.week_unsettled[week] += 1
                for i, entrant in enumerate(entrants):
                    granted = outcome["counts"][i] * unit_kg
                    self._deliver(depot, week, entrant["item"], granted)
                    self.rationed_delivered += granted
                    self.allocation_rows.append({
                        "week": week,
                        "depot": depot,
                        "customer_id": entrant["customer_id"],
                        "segment": ex.segment_of(entrant["customer_id"]),
                        "demand_kg": entrant["demand_kg"],
                        "weight": outcome["weights"][i],
                        "reviewed": outcome["reviewed"][i],
                        "allocated_kg": granted,
                    })
                self.rationing_events.append({
                    "depot": depot,
                    "week": week,
                    "available_kg": available,
                    "demand_kg": total_demand,
                    "allocable_units": allocable,
                    "level": level_text(outcome["level"]),
                    "whole_part_units": sum(floor_div(s) for s in outcome["shares"]),
                    "units_granted": sum(outcome["counts"]),
                    "review_rounds": outcome["rounds"],
                    "settled": outcome["settled"],
                })
            for customer in sorted(deficit_seen):
                self.deficit_boosts.append({"week": week, "customer_id": customer})
            self._lapse(week)

        self.closing = dict(self.stock)
        self._season_close()

    def _apply_identity_events(self, week):
        ex = self.ex
        for event in ex.identity_events:
            if event["kind"] not in ("merge", "retire"):
                continue
            if ex.week_of(event["instant"]) != week:
                continue
            if event["kind"] == "merge":
                target = ex.merge_target(event["target"], event["instant"])
                for lot in self.lots:
                    if (lot["holder"] == event["code"]
                            and lot["placed_at"] < event["instant"]):
                        lot["holder"] = target
            else:
                for lot in self.lots:
                    if (lot["holder"] == event["code"]
                            and lot["placed_at"] < event["instant"]
                            and self._open(lot) > 0):
                        amount = self._open(lot)
                        lot["status"] = "withdrawn"
                        lot["closed_week"] = week
                        lot["closed_kg"] = amount
                        self.week_withdrawn[week] += amount
                        self.withdrawn_records.append(lot)

    @staticmethod
    def _open(lot):
        if lot["status"] != "open":
            return 0
        return lot["quantity_kg"] - lot["delivered_kg"]

    def _on_offer(self, lot, week):
        if self._open(lot) <= 0:
            return False
        offer_weeks = self.ex.order_classes[lot["order_class"]]["offer_weeks"]
        return lot["placement_week"] <= week <= lot["placement_week"] + offer_weeks - 1

    def _open_demand(self, depot, week):
        grouped = {}
        for lot in self.lots_by_depot.get(depot, []):
            if not self._on_offer(lot, week):
                continue
            entry = grouped.get(lot["holder"])
            if entry is None:
                entry = {"customer_id": lot["holder"], "demand_kg": 0,
                         "oldest_lot_at": lot["placed_at"], "lots": []}
                grouped[lot["holder"]] = entry
            entry["demand_kg"] += self._open(lot)
            if lot["placed_at"] < entry["oldest_lot_at"]:
                entry["oldest_lot_at"] = lot["placed_at"]
            entry["lots"].append(lot)
        return [grouped[key] for key in sorted(grouped)]

    def _deliver(self, depot, week, item, amount):
        if amount <= 0:
            return
        left = amount
        for lot in sorted(item["lots"], key=lambda l: (l["placed_at"], l["order_id"])):
            if left <= 0:
                break
            room = self._open(lot)
            if room <= 0:
                continue
            take = min(room, left)
            lot["delivered_kg"] += take
            lot["delivered_by_week"][week] = lot["delivered_by_week"].get(week, 0) + take
            left -= take
        delivered = amount - left
        self.stock[depot] -= delivered
        self.depot_delivered[depot] += delivered
        self.week_delivered[week] += delivered
        self.region_week_delivered[self.ex.depots[depot]["region"]][week] += delivered

    def _deficit_customers(self, week, values):
        threshold = Fraction(values["deficit_threshold"])
        entitled = {}
        delivered = {}
        for lot in self.lots:
            if lot["placement_week"] >= week:
                continue
            basis = self.ex.order_classes[lot["order_class"]]["entitlement_basis"]
            if basis == "excluded":
                continue
            earlier = sum(kg for w, kg in lot["delivered_by_week"].items() if w < week)
            holder = lot["holder"]
            if basis == "ordered":
                entitled[holder] = entitled.get(holder, 0) + lot["quantity_kg"]
            else:
                entitled[holder] = entitled.get(holder, 0) + earlier
            delivered[holder] = delivered.get(holder, 0) + earlier
        out = set()
        for customer, total in entitled.items():
            if total > 0 and delivered.get(customer, 0) < threshold * total:
                out.add(customer)
        return out

    def _lapse(self, week):
        last = len(self.ex.week_ids) - 1
        for lot in self.lots:
            if self._open(lot) <= 0:
                continue
            offer_weeks = self.ex.order_classes[lot["order_class"]]["offer_weeks"]
            end = lot["placement_week"] + offer_weeks - 1
            if end == week and end <= last:
                amount = self._open(lot)
                lot["status"] = "lapsed"
                lot["closed_week"] = week
                lot["closed_kg"] = amount
                self.week_lapsed[week] += amount
                self.lapsed_records.append(lot)

    def _season_close(self):
        ex = self.ex
        final = ex.season_end
        self.open_at_close = {}
        for lot in self.lots:
            self.open_at_close[lot["order_id"]] = max(self._open(lot), 0)
        ordered = {}
        delivered = {}
        for lot in self.lots:
            ordered[lot["holder"]] = ordered.get(lot["holder"], 0) + lot["quantity_kg"]
            delivered[lot["holder"]] = (delivered.get(lot["holder"], 0)
                                        + lot["delivered_kg"])
        self.true_up = []
        for customer in sorted(ex.contracts):
            contract = ex.contracts[customer]
            if contract["segment"] != "public" or contract["contract_min_kg"] <= 0:
                continue
            if ex.merge_target(customer, final) != customer:
                continue
            if ex.is_retired(customer, final):
                continue
            credit = (min(contract["contract_min_kg"], ordered.get(customer, 0))
                      - delivered.get(customer, 0))
            if credit > 0:
                self.true_up.append({
                    "customer_id": customer,
                    "contract_min_kg": contract["contract_min_kg"],
                    "delivered_kg": delivered.get(customer, 0),
                    "credit_kg": credit,
                })


# --------------------------------------------------------------------------
# the reports
# --------------------------------------------------------------------------

def build_reports(season):
    ex = season.ex
    weeks = ex.week_ids
    reports = {}

    depots = []
    for code in ex.depot_codes:
        depots.append({
            "depot": code,
            "region": ex.depots[code]["region"],
            "opening_kg": ex.depots[code]["opening_kg"],
            "receipts_kg": season.depot_receipts[code],
            "delivered_kg": season.depot_delivered[code],
            "closing_kg": season.closing[code],
            "rationed_weeks": [weeks[w] for w in season.depot_rationed_weeks[code]],
        })
    week_rows = []
    for i, week_id in enumerate(weeks):
        week_rows.append({
            "week": week_id,
            "receipts_kg": season.week_receipts[i],
            "delivered_kg": season.week_delivered[i],
            "lapsed_kg": season.week_lapsed[i],
            "withdrawn_kg": season.week_withdrawn[i],
            "rationed_depots": season.week_rationed[i],
            "unsettled_depots": season.week_unsettled[i],
        })
    reports["summary"] = {
        "depots": depots,
        "weeks": week_rows,
        "true_up": season.true_up,
    }

    carrier_settings = []
    for carrier in sorted(season.settings):
        unit, moisture, rounding = season.settings_at(carrier, ex.season_end)
        carrier_settings.append({
            "carrier": carrier,
            "unit": unit,
            "moisture_deduction": moisture,
            "rounding": rounding,
        })
    parameters = []
    for i, week_id in enumerate(weeks):
        values, version_id = season.week_parameters[i]
        row = {"week": week_id, "version_id": version_id}
        for name in PARAM_NAMES:
            row[name] = int(values[name]) if name in INTEGER_PARAMS else values[name]
        parameters.append(row)
    events = []
    for event in sorted(season.rationing_events,
                        key=lambda e: (e["week"], e["depot"])):
        row = dict(event)
        row["week"] = weeks[event["week"]]
        events.append(row)
    reports["policy_audit"] = {
        "carrier_settings": carrier_settings,
        "parameters": parameters,
        "rationing_events": events,
        "deficit_boosts": [{"week": weeks[b["week"]], "customer_id": b["customer_id"]}
                           for b in season.deficit_boosts],
    }

    orphans = [{"order_id": oid, "customer_ref": ref, "reason": reason}
               for oid, ref, reason in sorted(season.orphans)]
    amendments = []
    for po in sorted(season.matched_pos):
        for oid in sorted(season.matched_pos[po]):
            order = ex.orders_by_id[oid]
            amendments.append({
                "po_number": po,
                "order_id": oid,
                "final_quantity_kg": season.final_quantity.get(oid,
                                                               order["quantity_kg"]),
                "cancelled": bool(season.cancelled.get(oid)),
            })
    lapsed = [{
        "order_id": lot["order_id"],
        "customer_id": lot["holder"],
        "depot": lot["depot"],
        "week": weeks[lot["closed_week"]],
        "lapsed_kg": lot["closed_kg"],
    } for lot in sorted(season.lapsed_records, key=lambda l: l["order_id"])]
    withdrawn = [{
        "order_id": lot["order_id"],
        "customer_id": lot["holder"],
        "depot": lot["depot"],
        "week": weeks[lot["closed_week"]],
        "withdrawn_kg": lot["closed_kg"],
    } for lot in sorted(season.withdrawn_records, key=lambda l: l["order_id"])]
    opening = sum(ex.depots[c]["opening_kg"] for c in ex.depot_codes)
    receipts = sum(season.depot_receipts.values())
    delivered = sum(season.depot_delivered.values())
    closing = sum(season.closing.values())
    ordered_total = sum(lot["quantity_kg"] for lot in season.lots)
    delivered_total = sum(lot["delivered_kg"] for lot in season.lots)
    lapsed_total = sum(row["lapsed_kg"] for row in lapsed)
    withdrawn_total = sum(row["withdrawn_kg"] for row in withdrawn)
    open_total = sum(season.open_at_close[lot["order_id"]] for lot in season.lots)
    reports["data_quality"] = {
        "orphan_orders": orphans,
        "voided_orders": sorted(season.void_orders),
        "amendments": amendments,
        "unmatched_amendments": season.unmatched_amendments,
        "lapsed_lots": lapsed,
        "withdrawn_lots": withdrawn,
        "reconciliation": {
            "stock": {
                "opening_kg": opening,
                "receipts_kg": receipts,
                "delivered_kg": delivered,
                "closing_kg": closing,
                "residual_kg": opening + receipts - delivered - closing,
            },
            "demand": {
                "ordered_kg": ordered_total,
                "delivered_kg": delivered_total,
                "lapsed_kg": lapsed_total,
                "withdrawn_kg": withdrawn_total,
                "open_at_close_kg": open_total,
                "residual_kg": (ordered_total - delivered_total - lapsed_total
                                - withdrawn_total - open_total),
            },
            "allocation": {
                "rationed_kg": season.rationed_delivered,
                "unrationed_kg": season.unrationed_delivered,
                "delivered_kg": delivered_total,
                "residual_kg": (delivered_total - season.rationed_delivered
                                - season.unrationed_delivered),
            },
        },
    }

    for region in REGIONS:
        codes = sorted(c for c in ex.depot_codes if ex.depots[c]["region"] == region)
        rationed = sum(len(season.depot_rationed_weeks[c]) for c in codes)
        key = "region_" + region
        if rationed == 0:
            reports[key] = {"region": region, "in_scope": False}
            continue
        per_customer = {}
        for lot in season.lots:
            if ex.depots[lot["depot"]]["region"] != region:
                continue
            entry = per_customer.setdefault(lot["holder"], {
                "customer_id": lot["holder"],
                "segment": ex.segment_of(lot["holder"]),
                "ordered_kg": 0, "delivered_kg": 0, "lapsed_kg": 0,
                "withdrawn_kg": 0, "open_at_close_kg": 0,
            })
            entry["ordered_kg"] += lot["quantity_kg"]
            entry["delivered_kg"] += lot["delivered_kg"]
            if lot["status"] == "lapsed":
                entry["lapsed_kg"] += lot["closed_kg"]
            elif lot["status"] == "withdrawn":
                entry["withdrawn_kg"] += lot["closed_kg"]
            else:
                entry["open_at_close_kg"] += season.open_at_close[lot["order_id"]]
        customers = []
        for customer in sorted(per_customer):
            entry = per_customer[customer]
            entry["fill_ratio"] = ratio_text(entry["delivered_kg"], entry["ordered_kg"])
            customers.append(entry)
        reports[key] = {
            "region": region,
            "in_scope": True,
            "depots": codes,
            "rationed_depot_weeks": rationed,
            "customers": customers,
            "weekly_delivered_kg": {week_id: season.region_week_delivered[region][i]
                                    for i, week_id in enumerate(weeks)},
        }

    for segment in SEGMENTS:
        rows = [row for row in season.allocation_rows if row["segment"] == segment]
        key = "segment_" + segment
        if not rows:
            reports[key] = {"segment": segment, "in_scope": False}
            continue
        holders = set()
        ordered = delivered_kg = lapsed_kg = 0
        for lot in season.lots:
            if ex.segment_of(lot["holder"]) != segment:
                continue
            holders.add(lot["holder"])
            ordered += lot["quantity_kg"]
            delivered_kg += lot["delivered_kg"]
            if lot["status"] == "lapsed":
                lapsed_kg += lot["closed_kg"]
        rows.sort(key=lambda r: (r["week"], r["depot"], r["customer_id"]))
        reports[key] = {
            "segment": segment,
            "in_scope": True,
            "customer_count": len(holders),
            "ordered_kg": ordered,
            "delivered_kg": delivered_kg,
            "lapsed_kg": lapsed_kg,
            "rationed_allocations": [{
                "week": weeks[row["week"]],
                "depot": row["depot"],
                "customer_id": row["customer_id"],
                "demand_kg": row["demand_kg"],
                "weight": row["weight"],
                "reviewed": row["reviewed"],
                "allocated_kg": row["allocated_kg"],
            } for row in rows],
        }
    return reports


REPORT_FILES = (
    ("summary", "summary.json"),
    ("policy_audit", "policy_audit.json"),
    ("data_quality", "data_quality.json"),
    ("region_North", "region_North.json"),
    ("region_South", "region_South.json"),
    ("region_West", "region_West.json"),
    ("region_East", "region_East.json"),
    ("segment_commercial", "segment_commercial.json"),
    ("segment_public", "segment_public.json"),
)


def write_reports(reports, out_dir):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    for key, name in REPORT_FILES:
        text = json.dumps(reports[key], indent=2, sort_keys=True) + "\n"
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(text)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    extract = Extract(argv[1])
    season = Season(extract)
    season.run()
    write_reports(build_reports(season), argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
