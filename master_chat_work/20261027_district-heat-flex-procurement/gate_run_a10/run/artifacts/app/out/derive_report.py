#!/usr/bin/env python3
"""Derive the winter demand-response programme reports from a season extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

from __future__ import annotations

import configparser
import csv
import datetime
import json
import os
import sys
import xml.etree.ElementTree as ET

LABELS = (
    "SAFETY_HOLD",
    "COOLDOWN",
    "CONTINUITY_WAIVED",
    "CERTIFICATE_PENDING",
    "CLEAR",
)


def to_ticks(wh, wh_per_tick):
    """A record's Wh value as ticks, rounded half up."""
    return (2 * wh + wh_per_tick) // (2 * wh_per_tick)


def div_half_up(num, den):
    return (2 * num + den) // (2 * den)


def div_half_even(num, den):
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2 == 1):
        q += 1
    return q




def read_rows(path, delimiter):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def read_commented_rows(path):
    """Header and data rows of a TSV file whose comment lines start with '#'."""
    with open(path, encoding="utf-8") as fh:
        lines = [ln.rstrip("\n").rstrip("\r") for ln in fh if not ln.startswith("#")]
    lines = [ln for ln in lines if ln.strip() != ""]
    if not lines:
        return [], []
    return lines[0].split("\t"), [ln.split("\t") for ln in lines[1:]]


def fixed_width_lines(path):
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            if ln.startswith("#"):
                continue
            ln = ln.rstrip("\n").rstrip("\r")
            if ln.strip() == "":
                continue
            yield ln


class Offer:
    __slots__ = ("oid", "event_id", "site_id", "bid", "rel", "rec",
                 "tot_rel", "tot_rec", "seg")

    def __init__(self, oid, event_id, site_id, bid, ic):
        self.oid = oid
        self.event_id = event_id
        self.site_id = site_id
        self.bid = bid
        self.rel = [0] * ic
        self.rec = [0] * ic
        self.tot_rel = 0
        self.tot_rec = 0
        self.seg = -1


class Extract:
    """One season extract, parsed and reduced to the facts the reports need."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.rows = {}
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
        self._load_weights()
        self._load_pools()
        self._load_allowances()
        self._load_manifest()
        self._derive_labels()
        self._derive_rates()

    def path(self, name):
        return os.path.join(self.dir, name)

    def region_name(self, code):
        return self.region_of_code.get(code.strip().lower())

    def segment_name(self, code):
        return self.segment_of_code.get(str(code).strip().lower())

    # ---------------- loading ----------------

    def _load_program(self):
        cp = configparser.ConfigParser()
        with open(self.path("program.ini"), encoding="utf-8") as fh:
            cp.read_file(fh)
        self.wh_per_tick = cp.getint("units", "wh_per_tick")
        self.millicents_per_cent = cp.getint("units", "millicents_per_cent")
        self.region_of_code = dict(cp["region_codes"])
        self.segment_of_code = dict(cp["segment_codes"])
        adders = (
            dict(cp["segment_rate_adders"])
            if cp.has_section("segment_rate_adders")
            else {}
        )
        self.claim_cents_per_weight = cp.getint("grants", "claim_cents_per_weight")
        self.minimum_grant_cents = cp.getint("grants", "minimum_grant_cents")

        self.regions = sorted(set(self.region_of_code.values()))
        self.segments = sorted(set(self.segment_of_code.values()))
        self.seg_index = {name: i for i, name in enumerate(self.segments)}
        self.n_seg = len(self.segments)
        self.seg_adder = [int(adders.get(name.lower(), 0)) for name in self.segments]

    def _load_events(self):
        with open(self.path("events.json"), encoding="utf-8") as fh:
            events = json.load(fh)
        self.rows["events.json"] = len(events)
        self.events = {}
        for ev in events:
            self.events[ev["event_id"]] = {
                "event_id": ev["event_id"],
                "interval_count": int(ev["interval_count"]),
                "cost_weight": int(ev["objective"]["cost_weight"]),
                "recovery_weight": int(ev["objective"]["recovery_weight"]),
                "start": datetime.datetime.fromisoformat(ev["dispatch_start"]),
                "uplift": int(ev["uplift_millicents_per_kwh"]),
            }
        self.event_ids_sorted = sorted(self.events)
        by_start = {}
        for eid, ev in self.events.items():
            by_start.setdefault(ev["start"], []).append(eid)
        self.season_order = [
            eid
            for start in sorted(by_start)
            for eid in sorted(by_start[start], reverse=True)
        ]

    def _load_sites(self):
        rows = read_rows(self.path("sites.csv"), ",")
        self.rows["sites.csv"] = len(rows)
        self.sites = {}
        self.unknown_region_site_rows = 0
        for r in rows:
            region = self.region_name(r["region_code"])
            if region is None:
                self.unknown_region_site_rows += 1
                continue
            seg_name = self.segment_name(r["segment_code"])
            self.sites[(r["event_id"], r["site_id"])] = {
                "event_id": r["event_id"],
                "site_id": r["site_id"],
                "region": region,
                "segment": seg_name,
                "seg_idx": self.seg_index.get(seg_name, self.n_seg),
                "beneficiary_id": r["beneficiary_id"],
                "critical": r["critical"].strip() == "Y",
            }

    def _load_offers(self):
        rows = read_rows(self.path("offers.csv"), ",")
        self.rows["offers.csv"] = len(rows)
        self.offers = {}
        # every offer_id of offers.csv with the interval count of its event, so
        # that profile rows of orphan offers are still classified by their kind
        self.offer_intervals = {}
        self.orphan_offer_rows = 0
        for r in rows:
            oid = r["offer_id"]
            event_id = r["event_id"]
            ic = self.events[event_id]["interval_count"]
            self.offer_intervals[oid] = ic
            key = (event_id, r["site_id"])
            if key not in self.sites:
                self.orphan_offer_rows += 1
                continue
            off = Offer(oid, event_id, r["site_id"], int(r["bid_cost_cents"]), ic)
            off.seg = self.sites[key]["seg_idx"]
            self.offers[oid] = off

    def _load_profiles(self):
        self.orphan_profile_rows = 0
        self.out_of_range_profile_rows = 0
        self.duplicate_profile_rows = 0
        wpt = self.wh_per_tick
        seen = set()
        count = 0
        with open(self.path("profiles.tsv"), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                count += 1
                oid = r["offer_id"]
                ic = self.offer_intervals.get(oid)
                if ic is None:
                    self.orphan_profile_rows += 1
                    continue
                interval = int(r["interval"])
                if interval < 1 or interval > ic:
                    self.out_of_range_profile_rows += 1
                    continue
                key = (oid, interval)
                if key in seen:
                    self.duplicate_profile_rows += 1
                    continue
                seen.add(key)
                off = self.offers.get(oid)
                if off is None:
                    continue
                mult = int(r["register_multiplier"])
                off.rel[interval - 1] = to_ticks(int(r["relief_wh"]) * mult, wpt)
                off.rec[interval - 1] = to_ticks(int(r["recovery_wh"]) * mult, wpt)
        self.rows["profiles.tsv"] = count
        for off in self.offers.values():
            off.tot_rel = sum(off.rel)
            off.tot_rec = sum(off.rec)

    def _load_targets(self):
        rows = read_rows(self.path("targets.tsv"), "\t")
        self.rows["targets.tsv"] = len(rows)
        self.targets = {}
        wpt = self.wh_per_tick
        for r in rows:
            region = self.region_name(r["region_code"])
            if region is None:
                continue
            self.targets[(r["event_id"], region, int(r["interval"]))] = (
                to_ticks(int(r["target_wh"]), wpt),
                int(r["shortfall_weight"]),
            )

    def _load_feeder_limits(self):
        self.ceilings = {}
        wpt = self.wh_per_tick
        count = 0
        for ln in fixed_width_lines(self.path("feeder_limits.txt")):
            count += 1
            event_id = ln[0:10].strip()
            region = self.region_name(ln[10:14])
            interval = int(ln[14:17])
            relief = int(ln[17:27])
            recovery = int(ln[27:37])
            if region is None:
                continue
            self.ceilings[(event_id, region, interval)] = (
                to_ticks(relief, wpt),
                to_ticks(recovery, wpt),
            )
        self.rows["feeder_limits.txt"] = count

    def _load_site_state(self):
        self.state = {}
        count = 0
        with open(self.path("site_state.jsonl"), encoding="utf-8") as fh:
            for ln in fh:
                if ln.strip() == "":
                    continue
                count += 1
                d = json.loads(ln)
                key = (d["event_id"], d["site_id"])
                if key not in self.sites:
                    continue
                self.state[key] = (
                    bool(d["dispatch_authorized"]),
                    bool(d["safety_hold"]),
                    bool(d["cooldown"]),
                )
        self.rows["site_state.jsonl"] = count

    def _load_waivers(self):
        rows = read_rows(self.path("continuity_waivers.csv"), ",")
        self.rows["continuity_waivers.csv"] = len(rows)
        self.waiver_signed_missing = 0
        self.waivers = {}
        for r in rows:
            signed = (r.get("waiver_signed") or "").strip()
            if signed == "":
                self.waiver_signed_missing += 1
            key = (r["event_id"], r["site_id"])
            if key not in self.sites:
                continue
            self.waivers[key] = (
                r["routine_certificate_pending"].strip() == "Y",
                r["waiver_status"].strip(),
                signed,
            )

    def _load_floors(self):
        with open(self.path("segment_floors.json"), encoding="utf-8") as fh:
            floors = json.load(fh)["floors"]
        self.rows["segment_floors.json"] = len(floors)
        self.floors = {}
        wpt = self.wh_per_tick
        for f in floors:
            region = self.region_name(f["region_code"])
            seg = self.segment_name(f["segment_code"])
            if region is None or seg is None:
                continue
            self.floors[(f["event_id"], region, seg)] = (
                to_ticks(int(f["floor_wh"]), wpt),
                int(f["priority_weight"]),
            )

    def _load_rate_cards(self):
        cards = ET.parse(self.path("rate_cards.xml")).getroot().findall("card")
        self.rows["rate_cards.xml"] = len(cards)
        self.cards = {}
        for c in cards:
            key = (c.get("event"), c.get("site"))
            if key not in self.sites:
                continue
            base = int(c.find("base").text)
            override = c.find("override")
            self.cards[key] = (
                base if override is None else int(override.text),
                int(c.find("cap").text),
            )

    def _load_weights(self):
        rows = read_rows(self.path("recipient_weights.tsv"), "\t")
        self.rows["recipient_weights.tsv"] = len(rows)
        self.weights = {}
        for r in rows:
            key = (r["event_id"], r["site_id"])
            if key not in self.sites:
                continue
            self.weights[key] = int(r["grant_weight"])

    def _load_pools(self):
        self.pools = {}
        count = 0
        for ln in fixed_width_lines(self.path("pools.txt")):
            count += 1
            event_id = ln[0:10].strip()
            region = self.region_name(ln[10:14])
            cents = int(ln[14:26])
            if region is None:
                continue
            self.pools[(event_id, region)] = cents
        self.rows["pools.txt"] = count

    def _load_allowances(self):
        header, rows = read_commented_rows(self.path("site_allowances.tsv"))
        self.rows["site_allowances.tsv"] = len(rows)
        idx = {name: i for i, name in enumerate(header)}
        raw = {}
        for r in rows:
            draws = r[idx["draws_from"]].strip() if len(r) > idx["draws_from"] else ""
            raw[r[idx["site_id"]]] = (int(r[idx["allowance_ticks"]]), draws)
        self.allowance_root = {}
        self.allowance_ticks = {}
        for site in raw:
            cur = site
            seen = {cur}
            while raw[cur][1] and raw[cur][1] in raw:
                cur = raw[cur][1]
                if cur in seen:
                    break
                seen.add(cur)
            self.allowance_root[site] = cur
            self.allowance_ticks[cur] = raw[cur][0]

    def _load_manifest(self):
        _, rows = read_commented_rows(self.path("export_manifest.tsv"))
        self.rows["export_manifest.tsv"] = len(rows)

    # ---------------- derived facts ----------------

    def _derive_labels(self):
        self.labels = {}
        for key, site in self.sites.items():
            authorized, hold, cooldown = self.state.get(key, (False, False, False))
            pending, status, signed = self.waivers.get(key, (False, "NONE", ""))
            site["authorized"] = authorized
            waiver_valid = (
                status == "VALID"
                and signed == "Y"
                and site["critical"]
                and site["segment"] == "public"
            )
            if hold:
                label = "SAFETY_HOLD"
            elif cooldown:
                label = "COOLDOWN"
            elif pending and waiver_valid:
                label = "CONTINUITY_WAIVED"
            elif pending:
                label = "CERTIFICATE_PENDING"
            else:
                label = "CLEAR"
            self.labels[key] = label

    def _derive_rates(self):
        for key, site in self.sites.items():
            start, cap = self.cards.get(key, (0, 0))
            adder = self.seg_adder[site["seg_idx"]] if site["seg_idx"] < self.n_seg else 0
            rate = start + adder + self.events[site["event_id"]]["uplift"]
            site["cap_binding"] = rate > cap
            site["rate"] = cap if rate > cap else rate


def best_portfolio(ic, opts, target, weight, rceil, cceil, floor_terms, cw, rw, n_seg):
    """Enumerate feasible portfolios; return (selected offer ids, tie count).

    A portfolio holds at most one candidate offer per site. Adding an offer never
    lowers relief or recovery, so a branch that breaks a ceiling is pruned whole.

    Each component of the objective is also bounded from below over a branch: the
    sites still to decide can add at most their largest relief, and cost, recovery
    and offer count only grow. Bounding the components one by one bounds the whole
    key in lexicographic order, so a branch whose bound is above the best key so
    far holds no optimal and no tied portfolio and is dropped.
    """
    n = len(opts)
    relief = [0] * ic
    recov = [0] * ic
    segrel = [0] * (n_seg + 1)
    chosen = []
    rng = range(ic)
    best_key = None
    best_sel = ()
    tie_count = 0

    suf_rel = [[0] * ic for _ in range(n + 1)]
    suf_seg = [[0] * (n_seg + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        nxt_rel = suf_rel[i + 1]
        cur_rel = suf_rel[i]
        for t in rng:
            cur_rel[t] = nxt_rel[t] + max(off.rel[t] for off in opts[i])
        suf_seg[i] = list(suf_seg[i + 1])
        suf_seg[i][opts[i][0].seg] += max(off.tot_rel for off in opts[i])

    def walk(i, bid, rec_tot, nsel):
        nonlocal best_key, best_sel, tie_count
        lb1 = 0
        lb4 = 0
        sr = suf_rel[i]
        for t in rng:
            r = relief[t]
            tg = target[t]
            d = tg - r - sr[t]
            if d > 0:
                lb1 += weight[t] * d
            elif r > tg:
                lb4 += r - tg
        lb2 = 0
        ss = suf_seg[i]
        for sidx, fticks, pw in floor_terms:
            d = fticks - segrel[sidx] - ss[sidx]
            if d > 0:
                lb2 += pw * d
        key = (lb1, lb2, cw * bid + rw * rec_tot, lb4, nsel)
        if best_key is not None and key > best_key:
            return
        if i == n:
            # with no site left to decide the bound is the portfolio's own key
            if best_key is None or key < best_key:
                best_key = key
                best_sel = tuple(sorted(chosen))
                tie_count = 1
            else:
                tie_count += 1
                cand = tuple(sorted(chosen))
                if cand > best_sel:
                    best_sel = cand
            return
        walk(i + 1, bid, rec_tot, nsel)
        for off in opts[i]:
            orel = off.rel
            orec = off.rec
            ok = True
            for t in rng:
                if relief[t] + orel[t] > rceil[t] or recov[t] + orec[t] > cceil[t]:
                    ok = False
                    break
            if not ok:
                continue
            for t in rng:
                relief[t] += orel[t]
                recov[t] += orec[t]
            segrel[off.seg] += off.tot_rel
            chosen.append(off.oid)
            walk(i + 1, bid + off.bid, rec_tot + off.tot_rec, nsel + 1)
            chosen.pop()
            segrel[off.seg] -= off.tot_rel
            for t in rng:
                relief[t] -= orel[t]
                recov[t] -= orec[t]

    walk(0, 0, 0, 0)
    return best_sel, tie_count


def largest_remainder(funded, entries):
    """Share `funded` cents over (beneficiary_id, weight) pairs with weight > 0.

    Returns (shares, cents handed out by remainder, residual tie flag).
    """
    total_w = sum(w for _, w in entries)
    shares = {}
    rems = []
    for bid, w in entries:
        q, r = divmod(funded * w, total_w)
        shares[bid] = q
        rems.append((r, bid))
    left = funded - sum(shares.values())
    rems.sort(key=lambda t: (t[0], t[1]), reverse=True)
    for i in range(left):
        shares[rems[i][1]] += 1
    nonzero = [r for r, _ in rems if r != 0]
    tie = len(nonzero) != len(set(nonzero))
    return shares, left, tie


def allocate_grants(ex, funded, beneficiary_weights):
    """Returns (shares, allocated cents, residual cents, residual tie flag)."""
    positive = sorted((b, w) for b, w in beneficiary_weights.items() if w > 0)
    if not positive:
        return {}, 0, 0, False
    claims = {b: w * ex.claim_cents_per_weight for b, w in positive}
    if sum(claims.values()) <= funded:
        return claims, sum(claims.values()), 0, False
    shares, residual, tie = largest_remainder(funded, positive)
    keep = [(b, w) for b, w in positive if shares[b] >= ex.minimum_grant_cents]
    if len(keep) == len(positive):
        return shares, funded, residual, tie
    if not keep:
        return {b: 0 for b, _ in positive}, 0, 0, False
    shares2, residual2, tie2 = largest_remainder(funded, keep)
    final = {b: 0 for b, _ in positive}
    final.update(shares2)
    return final, funded, residual2, tie2


REGION_TOTAL_KEYS = (
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


def derive(ex):
    """Run the season: candidates, portfolios, credits and grants per event-region."""
    regions = ex.regions
    n_seg = ex.n_seg
    denom = 1000 * ex.millicents_per_cent
    wpt = ex.wh_per_tick

    offers_by_er = {}
    for off in ex.offers.values():
        region = ex.sites[(off.event_id, off.site_id)]["region"]
        offers_by_er.setdefault((off.event_id, region), []).append(off)
    sites_by_er = {}
    for site in ex.sites.values():
        sites_by_er.setdefault((site["event_id"], site["region"]), []).append(site)

    stats = {
        "ineligible_offer_count": 0,
        "allowance_blocked_offer_count": 0,
        "empty_candidate_groups": 0,
        "cap_binding_count": 0,
        "residual_cents": 0,
        "residual_tie_pool_count": 0,
        "unallocated_pool_count": 0,
    }
    tie_decisions = []
    allowance_used = dict.fromkeys(ex.allowance_ticks, 0)
    carried = dict.fromkeys(regions, 0)
    results = {}

    for event_id in ex.season_order:
        event = ex.events[event_id]
        ic = event["interval_count"]
        cw = event["cost_weight"]
        rw = event["recovery_weight"]
        relief_by_root = {}

        for region in regions:
            key_er = (event_id, region)
            site_rows = sites_by_er.get(key_er, [])

            candidates_by_site = {}
            candidate_count = 0
            for off in offers_by_er.get(key_er, []):
                if not ex.sites[(off.event_id, off.site_id)]["authorized"]:
                    stats["ineligible_offer_count"] += 1
                    continue
                root = ex.allowance_root.get(off.site_id, off.site_id)
                remaining = ex.allowance_ticks.get(root, 0) - allowance_used.get(root, 0)
                if off.tot_rel > remaining:
                    stats["allowance_blocked_offer_count"] += 1
                    continue
                candidates_by_site.setdefault(off.site_id, []).append(off)
                candidate_count += 1
            if candidate_count == 0:
                stats["empty_candidate_groups"] += 1

            target = [0] * ic
            weight = [0] * ic
            rceil = [0] * ic
            cceil = [0] * ic
            for t in range(ic):
                target[t], weight[t] = ex.targets.get((event_id, region, t + 1), (0, 0))
                rceil[t], cceil[t] = ex.ceilings.get((event_id, region, t + 1), (0, 0))

            floor_ticks_by_seg = [0] * n_seg
            floor_terms = []
            for i, seg_name in enumerate(ex.segments):
                fticks, pw = ex.floors.get((event_id, region, seg_name), (0, 0))
                floor_ticks_by_seg[i] = fticks
                if fticks > 0 and pw > 0:
                    floor_terms.append((i, fticks, pw))

            opts = [candidates_by_site[s] for s in sorted(candidates_by_site)]
            selected_ids, tie_count = best_portfolio(
                ic, opts, target, weight, rceil, cceil, floor_terms, cw, rw, n_seg
            )
            if tie_count >= 2:
                tie_decisions.append(
                    {
                        "event_id": event_id,
                        "region": region,
                        "tied_portfolio_count": tie_count,
                        "selected_offer_ids": list(selected_ids),
                    }
                )

            relief = [0] * ic
            recov = [0] * ic
            bid_cost = 0
            credit_total = 0
            seg_stats = [
                {"ids": [], "relief": 0, "recovery": 0, "bid": 0, "credit": 0}
                for _ in range(n_seg)
            ]
            for oid in selected_ids:
                off = ex.offers[oid]
                site = ex.sites[(off.event_id, off.site_id)]
                rate = site["rate"]
                credit = 0
                for t in range(ic):
                    relief[t] += off.rel[t]
                    recov[t] += off.rec[t]
                    credited = off.rel[t] - off.rec[t]
                    if credited > 0:
                        credit += div_half_even(credited * wpt * rate, denom)
                credit_total += credit
                bid_cost += off.bid
                if site["cap_binding"]:
                    stats["cap_binding_count"] += 1
                if off.seg < n_seg:
                    st = seg_stats[off.seg]
                    st["ids"].append(oid)
                    st["relief"] += off.tot_rel
                    st["recovery"] += off.tot_rec
                    st["bid"] += off.bid
                    st["credit"] += credit
                root = ex.allowance_root.get(off.site_id, off.site_id)
                relief_by_root[root] = relief_by_root.get(root, 0) + off.tot_rel

            intervals = []
            shortfall_total = 0
            over_total = 0
            for t in range(ic):
                gap = target[t] - relief[t]
                short = gap if gap > 0 else 0
                over = -gap if gap < 0 else 0
                shortfall_total += short
                over_total += over
                intervals.append(
                    {
                        "interval": t + 1,
                        "target_ticks": target[t],
                        "relief_ticks": relief[t],
                        "recovery_ticks": recov[t],
                        "shortfall_ticks": short,
                        "overdelivery_ticks": over,
                    }
                )

            pool = ex.pools.get(key_er, 0)
            funded = pool + carried[region] - credit_total
            if funded < 0:
                funded = 0

            beneficiary_weights = {}
            recipients = 0
            for site in site_rows:
                skey = (site["event_id"], site["site_id"])
                if skey not in ex.weights:
                    continue
                recipients += 1
                w = ex.weights[skey]
                if ex.labels[skey] == "CONTINUITY_WAIVED":
                    w *= 2
                bid_key = site["beneficiary_id"]
                beneficiary_weights[bid_key] = beneficiary_weights.get(bid_key, 0) + w
            if recipients == 0 or sum(beneficiary_weights.values()) == 0:
                stats["unallocated_pool_count"] += 1
                shares, allocated, residual, tie = {}, 0, 0, False
            else:
                shares, allocated, residual, tie = allocate_grants(
                    ex, funded, beneficiary_weights
                )
            stats["residual_cents"] += residual
            if tie:
                stats["residual_tie_pool_count"] += 1
            unallocated = funded - allocated
            carried[region] = unallocated

            results[key_er] = {
                "candidate_offer_count": candidate_count,
                "selected_offer_ids": list(selected_ids),
                "intervals": intervals,
                "relief_total": sum(relief),
                "recovery_total": sum(recov),
                "shortfall_total": shortfall_total,
                "over_total": over_total,
                "bid_cost_cents": bid_cost,
                "credit_cents": credit_total,
                "grant_pool_cents": pool,
                "grant_funded_cents": funded,
                "grant_allocated_cents": allocated,
                "grant_unallocated_cents": unallocated,
                "grants": [
                    {"beneficiary_id": b, "cents": shares.get(b, 0)}
                    for b in sorted(b for b, w in beneficiary_weights.items() if w > 0)
                ],
                "compliance_counts": compliance_counts(ex, site_rows),
                "seg_stats": seg_stats,
                "floor_ticks": floor_ticks_by_seg,
            }

        for root, used in relief_by_root.items():
            allowance_used[root] = allowance_used.get(root, 0) + used

    return results, tie_decisions, stats


def compliance_counts(ex, site_rows):
    counts = dict.fromkeys(LABELS, 0)
    for site in site_rows:
        counts[ex.labels[(site["event_id"], site["site_id"])]] += 1
    return counts


def run(data_dir, out_dir):
    ex = Extract(data_dir)
    results, tie_decisions, stats = derive(ex)

    os.makedirs(out_dir, exist_ok=True)

    def write(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, sort_keys=True, separators=(",", ":"))
            fh.write("\n")

    event_ids = ex.event_ids_sorted
    grand = dict.fromkeys(REGION_TOTAL_KEYS, 0)
    region_summary = {}

    for region in ex.regions:
        events_out = []
        totals = dict.fromkeys(REGION_TOTAL_KEYS, 0)
        for event_id in event_ids:
            res = results[(event_id, region)]
            events_out.append(
                {
                    "event_id": event_id,
                    "candidate_offer_count": res["candidate_offer_count"],
                    "selected_offer_ids": res["selected_offer_ids"],
                    "intervals": res["intervals"],
                    "bid_cost_cents": res["bid_cost_cents"],
                    "credit_cents": res["credit_cents"],
                    "grant_pool_cents": res["grant_pool_cents"],
                    "grant_funded_cents": res["grant_funded_cents"],
                    "grant_allocated_cents": res["grant_allocated_cents"],
                    "grant_unallocated_cents": res["grant_unallocated_cents"],
                    "grants": res["grants"],
                    "compliance_counts": res["compliance_counts"],
                }
            )
            totals["candidate_offer_count"] += res["candidate_offer_count"]
            totals["selected_offer_count"] += len(res["selected_offer_ids"])
            totals["relief_ticks"] += res["relief_total"]
            totals["recovery_ticks"] += res["recovery_total"]
            totals["shortfall_ticks"] += res["shortfall_total"]
            totals["overdelivery_ticks"] += res["over_total"]
            for key in (
                "bid_cost_cents",
                "credit_cents",
                "grant_pool_cents",
                "grant_funded_cents",
                "grant_allocated_cents",
                "grant_unallocated_cents",
            ):
                totals[key] += res[key]
        write(
            "region_%s.json" % region,
            {
                "region": region,
                "events": events_out,
                "totals": dict(totals, event_count=len(event_ids)),
            },
        )
        for key in REGION_TOTAL_KEYS:
            grand[key] += totals[key]
        region_summary[region] = {
            "selected_offer_count": totals["selected_offer_count"],
            "relief_ticks": totals["relief_ticks"],
            "bid_cost_cents": totals["bid_cost_cents"],
            "credit_cents": totals["credit_cents"],
            "grant_allocated_cents": totals["grant_allocated_cents"],
        }

    segment_summary = {}
    for i, seg_name in enumerate(ex.segments):
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
        for event_id in event_ids:
            for region in ex.regions:
                res = results[(event_id, region)]
                st = res["seg_stats"][i]
                floor_ticks = res["floor_ticks"][i]
                relief = st["relief"]
                if floor_ticks == 0:
                    bp = 10000
                else:
                    bp = min(10000, div_half_up(10000 * relief, floor_ticks))
                entries.append(
                    {
                        "event_id": event_id,
                        "region": region,
                        "selected_offer_ids": sorted(st["ids"]),
                        "relief_ticks": relief,
                        "recovery_ticks": st["recovery"],
                        "bid_cost_cents": st["bid"],
                        "credit_cents": st["credit"],
                        "floor_ticks": floor_ticks,
                        "floor_attainment_bp": bp,
                    }
                )
                totals["selected_offer_count"] += len(st["ids"])
                totals["relief_ticks"] += relief
                totals["recovery_ticks"] += st["recovery"]
                totals["bid_cost_cents"] += st["bid"]
                totals["credit_cents"] += st["credit"]
                totals["floor_ticks"] += floor_ticks
        write(
            "segment_%s.json" % seg_name,
            {"segment": seg_name, "event_regions": entries, "totals": totals},
        )
        segment_summary[seg_name] = {
            "selected_offer_count": totals["selected_offer_count"],
            "relief_ticks": totals["relief_ticks"],
            "bid_cost_cents": totals["bid_cost_cents"],
            "credit_cents": totals["credit_cents"],
        }

    write(
        "summary.json",
        {
            "event_count": len(event_ids),
            "event_region_count": len(event_ids) * len(ex.regions),
            "site_count": len(ex.sites),
            "candidate_offer_count": grand["candidate_offer_count"],
            "selected_offer_count": grand["selected_offer_count"],
            "relief_ticks": grand["relief_ticks"],
            "recovery_ticks": grand["recovery_ticks"],
            "shortfall_ticks": grand["shortfall_ticks"],
            "overdelivery_ticks": grand["overdelivery_ticks"],
            "bid_cost_cents": grand["bid_cost_cents"],
            "credit_cents": grand["credit_cents"],
            "grant_pool_cents": grand["grant_pool_cents"],
            "grant_funded_cents": grand["grant_funded_cents"],
            "grant_allocated_cents": grand["grant_allocated_cents"],
            "grant_unallocated_cents": grand["grant_unallocated_cents"],
            "regions": region_summary,
            "segments": segment_summary,
        },
    )

    write(
        "policy_audit.json",
        {
            "compliance_counts": compliance_counts(ex, ex.sites.values()),
            "site_labels": [
                {"event_id": e, "site_id": s, "label": ex.labels[(e, s)]}
                for e, s in sorted(ex.sites)
            ],
            "tie_decisions": sorted(
                tie_decisions, key=lambda d: (d["event_id"], d["region"])
            ),
            "cap_binding_count": stats["cap_binding_count"],
            "residual_cents": stats["residual_cents"],
            "residual_tie_pool_count": stats["residual_tie_pool_count"],
        },
    )

    zero_floor_count = 0
    for event_id in event_ids:
        for region in ex.regions:
            for seg_name in ex.segments:
                if ex.floors.get((event_id, region, seg_name), (0, 0))[0] == 0:
                    zero_floor_count += 1

    write(
        "data_quality.json",
        {
            "rows": ex.rows,
            "orphan_offer_rows": ex.orphan_offer_rows,
            "orphan_profile_rows": ex.orphan_profile_rows,
            "out_of_range_profile_rows": ex.out_of_range_profile_rows,
            "duplicate_profile_rows": ex.duplicate_profile_rows,
            "unknown_region_site_rows": ex.unknown_region_site_rows,
            "waiver_signed_missing": ex.waiver_signed_missing,
            "ineligible_offer_count": stats["ineligible_offer_count"],
            "allowance_blocked_offer_count": stats["allowance_blocked_offer_count"],
            "empty_candidate_groups": stats["empty_candidate_groups"],
            "zero_floor_count": zero_floor_count,
            "unallocated_pool_count": stats["unallocated_pool_count"],
        },
    )


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    sys.setrecursionlimit(100000)
    run(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
