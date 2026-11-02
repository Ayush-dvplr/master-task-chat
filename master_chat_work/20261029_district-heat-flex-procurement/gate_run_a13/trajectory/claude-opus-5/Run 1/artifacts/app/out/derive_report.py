#!/usr/bin/env python3
"""Derive the winter demand-response reports from one season extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import configparser
import csv
import json
import os
import sys
from datetime import datetime
from xml.etree import ElementTree as ET

LABELS = ("SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR")


def round_half_up(num, den):
    return (2 * num + den) // (2 * den)


def round_half_even(num, den):
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2):
        q += 1
    return q


def read_text_rows(path, delimiter):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def read_commented_rows(path):
    """Tab separated file where '#' lines are comments and the first other line is the header."""
    with open(path, encoding="utf-8") as fh:
        lines = [ln.rstrip("\n") for ln in fh]
    lines = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        fields = ln.split("\t")
        fields += [""] * (len(header) - len(fields))
        rows.append(dict(zip(header, fields)))
    return rows


def non_comment_lines(path):
    with open(path, encoding="utf-8") as fh:
        return [ln.rstrip("\n") for ln in fh if ln.strip() and not ln.startswith("#")]


class Extract:
    def __init__(self, data_dir):
        self.dir = data_dir
        self.load_program()
        self.load_events()
        self.load_sites()
        self.load_offers()
        self.load_profiles()
        self.load_grids()
        self.load_state()
        self.load_cards()
        self.load_grant_inputs()
        self.load_allowances()
        self.manifest_row_count = len(read_commented_rows(self.path("export_manifest.tsv")))

    def path(self, name):
        return os.path.join(self.dir, name)

    def ticks(self, wh):
        return round_half_up(wh, self.wh_per_tick)

    def region_name(self, code):
        return self.region_of_code[code.lower()]

    def load_program(self):
        cp = configparser.ConfigParser()
        with open(self.path("program.ini"), encoding="utf-8") as fh:
            cp.read_file(fh)
        defaults = cp.defaults()

        def section(name):
            if not cp.has_section(name):
                return {}
            return {k: v for k, v in cp.items(name) if k not in defaults}

        units = section("units")
        self.wh_per_tick = int(units["wh_per_tick"])
        self.millicents_per_cent = int(units["millicents_per_cent"])
        self.region_of_code = section("region_codes")
        self.segment_of_code = section("segment_codes")
        self.regions = sorted(set(self.region_of_code.values()))
        self.segments = sorted(set(self.segment_of_code.values()))
        self.seg_index = {name: i for i, name in enumerate(self.segments)}
        adders = section("segment_rate_adders")
        self.segment_adder = {name: int(adders.get(name.lower(), 0)) for name in self.segments}
        grants = section("grants")
        self.claim_per_weight = int(grants["claim_cents_per_weight"])
        self.minimum_grant = int(grants["minimum_grant_cents"])

    def load_events(self):
        with open(self.path("events.json"), encoding="utf-8") as fh:
            events = json.load(fh)
        self.event_row_count = len(events)
        self.events = {}
        for ev in events:
            self.events[ev["event_id"]] = {
                "event_id": ev["event_id"],
                "interval_count": int(ev["interval_count"]),
                "cost_weight": int(ev["objective"]["cost_weight"]),
                "recovery_weight": int(ev["objective"]["recovery_weight"]),
                "uplift": int(ev["uplift_millicents_per_kwh"]),
                "instant": datetime.fromisoformat(ev["dispatch_start"]),
            }
        self.event_ids = sorted(self.events)
        # Season order: ascending start instant; equal instants take the greatest id first.
        by_id_desc = sorted(self.events.values(), key=lambda e: e["event_id"], reverse=True)
        self.season_order = [e["event_id"] for e in sorted(by_id_desc, key=lambda e: e["instant"])]

    def load_sites(self):
        rows = read_text_rows(self.path("sites.csv"), ",")
        self.site_file_row_count = len(rows)
        self.unknown_region_site_rows = 0
        self.site_rows = {}
        self.sites_of_group = {}
        for row in rows:
            code = row["region_code"].lower()
            if code not in self.region_of_code:
                self.unknown_region_site_rows += 1
                continue
            region = self.region_of_code[code]
            key = (row["event_id"], row["site_id"])
            self.site_rows[key] = {
                "event_id": row["event_id"],
                "site_id": row["site_id"],
                "region": region,
                "segment": self.segment_of_code.get(row["segment_code"].lower()),
                "beneficiary_id": row["beneficiary_id"],
                "critical": row["critical"] == "Y",
            }
            self.sites_of_group.setdefault((row["event_id"], region), []).append(key)

    def load_offers(self):
        rows = read_text_rows(self.path("offers.csv"), ",")
        self.offer_row_count = len(rows)
        self.offers = {}
        self.offer_event = {}
        self.orphan_offer_rows = 0
        for row in rows:
            self.offer_event[row["offer_id"]] = row["event_id"]
            key = (row["event_id"], row["site_id"])
            if key not in self.site_rows:
                self.orphan_offer_rows += 1
                continue
            n_int = self.events[row["event_id"]]["interval_count"]
            self.offers[row["offer_id"]] = {
                "offer_id": row["offer_id"],
                "event_id": row["event_id"],
                "site_id": row["site_id"],
                "bid_cost_cents": int(row["bid_cost_cents"]),
                "relief": [0] * n_int,
                "recovery": [0] * n_int,
            }

    def load_profiles(self):
        self.profile_row_count = 0
        self.orphan_profile_rows = 0
        self.out_of_range_profile_rows = 0
        self.duplicate_profile_rows = 0
        kept = set()
        with open(self.path("profiles.tsv"), newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                self.profile_row_count += 1
                offer_id = row["offer_id"]
                event_id = self.offer_event.get(offer_id)
                if event_id is None:
                    self.orphan_profile_rows += 1
                    continue
                interval = int(row["interval"])
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
                mult = int(row["register_multiplier"])
                offer["relief"][interval - 1] = self.ticks(int(row["relief_wh"]) * mult)
                offer["recovery"][interval - 1] = self.ticks(int(row["recovery_wh"]) * mult)
        for offer in self.offers.values():
            offer["total_relief"] = sum(offer["relief"])
            offer["total_recovery"] = sum(offer["recovery"])

    def load_grids(self):
        rows = read_text_rows(self.path("targets.tsv"), "\t")
        self.target_row_count = len(rows)
        self.targets = {}
        for row in rows:
            key = (row["event_id"], self.region_name(row["region_code"]), int(row["interval"]))
            self.targets[key] = (self.ticks(int(row["target_wh"])), int(row["shortfall_weight"]))
        lines = non_comment_lines(self.path("feeder_limits.txt"))
        self.feeder_row_count = len(lines)
        self.ceilings = {}
        for ln in lines:
            key = (ln[0:10].strip(), self.region_name(ln[10:14].strip()), int(ln[14:17]))
            self.ceilings[key] = (self.ticks(int(ln[17:27])), self.ticks(int(ln[27:37])))

    def load_state(self):
        self.state = {}
        count = 0
        with open(self.path("site_state.jsonl"), encoding="utf-8") as fh:
            for ln in fh:
                if not ln.strip():
                    continue
                count += 1
                obj = json.loads(ln)
                key = (obj["event_id"], obj["site_id"])
                if key in self.site_rows:
                    self.state[key] = obj
        self.state_row_count = count

        rows = read_text_rows(self.path("continuity_waivers.csv"), ",")
        self.waiver_row_count = len(rows)
        self.waiver_signed_missing = 0
        self.waivers = {}
        for row in rows:
            if (row["waiver_signed"] or "").strip() == "":
                self.waiver_signed_missing += 1
            key = (row["event_id"], row["site_id"])
            if key in self.site_rows:
                self.waivers[key] = row

    def load_cards(self):
        cards = ET.parse(self.path("rate_cards.xml")).getroot().findall("card")
        self.card_row_count = len(cards)
        self.cards = {}
        for card in cards:
            key = (card.get("event"), card.get("site"))
            if key not in self.site_rows:
                continue
            override = card.find("override")
            self.cards[key] = (
                int(card.find("base").text),
                int(card.find("cap").text),
                None if override is None else int(override.text),
            )

    def load_grant_inputs(self):
        with open(self.path("segment_floors.json"), encoding="utf-8") as fh:
            floors = json.load(fh)["floors"]
        self.floor_row_count = len(floors)
        self.floors = {}
        for entry in floors:
            segment = self.segment_of_code.get(entry["segment_code"].lower())
            if segment is None:
                continue
            key = (entry["event_id"], self.region_name(entry["region_code"]), segment)
            self.floors[key] = (self.ticks(int(entry["floor_wh"])), int(entry["priority_weight"]))

        rows = read_text_rows(self.path("recipient_weights.tsv"), "\t")
        self.weight_row_count = len(rows)
        self.grant_weights = {}
        for row in rows:
            key = (row["event_id"], row["site_id"])
            if key in self.site_rows:
                self.grant_weights[key] = int(row["grant_weight"])

        lines = non_comment_lines(self.path("pools.txt"))
        self.pool_row_count = len(lines)
        self.pools = {}
        for ln in lines:
            key = (ln[0:10].strip(), self.region_name(ln[10:14].strip()))
            self.pools[key] = int(ln[14:26])

    def load_allowances(self):
        rows = read_commented_rows(self.path("site_allowances.tsv"))
        self.allowance_row_count = len(rows)
        self.allowance_ticks = {}
        draws_from = {}
        for row in rows:
            site = row["site_id"]
            self.allowance_ticks[site] = int(row["allowance_ticks"])
            draws_from[site] = row["draws_from"].strip()
        self.allowance_root = {}
        for site in draws_from:
            node = site
            while draws_from[node]:
                node = draws_from[node]
            self.allowance_root[site] = node


def label_of(ex, key):
    state = ex.state[key]
    if state["safety_hold"]:
        return "SAFETY_HOLD"
    if state["cooldown"]:
        return "COOLDOWN"
    waiver = ex.waivers[key]
    if waiver["routine_certificate_pending"] != "Y":
        return "CLEAR"
    site = ex.site_rows[key]
    waived = (
        waiver["waiver_status"] == "VALID"
        and (waiver["waiver_signed"] or "").strip() == "Y"
        and site["critical"]
        and site["segment"] == "public"
    )
    return "CONTINUITY_WAIVED" if waived else "CERTIFICATE_PENDING"


def rate_of(ex, key):
    """(effective rate, cap binding) for a site row, in mill-cents per kWh."""
    base, cap, override = ex.cards[key]
    site = ex.site_rows[key]
    rate = base if override is None else override
    rate += ex.events[site["event_id"]]["uplift"]
    rate += ex.segment_adder.get(site["segment"], 0)
    return min(rate, cap), rate > cap


def credit_of(ex, offer, rate):
    denom = 1000 * ex.millicents_per_cent
    total = 0
    for relief, recovery in zip(offer["relief"], offer["recovery"]):
        credited = relief - recovery
        if credited > 0:
            total += round_half_even(credited * ex.wh_per_tick * rate, denom)
    return total


def optimise(options, targets, weights, relief_cap, recovery_cap, floors, cost_w, recovery_w):
    """Return (best offer ids, count of portfolios tied at the best value)."""
    n_int = len(targets)
    n_seg = len(floors)
    n_site = len(options)
    relief = [0] * n_int
    recovery = [0] * n_int
    seg_relief = [0] * (n_seg + 1)
    chosen = []
    best_key = None
    best_ids = None
    tied = 0

    def walk(i, bid, count, recovery_total):
        nonlocal best_key, best_ids, tied
        if i == n_site:
            shortfall = 0
            over = 0
            for t in range(n_int):
                diff = targets[t] - relief[t]
                if diff > 0:
                    shortfall += weights[t] * diff
                else:
                    over -= diff
            deficit = 0
            for s in range(n_seg):
                floor, priority = floors[s]
                gap = floor - seg_relief[s]
                if gap > 0:
                    deficit += priority * gap
            key = (shortfall, deficit, cost_w * bid + recovery_w * recovery_total, over, count)
            if best_key is None or key < best_key:
                best_key = key
                best_ids = tuple(sorted(chosen))
                tied = 1
            elif key == best_key:
                tied += 1
                ids = tuple(sorted(chosen))
                if ids > best_ids:
                    best_ids = ids
            return
        walk(i + 1, bid, count, recovery_total)
        for offer_id, rel, rec, cost, total_rel, total_rec, seg in options[i]:
            fits = True
            for t in range(n_int):
                if relief[t] + rel[t] > relief_cap[t] or recovery[t] + rec[t] > recovery_cap[t]:
                    fits = False
                    break
            if not fits:
                continue
            for t in range(n_int):
                relief[t] += rel[t]
                recovery[t] += rec[t]
            seg_relief[seg] += total_rel
            chosen.append(offer_id)
            walk(i + 1, bid + cost, count + 1, recovery_total + total_rec)
            chosen.pop()
            seg_relief[seg] -= total_rel
            for t in range(n_int):
                relief[t] -= rel[t]
                recovery[t] -= rec[t]

    walk(0, 0, 0, 0)
    return list(best_ids), tied


def largest_remainder(funded, weights):
    """Share `funded` cents in proportion to weights. Returns (shares, residual, tie)."""
    total_weight = sum(weights.values())
    shares = {}
    remainders = {}
    for ben, weight in weights.items():
        product = funded * weight
        shares[ben] = product // total_weight
        remainders[ben] = product % total_weight
    residual = funded - sum(shares.values())
    order = sorted(weights, key=lambda b: (remainders[b], b), reverse=True)
    for ben in order[:residual]:
        shares[ben] += 1
    non_zero = [r for r in remainders.values() if r]
    return shares, residual, len(non_zero) != len(set(non_zero))


def apportion(ex, funded, beneficiary_weights, has_recipients):
    """Return (grants, allocated, unallocated, residual cents, residual tie)."""
    positive = {b: w for b, w in beneficiary_weights.items() if w > 0}
    if not has_recipients or sum(beneficiary_weights.values()) == 0:
        return {b: 0 for b in positive}, 0, funded, 0, False
    claims = {b: w * ex.claim_per_weight for b, w in positive.items()}
    claimed = sum(claims.values())
    if claimed <= funded:
        return claims, claimed, funded - claimed, 0, False
    shares, residual, tie = largest_remainder(funded, positive)
    survivors = {b: w for b, w in positive.items() if shares[b] >= ex.minimum_grant}
    if not survivors:
        return {b: 0 for b in positive}, 0, funded, 0, False
    if len(survivors) == len(positive):
        allocated = sum(shares.values())
        return shares, allocated, funded - allocated, residual, tie
    shares, residual, tie = largest_remainder(funded, survivors)
    grants = {b: shares.get(b, 0) for b in positive}
    allocated = sum(shares.values())
    return grants, allocated, funded - allocated, residual, tie


def build(ex):
    region_events = {region: {} for region in ex.regions}
    segment_entries = {segment: {} for segment in ex.segments}
    audit = {
        "compliance_counts": {label: 0 for label in LABELS},
        "site_labels": [],
        "tie_decisions": [],
        "cap_binding_count": 0,
        "residual_cents": 0,
        "residual_tie_pool_count": 0,
    }
    quality = {
        "ineligible_offer_count": 0,
        "allowance_blocked_offer_count": 0,
        "empty_candidate_groups": 0,
        "zero_floor_count": 0,
        "unallocated_pool_count": 0,
    }

    labels = {}
    rates = {}
    for key in ex.site_rows:
        labels[key] = label_of(ex, key)
        audit["compliance_counts"][labels[key]] += 1
        rates[key] = rate_of(ex, key)
    audit["site_labels"] = [
        {"event_id": key[0], "site_id": key[1], "label": labels[key]}
        for key in sorted(ex.site_rows)
    ]

    offers_of_event = {}
    for offer in ex.offers.values():
        offers_of_event.setdefault(offer["event_id"], []).append(offer)

    consumed = dict.fromkeys(set(ex.allowance_root.values()), 0)
    carried = dict.fromkeys(ex.regions, 0)

    for event_id in ex.season_order:
        event = ex.events[event_id]
        n_int = event["interval_count"]
        candidates = {}
        for offer in offers_of_event.get(event_id, []):
            key = (event_id, offer["site_id"])
            if not ex.state[key]["dispatch_authorized"]:
                quality["ineligible_offer_count"] += 1
                continue
            root = ex.allowance_root[offer["site_id"]]
            if offer["total_relief"] > ex.allowance_ticks[root] - consumed[root]:
                quality["allowance_blocked_offer_count"] += 1
                continue
            region = ex.site_rows[key]["region"]
            candidates.setdefault(region, {}).setdefault(key, []).append(offer)

        for region in ex.regions:
            by_site = candidates.get(region, {})
            candidate_count = sum(len(v) for v in by_site.values())
            if candidate_count == 0:
                quality["empty_candidate_groups"] += 1

            targets = []
            weights = []
            relief_cap = []
            recovery_cap = []
            for t in range(1, n_int + 1):
                target, weight = ex.targets[(event_id, region, t)]
                relief_ceiling, recovery_ceiling = ex.ceilings[(event_id, region, t)]
                targets.append(target)
                weights.append(weight)
                relief_cap.append(relief_ceiling)
                recovery_cap.append(recovery_ceiling)

            floors = []
            for segment in ex.segments:
                floor, priority = ex.floors.get((event_id, region, segment), (0, 0))
                floors.append((floor, priority))
                if floor == 0:
                    quality["zero_floor_count"] += 1

            options = []
            for key in sorted(by_site):
                seg = ex.seg_index.get(ex.site_rows[key]["segment"], len(ex.segments))
                options.append(
                    [
                        (
                            offer["offer_id"],
                            offer["relief"],
                            offer["recovery"],
                            offer["bid_cost_cents"],
                            offer["total_relief"],
                            offer["total_recovery"],
                            seg,
                        )
                        for offer in sorted(by_site[key], key=lambda o: o["offer_id"])
                    ]
                )
            selected_ids, tied_count = optimise(
                options,
                targets,
                weights,
                relief_cap,
                recovery_cap,
                floors,
                event["cost_weight"],
                event["recovery_weight"],
            )
            if tied_count > 1:
                audit["tie_decisions"].append(
                    {
                        "event_id": event_id,
                        "region": region,
                        "tied_portfolio_count": tied_count,
                        "selected_offer_ids": list(selected_ids),
                    }
                )

            relief = [0] * n_int
            recovery = [0] * n_int
            bid_cost = 0
            credit_cents = 0
            seg_data = {
                segment: {"ids": [], "relief": 0, "recovery": 0, "bid": 0, "credit": 0}
                for segment in ex.segments
            }
            for offer_id in selected_ids:
                offer = ex.offers[offer_id]
                key = (event_id, offer["site_id"])
                rate, cap_binding = rates[key]
                if cap_binding:
                    audit["cap_binding_count"] += 1
                credit = credit_of(ex, offer, rate)
                credit_cents += credit
                bid_cost += offer["bid_cost_cents"]
                for t in range(n_int):
                    relief[t] += offer["relief"][t]
                    recovery[t] += offer["recovery"][t]
                consumed[ex.allowance_root[offer["site_id"]]] += offer["total_relief"]
                segment = ex.site_rows[key]["segment"]
                if segment in seg_data:
                    bucket = seg_data[segment]
                    bucket["ids"].append(offer_id)
                    bucket["relief"] += offer["total_relief"]
                    bucket["recovery"] += offer["total_recovery"]
                    bucket["bid"] += offer["bid_cost_cents"]
                    bucket["credit"] += credit

            intervals = []
            shortfall_total = 0
            over_total = 0
            for t in range(n_int):
                shortfall = max(0, targets[t] - relief[t])
                over = max(0, relief[t] - targets[t])
                shortfall_total += shortfall
                over_total += over
                intervals.append(
                    {
                        "interval": t + 1,
                        "target_ticks": targets[t],
                        "relief_ticks": relief[t],
                        "recovery_ticks": recovery[t],
                        "shortfall_ticks": shortfall,
                        "overdelivery_ticks": over,
                    }
                )

            site_keys = ex.sites_of_group.get((event_id, region), [])
            compliance = {label: 0 for label in LABELS}
            for key in site_keys:
                compliance[labels[key]] += 1

            pool = ex.pools.get((event_id, region), 0)
            funded = max(0, pool + carried[region] - credit_cents)
            beneficiary_weights = {}
            has_recipients = False
            for key in site_keys:
                weight = ex.grant_weights.get(key)
                if weight is None:
                    continue
                has_recipients = True
                if labels[key] == "CONTINUITY_WAIVED":
                    weight *= 2
                ben = ex.site_rows[key]["beneficiary_id"]
                beneficiary_weights[ben] = beneficiary_weights.get(ben, 0) + weight
            if not has_recipients or sum(beneficiary_weights.values()) == 0:
                quality["unallocated_pool_count"] += 1
            grants, allocated, unallocated, residual, residual_tie = apportion(
                ex, funded, beneficiary_weights, has_recipients
            )
            audit["residual_cents"] += residual
            if residual_tie:
                audit["residual_tie_pool_count"] += 1
            carried[region] = unallocated

            region_events[region][event_id] = {
                "event_id": event_id,
                "candidate_offer_count": candidate_count,
                "selected_offer_ids": list(selected_ids),
                "intervals": intervals,
                "bid_cost_cents": bid_cost,
                "credit_cents": credit_cents,
                "grant_pool_cents": pool,
                "grant_funded_cents": funded,
                "grant_allocated_cents": allocated,
                "grant_unallocated_cents": unallocated,
                "grants": [
                    {"beneficiary_id": ben, "cents": grants[ben]} for ben in sorted(grants)
                ],
                "compliance_counts": compliance,
                "_relief": sum(relief),
                "_recovery": sum(recovery),
                "_shortfall": shortfall_total,
                "_over": over_total,
            }

            for segment in ex.segments:
                bucket = seg_data[segment]
                floor = ex.floors.get((event_id, region, segment), (0, 0))[0]
                if floor == 0:
                    attainment = 10000
                else:
                    attainment = min(10000, round_half_up(10000 * bucket["relief"], floor))
                segment_entries[segment][(event_id, region)] = {
                    "event_id": event_id,
                    "region": region,
                    "selected_offer_ids": sorted(bucket["ids"]),
                    "relief_ticks": bucket["relief"],
                    "recovery_ticks": bucket["recovery"],
                    "bid_cost_cents": bucket["bid"],
                    "credit_cents": bucket["credit"],
                    "floor_ticks": floor,
                    "floor_attainment_bp": attainment,
                }

    audit["tie_decisions"].sort(key=lambda entry: (entry["event_id"], entry["region"]))
    return region_events, segment_entries, audit, quality


REGION_TOTAL_FIELDS = (
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


def region_documents(ex, region_events):
    docs = {}
    for region in ex.regions:
        entries = []
        totals = dict.fromkeys(REGION_TOTAL_FIELDS, 0)
        for event_id in ex.event_ids:
            entry = dict(region_events[region][event_id])
            totals["event_count"] += 1
            totals["candidate_offer_count"] += entry["candidate_offer_count"]
            totals["selected_offer_count"] += len(entry["selected_offer_ids"])
            totals["relief_ticks"] += entry.pop("_relief")
            totals["recovery_ticks"] += entry.pop("_recovery")
            totals["shortfall_ticks"] += entry.pop("_shortfall")
            totals["overdelivery_ticks"] += entry.pop("_over")
            for field in (
                "bid_cost_cents",
                "credit_cents",
                "grant_pool_cents",
                "grant_funded_cents",
                "grant_allocated_cents",
                "grant_unallocated_cents",
            ):
                totals[field] += entry[field]
            entries.append(entry)
        docs[region] = {"region": region, "events": entries, "totals": totals}
    return docs


def segment_documents(ex, segment_entries):
    docs = {}
    for segment in ex.segments:
        entries = [segment_entries[segment][key] for key in sorted(segment_entries[segment])]
        docs[segment] = {
            "segment": segment,
            "event_regions": entries,
            "totals": {
                "selected_offer_count": sum(len(e["selected_offer_ids"]) for e in entries),
                "relief_ticks": sum(e["relief_ticks"] for e in entries),
                "recovery_ticks": sum(e["recovery_ticks"] for e in entries),
                "bid_cost_cents": sum(e["bid_cost_cents"] for e in entries),
                "credit_cents": sum(e["credit_cents"] for e in entries),
                "floor_ticks": sum(e["floor_ticks"] for e in entries),
            },
        }
    return docs


def summary_document(ex, region_docs, segment_docs):
    fields = (
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
    doc = dict.fromkeys(fields, 0)
    doc["event_count"] = len(ex.event_ids)
    doc["event_region_count"] = len(ex.event_ids) * len(ex.regions)
    doc["site_count"] = len(ex.site_rows)
    doc["regions"] = {}
    doc["segments"] = {}
    for region, region_doc in region_docs.items():
        totals = region_doc["totals"]
        for field in fields:
            doc[field] += totals[field]
        doc["regions"][region] = {
            "selected_offer_count": totals["selected_offer_count"],
            "relief_ticks": totals["relief_ticks"],
            "bid_cost_cents": totals["bid_cost_cents"],
            "credit_cents": totals["credit_cents"],
            "grant_allocated_cents": totals["grant_allocated_cents"],
        }
    for segment, segment_doc in segment_docs.items():
        totals = segment_doc["totals"]
        doc["segments"][segment] = {
            "selected_offer_count": totals["selected_offer_count"],
            "relief_ticks": totals["relief_ticks"],
            "bid_cost_cents": totals["bid_cost_cents"],
            "credit_cents": totals["credit_cents"],
        }
    return doc


def quality_document(ex, quality):
    doc = dict(quality)
    doc["rows"] = {
        "events.json": ex.event_row_count,
        "sites.csv": ex.site_file_row_count,
        "offers.csv": ex.offer_row_count,
        "profiles.tsv": ex.profile_row_count,
        "targets.tsv": ex.target_row_count,
        "continuity_waivers.csv": ex.waiver_row_count,
        "recipient_weights.tsv": ex.weight_row_count,
        "site_allowances.tsv": ex.allowance_row_count,
        "feeder_limits.txt": ex.feeder_row_count,
        "pools.txt": ex.pool_row_count,
        "site_state.jsonl": ex.state_row_count,
        "segment_floors.json": ex.floor_row_count,
        "rate_cards.xml": ex.card_row_count,
        "export_manifest.tsv": ex.manifest_row_count,
    }
    doc["orphan_offer_rows"] = ex.orphan_offer_rows
    doc["orphan_profile_rows"] = ex.orphan_profile_rows
    doc["out_of_range_profile_rows"] = ex.out_of_range_profile_rows
    doc["duplicate_profile_rows"] = ex.duplicate_profile_rows
    doc["unknown_region_site_rows"] = ex.unknown_region_site_rows
    doc["waiver_signed_missing"] = ex.waiver_signed_missing
    return doc


def write_json(out_dir, name, doc):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, sort_keys=True, indent=1)
        fh.write("\n")


def main(argv):
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    sys.setrecursionlimit(100000)

    ex = Extract(data_dir)
    region_events, segment_entries, audit, quality = build(ex)
    region_docs = region_documents(ex, region_events)
    segment_docs = segment_documents(ex, segment_entries)

    for region, doc in region_docs.items():
        write_json(out_dir, "region_%s.json" % region, doc)
    for segment, doc in segment_docs.items():
        write_json(out_dir, "segment_%s.json" % segment, doc)
    write_json(out_dir, "summary.json", summary_document(ex, region_docs, segment_docs))
    write_json(out_dir, "policy_audit.json", audit)
    write_json(out_dir, "data_quality.json", quality_document(ex, quality))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
