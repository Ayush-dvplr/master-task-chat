#!/usr/bin/env python3
"""Outage season replan (prototype of the reference program).

python3 solve_proto.py --data <data dir> --out <out dir>
"""
import argparse
import csv
import json
import os
import re
import sys
import tomllib

H = 91
DEF = H + 1
REGIONS = ("North", "South", "West", "East")
TYPES = ("line", "substation", "protection")
REASONS = ("unknown_asset", "out_of_season", "window_too_short", "duplicate_request")


class InputError(Exception):
    pass


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise InputError("%s: %s" % (os.path.basename(path), exc)) from exc


def load_lines(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().splitlines()
    except OSError as exc:
        raise InputError("%s: %s" % (os.path.basename(path), exc)) from exc


def read_inputs(data):
    p = lambda name: os.path.join(data, name)
    inp = {}
    assets = {}
    for n, line in enumerate(load_lines(p("assets.jsonl")), 1):
        if not line.strip():
            continue
        try:
            a = json.loads(line)
            assets[a["asset_id"]] = (a["region"], a["crew_type"])
        except (ValueError, KeyError) as exc:
            raise InputError("assets.jsonl line %d: %s" % (n, exc)) from exc
    inp["assets"] = assets
    inp["requests"] = load_json(p("requests.json"))["requests"]
    inp["plan"] = load_json(p("published_plan.json"))
    inp["network"] = load_json(p("network_constraints.json"))
    inp["calendar"] = load_json(p("region_calendar.json"))
    try:
        with open(p("risk_policy.toml"), "rb") as fh:
            inp["policy"] = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise InputError("risk_policy.toml: %s" % exc) from exc
    try:
        with open(p("customers.csv"), encoding="utf-8", newline="") as fh:
            inp["customers"] = list(csv.DictReader(fh))
    except OSError as exc:
        raise InputError("customers.csv: %s" % exc) from exc
    peak = {}
    for n, line in enumerate(load_lines(p("load_forecast.tsv"))[1:], 2):
        parts = line.split("\t")
        if len(parts) != 4:
            raise InputError("load_forecast.tsv line %d: expected 4 fields" % n)
        key = (parts[0], int(parts[1]))
        peak[key] = max(peak.get(key, 0), int(parts[3]))
    inp["peak"] = peak
    duty = {}
    for n, line in enumerate(load_lines(p("crew_roster.jsonl")), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        if r["status"] == "on_duty":
            k = (r["region"], r["crew_type"], r["day"])
            duty[k] = duty.get(k, 0) + 1
    inp["duty"] = duty
    inp["log"] = load_lines(p("control_room.log"))
    return inp


EVENT_KEYS = {
    "CREW_LOSS": ("region", "crew_type", "from", "to", "count"),
    "NEW_REQUEST": ("asset_id", "duration_days", "earliest_start", "latest_finish", "crews"),
    "WITHDRAW": ("asset_id",),
}
INT_KEYS = {"from", "to", "count", "duration_days", "earliest_start", "latest_finish", "crews"}
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def parse_event(line):
    """Return (ts, event, fields) for a well-formed event line, ('HB',) for a heartbeat, None otherwise."""
    parts = line.split()
    if len(parts) < 3 or not TS_RE.match(parts[0]):
        return None
    if parts[2] == "HEARTBEAT":
        return ("HB",)
    keys = EVENT_KEYS.get(parts[2])
    if keys is None:
        return None
    fields = {}
    for tok in parts[3:]:
        k, sep, v = tok.partition("=")
        if not sep or k in fields:
            return None
        fields[k] = v
    if set(fields) != set(keys):
        return None
    for k in keys:
        if k in INT_KEYS:
            if not re.fullmatch(r"-?\d+", fields[k]):
                return None
            fields[k] = int(fields[k])
    if parts[2] == "CREW_LOSS":
        if fields["region"] not in REGIONS or fields["crew_type"] not in TYPES:
            return None
        if fields["from"] > fields["to"] or fields["count"] < 1:
            return None
    return (parts[0], parts[2], fields)


def check_record(rec, assets, accepted):
    if rec["asset_id"] not in assets:
        return "unknown_asset"
    if rec["earliest_start"] < 1 or rec["latest_finish"] > H:
        return "out_of_season"
    if rec["latest_finish"] - rec["earliest_start"] + 1 < rec["duration_days"]:
        return "window_too_short"
    if rec["asset_id"] in accepted:
        return "duplicate_request"
    return None


def build_season(inp):
    assets = inp["assets"]
    rejected = []
    accepted = {}  # asset_id -> record (origin kept)
    for pos, rec in enumerate(inp["requests"]):
        why = check_record(rec, assets, accepted)
        if why:
            rejected.append({"source": "requests.json", "position": pos, "asset_id": rec["asset_id"], "reason": why})
        else:
            accepted[rec["asset_id"]] = dict(rec, origin="published")
    pub_at = inp["plan"]["published_at"]
    loss = {}
    withdrawn = []
    active = set(accepted)
    ignored = 0
    for n, line in enumerate(inp["log"], 1):
        ev = parse_event(line)
        if ev is None:
            ignored += 1
            continue
        if ev[0] == "HB" or ev[0] <= pub_at:
            continue
        _, kind, f = ev
        if kind == "CREW_LOSS":
            for d in range(max(1, f["from"]), min(H, f["to"]) + 1):
                k = (f["region"], f["crew_type"], d)
                loss[k] = loss.get(k, 0) + f["count"]
        elif kind == "NEW_REQUEST":
            why = check_record(f, assets, accepted)
            if why:
                rejected.append({"source": "control_room.log", "position": n, "asset_id": f["asset_id"], "reason": why})
            else:
                accepted[f["asset_id"]] = dict(f, origin="control_room")
                active.add(f["asset_id"])
        else:
            if f["asset_id"] in active:
                active.discard(f["asset_id"])
                withdrawn.append(f["asset_id"])
            else:
                ignored += 1
    pol = inp["policy"]
    cw = pol["class_weight"]
    bands = sorted(pol["load_band"]["bands"], key=lambda b: b["min_mw"])
    defer_factor = pol["deferral"]["defer_factor"]
    counts = {}
    for row in inp["customers"]:
        k = (row["asset_id"], row["class"])
        counts[k] = counts.get(k, 0) + 1
    factor = {}
    for (R, d), pk in inp["peak"].items():
        fv = None
        for b in bands:
            if pk >= b["min_mw"]:
                fv = b["factor"]
        factor[(R, d)] = fv
    plan = {}
    for x in inp["plan"]["plan"]:
        plan[x["asset_id"]] = x["start"] if x["status"] == "scheduled" else DEF
    reqs = []
    for aid in sorted(active):
        rec = accepted[aid]
        R, T = assets[aid]
        wc = counts.get((aid, "commercial"), 0) * cw["commercial"]
        wp = counts.get((aid, "public"), 0) * cw["public"]
        pub = plan.get(aid) if rec["origin"] == "published" else None
        reqs.append(dict(id=aid, region=R, type=T, origin=rec["origin"], crews=rec["crews"], dur=rec["duration_days"],
                         e=rec["earliest_start"], l=rec["latest_finish"], wc=wc, wp=wp, w=wc + wp, pub=pub))
    ids = {r["id"] for r in reqs}
    inc = [(a, b) for a, b in inp["network"]["incompatible"] if a in ids and b in ids]
    prec = [(x["before"], x["after"]) for x in inp["network"]["precedence"] if x["before"] in ids and x["after"] in ids]
    cap = {}
    for R in REGIONS:
        for T in TYPES:
            cap[(R, T)] = [0] + [max(0, inp["duty"].get((R, T, d), 0) - loss.get((R, T, d), 0)) for d in range(1, H + 1)] + [0]
    fac = {R: [0] + [factor[(R, d)] for d in range(1, H + 1)] + [0] for R in REGIONS}
    black = {R: set(inp["calendar"][R]["blackout_days"]) for R in REGIONS}
    return dict(reqs=reqs, inc=inc, prec=prec, cap=cap, fac=fac, black=black, defer=defer_factor,
                rejected=rejected, withdrawn=sorted(withdrawn), ignored=ignored)


def solve_lane(rs, inc, prec, cap, fac, black, defer):
    """Exact lexicographic optimum for one region and crew type: day sweep carrying the best
    (risk, moved, start list) per state. Paths reaching one state have decided the same requests."""
    n = len(rs)
    idx = {r["id"]: k for k, r in enumerate(rs)}
    inc_of = [set() for _ in range(n)]
    for a, b in inc:
        inc_of[idx[a]].add(idx[b])
        inc_of[idx[b]].add(idx[a])
    preds = [[] for _ in range(n)]
    is_pred = set()
    for a, b in prec:
        preds[idx[b]].append(idx[a])
        is_pred.add(idx[a])
    cost = []
    for r in rs:
        c = {}
        for s in range(r["e"], r["l"] - r["dur"] + 2):
            if s not in black and all(cap[x] >= r["crews"] for x in range(s, s + r["dur"])):
                c[s] = r["w"] * sum(fac[s:s + r["dur"]])
        c[DEF] = r["w"] * r["dur"] * defer
        cost.append(c)

    def moved(k, s):
        p = rs[k]["pub"]
        return 0 if p is None or p == s else 1

    arrive = [[] for _ in range(H + 2)]
    expire = [[] for _ in range(H + 2)]
    for k, r in enumerate(rs):
        arrive[r["e"]].append(k)
        expire[r["l"] - r["dur"] + 1].append(k)
    best = {(frozenset(), (), frozenset()): (0, 0, (0,) * n)}
    for d in range(1, H + 1):
        nxt = {}
        for (pend, run, dset), (cv, mv, vec) in best.items():
            pend = pend | frozenset(arrive[d])
            run = tuple(x for x in run if x[0] >= d)
            running = {k for _, k in run}
            elig = []
            if d not in black:
                for k in sorted(pend):
                    if d not in cost[k]:
                        continue
                    if any(p in pend or p in dset or p in running or rs[p]["e"] >= d for p in preds[k]):
                        continue
                    if inc_of[k] & running:
                        continue
                    elig.append(k)
            use = [0] * (H + 7)
            for e, k in run:
                for x in range(d, e + 1):
                    use[x] += rs[k]["crews"]
            out = []

            def grow(j, chosen):
                if j == len(elig):
                    out.append(tuple(chosen))
                    return
                grow(j + 1, chosen)
                k = elig[j]
                r = rs[k]
                if inc_of[k] & set(chosen):
                    return
                if any(use[x] + r["crews"] > cap[x] for x in range(d, d + r["dur"])):
                    return
                for x in range(d, d + r["dur"]):
                    use[x] += r["crews"]
                chosen.append(k)
                grow(j + 1, chosen)
                chosen.pop()
                for x in range(d, d + r["dur"]):
                    use[x] -= r["crews"]

            grow(0, [])
            for S in out:
                c2, m2, v2 = cv, mv, list(vec)
                for k in S:
                    c2 += cost[k][d]
                    m2 += moved(k, d)
                    v2[k] = d
                p2 = pend.difference(S)
                gone = [k for k in expire[d] if k in p2]
                for k in gone:
                    c2 += cost[k][DEF]
                    m2 += moved(k, DEF)
                    v2[k] = DEF
                p2 = p2.difference(gone)
                d2 = dset | frozenset(k for k in gone if k in is_pred)
                r2 = [x for x in run if x[0] > d] + [(d + rs[k]["dur"] - 1, k) for k in S if rs[k]["dur"] > 1]
                key = (p2, tuple(sorted(r2)), d2)
                val = (c2, m2, tuple(v2))
                if key not in nxt or val < nxt[key]:
                    nxt[key] = val
        best = nxt
    fin = [v for k, v in best.items() if not k[0]]
    return min(fin)[2]


def reason_of(k, plan, rs, cost_ok, preds):
    if not cost_ok[k]:
        return "no_feasible_start"
    if any(plan[p] == DEF for p in preds[k]):
        return "predecessor_deferred"
    return "displaced"


def derive(inp):
    S = build_season(inp)
    reqs = S["reqs"]
    lanes = {}
    for r in reqs:
        lanes.setdefault((r["region"], r["type"]), []).append(r)
    start = {}
    for (R, T), rs in lanes.items():
        ids = {r["id"] for r in rs}
        inc = [x for x in S["inc"] if x[0] in ids and x[1] in ids]
        prec = [x for x in S["prec"] if x[0] in ids and x[1] in ids]
        vec = solve_lane(rs, inc, prec, S["cap"][(R, T)], S["fac"][R], S["black"][R], S["defer"])
        for r, s in zip(rs, vec):
            start[r["id"]] = s
    preds = {}
    for a, b in S["prec"]:
        preds.setdefault(b, []).append(a)
    audit = []
    for r in reqs:
        s = start[r["id"]]
        fs = S["fac"][r["region"]]
        capl = S["cap"][(r["region"], r["type"])]
        blk = S["black"][r["region"]]
        has_start = any(x not in blk and all(capl[y] >= r["crews"] for y in range(x, x + r["dur"]))
                        for x in range(r["e"], r["l"] - r["dur"] + 2))
        if s == DEF:
            days = r["dur"] * S["defer"]
            if not has_start:
                why = "no_feasible_start"
            elif any(start.get(p) == DEF for p in preds.get(r["id"], [])):
                why = "predecessor_deferred"
            else:
                why = "displaced"
        else:
            days = sum(fs[s:s + r["dur"]])
            why = None
        pub = r["pub"]
        audit.append(dict(
            asset_id=r["id"], region=r["region"], crew_type=r["type"], origin=r["origin"],
            status="deferred" if s == DEF else "scheduled",
            start=None if s == DEF else s, end=None if s == DEF else s + r["dur"] - 1,
            published_start=pub if pub is not None and pub != DEF else None,
            moved=pub is not None and pub != s, risk_days=r["w"] * days, reason=why,
            _wc=r["wc"] * days, _wp=r["wp"] * days, _crew_days=0 if s == DEF else r["crews"] * r["dur"]))
    return S, audit


def write_outputs(S, audit, out):
    os.makedirs(out, exist_ok=True)

    def dump(name, obj):
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True)
            fh.write("\n")

    dump("policy_audit.json", {"requests": [{k: v for k, v in a.items() if not k.startswith("_")} for a in audit]})
    for R in REGIONS:
        rows = [a for a in audit if a["region"] == R]
        dump("region_%s.json" % R, {
            "region": R,
            "schedule": [{"asset_id": a["asset_id"], "crew_type": a["crew_type"], "start": a["start"], "end": a["end"]}
                         for a in sorted(rows, key=lambda a: (a["start"] or 0, a["asset_id"])) if a["status"] == "scheduled"],
            "crew_days": {T: sum(a["_crew_days"] for a in rows if a["crew_type"] == T) for T in TYPES},
            "risk_days": sum(a["risk_days"] for a in rows),
            "deferred": [a["asset_id"] for a in rows if a["status"] == "deferred"],
            "moved": sum(1 for a in rows if a["moved"]),
        })
    for seg, key in (("commercial", "_wc"), ("public", "_wp")):
        dump("segment_%s.json" % seg, {
            "segment": seg,
            "risk_days": sum(a[key] for a in audit),
            "by_region": {R: sum(a[key] for a in audit if a["region"] == R) for R in REGIONS},
            "deferred_risk_days": sum(a[key] for a in audit if a["status"] == "deferred"),
        })
    risk = sum(a["risk_days"] for a in audit)
    moved = sum(1 for a in audit if a["moved"])
    dump("summary.json", {
        "requests": len(audit),
        "scheduled": sum(1 for a in audit if a["status"] == "scheduled"),
        "deferred": sum(1 for a in audit if a["status"] == "deferred"),
        "moved": moved, "risk_days": risk,
        "crew_days": sum(a["_crew_days"] for a in audit),
        "objective": [risk, moved],
    })
    rej = sorted(S["rejected"], key=lambda x: (x["source"], x["position"]))
    dump("data_quality.json", {
        "rejected": rej,
        "counts": {k: sum(1 for x in rej if x["reason"] == k) for k in REASONS},
        "withdrawn": S["withdrawn"],
        "ignored_lines": S["ignored"],
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    try:
        inp = read_inputs(a.data)
        S, audit = derive(inp)
    except InputError as exc:
        print("error: %s" % exc, file=sys.stderr)
        sys.exit(2)
    write_outputs(S, audit, a.out)


if __name__ == "__main__":
    main()
