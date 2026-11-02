"""Write single-lever mutants of solution/solve.py to fz/mut/<lever>/reconcile.py.

usage: python3 -B mkmut.py <solve.py> <out_dir>
"""
import os
import sys

src = open(sys.argv[1]).read()
out = sys.argv[2]

PATCHES = {
    # A: closure roots skip SETTLED, WITHDRAWN and ambiguous-obligee dependents
    "A": (
        "        for node in sorted(self.forward):\n            if node in self.circular:\n                continue\n",
        "        for node in sorted(self.forward):\n            if node in self.circular:\n                continue\n"
        "            if self.state_of.get(node) in (\"SETTLED\", \"WITHDRAWN\"):\n                continue\n"
        "            if self.winner.get(node, {}).get(\"obligee_status\") == \"AMBIGUOUS\":\n                continue\n",
    ),
    # B: a period both discharged and waived also counts in periods_waived
    "B": (
        "                    if spared:\n                        self.inert += 1\n",
        "                    if spared:\n                        self.inert += 1\n                        excused_here += 1\n",
    ),
    # C: only waivers in undischarged periods draw on the allowance
    "C": (
        "                if slot >= 0 and opens < WINDOW_SHUT:\n",
        "                if slot >= 0 and opens < WINDOW_SHUT and not any(\n"
        "                    opens <= when < min(opens + width, WINDOW_SHUT)\n"
        "                    for when in discharged.get(marker, ())\n                ):\n",
    ),
    # H7: the second pass re-enters the at-or-below branch
    "H7": (
        "                if keeping:\n                    given = apportion(keeping, usable)\n",
        "                if keeping:\n                    given = (apportion(keeping, usable)\n"
        "                             if sum(keeping.values()) > usable else dict(keeping))\n",
    ),
}

for lever, (old, new) in PATCHES.items():
    assert src.count(old) == 1, (lever, src.count(old))
    d = os.path.join(out, lever)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "reconcile.py"), "w") as fh:
        fh.write(src.replace(old, new))
    print(lever, "ok")
