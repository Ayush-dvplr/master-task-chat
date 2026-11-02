#!/usr/bin/env python3
"""Derive the winter demand-response programme reports from one season extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import configparser
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

LABELS = ("SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR")


def round_half_up(num, den):
    q, r = divmod(num, den)
    if 2 * r >= den:
        q += 1
    return q


def round_half_even(num, den):
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2):
        q += 1
    return q


def read_text_lines(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().splitlines()


def read_table(path, delimiter):
    """Header row plus data rows of a CSV/TSV file, as lists of fields."""
    with open(path, encoding="utf-8", newline="") as fh:
        if delimiter == "\t":
            rows = [ln.split("\t") for ln in fh.read().splitlines()]
        else:
            rows = list(csv.reader(fh, delimiter=delimiter))
    rows = [row for row in rows if any(field for field in row)]
    return rows[0], rows[1:]


def fixed_width_records(path):
    """Non-comment, non-empty lines of a fixed-width file."""
    return [ln for ln in read_text_lines(path) if not ln.startswith("#") and ln.strip()]


class Extract:
    def __init__(self, data_dir):
        self.dir = data_dir
        self.dq_rows = {}
        self._load_program()
        self._load_events()
        self._load_sites()
        self._load_offers()
        self._load_profiles()
        self._load_targets()
        self._load_feeder_limits()
        self._load_site_state()
        self._load_waivers()
        self._load_floors()
        self._load_rate_cards()
        self._load_recipient_weights()
        self._load_pools()
        self._load_allowances()
        self._load_manifest()
        self._derive_site_rows()
        self._derive_offers()

    def path(self, name):
        return os.path.join(self.dir, name)

    def ticks(self, wh):
        return round_half_up(wh, self.wh_per_tick)

    # ---------------- parsing ----------------

    def _load_program(self):
        cp = configparser.ConfigParser()
        with open(self.path("program.ini"), encoding="utf-8") as fh:
            cp.read_file(fh)
        self.wh_per_tick = int(cp["units"]["wh_per_tick"])
        self.millicents_per_cent = int(cp["units"]["millicents_per_cent"])
        self.region_of_code = {k.upper(): v for k, v in cp["region_codes"].items()}
        self.segment_of_code = {k.upper(): v for k, v in cp["segment_codes"].items()}
        self.segment_adders = {}
        if cp.has_section("segment_rate_adders"):
            self.segment_adders = {k.lower(): int(v) for k, v in cp["segment_rate_adders"].items()}
        self.claim_cents_per_weight = int(cp["grants"]["claim_cents_per_weight"])
        self.minimum_grant_cents = int(cp["grants"]["minimum_grant_cents"])
        self.region_names = sorted(set(self.region_of_code.values()))
        self.segment_names = sorted(set(self.segment_of_code.values()))
        self.segment_index = {name: i for i, name in enumerate(self.segment_names)}

    def _load_events(self):
        with open(self.path("events.json"), encoding="utf-8") as fh:
            events = json.load(fh)
        self.dq_rows["events.json"] = len(events)
        self.events = {e["event_id"]: e for e in events}
        self.event_ids_sorted = sorted(self.events)
        # Season order is by dispatch_start instant; events sharing an instant are
        # reached one at a time, so by convention in descending event_id order.
        by_id_desc = sorted(events, key=lambda e: e["event_id"], reverse=True)
        self.season_order = [
            e["event_id"]
            for e in sorted(by_id_desc, key=lambda e: datetime.fromisoformat(e["dispatch_start"]))
        ]

    def _load_sites(self):
        header, rows = read_table(self.path("sites.csv"), ",")
        self.dq_rows["sites.csv"] = len(rows)
        idx = {name: i for i, name in enumerate(header)}
        self.site_rows = {}
        self.unknown_region_site_rows = 0
        for row in rows:
            region = self.region_of_code.get(row[idx["region_code"]].upper())
            if region is None:
                self.unknown_region_site_rows += 1
                continue
            key = (row[idx["event_id"]], row[idx["site_id"]])
            self.site_rows[key] = {
                "region": region,
                "segment": self.segment_of_code[row[idx["segment_code"]].upper()],
                "beneficiary_id": row[idx["beneficiary_id"]],
                "critical": row[idx["critical"]],
            }

    def _load_offers(self):
        header, rows = read_table(self.path("offers.csv"), ",")
        self.dq_rows["offers.csv"] = len(rows)
        idx = {name: i for i, name in enumerate(header)}
        self.offers = {}
        self.offer_event = {}
        self.orphan_offer_rows = 0
        for row in rows:
            oid = row[idx["offer_id"]]
            eid = row[idx["event_id"]]
            sid = row[idx["site_id"]]
            self.offer_event[oid] = eid
            if (eid, sid) not in self.site_rows:
                self.orphan_offer_rows += 1
                continue
            self.offers[oid] = {
                "offer_id": oid,
                "event_id": eid,
                "site_id": sid,
                "bid_cost_cents": int(row[idx["bid_cost_cents"]]),
            }

    def _load_profiles(self):
        header, rows = read_table(self.path("profiles.tsv"), "\t")
        self.dq_rows["profiles.tsv"] = len(rows)
        idx = {name: i for i, name in enumerate(header)}
        i_off, i_itv = idx["offer_id"], idx["interval"]
        i_rel, i_rec, i_mul = idx["relief_wh"], idx["recovery_wh"], idx["register_multiplier"]
        self.orphan_profile_rows = 0
        self.out_of_range_profile_rows = 0
        self.duplicate_profile_rows = 0
        seen = set()
        self.profiles = {}
        wh_per_tick = self.wh_per_tick
        for row in rows:
            oid = row[i_off]
            eid = self.offer_event.get(oid)
            if eid is None:
                self.orphan_profile_rows += 1
                continue
            interval = int(row[i_itv])
            if interval < 1 or interval > self.events[eid]["interval_count"]:
                self.out_of_range_profile_rows += 1
                continue
            key = (oid, interval)
            if key in seen:
                self.duplicate_profile_rows += 1
                continue
            seen.add(key)
            if oid not in self.offers:
                continue
            mul = int(row[i_mul])
            self.profiles.setdefault(oid, {})[interval] = (
                round_half_up(int(row[i_rel]) * mul, wh_per_tick),
                round_half_up(int(row[i_rec]) * mul, wh_per_tick),
            )

    def _load_targets(self):
        header, rows = read_table(self.path("targets.tsv"), "\t")
        self.dq_rows["targets.tsv"] = len(rows)
        idx = {name: i for i, name in enumerate(header)}
        self.targets = {}
        for row in rows:
            region = self.region_of_code[row[idx["region_code"]].upper()]
            key = (row[idx["event_id"]], region, int(row[idx["interval"]]))
            self.targets[key] = (
                self.ticks(int(row[idx["target_wh"]])),
                int(row[idx["shortfall_weight"]]),
            )

    def _load_feeder_limits(self):
        lines = fixed_width_records(self.path("feeder_limits.txt"))
        self.dq_rows["feeder_limits.txt"] = len(lines)
        self.ceilings = {}
        for ln in lines:
            region = self.region_of_code[ln[10:14].strip().upper()]
            key = (ln[0:10].strip(), region, int(ln[14:17]))
            self.ceilings[key] = (self.ticks(int(ln[17:27])), self.ticks(int(ln[27:37])))

    def _load_site_state(self):
        lines = [ln for ln in read_text_lines(self.path("site_state.jsonl")) if ln.strip()]
        self.dq_rows["site_state.jsonl"] = len(lines)
        self.site_state = {}
        for ln in lines:
            obj = json.loads(ln)
            key = (obj["event_id"], obj["site_id"])
            if key in self.site_rows:
                self.site_state[key] = obj

    def _load_waivers(self):
        header, rows = read_table(self.path("continuity_waivers.csv"), ",")
        self.dq_rows["continuity_waivers.csv"] = len(rows)
        idx = {name: i for i, name in enumerate(header)}
        i_signed = idx["waiver_signed"]
        self.waiver_signed_missing = 0
        self.waivers = {}
        for row in rows:
            signed = row[i_signed] if i_signed < len(row) else ""
            if signed == "":
                self.waiver_signed_missing += 1
            key = (row[idx["event_id"]], row[idx["site_id"]])
            if key in self.site_rows:
                self.waivers[key] = (row[idx["routine_certificate_pending"]],
                                     row[idx["waiver_status"]], signed)

    def _load_floors(self):
        with open(self.path("segment_floors.json"), encoding="utf-8") as fh:
            entries = json.load(fh)["floors"]
        self.dq_rows["segment_floors.json"] = len(entries)
        self.floors = {}
        for entry in entries:
            region = self.region_of_code[entry["region_code"].upper()]
            segment = self.segment_of_code[entry["segment_code"].upper()]
            self.floors[(entry["event_id"], region, segment)] = (
                self.ticks(int(entry["floor_wh"])),
                int(entry["priority_weight"]),
            )

    def _load_rate_cards(self):
        cards = ET.parse(self.path("rate_cards.xml")).getroot().findall("card")
        self.dq_rows["rate_cards.xml"] = len(cards)
        self.cards = {}
        for card in cards:
            key = (card.get("event"), card.get("site"))
            if key not in self.site_rows:
                continue
            override = card.find("override")
            base = int(card.find("base").text)
            self.cards[key] = (base if override is None else int(override.text),
                               int(card.find("cap").text))

    def _load_recipient_weights(self):
        header, rows = read_table(self.path("recipient_weights.tsv"), "\t")
        self.dq_rows["recipient_weights.tsv"] = len(rows)
        idx = {name: i for i, name in enumerate(header)}
        self.grant_weights = {}
        for row in rows:
            key = (row[idx["event_id"]], row[idx["site_id"]])
            if key in self.site_rows:
                self.grant_weights[key] = int(row[idx["grant_weight"]])

    def _load_pools(self):
        lines = fixed_width_records(self.path("pools.txt"))
        self.dq_rows["pools.txt"] = len(lines)
        self.pools = {}
        for ln in lines:
            region = self.region_of_code[ln[10:14].strip().upper()]
            self.pools[(ln[0:10].strip(), region)] = int(ln[14:26])

    def _load_allowances(self):
        lines = [ln for ln in read_text_lines(self.path("site_allowances.tsv"))
                 if not ln.startswith("#") and ln.strip()]
        rows = [ln.split("\t") for ln in lines[1:]]
        self.dq_rows["site_allowances.tsv"] = len(rows)
        allowance = {}
        draws_from = {}
        for row in rows:
            allowance[row[0]] = int(row[1])
            draws_from[row[0]] = row[2] if len(row) > 2 else ""
        self.allowance_root = {}
        for site in draws_from:
            node = site
            while draws_from[node]:
                node = draws_from[node]
            self.allowance_root[site] = node
        self.allowance_ticks = allowance

    def _load_manifest(self):
        lines = [ln for ln in read_text_lines(self.path("export_manifest.tsv"))
                 if not ln.startswith("#") and ln.strip()]
        self.dq_rows["export_manifest.tsv"] = max(len(lines) - 1, 0)

    # ---------------- derived per site row and per offer ----------------

    def _derive_site_rows(self):
        adders = self.segment_adders
        for key, site in self.site_rows.items():
            state = self.site_state[key]
            pending, status, signed = self.waivers[key]
            waiver_valid = (status == "VALID" and signed == "Y"
                            and site["critical"] == "Y" and site["segment"] == "public")
            if state["safety_hold"]:
                label = "SAFETY_HOLD"
            elif state["cooldown"]:
                label = "COOLDOWN"
            elif pending == "Y" and waiver_valid:
                label = "CONTINUITY_WAIVED"
            elif pending == "Y":
                label = "CERTIFICATE_PENDING"
            else:
                label = "CLEAR"
            site["label"] = label
            site["can_dispatch"] = bool(state["dispatch_authorized"])

            start, cap = self.cards[key]
            rate = (start + adders.get(site["segment"].lower(), 0)
                    + int(self.events[key[0]]["uplift_millicents_per_kwh"]))
            site["cap_binding"] = rate > cap
            site["effective_rate"] = cap if rate > cap else rate

    def _derive_offers(self):
        den = 1000 * self.millicents_per_cent
        wh_per_tick = self.wh_per_tick
        for oid, offer in self.offers.items():
            n = self.events[offer["event_id"]]["interval_count"]
            site = self.site_rows[(offer["event_id"], offer["site_id"])]
            relief = [0] * n
            recovery = [0] * n
            for interval, (rel, rec) in self.profiles.get(oid, {}).items():
                relief[interval - 1] = rel
                recovery[interval - 1] = rec
            rate = site["effective_rate"]
            credit = 0
            for rel, rec in zip(relief, recovery):
                credited = rel - rec
                if credited > 0:
                    credit += round_half_even(credited * wh_per_tick * rate, den)
            offer["relief"] = tuple(relief)
            offer["recovery"] = tuple(recovery)
            offer["total_relief"] = sum(relief)
            offer["total_recovery"] = sum(recovery)
            offer["credit_cents"] = credit
            offer["segment_index"] = self.segment_index[site["segment"]]


def best_portfolio(options, target, weight, relief_cap, recovery_cap, floor_terms,
                   cost_weight, recovery_weight, n_segments, n):
    """Return (selected offers, count of portfolios tied at the best value).

    Portfolios are grown one site at a time and pruned as soon as a ceiling is
    breached, which is sound because relief and recovery are never negative.
    """
    zeros = (0,) * n
    states = [(zeros, zeros, 0, 0, (0,) * n_segments, ())]
    for site_options in options:
        grown = list(states)
        for relief, recovery, bid, rec_total, seg_relief, chosen in states:
            for offer in site_options:
                new_relief = tuple(a + b for a, b in zip(relief, offer["relief"]))
                breached = False
                for value, cap in zip(new_relief, relief_cap):
                    if value > cap:
                        breached = True
                        break
                if breached:
                    continue
                new_recovery = tuple(a + b for a, b in zip(recovery, offer["recovery"]))
                for value, cap in zip(new_recovery, recovery_cap):
                    if value > cap:
                        breached = True
                        break
                if breached:
                    continue
                new_seg = list(seg_relief)
                new_seg[offer["segment_index"]] += offer["total_relief"]
                grown.append((new_relief, new_recovery, bid + offer["bid_cost_cents"],
                              rec_total + offer["total_recovery"], tuple(new_seg),
                              chosen + (offer,)))
        states = grown

    best_key = None
    best_sorted = None
    best_chosen = ()
    tied = 0
    for relief, recovery, bid, rec_total, seg_relief, chosen in states:
        shortfall = 0
        overdelivery = 0
        for value, tgt, wgt in zip(relief, target, weight):
            diff = tgt - value
            if diff > 0:
                shortfall += wgt * diff
            else:
                overdelivery -= diff
        deficit = 0
        for si, floor_ticks, priority in floor_terms:
            gap = floor_ticks - seg_relief[si]
            if gap > 0:
                deficit += priority * gap
        key = (shortfall, deficit, cost_weight * bid + recovery_weight * rec_total,
               overdelivery, len(chosen))
        if best_key is None or key < best_key:
            best_key = key
            best_chosen = chosen
            best_sorted = None
            tied = 1
        elif key == best_key:
            tied += 1
            if best_sorted is None:
                best_sorted = tuple(sorted(o["offer_id"] for o in best_chosen))
            candidate = tuple(sorted(o["offer_id"] for o in chosen))
            if candidate > best_sorted:
                best_sorted = candidate
                best_chosen = chosen
    return best_chosen, tied


def largest_remainder(funded, weights):
    """Share `funded` over `weights` by largest remainder.

    Returns (shares, remainders, residual), the residual being the number of cents
    handed out one at a time.
    """
    total = sum(weights.values())
    shares = {}
    remainders = {}
    for ben, weight in weights.items():
        quotient, remainder = divmod(funded * weight, total)
        shares[ben] = quotient
        remainders[ben] = remainder
    residual = funded - sum(shares.values())
    order = sorted(sorted(weights, reverse=True), key=lambda b: -remainders[b])
    for ben in order[:residual]:
        shares[ben] += 1
    return shares, remainders, residual


def has_remainder_tie(remainders):
    seen = set()
    for value in remainders.values():
        if value == 0:
            continue
        if value in seen:
            return True
        seen.add(value)
    return False


def apportion(funded, weights, claim_rate, minimum):
    """Apportion a funded pool as section 7 prescribes.

    Returns (shares, allocated, residual_cents, residual_tie).
    """
    positive = {b: w for b, w in weights.items() if w > 0}
    if not positive:
        return {}, 0, 0, False
    if sum(w * claim_rate for w in positive.values()) <= funded:
        shares = {b: w * claim_rate for b, w in positive.items()}
        return shares, sum(shares.values()), 0, False
    shares, remainders, residual = largest_remainder(funded, positive)
    qualified = {b: w for b, w in positive.items() if shares[b] >= minimum}
    if len(qualified) == len(positive):
        return shares, sum(shares.values()), residual, has_remainder_tie(remainders)
    if not qualified:
        return {b: 0 for b in positive}, 0, 0, False
    second, remainders2, residual2 = largest_remainder(funded, qualified)
    final = {b: second.get(b, 0) for b in positive}
    return final, sum(final.values()), residual2, has_remainder_tie(remainders2)


class Report:
    def __init__(self, extract):
        self.x = extract
        self.results = {}
        self.tie_decisions = []
        self.cap_binding_count = 0
        self.residual_cents = 0
        self.residual_tie_pool_count = 0
        self.ineligible_offer_count = 0
        self.allowance_blocked_offer_count = 0
        self.empty_candidate_groups = 0
        self.unallocated_pool_count = 0

    def run(self):
        x = self.x
        offers_by_site_row = {}
        for offer in x.offers.values():
            offers_by_site_row.setdefault((offer["event_id"], offer["site_id"]), []).append(offer)
        for key, offers in offers_by_site_row.items():
            offers.sort(key=lambda o: o["offer_id"])
            if not x.site_rows[key]["can_dispatch"]:
                self.ineligible_offer_count += len(offers)

        sites_by_event_region = {}
        for (event_id, site_id), site in x.site_rows.items():
            sites_by_event_region.setdefault((event_id, site["region"]), []).append(site_id)
        for site_ids in sites_by_event_region.values():
            site_ids.sort()

        drawn = {root: 0 for root in x.allowance_ticks}
        carried = {region: 0 for region in x.region_names}

        for event_id in x.season_order:
            event = x.events[event_id]
            n = event["interval_count"]
            cost_weight = int(event["objective"]["cost_weight"])
            recovery_weight = int(event["objective"]["recovery_weight"])
            event_drawn = {}
            for region in x.region_names:
                site_ids = sites_by_event_region.get((event_id, region), ())
                options = []
                candidate_count = 0
                for site_id in site_ids:
                    site_key = (event_id, site_id)
                    if not x.site_rows[site_key]["can_dispatch"]:
                        continue
                    root = x.allowance_root[site_id]
                    remaining = x.allowance_ticks[root] - drawn[root]
                    allowed = []
                    for offer in offers_by_site_row.get(site_key, ()):
                        if offer["total_relief"] > remaining:
                            self.allowance_blocked_offer_count += 1
                        else:
                            allowed.append(offer)
                    if allowed:
                        options.append(allowed)
                        candidate_count += len(allowed)
                if candidate_count == 0:
                    self.empty_candidate_groups += 1

                target = []
                weight = []
                relief_cap = []
                recovery_cap = []
                for t in range(1, n + 1):
                    tgt, wgt = x.targets[(event_id, region, t)]
                    target.append(tgt)
                    weight.append(wgt)
                    rel_cap, rec_cap = x.ceilings[(event_id, region, t)]
                    relief_cap.append(rel_cap)
                    recovery_cap.append(rec_cap)
                floor_terms = []
                floor_ticks_by_segment = {}
                for segment in x.segment_names:
                    ticks, priority = x.floors.get((event_id, region, segment), (0, 0))
                    floor_ticks_by_segment[segment] = ticks
                    if ticks > 0 and priority > 0:
                        floor_terms.append((x.segment_index[segment], ticks, priority))

                chosen, tied = best_portfolio(
                    options, target, weight, relief_cap, recovery_cap, floor_terms,
                    cost_weight, recovery_weight, len(x.segment_names), n)
                if tied >= 2:
                    self.tie_decisions.append({
                        "event_id": event_id,
                        "region": region,
                        "tied_portfolio_count": tied,
                        "selected_offer_ids": sorted(o["offer_id"] for o in chosen),
                    })

                relief = [0] * n
                recovery = [0] * n
                bid_cost = 0
                credit = 0
                for offer in chosen:
                    orel = offer["relief"]
                    orec = offer["recovery"]
                    for t in range(n):
                        relief[t] += orel[t]
                        recovery[t] += orec[t]
                    bid_cost += offer["bid_cost_cents"]
                    credit += offer["credit_cents"]
                    if x.site_rows[(event_id, offer["site_id"])]["cap_binding"]:
                        self.cap_binding_count += 1
                    root = x.allowance_root[offer["site_id"]]
                    event_drawn[root] = event_drawn.get(root, 0) + offer["total_relief"]

                pool = x.pools.get((event_id, region), 0)
                funded = pool + carried[region] - credit
                if funded < 0:
                    funded = 0

                weights = {}
                recipient_count = 0
                for site_id in site_ids:
                    site_key = (event_id, site_id)
                    if site_key not in x.grant_weights:
                        continue
                    recipient_count += 1
                    site = x.site_rows[site_key]
                    value = x.grant_weights[site_key]
                    if site["label"] == "CONTINUITY_WAIVED":
                        value *= 2
                    ben = site["beneficiary_id"]
                    weights[ben] = weights.get(ben, 0) + value
                if recipient_count == 0 or sum(weights.values()) == 0:
                    self.unallocated_pool_count += 1
                    shares, allocated, residual, residual_tie = {}, 0, 0, False
                else:
                    shares, allocated, residual, residual_tie = apportion(
                        funded, weights, x.claim_cents_per_weight, x.minimum_grant_cents)
                self.residual_cents += residual
                if residual_tie:
                    self.residual_tie_pool_count += 1
                carried[region] = funded - allocated

                self.results[(event_id, region)] = {
                    "candidate_offer_count": candidate_count,
                    "chosen": chosen,
                    "relief": relief,
                    "recovery": recovery,
                    "target": target,
                    "bid_cost_cents": bid_cost,
                    "credit_cents": credit,
                    "grant_pool_cents": pool,
                    "grant_funded_cents": funded,
                    "grant_allocated_cents": allocated,
                    "grant_unallocated_cents": funded - allocated,
                    "grants": shares,
                    "floor_ticks": floor_ticks_by_segment,
                    "site_ids": site_ids,
                }
            for root, amount in event_drawn.items():
                drawn[root] += amount

    # ---------------- documents ----------------

    def region_document(self, region):
        x = self.x
        events = []
        totals = {key: 0 for key in (
            "event_count", "candidate_offer_count", "selected_offer_count", "relief_ticks",
            "recovery_ticks", "shortfall_ticks", "overdelivery_ticks", "bid_cost_cents",
            "credit_cents", "grant_pool_cents", "grant_funded_cents", "grant_allocated_cents",
            "grant_unallocated_cents")}
        for event_id in x.event_ids_sorted:
            result = self.results[(event_id, region)]
            intervals = []
            for t, (relief, recovery, target) in enumerate(
                    zip(result["relief"], result["recovery"], result["target"]), start=1):
                gap = target - relief
                intervals.append({
                    "interval": t,
                    "target_ticks": target,
                    "relief_ticks": relief,
                    "recovery_ticks": recovery,
                    "shortfall_ticks": gap if gap > 0 else 0,
                    "overdelivery_ticks": -gap if gap < 0 else 0,
                })
            counts = {label: 0 for label in LABELS}
            for site_id in result["site_ids"]:
                counts[x.site_rows[(event_id, site_id)]["label"]] += 1
            entry = {
                "event_id": event_id,
                "candidate_offer_count": result["candidate_offer_count"],
                "selected_offer_ids": sorted(o["offer_id"] for o in result["chosen"]),
                "intervals": intervals,
                "bid_cost_cents": result["bid_cost_cents"],
                "credit_cents": result["credit_cents"],
                "grant_pool_cents": result["grant_pool_cents"],
                "grant_funded_cents": result["grant_funded_cents"],
                "grant_allocated_cents": result["grant_allocated_cents"],
                "grant_unallocated_cents": result["grant_unallocated_cents"],
                "grants": [{"beneficiary_id": ben, "cents": result["grants"][ben]}
                           for ben in sorted(result["grants"])],
                "compliance_counts": counts,
            }
            events.append(entry)
            totals["event_count"] += 1
            totals["candidate_offer_count"] += entry["candidate_offer_count"]
            totals["selected_offer_count"] += len(entry["selected_offer_ids"])
            for key in ("relief_ticks", "recovery_ticks", "shortfall_ticks",
                        "overdelivery_ticks"):
                totals[key] += sum(i[key] for i in intervals)
            for key in ("bid_cost_cents", "credit_cents", "grant_pool_cents",
                        "grant_funded_cents", "grant_allocated_cents",
                        "grant_unallocated_cents"):
                totals[key] += entry[key]
        return {"region": region, "events": events, "totals": totals}

    def segment_document(self, segment):
        x = self.x
        entries = []
        totals = {key: 0 for key in ("selected_offer_count", "relief_ticks", "recovery_ticks",
                                     "bid_cost_cents", "credit_cents", "floor_ticks")}
        for event_id in x.event_ids_sorted:
            for region in x.region_names:
                result = self.results[(event_id, region)]
                offer_ids = []
                relief = recovery = bid_cost = credit = 0
                for offer in result["chosen"]:
                    if x.site_rows[(event_id, offer["site_id"])]["segment"] != segment:
                        continue
                    offer_ids.append(offer["offer_id"])
                    relief += offer["total_relief"]
                    recovery += offer["total_recovery"]
                    bid_cost += offer["bid_cost_cents"]
                    credit += offer["credit_cents"]
                floor_ticks = result["floor_ticks"][segment]
                if floor_ticks == 0:
                    attainment = 10000
                else:
                    attainment = min(10000, round_half_up(10000 * relief, floor_ticks))
                entries.append({
                    "event_id": event_id,
                    "region": region,
                    "selected_offer_ids": sorted(offer_ids),
                    "relief_ticks": relief,
                    "recovery_ticks": recovery,
                    "bid_cost_cents": bid_cost,
                    "credit_cents": credit,
                    "floor_ticks": floor_ticks,
                    "floor_attainment_bp": attainment,
                })
                totals["selected_offer_count"] += len(offer_ids)
                totals["relief_ticks"] += relief
                totals["recovery_ticks"] += recovery
                totals["bid_cost_cents"] += bid_cost
                totals["credit_cents"] += credit
                totals["floor_ticks"] += floor_ticks
        return {"segment": segment, "event_regions": entries, "totals": totals}

    def summary_document(self, region_docs, segment_docs):
        x = self.x
        keys = ("candidate_offer_count", "selected_offer_count", "relief_ticks", "recovery_ticks",
                "shortfall_ticks", "overdelivery_ticks", "bid_cost_cents", "credit_cents",
                "grant_pool_cents", "grant_funded_cents", "grant_allocated_cents",
                "grant_unallocated_cents")
        document = {key: sum(doc["totals"][key] for doc in region_docs.values()) for key in keys}
        document["event_count"] = len(x.events)
        document["event_region_count"] = len(x.events) * len(x.region_names)
        document["site_count"] = len(x.site_rows)
        document["regions"] = {
            region: {key: doc["totals"][key] for key in (
                "selected_offer_count", "relief_ticks", "bid_cost_cents", "credit_cents",
                "grant_allocated_cents")}
            for region, doc in region_docs.items()}
        document["segments"] = {
            segment: {key: doc["totals"][key] for key in (
                "selected_offer_count", "relief_ticks", "bid_cost_cents", "credit_cents")}
            for segment, doc in segment_docs.items()}
        return document

    def policy_audit_document(self):
        x = self.x
        counts = {label: 0 for label in LABELS}
        site_labels = []
        for key in sorted(x.site_rows):
            label = x.site_rows[key]["label"]
            counts[label] += 1
            site_labels.append({"event_id": key[0], "site_id": key[1], "label": label})
        return {
            "compliance_counts": counts,
            "site_labels": site_labels,
            "tie_decisions": sorted(self.tie_decisions,
                                    key=lambda d: (d["event_id"], d["region"])),
            "cap_binding_count": self.cap_binding_count,
            "residual_cents": self.residual_cents,
            "residual_tie_pool_count": self.residual_tie_pool_count,
        }

    def data_quality_document(self):
        x = self.x
        zero_floor_count = 0
        for (event_id, region), result in self.results.items():
            for segment in x.segment_names:
                if result["floor_ticks"][segment] == 0:
                    zero_floor_count += 1
        return {
            "rows": dict(x.dq_rows),
            "orphan_offer_rows": x.orphan_offer_rows,
            "orphan_profile_rows": x.orphan_profile_rows,
            "out_of_range_profile_rows": x.out_of_range_profile_rows,
            "duplicate_profile_rows": x.duplicate_profile_rows,
            "unknown_region_site_rows": x.unknown_region_site_rows,
            "waiver_signed_missing": x.waiver_signed_missing,
            "ineligible_offer_count": self.ineligible_offer_count,
            "allowance_blocked_offer_count": self.allowance_blocked_offer_count,
            "empty_candidate_groups": self.empty_candidate_groups,
            "zero_floor_count": zero_floor_count,
            "unallocated_pool_count": self.unallocated_pool_count,
        }


def write_json(path, document):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(document, fh, sort_keys=True, indent=1)
        fh.write("\n")


def main(argv):
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    extract = Extract(data_dir)
    report = Report(extract)
    report.run()

    region_docs = {region: report.region_document(region) for region in extract.region_names}
    segment_docs = {segment: report.segment_document(segment)
                    for segment in extract.segment_names}
    for region, document in region_docs.items():
        write_json(os.path.join(out_dir, "region_%s.json" % region), document)
    for segment, document in segment_docs.items():
        write_json(os.path.join(out_dir, "segment_%s.json" % segment), document)
    write_json(os.path.join(out_dir, "summary.json"),
               report.summary_document(region_docs, segment_docs))
    write_json(os.path.join(out_dir, "policy_audit.json"), report.policy_audit_document())
    write_json(os.path.join(out_dir, "data_quality.json"), report.data_quality_document())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
