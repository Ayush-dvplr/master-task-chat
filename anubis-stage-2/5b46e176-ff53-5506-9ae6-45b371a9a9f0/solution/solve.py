#!/usr/bin/env python3
"""Clearance engine for one revenue epoch of a transit interchange.

Usage: clear_epoch.py <register-directory> <output-directory>

The engine recovers the seven platform properties the interchange never wrote
down from the calibration material that travels with the registers, clears the
epoch, nets the interchange obligations down to a cycle free residual, and
settles the cleared ledger onto a per distance unit assurance basis. Every
figure is an integer count of micros or of distance units; no floating point
value takes part in any decision.

Nothing in this file is true only of one epoch. Every parameter the clearance
needs is read from the register directory it is pointed at.
"""

from __future__ import annotations

import csv
import itertools
import json
import os
import sys

PROPERTY_NAMES = (
    "adjustment_order",
    "levy_basis",
    "grid_step_micros",
    "midpoint_rule",
    "void_reach",
    "cap_release_order",
    "fault_window_edge",
)

ADJUSTMENTS = (
    "fault_abatement",
    "concession_relief",
    "interchange_uplift",
    "shortfall_levy",
)

# ---------------------------------------------------------------------------
# register loading
# ---------------------------------------------------------------------------

INT = "int"
STR = "str"

CSV_SCHEMA = {
    "epoch_calendar": {
        "epoch_id": STR, "opens_at": STR, "closes_at": STR,
    },
    "epoch_policy": {
        "epoch_id": STR, "boundary": STR, "peak_from": STR, "peak_to": STR,
    },
    "operators": {
        "operator_id": STR, "clearing_rank": INT,
        "float_ceiling_micros": INT, "funding_ceiling_micros": INT,
    },
    "zones": {
        "zone_id": STR, "operator_id": STR, "tariff_band": INT,
        "validation_floor": INT, "revenue_cap_micros": INT, "provisional": INT,
    },
    "gates": {
        "gate_id": STR, "zone_id": STR, "gate_class": STR,
        "fault_allowance_bp": INT, "floor_fare_micros": INT, "decommissioned": INT,
    },
    "taps": {
        "tap_id": STR, "token_ref": STR, "gate_id": STR, "tapped_at": STR,
        "distance_units": INT, "rider_class": STR, "completion_class": STR, "op": STR,
    },
    "token_events": {
        "event_id": STR, "effective_at": STR, "event_type": STR,
        "subject_ref": STR, "target_ref": STR,
    },
    "tariff_tables": {
        "table_id": STR, "effective_from": STR, "superseded_at": STR,
        "rate_peak": INT, "rate_offpeak": INT, "rate_concession": INT,
        "mult_complete": INT, "mult_open_exit": INT, "mult_forced": INT,
        "uplift_bp": INT, "relief_bp": INT, "levy_bp": INT,
    },
    "gate_faults": {
        "fault_id": STR, "gate_id": STR, "severity": INT,
        "opened_at": STR, "closed_at": STR, "abatement_micros": INT,
    },
    "netting_policy": {
        "interchange_share_bp": INT, "netting_multiplier": INT, "netting_modulus": INT,
    },
    "assurance_policy": {
        "assurance_sigma": INT, "assurance_multiplier": INT,
        "assurance_modulus": INT, "min_sample": INT,
    },
}

SORT_KEYS = {
    "epoch_calendar": ("epoch_id",),
    "epoch_policy": ("epoch_id",),
    "operators": ("operator_id",),
    "zones": ("zone_id",),
    "gates": ("gate_id",),
    "taps": ("tapped_at", "tap_id"),
    "token_events": ("effective_at", "event_id"),
    "tariff_tables": ("effective_from", "table_id"),
    "gate_faults": ("fault_id",),
    "netting_policy": ("interchange_share_bp",),
    "assurance_policy": ("assurance_sigma",),
}


def _coerce(table, row):
    """One register row with every field at the type the schema gives it.

    Rows reach this function either from a CSV reader, where every field is a
    string, or from the calibration block, where JSON has already typed them.
    Both shapes are accepted so the calibration slice and the shipped
    registers travel through exactly the same clearance.
    """
    fields = CSV_SCHEMA[table]
    out = {}
    for name, kind in fields.items():
        raw = row.get(name)
        if kind is INT:
            if isinstance(raw, bool):
                out[name] = int(raw)
            elif isinstance(raw, int):
                out[name] = raw
            else:
                text = (raw or "").strip()
                out[name] = int(text) if text else 0
        else:
            out[name] = raw.strip() if isinstance(raw, str) else ("" if raw is None else str(raw))
    return out


def load_registers(data_dir):
    """Read every register the clearance needs, sorted into canonical order.

    The registers state their rows in no fixed order, so every table is sorted
    on its own key here and nothing downstream ever looks at file order.
    """
    registers = {}
    for table in CSV_SCHEMA:
        path = os.path.join(data_dir, table + ".csv")
        rows = []
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if any((value or "").strip() for value in row.values()):
                    rows.append(_coerce(table, row))
        keys = SORT_KEYS[table]
        rows.sort(key=lambda r: tuple(r[k] for k in keys))
        registers[table] = rows

    with open(os.path.join(data_dir, "exceptions.json"), encoding="utf-8") as handle:
        payload = json.load(handle)
    exceptions = sorted(payload.get("exceptions", []), key=lambda e: e["exception_id"])
    registers["exceptions"] = exceptions

    with open(os.path.join(data_dir, "calibration_controls.json"), encoding="utf-8") as handle:
        registers["calibration"] = json.load(handle)
    return registers


def registers_from_slice(block):
    """Rebuild a register set from the calibration block's embedded rows."""
    registers = {}
    for table in CSV_SCHEMA:
        rows = [_coerce(table, row) for row in block.get(table, [])]
        keys = SORT_KEYS[table]
        rows.sort(key=lambda r: tuple(r[k] for k in keys))
        registers[table] = rows
    registers["exceptions"] = sorted(block.get("exceptions", []),
                                     key=lambda e: e["exception_id"])
    registers["calibration"] = None
    return registers


# ---------------------------------------------------------------------------
# grid placement
# ---------------------------------------------------------------------------

def place(numer, denom, step, rule):
    """Put the non negative rational numer/denom onto the settlement grid.

    The grid is the multiples of step. A value strictly between two grid
    points goes to the nearer one. A value exactly half way between two grid
    points is decided by rule, which is one of the four conventions the
    calibration material admits.
    """
    if numer < 0:
        numer = 0
    unit = denom * step
    k, rem = divmod(numer, unit)
    twice = 2 * rem
    if twice > unit:
        k += 1
    elif twice == unit:
        if rule == "to_even_multiple":
            k = k if k % 2 == 0 else k + 1
        elif rule == "to_odd_multiple":
            k = k if k % 2 == 1 else k + 1
        elif rule == "away_from_zero":
            k += 1
        elif rule == "toward_zero":
            pass
        else:
            raise ValueError("unknown midpoint rule " + repr(rule))
    return k * step


# ---------------------------------------------------------------------------
# instants
# ---------------------------------------------------------------------------

def clock(instant):
    """The wall clock time of day of an instant, as a comparable HH:MM."""
    return instant[11:16]


def within(instant, opens_at, closes_at, boundary):
    """Whether instant falls inside the interval under the named convention."""
    low = instant > opens_at if boundary.startswith("open") else instant >= opens_at
    high = instant < closes_at if boundary.endswith("open") else instant <= closes_at
    return low and high


# ---------------------------------------------------------------------------
# identity resolution
# ---------------------------------------------------------------------------

def resolve_identity(events_by_subject, terminal_events, token, instant):
    """The canonical identity of token as at instant, with its chain.

    Rotation and merge events redirect a token to a target. The redirection in
    force at an instant is the latest one effective at or before it. A chain
    that returns to a token it already visited is a cycle, and a cycle settles
    on the lexicographically smallest identity it contains. A terminal event on
    the identity the chain lands on ends the walk: a revocation outranks a
    retirement.
    """
    chain = [token]
    seen = {token}
    current = token
    while True:
        candidates = [e for e in events_by_subject.get(current, ())
                      if e["effective_at"] <= instant]
        if not candidates:
            break
        nxt = max(candidates, key=lambda e: (e["effective_at"], e["event_id"]))["target_ref"]
        if nxt in seen:
            chain.append(nxt)
            return min(seen | {nxt}), "cycle_broken", chain
        chain.append(nxt)
        seen.add(nxt)
        current = nxt

    kinds = set()
    for member in chain:
        for event in terminal_events.get(member, ()):
            if event["effective_at"] <= instant:
                kinds.add(event["event_type"])
    if "revoke" in kinds:
        return current, "revoked", chain
    if "retire" in kinds:
        return current, "retired", chain
    return current, ("rotated" if len(chain) > 1 else "direct"), chain


# ---------------------------------------------------------------------------
# clearance
# ---------------------------------------------------------------------------

VOID_REASONS = (
    "out_of_epoch",
    "duplicate_tap_id",
    "decommissioned_gate",
    "identity_revoked",
    "identity_retired",
    "no_governing_table",
    "voided_by_reversal",
    "reversal_record",
    "gate_suspended",
    "cap_curtailed",
)


def clear_epoch(registers, params):
    """Clear one epoch under one reading of the seven withheld properties."""
    step = params["grid_step_micros"]
    rule = params["midpoint_rule"]

    epoch = registers["epoch_calendar"][0]
    policy = registers["epoch_policy"][0]
    operators = {row["operator_id"]: row for row in registers["operators"]}
    zones = {row["zone_id"]: row for row in registers["zones"]}
    gates = {row["gate_id"]: row for row in registers["gates"]}
    tables = registers["tariff_tables"]

    events_by_subject = {}
    terminal_events = {}
    for event in registers["token_events"]:
        if event["event_type"] in ("rotate", "merge"):
            events_by_subject.setdefault(event["subject_ref"], []).append(event)
        else:
            terminal_events.setdefault(event["subject_ref"], []).append(event)

    faults_by_gate = {}
    for fault in registers["gate_faults"]:
        faults_by_gate.setdefault(fault["gate_id"], []).append(fault)

    # --- admission ---------------------------------------------------------
    seen_ids = set()
    ledger = []
    for tap in registers["taps"]:
        row = {
            "tap_id": tap["tap_id"],
            "token_ref": tap["token_ref"],
            "gate_id": tap["gate_id"],
            "tapped_at": tap["tapped_at"],
            "distance_units": tap["distance_units"],
            "rider_class": tap["rider_class"],
            "completion_class": tap["completion_class"],
            "op": tap["op"],
            "canonical_token": tap["token_ref"],
            "identity_outcome": "direct",
            "identity_chain": [tap["token_ref"]],
            "zone_id": "",
            "operator_id": "",
            "home_operator_id": "",
            "governing_table_id": "",
            "peak": False,
            "cross_operator": False,
            "gross_before_adjustments_micros": 0,
            "unit_fare_micros": 0,
            "exception_id": "",
            "disposition": "priced",
            "withdrawal_reason": "",
        }
        gate = gates.get(tap["gate_id"])
        if gate is not None:
            row["zone_id"] = gate["zone_id"]
            zone = zones.get(gate["zone_id"])
            row["operator_id"] = zone["operator_id"] if zone else ""
        if not within(tap["tapped_at"], epoch["opens_at"], epoch["closes_at"],
                      policy["boundary"]):
            row["disposition"] = "out_of_epoch"
            row["withdrawal_reason"] = "out_of_epoch"
        elif tap["tap_id"] in seen_ids:
            row["disposition"] = "withdrawn"
            row["withdrawal_reason"] = "duplicate_tap_id"
        seen_ids.add(tap["tap_id"])
        ledger.append(row)

    admitted = [r for r in ledger if r["disposition"] != "out_of_epoch"]

    # --- identity ----------------------------------------------------------
    for row in admitted:
        token, outcome, chain = resolve_identity(
            events_by_subject, terminal_events, row["token_ref"], row["tapped_at"])
        row["canonical_token"] = token
        row["identity_outcome"] = outcome
        row["identity_chain"] = chain

    def withdraw(row, reason):
        if row["disposition"] == "priced":
            row["disposition"] = "withdrawn"
            row["withdrawal_reason"] = reason

    for row in admitted:
        if row["withdrawal_reason"]:
            continue
        gate = gates.get(row["gate_id"])
        if gate is None or gate["decommissioned"]:
            withdraw(row, "decommissioned_gate")
        elif row["identity_outcome"] == "revoked":
            withdraw(row, "identity_revoked")
        elif row["identity_outcome"] == "retired":
            withdraw(row, "identity_retired")

    # --- home operator -----------------------------------------------------
    home = {}
    for row in sorted(admitted, key=lambda r: (r["tapped_at"], r["tap_id"])):
        home.setdefault(row["canonical_token"], row["operator_id"])
    for row in admitted:
        row["home_operator_id"] = home.get(row["canonical_token"], "")
        row["cross_operator"] = bool(
            row["operator_id"] and row["home_operator_id"]
            and row["operator_id"] != row["home_operator_id"])

    # --- pricing -----------------------------------------------------------
    for row in admitted:
        if row["disposition"] != "priced":
            continue
        live = [t for t in tables
                if t["effective_from"] <= row["tapped_at"]
                and (t["superseded_at"] == "" or row["tapped_at"] < t["superseded_at"])]
        if not live:
            withdraw(row, "no_governing_table")
            continue
        table = max(live, key=lambda t: (t["effective_from"], t["table_id"]))
        row["governing_table_id"] = table["table_id"]
        gate = gates[row["gate_id"]]
        zone = zones[gate["zone_id"]]
        peak = policy["peak_from"] <= clock(row["tapped_at"]) < policy["peak_to"]
        row["peak"] = peak
        if row["rider_class"] == "concession":
            rate = table["rate_concession"]
        else:
            rate = table["rate_peak"] if peak else table["rate_offpeak"]
        mult = {
            "complete": table["mult_complete"],
            "open_exit": table["mult_open_exit"],
            "forced": table["mult_forced"],
        }[row["completion_class"]]
        distance_rate_product = rate * row["distance_units"]
        gross = place(distance_rate_product * zone["tariff_band"] * mult, 10000, step, rule)
        row["gross_before_adjustments_micros"] = gross

        abatement = 0
        for fault in faults_by_gate.get(row["gate_id"], ()):
            closes = fault["closed_at"] or epoch["closes_at"]
            if within(row["tapped_at"], fault["opened_at"], closes,
                      params["fault_window_edge"]):
                abatement = max(abatement, fault["abatement_micros"])

        basis = {
            "gross_before_adjustments": gross,
            "floor_fare": gate["floor_fare_micros"],
            "distance_rate_product": distance_rate_product,
        }
        value = gross
        for name in params["adjustment_order"]:
            if name == "fault_abatement":
                value = place(value - abatement, 1, step, rule)
            elif name == "concession_relief":
                if row["rider_class"] == "concession":
                    value = place(value * (10000 - table["relief_bp"]), 10000, step, rule)
            elif name == "interchange_uplift":
                if row["cross_operator"]:
                    value = place(value * (10000 + table["uplift_bp"]), 10000, step, rule)
            elif name == "shortfall_levy":
                reference = value if params["levy_basis"] == "running_value" \
                    else basis[params["levy_basis"]]
                value = place(value + place(reference * table["levy_bp"], 10000, step, rule),
                              1, step, rule)
            else:
                raise ValueError("unknown adjustment " + repr(name))
        row["unit_fare_micros"] = max(value, gate["floor_fare_micros"])

    # --- reversal records and their reach ----------------------------------
    by_id = {row["tap_id"]: row for row in admitted}
    reach = params["void_reach"]
    reversals = sorted((r for r in admitted if r["op"] == "void"),
                       key=lambda r: (r["tapped_at"], r["tap_id"]))
    for reversal in reversals:
        for row in admitted:
            if row["tap_id"] == reversal["tap_id"]:
                continue
            if row["canonical_token"] != reversal["canonical_token"]:
                continue
            if reach == "tap_only":
                continue
            if reach == "token_zone_epoch" and row["zone_id"] != reversal["zone_id"]:
                continue
            if reach == "token_operator_epoch" and row["operator_id"] != reversal["operator_id"]:
                continue
            withdraw(row, "voided_by_reversal")
    for reversal in reversals:
        reversal["disposition"] = "withdrawn"
        reversal["withdrawal_reason"] = reversal["withdrawal_reason"] or "reversal_record"

    # --- suspension fixpoint ----------------------------------------------
    gate_rows = {}
    for row in admitted:
        gate_rows.setdefault(row["gate_id"], []).append(row)
    suspended = {}
    unvalidated = set()
    stood_down = set()
    for gate_id, gate in gates.items():
        if gate["decommissioned"]:
            suspended[gate_id] = "decommissioned"

    iterations = 0
    burdens = {}
    while True:
        iterations += 1
        changed = False
        for gate_id in sorted(gates):
            rows = gate_rows.get(gate_id, [])
            total = len(rows)
            defects = sum(1 for r in rows if r["disposition"] == "withdrawn")
            burden = (10000 * defects) // total if total else 0
            burdens[gate_id] = burden
            if gate_id not in suspended and total and burden > gates[gate_id]["fault_allowance_bp"]:
                suspended[gate_id] = "burden"
                changed = True
        for zone_id in sorted(zones):
            live_gates = [g for g in sorted(gates)
                          if gates[g]["zone_id"] == zone_id and g not in suspended
                          and any(r["disposition"] == "priced" for r in gate_rows.get(g, []))]
            if zone_id in unvalidated:
                continue
            if len(live_gates) < zones[zone_id]["validation_floor"]:
                unvalidated.add(zone_id)
                changed = True
        for zone_id in sorted(zones):
            if zone_id in unvalidated or not zones[zone_id]["provisional"]:
                continue
            siblings = [z for z in sorted(zones)
                        if z != zone_id
                        and zones[z]["operator_id"] == zones[zone_id]["operator_id"]]
            if any(z in unvalidated for z in siblings):
                unvalidated.add(zone_id)
                changed = True
        for operator_id in sorted(operators):
            owned = [z for z in sorted(zones) if zones[z]["operator_id"] == operator_id]
            if operator_id in stood_down or not owned:
                continue
            if all(z in unvalidated for z in owned):
                stood_down.add(operator_id)
                changed = True
        for gate_id in sorted(gates):
            if gate_id in suspended:
                continue
            zone_id = gates[gate_id]["zone_id"]
            if zone_id in unvalidated:
                suspended[gate_id] = "zone_unvalidated"
                changed = True
            elif zones.get(zone_id, {}).get("operator_id") in stood_down:
                suspended[gate_id] = "operator_stood_down"
                changed = True
        for gate_id in sorted(suspended):
            for row in gate_rows.get(gate_id, []):
                if row["disposition"] == "priced":
                    withdraw(row, "gate_suspended")
                    changed = True
        if not changed:
            break

    # --- exceptions --------------------------------------------------------
    upheld = 0
    rejected = 0
    on_withdrawn = []
    for exception in registers["exceptions"]:
        row = by_id.get(exception["tap_id"])
        if exception["status"] == "upheld":
            upheld += 1
        else:
            rejected += 1
        if row is None:
            continue
        if exception["status"] != "upheld":
            continue
        if row["disposition"] != "priced":
            on_withdrawn.append(exception["exception_id"])
            continue
        row["exception_id"] = exception["exception_id"]
        row["unit_fare_micros"] = exception["unit_fare_micros"]

    # --- revenue caps, surplus lending, curtailment -----------------------
    def priced_of(zone_id):
        return [r for r in admitted
                if r["zone_id"] == zone_id and r["disposition"] == "priced"]

    def zone_total(zone_id):
        return sum(r["unit_fare_micros"] for r in priced_of(zone_id))

    headroom = {z: zones[z]["revenue_cap_micros"] - zone_total(z) for z in zones}
    order_name = params["cap_release_order"]
    if order_name == "ascending_zone_id":
        release_order = sorted(zones)
    elif order_name == "descending_headroom_then_zone":
        release_order = sorted(zones, key=lambda z: (-headroom[z], z))
    elif order_name == "ascending_headroom_then_zone":
        release_order = sorted(zones, key=lambda z: (headroom[z], z))
    elif order_name == "descending_cap_then_zone":
        release_order = sorted(zones, key=lambda z: (-zones[z]["revenue_cap_micros"], z))
    else:
        raise ValueError("unknown cap release order " + repr(order_name))

    effective_cap = {z: zones[z]["revenue_cap_micros"] for z in zones}
    lent = {z: 0 for z in zones}
    borrowed = {z: 0 for z in zones}
    operator_lent = {o: 0 for o in operators}
    loans = []
    free = dict(headroom)
    for zone_id in release_order:
        need = -free[zone_id]
        if need <= 0:
            continue
        operator_id = zones[zone_id]["operator_id"]
        ceiling = operators[operator_id]["float_ceiling_micros"]
        for lender in release_order:
            if need <= 0:
                break
            if lender == zone_id or zones[lender]["operator_id"] != operator_id:
                continue
            available = free[lender]
            room = ceiling - operator_lent[operator_id]
            amount = min(available, need, room)
            if amount <= 0:
                continue
            free[lender] -= amount
            free[zone_id] += amount
            effective_cap[zone_id] += amount
            lent[lender] += amount
            borrowed[zone_id] += amount
            operator_lent[operator_id] += amount
            need -= amount
            loans.append({"from_zone": lender, "to_zone": zone_id,
                          "operator_id": operator_id, "amount_micros": amount})

    cap_rows = []
    cap_infeasible = []
    for zone_id in sorted(zones):
        before = zone_total(zone_id)
        curtailed = []
        total = before
        if total > effective_cap[zone_id]:
            candidates = sorted(priced_of(zone_id),
                                key=lambda r: (-r["unit_fare_micros"], r["tapped_at"], r["tap_id"]))
            for row in candidates:
                if total <= effective_cap[zone_id]:
                    break
                gate_id = row["gate_id"]
                siblings = [r for r in priced_of(row["zone_id"])
                            if r["gate_id"] == gate_id]
                if gate_id not in suspended and len(siblings) <= 1:
                    continue
                withdraw(row, "cap_curtailed")
                curtailed.append(row["tap_id"])
                total -= row["unit_fare_micros"]
        residual = max(0, total - effective_cap[zone_id])
        if residual:
            cap_infeasible.append(zone_id)
        cap_rows.append({
            "zone_id": zone_id,
            "revenue_cap_micros": zones[zone_id]["revenue_cap_micros"],
            "effective_cap_micros": effective_cap[zone_id],
            "priced_total_before_micros": before,
            "priced_total_after_micros": total,
            "lent_micros": lent[zone_id],
            "borrowed_micros": borrowed[zone_id],
            "curtailed_tap_ids": sorted(curtailed),
            "residual_micros": residual,
            "cap_infeasible": bool(residual),
        })

    # --- running charge ----------------------------------------------------
    ledger.sort(key=lambda r: (r["tapped_at"], r["tap_id"]))
    running = 0
    for row in ledger:
        if row["disposition"] == "priced":
            running += row["unit_fare_micros"]
        row["running_charge_micros"] = running

    priced = [r for r in ledger if r["disposition"] == "priced"]
    withdrawn = [r for r in ledger if r["disposition"] == "withdrawn"]
    out_of_epoch = [r for r in ledger if r["disposition"] == "out_of_epoch"]
    charge = sum(r["unit_fare_micros"] for r in priced)

    zones_in_scope = sorted({r["zone_id"] for r in priced})
    operators_in_scope = sorted({r["operator_id"] for r in priced})

    state = {
        "epoch": epoch,
        "policy": policy,
        "operators": operators,
        "zones": zones,
        "gates": gates,
        "ledger": ledger,
        "priced": priced,
        "withdrawn": withdrawn,
        "out_of_epoch": out_of_epoch,
        "charge": charge,
        "params": params,
        "suspended": suspended,
        "burdens": burdens,
        "unvalidated": sorted(unvalidated),
        "stood_down": sorted(stood_down),
        "iterations": iterations,
        "cap_rows": cap_rows,
        "cap_infeasible": cap_infeasible,
        "loans": loans,
        "release_order": release_order,
        "zones_in_scope": zones_in_scope,
        "operators_in_scope": operators_in_scope,
        "exceptions": {"total": len(registers["exceptions"]), "upheld": upheld,
                       "rejected": rejected, "on_withdrawn": sorted(on_withdrawn)},
        "registers": registers,
        "gate_rows": gate_rows,
    }
    return state


# ---------------------------------------------------------------------------
# netting
# ---------------------------------------------------------------------------

def canonical_cycle(edges):
    """The first simple cycle of the obligation graph in canonical order.

    Cycles are compared by length first and then by the node sequence written
    from the smallest node it contains. The shortest sequence that sorts first
    is the one the netting rulebook cancels next.
    """
    nodes = sorted({payer for payer, _ in edges} | {payee for _, payee in edges})
    successors = {node: [] for node in nodes}
    for payer, payee in sorted(edges):
        successors[payer].append(payee)
    best = None
    for start in nodes:
        # Only nodes at or above start are walked, so every path found here has
        # start as its smallest member and each cycle is met exactly once, from
        # the node it is written from.
        stack = [(start, (start,), {start})]
        while stack:
            node, path, seen = stack.pop()
            for nxt in successors[node]:
                if nxt == start:
                    key = (len(path), path)
                    if best is None or key < best[0]:
                        best = (key, path)
                elif nxt > start and nxt not in seen:
                    if best is not None and len(path) + 1 > best[0][0]:
                        continue
                    stack.append((nxt, path + (nxt,), seen | {nxt}))
    return list(best[1]) if best else None


def net_epoch(state):
    """Net the interchange obligations the cleared ledger raises."""
    params = state["params"]
    policy = state["registers"]["netting_policy"][0]
    share_bp = policy["interchange_share_bp"]
    step = params["grid_step_micros"]
    rule = params["midpoint_rule"]

    gross = {}
    tap_counts = {}
    for row in sorted(state["priced"], key=lambda r: (r["tapped_at"], r["tap_id"])):
        if not row["cross_operator"]:
            continue
        key = (row["operator_id"], row["home_operator_id"])
        amount = place(row["unit_fare_micros"] * share_bp, 10000, step, rule)
        if amount <= 0:
            continue
        gross[key] = gross.get(key, 0) + amount
        tap_counts[key] = tap_counts.get(key, 0) + 1

    residual = dict(gross)
    cycles = []
    while True:
        live = {key for key, amount in residual.items() if amount > 0}
        if not live:
            break
        cycle = canonical_cycle(live)
        if cycle is None:
            break
        pairs = [(cycle[i], cycle[(i + 1) % len(cycle)]) for i in range(len(cycle))]
        amount = min(residual[pair] for pair in pairs)
        for pair in pairs:
            residual[pair] -= amount
            if residual[pair] == 0:
                del residual[pair]
        cycles.append({"sequence": list(cycle), "amount_micros": amount})

    operators = state["operators"]
    positions = []
    for operator_id in sorted(operators):
        gross_out = sum(a for (p, _), a in gross.items() if p == operator_id)
        gross_in = sum(a for (_, q), a in gross.items() if q == operator_id)
        res_out = sum(a for (p, _), a in residual.items() if p == operator_id)
        res_in = sum(a for (_, q), a in residual.items() if q == operator_id)
        positions.append({
            "operator_id": operator_id,
            "gross_out_micros": gross_out,
            "gross_in_micros": gross_in,
            "residual_out_micros": res_out,
            "residual_in_micros": res_in,
            "net_position_micros": res_out - res_in,
        })

    rank = {o: operators[o]["clearing_rank"] for o in operators}
    schedule_edges = sorted(residual.items(),
                            key=lambda item: (rank.get(item[0][0], 0), rank.get(item[0][1], 0),
                                              -item[1], item[0][0], item[0][1]))
    funded_running = {o: 0 for o in operators}
    schedule = []
    for (payer, payee), amount in schedule_edges:
        ceiling = operators[payer]["funding_ceiling_micros"]
        if funded_running[payer] + amount > ceiling:
            state_name = "deferred"
        else:
            funded_running[payer] += amount
            state_name = "funded"
        schedule.append({
            "payer": payer, "payee": payee, "amount_micros": amount,
            "state": state_name,
            "payer_funded_running_micros": funded_running[payer],
        })

    digest = 0
    for entry in schedule:
        digest = (digest * policy["netting_multiplier"] + entry["amount_micros"]) \
            % policy["netting_modulus"]

    return {
        "share_bp": share_bp,
        "gross": gross,
        "tap_counts": tap_counts,
        "residual": residual,
        "cycles": cycles,
        "positions": positions,
        "schedule": schedule,
        "funded_running": funded_running,
        "digest": digest,
        "policy": policy,
    }


# ---------------------------------------------------------------------------
# assurance
# ---------------------------------------------------------------------------

def lower_middle_median(sample):
    """The median of a sample, taking the lower middle of an even sample.

    The assurance rulebook settles an even sample on the lower of its two
    middle values rather than averaging them, so the median is always a value
    the sample actually contains.
    """
    ordered = sorted(sample)
    count = len(ordered)
    if count == 0:
        return 0
    return ordered[count // 2] if count % 2 else ordered[count // 2 - 1]


def assure_epoch(state):
    """Settle the cleared ledger onto a per distance unit basis."""
    policy = state["registers"]["assurance_policy"][0]
    gates = state["gates"]

    zero_distance = []
    sample = []
    for row in sorted(state["priced"], key=lambda r: r["tap_id"]):
        if row["distance_units"] <= 0:
            zero_distance.append(row["tap_id"])
            continue
        floor = gates[row["gate_id"]]["floor_fare_micros"]
        margin = (row["unit_fare_micros"] - floor) // row["distance_units"]
        sample.append({
            "tap_id": row["tap_id"],
            "rider_class": row["rider_class"],
            "unit_fare_micros": row["unit_fare_micros"],
            "floor_fare_micros": floor,
            "distance_units": row["distance_units"],
            "margin": margin,
        })

    median = lower_middle_median([entry["margin"] for entry in sample])
    for entry in sample:
        entry["deviation"] = abs(entry["margin"] - median)
    mad = lower_middle_median([entry["deviation"] for entry in sample])
    threshold = policy["assurance_sigma"] * mad
    small = len(sample) <= policy["min_sample"]
    for entry in sample:
        entry["held_back"] = (not small) and entry["deviation"] > threshold

    retained = [e for e in sample if not e["held_back"]]
    held_back = [e for e in sample if e["held_back"]]
    pool = sum(e["margin"] for e in retained)

    priced_distance = sum(r["distance_units"] for r in state["priced"])
    retained_distance = sum(e["distance_units"] for e in retained)
    classes = sorted({e["rider_class"] for e in retained})
    weights = {c: sum(e["margin"] for e in retained if e["rider_class"] == c) for c in classes}
    weight_total = sum(weights.values())
    shares = {c: 0 for c in classes}
    if classes and weight_total > 0:
        remainders = []
        assigned = 0
        for c in classes:
            exact = retained_distance * weights[c]
            base = exact // weight_total
            shares[c] = base
            assigned += base
            remainders.append((exact - base * weight_total, c))
        remainders.sort(key=lambda item: (-item[0], item[1]))
        index = 0
        while assigned < retained_distance and remainders:
            shares[remainders[index % len(remainders)][1]] += 1
            assigned += 1
            index += 1
    elif classes:
        shares[classes[0]] = retained_distance

    ordered = sorted(retained, key=lambda e: (e["margin"], e["tap_id"]))
    digest = 0
    for entry in ordered:
        digest = (digest * policy["assurance_multiplier"] + entry["margin"]) \
            % policy["assurance_modulus"]

    ladder = []
    for rider_class in sorted({e["rider_class"] for e in sample}):
        ladder.append({
            "rider_class": rider_class,
            "retained_count": sum(1 for e in retained if e["rider_class"] == rider_class),
            "held_back_count": sum(1 for e in held_back if e["rider_class"] == rider_class),
            "margin_total": sum(e["margin"] for e in retained if e["rider_class"] == rider_class),
            "share_units": shares.get(rider_class, 0),
        })

    return {
        "policy": policy,
        "sample": sample,
        "median": median,
        "mad": mad,
        "threshold": threshold,
        "retained": retained,
        "held_back": held_back,
        "pool": pool,
        "ordered": ordered,
        "digest": digest,
        "shares": shares,
        "share_total": sum(shares.values()),
        "priced_distance": priced_distance,
        "retained_distance": retained_distance,
        "zero_distance": zero_distance,
        "ladder": ladder,
    }


# ---------------------------------------------------------------------------
# parameter recovery
# ---------------------------------------------------------------------------

def calibration_figures(state, netting, assurance):
    """The figures the calibration material publishes for a cleared epoch."""
    return {
        "epoch_charge_micros": state["charge"],
        "taps_priced": len(state["priced"]),
        "taps_withdrawn": len(state["withdrawn"]),
        "priced_distance_units": assurance["priced_distance"],
        "unit_fare_checks": {row["tap_id"]: row["unit_fare_micros"]
                             for row in state["priced"]},
        "suspended_gates": sorted(state["suspended"]),
        "curtailed_tap_ids": sorted(
            tap for entry in state["cap_rows"] for tap in entry["curtailed_tap_ids"]),
        "loan_total_micros": sum(loan["amount_micros"] for loan in state["loans"]),
        "loans": [[loan["from_zone"], loan["to_zone"], loan["amount_micros"]]
                  for loan in state["loans"]],
        "netting_digest": netting["digest"],
        "assurance_pool_micros": assurance["pool"],
        "assurance_digest": assurance["digest"],
    }


def _figure_stages(registers, params, published):
    """Clear the calibration slice under one reading and compare in stages.

    The cheap figures are compared before the expensive ones so that a reading
    that already disagrees about pricing never pays for the netting and the
    assurance passes.
    """
    state = clear_epoch(registers, params)
    if state["charge"] != published["epoch_charge_micros"]:
        return False
    if len(state["priced"]) != published["taps_priced"]:
        return False
    if len(state["withdrawn"]) != published["taps_withdrawn"]:
        return False
    fares = {row["tap_id"]: row["unit_fare_micros"] for row in state["priced"]}
    if fares != published["unit_fare_checks"]:
        return False
    if sorted(state["suspended"]) != published["suspended_gates"]:
        return False
    curtailed = sorted(tap for entry in state["cap_rows"]
                       for tap in entry["curtailed_tap_ids"])
    if curtailed != published["curtailed_tap_ids"]:
        return False
    if sum(loan["amount_micros"] for loan in state["loans"]) != published["loan_total_micros"]:
        return False
    loans = [[loan["from_zone"], loan["to_zone"], loan["amount_micros"]]
             for loan in state["loans"]]
    if loans != [list(entry) for entry in published["loans"]]:
        return False
    assurance = assure_epoch(state)
    if assurance["priced_distance"] != published["priced_distance_units"]:
        return False
    if assurance["pool"] != published["assurance_pool_micros"]:
        return False
    if assurance["digest"] != published["assurance_digest"]:
        return False
    netting = net_epoch(state)
    return netting["digest"] == published["netting_digest"]


def recover_parameters(registers):
    """Find the one reading of the seven properties the calibration admits."""
    block = registers["calibration"]
    legal = block["legal_values"]
    published = block["published"]
    slice_registers = registers_from_slice(block["slice"])

    space = [legal[name] for name in PROPERTY_NAMES]
    found = None
    for combination in itertools.product(*space):
        params = dict(zip(PROPERTY_NAMES, combination))
        params["adjustment_order"] = list(params["adjustment_order"])
        if _figure_stages(slice_registers, params, published):
            found = params
            break
    if found is None:
        raise SystemExit("no reading of the seven properties reproduces the calibration figures")
    return found


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------

def _dump(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _dump_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(",".join(header) + "\n")
        for row in rows:
            handle.write(",".join(str(cell) for cell in row) + "\n")


LEDGER_FIELDS = (
    "tap_id", "canonical_token", "identity_outcome", "gate_id", "zone_id",
    "operator_id", "home_operator_id", "tapped_at", "distance_units",
    "rider_class", "completion_class", "op", "governing_table_id", "peak",
    "cross_operator", "gross_before_adjustments_micros", "unit_fare_micros",
    "disposition", "withdrawal_reason", "exception_id", "running_charge_micros",
)


def build_artifacts(state, netting, assurance):
    """Every artifact the cleared epoch owes, as a path to payload mapping."""
    epoch = state["epoch"]
    params = state["params"]
    gates = state["gates"]
    zones = state["zones"]
    ledger = state["ledger"]
    priced = state["priced"]
    withdrawn = state["withdrawn"]
    net_by_operator = {p["operator_id"]: p["net_position_micros"]
                       for p in netting["positions"]}

    files = {}

    files["summary.json"] = {
        "epoch_id": epoch["epoch_id"],
        "epoch_opens_at": epoch["opens_at"],
        "epoch_closes_at": epoch["closes_at"],
        "resolved_parameters": {
            "adjustment_order": list(params["adjustment_order"]),
            "levy_basis": params["levy_basis"],
            "grid_step_micros": params["grid_step_micros"],
            "midpoint_rule": params["midpoint_rule"],
            "void_reach": params["void_reach"],
            "cap_release_order": params["cap_release_order"],
            "fault_window_edge": params["fault_window_edge"],
        },
        "taps_total": len(ledger),
        "taps_admitted": len(priced) + len(withdrawn),
        "taps_priced": len(priced),
        "taps_withdrawn": len(withdrawn),
        "taps_out_of_epoch": len(state["out_of_epoch"]),
        "epoch_charge_micros": state["charge"],
        "priced_distance_units": sum(r["distance_units"] for r in priced),
        "admitted_distance_units": sum(r["distance_units"] for r in priced + withdrawn),
        "suspended_gates": sorted(state["suspended"]),
        "unvalidated_zones": state["unvalidated"],
        "stood_down_operators": state["stood_down"],
        "operators_in_scope": state["operators_in_scope"],
        "zones_in_scope": state["zones_in_scope"],
        "cap_infeasible_zones": sorted(state["cap_infeasible"]),
    }

    zone_charge = {}
    operator_charge = {}
    for row in priced:
        zone_charge[row["zone_id"]] = zone_charge.get(row["zone_id"], 0) + row["unit_fare_micros"]
        operator_charge[row["operator_id"]] = \
            operator_charge.get(row["operator_id"], 0) + row["unit_fare_micros"]

    admitted_by_predicate = [
        row for row in ledger
        if within(row["tapped_at"], epoch["opens_at"], epoch["closes_at"],
                  state["policy"]["boundary"])]
    cap_released = sum(entry["effective_cap_micros"] - entry["revenue_cap_micros"]
                       for entry in state["cap_rows"])
    identities = [
        ("admitted_plus_out_of_epoch_equals_total",
         len(priced) + len(withdrawn) + len(state["out_of_epoch"]), len(ledger)),
        ("priced_plus_withdrawn_equals_admitted",
         len(priced) + len(withdrawn), len(admitted_by_predicate)),
        ("zone_charges_sum_to_epoch_charge", sum(zone_charge.values()), state["charge"]),
        ("operator_charges_sum_to_epoch_charge",
         sum(operator_charge.values()), state["charge"]),
        ("ledger_running_total_closes_on_epoch_charge",
         ledger[-1]["running_charge_micros"] if ledger else 0, state["charge"]),
        ("priced_plus_withdrawn_distance_equals_admitted_distance",
         sum(r["distance_units"] for r in priced) + sum(r["distance_units"] for r in withdrawn),
         sum(r["distance_units"] for r in admitted_by_predicate)),
        ("loans_granted_equal_cap_released",
         sum(loan["amount_micros"] for loan in state["loans"]), cap_released),
        ("net_positions_sum_to_zero",
         sum(p["net_position_micros"] for p in netting["positions"]), 0),
        ("residual_plus_cancelled_equals_gross",
         sum(netting["residual"].values())
         + sum(c["amount_micros"] * len(c["sequence"]) for c in netting["cycles"]),
         sum(netting["gross"].values())),
        ("assurance_shares_sum_to_retained_distance",
         assurance["share_total"], assurance["retained_distance"]),
        ("retained_margins_sum_to_pool",
         sum(e["margin"] for e in assurance["retained"]), assurance["pool"]),
    ]
    files["reconciliation.json"] = {
        "identities": [{"identity": name, "left": left, "right": right,
                        "residual": left - right} for name, left, right in identities],
        "residual_total": sum(left - right for _, left, right in identities),
    }

    files["tap_ledger.json"] = {
        "rows": [{field: row[field] for field in LEDGER_FIELDS} for row in ledger],
        "row_count": len(ledger),
        "charge_micros": state["charge"],
    }

    by_outcome = {}
    resolutions = []
    for row in sorted(ledger, key=lambda r: r["tap_id"]):
        if row["disposition"] == "out_of_epoch":
            continue
        by_outcome.setdefault(row["identity_outcome"], []).append(row["tap_id"])
        resolutions.append({
            "tap_id": row["tap_id"],
            "token_ref": row["token_ref"],
            "canonical_token": row["canonical_token"],
            "outcome": row["identity_outcome"],
            "chain": list(row["identity_chain"]),
        })
    files["identity_register.json"] = {
        "outcomes": [{"outcome": outcome, "tap_ids": sorted(tap_ids),
                      "count": len(tap_ids)}
                     for outcome, tap_ids in sorted(by_outcome.items())],
        "resolutions": resolutions,
    }

    quality_fields = {
        "taps_out_of_epoch": sorted(r["tap_id"] for r in state["out_of_epoch"]),
        "taps_without_governing_table": sorted(
            r["tap_id"] for r in withdrawn if r["withdrawal_reason"] == "no_governing_table"),
        "taps_with_retired_identity": sorted(
            r["tap_id"] for r in withdrawn if r["withdrawal_reason"] == "identity_retired"),
        "taps_with_revoked_identity": sorted(
            r["tap_id"] for r in withdrawn if r["withdrawal_reason"] == "identity_revoked"),
        "identity_cycles_broken": sorted(
            r["tap_id"] for r in priced + withdrawn
            if r["identity_outcome"] == "cycle_broken"),
        "duplicate_tap_ids": sorted(
            r["tap_id"] for r in withdrawn if r["withdrawal_reason"] == "duplicate_tap_id"),
        "zero_distance_taps": sorted(assurance["zero_distance"]),
        "decommissioned_gates": sorted(
            g for g in gates if gates[g]["decommissioned"]),
        "faults_open_at_close": sorted(
            f["fault_id"] for f in state["registers"]["gate_faults"] if not f["closed_at"]),
        "exceptions_total": state["exceptions"]["total"],
        "exceptions_upheld": state["exceptions"]["upheld"],
        "exceptions_rejected": state["exceptions"]["rejected"],
        "exceptions_on_withdrawn_taps": state["exceptions"]["on_withdrawn"],
    }
    files["data_quality.json"] = quality_fields

    files["suspension_register.json"] = {
        "iterations": state["iterations"],
        "gates": [{
            "gate_id": gate_id,
            "zone_id": gates[gate_id]["zone_id"],
            "burden_bp": state["burdens"].get(gate_id, 0),
            "allowance_bp": gates[gate_id]["fault_allowance_bp"],
            "suspended": gate_id in state["suspended"],
            "reason": state["suspended"].get(gate_id, ""),
        } for gate_id in sorted(gates)],
        "zones": [{
            "zone_id": zone_id,
            "validated_gate_count": sum(
                1 for g in sorted(gates)
                if gates[g]["zone_id"] == zone_id and g not in state["suspended"]),
            "validation_floor": zones[zone_id]["validation_floor"],
            "unvalidated": zone_id in state["unvalidated"],
        } for zone_id in sorted(zones)],
        "operators": [{"operator_id": operator_id,
                       "stood_down": operator_id in state["stood_down"]}
                      for operator_id in sorted(state["operators"])],
    }

    files["cap_relief.json"] = {
        "release_order": list(state["release_order"]),
        "zones": state["cap_rows"],
        "loans": state["loans"],
        "loan_total_micros": sum(loan["amount_micros"] for loan in state["loans"]),
    }

    for operator_id in state["operators_in_scope"]:
        rows = [r for r in priced if r["operator_id"] == operator_id]
        files["operator_%s.json" % operator_id] = {
            "partition_kind": "operator",
            "partition_id": operator_id,
            "epoch_id": epoch["epoch_id"],
            "taps_priced": len(rows),
            "taps_withdrawn": sum(1 for r in withdrawn if r["operator_id"] == operator_id),
            "charge_micros": sum(r["unit_fare_micros"] for r in rows),
            "priced_distance_units": sum(r["distance_units"] for r in rows),
            "zones_in_scope": sorted({r["zone_id"] for r in rows}),
            "gates_suspended": sorted(
                g for g in state["suspended"]
                if zones.get(gates[g]["zone_id"], {}).get("operator_id") == operator_id),
            "net_position_micros": net_by_operator.get(operator_id, 0),
        }

    cap_by_zone = {entry["zone_id"]: entry for entry in state["cap_rows"]}
    for zone_id in state["zones_in_scope"]:
        rows = [r for r in priced if r["zone_id"] == zone_id]
        entry = cap_by_zone[zone_id]
        files["zone_%s.json" % zone_id] = {
            "partition_kind": "zone",
            "partition_id": zone_id,
            "epoch_id": epoch["epoch_id"],
            "operator_id": zones[zone_id]["operator_id"],
            "taps_priced": len(rows),
            "taps_withdrawn": sum(1 for r in withdrawn if r["zone_id"] == zone_id),
            "charge_micros": sum(r["unit_fare_micros"] for r in rows),
            "priced_distance_units": sum(r["distance_units"] for r in rows),
            "revenue_cap_micros": entry["revenue_cap_micros"],
            "effective_cap_micros": entry["effective_cap_micros"],
            "gates_in_scope": sorted({r["gate_id"] for r in rows}),
            "cap_infeasible": entry["cap_infeasible"],
        }

    gross_edges = [{"payer": payer, "payee": payee, "amount_micros": amount,
                    "tap_count": netting["tap_counts"][(payer, payee)]}
                   for (payer, payee), amount in sorted(netting["gross"].items())]
    residual_edges = [{"payer": payer, "payee": payee, "amount_micros": amount}
                      for (payer, payee), amount in sorted(netting["residual"].items())]
    files["netting_summary.json"] = {
        "epoch_id": epoch["epoch_id"],
        "interchange_share_bp": netting["share_bp"],
        "obligation_total_micros": sum(netting["gross"].values()),
        "residual_total_micros": sum(netting["residual"].values()),
        "cancelled_cycle_count": len(netting["cycles"]),
        "cancelled_total_micros": sum(
            c["amount_micros"] * len(c["sequence"]) for c in netting["cycles"]),
        "net_position_total_micros": sum(p["net_position_micros"] for p in netting["positions"]),
        "netting_digest": netting["digest"],
        "funded_edge_count": sum(1 for e in netting["schedule"] if e["state"] == "funded"),
        "deferred_edge_count": sum(1 for e in netting["schedule"] if e["state"] == "deferred"),
        "funded_total_micros": sum(
            e["amount_micros"] for e in netting["schedule"] if e["state"] == "funded"),
        "deferred_total_micros": sum(
            e["amount_micros"] for e in netting["schedule"] if e["state"] == "deferred"),
    }
    files["netting_obligations.json"] = {
        "edges": gross_edges, "total_micros": sum(netting["gross"].values())}
    files["netting_residual.json"] = {
        "edges": residual_edges,
        "cycles": netting["cycles"],
        "total_micros": sum(netting["residual"].values()),
    }
    files["netting_positions.json"] = {
        "positions": netting["positions"],
        "net_total_micros": sum(p["net_position_micros"] for p in netting["positions"]),
    }
    files["netting_schedule.json"] = {
        "rows": netting["schedule"],
        "funding_ceilings": [{
            "operator_id": operator_id,
            "funding_ceiling_micros": state["operators"][operator_id]["funding_ceiling_micros"],
            "funded_micros": netting["funded_running"][operator_id],
        } for operator_id in sorted(state["operators"])],
    }

    files["assurance_summary.json"] = {
        "epoch_id": epoch["epoch_id"],
        "assurance_sigma": assurance["policy"]["assurance_sigma"],
        "assurance_modulus": assurance["policy"]["assurance_modulus"],
        "min_sample": assurance["policy"]["min_sample"],
        "sample_size": len(assurance["sample"]),
        "median_margin": assurance["median"],
        "mad": assurance["mad"],
        "threshold": assurance["threshold"],
        "retained_count": len(assurance["retained"]),
        "held_back_count": len(assurance["held_back"]),
        "pool_micros": assurance["pool"],
        "assurance_digest": assurance["digest"],
        "priced_distance_units": assurance["priced_distance"],
        "zero_distance_taps": sorted(assurance["zero_distance"]),
    }
    files["assurance_margins.json"] = {
        "rows": [{
            "tap_id": e["tap_id"], "rider_class": e["rider_class"],
            "unit_fare_micros": e["unit_fare_micros"],
            "floor_fare_micros": e["floor_fare_micros"],
            "distance_units": e["distance_units"], "margin": e["margin"],
            "deviation": e["deviation"], "held_back": e["held_back"],
        } for e in sorted(assurance["sample"], key=lambda e: e["tap_id"])],
        "row_count": len(assurance["sample"]),
    }
    files["assurance_holdbacks.json"] = {
        "rows": [{
            "tap_id": e["tap_id"], "margin": e["margin"],
            "median_margin": assurance["median"], "deviation": e["deviation"],
            "threshold": assurance["threshold"],
        } for e in sorted(assurance["held_back"], key=lambda e: e["tap_id"])],
        "row_count": len(assurance["held_back"]),
    }
    files["assurance_order.json"] = {
        "tap_ids": [e["tap_id"] for e in assurance["ordered"]],
        "margins": [e["margin"] for e in assurance["ordered"]],
        "digest": assurance["digest"],
    }
    files["assurance_apportionment.json"] = {
        "retained_distance_units": assurance["retained_distance"],
        "shares": [{
            "rider_class": rider_class,
            "retained_margin_micros": sum(
                e["margin"] for e in assurance["retained"] if e["rider_class"] == rider_class),
            "share_units": assurance["shares"][rider_class],
        } for rider_class in sorted(assurance["shares"])],
        "share_total_units": assurance["share_total"],
    }
    return files


LADDER_HEADER = ("rider_class", "retained_count", "held_back_count",
                 "margin_total", "share_units")
CYCLES_HEADER = ("cycle_index", "sequence", "amount_micros")


def write_outputs(out_dir, state, netting, assurance):
    os.makedirs(out_dir, exist_ok=True)
    for name, payload in build_artifacts(state, netting, assurance).items():
        _dump(os.path.join(out_dir, name), payload)
    _dump_csv(os.path.join(out_dir, "netting_cycles.csv"), CYCLES_HEADER,
              [(index + 1, ">".join(cycle["sequence"]), cycle["amount_micros"])
               for index, cycle in enumerate(netting["cycles"])])
    _dump_csv(os.path.join(out_dir, "assurance_ladder.csv"), LADDER_HEADER,
              [(row["rider_class"], row["retained_count"], row["held_back_count"],
                row["margin_total"], row["share_units"]) for row in assurance["ladder"]])


def settle(data_dir, out_dir=None, params=None):
    registers = load_registers(data_dir)
    if params is None:
        params = recover_parameters(registers)
    state = clear_epoch(registers, params)
    netting = net_epoch(state)
    assurance = assure_epoch(state)
    if out_dir is not None:
        write_outputs(out_dir, state, netting, assurance)
    return state, netting, assurance


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: %s <register-directory> <output-directory>\n" % argv[0])
        return 2
    settle(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
