"""L-CONV prototype core (proto only; never shipped).

Conventions per station (stated domain, readings never listed per station):
  kA  part assist block counted when its minutes reach kA, kA in 1..30 (30 = never)
  kD  part tenth of draft billed up when its centimetres reach kD, kD in 1..10 (10 = never)
  S   Sunday holiday also kept on the Monday: True / False
  B   surcharge reckoned on the assist line too: True / False
  H   holiday calendar kept: one of CALENDARS
  N   surcharge hours (start, end) as minutes of day on quarter hours, start != end
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
CALENDARS = ["national", "north", "south", "west", "east", "harbour", "fishery"]
OWN = {"North": "north", "South": "south", "West": "west", "East": "east"}
KA_ALL = list(range(1, 31))
KD_ALL = list(range(1, 11))
S_ALL = [True, False]
B_ALL = [True, False]
Q_ALL = [(s, e) for s in range(0, 1440, 15) for e in range(0, 1440, 15) if s != e]
HEADLINE = {"kA": 1, "kD": 1, "S": True, "B": True, "N": (1320, 360)}
D0 = date(2026, 7, 1)
NDAYS = 92


def rhe(num, den):
    q, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and q % 2 == 1):
        return q + 1
    return q


def blocks(minutes, kA):
    q, r = divmod(minutes, 30)
    return q + (1 if r and r >= kA else 0)


def tenth(cm, kD):
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
    l2 = d * max(0, tenth(v["draft_cm"], c["kD"]) - 60)
    l3 = tt * v["tugs"]
    l4 = ASSIST_RATE * blocks(v["assist"], c["kA"])
    base = l1 + l2 + l3 + (l4 if c["B"] else 0)
    l5 = rhe((n - 100) * base, 100) if flag else 0
    return l1 + l2 + l3 + l4 + l5


def vday(v):
    return date.fromisoformat(v["board"][:10])


def vmin(v):
    return int(v["board"][11:13]) * 60 + int(v["board"][14:16])


def surcharged(v, c, cals):
    return holiday(vday(v), cals[c["H"]], c["S"]) or in_window(vmin(v), c["N"])


def true_due(t, v, c, cals):
    return due(t, v, c, surcharged(v, c, cals))


def period_of(v, starts):
    d = vday(v)
    k = 0
    for i, s in enumerate(starts):
        if d >= s:
            k = i
    return k


def fit(st, cals, domA=KA_ALL, domD=KD_ALL, domS=S_ALL, domB=B_ALL, domH=CALENDARS,
        wins=Q_ALL, tariffs=TARIFFS):
    """Return {conv_key: [per-period list of tariffs]} for every convention combination
    under which every period has at least one tariff reproducing all its paid invoices.
    conv_key = (kA, kD, B, H, S, window)."""
    starts = [date.fromisoformat(p) for p in st["period_starts"]]
    groups = [[] for _ in starts]
    for v in st["paid"]:
        groups[period_of(v, starts)].append(v)
    # window masks per invoice
    wmask = {}
    for v in st["paid"]:
        m = vmin(v)
        if m not in wmask:
            x = 0
            for i, w in enumerate(wins):
                if in_window(m, w):
                    x |= 1 << i
            wmask[m] = x
    full = (1 << len(wins)) - 1
    per_period = []
    for inv in groups:
        found = {}  # (kA,kD,B,H,S) -> list of (t, mask)
        for t in tariffs:
            opts = []
            for v in inv:
                o = {}
                qa, ra = divmod(v["assist"], 30)
                qd, rd = divmod(v["draft_cm"], 10)
                for upd in ((0, 1) if rd else (0,)):
                    for upa in ((0, 1) if ra else (0,)):
                        for B in domB:
                            b, d, n, tt = t
                            l1 = rhe(b * v["gt"], 100)
                            l2 = d * max(0, qd + upd - 60)
                            l3 = tt * v["tugs"]
                            l4 = ASSIST_RATE * (qa + upa)
                            base = l1 + l2 + l3 + (l4 if B else 0)
                            s0 = l1 + l2 + l3 + l4
                            if v["amount"] == s0:
                                o[(upd, upa, B)] = 0
                            elif v["amount"] == s0 + rhe((n - 100) * base, 100):
                                o[(upd, upa, B)] = 1
                if not o:
                    opts = None
                    break
                opts.append((o, ra, rd))
            if opts is None:
                continue
            for kA in domA:
                for kD in domD:
                    for B in domB:
                        flags = []
                        ok = True
                        for o, ra, rd in opts:
                            key = (1 if rd and rd >= kD else 0, 1 if ra and ra >= kA else 0, B)
                            f = o.get(key)
                            if f is None:
                                ok = False
                                break
                            flags.append(f)
                        if not ok:
                            continue
                        for H in domH:
                            for S in domS:
                                m = full
                                for v, f in zip(inv, flags):
                                    if holiday(vday(v), cals[H], S):
                                        if not f:
                                            m = 0
                                            break
                                    else:
                                        m &= wmask[vmin(v)] if f else (full ^ wmask[vmin(v)])
                                        if not m:
                                            break
                                if m:
                                    found.setdefault((kA, kD, B, H, S), []).append((t, m))
        per_period.append(found)
    out = {}
    keys = set(per_period[0]) if per_period else set()
    for f in per_period[1:]:
        keys &= set(f)
    for k in keys:
        m = full
        for f in per_period:
            u = 0
            for _, x in f[k]:
                u |= x
            m &= u
        i = 0
        while m:
            if m & 1:
                w = wins[i]
                out[k + (w,)] = [[t for t, x in f[k] if (x >> i) & 1] for f in per_period]
            m >>= 1
            i += 1
    return out


def conv_of(key):
    kA, kD, B, H, S, w = key
    return {"kA": kA, "kD": kD, "B": B, "H": H, "S": S, "N": w}


def recompute(st, cals, conv, tariffs_by_period):
    """tariffs_by_period: list of tariff tuples or None (unresolved)."""
    starts = [date.fromisoformat(p) for p in st["period_starts"]]
    res = {}
    for v in st["disputed"]:
        t = tariffs_by_period[period_of(v, starts)] if conv is not None else None
        res[v["id"]] = None if t is None else true_due(t, v, conv, cals)
    return res
