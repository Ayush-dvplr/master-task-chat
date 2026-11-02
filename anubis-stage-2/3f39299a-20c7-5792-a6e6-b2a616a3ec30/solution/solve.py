#!/usr/bin/env python3
"""Replay a road-salt rationing season and write the office's nine reports.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Everything is read from DATA_DIR; nothing about any particular season is built in.
Quantities are carried as integer kg and shares as exact fractions.
"""

from __future__ import annotations

import csv
import heapq
import json
import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from fractions import Fraction
from pathlib import Path

PARAMETER_DEFAULTS = {
    "public_weight": 2,
    "commercial_weight": 1,
    "allocation_unit_kg": 500,
    "tie_break": "lowest_customer_id",
    "deficit_threshold": "0.50",
    "bonus_composition": "additive",
    "review_floor": "0.40",
    "review_round_limit": 1,
}
UNIT_KG = {"short_ton": Decimal("907.18474"), "metric_tonne": Decimal("1000"), "long_ton": Decimal("1016.0469088")}
ROUNDING = {"half_up": ROUND_HALF_UP, "down": ROUND_DOWN, "up": ROUND_UP}
REGIONS = ("North", "South", "West", "East")
SEGMENTS = ("commercial", "public")


# --------------------------------------------------------------------------- reading

def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def instant(stamp: str) -> int:
    """An offset-carrying timestamp as whole seconds since the epoch."""
    moment = datetime.fromisoformat(stamp.strip().replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError(f"timestamp without offset: {stamp!r}")
    return int(moment.timestamp())


def offset_seconds(text: str) -> int:
    sign = -1 if text.startswith("-") else 1
    hours, minutes = text.lstrip("+-").split(":")
    return sign * (int(hours) * 3600 + int(minutes) * 60)


def tonnes_to_kg(text: str) -> int:
    return int(Decimal(text.strip()) * 1000)


def credit(quantity: str, setting: tuple) -> int:
    """Credited whole kg of one load under (unit, moisture deduction %, rounding)."""
    unit, deduction, rounding = setting
    value = Decimal(quantity.strip()) * UNIT_KG[unit] * (100 - deduction) / 100
    return int(value.quantize(Decimal(1), rounding=ROUNDING[rounding]))


FACTORS = {(unit, deduction): Fraction(UNIT_KG[unit]) * Fraction(100 - deduction, 100)
           for unit in UNIT_KG for deduction in range(10)}


def exact_inverse(rows: list[list[Fraction]]) -> list[list[Fraction]] | None:
    """Inverse of a square rational matrix by exact Gauss-Jordan elimination; None when it is singular."""
    size = len(rows)
    work = [list(row) + [Fraction(int(i == j)) for j in range(size)] for i, row in enumerate(rows)]
    for col in range(size):
        pivot = next((r for r in range(col, size) if work[r][col]), None)
        if pivot is None:
            return None
        work[col], work[pivot] = work[pivot], work[col]
        lead = work[col][col]
        work[col] = [x / lead for x in work[col]]
        for r in range(size):
            if r != col and work[r][col]:
                k = work[r][col]
                work[r] = [x - k * y for x, y in zip(work[r], work[col])]
    return [row[size:] for row in work]


class Calibration:
    """Every assignment of weighbridge settings that reproduces a list of calibration batches.

    A load's credit lies strictly within one kg of its quantity times its carrier's factor, so each batch
    total pins a linear combination of the factors to an open interval. Any run of consecutive batches as
    long as the number of carriers still open is solved exactly in rationals, which confines each open
    factor to an interval; a factor outside the interval of any run is dropped. Carriers left with one
    factor are fixed, which narrows the intervals again, and the search branches only when no carrier is
    settled that way. With every factor fixed, the roundings are matched by meeting in the middle. When no
    run of batches gives a regular system, every stated factor stays open.
    """

    def __init__(self, batches: list[dict]) -> None:
        self.batches = batches
        self.carriers = sorted({load["carrier"] for batch in batches for load in batch["loads"]})
        self.targets = [int(batch["credited_kg"]) for batch in batches]
        self.tonnage = {c: [sum((Fraction(Decimal(l["quantity"].strip())) for l in b["loads"] if l["carrier"] == c),
                                Fraction(0)) for b in batches] for c in self.carriers}
        self.loads = {c: [sum(1 for l in b["loads"] if l["carrier"] == c) for b in batches] for c in self.carriers}
        self.cache: dict = {}

    def credits(self, carrier: str, setting: tuple) -> list[int]:
        key = (carrier, setting)
        if key not in self.cache:
            self.cache[key] = [sum(credit(l["quantity"], setting) for l in b["loads"] if l["carrier"] == carrier)
                               for b in self.batches]
        return self.cache[key]

    def band(self, carrier: str, factor: tuple) -> tuple[list[int], list[int]]:
        """Per batch, the least and the greatest credit the carrier's three roundings give under a factor."""
        options = [self.credits(carrier, (*factor, rounding)) for rounding in ROUNDING]
        return [min(v) for v in zip(*options)], [max(v) for v in zip(*options)]

    def open_factors(self, fixed: dict) -> dict[str, set]:
        free = [c for c in self.carriers if c not in fixed]
        low, high = list(self.targets), list(self.targets)
        for carrier, factor in fixed.items():
            least, most = self.band(carrier, factor)
            low = [x - m for x, m in zip(low, most)]
            high = [x - m for x, m in zip(high, least)]
        for b in range(len(self.batches)):
            room = sum(self.loads[c][b] for c in free)
            low[b] -= room
            high[b] += room
        found = {c: set(FACTORS) for c in free}
        for start in range(len(self.batches) - len(free) + 1):
            run = range(start, start + len(free))
            inverse = exact_inverse([[self.tonnage[c][b] for c in free] for b in run])
            if inverse is None:
                continue
            for i, carrier in enumerate(free):
                centre = sum(inverse[i][j] * (low[b] + high[b]) for j, b in enumerate(run)) / 2
                radius = sum(abs(inverse[i][j]) * (high[b] - low[b]) for j, b in enumerate(run)) / 2
                found[carrier] = {k for k in found[carrier] if abs(FACTORS[k] - centre) <= radius}
        return found

    def solve(self, first_only: bool = False) -> list[dict]:
        fits: list[dict] = []
        self.descend({}, fits, first_only)
        return fits

    def descend(self, fixed: dict, fits: list, first_only: bool) -> None:
        while True:
            if len(fixed) == len(self.carriers):
                self.match_roundings(fixed, fits)
                return
            options = self.open_factors(fixed)
            if any(not factors for factors in options.values()):
                return
            settled = {c: next(iter(f)) for c, f in options.items() if len(f) == 1}
            if not settled:
                break
            fixed = {**fixed, **settled}
        carrier = min(options, key=lambda c: (len(options[c]), c))
        for factor in sorted(options[carrier]):
            self.descend({**fixed, carrier: factor}, fits, first_only)
            if first_only and fits:
                return

    def match_roundings(self, factors: dict, fits: list) -> None:
        """Every choice of roundings whose credits add up to every batch total, met in the middle."""
        order = sorted(factors)
        middle = len(order) // 2

        def sums(group: list[str]) -> dict[tuple, list[int]]:
            table: dict[tuple, list[int]] = {(): [0] * len(self.batches)}
            for carrier in group:
                table = {picks + (rounding,): [x + y for x, y in zip(total, self.credits(carrier, (*factors[carrier], rounding)))]
                         for picks, total in table.items() for rounding in ROUNDING}
            return table
        first: dict[tuple, list[tuple]] = {}
        for picks, total in sums(order[:middle]).items():
            first.setdefault(tuple(total), []).append(picks)
        for picks, total in sums(order[middle:]).items():
            for head in first.get(tuple(t - x for t, x in zip(self.targets, total)), ()):
                chosen = head + picks
                fits.append({c: (*factors[c], chosen[i]) for i, c in enumerate(order)})


def recover_weighbridge(batches: list[dict]) -> list[tuple]:
    """The periods of fixed settings, [(first instant or None, settings)], that the dated batches show.

    In weighing order, a prefix of the batches that some assignment reproduces stays reproducible when it
    is cut shorter, so the longest such prefix is found by bisection. When it is not the whole list, the
    settings change at the first batch after it: the prefix and the rest must each admit exactly one
    assignment, and the later one must miss the last earlier batch, or the change has no single place.
    """
    order = sorted(batches, key=lambda b: (instant(b["weighed_at"]), b["batch_id"]))
    whole = Calibration(order).solve()
    if len(whole) > 1:
        raise ValueError("the calibration batches admit more than one assignment")
    if whole:
        return [(None, whole[0])]
    fits, misses = 0, len(order)  # order[:fits] is reproducible, order[:misses] is not
    while misses - fits > 1:
        middle = (fits + misses) // 2
        if Calibration(order[:middle]).solve(first_only=True):
            fits = middle
        else:
            misses = middle
    before = Calibration(order[:fits]).solve()
    after = Calibration(order[fits:]).solve()
    if len(before) != 1 or len(after) != 1:
        raise ValueError("no split of the calibration batches settles the weighbridge settings")
    last = order[fits - 1]
    if sum(credit(l["quantity"], after[0][l["carrier"]]) for l in last["loads"]) == int(last["credited_kg"]):
        raise ValueError("the change of weighbridge settings has no single place among the batches")
    return [(None, before[0]), (instant(order[fits]["weighed_at"]), after[0])]


# --------------------------------------------------------------------------- calendar

class Calendar:
    def __init__(self, rows: list[dict], periods: list[dict]) -> None:
        self.periods = sorted(
            (datetime.strptime(p["from_local"], "%Y-%m-%d %H:%M"), offset_seconds(p["utc_offset"]))
            for p in periods
        )
        self.ids = [row["week_id"] for row in rows]
        self.opening = self.local(rows[0]["opens_at"])
        self.closes = [self.local(row["closes_at"]) for row in rows]

    def local(self, text: str) -> int:
        wall = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M")
        offset = None
        for start, seconds in self.periods:
            if start <= wall:
                offset = seconds
        if offset is None:
            raise ValueError(f"no cooperative-time period covers {text!r}")
        return int(wall.replace(tzinfo=timezone(timedelta(seconds=offset))).timestamp())

    def week_of(self, moment: int) -> int | None:
        """Weeks run from just after the opening cutoff up to and including the closing cutoff."""
        if moment <= self.opening or moment > self.closes[-1]:
            return None
        low, high = 0, len(self.closes) - 1
        while low < high:
            mid = (low + high) // 2
            if moment <= self.closes[mid]:
                high = mid
            else:
                low = mid + 1
        return low


# --------------------------------------------------------------------------- identity, areas, CRM, parameters

class Identity:
    def __init__(self, rows: list[dict], contract_ids: set[str]) -> None:
        self.contract_ids = contract_ids
        self.events = sorted(
            (instant(r["effective_at"]), r["event_id"], r["kind"], r["code"], r["target"]) for r in rows
        )

    def resolve(self, ref: str, moment: int) -> str | None:
        ref = ref.strip().upper()
        live = [e for e in self.events if e[0] <= moment]
        if ref in self.contract_ids:
            who = ref
        else:
            aliases = [e[4] for e in live if e[2] == "alias" and e[3] == ref]
            if not aliases:
                return None
            who = aliases[-1]
        merged = {}
        for event in live:
            if event[2] == "merge":
                merged[event[3]] = event[4]
        visited = {who}
        while who in merged:
            who = merged[who]
            if who in visited:
                break
            visited.add(who)
        return who

    def retired(self, customer: str, moment: int) -> bool:
        state = False
        for event in self.events:
            if event[0] > moment:
                break
            if event[3] == customer and event[2] in ("retire", "reactivate"):
                state = event[2] == "retire"
        return state


class ServiceAreas:
    def __init__(self, doc: dict) -> None:
        self.by_customer: dict[str, list] = {}
        for entry in doc["assignments"]:
            self.by_customer.setdefault(entry["customer_id"], []).append(
                (instant(entry["effective_from"]), entry["depot"])
            )
        for spans in self.by_customer.values():
            spans.sort()

    def depot_at(self, customer: str, moment: int) -> str | None:
        found = None
        for start, depot in self.by_customer.get(customer, []):
            if start <= moment:
                found = depot
        return found


class CriticalRoutes:
    def __init__(self, accounts: list[dict], route_codes: dict[str, str], critical_routes: set[str]) -> None:
        self.rows: dict[str, list] = {}
        for acct in accounts:
            key = (instant(acct["updated_at"]), int(acct["revision"]))
            self.rows.setdefault(acct["customer_id"], []).append((key, acct))
        for rows in self.rows.values():
            rows.sort(key=lambda item: item[0])
        self.route_codes = route_codes
        self.critical_routes = critical_routes

    def critical_at(self, customer: str, moment: int) -> bool:
        current = None
        for (updated, _revision), acct in self.rows.get(customer, []):
            if updated <= moment:
                current = acct
        if current is None:
            return False
        if current["route_source"] == "contract":
            return self.route_codes.get(customer, "") in self.critical_routes
        return current["critical_route"] is True


class Parameters:
    def __init__(self, versions: list[dict]) -> None:
        self.versions = sorted(versions, key=lambda v: (instant(v["effective_at"]), v["version_id"]))

    def at(self, moment: int) -> tuple[str | None, dict]:
        values = dict(PARAMETER_DEFAULTS)
        latest = None
        for version in self.versions:
            if instant(version["effective_at"]) > moment:
                break
            if version["mode"] == "replace":
                values = dict(PARAMETER_DEFAULTS)
            values.update(version["values"])
            latest = version["version_id"]
        return latest, values


# --------------------------------------------------------------------------- lots

@dataclass
class Lot:
    order_id: str
    placed: int
    week: int
    depot: str
    holder: str
    quantity: int
    offer_weeks: int
    basis: str
    delivered: dict = field(default_factory=dict)
    lapsed: tuple | None = None
    withdrawn: tuple | None = None

    @property
    def delivered_total(self) -> int:
        return sum(self.delivered.values())

    @property
    def open_quantity(self) -> int:
        if self.lapsed or self.withdrawn:
            return 0
        return self.quantity - self.delivered_total

    def delivered_before(self, week: int) -> int:
        return sum(kg for w, kg in self.delivered.items() if w < week)

    def on_offer(self, week: int) -> bool:
        return self.week <= week <= self.week + self.offer_weeks - 1 and self.open_quantity > 0


def entitlement(lot: Lot, week: int) -> tuple[int, int]:
    """(entitled, delivered) contribution of a lot to season-to-date figures at a week."""
    got = lot.delivered_before(week)
    if lot.basis == "ordered":
        return lot.quantity, got
    if lot.basis == "delivered":
        return got, got
    return 0, 0


# --------------------------------------------------------------------------- the extract

class Extract:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calendar = Calendar(read_csv(root / "season_calendar.csv"),
                                 read_json(root / "cooperative_time.json")["periods"])
        network = ET.parse(root / "depots.xml").getroot()
        self.depots: dict[str, tuple[str, int]] = {}
        for node in network.findall("depot"):
            self.depots[node.get("code")] = (node.get("region"), int(node.findtext("opening_stock_kg").strip()))
        critical = {r.get("code") for r in network.iter("route") if r.get("critical") == "yes"}
        contracts = read_csv(root / "contracts.csv")
        self.segment = {c["customer_id"]: c["segment"] for c in contracts}
        self.contract_min = {c["customer_id"]: tonnes_to_kg(c["contract_min_t"]) for c in contracts}
        route_codes = {c["customer_id"]: (c.get("route_code") or "").strip() for c in contracts}
        self.identity = Identity(read_csv(root / "identity_events.csv"), set(self.segment))
        self.areas = ServiceAreas(read_json(root / "service_areas.json"))
        self.routes = CriticalRoutes(read_json(root / "crm_accounts.json")["accounts"], route_codes, critical)
        self.parameters = Parameters(read_json(root / "allocation_parameters.json")["versions"])
        self.classes = {
            row["class_code"]: (int(row["offer_weeks"]), row["entitlement_basis"])
            for row in read_csv(root / "order_classes.csv")
        }
        self.orders = read_csv(root / "orders.csv")
        self.board = read_csv(root / "dispatch_board_final.csv")
        lines = (root / "order_amendments.jsonl").read_text(encoding="utf-8").splitlines()
        self.amendments = [json.loads(line) for line in lines if line.strip()]
        latest: dict[str, dict] = {}
        for row in read_csv(root / "receipts.csv"):
            latest.pop(row["receipt_id"], None)  # a re-keyed load: the last row in the file is in force
            latest[row["receipt_id"]] = row
        self.receipts = list(latest.values())
        self.periods = recover_weighbridge(read_json(root / "carrier_calibration.json")["batches"])
        final = self.calendar.closes[-1]
        self.weighbridge = {c: self.setting(c, final) for c in self.periods[0][1]}  # in force at the last closing cutoff
        # receipts may key a carrier with spaces around it or in other letter case
        self.carrier_names = {name.strip().upper(): name for name in self.weighbridge}

    def carrier(self, keyed: str) -> str:
        return self.carrier_names[keyed.strip().upper()]

    def setting(self, carrier: str, at: int) -> tuple:
        """The settings in force for the carrier at an instant."""
        chosen = self.periods[0][1]
        for start, settings in self.periods[1:]:
            if at >= start:
                chosen = settings
        return chosen[carrier]


def screen_orders(ex: Extract):
    """Void marks, net amendments, orphans and lots."""
    void: set[str] = set()
    for line in sorted(ex.board, key=lambda b: b["board_line"]):
        if line["status"] != "VOID-DUP":
            continue
        po = line["po_number"].strip()  # a board line may carry spaces around its purchase order number
        pool = [o["order_id"] for o in ex.orders if o["po_number"] == po and o["order_id"] not in void]
        if pool:
            void.add(max(pool))
    live_pos = {o["po_number"] for o in ex.orders if o["order_id"] not in void}
    final_qty: dict[str, int] = {}
    cancelled: dict[str, bool] = {}
    unmatched: set[str] = set()
    for amendment in sorted(ex.amendments, key=lambda a: int(a["seq"])):
        po = amendment["po_number"]
        if po not in live_pos:
            unmatched.add(po)
        elif amendment["action"] == "set_quantity":
            final_qty[po] = tonnes_to_kg(amendment["quantity_t"])
        elif amendment["action"] == "cancel":
            cancelled[po] = True
        elif amendment["action"] == "reinstate":
            cancelled[po] = False
    amended = set(final_qty) | set(cancelled)
    corrections, orphans, lots = [], [], []
    for order in ex.orders:
        if order["order_id"] in void:
            continue
        po = order["po_number"]
        quantity = final_qty.get(po, tonnes_to_kg(order["quantity_t"]))
        gone = cancelled.get(po, False)
        if po in amended:
            corrections.append({"po_number": po, "order_id": order["order_id"],
                                "final_quantity_kg": quantity, "cancelled": gone})
        if gone:
            continue
        reason, lot = classify(ex, order, quantity)
        if reason:
            orphans.append({"order_id": order["order_id"], "customer_ref": order["customer_ref"], "reason": reason})
        else:
            lots.append(lot)
    return void, corrections, unmatched, orphans, lots


def classify(ex: Extract, order: dict, quantity: int):
    placed = instant(order["placed_at"])
    week = ex.calendar.week_of(placed)
    if week is None:
        return "out_of_season", None
    customer = ex.identity.resolve(order["customer_ref"], placed)
    if customer is None:
        return "unknown_reference", None
    if ex.identity.retired(customer, placed):
        return "retired_reference", None
    depot = ex.areas.depot_at(customer, placed)
    if depot is None:
        return "unserved", None
    if order["order_class"] not in ex.classes:
        return "unknown_class", None
    offer_weeks, basis = ex.classes[order["order_class"]]
    return None, Lot(order["order_id"], placed, week, depot, customer, quantity, offer_weeks, basis)


# --------------------------------------------------------------------------- one rationed depot-week

def water_fill(caps: dict[str, int], weights: dict[str, int], units: int):
    """Fair shares in units, and the level (None when every cap fits)."""
    if sum(caps.values()) <= units:
        return {c: Fraction(caps[c]) for c in caps}, None
    order = sorted(caps, key=lambda c: (Fraction(caps[c], weights[c]), c))
    left, weight_left = Fraction(units), sum(weights.values())
    pinned: dict[str, Fraction] = {}
    for customer in order:
        level = left / weight_left
        if caps[customer] <= weights[customer] * level:
            pinned[customer] = Fraction(caps[customer])
            left -= caps[customer]
            weight_left -= weights[customer]
        else:
            break
    level = left / weight_left
    shares = {c: pinned.get(c, weights[c] * level) for c in caps}
    return shares, level


FIRST_DIVISOR = Fraction(5, 4)  # d(0) = 1.25
LATER_SLOPE, LATER_OFFSET = 2, Fraction(1, 2)  # d(n) = 2n + 0.5 for n >= 1


def divisor(held: int) -> Fraction:
    return FIRST_DIVISOR if held == 0 else LATER_SLOPE * held + LATER_OFFSET


def priority(weight: int, held: int) -> Fraction:
    return Fraction(weight) / divisor(held)


def whole_units(caps, weights, first_lot, tie_break, units):
    """Hand out whole units one at a time to the highest priority, within caps.

    A customer holding no unit yet has priority weight / 1.25; one holding n units has weight / (2n + 0.5).
    Equal priorities go to the customer the tie-break in force puts first. Every unit priced strictly above
    a level is handed out before any other, so when no more than the units to hand out lie above a level,
    they are granted at once; the level comes from the share each priority implies, proportionally refined.
    The rest go out from a heap of each open customer's next priority, ordered by priority and then by the
    tie-break, and a customer leaves the heap when it reaches its cap.
    """
    def rank(c):
        if tie_break == "highest_weight":
            return (-weights[c], c)
        if tie_break == "oldest_open_lot":
            return (first_lot[c], c)
        return (c,)

    def above(c, level):
        """Units of customer c priced strictly above the level, at most its cap."""
        reach = Fraction(weights[c]) / level  # a unit counts while its divisor is below this
        if reach <= FIRST_DIVISOR:
            return 0
        return min(caps[c], math.ceil((reach - LATER_OFFSET) / LATER_SLOPE))

    total = min(units, sum(caps.values()))
    granted = {c: 0 for c in caps}
    open_customers = [c for c in caps if caps[c] > 0]
    if total == 0:
        return granted
    level = Fraction(sum(weights[c] for c in open_customers), LATER_SLOPE * total)
    for _ in range(8):
        held = {c: above(c, level) for c in open_customers}
        free = sum(n for c, n in held.items() if n < caps[c])
        need = total - sum(n for c, n in held.items() if n == caps[c])
        if total - 2 * len(open_customers) <= sum(held.values()) <= total or free == 0 or need <= 0:
            break
        level = level * free / need
    while sum(above(c, level) for c in open_customers) > total:
        level *= Fraction(1025, 1024)
    for c in open_customers:
        granted[c] = above(c, level)
    queue = [(-priority(weights[c], granted[c]), rank(c), c) for c in open_customers if granted[c] < caps[c]]
    heapq.heapify(queue)
    for _ in range(total - sum(granted.values())):
        _, key, chosen = heapq.heappop(queue)
        granted[chosen] += 1
        if granted[chosen] < caps[chosen]:
            heapq.heappush(queue, (-priority(weights[chosen], granted[chosen]), key, chosen))
    return granted


def ration(demand, base_bonuses, segment_weight, params, stock, first_lot):
    unit = int(params["allocation_unit_kg"])
    units = stock // unit
    caps = {c: demand[c] // unit for c in demand}
    floor_share = Fraction(params["review_floor"])
    limit = int(params["review_round_limit"])
    reviewed: set[str] = set()

    def weights_with(review: set[str]) -> dict[str, int]:
        out = {}
        for c in demand:
            bonuses = base_bonuses[c] + (1 if c in review else 0)
            if params["bonus_composition"] == "multiplicative":
                out[c] = segment_weight[c] * (2 ** bonuses)
            else:
                out[c] = segment_weight[c] + bonuses
        return out

    def allocate(review):
        weights = weights_with(review)
        shares, level = water_fill(caps, weights, units)
        granted = whole_units(caps, weights, first_lot, params["tie_break"], units)
        return weights, shares, granted, level

    weights, shares, granted, level = allocate(reviewed)
    base = shares  # fair shares before any review bonus
    rounds, settled = 0, True
    while True:
        joining = {c for c in demand if c not in reviewed and base[c] > 0 and granted[c] < floor_share * base[c]}
        if not joining:
            break
        if rounds == limit:
            settled = False
            break
        reviewed |= joining
        rounds += 1
        weights, shares, granted, level = allocate(reviewed)
    whole = sum(s.numerator // s.denominator for s in shares.values())
    return {
        "units": units, "level": level, "whole": whole, "granted_units": sum(granted.values()), "rounds": rounds,
        "settled": settled, "weights": weights, "kg": {c: granted[c] * unit for c in demand}, "reviewed": set(reviewed),
    }


# --------------------------------------------------------------------------- the season

class Season:
    def __init__(self, ex: Extract, lots: list[Lot]) -> None:
        self.ex = ex
        self.lots = lots
        self.weeks = len(ex.calendar.ids)
        self.stock = {d: ex.depots[d][1] for d in ex.depots}
        self.arrived = {d: 0 for d in ex.depots}
        self.sent = {d: 0 for d in ex.depots}
        self.week_rows: list[dict] = []
        self.events: list[dict] = []
        self.allocations: list[dict] = []
        self.boosts: list[tuple[int, str]] = []
        self.parameter_rows: list[dict] = []
        self.rationed_weeks = {d: [] for d in ex.depots}
        self.rationed_kg = 0
        self.merge_moves: list[tuple[str, int]] = []
        self.receipts = self._receipts()

    def _receipts(self) -> dict:
        found: dict = {}
        for row in self.ex.receipts:
            week = self.ex.calendar.week_of(instant(row["arrived_at"]))
            if week is not None:
                key = (row["depot"], week)
                found[key] = found.get(key, 0) + credit(row["quantity"],
                                                     self.ex.setting(self.ex.carrier(row["carrier"]), instant(row["arrived_at"])))
        return found

    def identity_events(self, week: int) -> int:
        withdrawn = 0
        for moment, event_id, kind, code, target in self.ex.identity.events:
            if kind not in ("merge", "retire") or self.ex.calendar.week_of(moment) != week:
                continue
            held = [lot for lot in self.lots if lot.holder == code and lot.placed < moment]
            if kind == "merge":
                self.merge_moves.append((event_id, sum(lot.open_quantity for lot in held)))
                successor = self.ex.identity.resolve(target, moment)
                for lot in held:
                    lot.holder = successor
            else:
                for lot in held:
                    if lot.open_quantity > 0:
                        lot.withdrawn = (week, lot.open_quantity)
                        withdrawn += lot.withdrawn[1]
        return withdrawn

    def deficits(self, week: int, threshold: Fraction) -> set[str]:
        entitled: dict[str, int] = {}
        delivered: dict[str, int] = {}
        for lot in self.lots:
            if lot.week < week:
                e, d = entitlement(lot, week)
                entitled[lot.holder] = entitled.get(lot.holder, 0) + e
                delivered[lot.holder] = delivered.get(lot.holder, 0) + d
        return {c for c in entitled if entitled[c] > 0 and delivered[c] < threshold * entitled[c]}

    def run(self) -> None:
        cal = self.ex.calendar
        for week in range(self.weeks):
            moment = cal.closes[week]
            withdrawn = self.identity_events(week)
            version, params = self.ex.parameters.at(moment)
            self.parameter_rows.append({"week": cal.ids[week], "version_id": version, **params})
            short = self.deficits(week, Fraction(params["deficit_threshold"]))
            received = delivered = rationed_count = unsettled = 0
            boosted: set[str] = set()
            for depot in sorted(self.ex.depots):
                incoming = self.receipts.get((depot, week), 0)
                received += incoming
                self.arrived[depot] += incoming
                stock = self.stock[depot] + incoming
                offer = sorted((lot for lot in self.lots if lot.depot == depot and lot.on_offer(week)),
                               key=lambda lot: (lot.placed, lot.order_id))
                demand: dict[str, int] = {}
                first_lot: dict[str, int] = {}
                for lot in offer:
                    demand[lot.holder] = demand.get(lot.holder, 0) + lot.open_quantity
                    first_lot.setdefault(lot.holder, lot.placed)
                if sum(demand.values()) > stock:
                    rationed_count += 1
                    self.rationed_weeks[depot].append(cal.ids[week])
                    segment_weight, bonuses = {}, {}
                    for c in demand:
                        segment = self.ex.segment[c]
                        segment_weight[c] = int(params["public_weight"] if segment == "public" else params["commercial_weight"])
                        bonuses[c] = int(self.ex.routes.critical_at(c, moment)) + int(c in short)
                    outcome = ration(demand, bonuses, segment_weight, params, stock, first_lot)
                    grant = dict(outcome["kg"])
                    unsettled += 0 if outcome["settled"] else 1
                    self.events.append({
                        "depot": depot, "week": cal.ids[week], "available_kg": stock,
                        "demand_kg": sum(demand.values()), "allocable_units": outcome["units"],
                        "level": fraction_text(outcome["level"]), "whole_part_units": outcome["whole"],
                        "units_granted": outcome["granted_units"],
                        "review_rounds": outcome["rounds"], "settled": outcome["settled"],
                    })
                    for c in sorted(demand):
                        if c in short:
                            boosted.add(c)
                        self.allocations.append({
                            "week": cal.ids[week], "depot": depot, "customer_id": c,
                            "demand_kg": demand[c], "weight": outcome["weights"][c],
                            "reviewed": c in outcome["reviewed"], "allocated_kg": grant[c],
                            "segment": self.ex.segment[c],
                        })
                    self.rationed_kg += sum(grant.values())
                else:
                    grant = dict(demand)
                for lot in offer:
                    portion = min(lot.open_quantity, grant[lot.holder])
                    if portion > 0:
                        lot.delivered[week] = lot.delivered.get(week, 0) + portion
                        grant[lot.holder] -= portion
                        stock -= portion
                        delivered += portion
                        self.sent[depot] += portion
                self.stock[depot] = stock
            lapsed = 0
            for lot in self.lots:
                if lot.week + lot.offer_weeks - 1 == week and lot.open_quantity > 0:
                    lot.lapsed = (week, lot.open_quantity)
                    lapsed += lot.lapsed[1]
            self.boosts.extend((week, c) for c in sorted(boosted))
            self.week_rows.append({
                "week": cal.ids[week], "receipts_kg": received, "delivered_kg": delivered,
                "lapsed_kg": lapsed, "withdrawn_kg": withdrawn,
                "rationed_depots": rationed_count, "unsettled_depots": unsettled,
            })


def fraction_text(value: Fraction | None) -> str | None:
    if value is None:
        return None
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def fill_ratio(delivered: int, ordered: int) -> str:
    scaled = Fraction(delivered * 10000, ordered) + Fraction(1, 2)
    whole = scaled.numerator // scaled.denominator
    return f"{whole // 10000}.{whole % 10000:04d}"


# --------------------------------------------------------------------------- reports

def build_reports(ex: Extract) -> tuple[dict, Season]:
    void, corrections, unmatched, orphans, lots = screen_orders(ex)
    season = Season(ex, lots)
    season.run()
    cal = ex.calendar
    docs: dict[str, dict] = {}

    depot_rows = [{
        "depot": d, "region": ex.depots[d][0], "opening_kg": ex.depots[d][1],
        "receipts_kg": season.arrived[d], "delivered_kg": season.sent[d], "closing_kg": season.stock[d],
        "rationed_weeks": season.rationed_weeks[d],
    } for d in sorted(ex.depots)]
    docs["summary.json"] = {"depots": depot_rows, "weeks": season.week_rows, "true_up": true_up(ex, lots)}

    docs["policy_audit.json"] = {
        "carrier_settings": [
            {"carrier": c, "unit": u, "moisture_deduction": d, "rounding": r}
            for c, (u, d, r) in sorted(ex.weighbridge.items())
        ],
        "parameters": season.parameter_rows,
        "rationing_events": season.events,
        "deficit_boosts": [{"week": cal.ids[w], "customer_id": c} for w, c in season.boosts],
    }

    stock = {key: sum(row[key] for row in depot_rows) for key in ("opening_kg", "receipts_kg", "delivered_kg", "closing_kg")}
    stock["residual_kg"] = stock["opening_kg"] + stock["receipts_kg"] - stock["delivered_kg"] - stock["closing_kg"]
    demand = {
        "ordered_kg": sum(l.quantity for l in lots),
        "delivered_kg": sum(l.delivered_total for l in lots),
        "lapsed_kg": sum(l.lapsed[1] for l in lots if l.lapsed),
        "withdrawn_kg": sum(l.withdrawn[1] for l in lots if l.withdrawn),
        "open_at_close_kg": sum(l.open_quantity for l in lots),
    }
    demand["residual_kg"] = (demand["ordered_kg"] - demand["delivered_kg"] - demand["lapsed_kg"]
                             - demand["withdrawn_kg"] - demand["open_at_close_kg"])
    total_sent = sum(season.sent.values())
    allocation = {"rationed_kg": season.rationed_kg, "unrationed_kg": total_sent - season.rationed_kg,
                  "delivered_kg": total_sent}
    allocation["residual_kg"] = allocation["delivered_kg"] - allocation["rationed_kg"] - allocation["unrationed_kg"]
    by_id = sorted(lots, key=lambda l: l.order_id)
    docs["data_quality.json"] = {
        "orphan_orders": sorted(orphans, key=lambda r: r["order_id"]),
        "voided_orders": sorted(void),
        "amendments": sorted(corrections, key=lambda r: (r["po_number"], r["order_id"])),
        "unmatched_amendments": sorted(unmatched),
        "lapsed_lots": [{"order_id": l.order_id, "customer_id": l.holder, "depot": l.depot,
                         "week": cal.ids[l.lapsed[0]], "lapsed_kg": l.lapsed[1]} for l in by_id if l.lapsed],
        "withdrawn_lots": [{"order_id": l.order_id, "customer_id": l.holder, "depot": l.depot,
                            "week": cal.ids[l.withdrawn[0]], "withdrawn_kg": l.withdrawn[1]} for l in by_id if l.withdrawn],
        "reconciliation": {"stock": stock, "demand": demand, "allocation": allocation},
    }

    for region in REGIONS:
        members = sorted(d for d in ex.depots if ex.depots[d][0] == region)
        count = sum(len(season.rationed_weeks[d]) for d in members)
        docs[f"region_{region}.json"] = (regional(ex, lots, region, members, count) if count
                                         else {"region": region, "in_scope": False})
    for segment in SEGMENTS:
        rows = [a for a in season.allocations if a["segment"] == segment]
        if not rows:
            docs[f"segment_{segment}.json"] = {"segment": segment, "in_scope": False}
            continue
        held = [l for l in lots if ex.segment[l.holder] == segment]
        docs[f"segment_{segment}.json"] = {
            "segment": segment, "in_scope": True,
            "customer_count": len({l.holder for l in held}),
            "ordered_kg": sum(l.quantity for l in held),
            "delivered_kg": sum(l.delivered_total for l in held),
            "lapsed_kg": sum(l.lapsed[1] for l in held if l.lapsed),
            "rationed_allocations": [{k: v for k, v in a.items() if k != "segment"} for a in rows],
        }
    return docs, season


def true_up(ex: Extract, lots: list[Lot]) -> list[dict]:
    final = ex.calendar.closes[-1]
    owed = []
    for customer in sorted(ex.segment):
        minimum = ex.contract_min[customer]
        if ex.segment[customer] != "public" or minimum <= 0:
            continue
        if ex.identity.resolve(customer, final) != customer or ex.identity.retired(customer, final):
            continue
        mine = [l for l in lots if l.holder == customer]
        ordered = sum(l.quantity for l in mine)
        delivered = sum(l.delivered_total for l in mine)
        credit = min(minimum, ordered) - delivered
        if credit > 0:
            owed.append({"customer_id": customer, "contract_min_kg": minimum,
                         "delivered_kg": delivered, "credit_kg": credit})
    return owed


def regional(ex: Extract, lots: list[Lot], region: str, members: list[str], count: int) -> dict:
    rows: dict[str, dict] = {}
    weekly = {w: 0 for w in ex.calendar.ids}
    for lot in lots:
        if lot.depot not in members:
            continue
        row = rows.setdefault(lot.holder, {
            "customer_id": lot.holder, "segment": ex.segment[lot.holder], "ordered_kg": 0,
            "delivered_kg": 0, "lapsed_kg": 0, "withdrawn_kg": 0, "open_at_close_kg": 0,
        })
        row["ordered_kg"] += lot.quantity
        row["delivered_kg"] += lot.delivered_total
        row["lapsed_kg"] += lot.lapsed[1] if lot.lapsed else 0
        row["withdrawn_kg"] += lot.withdrawn[1] if lot.withdrawn else 0
        row["open_at_close_kg"] += lot.open_quantity
        for week, kg in lot.delivered.items():
            weekly[ex.calendar.ids[week]] += kg
    for row in rows.values():
        row["fill_ratio"] = fill_ratio(row["delivered_kg"], row["ordered_kg"])
    return {"region": region, "in_scope": True, "depots": members, "rationed_depot_weeks": count,
            "customers": [rows[c] for c in sorted(rows)], "weekly_delivered_kg": weekly}


def write_reports(docs: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(docs):
        text = json.dumps(docs[name], indent=2, sort_keys=True) + "\n"
        (out_dir / name).write_text(text, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    docs, _season = build_reports(Extract(Path(argv[1])))
    write_reports(docs, Path(argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
