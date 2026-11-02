#!/usr/bin/env python3
"""Replan the maintenance outage season and publish the replan documents.

Usage: python3 derive_report.py --data <data dir> --out <out dir>
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone

REGIONS = ["North", "South", "West", "East"]
CREW_TYPES = ["line", "substation", "protection"]
REASONS = ["unknown_asset", "out_of_season", "window_too_short", "duplicate_request"]
TS_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
INT_RE = re.compile(r"^-?[0-9]+$")
EVENT_KEYS = {
    "CREW_LOSS": {"region": False, "crew_type": False, "from": True, "to": True, "count": True},
    "NEW_REQUEST": {"asset_id": False, "duration_days": True, "earliest_start": True,
                    "latest_finish": True, "crews": True},
    "WITHDRAW": {"asset_id": False},
}
INF_START = float("inf")


class InputError(Exception):
    pass


# ---------------------------------------------------------------- reading

def path_of(data_dir, name):
    return os.path.join(data_dir, name)


def read_text(data_dir, name):
    p = path_of(data_dir, name)
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError("cannot read %s: %s" % (name, exc))


def read_json(data_dir, name):
    txt = read_text(data_dir, name)
    try:
        return json.loads(txt)
    except ValueError as exc:
        raise InputError("cannot parse %s: %s" % (name, exc))


def read_jsonl(data_dir, name):
    out = []
    for i, line in enumerate(read_text(data_dir, name).splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError as exc:
            raise InputError("cannot parse %s line %d: %s" % (name, i, exc))
    return out


def _toml_value(s):
    s = s.strip()
    if s.startswith("["):
        inner = s[1:-1]
        items, depth, cur = [], 0, ""
        for ch in inner:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            if ch == "," and depth == 0:
                if cur.strip():
                    items.append(_toml_value(cur))
                cur = ""
            else:
                cur += ch
        if cur.strip():
            items.append(_toml_value(cur))
        return items
    if s.startswith("{"):
        inner = s[1:-1]
        d, depth, cur, parts = {}, 0, "", []
        for ch in inner:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        parts.append(cur)
        for part in parts:
            if part.strip():
                k, v = part.split("=", 1)
                d[k.strip().strip('"')] = _toml_value(v)
        return d
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    if s in ("true", "false"):
        return s == "true"
    try:
        return int(s.replace("_", ""))
    except ValueError:
        return float(s)


def _strip_comment(line):
    out, in_str = "", False
    for ch in line:
        if ch == '"':
            in_str = not in_str
        if ch == "#" and not in_str:
            break
        out += ch
    return out


def parse_toml_minimal(txt):
    root, table = {}, None
    table = root
    pending = None
    for raw in txt.splitlines():
        line = _strip_comment(raw).strip()
        if pending is not None:
            pending[1] += " " + line
            if pending[1].count("[") <= pending[1].count("]") and \
                    pending[1].count("{") <= pending[1].count("}"):
                table[pending[0]] = _toml_value(pending[1])
                pending = None
            continue
        if not line:
            continue
        if line.startswith("[") and line.endswith("]") and "=" not in line:
            table = root
            for part in line[1:-1].split("."):
                table = table.setdefault(part.strip().strip('"'), {})
            continue
        k, v = line.split("=", 1)
        k, v = k.strip().strip('"'), v.strip()
        if v.count("[") > v.count("]") or v.count("{") > v.count("}"):
            pending = [k, v]
        else:
            table[k] = _toml_value(v)
    return root


def read_toml(data_dir, name):
    txt = read_text(data_dir, name)
    try:
        import tomllib  # Python 3.11+
        try:
            return tomllib.loads(txt)
        except tomllib.TOMLDecodeError as exc:
            raise InputError("cannot parse %s: %s" % (name, exc))
    except ImportError:
        try:
            return parse_toml_minimal(txt)
        except (ValueError, IndexError) as exc:
            raise InputError("cannot parse %s: %s" % (name, exc))


def read_csv(data_dir, name, delimiter=","):
    txt = read_text(data_dir, name)
    return list(csv.DictReader(txt.splitlines(), delimiter=delimiter))


def canon_ts(ts):
    s = str(ts).strip()
    if TS_RE.match(s):
        return s
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return s
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- intake

def intake(data_dir):
    assets = {}
    for rec in read_jsonl(data_dir, "assets.jsonl"):
        assets[rec["asset_id"]] = rec
    reqdoc = read_json(data_dir, "requests.json")
    try:
        first_day = int(reqdoc["season"]["first_day"])
        last_day = int(reqdoc["season"]["last_day"])
        req_list = reqdoc["requests"]
    except (KeyError, TypeError, ValueError) as exc:
        raise InputError("cannot parse requests.json: %s" % exc)
    pubdoc = read_json(data_dir, "published_plan.json")
    try:
        published_at = canon_ts(pubdoc["published_at"])
        plan = {e["asset_id"]: e for e in pubdoc["plan"]}
    except (KeyError, TypeError) as exc:
        raise InputError("cannot parse published_plan.json: %s" % exc)
    log_text = read_text(data_dir, "control_room.log")

    accepted = {}          # asset_id -> request dict
    ever_accepted = set()
    withdrawn = []
    rejected = []

    def check(rec, source, position):
        aid = rec["asset_id"]
        if aid not in assets:
            reason = "unknown_asset"
        elif rec["earliest_start"] < first_day or rec["latest_finish"] > last_day:
            reason = "out_of_season"
        elif rec["latest_finish"] - rec["earliest_start"] + 1 < rec["duration_days"]:
            reason = "window_too_short"
        elif aid in ever_accepted:
            reason = "duplicate_request"
        else:
            reason = None
        if reason:
            rejected.append({"source": source, "position": position,
                             "asset_id": aid, "reason": reason})
            return
        ever_accepted.add(aid)
        a = assets[aid]
        accepted[aid] = {
            "asset_id": aid, "region": a["region"], "crew_type": a["crew_type"],
            "duration_days": rec["duration_days"], "earliest_start": rec["earliest_start"],
            "latest_finish": rec["latest_finish"], "crews": rec["crews"],
            "origin": "published" if source == "requests.json" else "control_room",
        }

    for i, rec in enumerate(req_list):
        try:
            r = {"asset_id": rec["asset_id"], "duration_days": int(rec["duration_days"]),
                 "earliest_start": int(rec["earliest_start"]),
                 "latest_finish": int(rec["latest_finish"]), "crews": int(rec["crews"])}
        except (KeyError, TypeError, ValueError) as exc:
            raise InputError("cannot parse requests.json record %d: %s" % (i, exc))
        check(r, "requests.json", i)

    losses = {}   # (region, crew_type, day) -> count
    ignored = 0
    for lineno, line in enumerate(log_text.splitlines(), 1):
        parts = line.split()
        ts_ok = len(parts) >= 1 and bool(TS_RE.match(parts[0]))
        if ts_ok and len(parts) >= 3 and parts[2] == "HEARTBEAT":
            continue
        ev = parse_event(parts) if ts_ok else None
        if ev is None:
            ignored += 1
            continue
        if parts[0] <= published_at:
            continue
        name, kv = ev
        if name == "CREW_LOSS":
            lo, hi = max(kv["from"], first_day), min(kv["to"], last_day)
            for d in range(lo, hi + 1):
                key = (kv["region"], kv["crew_type"], d)
                losses[key] = losses.get(key, 0) + kv["count"]
        elif name == "NEW_REQUEST":
            check(kv, "control_room.log", lineno)
        else:
            aid = kv["asset_id"]
            if aid in accepted:
                del accepted[aid]
                withdrawn.append(aid)
            else:
                ignored += 1

    return {
        "assets": assets, "first_day": first_day, "last_day": last_day,
        "plan": plan, "active": accepted, "withdrawn": sorted(set(withdrawn)),
        "rejected": rejected, "losses": losses, "ignored": ignored,
    }


def parse_event(parts):
    if len(parts) < 3:
        return None
    name = parts[2]
    spec = EVENT_KEYS.get(name)
    if spec is None:
        return None
    kv = {}
    for tok in parts[3:]:
        if "=" not in tok:
            return None
        k, v = tok.split("=", 1)
        if k in kv or k not in spec:
            return None
        kv[k] = v
    if set(kv) != set(spec):
        return None
    for k, is_int in spec.items():
        if is_int:
            if not INT_RE.match(kv[k]):
                return None
            kv[k] = int(kv[k])
    if name == "CREW_LOSS":
        if kv["region"] not in REGIONS or kv["crew_type"] not in CREW_TYPES:
            return None
        if kv["from"] > kv["to"] or kv["count"] < 1:
            return None
    return name, kv


# ---------------------------------------------------------------- model

def build_model(data_dir, st):
    first, last = st["first_day"], st["last_day"]
    policy = read_toml(data_dir, "risk_policy.toml")
    try:
        cw = policy["class_weight"]
        w_com, w_pub = cw["commercial"], cw["public"]
        bands = sorted(((b["min_mw"], b["factor"]) for b in policy["load_band"]["bands"]))
        defer_factor = policy["deferral"]["defer_factor"]
    except (KeyError, TypeError) as exc:
        raise InputError("cannot parse risk_policy.toml: %s" % exc)

    n_com, n_pub = {}, {}
    for row in read_csv(data_dir, "customers.csv"):
        cls, aid = (row.get("class") or "").strip(), (row.get("asset_id") or "").strip()
        if cls == "commercial":
            n_com[aid] = n_com.get(aid, 0) + 1
        elif cls == "public":
            n_pub[aid] = n_pub.get(aid, 0) + 1

    peak = {}
    for row in read_csv(data_dir, "load_forecast.tsv", delimiter="\t"):
        try:
            key = (row["region"].strip(), int(row["day"]))
            mw = float(row["load_mw"])
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise InputError("cannot parse load_forecast.tsv: %s" % exc)
        if key not in peak or mw > peak[key]:
            peak[key] = mw

    def factor(region, day):
        p = peak.get((region, day), 0)
        f = 0
        for mn, fc in bands:
            if mn <= p:
                f = fc
        return f

    # prefix sums of load factor per region over days 0..last
    pref = {}
    for rg in REGIONS:
        arr = [0] * (last + 2)
        for d in range(1, last + 1):
            arr[d] = arr[d - 1] + (factor(rg, d) if d >= first else 0)
        pref[rg] = arr

    on_duty = {}
    for rec in read_jsonl(data_dir, "crew_roster.jsonl"):
        if rec.get("status") == "on_duty":
            key = (rec.get("region"), rec.get("crew_type"), rec.get("day"))
            on_duty[key] = on_duty.get(key, 0) + 1
    cap = {}
    for rg in REGIONS:
        for ct in CREW_TYPES:
            arr = [0] * (last + 2)
            for d in range(first, last + 1):
                arr[d] = max(0, on_duty.get((rg, ct, d), 0) - st["losses"].get((rg, ct, d), 0))
            cap[(rg, ct)] = arr

    cal = read_json(data_dir, "region_calendar.json")
    blackout = {}
    for rg in REGIONS:
        entry = cal.get(rg) if isinstance(cal, dict) else None
        blackout[rg] = set(entry.get("blackout_days", [])) if isinstance(entry, dict) else set()

    net = read_json(data_dir, "network_constraints.json")
    incompatible = net.get("incompatible", []) if isinstance(net, dict) else []
    precedence = net.get("precedence", []) if isinstance(net, dict) else []

    return {
        "w_com": w_com, "w_pub": w_pub, "n_com": n_com, "n_pub": n_pub,
        "defer_factor": defer_factor, "pref": pref, "cap": cap, "blackout": blackout,
        "incompatible": incompatible, "precedence": precedence,
    }


# ---------------------------------------------------------------- solver

class Var:
    __slots__ = ("aid", "req", "group", "dur", "crews", "values", "by_cost",
                 "defer_cost", "incompat", "preds", "succs", "lo_day", "hi_day")


def solve(st, md):
    active = st["active"]
    aids = sorted(active)
    n = len(aids)
    big = n + 1
    plan = st["plan"]
    last = st["last_day"]

    weight, wc, wp = {}, {}, {}
    for aid in aids:
        wc[aid] = md["n_com"].get(aid, 0) * md["w_com"]
        wp[aid] = md["n_pub"].get(aid, 0) * md["w_pub"]
        weight[aid] = wc[aid] + wp[aid]

    def pub_start(aid):
        e = plan.get(aid) if active[aid]["origin"] == "published" else None
        if e is None:
            return None, False
        if e.get("status") == "scheduled":
            return e.get("start"), True
        return None, True

    def moved_of(aid, start):
        ps, in_plan = pub_start(aid)
        if not in_plan:
            return 0
        if ps is None:
            return 0 if start is None else 1
        return 0 if start == ps else 1

    def risk_sched(aid, s, w):
        r = active[aid]
        pr = md["pref"][r["region"]]
        e = s + r["duration_days"] - 1
        if e < s:
            return 0
        return w * (pr[e] - pr[s - 1])

    def risk_def(aid, w):
        return w * active[aid]["duration_days"] * md["defer_factor"]

    vars_ = {}
    for aid in aids:
        r = active[aid]
        v = Var()
        v.aid, v.req = aid, r
        v.group = (r["region"], r["crew_type"])
        v.dur, v.crews = r["duration_days"], r["crews"]
        capa = md["cap"][v.group]
        bl = md["blackout"][r["region"]]
        vals = []
        for s in range(r["earliest_start"], r["latest_finish"] - v.dur + 2):
            if s in bl:
                continue
            ok = True
            for d in range(s, s + v.dur):
                if d < 1 or d > last or capa[d] < v.crews:
                    ok = False
                    break
            if ok:
                vals.append((s, risk_sched(aid, s, weight[aid]) * big + moved_of(aid, s)))
        v.values = vals
        v.by_cost = sorted(vals, key=lambda x: (x[1], x[0]))
        v.defer_cost = risk_def(aid, weight[aid]) * big + moved_of(aid, None)
        v.incompat, v.preds, v.succs = set(), set(), set()
        if vals:
            v.lo_day = vals[0][0]
            v.hi_day = vals[-1][0] + v.dur - 1
        else:
            v.lo_day, v.hi_day = 0, -1
        vars_[aid] = v

    for a, b in md["incompatible"]:
        if a in vars_ and b in vars_ and a != b:
            vars_[a].incompat.add(b)
            vars_[b].incompat.add(a)
    for e in md["precedence"]:
        b, a = e.get("before"), e.get("after")
        if a in vars_ and b in vars_:
            vars_[a].preds.add(b)
            vars_[b].succs.add(a)

    # components
    parent = {aid: aid for aid in aids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)

    by_group = {}
    for aid in aids:
        by_group.setdefault(vars_[aid].group, []).append(aid)
    for g, members in by_group.items():
        capa = md["cap"][g]
        for d in range(1, last + 1):
            touching = [m for m in members
                        if any(s <= d <= s + vars_[m].dur - 1 for s, _ in vars_[m].values)]
            if len(touching) > 1 and sum(vars_[m].crews for m in touching) > capa[d]:
                for m in touching[1:]:
                    union(touching[0], m)
    for aid in aids:
        v = vars_[aid]
        for o in v.incompat:
            w = vars_[o]
            if v.values and w.values and v.lo_day <= w.hi_day and w.lo_day <= v.hi_day:
                union(aid, o)
        for o in v.preds:
            union(aid, o)

    comps = {}
    for aid in aids:
        comps.setdefault(find(aid), []).append(aid)

    start = {}
    for root in sorted(comps):
        members = sorted(comps[root])
        start.update(solve_component([vars_[m] for m in members], md["cap"], last))

    return start, vars_, weight, wc, wp, pub_start, moved_of, risk_sched, risk_def


def solve_component(cvars, cap, last):
    """Exact lexicographic optimum for one component.

    Variables are branched in ascending asset_id order and values in ascending
    start order with deferral last, so the first solution reached at a given
    cost is the lexicographically smallest start list among equal-cost ones.
    """
    if len(cvars) == 1 and not cvars[0].preds and not cvars[0].succs:
        v = cvars[0]
        best_val, best_cost = None, v.defer_cost
        for s, c in v.values:
            if c < best_cost:
                best_val, best_cost = s, c
        return {v.aid: best_val}

    k = len(cvars)
    idx = {v.aid: i for i, v in enumerate(cvars)}
    groups = sorted({v.group for v in cvars})
    used = {g: [0] * (last + 2) for g in groups}
    capg = {g: cap[g] for g in groups}
    assign = [None] * k          # None = unassigned, -1 = deferred, else start
    UNASSIGNED, DEFER = None, -1
    incompat_i = [[idx[o] for o in v.incompat if o in idx] for v in cvars]
    preds_i = [[idx[o] for o in v.preds if o in idx] for v in cvars]
    succs_i = [[idx[o] for o in v.succs if o in idx] for v in cvars]
    durs = [v.dur for v in cvars]

    def feasible(i, val):
        a = assign
        if val == DEFER:
            for j in succs_i[i]:
                if a[j] is not None and a[j] != DEFER:
                    return False
            return True
        v = cvars[i]
        e = val + v.dur - 1
        u, cp, cr = used[v.group], capg[v.group], v.crews
        for d in range(val, e + 1):
            if u[d] + cr > cp[d]:
                return False
        for j in incompat_i[i]:
            sj = a[j]
            if sj is not None and sj != DEFER:
                if sj <= e and val <= sj + durs[j] - 1:
                    return False
        for j in preds_i[i]:
            sj = a[j]
            if sj is not None:
                if sj == DEFER or val <= sj + durs[j] - 1:
                    return False
        for j in succs_i[i]:
            sj = a[j]
            if sj is not None and sj != DEFER and sj <= e:
                return False
        return True

    def place(i, val, sign):
        if val == DEFER:
            return
        v = cvars[i]
        u, cr = used[v.group], v.crews * sign
        for d in range(val, val + v.dur):
            u[d] += cr

    def min_cost(i):
        v = cvars[i]
        dc = v.defer_cost
        for s, c in v.by_cost:
            if c >= dc:
                break
            if feasible(i, s):
                return c
        if feasible(i, DEFER):
            return dc
        # deferral blocked by a scheduled successor; any scheduled value must do
        for s, c in v.by_cost:
            if feasible(i, s):
                return c
        return None

    # greedy seed (cost bound only; pruning against it is strict)
    seed_cost = 0
    seed_ok = True
    for i in range(k):
        best = None
        for s, c in cvars[i].by_cost:
            if c < cvars[i].defer_cost and feasible(i, s):
                best = (c, s)
                break
        if best is None:
            if feasible(i, DEFER):
                best = (cvars[i].defer_cost, DEFER)
            else:
                seed_ok = False
                break
        seed_cost += best[0]
        assign[i] = best[1]
        place(i, best[1], 1)
    for i in range(k):
        if assign[i] is not None:
            place(i, assign[i], -1)
            assign[i] = None

    state = {"best": seed_cost if seed_ok else float("inf"), "found": False, "sol": None}

    def lower_bound(i0):
        tot = 0
        for j in range(i0, k):
            c = min_cost(j)
            if c is None:
                return None
            tot += c
        return tot

    def dfs(i, cost):
        if i == k:
            if (not state["found"] and cost <= state["best"]) or cost < state["best"]:
                state["best"], state["found"] = cost, True
                state["sol"] = list(assign)
            return
        v = cvars[i]
        options = [(s, c) for s, c in v.values] + [(DEFER, v.defer_cost)]
        for val, c in options:
            if not feasible(i, val):
                continue
            assign[i] = val
            place(i, val, 1)
            lb = lower_bound(i + 1)
            if lb is not None:
                total = cost + c + lb
                if total < state["best"] or (not state["found"] and total <= state["best"]):
                    dfs(i + 1, cost + c)
            place(i, val, -1)
            assign[i] = None

    sys.setrecursionlimit(max(1000, 4 * k + 100))
    dfs(0, 0)
    if state["sol"] is None:
        raise RuntimeError("no feasible season found for component starting %s" % cvars[0].aid)
    return {v.aid: (None if state["sol"][i] == DEFER else state["sol"][i])
            for i, v in enumerate(cvars)}


# ---------------------------------------------------------------- reporting

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    try:
        st = intake(args.data)
        md = build_model(args.data, st)
    except InputError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        print("error: malformed input data: %r" % (exc,), file=sys.stderr)
        return 2

    start, vars_, weight, wc, wp, pub_start, moved_of, risk_sched, risk_def = solve(st, md)
    active = st["active"]
    aids = sorted(active)

    def risks(aid):
        s = start[aid]
        if s is None:
            return risk_def(aid, weight[aid]), risk_def(aid, wc[aid]), risk_def(aid, wp[aid])
        return (risk_sched(aid, s, weight[aid]), risk_sched(aid, s, wc[aid]),
                risk_sched(aid, s, wp[aid]))

    rows = []
    for aid in aids:
        r = active[aid]
        s = start[aid]
        ps, _ = pub_start(aid)
        rt, rc, rp = risks(aid)
        reason = None
        if s is None:
            if not vars_[aid].values:
                reason = "no_feasible_start"
            elif any(start[b] is None for b in vars_[aid].preds):
                reason = "predecessor_deferred"
            else:
                reason = "displaced"
        rows.append({
            "asset_id": aid, "region": r["region"], "crew_type": r["crew_type"],
            "origin": r["origin"], "status": "deferred" if s is None else "scheduled",
            "start": s, "end": None if s is None else s + r["duration_days"] - 1,
            "published_start": ps, "moved": bool(moved_of(aid, s)),
            "risk_days": rt, "reason": reason,
            "_rc": rc, "_rp": rp, "_cd": 0 if s is None else r["crews"] * r["duration_days"],
        })

    def clean(row):
        return {k: v for k, v in row.items() if not k.startswith("_")}

    docs = {"policy_audit.json": {"requests": [clean(x) for x in rows]}}

    for rg in REGIONS:
        rr = [x for x in rows if x["region"] == rg]
        sched = sorted((x for x in rr if x["status"] == "scheduled"),
                       key=lambda x: (x["start"], x["asset_id"]))
        docs["region_%s.json" % rg] = {
            "region": rg,
            "schedule": [{"asset_id": x["asset_id"], "crew_type": x["crew_type"],
                          "start": x["start"], "end": x["end"]} for x in sched],
            "crew_days": {ct: sum(x["_cd"] for x in rr if x["crew_type"] == ct)
                          for ct in CREW_TYPES},
            "risk_days": sum(x["risk_days"] for x in rr),
            "deferred": [x["asset_id"] for x in rr if x["status"] == "deferred"],
            "moved": sum(1 for x in rr if x["moved"]),
        }

    for seg, key in (("commercial", "_rc"), ("public", "_rp")):
        docs["segment_%s.json" % seg] = {
            "segment": seg,
            "risk_days": sum(x[key] for x in rows),
            "by_region": {rg: sum(x[key] for x in rows if x["region"] == rg) for rg in REGIONS},
            "deferred_risk_days": sum(x[key] for x in rows if x["status"] == "deferred"),
        }

    total_risk = sum(x["risk_days"] for x in rows)
    n_moved = sum(1 for x in rows if x["moved"])
    docs["summary.json"] = {
        "requests": len(rows),
        "scheduled": sum(1 for x in rows if x["status"] == "scheduled"),
        "deferred": sum(1 for x in rows if x["status"] == "deferred"),
        "moved": n_moved,
        "risk_days": total_risk,
        "crew_days": sum(x["_cd"] for x in rows),
        "objective": [total_risk, n_moved],
    }

    src_order = {"control_room.log": 0, "requests.json": 1}
    rej = sorted(st["rejected"], key=lambda x: (src_order[x["source"]], x["position"]))
    docs["data_quality.json"] = {
        "rejected": rej,
        "counts": {r: sum(1 for x in rej if x["reason"] == r) for r in REASONS},
        "withdrawn": st["withdrawn"],
        "ignored_lines": st["ignored"],
    }

    os.makedirs(args.out, exist_ok=True)
    for name, doc in docs.items():
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
