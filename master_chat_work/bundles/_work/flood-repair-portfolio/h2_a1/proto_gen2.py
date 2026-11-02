"""Write prototype hidden books: python3 -B proto_gen2.py OUTROOT NAME SEED BASE REPEAT.

BASE is H1, H2 or H3 (current hidden large-round list from tests/test_output.py _BOOKS); the large list is
repeated REPEAT times. Same generator family (bookgen.make_book), registers scale with the large-round count.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bookgen  # noqa: E402

BASE = {"H1": [(156, 13), (160, 14)], "H2": [(148, 12), (160, 13)], "H3": [(152, 14), (144, 12)]}


def main(argv):
    root, name, seed, base, rep = argv[1], argv[2], int(argv[3]), argv[4], int(argv[5])
    large = BASE[base] * rep
    k = len(large)
    spec = {"audit_large": 60, "audit_small": 12, "blank_row": 50, "crews": 700 + 60 * k,
            "faults": 12, "large": large, "order": "shuffle", "permits": 600 + 80 * k,
            "sites": 500 + 60 * k, "small": 40, "ties": 8}
    files, meta = bookgen.make_book(seed, spec)
    out = os.path.join(root, name)
    os.makedirs(out, exist_ok=True)
    for fname, text in files.items():
        with open(os.path.join(out, fname), "w") as fh:
            fh.write(text)
    print(name, "rounds", k + 40, "large", k, "edges_mean",
          round(sum(x["edges"] for x in meta["large"]) / k, 1), flush=True)


if __name__ == "__main__":
    main(sys.argv)
