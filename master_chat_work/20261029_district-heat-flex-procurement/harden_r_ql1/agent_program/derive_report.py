#!/usr/bin/env python3
"""Derive the district-heat flexibility programme reports from a season extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import configparser
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

LABELS = ["SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR"]


def round_half_up(num, den):
    return (2 * num + den) // (2 * den)


def round_half_even(num, den):
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2):
        q += 1
    return q


def read_rows(path, delimiter):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def non_comment_lines(path):
    with open(path, encoding="utf-8") as fh:
        return [line.rstrip("\n") for line in fh if not line.startswith("#")]


class NegStr:
    """Sort helper giving descending string order inside an ascending sort key."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value > other.value

    def __eq__(self, other):
        return self.value == other.value


class Extract:
    def __init__(self, data_dir):
        self.dir = data_dir
        self.load_program()
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
        self.load_manifest()

    def path(self, name):
        return os.path.join(self.dir, name)

    def ticks(self, wh):
        return round_half_up(wh, self.wh_per_tick)

    def load_program(self):
        cp = configparser.ConfigParser()
        with open(self.path("program.ini"), encoding="utf-8") as fh:
            cp.read_file(fh)
        self.wh_per_tick = int(cp["units"]["wh_per_tick"])
        self.millicents_per_cent = int(cp["units"]["millicents_per_cent"])
        self.region_of_code = {k.upper(): v for k, v in cp["region_codes"].items()}
        self.segment_of_code = {k.upper(): v for k, v in cp["segment_codes"].items()}
        self.region_names = sorted(set(self.region_of_code.values()))
        self.segment_names = sorted(set(self.segment_of_code.values()))
        self.segment_adder = {name: 0 for name in self.segment_names}
        if cp.has_section("segment_rate_adders"):
            by_lower = {name.lower(): name for name in self.segment_names}
            for key, value in cp["segment_rate_adders"].items():
                name = by_lower.get(key.lower())
                if name is not None:
                    self.segment_adder[name] = int(value)
        self.claim_cents_per_weight = int(cp["grants"]["claim_cents_per_weight"])
        self.minimum_grant_cents = int(cp["grants"]["minimum_grant_cents"])

    def load_events(self):
        with open(self.path("events.json"), encoding="utf-8") as fh:
            events = json.load(fh)
        self.event_rows = len(events)
        self.events = {}
        for ev in events:
            self.events[ev["event_id"]] = {
                "event_id": ev["event_id"],
                "interval_count": int(ev["interval_count"]),
                "cost_weight": int(ev["objective"]["cost_weight"]),
                "recovery_weight": int(ev["objective"]["recovery_weight"]),
                "uplift": int(ev["uplift_millicents_per_kwh"]),
                "start": datetime.fromisoformat(ev["dispatch_start"]),
            }
        self.event_ids_sorted = sorted(self.events)
        self.season_order = sorted(
            self.events.values(), key=lambda e: (e["start"], NegStr(e["event_id"]))
        )

    def load_sites(self):
        rows = read_rows(self.path("sites.csv"), ",")
        self.sites_rows = len(rows)
        self.unknown_region_site_rows = 0
        self.site_rows = {}
        for row in rows:
            region = self.region_of_code.get(row["region_code"])
            if region is None:
                self.unknown_region_site_rows += 1
                continue
            self.site_rows[(row["event_id"], row["site_id"])] = {
                "event_id": row["event_id"],
                "site_id": row["site_id"],
                "region": region,
                "segment": self.segment_of_code[row["segment_code"]],
                "beneficiary_id": row["beneficiary_id"],
                "critical": row["critical"] == "Y",
            }

    def load_offers(self):
        rows = read_rows(self.path("offers.csv"), ",")
        self.offers_rows = len(rows)
        self.orphan_offer_rows = 0
        self.offers = {}
        self.offer_events = {}
        for row in rows:
            self.offer_events[row["offer_id"]] = row["event_id"]
            site = self.site_rows.get((row["event_id"], row["site_id"]))
            if site is None:
                self.orphan_offer_rows += 1
                continue
            self.offers[row["offer_id"]] = {
                "offer_id": row["offer_id"],
                "event_id": row["event_id"],
                "site_id": row["site_id"],
                "segment": site["segment"],
                "bid_cost_cents": int(row["bid_cost_cents"]),
            }

    def load_profiles(self):
        self.profiles_rows = 0
        self.orphan_profile_rows = 0
        self.out_of_range_profile_rows = 0
        self.duplicate_profile_rows = 0
        relief = {}
        recovery = {}
        seen = set()
        with open(self.path("profiles.tsv"), encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                self.profiles_rows += 1
                offer_id = row["offer_id"]
                event_id = self.offer_events.get(offer_id)
                if event_id is None:
                    self.orphan_profile_rows += 1
                    continue
                interval = int(row["interval"])
                if interval < 1 or interval > self.events[event_id]["interval_count"]:
                    self.out_of_range_profile_rows += 1
                    continue
                key = (offer_id, interval)
                if key in seen:
                    self.duplicate_profile_rows += 1
                    continue
                seen.add(key)
                if offer_id not in self.offers:
                    continue
                mult = int(row["register_multiplier"])
                relief[key] = self.ticks(int(row["relief_wh"]) * mult)
                recovery[key] = self.ticks(int(row["recovery_wh"]) * mult)
        for offer in self.offers.values():
            offer_id = offer["offer_id"]
            count = self.events[offer["event_id"]]["interval_count"]
            offer["relief"] = [relief.get((offer_id, t), 0) for t in range(1, count + 1)]
            offer["recovery"] = [recovery.get((offer_id, t), 0) for t in range(1, count + 1)]
            offer["total_relief"] = sum(offer["relief"])
            offer["total_recovery"] = sum(offer["recovery"])

    def load_targets(self):
        rows = read_rows(self.path("targets.tsv"), "\t")
        self.targets_rows = len(rows)
        self.targets = {}
        for row in rows:
            region = self.region_of_code[row["region_code"]]
            self.targets[(row["event_id"], region, int(row["interval"]))] = (
                self.ticks(int(row["target_wh"])),
                int(row["shortfall_weight"]),
            )

    def load_feeder_limits(self):
        lines = non_comment_lines(self.path("feeder_limits.txt"))
        self.feeder_rows = len(lines)
        self.ceilings = {}
        for line in lines:
            region = self.region_of_code[line[10:14].strip()]
            key = (line[0:10].strip(), region, int(line[14:17]))
            self.ceilings[key] = (self.ticks(int(line[17:27])), self.ticks(int(line[27:37])))

    def load_state(self):
        self.state_rows = 0
        self.state = {}
        with open(self.path("site_state.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                self.state_rows += 1
                obj = json.loads(line)
                key = (obj["event_id"], obj["site_id"])
                if key in self.site_rows:
                    self.state[key] = obj

    def load_waivers(self):
        rows = read_rows(self.path("continuity_waivers.csv"), ",")
        self.waiver_rows = len(rows)
        self.waiver_signed_missing = 0
        self.waivers = {}
        for row in rows:
            if (row.get("waiver_signed") or "").strip() == "":
                self.waiver_signed_missing += 1
            key = (row["event_id"], row["site_id"])
            if key in self.site_rows:
                self.waivers[key] = row

    def load_floors(self):
        with open(self.path("segment_floors.json"), encoding="utf-8") as fh:
            entries = json.load(fh)["floors"]
        self.floor_rows = len(entries)
        self.floors = {}
        for entry in entries:
            key = (
                entry["event_id"],
                self.region_of_code[entry["region_code"]],
                self.segment_of_code[entry["segment_code"]],
            )
            self.floors[key] = (self.ticks(int(entry["floor_wh"])), int(entry["priority_weight"]))

    def load_rate_cards(self):
        cards = ET.parse(self.path("rate_cards.xml")).getroot().findall("card")
        self.card_rows = len(cards)
        self.cards = {}
        for card in cards:
            key = (card.get("event"), card.get("site"))
            if key not in self.site_rows:
                continue
            override = card.find("override")
            source = override if override is not None else card.find("base")
            self.cards[key] = (int(source.text), int(card.find("cap").text))

    def load_weights(self):
        rows = read_rows(self.path("recipient_weights.tsv"), "\t")
        self.weight_rows = len(rows)
        self.grant_weights = {}
        for row in rows:
            key = (row["event_id"], row["site_id"])
            if key in self.site_rows:
                self.grant_weights[key] = int(row["grant_weight"])

    def load_pools(self):
        lines = non_comment_lines(self.path("pools.txt"))
        self.pool_rows = len(lines)
        self.pools = {}
        for line in lines:
            region = self.region_of_code[line[10:14].strip()]
            self.pools[(line[0:10].strip(), region)] = int(line[14:26])

    def load_allowances(self):
        lines = non_comment_lines(self.path("site_allowances.tsv"))
        self.allowance_rows = max(0, len(lines) - 1)
        self.allowance_ticks = {}
        draws_from = {}
        for line in lines[1:]:
            fields = line.split("\t")
            self.allowance_ticks[fields[0]] = int(fields[1])
            draws_from[fields[0]] = fields[2].strip() if len(fields) > 2 else ""
        self.allowance_root = {}
        for site_id in self.allowance_ticks:
            node = site_id
            while draws_from.get(node):
                node = draws_from[node]
            self.allowance_root[site_id] = node

    def load_manifest(self):
        self.manifest_rows = max(0, len(non_comment_lines(self.path("export_manifest.tsv"))) - 1)

    def compliance_label(self, key):
        state = self.state.get(key, {})
        if state.get("safety_hold"):
            return "SAFETY_HOLD"
        if state.get("cooldown"):
            return "COOLDOWN"
        waiver = self.waivers.get(key, {})
        if waiver.get("routine_certificate_pending") != "Y":
            return "CLEAR"
        site = self.site_rows[key]
        valid = (
            waiver.get("waiver_status") == "VALID"
            and waiver.get("waiver_signed") == "Y"
            and site["critical"]
            and site["segment"] == "public"
        )
        return "CONTINUITY_WAIVED" if valid else "CERTIFICATE_PENDING"

    def rates(self, key):
        """Return (pre-cap rate, effective rate, cap binding) for a site row."""
        start, cap = self.cards[key]
        site = self.site_rows[key]
        pre_cap = start + self.events[site["event_id"]]["uplift"] + self.segment_adder[site["segment"]]
        return pre_cap, min(pre_cap, cap), pre_cap > cap

    def credit_cents(self, offer, rate):
        den = 1000 * self.millicents_per_cent
        total = 0
        for relief, recovery in zip(offer["relief"], offer["recovery"]):
            credited = relief - recovery
            if credited > 0:
                total += round_half_even(credited * self.wh_per_tick * rate, den)
        return total


def solve_portfolio(ex, event, region, site_groups):
    """Return (best portfolio offer ids, number of portfolios tied at the best value)."""
    count = event["interval_count"]
    event_id = event["event_id"]
    targets = []
    weights = []
    relief_cap = []
    recovery_cap = []
    for t in range(1, count + 1):
        target, weight = ex.targets.get((event_id, region, t), (0, 0))
        targets.append(target)
        weights.append(weight)
        rcap, vcap = ex.ceilings.get((event_id, region, t), (0, 0))
        relief_cap.append(rcap)
        recovery_cap.append(vcap)
    floors = []
    for segment in ex.segment_names:
        floor, priority = ex.floors.get((event_id, region, segment), (0, 0))
        if floor > 0 and priority > 0:
            floors.append((segment, floor, priority))
    cost_w = event["cost_weight"]
    rec_w = event["recovery_weight"]

    group_offers = [offers for _, offers in sorted(site_groups.items())]
    n = len(group_offers)
    relief = [0] * count
    recovery = [0] * count
    seg_relief = {segment: 0 for segment in ex.segment_names}
    chosen = []
    best_key = None
    best_ids = None
    tied = 0

    def leaf(cost):
        nonlocal best_key, best_ids, tied
        shortfall = 0
        over = 0
        recovery_total = 0
        for t in range(count):
            diff = targets[t] - relief[t]
            if diff > 0:
                shortfall += weights[t] * diff
            else:
                over -= diff
            recovery_total += recovery[t]
        deficit = 0
        for segment, floor, priority in floors:
            gap = floor - seg_relief[segment]
            if gap > 0:
                deficit += priority * gap
        key = (shortfall, deficit, cost_w * cost + rec_w * recovery_total, over, len(chosen))
        if best_key is None or key < best_key:
            best_key = key
            best_ids = tuple(sorted(chosen))
            tied = 1
        elif key == best_key:
            tied += 1
            ids = tuple(sorted(chosen))
            if ids > best_ids:
                best_ids = ids

    def walk(index, cost):
        if index == n:
            leaf(cost)
            return
        walk(index + 1, cost)
        for offer in group_offers[index]:
            orelief = offer["relief"]
            orecovery = offer["recovery"]
            feasible = True
            for t in range(count):
                if (
                    relief[t] + orelief[t] > relief_cap[t]
                    or recovery[t] + orecovery[t] > recovery_cap[t]
                ):
                    feasible = False
                    break
            if not feasible:
                continue
            for t in range(count):
                relief[t] += orelief[t]
                recovery[t] += orecovery[t]
            seg_relief[offer["segment"]] += offer["total_relief"]
            chosen.append(offer["offer_id"])
            walk(index + 1, cost + offer["bid_cost_cents"])
            chosen.pop()
            seg_relief[offer["segment"]] -= offer["total_relief"]
            for t in range(count):
                relief[t] -= orelief[t]
                recovery[t] -= orecovery[t]

    walk(0, 0)
    return best_ids, tied


def largest_remainder(funded, weights):
    """Share `funded` cents by largest remainder. Returns (shares, residual, tie)."""
    total_weight = sum(weights.values())
    shares = {}
    remainders = {}
    for beneficiary, weight in weights.items():
        shares[beneficiary], remainders[beneficiary] = divmod(funded * weight, total_weight)
    leftover = funded - sum(shares.values())
    order = sorted(remainders, key=lambda b: (remainders[b], b), reverse=True)
    for beneficiary in order[:leftover]:
        shares[beneficiary] += 1
    seen = set()
    tie = False
    for value in remainders.values():
        if value:
            if value in seen:
                tie = True
                break
            seen.add(value)
    return shares, leftover, tie


def apportion(ex, funded, weights):
    """Share a funded pool among beneficiaries. Returns (shares, residual cents, tie)."""
    positive = {b: w for b, w in weights.items() if w > 0}
    if not positive:
        return {}, 0, False
    claims = {b: w * ex.claim_cents_per_weight for b, w in positive.items()}
    if sum(claims.values()) <= funded:
        return claims, 0, False
    shares, residual, tie = largest_remainder(funded, positive)
    kept = {b: w for b, w in positive.items() if shares[b] >= ex.minimum_grant_cents}
    if not kept:
        return {b: 0 for b in positive}, 0, False
    if len(kept) == len(positive):
        return shares, residual, tie
    second, residual, tie = largest_remainder(funded, kept)
    return {b: second.get(b, 0) for b in positive}, residual, tie


def run(ex):
    labels = {key: ex.compliance_label(key) for key in ex.site_rows}

    offers_by_event = {}
    for offer in ex.offers.values():
        offers_by_event.setdefault(offer["event_id"], []).append(offer)
    site_rows_by_event_region = {}
    for key, site in ex.site_rows.items():
        site_rows_by_event_region.setdefault((site["event_id"], site["region"]), []).append(key)

    stats = {
        "ineligible_offer_count": 0,
        "allowance_blocked_offer_count": 0,
        "empty_candidate_groups": 0,
        "cap_binding_count": 0,
        "residual_cents": 0,
        "residual_tie_pool_count": 0,
        "unallocated_pool_count": 0,
    }
    consumed = {}
    carried = {region: 0 for region in ex.region_names}
    results = {}
    tie_decisions = []

    for event in ex.season_order:
        event_id = event["event_id"]
        count = event["interval_count"]
        candidates = {}
        for offer in offers_by_event.get(event_id, []):
            key = (event_id, offer["site_id"])
            if not ex.state.get(key, {}).get("dispatch_authorized"):
                stats["ineligible_offer_count"] += 1
                continue
            root = ex.allowance_root[offer["site_id"]]
            if offer["total_relief"] > ex.allowance_ticks[root] - consumed.get(root, 0):
                stats["allowance_blocked_offer_count"] += 1
                continue
            region = ex.site_rows[key]["region"]
            candidates.setdefault(region, {}).setdefault(offer["site_id"], []).append(offer)

        for region in ex.region_names:
            site_groups = candidates.get(region, {})
            candidate_count = sum(len(group) for group in site_groups.values())
            if candidate_count == 0:
                stats["empty_candidate_groups"] += 1
            selected_ids, tied = solve_portfolio(ex, event, region, site_groups)
            if tied >= 2:
                tie_decisions.append(
                    {
                        "event_id": event_id,
                        "region": region,
                        "tied_portfolio_count": tied,
                        "selected_offer_ids": list(selected_ids),
                    }
                )

            relief = [0] * count
            recovery = [0] * count
            bid_cost = 0
            credits = 0
            offer_credits = {}
            for offer_id in selected_ids:
                offer = ex.offers[offer_id]
                key = (event_id, offer["site_id"])
                _, rate, binding = ex.rates(key)
                if binding:
                    stats["cap_binding_count"] += 1
                offer_credits[offer_id] = ex.credit_cents(offer, rate)
                credits += offer_credits[offer_id]
                bid_cost += offer["bid_cost_cents"]
                for t in range(count):
                    relief[t] += offer["relief"][t]
                    recovery[t] += offer["recovery"][t]
                root = ex.allowance_root[offer["site_id"]]
                consumed[root] = consumed.get(root, 0) + offer["total_relief"]

            intervals = []
            for t in range(count):
                target = ex.targets.get((event_id, region, t + 1), (0, 0))[0]
                intervals.append(
                    {
                        "interval": t + 1,
                        "target_ticks": target,
                        "relief_ticks": relief[t],
                        "recovery_ticks": recovery[t],
                        "shortfall_ticks": max(0, target - relief[t]),
                        "overdelivery_ticks": max(0, relief[t] - target),
                    }
                )

            pool = ex.pools.get((event_id, region), 0)
            funded = max(0, pool + carried[region] - credits)
            site_keys = site_rows_by_event_region.get((event_id, region), [])
            weights = {}
            recipients = 0
            for key in site_keys:
                if key not in ex.grant_weights:
                    continue
                recipients += 1
                weight = ex.grant_weights[key]
                if labels[key] == "CONTINUITY_WAIVED":
                    weight *= 2
                beneficiary = ex.site_rows[key]["beneficiary_id"]
                weights[beneficiary] = weights.get(beneficiary, 0) + weight
            if recipients == 0 or sum(weights.values()) == 0:
                stats["unallocated_pool_count"] += 1
                shares, residual, tie = {}, 0, False
            else:
                shares, residual, tie = apportion(ex, funded, weights)
            stats["residual_cents"] += residual
            if tie:
                stats["residual_tie_pool_count"] += 1
            allocated = sum(shares.values())
            carried[region] = funded - allocated

            counts = {label: 0 for label in LABELS}
            for key in site_keys:
                counts[labels[key]] += 1

            results[(event_id, region)] = {
                "candidate_offer_count": candidate_count,
                "selected_offer_ids": list(selected_ids),
                "intervals": intervals,
                "bid_cost_cents": bid_cost,
                "credit_cents": credits,
                "grant_pool_cents": pool,
                "grant_funded_cents": funded,
                "grant_allocated_cents": allocated,
                "grant_unallocated_cents": funded - allocated,
                "grants": [{"beneficiary_id": b, "cents": shares[b]} for b in sorted(shares)],
                "compliance_counts": counts,
                "offer_credits": offer_credits,
            }

    return labels, results, stats, tie_decisions


REGION_EVENT_FIELDS = (
    "candidate_offer_count",
    "selected_offer_ids",
    "intervals",
    "bid_cost_cents",
    "credit_cents",
    "grant_pool_cents",
    "grant_funded_cents",
    "grant_allocated_cents",
    "grant_unallocated_cents",
    "grants",
    "compliance_counts",
)

REGION_MONEY_FIELDS = (
    "bid_cost_cents",
    "credit_cents",
    "grant_pool_cents",
    "grant_funded_cents",
    "grant_allocated_cents",
    "grant_unallocated_cents",
)


def region_document(ex, results, region):
    events = []
    totals = dict.fromkeys(
        (
            "event_count",
            "candidate_offer_count",
            "selected_offer_count",
            "relief_ticks",
            "recovery_ticks",
            "shortfall_ticks",
            "overdelivery_ticks",
        )
        + REGION_MONEY_FIELDS,
        0,
    )
    for event_id in ex.event_ids_sorted:
        res = results[(event_id, region)]
        entry = {"event_id": event_id}
        for field in REGION_EVENT_FIELDS:
            entry[field] = res[field]
        events.append(entry)
        totals["event_count"] += 1
        totals["candidate_offer_count"] += res["candidate_offer_count"]
        totals["selected_offer_count"] += len(res["selected_offer_ids"])
        for interval in res["intervals"]:
            for field in (
                "relief_ticks",
                "recovery_ticks",
                "shortfall_ticks",
                "overdelivery_ticks",
            ):
                totals[field] += interval[field]
        for field in REGION_MONEY_FIELDS:
            totals[field] += res[field]
    return {"region": region, "events": events, "totals": totals}


def segment_document(ex, results, segment):
    entries = []
    totals = dict.fromkeys(
        (
            "selected_offer_count",
            "relief_ticks",
            "recovery_ticks",
            "bid_cost_cents",
            "credit_cents",
            "floor_ticks",
        ),
        0,
    )
    for event_id in ex.event_ids_sorted:
        for region in ex.region_names:
            res = results[(event_id, region)]
            offer_ids = []
            relief = 0
            recovery = 0
            bid_cost = 0
            credits = 0
            for offer_id in res["selected_offer_ids"]:
                offer = ex.offers[offer_id]
                if offer["segment"] != segment:
                    continue
                offer_ids.append(offer_id)
                relief += offer["total_relief"]
                recovery += offer["total_recovery"]
                bid_cost += offer["bid_cost_cents"]
                credits += res["offer_credits"][offer_id]
            floor = ex.floors.get((event_id, region, segment), (0, 0))[0]
            attainment = 10000 if floor == 0 else min(10000, round_half_up(10000 * relief, floor))
            entries.append(
                {
                    "event_id": event_id,
                    "region": region,
                    "selected_offer_ids": offer_ids,
                    "relief_ticks": relief,
                    "recovery_ticks": recovery,
                    "bid_cost_cents": bid_cost,
                    "credit_cents": credits,
                    "floor_ticks": floor,
                    "floor_attainment_bp": attainment,
                }
            )
            totals["selected_offer_count"] += len(offer_ids)
            totals["relief_ticks"] += relief
            totals["recovery_ticks"] += recovery
            totals["bid_cost_cents"] += bid_cost
            totals["credit_cents"] += credits
            totals["floor_ticks"] += floor
    return {"segment": segment, "event_regions": entries, "totals": totals}


def summary_document(ex, region_docs, segment_docs):
    summed = (
        "candidate_offer_count",
        "selected_offer_count",
        "relief_ticks",
        "recovery_ticks",
        "shortfall_ticks",
        "overdelivery_ticks",
    ) + REGION_MONEY_FIELDS
    document = dict.fromkeys(summed, 0)
    document["event_count"] = len(ex.events)
    document["event_region_count"] = len(ex.events) * len(ex.region_names)
    document["site_count"] = len(ex.site_rows)
    regions = {}
    for region, doc in region_docs.items():
        totals = doc["totals"]
        for field in summed:
            document[field] += totals[field]
        regions[region] = {
            "selected_offer_count": totals["selected_offer_count"],
            "relief_ticks": totals["relief_ticks"],
            "bid_cost_cents": totals["bid_cost_cents"],
            "credit_cents": totals["credit_cents"],
            "grant_allocated_cents": totals["grant_allocated_cents"],
        }
    segments = {}
    for segment, doc in segment_docs.items():
        totals = doc["totals"]
        segments[segment] = {
            "selected_offer_count": totals["selected_offer_count"],
            "relief_ticks": totals["relief_ticks"],
            "bid_cost_cents": totals["bid_cost_cents"],
            "credit_cents": totals["credit_cents"],
        }
    document["regions"] = regions
    document["segments"] = segments
    return document


def data_quality_document(ex, stats):
    zero_floor = 0
    for event_id in ex.events:
        for region in ex.region_names:
            for segment in ex.segment_names:
                if ex.floors.get((event_id, region, segment), (0, 0))[0] == 0:
                    zero_floor += 1
    return {
        "rows": {
            "events.json": ex.event_rows,
            "sites.csv": ex.sites_rows,
            "offers.csv": ex.offers_rows,
            "profiles.tsv": ex.profiles_rows,
            "targets.tsv": ex.targets_rows,
            "continuity_waivers.csv": ex.waiver_rows,
            "recipient_weights.tsv": ex.weight_rows,
            "site_allowances.tsv": ex.allowance_rows,
            "feeder_limits.txt": ex.feeder_rows,
            "pools.txt": ex.pool_rows,
            "site_state.jsonl": ex.state_rows,
            "segment_floors.json": ex.floor_rows,
            "rate_cards.xml": ex.card_rows,
            "export_manifest.tsv": ex.manifest_rows,
        },
        "orphan_offer_rows": ex.orphan_offer_rows,
        "orphan_profile_rows": ex.orphan_profile_rows,
        "out_of_range_profile_rows": ex.out_of_range_profile_rows,
        "duplicate_profile_rows": ex.duplicate_profile_rows,
        "unknown_region_site_rows": ex.unknown_region_site_rows,
        "waiver_signed_missing": ex.waiver_signed_missing,
        "ineligible_offer_count": stats["ineligible_offer_count"],
        "allowance_blocked_offer_count": stats["allowance_blocked_offer_count"],
        "empty_candidate_groups": stats["empty_candidate_groups"],
        "zero_floor_count": zero_floor,
        "unallocated_pool_count": stats["unallocated_pool_count"],
    }


def policy_audit_document(labels, stats, tie_decisions):
    counts = dict.fromkeys(LABELS, 0)
    site_labels = []
    for key in sorted(labels):
        counts[labels[key]] += 1
        site_labels.append({"event_id": key[0], "site_id": key[1], "label": labels[key]})
    return {
        "compliance_counts": counts,
        "site_labels": site_labels,
        "tie_decisions": sorted(tie_decisions, key=lambda d: (d["event_id"], d["region"])),
        "cap_binding_count": stats["cap_binding_count"],
        "residual_cents": stats["residual_cents"],
        "residual_tie_pool_count": stats["residual_tie_pool_count"],
    }


def write_json(out_dir, name, document):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
        json.dump(document, fh, sort_keys=True, indent=1)
        fh.write("\n")


def main(argv):
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    ex = Extract(data_dir)
    labels, results, stats, tie_decisions = run(ex)

    region_docs = {region: region_document(ex, results, region) for region in ex.region_names}
    segment_docs = {seg: segment_document(ex, results, seg) for seg in ex.segment_names}
    for region, doc in region_docs.items():
        write_json(out_dir, "region_%s.json" % region, doc)
    for segment, doc in segment_docs.items():
        write_json(out_dir, "segment_%s.json" % segment, doc)
    write_json(out_dir, "summary.json", summary_document(ex, region_docs, segment_docs))
    write_json(out_dir, "policy_audit.json", policy_audit_document(labels, stats, tie_decisions))
    write_json(out_dir, "data_quality.json", data_quality_document(ex, stats))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
