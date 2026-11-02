"""State-aware book generator. Plants coincident instants against a live unit-step replay."""
import random

from refsim import SetReplay, TERMINAL

POOL_NAMES = ["birch", "cedar", "elm", "fir", "hazel", "larch", "maple", "oak", "pine", "rowan", "spruce", "yew"]

PROFILES = {
    # jobs, workers, events target, checkpoints, horizon, work range
    "hidden": dict(jobs=(80, 140), workers=(8, 24), events=(500, 1000), cps=(10, 20), horizon=(320, 480),
                   work=(5, 50), dens=1.0, edges=0.45, coinc=0.6, ties=10, hold=2),
    "shipped": dict(jobs=(10, 16), workers=(5, 7), events=(30, 60), cps=(6, 6), horizon=(60, 110),
                    work=(2, 20), dens=0.3, edges=0.5, coinc=0.3, ties=1),
}


def make_pools(rng):
    names = rng.sample(POOL_NAMES, rng.randint(4, 6))
    flags = [True] * len(names)
    flags[rng.randrange(len(names))] = False
    return {n: f for n, f in zip(names, flags)}


def _dag(rng, ids, ratio):
    order = list(ids)
    rng.shuffle(order)
    edges = set()
    n = len(order)
    # at least three chains of length >= 4
    for _ in range(3):
        if n < 5:
            break
        idx = sorted(rng.sample(range(n), 4))
        for a, b in zip(idx, idx[1:]):
            edges.add((order[a], order[b]))
    while len(edges) < int(n * ratio):
        a, b = sorted(rng.sample(range(n), 2))
        if b - a <= max(3, n // 4):
            edges.add((order[a], order[b]))
    return sorted(edges)


def make_set(rng, prof, pools, lease, delay, id_hi):
    nj = rng.randint(*prof["jobs"])
    nw = rng.randint(*prof["workers"])
    pool_names = sorted(pools)
    used = rng.sample(pool_names, min(len(pool_names), max(2, min(4, nw // 2))))
    wids = rng.sample(range(10, id_hi), nw)
    workers = {}
    for k, w in enumerate(wids):
        pool = used[k % len(used)] if k < len(used) * 2 else rng.choice(used)
        workers[w] = [pool, rng.random() > 0.1]
    jids = rng.sample(range(10, id_hi), nj)
    jobs, work = {}, {}
    for j in jids:
        jobs[j] = [rng.choice(used), rng.randint(0, 9), rng.choice([0, 1, 1, 2, 2, 3])]
        lo, hi = prof["work"]
        work[j] = rng.randint(lo, hi) if rng.random() < 0.7 else rng.randint(1, min(60, hi + 15))
    deps = _dag(rng, jids, prof["edges"])
    horizon = rng.randint(*prof["horizon"])
    k = rng.randint(*prof["cps"])
    cps = sorted(rng.sample(range(1, horizon), k - 1) + [horizon])
    s = {"workers": workers, "jobs": jobs, "work": work, "deps": [list(e) for e in deps],
         "events": [], "checkpoints": cps}
    _plant(rng, prof, s, lease, delay, pools, id_hi)
    return s


def _plant(rng, prof, s, lease, delay, pools, id_hi):
    horizon = s["checkpoints"][-1]
    target = rng.randint(*prof["events"])
    dens = prof["dens"]
    jids = sorted(s["jobs"])
    parents = {j: set() for j in jids}
    for p, c in s["deps"]:
        parents[c].add(p)
    plan = {}
    for j in jids:
        if rng.random() < 0.95:
            plan.setdefault(rng.randint(0, int(horizon * 0.6)), []).append(j)
    # tie groups: root jobs of one preempt pool, equal low priority, submitted together
    pre_pools = sorted({s["workers"][w][0] for w in s["workers"]} & {p for p in pools if pools[p]})
    for _ in range(prof["ties"]):
        if not pre_pools:
            break
        pool = rng.choice(pre_pools)
        roots = [j for j in jids if not parents[j] and s["jobs"][j][0] == pool]
        if len(roots) < 2:
            continue
        grp = rng.sample(roots, min(len(roots), rng.randint(2, 3)))
        pr = rng.randint(0, 2)
        tt = rng.randint(0, int(horizon * 0.5))
        for tl in plan.values():
            for j in grp:
                if j in tl:
                    tl.remove(j)
        for j in grp:
            s["jobs"][j][1] = pr
            s["work"][j] = max(s["work"][j], lease + 3)
        plan.setdefault(tt, []).extend(grp)
    r = SetReplay(s, lease, delay, pools)
    used_ids = set()
    events = []
    gap = {j: rng.randint(1, max(1, min(3, lease - 1))) for j in jids}
    chatty = {j for j in jids if rng.random() < 0.5}
    sched = {}
    doom = {}

    def new_id():
        while True:
            x = rng.randint(1, id_hi * 10)
            if x not in used_ids:
                used_ids.add(x)
                return x

    budget = lambda: len(events) < target
    room = lambda: len(events) < 1100
    submitted = set()
    # a few root jobs with dependents stay unsubmitted, so their edges stay open
    held = [j for j in jids if not parents[j] and r.children[j]][:prof.get("hold", 0)]
    for tl in plan.values():
        for j in held:
            if j in tl:
                tl.remove(j)
    submitted.update(held)
    copy_p = {"boost": 0.3, "cancel": 0.25, "worker_down": 0.25, "worker_up": 0.25}
    for t in range(0, horizon + 1):
        r.internal(t)
        evs = []
        J = r.jobs

        def add(kind, **kw):
            if not room():
                return None
            ev = {"id": new_id(), "t": t, "type": kind}
            ev.update(kw)
            evs.append(ev)
            if rng.random() < copy_p.get(kind, 0.06) * dens:
                evs.append(dict(ev))
            return ev

        def ready_parents(k):
            return all(J[p]["state"] == "completed" for p in r.parents[k])

        def press(pool, floor):
            """Make a job of priority above floor want a worker of pool now."""
            hi = [k for k in jids if J[k]["state"] == "unsubmitted" and k not in submitted
                  and J[k]["pool"] == pool and J[k]["prio"] > floor and ready_parents(k)]
            if hi:
                k = rng.choice(hi)
                add("submit", job=k)
                submitted.add(k)
                return
            q = [k for k in jids if J[k]["state"] == "queued" and J[k]["pool"] == pool
                 and 0 < floor + 1 - J[k]["prio"] <= 3]
            if q:
                k = rng.choice(q)
                add("boost", job=k, delta=floor + 1 - J[k]["prio"])

        for item in sched.pop(t, []):
            kind, j, att = item
            if kind == "fail" and J[j]["state"] == "running" and J[j]["attempt"] == att:
                add("fail", job=j, attempt=att)
            elif kind == "stale" and J[j]["state"] not in TERMINAL:
                add("heartbeat" if rng.random() < 0.6 else "fail", job=j, attempt=att)
            elif kind == "press":
                press(j, att)
        for j in plan.get(t, []):
            if J[j]["state"] in ("unsubmitted", "cancelled") and j not in submitted:
                add("submit", job=j)
                submitted.add(j)
        for j in r.last["expired"]:
            if rng.random() < 0.5 * dens:
                add("heartbeat", job=j, attempt=r.exp_att[j])
            elif rng.random() < 0.2 * dens:
                add("fail", job=j, attempt=r.exp_att[j])
            if rng.random() < 0.3 * dens:
                hi = [k for k in jids if J[k]["state"] == "unsubmitted" and k not in submitted
                      and s["jobs"][k][0] == s["jobs"][j][0] and J[k]["prio"] > J[j]["prio"]]
                if hi:
                    k = rng.choice(hi)
                    add("submit", job=k)
                    submitted.add(k)
        for j in r.last["completed"]:
            x = rng.random() / max(dens, 0.01)
            if x < 0.25:
                add("fail", job=j, attempt=J[j]["attempt"])
            elif x < 0.45:
                add("heartbeat", job=j, attempt=J[j]["attempt"])
            elif x < 0.6:
                add("cancel", job=j)
            elif x < 0.7:
                add("boost", job=j, delta=rng.choice([-3, -2, -1, 1, 2, 3]))
            for c in sorted(r.children[j]):
                if J[c]["state"] == "unsubmitted" and c not in submitted and rng.random() < 0.5:
                    add("submit", job=c)
                    submitted.add(c)
        for j in r.last["ready"]:
            x = rng.random() / max(dens, 0.01)
            if x < 0.3:
                hi = [k for k in jids if J[k]["state"] == "unsubmitted" and k not in submitted
                      and s["jobs"][k][0] == s["jobs"][j][0] and J[k]["prio"] >= J[j]["prio"]]
                if hi:
                    k = rng.choice(hi)
                    add("submit", job=k)
                    submitted.add(k)
            elif x < 0.4:
                add("cancel", job=j)
            elif x < 0.6:
                add("boost", job=j, delta=rng.choice([1, 2, 3]))
        run = [j for j in jids if J[j]["state"] == "running"]
        # completion, expiry and retry-ready at one instant
        comp_at = {}
        for a in run:
            comp_at.setdefault(t + J[a]["rem"], []).append(a)
        ready_at = {J[j]["ready"] for j in jids if J[j]["state"] == "backoff"}
        for k in run:
            d = J[k]["deadline"]
            if doom.get(k) == J[k]["attempt"] or d <= t or d >= t + J[k]["rem"]:
                continue
            if not [a for a in comp_at.get(d, []) if a != k] or rng.random() > prof["coinc"]:
                continue
            doom[k] = J[k]["attempt"]
            if d in ready_at:
                continue
            fm = [m for m in run if m != k and m not in comp_at.get(d, []) and doom.get(m) != J[m]["attempt"]
                  and J[m]["attempt"] <= J[m]["limit"] and t + J[m]["rem"] > d - delay]
            if fm and d - delay >= t:
                m = rng.choice(fm)
                if d - delay == t:
                    add("fail", job=m, attempt=J[m]["attempt"])
                else:
                    sched.setdefault(d - delay, []).append(("fail", m, J[m]["attempt"]))
        # resumed after two preemptions: let the lease run out
        for k in run:
            if J[k]["pre_att"] >= 2 and doom.get(k) != J[k]["attempt"] and rng.random() < 0.8:
                doom[k] = J[k]["attempt"]
        # pressure on preempt pools whose lowest running job was already preempted
        lows = {}
        for k in run:
            p = J[k]["pool"]
            if pools[p] and (p not in lows or J[k]["prio"] < J[lows[p]]["prio"]):
                lows[p] = k
        for p, k in lows.items():
            if J[k]["pre_att"] >= 1 and rng.random() < 0.25 * dens:
                press(p, J[k]["prio"])
        for k in run:
            if J[k]["pre_att"] >= 1 and rng.random() < 0.02 * dens:
                add("cancel", job=k)
        for k in jids:
            x = J[k]
            if x["state"] == "queued" and x["rem"] < x["work"] and r.children[k] and rng.random() < 0.06 * dens:
                add("cancel", job=k)
        if budget():
            nrun = len(run)
            p_fill = (target - len(events)) / max(1.0, (horizon + 1 - t) * max(1, nrun) * 0.5)
            for j in jids:
                x = J[j]
                alive = doom.get(j) != x["attempt"]
                if x["state"] == "running" and alive and x["deadline"] - t == gap[j] and rng.random() < 0.9:
                    add("heartbeat", job=j, attempt=x["attempt"])
                elif x["state"] == "queued" and x["rem"] < x["work"] and rng.random() < 0.08 * dens:
                    add("heartbeat" if rng.random() < 0.7 else "fail", job=j, attempt=x["attempt"])
                elif x["state"] in ("running", "backoff", "queued") and x["attempt"] > 1 and rng.random() < 0.01 * dens:
                    add("heartbeat" if rng.random() < 0.5 else "fail", job=j, attempt=x["attempt"] - 1)
                elif x["state"] == "running" and rng.random() < 0.004 * dens:
                    add("fail", job=j, attempt=x["attempt"])
                elif x["state"] == "running" and alive and j in chatty and rng.random() < p_fill:
                    add("heartbeat", job=j, attempt=x["attempt"])
            busy = {}
            for j in run:
                busy.setdefault(J[j]["pool"], []).append(J[j]["prio"])
            for pool, prios in busy.items():
                if pools[pool] and rng.random() < 0.08 * dens:
                    press(pool, min(prios))
            if rng.random() < 0.015 * dens:
                live = [j for j in jids if J[j]["state"] not in TERMINAL and j not in held]
                with_kids = [j for j in live if r.children[j]]
                pick = with_kids if with_kids and rng.random() < 0.7 else live
                if pick:
                    add("cancel", job=rng.choice(pick))
            if rng.random() < 0.12 * dens:
                live = [j for j in jids if J[j]["state"] in ("queued", "running", "waiting", "backoff", "unsubmitted")]
                if live:
                    add("boost", job=rng.choice(live), delta=rng.choice([-3, -2, -1, 1, 2, 3]))
            if rng.random() < 0.03 * max(dens, 0.5):
                ws = sorted(r.workers)
                down = [w for w in ws if not r.workers[w]["up"]]
                w = rng.choice(down if down and rng.random() < 0.5 else ws)
                if all(e.get("worker") != w for e in evs):
                    add("worker_down" if r.workers[w]["up"] else "worker_up", worker=w)
        r.external(t, evs)
        nd = len(r.dispatches)
        r.dispatch(t)
        for row in r.dispatches[nd:]:
            _, j, w, att = row
            if att > 1 and rng.random() < 0.5 * max(dens, 0.5):
                sched.setdefault(t + rng.randint(1, max(1, lease - 1)), []).append(("stale", j, att - 1))
        starts = {}
        for k in jids:
            x = J[k]
            if x["state"] == "running" and x["start"] == t and pools[x["pool"]]:
                starts.setdefault((x["pool"], x["prio"]), []).append(k)
        for (pool, pr), grp in starts.items():
            floor = min(J[k]["prio"] for k in jids if J[k]["state"] == "running" and J[k]["pool"] == pool)
            if len(grp) >= 2 and pr == floor:
                sched.setdefault(t + 1, []).append(("press", pool, pr))
        events.extend(evs)
    assert len(events) <= 1200, len(events)
    s["events"] = events


def make_book(seed, profile, nsets, lease=None, delay=None):
    rng = random.Random(seed)
    prof = PROFILES[profile]
    pools = make_pools(rng)
    lease = lease or (rng.randint(12, 20) if profile == "hidden" else rng.randint(6, 10))
    delay = delay or rng.randint(1, 10)
    id_hi = 100000 if profile == "hidden" else 9000
    sids = rng.sample(range(100, 99999 if profile == "hidden" else 9999), nsets)
    sets = {sid: make_set(rng, prof, pools, lease, delay, id_hi) for sid in sids}
    return {"lease": lease, "delay": delay, "pools": pools, "sets": sets}
