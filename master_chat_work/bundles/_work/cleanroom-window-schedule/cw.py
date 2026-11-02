"""WORK library: book model, exact solver with optimum counting, plan checker, wrong solvers.

Used by datagen.py and build checks only (never shipped)."""
import random

HORIZON = 1440


def gen_intervals(rng, n_jobs, max_overlap, dur_lo=30, dur_hi=180):
    while True:
        iv = []
        tries = 0
        while len(iv) < n_jobs and tries < 40000:
            tries += 1
            d = rng.randint(dur_lo, dur_hi)
            s = rng.randint(0, HORIZON - d)
            e = s + d
            pts = [s] + [a for a, b in iv if s <= a < e]
            if all(sum(1 for a, b in iv + [(s, e)] if a <= p < b) <= max_overlap for p in pts):
                iv.append((s, e))
        if len(iv) == n_jobs:
            return iv


def max_overlap(iv):
    return max((sum(1 for a, b in iv if a <= p < b) for p, _ in iv), default=0)


# ---------------------------------------------------------------- solver

def solve_night(night, bays, quals, before, crew=True, initial=True, gapcarry=True,
                use_quals=True, naive=False, count=True):
    """Exact sweep DP over jobs sorted by (start, job_id).

    bays: list of (bay_id, rate). before: {bay: family before the night}.
    Returns (net, plan {job_id: bay_id}, number_of_optimal_plans) or (None, None, 0)."""
    ids = [b for b, _ in bays]
    rate = dict(bays)
    jobs = sorted(night["jobs"], key=lambda j: (j["start"], j["job_id"]))
    fee = night["fee"]
    dmax = 0 if naive else max(c for _, c in fee.values())
    start = (tuple((before[b], None) for b in ids), -10 ** 6)
    states = {start: (0, 1, None)}
    hist = []

    def norm(lst, cf, s):
        out = tuple((f, (-1 if (e is not None and e <= s - dmax) else e)) for f, e in lst)
        return (out, -10 ** 6 if cf <= s - dmax else cf)

    for j in jobs:
        s, e, f = j["start"], j["end"], j["family"]
        new = {}

        def push(key, val, cnt, back):
            cur = new.get(key)
            if cur is None or val > cur[0]:
                new[key] = (val, cnt, back)
            elif val == cur[0]:
                new[key] = (val, cur[1] + cnt, cur[2])

        for key, (val, cnt, _) in states.items():
            lst, cf = key
            if j["job_id"] not in night["mand"]:
                push(norm(lst, cf, s), val, cnt, (key, None))
            for k, b in enumerate(ids):
                if use_quals and f not in quals[b]:
                    continue
                fam, end = lst[k]
                e0 = 0 if end is None else end
                if s < e0:
                    continue
                add = j["value"] - rate[b] * (e - s)
                ncf = cf
                if f != fam:
                    charge = True
                    if end is None and not initial:
                        charge = False
                    if end is not None and not gapcarry and s != end:
                        charge = False
                    if charge:
                        fe, d = fee[(fam, f)]
                        if s - d < e0:
                            continue
                        if crew and s - d < cf:
                            continue
                        ncf = s
                        add -= fe
                nl = list(lst)
                nl[k] = (f, e)
                push(norm(tuple(nl), ncf, s), val + add, cnt, (key, b))
        hist.append((j["job_id"], new))
        states = new
    if not states:
        return None, None, 0
    bestkey = max(states, key=lambda k: (states[k][0], repr(k)))
    best = states[bestkey][0]
    tot = sum(c for v, c, _ in states.values() if v == best)
    plan = {}
    key = bestkey
    for jid, st in reversed(hist):
        _, _, back = st[key]
        pk, b = back
        if b is not None:
            plan[jid] = b
        key = pk
    return best, plan, tot


# ---------------------------------------------------------------- checker

def evaluate(night, bays, quals, before, plan):
    """True-rule feasibility and net. Returns (ok, net, reason, crew_windows, after)."""
    rate = dict(bays)
    J = {j["job_id"]: j for j in night["jobs"]}
    for m in night["mand"]:
        if m not in plan:
            return False, None, "mandatory " + m, None, None
    net = 0
    windows = []
    after = dict(before)
    for b, _ in bays:
        seq = sorted((J[i] for i, x in plan.items() if x == b), key=lambda j: (j["start"], j["job_id"]))
        fam, end = before[b], None
        for j in seq:
            if j["family"] not in quals[b]:
                return False, None, "qualification " + j["job_id"], None, None
            e0 = 0 if end is None else end
            if j["start"] < e0:
                return False, None, "overlap " + j["job_id"], None, None
            if j["family"] != fam:
                fe, d = night["fee"][(fam, j["family"])]
                if j["start"] - d < e0:
                    return False, None, "bay busy in window " + j["job_id"], None, None
                windows.append((j["start"] - d, j["start"], b, j["job_id"]))
                net -= fe
            fam, end = j["family"], j["end"]
            net += j["value"] - rate[b] * (j["end"] - j["start"])
        after[b] = fam
    windows.sort()
    for w1, w2 in zip(windows, windows[1:]):
        if w2[0] < w1[1]:
            return False, None, "crew %s %s" % (w1[3], w2[3]), None, None
    return True, net, "", windows, after


def crossing_windows(night, bays, before, plan):
    """Master point 5: a later-starting job's crew window begins before an earlier-starting job's window."""
    J = {j["job_id"]: j for j in night["jobs"]}
    wins = []
    for b, _ in bays:
        seq = sorted((J[i] for i, x in plan.items() if x == b), key=lambda j: (j["start"], j["job_id"]))
        fam = before[b]
        for j in seq:
            if j["family"] != fam:
                wins.append((j["start"], j["start"] - night["fee"][(fam, j["family"])][1]))
            fam = j["family"]
    return any(s2 > s1 and a2 < a1 for s1, a1 in wins for s2, a2 in wins)


# ---------------------------------------------------------------- wrong solvers (night level)

def greedy_density(night, bays, quals, before):
    J = sorted(night["jobs"], key=lambda j: (j["job_id"] not in night["mand"],
                                             -j["value"] / (j["end"] - j["start"]), j["job_id"]))
    plan, cur = {}, 0
    nm = dict(night, mand=set())
    for j in J:
        best = None
        for b, _ in bays:
            p = dict(plan)
            p[j["job_id"]] = b
            ok, net, *_ = evaluate(nm, bays, quals, before, p)
            if ok and (best is None or net > best[0]):
                best = (net, b)
        if best and (best[0] > cur or j["job_id"] in night["mand"]):
            plan[j["job_id"]] = best[1]
            cur = best[0]
    return plan


def local_search(night, bays, quals, before, plan):
    def val(p):
        ok, net, *_ = evaluate(night, bays, quals, before, p)
        return net if ok else None
    cur = val(plan)
    if cur is None:
        return plan
    ids = [j["job_id"] for j in night["jobs"]]
    improved = True
    while improved:
        improved = False
        for a in ids:
            opts = []
            if a in plan:
                if a not in night["mand"]:
                    p = dict(plan)
                    del p[a]
                    opts.append(p)
                for b, _ in bays:
                    if b != plan[a]:
                        p = dict(plan)
                        p[a] = b
                        opts.append(p)
                if a not in night["mand"]:
                    for c in ids:
                        if c not in plan:
                            for b, _ in bays:
                                p = dict(plan)
                                del p[a]
                                p[c] = b
                                opts.append(p)
            else:
                for b, _ in bays:
                    p = dict(plan)
                    p[a] = b
                    opts.append(p)
            for p in opts:
                v = val(p)
                if v is not None and v > cur:
                    plan, cur, improved = p, v, True
                    break
    return plan


def lane_by_lane(night, bays, quals, before):
    plan, taken = {}, set()
    for b, r in bays:
        sub = dict(night, jobs=[j for j in night["jobs"] if j["job_id"] not in taken], mand=set())
        _, p, _ = solve_night(sub, [(b, r)], quals, before, crew=False, count=False)
        plan.update(p or {})
        taken |= set(p or {})
    return plan


VARIANTS = {
    "greedy": lambda n, B, Q, f: greedy_density(n, B, Q, f),
    "greedy_ls": lambda n, B, Q, f: local_search(n, B, Q, f, greedy_density(n, B, Q, f)),
    "lane_by_lane": lambda n, B, Q, f: lane_by_lane(n, B, Q, f),
    "flow_relax": lambda n, B, Q, f: solve_night(n, B, Q, f, crew=False, use_quals=False, count=False)[1],
    "no_initial": lambda n, B, Q, f: solve_night(n, B, Q, f, initial=False, count=False)[1],
    "touching_only": lambda n, B, Q, f: solve_night(n, B, Q, f, gapcarry=False, count=False)[1],
    "no_crew": lambda n, B, Q, f: solve_night(n, B, Q, f, crew=False, count=False)[1],
    "naive_collapse": lambda n, B, Q, f: solve_night(n, B, Q, f, naive=True, count=False)[1],
}


def run_book(book, solver, carry=True):
    """Runs nights in date order. Returns list of (night_id, plan or None for rejected)."""
    bays = [(b["bay_id"], b["minute_rate"]) for b in book["bays"]]
    init = {b["bay_id"]: b["initial_family"] for b in book["bays"]}
    fam = dict(init)
    out = []
    for n in book["order"]:
        if n["reject"]:
            out.append((n["night_id"], None))
            continue
        before = dict(fam if carry else init)
        p = solver(n, bays, book["quals"], before) or {}
        out.append((n["night_id"], p))
        J = {j["job_id"]: j for j in n["jobs"]}
        for b, _ in bays:
            seq = sorted((J[i] for i, x in p.items() if x == b), key=lambda j: (j["start"], j["job_id"]))
            if seq:
                fam[b] = seq[-1]["family"]
    return out


def ref_solver(n, B, Q, f):
    return solve_night(n, B, Q, f, count=False)[1]


def true_eval_book(book, runs):
    """Evaluate a sequence of plans under true rules with the carry the plans themselves produce."""
    bays = [(b["bay_id"], b["minute_rate"]) for b in book["bays"]]
    fam = {b["bay_id"]: b["initial_family"] for b in book["bays"]}
    res = []
    for n, (nid, p) in zip(book["order"], runs):
        if p is None:
            res.append(None)
            continue
        ok, net, why, _, after = evaluate(n, bays, book["quals"], fam, p)
        res.append(net if ok else "INF:" + why)
        if ok:
            fam = after
        else:
            J = {j["job_id"]: j for j in n["jobs"]}
            for b, _ in bays:
                seq = sorted((J[i] for i, x in p.items() if x == b), key=lambda j: (j["start"], j["job_id"]))
                if seq:
                    fam[b] = seq[-1]["family"]
    return res
