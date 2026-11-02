"""Unit-step reference replay (integer clock, no heap).

Book model (in memory):
  book = {"lease": int, "delay": int, "pools": {name: preempt_bool},
          "sets": {sid: {"workers": {w: [pool, up_bool]},
                         "jobs": {j: [pool, priority, retry_limit]},
                         "work": {j: int}, "deps": [[p, c], ...],
                         "events": [dict, ...], "checkpoints": [t, ...]}}}
"""
import hashlib
from collections import Counter

TERMINAL = ("completed", "dead", "cancelled")
REASONS = ("redelivery", "finished", "stale_attempt", "not_running")


class SetReplay:
    def __init__(self, s, lease, delay, pools):
        self.lease, self.delay, self.pools = lease, delay, pools
        self.jobs = {}
        for j, (pool, prio, limit) in s["jobs"].items():
            self.jobs[j] = {"pool": pool, "prio": prio, "limit": limit, "work": s["work"][j],
                            "state": "unsubmitted", "attempt": 1, "rem": s["work"][j],
                            "worker": None, "start": None, "deadline": None, "ready": None,
                            "runs": 0, "executed": 0, "lost": 0, "preemptions": 0,
                            "evictions": 0, "attempts_ended": 0,
                            "pre_att": 0, "old_finish": None, "run_rem": None}
        self.workers = {w: {"pool": p, "up": up, "job": None} for w, (p, up) in s["workers"].items()}
        self.parents = {j: set() for j in self.jobs}
        self.children = {j: set() for j in self.jobs}
        for p, c in s["deps"]:
            self.parents[c].add(p)
            self.children[p].add(c)
        self.seen = {}
        self.dispatches, self.audit, self.checkpoints = [], [], []
        self.released, self.cascaded, self.done_at = {}, {}, {}
        self.last = {"completed": [], "expired": [], "ready": []}
        self.cases = Counter()
        self.exp_att = {}

    # ---- helpers
    def _idle_worker(self, j):
        job = self.jobs[j]
        job["worker"] = None
        job["deadline"] = None

    def _free(self, j):
        w = self.jobs[j]["worker"]
        if w is not None:
            self.workers[w]["job"] = None
        self._idle_worker(j)

    def _end_attempt(self, j, t):
        job = self.jobs[j]
        self._free(j)
        job["lost"] += job["work"] - job["rem"]
        job["attempts_ended"] += 1
        if job["attempt"] == job["limit"] + 1:
            job["state"] = "dead"
            self.cases["dead"] += 1
            self.done_at[j] = t
            self._cascade(j, t)
        else:
            job["attempt"] += 1
            job["pre_att"] = 0
            job["rem"] = job["work"]
            job["state"] = "backoff"
            job["ready"] = t + self.delay

    def _cascade(self, j, t, depth=1):
        for c in sorted(self.children[j]):
            cj = self.jobs[c]
            if cj["state"] in TERMINAL:
                continue
            assert cj["state"] in ("waiting", "unsubmitted"), cj["state"]
            self.cases["cascade_" + cj["state"]] += 1
            if depth >= 3:
                self.cases["cascade_depth4"] += 1
            cj["state"] = "cancelled"
            self.done_at[c] = t
            self.cascaded[c] = t
            self._cascade(c, t, depth + 1)

    def _all_parents_done(self, j):
        return all(self.jobs[p]["state"] == "completed" for p in self.parents[j])

    # ---- phases
    def internal(self, t):
        running = [j for j in sorted(self.jobs) if self.jobs[j]["state"] == "running"]
        if t > 0:
            for j in running:
                self.jobs[j]["rem"] -= 1
                self.jobs[j]["executed"] += 1
        comp = [j for j in running if self.jobs[j]["rem"] == 0]
        for j in comp:
            self._free(j)
            self.jobs[j]["state"] = "completed"
            self.done_at[j] = t
        for j in sorted(self.jobs):
            if self.jobs[j]["state"] == "waiting" and self._all_parents_done(j):
                self.jobs[j]["state"] = "queued"
                self.released[j] = t
        exp = [j for j in running if self.jobs[j]["state"] == "running" and self.jobs[j]["deadline"] == t]
        self.exp_att = {j: self.jobs[j]["attempt"] for j in exp}
        for j in exp:
            self.cases["expiry"] += 1
            if self.jobs[j]["pre_att"] >= 2:
                self.cases["preempt2_expire"] += 1
            self._end_attempt(j, t)
        rdy = [j for j in sorted(self.jobs) if self.jobs[j]["state"] == "backoff" and self.jobs[j]["ready"] == t]
        for j in rdy:
            self.jobs[j]["state"] = "queued"
            self.jobs[j]["ready"] = None
        self.last = {"completed": comp, "expired": exp, "ready": rdy}
        if comp and exp and rdy:
            self.cases["coinc3"] += 1
        if comp and exp:
            self.cases["coinc_comp_exp"] += 1
        if (comp or exp) and rdy:
            self.cases["coinc_x_ready"] += 1

    def _audit(self, t, ev, reason):
        self.audit.append([t, ev["id"], reason])
        self.cases["audit_" + reason] += 1

    def external(self, t, events):
        for ev in sorted(events, key=lambda e: e["id"]):
            key = ev["id"]
            if key in self.seen:
                self._audit(t, ev, "redelivery")
                self.cases["redeliver_" + ev["type"]] += 1
                continue
            self.cases["event_" + ev["type"]] += 1
            self.seen[key] = ev
            kind = ev["type"]
            if kind in ("worker_down", "worker_up"):
                wk = self.workers[ev["worker"]]
                if kind == "worker_up":
                    wk["up"] = True
                    continue
                wk["up"] = False
                if wk["job"] is not None:
                    j = wk["job"]
                    self._free(j)
                    self.jobs[j]["state"] = "queued"
                    self.jobs[j]["evictions"] += 1
                    self.jobs[j]["pre_att"] += 1
                    self.jobs[j]["old_finish"] = t + self.jobs[j]["rem"]
                    self.cases["eviction"] += 1
                continue
            j = ev["job"]
            job = self.jobs[j]
            if j in self.last["completed"] or j in self.exp_att:
                self.cases["event_at_internal"] += 1
            if kind in ("heartbeat", "fail") and self.exp_att.get(j) == ev["attempt"]:
                self.cases["token_at_deadline"] += 1
            if job["state"] in TERMINAL:
                self._audit(t, ev, "finished")
                continue
            if kind == "submit":
                if self._all_parents_done(j):
                    job["state"] = "queued"
                    if self.parents[j]:
                        self.released[j] = t
                else:
                    job["state"] = "waiting"
            elif kind == "boost":
                if job["state"] == "unsubmitted":
                    self.cases["boost_unsubmitted"] += 1
                job["prio"] += ev["delta"]
            elif kind == "cancel":
                if job["state"] == "running" and job["pre_att"]:
                    self.cases["cancel_running_resumed"] += 1
                if job["state"] == "queued" and job["rem"] < job["work"] and self.children[j]:
                    self.cases["cancel_preempted_with_children"] += 1
                if job["state"] == "running":
                    self._free(j)
                job["lost"] += job["work"] - job["rem"]
                job["state"] = "cancelled"
                self.done_at[j] = t
                self._cascade(j, t)
            elif kind in ("heartbeat", "fail"):
                if ev["attempt"] != job["attempt"]:
                    if job["state"] == "running":
                        self.cases["stale_while_retry_runs"] += 1
                    self._audit(t, ev, "stale_attempt")
                elif job["state"] != "running":
                    if job["state"] == "queued" and job["rem"] < job["work"]:
                        self.cases["token_on_preempted"] += 1
                    self._audit(t, ev, "not_running")
                elif kind == "heartbeat":
                    job["deadline"] = t + self.lease
                else:
                    self._end_attempt(j, t)
            else:
                raise ValueError(kind)

    def _start(self, j, w, t):
        job = self.jobs[j]
        if job["old_finish"] is not None and t < job["old_finish"]:
            self.cases["resume_before_old_finish"] += 1
        job["old_finish"] = None
        job.update(state="running", worker=w, start=t, deadline=t + self.lease)
        job["runs"] += 1
        self.workers[w]["job"] = j
        self.dispatches.append([t, j, w, job["attempt"]])

    def dispatch(self, t):
        queue = sorted((j for j in self.jobs if self.jobs[j]["state"] == "queued"),
                       key=lambda j: (-self.jobs[j]["prio"], j))
        for j in queue:
            job = self.jobs[j]
            idle = [w for w in sorted(self.workers) if self.workers[w]["pool"] == job["pool"]
                    and self.workers[w]["up"] and self.workers[w]["job"] is None]
            if idle:
                self._start(j, idle[0], t)
                continue
            if not self.pools[job["pool"]]:
                continue
            cands = [k for k in self.jobs if self.jobs[k]["state"] == "running"
                     and self.jobs[k]["pool"] == job["pool"] and self.jobs[k]["prio"] < job["prio"]]
            if not cands:
                continue
            v = min(cands, key=lambda k: (self.jobs[k]["prio"], -self.jobs[k]["start"], -k))
            low = [k for k in cands if self.jobs[k]["prio"] == self.jobs[v]["prio"]]
            if len(low) > 1:
                same = [k for k in low if self.jobs[k]["start"] == self.jobs[v]["start"]]
                self.cases["victim_tie_start" if len(same) > 1 else "victim_tie_prio"] += 1
            self.cases["preemption"] += 1
            self.jobs[v]["pre_att"] += 1
            self.jobs[v]["old_finish"] = t + self.jobs[v]["rem"]
            w = self.jobs[v]["worker"]
            self._free(v)
            self.jobs[v]["state"] = "queued"
            self.jobs[v]["preemptions"] += 1
            self._start(j, w, t)

    def snapshot(self, t):
        jobs = {}
        for j in sorted(self.jobs):
            x = self.jobs[j]
            jobs[str(j)] = {"state": x["state"], "priority": x["prio"], "attempt": x["attempt"],
                            "remaining": x["rem"], "worker": x["worker"]}
        workers = {str(w): {"up": x["up"], "job": x["job"]} for w, x in sorted(self.workers.items())}
        self.checkpoints.append({"t": t, "jobs": jobs, "workers": workers})


def case_counts(book):
    out = {}
    for sid in sorted(book["sets"]):
        out[sid] = dict(replay_set(book["sets"][sid], book["lease"], book["delay"], book["pools"]).cases)
    return out


def replay_set(s, lease, delay, pools):
    r = SetReplay(s, lease, delay, pools)
    by_t = {}
    for ev in s["events"]:
        by_t.setdefault(ev["t"], []).append(ev)
    cps = set(s["checkpoints"])
    for t in range(0, max(cps) + 1):
        r.internal(t)
        r.external(t, by_t.get(t, []))
        r.dispatch(t)
        if t in cps:
            r.snapshot(t)
    return r


def documents(book):
    core, metrics, deps, summ = {}, {}, {}, {}
    for sid in sorted(book["sets"]):
        s = book["sets"][sid]
        r = replay_set(s, book["lease"], book["delay"], book["pools"])
        k = str(sid)
        core[k] = {"checkpoints": r.checkpoints, "dispatches": r.dispatches, "audit": r.audit}
        fields = ("runs", "executed", "lost", "preemptions", "evictions", "attempts_ended")
        jm = {str(j): {f: r.jobs[j][f] for f in fields} for j in sorted(r.jobs)}
        tot = {f: sum(r.jobs[j][f] for j in r.jobs) for f in fields}
        tot["audit"] = {reason: sum(1 for a in r.audit if a[2] == reason) for reason in REASONS}
        metrics[k] = {"jobs": jm, "totals": tot}
        edges = []
        for p, c in sorted({(p, c) for p, c in s["deps"]}):
            st = r.jobs[p]["state"]
            if st == "completed":
                edges.append({"parent": p, "child": c, "outcome": "satisfied", "t": r.done_at[p]})
            elif st in TERMINAL:
                edges.append({"parent": p, "child": c, "outcome": "broken", "t": r.done_at[p]})
            else:
                edges.append({"parent": p, "child": c, "outcome": "open", "t": None})
        deps[k] = {"edges": edges,
                   "released": {str(j): t for j, t in sorted(r.released.items())},
                   "cascaded": {str(j): t for j, t in sorted(r.cascaded.items())}}
        final = {"completed": 0, "dead": 0, "cancelled": 0, "other": 0}
        for j in r.jobs:
            st = r.jobs[j]["state"]
            final[st if st in TERMINAL else "other"] += 1
        lines = "".join("%d %d %d %d\n" % tuple(d) for d in r.dispatches)
        summ[k] = {"final": final, "executed": tot["executed"], "lost": tot["lost"],
                   "dispatch_sha256": hashlib.sha256(lines.encode()).hexdigest()}
    return ({"sets": core}, {"sets": metrics}, {"sets": deps},
            {"set_count": len(book["sets"]), "sets": summ})
