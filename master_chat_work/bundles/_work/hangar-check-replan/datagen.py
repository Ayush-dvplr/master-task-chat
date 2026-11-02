"""Seeded generator for hangar-check-replan (stdlib only).

Writes one data folder: fleet_register.csv, check_requests.csv, published_plan.csv, base_calendar.jsonl,
disruption_notice.docx, planning_limits.docx, check_types.json, fleet_limits.toml.
Usage: python3 -B datagen.py OUTDIR            (shipped sample, seed 2)
       python3 -B datagen.py OUTDIR hidden SEED EMPTY STYPE X1   (one held-out corpus, for checks)
The same code is embedded in tests/test_output.py (the block between the GEN markers)."""
# ---- GEN BEGIN ----
import copy
import csv
import datetime as dt
import json
import os
import random
import re
import string
import sys
import tomllib
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

BASES = ["North", "South", "West", "East"]
SEGMENTS = {"commercial": ("widebody", "narrowbody"), "public": ("regional",)}
REASONS = ["duplicate_request", "unknown_base", "unknown_check_type", "unknown_tail", "retired_tail", "bad_date",
           "bad_duration", "no_published_start"]
TYPES = {"A": {"c": 1, "h": 2, "p": (2, 4)}, "C": {"c": 2, "h": 3, "p": (6, 10)}, "D": {"c": 3, "h": 4, "p": (12, 18)}}
CLASSES = {"widebody": {"rev": 90, "w": 6, "pen": 400}, "narrowbody": {"rev": 50, "w": 4, "pen": 260},
           "regional": {"rev": 20, "w": 2, "pen": 30}}
RANK = {"widebody": 0, "narrowbody": 1, "regional": 2}
SEASONS = [("2025A", dt.date(2025, 3, 1)), ("2025B", dt.date(2025, 9, 1)), ("2026A", dt.date(2026, 3, 1)),
           ("2026B", dt.date(2026, 9, 1)), ("2027A", dt.date(2027, 3, 1)), ("2027B", dt.date(2027, 9, 1)),
           ("2028A", dt.date(2028, 3, 1))]
CAL0, CAL1 = dt.date(2025, 1, 1), dt.date(2029, 12, 31)


# ---------- exact season plan on the abstract instance ----------
def _frontier(inst, base, checks):
    """Per base: overtime used -> best (T1, T2, T3, starts, finishes, compress) over orders of its checks."""
    S, rate = inst["S"], inst["shift_cost"]
    closed, nostart = set(inst["closed"][base]), set(inst["nostart"][base])
    cls, typ = inst["classes"], inst["types"]
    n = len(checks)
    memo, es_memo = {}, {}

    def ok(s, dur):
        return s not in nostart and s + dur - 1 <= S and not any(d in closed for d in range(s, s + dur))

    def es(t, dur):
        if (t, dur) not in es_memo:
            s = t
            while s + dur - 1 <= S and not ok(s, dur):
                s += 1
            es_memo[(t, dur)] = s if s + dur - 1 <= S else None
        return es_memo[(t, dur)]

    def best(mask, tfree):
        key = (mask, tfree)
        if key in memo:
            return memo[key]
        if mask == 0:
            z = (0,) * n
            memo[key] = ((0, (0, 0, 0, z, z, z)),)
            return memo[key]
        out = {}
        for j in range(n):
            if not mask >> j & 1:
                continue
            ch, rest = checks[j], mask & ~(1 << j)
            c, ty = cls[ch["cls"]], typ[ch["type"]]
            lo, ps = max(tfree, ch["r"]), ch["ps"]
            opts = [(S + 1, S + 1, 0, c["pen"], 0, 1, 0)]
            for x in range(0, min(ty["c"], ch["p"] - 1) + 1):
                dur = ch["p"] - x
                a = es(lo, dur)
                if a is None:
                    continue
                cand = [a] + ([ps] if ps > a and ok(ps, dur) else [])
                for s in cand:
                    f = s + dur - 1
                    opts.append((s, f, x, max(0, f - ch["due"]) * c["w"], c["rev"] * dur + rate * ty["h"] * x,
                                 int(s != ps), ty["h"] * x))
            for s, f, x, a1, a2, a3, ot in opts:
                for o, v in best(rest, tfree if s > S else f + 1):
                    cand = (v[0] + a1, v[1] + a2, v[2] + a3, v[3][:j] + (s,) + v[3][j + 1:],
                            v[4][:j] + (f,) + v[4][j + 1:], v[5][:j] + (x,) + v[5][j + 1:])
                    cur = out.get(o + ot)
                    if cur is None or cand < cur:
                        out[o + ot] = cand
        res, bestv = [], None
        for o in sorted(out):
            if bestv is None or out[o] < bestv:
                res.append((o, out[o]))
                bestv = out[o]
        memo[key] = tuple(res)
        return memo[key]

    return dict(best((1 << n) - 1, 1))


def solve(inst, cache=None):
    """Exact optimum: per-base frontiers merged over the shared pool, ties by the fleet start/finish vectors."""
    cache = {} if cache is None else cache
    checks = sorted(inst["checks"], key=lambda c: c["id"])
    pos = {c["id"]: i for i, c in enumerate(checks)}
    S, N = inst["S"], len(checks)
    per = {}
    for b in inst["bases"]:
        cb = [c for c in checks if c["base"] == b]
        key = json.dumps([b, inst["S"], inst["shift_cost"], inst["closed"][b], inst["nostart"][b], cb], sort_keys=True)
        if key not in cache:
            cache[key] = _frontier(inst, b, cb)
        per[b] = (cb, cache[key])
    states = {0: (0, 0, 0, (S + 1,) * N, (S + 1,) * N, ())}
    for b in inst["bases"]:
        cb, fr = per[b]
        new = {}
        for u, sv in states.items():
            for o, v in fr.items():
                if u + o > inst["K"]:
                    continue
                st, fi = list(sv[3]), list(sv[4])
                for k, ch in enumerate(cb):
                    st[pos[ch["id"]]], fi[pos[ch["id"]]] = v[3][k], v[4][k]
                cand = (sv[0] + v[0], sv[1] + v[1], sv[2] + v[2], tuple(st), tuple(fi), sv[5] + (o,))
                cur = new.get(u + o)
                if cur is None or cand[:5] < cur[:5]:
                    new[u + o] = cand
        states = new
    win = min(states.values(), key=lambda v: v[:5])
    plan = {}
    for bi, b in enumerate(inst["bases"]):
        cb, fr = per[b]
        v = fr[win[5][bi]]
        for k, ch in enumerate(cb):
            plan[ch["id"]] = (v[3][k], v[4][k], v[5][k])
    return {"T": list(win[:3]), "used": sum(win[5]), "plan": plan}


# ---------- abstract instance ----------
def make(mode, seed, n, empty_axes=False):
    rng = random.Random(seed)
    rare = random.Random(seed * 7919 + 17)
    hidden = mode == "hidden"
    eb = rare.choice(BASES) if empty_axes else None
    live = [b for b in BASES if b != eb]
    tight = rng.choice(live) if hidden else None
    noslot_base = rare.choice([b for b in live if b != tight]) if hidden else rng.choice(BASES)
    S = 160 if empty_axes else (rng.randint(120, 130) if hidden else 120)
    cls_names = ["widebody", "narrowbody"] if empty_axes else list(CLASSES)
    cls_w = [2, 3] if empty_axes else [2, 3, 3]
    inst = {"S": S, "bases": list(BASES), "shift_cost": 15,
            "classes": {k: dict(v) for k, v in CLASSES.items()},
            "types": {k: {"c": v["c"], "h": v["h"]} for k, v in TYPES.items()},
            "closed": {b: [] for b in BASES}, "nostart": {}, "checks": []}
    ids = rng.sample(range(10000, 99999), 4 * n + 4)
    k = 0
    twin = None
    for b in BASES:
        t = 1 + rng.randint(0, 3)
        nost = sorted(rng.sample(range(1, S + 1), S // 10))
        inst["nostart"][b] = nost
        if b == eb:
            continue
        for i in range(n):
            ty = rng.choices("ACD", weights=[3, 4, 2])[0]
            p = rng.randint(*TYPES[ty]["p"])
            cl = rng.choices(cls_names, weights=cls_w)[0]
            ps = t
            while ps in nost:
                ps += 1
            due = ps + p - 1 + rng.randint(0, 4)
            r = ps
            if hidden and rng.random() < 0.45:
                r = max(1, ps - rng.randint(1, 6))
            if hidden and i == 1:
                if twin is None:
                    twin = (ty, p, cl, due - ps, ps - r)
                else:
                    ty, p, cl = twin[0], twin[1], twin[2]
                    due, r = ps + twin[3], max(1, ps - twin[4])
            inst["checks"].append({"id": "Q%05d" % ids[k], "base": b, "cls": cl, "type": ty, "p": p,
                                   "ps": ps, "due": due, "r": r})
            k += 1
            t = ps + p + (0 if b == tight else rng.randint(0, 2))
        if b == tight:
            ps = t
            while ps in nost:
                ps += 1
            gcl = "narrowbody" if empty_axes else "regional"
            p = rng.randint(12, 14) if gcl == "regional" else rng.randint(7, 9)
            gty = "D" if gcl == "regional" else "C"
            c = inst["classes"][gcl]
            L = min(c["pen"] // c["w"] + rng.randint(5, 9), S - ps - p)
            if L % 10 == 0:
                L -= 1
            inst["checks"].append({"id": "Q%05d" % ids[k], "base": b, "cls": gcl, "type": gty, "p": p,
                                   "ps": ps, "due": ps + p - 1, "r": ps})
            k += 1
            inst["closed"][b] = list(range(ps + 1, ps + 1 + L))
        elif rng.random() < 0.8:
            c0 = rng.randint(10, max(11, min(S - 10, t - 10)))
            inst["closed"][b] = list(range(c0, c0 + rng.randint(11, 19)))
    # one check that cannot finish by season end at any compression (deferred, no_slot)
    p = rare.randint(12, 18)
    mind = p - 3
    if hidden:
        cstart = S - rare.randint(15, 25) + 1
        r = cstart - rare.randint(3, mind - 1)
        inst["closed"][noslot_base] = sorted(set(inst["closed"][noslot_base]) | set(range(cstart, S + 1)))
    else:
        r = S - mind + 1 + rare.randint(1, 4)
    while r in inst["nostart"][noslot_base]:
        r -= 1
    inst["checks"].append({"id": "Q%05d" % ids[k], "base": noslot_base, "cls": "widebody" if empty_axes
                           else rare.choice(list(CLASSES)), "type": "D", "p": p, "ps": r, "due": r + p - 1, "r": r})
    inst["meta"] = {"mode": mode, "seed": seed, "empty_base": eb, "empty_segment": "public" if empty_axes else None,
                    "tight": tight, "noslot_base": noslot_base, "noslot_id": "Q%05d" % ids[k]}
    inst["K"] = 10 ** 6
    free = solve(inst)["used"]
    inst["K"] = int(0.5 * free) if hidden else free
    if hidden and inst["K"] % 10 == 0:
        inst["K"] -= 1
    inst["meta"]["free_used"] = free
    return inst


# ---------- overtime allowance (own RNG stream) ----------
def priority(rows):
    """Settlement order: class widebody, narrowbody, regional; earlier due date; smaller request_id."""
    return sorted(rows, key=lambda r: (RANK[r["aircraft_class"]], r["due"], r["request_id"]))


def ot_rows(inst, res):
    rows = []
    for c in inst["checks"]:
        s, f, x = res["plan"][c["id"]]
        h = inst["types"][c["type"]]["h"] * x
        if s <= inst["S"] and h:
            rows.append({"request_id": c["id"], "base": c["base"], "aircraft_class": c["cls"], "start": s,
                         "due": c["due"], "overtime_shifts": h})
    return rows


def plant_pair(inst, rows, g, cache):
    """Two overtime checks of one class at two bases get the same due date, so the request_id decides their
    settlement order (smaller id at the later base); keep a candidate whose re-solved plan has the allowance
    run out inside the first of them. -> (A, pair) or None"""
    bi = inst["bases"].index
    cands = [(a, b) for a in rows for b in rows if a["aircraft_class"] == b["aircraft_class"]
             and a["request_id"] < b["request_id"] and bi(a["base"]) > bi(b["base"]) and a["overtime_shifts"] >= 2]
    g.shuffle(cands)
    for a, b in cands[:12]:
        trial = copy.deepcopy(inst)
        due = max(a["due"], b["due"])
        for c in trial["checks"]:
            if c["id"] in (a["request_id"], b["request_id"]):
                c["due"] = due
        rs = ot_rows(trial, solve(trial, cache))
        got = {r["request_id"]: r for r in rs}
        if a["request_id"] not in got or b["request_id"] not in got or got[a["request_id"]]["overtime_shifts"] < 2:
            continue
        u = sum(r["overtime_shifts"] for r in rs)
        cum = 0
        for r in priority(rs):
            if r["request_id"] == a["request_id"]:
                break
            cum += r["overtime_shifts"]
        if 0.3 * u <= cum <= 0.8 * u:
            inst["checks"] = trial["checks"]
            return cum + g.randint(1, got[a["request_id"]]["overtime_shifts"] - 1), [a["request_id"], b["request_id"]]
    return None


def grants_for(inst, stype):
    """Fleet allowance A against the optimal plan's overtime U, split into four base grants."""
    meta = inst["meta"]
    g = random.Random(meta["seed"] * 31337 + 5)
    cache, pair, A = {}, None, None
    if stype == "bind":
        got = plant_pair(inst, ot_rows(inst, solve(inst, cache)), g, cache)
        if got:
            A, pair = got
    rows = ot_rows(inst, solve(inst, cache))
    U = sum(r["overtime_shifts"] for r in rows)
    ub = {b: sum(r["overtime_shifts"] for r in rows if r["base"] == b) for b in inst["bases"]}
    if stype == "slack":
        A = U + g.randint(6, 12)
    elif stype == "cap":
        A = U
    elif stype == "short":
        A = U - 1
    elif pair is None:
        A = int(U * g.uniform(0.4, 0.7))
    if meta["mode"] == "shipped":
        gr = dict(ub)
        for _ in range(A - U):
            gr[g.choice(inst["bases"])] += 1
    else:
        gr = None
        for _ in range(500):
            w = {b: g.uniform(0.5, 1.5) for b in inst["bases"]}
            tw = sum(w.values())
            gr = {b: int(A * w[b] / tw) for b in inst["bases"]}
            gr[inst["bases"][0]] += A - sum(gr.values())
            if any(ub[b] > gr[b] for b in inst["bases"]) and all(v > 0 for v in gr.values()):
                break
        assert gr and all(v >= 0 for v in gr.values()) and sum(gr.values()) == A
    meta.update({"grants": gr, "A": A, "U": U, "U_b": ub, "stype": stype, "pair": pair})
    return inst


# ---------- Word packages ----------
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _wrun(t):
    return '<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % escape(str(t))


def write_docx(path, blocks):
    """blocks: ("p", text) or ("tbl", rows). Plain WordprocessingML package, fixed timestamps."""
    body = []
    for kind, val in blocks:
        if kind == "p":
            body.append("<w:p>%s</w:p>" % _wrun(val))
        else:
            trs = "".join("<w:tr>%s</w:tr>" % "".join("<w:tc><w:p>%s</w:p></w:tc>" % _wrun(c) for c in row)
                          for row in val)
            body.append('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/></w:tblPr>%s</w:tbl>' % trs)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="%s"><w:body>%s<w:sectPr/>'
           '</w:body></w:document>' % (_W, "".join(body)))
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/'
          'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
          'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/'
          'document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"'
          '/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
            'openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
    with zipfile.ZipFile(path, "w") as z:
        for name, data in (("[Content_Types].xml", ct), ("_rels/.rels", rels), ("word/document.xml", doc)):
            info = zipfile.ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)


# ---------- data folder ----------
def render(inst, outdir, x1=False):
    """Write the eight data files for one abstract instance."""
    meta = inst["meta"]
    seed = meta["seed"]
    rng = random.Random(seed * 31 + 5)
    xr = random.Random(seed * 7349 + 11)
    hidden = meta["mode"] == "hidden"
    season, sstart = SEASONS[4] if not hidden else rng.choice(SEASONS[2:])
    S = inst["S"]
    iso = dt.date.isoformat

    def day(d):
        return sstart + dt.timedelta(days=d - 1)
    os.makedirs(outdir, exist_ok=True)
    used = set()

    def new_tail():
        while True:
            t = "VT-" + "".join(rng.choice(string.ascii_uppercase) for _ in range(3))
            if t not in used:
                used.add(t)
                return t
    register = [[new_tail(), rng.choices(list(CLASSES), weights=[2, 3, 3])[0],
                 rng.choice(["IndiGo Air", "Vistara Regional", "Coastal Link", "Deccan Wings"]), "ACTIVE"]
                for _ in range(2600)]
    for row in rng.sample(register, 120):
        row[3] = "RETIRED"
    tail_of = {}
    for ch in inst["checks"]:
        t = new_tail()
        tail_of[ch["id"]] = t
        register.append([t, ch["cls"], rng.choice(["IndiGo Air", "Vistara Regional", "Coastal Link"]), "ACTIVE"])
    retired = [r[0] for r in register if r[3] == "RETIRED"]
    rng.shuffle(register)
    rows, pub = [], []
    rid_pool = iter(rng.sample(range(100000, 999999), 9000))
    planned_tails = set(tail_of.values())
    active = [r for r in register if r[3] == "ACTIVE" and r[0] not in planned_tails]
    for sn, s0 in SEASONS:
        if sn == season:
            continue
        for _ in range(900):
            rid = "R%06d" % next(rid_pool)
            ty = rng.choice("ACD")
            p = rng.randint(*TYPES[ty]["p"])
            a = s0 + dt.timedelta(days=rng.randint(0, 150))
            rows.append([rid, sn, rng.choice(active)[0], ty, rng.choice(BASES), iso(a),
                         iso(a + dt.timedelta(days=p + rng.randint(0, 9))), str(p),
                         rng.choice(["DONE", "DONE", "CANCELLED"])])
            pub.append([rid, iso(a + dt.timedelta(days=rng.randint(0, 3)))])
    notice_avail, plan_rows = [], []
    for ch in inst["checks"]:
        a = day(ch["r"])
        noted = False
        if hidden and ch["r"] < ch["ps"] and rng.random() < 0.5:
            notice_avail.append((tail_of[ch["id"]], iso(a)))
            a = day(ch["ps"] + rng.randint(1, 5))
            noted = True
        elif not hidden and rng.random() < 0.15:
            notice_avail.append((tail_of[ch["id"]], iso(a)))
            a = day(max(1, ch["r"] - rng.randint(1, 5)))
        if hidden and not noted and ch["r"] == 1:
            a = day(1 - xr.randint(1, 10))      # available before the season opens: clipped to day 1
        plan_rows.append([ch["id"], season, tail_of[ch["id"]], ch["type"], ch["base"], iso(a), iso(day(ch["due"])),
                          str(ch["p"]), "OPEN"])
        pub.append([ch["id"], iso(day(ch["ps"]))])
    extra = []

    def base_row(b=None):
        rid = "Q%05d" % rng.randint(10000, 99999)
        while any(r[0] == rid for r in plan_rows + extra):
            rid = "Q%05d" % rng.randint(10000, 99999)
        ty = rng.choice("ACD")
        p = rng.randint(*TYPES[ty]["p"])
        a = rng.randint(1, S - 30)
        return [rid, season, rng.choice(active)[0], ty, b or rng.choice(BASES), iso(day(a)),
                iso(day(a + p + 3)), str(p), "OPEN"]
    for _ in range(25):
        r = base_row()
        r[8] = "CANCELLED"
        extra.append(r)
        pub.append([r[0], r[5]])
    kinds = ["unknown_tail", "retired_tail", "bad_date", "bad_duration", "unknown_base", "unknown_check_type",
             "no_published_start"]
    eb = meta["empty_base"]
    todo = list(kinds) + (["retired_tail", "bad_date", "bad_duration"] if eb else [])
    for j, kd in enumerate(todo):
        r = base_row(eb if j >= len(kinds) else None)
        if kd == "unknown_tail":
            r[2] = "VT-" + "".join(rng.choice("0123456789") for _ in range(3))
        elif kd == "retired_tail":
            r[2] = rng.choice(retired)
        elif kd == "bad_date":
            r[6] = rng.choice(["2027-02-30", r[6].replace("-", "/"), "31-12-2027"])
        elif kd == "bad_duration":
            r[7] = rng.choice(["0", "-4", "7.5", "ten"])
        elif kd == "unknown_base":
            r[4] = rng.choice(["Central", "north", "Hub"])
        elif kd == "unknown_check_type":
            r[3] = rng.choice(["B", "E", "a"])
        if kd != "no_published_start":
            pub.append([r[0], r[5]])
        extra.append(r)
    if eb:
        for _ in range(2):
            r = base_row(eb)
            r[8] = "CANCELLED"
            extra.append(r)
            pub.append([r[0], r[5]])
    dup = list(rng.choice(plan_rows))
    dup[6] = iso(dt.date.fromisoformat(dup[6]) + dt.timedelta(days=7))
    allrows = rows + plan_rows + extra
    rng.shuffle(allrows)
    pos = rng.randint(len(allrows) // 2, len(allrows))
    first = next(i for i, r in enumerate(allrows) if r[0] == dup[0])
    allrows.insert(max(pos, first + 1), dup)
    if x1:
        # a cancelled row of this season, earlier in the file, carries the id of a planned request
        pick = xr.choice([r for r in plan_rows if r[0] not in (dup[0], meta["noslot_id"])])
        at = next(i for i, r in enumerate(allrows) if r is pick)
        old = list(pick)
        old[2], old[8] = xr.choice(active)[0], "CANCELLED"
        old[5] = iso(dt.date.fromisoformat(old[5]) - dt.timedelta(days=xr.randint(5, 20)))
        allrows.insert(xr.randint(0, at), old)
        meta["x1_id"] = pick[0]
    late_pub = []
    if hidden:
        # held-out rows with two faults each (adjacent pairs of the rejection order) and one bad
        # available_from; own random stream, appended last, so the rest of the folder is unchanged
        tr = random.Random(seed * 911 + 3)
        taken = {r[0] for r in allrows} | {p[0] for p in pub}

        def fresh():
            rid = "Q%05d" % tr.randint(10000, 99999)
            while rid in taken:
                rid = "Q%05d" % tr.randint(10000, 99999)
            taken.add(rid)
            ty = tr.choice("ACD")
            p = tr.randint(*TYPES[ty]["p"])
            a = tr.randint(1, S - 30)
            return [rid, season, tr.choice(active)[0], ty, tr.choice(BASES), iso(day(a)),
                    iso(day(a + p + 3)), str(p), "OPEN"]
        meta["two_fault"] = []
        twin = list(tr.choice([r for r in plan_rows if r[0] != dup[0]]))
        twin[4] = tr.choice(["Central", "north", "Hub"])
        plan = [(twin, "duplicate_request", False)]
        r = fresh(); r[4] = tr.choice(["Central", "north", "Hub"]); r[3] = tr.choice(["B", "E", "a"])
        plan.append((r, "unknown_base", True))
        r = fresh(); r[3] = tr.choice(["B", "E", "a"]); r[2] = "VT-" + "".join(tr.choice("0123456789") for _ in range(3))
        plan.append((r, "unknown_check_type", True))
        r = fresh(); r[2] = "VT-" + "".join(tr.choice("0123456789") for _ in range(3)); r[6] = "2027-02-30"
        plan.append((r, "unknown_tail", True))
        r = fresh(); r[2] = tr.choice(retired); r[6] = tr.choice(["2027-02-30", "31-12-2027"])
        plan.append((r, "retired_tail", True))
        r = fresh(); r[6] = tr.choice(["2027-02-30", r[6].replace("-", "/")]); r[7] = tr.choice(["0", "-4", "7.5", "ten"])
        plan.append((r, "bad_date", True))
        r = fresh(); r[7] = tr.choice(["0", "7.5", "ten"])
        plan.append((r, "bad_duration", False))
        r = fresh(); r[5] = tr.choice(["2027-13-45", r[5].replace("-", "/"), "04-03-2027"])
        plan.append((r, "bad_date", True))
        for r, why, published in plan:
            allrows.append(r)
            meta["two_fault"].append([len(allrows) + 1, r[0], why])
            if published:
                late_pub.append([r[0], iso(day(1 + len(late_pub)))])
    with open(os.path.join(outdir, "check_requests.csv"), "w") as f:
        f.write("request_id,season,tail,check_type,base,available_from,due_date,duration_days,status\n")
        f.writelines(",".join(r) + "\n" for r in allrows)
    rng.shuffle(pub)
    pub.extend(late_pub)
    with open(os.path.join(outdir, "published_plan.csv"), "w") as f:
        f.write("request_id,published_start\n")
        f.writelines(",".join(r) + "\n" for r in pub)
    with open(os.path.join(outdir, "fleet_register.csv"), "w") as f:
        f.write("tail,aircraft_class,operator,status\n")
        f.writelines(",".join(r) + "\n" for r in register)
    notice_closed, cal_closed = [], {b: set() for b in BASES}
    for b in BASES:
        runs = []
        for d in sorted(inst["closed"].get(b, [])):
            if runs and d == runs[-1][1] + 1:
                runs[-1][1] = d
            else:
                runs.append([d, d])
        for a, z in runs:
            # held-out folders: every closure that ends inside the season is in the notice
            if z == S or (not hidden and b != meta.get("tight") and rng.random() < 0.4):
                cal_closed[b].update(range(a, z + 1))
            else:
                notice_closed.append((b, iso(day(a)), z - a + 1))
    with open(os.path.join(outdir, "base_calendar.jsonl"), "w") as f:
        for b in BASES:
            ns = set(inst["nostart"][b])
            d = CAL0
            while d <= CAL1:
                k = (d - sstart).days + 1
                if 1 <= k <= S:
                    st = "CLOSED" if k in cal_closed[b] else ("NO_START" if k in ns else "OPEN")
                else:
                    u = rng.random()
                    st = "CLOSED" if u < 0.02 else ("NO_START" if u < 0.06 else "OPEN")
                f.write(json.dumps({"base": b, "date": iso(d), "status": st}) + "\n")
                d += dt.timedelta(days=1)
    for _ in range(3):
        notice_avail.append((rng.choice(active)[0], iso(day(rng.randint(1, S)))))
    rng.shuffle(notice_avail)
    closures = sorted(notice_closed, key=lambda c: (c[1], c[0]))
    write_docx(os.path.join(outdir, "disruption_notice.docx"), [
        ("p", "Disruption notice for season %s" % season),
        ("p", "Issued by Maintenance Control after the published plan."), ("p", "Base closures"),
        ("tbl", [["base", "from", "days"]] + [[b, a, str(n)] for b, a, n in closures]),
        ("p", "Revised availability"), ("tbl", [["tail", "available_from"]] + [[t, a] for t, a in notice_avail])])
    gr = meta["grants"]
    write_docx(os.path.join(outdir, "planning_limits.docx"), [
        ("p", "Planning limits for season %s" % season), ("p", "Overtime pool"),
        ("tbl", [["item", "value"], ["overtime_pool_shifts", str(inst["K"])], ["shift_cost", str(inst["shift_cost"])]]),
        ("p", "Class rates"),
        ("tbl", [["class", "revenue_per_day", "overdue_weight", "deferral_penalty"]] +
         [[c, str(v["rev"]), str(v["w"]), str(v["pen"])] for c, v in inst["classes"].items()]),
        ("p", "Overtime allowance"),
        ("tbl", [["base", "allowance_shifts"]] + [[b, str(gr[b])] for b in inst["bases"]])])
    with open(os.path.join(outdir, "check_types.json"), "w") as f:
        json.dump({k: {"max_compress_days": v["c"], "overtime_shifts_per_day": v["h"]}
                   for k, v in inst["types"].items()}, f, indent=2)
        f.write("\n")
    with open(os.path.join(outdir, "fleet_limits.toml"), "w") as f:
        f.write('season = "%s"\nseason_start = "%s"\nseason_end = "%s"\n'
                % (season, iso(sstart), iso(sstart + dt.timedelta(days=S - 1))))
    return inst


# ---------- expected outputs, read back from a data folder ----------
def _docx_tables(path):
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    with zipfile.ZipFile(path) as z:
        rels = ET.fromstring(z.read("_rels/.rels"))
        main = next(r.get("Target") for r in rels.iter(rel_ns + "Relationship")
                    if r.get("Type", "").endswith("/officeDocument")).lstrip("/")
        root = ET.fromstring(z.read(main))
    out = {}
    for tbl in root.iter("{%s}tbl" % ns["w"]):
        rows = [["".join(t.text or "" for t in tc.iter("{%s}t" % ns["w"])).strip()
                 for tc in tr.findall("w:tc", ns)] for tr in tbl.findall("w:tr", ns)]
        if rows:
            out.setdefault("/".join(rows[0][:2]), [dict(zip(rows[0], r)) for r in rows[1:]])
    return out


def _date(s):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        raise ValueError(s)
    return dt.date.fromisoformat(s)


def derive(data):
    """Return {output file name: object} for one data folder."""
    P = lambda f: os.path.join(data, f)
    with open(P("fleet_limits.toml"), "rb") as f:
        lim = tomllib.load(f)
    tabs = _docx_tables(P("planning_limits.docx"))
    tabs.update(_docx_tables(P("disruption_notice.docx")))
    for r in tabs["item/value"]:
        lim[r["item"]] = int(r["value"])
    rates = {r["class"]: {"rev": int(r["revenue_per_day"]), "w": int(r["overdue_weight"]),
                          "pen": int(r["deferral_penalty"])} for r in tabs["class/revenue_per_day"]}
    grants = {b: 0 for b in BASES}
    for r in tabs["base/allowance_shifts"]:
        grants[r["base"]] = int(r["allowance_shifts"])
    closures = tabs["base/from"]
    with open(P("check_types.json")) as f:
        types = json.load(f)
    with open(P("fleet_register.csv")) as f:
        reg = {r["tail"]: r for r in csv.DictReader(f)}
    with open(P("published_plan.csv")) as f:
        pub = {r["request_id"]: r["published_start"] for r in csv.DictReader(f)}
    s0, s1 = _date(lim["season_start"]), _date(lim["season_end"])
    S = (s1 - s0).days + 1
    dn = lambda d: (d - s0).days + 1
    dd = lambda k: (s0 + dt.timedelta(days=k - 1)).isoformat()
    avail = {r["tail"]: r["available_from"] for r in tabs["tail/available_from"]}
    rejected, seen, planning = [], set(), []
    with open(P("check_requests.csv")) as f:
        for line, r in enumerate(csv.DictReader(f), start=2):
            if r["season"] != lim["season"] or r["status"] != "OPEN":
                continue
            rid, why = r["request_id"], None
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
                    _date(r["available_from"]), _date(r["due_date"])
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
    with open(P("base_calendar.jsonl")) as f:
        for ln in f:
            if not ln.strip():
                continue
            c = json.loads(ln)
            k = dn(_date(c["date"]))
            if 1 <= k <= S and c["base"] in closed:
                if c["status"] == "CLOSED":
                    closed[c["base"]].add(k)
                elif c["status"] == "NO_START":
                    nostart[c["base"]].add(k)
    for c in closures:
        a = dn(_date(c["from"]))
        for k in range(a, a + int(c["days"])):
            if 1 <= k <= S:
                closed[c["base"]].add(k)
    checks = []
    for r in planning:
        checks.append({"id": r["request_id"], "base": r["base"], "cls": reg[r["tail"]]["aircraft_class"],
                       "type": r["check_type"], "p": int(r["duration_days"]), "ps": dn(_date(pub[r["request_id"]])),
                       "due": dn(_date(r["due_date"])),
                       "r": max(1, dn(_date(avail.get(r["tail"], r["available_from"])))), "tail": r["tail"]})
    inst = {"S": S, "bases": BASES, "shift_cost": lim["shift_cost"], "K": lim["overtime_pool_shifts"],
            "classes": rates,
            "types": {t: {"c": v["max_compress_days"], "h": v["overtime_shifts_per_day"]} for t, v in types.items()},
            "closed": {b: sorted(v) for b, v in closed.items()}, "nostart": {b: sorted(v) for b, v in nostart.items()},
            "checks": checks}
    return _outputs(lim, grants, inst, solve(inst), rejected, dd)


def _fits_empty(ch, inst):
    cl, ns = set(inst["closed"][ch["base"]]), set(inst["nostart"][ch["base"]])
    for x in range(0, min(inst["types"][ch["type"]]["c"], ch["p"] - 1) + 1):
        dur = ch["p"] - x
        for s in range(ch["r"], inst["S"] - dur + 2):
            if s not in ns and not any(d in cl for d in range(s, s + dur)):
                return True
    return False


def _outputs(lim, grants, inst, res, rejected, dd):
    S, sc_cost, used = inst["S"], inst["shift_cost"], res["used"]
    seg_of = {c: s for s, cs in SEGMENTS.items() for c in cs}
    rows = []
    for ch in sorted(inst["checks"], key=lambda c: c["id"]):
        s, f, x = res["plan"][ch["id"]]
        cl = inst["classes"][ch["cls"]]
        r = {"request_id": ch["id"], "tail": ch["tail"], "base": ch["base"], "aircraft_class": ch["cls"],
             "segment": seg_of[ch["cls"]], "check_type": ch["type"]}
        if s > S:
            r.update({"decision": "deferred", "start_date": None, "finish_date": None, "compress_days": 0,
                      "overtime_shifts": 0, "overdue_days": 0, "moved": True,
                      "deferral_reason": "plan_trade" if _fits_empty(ch, inst) else "no_slot",
                      "_pen": cl["pen"], "_rev": 0, "_odc": 0})
        else:
            od = max(0, f - ch["due"])
            r.update({"decision": "scheduled", "start_date": dd(s), "finish_date": dd(f), "compress_days": x,
                      "overtime_shifts": inst["types"][ch["type"]]["h"] * x, "overdue_days": od,
                      "moved": s != ch["ps"], "deferral_reason": None,
                      "_pen": 0, "_rev": cl["rev"] * (ch["p"] - x), "_odc": od * cl["w"]})
            r["_key"] = (RANK[ch["cls"]], ch["due"], ch["id"])
        rows.append(r)
    left = sum(grants.values())
    for r in sorted((r for r in rows if "_key" in r), key=lambda r: r["_key"]):
        r["_take"] = min(r["overtime_shifts"], left)
        left -= r["_take"]
    for r in rows:
        h, t = r["overtime_shifts"], r.get("_take", 0)
        r.update({"overtime_cost": sc_cost * h, "allowance_shifts": t, "paid_shifts": h - t,
                  "allowance_credit": sc_cost * t, "settled_overtime_cost": sc_cost * (h - t)})

    def money(sel):
        return {"overtime_cost": sum(r["overtime_cost"] for r in sel),
                "allowance_used": sum(r["allowance_shifts"] for r in sel),
                "allowance_credit": sum(r["allowance_credit"] for r in sel),
                "settled_overtime_cost": sum(r["settled_overtime_cost"] for r in sel)}

    def agg(sel):
        sc = [r for r in sel if r["decision"] == "scheduled"]
        return {"checks_scheduled": len(sc), "checks_deferred": len(sel) - len(sc),
                "compress_days": sum(r["compress_days"] for r in sc),
                "overtime_shifts": sum(r["overtime_shifts"] for r in sc),
                "overdue_days": sum(r["overdue_days"] for r in sc),
                "overdue_cost": sum(r["_odc"] for r in sc),
                "deferral_cost": sum(r["_pen"] for r in sel),
                "revenue_lost": sum(r["_rev"] for r in sc),
                "moved": sum(1 for r in sel if r["moved"]),
                "first_start": min((r["start_date"] for r in sc), default=None),
                "last_finish": max((r["finish_date"] for r in sc), default=None),
                "fleet_overtime_used": used}
    out = {"policy_audit.json": {"season": lim["season"],
                                 "checks": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]}}
    summ_b, summ_s = [], []
    for b in BASES:
        sel = [r for r in rows if r["base"] == b]
        g, m = agg(sel), money(sel)
        out["region_%s.json" % b] = dict({"base": b}, **g, allowance_granted=grants[b], **m)
        summ_b.append({"base": b, "checks_scheduled": g["checks_scheduled"], "checks_deferred": g["checks_deferred"],
                       "overtime_shifts": g["overtime_shifts"], "allowance_granted": grants[b],
                       "allowance_used": m["allowance_used"], "settled_overtime_cost": m["settled_overtime_cost"]})
    for s in SEGMENTS:
        sel = [r for r in rows if r["segment"] == s]
        g = agg(sel)
        out["segment_%s.json" % s] = dict({"segment": s}, **g, **money(sel))
        summ_s.append({"segment": s, "checks_scheduled": g["checks_scheduled"], "checks_deferred": g["checks_deferred"]})
    g, m, A = agg(rows), money(rows), sum(grants.values())
    out["summary.json"] = {
        "season": lim["season"], "plan_terms": {"first": res["T"][0], "second": res["T"][1], "third": res["T"][2]},
        "overtime_pool_shifts": inst["K"], "fleet_overtime_used": used, "checks_scheduled": g["checks_scheduled"],
        "checks_deferred": g["checks_deferred"], "moved": g["moved"],
        "settlement": {"allowance_granted": A, "allowance_used": m["allowance_used"],
                       "allowance_left": A - m["allowance_used"], "overtime_cost": m["overtime_cost"],
                       "allowance_credit": m["allowance_credit"], "settled_overtime_cost": m["settled_overtime_cost"]},
        "bases": summ_b, "segments": summ_s}
    out["data_quality.json"] = {"rejected": rejected,
                                "counts": {k: sum(1 for r in rejected if r["reason"] == k) for k in REASONS}}
    return out


def corpus(mode, seed, n, empty, stype, x1, outdir):
    inst = make(mode, seed, n, empty)
    grants_for(inst, stype)
    return render(inst, outdir, x1)
# ---- GEN END ----


def main():
    a = sys.argv[1:]
    if a and a[0] == "derive":
        os.makedirs(a[2], exist_ok=True)
        for name, obj in derive(a[1]).items():
            with open(os.path.join(a[2], name), "w") as f:
                json.dump(obj, f, indent=2)
                f.write("\n")
    elif len(a) == 1:
        inst = corpus("shipped", 2, 5, False, "slack", False, a[0])
        print(json.dumps(inst["meta"]))
    else:
        out, mode, seed, empty, stype, x1 = a
        inst = corpus(mode, int(seed), 5 if mode == "shipped" else 8, empty == "1", stype, x1 == "1", out)
        print(json.dumps(inst["meta"]))


if __name__ == "__main__":
    main()
