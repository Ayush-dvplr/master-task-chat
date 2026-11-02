#!/usr/bin/env python3
"""Prototype generator v2 (Phase 0b, second blind read) for pilotage-dues-reconstruction.

python3 gen_proto.py --seed S --out DIR [--hidden] [--scale F] [--meta FILE]
Shipped: --seed 482617 (no --hidden). Hidden corpora: --hidden with other seeds.
"""
import argparse
import json
import os
import random
import re
import shutil
from datetime import date, datetime, timedelta

STATIONS = ["North", "South", "West", "East"]
COEF = ["base_per_100gt", "draft_per_dm", "night_factor", "per_tug"]
LISTS = [
    ["1.80", "1.95", "2.10", "2.25", "2.40"],
    ["2.50", "3.00", "3.50", "4.00"],
    ["1.25", "1.40", "1.50"],
    ["35.00", "50.00", "65.00"],
]
COMBOS = [(b, d, n, t) for b in LISTS[0] for d in LISTS[1] for n in LISTS[2] for t in LISTS[3]]
D0 = date(2026, 7, 1)
WSTART = datetime(2026, 7, 1)
WMIN = 92 * 1440
FMT = "%Y-%m-%d %H:%M"
DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
Z_PAIRS = [("2.50", "65.00"), ("3.50", "50.00"), ("3.00", "65.00"), ("4.00", "50.00"),
           ("2.50", "50.00"), ("3.50", "35.00"), ("3.00", "50.00"), ("4.00", "35.00")]
NOTES = ["fog bank lifted", "launch refuelled", "boarding ladder inspected", "radar check complete",
         "pilot roster updated", "swell reported at the fairway buoy"]
QUIET = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10"]


def cents(s):
    return int(s.replace(".", ""))


def rhe(num, den):
    q, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and q % 2 == 1):
        return q + 1
    return q


def money(c):
    s = "-" if c < 0 else ""
    c = abs(c)
    return f"{s}{c // 100}.{c % 100:02d}"


def d00(d):
    return datetime(d.year, d.month, d.day)


def line_cents(combo, gt, draft, tugs, assist, night):
    b, d, n, t = (cents(x) for x in combo)
    l1 = rhe(b * gt, 100)
    l2 = d * max(0, draft - 60)
    l3 = t * tugs
    l4 = 4000 * (-(-assist // 30))
    l5 = rhe((n - 100) * (l1 + l2 + l3), 100) if night else 0
    return [l1, l2, l3, l4, l5]


def due_from(combo, f):
    """f = (gt, draft, tugs, assist, night, billed, onboard, minimum or 0)"""
    ls = line_cents(combo, f[0], f[1], f[2], f[3], f[4])
    billed, onboard = f[5], f[6]
    if billed == onboard:
        s = sum(ls)
    elif billed == 0:
        s = 0
    else:
        s = sum(rhe(x * billed, onboard) for x in ls)
    return max(s, f[7])


class Gen:
    def __init__(self, seed, hidden, scale):
        self.rng = random.Random(seed)
        self.rare = random.Random(seed * 7919 + 17)
        self.rolerng = random.Random(f"roles:{seed}")
        self.hidden = hidden
        self.scale = scale
        self.used_ids = set()
        self.vessels = {}      # vid -> list of rows {gt, seg, cert, mfrom}
        self.certs = {}        # cid -> {holder, expiry, allowance, plant}
        self.visits = []
        self.meta = {"seed": seed, "hidden": hidden}
        self.owned = {q: {"ids": [], "lines": []} for q in QUIET}
        self.lever = {"LV-1": [], "LV-2": [], "LV-3": []}
        self.extra_hol = {"all": [], "sunday": None}

    # ---------- ids
    def new_id(self, prefix, width, r=None):
        r = r or self.rng
        while True:
            v = f"{prefix}{r.randrange(10 ** (width - 1), 10 ** width)}"
            if v not in self.used_ids:
                self.used_ids.add(v)
                return v

    # ---------- vessel and calendar helpers
    def row_at(self, vid, inst):
        rows = self.vessels[vid]
        best = rows[0]
        for rw in rows[1:]:
            if rw["mfrom"] <= inst.date() and (best["mfrom"] is None or rw["mfrom"] > best["mfrom"]):
                best = rw
        return best

    def seg(self, vid):
        return self.vessels[vid][0]["seg"]

    def cert(self, vid):
        return self.vessels[vid][0]["cert"]

    def period_start(self, st, inst):
        n = self.notices.get(st)
        if n is not None and inst >= d00(n[0]):
            return n[0]
        return D0

    def holiday(self, st, d):
        days = set(self.holidays[st]) | set(self.extra_hol["all"])
        if self.extra_hol["sunday"] and self.extra_hol["sunday"][0] == st:
            days.add(self.extra_hol["sunday"][1])
        if d in days:
            return True
        prev = d - timedelta(days=1)
        return d.weekday() == 0 and prev in days and prev.weekday() == 6

    def night(self, v):
        if v.get("cancel"):
            return False
        b = v["board"]
        return b.hour >= 22 or b.hour < 6 or self.holiday(v["station"], b.date())

    def onboard(self, v):
        if v.get("cancel"):
            return 0
        return int((v["release"] - v["board"]).total_seconds() // 60)

    def pre_expiry(self, v, cid):
        if v.get("cancel"):
            return 0
        cut = d00(self.certs[cid]["expiry"])
        end = min(v["release"], cut)
        return max(0, int((end - v["board"]).total_seconds() // 60))

    def covered(self, v):
        vid = v["vessel"]
        if self.seg(vid) != "public" or self.cert(vid) == "-":
            return 0
        cid = self.cert(vid)
        if not self.certs[cid]["plant"]:
            return self.pre_expiry(v, cid)
        return self.plant_cover[v["id"]]

    def minutes(self, v):
        ob = self.onboard(v)
        return ob, ob - self.covered(v)

    def feats(self, v):
        ob, bm = self.minutes(v)
        gt = self.row_at(v["vessel"], v["board"])["gt"]
        mn = self.minimum[v["station"]] if self.seg(v["vessel"]) == "commercial" else 0
        return (gt, v["draft"], v["tugs"], v.get("assist", 0), self.night(v), bm, ob, mn)

    def due(self, v, combo=None):
        st = v["station"]
        if v.get("cancel"):
            return self.fee[st]
        combo = combo or self.tariff[(st, self.period_start(st, v["board"]))]
        return due_from(combo, self.feats(v))

    def full_due(self, v):
        f = list(self.feats(v))
        f[5] = f[6]
        if v.get("cancel"):
            return self.fee[v["station"]]
        return due_from(self.tariff[(v["station"], self.period_start(v["station"], v["board"]))], f)

    # ---------- guards for ordinary visits
    def guarded(self, st, board, release, vessel):
        n = self.notices.get(st)
        if n is not None:
            n0 = d00(n[0])
            if n0 - timedelta(days=6) <= board < n0 + timedelta(days=1):
                return True
        if self.seg(vessel) == "public" and self.cert(vessel) != "-":
            e0 = d00(self.certs[self.cert(vessel)]["expiry"])
            if board < e0 + timedelta(days=1) and release > e0 - timedelta(hours=12):
                return True
        bd = board.date()
        if bd in self.blocked_all or (st, bd) in self.blocked_st:
            return True
        return False

    def ordinary_visit(self, st, kind, constraint=None):
        r = self.rng
        while True:
            board = WSTART + timedelta(minutes=r.randrange(WMIN))
            dur = r.randint(40, 600)
            release = board + timedelta(minutes=dur)
            vessel = r.choice(self.vessel_ids)
            draft = r.randint(40, 140)
            tugs = r.choices([0, 1, 2, 3], [35, 35, 20, 10])[0]
            if self.guarded(st, board, release, vessel):
                continue
            v = {"station": st, "board": board, "release": release, "vessel": vessel,
                 "draft": draft, "tugs": tugs, "kind": kind}
            ps = self.period_start(st, board)
            if constraint and not constraint(v, ps):
                continue
            return v

    # ---------- build
    def build(self):
        r = self.rng
        n_vessels = max(700, int(2100 * self.scale))
        for _ in range(n_vessels):
            vid = self.new_id("IMO9", 6)
            if r.random() < 0.12:
                cid = self.new_id("C", 5)
                self.certs[cid] = {"holder": f"Harbour Authority {cid[1:]}",
                                   "expiry": D0 - timedelta(days=61) + timedelta(days=r.randint(0, 244)),
                                   "allowance": None, "plant": False}
                self.vessels[vid] = [{"gt": r.randint(2000, 90000), "seg": "public", "cert": cid, "mfrom": None}]
            else:
                self.vessels[vid] = [{"gt": r.randint(3000, 95000), "seg": "commercial", "cert": "-", "mfrom": None}]
        self.vessel_ids = sorted(self.vessels)

        def nosunday(st):
            out = set()
            while len(out) < 3:
                d = D0 + timedelta(days=r.randrange(92))
                if d.weekday() != 6:
                    out.add(d)
            return sorted(out)
        self.holidays = {s: nosunday(s) for s in STATIONS}
        self.fee = {s: 50 * r.randint(120, 180) for s in STATIONS}
        self.minimum = {s: 100 * r.randint(25, 45) for s in STATIONS}
        self.blocked_all = set()
        self.blocked_st = set()
        if self.hidden:
            roles = STATIONS[:]
            self.rolerng.shuffle(roles)
            X, Y, Z, W = roles
            self.roles = {"X": X, "Y": Y, "Z": Z, "W": W}
            q = self.rare
            s_coef, f2 = q.sample([1, 2, 3], 2)
            others = [i for i in range(4) if i not in (s_coef, f2)]
            ny = {f2} | set(i for i in others if q.random() < 0.6)
            ny.add(f2)
            nx = set(q.sample(range(4), 2))
            nw = set(q.sample([1, 2, 3], q.randint(1, 2)))
            self.notices = {X: (D0 + timedelta(days=31 + q.randint(0, 30)), nx),
                            Y: (D0 + timedelta(days=31 + q.randint(0, 30)), ny),
                            W: (D0 + timedelta(days=31 + q.randint(0, 30)), nw)}
            self.y_s, self.y_f2 = s_coef, f2
            self.meta.update({"roles": self.roles, "y_shared_unexercised_in_p1": COEF[s_coef],
                              "y_named_unexercised_in_p2": COEF[f2],
                              "notices": {k: [v[0].isoformat(), sorted(COEF[i] for i in v[1])] for k, v in self.notices.items()}})
        else:
            self.notices = {"North": (date(2026, 8, 17), {0, 1, 2, 3})}
            self.roles = {}
        self.tariff = {}
        for s in STATIONS:
            c1 = r.choice(COMBOS)
            self.tariff[(s, D0)] = c1
            if s in self.notices:
                nd, names = self.notices[s]
                while True:
                    c2 = tuple(r.choice(LISTS[i]) if i in names else c1[i] for i in range(4))
                    if all(c2[i] != c1[i] for i in names):
                        break
                self.tariff[(s, nd)] = c2
        constraints = {}
        if self.hidden:
            X, Y, Z, W = (self.roles[k] for k in "XYZW")
            q = self.rare
            # Y: shared coefficient s not first listed in its list
            c1 = list(self.tariff[(Y, D0)])
            c1[self.y_s] = q.choice(LISTS[self.y_s][1:])
            self.tariff[(Y, D0)] = tuple(c1)
            c2 = list(self.tariff[(Y, self.notices[Y][0])])
            c2[self.y_s] = c1[self.y_s]
            self.tariff[(Y, self.notices[Y][0])] = tuple(c2)
            # Z: tie pair
            zd, zt = q.choice(Z_PAIRS)
            c = self.tariff[(Z, D0)]
            self.tariff[(Z, D0)] = (c[0], zd, c[2], zt)
            # W: one unnamed coefficient differs between the periods
            wn = self.notices[W][1]
            u = q.choice([i for i in range(4) if i not in wn])
            a = self.tariff[(W, D0)]
            b = list(self.tariff[(W, self.notices[W][0])])
            b[u] = q.choice([x for x in LISTS[u] if x != a[u]])
            self.tariff[(W, self.notices[W][0])] = tuple(b)
            self.meta.update({"z_pair": [zd, zt], "w_unnamed_differs": COEF[u]})
            yp2 = self.notices[Y][0]

            def unex(v, i):
                if i == 1:
                    return v["draft"] <= 60
                if i == 3:
                    return v["tugs"] == 0
                return not self.night(v)

            def ycon(v, ps):
                if v["kind"] != "paid":
                    return True
                return unex(v, self.y_s) if ps == D0 else unex(v, self.y_f2)

            def zcon(v, ps):
                if v["kind"] != "paid":
                    return True
                k = self.rng.randint(0, 3)
                v["tugs"] = k
                v["draft"] = self.rng.randint(40, 60) if k == 0 else 60 + 15 * k
                return True
            constraints = {Y: ycon, Z: zcon}
            self.reserve_days()
        per_station = int(3000 * self.scale)
        for s in STATIONS:
            for _ in range(per_station):
                x = r.random()
                kind = "paid" if x < 0.78 else ("disputed" if x < 0.96 else "none")
                v = self.ordinary_visit(s, kind, constraints.get(s))
                self.visits.append(v)
        if self.hidden:
            self.plants()
        for v in self.visits:
            v["id"] = self.new_id("V", 6)
        if self.hidden:
            self.fix_ties()
        self.allocate_plant_certs()
        for v in self.visits:
            if v["kind"] == "paid" and self.minutes(v)[1] == 0:
                v["kind"] = "disputed"
        self.invoices()
        self.inject()
        self.finalize_allowances()

    # ---------- hidden day reservation
    def reserve_days(self):
        q = self.rare
        X = self.roles["X"]
        nx = self.notices[X][0]
        used = set()
        hol = set()
        for s in STATIONS:
            hol |= set(self.holidays[s])

        def ok(d, span=1):
            for k in range(-1, span + 1):
                dd = d + timedelta(days=k)
                if dd in used or dd in hol or not (D0 + timedelta(days=2) <= dd <= date(2026, 9, 28)):
                    return False
                if nx - timedelta(days=8) <= dd <= nx + timedelta(days=2):
                    return False
            return True

        def pick(span=1, weekday=None):
            while True:
                d = D0 + timedelta(days=q.randrange(92))
                if weekday is not None and d.weekday() != weekday:
                    continue
                if ok(d, span):
                    for k in range(-1, span + 1):
                        used.add(d + timedelta(days=k))
                    return d
        sunday = pick(2, weekday=6)
        self.extra_hol["sunday"] = (X, sunday)
        self.q3_monday = sunday + timedelta(days=1)
        self.blocked_st.add((X, self.q3_monday))
        a = pick(1)
        while a.weekday() in (6, 0):
            used.discard(a)
            a = pick(1)
        self.extra_hol["all"] = [a]
        self.q10_day = a
        self.blocked_all.add(a)
        self.day_lv3a = pick(3)
        self.day_lv3b = pick(1)
        self.day_lv3c = pick(2)
        self.qdays = [pick(1) for _ in range(4)]
        self.meta["days"] = {"q3_sunday": sunday.isoformat(), "q10_all": a.isoformat(),
                             "lv3a": self.day_lv3a.isoformat(), "lv3b": self.day_lv3b.isoformat(),
                             "lv3c": self.day_lv3c.isoformat()}

    # ---------- hidden plants (rare stream)
    def fresh_vessel(self, seg, gt=None, cert="-"):
        q = self.rare
        vid = self.new_id("IMO9", 6, q)
        self.vessels[vid] = [{"gt": gt or q.randint(3000, 90000), "seg": seg, "cert": cert, "mfrom": None}]
        return vid

    def plant_cert(self, expiry, allowance):
        cid = self.new_id("C", 5, self.rare)
        self.certs[cid] = {"holder": f"Harbour Authority {cid[1:]}", "expiry": expiry,
                           "allowance": allowance, "plant": True}
        return cid

    def add(self, st, board, dur, vessel, kind, tag, lever=None, quiet=None, **kw):
        q = self.rare
        v = {"station": st, "board": board, "release": board + timedelta(minutes=dur), "vessel": vessel,
             "draft": kw.pop("draft", q.randint(40, 140)), "tugs": kw.pop("tugs", q.choice([0, 1, 2])),
             "kind": kind, "tag": tag, "lever": lever, "quiet": quiet}
        v.update(kw)
        self.visits.append(v)
        return v

    def day_at(self, d, lo=7 * 60, hi=19 * 60):
        return d00(d) + timedelta(minutes=self.rare.randint(lo, hi))

    def plants(self):
        q = self.rare
        X = self.roles["X"]
        nx = self.notices[X][0]
        nx0 = d00(nx)
        p1, p2 = self.tariff[(X, D0)], self.tariff[(X, nx)]
        commercial = [k for k in self.vessel_ids if self.seg(k) == "commercial"]

        def lv2(board, dur, kind, tag, inv=None):
            while True:
                v = {"station": X, "board": board, "release": board + timedelta(minutes=dur),
                     "vessel": q.choice(commercial), "draft": q.randint(40, 140), "tugs": q.choice([0, 1, 2, 3]),
                     "kind": kind}
                if due_from(p1, self.feats_raw(v)) != due_from(p2, self.feats_raw(v)):
                    break
            v.update({"tag": tag, "lever": "LV-2", "quiet": None, "inv_date": inv})
            self.visits.append(v)
        for i, kind in enumerate(["paid", "paid", "disputed"]):
            b = nx0 + timedelta(minutes=q.randint(0, 30) if i == 0 else q.randint(60, 1200))
            lv2(b, q.randint(40, 300), kind, "notice_day")
        for kind in ["paid", "paid", "disputed"]:
            b = nx0 - timedelta(minutes=q.randint(1, 120))
            lv2(b, q.randint(150, 400), kind, "eve")
        for kind in ["paid", "paid", "disputed"]:
            b = nx0 - timedelta(days=q.randint(1, 5)) + timedelta(minutes=q.randint(360, 1100))
            lv2(b, q.randint(40, 300), kind, "lag_cross", nx + timedelta(days=q.randint(0, 3)))
        # LV-3 scenario A: shared certificate, uninvoiced draw at another station, cap hit mid-visit
        da = self.day_lv3a
        other = q.choice([s for s in STATIONS if s != X])
        m1, m2 = q.randint(100, 300), q.randint(200, 400)
        allow_a = m1 + q.randint(30, m2 - 30)
        ca = self.plant_cert(da + timedelta(days=3), allow_a)
        a1, a2, a3 = (self.fresh_vessel("public", cert=ca) for _ in range(3))
        self.add(other, self.day_at(da, 6 * 60 + 30, 9 * 60), m1, a1, "none", "uninvoiced_draw", "LV-3")
        self.add(X, self.day_at(da, 12 * 60, 15 * 60), m2, a2, "paid", "cap_mid_visit", "LV-3")
        self.add(X, self.day_at(da + timedelta(days=1)), q.randint(60, 300), a3, "disputed", "exhausted", "LV-3")
        self.add(X, self.day_at(da + timedelta(days=2)), q.randint(60, 300), a1, "disputed", "exhausted", "LV-3")
        # LV-3 scenario B: tie on the instant, lower visit id draws first
        db = self.day_lv3b
        mb = q.randint(60, 200)
        rem = q.randint(20, 80)
        cb = self.plant_cert(db + timedelta(days=2), mb + rem)
        b1, b2 = self.fresh_vessel("public", cert=cb), self.fresh_vessel("public", cert=cb)
        self.add(other, self.day_at(db, 6 * 60 + 30, 8 * 60), mb, b1, "none", "uninvoiced_draw", "LV-3")
        t = self.day_at(db, 12 * 60, 16 * 60)
        self.tie = [self.add(X, t, rem + q.randint(30, 200), b1, "disputed", "tie", "LV-3"),
                    self.add(X, t, rem + q.randint(30, 200), b2, "disputed", "tie", "LV-3")]
        # LV-3 scenario C: expiry at midnight splits visits
        dc = self.day_lv3c
        cc = self.plant_cert(dc + timedelta(days=1), 100000)
        c1, c2 = self.fresh_vessel("public", cert=cc), self.fresh_vessel("public", cert=cc)
        e0 = d00(dc + timedelta(days=1))
        for kind, vv in (("paid", c1), ("disputed", c2), ("disputed", c1)):
            b = e0 - timedelta(minutes=q.randint(10, 170))
            self.add(X, b, int((e0 - b).total_seconds() // 60) + q.randint(20, 240), vv, kind, "across_midnight", "LV-3")
        self.add(X, self.day_at(dc + timedelta(days=1)), q.randint(60, 300), c2, "disputed", "on_expiry_day", "LV-3")
        # quiet plants
        qd = self.qdays

        def qv(rule, d, **kw):
            vessel = kw.pop("vessel", None) or self.fresh_vessel("commercial")
            return self.add(X, self.day_at(d), kw.pop("dur", q.randint(60, 300)), vessel, "disputed", rule,
                            None, rule, **kw)
        for _ in range(3):
            qv("Q1", qd[0], assist=q.randint(10, 95))
        for _ in range(3):
            dm = q.randint(61, 139)
            metres = dm * 10 - 10 + q.randint(1, 4)
            qv("Q2", qd[0], draft=dm, draft_m=f"{metres // 100}.{metres % 100:02d}")
        for _ in range(3):
            qv("Q3", self.q3_monday)
        for _ in range(3):
            qv("Q4", qd[1], cancel=True, tugs=0, draft=50, dur=0)
        bmax = max(cents(self.tariff[(X, D0)][0]), cents(self.tariff[(X, nx)][0]))
        gmax = (self.minimum[X] - 100) * 100 // bmax
        for _ in range(3):
            qv("Q5", qd[1], vessel=self.fresh_vessel("commercial", gt=q.randint(500, max(500, gmax))),
               tugs=0, draft=q.randint(40, 60))
        q6 = self.fresh_vessel("commercial")
        g1 = self.vessels[q6][0]["gt"]
        mday = qd[2] + timedelta(days=1)
        self.vessels[q6].append({"gt": g1 + q.choice([-1, 1]) * q.randint(5, 40) * 100, "seg": "commercial",
                                 "cert": "-", "mfrom": mday})
        qv("Q6", qd[2], vessel=q6)
        qv("Q6", mday, vessel=q6)
        qv("Q6", mday + timedelta(days=1), vessel=q6)
        q7 = self.fresh_vessel("public")
        for d in (qd[2], qd[3], qd[3]):
            qv("Q7", d, vessel=q7)
        self.q8 = [qv("Q8", qd[3]) for _ in range(2)]
        for _ in range(3):
            qv("Q9", qd[3])
        for _ in range(3):
            qv("Q10", self.q10_day)

    def feats_raw(self, v):
        mn = self.minimum[v["station"]] if self.seg(v["vessel"]) == "commercial" else 0
        ob = self.onboard(v)
        return (self.row_at(v["vessel"], v["board"])["gt"], v["draft"], v["tugs"], v.get("assist", 0),
                self.night(v), ob, ob, mn)

    def fix_ties(self):
        a, b = self.tie
        lo, hi = sorted([a["id"], b["id"]])
        a["id"], b["id"] = lo, hi
        b["log_first"] = True

    def allocate_plant_certs(self):
        self.plant_cover = {}
        for cid, c in self.certs.items():
            if not c["plant"]:
                continue
            vs = [v for v in self.visits if self.seg(v["vessel"]) == "public" and self.cert(v["vessel"]) == cid]
            vs.sort(key=lambda v: (v["board"], v["id"]))
            left = c["allowance"]
            for v in vs:
                cov = min(self.pre_expiry(v, cid), left)
                left -= cov
                self.plant_cover[v["id"]] = cov

    def finalize_allowances(self):
        need = {}
        for v in self.visits:
            if "board" not in v or self.seg(v["vessel"]) != "public" or self.cert(v["vessel"]) == "-":
                continue
            cid = self.cert(v["vessel"])
            if not self.certs[cid]["plant"]:
                need[cid] = need.get(cid, 0) + self.pre_expiry(v, cid)
        for cid in sorted(self.certs):
            c = self.certs[cid]
            if not c["plant"]:
                c["allowance"] = need.get(cid, 0) + self.rng.randint(30, 900)

    # ---------- invoices
    def invoices(self):
        r = self.rng
        self.paid = []
        self.disputed = []
        for v in self.visits:
            if v["kind"] == "none":
                continue
            lag = r.randint(0, 5)
            inv_date = v.get("inv_date") or (v["board"].date() + timedelta(days=lag))
            due = self.due(v)
            if v["kind"] == "paid":
                self.paid.append({"id": self.new_id("P", 7), "visit": v, "date": inv_date, "amount": due,
                                  "file": v["station"]})
                continue
            billed = self.billed_for(v, due)
            d = {"id": self.new_id("D", 7), "visit": v, "date": inv_date, "billed": billed,
                 "station": v["station"], "supersedes": "", "cform": v.get("quiet") == "Q9"}
            self.disputed.append(d)
            if v.get("quiet"):
                self.owned[v["quiet"]]["ids"].append(d["id"])
            if v.get("lever"):
                self.lever[v["lever"]].append(d["id"])
        if self.hidden:
            for v in self.q8:
                orig = [d for d in self.disputed if d["visit"] is v][0]
                sup = {"id": self.new_id("D", 7), "visit": v, "date": orig["date"],
                       "billed": self.billed_for(v, self.due(v)), "station": v["station"],
                       "supersedes": orig["id"], "cform": False}
                self.disputed.append(sup)
                self.owned["Q8"]["ids"].append(sup["id"])

    def billed_for(self, v, due):
        r = self.rng
        x = r.random()
        full = self.full_due(v)
        if due == 0:
            return 0 if x < 0.5 else full
        if x < 0.45:
            return due
        if x < 0.75:
            return due + r.randint(1, 30000)
        return max(0, due - r.randint(1, min(due, 30000)))

    # ---------- plain rejections
    def inject(self):
        r = self.rng
        k = max(1, int(round(6 * self.scale)))
        self.bad = {"paid": {s: [] for s in STATIONS}, "disputed": [], "log": [], "register": []}
        self.extra_paid = []
        self.extra_disputed = []
        self.board_bad = set()
        self.release_bad = set()
        self.register_bad_only = set()
        plain_paid = [p for p in self.paid if not p["visit"].get("tag")]
        plain_disp = [p for p in self.disputed if not p["visit"].get("tag")]
        for s in STATIONS:
            mine = [p for p in plain_paid if p["file"] == s]
            for p in r.sample(mine, 3 * k):
                self.bad["paid"][s].append(dict(p, corrupt=r.randint(0, 2)))

        def extra(s, kind):
            v = self.ordinary_visit(s, kind)
            while kind == "paid" and self.minutes(dict(v, id="-"))[1] != self.onboard(v):
                v = self.ordinary_visit(s, kind)
            v["id"] = self.new_id("V", 6)
            self.visits.append(v)
            return v
        for _ in range(2 * k):
            s = r.choice(STATIONS)
            v = extra(s, "paid")
            iid = self.new_id("P", 7)
            d = v["board"].date() + timedelta(days=r.randint(0, 5))
            due = self.due(v)
            other = r.choice(STATIONS) if r.random() < 0.5 else s
            self.extra_paid.append({"id": iid, "visit": v, "date": d, "amount": due, "file": s})
            self.extra_paid.append({"id": iid, "visit": v, "date": d, "amount": due + 100, "file": other})
        for _ in range(k):
            fake = {"id": self.new_id("V", 6)}
            self.extra_paid.append({"id": self.new_id("P", 7), "visit": fake,
                                    "date": date(2026, 8, 3) + timedelta(days=r.randint(0, 40)),
                                    "amount": r.randint(5000, 900000), "file": r.choice(STATIONS)})
        for kind in ("board", "release", "register"):
            for _ in range(k):
                s = r.choice(STATIONS)
                if kind == "register":
                    vid = self.new_id("IMO9", 6)
                    self.vessels[vid] = [{"gt": r.randint(3000, 95000), "seg": "commercial", "cert": "-", "mfrom": None}]
                    self.register_bad_only.add(vid)
                v = extra(s, "paid")
                if kind == "register":
                    v["vessel"] = vid
                elif kind == "board":
                    self.board_bad.add(v["id"])
                else:
                    self.release_bad.add(v["id"])
                self.extra_paid.append({"id": self.new_id("P", 7), "visit": v, "date": v["board"].date(),
                                        "amount": self.due(v), "file": s})
        for _ in range(k):
            s = r.choice(STATIONS)
            v = extra(s, "paid")
            self.extra_paid.append({"id": self.new_id("P", 7), "visit": v, "date": v["board"].date(),
                                    "amount": self.due(v), "file": r.choice([x for x in STATIONS if x != s])})
        # early_invoice: paid and disputed dated before the visit's date
        for _ in range(k):
            s = r.choice(STATIONS)
            v = extra(s, "paid")
            self.extra_paid.append({"id": self.new_id("P", 7), "visit": v,
                                    "date": v["board"].date() - timedelta(days=r.randint(1, 4)),
                                    "amount": self.due(v), "file": s})
            v2 = extra(s, "disputed")
            self.extra_disputed.append({"id": self.new_id("D", 7), "visit": v2,
                                        "date": v2["board"].date() - timedelta(days=r.randint(1, 4)),
                                        "billed": self.due(v2), "station": s, "supersedes": "", "cform": False})
        # already_paid: disputed invoice on a visit with an accepted paid invoice
        for p in r.sample(plain_paid, 2 * k):
            if p in sum(self.bad["paid"].values(), []):
                continue
            self.extra_disputed.append({"id": self.new_id("D", 7), "visit": p["visit"], "date": p["date"],
                                        "billed": p["amount"] + r.randint(0, 5000), "station": p["visit"]["station"],
                                        "supersedes": "", "cform": False})
        for p in r.sample(plain_disp, 3 * k):
            self.bad["disputed"].append(dict(p, corrupt=r.randint(0, 2)))
        for _ in range(k):
            s = r.choice(STATIONS)
            v = extra(s, "disputed")
            iid = self.new_id("D", 7)
            for _ in range(2):
                self.extra_disputed.append({"id": iid, "visit": v, "date": v["board"].date(), "billed": self.due(v),
                                            "station": s, "supersedes": "", "cform": False})
            fake = {"id": self.new_id("V", 6)}
            self.extra_disputed.append({"id": self.new_id("D", 7), "visit": fake, "date": date(2026, 8, 9),
                                        "billed": r.randint(5000, 500000), "station": s, "supersedes": "", "cform": False})
            v2 = extra(s, "disputed")
            self.extra_disputed.append({"id": self.new_id("D", 7), "visit": v2, "date": v2["board"].date(),
                                        "billed": self.due(v2), "station": r.choice([x for x in STATIONS if x != s]),
                                        "supersedes": "", "cform": False})
        plain_vis = [v for v in self.visits if "board" in v and not v.get("tag") and not v.get("cancel")]
        for v in r.sample(plain_vis, 4 * k):
            self.bad["log"].append((v, r.randint(0, 3)))
        plain_ves = [x for x in self.vessel_ids]
        for vid in r.sample(plain_ves, 3 * k):
            self.bad["register"].append((vid, r.randint(0, 2)))

    # ---------- writing
    def board_line(self, v):
        dpart = f"draft_m={v['draft_m']}" if v.get("draft_m") else f"draft_dm={v['draft']}"
        s = f"{v['board'].strftime(FMT)} BOARD {v['station']} {v['id']} {v['vessel']} {dpart} tugs={v['tugs']}"
        if v.get("assist"):
            s += f" assist={v['assist']}"
        return s

    def write(self, out):
        r = self.rng
        os.makedirs(out, exist_ok=True)
        for f in sorted(os.listdir(DOCS)):
            shutil.copy(os.path.join(DOCS, f), os.path.join(out, f))
        recs = []
        for v in self.visits:
            if "board" not in v:
                continue
            if v.get("cancel"):
                recs.append((v["board"], 0, 0, f"{v['board'].strftime(FMT)} CANCEL {v['station']} {v['id']} {v['vessel']}", v))
                continue
            b = self.board_line(v)
            if v["id"] in self.board_bad:
                b = b.replace(f"draft_dm={v['draft']}", f"draft_dm={v['draft']}.5")
            rl = f"{v['release'].strftime(FMT)} RELEASE {v['id']}"
            if v["id"] in self.release_bad:
                rl = rl.replace(v["release"].strftime(FMT), v["release"].strftime("%Y-%m-%d") + " 24:" + v["release"].strftime("%M"))
            recs.append((v["board"], 0, -1 if v.get("log_first") else 0, b, v))
            recs.append((v["release"], 1, 0, rl, None))
        for _ in range(int(500 * self.scale)):
            t = WSTART + timedelta(minutes=r.randrange(WMIN))
            recs.append((t, 2, 0, f"{t.strftime(FMT)} NOTE {r.choice(STATIONS)} {r.choice(NOTES)}", None))
        recs.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
        lines = [(x[3], x[4]) for x in recs]
        for v, c in self.bad["log"]:
            good = self.board_line(v)
            bad = [good.replace(" BOARD ", " BOARD  "), good.replace(f"tugs={v['tugs']}", "tugs="),
                   good.replace(v["station"], v["station"][:-1], 1),
                   good.replace(v["board"].strftime("%H:%M"), "25:" + v["board"].strftime("%M"), 1)][c]
            lines.insert(r.randrange(len(lines) + 1), (bad, None))
        for i, (_, v) in enumerate(lines):
            if v is not None and v.get("quiet") in ("Q1", "Q2", "Q4"):
                self.owned[v["quiet"]]["lines"].append(["pilot_movements.log", i + 1])
        self._w(out, "pilot_movements.log", [x[0] for x in lines])
        # register
        reg = []
        qreg = {}
        for vid in sorted(self.vessels):
            for rw in self.vessels[vid]:
                row = f"{vid}\tMV {vid[-4:]}\t{rw['gt']}\t{rw['seg']}\t{rw['cert']}\t{rw['mfrom'].isoformat() if rw['mfrom'] else '-'}"
                if vid in self.register_bad_only:
                    row = f"{vid}\tMV {vid[-4:]}\t{rw['gt']}t\t{rw['seg']}\t-\t-"
                reg.append((row, vid))
        r.shuffle(reg)
        for vid, c in self.bad["register"]:
            rw = self.vessels[vid][0]
            bad = [f"{vid}\tMV {vid[-4:]}\t{rw['gt']}.0\t{rw['seg']}\t{rw['cert']}\t-",
                   f"{vid}\tMV {vid[-4:]}\t{rw['gt']}\tstate\t-\t-",
                   f"{vid}\tMV {vid[-4:]}\t{rw['gt']}\t{rw['seg']}\t{rw['cert']}"][c]
            reg.insert(r.randrange(len(reg) + 1), (bad, None))
        qv = {}
        for v in self.visits:
            if v.get("quiet") in ("Q6", "Q7"):
                qv[v["vessel"]] = v["quiet"]
        for i, (_, vid) in enumerate(reg):
            if vid in qv:
                self.owned[qv[vid]]["lines"].append(["vessel_register.tsv", i + 2])
        self._w(out, "vessel_register.tsv",
                ["vessel_id\tname\tgross_tonnage\tsegment\tcertificate\tmeasured_from"] + [x[0] for x in reg])
        # certificates, holidays, notices
        with open(os.path.join(out, "certificates.json"), "w") as fh:
            json.dump({cid: {"holder": c["holder"], "expiry": c["expiry"].isoformat(),
                             "allowance_minutes": c["allowance"]} for cid, c in sorted(self.certs.items())}, fh, indent=2)
            fh.write("\n")
        hol = {s: [d.isoformat() for d in self.holidays[s]] for s in STATIONS}
        if self.extra_hol["sunday"]:
            st, d = self.extra_hol["sunday"]
            hol[st] = sorted(hol[st] + [d.isoformat()])
        hol["all"] = [d.isoformat() for d in self.extra_hol["all"]]
        with open(os.path.join(out, "holidays.json"), "w") as fh:
            json.dump(hol, fh, indent=2)
            fh.write("\n")
        nl = ["# Station Notices", "", "## Tariff notices", "",
              "| station | notice_date | coefficients |", "|---|---|---|"]
        for s in STATIONS:
            if s in self.notices:
                nd, names = self.notices[s]
                nl.append(f"| {s} | {nd.isoformat()} | {', '.join(COEF[i] for i in sorted(names))} |")
        nl += ["", "## Station fees", "", "| station | call_out_fee | minimum_due |", "|---|---|---|"]
        nl += [f"| {s} | {money(self.fee[s])} | {money(self.minimum[s])} |" for s in STATIONS]
        assert all(self.fee[s] > self.minimum[s] for s in STATIONS)
        nl += ["", "A cancelled booking's due is the call_out_fee of its station, with no other line; the",
               "minimum_due does not apply to it. The due of a commercial visit is never below the minimum_due",
               "of its station; a lower due is raised to the minimum_due. Example on invented values: with a",
               "call_out_fee of 18.00 and a minimum_due of 12.00, a cancelled booking has the due 18.00, and a",
               "commercial visit whose five lines add up to 9.31 has the due 12.00."]
        self._w(out, "station_notices.md", nl)
        allpaid = self.paid + self.extra_paid
        for s in STATIONS:
            mine = [p for p in allpaid if p["file"] == s]
            r.shuffle(mine)
            ls = [self.fmt_paid(s, p) for p in mine]
            for p in self.bad["paid"][s]:
                ls.insert(r.randrange(len(ls) + 1), self.fmt_paid(s, p, p["corrupt"]))
            if s == "North":
                self._w(out, "paid_north.csv", ["invoice_id,visit_id,invoice_date,amount"] + ls)
            elif s == "South":
                self._w(out, "paid_south.jsonl", ls)
            elif s == "West":
                self._w(out, "paid_west.txt", ls)
            else:
                self._w(out, "paid_east.xml", ['<paid_invoices station="East">'] + ls + ["</paid_invoices>"])
        disp = self.disputed + self.extra_disputed
        r.shuffle(disp)
        ls = [(self.fmt_disp(p), p) for p in disp]
        for p in self.bad["disputed"]:
            ls.insert(r.randrange(len(ls) + 1), (self.fmt_disp(p, p["corrupt"]), None))
        own = {}
        for qn in QUIET:
            for iid in self.owned[qn]["ids"]:
                own[iid] = qn
        sup_targets = {p["supersedes"]: "Q8" for p in disp if p["supersedes"]}
        for i, (_, p) in enumerate(ls):
            if p is None:
                continue
            qn = own.get(p["id"]) or sup_targets.get(p["id"])
            if qn:
                self.owned[qn]["lines"].append(["disputed_batch.csv", i + 2])
        for iid in sup_targets:
            self.owned["Q8"]["ids"].append(iid)
        for iid in sup_targets:
            assert sum(1 for x in ls if x[0].startswith(iid + ",")) == 1, iid
        self._w(out, "disputed_batch.csv", ["invoice_id,visit_id,station,invoice_date,billed,supersedes"] + [x[0] for x in ls])
        heads, rels = {}, {}
        pat = re.compile(r"^\d{4}-\d{2}-\d{2} (?:[01]\d|2[0-3]):[0-5]\d (?:(BOARD|CANCEL) (?:North|South|West|East)"
                         r" (\S+) .*|(RELEASE) (\S+))$")
        with open(os.path.join(out, "pilot_movements.log")) as fh:
            for ln in fh:
                m = pat.match(ln.rstrip("\n"))
                if m and "  " not in ln and not re.search(r"tugs=(\s|$)", ln):
                    bucket, key = (rels, m.group(4)) if m.group(3) else (heads, m.group(2))
                    bucket[key] = bucket.get(key, 0) + 1
        assert all(n == 1 for n in heads.values()) and all(n == 1 for n in rels.values())
        self.meta["owned"] = self.owned
        self.meta["lever_ids"] = self.lever
        self.meta["expect_due"] = {d["id"]: self.due(d["visit"]) for d in self.disputed}

    def fmt_paid(self, s, p, corrupt=None):
        iid, vid, d, a = p["id"], p["visit"]["id"], p["date"].isoformat(), money(p["amount"])
        if corrupt == 0:
            a = a[:-1]
        elif corrupt == 1:
            d = d[:8] + "32"
        if s == "North":
            ln = f"{iid},{vid},{d},{a}"
            return ln + ",x" if corrupt == 2 else ln
        if s == "South":
            obj = {"invoice_id": iid, "visit_id": vid, "invoice_date": d, "amount": a}
            if corrupt == 2:
                del obj["visit_id"]
            return json.dumps(obj)
        if s == "West":
            ln = f"{iid:<10}{vid:<8}{d:<10}{a:>12}"
            return ln + " " if corrupt == 2 else ln
        ln = f'<invoice id="{iid}" visit="{vid}" date="{d}" amount="{a}"/>'
        return ln.replace(f' amount="{a}"', "") if corrupt == 2 else ln

    def fmt_disp(self, p, corrupt=None):
        iid, vid, st, d = p["id"], p["visit"]["id"], p["station"], p["date"].isoformat()
        b = f"{p['billed']}c" if p.get("cform") else money(p["billed"])
        if corrupt == 0:
            b = b.replace(".", ",")
        elif corrupt == 1:
            st = "Harbour"
        elif corrupt == 2:
            return f"{iid},{vid},{st},{d},{b}"
        return f"{iid},{vid},{st},{d},{b},{p['supersedes']}"

    def _w(self, out, name, lines):
        with open(os.path.join(out, name), "w", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")

    # ---------- self checks
    def alone_fits(self, s, ps):
        rows = [(self.feats(p["visit"]), p["amount"]) for p in self.paid
                if p["visit"]["station"] == s and self.period_start(s, p["visit"]["board"]) == ps]
        return [c for c in COMBOS if all(due_from(c, f) == a for f, a in rows)]

    def check(self):
        res = {}
        proj = {}
        for s in STATIONS:
            f1 = self.alone_fits(s, D0)
            res[f"{s} {D0}"] = len(f1)
            if s not in self.notices:
                proj[(s, D0)] = set(f1)
                continue
            nd, names = self.notices[s]
            f2 = self.alone_fits(s, nd)
            res[f"{s} {nd}"] = len(f2)
            pairs = [(a, b) for a in f1 for b in f2 if all(a[i] == b[i] for i in range(4) if i not in names)]
            proj[(s, D0)] = {a for a, _ in pairs}
            proj[(s, nd)] = {b for _, b in pairs}
        joint = {f"{k[0]} {k[1]}": len(v) for k, v in proj.items()}
        self.meta["fits_alone"] = res
        self.meta["fits_joint"] = joint
        for (s, ps), c in self.tariff.items():
            if len(proj[(s, ps)]) == 1:
                assert proj[(s, ps)] == {c}, (s, ps)
        if not self.hidden:
            assert all(n == 1 for n in res.values()) and all(n == 1 for n in joint.values()), (res, joint)
        else:
            R = self.roles
            nX, nY, nW = (self.notices[R[k]][0] for k in "XYW")
            want_alone = {(R["X"], D0): "1", (R["X"], nX): "1", (R["Y"], D0): "3+", (R["Z"], D0): "2",
                          (R["W"], D0): "1", (R["W"], nW): "1"}
            want_joint = {(R["X"], D0): "1", (R["X"], nX): "1", (R["Y"], D0): "1", (R["Y"], nY): "3+",
                          (R["Z"], D0): "2", (R["W"], D0): "0", (R["W"], nW): "0"}
            for want, got in ((want_alone, res), (want_joint, joint)):
                for (s, ps), w in want.items():
                    n = got[f"{s} {ps}"]
                    assert (n >= 3) if w == "3+" else n == int(w), (s, ps, w, res, joint)
            # disputed rows per multi-fit / no-fit period; Y1 rows that first fit alone gets wrong
            first_y1 = self.alone_fits(R["Y"], D0)[0]
            ny1 = sum(1 for d in self.disputed if d["visit"]["station"] == R["Y"] and not d["visit"].get("tag")
                      and self.period_start(R["Y"], d["visit"]["board"]) == D0
                      and self.due(d["visit"], first_y1) != self.due(d["visit"]))
            assert ny1 >= 2, ny1
            for s, ps in ((R["Y"], nY), (R["Z"], D0), (R["W"], D0), (R["W"], nW)):
                n = sum(1 for d in self.disputed if d["visit"]["station"] == s
                        and self.period_start(s, d["visit"]["board"]) == ps)
                assert n >= 2, (s, ps, n)
            for qn in QUIET:
                assert len(self.owned[qn]["ids"]) >= 2, qn
            for v in self.visits:
                if v.get("quiet") == "Q5":
                    assert self.due(v) == self.minimum[v["station"]], v
            self.meta["y1_first_fit_wrong_rows"] = ny1
        tags = {}
        for v in self.visits:
            if v.get("tag"):
                tags[v["tag"]] = tags.get(v["tag"], 0) + 1
        self.meta["plants"] = tags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hidden", action="store_true")
    ap.add_argument("--scale", type=float, default=None)
    ap.add_argument("--meta")
    a = ap.parse_args()
    scale = a.scale if a.scale is not None else (0.34 if a.hidden else 1.0)
    g = Gen(a.seed, a.hidden, scale)
    g.build()
    g.check()
    g.write(a.out)
    if a.meta:
        with open(a.meta, "w") as fh:
            json.dump(g.meta, fh, indent=2, default=str)
    print(json.dumps({k: g.meta[k] for k in g.meta if k not in ("owned", "lever_ids")}, default=str))


if __name__ == "__main__":
    main()
