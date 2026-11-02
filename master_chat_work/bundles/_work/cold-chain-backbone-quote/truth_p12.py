"""P12 (QC v1 fix): rewrite the TRUTH.md lines the fixes touch. python3 truth_p12.py <BUNDLE> <scores.json>

scores.json: {"oracle": 109, "dw_global": x, "kmb": x, ...} measured in Docker on the current tests.
"""
import json
import sys
from pathlib import Path

p = Path(sys.argv[1]) / "solution/TRUTH.md"
s = json.loads(Path(sys.argv[2]).read_text())
t = p.read_text()
R = [
("""Expected documents are recomputed at grade time by an independent reader and exact solver inside the test file and
compared whole (parsed JSON); a mismatch reports the first differing path.""",
"""Expected documents are recomputed at grade time by a reader and an exact solver inside the test file that are
written apart from the oracle: links are grouped into blocks by taking each site away in turn and seeing which of its
links still reach each other, and each block is solved either link by link or by growing partial trees from one
queue ordered by price; links carry a plus or minus rank bit, and a network is the only cheapest one when both signs
pick it. Documents are compared whole (parsed JSON); a mismatch reports the first differing path."""),
("the rejection book plants every rejection code;",
 "the rejection book plants every rejection code, and one project carries a duplicate site and a link to an unknown site;"),
("Channel A checks and weights (positive weight total 108):", "Channel A checks and weights (positive weight total 109):"),
("| archive_follows_build_config | 1 |\n", "| archive_follows_build_config | 1 |\n| archived_package_metadata | 1 |\n"),
("""Measured in Docker on the 108-point tests (27 Oct, after the 25c745d fix): oracle 108 with both negatives
silent; exact sweep along corridor order 81; Dreyfus-Wagner when a project has 14 or fewer cold rooms, else the
corridor sweep, 84; Dreyfus-Wagner over all cold rooms 84; terminal-metric tree, shortest-path heuristic and
greedy attach 24 each; window sweep with width from the data 65; earlier blind packages with the span check
removed 68 and 84. Every exact program that is fast on the shipped book loses only the six far-reaching checks.""",
"""Measured in Docker on these tests (points of 109): oracle %(oracle)d with both negatives silent; Dreyfus-Wagner
over all cold rooms %(dw_global)d; terminal-metric tree %(kmb)d; activation charged per booked link %(perlink)d; report lines
charged per booked link with the quote right %(report_only)d. An exact program that is fast on the shipped book loses
only the six far-reaching checks.""" % s),
]
for old, new in R:
    assert t.count(old) == 1, old[:60]
    t = t.replace(old, new)
p.write_text(t)
print("TRUTH rewritten")
