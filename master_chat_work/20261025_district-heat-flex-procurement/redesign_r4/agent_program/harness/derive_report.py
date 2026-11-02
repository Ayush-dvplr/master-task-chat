#!/usr/bin/env python3
"""Derive the district-heat flexibility programme reports for one season extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import configparser
import csv
import json
import os
import sys
from collections import defaultdict
from xml.etree import ElementTree

LABELS = ("SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR")

# Per-interval energy vectors are packed into one integer, one field per interval,
# so that adding an offer to a portfolio is a single integer addition.
FIELD = 48
MASK = (1 << FIELD) - 1


def div_half_up(num, den):
    return (2 * num + den) // (2 * den)


def div_half_even(num, den):
    quo, rem = divmod(num, den)
    twice = 2 * rem
    if twice > den or (twice == den and quo & 1):
        quo += 1
    return quo


def pack(values):
    out = 0
    for i, value in enumerate(values):
        out |= value << (i * FIELD)
    return out


def guards(count):
    return pack([1 << (FIELD - 1)] * count)


def unpack(packed, count):
    return [(packed >> (i * FIELD)) & MASK for i in range(count)]


# --------------------------------------------------------------------------- #
# extract                                                                     #
# --------------------------------------------------------------------------- #


class Extract:
    """Everything the rulebook needs from one data directory."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.rows = {}
        self._load_program()
        self._load_events()
        self._load_sites()
        self._load_site_state()
        self._load_waivers()
        self._load_rate_cards()
        self._load_weights()
        self._load_offers()
        self._load_profiles()
        self._load_targets()
        self._load_feeder_limits()
        self._load_floors()
        self._load_pools()
        self._count_manifest()
        self._label_sites()

    def path(self, name):
        return os.path.join(self.dir, name)

    def _text_rows(self, name, delimiter):
        with open(self.path(name), newline="", encoding="utf-8") as handle:
            yield from csv.DictReader(handle, delimiter=delimiter)

    def _fixed_lines(self, name):
        with open(self.path(name), encoding="utf-8") as handle:
            for line in handle:
                line = line.rstrip("\n").rstrip("\r")
                if line.startswith("#") or not line:
                    continue
                yield line

    def _load_program(self):
        parser = configparser.ConfigParser()
        with open(self.path("program.ini"), encoding="utf-8") as handle:
            parser.read_file(handle)
        self.wh_per_tick = parser.getint("units", "wh_per_tick")
        self.millicents_per_cent = parser.getint("units", "millicents_per_cent")
        self.region_of_code = {k.upper(): v for k, v in parser["region_codes"].items()}
        self.segment_of_code = {k.upper(): v for k, v in parser["segment_codes"].items()}
        self.regions = sorted(set(self.region_of_code.values()))
        self.segments = sorted(set(self.segment_of_code.values()))
        adders = {}
        if parser.has_section("segment_rate_adders"):
            adders = {k.lower(): int(v) for k, v in parser["segment_rate_adders"].items()}
        self.rate_adder = {name: adders.get(name.lower(), 0) for name in self.segments}

    def ticks(self, wh):
        return div_half_up(wh, self.wh_per_tick)

    def _load_events(self):
        with open(self.path("events.json"), encoding="utf-8") as handle:
            events = json.load(handle)
        self.rows["events.json"] = len(events)
        self.event_ids = sorted(event["event_id"] for event in events)
        self.interval_count = {e["event_id"]: int(e["interval_count"]) for e in events}
        self.cost_weight = {e["event_id"]: int(e["objective"]["cost_weight"]) for e in events}
        self.recovery_weight = {
            e["event_id"]: int(e["objective"]["recovery_weight"]) for e in events
        }
        self.uplift = {e["event_id"]: int(e["uplift_millicents_per_kwh"]) for e in events}

    def _load_sites(self):
        count = 0
        unknown = 0
        self.sites = {}
        for row in self._text_rows("sites.csv", ","):
            count += 1
            region = self.region_of_code.get(row["region_code"].upper())
            if region is None:
                unknown += 1
                continue
            self.sites[(row["event_id"], row["site_id"])] = {
                "region": region,
                "segment": self.segment_of_code[row["segment_code"].upper()],
                "beneficiary_id": row["beneficiary_id"],
                "critical": row["critical"] == "Y",
            }
        self.rows["sites.csv"] = count
        self.unknown_region_site_rows = unknown

    def _load_site_state(self):
        count = 0
        self.state = {}
        with open(self.path("site_state.jsonl"), encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                count += 1
                record = json.loads(line)
                key = (record["event_id"], record["site_id"])
                if key in self.sites:
                    self.state[key] = record
        self.rows["site_state.jsonl"] = count

    def _load_waivers(self):
        count = 0
        missing = 0
        self.waivers = {}
        for row in self._text_rows("continuity_waivers.csv", ","):
            count += 1
            if not (row.get("waiver_signed") or "").strip():
                missing += 1
            key = (row["event_id"], row["site_id"])
            if key in self.sites:
                self.waivers[key] = row
        self.rows["continuity_waivers.csv"] = count
        self.waiver_signed_missing = missing

    def _load_rate_cards(self):
        root = ElementTree.parse(self.path("rate_cards.xml")).getroot()
        count = 0
        self.cards = {}
        for card in root.findall("card"):
            count += 1
            key = (card.get("event"), card.get("site"))
            if key not in self.sites:
                continue
            override = card.find("override")
            start = card.find("base") if override is None else override
            self.cards[key] = (int(start.text), int(card.find("cap").text))
        self.rows["rate_cards.xml"] = count

    def _load_weights(self):
        count = 0
        self.grant_weight = {}
        for row in self._text_rows("recipient_weights.tsv", "\t"):
            count += 1
            key = (row["event_id"], row["site_id"])
            if key in self.sites:
                self.grant_weight[key] = int(row["grant_weight"])
        self.rows["recipient_weights.tsv"] = count

    def _load_offers(self):
        count = 0
        orphans = 0
        self.offers = {}
        for row in self._text_rows("offers.csv", ","):
            count += 1
            key = (row["event_id"], row["site_id"])
            orphan = key not in self.sites
            orphans += orphan
            self.offers[row["offer_id"]] = {
                "event_id": row["event_id"],
                "site_id": row["site_id"],
                "bid_cost_cents": int(row["bid_cost_cents"]),
                "orphan": orphan,
            }
        self.rows["offers.csv"] = count
        self.orphan_offer_rows = orphans

    def _load_profiles(self):
        count = 0
        orphan = 0
        out_of_range = 0
        duplicate = 0
        self.profile = {}
        for row in self._text_rows("profiles.tsv", "\t"):
            count += 1
            offer_id = row["offer_id"]
            offer = self.offers.get(offer_id)
            if offer is None:
                orphan += 1
                continue
            interval = int(row["interval"])
            if not 1 <= interval <= self.interval_count[offer["event_id"]]:
                out_of_range += 1
                continue
            key = (offer_id, interval)
            if key in self.profile:
                duplicate += 1
                continue
            multiplier = int(row["register_multiplier"])
            self.profile[key] = (
                self.ticks(int(row["relief_wh"]) * multiplier),
                self.ticks(int(row["recovery_wh"]) * multiplier),
            )
        self.rows["profiles.tsv"] = count
        self.orphan_profile_rows = orphan
        self.out_of_range_profile_rows = out_of_range
        self.duplicate_profile_rows = duplicate

    def _load_targets(self):
        count = 0
        self.targets = {}
        for row in self._text_rows("targets.tsv", "\t"):
            count += 1
            key = (
                row["event_id"],
                self.region_of_code[row["region_code"].upper()],
                int(row["interval"]),
            )
            self.targets[key] = (
                self.ticks(int(row["target_wh"])),
                int(row["shortfall_weight"]),
            )
        self.rows["targets.tsv"] = count

    def _load_feeder_limits(self):
        count = 0
        self.ceilings = {}
        for line in self._fixed_lines("feeder_limits.txt"):
            count += 1
            key = (
                line[0:10].strip(),
                self.region_of_code[line[10:14].strip().upper()],
                int(line[14:17]),
            )
            self.ceilings[key] = (
                self.ticks(int(line[17:27])),
                self.ticks(int(line[27:37])),
            )
        self.rows["feeder_limits.txt"] = count

    def _load_floors(self):
        with open(self.path("segment_floors.json"), encoding="utf-8") as handle:
            floors = json.load(handle)["floors"]
        self.rows["segment_floors.json"] = len(floors)
        self.floors = {}
        for entry in floors:
            key = (
                entry["event_id"],
                self.region_of_code[entry["region_code"].upper()],
                self.segment_of_code[entry["segment_code"].upper()],
            )
            self.floors[key] = (
                self.ticks(int(entry["floor_wh"])),
                int(entry["priority_weight"]),
            )

    def _load_pools(self):
        count = 0
        self.pools = {}
        for line in self._fixed_lines("pools.txt"):
            count += 1
            key = (line[0:10].strip(), self.region_of_code[line[10:14].strip().upper()])
            self.pools[key] = int(line[14:26])
        self.rows["pools.txt"] = count

    def _count_manifest(self):
        lines = sum(1 for _ in self._fixed_lines("export_manifest.tsv"))
        self.rows["export_manifest.tsv"] = max(lines - 1, 0)  # the first line is the header

    def floor_of(self, event_id, region, segment):
        return self.floors.get((event_id, region, segment), (0, 0))

    def _label_sites(self):
        self.label = {}
        for key, site in self.sites.items():
            state = self.state[key]
            waiver = self.waivers.get(key, {})
            pending = waiver.get("routine_certificate_pending") == "Y"
            waived = (
                waiver.get("waiver_status") == "VALID"
                and waiver.get("waiver_signed") == "Y"
                and site["critical"]
                and site["segment"].lower() == "public"
            )
            if state["safety_hold"]:
                label = "SAFETY_HOLD"
            elif state["cooldown"]:
                label = "COOLDOWN"
            elif pending and waived:
                label = "CONTINUITY_WAIVED"
            elif pending:
                label = "CERTIFICATE_PENDING"
            else:
                label = "CLEAR"
            self.label[key] = label

    def rates(self, site_key):
        """(rate before cap, effective rate, cap binding)."""
        start, cap = self.cards[site_key]
        site = self.sites[site_key]
        before = start + self.uplift[site_key[0]] + self.rate_adder[site["segment"]]
        return before, min(before, cap), before > cap

    def credit_cents(self, site_key, relief_ticks):
        effective = self.rates(site_key)[1]
        den = 1000 * self.millicents_per_cent
        return sum(
            div_half_even(ticks * self.wh_per_tick * effective, den)
            for ticks in relief_ticks
        )


# --------------------------------------------------------------------------- #
# optimisation                                                                #
# --------------------------------------------------------------------------- #


def choose_portfolio(extract, event_id, region, by_site):
    """Best portfolio of an event-region: (offer ids ascending, portfolios tied at best)."""
    count = extract.interval_count[event_id]
    intervals = range(1, count + 1)
    targets = []
    weights = []
    relief_ceiling = []
    recovery_ceiling = []
    for interval in intervals:
        target, weight = extract.targets[(event_id, region, interval)]
        targets.append(target)
        weights.append(weight)
        ceiling = extract.ceilings[(event_id, region, interval)]
        relief_ceiling.append(ceiling[0])
        recovery_ceiling.append(ceiling[1])

    segments = extract.segments
    seg_count = len(segments)
    seg_index = {name: i for i, name in enumerate(segments)}
    floor_ticks = []
    floor_weight = []
    for name in segments:
        ticks, weight = extract.floor_of(event_id, region, name)
        floor_ticks.append(ticks)
        floor_weight.append(weight)

    guard = guards(count)
    relief_limit = pack(relief_ceiling) + guard
    recovery_limit = pack(recovery_ceiling) + guard

    options = []
    for site_id in sorted(by_site):
        choices = [(0, 0, 0, 0, 0, None)]
        index = seg_index[extract.sites[(event_id, site_id)]["segment"]]
        for offer_id in sorted(by_site[site_id]):
            relief = []
            recovery = []
            for interval in intervals:
                row = extract.profile.get((offer_id, interval), (0, 0))
                relief.append(row[0])
                recovery.append(row[1])
            choices.append(
                (
                    pack(relief),
                    pack(recovery),
                    extract.offers[offer_id]["bid_cost_cents"],
                    sum(recovery),
                    sum(relief) << (index * FIELD),
                    offer_id,
                )
            )
        options.append(choices)

    cost_weight = extract.cost_weight[event_id]
    recovery_weight = extract.recovery_weight[event_id]
    depth_limit = len(options)
    relief_cache = {}
    floor_cache = {}
    best_key = None
    best_tag = None
    best_count = 0

    def evaluate(relief_packed, seg_packed, bid, recovery_total, chosen):
        nonlocal best_key, best_tag, best_count
        cached = relief_cache.get(relief_packed)
        if cached is None:
            weighted = 0
            over = 0
            for i, value in enumerate(unpack(relief_packed, count)):
                gap = targets[i] - value
                if gap > 0:
                    weighted += weights[i] * gap
                else:
                    over -= gap
            cached = (weighted, over)
            relief_cache[relief_packed] = cached
        deficit = floor_cache.get(seg_packed)
        if deficit is None:
            deficit = 0
            for i, value in enumerate(unpack(seg_packed, seg_count)):
                gap = floor_ticks[i] - value
                if gap > 0:
                    deficit += floor_weight[i] * gap
            floor_cache[seg_packed] = deficit
        key = (
            cached[0],
            deficit,
            cost_weight * bid + recovery_weight * recovery_total,
            cached[1],
            len(chosen),
        )
        if best_key is None or key < best_key:
            best_key = key
            best_tag = sorted(chosen)
            best_count = 1
        elif key == best_key:
            best_count += 1
            tag = sorted(chosen)
            if tag > best_tag:
                best_tag = tag

    def walk(depth, relief_packed, recovery_packed, bid, recovery_total, seg_packed, chosen):
        if depth == depth_limit:
            evaluate(relief_packed, seg_packed, bid, recovery_total, chosen)
            return
        for d_relief, d_recovery, d_bid, d_rec, d_seg, offer_id in options[depth]:
            if offer_id is None:
                walk(
                    depth + 1,
                    relief_packed,
                    recovery_packed,
                    bid,
                    recovery_total,
                    seg_packed,
                    chosen,
                )
                continue
            new_relief = relief_packed + d_relief
            if ((relief_limit - new_relief) & guard) != guard:
                continue
            new_recovery = recovery_packed + d_recovery
            if ((recovery_limit - new_recovery) & guard) != guard:
                continue
            walk(
                depth + 1,
                new_relief,
                new_recovery,
                bid + d_bid,
                recovery_total + d_rec,
                seg_packed + d_seg,
                chosen + (offer_id,),
            )

    walk(0, 0, 0, 0, 0, 0, ())
    return best_tag, best_count


# --------------------------------------------------------------------------- #
# grants                                                                      #
# --------------------------------------------------------------------------- #


def apportion(funded, weights):
    """Largest-remainder split of `funded` over beneficiary weights.

    Returns (cents by beneficiary or None when the pool is unallocated,
    residual cents, residual tie).
    """
    total = sum(weights.values())
    if total == 0:
        return None, 0, False
    shares = {}
    remainders = {}
    allocated = 0
    for beneficiary, weight in weights.items():
        if weight <= 0:
            continue
        base, rem = divmod(funded * weight, total)
        shares[beneficiary] = base
        remainders[beneficiary] = rem
        allocated += base
    residual = funded - allocated
    order = sorted(
        shares,
        key=lambda beneficiary: (remainders[beneficiary], beneficiary),
        reverse=True,
    )
    for beneficiary in order[:residual]:
        shares[beneficiary] += 1
    seen = set()
    tie = False
    for rem in remainders.values():
        if rem == 0:
            continue
        if rem in seen:
            tie = True
            break
        seen.add(rem)
    return shares, residual, tie


# --------------------------------------------------------------------------- #
# reporting                                                                   #
# --------------------------------------------------------------------------- #


def build(extract):
    event_ids = extract.event_ids
    regions = extract.regions
    segments = extract.segments

    candidates = defaultdict(lambda: defaultdict(list))
    ineligible = 0
    for offer_id, offer in extract.offers.items():
        if offer["orphan"]:
            continue
        site_key = (offer["event_id"], offer["site_id"])
        if not extract.state[site_key]["dispatch_authorized"]:
            ineligible += 1
            continue
        group = (offer["event_id"], extract.sites[site_key]["region"])
        candidates[group][offer["site_id"]].append(offer_id)

    group_sites = defaultdict(list)
    for site_key, site in extract.sites.items():
        group_sites[(site_key[0], site["region"])].append(site_key)

    region_events = {region: [] for region in regions}
    segment_entries = {segment: [] for segment in segments}
    tie_decisions = []
    cap_binding_count = 0
    residual_cents = 0
    residual_tie_pool_count = 0
    empty_candidate_groups = 0
    unallocated_pool_count = 0
    zero_floor_count = 0

    for event_id in event_ids:
        count = extract.interval_count[event_id]
        for region in regions:
            group = (event_id, region)
            by_site = candidates.get(group, {})
            candidate_offer_count = sum(len(v) for v in by_site.values())
            if candidate_offer_count == 0:
                empty_candidate_groups += 1
            selected, tied = choose_portfolio(extract, event_id, region, by_site)
            if tied >= 2:
                tie_decisions.append(
                    {
                        "event_id": event_id,
                        "region": region,
                        "selected_offer_ids": list(selected),
                        "tied_portfolio_count": tied,
                    }
                )

            relief = [0] * count
            recovery = [0] * count
            bid_cost_cents = 0
            credit_cents = 0
            per_segment = {
                segment: {
                    "selected_offer_ids": [],
                    "relief_ticks": 0,
                    "recovery_ticks": 0,
                    "bid_cost_cents": 0,
                    "credit_cents": 0,
                }
                for segment in segments
            }
            for offer_id in selected:
                offer = extract.offers[offer_id]
                site_key = (offer["event_id"], offer["site_id"])
                offer_relief = []
                offer_recovery = 0
                for index in range(count):
                    row = extract.profile.get((offer_id, index + 1), (0, 0))
                    offer_relief.append(row[0])
                    relief[index] += row[0]
                    recovery[index] += row[1]
                    offer_recovery += row[1]
                offer_credit = extract.credit_cents(site_key, offer_relief)
                bid_cost_cents += offer["bid_cost_cents"]
                credit_cents += offer_credit
                if extract.rates(site_key)[2]:
                    cap_binding_count += 1
                bucket = per_segment[extract.sites[site_key]["segment"]]
                bucket["selected_offer_ids"].append(offer_id)
                bucket["relief_ticks"] += sum(offer_relief)
                bucket["recovery_ticks"] += offer_recovery
                bucket["bid_cost_cents"] += offer["bid_cost_cents"]
                bucket["credit_cents"] += offer_credit

            interval_entries = []
            for index in range(count):
                target = extract.targets[(event_id, region, index + 1)][0]
                interval_entries.append(
                    {
                        "interval": index + 1,
                        "target_ticks": target,
                        "relief_ticks": relief[index],
                        "recovery_ticks": recovery[index],
                        "shortfall_ticks": max(0, target - relief[index]),
                        "overdelivery_ticks": max(0, relief[index] - target),
                    }
                )

            pool_cents = extract.pools.get(group, 0)
            funded_cents = max(0, pool_cents - credit_cents)
            weights = defaultdict(int)
            recipients = 0
            for site_key in group_sites.get(group, ()):
                weight = extract.grant_weight.get(site_key)
                if weight is None:
                    continue
                recipients += 1
                if extract.label[site_key] == "CONTINUITY_WAIVED":
                    weight *= 2
                weights[extract.sites[site_key]["beneficiary_id"]] += weight
            if recipients == 0:
                shares, residual, tie = None, 0, False
            else:
                shares, residual, tie = apportion(funded_cents, weights)
            if shares is None:
                unallocated_pool_count += 1
                grants = []
                allocated_cents = 0
            else:
                grants = [
                    {"beneficiary_id": beneficiary, "cents": cents}
                    for beneficiary, cents in sorted(shares.items())
                ]
                allocated_cents = sum(shares.values())
            residual_cents += residual
            residual_tie_pool_count += tie

            compliance_counts = {label: 0 for label in LABELS}
            for site_key in group_sites.get(group, ()):
                compliance_counts[extract.label[site_key]] += 1

            region_events[region].append(
                {
                    "event_id": event_id,
                    "candidate_offer_count": candidate_offer_count,
                    "selected_offer_ids": list(selected),
                    "intervals": interval_entries,
                    "bid_cost_cents": bid_cost_cents,
                    "credit_cents": credit_cents,
                    "grant_pool_cents": pool_cents,
                    "grant_funded_cents": funded_cents,
                    "grant_allocated_cents": allocated_cents,
                    "grant_unallocated_cents": funded_cents - allocated_cents,
                    "grants": grants,
                    "compliance_counts": compliance_counts,
                }
            )
            for segment in segments:
                bucket = per_segment[segment]
                floor_ticks = extract.floor_of(event_id, region, segment)[0]
                if floor_ticks == 0:
                    zero_floor_count += 1
                    attainment = 10000
                else:
                    attainment = min(
                        10000, div_half_up(10000 * bucket["relief_ticks"], floor_ticks)
                    )
                segment_entries[segment].append(
                    {
                        "event_id": event_id,
                        "region": region,
                        "selected_offer_ids": sorted(bucket["selected_offer_ids"]),
                        "relief_ticks": bucket["relief_ticks"],
                        "recovery_ticks": bucket["recovery_ticks"],
                        "bid_cost_cents": bucket["bid_cost_cents"],
                        "credit_cents": bucket["credit_cents"],
                        "floor_ticks": floor_ticks,
                        "floor_attainment_bp": attainment,
                    }
                )

    documents = {}
    region_totals = {}
    for region in regions:
        events = region_events[region]
        totals = {
            "event_count": len(events),
            "candidate_offer_count": sum(e["candidate_offer_count"] for e in events),
            "selected_offer_count": sum(len(e["selected_offer_ids"]) for e in events),
            "relief_ticks": sum(i["relief_ticks"] for e in events for i in e["intervals"]),
            "recovery_ticks": sum(i["recovery_ticks"] for e in events for i in e["intervals"]),
            "shortfall_ticks": sum(
                i["shortfall_ticks"] for e in events for i in e["intervals"]
            ),
            "overdelivery_ticks": sum(
                i["overdelivery_ticks"] for e in events for i in e["intervals"]
            ),
            "bid_cost_cents": sum(e["bid_cost_cents"] for e in events),
            "credit_cents": sum(e["credit_cents"] for e in events),
            "grant_pool_cents": sum(e["grant_pool_cents"] for e in events),
            "grant_funded_cents": sum(e["grant_funded_cents"] for e in events),
            "grant_allocated_cents": sum(e["grant_allocated_cents"] for e in events),
            "grant_unallocated_cents": sum(e["grant_unallocated_cents"] for e in events),
        }
        region_totals[region] = totals
        documents["region_%s.json" % region] = {
            "region": region,
            "events": events,
            "totals": totals,
        }

    segment_totals = {}
    for segment in segments:
        entries = segment_entries[segment]
        totals = {
            "selected_offer_count": sum(len(e["selected_offer_ids"]) for e in entries),
            "relief_ticks": sum(e["relief_ticks"] for e in entries),
            "recovery_ticks": sum(e["recovery_ticks"] for e in entries),
            "bid_cost_cents": sum(e["bid_cost_cents"] for e in entries),
            "credit_cents": sum(e["credit_cents"] for e in entries),
            "floor_ticks": sum(e["floor_ticks"] for e in entries),
        }
        segment_totals[segment] = totals
        documents["segment_%s.json" % segment] = {
            "segment": segment,
            "event_regions": entries,
            "totals": totals,
        }

    def over_regions(field):
        return sum(totals[field] for totals in region_totals.values())

    documents["summary.json"] = {
        "event_count": len(event_ids),
        "event_region_count": len(event_ids) * len(regions),
        "site_count": len(extract.sites),
        "candidate_offer_count": over_regions("candidate_offer_count"),
        "selected_offer_count": over_regions("selected_offer_count"),
        "relief_ticks": over_regions("relief_ticks"),
        "recovery_ticks": over_regions("recovery_ticks"),
        "shortfall_ticks": over_regions("shortfall_ticks"),
        "overdelivery_ticks": over_regions("overdelivery_ticks"),
        "bid_cost_cents": over_regions("bid_cost_cents"),
        "credit_cents": over_regions("credit_cents"),
        "grant_pool_cents": over_regions("grant_pool_cents"),
        "grant_funded_cents": over_regions("grant_funded_cents"),
        "grant_allocated_cents": over_regions("grant_allocated_cents"),
        "grant_unallocated_cents": over_regions("grant_unallocated_cents"),
        "regions": {
            region: {
                "selected_offer_count": totals["selected_offer_count"],
                "relief_ticks": totals["relief_ticks"],
                "bid_cost_cents": totals["bid_cost_cents"],
                "credit_cents": totals["credit_cents"],
                "grant_allocated_cents": totals["grant_allocated_cents"],
            }
            for region, totals in region_totals.items()
        },
        "segments": {
            segment: {
                "selected_offer_count": totals["selected_offer_count"],
                "relief_ticks": totals["relief_ticks"],
                "bid_cost_cents": totals["bid_cost_cents"],
                "credit_cents": totals["credit_cents"],
            }
            for segment, totals in segment_totals.items()
        },
    }

    compliance_counts = {label: 0 for label in LABELS}
    for label in extract.label.values():
        compliance_counts[label] += 1
    documents["policy_audit.json"] = {
        "compliance_counts": compliance_counts,
        "site_labels": [
            {"event_id": key[0], "site_id": key[1], "label": extract.label[key]}
            for key in sorted(extract.label)
        ],
        "tie_decisions": tie_decisions,
        "cap_binding_count": cap_binding_count,
        "residual_cents": residual_cents,
        "residual_tie_pool_count": residual_tie_pool_count,
    }

    documents["data_quality.json"] = {
        "rows": extract.rows,
        "orphan_offer_rows": extract.orphan_offer_rows,
        "orphan_profile_rows": extract.orphan_profile_rows,
        "out_of_range_profile_rows": extract.out_of_range_profile_rows,
        "duplicate_profile_rows": extract.duplicate_profile_rows,
        "unknown_region_site_rows": extract.unknown_region_site_rows,
        "waiver_signed_missing": extract.waiver_signed_missing,
        "ineligible_offer_count": ineligible,
        "empty_candidate_groups": empty_candidate_groups,
        "zero_floor_count": zero_floor_count,
        "unallocated_pool_count": unallocated_pool_count,
    }
    return documents


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    documents = build(Extract(data_dir))
    os.makedirs(out_dir, exist_ok=True)
    for name, document in documents.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            json.dump(document, handle, sort_keys=True, indent=1)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
