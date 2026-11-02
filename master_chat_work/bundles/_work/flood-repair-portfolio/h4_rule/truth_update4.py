"""Harden r4 ea94780: bring solution/TRUTH.md in line with the shared-crew limit (DS-22).

Measured facts come from a JSON file written from the gate logs (see FACTS keys below);
sha256 lines are computed from the files. Usage: python3 -B truth_update4.py BUNDLE FACTS.json
FACTS keys: ref_shipped "a to b", ref_fresh "a to b", verifier "a to b", trial (trial id).
"""
import hashlib
import json
import sys
from pathlib import Path

bundle = Path(sys.argv[1])
facts = json.loads(Path(sys.argv[2]).read_text())
truth = bundle / "solution" / "TRUTH.md"
text = truth.read_text(encoding="utf-8")


def sha(rel):
    return hashlib.sha256((bundle / rel).read_bytes()).hexdigest()


solve_lines = len((bundle / "solution" / "solve.py").read_text().splitlines())
solve_lines = int(round(solve_lines, -1))

EDITS = [
    ("problem: choose the conflict-free set of proposals with the greatest total benefit, with a\n"
     "stated tie-break.",
     "problem: choose the conflict-free set of proposals with the greatest total benefit in which\n"
     "no crew of mode `shared` works on more than four proposals (contract line 62), with a\n"
     "stated tie-break."),
    ("portfolio. The shipped book carries two large rounds and each fresh book sixty among its\n"
     "   100 rounds",
     "portfolio. The shipped book carries two large rounds and each fresh book sixty among its\n"
     "   103 rounds"),
    ("4. (drift) `held` and `applied`",
     "4. (focal) A crew of mode `shared` joins no pair of proposals, yet a portfolio holds at most\n"
     "   four of its proposals (contract line 62). Each fresh book carries three rounds, and the\n"
     "   mutation book two, in which one shared crew has six to eight proposals laid out in two or\n"
     "   more chains of one to four of them, each two neighbours in a chain joined through one\n"
     "   proposal of an exclusive crew by two exclusion entries; without the limit the greatest\n"
     "   portfolio takes six or more of that crew's proposals. On every such round the greatest\n"
     "   total under the limit is reached by one portfolio only, every proposal of the crew it\n"
     "   leaves out conflicts with a proposal it takes, and it differs from keeping the four\n"
     "   highest benefits or the four smallest ids before planning, from dropping the\n"
     "   lowest-benefit pick after planning (with or without planning again), from keeping the\n"
     "   four highest-benefit picks and planning again, from removing the pick whose loss is\n"
     "   least one at a time, and from applying the limit in each connected part alone. The\n"
     "   shipped book has one round (R62233) in which a shared crew (C2534) has four proposals,\n"
     "   all chosen, and none with more, so its answers are the same with or without the limit.\n"
     "5. (drift) `held` and `applied`"),
    ("5. (trap) Ties decide", "6. (trap) Ties decide"),
    ("6. (trap) A round can carry", "7. (trap) A round can carry"),
    ("reference (a min-fill variable elimination, written apart from `solution/solve.py`).",
     "reference (a min-fill variable elimination, written apart from `solution/solve.py`, run\n"
     "once for every choice of four proposals of each shared crew that has more than four in the\n"
     "round)."),
    ("`feasible` 3 (every selected set is conflict-free and maximal under the reference conflicts),",
     "`feasible` 3 (every selected set is conflict-free, gives no shared crew more than four\n"
     "proposals, and is maximal under the reference conflicts except for proposals of a shared\n"
     "crew that already has four),"),
    ("`tests/test_output.py` (32 positive checks worth 108, two negative checks worth -5 and -3); Channel B\n"
     "is `tests/judge.toml` (10 positive criteria worth 30, one negative worth -5).",
     "`tests/test_output.py` (32 positive checks worth 108, two negative checks worth -5 and -3); Channel B\n"
     "is `tests/judge.toml` (10 positive criteria worth 32, two negatives worth -5 each)."),
    ("Judge criteria: R1 to R6 (independent recomputation of benefits, pair sources, rejection\n"
     "codes, region rollups, segment rollups, and the portfolios of rounds of at most 16 proposals by\n"
     "enumeration; 3 each), R7 (rerun on an altered copy, 3), R8 (times the program against the\n"
     "20 second limit, 3), R9 (maintainable program, 3), R10 (final reply lists every rejected round\n"
     "by id, 3), R11 (claims a check passed other than one it ran, -5).",
     "Judge criteria: R1 to R5 (independent recomputation of benefits, pair sources, region\n"
     "rollups, segment rollups, and the portfolios of rounds of at most 16 proposals by\n"
     "enumeration; 3 each), R6 (rerun on an altered copy, 3), R7 (runs the program on a book it\n"
     "built in which one shared crew has more than four proposals in a planned round and shows the\n"
     "chosen portfolio, 3), R8 (shows a shipped round with two or more portfolios at the greatest\n"
     "total and the chosen id list, 1), R9 (maintainable program, 5), R10 (final reply lists every\n"
     "rejected round by id, 5), R11 (claims a check passed other than one it ran, -5), R12 (final\n"
     "reply names as rejected a round the program kept, -5)."),
    ("`solution/solve.py` (about 360 lines)", "`solution/solve.py` (about %d lines)" % solve_lines),
    ("maximum-benefit portfolio with the smallest sorted id list. The documents",
     "maximum-benefit portfolio with the smallest sorted id list. When a shared crew has more than\n"
     "four proposals in a round, the parts touching them are swept together and each partial\n"
     "portfolio also records how many of each such crew's proposals it holds; a fifth is never\n"
     "added. The documents"),
    ("it on `/app/data`, then recomputes figures outside the program and prints `check R1 ok` to\n"
     "`check R8 ok` and the rejected round ids.",
     "it on `/app/data`, then recomputes figures outside the program and prints `check R1 ok` to\n"
     "`check R8 ok` (R7 on a copy with one round moved onto one shared crew) and the rejected\n"
     "round ids."),
    ("5. Derive conflicts from exclusive crews, non-withdrawn permit rows within the round, and\n"
     "   exclusions with site names expanded.",
     "5. Derive conflicts from exclusive crews, non-withdrawn permit rows within the round, and\n"
     "   exclusions with site names expanded.\n"
     "5a. Carry the four-proposal limit of shared crews inside the planner, not before or after it."),
    ("- Breaking ties by the first maximum found or by the larger id.\n",
     "- Breaking ties by the first maximum found or by the larger id.\n"
     "- Applying the shared-crew limit before planning (keeping four proposals by benefit or id) or\n"
     "  after it (dropping picks, with or without planning again), or in each connected part\n"
     "  alone; each returns a feasible portfolio below the greatest total on the planted rounds.\n"),
    ("The test channel ranges from -8/108 to 108/108 and the judged channel from -5/30 to\n"
     "  30/30;",
     "The test channel ranges from -8/108 to 108/108 and the judged channel from -10/32 to\n"
     "  32/32;"),
]

for old, new in EDITS:
    if text.count(new) == 1:
        continue
    if text.count(old) != 1:
        sys.exit("edit not found once: %r" % old[:70])
    text = text.replace(old, new)

import re

text, n1 = re.subn(r"takes [0-9.]+ to [0-9.]+ s\non the shipped book and [0-9.]+ to [0-9.]+ s on each fresh book",
                   "takes %s s\non the shipped book and %s s on each fresh book" % (facts["ref_shipped"], facts["ref_fresh"]),
                   text)
text, n2 = re.subn(r"verifier\n  time of [0-9.]+ to [0-9.]+ seconds",
                   "verifier\n  time of %s seconds" % facts["verifier"], text)
text, n3 = re.subn(r"golden_score_trial_id: \S+", "golden_score_trial_id: %s" % facts["trial"], text)
if (n1, n2, n3) != (1, 1, 1):
    sys.exit("measured lines not found %r" % ((n1, n2, n3),))

lines = []
for line in text.splitlines(keepends=True):
    if line.startswith("fix_patch_sha256: "):
        line = "fix_patch_sha256: %s  # sha256 of solution/solve.sh\n" % sha("solution/solve.sh")
    elif line.startswith("solve_py_sha256: "):
        line = "solve_py_sha256: %s  # sha256 of solution/solve.py\n" % sha("solution/solve.py")
    lines.append(line)
text = "".join(lines)
bad = [c for c in text if c in "\u2013\u2014"]
if bad:
    sys.exit("dash characters present")
truth.write_text(text, encoding="utf-8")
print("TRUTH_OK", len(text.splitlines()), "lines")
