"""Repair the leasebook package, ship it as a zip and replay the shipped book.

Stages: unpack project.zip, replace the faulty sources, zip the repaired tree,
run the archive's own tests, replay /app/data, then cross-check every
written document against figures recomputed here from the other documents.
"""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

DATA = Path("/app/data")
OUT = Path("/app/out")
WORK = Path("/app/build")
PACKAGE = "leasebook"
DOCUMENTS = ("module_core.json", "module_metrics.json", "dependency_resolution.json", "summary.json")
TERMINAL = ("completed", "dead", "cancelled")

# Repaired files; every other member of project.zip (the tests) is kept as shipped.
SOURCES = {
    'pyproject.toml': r'''[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "leasebook"
version = "1.4.0"
description = "Replay of batch lease scheduler books"
requires-python = ">=3.10"

[tool.setuptools.packages.find]
where = ["src"]
''',
    'src/leasebook/__init__.py': r'''"""leasebook: replay of batch lease scheduler books."""
from .cli import main

__version__ = "1.4.0"
__all__ = ["main", "__version__"]
''',
    'src/leasebook/__main__.py': r'''import sys

from . import main

raise SystemExit(main(sys.argv[1:]))
''',
    'src/leasebook/book.py': r'''"""Reading and validating one book directory."""
import configparser
import csv
import json
import os
import re

INPUT_FILES = (
    "policy.ini",
    "pools.json",
    "workers.csv",
    "jobs.tsv",
    "durations.csv",
    "dependencies.csv",
    "events.jsonl",
    "checkpoints.txt",
)
WHOLE = re.compile(r"[0-9]+")
JOB_EVENTS = ("submit", "heartbeat", "fail", "cancel", "boost")
WORKER_EVENTS = ("worker_down", "worker_up")


class BookError(Exception):
    """A book the replay refuses to run."""

    def __init__(self, code, detail=""):
        super().__init__(code)
        self.code = code
        self.detail = detail

    def message(self):
        if self.detail:
            return "ERROR %s %s" % (self.code, self.detail)
        return "ERROR %s" % self.code


class Book:
    """Policy, pools and the sets of one book."""

    def __init__(self, lease, delay, pools, sets):
        self.lease = lease
        self.delay = delay
        self.pools = pools
        self.sets = sets


def _bounded(text, low, high):
    text = (text or "").strip()
    if not WHOLE.fullmatch(text):
        raise BookError("INVALID_POLICY")
    value = int(text)
    if not low <= value <= high:
        raise BookError("INVALID_POLICY")
    return value


def _read_policy(path):
    parser = configparser.ConfigParser()
    try:
        with open(path, encoding="utf-8") as handle:
            parser.read_file(handle)
    except configparser.Error as exc:
        raise BookError("INVALID_POLICY") from exc
    if not parser.has_option("lease", "ticks") or not parser.has_option("retry", "delay"):
        raise BookError("INVALID_POLICY")
    return _bounded(parser.get("lease", "ticks"), 2, 20), _bounded(parser.get("retry", "delay"), 1, 10)


def _read_pools(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except ValueError as exc:
        raise BookError("INVALID_POLICY") from exc
    entries = data.get("pools") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise BookError("INVALID_POLICY")
    pools = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise BookError("INVALID_POLICY")
        name, preempt = entry.get("pool"), entry.get("preempt")
        if not isinstance(name, str) or not isinstance(preempt, bool) or name in pools:
            raise BookError("INVALID_POLICY")
        pools[name] = preempt
    return pools


def _rows(path, delimiter):
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        return [row for row in reader if any((value or "").strip() for value in row.values())]


def _events(path):
    events = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    return events


def _checkpoints(path):
    times = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            fields = line.split()
            if fields:
                times.setdefault(int(fields[0]), []).append(int(fields[1]))
    return times


def _new_set(times):
    return {"workers": {}, "jobs": {}, "work": {}, "deps": [], "events": [], "checkpoints": sorted(times)}


def _known(sets, set_id):
    if set_id not in sets:
        raise BookError("UNKNOWN_ENTITY")
    return sets[set_id]


def _fill_sets(sets, pools, files):
    for row in files["workers.csv"]:
        spec = _known(sets, int(row["set"]))
        if row["pool"] not in pools:
            raise BookError("UNKNOWN_ENTITY")
        spec["workers"][int(row["worker"])] = (row["pool"], row["state"] == "up")
    for row in files["jobs.tsv"]:
        spec = _known(sets, int(row["set"]))
        if row["pool"] not in pools:
            raise BookError("UNKNOWN_ENTITY")
        spec["jobs"][int(row["job"])] = (row["pool"], int(row["priority"]), int(row["retry_limit"]))
    for row in files["durations.csv"]:
        spec = _known(sets, int(row["set"]))
        job = int(row["job"])
        if job not in spec["jobs"]:
            raise BookError("UNKNOWN_ENTITY")
        spec["work"][job] = int(row["work"])
    for row in files["dependencies.csv"]:
        spec = _known(sets, int(row["set"]))
        parent, child = int(row["parent"]), int(row["child"])
        if parent not in spec["jobs"] or child not in spec["jobs"]:
            raise BookError("UNKNOWN_ENTITY")
        spec["deps"].append((parent, child))
    for event in files["events.jsonl"]:
        spec = _known(sets, event["set"])
        if event["type"] in JOB_EVENTS and event["job"] not in spec["jobs"]:
            raise BookError("UNKNOWN_ENTITY")
        if event["type"] in WORKER_EVENTS and event["worker"] not in spec["workers"]:
            raise BookError("UNKNOWN_ENTITY")
        spec["events"].append(event)


def _check_event_ids(sets):
    for spec in sets.values():
        first = {}
        for event in spec["events"]:
            known = first.setdefault(event["id"], event)
            if known != event:
                raise BookError("EVENT_ID_CONFLICT")


def _has_cycle(spec):
    children = {}
    for parent, child in spec["deps"]:
        children.setdefault(parent, []).append(child)
    colour = {}
    for root in sorted(children):
        if colour.get(root):
            continue
        stack = [(root, iter(children.get(root, ())))]
        colour[root] = 1
        while stack:
            node, rest = stack[-1]
            nxt = next(rest, None)
            if nxt is None:
                colour[node] = 2
                stack.pop()
            elif colour.get(nxt) == 1:
                return True
            elif not colour.get(nxt):
                colour[nxt] = 1
                stack.append((nxt, iter(children.get(nxt, ()))))
    return False


def load_book(data_dir):
    """Read every input file of a book; raise BookError for a refused book."""
    for name in INPUT_FILES:
        if not os.path.isfile(os.path.join(data_dir, name)):
            raise BookError("MISSING_INPUT", name)
    path = lambda name: os.path.join(data_dir, name)
    lease, delay = _read_policy(path("policy.ini"))
    pools = _read_pools(path("pools.json"))
    files = {
        "workers.csv": _rows(path("workers.csv"), ","),
        "jobs.tsv": _rows(path("jobs.tsv"), "\t"),
        "durations.csv": _rows(path("durations.csv"), ","),
        "dependencies.csv": _rows(path("dependencies.csv"), ","),
        "events.jsonl": _events(path("events.jsonl")),
    }
    sets = {set_id: _new_set(times) for set_id, times in _checkpoints(path("checkpoints.txt")).items()}
    _fill_sets(sets, pools, files)
    _check_event_ids(sets)
    if any(_has_cycle(spec) for spec in sets.values()):
        raise BookError("DEPENDENCY_CYCLE")
    return Book(lease, delay, pools, sets)
''',
    'src/leasebook/cli.py': r'''"""Command line entry: leasebook DATA_DIR OUT_DIR."""
import json
import os
import sys

from .book import BookError, load_book
from .replay import SetReplay
from .report import build_documents


def replay_book(book):
    """Replay every set of a loaded book; returns set id -> SetReplay."""
    return {
        set_id: SetReplay(spec, book.lease, book.delay, book.pools).run()
        for set_id, spec in book.sets.items()
    }


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: leasebook DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = args
    try:
        book = load_book(data_dir)
    except BookError as exc:
        print(exc.message())
        return 2
    documents = build_documents(replay_book(book))
    os.makedirs(out_dir, exist_ok=True)
    for name, document in documents.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=1, sort_keys=True)
            handle.write("\n")
    return 0
''',
    'src/leasebook/replay.py': r'''"""Replay of one set: timed internal events, external events and dispatch."""
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
''',
    'src/leasebook/report.py': r'''"""Turning replayed sets into the four book documents."""
import hashlib

from .replay import COUNTERS, REASONS, TERMINAL


def _core(replay):
    return {"checkpoints": replay.snapshots, "dispatches": replay.dispatches, "audit": replay.audit}


def _metrics(replay):
    jobs = {}
    totals = dict.fromkeys(COUNTERS, 0)
    for job_id in sorted(replay.jobs):
        counts = replay.jobs[job_id].counts
        jobs[str(job_id)] = dict(counts)
        for name in COUNTERS:
            totals[name] += counts[name]
    reasons = dict.fromkeys(REASONS, 0)
    for _, _, reason in replay.audit:
        reasons[reason] += 1
    totals["audit"] = reasons
    return {"jobs": jobs, "totals": totals}


def _outcome(replay, parent_id):
    parent = replay.jobs[parent_id]
    if parent.state == "completed":
        return "satisfied", replay.ended[parent_id]
    if parent.state in TERMINAL:
        return "broken", replay.ended[parent_id]
    return "open", None


def _dependencies(replay):
    edges = []
    pairs = sorted({(p, c) for p, job in replay.jobs.items() for c in job.children})
    for parent, child in pairs:
        outcome, when = _outcome(replay, parent)
        edges.append({"parent": parent, "child": child, "outcome": outcome, "t": when})
    return {
        "edges": edges,
        "released": {str(j): t for j, t in sorted(replay.released.items())},
        "cascaded": {str(j): t for j, t in sorted(replay.cascaded.items())},
    }


def _summary(replay):
    final = {"completed": 0, "dead": 0, "cancelled": 0, "other": 0}
    for job in replay.jobs.values():
        final[job.state if job.state in TERMINAL else "other"] += 1
    lines = "".join("%d %d %d %d\n" % tuple(row) for row in replay.dispatches)
    return {
        "final": final,
        "executed": sum(job.counts["executed"] for job in replay.jobs.values()),
        "lost": sum(job.counts["lost"] for job in replay.jobs.values()),
        "dispatch_sha256": hashlib.sha256(lines.encode("ascii")).hexdigest(),
    }


def build_documents(replays):
    """Map set id -> finished SetReplay to the four documents, keyed by name."""
    order = sorted(replays)
    return {
        "module_core.json": {"sets": {str(s): _core(replays[s]) for s in order}},
        "module_metrics.json": {"sets": {str(s): _metrics(replays[s]) for s in order}},
        "dependency_resolution.json": {"sets": {str(s): _dependencies(replays[s]) for s in order}},
        "summary.json": {"set_count": len(order), "sets": {str(s): _summary(replays[s]) for s in order}},
    }
''',
}


def unpack(archive, target):
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            dest = (target / name).resolve()
            if not str(dest).startswith(str(target.resolve())):
                raise SystemExit("unsafe member %s" % name)
        zf.extractall(target)


def repair(tree):
    for rel, text in sorted(SOURCES.items()):
        path = tree / rel
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print("changed %s" % rel)


def pack(tree, archive):
    files = sorted(p for p in tree.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(tree).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())


def version_of(tree):
    import tomllib
    with open(tree / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def run_unittests(tree):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    probe = (
        "import sys, unittest\n"
        "suite = unittest.defaultTestLoader.discover('tests')\n"
        "result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)\n"
        "print(result.testsRun, len(result.failures), len(result.errors), len(result.skipped))\n"
    )
    done = subprocess.run([sys.executable, "-c", probe], cwd=tree, env=env,
                          capture_output=True, text=True, check=True)
    run, failures, errors, skipped = (int(x) for x in done.stdout.split())
    return run, run - failures - errors - skipped


def write_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.write("\n")


def replay(tree, data, out):
    env = dict(os.environ, PYTHONPATH=str(tree / "src"), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-m", PACKAGE, str(data), str(out)], env=env,
                          capture_output=True, text=True)


def load(out):
    return {name: json.loads((out / name).read_text(encoding="utf-8")) for name in DOCUMENTS}


def read_pools_of_workers(data):
    pools = {}
    with open(data / "workers.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            pools[(row["set"], row["worker"])] = row["pool"]
    jobs = {}
    with open(data / "jobs.tsv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            jobs[(row["set"], row["job"])] = row["pool"]
    return pools, jobs


def check_core(docs, data):
    worker_pool, job_pool = read_pools_of_workers(data)
    for sid, body in docs["module_core.json"]["sets"].items():
        for cp in body["checkpoints"]:
            for jid, job in cp["jobs"].items():
                if job["state"] != "running":
                    assert job["worker"] is None, (sid, cp["t"], jid)
                    continue
                slot = cp["workers"][str(job["worker"])]
                assert slot["up"] and slot["job"] == int(jid), (sid, cp["t"], jid)
                assert worker_pool[(sid, str(job["worker"]))] == job_pool[(sid, jid)], (sid, jid)
            for wid, slot in cp["workers"].items():
                if slot["job"] is not None:
                    assert cp["jobs"][str(slot["job"])]["worker"] == int(wid), (sid, cp["t"], wid)
    print("check C1 ok")


def check_metrics(docs):
    for sid, body in docs["module_metrics.json"]["sets"].items():
        core = docs["module_core.json"]["sets"][sid]
        runs = Counter(str(row[1]) for row in core["dispatches"])
        reasons = Counter(row[2] for row in core["audit"])
        for jid, counts in body["jobs"].items():
            assert counts["runs"] == runs.get(jid, 0), (sid, jid)
        for name, total in body["totals"].items():
            if name == "audit":
                assert total == {r: reasons.get(r, 0) for r in total}, sid
            else:
                assert total == sum(c[name] for c in body["jobs"].values()), (sid, name)
    print("check C2 ok")


def check_dependencies(docs):
    for sid, body in docs["dependency_resolution.json"]["sets"].items():
        last = docs["module_core.json"]["sets"][sid]["checkpoints"][-1]["jobs"]
        for edge in body["edges"]:
            state = last[str(edge["parent"])]["state"]
            want = "satisfied" if state == "completed" else "broken" if state in TERMINAL else "open"
            assert edge["outcome"] == want, (sid, edge)
            assert (edge["t"] is None) == (want == "open"), (sid, edge)
        for jid in body["cascaded"]:
            assert last[jid]["state"] == "cancelled", (sid, jid)
    print("check C3 ok")


def check_summary(docs):
    summary = docs["summary.json"]
    assert summary["set_count"] == len(docs["module_core.json"]["sets"])
    for sid, body in summary["sets"].items():
        core = docs["module_core.json"]["sets"][sid]
        totals = docs["module_metrics.json"]["sets"][sid]["totals"]
        final = Counter()
        for job in core["checkpoints"][-1]["jobs"].values():
            final[job["state"] if job["state"] in TERMINAL else "other"] += 1
        assert body["final"] == {k: final.get(k, 0) for k in body["final"]}, sid
        assert (body["executed"], body["lost"]) == (totals["executed"], totals["lost"]), sid
        text = "".join("%d %d %d %d\n" % tuple(row) for row in core["dispatches"])
        assert body["dispatch_sha256"] == hashlib.sha256(text.encode()).hexdigest(), sid
    print("check C4 ok")


def check_archive(archive):
    report = json.loads((OUT / "build_report.json").read_text(encoding="utf-8"))
    assert report["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as zf:
        assert report["files"] == sorted(zf.namelist())
    fresh = Path(tempfile.mkdtemp(prefix="leasebook-check-"))
    unpack(archive, fresh)
    selftest = json.loads((OUT / "selftest.json").read_text(encoding="utf-8"))
    run, passed = run_unittests(fresh)
    assert (selftest["tests_run"], selftest["tests_passed"]) == (run, passed)
    assert selftest["version"] == report["version"] == version_of(fresh)
    shutil.rmtree(fresh)
    print("check C5 ok")


def check_altered_copy(tree, docs):
    scratch = Path(tempfile.mkdtemp(prefix="leasebook-alter-"))
    copy = scratch / "book"
    shutil.copytree(DATA, copy)
    policy = (copy / "policy.ini").read_text(encoding="utf-8")
    ticks = int(policy.split("ticks =")[1].split()[0])
    (copy / "policy.ini").write_text(policy.replace("ticks = %d" % ticks, "ticks = %d" % (ticks + 3)),
                                     encoding="utf-8")
    done = replay(tree, copy, scratch / "out")
    assert done.returncode == 0, done.stdout + done.stderr
    moved = load(scratch / "out")["summary.json"]["sets"]
    changed = [s for s, body in moved.items() if body != docs["summary.json"]["sets"][s]]
    assert changed, "altered lease left every set unchanged"
    shutil.rmtree(scratch)
    print("check J9 ok (%d sets moved)" % len(changed))


def main():
    tree = WORK / PACKAGE
    unpack(DATA / "project.zip", tree)
    repair(tree)
    archive = OUT / "package.zip"
    pack(tree, archive)
    built = WORK / "from_zip"
    unpack(archive, built)
    run, passed = run_unittests(built)
    if passed != run:
        raise SystemExit("package tests failed: %d of %d passed" % (passed, run))
    version = version_of(built)
    write_json(OUT / "selftest.json", {"package": PACKAGE, "version": version,
                                       "tests_run": run, "tests_passed": passed})
    with zipfile.ZipFile(archive) as zf:
        members = sorted(zf.namelist())
    write_json(OUT / "build_report.json", {
        "package": PACKAGE, "version": version, "files": members,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()})
    done = replay(built, DATA, OUT)
    if done.returncode != 0:
        raise SystemExit("replay refused the shipped book: " + done.stdout + done.stderr)
    docs = load(OUT)
    check_core(docs, DATA)
    check_metrics(docs)
    check_dependencies(docs)
    check_summary(docs)
    check_archive(archive)
    check_altered_copy(built, docs)
    print("wrote %s" % ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
