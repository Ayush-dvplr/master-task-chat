"""Write prototype books: python3 -B proto_gen.py OUTROOT NAME SEED K N ROWS [SMALL].

K large rounds of N proposals on ROWS-row lattices from the shipped generator family
(bookgen.make_book, pdiag 0.7), plus SMALL small rounds (default 40). Registers scale with K.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bookgen  # noqa: E402


def main(argv):
    root, name, seed, k, n, rows = argv[1], argv[2], int(argv[3]), int(argv[4]), int(argv[5]), int(argv[6])
    small = int(argv[7]) if len(argv) > 7 else 40
    spec = {"audit_large": 60, "audit_small": 12, "blank_row": 50, "crews": 700 + 60 * k,
            "faults": 12, "large": [(n, rows)] * k, "order": "shuffle", "permits": 600 + 80 * k,
            "sites": 500 + 60 * k, "small": small, "ties": 8}
    files, meta = bookgen.make_book(seed, spec)
    out = os.path.join(root, name)
    os.makedirs(out, exist_ok=True)
    for fname, text in files.items():
        with open(os.path.join(out, fname), "w") as fh:
            fh.write(text)
    with open(os.path.join(root, name + ".meta.json"), "w") as fh:
        json.dump({"seed": seed, "k": k, "n": n, "rows": rows, "small": small,
                   "edges": [x["edges"] for x in meta["large"]]}, fh)
    print(name, "rounds", k + small, "large", k, "edges_mean",
          sum(x["edges"] for x in meta["large"]) / max(1, k))


if __name__ == "__main__":
    main(sys.argv)
