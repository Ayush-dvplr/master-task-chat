"""L-CONV prototype generator v3 (proto only; never shipped).

Usage: gen3.py SEED DATA_DIR TRUTH.json [--shipped] [--paid N]
Renders the 14-file layout of the design-blind world into DATA_DIR and writes the
truth (conventions, tariffs, ambiguity flags) to TRUTH.json (outside DATA_DIR).
"""
import json
import os
import random
import sys
import time
from datetime import date, datetime, timedelta

from core3 import (B_LIST, D0, D_LIST, HEADLINE, KA_ALL, KD_ALL, N_LIST, NDAYS, STATIONS,
                   T_LIST, TARIFFS, fit, holiday, in_window, true_due)

CALENDARS = ["national", "north", "south", "west", "east", "harbour", "fishery"]
DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
FILE_OF = {"North": "paid_north.csv", "South": "paid_south.jsonl",
           "West": "paid_west.txt", "East": "paid_east.xml"}
END = D0 + timedelta(days=NDAYS)


def money(c):
    s = "-" if c < 0 else ""
    c = abs(c)
    return f"{s}{c // 100}.{c % 100:02d}"


def make_calendars(r):
    days = [D0 + timedelta(days=i) for i in range(NDAYS)]
    sundays = [d for d in days if d.weekday() == 6]
    nat = set(r.sample([d for d in days if d.weekday() not in (6, 0)], 2)) | {r.choice(sundays)}
    cals = {"national": nat}
    for c in CALENDARS[1:]:
        while True:
            own = set(r.sample([d for d in days if d not in nat and d.weekday() != 0], 2))
            own.add(r.choice([s for s in sundays if s not in nat and s + timedelta(days=1) not in nat]))
            cand = nat | own
            if all(cand != v for v in cals.values()):
                break
        cals[c] = cand
    return cals


def draw_conv(r, st, shipped):
    own = st.lower()
    if shipped:
        c = dict(HEADLINE)
        c["H"] = own
        return c
    kA = r.choice([1, 15, 16, 30]) if r.random() < 0.2 else r.choice(KA_ALL)
    kD = r.choice([1, 5, 6, 10]) if r.random() < 0.2 else r.choice(KD_ALL)
    if r.random() < 0.15:
        w = (1320, 360)
    else:
        w = (r.randrange(17 * 60, 24 * 60), r.randrange(4 * 60, 9 * 60))
    H = own if r.random() < 0.25 else r.choice([c for c in CALENDARS if c != own])
    return {"kA": kA, "kD": kD, "S": r.random() < 0.5, "B": r.random() < 0.5, "H": H, "N": w}


class Gen:
    def __init__(self, seed, shipped, n_paid):
        self.seed = seed
        self.r = random.Random(seed)
        self.obs = random.Random(seed * 13 + 7)
        self.shipped = shipped
        self.n_paid = n_paid
        self.cals = make_calendars(self.r)
        self.used_v = set()
        self.used_i = set()
        self.visits = []      # dicts: id, station, vessel, day, minute, cm, tugs, assist, dur
        self.vessels = []
        self.certs = {}
        self.make_vessels()

    # ---------------- register ----------------
    def make_vessels(self):
        r = self.r
        n = 0
        for i in range(1400):
            vid = f"IMO{r.randrange(9000000, 9999999)}"
            while any(v["id"] == vid for v in self.vessels[-50:]):
                vid = f"IMO{r.randrange(9000000, 9999999)}"
            seg = "public" if r.random() < 0.15 else "commercial"
            cert = ""
            if seg == "public" and r.random() < 0.8:
                n += 1
                cert = f"C{10000 + n}"
                exp = D0 + timedelta(days=r.randrange(-30, NDAYS + 60))
                self.certs[cert] = {"holder": vid, "expiry": exp.isoformat()}
            self.vessels.append({"id": vid, "name": f"{r.choice(NAMES)} {r.choice(NAMES2)}",
                                 "gt": r.randrange(800, 60000), "segment": seg, "certificate": cert})
        ids = set()
        uniq = []
        for v in self.vessels:
            if v["id"] not in ids:
                ids.add(v["id"])
                uniq.append(v)
        self.vessels = uniq

    @staticmethod
    def rel(v):
        t0 = datetime(v["day"].year, v["day"].month, v["day"].day) + timedelta(minutes=v["minute"] + v["dur"])
        return t0.date().isoformat()

    def exempt(self, ves, day):
        if ves["segment"] != "public" or not ves["certificate"]:
            return False
        return day < date.fromisoformat(self.certs[ves["certificate"]]["expiry"])

    def vid(self, r):
        while True:
            v = f"V{r.randrange(100000, 999999)}"
            if v not in self.used_v:
                self.used_v.add(v)
                return v

    def iid(self, r, pre):
        while True:
            v = f"{pre}{r.randrange(1000000, 9999999)}"
            if v not in self.used_i:
                self.used_i.add(v)
                return v

    def visit(self, r, st, day=None, minute=None, assist=None, draft=None, tugs=None, notugs=False,
              lo=D0, hi=END, want_exempt=None):
        day = day if day is not None else lo + timedelta(days=r.randrange((hi - lo).days))
        minute = minute if minute is not None else r.randrange(1440)
        while True:
            ves = r.choice(self.vessels)
            ex = self.exempt(ves, day)
            if want_exempt is None and not ex:
                break
            if want_exempt is not None and ex == want_exempt:
                break
        v = {"id": self.vid(r), "station": st, "vessel": ves["id"], "gt": ves["gt"], "day": day,
             "minute": minute, "cm": draft if draft is not None else r.randrange(450, 1400),
             "tugs": 0 if notugs else (tugs if tugs is not None else r.randrange(0, 4)),
             "assist": assist if assist is not None else r.choice([0, 0, r.randrange(1, 240)]),
             "dur": r.randrange(30, 600), "exempt": ex}
        self.visits.append(v)
        return v

    # ---------------- one station ----------------
    def station(self, st):
        r = self.r
        c = draw_conv(r, st, self.shipped)
        starts = [D0]
        tar = [r.choice(TARIFFS)]
        if (not self.shipped) and r.random() < 0.6:
            starts.append(D0 + timedelta(days=r.randrange(30, 62)))
            t = list(tar[0])
            for k in r.sample(range(4), r.choice([1, 2])):
                lst = [B_LIST, D_LIST, N_LIST, T_LIST][k]
                t[k] = r.choice([x for x in lst if x != t[k]])
            tar.append(tuple(t))
        amb = [False] * len(starts)
        # an unresolved period only beside a resolved one, so the conventions stay observable
        if not self.shipped and len(starts) > 1 and r.random() < 0.6:
            amb[r.randrange(len(starts))] = True
        bounds = [(starts[p], starts[p + 1] if p + 1 < len(starts) else END) for p in range(len(starts))]
        groups = [[] for _ in starts]

        def per_of(day):
            return max(i for i, s0 in enumerate(starts) if day >= s0)

        def add(p, rr=None, **kw):
            rr = rr or r
            lo, hi = bounds[p]
            v = self.visit(rr, st, notugs=amb[p], lo=lo, hi=hi, **kw)
            v["amount"] = true_due(tar[p], v, c, self.cals)
            groups[p].append(v)
            return v

        def plain(p):
            lo, hi = bounds[p]
            while True:
                d = lo + timedelta(days=r.randrange((hi - lo).days))
                if not any(holiday(d, self.cals[h], s) for h in CALENDARS for s in (True, False)):
                    return d

        def daymin():
            while True:
                m = r.randrange(1440)
                if not in_window(m, c["N"]):
                    return m

        for p in range(len(starts)):
            for _ in range(self.n_paid):
                add(p)
        p0 = 0
        for k in (c["kA"] - 1, c["kA"]):
            if 1 <= k <= 29:
                add(p0, day=plain(p0), minute=daymin(), assist=30 * r.randrange(0, 4) + k, tugs=1)
        for k in (c["kD"] - 1, c["kD"]):
            if 1 <= k <= 9:
                add(p0, day=plain(p0), minute=daymin(), draft=10 * r.randrange(62, 130) + k, assist=0)
        s, e = c["N"]
        for m0 in (s - 1, s, e - 1, e):
            add(p0, day=plain(p0), minute=m0 % 1440, assist=30 * r.randrange(1, 4) + r.randrange(1, 30))
        for d in sorted(set().union(*self.cals.values())):
            for dd in (d, d + timedelta(days=1)):
                if dd < END:
                    add(per_of(dd), day=dd, minute=daymin())
        truth = None
        for it in range(80):
            fits = fit(groups, self.cals)
            truth = None
            rivals = []
            for conv, per in fits:
                if conv["N"] is None:
                    raise SystemExit(f"{st}: open window rival {conv}")
                if (conv["kA"], conv["kD"], conv["B"], conv["H"], conv["S"], conv["N"]) == \
                        (c["kA"], c["kD"], c["B"], c["H"], c["S"], tuple(c["N"])):
                    truth = per
                else:
                    rivals.append((conv, per))
            assert truth is not None, (st, "truth lost")
            bad = [p for p in range(len(starts)) if not amb[p] and len(truth[p]) != 1]
            if not rivals and not bad:
                break
            o = self.obs
            if rivals:
                rc, rper = o.choice(rivals)
                for _ in range(20000):
                    p = o.randrange(len(starts))
                    lo, hi = bounds[p]
                    v = self.visit(o, st, notugs=amb[p], lo=lo, hi=hi)
                    v["amount"] = true_due(tar[p], v, c, self.cals)
                    if all(true_due(t, v, rc, self.cals) != v["amount"] for t in rper[p]):
                        groups[p].append(v)
                        break
                    self.visits.pop()
                else:
                    raise SystemExit(f"{st}: cannot kill rival {rc}")
            else:
                p = bad[0]
                ts = [t for t in truth[p] if t != tar[p]]
                for _ in range(20000):
                    lo, hi = bounds[p]
                    v = self.visit(o, st, notugs=amb[p], lo=lo, hi=hi)
                    v["amount"] = true_due(tar[p], v, c, self.cals)
                    if all(true_due(t, v, c, self.cals) != v["amount"] for t in ts):
                        groups[p].append(v)
                        break
                    self.visits.pop()
        else:
            raise SystemExit(f"no unique fit for {st}")
        for p in range(len(starts)):
            n = len(truth[p])
            assert (n > 1) if amb[p] else (n == 1), (st, p, n)
        disputed = []
        for _ in range(max(60, self.n_paid // 4)):
            v = self.visit(r, st, want_exempt=(True if r.random() < 0.08 else None))
            p = per_of(v["day"])
            d = true_due(tar[p], v, c, self.cals)
            u = r.random()
            v["billed"] = d if u < 0.45 else (d + r.randrange(100, 9000) if u < 0.8 else max(0, d - r.randrange(100, 9000)))
            if v["exempt"]:
                v["billed"] = r.randrange(5000, 400000)
            disputed.append(v)
        paid = [v for g in groups for v in g]
        return {"station": st, "starts": [s0.isoformat() for s0 in starts], "paid": paid,
                "disputed": disputed,
                "truth": {"conv": {**c, "N": list(c["N"])}, "tariffs": [list(t) for t in tar],
                          "ambiguous": amb, "obs_rows": it}}

    def build(self):
        self.st = [self.station(s) for s in STATIONS]
        if not self.shipped:
            tr = [s["truth"] for s in self.st]
            assert any(len(t["tariffs"]) > 1 for t in tr), "corpus without a notice"
            assert any(any(t["ambiguous"]) for t in tr), "corpus without an unresolved period"
        return self

    # ---------------- rendering ----------------
    def render(self, out):
        r = random.Random(self.seed * 7 + 3)
        os.makedirs(out, exist_ok=True)
        # noise visits for station_mismatch rows
        extra = {}
        for st in STATIONS:
            extra[st] = [self.visit(r, st) for _ in range(3)]
        # register
        with open(os.path.join(out, "vessel_register.tsv"), "w") as f:
            f.write("vessel_id\tname\tgross_tonnage\tsegment\tcertificate\n")
            for v in self.vessels:
                f.write(f"{v['id']}\t{v['name']}\t{v['gt']}\t{v['segment']}\t{v['certificate']}\n")
        with open(os.path.join(out, "certificates.json"), "w") as f:
            json.dump(self.certs, f, indent=1, sort_keys=True)
            f.write("\n")
        with open(os.path.join(out, "holidays.json"), "w") as f:
            json.dump({"about": HOL_ABOUT,
                       "calendars": {k: sorted(d.isoformat() for d in self.cals[k]) for k in CALENDARS}},
                      f, indent=1)
            f.write("\n")
        # notices
        rows = [(s["station"], s["starts"][1]) for s in self.st if len(s["starts"]) > 1]
        with open(os.path.join(DOCS, "station_notices.md")) as f:
            txt = f.read()
        txt = txt.rstrip("\n") + "\n" + "".join(f"| {a} | {b} |\n" for a, b in rows)
        with open(os.path.join(out, "station_notices.md"), "w") as f:
            f.write(txt)
        # paid files
        for s in self.st:
            st = s["station"]
            recs = [(self.iid(r, "INV"), v["id"], self.rel(v), money(v["amount"]))
                    for v in s["paid"]]
            noise = []
            # malformed
            v = s["paid"][0]
            noise.append(("BAD", (self.iid(r, "INV"), v["id"], self.rel(v), "12,40")))
            noise.append(("BAD", (self.iid(r, "INV"), v["id"], "2026-13-40", "10.00")))
            # duplicate pair (both copies new rows)
            dv = self.visit(r, st)
            did = self.iid(r, "INV")
            noise.append(("DUP", (did, dv["id"], self.rel(dv), money(r.randrange(10000, 900000)))))
            noise.append(("DUP", (did, dv["id"], self.rel(dv), money(r.randrange(10000, 900000)))))
            # unknown visit
            noise.append(("UNK", (self.iid(r, "INV"), f"V{r.randrange(100, 999)}000", "2026-08-01",
                                  money(r.randrange(10000, 900000)))))
            # station mismatch: a visit of another station
            other = r.choice([x for x in STATIONS if x != st])
            ov = extra[other][STATIONS.index(st) % 3]
            noise.append(("MIS", (self.iid(r, "INV"), ov["id"], self.rel(ov),
                                  money(r.randrange(10000, 900000)))))
            allrec = [("OK", x) for x in recs] + noise
            r.shuffle(allrec)
            self.write_paid(out, st, allrec)
        # disputed
        recs = []
        for s in self.st:
            for v in s["disputed"]:
                recs.append(("OK", (self.iid(r, "D"), v["id"], s["station"], self.rel(v),
                                    money(v["billed"]))))
        v = self.st[0]["disputed"][0]
        recs.append(("BAD", (self.iid(r, "D"), v["id"], "North", "2026-08-02", "abc")))
        did = self.iid(r, "D")
        dv = self.visit(r, "South")
        recs.append(("DUP", (did, dv["id"], "South", self.rel(dv), "120.00")))
        recs.append(("DUP", (did, dv["id"], "South", self.rel(dv), "130.00")))
        recs.append(("UNK", (self.iid(r, "D"), "V100000", "West", "2026-08-03", "99.00")))
        ov = extra["East"][2]
        recs.append(("MIS", (self.iid(r, "D"), ov["id"], "North", self.rel(ov), "77.00")))
        r.shuffle(recs)
        with open(os.path.join(out, "disputed_batch.csv"), "w") as f:
            f.write("invoice_id,visit_id,station,invoice_date,billed\n")
            for _, x in recs:
                f.write(",".join(x) + "\n")
        # The noise visits were appended after the log was written: rewrite the log.
        self.rewrite_log(out, r)
        for name in ("tariff_circular.md", "exemption_policy.md", "output_contract.md", "rule_register.md"):
            with open(os.path.join(DOCS, name)) as f:
                txt = f.read()
            with open(os.path.join(out, name), "w") as f:
                f.write(txt)

    def rewrite_log(self, out, r):
        lines = []
        rr = random.Random(self.seed * 11 + 1)
        for v in self.visits:
            t0 = datetime(v["day"].year, v["day"].month, v["day"].day) + timedelta(minutes=v["minute"])
            t1 = t0 + timedelta(minutes=v["dur"])
            a = f" assist={v['assist']}" if v["assist"] else ""
            lines.append((t0, 0, f"{t0:%Y-%m-%d %H:%M} BOARD {v['station']} {v['id']} {v['vessel']} "
                                 f"draft={v['cm'] // 100}.{v['cm'] % 100:02d} tugs={v['tugs']}{a}"))
            lines.append((t1, 1, f"{t1:%Y-%m-%d %H:%M} RELEASE {v['id']}"))
        for i in range(40):
            t = datetime(2026, 7, 1) + timedelta(minutes=rr.randrange(NDAYS * 1440))
            lines.append((t, 2, f"NOTE {rr.choice(STATIONS)} {rr.choice(NOTES)}"))
        lines.sort(key=lambda x: (x[0], x[1]))
        with open(os.path.join(out, "pilot_movements.log"), "w") as f:
            for _, _, s in lines:
                f.write(s + "\n")

    def write_paid(self, out, st, allrec):
        path = os.path.join(out, FILE_OF[st])
        with open(path, "w") as f:
            if st == "North":
                f.write("invoice_id,visit_id,invoice_date,amount\n")
                for _, x in allrec:
                    f.write(",".join(x) + "\n")
            elif st == "South":
                for _, x in allrec:
                    f.write(json.dumps({"invoice_id": x[0], "visit_id": x[1], "invoice_date": x[2],
                                        "amount": x[3]}) + "\n")
            elif st == "West":
                for _, x in allrec:
                    f.write(f"{x[0]:<10}{x[1]:<8}{x[2]:<10}{x[3]:>12}\n")
            else:
                f.write('<paid_invoices station="East">\n')
                for _, x in allrec:
                    f.write(f'<invoice id="{x[0]}" visit="{x[1]}" date="{x[2]}" amount="{x[3]}"/>\n')
                f.write("</paid_invoices>\n")

    def truth(self):
        return {"seed": self.seed, "stations": [{"station": s["station"], "starts": s["starts"],
                                                 "paid": len(s["paid"]), **s["truth"]} for s in self.st]}


HOL_ABOUT = ("Holiday calendars of the harbour. Each station keeps exactly one of these calendars, "
             "and a station may also keep the Monday after each Sunday holiday of its calendar. "
             "Which calendar a station keeps, and whether it keeps those Mondays, are conventions "
             "of the station (tariff_circular.md section 5).")
NAMES = ["Nordic", "Atlantic", "Baltic", "Coral", "Granite", "Harbour", "Iron", "Jade", "Kestrel",
         "Lumen", "Meridian", "Opal", "Pioneer", "Quay", "Ranger", "Solent", "Tern", "Vega"]
NAMES2 = ["Star", "Spirit", "Trader", "Venture", "Carrier", "Breeze", "Pride", "Dawn", "Arrow"]
NOTES = ["radio check completed", "berth 4 dredging in progress", "pilot boat refuelled",
         "fog signal tested", "shift handover", "tide gauge recalibrated"]


if __name__ == "__main__":
    t0 = time.time()
    seed = int(sys.argv[1])
    n_paid = int(sys.argv[sys.argv.index("--paid") + 1]) if "--paid" in sys.argv else 250
    g = Gen(seed, "--shipped" in sys.argv, n_paid).build()
    g.render(sys.argv[2])
    tr = g.truth()
    with open(sys.argv[3], "w") as f:
        json.dump(tr, f, indent=1)
    print(seed, "built in %.1fs" % (time.time() - t0),
          [(s["station"], s["paid"], s["obs_rows"], s["ambiguous"], s["conv"]) for s in tr["stations"]])
