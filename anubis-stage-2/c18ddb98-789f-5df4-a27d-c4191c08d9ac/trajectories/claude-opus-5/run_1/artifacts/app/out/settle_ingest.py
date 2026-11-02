#!/usr/bin/env python3
"""Settle one change-data-capture ingest window and its egress layer.

Usage: settle_ingest.py <register_dir> <output_dir>

Every platform property that the reference set leaves unwritten is recovered at
run time from the calibration material shipped inside the register directory.
"""

from __future__ import annotations

import csv
import itertools
import json
import os
import sys
from datetime import datetime

# --------------------------------------------------------------------------
# register loading
# --------------------------------------------------------------------------

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
JSON_REGISTERS = ("exceptions",)


def load_registers(path):
    regs = {}
    for name in CSV_REGISTERS:
        fp = os.path.join(path, name + ".csv")
        if os.path.exists(fp):
            with open(fp, newline="", encoding="utf-8") as fh:
                regs[name] = [dict(row) for row in csv.DictReader(fh)]
        else:
            regs[name] = []
    for name in JSON_REGISTERS:
        fp = os.path.join(path, name + ".json")
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as fh:
                regs[name] = json.load(fh)
        else:
            regs[name] = []
    return regs


def load_calibration(path):
    fp = os.path.join(path, "calibration_controls.json")
    if not os.path.exists(fp):
        return None
    with open(fp, encoding="utf-8") as fh:
        blob = json.load(fh)
    regs = {}
    for name in CSV_REGISTERS + JSON_REGISTERS:
        regs[name] = blob.get("registers", {}).get(name, []) or []
    return regs, blob["controls"]


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def ts(text):
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def as_int(text):
    return int(str(text).strip())


def as_bool(text):
    return str(text).strip().lower() == "true"


ROUNDING_MODES = ("ceil", "floor", "half_down", "half_even", "half_up")
QUANT_STEPS = (5, 10, 20, 25, 40, 50, 80, 100, 125)
ADJUSTMENTS = ("abatement", "override", "rebate", "surcharge")
TOMBSTONE_READINGS = ("retroactive", "forward")


def place(num, den, step, mode):
    """Place the exact rational num/den onto the grid of `step` micros."""
    if num <= 0:
        return 0
    if den == 1 and num % step == 0:
        return num
    unit = step * den
    q, rem = divmod(num, unit)
    if rem == 0:
        return q * step
    if mode == "floor":
        return q * step
    if mode == "ceil":
        return (q + 1) * step
    twice = 2 * rem
    if twice > unit:
        return (q + 1) * step
    if twice < unit:
        return q * step
    if mode == "half_up":
        return (q + 1) * step
    if mode == "half_down":
        return q * step
    # half_even: pick the grid point that is an even multiple of the spacing
    return q * step if q % 2 == 0 else (q + 1) * step


# --------------------------------------------------------------------------
# parsed working set
# --------------------------------------------------------------------------


class WorkingSet:
    def __init__(self, regs):
        cal = regs["window_calendar"][0]
        self.window_id = cal["window_id"]
        self.window_open_text = cal["window_open"]
        self.window_close_text = cal["window_close"]
        self.window_open = ts(cal["window_open"])
        self.window_close = ts(cal["window_close"])

        self.policy = {r["policy_key"]: r["policy_value"] for r in regs["window_policy"]}
        self.egress_policy = {
            r["policy_key"]: r["policy_value"] for r in regs["egress_policy"]
        }

        self.channels = {}
        for r in regs["channels"]:
            self.channels[r["channel_id"]] = {
                "channel_id": r["channel_id"],
                "slot_ceiling": as_int(r["slot_ceiling"]),
            }
        self.domains = {}
        for r in regs["domains"]:
            self.domains[r["domain_id"]] = {
                "domain_id": r["domain_id"],
                "channel_id": r["channel_id"],
                "quarantine_floor": as_int(r["quarantine_floor"]),
                "curated_cap": as_int(r["curated_cap"]),
                "provisional": as_bool(r["provisional"]),
            }
        self.feeds = {}
        for r in regs["feeds"]:
            self.feeds[r["feed_id"]] = {
                "feed_id": r["feed_id"],
                "domain_id": r["domain_id"],
                "feed_class": r["feed_class"],
                "nominal_throughput": as_int(r["nominal_throughput"]),
                "defect_allowance_bp": as_int(r["defect_allowance_bp"]),
                "floor_rate_micros": as_int(r["floor_rate_micros"]),
                "suspended": as_bool(r["suspended"]),
            }
        self.producers = {r["producer_id"] for r in regs["producers"]}

        self.events = []
        for r in regs["producer_events"]:
            self.events.append(
                {
                    "event_id": r["event_id"],
                    "effective_at": ts(r["effective_at"]),
                    "event_type": r["event_type"],
                    "subject_ref": r["subject_ref"],
                    "target_ref": (r.get("target_ref") or "").strip(),
                }
            )
        self.cards = []
        for r in regs["rate_cards"]:
            self.cards.append(
                {
                    "card_id": r["card_id"],
                    "effective_from": ts(r["effective_from"]),
                    "superseded_at": ts(r.get("superseded_at")),
                    "rate": {
                        "bulk": as_int(r["rate_bulk"]),
                        "stream": as_int(r["rate_stream"]),
                        "micro": as_int(r["rate_micro"]),
                    },
                    "mult": {
                        "full": as_int(r["mult_full"]),
                        "delta": as_int(r["mult_delta"]),
                        "snapshot": as_int(r["mult_snapshot"]),
                    },
                }
            )
        self.incidents = []
        for r in regs["feed_incidents"]:
            self.incidents.append(
                {
                    "incident_id": r["incident_id"],
                    "feed_id": r["feed_id"],
                    "severity": as_int(r["severity"]),
                    "opened_at": ts(r["opened_at"]),
                    "closed_at": ts(r.get("closed_at")),
                    "abatement_micros": as_int(r["abatement_micros"]),
                }
            )
        self.records = []
        for r in regs["landing_records"]:
            self.records.append(
                {
                    "record_id": r["record_id"],
                    "producer_ref": r["producer_ref"],
                    "feed_id": r["feed_id"],
                    "emitted_at": r["emitted_at"],
                    "emitted": ts(r["emitted_at"]),
                    "payload_units": as_int(r["payload_units"]),
                    "tier_class": r["tier_class"],
                    "form_class": r["form_class"],
                    "op": r["op"],
                }
            )
        self.exceptions = list(regs["exceptions"])
        self.upheld = {}
        self.upheld_count = 0
        self.dismissed_count = 0
        for e in self.exceptions:
            if e["status"] == "upheld":
                self.upheld_count += 1
                self.upheld[e["record_id"]] = int(e["agreed_unit_rate_micros"])
            elif e["status"] == "dismissed":
                self.dismissed_count += 1


# --------------------------------------------------------------------------
# identity resolution
# --------------------------------------------------------------------------


def build_identity(ws):
    """Return resolve(producer_ref, instant) -> (canonical_id, status)."""
    maps = {}
    retires = {}
    for ev in ws.events:
        if ev["event_type"] in ("rename", "merge"):
            maps.setdefault(ev["subject_ref"], []).append(ev)
        elif ev["event_type"] == "retire":
            retires.setdefault(ev["subject_ref"], []).append(ev)

    def in_force_target(ref, instant):
        best = None
        for ev in maps.get(ref, ()):
            if ev["effective_at"] <= instant:
                key = (ev["effective_at"], ev["event_id"])
                if best is None or key > best[0]:
                    best = (key, ev["target_ref"])
        return None if best is None else best[1]

    def retired(ref, instant):
        for ev in retires.get(ref, ()):
            if ev["effective_at"] <= instant:
                return True
        return False

    cache = {}

    def resolve(ref, instant):
        key = (ref, instant)
        hit = cache.get(key)
        if hit is not None:
            return hit
        seen = {ref}
        cur = ref
        status = "resolved"
        while True:
            nxt = in_force_target(cur, instant)
            if nxt is None:
                break
            if nxt in seen:
                status = "cyclic"
                break
            seen.add(nxt)
            cur = nxt
        if status == "cyclic":
            out = ("", "cyclic")
        elif retired(cur, instant):
            out = (cur, "retired")
        elif cur not in ws.producers:
            out = ("", "unknown")
        else:
            out = (cur, "resolved")
        cache[key] = out
        return out

    return resolve


# --------------------------------------------------------------------------
# cards and incidents
# --------------------------------------------------------------------------


def governing_card(ws, instant):
    best = None
    for card in ws.cards:
        if card["effective_from"] <= instant and (
            card["superseded_at"] is None or instant < card["superseded_at"]
        ):
            key = (card["effective_from"], card["card_id"])
            if best is None or key > best[0]:
                best = (key, card)
    return None if best is None else best[1]


def governing_incident(ws, feed_id, instant):
    best = None
    for inc in ws.incidents:
        if inc["feed_id"] != feed_id:
            continue
        if inc["opened_at"] <= instant and (
            inc["closed_at"] is None or instant < inc["closed_at"]
        ):
            key = (inc["severity"], inc["incident_id"])
            if best is None or key > best[0]:
                best = (key, inc)
    return None if best is None else best[1]


def feed_has_incident_at(ws, feed_id, instant):
    return governing_incident(ws, feed_id, instant) is not None


# --------------------------------------------------------------------------
# reserve slot designation
# --------------------------------------------------------------------------


def designate_slots(ws):
    participating = []
    for cid in sorted(ws.channels):
        members = [d for d in ws.domains.values() if d["channel_id"] == cid]
        if any(not d["provisional"] for d in members):
            participating.append(cid)

    window_nominal = sum(
        f["nominal_throughput"] for f in ws.feeds.values() if not f["suspended"]
    )
    low = as_int(ws.policy["designated_band_low_bp"])
    high = as_int(ws.policy["designated_band_high_bp"])

    per_channel = {}
    candidates = {}
    for cid in participating:
        cands = []
        for fid in sorted(ws.feeds):
            feed = ws.feeds[fid]
            dom = ws.domains.get(feed["domain_id"])
            if dom is None or dom["channel_id"] != cid:
                continue
            if feed["suspended"] or dom["provisional"]:
                continue
            if feed_has_incident_at(ws, fid, ws.window_close):
                continue
            cands.append(fid)
        candidates[cid] = cands
        ceiling = ws.channels[cid]["slot_ceiling"]
        options = []
        if 0 < ceiling <= len(cands):
            eligible_by_domain = {}
            for fid in cands:
                eligible_by_domain.setdefault(ws.feeds[fid]["domain_id"], set()).add(fid)
            for combo in itertools.combinations(cands, ceiling):
                classes = [ws.feeds[f]["feed_class"] for f in combo]
                if len(set(classes)) != len(classes):
                    continue
                if "primary" not in classes:
                    continue
                chosen = set(combo)
                bad = False
                for dom_id, elig in eligible_by_domain.items():
                    if elig and elig <= chosen:
                        bad = True
                        break
                if bad:
                    continue
                options.append(tuple(sorted(combo)))
        elif ceiling == 0:
            options.append(())
        per_channel[cid] = options or [()]

    solutions = []
    keys = participating
    for combo in itertools.product(*(per_channel[c] for c in keys)):
        total = 0
        for feeds in combo:
            total += sum(ws.feeds[f]["nominal_throughput"] for f in feeds)
        share = (total * 10000) // window_nominal if window_nominal else 0
        if low <= share <= high:
            solutions.append((combo, total, share))

    if solutions:
        solutions.sort(key=lambda s: sorted(f for feeds in s[0] for f in feeds))
        combo, total, share = solutions[0]
    else:
        combo = tuple(() for _ in keys)
        total = 0
    designation = {keys[i]: list(combo[i]) for i in range(len(keys))}
    return {
        "participating": keys,
        "candidates": candidates,
        "designation": designation,
        "window_nominal": window_nominal,
        "designated_nominal": total,
        "band_low": low,
        "band_high": high,
    }


# --------------------------------------------------------------------------
# structural settlement (independent of the rate parameters)
# --------------------------------------------------------------------------

REASON_PROVISIONAL = "withdrawn_provisional_domain"
REASON_RETIRED = "withdrawn_retired_producer"
REASON_UNKNOWN = "withdrawn_unknown_producer"
REASON_CYCLIC = "withdrawn_cyclic_identity"
REASON_NO_CARD = "withdrawn_no_governing_card"
REASON_TOMBSTONE = "withdrawn_by_tombstone"
REASON_RESERVE = "withdrawn_by_reserve_designation"
REASON_CASCADE = "withdrawn_by_quarantine_cascade"
REASON_CURTAIL = "withdrawn_by_curtailment"
REASON_QUARANTINE = "quarantined_defect_rate"


def structural_stage(ws, tombstone_reading):
    resolve = build_identity(ws)
    slots = designate_slots(ws)
    designated = set()
    for feeds in slots["designation"].values():
        designated.update(feeds)

    rows = {}
    out_of_window = 0
    suspended_records = 0
    participating = []

    for rec in ws.records:
        in_window = ws.window_open <= rec["emitted"] < ws.window_close
        if not in_window:
            out_of_window += 1
            continue
        feed = ws.feeds[rec["feed_id"]]
        if feed["suspended"]:
            suspended_records += 1
            continue
        canon, status = resolve(rec["producer_ref"], rec["emitted"])
        card = governing_card(ws, rec["emitted"])
        row = {
            "record_id": rec["record_id"],
            "rec": rec,
            "feed_id": rec["feed_id"],
            "domain_id": feed["domain_id"],
            "canonical_producer_id": canon,
            "identity_status": status,
            "governing_card": card,
            "payload_units": rec["payload_units"],
            "disposition": None,
            "reason": "",
        }
        rows[rec["record_id"]] = row
        participating.append(row)

    quality = {
        "out_of_window": out_of_window,
        "suspended": suspended_records,
        "provisional": 0,
        "retired": 0,
        "unknown": 0,
        "cyclic": 0,
        "no_card": 0,
    }
    for row in participating:
        if ws.domains[row["domain_id"]]["provisional"]:
            quality["provisional"] += 1
        if row["identity_status"] == "retired":
            quality["retired"] += 1
        elif row["identity_status"] == "unknown":
            quality["unknown"] += 1
        elif row["identity_status"] == "cyclic":
            quality["cyclic"] += 1
        if row["governing_card"] is None:
            quality["no_card"] += 1

    def withdraw(row, reason):
        row["disposition"] = "withdrawn"
        row["reason"] = reason

    for row in participating:
        if ws.domains[row["domain_id"]]["provisional"]:
            withdraw(row, REASON_PROVISIONAL)
        elif row["identity_status"] == "retired":
            withdraw(row, REASON_RETIRED)
        elif row["identity_status"] == "unknown":
            withdraw(row, REASON_UNKNOWN)
        elif row["identity_status"] == "cyclic":
            withdraw(row, REASON_CYCLIC)
        elif row["governing_card"] is None:
            withdraw(row, REASON_NO_CARD)

    # R1 tombstones
    tomb_instants = {}
    for row in participating:
        if row["disposition"] is not None:
            continue
        if row["rec"]["op"] == "tombstone":
            ent = row["canonical_producer_id"]
            inst = row["rec"]["emitted"]
            if ent not in tomb_instants or inst < tomb_instants[ent]:
                tomb_instants[ent] = inst
    tombstone_entities = sorted(tomb_instants)
    for row in participating:
        if row["disposition"] is not None:
            continue
        ent = row["canonical_producer_id"]
        if ent not in tomb_instants:
            continue
        if tombstone_reading == "forward" and row["rec"]["emitted"] < tomb_instants[ent]:
            continue
        withdraw(row, REASON_TOMBSTONE)
    tombstoned = {
        r["record_id"] for r in participating if r["reason"] == REASON_TOMBSTONE
    }

    # S1 reserve designation
    for row in participating:
        if row["disposition"] is None and row["feed_id"] in designated:
            withdraw(row, REASON_RESERVE)

    # Q1 pools
    pools = {}
    for row in participating:
        if row["feed_id"] in designated:
            continue
        if row["disposition"] is None or row["record_id"] in tombstoned:
            pools.setdefault(row["feed_id"], []).append(row)

    # Q5 confluent quarantine / taint state
    quarantined = set()
    tainted = set()
    while True:
        new_q = set()
        for fid, pool in pools.items():
            allowance = ws.feeds[fid]["defect_allowance_bp"]
            dom = ws.feeds[fid]["domain_id"]
            defective = 0
            for row in pool:
                if row["record_id"] in tombstoned or (
                    dom,
                    row["canonical_producer_id"],
                ) in tainted:
                    defective += 1
            rate_bp = (defective * 10000) // len(pool)
            if rate_bp > allowance:
                new_q.add(fid)
        new_t = set()
        for fid in new_q:
            dom = ws.feeds[fid]["domain_id"]
            for row in pools[fid]:
                if row["record_id"] not in tombstoned:
                    new_t.add((dom, row["canonical_producer_id"]))
        if new_q == quarantined and new_t == tainted:
            break
        quarantined = new_q
        tainted = new_t

    for row in participating:
        if row["disposition"] is None and row["feed_id"] in quarantined:
            row["disposition"] = "quarantined"
            row["reason"] = REASON_QUARANTINE
    for row in participating:
        if row["disposition"] is None and (
            row["domain_id"],
            row["canonical_producer_id"],
        ) in tainted:
            withdraw(row, REASON_CASCADE)

    eligible = [r for r in participating if r["disposition"] is None]

    feed_load = {}
    for row in eligible:
        feed_load[row["feed_id"]] = feed_load.get(row["feed_id"], 0) + row["payload_units"]

    overage_bp = {}
    for fid, load in feed_load.items():
        nominal = ws.feeds[fid]["nominal_throughput"]
        if load > nominal and nominal > 0:
            overage_bp[fid] = ((load - nominal) * 10000) // nominal

    return {
        "rows": rows,
        "participating": participating,
        "eligible": eligible,
        "quality": quality,
        "slots": slots,
        "designated": designated,
        "quarantined": quarantined,
        "tainted": tainted,
        "tombstone_entities": tombstone_entities,
        "feed_load": feed_load,
        "overage_bp": overage_bp,
    }


# --------------------------------------------------------------------------
# rates, curtailment and totals
# --------------------------------------------------------------------------


def unit_rate_for(ws, row, params, overage_bp):
    step = params["quantisation_step_micros"]
    mode = params["rounding_mode"]
    card = row["governing_card"]
    rate = place(
        card["rate"][row["rec"]["tier_class"]] * card["mult"][row["rec"]["form_class"]],
        10000,
        step,
        mode,
    )
    feed = ws.feeds[row["feed_id"]]
    inc = governing_incident(ws, row["feed_id"], row["rec"]["emitted"])
    agreed = ws.upheld.get(row["record_id"])
    over = overage_bp.get(row["feed_id"], 0)
    coef = params["backpressure_coefficient_micros"]

    for adj in params["adjustment_precedence"]:
        if adj == "abatement":
            if inc is not None:
                value = rate - inc["abatement_micros"]
                rate = place(value if value > 0 else 0, 1, step, mode)
        elif adj == "rebate":
            rate = place(rate * (10000 - feed["defect_allowance_bp"]), 10000, step, mode)
        elif adj == "override":
            if agreed is not None:
                rate = place(agreed, 1, step, mode)
        elif adj == "surcharge":
            if over > 0:
                rate = place(rate + (coef * over) // 10000, 1, step, mode)
    if rate < feed["floor_rate_micros"]:
        rate = feed["floor_rate_micros"]
    return rate


def curtail_domain(rows, cap):
    """Pick the retained subset: max charge, then max count, then least ids."""
    total_units = sum(r["payload_units"] for r in rows)
    if total_units <= cap:
        return rows, []
    rows = sorted(rows, key=lambda r: r["record_id"])
    feeds = sorted({r["feed_id"] for r in rows})
    bit = {f: 1 << i for i, f in enumerate(feeds)}
    full = (1 << len(feeds)) - 1

    # state -> (charge, count, ids tuple)
    states = {(0, 0): (0, 0, ())}
    for row in rows:
        units = row["payload_units"]
        charge = row["charge"]
        fb = bit[row["feed_id"]]
        rid = row["record_id"]
        nxt = dict(states)
        for (used, mask), val in states.items():
            nu = used + units
            if nu > cap:
                continue
            key = (nu, mask | fb)
            cand = (val[0] + charge, val[1] + 1, val[2] + (rid,))
            cur = nxt.get(key)
            if cur is None or _better(cand, cur):
                nxt[key] = cand
        states = nxt

    best = None
    for (used, mask), val in states.items():
        if mask != full:
            continue
        if best is None or _better(val, best):
            best = val
    if best is None:
        best = (0, 0, ())
    keep = set(best[2])
    retained = [r for r in rows if r["record_id"] in keep]
    dropped = [r for r in rows if r["record_id"] not in keep]
    return retained, dropped


def _better(a, b):
    if a[0] != b[0]:
        return a[0] > b[0]
    if a[1] != b[1]:
        return a[1] > b[1]
    return a[2] < b[2]


def rate_stage(ws, struct, params):
    overage = struct["overage_bp"]
    candidates = struct["eligible"]
    for row in candidates:
        row["unit_rate"] = unit_rate_for(ws, row, params, overage)
        row["charge"] = row["unit_rate"] * row["payload_units"]

    by_domain = {}
    for row in candidates:
        by_domain.setdefault(row["domain_id"], []).append(row)

    curated = []
    curtailed_by_domain = {}
    for dom_id in sorted(by_domain):
        cap = ws.domains[dom_id]["curated_cap"]
        keep, drop = curtail_domain(by_domain[dom_id], cap)
        curated.extend(keep)
        curtailed_by_domain[dom_id] = [r["record_id"] for r in drop]
        for row in drop:
            row["disposition"] = "withdrawn"
            row["reason"] = REASON_CURTAIL
            row["unit_rate"] = 0
            row["charge"] = 0
    for row in curated:
        row["disposition"] = "curated"
        row["reason"] = ""
    for row in struct["participating"]:
        if row["disposition"] != "curated":
            row["unit_rate"] = 0
            row["charge"] = 0
    return {"curated": curated, "curtailed": curtailed_by_domain}


def reset_dispositions(struct):
    for row in struct["participating"]:
        row.pop("unit_rate", None)
        row.pop("charge", None)
    for row in struct["eligible"]:
        row["disposition"] = None
        row["reason"] = ""


# --------------------------------------------------------------------------
# parameter recovery from the calibration slice
# --------------------------------------------------------------------------


def recover_parameters(path):
    loaded = load_calibration(path)
    if loaded is None:
        raise SystemExit("calibration material missing from register directory")
    regs, controls = loaded
    ws = WorkingSet(regs)

    structs = {}
    for reading in TOMBSTONE_READINGS:
        struct = structural_stage(ws, reading)
        if not _structural_matches(ws, struct, controls):
            continue
        structs[reading] = struct

    control_rates = controls.get("adjusted_unit_rate_micros", {})
    coef_range = range(0, 601)
    found = []

    for reading, struct in structs.items():
        overage = struct["overage_bp"]
        rate_rows = {r["record_id"]: r for r in struct["eligible"]}
        probes = []
        for rid in sorted(control_rates):
            row = rate_rows.get(rid)
            if row is None:
                continue
            surcharged = overage.get(row["feed_id"], 0) > 0
            probes.append((surcharged, rid, row, control_rates[rid]))
        probes.sort(key=lambda p: (p[0], p[1]))

        for precedence in itertools.permutations(ADJUSTMENTS):
            for step in QUANT_STEPS:
                for mode in ROUNDING_MODES:
                    coefs = list(coef_range)
                    params = {
                        "adjustment_precedence": list(precedence),
                        "quantisation_step_micros": step,
                        "rounding_mode": mode,
                        "tombstone_reading": reading,
                        "backpressure_coefficient_micros": 0,
                    }
                    for surcharged, _rid, row, target in probes:
                        if not surcharged:
                            params["backpressure_coefficient_micros"] = coefs[0]
                            if unit_rate_for(ws, row, params, overage) != target:
                                coefs = []
                                break
                        else:
                            kept = []
                            for c in coefs:
                                params["backpressure_coefficient_micros"] = c
                                if unit_rate_for(ws, row, params, overage) == target:
                                    kept.append(c)
                            coefs = kept
                        if not coefs:
                            break
                    for c in coefs:
                        cand = {
                            "adjustment_precedence": list(precedence),
                            "backpressure_coefficient_micros": c,
                            "quantisation_step_micros": step,
                            "rounding_mode": mode,
                            "tombstone_reading": reading,
                        }
                        if _full_matches(ws, struct, cand, controls):
                            found.append(cand)

    if not found:
        raise SystemExit("no reading of the platform reproduces the calibration slice")
    canonical = json.dumps(found[0], sort_keys=True)
    for cand in found[1:]:
        if json.dumps(cand, sort_keys=True) != canonical:
            raise SystemExit("calibration slice does not pin the platform down")
    return found[0]


def _structural_matches(ws, struct, controls):
    rows = struct["participating"]
    quarantined = [r for r in rows if r["disposition"] == "quarantined"]
    if "quarantined_record_count" in controls:
        if len(quarantined) != controls["quarantined_record_count"]:
            return False
    if "quarantined_feed_ids" in controls:
        if sorted(struct["quarantined"]) != sorted(controls["quarantined_feed_ids"]):
            return False
    return True


def _full_matches(ws, struct, params, controls):
    reset_dispositions(struct)
    stage = rate_stage(ws, struct, params)
    rows = struct["participating"]
    curated = stage["curated"]
    withdrawn = [r for r in rows if r["disposition"] == "withdrawn"]
    quarantined = [r for r in rows if r["disposition"] == "quarantined"]

    def check(key, value):
        return key not in controls or controls[key] == value

    if not check("curated_record_count", len(curated)):
        return False
    if not check("withdrawn_record_count", len(withdrawn)):
        return False
    if not check("quarantined_record_count", len(quarantined)):
        return False
    units = sum(r["payload_units"] for r in curated)
    if not check("curated_payload_units", units):
        return False
    charge = sum(r["charge"] for r in curated)
    if not check("settled_charge_micros", charge):
        return False
    if "withdrawal_reason_counts" in controls:
        counts = {}
        for r in withdrawn:
            counts[r["reason"]] = counts.get(r["reason"], 0) + 1
        if counts != controls["withdrawal_reason_counts"]:
            return False
    if "quarantined_feed_ids" in controls:
        if sorted(struct["quarantined"]) != sorted(controls["quarantined_feed_ids"]):
            return False
    if "domain_settled_charge_micros" in controls:
        per = {}
        for r in curated:
            per[r["domain_id"]] = per.get(r["domain_id"], 0) + r["charge"]
        if per != controls["domain_settled_charge_micros"]:
            return False
    if "adjusted_unit_rate_micros" in controls:
        index = {r["record_id"]: r for r in curated}
        for rid, target in controls["adjusted_unit_rate_micros"].items():
            row = index.get(rid)
            if row is None or row["unit_rate"] != target:
                return False
    return True


# --------------------------------------------------------------------------
# artifact writing
# --------------------------------------------------------------------------


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, indent=2, sort_keys=True))
        fh.write("\n")


def slug(identifier):
    out = []
    run = False
    for ch in identifier.lower():
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            out.append(ch)
            run = False
        elif not run:
            out.append("_")
            run = True
    return "".join(out)


# --------------------------------------------------------------------------
# egress layer
# --------------------------------------------------------------------------


def lower_median(values):
    ordered = sorted(values)
    n = len(ordered)
    if n % 2:
        return ordered[n // 2]
    return ordered[n // 2 - 1]


def run_egress(ws, curated, out_dir):
    sigma = as_int(ws.egress_policy["egress_sigma"])
    modulus = as_int(ws.egress_policy["egress_modulus"])
    octets = as_int(ws.egress_policy["payload_unit_octets"])

    rates = []
    for row in sorted(curated, key=lambda r: r["record_id"]):
        denom = row["payload_units"] * octets
        rate = row["charge"] // denom if denom else 0
        rates.append(
            {
                "record_id": row["record_id"],
                "feed_id": row["feed_id"],
                "domain_id": row["domain_id"],
                "payload_units": row["payload_units"],
                "record_charge_micros": row["charge"],
                "egress_rate": rate,
            }
        )

    groups = {}
    for r in rates:
        groups.setdefault(r["domain_id"] + ":" + r["feed_id"], []).append(r)

    bursts = []
    retained = []
    for key in sorted(groups):
        members = groups[key]
        if len(members) < 4:
            retained.extend(members)
            continue
        values = [m["egress_rate"] for m in members]
        med = lower_median(values)
        mad = lower_median([abs(v - med) for v in values])
        threshold = med + sigma * mad
        for m in members:
            if m["egress_rate"] > threshold:
                bursts.append(
                    {
                        "record_id": m["record_id"],
                        "feed_id": m["feed_id"],
                        "domain_id": m["domain_id"],
                        "egress_rate": m["egress_rate"],
                        "group_median": med,
                        "group_mad": mad,
                        "threshold": threshold,
                    }
                )
            else:
                retained.append(m)

    retained_sorted = sorted(retained, key=lambda r: (r["egress_rate"], r["record_id"]))
    pool = sum(r["egress_rate"] for r in retained_sorted)
    digest = sum((i + 1) * r["egress_rate"] for i, r in enumerate(retained_sorted))
    digest %= modulus

    retained_by_group = {}
    for r in retained:
        retained_by_group.setdefault(r["domain_id"] + ":" + r["feed_id"], []).append(r)

    units = sum(r["payload_units"] for r in curated)
    keys = sorted(retained_by_group)
    weights = {k: sum(x["egress_rate"] for x in retained_by_group[k]) for k in keys}
    total_weight = sum(weights.values())
    shares = {k: 0 for k in keys}
    if keys:
        if total_weight > 0:
            remainders = []
            assigned = 0
            for k in keys:
                base, rem = divmod(units * weights[k], total_weight)
                shares[k] = base
                assigned += base
                remainders.append((-rem, k))
            remainders.sort()
            left = units - assigned
            for i in range(left):
                shares[remainders[i % len(remainders)][1]] += 1
        else:
            for i in range(units):
                shares[keys[i % len(keys)]] += 1

    wid = ws.window_id
    write_json(
        os.path.join(out_dir, "egress_summary.json"),
        {
            "window_id": wid,
            "egress_pool_micros": pool,
            "egress_digest": digest,
            "retained_record_count": len(retained_sorted),
            "burst_record_count": len(bursts),
            "payload_unit_octets": octets,
        },
    )
    write_json(os.path.join(out_dir, "egress_rates.json"), {"window_id": wid, "rates": rates})
    write_json(
        os.path.join(out_dir, "egress_bursts.json"),
        {"window_id": wid, "bursts": sorted(bursts, key=lambda b: b["record_id"])},
    )
    write_json(
        os.path.join(out_dir, "egress_order.json"),
        {
            "window_id": wid,
            "order": [
                {
                    "position": i + 1,
                    "record_id": r["record_id"],
                    "egress_rate": r["egress_rate"],
                }
                for i, r in enumerate(retained_sorted)
            ],
        },
    )
    write_json(
        os.path.join(out_dir, "egress_apportionment.json"),
        {"window_id": wid, "curated_payload_units": units, "shares": shares},
    )
    lines = ["group_key,retained_count,group_rate_total,payload_share"]
    for k in keys:
        lines.append(
            "%s,%d,%d,%d" % (k, len(retained_by_group[k]), weights[k], shares[k])
        )
    with open(os.path.join(out_dir, "egress_ladder.csv"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: settle_ingest.py <register_dir> <output_dir>")
    reg_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    params = recover_parameters(reg_dir)

    ws = WorkingSet(load_registers(reg_dir))
    struct = structural_stage(ws, params["tombstone_reading"])
    stage = rate_stage(ws, struct, params)

    rows = struct["participating"]
    curated = stage["curated"]
    withdrawn = [r for r in rows if r["disposition"] == "withdrawn"]
    quarantined = [r for r in rows if r["disposition"] == "quarantined"]

    ledger_rows = sorted(rows, key=lambda r: (r["rec"]["emitted"], r["record_id"]))
    running = 0
    ledger = []
    for i, row in enumerate(ledger_rows):
        running += row["charge"]
        card = row["governing_card"]
        ledger.append(
            {
                "record_id": row["record_id"],
                "sequence": i + 1,
                "emitted_at": row["rec"]["emitted_at"],
                "feed_id": row["feed_id"],
                "domain_id": row["domain_id"],
                "canonical_producer_id": row["canonical_producer_id"],
                "governing_card_id": card["card_id"] if card else "",
                "payload_units": row["payload_units"],
                "disposition": row["disposition"],
                "reason": row["reason"],
                "unit_charge_micros": row["unit_rate"],
                "record_charge_micros": row["charge"],
                "cumulative_charge_micros": running,
            }
        )
    settled_charge = running
    curated_units = sum(r["payload_units"] for r in curated)

    reason_counts = {}
    for row in withdrawn:
        reason_counts[row["reason"]] = reason_counts.get(row["reason"], 0) + 1

    dom_curated = {}
    for row in curated:
        dom_curated.setdefault(row["domain_id"], []).append(row)
    settled_domains = sorted(dom_curated)
    settled_channels = sorted(
        {ws.domains[d]["channel_id"] for d in settled_domains}
    )

    dom_charge = {d: sum(r["charge"] for r in dom_curated[d]) for d in settled_domains}
    dom_units = {
        d: sum(r["payload_units"] for r in dom_curated[d]) for d in settled_domains
    }

    designated_all = sorted(struct["designated"])

    write_json(
        os.path.join(out_dir, "summary.json"),
        {
            "window_id": ws.window_id,
            "window_open": ws.window_open_text,
            "window_close": ws.window_close_text,
            "landing_record_count": len(ws.records),
            "in_window_record_count": len(rows),
            "curated_record_count": len(curated),
            "withdrawn_record_count": len(withdrawn),
            "quarantined_record_count": len(quarantined),
            "curated_payload_units": curated_units,
            "settled_charge_micros": settled_charge,
            "withdrawal_reason_counts": reason_counts,
            "designated_reserve_feed_ids": designated_all,
            "quarantined_feed_ids": sorted(struct["quarantined"]),
            "admitted_domain_count": len(settled_domains),
            "admitted_channel_count": len(settled_channels),
            "resolved_parameters": params,
        },
    )

    per_domain = []
    for d in settled_domains:
        dr = [r for r in rows if r["domain_id"] == d]
        per_domain.append(
            {
                "domain_id": d,
                "curated_record_count": len(dom_curated[d]),
                "withdrawn_record_count": len(
                    [r for r in dr if r["disposition"] == "withdrawn"]
                ),
                "quarantined_record_count": len(
                    [r for r in dr if r["disposition"] == "quarantined"]
                ),
                "settled_charge_micros": dom_charge[d],
                "residual_micros": dom_charge[d]
                - sum(r["charge"] for r in dom_curated[d]),
            }
        )
    channel_charge_total = 0
    for c in settled_channels:
        channel_charge_total += sum(
            dom_charge[d] for d in settled_domains if ws.domains[d]["channel_id"] == c
        )
    domain_charge_total = sum(dom_charge.values())
    write_json(
        os.path.join(out_dir, "reconciliation.json"),
        {
            "window_id": ws.window_id,
            "identity": {
                "in_window_record_count": len(rows),
                "curated_record_count": len(curated),
                "withdrawn_record_count": len(withdrawn),
                "quarantined_record_count": len(quarantined),
                "residual_record_count": len(rows)
                - len(curated)
                - len(withdrawn)
                - len(quarantined),
            },
            "charge": {
                "window_settled_charge_micros": settled_charge,
                "domain_charge_total_micros": domain_charge_total,
                "channel_charge_total_micros": channel_charge_total,
                "residual_micros": settled_charge - domain_charge_total,
            },
            "units": {
                "curated_payload_units": curated_units,
                "domain_curated_units_total": sum(dom_units.values()),
                "residual_units": curated_units - sum(dom_units.values()),
            },
            "per_domain": per_domain,
        },
    )

    resolutions = {}
    for row in rows:
        key = (
            row["rec"]["producer_ref"],
            row["canonical_producer_id"],
            row["identity_status"],
        )
        resolutions[key] = resolutions.get(key, 0) + 1
    write_json(
        os.path.join(out_dir, "ingest_audit.json"),
        {
            "window_id": ws.window_id,
            "ledger": ledger,
            "identity_resolutions": [
                {
                    "producer_ref": k[0],
                    "canonical_producer_id": k[1],
                    "status": k[2],
                    "record_count": v,
                }
                for k, v in sorted(resolutions.items())
            ],
            "tombstone_entity_ids": struct["tombstone_entities"],
            "override_record_ids": sorted(
                r["record_id"] for r in curated if r["record_id"] in ws.upheld
            ),
        },
    )

    q = struct["quality"]
    write_json(
        os.path.join(out_dir, "data_quality.json"),
        {
            "window_id": ws.window_id,
            "out_of_window_record_count": q["out_of_window"],
            "suspended_feed_record_count": q["suspended"],
            "provisional_domain_record_count": q["provisional"],
            "retired_producer_record_count": q["retired"],
            "unknown_producer_record_count": q["unknown"],
            "cyclic_identity_record_count": q["cyclic"],
            "records_without_governing_card": q["no_card"],
            "feeds_over_nominal_throughput": sorted(struct["overage_bp"]),
            "domains_at_quarantine_floor": sorted(
                d
                for d in settled_domains
                if dom_units[d] <= ws.domains[d]["quarantine_floor"]
            ),
            "upheld_exception_count": ws.upheld_count,
            "dismissed_exception_count": ws.dismissed_count,
        },
    )

    slots = struct["slots"]
    write_json(
        os.path.join(out_dir, "slot_designation.json"),
        {
            "window_id": ws.window_id,
            "window_nominal_throughput": slots["window_nominal"],
            "designated_nominal_throughput": slots["designated_nominal"],
            "designated_band_low_bp": slots["band_low"],
            "designated_band_high_bp": slots["band_high"],
            "channels": [
                {
                    "channel_id": c,
                    "slot_ceiling": ws.channels[c]["slot_ceiling"],
                    "candidate_feed_count": len(slots["candidates"][c]),
                    "designated_feed_ids": sorted(slots["designation"][c]),
                    "designated_nominal_throughput": sum(
                        ws.feeds[f]["nominal_throughput"]
                        for f in slots["designation"][c]
                    ),
                }
                for c in slots["participating"]
            ],
        },
    )

    for d in settled_domains:
        dom = ws.domains[d]
        dr = [r for r in rows if r["domain_id"] == d]
        counts = {}
        for r in dr:
            if r["disposition"] == "withdrawn":
                counts[r["reason"]] = counts.get(r["reason"], 0) + 1
        write_json(
            os.path.join(out_dir, "domain_%s.json" % slug(d)),
            {
                "domain_id": d,
                "channel_id": dom["channel_id"],
                "curated_cap": dom["curated_cap"],
                "quarantine_floor": dom["quarantine_floor"],
                "curated_record_count": len(dom_curated[d]),
                "curated_payload_units": dom_units[d],
                "settled_charge_micros": dom_charge[d],
                "curated_record_ids": sorted(r["record_id"] for r in dom_curated[d]),
                "curtailed_record_ids": sorted(stage["curtailed"].get(d, [])),
                "feed_ids": sorted(
                    f for f, v in ws.feeds.items() if v["domain_id"] == d
                ),
                "producer_ids": sorted(
                    {r["canonical_producer_id"] for r in dom_curated[d]}
                ),
                "quarantined_feed_ids": sorted(
                    f for f in struct["quarantined"] if ws.feeds[f]["domain_id"] == d
                ),
                "withdrawal_reason_counts": counts,
            },
        )

    for c in settled_channels:
        members = sorted(
            d for d, v in ws.domains.items() if v["channel_id"] == c
        )
        admitted = [d for d in settled_domains if ws.domains[d]["channel_id"] == c]
        write_json(
            os.path.join(out_dir, "channel_%s.json" % slug(c)),
            {
                "channel_id": c,
                "slot_ceiling": ws.channels[c]["slot_ceiling"],
                "curated_record_count": sum(len(dom_curated[d]) for d in admitted),
                "curated_payload_units": sum(dom_units[d] for d in admitted),
                "settled_charge_micros": sum(dom_charge[d] for d in admitted),
                "designated_reserve_feed_ids": sorted(
                    slots["designation"].get(c, [])
                ),
                "member_domain_ids": members,
                "admitted_domain_ids": sorted(admitted),
                "domain_charge_micros": {d: dom_charge[d] for d in sorted(admitted)},
            },
        )

    run_egress(ws, curated, out_dir)


if __name__ == "__main__":
    main(sys.argv)
