#!/usr/bin/env python3
"""Replan the maintenance outage season and publish the replan documents."""

import argparse
import csv
import json
import os
import re
import sys

REGIONS = ["North", "South", "West", "East"]
CREW_TYPES = ["line", "substation", "protection"]
REASONS = ["unknown_asset", "out_of_season", "window_too_short", "duplicate_request"]

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
INT_RE = re.compile(r"^-?\d+$")

EVENT_KEYS = {
    "CREW_LOSS": {"region", "crew_type", "from", "to", "count"},
    "NEW_REQUEST": {"asset_id", "duration_days", "earliest_start", "latest_finish", "crews"},
    "WITHDRAW": {"asset_id"},
}
EVENT_INT_KEYS = {
    "CREW_LOSS": {"from", "to", "count"},
    "NEW_REQUEST": {"duration_days", "earliest_start", "latest_finish", "crews"},
    "WITHDRAW": set(),
}


def die(path, detail=None):
    msg = "error: cannot read required file: %s" % path
    if detail:
        msg += " (%s)" % detail
    sys.stderr.write(msg + "\n")
    sys.exit(1)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        die(path, exc.strerror)


def load_json(path):
    text = read_text(path)
    try:
        return json.loads(text)
    except ValueError as exc:
        die(path, str(exc))


def load_jsonl(path):
    out = []
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError as exc:
            die(path, str(exc))
    return out


def load_toml(path):
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        die(path, exc.strerror)
    try:
        import tomllib
    except ImportError:
        return parse_toml_text(raw.decode("utf-8"), path)
    try:
        return tomllib.loads(raw.decode("utf-8"))
    except Exception as exc:
        die(path, str(exc))


def _toml_scalar(text):
    text = text.strip()
    if INT_RE.match(text):
        return int(text)
    if text[:1] in ('"', "'"):
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    try:
        return float(text)
    except ValueError:
        return text


def _toml_split(body):
    parts = []
    depth = 0
    cur = ""
    for ch in body:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [p for p in parts if p.strip()]


def _toml_value(text):
    text = text.strip()
    if text.startswith("["):
        return [_toml_value(p) for p in _toml_split(text[1:-1])]
    if text.startswith("{"):
        obj = {}
        for part in _toml_split(text[1:-1]):
            key, _, value = part.partition("=")
            obj[key.strip().strip('"')] = _toml_value(value)
        return obj
    return _toml_scalar(text)


def parse_toml_text(text, path):
    """Minimal TOML reader used only when tomllib is unavailable."""
    data = {}
    section = data
    buf = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not buf:
            line = line.split("#")[0].strip()
            if not line:
                continue
            if line.startswith("[") and "=" not in line:
                name = line.strip("[]").strip()
                section = data
                for part in name.split("."):
                    section = section.setdefault(part.strip().strip('"'), {})
                continue
        buf += line
        if buf.count("[") != buf.count("]") or buf.count("{") != buf.count("}"):
            continue
        key, sep, value = buf.partition("=")
        if not sep:
            die(path, "bad line %r" % raw_line)
        section[key.strip().strip('"')] = _toml_value(value)
        buf = ""
    return data


def num(x):
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


# --------------------------------------------------------------------------
# intake
# --------------------------------------------------------------------------

class Request(object):
    __slots__ = ("asset_id", "duration", "es", "lf", "crews", "origin", "position",
                 "region", "crew_type", "weight", "w_comm", "w_pub",
                 "published_start", "published_entry", "starts")


def do_intake(data_dir):
    assets = {}
    for obj in load_jsonl(os.path.join(data_dir, "assets.jsonl")):
        assets[obj["asset_id"]] = obj

    req_doc = load_json(os.path.join(data_dir, "requests.json"))
    season = req_doc["season"]
    first_day = season["first_day"]
    last_day = season["last_day"]

    plan_doc = load_json(os.path.join(data_dir, "published_plan.json"))
    published_at = plan_doc["published_at"]
    published = {}
    for entry in plan_doc["plan"]:
        published[entry["asset_id"]] = entry

    seen = set()
    accepted = {}
    rejected = []

    def classify(asset_id, duration, es, lf):
        if asset_id not in assets:
            return "unknown_asset"
        if es < first_day or lf > last_day:
            return "out_of_season"
        if lf - es + 1 < duration:
            return "window_too_short"
        if asset_id in seen:
            return "duplicate_request"
        return None

    def accept(asset_id, duration, es, lf, crews, origin, position):
        seen.add(asset_id)
        r = Request()
        r.asset_id = asset_id
        r.duration = duration
        r.es = es
        r.lf = lf
        r.crews = crews
        r.origin = origin
        r.position = position
        r.region = assets[asset_id]["region"]
        r.crew_type = assets[asset_id]["crew_type"]
        accepted[asset_id] = r

    for idx, rec in enumerate(req_doc["requests"]):
        aid = rec["asset_id"]
        reason = classify(aid, rec["duration_days"], rec["earliest_start"],
                          rec["latest_finish"])
        if reason:
            rejected.append({"source": "requests.json", "position": idx,
                             "asset_id": aid, "reason": reason})
        else:
            accept(aid, rec["duration_days"], rec["earliest_start"],
                   rec["latest_finish"], rec["crews"], "published", idx)

    log_path = os.path.join(data_dir, "control_room.log")
    ignored_lines = 0
    withdrawn = []
    losses = {}

    for lineno, line in enumerate(read_text(log_path).splitlines(), 1):
        tokens = line.split()
        if len(tokens) >= 3 and TS_RE.match(tokens[0]) and tokens[2] == "HEARTBEAT":
            continue
        event = None
        kv = {}
        if len(tokens) >= 3 and TS_RE.match(tokens[0]) and tokens[2] in EVENT_KEYS:
            name = tokens[2]
            good = True
            for tok in tokens[3:]:
                key, sep, value = tok.partition("=")
                if not sep or key in kv:
                    good = False
                    break
                kv[key] = value
            if good and set(kv) == EVENT_KEYS[name]:
                for key in EVENT_INT_KEYS[name]:
                    if not INT_RE.match(kv[key]):
                        good = False
                        break
            else:
                good = False
            if good and name == "CREW_LOSS":
                if (kv["region"] not in REGIONS or kv["crew_type"] not in CREW_TYPES
                        or int(kv["from"]) > int(kv["to"]) or int(kv["count"]) < 1):
                    good = False
            if good:
                event = name
        if event is None:
            ignored_lines += 1
            continue
        if tokens[0] <= published_at:
            continue
        if event == "CREW_LOSS":
            group = (kv["region"], kv["crew_type"])
            count = int(kv["count"])
            lo = max(first_day, int(kv["from"]))
            hi = min(last_day, int(kv["to"]))
            for day in range(lo, hi + 1):
                losses[(group, day)] = losses.get((group, day), 0) + count
        elif event == "NEW_REQUEST":
            aid = kv["asset_id"]
            duration = int(kv["duration_days"])
            es = int(kv["earliest_start"])
            lf = int(kv["latest_finish"])
            reason = classify(aid, duration, es, lf)
            if reason:
                rejected.append({"source": "control_room.log", "position": lineno,
                                 "asset_id": aid, "reason": reason})
            else:
                accept(aid, duration, es, lf, int(kv["crews"]), "control_room", lineno)
        else:
            aid = kv["asset_id"]
            if aid in accepted:
                del accepted[aid]
                withdrawn.append(aid)
            else:
                ignored_lines += 1

    for r in accepted.values():
        entry = published.get(r.asset_id) if r.origin == "published" else None
        r.published_entry = entry
        r.published_start = entry["start"] if entry and entry["status"] == "scheduled" else None

    return {
        "assets": assets,
        "first_day": first_day,
        "last_day": last_day,
        "requests": accepted,
        "rejected": rejected,
        "withdrawn": withdrawn,
        "losses": losses,
        "ignored_lines": ignored_lines,
    }


# --------------------------------------------------------------------------
# reference data
# --------------------------------------------------------------------------

def load_weights(data_dir, policy, requests):
    path = os.path.join(data_dir, "customers.csv")
    counts = {}
    reader = csv.DictReader(read_text(path).splitlines())
    if not reader.fieldnames or "asset_id" not in reader.fieldnames:
        die(path, "missing header")
    for row in reader:
        key = (row["asset_id"], row["class"])
        counts[key] = counts.get(key, 0) + 1
    class_weight = policy["class_weight"]
    for r in requests.values():
        r.w_comm = counts.get((r.asset_id, "commercial"), 0) * class_weight["commercial"]
        r.w_pub = counts.get((r.asset_id, "public"), 0) * class_weight["public"]
        r.weight = r.w_comm + r.w_pub


def load_factors(data_dir, policy, first_day, last_day):
    path = os.path.join(data_dir, "load_forecast.tsv")
    lines = read_text(path).splitlines()
    if not lines:
        die(path, "empty")
    header = [h.strip() for h in lines[0].split("\t")]
    try:
        i_region = header.index("region")
        i_day = header.index("day")
        i_load = header.index("load_mw")
    except ValueError as exc:
        die(path, str(exc))
    peak = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        cells = line.split("\t")
        key = (cells[i_region].strip(), int(cells[i_day]))
        load = float(cells[i_load])
        if key not in peak or load > peak[key]:
            peak[key] = load
    bands = sorted(policy["load_band"]["bands"], key=lambda b: b["min_mw"])
    factors = {}
    for region in REGIONS:
        row = {}
        for day in range(first_day, last_day + 1):
            p = peak.get((region, day))
            if p is None:
                die(path, "no rows for %s day %d" % (region, day))
            factor = None
            for band in bands:
                if band["min_mw"] <= p:
                    factor = band["factor"]
            if factor is None:
                die(path, "no load band for %s day %d" % (region, day))
            row[day] = factor
        factors[region] = row
    return factors


def load_capacity(data_dir, losses, first_day, last_day):
    on_duty = {}
    for obj in load_jsonl(os.path.join(data_dir, "crew_roster.jsonl")):
        if obj.get("status") != "on_duty":
            continue
        key = ((obj["region"], obj["crew_type"]), obj["day"])
        on_duty[key] = on_duty.get(key, 0) + 1
    cap = {}
    for region in REGIONS:
        for crew_type in CREW_TYPES:
            group = (region, crew_type)
            row = {}
            for day in range(first_day, last_day + 1):
                value = on_duty.get((group, day), 0) - losses.get((group, day), 0)
                row[day] = value if value > 0 else 0
            cap[group] = row
    return cap


def load_blackouts(data_dir):
    doc = load_json(os.path.join(data_dir, "region_calendar.json"))
    out = {}
    for region in REGIONS:
        entry = doc.get(region) or {}
        out[region] = set(entry.get("blackout_days", []))
    return out


# --------------------------------------------------------------------------
# scheduling
# --------------------------------------------------------------------------

class Var(object):
    __slots__ = ("req", "group", "options", "min_risk", "min_moved",
                 "incompat", "before", "after")


def moved_flag(r, start):
    if r.origin != "published":
        return 0
    entry = r.published_entry
    if entry is None:
        return 0
    if entry["status"] == "scheduled":
        return 1 if start != entry["start"] else 0
    return 1 if start is not None else 0


def build_vars(requests, cap, blackouts, factors, defer_factor):
    vars_by_id = {}
    for aid, r in requests.items():
        v = Var()
        v.req = r
        v.group = (r.region, r.crew_type)
        day_factor = factors[r.region]
        starts = []
        for s in range(r.es, r.lf - r.duration + 2):
            if s in blackouts[r.region]:
                continue
            ok = True
            for day in range(s, s + r.duration):
                if cap[v.group].get(day, 0) < r.crews:
                    ok = False
                    break
            if ok:
                starts.append(s)
        r.starts = starts
        options = []
        for s in starts:
            risk = r.weight * sum(day_factor[d] for d in range(s, s + r.duration))
            options.append((s, risk, moved_flag(r, s)))
        options.append((None, r.weight * r.duration * defer_factor, moved_flag(r, None)))
        v.options = options
        v.min_risk = min(o[1] for o in options)
        v.min_moved = min(o[2] for o in options)
        v.incompat = []
        v.before = []
        v.after = []
        vars_by_id[aid] = v
    return vars_by_id


def components(vars_by_id, net):
    parent = {aid: aid for aid in vars_by_id}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for pair in net.get("incompatible", []):
        a, b = pair[0], pair[1]
        if a in vars_by_id and b in vars_by_id and a != b:
            vars_by_id[a].incompat.append(b)
            vars_by_id[b].incompat.append(a)
            union(a, b)
    for entry in net.get("precedence", []):
        a, b = entry["before"], entry["after"]
        if a in vars_by_id and b in vars_by_id and a != b:
            vars_by_id[a].after.append(b)
            vars_by_id[b].before.append(a)
            union(a, b)

    by_group = {}
    for aid, v in vars_by_id.items():
        by_group.setdefault(v.group, []).append(aid)
    for members in by_group.values():
        members = sorted(members, key=lambda a: vars_by_id[a].req.es)
        for i, a in enumerate(members):
            reach = vars_by_id[a].req.lf
            for b in members[i + 1:]:
                if vars_by_id[b].req.es > reach:
                    break
                union(a, b)

    comps = {}
    for aid in vars_by_id:
        comps.setdefault(find(aid), []).append(aid)
    return [sorted(m) for m in comps.values()]


def option_key(option):
    return (1, 0) if option[0] is None else (0, option[0])


class Solver(object):
    """Exhaustive search with bounds over one independent component."""

    def __init__(self, vars_by_id, member_ids, cap):
        self.V = vars_by_id
        self.members = member_ids
        self.cap = cap
        self.assign = {}
        self.used = {}
        self.order = []
        self.suffix_risk = []
        self.suffix_moved = []
        self.best = None
        self.target = None

    def fits(self, aid, option):
        v = self.V[aid]
        r = v.req
        start = option[0]
        assign = self.assign
        for other in v.incompat:
            if other in assign:
                ostart = assign[other][0]
                if start is not None and ostart is not None:
                    odur = self.V[other].req.duration
                    if start <= ostart + odur - 1 and ostart <= start + r.duration - 1:
                        return False
        for other in v.before:
            if other in assign:
                ostart = assign[other][0]
                if ostart is None:
                    if start is not None:
                        return False
                elif start is not None:
                    if start <= ostart + self.V[other].req.duration - 1:
                        return False
        for other in v.after:
            if other in assign:
                ostart = assign[other][0]
                if start is None:
                    if ostart is not None:
                        return False
                elif ostart is not None:
                    if ostart <= start + r.duration - 1:
                        return False
        if start is not None:
            cap = self.cap[v.group]
            used = self.used
            group = v.group
            crews = r.crews
            for day in range(start, start + r.duration):
                if used.get((group, day), 0) + crews > cap[day]:
                    return False
        return True

    def place(self, aid, option):
        v = self.V[aid]
        self.assign[aid] = option
        if option[0] is not None:
            group = v.group
            used = self.used
            for day in range(option[0], option[0] + v.req.duration):
                key = (group, day)
                used[key] = used.get(key, 0) + v.req.crews

    def unplace(self, aid):
        v = self.V[aid]
        option = self.assign.pop(aid)
        if option[0] is not None:
            group = v.group
            used = self.used
            for day in range(option[0], option[0] + v.req.duration):
                used[(group, day)] -= v.req.crews

    def prepare(self, pending):
        order = sorted(pending, key=lambda a: (len(self.V[a].options),
                                               self.V[a].req.es, a))
        self.order = order
        n = len(order)
        self.suffix_risk = [0] * (n + 1)
        self.suffix_moved = [0] * (n + 1)
        for i in range(n - 1, -1, -1):
            v = self.V[order[i]]
            self.suffix_risk[i] = self.suffix_risk[i + 1] + v.min_risk
            self.suffix_moved[i] = self.suffix_moved[i + 1] + v.min_moved

    def minimise(self):
        """Smallest (risk, moved) pair reachable in this component."""
        self.assign = {}
        self.used = {}
        self.prepare(list(self.members))
        self.best = None
        self._min_dfs(0, 0, 0)
        return self.best

    def _min_dfs(self, k, risk, moved):
        if k == len(self.order):
            cand = (risk, moved)
            if self.best is None or cand < self.best:
                self.best = cand
            return
        aid = self.order[k]
        rest_r = self.suffix_risk[k + 1]
        rest_m = self.suffix_moved[k + 1]
        for option in self.V[aid].options:
            nr = risk + option[1]
            nm = moved + option[2]
            if self.best is not None and (nr + rest_r, nm + rest_m) >= self.best:
                continue
            if not self.fits(aid, option):
                continue
            self.place(aid, option)
            self._min_dfs(k + 1, nr, nm)
            self.unplace(aid)

    def refine(self, target):
        """Lexicographically smallest start-day list holding the target pair."""
        self.assign = {}
        self.used = {}
        self.target = target
        for aid in sorted(self.members):
            chosen = None
            for option in sorted(self.V[aid].options, key=option_key):
                if not self.fits(aid, option):
                    continue
                self.place(aid, option)
                pending = [a for a in self.members if a not in self.assign]
                self.prepare(pending)
                risk = sum(o[1] for o in self.assign.values())
                moved = sum(o[2] for o in self.assign.values())
                if self._exact_dfs(0, risk, moved):
                    chosen = option
                    break
                self.unplace(aid)
            if chosen is None:
                raise RuntimeError("no completion for %s" % aid)
        return dict(self.assign)

    def _exact_dfs(self, k, risk, moved):
        if k == len(self.order):
            return (risk, moved) == self.target
        aid = self.order[k]
        rest_r = self.suffix_risk[k + 1]
        rest_m = self.suffix_moved[k + 1]
        tr, tm = self.target
        for option in self.V[aid].options:
            nr = risk + option[1]
            nm = moved + option[2]
            if nr + rest_r > tr or nm + rest_m > tm:
                continue
            if not self.fits(aid, option):
                continue
            self.place(aid, option)
            found = self._exact_dfs(k + 1, nr, nm)
            self.unplace(aid)
            if found:
                return True
        return False


def solve(vars_by_id, comps, cap):
    schedule = {}
    for member_ids in comps:
        solver = Solver(vars_by_id, member_ids, cap)
        target = solver.minimise()
        if target is None:
            raise RuntimeError("no feasible season for component %r" % (member_ids,))
        schedule.update(solver.refine(target))
    return schedule


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def deferral_reason(r, vars_by_id, schedule):
    if not r.starts:
        return "no_feasible_start"
    for other in vars_by_id[r.asset_id].before:
        if schedule[other][0] is None:
            return "predecessor_deferred"
    return "displaced"


def main():
    ap = argparse.ArgumentParser(description="replan the outage season")
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    data_dir = args.data
    out_dir = args.out

    intake = do_intake(data_dir)
    requests = intake["requests"]
    first_day = intake["first_day"]
    last_day = intake["last_day"]

    policy = load_toml(os.path.join(data_dir, "risk_policy.toml"))
    defer_factor = policy["deferral"]["defer_factor"]
    load_weights(data_dir, policy, requests)
    factors = load_factors(data_dir, policy, first_day, last_day)
    cap = load_capacity(data_dir, intake["losses"], first_day, last_day)
    blackouts = load_blackouts(data_dir)
    net = load_json(os.path.join(data_dir, "network_constraints.json"))

    vars_by_id = build_vars(requests, cap, blackouts, factors, defer_factor)
    schedule = solve(vars_by_id, components(vars_by_id, net), cap)

    rows = []
    for aid in sorted(requests):
        r = requests[aid]
        start, risk, moved = schedule[aid]
        if start is None:
            end = None
            reason = deferral_reason(r, vars_by_id, schedule)
            mult = r.duration * defer_factor
        else:
            end = start + r.duration - 1
            reason = None
            mult = sum(factors[r.region][d] for d in range(start, end + 1))
        rows.append({
            "asset_id": aid,
            "region": r.region,
            "crew_type": r.crew_type,
            "origin": r.origin,
            "status": "deferred" if start is None else "scheduled",
            "start": start,
            "end": end,
            "published_start": r.published_start,
            "moved": bool(moved),
            "risk_days": num(risk),
            "reason": reason,
            "_comm": num(r.w_comm * mult),
            "_pub": num(r.w_pub * mult),
            "_crew_days": r.crews * r.duration,
        })

    total_risk = num(sum(row["risk_days"] for row in rows))
    total_moved = sum(1 for row in rows if row["moved"])
    scheduled_rows = [row for row in rows if row["status"] == "scheduled"]

    os.makedirs(out_dir, exist_ok=True)

    def write(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=1)
            fh.write("\n")

    audit_keys = ("asset_id", "region", "crew_type", "origin", "status", "start",
                  "end", "published_start", "moved", "risk_days", "reason")
    write("policy_audit.json",
          {"requests": [{k: row[k] for k in audit_keys} for row in rows]})

    for region in REGIONS:
        region_rows = [row for row in rows if row["region"] == region]
        sched = sorted((row for row in region_rows if row["status"] == "scheduled"),
                       key=lambda row: (row["start"], row["asset_id"]))
        crew_days = dict((ct, 0) for ct in CREW_TYPES)
        for row in sched:
            crew_days[row["crew_type"]] += row["_crew_days"]
        write("region_%s.json" % region, {
            "region": region,
            "schedule": [{"asset_id": row["asset_id"], "crew_type": row["crew_type"],
                          "start": row["start"], "end": row["end"]} for row in sched],
            "crew_days": crew_days,
            "risk_days": num(sum(row["risk_days"] for row in region_rows)),
            "deferred": sorted(row["asset_id"] for row in region_rows
                               if row["status"] == "deferred"),
            "moved": sum(1 for row in region_rows if row["moved"]),
        })

    for segment, key in (("commercial", "_comm"), ("public", "_pub")):
        write("segment_%s.json" % segment, {
            "segment": segment,
            "risk_days": num(sum(row[key] for row in rows)),
            "by_region": dict((region, num(sum(row[key] for row in rows
                                               if row["region"] == region)))
                              for region in REGIONS),
            "deferred_risk_days": num(sum(row[key] for row in rows
                                          if row["status"] == "deferred")),
        })

    write("summary.json", {
        "requests": len(rows),
        "scheduled": len(scheduled_rows),
        "deferred": len(rows) - len(scheduled_rows),
        "moved": total_moved,
        "risk_days": total_risk,
        "crew_days": sum(row["_crew_days"] for row in scheduled_rows),
        "objective": [total_risk, total_moved],
    })

    rejected = sorted(intake["rejected"], key=lambda row: (row["source"], row["position"]))
    counts = dict((reason, 0) for reason in REASONS)
    for row in rejected:
        counts[row["reason"]] = counts.get(row["reason"], 0) + 1
    write("data_quality.json", {
        "rejected": rejected,
        "counts": counts,
        "withdrawn": sorted(intake["withdrawn"]),
        "ignored_lines": intake["ignored_lines"],
    })


if __name__ == "__main__":
    main()
