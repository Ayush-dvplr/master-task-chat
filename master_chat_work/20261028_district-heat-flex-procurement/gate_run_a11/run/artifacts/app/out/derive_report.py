#!/usr/bin/env python3
"""Derive the district-heat flexibility programme reports from one season extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import configparser
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

LABELS = (
    "SAFETY_HOLD",
    "COOLDOWN",
    "CONTINUITY_WAIVED",
    "CERTIFICATE_PENDING",
    "CLEAR",
)

REGION_TOTAL_KEYS = (
    "event_count",
    "candidate_offer_count",
    "selected_offer_count",
    "relief_ticks",
    "recovery_ticks",
    "shortfall_ticks",
    "overdelivery_ticks",
    "bid_cost_cents",
    "credit_cents",
    "grant_pool_cents",
    "grant_funded_cents",
    "grant_allocated_cents",
    "grant_unallocated_cents",
)

SEGMENT_TOTAL_KEYS = (
    "selected_offer_count",
    "relief_ticks",
    "recovery_ticks",
    "bid_cost_cents",
    "credit_cents",
    "floor_ticks",
)


def half_up(num, den):
    return (2 * num + den) // (2 * den)


def half_even(num, den):
    quotient, rest = divmod(num, den)
    twice = 2 * rest
    if twice > den or (twice == den and quotient % 2):
        quotient += 1
    return quotient


def read_delimited(path, delimiter):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def read_commented_delimited(path, delimiter):
    with open(path, encoding="utf-8") as handle:
        lines = [
            line
            for line in handle.read().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    return list(csv.DictReader(lines, delimiter=delimiter))


def read_record_lines(path):
    with open(path, encoding="utf-8") as handle:
        return [
            line
            for line in handle.read().splitlines()
            if line.strip() and not line.startswith("#")
        ]


class Extract:
    """Everything one season extract says, parsed into report-ready form."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.rows = {}
        self.load_config()
        self.load_events()
        self.load_sites()
        self.load_offers()
        self.load_profiles()
        self.load_targets()
        self.load_feeder_limits()
        self.load_state()
        self.load_waivers()
        self.load_floors()
        self.load_rate_cards()
        self.load_weights()
        self.load_pools()
        self.load_allowances()
        self.rows["export_manifest.tsv"] = len(
            read_commented_delimited(self.path("export_manifest.tsv"), "\t")
        )

    def path(self, name):
        return os.path.join(self.dir, name)

    def ticks(self, wh):
        return half_up(wh, self.wh_per_tick)

    def region_name(self, code):
        return self.region_of_code.get(code.strip().lower())

    def segment_name(self, code):
        return self.segment_of_code.get(code.strip().lower())

    # ---------------------------------------------------------------- config
    def load_config(self):
        cfg = configparser.ConfigParser()
        with open(self.path("program.ini"), encoding="utf-8") as handle:
            cfg.read_file(handle)
        self.wh_per_tick = cfg.getint("units", "wh_per_tick")
        self.millicents_per_cent = cfg.getint("units", "millicents_per_cent")
        self.region_of_code = dict(cfg["region_codes"])
        self.segment_of_code = dict(cfg["segment_codes"])
        self.region_names = sorted(set(self.region_of_code.values()))
        self.segment_names = sorted(set(self.segment_of_code.values()))
        adders = dict(cfg["segment_rate_adders"]) if cfg.has_section(
            "segment_rate_adders"
        ) else {}
        self.segment_adder = {
            name: int(adders.get(name.lower(), 0)) for name in self.segment_names
        }
        self.claim_cents_per_weight = cfg.getint("grants", "claim_cents_per_weight")
        self.minimum_grant_cents = cfg.getint("grants", "minimum_grant_cents")

    # ---------------------------------------------------------------- events
    def load_events(self):
        with open(self.path("events.json"), encoding="utf-8") as handle:
            raw = json.load(handle)
        self.rows["events.json"] = len(raw)
        self.events = {}
        for entry in raw:
            self.events[entry["event_id"]] = {
                "event_id": entry["event_id"],
                "interval_count": int(entry["interval_count"]),
                "cost_weight": int(entry["objective"]["cost_weight"]),
                "recovery_weight": int(entry["objective"]["recovery_weight"]),
                "uplift": int(entry["uplift_millicents_per_kwh"]),
                "start": datetime.fromisoformat(entry["dispatch_start"]),
            }
        self.event_ids = sorted(self.events)
        # Season order: ascending start instant, events sharing an instant
        # reached in descending event_id (section 2.4).
        self.season_order = sorted(
            sorted(self.event_ids, reverse=True),
            key=lambda event_id: self.events[event_id]["start"],
        )

    # ----------------------------------------------------------------- sites
    def load_sites(self):
        records = read_delimited(self.path("sites.csv"), ",")
        self.rows["sites.csv"] = len(records)
        self.sites = {}
        self.unknown_region_site_rows = 0
        for record in records:
            region = self.region_name(record["region_code"])
            if region is None:
                self.unknown_region_site_rows += 1
                continue
            self.sites[(record["event_id"], record["site_id"])] = {
                "event_id": record["event_id"],
                "site_id": record["site_id"],
                "region": region,
                "segment": self.segment_name(record["segment_code"]),
                "beneficiary_id": record["beneficiary_id"],
                "critical": record["critical"] == "Y",
            }

    # ---------------------------------------------------------------- offers
    def load_offers(self):
        records = read_delimited(self.path("offers.csv"), ",")
        self.rows["offers.csv"] = len(records)
        self.offers = {}
        self.offer_event = {}
        self.orphan_offer_rows = 0
        for record in records:
            self.offer_event[record["offer_id"]] = record["event_id"]
            key = (record["event_id"], record["site_id"])
            if key not in self.sites:
                self.orphan_offer_rows += 1
                continue
            count = self.events[record["event_id"]]["interval_count"]
            self.offers[record["offer_id"]] = {
                "offer_id": record["offer_id"],
                "event_id": record["event_id"],
                "site_id": record["site_id"],
                "bid_cost_cents": int(record["bid_cost_cents"]),
                "relief": [0] * count,
                "recovery": [0] * count,
                "relief_total": 0,
                "recovery_total": 0,
            }

    # -------------------------------------------------------------- profiles
    def load_profiles(self):
        records = read_delimited(self.path("profiles.tsv"), "\t")
        self.rows["profiles.tsv"] = len(records)
        self.orphan_profile_rows = 0
        self.out_of_range_profile_rows = 0
        self.duplicate_profile_rows = 0
        kept = set()
        for record in records:
            offer_id = record["offer_id"]
            event_id = self.offer_event.get(offer_id)
            if event_id is None:
                self.orphan_profile_rows += 1
                continue
            interval = int(record["interval"])
            if interval < 1 or interval > self.events[event_id]["interval_count"]:
                self.out_of_range_profile_rows += 1
                continue
            if (offer_id, interval) in kept:
                self.duplicate_profile_rows += 1
                continue
            kept.add((offer_id, interval))
            offer = self.offers.get(offer_id)
            if offer is None:
                continue
            multiplier = int(record["register_multiplier"])
            relief = self.ticks(int(record["relief_wh"]) * multiplier)
            recovery = self.ticks(int(record["recovery_wh"]) * multiplier)
            offer["relief"][interval - 1] = relief
            offer["recovery"][interval - 1] = recovery
            offer["relief_total"] += relief
            offer["recovery_total"] += recovery

    # --------------------------------------------------------------- targets
    def load_targets(self):
        records = read_delimited(self.path("targets.tsv"), "\t")
        self.rows["targets.tsv"] = len(records)
        self.targets = {}
        for record in records:
            event_id = record["event_id"]
            key = (event_id, self.region_name(record["region_code"]))
            count = self.events[event_id]["interval_count"]
            slot = self.targets.setdefault(key, ([0] * count, [0] * count))
            interval = int(record["interval"])
            slot[0][interval - 1] = self.ticks(int(record["target_wh"]))
            slot[1][interval - 1] = int(record["shortfall_weight"])

    def target_of(self, event_id, region):
        count = self.events[event_id]["interval_count"]
        return self.targets.get((event_id, region), ([0] * count, [0] * count))

    # --------------------------------------------------------- feeder limits
    def load_feeder_limits(self):
        lines = read_record_lines(self.path("feeder_limits.txt"))
        self.rows["feeder_limits.txt"] = len(lines)
        self.ceilings = {}
        for line in lines:
            event_id = line[0:10].strip()
            key = (event_id, self.region_name(line[10:14]))
            count = self.events[event_id]["interval_count"]
            slot = self.ceilings.setdefault(key, ([0] * count, [0] * count))
            interval = int(line[14:17])
            slot[0][interval - 1] = self.ticks(int(line[17:27]))
            slot[1][interval - 1] = self.ticks(int(line[27:37]))

    def ceiling_of(self, event_id, region):
        count = self.events[event_id]["interval_count"]
        return self.ceilings.get((event_id, region), ([0] * count, [0] * count))

    # ----------------------------------------------------------- site state
    def load_state(self):
        with open(self.path("site_state.jsonl"), encoding="utf-8") as handle:
            lines = [line for line in handle.read().splitlines() if line.strip()]
        self.rows["site_state.jsonl"] = len(lines)
        self.state = {}
        for line in lines:
            entry = json.loads(line)
            key = (entry["event_id"], entry["site_id"])
            if key in self.sites:
                self.state[key] = entry

    # -------------------------------------------------------------- waivers
    def load_waivers(self):
        records = read_delimited(self.path("continuity_waivers.csv"), ",")
        self.rows["continuity_waivers.csv"] = len(records)
        self.waiver_signed_missing = 0
        self.waivers = {}
        for record in records:
            if record["waiver_signed"].strip() == "":
                self.waiver_signed_missing += 1
            key = (record["event_id"], record["site_id"])
            if key in self.sites:
                self.waivers[key] = record

    # ---------------------------------------------------------------- floors
    def load_floors(self):
        with open(self.path("segment_floors.json"), encoding="utf-8") as handle:
            entries = json.load(handle)["floors"]
        self.rows["segment_floors.json"] = len(entries)
        self.floors = {}
        for entry in entries:
            key = (
                entry["event_id"],
                self.region_name(entry["region_code"]),
                self.segment_name(entry["segment_code"]),
            )
            self.floors[key] = (
                self.ticks(int(entry["floor_wh"])),
                int(entry["priority_weight"]),
            )

    def floor_of(self, event_id, region, segment):
        return self.floors.get((event_id, region, segment), (0, 0))

    # ------------------------------------------------------------ rate cards
    def load_rate_cards(self):
        cards = ET.parse(self.path("rate_cards.xml")).getroot().findall("card")
        self.rows["rate_cards.xml"] = len(cards)
        self.cards = {}
        for card in cards:
            key = (card.get("event"), card.get("site"))
            if key not in self.sites:
                continue
            override = card.find("override")
            start = card.find("base") if override is None else override
            self.cards[key] = (int(start.text), int(card.find("cap").text))

    # --------------------------------------------------------------- weights
    def load_weights(self):
        records = read_delimited(self.path("recipient_weights.tsv"), "\t")
        self.rows["recipient_weights.tsv"] = len(records)
        self.grant_weights = {}
        for record in records:
            key = (record["event_id"], record["site_id"])
            if key in self.sites:
                self.grant_weights[key] = int(record["grant_weight"])

    # ----------------------------------------------------------------- pools
    def load_pools(self):
        lines = read_record_lines(self.path("pools.txt"))
        self.rows["pools.txt"] = len(lines)
        self.pools = {}
        for line in lines:
            key = (line[0:10].strip(), self.region_name(line[10:14]))
            self.pools[key] = int(line[14:26])

    # ------------------------------------------------------------ allowances
    def load_allowances(self):
        records = read_commented_delimited(self.path("site_allowances.tsv"), "\t")
        self.rows["site_allowances.tsv"] = len(records)
        self.allowance_ticks = {}
        draws_from = {}
        for record in records:
            site_id = record["site_id"]
            self.allowance_ticks[site_id] = int(record["allowance_ticks"])
            draws_from[site_id] = (record.get("draws_from") or "").strip()
        self.allowance_root = {}
        for site_id in self.allowance_ticks:
            chain = [site_id]
            current = site_id
            while draws_from.get(current):
                current = draws_from[current]
                chain.append(current)
            for node in chain:
                self.allowance_root[node] = current

    def root_of(self, site_id):
        return self.allowance_root.get(site_id, site_id)


def compliance_label(extract, key, site):
    state = extract.state.get(key)
    if state is not None:
        if state["safety_hold"]:
            return "SAFETY_HOLD"
        if state["cooldown"]:
            return "COOLDOWN"
    waiver = extract.waivers.get(key)
    if waiver is None or waiver["routine_certificate_pending"] != "Y":
        return "CLEAR"
    waiver_valid = (
        waiver["waiver_status"] == "VALID"
        and waiver["waiver_signed"] == "Y"
        and site["critical"]
        and site["segment"] == "public"
    )
    return "CONTINUITY_WAIVED" if waiver_valid else "CERTIFICATE_PENDING"


def choose_portfolio(groups, targets, ceilings, floors, objective, interval_count):
    """Pick the best feasible portfolio by section 5.

    groups holds one list of (offer, segment index) pairs per site with
    candidate offers. Returns (selected offer ids sorted, tied portfolio count).
    """
    target_ticks, shortfall_weight = targets
    relief_ceiling, recovery_ceiling = ceilings
    cost_weight, recovery_weight = objective
    segment_count = len(floors)
    relief = [0] * interval_count
    recovery = [0] * interval_count
    segment_relief = [0] * segment_count
    chosen = []
    best_key = None
    best_ids = ()
    tied = 0

    def evaluate(bid_cost):
        nonlocal best_key, best_ids, tied
        weighted_shortfall = 0
        overdelivery = 0
        recovery_sum = 0
        for index in range(interval_count):
            gap = target_ticks[index] - relief[index]
            if gap > 0:
                weighted_shortfall += shortfall_weight[index] * gap
            elif gap < 0:
                overdelivery -= gap
            recovery_sum += recovery[index]
        floor_deficit = 0
        for index in range(segment_count):
            floor_ticks, priority_weight = floors[index]
            deficit = floor_ticks - segment_relief[index]
            if deficit > 0:
                floor_deficit += priority_weight * deficit
        key = (
            weighted_shortfall,
            floor_deficit,
            cost_weight * bid_cost + recovery_weight * recovery_sum,
            overdelivery,
            len(chosen),
        )
        if best_key is None or key < best_key:
            best_key = key
            best_ids = tuple(sorted(chosen))
            tied = 1
        elif key == best_key:
            tied += 1
            ids = tuple(sorted(chosen))
            if ids > best_ids:
                best_ids = ids

    def recurse(index, bid_cost):
        if index == len(groups):
            evaluate(bid_cost)
            return
        recurse(index + 1, bid_cost)
        for offer, segment_index in groups[index]:
            offer_relief = offer["relief"]
            offer_recovery = offer["recovery"]
            feasible = True
            for slot in range(interval_count):
                relief[slot] += offer_relief[slot]
                recovery[slot] += offer_recovery[slot]
                if (
                    relief[slot] > relief_ceiling[slot]
                    or recovery[slot] > recovery_ceiling[slot]
                ):
                    feasible = False
            if feasible:
                segment_relief[segment_index] += offer["relief_total"]
                chosen.append(offer["offer_id"])
                recurse(index + 1, bid_cost + offer["bid_cost_cents"])
                chosen.pop()
                segment_relief[segment_index] -= offer["relief_total"]
            for slot in range(interval_count):
                relief[slot] -= offer_relief[slot]
                recovery[slot] -= offer_recovery[slot]

    recurse(0, 0)
    return list(best_ids), tied


def largest_remainder(funded, weights):
    """Share funded cents in proportion to weights; returns shares, leftover, tie."""
    total = sum(weights.values())
    shares = {}
    remainders = {}
    for beneficiary, weight in weights.items():
        product = funded * weight
        shares[beneficiary] = product // total
        remainders[beneficiary] = product % total
    leftover = funded - sum(shares.values())
    order = sorted(weights, reverse=True)
    order.sort(key=lambda beneficiary: -remainders[beneficiary])
    for beneficiary in order[:leftover]:
        shares[beneficiary] += 1
    seen = defaultdict(int)
    for remainder in remainders.values():
        if remainder:
            seen[remainder] += 1
    return shares, leftover, any(count >= 2 for count in seen.values())


def apportion(funded, weights, claim_per_weight, minimum):
    """Section 7: returns shares, allocated, unallocated, residual, residual tie."""
    positive = {
        beneficiary: weight for beneficiary, weight in weights.items() if weight > 0
    }
    if not positive:
        return {}, 0, funded, 0, False
    claims = {
        beneficiary: weight * claim_per_weight
        for beneficiary, weight in positive.items()
    }
    if sum(claims.values()) <= funded:
        allocated = sum(claims.values())
        return claims, allocated, funded - allocated, 0, False
    shares, residual, tie = largest_remainder(funded, positive)
    below = [
        beneficiary for beneficiary, cents in shares.items() if cents < minimum
    ]
    if len(below) == len(positive):
        return {beneficiary: 0 for beneficiary in positive}, 0, funded, 0, False
    if below:
        keep = {
            beneficiary: weight
            for beneficiary, weight in positive.items()
            if beneficiary not in below
        }
        shares, residual, tie = largest_remainder(funded, keep)
        for beneficiary in below:
            shares[beneficiary] = 0
    allocated = sum(shares.values())
    return shares, allocated, funded - allocated, residual, tie


def derive(extract):
    """Work the season through in season order; returns per event-region results."""
    credit_denominator = 1000 * extract.millicents_per_cent

    site_rows = defaultdict(list)
    for key in sorted(extract.sites):
        site = extract.sites[key]
        site_rows[(site["event_id"], site["region"])].append(key)

    labels = {key: compliance_label(extract, key, extract.sites[key]) for key in extract.sites}

    effective_rate = {}
    cap_binding = {}
    for key, site in extract.sites.items():
        card = extract.cards.get(key)
        if card is None:
            continue
        rate, cap = card
        rate += extract.segment_adder.get(site["segment"], 0)
        rate += extract.events[site["event_id"]]["uplift"]
        effective_rate[key] = min(rate, cap)
        cap_binding[key] = rate > cap

    offers_of_site_row = defaultdict(list)
    for offer_id in sorted(extract.offers):
        offer = extract.offers[offer_id]
        offers_of_site_row[(offer["event_id"], offer["site_id"])].append(offer)

    segment_index = {name: index for index, name in enumerate(extract.segment_names)}

    audit = {
        "cap_binding_count": 0,
        "residual_cents": 0,
        "residual_tie_pool_count": 0,
    }
    quality = {
        "ineligible_offer_count": 0,
        "allowance_blocked_offer_count": 0,
        "empty_candidate_groups": 0,
        "unallocated_pool_count": 0,
    }
    tie_decisions = []
    drawn = defaultdict(int)
    carried = defaultdict(int)
    results = {}

    for event_id in extract.season_order:
        event = extract.events[event_id]
        interval_count = event["interval_count"]

        # Candidate offers of the whole event, before any of its own draws.
        candidates = {region: defaultdict(list) for region in extract.region_names}
        for region in extract.region_names:
            for key in site_rows[(event_id, region)]:
                site = extract.sites[key]
                state = extract.state.get(key)
                can_dispatch = state is not None and state["dispatch_authorized"]
                root = extract.root_of(site["site_id"])
                remaining = extract.allowance_ticks.get(root, 0) - drawn[root]
                for offer in offers_of_site_row[key]:
                    if not can_dispatch:
                        quality["ineligible_offer_count"] += 1
                    elif offer["relief_total"] > remaining:
                        quality["allowance_blocked_offer_count"] += 1
                    else:
                        candidates[region][site["site_id"]].append(offer)

        for region in extract.region_names:
            groups = []
            candidate_offer_count = 0
            for site_id in sorted(candidates[region]):
                offers = candidates[region][site_id]
                segment = extract.sites[(event_id, site_id)]["segment"]
                groups.append([(offer, segment_index[segment]) for offer in offers])
                candidate_offer_count += len(offers)
            if candidate_offer_count == 0:
                quality["empty_candidate_groups"] += 1

            targets = extract.target_of(event_id, region)
            floors = [
                extract.floor_of(event_id, region, segment)
                for segment in extract.segment_names
            ]
            selected_ids, tied = choose_portfolio(
                groups,
                targets,
                extract.ceiling_of(event_id, region),
                floors,
                (event["cost_weight"], event["recovery_weight"]),
                interval_count,
            )
            if tied >= 2:
                tie_decisions.append(
                    {
                        "event_id": event_id,
                        "region": region,
                        "tied_portfolio_count": tied,
                        "selected_offer_ids": list(selected_ids),
                    }
                )

            relief = [0] * interval_count
            recovery = [0] * interval_count
            bid_cost_cents = 0
            credit_cents = 0
            offer_credits = {}
            for offer_id in selected_ids:
                offer = extract.offers[offer_id]
                key = (offer["event_id"], offer["site_id"])
                bid_cost_cents += offer["bid_cost_cents"]
                rate = effective_rate.get(key, 0)
                credit = 0
                for slot in range(interval_count):
                    relief[slot] += offer["relief"][slot]
                    recovery[slot] += offer["recovery"][slot]
                    credited = offer["relief"][slot] - offer["recovery"][slot]
                    if credited > 0:
                        credit += half_even(
                            credited * extract.wh_per_tick * rate, credit_denominator
                        )
                offer_credits[offer_id] = credit
                credit_cents += credit
                if cap_binding.get(key):
                    audit["cap_binding_count"] += 1
                drawn[extract.root_of(offer["site_id"])] += offer["relief_total"]

            pool_cents = extract.pools.get((event_id, region), 0)
            funded_cents = max(0, pool_cents + carried[region] - credit_cents)
            weights = defaultdict(int)
            recipients = 0
            for key in site_rows[(event_id, region)]:
                if key not in extract.grant_weights:
                    continue
                recipients += 1
                weight = extract.grant_weights[key]
                if labels[key] == "CONTINUITY_WAIVED":
                    weight *= 2
                weights[extract.sites[key]["beneficiary_id"]] += weight
            shares, allocated, unallocated, residual, tie = apportion(
                funded_cents,
                dict(weights),
                extract.claim_cents_per_weight,
                extract.minimum_grant_cents,
            )
            if recipients == 0 or sum(weights.values()) == 0:
                quality["unallocated_pool_count"] += 1
            audit["residual_cents"] += residual
            if tie:
                audit["residual_tie_pool_count"] += 1
            carried[region] = unallocated

            counts = {label: 0 for label in LABELS}
            for key in site_rows[(event_id, region)]:
                counts[labels[key]] += 1

            results[(event_id, region)] = {
                "candidate_offer_count": candidate_offer_count,
                "selected_ids": list(selected_ids),
                "offer_credits": offer_credits,
                "relief": relief,
                "recovery": recovery,
                "targets": targets[0],
                "bid_cost_cents": bid_cost_cents,
                "credit_cents": credit_cents,
                "grant_pool_cents": pool_cents,
                "grant_funded_cents": funded_cents,
                "grant_allocated_cents": allocated,
                "grant_unallocated_cents": unallocated,
                "grants": shares,
                "compliance_counts": counts,
            }

    # The season runs in dispatch order; the report wants event_id then region.
    tie_decisions.sort(key=lambda entry: (entry["event_id"], entry["region"]))
    return results, labels, tie_decisions, audit, quality


def dump(path, document):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, sort_keys=True, indent=1)
        handle.write("\n")


def region_document(extract, results, region):
    events = []
    totals = {key: 0 for key in REGION_TOTAL_KEYS}
    for event_id in extract.event_ids:
        result = results[(event_id, region)]
        intervals = []
        for slot in range(extract.events[event_id]["interval_count"]):
            target = result["targets"][slot]
            relief = result["relief"][slot]
            intervals.append(
                {
                    "interval": slot + 1,
                    "target_ticks": target,
                    "relief_ticks": relief,
                    "recovery_ticks": result["recovery"][slot],
                    "shortfall_ticks": max(0, target - relief),
                    "overdelivery_ticks": max(0, relief - target),
                }
            )
        events.append(
            {
                "event_id": event_id,
                "candidate_offer_count": result["candidate_offer_count"],
                "selected_offer_ids": result["selected_ids"],
                "intervals": intervals,
                "bid_cost_cents": result["bid_cost_cents"],
                "credit_cents": result["credit_cents"],
                "grant_pool_cents": result["grant_pool_cents"],
                "grant_funded_cents": result["grant_funded_cents"],
                "grant_allocated_cents": result["grant_allocated_cents"],
                "grant_unallocated_cents": result["grant_unallocated_cents"],
                "grants": [
                    {"beneficiary_id": beneficiary, "cents": cents}
                    for beneficiary, cents in sorted(result["grants"].items())
                ],
                "compliance_counts": result["compliance_counts"],
            }
        )
        totals["event_count"] += 1
        totals["candidate_offer_count"] += result["candidate_offer_count"]
        totals["selected_offer_count"] += len(result["selected_ids"])
        totals["relief_ticks"] += sum(result["relief"])
        totals["recovery_ticks"] += sum(result["recovery"])
        totals["shortfall_ticks"] += sum(item["shortfall_ticks"] for item in intervals)
        totals["overdelivery_ticks"] += sum(
            item["overdelivery_ticks"] for item in intervals
        )
        for key in (
            "bid_cost_cents",
            "credit_cents",
            "grant_pool_cents",
            "grant_funded_cents",
            "grant_allocated_cents",
            "grant_unallocated_cents",
        ):
            totals[key] += result[key]
    return {"region": region, "events": events, "totals": totals}


def segment_document(extract, results, segment):
    entries = []
    totals = {key: 0 for key in SEGMENT_TOTAL_KEYS}
    for event_id in extract.event_ids:
        for region in extract.region_names:
            result = results[(event_id, region)]
            offer_ids = []
            relief_ticks = 0
            recovery_ticks = 0
            bid_cost_cents = 0
            credit_cents = 0
            for offer_id in result["selected_ids"]:
                offer = extract.offers[offer_id]
                site = extract.sites[(offer["event_id"], offer["site_id"])]
                if site["segment"] != segment:
                    continue
                offer_ids.append(offer_id)
                relief_ticks += offer["relief_total"]
                recovery_ticks += offer["recovery_total"]
                bid_cost_cents += offer["bid_cost_cents"]
                credit_cents += result["offer_credits"][offer_id]
            floor_ticks = extract.floor_of(event_id, region, segment)[0]
            if floor_ticks == 0:
                attainment = 10000
            else:
                attainment = min(10000, half_up(10000 * relief_ticks, floor_ticks))
            entries.append(
                {
                    "event_id": event_id,
                    "region": region,
                    "selected_offer_ids": sorted(offer_ids),
                    "relief_ticks": relief_ticks,
                    "recovery_ticks": recovery_ticks,
                    "bid_cost_cents": bid_cost_cents,
                    "credit_cents": credit_cents,
                    "floor_ticks": floor_ticks,
                    "floor_attainment_bp": attainment,
                }
            )
            totals["selected_offer_count"] += len(offer_ids)
            totals["relief_ticks"] += relief_ticks
            totals["recovery_ticks"] += recovery_ticks
            totals["bid_cost_cents"] += bid_cost_cents
            totals["credit_cents"] += credit_cents
            totals["floor_ticks"] += floor_ticks
    return {"segment": segment, "event_regions": entries, "totals": totals}


def write_outputs(extract, out_dir, results, labels, tie_decisions, audit, quality):
    os.makedirs(out_dir, exist_ok=True)

    region_docs = {}
    for region in extract.region_names:
        region_docs[region] = region_document(extract, results, region)
        dump(os.path.join(out_dir, "region_%s.json" % region), region_docs[region])

    segment_docs = {}
    for segment in extract.segment_names:
        segment_docs[segment] = segment_document(extract, results, segment)
        dump(os.path.join(out_dir, "segment_%s.json" % segment), segment_docs[segment])

    summary = {
        "event_count": len(extract.event_ids),
        "event_region_count": len(extract.event_ids) * len(extract.region_names),
        "site_count": len(extract.sites),
    }
    for key in REGION_TOTAL_KEYS:
        if key == "event_count":
            continue
        summary[key] = sum(doc["totals"][key] for doc in region_docs.values())
    summary["regions"] = {
        region: {
            key: doc["totals"][key]
            for key in (
                "selected_offer_count",
                "relief_ticks",
                "bid_cost_cents",
                "credit_cents",
                "grant_allocated_cents",
            )
        }
        for region, doc in region_docs.items()
    }
    summary["segments"] = {
        segment: {
            key: doc["totals"][key]
            for key in (
                "selected_offer_count",
                "relief_ticks",
                "bid_cost_cents",
                "credit_cents",
            )
        }
        for segment, doc in segment_docs.items()
    }
    dump(os.path.join(out_dir, "summary.json"), summary)

    counts = {label: 0 for label in LABELS}
    for label in labels.values():
        counts[label] += 1
    dump(
        os.path.join(out_dir, "policy_audit.json"),
        {
            "compliance_counts": counts,
            "site_labels": [
                {"event_id": key[0], "site_id": key[1], "label": labels[key]}
                for key in sorted(labels)
            ],
            "tie_decisions": tie_decisions,
            "cap_binding_count": audit["cap_binding_count"],
            "residual_cents": audit["residual_cents"],
            "residual_tie_pool_count": audit["residual_tie_pool_count"],
        },
    )

    document = dict(quality)
    document["rows"] = dict(extract.rows)
    document["orphan_offer_rows"] = extract.orphan_offer_rows
    document["orphan_profile_rows"] = extract.orphan_profile_rows
    document["out_of_range_profile_rows"] = extract.out_of_range_profile_rows
    document["duplicate_profile_rows"] = extract.duplicate_profile_rows
    document["unknown_region_site_rows"] = extract.unknown_region_site_rows
    document["waiver_signed_missing"] = extract.waiver_signed_missing
    document["zero_floor_count"] = sum(
        1
        for event_id in extract.event_ids
        for region in extract.region_names
        for segment in extract.segment_names
        if extract.floor_of(event_id, region, segment)[0] == 0
    )
    dump(os.path.join(out_dir, "data_quality.json"), document)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    extract = Extract(argv[1])
    results, labels, tie_decisions, audit, quality = derive(extract)
    write_outputs(extract, argv[2], results, labels, tie_decisions, audit, quality)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
