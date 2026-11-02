from __future__ import annotations

import hashlib
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "schema-migration-plan-repair"
text = (WORK / "before_g37/solution/TRUTH.md").read_text()


def replace_section(start: str, end: str, replacement: str) -> None:
    global text
    first = text.index(start)
    last = text.index(end, first)
    text = text[:first] + replacement.rstrip() + "\n\n" + text[last:]


replace_section(
    "Channel A is `tests/test_output.py`:",
    "Negative checks (inverted polarity",
    """Channel A is `tests/test_output.py`: 141 checks, 135 positive with total
of 591 and six negative with total weight 14. Channel B is `tests/judge.toml`:
23 criteria, 17 positive worth 49 and six negative worth 20. `tests/reward.toml`
gives each channel half of the reward after dividing by its positive total.

Channel A has ten weight-1 structure/report checks (six shipped-output-only),
seventeen isolated checks worth 41, and 108 weight-5 whole-document checks worth
540 (106 hidden worlds and two input mutations). Each world owns its generated
contract folder, feed, corrections and manifest. Its records and run summary are
compared whole with the independent reference result. The instruction explicitly
requires whole-output comparison on fresh inputs.

The 46 frozen worlds and every old check body are unchanged. Worlds 29-46 contain
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
or a partner token line and compare the complete run output again.
""",
)
replace_section(
    "The judged channel has twelve",
    "Shipped data (sha256):",
    """The judged channel has sixteen weight-3 process probes and one weight-1
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
delivered summary (-5), and an overstated passing-check size (-3).

For reference, the repaired shipped run has 5604 migrated, 1969 rejected, 5648
attempted, 1787 E_UNREACHABLE, 405 invalid corrections, 12661 completed_steps and
an empty receipt_mismatches. The shipped input bytes did not change in this round.

K14 states ten seconds per plan_migration call. Existing four-record large-graph
worlds allow 60 seconds per run. New one-record gated worlds allow 15 seconds,
including five seconds for startup/output. Ladder budgets remain unchanged. Every
submission child has 4096 MiB address space and a failed child loses only its own
check. The 300-seed Docker audit measured maximum reference planning at 0.267 s;
the old 987 reference calls returned identical plans (digest b0f465e55d9b6d1a).
The direct authoring runner passed 591/591 for the oracle; this is separate from
real Harbor gate runs, whose measured status is reported outside the bundle.
""",
)
replace_section(
    "Ordering the heap by (cost,",
    "The field view is the one representation",
    """Ordering the heap by (cost, edge-id tuple) over product nodes gives the right
answer, but a cheap region can contain many product states below the optimum cost.
A schema-graph remainder prunes the older large-graph worlds yet remains weak when
cheap region exits require a field absent from that region. The oracle combines
the schema remainder with each prerequisite field's projected-state remainder by
taking their maximum. Each projection relaxes the full state problem, so it is a
lower bound; their maximum preserves the least-cost and edge-id-list objective.
""",
)
solve = BUNDLE / "solution/solve.py"
line_count = len(solve.read_text().splitlines())
text = text.replace("`solution/solve.py` (968 lines)", f"`solution/solve.py` ({line_count} lines)")
text = text.replace("thirty text repairs", "thirty-one text repairs")
text = text.replace(
    "plus the cheapest schema-graph remainder, edge-id tuple)",
    "plus the maximum of schema and per-field projection remainders, edge-id tuple)",
)
text = text.replace(
    "the shipped contracts), and copies the repaired tree back over `/app/repo`.",
    "the shipped contracts), then the five R21-R25 probes described above, and copies the repaired tree back over `/app/repo`.",
)
text = text.replace("solve.py is 968 lines", f"solve.py is {line_count} lines")
for key, relative in (("fix_patch_sha256", "solution/solve.sh"), ("solve_py_sha256", "solution/solve.py")):
    rows = text.splitlines()
    for index, row in enumerate(rows):
        if row.startswith(key + ":"):
            comment = row.partition("  #")[2]
            rows[index] = f"{key}: {hashlib.sha256((BUNDLE / relative).read_bytes()).hexdigest()}" + ("  #" + comment if comment else "")
    text = "\n".join(rows) + "\n"
replace_section(
    "  The test channel carries 75 positive checks",
    "```",
    """  The test channel carries 135 positive checks worth 591 and six negative
  checks worth -14, so it ranges -14/591 to +1.000. The judged channel carries
  23 criteria, 17 positive worth 49 and six negative worth -20, so it ranges
  -20/49 to +1.000. reward.toml normalizes each positive denominator and gives
  each channel half of the reward, with no clamp.""",
)
(WORK / "TRUTH.g37.src.md").write_text(text)
(BUNDLE / "solution/TRUTH.md").write_text(text)
print("Rendered TRUTH from frozen factual baseline with current counts and SHA values")
