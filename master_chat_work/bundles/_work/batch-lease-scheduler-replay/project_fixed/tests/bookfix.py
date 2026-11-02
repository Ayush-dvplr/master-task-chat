"""Tiny book fixtures written to a temporary directory."""
import json
import os
import sys
import tempfile

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

POLICY = "[lease]\nticks = 10\n\n[retry]\ndelay = 2\n"
POOLS = {"pools": [{"pool": "oak", "preempt": True}, {"pool": "elm", "preempt": False}]}
WORKERS = [(1, 11, "oak", "up"), (1, 12, "elm", "up")]
JOBS = [(1, 5, "oak", 3, 1), (1, 6, "oak", 2, 1), (1, 7, "elm", 4, 0)]
WORK = [(1, 5, 4), (1, 6, 3), (1, 7, 5)]
DEPS = [(1, 5, 6)]
EVENTS = [
    {"set": 1, "id": 1, "t": 0, "type": "submit", "job": 5},
    {"set": 1, "id": 2, "t": 1, "type": "submit", "job": 6},
    {"set": 1, "id": 3, "t": 2, "type": "submit", "job": 7},
]
CHECKPOINTS = [(1, 3), (1, 30)]


def write_book(policy=POLICY, pools=POOLS, workers=WORKERS, jobs=JOBS, work=WORK, deps=DEPS,
               events=EVENTS, checkpoints=CHECKPOINTS, blank_lines=False):
    root = tempfile.mkdtemp(prefix="leasebook-")

    def table(name, header, rows, sep):
        with open(os.path.join(root, name), "w", encoding="utf-8") as handle:
            handle.write(sep.join(header) + "\n")
            for row in rows:
                handle.write(sep.join(str(v) for v in row) + "\n")

    with open(os.path.join(root, "policy.ini"), "w", encoding="utf-8") as handle:
        handle.write(policy)
    with open(os.path.join(root, "pools.json"), "w", encoding="utf-8") as handle:
        json.dump(pools, handle)
    table("workers.csv", ("set", "worker", "pool", "state"), workers, ",")
    table("jobs.tsv", ("set", "job", "pool", "priority", "retry_limit"), jobs, "\t")
    table("durations.csv", ("set", "job", "work"), work, ",")
    table("dependencies.csv", ("set", "parent", "child"), deps, ",")
    with open(os.path.join(root, "events.jsonl"), "w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
            if blank_lines:
                handle.write("\n")
    with open(os.path.join(root, "checkpoints.txt"), "w", encoding="utf-8") as handle:
        for set_id, t in checkpoints:
            handle.write("%d %d\n" % (set_id, t))
    return root
