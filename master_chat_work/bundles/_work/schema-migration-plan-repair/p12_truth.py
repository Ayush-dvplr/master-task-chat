"""P12 v12 (board 08741c4): rewrite solution/TRUTH.md to the current grading; run before truth_sha.py.

    python3 -B p12_truth.py
Each replacement must match exactly once in the current bundle TRUTH.md.
"""
from __future__ import annotations

from pathlib import Path

BUNDLE = Path(__file__).resolve().parent.parent.parent / "schema-migration-plan-repair"
TRUTH = BUNDLE / "solution" / "TRUTH.md"
SOLVE_LINES = len((BUNDLE / "solution" / "solve.py").read_text(encoding="utf-8").splitlines())

REPLACEMENTS = [
    ("23 criteria, 17 positive worth 49 and six negative worth 20. `tests/reward.toml`",
     "21 criteria, 15 positive worth 43 and six negative worth 20. `tests/reward.toml`"),
    ("""The 46 frozen worlds and every old check body are unchanged. Worlds 29-46 contain
large migration graphs, four records per world, and a priced corridor beside a cheap
state-changing region. Worlds 47-106 add one hard record each from the same generator
family with their own RNG streams (9000 plus world number). Their cheap region exits
require a field established only through a dear entry. A schema-only remainder sees
an attractive exit that the reached field state cannot use. Each generator draw
asserts the existing K14 bounds, positive integer costs, a reachable non-empty plan,
and a plan length at most 80. No shipped data, contract or instruction changed.

The 60 new worlds carry 300/591 = 50.76% of positive test weight. All hidden
whole-document checks together carry 540/591 = 91.37%. Every new world has its own
submission call and exact comparison. The two existing mutations change a receipt
or a partner token line and compare the complete run output again.""",
     """Worlds 29-46 contain large migration graphs, four records per world, and a priced
corridor beside a cheap state-changing region. Worlds 47-106 hold one hard record
each from the same generator family with their own RNG streams (9000 plus world
number). Their cheap region exits require a field established only through a dear
entry. A schema-only remainder sees an attractive exit that the reached field state
cannot use. Each generator draw asserts the K14 bounds, positive integer costs, a
reachable non-empty plan, and a plan length at most 80.

Worlds 47-106 carry 300/591 = 50.76% of positive test weight. All hidden
whole-document checks together carry 540/591 = 91.37%. Each world has its own
submission call and exact comparison. The two input mutations change a receipt
or a partner token line and compare the complete run output again."""),
    ("""The judged channel has sixteen weight-3 process probes and one weight-1
code-quality criterion. The following references use stable logical IDs from the
design and oracle witness labels. The live kit requires sequential physical IDs:
logical R6-R12 map to R5-R11, R14-R20 map to R12-R18, and R21-R25 map to R19-R23.
R1-R4 cover damaged receipts, partner-rejected fingerprints,
parse-rejected batch scope and spaced tokens. R6-R12 cover a timed built graph of at
least a thousand schemas, a separate search comparison, costly edges, an unnamed
extra file, an empty manifest batch, reused CLI output, and an altered shipped edge.
R5 and the easy --help R13 criterion were removed. New R21-R25 ask for a missing
declared-file probe, an empty-feed probe, a non-integer edge-cost probe, a changed
policy-row copy, and a changed explicit_null-line copy. These grade agent probe acts,
not a required malformed-input output or a second correctness rule. The reference
solution runs them and prints `check R21 ok` through `check R25 ok` with witnesses.
R14 remains the sole J4 criterion: every private helper in the repaired package is
called. Negative criteria remain debug residue (-3), grader-file reading (-5), a
third-party install (-1), an unrun check claim (-3), a figure differing from the
delivered summary (-5), and an overstated passing-check size (-3).""",
     """The judged channel has fourteen weight-3 process probes and one weight-1
code-quality criterion. R1-R4 cover damaged receipts, partner-rejected fingerprints,
parse-rejected batch scope and spaced tokens. R5-R11 cover a timed built graph of at
least a thousand schemas, a separate search comparison, costly edges, an unnamed
extra file, an empty manifest batch, reused CLI output, and an altered shipped edge.
R12 is the J4 criterion: every private helper in the repaired package is called.
R13-R18 are negative: debug residue (-3), grader-file reading (-5), a third-party
install (-1), an unrun check claim (-3), a figure differing from the delivered
summary (-5), and an overstated passing-check size (-3). R19-R21 ask for an
empty-feed probe, a changed policy-row copy, and a changed explicit_null-line copy.
These grade agent probe acts, not a second correctness rule. The reference solution
runs every probe and prints `check <description> ok` with its witness."""),
    ("""an empty receipt_mismatches. The shipped input bytes did not change in this round.""",
     """an empty receipt_mismatches."""),
    ("""K14 states ten seconds per plan_migration call. Existing four-record large-graph
worlds allow 60 seconds per run. New one-record gated worlds allow 15 seconds,
including five seconds for startup/output. Ladder budgets remain unchanged. Every
submission child has 4096 MiB address space and a failed child loses only its own
check. The 300-seed Docker audit measured maximum reference planning at 0.267 s;
the old 987 reference calls returned identical plans (digest b0f465e55d9b6d1a).
The direct authoring runner passed 591/591 for the oracle; this is separate from
real Harbor gate runs, whose measured status is reported outside the bundle.""",
     """K14 states ten seconds per plan_migration call. Four-record large-graph worlds
allow 60 seconds per run. One-record gated worlds allow 15 seconds, including five
seconds for startup/output. Every submission child has 4096 MiB address space and a
failed child loses only its own check."""),
    ("""taking their maximum. Each projection relaxes the full state problem, so it is a
lower bound; their maximum preserves the least-cost and edge-id-list objective.""",
     """taking their maximum. Each projection relaxes the full state problem, so it is a
lower bound; their maximum preserves the least-cost and edge-id-list objective.
Before searching, the oracle drops every edge whose prerequisites no field state
reachable from the start can meet, found by a search over field states alone in
which every edge of the domain may fire from any schema. Such an edge can never fire,
so dropping it leaves the plan unchanged; it keeps the search short when many exits
need prerequisite fields that can never be set together."""),
    ("""2. `plan_migration` runs a heap search over (schema, field states) ordered by (cost""",
     """2. `plan_migration` drops edges whose prerequisites no reachable field state meets,
   then runs a heap search over (schema, field states) ordered by (cost"""),
    ("(a 1,082-schema graph timed and compared with a separate search, edge costs above one\n"
     "million, an unnamed extra file, a manifest batch with no lines, a command-line rerun\n"
     "over an older output folder, `--help`, a malformed contract file, an altered copy of\n"
     "the shipped contracts), then the five R21-R25 probes described above, and copies the repaired tree back over `/app/repo`.",
     "(a 1,082-schema graph timed and compared with a separate search, edge costs above one\n"
     "million, an unnamed extra file, a manifest batch with no lines, a command-line rerun\n"
     "over an older output folder, `--help`, a malformed contract file, an altered copy of\n"
     "the shipped contracts), then three probes on copies of `/app/ci` (an empty feed file,\n"
     "a changed field_policy.tsv row, a changed explicit_null line), and copies the repaired\n"
     "tree back over `/app/repo`."),
    ("""  23 criteria, 17 positive worth 49 and six negative worth -20, so it ranges
  -20/49 to +1.000.""",
     """  21 criteria, 15 positive worth 43 and six negative worth -20, so it ranges
  -20/43 to +1.000."""),
]


def main() -> None:
    text = TRUTH.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        assert text.count(old) == 1, old[:60]
        text = text.replace(old, new)
    for old in ("`solution/solve.py` (1114 lines)", "solve.py is 1114 lines"):
        assert text.count(old) == 1, old
        text = text.replace(old, old.replace("1114", str(SOLVE_LINES)))
    TRUTH.write_text(text, encoding="utf-8")
    print("TRUTH rewritten;", len(REPLACEMENTS), "replacements; solve.py", SOLVE_LINES, "lines")


if __name__ == "__main__":
    main()
