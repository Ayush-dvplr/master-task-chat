"""P12 v13 (board 6ebf33a): rewrite solution/TRUTH.md to the shipped probe prints and verifier budget and planner; run before truth_sha.py.

    python3 -B p13_truth.py
Each replacement must match exactly once in the current bundle TRUTH.md.
"""
from __future__ import annotations

import re
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent.parent.parent / "schema-migration-plan-repair"
TRUTH = BUNDLE / "solution" / "TRUTH.md"
SOLVE_LINES = len((BUNDLE / "solution" / "solve.py").read_text(encoding="utf-8").splitlines())
TESTS = (BUNDLE / "tests" / "test_output.py").read_text(encoding="utf-8")
BUDGET = re.search(r'_CHILD_SECONDS = \{"left": ([0-9.]+)\}', TESTS).group(1)
BUDGET = str(int(float(BUDGET)))

REPLACEMENTS = [
    ("""   the previous edge's operations, M7 allows a schema to repeat, and K14 needs a
   polynomial search on graphs with far too many paths to list, inside 10 seconds
   even when a cheap region of a thousand schemas multiplies the field states.""",
     """   the previous edge's operations, M7 allows a schema to repeat, and K14 needs a
   search whose work grows with the schemas, edges and field states inside the K14
   limits, never with the number of paths, and ends inside 10 seconds even when a
   cheap region of a thousand schemas multiplies the field states."""),
    ("""A schema-graph remainder prunes the older large-graph worlds yet remains weak when
cheap region exits require a field absent from that region. The oracle combines
the schema remainder with each prerequisite field's projected-state remainder by
taking their maximum. Each projection relaxes the full state problem, so it is a
lower bound; their maximum preserves the least-cost and edge-id-list objective.
Before searching, the oracle drops every edge whose prerequisites no field state
reachable from the start can meet, found by a search over field states alone in
which every edge of the domain may fire from any schema. Such an edge can never fire,
so dropping it leaves the plan unchanged; it keeps the search short when many exits
need prerequisite fields that can never be set together.""",
     """The oracle finds least remaining costs backwards from the canonical schema. The field
states of one schema that share a remaining cost are held as one bit set (at most
3^10 states for ten fields), and each edge is stepped backwards through its
operations and prerequisites. Bit sets leave a queue ordered by remaining cost plus
the least schema-only cost from the start, a consistent lower bound, so each state's
first cost is exact; the search stops once no unsettled set can lie on a cheapest
plan from the start, and no give-up limit is needed. The plan is then rebuilt
forwards by taking, at each step, the smallest edge id whose cost plus the exact
remaining cost of the state it reaches equals the cost left. Costs are positive, so
this yields the smallest edge-id list among the cheapest plans; a start state with
no cost is E_UNREACHABLE."""),
    ("""2. `plan_migration` drops edges whose prerequisites no reachable field state meets,
   then runs a heap search over (schema, field states) ordered by (cost
   plus the maximum of schema and per-field projection remainders, edge-id tuple), with prerequisites checked on the state reached and repeated
   schemas allowed.""",
     """2. `plan_migration` computes the exact least remaining cost of each (schema, field
   states) pair backwards over bit sets of field states, then rebuilds the plan
   forwards edge by edge, smallest edge id first among edges that keep the total
   least, with prerequisites checked on the state reached and repeated schemas
   allowed."""),
    ("""These grade agent probe acts, not a second correctness rule. The reference solution
runs every probe and prints `check <description> ok` with its witness.""",
     """These grade agent probe acts, not a second correctness rule. The reference solution
runs every probe and writes every result to repair-report.json. It prints the three
probe-band checks as `check <description> ok: <witness>` and the nine contract checks
as `<description>: ok (<seen>)`; the self-check probes write only to
repair-report.json."""),
    ("""seconds for startup/output. Every submission child has 4096 MiB address space and a
failed child loses only its own check.""",
     f"""seconds for startup/output. Every submission child has 4096 MiB address space and a
failed child loses only its own check. All submission children share one budget of
{BUDGET} seconds of wall time: a child runs for the smaller of its own cap and the
budget left, and none starts once it is spent, so the whole verifier ends inside the
3600 seconds of task.toml."""),
]


def main() -> None:
    text = TRUTH.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        assert text.count(old) == 1, old[:80]
        text = text.replace(old, new)
    text, first = re.subn(r"`solution/solve\.py` \(\d+ lines\)", f"`solution/solve.py` ({SOLVE_LINES} lines)", text)
    text, second = re.subn(r"solve\.py is \d+ lines", f"solve.py is {SOLVE_LINES} lines", text)
    assert first == 1 and second == 1
    TRUTH.write_text(text, encoding="utf-8")
    print(f"TRUTH rewritten: {len(REPLACEMENTS)} replacements, solve.py {SOLVE_LINES} lines, budget {BUDGET} s")


if __name__ == "__main__":
    main()
