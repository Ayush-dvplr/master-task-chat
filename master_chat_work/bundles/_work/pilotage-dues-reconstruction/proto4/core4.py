"""Try-4 core: anchor-type station conventions.

A station's conventions say which record each charge is anchored to:
  cal   which holiday calendar applies to a visit: 'flag' (vessel flag state),
        'agent' (city of the vessel agent's office) or 'cal:<name>' (one calendar for
        every visit of the station; the port calendar is cal:<station lower>)
  hrs   which hours are surcharge hours: 'watch' (station night watch),
        'office' (outside station office hours), 'agent' (outside the agent's office hours)
  time  which recorded time of the visit is read: 'order', 'board', 'release'
  draft which draft: 'measured' (BOARD), 'declared' (ORDER), 'register' (max_draft)
  ton   which tonnage: 'gross', 'net'
"""
from datetime import date, timedelta
from itertools import product

B_LIST = [180, 195, 210, 225, 240]      # cents per 100 tonnes
D_LIST = [250, 300, 350, 400]           # cents per started tenth above 6.0 m
N_LIST = [125, 140, 150]                # surcharge factor x100
T_LIST = [3500, 5000, 6500]             # cents per tug
ASSIST = 4000                           # cents per started 30 minutes
TARIFFS = list(product(B_LIST, D_LIST, N_LIST, T_LIST))
STATIONS = ["North", "South", "West", "East"]
D0 = date(2026, 7, 1)
NDAYS = 92
HEAD = {"cal": None, "hrs": "watch", "time": "board", "draft": "measured", "ton": "gross"}
HRS = ("watch", "office", "agent")
TIMES = ("order", "board", "release")
DRAFTS = ("measured", "declared", "register")
TONS = ("gross", "net")


def rhe(n, d):
    q, r = divmod(n, d)
    if 2 * r > d or (2 * r == d and q % 2):
        q += 1
    return q


def inwin(m, a, b):
    return a <= m < b if a < b else (m >= a or m < b)


def calendar_of(opt, v, ctx):
    if opt == "flag":
        return v["flag"]
    if opt == "agent":
        return ctx["agents"][v["agent"]][0]
    return opt[4:]


def window_of(opt, v, ctx):
    if opt == "watch":
        return ctx["watch"][v["station"]]
    if opt == "office":
        o, c = ctx["office"][v["station"]]
        return (c, o)
    _, o, c = ctx["agents"][v["agent"]]
    return (c, o)


def surcharged(v, c, h, t, ctx):
    day, minute = v[t]
    a, b = window_of(h, v, ctx)
    return inwin(minute, a, b) or day in ctx["cals"].get(calendar_of(c, v, ctx), ())


def draft_cm(v, d):
    return {"measured": v["cm"], "declared": v["decl_cm"], "register": v["max_cm"]}[d]


def base(t, v, g, d):
    b, dd, _n, T = t
    tenths = -(-draft_cm(v, d) // 10)
    return (rhe(b * v[g], 100) + dd * max(0, tenths - 60) + T * v["tugs"]
            + ASSIST * (-(-v["assist"] // 30)))


def amount(t, v, conv, ctx):
    if v.get("exempt"):
        return 0
    s = base(t, v, conv["ton"], conv["draft"])
    if surcharged(v, conv["cal"], conv["hrs"], conv["time"], ctx):
        s += rhe((t[2] - 100) * s, 100)
    return s


def full_domain(ctx):
    cals = ["flag", "agent"] + ["cal:" + k for k in sorted(ctx["cals"])]
    return {"cal": cals, "hrs": list(HRS), "time": list(TIMES), "draft": list(DRAFTS),
            "ton": list(TONS)}


def fit(groups, ctx, dom, tariffs=TARIFFS):
    """groups: per-period lists of visits with 'amount' (cents). Returns
    [(conv, [sorted tariff list per period])] for every conv under which every
    period keeps at least one tariff."""
    req = {}
    for g in dom["ton"]:
        for d in dom["draft"]:
            per = []
            for grp in groups:
                ok = []
                for t in tariffs:
                    need = []
                    for v in grp:
                        a0 = base(t, v, g, d)
                        if v["amount"] == a0:
                            need.append(0)
                        elif v["amount"] == a0 + rhe((t[2] - 100) * a0, 100):
                            need.append(1)
                        else:
                            break
                    else:
                        ok.append((t, tuple(need)))
                per.append(ok)
            req[(g, d)] = per
    out = []
    for c, h, tm in product(dom["cal"], dom["hrs"], dom["time"]):
        vecs = [tuple(1 if surcharged(v, c, h, tm, ctx) else 0 for v in grp) for grp in groups]
        for (g, d), per in req.items():
            lists = []
            for vec, ok in zip(vecs, per):
                ts = sorted(t for t, nd in ok if nd == vec)
                if not ts:
                    break
                lists.append(ts)
            else:
                out.append(({"cal": c, "hrs": h, "time": tm, "draft": d, "ton": g}, lists))
    return out


def day_min(dt):
    return (dt.date(), dt.hour * 60 + dt.minute)


def days():
    return [D0 + timedelta(days=i) for i in range(NDAYS)]
