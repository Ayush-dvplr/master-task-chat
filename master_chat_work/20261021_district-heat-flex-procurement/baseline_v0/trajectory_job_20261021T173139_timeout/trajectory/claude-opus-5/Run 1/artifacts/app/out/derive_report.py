#!/usr/bin/env python3
"""Reports for one season extract of the winter demand-response programme.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import configparser
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from types import SimpleNamespace

LABELS = (
    "SAFETY_HOLD",
    "COOLDOWN",
    "CONTINUITY_WAIVED",
    "CERTIFICATE_PENDING",
    "CLEAR",
)


def round_half_up(num, den):
    """Nearest integer to num/den, an exact half going up; both non-negative."""
    return (2 * num + den) // (2 * den)


def data_rows(path, delimiter):
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=delimiter):
            yield row


def fixed_lines(path, spans):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if line.startswith("#") or not line.strip():
                continue
            yield [line[start:stop].strip() for start, stop in spans]


def load_extract(data_dir):
    def path(name):
        return os.path.join(data_dir, name)

    ex = SimpleNamespace()
    rows = {}

    parser = configparser.ConfigParser()
    with open(path("program.ini"), encoding="utf-8") as handle:
        parser.read_file(handle)
    ex.wh_per_tick = int(parser["units"]["wh_per_tick"])
    ex.mc_per_cent = int(parser["units"]["millicents_per_cent"])
    region_of_code = {k.upper(): v for k, v in parser["region_codes"].items()}
    segment_of_code = {k.upper(): v for k, v in parser["segment_codes"].items()}
    ex.region_names = sorted(set(region_of_code.values()))
    ex.segment_names = sorted(set(segment_of_code.values()))
    ex.seg_index = {name: i for i, name in enumerate(ex.segment_names)}

    wh_per_tick = ex.wh_per_tick

    def ticks(value):
        return round_half_up(int(value), wh_per_tick)

    with open(path("events.json"), encoding="utf-8") as handle:
        events = json.load(handle)
    rows["events.json"] = len(events)
    events.sort(key=lambda e: e["event_id"])
    ex.events = events
    ex.event_by_id = {e["event_id"]: e for e in events}

    site_rows = {}
    count = 0
    unknown_region = 0
    for row in data_rows(path("sites.csv"), ","):
        count += 1
        code = row["region_code"].strip().upper()
        if code not in region_of_code:
            unknown_region += 1
            continue
        key = (row["event_id"], row["site_id"])
        site_rows[key] = SimpleNamespace(
            event_id=row["event_id"],
            site_id=row["site_id"],
            region=region_of_code[code],
            segment=segment_of_code[row["segment_code"].strip().upper()],
            beneficiary_id=row["beneficiary_id"],
            critical=row["critical"].strip() == "Y",
            label=None,
        )
    rows["sites.csv"] = count
    ex.site_rows = site_rows
    ex.unknown_region_site_rows = unknown_region

    offer_event = {}
    offer_site = {}
    offer_cost = {}
    count = 0
    orphan_offers = 0
    for row in data_rows(path("offers.csv"), ","):
        count += 1
        offer_id = row["offer_id"]
        key = (row["event_id"], row["site_id"])
        offer_event[offer_id] = row["event_id"]
        if key not in site_rows:
            orphan_offers += 1
            continue
        offer_site[offer_id] = key
        offer_cost[offer_id] = int(row["bid_cost_cents"])
    rows["offers.csv"] = count
    ex.offer_site = offer_site
    ex.offer_cost = offer_cost
    ex.orphan_offer_rows = orphan_offers

    profiles = defaultdict(dict)
    count = 0
    orphan_profiles = 0
    out_of_range = 0
    duplicates = 0
    with open(path("profiles.tsv"), encoding="utf-8") as handle:
        next(handle, None)
        for line in handle:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            count += 1
            offer_id, interval, relief_wh, recovery_wh = line.split("\t")[:4]
            if offer_id not in offer_event:
                orphan_profiles += 1
                continue
            interval = int(interval)
            interval_count = ex.event_by_id[offer_event[offer_id]]["interval_count"]
            if interval < 1 or interval > interval_count:
                out_of_range += 1
                continue
            kept = profiles[offer_id]
            if interval in kept:
                duplicates += 1
                continue
            kept[interval] = (ticks(relief_wh), ticks(recovery_wh))
    rows["profiles.tsv"] = count
    ex.profiles = profiles
    ex.orphan_profile_rows = orphan_profiles
    ex.out_of_range_profile_rows = out_of_range
    ex.duplicate_profile_rows = duplicates

    targets = {}
    count = 0
    for row in data_rows(path("targets.tsv"), "\t"):
        count += 1
        region = region_of_code[row["region_code"].strip().upper()]
        key = (row["event_id"], region, int(row["interval"]))
        targets[key] = (ticks(row["target_wh"]), int(row["shortfall_weight"]))
    rows["targets.tsv"] = count
    ex.targets = targets

    ceilings = {}
    count = 0
    spans = ((0, 10), (10, 14), (14, 17), (17, 27), (27, 37))
    for event_id, code, interval, relief_wh, recovery_wh in fixed_lines(
        path("feeder_limits.txt"), spans
    ):
        count += 1
        region = region_of_code[code.upper()]
        key = (event_id, region, int(interval))
        ceilings[key] = (ticks(relief_wh), ticks(recovery_wh))
    rows["feeder_limits.txt"] = count
    ex.ceilings = ceilings

    state = {}
    count = 0
    with open(path("site_state.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            count += 1
            obj = json.loads(line)
            key = (obj["event_id"], obj["site_id"])
            if key not in site_rows:
                continue
            state[key] = (
                bool(obj["dispatch_authorized"]),
                bool(obj["safety_hold"]),
                bool(obj["cooldown"]),
            )
    rows["site_state.jsonl"] = count
    ex.state = state

    waivers = {}
    count = 0
    signed_missing = 0
    for row in data_rows(path("continuity_waivers.csv"), ","):
        count += 1
        key = (row["event_id"], row["site_id"])
        if key not in site_rows:
            continue
        signed = (row.get("waiver_signed") or "").strip()
        if signed == "":
            signed_missing += 1
        waivers[key] = (
            row["routine_certificate_pending"].strip() == "Y",
            row["waiver_status"].strip(),
            signed,
        )
    rows["continuity_waivers.csv"] = count
    ex.waivers = waivers
    ex.waiver_signed_missing = signed_missing

    floors = {}
    with open(path("segment_floors.json"), encoding="utf-8") as handle:
        entries = json.load(handle)["floors"]
    rows["segment_floors.json"] = len(entries)
    for entry in entries:
        region = region_of_code[entry["region_code"].strip().upper()]
        segment = segment_of_code[entry["segment_code"].strip().upper()]
        floors[(entry["event_id"], region, segment)] = (
            ticks(entry["floor_wh"]),
            int(entry["priority_weight"]),
        )
    ex.floors = floors

    cards = {}
    count = 0
    root = ET.parse(path("rate_cards.xml")).getroot()
    for card in root.findall("card"):
        count += 1
        key = (card.get("event"), card.get("site"))
        if key not in site_rows:
            continue
        cards[key] = (int(card.find("base").text), int(card.find("cap").text))
    rows["rate_cards.xml"] = count
    ex.cards = cards

    weights = {}
    count = 0
    for row in data_rows(path("recipient_weights.tsv"), "\t"):
        count += 1
        key = (row["event_id"], row["site_id"])
        if key not in site_rows:
            continue
        weights[key] = int(row["grant_weight"])
    rows["recipient_weights.tsv"] = count
    ex.weights = weights

    pools = {}
    count = 0
    for event_id, code, cents in fixed_lines(
        path("pools.txt"), ((0, 10), (10, 14), (14, 26))
    ):
        count += 1
        pools[(event_id, region_of_code[code.upper()])] = int(cents)
    rows["pools.txt"] = count
    ex.pools = pools

    ex.rows = rows
    return ex


def label_sites(ex):
    for key, site in ex.site_rows.items():
        authorized, safety_hold, cooldown = ex.state.get(key, (False, False, False))
        pending, status, signed = ex.waivers.get(key, (False, "NONE", ""))
        waiver_valid = (
            status == "VALID"
            and signed == "Y"
            and site.critical
            and site.segment == "public"
        )
        if safety_hold:
            site.label = "SAFETY_HOLD"
        elif cooldown:
            site.label = "COOLDOWN"
        elif pending and waiver_valid:
            site.label = "CONTINUITY_WAIVED"
        elif pending:
            site.label = "CERTIFICATE_PENDING"
        else:
            site.label = "CLEAR"
        site.can_dispatch = authorized


def _drop_dominated(options, ic, cost_weight, recovery_weight):
    """Remove options that can never sit in a best or tied-at-best portfolio.

    An option is dropped only when another choice at the same site matches it on
    relief in every interval (so the shortfall, floor and overdelivery
    components are untouched), needs no more recovery in any interval (so it is
    feasible wherever the dropped one is) and has a strictly smaller blended
    cost. Swapping in that choice then makes any portfolio strictly better, so
    nothing that is dropped could have tied at the best value.
    """
    real = [o for o in options if o is not None]
    kept = []
    for option in real:
        if option[4] == 0 and option[6] == 0:
            continue  # choosing no offer matches it and keeps the portfolio smaller
        blended = cost_weight * option[1] + recovery_weight * option[6]
        dominated = False
        for other in real:
            if other is option or other[2] != option[2]:
                continue
            if any(other[3][t] > option[3][t] for t in range(ic)):
                continue
            if cost_weight * other[1] + recovery_weight * other[6] < blended:
                dominated = True
                break
        if not dominated:
            kept.append(option)
    kept.append(None)
    return kept


def _cheaper(a, b):
    """True when rate `a` is below rate `b`; a rate is a (blended, relief) pair."""
    if b is None:
        return True
    if a is None:
        return False
    return a[0] * b[1] < b[0] * a[1]


def _greedy_value(groups, ic, tgt, shortfall_w, relief_cap, recovery_cap, floors,
                  cost_weight, recovery_weight):
    """Objective of one feasible portfolio, used only to prime the search bound.

    Each site takes whichever of its choices looks best while the sites after it
    are still empty. The result is just a feasible portfolio, so its value is a
    valid upper bound on the best value and nothing here can change the outcome.
    """
    nseg = len(floors)
    relief = [0] * ic
    recovery = [0] * ic
    segment_relief = [0] * nseg
    cost = 0
    recovery_total = 0
    size = 0

    def value():
        weighted_shortfall = 0
        overdelivery = 0
        for t in range(ic):
            spare = relief[t] - tgt[t]
            if spare < 0:
                weighted_shortfall -= shortfall_w[t] * spare
            else:
                overdelivery += spare
        floor_deficit = 0
        for s in range(nseg):
            floor_ticks, priority = floors[s]
            gap = floor_ticks - segment_relief[s]
            if gap > 0:
                floor_deficit += priority * gap
        return (
            weighted_shortfall,
            floor_deficit,
            cost_weight * cost + recovery_weight * recovery_total,
            overdelivery,
            size,
        )

    def apply(option, sign):
        nonlocal cost, recovery_total, size
        for t in range(ic):
            relief[t] += sign * option[2][t]
            recovery[t] += sign * option[3][t]
        segment_relief[option[5]] += sign * option[4]
        cost += sign * option[1]
        recovery_total += sign * option[6]
        size += sign

    for options in groups:
        best_key = value()
        best_option = None
        for option in options:
            if option is None:
                continue
            feasible = True
            for t in range(ic):
                if (relief[t] + option[2][t] > relief_cap[t]
                        or recovery[t] + option[3][t] > recovery_cap[t]):
                    feasible = False
                    break
            if not feasible:
                continue
            apply(option, 1)
            key = value()
            apply(option, -1)
            if key < best_key:
                best_key = key
                best_option = option
        if best_option is not None:
            apply(best_option, 1)
    return value()


def choose_portfolio(groups, ic, tgt, shortfall_w, relief_cap, recovery_cap, floors,
                     cost_weight, recovery_weight):
    """Exact lexicographic best portfolio.

    `groups` is one list of options per candidate site; an option is
    (offer_id, cost, relief[ic], recovery[ic], relief_total, segment, recovery_total)
    and None stands for choosing no offer at that site. Returns the winning
    objective tuple, its offer ids and the number of portfolios tied on it.

    Depth-first search over the sites against a lexicographic lower bound on the
    objective. The bound is evaluated one component at a time and the next
    component is only derived while the ones before it sit exactly on the
    incumbent. A node is cut only when some component is strictly worse than the
    incumbent's, so every portfolio tied at the best value is still reached and
    counted.
    """
    groups = [_drop_dominated(o, ic, cost_weight, recovery_weight) for o in groups]
    n = len(groups)
    nseg = len(floors)

    # Per suffix of sites: the most relief still reachable, the most weighted
    # shortfall still removable, and the cheapest blended cost per tick of relief
    # still on offer. All ignore the ceilings, which is what makes them bounds.
    suffix_relief = [[0] * ic for _ in range(n + 1)]
    suffix_segment = [[0] * nseg for _ in range(n + 1)]
    suffix_cover = [0] * (n + 1)
    rate_interval = [[None] * (n + 1) for _ in range(ic)]
    rate_segment = [[None] * (n + 1) for _ in range(nseg)]
    for i in range(n - 1, -1, -1):
        options = [o for o in groups[i] if o is not None]
        for t in range(ic):
            best_add = 0
            site_rate = None
            for option in options:
                gain = option[2][t]
                if gain > best_add:
                    best_add = gain
                if gain > 0:
                    rate = (cost_weight * option[1] + recovery_weight * option[6], gain)
                    if _cheaper(rate, site_rate):
                        site_rate = rate
            suffix_relief[i][t] = suffix_relief[i + 1][t] + best_add
            later = rate_interval[t][i + 1]
            rate_interval[t][i] = site_rate if _cheaper(site_rate, later) else later
        for s in range(nseg):
            best_add = 0
            site_rate = None
            for option in options:
                if option[5] != s:
                    continue
                gain = option[4]
                if gain > best_add:
                    best_add = gain
                if gain > 0:
                    rate = (cost_weight * option[1] + recovery_weight * option[6], gain)
                    if _cheaper(rate, site_rate):
                        site_rate = rate
            suffix_segment[i][s] = suffix_segment[i + 1][s] + best_add
            later = rate_segment[s][i + 1]
            rate_segment[s][i] = site_rate if _cheaper(site_rate, later) else later
        # A site fills one mode only, so the weighted shortfall it can remove is
        # at most that of its single most useful offer. Summing this over a
        # suffix bounds the whole suffix, because covering a need with several
        # sites never removes more than covering it with each of them alone.
        best_cover = 0
        for option in options:
            relief_option = option[2]
            cover = 0
            for t in range(ic):
                weight = shortfall_w[t]
                if weight:
                    gain = relief_option[t]
                    if gain > tgt[t]:
                        gain = tgt[t]
                    cover += weight * gain
            if cover > best_cover:
                best_cover = cover
        suffix_cover[i] = suffix_cover[i + 1] + best_cover

    relief = [0] * ic
    recovery = [0] * ic
    segment_relief = [0] * nseg
    chosen = []
    best = _greedy_value(groups, ic, tgt, shortfall_w, relief_cap, recovery_cap,
                         floors, cost_weight, recovery_weight)
    best_ids = None
    tied = 0

    def dfs(i, cost, recovery_total, size):
        nonlocal best, best_ids, tied
        reachable = suffix_relief[i]
        max_relief_bound = 0
        shortfall_now = 0
        for t in range(ic):
            weight = shortfall_w[t]
            if weight:
                gap = tgt[t] - relief[t]
                if gap > 0:
                    shortfall_now += weight * gap
                    reach = relief[t] + reachable[t]
                    if reach > relief_cap[t]:
                        reach = relief_cap[t]
                    gap = tgt[t] - reach
                    if gap > 0:
                        max_relief_bound += weight * gap
        weighted_shortfall = shortfall_now - suffix_cover[i]
        if max_relief_bound > weighted_shortfall:
            weighted_shortfall = max_relief_bound
        if weighted_shortfall > best[0]:
            return
        if weighted_shortfall == best[0]:
            remaining = suffix_segment[i]
            floor_deficit = 0
            for s in range(nseg):
                floor_ticks, priority = floors[s]
                if priority:
                    gap = floor_ticks - segment_relief[s] - remaining[s]
                    if gap > 0:
                        floor_deficit += priority * gap
            if floor_deficit > best[1]:
                return
            if floor_deficit == best[1]:
                # Holding the shortfall and the floor deficit at the bound forces
                # a known amount of extra relief in each interval and segment, and
                # that relief cannot cost less than the cheapest rate still on
                # offer.
                extra = 0
                # Sitting on the shortfall bound only forces relief in a given
                # interval while the max-relief bound is the binding one. When
                # the per-site coverage bound binds instead, the shortfall can be
                # held without filling any particular interval, so nothing is
                # owed for it.
                forced = range(ic) if max_relief_bound == best[0] else ()
                for t in forced:
                    if not shortfall_w[t]:
                        continue
                    reach = relief[t] + reachable[t]
                    if reach > relief_cap[t]:
                        reach = relief_cap[t]
                    if reach > tgt[t]:
                        reach = tgt[t]
                    need = reach - relief[t]
                    if need > 0:
                        rate = rate_interval[t][i]
                        if rate is not None:
                            owed = -(-rate[0] * need // rate[1])
                            if owed > extra:
                                extra = owed
                for s in range(nseg):
                    floor_ticks, priority = floors[s]
                    if not priority:
                        continue
                    reach = segment_relief[s] + remaining[s]
                    if reach > floor_ticks:
                        reach = floor_ticks
                    need = reach - segment_relief[s]
                    if need > 0:
                        rate = rate_segment[s][i]
                        if rate is not None:
                            owed = -(-rate[0] * need // rate[1])
                            if owed > extra:
                                extra = owed
                blended = cost_weight * cost + recovery_weight * recovery_total
                if blended + extra > best[2]:
                    return
                if blended + extra == best[2]:
                    overdelivery = 0
                    for t in range(ic):
                        spare = relief[t] - tgt[t]
                        if spare > 0:
                            overdelivery += spare
                    if overdelivery > best[3]:
                        return
                    if overdelivery == best[3] and size > best[4]:
                        return
        if i == n:
            weighted_shortfall = 0
            overdelivery = 0
            for t in range(ic):
                spare = relief[t] - tgt[t]
                if spare < 0:
                    weighted_shortfall -= shortfall_w[t] * spare
                else:
                    overdelivery += spare
            floor_deficit = 0
            for s in range(nseg):
                floor_ticks, priority = floors[s]
                gap = floor_ticks - segment_relief[s]
                if gap > 0:
                    floor_deficit += priority * gap
            value = (
                weighted_shortfall,
                floor_deficit,
                cost_weight * cost + recovery_weight * recovery_total,
                overdelivery,
                size,
            )
            ids = tuple(sorted(chosen))
            if value < best:
                best, best_ids, tied = value, ids, 1
            elif value == best:
                if best_ids is None:
                    best_ids, tied = ids, 1
                else:
                    tied += 1
                    if ids > best_ids:
                        best_ids = ids
            return
        for option in groups[i]:
            if option is None:
                dfs(i + 1, cost, recovery_total, size)
                continue
            add_relief, add_recovery = option[2], option[3]
            feasible = True
            for t in range(ic):
                if (relief[t] + add_relief[t] > relief_cap[t]
                        or recovery[t] + add_recovery[t] > recovery_cap[t]):
                    feasible = False
                    break
            if not feasible:
                continue
            for t in range(ic):
                relief[t] += add_relief[t]
                recovery[t] += add_recovery[t]
            segment_relief[option[5]] += option[4]
            chosen.append(option[0])
            dfs(i + 1, cost + option[1], recovery_total + option[6], size + 1)
            chosen.pop()
            segment_relief[option[5]] -= option[4]
            for t in range(ic):
                relief[t] -= add_relief[t]
                recovery[t] -= add_recovery[t]

    dfs(0, 0, 0, 0)
    return best, best_ids, tied


def apportion(funded, weight_of_beneficiary):
    """Largest remainder share-out. Returns (grants, allocated, residual, tie).

    `grants` is None when the pool is unallocated: no recipients, or total
    weight 0.
    """
    total = sum(weight_of_beneficiary.values())
    if not weight_of_beneficiary or total == 0:
        return None, 0, 0, False
    positive = {b: w for b, w in weight_of_beneficiary.items() if w > 0}
    cents = {}
    remainder = {}
    for beneficiary, weight in positive.items():
        cents[beneficiary] = funded * weight // total
        remainder[beneficiary] = funded * weight % total
    residual = funded - sum(cents.values())
    order = sorted(positive, key=lambda b: (remainder[b], b), reverse=True)
    for beneficiary in order[:residual]:
        cents[beneficiary] += 1
    seen = set()
    tie = False
    for value in remainder.values():
        if value:
            if value in seen:
                tie = True
                break
            seen.add(value)
    return cents, sum(cents.values()), residual, tie


def build_reports(ex):
    label_sites(ex)

    sites_by_er = defaultdict(list)
    for key, site in ex.site_rows.items():
        sites_by_er[(site.event_id, site.region)].append(key)
    for keys in sites_by_er.values():
        keys.sort()
    offers_by_site = defaultdict(list)
    for offer_id, key in ex.offer_site.items():
        offers_by_site[key].append(offer_id)

    region_names = ex.region_names
    segment_names = ex.segment_names
    seg_index = ex.seg_index
    wh_per_tick = ex.wh_per_tick
    credit_den = 1000 * ex.mc_per_cent

    region_events = {name: [] for name in region_names}
    segment_entries = {name: [] for name in segment_names}
    tie_decisions = []
    totals = defaultdict(int)
    region_summary = {
        name: defaultdict(int) for name in region_names
    }
    segment_summary = {
        name: defaultdict(int) for name in segment_names
    }
    cap_binding_count = 0
    residual_cents = 0
    residual_tie_pools = 0
    empty_candidate_groups = 0
    zero_floor_count = 0
    unallocated_pool_count = 0

    for event in ex.events:
        event_id = event["event_id"]
        ic = event["interval_count"]
        cost_weight = event["objective"]["cost_weight"]
        recovery_weight = event["objective"]["recovery_weight"]
        uplift = event["uplift_millicents_per_kwh"]
        for region in region_names:
            keys = sites_by_er.get((event_id, region), [])
            tgt = [0] * ic
            shortfall_w = [0] * ic
            relief_cap = [0] * ic
            recovery_cap = [0] * ic
            for t in range(1, ic + 1):
                target = ex.targets.get((event_id, region, t))
                if target is not None:
                    tgt[t - 1], shortfall_w[t - 1] = target
                ceiling = ex.ceilings.get((event_id, region, t))
                if ceiling is not None:
                    relief_cap[t - 1], recovery_cap[t - 1] = ceiling
            floors = []
            for segment in segment_names:
                floor = ex.floors.get((event_id, region, segment), (0, 0))
                floors.append(floor)
                if floor[0] == 0:
                    zero_floor_count += 1

            groups = []
            candidate_offer_count = 0
            for key in keys:
                site = ex.site_rows[key]
                if not site.can_dispatch:
                    continue
                offer_ids = offers_by_site.get(key)
                if not offer_ids:
                    continue
                candidate_offer_count += len(offer_ids)
                options = []
                segment = seg_index[site.segment]
                for offer_id in sorted(offer_ids):
                    kept = ex.profiles.get(offer_id, {})
                    relief = [0] * ic
                    recovery = [0] * ic
                    for interval, (relief_ticks, recovery_ticks) in kept.items():
                        relief[interval - 1] = relief_ticks
                        recovery[interval - 1] = recovery_ticks
                    options.append((
                        offer_id,
                        ex.offer_cost[offer_id],
                        relief,
                        recovery,
                        sum(relief),
                        segment,
                        sum(recovery),
                    ))
                options.sort(key=lambda o: (-o[4], o[1], o[0]))
                options.append(None)
                groups.append((key, options))
            if candidate_offer_count == 0:
                empty_candidate_groups += 1
            groups.sort(
                key=lambda item: (
                    -max(o[4] for o in item[1] if o is not None),
                    item[0],
                )
            )

            _, selected, tied = choose_portfolio(
                [options for _, options in groups],
                ic,
                tgt,
                shortfall_w,
                relief_cap,
                recovery_cap,
                floors,
                cost_weight,
                recovery_weight,
            )
            selected_ids = sorted(selected)
            if tied >= 2:
                tie_decisions.append({
                    "event_id": event_id,
                    "region": region,
                    "tied_portfolio_count": tied,
                    "selected_offer_ids": selected_ids,
                })

            relief_per_interval = [0] * ic
            recovery_per_interval = [0] * ic
            bid_cost_cents = 0
            credit_cents = 0
            per_segment = {
                name: {
                    "offer_ids": [],
                    "relief_ticks": 0,
                    "recovery_ticks": 0,
                    "bid_cost_cents": 0,
                    "credit_cents": 0,
                }
                for name in segment_names
            }
            for offer_id in selected_ids:
                key = ex.offer_site[offer_id]
                site = ex.site_rows[key]
                kept = ex.profiles.get(offer_id, {})
                relief_total = 0
                recovery_total = 0
                for interval, (relief_ticks, recovery_ticks) in kept.items():
                    relief_per_interval[interval - 1] += relief_ticks
                    recovery_per_interval[interval - 1] += recovery_ticks
                    relief_total += relief_ticks
                    recovery_total += recovery_ticks
                cost = ex.offer_cost[offer_id]
                bid_cost_cents += cost
                base, cap = ex.cards.get(key, (0, 0))
                rate = base + uplift
                if rate > cap:
                    rate = cap
                    cap_binding_count += 1
                credit = round_half_up(relief_total * wh_per_tick * rate, credit_den)
                credit_cents += credit
                bucket = per_segment[site.segment]
                bucket["offer_ids"].append(offer_id)
                bucket["relief_ticks"] += relief_total
                bucket["recovery_ticks"] += recovery_total
                bucket["bid_cost_cents"] += cost
                bucket["credit_cents"] += credit

            intervals = []
            relief_ticks = 0
            recovery_ticks = 0
            shortfall_ticks = 0
            overdelivery_ticks = 0
            for t in range(ic):
                shortfall = tgt[t] - relief_per_interval[t]
                over = -shortfall
                if shortfall < 0:
                    shortfall = 0
                if over < 0:
                    over = 0
                intervals.append({
                    "interval": t + 1,
                    "target_ticks": tgt[t],
                    "relief_ticks": relief_per_interval[t],
                    "recovery_ticks": recovery_per_interval[t],
                    "shortfall_ticks": shortfall,
                    "overdelivery_ticks": over,
                })
                relief_ticks += relief_per_interval[t]
                recovery_ticks += recovery_per_interval[t]
                shortfall_ticks += shortfall
                overdelivery_ticks += over

            pool_cents = ex.pools.get((event_id, region), 0)
            funded = pool_cents - credit_cents
            if funded < 0:
                funded = 0
            weight_of_beneficiary = {}
            for key in keys:
                weight = ex.weights.get(key)
                if weight is None:
                    continue
                site = ex.site_rows[key]
                if site.label == "CONTINUITY_WAIVED":
                    weight *= 2
                beneficiary = site.beneficiary_id
                weight_of_beneficiary[beneficiary] = (
                    weight_of_beneficiary.get(beneficiary, 0) + weight
                )
            grants, allocated, residual, tie = apportion(funded, weight_of_beneficiary)
            residual_cents += residual
            if tie:
                residual_tie_pools += 1
            if grants is None:
                unallocated_pool_count += 1
                grant_entries = []
            else:
                grant_entries = [
                    {"beneficiary_id": beneficiary, "cents": grants[beneficiary]}
                    for beneficiary in sorted(grants)
                ]
            unallocated = funded - allocated

            compliance_counts = {label: 0 for label in LABELS}
            for key in keys:
                compliance_counts[ex.site_rows[key].label] += 1

            region_events[region].append({
                "event_id": event_id,
                "candidate_offer_count": candidate_offer_count,
                "selected_offer_ids": selected_ids,
                "intervals": intervals,
                "bid_cost_cents": bid_cost_cents,
                "credit_cents": credit_cents,
                "grant_pool_cents": pool_cents,
                "grant_funded_cents": funded,
                "grant_allocated_cents": allocated,
                "grant_unallocated_cents": unallocated,
                "grants": grant_entries,
                "compliance_counts": compliance_counts,
            })

            for segment in segment_names:
                bucket = per_segment[segment]
                floor_ticks, _ = ex.floors.get((event_id, region, segment), (0, 0))
                segment_relief = bucket["relief_ticks"]
                if floor_ticks == 0:
                    attainment = 10000
                else:
                    attainment = round_half_up(10000 * segment_relief, floor_ticks)
                    if attainment > 10000:
                        attainment = 10000
                segment_entries[segment].append({
                    "event_id": event_id,
                    "region": region,
                    "selected_offer_ids": sorted(bucket["offer_ids"]),
                    "relief_ticks": segment_relief,
                    "recovery_ticks": bucket["recovery_ticks"],
                    "bid_cost_cents": bucket["bid_cost_cents"],
                    "credit_cents": bucket["credit_cents"],
                    "floor_ticks": floor_ticks,
                    "floor_attainment_bp": attainment,
                })
                summary = segment_summary[segment]
                summary["selected_offer_count"] += len(bucket["offer_ids"])
                summary["relief_ticks"] += segment_relief
                summary["bid_cost_cents"] += bucket["bid_cost_cents"]
                summary["credit_cents"] += bucket["credit_cents"]

            summary = region_summary[region]
            summary["selected_offer_count"] += len(selected_ids)
            summary["relief_ticks"] += relief_ticks
            summary["bid_cost_cents"] += bid_cost_cents
            summary["credit_cents"] += credit_cents
            summary["grant_allocated_cents"] += allocated

            totals["candidate_offer_count"] += candidate_offer_count
            totals["selected_offer_count"] += len(selected_ids)
            totals["relief_ticks"] += relief_ticks
            totals["recovery_ticks"] += recovery_ticks
            totals["shortfall_ticks"] += shortfall_ticks
            totals["overdelivery_ticks"] += overdelivery_ticks
            totals["bid_cost_cents"] += bid_cost_cents
            totals["credit_cents"] += credit_cents
            totals["grant_pool_cents"] += pool_cents
            totals["grant_funded_cents"] += funded
            totals["grant_allocated_cents"] += allocated
            totals["grant_unallocated_cents"] += unallocated

    reports = {}
    for region in region_names:
        events_out = region_events[region]
        region_totals = {
            "event_count": len(events_out),
            "candidate_offer_count": 0,
            "selected_offer_count": 0,
            "relief_ticks": 0,
            "recovery_ticks": 0,
            "shortfall_ticks": 0,
            "overdelivery_ticks": 0,
            "bid_cost_cents": 0,
            "credit_cents": 0,
            "grant_pool_cents": 0,
            "grant_funded_cents": 0,
            "grant_allocated_cents": 0,
            "grant_unallocated_cents": 0,
        }
        for entry in events_out:
            region_totals["candidate_offer_count"] += entry["candidate_offer_count"]
            region_totals["selected_offer_count"] += len(entry["selected_offer_ids"])
            for interval in entry["intervals"]:
                region_totals["relief_ticks"] += interval["relief_ticks"]
                region_totals["recovery_ticks"] += interval["recovery_ticks"]
                region_totals["shortfall_ticks"] += interval["shortfall_ticks"]
                region_totals["overdelivery_ticks"] += interval["overdelivery_ticks"]
            for field in (
                "bid_cost_cents",
                "credit_cents",
                "grant_pool_cents",
                "grant_funded_cents",
                "grant_allocated_cents",
                "grant_unallocated_cents",
            ):
                region_totals[field] += entry[field]
        reports["region_%s.json" % region] = {
            "region": region,
            "events": events_out,
            "totals": region_totals,
        }

    for segment in segment_names:
        entries = segment_entries[segment]
        segment_totals = {
            "selected_offer_count": 0,
            "relief_ticks": 0,
            "recovery_ticks": 0,
            "bid_cost_cents": 0,
            "credit_cents": 0,
            "floor_ticks": 0,
        }
        for entry in entries:
            segment_totals["selected_offer_count"] += len(entry["selected_offer_ids"])
            for field in (
                "relief_ticks",
                "recovery_ticks",
                "bid_cost_cents",
                "credit_cents",
                "floor_ticks",
            ):
                segment_totals[field] += entry[field]
        reports["segment_%s.json" % segment] = {
            "segment": segment,
            "event_regions": entries,
            "totals": segment_totals,
        }

    reports["summary.json"] = {
        "event_count": len(ex.events),
        "event_region_count": len(ex.events) * len(region_names),
        "site_count": len(ex.site_rows),
        "candidate_offer_count": totals["candidate_offer_count"],
        "selected_offer_count": totals["selected_offer_count"],
        "relief_ticks": totals["relief_ticks"],
        "recovery_ticks": totals["recovery_ticks"],
        "shortfall_ticks": totals["shortfall_ticks"],
        "overdelivery_ticks": totals["overdelivery_ticks"],
        "bid_cost_cents": totals["bid_cost_cents"],
        "credit_cents": totals["credit_cents"],
        "grant_pool_cents": totals["grant_pool_cents"],
        "grant_funded_cents": totals["grant_funded_cents"],
        "grant_allocated_cents": totals["grant_allocated_cents"],
        "grant_unallocated_cents": totals["grant_unallocated_cents"],
        "regions": {
            region: {
                "selected_offer_count": region_summary[region]["selected_offer_count"],
                "relief_ticks": region_summary[region]["relief_ticks"],
                "bid_cost_cents": region_summary[region]["bid_cost_cents"],
                "credit_cents": region_summary[region]["credit_cents"],
                "grant_allocated_cents":
                    region_summary[region]["grant_allocated_cents"],
            }
            for region in region_names
        },
        "segments": {
            segment: {
                "selected_offer_count":
                    segment_summary[segment]["selected_offer_count"],
                "relief_ticks": segment_summary[segment]["relief_ticks"],
                "bid_cost_cents": segment_summary[segment]["bid_cost_cents"],
                "credit_cents": segment_summary[segment]["credit_cents"],
            }
            for segment in segment_names
        },
    }

    compliance_counts = {label: 0 for label in LABELS}
    site_labels = []
    for key in sorted(ex.site_rows):
        site = ex.site_rows[key]
        compliance_counts[site.label] += 1
        site_labels.append({
            "event_id": site.event_id,
            "site_id": site.site_id,
            "label": site.label,
        })
    reports["policy_audit.json"] = {
        "compliance_counts": compliance_counts,
        "site_labels": site_labels,
        "tie_decisions": tie_decisions,
        "cap_binding_count": cap_binding_count,
        "residual_cents": residual_cents,
        "residual_tie_pool_count": residual_tie_pools,
    }

    ineligible = sum(
        1
        for key in ex.offer_site.values()
        if not ex.site_rows[key].can_dispatch
    )
    reports["data_quality.json"] = {
        "rows": ex.rows,
        "orphan_offer_rows": ex.orphan_offer_rows,
        "orphan_profile_rows": ex.orphan_profile_rows,
        "out_of_range_profile_rows": ex.out_of_range_profile_rows,
        "duplicate_profile_rows": ex.duplicate_profile_rows,
        "unknown_region_site_rows": ex.unknown_region_site_rows,
        "waiver_signed_missing": ex.waiver_signed_missing,
        "ineligible_offer_count": ineligible,
        "empty_candidate_groups": empty_candidate_groups,
        "zero_floor_count": zero_floor_count,
        "unallocated_pool_count": unallocated_pool_count,
    }
    return reports


def main(argv):
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    reports = build_reports(load_extract(data_dir))
    for name, payload in reports.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=1)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
