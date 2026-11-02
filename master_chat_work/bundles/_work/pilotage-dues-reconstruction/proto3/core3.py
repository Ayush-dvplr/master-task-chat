"""L-CONV prototype core v3 (proto only; never shipped).

Station conventions (domains implied by their units, never listed in docs):
  kA  assist mark: part 30-minute block charged when its minutes reach kA (1..30; 30 = never)
  kD  draft mark: part tenth of a metre billed when its centimetres reach kD (1..10; 10 = never)
  B   surcharge base includes the assist line
  H   calendar kept (a key of holidays.json)
  S   Monday after a Sunday holiday also kept
  N   surcharge hours [start, end) in minutes of day, start != end, passing midnight when end < start
"""
from datetime import date, timedelta
from itertools import product

B_LIST = [180, 195, 210, 225, 240]
D_LIST = [250, 300, 350, 400]
N_LIST = [125, 140, 150]
T_LIST = [3500, 5000, 6500]
ASSIST_RATE = 4000
TARIFFS = list(product(B_LIST, D_LIST, N_LIST, T_LIST))
STATIONS = ["North", "South", "West", "East"]
KA_ALL = list(range(1, 31))
KD_ALL = list(range(1, 11))
HEADLINE = {"kA": 1, "kD": 1, "S": True, "B": True, "N": (1320, 360)}
D0 = date(2026, 7, 1)
NDAYS = 92
DAY = 1440


def rhe(num, den):
    q, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and q % 2 == 1):
        return q + 1
    return q


def blocks(minutes, kA):
    q, r = divmod(minutes, 30)
    return q + (1 if r and r >= kA else 0)


def tenths(cm, kD):
    q, r = divmod(cm, 10)
    return q + (1 if r and r >= kD else 0)


def in_window(m, w):
    s, e = w
    return s <= m < e if s < e else (m >= s or m < e)


def holiday(day, cal, S):
    if day in cal:
        return True
    return S and day.weekday() == 0 and (day - timedelta(days=1)) in cal


def due(t, v, c, flag):
    b, d, n, tt = t
    l1 = rhe(b * v["gt"], 100)
    l2 = d * max(0, tenths(v["cm"], c["kD"]) - 60)
    l3 = tt * v["tugs"]
    l4 = ASSIST_RATE * blocks(v["assist"], c["kA"])
    base = l1 + l2 + l3 + (l4 if c["B"] else 0)
    l5 = rhe((n - 100) * base, 100) if flag else 0
    return l1 + l2 + l3 + l4 + l5


def surcharged(v, c, cals):
    return holiday(v["day"], cals[c["H"]], c["S"]) or in_window(v["minute"], c["N"])


def true_due(t, v, c, cals):
    if v.get("exempt"):
        return 0
    return due(t, v, c, surcharged(v, c, cals))


def arc(a, b):
    """minutes a, a+1, ..., b (inclusive), circular."""
    out = []
    m = a % DAY
    while True:
        out.append(m)
        if m == b % DAY:
            return out
        m = (m + 1) % DAY


def windows(IN, OUT):
    """Set of windows [s,e) containing every IN minute and no OUT minute.
    Returns None (no window), 'many' (unbounded side), or (Sset, Eset) rectangle."""
    if IN & OUT:
        return None
    if not IN or not OUT:
        return "many"
    pts = sorted(IN | OUT)
    lab = [p in IN for p in pts]
    n = len(pts)
    starts = [i for i in range(n) if lab[i] and not lab[i - 1]]
    if len(starts) != 1:
        return None
    i0 = starts[0]
    i1 = i0
    while lab[(i1 + 1) % n]:
        i1 = (i1 + 1) % n
    prev_o = pts[i0 - 1]
    next_o = pts[(i1 + 1) % n]
    return (frozenset(arc(prev_o + 1, pts[i0])), frozenset(arc(pts[i1] + 1, next_o)))


def count_windows(rects):
    rects = [r for r in rects if r is not None]
    if not rects:
        return 0, set()
    if any(r == "many" for r in rects):
        return 10 ** 9, None
    uniq = list(set(rects))
    if sum(len(a) * len(b) for a, b in uniq) > 400000:
        return 10 ** 9, None
    pts = set()
    for a, b in uniq:
        for s in a:
            for e in b:
                pts.add((s, e))
    return len(pts), pts


def fit(groups, cals, domA=KA_ALL, domD=KD_ALL, domB=(True, False), domH=None, domS=(True, False),
        win_filter=None, tariffs=TARIFFS):
    """groups: per period list of paid invoices (non-exempt, accepted).
    Returns list of (conv dict, per-period tariff lists) for every convention choice that leaves every
    period with at least one tariff. win_filter(s, e) -> bool restricts the window domain."""
    domH = list(cals) if domH is None else domH
    per_period = []
    for inv in groups:
        surv = []
        for t in tariffs:
            b, d, n, tt = t
            opts = []
            ok = True
            for v in inv:
                o = {}
                qa, ra = divmod(v["assist"], 30)
                qd, rd = divmod(v["cm"], 10)
                l1 = rhe(b * v["gt"], 100)
                l3 = tt * v["tugs"]
                for upd in ((0, 1) if rd else (0,)):
                    l2 = d * max(0, qd + upd - 60)
                    for upa in ((0, 1) if ra else (0,)):
                        l4 = ASSIST_RATE * (qa + upa)
                        s0 = l1 + l2 + l3 + l4
                        for B in domB:
                            base = l1 + l2 + l3 + (l4 if B else 0)
                            if v["amount"] == s0:
                                o[(upd, upa, B)] = 0
                            elif v["amount"] == s0 + rhe((n - 100) * base, 100):
                                o[(upd, upa, B)] = 1
                if not o:
                    ok = False
                    break
                opts.append((o, ra, rd))
            if ok:
                surv.append((t, opts))
        per_period.append(surv)
    results = []
    for kA in domA:
        for kD in domD:
            for B in domB:
                pp = []
                for inv, surv in zip(groups, per_period):
                    lst = []
                    for t, opts in surv:
                        flags = []
                        for o, ra, rd in opts:
                            f = o.get((1 if rd and rd >= kD else 0, 1 if ra and ra >= kA else 0, B))
                            if f is None:
                                break
                            flags.append(f)
                        else:
                            lst.append((t, flags))
                    if not lst:
                        break
                    pp.append(lst)
                else:
                    for H in domH:
                        for S in domS:
                            pph = []
                            for inv, lst in zip(groups, pp):
                                hol = [holiday(v["day"], cals[H], S) for v in inv]
                                l2 = []
                                for t, flags in lst:
                                    IN, OUT = set(), set()
                                    good = True
                                    for v, f, h in zip(inv, flags, hol):
                                        if h:
                                            if not f:
                                                good = False
                                                break
                                        elif f:
                                            IN.add(v["minute"])
                                        else:
                                            OUT.add(v["minute"])
                                    if good:
                                        l2.append((t, IN, OUT))
                                if not l2:
                                    break
                                pph.append(l2)
                            else:
                                combos = []
                                for choice in product(*pph):
                                    IN = set().union(*[c[1] for c in choice])
                                    OUT = set().union(*[c[2] for c in choice])
                                    w = windows(IN, OUT)
                                    if w is not None:
                                        combos.append(([c[0] for c in choice], w))
                                if not combos:
                                    continue
                                cnt, pts = count_windows([w for _, w in combos])
                                if pts is not None and win_filter is not None:
                                    pts = {p for p in pts if win_filter(*p)}
                                    cnt = len(pts)
                                if cnt == 0:
                                    continue
                                if pts is None:
                                    results.append(({"kA": kA, "kD": kD, "B": B, "H": H, "S": S,
                                                     "N": None, "count": cnt}, None))
                                    continue
                                for p in sorted(pts):
                                    per = [set() for _ in groups]
                                    for ts, w in combos:
                                        if w != "many" and p[0] in w[0] and p[1] in w[1]:
                                            for i, t in enumerate(ts):
                                                per[i].add(t)
                                    results.append(({"kA": kA, "kD": kD, "B": B, "H": H, "S": S,
                                                     "N": p, "count": 1},
                                                    [sorted(x) for x in per]))
    return results


def n_conventions(results):
    return sum(c["count"] for c, _ in results)
