"""Phase 0b prototype program: data dir -> out dir (core rules only). Usage: solve_proto.py --data D --out O"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import tomllib
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ref import solve  # noqa: E402
import docx  # noqa: E402
READER = os.environ.get("READER", "ref")

BASES = ["North", "South", "West", "East"]
SEGMENTS = {"commercial": ("widebody", "narrowbody"), "public": ("regional",)}
REASONS = ["duplicate_request", "unknown_base", "unknown_check_type", "unknown_tail", "retired_tail", "bad_date",
           "bad_duration", "no_published_start"]
FILES = ["fleet_register.csv", "check_requests.csv", "published_plan.csv", "base_calendar.jsonl",
         "disruption_notice.docx", "planning_limits.docx", "check_types.json", "fleet_limits.toml"]


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def pdate(s):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        raise ValueError(s)
    return dt.date.fromisoformat(s)


def read_yaml(path):
    out, cur = {}, None
    for line in open(path):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            cur = line.split(":")[0].strip()
            out[cur] = {}
        else:
            k, v = line.split(":", 1)
            out[cur][k.strip()] = int(v.strip())
    return out


def md_tables(path):
    tables, cur, name = {}, None, None
    for line in open(path):
        s = line.strip()
        if s.startswith("## "):
            name = s[3:].strip()
            cur = None
        elif s.startswith("|") and name:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cur is None:
                cur = tables.setdefault(name, [])
                hdr = cells
            elif set(s) <= set("|-: "):
                continue
            else:
                cur.append(dict(zip(hdr, cells)))
    return tables


def load(data):
    for f in FILES:
        if not os.path.isfile(os.path.join(data, f)):
            die("missing input file: %s" % f)
    P = lambda f: os.path.join(data, f)
    try:
        lim = tomllib.load(open(P("fleet_limits.toml"), "rb"))
        by = {}
        for f in ("planning_limits.docx", "disruption_notice.docx"):
            for t in docx.read_tables(P(f), READER):
                if t:
                    by.setdefault(t[0][0], [dict(zip(t[0], r)) for r in t[1:]])
        for r in by["item"]:
            lim[r["item"]] = int(r["value"])
        rates = {r["class"]: {k: int(v) for k, v in r.items() if k != "class"} for r in by["class"]}
        notice = {"Revised availability": by["tail"], "Base closures": [
            {"base": r["base"], "from": r["from"],
             "to": (pdate(r["from"]) + dt.timedelta(days=int(r["days"]) - 1)).isoformat()} for r in by["base"]]}
        types = json.load(open(P("check_types.json")))
        reg = {r["tail"]: r for r in csv.DictReader(open(P("fleet_register.csv")))}
        pub = {r["request_id"]: r["published_start"] for r in csv.DictReader(open(P("published_plan.csv")))}
        cal = [json.loads(l) for l in open(P("base_calendar.jsonl")) if l.strip()]
    except (OSError, ValueError, KeyError, IndexError, zipfile.BadZipFile, ET.ParseError, json.JSONDecodeError, tomllib.TOMLDecodeError) as e:
        die("cannot parse input: %s" % e)
    return lim, rates, types, reg, pub, cal, notice


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/app/environment/data")
    ap.add_argument("--out", default="/app/out")
    a = ap.parse_args()
    lim, rates, types, reg, pub, cal, notice = load(a.data)
    s0, s1 = pdate(lim["season_start"]), pdate(lim["season_end"])
    S = (s1 - s0).days + 1
    dn = lambda d: (d - s0).days + 1
    dd = lambda k: (s0 + dt.timedelta(days=k - 1)).isoformat()
    avail = {r["tail"]: r["available_from"] for r in notice.get("Revised availability", [])}
    rejected, seen, planning = [], set(), []
    with open(os.path.join(a.data, "check_requests.csv")) as f:
        rd = csv.DictReader(f)
        for line, r in enumerate(rd, start=2):
            if r["season"] != lim["season"] or r["status"] != "OPEN":
                continue
            rid = r["request_id"]
            why = None
            if rid in seen:
                why = "duplicate_request"
            elif r["base"] not in BASES:
                why = "unknown_base"
            elif r["check_type"] not in types:
                why = "unknown_check_type"
            elif r["tail"] not in reg:
                why = "unknown_tail"
            elif reg[r["tail"]]["status"] == "RETIRED":
                why = "retired_tail"
            else:
                try:
                    pdate(r["available_from"]), pdate(r["due_date"])
                except ValueError:
                    why = "bad_date"
                if why is None and not re.fullmatch(r"[1-9]\d*", r["duration_days"]):
                    why = "bad_duration"
                if why is None and rid not in pub:
                    why = "no_published_start"
            seen.add(rid)
            if why:
                rejected.append({"request_id": rid, "line": line, "reason": why})
            else:
                planning.append(r)
    closed = {b: set() for b in BASES}
    nostart = {b: set() for b in BASES}
    for c in cal:
        k = dn(pdate(c["date"]))
        if 1 <= k <= S and c["base"] in closed:
            if c["status"] == "CLOSED":
                closed[c["base"]].add(k)
            elif c["status"] == "NO_START":
                nostart[c["base"]].add(k)
    for c in notice.get("Base closures", []):
        for k in range(dn(pdate(c["from"])), dn(pdate(c["to"])) + 1):
            if 1 <= k <= S:
                closed[c["base"]].add(k)
    checks = []
    for r in planning:
        af = avail.get(r["tail"], r["available_from"])
        checks.append({"id": r["request_id"], "base": r["base"], "cls": reg[r["tail"]]["aircraft_class"],
                       "type": r["check_type"], "p": int(r["duration_days"]), "ps": dn(pdate(pub[r["request_id"]])),
                       "due": dn(pdate(r["due_date"])), "r": max(1, dn(pdate(af))), "tail": r["tail"]})
    inst = {"S": S, "bases": BASES, "shift_cost": lim["shift_cost"], "K": lim["overtime_pool_shifts"],
            "classes": {c: {"rev": v["revenue_per_day"], "w": v["overdue_weight"], "pen": v["deferral_penalty"]}
                        for c, v in rates.items()},
            "types": {t: {"c": v["max_compress_days"], "h": v["overtime_shifts_per_day"]} for t, v in types.items()},
            "closed": {b: sorted(v) for b, v in closed.items()}, "nostart": {b: sorted(v) for b, v in nostart.items()},
            "checks": checks}
    res = solve(inst)
    write(a.out, lim, inst, res, rejected, dd)


def fits_empty(ch, inst):
    S = inst["S"]
    cl, ns = set(inst["closed"][ch["base"]]), set(inst["nostart"][ch["base"]])
    for x in range(0, min(inst["types"][ch["type"]]["c"], ch["p"] - 1) + 1):
        dur = ch["p"] - x
        for s in range(ch["r"], S - dur + 2):
            if s not in ns and not any(d in cl for d in range(s, s + dur)):
                return True
    return False


def write(out, lim, inst, res, rejected, dd):
    S = inst["S"]
    seg_of = {c: s for s, cs in SEGMENTS.items() for c in cs}
    rows = []
    for ch in sorted(inst["checks"], key=lambda c: c["id"]):
        s, f, x = res["plan"][ch["id"]]
        cl = inst["classes"][ch["cls"]]
        h = inst["types"][ch["type"]]["h"]
        if s > S:
            rows.append({"request_id": ch["id"], "tail": ch["tail"], "base": ch["base"], "aircraft_class": ch["cls"],
                         "segment": seg_of[ch["cls"]], "check_type": ch["type"], "decision": "deferred",
                         "start_date": None, "finish_date": None, "compress_days": 0, "overtime_shifts": 0,
                         "overdue_days": 0, "moved": True,
                         "deferral_reason": "plan_trade" if fits_empty(ch, inst) else "no_slot",
                         "_pen": cl["pen"], "_rev": 0})
        else:
            od = max(0, f - ch["due"])
            rows.append({"request_id": ch["id"], "tail": ch["tail"], "base": ch["base"], "aircraft_class": ch["cls"],
                         "segment": seg_of[ch["cls"]], "check_type": ch["type"], "decision": "scheduled",
                         "start_date": dd(s), "finish_date": dd(f), "compress_days": x, "overtime_shifts": h * x,
                         "overdue_days": od, "moved": s != ch["ps"], "deferral_reason": None,
                         "_pen": 0, "_rev": cl["rev"] * (ch["p"] - x), "_odc": od * cl["w"]})
    used = res["used"]

    def agg(sel):
        sc = [r for r in sel if r["decision"] == "scheduled"]
        return {"checks_scheduled": len(sc), "checks_deferred": len(sel) - len(sc),
                "compress_days": sum(r["compress_days"] for r in sc),
                "overtime_shifts": sum(r["overtime_shifts"] for r in sc),
                "overdue_days": sum(r["overdue_days"] for r in sc),
                "overdue_cost": sum(r.get("_odc", 0) for r in sc),
                "deferral_cost": sum(r["_pen"] for r in sel),
                "revenue_lost": sum(r["_rev"] for r in sc),
                "moved": sum(1 for r in sel if r["moved"]),
                "first_start": min((r["start_date"] for r in sc), default=None),
                "last_finish": max((r["finish_date"] for r in sc), default=None),
                "fleet_overtime_used": used}
    os.makedirs(os.path.join(out, "regions"), exist_ok=True)
    os.makedirs(os.path.join(out, "segments"), exist_ok=True)
    pub_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    dump(os.path.join(out, "check_plan.json"), {"season": lim["season"], "checks": pub_rows})
    summ_b, summ_s = [], []
    for b in BASES:
        g = agg([r for r in rows if r["base"] == b])
        dump(os.path.join(out, "regions", "region_%s.json" % b.lower()), dict({"base": b}, **g))
        summ_b.append({"base": b, "checks_scheduled": g["checks_scheduled"], "checks_deferred": g["checks_deferred"],
                       "overtime_shifts": g["overtime_shifts"]})
    for s in SEGMENTS:
        g = agg([r for r in rows if r["segment"] == s])
        dump(os.path.join(out, "segments", "segment_%s.json" % s), dict({"segment": s}, **g))
        summ_s.append({"segment": s, "checks_scheduled": g["checks_scheduled"], "checks_deferred": g["checks_deferred"]})
    g = agg(rows)
    dump(os.path.join(out, "plan_summary.json"), {
        "season": lim["season"], "plan_terms": {"first": res["T"][0], "second": res["T"][1], "third": res["T"][2]},
        "overtime_pool_shifts": inst["K"], "fleet_overtime_used": used, "checks_scheduled": g["checks_scheduled"],
        "checks_deferred": g["checks_deferred"], "moved": g["moved"], "bases": summ_b, "segments": summ_s})
    counts = {k: sum(1 for r in rejected if r["reason"] == k) for k in REASONS}
    dump(os.path.join(out, "data_quality.json"), {"rejected": rejected, "counts": counts})


def dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
