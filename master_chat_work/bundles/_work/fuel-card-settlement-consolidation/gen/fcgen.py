"""Seeded stdlib generator for fuel-card settlement months.

generate(out_dir, seed, plants=(), full=True, shipped=False, docs=None)
writes ref/ and exports/ (and docs/ when docs is given) and returns a
manifest of planted quiet cases.
"""
import calendar
import json
import os
import random
from datetime import date, datetime, timedelta, timezone

PROCS = ["kestrel", "lumen", "marlow", "norvik", "oberon"]
REGIONS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "corporate", "enterprise", "smb"]
FORMATS = {"kestrel": ("csv", "csv"), "lumen": ("fixed-width", "txt"),
           "marlow": ("jsonl", "jsonl"), "norvik": ("xml", "xml"),
           "oberon": ("tsv", "tsv")}
LETTER = {"kestrel": "K", "lumen": "L", "marlow": "M", "norvik": "N", "oberon": "O"}
OFFSETS = ["-08:00", "-07:00", "-06:00", "-05:00", "-03:30", "+00:00",
           "+01:00", "+05:30", "+09:30", "+10:00"]
# code, kind, tax_class, unit, aliases kestrel/lumen/marlow/norvik/oberon
PRODUCTS = [
    ("ULP91", "fuel", "road_fuel", "litre", ["U91", "91", "ULP91", "REG", "0091"]),
    ("ULP95", "fuel", "road_fuel", "litre", ["U95", "95", "ULP95", "PREM", "0095"]),
    ("ULP98", "fuel", "road_fuel", "litre", ["PREM", "98", "ULP98", "SUPR", "0098"]),
    ("DSL", "fuel", "road_fuel", "litre", ["DSL", "D", "DIESEL", "DSL", "0050"]),
    ("DSLP", "fuel", "road_fuel", "litre", ["DSLP", "DP", "DIESELP", "DSLX", "0051"]),
    ("E85", "fuel", "road_fuel", "litre", ["E85", "E8", "E85", "ETH", "0085"]),
    ("LPG", "fuel", "gas_fuel", "litre", ["LPG", "LP", "AUTOGAS", "LPG", "0060"]),
    ("CNG", "fuel", "gas_fuel", "kg", ["CNG", None, "CNG", "METH", None]),
    ("ADBLUE", "nonfuel", "general", "litre", ["ADB", "AB", "ADBLUE", "DEF", "0070"]),
    ("LUBE", "nonfuel", "general", "each", ["OIL", "LU", "LUBE", "OIL", "0080"]),
    ("WASH", "nonfuel", "general", "each", ["WSH", "CW", "WASH", "WASH", "0081"]),
    ("SHOP", "nonfuel", "general", "each", ["SHP", "SH", "SHOP", "SHOP", "0082"]),
]
PROD = {p[0]: p for p in PRODUCTS}
ALIAS = {pr: {p[0]: p[4][i] for p in PRODUCTS if p[4][i]} for i, pr in enumerate(PROCS)}
FUEL_BASE = ["ULP91", "ULP95", "ULP98", "DSL", "DSLP", "E85", "LPG"]
NONFUEL = ["ADBLUE", "LUBE", "WASH", "SHOP"]
INCL = {"kestrel": True, "lumen": False, "marlow": False, "norvik": True, "oberon": True}
PUMP_TYPES = ["PT", "PX", "TST", "CAL", "PMP", "QA"]
LAYOUT_SHIPPED = [("batch", 6), ("txn", 8), ("line", 3), ("stamp", 10), ("site", 5),
                  ("card", 16), ("product", 6), ("quantity", 8), ("amount", 9),
                  ("sign", 1), ("ref", 20)]
LUMEN_NUMERIC = {"txn", "line", "quantity", "amount"}
LUMEN_FIXED = {"stamp", "site", "card", "sign"}
INI_TEXT = """; Fleet discount tiers and monthly caps.

[eligible]
segments = corporate, enterprise, smb

[tier.base]
floor_litres = 0
rate_per_litre = 0.000

[tier.bronze]
floor_litres = 400
rate_per_litre = 0.015

[tier.silver]
floor_litres = 1000
rate_per_litre = 0.025

[tier.gold]
floor_litres = 2500
rate_per_litre = 0.040

[tier.platinum]
floor_litres = 5000
rate_per_litre = 0.055

[cap]
smb = 150.00
corporate = 400.00
enterprise = 900.00
"""
QUIET = ["Q%d" % i for i in range(1, 16)]


def off_minutes(off):
    sign = -1 if off[0] == "-" else 1
    return sign * (int(off[1:3]) * 60 + int(off[4:6]))


def fmt3(milli):
    s = "-" if milli < 0 else ""
    m = abs(milli)
    return "%s%d.%03d" % (s, m // 1000, m % 1000)


def fmt2(cents):
    s = "-" if cents < 0 else ""
    c = abs(cents)
    return "%s%d.%02d" % (s, c // 100, c % 100)


class Gen:
    def __init__(self, seed, full, shipped, plants):
        self.rng = random.Random(seed)
        self.prng = random.Random(seed ^ 0x5A17)
        self.full = full
        self.shipped = shipped
        self.plants = set(plants)
        self.manifest = []
        r = self.rng
        if shipped:
            self.y, self.m = 2026, 9
            self.ho_offset = "+10:00"
            self.pump_type = "PT"
            self.layout = list(LAYOUT_SHIPPED)
            self.paths = {p: "exports/%s_settlement.%s" % (p, FORMATS[p][1]) for p in PROCS}
            self.home = {"kestrel": "north", "lumen": "east", "marlow": "south",
                         "norvik": "west", "oberon": "central"}
        else:
            self.y, self.m = r.randint(2025, 2029), r.randint(1, 12)
            self.ho_offset = r.choice([o for o in OFFSETS if o != "+00:00"])
            self.pump_type = r.choice(PUMP_TYPES)
            lay = list(LAYOUT_SHIPPED)
            r.shuffle(lay)
            self.layout = [(f, w if f in LUMEN_FIXED else w + r.randint(0, 3)) for f, w in lay]
            ym = "%04d%02d" % (self.y, self.m)
            style = r.random() < 0.5
            self.paths = {p: ("exports/%s_%s.%s" % (p, ym, FORMATS[p][1]) if style
                              else "exports/%s_settlement.%s" % (p, FORMATS[p][1])) for p in PROCS}
            self.home = {p: r.choice(REGIONS) for p in PROCS}
        self.ndays = calendar.monthrange(self.y, self.m)[1]
        self.mstart = date(self.y, self.m, 1)
        self.mend = date(self.y, self.m, self.ndays)
        self.t0 = datetime(self.y, self.m, 1, tzinfo=timezone.utc)
        self.nwin = (self.ndays + 2) // 3
        self.used_ids = {p: set() for p in PROCS}
        self.used_batch = {p: set() for p in PROCS}
        self.records = {p: [] for p in PROCS}
        self.log = []
        self.batch_open = {}
        self.file_rank = {}
        self.accounts = []   # (id, [(segment, eff)], closed_on)
        self.cards = []      # (card, acct, from, to)
        self.card_set = set()
        self.acct_set = set()
        self.tax_rows = []
        self.extra_tax = []

    # ---------- ids ----------
    def new_batch(self, p, rng):
        while True:
            b = "%s%d" % (LETTER[p], rng.randint(1000, 9999))
            if b not in self.used_batch[p]:
                self.used_batch[p].add(b)
                return b

    def new_src(self, p, rng, tender=1):
        while True:
            if p == "kestrel":
                s = str(rng.randint(1000000, 9999999))
            elif p == "lumen":
                s = "%d-%d" % (rng.randint(3000000, 8999999), rng.randint(1, 2))
            elif p == "marlow":
                s = str(rng.randint(100000000, 999999999))
            elif p == "norvik":
                s = str(rng.randint(200000, 999999))
            else:
                s = "%d/%d" % (rng.randint(5000000, 9999999), tender)
            key = s.split("/")[0] if p == "oberon" else (s.split("-")[0] if p == "lumen" else s)
            if key not in self.used_ids[p]:
                self.used_ids[p].add(key)
                return s

    def new_acct_id(self, rng):
        while True:
            a = "4%06d" % rng.randint(0, 999999)
            if a not in self.acct_set:
                self.acct_set.add(a)
                return a

    def new_card(self, rng):
        while True:
            c = "7%015d" % rng.randint(0, 10 ** 15 - 1)
            if c not in self.card_set:
                self.card_set.add(c)
                return c

    def d(self, day):
        return self.mstart + timedelta(days=day - 1)

    # ---------- reference data ----------
    def make_sites(self):
        r = self.rng
        n = 2400 if self.full else 300
        nj = 40 if self.full else 12
        self.jurs = ["JR%02d" % (i + 1) for i in range(nj)]
        ids = r.sample(range(10000, 100000), n)
        self.sites = []
        for i, s in enumerate(ids):
            off = OFFSETS[i % len(OFFSETS)] if i < len(OFFSETS) * 2 else r.choice(OFFSETS)
            self.sites.append((str(s), r.choice(REGIONS), off, r.choice(self.jurs)))
        self.site_by = {s[0]: s for s in self.sites}

    def make_tax(self):
        r = self.rng
        hist = 17 if self.full else 3
        for j in self.jurs:
            for cls in ("road_fuel", "gas_fuel", "general"):
                d0 = self.mstart - timedelta(days=r.randint(20, 400))
                rows = [d0]
                for _ in range(hist - 1):
                    rows.append(rows[-1] - timedelta(days=r.randint(60, 200)))
                for dd in rows:
                    self.tax_rows.append((j, cls, r.randint(10, 40) * 50, dd))
                if r.random() < 0.4:
                    fut = self.mend + timedelta(days=r.randint(1, 90))
                    self.tax_rows.append((j, cls, r.randint(10, 40) * 50, fut))

    def add_account(self, rng, seg_hist, closed_on=None, ncards=1, card_from=None, card_to=None):
        a = self.new_acct_id(rng)
        self.accounts.append((a, seg_hist, closed_on))
        cards = []
        for _ in range(ncards):
            c = self.new_card(rng)
            vf = card_from or (self.mstart - timedelta(days=rng.randint(30, 900)))
            self.cards.append((c, a, vf, card_to))
            cards.append(c)
        return a, cards

    def make_accounts(self):
        r = self.rng
        n = 1300 if self.full else 250
        self.active = []
        for _ in range(n):
            seg = r.choices(SEGMENTS, [4, 2, 1, 3])[0]
            hist = []
            k = r.choice([1, 1, 2, 3])
            dd = self.mstart - timedelta(days=r.randint(5, 200))
            hist.append((seg, dd))
            for _ in range(k - 1):
                dd = dd - timedelta(days=r.randint(30, 400))
                hist.append((r.choice(SEGMENTS), dd))
            u = r.random()
            if u < 0.05:
                closed = self.mstart - timedelta(days=r.randint(1, 300))
                a, cards = self.add_account(r, hist, closed, 1, card_to=closed)
                continue
            closed = None
            mid = False
            if u < 0.07:
                closed = self.d(r.randint(10, self.ndays - 3))
                mid = True
            a, cards = self.add_account(r, hist, closed, r.choice([1, 1, 2, 3]))
            for c in cards:
                if r.random() < 0.10:
                    other = r.choice(self.accounts)[0] if r.random() < 0.3 else None
                    prev = other or a
                    vt = self.mstart - timedelta(days=r.randint(40, 300))
                    self.cards.append((c, prev, vt - timedelta(days=r.randint(30, 300)), vt))
                    if other:
                        self.accounts.append((other, [(r.choice(SEGMENTS), vt - timedelta(days=500))], None))
                    # current row starts after previous ends
                    for i, row in enumerate(self.cards):
                        if row[0] == c and row[1] == a:
                            self.cards[i] = (c, a, vt + timedelta(days=1), None)
            self.active.append((a, seg, cards, closed if mid else None))
        # expired cards still used
        self.expired = []
        for _ in range(int(n * 0.04)):
            a, cards = self.add_account(r, [(r.choice(SEGMENTS), self.mstart - timedelta(days=700))],
                                        None, 1, card_to=self.mstart - timedelta(days=r.randint(1, 120)))
            self.expired.append(cards[0])

    # ---------- batches ----------
    def make_batches(self):
        r = self.rng
        self.win_batch = {}
        for pi, p in enumerate(PROCS):
            for w in range(self.nwin):
                b = self.new_batch(p, r)
                op = self.t0 + timedelta(days=3 * w, hours=1, minutes=7 * pi)
                self.win_batch[(p, w)] = b
                self.batch_open[(p, b)] = op
                self.log.append((op, p, b, "OPENED"))
                self.log.append((op + timedelta(days=3, hours=2), p, b, "CLOSED"))
        months = 20 if self.full else 2
        for k in range(1, months + 1):
            y, m = self.y, self.m - k
            while m <= 0:
                m += 12
                y -= 1
            t = datetime(y, m, 1, tzinfo=timezone.utc)
            nd = calendar.monthrange(y, m)[1]
            for pi, p in enumerate(PROCS):
                for w in range((nd + 2) // 3):
                    b = self.new_batch(p, r)
                    op = t + timedelta(days=3 * w, hours=1, minutes=7 * pi)
                    self.log.append((op, p, b, "OPENED"))
                    self.log.append((op + timedelta(days=3, hours=2), p, b, "CLOSED"))
                    if r.random() < 0.01:
                        self.log.append((op + timedelta(days=4), p, b,
                                         r.choice(["SUPERSEDED", "WITHDRAWN"])))

    def window(self, inst):
        w = (inst - self.t0).days // 3
        return min(self.nwin - 1, max(0, w))

    def extra_batch(self, p, after, rng):
        b = self.new_batch(p, rng)
        self.batch_open[(p, b)] = after
        self.log.append((after, p, b, "OPENED"))
        self.log.append((after + timedelta(hours=20), p, b, "CLOSED"))
        return b

    # ---------- records ----------
    def native(self, p, code, litres_milli=None, items=None, rng=None):
        """Return native quantity integer for processor p."""
        unit = PROD[code][3]
        if unit == "each":
            return items
        if unit == "kg":
            return litres_milli  # milli-kg passed directly
        if p in ("kestrel", "marlow"):
            return litres_milli
        if p == "oberon":
            return litres_milli
        if p == "lumen":
            return max(1, int(round(litres_milli / 37.85411784)))
        return max(1, int(round(litres_milli / 4.54609)))

    def amount_for(self, p, code, litres_milli, items, rng):
        kind = PROD[code][1]
        if kind == "fuel":
            price = rng.uniform(1.40, 2.30) if INCL[p] else rng.uniform(1.25, 2.05)
            return max(1, int(round(litres_milli / 1000.0 * price * 100)))
        if PROD[code][3] == "litre":
            return max(1, int(round(litres_milli / 1000.0 * rng.uniform(1.0, 2.5) * 100)))
        return items * rng.randint(200, 2000)

    def rec(self, p, kind, inst, site, card, code, rng, batch=None, src=None,
            litres_milli=None, items=None, amount=None, ref=None, alias=None, **extra):
        if litres_milli is None and PROD[code][3] != "each":
            litres_milli = rng.randint(5000, 90000)
        if items is None and PROD[code][3] == "each":
            items = rng.randint(1, 3)
        if p == "lumen":
            inst = inst.replace(second=0)
        q = self.native(p, code, litres_milli, items, rng)
        if amount is None:
            amount = self.amount_for(p, code, litres_milli, items, rng)
        if batch is None:
            w = self.window(inst)
            batch = self.win_batch[(p, w)]
            k = 1
            while getattr(self, "planting", False) and (p, batch) in self.dead_batches:
                batch = self.win_batch[(p, min(self.nwin - 1, max(0, w + (k if k % 2 else -k))))]
                k += 1
        if src is None:
            src = self.new_src(p, rng)
        r = {"p": p, "kind": kind, "inst": inst, "site": site, "card": card,
             "code": code, "alias": alias if alias is not None else ALIAS[p].get(code),
             "q": q, "amount": amount, "batch": batch, "src": src, "ref": ref,
             "lm": litres_milli}
        r.update(extra)
        self.records[p].append(r)
        return r

    def base_instant(self, rng):
        lo = self.t0 + timedelta(days=1, hours=12)
        hi = self.t0 + timedelta(days=self.ndays - 2, hours=12)
        return lo + timedelta(seconds=rng.randint(0, int((hi - lo).total_seconds())))

    def pick_proc(self, rng, exclude=()):
        return rng.choice([p for p in PROCS if p not in exclude])

    def make_lines(self):
        r = self.rng
        self.sales = []
        lines_rng = {"consumer": (1, 10), "smb": (2, 20), "corporate": (4, 45), "enterprise": (10, 120)}
        if not self.full:
            lines_rng = {"consumer": (1, 6), "smb": (2, 10), "corporate": (3, 25), "enterprise": (6, 60)}
        site_ids = [s[0] for s in self.sites]
        for a, seg, cards, closed in self.active:
            n = r.randint(*lines_rng[seg])
            for _ in range(n):
                p = r.choice(PROCS)
                inst = self.base_instant(r)
                site = r.choice(site_ids)
                if closed is not None:
                    off = off_minutes(self.site_by[site][2])
                    while (inst + timedelta(minutes=off)).date() > closed:
                        inst = self.base_instant(r)
                code = r.choice(FUEL_BASE) if r.random() < 0.8 else r.choice(NONFUEL)
                card = r.choice(cards)
                rec = self.rec(p, "S", inst, site, card, code, r)
                self.sales.append(rec)
                if p == "lumen" and r.random() < 0.15 and PROD[code][1] == "fuel":
                    txn = rec["src"].split("-")[0]
                    rec2 = self.rec(p, "S", inst, site, card, r.choice(NONFUEL), r,
                                    batch=rec["batch"], src="%s-%d" % (txn, 2 if rec["src"].endswith("-1") else 1))
                    self.sales.append(rec2)

    def make_rejections(self):
        r = self.rng
        site_ids = [s[0] for s in self.sites]
        base_cards = [c for (_, _, cs, cl) in self.active if cl is None for c in cs]
        n = len(self.sales)
        # pump tests
        for _ in range(int(n * 0.015)):
            p = self.pick_proc(r, ("norvik",))
            card = "0" * 16 if p == "lumen" else r.choice(base_cards)
            self.rec(p, "P", self.base_instant(r), r.choice(site_ids), card,
                     r.choice(FUEL_BASE), r, litres_milli=r.randint(1000, 20000))
        # unknown product via other processors' aliases
        for _ in range(max(3, int(n * 0.005))):
            p = r.choice(PROCS)
            own = set(ALIAS[p].values())
            foreign = sorted({v for q in PROCS if q != p for v in ALIAS[q].values()} - own)
            if p == "lumen":
                foreign = [v for v in foreign if len(v) <= 6]
            alias = r.choice(foreign)
            self.rec(p, "S", self.base_instant(r), r.choice(site_ids), r.choice(base_cards),
                     "ULP91", r, alias=alias)
        # unknown card
        for _ in range(int(n * 0.01)):
            card = r.choice(self.expired) if r.random() < 0.6 else self.new_card(r)
            self.rec(r.choice(PROCS), "S", self.base_instant(r), r.choice(site_ids), card,
                     r.choice(FUEL_BASE), r)
        # out of period (weeks before the month)
        for _ in range(int(n * 0.01)):
            inst = self.t0 - timedelta(days=r.randint(15, 40), hours=r.randint(0, 23))
            self.rec(r.choice(PROCS), "S", inst, r.choice(site_ids), r.choice(base_cards),
                     r.choice(FUEL_BASE), r, batch=None)
        # superseded batches (kestrel, lumen) resent; withdrawn norvik batch
        self.blocked = set()
        self.dead_batches = set()
        for p in ("kestrel", "lumen"):
            w = r.randint(1, self.nwin - 3)
            b = self.win_batch[(p, w)]
            close = self.batch_open[(p, b)] + timedelta(days=3, hours=2)
            nb = self.extra_batch(p, close + timedelta(days=1, minutes=PROCS.index(p)), r)
            self.log.append((close + timedelta(days=1) - timedelta(minutes=10), p, b, "SUPERSEDED"))
            self.dead_batches.add((p, b))
            for rec in [x for x in self.records[p] if x["batch"] == b]:
                cp = dict(rec)
                cp["batch"] = nb
                if r.random() < 0.3:
                    cp["amount"] = max(1, rec["amount"] + r.randint(-40, 40))
                self.records[p].append(cp)
                self.blocked.add((p, rec["src"]))
        w = r.randint(1, self.nwin - 2)
        b = self.win_batch[("norvik", w)]
        self.log.append((self.batch_open[("norvik", b)] + timedelta(days=4), "norvik", b, "WITHDRAWN"))
        self.dead_batches.add(("norvik", b))
        for rec in self.records["norvik"]:
            if rec["batch"] == b:
                self.blocked.add(("norvik", rec["src"]))
        clean = [s for s in self.sales if (s["p"], s["src"]) not in self.blocked]
        r.shuffle(clean)
        k = 0
        # same-processor reversals / marlow voids
        self.r43 = []
        for s in clean[: int(n * 0.03)]:
            k += 1
            s["touched"] = True
            rv = self.reverse(s, s["p"], r, same=True)
            if s["p"] in ("norvik", "oberon") and r.random() < 0.5:
                rv["ref"] = ""
                self.r43.append((rv, s))
        # duplicates in a later batch, different amount
        for s in clean[int(n * 0.03): int(n * 0.035)]:
            w = self.window(s["inst"])
            if w + 1 >= self.nwin:
                continue
            s["touched"] = True
            cp = dict(s)
            cp["batch"] = self.win_batch[(s["p"], w + 1)]
            cp["amount"] = s["amount"] + r.choice([-1, 1]) * r.randint(1, 50)
            self.records[s["p"]].append(cp)
        # orphan reversals naming ids that do not exist
        for _ in range(max(2, int(n * 0.003))):
            p = self.pick_proc(r, ("marlow",))
            ghost = self.new_src(p, r)
            self.rec(p, "R", self.base_instant(r), r.choice(site_ids), r.choice(base_cards),
                     r.choice(FUEL_BASE), r, ref=ghost)

    def reverse(self, s, p, rng, same=True, inst=None, batch=None, src=None):
        if inst is None:
            lim = self.t0 + timedelta(days=self.ndays - 2, hours=12)
            inst = min(lim, s["inst"] + timedelta(seconds=rng.randint(3600, 3 * 86400)))
            if inst <= s["inst"]:
                inst = s["inst"] + timedelta(seconds=60)
        ref = s["src"] if same else "%s:%s" % (s["p"], s["src"])
        if p == "marlow":
            return self.rec(p, "V", inst, s["site"], s["card"], s["code"], rng,
                            litres_milli=s["lm"], items=s["q"] if PROD[s["code"]][3] == "each" else None,
                            amount=s["amount"], ref=s["src"], batch=batch, src=src)
        items = s["q"] if PROD[s["code"]][3] == "each" else None
        amount = s["amount"] if (same or INCL[p] == INCL[s["p"]]) else int(round(s["amount"] * 1.1))
        return self.rec(p, "R", inst, s["site"], s["card"], s["code"], rng, litres_milli=s["lm"],
                        items=items, amount=amount, ref=ref, batch=batch, src=src)

    # ---------- quiet plants ----------
    def sites_with(self, pred):
        return [s[0] for s in self.sites if pred(s)]

    def plant(self):
        self.planting = True
        g = self.prng
        man = self.manifest
        site_ids = [s[0] for s in self.sites]

        def note(q, recs, text):
            man.append({"q": q, "lines": ["%s:%s" % (x["p"], x["src"]) for x in recs], "note": text})

        def acct(seg, ncards=1, hist=None, closed=None):
            h = hist or [(seg, self.mstart - timedelta(days=g.randint(10, 300)))]
            return self.add_account(g, h, closed, ncards)

        def mid(day, hour=12):
            return self.t0 + timedelta(days=day - 1, hours=hour, minutes=g.randint(0, 59))

        def fuel():
            return g.choice(["ULP91", "ULP95", "DSL", "DSLP"])

        if "Q1" in self.plants:
            a, (c,) = acct("corporate")
            neg = g.choice(self.sites_with(lambda s: s[2] in ("-06:00", "-07:00", "-08:00")))
            neg5 = g.choice(self.sites_with(lambda s: s[2] in ("-05:00", "-06:00", "-07:00", "-08:00")))
            pos = g.choice(self.sites_with(lambda s: s[2] in ("+10:00", "+09:30")))
            recs = []
            nxt = self.t0 + timedelta(days=self.ndays)
            for p in g.sample(["kestrel", "marlow", "norvik", "oberon"], 2):
                recs.append(self.rec(p, "S", self.t0 + timedelta(hours=3), neg, c, fuel(), g,
                                     batch=self.win_batch[(p, 0)]))
                recs.append(self.rec(p, "S", nxt + timedelta(hours=2, minutes=30), neg5, c, fuel(), g,
                                     batch=self.win_batch[(p, self.nwin - 1)]))
                recs.append(self.rec(p, "S", nxt - timedelta(hours=3), pos, c, fuel(), g,
                                     batch=self.win_batch[(p, self.nwin - 1)]))
                recs.append(self.rec(p, "S", self.t0 - timedelta(hours=4), pos, c, fuel(), g,
                                     batch=self.win_batch[(p, 0)]))
            p = g.choice(["kestrel", "norvik", "oberon"])
            s = self.rec(p, "S", mid(self.ndays - 2), pos, c, fuel(), g)
            rv = self.reverse(s, p, g, inst=nxt - timedelta(hours=3),
                              batch=self.win_batch[(p, self.nwin - 1)])
            recs += [s, rv]
            note("Q1", recs, "month boundary at site offset")
        if "Q2" in self.plants:
            for _ in range(2):
                a1, _ = acct(g.choice(["corporate", "enterprise"]))
                a2, _ = acct(g.choice(["smb", "corporate"]))
                c = self.new_card(g)
                cut = g.randint(11, self.ndays - 10)
                self.cards.append((c, a1, self.mstart - timedelta(days=g.randint(30, 400)), self.d(cut)))
                self.cards.append((c, a2, self.d(cut + 1), None))
                recs = []
                for k in range(g.randint(3, 5)):
                    day = g.randint(3, cut) if k % 2 == 0 else g.randint(cut + 1, self.ndays - 2)
                    recs.append(self.rec(g.choice(PROCS), "S", mid(day), g.choice(site_ids), c, fuel(), g))
                note("Q2", recs, "card passes between accounts mid-month")
        if "Q3" in self.plants:
            for _ in range(2):
                cut = g.randint(10, self.ndays - 8)
                old = g.choice(["consumer", "smb"])
                new = g.choice(["corporate", "enterprise"])
                hist = [(new, self.d(cut)), (old, self.mstart - timedelta(days=g.randint(30, 300)))]
                a, (c,) = acct(new, hist=hist)
                recs = []
                for k in range(g.randint(4, 6)):
                    day = g.randint(3, cut - 1) if k % 2 == 0 else g.randint(cut, self.ndays - 2)
                    recs.append(self.rec(g.choice(PROCS), "S", mid(day), g.choice(site_ids), c, fuel(), g))
                note("Q3", recs, "segment change mid-month")
        if "Q4" in self.plants:
            j = g.choice(self.jurs)
            cut = g.randint(12, self.ndays - 6)
            self.extra_tax.append((j, "road_fuel", g.randint(10, 40) * 50 + 25 * 0, self.d(cut)))
            a, (c,) = acct("corporate")
            js = self.sites_with(lambda s: s[3] == j)
            recs = []
            for k in range(4):
                day = g.randint(3, cut - 1) if k % 2 == 0 else g.randint(cut, self.ndays - 2)
                recs.append(self.rec(g.choice(PROCS), "S", mid(day), g.choice(js), c, fuel(), g))
            note("Q4", recs, "tax rate change mid-month for %s road_fuel" % j)
        if "Q5" in self.plants:
            for floor in (1000, 2500):
                a, (c,) = acct(g.choice(["corporate", "enterprise"]))
                total = floor * 1000
                parts = []
                while total > 90000:
                    v = g.randint(30000, 85000)
                    parts.append(v)
                    total -= v
                parts.append(total) if total >= 1000 else parts.__setitem__(-1, parts[-1] + total)
                recs = []
                for v in parts:
                    p = g.choice(["kestrel", "oberon", "marlow"])
                    recs.append(self.rec(p, "S", mid(g.randint(3, self.ndays - 2)), g.choice(site_ids),
                                         c, fuel(), g, litres_milli=v))
                note("Q5", recs, "tier volume exactly on floor %d" % floor)
        if "Q6" in self.plants:
            a, (c,) = acct("smb")
            recs = []
            for _ in range(66):
                recs.append(self.rec(g.choice(["kestrel", "marlow", "oberon", "norvik"]), "S",
                                     mid(g.randint(3, self.ndays - 3)), g.choice(site_ids), c, fuel(), g,
                                     litres_milli=g.randint(80000, 90000)))
            srt = sorted(recs, key=lambda x: x["inst"])
            for s in (srt[3], srt[-3]):
                if s["p"] != "marlow":
                    recs.append(self.reverse(s, s["p"], g))
            note("Q6", recs, "smb cap reached")
        if "Q7" in self.plants:
            a, (c,) = acct("enterprise")
            recs = []
            for src_p, rev_p in (("norvik", "kestrel"), ("lumen", "oberon"), ("kestrel", "norvik")):
                s = self.rec(src_p, "S", mid(g.randint(3, self.ndays - 6)), g.choice(site_ids), c, fuel(), g)
                recs += [s, self.reverse(s, rev_p, g, same=False)]
            note("Q7", recs, "cross-processor reversals")
        if "Q8" in self.plants:
            recs = []
            ghost = self.new_card(g)
            p = g.choice(["kestrel", "lumen", "norvik", "oberon"])
            s = self.rec(p, "S", mid(g.randint(3, self.ndays - 6)), g.choice(site_ids), ghost, fuel(), g)
            recs += [s, self.reverse(s, p, g)]
            a, (c,) = acct("corporate")
            p = g.choice(["kestrel", "norvik", "oberon"])
            s = self.rec(p, "S", self.t0 - timedelta(days=2), g.choice(site_ids), c, fuel(), g,
                         batch=self.win_batch[(p, 0)])
            recs += [s, self.reverse(s, p, g, inst=mid(3))]
            note("Q8", recs, "reversal of a rejected original")
        if "Q9" in self.plants:
            recs = []
            for _ in range(2):
                cl = g.randint(12, self.ndays - 6)
                a, (c,) = acct(g.choice(["corporate", "smb", "consumer"]), closed=self.d(cl))
                utc0 = self.sites_with(lambda s: s[2] in ("+00:00", "+01:00"))
                for day in (cl - 3, cl, cl + 1, cl + 3):
                    recs.append(self.rec(g.choice(PROCS), "S", mid(day), g.choice(utc0), c, fuel(), g))
            note("Q9", recs, "account closed mid-month")
        if "Q10" in self.plants:
            while True:
                p = g.choice(["lumen", "oberon", "kestrel"])
                w = g.randint(1, self.nwin - 2)
                b = self.win_batch[(p, w)]
                if (p, b) not in self.dead_batches:
                    break
            self.dead_batches.add((p, b))
            t = self.batch_open[(p, b)] + timedelta(days=4)
            self.log.append((t, p, b, "WITHDRAWN"))
            self.log.append((t + timedelta(hours=g.randint(2, 30)), p, b, "REINSTATED"))
            man.append({"q": "Q10", "lines": ["%s batch %s" % (p, b)], "note": "withdrawn then reinstated"})
        if "Q11" in self.plants:
            a, (c,) = acct(g.choice(["corporate", "enterprise"]))
            recs = []
            for p in ("kestrel", "marlow", "norvik", "kestrel", "norvik"):
                recs.append(self.rec(p, "S", mid(g.randint(3, self.ndays - 2)), g.choice(site_ids), c,
                                     "CNG", g, litres_milli=g.randint(4000, 25000)))
            note("Q11", recs, "CNG in kilograms")
        if "Q12" in self.plants:
            recs = []
            ms = [s for s in self.sales if s["p"] == "marlow" and (s["p"], s["src"]) not in self.blocked
                  and self.window(s["inst"]) < self.nwin - 1 and not s.get("touched")]
            for s in g.sample(ms, 2):
                s["touched"] = True
                nb = self.win_batch[("marlow", self.window(s["inst"]) + 1)]
                y = self.rec("marlow", "S", s["inst"], s["site"], s["card"], s["code"], g, batch=nb,
                             litres_milli=s["lm"], items=s["q"] if PROD[s["code"]][3] == "each" else None,
                             amount=s["amount"] + g.randint(5, 90), resub=s["src"])
                recs += [s, y]
            note("Q12", recs, "marlow resubmission")
        if "Q13" in self.plants:
            recs = []
            base_cards = [c for (_, _, cs, cl) in self.active if cl is None for c in cs]
            for _ in range(3):
                recs.append(self.rec("norvik", "S", mid(g.randint(3, self.ndays - 2)), g.choice(site_ids),
                                     g.choice(base_cards), fuel(), g, litres_milli=g.randint(5000, 20000),
                                     purpose="calibration"))
            note("Q13", recs, "norvik calibration")
        if "Q14" in self.plants:
            recs = []
            a1, (c1,) = acct("corporate")
            a2, (c2,) = acct(g.choice(["smb", "enterprise", "consumer"]))
            for _ in range(2):
                inst = mid(g.randint(3, self.ndays - 2))
                site = g.choice(site_ids)
                s1 = self.rec("oberon", "S", inst, site, c1, fuel(), g)
                txn = s1["src"].split("/")[0]
                s2 = self.rec("oberon", "S", inst, site, c2, fuel(), g, batch=s1["batch"], src=txn + "/2")
                recs += [s1, s2]
            note("Q14", recs, "oberon split tender")
        if "Q15" in self.plants:
            recs = []
            while True:
                p = g.choice(["kestrel", "norvik", "oberon", "lumen"])
                w = g.randint(1, self.nwin - 3)
                b = self.win_batch[(p, w)]
                cand = [s for s in self.sales if s["p"] == p and s["batch"] == b and not s.get("touched")
                        and (p, s["src"]) not in self.blocked]
                if (p, b) not in self.dead_batches and len(cand) >= 2:
                    break
            nb = self.extra_batch(p, self.batch_open[(p, b)] + timedelta(days=3, hours=5), g)
            self.file_rank[(p, nb)] = (p, b)
            for s in g.sample(cand, 2):
                s["touched"] = True
                cp = dict(s)
                cp["batch"] = nb
                cp["amount"] = s["amount"] + g.choice([-1, 1]) * g.randint(10, 300)
                self.records[p].append(cp)
                recs += [s, cp]
            note("Q15", recs, "duplicate whose later-opened copy comes first in the file")

        # ---------- unreferenced reversals (unique fit) ----------
        def has(code):
            return code in self.plants or (code[:2] == "U3" and "U3" in self.plants)

        def sale(p, day, c, code, lm, amt, hour=None, batch=None, src=None, site=None):
            h = g.randint(9, 13) if hour is None else hour
            return self.rec(p, "S", mid(day, h), site or g.choice(site_ids), c, code, g,
                            litres_milli=lm, amount=amt, batch=batch, src=src)

        def unref(p, day, c, code, lm, amt, hour=None, batch=None, src=None):
            h = g.randint(9, 13) if hour is None else hour
            return self.rec(p, "R", mid(day, h), g.choice(site_ids), c, code, g,
                            litres_milli=lm, amount=amt, ref="", batch=batch, src=src)

        def twin_args():
            p = g.choice(["norvik", "oberon"])
            lm = g.randint(20000, 80000)
            if p == "norvik":
                lm = int(round(round(lm / 4.54609) * 4.54609))
            amt = self.amount_for(p, "DSL", lm, None, g)
            return p, fuel(), lm, amt

        if has("U1"):
            recs = []
            for _ in range(2):
                a, (c,) = acct("corporate")
                p, code, lm, amt = twin_args()
                d = g.randint(7, self.ndays - 3)
                recs += [sale(p, d - 4, c, code, lm, amt), sale(p, d - 1, c, code, lm, amt),
                         unref(p, d, c, code, lm, amt)]
            note("U1", recs, "two sale lines fit an unreferenced reversal")
        if has("U2"):
            recs = []
            for _ in range(2):
                a, (c,) = acct("corporate")
                p, code, lm, amt = twin_args()
                d = g.randint(5, self.ndays - 3)
                s0 = sale(p, d - 2, c, code, lm, amt)
                srcs = sorted([self.new_src(p, g), self.new_src(p, g)])
                rb = unref(p, d, c, code, lm, amt, hour=9, src=srcs[1])
                ra = unref(p, d, c, code, lm, amt, hour=13, batch=rb["batch"], src=srcs[0])
                recs += [s0, rb, ra]
            note("U2", recs, "two unreferenced reversals on one day; ledger order decides")
        if has("U2r"):
            recs = []
            for _ in range(2):
                a, (c,) = acct("corporate")
                p, code, lm, amt = twin_args()
                d = g.randint(6, self.ndays - 3)
                s1 = sale(p, d - 3, c, code, lm, amt)
                s2 = sale(p, d - 2, c, code, lm, amt)
                ru = unref(p, d - 1, c, code, lm, amt)
                rr = self.rec(p, "R", mid(d, g.randint(9, 13)), g.choice(site_ids), c, code, g,
                              litres_milli=lm, amount=amt, ref=s1["src"])
                recs += [s1, s2, ru, rr]
            note("U2r", recs, "referenced reversal resolved before an earlier unreferenced one")
        if has("U3a"):
            recs = []
            a, (c,) = acct("corporate")
            p, code, lm, amt = twin_args()
            d = g.randint(8, self.ndays - 4)
            t = mid(d - 3, 9)
            b0 = self.extra_batch(p, t - timedelta(hours=2), g)
            s0 = sale(p, d - 3, c, code, lm, amt, hour=10, batch=b0)
            self.log.append((t + timedelta(days=1), p, b0, "SUPERSEDED"))
            self.dead_batches.add((p, b0))
            nb = self.extra_batch(p, t + timedelta(days=1, minutes=30), g)
            cp = dict(s0)
            cp["batch"] = nb
            cp["amount"] = amt + g.choice([-1, 1]) * g.randint(20, 200)
            self.records[p].append(cp)
            s1 = sale(p, d - 2, c, code, lm, amt)
            rv = unref(p, d, c, code, lm, amt)
            recs += [s0, cp, s1, rv]
            note("U3a", recs, "superseded copy would fit; resent copy differs")
        if has("U3b"):
            recs = []
            a, (c,) = acct("corporate")
            p, code, lm, amt = twin_args()
            d = g.randint(6, self.ndays - 4)
            s1 = sale(p, d - 2, c, code, lm, amt)
            nb = self.extra_batch(p, self.batch_open[(p, s1["batch"])] + timedelta(days=3, hours=5), g)
            self.file_rank[(p, nb)] = (p, s1["batch"])
            cp = dict(s1)
            cp["batch"] = nb
            cp["amount"] = amt + g.choice([-1, 1]) * g.randint(20, 200)
            self.records[p].append(cp)
            rv = unref(p, d, c, code, lm, cp["amount"])
            recs += [s1, cp, rv]
            note("U3b", recs, "only the rejected duplicate copy would fit")
        if has("U3c"):
            recs = []
            a, (c,) = acct("corporate")
            p, code, lm, amt = twin_args()
            s0 = self.rec(p, "S", self.t0 - timedelta(hours=12), g.choice(site_ids), c, code, g,
                          litres_milli=lm, amount=amt, batch=self.win_batch[(p, 0)])
            s1 = sale(p, 2, c, code, lm, amt)
            rv = unref(p, 4, c, code, lm, amt)
            recs += [s0, s1, rv]
            note("U3c", recs, "out-of-period twin would fit")
        if has("U4"):
            recs = []
            for _ in range(2):
                a, (c,) = acct("corporate")
                p, code, lm, amt = twin_args()
                d = g.randint(11, self.ndays - 4)
                recs += [sale(p, d - 8, c, code, lm, amt), sale(p, d - 3, c, code, lm, amt),
                         sale(p, d + 2, c, code, lm, amt), unref(p, d, c, code, lm, amt)]
            note("U4", recs, "twins outside the seven-day window")
        if has("U5"):
            recs = []
            cut = g.randint(6, self.ndays - 5)
            hx = [("corporate", self.mstart - timedelta(days=g.randint(10, 300)))]
            ax, (c,) = self.add_account(g, hx, None, 1, None, self.d(cut))
            ay, (cy,) = acct("corporate")
            self.cards.append((c, ay, self.d(cut + 1), None))
            p = "oberon"
            lm = 2 * g.randint(20000, 40000)
            amt = self.amount_for(p, "DSL", lm, None, g)
            code = fuel()
            sx = sale(p, cut - 1, c, code, lm, amt)
            sy = sale(p, cut + 1, c, code, lm, amt)
            ru = unref(p, cut + 2, c, code, lm, amt)
            rr = self.rec(p, "R", mid(cut + 3, g.randint(9, 13)), g.choice(site_ids), c, code, g,
                          litres_milli=lm, amount=amt, ref=sx["src"])
            recs += [sx, sy, ru, rr]
            for card, total, lo, hi in ((c, 1000000 + lm // 2, 2, cut - 1), (cy, 1000000 - lm // 2, 2, self.ndays - 2)):
                while total > 0:
                    v = min(total, g.randint(30000, 85000))
                    if 0 < total - v < 1000:
                        v = total
                    recs.append(self.rec(g.choice(["kestrel", "marlow"]), "S", mid(g.randint(lo, hi)),
                                         g.choice(site_ids), card, fuel(), g, litres_milli=v))
                    total -= v
            note("U5", recs, "unreferenced reversal across a card reassignment near a tier floor")
        if has("Q16"):
            recs = []
            j = "JR%02d" % (len(self.jurs) + 1)
            self.jurs.append(j)
            cut = g.randint(12, 16)
            for cls in ("road_fuel", "gas_fuel", "general"):
                self.tax_rows.append((j, cls, g.randint(10, 40) * 50, self.mstart - timedelta(days=g.randint(20, 300))))
            old_rate = [t for t in self.tax_rows if t[0] == j and t[1] == "road_fuel"][0][2]
            new_rate = old_rate
            while new_rate == old_rate:
                new_rate = g.randint(10, 40) * 50
            self.extra_tax.append((j, "road_fuel", new_rate, self.d(cut)))
            sites = []
            for _ in range(2):
                while True:
                    sid = str(g.randint(10000, 99999))
                    if sid not in self.site_by:
                        break
                st = (sid, g.choice(REGIONS), g.choice(OFFSETS), j)
                self.sites.insert(g.randint(0, len(self.sites)), st)
                self.site_by[sid] = st
                sites.append(sid)
            a, (c,) = acct("corporate")
            for p in (g.choice(["kestrel", "norvik", "oberon"]), "lumen"):
                s = self.rec(p, "S", mid(g.randint(3, cut - 2)), g.choice(sites), c,
                             g.choice(["ULP91", "ULP95", "DSL"]), g)
                recs += [s, self.reverse(s, p, g, inst=mid(g.randint(cut + 1, self.ndays - 2)))]
            note("Q16", recs, "reversal dated after a tax change of %s road_fuel" % j)

        # ---------- unreferenced base reversals must fit exactly one line ----------
        for rv, s in self.r43:
            key = (s["card"], s["alias"], s["q"], s["amount"])
            n_fit = sum(1 for x in self.records[s["p"]]
                        if x["kind"] == "S" and (x["card"], x["alias"], x["q"], x["amount"]) == key)
            if n_fit != 1:
                rv["ref"] = s["src"]
        self.check_stated_cases()

    def check_stated_cases(self):
        accts = {a for a, _, _ in self.accounts}
        first_seg = {a: min(e for _, e in h) for a, h, _ in self.accounts}
        for c, a, _, _ in self.cards:
            assert a in accts, ("card account missing", c)
        taxes = {}
        for j, cls, _, dd in self.tax_rows + self.extra_tax:
            taxes[(j, cls)] = min(dd, taxes.get((j, cls), dd))
        y, m = self.y, self.m
        for p in PROCS:
            for x in self.records[p]:
                assert x["site"] in self.site_by, ("unknown site", p, x["src"])
                ld = self.site_local(x["inst"], x["site"]).date()
                if (ld.year, ld.month) != (y, m) or x["kind"] not in ("S", "R"):
                    continue
                if x["code"] in PROD and x["alias"] == ALIAS[p].get(x["code"]):
                    cls = PROD[x["code"]][2]
                    j = self.site_by[x["site"]][3]
                    assert taxes.get((j, cls)) is not None and taxes[(j, cls)] <= ld, ("tax before first row", p, x["src"])
                for c, a, vf, vt in self.cards:
                    if c == x["card"] and vf <= ld and (vt is None or ld <= vt):
                        assert first_seg[a] <= ld, ("segment before first row", p, x["src"])

    # ---------- rendering ----------
    def ordered(self, p):
        opened = {}
        for (pp, b), t in self.batch_open.items():
            if pp == p:
                opened[b] = t
        def key(r):
            b = r["batch"]
            t = opened[b]
            if (p, b) in self.file_rank:
                t = opened[self.file_rank[(p, b)][1]] - timedelta(seconds=1)
            return (t, r["inst"], r["src"])
        return sorted(self.records[p], key=key)

    def site_local(self, inst, site):
        return inst + timedelta(minutes=off_minutes(self.site_by[site][2]))

    def render(self, out):
        r = self.rng
        os.makedirs(os.path.join(out, "exports"), exist_ok=True)
        # kestrel
        rows = ["batch,txn_id,type,timestamp,site,card,product,quantity,amount,orig_txn"]
        for x in self.ordered("kestrel"):
            t = {"S": "SALE", "R": "REV", "P": self.pump_type}[x["kind"]]
            q = str(x["q"]) if PROD[x["code"]][3] == "each" else fmt3(x["q"])
            rows.append(",".join([x["batch"], x["src"], t, x["inst"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  x["site"], x["card"], x["alias"], q, fmt2(x["amount"]),
                                  x["ref"] or ""]))
        self.write(out, self.paths["kestrel"], "\n".join(rows) + "\n")
        # lumen
        rows = []
        for x in self.ordered("lumen"):
            txn, line = x["src"].split("-")
            vals = {"batch": x["batch"], "txn": txn, "line": line,
                    "stamp": self.site_local(x["inst"], x["site"]).strftime("%y%m%d%H%M"),
                    "site": x["site"], "card": x["card"], "product": x["alias"], "quantity": str(x["q"]),
                    "amount": str(x["amount"]), "sign": "-" if x["kind"] == "R" else " ",
                    "ref": x["ref"] or ""}
            parts = []
            for f, w in self.layout:
                v = vals[f]
                assert len(v) <= w, (f, v, w)
                parts.append(v.rjust(w, "0") if f in LUMEN_NUMERIC else v.ljust(w))
            rows.append("".join(parts))
        self.write(out, self.paths["lumen"], "\n".join(rows) + "\n")
        # marlow
        rows = []
        ho = off_minutes(self.ho_offset)
        for x in self.ordered("marlow"):
            q = str(x["q"]) if PROD[x["code"]][3] == "each" else fmt3(x["q"])
            o = {"batch": x["batch"], "id": x["src"], "kind": "void" if x["kind"] == "V" else "sale",
                 "at": (x["inst"] + timedelta(minutes=ho)).strftime("%Y-%m-%d %H:%M:%S"),
                 "site": x["site"], "card": x["card"], "product": x["alias"], "quantity": q,
                 "amount": fmt2(x["amount"]), "test": x["kind"] == "P"}
            if x["kind"] == "V":
                o["voids"] = x["ref"]
            if x.get("resub"):
                o["resubmission_of"] = x["resub"]
            rows.append(json.dumps(o))
        self.write(out, self.paths["marlow"], "\n".join(rows) + "\n")
        # norvik
        rows = ['<?xml version="1.0" encoding="UTF-8"?>', '<settlement processor="norvik">']
        for x in self.ordered("norvik"):
            off = r.choice(OFFSETS)
            lt = x["inst"] + timedelta(minutes=off_minutes(off))
            neg = "-" if x["kind"] == "R" else ""
            q = str(x["q"]) if PROD[x["code"]][3] == "each" else fmt3(x["q"])
            purpose = x.get("purpose") or r.choice(["retail", "fleet"])
            rows.append('  <record batch="%s" id="%s">' % (x["batch"], x["src"]))
            rows.append("    <time>%s%s</time>" % (lt.strftime("%Y-%m-%dT%H:%M:%S"), off))
            rows.append("    <site>%s</site>" % x["site"])
            rows.append("    <card>%s</card>" % x["card"])
            rows.append("    <product>%s</product>" % x["alias"])
            rows.append("    <quantity>%s%s</quantity>" % (neg, q))
            rows.append("    <amount>%s%s</amount>" % (neg, fmt2(x["amount"])))
            rows.append("    <purpose>%s</purpose>" % purpose)
            if x["kind"] == "R":
                rows.append("    <reverses>%s</reverses>" % (x["ref"] or ""))
            rows.append("  </record>")
        rows.append("</settlement>")
        self.write(out, self.paths["norvik"], "\n".join(rows) + "\n")
        # oberon
        rows = ["\t".join(["batch", "txn_id", "tender", "entry", "epoch", "site", "card", "product",
                           "ml", "amount_cents", "ref"])]
        for x in self.ordered("oberon"):
            txn, tender = x["src"].split("/")
            rows.append("\t".join([x["batch"], txn, tender, {"S": "S", "R": "R", "P": "T"}[x["kind"]],
                                   str(int(x["inst"].timestamp())), x["site"], x["card"], x["alias"],
                                   str(x["q"]), str(x["amount"]), x["ref"] or ""]))
        self.write(out, self.paths["oberon"], "\n".join(rows) + "\n")
        # reference files
        procs = []
        for p in PROCS:
            o = {"name": p, "export": self.paths[p], "format": FORMATS[p][0], "home_region": self.home[p]}
            if p == "marlow":
                o["head_office_offset"] = self.ho_offset
            if p == "kestrel":
                o["pump_test_type"] = self.pump_type
            if p == "lumen":
                lay, col = [], 1
                for f, w in self.layout:
                    lay.append({"field": f, "start": col, "width": w})
                    col += w
                o["layout"] = lay
            procs.append(o)
        self.write(out, "ref/processors.json", json.dumps(
            {"settlement_month": "%04d-%02d" % (self.y, self.m), "processors": procs}, indent=2) + "\n")
        self.write(out, "ref/sites.csv", "site_id,region,utc_offset,jurisdiction\n" +
                   "".join("%s,%s,%s,%s\n" % s for s in self.sites))
        cards = list(self.cards)
        r.shuffle(cards)
        self.write(out, "ref/cards.csv", "card_number,account_id,valid_from,valid_to\n" + "".join(
            "%s,%s,%s,%s\n" % (c, a, f.isoformat(), t.isoformat() if t else "") for c, a, f, t in cards))
        arows = []
        for a, hist, closed in self.accounts:
            for seg, eff in hist:
                arows.append("%s,%s,%s,%s\n" % (a, seg, eff.isoformat(), closed.isoformat() if closed else ""))
        r.shuffle(arows)
        self.write(out, "ref/accounts.csv", "account_id,segment,effective_from,closed_on\n" + "".join(arows))
        x = ['<?xml version="1.0" encoding="UTF-8"?>', "<catalogue>"]
        for code, kind, cls, unit, al in PRODUCTS:
            x.append('  <product code="%s" kind="%s" tax_class="%s" unit="%s">' % (code, kind, cls, unit))
            for i, p in enumerate(PROCS):
                if al[i]:
                    x.append('    <alias processor="%s" code="%s"/>' % (p, al[i]))
            x.append("  </product>")
        x.append("</catalogue>")
        self.write(out, "ref/products.xml", "\n".join(x) + "\n")
        self.write(out, "ref/discount_tiers.ini", INI_TEXT)
        trows = self.tax_rows + self.extra_tax
        trows = [t for t in trows]
        r.shuffle(trows)
        self.write(out, "ref/tax_rates.tsv", "jurisdiction\ttax_class\trate\teffective_from\n" + "".join(
            "%s\t%s\t0.%04d\t%s\n" % (j, c, rate, d.isoformat()) for j, c, rate, d in trows))
        log = sorted(self.log, key=lambda e: (e[0], e[1], e[2]))
        self.write(out, "ref/batches.log", "".join(
            "%s %s %s %s\n" % (t.strftime("%Y-%m-%dT%H:%M:%SZ"), p, b, ev) for t, p, b, ev in log))

    def write(self, out, rel, text):
        path = os.path.join(out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def generate(out_dir, seed, plants=(), full=True, shipped=False, docs=None):
    g = Gen(seed, full, shipped, plants)
    g.make_sites()
    g.make_tax()
    g.make_accounts()
    g.make_batches()
    g.make_lines()
    g.make_rejections()
    g.plant()
    g.render(out_dir)
    if docs:
        for rel, text in docs.items():
            g.write(out_dir, rel, text)
    return {"month": "%04d-%02d" % (g.y, g.m), "plants": g.manifest}


if __name__ == "__main__":
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "..", "docs_src")
    docs = {}
    for fn in sorted(os.listdir(src)):
        with open(os.path.join(src, fn), encoding="utf-8") as fh:
            docs["docs/" + fn] = fh.read()
    out, seed = sys.argv[1], int(sys.argv[2])
    plants = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else ()
    full = "--small" not in sys.argv
    shipped = "--shipped" in sys.argv
    print(json.dumps(generate(out, seed, plants, full, shipped, docs), indent=1))
