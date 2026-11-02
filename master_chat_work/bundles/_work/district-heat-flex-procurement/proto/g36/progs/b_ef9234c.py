#!/usr/bin/env python3
"""District heat flexibility programme: derive season reports.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""
import configparser
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

LABELS = ["SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR"]


def rhu(num, den):
    """Round num/den half up (non-negative)."""
    return (2 * num + den) // (2 * den)


def rhe(num, den):
    """Round num/den half to even (non-negative)."""
    q, r = divmod(num, den)
    if 2 * r > den:
        return q + 1
    if 2 * r < den:
        return q
    return q + 1 if q % 2 == 1 else q


def read_csv(path, delim):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=delim))


def read_commented_tsv(path):
    header = None
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if line.startswith("#"):
                continue
            if header is None:
                if line.strip() == "":
                    continue
                header = line.split("\t")
                continue
            if line.strip() == "":
                continue
            parts = line.split("\t")
            parts += [""] * (len(header) - len(parts))
            rows.append(dict(zip(header, parts)))
    return rows


def read_fixed(path):
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if line.startswith("#") or line.strip() == "":
                continue
            lines.append(line)
    return lines


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, sort_keys=True, indent=1)
        f.write("\n")


def lr_share(F, items):
    """Largest remainder share of F over items [(id, weight)] with weight > 0.

    Returns (shares dict, residual cents, residual tie flag)."""
    W = sum(w for _, w in items)
    shares = {}
    rems = []
    given = 0
    for bid, w in items:
        q, r = divmod(F * w, W)
        shares[bid] = q
        given += q
        rems.append((r, bid))
    left = F - given
    rems.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for k in range(left):
        shares[rems[k][1]] += 1
    cnt = {}
    for r, _ in rems:
        if r > 0:
            cnt[r] = cnt.get(r, 0) + 1
    tie = any(v >= 2 for v in cnt.values())
    return shares, left, tie


def solve(n, sites_opts, target, tweight, rel_ceil, rec_ceil, seg_names, floors, cw, rw):
    """Exhaustive branch and bound. sites_opts: list of lists of offers.

    Offer: dict with id, rel (list), rec (list), relsum, recsum, cost, seg.
    Returns (best key, list of tied id tuples)."""
    m = len(sites_opts)
    # suffix maxima for bounds
    suf_rel = [[0] * n for _ in range(m + 1)]
    suf_seg = [dict((s, 0) for s in seg_names) for _ in range(m + 1)]
    for i in range(m - 1, -1, -1):
        for t in range(n):
            suf_rel[i][t] = suf_rel[i + 1][t] + max(o["rel"][t] for o in sites_opts[i])
        d = dict(suf_seg[i + 1])
        best_by_seg = {}
        for o in sites_opts[i]:
            best_by_seg[o["seg"]] = max(best_by_seg.get(o["seg"], 0), o["relsum"])
        for s, v in best_by_seg.items():
            d[s] = d.get(s, 0) + v
        suf_seg[i] = d

    best = [None]
    ties = []
    cur_rel = [0] * n
    cur_rec = [0] * n
    seg_rel = dict((s, 0) for s in seg_names)
    chosen = []
    state = {"bid": 0, "rec": 0}

    def leaf():
        sf = 0
        ov = 0
        for t in range(n):
            d = target[t] - cur_rel[t]
            if d > 0:
                sf += tweight[t] * d
            else:
                ov += -d
        fd = 0
        for s in seg_names:
            fl, pw = floors[s]
            d = fl - seg_rel.get(s, 0)
            if d > 0:
                fd += pw * d
        key = (sf, fd, cw * state["bid"] + rw * state["rec"], ov, len(chosen))
        ids = tuple(sorted(chosen))
        if best[0] is None or key < best[0]:
            best[0] = key
            ties.clear()
            ties.append(ids)
        elif key == best[0]:
            ties.append(ids)

    def bound_prune(i):
        if best[0] is None:
            return False
        lb1 = 0
        sr = suf_rel[i]
        for t in range(n):
            mx = cur_rel[t] + sr[t]
            if mx > rel_ceil[t]:
                mx = rel_ceil[t]
            d = target[t] - mx
            if d > 0:
                lb1 += tweight[t] * d
        b = best[0]
        if lb1 != b[0]:
            return lb1 > b[0]
        lb2 = 0
        ss = suf_seg[i]
        for s in seg_names:
            fl, pw = floors[s]
            d = fl - seg_rel.get(s, 0) - ss.get(s, 0)
            if d > 0:
                lb2 += pw * d
        if lb2 != b[1]:
            return lb2 > b[1]
        lb3 = cw * state["bid"] + rw * state["rec"]
        return lb3 > b[2]

    def dfs(i):
        if i == m:
            leaf()
            return
        if bound_prune(i):
            return
        for o in sites_opts[i]:
            rel = o["rel"]
            rec = o["rec"]
            ok = True
            for t in range(n):
                if cur_rel[t] + rel[t] > rel_ceil[t] or cur_rec[t] + rec[t] > rec_ceil[t]:
                    ok = False
                    break
            if not ok:
                continue
            for t in range(n):
                cur_rel[t] += rel[t]
                cur_rec[t] += rec[t]
            seg_rel[o["seg"]] = seg_rel.get(o["seg"], 0) + o["relsum"]
            state["bid"] += o["cost"]
            state["rec"] += o["recsum"]
            chosen.append(o["id"])
            dfs(i + 1)
            chosen.pop()
            state["bid"] -= o["cost"]
            state["rec"] -= o["recsum"]
            seg_rel[o["seg"]] -= o["relsum"]
            for t in range(n):
                cur_rel[t] -= rel[t]
                cur_rec[t] -= rec[t]
        # choose nothing at this site
        dfs(i + 1)

    dfs(0)
    return best[0], ties


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        sys.exit(2)
    data, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    P = lambda name: os.path.join(data, name)

    cp = configparser.ConfigParser()
    cp.read(P("program.ini"), encoding="utf-8")
    wpt = int(cp["units"]["wh_per_tick"])
    mcpc = int(cp["units"]["millicents_per_cent"])
    region_codes = {k.lower(): v.strip() for k, v in cp["region_codes"].items()}
    segment_codes = {k.lower(): v.strip() for k, v in cp["segment_codes"].items()}
    adders = {}
    if cp.has_section("segment_rate_adders"):
        adders = {k.lower(): int(v) for k, v in cp["segment_rate_adders"].items()}
    claim_per_w = int(cp["grants"]["claim_cents_per_weight"])
    min_grant = int(cp["grants"]["minimum_grant_cents"])
    regions = sorted(set(region_codes.values()))
    segments = sorted(set(segment_codes.values()))

    def reg(code):
        return region_codes.get(code.strip().lower())

    def segn(code):
        return segment_codes.get(code.strip().lower())

    def ticks(wh):
        return rhu(wh, wpt)

    rows = {}

    # events
    with open(P("events.json"), encoding="utf-8") as f:
        events_list = json.load(f)
    rows["events.json"] = len(events_list)
    events = {}
    for e in events_list:
        events[e["event_id"]] = e
    event_ids = sorted(events)
    # season order: start instant ascending, same instant -> greater id first
    season = sorted(event_ids, reverse=True)
    season.sort(key=lambda eid: datetime.fromisoformat(events[eid]["dispatch_start"]))

    # sites
    site_rows_raw = read_csv(P("sites.csv"), ",")
    rows["sites.csv"] = len(site_rows_raw)
    sites = {}
    unknown_keys = set()
    unknown_region = 0
    for r in site_rows_raw:
        key = (r["event_id"], r["site_id"])
        rg = reg(r["region_code"])
        if rg is None:
            unknown_region += 1
            unknown_keys.add(key)
            continue
        sites[key] = {
            "event_id": r["event_id"],
            "site_id": r["site_id"],
            "region": rg,
            "segment": segn(r["segment_code"]),
            "beneficiary": r["beneficiary_id"],
            "critical": r["critical"].strip() == "Y",
            "auth": False,
            "hold": False,
            "cool": False,
            "cert": False,
            "wstatus": "NONE",
            "wsigned": "",
            "weight": None,
            "rate": 0,
            "cap": 0,
        }

    # site state
    n_state = 0
    with open(P("site_state.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip() == "":
                continue
            n_state += 1
            o = json.loads(line)
            key = (o["event_id"], o["site_id"])
            if key in sites:
                s = sites[key]
                s["auth"] = o.get("dispatch_authorized") is True
                s["hold"] = o.get("safety_hold") is True
                s["cool"] = o.get("cooldown") is True
    rows["site_state.jsonl"] = n_state

    # waivers
    wv = read_csv(P("continuity_waivers.csv"), ",")
    rows["continuity_waivers.csv"] = len(wv)
    waiver_signed_missing = 0
    for r in wv:
        signed = (r.get("waiver_signed") or "").strip()
        if signed == "":
            waiver_signed_missing += 1
        key = (r["event_id"], r["site_id"])
        if key in sites:
            s = sites[key]
            s["cert"] = r["routine_certificate_pending"].strip() == "Y"
            s["wstatus"] = r["waiver_status"].strip()
            s["wsigned"] = signed

    # rate cards
    tree = ET.parse(P("rate_cards.xml"))
    cards = tree.getroot().findall("card")
    rows["rate_cards.xml"] = len(cards)
    for c in cards:
        key = (c.get("event"), c.get("site"))
        if key not in sites:
            continue
        s = sites[key]
        base = int(c.find("base").text.strip())
        ov = c.find("override")
        rate = int(ov.text.strip()) if ov is not None and ov.text is not None and ov.text.strip() != "" else base
        rate += int(events[s["event_id"]]["uplift_millicents_per_kwh"])
        rate += adders.get((s["segment"] or "").lower(), 0)
        s["rate"] = rate
        s["cap"] = int(c.find("cap").text.strip())

    # recipient weights
    rw_rows = read_csv(P("recipient_weights.tsv"), "\t")
    rows["recipient_weights.tsv"] = len(rw_rows)
    for r in rw_rows:
        key = (r["event_id"], r["site_id"])
        if key in sites:
            sites[key]["weight"] = int(r["grant_weight"])

    # labels
    for s in sites.values():
        waiver_valid = (s["wstatus"] == "VALID" and s["wsigned"] == "Y" and s["critical"]
                        and s["segment"] == "public")
        if s["hold"]:
            lab = "SAFETY_HOLD"
        elif s["cool"]:
            lab = "COOLDOWN"
        elif s["cert"] and waiver_valid:
            lab = "CONTINUITY_WAIVED"
        elif s["cert"]:
            lab = "CERTIFICATE_PENDING"
        else:
            lab = "CLEAR"
        s["label"] = lab

    # offers
    offers_raw = read_csv(P("offers.csv"), ",")
    rows["offers.csv"] = len(offers_raw)
    offer_event = {}
    offers = {}
    orphan_offers = 0
    for r in offers_raw:
        oid = r["offer_id"]
        offer_event.setdefault(oid, r["event_id"])
        key = (r["event_id"], r["site_id"])
        if key not in sites:
            orphan_offers += 1
            continue
        n = int(events[r["event_id"]]["interval_count"])
        offers[oid] = {
            "id": oid,
            "key": key,
            "cost": int(r["bid_cost_cents"]),
            "rel": [0] * n,
            "rec": [0] * n,
            "seg": sites[key]["segment"],
        }

    # profiles
    prof = read_csv(P("profiles.tsv"), "\t")
    rows["profiles.tsv"] = len(prof)
    orphan_prof = oor_prof = dup_prof = 0
    kept = set()
    for r in prof:
        oid = r["offer_id"]
        if oid not in offer_event:
            orphan_prof += 1
            continue
        itv = int(r["interval"])
        n = int(events[offer_event[oid]]["interval_count"])
        if itv < 1 or itv > n:
            oor_prof += 1
            continue
        if (oid, itv) in kept:
            dup_prof += 1
            continue
        kept.add((oid, itv))
        if oid in offers:
            mult = int(r["register_multiplier"])
            offers[oid]["rel"][itv - 1] = ticks(int(r["relief_wh"]) * mult)
            offers[oid]["rec"][itv - 1] = ticks(int(r["recovery_wh"]) * mult)
    for o in offers.values():
        o["relsum"] = sum(o["rel"])
        o["recsum"] = sum(o["rec"])

    # targets
    tg = read_csv(P("targets.tsv"), "\t")
    rows["targets.tsv"] = len(tg)
    targets = {}
    for r in tg:
        targets[(r["event_id"], reg(r["region_code"]), int(r["interval"]))] = (
            ticks(int(r["target_wh"])), int(r["shortfall_weight"]))

    # feeder limits
    fl_lines = read_fixed(P("feeder_limits.txt"))
    rows["feeder_limits.txt"] = len(fl_lines)
    ceilings = {}
    for line in fl_lines:
        eid = line[0:10].strip()
        rg = reg(line[10:14])
        itv = int(line[14:17].strip())
        ceilings[(eid, rg, itv)] = (ticks(int(line[17:27].strip())), ticks(int(line[27:37].strip())))

    # segment floors
    with open(P("segment_floors.json"), encoding="utf-8") as f:
        fl_json = json.load(f)
    fl_entries = fl_json.get("floors", [])
    rows["segment_floors.json"] = len(fl_entries)
    floors = {}
    for r in fl_entries:
        floors[(r["event_id"], reg(r["region_code"]), segn(r["segment_code"]))] = (
            ticks(int(r["floor_wh"])), int(r["priority_weight"]))

    # pools
    pl_lines = read_fixed(P("pools.txt"))
    rows["pools.txt"] = len(pl_lines)
    pools = {}
    for line in pl_lines:
        pools[(line[0:10].strip(), reg(line[10:14]))] = int(line[14:26].strip())

    # allowances
    al_rows = read_commented_tsv(P("site_allowances.tsv"))
    rows["site_allowances.tsv"] = len(al_rows)
    allow = {}
    draws = {}
    for r in al_rows:
        sid = r["site_id"]
        allow[sid] = int(r["allowance_ticks"].strip() or "0")
        draws[sid] = (r.get("draws_from") or "").strip()

    def root_of(sid):
        seen = set()
        cur = sid
        while cur in draws and draws[cur] != "" and cur not in seen:
            seen.add(cur)
            cur = draws[cur]
        return cur

    remaining = {}
    for sid in allow:
        if draws[sid] == "":
            remaining[sid] = allow[sid]

    # manifest
    rows["export_manifest.tsv"] = len(read_commented_tsv(P("export_manifest.tsv")))

    # group site rows by event-region
    er_sites = {}
    for key, s in sites.items():
        er_sites.setdefault((s["event_id"], s["region"]), []).append(s)
    offers_by_site = {}
    for o in offers.values():
        offers_by_site.setdefault(o["key"], []).append(o)

    ineligible = 0
    allowance_blocked = 0
    empty_groups = 0
    zero_floor = 0
    unalloc_pools = 0
    cap_binding = 0
    residual_total = 0
    residual_tie_pools = 0
    tie_decisions = []
    carried = {rg: 0 for rg in regions}
    results = {}

    for eid in season:
        ev = events[eid]
        n = int(ev["interval_count"])
        cw = int(ev["objective"]["cost_weight"])
        rwt = int(ev["objective"]["recovery_weight"])
        deductions = {}
        for rg in regions:
            srows = sorted(er_sites.get((eid, rg), []), key=lambda s: s["site_id"])
            site_opts = []
            cand_count = 0
            for s in srows:
                key = (eid, s["site_id"])
                so = offers_by_site.get(key, [])
                if not s["auth"]:
                    ineligible += len(so)
                    continue
                root = root_of(s["site_id"])
                rem = remaining.get(root)
                cands = []
                for o in sorted(so, key=lambda o: o["id"]):
                    if rem is not None and o["relsum"] > rem:
                        allowance_blocked += 1
                        continue
                    cands.append(o)
                cand_count += len(cands)
                if cands:
                    site_opts.append(cands)
            if cand_count == 0:
                empty_groups += 1
            target = []
            tweight = []
            rc = []
            vc = []
            for t in range(1, n + 1):
                tt, ww = targets.get((eid, rg, t), (0, 0))
                target.append(tt)
                tweight.append(ww)
                a, b = ceilings.get((eid, rg, t), (0, 0))
                rc.append(a)
                vc.append(b)
            fl = {}
            for sg in segments:
                fl[sg] = floors.get((eid, rg, sg), (0, 0))
                if fl[sg][0] == 0:
                    zero_floor += 1
            best, ties = solve(n, site_opts, target, tweight, rc, vc, segments, fl, cw, rwt)
            chosen_ids = max(ties)
            if len(ties) >= 2:
                tie_decisions.append({"event_id": eid, "region": rg,
                                      "tied_portfolio_count": len(ties),
                                      "selected_offer_ids": list(chosen_ids)})
            chosen = [offers[i] for i in chosen_ids]
            rel_t = [0] * n
            rec_t = [0] * n
            credit = 0
            bid = 0
            seg_stats = {sg: {"ids": [], "rel": 0, "rec": 0, "bid": 0, "credit": 0} for sg in segments}
            for o in chosen:
                s = sites[o["key"]]
                eff = min(s["rate"], s["cap"])
                if s["rate"] > s["cap"]:
                    cap_binding += 1
                oc = 0
                for t in range(n):
                    rel_t[t] += o["rel"][t]
                    rec_t[t] += o["rec"][t]
                    cr = o["rel"][t] - o["rec"][t]
                    if cr > 0:
                        oc += rhe(cr * wpt * eff, 1000 * mcpc)
                credit += oc
                bid += o["cost"]
                st = seg_stats.setdefault(o["seg"], {"ids": [], "rel": 0, "rec": 0, "bid": 0, "credit": 0})
                st["ids"].append(o["id"])
                st["rel"] += o["relsum"]
                st["rec"] += o["recsum"]
                st["bid"] += o["cost"]
                st["credit"] += oc
                root = root_of(s["site_id"])
                if root in remaining:
                    deductions[root] = deductions.get(root, 0) + o["relsum"]
            intervals = []
            for t in range(n):
                intervals.append({
                    "interval": t + 1,
                    "target_ticks": target[t],
                    "relief_ticks": rel_t[t],
                    "recovery_ticks": rec_t[t],
                    "shortfall_ticks": max(0, target[t] - rel_t[t]),
                    "overdelivery_ticks": max(0, rel_t[t] - target[t]),
                })

            # grants
            pool = pools.get((eid, rg), 0)
            F = max(0, pool + carried[rg] - credit)
            bweights = {}
            has_recip = False
            for s in srows:
                if s["weight"] is None:
                    continue
                has_recip = True
                w = s["weight"] * (2 if s["label"] == "CONTINUITY_WAIVED" else 1)
                bweights[s["beneficiary"]] = bweights.get(s["beneficiary"], 0) + w
            W = sum(bweights.values())
            pos = sorted((b, w) for b, w in bweights.items() if w > 0)
            grants = {b: 0 for b, _ in pos}
            if not has_recip or W == 0:
                unalloc_pools += 1
            else:
                claims = sum(w * claim_per_w for _, w in pos)
                if claims <= F:
                    for b, w in pos:
                        grants[b] = w * claim_per_w
                else:
                    shares, resid, tie = lr_share(F, pos)
                    small = [b for b, _ in pos if shares[b] < min_grant]
                    if not small:
                        grants.update(shares)
                        residual_total += resid
                        residual_tie_pools += 1 if tie else 0
                    elif len(small) < len(pos):
                        keep = [(b, w) for b, w in pos if shares[b] >= min_grant]
                        shares2, resid2, tie2 = lr_share(F, keep)
                        grants.update(shares2)
                        residual_total += resid2
                        residual_tie_pools += 1 if tie2 else 0
                    # else: all nothing, whole F unallocated
            allocated = sum(grants.values())
            unalloc = F - allocated
            carried[rg] = unalloc

            cc = {lab: 0 for lab in LABELS}
            for s in srows:
                cc[s["label"]] += 1

            results[(eid, rg)] = {
                "event_id": eid,
                "candidate_offer_count": cand_count,
                "selected_offer_ids": list(chosen_ids),
                "intervals": intervals,
                "bid_cost_cents": bid,
                "credit_cents": credit,
                "grant_pool_cents": pool,
                "grant_funded_cents": F,
                "grant_allocated_cents": allocated,
                "grant_unallocated_cents": unalloc,
                "grants": [{"beneficiary_id": b, "cents": grants[b]} for b, _ in pos],
                "compliance_counts": cc,
                "_seg": seg_stats,
                "_fl": fl,
            }
        for root, d in deductions.items():
            remaining[root] -= d

    # region files
    tot_keys = ["event_count", "candidate_offer_count", "selected_offer_count", "relief_ticks",
                "recovery_ticks", "shortfall_ticks", "overdelivery_ticks", "bid_cost_cents",
                "credit_cents", "grant_pool_cents", "grant_funded_cents", "grant_allocated_cents",
                "grant_unallocated_cents"]
    summary = {k: 0 for k in tot_keys if k != "event_count"}
    summary["event_count"] = len(event_ids)
    summary["event_region_count"] = len(event_ids) * len(regions)
    summary["site_count"] = len(sites)
    summary["regions"] = {}
    summary["segments"] = {}
    for rg in regions:
        evs = []
        tot = {k: 0 for k in tot_keys}
        for eid in event_ids:
            r = results[(eid, rg)]
            e = {k: v for k, v in r.items() if not k.startswith("_")}
            evs.append(e)
            tot["event_count"] += 1
            tot["candidate_offer_count"] += e["candidate_offer_count"]
            tot["selected_offer_count"] += len(e["selected_offer_ids"])
            for iv in e["intervals"]:
                tot["relief_ticks"] += iv["relief_ticks"]
                tot["recovery_ticks"] += iv["recovery_ticks"]
                tot["shortfall_ticks"] += iv["shortfall_ticks"]
                tot["overdelivery_ticks"] += iv["overdelivery_ticks"]
            for k in ["bid_cost_cents", "credit_cents", "grant_pool_cents", "grant_funded_cents",
                      "grant_allocated_cents", "grant_unallocated_cents"]:
                tot[k] += e[k]
        dump(os.path.join(out, "region_%s.json" % rg), {"region": rg, "events": evs, "totals": tot})
        for k in tot_keys:
            if k != "event_count":
                summary[k] += tot[k]
        summary["regions"][rg] = {
            "selected_offer_count": tot["selected_offer_count"],
            "relief_ticks": tot["relief_ticks"],
            "bid_cost_cents": tot["bid_cost_cents"],
            "credit_cents": tot["credit_cents"],
            "grant_allocated_cents": tot["grant_allocated_cents"],
        }

    for sg in segments:
        ers = []
        tot = {"selected_offer_count": 0, "relief_ticks": 0, "recovery_ticks": 0,
               "bid_cost_cents": 0, "credit_cents": 0, "floor_ticks": 0}
        for eid in event_ids:
            for rg in regions:
                r = results[(eid, rg)]
                st = r["_seg"][sg]
                flt = r["_fl"][sg][0]
                if flt == 0:
                    bp = 10000
                else:
                    bp = min(10000, rhu(10000 * st["rel"], flt))
                ers.append({
                    "event_id": eid,
                    "region": rg,
                    "selected_offer_ids": sorted(st["ids"]),
                    "relief_ticks": st["rel"],
                    "recovery_ticks": st["rec"],
                    "bid_cost_cents": st["bid"],
                    "credit_cents": st["credit"],
                    "floor_ticks": flt,
                    "floor_attainment_bp": bp,
                })
                tot["selected_offer_count"] += len(st["ids"])
                tot["relief_ticks"] += st["rel"]
                tot["recovery_ticks"] += st["rec"]
                tot["bid_cost_cents"] += st["bid"]
                tot["credit_cents"] += st["credit"]
                tot["floor_ticks"] += flt
        dump(os.path.join(out, "segment_%s.json" % sg), {"segment": sg, "event_regions": ers, "totals": tot})
        summary["segments"][sg] = {
            "selected_offer_count": tot["selected_offer_count"],
            "relief_ticks": tot["relief_ticks"],
            "bid_cost_cents": tot["bid_cost_cents"],
            "credit_cents": tot["credit_cents"],
        }

    dump(os.path.join(out, "summary.json"), summary)

    cc_all = {lab: 0 for lab in LABELS}
    labels = []
    for key in sorted(sites):
        s = sites[key]
        cc_all[s["label"]] += 1
        labels.append({"event_id": key[0], "site_id": key[1], "label": s["label"]})
    tie_decisions.sort(key=lambda d: (d["event_id"], d["region"]))
    dump(os.path.join(out, "policy_audit.json"), {
        "compliance_counts": cc_all,
        "site_labels": labels,
        "tie_decisions": tie_decisions,
        "cap_binding_count": cap_binding,
        "residual_cents": residual_total,
        "residual_tie_pool_count": residual_tie_pools,
    })

    dump(os.path.join(out, "data_quality.json"), {
        "rows": rows,
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
        "unallocated_pool_count": unalloc_pools,
    })


if __name__ == "__main__":
    main()
