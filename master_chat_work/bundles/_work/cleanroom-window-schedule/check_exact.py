"""Independent recomputation of the ten documents from the visible inputs (G9).

Usage: python3 -B check_exact.py <data_dir> <out_dir>

Never imports solve.py. Nights with at most 12 jobs are solved by plain enumeration of every
assignment (each job: not run, or one bay); larger nights by a top-down memoised recursion.
Every night's optimum count must be 1. Prints one line per differing record and exits 1 on any
difference or failed invariant."""
import collections
import csv
import json
import sys
import tomllib
from functools import lru_cache
from pathlib import Path

sys.setrecursionlimit(10000)


def load(data):
    def rows(name, sep):
        return list(csv.reader(open(data / name, encoding="utf-8"), delimiter=sep))[1:]

    jobs = rows("jobs.csv", ",")
    win = {r[0]: (int(r[1]), int(r[2])) for r in rows("windows.tsv", "\t")}
    bays = json.load(open(data / "bays.json"))["bays"]
    quals, section = {}, None
    for line in open(data / "qualifications.ini", encoding="utf-8"):
        line = line.strip()
        if line.startswith("["):
            section = line[1:-1]
        elif "=" in line:
            quals[section] = [x.strip() for x in line.split("=", 1)[1].split(",") if x.strip()]
    fee = {}
    for n, a, b, f, c in rows("setup_fees.csv", ","):
        fee.setdefault(n, {})[(a, b)] = (int(f), int(c))
    clients = {}
    for line in open(data / "clients.jsonl", encoding="utf-8"):
        if line.strip():
            d = json.loads(line)
            clients[d["client_id"]] = d["site"]
    region = dict(rows("regions.csv", ","))
    segment = dict(rows("segments.tsv", "\t"))
    mand = json.load(open(data / "mandatory.json"))
    audit = tomllib.load(open(data / "audit.toml", "rb"))
    return jobs, win, bays, quals, fee, clients, region, segment, mand, audit


def code_of(nid, rows, counts, win, catalog, clients, fee):
    if any(counts[r[0]] > 1 for r in rows):
        return "E_DUP_JOB"
    if any(r[2] not in win or not (0 <= win[r[2]][0] < win[r[2]][1] <= 1440) for r in rows):
        return "E_BAD_WINDOW"
    if any(r[4] not in catalog or r[3] not in clients for r in rows):
        return "E_UNKNOWN_RESOURCE"
    if any((a, b) not in fee.get(nid, {}) for a in catalog for b in catalog if a != b):
        return "E_BAD_FEE"
    return None


def money(plan, jobs, bays, table, before):
    """Feasibility under the stated rules and the money of a plan {job_id: bay position}."""
    rate = [b["minute_rate"] for b in bays]
    fam = list(before)
    end = [None] * len(bays)
    windows, lines = [], []
    for j in sorted((j for j in jobs if j[0] in plan), key=lambda j: (j[1], j[0])):
        k = plan[j[0]]
        if end[k] is not None and j[1] < end[k]:
            return None
        f = 0
        if j[3] != fam[k]:
            f, c = table[(fam[k], j[3])]
            lo = j[1] - c
            if lo < 0 or (end[k] is not None and lo < end[k]):
                return None
            if any(lo < w1 and w0 < j[1] for w0, w1, _, _ in windows):
                return None
            windows.append((lo, j[1], k, j[0]))
        fam[k], end[k] = j[3], j[2]
        lines.append((j, k, f, j[4] - rate[k] * (j[2] - j[1]) - f))
    return sum(x[3] for x in lines), lines, windows, fam


def tie(plan, ids):
    return [1 if i in plan else 0 for i in ids] + [plan[i] + 1 if i in plan else 0 for i in ids]


def enumerate_night(jobs, bays, quals, table, before, must):
    order = sorted(jobs, key=lambda j: (j[1], j[0]))
    ids = sorted(j[0] for j in jobs)
    best = [None, None, 0]

    def go(i, plan):
        if i == len(order):
            if not must <= set(plan):
                return
            got = money(plan, jobs, bays, table, before)
            if got is None:
                return
            key = (got[0], [-x for x in tie(plan, ids)])
            if best[0] is None or key > best[0]:
                best[:] = [key, dict(plan), 1]
            elif key[0] == best[0][0]:
                best[2] += 1
                if key > best[0]:
                    best[0], best[1] = key, dict(plan)
            return
        j = order[i]
        go(i + 1, plan)
        for k, b in enumerate(bays):
            if j[3] in quals[b["bay_id"]]:
                plan[j[0]] = k
                go(i + 1, plan)
                del plan[j[0]]

    go(0, {})
    return best[1], best[2]


def recurse_night(jobs, bays, quals, table, before, must):
    order = sorted(jobs, key=lambda j: (j[1], j[0]))
    lead = max(c for _, c in table.values())
    rate = [b["minute_rate"] for b in bays]
    NEG = float("-inf")

    @lru_cache(maxsize=None)
    def f(i, lanes, crew):
        if i == len(order):
            return 0, 1
        j = order[i]
        cut = j[1] - lead
        lanes = tuple((fa, e if e > cut else 0) for fa, e in lanes)
        crew = crew if crew > cut else 0
        best, n = NEG, 0
        options = []
        if j[0] not in must:
            options.append((0, lanes, crew))
        for k, b in enumerate(bays):
            fa, e = lanes[k]
            if j[3] not in quals[b["bay_id"]] or j[1] < e:
                continue
            gain, c2 = j[4] - rate[k] * (j[2] - j[1]), crew
            if j[3] != fa:
                fe, c = table[(fa, j[3])]
                if j[1] - c < max(e, crew, 0):
                    continue
                gain -= fe
                c2 = j[1]
            nl = list(lanes)
            nl[k] = (j[3], j[2])
            options.append((gain, tuple(nl), c2))
        for gain, nl, c2 in options:
            v, m = f(i + 1, nl, c2)
            if v == NEG:
                continue
            if v + gain > best:
                best, n = v + gain, m
            elif v + gain == best:
                n += m
        return best, n

    def walk():
        plan, lanes, crew = {}, tuple((fa, 0) for fa in before), 0
        for i, j in enumerate(order):
            cut = j[1] - lead
            lanes = tuple((fa, e if e > cut else 0) for fa, e in lanes)
            crew = crew if crew > cut else 0
            target = f(i, lanes, crew)[0]
            if j[0] not in must and f(i + 1, lanes, crew)[0] == target:
                continue
            for k, b in enumerate(bays):
                fa, e = lanes[k]
                if j[3] not in quals[b["bay_id"]] or j[1] < e:
                    continue
                gain, c2 = j[4] - rate[k] * (j[2] - j[1]), crew
                if j[3] != fa:
                    fe, c = table[(fa, j[3])]
                    if j[1] - c < max(e, crew, 0):
                        continue
                    gain -= fe
                    c2 = j[1]
                nl = list(lanes)
                nl[k] = (j[3], j[2])
                if f(i + 1, tuple(nl), c2)[0] + gain == target:
                    plan[j[0]] = k
                    lanes, crew = tuple(nl), c2
                    break
        return plan

    total, count = f(0, tuple((fa, 0) for fa in before), 0)
    plan = walk() if count == 1 else None
    f.cache_clear()
    return plan, count


def expected(data):
    jobs, win, bays, quals, fee, clients, region, segment, mand, audit = load(data)
    catalog = quals["catalog"]
    counts = collections.Counter(r[0] for r in jobs)
    by_night = collections.defaultdict(list)
    for r in jobs:
        by_night[r[1]].append(r)
    th = audit["thresholds"]
    holding = [b["initial_family"] for b in bays]
    bay_ids = [b["bay_id"] for b in bays]
    nights, pol, dq = [], [], []
    roll = {("region", g): [] for g in ("North", "South", "West", "East")}
    roll.update({("segment", g): [] for g in ("commercial", "public")})
    for night in sorted(audit["night"], key=lambda n: n["date"]):
        nid = night["id"]
        rows = by_night.get(nid, [])
        code = code_of(nid, rows, counts, win, catalog, clients, fee)
        if code:
            dq.append({"code": code, "message": "night %s rejected: %s" % (nid, code), "night_id": nid})
            nights.append({"bay_charge": 0, "date": night["date"], "fees": 0, "gross": 0, "net": 0,
                           "night_id": nid, "plan": [], "status": "rejected"})
            pol.append({"crew_minutes": 0, "crew_windows": [], "families_after": dict(zip(bay_ids, holding)),
                        "flags": [], "night_id": nid, "status": "rejected"})
            continue
        js = [(r[0], win[r[2]][0], win[r[2]][1], r[4], int(r[5]), r[3]) for r in rows]
        must = set(mand.get(nid, []))
        table = fee[nid]
        solver = enumerate_night if len(js) <= 12 else recurse_night
        plan, count = solver(js, bays, quals, table, tuple(holding), frozenset(must)) if js else ({}, 1)
        assert count == 1, (nid, count)
        net, lines, windows, after = money(plan, js, bays, table, holding)
        holding = after
        gross = sum(x[0][4] for x in lines)
        fees = sum(x[2] for x in lines)
        nights.append({"bay_charge": gross - fees - net, "date": night["date"], "fees": fees, "gross": gross,
                       "net": net, "night_id": nid, "status": "accepted",
                       "plan": [{"bay_id": bay_ids[k], "changeover_fee": f, "end": j[2], "family": j[3],
                                 "job_id": j[0], "start": j[1]} for j, k, f, _ in lines]})
        cm = sum(w[1] - w[0] for w in windows)
        flags = sorted(x for x, on in (("crew_load_high", cm > th["crew_minutes_limit"]),
                                       ("low_margin", net < th["margin_floor"])) if on)
        pol.append({"crew_minutes": cm, "night_id": nid, "status": "accepted", "flags": flags,
                    "families_after": dict(zip(bay_ids, holding)),
                    "crew_windows": [{"bay_id": bay_ids[k], "end": e, "job_id": i, "start": s}
                                     for s, e, k, i in sorted(windows)]})
        for (kind, g), out in roll.items():
            mine = [x for x in lines if (region[clients[x[0][5]]] if kind == "region" else segment[x[0][5]]) == g]
            out.append({"gross": sum(x[0][4] for x in mine), "jobs_run": len(mine), "net": sum(x[3] for x in mine),
                        "night_id": nid})
    docs = {"summary.json": {"nights": nights, "totals": {
        "accepted_nights": sum(n["status"] == "accepted" for n in nights), "rejected_nights": len(dq),
        "jobs_run": sum(len(n["plan"]) for n in nights),
        **{k: sum(n[k] for n in nights) for k in ("gross", "bay_charge", "fees", "net")}}},
        "policy_audit.json": {"nights": pol}, "data_quality.json": {"rejected": dq}}
    for (kind, g), out in roll.items():
        docs["%s_%s.json" % (kind, g)] = {kind: g, "nights": out,
                                          "totals": {k: sum(e[k] for e in out) for k in ("jobs_run", "gross", "net")}}
    return docs


def diff(a, b, path="$"):
    if type(a) is not type(b):
        return path
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return path + "." + k
            d = diff(a[k], b[k], path + "." + k)
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return path + ".length"
        for i, (x, y) in enumerate(zip(a, b)):
            d = diff(x, y, "%s[%d]" % (path, i))
            if d:
                return d
        return None
    return None if a == b else path


def invariants(docs):
    for n in docs["policy_audit.json"]["nights"]:
        w = n["crew_windows"]
        assert all(x["end"] <= y["start"] for x, y in zip(w, w[1:])), n["night_id"]
        assert n["crew_minutes"] == sum(x["end"] - x["start"] for x in w)
    s = docs["summary.json"]
    for n in s["nights"]:
        assert n["net"] == n["gross"] - n["bay_charge"] - n["fees"], n["night_id"]
    for kind, groups in (("region", ("North", "South", "West", "East")), ("segment", ("commercial", "public"))):
        assert sum(docs["%s_%s.json" % (kind, g)]["totals"]["net"] for g in groups) == s["totals"]["net"]


def main():
    data, out = Path(sys.argv[1]), Path(sys.argv[2])
    want = expected(data)
    invariants(want)
    bad = 0
    for name, doc in sorted(want.items()):
        got = json.loads((out / name).read_text())
        d = diff(doc, got)
        if d:
            bad += 1
            print("DIFF %s at %s" % (name, d))
        else:
            print("same %s" % name)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
