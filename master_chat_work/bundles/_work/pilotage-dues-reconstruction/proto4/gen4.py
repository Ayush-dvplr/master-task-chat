"""Try-4 prototype generator: gen4.py SEED DATA_DIR TRUTH.json [--shipped] [--paid N]"""
import json, os, random, shutil, sys, time
from datetime import datetime, timedelta
from core4 import (D0, NDAYS, STATIONS, TARIFFS, B_LIST, D_LIST, N_LIST, T_LIST,
                   amount, fit, full_domain, day_min, days)

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")
FLAGS = ["Aurelia", "Borvia", "Calder", "Dravia", "Estmark"]
OFFICES = ["Portmere", "Kelby", "Halden", "Ostra"]
FILE_OF = {"North": "paid_north.csv", "South": "paid_south.jsonl",
           "West": "paid_west.txt", "East": "paid_east.xml"}
NAMES = ["Albatross", "Beacon", "Corsair", "Delphine", "Egret", "Falcon", "Gannet", "Heron",
         "Ibis", "Jade", "Kestrel", "Lark", "Merlin", "Nereid", "Osprey", "Petrel", "Quill",
         "Raven", "Swift", "Tern"]
NAMES2 = ["Star", "Spirit", "Trader", "Venture", "Pioneer", "Glory", "Wind", "Crest"]
AGENTS = ["Harbour Line", "Blue Anchor", "Northgate", "Meridian", "Saltway", "Tidewell",
          "Keel and Co", "Lantern", "Seabright", "Quayside"]
NOTES = ["berth 4 dredging", "fog signal tested", "pilot boat refuelled", "radio check",
         "shift handover", "tide gauge recalibrated"]
HOL_ABOUT = ("Holiday calendars: the national calendar, the calendar of each harbour region, "
             "the calendar of each flag state whose ships call here and the calendar of each "
             "city where a shipping agent keeps an office.")


def money(c):
    s = "-" if c < 0 else ""
    c = abs(c)
    return f"{s}{c // 100}.{c % 100:02d}"


def hm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


class Gen:
    def __init__(self, seed, shipped, n_paid):
        self.seed, self.shipped, self.n_paid = seed, shipped, n_paid
        self.r = random.Random(seed)
        self.obs = random.Random(seed * 13 + 7)
        self.used = set()
        self.visits = []
        self.make_world()

    def uid(self, pre, n, r=None):
        r = r or self.r
        while True:
            x = pre + str(r.randrange(10 ** (n - 1), 10 ** n))
            if x not in self.used:
                self.used.add(x)
                return x

    def make_world(self):
        r = self.r
        pool = days()
        r.shuffle(pool)
        it = iter(pool)
        cals = {"national": sorted(next(it) for _ in range(3))}
        for st in STATIONS:
            cals[st.lower()] = sorted(cals["national"] + [next(it) for _ in range(2)])
        for f in FLAGS + OFFICES:
            cals[f] = sorted(next(it) for _ in range(2))
        self.calendars = cals
        self.agents = {}
        for i, nm in enumerate(AGENTS):
            self.agents[f"AG{i + 1:02d}"] = (r.choice(OFFICES), 5 * r.randrange(72, 118),
                                             5 * r.randrange(192, 240), nm)
        self.watch, self.office = {}, {}
        for st in STATIONS:
            if self.shipped:
                self.watch[st] = (22 * 60, 6 * 60)
            else:
                self.watch[st] = (5 * r.randrange(240, 283), 5 * r.randrange(60, 91))
            self.office[st] = (5 * r.randrange(84, 109), 5 * r.randrange(192, 223))
        self.ctx = {"cals": {k: set(v) for k, v in cals.items()},
                    "agents": {k: (v[0], v[1], v[2]) for k, v in self.agents.items()},
                    "watch": self.watch, "office": self.office}
        self.vessels, self.certs = {}, {}
        for _ in range(1400):
            vid = self.uid("IMO", 7)
            gross = r.randrange(400, 60000)
            seg = "public" if r.random() < 0.15 else "commercial"
            cert = ""
            if seg == "public" and r.random() < 0.8:
                cert = self.uid("C", 5)
                self.certs[cert] = {"holder": vid,
                                    "expiry": str(D0 + timedelta(days=r.randrange(-30, 152)))}
            self.vessels[vid] = {"gross": gross, "net": int(gross * r.uniform(0.28, 0.62)),
                                 "max_cm": r.randrange(700, 1500), "flag": r.choice(FLAGS),
                                 "agent": r.choice(sorted(self.agents)), "segment": seg,
                                 "cert": cert,
                                 "name": f"{r.choice(NAMES)} {r.choice(NAMES2)}"}

    def exempt(self, vid, day):
        ves = self.vessels[vid]
        if ves["segment"] != "public" or not ves["cert"]:
            return False
        return str(day) < self.certs[ves["cert"]]["expiry"]

    def visit(self, r, st, lo, hi, notugs=False, want_exempt=False, day=None, minute=None):
        while True:
            vid = r.choice(sorted(self.vessels)) if not hasattr(self, "_vl") else r.choice(self._vl)
            d = day if day is not None else lo + timedelta(days=r.randrange((hi - lo).days))
            if self.exempt(vid, d) == want_exempt:
                break
        ves = self.vessels[vid]
        m = minute if minute is not None else r.randrange(1440)
        board = datetime(d.year, d.month, d.day) + timedelta(minutes=m)
        order = board - timedelta(minutes=r.randrange(30, 301))
        release = board + timedelta(minutes=r.randrange(30, 601))
        cm = r.randrange(550, ves["max_cm"] + 1)
        decl = cm if r.random() < 0.15 else max(450, min(ves["max_cm"], cm + r.choice([-1, 1]) * r.randrange(5, 61)))
        v = {"id": self.uid("V", 6, r), "station": st, "vessel": vid, "gross": ves["gross"],
             "net": ves["net"], "max_cm": ves["max_cm"], "flag": ves["flag"],
             "agent": ves["agent"], "cm": cm, "decl_cm": decl,
             "tugs": 0 if notugs else r.randrange(0, 4),
             "assist": 0 if r.random() < 0.5 else r.randrange(1, 240),
             "order": day_min(order), "board": day_min(board), "release": day_min(release),
             "dts": (order, board, release), "exempt": want_exempt}
        self.visits.append(v)
        return v

    def draw_conv(self, st):
        r = self.r
        if self.shipped:
            return {"cal": "cal:" + st.lower(), "hrs": "watch", "time": "board",
                    "draft": "measured", "ton": "gross"}
        x = r.random()
        if x < 0.35:
            cal = "flag"
        elif x < 0.7:
            cal = "agent"
        elif x < 0.85:
            cal = "cal:" + st.lower()
        elif x < 0.9:
            cal = "cal:national"
        else:
            cal = "cal:" + r.choice([k for k in self.calendars if k != st.lower()])
        return {"cal": cal, "hrs": r.choices(["watch", "office", "agent"], [3, 3, 4])[0],
                "time": r.choices(["board", "order", "release"], [4, 3, 3])[0],
                "draft": r.choices(["measured", "declared", "register"], [4, 3, 3])[0],
                "ton": r.choice(["gross", "net"])}

    def station(self, st):
        r = self.r
        conv = self.draw_conv(st)
        starts = [D0]
        if not self.shipped and r.random() < 0.6:
            starts.append(D0 + timedelta(days=r.randrange(30, 62)))
        amb = [False] * len(starts)
        if len(starts) > 1 and r.random() < 0.6:
            amb[r.randrange(len(starts))] = True
        tar = [r.choice(TARIFFS)]
        if len(starts) > 1:
            t = list(tar[0])
            lists = [B_LIST, D_LIST, N_LIST, T_LIST]
            for i in r.sample(range(4), r.choice([1, 2])):
                t[i] = r.choice([x for x in lists[i] if x != t[i]])
            tar.append(tuple(t))
        bounds = [(s, starts[i + 1] if i + 1 < len(starts) else D0 + timedelta(days=NDAYS))
                  for i, s in enumerate(starts)]
        groups = [[] for _ in starts]

        def add(p, v):
            v["amount"] = amount(tar[p], v, conv, self.ctx)
            v["period"] = p
            groups[p].append(v)

        for p, (lo, hi) in enumerate(bounds):
            for _ in range(self.n_paid):
                add(p, self.visit(r, st, lo, hi, notugs=amb[p]))
        dom = full_domain(self.ctx)
        obs_rows = 0
        hol = sorted(set(d for v in self.calendars.values() for d in v))
        for _ in range(300):
            res = fit(groups, self.ctx, dom)
            convs = [c for c, _ in res]
            assert conv in convs, (st, "truth lost")
            rivals = [(c, ts) for c, ts in res if c != conv]
            mine = dict((tuple(sorted(c.items())), ts) for c, ts in res)[tuple(sorted(conv.items()))]
            target = None
            if rivals:
                target = self.obs.choice(rivals)
            else:
                bad = [p for p, ts in enumerate(mine) if not amb[p] and len(ts) > 1]
                if not bad:
                    break
                target = (conv, mine)
            rc, rts = target
            for _ in range(5000):
                p = self.obs.randrange(len(starts))
                lo, hi = bounds[p]
                day = None
                if self.obs.random() < 0.5:
                    cand = [d for d in hol if lo <= d < hi]
                    if cand:
                        day = self.obs.choice(cand)
                v = self.visit(self.obs, st, lo, hi, notugs=amb[p], day=day)
                truth = amount(tar[p], v, conv, self.ctx)
                others = [t for t in rts[p] if not (rc == conv and t == tar[p])]
                if all(amount(t, v, rc, self.ctx) != truth for t in others):
                    add(p, v)
                    obs_rows += 1
                    break
                self.visits.pop()
            else:
                raise AssertionError((st, "no separating visit", rc))
        else:
            raise AssertionError((st, "observe loop did not converge"))
        res = fit(groups, self.ctx, dom)
        assert len(res) == 1 and res[0][0] == conv, (st, len(res))
        for p, ts in enumerate(res[0][1]):
            assert (len(ts) > 1) if amb[p] else (ts == [tar[p]]), (st, p, ts)
        self.paid[st] = [v for g in groups for v in g]
        disp = []
        for _ in range(max(60, self.n_paid // 4)):
            p = r.randrange(len(starts))
            lo, hi = bounds[p]
            ex = r.random() < 0.08
            v = self.visit(r, st, lo, hi, want_exempt=ex)
            due = amount(tar[p], v, conv, self.ctx)
            x = r.random()
            if ex:
                billed = r.randrange(5000, 400000)
            elif x < 0.45:
                billed = due
            elif x < 0.8:
                billed = due + r.randrange(100, 9001)
            else:
                billed = max(0, due - r.randrange(100, 9001))
            disp.append((v, billed))
        self.disputed[st] = disp
        self.truth_st.append({"station": st, "starts": [str(s) for s in starts], "conv": conv,
                              "tariffs": [list(t) for t in tar], "ambiguous": amb,
                              "obs_rows": obs_rows, "paid": len(self.paid[st])})
        return starts

    def build(self):
        self.paid, self.disputed, self.truth_st, self.notices = {}, {}, [], []
        for st in STATIONS:
            starts = self.station(st)
            if len(starts) > 1:
                self.notices.append((st, starts[1]))
        if not self.shipped:
            per_visit = sum(1 for t in self.truth_st
                            if t["conv"]["cal"] in ("flag", "agent") or t["conv"]["hrs"] == "agent")
            assert per_visit >= 3, "corpus with fewer than 3 per-visit anchors"
            assert self.notices, "corpus without a notice"
            assert any(any(t["ambiguous"]) for t in self.truth_st), "corpus without an unresolved period"

    def render(self, out):
        r = self.r
        os.makedirs(out, exist_ok=True)
        extra = {st: [self.visit(r, st, D0, D0 + timedelta(days=NDAYS)) for _ in range(3)]
                 for st in STATIONS}
        reg = ["vessel_id\tname\tgross_tonnage\tnet_tonnage\tmax_draft\tflag\tagent\tsegment\tcertificate"]
        for vid in sorted(self.vessels):
            v = self.vessels[vid]
            reg.append(f"{vid}\t{v['name']}\t{v['gross']}\t{v['net']}\t{v['max_cm'] // 100}.{v['max_cm'] % 100:02d}"
                       f"\t{v['flag']}\t{v['agent']}\t{v['segment']}\t{v['cert']}")
        self.w(out, "vessel_register.tsv", reg)
        ag = ["agent\tname\toffice\topens\tcloses"]
        for k in sorted(self.agents):
            o, op, cl, nm = self.agents[k]
            ag.append(f"{k}\t{nm}\t{o}\t{hm(op)}\t{hm(cl)}")
        self.w(out, "agents.tsv", ag)
        sts = ["station\twatch_from\twatch_to\topens\tcloses"]
        for st in STATIONS:
            sts.append(f"{st}\t{hm(self.watch[st][0])}\t{hm(self.watch[st][1])}\t"
                       f"{hm(self.office[st][0])}\t{hm(self.office[st][1])}")
        self.w(out, "stations.tsv", sts)
        with open(os.path.join(out, "certificates.json"), "w") as f:
            json.dump(self.certs, f, indent=1, sort_keys=True)
            f.write("\n")
        with open(os.path.join(out, "holidays.json"), "w") as f:
            json.dump({"about": HOL_ABOUT,
                       "calendars": {k: [str(d) for d in v] for k, v in self.calendars.items()}},
                      f, indent=1)
            f.write("\n")
        with open(os.path.join(DOCS, "station_notices.md")) as f:
            notes = f.read().rstrip("\n").split("\n")
        for st, d in self.notices:
            notes.append(f"| {st} | {d} |")
        self.w(out, "station_notices.md", notes)
        for d in ["tariff_circular.md", "exemption_policy.md", "output_contract.md", "rule_register.md"]:
            shutil.copy(os.path.join(DOCS, d), os.path.join(out, d))
        allvis = {v["id"]: v for v in self.visits}
        for i, st in enumerate(STATIONS):
            rows = [(self.uid("INV", 7), v["id"], str(v["dts"][2].date()), money(v["amount"]))
                    for v in self.paid[st]]
            other = extra[STATIONS[(i + 1) % 4]][0]
            fresh = extra[st][1]
            dup = self.uid("INV", 7)
            rows += [(self.uid("INV", 7), self.paid[st][0]["id"], str(self.paid[st][0]["dts"][2].date()), "12,40"),
                     (self.uid("INV", 7), self.paid[st][1]["id"], "2026-13-40", "100.00"),
                     (dup, fresh["id"], str(fresh["dts"][2].date()), "250.00"),
                     (dup, fresh["id"], str(fresh["dts"][2].date()), "250.00"),
                     (self.uid("INV", 7), f"V{r.randrange(100, 999)}000", "2026-08-01", "300.00"),
                     (self.uid("INV", 7), other["id"], str(other["dts"][2].date()), "410.00")]
            r.shuffle(rows)
            self.write_paid(out, st, rows)
        drows = []
        for st in STATIONS:
            for v, billed in self.disputed[st]:
                drows.append((self.uid("D", 7), v["id"], st, str(v["dts"][2].date()), money(billed)))
        e = extra["East"][2]
        s2 = extra["South"][2]
        dupd = self.uid("D", 7)
        drows += [(self.uid("D", 7), drows[0][1], drows[0][2], drows[0][3], "abc"),
                  (dupd, s2["id"], "South", str(s2["dts"][2].date()), "500.00"),
                  (dupd, s2["id"], "South", str(s2["dts"][2].date()), "500.00"),
                  (self.uid("D", 7), "V100000", "North", "2026-08-02", "90.00"),
                  (self.uid("D", 7), e["id"], "North", str(e["dts"][2].date()), "77.00")]
        r.shuffle(drows)
        self.w(out, "disputed_batch.csv", ["invoice_id,visit_id,station,invoice_date,billed"]
               + [",".join(x) for x in drows])
        self.write_log(out)

    def write_log(self, out):
        r = self.r
        ev = []
        for v in self.visits:
            o, b, rl = v["dts"]
            ev.append((o, 0, f"{o:%Y-%m-%d %H:%M} ORDER {v['station']} {v['id']} draft={v['decl_cm'] // 100}.{v['decl_cm'] % 100:02d}"))
            line = (f"{b:%Y-%m-%d %H:%M} BOARD {v['station']} {v['id']} {v['vessel']} "
                    f"draft={v['cm'] // 100}.{v['cm'] % 100:02d} tugs={v['tugs']}")
            if v["assist"]:
                line += f" assist={v['assist']}"
            ev.append((b, 1, line))
            ev.append((rl, 2, f"{rl:%Y-%m-%d %H:%M} RELEASE {v['id']}"))
        for _ in range(40):
            t = datetime(2026, 7, 1) + timedelta(minutes=r.randrange(NDAYS * 1440))
            ev.append((t, 3, f"{t:%Y-%m-%d %H:%M} NOTE {r.choice(STATIONS)} {r.choice(NOTES)}"))
        ev.sort(key=lambda x: (x[0], x[1], x[2]))
        self.w(out, "pilot_movements.log", [x[2] for x in ev])

    def write_paid(self, out, st, rows):
        name = FILE_OF[st]
        if name.endswith(".csv"):
            lines = ["invoice_id,visit_id,invoice_date,amount"] + [",".join(x) for x in rows]
        elif name.endswith(".jsonl"):
            lines = [json.dumps({"invoice_id": a, "visit_id": b, "invoice_date": c, "amount": d})
                     for a, b, c, d in rows]
        elif name.endswith(".txt"):
            lines = [f"{a:<10}{b:<8}{c:<10}{d:>12}" for a, b, c, d in rows]
        else:
            lines = ['<paid_invoices station="East">'] + [
                f'  <invoice id="{a}" visit="{b}" date="{c}" amount="{d}"/>' for a, b, c, d in rows
            ] + ["</paid_invoices>"]
        self.w(out, name, lines)

    @staticmethod
    def w(out, name, lines):
        with open(os.path.join(out, name), "w") as f:
            f.write("\n".join(lines) + "\n")


def main():
    a = sys.argv[1:]
    seed, out, tpath = int(a[0]), a[1], a[2]
    shipped = "--shipped" in a
    n = int(a[a.index("--paid") + 1]) if "--paid" in a else 250
    t0 = time.time()
    g = Gen(seed, shipped, n)
    g.build()
    g.render(out)
    with open(tpath, "w") as f:
        json.dump({"seed": seed, "stations": g.truth_st}, f, indent=1)
    print(f"gen4 seed={seed} shipped={shipped} {time.time() - t0:.2f}s",
          [(t["station"], t["conv"]["cal"], t["conv"]["hrs"], t["conv"]["time"], t["conv"]["draft"],
            t["conv"]["ton"], len(t["starts"]), t["ambiguous"], t["obs_rows"]) for t in g.truth_st])


if __name__ == "__main__":
    main()
