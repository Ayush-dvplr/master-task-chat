#!/usr/bin/env python3
"""Settle one ingest window of the change data capture platform.

Usage: settle_ingest.py <register_directory> <output_directory>

The program recovers every platform property it needs (adjustment precedence,
backpressure coefficient, settlement grid spacing, the convention for values
between grid points, and the reading of the tombstone rule) from the
calibration material in the register directory, then settles the window the
same registers describe and writes the settled account, the partition reports
and the egress layer into the output directory.
"""

import csv
import json
import os
import sys
from itertools import combinations

# ---------------------------------------------------------------------------
# register loading
# ---------------------------------------------------------------------------


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return [
            {(k or ""): (v if v is not None else "") for k, v in row.items()}
            for row in csv.DictReader(fh)
        ]


def _read_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class Registers(object):
    """Every machine readable register the platform keeps."""

    def __init__(self, directory):
        def csvp(name):
            return _read_csv(os.path.join(directory, name))

        cal = _read_json(os.path.join(directory, "calibration_controls.json"))

        self.calibration_controls = cal.get("controls", {}) if isinstance(cal, dict) else {}
        self.calibration_registers = cal.get("registers", {}) if isinstance(cal, dict) else {}

        window = csvp("window_calendar.csv")
        self.window_id = ""
        self.window_open = ""
        self.window_close = ""
        if window:
            row = window[0]
            self.window_id = row.get("window_id", "")
            self.window_open = row.get("window_open", "")
            self.window_close = row.get("window_close", "")

        self.policy = {}
        for row in csvp("window_policy.csv"):
            self.policy[row.get("policy_key", "")] = row.get("policy_value", "")
        self.egress_policy = {}
        for row in csvp("egress_policy.csv"):
            self.egress_policy[row.get("policy_key", "")] = row.get("policy_value", "")

        self.domains = {}
        for row in csvp("domains.csv"):
            self.domains[row["domain_id"]] = {
                "domain_id": row["domain_id"],
                "channel_id": row.get("channel_id", ""),
                "quarantine_floor": int(row.get("quarantine_floor") or 0),
                "curated_cap": int(row.get("curated_cap") or 0),
                "provisional": _flag(row.get("provisional")),
            }

        self.channels = {}
        for row in csvp("channels.csv"):
            self.channels[row["channel_id"]] = {
                "channel_id": row["channel_id"],
                "slot_ceiling": int(row.get("slot_ceiling") or 0),
            }

        self.feeds = {}
        for row in csvp("feeds.csv"):
            self.feeds[row["feed_id"]] = {
                "feed_id": row["feed_id"],
                "domain_id": row.get("domain_id", ""),
                "feed_class": row.get("feed_class", ""),
                "nominal_throughput": int(row.get("nominal_throughput") or 0),
                "defect_allowance_bp": int(row.get("defect_allowance_bp") or 0),
                "floor_rate_micros": int(row.get("floor_rate_micros") or 0),
                "suspended": _flag(row.get("suspended")),
            }

        self.producers = set()
        for row in csvp("producers.csv"):
            if row.get("producer_id"):
                self.producers.add(row["producer_id"])

        self.events = []
        for row in csvp("producer_events.csv"):
            self.events.append(
                {
                    "event_id": row.get("event_id", ""),
                    "effective_at": row.get("effective_at", ""),
                    "event_type": row.get("event_type", ""),
                    "subject_ref": row.get("subject_ref", ""),
                    "target_ref": row.get("target_ref", ""),
                }
            )

        self.cards = []
        for row in csvp("rate_cards.csv"):
            self.cards.append(
                {
                    "card_id": row.get("card_id", ""),
                    "effective_from": row.get("effective_from", ""),
                    "superseded_at": row.get("superseded_at", ""),
                    "rates": {
                        "bulk": int(row.get("rate_bulk") or 0),
                        "stream": int(row.get("rate_stream") or 0),
                        "micro": int(row.get("rate_micro") or 0),
                    },
                    "mults": {
                        "full": int(row.get("mult_full") or 0),
                        "delta": int(row.get("mult_delta") or 0),
                        "snapshot": int(row.get("mult_snapshot") or 0),
                    },
                }
            )

        self.incidents = []
        for row in csvp("feed_incidents.csv"):
            self.incidents.append(
                {
                    "incident_id": row.get("incident_id", ""),
                    "feed_id": row.get("feed_id", ""),
                    "severity": int(row.get("severity") or 0),
                    "opened_at": row.get("opened_at", ""),
                    "closed_at": row.get("closed_at", ""),
                    "abatement_micros": int(row.get("abatement_micros") or 0),
                }
            )

        self.exceptions = []
        for row in _read_json(os.path.join(directory, "exceptions.json")) or []:
            if isinstance(row, dict):
                self.exceptions.append(
                    {
                        "exception_id": row.get("exception_id", ""),
                        "record_id": row.get("record_id", ""),
                        "status": row.get("status", ""),
                        "agreed_unit_rate_micros": int(row.get("agreed_unit_rate_micros") or 0),
                    }
                )

        self.landing = []
        for row in csvp("landing_records.csv"):
            self.landing.append(
                {
                    "record_id": row.get("record_id", ""),
                    "producer_ref": row.get("producer_ref", ""),
                    "feed_id": row.get("feed_id", ""),
                    "emitted_at": row.get("emitted_at", ""),
                    "payload_units": int(row.get("payload_units") or 0),
                    "tier_class": row.get("tier_class", ""),
                    "form_class": row.get("form_class", ""),
                    "op": row.get("op", ""),
                }
            )

    # -- policy helpers ----------------------------------------------------

    def policy_int(self, key, default=0):
        try:
            return int(str(self.policy.get(key, default)).strip())
        except (TypeError, ValueError):
            return default

    def egress_policy_int(self, key, default=0):
        try:
            return int(str(self.egress_policy.get(key, default)).strip())
        except (TypeError, ValueError):
            return default

    @classmethod
    def from_mapping(cls, mapping):
        """Build a register view from the calibration slice's register block."""

        def rows(key):
            return [dict(r) for r in (mapping.get(key) or [])]

        fake = cls.__new__(cls)
        window = rows("window_calendar")
        fake.window_id = window[0].get("window_id", "") if window else ""
        fake.window_open = window[0].get("window_open", "") if window else ""
        fake.window_close = window[0].get("window_close", "") if window else ""
        policy = {}
        for row in rows("window_policy"):
            policy[row.get("policy_key", "")] = row.get("policy_value", "")
        fake.policy = policy
        fake.egress_policy = dict(mapping.get("egress_policy") or {})
        fake.domains = {}
        for row in rows("domains"):
            fake.domains[row["domain_id"]] = {
                "domain_id": row["domain_id"],
                "channel_id": row.get("channel_id", ""),
                "quarantine_floor": int(row.get("quarantine_floor") or 0),
                "curated_cap": int(row.get("curated_cap") or 0),
                "provisional": _flag(row.get("provisional")),
            }
        fake.channels = {}
        for row in rows("channels"):
            fake.channels[row["channel_id"]] = {
                "channel_id": row["channel_id"],
                "slot_ceiling": int(row.get("slot_ceiling") or 0),
            }
        fake.feeds = {}
        for row in rows("feeds"):
            fake.feeds[row["feed_id"]] = {
                "feed_id": row["feed_id"],
                "domain_id": row.get("domain_id", ""),
                "feed_class": row.get("feed_class", ""),
                "nominal_throughput": int(row.get("nominal_throughput") or 0),
                "defect_allowance_bp": int(row.get("defect_allowance_bp") or 0),
                "floor_rate_micros": int(row.get("floor_rate_micros") or 0),
                "suspended": _flag(row.get("suspended")),
            }
        fake.producers = set()
        for row in rows("producers"):
            if row.get("producer_id"):
                fake.producers.add(row["producer_id"])
        fake.events = []
        for row in rows("producer_events"):
            fake.events.append(
                {
                    "event_id": row.get("event_id", ""),
                    "effective_at": row.get("effective_at", ""),
                    "event_type": row.get("event_type", ""),
                    "subject_ref": row.get("subject_ref", ""),
                    "target_ref": row.get("target_ref", ""),
                }
            )
        fake.cards = []
        for row in rows("rate_cards"):
            fake.cards.append(
                {
                    "card_id": row.get("card_id", ""),
                    "effective_from": row.get("effective_from", ""),
                    "superseded_at": row.get("superseded_at", ""),
                    "rates": {
                        "bulk": int(row.get("rate_bulk") or 0),
                        "stream": int(row.get("rate_stream") or 0),
                        "micro": int(row.get("rate_micro") or 0),
                    },
                    "mults": {
                        "full": int(row.get("mult_full") or 0),
                        "delta": int(row.get("mult_delta") or 0),
                        "snapshot": int(row.get("mult_snapshot") or 0),
                    },
                }
            )
        fake.incidents = []
        for row in rows("feed_incidents"):
            fake.incidents.append(
                {
                    "incident_id": row.get("incident_id", ""),
                    "feed_id": row.get("feed_id", ""),
                    "severity": int(row.get("severity") or 0),
                    "opened_at": row.get("opened_at", ""),
                    "closed_at": row.get("closed_at", ""),
                    "abatement_micros": int(row.get("abatement_micros") or 0),
                }
            )
        fake.exceptions = []
        for row in rows("exceptions"):
            fake.exceptions.append(
                {
                    "exception_id": row.get("exception_id", ""),
                    "record_id": row.get("record_id", ""),
                    "status": row.get("status", ""),
                    "agreed_unit_rate_micros": int(row.get("agreed_unit_rate_micros") or 0),
                }
            )
        fake.landing = []
        for row in rows("landing_records"):
            fake.landing.append(
                {
                    "record_id": row.get("record_id", ""),
                    "producer_ref": row.get("producer_ref", ""),
                    "feed_id": row.get("feed_id", ""),
                    "emitted_at": row.get("emitted_at", ""),
                    "payload_units": int(row.get("payload_units") or 0),
                    "tier_class": row.get("tier_class", ""),
                    "form_class": row.get("form_class", ""),
                    "op": row.get("op", ""),
                }
            )
        return fake


def _flag(text):
    return str(text or "").strip().lower() in ("true", "1", "yes", "y", "t")


# ---------------------------------------------------------------------------
# settlement grid
# ---------------------------------------------------------------------------

GRID_CANDIDATES = (5, 10, 20, 25, 40, 50, 80, 100, 125)
ROUNDING_MODES = ("ceil", "floor", "half_down", "half_even", "half_up")
ADJUSTMENTS = ("abatement", "rebate", "override", "surcharge")


def place(num, den, step, mode):
    """Place num/den onto the settlement grid, exact when it already sits on it."""
    if den == 0:
        return 0
    if num % den == 0 and (num // den) % step == 0:
        return num // den
    q = num // (den * step)
    lo = q * step
    hi = lo + step
    lhs = 2 * num
    rhs = (2 * q + 1) * step * den
    if lhs < rhs:
        return lo
    if lhs > rhs:
        return hi
    if mode == "ceil":
        return hi
    if mode == "floor":
        return lo
    if mode == "half_up":
        return hi
    if mode == "half_down":
        return lo
    if mode == "half_even":
        return lo if (q % 2) == 0 else hi
    raise ValueError("unknown rounding mode %r" % (mode,))


# ---------------------------------------------------------------------------
# one record
# ---------------------------------------------------------------------------


class Rec(object):
    __slots__ = (
        "record_id",
        "producer_ref",
        "feed_id",
        "emitted_at",
        "payload_units",
        "tier_class",
        "form_class",
        "op",
        "domain_id",
        "in_window",
        "canonical",
        "status",
        "governing_card_id",
        "disposition",
        "reason",
        "unit_rate",
        "charge",
    )


    def __init__(self, row):
        self.record_id = row["record_id"]
        self.producer_ref = row["producer_ref"]
        self.feed_id = row["feed_id"]
        self.emitted_at = row["emitted_at"]
        self.payload_units = row["payload_units"]
        self.tier_class = row["tier_class"]
        self.form_class = row["form_class"]
        self.op = row["op"]
        self.domain_id = ""
        self.in_window = False
        self.canonical = ""
        self.status = ""
        self.governing_card_id = ""
        self.disposition = ""
        self.reason = ""
        self.unit_rate = 0
        self.charge = 0


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------


def resolve_identity(regs, emitted_at, producer_ref):
    """Return (canonical_producer_id, status) for one reference at one instant."""
    speaking = {}
    retired = set()
    for ev in regs.events:
        if ev["effective_at"] > emitted_at:
            continue
        kind = ev["event_type"]
        if kind == "retire":
            retired.add(ev["subject_ref"])
            continue
        if kind not in ("rename", "merge"):
            continue
        prev = speaking.get(ev["subject_ref"])
        if (
            prev is None
            or ev["effective_at"] > prev["effective_at"]
            or (
                ev["effective_at"] == prev["effective_at"]
                and ev["event_id"] > prev["event_id"]
            )
        ):
            speaking[ev["subject_ref"]] = ev
    ref = producer_ref
    seen = []
    while True:
        ev = speaking.get(ref)
        if ev is None:
            break
        if ref in seen:
            return ("", "cyclic")
        seen.append(ref)
        ref = ev["target_ref"]
    if ref in retired:
        return (ref, "retired")
    if ref in regs.producers:
        return (ref, "resolved")
    return ("", "unknown")


def governing_card(regs, emitted_at, tier_class, form_class):
    """Return (card_id, rate, mult) for one record, or ("", 0, 0)."""
    best = None
    for card in regs.cards:
        if card["effective_from"] > emitted_at:
            continue
        if card["superseded_at"] and card["superseded_at"] <= emitted_at:
            continue
        if best is None or card["effective_from"] > best["effective_from"] or (
            card["effective_from"] == best["effective_from"]
            and card["card_id"] > best["card_id"]
        ):
            best = card
    if best is None:
        return ("", 0, 0)
    return (best["card_id"], best["rates"].get(tier_class, 0), best["mults"].get(form_class, 0))


def speaking_incident(regs, rec):
    """The one incident that speaks for a record, or None."""
    best = None
    for inc in regs.incidents:
        if inc["feed_id"] != rec.feed_id:
            continue
        if inc["opened_at"] > rec.emitted_at:
            continue
        if inc["closed_at"] and inc["closed_at"] <= rec.emitted_at:
            continue
        if (
            best is None
            or inc["severity"] > best["severity"]
            or (inc["severity"] == best["severity"] and inc["incident_id"] > best["incident_id"])
        ):
            best = inc
    return best


def incident_open_at(regs, feed_id, instant):
    for inc in regs.incidents:
        if inc["feed_id"] != feed_id:
            continue
        if inc["opened_at"] > instant:
            continue
        if inc["closed_at"] and inc["closed_at"] <= instant:
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# reserve designation
# ---------------------------------------------------------------------------


def designate_slots(regs):
    """The one valid designation of reserve slots for the window."""
    throughput = 0
    for feed in regs.feeds.values():
        if not feed["suspended"]:
            throughput += feed["nominal_throughput"]

    channel_members = {}
    for domain in regs.domains.values():
        channel_members.setdefault(domain["channel_id"], []).append(domain["domain_id"])
    domain_feeds = {}
    for feed in regs.feeds.values():
        domain_feeds.setdefault(feed["domain_id"], []).append(feed["feed_id"])

    candidates = {}
    for channel_id in sorted(regs.channels):
        domain_ids = channel_members.get(channel_id, [])
        if not any(not regs.domains[d]["provisional"] for d in domain_ids):
            continue
        pool = []
        for feed_id in sorted(regs.feeds):
            feed = regs.feeds[feed_id]
            if feed["domain_id"] not in domain_ids:
                continue
            if feed["suspended"]:
                continue
            if regs.domains[feed["domain_id"]]["provisional"]:
                continue
            if incident_open_at(regs, feed_id, regs.window_close):
                continue
            pool.append(feed_id)
        candidates[channel_id] = pool

    per_channel = []
    for channel_id in sorted(candidates):
        pool = candidates[channel_id]
        ceiling = regs.channels[channel_id]["slot_ceiling"]
        options = []
        for combo in combinations(pool, ceiling) if ceiling <= len(pool) else ():
            classes = [regs.feeds[f]["feed_class"] for f in combo]
            if len(set(classes)) != len(classes):
                continue
            if not any(c == "primary" for c in classes):
                continue
            ok = True
            for domain_id in channel_members.get(channel_id, []):
                eligible = [f for f in pool if regs.feeds[f]["domain_id"] == domain_id]
                if eligible and all(f in combo for f in eligible):
                    ok = False
                    break
            if not ok:
                continue
            options.append(tuple(sorted(combo)))
        per_channel.append((channel_id, pool, options))

    low = regs.policy_int("designated_band_low_bp", 0)
    high = regs.policy_int("designated_band_high_bp", 0)

    valid = []

    def walk(index, chosen):
        if index == len(per_channel):
            total = sum(
                regs.feeds[f]["nominal_throughput"] for combo in chosen.values() for f in combo
            )
            if throughput <= 0:
                return
            share = total * 10000 // throughput
            if low <= share <= high:
                valid.append(tuple(sorted(chosen.items())))
            return
        channel_id, pool, options = per_channel[index]
        for combo in options:
            chosen[channel_id] = combo
            walk(index + 1, chosen)
            del chosen[channel_id]

    walk(0, {})
    valid.sort()

    if valid:
        chosen = dict(valid[0])
    else:
        chosen = {}

    channels = []
    for channel_id, pool, _options in per_channel:
        combo = chosen.get(channel_id, ())
        channels.append(
            {
                "channel_id": channel_id,
                "slot_ceiling": regs.channels[channel_id]["slot_ceiling"],
                "candidate_feed_count": len(pool),
                "designated_feed_ids": list(combo),
                "designated_nominal_throughput": sum(
                    regs.feeds[f]["nominal_throughput"] for f in combo
                ),
            }
        )

    designated = []
    for combo in chosen.values():
        designated.extend(combo)
    total = sum(regs.feeds[f]["nominal_throughput"] for f in designated)
    return {
        "window_nominal_throughput": throughput,
        "designated_nominal_throughput": total,
        "designated_band_low_bp": low,
        "designated_band_high_bp": high,
        "designated_feed_ids": sorted(designated),
        "channels": channels,
        "valid_count": len(valid),
    }


# ---------------------------------------------------------------------------
# disposition of every record
# ---------------------------------------------------------------------------


class Window(object):
    """A window settled far enough to know the disposition of every record.

    Everything this class decides is independent of the platform properties
    that the calibration slice has to pin down, except for the tombstone
    reading, which is a parameter of the constructor.
    """

    def __init__(self, regs, tombstone_reading):
        self.regs = regs
        self.tombstone_reading = tombstone_reading
        self.window_id = regs.window_id
        self.window_open = regs.window_open
        self.window_close = regs.window_close

        self.records = []
        by_id = {}
        for row in regs.landing:
            rec = Rec(row)
            feed = regs.feeds.get(rec.feed_id)
            rec.domain_id = feed["domain_id"] if feed else ""
            rec.in_window = bool(
                feed
                and self.window_open <= rec.emitted_at < self.window_close
                and not feed["suspended"]
            )
            self.records.append(rec)
            by_id[rec.record_id] = rec
        self.by_id = by_id

        # identity work over every record that took part in the settlement
        self.participating = [r for r in self.records if r.in_window]
        for rec in self.participating:
            rec.canonical, rec.status = resolve_identity(
                regs, rec.emitted_at, rec.producer_ref
            )

        self.upheld = {}
        for exc in regs.exceptions:
            if exc["status"] == "upheld":
                self.upheld[exc["record_id"]] = exc["agreed_unit_rate_micros"]

        self.incident_of = {}
        self.card_of = {}
        for rec in self.participating:
            self.incident_of[rec.record_id] = speaking_incident(regs, rec)
            card_id, rate, mult = governing_card(
                regs, rec.emitted_at, rec.tier_class, rec.form_class
            )
            self.card_of[rec.record_id] = (card_id, rate, mult)
            rec.governing_card_id = card_id

        # admission and identity judgements
        for rec in self.participating:
            domain = regs.domains.get(rec.domain_id)
            if domain is not None and domain["provisional"]:
                rec.disposition = "withdrawn"
                rec.reason = "withdrawn_provisional_domain"
            elif rec.status == "retired":
                rec.disposition = "withdrawn"
                rec.reason = "withdrawn_retired_producer"
            elif rec.status == "unknown":
                rec.disposition = "withdrawn"
                rec.reason = "withdrawn_unknown_producer"
            elif rec.status == "cyclic":
                rec.disposition = "withdrawn"
                rec.reason = "withdrawn_cyclic_identity"
            elif rec.governing_card_id == "":
                rec.disposition = "withdrawn"
                rec.reason = "withdrawn_no_governing_card"

        self.eligible = [r for r in self.participating if not r.disposition]

        # tombstones
        self.tombstone_entities = set()
        if self.tombstone_reading == "retroactive":
            spoken = set()
            for rec in self.eligible:
                if rec.op == "tombstone" and rec.canonical:
                    spoken.add(rec.canonical)
            self.tombstone_entities = spoken
            for rec in self.eligible:
                if rec.canonical in spoken:
                    rec.disposition = "withdrawn"
                    rec.reason = "withdrawn_by_tombstone"
        else:
            order = sorted(self.eligible, key=lambda r: (r.emitted_at, r.record_id))
            gone = set()
            for rec in order:
                if rec.disposition:
                    continue
                if rec.op == "tombstone" and rec.canonical:
                    if rec.canonical not in gone:
                        gone.add(rec.canonical)
                    rec.disposition = "withdrawn"
                    rec.reason = "withdrawn_by_tombstone"
                elif rec.canonical in gone:
                    rec.disposition = "withdrawn"
                    rec.reason = "withdrawn_by_tombstone"
            self.tombstone_entities = gone
        self.eligible = [r for r in self.participating if not r.disposition]

        # reserve designation
        self.designation = designate_slots(regs)
        self.designated = set(self.designation["designated_feed_ids"])
        for rec in self.eligible:
            if rec.feed_id in self.designated:
                rec.disposition = "withdrawn"
                rec.reason = "withdrawn_by_reserve_designation"
        self.eligible = [r for r in self.participating if not r.disposition]

        # quarantine and taint, settled together
        self.quarantined_feeds, self.taint = self._settle_quarantine()
        for rec in self.eligible:
            if rec.feed_id in self.quarantined_feeds:
                rec.disposition = "quarantined"
                rec.reason = "quarantined_defect_rate"
        self.eligible = [r for r in self.participating if not r.disposition]
        for rec in self.eligible:
            if (rec.domain_id, rec.canonical) in self.taint:
                rec.disposition = "withdrawn"
                rec.reason = "withdrawn_by_quarantine_cascade"
        self.eligible = [r for r in self.participating if not r.disposition]

        # feed load over the curated set as it stands before curtailment
        self.load = {}
        for feed_id in self.regs.feeds:
            self.load[feed_id] = 0
        for rec in self.eligible:
            self.load[rec.feed_id] += rec.payload_units
        self.overage_bp = {}
        for feed_id, feed in self.regs.feeds.items():
            nominal = feed["nominal_throughput"]
            load = self.load.get(feed_id, 0)
            if nominal > 0 and load > nominal:
                self.overage_bp[feed_id] = (load - nominal) * 10000 // nominal
            else:
                self.overage_bp[feed_id] = 0

        self.pre_curtailment_units = {}
        for domain_id in self.regs.domains:
            self.pre_curtailment_units[domain_id] = sum(
                r.payload_units for r in self.eligible if r.domain_id == domain_id
            )
        self.eligible_set = set(self.eligible)

    # -- quarantine ---------------------------------------------------------

    def _pool_of(self, feed_id):
        pool = []
        for rec in self.participating:
            if rec.feed_id != feed_id:
                continue
            if rec.reason == "withdrawn_by_tombstone" or not rec.disposition:
                pool.append(rec)
        return pool

    def _settle_quarantine(self):
        regs = self.regs
        pools = {}
        for feed_id in sorted(regs.feeds):
            if feed_id in self.designated:
                continue
            pool = self._pool_of(feed_id)
            if pool:
                pools[feed_id] = pool
        quarantined = set()
        taint = set()
        while True:
            new_taint = set()
            for feed_id in quarantined:
                domain_id = regs.feeds[feed_id]["domain_id"]
                for rec in pools.get(feed_id, ()):
                    if not rec.disposition and rec.canonical:
                        new_taint.add((domain_id, rec.canonical))
            new_quarantined = set()
            for feed_id, pool in pools.items():
                allowance = regs.feeds[feed_id]["defect_allowance_bp"]
                if not pool:
                    continue
                defective = 0
                for rec in pool:
                    if rec.reason == "withdrawn_by_tombstone":
                        defective += 1
                    elif (rec.domain_id, rec.canonical) in taint:
                        defective += 1
                rate = defective * 10000 // len(pool)
                if rate > allowance:
                    new_quarantined.add(feed_id)
            if new_quarantined == quarantined and new_taint == taint:
                return new_quarantined, new_taint
            quarantined = new_quarantined
            taint = new_taint

    # -- rates ---------------------------------------------------------------

    def rate_inputs(self, rec):
        """Everything the adjustments need, gathered once per record."""
        _card_id, rate, mult = self.card_of[rec.record_id]
        incident = self.incident_of[rec.record_id]
        feed = self.regs.feeds[rec.feed_id]
        return {
            "base_num": rate * mult,
            "base_den": 10000,
            "abatement": incident["abatement_micros"] if incident else 0,
            "allowance_bp": feed["defect_allowance_bp"],
            "override": self.upheld.get(rec.record_id),
            "overage_bp": self.overage_bp.get(rec.feed_id, 0),
            "floor": feed["floor_rate_micros"],
        }

    def unit_rate(self, rec, params):
        inputs = self.rate_inputs(rec)
        return adjusted_rate(inputs, params)

    def rate_all(self, params):
        for rec in self.eligible:
            rec.unit_rate = self.unit_rate(rec, params)
            rec.charge = rec.unit_rate * rec.payload_units

    # -- curtailment ---------------------------------------------------------

    def curtail(self):
        """Fit every domain inside its curated cap, keeping the most charge."""
        self.curtailed_ids = []
        for domain_id in sorted(self.regs.domains):
            domain = self.regs.domains[domain_id]
            pool = [r for r in self.eligible if r.domain_id == domain_id]
            cap = domain["curated_cap"]
            total = sum(r.payload_units for r in pool)
            if total <= cap or not pool:
                for rec in pool:
                    rec.disposition = "curated"
                    rec.reason = ""
                continue
            keep = solve_curtailment(pool, cap)
            keep_set = set(keep)
            for rec in pool:
                if rec.record_id in keep_set:
                    rec.disposition = "curated"
                    rec.reason = ""
                else:
                    rec.disposition = "withdrawn"
                    rec.reason = "withdrawn_by_curtailment"
                    self.curtailed_ids.append(rec.record_id)
        # a record that is not curated carries no charge at all
        for rec in self.participating:
            if rec.disposition != "curated":
                rec.unit_rate = 0
                rec.charge = 0


def adjusted_rate(inputs, params):
    """The settled unit rate of one record under one reading of the platform."""
    step = params["quantisation_step_micros"]
    mode = params["rounding_mode"]
    rate = place(inputs["base_num"], inputs["base_den"], step, mode)
    for name in params["adjustment_precedence"]:
        if name == "abatement":
            if inputs["abatement"]:
                rate = place(max(0, rate - inputs["abatement"]), 1, step, mode)
        elif name == "rebate":
            if inputs["allowance_bp"]:
                rate = place(
                    rate * (10000 - inputs["allowance_bp"]), 10000, step, mode
                )
        elif name == "override":
            if inputs["override"] is not None:
                rate = place(inputs["override"], 1, step, mode)
        elif name == "surcharge":
            if inputs["overage_bp"]:
                share = params["backpressure_coefficient_micros"] * inputs["overage_bp"] // 10000
                rate = place(rate + share, 1, step, mode)
    if rate < inputs["floor"]:
        rate = inputs["floor"]
    return rate


COUNT_SCALE = 1 << 24


def solve_curtailment(pool, cap):
    """Keep the way of fitting inside the cap the platform prefers.

    Most charge first, then most records, then the retained identifiers that
    come first compared as text, and never a way that silences a feed that
    reached curtailment with a record still eligible.
    """
    items = sorted(pool, key=lambda r: r.record_id)
    n = len(items)
    feeds = sorted({r.feed_id for r in items})
    feed_index = {f: i for i, f in enumerate(feeds)}
    full_mask = (1 << len(feeds)) - 1
    weights = [r.payload_units for r in items]
    values = [r.charge for r in items]
    masks = [1 << feed_index[r.feed_id] for r in items]
    width = 1 << len(feeds)

    # best[i][m][c]: the greatest packed (charge, record count) pair reachable
    # from items i.. with capacity c starting from covered feed mask m. Charge
    # is carried above COUNT_SCALE and the count below it, so a single integer
    # comparison settles both preferences in the order the rulebook states.
    neg = -(1 << 62)
    best = []
    for _i in range(n + 1):
        best.append([[neg] * (cap + 1) for _ in range(width)])
    for c in range(cap + 1):
        best[n][full_mask][c] = 0
    for i in range(n - 1, -1, -1):
        w = weights[i]
        v = values[i]
        bit = masks[i]
        for m in range(width):
            row = best[i][m]
            skip = best[i + 1][m]
            taken = best[i + 1][m | bit]
            for c in range(cap + 1):
                a = skip[c]
                b = neg
                if w <= c:
                    sub = taken[c - w]
                    if sub != neg:
                        b = sub + v * COUNT_SCALE + 1
                row[c] = a if a >= b else b

    keep = walk_solution(items, best, cap, weights, masks, values, n)
    if keep is not None:
        return keep

    # No way of fitting inside the cap keeps every feed speaking; fall back to
    # the plain optimum so the window still settles at all.
    plain = [[[neg] * (cap + 1)] for _ in range(n + 1)]
    for c in range(cap + 1):
        plain[n][0][c] = 0
    for i in range(n - 1, -1, -1):
        w = weights[i]
        v = values[i]
        row = plain[i][0]
        nxt = plain[i + 1][0]
        for c in range(cap + 1):
            a = nxt[c]
            b = neg
            if w <= c:
                sub = nxt[c - w]
                if sub != neg:
                    b = sub + v * COUNT_SCALE + 1
            row[c] = a if a >= b else b
    return walk_solution(items, plain, cap, weights, masks, values, n)


def walk_solution(items, table, cap, weights, masks, values, n):
    """Walk a packed table, taking the smallest record identifiers it can.

    Every solution the walk can reach settles the same charge and keeps the
    same number of records, so taking an item whenever the optimum survives it
    yields the retained identifier list that compares first as text.
    """
    if table[0][0][cap] == -(1 << 62):
        return None
    keep = []
    c = cap
    m = 0
    for i in range(n):
        w = weights[i]
        if w > c:
            continue
        here = table[i][m][c]
        nm = m | masks[i] if len(table[0]) > 1 else m
        sub = table[i + 1][nm][c - w]
        if sub == -(1 << 62):
            continue
        if sub + values[i] * COUNT_SCALE + 1 == here:
            keep.append(items[i].record_id)
            c -= w
            m = nm
    return keep


# ---------------------------------------------------------------------------
# parameter recovery
# ---------------------------------------------------------------------------


def _permutations(seq):
    if len(seq) <= 1:
        return [list(seq)]
    out = []
    for i, item in enumerate(seq):
        rest = seq[:i] + seq[i + 1 :]
        for tail in _permutations(rest):
            out.append([item] + tail)
    return out


ADJUSTMENT_ORDERS = _permutations(list(ADJUSTMENTS))
COEFFICIENT_RANGE = 601


def recover_parameters(regs):
    """Find the one reading of the platform that reproduces every control."""
    controls = regs.calibration_controls
    if not controls:
        raise SystemExit("no calibration controls in the register directory")

    cal_regs = Registers.from_mapping(regs.calibration_registers)
    rate_controls = controls.get("adjusted_unit_rate_micros") or {}

    surviving = []
    for tombstone_reading in ("retroactive", "forward"):
        win = Window(cal_regs, tombstone_reading)
        if not _dispositions_match(win, controls):
            continue
        surviving.append((tombstone_reading, win))
    if not surviving:
        raise SystemExit("no reading of the platform reproduces the calibration figures")

    candidates = []
    for tombstone_reading, win in surviving:
        named = []
        for record_id, wanted in sorted(rate_controls.items()):
            rec = win.by_id.get(record_id)
            if rec is None or rec not in win.eligible_set:
                named = []
                break
            named.append((rec, wanted))
        if not named and not _no_curtailment_possible(win):
            continue
        for order in ADJUSTMENT_ORDERS:
            for step in GRID_CANDIDATES:
                for mode in ROUNDING_MODES:
                    if named:
                        head_rec, head_wanted = named[0]
                        head_inputs = win.rate_inputs(head_rec)
                        for coeff in range(COEFFICIENT_RANGE):
                            params = {
                                "adjustment_precedence": order,
                                "backpressure_coefficient_micros": coeff,
                                "quantisation_step_micros": step,
                                "rounding_mode": mode,
                                "tombstone_reading": tombstone_reading,
                            }
                            if adjusted_rate(head_inputs, params) != head_wanted:
                                continue
                            if all(
                                adjusted_rate(win.rate_inputs(rec), params) == wanted
                                for rec, wanted in named[1:]
                            ):
                                candidates.append(params)
                    else:
                        # no record level figure published: settle the slice
                        # itself under every reading and let the totals decide
                        inputs = [win.rate_inputs(rec) for rec in win.eligible]
                        payloads = [rec.payload_units for rec in win.eligible]
                        for coeff in range(COEFFICIENT_RANGE):
                            params = {
                                "adjustment_precedence": order,
                                "backpressure_coefficient_micros": coeff,
                                "quantisation_step_micros": step,
                                "rounding_mode": mode,
                                "tombstone_reading": tombstone_reading,
                            }
                            if _slice_totals_match(inputs, payloads, params, controls):
                                candidates.append(params)
    if not candidates:
        raise SystemExit("no combination of the platform properties matches the controls")

    settled = []
    for params in candidates:
        win = Window(cal_regs, params["tombstone_reading"])
        win.rate_all(params)
        win.curtail()
        if _settlement_matches(win, controls):
            settled.append(params)
    if not settled:
        raise SystemExit("no combination reproduces every published control figure")
    if len(settled) > 1:
        settled.sort(key=_params_sort_key)
    return settled[0]


def _params_sort_key(params):
    return (
        params["adjustment_precedence"],
        params["backpressure_coefficient_micros"],
        params["quantisation_step_micros"],
        params["rounding_mode"],
        params["tombstone_reading"],
    )


def _dispositions_match(win, controls):
    """Controls that do not depend on charge or on the settlement grid."""
    okay = True
    if "quarantined_feed_ids" in controls:
        okay = okay and sorted(win.quarantined_feeds) == sorted(controls["quarantined_feed_ids"])
    if not okay:
        return False
    if "withdrawal_reason_counts" in controls:
        counts = _reason_counts(win)
        expected = dict(controls["withdrawal_reason_counts"])
        if "withdrawn_by_curtailment" in expected:
            expected.pop("withdrawn_by_curtailment")
            counts = {k: v for k, v in counts.items() if k != "withdrawn_by_curtailment"}
        if counts != expected:
            return False
    if "curated_record_count" in controls and _no_curtailment_possible(win):
        if len(win.eligible) != controls["curated_record_count"]:
            return False
    if "curated_payload_units" in controls and _no_curtailment_possible(win):
        if sum(r.payload_units for r in win.eligible) != controls["curated_payload_units"]:
            return False
    if "withdrawn_record_count" in controls and _no_curtailment_possible(win):
        if len([r for r in win.participating if r.disposition == "withdrawn"]) != controls[
            "withdrawn_record_count"
        ]:
            return False
    return True


def _no_curtailment_possible(win):
    for domain_id, units in win.pre_curtailment_units.items():
        if units > win.regs.domains[domain_id]["curated_cap"]:
            return False
    return True


def _slice_totals_match(inputs, payloads, params, controls):
    """Totals the slice would settle, for slices that publish no record rates."""
    total = 0
    units = 0
    for one, payload in zip(inputs, payloads):
        total += adjusted_rate(one, params) * payload
        units += payload
    if "settled_charge_micros" in controls and total != controls["settled_charge_micros"]:
        return False
    if "curated_payload_units" in controls and units != controls["curated_payload_units"]:
        return False
    return True


def _reason_counts(win):
    counts = {}
    for rec in win.participating:
        if rec.disposition == "withdrawn" and rec.reason:
            counts[rec.reason] = counts.get(rec.reason, 0) + 1
    return counts


def _settlement_matches(win, controls):
    curated = [r for r in win.participating if r.disposition == "curated"]
    withdrawn = [r for r in win.participating if r.disposition == "withdrawn"]
    quarantined = [r for r in win.participating if r.disposition == "quarantined"]
    charge = sum(r.charge for r in curated)
    if "curated_record_count" in controls and len(curated) != controls["curated_record_count"]:
        return False
    if "withdrawn_record_count" in controls and len(withdrawn) != controls["withdrawn_record_count"]:
        return False
    if "quarantined_record_count" in controls and len(quarantined) != controls["quarantined_record_count"]:
        return False
    if "curated_payload_units" in controls and sum(
        r.payload_units for r in curated
    ) != controls["curated_payload_units"]:
        return False
    if "settled_charge_micros" in controls and charge != controls["settled_charge_micros"]:
        return False
    if "quarantined_feed_ids" in controls and sorted(win.quarantined_feeds) != sorted(
        controls["quarantined_feed_ids"]
    ):
        return False
    if "withdrawal_reason_counts" in controls and _reason_counts(win) != dict(
        controls["withdrawal_reason_counts"]
    ):
        return False
    if "domain_settled_charge_micros" in controls:
        per_domain = {}
        for rec in curated:
            per_domain[rec.domain_id] = per_domain.get(rec.domain_id, 0) + rec.charge
        expected = {k: int(v) for k, v in controls["domain_settled_charge_micros"].items()}
        if per_domain != expected:
            return False
    rates = controls.get("adjusted_unit_rate_micros") or {}
    for record_id, wanted in rates.items():
        rec = win.by_id.get(record_id)
        if rec is None or rec.disposition != "curated" or rec.unit_rate != int(wanted):
            return False
    return True


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True))
        fh.write("\n")


def partition_name(kind, identifier):
    """The file name a partition report is written under."""
    out = []
    for ch in identifier.lower():
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            out.append(ch)
        elif out and out[-1] != "_":
            out.append("_")
    return "%s_%s.json" % (kind, "".join(out).strip("_"))


def ledger_rows(win):
    order = sorted(win.participating, key=lambda r: (r.emitted_at, r.record_id))
    rows = []
    cumulative = 0
    for index, rec in enumerate(order, 1):
        cumulative += rec.charge
        rows.append(
            {
                "record_id": rec.record_id,
                "sequence": index,
                "emitted_at": rec.emitted_at,
                "feed_id": rec.feed_id,
                "domain_id": rec.domain_id,
                "canonical_producer_id": rec.canonical,
                "governing_card_id": rec.governing_card_id,
                "payload_units": rec.payload_units,
                "disposition": rec.disposition,
                "reason": rec.reason,
                "unit_charge_micros": rec.unit_rate,
                "record_charge_micros": rec.charge,
                "cumulative_charge_micros": cumulative,
            }
        )
    return rows


def identity_rows(win):
    counts = {}
    for rec in win.participating:
        key = (rec.producer_ref, rec.canonical, rec.status)
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "producer_ref": ref,
            "canonical_producer_id": canonical,
            "status": status,
            "record_count": counts[(ref, canonical, status)],
        }
        for (ref, canonical, status) in sorted(counts)
    ]


def build_domain_report(win, domain_id):
    regs = win.regs
    domain = regs.domains[domain_id]
    records = [r for r in win.participating if r.domain_id == domain_id]
    curated = [r for r in records if r.disposition == "curated"]
    reasons = {}
    for rec in records:
        if rec.disposition == "withdrawn" and rec.reason:
            reasons[rec.reason] = reasons.get(rec.reason, 0) + 1
    return {
        "domain_id": domain_id,
        "channel_id": domain["channel_id"],
        "curated_cap": domain["curated_cap"],
        "quarantine_floor": domain["quarantine_floor"],
        "curated_record_count": len(curated),
        "curated_payload_units": sum(r.payload_units for r in curated),
        "settled_charge_micros": sum(r.charge for r in curated),
        "curated_record_ids": sorted(r.record_id for r in curated),
        "curtailed_record_ids": sorted(
            r.record_id for r in records if r.reason == "withdrawn_by_curtailment"
        ),
        "feed_ids": sorted(
            f for f, feed in regs.feeds.items() if feed["domain_id"] == domain_id
        ),
        "producer_ids": sorted({r.canonical for r in curated if r.canonical}),
        "quarantined_feed_ids": sorted(
            f
            for f, feed in regs.feeds.items()
            if feed["domain_id"] == domain_id and f in win.quarantined_feeds
        ),
        "withdrawal_reason_counts": reasons,
    }


def build_channel_report(win, channel_id):
    regs = win.regs
    members = sorted(
        d for d, domain in regs.domains.items() if domain["channel_id"] == channel_id
    )
    admitted = []
    charge = {}
    curated_count = 0
    curated_units = 0
    for domain_id in members:
        report = win.domain_reports.get(domain_id)
        if report is None:
            continue
        admitted.append(domain_id)
        charge[domain_id] = report["settled_charge_micros"]
        curated_count += report["curated_record_count"]
        curated_units += report["curated_payload_units"]
    return {
        "channel_id": channel_id,
        "slot_ceiling": regs.channels[channel_id]["slot_ceiling"],
        "curated_record_count": curated_count,
        "curated_payload_units": curated_units,
        "settled_charge_micros": sum(charge.values()),
        "designated_reserve_feed_ids": sorted(
            f
            for f in win.designation["designated_feed_ids"]
            if f in regs.feeds and regs.feeds[f]["domain_id"] in members
        ),
        "member_domain_ids": members,
        "admitted_domain_ids": admitted,
        "domain_charge_micros": charge,
    }


def write_egress(win, out_dir):
    """The egress layer: what each curated record cost per octet of payload."""
    regs = win.regs
    octets = regs.egress_policy_int("payload_unit_octets", 0)
    sigma = regs.egress_policy_int("egress_sigma", 0)
    modulus = regs.egress_policy_int("egress_modulus", 0)

    curated = sorted(
        (r for r in win.participating if r.disposition == "curated"),
        key=lambda r: r.record_id,
    )
    rates = []
    for rec in curated:
        octet_count = rec.payload_units * octets
        rate = rec.charge // octet_count if octet_count else 0
        rates.append(
            {
                "record_id": rec.record_id,
                "feed_id": rec.feed_id,
                "domain_id": rec.domain_id,
                "payload_units": rec.payload_units,
                "record_charge_micros": rec.charge,
                "egress_rate": rate,
            }
        )

    groups = {}
    for row in rates:
        key = "%s:%s" % (row["domain_id"], row["feed_id"])
        groups.setdefault(key, []).append(row["egress_rate"])

    bursts = []
    retained = []
    stats = {}
    for key in sorted(groups):
        sample = sorted(groups[key])
        med = _median(sample)
        mad = _median([abs(v - med) for v in sample])
        threshold = med + sigma * mad
        stats[key] = (med, mad, threshold)
    for row in rates:
        key = "%s:%s" % (row["domain_id"], row["feed_id"])
        med, mad, threshold = stats[key]
        if len(groups[key]) < 4:
            retained.append(row)
            continue
        if row["egress_rate"] > threshold:
            bursts.append(
                {
                    "record_id": row["record_id"],
                    "feed_id": row["feed_id"],
                    "domain_id": row["domain_id"],
                    "egress_rate": row["egress_rate"],
                    "group_median": med,
                    "group_mad": mad,
                    "threshold": threshold,
                }
            )
        else:
            retained.append(row)

    order = sorted(retained, key=lambda row: (row["egress_rate"], row["record_id"]))
    digest = 0
    for position, row in enumerate(order, 1):
        digest += position * row["egress_rate"]
    digest %= modulus if modulus else 1
    pool = sum(row["egress_rate"] for row in retained)

    units = sum(r.payload_units for r in curated)
    totals = {}
    counts = {}
    for row in retained:
        key = "%s:%s" % (row["domain_id"], row["feed_id"])
        totals[key] = totals.get(key, 0) + row["egress_rate"]
        counts[key] = counts.get(key, 0) + 1
    shares = {}
    remainders = []
    if pool > 0 and units:
        for key in sorted(totals):
            exact = totals[key] * units
            shares[key] = exact // pool
            remainders.append((exact % pool, key))
        left = units - sum(shares.values())
        remainders.sort(key=lambda item: (-item[0], item[1]))
        for index in range(left):
            shares[remainders[index % len(remainders)][1]] += 1

    _write_json(
        os.path.join(out_dir, "egress_summary.json"),
        {
            "window_id": win.window_id,
            "egress_pool_micros": pool,
            "egress_digest": digest,
            "retained_record_count": len(retained),
            "burst_record_count": len(bursts),
            "payload_unit_octets": octets,
        },
    )
    _write_json(
        os.path.join(out_dir, "egress_rates.json"),
        {"window_id": win.window_id, "rates": rates},
    )
    _write_json(
        os.path.join(out_dir, "egress_bursts.json"),
        {"window_id": win.window_id, "bursts": bursts},
    )
    _write_json(
        os.path.join(out_dir, "egress_order.json"),
        {
            "window_id": win.window_id,
            "order": [
                {"position": i, "record_id": row["record_id"], "egress_rate": row["egress_rate"]}
                for i, row in enumerate(order, 1)
            ],
        },
    )
    _write_json(
        os.path.join(out_dir, "egress_apportionment.json"),
        {"window_id": win.window_id, "curated_payload_units": units, "shares": shares},
    )
    lines = ["group_key,retained_count,group_rate_total,payload_share"]
    for key in sorted(totals):
        lines.append(
            "%s,%d,%d,%d" % (key, counts[key], totals[key], shares.get(key, 0))
        )
    with open(os.path.join(out_dir, "egress_ladder.csv"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")


def _median(sample):
    """The egress median: an even sample takes its lower middle value."""
    ordered = sorted(sample)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return ordered[middle - 1]


# ---------------------------------------------------------------------------
# settling a window
# ---------------------------------------------------------------------------

QUALITY_REASONS = (
    "withdrawn_provisional_domain",
    "withdrawn_retired_producer",
    "withdrawn_unknown_producer",
    "withdrawn_cyclic_identity",
    "withdrawn_no_governing_card",
)


def settle(regs, out_dir):
    params = recover_parameters(regs)
    win = Window(regs, params["tombstone_reading"])
    win.rate_all(params)
    win.curtail()

    win.domain_reports = {}
    for domain_id in sorted(regs.domains):
        report = build_domain_report(win, domain_id)
        if report["curated_record_count"] > 0:
            win.domain_reports[domain_id] = report

    curated = [r for r in win.participating if r.disposition == "curated"]
    withdrawn = [r for r in win.participating if r.disposition == "withdrawn"]
    quarantined = [r for r in win.participating if r.disposition == "quarantined"]
    charge = sum(r.charge for r in curated)
    units = sum(r.payload_units for r in curated)

    reasons = {}
    for rec in withdrawn:
        if rec.reason:
            reasons[rec.reason] = reasons.get(rec.reason, 0) + 1

    settled_channels = sorted(
        {report["channel_id"] for report in win.domain_reports.values()}
    )

    _write_json(
        os.path.join(out_dir, "summary.json"),
        {
            "window_id": win.window_id,
            "window_open": win.window_open,
            "window_close": win.window_close,
            "landing_record_count": len(regs.landing),
            "in_window_record_count": len(win.participating),
            "curated_record_count": len(curated),
            "withdrawn_record_count": len(withdrawn),
            "quarantined_record_count": len(quarantined),
            "curated_payload_units": units,
            "settled_charge_micros": charge,
            "withdrawal_reason_counts": reasons,
            "designated_reserve_feed_ids": sorted(win.designated),
            "quarantined_feed_ids": sorted(win.quarantined_feeds),
            "admitted_domain_count": len(win.domain_reports),
            "admitted_channel_count": len(settled_channels),
            "resolved_parameters": {
                "adjustment_precedence": list(params["adjustment_precedence"]),
                "backpressure_coefficient_micros": params[
                    "backpressure_coefficient_micros"
                ],
                "quantisation_step_micros": params["quantisation_step_micros"],
                "rounding_mode": params["rounding_mode"],
                "tombstone_reading": params["tombstone_reading"],
            },
        },
    )

    domain_charge_total = sum(
        report["settled_charge_micros"] for report in win.domain_reports.values()
    )
    channel_reports = {}
    channel_charge_total = 0
    for channel_id in settled_channels:
        report = build_channel_report(win, channel_id)
        channel_reports[channel_id] = report
        channel_charge_total += report["settled_charge_micros"]

    domain_units_total = sum(
        report["curated_payload_units"] for report in win.domain_reports.values()
    )
    _write_json(
        os.path.join(out_dir, "reconciliation.json"),
        {
            "window_id": win.window_id,
            "identity": {
                "in_window_record_count": len(win.participating),
                "curated_record_count": len(curated),
                "withdrawn_record_count": len(withdrawn),
                "quarantined_record_count": len(quarantined),
                "residual_record_count": len(win.participating)
                - len(curated)
                - len(withdrawn)
                - len(quarantined),
            },
            "charge": {
                "window_settled_charge_micros": charge,
                "domain_charge_total_micros": domain_charge_total,
                "channel_charge_total_micros": channel_charge_total,
                "residual_micros": charge - domain_charge_total,
            },
            "units": {
                "curated_payload_units": units,
                "domain_curated_units_total": domain_units_total,
                "residual_units": units - domain_units_total,
            },
            "per_domain": [
                {
                    "domain_id": domain_id,
                    "curated_record_count": win.domain_reports[domain_id][
                        "curated_record_count"
                    ],
                    "withdrawn_record_count": len(
                        [
                            r
                            for r in win.participating
                            if r.domain_id == domain_id
                            and r.disposition == "withdrawn"
                        ]
                    ),
                    "quarantined_record_count": len(
                        [
                            r
                            for r in win.participating
                            if r.domain_id == domain_id
                            and r.disposition == "quarantined"
                        ]
                    ),
                    "settled_charge_micros": win.domain_reports[domain_id][
                        "settled_charge_micros"
                    ],
                    "residual_micros": win.domain_reports[domain_id][
                        "settled_charge_micros"
                    ]
                    - sum(
                        r.charge
                        for r in win.participating
                        if r.domain_id == domain_id and r.disposition == "curated"
                    ),
                }
                for domain_id in sorted(win.domain_reports)
            ],
        },
    )

    _write_json(
        os.path.join(out_dir, "ingest_audit.json"),
        {
            "window_id": win.window_id,
            "ledger": ledger_rows(win),
            "identity_resolutions": identity_rows(win),
            "tombstone_entity_ids": sorted(win.tombstone_entities),
            "override_record_ids": sorted(
                r.record_id for r in curated if r.record_id in win.upheld
            ),
        },
    )

    in_window_only = [
        r for r in win.records if win.window_open <= r.emitted_at < win.window_close
    ]
    _write_json(
        os.path.join(out_dir, "data_quality.json"),
        {
            "window_id": win.window_id,
            "out_of_window_record_count": len(regs.landing) - len(in_window_only),
            "suspended_feed_record_count": len(
                [
                    r
                    for r in in_window_only
                    if r.feed_id in win.regs.feeds
                    and win.regs.feeds[r.feed_id]["suspended"]
                ]
            ),
            "provisional_domain_record_count": len(
                [r for r in win.participating if r.reason == QUALITY_REASONS[0]]
            ),
            "retired_producer_record_count": len(
                [r for r in win.participating if r.reason == QUALITY_REASONS[1]]
            ),
            "unknown_producer_record_count": len(
                [r for r in win.participating if r.reason == QUALITY_REASONS[2]]
            ),
            "cyclic_identity_record_count": len(
                [r for r in win.participating if r.reason == QUALITY_REASONS[3]]
            ),
            "records_without_governing_card": len(
                [r for r in win.participating if r.reason == QUALITY_REASONS[4]]
            ),
            "feeds_over_nominal_throughput": sorted(
                f for f in win.load if win.overage_bp.get(f, 0) > 0
            ),
            "domains_at_quarantine_floor": sorted(
                domain_id
                for domain_id, report in win.domain_reports.items()
                if report["curated_payload_units"]
                <= regs.domains[domain_id]["quarantine_floor"]
            ),
            "upheld_exception_count": len(
                [e for e in regs.exceptions if e["status"] == "upheld"]
            ),
            "dismissed_exception_count": len(
                [e for e in regs.exceptions if e["status"] == "dismissed"]
            ),
        },
    )

    _write_json(
        os.path.join(out_dir, "slot_designation.json"),
        {
            "window_id": win.window_id,
            "window_nominal_throughput": win.designation["window_nominal_throughput"],
            "designated_nominal_throughput": win.designation[
                "designated_nominal_throughput"
            ],
            "designated_band_low_bp": win.designation["designated_band_low_bp"],
            "designated_band_high_bp": win.designation["designated_band_high_bp"],
            "channels": win.designation["channels"],
        },
    )

    for domain_id, report in win.domain_reports.items():
        _write_json(os.path.join(out_dir, partition_name("domain", domain_id)), report)
    for channel_id, report in channel_reports.items():
        _write_json(os.path.join(out_dir, partition_name("channel", channel_id)), report)

    write_egress(win, out_dir)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: settle_ingest.py <registers> <output>\n")
        return 2
    register_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(register_dir):
        sys.stderr.write("not a directory: %s\n" % register_dir)
        return 2
    os.makedirs(out_dir, exist_ok=True)
    regs = Registers(register_dir)
    settle(regs, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))




