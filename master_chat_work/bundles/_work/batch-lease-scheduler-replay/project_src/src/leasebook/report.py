"""Turning replayed sets into the four book documents."""
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
    lines = "".join("%d,%d,%d,%d\n" % tuple(row) for row in replay.dispatches)
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
