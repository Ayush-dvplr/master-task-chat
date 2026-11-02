"""Book-level survey: nights carry bay families forward. Baseline losses per hidden book."""
import random, sys, time, signal
import proto

class TO(Exception):
    pass

def _h(*a):
    raise TO()

signal.signal(signal.SIGALRM, _h)

BOOKS = {
    "H1_dense": dict(nights=5, n=(64, 72), ov=7, durs=[30, 35, 40, 45, 50, 55, 60], fees=(20, 120)),
    "H2_carry": dict(nights=8, n=(20, 48), ov=6, durs=[20, 25, 30, 35, 40, 45], fees=(40, 200)),
    "H3_wide": dict(nights=6, n=(48, 72), ov=7, durs=[25, 30, 40, 50, 60], fees=(30, 160)),
}


def gen_book(rng, spec):
    proto.DURS[0] = spec["durs"]
    proto.FEES[0] = spec["fees"]
    base = proto.gen_night(rng, 4, max_overlap=spec["ov"])
    nights = []
    for k in range(spec["nights"]):
        while True:
            nt = proto.gen_night(rng, rng.randint(*spec["n"]), max_overlap=spec["ov"])
            nt.update(lanes=base["lanes"], qual=base["qual"], rate=base["rate"])
            nights.append(nt)
            break
    return base["init"], nights


def end_fams(night, plan, init):
    out = dict(init)
    J = {j["id"]: j for j in night["jobs"]}
    for ln in night["lanes"]:
        seq = sorted((J[i] for i, l in plan.items() if l == ln), key=lambda j: j["s"])
        if seq:
            out[ln] = seq[-1]["f"]
    return out


def run_book(init, nights, solver, carry=True):
    fam = dict(init)
    plans = []
    for nt in nights:
        n2 = dict(nt, init=dict(fam if carry else init))
        p = solver(n2)
        plans.append(p)
        if p is None:
            p = {}
        fam = end_fams(n2, p, fam)
    return plans


def true_eval(init, nights, plans):
    """evaluate wrong plans under true rules with true carry (carry follows the plan actually run)."""
    fam = dict(init)
    res = []
    for nt, p in zip(nights, plans):
        n2 = dict(nt, init=dict(fam))
        if p is None:
            res.append(("NONE", None)); continue
        ok, net, why = proto.evaluate(n2, p)
        res.append((net if ok else "INF:" + why, p))
        fam = end_fams(n2, p, fam)
    return res


def main():
    seed = int(sys.argv[1])
    for name, spec in BOOKS.items():
        rng = random.Random(seed * 100 + sum(map(ord, name)))
        init, nights = gen_book(rng, spec)
        t = time.time()
        ref = run_book(init, nights, lambda n: proto.solve_dp(n)[1])
        cnts = []
        fam = dict(init)
        tmax = 0
        for nt in nights:
            n2 = dict(nt, init=dict(fam))
            t0 = time.time(); b, p, c = proto.solve_dp(n2); tmax = max(tmax, time.time() - t0)
            cnts.append(c)
            fam = end_fams(n2, p or {}, fam)
        sizes = [len(nt["jobs"]) for nt in nights]
        line = [f"{name} sizes={sizes} counts={cnts} ref_tmax={tmax:.2f}s"]
        variants = {
            "greedy": (lambda n: proto.greedy_density(n), True),
            "ls": (lambda n: proto.local_search(n, proto.greedy_density(n)), True),
            "lanebylane": (lambda n: proto.lane_by_lane(n), True),
            "flowrelax": (lambda n: proto.solve_dp(n, quals=False, crew=False)[1], True),
            "reset_nightly": (lambda n: proto.solve_dp(n)[1], False),
            "noinit": (lambda n: proto.solve_dp(n, initial=False)[1], True),
            "nogap": (lambda n: proto.solve_dp(n, gapcarry=False)[1], True),
            "nocrew": (lambda n: proto.solve_dp(n, crew=False)[1], True),
        }
        for vname, (fn, carry) in variants.items():
            plans = run_book(init, nights, fn, carry=carry)
            diff = sum(1 for a, b in zip(plans, ref) if a != b)
            rv = true_eval(init, nights, plans)
            refv = true_eval(init, nights, ref)
            inf = sum(1 for v, _ in rv if not isinstance(v, int))
            loss = sum(r[0] for r in refv if isinstance(r[0], int)) - sum(v for v, _ in rv if isinstance(v, int))
            line.append(f"{vname}:{diff}/{len(nights)}(inf{inf},loss{loss})")
        proto.NAIVE[0] = True
        plans = run_book(init, nights, lambda n: proto.solve_dp(n)[1])
        proto.NAIVE[0] = False
        line.append(f"naivenorm:{sum(1 for a, b in zip(plans, ref) if a != b)}/{len(nights)}")
        # nonorm runtime on largest night
        big = max(range(len(nights)), key=lambda i: len(nights[i]["jobs"]))
        orig = proto.norm
        proto.norm = lambda l, cf, s, d: (l, cf)
        signal.alarm(30); t0 = time.time()
        try:
            proto.solve_dp(nights[big]); line.append(f"nonorm_big={time.time() - t0:.1f}s")
        except TO:
            line.append("nonorm_big>30s")
        signal.alarm(0)
        proto.norm = orig
        print(" ".join(line), flush=True)


if __name__ == "__main__":
    main()
