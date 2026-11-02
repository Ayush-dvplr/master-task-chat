"""Per-depot meter convention prototype (redesign G-8).

conv(seed, kind) -> inst with inst["dprice"] (true per-depot plan-day prices), inst["hist"]
(settled sessions), inst["old"] (older tariff versions), inst["k"] (true shifts).
A depot's meter applies to slot s the tariff price of slot (s + k_d) mod 96.
Fitters return a believed dprice per depot from the history only.
"""
import random

from gen_proto import gen, DEPOTS

S = 96


def bands_rng(rng):
    n = rng.randint(4, 6)
    edges = sorted(rng.sample(range(4, 92, 2), n - 1))
    edges = [0] + edges + [S]
    prices = [rng.randint(10, 40) for _ in range(n)]
    arr = []
    for i in range(n):
        arr += [prices[i]] * (edges[i + 1] - edges[i])
    return arr


def cents(tar, s0, L, r, k):
    return sum(r * tar[(s + k) % S] for s in range(s0, s0 + L))


def fits(tar_of_day, sess, k):
    return all(c == cents(tar_of_day[day], s0, L, r, k) for (day, s0, L, r, c) in sess)


def conv(seed, kind):
    inst = gen(seed, kind)
    rng = random.Random(seed * 104729 + {"shipped": 0, "hidden": 1, "large": 2}[kind])
    if kind == "shipped":
        ks = {d: 0 for d in DEPOTS}
    else:
        pool = list(range(4, 92))
        rng.shuffle(pool)
        ks = {d: pool[i] for i, d in enumerate(DEPOTS)}
    while True:
        old = [bands_rng(rng), bands_rng(rng)]
        tar_of_day = {day: old[0 if day < 7 else 1] for day in range(14)}
        hist = {d: [] for d in DEPOTS}
        for d in DEPOTS:
            for day in range(14):
                for _ in range(rng.randint(36, 44)):
                    L = rng.randint(1, 10)
                    s0 = rng.randint(0, S - L)
                    r = rng.choice([30, 45, 60])
                    hist[d].append((day, s0, L, r, cents(tar_of_day[day], s0, L, r, ks[d])))
        ok = True
        for d in DEPOTS:
            fit = [k for k in range(S) if fits(tar_of_day, hist[d], k)]
            if fit != [ks[d]]:
                ok = False
        if ok:
            break
    inst["k"] = ks
    inst["old"] = old
    inst["hist"] = hist
    inst["tod"] = tar_of_day
    inst["dprice"] = {d: [inst["price"][(s + ks[d]) % S] for s in range(S)] for d in DEPOTS}
    return inst


def shifted(inst, kd):
    return {d: [inst["price"][(s + kd[d]) % S] for s in range(S)] for d in DEPOTS}


def fit_identity(inst):
    return shifted(inst, {d: 0 for d in DEPOTS})


def fit_multiplier(inst):
    """(a) literal reader: identity if it agrees, else one ratio per depot applied to the tariff."""
    out = {}
    for d in DEPOTS:
        sess = inst["hist"][d]
        if fits(inst["tod"], sess, 0):
            out[d] = list(inst["price"])
            continue
        num = sum(c for (_, _, _, _, c) in sess)
        den = sum(cents(inst["tod"][day], s0, L, r, 0) for (day, s0, L, r, _) in sess)
        out[d] = [int(p * num / den + 0.5) for p in inst["price"]]
    return out


def resid(inst, d, pred):
    return sum((c - pred(day, s0, L, r)) ** 2 for (day, s0, L, r, c) in inst["hist"][d])


def fit_enum(inst):
    """(b) careful enumerator over readings nameable from the docs (no clock shift named)."""
    out = {}
    for d in DEPOTS:
        tod = inst["tod"]
        sess = inst["hist"][d]
        num = sum(c for (_, _, _, _, c) in sess)
        den = sum(cents(tod[day], s0, L, r, 0) for (day, s0, L, r, _) in sess)
        m = num / den
        cands = {
            "start_price": (lambda day, s0, L, r: cents(tod[day], s0, L, r, 0), [0]),
            "end_price": (lambda day, s0, L, r: cents(tod[day], s0, L, r, 1), [1]),
            "prev_price": (lambda day, s0, L, r: cents(tod[day], s0, L, r, -1), [-1]),
            "session_start": (lambda day, s0, L, r: r * L * tod[day][s0], [0]),
            "session_max": (lambda day, s0, L, r: r * L * max(tod[day][s0:s0 + L]), [0]),
            "session_min": (lambda day, s0, L, r: r * L * min(tod[day][s0:s0 + L]), [0]),
            "multiplier": (lambda day, s0, L, r: m * cents(tod[day], s0, L, r, 0), None),
        }
        best = min(cands, key=lambda n: resid(inst, d, cands[n][0]))
        if cands[best][1] is None:
            out[d] = [int(p * m + 0.5) for p in inst["price"]]
        else:
            k = cands[best][1][0]
            out[d] = [inst["price"][(s + k) % S] for s in range(S)]
    return out


def fit_shift_all(inst):
    """(b+) wide: every cyclic shift; the one that fits every settled session (= reference)."""
    kd = {}
    for d in DEPOTS:
        kd[d] = [k for k in range(S) if fits(inst["tod"], inst["hist"][d], k)][0]
    return shifted(inst, kd)


def fit_shift_firstday(inst):
    """H8: first shift that fits the depot's first settled day only."""
    kd = {}
    for d in DEPOTS:
        sess = [x for x in inst["hist"][d] if x[0] == 0]
        kd[d] = [k for k in range(S) if fits(inst["tod"], sess, k)][0]
    return shifted(inst, kd)


FITTERS = {
    "a_literal_multiplier": fit_multiplier,
    "b_enumerator": fit_enum,
    "c_fd98e12_tariff_as_stated": fit_identity,
    "d_shipped_convention": fit_identity,
    "h8_firstday_shift": fit_shift_firstday,
    "bplus_all_shifts": fit_shift_all,
}
