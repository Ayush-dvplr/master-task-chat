"""Write the shipped sample and hidden prototype corpora.
Usage: gen_proto.py outroot shipped_seed "h_seed:empty ..."   e.g. gen_proto.py /tmp/c 1 "3:1:F1+F3 5:1 2:0:F2"
Shipped: n=5 per base. Hidden: n=8 per base; empty=1 adds one base with no eligible request and an empty segment."""
import json
import os
import sys

from absgen import make
from render import render


def one(mode, seed, n, empty, out, traps=()):
    inst = make(mode, seed, n, empty)
    inst["meta"]["traps"] = list(traps)
    render(inst, os.path.join(out, "data"), seed, traps)
    with open(os.path.join(out, "abstract.json"), "w") as f:
        json.dump(inst, f)


if __name__ == "__main__":
    root, ship = sys.argv[1], int(sys.argv[2])
    one("shipped", ship, 5, False, os.path.join(root, "shipped"))
    for k, tok in enumerate(sys.argv[3].split(), start=1):
        s, e, *t = tok.split(":")
        one("hidden", int(s), 8, e == "1", os.path.join(root, "h%d" % k), t[0].split("+") if t else ())
    print("ALL_DONE")
