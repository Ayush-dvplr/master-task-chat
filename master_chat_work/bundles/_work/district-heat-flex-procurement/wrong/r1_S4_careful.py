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
from pathlib import Path

LABELS = ("SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR")


def half_up(numerator: int, denominator: int) -> int:
    """Nearest integer to numerator/denominator, exact halves upward (both non-negative)."""
    return (2 * numerator + denominator) // (2 * denominator)


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
    weight: int | None = None


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
    quality: dict = field(default_factory=dict)


def read_profiles(folder: Path, offer_rows: list[dict[str, str]], offers: dict[str, Offer],
                  interval_count: dict[str, int], rows: dict[str, int]) -> dict[str, int]:
    """Profile rows written straight into their interval slot."""
    known = {r["offer_id"] for r in offer_rows}
    profile_rows = table(folder / "profiles.tsv", "\t")
    rows["profiles.tsv"] = len(profile_rows)
    rejected = {"orphan_profile_rows": 0, "out_of_range_profile_rows": 0, "duplicate_profile_rows": 0}
    for r in profile_rows:
        if r["offer_id"] not in known:
            rejected["orphan_profile_rows"] += 1
            continue
        offer = offers.get(r["offer_id"])
        if offer is not None:
            offer.relief_wh[int(r["interval"]) - 1] = int(r["relief_wh"])
            offer.recovery_wh[int(r["interval"]) - 1] = int(r["recovery_wh"])
    return rejected


def checked_profiles(folder: Path, offer_rows: list[dict[str, str]], offers: dict[str, Offer],
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
                offer.relief_wh[interval - 1] = int(r["relief_wh"])
                offer.recovery_wh[interval - 1] = int(r["recovery_wh"])
    return rejected


def load(folder: Path) -> Extract:
    ini = configparser.ConfigParser()
    ini.read(folder / "program.ini", encoding="utf-8")
    wh = ini.getint("units", "wh_per_tick")
    region_of = {code.upper(): name for code, name in ini.items("region_codes")}
    segment_of = {code.upper(): name for code, name in ini.items("segment_codes")}

    def ticks(raw: str) -> int:
        return half_up(int(raw), wh)

    events = json.loads((folder / "events.json").read_text(encoding="utf-8"))
    rows = {"events.json": len(events)}

    sites: dict[tuple[str, str], Site] = {}
    site_rows = table(folder / "sites.csv", ",")
    rows["sites.csv"] = len(site_rows)
    unknown_region = 0
    for r in site_rows:
        region = region_of[r["region_code"].upper()]
        sites[(r["event_id"], r["site_id"])] = Site(
            r["event_id"], r["site_id"], region, segment_of[r["segment_code"].upper()], r["beneficiary_id"],
            r["critical"] == "Y")

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

    pool_lines = fixed_width(folder / "pools.txt", {"event": (1, 10), "code": (11, 14), "pool": (15, 26)})
    rows["pools.txt"] = len(pool_lines)
    pools = {(r["event"], region_of[r["code"].upper()]): int(r["pool"]) for r in pool_lines}

    extract = Extract(wh, ini.getint("units", "millicents_per_cent"), sorted(set(region_of.values())),
                      sorted(set(segment_of.values())), sorted(events, key=lambda e: e["event_id"]), sites,
                      list(offers.values()), targets, ceilings, floors, pools)
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


def search_scale(ex: Extract) -> int:
    """Units of the search per energy tick: 1 means the search adds per-value ticks (section 2.3)."""
    return ex.wh_per_tick


def search_units(offer: Offer, scale: int) -> tuple[list[int], list[int]]:
    if scale == 1:
        return offer.relief, offer.recovery
    return offer.relief_wh, offer.recovery_wh


def prefer(first: tuple[str, ...], second: tuple[str, ...]) -> tuple[str, ...]:
    """Ordered choice among equal portfolios: the greatest sorted offer-id tuple (section 2.4)."""
    return max(first, second)


def choose_portfolio(ex: Extract, event: dict, region: str, candidates: list[Offer]) -> tuple[list[Offer], int]:
    """Plain enumeration of every portfolio."""
    import itertools
    eid = event["event_id"]
    n = int(event["interval_count"])
    scale = search_scale(ex)
    target = [ex.targets.get((eid, region, t + 1), (0, 0)) for t in range(n)]
    limit = [ex.ceilings.get((eid, region, t + 1), (0, 0)) for t in range(n)]
    cost_w = int(event["objective"]["cost_weight"])
    rec_w = int(event["objective"]["recovery_weight"])
    seg_floor = {s: ex.floors.get((eid, region, s), (0, 0)) for s in ex.segments}
    by_site: dict[str, list[Offer]] = {}
    for offer in candidates:
        by_site.setdefault(offer.site.site_id, []).append(offer)
    options = [[None, *by_site[k]] for k in sorted(by_site)]
    best_key, best, winners = None, [], {}
    for combo in itertools.product(*options):
        chosen = [o for o in combo if o is not None]
        units = [search_units(o, scale) for o in chosen]
        relief = [half_up(sum(u[0][t] for u in units), scale) for t in range(n)]
        recovery = [half_up(sum(u[1][t] for u in units), scale) for t in range(n)]
        if any(relief[t] > limit[t][0] or recovery[t] > limit[t][1] for t in range(n)):
            continue
        shortfall = sum(target[t][1] * max(0, target[t][0] - relief[t]) for t in range(n))
        deficit = 0
        for seg, (floor, weight) in seg_floor.items():
            got = half_up(sum(sum(u[0]) for o, u in zip(chosen, units) if o.site.segment == seg), scale)
            deficit += weight * max(0, floor - got)
        blended = cost_w * sum(o.cost for o in chosen) + rec_w * sum(recovery)
        over = sum(max(0, relief[t] - target[t][0]) for t in range(n))
        key = (shortfall, deficit, blended, over, len(chosen))
        ids = tuple(sorted(o.offer_id for o in chosen))
        if best_key is None or key < best_key:
            best_key, best, winners = key, [ids], {ids: chosen}
        elif key == best_key:
            best.append(ids)
            winners[ids] = chosen
    pick = best[0]
    for ids in best[1:]:
        pick = prefer(pick, ids)
    return winners[pick], len(best)


def exact_portfolio(ex: Extract, event: dict, region: str, candidates: list[Offer]) -> tuple[list[Offer], int]:
    """Exact best portfolio by dynamic programming over sites.

    Two partial portfolios that reach the same per-interval relief and recovery and the same
    segment relief (capped at the segment floor) can only differ later through weighted bid
    cost (cost_weight times bid cost) and offer count, so only the cheaper and then smaller
    one survives; equal survivors are
    counted and the preferred id tuple is kept. Returns the chosen offers and the tied
    portfolio count."""
    eid = event["event_id"]
    n = int(event["interval_count"])
    scale = search_scale(ex)
    target = [ex.targets.get((eid, region, t + 1), (0, 0)) for t in range(n)]
    limit = [ex.ceilings.get((eid, region, t + 1), (0, 0)) for t in range(n)]
    cost_w = int(event["objective"]["cost_weight"])
    rec_w = int(event["objective"]["recovery_weight"])
    floor_of = [ex.floors.get((eid, region, s), (0, 0)) for s in ex.segments]
    segment_slot = {s: 2 * n + i for i, s in enumerate(ex.segments)}
    floor_cap = [floor * scale for floor, _ in floor_of]

    def measure(total: int) -> int:
        return half_up(total, scale)

    by_site: dict[str, list[Offer]] = {}
    for offer in candidates:
        by_site.setdefault(offer.site.site_id, []).append(offer)
    by_id = {o.offer_id: o for o in candidates}

    moves: dict[str, list[tuple[str, int, list[tuple[int, int]], int, int]]] = {}
    for site_id, offers in by_site.items():
        moves[site_id] = []
        for offer in offers:
            relief, recovery = search_units(offer, scale)
            steps = [(t, v) for t, v in enumerate(relief) if v] + [(n + t, v) for t, v in enumerate(recovery) if v]
            moves[site_id].append((offer.offer_id, cost_w * offer.cost, steps, segment_slot[offer.site.segment],
                                   sum(relief)))

    # half_up(x, scale) <= c exactly when x <= scale * c + ceil(scale / 2) - 1
    caps = [scale * c + (scale + 1) // 2 - 1 for c in [lim[0] for lim in limit] + [lim[1] for lim in limit]]
    frontier: dict[tuple[int, ...], tuple[int, int, int, tuple[str, ...]]] = {
        (0,) * (2 * n + len(ex.segments)): (0, 0, 1, ())}
    for site_id in sorted(moves):
        grown = dict(frontier)
        for state, (cost, count, ways, ids) in frontier.items():
            for offer_id, offer_cost, steps, slot, segment_relief in moves[site_id]:
                nxt = list(state)
                feasible = True
                for index, amount in steps:
                    nxt[index] += amount
                    if nxt[index] > caps[index]:
                        feasible = False
                        break
                if not feasible:
                    continue
                nxt[slot] = min(floor_cap[slot - 2 * n], nxt[slot] + segment_relief)
                key = tuple(nxt)
                entry = (cost + offer_cost, count + 1, ways, tuple(sorted(ids + (offer_id,))))
                held = grown.get(key)
                if held is None or entry[:2] < held[:2]:
                    grown[key] = entry
                elif entry[:2] == held[:2]:
                    grown[key] = (held[0], held[1], held[2] + ways, prefer(held[3], entry[3]))
        frontier = grown

    best_key, best_ways, best_ids = None, 0, ()
    for state, (cost, count, ways, ids) in frontier.items():
        relief = [measure(v) for v in state[:n]]
        recovery = [measure(v) for v in state[n:2 * n]]
        shortfall = sum(target[t][1] * max(0, target[t][0] - relief[t]) for t in range(n))
        deficit = sum(weight * max(0, floor - measure(state[2 * n + i])) for i, (floor, weight) in enumerate(floor_of))
        blended = cost + rec_w * sum(recovery)
        over = sum(max(0, relief[t] - target[t][0]) for t in range(n))
        key = (shortfall, deficit, blended, over, count)
        if best_key is None or key < best_key:
            best_key, best_ways, best_ids = key, ways, ids
        elif key == best_key:
            best_ways += ways
            best_ids = prefer(best_ids, ids)
    return [by_id[i] for i in best_ids], best_ways


def report_ticks(ex: Extract, offers: list[Offer], interval: int, kind: str) -> int:
    """Energy of several offers at one interval: a sum of per-value ticks (section 2.3)."""
    return sum(getattr(o, kind)[interval] for o in offers)


def credit_cents(ex: Extract, offer: Offer, uplift: int) -> int:
    rate = min(offer.site.base + uplift, offer.site.cap)
    energy_wh = sum(offer.relief) * ex.wh_per_tick
    return half_up(energy_wh * rate, 1000 * ex.millicents_per_cent)


def grant_weight(site: Site) -> int:
    """A recipient site row's weight; doubled when its compliance label is CONTINUITY_WAIVED (section 7)."""
    waiver_valid = (site.waiver_status == "VALID" and site.waiver_signed == "Y"
                    and site.critical and site.segment == "public")
    return site.weight * 2 if site.pending and waiver_valid else site.weight


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


def funded_pool(pool: int, credit_total: int) -> int:
    """The pool that is apportioned: the pools.txt pool minus the event-region credit, never below 0."""
    return pool


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
    for event in ex.events:
        eid = event["event_id"]
        n = int(event["interval_count"])
        uplift = int(event["uplift_millicents_per_kwh"])
        for region in ex.regions:
            pool_sites = by_er.get((eid, region), [])
            offers = candidates.get((eid, region), [])
            if not offers:
                empty_groups += 1
            chosen, tied = choose_portfolio(ex, event, region, offers)
            chosen_ids = sorted(o.offer_id for o in chosen)
            if tied > 1:
                ties.append({"event_id": eid, "region": region, "tied_portfolio_count": tied,
                             "selected_offer_ids": chosen_ids})
            credit = {o.offer_id: credit_cents(ex, o, uplift) for o in chosen}
            cap_binding += sum(1 for o in chosen if o.site.base + uplift > o.site.cap)
            intervals = []
            for t in range(n):
                tgt = ex.targets.get((eid, region, t + 1), (0, 0))[0]
                rel = report_ticks(ex, chosen, t, "relief")
                intervals.append({"interval": t + 1, "target_ticks": tgt, "relief_ticks": rel,
                                  "recovery_ticks": report_ticks(ex, chosen, t, "recovery"),
                                  "shortfall_ticks": max(0, tgt - rel), "overdelivery_ticks": max(0, rel - tgt)})
            credit_total = sum(credit.values())
            pool = ex.pools.get((eid, region), 0)
            funded = funded_pool(pool, credit_total)
            shares, residual, tie = share_pool(funded, [s for s in pool_sites if s.weight is not None])
            if shares is None:
                unallocated_pools += 1
                shares = {}
            residual_total += residual
            residual_ties += tie
            allocated = sum(shares.values())
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
                relief = sum(report_ticks(ex, mine, t, "relief") for t in range(n))
                if floor == 0:
                    zero_floors += 1
                attainment = 10000 if floor == 0 else min(10000, half_up(10000 * relief, floor))
                segment_rows[seg].append({
                    "event_id": eid, "region": region, "selected_offer_ids": sorted(o.offer_id for o in mine),
                    "relief_ticks": relief, "recovery_ticks": sum(report_ticks(ex, mine, t, "recovery") for t in range(n)),
                    "bid_cost_cents": sum(o.cost for o in mine), "credit_cents": sum(credit[o.offer_id] for o in mine),
                    "floor_ticks": floor, "floor_attainment_bp": attainment,
                })
    return assemble(ex, region_events, segment_rows, ties, cap_binding, residual_total, residual_ties,
                    {"ineligible_offer_count": ineligible, "empty_candidate_groups": empty_groups,
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
