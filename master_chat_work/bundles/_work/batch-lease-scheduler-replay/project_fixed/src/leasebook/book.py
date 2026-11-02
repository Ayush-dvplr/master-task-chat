"""Reading and validating one book directory."""
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
