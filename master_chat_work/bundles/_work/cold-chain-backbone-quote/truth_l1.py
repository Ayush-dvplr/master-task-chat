"""Law-1 fix 25c745d: rewrite the TRUTH.md lines the fresh-book change touches. python3 truth_l1.py <BUNDLE>"""
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "solution/TRUTH.md"
t = p.read_text()
times = json.loads((Path(__file__).parent / "runs/time_books_l1.json").read_text())
R = [
("""A textbook Dreyfus-Wagner over cold room subsets, or a corridor-order sweep whose window is
  the widest link seen, finishes it in seconds, so either looks fine locally.""",
 """A textbook Dreyfus-Wagner over cold room subsets finishes it in seconds, so it looks fine
  locally (a corridor-order sweep whose window is the widest link seen already runs out of memory on it)."""),
("""carry 16 or 17 cold rooms on narrow corridors, and the far-reaching books carry 30 to 41 cold rooms with links
  across half the book, where both methods run out of time or memory.""",
 """carry 8 to 10 cold rooms on narrow corridors, like the shipped book, and the far-reaching books carry 30 to 41
  cold rooms with links across half the book, where subsets and sweeps run out of time or memory."""),
("16 or 17 cold rooms, relay hubs with two", "8 to 10 cold rooms, relay hubs with two"),
("""Measured in Docker on the 108-point tests (27 Oct): oracle 108 with both negatives silent; exact sweep along
corridor order 81; Dreyfus-Wagner when a project has 14 or fewer cold rooms, else the corridor sweep, 84;
Dreyfus-Wagner over all cold rooms 30; terminal-metric tree, shortest-path heuristic and greedy attach 24 each;
window sweep with width from the data 65; earlier blind packages with the span check removed 68 and 84.""",
"""Measured in Docker on the 108-point tests (27 Oct, after the 25c745d fix): oracle 108 with both negatives
silent; exact sweep along corridor order 81; Dreyfus-Wagner when a project has 14 or fewer cold rooms, else the
corridor sweep, 84; Dreyfus-Wagner over all cold rooms 84; terminal-metric tree, shortest-path heuristic and
greedy attach 24 each; window sweep with width from the data 65; earlier blind packages with the span check
removed 68 and 84. Every exact program that is fast on the shipped book loses only the six far-reaching checks."""),
("""  out on the far-reaching books; subsets also time out on the fresh books.""",
 """  out on the far-reaching books."""),
]
for old, new in R:
    assert t.count(old) == 1, old[:60]
    t = t.replace(old, new)
lines = t.split("\n")
for i, line in enumerate(lines):
    for name, (n, lim, sec, rc) in times.items():
        if line.startswith("| %s | " % name):
            lines[i] = "| %s | %d | %d | %.2f |" % (name, n, lim, sec)
p.write_text("\n".join(lines))
print("TRUTH rewritten")
