#!/usr/bin/env python3
"""Reference settlement engine for one change data capture ingest window.

The program takes a data directory and an output directory as positional
arguments.  It reads only the machine readable registers, recovers the five
withheld properties from the published calibration block, settles the window
and writes every artifact.  It holds no instance specific constant.
"""

from __future__ import annotations

import csv
import itertools
import json
import sys
from pathlib import Path

CURATED = "curated"
WITHDRAWN = "withdrawn"
QUARANTINED = "quarantined"

R_TOMBSTONE = "withdrawn_by_tombstone"
R_RETIRED = "withdrawn_retired_producer"
R_UNKNOWN = "withdrawn_unknown_producer"
R_CYCLIC = "withdrawn_cyclic_identity"
R_NO_CARD = "withdrawn_no_governing_card"
R_PROVISIONAL = "withdrawn_provisional_domain"
R_RESERVE = "withdrawn_by_reserve_designation"
R_CASCADE = "withdrawn_by_quarantine_cascade"
R_CURTAIL = "withdrawn_by_curtailment"
R_QUARANTINE = "quarantined_defect_rate"

ADJUSTMENTS = ("abatement", "override", "rebate", "surcharge")
ROUNDING_MODES = ("ceil", "floor", "half_down", "half_even", "half_up")
STEP_CHOICES = (5, 10, 20, 25, 40, 50, 80, 100, 125)
COEFFICIENT_LIMIT = 600
TOMBSTONE_READINGS = ("forward", "retroactive")

CSV_REGISTERS = (
    "window_calendar",
    "window_policy",
    "channels",
    "domains",
    "feeds",
    "producers",
    "producer_events",
    "rate_cards",
    "feed_incidents",
    "landing_records",
    "egress_policy",
)


# --------------------------------------------------------------------------
# register loading
# --------------------------------------------------------------------------


def _rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _as_int(value) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text) if text else 0


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1"}


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def load_registers(data_dir: Path) -> dict:
    registers = {name: _rows(data_dir / (name + ".csv")) for name in CSV_REGISTERS}
    registers["exceptions"] = json.loads(
        (data_dir / "exceptions.json").read_text(encoding="utf-8")
    )
    return registers


def load_calibration(data_dir: Path) -> dict:
    return json.loads((data_dir / "calibration_controls.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# arithmetic
# --------------------------------------------------------------------------


def place(numerator: int, denominator: int, step: int, mode: str) -> int:
    """Place an exact rational charge on the settlement grid."""
    total = denominator * step
    whole, remainder = divmod(numerator, total)
    if remainder == 0:
        placed = whole
    elif mode == "floor":
        placed = whole
    elif mode == "ceil":
        placed = whole + 1
    elif mode == "half_up":
        placed = whole + 1 if 2 * remainder >= total else whole
    elif mode == "half_down":
        placed = whole + 1 if 2 * remainder > total else whole
    elif mode == "half_even":
        if 2 * remainder > total:
            placed = whole + 1
        elif 2 * remainder < total:
            placed = whole
        else:
            placed = whole if whole % 2 == 0 else whole + 1
    else:
        raise ValueError("unknown rounding convention: " + mode)
    return placed * step


# --------------------------------------------------------------------------
# identity resolution
# --------------------------------------------------------------------------


def build_identity_index(events: list[dict]) -> dict:
    index: dict[str, list[tuple]] = {}
    for row in events:
        subject = _text(row["subject_ref"])
        index.setdefault(subject, []).append(
            (
                _text(row["effective_at"]),
                _text(row["event_id"]),
                _text(row["event_type"]),
                _text(row["target_ref"]),
            )
        )
    for entries in index.values():
        entries.sort()
    return index


def resolve_identity(index: dict, known: set, ref: str, instant: str) -> tuple:
    """Follow the identity chain in force at an instant."""
    current = ref
    seen = {current}
    while True:
        entries = [item for item in index.get(current, []) if item[0] <= instant]
        if not entries:
            break
        kind = entries[-1][2]
        target = entries[-1][3]
        if kind == "retire":
            return current, "retired"
        if not target:
            break
        if target in seen:
            return current, "cyclic"
        seen.add(target)
        current = target
    if current not in known:
        return current, "unknown"
    return current, "resolved"


# --------------------------------------------------------------------------
# rate cards and incidents
# --------------------------------------------------------------------------


def governing_card(cards: list[dict], instant: str):
    live = []
    for card in cards:
        start = _text(card["effective_from"])
        stop = _text(card["superseded_at"])
        if start <= instant and (not stop or instant < stop):
            live.append((start, _text(card["card_id"]), card))
    if not live:
        return None
    live.sort(key=lambda item: (item[0], item[1]))
    return live[-1][2]


def governing_incident(incidents: list[dict], feed_id: str, instant: str):
    covering = []
    for row in incidents:
        if _text(row["feed_id"]) != feed_id:
            continue
        start = _text(row["opened_at"])
        stop = _text(row["closed_at"])
        if start <= instant and (not stop or instant < stop):
            covering.append((_as_int(row["severity"]), _text(row["incident_id"]), row))
    if not covering:
        return None
    covering.sort(key=lambda item: (item[0], item[1]))
    return covering[-1][2]


# --------------------------------------------------------------------------
# reserve slot designation
# --------------------------------------------------------------------------


def designate_reserve_slots(reg: dict) -> dict:
    feeds = {_text(row["feed_id"]): row for row in reg["feeds"]}
    domains = {_text(row["domain_id"]): row for row in reg["domains"]}
    close = _text(reg["window_calendar"][0]["window_close"])
    policy = {
        _text(row["policy_key"]): _as_int(row["policy_value"]) for row in reg["window_policy"]
    }
    low_bp = policy["designated_band_low_bp"]
    high_bp = policy["designated_band_high_bp"]

    capacity = sum(
        _as_int(row["nominal_throughput"])
        for row in reg["feeds"]
        if not _as_bool(row["suspended"])
    )

    per_channel = []
    for channel in sorted(reg["channels"], key=lambda row: _text(row["channel_id"])):
        channel_id = _text(channel["channel_id"])
        members = sorted(
            domain_id
            for domain_id, row in domains.items()
            if _text(row["channel_id"]) == channel_id
        )
        if not any(not _as_bool(domains[domain_id]["provisional"]) for domain_id in members):
            continue
        ceiling = _as_int(channel["slot_ceiling"])
        candidates = []
        live_by_domain: dict[str, list] = {}
        for feed_id in sorted(feeds):
            row = feeds[feed_id]
            domain_id = _text(row["domain_id"])
            if domain_id not in members or _as_bool(row["suspended"]):
                continue
            if _as_bool(domains[domain_id]["provisional"]):
                continue
            if governing_incident(reg["feed_incidents"], feed_id, close) is not None:
                continue
            live_by_domain.setdefault(domain_id, []).append(feed_id)
            candidates.append(feed_id)
        feasible = []
        for combo in itertools.combinations(candidates, ceiling):
            classes = [_text(feeds[feed_id]["feed_class"]) for feed_id in combo]
            if len(set(classes)) != len(classes) or "primary" not in classes:
                continue
            chosen = set(combo)
            if any(all(feed_id in chosen for feed_id in live) for live in live_by_domain.values()):
                continue
            feasible.append(tuple(sorted(combo)))
        per_channel.append((channel_id, ceiling, len(candidates), feasible))

    solutions = []
    for assignment in itertools.product(*[item[3] for item in per_channel]):
        total = sum(
            _as_int(feeds[feed_id]["nominal_throughput"])
            for combo in assignment
            for feed_id in combo
        )
        share = total * 10000 // capacity if capacity else 0
        if low_bp <= share <= high_bp:
            solutions.append(assignment)
    if len(solutions) != 1:
        raise SystemExit(
            "reserve slot designation is not uniquely feasible: %d assignments" % len(solutions)
        )
    winner = solutions[0]

    entries = []
    designated: set[str] = set()
    for (channel_id, ceiling, candidate_count, _), combo in zip(per_channel, winner):
        designated.update(combo)
        entries.append(
            {
                "candidate_feed_count": candidate_count,
                "channel_id": channel_id,
                "designated_feed_ids": list(combo),
                "designated_nominal_throughput": sum(
                    _as_int(feeds[feed_id]["nominal_throughput"]) for feed_id in combo
                ),
                "slot_ceiling": ceiling,
            }
        )
    return {
        "channels": entries,
        "designated": designated,
        "designated_band_high_bp": high_bp,
        "designated_band_low_bp": low_bp,
        "designated_nominal_throughput": sum(
            _as_int(feeds[feed_id]["nominal_throughput"]) for feed_id in sorted(designated)
        ),
        "window_nominal_throughput": capacity,
    }


# --------------------------------------------------------------------------
# curtailment
# --------------------------------------------------------------------------


def curtail(records: list[dict], cap: int, feed_ids: list[str]) -> set:
    """Choose the retained record identifiers under a curated unit cap.

    The retained set maximises settled charge, then record count, then takes
    the lexicographically smallest identifier list, and every feed that
    carried a curated record keeps at least one.
    """
    if sum(row["payload_units"] for row in records) <= cap:
        return {row["record_id"] for row in records}
    order = sorted(records, key=lambda row: row["record_id"])
    count = len(order)
    slot = {feed_id: position for position, feed_id in enumerate(sorted(feed_ids))}
    full = (1 << len(slot)) - 1

    reach: list[set] = [set() for _ in range(count + 1)]
    reach[0].add((0, 0))
    for position, row in enumerate(order):
        bit = 1 << slot[row["feed_id"]]
        units = row["payload_units"]
        nxt = reach[position + 1]
        for used, mask in reach[position]:
            if used + units <= cap:
                nxt.add((used + units, mask | bit))
            nxt.add((used, mask))

    table: list[dict] = [dict() for _ in range(count + 1)]
    for used, mask in reach[count]:
        if mask == full:
            table[count][(used, mask)] = (0, 0)
    for position in range(count - 1, -1, -1):
        row = order[position]
        bit = 1 << slot[row["feed_id"]]
        units = row["payload_units"]
        charge = row["record_charge_micros"]
        current = table[position]
        forward = table[position + 1]
        for state in reach[position]:
            used, mask = state
            best = None
            if used + units <= cap:
                value = forward.get((used + units, mask | bit))
                if value is not None:
                    best = (value[0] + charge, value[1] + 1)
            value = forward.get(state)
            if value is not None and (best is None or value > best):
                best = value
            if best is not None:
                current[state] = best

    if (0, 0) not in table[0]:
        raise SystemExit("no curtailment satisfies the feed coverage obligation")

    keep = set()
    used, mask = 0, 0
    for position, row in enumerate(order):
        bit = 1 << slot[row["feed_id"]]
        units = row["payload_units"]
        charge = row["record_charge_micros"]
        include = None
        if used + units <= cap:
            value = table[position + 1].get((used + units, mask | bit))
            if value is not None:
                include = (value[0] + charge, value[1] + 1)
        exclude = table[position + 1].get((used, mask))
        if include is not None and (exclude is None or include >= exclude):
            keep.add(row["record_id"])
            used += units
            mask |= bit
    return keep


# --------------------------------------------------------------------------
# charge composition
# --------------------------------------------------------------------------


def compose_charge(context: dict, params: dict) -> int:
    step = params["quantisation_step_micros"]
    mode = params["rounding_mode"]
    coefficient = params["backpressure_coefficient_micros"]
    value = place(context["rate"] * context["multiplier"], 10000, step, mode)
    for name in params["adjustment_precedence"]:
        if name == "abatement":
            value = place(max(0, value - context["abatement"]), 1, step, mode)
        elif name == "rebate":
            value = place(value * (10000 - context["allowance"]), 10000, step, mode)
        elif name == "override":
            if context["override"] is not None:
                value = place(context["override"], 1, step, mode)
        elif name == "surcharge":
            value = place(value + coefficient * context["excess_bp"] // 10000, 1, step, mode)
    return max(value, context["floor"])


def charge_context(reg: dict, feeds: dict, feed_units: dict, upheld: dict, row: dict) -> dict:
    feed = feeds[row["feed_id"]]
    card = governing_card(reg["rate_cards"], row["emitted_at"])
    incident = governing_incident(reg["feed_incidents"], row["feed_id"], row["emitted_at"])
    nominal = _as_int(feed["nominal_throughput"])
    used = feed_units.get(row["feed_id"], 0)
    return {
        "abatement": _as_int(incident["abatement_micros"]) if incident is not None else 0,
        "allowance": _as_int(feed["defect_allowance_bp"]),
        "excess_bp": max(0, (used - nominal) * 10000 // nominal) if nominal else 0,
        "floor": _as_int(feed["floor_rate_micros"]),
        "multiplier": _as_int(card["mult_" + row["form_class"]]),
        "override": upheld.get(row["record_id"]),
        "rate": _as_int(card["rate_" + row["tier_class"]]),
    }


# --------------------------------------------------------------------------
# settlement
# --------------------------------------------------------------------------


def settle(reg: dict, params: dict) -> dict:
    reading = params["tombstone_reading"]
    calendar = reg["window_calendar"][0]
    window_id = _text(calendar["window_id"])
    window_open = _text(calendar["window_open"])
    window_close = _text(calendar["window_close"])

    feeds = {_text(row["feed_id"]): row for row in reg["feeds"]}
    domains = {_text(row["domain_id"]): row for row in reg["domains"]}
    channels = {_text(row["channel_id"]): row for row in reg["channels"]}
    known = {_text(row["producer_id"]) for row in reg["producers"]}
    index = build_identity_index(reg["producer_events"])
    upheld = {
        _text(row["record_id"]): _as_int(row["agreed_unit_rate_micros"])
        for row in reg["exceptions"]
        if _text(row["status"]) == "upheld"
    }
    dismissed = sum(1 for row in reg["exceptions"] if _text(row["status"]) == "dismissed")

    slots = designate_reserve_slots(reg)
    designated = slots["designated"]

    quality = {
        "cyclic_identity_record_count": 0,
        "out_of_window_record_count": 0,
        "provisional_domain_record_count": 0,
        "records_without_governing_card": 0,
        "retired_producer_record_count": 0,
        "suspended_feed_record_count": 0,
        "unknown_producer_record_count": 0,
    }

    ledger: list[dict] = []
    identity_counts: dict[tuple, int] = {}
    for row in reg["landing_records"]:
        feed_id = _text(row["feed_id"])
        instant = _text(row["emitted_at"])
        feed = feeds[feed_id]
        if not (window_open <= instant < window_close):
            quality["out_of_window_record_count"] += 1
            continue
        if _as_bool(feed["suspended"]):
            quality["suspended_feed_record_count"] += 1
            continue
        ref = _text(row["producer_ref"])
        canonical, status = resolve_identity(index, known, ref, instant)
        key = (ref, canonical, status)
        identity_counts[key] = identity_counts.get(key, 0) + 1
        entry = {
            "canonical_producer_id": canonical,
            "domain_id": _text(feed["domain_id"]),
            "emitted_at": instant,
            "feed_id": feed_id,
            "form_class": _text(row["form_class"]),
            "governing_card_id": "",
            "identity_status": status,
            "op": _text(row["op"]),
            "payload_units": _as_int(row["payload_units"]),
            "record_id": _text(row["record_id"]),
            "tier_class": _text(row["tier_class"]),
        }
        if _as_bool(domains[entry["domain_id"]]["provisional"]):
            quality["provisional_domain_record_count"] += 1
            entry["disposition"] = WITHDRAWN
            entry["reason"] = R_PROVISIONAL
        elif status == "retired":
            quality["retired_producer_record_count"] += 1
            entry["disposition"] = WITHDRAWN
            entry["reason"] = R_RETIRED
        elif status == "unknown":
            quality["unknown_producer_record_count"] += 1
            entry["disposition"] = WITHDRAWN
            entry["reason"] = R_UNKNOWN
        elif status == "cyclic":
            quality["cyclic_identity_record_count"] += 1
            entry["disposition"] = WITHDRAWN
            entry["reason"] = R_CYCLIC
        else:
            card = governing_card(reg["rate_cards"], instant)
            if card is None:
                quality["records_without_governing_card"] += 1
                entry["disposition"] = WITHDRAWN
                entry["reason"] = R_NO_CARD
            else:
                entry["governing_card_id"] = _text(card["card_id"])
                entry["disposition"] = CURATED
                entry["reason"] = ""
        ledger.append(entry)

    tombstone_instant: dict[str, str] = {}
    for row in ledger:
        if row["reason"] == "" and row["op"] == "tombstone":
            entity = row["canonical_producer_id"]
            if entity not in tombstone_instant or row["emitted_at"] < tombstone_instant[entity]:
                tombstone_instant[entity] = row["emitted_at"]
    for row in ledger:
        if row["reason"] != "":
            continue
        instant = tombstone_instant.get(row["canonical_producer_id"])
        if instant is None:
            continue
        if reading == "retroactive" or row["emitted_at"] >= instant:
            row["disposition"] = WITHDRAWN
            row["reason"] = R_TOMBSTONE

    for row in ledger:
        if row["reason"] == "" and row["feed_id"] in designated:
            row["disposition"] = WITHDRAWN
            row["reason"] = R_RESERVE

    quarantined: set[str] = set()
    while True:
        cascade = {
            (row["domain_id"], row["canonical_producer_id"])
            for row in ledger
            if row["feed_id"] in quarantined and row["reason"] == ""
        }
        grown = set()
        for feed_id in sorted(feeds):
            if feed_id in designated or feed_id in quarantined:
                continue
            pool = [
                row
                for row in ledger
                if row["feed_id"] == feed_id and row["reason"] in ("", R_TOMBSTONE)
            ]
            if not pool:
                continue
            bad = sum(
                1
                for row in pool
                if row["reason"] == R_TOMBSTONE
                or (row["domain_id"], row["canonical_producer_id"]) in cascade
            )
            if 10000 * bad // len(pool) > _as_int(feeds[feed_id]["defect_allowance_bp"]):
                grown.add(feed_id)
        if not grown:
            break
        quarantined |= grown

    cascade = {
        (row["domain_id"], row["canonical_producer_id"])
        for row in ledger
        if row["feed_id"] in quarantined and row["reason"] == ""
    }
    for row in ledger:
        if row["reason"] != "":
            continue
        if row["feed_id"] in quarantined:
            row["disposition"] = QUARANTINED
            row["reason"] = R_QUARANTINE
        elif (row["domain_id"], row["canonical_producer_id"]) in cascade:
            row["disposition"] = WITHDRAWN
            row["reason"] = R_CASCADE

    curated = [row for row in ledger if row["disposition"] == CURATED]
    feed_units: dict[str, int] = {}
    for row in curated:
        feed_units[row["feed_id"]] = feed_units.get(row["feed_id"], 0) + row["payload_units"]

    for row in ledger:
        row["unit_charge_micros"] = 0
        row["record_charge_micros"] = 0
    override_records = []
    for row in curated:
        context = charge_context(reg, feeds, feed_units, upheld, row)
        if context["override"] is not None:
            override_records.append(row["record_id"])
        value = compose_charge(context, params)
        row["unit_charge_micros"] = value
        row["record_charge_micros"] = value * row["payload_units"]

    by_domain: dict[str, list] = {}
    for row in curated:
        by_domain.setdefault(row["domain_id"], []).append(row)
    for domain_id in sorted(by_domain):
        members = by_domain[domain_id]
        keep = curtail(
            members,
            _as_int(domains[domain_id]["curated_cap"]),
            sorted({row["feed_id"] for row in members}),
        )
        for row in members:
            if row["record_id"] not in keep:
                row["disposition"] = WITHDRAWN
                row["reason"] = R_CURTAIL
                row["unit_charge_micros"] = 0
                row["record_charge_micros"] = 0

    # rulebook_admission.md A4: only the records that actually carried an upheld
    # agreed rate into the settled output are reported. The list above is built
    # before curtailment, so a curtailed record is withdrawn from it here.
    surviving = {row["record_id"] for row in curated if row["disposition"] == CURATED}
    override_records = [rid for rid in override_records if rid in surviving]

    ledger.sort(key=lambda row: (row["emitted_at"], row["record_id"]))
    running = 0
    for position, row in enumerate(ledger, start=1):
        running += row["record_charge_micros"]
        row["sequence"] = position
        row["cumulative_charge_micros"] = running

    curated = [row for row in ledger if row["disposition"] == CURATED]
    admitted_domains = [
        domain_id
        for domain_id in sorted({row["domain_id"] for row in curated})
        if not _as_bool(domains[domain_id]["provisional"])
    ]
    admitted_channels = sorted(
        {_text(domains[domain_id]["channel_id"]) for domain_id in admitted_domains}
    )

    return {
        "admitted_channels": admitted_channels,
        "admitted_domains": admitted_domains,
        "channels": channels,
        "curated": curated,
        "dismissed_exception_count": dismissed,
        "domains": domains,
        # recover_parameters settles the calibration slice's own register set,
        # which carries no egress policy and is never rendered. egress_layer
        # still reads the keys strictly, so a missing policy on the real path
        # fails loudly rather than settling on an invented constant.
        "egress_policy": {
            _text(row["policy_key"]): _as_int(row["policy_value"])
            for row in reg.get("egress_policy", [])
        },
        "feed_units": feed_units,
        "feeds": feeds,
        "identity_counts": identity_counts,
        "landing_record_count": len(reg["landing_records"]),
        "ledger": ledger,
        "override_records": sorted(set(override_records)),
        "params": params,
        "quality": quality,
        "quarantined_feeds": sorted(quarantined),
        "slots": slots,
        "tombstone_entities": sorted(tombstone_instant),
        "upheld": upheld,
        "upheld_exception_count": len(upheld),
        "window_close": window_close,
        "window_id": window_id,
        "window_open": window_open,
    }


# --------------------------------------------------------------------------
# calibration
# --------------------------------------------------------------------------


def reason_counts(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        if row["disposition"] == WITHDRAWN:
            counts[row["reason"]] = counts.get(row["reason"], 0) + 1
    return counts


def control_figures(state: dict) -> dict:
    ledger = state["ledger"]
    curated = state["curated"]
    charge: dict[str, int] = {}
    for row in curated:
        charge[row["domain_id"]] = charge.get(row["domain_id"], 0) + row["record_charge_micros"]
    return {
        "curated_payload_units": sum(row["payload_units"] for row in curated),
        "curated_record_count": len(curated),
        "domain_settled_charge_micros": charge,
        "quarantined_feed_ids": state["quarantined_feeds"],
        "quarantined_record_count": sum(1 for row in ledger if row["disposition"] == QUARANTINED),
        "settled_charge_micros": sum(row["record_charge_micros"] for row in curated),
        "withdrawal_reason_counts": reason_counts(ledger),
        "withdrawn_record_count": sum(1 for row in ledger if row["disposition"] == WITHDRAWN),
    }


def recover_parameters(block: dict) -> dict:
    """Find the one combination that reproduces every published figure."""
    reg = block["registers"]
    controls = block["controls"]
    probes = controls["adjusted_unit_rate_micros"]
    for reading in TOMBSTONE_READINGS:
        seed = {
            "adjustment_precedence": list(ADJUSTMENTS),
            "backpressure_coefficient_micros": 0,
            "quantisation_step_micros": STEP_CHOICES[0],
            "rounding_mode": "floor",
            "tombstone_reading": reading,
        }
        try:
            base = settle(reg, seed)
        except SystemExit:
            continue
        figures = control_figures(base)
        if figures["curated_record_count"] != controls["curated_record_count"]:
            continue
        if figures["withdrawn_record_count"] != controls["withdrawn_record_count"]:
            continue
        if figures["quarantined_record_count"] != controls["quarantined_record_count"]:
            continue
        contexts = {
            row["record_id"]: charge_context(
                reg, base["feeds"], base["feed_units"], base["upheld"], row
            )
            for row in base["curated"]
        }
        if any(key not in contexts for key in probes):
            continue
        steady = [key for key in sorted(probes) if contexts[key]["excess_bp"] == 0]
        moving = [key for key in sorted(probes) if contexts[key]["excess_bp"] != 0]
        for order in itertools.permutations(ADJUSTMENTS):
            for mode in ROUNDING_MODES:
                for step in STEP_CHOICES:
                    params = {
                        "adjustment_precedence": list(order),
                        "backpressure_coefficient_micros": 0,
                        "quantisation_step_micros": step,
                        "rounding_mode": mode,
                        "tombstone_reading": reading,
                    }
                    if any(
                        compose_charge(contexts[key], params) != probes[key] for key in steady
                    ):
                        continue
                    for coefficient in range(COEFFICIENT_LIMIT + 1):
                        params["backpressure_coefficient_micros"] = coefficient
                        if any(
                            compose_charge(contexts[key], params) != probes[key]
                            for key in moving
                        ):
                            continue
                        candidate = dict(params)
                        figures = control_figures(settle(reg, candidate))
                        if figures["settled_charge_micros"] != controls["settled_charge_micros"]:
                            continue
                        if figures["curated_payload_units"] != controls["curated_payload_units"]:
                            continue
                        if (
                            figures["domain_settled_charge_micros"]
                            != controls["domain_settled_charge_micros"]
                        ):
                            continue
                        if figures["quarantined_feed_ids"] != controls["quarantined_feed_ids"]:
                            continue
                        if (
                            figures["withdrawal_reason_counts"]
                            != controls["withdrawal_reason_counts"]
                        ):
                            continue
                        return candidate
    raise SystemExit("no parameter combination reproduces the published control figures")


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def _dump(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def slugify(value: str) -> str:
    out = []
    filled = False
    for character in value.lower():
        if character.isascii() and character.isalnum():
            out.append(character)
            filled = True
        elif filled and out[-1] != "_":
            out.append("_")
    return "".join(out).strip("_")


def egress_median(sample: list) -> int:
    """rulebook_egress.md E3: an even sample takes its LOWER middle value, never
    the mean of the two and never placed on the settlement grid.

    Derived without branching on parity. For a sample of size n the wanted
    offset is (n - 1) // 2 in both cases: the middle of an odd sample and the
    lower of the two middles of an even one.
    """
    graded = sorted(sample)
    return graded[(len(graded) - 1) // 2]


def egress_layer(state: dict) -> dict:
    """rulebook_egress.md E1 to E7. Reads the curated ledger the settlement
    produced and revises nothing in it.

    Written as an independent derivation of the rulebook rather than as a
    second copy of the grader's arithmetic: the rate comes from divmod so the
    discarded remainder is explicit, groups are keyed by the rendered group key,
    the burst test is a predicate over an explicitly named threshold, the order
    is built by ranking record identifiers rather than row records, and the
    apportionment splits each exact quotient with divmod. Two routes that agree
    are evidence; one route run twice is not.
    """
    policy = state["egress_policy"]
    sigma = policy["egress_sigma"]
    modulus = policy["egress_modulus"]
    octets = policy["payload_unit_octets"]

    # E1: divmod names the remainder the rulebook throws away, so a charge that
    # does not divide evenly across its octets cannot quietly round upward.
    rates = []
    discarded = {}
    for row in state["ledger"]:
        if row["disposition"] != CURATED:
            continue
        units = row["payload_units"]
        if units <= 0:
            continue
        whole, remainder = divmod(row["record_charge_micros"], units * octets)
        discarded[row["record_id"]] = remainder
        rates.append({
            "record_id": row["record_id"],
            "domain_id": row["domain_id"],
            "feed_id": row["feed_id"],
            "record_charge_micros": row["record_charge_micros"],
            "payload_units": units,
            "egress_rate": whole,
        })
    rates.sort(key=lambda r: r["record_id"])

    rate_of = {r["record_id"]: r["egress_rate"] for r in rates}

    def group_key_of(row):
        return row["domain_id"] + ":" + row["feed_id"]

    # E2: group by the rendered group key, so the key the apportionment and the
    # rendering are written under is the same object the burst rule decided on.
    membership = {}
    for row in rates:
        membership.setdefault(group_key_of(row), []).append(row["record_id"])

    bursts = []
    for key in sorted(membership):
        members = membership[key]
        # The rulebook never rejects from a group of fewer than four.
        if len(members) < 4:
            continue
        sample = [rate_of[rid] for rid in members]
        centre = egress_median(sample)
        spread = egress_median([abs(value - centre) for value in sample])
        threshold = centre + sigma * spread
        for rid in members:
            # STRICTLY greater, so a record sitting exactly on the threshold is
            # retained rather than held back.
            if not rate_of[rid] > threshold:
                continue
            source = next(r for r in rates if r["record_id"] == rid)
            bursts.append({
                "record_id": rid,
                "domain_id": source["domain_id"],
                "feed_id": source["feed_id"],
                "egress_rate": rate_of[rid],
                "group_median": centre,
                "group_mad": spread,
                "threshold": threshold,
            })
    bursts.sort(key=lambda r: r["record_id"])

    held_back = {r["record_id"] for r in bursts}
    retained = [r for r in rates if r["record_id"] not in held_back]

    # E5: accumulate rather than fold, so the pool is visibly the sum of the
    # retained rates and of nothing else.
    pool = 0
    for row in retained:
        pool += row["egress_rate"]

    # E4: rank the record identifiers, ascending rate, ties by identifier.
    ranked = sorted((r["record_id"] for r in retained),
                    key=lambda rid: (rate_of[rid], rid))
    order = []
    position = 0
    for rid in ranked:
        position += 1
        order.append({"position": position, "record_id": rid,
                      "egress_rate": rate_of[rid]})

    # E7: multiply and accumulate across the E4 order, reduced once at the end.
    running = 0
    for placed in order:
        running += placed["position"] * placed["egress_rate"]
    digest = running % modulus

    # E6: largest remainder over the summed retained rate of each group.
    group_total = {}
    group_count = {}
    for row in retained:
        key = group_key_of(row)
        group_total[key] = group_total.get(key, 0) + row["egress_rate"]
        group_count[key] = group_count.get(key, 0) + 1

    units_total = 0
    for row in rates:
        units_total += row["payload_units"]

    weight = 0
    for key in group_total:
        weight += group_total[key]

    shares = {}
    if weight > 0:
        exact = {}
        residue = []
        for key in sorted(group_total):
            quotient, remainder = divmod(units_total * group_total[key], weight)
            exact[key] = quotient
            residue.append((-remainder, key))
        distributed = 0
        for key in exact:
            distributed += exact[key]
        residue.sort()
        for _, key in residue[:units_total - distributed]:
            exact[key] += 1
        shares = exact

    return {
        "rates": rates, "bursts": bursts, "retained": retained, "pool": pool,
        "order": order, "digest": digest, "shares": shares,
        "group_total": group_total, "group_count": group_count,
        "curated_payload_units": units_total, "payload_unit_octets": octets,
        "discarded_remainders": discarded,
    }


def render(state: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = state["ledger"]
    curated = state["curated"]
    domains = state["domains"]
    feeds = state["feeds"]
    channels = state["channels"]
    admitted_domains = state["admitted_domains"]
    admitted_channels = state["admitted_channels"]

    settled_total = sum(row["record_charge_micros"] for row in curated)
    quarantined_total = sum(1 for row in ledger if row["disposition"] == QUARANTINED)
    withdrawn_total = sum(1 for row in ledger if row["disposition"] == WITHDRAWN)
    domain_charge = {domain_id: 0 for domain_id in admitted_domains}
    domain_units = {domain_id: 0 for domain_id in admitted_domains}
    for row in curated:
        if row["domain_id"] in domain_charge:
            domain_charge[row["domain_id"]] += row["record_charge_micros"]
            domain_units[row["domain_id"]] += row["payload_units"]

    _dump(
        out_dir / "summary.json",
        {
            "admitted_channel_count": len(admitted_channels),
            "admitted_domain_count": len(admitted_domains),
            "curated_payload_units": sum(row["payload_units"] for row in curated),
            "curated_record_count": len(curated),
            "designated_reserve_feed_ids": sorted(state["slots"]["designated"]),
            "in_window_record_count": len(ledger),
            "landing_record_count": state["landing_record_count"],
            "quarantined_feed_ids": state["quarantined_feeds"],
            "quarantined_record_count": quarantined_total,
            "resolved_parameters": {
                "adjustment_precedence": list(state["params"]["adjustment_precedence"]),
                "backpressure_coefficient_micros": state["params"][
                    "backpressure_coefficient_micros"
                ],
                "quantisation_step_micros": state["params"]["quantisation_step_micros"],
                "rounding_mode": state["params"]["rounding_mode"],
                "tombstone_reading": state["params"]["tombstone_reading"],
            },
            "settled_charge_micros": settled_total,
            "window_close": state["window_close"],
            "window_id": state["window_id"],
            "window_open": state["window_open"],
            "withdrawal_reason_counts": reason_counts(ledger),
            "withdrawn_record_count": withdrawn_total,
        },
    )

    per_domain = []
    for domain_id in admitted_domains:
        members = [row for row in ledger if row["domain_id"] == domain_id]
        kept = [row for row in members if row["disposition"] == CURATED]
        per_domain.append(
            {
                "curated_record_count": len(kept),
                "domain_id": domain_id,
                "quarantined_record_count": sum(
                    1 for row in members if row["disposition"] == QUARANTINED
                ),
                "residual_micros": sum(row["record_charge_micros"] for row in kept)
                - domain_charge[domain_id],
                "settled_charge_micros": domain_charge[domain_id],
                "withdrawn_record_count": sum(
                    1 for row in members if row["disposition"] == WITHDRAWN
                ),
            }
        )

    channel_charge = {}
    for channel_id in admitted_channels:
        channel_charge[channel_id] = sum(
            domain_charge[domain_id]
            for domain_id in admitted_domains
            if _text(domains[domain_id]["channel_id"]) == channel_id
        )

    _dump(
        out_dir / "reconciliation.json",
        {
            "charge": {
                "channel_charge_total_micros": sum(channel_charge.values()),
                "domain_charge_total_micros": sum(domain_charge.values()),
                "residual_micros": settled_total - sum(domain_charge.values()),
                "window_settled_charge_micros": settled_total,
            },
            "identity": {
                "curated_record_count": len(curated),
                "in_window_record_count": len(ledger),
                "quarantined_record_count": quarantined_total,
                "residual_record_count": len(ledger)
                - len(curated)
                - quarantined_total
                - withdrawn_total,
                "withdrawn_record_count": withdrawn_total,
            },
            "per_domain": per_domain,
            "units": {
                "curated_payload_units": sum(row["payload_units"] for row in curated),
                "domain_curated_units_total": sum(domain_units.values()),
                "residual_units": sum(row["payload_units"] for row in curated)
                - sum(domain_units.values()),
            },
            "window_id": state["window_id"],
        },
    )

    identity_rows: dict[tuple, int] = {}
    for (ref, canonical, status), count in state["identity_counts"].items():
        reported = "" if status in ("unknown", "cyclic") else canonical
        key = (ref, reported, status)
        identity_rows[key] = identity_rows.get(key, 0) + count

    _dump(
        out_dir / "ingest_audit.json",
        {
            "identity_resolutions": [
                {
                    "canonical_producer_id": canonical,
                    "producer_ref": ref,
                    "record_count": count,
                    "status": status,
                }
                for (ref, canonical, status), count in sorted(identity_rows.items())
            ],
            "ledger": [
                {
                    "canonical_producer_id": row["canonical_producer_id"],
                    "cumulative_charge_micros": row["cumulative_charge_micros"],
                    "disposition": row["disposition"],
                    "domain_id": row["domain_id"],
                    "emitted_at": row["emitted_at"],
                    "feed_id": row["feed_id"],
                    "governing_card_id": row["governing_card_id"],
                    "payload_units": row["payload_units"],
                    "reason": row["reason"],
                    "record_charge_micros": row["record_charge_micros"],
                    "record_id": row["record_id"],
                    "sequence": row["sequence"],
                    "unit_charge_micros": row["unit_charge_micros"],
                }
                for row in ledger
            ],
            "override_record_ids": state["override_records"],
            "tombstone_entity_ids": state["tombstone_entities"],
            "window_id": state["window_id"],
        },
    )

    quality = dict(state["quality"])
    quality.update(
        {
            "dismissed_exception_count": state["dismissed_exception_count"],
            "domains_at_quarantine_floor": [
                domain_id
                for domain_id in admitted_domains
                if domain_units[domain_id] <= _as_int(domains[domain_id]["quarantine_floor"])
            ],
            "feeds_over_nominal_throughput": sorted(
                feed_id
                for feed_id, units in state["feed_units"].items()
                if units > _as_int(feeds[feed_id]["nominal_throughput"])
            ),
            "upheld_exception_count": state["upheld_exception_count"],
            "window_id": state["window_id"],
        }
    )
    _dump(out_dir / "data_quality.json", quality)

    _dump(
        out_dir / "slot_designation.json",
        {
            "channels": state["slots"]["channels"],
            "designated_band_high_bp": state["slots"]["designated_band_high_bp"],
            "designated_band_low_bp": state["slots"]["designated_band_low_bp"],
            "designated_nominal_throughput": state["slots"]["designated_nominal_throughput"],
            "window_id": state["window_id"],
            "window_nominal_throughput": state["slots"]["window_nominal_throughput"],
        },
    )

    for domain_id in admitted_domains:
        members = [row for row in ledger if row["domain_id"] == domain_id]
        kept = [row for row in members if row["disposition"] == CURATED]
        _dump(
            out_dir / ("domain_" + slugify(domain_id) + ".json"),
            {
                "channel_id": _text(domains[domain_id]["channel_id"]),
                "curated_cap": _as_int(domains[domain_id]["curated_cap"]),
                "curated_payload_units": domain_units[domain_id],
                "curated_record_count": len(kept),
                "curated_record_ids": sorted(row["record_id"] for row in kept),
                "curtailed_record_ids": sorted(
                    row["record_id"] for row in members if row["reason"] == R_CURTAIL
                ),
                "domain_id": domain_id,
                "feed_ids": sorted(
                    feed_id
                    for feed_id, feed_row in feeds.items()
                    if _text(feed_row["domain_id"]) == domain_id
                ),
                "producer_ids": sorted({row["canonical_producer_id"] for row in kept}),
                "quarantine_floor": _as_int(domains[domain_id]["quarantine_floor"]),
                "quarantined_feed_ids": sorted(
                    {row["feed_id"] for row in members if row["disposition"] == QUARANTINED}
                ),
                "settled_charge_micros": domain_charge[domain_id],
                "withdrawal_reason_counts": reason_counts(members),
            },
        )

    for channel_id in admitted_channels:
        members = sorted(
            domain_id
            for domain_id in domains
            if _text(domains[domain_id]["channel_id"]) == channel_id
        )
        admitted_members = [domain_id for domain_id in members if domain_id in admitted_domains]
        rows = [row for row in curated if row["domain_id"] in admitted_members]
        _dump(
            out_dir / ("channel_" + slugify(channel_id) + ".json"),
            {
                "admitted_domain_ids": admitted_members,
                "channel_id": channel_id,
                "curated_payload_units": sum(row["payload_units"] for row in rows),
                "curated_record_count": len(rows),
                "designated_reserve_feed_ids": sorted(
                    feed_id
                    for feed_id in state["slots"]["designated"]
                    if _text(domains[_text(feeds[feed_id]["domain_id"])]["channel_id"])
                    == channel_id
                ),
                "domain_charge_micros": {
                    domain_id: domain_charge[domain_id] for domain_id in admitted_members
                },
                "member_domain_ids": members,
                "settled_charge_micros": sum(row["record_charge_micros"] for row in rows),
                "slot_ceiling": _as_int(channels[channel_id]["slot_ceiling"]),
            },
        )

    egress = egress_layer(state)

    _dump(
        out_dir / "egress_summary.json",
        {
            "burst_record_count": len(egress["bursts"]),
            "egress_digest": egress["digest"],
            "egress_pool_micros": egress["pool"],
            "payload_unit_octets": egress["payload_unit_octets"],
            "retained_record_count": len(egress["retained"]),
            "window_id": state["window_id"],
        },
    )

    _dump(
        out_dir / "egress_rates.json",
        {"rates": egress["rates"], "window_id": state["window_id"]},
    )

    _dump(
        out_dir / "egress_bursts.json",
        {"bursts": egress["bursts"], "window_id": state["window_id"]},
    )

    _dump(
        out_dir / "egress_order.json",
        {"order": egress["order"], "window_id": state["window_id"]},
    )

    _dump(
        out_dir / "egress_apportionment.json",
        {
            "curated_payload_units": egress["curated_payload_units"],
            "shares": dict(sorted(egress["shares"].items())),
            "window_id": state["window_id"],
        },
    )

    ladder = ["group_key,retained_count,group_rate_total,payload_share"]
    for key in sorted(egress["group_total"]):
        ladder.append(
            "%s,%d,%d,%d"
            % (
                key,
                egress["group_count"][key],
                egress["group_total"][key],
                egress["shares"][key],
            )
        )
    (out_dir / "egress_ladder.csv").write_text(
        "\n".join(ladder) + "\n", encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: settle_ingest.py <data-dir> <out-dir>\n")
        return 2
    data_dir = Path(argv[1])
    out_dir = Path(argv[2])
    registers = load_registers(data_dir)
    params = recover_parameters(load_calibration(data_dir))
    render(settle(registers, params), out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
