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

LABELS = ["SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR"]

REGION_TOTAL_KEYS = [
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
]

SEGMENT_TOTAL_KEYS = [
    "selected_offer_count",
    "relief_ticks",
    "recovery_ticks",
    "bid_cost_cents",
    "credit_cents",
    "floor_ticks",
]


def round_half_up(num, den):
    """Round the non-negative rational num/den to the nearest integer, halves up."""
    return (2 * num + den) // (2 * den)


def read_config(path):
    cp = configparser.ConfigParser()
    with open(path, encoding="utf-8") as fh:
        cp.read_file(fh)
    units = cp["units"]
    wh_per_tick = int(units["wh_per_tick"])
    millicents_per_cent = int(units["millicents_per_cent"])
    region_codes = {code.upper(): name for code, name in cp["region_codes"].items()}
    segment_codes = {code.upper(): name for code, name in cp["segment_codes"].items()}
    return wh_per_tick, millicents_per_cent, region_codes, segment_codes


def read_delimited(path, delimiter):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def fixed_fields(line, spans):
    return [line[a:b].strip() for a, b in spans]


def best_portfolio(site_list, by_site, offer_data, nint, target_t, weight_t, ceil_r, ceil_x,
                   group_floors, segment_names, cost_weight, recovery_weight):
    """Return (selected offer ids ascending, number of portfolios tied at the best value)."""
    relief_acc = [0] * nint
    recov_acc = [0] * nint
    chosen = []
    state = {"key": None, "tiebreak": None, "choice": None, "ties": 0}

    def visit():
        shortfall = 0
        over = 0
        for t in range(nint):
            diff = target_t[t] - relief_acc[t]
            if diff > 0:
                shortfall += weight_t[t] * diff
            else:
                over -= diff
        seg_relief = dict.fromkeys(segment_names, 0)
        bid_sum = 0
        for offer_id in chosen:
            od = offer_data[offer_id]
            bid_sum += od["bid"]
            if od["segment"] in seg_relief:
                seg_relief[od["segment"]] += od["relief_total"]
        floor_deficit = 0
        for segment in segment_names:
            floor_ticks, priority_weight = group_floors[segment]
            deficit = floor_ticks - seg_relief[segment]
            if deficit > 0:
                floor_deficit += priority_weight * deficit
        blended = cost_weight * bid_sum + recovery_weight * sum(recov_acc)
        key = (shortfall, floor_deficit, blended, over, len(chosen))
        if state["key"] is None or key < state["key"]:
            state["key"] = key
            state["tiebreak"] = tuple(sorted(chosen))
            state["choice"] = state["tiebreak"]
            state["ties"] = 1
        elif key == state["key"]:
            state["ties"] += 1
            tiebreak = tuple(sorted(chosen))
            if tiebreak > state["tiebreak"]:
                state["tiebreak"] = tiebreak
                state["choice"] = tiebreak

    def recurse(i):
        if i == len(site_list):
            visit()
            return
        recurse(i + 1)
        for offer_id in by_site[site_list[i]]:
            od = offer_data[offer_id]
            relief = od["relief"]
            recovery = od["recovery"]
            for t in range(nint):
                relief_acc[t] += relief[t]
                recov_acc[t] += recovery[t]
            feasible = True
            for t in range(nint):
                if (ceil_r[t] is not None and relief_acc[t] > ceil_r[t]) or (
                    ceil_x[t] is not None and recov_acc[t] > ceil_x[t]
                ):
                    feasible = False
                    break
            if feasible:
                chosen.append(offer_id)
                recurse(i + 1)
                chosen.pop()
            for t in range(nint):
                relief_acc[t] -= relief[t]
                recov_acc[t] -= recovery[t]

    recurse(0)
    return list(state["choice"]), state["ties"]


def apportion(funded, beneficiary_weights):
    """Largest remainder share-out. Returns (shares, residual_cents, has_residual_tie)."""
    positive = {ben: w for ben, w in beneficiary_weights.items() if w > 0}
    total_weight = sum(beneficiary_weights.values())
    shares = {}
    remainders = {}
    for ben, w in positive.items():
        shares[ben] = funded * w // total_weight
        remainders[ben] = (funded * w) % total_weight
    residual = funded - sum(shares.values())
    order = sorted(positive, key=lambda ben: (remainders[ben], ben), reverse=True)
    for ben in order[:residual]:
        shares[ben] += 1
    nonzero = [r for r in remainders.values() if r != 0]
    has_tie = len(nonzero) != len(set(nonzero))
    return shares, residual, has_tie


def main(argv):
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    def p(name):
        return os.path.join(data_dir, name)

    wh_per_tick, millicents_per_cent, region_codes, segment_codes = read_config(p("program.ini"))

    def ticks(wh):
        return round_half_up(int(wh), wh_per_tick)

    region_names = sorted(set(region_codes.values()))
    segment_names = sorted(set(segment_codes.values()))

    with open(p("events.json"), encoding="utf-8") as fh:
        events = json.load(fh)
    event_ids = sorted(e["event_id"] for e in events)
    event_info = {
        e["event_id"]: {
            "interval_count": int(e["interval_count"]),
            "cost_weight": int(e["objective"]["cost_weight"]),
            "recovery_weight": int(e["objective"]["recovery_weight"]),
            "uplift": int(e["uplift_millicents_per_kwh"]),
        }
        for e in events
    }

    # ---- site rows -------------------------------------------------------
    site_rows_raw = read_delimited(p("sites.csv"), ",")
    sites = {}
    unknown_region_site_rows = 0
    for r in site_rows_raw:
        region = region_codes.get(r["region_code"].strip().upper())
        if region is None:
            unknown_region_site_rows += 1
            continue
        sites[(r["event_id"], r["site_id"])] = {
            "region": region,
            "segment": segment_codes.get(r["segment_code"].strip().upper()),
            "beneficiary_id": r["beneficiary_id"],
            "critical": r["critical"].strip() == "Y",
        }

    # ---- site state ------------------------------------------------------
    state_by_site = {}
    state_lines = 0
    with open(p("site_state.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            state_lines += 1
            o = json.loads(line)
            key = (o["event_id"], o["site_id"])
            if key in sites:
                state_by_site[key] = o

    # ---- continuity waivers ---------------------------------------------
    waiver_rows = read_delimited(p("continuity_waivers.csv"), ",")
    waiver_signed_missing = 0
    waivers = {}
    for r in waiver_rows:
        signed = (r.get("waiver_signed") or "").strip()
        if signed == "":
            waiver_signed_missing += 1
        key = (r["event_id"], r["site_id"])
        if key in sites:
            waivers[key] = {
                "pending": r["routine_certificate_pending"].strip() == "Y",
                "status": r["waiver_status"].strip(),
                "signed": signed,
            }

    # ---- rate cards ------------------------------------------------------
    cards = ET.parse(p("rate_cards.xml")).getroot().findall("card")
    rate_cards = {}
    for c in cards:
        key = (c.get("event"), c.get("site"))
        if key in sites:
            rate_cards[key] = (int(c.find("base").text), int(c.find("cap").text))

    # ---- recipient weights ----------------------------------------------
    weight_rows = read_delimited(p("recipient_weights.tsv"), "\t")
    grant_weights = {}
    for r in weight_rows:
        key = (r["event_id"], r["site_id"])
        if key in sites:
            grant_weights[key] = int(r["grant_weight"])

    # ---- offers ----------------------------------------------------------
    offer_rows = read_delimited(p("offers.csv"), ",")
    offers = {}
    offer_events = {}
    orphan_offer_rows = 0
    ineligible_offer_count = 0
    for r in offer_rows:
        key = (r["event_id"], r["site_id"])
        offer_events[r["offer_id"]] = r["event_id"]
        if key not in sites:
            orphan_offer_rows += 1
            continue
        offers[r["offer_id"]] = {
            "event_id": r["event_id"],
            "site_id": r["site_id"],
            "bid": int(r["bid_cost_cents"]),
        }
        st = state_by_site.get(key)
        if st is None or st.get("dispatch_authorized") is not True:
            ineligible_offer_count += 1

    # ---- profiles --------------------------------------------------------
    orphan_profile_rows = 0
    out_of_range_profile_rows = 0
    duplicate_profile_rows = 0
    profile_rows = 0
    profiles = defaultdict(dict)
    with open(p("profiles.tsv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            profile_rows += 1
            offer_event = offer_events.get(r["offer_id"])
            if offer_event is None:
                orphan_profile_rows += 1
                continue
            interval = int(r["interval"])
            if not 1 <= interval <= event_info[offer_event]["interval_count"]:
                out_of_range_profile_rows += 1
                continue
            kept = profiles[r["offer_id"]]
            if interval in kept:
                duplicate_profile_rows += 1
                continue
            kept[interval] = (ticks(r["relief_wh"]), ticks(r["recovery_wh"]))

    # ---- targets ---------------------------------------------------------
    target_rows = read_delimited(p("targets.tsv"), "\t")
    targets = {}
    for r in target_rows:
        region = region_codes[r["region_code"].strip().upper()]
        targets[(r["event_id"], region, int(r["interval"]))] = (
            ticks(r["target_wh"]),
            int(r["shortfall_weight"]),
        )

    # ---- feeder limits ---------------------------------------------------
    ceilings = {}
    feeder_lines = 0
    with open(p("feeder_limits.txt"), encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#") or not line.strip():
                continue
            feeder_lines += 1
            event_id, code, interval, relief_ceil, recovery_ceil = fixed_fields(
                line, [(0, 10), (10, 14), (14, 17), (17, 27), (27, 37)]
            )
            region = region_codes[code.upper()]
            ceilings[(event_id, region, int(interval))] = (
                ticks(relief_ceil),
                ticks(recovery_ceil),
            )

    # ---- segment floors --------------------------------------------------
    with open(p("segment_floors.json"), encoding="utf-8") as fh:
        floor_entries = json.load(fh)["floors"]
    floors = {}
    for f in floor_entries:
        region = region_codes[f["region_code"].strip().upper()]
        segment = segment_codes[f["segment_code"].strip().upper()]
        floors[(f["event_id"], region, segment)] = (
            ticks(f["floor_wh"]),
            int(f["priority_weight"]),
        )

    # ---- pools -----------------------------------------------------------
    pools = {}
    pool_lines = 0
    with open(p("pools.txt"), encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#") or not line.strip():
                continue
            pool_lines += 1
            event_id, code, pool_cents = fixed_fields(line, [(0, 10), (10, 14), (14, 26)])
            pools[(event_id, region_codes[code.upper()])] = int(pool_cents)

    # ---- compliance labels ----------------------------------------------
    labels = {}
    for key, site in sites.items():
        st = state_by_site.get(key, {})
        waiver = waivers.get(key, {})
        pending = bool(waiver.get("pending"))
        waiver_valid = (
            waiver.get("status") == "VALID"
            and waiver.get("signed") == "Y"
            and site["critical"]
            and site["segment"] == "public"
        )
        if st.get("safety_hold") is True:
            labels[key] = "SAFETY_HOLD"
        elif st.get("cooldown") is True:
            labels[key] = "COOLDOWN"
        elif pending and waiver_valid:
            labels[key] = "CONTINUITY_WAIVED"
        elif pending:
            labels[key] = "CERTIFICATE_PENDING"
        else:
            labels[key] = "CLEAR"

    # ---- grouping --------------------------------------------------------
    candidates = defaultdict(list)
    for offer_id, offer in offers.items():
        key = (offer["event_id"], offer["site_id"])
        st = state_by_site.get(key)
        if st is None or st.get("dispatch_authorized") is not True:
            continue
        candidates[(offer["event_id"], sites[key]["region"])].append(offer_id)

    site_rows_by_group = defaultdict(list)
    for key, site in sites.items():
        site_rows_by_group[(key[0], site["region"])].append(key)

    # ---- per event-region computation ------------------------------------
    results = {}
    empty_candidate_groups = 0
    zero_floor_count = 0
    unallocated_pool_count = 0
    residual_cents_total = 0
    residual_tie_pool_count = 0
    cap_binding_count = 0
    tie_decisions = []

    for event_id in event_ids:
        info = event_info[event_id]
        nint = info["interval_count"]
        uplift = info["uplift"]
        for region in region_names:
            group = (event_id, region)
            cand_ids = sorted(candidates.get(group, []))
            if not cand_ids:
                empty_candidate_groups += 1

            target_t = []
            weight_t = []
            ceil_r = []
            ceil_x = []
            for t in range(1, nint + 1):
                target_ticks, shortfall_weight = targets.get((event_id, region, t), (0, 0))
                target_t.append(target_ticks)
                weight_t.append(shortfall_weight)
                ceiling = ceilings.get((event_id, region, t))
                ceil_r.append(None if ceiling is None else ceiling[0])
                ceil_x.append(None if ceiling is None else ceiling[1])

            group_floors = {}
            for segment in segment_names:
                floor_ticks, priority_weight = floors.get((event_id, region, segment), (0, 0))
                group_floors[segment] = (floor_ticks, priority_weight)
                if floor_ticks == 0:
                    zero_floor_count += 1

            by_site = defaultdict(list)
            offer_data = {}
            for offer_id in cand_ids:
                offer = offers[offer_id]
                by_site[offer["site_id"]].append(offer_id)
                kept = profiles.get(offer_id, {})
                relief = [kept.get(t, (0, 0))[0] for t in range(1, nint + 1)]
                recovery = [kept.get(t, (0, 0))[1] for t in range(1, nint + 1)]
                offer_data[offer_id] = {
                    "relief": relief,
                    "recovery": recovery,
                    "relief_total": sum(relief),
                    "recovery_total": sum(recovery),
                    "bid": offer["bid"],
                    "segment": sites[(event_id, offer["site_id"])]["segment"],
                }
            site_list = sorted(by_site)

            selected, tie_count = best_portfolio(
                site_list,
                by_site,
                offer_data,
                nint,
                target_t,
                weight_t,
                ceil_r,
                ceil_x,
                group_floors,
                segment_names,
                info["cost_weight"],
                info["recovery_weight"],
            )
            if tie_count >= 2:
                tie_decisions.append(
                    {
                        "event_id": event_id,
                        "region": region,
                        "tied_portfolio_count": tie_count,
                        "selected_offer_ids": selected,
                    }
                )

            relief_t = [0] * nint
            recovery_t = [0] * nint
            bid_cost = 0
            credit_total = 0
            credits = {}
            for offer_id in selected:
                od = offer_data[offer_id]
                for t in range(nint):
                    relief_t[t] += od["relief"][t]
                    recovery_t[t] += od["recovery"][t]
                bid_cost += od["bid"]
                base, cap = rate_cards.get((event_id, offers[offer_id]["site_id"]), (0, 0))
                raw_rate = base + uplift
                if raw_rate > cap:
                    cap_binding_count += 1
                    rate = cap
                else:
                    rate = raw_rate
                relief_wh = od["relief_total"] * wh_per_tick
                credit = round_half_up(relief_wh * rate, 1000 * millicents_per_cent)
                credits[offer_id] = credit
                credit_total += credit

            shortfall_t = [max(0, target_t[t] - relief_t[t]) for t in range(nint)]
            over_t = [max(0, relief_t[t] - target_t[t]) for t in range(nint)]

            # ---- grants ----
            pool_cents = pools.get(group, 0)
            funded = max(0, pool_cents - credit_total)
            beneficiary_weights = defaultdict(int)
            recipient_count = 0
            for site_key in site_rows_by_group.get(group, []):
                if site_key not in grant_weights:
                    continue
                recipient_count += 1
                w = grant_weights[site_key]
                if labels[site_key] == "CONTINUITY_WAIVED":
                    w *= 2
                beneficiary_weights[sites[site_key]["beneficiary_id"]] += w
            grants = []
            allocated = 0
            residual = 0
            if recipient_count == 0 or sum(beneficiary_weights.values()) == 0:
                unallocated_pool_count += 1
            else:
                shares, residual, has_tie = apportion(funded, beneficiary_weights)
                allocated = sum(shares.values())
                grants = [{"beneficiary_id": b, "cents": shares[b]} for b in sorted(shares)]
                if has_tie:
                    residual_tie_pool_count += 1
            residual_cents_total += residual

            counts = dict.fromkeys(LABELS, 0)
            for site_key in site_rows_by_group.get(group, []):
                counts[labels[site_key]] += 1

            seg_data = {}
            for segment in segment_names:
                seg_offers = [o for o in selected if offer_data[o]["segment"] == segment]
                seg_relief = sum(offer_data[o]["relief_total"] for o in seg_offers)
                floor_ticks = group_floors[segment][0]
                seg_data[segment] = {
                    "selected_offer_ids": seg_offers,
                    "relief_ticks": seg_relief,
                    "recovery_ticks": sum(offer_data[o]["recovery_total"] for o in seg_offers),
                    "bid_cost_cents": sum(offer_data[o]["bid"] for o in seg_offers),
                    "credit_cents": sum(credits[o] for o in seg_offers),
                    "floor_ticks": floor_ticks,
                    "floor_attainment_bp": 10000
                    if floor_ticks == 0
                    else min(10000, round_half_up(10000 * seg_relief, floor_ticks)),
                }

            results[group] = {
                "candidate_offer_count": len(cand_ids),
                "selected_offer_ids": selected,
                "target_t": target_t,
                "relief_t": relief_t,
                "recovery_t": recovery_t,
                "shortfall_t": shortfall_t,
                "over_t": over_t,
                "bid_cost_cents": bid_cost,
                "credit_cents": credit_total,
                "grant_pool_cents": pool_cents,
                "grant_funded_cents": funded,
                "grant_allocated_cents": allocated,
                "grant_unallocated_cents": funded - allocated,
                "grants": grants,
                "compliance_counts": counts,
                "segments": seg_data,
            }

    def dump(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, sort_keys=True, indent=1)
            fh.write("\n")

    # ---- region files ----------------------------------------------------
    region_totals = {}
    for region in region_names:
        events_out = []
        totals = dict.fromkeys(REGION_TOTAL_KEYS, 0)
        for event_id in event_ids:
            res = results[(event_id, region)]
            nint = event_info[event_id]["interval_count"]
            events_out.append(
                {
                    "event_id": event_id,
                    "candidate_offer_count": res["candidate_offer_count"],
                    "selected_offer_ids": res["selected_offer_ids"],
                    "intervals": [
                        {
                            "interval": t + 1,
                            "target_ticks": res["target_t"][t],
                            "relief_ticks": res["relief_t"][t],
                            "recovery_ticks": res["recovery_t"][t],
                            "shortfall_ticks": res["shortfall_t"][t],
                            "overdelivery_ticks": res["over_t"][t],
                        }
                        for t in range(nint)
                    ],
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
            totals["event_count"] += 1
            totals["candidate_offer_count"] += res["candidate_offer_count"]
            totals["selected_offer_count"] += len(res["selected_offer_ids"])
            totals["relief_ticks"] += sum(res["relief_t"])
            totals["recovery_ticks"] += sum(res["recovery_t"])
            totals["shortfall_ticks"] += sum(res["shortfall_t"])
            totals["overdelivery_ticks"] += sum(res["over_t"])
            for key in (
                "bid_cost_cents",
                "credit_cents",
                "grant_pool_cents",
                "grant_funded_cents",
                "grant_allocated_cents",
                "grant_unallocated_cents",
            ):
                totals[key] += res[key]
        region_totals[region] = totals
        dump("region_%s.json" % region, {"region": region, "events": events_out, "totals": totals})

    # ---- segment files ---------------------------------------------------
    segment_totals = {}
    for segment in segment_names:
        entries = []
        totals = dict.fromkeys(SEGMENT_TOTAL_KEYS, 0)
        for event_id in event_ids:
            for region in region_names:
                sd = results[(event_id, region)]["segments"][segment]
                entry = {"event_id": event_id, "region": region}
                entry.update(sd)
                entries.append(entry)
                totals["selected_offer_count"] += len(sd["selected_offer_ids"])
                for key in SEGMENT_TOTAL_KEYS[1:]:
                    totals[key] += sd[key]
        segment_totals[segment] = totals
        dump(
            "segment_%s.json" % segment,
            {"segment": segment, "event_regions": entries, "totals": totals},
        )

    # ---- summary ---------------------------------------------------------
    summary = {
        "event_count": len(event_ids),
        "event_region_count": len(event_ids) * len(region_names),
        "site_count": len(sites),
    }
    for key in REGION_TOTAL_KEYS:
        if key == "event_count":
            continue
        summary[key] = sum(region_totals[r][key] for r in region_names)
    summary["regions"] = {
        region: {
            key: region_totals[region][key]
            for key in (
                "selected_offer_count",
                "relief_ticks",
                "bid_cost_cents",
                "credit_cents",
                "grant_allocated_cents",
            )
        }
        for region in region_names
    }
    summary["segments"] = {
        segment: {
            key: segment_totals[segment][key]
            for key in ("selected_offer_count", "relief_ticks", "bid_cost_cents", "credit_cents")
        }
        for segment in segment_names
    }
    dump("summary.json", summary)

    # ---- policy audit ----------------------------------------------------
    compliance_counts = dict.fromkeys(LABELS, 0)
    for label in labels.values():
        compliance_counts[label] += 1
    dump(
        "policy_audit.json",
        {
            "compliance_counts": compliance_counts,
            "site_labels": [
                {"event_id": key[0], "site_id": key[1], "label": labels[key]}
                for key in sorted(labels)
            ],
            "tie_decisions": tie_decisions,
            "cap_binding_count": cap_binding_count,
            "residual_cents": residual_cents_total,
            "residual_tie_pool_count": residual_tie_pool_count,
        },
    )

    # ---- data quality ----------------------------------------------------
    dump(
        "data_quality.json",
        {
            "rows": {
                "events.json": len(events),
                "sites.csv": len(site_rows_raw),
                "offers.csv": len(offer_rows),
                "profiles.tsv": profile_rows,
                "targets.tsv": len(target_rows),
                "continuity_waivers.csv": len(waiver_rows),
                "recipient_weights.tsv": len(weight_rows),
                "feeder_limits.txt": feeder_lines,
                "pools.txt": pool_lines,
                "site_state.jsonl": state_lines,
                "segment_floors.json": len(floor_entries),
                "rate_cards.xml": len(cards),
            },
            "orphan_offer_rows": orphan_offer_rows,
            "orphan_profile_rows": orphan_profile_rows,
            "out_of_range_profile_rows": out_of_range_profile_rows,
            "duplicate_profile_rows": duplicate_profile_rows,
            "unknown_region_site_rows": unknown_region_site_rows,
            "waiver_signed_missing": waiver_signed_missing,
            "ineligible_offer_count": ineligible_offer_count,
            "empty_candidate_groups": empty_candidate_groups,
            "zero_floor_count": zero_floor_count,
            "unallocated_pool_count": unallocated_pool_count,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
