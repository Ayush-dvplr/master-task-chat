#!/usr/bin/env python3
"""Derive the winter demand-response programme reports from a season extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import configparser
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from bisect import bisect_left
from datetime import datetime

LABELS = ("SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR")


def rhu(num, den):
    """num/den rounded half up (num >= 0, den > 0)."""
    return (2 * num + den) // (2 * den)


def rhe(num, den):
    """num/den rounded half to even (num >= 0, den > 0)."""
    q, r = divmod(num, den)
    two_r = 2 * r
    if two_r > den or (two_r == den and q % 2):
        q += 1
    return q


def raw_lines(path):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def content_lines(path):
    """Non-comment, non-blank lines of a commented text file."""
    return [l for l in raw_lines(path) if l.strip() and not l.startswith("#")]


def csv_rows(path, delimiter=","):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


class Offer:
    __slots__ = ("oid", "event_id", "site_id", "bid", "rel", "rec", "trel", "trec",
                 "credit", "segment", "cap_binding")


class Extract:
    """Everything one season extract says, parsed and quantised."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.counts = {}
        self._load()

    def p(self, name):
        return os.path.join(self.dir, name)

    def _load(self):
        self._load_program()
        self._load_events()
        self._load_sites()
        self._load_site_state()
        self._load_waivers()
        self._load_rate_cards()
        self._load_recipient_weights()
        self._finish_site_rows()
        self._load_offers()
        self._load_profiles()
        self._load_targets()
        self._load_feeder_limits()
        self._load_floors()
        self._load_pools()
        self._load_allowances()
        self.counts["export_manifest.tsv"] = max(
            0, len(content_lines(self.p("export_manifest.tsv"))) - 1)

    def _load_program(self):
        cp = configparser.ConfigParser(interpolation=None)
        with open(self.p("program.ini"), encoding="utf-8") as fh:
            cp.read_file(fh)
        units = cp["units"]
        self.wh_per_tick = int(units["wh_per_tick"])
        self.millicents_per_cent = int(units["millicents_per_cent"])
        self.region_of_code = {k.lower(): v for k, v in cp["region_codes"].items()}
        self.segment_of_code = {k.lower(): v for k, v in cp["segment_codes"].items()}
        self.regions = sorted(set(self.region_of_code.values()))
        self.segments = sorted(set(self.segment_of_code.values()))
        adders = ({k.lower(): int(v) for k, v in cp["segment_rate_adders"].items()}
                  if cp.has_section("segment_rate_adders") else {})
        self.segment_adder = {s: adders.get(s.lower(), 0) for s in self.segments}
        grants = cp["grants"]
        self.claim_cents_per_weight = int(grants["claim_cents_per_weight"])
        self.minimum_grant_cents = int(grants["minimum_grant_cents"])

    def _load_events(self):
        with open(self.p("events.json"), encoding="utf-8") as fh:
            events = json.load(fh)
        self.counts["events.json"] = len(events)
        self.events = {}
        for e in events:
            self.events[e["event_id"]] = {
                "event_id": e["event_id"],
                "interval_count": int(e["interval_count"]),
                "cost_weight": int(e["objective"]["cost_weight"]),
                "recovery_weight": int(e["objective"]["recovery_weight"]),
                "uplift": int(e["uplift_millicents_per_kwh"]),
                "start": datetime.fromisoformat(e["dispatch_start"]),
            }
        self.event_ids = sorted(self.events)
        season = sorted(self.events.values(), key=lambda e: e["event_id"], reverse=True)
        season.sort(key=lambda e: e["start"])
        self.season_order = [e["event_id"] for e in season]

    def _load_sites(self):
        rows = csv_rows(self.p("sites.csv"))
        self.counts["sites.csv"] = len(rows)
        self.site_rows = {}
        self.unknown_region_site_rows = 0
        for r in rows:
            region = self.region_of_code.get((r["region_code"] or "").lower())
            if region is None:
                self.unknown_region_site_rows += 1
                continue
            self.site_rows[(r["event_id"], r["site_id"])] = {
                "event_id": r["event_id"],
                "site_id": r["site_id"],
                "region": region,
                "segment": self.segment_of_code.get((r["segment_code"] or "").lower()),
                "beneficiary_id": r["beneficiary_id"],
                "critical": r["critical"] == "Y",
            }

    def _load_site_state(self):
        lines = [l for l in raw_lines(self.p("site_state.jsonl")) if l.strip()]
        self.counts["site_state.jsonl"] = len(lines)
        for l in lines:
            o = json.loads(l)
            sr = self.site_rows.get((o["event_id"], o["site_id"]))
            if sr is None:
                continue
            sr["dispatch_authorized"] = bool(o["dispatch_authorized"])
            sr["safety_hold"] = bool(o["safety_hold"])
            sr["cooldown"] = bool(o["cooldown"])

    def _load_waivers(self):
        rows = csv_rows(self.p("continuity_waivers.csv"))
        self.counts["continuity_waivers.csv"] = len(rows)
        self.waiver_signed_missing = 0
        for r in rows:
            if not (r.get("waiver_signed") or ""):
                self.waiver_signed_missing += 1
            sr = self.site_rows.get((r["event_id"], r["site_id"]))
            if sr is None:
                continue
            sr["cert_pending"] = r["routine_certificate_pending"] == "Y"
            sr["waiver_status"] = r["waiver_status"]
            sr["waiver_signed"] = (r.get("waiver_signed") or "") == "Y"

    def _load_rate_cards(self):
        cards = ET.parse(self.p("rate_cards.xml")).getroot().findall("card")
        self.counts["rate_cards.xml"] = len(cards)
        for c in cards:
            sr = self.site_rows.get((c.get("event"), c.get("site")))
            if sr is None:
                continue
            override = c.find("override")
            sr["rate_base"] = int((override if override is not None else c.find("base")).text)
            sr["cap"] = int(c.find("cap").text)

    def _load_recipient_weights(self):
        rows = csv_rows(self.p("recipient_weights.tsv"), "\t")
        self.counts["recipient_weights.tsv"] = len(rows)
        for r in rows:
            sr = self.site_rows.get((r["event_id"], r["site_id"]))
            if sr is None:
                continue
            sr["grant_weight"] = int(r["grant_weight"])

    def _finish_site_rows(self):
        """Compliance label and effective rate of every site row."""
        for sr in self.site_rows.values():
            waiver_valid = (sr.get("waiver_status") == "VALID" and sr.get("waiver_signed")
                            and sr["critical"] and sr["segment"] == "public")
            if sr.get("safety_hold"):
                label = "SAFETY_HOLD"
            elif sr.get("cooldown"):
                label = "COOLDOWN"
            elif sr.get("cert_pending") and waiver_valid:
                label = "CONTINUITY_WAIVED"
            elif sr.get("cert_pending"):
                label = "CERTIFICATE_PENDING"
            else:
                label = "CLEAR"
            sr["label"] = label
            raw = (sr["rate_base"] + self.events[sr["event_id"]]["uplift"]
                   + self.segment_adder.get(sr["segment"], 0))
            cap = sr["cap"]
            sr["rate"] = cap if raw > cap else raw
            sr["cap_binding"] = raw > cap

    def _load_offers(self):
        rows = csv_rows(self.p("offers.csv"))
        self.counts["offers.csv"] = len(rows)
        self.offer_event = {}
        self.offer_rows = []
        self.orphan_offer_rows = 0
        for r in rows:
            self.offer_event[r["offer_id"]] = r["event_id"]
            if (r["event_id"], r["site_id"]) not in self.site_rows:
                self.orphan_offer_rows += 1
                continue
            self.offer_rows.append(r)

    def _load_profiles(self):
        wpt = self.wh_per_tick
        lines = raw_lines(self.p("profiles.tsv"))
        idx = {name: i for i, name in enumerate(lines[0].split("\t"))}
        i_off, i_itv = idx["offer_id"], idx["interval"]
        i_rel, i_rec, i_mul = idx["relief_wh"], idx["recovery_wh"], idx["register_multiplier"]
        self.counts["profiles.tsv"] = len(lines) - 1
        self.orphan_profile_rows = 0
        self.out_of_range_profile_rows = 0
        self.duplicate_profile_rows = 0
        prof = {}
        for line in lines[1:]:
            f = line.split("\t")
            oid = f[i_off]
            event_id = self.offer_event.get(oid)
            if event_id is None:
                self.orphan_profile_rows += 1
                continue
            itv = int(f[i_itv])
            if itv < 1 or itv > self.events[event_id]["interval_count"]:
                self.out_of_range_profile_rows += 1
                continue
            slot = prof.setdefault(oid, {})
            if itv in slot:
                self.duplicate_profile_rows += 1
                continue
            mul = int(f[i_mul])
            slot[itv] = (rhu(int(f[i_rel]) * mul, wpt), rhu(int(f[i_rec]) * mul, wpt))
        self.profiles = prof

    def _load_targets(self):
        rows = csv_rows(self.p("targets.tsv"), "\t")
        self.counts["targets.tsv"] = len(rows)
        self.targets = {}
        for r in rows:
            region = self.region_of_code[r["region_code"].lower()]
            self.targets[(r["event_id"], region, int(r["interval"]))] = (
                rhu(int(r["target_wh"]), self.wh_per_tick), int(r["shortfall_weight"]))

    def _load_feeder_limits(self):
        lines = content_lines(self.p("feeder_limits.txt"))
        self.counts["feeder_limits.txt"] = len(lines)
        self.ceilings = {}
        for l in lines:
            region = self.region_of_code[l[10:14].strip().lower()]
            self.ceilings[(l[0:10].strip(), region, int(l[14:17]))] = (
                rhu(int(l[17:27]), self.wh_per_tick), rhu(int(l[27:37]), self.wh_per_tick))

    def _load_floors(self):
        with open(self.p("segment_floors.json"), encoding="utf-8") as fh:
            floors = json.load(fh)["floors"]
        self.counts["segment_floors.json"] = len(floors)
        self.floors = {}
        for f in floors:
            region = self.region_of_code[f["region_code"].lower()]
            segment = self.segment_of_code[f["segment_code"].lower()]
            self.floors[(f["event_id"], region, segment)] = (
                rhu(int(f["floor_wh"]), self.wh_per_tick), int(f["priority_weight"]))

    def _load_pools(self):
        lines = content_lines(self.p("pools.txt"))
        self.counts["pools.txt"] = len(lines)
        self.pools = {}
        for l in lines:
            region = self.region_of_code[l[10:14].strip().lower()]
            self.pools[(l[0:10].strip(), region)] = int(l[14:26])

    def _load_allowances(self):
        lines = content_lines(self.p("site_allowances.tsv"))
        self.counts["site_allowances.tsv"] = max(0, len(lines) - 1)
        idx = {name: i for i, name in enumerate(lines[0].split("\t"))}
        i_site, i_ticks, i_from = idx["site_id"], idx["allowance_ticks"], idx["draws_from"]
        self.allowance_ticks = {}
        draws = {}
        for l in lines[1:]:
            f = l.split("\t")
            site_id = f[i_site]
            self.allowance_ticks[site_id] = int(f[i_ticks])
            draws[site_id] = f[i_from].strip() if i_from < len(f) else ""
        root = {}
        for site_id in self.allowance_ticks:
            chain = []
            cur = site_id
            while cur not in root and draws.get(cur):
                chain.append(cur)
                cur = draws[cur]
            cur = root.get(cur, cur)
            for s in chain:
                root[s] = cur
            root[site_id] = cur
        self.allowance_root = root


def build_offers(ex):
    """One Offer per non-orphan offer, with interval ticks, totals and credit."""
    out = []
    den = 1000 * ex.millicents_per_cent
    wpt = ex.wh_per_tick
    for r in ex.offer_rows:
        sr = ex.site_rows[(r["event_id"], r["site_id"])]
        n = ex.events[r["event_id"]]["interval_count"]
        prof = ex.profiles.get(r["offer_id"], {})
        rate = sr["rate"]
        rel, rec, credit = [], [], 0
        for t in range(1, n + 1):
            a, b = prof.get(t, (0, 0))
            rel.append(a)
            rec.append(b)
            if a > b:
                credit += rhe((a - b) * wpt * rate, den)
        o = Offer()
        o.oid = r["offer_id"]
        o.event_id = r["event_id"]
        o.site_id = r["site_id"]
        o.bid = int(r["bid_cost_cents"])
        o.segment = sr["segment"]
        o.cap_binding = sr["cap_binding"]
        o.rel = rel
        o.rec = rec
        o.trel = sum(rel)
        o.trec = sum(rec)
        o.credit = credit
        out.append(o)
    return out


def solve(ex, event_id, region, site_options):
    """Best feasible portfolio of an event-region; returns (offers, tied_count)."""
    ev = ex.events[event_id]
    n = ev["interval_count"]
    target, weight, rel_ceil, rec_ceil = [], [], [], []
    for t in range(1, n + 1):
        tg, w = ex.targets[(event_id, region, t)]
        target.append(tg)
        weight.append(w)
        rc, qc = ex.ceilings[(event_id, region, t)]
        rel_ceil.append(rc)
        rec_ceil.append(qc)
    floors = []
    for seg in ex.segments:
        f, pw = ex.floors.get((event_id, region, seg), (0, 0))
        if f > 0 and pw > 0:
            floors.append((seg, f, pw))
    seg_index = {seg: i for i, (seg, _f, _w) in enumerate(floors)}
    nseg = len(floors)
    cost_weight = ev["cost_weight"]
    recovery_weight = ev["recovery_weight"]

    options = [[None] + sorted(site_options[s], key=lambda o: o.oid)
               for s in sorted(site_options)]
    depth = len(options)
    # All offers of a site belong to one site row, hence to one segment.
    site_seg = [seg_index.get(opts[1].segment) for opts in options]

    # Optimistic bounds for the sites from index i onwards: the most relief and the
    # most segment relief any completion could still add.
    suf_rel = [[0] * n for _ in range(depth + 1)]
    suf_seg = [[0] * nseg for _ in range(depth + 1)]
    for i in range(depth - 1, -1, -1):
        offs = options[i][1:]
        for t in range(n):
            suf_rel[i][t] = suf_rel[i + 1][t] + max(o.rel[t] for o in offs)
        most = max(o.trel for o in offs)
        for k in range(nseg):
            suf_seg[i][k] = suf_seg[i + 1][k] + (most if k == site_seg[i] else 0)

    rel = [0] * n
    rec = [0] * n
    segrel = [0] * nseg
    ids = []  # offer ids of the portfolio under construction, kept sorted ascending
    short = sum(weight[t] * target[t] for t in range(n))
    over = 0
    deficit = sum(pw * f for _s, f, pw in floors)
    blend = 0
    count = 0
    best_key = None
    best_ids = None
    best_count = 0

    def dfs(i):
        nonlocal short, over, deficit, blend, count
        nonlocal best_key, best_ids, best_count
        if i == depth:
            key = (short, deficit, blend, over, count)
            if best_key is None or key < best_key:
                best_key = key
                best_ids = ids.copy()
                best_count = 1
            elif key == best_key:
                best_count += 1
                if ids > best_ids:
                    best_ids = ids.copy()
            return
        if best_key is not None:
            lb_short = 0
            sr = suf_rel[i]
            for t in range(n):
                d = target[t] - rel[t] - sr[t]
                if d > 0:
                    lb_short += weight[t] * d
            lb_deficit = 0
            if nseg:
                ss = suf_seg[i]
                for k in range(nseg):
                    d = floors[k][1] - segrel[k] - ss[k]
                    if d > 0:
                        lb_deficit += floors[k][2] * d
            if (lb_short, lb_deficit, blend, over, count) > best_key:
                return
        si = site_seg[i]
        for o in options[i]:
            if o is None:
                dfs(i + 1)
                continue
            orel, orec = o.rel, o.rec
            short0, over0 = short, over
            bad = -1
            for t in range(n):
                a = orel[t]
                b = orec[t]
                new = rel[t] + a
                nrec = rec[t] + b
                if new > rel_ceil[t] or nrec > rec_ceil[t]:
                    bad = t
                    break
                if a:
                    old = rel[t]
                    rel[t] = new
                    tg = target[t]
                    if old < tg:
                        short -= weight[t] * ((tg - old) - (tg - new if new < tg else 0))
                    if new > tg:
                        over += new - tg - (old - tg if old > tg else 0)
                if b:
                    rec[t] = nrec
            if bad >= 0:
                for t in range(bad):
                    rel[t] -= orel[t]
                    rec[t] -= orec[t]
                short, over = short0, over0
                continue
            deficit0, blend0 = deficit, blend
            if si is not None:
                old = segrel[si]
                new = old + o.trel
                segrel[si] = new
                f, pw = floors[si][1], floors[si][2]
                if old < f:
                    deficit -= pw * ((f - old) - (f - new if new < f else 0))
            blend += cost_weight * o.bid + recovery_weight * o.trec
            count += 1
            pos = bisect_left(ids, o.oid)
            ids.insert(pos, o.oid)
            dfs(i + 1)
            del ids[pos]
            count -= 1
            blend, deficit, over, short = blend0, deficit0, over0, short0
            if si is not None:
                segrel[si] -= o.trel
            for t in range(n):
                rel[t] -= orel[t]
                rec[t] -= orec[t]

    dfs(0)
    by_id = {o.oid: o for opts in options for o in opts if o is not None}
    return [by_id[i] for i in best_ids], best_count


def largest_remainder(F, weights, order_desc):
    """Apportion F by weight using largest remainder.

    order_desc lists the beneficiaries in descending identifier order, which is how
    equal remainders are served.  Returns (shares, residual cents, residual tie).
    """
    W = sum(weights.values())
    shares = {b: F * w // W for b, w in weights.items()}
    rem = {b: (F * w) % W for b, w in weights.items()}
    left = F - sum(shares.values())
    seen = set()
    tie = False
    for r in rem.values():
        if r:
            if r in seen:
                tie = True
            seen.add(r)
    order = list(order_desc)
    order.sort(key=lambda b: -rem[b])
    for b in order[:left]:
        shares[b] += 1
    return shares, left, tie


def compute_grants(ex, pool, carried, credit_cents, site_rows):
    """Fund and apportion one event-region's grant pool."""
    F = pool + carried - credit_cents
    if F < 0:
        F = 0
    weights = {}
    recipients = 0
    for sr in site_rows:
        if "grant_weight" not in sr:
            continue
        recipients += 1
        w = sr["grant_weight"]
        if sr["label"] == "CONTINUITY_WAIVED":
            w *= 2
        b = sr["beneficiary_id"]
        weights[b] = weights.get(b, 0) + w
    W = sum(weights.values())
    out = {"pool": pool, "F": F, "allocated": 0, "unallocated": F, "grants": [],
           "residual": 0, "residual_tie": False,
           "zero_denominator": recipients == 0 or W == 0}
    if out["zero_denominator"]:
        return out

    positive = {b: w for b, w in weights.items() if w > 0}
    order_desc = sorted(positive, reverse=True)
    claims = {b: w * ex.claim_cents_per_weight for b, w in positive.items()}
    if sum(claims.values()) <= F:
        shares, residual, tie = claims, 0, False
    else:
        shares, residual, tie = largest_remainder(F, positive, order_desc)
        kept = {b: w for b, w in positive.items() if shares[b] >= ex.minimum_grant_cents}
        if len(kept) != len(positive):
            if kept:
                second, residual, tie = largest_remainder(
                    F, kept, [b for b in order_desc if b in kept])
                shares = {b: second.get(b, 0) for b in positive}
            else:
                shares, residual, tie = {b: 0 for b in positive}, 0, False
    allocated = sum(shares.values())
    out["allocated"] = allocated
    out["unallocated"] = F - allocated
    out["grants"] = [{"beneficiary_id": b, "cents": shares[b]} for b in sorted(positive)]
    out["residual"] = residual
    out["residual_tie"] = tie
    return out


def run(ex):
    """Walk the season in order, choosing portfolios and settling grants."""
    offers = build_offers(ex)
    by_event_region = {}
    for o in offers:
        key = (o.event_id, ex.site_rows[(o.event_id, o.site_id)]["region"])
        by_event_region.setdefault(key, []).append(o)
    rows_by_event_region = {}
    for sr in ex.site_rows.values():
        rows_by_event_region.setdefault((sr["event_id"], sr["region"]), []).append(sr)

    remaining = {r: ex.allowance_ticks[r] for r in set(ex.allowance_root.values())}
    carried = {r: 0 for r in ex.regions}
    stats = {"ineligible": 0, "blocked": 0, "empty_groups": 0, "cap_binding": 0,
             "residual": 0, "residual_tie_pools": 0, "unallocated_pools": 0}
    results = {}

    for event_id in ex.season_order:
        n = ex.events[event_id]["interval_count"]
        consumed = []
        for region in ex.regions:
            key = (event_id, region)
            site_options = {}
            for o in by_event_region.get(key, []):
                sr = ex.site_rows[(o.event_id, o.site_id)]
                if not sr.get("dispatch_authorized"):
                    stats["ineligible"] += 1
                    continue
                if o.trel > remaining.get(ex.allowance_root.get(o.site_id), 0):
                    stats["blocked"] += 1
                    continue
                site_options.setdefault(o.site_id, []).append(o)
            candidate_count = sum(len(v) for v in site_options.values())
            if candidate_count == 0:
                stats["empty_groups"] += 1
            chosen, tied = solve(ex, event_id, region, site_options)
            consumed.extend(chosen)

            rel = [0] * n
            rec = [0] * n
            bid = credit = 0
            for o in chosen:
                for t in range(n):
                    rel[t] += o.rel[t]
                    rec[t] += o.rec[t]
                bid += o.bid
                credit += o.credit
                if o.cap_binding:
                    stats["cap_binding"] += 1

            site_rows = rows_by_event_region.get(key, ())
            g = compute_grants(ex, ex.pools.get(key, 0), carried[region], credit, site_rows)
            carried[region] = g["unallocated"]
            stats["residual"] += g["residual"]
            stats["residual_tie_pools"] += 1 if g["residual_tie"] else 0
            stats["unallocated_pools"] += 1 if g["zero_denominator"] else 0

            counts = {lab: 0 for lab in LABELS}
            for sr in site_rows:
                counts[sr["label"]] += 1

            results[key] = {
                "candidate_offer_count": candidate_count,
                "chosen": chosen,
                "rel": rel,
                "rec": rec,
                "bid": bid,
                "credit": credit,
                "grants": g,
                "compliance_counts": counts,
                "tied": tied,
            }
        for o in consumed:
            root = ex.allowance_root.get(o.site_id)
            if root in remaining:
                remaining[root] -= o.trel
    return results, stats


REGION_TOTAL_KEYS = ("event_count", "candidate_offer_count", "selected_offer_count",
                     "relief_ticks", "recovery_ticks", "shortfall_ticks",
                     "overdelivery_ticks", "bid_cost_cents", "credit_cents",
                     "grant_pool_cents", "grant_funded_cents", "grant_allocated_cents",
                     "grant_unallocated_cents")


def region_doc(ex, region, results):
    events_out = []
    totals = {k: 0 for k in REGION_TOTAL_KEYS}
    for event_id in ex.event_ids:
        r = results[(event_id, region)]
        intervals = []
        rel_sum = rec_sum = short_sum = over_sum = 0
        for t in range(1, ex.events[event_id]["interval_count"] + 1):
            tg = ex.targets[(event_id, region, t)][0]
            rl = r["rel"][t - 1]
            rc = r["rec"][t - 1]
            short = tg - rl if tg > rl else 0
            over = rl - tg if rl > tg else 0
            intervals.append({"interval": t, "target_ticks": tg, "relief_ticks": rl,
                              "recovery_ticks": rc, "shortfall_ticks": short,
                              "overdelivery_ticks": over})
            rel_sum += rl
            rec_sum += rc
            short_sum += short
            over_sum += over
        g = r["grants"]
        events_out.append({
            "event_id": event_id,
            "candidate_offer_count": r["candidate_offer_count"],
            "selected_offer_ids": sorted(o.oid for o in r["chosen"]),
            "intervals": intervals,
            "bid_cost_cents": r["bid"],
            "credit_cents": r["credit"],
            "grant_pool_cents": g["pool"],
            "grant_funded_cents": g["F"],
            "grant_allocated_cents": g["allocated"],
            "grant_unallocated_cents": g["unallocated"],
            "grants": g["grants"],
            "compliance_counts": r["compliance_counts"],
        })
        totals["event_count"] += 1
        totals["candidate_offer_count"] += r["candidate_offer_count"]
        totals["selected_offer_count"] += len(r["chosen"])
        totals["relief_ticks"] += rel_sum
        totals["recovery_ticks"] += rec_sum
        totals["shortfall_ticks"] += short_sum
        totals["overdelivery_ticks"] += over_sum
        totals["bid_cost_cents"] += r["bid"]
        totals["credit_cents"] += r["credit"]
        totals["grant_pool_cents"] += g["pool"]
        totals["grant_funded_cents"] += g["F"]
        totals["grant_allocated_cents"] += g["allocated"]
        totals["grant_unallocated_cents"] += g["unallocated"]
    return {"region": region, "events": events_out, "totals": totals}


def segment_doc(ex, segment, results):
    entries = []
    totals = {k: 0 for k in ("selected_offer_count", "relief_ticks", "recovery_ticks",
                             "bid_cost_cents", "credit_cents", "floor_ticks")}
    for event_id in ex.event_ids:
        for region in ex.regions:
            chosen = [o for o in results[(event_id, region)]["chosen"]
                      if o.segment == segment]
            rel = sum(o.trel for o in chosen)
            rec = sum(o.trec for o in chosen)
            bid = sum(o.bid for o in chosen)
            credit = sum(o.credit for o in chosen)
            floor = ex.floors.get((event_id, region, segment), (0, 0))[0]
            bp = 10000 if floor == 0 else min(10000, rhu(10000 * rel, floor))
            entries.append({
                "event_id": event_id, "region": region,
                "selected_offer_ids": sorted(o.oid for o in chosen),
                "relief_ticks": rel, "recovery_ticks": rec,
                "bid_cost_cents": bid, "credit_cents": credit,
                "floor_ticks": floor, "floor_attainment_bp": bp,
            })
            totals["selected_offer_count"] += len(chosen)
            totals["relief_ticks"] += rel
            totals["recovery_ticks"] += rec
            totals["bid_cost_cents"] += bid
            totals["credit_cents"] += credit
            totals["floor_ticks"] += floor
    return {"segment": segment, "event_regions": entries, "totals": totals}


def summary_doc(ex, region_docs, segment_docs):
    keys = [k for k in REGION_TOTAL_KEYS if k != "event_count"]
    doc = {k: 0 for k in keys}
    for region in ex.regions:
        t = region_docs[region]["totals"]
        for k in keys:
            doc[k] += t[k]
    doc["event_count"] = len(ex.event_ids)
    doc["event_region_count"] = len(ex.event_ids) * len(ex.regions)
    doc["site_count"] = len(ex.site_rows)
    doc["regions"] = {
        region: {k: region_docs[region]["totals"][k] for k in
                 ("selected_offer_count", "relief_ticks", "bid_cost_cents",
                  "credit_cents", "grant_allocated_cents")}
        for region in ex.regions}
    doc["segments"] = {
        segment: {k: segment_docs[segment]["totals"][k] for k in
                  ("selected_offer_count", "relief_ticks", "bid_cost_cents",
                   "credit_cents")}
        for segment in ex.segments}
    return doc


def policy_doc(ex, results, stats):
    counts = {lab: 0 for lab in LABELS}
    labels = []
    for key in sorted(ex.site_rows):
        sr = ex.site_rows[key]
        counts[sr["label"]] += 1
        labels.append({"event_id": sr["event_id"], "site_id": sr["site_id"],
                       "label": sr["label"]})
    ties = []
    for event_id in ex.event_ids:
        for region in ex.regions:
            r = results[(event_id, region)]
            if r["tied"] >= 2:
                ties.append({"event_id": event_id, "region": region,
                             "tied_portfolio_count": r["tied"],
                             "selected_offer_ids": sorted(o.oid for o in r["chosen"])})
    return {
        "compliance_counts": counts,
        "site_labels": labels,
        "tie_decisions": ties,
        "cap_binding_count": stats["cap_binding"],
        "residual_cents": stats["residual"],
        "residual_tie_pool_count": stats["residual_tie_pools"],
    }


def quality_doc(ex, stats):
    zero_floor = 0
    for event_id in ex.event_ids:
        for region in ex.regions:
            for segment in ex.segments:
                if ex.floors.get((event_id, region, segment), (0, 0))[0] == 0:
                    zero_floor += 1
    return {
        "rows": dict(ex.counts),
        "orphan_offer_rows": ex.orphan_offer_rows,
        "orphan_profile_rows": ex.orphan_profile_rows,
        "out_of_range_profile_rows": ex.out_of_range_profile_rows,
        "duplicate_profile_rows": ex.duplicate_profile_rows,
        "unknown_region_site_rows": ex.unknown_region_site_rows,
        "waiver_signed_missing": ex.waiver_signed_missing,
        "ineligible_offer_count": stats["ineligible"],
        "allowance_blocked_offer_count": stats["blocked"],
        "empty_candidate_groups": stats["empty_groups"],
        "zero_floor_count": zero_floor,
        "unallocated_pool_count": stats["unallocated_pools"],
    }


def write_json(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, sort_keys=True, indent=1)
        fh.write("\n")


def main(argv):
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    ex = Extract(data_dir)
    results, stats = run(ex)
    region_docs = {r: region_doc(ex, r, results) for r in ex.regions}
    segment_docs = {s: segment_doc(ex, s, results) for s in ex.segments}
    for region, doc in region_docs.items():
        write_json(os.path.join(out_dir, "region_%s.json" % region), doc)
    for segment, doc in segment_docs.items():
        write_json(os.path.join(out_dir, "segment_%s.json" % segment), doc)
    write_json(os.path.join(out_dir, "summary.json"),
               summary_doc(ex, region_docs, segment_docs))
    write_json(os.path.join(out_dir, "policy_audit.json"), policy_doc(ex, results, stats))
    write_json(os.path.join(out_dir, "data_quality.json"), quality_doc(ex, stats))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
