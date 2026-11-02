"""L-CONV prototype generator (proto only). Usage: gen2.py SEED OUT.json [--shipped]"""
import json
import random
import sys
import time
from datetime import timedelta

from core2 import (B_LIST, CALENDARS, D0, D_LIST, HEADLINE, KA_ALL, KD_ALL, N_LIST, NDAYS, OWN,
                   STATIONS, T_LIST, TARIFFS, conv_of, fit, holiday, in_window, true_due)


def make_calendars(r):
    sundays = [D0 + timedelta(days=i) for i in range(NDAYS) if (D0 + timedelta(days=i)).weekday() == 6]
    days = [D0 + timedelta(days=i) for i in range(NDAYS)]
    nat = set(r.sample([d for d in days if d.weekday() not in (6, 0)], 2)) | {r.choice(sundays)}
    cals = {"national": nat}
    for c in CALENDARS[1:]:
        own = set(r.sample([d for d in days if d not in nat and d.weekday() != 0], 2))
        own.add(r.choice([s for s in sundays if s not in nat and s + timedelta(days=1) not in nat]))
        cals[c] = nat | own
    return cals


def draw_conv(r, st, shipped):
    if shipped:
        c = dict(HEADLINE)
        c["H"] = OWN[st]
        return c
    kA = r.choice([1, 15, 16, 30]) if r.random() < 0.2 else r.choice(KA_ALL)
    kD = r.choice([1, 5, 6, 10]) if r.random() < 0.2 else r.choice(KD_ALL)
    if r.random() < 0.15:
        w = (1320, 360)
    else:
        w = (r.randrange(18 * 4, 24 * 4) * 15, r.randrange(4 * 4, 9 * 4) * 15)
    H = OWN[st] if r.random() < 0.25 else r.choice([c for c in CALENDARS if c != OWN[st]])
    return {"kA": kA, "kD": kD, "S": r.random() < 0.5, "B": r.random() < 0.5, "H": H, "N": w}


class Gen:
    def __init__(self, seed, shipped):
        self.r = random.Random(seed)
        self.obs = random.Random(seed * 13 + 7)
        self.shipped = shipped
        self.cals = make_calendars(self.r)
        self.n = 0

    def inv(self, r, day=None, minute=None, assist=None, draft=None, tugs=None, notugs=False):
        self.n += 1
        day = day if day is not None else D0 + timedelta(days=r.randrange(NDAYS))
        minute = minute if minute is not None else r.randrange(1440)
        return {"id": f"V{self.n:05d}", "gt": r.randrange(800, 60000),
                "draft_cm": draft if draft is not None else r.randrange(450, 1400),
                "tugs": 0 if notugs else (tugs if tugs is not None else r.randrange(0, 4)),
                "assist": assist if assist is not None else r.choice([0, 0, r.randrange(1, 240)]),
                "board": f"{day.isoformat()} {minute // 60:02d}:{minute % 60:02d}"}

    def plain_day(self, r, c, pick=None):
        while True:
            d = pick() if pick else D0 + timedelta(days=r.randrange(NDAYS))
            if not any(holiday(d, self.cals[h], s) for h in CALENDARS for s in (True, False)):
                return d

    def day_minute(self, r, c):
        while True:
            m = r.randrange(1440)
            if not in_window(m, c["N"]):
                return m

    def station(self, st):
        r = self.r
        c = draw_conv(r, st, self.shipped)
        starts = ["2026-07-01"]
        tar = [r.choice(TARIFFS)]
        notice = (not self.shipped) and r.random() < 0.6
        if notice:
            nd = D0 + timedelta(days=r.randrange(30, 62))
            starts.append(nd.isoformat())
            t = list(tar[0])
            for k in r.sample(range(4), r.choice([1, 2])):
                lst = [B_LIST, D_LIST, N_LIST, T_LIST][k]
                t[k] = r.choice([x for x in lst if x != t[k]])
            tar.append(tuple(t))
        amb = [False] * len(starts)
        if not self.shipped and r.random() < 0.4:
            amb[r.randrange(len(starts))] = True
        paid = []

        def pday(p):
            lo = (D0 if p == 0 else __import__("datetime").date.fromisoformat(starts[p]))
            hi = (__import__("datetime").date.fromisoformat(starts[p + 1]) if p + 1 < len(starts)
                  else D0 + timedelta(days=NDAYS))
            return lo + timedelta(days=r.randrange((hi - lo).days))

        def add(p, **kw):
            if "day" not in kw:
                kw["day"] = pday(p)
            v = self.inv(r, notugs=amb[p], **kw)
            v["amount"] = true_due(tar[p], v, c, self.cals)
            paid.append(v)
        for p in range(len(starts)):
            for _ in range(60):
                add(p)
        # coverage plants (first period that is not ambiguous, else period 0)
        p0 = 0
        pl = lambda **kw: add(p0, day=self.plain_day(r, c, lambda: pday(p0)), minute=self.day_minute(r, c), **kw)
        for k in (c["kA"] - 1, c["kA"]):
            if 1 <= k <= 29:
                pl(assist=30 * r.randrange(0, 4) + k, tugs=1)
        for k in (c["kD"] - 1, c["kD"]):
            if 1 <= k <= 9:
                pl(draft=10 * r.randrange(62, 130) + k, assist=0)
        s, e = c["N"]
        for m0 in (s - 15, s, e - 15, e):
            add(p0, day=self.plain_day(r, c, lambda: pday(p0)), minute=(m0 + r.randrange(15)) % 1440, assist=30 * r.randrange(1, 4) + r.randrange(1, 30))
        for d in sorted(set().union(*self.cals.values())):
            for dd in (d, d + timedelta(days=1)):
                if dd < D0 + timedelta(days=NDAYS):
                    p = max(i for i, s0 in enumerate(starts) if dd.isoformat() >= s0)
                    add(p, day=dd, minute=self.day_minute(r, c))
        st_d = {"station": st, "period_starts": starts, "paid": paid, "disputed": []}
        # observe loop: add evidence until the conventions are unique and every
        # non-ambiguous period has exactly one tariff
        for it in range(60):
            fits = fit(st_d, self.cals)
            truth = (c["kA"], c["kD"], c["B"], c["H"], c["S"], c["N"])
            assert truth in fits, (st, "truth lost")
            rivals = [k for k in fits if k != truth]
            bad_p = [p for p in range(len(starts)) if not amb[p] and len(fits[truth][p]) != 1]
            if not rivals and not bad_p:
                break
            o = self.obs
            if rivals:
                rk = o.choice(rivals)
                rc = conv_of(rk)
                for _ in range(5000):
                    p = o.randrange(len(starts))
                    v = self.inv(o, day=pday(p), notugs=amb[p])
                    v["amount"] = true_due(tar[p], v, c, self.cals)
                    if all(true_due(t, v, rc, self.cals) != v["amount"] for t in fits[rk][p]):
                        paid.append(v)
                        break
            else:
                p = bad_p[0]
                ts = [t for t in fits[truth][p] if t != tar[p]]
                for _ in range(5000):
                    v = self.inv(o, day=pday(p), notugs=amb[p])
                    v["amount"] = true_due(tar[p], v, c, self.cals)
                    if all(true_due(t, v, c, self.cals) != v["amount"] for t in ts):
                        paid.append(v)
                        break
        else:
            raise SystemExit(f"no unique fit for {st}")
        for p in range(len(starts)):
            n = len(fits[truth][p])
            assert (n > 1) if amb[p] else (n == 1), (st, p, n)
        for _ in range(60):
            v = self.inv(r)
            p = max(i for i, s0 in enumerate(starts) if v["board"][:10] >= s0)
            d = true_due(tar[p], v, c, self.cals)
            v["billed"] = d if r.random() < 0.5 else d + r.choice([-1, 1]) * r.randrange(100, 9000)
            st_d["disputed"].append(v)
        r.shuffle(paid)
        st_d["truth"] = {"conv": {**c, "N": list(c["N"])}, "tariffs": [list(t) for t in tar],
                         "ambiguous": amb, "obs_rows": it}
        return st_d

    def build(self):
        return {"calendars": {k: sorted(d.isoformat() for d in v) for k, v in self.cals.items()},
                "stations": [self.station(s) for s in STATIONS]}


if __name__ == "__main__":
    t0 = time.time()
    seed = int(sys.argv[1])
    doc = Gen(seed, "--shipped" in sys.argv).build()
    json.dump(doc, open(sys.argv[2], "w"))
    print(seed, "built in %.1fs" % (time.time() - t0),
          [(s["station"], len(s["paid"]), s["truth"]["obs_rows"], s["truth"]["ambiguous"]) for s in doc["stations"]])
