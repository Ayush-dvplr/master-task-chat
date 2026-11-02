#!/usr/bin/env python3
"""Harbourline PM2.5 monthly report derivation.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""
import bisect
import csv
import datetime
import json
import os
import sys
from decimal import Decimal
from fractions import Fraction

REPORT_NAMES = [
    "summary.json", "policy_audit.json", "data_quality.json",
    "region_North.json", "region_South.json", "region_West.json", "region_East.json",
    "segment_commercial.json", "segment_public.json",
]
DISTRICTS = ["North", "South", "West", "East"]
OPERATOR_CLASSES = ["commercial", "public"]
MAX_OFFSET = 19


def tmin(s):
    s = s.strip()
    d = datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    return d.toordinal() * 1440 + int(s[11:13]) * 60 + int(s[14:16])


def read_text(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return fh.read()


def read_json(path):
    return json.loads(read_text(path))


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.reader(fh)]
    rows = [r for r in rows if r]
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        r = list(r) + [""] * (len(header) - len(r))
        out.append(dict(zip(header, r)))
    return out


def norm_channel(c):
    return c.strip().upper()


def site_num(sid):
    try:
        return (0, int(sid[1:]), sid)
    except ValueError:
        return (1, 0, sid)


def entry_num(eid):
    try:
        return int(eid.strip()[1:])
    except ValueError:
        return -1


def tenths_from_decimal_text(text):
    v = Decimal(str(text).strip()) * 10
    return int(v.to_integral_value())


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    P = lambda name: os.path.join(data_dir, name)
    listing = sorted(os.listdir(data_dir))

    manifest = read_json(P("extract_manifest.json"))
    first_day = str(manifest["first_day"]).strip()
    days = int(manifest["days"])
    first_ord = datetime.date(int(first_day[0:4]), int(first_day[5:7]), int(first_day[8:10])).toordinal()
    last_ord_excl = first_ord + days
    pol_rev = str(manifest["policy_revision"])
    span_rev = str(manifest["span_register_revision"])

    # ---- policy in force
    policy = None
    for name in listing:
        if name.startswith("network_policy") and name.endswith(".json"):
            obj = read_json(P(name))
            if isinstance(obj, dict) and str(obj.get("revision")) == pol_rev:
                policy = obj
                break
    if policy is None:
        raise SystemExit("no network policy with revision %r" % pol_rev)
    std_tenths = tenths_from_decimal_text(policy["daily_standard"])
    hour_min = int(policy["hour_min_readings"])
    day_min = int(policy["day_min_hours"])
    pct = int(policy["site_min_valid_day_percent"])
    required_days = -((-days * pct) // 100)

    # ---- zone rules
    zone = read_json(P("zone_rules.json"))
    std_off = int(zone["standard_offset_minutes"])
    dst = [(tmin(p["begins"]), tmin(p["ends"]), int(p["shift_minutes"])) for p in zone.get("daylight_saving") or []]

    def civil_to_utc(c):
        for b, e, sh in dst:
            if b <= c < e:
                return c - std_off - sh
        return c - std_off

    # ---- sites
    sites = read_csv(P("site_register.csv"))
    site_info = {}
    for r in sites:
        site_info[r["site_id"]] = r
    site_ids = sorted(site_info, key=site_num)

    # ---- maintenance
    mlog = read_json(P("maintenance_log.json"))
    basis = str(mlog.get("time_basis", "utc")).strip().lower()
    maint = {}
    for e in mlog.get("entries") or []:
        b, en = tmin(e["begins"]), tmin(e["ends"])
        if basis == "civil":
            b, en = civil_to_utc(b), civil_to_utc(en)
        maint.setdefault(e["site_id"], []).append((b, en))

    # ---- deployments
    deps = {}
    unit_channel = {}
    for r in read_csv(P("unit_deployments.csv")):
        u = r["unit_id"]
        inst = tmin(r["installed_utc"])
        rem = tmin(r["removed_utc"]) if r["removed_utc"].strip() else None
        deps.setdefault(u, []).append((inst, rem, r["site_id"]))
        if r["channel"].strip() and u not in unit_channel:
            unit_channel[u] = norm_channel(r["channel"])

    # ---- asset tags
    tags = {}
    for r in read_csv(P("asset_tags.csv")):
        vf = tmin(r["valid_from_utc"])
        vt = tmin(r["valid_to_utc"]) if r["valid_to_utc"].strip() else None
        tags.setdefault(r["asset_tag"], []).append((vf, vt, r["unit_id"]))

    def tag_unit(tag, t):
        for vf, vt, u in tags.get(tag, []):
            if vf <= t and (vt is None or t < vt):
                return u
        return None

    # ---- span register in force
    span_rows = None
    for name in listing:
        if name.startswith("span_register") and name.endswith(".csv"):
            rows = read_csv(P(name))
            if rows and all(r.get("revision", "") == span_rev for r in rows):
                span_rows = rows
                break
    if span_rows is None:
        for name in listing:
            if name.startswith("span_register") and name.endswith(".csv"):
                rows = [r for r in read_csv(P(name)) if r.get("revision", "") == span_rev]
                if rows:
                    span_rows = rows
                    break
    if span_rows is None:
        span_rows = []
    entries = {}
    for r in span_rows:
        entries[r["entry_id"].strip()] = r
    void = set()
    for eid, r in entries.items():
        if r["action"].strip() == "withdraw":
            t = r["target_entry"].strip()
            if t in entries and entries[t]["action"].strip() in ("set", "amend"):
                void.add(t)
    amend_best = {}
    for eid, r in entries.items():
        if r["action"].strip() == "amend" and eid not in void:
            t = r["target_entry"].strip()
            if t in entries and entries[t]["action"].strip() == "set":
                cur = amend_best.get(t)
                if cur is None or entry_num(eid) > entry_num(cur):
                    amend_best[t] = eid
    unit_spans = {}
    for eid, r in entries.items():
        if r["action"].strip() != "set" or eid in void:
            continue
        eff = tmin(r["effective_utc"])
        ref = r["unit_ref"].strip()
        if ref in tags:
            unit = tag_unit(ref, eff)
            if unit is None:
                continue
        else:
            unit = ref
        src = entries[amend_best[eid]] if eid in amend_best else r
        factor = Fraction(Decimal(src["span_factor"].strip()))
        unit_spans.setdefault(unit, []).append((eff, entry_num(eid), factor))
    span_eff = {}
    for u, lst in unit_spans.items():
        lst.sort(key=lambda x: (x[0], x[1]))
        span_eff[u] = [x[0] for x in lst]

    def factor_at(u, t):
        lst = unit_spans.get(u)
        if not lst:
            return None
        i = bisect.bisect_right(span_eff[u], t)
        if i == 0:
            return None
        return lst[i - 1][2]

    # ---- receipt journal
    journal_rows = read_csv(P("receipt_journal.csv"))
    journal = set()
    for r in journal_rows:
        journal.add((norm_channel(r["channel"]), tmin(r["received_utc"]), int(r["frame"].strip())))

    # ---- card readings
    card = read_csv(P("card_readings.csv"))
    by_unit = {}
    parsed = []
    for r in card:
        u = r["unit_id"]
        rec = (u, tmin(r["card_stamp"]), int(r["frame"].strip()), r["pm25_raw"].strip(), r["status"].strip())
        parsed.append(rec)
        by_unit.setdefault(u, []).append(rec)

    # ---- clock offsets from the journal
    offsets = {}
    received = {}
    for u in sorted(by_unit):
        ch = unit_channel.get(u)
        best = (0, 0)
        best_count = -1
        for o in range(-MAX_OFFSET, MAX_OFFSET + 1):
            if ch is None:
                cnt = 0
            else:
                cnt = 0
                for rec in by_unit[u]:
                    if (ch, rec[1] - o, rec[2]) in journal:
                        cnt += 1
            key = (cnt, -abs(o), -o)
            if best_count < 0 or key > (best_count, -abs(best[0]), -best[0]):
                best = (o, cnt)
                best_count = cnt
        offsets[u] = best[0]
        received[u] = best[1]

    # ---- classify readings
    excl = {"outside_window": 0, "undeployed": 0, "missing_value": 0, "flagged": 0,
            "uncalibrated": 0, "maintenance": 0}
    excluded = 0
    valid_total = 0
    site_valid = {}
    hour_vals = {}  # (site, hour_start_local) -> list of corrected
    for u, stamp, frame, raw, status in parsed:
        t = stamp - offsets[u]
        local = t + std_off
        hour_start = ((local - 1) // 60) * 60
        day = hour_start // 1440
        if not (first_ord <= day < last_ord_excl):
            excl["outside_window"] += 1
            excluded += 1
            continue
        site = None
        for inst, rem, s in deps.get(u, []):
            if inst <= t and (rem is None or t < rem):
                site = s
                break
        factor = factor_at(u, t)
        bad = False
        if site is None:
            excl["undeployed"] += 1
            bad = True
        if raw == "":
            excl["missing_value"] += 1
            bad = True
        if status != "":
            excl["flagged"] += 1
            bad = True
        if factor is None:
            excl["uncalibrated"] += 1
            bad = True
        if site is not None:
            for b, e in maint.get(site, []):
                if b <= t < e:
                    excl["maintenance"] += 1
                    bad = True
                    break
        if bad:
            excluded += 1
            continue
        prod = int(raw) * factor
        corr = (2 * prod.numerator + prod.denominator) // (2 * prod.denominator)
        valid_total += 1
        site_valid[site] = site_valid.get(site, 0) + 1
        hour_vals.setdefault((site, hour_start), []).append(corr)

    # ---- hours and days
    day_hours = {}  # (site, day) -> list of hourly values
    valid_hours_total = 0
    for (site, hs), vals in hour_vals.items():
        if len(vals) >= hour_min:
            hv = sum(vals) // len(vals)
            valid_hours_total += 1
            day_hours.setdefault((site, hs // 1440), []).append(hv)
    all_sites = set(site_info) | set(site_valid)
    site_days = {s: {} for s in all_sites}
    site_complete = {s: 0 for s in all_sites}
    for (site, d), hvs in day_hours.items():
        mean = sum(hvs) // len(hvs)
        if len(hvs) >= day_min:
            site_days[site][d] = mean
            site_complete[site] += 1
        elif mean > std_tenths:
            site_days[site][d] = mean

    site_res = {}
    for s in all_sites:
        dv = site_days[s]
        n = len(dv)
        exc = sum(1 for v in dv.values() if v > std_tenths)
        if n:
            rank = -(-n // 50)
            design = sorted(dv.values(), reverse=True)[rank - 1]
        else:
            rank = None
            design = None
        if design is not None and design > std_tenths:
            status = "nonattainment"
        elif n >= required_days:
            status = "attainment"
        else:
            status = "incomplete"
        site_res[s] = {"valid_days": n, "complete_days": site_complete[s], "exceedance_days": exc,
                       "design_rank": rank, "design_value": design, "status": status,
                       "valid_readings": site_valid.get(s, 0)}

    def worst(group):
        best = None
        for s in sorted(group, key=site_num):
            v = site_res[s]["design_value"]
            if v is None:
                continue
            if best is None or v > site_res[best]["design_value"]:
                best = s
        return best

    def rollup(key, value, members):
        members = sorted(members, key=site_num)
        in_scope = any(site_res[s]["status"] != "incomplete" for s in members)
        if not in_scope:
            return {key: value, "in_scope": False}, False, 0
        w = worst(members)
        rep = {
            key: value,
            "in_scope": True,
            "sites": [{
                "site_id": s,
                "status": site_res[s]["status"],
                "valid_readings": site_res[s]["valid_readings"],
                "daily_values": {datetime.date.fromordinal(d).isoformat(): v
                                 for d, v in sorted(site_days[s].items())},
            } for s in members],
            "valid_readings": sum(site_res[s]["valid_readings"] for s in members),
            "exceedance_days": sum(site_res[s]["exceedance_days"] for s in members),
            "worst_site": None if w is None else {"site_id": w, "design_value": site_res[w]["design_value"]},
            "status": "nonattainment" if any(site_res[s]["status"] == "nonattainment" for s in members)
            else "attainment",
        }
        return rep, True, rep["valid_readings"]

    reports = {}
    rolled_up = 0
    for d in DISTRICTS:
        members = [s for s in site_ids if site_info[s]["district"] == d]
        rep, _, vr = rollup("district", d, members)
        rolled_up += vr
        reports["region_%s.json" % d] = rep
    for oc in OPERATOR_CLASSES:
        members = [s for s in site_ids if site_info[s]["operator_class"] == oc]
        rep, _, _ = rollup("operator_class", oc, members)
        reports["segment_%s.json" % oc] = rep

    counts = {"attainment": 0, "incomplete": 0, "nonattainment": 0}
    for s in site_ids:
        counts[site_res[s]["status"]] += 1
    w = worst(site_ids)
    reports["summary.json"] = {
        "report_id": manifest["report_id"],
        "first_day": manifest["first_day"],
        "days": days,
        "card_rows": len(card),
        "valid_readings": valid_total,
        "valid_hours": valid_hours_total,
        "valid_days": sum(r["valid_days"] for r in site_res.values()),
        "exceedance_days": sum(r["exceedance_days"] for r in site_res.values()),
        "site_status_counts": counts,
        "highest_design_value": {"site_id": w, "value": None if w is None else site_res[w]["design_value"]},
        "reconciliation": {
            "card_rows": len(card),
            "excluded_readings": excluded,
            "valid_readings": valid_total,
            "rolled_up_valid_readings": rolled_up,
            "residual": valid_total - rolled_up,
        },
    }
    reports["policy_audit.json"] = {
        "policy_revision": str(policy["revision"]),
        "span_register_revision": span_rev,
        "daily_standard_tenths": std_tenths,
        "hour_min_readings": hour_min,
        "day_min_hours": day_min,
        "required_valid_days": required_days,
        "sites": [{
            "site_id": s,
            "district": site_info[s]["district"],
            "operator_class": site_info[s]["operator_class"],
            "valid_days": site_res[s]["valid_days"],
            "complete_days": site_res[s]["complete_days"],
            "exceedance_days": site_res[s]["exceedance_days"],
            "design_rank": site_res[s]["design_rank"],
            "design_value": site_res[s]["design_value"],
            "status": site_res[s]["status"],
        } for s in site_ids],
    }
    reports["data_quality.json"] = {
        "journal_entries": len(journal_rows),
        "excluded_readings": excluded,
        "exclusions": excl,
        "units": [{
            "unit_id": u,
            "channel": unit_channel.get(u, ""),
            "card_rows": len(by_unit[u]),
            "received_packets": received[u],
        } for u in sorted(by_unit)],
    }

    os.makedirs(out_dir, exist_ok=True)
    for name in REPORT_NAMES:
        data = (json.dumps(reports[name], sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(data)
        sys.stdout.write("%s %d\n" % (name, len(data)))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
