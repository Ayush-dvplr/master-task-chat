"""Count, per branch variant, how many output documents differ from the reference.

usage: branch_fire.py <shipped_dir> <hidden_root>...
A branch "fires" on an extract when the variant that drops that branch writes at
least one document different from the reference.
"""
import os
import sys

import solve_proto as C
from gen_proto import VAR

DOCS = None


def run(inp, spec):
    D = C.parse(inp)
    out, _ = C.engine(D, C.variant(spec))
    return {k: C.dumps(v) for k, v in out.items()}


def count(inp):
    ref = run(inp, "")
    res = {}
    for name, spec in VAR.items():
        alt = run(inp, spec)
        res[name] = sum(1 for k in ref if ref[k] != alt.get(k))
    return res


def main():
    ship, roots = sys.argv[1], sys.argv[2:]
    r = count(ship)
    print("SHIPPED", " ".join(f"{k}={v}" for k, v in sorted(r.items())))
    for root in roots:
        for d in sorted(os.listdir(root)):
            r = count(os.path.join(root, d))
            fired = [k for k, v in sorted(r.items()) if v]
            print(os.path.basename(root), d, " ".join(f"{k}={r[k]}" for k in fired))
    print("ALL_DONE")


if __name__ == "__main__":
    main()
