#!/usr/bin/env python3
"""District heat flexibility programme: derive season reports from one extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""
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
    """num/den rounded half up, for non-negative integers."""
    return (2 * num + den) // (2 * den)


def half_even_div(num, den):
    q, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and q % 2 == 1):
        q += 1
    return q


def read_delimited(path, delim):
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh, delimiter=delim))
    rows = [r for r in rows if r]
    header = rows[0]
    out = []
    for r in rows[1:]:
        d = {}
        for i, h in enumerate(header):
            d[h] = r[i] if i < len(r) else ""
        out.append(d)
    return out


def read_commented_tsv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        lines = [l.rstrip("\r\n") for l in fh]
    lines = [l for l in lines if not l.startswith("#") and l.strip() != ""]
    header = lines[0].split("\t")
    out = []
    for l in lines[1:]:
        parts = l.split("\t")
        out.append({h: (parts[i] if i < len(parts) else "") for i, h in enumerate(header)})
    return out


def read_fixed(path):
    with open(path, encoding="utf-8", newline="") as fh:
        lines = [l.rstrip("\r\n") for l in fh]
    return [l for l in lines if not l.startswith("#") and l.strip() != ""]


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, sort_keys=True, indent=2)
        fh.write("\n")


def main():
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    P = lambda name: os.path.join(data_dir, name)

    # ---------------- program.ini ----------------
    cp = configparser.ConfigParser()
    cp.read(P("program.ini"), encoding="utf-8")
    wpt = int(cp["units"]["wh_per_tick"])
    mcpc = int(cp["units"]["millicents_per_cent"])
    region_codes = {k.lower(): v for k, v in cp["region_codes"].items()}
    segment_codes = {k.lower(): v for k, v in cp["segment_codes"].items()}
    seg_adders = {}
    if cp.has_section("segment_rate_adders"):
        seg_adders = {k.lower(): int(v) for k, v in cp["segment_rate_adders"].items()}
    region_names = sorted(set(region_codes.values()))
    segment_names = sorted(set(segment_codes.values()))

    def region_of(code):
        return region_codes.get(code.lower())

    def segment_of(code):
        return segment_codes.get(code.lower())

    def ticks(wh):
        return half_up_div(wh, wpt)

    dq_rows = {}

    # ---------------- events ----------------
    with open(P("events.json"), encoding="utf-8") as fh:
        events_list = json.load(fh)
    dq_rows["events.json"] = len(events_list)
    events = {e["event_id"]: e for e in events_list}
    event_ids = sorted(events)

    # ---------------- sites ----------------
    site_raw = read_delimited(P("sites.csv"), ",")
    dq_rows["sites.csv"] = len(site_raw)
    sites = {}  # (event, site) -> dict
    unknown_keys = set()
    unknown_region_rows = 0
    for r in site_raw:
        key = (r["event_id"], r["site_id"])
        reg = region_of(r["region_code"])
        if reg is None:
            unknown_region_rows += 1
            unknown_keys.add(key)
            continue
        sites[key] = {
            "event_id": r["event_id"],
            "site_id": r["site_id"],
            "region": reg,
            "segment": segment_of(r["segment_code"]),
            "beneficiary_id": r["beneficiary_id"],
            "critical": r["critical"].strip() == "Y",
        }

    # ---------------- site state ----------------
    state = {}
    n_state = 0
    with open(P("site_state.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            n_state += 1
            d = json.loads(line)
            key = (d["event_id"], d["site_id"])
            if key in sites:
                state[key] = d
    dq_rows["site_state.jsonl"] = n_state

    # ---------------- waivers ----------------
    waiv_raw = read_delimited(P("continuity_waivers.csv"), ",")
    dq_rows["continuity_waivers.csv"] = len(waiv_raw)
    waiver_signed_missing = 0
    waivers = {}
    for r in waiv_raw:
        if (r.get("waiver_signed") or "").strip() == "":
            waiver_signed_missing += 1
        key = (r["event_id"], r["site_id"])
        if key in sites:
            waivers[key] = r

    # ---------------- rate cards ----------------
    tree = ET.parse(P("rate_cards.xml"))
    root = tree.getroot()
    cards = {}
    n_cards = 0
    for card in root.iter("card"):
        n_cards += 1
        key = (card.get("event"), card.get("site"))
        if key not in sites:
            continue
        base = int(card.find("base").text.strip())
        cap = int(card.find("cap").text.strip())
        ov = card.find("override")
        start = int(ov.text.strip()) if ov is not None else base
        cards[key] = (start, cap)
    dq_rows["rate_cards.xml"] = n_cards

    # ---------------- recipient weights ----------------
    rw_raw = read_delimited(P("recipient_weights.tsv"), "\t")
    dq_rows["recipient_weights.tsv"] = len(rw_raw)
    weights = {}
    for r in rw_raw:
        key = (r["event_id"], r["site_id"])
        if key in sites:
            weights[key] = int(r["grant_weight"])

    # ---------------- offers ----------------
    off_raw = read_delimited(P("offers.csv"), ",")
    dq_rows["offers.csv"] = len(off_raw)
    offer_event = {}
    offers = {}  # offer_id -> dict (non-orphan)
    orphan_offers = 0
    for r in off_raw:
        oid = r["offer_id"]
        offer_event.setdefault(oid, r["event_id"])
        key = (r["event_id"], r["site_id"])
        if key not in sites:
            orphan_offers += 1
            continue
        offers[oid] = {
            "offer_id": oid,
            "key": key,
            "cost": int(r["bid_cost_cents"]),
        }

    # ---------------- profiles ----------------
    prof_raw = read_delimited(P("profiles.tsv"), "\t")
    dq_rows["profiles.tsv"] = len(prof_raw)
    orphan_prof = oor_prof = dup_prof = 0
    kept = {}  # (offer, interval) -> (relief_ticks, recovery_ticks)
    for r in prof_raw:
        oid = r["offer_id"]
        if oid not in offer_event:
            orphan_prof += 1
            continue
        itv = int(r["interval"])
        ev = events.get(offer_event[oid])
        n_itv = int(ev["interval_count"]) if ev is not None else 0
        if itv < 1 or itv > n_itv:
            oor_prof += 1
            continue
        pk = (oid, itv)
        if pk in kept:
            dup_prof += 1
            continue
        mult = int(r["register_multiplier"])
        kept[pk] = (ticks(int(r["relief_wh"]) * mult), ticks(int(r["recovery_wh"]) * mult))

    for oid, o in offers.items():
        ev = events[o["key"][0]]
        n = int(ev["interval_count"])
        rel = [0] * n
        rec = [0] * n
        for t in range(1, n + 1):
            v = kept.get((oid, t))
            if v is not None:
                rel[t - 1], rec[t - 1] = v
        o["rel"] = rel
        o["rec"] = rec
        o["relsum"] = sum(rel)
        o["recsum"] = sum(rec)

    # ---------------- targets ----------------
    tg_raw = read_delimited(P("targets.tsv"), "\t")
    dq_rows["targets.tsv"] = len(tg_raw)
    targets = {}
    for r in tg_raw:
        targets[(r["event_id"], region_of(r["region_code"]), int(r["interval"]))] = (
            ticks(int(r["target_wh"])),
            int(r["shortfall_weight"]),
        )

    # ---------------- feeder limits ----------------
    fl_lines = read_fixed(P("feeder_limits.txt"))
    dq_rows["feeder_limits.txt"] = len(fl_lines)
    ceilings = {}
    for l in fl_lines:
        ev = l[0:10].strip()
        code = l[10:14].strip()
        itv = int(l[14:17].strip())
        rc = int(l[17:27].strip())
        vc = int(l[27:37].strip())
        ceilings[(ev, region_of(code), itv)] = (ticks(rc), ticks(vc))

    # ---------------- pools ----------------
    pl_lines = read_fixed(P("pools.txt"))
    dq_rows["pools.txt"] = len(pl_lines)
    pools = {}
    for l in pl_lines:
        ev = l[0:10].strip()
        code = l[10:14].strip()
        pools[(ev, region_of(code))] = int(l[14:26].strip())

    # ---------------- segment floors ----------------
    with open(P("segment_floors.json"), encoding="utf-8") as fh:
        floors_raw = json.load(fh)["floors"]
    dq_rows["segment_floors.json"] = len(floors_raw)
    floors = {}
    for f in floors_raw:
        floors[(f["event_id"], region_of(f["region_code"]), segment_of(f["segment_code"]))] = (
            ticks(int(f["floor_wh"])),
            int(f["priority_weight"]),
        )

    # ---------------- allowances ----------------
    al_raw = read_commented_tsv(P("site_allowances.tsv"))
    dq_rows["site_allowances.tsv"] = len(al_raw)
    allowance = {}
    for r in al_raw:
        allowance[r["site_id"]] = int(r["allowance_ticks"])

    # ---------------- manifest ----------------
    man = read_commented_tsv(P("export_manifest.tsv"))
    dq_rows["export_manifest.tsv"] = len(man)

    # ---------------- compliance ----------------
    labels = {}
    for key, s in sites.items():
        st = state.get(key, {})
        w = waivers.get(key, {})
        cert_pending = (w.get("routine_certificate_pending") or "").strip() == "Y"
        waiver_valid = (
            (w.get("waiver_status") or "").strip() == "VALID"
            and (w.get("waiver_signed") or "").strip() == "Y"
            and s["critical"]
            and s["segment"] == "public"
        )
        if st.get("safety_hold") is True:
            lab = "SAFETY_HOLD"
        elif st.get("cooldown") is True:
            lab = "COOLDOWN"
        elif cert_pending and waiver_valid:
            lab = "CONTINUITY_WAIVED"
        elif cert_pending:
            lab = "CERTIFICATE_PENDING"
        else:
            lab = "CLEAR"
        labels[key] = lab

    def can_dispatch(key):
        return state.get(key, {}).get("dispatch_authorized") is True

    # effective rates
    rates = {}
    for key, s in sites.items():
        start, cap = cards.get(key, (0, 0))
        ev = events[key[0]]
        rate = start + int(ev.get("uplift_millicents_per_kwh", 0)) + seg_adders.get((s["segment"] or "").lower(), 0)
        rates[key] = (min(rate, cap), rate > cap)

    def credit_of(o):
        eff = rates[o["key"]][0]
        den = 1000 * mcpc
        return sum(half_even_div(rt * wpt * eff, den) for rt in o["rel"])

    # group offers by event-region
    er_offers = defaultdict(list)
    ineligible = 0
    for oid, o in offers.items():
        key = o["key"]
        if not can_dispatch(key):
            ineligible += 1
            continue
        er_offers[(key[0], sites[key]["region"])].append(o)

    er_sites = defaultdict(list)
    for key, s in sites.items():
        er_sites[(key[0], s["region"])].append(key)

    # event processing order for allowances
    def ev_instant(eid):
        return datetime.fromisoformat(events[eid]["dispatch_start"])

    order = sorted(event_ids, key=lambda e: e, reverse=True)
    order = sorted(order, key=ev_instant)  # stable: equal instants keep descending id order

    used = defaultdict(int)  # site_id -> relief ticks drawn
    allowance_blocked = 0
    results = {}

    for eid in order:
        ev = events[eid]
        n = int(ev["interval_count"])
        cw = int(ev["objective"]["cost_weight"])
        rw = int(ev["objective"]["recovery_weight"])
        ev_chosen = []
        for reg in region_names:
            cands = []
            for o in er_offers.get((eid, reg), []):
                sid = o["key"][1]
                if sid in allowance:
                    remaining = allowance[sid] - used[sid]
                    if o["relsum"] > remaining:
                        allowance_blocked += 1
                        continue
                cands.append(o)
            res = optimise(eid, reg, n, cw, rw, cands, sites, targets, ceilings, floors, segment_names)
            res["candidates"] = cands
            results[(eid, reg)] = res
            ev_chosen.extend(res["chosen"])
        for o in ev_chosen:
            used[o["key"][1]] += o["relsum"]

    # ---------------- reports ----------------
    region_docs = {r: {"region": r, "events": []} for r in region_names}
    seg_docs = {s: {"segment": s, "event_regions": []} for s in segment_names}
    tie_decisions = []
    cap_binding = 0
    residual_total = 0
    residual_tie_pools = 0
    empty_groups = 0
    zero_floor = 0
    unalloc_pools = 0

    for eid in event_ids:
        n = int(events[eid]["interval_count"])
        for reg in region_names:
            res = results[(eid, reg)]
            chosen = res["chosen"]
            if not res["candidates"]:
                empty_groups += 1
            if res["tied"] >= 2:
                tie_decisions.append({
                    "event_id": eid,
                    "region": reg,
                    "tied_portfolio_count": res["tied"],
                    "selected_offer_ids": sorted(o["offer_id"] for o in chosen),
                })
            credits = {}
            for o in chosen:
                credits[o["offer_id"]] = credit_of(o)
                if rates[o["key"]][1]:
                    cap_binding += 1
            intervals = []
            for t in range(1, n + 1):
                tgt = targets.get((eid, reg, t), (0, 0))[0]
                rel = sum(o["rel"][t - 1] for o in chosen)
                rec = sum(o["rec"][t - 1] for o in chosen)
                intervals.append({
                    "interval": t,
                    "target_ticks": tgt,
                    "relief_ticks": rel,
                    "recovery_ticks": rec,
                    "shortfall_ticks": max(0, tgt - rel),
                    "overdelivery_ticks": max(0, rel - tgt),
                })
            bid = sum(o["cost"] for o in chosen)
            credit = sum(credits.values())
            pool = pools.get((eid, reg), 0)
            F = max(0, pool - credit)

            # grants
            ben_w = defaultdict(int)
            n_recipients = 0
            for key in er_sites.get((eid, reg), []):
                if key in weights:
                    n_recipients += 1
                    w = weights[key] * (2 if labels[key] == "CONTINUITY_WAIVED" else 1)
                    ben_w[sites[key]["beneficiary_id"]] += w
            W = sum(ben_w.values())
            grants = []
            allocated = 0
            if n_recipients == 0 or W == 0:
                unalloc_pools += 1
            else:
                pos = {b: w for b, w in ben_w.items() if w > 0}
                share = {}
                rem = {}
                for b, w in pos.items():
                    share[b] = F * w // W
                    rem[b] = F * w % W
                left = F - sum(share.values())
                residual_total += left
                ranking = sorted(pos, key=lambda b: (rem[b], b), reverse=True)
                for b in ranking[:left]:
                    share[b] += 1
                remcount = defaultdict(int)
                for b in pos:
                    if rem[b] != 0:
                        remcount[rem[b]] += 1
                if any(c >= 2 for c in remcount.values()):
                    residual_tie_pools += 1
                allocated = sum(share.values())
                grants = [{"beneficiary_id": b, "cents": share[b]} for b in sorted(pos)]
            unallocated = F - allocated

            cc = {l: 0 for l in LABELS}
            for key in er_sites.get((eid, reg), []):
                cc[labels[key]] += 1

            region_docs[reg]["events"].append({
                "event_id": eid,
                "candidate_offer_count": len(res["candidates"]),
                "selected_offer_ids": sorted(o["offer_id"] for o in chosen),
                "intervals": intervals,
                "bid_cost_cents": bid,
                "credit_cents": credit,
                "grant_pool_cents": pool,
                "grant_funded_cents": F,
                "grant_allocated_cents": allocated,
                "grant_unallocated_cents": unallocated,
                "grants": grants,
                "compliance_counts": cc,
            })

            for seg in segment_names:
                sel = [o for o in chosen if sites[o["key"]]["segment"] == seg]
                ft = floors.get((eid, reg, seg), (0, 0))[0]
                srel = sum(o["relsum"] for o in sel)
                if ft == 0:
                    zero_floor += 1
                    att = 10000
                else:
                    att = min(10000, half_up_div(10000 * srel, ft))
                seg_docs[seg]["event_regions"].append({
                    "event_id": eid,
                    "region": reg,
                    "selected_offer_ids": sorted(o["offer_id"] for o in sel),
                    "relief_ticks": srel,
                    "recovery_ticks": sum(o["recsum"] for o in sel),
                    "bid_cost_cents": sum(o["cost"] for o in sel),
                    "credit_cents": sum(credits[o["offer_id"]] for o in sel),
                    "floor_ticks": ft,
                    "floor_attainment_bp": att,
                })

    for reg, doc in region_docs.items():
        evs = doc["events"]
        doc["totals"] = {
            "event_count": len(evs),
            "candidate_offer_count": sum(e["candidate_offer_count"] for e in evs),
            "selected_offer_count": sum(len(e["selected_offer_ids"]) for e in evs),
            "relief_ticks": sum(i["relief_ticks"] for e in evs for i in e["intervals"]),
            "recovery_ticks": sum(i["recovery_ticks"] for e in evs for i in e["intervals"]),
            "shortfall_ticks": sum(i["shortfall_ticks"] for e in evs for i in e["intervals"]),
            "overdelivery_ticks": sum(i["overdelivery_ticks"] for e in evs for i in e["intervals"]),
            "bid_cost_cents": sum(e["bid_cost_cents"] for e in evs),
            "credit_cents": sum(e["credit_cents"] for e in evs),
            "grant_pool_cents": sum(e["grant_pool_cents"] for e in evs),
            "grant_funded_cents": sum(e["grant_funded_cents"] for e in evs),
            "grant_allocated_cents": sum(e["grant_allocated_cents"] for e in evs),
            "grant_unallocated_cents": sum(e["grant_unallocated_cents"] for e in evs),
        }
        write_json(os.path.join(out_dir, "region_%s.json" % reg), doc)

    for seg, doc in seg_docs.items():
        ers = doc["event_regions"]
        doc["totals"] = {
            "selected_offer_count": sum(len(e["selected_offer_ids"]) for e in ers),
            "relief_ticks": sum(e["relief_ticks"] for e in ers),
            "recovery_ticks": sum(e["recovery_ticks"] for e in ers),
            "bid_cost_cents": sum(e["bid_cost_cents"] for e in ers),
            "credit_cents": sum(e["credit_cents"] for e in ers),
            "floor_ticks": sum(e["floor_ticks"] for e in ers),
        }
        write_json(os.path.join(out_dir, "segment_%s.json" % seg), doc)

    tot_keys = ["candidate_offer_count", "selected_offer_count", "relief_ticks", "recovery_ticks",
                "shortfall_ticks", "overdelivery_ticks", "bid_cost_cents", "credit_cents",
                "grant_pool_cents", "grant_funded_cents", "grant_allocated_cents",
                "grant_unallocated_cents"]
    summary = {k: sum(region_docs[r]["totals"][k] for r in region_names) for k in tot_keys}
    summary["event_count"] = len(event_ids)
    summary["event_region_count"] = len(event_ids) * len(region_names)
    summary["site_count"] = len(sites)
    summary["regions"] = {
        r: {k: region_docs[r]["totals"][k] for k in
            ["selected_offer_count", "relief_ticks", "bid_cost_cents", "credit_cents", "grant_allocated_cents"]}
        for r in region_names
    }
    summary["segments"] = {
        s: {k: seg_docs[s]["totals"][k] for k in
            ["selected_offer_count", "relief_ticks", "bid_cost_cents", "credit_cents"]}
        for s in segment_names
    }
    write_json(os.path.join(out_dir, "summary.json"), summary)

    cc_all = {l: 0 for l in LABELS}
    for lab in labels.values():
        cc_all[lab] += 1
    audit = {
        "compliance_counts": cc_all,
        "site_labels": [
            {"event_id": k[0], "site_id": k[1], "label": labels[k]} for k in sorted(labels)
        ],
        "tie_decisions": tie_decisions,
        "cap_binding_count": cap_binding,
        "residual_cents": residual_total,
        "residual_tie_pool_count": residual_tie_pools,
    }
    write_json(os.path.join(out_dir, "policy_audit.json"), audit)

    dq = {
        "rows": dq_rows,
        "orphan_offer_rows": orphan_offers,
        "orphan_profile_rows": orphan_prof,
        "out_of_range_profile_rows": oor_prof,
        "duplicate_profile_rows": dup_prof,
        "unknown_region_site_rows": unknown_region_rows,
        "waiver_signed_missing": waiver_signed_missing,
        "ineligible_offer_count": ineligible,
        "allowance_blocked_offer_count": allowance_blocked,
        "empty_candidate_groups": empty_groups,
        "zero_floor_count": zero_floor,
        "unallocated_pool_count": unalloc_pools,
    }
    write_json(os.path.join(out_dir, "data_quality.json"), dq)


def optimise(eid, reg, n, cw, rw, cands, sites, targets, ceilings, floors, segment_names):
    """Exhaustive search with sound pruning; returns chosen offers and tie count."""
    tgt = [targets.get((eid, reg, t), (0, 0))[0] for t in range(1, n + 1)]
    swt = [targets.get((eid, reg, t), (0, 0))[1] for t in range(1, n + 1)]
    ceil = [ceilings.get((eid, reg, t), (0, 0)) for t in range(1, n + 1)]
    rcap = [c[0] for c in ceil]
    vcap = [c[1] for c in ceil]
    seg_idx = {s: i for i, s in enumerate(segment_names)}
    fl = [floors.get((eid, reg, s), (0, 0)) for s in segment_names]

    by_site = defaultdict(list)
    for o in cands:
        by_site[o["key"][1]].append(o)
    site_ids = sorted(by_site)
    groups = []
    for sid in site_ids:
        opts = []
        for o in by_site[sid]:
            # an offer infeasible on its own can never be part of a feasible portfolio
            if any(o["rel"][i] > rcap[i] or o["rec"][i] > vcap[i] for i in range(n)):
                continue
            opts.append(o)
        if opts:
            groups.append(opts)
    m = len(groups)
    # suffix max relief per interval for shortfall lower bound
    sufmax = [[0] * n for _ in range(m + 1)]
    for k in range(m - 1, -1, -1):
        for i in range(n):
            sufmax[k][i] = sufmax[k + 1][i] + max(o["rel"][i] for o in groups[k])

    best = [None, 0, None]  # key, tie count, best ids tuple
    best_port = [None]
    rel = [0] * n
    rec = [0] * n
    segrel = [0] * len(segment_names)
    chosen = []

    def leaf(cost, recsum):
        c1 = 0
        c4 = 0
        for i in range(n):
            d = tgt[i] - rel[i]
            if d > 0:
                c1 += swt[i] * d
            else:
                c4 -= d
        c2 = 0
        for j, (ft, pw) in enumerate(fl):
            d = ft - segrel[j]
            if d > 0:
                c2 += pw * d
        c3 = cw * cost + rw * recsum
        key = (c1, c2, c3, c4, len(chosen))
        bk = best[0]
        if bk is None or key < bk:
            best[0] = key
            best[1] = 1
            ids = tuple(sorted(o["offer_id"] for o in chosen))
            best[2] = ids
            best_port[0] = list(chosen)
        elif key == bk:
            best[1] += 1
            ids = tuple(sorted(o["offer_id"] for o in chosen))
            if ids > best[2]:
                best[2] = ids
                best_port[0] = list(chosen)

    def dfs(k, cost, recsum):
        if best[0] is not None:
            sm = sufmax[k]
            lb = 0
            for i in range(n):
                reach = rel[i] + sm[i]
                if reach > rcap[i]:
                    reach = rcap[i]
                d = tgt[i] - reach
                if d > 0:
                    lb += swt[i] * d
            if lb > best[0][0]:
                return
        if k == m:
            leaf(cost, recsum)
            return
        dfs(k + 1, cost, recsum)
        for o in groups[k]:
            orl = o["rel"]
            orc = o["rec"]
            ok = True
            for i in range(n):
                if rel[i] + orl[i] > rcap[i] or rec[i] + orc[i] > vcap[i]:
                    ok = False
                    break
            if not ok:
                continue
            for i in range(n):
                rel[i] += orl[i]
                rec[i] += orc[i]
            j = seg_idx.get(sites[o["key"]]["segment"])
            if j is not None:
                segrel[j] += o["relsum"]
            chosen.append(o)
            dfs(k + 1, cost + o["cost"], recsum + o["recsum"])
            chosen.pop()
            if j is not None:
                segrel[j] -= o["relsum"]
            for i in range(n):
                rel[i] -= orl[i]
                rec[i] -= orc[i]

    dfs(0, 0, 0)
    return {"chosen": best_port[0] or [], "tied": best[1]}


if __name__ == "__main__":
    main()
