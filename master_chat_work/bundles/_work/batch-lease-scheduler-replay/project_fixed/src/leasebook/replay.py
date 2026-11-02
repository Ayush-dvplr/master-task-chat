"""Replay of one set: timed internal events, external events and dispatch."""
import heapq

TERMINAL = ("completed", "dead", "cancelled")
COUNTERS = ("runs", "executed", "lost", "preemptions", "evictions", "attempts_ended")
REASONS = ("redelivery", "finished", "stale_attempt", "not_running")
COMPLETION, EXPIRY, RETRY_READY = 1, 2, 3


class Job:
    """One job; `remaining` is the work left when its current run started."""

    def __init__(self, job_id, pool, priority, retry_limit, work):
        self.id = job_id
        self.pool = pool
        self.priority = priority
        self.retry_limit = retry_limit
        self.work = work
        self.state = "unsubmitted"
        self.attempt = 1
        self.remaining = work
        self.worker = None
        self.started = None
        self.deadline = None
        self.run_no = 0
        self.parents = []
        self.children = []
        self.counts = dict.fromkeys(COUNTERS, 0)

    def remaining_at(self, now):
        if self.state == "running":
            return self.remaining - (now - self.started)
        return self.remaining


class Worker:
    def __init__(self, worker_id, pool, up):
        self.id = worker_id
        self.pool = pool
        self.up = up
        self.job = None


class SetReplay:
    """Replays one set from time 0 to its last checkpoint."""

    def __init__(self, spec, lease, delay, preempt):
        self.lease = lease
        self.delay = delay
        self.preempt = preempt
        self.jobs = {}
        for job_id, (pool, priority, limit) in spec["jobs"].items():
            self.jobs[job_id] = Job(job_id, pool, priority, limit, spec["work"][job_id])
        self.workers = {w: Worker(w, pool, up) for w, (pool, up) in spec["workers"].items()}
        for parent, child in spec["deps"]:
            self.jobs[child].parents.append(parent)
            self.jobs[parent].children.append(child)
        self.events = spec["events"]
        self.checkpoints = sorted(spec["checkpoints"])
        self.timers = []
        self.sequence = 0
        self.seen = set()
        self.dispatches = []
        self.audit = []
        self.snapshots = []
        self.released = {}
        self.cascaded = {}
        self.ended = {}

    # timeline -----------------------------------------------------------
    def run(self):
        by_time = {}
        for event in self.events:
            by_time.setdefault(event["t"], []).append(event)
        end = self.checkpoints[-1]
        marks = sorted(set(by_time) | set(self.checkpoints))
        wanted = set(self.checkpoints)
        index = 0
        while True:
            upcoming = marks[index:index + 1]
            if self.timers:
                upcoming.append(self.timers[0][0])
            if not upcoming or min(upcoming) > end:
                break
            now = min(upcoming)
            if index < len(marks) and marks[index] == now:
                index += 1
            self._fire_timers(now)
            self._external(now, by_time.get(now, ()))
            self._dispatch(now)
            if now in wanted:
                self._snapshot(now)
        for job in self.jobs.values():
            if job.state == "running":
                job.counts["executed"] += end - job.started
        return self

    def _schedule(self, when, phase, job, token):
        self.sequence += 1
        heapq.heappush(self.timers, (when, phase, self.sequence, job.id, token))

    def _fire_timers(self, now):
        while self.timers and self.timers[0][0] == now:
            _, phase, _, job_id, token = heapq.heappop(self.timers)
            job = self.jobs[job_id]
            if phase == COMPLETION and job.state == "running" and job.run_no == token:
                self._complete(job, now)
            elif phase == EXPIRY and job.state == "running" and (job.run_no, job.deadline) == token:
                self._end_attempt(job, now)
            elif phase == RETRY_READY and job.state == "backoff" and job.attempt == token:
                job.state = "queued"

    # state changes --------------------------------------------------------
    def _stop_run(self, job, now):
        if job.state != "running":
            return
        ran = now - job.started
        job.counts["executed"] += ran
        job.remaining -= ran
        self.workers[job.worker].job = None
        job.worker = job.started = job.deadline = None

    def _start(self, job, worker, now):
        job.state = "running"
        job.worker = worker.id
        job.started = now
        job.deadline = now + self.lease
        job.run_no += 1
        job.counts["runs"] += 1
        worker.job = job.id
        self.dispatches.append([now, job.id, worker.id, job.attempt])
        self._schedule(now + job.remaining, COMPLETION, job, job.run_no)
        self._schedule(job.deadline, EXPIRY, job, (job.run_no, job.deadline))

    def _complete(self, job, now):
        self._stop_run(job, now)
        job.state = "completed"
        self.ended[job.id] = now
        for child_id in sorted(job.children):
            child = self.jobs[child_id]
            if child.state == "waiting" and self._parents_completed(child):
                child.state = "queued"
                self.released[child.id] = now

    def _parents_completed(self, job):
        return all(self.jobs[p].state == "completed" for p in job.parents)

    def _end_attempt(self, job, now):
        self._stop_run(job, now)
        job.counts["lost"] += job.work - job.remaining
        job.counts["attempts_ended"] += 1
        if job.attempt == job.retry_limit + 1:
            self._finish(job, "dead", now)
            return
        job.attempt += 1
        job.remaining = job.work
        job.state = "backoff"
        self._schedule(now + self.delay, RETRY_READY, job, job.attempt)

    def _finish(self, job, state, now):
        job.state = state
        self.ended[job.id] = now
        stack = list(job.children)
        while stack:
            dependent = self.jobs[stack.pop()]
            if dependent.state in TERMINAL:
                continue
            dependent.state = "cancelled"
            self.ended[dependent.id] = now
            self.cascaded[dependent.id] = now
            stack.extend(dependent.children)

    # external events ------------------------------------------------------
    def _external(self, now, events):
        for event in sorted(events, key=lambda e: e["id"]):
            if event["id"] in self.seen:
                self.audit.append([now, event["id"], "redelivery"])
                continue
            self.seen.add(event["id"])
            kind = event["type"]
            if kind == "worker_up":
                self.workers[event["worker"]].up = True
            elif kind == "worker_down":
                self._worker_down(self.workers[event["worker"]], now)
            else:
                self._job_event(now, event, self.jobs[event["job"]])

    def _worker_down(self, worker, now):
        worker.up = False
        if worker.job is not None:
            job = self.jobs[worker.job]
            self._stop_run(job, now)
            job.state = "queued"
            job.counts["evictions"] += 1

    def _job_event(self, now, event, job):
        kind = event["type"]
        if job.state in TERMINAL:
            self.audit.append([now, event["id"], "finished"])
        elif kind == "submit":
            if self._parents_completed(job):
                job.state = "queued"
                if job.parents:
                    self.released[job.id] = now
            else:
                job.state = "waiting"
        elif kind == "boost":
            job.priority += event["delta"]
        elif kind == "cancel":
            self._stop_run(job, now)
            job.counts["lost"] += job.work - job.remaining
            self._finish(job, "cancelled", now)
        elif event["attempt"] != job.attempt:
            self.audit.append([now, event["id"], "stale_attempt"])
        elif job.state != "running":
            self.audit.append([now, event["id"], "not_running"])
        elif kind == "heartbeat":
            job.deadline = now + self.lease
            self._schedule(job.deadline, EXPIRY, job, (job.run_no, job.deadline))
        else:
            self._end_attempt(job, now)

    # dispatch ---------------------------------------------------------------
    def _dispatch(self, now):
        queue = sorted((j for j in self.jobs.values() if j.state == "queued"),
                       key=lambda j: (-j.priority, j.id))
        for job in queue:
            worker = self._idle_worker(job.pool)
            if worker is None and self.preempt[job.pool]:
                worker = self._preempt_for(job, now)
            if worker is not None:
                self._start(job, worker, now)

    def _idle_worker(self, pool):
        idle = [w for w in self.workers.values() if w.pool == pool and w.up and w.job is None]
        return min(idle, key=lambda w: w.id) if idle else None

    def _preempt_for(self, job, now):
        running = [self.jobs[w.job] for w in self.workers.values() if w.pool == job.pool and w.job is not None]
        lower = [r for r in running if r.priority < job.priority]
        if not lower:
            return None
        victim = min(lower, key=lambda r: (r.priority, -r.started, -r.id))
        worker = self.workers[victim.worker]
        self._stop_run(victim, now)
        victim.state = "queued"
        victim.counts["preemptions"] += 1
        return worker

    def _snapshot(self, now):
        jobs = {}
        for job_id in sorted(self.jobs):
            job = self.jobs[job_id]
            jobs[str(job_id)] = {
                "state": job.state,
                "priority": job.priority,
                "attempt": job.attempt,
                "remaining": job.remaining_at(now),
                "worker": job.worker,
            }
        workers = {str(w.id): {"up": w.up, "job": w.job} for w in sorted(self.workers.values(), key=lambda w: w.id)}
        self.snapshots.append({"t": now, "jobs": jobs, "workers": workers})
