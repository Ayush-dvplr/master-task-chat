"""Harden r2 cb8dada: bring solution/TRUTH.md in line with the shipped bundle (DS-22).

Facts come from measured logs: truth_facts.log (book shapes, run in the verifier image),
kill2.log (oracle seconds per fresh book), hardengate lanes (oracle/owner/nop rewards and
verifier seconds). The sha256 lines are computed from the files, never typed.
Usage: python3 -B truth_update.py BUNDLE
"""
import hashlib
import sys
from pathlib import Path

bundle = Path(sys.argv[1])
truth = bundle / "solution" / "TRUTH.md"
text = truth.read_text(encoding="utf-8")


def sha(rel):
    return hashlib.sha256((bundle / rel).read_bytes()).hexdigest()


EDITS = [
    ("portfolio. Each book carries two large rounds (144 to 160 proposals, each in conflict with\n"
     "   about 4.8 others) whose conflicts form a planar near-lattice with odd holes and near-equal\n"
     "   benefits. Greedy by benefit or by benefit per conflict, greedy followed by one-for-many and\n",
     "portfolio. The shipped book carries two large rounds and each fresh book sixty among its\n"
     "   100 rounds (144 to 160 proposals, each in conflict with 4.7 to 5.0 others); their conflicts\n"
     "   form a planar near-lattice with odd holes and near-equal benefits. Greedy by benefit or by\n"
     "   benefit per conflict, greedy followed by one-for-many and\n"),
    ("all return feasible portfolios that fall short on these\n"
     "   rounds, by 44 to 14,160 benefit units. Branch",
     "all return feasible portfolios that fall short on these\n"
     "   rounds. Branch"),
    ("subsets of that frontier, or a variable elimination along a min-fill order, finishes a large\n"
     "   round in about 0.1 seconds. Searching",
     "subsets of that frontier finishes a large round in about 0.02 seconds and a fresh book in\n"
     "   about 1 second; a variable elimination along a min-fill order takes 6 to 8 seconds a fresh\n"
     "   book, and a search that needs a second or more a large round exceeds the 20 second limit\n"
     "   on a fresh book. Searching"),
    ("large rounds carry 430 to 490.",
     "large rounds carry 425 to 517."),
    ("Every\nlarge round of every book has exactly one maximum-benefit portfolio; each planted tie round\n"
     "has exactly two.",
     "Nine of\nthe 180 large rounds of the fresh books have two or four maximum-benefit portfolios and are\n"
     "decided by the tie rule (contract line 62); every other large round has exactly one, and each\n"
     "planted tie round has exactly two. Each run of the program starts in its own session, and the\n"
     "whole group is killed when the run ends."),
    ("on the shipped book and 0.08 to 0.12 s on each fresh book, with 1 or 2 CPUs.",
     "on the shipped book and 0.95 to 1.20 s on each fresh book, with 2 CPUs, one of them kept busy\n"
     "or not."),
    ("time it on the\n   two large rounds of the shipped book and keep it far inside 20 seconds.",
     "time it on a\n   book at the stated limits, not only on the shipped book, and keep it far inside 20\n"
     "   seconds."),
    ("- Generic branch and bound or memoised search in id order times out on the large rounds.\n",
     "- Generic branch and bound or memoised search in id order times out on the large rounds.\n"
     "- A planner timed only on the two large rounds of the shipped book can pass there and still\n"
     "  exceed 20 seconds on a fresh book with sixty of them.\n"),
    ("golden_score_trial_id: flood-repair-portfolio__j89Z7bE\n",
     "golden_score_trial_id: plain__gYTHojZ\n"),
    ("  Three harbor 0.24 oracle runs of the test channel score 1.0 (108 of 108) with a\n"
     "  verifier time of 21 to 24 seconds; a no-op run scores 0.0.",
     "  Three harbor oracle runs of the test channel score 1.0 (108 of 108) with a verifier\n"
     "  time of 124 to 152 seconds; an owner-only run scores 1.0; a no-op run scores 0.0."),
]

for old, new in EDITS:
    if text.count(new) == 1:
        continue
    if text.count(old) != 1:
        sys.exit("edit not found once: %r" % old[:60])
    text = text.replace(old, new)

lines = []
for line in text.splitlines(keepends=True):
    if line.startswith("fix_patch_sha256: "):
        line = "fix_patch_sha256: %s  # sha256 of solution/solve.sh\n" % sha("solution/solve.sh")
    elif line.startswith("solve_py_sha256: "):
        line = "solve_py_sha256: %s  # sha256 of solution/solve.py\n" % sha("solution/solve.py")
    lines.append(line)
text = "".join(lines)
bad = [c for c in text if c in "\u2013\u2014"]
assert not bad and "\r" not in text, "dash or CR"
truth.write_text(text, encoding="utf-8")
print("TRUTH updated", hashlib.sha256(text.encode()).hexdigest()[:12])
