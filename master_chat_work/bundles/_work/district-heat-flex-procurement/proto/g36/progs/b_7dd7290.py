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
from datetime import datetime

LABELS = ("SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR")


def half_up(num, den):
    """Non-negative num/den rounded half up."""
    return (2 * num + den) // (2 * den)


def half_even(num, den):
    q, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and q % 2 == 1):
        q += 1
    return q


def read_csv(path, delimiter=","):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def non_comment_lines(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if line.startswith("#") or not line.strip():
                continue
            out.append(line)
    return out


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, sort_keys=True, indent=1))
        fh.write("\n")


def largest_remainder(total, weights):
    """weights: dict id -> positive weight. Returns (shares, residual_cents, has_tie)."""
    W = sum(weights.values())
    shares = {}
    rems = {}
    for b, w in weights.items():
        shares[b] = (total * w) // W
        rems[b] = (total * w) % W
    left = total - sum(shares.values())
    order = sorted(weights, key=lambda b: (rems[b], b), reverse=True)
    for b in order[:left]:
        shares[b] += 1
    seen = {}
    tie = False
    for b, r in rems.items():
        if r != 0:
            if r in seen:
                tie = True
            seen[r] = True
    return shares, left, tie


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    def P(name):
        return os.path.join(data_dir, name)

    # ---------------- program.ini ----------------
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(P("program.ini"), encoding="utf-8")
    wh_per_tick = int(cp.get("units", "wh_per_tick"))
    mc_per_cent = int(cp.get("units", "millicents_per_cent"))
    region_codes = {}
    for k, v in cp.items("region_codes", raw=True):
        region_codes[k.lower()] = v.strip()
    segment_codes = {}
    for k, v in cp.items("segment_codes", raw=True):
        segment_codes[k.lower()] = v.strip()
    adders = {}
    if cp.has_section("segment_rate_adders"):
        for k, v in cp.items("segment_rate_adders", raw=True):
            adders[k.lower()] = int(v.strip())
    claim_per_weight = int(cp.get("grants", "claim_cents_per_weight"))
    min_grant = int(cp.get("grants", "minimum_grant_cents"))

    regions = sorted(set(region_codes.values()))
    segments = sorted(set(segment_codes.values()))

    def region_of(code):
        return region_codes.get(code.lower())

    def segment_of(code):
        return segment_codes.get(code.lower())

    def ticks(wh):
        return half_up(wh, wh_per_tick)

    rows = {}

    # ---------------- events ----------------
    with open(P("events.json"), encoding="utf-8") as fh:
        events_raw = json.load(fh)
    rows["events.json"] = len(events_raw)
    events = {}
    for e in events_raw:
        ds = e["dispatch_start"]
        if ds.endswith("Z"):
            ds = ds[:-1] + "+00:00"
        events[e["event_id"]] = {
            "n": int(e["interval_count"]),
            "cw": int(e["objective"]["cost_weight"]),
            "rw": int(e["objective"]["recovery_weight"]),
            "start": datetime.fromisoformat(ds),
            "uplift": int(e["uplift_millicents_per_kwh"]),
        }
    event_ids = sorted(events)
    # season order: ascending start instant; equal instants -> greatest id first
    season = sorted(event_ids, reverse=True)
    season.sort(key=lambda x: events[x]["start"])

    # ---------------- sites ----------------
    sites_raw = read_csv(P("sites.csv"))
    rows["sites.csv"] = len(sites_raw)
    unknown_region = 0
    siterows = {}  # (ev, site) -> dict
    skipped_keys = set()
    for r in sites_raw:
        key = (r["event_id"], r["site_id"])
        reg = region_of(r["region_code"])
        if reg is None:
            unknown_region += 1
            skipped_keys.add(key)
            continue
        siterows[key] = {
            "region": reg,
            "segment": segment_of(r["segment_code"]),
            "ben": r["beneficiary_id"],
            "critical": r["critical"] == "Y",
            "auth": False,
            "hold": False,
            "cool": False,
            "cert": False,
            "waiver_valid": False,
            "weight": None,
        }

    # ---------------- site_state ----------------
    n_state = 0
    with open(P("site_state.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            n_state += 1
            o = json.loads(line)
            sr = siterows.get((o["event_id"], o["site_id"]))
            if sr is None:
                continue
            sr["auth"] = o.get("dispatch_authorized") is True
            sr["hold"] = o.get("safety_hold") is True
            sr["cool"] = o.get("cooldown") is True
    rows["site_state.jsonl"] = n_state

    # ---------------- waivers ----------------
    wv = read_csv(P("continuity_waivers.csv"))
    rows["continuity_waivers.csv"] = len(wv)
    waiver_missing = 0
    for r in wv:
        signed = (r.get("waiver_signed") or "").strip()
        if signed == "":
            waiver_missing += 1
        sr = siterows.get((r["event_id"], r["site_id"]))
        if sr is None:
            continue
        sr["cert"] = r["routine_certificate_pending"] == "Y"
        sr["waiver_valid"] = (
            r["waiver_status"] == "VALID"
            and signed == "Y"
            and sr["critical"]
            and sr["segment"] == "public"
        )

    for sr in siterows.values():
        if sr["hold"]:
            lab = "SAFETY_HOLD"
        elif sr["cool"]:
            lab = "COOLDOWN"
        elif sr["cert"] and sr["waiver_valid"]:
            lab = "CONTINUITY_WAIVED"
        elif sr["cert"]:
            lab = "CERTIFICATE_PENDING"
        else:
            lab = "CLEAR"
        sr["label"] = lab

    # ---------------- rate cards ----------------
    tree = ET.parse(P("rate_cards.xml"))
    cards = tree.getroot().findall("card")
    rows["rate_cards.xml"] = len(cards)
    for c in cards:
        sr = siterows.get((c.get("event"), c.get("site")))
        if sr is None:
            continue
        base = int(c.find("base").text.strip())
        ov = c.find("override")
        rate = int(ov.text.strip()) if ov is not None else base
        cap = int(c.find("cap").text.strip())
        sr["card"] = (rate, cap)

    # ---------------- recipient weights ----------------
    rw_rows = read_csv(P("recipient_weights.tsv"), "\t")
    rows["recipient_weights.tsv"] = len(rw_rows)
    for r in rw_rows:
        sr = siterows.get((r["event_id"], r["site_id"]))
        if sr is None:
            continue
        sr["weight"] = int(r["grant_weight"])

    # ---------------- offers ----------------
    offers_raw = read_csv(P("offers.csv"))
    rows["offers.csv"] = len(offers_raw)
    offer_event = {}
    offers = {}
    orphan_offers = 0
    for r in offers_raw:
        oid = r["offer_id"]
        offer_event[oid] = r["event_id"]
        key = (r["event_id"], r["site_id"])
        if key not in siterows:
            orphan_offers += 1
            continue
        n = events[r["event_id"]]["n"]
        offers[oid] = {
            "id": oid,
            "key": key,
            "cost": int(r["bid_cost_cents"]),
            "rel": [0] * n,
            "rec": [0] * n,
        }

    # ---------------- profiles ----------------
    prof = read_csv(P("profiles.tsv"), "\t")
    rows["profiles.tsv"] = len(prof)
    orphan_prof = oor_prof = dup_prof = 0
    kept = set()
    for r in prof:
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
        o = offers.get(oid)
        if o is None:
            continue
        m = int(r["register_multiplier"])
        o["rel"][t - 1] = ticks(int(r["relief_wh"]) * m)
        o["rec"][t - 1] = ticks(int(r["recovery_wh"]) * m)
    for o in offers.values():
        o["rel_total"] = sum(o["rel"])
        o["rec_total"] = sum(o["rec"])

    # ---------------- targets / ceilings / floors / pools ----------------
    tg = read_csv(P("targets.tsv"), "\t")
    rows["targets.tsv"] = len(tg)
    targets = {}
    for r in tg:
        targets[(r["event_id"], region_of(r["region_code"]), int(r["interval"]))] = (
            ticks(int(r["target_wh"])),
            int(r["shortfall_weight"]),
        )

    fl = non_comment_lines(P("feeder_limits.txt"))
    rows["feeder_limits.txt"] = len(fl)
    ceilings = {}
    for line in fl:
        ev = line[0:10].strip()
        reg = region_of(line[10:14].strip())
        t = int(line[14:17].strip())
        ceilings[(ev, reg, t)] = (ticks(int(line[17:27].strip())), ticks(int(line[27:37].strip())))

    with open(P("segment_floors.json"), encoding="utf-8") as fh:
        floors_raw = json.load(fh)["floors"]
    rows["segment_floors.json"] = len(floors_raw)
    floors = {}
    for f in floors_raw:
        floors[(f["event_id"], region_of(f["region_code"]), segment_of(f["segment_code"]))] = (
            ticks(int(f["floor_wh"])),
            int(f["priority_weight"]),
        )

    pl = non_comment_lines(P("pools.txt"))
    rows["pools.txt"] = len(pl)
    pools = {}
    for line in pl:
        ev = line[0:10].strip()
        reg = region_of(line[10:14].strip())
        pools[(ev, reg)] = int(line[14:26].strip())

    # ---------------- allowances ----------------
    al_lines = non_comment_lines(P("site_allowances.tsv"))
    al_rows = list(csv.DictReader(al_lines, delimiter="\t"))
    rows["site_allowances.tsv"] = len(al_rows)
    allow = {}
    draws = {}
    for r in al_rows:
        allow[r["site_id"]] = int(r["allowance_ticks"])
        d = (r.get("draws_from") or "").strip()
        draws[r["site_id"]] = d

    def root_of(site):
        seen = set()
        cur = site
        while draws.get(cur) and cur not in seen:
            seen.add(cur)
            cur = draws[cur]
        return cur

    roots = {}
    drawn = {}

    # ---------------- manifest ----------------
    mf = non_comment_lines(P("export_manifest.tsv"))
    rows["export_manifest.tsv"] = max(0, len(mf) - 1)

    # ---------------- group site rows / offers by event-region ----------------
    er_sites = {}
    for key, sr in siterows.items():
        er_sites.setdefault((key[0], sr["region"]), []).append(key)
    site_offers = {}
    for o in offers.values():
        site_offers.setdefault(o["key"], []).append(o)

    ineligible = 0
    blocked = 0
    empty_groups = 0
    zero_floor = 0
    unalloc_pools = 0
    cap_binding = 0
    residual_total = 0
    residual_tie_pools = 0
    tie_decisions = []
    carried = {reg: 0 for reg in regions}
    results = {}  # (ev, reg) -> dict

    for ev in season:
        E = events[ev]
        n = E["n"]
        chosen_this_event = []
        for reg in regions:
            # candidates
            cand_by_site = {}
            cand_count = 0
            for key in sorted(er_sites.get((ev, reg), [])):
                sr = siterows[key]
                for o in site_offers.get(key, []):
                    if not sr["auth"]:
                        ineligible += 1
                        continue
                    site = key[1]
                    if site in allow or site in draws:
                        if site not in roots:
                            roots[site] = root_of(site)
                        rt = roots[site]
                        if rt in allow:
                            remaining = allow[rt] - drawn.get(rt, 0)
                            if o["rel_total"] > remaining:
                                blocked += 1
                                continue
                    cand_by_site.setdefault(key, []).append(o)
                    cand_count += 1
            if cand_count == 0:
                empty_groups += 1

            tgt = []
            sw = []
            rc = []
            vc = []
            for t in range(1, n + 1):
                a, b = targets.get((ev, reg, t), (0, 0))
                tgt.append(a)
                sw.append(b)
                c, d = ceilings.get((ev, reg, t), (0, 0))
                rc.append(c)
                vc.append(d)
            seg_idx = {s: i for i, s in enumerate(segments)}
            fl_t = []
            fl_w = []
            for s in segments:
                a, b = floors.get((ev, reg, s), (0, 0))
                fl_t.append(a)
                fl_w.append(b)
                if a == 0:
                    zero_floor += 1
            cw, rwt = E["cw"], E["rw"]

            groups = []
            for key in sorted(cand_by_site):
                si = seg_idx.get(siterows[key]["segment"], -1)
                opts = []
                for o in sorted(cand_by_site[key], key=lambda x: x["id"]):
                    opts.append((o["id"], o["rel"], o["rec"], o["cost"], si, o["rel_total"]))
                groups.append(opts)
            G = len(groups)
            # max additional relief per interval from groups i.. (for a shortfall bound)
            maxrem = [[0] * n for _ in range(G + 1)]
            for i in range(G - 1, -1, -1):
                for t in range(n):
                    m = 0
                    for op in groups[i]:
                        if op[1][t] > m:
                            m = op[1][t]
                    maxrem[i][t] = maxrem[i + 1][t] + min(m, rc[t])
            nseg = len(segments)
            best = [None]
            ties = []
            T = range(n)

            def dfs(i, rel, rec, cost, segrel, chosen):
                if best[0] is not None:
                    mr = maxrem[i]
                    lb = 0
                    for t in T:
                        d = tgt[t] - rel[t] - mr[t]
                        if d > 0:
                            lb += sw[t] * d
                    if lb > best[0][0]:
                        return
                if i == G:
                    c1 = 0
                    c4 = 0
                    for t in T:
                        d = tgt[t] - rel[t]
                        if d > 0:
                            c1 += sw[t] * d
                        else:
                            c4 -= d
                    c2 = 0
                    for s in range(nseg):
                        d = fl_t[s] - segrel[s]
                        if d > 0:
                            c2 += fl_w[s] * d
                    c3 = cw * cost + rwt * sum(rec)
                    k = (c1, c2, c3, c4, len(chosen))
                    if best[0] is None or k < best[0]:
                        best[0] = k
                        ties.clear()
                        ties.append(tuple(chosen))
                    elif k == best[0]:
                        ties.append(tuple(chosen))
                    return
                dfs(i + 1, rel, rec, cost, segrel, chosen)
                for op in groups[i]:
                    orel, orec = op[1], op[2]
                    nrel = [rel[t] + orel[t] for t in T]
                    ok = True
                    for t in T:
                        if nrel[t] > rc[t]:
                            ok = False
                            break
                    if not ok:
                        continue
                    nrec = [rec[t] + orec[t] for t in T]
                    for t in T:
                        if nrec[t] > vc[t]:
                            ok = False
                            break
                    if not ok:
                        continue
                    if op[4] >= 0:
                        nseg_rel = list(segrel)
                        nseg_rel[op[4]] += op[5]
                    else:
                        nseg_rel = segrel
                    chosen.append(op[0])
                    dfs(i + 1, nrel, nrec, cost + op[3], nseg_rel, chosen)
                    chosen.pop()

            dfs(0, [0] * n, [0] * n, 0, [0] * nseg, [])
            sel = max(tuple(sorted(x)) for x in ties)
            if len(ties) >= 2:
                tie_decisions.append(
                    {
                        "event_id": ev,
                        "region": reg,
                        "tied_portfolio_count": len(ties),
                        "selected_offer_ids": list(sel),
                    }
                )
            sel_offers = [offers[oid] for oid in sel]
            chosen_this_event.extend(sel_offers)

            # settlement
            credit_total = 0
            per_offer = {}
            for o in sel_offers:
                sr = siterows[o["key"]]
                base_rate, cap = sr.get("card", (0, 0))
                rate = base_rate + adders.get((sr["segment"] or "").lower(), 0) + E["uplift"]
                if rate > cap:
                    cap_binding += 1
                    eff = cap
                else:
                    eff = rate
                cr = 0
                for t in T:
                    ct = o["rel"][t] - o["rec"][t]
                    if ct > 0:
                        cr += half_even(ct * wh_per_tick * eff, 1000 * mc_per_cent)
                per_offer[o["id"]] = cr
                credit_total += cr

            # grants
            pool = pools.get((ev, reg), 0)
            F = pool + carried[reg] - credit_total
            if F < 0:
                F = 0
            bw = {}
            recipients = 0
            for key in er_sites.get((ev, reg), []):
                sr = siterows[key]
                if sr["weight"] is None:
                    continue
                recipients += 1
                w = sr["weight"] * (2 if sr["label"] == "CONTINUITY_WAIVED" else 1)
                bw[sr["ben"]] = bw.get(sr["ben"], 0) + w
            pos = {b: w for b, w in bw.items() if w > 0}
            W = sum(pos.values())
            grants = {}
            if recipients == 0 or W == 0:
                unalloc_pools += 1
                allocated = 0
            else:
                claims = {b: w * claim_per_weight for b, w in pos.items()}
                if sum(claims.values()) <= F:
                    grants = claims
                    allocated = sum(claims.values())
                else:
                    shares, left, tie = largest_remainder(F, pos)
                    keep = {b: w for b, w in pos.items() if shares[b] >= min_grant}
                    if len(keep) == len(pos):
                        grants = shares
                        residual_total += left
                        residual_tie_pools += 1 if tie else 0
                    elif not keep:
                        grants = {b: 0 for b in pos}
                    else:
                        shares2, left2, tie2 = largest_remainder(F, keep)
                        grants = {b: shares2.get(b, 0) for b in pos}
                        residual_total += left2
                        residual_tie_pools += 1 if tie2 else 0
                    allocated = sum(grants.values())
            unallocated = F - allocated
            carried[reg] = unallocated

            intervals = []
            for t in T:
                relt = sum(o["rel"][t] for o in sel_offers)
                rect = sum(o["rec"][t] for o in sel_offers)
                intervals.append(
                    {
                        "interval": t + 1,
                        "target_ticks": tgt[t],
                        "relief_ticks": relt,
                        "recovery_ticks": rect,
                        "shortfall_ticks": max(0, tgt[t] - relt),
                        "overdelivery_ticks": max(0, relt - tgt[t]),
                    }
                )
            counts = {lab: 0 for lab in LABELS}
            for key in er_sites.get((ev, reg), []):
                counts[siterows[key]["label"]] += 1
            seg_parts = {}
            for s in segments:
                so = [o for o in sel_offers if siterows[o["key"]]["segment"] == s]
                ft = floors.get((ev, reg, s), (0, 0))[0]
                rel_s = sum(o["rel_total"] for o in so)
                if ft == 0:
                    bp = 10000
                else:
                    bp = min(10000, half_up(10000 * rel_s, ft))
                seg_parts[s] = {
                    "event_id": ev,
                    "region": reg,
                    "selected_offer_ids": sorted(o["id"] for o in so),
                    "relief_ticks": rel_s,
                    "recovery_ticks": sum(o["rec_total"] for o in so),
                    "bid_cost_cents": sum(o["cost"] for o in so),
                    "credit_cents": sum(per_offer[o["id"]] for o in so),
                    "floor_ticks": ft,
                    "floor_attainment_bp": bp,
                }
            results[(ev, reg)] = {
                "entry": {
                    "event_id": ev,
                    "candidate_offer_count": cand_count,
                    "selected_offer_ids": list(sel),
                    "intervals": intervals,
                    "bid_cost_cents": sum(o["cost"] for o in sel_offers),
                    "credit_cents": credit_total,
                    "grant_pool_cents": pool,
                    "grant_funded_cents": F,
                    "grant_allocated_cents": allocated,
                    "grant_unallocated_cents": unallocated,
                    "grants": [
                        {"beneficiary_id": b, "cents": grants.get(b, 0)} for b in sorted(pos)
                    ],
                    "compliance_counts": counts,
                },
                "seg": seg_parts,
            }
        # draw allowances after every region of this event is decided
        for o in chosen_this_event:
            site = o["key"][1]
            rt = roots.get(site)
            if rt is None:
                rt = root_of(site)
                roots[site] = rt
            drawn[rt] = drawn.get(rt, 0) + o["rel_total"]

    # ---------------- region files ----------------
    tot_keys = [
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
    summary = {k: 0 for k in tot_keys}
    summary_regions = {}
    for reg in regions:
        entries = [results[(ev, reg)]["entry"] for ev in event_ids]
        tot = {k: 0 for k in tot_keys}
        tot["event_count"] = len(entries)
        for e in entries:
            tot["candidate_offer_count"] += e["candidate_offer_count"]
            tot["selected_offer_count"] += len(e["selected_offer_ids"])
            for iv in e["intervals"]:
                tot["relief_ticks"] += iv["relief_ticks"]
                tot["recovery_ticks"] += iv["recovery_ticks"]
                tot["shortfall_ticks"] += iv["shortfall_ticks"]
                tot["overdelivery_ticks"] += iv["overdelivery_ticks"]
            for k in (
                "bid_cost_cents",
                "credit_cents",
                "grant_pool_cents",
                "grant_funded_cents",
                "grant_allocated_cents",
                "grant_unallocated_cents",
            ):
                tot[k] += e[k]
        write_json(
            os.path.join(out_dir, "region_%s.json" % reg),
            {"region": reg, "events": entries, "totals": tot},
        )
        for k in tot_keys:
            summary[k] += tot[k]
        summary_regions[reg] = {
            "selected_offer_count": tot["selected_offer_count"],
            "relief_ticks": tot["relief_ticks"],
            "bid_cost_cents": tot["bid_cost_cents"],
            "credit_cents": tot["credit_cents"],
            "grant_allocated_cents": tot["grant_allocated_cents"],
        }

    # ---------------- segment files ----------------
    summary_segments = {}
    for s in segments:
        parts = [results[(ev, reg)]["seg"][s] for ev in event_ids for reg in regions]
        tot = {
            "selected_offer_count": sum(len(p["selected_offer_ids"]) for p in parts),
            "relief_ticks": sum(p["relief_ticks"] for p in parts),
            "recovery_ticks": sum(p["recovery_ticks"] for p in parts),
            "bid_cost_cents": sum(p["bid_cost_cents"] for p in parts),
            "credit_cents": sum(p["credit_cents"] for p in parts),
            "floor_ticks": sum(p["floor_ticks"] for p in parts),
        }
        write_json(
            os.path.join(out_dir, "segment_%s.json" % s),
            {"segment": s, "event_regions": parts, "totals": tot},
        )
        summary_segments[s] = {
            "selected_offer_count": tot["selected_offer_count"],
            "relief_ticks": tot["relief_ticks"],
            "bid_cost_cents": tot["bid_cost_cents"],
            "credit_cents": tot["credit_cents"],
        }

    summary["event_count"] = len(event_ids)
    summary["event_region_count"] = len(event_ids) * len(regions)
    summary["site_count"] = len(siterows)
    summary["regions"] = summary_regions
    summary["segments"] = summary_segments
    write_json(os.path.join(out_dir, "summary.json"), summary)

    # ---------------- policy audit ----------------
    counts = {lab: 0 for lab in LABELS}
    labels = []
    for key in sorted(siterows):
        lab = siterows[key]["label"]
        counts[lab] += 1
        labels.append({"event_id": key[0], "site_id": key[1], "label": lab})
    tie_decisions.sort(key=lambda d: (d["event_id"], d["region"]))
    write_json(
        os.path.join(out_dir, "policy_audit.json"),
        {
            "compliance_counts": counts,
            "site_labels": labels,
            "tie_decisions": tie_decisions,
            "cap_binding_count": cap_binding,
            "residual_cents": residual_total,
            "residual_tie_pool_count": residual_tie_pools,
        },
    )

    # ---------------- data quality ----------------
    write_json(
        os.path.join(out_dir, "data_quality.json"),
        {
            "rows": rows,
            "orphan_offer_rows": orphan_offers,
            "orphan_profile_rows": orphan_prof,
            "out_of_range_profile_rows": oor_prof,
            "duplicate_profile_rows": dup_prof,
            "unknown_region_site_rows": unknown_region,
            "waiver_signed_missing": waiver_missing,
            "ineligible_offer_count": ineligible,
            "allowance_blocked_offer_count": blocked,
            "empty_candidate_groups": empty_groups,
            "zero_floor_count": zero_floor,
            "unallocated_pool_count": unalloc_pools,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
