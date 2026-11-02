"""Second, independent recomputation of the hidden planner cases.

    python3 check_exact.py

1. Brute force: enumerate every walk of at most MAX_STEPS edges on each small hidden
   graph (explicit records, no state abstraction, no heap), keep the minimum
   (cost, edge-id list), and compare with the expected value the tests hold.
2. Ladders: compare the tests' planner (backward cost-to-go plus greedy) with the
   repaired package's planner (heap over (cost, path)) and, for ladder_small, with
   brute force too.
3. Executor cases: replay each supplied plan with a plain dict simulator written here
   and compare with the tests' expected result.
Exit status 0 when every comparison agrees.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parent / "rewardkit_stub"))
sys.path.insert(0, str(WORK / "repo_fixed" / "src"))
spec = importlib.util.spec_from_file_location("hidden", WORK / "test_output.src.py")
hidden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hidden)
import migrakit  # noqa: E402

MAX_STEPS = 8


def present(spec, dom, name, record):
    if name not in record:
        return False
    if record[name] is not None:
        return True
    row = next((p for p in spec.policy if p[0] == dom and p[1] == name), None)
    return (row[4] if row and row[4] else spec.presence) == "present"


def apply(spec, dom, record, ops):
    record = dict(record)
    for op in filter(None, ops.split(";")):
        kind, rest = op.split(":", 1)
        if kind == "rename":
            a, b = rest.split(">")
            if a in record:
                record[b] = record.pop(a)
        elif kind == "drop":
            record.pop(rest, None)
        elif kind == "add":
            row = next((p for p in spec.policy if p[0] == dom and p[1] == rest), None)
            if row and row[2]:
                fill = row[3] if row[3] else spec.fill
                if rest not in record or (record[rest] is None and fill == "absent_or_null"):
                    record[rest] = "default"
    return record


def allowed(spec, dom, record, req):
    for part in filter(None, req.split(";")):
        kind, name = part.split(":")
        if present(spec, dom, name, record) != (kind == "has"):
            return False
    return True


def brute(spec, start, payload, limit=MAX_STEPS):
    dom = start.rsplit(".v", 1)[0]
    target = next(s for s in spec.canonical if s.startswith(dom + ".v"))
    if start == target:
        return []
    best = None
    stack = [(start, payload, [], 0)]
    while stack:
        node, record, path, cost = stack.pop()
        if node == target:
            if best is None or (cost, path) < best:
                best = (cost, path)
            continue
        if len(path) == limit:
            continue
        for e in spec.edges:
            if e[1] == node and allowed(spec, dom, record, e[3]):
                stack.append((e[2], apply(spec, dom, record, e[4]), path + [e[0]], cost + int(e[5])))
    return None if best is None else best[1]


def simulate(spec, job):
    dom = job["schema"].rsplit(".v", 1)[0]
    record, current, seen, applied = dict(job["payload"]), job["schema"], set(), []
    edges = {e[0]: e for e in spec.edges}

    def arrive(schema):
        if schema in seen:
            return
        seen.add(schema)
        for c in job["corrections"]:
            if c["schema"] == schema:
                applied.append(c["id"])
                if c["op"] == "SET":
                    record[c["field"]] = c["value"]
                elif c["op"] == "UNSET":
                    record.pop(c["field"], None)
                else:
                    record[c["field"]] = None

    arrive(current)
    for step, eid in enumerate(job["plan"]):
        e = edges[eid]
        if not allowed(spec, dom, record, e[3]):
            return {"status": "failed", "failed_edge": eid, "completed_steps": step, "schema": current, "applied": applied}
        record = apply(spec, dom, record, e[4])
        current = e[2]
        arrive(current)
    return {"status": "migrated", "schema": current, "keys": sorted(record), "applied": applied}


def main() -> int:
    problems = []
    for build in (hidden.case_dropped_earlier, hidden.case_enabled_earlier, hidden.case_revisit, hidden.case_renamed_null,
                  hidden.case_tie_first_edge, hidden.case_tie_longer, hidden.case_unreachable):
        s, job, expected = build()
        got = brute(s, job["schema"], job["payload"])
        want = None if expected == "E_UNREACHABLE" else expected
        print(f"{build.__name__}: brute {got} expected {want}")
        if got != want:
            problems.append(build.__name__)
    for name in hidden.LADDERS:
        s, job, expected = hidden.case_ladder(name)
        package = migrakit.plan_migration(migrakit.load_contracts(s.write()), job["schema"], job["payload"])
        extra = ""
        if name == "ladder_small":
            forced = brute(s, job["schema"], job["payload"], limit=7)
            extra = f" brute={'agree' if forced == expected else forced}"
            if forced != expected:
                problems.append(name + " brute")
        print(f"{name}: tests-planner == package-planner: {package == expected}{extra}")
        if package != expected:
            problems.append(name)
    for build in (hidden.case_unset_breaks, hidden.case_null_blocks_lacks, hidden.case_null_counted_absent,
                  hidden.case_first_arrival, hidden.case_source_arrival):
        s, job, expected = build()
        sim = simulate(s, job)
        ok = sim["status"] == expected["status"] and sim["applied"] == expected["corrections_applied"] and sim["schema"] == expected["schema"]
        if expected["status"] == "failed":
            ok = ok and sim["failed_edge"] == expected["failed_edge"] and sim["completed_steps"] == expected["completed_steps"]
        else:
            ok = ok and sim["keys"] == sorted(expected["payload"])
        print(f"{build.__name__}: simulator agrees {ok}")
        if not ok:
            problems.append(build.__name__)
    print("PROBLEMS", problems or "none")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
