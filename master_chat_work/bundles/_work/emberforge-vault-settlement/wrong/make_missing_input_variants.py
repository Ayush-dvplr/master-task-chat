"""Build the two missing-input variants of solve.py used to prove program_names_missing_input.

usage: python3 make_missing_input_variants.py <solve.py> <out_dir>

mi_generic.py    exits 1 with a message that does not name the missing file.
mi_traceback.py  crashes with a bare traceback (RuntimeError) that does not name it.
"""
import sys
from pathlib import Path

CHECK = '            print("settle_vault: missing input file %s" % (data_dir / name), file=sys.stderr)\n            return 1\n'
VARIANTS = {
    "mi_generic.py": '            print("settle_vault: an input file is missing", file=sys.stderr)\n            return 1\n',
    "mi_traceback.py": '            raise RuntimeError("input missing")\n',
}

source = Path(sys.argv[1]).read_text()
assert source.count(CHECK) == 1, "missing-input check not found exactly once"
out = Path(sys.argv[2])
for name, replacement in VARIANTS.items():
    (out / name).write_text(source.replace(CHECK, replacement))
    print("wrote", out / name)
