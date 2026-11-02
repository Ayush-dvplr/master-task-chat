"""Checks for the heavy check season replan task.

Expected outputs are derived here from the input files of each data folder.
The shipped folder is embedded below; further folders are generated from
seeds that live only in this file, and the submitted program is run on each
of them with the command stated in the task.

Test polarity for negative-weight tests: the assertion HOLDS when the cheat is
present. Honest agent -> assertion fails -> negative weight not added.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false

from __future__ import annotations

import base64
import hashlib
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import zlib
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

OUT = Path("/app/out")
SCRIPT = OUT / "derive_report.py"
ARTIFACT_NAMES = ["summary.json", "policy_audit.json", "data_quality.json", "region_North.json",
                  "region_South.json", "region_West.json", "region_East.json", "segment_commercial.json",
                  "segment_public.json"]
RUN_LIMIT = 60
MISSING_INPUT = "fleet_register.csv"
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

# ---- generator and expected outputs ----
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
    _write_governing_docs(Path(outdir))
    return inst


def _write_governing_docs(data: Path) -> None:
    docs = data / "docs"
    docs.mkdir()
    for name, blob in _GOVERNING_DOCS.items():
        (docs / name).write_bytes(zlib.decompress(base64.b64decode(blob)))


_GOVERNING_DOCS = {
    'README.md': 'eJxtUz2P2zAM3f0rCHRpgVyyX6eiKNDltgIdE0aiY7ay5Ep0fAHy40tKTpBebzBs8+O9x68P8J3wfAE3kPsNmaaA8Rl8cvNIUdRw4iKUu+4FOQpFjI7ga4qSU4BpPgYuAxVAGB5gDAT6lIHQDVAIS4pb+AKeS54n4RQhJmFFGrCASyMB9sYiA7XkRe03dL8BjB7M16BqliQ40io4kq90FrIMKRD0gUi28EO10b0alZmpcvRzCAomkHrIc9ACWjrKiriFbyZd0sQOuMApnSkbzfEC9IpOwgVSVCAO9Nx11zXyugZyPFUXXLvr09NTfTSI4zRLdZSNvih4GAktWv+XgZUxp6XKhLWujQr6RU6UurqucNjhNO08Cu60sFK/9i7Fs1aonS3b0R+MV7sUT5ghcDQ6h4Gix6yfRTBL7WnPUTsMHi9qHtJSWRu/TmXSt3+HsUpT0fspBXaXO6GlZCrFqse2ChuwfgjrhMvAvSjNwxzvviml0Dx3E4aQlrptJpR1eDovCVTX8n9Nt7y3mjz1lHNTlOnPTEVsdSK9yk3Fbbly+83kUvbvFt7AMLwlSbM8DFaxOLfxlgpuja2XcMYwk62TRoZ3GRrSvmjzRlzxO91iiPN4pFzgY0YxkklPMQjbZ+CRrbFrOd4CPqn1rN2Muqcca3lG0iTCHL0e2wP34XMNOVQNBz2GoAFm0kXQe9I65N9L2sLP6pQlPZxXIRqtuwUvnedem2XDksEWHPCoxdWjqbfSxv3mXO5XuB5eUy54VJ/ma0WeHHsq2+4vrCWzIg==',
    'data_conventions.md': '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',
    'deferral_policy.md': 'eJx1kD1uwzAMhXedgkCHLm3uEKBL9+42LdG1UJl0RSaub1/KcdAsBbSIP+99fE/wRiPVigUWKTluIZx5A1mIodL3hdRgxg0GgrQPUgITYPoxUEIVhsxqhAlk9KnMn6BxonQplE5w/tu6q2FKGmwi6NPh3LkZFtv6JpFNIRZUbTZtbMzVt4zqDMgJolzYR1BhlmuzePdfPUgUepZOi1gf1slPaAJOE78gIrOYq3HWCYbtTk+uiU7lR0eZl0qq2cv+EEpmgjXbBCwgrlVvYi+NJPRLQe6sYqL+1l2z0imEDzf9b9XTcihs4bERR2rQjfKI51lBVoYB9VHjFoqox5hw09CCYHlVw2p7ZSd6uFYtlwJ7X9stUgFHz3BXwivmgkOhtnoKv69OuNM=',
    'output_schema.md': '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',
    'overtime_policy.md': 'eJyFVbty3DAM7PkVmHHraJzWrlIkbZr0Ek8CT4wpUiYp391MPj4LUvf0OenEB4DdxYJ6oJ/vHLOdmObgbH9Q6hv1I/evNOkDbZjSGGJmzwNtDrTMlAN1k963fZjmyCm1gz6kjoIhmxPlw8wvxLofCfuU9St7nBlaEifVhbVYm0ZrcmpnjhLfUV039Gtketdu4UQ6AhPHFY0kJuupK8tWlqn5nYLvGjoifmWek9KZHOuUKXguIIKnbQyLHx4phYLyiB2kBH0ppWk3Bsfkl2mDqiaGiZ6EbQakNGnnsBuMukde+4G6YYk62+DXvS/0tdI5cl45ilJ6BSx17+BRcj3Rp2oJ44ENx4iAyG9QK9OoE/B+YAZkT7cQGqUEmHHMNU6UCmcfBEcmxEocSgb/XL7vEXHusmRhhaJZDpQJS6SNRuMh45aRIhZT+ZCJ9z0j4ExRqq48O+nz7LT31m9bZydI1Ayh3wP3w8PZsKgRdtr3XOlkvUH7OilIf86H/0sKb2gvbG7YofPFxpKvNLLyWW+fCEGoqehX1QwfwN1Iid6ZzJc7BRXZpIzdMzyaT60555ill5LolF9KJug9LO4ofNGdyim45tGCVBw4PpO2sY/aZNU7nRLt7MCbMBxKLU9exxh2FxuRt/Cxdi+4iTRe/FoCBRrr6CwIwO8MN2buyNiY8ovMGS6opAEAhySHV9PTrV5t7bAGNfRdNF5HHI9Fuhm3Mh43rVFiarl21idlCyc6NvkRY2yRDyGldUgAbSENzPMDAvKp3iN1d0wCdUboiKgKp7wD18XKtM/aDpdRcgVTkNV9zM2F1fuQconpytm6rjN/J/QKZ4+Rt7lTn0dfiLKGF7yJc4ZT2jsobrYm6xc81R9q/uPVEYtAf2PfYV3Lbjg+MbXqxL42AWEz/iarU6gYvti/vpSJ+yCtZYyUPPWnca2/pmaCbXo85PnyT1JAV5LXbfLFA/2o/ZZTdcVx1CjMiNWuUX8BXxONMg==',
    'planning_policy.md': 'eJyNVU2P2zgMvetXEJhDZ7AZo722p2LRBfbURTtAj7Fi02NhbCkryUnz7/eRsmMn7WEvk7HEj8fHR+qB/hms986/0jEMrrkY8/BA39mm4Km1l0TWtzQ4z8mY9Zg+kEtUJz3Yp2xjrtUy90yDTZnSaruxZN/WFX2xTU8Hm5h6myh4/LI9XUzTc/OmyXZrMHzROcQ3MVTbYmUzWcpu5Io+z0dT4kR84njRtF0MI7mcSOHpUQ5GDjrnXer1BDHlJJy9AnqXNGFFL0jt+WeeQ8Ms90ipaEb4lZh6zBrIdpmjfJlj5JML000auIoh2zg4Trky5oviDEf2FPnfCYfCEzuYRUrI2k4Dt+QkAy5mOkOkljuOEVePiZnq8mmHfWlfNbb1U2U+b0JoBR+NeS6gC49xBizF25N1gz0MWsinGztbaJPSAcLP8Cw1Q0gILZdeYuHv80pz6DSuECrhpMk+bH02Bmj05Yyg/Pt+0V2/HreJEugxRAfOZwaPNhaliJjl9kmSF19eqj5wF2D2G5miJ4uQzigTzE7RZgfRSqyajirJhpowosNpLiXNbQhop6hx2wYtfMVu0GY7SE1rgX8g7DOCPtOHiv5GqRoSgF5jmJBOSlKLSufyzwDIIM/SEVMrLf2KvO3Es5/c3Dd+y97oPHSJyhhFZa53Qsl7Av8yBndcKbPKlvSgJMlcIelfLgIH5DN+VCbTNJIQcJ9bEYUtQqEoqU89n+/P7F57bA+YyvRQccUgNmhQ2qHSafZYpc7eDvmy+BRL+ZiHf5mQebAE8ndugmyU/4f5rgsb1Jht9kB95Ci62MLewK1T77q8b9CueuO9iIT0uvRrGLaKKhAE8Evv4havn8YD0MJlRJhrbUnW32aBlMulobI4ruWpqm0RH/DqHOo4Y7zLFqyP02EQBbTLSsf62RyK6KomnYpuNkkWxheVjkcb9UmBA94NeWKSarnRK4CZN2d3VdJOvsthWnu1Oc1XQj4VqxHcAf3JDhObecGu8crSal0HZAm1ezD1Q2IpJjSFdb+B/txHTLD4oH0zwPnpKdNWGFsmrGjsSvl1fe8dqootED3aXySIuJOXVZvuHox5/+BdfNqZLgxDOMPrcLkBsE5wKg8CqreQkaa7ZUNdbsgoFLBvuLBgzItyrHmFDGmgmOv/yprYlWen0OHE1I4BHRXCZgbF8o35uDACkc3oEps2NNPIXvT5baGqvdMAyEAoccFDW5n/AIA5Ay4=',
}


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


_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
_W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
# held-out Word forms: table -> (file, header pair, value cell)
_FORM_TABLES = {"allow": ("planning_limits.docx", ("base", "allowance_shifts"), 1),
                "close": ("disruption_notice.docx", ("base", "from"), 2),
                "avail": ("disruption_notice.docx", ("tail", "available_from"), 1)}
_FORM_ROOT = '<w:document xmlns:w="'
_FORM_ROOT_WIDE = ('<w:document xmlns:mc="%s" xmlns:w14="%s" xmlns:w15="%s" mc:Ignorable="w14 w15" xmlns:w="'
                   % (_MC, _W14, _W15))
_FORM_RUN = re.compile(r'<w:r><w:t xml:space="preserve">[^<]*</w:t></w:r>')


def _form_rows(kind, rows, cell):
    """The data rows of one table written in WordprocessingML form `kind`; every cell keeps its text."""
    if kind == "sdt":
        items = "".join('<w:sdt><w:sdtPr><w:id w:val="%d"/><w15:repeatingSectionItem/></w:sdtPr>'
                        '<w:sdtContent>%s</w:sdtContent></w:sdt>' % (900 + k, row) for k, row in enumerate(rows))
        return ('<w:sdt><w:sdtPr><w:alias w:val="rows"/><w:id w:val="899"/><w15:repeatingSection/></w:sdtPr>'
                '<w:sdtContent>%s</w:sdtContent></w:sdt>' % items)
    if kind == "cxml":
        return "".join('<w:customXml w:uri="urn:planning" w:element="row">%s</w:customXml>' % row for row in rows)
    assert kind == "alt", kind
    out = []
    for row in rows:
        cells = re.findall(r"<w:tc>.*?</w:tc>", row, re.S)
        run = _FORM_RUN.search(cells[cell]).group(0)
        choice = run.replace("<w:r>", '<w:r><w:rPr><w14:ligatures w14:val="standard"/></w:rPr>', 1)
        cells[cell] = cells[cell].replace(run, '<mc:AlternateContent><mc:Choice Requires="w14">%s</mc:Choice>'
                                          '<mc:Fallback>%s</mc:Fallback></mc:AlternateContent>' % (choice, run), 1)
        head, tail = row[:row.index("<w:tc>")], row[row.rindex("</w:tc>") + len("</w:tc>"):]
        out.append(head + "".join(cells) + tail)
    return "".join(out)


def _form_plain(doc):
    """Undo the held-out Word forms by text: the plain document part write_docx wrote."""
    doc = doc.replace(_FORM_ROOT_WIDE, _FORM_ROOT, 1)
    doc = re.sub(r"<w:sdt><w:sdtPr>.*?</w:sdtPr><w:sdtContent>", "", doc, flags=re.S)
    doc = doc.replace("</w:sdtContent></w:sdt>", "")
    doc = re.sub(r"<w:customXml [^>]*>|</w:customXml>", "", doc)
    return re.sub(r"<mc:AlternateContent><mc:Choice [^>]*>.*?</mc:Choice><mc:Fallback>(.*?)</mc:Fallback>"
                  r"</mc:AlternateContent>", r"\1", doc, flags=re.S)


def _reform(data, table, kind):
    """Rewrite the data rows of one table of a held-out folder in another WordprocessingML form, values unchanged."""
    name, head, cell = _FORM_TABLES[table]
    path = Path(data) / name
    before = _docx_tables(path)
    with zipfile.ZipFile(path) as z:
        items = [(info, z.read(info)) for info in z.infolist()]
    k = next(i for i, (info, _) in enumerate(items) if info.filename == "word/document.xml")
    doc = items[k][1].decode("utf-8")
    new = doc
    for tbl in re.findall(r"<w:tbl>.*?</w:tbl>", doc, re.S):
        rows = re.findall(r"<w:tr>.*?</w:tr>", tbl, re.S)
        if tuple(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", rows[0])[:2]) == head:
            assert len(rows) > 1, "table %s has no data rows" % table
            new = doc.replace(tbl, tbl.replace("".join(rows[1:]), _form_rows(kind, rows[1:], cell), 1), 1)
            break
    assert new != doc, "table %s not found in %s" % (table, name)
    new = new.replace(_FORM_ROOT, _FORM_ROOT_WIDE, 1)
    assert _form_plain(new) == doc, "held-out form of %s changed a value" % name
    ET.fromstring(new.encode("utf-8"))
    items[k] = (items[k][0], new.encode("utf-8"))
    with zipfile.ZipFile(path, "w") as z:
        for info, blob in items:
            z.writestr(info, blob)
    assert _docx_tables(path) != before, "held-out form of %s reads the same row by row" % name


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


_SHIPPED_DATA: dict[str, str] = {
    "base_calendar.jsonl": "eNql3U3PXe12puU+v6K02yBljHnP8UEPQXooQaQkmiioSqJXEkm1Svx3CLTYa5q95rGktCIN+d325XX4fmyf/i9/+d/++V/+41/+23/3l3/4T//Hv/7vf/mv/91f/sM//+v/8//Iv8v7v/m7+L//79/+v//yr//8r//5X/7t//+P/9Pf/8Nf/s//6r98cZl8efHl4cubL4sv+/97+Q//+L/+07//7/7nf//l9fC3u3oZf8eXvKPgHQXvKHhHwTsK3lE0X/KGgjeUvKHkDSVvKHlDeX752Z28o+QdJe8oeUfJO7p4RxfuKFnDZA2TNUzWMFnDZA3zQ8MXl8OXq5cqYbKEyRImS5gsYbKEyRImS5gsYbKEyRImS5gsYbKE+SHhi0ve0F8r+EbfZAmTJbzYlottudiWi2252JaLbbnYlottudiWi2252JaLbbnYlottudiWi2252JaLbbnYlottudiWi2252JaLbbk+bHkjxPWTLxf7cv3gS/KWLt6SvrQOa3hYw8MaHtbwsIaHNTys4WEND2t4PjR88zPtsIiHRTws4mERD4t4WMTDIh4W8bCIh0U8LOJhEQ+LeFjEw6+tw19zPCzh+ZDw3edC8o5Uw5tNu9m0m0272bSbTbvZtJtNu9m0m027+YV3s2c3e3azZzd7drNnN3t2s2c3e3azZzd7drNnN3t2s2c3e3b/9MK72bSbTbt/Mu3+MO3dtbumr7xiEetDxDf/W4tVLFaxWMViFYtVLFaxWMViFYtVLFaxWMViFYtVLFaxWMViFetDxXc/u5N3lLyj5B0l7yh5R8k7St5R8o6Sd5T8WaQaNpvW/Mpr9qzZs2bPmj1r9qzZs2bPmj1r9qzZs2bPmj1r9qzZs2bPmj1rfuX1h2VvJGz2rNmzZs+aPWv2rNmzZs+aPWv2rH/wTF93wxIOSzgs4bCEwxIOSzgs4bCE8yHhf/8//uM//f3/8N2tWjhs4bCFwxYOWzhs4bCFwxYOWzhs4fC7btjBYQeHHRx2cNjBYQeHHRx2cNjBYQeHHVx2cH/6KueyhcsWLlu4bOGyhcsWLr8KlyVclnBZwmUJlyVclnBZwmUJlyVclnBZwmUJlyVclnBZwmUJlyVclnBZwmUJVyWMv1PP/u0y+fLiy8OXN18WXzZfDl+uXgZvKHhDwRsK3lDwhoI3FLyh4A0Fbyh4Q8kbSt5Q8oaSN5S8oeQN/bVlX3/F5t9ueUXJK0pekWuG77rgNkrEL++64D5KcB8luI8S3EeJYAu5jRLcRgluowS3UYLbKMFtlOA2SnAbJbiNEtxGCW6jBLdRgtsowW2U4DZKcBslgi3kLkpwFyW4ixLcRQnuogR3UeKzbvJGJS6cBBdOggsnwYWT4MJJcOEkuHASXDgJLpwEF06CCyfBhZP4LJy8W33wjoJ3FLyj4B0F7yh5R8k7St5R8o6SP4uSN5S8oeQNJW8oeUNuGr3uisuXxeXL4vJlcfmyuHxZXL6sp/Lli8vhy9VLkrCeqpdffv2luHtZ3L0s7l4Wdy+Lu5fF3cvi7mVx97Keupdf/zqjuH1Z3L4sbl/WU/vyxSXvKHlHyTtK3lHyji7+NFILky1MtjDZwmQLky1MtjDZwmQLky1MthBfhcXdy+LuZXH3sp66l28+55M1TNbw81X48r+Yt5S8peQtJW8peUvJW0r+PEreUfKOVMOLfbnYl4t9udiXi3252JeLfbnYl4t9udiXi3252JeLfbnYl4tfWhfbcrEtF7+0LnblYlcuduViVy525WJXLnblYlcuduX6wZXkDV28IX1lHVbwsIKHFTys4GEFDyt4WMHDCh5W8LCChxU8rOBhBQ8reFjBwwoeVvCwgocVPKzgYQUPK3hYwcMKHlbwsIKHFTys4GEFDyt4s2U3W3azZTdbdrNlN1t2s2U3W3azZTdbdrNlN1t2s2U3W3azZTdbdrNlN1t2s2U3W3azZTdbdrNlN1t2s2U3W3azZTdbdrNl9w+W6YuuWMFiBYsV/Gxbfv+nFYodLHaw2MFiB4sdLHaw2MFiB4sdLHaw2MFiB4sdLHaw2MFiB4sdLHaw2MFiB4sdLHaw2MFiB4sdLHawWbNmzZo1a37TNVvWbFmzZc2WNVvW/m/yFNcti+uWxXXL4rplcd2yuG5ZXLesp7rlyx9T3lLy51HyjjJ/+d+avKXkLSVvKXlLyVtK/kxK3pG7pu+7YRHH/wZ4ceWyuHJZXLksrlwWVy7rqXL58vt39dv9RcZhGYdlHJZxWMZhGYdlHJZx+KU3rOKwisMqDr/0hkUcFnFYxGERh0UcFnFYxGERh0VcFnH5jbis4bKGyxoua7is4fIbcVnC5a93Liu4rOCygssKLiu4rOCygssKLiu4rOCygssKLiu4rOCygssKLiu4rOCygqsKaueyuHNZ3Lks7lwWdy6LO5fFncvizmVx57KeOpcvXnUPrcuX17yl4C0Fbyl4S8FbCt5S8JaCt5T8eZT8eZS8oeQNJW8oeUPJG0reUPKGkjfkpuHLLriHEtxDCe6hBPdQgnsowT2U4B5KcA8luIcS3EPR0mVx6bK4dFlPpcs3bnMRJbiIElxECS6iBBdRtHZZXLssrl0W1y6La5fFtcvi2mVx7bK4dllcuyyuXdZT7fLFZfLlxZeHL2++LL5svhy+XL0M3lDwhoI3FLyh4A0Fbyh4Q8EbCt5Q8IZ+qHsF90yCeybBPZPgnklwzyS4ZxLcMwnumWjpsrh0WVy6bC5dNpcum0uXzaXL5tJlc+myuXTZXLpsLl32U+ny60+xfqpdvvh2eUfBOwreUfCOgncUvKPgHQXviF52zZ3L5s5lc+eyuXPZ3Lls7lw2dy6bO5fNncvmzmVz57K5c9ncuWzuXDZ3Lps7l82dy+bOZXPnsrlz2dy5bO5cNncu+6lz+cbtZAmTJfx8F778L+YtBW8peEvJW0reUvKWkj+PkneUvKPkz6PkDamGF/tysS8X+3KxLxf7crEvF/tysS8X+3KxLxf7crEvF7+yLrblYlsufmVd7MrFrlzsysWuXOzK5X9zrrl12dy67KfW5ZdVi36qXb667R9u54fb9du/fnO9ug29/SxfvrrNH26vH27PD7f3D7f1w23/cDs/3OJn3PnpK5KHrTxs5WErD1t52Mrz0zvssJfH/7Z5cxWzuYrZXMVsrmI2VzH7qYr57vs3eU/6Hjv8Hjv8HvssY777XtKvUN78Drz5HXjzO/Dmd+DN78Cb34Gfdcw3P6Y3vwVvNu7mt+Dtf7OguZLZXMlsrmQ2VzKbK5nNlczmSmZzJbO5ktlcyWyuZDZXMpsrmc2VzOZKZnMls7mS2VzJbK5kNlcymyuZzZXM5kpmP1UyX1zefFl82Xw5fLl6qRIWv/SKFSxWsFjBYgWLFSxWsFjBYgWLFSxWsH76quhnJ/PlNW8p75++Xd5T8p5yfvov5k2pip/NzDf/xc2+NfvW7Fuzb82+NfvW7Fuzb82+NfvW7Fuzb82+NfvWP30ls9m4ZuOajWs2rtm45pde80uv2bbml16za82uNb/0mk3rH0zTl97wS29YwmEJhyUclnB++N29YQuHLRy2cNjCYQuHLRy2cPxvkTeXMptLmc2lzOZSZnMps7mU2VzKbC5lNpcym0uZzaXM5lJmcymzuZTZXMpsLmU2lzKbS5nNpczmUmZzKbO5lNlcymwuZTaXMptLmc2lzOZSZnMps7mU2VzKbC5lNpcym0uZzaXM5lJmcymzuZTZXMrsp1Lmm18TLUu4LOGyhMsSLku4LOGqhFrLbK5lNtcym2uZzbXM5lpmcy2zuZbZXMvsp1rmi0veUPCGgjcUvKHgDQVvKHhDwRsK3lDyhtJ/x0VLmc2lzOZSZnMps7mU2VzKbC5lNpcym0uZzaXM5lJmcymzuZTZXMpsLmU2lzKbS5nNpczmUmZzKbO5lNlcymwuZfZTKfPFJW8oeEPBGwreUPCGkjeUvKHkDSVvKHlDyRviv98XXFMJrqkE11QeOpnf/y/lKkpwFeWhlPnqv/fwt3rzZfFl8+Xw5eqlisZdlOAuSvzURQnuogR3UbSX2dzL7Kde5pufa8FLSl5S8pJ++HOawWWU4DJKcBkluIwSXEYJLqNoMbO5mNlPxcyv1zBczRyuZg5XM+epmvnyf+vN327xZfPl/PS/dfXb5b+rPlzPnKd65pef38P9zOF+5nA/c7ifOdzPHO5nDvczh/uZw/3M4X7mPPUz3+0+eUfJO0reUfKOkneUvKOLd3ThjpJdTHYx2UV8Kw43NIcbmsMNzeGG5nBDc7ihOdzQHG5ozlND88Ulbyh4Q8EbCt5Q8IaCN5S8oeQNJW8oeUPJG0reUJa7nSxhsoTJEl5aGBtubw63N4fbm8PtzeH25nB7c7i9OdzeHG5vDrc3h9ubw+3N4fbmcHtzuL053N6cp/bmm8+xi2262KaLbbrYpottutimi226+IV2sUsXu3T94NLFG9IX2uEX2mEJD0t4WMLDEh6W8LCEhyU8LOH56SuWhzU8rOFhDY//PbzhwuY8FTZfXPKWgrcUvCXV8LCGhzU8rOFhDQ9reFjDwxoe1vCwhoc1vNm0m0272bSbTbvZtJtNu7UaPU89zTefujfLdvMb74em5nBTc7ipOdzUHG5qzlNT8+X3UvO3O3zJW0reUvKnUvKOkneUvKPkHSV/KiVvKHlD3IsebmsOtzWH25rDbc3htuZwW3O4rTnc1hxuaw63Neeprfm9xcUmFr/0Puuab37GFJtYbOJnYfPlfzGvKXhNwWtSE4tNLDax2MRiE4tNLDax2MRiE4tNLH7tFXvYrFqzas2qNavWrFqzas2qNavW/M5rNq3ZtOY33mdR83u9m0VrfuU1a9asWbNmzZo1a9asWbNmzZo1a9asWbNmzZo1a9asWf+gmb7uhh0cdnDYwWEHhx0cdnDYwWEHhx0cdnDYwWEHh991wwoOKzis4LCCwwoOKzis4LCCwwoOKzis4LCCwwoOKzis4LCCwwoOK7is4LKCywouK7is4LKCywouK7is4P7051mWJVyWcFnCZQmXJdyfftdvWcNlDZc1XNZwWcNlDZc1XNZwWcNlDVf/VfXhnuZwT3O4pznc0xzuaQ73NId7msM9zeGe5nBPc7inOdzTHO5pDvc0h3uawz3N4Z7mcE9zuKc5Tz3Nrz+JtKg5XNQcLmrOT0XN4aLmcFFzuKg5XNQcLmoOFzWHi5rDRc3houZwUXO4qDlc1Bwuag4XNYeLmsNFzeGi5nBRc7ioOVzUHC5qDhc1h4uaw0XN4aLmcFFzuKg5XNQcLmoOFzWHi5rDRc3houZwUXO4qDlPRc0Xl7yh5A0lb0gV5D5KcB8luI/y0NJ882s/bqQEN1KCGykPPc2X/1tXv93gLQVvKXhLwVuKn7YUvKUofalxLSW4lhJcSwmupQTXUoJrKcG1lOBaSnAtRXuawz3N4Z7mcE9zuKc5Tz3Nry6XW5rLLc3lluY+tTS//DxZLmnuU0nz60/P5ZrmPtU0X1yufz+RicsdzX3qaL64vH75saG33nJJc7mkuVzSXC5pLpc0l0uayyXN5ZLmPpU0X1zyhpI3lLyh5A0lbyh5QxdvSEVMFjFZxGQRsaK5XNFcrmguVzSXK5rLFc3liuZyRXO5orlc0VyuaC5XNJcrmssVzeWK5nJFc7miuVzRXK5oLlc0lyuayxXNfapofv+r3GQHkx28WJaLZblYlotluViWi2W5WJaLZblYlotluViWi2W5WJaLZblYlotl+exgvnlLXqzLxbp8djDf/Rcnbyl5S8lbSt5S8paSt5T8eeS+JO8I/4265Rrmcg1zuYa5XMNcrmEu1zD3qYb5/Y/LYREPi3hYxMMiHhbxsIiHRTws4mERD4t4+K11vAy93MJcbmEutzCXW5jLLczlFuZyC3O5hbncwlxuYS63MJdbmMstzOUW5nILc7mFudzCXG5h7lML88Xl8OXqZfzwK/ObTbvZtJtNu9m0m0272bSbTbv1X2tdbmAuNzCXG5jLDczlBuZyA3O5gbncwFxuYC43MPepgfn9pYvG/1LrcgNzuYG53MBcbmAuNzCXG5jLDczlBuY+NTC/v9T3XbGFxRYWW1hsYbGFxRbWT1/xLP6KZ7GGxRoWa1isYbGGxRoWa1isYbGGxRoWa1isYbNnzZ41e9bsWbNn/dOflWw2rdm0ZtOaTWs2rdm0ZtOaTWs2rdm0/sm0ZtOaTWs2rdm0zwbm92/ZZtU+K5jvfmyS15Q/fSolfyolryl5Ta6b/k7esIvDLg67OOzisIvD77xhE4dNHDZx2MRhE4dNHDZx2MRhE4dNHP6a57CHwx4Oezjs4fAbb1jD4TfesITzk4TDEg5LOCzhsITDEi5LuCzhsoTLEi5LuCzhsoSfRczvf7W7bOGyhcsWLlu4bOGyhcsWLlu4bOGyhcsWLlu4bOGyhcsWLlu4bOHy1zuXHVx2cNnBVQe1hLlcwlwuYS6XMJdLmMslzOUS5nIJc7mEuVzCXC5hLpcw96mE+eJXuVrDXK5hLtcw96mG+eJyfvpe4i0lbyl5S8lbSv48St5R8o6Sd5S8o+TPo+QNuWn4tgtupQS3UoJbKQ8tzDc/u7mWoj3M5R7mcg9zuYe53MPcpx7mux+Z4C0Fb0lF5E5KcCcluJMS3EkJ7qQEd1KCOynBnZTgTkpwJyW4kxLcSXloYr77OZq8o+QdqYhcPAkungQXT4KLJ8HFk+DiSXDxJLh4Elw8CS6eBBdPgosnwcWT4OJJcPEkuHgSXDwJLp4EF0+CiyfBxZPg4klw8SS4eBJcPNES5nIJc7mEuVzCXC5h7lclzH/6T//54/L+qoT558vky4svD1/efFl82Xw5fLl6+TcV/PMlbyh4Q199rfPP17yj4B0F7yh4R8E7+msJ333/flVo+fM17yl5T8mfSclbSt5S8paSt5S8peTPpIs/k1TEZBGTRfx8F775+ZKsYrKKySomq5isYrKKySomq5is4hdvwz9f8oaCNxS8oeANBW8oeEPJG0reUPKGkjeUvKHkDSVvKHlDKuHFtlxsy8WvrYtdudiVi1252JWLXbnYlYtdub77fbQ/X/OOgncUvKO/tuXl/1beUvCWgrcUvKXkLSV/HiXvKHlHyTtK/jxK3lDyhtyX5A1dvCF9aR3W8LOE+eZz4bCIh0U8LOJhEQ+LeFjEwyIeFvHwS+uwhoc1PKzh4ZfWYQkPS3hYwsMSHpbwsISHJTws4fnub5T/+Zp3lLyj5B0l7yh5R6rhzabd/MK7f/rq4c2m3WzazaZ99jAf/k7bn2+Hv9XVy+AlBS8peEmq2s2q3azazardrNrNqt2s2s2q3azazardrNrN77ubRbtZtJtFu1m0m0W7fxBN33fFFhZbWPy2K3aw2MFiB4vfdsUK1jf/vuofb9XBYgeLHayf/nRJsYXFFhZbWGxhsYXFFhZbWGxhsYXFFhZbWGxhsYXFFn6WMN98piSvSDVsNq3ZtGbTmk1rNq3ZtGbTmk1rftk1i9YsWrNozS+7Zs2aNWvWrFmzZs2aNWvWrFmzZs2aNWvWrFmzZs2aNWt+2TVb1j9Ypi+7YQWHFRxWcFjBYQWHFZwfvsI57OCwg8MODjs47OCwg8MODjv42b588w4dtnDYwmELhy0ctnDYwmEL56ffuxv2cNjDYQ+HPRz2cNjDYQ+XPVz2cNnDZQ+XPVz2cPlVuKzhsobLGi5ruKzhsobLGi5ruPwqXJZwWcJlCZclXJZwWcJlCZdfhcsKLiu4rOCygssKrir4Tf3yz5fJlxdfHr68+bL4svly+HL1MnhDf23Z12/Yb/qXf77kFQWvKHhFwSsKXlHwioJXlLyi5E+i5A0lbyh5Q8kbSt5Q8oaSN5S8IdcM33TBZZSH7uWLF35wHSW4jhJcRwmuowTXUYLrKMF1lOA6SnAdJbiO8k3z8s+XvKHgDQVvKHhDwRsK3lDyhpI3lLyh5A0lbyh5Q8kbSt5Q8oaSN6QSctckuGsSP3VNHpqXL69v/q8uvmy+HL5cvQzeUvCWgrekpnHbJLhtEtw2CW6bBLdNgtsmwW2T4LZJcNvkoXv5/dcluG7yUL589zmWvKTkJSUvKXlJLhu98Yrrl8X1y+L6ZXH9srh+WVy/LK5fFtcvi+uXxfXL4vplcf2ynuqXLy55Q8EbCt5Q8Ia++ld+/nzNO0reUfKOkneU1y/fS8lbSt5S8paSt5T8eZS8o4t3pBoma5is4Q8vxOLyZXH5srh8WVy+LC5fFpcvi8uXxeXL4vJlPZUv3+0ozk/XvCX+853FFcziCmZxBbO4gllcwSyuYBZXMIsrmMUVzOIKZj1VMN8tUGW82JqLrbn45XWxMxc7c7EzFzvzWcJ8s4aLrbnYmoutudiai19fF7++Ljbm4tfXxb58VjC//DpbcQezuINZ3MEs7mAWdzCLO5j11MF89/M766drXpMrk7yli7d0hX8vHXbxsIuHXTzs4mEXD7t42MXD76/DJh428bCJh008bOJhEw+beNjEwyYefnMdFvGzh/m9w4dN/CxivvpWeUfJO0reUfKOkneUvKPcX2RSEW827WbTbjbtZtNuNu1m02427WbTPmuYb3b0WcR8eR0/XfOegvcUvKfgPQXvKfqn71/elBp386vvZuFufvXd7NvNvt3s282+3ezbzb7d/Nq7f7BNf7etWMXyv19QXMgsLmQWFzKLC5nFhcziQmY9FTK/v9TXXvFrr1jDYg3rp99pKxaxWMTiF1+xhsUaFmtYrGGxhsUaFmtYrGGxhsUaFmtYrGGxhs2mNb/0mj37rGN+/3WKZtGaRWsWrVm0ZtH6p3des2rNqjWr1vzGaxatWbRm0ZpFa//3xIs7mcWdzOJOZnEns7iTWdzJLO5kFncyizuZxZ3M4k5mcSezuJNZ3Mks7mQWdzKLO5nFncx66mS+uBy+XL3U992whMMSDks4LOGwhMMSDks4LOHw225YwWEFhxUcVnBYwWEFhxUcVnBYwWEFhxUcVnBZwWUFlxVcVnBZwWUFlxVcVnBZwWUFlxVcVnBZwWUFlxVcVnBZwWUFlxVcVnBZwWUFlxVcVnBZwWUFlxVcVnBZwVUFtY5ZXMcsrmMW1zGL65jFdcziOmZxHbO4jllcx6ynOuaLS95Q8IaCNxS8oeANBW8oeEPBG0reUPKGkjeUvKHkDSVvKHlDyRtK3lDyhi79M75axyyuY9ZTHfPF5cWXhy9vviy+bL4cvly9VAe5nBJcTgkupwSXU4LLKcHllOByipYx66mM+eL3+ILLKcHllOByitYxi+uYxXXM4jpmcR2zuI5ZXMcsrmMW1zGL65j1VMd8cXn48ubL4svmy+HL1cvgDQVvKHhDwRsK3lDwhoI3FLyh4A0Fbyh5Q8kbSt5Q8obS/zTvQxfz+5cLF0+0illcxSyuYhZXMYurmM1VzOYqZnMVs7mK2VzFbK5iNlcxm6uYzVXM5ipmcxWzuYrZXMXspyrml59EzV3M5i5mcxezn7qYLy55RckrSl5R8oqSV8QaNjcxm5uYzU3M5iZmcxOzuYnZ3MRsbmI2NzH7qYn54vLw5c2XxZfNl8OXq5dqYbKFyRb+0MPsn3qYzT3Mfuphfu9wsonJJiab+PlCfPc9nLyo5EXhv53QT03Ml/9reU/Jn03Ja1IZL7bmYmsutuZiay625mJrLrbmYmsutuZiay625mJrLn53YQ+zuYfZ3MNs7mH2Uw/zxSVvCNtf/dTDfHWbP9xeP9yeH27vH27rh9v+4XZ+uF2/vX7Ylb7DDtt42MbDNh628bCNh208bONhGw/beNjGwzYetvGwjeenN9hnG/PlNW8peEvBWwreUvKWkreUvKXkLSV/HiV/HiVvKHlDOb+snvuYzX3M5j5mcx+zuY/ZT33MN99Ln43Ml9fF/9XNl8OXq5fBWwreUuQvPzLBe9I34M1vwJt9u9m3m3272bebfbvZt5t9u9m3+6evL95s3M3G3WzczV9fvPl33u4fbNMXX7GKxSoWq1j84it+8RVrWKxhsYbFGpaXxJr7mM19zOY+Zj/1MV9c3j99L/GWgrcUvKXgLamIxSJ+9jHf/cgkb+kXFYtVLFaxWMViFYtV/Oxkvvn+bfatvf/c3Mvsp17mi8ubL4svmy+HL1cv9cXX7Fuzb82+NfvW/Nprtq3Ztmbbmm1rtq3ZtubXXrNrzV/NbDat/d++ay5lNpcym0uZzaXM5lJmcymzuZTZXMpsLmU2lzL7qZT5ZoHDGg5rOKzhsIbDGg5rOKzhsIbDGg5rOKzhsIbDGg5rOKzhsIbDGs5Pr7xhEYdfecMazk+/vzcs4rCIwyJ+VjPf/G9dVnFZxWUVl1Vcfh8ui7gs4rKIyyIui7gs4rKIyyIui7gs4rKIyyIui7gs4rKI+9PXPpdVXH4jLou4LOKyiMvvw2UNVzXUemZzPbO5ntlcz2yuZzbXM5vrmc31zOZ6ZnM9s7me2VzP7Kd65td/5ln7mc39zOZ+ZnM/s7mf2dzPbO5nNvczm/uZzf3M5n5mcz+zuZ/Z3M9s7mc29zP7qZ/54tJfaMGVleDKSnBlJbiyElxZCa6sBFdWgisrwZWV4MpKcGUluLISXFnRgmZzQbO5oNlc0Oyngua7z4XgHSXvKHlHyTtK3lHyjpJ3lLyj5B3x3/ALrqwEV1aCWynBrZTgVkpwKyW4lRLcSnloaH6/Ba6lBNdSgmspwbWU4FqKVjSbK5rNFc3mimZzRbO5otlc0WyuaDZXNJsrms0VzX6qaL645A0lbyh5Q8kbSt6Qa0a/czdP/cwvP6uHC5rDBc3hguZwQXO4oDlc0BwuaA4XNIcLmsMFzeGC5nBBc54Kmi8ueUPBGwreUPCGgjeUvKHkDSVvKHlDyRtK3lDyhpI3lLyh5A1dvCF1EN+Dw+3M4XbmcDtzuJ053M4cbmcOtzOH25nD7czhduZwO3Oe2pkvLnlDwRsK3lDwhoI3FLyh5A0lbyh5Q8kbSt5Q8oaSN5S8oeQNqYIXi3SxSJ+Fza9/N2C4sjlc2RyubA5XNocrm8OVzeHK5nBlc7iyOVzZHK5sDlc2hyubw5XN4crmcGVzniqbLy55Q8kbSt5Q8oaSN5S8oeQNJW/IVbp4Q/o2OyzhYQkPv80OK3hYwcMKHlbwsIKHFTys4GEFDyt4WMHDCh5W8LCChxU8rOBhBQ8reFjBwwoeVvCwgocVPKzgYQUPK3hYweM1leGG5nBDc7ihOU8NzReXN18WXzZfDl+uXqpnN3t2s2e3/zs9w+3M4XbmPLUzX/4X85aCtxS8peQtJW8peUvJn0fJO0reUfLnUfKGkjeUvKGLN6Svu2INizUs1rBYw2INizUs1rBYw2INizUs1rBYw+LXXbGExRIWv+6KFSxWsFjB8n+rbribOU/dzBeXvKPkHSXvKHlHyTtK3lHyjlTCZs+aPWv2rNmzZs+aPfvsZL752d1sWrNpzaY1m9ZsWrNpzaY1m9Zs2mcr892OgncUvKPkHSXvKHlHyTtK3lHyjpJ3pKa1/n254VrmcC1zuJY5XMscrmUO1zKHa5nDtcx5qmW+uGy+HL5cvVQLhy0ctnDYwmELhy0ctnD4fTfs4LCDww4OOzjs4LCDww5+VjLf/Npm2MJhC4ffd8MSDks4LOGyhMsSLku4LOGyhMsSLku4LOFnIfPNz7RlDZc1XNZwWcNlDZc1XNZwWcNlDZc1XNZwWcMfKpnDlczhSuZwJXO4kjlcyRyuZA5XMocrmcOVzOFK5nAlc7iSOVzJHK5kDlcyhyuZw5XM4UrmcCVzuJI5T5XMF5e8oeANBW8oeEPBGwreUPKGkjeUvKHkDSVvKHlDyRtK3lDyhpI35Jbhy077mPPUx3zxq6ngjkpwRyW4oxLcUQnuqDw0Ml9+/65+u6oht1SCWyrBLZXglkpwSyW4pRLcUgluqQS3VIJbKsEtleCWSnBLJbilEtxSCW6pBLdUglsqwS2Vh0Lmm88/rqIEV1GCqyjBVZTgKkpwFSW4ihJcRQmuojw0Mr/+/ergLkpwFyW4ixLcRQnuogR3UYK7KMFdlOAuSnAXJbiLEtxFCe6iBHdRgrsowV2U4C5KcBcluIuilczhSuY+VTJfXCZfXnx5+PLmy+JL/bN4y53Mfepkvvt26X233MpcbmUutzKXW5nLrczlVuZyK3O5lblPrcwvf2W0XMvcp1rmq281f1l+8paSt5S8peQtJW8peUuk4nIzc7mZudzMXG5mLjczl5uZy83M5WbmcjNzuZm53MxcbmYuNzOXm5nLzczlZuZyM3O5mbnczFxuZu5TM/ONLcke4vtwn7qZL/+LeUvJW+I/4bncz9ynfub3v+ZINvFiZS5W5mJlLlbms4H55kf1YmkuluZiaS6W5mJpLpbmYmkuluZiaS6W5mJpLpbmYmmwg7ncwVzuYC53MJc7mMsdzOUO5nIHc7mDudzBXO5gLncwlzuYyx3M5Q7mcgdzuYO53MFc7mAudzCXO5jLHczlDuZyB3O5g7ncwVzuYC53MJc7mMsdzOUO5nIHc7mDudzBXO5gLncwlzuYyx3M5Q7mcgdzuYO53MHcpw7mt5c3W3azZTdbdrNlN1t2s2U3W/bZwPz+hX+zZjdrdrNmN2t2s2Y3a3azZjdrdrNmN2t2s2Y3a3azZjdr9lm/fPPzLHlFyStKXlHyipJXlLwi90xfdcUSFktY/u/8LDcwlxuYyw3M5QbmcgNzuYG5Tw3Mdz8ywVsK3pJ6WOxhsYfFHhZ7WOxhsYfFHhZ7WOxh8euuWMNiDYs1LNawWMNiDYs1bDat2bTm112zZ82eNXvW7FmzZ82eNb/tmi1rtqzZsmbLmi1rtqzZsmbLmi1rtqzZsmbLmi1rtqzZsmbLmi1rtqzZsv7BMn3ZDSs4rOCwgsMKDis4rOCwgsMKzk9/Y2BYwmEJhyUclnBYwmEJhyUclnBYwmEJhyUclnBYwmEJhyUclnBYwmEJhyUclnBYws/y5ZvPv2UNlzVc1nBZw2UNlzVc1nC9j7JPBczvv13V8LN++e6/OHhLwVsK3lLwlv5axO9/h2nZxGUTl01cNnHZxGUTl01cNnHZxGUTl01cNnHZxFUTtX+53L9c7l8u9y+X+5fL/cvl/uVy/3K5f7ncv1zuXy73L5f7l8v9y+X+5XL/crl/udy/XO5fLvcvl/uXy/3L5f7lcv9yuX+53L/cp/7li19xagNzuYG53MBcbmAuNzD3qYH54vLiy8OXN18WXzZfDl+uXqqE3EYJbqMEt1GC2yjBbZTgNkpwGyW4jfLQvnzzycl1FO1fLvcvl/uXy/3Lfepffv3KDy6jBJdRgssowWWU4DJKcN/koX75/Y8LF06CCyfBhZPgwklw4SS4cBJcOAkunAQXToILJ8GFk4f65ZvlBq8oeEXBKwr/yrc2MJcbmMsNzOUG5nIDc7mBudzAXG5gLjcwlxuYyw3M5QbmftXA/F/+47/8618d3l8lMP94mHp46eHRw1sPSw9bD0cPFw//poB/PNTlhC4ndDmhywldTuhyQpcTupzQ5aQuJ3U5qctJXU7qclKXk7qc1OWkLid1OZcuB5lLZS6VuVTmUplLZS6VuVTmUplLZe6rf+jgj6e6ndDthG4ndDuh2wndTuh2QrcTuh2ELhW6z4fdi7Wmbid1O6nbSd1O6naQukv9uNSPS/241I9L/bjUj0v9uNSPS/249Jl0qR6X6nGpHpfq8dmmfPya2x+PdT2h6wldT+h6UteTup7U9aSuJ3U9+ct6/tqQd8e6IHYkdUGXLgifTEfJO9/926d/PL70Wz16eOth/fK/s/VbHT1cPET6PqOUX/8q9ih+R/E7it/Rp9NR+I7CdxS+o/Adhe8ofEfhOwrfUfiOPpyOPpyOgncUvKPgHQXvVrdufardatatZt1q1q1PtVu9utWrW7261atbn2q3anWrVrdqdatWt2p1q1a3anWrVrdqdatWt2p1q1a3anWrVrdqdatWt2p1q1a3a4XPs1LmSpkrZa6UuVLmSpkrZa6UuVLmSpmr7/6m9R+PdT2h6wldT+h6on75DtIFhS4odEGpC0r97EldT+p6UteTup7Uz56v/j7aH491Pbn4RZpS9FrtarWr1a5Wu1rtarWr1a5Wuz77kV9vp1Wv1kdaq1ytcrXK1SpX6yOtVa1WtVrValWrVa1WtVrValWrVa1WtVofaa1itT7S2r3CR9oodKPQjUI3Ct0odKPQjUI3Ct3oI22UuVHmRpkbZW6UuVHmRpkbZW6UuVHmRpkbZW6UuVHmRpkbZW6UuVHmRpn7TEG+eA6OUjdK3Sp1q9R9ViC/fn2sYreK3Sp2q9jtN//o2x9PF79N5G6Vu1XuVrlb5e6z+vjiByR0PaHrQfBWwVsFbxW89T9lv9/8S29/PNX9pH72pK4ndT2p60ldj4H3Tenxj4eph5ceHj289bD0sPVw9HDx8Kt/mu2Px7qe0PWErid0PaHrCV1P6HpC1xO6ntTPndTlpC5Hzfom7PjHQ91O6nZSt5O6ndTtsFn2SAutfYTWPkJrH6G1j9DaR2jtI7T2EVr7CK19hNY+HhKOX394aO8jtPcR2vsI7X2E9j5Cex+hvY/Q3kdo7yO09xHa+wjtfYT2PkJ7H6G9j9DeR2jvI7T3Edr7CM12hGY7QrMdodmO0GxHaLYjNNsRmu0IzXZ802f846EuJ/hvL4aGO0LDHaHhjtBwR2i4IzTcERruCA13hIY7viky/vFQl5O6nNTlpC4ndTmpy0ldDoslT7N6CjF++7lTGmMsjTGWxhhLY4ylMcZ6ijG++54d/VYXD4W80iBjaZCxNMhYGmQsDTKWBhnrKcj43cO3NMlYmmQsTTLWU5Lx1c+R1P2k7id1P6n7Sd2PoFeaZSzNMtZTlvHVCBA+e+OVphlL04ylacZ6SjO++J5Nhc/eeaV5xtI8Yz3lGb8/1PVE4ud6Knup7KWyl8qevfJK84ylecbSPGNpnrGe8ozfH+pyUpeTupzU5aQuB8G7VJDrm3/P5Y+nl36bRw/dkEsNudSQSw251JBLDbnUkEsfTpcKcqkglwpyqSCXCnKpIJcKcqkglwpyqSCXCnKpIJcKcqkgF/9F6NI0Y2masTTNWJpmLE0z1lOa8fvDi39IjpJ39GuFR7k7yt1R7o5yd5S7o9wd5e4od0e5O8rdUe4+o4yvfoaErid0PanrSV1P6npS15O6ntT1pK4n9XMndTmpy0HublXr5qBwaZyxNM5YGmcsjTOWxhlL44ylccbSOGNpnLE0zlgaZyyNM5bGGUvjjKVxxtI4Y2mcsTTOWBpnLI0zlsYZS+OMpXHG0jhjaZyxNM5YGmcsjTOWxhlL44ylccbSOGNpnLE0zlgaZyyNM5bGGUvjjKVxxnqKM35/qMsJXU7ockKX89fMff31+lLoSqErha4UulLoSqErha4UulLoSqErha4UulLoSqFr9arVq1avWr1q9arVq1avWr3SIGNpkLE0yFgaZCwNMpYGGUuDjKVBxtIgY2mQsTTIWBpkLA0ylgYZS4OMpUHG0iBjaZCxNMhYGmSspyDji08dFgufZqPUjVI3St0odaPUjVI3St0odaNPs1HoRqEbhW4UulHoRqEbhW4UulHoRqEbhW4UulHoRqEbhW4UulHoRqEbhW70YTa//Mn6UepWqVulbpW6zyDji++gzyjj17/++Mwyvjlt/d86erh4iOStkrdK3meW8cUPCKK3it7yPxRTmmYsTTOWphlL04ylacZ6SjN+f6ifQKnrSV0PwrcK3yp8q/Atvu8wy1iaZSzNMpZmGUuzjPWUZfz2QxLDjKVhxtIwYz2FGb8/1O2Ebid0O6HbCd2OPdQwylgaZSyNMpZGGUujjKVRxnqKMn5/qMtJXU7qclKXk7qc1OX4Qw2zjKVZxtIsYz1lGV/879T2R2j7I7T9gWnG0jRjaZqxNM1YT2nG7w91Pciddj9Cux+h3Q8MM5aGGUvDjKVhxtIwY2mYsTTMWBpmLA0zloYZS8OMpWHG0jBjaZixNMxYT2HGF/BouCM03PEQZ/z6paXZjtBsR2i2IzTbEZrtCM12POQZvz/U7YRuB83SaEdotCM02hEa7QiNdoRGO0KjHaHRjtBoR2i0IzTaERrtCI12YJqxntKMrwSRJ1r/kmdszTO25hlb84ytecbWPGM/5Rm/Pxw9XDwU7lrTjK1pxtY0Y2uasTXN2Jpm7Kc04/eH88NP5tD1pK4ndT2p60ldT+p6UteTup7U9aR+7qQu59LlIHf2vuunKON3D6bWLGNrlrGfsozfH5Yeth6OHi4eInap2KVil4pdKnap2KVil4qdve1ag4ytQcbWIGNrkLE1yNgaZGwNMrYGGVuDjK1BxtYgYz8FGb8/vPTw6OGth6WHzb9q/cwxvjte/E9GQy415FJDLjXkM8n46ns2dEWhK0JHLnXkM8v49S8JP8OMb07DT9NPLz89fnr7aflp++n4qa9Jv3LYGmtsjTW2xhr7Kdb4/aF/lB0F8SiIRx9TRx9TRyE8CuFRCI9CeBTCo4+powgeRfAogkcRPPqYOvqYOvqYOvqYOvqYOvqYOvqYOvqYOvqYOvqYOvpVw6NfNbxVrFvFulWsW59vt2p1q1a3anWrVrdqdatWt2p1q1afkcYXv2S5VazPUOO7b1UXFLqg0AWFLih1QakLSl1Q/rKg1AWlfv6krif7l/+duqDUBbFe+FArZa+UvVL26peHWil9pfSV0ldKXyl9pfSV0ldKX+lDrZS90odaKXml5JWSV0peKXnF//Zma7qxNd3Ymm5sTTf2U7rx3XeQLih1QakLQvJa5WqVq1Wu1gdbq1qtarWq1arWZ77xxdBb5WqVq1WuVrla5WqVq1WuVrla5WqVq1Wu1sfaZ8Dx1dBT15O6ntT1pK4ndT2p60ldD6uFD7VR7ka5G+VulLtR7ka5G+VulLvRR9oodaPUjVI3St0odaPUjVI3St0odaPUjVI3St3oA22UuVHmRpkbZW6UuVHmRpkbZW6UuVXmlv+OdWvCsZ8Sjt8f3npYeth6OHq4eIjUrVK3St0qdavUrVK3St0qdavUrVK3St0qdavUrVK3St0qdavUrVK3St0qdYvUYbSxNdrYGm1sjTa2Rhv7Kdr4/WHr4ejh4mHockKXE7qc0OWELid0OaHLCV1O6HJCl5O6nNTlpC4ndTmpy0ldTupyUpeTupzU5bBW9jDDXGNrrrGfco3fHx49vPWw9LD1cPRw8RCZ0w5IaAcktAMS2gEJ7YCEdkBCOyCYamxNNbamGltTja2pxtZUY2uqsTXV2JpqbE01tqYaW1ONranG1lRjP6Uavz+89PDo4a2HpYeth6OH/IdDQmMeoTGP0JhHaMzjIdT47jtIFxS6oNAFhS4I1dKgR2jQ4yHW+OrHMnVBqZ8/qetJXU/qenJ++Z7VBbFeF/7h2HmKNn7zrY4GG0eDjaPBxtFg42iwcTTYOE/Bxnc/lovfqtA3Gm0cjTaORhtHo42j0cZ5ija++rEMXZDQN0/Rxlf/uakLSl1Q6oJSF5S6oNQFpX7+pK4ndT2pnz2XLuey5aSSl0peKnmp5KWSl0peKnn22hvNNo5mG0ezjaPZxtFs42i2cTTbOJptHM02jmYbR7ONo9nG0WzjaLZxNNs4mm0czTaOZhtHs42j2cb/99CWcyk6l6JzKTqXonMpOpeicyk6l6JzKTqXonMpOpeicyk6l6JzKTqXonMpOpeicyk6l6JzKTqXonNxKGSe6o7ff6u6ntT1pK4ndT0Mz6XrwffVUeqOUneUuqPUHaXuKHVHqTtK3VHqjlL3WXJ88fFxlLuj3B3l7ih3R7k7yt1R7o5yd5S7gznj0Z7jaM9xtOc42nMc7TmO9hxHe46jPcfRnuNoz3Geeo4vPrJudetWt25161a3bnXrVrdudetWt259ot1q1q1m3WrWrWbdatatZt1q1q1m3WrW7WbdatatZt1q1q1m3WrWrWbdatatZt1uFj7QSrErfaCVQlcKXSl0pdCVQlcKXSl0pdCVQlcKXSl0pdCVQlcKXSl0pdCVQlcKXenXIkuZK2WulLlS5kqZK2WulLlS5kqZa9WqVavPcuOLN12rWK1itYrVKlarWK1itYrVKlarWK1itYrVKlarWK1itYrVKlarWK1itYrVKlarWK1itYrVKlarWK1itYuFD7NR6kapG32YjTI3ytwoc6PMfVYbv/7izCh0o9CNQjcK3Sh0o9CNQjcK3Sh0o9CNQjcK3Sh0g/8I6Gi5cbTcOFpuHC03jpYbR8uNo+XG0XLjaLlxtNw4T+XG7w8vPTx6eOth6WHr4ejh4iFCtwrdKnSr0K1CtwrdKnSr0K1CtwrdKnSr0K2+6FaZW2VulblV5laZW/5r1qPlxtFy42i5cbTcOFpuHC03jpYbR8uNo+XG0XLjaLlxtNw4Wm6cp3Ljt7/AxnbjaLtxtN042m4cbTeOthtH242j7cbRduNou3G03TjabhxtN462G0fbjaPtxtF242i7cbTdONpuHG03zlO78ftfCYRmQUKzIKFZkNAsCPYbR/uNo/3G0X7jaL9xtN842m8c7TeO9hvnqd/49a8ENAiCBcfRguNowXG04DhacBwtOI4WHEcLjqMFx9GC42jBcbTgOFpwHC04jhYcRwuOowXH0YLjaMFxtOA4TwXHrw9DlxO6nNDlhC4ndDmhywldTuhyQpcTupzU5eif3Q+teoRWPUKrHqFVj9CqR2jVI7TqEVr1wGbjPDUbvzncp17jt0+l1WbjarNxtdm4T83G735yrVYbV6uN+1Rt/P5w8VC4Wy02rhYbV4uN+1RsfDV1IW+fqo3fH+p6Yn7536kLSl1Q/vIJlLqi1BWlfgKlfwKlbih1Q6mfQKn7uXQ/SJ+98Va7javdxtVu42q3cbXbuNptXO02rnYbV7uNq93G1W7jardxtdu42m1c7TbuU7fxBQT2zlttN+5Tu/Hrz/P8hbxU8lLJSyXP3nqrBcfVguNqwXE1xLgaYlwNMa6GGFdDjKshxtUQ42qIcTXEuBpiXA0xroYYV0OMqyHG1RDjPoUYv/50vfThdKkhlxpy6aPJUoyrKcZ9SjF+f6jb+Ws9Xih5qSCXCnK5IKnruXQ9+GQ6it1R7I5idxS7o9gdxe4odkexO4rdUeyOYncUu6PYHcXuKHZHn0xHqTtK3VHqjlJ3lLqj1B2l7ih1Rx9KR5k7ytxR5j4jjC84P0rdrWLdKtatYt0q1q1i3SrWrWLdKtatYt0q1q1ifUYYXwz9VrVuVetWtW5V61a1blXrVrVuVetWtW5V61a1PjOMXz+1b3XrVrdudetWt259nt1uFj7PPkOMX/9IlnL3mWJ8820e/TZvPSw9bD0cPVw8RPBKwSt9opViV4pdKXal2JViV4pdKXal2BX+ycXVHOM+5Rhf/Cqr9KFWCl4peKXglYJXCl4peO1utbrlUcbVKONqlHE1yrgaZVyNMq5GGfcpyvjqhwT1atWrVa9WvVr1atWrVa9WvVr1atWr9anW2KtaTTOuphlX04yracbVNONqmnE1zbiaZlxNM66mGVfTjKtpxtU042qacTXNuJpm3Kc04/eHi4f4TBuFbhS6UehGoRuFbhS6UehGoRuFbhS6UehGH2mjzI0yN8rcKHOjzI0yN8rcKHOjzK0yt8rcKnOfWcYXr49V6lapW6VulbpV6lapW6VulbpV6lapW6VulbpV6lapW6VulbpV6lapW6VulbpV6j7TjK8+6VLXk7qe1PUYd5hmXE0zrqYZV9OMq2nG1TTjappxNc24mmZcTTOuphn3Kc34/aEuJ3Q5ocsJXU7ockKXE7qc1OWkLid1OanLSV1O6nJSl5O6nNTlpC6HtbLHGYYZV8OM+xRm/P6QH2cYZlwNM66GGfcpzPjtbymEtj9C2x+h7Y/Q9kdo+wPTjKtpxtU04z6lGV9NHcHT7kdo9wPjjKtxxtU442qccTXOuBpnXI0zrsYZV+OMq3HG1TjjPsUZX/zU0nhHaLwjNN4RGu8IjXeExjtC4x2h8Y7QeEdovCM03hEa7wiNd4TGOzDQuBpoXA00rgYa9ynQ+P2hLid1OanLSV1O6nJSl5O6nNTlsFh/84n29//8cXg/5Rm/P0w9vPTw6OE3f8//j8el32rr4ejh4uHfpO6Ph7qe0PWErid0PX+Tuj8e/u3CyB9PdTuh2wndTup2UreTup3U7aRuJ3U7qZ86qctJXU7qci5dDmKXil0qdqnYpWL3xZvuj4elh828pmKXil0qdp/vuq8/z1O5S+UulbtU7r542f3xsPVQtxO6ndTtpH7ypC4ndTmpy0ldTupyUpeD2F0qyKWCXCrIpYJcKsilglz6VLpUj0v1uFSPS59Kl9pxqR2X2nGpHZfacakdl9pxqR2X2nGpHZfacakdl9pxqR2X2nGpHZfbkbqcS5eDD6WjzB1l7ihzR5k7ytxR5o4yd5S5o8wdZe4oc0eZO8rcUeaOMnf8K4JHoTsK3VHojkJ3FLqj0B2F7ih0R6E7Ct1R6I5CdxS6o9Dd6tWtXt3f1T3+eHz0W731sPSw9XB++Q5a/FZDFxS6oNAFoVu3unWrW7c+z25V61a1blXrVrVuVetWtW5V61a1blXrVrVuVetWtW5V63a18HlW3/2bmn88Tv1WLz08enjrYelh6+Ho4eIhUldKXSl1pdSVUldKXSl1pdSVUldKXSl1pdSVUvcZYfz6xVyKXSl2pdiVYleKXSl2pdi1PtFavWr1qtWrVq9avWr1qtWrVq9avWr1qtWrz/Dii19ftZrValarWa1mtZrValarWa1mtZrV+jxrFatVrFaxWsVqFau/+9dd/nTMauETbZS7z/zi17/iGQVvFLxR8EbBGwVvFLxR8EbBGwVvFLzRB9oodqPYjWI3it0odqPYjWI3it0odqPYjWI3it18V6X647GuJ3U9qeu5dD2I3Sp2q2+7/eW331a5W+VulbtV7la5W+VulbtV7la5W+VulbtV7j4jjK+GHrqe0PWErid1PanrSV1P6npS15O6ntTPndTlpC4ndTnG3TcRxj8eph5eenj08NbD0sPWw9HDxcPQ5YQuJ3Q5ocsJXU7ocvQPOX6TYfzjoW4ndDup20ndTup2UreTup3U7aR+6qQuJ4fXmrodFsseaKGVj9DKx0OI8evvV+18fJNh/ONh6WHr4ejh8vcrchf8F59DOx+hnY+HEOP3D6aHGOO7Y11R6IpCV4Tsae0jtPYRWvsIrX2E1j4eYoyv1pO6ntT1pK4ndT0In4Y7QsMdoeGO0HBHaLgjNNzxTYzxj4ejh4uHocsJ/qOyodmOhyDju29VFxS6oNAFRf/yv1NXFLqi1BWlfv6kLij18yd1PanrSV1P6udP6nJSl8NyyZOtNMxYGmYsDTOWhhnrKcz43cOiNMtYmmUszTKWZhlLs4ylWcbSLGNplrE0y1iaZaynLOP3h7qc0OWELid1OanLSV1O6nJSl5O6nNTlpC4ndTmpy7l0OQhdKnSp0KVClwqdve1Ko4z1FGX8/nD0cPEQmUtlLpW5VOZSmUtlLpW5VOZSmUtlLpW5VOZSmft8z337Ui5NMtZTkvHrX2CnYpeKXSp2lwpyqSCXCnKpIJcKcqkglwpyqSCXCnKpIJcKcqkglwpyqSCXCnLxHz0sDTOWhhlLw4ylYcbSMGNpmLE0zFgaZiwNM5aGGUvDjKVhxtIwY2mYsTTMWBpmLA0zloYZS8OMpWHG0jBjaZixNMxYGmYsDTOWhhlLw4ylYcbSMGNpmLGewozfH+pyQpcTupzU5aQuJ3U5Vv0oDTOWhhlLw4ylYcbSMGNpmLE0zFgaZiwNM9ZTmPH7w6OHtx6WHrYejh4uHoYuJ3Q5ocsJXU7ockKXE7qc0OXE8GPwVrNuNetWs24169an2a1i3SrWrWJ9RhlfjSD1syd1PawWPs9KuSvlrpS7Uu5KuSvlrpS7Uu5KuSvlrpS7Uu5KuSvlrpS7Uu5KuSt9npVSV0pdKXWl1JVSV0pdKXWl1JU+zkqZK2WulLlWrVq1atWqVatWrVq1atWqVatWrT6TjC9+PdcqVqtYrWK1itUqVqtYrWK1itUqVqtYrWK1itUqVqtYrWK1itUqVqtYrWK1i4UPs1HqRqkbLlSVBhlLg4ylQcbSIGNpkLE0yFgaZCwNMpYGGUuDjKVBxtIgY2mQsTTIWBpkLA0ylgYZS4OMpUHG0iBjaZCxNMhYT0HG7w91OVb7KM0xluYYS3OMpTnG0hxjPeUYvz88enjrYelh6+Ho4eIhQrcK3Sp0y39TujTHWE85xnffqi4odEGhCwpdUOqCUheUuqD8ZUGpC0r9/EldT+p6UteTup6/Ju9bZjHKWBplLI0ylkYZS6OMpVHG0ihjaZSxNMpYGmUsjTKWRhlLo4ylUcbSKGM9RRm/P9TlhC4ndDmpy0ldTupyUpeTupzU5aQuJ3U5qctJXc6ly7EnWmjdI7TuEVr3CK17YI6xNMdYmmMszTHWU47x60NkTtseDynGr39RpnWP0LpHaN0jtO4RWvcIrXuE1j1C6x6hdY/Qukdo3SO07hFa9wite4TWPULrHqF1j9C6R2ikIzTSERrpCI10hEY6QiMdoZGO0EhHaKQjNNIRGukIjXSERjpCIx2hkY7QSEdopCM00hEa6QiNdIRGOh6ii1//SifVK010YHaxNLtYml0szS6WZhdLs4ul2cXW7GJrdrE1u9iaXeyn7OL3h6WHrYejh/jPxbaGF1vDi63hxdbwYmt4sTW82BpebA0vtoYXW8OLreHF1vBia3ixNbzYGl7sp/Diq5+TqetJXU/qelLXc+l6kLtU7lK5S+UulbtU7lK5S+UulTt717XGF1vji63xxdb4Yj/FF1987qRyl8pdKnep3KVyl8pdKnep3KVyl8qdvexa04ut6cXW9GI/pRdf/NS61JBLDfnML777z71/OS79T2495B/TxUO05FJLLrXkUksufTZd/EcO+ynF+P23qusJXU/oevLvfvgOSl1Q6oKsUdVPMcY3p7eflp+2n46fLp/aH0DspzTj16efccY3p+mn9lF29EF19EH1GWh88VP8KIRHITwK4VEIj0J4FMLDf/6+n0KN7451RYjhUQyPYngUw6MPq6MQHoXw6MPq6MPq6MPq6MPq6MPq6MPq6NcQj34N8dYvBX6mGl98Ctyq16163arXrU+4W+W6Va5b5bpVrlvlulWuW59wtz7hbhXrVrFuFctzja25xn7KNb76VlMXlLqg1AWlLih1QakLSl1Q6mdP6npYLvzdr1LySr9yWcpd/fKVy1LySskrJa+UvFLySskrJa+UvFLySskrJa+UvFLySh9ppdyVPtJKqSulrpS6UupKqSulrpS6UupKqSulrlWsVrFaxWp9oPUvv8/WKlarWJ/Zxnf/uYvfauiCQhcUuqDQBYUuKH5ZUOjvk7Ta1WpXq12tdrXa1WpXq12tdrXa1WpXq12tdrXa1W4XPtNG0RtFbxS9UfRGn2ij4I2CN/pEG8VuFLtR7EaxG8VuFLvRJ9roE22UuVHmPsONL0AfpW6UulHqRqkbpW5++TP5o9yNcjfK3Sh3o9yNcrfK3Sp3q9ytcrfK3Sp3q9ytcrfK3Sp3q9ytcrfK3Sp3q9ytcrfK3Sp3q6+6VepWqVulbpW6VerW/+zkKnSr0K1Ctwrd8p+ZxGhja7SxNdrYGm1sjTa2Rhtbo42t0cZ+ija+mED4ekLXE7qe0PWErid0PaHrCV1P6HpMrYdw4/dvEIw3tsYb+yne+O4/9/xyrCtKXVHqilJXlLqi65cV2WMttBcS2gsJ7YWE9kJCeyEPIccXPyTaDAlthmDMsTXm2Bpz7KeY4/eHup7Q9YSuB+nTXkhoLyS0FxLaCwnthYT2QkJ7IaG9EEw5tqYcW1OOrSnH1pRja8qxNeXYmnJsTTm2phxbU46tKcfWlGNryrE15diacmxNObamHFtTjq0px9aUY2vKsTXl2JpybE05tqYcW1OO/ZRy/P5Ql5O6nNTlpC4ndTmpy0ldDmslD7PRkONoyHE05DgachwNOc5TyPHbh9lozHE05jhPMcevD4W60ZDjaMhxNOQ4GnIcDTmOhhxHQ46jIcfRkONoyHE05DgachwNOY6GHOcp5Pj9oS4ndTmpy0ldzqXLQepSqUulLpW65L/GNhpyHA05joYcR0OOoyHH0ZDjaMhxNOQ4GnKcp5Dj94e6nNDlhC4ndDmhy0ldTsYPP5lT15O6ntT1pK4ndT2p60ldD3J3KT6X4nMpPpe+sy6F51J4LoXnUnguhedSeC6F51J4LoXnUnguhedSeC6F51J4LoXnUngufWNdis6l6FyKzqXoaOdxnjqP33+buh1m59Lt4CvrKHRHoTsK3VHoDv/V63mqO37/rbYejh4uHiJ2R7E7it1R7I5idxS7o9gdxe4odkexO4rdUeyOYncUu6PYHcXu6AvrKHVHqTtK3VHqbhXrVrFuFetWsW59mt2q1a1a3arVrVrdqtWtWt2q1a1a3arVrVrdqtWtWt2q1a1a3arVrVrdqtWtWt2q1Y1/kWy04zjacRztOI52HEc7jqMdx9GO42jHcbTjOE8dx+8P/WlWil0pdqXYlWJXil0pdqXYlWJXil0pdqXYlWJXil0pdqXYlWJXil0pdqXYlT7NSqkrpe6z4/jqIzL3h2Mkr1WuVrla5WqVq/WJ1qpWq1qtarWq1apWq1qtarWq1apWq1qtarWq1apWq1qtarWq1apWq1qtarWq1apWq1qtD7TWB1q7VvhAG2VulLlR5kaZG2VulLlR5kaZG2VulLlR5kaZG2VulLlR5kaZG2Xus+D49Ze+RqEbhW4UulHoRqEbhW4UulHoRqEbhW5+eZqNYjeK3Sp2q9itYreK3Sp2q9itYreK3Sp2q9itYreK3Sp2q9itYreK3Sp2q2+6VepWqVulbpW65QrWaMNxnhqO3x/qelLXk7qe1PUYddhvHO03jvYbR/uNo/3G0X7jaL9xtN84T/3Grw9DlxP8V4Cw3zjabxztN472G+ep3/jtgwkLjqMFx9GC4zwVHL8/1E+e1O2kbid1O6nbSf3kSV1O6nJSl8Nm2fMsNAwSGgYJDYOEhkFCwyAPxcbvD1sPRw8XDxE7jYKERkFCoyChUZDQKEhoFCQ0ChIaBQmNgoRGQUKjIKFRkNAoSGgUJDQKEhoFCY2ChEZBQqMgD7XGF79O1r5HaN8jtO+BxcbRYuNosXG02DhabBwtNo4WG0eLjaPFxtFi42ixcbTYOFpsHC02jhYbR4uNo8XG0WLjaLFxtNg4WmwcLTbOU7Hx60e9lj1Cyx6hZQ9sNo42G1ebjavNxtVm42qzcbXZuE/Nxu8PWw/pN/tXi42rxcbVYuNqsXG12LhabFwtNq4WG1eLjavFxtVi42qxcbXYuFpsXC02rhYbV4uNq8XG1WLjarFxtdi4WmxcLTauFhtXi42rxcZ9KjZ+f3jrYelh6+Ho4aKQqdClQpcKXSp0qdClQpcKXSp0qdClQpcKXSp0qdAl/yGR1V7jPvUa332ruqDUBSF4lypyqSKXKnKpIpcqcqkilypyqSKXPpY+04svhn6pI5c6cqkjlzpyqSOXOnKpI5c6cqkjlzpyqSOXOnLpg+lSQy59MF3qx6V+XO6H/rn61QDjaoBxNcC4TwHGF/87j5J3lLyj5B0l7yh5R8k7St7RZ9NR7o5yd5S7o9wd5e4od0e5O8rdUe6OcneUu6PcHeXuKHdHuTvK3VHujnJ39OuDR6m7VaxbH2i3anWrVrdqdatWt2p1q1a3anWrVrdqdatWt2p1q1a3anWrVp8Bxq+/XHurV7d6datXt3p1q1e3enWrV7d6datXt3p1q1e3enW7V/g0K4WuFLpS6EqhK4WuFLpS6Mr/4EYpdaXUlVJXSl0pdaXUlVJXSl3pw6wUulLoSqErha4UulLoSqErha4UulLoSqGrX74OWYpdq1mtZrWa1WpWq1mtZrWa1fo4axWrVaxWsVrFahXrM7349a8EWs1qNavVrFazWs1qNavVrFazWs1qNavVrFazWs1qNat/MavdLHygfQYYX/znjoI3Ct4oeKPgjYI3Ct4oeKPgjYI3Ct4oeKPgjT7RRrkb5W6Uu1HuRrkb5W74n4hezTCuZhhXM4yrGcbVDONqhnE1w7hPGcavDy9dD3K3+rZbpW6VulXqVqlbpW6VulXqVqlbpW6VulXqVqlbpW6VulXqVqlbpW6VulXqVl92q8ytMrfK3Cpzq8ytMrfK3Cpzi8w95Be//0USJhhXE4yrCcbVBONqgnE1wbiaYFxNMK4mGPcpwfj9oS4ndDmhywldTuhy9I+KYH5xNb+4ml9czS+u5hdX84ur+cXV/OJqfnE1v7iaX1zNL67mF1fzi6v5xdX84mp+cTW/uJpfXM0vruYXV/OLq/nF1fzian5xNb+4ml9czS+u5hdX84ur+cXV/OI+5Rdf/HJXKx+hlY/Qykdo5eMhwfjuO+j+5VhXlLqi1BXlLytC9jTcERruCA13hIY7QsMdoeGO0HBHaLgDU4yrKcbVFONqinE1xbiaYlxNMa6mGFdTjKspxtUU42qKcTXFuJpiXE0xrqYYV1OM+5RifMGAJjtCkx0YY1yNMe7/T4zx/wJafyLt",
    "check_requests.csv": "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",
    "check_types.json": "eNqr5lJQUHJUslKoBjKAzNzEivjk/NyCotTi4viUxMpioJShDkQuvyy1qCQzNzW+OCMzraQ4viC1CKQEqMIIqKAWpErJGb9RRgSNMoYb5YLfKGOCRpmAjOKq5QIA0SFDiw==",
    "disruption_notice.docx": "eNoL8GZmEWFgYOAAYsWIk/5SG14DWesYGRiEgXS0c35eSWpeSXxIZUFqcaxeRW5ObcBev8MGAvcquU5rd8lKCDh5Wn0wZnKubJhc66nzZvPTYu/f3yxyXzZwPb77ffX66LdN4tFn3ih9/eS2NUhhZoas794/EftNvgcVMG56oJyo//1EkWlM6etaJ7FQnzund075ssB0tiTzhi7OlUrJZxi9bD8vEZ7hPyPg/ra3c80mcgVlnnqk2P6O0/3GD6V55V9rdSZd3CzS7/5o0lVvj5PWzEsfVXl/C/cq9goIrXzw4Y1QfHjTFXFhsSfvGya/W6s3ea7rR76de5xW6PwV3XzVbJbvCq+v+8+2ziuUmXtwc12ht6VUyrrJ7OvPeTC42//9mvjuoXQAStjsbHQp3ABkaQHDhhtIxxel5hTr64HI3vPWfIcMeNgezA12uZcZxdYSMFmPY6W2FnuHkHlvhpzXocXb1ZmZFdjcbu+3P537fYPxzkSfY9ZsvqHMjup7jfyMLfiPf+XzOHVI07C6nUfM58LH0OpDkU82TVYTFtLs8OZZNufwvEsq6luUQu0WaE++6K5dpLl4meOJ7gse5qV7l368y/AvcVKcYcferAYe7wP1OfZ9bo8Onl7tOr1+zg8vkUiX3pkH77q7Xl0dKyqmkf/yePcfTlSPrd44XfUw0FPqnAwMgkCR8vyiFP2U/OTSXGDMg6L87DTH/MsGIsff13Cd/n4lky3VxXfZusUZ7AELZd+0yTwv3frkxrT5kyfl91+e9jVoY5PQwaeWhW/+//75/snRy7PlpyrxWkxxSy+x6dJk1PXR/BrsJn+t+8UsoS8x02MkeSVzGV/6/sva5e2t/Ipri7qjY/Ku0y+uVc82akviFj0+ceOCw5t7C0W/P7xmu3Fu4dJSN4YkjwDNaUc+toTGZM1iP3loSu71W3o79N5cDd4S03LnGmNTdsOzcqHY3NoEtVsVmg0tOiyNyS88Hz15m3Pq0JM93Xnyb113fe8wnbIk4+TxA08ci2W3PHerThd5KM3f90NXIFrc65EZz9au1xfvq+5+yuGi0Vz6wkr7IXdpzrR3FRs/rWXa5C29zmjXs9Ymfr9pU96qz2WTW7SjYzGHTPqlzfFM4qdy5qysmqBZWX2uZzGP9Zpe2+rPi+6JZ6i09T7ind4lHuR5/5/z5toFLw4ufZwlUvN/79s3ku/9FfavW/z98245g93+hl3rF6UYMTzKMXvPWyh09D2bw565tt/afqhJxfM27Pix7QXvx1IRdWaFe/r233/q9bE7xNh+2X6R8WMVw5Gfry7Xv3+UPN81/U/RRcu/7gIt8bucU+1lnG+87Jj8nyXAm5FJhBl3RoeBJYwM2LM9ugHouQFhgAwjSt5A14ie2hAavzJiSXsB3qxsIGlmINwJpJ8zg3gALh/rDw==",
    "fleet_limits.toml": "eNorTk0szs9TsFVQMjIwMndU4ioGC8QXlyQWlcCEdQ2MdQ0M4XKpeSkIGTNdIwslLgDh7xMK",
    "fleet_register.csv": "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",
    "planning_limits.docx": "eNoL8GZmEWFgYOAAYsWIk/5SG14DWesYGRiEgXS0c35eSWpeSXxIZUFqcaxeRW5ObcBev8MGAvcquU5rd8lKCDh5Wn0wZnKubJhc66nzZvPTYu/f3yxyXzZwPb77ffX66LdN4tFn3ih9/eS2NUhhZoas794/EftNvgcVMG56oJyo//1EkWlM6etaJ7FQnzund075ssB0tiTzhi7OlUrJZxi9bD8vEZ7hPyPg/ra3c80mcgVlnnqk2P6O0/3GD6V55V9rdSZd3CzS7/5o0lVvj5PWzEsfVXl/C/cq9goIrXzw4Y1QfHjTFXFhsSfvGya/W6s3ea7rR76de5xW6PwV3XzVbJbvCq+v+8+2ziuUmXtwc12ht6VUyrrJ7OvPeTC42//9mvjuoXQAStjsbHQp3ABkaQHDhhtIxxel5hTr64HI3vPWfIcMeNgezA12uZcZxdYSMFmPY6W2FnuHkHlvhpzXocXb1ZmZFdjcbu+3P537fYPxzkSfY9ZsvqHMjup7jfyMLfiPf+XzOHVI07C6nUfM58LH0OpDkU82TVYTFtLs8OZZNufwvEsq6luUQu0WaE++6K5dpLl4meOJ7gse5qV7l368y/AvcVKcYcferAYe7wP1OfZ9bo8Onl7tOr1+zg8vkUiX3pkH77q7Xl0dKyqmkf/yePcfTlSPSXVlxLwBesqbh4FBEChSnl+Uop+Sn1yaC4x5UJTvnX6wb7aBQNv7Wq7T39dx7p5dFpgQGpqbn7vkbmj/RRb/JtXkxRuFZ21f73npTauaQOTOHscH9+X3H5czrv4XnL3NtejUrDn+74TOXZgSprX53M/br7/3z7csluthyeV9VtPeZy8un5arlrtz5cUKMZGe07fmhN8znymwbs0GtvJ0aZOHN08F8drduRS1ZVqK8zaX54cYtoplTvJx5T31QclDb+2d0tzLrK8OxdkW805JfNN2QTF3ongx7zEW1mWha/ckJ/I8E5hjquN7yT8+TalEd5fH7xs8QX9Faz6scrsWsbpa9U+Q/GxLWf24P37K2Zt1X8zZfyjoMX/QpO7a5d/F+TfKHFloc832cHc9E3Mq00W2/+uV/UKSb7y5uNj1+cVDoVlPY1muvXTOuWB7a9GWc+4HZtvEHRFe/mbHim+hzcU9B5Lnl24/tWnT4o4HvA/FzqqpsFxyOqTXlDQ92Uhj24proT0vJ+9wUrrQeLHhW7rE+tNbwzzffFvHscLfs+eqiONjRUvnorm+bB050idXHJdwm3uzlC17yeUXboLrnC3b9kmZzNJr881k6f19Wq/3hpP/Uqkt23RnbFp/4W6WemyTdXA6++k5dk+TIvfqra6L+nQ1N61I5Wb3XRfF2XM8r7w+UZc85/Ph2pwN+QLsbzKPrCqJ+GUpG3bq4Qq9e/XMXfsDvBmZRJhxlwgwsISRAXv5gG4AerZBGCDDiJKJ0DWiJ0uExq+MWBJpgDcrG0iaGQh3AmkBFhAPAMq8+NE=",
    "published_plan.csv": "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",
}

# name: (seed, empty base and segment, allowance layout, reused id row)
HIDDEN = {"h1": (1, True, "cap", False), "h2": (3, True, "short", False), "h3": (1, False, "bind", True),
          "h4": (3, False, "bind", False), "h5": (5, False, "bind", True), "h6": (6, False, "bind", False)}
# name: (seed, table, Word form of its data rows)
FORMS = {"h7": (7, "allow", "sdt"), "h8": (8, "allow", "cxml"), "h9": (9, "allow", "alt"),
         "h10": (10, "close", "sdt"), "h11": (11, "close", "cxml"), "h12": (12, "close", "alt"),
         "h13": (13, "avail", "sdt"), "h14": (14, "avail", "cxml"), "h15": (15, "avail", "alt")}
PLAN_ROW = ["request_id", "tail", "base", "aircraft_class", "segment", "check_type", "decision", "start_date",
            "finish_date", "compress_days", "overtime_shifts", "overdue_days", "moved", "deferral_reason"]
SETTLE_ROW = ["request_id", "overtime_cost", "allowance_shifts", "paid_shifts", "allowance_credit",
              "settled_overtime_cost"]
SETTLE_GROUP = ["allowance_granted", "overtime_cost", "allowance_used", "allowance_credit", "settled_overtime_cost"]
PLAN_SUMMARY = ["season", "plan_terms", "overtime_pool_shifts", "fleet_overtime_used", "checks_scheduled",
                "checks_deferred", "moved"]
_MISSING = "<missing>"
_CASES: dict[str, Any] = {}
# Checks may run in parallel threads; each folder is built and run once, one at a time.
_CASE_LOCK = threading.Lock()
# one untrusted run at a time; held across the run and the sweep of what it left
_RUN_LOCK = threading.RLock()


def _seal(root: Path) -> None:
    for path in root.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    root.chmod(0o755)


def _shipped_root(parent: Path) -> Path:
    root = parent / "data"
    root.mkdir()
    for rel, blob in _SHIPPED_DATA.items():
        (root / rel).write_bytes(zlib.decompress(base64.b64decode(blob)))
    _write_governing_docs(root)
    return root


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename it,
    so a program the agent wrote can land at mode 0600 (owner-only). The checks
    run that program as an unprivileged user, which then cannot open it, and a
    correct submission would score zero for a reason that has nothing to do with
    the task. The verifier runs as root, so widening the mode is always allowed
    here and it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _folder_state(path: Path) -> dict[str, str]:
    state = {}
    for item in sorted(path.rglob("*")):
        rel = str(item.relative_to(path))
        state[rel] = hashlib.sha256(item.read_bytes()).hexdigest() if item.is_file() else "dir"
    return state


def _prepare_run(work: Path) -> tuple[Path, Path]:
    out = work / "out"
    cwd = work / "cwd"
    for folder in (out, cwd):
        folder.mkdir()
        folder.chmod(0o777)
    work.chmod(0o777)
    return out, cwd


def _stop_untrusted(group: int) -> None:
    """Kill the run's process group and, when isolated, every process left under the dropped uid."""
    if os.name != "posix":
        return
    try:
        os.killpg(group, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if os.geteuid() != 0:
        return
    import pwd
    uid = str(pwd.getpwnam("nobody").pw_uid)
    for _ in range(20):
        found = False
        for entry in sorted(Path("/proc").iterdir()):
            if not entry.name.isdigit():
                continue
            try:
                status = (entry / "status").read_text(encoding="utf-8")
            except OSError:
                continue
            line = next((row for row in status.splitlines() if row.startswith("Uid:")), "")
            if uid not in line.split()[1:2] or "State:\tZ" in status:
                continue
            found = True
            try:
                os.kill(int(entry.name), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        if not found:
            return
        time.sleep(0.05)


def _launch(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run an untrusted command in its own session; when this returns, every process it started is gone."""
    with _RUN_LOCK, tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(_untrusted_command(command), cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=err,
                                start_new_session=True)
        try:
            proc.wait(timeout=RUN_LIMIT)
        except subprocess.TimeoutExpired:
            _stop_untrusted(proc.pid)
            proc.wait()
            raise
        finally:
            _stop_untrusted(proc.pid)
        err.seek(0)
        return subprocess.CompletedProcess(command, proc.returncode, "", err.read())


def _run_program(data: Path, work: Path, stray: list[str] | None = None) -> dict[str, Any]:
    """Run the stated command from a foreign working folder; return parsed outputs.

    OUT_DIR exists (mode 0777) before the run. When `stray` is given, every write the run made
    outside OUT_DIR (the working folder, the folder that holds OUT_DIR, the data folder) is appended to it.
    """
    out, cwd = _prepare_run(work)
    before = _folder_state(data)
    try:
        run = _launch(["python3", str(SCRIPT), str(data), str(out)], cwd)
        if run.returncode != 0:
            raise subprocess.CalledProcessError(run.returncode, run.args)
    finally:
        if stray is not None:
            stray.extend("work/%s" % n for n in sorted(os.listdir(work)) if n not in ("out", "cwd"))
            stray.extend("cwd/%s" % n for n in _folder_state(cwd))
            if _folder_state(data) != before:
                stray.append("data folder changed")
    got = {}
    for name in ARTIFACT_NAMES:
        got[name] = json.loads((out / name).read_text(encoding="utf-8"))
    return got


def _shipped_case() -> dict[str, Any]:
    with _CASE_LOCK:
        return _shipped_case_locked()


def _shipped_case_locked() -> dict[str, Any]:
    if "shipped" not in _CASES:
        root = Path(tempfile.mkdtemp(prefix="hangar-shipped-"))
        root.chmod(0o755)
        data = _shipped_root(root)
        _seal(data)
        _CASES["shipped"] = {"data": data, "want": derive(str(data))}
    return _CASES["shipped"]


def _rewrite_tables(path: Path, change) -> None:
    tables = _docx_tables(str(path))
    blocks = []
    for key, rows in tables.items():
        rows = change(key, [dict(r) for r in rows])
        head = list(rows[0].keys())
        blocks.append(("p", key))
        blocks.append(("tbl", [head] + [[r[h] for h in head] for r in rows]))
    write_docx(str(path), blocks)


def _mutant_data(name: str, root: Path) -> Path:
    data = _shipped_root(root)
    if name == "m1":
        used = {b: derive(str(data))["region_%s.json" % b]["overtime_shifts"] for b in BASES}
        top = max(BASES, key=lambda b: (used[b], b))
        low = min(BASES, key=lambda b: (used[b], b))
        grant = {b: used[b] for b in BASES}
        grant[top] = max(0, used[top] - 9)
        grant[low] = used[low] + 3

        def change(key, rows):
            if key == "base/allowance_shifts":
                for r in rows:
                    r["allowance_shifts"] = str(grant[r["base"]])
            return rows
        _rewrite_tables(data / "planning_limits.docx", change)
    else:
        def change(key, rows):
            return [] if key == "tail/available_from" else rows

        tables = _docx_tables(str(data / "disruption_notice.docx"))
        blocks = []
        for key, head in (("base/from", ["base", "from", "days"]), ("tail/available_from", ["tail", "available_from"])):
            rows = change(key, tables.get(key, []))
            blocks.append(("p", key))
            blocks.append(("tbl", [head] + [[r[h] for h in head] for r in rows]))
        write_docx(str(data / "disruption_notice.docx"), blocks)
    _seal(data)
    return data


def _case(name: str) -> dict[str, Any]:
    """Generate (or rebuild) one data folder, derive its expected outputs and run the program once."""
    with _CASE_LOCK:
        _build_case(name)
    case = _CASES[name]
    assert "error" not in case, case.get("error")
    return case


def _build_case(name: str) -> None:
    if name not in _CASES:
        root = Path(tempfile.mkdtemp(prefix="hangar-%s-" % name))
        case: dict[str, Any] = {}
        try:
            if name in HIDDEN:
                seed, empty, stype, x1 = HIDDEN[name]
                data = root / "data"
                data.mkdir()
                inst, want = _planted_corpus(name, seed, empty, stype, x1, data)
                case["meta"] = inst["meta"]
            elif name in FORMS:
                seed, table, kind = FORMS[name]
                data = root / "data"
                data.mkdir()
                inst, want = _planted_corpus(name, seed, False, "bind", False, data)
                case["meta"] = inst["meta"]
                _reform(data, table, kind)
                _seal(data)
            else:
                data = _mutant_data(name, root)
                want = derive(str(data))
            case["data"], case["want"] = data, want
            work = Path(tempfile.mkdtemp(prefix="hangar-run-"))
            case["stray"] = []
            with _RUN_LOCK:
                root.chmod(0o755)
                try:
                    case["got"] = _run_program(data, work, case["stray"])
                finally:
                    root.chmod(0o700)
                    shutil.rmtree(work, ignore_errors=True)
        except Exception as exc:  # recorded; every check on this folder then fails with this message
            case["error"] = "%s: %s" % (type(exc).__name__, exc)
        _CASES[name] = case


def _planted_corpus(name: str, seed: int, empty: bool, stype: str, x1: bool,
                    data: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Write a hidden folder whose expected plan fires every planted branch.

    The first attempt uses the seed itself; a later attempt (a derived seed) is used
    only when a draw misses a planted branch, so every seed yields a usable folder.
    """
    last: Exception | None = None
    for attempt in range(8):
        shutil.rmtree(data, ignore_errors=True)
        data.mkdir()
        inst = corpus("hidden", seed + 100003 * attempt, 8, empty, stype, x1, str(data))
        _seal(data)
        want = derive(str(data))
        try:
            _assert_planted(name, inst, want)
            inst["meta"]["draw"] = attempt
            return inst, want
        except AssertionError as exc:
            last = exc
    raise AssertionError("%s: no planted folder after 8 draws (%s)" % (name, last))


def _assert_planted(name: str, inst: dict[str, Any], want: dict[str, Any]) -> None:
    meta, s = inst["meta"], want["summary.json"]["settlement"]
    rows = want["policy_audit.json"]["checks"]
    assert any(r["deferral_reason"] == "no_slot" for r in rows), name + ": no_slot deferral missing"
    assert any(r["deferral_reason"] == "plan_trade" for r in rows), name + ": plan_trade deferral missing"
    assert any(r["allowance_shifts"] < want["region_%s.json" % r["base"]]["allowance_granted"] for r in rows), name
    over = [b for b in BASES if want["region_%s.json" % b]["allowance_used"]
            > want["region_%s.json" % b]["allowance_granted"]]
    assert over, name + ": no base uses more than its own grant"
    if meta["stype"] == "cap":
        assert s["allowance_left"] == 0 and s["allowance_used"] == want["summary.json"]["fleet_overtime_used"]
    else:
        assert s["allowance_left"] == 0 and s["allowance_used"] < want["summary.json"]["fleet_overtime_used"]
        assert any(0 < r["allowance_shifts"] < r["overtime_shifts"] for r in rows), name + ": no partly paid check"
    if meta["empty_base"]:
        eb = want["region_%s.json" % meta["empty_base"]]
        es = want["segment_%s.json" % meta["empty_segment"]]
        assert eb["checks_scheduled"] + eb["checks_deferred"] == 0 and eb["first_start"] is None, name
        assert es["checks_scheduled"] + es["checks_deferred"] == 0, name
    if meta.get("x1_id"):
        assert any(r["request_id"] == meta["x1_id"] for r in rows), name + ": reused id row not planned"
    rejected = want["data_quality.json"]["rejected"]
    for line, rid, why in meta["two_fault"]:
        assert {"request_id": rid, "line": line, "reason": why} in rejected, "%s: two-fault row %d" % (name, line)


def _pick(obj: Any, keys: list[str]) -> dict[str, Any]:
    return {k: obj.get(k, _MISSING) if isinstance(obj, dict) else _MISSING for k in keys}


def _first_diff(got: Any, want: Any, path: str) -> str | None:
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return path
        for k in want:
            d = _first_diff(got.get(k, _MISSING), want[k], path + "." + k)
            if d:
                return d
        return None
    if isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            return path + " (list length)"
        for i, (g, w) in enumerate(zip(got, want)):
            d = _first_diff(g, w, "%s[%d]" % (path, i))
            if d:
                return d
        return None
    if type(got) is not type(want) or got != want:
        return "%s: got %r, want %r" % (path, got, want)
    return None


def _same(got: Any, want: Any, label: str) -> None:
    diff = _first_diff(got, want, label)
    assert diff is None, "first difference at " + str(diff)


def _rows(doc: Any, keys: list[str]) -> list[dict[str, Any]]:
    checks = doc.get("checks", []) if isinstance(doc, dict) else []
    return [_pick(r, keys) for r in checks]


def _live(case: dict[str, Any]) -> tuple[list[str], list[str]]:
    meta = case.get("meta", {})
    bases = [b for b in BASES if b != meta.get("empty_base")]
    segs = [s for s in SEGMENTS if s != meta.get("empty_segment")]
    return bases, segs


def _group_keys(doc: dict[str, Any], settle: bool) -> list[str]:
    keys = [k for k in doc if (k in SETTLE_GROUP) == settle]
    return keys


def _view_plan(case: dict[str, Any], side: str, reports: bool, audit: bool) -> dict[str, Any]:
    doc = case[side]
    bases, segs = _live(case)
    view: dict[str, Any] = {}
    if audit:
        view["policy_audit.json"] = {"season": doc["policy_audit.json"].get("season", _MISSING),
                                     "checks": _rows(doc["policy_audit.json"], PLAN_ROW)}
    if reports:
        want = case["want"]
        for b in bases:
            n = "region_%s.json" % b
            view[n] = _pick(doc[n], _group_keys(want[n], False))
        for s in segs:
            n = "segment_%s.json" % s
            view[n] = _pick(doc[n], _group_keys(want[n], False))
        summ = doc["summary.json"]
        view["summary.json"] = dict(_pick(summ, PLAN_SUMMARY),
                                    bases=[_pick(r, ["base", "checks_scheduled", "checks_deferred", "overtime_shifts"])
                                           for r in summ.get("bases", []) if r.get("base") in bases],
                                    segments=[_pick(r, ["segment", "checks_scheduled", "checks_deferred"])
                                              for r in summ.get("segments", []) if r.get("segment") in segs])
    return view


def _view_settle(case: dict[str, Any], side: str, part: str) -> dict[str, Any]:
    doc = case[side]
    bases, segs = _live(case)
    if part == "checks":
        return {"policy_audit.json": _rows(doc["policy_audit.json"], SETTLE_ROW)}
    if part == "groups":
        view = {}
        for b in bases:
            view["region_%s.json" % b] = _pick(doc["region_%s.json" % b], SETTLE_GROUP)
        for s in segs:
            view["segment_%s.json" % s] = _pick(doc["segment_%s.json" % s], SETTLE_GROUP[1:])
        return view
    summ = doc["summary.json"]
    return {"settlement": summ.get("settlement", _MISSING),
            "bases": [_pick(r, ["base", "allowance_granted", "allowance_used", "settled_overtime_cost"])
                      for r in summ.get("bases", []) if r.get("base") in bases]}


def _view_empty(case: dict[str, Any], side: str) -> dict[str, Any]:
    doc, meta = case[side], case["meta"]
    eb, es = meta["empty_base"], meta["empty_segment"]
    want = case["want"]
    summ = doc["summary.json"]
    return {"region": _pick(doc["region_%s.json" % eb], list(want["region_%s.json" % eb])),
            "segment": _pick(doc["segment_%s.json" % es], list(want["segment_%s.json" % es])),
            "base_row": [r for r in summ.get("bases", []) if r.get("base") == eb],
            "segment_row": [r for r in summ.get("segments", []) if r.get("segment") == es]}


def _compare(name: str, view) -> None:
    case = _case(name)
    _same(view(case, "got"), view(case, "want"), name)


def _check_hidden_rows(name: str) -> None:
    _compare(name, lambda c, s: _view_plan(c, s, False, True))


def _check_hidden_group_totals(name: str) -> None:
    _compare(name, lambda c, s: _view_plan(c, s, True, False))


def _check_hidden_settle(name: str, part: str) -> None:
    _compare(name, lambda c, s: _view_settle(c, s, part))


def _check_hidden_empty(name: str) -> None:
    _compare(name, _view_empty)


def _check_hidden_data_quality(name: str) -> None:
    _compare(name, lambda c, s: {"data_quality.json": c[s]["data_quality.json"]})


def _check_mutant_settlement() -> None:
    _compare("m1", lambda c, s: dict(_view_settle(c, s, "checks"), **_view_settle(c, s, "groups"),
                                     **_view_settle(c, s, "summary")))


def _check_mutant_all() -> None:
    _compare("m2", lambda c, s: dict(_view_plan(c, s, True, True), **_view_settle(c, s, "checks"),
                                     **_view_settle(c, s, "groups"), **_view_settle(c, s, "summary")))


def _delivered() -> dict[str, Any]:
    case = dict(_shipped_case())
    case["got"] = {n: json.loads((OUT / n).read_text(encoding="utf-8")) for n in ARTIFACT_NAMES}
    return case


def _check_program_runs_shipped() -> None:
    case = _shipped_case()
    work = Path(tempfile.mkdtemp(prefix="hangar-run-"))
    got = _run_program(case["data"], work)
    assert sorted(got) == sorted(ARTIFACT_NAMES)
    shutil.rmtree(work, ignore_errors=True)


def _check_shipped_rows() -> None:
    case = _delivered()
    _same(_view_plan(case, "got", False, True), _view_plan(case, "want", False, True), "shipped")


def _check_shipped_data_quality() -> None:
    case = _delivered()
    _same(case["got"]["data_quality.json"], case["want"]["data_quality.json"], "shipped")


def _check_stops_on_missing_input() -> None:
    root = Path(tempfile.mkdtemp(prefix="hangar-missing-"))
    root.chmod(0o755)
    data = _shipped_root(root)
    (data / MISSING_INPUT).unlink()
    _seal(data)
    work = Path(tempfile.mkdtemp(prefix="hangar-run-"))
    out, cwd = _prepare_run(work)
    run = _launch(["python3", str(SCRIPT), str(data), str(out)], cwd)
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(root, ignore_errors=True)
    assert run.returncode != 0, "exit code 0 with %s missing" % MISSING_INPUT
    assert MISSING_INPUT in run.stderr, "standard error does not name %s" % MISSING_INPUT


def _check_shipped_reports() -> None:
    case = _delivered()
    _same(_view_plan(case, "got", True, False), _view_plan(case, "want", True, False), "shipped")


def _check_shipped_settlement() -> None:
    case = _delivered()
    view = lambda s: dict(_view_settle(case, s, "checks"), **_view_settle(case, s, "groups"),
                          **_view_settle(case, s, "summary"))
    _same(view("got"), view("want"), "shipped")


def _check_negative_weight_hardcoded_sample_answers() -> None:
    shipped = _shipped_case()["want"]
    found = []
    for name in list(HIDDEN) + list(FORMS):
        with _CASE_LOCK:
            _build_case(name)
        case = _CASES[name]
        if "error" not in case and not case.get("stray") and case["want"] != shipped and case["got"] == shipped:
            found.append(name)
    assert found, "no successful hidden run replayed the differing shipped answers"


def _check_negative_weight_writes_outside_out_dir() -> None:
    """NEGATIVE: a held-out or changed-data run wrote outside OUT_DIR or changed the data folder."""
    found = []
    for name in list(HIDDEN) + list(FORMS) + ["m1", "m2"]:
        with _CASE_LOCK:
            _build_case(name)
        found += ["%s: %s" % (name, w) for w in _CASES[name].get("stray", [])]
    assert found, "every run wrote only inside OUT_DIR"


def _write_corpus(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, (seed, empty, stype, x1) in HIDDEN.items():
        (root / name).mkdir()
        corpus("hidden", seed, 8, empty, stype, x1, str(root / name))


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


@criterion(description="Running the stated command on a fresh copy of the shipped data folder, from another working folder, writes all nine JSON reports and each parses.")
def program_runs_on_shipped_data(workspace: Path) -> bool:
    return _holds(_check_program_runs_shipped)


@criterion(description="Running the stated command on a copy of the shipped data folder with fleet_register.csv removed ends with a non-zero exit code and a standard error message that names fleet_register.csv.")
def program_stops_on_a_missing_input(workspace: Path) -> bool:
    return _holds(_check_stops_on_missing_input)


@criterion(description="On the shipped data, the delivered policy_audit.json season and plan fields of every request match the expected values.")
def shipped_plan_rows(workspace: Path) -> bool:
    return _holds(_check_shipped_rows)


@criterion(description="On the shipped data, the delivered data_quality.json lists every rejected row with its line and reason, and the counts match.")
def shipped_data_quality(workspace: Path) -> bool:
    return _holds(_check_shipped_data_quality)


@criterion(description="On the shipped data, the delivered region, segment and summary files match the expected counts, totals, dates and plan terms (settlement fields excluded).")
def shipped_group_reports(workspace: Path) -> bool:
    return _holds(_check_shipped_reports)


@criterion(description="On the shipped data, every settlement field of the delivered checks, regions, segments and summary matches the expected values.")
def shipped_settlement(workspace: Path) -> bool:
    return _holds(_check_shipped_settlement)


@criterion(description="On held-out data folder h1, the policy_audit.json season and plan fields of every request match.")
def h1_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h1"))


@criterion(description="On held-out data folder h1, the non-settlement fields of the region, segment and summary reports match.")
def h1_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h1"))


@criterion(description="On held-out data folder h1, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h1_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h1", "checks"))


@criterion(description="On held-out data folder h1, the settlement fields of every base report and segment report with requests match.")
def h1_settlement_by_base_and_segment(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h1", "groups"))


@criterion(description="On held-out data folder h1, the summary settlement object and the allowance fields of the base rows match.")
def h1_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h1", "summary"))


@criterion(description="On held-out data folder h2, the policy_audit.json season and plan fields of every request match.")
def h2_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h2"))


@criterion(description="On held-out data folder h2, the non-settlement fields of the region, segment and summary reports match.")
def h2_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h2"))


@criterion(description="On held-out data folder h2, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h2_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h2", "checks"))


@criterion(description="On held-out data folder h2, the settlement fields of every base report and segment report with requests match.")
def h2_settlement_by_base_and_segment(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h2", "groups"))


@criterion(description="On held-out data folder h2, the summary settlement object and the allowance fields of the base rows match.")
def h2_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h2", "summary"))


@criterion(description="On held-out data folder h3, the policy_audit.json season and plan fields of every request match.")
def h3_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h3"))


@criterion(description="On held-out data folder h3, the non-settlement fields of the region, segment and summary reports match.")
def h3_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h3"))


@criterion(description="On held-out data folder h3, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h3_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h3", "checks"))


@criterion(description="On held-out data folder h3, the settlement fields of every base report and segment report with requests match.")
def h3_settlement_by_base_and_segment(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h3", "groups"))


@criterion(description="On held-out data folder h3, the summary settlement object and the allowance fields of the base rows match.")
def h3_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h3", "summary"))


@criterion(description="On held-out data folder h4, the policy_audit.json season and plan fields of every request match.")
def h4_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h4"))


@criterion(description="On held-out data folder h4, the non-settlement fields of the region, segment and summary reports match.")
def h4_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h4"))


@criterion(description="On held-out data folder h4, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h4_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h4", "checks"))


@criterion(description="On held-out data folder h4, the settlement fields of every base report and segment report with requests match.")
def h4_settlement_by_base_and_segment(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h4", "groups"))


@criterion(description="On held-out data folder h4, the summary settlement object and the allowance fields of the base rows match.")
def h4_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h4", "summary"))


@criterion(description="On held-out data folder h5, the policy_audit.json season and plan fields of every request match.")
def h5_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h5"))


@criterion(description="On held-out data folder h5, the non-settlement fields of the region, segment and summary reports match.")
def h5_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h5"))


@criterion(description="On held-out data folder h5, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h5_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h5", "checks"))


@criterion(description="On held-out data folder h5, the settlement fields of every base report and segment report with requests match.")
def h5_settlement_by_base_and_segment(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h5", "groups"))


@criterion(description="On held-out data folder h5, the summary settlement object and the allowance fields of the base rows match.")
def h5_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h5", "summary"))


@criterion(description="On held-out data folder h6, the policy_audit.json season and plan fields of every request match.")
def h6_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h6"))


@criterion(description="On held-out data folder h6, the non-settlement fields of the region, segment and summary reports match.")
def h6_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h6"))


@criterion(description="On held-out data folder h6, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h6_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h6", "checks"))


@criterion(description="On held-out data folder h6, the settlement fields of every base report and segment report with requests match.")
def h6_settlement_by_base_and_segment(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h6", "groups"))


@criterion(description="On held-out data folder h6, the summary settlement object and the allowance fields of the base rows match.")
def h6_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h6", "summary"))


@criterion(description="On held-out data folder h1, the base and the segment that have no open request still get their report file and summary row with the stated zero and null values.")
def h1_base_and_segment_with_no_requests(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_empty("h1"))


@criterion(description="On held-out data folder h2, the base and the segment that have no open request still get their report file and summary row with the stated zero and null values.")
def h2_base_and_segment_with_no_requests(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_empty("h2"))


@criterion(description="On held-out data folder h1, data_quality.json lists every rejected row with its line and reason (rows with two faults and a row with a bad available_from included), and the counts match.")
def h1_data_quality(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_data_quality("h1"))


@criterion(description="On the shipped data with the allowance grants changed so the fleet allowance runs out, every settlement field matches.")
def changed_allowance_grants(workspace: Path) -> bool:
    return _holds(_check_mutant_settlement)


@criterion(description="On the shipped data with the revised availability table emptied, every plan and settlement field matches.")
def revised_availability_removed(workspace: Path) -> bool:
    return _holds(_check_mutant_all)


@criterion(description="On held-out data folder h7, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h7_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h7", "checks"))


@criterion(description="On held-out data folder h7, the settlement fields of every base report and segment report with requests match.")
def h7_settlement_by_base_and_segment(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h7", "groups"))


@criterion(description="On held-out data folder h7, the summary settlement object and the allowance fields of the base rows match.")
def h7_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h7", "summary"))


@criterion(description="On held-out data folder h8, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h8_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h8", "checks"))


@criterion(description="On held-out data folder h8, the settlement fields of every base report and segment report with requests match.")
def h8_settlement_by_base_and_segment(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h8", "groups"))


@criterion(description="On held-out data folder h8, the summary settlement object and the allowance fields of the base rows match.")
def h8_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h8", "summary"))


@criterion(description="On held-out data folder h9, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h9_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h9", "checks"))


@criterion(description="On held-out data folder h9, the settlement fields of every base report and segment report with requests match.")
def h9_settlement_by_base_and_segment(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h9", "groups"))


@criterion(description="On held-out data folder h9, the summary settlement object and the allowance fields of the base rows match.")
def h9_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h9", "summary"))


@criterion(description="On held-out data folder h10, the policy_audit.json season and plan fields of every request match.")
def h10_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h10"))


@criterion(description="On held-out data folder h10, the non-settlement fields of the region, segment and summary reports match.")
def h10_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h10"))


@criterion(description="On held-out data folder h10, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h10_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h10", "checks"))


@criterion(description="On held-out data folder h10, the summary settlement object and the allowance fields of the base rows match.")
def h10_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h10", "summary"))


@criterion(description="On held-out data folder h11, the policy_audit.json season and plan fields of every request match.")
def h11_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h11"))


@criterion(description="On held-out data folder h11, the non-settlement fields of the region, segment and summary reports match.")
def h11_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h11"))


@criterion(description="On held-out data folder h11, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h11_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h11", "checks"))


@criterion(description="On held-out data folder h11, the summary settlement object and the allowance fields of the base rows match.")
def h11_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h11", "summary"))


@criterion(description="On held-out data folder h12, the policy_audit.json season and plan fields of every request match.")
def h12_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h12"))


@criterion(description="On held-out data folder h12, the non-settlement fields of the region, segment and summary reports match.")
def h12_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h12"))


@criterion(description="On held-out data folder h12, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h12_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h12", "checks"))


@criterion(description="On held-out data folder h12, the summary settlement object and the allowance fields of the base rows match.")
def h12_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h12", "summary"))


@criterion(description="On held-out data folder h13, the policy_audit.json season and plan fields of every request match.")
def h13_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h13"))


@criterion(description="On held-out data folder h13, the non-settlement fields of the region, segment and summary reports match.")
def h13_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h13"))


@criterion(description="On held-out data folder h13, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h13_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h13", "checks"))


@criterion(description="On held-out data folder h13, the summary settlement object and the allowance fields of the base rows match.")
def h13_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h13", "summary"))


@criterion(description="On held-out data folder h14, the policy_audit.json season and plan fields of every request match.")
def h14_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h14"))


@criterion(description="On held-out data folder h14, the non-settlement fields of the region, segment and summary reports match.")
def h14_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h14"))


@criterion(description="On held-out data folder h14, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h14_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h14", "checks"))


@criterion(description="On held-out data folder h14, the summary settlement object and the allowance fields of the base rows match.")
def h14_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h14", "summary"))


@criterion(description="On held-out data folder h15, the policy_audit.json season and plan fields of every request match.")
def h15_plan_rows(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_rows("h15"))


@criterion(description="On held-out data folder h15, the non-settlement fields of the region, segment and summary reports match.")
def h15_plan_group_totals(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_group_totals("h15"))


@criterion(description="On held-out data folder h15, overtime_cost, allowance_shifts, paid_shifts, allowance_credit and settled_overtime_cost of every request match.")
def h15_settlement_per_check(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h15", "checks"))


@criterion(description="On held-out data folder h15, the summary settlement object and the allowance fields of the base rows match.")
def h15_settlement_summary(workspace: Path) -> bool:
    return _holds(lambda: _check_hidden_settle("h15", "summary"))


@criterion(description="Penalty: a successful held-out run with different expected answers writes all nine shipped answer documents instead; crashes and runs with out-of-scope writes are excluded.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_weight_hardcoded_sample_answers)


@criterion(description="Penalty: a run on a held-out or changed data folder leaves files in its working folder or beside OUT_DIR, or changes the data folder.")
def negative_writes_outside_out_dir(workspace: Path) -> bool:
    return _holds(_check_negative_weight_writes_outside_out_dir)



criteria.program_runs_on_shipped_data(weight=1)
criteria.program_stops_on_a_missing_input(weight=1)
criteria.shipped_plan_rows(weight=5)
criteria.shipped_data_quality(weight=1)
criteria.shipped_group_reports(weight=5)
criteria.shipped_settlement(weight=5)
criteria.h1_plan_rows(weight=5)
criteria.h1_plan_group_totals(weight=5)
criteria.h1_settlement_per_check(weight=5)
criteria.h1_settlement_by_base_and_segment(weight=5)
criteria.h1_settlement_summary(weight=5)
criteria.h2_plan_rows(weight=5)
criteria.h2_plan_group_totals(weight=5)
criteria.h2_settlement_per_check(weight=5)
criteria.h2_settlement_by_base_and_segment(weight=5)
criteria.h2_settlement_summary(weight=5)
criteria.h3_plan_rows(weight=5)
criteria.h3_plan_group_totals(weight=5)
criteria.h3_settlement_per_check(weight=5)
criteria.h3_settlement_by_base_and_segment(weight=5)
criteria.h3_settlement_summary(weight=5)
criteria.h4_plan_rows(weight=5)
criteria.h4_plan_group_totals(weight=5)
criteria.h4_settlement_per_check(weight=5)
criteria.h4_settlement_by_base_and_segment(weight=5)
criteria.h4_settlement_summary(weight=5)
criteria.h5_plan_rows(weight=5)
criteria.h5_plan_group_totals(weight=5)
criteria.h5_settlement_per_check(weight=5)
criteria.h5_settlement_by_base_and_segment(weight=5)
criteria.h5_settlement_summary(weight=5)
criteria.h6_plan_rows(weight=5)
criteria.h6_plan_group_totals(weight=5)
criteria.h6_settlement_per_check(weight=5)
criteria.h6_settlement_by_base_and_segment(weight=5)
criteria.h6_settlement_summary(weight=5)
criteria.h1_base_and_segment_with_no_requests(weight=1)
criteria.h2_base_and_segment_with_no_requests(weight=1)
criteria.h1_data_quality(weight=3)
criteria.changed_allowance_grants(weight=3)
criteria.revised_availability_removed(weight=3)
criteria.h7_settlement_per_check(weight=5)
criteria.h7_settlement_by_base_and_segment(weight=5)
criteria.h7_settlement_summary(weight=5)
criteria.h8_settlement_per_check(weight=5)
criteria.h8_settlement_by_base_and_segment(weight=5)
criteria.h8_settlement_summary(weight=5)
criteria.h9_settlement_per_check(weight=5)
criteria.h9_settlement_by_base_and_segment(weight=5)
criteria.h9_settlement_summary(weight=5)
criteria.h10_plan_rows(weight=5)
criteria.h10_plan_group_totals(weight=5)
criteria.h10_settlement_per_check(weight=5)
criteria.h10_settlement_summary(weight=5)
criteria.h11_plan_rows(weight=5)
criteria.h11_plan_group_totals(weight=5)
criteria.h11_settlement_per_check(weight=5)
criteria.h11_settlement_summary(weight=5)
criteria.h12_plan_rows(weight=5)
criteria.h12_plan_group_totals(weight=5)
criteria.h12_settlement_per_check(weight=5)
criteria.h12_settlement_summary(weight=5)
criteria.h13_plan_rows(weight=5)
criteria.h13_plan_group_totals(weight=5)
criteria.h13_settlement_per_check(weight=5)
criteria.h13_settlement_summary(weight=5)
criteria.h14_plan_rows(weight=5)
criteria.h14_plan_group_totals(weight=5)
criteria.h14_settlement_per_check(weight=5)
criteria.h14_settlement_summary(weight=5)
criteria.h15_plan_rows(weight=5)
criteria.h15_plan_group_totals(weight=5)
criteria.h15_settlement_per_check(weight=5)
criteria.h15_settlement_summary(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-3)
criteria.negative_writes_outside_out_dir(weight=-3)
