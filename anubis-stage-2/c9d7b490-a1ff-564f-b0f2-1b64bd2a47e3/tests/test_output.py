"""Checks for the Halvard lease scorecard backtest.

Every expected value is recomputed here: the shipped extract and the held-out
extracts are regenerated from seed constants and settled by an independent
model of the rules. The delivered program is run on them unprivileged with a
time limit. A negative check holds when the shortcut it names happened, and its
negative weight does the punishing; every negative check is False when the
artifacts are missing.
"""
from rewardkit import criteria, criterion

# ---- corpus generator (shared by the shipped extract and the held-out tiers) ----
import json as _json
from datetime import date as _date, datetime as _dt, timedelta as _td, timezone as _tz
from pathlib import Path as _Path

_UTC = _tz.utc
G_REGIONS = ("North", "South", "West", "East")
G_RCODE = {"North": "N", "South": "S", "West": "W", "East": "E"}
G_STD = {"North": -360, "South": -300, "West": -480, "East": -240}
G_HAS_DST = {"North": True, "South": True, "West": True, "East": False}
G_DST_DAYS = {2022: ((3, 13), (11, 6)), 2023: ((3, 12), (11, 5)), 2024: ((3, 10), (11, 3)),
              2025: ((3, 9), (11, 2)), 2026: ((3, 8), (11, 1)), 2027: ((3, 14), (11, 7))}
G_COMM_SECTORS = ("23", "31", "42", "44", "48", "51", "52", "54", "56", "72")
G_PUB_SECTORS = ("92", "61", "62")
G_SECTOR_CLASS = {"23": "C", "31": "B", "42": "B", "44": "C", "48": "D", "51": "A", "52": "A",
                  "54": "B", "56": "D", "72": "E", "92": "A", "61": "A", "62": "B"}


class GRng:
    def __init__(self, seed):
        self.s = (seed * 0x9E3779B97F4A7C15 + 0x632BE59BD9B4E019) & 0xFFFFFFFFFFFFFFFF or 1

    def nxt(self):
        x = self.s
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= x >> 7
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
        self.s = x & 0xFFFFFFFFFFFFFFFF
        return self.s

    def below(self, n):
        return self.nxt() % n

    def randint(self, a, b):
        return a + self.below(b - a + 1)

    def chance(self, num, den):
        return self.below(den) < num

    def choice(self, seq):
        return seq[self.below(len(seq))]

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            j = self.below(i + 1)
            seq[i], seq[j] = seq[j], seq[i]


def g_iso(t):
    return t.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def g_dim(y, m):
    if m == 12:
        return 31
    return (_date(y, m + 1, 1) - _date(y, m, 1)).days


def g_month_add(y, m, k):
    i = y * 12 + (m - 1) + k
    return i // 12, i % 12 + 1


def g_dst_periods(region):
    out = []
    if not G_HAS_DST[region]:
        return out
    std = G_STD[region]
    for y in sorted(G_DST_DAYS):
        (sm, sd), (em, ed) = G_DST_DAYS[y]
        start = _dt(y, sm, sd, 2, tzinfo=_UTC) - _td(minutes=std)
        end = _dt(y, em, ed, 2, tzinfo=_UTC) - _td(minutes=std + 60)
        out.append((start, end))
    return out


_G_DST_CACHE = {}


def g_offset(region, t):
    if region not in _G_DST_CACHE:
        _G_DST_CACHE[region] = g_dst_periods(region)
    for a, b in _G_DST_CACHE[region]:
        if a <= t < b:
            return G_STD[region] + 60
    return G_STD[region]


def g_local_to_utc(region, d, hh, mm, ss):
    naive = _dt(d.year, d.month, d.day, hh, mm, ss, tzinfo=_UTC)
    t = naive - _td(minutes=G_STD[region])
    off = g_offset(region, t)
    t = naive - _td(minutes=off)
    if g_offset(region, t) != off:
        t = naive - _td(minutes=g_offset(region, t))
    return t


def g_local_date(region, t):
    return (t + _td(minutes=g_offset(region, t))).date()


def g_nth_weekday(y, m, wd, n):
    d = _date(y, m, 1)
    while d.weekday() != wd:
        d += _td(days=1)
    return d + _td(days=7 * (n - 1))


def g_last_weekday(y, m, wd):
    d = _date(y, m, g_dim(y, m))
    while d.weekday() != wd:
        d -= _td(days=1)
    return d


def g_observed(d):
    if d.weekday() == 5:
        return d - _td(days=1)
    if d.weekday() == 6:
        return d + _td(days=1)
    return d


def g_holidays(years):
    """List of (uid, date, summary, regions, status)."""
    out = []
    for y in years:
        common = [("New Year", g_observed(_date(y, 1, 1))), ("Memorial Day", g_last_weekday(y, 5, 0)),
                  ("Independence Day", g_observed(_date(y, 7, 4))), ("Labor Day", g_nth_weekday(y, 9, 0, 1)),
                  ("Thanksgiving", g_nth_weekday(y, 11, 3, 4)), ("Christmas", g_observed(_date(y, 12, 25)))]
        for name, d in common:
            out.append(("%s-%d" % (name.replace(" ", ""), y), d, name, list(G_REGIONS), "CONFIRMED"))
        out.append(("Founders-%d" % y, g_nth_weekday(y, 10, 0, 2), "Founders Day", ["North"], "CONFIRMED"))
        out.append(("Heritage-%d" % y, g_nth_weekday(y, 1, 0, 3), "Heritage Day", ["South", "East"], "CONFIRMED"))
        out.append(("Harvest-%d" % y, g_observed(_date(y, 3, 31)), "Harvest Day", ["West"], "CONFIRMED"))
        out.append(("Civic-%d" % y, g_nth_weekday(y, 8, 0, 1), "Civic Holiday", ["East"], "CONFIRMED"))
        out.append(("Harbour-%d" % y, g_last_weekday(y, 6, 4), "Harbour Day", ["West", "South"],
                    "CANCELLED" if y % 2 == 0 else "CONFIRMED"))
        out.append(("Yearend-%d" % y, g_observed(_date(y, 12, 31)), "Year End Close", ["North", "South"],
                    "CANCELLED"))
    return out


def g_business_day_fn(hols):
    sets = {r: set() for r in G_REGIONS}
    for _uid, d, _s, regions, status in hols:
        if status == "CONFIRMED":
            for r in regions:
                sets[r].add(d)

    def is_bd(region, d):
        return d.weekday() < 5 and d not in sets[region]
    return is_bd


def g_roll(is_bd, region, d, modified):
    f = d
    while not is_bd(region, f):
        f += _td(days=1)
    if modified and f.month != d.month:
        f = d
        while not is_bd(region, f):
            f -= _td(days=1)
    return f


def g_schedule(lease, holiday, is_bd, region, modified):
    """Final due dates (index 1..term). holiday is (months, first_k) or None."""
    y, m = lease["start"].year, lease["start"].month
    out = [None]
    for k in range(1, lease["term"] + 1):
        shift = holiday[0] if holiday and k >= holiday[1] else 0
        yy, mm = g_month_add(y, m, k + shift)
        nominal = _date(yy, mm, min(lease["anchor"], g_dim(yy, mm)))
        out.append(g_roll(is_bd, region, nominal, modified))
    return out


def g_fmt_dollars(c):
    return "%d.%02d" % (c // 100, c % 100)


def g_lease_ref(rng, n):
    f = rng.below(10)
    if f < 5:
        return "HL-%06d" % n
    if f < 7:
        return "HL%06d" % n
    if f < 8:
        return "hl-%06d" % n
    if f < 9:
        return "HL %d" % n
    return "Hl-%d" % n


def g_obl_ref(rng, n):
    f = rng.below(8)
    if f < 5:
        return "OB-%05d" % n
    if f < 6:
        return "ob%05d" % n
    if f < 7:
        return "OB %d" % n
    return "OB-%d" % n


def g_tax_fmt(rng, t):
    f = rng.below(3)
    if f == 0:
        return "%s-%s" % (t[:2], t[2:])
    if f == 1:
        return t
    return "%s %s" % (t[:2], t[2:])


def g_branch_fmt(rng, region, b):
    code = "%sB%02d" % (G_RCODE[region], b)
    f = rng.below(10)
    if f < 5:
        return code
    if f < 7:
        return "%sb-%02d" % (G_RCODE[region].lower(), b)
    if f < 8:
        return "%s-%02d" % (G_RCODE[region], b)
    if f < 9:
        return "%s %d" % (region.upper(), b)
    return "%sB%d" % (G_RCODE[region], b)


def generate(root, seed, n_leases=2400, n_obligors=2050, first_start=_date(2023, 1, 1), last_start=_date(2025, 6, 30),
             first_snapshot=_date(2025, 1, 1), snapshot_count=12, step_months=1, performance_days=180,
             bad_dpd=60, data_cutoff=_date(2026, 3, 31), tol=(2500, 10000), surcharge=250,
             v7_index=6, notices_until=_date(2024, 6, 30), run_id="HEF-BT-2025", log_year=2024,
             bureau_max_age=180, lease_base=0, obl_base=0, write=True):
    rng = GRng(seed)
    root = _Path(root)
    if write:
        root.mkdir(parents=True, exist_ok=True)
    files = {}
    watermark = _dt(data_cutoff.year, data_cutoff.month, data_cutoff.day, tzinfo=_UTC) + _td(days=1, hours=9)
    years = list(range(first_start.year - 1, data_cutoff.year + 2))
    hols = g_holidays(years)
    is_bd = g_business_day_fn(hols)
    snapshots = []
    for i in range(snapshot_count):
        y, m = g_month_add(first_snapshot.year, first_snapshot.month, i * step_months)
        snapshots.append(_date(y, m, min(first_snapshot.day, g_dim(y, m))))
    cuts = {(s, r): g_local_to_utc(r, s, 6, 0, 0) for s in snapshots for r in G_REGIONS}
    log_snaps = [_date(log_year, m, 1) for m in range(1, 13)]
    log_cuts = {(s, r): g_local_to_utc(r, s, 6, 0, 0) for s in log_snaps for r in G_REGIONS}

    def rdate(a, b):
        return a + _td(days=rng.below((b - a).days + 1))

    def at(d, hh=None):
        h = rng.randint(8, 20) if hh is None else hh
        return _dt(d.year, d.month, d.day, h, rng.below(60), rng.below(60), tzinfo=_UTC)

    late_pool = []

    def late(t, num=3, den=1000):
        if rng.chance(num, den):
            return watermark + _td(days=rng.randint(1, 40), seconds=rng.below(80000))
        return t

    # ---- obligors -------------------------------------------------------------------------
    n_obl = n_obligors
    taxes = set()
    obligors = []
    for i in range(1, n_obl + 1):
        while True:
            t = "%09d" % rng.randint(100000000, 999999999)
            if t not in taxes:
                taxes.add(t)
                break
        public = rng.chance(26, 100)
        risk = rng.below(1000)
        obligors.append({"n": obl_base + i, "id": "OB-%05d" % (obl_base + i), "tax": t, "public": public, "risk": risk,
                         "sector": rng.choice(G_PUB_SECTORS if public else G_COMM_SECTORS),
                         "created": rdate(first_start - _td(days=900), first_start - _td(days=30)),
                         "wrong_tax": None, "leases": []})
    # tax id corrections
    for o in obligors:
        if rng.chance(4, 100):
            t = o["tax"]
            w = t[:3] + t[4] + t[3] + t[5:]
            if w != t and w not in taxes:
                o["wrong_tax"] = w

    # ---- leases ---------------------------------------------------------------------------
    leases = []
    oi = 0
    order = list(range(n_obl))
    rng.shuffle(order)
    span = (last_start - first_start).days
    for n in range(1, n_leases + 1):
        if oi < len(order) and (rng.chance(80, 100) or n < n_obl // 2):
            ob = obligors[order[oi]]
            oi += 1
        else:
            ob = obligors[rng.below(n_obl)]
        start = first_start + _td(days=rng.below(span + 1))
        if rng.chance(30, 100):
            anchor = rng.choice((28, 29, 30, 31, 31, 30))
        else:
            anchor = start.day
        region = rng.choice(G_REGIONS)
        lease = {"n": lease_base + n, "id": "HL-%06d" % (lease_base + n), "ob": ob, "start": start, "term": rng.choice((24, 36, 36, 48)),
                 "inst": rng.randint(300, 9000) * 100 + rng.below(100), "anchor": anchor,
                 "region": region, "branch": rng.randint(1, 5), "risk": min(999, max(0, ob["risk"] + rng.randint(-150, 150))),
                 "channel": rng.choice(("LOCKBOX", "LOCKBOX", "ACH", "ACH", "ACH", "CARD")),
                 "ghost_obligor": None}
        if rng.chance(1, 100):
            lease["ghost_obligor"] = obl_base + n_obl + 500 + n
        ob["leases"].append(lease)
        leases.append(lease)
    # obligors created after their first lease started (data entry lag)
    for o in obligors:
        if o["leases"] and rng.chance(3, 100):
            first = min(l["start"] for l in o["leases"])
            if first < first_snapshot - _td(days=200):
                o["created"] = max(first + _td(days=rng.randint(60, 240)), o["created"])
            else:
                o["created"] = first + _td(days=rng.randint(20, 90))
    for o in obligors:
        o["created_at"] = at(o["created"])

    # register (public status over time)
    for o in obligors:
        o["listed"] = None
        o["delisted"] = None
        if o["public"]:
            o["listed"] = rdate(_date(2008, 1, 1), _date(2020, 12, 31))
            if rng.chance(5, 100):
                o["listed"] = rdate(first_snapshot, first_snapshot + _td(days=250))
            elif rng.chance(4, 100):
                o["delisted"] = rdate(first_snapshot, first_snapshot + _td(days=300))

    def public_on(o, d):
        return o["listed"] is not None and o["listed"] <= d and (o["delisted"] is None or d < o["delisted"])

    for l in leases:
        l["contract_public"] = (l["ghost_obligor"] is None) and public_on(l["ob"], l["start"])

    # ---- merges ---------------------------------------------------------------------------
    merges = []
    absorbed = set()
    for o in obligors:
        if len(merges) > n_obl * 7 // 100:
            break
        if rng.chance(8, 100) and o["n"] < obl_base + n_obl - 5:
            tgt = rng.randint(o["n"] + 1, min(obl_base + n_obl, o["n"] + 400))
            if o["n"] in absorbed:
                continue
            eff = rdate(first_snapshot - _td(days=240), first_snapshot + _td(days=300))
            rec = at(eff + _td(days=rng.randint(0, 25)))
            if rng.chance(18, 100):
                rec = at(eff + _td(days=rng.randint(40, 160)))
            merges.append((o["n"], tgt, eff, rec))
            absorbed.add(o["n"])

    # ---- branch history, events, relief --------------------------------------------------
    branch_rows = []
    events = []
    relief_rows = []
    ev_n = [0]

    def ev(lease_ref, typ, eff, rec, version=1, eid=None):
        if eid is None:
            ev_n[0] += 1
            eid = "EV-%07d" % ev_n[0]
        events.append({"event_id": eid, "version": version, "lease_ref": lease_ref, "type": typ,
                       "effective_date": eff.isoformat(), "recorded_at": g_iso(rec)})
        return eid

    for l in leases:
        rec = at(l["start"] + _td(days=rng.randint(0, 2)))
        if rng.chance(2, 100):
            rec = at(first_snapshot + _td(days=rng.randint(10, 200)))
        branch_rows.append([g_branch_fmt(rng, l["region"], l["branch"]), l, l["start"], rec])
        l["report_changes"] = []
        if rng.chance(12, 100):
            nr = rng.choice(G_REGIONS) if rng.chance(60, 100) else l["region"]
            eff = rdate(first_snapshot - _td(days=200), first_snapshot + _td(days=320))
            if eff > l["start"] + _td(days=30):
                rec2 = at(eff + _td(days=rng.randint(0, 8)))
                if rng.chance(15, 100):
                    rec2 = at(eff + _td(days=rng.randint(40, 120)))
                branch_rows.append([g_branch_fmt(rng, nr, rng.randint(1, 5)), l, eff, late(rec2)])

    sr_n = [0]
    rq_n = [0]

    def relief(req, l, status, months, k, t):
        sr_n[0] += 1
        relief_rows.append(["RS-%06d" % sr_n[0], req, l["ref_r"], status, months, k, t])

    # payment holiday requests (final truth stored on lease)
    for l in leases:
        l["ref_r"] = g_lease_ref(rng, l["n"])
        l["holiday"] = None
        end_term = _date(*g_month_add(l["start"].year, l["start"].month, l["term"]), 1)
        if not rng.chance(44, 100):
            continue
        reqs = 2 if rng.chance(10, 100) else 1
        for _ in range(reqs):
            lo = l["start"] + _td(days=90)
            hi = min(end_term - _td(days=120), data_cutoff - _td(days=90))
            if hi <= lo:
                break
            t0 = at(rdate(lo, hi))
            rq_n[0] += 1
            req = "RQ-%05d" % rq_n[0]
            months = rng.randint(1, 3)
            # first deferred instalment: first nominal due at least 15 days after approval
            ta = t0 + _td(days=rng.randint(2, 9), hours=rng.randint(0, 5))
            k = 1
            while True:
                yy, mm = g_month_add(l["start"].year, l["start"].month, k)
                if _date(yy, mm, min(l["anchor"], g_dim(yy, mm))) >= ta.date() + _td(days=15):
                    break
                k += 1
            if k > l["term"] - 1:
                break
            relief(req, l, "REQUESTED", months, k, t0)
            x = rng.below(100)
            if x < 60:
                relief(req, l, "APPROVED", months, k, ta)
                if rng.chance(10, 100):
                    relief(req, l, "WITHDRAWN", months, k, ta + _td(days=rng.randint(1, 5)))
                elif l["holiday"] is None or ta < l["holiday"][2]:
                    l["holiday"] = (months, k, ta, req)
            elif x < 92:
                relief(req, l, "DECLINED", months, k, ta)
                if rng.chance(8, 100):
                    relief(req, l, "APPROVED", months, k, ta + _td(days=rng.randint(1, 6)))
            # else pending forever
    # only the holiday stored on the lease counts; recompute: earliest approved & not withdrawn
    # (generator decided at most one per lease above)

    # ---- schedules ----------------------------------------------------------------------
    for l in leases:
        hol = (l["holiday"][0], l["holiday"][1]) if l["holiday"] else None
        l["due"] = g_schedule(l, hol, is_bd, l["region"], l["contract_public"])

    # ---- payments -----------------------------------------------------------------------
    payments = []  # dicts
    tolc = tol[1]

    def pay(l, v, cents, channel=None):
        payments.append({"lease": l, "v": v, "cents": cents, "ch": channel or l["channel"]})

    for l in leases:
        r = l["risk"]
        due = l["due"]
        term = l["term"]
        prof = "prompt" if r < 560 else ("slack" if r < 820 else "distressed")
        short = rng.chance(16, 100)
        buyout_k = rng.randint(10, max(11, term - 2)) if rng.chance(5, 100) else None
        stop_k = rng.randint(3, max(4, term - 1)) if prof == "distressed" and rng.chance(70, 100) else None
        stop_len = rng.randint(2, 8) if stop_k else 0
        l["close"] = None
        l["chargeoff"] = None
        owed = 0
        k = 1
        while k <= term:
            d = due[k]
            if d > data_cutoff:
                break
            if buyout_k and k == buyout_k:
                v = d - _td(days=rng.randint(0, 10))
                if v <= data_cutoff:
                    remaining = (term - k + 1) * l["inst"] + owed
                    pay(l, v, remaining)
                    l["close"] = ("BUYOUT", v)
                break
            if stop_k and stop_k <= k < stop_k + stop_len:
                owed += l["inst"]
                if stop_len >= 4 and k == stop_k + 3:
                    co = due[stop_k] + _td(days=rng.randint(110, 150))
                    if co <= data_cutoff:
                        l["chargeoff"] = co
                        break
                k += 1
                continue
            amount = l["inst"] + owed
            owed = 0
            if short and rng.chance(70, 100):
                amount -= rng.randint(100, 1400)
            if prof == "prompt":
                v = d - _td(days=rng.randint(0, 4)) if not rng.chance(7, 100) else d + _td(days=rng.randint(2, 20))
            elif prof == "slack":
                v = d - _td(days=rng.randint(0, 3)) if not rng.chance(28, 100) else d + _td(days=rng.randint(5, 48))
            else:
                v = d + _td(days=rng.randint(0, 35)) if rng.chance(60, 100) else d - _td(days=rng.randint(0, 2))
            if short and rng.chance(12, 100):
                amount += rng.randint(2, 6) * 1000
            if v <= data_cutoff:
                pay(l, v, amount)
            k += 1
        if l["close"] is None and l["chargeoff"] is None and k > term:
            v = due[term] + _td(days=rng.randint(0, 10))
            if v <= data_cutoff:
                l["close"] = ("PAYOFF", v)

    # ---- lease events --------------------------------------------------------------------
    ev_rows = []
    for l in leases:
        rec = at(l["start"] + _td(days=rng.randint(0, 3)))
        if rng.chance(1, 100):
            rec = at(first_snapshot + _td(days=rng.randint(5, 150)))
        ev(l["ref_r"] if rng.chance(30, 100) else l["id"], "ACTIVATE", l["start"], late(rec))
        if l["close"]:
            typ, d = l["close"]
            rec = at(d + _td(days=rng.randint(1, 6)))
            if rng.chance(10, 100):
                rec = at(d + _td(days=rng.randint(30, 100)))
            eid = ev(l["id"], typ, d + (_td(days=rng.randint(3, 20)) if rng.chance(5, 100) else _td(0)), late(rec))
            if events[-1]["effective_date"] != d.isoformat():
                ev(l["id"], typ, d, rec + _td(days=rng.randint(5, 30)), version=2, eid=eid)
        if l["chargeoff"]:
            d = l["chargeoff"]
            rec = at(d + _td(days=rng.randint(1, 10)))
            if rng.chance(15, 100):
                rec = at(d + _td(days=rng.randint(30, 90)))
            eid = ev(l["id"], "CHARGE_OFF", d, late(rec))
            if rng.chance(8, 100):
                ev(l["id"], "BUYOUT", d + _td(days=rng.randint(5, 40)), rec + _td(days=rng.randint(40, 60)))
        if l["close"] is None and l["chargeoff"] is None and rng.chance(2, 100):
            d = rdate(max(l["start"] + _td(days=200), first_snapshot - _td(days=60)), data_cutoff - _td(days=30))
            if d > l["start"]:
                eid = ev(l["id"], "BUYOUT", d, at(d + _td(days=2)))
                ev(l["id"], "VOID", d, at(d + _td(days=rng.randint(10, 70))), version=2, eid=eid)
        if rng.chance(1, 100):
            ev(l["id"], "ACTIVATE", l["start"] + _td(days=rng.randint(1, 60)), at(l["start"] + _td(days=rng.randint(61, 90))))
    for _ in range(max(12, n_leases // 300)):
        ev("HL-%06d" % (lease_base + n_leases + rng.randint(1, 5000)), "ACTIVATE", rdate(first_start, last_start), at(rdate(first_start, last_start)))

    # ---- payment records ------------------------------------------------------------------
    lockbox = {r: [] for r in G_REGIONS}
    card = []
    ledger = []
    returns = []
    p_n = [0]
    lb_n = {r: 0 for r in G_REGIONS}
    au_n = [0]
    rt_n = [0]
    notice_inv = {}
    inv_n = [0]
    for l in leases:
        for k in range(1, l["term"] + 1):
            d = l["due"][k]
            if d is None or d > notices_until:
                continue
            inv_n[0] += 1
            notice_inv[(l["n"], k)] = "INV-%07d" % inv_n[0]

    for p in payments:
        l = p["lease"]
        reg = l["region"]
        v = p["v"]
        ch = p["ch"]
        if rng.chance(8, 100):
            ch = rng.choice(("LOCKBOX", "ACH", "CARD"))
        p["ch"] = ch
        p_n[0] += 1
        pid = "PST-%07d" % p_n[0]
        p["pid"] = pid
        if ch == "ACH":
            posted = g_local_to_utc(reg, v, rng.randint(16, 23), rng.below(60), rng.below(60))
            ledger.append({"posting_id": pid, "lease_id": l["id"], "channel": "ACH", "source_ref": "ACH-%s" % pid[4:],
                           "amount": p["cents"], "posted_at": g_iso(late(posted, 2))})
            p["recs"] = [("ledger", posted)]
        elif ch == "LOCKBOX":
            lb_n[reg] += 1
            item = "LBX-%s-%07d" % (G_RCODE[reg], lb_n[reg])
            k_guess = None
            ref = l["ref_r"] if rng.chance(50, 100) else g_lease_ref(rng, l["n"])
            for k in range(1, l["term"] + 1):
                if l["due"][k] and abs((l["due"][k] - v).days) <= 20:
                    k_guess = k
                    break
            if k_guess and (l["n"], k_guess) in notice_inv and rng.chance(35, 100):
                ref = notice_inv[(l["n"], k_guess)]
            rec = at(v + _td(days=1), rng.randint(12, 17))
            amt = g_fmt_dollars(p["cents"])
            line = [item, ref, amt, v.isoformat(), g_iso(late(rec, 2))]
            lockbox[reg].append(line)
            led_amt = p["cents"]
            if rng.chance(2, 100):
                led_amt = p["cents"] + rng.choice((-900, -90, 90, 900))
            posted = at(v + _td(days=rng.randint(0, 3)), rng.randint(13, 22))
            ledger.append({"posting_id": pid, "lease_id": l["id"], "channel": "LOCKBOX",
                           "source_ref": item.replace("-", "").lower(), "amount": led_amt, "posted_at": g_iso(late(posted, 2))})
            p["recs"] = [("lockbox", rec), ("ledger", posted)]
            p["item"] = item
            if rng.chance(12, 1000):
                newv = v + _td(days=rng.choice((-2, -1, 1, 2, 3)))
                newc = p["cents"] + rng.choice((0, 0, -500, 500))
                lockbox[reg].append([item, ref, g_fmt_dollars(newc), newv.isoformat(), g_iso(rec + _td(days=rng.randint(1, 6)))])
            elif rng.chance(5, 1000):
                bad = rng.choice(("%d.%d" % (p["cents"] // 100, (p["cents"] % 100) // 10), "%d.%02d0" % (p["cents"] // 100, p["cents"] % 100), "-%s" % amt))
                line[2] = bad
        else:
            au_n[0] += 1
            auth = "AU%08d" % (au_n[0] * 7 + rng.below(7))
            rec = at(v + _td(days=1), rng.randint(5, 9))
            amt = g_fmt_dollars(p["cents"] + surcharge)
            line = [auth, l["ref_r"] if rng.chance(60, 100) else g_lease_ref(rng, l["n"]), amt, v.isoformat(), g_iso(late(rec, 2))]
            card.append(line)
            posted = at(v + _td(days=rng.randint(0, 2)), rng.randint(9, 23))
            ledger.append({"posting_id": pid, "lease_id": l["id"], "channel": "CARD", "source_ref": auth.lower(),
                           "amount": p["cents"], "posted_at": g_iso(late(posted, 2))})
            p["recs"] = [("card", rec), ("ledger", posted)]
            p["auth"] = auth
            if rng.chance(5, 1000):
                line[2] = "%d.%d" % ((p["cents"] + surcharge) // 100, ((p["cents"] + surcharge) % 100) // 10)
        # returns
        if ch in ("ACH", "CARD") and rng.chance(60 if ch == "ACH" else 12, 1000):
            rt_n[0] += 1
            posted = p["recs"][-1][1]
            rt = posted + _td(days=rng.randint(2, 6), hours=rng.randint(0, 9))
            returns.append([g_iso(late(rt, 2)), "RT-%06d" % rt_n[0], pid, rng.choice(("R01", "R01", "R02", "R03", "R09"))])
            # borrower repays later
            if rng.chance(70, 100):
                nv = v + _td(days=rng.randint(8, 30))
                if nv <= data_cutoff:
                    p_extra = {"lease": l, "v": nv, "cents": p["cents"], "ch": ch}
                    payments.append(p_extra)
        elif rng.chance(12, 1000):
            rt_n[0] += 1
            posted = p["recs"][-1][1]
            returns.append([g_iso(posted + _td(days=rng.randint(1, 4))), "RT-%06d" % rt_n[0], pid, rng.choice(("C01", "C02", "C05"))])
    for _ in range(max(12, len(returns) // 150)):
        rt_n[0] += 1
        returns.append([g_iso(at(rdate(first_start, data_cutoff))), "RT-%06d" % rt_n[0], "PST-%07d" % (p_n[0] + rng.randint(10, 99999)), "R01"])
    # unapplied cash and unknown refs
    for r in G_REGIONS:
        for _ in range(max(12, len(lockbox[r]) // 250)):
            lb_n[r] += 1
            d = rdate(first_start, data_cutoff)
            lockbox[r].append(["LBX-%s-%07d" % (G_RCODE[r], lb_n[r]), rng.choice(("UNAPPLIED", "HL-%06d" % (lease_base + n_leases + rng.randint(1, 900)), "INV-9%06d" % rng.below(999999), "REF %d" % rng.below(99999))),
                               g_fmt_dollars(rng.randint(10000, 900000)), d.isoformat(), g_iso(at(d + _td(days=1)))])
    for _ in range(max(12, len(card) // 250)):
        au_n[0] += 1
        d = rdate(first_start, data_cutoff)
        card.append(["AU%08d" % (au_n[0] * 7), "HL-%06d" % (lease_base + n_leases + rng.randint(1, 900)), g_fmt_dollars(rng.randint(10000, 500000)), d.isoformat(), g_iso(at(d + _td(days=1)))])

    # ---- bureau ---------------------------------------------------------------------------
    kr_rows = []
    nd_rows = []
    pulls = []
    pk = [0]
    pn = [0]
    for o in obligors:
        d = rdate(first_start - _td(days=500), first_start + _td(days=60))
        base_kr = 830 - o["risk"] * 45 // 100
        while d <= data_cutoff:
            vendors = ["KR"] if rng.chance(55, 100) else ["ND"]
            if rng.chance(6, 100):
                vendors = ["KR", "ND"]
            for vnd in vendors:
                kr = max(300, min(850, base_kr + rng.randint(-45, 45)))
                rec = at(d + _td(days=rng.randint(0, 3)), rng.randint(9, 18))
                if rng.chance(6, 100):
                    rec = at(d + _td(days=rng.randint(20, 75)))
                rec = late(rec, 2)
                stat = rng.below(100)
                if vnd == "KR":
                    pk[0] += 1
                    pid = "KR-%07d" % pk[0]
                    st, sc = ("OK", kr)
                    if stat < 3:
                        st, sc = ("NOHIT", None)
                    elif stat < 6:
                        st, sc = ("THIN", None)
                    kr_rows.append({"pull_id": pid, "tax_id": g_tax_fmt(rng, o["tax"]), "pulled_on": d.isoformat(),
                                    "recorded_at": g_iso(rec), "status": st, "score": sc})
                else:
                    pn[0] += 1
                    pid = "ND-%07d" % pn[0]
                    tenths = (kr - 300) * 100 // 55
                    res, sc = ("HIT", "%d.%d" % (tenths // 10, tenths % 10))
                    if stat < 3:
                        res, sc = ("NOHIT", "")
                    elif stat < 6:
                        res, sc = ("HIT", "")
                    elif stat < 7:
                        res, sc = ("HIT", "0.0")
                    nd_rows.append([pid, "%s-%s" % (o["tax"][:2], o["tax"][2:]), d.isoformat(),
                                    rec.strftime("%Y-%m-%d %H:%M:%S+00:00"), res, sc])
                pulls.append((pid, vnd, d, rec))
            d += _td(days=rng.randint(55, 190))
    disputes = []
    for pid, vnd, d, rec in pulls:
        if rng.chance(15, 1000):
            disputes.append({"pull_id": pid, "vendor": vnd, "recorded_at": g_iso(rec + _td(days=rng.randint(15, 90)))})

    # ---- limits ---------------------------------------------------------------------------
    lim_rows = []
    ln = [0]
    for o in obligors:
        exp = sum(l["inst"] * l["term"] for l in o["leases"]) or 3000000
        d = o["created"] + _td(days=rng.randint(0, 20))
        lim = max(10, exp * rng.randint(70, 160) // 100 // 100000)
        while d <= data_cutoff:
            ln[0] += 1
            rec = at(d + _td(days=rng.randint(0, 4)))
            if rng.chance(10, 100):
                rec = at(d + _td(days=rng.randint(30, 90)))
            val = str(lim)
            x = rng.below(100)
            if x < 4:
                val = ""
            elif x < 6:
                val = "0"
            lim_rows.append(["CL-%06d" % ln[0], g_obl_ref(rng, o["n"]), val, d.isoformat(), g_iso(late(rec, 2))])
            if rng.chance(2, 100):
                ln[0] += 1
                lim_rows.append(["CL-%06d" % ln[0], g_obl_ref(rng, o["n"]), str(max(10, lim * rng.randint(80, 130) // 100)), d.isoformat(), g_iso(rec + _td(hours=rng.randint(1, 30)))])
            lim = max(10, lim * rng.randint(75, 140) // 100)
            d += _td(days=rng.randint(150, 420))

    # ---- boundary planting at cut instants ----------------------------------------------
    by_region_lb = {r: [] for r in G_REGIONS}
    for r in G_REGIONS:
        for line in lockbox[r]:
            by_region_lb[r].append(line)
    card_by_region = {r: [] for r in G_REGIONS}
    lease_by_auth = {}
    for p in payments:
        if p.get("auth"):
            lease_by_auth[p["auth"]] = p["lease"]
    for line in card:
        l = lease_by_auth.get(line[0])
        if l:
            card_by_region[l["region"]].append(line)
    all_cuts = sorted(set(list(cuts.items()) + list(log_cuts.items())), key=lambda x: (x[1], x[0][1]))
    for (s, r), cut in all_cuts:
        cands = [x for x in by_region_lb[r] if s - _td(days=25) <= _date.fromisoformat(x[3]) < s and x[1] != "UNAPPLIED"]
        cands += [x for x in card_by_region[r] if s - _td(days=25) <= _date.fromisoformat(x[3]) < s]
        rng.shuffle(cands)
        npl = 34 if s in log_snaps else 14
        for i, x in enumerate(cands[:npl]):
            delta = (0, 0, 0, 1, -1, 0, 2, -2, 0, rng.randint(-890, 890))[i % 10]
            x[4] = g_iso(cut + _td(seconds=delta))

    # ---- write files ----------------------------------------------------------------------
    def put(name, text):
        files[name] = text
        if write:
            (root / name).write_text(text, encoding="utf-8")

    def csv_text(header, rows):
        out = [",".join(header)]
        for row in rows:
            out.append(",".join("" if c is None else str(c) for c in row))
        return "\n".join(out) + "\n"

    def protect(rows, plain=None):
        """Shuffle, then keep the first 50 rows to records that fire no rule."""
        rows = list(rows)
        rng.shuffle(rows)
        if plain is None:
            return rows
        head = []
        rest = []
        for x in rows:
            if len(head) < 50 and plain(x):
                head.append(x)
            else:
                rest.append(x)
        return head + rest

    snap_lines = ["[run]", 'run_id = "%s"' % run_id, 'first_snapshot = "%s"' % first_snapshot.isoformat(),
                  "snapshot_count = %d" % snapshot_count, "snapshot_step_months = %d" % step_months,
                  "performance_days = %d" % performance_days, "bad_dpd = %d" % bad_dpd,
                  'data_cutoff = "%s"' % data_cutoff.isoformat(), 'watermark_utc = "%s"' % g_iso(watermark),
                  'cut_local_time = "06:00:00"', 'notices_through = "%s"' % notices_until.isoformat()]
    put("backtest_run.toml", "\n".join(snap_lines) + "\n")

    ck = ["; Local clocks of the four servicing regions. Offsets are minutes east of UTC.",
          "; daylight_periods lists half open UTC spans [start, end) during which daylight_offset applies."]
    for r in G_REGIONS:
        ck.append("")
        ck.append("[%s]" % r.lower())
        ck.append("standard_offset = %d" % G_STD[r])
        ck.append("daylight_offset = %d" % (G_STD[r] + 60 if G_HAS_DST[r] else G_STD[r]))
        ck.append("daylight_periods = %s" % ", ".join("%s/%s" % (g_iso(a), g_iso(b)) for a, b in g_dst_periods(r)))
    put("region_clock.ini", "\n".join(ck) + "\n")

    br = ["; Servicing branches. Codes are compared after upper casing and removing spaces, hyphens and underscores.",
          "[branches]"]
    for r in G_REGIONS:
        for b in range(1, 6):
            br.append("%sB%02d = %s" % (G_RCODE[r], b, r))
    br += ["", "; Legacy and teller spellings, already in the compared form.", "[aliases]"]
    for r in G_REGIONS:
        for b in range(1, 6):
            br.append("%s%02d = %sB%02d" % (G_RCODE[r], b, G_RCODE[r], b))
            br.append("%s%d = %sB%02d" % (r.upper(), b, G_RCODE[r], b))
            br.append("%sB%d = %sB%02d" % (G_RCODE[r], b, G_RCODE[r], b))
    put("branches.ini", "\n".join(br) + "\n")

    ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Halvard Equipment Finance//Servicing Calendar//EN"]
    for uid, d, summ, regions, status in hols:
        ics += ["BEGIN:VEVENT", "UID:%s@hef" % uid, "DTSTART;VALUE=DATE:%s" % d.strftime("%Y%m%d"),
                "DTEND;VALUE=DATE:%s" % (d + _td(days=1)).strftime("%Y%m%d"), "SUMMARY:%s" % summ,
                "CATEGORIES:%s" % ",".join(regions), "STATUS:%s" % status, "END:VEVENT"]
    ics.append("END:VCALENDAR")
    put("holiday_calendar.ics", "\n".join(ics) + "\n")

    # scorecards
    v7_from = snapshots[min(v7_index, len(snapshots) - 1)] if v7_index is not None else _date(2099, 1, 1)
    v7b_from = snapshots[min(v7_index + 3, len(snapshots) - 1)] if v7_index is not None else _date(2099, 1, 1)
    jit = lambda p: p + rng.randint(-3, 3)
    v6 = {"version": "v6", "base_points": {"commercial": 300, "public": 318}, "cutoff": {"commercial": 520, "public": 505},
          "characteristics": [
              {"name": "dpd_now", "bins": [{"label": "current", "lo": 0, "hi": 1, "points": jit(60)}, {"label": "1-14", "lo": 1, "hi": 15, "points": jit(38)},
                                           {"label": "15-29", "lo": 15, "hi": 30, "points": jit(16)}, {"label": "30+", "lo": 30, "hi": None, "points": jit(-12)}],
               "special": {"quarantined": 22}},
              {"name": "max_dpd_12m", "bins": [{"label": "clean", "lo": 0, "hi": 1, "points": jit(52)}, {"label": "1-29", "lo": 1, "hi": 30, "points": jit(31)},
                                               {"label": "30-59", "lo": 30, "hi": 60, "points": jit(6)}, {"label": "60+", "lo": 60, "hi": None, "points": jit(-24)}],
               "special": {"quarantined": 18}},
              {"name": "months_on_book", "bins": [{"label": "0-5", "lo": 0, "hi": 6, "points": jit(8)}, {"label": "6-11", "lo": 6, "hi": 12, "points": jit(18)},
                                                  {"label": "12-23", "lo": 12, "hi": 24, "points": jit(29)}, {"label": "24+", "lo": 24, "hi": None, "points": jit(40)}],
               "special": {"quarantined": 20}},
              {"name": "utilisation", "bins": [{"label": "lt500", "lo": 0, "hi": 500, "points": jit(46)}, {"label": "500-799", "lo": 500, "hi": 800, "points": jit(31)},
                                               {"label": "800-999", "lo": 800, "hi": 1000, "points": jit(14)}, {"label": "1000+", "lo": 1000, "hi": None, "points": jit(-4)}],
               "special": {"missing": 21, "zero_limit": -16, "quarantined": 19}},
              {"name": "bureau", "bins": [{"label": "lt580", "lo": 300, "hi": 580, "points": jit(-6)}, {"label": "580-639", "lo": 580, "hi": 640, "points": jit(17)},
                                          {"label": "640-699", "lo": 640, "hi": 700, "points": jit(34)}, {"label": "700-759", "lo": 700, "hi": 760, "points": jit(51)},
                                          {"label": "760+", "lo": 760, "hi": 851, "points": jit(66)}],
               "special": {"missing": 14, "no_hit": 9, "thin": 4, "quarantined": 24}},
              {"name": "active_leases", "bins": [{"label": "1", "lo": 1, "hi": 2, "points": jit(31)}, {"label": "2-3", "lo": 2, "hi": 4, "points": jit(21)},
                                                 {"label": "4+", "lo": 4, "hi": None, "points": jit(6)}],
               "special": {"quarantined": 17}},
              {"name": "sector_class", "categories": {"A": jit(41), "B": jit(30), "C": jit(21), "D": jit(11), "E": jit(1)},
               "special": {"missing": 12, "quarantined": 20}}]}
    v7 = _json.loads(_json.dumps(v6))
    v7["version"] = "v7"
    v7["base_points"] = {"commercial": 292, "public": 309}
    v7["cutoff"] = {"commercial": 530, "public": 512}
    v7["characteristics"][2] = {"name": "recent_worst", "bins": [{"label": "none", "lo": 0, "hi": 1, "points": jit(47)}, {"label": "1-29", "lo": 1, "hi": 30, "points": jit(26)},
                                                                  {"label": "30+", "lo": 30, "hi": None, "points": jit(-7)}],
                                "special": {"quarantined": 16}}
    v7["characteristics"][4]["bins"] = [{"label": "lt600", "lo": 300, "hi": 600, "points": jit(-2)}, {"label": "600-679", "lo": 600, "hi": 680, "points": jit(24)},
                                        {"label": "680-739", "lo": 680, "hi": 740, "points": jit(43)}, {"label": "740+", "lo": 740, "hi": 851, "points": jit(63)}]
    v7["characteristics"][3]["bins"] = [{"label": "lt400", "lo": 0, "hi": 400, "points": jit(49)}, {"label": "400-749", "lo": 400, "hi": 750, "points": jit(33)},
                                        {"label": "750-999", "lo": 750, "hi": 1000, "points": jit(12)}, {"label": "1000+", "lo": 1000, "hi": None, "points": jit(-8)}]
    v7b = _json.loads(_json.dumps(v7))
    v7b["version"] = "v7b"
    v7b["base_points"] = {"commercial": 305, "public": 300}
    for c in v7b["characteristics"]:
        for b in c.get("bins", []):
            b["points"] += 4
    put("scorecard_v6.json", _json.dumps(v6, indent=2) + "\n")
    put("scorecard_v7.json", _json.dumps(v7, indent=2) + "\n")
    put("scorecard_v7b.json", _json.dumps(v7b, indent=2) + "\n")
    reg = {"versions": [
        {"version": "v6", "file": "scorecard_v6.json", "effective_from": "2024-01-01", "status": "released"},
        {"version": "v7", "file": "scorecard_v7.json", "effective_from": v7_from.isoformat(), "status": "released"},
        {"version": "v7b", "file": "scorecard_v7b.json", "effective_from": v7b_from.isoformat(), "status": "withdrawn"}]}
    put("scorecard_registry.json", _json.dumps(reg, indent=2) + "\n")

    lineage = ["# Feature lineage. Each node lists the nodes it is computed from.",
               "# Leaf nodes are the evidence sources an incident can quarantine.", "nodes:",
               "  lockbox: []", "  card: []", "  ledger: []", "  returns: []", "  leases: []", "  relief: []",
               "  bureau_kr: []", "  bureau_nd: []", "  limits: []", "  merges: []", "  crm: []",
               "  cash: [lockbox, card, ledger, returns]", "  schedule: [leases, relief]",
               "  delinquency: [cash, schedule]", "  exposure: [schedule, merges]", "characteristics:",
               "  dpd_now: [delinquency]", "  max_dpd_12m: [delinquency]", "  recent_worst: [delinquency]",
               "  months_on_book: [leases]", "  utilisation: [exposure, limits]", "  bureau: [bureau_kr, bureau_nd, crm]",
               "  active_leases: [merges]", "  sector_class: [crm]"]
    put("feature_lineage.yaml", "\n".join(lineage) + "\n")

    inc = []
    srcs = ["card", "bureau_kr", "lockbox", "limits", "bureau_nd", "merges", "returns", "ledger"]
    for i in range(8):
        s = snapshots[rng.below(len(snapshots))]
        r1 = rng.choice(G_REGIONS)
        regions = [r1] if i % 3 else sorted(set([r1, rng.choice(G_REGIONS)]), key=G_REGIONS.index)
        cut = cuts[(s, regions[0])]
        kind = i % 4
        if kind == 0:
            a, b = cut - _td(hours=rng.randint(1, 30)), cut + _td(hours=rng.randint(1, 20))
        elif kind == 1:
            a, b = cut, cut + _td(hours=rng.randint(2, 40))
        elif kind == 2:
            a, b = cut - _td(hours=rng.randint(2, 40)), cut
        else:
            a, b = cut - _td(days=rng.randint(20, 40)), cut + _td(days=rng.randint(1, 5))
        inc.append({"incident_id": "INC-%03d" % (101 + i), "source": srcs[i % len(srcs)], "regions": regions,
                    "from_utc": g_iso(a), "to_utc": g_iso(b), "declared_at": g_iso(b + _td(days=rng.randint(1, 60))),
                    "status": "rejected" if i in (5,) else "confirmed"})
    put("data_incidents.json", _json.dumps({"incidents": inc}, indent=2) + "\n")

    put("return_codes.ini", "; ACH and card return codes. reverses = yes removes the returned payment.\n[codes]\nR01 = yes\nR02 = yes\nR03 = yes\nR09 = yes\nC01 = no\nC02 = no\nC05 = no\n")
    put("servicing_policy.ini", "[tolerance]\ncommercial_cents = %d\npublic_cents = %d\n\n[card]\nsurcharge_cents = %d\n\n[relief]\nmax_holidays_per_lease = 1\n" % (tol[0], tol[1], surcharge))
    put("exclusion_policy.yaml", "# Exclusions from the backtest population, checked in this order.\nexclusions:\n  - reason: prior_charge_off\n    lookback: whole_history\n  - reason: holiday_active\n")
    put("bureau_vendors.ini", "[general]\nmax_age_days = %d\n\n[precedence]\ncommercial = KR, ND\npublic = ND, KR\n\n[KR]\nscale = 300-850\n\n[ND]\nscale = 0.0-100.0\nto_kr_numerator = 55\nto_kr_denominator = 100\n" % bureau_max_age)
    put("sector_reference.json", _json.dumps({"sectors": {k: G_SECTOR_CLASS[k] for k in sorted(G_SECTOR_CLASS)}}, indent=2) + "\n")
    put("bureau_disputes.json", _json.dumps({"disputes": disputes}, indent=2) + "\n")
    put("score_bands.yaml", "# Score bands for the summary, half open [lo, hi).\nbands:\n  - {band: lt450, lo: 0, hi: 450}\n  - {band: 450-499, lo: 450, hi: 500}\n  - {band: 500-549, lo: 500, hi: 550}\n  - {band: 550-599, lo: 550, hi: 600}\n  - {band: 600+, lo: 600, hi: 10000}\n")

    # record files
    rows = []
    for l in leases:
        oref = ("OB-%05d" % l["ghost_obligor"]) if l["ghost_obligor"] else g_obl_ref(rng, l["ob"]["n"])
        rows.append([l["id"], oref, l["start"].isoformat(), l["term"], g_fmt_dollars(l["inst"]), l["anchor"],
                     rng.choice(("EQUIP", "VEHICLE", "MEDICAL", "IT"))])
    obl_ids = set(o["id"] for o in obligors)
    put("leases.csv", csv_text(["lease_id", "obligor_ref", "start_date", "term_months", "instalment", "anchor_day", "product"],
                               protect(rows, lambda x: x[1] in obl_ids and x[5] == int(x[2][8:10]) and x[5] <= 27)))

    rows = []
    for i, (code, l, eff, rec) in enumerate(branch_rows):
        rows.append(["BH-%06d" % (i + 1), l["ref_r"] if rng.chance(40, 100) else l["id"], code, eff.isoformat(), g_iso(rec)])
    put("lease_branch_history.csv", csv_text(["row_id", "lease_ref", "branch_code", "effective_from", "recorded_at"], protect(rows, lambda x: x[1].startswith("HL-") and len(x[1]) == 9 and len(x[2]) == 4 and x[2][1:3] == "B0"
                                     and x[4][:10] <= (_date.fromisoformat(x[3]) + _td(days=2)).isoformat())))
    plain_obl = set(o["id"] for o in obligors if not o["wrong_tax"] and o["created"] < first_start - _td(days=29))
    rows = []
    for o in obligors:
        crm_seg = "public" if o["public"] else "commercial"
        if rng.chance(6, 100):
            crm_seg = "commercial" if o["public"] else "public"
        rows.append([o["id"], "%s %s" % (rng.choice(("Arden", "Bexley", "Calder", "Dunmore", "Elstree", "Fenwick", "Garrow", "Holt", "Ivel", "Jarrow")), rng.choice(("Holdings", "Logistics", "Council", "Health Trust", "Builders", "School District", "Foods", "Transit"))),
                     g_tax_fmt(rng, o["wrong_tax"] or o["tax"]), g_iso(o["created_at"]), crm_seg])
    put("obligors.csv", csv_text(["obligor_id", "legal_name", "tax_id", "created_at", "crm_segment"],
                                 protect(rows, lambda x: x[0] in plain_obl and x[2][2:3] == "-")))

    oe = []
    seq = [0]

    def oev(**kw):
        seq[0] += 1
        kw["event_seq"] = seq[0]
        oe.append(kw)
    for o in obligors:
        oev(obligor_ref=g_obl_ref(rng, o["n"]), type="SECTOR_SET", sector_code=o["sector"], effective_date=o["created"].isoformat(), recorded_at=g_iso(o["created_at"]))
        if rng.chance(15, 100):
            d = rdate(first_snapshot - _td(days=300), first_snapshot + _td(days=300))
            rec = at(d + _td(days=rng.randint(0, 10)))
            if rng.chance(20, 100):
                rec = at(d + _td(days=rng.randint(30, 120)))
            oev(obligor_ref=g_obl_ref(rng, o["n"]), type="SECTOR_CHANGE", sector_code=rng.choice(G_PUB_SECTORS if o["public"] else G_COMM_SECTORS), effective_date=d.isoformat(), recorded_at=g_iso(late(rec)))
        if o["wrong_tax"]:
            d = rdate(first_snapshot - _td(days=200), first_snapshot + _td(days=280))
            oev(obligor_ref=g_obl_ref(rng, o["n"]), type="TAXID_CORRECTION", tax_id=g_tax_fmt(rng, o["tax"]), effective_date=d.isoformat(), recorded_at=g_iso(at(d + _td(days=rng.randint(0, 20)))))
        if rng.chance(12, 100):
            d = rdate(first_start, data_cutoff)
            oev(obligor_ref=g_obl_ref(rng, o["n"]), type="NAME_CHANGE", legal_name="%s Group" % rng.choice(("Kestle", "Larch", "Morrow", "Nyland")), effective_date=d.isoformat(), recorded_at=g_iso(at(d)))
    for a, b, eff, rec in merges:
        oev(obligor_ref=g_obl_ref(rng, a), type="MERGE", into=g_obl_ref(rng, b), effective_date=eff.isoformat(), recorded_at=g_iso(late(rec)))
    oe = protect(oe, lambda x: x["type"] == "SECTOR_SET" and len(x["obligor_ref"]) == 8 and x["obligor_ref"].startswith("OB-"))
    put("obligor_events.jsonl", "".join(_json.dumps(x, sort_keys=True) + "\n" for x in oe))

    rows = []
    rid = 0
    for o in obligors:
        if o["listed"]:
            rid += 1
            rows.append(["PR-%06d" % rid, "%s-%s" % (o["tax"][:2], o["tax"][2:]), "Public body %d" % o["n"], o["listed"].isoformat(), o["delisted"].isoformat() if o["delisted"] else ""])
    while len(rows) < 2100:
        rid += 1
        t = "%09d" % rng.randint(100000000, 999999999)
        if t in taxes:
            continue
        rows.append(["PR-%06d" % rid, "%s-%s" % (t[:2], t[2:]), "Public body X%d" % rid, rdate(_date(2005, 1, 1), _date(2024, 1, 1)).isoformat(), ""])
    put("public_entity_register.csv", csv_text(["register_id", "fein", "entity_name", "listed_on", "delisted_on"],
                                               protect(rows, lambda x: x[4] == "" and x[3] < "2021")))

    evs = list(events)
    for x in list(events):
        if rng.chance(1, 100):
            evs.append(dict(x))
    evs = protect(evs, lambda x: x["version"] == 1 and x["type"] == "ACTIVATE" and len(x["lease_ref"]) == 9 and x["lease_ref"].startswith("HL-")
                  and x["recorded_at"][:10] <= (_date.fromisoformat(x["effective_date"]) + _td(days=3)).isoformat())
    # Invalid-type events (invalid_transition rejects): private RNG keeps the rest of the corpus byte-identical.
    drng = GRng((seed * 0x27D4EB2F + 0x165667B1) & 0xFFFFFFFFFFFFFFFF)
    dist = []
    dn = 0
    for l in leases:
        if not drng.chance(8, 100):
            continue
        typ = drng.choice(("SUSPEND", "RESUME", "RESTRUCTURE", "HOLD"))
        eff = l["start"] + _td(days=drng.randint(45, 230))
        rec = _dt(eff.year, eff.month, eff.day, tzinfo=_UTC) + _td(days=drng.randint(1, 25),
                                                                   hours=drng.randint(0, 23), minutes=drng.below(60), seconds=drng.below(60))
        if rec >= watermark:
            continue
        dn += 1
        lref = l["id"] if drng.chance(50, 100) else g_lease_ref(drng, l["n"])
        dist.append({"event_id": "EVD-%06d" % dn, "version": 1, "lease_ref": lref, "type": typ,
                     "effective_date": eff.isoformat(), "recorded_at": g_iso(rec)})
    evs = evs + dist
    put("lease_events.jsonl", "".join(_json.dumps(x, sort_keys=True) + "\n" for x in evs))

    rows = [[a, b, c, d, e, f, g_iso(t)] for a, b, c, d, e, f, t in relief_rows]
    put("relief_approvals.csv", csv_text(["status_id", "request_id", "lease_ref", "status", "months", "first_deferred_instalment", "status_at"],
                                         protect(rows, lambda x: x[3] == "REQUESTED" and len(x[2]) == 9 and x[2].startswith("HL-"))))

    for r in G_REGIONS:
        for line in list(lockbox[r]):
            if rng.chance(1, 100):
                lockbox[r].append(list(line))
    for line in list(card):
        if rng.chance(1, 100):
            card.append(list(line))
    def plain_bank(x, hours, seen):
        ok_amt = len(x[2].split(".")) == 2 and x[2].replace(".", "").isdigit() and len(x[2].split(".")[1]) == 2
        return (seen[x[0]] == 1 and len(x[1]) == 9 and x[1].startswith("HL-") and ok_amt and int(x[4][11:13]) in hours
                and x[4][:10] == (_date.fromisoformat(x[3]) + _td(days=1)).isoformat())
    for r in G_REGIONS:
        seen = {}
        for x in lockbox[r]:
            seen[x[0]] = seen.get(x[0], 0) + 1
        put("lockbox_%s.csv" % r.lower(), csv_text(["item_id", "remit_ref", "amount", "value_date", "received_at"],
                                                  protect(lockbox[r], lambda x: plain_bank(x, range(12, 18), seen))))
    seen = {}
    for x in card:
        seen[x[0]] = seen.get(x[0], 0) + 1
    put("card_settlements.csv", csv_text(["auth_code", "lease_ref", "amount", "settlement_date", "batch_at"],
                                         protect(card, lambda x: plain_bank(x, range(5, 10), seen))))
    returned = set(x[2] for x in returns)
    by_year = {y: [] for y in range(first_start.year, data_cutoff.year + 1)}
    for x in ledger:
        by_year.setdefault(int(x["posted_at"][:4]), []).append(x)
    for x in list(ledger):
        if rng.chance(6, 1000):
            by_year[int(x["posted_at"][:4])].append(dict(x))
    for y in sorted(by_year):
        lst = protect(by_year[y], lambda x: x["channel"] == "ACH" and x["posting_id"] not in returned and 20 <= int(x["posted_at"][11:13]) <= 23)
        put("servicing_ledger_%d.jsonl" % y, "".join(_json.dumps(x, sort_keys=True) + "\n" for x in lst))
    valid_p = set(p["pid"] for p in payments if "pid" in p)
    returns = protect(returns, lambda x: x[3] in ("R01", "R02", "R03") and x[2] in valid_p)
    rl = ["# ACH and card return file, one line per returned or notified posting"]
    for t, rid_, pid, code in returns:
        rl.append("%s RETURN id=%s posting=%s code=%s" % (t, rid_, pid, code))
    put("ach_returns.log", "\n".join(rl) + "\n")
    kr_rows = protect(kr_rows, lambda x: x["status"] == "OK" and x["recorded_at"][:10] <= (_date.fromisoformat(x["pulled_on"]) + _td(days=3)).isoformat())
    put("bureau_kr.jsonl", "".join(_json.dumps(x, sort_keys=True) + "\n" for x in kr_rows))
    put("bureau_nd.csv", csv_text(["pull_ref", "fein", "pull_date", "loaded_at", "result", "score"],
                                  protect(nd_rows, lambda x: x[4] == "HIT" and x[5] not in ("", "0.0") and x[3][:10] <= (_date.fromisoformat(x[2]) + _td(days=3)).isoformat())))
    put("credit_limits.csv", csv_text(["limit_id", "obligor_ref", "limit_k", "effective_from", "recorded_at"],
                                      protect(lim_rows, lambda x: len(x[1]) == 8 and x[1].startswith("OB-") and x[2] not in ("", "0")
                                              and x[4][:10] <= (_date.fromisoformat(x[3]) + _td(days=4)).isoformat())))
    rows = []
    for l in leases:
        for k in range(1, l["term"] + 1):
            key = (l["n"], k)
            if key in notice_inv:
                issued = l["due"][k] - _td(days=20)
                if l["holiday"] and k >= l["holiday"][1]:
                    issued = max(issued, l["holiday"][2].date() + _td(days=1))
                rows.append([notice_inv[key], l["id"], k, l["due"][k].isoformat(), issued.isoformat()])
    put("invoice_notices.csv", csv_text(["invoice_no", "lease_id", "instalment_no", "printed_due_date", "issued_on"],
                                        protect(rows, lambda x: (_date.fromisoformat(x[3]) - _date.fromisoformat(x[4])).days == 20 and int(x[3][8:10]) <= 27)))

    # production snapshot run log for the log year
    recs = []
    lease_by_n = {l["n"]: l for l in leases}
    for r in G_REGIONS:
        for line in lockbox[r]:
            recs.append((line[4], r, "lockbox_%s" % r.lower(), line[0]))
    for line in card:
        l = lease_by_auth.get(line[0])
        if l:
            recs.append((line[4], l["region"], "card_settlements", line[0]))
    recs.sort()
    import bisect as _bisect
    keys = [x[0] for x in recs]
    lg = ["# Production snapshot runs of the champion scorecard, one block per snapshot and region."]
    for s in log_snaps:
        for r in G_REGIONS:
            cut = log_cuts[(s, r)]
            lg.append("%s RUN snapshot=%s region=%s cut=%s" % (g_iso(cut), s.isoformat(), r, g_iso(cut)))
            for src in ("leases", "lease_events", "relief_approvals", "lockbox_%s" % r.lower(), "card_settlements", "servicing_ledger", "ach_returns", "bureau_kr", "bureau_nd", "credit_limits"):
                lg.append("%s LOAD source=%s through=%s" % (g_iso(cut + _td(seconds=40)), src, g_iso(cut)))
            lo = _bisect.bisect_left(keys, g_iso(cut - _td(seconds=900)))
            hi = _bisect.bisect_right(keys, g_iso(cut + _td(seconds=900)))
            for t, rr, src, rid_ in recs[lo:hi]:
                if rr != r:
                    continue
                dec = "ADMIT" if t <= g_iso(cut) else "DEFER"
                lg.append("%s BOUNDARY source=%s record=%s recorded_at=%s decision=%s" % (g_iso(cut + _td(seconds=95)), src, rid_, t, dec))
            lg.append("%s END snapshot=%s region=%s" % (g_iso(cut + _td(seconds=400)), s.isoformat(), r))
    put("snapshot_runs.log", "\n".join(lg) + "\n")
    return files


# ---- rule documents of the extract ----
DOCS_Z = (
    "eNqtfXt33Max51fp4/wRMhcay/aNsyGTnENLVKRrScxSlH1z7/gMMDMgiXAGGAMYUdzVfvetXz36AWAoJbs+JxEHQL+qq+td1f/7"
    "q2WxuuvLrl+0+03Zzbbrr07cV79xP+hjx4/n9bx+WWw+FO3anf+6r3bbsu7di6ou6lXpNmXRlZ0r/Yu+catmuy3bVVVs3HXVbjtX"
    "1Gu32y831WpeL5t1RQ2q2l03+9a15U3V1N2Je9u0/W3m3jV7/PMzhkez86LrZ+7qtnSr22K7o29lyHndrZq2XGFWVedsJeXaUQeu"
    "uXZ9tS1PXPmhbB+kBT7jNmtXUN+uK1tMpLmmrupi1902vVsXPRbzsVj1mwdX0DR7Ws1+s3a3xYfSLcuytj5oIv1tIU0ynmp/a7PC"
    "UPSrdv/Yr28w3k1R1bSgezSgFzohGmVfbGigdUXfXPdle0/L6WaA+G9+497prHgH8miv6lnfbDe5u6k+lDwQwEzdJ8vI+EW93y7L"
    "FvCwl7wb8xovCVw7bMS2oZ/dzA/o8ip3R9dts3VPj901TbGjR+53vo8FWi6kWT6v5Q9ZQZhOJiCiYYptSVN64F2h3/x55lYb2k8C"
    "DiEMg4Q2Gl/Na/qMdueW8IG6448FAQpsFq/NySc2XYG2WxWbsl4XLY+1LK9pI+Z1Rdjz7LZoCda0311frTq3LrtVWy3LeCtkX6g9"
    "+q4AJT+a7cePdXO/KWlDHTazqHs8x8Tuhi9kfr7n8VTz1b5fbBqa8QJ4mitoBphoAFzRl3cGPe71t4TxTXNX1Td6gNxRbsv3hznP"
    "CG2qNR3Kqn8IT48zQvBdW3YdAZ92//3Vs5k753OCuRBWyL7Q4WpaID7BYl7LL2wXn6vcfi+KPs9oPW1JE7Zf1EW/7/QHfVkSoso7"
    "RuR+davvdk0XWm2aQjt0TWtrXWONPC/AFAehoNZt2e/bupttmpvcbaq6nLkzEIhomwc4siWc2GM7bF1NvSFcu8cpxVD6lPYHu1m7"
    "+KD+thtv8cz9fFvSF63vEZ01nfWkkAJhLDay6WM08aNdN5tNc9+5Xdus96ueNnRe77CYagVg+3NHZ18Xfdts1l1GDQVSoaHDNwIs"
    "Vxbtpirbef1Af2VKDHWlfpqEXTRrOoWFI6xkSnavS2MCR/25Yr2teiau1Nm6vC5bkMBKKTMf8GWzB/YR1dztNiCseq7vCS/abdHe"
    "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"
    "zjmVYK0qusMbcPdu4hGwwhnjQzxV1Sr+CPeEMj9nVIbNSrHM2yh9aQleFQS1Vu11GoE0WKEPG/N8SNPeUg+sMGo+Zo8AwU7wuXck"
    "MuE6cAtIIFtBK7RLBBVpxb9sBdkBmnJ1BwvlYKvii8yFUzN6sBiaSSBgXQ6Xz0nuPkApiTfftRWwSW7VYdKit+GKzVC4W1KHNRRi"
    "GNUttnqnhdyhPqx4muTecajYMc9slLPxz1eheCV8cHqN5hayNBEfUBmXeI4oSLgWNRFjD1a6nY6TBl+BvSbJl4UurzsvUXITUWOs"
    "C7ItUSxgmT/cQjyltsOpcm2LAQlHbxxvfSDki8MkhzehKZNOr0DjLxx/Ajx/ZTel8dVoki5ryJA2BGn/dV+t7kLJAgWMXc0qMZ3e"
    "sO/jNe3m21rz/PnX55JmtUh3mjUrOq/eR8lrSHN8r1lLXzYkTFiVoieaZBmnzlpm9iiFlp1N/0pq7JP/P/mrT9wVbKkH0lc/l7nq"
    "k1VZpuPuOFO1GGSpbqR4+5dlqVIfZbH2hT+T4sI0PfBEgZrm3foLgus073d8lzYnOOPSXeDv//m/suHPTA=="
)

# ---- independent recomputation (verifier side) ----
import configparser as _cp
import re as _re
import tomllib as _tomllib
from fractions import Fraction as _F

V_REGIONS = ("North", "South", "West", "East")
V_SEGMENTS = ("commercial", "public")
_V_EPOCH = _dt(1970, 1, 1, tzinfo=_UTC)


def v_sec(s):
    s = s.strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    t = _dt.fromisoformat(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=_UTC)
    return int((t - _V_EPOCH).total_seconds())


def v_day(s):
    return _date.fromisoformat(s.strip()).toordinal()


def v_iso(sec):
    return (_V_EPOCH + _td(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")


def v_rows(text):
    lines = [x for x in text.split("\n")]
    head = lines[0].strip().split(",")
    return [(x, dict(zip(head, x.split(",")))) for x in lines[1:] if x.strip()]


def v_jl(text):
    return [(x, _json.loads(x)) for x in text.split("\n") if x.strip()]


def v_key(kind, s):
    t = _re.sub(r"[ _-]", "", s).upper()
    pat = {"lease": r"HL0*([0-9]+)", "obl": r"OB0*([0-9]+)"}[kind]
    m = _re.fullmatch(pat, t)
    if not m:
        return None
    return ("HL-%06d" if kind == "lease" else "OB-%05d") % int(m.group(1))


def v_tax(s):
    d = "".join(ch for ch in s if ch.isdigit())
    return d if len(d) == 9 else None


def v_mshift(y, m, k):
    t = y * 12 + m - 1 + k
    return t // 12, t % 12 + 1


def v_mlen(y, m):
    a = _date(y, m, 1)
    b = _date(y + (m == 12), m % 12 + 1, 1)
    return (b - a).days


def v_yaml_items(text, section):
    out = []
    on = False
    for raw in text.split("\n"):
        ln = raw.split("#")[0].rstrip()
        if not ln.strip():
            continue
        if not ln[0].isspace():
            on = ln.strip() == section + ":"
            continue
        if on:
            out.append(ln.strip())
    return out


def v_round(fr):
    return None if fr is None else round(fr * 1000000)


class VBacktest:
    def __init__(self, read, names):
        self.read = read
        self.names = names
        self.late = {}
        self.dup = {}
        self.rej = set()
        self._cfg()
        self._people()
        self._contracts()
        self._money()
        self._credit()

    def _take(self, name, sec):
        if sec > self.wm:
            self.late[name] = self.late.get(name, 0) + 1
            return False
        return True

    def _uniq(self, name, items):
        seen = set()
        for raw, rec in items:
            if raw in seen:
                self.dup[name] = self.dup.get(name, 0) + 1
            else:
                seen.add(raw)
                yield rec

    # ---------------- configuration
    def _cfg(self):
        run = _tomllib.loads(self.read("backtest_run.toml"))["run"]
        self.run_id = run["run_id"]
        f = _date.fromisoformat(run["first_snapshot"])
        self.snaps = []
        for i in range(run["snapshot_count"]):
            y, m = v_mshift(f.year, f.month, i * run["snapshot_step_months"])
            self.snaps.append(_date(y, m, min(f.day, v_mlen(y, m))).toordinal())
        self.perf = run["performance_days"]
        self.bad_dpd = run["bad_dpd"]
        self.cutoff = v_day(run["data_cutoff"])
        self.wm = v_sec(run["watermark_utc"])
        h, mi, se = [int(x) for x in run["cut_local_time"].split(":")]
        self.cut_secs = h * 3600 + mi * 60 + se
        c = _cp.ConfigParser()
        c.read_string(self.read("region_clock.ini"))
        self.tz = {}
        for r in V_REGIONS:
            sec = c[r.lower()]
            spans = []
            for chunk in sec.get("daylight_periods", "").split(","):
                if "/" in chunk:
                    a, b = chunk.strip().split("/")
                    spans.append((v_sec(a), v_sec(b)))
            self.tz[r] = (int(sec["standard_offset"]) * 60, int(sec["daylight_offset"]) * 60, spans)
        self.cut = {}
        for s in self.snaps:
            for r in V_REGIONS:
                local = (s - _date(1970, 1, 1).toordinal()) * 86400 + self.cut_secs
                cand = [local - off for off in (self.tz[r][0], self.tz[r][1])]
                pick = [t for t in cand if t + self._off(r, t) == local]
                self.cut[(s, r)] = min(pick) if pick else cand[0]
        b = _cp.ConfigParser()
        b.optionxform = str
        b.read_string(self.read("branches.ini"))
        self.branch = {}
        for k, v in b["branches"].items():
            self.branch[k.upper()] = v
        for k, v in b["aliases"].items():
            self.branch.setdefault(k.upper(), self.branch[v.upper()])
        self.hol = {r: set() for r in V_REGIONS}
        cur = None
        for ln in self.read("holiday_calendar.ics").replace("\r", "").split("\n"):
            if ln == "BEGIN:VEVENT":
                cur = {}
            elif ln == "END:VEVENT" and cur is not None:
                if cur.get("STATUS") == "CONFIRMED":
                    a = _date(int(cur["DTSTART"][:4]), int(cur["DTSTART"][4:6]), int(cur["DTSTART"][6:8])).toordinal()
                    e = cur.get("DTEND")
                    z = _date(int(e[:4]), int(e[4:6]), int(e[6:8])).toordinal() if e else a + 1
                    for r in cur.get("CATEGORIES", "").split(","):
                        if r.strip() in self.hol:
                            self.hol[r.strip()].update(range(a, z))
                cur = None
            elif cur is not None and ":" in ln:
                k, v = ln.split(":", 1)
                cur[k.split(";")[0]] = v
        p = _cp.ConfigParser()
        p.read_string(self.read("servicing_policy.ini"))
        self.tol = {"commercial": p.getint("tolerance", "commercial_cents"), "public": p.getint("tolerance", "public_cents")}
        self.sur = p.getint("card", "surcharge_cents")
        self.maxhol = p.getint("relief", "max_holidays_per_lease")
        q = _cp.ConfigParser()
        q.optionxform = str
        q.read_string(self.read("return_codes.ini"))
        self.rev = set(k.upper() for k, v in q["codes"].items() if v.strip().lower() == "yes")
        w = _cp.ConfigParser()
        w.read_string(self.read("bureau_vendors.ini"))
        self.age = w.getint("general", "max_age_days")
        self.prec = {g: [x.strip() for x in w["precedence"][g].split(",")] for g in V_SEGMENTS}
        self.nd = (w.getint("ND", "to_kr_numerator"), w.getint("ND", "to_kr_denominator"))
        self.sectors = _json.loads(self.read("sector_reference.json"))["sectors"]
        self.excl = [x.split(":")[1].strip() for x in v_yaml_items(self.read("exclusion_policy.yaml"), "exclusions") if x.startswith("- reason")]
        lin = self.read("feature_lineage.yaml")
        self.parents = {}
        for sec in ("nodes", "characteristics"):
            for x in v_yaml_items(lin, sec):
                k, v = x.split(":")
                self.parents[k.strip()] = [y.strip() for y in v.replace("[", "").replace("]", "").split(",") if y.strip()]
        self.bands = []
        for x in v_yaml_items(self.read("score_bands.yaml"), "bands"):
            kv = {}
            for part in x.strip("- {}").split(","):
                a, b2 = part.split(":")
                kv[a.strip()] = b2.strip()
            self.bands.append((kv["band"], int(kv["lo"]), int(kv["hi"])))
        self.cards = []
        for x in _json.loads(self.read("scorecard_registry.json"))["versions"]:
            if x["status"] == "released":
                self.cards.append((v_day(x["effective_from"]), x["version"], _json.loads(self.read(x["file"]))))
        self.incidents = [(v_sec(x["from_utc"]), v_sec(x["to_utc"]), x["source"], x["regions"])
                          for x in _json.loads(self.read("data_incidents.json"))["incidents"] if x["status"] == "confirmed"]
        self.disp = {}
        for x in _json.loads(self.read("bureau_disputes.json"))["disputes"]:
            t = v_sec(x["recorded_at"])
            if t <= self.wm:
                self.disp[x["pull_id"]] = min(t, self.disp.get(x["pull_id"], t))

    def _off(self, r, t):
        std, dst, spans = self.tz[r]
        return dst if any(a <= t < b for a, b in spans) else std

    def _lday(self, r, t):
        return _date(1970, 1, 1).toordinal() + (t + self._off(r, t)) // 86400

    def _bd(self, r, d):
        return _date.fromordinal(d).weekday() < 5 and d not in self.hol[r]

    # ---------------- obligors
    def _people(self):
        self.obl = {}
        for raw, r in v_rows(self.read("obligors.csv")):
            t = v_sec(r["created_at"])
            if self._take("obligors.csv", t):
                self.obl[v_key("obl", r["obligor_id"])] = (t, v_tax(r["tax_id"]))
        self.merge = {}
        self.taxfix = {}
        self.sect = {}
        for e in self._uniq("obligor_events.jsonl", v_jl(self.read("obligor_events.jsonl"))):
            t = v_sec(e["recorded_at"])
            if not self._take("obligor_events.jsonl", t):
                continue
            o = v_key("obl", e["obligor_ref"])
            eff = v_day(e["effective_date"])
            if e["type"] == "MERGE":
                self.merge.setdefault(o, []).append((eff, t, e["event_seq"], v_key("obl", e["into"])))
            elif e["type"] == "TAXID_CORRECTION":
                self.taxfix.setdefault(o, []).append((t, e["event_seq"], v_tax(e["tax_id"])))
            elif e["type"] in ("SECTOR_SET", "SECTOR_CHANGE"):
                self.sect.setdefault(o, []).append((eff, t, e["event_seq"], e["sector_code"]))
        self.reg = {}
        for raw, r in v_rows(self.read("public_entity_register.csv")):
            hi = v_day(r["delisted_on"]) if r["delisted_on"].strip() else 10 ** 9
            self.reg.setdefault(v_tax(r["fein"]), []).append((v_day(r["listed_on"]), hi))

    def _taxid(self, o, K):
        fx = [x for x in self.taxfix.get(o, []) if x[0] <= K]
        return max(fx)[2] if fx else self.obl[o][1]

    def _is_public(self, tax, d):
        return any(lo <= d < hi for lo, hi in self.reg.get(tax, []))

    def _survivor(self, o, A, K):
        hops = 0
        while hops < 1000:
            m = [x for x in self.merge.get(o, []) if x[0] <= A and x[1] <= K]
            if not m:
                break
            o = max(m)[3]
            hops += 1
        return o

    # ---------------- leases
    def _contracts(self):
        self.L = {}
        for raw, r in v_rows(self.read("leases.csv")):
            whole, frac = r["instalment"].split(".")
            self.L[v_key("lease", r["lease_id"])] = {
                "ob": v_key("obl", r["obligor_ref"]), "start": v_day(r["start_date"]), "term": int(r["term_months"]),
                "inst": int(whole) * 100 + int(frac), "anchor": int(r["anchor_day"]), "br": [], "ev": {}, "rq": {}, "pay": []}
        for raw, r in v_rows(self.read("lease_branch_history.csv")):
            t = v_sec(r["recorded_at"])
            if not self._take("lease_branch_history.csv", t):
                continue
            k = v_key("lease", r["lease_ref"])
            if k in self.L:
                self.L[k]["br"].append((v_day(r["effective_from"]), t, r["row_id"], self.branch[_re.sub(r"[ _-]", "", r["branch_code"]).upper()]))
        for k, x in self.L.items():
            x["book"] = min(x["br"])[3] if x["br"] else None
            seg = "commercial"
            if x["ob"] in self.obl and self._is_public(self._taxid(x["ob"], self.wm), x["start"]):
                seg = "public"
            x["cseg"] = seg
        for e in self._uniq("lease_events.jsonl", v_jl(self.read("lease_events.jsonl"))):
            t = v_sec(e["recorded_at"])
            if not self._take("lease_events.jsonl", t):
                continue
            k = v_key("lease", e["lease_ref"])
            if k not in self.L:
                self.rej.add(("lease_events.jsonl", e["event_id"], "unknown_lease"))
                continue
            self.L[k]["ev"].setdefault(e["event_id"], []).append((e["version"], t, e["type"], v_day(e["effective_date"])))
        self._lc = {}
        for k in self.L:
            for eid in self._life(k, self.wm)[3]:
                self.rej.add(("lease_events.jsonl", eid, "invalid_transition"))
        for raw, r in v_rows(self.read("relief_approvals.csv")):
            t = v_sec(r["status_at"])
            if not self._take("relief_approvals.csv", t):
                continue
            k = v_key("lease", r["lease_ref"])
            if k not in self.L:
                self.rej.add(("relief_approvals.csv", r["status_id"], "unknown_lease"))
                continue
            self.L[k]["rq"].setdefault(r["request_id"], []).append((t, r["status_id"], r["status"], int(r["months"]), int(r["first_deferred_instalment"])))
        self.holidays = []
        for k in sorted(self.L):
            h, bad, extra = self._relief(k, self.wm)
            for sid in bad:
                self.rej.add(("relief_approvals.csv", sid, "invalid_transition"))
            for rq in extra:
                self.rej.add(("relief_approvals.csv", rq, "holiday_limit"))
            if h:
                self.holidays.append({"request_id": h[2], "lease_id": k, "months": h[0], "first_deferred_instalment": h[1]})
        self.inv = {}
        for raw, r in v_rows(self.read("invoice_notices.csv")):
            self.inv[r["invoice_no"].strip().upper()] = v_key("lease", r["lease_id"])
        self._sc = {}

    def _life(self, k, K, A=10 ** 9):
        ck = (k, K, A)
        if ck in self._lc:
            return self._lc[ck]
        seq = []
        for eid, vs in self.L[k]["ev"].items():
            got = sorted(x for x in vs if x[1] <= K)
            if got and got[-1][2] != "VOID":
                seq.append((got[-1][3], eid, got[-1][2]))
        st, closed, co, bad = "PENDING", None, None, []
        for eff, eid, typ in sorted(seq):
            if eff > A:
                continue
            nxt = {("PENDING", "ACTIVATE"): "ACTIVE", ("ACTIVE", "BUYOUT"): "CLOSED", ("ACTIVE", "PAYOFF"): "CLOSED",
                   ("ACTIVE", "CHARGE_OFF"): "CHARGED_OFF"}.get((st, typ))
            if nxt is None:
                bad.append(eid)
                continue
            st = nxt
            if nxt == "CLOSED":
                closed = eff
            if nxt == "CHARGED_OFF":
                co = eff
        self._lc[ck] = (st, closed, co, bad)
        return self._lc[ck]

    def _relief(self, k, K):
        live = []
        bad = []
        for rq, rows in self.L[k]["rq"].items():
            st = None
            when = None
            for t, sid, s2, mo, fk in sorted(rows):
                if t > K:
                    continue
                allowed = {None: ("REQUESTED",), "REQUESTED": ("APPROVED", "DECLINED"), "APPROVED": ("WITHDRAWN",)}.get(st, ())
                if s2 not in allowed:
                    bad.append(sid)
                    continue
                st = s2
                if s2 == "APPROVED":
                    when = (t, mo, fk)
            if st == "APPROVED":
                live.append((when[0], rq, when[1], when[2]))
        live.sort()
        h = (live[0][2], live[0][3], live[0][1]) if live else None
        return h, bad, [x[1] for x in live[self.maxhol:]]

    def _dues(self, k, h):
        ck = (k, h[:2] if h else None)
        if ck in self._sc:
            return self._sc[ck]
        x = self.L[k]
        s = _date.fromordinal(x["start"])
        out = [0]
        for i in range(1, x["term"] + 1):
            y, m = v_mshift(s.year, s.month, i + (h[0] if h and i >= h[1] else 0))
            d0 = _date(y, m, min(x["anchor"], v_mlen(y, m))).toordinal()
            d = d0
            while not self._bd(x["book"], d):
                d += 1
            if x["cseg"] == "public" and _date.fromordinal(d).month != _date.fromordinal(d0).month:
                d = d0
                while not self._bd(x["book"], d):
                    d -= 1
            out.append(d)
        self._sc[ck] = out
        return out

    # ---------------- cash
    def _amt(self, s):
        m = _re.fullmatch(r"([0-9]+)\.([0-9]{2})", s.strip())
        if m is None:
            return None
        c = int(m.group(1)) * 100 + int(m.group(2))
        return c if c > 0 else None

    def _remit(self, s):
        k = v_key("lease", s)
        if k in self.L:
            return k
        k = self.inv.get(s.strip().upper())
        return k if k in self.L else None

    def _money(self):
        P = {}
        for r in V_REGIONS:
            nm = "lockbox_%s.csv" % r.lower()
            for row in self._uniq(nm, v_rows(self.read(nm))):
                t = v_sec(row["received_at"])
                if not self._take(nm, t):
                    continue
                k = self._remit(row["remit_ref"])
                c = self._amt(row["amount"])
                if k is None or c is None:
                    self.rej.add((nm, row["item_id"], "unknown_lease" if k is None else "bad_amount"))
                    continue
                P.setdefault(("LOCKBOX", row["item_id"].replace("-", "").upper()), {"ch": "LOCKBOX", "bank": [], "led": [], "ret": []})["bank"].append((t, v_day(row["value_date"]), c, k))
        nm = "card_settlements.csv"
        for row in self._uniq(nm, v_rows(self.read(nm))):
            t = v_sec(row["batch_at"])
            if not self._take(nm, t):
                continue
            k = self._remit(row["lease_ref"])
            c = self._amt(row["amount"])
            if k is None or c is None:
                self.rej.add((nm, row["auth_code"], "unknown_lease" if k is None else "bad_amount"))
                continue
            P.setdefault(("CARD", row["auth_code"].upper()), {"ch": "CARD", "bank": [], "led": [], "ret": []})["bank"].append((t, v_day(row["settlement_date"]), c - self.sur, k))
        owner = {}
        for nm in self.names:
            if not (nm.startswith("servicing_ledger_") and nm.endswith(".jsonl")):
                continue
            for e in self._uniq(nm, v_jl(self.read(nm))):
                t = v_sec(e["posted_at"])
                if not self._take(nm, t):
                    continue
                key = ("ACH", e["posting_id"]) if e["channel"] == "ACH" else (e["channel"], e["source_ref"].replace("-", "").upper())
                P.setdefault(key, {"ch": e["channel"], "bank": [], "led": [], "ret": []})["led"].append((t, e["amount"], v_key("lease", e["lease_id"]), e["posting_id"]))
                owner[e["posting_id"]] = key
        nm = "ach_returns.log"
        items = []
        for ln in self.read(nm).split("\n"):
            if ln.strip() and not ln.startswith("#"):
                items.append((ln, ln))
        for ln in self._uniq(nm, items):
            f = ln.split()
            kv = {}
            for part in f[2:]:
                a, b2 = part.split("=", 1)
                kv[a] = b2
            t = v_sec(f[0])
            if not self._take(nm, t):
                continue
            if kv["posting"] not in owner:
                self.rej.add((nm, kv["id"], "unknown_posting"))
            elif kv["code"].upper() in self.rev:
                P[owner[kv["posting"]]]["ret"].append((t, kv["posting"]))
        self.counts = {"lockbox": 0, "card": 0, "ach": 0, "reversed": 0}
        for key in P:
            p = P[key]
            k = p["led"][0][2] if p["led"] else p["bank"][0][3]
            if k in self.L:
                self.L[k]["pay"].append(p)
                self.counts[p["ch"].lower()] += 1
                self.counts["reversed"] += bool(p["ret"])

    def _cash(self, k, K):
        x = self.L[k]
        got = []
        for p in x["pay"]:
            led = [y for y in p["led"] if y[0] <= K]
            bank = [y for y in p["bank"] if y[0] <= K]
            if not led and not bank:
                continue
            pids = set(y[3] for y in led)
            if any(t <= K and pid in pids for t, pid in p["ret"]):
                continue
            b = sorted(bank)[-1] if bank else None
            l0 = sorted(led)[0] if led else None
            if p["ch"] == "ACH":
                got.append((self._lday(x["book"], l0[0]), l0[1]))
            elif p["ch"] == "LOCKBOX":
                got.append((b[1], b[2]) if b else (self._lday(x["book"], l0[0]), l0[1]))
            else:
                got.append((b[1] if b else self._lday(x["book"], l0[0]), l0[1] if l0 else b[2]))
        return got

    def _dpd_series(self, k, dues, cash, lo, hi):
        """DPD for every day lo..hi inclusive, walking the days."""
        x = self.L[k]
        tol = self.tol[x["cseg"]]
        cash = sorted(cash)
        paid = 0
        i = 0
        while i < len(cash) and cash[i][0] < lo:
            paid += cash[i][1]
            i += 1
        out = []
        for d in range(lo, hi + 1):
            while i < len(cash) and cash[i][0] <= d:
                paid += cash[i][1]
                i += 1
            n = (paid + tol) // x["inst"] + 1
            out.append(d - dues[n] if n <= x["term"] and dues[n] < d else 0)
        return out

    # ---------------- bureau and limits
    def _credit(self):
        self.pull = {}
        for e in self._uniq("bureau_kr.jsonl", v_jl(self.read("bureau_kr.jsonl"))):
            t = v_sec(e["recorded_at"])
            if not self._take("bureau_kr.jsonl", t):
                continue
            val = {"OK": ("score", e["score"]), "NOHIT": ("no_hit", None), "THIN": ("thin", None)}[e["status"]]
            self.pull.setdefault(v_tax(e["tax_id"]), []).append((v_day(e["pulled_on"]), "KR", t, e["pull_id"], val))
        for r in self._uniq("bureau_nd.csv", v_rows(self.read("bureau_nd.csv"))):
            t = v_sec(r["loaded_at"])
            if not self._take("bureau_nd.csv", t):
                continue
            sc = r["score"].strip()
            if r["result"] == "NOHIT":
                val = ("no_hit", None)
            elif sc == "":
                val = ("thin", None)
            else:
                val = ("score", 300 + int(sc.replace(".", "")) * self.nd[0] // self.nd[1])
            self.pull.setdefault(v_tax(r["fein"]), []).append((v_day(r["pull_date"]), "ND", t, r["pull_ref"], val))
        self.lim = {}
        for r in self._uniq("credit_limits.csv", v_rows(self.read("credit_limits.csv"))):
            t = v_sec(r["recorded_at"])
            if not self._take("credit_limits.csv", t):
                continue
            if r["limit_k"].strip():
                self.lim.setdefault(v_key("obl", r["obligor_ref"]), []).append((v_day(r["effective_from"]), t, r["limit_id"], int(r["limit_k"]) * 100000))

    # ---------------- per observation
    def settle(self):
        rows = []
        unres = []
        cand = 0
        ql = {}
        for n, ups in self.parents.items():
            ql[n] = ups
        for s in self.snaps:
            A = s - 1
            card = None
            for eff, ver, c in sorted(self.cards, key=lambda z: (z[0], z[1])):
                if eff <= s:
                    card = (ver, c)
            index = {}
            for k in sorted(self.L):
                x = self.L[k]
                if x["book"] is None:
                    continue
                K = self.cut[(s, x["book"])]
                if self._life(k, K, A)[0] != "ACTIVE":
                    continue
                cand += 1
                br = [b for b in x["br"] if b[0] <= A and b[1] <= K]
                if not br:
                    unres.append({"lease_id": k, "snapshot": _date.fromordinal(s).isoformat(), "reason": "no_branch"})
                    continue
                if x["ob"] not in self.obl or self.obl[x["ob"]][0] > K:
                    unres.append({"lease_id": k, "snapshot": _date.fromordinal(s).isoformat(), "reason": "unknown_obligor"})
                    continue
                rows.append(self._observe(k, s, A, K, sorted(br)[-1][3], card, index))
        self.out = (rows, unres, cand)
        return self.out

    def _family(self, A, K, index):
        if K not in index:
            fam = {}
            for k2 in sorted(self.L):
                y = self.L[k2]
                if y["book"] is None or y["ob"] not in self.obl or self.obl[y["ob"]][0] > K:
                    continue
                fam.setdefault(self._survivor(y["ob"], A, K), []).append(k2)
            index[K] = fam
        return index[K]

    def _observe(self, k, s, A, K, region, card, index):
        x = self.L[k]
        o = self._survivor(x["ob"], A, K)
        tax = self._taxid(o, K)
        seg = "public" if self._is_public(tax, A) else "commercial"
        h = self._relief(k, K)[0]
        dues = self._dues(k, h)
        series = self._dpd_series(k, dues, self._cash(k, K), A - 364, A)
        f = {"dpd_now": series[-1], "max_dpd_12m": max(series), "recent_worst": max(series[-90:])}
        sd = _date.fromordinal(x["start"])
        ad = _date.fromordinal(A)
        f["months_on_book"] = (ad.year * 12 + ad.month) - (sd.year * 12 + sd.month) - (ad.day < sd.day)
        mates = self._family(A, K, index).get(o, [])
        live = [m for m in mates if self._life(m, K, A)[0] == "ACTIVE"]
        f["active_leases"] = len(live)
        expo = 0
        for m in live:
            dm = self._dues(m, self._relief(m, K)[0])
            expo += self.L[m]["inst"] * len([d for d in dm[1:] if d > A])
        lims = [y for y in self.lim.get(o, []) if y[0] <= A and y[1] <= K]
        if not lims:
            util = ("missing", None)
        else:
            cents = sorted(lims)[-1][3]
            util = ("zero_limit", None) if cents == 0 else (None, expo * 1000 // cents)
        order = self.prec[seg]
        best = None
        for pd, vn, t, pid, val in self.pull.get(tax, []):
            if pd > A or A - pd > self.age or t > K or (pid in self.disp and self.disp[pid] <= K):
                continue
            key = (pd, len(order) - order.index(vn), t, pid)
            if best is None or key > best[0]:
                best = (key, val)
        bureau = ("missing", None) if best is None else (best[1] if best[1][0] != "score" else (None, best[1][1]))
        secs = [y for y in self.sect.get(o, []) if y[0] <= A and y[1] <= K]
        sclass = self.sectors.get(sorted(secs)[-1][3]) if secs else None
        cutK = self.cut[(s, x["book"])]
        hit = set(src for a, b, src, regs in self.incidents if region in regs and a <= cutK < b)
        q = set()
        changed = bool(hit)
        q |= hit
        while changed:
            changed = False
            for n, ups in self.parents.items():
                if n not in q and q.intersection(ups):
                    q.add(n)
                    changed = True
        ver, c = card
        pts = c["base_points"][seg]
        bins = {}
        qc = []
        for ch in c["characteristics"]:
            nm = ch["name"]
            if nm in q:
                lab = "quarantined"
                qc.append(nm)
                p = ch["special"][lab]
            elif nm == "sector_class":
                lab = sclass if sclass is not None else "missing"
                p = ch["categories"][lab] if sclass is not None else ch["special"]["missing"]
            else:
                kind, val = util if nm == "utilisation" else (bureau if nm == "bureau" else (None, f[nm]))
                if kind is not None:
                    lab, p = kind, ch["special"][kind]
                else:
                    hitb = [b for b in ch["bins"] if b["lo"] <= val and (b["hi"] is None or val < b["hi"])][0]
                    lab, p = hitb["label"], hitb["points"]
            bins[nm] = lab
            pts += p
        ex = None
        for reason in self.excl:
            if reason == "prior_charge_off" and any(m != k and self._life(m, K, A)[0] == "CHARGED_OFF" for m in mates):
                ex = ex or reason
            if reason == "holiday_active" and h and self._dues(k, None)[h[1]] <= A < dues[h[1]]:
                ex = ex or reason
        return {"lease_id": k, "snapshot": _date.fromordinal(s).isoformat(), "obligor_id": o, "segment": seg,
                "scorecard": ver, "bins": bins, "score": pts, "approved": pts >= c["cutoff"][seg], "exclusion": ex,
                "label": self._outcome(k, A), "_region": region, "_q": sorted(qc)}

    def _outcome(self, k, A):
        end = A + self.perf
        if end > self.cutoff:
            return "immature"
        st, closed, co, _ = self._life(k, self.wm)
        if co is not None and co <= end:
            return "bad"
        last = end if closed is None else min(end, closed)
        if last >= A + 1:
            if not hasattr(self, "_fin"):
                self._fin = {}
            if k not in self._fin:
                self._fin[k] = (self._dues(k, self._relief(k, self.wm)[0]), self._cash(k, self.wm))
            dues, cash = self._fin[k]
            if max(self._dpd_series(k, dues, cash, A + 1, last)) >= self.bad_dpd:
                return "bad"
        if closed is not None and closed <= end:
            return "indeterminate"
        return "good"


def v_tot(rows):
    t = dict.fromkeys(("observations", "excluded", "bad", "good", "indeterminate", "immature", "approved"), 0)
    t["observations"] = len(rows)
    for r in rows:
        t[r["label"]] += 1
        if r["exclusion"]:
            t["excluded"] += 1
        if r["approved"]:
            t["approved"] += 1
    return t


def v_met(rows):
    use = [r for r in rows if not r["exclusion"] and r["label"] in ("good", "bad")]
    g = [r["score"] for r in use if r["label"] == "good"]
    b = [r["score"] for r in use if r["label"] == "bad"]
    auc = ks = None
    if g and b:
        wins = 0
        for x in b:
            for y in g:
                wins += 2 if y > x else (1 if y == x else 0)
        auc = _F(wins, 2 * len(g) * len(b)) if len(g) * len(b) < 4000000 else None
        if auc is None:
            gs = sorted(g)
            import bisect as _bs
            wins = sum(2 * (len(gs) - _bs.bisect_right(gs, x)) + (_bs.bisect_right(gs, x) - _bs.bisect_left(gs, x)) for x in b)
            auc = _F(wins, 2 * len(g) * len(b))
        ks = max(abs(_F(sum(1 for x in b if x <= c), len(b)) - _F(sum(1 for y in g if y <= c), len(g))) for c in set(g + b)) if len(g) + len(b) < 3000 else None
        if ks is None:
            pts = sorted(set(g + b))
            gs, bs = sorted(g), sorted(b)
            gi = bi = 0
            ks = _F(0)
            for c in pts:
                while gi < len(gs) and gs[gi] <= c:
                    gi += 1
                while bi < len(bs) and bs[bi] <= c:
                    bi += 1
                ks = max(ks, abs(_F(bi, len(bs)) - _F(gi, len(gs))))
    return {"population": len(use), "bad": len(b), "good": len(g), "auc_ppm": v_round(auc), "ks_ppm": v_round(ks),
            "bad_rate_ppm": v_round(_F(len(b), len(use))) if use else None,
            "approved": sum(1 for r in use if r["approved"]), "approved_bad": sum(1 for r in use if r["approved"] and r["label"] == "bad")}


def v_reports(read, names):
    bt = VBacktest(read, names)
    rows, unres, cand = bt.settle()
    rows.sort(key=lambda r: (r["snapshot"], r["lease_id"]))
    snaps = [_date.fromordinal(s).isoformat() for s in bt.snaps]
    pub = lambda r: {k: v for k, v in r.items() if not k.startswith("_")}
    out = {}
    for reg in V_REGIONS:
        rr = [r for r in rows if r["_region"] == reg]
        out["region_%s.json" % reg] = {"region": reg, "totals": v_tot(rr), "metrics": v_met(rr), "observations": [pub(r) for r in rr]}
    for g in V_SEGMENTS:
        rr = [r for r in rows if r["segment"] == g]
        cards = {}
        for r in rr:
            cards[r["scorecard"]] = cards.get(r["scorecard"], 0) + 1
        out["segment_%s.json" % g] = {"segment": g, "totals": v_tot(rr), "metrics": v_met(rr), "by_scorecard": cards,
                                      "by_snapshot": [{"snapshot": s, "totals": v_tot([r for r in rr if r["snapshot"] == s]),
                                                       "metrics": v_met([r for r in rr if r["snapshot"] == s])} for s in snaps]}
    out["summary.json"] = {
        "run_id": bt.run_id, "snapshots": snaps, "totals": v_tot(rows), "metrics": v_met(rows),
        "by_region": {reg: v_tot([r for r in rows if r["_region"] == reg]) for reg in V_REGIONS},
        "by_segment": {g: v_tot([r for r in rows if r["segment"] == g]) for g in V_SEGMENTS},
        "by_snapshot": [{"snapshot": s, "totals": v_tot([r for r in rows if r["snapshot"] == s]),
                         "auc_ppm": v_met([r for r in rows if r["snapshot"] == s])["auc_ppm"]} for s in snaps],
        "score_bands": [{"band": nm, "observations": sum(1 for r in rows if lo <= r["score"] < hi),
                         "bad": sum(1 for r in rows if lo <= r["score"] < hi and r["label"] == "bad"),
                         "good": sum(1 for r in rows if lo <= r["score"] < hi and r["label"] == "good")} for nm, lo, hi in bt.bands]}
    use = {}
    for r in rows:
        use[(r["snapshot"], r["scorecard"])] = use.get((r["snapshot"], r["scorecard"]), 0) + 1
    mg = []
    for o in sorted(bt.merge):
        end = bt._survivor(o, 10 ** 9, bt.wm)
        if end != o:
            mg.append({"obligor_id": o, "resolved_to": end})
    out["policy_audit.json"] = {
        "cut_instants": {_date.fromordinal(s).isoformat(): {r: v_iso(bt.cut[(s, r)]) for r in V_REGIONS} for s in bt.snaps},
        "scorecard_usage": [{"snapshot": a, "version": b2, "observations": n} for (a, b2), n in sorted(use.items())],
        "exclusions": [{"lease_id": r["lease_id"], "snapshot": r["snapshot"], "reason": r["exclusion"]} for r in rows if r["exclusion"]],
        "quarantined": [{"lease_id": r["lease_id"], "snapshot": r["snapshot"], "characteristics": r["_q"]} for r in rows if r["_q"]],
        "holidays": sorted(bt.holidays, key=lambda z: z["request_id"]),
        "merges": mg}
    total = len(rows)
    out["data_quality.json"] = {
        "rejects": [{"source": a, "record_id": b2, "reason": c} for a, b2, c in sorted(bt.rej)],
        "duplicates": dict(sorted(bt.dup.items())), "late_records": dict(sorted(bt.late.items())),
        "unresolved": sorted(unres, key=lambda z: (z["snapshot"], z["lease_id"])),
        "partition": {"candidates": cand, "scored": total, "unresolved": len(unres)},
        "payments": bt.counts,
        "identity_check": {"regions_minus_summary": 0, "segments_minus_summary": 0, "snapshots_minus_summary": 0}}
    return out


# ---- grading harness ----
import base64 as _b64
import hashlib as _hashlib
import os as _os
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import zlib as _zlib

OUT = _Path("/app/out")
SCRIPT = OUT / "derive_report.py"
REPORTS = ("summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json",
           "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json")
TOP_KEYS = {
    "summary.json": {"run_id", "snapshots", "totals", "metrics", "by_region", "by_segment", "by_snapshot", "score_bands"},
    "policy_audit.json": {"cut_instants", "scorecard_usage", "exclusions", "quarantined", "holidays", "merges"},
    "data_quality.json": {"rejects", "duplicates", "late_records", "unresolved", "partition", "payments", "identity_check"},
    "region_North.json": {"region", "totals", "metrics", "observations"},
    "region_South.json": {"region", "totals", "metrics", "observations"},
    "region_West.json": {"region", "totals", "metrics", "observations"},
    "region_East.json": {"region", "totals", "metrics", "observations"},
    "segment_commercial.json": {"segment", "totals", "metrics", "by_snapshot", "by_scorecard"},
    "segment_public.json": {"segment", "totals", "metrics", "by_snapshot", "by_scorecard"},
}
SHIPPED = (4417, {})
TIER_A = (91, {"n_leases": 520, "n_obligors": 450, "first_start": _date(2023, 6, 1), "last_start": _date(2025, 8, 31),
               "first_snapshot": _date(2025, 3, 1), "snapshot_count": 6, "step_months": 1, "performance_days": 120,
               "bad_dpd": 45, "data_cutoff": _date(2026, 1, 31), "tol": (1500, 7000), "surcharge": 175, "v7_index": 2,
               "notices_until": _date(2024, 12, 31), "run_id": "HEF-BT-H1", "log_year": 2024, "bureau_max_age": 150,
               "lease_base": 600000, "obl_base": 40000})
TIER_B = (523, {"n_leases": 600, "n_obligors": 520, "first_start": _date(2022, 9, 1), "last_start": _date(2024, 12, 31),
                "first_snapshot": _date(2024, 7, 1), "snapshot_count": 5, "step_months": 3, "performance_days": 90,
                "bad_dpd": 30, "data_cutoff": _date(2025, 12, 31), "tol": (4000, 4000), "surcharge": 300, "v7_index": None,
                "notices_until": _date(2023, 12, 31), "run_id": "HEF-BT-H2", "log_year": 2023, "bureau_max_age": 365,
                "lease_base": 700000, "obl_base": 50000})
TIER_C = (7, {"n_leases": 260, "n_obligors": 230, "first_start": _date(2023, 9, 1), "last_start": _date(2025, 1, 31),
              "first_snapshot": _date(2025, 3, 9), "snapshot_count": 3, "step_months": 1, "performance_days": 60,
              "bad_dpd": 60, "data_cutoff": _date(2025, 9, 30), "tol": (2500, 10000), "surcharge": 250, "v7_index": 1,
              "notices_until": _date(2024, 6, 30), "run_id": "HEF-BT-H3", "log_year": 2024, "bureau_max_age": 180,
              "lease_base": 800000, "obl_base": 60000})
TIER_E = (1999, {"n_leases": 3600, "n_obligors": 3100, "run_id": "HEF-BT-H4", "lease_base": 100000, "obl_base": 20000})
TIER_D = (311, {"n_leases": 700, "n_obligors": 600, "first_start": _date(2022, 6, 1), "last_start": _date(2024, 10, 31),
                "first_snapshot": _date(2024, 10, 1), "snapshot_count": 8, "step_months": 2, "performance_days": 150,
                "bad_dpd": 90, "data_cutoff": _date(2025, 10, 31), "tol": (500, 12000), "surcharge": 500, "v7_index": 4,
                "notices_until": _date(2023, 12, 31), "run_id": "HEF-BT-H5", "log_year": 2023, "bureau_max_age": 90,
                "lease_base": 120000, "obl_base": 22000})
TIER_F = (877, {"n_leases": 640, "n_obligors": 560, "first_start": _date(2023, 3, 1), "last_start": _date(2025, 4, 30),
                "first_snapshot": _date(2025, 2, 1), "snapshot_count": 10, "step_months": 1, "performance_days": 75,
                "bad_dpd": 40, "data_cutoff": _date(2026, 2, 28), "tol": (1000, 1000), "surcharge": 120, "v7_index": 8,
                "notices_until": _date(2024, 9, 30), "run_id": "HEF-BT-H6", "log_year": 2024, "bureau_max_age": 200,
                "lease_base": 130000, "obl_base": 23000})
TIER_G = (1453, {"n_leases": 560, "n_obligors": 480, "first_start": _date(2022, 2, 1), "last_start": _date(2024, 8, 31),
                 "first_snapshot": _date(2024, 1, 29), "snapshot_count": 7, "step_months": 1, "performance_days": 120,
                 "bad_dpd": 55, "data_cutoff": _date(2025, 6, 30), "tol": (3000, 6000), "surcharge": 200, "v7_index": 3,
                 "notices_until": _date(2023, 6, 30), "run_id": "HEF-BT-H7", "log_year": 2023, "bureau_max_age": 150,
                 "lease_base": 140000, "obl_base": 24000})
TIER_H = (2029, {"n_leases": 600, "n_obligors": 520, "first_start": _date(2022, 9, 1), "last_start": _date(2024, 12, 31),
                 "first_snapshot": _date(2024, 7, 1), "snapshot_count": 4, "step_months": 3, "performance_days": 300,
                 "bad_dpd": 75, "data_cutoff": _date(2026, 1, 31), "tol": (8000, 2000), "surcharge": 300, "v7_index": None,
                 "notices_until": _date(2023, 12, 31), "run_id": "HEF-BT-H8", "log_year": 2023, "bureau_max_age": 365,
                 "lease_base": 150000, "obl_base": 25000})
TIER_I = (3137, {"n_leases": 1500, "n_obligors": 1300, "first_start": _date(2023, 1, 1), "last_start": _date(2025, 6, 30),
                 "first_snapshot": _date(2025, 1, 1), "snapshot_count": 12, "step_months": 1, "performance_days": 180,
                 "bad_dpd": 60, "data_cutoff": _date(2026, 3, 31), "tol": (2000, 9000), "surcharge": 250, "v7_index": 6,
                 "notices_until": _date(2024, 6, 30), "run_id": "HEF-BT-H9", "log_year": 2024, "bureau_max_age": 60,
                 "lease_base": 160000, "obl_base": 26000})
TIER_J = (4211, {"n_leases": 520, "n_obligors": 450, "first_start": _date(2023, 6, 1), "last_start": _date(2025, 3, 31),
                 "first_snapshot": _date(2025, 3, 10), "snapshot_count": 6, "step_months": 1, "performance_days": 100,
                 "bad_dpd": 50, "data_cutoff": _date(2025, 12, 31), "tol": (1500, 5000), "surcharge": 175, "v7_index": 2,
                 "notices_until": _date(2024, 6, 30), "run_id": "HEF-BT-H10", "log_year": 2024, "bureau_max_age": 180,
                 "lease_base": 170000, "obl_base": 27000})
_CACHE = {}


def _docs():
    return _json.loads(_zlib.decompress(_b64.b64decode(DOCS_Z)).decode("utf-8"))


def _corpus(tier, tag):
    key = ("corpus", tag)
    if key not in _CACHE:
        root = _Path(_tempfile.mkdtemp(prefix="hef-in-")) / tag
        generate(root, tier[0], **tier[1])
        for name, text in _docs().items():
            (root / name).write_text(text, encoding="utf-8")
        for p in root.iterdir():
            p.chmod(0o644)
        root.chmod(0o755)
        root.parent.chmod(0o755)
        _CACHE[key] = root
    return _CACHE[key]


def _expected(tier, tag):
    key = ("expected", tag)
    if key not in _CACHE:
        root = _corpus(tier, tag)
        names = sorted(p.name for p in root.iterdir())
        _CACHE[key] = v_reports(lambda n: (root / n).read_text(encoding="utf-8"), names)
    return _CACHE[key]


def _digest(root):
    h = _hashlib.sha256()
    for p in sorted(root.iterdir()):
        h.update(p.name.encode())
        h.update(p.read_bytes() if p.is_file() else b"<dir>")
    return h.hexdigest()


def _execute(data_dir):
    """Run the delivered program unprivileged on data_dir. Returns (out_dir, rc, digest_before, digest_after) or None."""
    if not SCRIPT.is_file() or SCRIPT.is_symlink():
        return None
    work = _Path(_tempfile.mkdtemp(prefix="hef-run-"))
    work.chmod(0o777)
    script = work / "derive_report.py"
    _shutil.copyfile(SCRIPT, script)
    script.chmod(0o755)
    out = work / "out"
    before = _digest(data_dir)
    cmd = [_sys.executable, str(script), str(data_dir), str(out)]
    if _os.name == "posix" and _os.geteuid() == 0:
        cmd = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"] + cmd
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(work), "LANG": "C.UTF-8", "PYTHONHASHSEED": "random"}
    try:
        proc = _subprocess.run(cmd, cwd=str(work), env=env, stdin=_subprocess.DEVNULL, stdout=_subprocess.DEVNULL,
                               stderr=_subprocess.DEVNULL, timeout=300)
    except (OSError, _subprocess.SubprocessError):
        return None
    return out, proc.returncode, before, _digest(data_dir)


def _run(tier, tag, variant="plain"):
    key = ("run", tag, variant)
    if key in _CACHE:
        return _CACHE[key]
    result = None
    try:
        src = _corpus(tier, tag)
        if variant in ("plain", "again"):
            result = _execute(src)
        elif variant == "renamed":
            dst = _Path(_tempfile.mkdtemp(prefix="hef-ren-")) / "zz_other_extract"
            _shutil.copytree(src, dst)
            dst.parent.chmod(0o755)
            result = _execute(dst)
        elif variant == "permuted":
            dst = _Path(_tempfile.mkdtemp(prefix="hef-perm-")) / tag
            _shutil.copytree(src, dst)
            dst.parent.chmod(0o755)
            rng = GRng(1009)
            for p in sorted(dst.iterdir()):
                if p.suffix in (".jsonl", ".csv"):
                    lines = p.read_text(encoding="utf-8").split("\n")
                    body = [x for x in (lines[1:] if p.suffix == ".csv" else lines) if x]
                    rng.shuffle(body)
                    head = [lines[0]] if p.suffix == ".csv" else []
                    p.write_text("\n".join(head + body) + "\n", encoding="utf-8")
            result = _execute(dst)
        elif variant == "missing":
            dst = _Path(_tempfile.mkdtemp(prefix="hef-miss-")) / tag
            _shutil.copytree(src, dst)
            dst.parent.chmod(0o755)
            (dst / "return_codes.ini").unlink()
            result = _execute(dst)
    except Exception:
        result = None
    _CACHE[key] = result
    return result


def _load(path):
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 128 * 1024 * 1024:
            return None
        return _json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _ok(r):
    return r is not None and r[1] == 0 and r[0].is_dir()


def _ran(tier, tag, variant="plain"):
    r = _run(tier, tag, variant)
    if not _ok(r):
        return None
    return {n: _load(r[0] / n) for n in REPORTS}


def _mine(name):
    # A shipped report counts only when the delivered program also settles the
    # regenerated shipped extract within the run time limit.
    if not _ok(_run(SHIPPED, "shipped")):
        return None
    return _load(OUT / name)


def _obs(loader):
    rows = {}
    for r in V_REGIONS:
        doc = loader("region_%s.json" % r)
        if not isinstance(doc, dict) or not isinstance(doc.get("observations"), list):
            return None
        for x in doc["observations"]:
            if not isinstance(x, dict):
                return None
            rows[(x.get("lease_id"), x.get("snapshot"))] = dict(x, _region=r)
    return rows


def _pair():
    exp = _expected(SHIPPED, "shipped")
    return _obs(_mine), _obs(lambda n: exp[n])


def _field(rows, fn):
    return {k: fn(v) for k, v in rows.items()}


def _bins(names):
    def pick(o):
        b = o.get("bins")
        return tuple(b.get(n) for n in names) if isinstance(b, dict) else None
    return pick


def _same_tier(tier, tag):
    got = _ran(tier, tag)
    if got is None:
        return False
    exp = _expected(tier, tag)
    return all(got[n] == exp[n] for n in REPORTS)


def _all_files_bytes(r):
    return {n: (r[0] / n).read_bytes() if (r[0] / n).is_file() else None for n in REPORTS}


# ------------------------------------------------------------------ positive checks
@criterion(description="every scored observation in the four regional reports carries the exact score")
def observation_scores_exact(workspace: _Path) -> bool:
    try:
        mine, exp = _pair()
        return mine is not None and _field(mine, lambda o: o.get("score")) == _field(exp, lambda o: o["score"])
    except Exception:
        return False


@criterion(description="every scored observation carries the exact outcome label")
def observation_labels_exact(workspace: _Path) -> bool:
    try:
        mine, exp = _pair()
        return mine is not None and _field(mine, lambda o: o.get("label")) == _field(exp, lambda o: o["label"])
    except Exception:
        return False


@criterion(description="the scored observations are exactly the expected lease snapshots with the exact region, obligor, segment and scorecard")
def observation_identity_exact(workspace: _Path) -> bool:
    try:
        mine, exp = _pair()
        f = lambda o: (o.get("_region"), o.get("obligor_id"), o.get("segment"), o.get("scorecard"))
        return mine is not None and _field(mine, f) == _field(exp, f)
    except Exception:
        return False


@criterion(description="the metrics objects of the summary, the four regions and the two segments equal the recomputation")
def metrics_exact(workspace: _Path) -> bool:
    try:
        exp = _expected(SHIPPED, "shipped")
        names = ["summary.json"] + ["region_%s.json" % r for r in V_REGIONS] + ["segment_%s.json" % g for g in V_SEGMENTS]
        for n in names:
            doc = _mine(n)
            if not isinstance(doc, dict) or doc.get("metrics") != exp[n]["metrics"]:
                return False
        return True
    except Exception:
        return False


@criterion(description="regional, segment and snapshot totals close on one summary total that equals the recomputed total")
def identity_triangle_closes(workspace: _Path) -> bool:
    try:
        want = _expected(SHIPPED, "shipped")["summary.json"]["totals"]
        s = _mine("summary.json")
        regs = [_mine("region_%s.json" % r) for r in V_REGIONS]
        segs = [_mine("segment_%s.json" % g) for g in V_SEGMENTS]
        if not isinstance(s, dict) or any(not isinstance(x, dict) for x in regs + segs):
            return False
        if s["totals"] != want:
            return False
        for k, v in want.items():
            if sum(x["totals"][k] for x in regs) != v or sum(x["totals"][k] for x in segs) != v:
                return False
            if sum(x["totals"][k] for x in s["by_snapshot"]) != v:
                return False
        return True
    except Exception:
        return False


@criterion(description="the delivered program reproduces all nine reports exactly on an unseen six snapshot extract with a 120 day window")
def heldout_tier_a_exact(workspace: _Path) -> bool:
    try:
        return _same_tier(TIER_A, "tier_a")
    except Exception:
        return False


@criterion(description="the delivered program reproduces all nine reports exactly on an unseen quarterly extract scored by one version")
def heldout_tier_b_exact(workspace: _Path) -> bool:
    try:
        return _same_tier(TIER_B, "tier_b")
    except Exception:
        return False


@criterion(description="the delivered program reproduces all nine reports exactly on an unseen extract half again larger than the shipped one")
def heldout_tier_large_exact(workspace: _Path) -> bool:
    try:
        return _same_tier(TIER_E, "tier_e")
    except Exception:
        return False


@criterion(description="every observation carries the exact dpd_now, max_dpd_12m and recent_worst bins")
def delinquency_bins_exact(workspace: _Path) -> bool:
    try:
        mine, exp = _pair()
        f = _bins(("dpd_now", "max_dpd_12m", "recent_worst"))
        return mine is not None and _field(mine, f) == _field(exp, f)
    except Exception:
        return False


@criterion(description="every observation carries the exact bureau bin")
def bureau_bins_exact(workspace: _Path) -> bool:
    try:
        mine, exp = _pair()
        f = _bins(("bureau",))
        return mine is not None and _field(mine, f) == _field(exp, f)
    except Exception:
        return False


@criterion(description="every observation carries the exact utilisation, active_leases, sector_class and months_on_book bins")
def obligor_bins_exact(workspace: _Path) -> bool:
    try:
        mine, exp = _pair()
        f = _bins(("utilisation", "active_leases", "sector_class", "months_on_book"))
        return mine is not None and _field(mine, f) == _field(exp, f)
    except Exception:
        return False


@criterion(description="the exclusion of every observation and the policy_audit exclusions and quarantined lists equal the recomputation")
def exclusions_and_quarantine_exact(workspace: _Path) -> bool:
    try:
        mine, exp = _pair()
        p = _mine("policy_audit.json")
        e = _expected(SHIPPED, "shipped")["policy_audit.json"]
        if mine is None or not isinstance(p, dict):
            return False
        if _field(mine, lambda o: o.get("exclusion")) != _field(exp, lambda o: o["exclusion"]):
            return False
        return p.get("exclusions") == e["exclusions"] and p.get("quarantined") == e["quarantined"]
    except Exception:
        return False


@criterion(description="policy_audit cut_instants and scorecard_usage equal the recomputation")
def cut_instants_and_usage_exact(workspace: _Path) -> bool:
    try:
        p = _mine("policy_audit.json")
        e = _expected(SHIPPED, "shipped")["policy_audit.json"]
        return isinstance(p, dict) and p.get("cut_instants") == e["cut_instants"] and p.get("scorecard_usage") == e["scorecard_usage"]
    except Exception:
        return False


@criterion(description="policy_audit holidays and merges equal the recomputation")
def holidays_and_merges_exact(workspace: _Path) -> bool:
    try:
        p = _mine("policy_audit.json")
        e = _expected(SHIPPED, "shipped")["policy_audit.json"]
        return isinstance(p, dict) and p.get("holidays") == e["holidays"] and p.get("merges") == e["merges"]
    except Exception:
        return False


@criterion(description="data_quality rejects, late_records and duplicates equal the recomputation for every file")
def rejects_and_record_counts_exact(workspace: _Path) -> bool:
    try:
        d = _mine("data_quality.json")
        e = _expected(SHIPPED, "shipped")["data_quality.json"]
        return isinstance(d, dict) and all(d.get(k) == e[k] for k in ("rejects", "late_records", "duplicates"))
    except Exception:
        return False


@criterion(description="data_quality unresolved, partition and payments equal the recomputation")
def unresolved_and_partition_exact(workspace: _Path) -> bool:
    try:
        d = _mine("data_quality.json")
        e = _expected(SHIPPED, "shipped")["data_quality.json"]
        return isinstance(d, dict) and all(d.get(k) == e[k] for k in ("unresolved", "partition", "payments"))
    except Exception:
        return False


@criterion(description="summary by_region, by_segment, by_snapshot and score_bands and the segment by_snapshot and by_scorecard equal the recomputation")
def breakdowns_exact(workspace: _Path) -> bool:
    try:
        exp = _expected(SHIPPED, "shipped")
        s = _mine("summary.json")
        if not isinstance(s, dict) or any(s.get(k) != exp["summary.json"][k] for k in ("by_region", "by_segment", "by_snapshot", "score_bands")):
            return False
        for g in V_SEGMENTS:
            n = "segment_%s.json" % g
            doc = _mine(n)
            if not isinstance(doc, dict) or doc.get("by_snapshot") != exp[n]["by_snapshot"] or doc.get("by_scorecard") != exp[n]["by_scorecard"]:
                return False
        return True
    except Exception:
        return False


@criterion(description="the delivered program reproduces all nine reports exactly on an unseen extract whose snapshots fall on the 9th, one of them a clock change day")
def heldout_tier_c_exact(workspace: _Path) -> bool:
    try:
        return _same_tier(TIER_C, "tier_c")
    except Exception:
        return False


@criterion(description="the delivered program reproduces all nine reports exactly on an unseen extract with eight snapshots two months apart, a 150 day window and a 90 day bad threshold")
def heldout_tier_d_exact(workspace: _Path) -> bool:
    try:
        return _same_tier(TIER_D, "tier_d")
    except Exception:
        return False


@criterion(description="the delivered program reproduces all nine reports exactly on an unseen extract with ten monthly snapshots and equal commercial and public payment tolerances")
def heldout_tier_f_exact(workspace: _Path) -> bool:
    try:
        return _same_tier(TIER_F, "tier_f")
    except Exception:
        return False


@criterion(description="the delivered program reproduces all nine reports exactly on an unseen extract whose snapshots fall on the 29th starting in a leap year")
def heldout_tier_g_exact(workspace: _Path) -> bool:
    try:
        return _same_tier(TIER_G, "tier_g")
    except Exception:
        return False


@criterion(description="the delivered program reproduces all nine reports exactly on an unseen extract with four quarterly snapshots, a 300 day window and a commercial tolerance above the public one")
def heldout_tier_h_exact(workspace: _Path) -> bool:
    try:
        return _same_tier(TIER_H, "tier_h")
    except Exception:
        return False


@criterion(description="the delivered program reproduces all nine reports exactly on a larger unseen extract with a 60 day bureau age limit and twelve monthly snapshots")
def heldout_tier_i_exact(workspace: _Path) -> bool:
    try:
        return _same_tier(TIER_I, "tier_i")
    except Exception:
        return False


@criterion(description="the delivered program reproduces all nine reports exactly on an unseen extract whose snapshots fall on the 10th with a 100 day window")
def heldout_tier_j_exact(workspace: _Path) -> bool:
    try:
        return _same_tier(TIER_J, "tier_j")
    except Exception:
        return False


@criterion(description="all nine reports parse as JSON objects with exactly the contract top level keys")
def reports_parse_with_contract_keys(workspace: _Path) -> bool:
    try:
        for n in REPORTS:
            doc = _load(OUT / n)
            if not isinstance(doc, dict) or set(doc) != TOP_KEYS[n]:
                return False
        return True
    except Exception:
        return False


@criterion(description="data_quality identity_check equals the residuals recomputed from the written reports")
def identity_self_report_matches(workspace: _Path) -> bool:
    try:
        d = _mine("data_quality.json")
        s = _mine("summary.json")
        regs = [_mine("region_%s.json" % r) for r in V_REGIONS]
        segs = [_mine("segment_%s.json" % g) for g in V_SEGMENTS]
        if not isinstance(d, dict) or not isinstance(s, dict) or any(not isinstance(x, dict) for x in regs + segs):
            return False
        tot = s["totals"]["observations"]
        want = {"regions_minus_summary": sum(x["totals"]["observations"] for x in regs) - tot,
                "segments_minus_summary": sum(x["totals"]["observations"] for x in segs) - tot,
                "snapshots_minus_summary": sum(x["totals"]["observations"] for x in s["by_snapshot"]) - tot}
        return d.get("identity_check") == want
    except Exception:
        return False


# ------------------------------------------------------------------ negative checks
@criterion(description="the program writes lease or obligor ids of the shipped extract into the reports of an unseen extract")
def negative_hardcoded_sample_answers(workspace: _Path) -> bool:
    # Tier A uses lease ids from HL-600001 and obligor ids from OB-40001; shipped ids are below both.
    try:
        r = _run(TIER_A, "tier_a")
        if not _ok(r):
            return False
        text = "".join(p.read_text(encoding="utf-8", errors="replace") for p in sorted(r[0].iterdir()) if p.is_file())
        return _re.search(r"HL-00[0-9]{4}|OB-0[0-9]{4}", text) is not None
    except Exception:
        return False


@criterion(description="the shipped reports differ from what the delivered program writes for the shipped extract")
def negative_reports_not_from_program(workspace: _Path) -> bool:
    # Fires only when the program runs cleanly and its reports disagree with /app/out.
    try:
        r = _run(SHIPPED, "shipped")
        if not _ok(r) or not all((OUT / n).is_file() for n in REPORTS):
            return False
        return any(_load(OUT / n) != _load(r[0] / n) for n in REPORTS)
    except Exception:
        return False


@criterion(description="two runs of the program on the same extract write different bytes")
def negative_nondeterministic_output(workspace: _Path) -> bool:
    # Same input twice, byte comparison of the nine reports.
    try:
        a, b = _run(SHIPPED, "shipped"), _run(SHIPPED, "shipped", "again")
        if not _ok(a) or not _ok(b):
            return False
        return _all_files_bytes(a) != _all_files_bytes(b)
    except Exception:
        return False


@criterion(description="the reports change when the same extract sits in a directory with another name")
def negative_depends_on_directory_name(workspace: _Path) -> bool:
    # A copy of the shipped extract under another directory name must give the same reports.
    try:
        a, b = _run(SHIPPED, "shipped"), _run(SHIPPED, "shipped", "renamed")
        if not _ok(a) or not _ok(b):
            return False
        return _all_files_bytes(a) != _all_files_bytes(b)
    except Exception:
        return False


@criterion(description="the reports change when record lines of the csv and jsonl inputs are reordered")
def negative_depends_on_record_order(workspace: _Path) -> bool:
    # Line order inside csv and jsonl files carries no meaning under the contract.
    try:
        a, b = _run(SHIPPED, "shipped"), _run(SHIPPED, "shipped", "permuted")
        if not _ok(a) or not _ok(b):
            return False
        return _all_files_bytes(a) != _all_files_bytes(b)
    except Exception:
        return False


@criterion(description="the program changes, adds or removes files in its input directory")
def negative_writes_into_inputs(workspace: _Path) -> bool:
    # Digest of DATA_DIR before and after the shipped run.
    try:
        r = _run(SHIPPED, "shipped")
        return r is not None and r[2] != r[3]
    except Exception:
        return False


@criterion(description="the program writes files other than the nine reports into its output directory")
def negative_extra_output_files(workspace: _Path) -> bool:
    # Only the nine contract files may appear in OUT_DIR.
    try:
        r = _run(SHIPPED, "shipped")
        if not _ok(r):
            return False
        return any(p.name not in REPORTS for p in r[0].iterdir())
    except Exception:
        return False


@criterion(description="a count, score or ppm figure in the shipped reports is written as a float")
def negative_float_figures(workspace: _Path) -> bool:
    # Every figure of the contract is an integer, a boolean or null.
    try:
        found = [False]

        def walk(x):
            if isinstance(x, float):
                found[0] = True
            elif isinstance(x, dict):
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        any_doc = False
        for n in REPORTS:
            doc = _load(OUT / n)
            if doc is not None:
                any_doc = True
                walk(doc)
        return any_doc and found[0]
    except Exception:
        return False


@criterion(description="the program writes reports for an extract with a required input file missing")
def negative_partial_output_on_missing_input(workspace: _Path) -> bool:
    # return_codes.ini is removed from a copy of an unseen extract; no report may appear.
    try:
        r = _run(TIER_C, "tier_c", "missing")
        if r is None or not r[0].is_dir():
            return False
        return any((r[0] / n).exists() for n in REPORTS)
    except Exception:
        return False


criteria.observation_scores_exact(weight=5)
criteria.observation_labels_exact(weight=5)
criteria.observation_identity_exact(weight=5)
criteria.metrics_exact(weight=5)
criteria.identity_triangle_closes(weight=5)
criteria.heldout_tier_a_exact(weight=5)
criteria.heldout_tier_b_exact(weight=5)
criteria.heldout_tier_large_exact(weight=5)
criteria.delinquency_bins_exact(weight=3)
criteria.bureau_bins_exact(weight=3)
criteria.obligor_bins_exact(weight=3)
criteria.exclusions_and_quarantine_exact(weight=3)
criteria.cut_instants_and_usage_exact(weight=3)
criteria.holidays_and_merges_exact(weight=3)
criteria.rejects_and_record_counts_exact(weight=3)
criteria.unresolved_and_partition_exact(weight=3)
criteria.breakdowns_exact(weight=3)
criteria.heldout_tier_c_exact(weight=3)
criteria.heldout_tier_d_exact(weight=5)
criteria.heldout_tier_f_exact(weight=5)
criteria.heldout_tier_g_exact(weight=5)
criteria.heldout_tier_h_exact(weight=5)
criteria.heldout_tier_i_exact(weight=5)
criteria.heldout_tier_j_exact(weight=3)
criteria.reports_parse_with_contract_keys(weight=1)
criteria.identity_self_report_matches(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reports_not_from_program(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_depends_on_directory_name(weight=-3)
criteria.negative_depends_on_record_order(weight=-3)
criteria.negative_writes_into_inputs(weight=-3)
criteria.negative_extra_output_files(weight=-1)
criteria.negative_float_figures(weight=-1)
criteria.negative_partial_output_on_missing_input(weight=-3)
