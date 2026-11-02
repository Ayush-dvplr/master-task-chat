#!/usr/bin/env python3
"""Prototype generator: shipped-like degenerate extract and hidden one-pair extracts.

python3 gen.py --out DIR --shipped [--seed N]
python3 gen.py --out DIR --hidden SEED     -> DIR/h_<kind>_<k>/
"""
import csv, hashlib, json, os, random, sys, datetime as dt
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import solve_proto as C

PRICES = {"BASE-PLAN": "49.00", "SEAT-STD": "12.00", "SEAT-PRO": "27.50", "USAGE-BLOCK": "7.20"}
VAR = {"cstart": "cstart=halfopen", "expiry": "expiry=inclusive", "sameday": "sameday=invoices_first",
       "cap": "cap=posted", "order": "order=arrival", "rounding": "rounding=half_up", "first": "fit=first",
       "best": "fit=best", "withvoid": "evidence=withvoid", "all": "evidence=all", "ncycles": "ncycles=fixed12",
       "fixed1": "fit=fixed1"}
KINDS = ["PA1", "PA2", "PA3", "PA4", "PA5", "PA6", "PB1", "PB1b", "PB2", "PS"]
MUST = {"PA1": {"cstart"}, "PA2": {"expiry"}, "PA3": {"sameday"}, "PA4": {"cap"}, "PA5": {"order"},
        "PA6": {"rounding"}, "PB1": {"first", "best"}, "PB1b": {"first"}, "PB2": {"best"}, "PB3": {"withvoid"},
        "PS": {"ncycles"}}
ALLOW = {"PB1": {"all"}, "PB1b": {"best", "all"}, "PB2": {"first", "all"}, "PB3": {"all"}, "PS": {"expiry"},
         "PA6": {"first", "best"}}
REGIONS, SEGMENTS = C.REGIONS, C.SEGMENTS
D1 = dt.timedelta(days=1)


class Ids:
    def __init__(self, rng):
        self.rng, self.used = rng, set()

    def new(self, prefix, n):
        while True:
            v = prefix + "".join(self.rng.choice("0123456789") for _ in range(n))
            if v not in self.used:
                self.used.add(v)
                return v


def money(rng, lo, hi):
    return Decimal(rng.randint(int(lo * 100), int(hi * 100))) / 100


class X:
    """One extract under construction."""

    def __init__(self, rng, first, months, ncyc, extract_id):
        self.rng, self.ids = rng, Ids(rng)
        self.first, self.months, self.last = first, months, C.madd(first, months - 1)
        self.ncyc, self.extract_id = ncyc, extract_id
        self.accounts, self.T, self.events, self.reg, self.void_src = [], {}, [], [], {}
        self.lots, self.transfers, self.corr, self.lines = [], [], [], {}
        self.extra_pay = {}
        self.alter = []

    def S(self, acct, m):
        return C.mstart(m, self.T[acct][0])

    def starts(self, acct):
        return {self.S(acct, C.madd(self.first, k)) for k in range(-1, self.months + 1)}

    def E_last(self, acct):
        return self.S(acct, C.madd(self.last, 1)) - D1

    def rand_day(self, lo, hi, avoid=()):
        for _ in range(200):
            x = lo + dt.timedelta(days=self.rng.randint(0, (hi - lo).days))
            if x not in avoid:
                return x
        raise RuntimeError("no day")

    def add_event(self, acct, item, qty, day):
        self.events.append(dict(event_id=self.ids.new("EV", 6), account_id=acct, item=item, quantity=qty,
                                date=day.isoformat()))

    def q_orig(self, acct, item, day):
        v, best = 0, None
        for e in self.events:
            if e["account_id"] == acct and e["item"] == item and e["date"] <= day.isoformat():
                if best is None or e["date"] >= best:
                    best, v = e["date"], e["quantity"]
        return v

    def last_change(self, acct, item):
        ds = [e["date"] for e in self.events if e["account_id"] == acct and e["item"] == item]
        return C.d(max(ds)) if ds else C.mstart(C.madd(self.first, -2), 1)

    def new_account(self, parent, anchor, basis, nchanges, zone=None):
        rng = self.rng
        a = self.ids.new("AC", 5)
        self.accounts.append(dict(account_id=a, parent_id=parent, region=rng.choice(REGIONS),
                                  segment=rng.choice(SEGMENTS)))
        self.T[a] = (anchor, basis)
        op = C.mstart(C.madd(self.first, -2), 1)
        self.add_event(a, "BASE-PLAN", 1, op)
        self.add_event(a, "SEAT-STD", rng.randint(2, 12), op)
        if rng.random() < 0.6:
            self.add_event(a, "SEAT-PRO", rng.randint(1, 3), op)
        self.add_event(a, "USAGE-BLOCK", rng.randint(1, 8), op)
        lo, hi = zone or (self.S(a, C.madd(self.first, -1)) + D1, self.E_last(a))
        for _ in range(nchanges):
            self.random_change(a, lo, hi)
        return a

    def random_change(self, a, lo, hi, avoid_extra=()):
        rng = self.rng
        item = rng.choice(["SEAT-STD", "SEAT-PRO", "USAGE-BLOCK"])
        day = self.rand_day(lo, hi, self.starts(a) | set(avoid_extra) |
                            {C.d(e["date"]) for e in self.events if e["account_id"] == a})
        cur = self.q_orig(a, item, day)
        floor = 1 if item == "SEAT-STD" else 0
        for _ in range(20):
            nv = cur + rng.choice([-3, -2, -1, 1, 1, 2, 2, 3, 4])
            if nv >= floor and nv != cur and nv <= 20:
                break
        else:
            nv = cur + 1
        self.add_event(a, item, nv, day)

    def add_invoices(self, void_p):
        for acct in [x["account_id"] for x in self.accounts]:
            for k in range(self.months):
                m = C.madd(self.first, k)
                iv = self.ids.new("IV", 6)
                self.reg.append(dict(invoice_id=iv, account_id=acct, statement_month=m,
                                     status="open" if k == self.months - 1 else "paid"))
                if k < self.months - 1 and self.rng.random() < void_p:
                    vid = self.ids.new("IV", 6)
                    self.reg.append(dict(invoice_id=vid, account_id=acct, statement_month=m, status="void"))
                    self.void_src[vid] = (acct, m, None)

    def add_lot(self, acct, amount, created, expires):
        lid = self.ids.new("LT", 5)
        self.lots.append(dict(lot_id=lid, account_id=acct, amount=str(amount), created_on=created.isoformat(),
                              expires_on=expires.isoformat()))
        return lid

    def random_lots(self, acct, n):
        sf = self.S(acct, self.first)
        for _ in range(n):
            created = sf - dt.timedelta(days=self.rng.randint(5, 60))
            exp = self.rand_day(sf + dt.timedelta(days=15), sf + dt.timedelta(days=420), self.starts(acct))
            self.add_lot(acct, money(self.rng, 20, 300), created, exp)

    def add_transfer(self, frm, to, day, req):
        tid = self.ids.new("TR", 5)
        ts = "%sT%02d:%02d:%02dZ" % (day.isoformat(), self.rng.randint(0, 23), self.rng.randint(0, 59),
                                     self.rng.randint(0, 59))
        self.transfers.append(dict(id=tid, frm=frm, to=to, req=req, date=day, ts=ts))
        return tid

    def random_transfer(self, frm, to):
        lo = self.S(frm, self.first) + D1
        hi = self.E_last(frm) - D1
        avoid = set(self.starts(frm)) | (self.starts(to) if to in self.T else set())
        avoid |= {C.d(l["expires_on"]) for l in self.lots}
        day = self.rand_day(lo, hi, avoid)
        return self.add_transfer(frm, to, day, money(self.rng, 10, 150))

    def add_correction(self, acct, item, qty, eff, cid=None):
        c = dict(correction_id=cid or self.ids.new("CR", 5), account_id=acct, item=item, quantity=qty,
                 effective_date=eff.isoformat(), arrival_seq=0)
        self.corr.append(c)
        return c

    def accepted_correction(self, acct, avoid_items=()):
        rng = self.rng
        items = [i for i in ("SEAT-STD", "SEAT-PRO", "USAGE-BLOCK") if i not in avoid_items]
        rng.shuffle(items)
        for item in items:
            lo = max(self.S(acct, self.first), self.last_change(acct, item) + D1)
            hi = self.S(acct, self.last) - D1
            if lo >= hi:
                continue
            eff = self.rand_day(lo, hi, self.starts(acct))
            cur = self.q_orig(acct, item, eff)
            floor = 1 if item == "SEAT-STD" else 0
            nv = max(floor, cur + rng.choice([-2, -1, 1, 2, 3]))
            if nv == cur:
                nv = cur + 1
            return self.add_correction(acct, item, nv, eff)
        return None

    def number_arrivals(self, pinned=()):
        """Assign arrival_seq: random order, then enforce pinned (earlier, later) pairs."""
        order = list(range(len(self.corr)))
        self.rng.shuffle(order)
        for a_i, b_i in pinned:
            pa, pb = order.index(a_i), order.index(b_i)
            if pa > pb:
                order[pa], order[pb] = order[pb], order[pa]
        for seq, i in enumerate(order, 1):
            self.corr[i]["arrival_seq"] = seq

    # ----- finalize: lines, payments, posted
    def finalize(self, overpay_p, void_override=None):
        V = C.variant("")
        prices = {k: Decimal(v) for k, v in PRICES.items()}
        D = self.as_D(prices, with_corr=False)
        orig = C.original_timelines(D)
        for r in self.reg:
            a = r["account_id"]
            an, b = self.T[a]
            if r["status"] == "void":
                fa = (void_override or {}).get(r["invoice_id"], (1, "actual"))
                self.lines[r["invoice_id"]] = C.rate(orig[a], r["statement_month"], fa[0], fa[1], prices, V)
            else:
                self.lines[r["invoice_id"]] = C.rate(orig[a], r["statement_month"], an, b, prices, V)
        D = self.as_D(prices, with_corr=False)
        status = {r["invoice_id"]: r["status"] for r in self.reg}
        pays = {}

        def pay_fn(inv, due):
            if status[inv["invoice_id"]] != "paid":
                return Decimal(0)
            h = int(hashlib.sha256((self.extract_id + inv["invoice_id"]).encode()).hexdigest()[:8], 16)
            r2 = random.Random(h)
            extra = money(r2, 5, 60) if r2.random() < overpay_p else Decimal(0)
            pays[inv["invoice_id"]] = due + extra
            return due + extra
        _out, info = C.engine(D, V, fit_override=self.T, pay_fn=pay_fn)
        self.pays = pays
        self.posted = dict(info["trace"])
        for inv, line_idx, delta in self.alter:
            ln = list(self.lines[inv][line_idx])
            ln[3] = ln[3] + delta
            self.lines[inv][line_idx] = tuple(ln)

    def as_D(self, prices, with_corr=True):
        D = dict(extract_id=self.extract_id, first=self.first, last=self.last,
                 accounts={a["account_id"]: a for a in self.accounts}, prices=prices, ncyc=self.ncyc,
                 events=self.events, reg=self.reg, lines=self.lines, corr=self.corr if with_corr else [],
                 lots=self.lots, pays={},
                 transfers=[dict(t, posted=t["req"]) for t in self.transfers])
        return D

    # ----- writing
    def write(self, outd):
        os.makedirs(outd, exist_ok=True)
        P = lambda f: os.path.join(outd, f)
        accs = sorted(self.accounts, key=lambda a: a["account_id"])
        with open(P("accounts.json"), "w") as f:
            json.dump(dict(extract_id=self.extract_id, first_statement_month=self.first,
                           last_statement_month=self.last, accounts=accs), f, indent=2)
            f.write("\n")
        with open(P("price_book.json"), "w") as f:
            json.dump(dict(currency="USD", items=PRICES), f, indent=2)
            f.write("\n")
        with open(P("legacy_terms.yaml"), "w") as f:
            f.write("# Billing terms of the retired billing system.\n"
                    "# billing_terms.md and credit_policy.md supersede every key in this file\n"
                    "# except credit_expiry_cycles, which stays in force.\n"
                    "default_anchor_day: 1\ndefault_basis: actual\nrounding: half_up\n"
                    "credit_expiry_cycles: %d\n" % self.ncyc)
        ev = sorted(self.events, key=lambda e: (e["date"], e["event_id"]))
        with open(P("entitlement_events.jsonl"), "w") as f:
            for e in ev:
                f.write(json.dumps(e) + "\n")
        with open(P("invoice_register.tsv"), "w") as f:
            f.write("invoice_id\taccount_id\tstatement_month\tstatus\n")
            for r in sorted(self.reg, key=lambda r: r["invoice_id"]):
                f.write("%s\t%s\t%s\t%s\n" % (r["invoice_id"], r["account_id"], r["statement_month"], r["status"]))
        with open(P("invoice_lines.csv"), "w") as f:
            f.write("invoice_id,line_no,kind,item,quantity,amount\n")
            for iv in sorted(self.lines):
                for n, (kind, item, qty, amt) in enumerate(self.lines[iv], 1):
                    f.write("%s,%d,%s,%s,%d,%s\n" % (iv, n, kind, item, qty, C.s2(amt)))
        with open(P("corrections.json"), "w") as f:
            json.dump(sorted(self.corr, key=lambda c: (c["correction_id"], c["arrival_seq"])), f, indent=2)
            f.write("\n")
        with open(P("credit_lots.json"), "w") as f:
            json.dump(sorted(self.lots, key=lambda l: l["lot_id"]), f, indent=2)
            f.write("\n")
        acct_of = {r["invoice_id"]: r for r in self.reg}
        log = []
        for iv, amt in self.pays.items():
            if amt <= 0:
                continue
            r = acct_of[iv]
            day = self.S(r["account_id"], r["statement_month"])
            h = int(hashlib.sha256(iv.encode()).hexdigest()[:8], 16)
            r2 = random.Random(h)
            parts = [amt]
            if amt > 60 and r2.random() < 0.2:
                p1 = (amt * Decimal(r2.randint(30, 70)) / 100).quantize(C.CENT)
                parts = [p1, amt - p1]
            for k, p in enumerate(parts):
                pd = day + dt.timedelta(days=r2.randint(1, 20) + 3 * k)
                ts = "%sT%02d:%02d:%02dZ" % (pd.isoformat(), r2.randint(0, 23), r2.randint(0, 59), r2.randint(0, 59))
                log.append((ts, "PAYMENT invoice=%s account=%s amount=%s" % (iv, r["account_id"], C.s2(p))))
        for t in self.transfers:
            posted = self.posted.get(t["id"], Decimal(0))
            log.append((t["ts"], "TRANSFER transfer=%s from=%s to=%s requested=%s posted=%s" %
                        (t["id"], t["frm"], t["to"], C.s2(t["req"]), C.s2(posted))))
        log.sort()
        with open(P("ledger_activity.log"), "w") as f:
            for ts, msg in log:
                f.write("%s %s\n" % (ts, msg))


def fired(outd, ref):
    D = C.parse(outd)
    res = set()
    for k, v in VAR.items():
        out, _ = C.engine(D, C.variant(v))
        if out != ref:
            res.add(k)
    return res


def nonneg(ref):
    for name, doc in ref.items():
        if name.startswith("region_"):
            for a in doc["accounts"]:
                for i in a["invoices"]:
                    if Decimal(i["corrected_total"]) < 0 or Decimal(i["original_total"]) < 0:
                        return False
    return True


def build_hidden(rng, kind, k, tag):
    year = rng.choice([2025, 2026, 2027])
    if kind == "PA6":
        first = "%04d-%02d" % (year, rng.choice([10, 11, 12]))
        if int(first[5:]) >= 10:
            first = "%04d-%02d" % (year - 1 if year > 2025 else year, int(first[5:]))
            first = "%04d-%02d" % (2026, int(first[5:]))  # window covers Feb/Mar 2027 (non-leap)
    else:
        first = "%04d-%02d" % (year, rng.randint(1, 12))
    months = 6
    ncyc = rng.choice([2, 3]) if kind == "PS" else 12
    x = X(rng, first, months, ncyc, "EX-%s" % tag)
    ngroups = 3
    parents = [x.ids.new("PG", 4) for _ in range(ngroups)]
    accts = []
    for i in range(8):
        an, b = rng.randint(2, 28), rng.choice(["actual", "thirty"])
        accts.append(x.new_account(parents[i % ngroups], an, b, rng.randint(2, 4)))
    x.quiet = set()
    if k == 1 and kind not in ("PB1", "PB1b", "PB2"):
        x.quiet.add(x.new_account(rng.choice(parents), rng.randint(2, 28), rng.choice(["actual", "thirty"]), 0))
    x.add_invoices(0.08)
    for a in accts:
        x.random_lots(a, rng.randint(0, 2))
    target = accts[0]
    void_override, pinned, overpay = {}, [], 0.15
    # plants
    if kind == "PB1":
        x.events = [e for e in x.events if not (e["account_id"] == target and e["date"] > C.mstart(C.madd(first, -2), 1).isoformat())]
        if k == 1:
            x.random_change(target, x.S(target, x.last) + D1, x.E_last(target))
    elif kind == "PB1b":
        x.T[target] = (x.T[target][0], "actual")
        x.events = [e for e in x.events if not (e["account_id"] == target and e["date"] > C.mstart(C.madd(first, -2), 1).isoformat())]
        cyc30 = [C.madd(first, j) for j in range(-1, months - 2) if int(C.madd(first, j)[5:]) in (4, 6, 9, 11)]
        if not cyc30:
            return None
        for m in cyc30[:2]:
            lo, hi = x.S(target, m) + D1, x.S(target, C.madd(m, 1)) - D1
            x.random_change(target, lo, hi)
    elif kind == "PA2":
        sf1 = x.S(target, C.madd(first, 1))
        x.add_lot(target, money(rng, 300, 450), x.S(target, first) - dt.timedelta(days=30), sf1)
    elif kind == "PA6":
        x.T[target] = (x.T[target][0], "actual")
        feb = [C.madd(first, j) for j in range(0, months - 1) if C.madd(first, j)[5:] == "02"]
        if not feb:
            return None
        m = feb[0]
        s_next = x.S(target, C.madd(m, 1))
        r, dlt = rng.choice([(21, 1), (7, 3), (21, -1), (7, -3)])
        day = s_next - dt.timedelta(days=r)
        cur = x.q_orig(target, "SEAT-PRO", day)
        if cur + dlt < 0:
            dlt = -dlt
        x.events = [e for e in x.events if not (e["account_id"] == target and e["item"] == "SEAT-PRO" and e["date"] >= day.isoformat())]
        if k == 0:
            x.add_event(target, "SEAT-PRO", cur + dlt, day)
        else:
            x.add_correction(target, "SEAT-PRO", cur + dlt, day)
    for a in accts:
        if rng.random() < 0.3:
            x.accepted_correction(a)
    groups = {}
    for a in accts:
        groups.setdefault(x.T and [z for z in x.accounts if z["account_id"] == a][0]["parent_id"], []).append(a)
    for g, mem in groups.items():
        for _ in range(rng.randint(1, 2)):
            s, t = rng.sample(mem, 2)
            x.random_transfer(s, t)
    if kind == "PA1":
        m = C.madd(first, rng.randint(1, months - 1))
        day = x.S(target, m)
        item = rng.choice(["SEAT-STD", "USAGE-BLOCK"])
        x.events = [e for e in x.events if not (e["account_id"] == target and e["item"] == item and e["date"] >= day.isoformat())]
        x.corr = [c for c in x.corr if c["account_id"] != target]
        cur = x.q_orig(target, item, day)
        x.add_correction(target, item, cur + rng.choice([1, 2, 3]), day)
    elif kind == "PA3":
        mem = [a for a in groups[[z for z in x.accounts if z["account_id"] == target][0]["parent_id"]] if a != target]
        m = C.madd(first, rng.randint(1, months - 2))
        day = x.S(target, m)
        x.add_lot(target, money(rng, 60, 220), day - dt.timedelta(days=3), day + dt.timedelta(days=200))
        x.add_transfer(target, rng.choice(mem), day, money(rng, 30, 150))
    elif kind == "PA4":
        mem = [a for a in groups[[z for z in x.accounts if z["account_id"] == target][0]["parent_id"]] if a != target]
        x.corr = [c for c in x.corr if c["account_id"] != target]
        x.add_lot(target, money(rng, 250, 500), x.S(target, first) - dt.timedelta(days=20),
                  x.S(target, first) + dt.timedelta(days=330))
        m3 = C.madd(first, 3)
        tday = x.S(target, m3) + dt.timedelta(days=rng.randint(5, 20))
        item = "SEAT-STD"
        eff = x.S(target, first) + dt.timedelta(days=rng.randint(3, 12))
        x.events = [e for e in x.events if not (e["account_id"] == target and e["item"] == item and e["date"] >= eff.isoformat())]
        x.add_correction(target, item, x.q_orig(target, item, eff) + rng.randint(4, 8), eff)
        x.add_transfer(target, rng.choice(mem), tday, money(rng, 80, 300))
    elif kind == "PA5":
        x.corr = [c for c in x.corr if c["account_id"] != target]
        item = rng.choice(["SEAT-STD", "USAGE-BLOCK"])
        e1 = x.S(target, C.madd(first, 1)) + dt.timedelta(days=rng.randint(2, 9))
        e2 = x.S(target, C.madd(first, 3)) + dt.timedelta(days=rng.randint(2, 9))
        x.events = [e for e in x.events if not (e["account_id"] == target and e["item"] == item and e["date"] >= e1.isoformat())]
        cur = x.q_orig(target, item, e1)
        c1 = x.add_correction(target, item, cur + 2, e1)
        c2 = x.add_correction(target, item, cur + 4, e2)
        pinned.append((x.corr.index(c2), x.corr.index(c1)))
    elif kind == "PB2":
        pass
    elif kind == "PB3":
        m = C.madd(first, rng.randint(1, months - 2))
        vid = x.ids.new("IV", 6)
        x.reg.append(dict(invoice_id=vid, account_id=target, statement_month=m, status="void"))
        void_override[vid] = (1, "actual")
    elif kind == "PS":
        overpay = 0.7
    va = rng.choice(accts[1:])
    vm = C.madd(first, rng.randint(0, months - 2))
    x.reg.append(dict(invoice_id=x.ids.new("IV", 6), account_id=va, statement_month=vm, status="void"))
    if kind in ("PB1", "PB1b", "PB2", "PB3") and rng.random() < 0.8:
        pass
    if kind in ("PB1", "PB1b", "PB2"):
        x.accepted_correction(target)
        mem = [a for a in groups[[z for z in x.accounts if z["account_id"] == target][0]["parent_id"]] if a != target]
        x.random_transfer(mem[0], target)
    # rejection-path corrections (some)
    if rng.random() < 0.5:
        x.add_correction(x.ids.new("AC", 5), "SEAT-STD", 3, x.S(accts[1], first) + dt.timedelta(days=9))
    if rng.random() < 0.5:
        x.add_correction(accts[2], "SEAT-ENT", 2, x.S(accts[2], first) + dt.timedelta(days=11))
    if rng.random() < 0.5:
        a = accts[3]
        x.add_correction(a, "SEAT-STD", 4, x.S(a, first) - dt.timedelta(days=rng.randint(1, 25)))
    if rng.random() < 0.5 and x.corr:
        c0 = rng.choice(x.corr)
        x.add_correction(c0["account_id"], c0["item"], c0["quantity"] + 1, C.d(c0["effective_date"]), cid=c0["correction_id"])
        pinned.append((x.corr.index(c0), len(x.corr) - 1))
    x.number_arrivals(pinned)
    x.finalize(overpay, void_override)
    if kind == "PB2":
        paid = [r["invoice_id"] for r in x.reg if r["account_id"] == target and r["status"] == "paid"]
        iv = rng.choice(paid)
        li = rng.randrange(len(x.lines[iv]))
        ln = list(x.lines[iv][li])
        ln[3] += Decimal("0.01")
        x.lines[iv][li] = tuple(ln)
    return x, target


def check_hidden(x, target, kind, outd):
    x.write(outd)
    D = C.parse(outd)
    ref, info = C.engine(D, C.variant(""))
    if not nonneg(ref):
        return False, "negative"
    unres = {u["account_id"]: u for u in info["unresolved"]}
    for a in x.T:
        if (kind in ("PB1", "PB1b", "PB2") and a == target) or a in getattr(x, "quiet", ()):
            if a not in unres:
                return False, "target resolved"
            continue
        if a in unres or info["fit"][a] != x.T[a]:
            return False, "fit %s" % a
    f = fired(outd, ref)
    f.discard("fixed1")
    if "withvoid" not in f:
        return False, "no void witness"
    f -= {"withvoid", "all"}
    if getattr(x, "quiet", None):
        if not {"first", "best"} <= f:
            return False, "quiet account not witnessed"
        f -= {"first", "best"}
    if not MUST[kind] <= f:
        return False, "missing %s" % (MUST[kind] - f)
    if not f <= MUST[kind] | ALLOW.get(kind, set()):
        return False, "extra %s" % (f - MUST[kind] - ALLOW.get(kind, set()))
    return True, sorted(f)


def hidden(seed, outroot, kinds=KINDS, reps=2, quiet=False):
    report = []
    for kind in kinds:
        for k in range(reps):
            rng = random.Random("%s-%s-%d" % (seed, kind, k))
            for attempt in range(400):
                r = build_hidden(rng, kind, k, "%s%d%02d" % (kind, k, attempt))
                if r is None:
                    continue
                x, target = r
                outd = os.path.join(outroot, "h_%s_%d" % (kind, k))
                ok, why = check_hidden(x, target, kind, outd)
                if ok:
                    report.append((kind, k, attempt, why))
                    if not quiet:
                        print("OK", kind, k, "attempt", attempt, "fired", why, flush=True)
                    break
            else:
                print("FAIL", kind, k, why, flush=True)
                report.append((kind, k, None, why))
    return report


def shipped(seed, outd, n_acc=400, quiet=False):
    rng = random.Random("shipped-%s" % seed)
    x = X(rng, "2025-07", 12, 12, "EX-2025H2")
    parents = [x.ids.new("PG", 4) for _ in range(90)]
    prices = {k: Decimal(v) for k, v in PRICES.items()}
    V = C.variant("")
    for i in range(n_acc):
        for _try in range(50):
            ev_before = len(x.events)
            a = x.new_account(parents[i % len(parents)], 1, "actual", rng.randint(2, 5))
            D = dict(accounts={a: x.accounts[-1]}, events=x.events)
            orig = C.original_timelines(dict(D, accounts={a: x.accounts[-1]}))
            # quick unique-fit check on the paid months
            fits = 0
            for c in C.CANDS:
                good = True
                for kk in range(11):
                    m = C.madd(x.first, kk)
                    if C.rate(orig[a], m, c[0], c[1], prices, V) != C.rate(orig[a], m, 1, "actual", prices, V):
                        good = False
                        break
                fits += good
            if fits == 1:
                break
            x.accounts.pop()
            del x.T[a]
            x.events = x.events[:ev_before]
        else:
            raise RuntimeError("no unique account")
    accts = [a["account_id"] for a in x.accounts]
    x.add_invoices(0.05)
    for a in accts:
        x.random_lots(a, rng.choice([0, 0, 1, 1, 2]))
    for a in accts:
        if rng.random() < 0.12:
            x.accepted_correction(a)
    groups = {}
    for z in x.accounts:
        groups.setdefault(z["parent_id"], []).append(z["account_id"])
    for g, mem in groups.items():
        if len(mem) >= 2:
            for _ in range(rng.randint(1, 3)):
                s, t = rng.sample(mem, 2)
                x.random_transfer(s, t)
    gl = list(groups)
    for _ in range(6):
        s = rng.choice(groups[gl[0]])
        t = rng.choice(groups[gl[1]])
        x.random_transfer(s, t)
    for _ in range(4):
        x.random_transfer(rng.choice(accts), x.ids.new("AC", 5))
    for _ in range(5):
        x.add_correction(x.ids.new("AC", 5), "SEAT-STD", 3, C.d("2025-08-14"))
    for _ in range(5):
        a = rng.choice(accts)
        x.add_correction(a, "SEAT-ENT", 2, C.d("2025-09-%02d" % rng.randint(2, 28)))
    for _ in range(5):
        a = rng.choice(accts)
        x.add_correction(a, "SEAT-STD", 4, C.d("2025-06-%02d" % rng.randint(2, 28)))
    pinned = []
    for _ in range(5):
        c0 = rng.choice([c for c in x.corr if c["item"] != "SEAT-ENT"])
        x.add_correction(c0["account_id"], c0["item"], c0["quantity"] + 1, C.d(c0["effective_date"]), cid=c0["correction_id"])
        pinned.append((x.corr.index(c0), len(x.corr) - 1))
    x.number_arrivals(pinned)
    for _round in range(8):
        x.finalize(0.15)
        x.write(outd)
        D = C.parse(outd)
        ref, info = C.engine(D, C.variant(""))
        bad = {t for t, mv in info["trace"] if mv != x.posted.get(t, Decimal(0))}
        if not bad:
            break
        x.transfers = [t for t in x.transfers if t["id"] not in bad]
    assert not info["unresolved"], info["unresolved"][:3]
    assert nonneg(ref)
    f = fired(outd, ref)
    if not quiet:
        print("shipped fired:", sorted(f))
    return f


if __name__ == "__main__":
    a = sys.argv
    out = a[a.index("--out") + 1]
    if "--shipped" in a:
        n = int(a[a.index("--n") + 1]) if "--n" in a else 400
        shipped(a[a.index("--seed") + 1] if "--seed" in a else "731905", out, n)
    else:
        hidden(a[a.index("--hidden") + 1], out)
