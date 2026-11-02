"""Write one mutant of solve.py per decode rule of a `none` entry.
Usage: python3 -B make_mutants.py <solve.py> <out_dir>"""
import sys
from pathlib import Path
src = Path(sys.argv[1]).read_text()
MUTANTS = {
    "mut_zero": ("else bytes(PAYLOAD)", "else None"),
    "mut_carry": ("carry = (0, 0) if fields is None else", "carry = carry if fields is None else"),
    "mut_stepped": ("            stored = 0 if fields is None else fields[0]\n",
                    "            if fields is None:\n                ticks.append(0)\n                continue\n            stored = fields[0]\n"),
    "mut_index": ("            if fields is None:\n                entries.append(None)",
                  "            if fields is None or fields[1] >= len(table):\n                entries.append(None)"),
}
out = Path(sys.argv[2])
for name, (old, new) in MUTANTS.items():
    assert src.count(old) == 1, name
    (out / (name + ".py")).write_text(src.replace(old, new))
    print("wrote", name)
