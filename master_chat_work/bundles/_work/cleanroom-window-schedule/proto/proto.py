"""Phase 0 prototype: generator, exact reference, baselines, uniqueness, timing."""
import random, time, sys, itertools

FAMS = ["F1", "F2", "F3"]
DURS = [[15, 20, 25, 30, 35, 40, 45]]
FEES = [(40, 250)]


def gen_night(rng, n_jobs, n_lanes=3, horizon=1440, max_overlap=7):
    while True:
        jobs = []
        tries = 0
        while len(jobs) < n_jobs and tries < 20000:
            tries += 1
            dur = rng.randint(30, 180)
            s = rng.randint(0, horizon - dur)
            e = s + dur
            cand = jobs + [(s, e)]
            # max overlap check at point s..e
            pts = sorted({x for a, b in cand for x in (a,)})
            ok = True
            for p in pts:
                if p < s or p >= e:
                    continue
                if sum(1 for a, b in cand if a <= p < b) > max_overlap:
                    ok = False
                    break
            if ok and sum(1 for a, b in cand if a <= s < b) <= max_overlap:
                jobs.append((s, e))
        if len(jobs) == n_jobs:
            break
    lanes = ["L%d" % (i + 1) for i in range(n_lanes)]
    qual = {}
    for ln in lanes:
        k = rng.choice([2, 3, 3])
        qual[ln] = set(rng.sample(FAMS, k))
    for f in FAMS:
        if not any(f in q for q in qual.values()):
            qual[rng.choice(lanes)].add(f)
    init = {ln: rng.choice(sorted(qual[ln])) for ln in lanes}
    rate = dict(zip(lanes, rng.sample([1, 2, 3, 4], n_lanes)))
    fee = {}
    dur = {}
    for a in FAMS:
        for b in FAMS:
            if a != b:
                fee[(a, b)] = rng.randint(*FEES[0])
                dur[(a, b)] = rng.choice(DURS[0])
    J = []
    for i, (s, e) in enumerate(jobs):
        f = rng.choice(FAMS)
        v = rng.randint(200, 900)
        J.append(dict(id="J%03d" % i, s=s, e=e, v=v, f=f))
    # mandatory: pick 2-4 jobs, verify later feasibility via DP
    mand = set(j["id"] for j in rng.sample(J, rng.randint(2, 4)))
    return dict(jobs=J, lanes=lanes, qual=qual, init=init, rate=rate, fee=fee, dur=dur, mand=mand, horizon=horizon)


def evaluate(night, plan, crew=True, initial=True, gapcarry=True):
    """plan: dict job id -> lane. returns (feasible, net, reason)."""
    J = {j["id"]: j for j in night["jobs"]}
    for m in night["mand"]:
        if m not in plan:
            return False, None, "mandatory " + m
    net = 0
    windows = []
    for ln in night["lanes"]:
        seq = sorted((J[i] for i, l in plan.items() if l == ln), key=lambda j: (j["s"], j["id"]))
        fam = night["init"][ln]
        end = 0
        first = True
        for j in seq:
            if j["f"] not in night["qual"][ln]:
                return False, None, "qual"
            if j["s"] < end:
                return False, None, "overlap"
            if j["f"] != fam:
                charge = True
                if first and not initial:
                    charge = False
                if not first and not gapcarry and j["s"] != end:
                    charge = False
                if charge:
                    d = night["dur"][(fam, j["f"])]
                    if j["s"] - d < end or j["s"] - d < 0:
                        return False, None, "lane busy in changeover"
                    windows.append((j["s"] - d, j["s"]))
                    net -= night["fee"][(fam, j["f"])]
            fam = j["f"]
            end = j["e"]
            first = False
            net += j["v"] - night["rate"][ln] * (j["e"] - j["s"])
    if crew:
        windows.sort()
        for (a, b), (c, d) in zip(windows, windows[1:]):
            if c < b:
                return False, None, "crew"
    return True, net, ""


def solve_dp(night, crew=True, initial=True, gapcarry=True, quals=True, count=False):
    """Exact sweep DP. state per lane (fam, end) + crew_free. Returns (net, plan, count)."""
    lanes = night["lanes"]
    jobs = sorted(night["jobs"], key=lambda j: (j["s"], j["id"]))
    dmax = max(night["dur"].values())
    start = tuple((night["init"][ln], -10**6 if initial else None) for ln in lanes)
    # end marker: None = no job yet (initial charge applies if initial), else end time
    start = tuple((night["init"][ln], None) for ln in lanes)
    states = {(start, -10**6): (0, 1, None)}
    hist = []
    for j in jobs:
        s = j["s"]
        new = {}
        def push(key, val, cnt, back):
            cur = new.get(key)
            if cur is None or val > cur[0]:
                new[key] = (val, cnt, back)
            elif val == cur[0]:
                new[key] = (val, cur[1] + cnt, cur[2])
        for key, (val, cnt, _) in states.items():
            lst, cf = key
            # reject
            if j["id"] not in night["mand"]:
                push(norm(lst, cf, s, dmax), val, cnt, (key, None))
            for k, ln in enumerate(lanes):
                if quals and j["f"] not in night["qual"][ln]:
                    continue
                fam, end = lst[k]
                e0 = 0 if end is None else end
                if s < e0:
                    continue
                add = j["v"] - night["rate"][ln] * (j["e"] - j["s"])
                ncf = cf
                if j["f"] != fam:
                    charge = True
                    if end is None and not initial:
                        charge = False
                    if end is not None and not gapcarry and s != end:
                        charge = False
                    if charge:
                        d = night["dur"][(fam, j["f"])]
                        if s - d < e0 or s - d < 0:
                            continue
                        if crew and s - d < cf:
                            continue
                        ncf = s
                        add -= night["fee"][(fam, j["f"])]
                nl = list(lst)
                nl[k] = (j["f"], j["e"])
                push(norm(tuple(nl), ncf, s, dmax), val + add, cnt, (key, ln))
        hist.append((j["id"], new))
        states = new
    if not states:
        return None, None, 0
    bestkey = max(states, key=lambda k: states[k][0])
    best = states[bestkey][0]
    tot = sum(c for v, c, _ in states.values() if v == best)
    # reconstruct
    plan = {}
    key = bestkey
    for jid, st in reversed(hist):
        val, cnt, back = st[key]
        pk, ln = back
        if ln is not None:
            plan[jid] = ln
        key = pk
    return best, plan, tot


NAIVE = [False]
def norm(lst, cf, s, dmax):
    if NAIVE[0]:
        dmax = 0
    # times at or before s - dmax can never block a later job (later starts >= s)
    out = []
    for fam, end in lst:
        if end is not None and end <= s - dmax:
            end = -1
        out.append((fam, end))
    if cf <= s - dmax:
        cf = -10**6
    return (tuple(out), cf)


def greedy_density(night):
    J = sorted(night["jobs"], key=lambda j: (j["id"] not in night["mand"], -j["v"] / (j["e"] - j["s"]), j["id"]))
    plan = {}
    cur = 0
    for j in J:
        best = None
        for ln in night["lanes"]:
            p = dict(plan); p[j["id"]] = ln
            ok, net, _ = evaluate(dict(night, mand=set()), p)
            if ok and (best is None or net > best[0]):
                best = (net, ln)
        if best and (best[0] > cur or j["id"] in night["mand"]):
            plan[j["id"]] = best[1]
            cur = best[0]
    return plan


def local_search(night, plan):
    def val(p):
        ok, net, _ = evaluate(night, p)
        return net if ok else None
    cur = val(plan)
    if cur is None:
        return plan
    ids = [j["id"] for j in night["jobs"]]
    improved = True
    while improved:
        improved = False
        for a in ids:
            opts = []
            if a in plan:
                if a not in night["mand"]:
                    p = dict(plan); del p[a]; opts.append(p)
                for ln in night["lanes"]:
                    if ln != plan[a]:
                        p = dict(plan); p[a] = ln; opts.append(p)
                for b in ids:
                    if b not in plan:
                        for ln in night["lanes"]:
                            if a in night["mand"]:
                                continue
                            p = dict(plan); del p[a]; p[b] = ln; opts.append(p)
            else:
                for ln in night["lanes"]:
                    p = dict(plan); p[a] = ln; opts.append(p)
            for p in opts:
                v = val(p)
                if v is not None and v > cur:
                    plan, cur, improved = p, v, True
                    break
    return plan


def lane_by_lane(night):
    plan = {}
    rest = dict(night)
    taken = set()
    for ln in night["lanes"]:
        sub = dict(night, lanes=[ln], jobs=[j for j in night["jobs"] if j["id"] not in taken], mand=set())
        # crew windows of earlier lanes ignored by per-lane solve (natural reading)
        _, p, _ = solve_dp(sub, crew=False)
        plan.update(p)
        taken |= set(p)
    return plan


def main():
    seed0 = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    for r in range(reps):
        rng = random.Random(seed0 * 1000 + r)
        night = gen_night(rng, n)
        t = time.time()
        best, plan, cnt = solve_dp(night)
        dt = time.time() - t
        if best is None:
            print(r, "infeasible"); continue
        ok, net, why = evaluate(night, plan)
        assert ok and net == best, (ok, net, best, why)
        row = [f"seed{r} n={n} opt={best} count={cnt} t={dt:.2f}s acc={len(plan)}"]
        for name, fn in [("greedy", lambda: greedy_density(night)),
                         ("greedy+ls", lambda: local_search(night, greedy_density(night))),
                         ("nocrew", lambda: solve_dp(night, crew=False)[1]),
                         ("noinit", lambda: solve_dp(night, initial=False)[1]),
                         ("nogap", lambda: solve_dp(night, gapcarry=False)[1]),
                         ("noqual", lambda: solve_dp(night, quals=False, crew=False)[1]),
                         ("lanebylane", lambda: lane_by_lane(night))]:
            p = fn()
            ok, net, why = evaluate(night, p) if p is not None else (False, None, "none")
            row.append(f"{name}={'%d' % net if ok else 'INF:' + why}")
        print(" ".join(row), flush=True)


if __name__ == "__main__":
    main()
