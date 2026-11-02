#!/usr/bin/env python3
"""Clear one revenue epoch of a transit interchange.

Usage: clear_epoch.py <register_dir> <output_dir>

Reads the machine readable registers of an epoch plus the calibration
material that travels with them, recovers the seven interchange properties
that the rulebooks leave unstated, clears the epoch, and writes the cleared
account, the netting layer and the assurance layer.
"""

import csv
import itertools
import json
import os
import sys
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# register loading
# --------------------------------------------------------------------------

CSV_REGISTERS = {
    "epoch_calendar": "epoch_calendar.csv",
    "epoch_policy": "epoch_policy.csv",
    "operators": "operators.csv",
    "zones": "zones.csv",
    "gates": "gates.csv",
    "tariff_tables": "tariff_tables.csv",
    "gate_faults": "gate_faults.csv",
    "token_events": "token_events.csv",
    "taps": "taps.csv",
    "netting_policy": "netting_policy.csv",
    "assurance_policy": "assurance_policy.csv",
}


def load_registers(path):
    reg = {}
    for name, fname in CSV_REGISTERS.items():
        full = os.path.join(path, fname)
        rows = []
        if os.path.exists(full):
            with open(full, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    rows.append({k: (v if v is not None else "") for k, v in row.items()})
        reg[name] = rows
    exc = os.path.join(path, "exceptions.json")
    if os.path.exists(exc):
        with open(exc, encoding="utf-8") as fh:
            blob = json.load(fh)
        reg["exceptions"] = blob["exceptions"] if isinstance(blob, dict) else blob
    else:
        reg["exceptions"] = []
    return reg


def load_calibration(path):
    full = os.path.join(path, "calibration_controls.json")
    with open(full, encoding="utf-8") as fh:
        return json.load(fh)


def as_int(value, default=0):
    text = str(value).strip()
    if text == "":
        return default
    return int(text)


def as_bool(value):
    text = str(value).strip().lower()
    return text in ("1", "true", "yes", "y", "t")


def parse_instant(text):
    text = str(text).strip()
    if text == "":
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    stamp = datetime.fromisoformat(text)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def parse_clock(text):
    hh, mm = str(text).strip().split(":")[:2]
    return int(hh) * 60 + int(mm)


# --------------------------------------------------------------------------
# settlement grid
# --------------------------------------------------------------------------


def place(num, den, step, rule):
    """Place num/den on the grid of whole multiples of ``step``."""
    if den < 0:
        num, den = -num, -den
    unit = den * step
    k = num // unit  # floor
    rem = num - k * unit
    twice = 2 * rem
    if twice < unit:
        chosen = k
    elif twice > unit:
        chosen = k + 1
    elif rule == "to_even_multiple":
        chosen = k if k % 2 == 0 else k + 1
    elif rule == "to_odd_multiple":
        chosen = k if k % 2 != 0 else k + 1
    elif rule == "away_from_zero":
        chosen = k + 1
    elif rule == "toward_zero":
        chosen = k
    else:
        raise ValueError("unknown midpoint rule %r" % (rule,))
    return chosen * step


def trunc_div(num, den):
    """Integer division truncating toward zero."""
    quo = abs(num) // abs(den)
    if (num < 0) != (den < 0):
        quo = -quo
    return quo


def interval_holds(convention, start, instant, end):
    if start is not None:
        if convention in ("closed_closed", "closed_open"):
            if instant < start:
                return False
        else:
            if instant <= start:
                return False
    if end is not None:
        if convention in ("closed_closed", "open_closed"):
            if instant > end:
                return False
        else:
            if instant >= end:
                return False
    return True


# --------------------------------------------------------------------------
# the clearance
# --------------------------------------------------------------------------

class Interchange:
    """Everything about an epoch that does not depend on the seven properties."""

    def __init__(self, reg):
        self.reg = reg
        self._abatements = {}

        calendar = sorted(reg["epoch_calendar"], key=lambda r: str(r["epoch_id"]))
        if not calendar:
            raise ValueError("the epoch calendar names no epoch")
        cal = calendar[0]
        self.epoch_id = str(cal["epoch_id"])
        self.opens_at_text = str(cal["opens_at"])
        self.closes_at_text = str(cal["closes_at"])
        self.opens_at = parse_instant(cal["opens_at"])
        self.closes_at = parse_instant(cal["closes_at"])

        policies = [r for r in reg["epoch_policy"] if str(r["epoch_id"]) == self.epoch_id]
        if not policies:
            policies = sorted(reg["epoch_policy"], key=lambda r: str(r["epoch_id"]))
        pol = policies[0]
        self.boundary = str(pol["boundary"]).strip()
        self.peak_from = parse_clock(pol["peak_from"])
        self.peak_to = parse_clock(pol["peak_to"])

        self.operators = {}
        for row in reg["operators"]:
            oid = str(row["operator_id"])
            self.operators[oid] = {
                "operator_id": oid,
                "clearing_rank": as_int(row["clearing_rank"]),
                "float_ceiling_micros": as_int(row["float_ceiling_micros"]),
                "funding_ceiling_micros": as_int(row["funding_ceiling_micros"]),
            }
        self.operator_ids = sorted(self.operators)

        self.zones = {}
        for row in reg["zones"]:
            zid = str(row["zone_id"])
            self.zones[zid] = {
                "zone_id": zid,
                "operator_id": str(row["operator_id"]),
                "tariff_band": as_int(row["tariff_band"]),
                "validation_floor": as_int(row["validation_floor"]),
                "revenue_cap_micros": as_int(row["revenue_cap_micros"]),
                "provisional": as_bool(row["provisional"]),
            }
        self.zone_ids = sorted(self.zones)
        self.zones_of_operator = {oid: [] for oid in self.operator_ids}
        for zid in self.zone_ids:
            self.zones_of_operator.setdefault(self.zones[zid]["operator_id"], []).append(zid)

        self.gates = {}
        for row in reg["gates"]:
            gid = str(row["gate_id"])
            self.gates[gid] = {
                "gate_id": gid,
                "zone_id": str(row["zone_id"]),
                "gate_class": str(row.get("gate_class", "")),
                "fault_allowance_bp": as_int(row["fault_allowance_bp"]),
                "floor_fare_micros": as_int(row["floor_fare_micros"]),
                "decommissioned": as_bool(row["decommissioned"]),
            }
        self.gate_ids = sorted(self.gates)
        self.gates_of_zone = {zid: [] for zid in self.zone_ids}
        for gid in self.gate_ids:
            self.gates_of_zone.setdefault(self.gates[gid]["zone_id"], []).append(gid)

        self.tables = []
        for row in reg["tariff_tables"]:
            self.tables.append(
                {
                    "table_id": str(row["table_id"]),
                    "effective_from": parse_instant(row["effective_from"]),
                    "superseded_at": parse_instant(row["superseded_at"]),
                    "rate_peak": as_int(row["rate_peak"]),
                    "rate_offpeak": as_int(row["rate_offpeak"]),
                    "rate_concession": as_int(row["rate_concession"]),
                    "mult_complete": as_int(row["mult_complete"]),
                    "mult_open_exit": as_int(row["mult_open_exit"]),
                    "mult_forced": as_int(row["mult_forced"]),
                    "uplift_bp": as_int(row["uplift_bp"]),
                    "relief_bp": as_int(row["relief_bp"]),
                    "levy_bp": as_int(row["levy_bp"]),
                }
            )

        self.faults = []
        for row in reg["gate_faults"]:
            closed = parse_instant(row["closed_at"])
            self.faults.append(
                {
                    "fault_id": str(row["fault_id"]),
                    "gate_id": str(row["gate_id"]),
                    "opened_at": parse_instant(row["opened_at"]),
                    "closed_at": closed,
                    "open_at_close": closed is None,
                    "abatement_micros": as_int(row["abatement_micros"]),
                }
            )
        self.faults_by_gate = {}
        for fault in self.faults:
            self.faults_by_gate.setdefault(fault["gate_id"], []).append(fault)

        self.events = []
        for row in reg["token_events"]:
            self.events.append(
                {
                    "event_id": str(row["event_id"]),
                    "effective_at": parse_instant(row["effective_at"]),
                    "event_type": str(row["event_type"]).strip(),
                    "subject_ref": str(row["subject_ref"]).strip(),
                    "target_ref": str(row["target_ref"]).strip(),
                }
            )
        self.redirects = {}
        self.terminals = {}
        for ev in self.events:
            if ev["event_type"] in ("rotate", "merge"):
                self.redirects.setdefault(ev["subject_ref"], []).append(ev)
            elif ev["event_type"] in ("retire", "revoke"):
                self.terminals.setdefault(ev["subject_ref"], []).append(ev)

        self.exceptions = []
        for row in reg["exceptions"]:
            self.exceptions.append(
                {
                    "exception_id": str(row["exception_id"]),
                    "tap_id": str(row["tap_id"]),
                    "status": str(row["status"]).strip(),
                    "unit_fare_micros": as_int(row["unit_fare_micros"]),
                }
            )

        taps = []
        for index, row in enumerate(reg["taps"]):
            gate_id = str(row["gate_id"])
            gate = self.gates.get(gate_id)
            zone_id = gate["zone_id"] if gate else ""
            zone = self.zones.get(zone_id)
            taps.append(
                {
                    "tap_id": str(row["tap_id"]),
                    "token_ref": str(row["token_ref"]),
                    "gate_id": gate_id,
                    "zone_id": zone_id,
                    "operator_id": zone["operator_id"] if zone else "",
                    "tapped_at": parse_instant(row["tapped_at"]),
                    "tapped_at_text": str(row["tapped_at"]),
                    "distance_units": as_int(row["distance_units"]),
                    "rider_class": str(row["rider_class"]),
                    "completion_class": str(row["completion_class"]),
                    "op": str(row["op"]).strip(),
                    "source_index": index,
                }
            )
        taps.sort(key=lambda t: (t["tapped_at"], t["tap_id"], t["source_index"]))
        self.taps = taps
        for pos, tap in enumerate(taps):
            tap["pos"] = pos
            minute = tap["tapped_at"].hour * 60 + tap["tapped_at"].minute
            tap["peak"] = self.peak_from <= minute < self.peak_to

        # admission: A1, A3, A4 do not depend on any recovered property
        self.in_epoch = []
        self.out_of_epoch = []
        for tap in taps:
            if interval_holds(self.boundary, self.opens_at, tap["tapped_at"], self.closes_at):
                self.in_epoch.append(tap)
            else:
                self.out_of_epoch.append(tap)

        seen = {}
        self.duplicate_positions = set()
        self.duplicate_tap_ids = set()
        for tap in self.in_epoch:
            if tap["tap_id"] in seen:
                self.duplicate_positions.add(tap["pos"])
                self.duplicate_tap_ids.add(tap["tap_id"])
            else:
                seen[tap["tap_id"]] = tap["pos"]

        self.taps_at_gate = {gid: [] for gid in self.gate_ids}
        for tap in self.in_epoch:
            self.taps_at_gate.setdefault(tap["gate_id"], []).append(tap)

        self.identity = {}
        for tap in self.in_epoch:
            self.identity[tap["pos"]] = self.resolve_identity(tap)

        # I6 home operator: earliest admitted tap in canonical order
        self.home_operator = {}
        for tap in self.in_epoch:
            token = self.identity[tap["pos"]]["canonical_token"]
            if token not in self.home_operator:
                self.home_operator[token] = tap["operator_id"]

        self.taps_by_identity = {}
        for tap in self.in_epoch:
            token = self.identity[tap["pos"]]["canonical_token"]
            self.taps_by_identity.setdefault(token, []).append(tap)

        netting = sorted(reg["netting_policy"], key=lambda r: str(sorted(r.items())))
        npol = netting[0] if netting else {}
        self.interchange_share_bp = as_int(npol.get("interchange_share_bp", 0))
        self.netting_multiplier = as_int(npol.get("netting_multiplier", 0))
        self.netting_modulus = as_int(npol.get("netting_modulus", 1), 1)

        assur = sorted(reg["assurance_policy"], key=lambda r: str(sorted(r.items())))
        apol = assur[0] if assur else {}
        self.assurance_sigma = as_int(apol.get("assurance_sigma", 0))
        self.assurance_multiplier = as_int(apol.get("assurance_multiplier", 0))
        self.assurance_modulus = as_int(apol.get("assurance_modulus", 1), 1)
        self.min_sample = as_int(apol.get("min_sample", 0))

    # -- identity ---------------------------------------------------------

    def resolve_identity(self, tap):
        instant = tap["tapped_at"]
        chain = [tap["token_ref"]]
        current = tap["token_ref"]
        seen = {current}
        outcome = None
        while True:
            candidates = [
                ev
                for ev in self.redirects.get(current, [])
                if ev["effective_at"] <= instant
            ]
            if not candidates:
                break
            chosen = max(candidates, key=lambda ev: (ev["effective_at"], ev["event_id"]))
            target = chosen["target_ref"]
            chain.append(target)
            if target in seen:
                outcome = "cycle_broken"
                break
            seen.add(target)
            current = target

        if outcome == "cycle_broken":
            # the cycle is the tail of the chain from the repeated identity
            repeat = chain[-1]
            start = chain.index(repeat)
            cycle = chain[start:-1]
            canonical = min(cycle)
        else:
            canonical = chain[-1]

        terminal = None
        for member in chain:
            for ev in self.terminals.get(member, []):
                if ev["effective_at"] <= instant:
                    if ev["event_type"] == "revoke":
                        terminal = "revoke"
                    elif terminal != "revoke":
                        terminal = "retire"
        if terminal == "revoke":
            outcome = "revoked"
        elif terminal == "retire":
            outcome = "retired"
        elif outcome is None:
            outcome = "direct" if len(chain) == 1 else "rotated"

        return {"canonical_token": canonical, "outcome": outcome, "chain": chain}

    # -- tariff -----------------------------------------------------------

    def governing_table(self, instant):
        live = [
            tbl
            for tbl in self.tables
            if tbl["effective_from"] <= instant
            and (tbl["superseded_at"] is None or instant < tbl["superseded_at"])
        ]
        if not live:
            return None
        return max(live, key=lambda tbl: (tbl["effective_from"], tbl["table_id"]))

    def abatement_for(self, tap, edge):
        key = (tap["pos"], edge)
        hit = self._abatements.get(key)
        if hit is None:
            hit = self._abatement_for(tap, edge)
            self._abatements[key] = hit
        return hit

    def _abatement_for(self, tap, edge):
        best = 0
        for fault in self.faults_by_gate.get(tap["gate_id"], []):
            end = fault["closed_at"] if fault["closed_at"] is not None else self.closes_at
            if interval_holds(edge, fault["opened_at"], tap["tapped_at"], end):
                if fault["abatement_micros"] > best:
                    best = fault["abatement_micros"]
        return best


def price_taps(ix, params):
    """Unit fares of every admitted tap that the tariff rulebook consumes."""
    step = params["grid_step_micros"]
    rule = params["midpoint_rule"]
    order = params["adjustment_order"]
    basis_name = params["levy_basis"]
    edge = params["fault_window_edge"]

    priced = {}
    for tap in ix.in_epoch:
        ident = ix.identity[tap["pos"]]
        if ident["outcome"] in ("retired", "revoked"):
            continue
        table = ix.governing_table(tap["tapped_at"])
        if table is None:
            priced[tap["pos"]] = {"table": None}
            continue
        gate = ix.gates[tap["gate_id"]]
        zone = ix.zones[tap["zone_id"]]
        if tap["rider_class"] == "concession":
            rate = table["rate_concession"]
        elif tap["peak"]:
            rate = table["rate_peak"]
        else:
            rate = table["rate_offpeak"]
        mult = {
            "complete": table["mult_complete"],
            "open_exit": table["mult_open_exit"],
            "forced": table["mult_forced"],
        }[tap["completion_class"]]
        distance_rate_product = rate * tap["distance_units"]
        gross = place(
            distance_rate_product * zone["tariff_band"] * mult, 10000, step, rule
        )
        cross = ix.home_operator[ident["canonical_token"]] != tap["operator_id"]

        value = gross
        for name in order:
            if name == "fault_abatement":
                abatement = ix.abatement_for(tap, edge)
                shifted = value - abatement
                value = place(shifted, 1, step, rule) if shifted > 0 else 0
                if value < 0:
                    value = 0
            elif name == "concession_relief":
                if tap["rider_class"] == "concession":
                    value = place(
                        value * (10000 - table["relief_bp"]), 10000, step, rule
                    )
            elif name == "interchange_uplift":
                if cross:
                    value = place(
                        value * (10000 + table["uplift_bp"]), 10000, step, rule
                    )
            elif name == "shortfall_levy":
                if basis_name == "gross_before_adjustments":
                    basis = gross
                elif basis_name == "running_value":
                    basis = value
                elif basis_name == "floor_fare":
                    basis = gate["floor_fare_micros"]
                elif basis_name == "distance_rate_product":
                    basis = distance_rate_product
                else:
                    raise ValueError("unknown levy basis %r" % (basis_name,))
                levy = place(basis * table["levy_bp"], 10000, step, rule)
                value = place(value + levy, 1, step, rule)
            else:
                raise ValueError("unknown adjustment %r" % (name,))

        unit_fare = max(value, gate["floor_fare_micros"])
        priced[tap["pos"]] = {
            "table": table["table_id"],
            "gross": gross,
            "unit_fare": unit_fare,
            "cross": cross,
        }
    return priced


def clear_epoch(ix, params, fares=None):
    """Run the whole clearance and return the cleared account."""
    step = params["grid_step_micros"]
    rule = params["midpoint_rule"]
    if fares is None:
        fares = price_taps(ix, params)

    state = {}
    for tap in ix.taps:
        state[tap["pos"]] = {
            "disposition": "out_of_epoch",
            "reason": "out_of_epoch",
            "table": "",
            "gross": 0,
            "unit_fare": 0,
            "cross": False,
            "canonical_token": "",
            "outcome": "",
            "home_operator": "",
            "exception_id": "",
        }

    def withdraw(pos, reason):
        row = state[pos]
        if row["disposition"] == "priced":
            row["disposition"] = "withdrawn"
            row["reason"] = reason
            return True
        return False

    no_table = []
    for tap in ix.in_epoch:
        pos = tap["pos"]
        ident = ix.identity[pos]
        row = state[pos]
        row["canonical_token"] = ident["canonical_token"]
        row["outcome"] = ident["outcome"]
        row["home_operator"] = ix.home_operator[ident["canonical_token"]]
        row["disposition"] = "priced"
        row["reason"] = ""
        info = fares.get(pos)
        if info is not None and info["table"] is not None:
            row["table"] = info["table"]
            row["gross"] = info["gross"]
            row["unit_fare"] = info["unit_fare"]
            row["cross"] = info["cross"]

    # A3 repeated tap identifiers
    for pos in sorted(ix.duplicate_positions):
        withdraw(pos, "duplicate_tap_id")

    # A4 gates no longer in service
    for tap in ix.in_epoch:
        if ix.gates[tap["gate_id"]]["decommissioned"]:
            withdraw(tap["pos"], "decommissioned_gate")

    # I4 terminal identities
    for tap in ix.in_epoch:
        outcome = state[tap["pos"]]["outcome"]
        if outcome == "revoked":
            withdraw(tap["pos"], "identity_revoked")
        elif outcome == "retired":
            withdraw(tap["pos"], "identity_retired")

    # T1 taps no table governs
    for tap in ix.in_epoch:
        pos = tap["pos"]
        info = fares.get(pos)
        if info is not None and info["table"] is None:
            no_table.append(tap["tap_id"])
            withdraw(pos, "no_governing_table")

    # L4 reversal records and their reach
    reach = params["void_reach"]
    for tap in ix.in_epoch:
        if tap["op"] != "void":
            continue
        pos = tap["pos"]
        withdraw(pos, "reversal_record")
        if reach == "tap_only":
            continue
        token = ix.identity[pos]["canonical_token"]
        for other in ix.taps_by_identity.get(token, []):
            if other["pos"] == pos:
                continue
            if reach == "token_zone_epoch" and other["zone_id"] != tap["zone_id"]:
                continue
            if reach == "token_operator_epoch" and other["operator_id"] != tap["operator_id"]:
                continue
            withdraw(other["pos"], "voided_by_reversal")

    # --- suspension fixpoint -------------------------------------------
    suspended = {}
    for gid in ix.gate_ids:
        if ix.gates[gid]["decommissioned"]:
            suspended[gid] = "decommissioned"
    unvalidated = set()
    stood_down = set()

    def priced_at(gid):
        return sum(
            1 for tap in ix.taps_at_gate.get(gid, []) if state[tap["pos"]]["disposition"] == "priced"
        )

    def burden_of(gid):
        taps = ix.taps_at_gate.get(gid, [])
        if not taps:
            return 0
        defects = sum(
            1 for tap in taps if state[tap["pos"]]["disposition"] == "withdrawn"
        )
        return (10000 * defects) // len(taps)

    iterations = 0
    while True:
        iterations += 1
        changed = False
        for gid in ix.gate_ids:
            if gid in suspended:
                continue
            if burden_of(gid) > ix.gates[gid]["fault_allowance_bp"]:
                suspended[gid] = "burden"
                changed = True
        for zid in ix.zone_ids:
            if zid in unvalidated:
                continue
            count = sum(
                1
                for gid in ix.gates_of_zone.get(zid, [])
                if gid not in suspended and priced_at(gid) > 0
            )
            if count < ix.zones[zid]["validation_floor"]:
                unvalidated.add(zid)
                changed = True
        for zid in ix.zone_ids:
            if zid in unvalidated or not ix.zones[zid]["provisional"]:
                continue
            siblings = ix.zones_of_operator.get(ix.zones[zid]["operator_id"], [])
            if any(other != zid and other in unvalidated for other in siblings):
                unvalidated.add(zid)
                changed = True
        for oid in ix.operator_ids:
            if oid in stood_down:
                continue
            owned = ix.zones_of_operator.get(oid, [])
            if owned and all(zid in unvalidated for zid in owned):
                stood_down.add(oid)
                changed = True
        for gid in ix.gate_ids:
            if gid in suspended:
                continue
            zid = ix.gates[gid]["zone_id"]
            if zid in unvalidated:
                suspended[gid] = "zone_unvalidated"
                changed = True
            elif ix.zones.get(zid, {}).get("operator_id") in stood_down:
                suspended[gid] = "operator_stood_down"
                changed = True
        for gid in ix.gate_ids:
            if gid not in suspended:
                continue
            for tap in ix.taps_at_gate.get(gid, []):
                if withdraw(tap["pos"], "gate_suspended"):
                    changed = True
        if not changed:
            break

    # --- L5 exceptions --------------------------------------------------
    first_by_tap_id = {}
    for tap in ix.taps:
        first_by_tap_id.setdefault(tap["tap_id"], tap)
    exceptions_on_withdrawn = []
    for exc in sorted(ix.exceptions, key=lambda e: e["exception_id"]):
        tap = first_by_tap_id.get(exc["tap_id"])
        if tap is None:
            continue
        if exc["status"] != "upheld":
            continue
        row = state[tap["pos"]]
        if row["disposition"] == "priced":
            row["unit_fare"] = exc["unit_fare_micros"]
            row["exception_id"] = exc["exception_id"]
        else:
            exceptions_on_withdrawn.append(exc["exception_id"])

    # --- capping --------------------------------------------------------
    priced_by_zone = {zid: [] for zid in ix.zone_ids}
    for tap in ix.in_epoch:
        if state[tap["pos"]]["disposition"] == "priced":
            priced_by_zone.setdefault(tap["zone_id"], []).append(tap)

    priced_total_before = {
        zid: sum(state[t["pos"]]["unit_fare"] for t in priced_by_zone.get(zid, []))
        for zid in ix.zone_ids
    }
    headroom = {
        zid: ix.zones[zid]["revenue_cap_micros"] - priced_total_before[zid]
        for zid in ix.zone_ids
    }

    order_name = params["cap_release_order"]
    if order_name == "ascending_zone_id":
        key = lambda zid: (zid,)
    elif order_name == "descending_headroom_then_zone":
        key = lambda zid: (-headroom[zid], zid)
    elif order_name == "ascending_headroom_then_zone":
        key = lambda zid: (headroom[zid], zid)
    elif order_name == "descending_cap_then_zone":
        key = lambda zid: (-ix.zones[zid]["revenue_cap_micros"], zid)
    else:
        raise ValueError("unknown release order %r" % (order_name,))
    release_order = sorted(ix.zone_ids, key=key)

    spare = {zid: headroom[zid] for zid in ix.zone_ids if headroom[zid] > 0}
    need = {zid: -headroom[zid] for zid in ix.zone_ids if headroom[zid] < 0}
    lent = {zid: 0 for zid in ix.zone_ids}
    borrowed = {zid: 0 for zid in ix.zone_ids}
    operator_lent = {oid: 0 for oid in ix.operator_ids}
    loans = []
    for borrower in release_order:
        if borrower not in need or need[borrower] <= 0:
            continue
        oid = ix.zones[borrower]["operator_id"]
        ceiling = ix.operators.get(oid, {}).get("float_ceiling_micros", 0)
        for lender in release_order:
            if need[borrower] <= 0:
                break
            if lender == borrower or lender not in spare or spare[lender] <= 0:
                continue
            if ix.zones[lender]["operator_id"] != oid:
                continue
            amount = min(
                spare[lender], need[borrower], ceiling - operator_lent.get(oid, 0)
            )
            if amount <= 0:
                continue
            spare[lender] -= amount
            need[borrower] -= amount
            lent[lender] += amount
            borrowed[borrower] += amount
            operator_lent[oid] = operator_lent.get(oid, 0) + amount
            loans.append(
                {
                    "from_zone": lender,
                    "to_zone": borrower,
                    "operator_id": oid,
                    "amount_micros": amount,
                }
            )

    effective_cap = {
        zid: ix.zones[zid]["revenue_cap_micros"] + borrowed[zid] for zid in ix.zone_ids
    }

    priced_at_gate = {gid: priced_at(gid) for gid in ix.gate_ids}
    curtailed = {zid: [] for zid in ix.zone_ids}
    residual = {}
    for zid in release_order:
        total = priced_total_before[zid]
        cap = effective_cap[zid]
        if total > cap:
            candidates = sorted(
                priced_by_zone.get(zid, []),
                key=lambda t: (-state[t["pos"]]["unit_fare"], t["tapped_at"], t["tap_id"]),
            )
            for tap in candidates:
                if total <= cap:
                    break
                gid = tap["gate_id"]
                if gid not in suspended and priced_at_gate.get(gid, 0) == 1:
                    continue
                if withdraw(tap["pos"], "cap_curtailed"):
                    total -= state[tap["pos"]]["unit_fare"]
                    priced_at_gate[gid] = priced_at_gate.get(gid, 0) - 1
                    curtailed[zid].append(tap["tap_id"])
        residual[zid] = max(0, total - cap)

    priced_total_after = {
        zid: sum(
            state[t["pos"]]["unit_fare"]
            for t in priced_by_zone.get(zid, [])
            if state[t["pos"]]["disposition"] == "priced"
        )
        for zid in ix.zone_ids
    }

    # --- the ledger -----------------------------------------------------
    running = 0
    ledger = []
    for tap in ix.taps:
        row = state[tap["pos"]]
        if row["disposition"] == "priced":
            running += row["unit_fare"]
        ledger.append(
            {
                "tap_id": tap["tap_id"],
                "canonical_token": row["canonical_token"],
                "identity_outcome": row["outcome"],
                "gate_id": tap["gate_id"],
                "zone_id": tap["zone_id"],
                "operator_id": tap["operator_id"],
                "home_operator_id": row["home_operator"],
                "tapped_at": tap["tapped_at_text"],
                "distance_units": tap["distance_units"],
                "rider_class": tap["rider_class"],
                "completion_class": tap["completion_class"],
                "op": tap["op"],
                "governing_table_id": row["table"],
                "peak": tap["peak"],
                "cross_operator": row["cross"],
                "gross_before_adjustments_micros": row["gross"],
                "unit_fare_micros": row["unit_fare"],
                "disposition": row["disposition"],
                "withdrawal_reason": row["reason"] if row["disposition"] != "priced" else "",
                "exception_id": row["exception_id"],
                "running_charge_micros": running,
            }
        )
    epoch_charge = running

    account = {
        "ix": ix,
        "params": params,
        "state": state,
        "ledger": ledger,
        "epoch_charge": epoch_charge,
        "suspended": suspended,
        "unvalidated": unvalidated,
        "stood_down": stood_down,
        "iterations": iterations,
        "burdens": {gid: burden_of(gid) for gid in ix.gate_ids},
        "loans": loans,
        "lent": lent,
        "borrowed": borrowed,
        "effective_cap": effective_cap,
        "priced_total_before": priced_total_before,
        "priced_total_after": priced_total_after,
        "curtailed": curtailed,
        "residual": residual,
        "release_order": release_order,
        "no_table": sorted(no_table),
        "exceptions_on_withdrawn": sorted(exceptions_on_withdrawn),
        "step": step,
        "rule": rule,
    }
    return account


# --------------------------------------------------------------------------
# netting layer
# --------------------------------------------------------------------------


def netting_layer(account):
    ix = account["ix"]
    state = account["state"]
    step = account["step"]
    rule = account["rule"]

    gross = {}
    counts = {}
    for tap in ix.taps:
        row = state[tap["pos"]]
        if row["disposition"] != "priced" or not row["cross"]:
            continue
        payer = tap["operator_id"]
        payee = row["home_operator"]
        amount = place(row["unit_fare"] * ix.interchange_share_bp, 10000, step, rule)
        if amount <= 0:
            continue
        gross[(payer, payee)] = gross.get((payer, payee), 0) + amount
        counts[(payer, payee)] = counts.get((payer, payee), 0) + 1

    residual = dict(gross)
    cycles = []
    while True:
        cycle = first_cycle(residual)
        if cycle is None:
            break
        edges = [(cycle[i], cycle[(i + 1) % len(cycle)]) for i in range(len(cycle))]
        amount = min(residual[e] for e in edges)
        for e in edges:
            residual[e] -= amount
            if residual[e] <= 0:
                del residual[e]
        cycles.append({"sequence": list(cycle), "amount_micros": amount})

    gross_total = sum(gross.values())
    residual_total = sum(residual.values())
    cancelled_total = sum(c["amount_micros"] * len(c["sequence"]) for c in cycles)

    positions = []
    net_total = 0
    for oid in ix.operator_ids:
        gross_out = sum(v for (p, q), v in gross.items() if p == oid)
        gross_in = sum(v for (p, q), v in gross.items() if q == oid)
        res_out = sum(v for (p, q), v in residual.items() if p == oid)
        res_in = sum(v for (p, q), v in residual.items() if q == oid)
        net = res_out - res_in
        net_total += net
        positions.append(
            {
                "operator_id": oid,
                "gross_out_micros": gross_out,
                "gross_in_micros": gross_in,
                "residual_out_micros": res_out,
                "residual_in_micros": res_in,
                "net_position_micros": net,
            }
        )

    def rank(oid):
        return ix.operators.get(oid, {}).get("clearing_rank", 0)

    schedule_edges = sorted(
        residual.items(), key=lambda kv: (rank(kv[0][0]), rank(kv[0][1]), -kv[1], kv[0][0], kv[0][1])
    )
    funded_running = {oid: 0 for oid in ix.operator_ids}
    rows = []
    digest = 0
    for (payer, payee), amount in schedule_edges:
        ceiling = ix.operators.get(payer, {}).get("funding_ceiling_micros", 0)
        if funded_running.get(payer, 0) + amount <= ceiling:
            funded_running[payer] = funded_running.get(payer, 0) + amount
            statestr = "funded"
        else:
            statestr = "deferred"
        rows.append(
            {
                "payer": payer,
                "payee": payee,
                "amount_micros": amount,
                "state": statestr,
                "payer_funded_running_micros": funded_running.get(payer, 0),
            }
        )
        if ix.netting_modulus:
            digest = (digest * ix.netting_multiplier + amount) % ix.netting_modulus

    return {
        "gross": gross,
        "counts": counts,
        "residual": residual,
        "cycles": cycles,
        "gross_total": gross_total,
        "residual_total": residual_total,
        "cancelled_total": cancelled_total,
        "positions": positions,
        "net_total": net_total,
        "rows": rows,
        "funded_running": funded_running,
        "digest": digest,
    }


def first_cycle(graph):
    """The first simple directed cycle in canonical cycle order."""
    nodes = sorted({n for edge in graph for n in edge})
    adjacency = {n: [] for n in nodes}
    for payer, payee in graph:
        adjacency[payer].append(payee)
    for node in adjacency:
        adjacency[node].sort()

    best = None
    for start in nodes:
        # every path begins at the cycle's smallest operator, so the path is
        # already the sequence N2 compares
        stack = [(start, [start], {start})]
        while stack:
            node, path, seen = stack.pop()
            for nxt in adjacency[node]:
                if nxt == start:
                    candidate = list(path)
                    if best is None or (len(candidate), candidate) < (len(best), best):
                        best = candidate
                elif nxt > start and nxt not in seen:
                    if best is None or len(path) + 1 <= len(best):
                        stack.append((nxt, path + [nxt], seen | {nxt}))
    return best


# --------------------------------------------------------------------------
# assurance layer
# --------------------------------------------------------------------------


def median_of(values):
    if not values:
        return 0
    ordered = sorted(values)
    size = len(ordered)
    if size % 2 == 1:
        return ordered[size // 2]
    return ordered[size // 2 - 1]


def assurance_layer(account):
    ix = account["ix"]
    state = account["state"]

    sample = []
    zero_distance = []
    for tap in ix.taps:
        row = state[tap["pos"]]
        if row["disposition"] != "priced":
            continue
        if tap["distance_units"] <= 0:
            zero_distance.append(tap["tap_id"])
            continue
        floor = ix.gates[tap["gate_id"]]["floor_fare_micros"]
        margin = trunc_div(row["unit_fare"] - floor, tap["distance_units"])
        sample.append(
            {
                "tap_id": tap["tap_id"],
                "rider_class": tap["rider_class"],
                "unit_fare_micros": row["unit_fare"],
                "floor_fare_micros": floor,
                "distance_units": tap["distance_units"],
                "margin": margin,
            }
        )

    median = median_of([s["margin"] for s in sample])
    for s in sample:
        s["deviation"] = abs(s["margin"] - median)
    mad = median_of([s["deviation"] for s in sample])
    threshold = ix.assurance_sigma * mad
    small = len(sample) <= ix.min_sample
    for s in sample:
        s["held_back"] = (not small) and s["deviation"] > threshold

    retained = [s for s in sample if not s["held_back"]]
    held_back = [s for s in sample if s["held_back"]]
    pool = sum(s["margin"] for s in retained)
    retained_distance = sum(s["distance_units"] for s in retained)

    classes_retained = sorted({s["rider_class"] for s in retained})
    weights = {
        cls: sum(s["margin"] for s in retained if s["rider_class"] == cls)
        for cls in classes_retained
    }
    total_weight = sum(weights.values())
    shares = {cls: 0 for cls in classes_retained}
    if classes_retained:
        if total_weight == 0:
            shares[classes_retained[0]] = retained_distance
        else:
            remainders = []
            assigned = 0
            for cls in classes_retained:
                exact = retained_distance * weights[cls]
                shares[cls] = exact // total_weight
                assigned += shares[cls]
                remainders.append((exact % total_weight, cls))
            left = retained_distance - assigned
            ordered = sorted(remainders, key=lambda rc: (-rc[0], rc[1]))
            index = 0
            while left > 0 and ordered:
                shares[ordered[index % len(ordered)][1]] += 1
                left -= 1
                index += 1

    digest_order = sorted(retained, key=lambda s: (s["margin"], s["tap_id"]))
    digest = 0
    for s in digest_order:
        if ix.assurance_modulus:
            digest = (digest * ix.assurance_multiplier + s["margin"]) % ix.assurance_modulus

    classes_sample = sorted({s["rider_class"] for s in sample})
    ladder = []
    for cls in classes_sample:
        ladder.append(
            {
                "rider_class": cls,
                "retained_count": sum(1 for s in retained if s["rider_class"] == cls),
                "held_back_count": sum(1 for s in held_back if s["rider_class"] == cls),
                "margin_total": sum(s["margin"] for s in retained if s["rider_class"] == cls),
                "share_units": shares.get(cls, 0),
            }
        )

    return {
        "sample": sample,
        "retained": retained,
        "held_back": held_back,
        "median": median,
        "mad": mad,
        "threshold": threshold,
        "pool": pool,
        "retained_distance": retained_distance,
        "shares": shares,
        "classes_retained": classes_retained,
        "weights": weights,
        "digest_order": digest_order,
        "digest": digest,
        "ladder": ladder,
        "zero_distance": zero_distance,
    }


# --------------------------------------------------------------------------
# recovering the seven properties
# --------------------------------------------------------------------------


def candidate_combinations(legal):
    fare_keys = [
        "adjustment_order",
        "levy_basis",
        "grid_step_micros",
        "midpoint_rule",
        "fault_window_edge",
    ]
    rest_keys = ["void_reach", "cap_release_order"]
    fare_space = [
        dict(zip(fare_keys, combo))
        for combo in itertools.product(*[legal[k] for k in fare_keys])
    ]
    rest_space = [
        dict(zip(rest_keys, combo))
        for combo in itertools.product(*[legal[k] for k in rest_keys])
    ]
    return fare_space, rest_space


def recover_parameters(calibration):
    legal = calibration["legal_values"]
    published = calibration["published"]
    slice_reg = dict(calibration["slice"])
    slice_reg.setdefault("exceptions", [])
    ix = Interchange(slice_reg)

    fare_space, rest_space = candidate_combinations(legal)
    # a published unit fare an upheld exception replaced says nothing about
    # the tariff, so the cheap first pass does not test those taps
    replaced = {e["tap_id"] for e in ix.exceptions if e["status"] == "upheld"}
    checks = {
        k: v
        for k, v in published.get("unit_fare_checks", {}).items()
        if k not in replaced
    }

    survivors = []
    for fare_params in fare_space:
        params = dict(fare_params)
        params["adjustment_order"] = list(fare_params["adjustment_order"])
        fares = price_taps(ix, params)
        by_tap = {}
        for pos, info in fares.items():
            if info["table"] is None:
                continue
            by_tap.setdefault(ix.taps[pos]["tap_id"], info["unit_fare"])
        ok = True
        for tap_id, fare in checks.items():
            if by_tap.get(tap_id) != fare:
                ok = False
                break
        if ok:
            survivors.append((params, fares))

    chosen = None
    for params, fares in survivors:
        for rest in rest_space:
            full = dict(params)
            full.update(rest)
            account = clear_epoch(ix, full, fares)
            if matches_published(account, published):
                chosen = full
                break
        if chosen is not None:
            break
    if chosen is None:
        raise SystemExit("no candidate reading reproduces the calibration figures")
    return {
        "adjustment_order": list(chosen["adjustment_order"]),
        "levy_basis": chosen["levy_basis"],
        "grid_step_micros": chosen["grid_step_micros"],
        "midpoint_rule": chosen["midpoint_rule"],
        "void_reach": chosen["void_reach"],
        "cap_release_order": chosen["cap_release_order"],
        "fault_window_edge": chosen["fault_window_edge"],
    }


def matches_published(account, published):
    state = account["state"]
    ix = account["ix"]
    priced = [t for t in ix.taps if state[t["pos"]]["disposition"] == "priced"]
    withdrawn = [t for t in ix.taps if state[t["pos"]]["disposition"] == "withdrawn"]
    if "taps_priced" in published and len(priced) != published["taps_priced"]:
        return False
    if "taps_withdrawn" in published and len(withdrawn) != published["taps_withdrawn"]:
        return False
    if "epoch_charge_micros" in published and account["epoch_charge"] != published["epoch_charge_micros"]:
        return False
    if "priced_distance_units" in published:
        if sum(t["distance_units"] for t in priced) != published["priced_distance_units"]:
            return False
    if "unit_fare_checks" in published:
        fares = {t["tap_id"]: state[t["pos"]]["unit_fare"] for t in priced}
        if fares != {k: v for k, v in published["unit_fare_checks"].items()}:
            return False
    if "suspended_gates" in published:
        if sorted(account["suspended"]) != list(published["suspended_gates"]):
            return False
    if "curtailed_tap_ids" in published:
        allc = sorted(t for zid in account["curtailed"] for t in account["curtailed"][zid])
        if allc != list(published["curtailed_tap_ids"]):
            return False
    if "loan_total_micros" in published:
        if sum(l["amount_micros"] for l in account["loans"]) != published["loan_total_micros"]:
            return False
    if "loans" in published:
        got = [[l["from_zone"], l["to_zone"], l["amount_micros"]] for l in account["loans"]]
        if got != [list(x) for x in published["loans"]]:
            return False
    if "netting_digest" in published or "assurance_pool_micros" in published or "assurance_digest" in published:
        net = netting_layer(account)
        assur = assurance_layer(account)
        if "netting_digest" in published and net["digest"] != published["netting_digest"]:
            return False
        if "assurance_pool_micros" in published and assur["pool"] != published["assurance_pool_micros"]:
            return False
        if "assurance_digest" in published and assur["digest"] != published["assurance_digest"]:
            return False
    return True


# --------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------


def write_json(path, payload):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True))
        fh.write("\n")


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(header))
        fh.write("\n")
        for row in rows:
            fh.write(",".join(str(cell) for cell in row))
            fh.write("\n")


def emit(account, net, assur, params, out_dir):
    ix = account["ix"]
    state = account["state"]
    ledger = account["ledger"]

    priced = [t for t in ix.taps if state[t["pos"]]["disposition"] == "priced"]
    withdrawn = [t for t in ix.taps if state[t["pos"]]["disposition"] == "withdrawn"]
    out_of_epoch = [t for t in ix.taps if state[t["pos"]]["disposition"] == "out_of_epoch"]

    priced_distance = sum(t["distance_units"] for t in priced)
    withdrawn_distance = sum(t["distance_units"] for t in withdrawn)
    admitted_distance = sum(t["distance_units"] for t in ix.in_epoch)

    zone_charge = {zid: 0 for zid in ix.zone_ids}
    zone_distance = {zid: 0 for zid in ix.zone_ids}
    zone_priced = {zid: 0 for zid in ix.zone_ids}
    zone_withdrawn = {zid: 0 for zid in ix.zone_ids}
    operator_charge = {oid: 0 for oid in ix.operator_ids}
    operator_distance = {oid: 0 for oid in ix.operator_ids}
    operator_priced = {oid: 0 for oid in ix.operator_ids}
    operator_withdrawn = {oid: 0 for oid in ix.operator_ids}
    gates_with_priced = {}
    for tap in ix.in_epoch:
        row = state[tap["pos"]]
        zid, oid = tap["zone_id"], tap["operator_id"]
        if row["disposition"] == "priced":
            zone_charge[zid] = zone_charge.get(zid, 0) + row["unit_fare"]
            zone_distance[zid] = zone_distance.get(zid, 0) + tap["distance_units"]
            zone_priced[zid] = zone_priced.get(zid, 0) + 1
            operator_charge[oid] = operator_charge.get(oid, 0) + row["unit_fare"]
            operator_distance[oid] = operator_distance.get(oid, 0) + tap["distance_units"]
            operator_priced[oid] = operator_priced.get(oid, 0) + 1
            gates_with_priced.setdefault(zid, set()).add(tap["gate_id"])
        else:
            zone_withdrawn[zid] = zone_withdrawn.get(zid, 0) + 1
            operator_withdrawn[oid] = operator_withdrawn.get(oid, 0) + 1

    zones_in_scope = sorted(zid for zid in ix.zone_ids if zone_priced.get(zid, 0) > 0)
    operators_in_scope = sorted(
        oid
        for oid in ix.operator_ids
        if any(zid in zones_in_scope for zid in ix.zones_of_operator.get(oid, []))
    )
    cap_infeasible = sorted(zid for zid in ix.zone_ids if account["residual"].get(zid, 0) > 0)

    # ---- summary -------------------------------------------------------
    summary = {
        "epoch_id": ix.epoch_id,
        "epoch_opens_at": ix.opens_at_text,
        "epoch_closes_at": ix.closes_at_text,
        "resolved_parameters": params,
        "taps_total": len(ix.taps),
        "taps_admitted": len(ix.in_epoch),
        "taps_priced": len(priced),
        "taps_withdrawn": len(withdrawn),
        "taps_out_of_epoch": len(out_of_epoch),
        "epoch_charge_micros": account["epoch_charge"],
        "priced_distance_units": priced_distance,
        "admitted_distance_units": admitted_distance,
        "suspended_gates": sorted(account["suspended"]),
        "unvalidated_zones": sorted(account["unvalidated"]),
        "stood_down_operators": sorted(account["stood_down"]),
        "operators_in_scope": operators_in_scope,
        "zones_in_scope": zones_in_scope,
        "cap_infeasible_zones": cap_infeasible,
    }
    write_json(os.path.join(out_dir, "summary.json"), summary)

    # ---- tap ledger ----------------------------------------------------
    write_json(
        os.path.join(out_dir, "tap_ledger.json"),
        {
            "rows": ledger,
            "row_count": len(ledger),
            "charge_micros": account["epoch_charge"],
        },
    )

    # ---- data quality --------------------------------------------------
    outcomes = {}
    for tap in ix.in_epoch:
        outcomes.setdefault(state[tap["pos"]]["outcome"], []).append(tap["tap_id"])
    upheld = [e for e in ix.exceptions if e["status"] == "upheld"]
    rejected = [e for e in ix.exceptions if e["status"] == "rejected"]
    quality = {
        "taps_out_of_epoch": sorted(t["tap_id"] for t in out_of_epoch),
        "taps_without_governing_table": account["no_table"],
        "taps_with_retired_identity": sorted(outcomes.get("retired", [])),
        "taps_with_revoked_identity": sorted(outcomes.get("revoked", [])),
        "identity_cycles_broken": sorted(outcomes.get("cycle_broken", [])),
        "duplicate_tap_ids": sorted(ix.duplicate_tap_ids),
        "zero_distance_taps": sorted(
            t["tap_id"] for t in ix.taps if t["distance_units"] == 0
        ),
        "decommissioned_gates": sorted(
            gid for gid in ix.gate_ids if ix.gates[gid]["decommissioned"]
        ),
        "faults_open_at_close": sorted(
            f["fault_id"] for f in ix.faults if f["open_at_close"]
        ),
        "exceptions_total": len(ix.exceptions),
        "exceptions_upheld": len(upheld),
        "exceptions_rejected": len(rejected),
        "exceptions_on_withdrawn_taps": account["exceptions_on_withdrawn"],
    }
    write_json(os.path.join(out_dir, "data_quality.json"), quality)

    # ---- identity register ---------------------------------------------
    outcome_rows = []
    for name in sorted(outcomes):
        tap_ids = sorted(outcomes[name])
        outcome_rows.append({"outcome": name, "tap_ids": tap_ids, "count": len(tap_ids)})
    resolutions = []
    for tap in sorted(ix.in_epoch, key=lambda t: (t["tap_id"], t["pos"])):
        ident = ix.identity[tap["pos"]]
        resolutions.append(
            {
                "tap_id": tap["tap_id"],
                "token_ref": tap["token_ref"],
                "canonical_token": ident["canonical_token"],
                "outcome": ident["outcome"],
                "chain": list(ident["chain"]),
            }
        )
    write_json(
        os.path.join(out_dir, "identity_register.json"),
        {"outcomes": outcome_rows, "resolutions": resolutions},
    )

    # ---- suspension register -------------------------------------------
    gate_rows = []
    for gid in ix.gate_ids:
        gate_rows.append(
            {
                "gate_id": gid,
                "zone_id": ix.gates[gid]["zone_id"],
                "burden_bp": account["burdens"][gid],
                "allowance_bp": ix.gates[gid]["fault_allowance_bp"],
                "suspended": gid in account["suspended"],
                "reason": account["suspended"].get(gid, ""),
            }
        )
    zone_rows = []
    for zid in ix.zone_ids:
        validated = sum(
            1
            for gid in ix.gates_of_zone.get(zid, [])
            if gid not in account["suspended"]
        )
        zone_rows.append(
            {
                "zone_id": zid,
                "validated_gate_count": validated,
                "validation_floor": ix.zones[zid]["validation_floor"],
                "unvalidated": zid in account["unvalidated"],
            }
        )
    write_json(
        os.path.join(out_dir, "suspension_register.json"),
        {
            "iterations": account["iterations"],
            "gates": gate_rows,
            "zones": zone_rows,
            "operators": [
                {"operator_id": oid, "stood_down": oid in account["stood_down"]}
                for oid in ix.operator_ids
            ],
        },
    )

    # ---- cap relief -----------------------------------------------------
    cap_zone_rows = []
    for zid in ix.zone_ids:
        cap_zone_rows.append(
            {
                "zone_id": zid,
                "revenue_cap_micros": ix.zones[zid]["revenue_cap_micros"],
                "effective_cap_micros": account["effective_cap"][zid],
                "priced_total_before_micros": account["priced_total_before"][zid],
                "priced_total_after_micros": account["priced_total_after"][zid],
                "lent_micros": account["lent"][zid],
                "borrowed_micros": account["borrowed"][zid],
                "curtailed_tap_ids": sorted(account["curtailed"].get(zid, [])),
                "residual_micros": account["residual"].get(zid, 0),
                "cap_infeasible": account["residual"].get(zid, 0) > 0,
            }
        )
    write_json(
        os.path.join(out_dir, "cap_relief.json"),
        {
            "release_order": list(account["release_order"]),
            "zones": cap_zone_rows,
            "loans": account["loans"],
            "loan_total_micros": sum(l["amount_micros"] for l in account["loans"]),
        },
    )

    # ---- netting artifacts ----------------------------------------------
    net_by_operator = {p["operator_id"]: p for p in net["positions"]}
    gross_edges = [
        {
            "payer": payer,
            "payee": payee,
            "amount_micros": amount,
            "tap_count": net["counts"][(payer, payee)],
        }
        for (payer, payee), amount in sorted(net["gross"].items())
    ]
    residual_edges = [
        {"payer": payer, "payee": payee, "amount_micros": amount}
        for (payer, payee), amount in sorted(net["residual"].items())
    ]
    funded = [r for r in net["rows"] if r["state"] == "funded"]
    deferred = [r for r in net["rows"] if r["state"] == "deferred"]
    write_json(
        os.path.join(out_dir, "netting_summary.json"),
        {
            "epoch_id": ix.epoch_id,
            "interchange_share_bp": ix.interchange_share_bp,
            "obligation_total_micros": net["gross_total"],
            "residual_total_micros": net["residual_total"],
            "cancelled_cycle_count": len(net["cycles"]),
            "cancelled_total_micros": net["cancelled_total"],
            "net_position_total_micros": net["net_total"],
            "netting_digest": net["digest"],
            "funded_edge_count": len(funded),
            "deferred_edge_count": len(deferred),
            "funded_total_micros": sum(r["amount_micros"] for r in funded),
            "deferred_total_micros": sum(r["amount_micros"] for r in deferred),
        },
    )
    write_json(
        os.path.join(out_dir, "netting_obligations.json"),
        {"edges": gross_edges, "total_micros": net["gross_total"]},
    )
    write_json(
        os.path.join(out_dir, "netting_residual.json"),
        {
            "edges": residual_edges,
            "cycles": [
                {"sequence": c["sequence"], "amount_micros": c["amount_micros"]}
                for c in net["cycles"]
            ],
            "total_micros": net["residual_total"],
        },
    )
    write_json(
        os.path.join(out_dir, "netting_positions.json"),
        {"positions": net["positions"], "net_total_micros": net["net_total"]},
    )
    write_json(
        os.path.join(out_dir, "netting_schedule.json"),
        {
            "rows": net["rows"],
            "funding_ceilings": [
                {
                    "operator_id": oid,
                    "funding_ceiling_micros": ix.operators[oid]["funding_ceiling_micros"],
                    "funded_micros": net["funded_running"].get(oid, 0),
                }
                for oid in ix.operator_ids
            ],
        },
    )
    write_csv(
        os.path.join(out_dir, "netting_cycles.csv"),
        ["cycle_index", "sequence", "amount_micros"],
        [
            [index + 1, ">".join(c["sequence"]), c["amount_micros"]]
            for index, c in enumerate(net["cycles"])
        ],
    )

    # ---- assurance artifacts ---------------------------------------------
    write_json(
        os.path.join(out_dir, "assurance_summary.json"),
        {
            "epoch_id": ix.epoch_id,
            "assurance_sigma": ix.assurance_sigma,
            "assurance_modulus": ix.assurance_modulus,
            "min_sample": ix.min_sample,
            "sample_size": len(assur["sample"]),
            "median_margin": assur["median"],
            "mad": assur["mad"],
            "threshold": assur["threshold"],
            "retained_count": len(assur["retained"]),
            "held_back_count": len(assur["held_back"]),
            "pool_micros": assur["pool"],
            "assurance_digest": assur["digest"],
            "priced_distance_units": priced_distance,
            "zero_distance_taps": sorted(assur["zero_distance"]),
        },
    )
    margin_rows = [
        {
            "tap_id": s["tap_id"],
            "rider_class": s["rider_class"],
            "unit_fare_micros": s["unit_fare_micros"],
            "floor_fare_micros": s["floor_fare_micros"],
            "distance_units": s["distance_units"],
            "margin": s["margin"],
            "deviation": s["deviation"],
            "held_back": s["held_back"],
        }
        for s in sorted(assur["sample"], key=lambda s: s["tap_id"])
    ]
    write_json(
        os.path.join(out_dir, "assurance_margins.json"),
        {"rows": margin_rows, "row_count": len(margin_rows)},
    )
    holdback_rows = [
        {
            "tap_id": s["tap_id"],
            "margin": s["margin"],
            "median_margin": assur["median"],
            "deviation": s["deviation"],
            "threshold": assur["threshold"],
        }
        for s in sorted(assur["held_back"], key=lambda s: s["tap_id"])
    ]
    write_json(
        os.path.join(out_dir, "assurance_holdbacks.json"),
        {"rows": holdback_rows, "row_count": len(holdback_rows)},
    )
    write_json(
        os.path.join(out_dir, "assurance_order.json"),
        {
            "tap_ids": [s["tap_id"] for s in assur["digest_order"]],
            "margins": [s["margin"] for s in assur["digest_order"]],
            "digest": assur["digest"],
        },
    )
    write_json(
        os.path.join(out_dir, "assurance_apportionment.json"),
        {
            "retained_distance_units": assur["retained_distance"],
            "shares": [
                {
                    "rider_class": cls,
                    "retained_margin_micros": assur["weights"][cls],
                    "share_units": assur["shares"][cls],
                }
                for cls in assur["classes_retained"]
            ],
            "share_total_units": sum(assur["shares"].values()),
        },
    )
    write_csv(
        os.path.join(out_dir, "assurance_ladder.csv"),
        ["rider_class", "retained_count", "held_back_count", "margin_total", "share_units"],
        [
            [
                row["rider_class"],
                row["retained_count"],
                row["held_back_count"],
                row["margin_total"],
                row["share_units"],
            ]
            for row in assur["ladder"]
        ],
    )

    # ---- partition reports ------------------------------------------------
    for oid in operators_in_scope:
        write_json(
            os.path.join(out_dir, "operator_%s.json" % oid),
            {
                "partition_kind": "operator",
                "partition_id": oid,
                "epoch_id": ix.epoch_id,
                "taps_priced": operator_priced.get(oid, 0),
                "taps_withdrawn": operator_withdrawn.get(oid, 0),
                "charge_micros": operator_charge.get(oid, 0),
                "priced_distance_units": operator_distance.get(oid, 0),
                "zones_in_scope": sorted(
                    zid for zid in ix.zones_of_operator.get(oid, []) if zid in zones_in_scope
                ),
                "gates_suspended": sorted(
                    gid
                    for gid in account["suspended"]
                    if ix.zones.get(ix.gates[gid]["zone_id"], {}).get("operator_id") == oid
                ),
                "net_position_micros": net_by_operator.get(oid, {}).get(
                    "net_position_micros", 0
                ),
            },
        )
    for zid in zones_in_scope:
        write_json(
            os.path.join(out_dir, "zone_%s.json" % zid),
            {
                "partition_kind": "zone",
                "partition_id": zid,
                "epoch_id": ix.epoch_id,
                "operator_id": ix.zones[zid]["operator_id"],
                "taps_priced": zone_priced.get(zid, 0),
                "taps_withdrawn": zone_withdrawn.get(zid, 0),
                "charge_micros": zone_charge.get(zid, 0),
                "priced_distance_units": zone_distance.get(zid, 0),
                "revenue_cap_micros": ix.zones[zid]["revenue_cap_micros"],
                "effective_cap_micros": account["effective_cap"][zid],
                "gates_in_scope": sorted(gates_with_priced.get(zid, set())),
                "cap_infeasible": account["residual"].get(zid, 0) > 0,
            },
        )

    # ---- reconciliation ---------------------------------------------------
    identities = [
        (
            "admitted_plus_out_of_epoch_equals_total",
            len(ix.in_epoch) + len(out_of_epoch),
            len(ix.taps),
        ),
        (
            "priced_plus_withdrawn_equals_admitted",
            len(priced) + len(withdrawn),
            len(ix.in_epoch),
        ),
        (
            "zone_charges_sum_to_epoch_charge",
            sum(zone_charge.values()),
            account["epoch_charge"],
        ),
        (
            "operator_charges_sum_to_epoch_charge",
            sum(operator_charge.values()),
            account["epoch_charge"],
        ),
        (
            "ledger_running_total_closes_on_epoch_charge",
            ledger[-1]["running_charge_micros"] if ledger else 0,
            account["epoch_charge"],
        ),
        (
            "priced_plus_withdrawn_distance_equals_admitted_distance",
            priced_distance + withdrawn_distance,
            admitted_distance,
        ),
        (
            "loans_granted_equal_cap_released",
            sum(l["amount_micros"] for l in account["loans"]),
            sum(
                account["effective_cap"][zid] - ix.zones[zid]["revenue_cap_micros"]
                for zid in ix.zone_ids
            ),
        ),
        ("net_positions_sum_to_zero", net["net_total"], 0),
        (
            "residual_plus_cancelled_equals_gross",
            net["residual_total"] + net["cancelled_total"],
            net["gross_total"],
        ),
        (
            "assurance_shares_sum_to_retained_distance",
            sum(assur["shares"].values()),
            assur["retained_distance"],
        ),
        (
            "retained_margins_sum_to_pool",
            sum(s["margin"] for s in assur["retained"]),
            assur["pool"],
        ),
    ]
    rows = [
        {"identity": name, "left": left, "right": right, "residual": left - right}
        for name, left, right in identities
    ]
    write_json(
        os.path.join(out_dir, "reconciliation.json"),
        {"identities": rows, "residual_total": sum(r["residual"] for r in rows)},
    )

    return summary


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    reg_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    registers = load_registers(reg_dir)
    calibration = load_calibration(reg_dir)
    params = recover_parameters(calibration)
    ix = Interchange(registers)
    account = clear_epoch(ix, params)
    net = netting_layer(account)
    assur = assurance_layer(account)
    emit(account, net, assur, params, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
