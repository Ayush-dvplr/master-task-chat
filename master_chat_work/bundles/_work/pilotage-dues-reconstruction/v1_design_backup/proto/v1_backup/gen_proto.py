#!/usr/bin/env python3
"""Prototype generator (Phase 0b) for pilotage-dues-reconstruction.

python3 gen_proto.py --seed S --out DIR [--hidden] [--scale F] [--meta FILE]
Shipped: --seed 482617 (no --hidden). Hidden corpora: --hidden with other seeds.
"""
import argparse
import json
import os
import random
import shutil
from datetime import date, datetime, timedelta
from fractions import Fraction

STATIONS = ["North", "South", "West", "East"]
LISTS = [
    ["1.80", "1.95", "2.10", "2.25", "2.40"],
    ["2.50", "3.00", "3.50", "4.00"],
    ["1.25", "1.40", "1.50"],
    ["35.00", "50.00", "65.00"],
]
COMBOS = [(b, d, n, t) for b in LISTS[0] for d in LISTS[1] for n in LISTS[2] for t in LISTS[3]]
WSTART = datetime(2026, 7, 1)
WMIN = 92 * 1440
FMT = "%Y-%m-%d %H:%M"
DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
Z_PAIRS = [("2.50", "65.00"), ("3.50", "50.00"), ("3.00", "65.00"), ("4.00", "50.00"),
           ("2.50", "50.00"), ("3.50", "35.00"), ("3.00", "50.00"), ("4.00", "35.00")]


def money(c):
    s = "-" if c < 0 else ""
    c = abs(c)
    return f"{s}{c // 100}.{c % 100:02d}"


def line_cents(combo, gt, draft, tugs, night):
    b, d, n, t = (Fraction(x) for x in combo)
    c1 = round(b * gt)
    c2 = round(d * max(0, draft - 60) * 100)
    c3 = round(t * tugs * 100)
    c4 = round((n - 1) * (c1 + c2 + c3)) if night else 0
    return [c1, c2, c3, c4]


def due_cents(combo, gt, draft, tugs, night, billed, onboard):
    ls = line_cents(combo, gt, draft, tugs, night)
    if billed == onboard:
        return sum(ls)
    if billed == 0:
        return 0
    return sum(round(Fraction(c * billed, onboard)) for c in ls)


class Gen:
    def __init__(self, seed, hidden, scale):
        self.rng = random.Random(seed)
        self.rare = random.Random(seed * 7919 + 17)
        self.hidden = hidden
        self.scale = scale
        self.used_ids = set()
        self.vessels = {}
        self.visits = []
        self.meta = {"seed": seed, "hidden": hidden}

    # ---------- ids
    def new_id(self, prefix, width, r=None):
        r = r or self.rng
        while True:
            v = f"{prefix}{r.randrange(10 ** (width - 1), 10 ** width)}"
            if v not in self.used_ids:
                self.used_ids.add(v)
                return v

    # ---------- calendar
    def period_start(self, st, board):
        d = self.notices.get(st)
        if d is not None and board >= datetime(d.year, d.month, d.day):
            return d
        return date(2026, 7, 1)

    def night(self, st, board):
        return board.hour >= 22 or board.hour < 6 or board.date() in self.holidays[st]

    def minutes(self, v):
        onboard = int((v["release"] - v["board"]).total_seconds() // 60)
        gt, seg, exp = self.vessels[v["vessel"]]
        if seg == "commercial":
            return onboard, onboard
        cut = datetime(exp.year, exp.month, exp.day)
        if v["release"] <= cut:
            return onboard, 0
        start = max(v["board"], cut)
        return onboard, int((v["release"] - start).total_seconds() // 60)

    def due(self, v, combo=None):
        st = v["station"]
        combo = combo or self.tariff[(st, self.period_start(st, v["board"]))]
        onboard, billed = self.minutes(v)
        gt = self.vessels[v["vessel"]][0]
        return due_cents(combo, gt, v["draft"], v["tugs"], self.night(st, v["board"]), billed, onboard)

    # ---------- guards for ordinary visits
    def guarded(self, st, board, release, vessel):
        d = self.notices.get(st)
        if d is not None:
            d0 = datetime(d.year, d.month, d.day)
            if d0 - timedelta(days=6) <= board < d0 + timedelta(days=1):
                return True
        gt, seg, exp = self.vessels[vessel]
        if seg == "public":
            e0 = datetime(exp.year, exp.month, exp.day)
            if board < e0 + timedelta(days=1) and release > e0 - timedelta(hours=12):
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
            if kind == "paid" and self.minutes(v)[1] == 0:
                continue
            return v

    # ---------- build
    def build(self):
        r = self.rng
        n_vessels = max(700, int(2100 * self.scale))
        for _ in range(n_vessels):
            vid = self.new_id("IMO9", 6)
            gt = r.randint(500, 95000)
            if r.random() < 0.12:
                exp = date(2026, 5, 1) + timedelta(days=r.randint(0, 244))
                self.vessels[vid] = (gt, "public", exp)
            else:
                self.vessels[vid] = (gt, "commercial", None)
        self.vessel_ids = sorted(self.vessels)
        self.holidays = {s: sorted(date(2026, 7, 1) + timedelta(days=x) for x in r.sample(range(92), 3))
                         for s in STATIONS}
        if self.hidden:
            roles = STATIONS[:]
            r.shuffle(roles)
            X, Y, Z, W = roles
            dx = date(2026, 8, 1) + timedelta(days=r.randint(0, 30))
            dy = date(2026, 8, 1) + timedelta(days=r.randint(0, 30))
            self.notices = {X: dx, Y: dy}
            self.roles = {"X": X, "Y": Y, "Z": Z, "W": W}
        else:
            self.notices = {"North": date(2026, 8, 17)}
            self.roles = {}
        self.tariff = {}
        for s in STATIONS:
            starts = [date(2026, 7, 1)] + ([self.notices[s]] if s in self.notices else [])
            prev = None
            for ps in starts:
                while True:
                    c = r.choice(COMBOS)
                    if prev is None or all(a != b for a, b in zip(c, prev)):
                        break
                self.tariff[(s, ps)] = c
                prev = c
        constraints = {}
        if self.hidden:
            Y, Z = self.roles["Y"], self.roles["Z"]
            self.free = self.rare.choice(["per_tug", "night_factor", "draft_per_dm"])
            zd, zt = self.rare.choice(Z_PAIRS)
            c = self.tariff[(Z, date(2026, 7, 1))]
            self.tariff[(Z, date(2026, 7, 1))] = (c[0], zd, c[2], zt)
            self.meta.update({"roles": self.roles, "free": self.free, "z_pair": [zd, zt]})
            y_before = date(2026, 7, 1)

            def ycon(v, ps):
                if v["kind"] != "paid" or ps != y_before:
                    return True
                if self.free == "per_tug":
                    return v["tugs"] == 0
                if self.free == "draft_per_dm":
                    return v["draft"] <= 60
                return not self.night(Y, v["board"])

            def zcon(v, ps):
                if v["kind"] != "paid":
                    return True
                k = self.rng.randint(0, 3)
                v["tugs"] = k
                v["draft"] = self.rng.randint(40, 60) if k == 0 else 60 + 15 * k
                return True
            constraints = {Y: ycon, Z: zcon}
        per_station = int(3000 * self.scale)
        for s in STATIONS:
            for _ in range(per_station):
                x = r.random()
                kind = "paid" if x < 0.78 else ("disputed" if x < 0.96 else "none")
                v = self.ordinary_visit(s, kind, constraints.get(s))
                if kind == "paid" and self.minutes(v)[1] == 0:
                    v["kind"] = "disputed"
                self.visits.append(v)
        if self.hidden:
            self.plants()
        for v in self.visits:
            v["id"] = self.new_id("V", 6)
        self.invoices()
        if self.hidden:
            self.w_plant()
        self.inject()

    # ---------- hidden plants (rare stream)
    def plant_vessel(self, seg, exp=None):
        q = self.rare
        vid = self.new_id("IMO9", 6, q)
        self.vessels[vid] = (q.randint(2000, 90000), seg, exp)
        return vid

    def add_plant(self, st, board, release, vessel, kind, tag, inv_date=None, billed_mode="correct"):
        q = self.rare
        v = {"station": st, "board": board, "release": release, "vessel": vessel,
             "draft": q.randint(40, 140), "tugs": q.choice([0, 1, 2]), "kind": kind,
             "tag": tag, "inv_date": inv_date, "billed_mode": billed_mode}
        self.visits.append(v)
        return v

    def plants(self):
        q = self.rare
        X, Y = self.roles["X"], self.roles["Y"]
        dx, dy = self.notices[X], self.notices[Y]
        dx0 = datetime(dx.year, dx.month, dx.day)
        commercial = [k for k in self.vessel_ids if self.vessels[k][1] == "commercial"]
        # LV-2 at X
        for i, kind in enumerate(["paid", "paid", "disputed"]):
            b = dx0 + timedelta(minutes=q.randint(0, 30) if i == 0 else q.randint(60, 1200))
            self.add_plant(X, b, b + timedelta(minutes=q.randint(40, 300)), q.choice(commercial), kind, "notice_day")
        for kind in ["paid", "paid", "disputed"]:
            b = dx0 - timedelta(minutes=q.randint(1, 120))
            self.add_plant(X, b, dx0 + timedelta(minutes=q.randint(20, 300)), q.choice(commercial), kind, "eve")
        for kind in ["paid", "paid", "disputed"]:
            b = dx0 - timedelta(days=q.randint(1, 5)) + timedelta(minutes=q.randint(360, 1100))
            inv = dx + timedelta(days=q.randint(0, 3))
            self.add_plant(X, b, b + timedelta(minutes=q.randint(40, 300)), q.choice(commercial), kind, "lag_cross", inv)
        # LV-3 at X: expiry on the notice date, across midnight and wholly on the day
        for kind in ["paid", "paid", "disputed"]:
            b = dx0 - timedelta(minutes=q.randint(10, 180))
            self.add_plant(X, b, dx0 + timedelta(minutes=q.randint(20, 240)), self.plant_vessel("public", dx), kind, "across_midnight")
        for kind in ["paid", "disputed"]:
            b = dx0 + timedelta(minutes=q.randint(60, 1080))
            self.add_plant(X, b, b + timedelta(minutes=q.randint(40, 300)), self.plant_vessel("public", dx), kind, "on_expiry_day")
        # LV-3 at Y after its notice
        e2 = dy + timedelta(days=q.randint(3, max(3, (date(2026, 9, 28) - dy).days)))
        e20 = datetime(e2.year, e2.month, e2.day)
        for kind in ["paid", "paid", "disputed"]:
            b = e20 - timedelta(minutes=q.randint(10, 240))
            self.add_plant(Y, b, e20 + timedelta(minutes=q.randint(20, 240)), self.plant_vessel("public", e2), kind, "across_midnight")
        for kind in ["paid", "disputed"]:
            b = e20 + timedelta(minutes=q.randint(60, 1080))
            self.add_plant(Y, b, b + timedelta(minutes=q.randint(40, 300)), self.plant_vessel("public", e2), kind, "on_expiry_day")
        b = e20 - timedelta(minutes=q.randint(60, 300))
        self.add_plant(Y, b, e20, self.plant_vessel("public", e2), "disputed", "ends_at_midnight", billed_mode="full")
        b = e20 - timedelta(minutes=q.randint(200, 400))
        self.add_plant(Y, b, e20 - timedelta(minutes=q.randint(5, 60)), self.plant_vessel("public", e2), "disputed", "ends_before", billed_mode="full")
        # Y before notice: disputed rows that use the free coefficient
        for _ in range(2):
            while True:
                b = WSTART + timedelta(minutes=q.randrange((datetime(dy.year, dy.month, dy.day) - WSTART).days * 1440 - 7 * 1440))
                v = {"station": Y, "board": b, "release": b + timedelta(minutes=q.randint(40, 400)),
                     "vessel": q.choice(commercial), "draft": q.randint(40, 140), "tugs": q.randint(1, 3)}
                if self.guarded(Y, v["board"], v["release"], v["vessel"]):
                    continue
                if self.free == "night_factor" and not self.night(Y, b):
                    continue
                if self.free == "draft_per_dm" and v["draft"] <= 60:
                    continue
                v.update({"kind": "disputed", "tag": "free_coefficient", "inv_date": None, "billed_mode": "correct"})
                self.visits.append(v)
                break

    def w_plant(self):
        W = self.roles["W"]
        cands = sorted((p for p in self.paid if p["visit"]["station"] == W and p["visit"]["draft"] > 60
                        and "tag" not in p["visit"]), key=lambda p: p["id"])
        for p in self.rare.sample(cands, 3):
            v = p["visit"]
            c = self.tariff[(W, date(2026, 7, 1))]
            p["amount"] = self.due(v, (c[0], "3.25", c[2], c[3]))
            v["tag"] = "w_off_list"

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
            else:
                mode = v.get("billed_mode") or "random"
                onboard, billed_min = self.minutes(v)
                full = self.due(v) if billed_min == onboard else due_cents(
                    self.tariff[(v["station"], self.period_start(v["station"], v["board"]))],
                    self.vessels[v["vessel"]][0], v["draft"], v["tugs"],
                    self.night(v["station"], v["board"]), onboard, onboard)
                x = r.random()
                if mode == "full":
                    billed = full
                elif mode == "correct":
                    billed = due
                elif due == 0:
                    billed = 0 if x < 0.5 else full
                elif x < 0.45:
                    billed = due
                elif x < 0.75:
                    billed = due + r.randint(1, 30000)
                else:
                    billed = max(0, due - r.randint(1, min(due, 30000)))
                self.disputed.append({"id": self.new_id("D", 7), "visit": v, "date": inv_date,
                                      "billed": billed, "station": v["station"]})

    # ---------- plain rejections
    def inject(self):
        r = self.rng
        k = max(1, int(round(6 * self.scale)))
        self.bad = {"paid": {s: [] for s in STATIONS}, "disputed": [], "log": [], "register": []}
        self.extra_paid = []      # accepted-looking lines that are rejected for content
        self.extra_disputed = []
        self.board_bad = set()
        self.release_bad = set()
        self.register_bad_only = set()
        # malformed copies of genuine paid lines
        for s in STATIONS:
            mine = [p for p in self.paid if p["file"] == s]
            for p in r.sample(mine, 3 * k):
                self.bad["paid"][s].append(dict(p, corrupt=r.randint(0, 2)))
        # duplicates: extra visits, two lines per id
        for _ in range(2 * k):
            s = r.choice(STATIONS)
            v = self.ordinary_visit(s, "paid")
            v["id"] = self.new_id("V", 6)
            self.visits.append(v)
            iid = self.new_id("P", 7)
            d = v["board"].date() + timedelta(days=r.randint(0, 5))
            due = self.due(v)
            other = r.choice(STATIONS) if r.random() < 0.5 else s
            self.extra_paid.append({"id": iid, "visit": v, "date": d, "amount": due, "file": s})
            self.extra_paid.append({"id": iid, "visit": v, "date": d, "amount": due + 100, "file": other})
        # unknown visit ids
        for _ in range(k):
            s = r.choice(STATIONS)
            fake = {"id": self.new_id("V", 6)}
            self.extra_paid.append({"id": self.new_id("P", 7), "visit": fake, "date": date(2026, 8, 3) + timedelta(days=r.randint(0, 40)),
                                    "amount": r.randint(5000, 900000), "file": s})
        # victims: malformed BOARD, malformed RELEASE, vessel only malformed in register
        for kind in ("board", "release", "register"):
            for _ in range(k):
                s = r.choice(STATIONS)
                v = self.ordinary_visit(s, "paid")
                v["id"] = self.new_id("V", 6)
                if kind == "register":
                    vid = self.new_id("IMO9", 6)
                    self.vessels[vid] = (r.randint(500, 95000), "commercial", None)
                    v["vessel"] = vid
                    self.register_bad_only.add(vid)
                self.visits.append(v)
                if kind == "board":
                    self.board_bad.add(v["id"])
                elif kind == "release":
                    self.release_bad.add(v["id"])
                self.extra_paid.append({"id": self.new_id("P", 7), "visit": v, "date": v["board"].date(),
                                        "amount": self.due(v), "file": s})
        # station mismatch
        for _ in range(k):
            s = r.choice(STATIONS)
            v = self.ordinary_visit(s, "paid")
            v["id"] = self.new_id("V", 6)
            self.visits.append(v)
            other = r.choice([x for x in STATIONS if x != s])
            self.extra_paid.append({"id": self.new_id("P", 7), "visit": v, "date": v["board"].date(),
                                    "amount": self.due(v), "file": other})
        # disputed rejections
        for p in r.sample(self.disputed, 3 * k):
            self.bad["disputed"].append(dict(p, corrupt=r.randint(0, 2)))
        for _ in range(k):
            s = r.choice(STATIONS)
            v = self.ordinary_visit(s, "disputed")
            v["id"] = self.new_id("V", 6)
            self.visits.append(v)
            iid = self.new_id("D", 7)
            for _ in range(2):
                self.extra_disputed.append({"id": iid, "visit": v, "date": v["board"].date(), "billed": self.due(v), "station": s})
            fake = {"id": self.new_id("V", 6)}
            self.extra_disputed.append({"id": self.new_id("D", 7), "visit": fake, "date": date(2026, 8, 9),
                                        "billed": r.randint(5000, 500000), "station": s})
            v2 = self.ordinary_visit(s, "disputed")
            v2["id"] = self.new_id("V", 6)
            self.visits.append(v2)
            self.extra_disputed.append({"id": self.new_id("D", 7), "visit": v2, "date": v2["board"].date(),
                                        "billed": self.due(v2), "station": r.choice([x for x in STATIONS if x != s])})
        # log and register malformed copies
        for v in r.sample(self.visits, 4 * k):
            if "board" in v:
                self.bad["log"].append((v, r.randint(0, 3)))
        for vid in r.sample(self.vessel_ids, 3 * k):
            self.bad["register"].append((vid, r.randint(0, 2)))

    # ---------- writing
    def write(self, out):
        r = self.rng
        os.makedirs(out, exist_ok=True)
        for f in sorted(os.listdir(DOCS)):
            shutil.copy(os.path.join(DOCS, f), os.path.join(out, f))
        # movements log
        recs = []
        for v in self.visits:
            if "board" not in v:
                continue
            b = f"{v['board'].strftime(FMT)} BOARD {v['station']} {v['id']} {v['vessel']} draft_dm={v['draft']} tugs={v['tugs']}"
            if v["id"] in self.board_bad:
                b = b.replace(f"draft_dm={v['draft']}", f"draft_dm={v['draft']}.5")
            rl = f"{v['release'].strftime(FMT)} RELEASE {v['id']}"
            if v["id"] in self.release_bad:
                rl = rl.replace(v["release"].strftime(FMT), v["release"].strftime("%Y-%m-%d") + " 24:" + v["release"].strftime("%M"))
            recs.append((v["board"], 0, b))
            recs.append((v["release"], 1, rl))
        notes = ["fog bank lifted", "launch refuelled", "boarding ladder inspected", "radar check complete",
                 "pilot roster updated", "swell reported at the fairway buoy"]
        for _ in range(int(500 * self.scale)):
            t = WSTART + timedelta(minutes=r.randrange(WMIN))
            recs.append((t, 2, f"{t.strftime(FMT)} NOTE {r.choice(STATIONS)} {r.choice(notes)}"))
        recs.sort(key=lambda x: (x[0], x[1], x[2]))
        lines = [x[2] for x in recs]
        for v, c in self.bad["log"]:
            good = f"{v['board'].strftime(FMT)} BOARD {v['station']} {v['id']} {v['vessel']} draft_dm={v['draft']} tugs={v['tugs']}"
            bad = [good.replace(" BOARD ", " BOARD  "), good.replace(f"tugs={v['tugs']}", "tugs="),
                   good.replace(v["station"], v["station"][:-1], 1), good.replace(v["board"].strftime("%H:%M"), "25:" + v["board"].strftime("%M"), 1)][c]
            lines.insert(r.randrange(len(lines) + 1), bad)
        self._w(out, "pilot_movements.log", lines)
        # register
        reg = []
        for vid in self.vessel_ids + sorted(k for k in self.vessels if k not in self.vessel_ids):
            gt, seg, exp = self.vessels[vid]
            row = f"{vid}\tMV {vid[-4:]}\t{gt}\t{seg}\t{exp.isoformat() if exp else '-'}"
            if vid in self.register_bad_only:
                row = f"{vid}\tMV {vid[-4:]}\t{gt}t\t{seg}\t-"
            reg.append(row)
        r.shuffle(reg)
        for vid, c in self.bad["register"]:
            gt, seg, exp = self.vessels[vid]
            bad = [f"{vid}\tMV {vid[-4:]}\t{gt}.0\t{seg}\t{exp.isoformat() if exp else '-'}",
                   f"{vid}\tMV {vid[-4:]}\t{gt}\tstate\t-",
                   f"{vid}\tMV {vid[-4:]}\t{gt}\t{seg}"][c]
            reg.insert(r.randrange(len(reg) + 1), bad)
        self._w(out, "vessel_register.tsv", ["vessel_id\tname\tgross_tonnage\tsegment\texemption_expiry"] + reg)
        # holidays, notices
        with open(os.path.join(out, "holidays.json"), "w") as fh:
            json.dump({s: [d.isoformat() for d in self.holidays[s]] for s in STATIONS}, fh, indent=2)
            fh.write("\n")
        nl = ["# Station Tariff Notices", "", "Each row is one tariff notice.", "",
              "| station | notice_date |", "|---|---|"]
        nl += [f"| {s} | {self.notices[s].isoformat()} |" for s in STATIONS if s in self.notices]
        self._w(out, "station_notices.md", nl)
        # paid files
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
        ls = [self.fmt_disp(p) for p in disp]
        for p in self.bad["disputed"]:
            ls.insert(r.randrange(len(ls) + 1), self.fmt_disp(p, p["corrupt"]))
        self._w(out, "disputed_batch.csv", ["invoice_id,visit_id,station,invoice_date,billed"] + ls)

    def fmt_paid(self, s, p, corrupt=None):
        iid, vid, d, a = p["id"], p["visit"]["id"], p["date"].isoformat(), money(p["amount"])
        if corrupt is not None:
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
        iid, vid, st, d, b = p["id"], p["visit"]["id"], p["station"], p["date"].isoformat(), money(p["billed"])
        if corrupt == 0:
            b = b.replace(".", ",")
        elif corrupt == 1:
            st = "Harbour"
        elif corrupt == 2:
            return f"{iid},{vid},{st},{d}"
        return f"{iid},{vid},{st},{d},{b}"

    def _w(self, out, name, lines):
        with open(os.path.join(out, name), "w", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")

    # ---------- self checks
    def check(self):
        fits = {}
        for (s, ps), _ in sorted(self.tariff.items()):
            rows = []
            for p in self.paid:
                v = p["visit"]
                if v["station"] == s and self.period_start(s, v["board"]) == ps:
                    onboard, billed = self.minutes(v)
                    rows.append((self.vessels[v["vessel"]][0], v["draft"], v["tugs"], self.night(s, v["board"]), billed, onboard, p["amount"]))
            n = 0
            for c in COMBOS:
                if all(due_cents(c, *row[:6]) == row[6] for row in rows):
                    n += 1
            fits[f"{s} {ps}"] = n
        self.meta["fits"] = fits
        if not self.hidden:
            assert all(n == 1 for n in fits.values()), fits
        else:
            R = self.roles
            want = {f"{R['X']} 2026-07-01": "1", f"{R['X']} {self.notices[R['X']]}": "1",
                    f"{R['Y']} 2026-07-01": "3+", f"{R['Y']} {self.notices[R['Y']]}": "1",
                    f"{R['Z']} 2026-07-01": "2", f"{R['W']} 2026-07-01": "0"}
            for key, w in want.items():
                n = fits[key]
                ok = n >= 3 if w == "3+" else n == int(w)
                assert ok, (key, w, fits)
            for key in (f"{R['Y']} 2026-07-01", f"{R['Z']} 2026-07-01"):
                s = key.split()[0]
                assert any(p["visit"]["station"] == s and self.period_start(s, p["visit"]["board"]) == date(2026, 7, 1)
                           for p in self.disputed), key
        tags = {}
        for v in self.visits:
            if "tag" in v:
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
    print(json.dumps(g.meta, default=str))


if __name__ == "__main__":
    main()
