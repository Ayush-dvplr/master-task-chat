#!/usr/bin/env python3
"""District heat flexibility programme report derivation (see schema.md)."""
import configparser
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

LABELS = ["SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR"]


def half_up_div(num, den):
    return (2 * num + den) // (2 * den)


def half_even_div(num, den):
    q, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and q % 2 == 1):
        q += 1
    return q


def read_lines(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read().splitlines()


def read_csv(path, delim):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter=delim))
    rows = [r for r in rows if r]
    header = [h.strip() for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:]]


def read_commented_tsv(path):
    lines = [l for l in read_lines(path) if not l.startswith("#") and l.strip() != ""]
    header = [h.strip() for h in lines[0].split("\t")]
    out = []
    for l in lines[1:]:
        parts = l.split("\t")
        parts += [""] * (len(header) - len(parts))
        out.append(dict(zip(header, parts)))
    return out


def fixed_lines(path):
    return [l for l in read_lines(path) if not l.startswith("#") and l.strip() != ""]


def lr_share(F, items):
    """items: list of (bid, weight>0). Returns (shares dict, residual, tie)."""
    W = sum(w for _, w in items)
    shares = {}
    rems = []
    total = 0
    for bid, w in items:
        shares[bid] = F * w // W
        total += shares[bid]
        rems.append((bid, (F * w) % W))
    left = F - total
    order = sorted(rems, key=lambda x: x[0], reverse=True)
    order.sort(key=lambda x: x[1], reverse=True)
    for i in range(left):
        shares[order[i][0]] += 1
    cnt = defaultdict(int)
    for _, r in rems:
        if r:
            cnt[r] += 1
    tie = any(c >= 2 for c in cnt.values())
    return shares, left, tie


def main():
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    P = lambda name: os.path.join(data_dir, name)
    os.makedirs(out_dir, exist_ok=True)

    cp = configparser.ConfigParser(interpolation=None)
    cp.read(P("program.ini"), encoding="utf-8")
    wpt = int(cp.get("units", "wh_per_tick"))
    mpc = int(cp.get("units", "millicents_per_cent"))
    region_of = {k.lower(): v.strip() for k, v in cp.items("region_codes", raw=True)} if cp.has_section("region_codes") else {}
    seg_of = {k.lower(): v.strip() for k, v in cp.items("segment_codes", raw=True)} if cp.has_section("segment_codes") else {}
    if cp.has_section("region_codes"):
        region_of = {k.lower(): cp.get("region_codes", k).strip() for k in cp.options("region_codes")}
    if cp.has_section("segment_codes"):
        seg_of = {k.lower(): cp.get("segment_codes", k).strip() for k in cp.options("segment_codes")}
    regions = sorted(set(region_of.values()))
    segments = sorted(set(seg_of.values()))

    def adder(seg):
        if seg is None or not cp.has_section("segment_rate_adders"):
            return 0
        if cp.has_option("segment_rate_adders", seg):
            return int(cp.get("segment_rate_adders", seg))
        return 0

    claim_cpw = int(cp.get("grants", "claim_cents_per_weight"))
    min_grant = int(cp.get("grants", "minimum_grant_cents"))

    def reg(code):
        return region_of.get(code.strip().lower())

    def segn(code):
        return seg_of.get(code.strip().lower())

    def ticks(wh):
        return half_up_div(wh, wpt)

    rows_count = {}

    # events
    with open(P("events.json"), encoding="utf-8") as f:
        events_raw = json.load(f)
    rows_count["events.json"] = len(events_raw)
    events = {}
    for e in events_raw:
        events[e["event_id"]] = {
            "n": int(e["interval_count"]),
            "cw": int(e["objective"]["cost_weight"]),
            "rw": int(e["objective"]["recovery_weight"]),
            "start": datetime.fromisoformat(e["dispatch_start"]),
            "uplift": int(e["uplift_millicents_per_kwh"]),
        }
    event_ids = sorted(events)
    season = sorted(event_ids, reverse=True)
    season.sort(key=lambda eid: events[eid]["start"])

    # sites
    sites_rows = read_csv(P("sites.csv"), ",")
    rows_count["sites.csv"] = len(sites_rows)
    site_rows = {}
    unknown_keys = set()
    unknown_region = 0
    for r in sites_rows:
        key = (r["event_id"], r["site_id"])
        rg = reg(r["region_code"])
        if rg is None:
            unknown_region += 1
            unknown_keys.add(key)
            continue
        site_rows[key] = {
            "region": rg,
            "segment": segn(r["segment_code"]),
            "ben": r["beneficiary_id"],
            "critical": r["critical"].strip() == "Y",
        }

    # site state
    state_lines = [l for l in read_lines(P("site_state.jsonl")) if l.strip()]
    rows_count["site_state.jsonl"] = len(state_lines)
    state = {}
    for l in state_lines:
        j = json.loads(l)
        key = (j["event_id"], j["site_id"])
        if key in site_rows:
            state[key] = j

    # waivers
    waivers_rows = read_csv(P("continuity_waivers.csv"), ",")
    rows_count["continuity_waivers.csv"] = len(waivers_rows)
    waiver_signed_missing = 0
    waivers = {}
    for r in waivers_rows:
        if (r.get("waiver_signed") or "").strip() == "":
            waiver_signed_missing += 1
        key = (r["event_id"], r["site_id"])
        if key in site_rows:
            waivers[key] = r

    # labels
    labels = {}
    for key, s in site_rows.items():
        st = state.get(key, {})
        w = waivers.get(key, {})
        pending = (w.get("routine_certificate_pending") or "").strip() == "Y"
        valid = ((w.get("waiver_status") or "").strip() == "VALID"
                 and (w.get("waiver_signed") or "").strip() == "Y"
                 and s["critical"] and s["segment"] == "public")
        if st.get("safety_hold") is True:
            lab = "SAFETY_HOLD"
        elif st.get("cooldown") is True:
            lab = "COOLDOWN"
        elif pending and valid:
            lab = "CONTINUITY_WAIVED"
        elif pending:
            lab = "CERTIFICATE_PENDING"
        else:
            lab = "CLEAR"
        labels[key] = lab

    # rate cards
    root = ET.parse(P("rate_cards.xml")).getroot()
    cards_all = list(root.iter("card"))
    rows_count["rate_cards.xml"] = len(cards_all)
    rate = {}
    for c in cards_all:
        key = (c.get("event"), c.get("site"))
        if key not in site_rows:
            continue
        base = int(c.find("base").text.strip())
        ov = c.find("override")
        cap = int(c.find("cap").text.strip())
        r0 = int(ov.text.strip()) if ov is not None and ov.text and ov.text.strip() else base
        r0 += adder(site_rows[key]["segment"]) + events[key[0]]["uplift"]
        rate[key] = (min(r0, cap), r0 > cap)

    # recipient weights
    rw_rows = read_csv(P("recipient_weights.tsv"), "\t")
    rows_count["recipient_weights.tsv"] = len(rw_rows)
    weights = {}
    for r in rw_rows:
        key = (r["event_id"], r["site_id"])
        if key in site_rows:
            weights[key] = int(r["grant_weight"])

    # offers
    offers_rows = read_csv(P("offers.csv"), ",")
    rows_count["offers.csv"] = len(offers_rows)
    offer_event = {}
    offers = {}
    orphan_offers = 0
    for r in offers_rows:
        oid = r["offer_id"]
        offer_event.setdefault(oid, r["event_id"])
        key = (r["event_id"], r["site_id"])
        if key not in site_rows:
            orphan_offers += 1
            continue
        offers[oid] = {"key": key, "bid": int(r["bid_cost_cents"])}

    # profiles
    prof_rows = read_csv(P("profiles.tsv"), "\t")
    rows_count["profiles.tsv"] = len(prof_rows)
    orphan_prof = oor_prof = dup_prof = 0
    kept = set()
    prof = {}
    for r in prof_rows:
        oid = r["offer_id"]
        if oid not in offer_event:
            orphan_prof += 1
            continue
        t = int(r["interval"])
        n = events[offer_event[oid]]["n"]
        if t < 1 or t > n:
            oor_prof += 1
            continue
        if (oid, t) in kept:
            dup_prof += 1
            continue
        kept.add((oid, t))
        m = int(r["register_multiplier"])
        if oid in offers:
            d = prof.setdefault(oid, {})
            d[t] = (ticks(int(r["relief_wh"]) * m), ticks(int(r["recovery_wh"]) * m))
    for oid, o in offers.items():
        n = events[o["key"][0]]["n"]
        d = prof.get(oid, {})
        o["rel"] = [d.get(t, (0, 0))[0] for t in range(1, n + 1)]
        o["rec"] = [d.get(t, (0, 0))[1] for t in range(1, n + 1)]
        o["rel_total"] = sum(o["rel"])
        o["rec_total"] = sum(o["rec"])

    # targets
    tg_rows = read_csv(P("targets.tsv"), "\t")
    rows_count["targets.tsv"] = len(tg_rows)
    targets = {}
    for r in tg_rows:
        targets[(r["event_id"], reg(r["region_code"]), int(r["interval"]))] = (
            ticks(int(r["target_wh"])), int(r["shortfall_weight"]))

    # feeder limits
    fl = fixed_lines(P("feeder_limits.txt"))
    rows_count["feeder_limits.txt"] = len(fl)
    ceilings = {}
    for l in fl:
        l = l.ljust(37)
        ceilings[(l[0:10].strip(), reg(l[10:14].strip()), int(l[14:17]))] = (
            ticks(int(l[17:27])), ticks(int(l[27:37])))

    # floors
    with open(P("segment_floors.json"), encoding="utf-8") as f:
        floors_raw = json.load(f)["floors"]
    rows_count["segment_floors.json"] = len(floors_raw)
    floors = {}
    for r in floors_raw:
        floors[(r["event_id"], reg(r["region_code"]), segn(r["segment_code"]))] = (
            ticks(int(r["floor_wh"])), int(r["priority_weight"]))

    # pools
    pl = fixed_lines(P("pools.txt"))
    rows_count["pools.txt"] = len(pl)
    pools = {}
    for l in pl:
        l = l.ljust(26)
        pools[(l[0:10].strip(), reg(l[10:14].strip()))] = int(l[14:26])

    # allowances
    al_rows = read_commented_tsv(P("site_allowances.tsv"))
    rows_count["site_allowances.tsv"] = len(al_rows)
    allow = {}
    draws = {}
    for r in al_rows:
        sid = r["site_id"].strip()
        a = (r.get("allowance_ticks") or "").strip()
        allow[sid] = int(a) if a else 0
        draws[sid] = (r.get("draws_from") or "").strip()

    def root_of(sid):
        seen = set()
        cur = sid
        while draws.get(cur) and cur not in seen:
            seen.add(cur)
            cur = draws[cur]
        return cur

    # manifest
    mf = read_commented_tsv(P("export_manifest.tsv"))
    rows_count["export_manifest.tsv"] = len(mf)

    # group offers by event-region
    er_offers = defaultdict(list)
    ineligible = 0
    for oid, o in offers.items():
        key = o["key"]
        if state.get(key, {}).get("dispatch_authorized") is True:
            er_offers[(key[0], site_rows[key]["region"])].append(oid)
        else:
            ineligible += 1
    er_sites = defaultdict(list)
    for key, s in site_rows.items():
        er_sites[(key[0], s["region"])].append(key)

    used = defaultdict(int)  # allowance root -> relief ticks drawn
    allowance_blocked = 0
    results = {}
    carry = defaultdict(int)
    residual_total = 0
    residual_tie_pools = 0
    unalloc_pool_count = 0
    cap_binding = 0
    tie_decisions = []

    for eid in season:
        ev = events[eid]
        n = ev["n"]
        remaining_at_reach = {}
        draws_this_event = defaultdict(int)
        for rg in regions:
            er = (eid, rg)
            cands = []
            for oid in er_offers.get(er, []):
                sid = offers[oid]["key"][1]
                if sid in allow:
                    rt = root_of(sid)
                    rem = allow.get(rt, 0) - used[rt]
                    if offers[oid]["rel_total"] > rem:
                        allowance_blocked += 1
                        continue
                cands.append(oid)
            tgt = [targets.get((eid, rg, t), (0, 0)) for t in range(1, n + 1)]
            ceil = [ceilings.get((eid, rg, t), (0, 0)) for t in range(1, n + 1)]
            seg_floor = {sg: floors.get((eid, rg, sg), (0, 0)) for sg in segments}
            by_site = defaultdict(list)
            for oid in cands:
                by_site[offers[oid]["key"][1]].append(oid)
            site_list = sorted(by_site)
            for sid in site_list:
                by_site[sid].sort()

            best = [None, None, 0]  # key, ids tuple, count

            rel = [0] * n
            rec = [0] * n
            segrel = defaultdict(int)
            chosen = []
            state_acc = {"bid": 0}

            def evaluate():
                c1 = 0
                c4 = 0
                for t in range(n):
                    tt, sw = tgt[t]
                    if tt > rel[t]:
                        c1 += sw * (tt - rel[t])
                    else:
                        c4 += rel[t] - tt
                c2 = 0
                for sg in segments:
                    ft, pw = seg_floor[sg]
                    if ft > segrel[sg]:
                        c2 += pw * (ft - segrel[sg])
                c3 = ev["cw"] * state_acc["bid"] + ev["rw"] * sum(rec)
                k = (c1, c2, c3, c4, len(chosen))
                ids = tuple(sorted(chosen))
                if best[0] is None or k < best[0]:
                    best[0], best[1], best[2] = k, ids, 1
                elif k == best[0]:
                    best[2] += 1
                    if ids > best[1]:
                        best[1] = ids

            def dfs(i):
                if i == len(site_list):
                    evaluate()
                    return
                dfs(i + 1)
                for oid in by_site[site_list[i]]:
                    o = offers[oid]
                    ok = True
                    for t in range(n):
                        if rel[t] + o["rel"][t] > ceil[t][0] or rec[t] + o["rec"][t] > ceil[t][1]:
                            ok = False
                            break
                    if not ok:
                        continue
                    for t in range(n):
                        rel[t] += o["rel"][t]
                        rec[t] += o["rec"][t]
                    sg = site_rows[o["key"]]["segment"]
                    segrel[sg] += o["rel_total"]
                    state_acc["bid"] += o["bid"]
                    chosen.append(oid)
                    dfs(i + 1)
                    chosen.pop()
                    state_acc["bid"] -= o["bid"]
                    segrel[sg] -= o["rel_total"]
                    for t in range(n):
                        rel[t] -= o["rel"][t]
                        rec[t] -= o["rec"][t]

            dfs(0)
            sel = list(best[1])
            if best[2] >= 2:
                tie_decisions.append({"event_id": eid, "region": rg,
                                      "tied_portfolio_count": best[2],
                                      "selected_offer_ids": sel})

            # interval figures
            relt = [0] * n
            rect = [0] * n
            for oid in sel:
                for t in range(n):
                    relt[t] += offers[oid]["rel"][t]
                    rect[t] += offers[oid]["rec"][t]
            intervals = []
            for t in range(n):
                tt = tgt[t][0]
                intervals.append({"interval": t + 1, "target_ticks": tt, "relief_ticks": relt[t],
                                  "recovery_ticks": rect[t],
                                  "shortfall_ticks": max(0, tt - relt[t]),
                                  "overdelivery_ticks": max(0, relt[t] - tt)})

            # credits
            credit = {}
            for oid in sel:
                o = offers[oid]
                r_eff, binding = rate.get(o["key"], (0, False))
                if binding:
                    cap_binding += 1
                c = 0
                for t in range(n):
                    cr = max(0, o["rel"][t] - o["rec"][t])
                    c += half_even_div(cr * wpt * r_eff, 1000 * mpc)
                credit[oid] = c
                draws_this_event[root_of(o["key"][1]) if o["key"][1] in allow else None] += o["rel_total"]
            credit_sum = sum(credit.values())
            bid_sum = sum(offers[oid]["bid"] for oid in sel)

            # grants
            pool = pools.get(er, 0)
            F = max(0, pool + carry[rg] - credit_sum)
            ben_w = defaultdict(int)
            has_recip = False
            for key in er_sites.get(er, []):
                if key in weights:
                    has_recip = True
                    w = weights[key] * (2 if labels[key] == "CONTINUITY_WAIVED" else 1)
                    ben_w[site_rows[key]["ben"]] += w
            W = sum(ben_w.values())
            pos = sorted((b, w) for b, w in ben_w.items() if w > 0)
            grants = {}
            residual = 0
            tie = False
            if not has_recip or W == 0:
                unalloc_pool_count += 1
            else:
                claims = sum(w * claim_cpw for _, w in pos)
                if claims <= F:
                    grants = {b: w * claim_cpw for b, w in pos}
                else:
                    shares, left, tie1 = lr_share(F, pos)
                    qual = [(b, w) for b, w in pos if shares[b] >= min_grant]
                    if len(qual) == len(pos):
                        grants = shares
                        residual, tie = left, tie1
                    elif not qual:
                        grants = {b: 0 for b, _ in pos}
                    else:
                        shares2, left2, tie2 = lr_share(F, qual)
                        grants = {b: shares2.get(b, 0) for b, _ in pos}
                        residual, tie = left2, tie2
            allocated = sum(grants.values())
            unallocated = F - allocated
            carry[rg] = unallocated
            residual_total += residual
            if tie:
                residual_tie_pools += 1

            cc = {lab: 0 for lab in LABELS}
            for key in er_sites.get(er, []):
                cc[labels[key]] += 1

            results[er] = {
                "event_id": eid,
                "candidate_offer_count": len(cands),
                "selected_offer_ids": sel,
                "intervals": intervals,
                "bid_cost_cents": bid_sum,
                "credit_cents": credit_sum,
                "grant_pool_cents": pool,
                "grant_funded_cents": F,
                "grant_allocated_cents": allocated,
                "grant_unallocated_cents": unallocated,
                "grants": [{"beneficiary_id": b, "cents": grants.get(b, 0)} for b, _ in pos],
                "compliance_counts": cc,
                "_credit": credit,
                "_floors": seg_floor,
            }
        for rt, v in draws_this_event.items():
            if rt is not None:
                used[rt] += v

    def write(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, sort_keys=True, indent=1)
            f.write("\n")

    def public(er):
        return {k: v for k, v in results[er].items() if not k.startswith("_")}

    tot_keys = ["candidate_offer_count", "selected_offer_count", "relief_ticks", "recovery_ticks",
                "shortfall_ticks", "overdelivery_ticks", "bid_cost_cents", "credit_cents",
                "grant_pool_cents", "grant_funded_cents", "grant_allocated_cents",
                "grant_unallocated_cents"]

    def er_totals(e):
        return {
            "candidate_offer_count": e["candidate_offer_count"],
            "selected_offer_count": len(e["selected_offer_ids"]),
            "relief_ticks": sum(i["relief_ticks"] for i in e["intervals"]),
            "recovery_ticks": sum(i["recovery_ticks"] for i in e["intervals"]),
            "shortfall_ticks": sum(i["shortfall_ticks"] for i in e["intervals"]),
            "overdelivery_ticks": sum(i["overdelivery_ticks"] for i in e["intervals"]),
            "bid_cost_cents": e["bid_cost_cents"],
            "credit_cents": e["credit_cents"],
            "grant_pool_cents": e["grant_pool_cents"],
            "grant_funded_cents": e["grant_funded_cents"],
            "grant_allocated_cents": e["grant_allocated_cents"],
            "grant_unallocated_cents": e["grant_unallocated_cents"],
        }

    summary = {k: 0 for k in tot_keys}
    summary_regions = {}
    for rg in regions:
        evs = [public((eid, rg)) for eid in event_ids]
        totals = {k: 0 for k in tot_keys}
        for e in evs:
            for k, v in er_totals(e).items():
                totals[k] += v
        totals["event_count"] = len(evs)
        for k in tot_keys:
            summary[k] += totals[k]
        summary_regions[rg] = {k: totals[k] for k in ["selected_offer_count", "relief_ticks",
                                                       "bid_cost_cents", "credit_cents",
                                                       "grant_allocated_cents"]}
        write("region_%s.json" % rg, {"region": rg, "events": evs, "totals": totals})

    summary_segments = {}
    zero_floor = 0
    for sg in segments:
        ers = []
        tot = {k: 0 for k in ["selected_offer_count", "relief_ticks", "recovery_ticks",
                              "bid_cost_cents", "credit_cents", "floor_ticks"]}
        for eid in event_ids:
            for rg in regions:
                res = results[(eid, rg)]
                ids = [oid for oid in res["selected_offer_ids"]
                       if site_rows[offers[oid]["key"]]["segment"] == sg]
                relv = sum(offers[oid]["rel_total"] for oid in ids)
                recv = sum(offers[oid]["rec_total"] for oid in ids)
                bid = sum(offers[oid]["bid"] for oid in ids)
                cr = sum(res["_credit"][oid] for oid in ids)
                ft = res["_floors"][sg][0]
                if ft == 0:
                    zero_floor += 1
                    bp = 10000
                else:
                    bp = min(10000, half_up_div(10000 * relv, ft))
                ers.append({"event_id": eid, "region": rg, "selected_offer_ids": ids,
                            "relief_ticks": relv, "recovery_ticks": recv, "bid_cost_cents": bid,
                            "credit_cents": cr, "floor_ticks": ft, "floor_attainment_bp": bp})
                tot["selected_offer_count"] += len(ids)
                tot["relief_ticks"] += relv
                tot["recovery_ticks"] += recv
                tot["bid_cost_cents"] += bid
                tot["credit_cents"] += cr
                tot["floor_ticks"] += ft
        summary_segments[sg] = {k: tot[k] for k in ["selected_offer_count", "relief_ticks",
                                                    "bid_cost_cents", "credit_cents"]}
        write("segment_%s.json" % sg, {"segment": sg, "event_regions": ers, "totals": tot})

    summary.update({
        "event_count": len(event_ids),
        "event_region_count": len(event_ids) * len(regions),
        "site_count": len(site_rows),
        "regions": summary_regions,
        "segments": summary_segments,
    })
    write("summary.json", summary)

    cc_all = {lab: 0 for lab in LABELS}
    for lab in labels.values():
        cc_all[lab] += 1
    write("policy_audit.json", {
        "compliance_counts": cc_all,
        "site_labels": [{"event_id": k[0], "site_id": k[1], "label": labels[k]}
                        for k in sorted(labels)],
        "tie_decisions": sorted(tie_decisions, key=lambda d: (d["event_id"], d["region"])),
        "cap_binding_count": cap_binding,
        "residual_cents": residual_total,
        "residual_tie_pool_count": residual_tie_pools,
    })

    empty_groups = sum(1 for er, r in results.items() if r["candidate_offer_count"] == 0)
    write("data_quality.json", {
        "rows": rows_count,
        "orphan_offer_rows": orphan_offers,
        "orphan_profile_rows": orphan_prof,
        "out_of_range_profile_rows": oor_prof,
        "duplicate_profile_rows": dup_prof,
        "unknown_region_site_rows": unknown_region,
        "waiver_signed_missing": waiver_signed_missing,
        "ineligible_offer_count": ineligible,
        "allowance_blocked_offer_count": allowance_blocked,
        "empty_candidate_groups": empty_groups,
        "zero_floor_count": zero_floor,
        "unallocated_pool_count": unalloc_pool_count,
    })


if __name__ == "__main__":
    main()
