"""Independent recompute of the hangar replan from the visible docs (G9).

Usage: python3 -B check_exact.py DATA_DIR OUT_DIR
OUT_DIR holds the program outputs to check. The plan is searched over every
legal start day (no dominance shortcut), the settlement is replayed from the
stated order, and invariants are asserted on the delivered files. Prints one
DIFF line per differing field, then OK or FAIL.
"""
import csv
import datetime
import json
import os
import re
import sys
import tomllib
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BASES = ["North", "South", "West", "East"]
SEG = {"widebody": "commercial", "narrowbody": "commercial", "regional": "public"}


def word_tables(path):
    z = zipfile.ZipFile(path)
    rels = ET.fromstring(z.read("_rels/.rels"))
    main = [r.get("Target") for r in rels if r.get("Type", "").endswith("/officeDocument")][0]
    root = ET.fromstring(z.read(main.lstrip("/")))
    out = {}
    for t in root.iter(W + "tbl"):
        rows = [["".join(x.text or "" for x in c.iter(W + "t")).strip() for c in r.iter(W + "tc")]
                for r in t.iter(W + "tr")]
        out[tuple(rows[0][:2])] = rows[1:]
    return out


def load(d):
    lim = tomllib.load(open(os.path.join(d, "fleet_limits.toml"), "rb"))
    s0 = datetime.date.fromisoformat(lim["season_start"])
    S = (datetime.date.fromisoformat(lim["season_end"]) - s0).days + 1
    day = lambda iso: (datetime.date.fromisoformat(iso) - s0).days + 1
    pl = word_tables(os.path.join(d, "planning_limits.docx"))
    item = {k: int(v) for k, v in pl[("item", "value")]}
    rates = {r[0]: tuple(int(x) for x in r[1:4]) for r in pl[("class", "revenue_per_day")]}
    grants = {b: int(v) for b, v in pl[("base", "allowance_shifts")]}
    dn = word_tables(os.path.join(d, "disruption_notice.docx"))
    types = json.load(open(os.path.join(d, "check_types.json")))
    reg = {r["tail"]: r for r in csv.DictReader(open(os.path.join(d, "fleet_register.csv")))}
    pub = {r["request_id"]: r["published_start"] for r in csv.DictReader(open(os.path.join(d, "published_plan.csv")))}
    closed = {b: set() for b in BASES}
    nost = {b: set() for b in BASES}
    for line in open(os.path.join(d, "base_calendar.jsonl")):
        r = json.loads(line)
        if r["base"] in closed and 1 <= day(r["date"]) <= S:
            if r["status"] == "CLOSED":
                closed[r["base"]].add(day(r["date"]))
            elif r["status"] == "NO_START":
                nost[r["base"]].add(day(r["date"]))
    for b, f, n in dn[("base", "from")]:
        for k in range(int(n)):
            closed[b].add(day(f) + k)
    revised = {t: a for t, a in dn[("tail", "available_from")]}
    good = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def okdate(x):
        if not good.match(x):
            return False
        try:
            datetime.date.fromisoformat(x)
        except ValueError:
            return False
        return True

    seen, rej, reqs = set(), [], []
    with open(os.path.join(d, "check_requests.csv")) as f:
        for ln, r in enumerate(csv.DictReader(f), start=2):
            if r["season"] != lim["season"] or r["status"] != "OPEN":
                continue
            rid = r["request_id"]
            reason = None
            if rid in seen:
                reason = "duplicate_request"
            elif r["base"] not in BASES:
                reason = "unknown_base"
            elif r["check_type"] not in types:
                reason = "unknown_check_type"
            elif r["tail"] not in reg:
                reason = "unknown_tail"
            elif reg[r["tail"]]["status"] != "ACTIVE":
                reason = "retired_tail"
            elif not (okdate(r["available_from"]) and okdate(r["due_date"])):
                reason = "bad_date"
            elif not re.match(r"^[1-9][0-9]*$", r["duration_days"]):
                reason = "bad_duration"
            elif rid not in pub:
                reason = "no_published_start"
            seen.add(rid)
            if reason:
                rej.append({"request_id": rid, "line": ln, "reason": reason})
                continue
            t = types[r["check_type"]]
            cls = reg[r["tail"]]["aircraft_class"]
            p = int(r["duration_days"])
            reqs.append(dict(id=rid, tail=r["tail"], base=r["base"], cls=cls, type=r["check_type"], p=p,
                             r=max(1, day(revised.get(r["tail"], r["available_from"]))),
                             due=day(r["due_date"]), ps=day(pub[rid]),
                             cmax=min(t["max_compress_days"], p - 1), h=t["overtime_shifts_per_day"]))
    return dict(S=S, day0=s0, item=item, rates=rates, grants=grants, closed=closed, nost=nost,
                reqs=sorted(reqs, key=lambda q: q["id"]), rej=rej, season=lim["season"])


def legal(P, b, s, dur):
    f = s + dur - 1
    return s not in P["nost"][b] and f <= P["S"] and not any(x in P["closed"][b] for x in range(s, f + 1))


def base_front(P, b):
    """Every legal start day searched. Returns {shifts: (T1, T2, T3, starts, finishes, comp)}."""
    qs = [q for q in P["reqs"] if q["base"] == b]
    S, sc = P["S"], P["item"]["shift_cost"]
    memo = {}

    def go(i_mask, tfree):
        key = (i_mask, tfree)
        if key in memo:
            return memo[key]
        if i_mask == (1 << len(qs)) - 1:
            memo[key] = {0: (0, 0, 0, (), (), ())}
            return memo[key]
        res = {}
        for i, q in enumerate(qs):
            if i_mask >> i & 1:
                continue
            rev, w, pen = P["rates"][q["cls"]]
            opts = [(None, 0)]
            for x in range(q["cmax"] + 1):
                dur = q["p"] - x
                for s in range(max(tfree, q["r"]), S - dur + 2):
                    if legal(P, b, s, dur):
                        opts.append((s, x))
            for s, x in opts:
                if s is None:
                    nxt, add = go(i_mask | 1 << i, tfree), (pen, 0, 1)
                    st, fi, ot = S + 1, S + 1, 0
                else:
                    fi = s + q["p"] - x - 1
                    nxt = go(i_mask | 1 << i, fi + 1)
                    add = (max(0, fi - q["due"]) * w, rev * (q["p"] - x) + sc * q["h"] * x, int(s != q["ps"]))
                    st, ot = s, q["h"] * x
                for o, v in nxt.items():
                    vec = dict(zip(v[5], zip(v[3], v[4])))
                    vec[q["id"]] = (st, fi)
                    ids = sorted(vec)
                    cand = (v[0] + add[0], v[1] + add[1], v[2] + add[2],
                            tuple(vec[k][0] for k in ids), tuple(vec[k][1] for k in ids), tuple(ids))
                    cand = cand[:5] + (cand[5],)
                    k = o + ot
                    if k not in res or cand[:5] < res[k][:5]:
                        res[k] = cand
        memo[key] = res
        return res

    return go(0, 1)


def plan(P):
    fleet = {0: (0, 0, 0, {})}
    for b in BASES:
        fr = base_front(P, b)
        nf = {}
        for o1, a in fleet.items():
            for o2, v in fr.items():
                o = o1 + o2
                if o > P["item"]["overtime_pool_shifts"]:
                    continue
                m = dict(a[3])
                m.update({i: (s, f) for i, s, f in zip(v[5], v[3], v[4])})
                c = (a[0] + v[0], a[1] + v[1], a[2] + v[2], m)
                if o not in nf or key(c) < key(nf[o]):
                    nf[o] = c
        fleet = nf
    best = min(fleet.items(), key=lambda kv: key(kv[1]))
    return best[0], best[1]


def key(c):
    ids = sorted(c[3])
    return (c[0], c[1], c[2], tuple(c[3][i][0] for i in ids), tuple(c[3][i][1] for i in ids))


def main():
    d, o = sys.argv[1], sys.argv[2]
    P = load(d)
    used, best = plan(P)
    got = {n: json.load(open(os.path.join(o, n))) for n in os.listdir(o) if n.endswith(".json")}
    diffs = []

    def eq(path, a, b):
        if a != b:
            diffs.append(f"DIFF {path}: want {a!r} got {b!r}")

    S = P["S"]
    tday = lambda n: (P["day0"] + datetime.timedelta(days=n - 1)).isoformat()
    rows = {r["request_id"]: r for r in got["policy_audit.json"]["checks"]}
    eq("policy_audit.json.ids", [q["id"] for q in P["reqs"]], list(rows))
    sc = P["item"]["shift_cost"]
    prio = []
    for q in P["reqs"]:
        s, f = best[3][q["id"]]
        r = rows.get(q["id"], {})
        if s == S + 1:
            eq(q["id"] + ".decision", "deferred", r.get("decision"))
            fits = any(legal(P, q["base"], t, q["p"] - x) for x in range(q["cmax"] + 1)
                       for t in range(q["r"], S + 1))
            eq(q["id"] + ".deferral_reason", "plan_trade" if fits else "no_slot", r.get("deferral_reason"))
            continue
        x = q["p"] - (f - s + 1)
        eq(q["id"] + ".start_date", tday(s), r.get("start_date"))
        eq(q["id"] + ".finish_date", tday(f), r.get("finish_date"))
        eq(q["id"] + ".compress_days", x, r.get("compress_days"))
        eq(q["id"] + ".moved", s != q["ps"], r.get("moved"))
        eq(q["id"] + ".overdue_days", max(0, f - q["due"]), r.get("overdue_days"))
        # invariants on the delivered row
        assert legal(P, q["base"], s, f - s + 1) and s >= q["r"], q["id"]
        if x:
            prio.append(({"widebody": 0, "narrowbody": 1, "regional": 2}[q["cls"]], q["due"], q["id"], q["h"] * x))
    left = sum(P["grants"].values())
    for _, _, rid, h in sorted(prio):
        t = min(h, left)
        left -= t
        r = rows.get(rid, {})
        eq(rid + ".allowance_shifts", t, r.get("allowance_shifts"))
        eq(rid + ".settled_overtime_cost", sc * (h - t), r.get("settled_overtime_cost"))
    for b in BASES:
        mine = [r for r in rows.values() if r["base"] == b]
        reg = got["region_%s.json" % b]
        for k in ("overtime_shifts", "allowance_shifts", "settled_overtime_cost"):
            k2 = "allowance_used" if k == "allowance_shifts" else k
            eq("region_%s.%s" % (b, k2), sum(r[k] for r in mine), reg.get(k2))
    summ = got["summary.json"]
    eq("summary.fleet_overtime_used", used, summ.get("fleet_overtime_used"))
    eq("summary.plan_terms", [best[0], best[1], best[2]],
       [summ["plan_terms"][k] for k in ("first", "second", "third")])
    eq("summary.settlement.allowance_left", left, summ["settlement"]["allowance_left"])
    eq("data_quality.rejected", P["rej"], got["data_quality.json"]["rejected"])
    for x in diffs:
        print(x)
    print("OK" if not diffs else "FAIL %d" % len(diffs))


if __name__ == "__main__":
    main()
