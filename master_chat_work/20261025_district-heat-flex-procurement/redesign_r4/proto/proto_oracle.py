#!/usr/bin/env python3
"""derive_report.py: district heat flexibility reports, as defined in DATA_DIR/schema.md.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""
from __future__ import annotations

import configparser
import csv
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import os

ON = set(filter(None, os.environ.get("PROTO_ON", "M1,M2,M3,CARRY").split(",")))
WRONG = set(filter(None, os.environ.get("PROTO_WRONG", "").split(",")))
TRACE: list | None = None  # fuzz hook: per event-region (eid, region, pool, carry_in, credit, weights)

LABELS = ("SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR")


def half_up(numerator: int, denominator: int) -> int:
    """Nearest integer to numerator/denominator, exact halves upward (both non-negative)."""
    return (2 * numerator + denominator) // (2 * denominator)


def half_even(numerator: int, denominator: int) -> int:
    """Nearest integer to numerator/denominator, exact halves to the even neighbour (both non-negative)."""
    quotient, remainder = divmod(numerator, denominator)
    twice = 2 * remainder
    if twice > denominator or (twice == denominator and quotient % 2 == 1):
        quotient += 1
    return quotient


def table(path: Path, delimiter: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def fixed_width(path: Path, spans: dict[str, tuple[int, int]]) -> list[dict[str, str]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        records.append({name: line[lo - 1:hi].strip() for name, (lo, hi) in spans.items()})
    return records


@dataclass
class Site:
    event_id: str
    site_id: str
    region: str
    segment: str
    beneficiary: str
    critical: bool
    authorized: bool = False
    hold: bool = False
    cooldown: bool = False
    pending: bool = False
    waiver_status: str = "NONE"
    waiver_signed: str = ""
    base: int = 0
    cap: int = 0
    override: int | None = None
    adder: int = 0
    weight: int | None = None

    def start_rate(self) -> int:
        """rate_cards.xml header: the override value when the card has one, else the base."""
        return self.base if self.override is None else self.override


@dataclass
class Offer:
    offer_id: str
    site: Site
    cost: int
    relief_wh: list[int]
    recovery_wh: list[int]
    relief: list[int] = field(default_factory=list)
    recovery: list[int] = field(default_factory=list)


@dataclass
class Extract:
    wh_per_tick: int
    millicents_per_cent: int
    regions: list[str]
    segments: list[str]
    events: list[dict]
    sites: dict[tuple[str, str], Site]
    offers: list[Offer]
    targets: dict[tuple[str, str, int], tuple[int, int]]
    ceilings: dict[tuple[str, str, int], tuple[int, int]]
    floors: dict[tuple[str, str, str], tuple[int, int]]
    pools: dict[tuple[str, str], int]
    allowance: dict[str, int] = field(default_factory=dict)
    draws: dict[str, str] = field(default_factory=dict)
    claim: int = 0
    minimum: int = 0
    has_grants: bool = False
    quality: dict = field(default_factory=dict)


def read_profiles(folder: Path, offer_rows: list[dict[str, str]], offers: dict[str, Offer],
                  interval_count: dict[str, int], rows: dict[str, int]) -> dict[str, int]:
    """Apply profiles.tsv in file order; returns the rejected-row counts of schema section 1."""
    event_of = {r["offer_id"]: r["event_id"] for r in offer_rows}
    profile_rows = table(folder / "profiles.tsv", "\t")
    rows["profiles.tsv"] = len(profile_rows)
    rejected = {"orphan_profile_rows": 0, "out_of_range_profile_rows": 0, "duplicate_profile_rows": 0}
    used: set[tuple[str, int]] = set()
    for r in profile_rows:
        offer_id, interval = r["offer_id"], int(r["interval"])
        if offer_id not in event_of:
            rejected["orphan_profile_rows"] += 1
        elif not 1 <= interval <= interval_count[event_of[offer_id]]:
            rejected["out_of_range_profile_rows"] += 1
        elif (offer_id, interval) in used:
            rejected["duplicate_profile_rows"] += 1
        else:
            used.add((offer_id, interval))
            offer = offers.get(offer_id)
            if offer is not None:
                multiplier = int(r["register_multiplier"])
                offer.relief_wh[interval - 1] = int(r["relief_wh"]) * multiplier
                offer.recovery_wh[interval - 1] = int(r["recovery_wh"]) * multiplier
    return rejected


def load(folder: Path) -> Extract:
    ini = configparser.ConfigParser()
    ini.read(folder / "program.ini", encoding="utf-8")
    wh = ini.getint("units", "wh_per_tick")
    region_of = {code.upper(): name for code, name in ini.items("region_codes")}
    segment_of = {code.upper(): name for code, name in ini.items("segment_codes")}
    adders = ({name.lower(): int(value) for name, value in ini.items("segment_rate_adders")}
              if ini.has_section("segment_rate_adders") else {})

    def ticks(raw: str) -> int:
        return half_up(int(raw), wh)

    events = json.loads((folder / "events.json").read_text(encoding="utf-8"))
    rows = {"events.json": len(events)}

    sites: dict[tuple[str, str], Site] = {}
    site_rows = table(folder / "sites.csv", ",")
    rows["sites.csv"] = len(site_rows)
    unknown_region = 0
    for r in site_rows:
        region = region_of.get(r["region_code"].upper())
        if region is None:
            unknown_region += 1
            continue
        segment = segment_of[r["segment_code"].upper()]
        sites[(r["event_id"], r["site_id"])] = Site(
            r["event_id"], r["site_id"], region, segment, r["beneficiary_id"], r["critical"] == "Y",
            adder=adders.get(segment.lower(), 0))

    state_lines = [json.loads(line) for line in (folder / "site_state.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows["site_state.jsonl"] = len(state_lines)
    for s in state_lines:
        site = sites.get((s["event_id"], s["site_id"]))
        if site is not None:
            site.authorized, site.hold, site.cooldown = s["dispatch_authorized"], s["safety_hold"], s["cooldown"]

    waivers = table(folder / "continuity_waivers.csv", ",")
    rows["continuity_waivers.csv"] = len(waivers)
    signed_missing = 0
    for w in waivers:
        signed = (w.get("waiver_signed") or "").strip()
        signed_missing += signed == ""
        site = sites.get((w["event_id"], w["site_id"]))
        if site is not None:
            site.pending = w["routine_certificate_pending"] == "Y"
            site.waiver_status = w["waiver_status"]
            site.waiver_signed = signed

    cards = ET.parse(folder / "rate_cards.xml").getroot().findall("card")
    rows["rate_cards.xml"] = len(cards)
    for card in cards:
        site = sites.get((card.get("event"), card.get("site")))
        if site is not None:
            site.base, site.cap = int(card.findtext("base")), int(card.findtext("cap"))
            if card.find("override") is not None:
                site.override = int(card.findtext("override"))

    weights = table(folder / "recipient_weights.tsv", "\t")
    rows["recipient_weights.tsv"] = len(weights)
    for w in weights:
        site = sites.get((w["event_id"], w["site_id"]))
        if site is not None:
            site.weight = int(w["grant_weight"])

    interval_count = {e["event_id"]: int(e["interval_count"]) for e in events}
    offer_rows = table(folder / "offers.csv", ",")
    rows["offers.csv"] = len(offer_rows)
    offers: dict[str, Offer] = {}
    orphans = 0
    for r in offer_rows:
        site = sites.get((r["event_id"], r["site_id"]))
        if site is None:
            orphans += 1
            continue
        n = interval_count[r["event_id"]]
        offers[r["offer_id"]] = Offer(r["offer_id"], site, int(r["bid_cost_cents"]), [0] * n, [0] * n)

    rejected = read_profiles(folder, offer_rows, offers, interval_count, rows)
    for offer in offers.values():
        offer.relief = [half_up(v, wh) for v in offer.relief_wh]
        offer.recovery = [half_up(v, wh) for v in offer.recovery_wh]

    target_rows = table(folder / "targets.tsv", "\t")
    rows["targets.tsv"] = len(target_rows)
    targets = {(r["event_id"], region_of[r["region_code"].upper()], int(r["interval"])):
               (ticks(r["target_wh"]), int(r["shortfall_weight"])) for r in target_rows}

    feeder = fixed_width(folder / "feeder_limits.txt", {"event": (1, 10), "code": (11, 14), "interval": (15, 17),
                                                         "relief": (18, 27), "recovery": (28, 37)})
    rows["feeder_limits.txt"] = len(feeder)
    ceilings = {(r["event"], region_of[r["code"].upper()], int(r["interval"])): (ticks(r["relief"]), ticks(r["recovery"]))
                for r in feeder}

    floor_entries = json.loads((folder / "segment_floors.json").read_text(encoding="utf-8"))["floors"]
    rows["segment_floors.json"] = len(floor_entries)
    floors = {(f["event_id"], region_of[f["region_code"].upper()], segment_of[f["segment_code"].upper()]):
              (ticks(str(f["floor_wh"])), int(f["priority_weight"])) for f in floor_entries}

    receipt = [line for line in (folder / "export_manifest.tsv").read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.startswith("#")]
    rows["export_manifest.tsv"] = len(receipt) - 1

    pool_lines = fixed_width(folder / "pools.txt", {"event": (1, 10), "code": (11, 14), "pool": (15, 26)})
    rows["pools.txt"] = len(pool_lines)
    pools = {(r["event"], region_of[r["code"].upper()]): int(r["pool"]) for r in pool_lines}

    allowance_lines = [line for line in (folder / "site_allowances.tsv").read_text(encoding="utf-8").splitlines()
                       if line.strip() and not line.startswith("#")]
    allowance_rows = list(csv.DictReader(allowance_lines, delimiter="\t"))
    rows["site_allowances.tsv"] = len(allowance_rows)
    allowance = {r["site_id"]: int(r["allowance_ticks"]) for r in allowance_rows}
    draws = {r["site_id"]: (r.get("draws_from") or "").strip() for r in allowance_rows}

    extract = Extract(wh, ini.getint("units", "millicents_per_cent"), sorted(set(region_of.values())),
                      sorted(set(segment_of.values())), sorted(events, key=lambda e: e["event_id"]), sites,
                      list(offers.values()), targets, ceilings, floors, pools, allowance)
    extract.draws = {k: v for k, v in draws.items() if v}
    if ini.has_section("grants"):
        extract.has_grants = True
        extract.claim = ini.getint("grants", "claim_cents_per_weight")
        extract.minimum = ini.getint("grants", "minimum_grant_cents")
    extract.quality = {"rows": rows, "orphan_offer_rows": orphans, "waiver_signed_missing": signed_missing,
                       "unknown_region_site_rows": unknown_region, **rejected}
    return extract


def label_for(site: Site) -> str:
    if site.hold:
        return "SAFETY_HOLD"
    if site.cooldown:
        return "COOLDOWN"
    waiver_valid = (site.waiver_status == "VALID" and site.waiver_signed == "Y"
                    and site.critical and site.segment == "public")
    if site.pending and waiver_valid:
        return "CONTINUITY_WAIVED"
    if site.pending:
        return "CERTIFICATE_PENDING"
    return "CLEAR"


def choose_portfolio(ex: Extract, event: dict, region: str, candidates: list[Offer]) -> tuple[list[Offer], int]:
    """Exact best portfolio by depth-first enumeration, one site at a time.

    Every choice of at most one candidate offer per site is visited. A branch is cut as soon as a running
    sum of per-value ticks passes a relief or recovery ceiling, because sums only grow. Each complete
    portfolio gets the five-component key of schema section 5; the smallest key wins, the portfolios that
    share it are counted, and among them the greatest sorted offer-id tuple is kept (section 2.4).
    Returns the chosen offers and the tied portfolio count."""
    eid = event["event_id"]
    n = int(event["interval_count"])
    target = [ex.targets.get((eid, region, t + 1), (0, 0)) for t in range(n)]
    limit = [ex.ceilings.get((eid, region, t + 1), (0, 0)) for t in range(n)]
    cost_w = int(event["objective"]["cost_weight"])
    rec_w = int(event["objective"]["recovery_weight"])
    floors = {s: ex.floors.get((eid, region, s), (0, 0)) for s in ex.segments}

    by_site: dict[str, list[Offer]] = {}
    for offer in candidates:
        by_site.setdefault(offer.site.site_id, []).append(offer)
    lanes = [by_site[site_id] for site_id in sorted(by_site)]
    by_id = {o.offer_id: o for o in candidates}

    relief = [0] * n
    recovery = [0] * n
    got = dict.fromkeys(ex.segments, 0)
    taken: list[Offer] = []
    best: dict = {"key": None, "ways": 0, "ids": ()}

    def settle() -> None:
        shortfall = sum(target[t][1] * max(0, target[t][0] - relief[t]) for t in range(n))
        deficit = sum(w * max(0, fl - got[s]) for s, (fl, w) in floors.items())
        blended = cost_w * sum(o.cost for o in taken) + rec_w * sum(recovery)
        over = sum(max(0, relief[t] - target[t][0]) for t in range(n))
        key = (shortfall, deficit, blended, over, len(taken))
        ids = tuple(sorted(o.offer_id for o in taken))
        if best["key"] is None or key < best["key"]:
            best.update(key=key, ways=1, ids=ids)
        elif key == best["key"]:
            best["ways"] += 1
            best["ids"] = max(best["ids"], ids)

    def visit(lane: int) -> None:
        if lane == len(lanes):
            settle()
            return
        visit(lane + 1)
        for offer in lanes[lane]:
            if any(relief[t] + offer.relief[t] > limit[t][0] or recovery[t] + offer.recovery[t] > limit[t][1]
                   for t in range(n)):
                continue
            for t in range(n):
                relief[t] += offer.relief[t]
                recovery[t] += offer.recovery[t]
            got[offer.site.segment] += sum(offer.relief)
            taken.append(offer)
            visit(lane + 1)
            taken.pop()
            got[offer.site.segment] -= sum(offer.relief)
            for t in range(n):
                relief[t] -= offer.relief[t]
                recovery[t] -= offer.recovery[t]

    visit(0)
    return [by_id[i] for i in best["ids"]], best["ways"]


def report_ticks(offers: list[Offer], interval: int, kind: str) -> int:
    """Energy of several offers at one interval: a sum of per-value ticks (section 2.3)."""
    return sum(getattr(o, kind)[interval] for o in offers)


def rate_before_cap(site: Site, uplift: int) -> int:
    """Card start rate + event uplift + segment rate adder (schema section 6)."""
    return site.start_rate() + uplift + site.adder


def credit_cents(ex: Extract, offer: Offer, uplift: int) -> int:
    """rate_cards.xml header: one half-to-even rounding per interval amount, then the sum."""
    rate = min(rate_before_cap(offer.site, uplift), offer.site.cap)
    divisor = 1000 * ex.millicents_per_cent
    if "M3" in ON and "RELIEF" not in WRONG:
        ticks_list = [max(0, a - b) for a, b in zip(offer.relief, offer.recovery)]
    else:
        ticks_list = offer.relief
    return sum(half_even(ticks * ex.wh_per_tick * rate, divisor) for ticks in ticks_list)


def grant_weight(site: Site) -> int:
    """A recipient site row's weight; doubled when its compliance label is CONTINUITY_WAIVED (section 7)."""
    return site.weight * 2 if label_for(site) == "CONTINUITY_WAIVED" else site.weight


def share_pool(pool: int, members: list[Site]) -> tuple[dict[str, int] | None, int, bool]:
    """Largest remainder; returns (cents per beneficiary or None when unallocated, residual, residual tie)."""
    weight: dict[str, int] = {}
    for site in members:
        weight[site.beneficiary] = weight.get(site.beneficiary, 0) + grant_weight(site)
    total = sum(weight.values())
    if not members or total == 0:
        return None, 0, False
    shares = {b: pool * w // total for b, w in weight.items() if w > 0}
    rest = {b: pool * w % total for b, w in weight.items() if w > 0}
    left = pool - sum(shares.values())
    order = sorted(shares, key=lambda b: (rest[b], b), reverse=True)
    for b in order[:left]:
        shares[b] += 1
    nonzero = [r for r in rest.values() if r]
    return shares, left, len(nonzero) != len(set(nonzero))


def _lr(pool: int, weight: dict[str, int]):
    total = sum(weight.values())
    shares = {b: pool * w // total for b, w in weight.items()}
    rest = {b: pool * w % total for b, w in weight.items()}
    left = pool - sum(shares.values())
    for b in sorted(shares, key=lambda b: (rest[b], b), reverse=True)[:left]:
        shares[b] += 1
    nonzero = [r for r in rest.values() if r]
    return shares, left, len(nonzero) != len(set(nonzero))


def share_grants(ex: Extract, pool: int, members: list[Site]):
    """M1: claims fit -> claims paid; else largest remainder, minimum drop, survivors share every cent again."""
    if "M1" not in ON or not ex.has_grants:
        return share_pool(pool, members)
    weight: dict[str, int] = {}
    for site in members:
        weight[site.beneficiary] = weight.get(site.beneficiary, 0) + grant_weight(site)
    weight = {b: w for b, w in weight.items() if w > 0}
    if not weight:
        return None, 0, False
    claims = {b: w * ex.claim for b, w in weight.items()}
    if sum(claims.values()) <= pool:
        return claims, 0, False
    shares, left, tie = _lr(pool, weight)
    if "NODROP" in WRONG:
        return shares, left, tie
    keep = {b: w for b, w in weight.items() if shares[b] >= ex.minimum}
    if len(keep) == len(weight):
        return shares, left, tie
    out = dict.fromkeys(weight, 0)
    if not keep:
        return out, 0, False
    if "DROPLEFT" in WRONG:
        out.update({b: shares[b] for b in keep})
        return out, left, tie
    if "REENTRY" in WRONG and sum(w * ex.claim for w in keep.values()) <= pool:
        out.update({b: w * ex.claim for b, w in keep.items()})
        return out, 0, False
    second, left2, tie2 = _lr(pool, keep)
    out.update(second)
    return out, left2, tie2


def holder(ex: Extract, sid: str) -> str:
    """M2: the site whose allowance a site draws on, following draws_from to a row with no draws_from."""
    if "M2" not in ON or "CHAIN0" in WRONG:
        return sid
    if "CHAIN1" in WRONG:
        return ex.draws.get(sid) or sid
    while ex.draws.get(sid):
        sid = ex.draws[sid]
    return sid


def funded_pool(pool: int, credit_total: int) -> int:
    """The pool that is apportioned: the pools.txt pool minus the event-region credit, never below 0."""
    return max(0, pool - credit_total)


def ledger_order(events: list[dict]) -> list[dict]:
    """site_allowances.tsv: events reach the allowances in the order of their start instants; events that
    start at the same instant are served in descending event_id order (section 2.4)."""
    by_id = sorted(events, key=lambda e: e["event_id"], reverse=True)
    return sorted(by_id, key=lambda e: datetime.fromisoformat(e["dispatch_start"]))


def choose_all(ex: Extract, candidates: dict[tuple[str, str], list[Offer]]):
    """Walk the season ledger. When an event is reached, an offer is a candidate only if its total relief
    ticks fit in what remains of its site's allowance; the event's chosen offers then draw the allowance.
    Returns {(event_id, region): (candidates, chosen, tied count)} and the allowance-blocked offer count."""
    remaining = dict(ex.allowance)
    picks: dict[tuple[str, str], tuple[list[Offer], list[Offer], int]] = {}
    blocked = 0
    for event in ledger_order(ex.events):
        eid = event["event_id"]
        drawn: list[Offer] = []
        for region in ex.regions:
            offers = [o for o in candidates.get((eid, region), [])
                      if sum(o.relief) <= remaining[holder(ex, o.site.site_id)]]
            blocked += len(candidates.get((eid, region), [])) - len(offers)
            chosen, tied = choose_portfolio(ex, event, region, offers)
            picks[(eid, region)] = (offers, chosen, tied)
            drawn.extend(chosen)
        for offer in drawn:
            remaining[holder(ex, offer.site.site_id)] -= sum(offer.relief)
    return picks, blocked


def build(folder: Path) -> dict[str, dict]:
    ex = load(folder)
    by_er: dict[tuple[str, str], list[Site]] = {}
    for site in ex.sites.values():
        by_er.setdefault((site.event_id, site.region), []).append(site)
    candidates: dict[tuple[str, str], list[Offer]] = {}
    ineligible = 0
    for offer in ex.offers:
        if offer.site.authorized:
            candidates.setdefault((offer.site.event_id, offer.site.region), []).append(offer)
        else:
            ineligible += 1

    region_events = {r: [] for r in ex.regions}
    segment_rows = {s: [] for s in ex.segments}
    ties, cap_binding, residual_total, residual_ties = [], 0, 0, 0
    empty_groups = zero_floors = unallocated_pools = 0
    picks, blocked = choose_all(ex, candidates)
    carry = dict.fromkeys(ex.regions, 0)
    for event in ledger_order(ex.events):
        eid = event["event_id"]
        n = int(event["interval_count"])
        uplift = int(event["uplift_millicents_per_kwh"])
        for region in ex.regions:
            pool_sites = by_er.get((eid, region), [])
            offers, chosen, tied = picks[(eid, region)]
            if not offers:
                empty_groups += 1
            chosen_ids = sorted(o.offer_id for o in chosen)
            if tied > 1:
                ties.append({"event_id": eid, "region": region, "tied_portfolio_count": tied,
                             "selected_offer_ids": chosen_ids})
            credit = {o.offer_id: credit_cents(ex, o, uplift) for o in chosen}
            cap_binding += sum(1 for o in chosen if rate_before_cap(o.site, uplift) > o.site.cap)
            intervals = []
            for t in range(n):
                tgt = ex.targets.get((eid, region, t + 1), (0, 0))[0]
                rel = report_ticks(chosen, t, "relief")
                intervals.append({"interval": t + 1, "target_ticks": tgt, "relief_ticks": rel,
                                  "recovery_ticks": report_ticks(chosen, t, "recovery"),
                                  "shortfall_ticks": max(0, tgt - rel), "overdelivery_ticks": max(0, rel - tgt)})
            credit_total = sum(credit.values())
            pool = ex.pools.get((eid, region), 0)
            funded = funded_pool(pool + (carry[region] if "CARRY" in ON else 0), credit_total)
            if TRACE is not None:
                bw: dict[str, int] = {}
                for site in pool_sites:
                    if site.weight is not None:
                        bw[site.beneficiary] = bw.get(site.beneficiary, 0) + grant_weight(site)
                TRACE.append((eid, region, pool, carry[region] if "CARRY" in ON else 0, credit_total,
                              {b: w for b, w in bw.items() if w > 0}))
            shares, residual, tie = share_grants(ex, funded, [s for s in pool_sites if s.weight is not None])
            if shares is None:
                unallocated_pools += 1
                shares = {}
            residual_total += residual
            residual_ties += tie
            allocated = sum(shares.values())
            carry[region] = funded - allocated
            counts = dict.fromkeys(LABELS, 0)
            for site in pool_sites:
                counts[label_for(site)] += 1
            region_events[region].append({
                "event_id": eid, "candidate_offer_count": len(offers), "selected_offer_ids": chosen_ids,
                "intervals": intervals, "bid_cost_cents": sum(o.cost for o in chosen),
                "credit_cents": credit_total, "grant_pool_cents": pool, "grant_funded_cents": funded,
                "grant_allocated_cents": allocated, "grant_unallocated_cents": funded - allocated,
                "grants": [{"beneficiary_id": b, "cents": c} for b, c in sorted(shares.items())],
                "compliance_counts": counts,
            })
            for seg in ex.segments:
                mine = [o for o in chosen if o.site.segment == seg]
                floor = ex.floors.get((eid, region, seg), (0, 0))[0]
                relief = sum(report_ticks(mine, t, "relief") for t in range(n))
                if floor == 0:
                    zero_floors += 1
                attainment = 10000 if floor == 0 else min(10000, half_up(10000 * relief, floor))
                segment_rows[seg].append({
                    "event_id": eid, "region": region, "selected_offer_ids": sorted(o.offer_id for o in mine),
                    "relief_ticks": relief, "recovery_ticks": sum(report_ticks(mine, t, "recovery") for t in range(n)),
                    "bid_cost_cents": sum(o.cost for o in mine), "credit_cents": sum(credit[o.offer_id] for o in mine),
                    "floor_ticks": floor, "floor_attainment_bp": attainment,
                })
    for r in region_events:
        region_events[r].sort(key=lambda e: e["event_id"])
    ties.sort(key=lambda t: (t["event_id"], t["region"]))
    return assemble(ex, region_events, segment_rows, ties, cap_binding, residual_total, residual_ties,
                    {"ineligible_offer_count": ineligible, "allowance_blocked_offer_count": blocked,
                     "empty_candidate_groups": empty_groups,
                     "zero_floor_count": zero_floors, "unallocated_pool_count": unallocated_pools})


MONEY_TOTALS = ("bid_cost_cents", "credit_cents", "grant_pool_cents", "grant_funded_cents", "grant_allocated_cents",
                "grant_unallocated_cents")


def region_totals(events: list[dict]) -> dict[str, int]:
    def total(key: str) -> int:
        return sum(i[key] for e in events for i in e["intervals"])
    sums = {
        "event_count": len(events),
        "candidate_offer_count": sum(e["candidate_offer_count"] for e in events),
        "selected_offer_count": sum(len(e["selected_offer_ids"]) for e in events),
        "relief_ticks": total("relief_ticks"), "recovery_ticks": total("recovery_ticks"),
        "shortfall_ticks": total("shortfall_ticks"), "overdelivery_ticks": total("overdelivery_ticks"),
    }
    sums.update({key: sum(e[key] for e in events) for key in MONEY_TOTALS})
    return sums


def assemble(ex, region_events, segment_rows, ties, cap_binding, residual_total, residual_ties, extra) -> dict[str, dict]:
    files: dict[str, dict] = {}
    region_sums = {}
    for region, events in region_events.items():
        region_sums[region] = region_totals(events)
        files[f"region_{region}.json"] = {"region": region, "events": events, "totals": region_sums[region]}
    segment_sums = {}
    for seg, entries in segment_rows.items():
        entries.sort(key=lambda e: (e["event_id"], e["region"]))
        segment_sums[seg] = {key: sum(e[key] for e in entries) for key in
                             ("relief_ticks", "recovery_ticks", "bid_cost_cents", "credit_cents", "floor_ticks")}
        segment_sums[seg]["selected_offer_count"] = sum(len(e["selected_offer_ids"]) for e in entries)
        files[f"segment_{seg}.json"] = {"segment": seg, "event_regions": entries, "totals": segment_sums[seg]}

    summary = {"event_count": len(ex.events), "event_region_count": len(ex.events) * len(ex.regions),
               "site_count": len(ex.sites)}
    for key in ("candidate_offer_count", "selected_offer_count", "relief_ticks", "recovery_ticks", "shortfall_ticks",
                "overdelivery_ticks", *MONEY_TOTALS):
        summary[key] = sum(r[key] for r in region_sums.values())
    summary["regions"] = {r: {k: s[k] for k in ("selected_offer_count", "relief_ticks", "bid_cost_cents",
                                                "credit_cents", "grant_allocated_cents")} for r, s in region_sums.items()}
    summary["segments"] = {g: {k: s[k] for k in ("selected_offer_count", "relief_ticks", "bid_cost_cents", "credit_cents")}
                           for g, s in segment_sums.items()}
    files["summary.json"] = summary

    labels = sorted(((s.event_id, s.site_id, label_for(s)) for s in ex.sites.values()))
    counts = dict.fromkeys(LABELS, 0)
    for _, _, label in labels:
        counts[label] += 1
    files["policy_audit.json"] = {
        "compliance_counts": counts,
        "site_labels": [{"event_id": e, "site_id": s, "label": lab} for e, s, lab in labels],
        "tie_decisions": ties, "cap_binding_count": cap_binding,
        "residual_cents": residual_total, "residual_tie_pool_count": residual_ties,
    }
    files["data_quality.json"] = {**ex.quality, **extra}
    return files


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    out = Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for name, payload in sorted(build(Path(argv[1])).items()):
        (out / name).write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
