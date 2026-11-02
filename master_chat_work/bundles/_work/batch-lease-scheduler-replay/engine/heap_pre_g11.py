"""Event-heap replay written from the contract (the 'first-write' shape), with slip flags.

With flags=set() it must equal refsim exactly. Each flag injects one plausible slip.
"""
import hashlib
import heapq

TERMINAL = ("completed", "dead", "cancelled")
REASONS = ("redelivery", "finished", "stale_attempt", "not_running")


class Heap:
    def __init__(self, s, lease, delay, pools, flags):
        self.f = flags
        self.lease, self.delay, self.pools = lease, delay, pools
        self.J = {}
        for j, (pool, prio, limit) in s["jobs"].items():
            self.J[j] = dict(pool=pool, prio=prio, limit=limit, work=s["work"][j], st="unsubmitted",
                             att=1, rem=s["work"][j], w=None, t0=None, dl=None, rd=None, run=0,
                             sub=None, m=[0, 0, 0, 0, 0, 0])
        self.W = {w: [p, up, None] for w, (p, up) in s["workers"].items()}
        self.par = {j: [] for j in self.J}
        self.kids = {j: [] for j in self.J}
        for p, c in s["deps"]:
            self.par[c].append(p)
            self.kids[p].append(c)
        self.h, self.seq = [], 0
        self.seen = set()
        self.disp, self.aud, self.cps = [], [], []
        self.rel, self.casc, self.end = {}, {}, {}

    def push(self, t, ph, kind, j, g):
        self.seq += 1
        heapq.heappush(self.h, (t, ph, self.seq, kind, j, g))

    def remaining(self, j, t):
        x = self.J[j]
        if x["st"] == "running":
            return x["rem"] - (t - x["t0"])
        return x["rem"]

    def stop_run(self, j, t, interp=True):
        x = self.J[j]
        if x["st"] == "running":
            ran = t - x["t0"]
            x["m"][1] += ran
            if interp:
                x["rem"] -= ran
            self.W[x["w"]][2] = None
            x["w"] = None
            x["dl"] = None
            return ran
        return 0

    def end_attempt(self, j, t):
        x = self.J[j]
        ran = self.stop_run(j, t)
        x["m"][2] += ran if "FW3" in self.f else x["work"] - x["rem"]
        x["m"][5] += 1
        if x["att"] == x["limit"] + 1:
            x["st"] = "dead"
            self.end[j] = t
            self.cascade(j, t)
        else:
            x["att"] += 1
            x["rem"] = x["work"]
            x["st"] = "backoff"
            x["rd"] = t + self.delay
            self.push(x["rd"], 3, "ready", j, x["att"])

    def cascade(self, j, t):
        if "ANYTERM" in self.f:
            self.release_check(t)
            return
        stack = list(self.kids[j])
        while stack:
            c = stack.pop()
            y = self.J[c]
            if y["st"] in TERMINAL:
                continue
            if "FW5" in self.f and y["st"] == "unsubmitted":
                continue
            y["st"] = "cancelled"
            self.end[c] = t
            self.casc[c] = t
            stack.extend(self.kids[c])

    def parents_ok(self, j):
        ok = TERMINAL if "ANYTERM" in self.f else ("completed",)
        return all(self.J[p]["st"] in ok for p in self.par[j])

    def release_check(self, t):
        for j in self.J:
            if self.J[j]["st"] == "waiting" and self.parents_ok(j):
                self.J[j]["st"] = "queued"
                self.rel[j] = t

    def start(self, j, w, t):
        x = self.J[j]
        x.update(st="running", w=w, t0=t, dl=t + self.lease)
        x["run"] += 1
        x["m"][0] += 1
        self.W[w][2] = j
        self.disp.append([t, j, w, x["att"]])
        self.push(t + x["rem"], 1, "done", j, x["att"] if "FW1" in self.f else x["run"])
        self.push(x["dl"], 2, "exp", j, x["dl"])

    def dispatch(self, t):
        if "SUBORDER" in self.f:
            key = lambda j: (-self.J[j]["prio"], self.J[j]["sub"], j)
        else:
            key = lambda j: (-self.J[j]["prio"], j)
        for j in sorted([j for j in self.J if self.J[j]["st"] == "queued"], key=key):
            x = self.J[j]
            free = sorted(w for w, v in self.W.items() if v[0] == x["pool"] and v[1] and v[2] is None)
            if free:
                self.start(j, free[0], t)
                continue
            if not self.pools[x["pool"]]:
                continue
            lower = [k for k in self.J if self.J[k]["st"] == "running" and self.J[k]["pool"] == x["pool"]
                     and self.J[k]["prio"] < x["prio"]]
            if not lower:
                continue
            v = min(lower, key=lambda k: (self.J[k]["prio"], -self.J[k]["t0"], -k))
            w = self.J[v]["w"]
            if "PREFAIL" in self.f:
                self.end_attempt(v, t)
            else:
                self.stop_run(v, t)
                self.J[v]["st"] = "queued"
                self.J[v]["m"][3] += 1
            self.start(j, w, t)

    def internal(self, t, stamp):
        while self.h and self.h[0][0] <= t:
            tt, ph, _, kind, j, g = heapq.heappop(self.h)
            self.one(kind, j, g, tt if stamp is None else stamp)

    def one(self, kind, j, g, t):
        x = self.J[j]
        if kind == "done":
            ok = x["st"] == "running" and (x["att"] == g if "FW1" in self.f else x["run"] == g)
            if ok:
                self.stop_run(j, t)
                x["rem"] = 0
                x["st"] = "completed"
                self.end[j] = t
                self.release_check(t)
        elif kind == "exp":
            if x["st"] == "running" and x["dl"] == g:
                self.end_attempt(j, t)
        elif kind == "ready":
            if x["st"] == "backoff" and x["att"] == g:
                x["st"] = "queued"
                x["rd"] = None

    def external(self, t, evs):
        for ev in sorted(evs, key=lambda e: e["id"]):
            if ev["id"] in self.seen and "REDUP" not in self.f:
                self.aud.append([t, ev["id"], "redelivery"])
                continue
            self.seen.add(ev["id"])
            self.apply(t, ev)
            if "PEREVENT" in self.f:
                self.dispatch(t)

    def apply(self, t, ev):
        k = ev["type"]
        if k == "worker_up":
            self.W[ev["worker"]][1] = True
            return
        if k == "worker_down":
            v = self.W[ev["worker"]]
            v[1] = False
            j = v[2]
            if j is not None:
                self.stop_run(j, t)
                self.J[j]["st"] = "queued"
                self.J[j]["m"][4] += 1
            return
        j = ev["job"]
        x = self.J[j]
        if x["st"] in TERMINAL:
            self.aud.append([t, ev["id"], "finished"])
            return
        if k == "submit":
            x["sub"] = (t, ev["id"])
            if self.parents_ok(j):
                x["st"] = "queued"
                if self.par[j]:
                    self.rel[j] = t
            else:
                x["st"] = "waiting"
        elif k == "boost":
            x["prio"] += ev["delta"]
        elif k == "cancel":
            ran = self.stop_run(j, t, interp="FW3b" not in self.f)
            x["m"][2] += ran if "FW3" in self.f else x["work"] - x["rem"]
            x["st"] = "cancelled"
            self.end[j] = t
            self.cascade(j, t)
        else:
            if "PRECSWAP" in self.f and x["st"] != "running":
                self.aud.append([t, ev["id"], "not_running"])
            elif ev["attempt"] != x["att"] and "STALE" not in self.f:
                self.aud.append([t, ev["id"], "stale_attempt"])
            elif x["st"] != "running" and not ("FW4" in self.f and x["st"] == "queued"):
                self.aud.append([t, ev["id"], "not_running"])
            elif k == "heartbeat":
                if x["st"] == "running":
                    x["dl"] = t + self.lease
                    self.push(x["dl"], 2, "exp", j, x["dl"])
            else:
                if x["st"] == "running":
                    self.end_attempt(j, t)
                else:
                    x["m"][2] += x["work"] - x["rem"]
                    x["m"][5] += 1
                    if x["att"] == x["limit"] + 1:
                        x["st"] = "dead"
                        self.end[j] = t
                        self.cascade(j, t)
                    else:
                        x["att"] += 1
                        x["rem"] = x["work"]
                        x["st"] = "backoff"
                        x["rd"] = t + self.delay
                        self.push(x["rd"], 3, "ready", j, x["att"])

    def snap(self, t):
        jobs = {str(j): {"state": x["st"], "priority": x["prio"], "attempt": x["att"],
                         "remaining": (x["rem"] if "FW2R" in self.f else self.remaining(j, t)),
                         "worker": x["w"]} for j, x in sorted(self.J.items())}
        workers = {str(w): {"up": v[1], "job": v[2]} for w, v in sorted(self.W.items())}
        self.cps.append({"t": t, "jobs": jobs, "workers": workers})


def run_set(s, lease, delay, pools, flags):
    r = Heap(s, lease, delay, pools, flags)
    by_t = {}
    for ev in s["events"]:
        by_t.setdefault(ev["t"], []).append(ev)
    cps = sorted(set(s["checkpoints"]))
    t_end = cps[-1]
    lazy = "LAZY" in r.f
    fixed = sorted(set(by_t) | set(cps))
    i, t = 0, -1
    while True:
        while i < len(fixed) and fixed[i] <= t:
            i += 1
        cand = fixed[i:i + 1]
        if r.h and not lazy:
            cand.append(r.h[0][0])
        if not cand or min(cand) > t_end:
            break
        t = min(cand)
        if lazy and t not in by_t:
            r.snap(t)
            continue
        if "FW2" in r.f:
            r.external(t, by_t.get(t, []))
            r.internal(t, t if lazy else None)
        else:
            r.internal(t, t if lazy else None)
            r.external(t, by_t.get(t, []))
        r.dispatch(t)
        if t in cps:
            r.snap(t)
    # close running runs at t_end
    for j, x in r.J.items():
        if x["st"] == "running":
            x["m"][1] += t_end - x["t0"]
    return r


def documents(book, flags=frozenset()):
    core, metrics, deps, summ = {}, {}, {}, {}
    names = ("runs", "executed", "lost", "preemptions", "evictions", "attempts_ended")
    for sid in sorted(book["sets"]):
        s = book["sets"][sid]
        r = run_set(s, book["lease"], book["delay"], book["pools"], set(flags))
        k = str(sid)
        core[k] = {"checkpoints": r.cps, "dispatches": r.disp, "audit": r.aud}
        jm = {str(j): dict(zip(names, x["m"])) for j, x in sorted(r.J.items())}
        tot = {n: sum(v[n] for v in jm.values()) for n in names}
        tot["audit"] = {n: sum(1 for a in r.aud if a[2] == n) for n in REASONS}
        metrics[k] = {"jobs": jm, "totals": tot}
        edges = []
        for p, c in sorted(set(map(tuple, s["deps"]))):
            st = r.J[p]["st"]
            out = "satisfied" if st == "completed" else ("broken" if st in TERMINAL else "open")
            edges.append({"parent": p, "child": c, "outcome": out, "t": r.end.get(p) if out != "open" else None})
        deps[k] = {"edges": edges, "released": {str(j): v for j, v in sorted(r.rel.items())},
                   "cascaded": {str(j): v for j, v in sorted(r.casc.items())}}
        fin = {"completed": 0, "dead": 0, "cancelled": 0, "other": 0}
        for x in r.J.values():
            fin[x["st"] if x["st"] in TERMINAL else "other"] += 1
        sha = hashlib.sha256("".join("%d %d %d %d\n" % tuple(d) for d in r.disp).encode()).hexdigest()
        summ[k] = {"final": fin, "executed": tot["executed"], "lost": tot["lost"], "dispatch_sha256": sha}
    return ({"sets": core}, {"sets": metrics}, {"sets": deps}, {"set_count": len(book["sets"]), "sets": summ})
