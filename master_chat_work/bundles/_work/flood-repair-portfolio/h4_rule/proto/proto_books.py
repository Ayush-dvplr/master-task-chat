"""Write prototype capped books: python3 -B proto_books.py TEST_OUTPUT OUTROOT K_H K_M.

For H1, H2, H3 and M of tests/test_output.py _BOOKS: confirm bookgen.make_book reproduces the shipped sha256
(capped=0), then write make_book2(seed, spec + capped=K) to OUTROOT/<name>c with meta.json beside it.
"""
import ast
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import capgen  # noqa: E402
import bookgen  # noqa: E402


def books(path):
    text = open(path, encoding="utf-8").read()
    start = text.index("_BOOKS: dict[str, dict[str, Any]] = ") + len("_BOOKS: dict[str, dict[str, Any]] = ")
    end = text.index("\n\n", start)
    return ast.literal_eval(text[start:end])


def main(argv):
    table, root, kh, km = books(argv[1]), argv[2], int(argv[3]), int(argv[4])
    for name in ("H1", "H2", "H3", "M"):
        e = table[name]
        files, _ = bookgen.make_book(e["seed"], e["spec"])
        digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        assert digest == e["sha256"], (name, "bookgen differs from embedded generator")
        spec = dict(e["spec"], capped=kh if name != "M" else km)
        files, meta = capgen.make_book2(e["seed"], spec)
        out = os.path.join(root, name + "c")
        os.makedirs(out, exist_ok=True)
        for k, v in files.items():
            with open(os.path.join(out, k), "w") as fh:
                fh.write(v)
        with open(os.path.join(root, name + "c.meta.json"), "w") as fh:
            json.dump({"capped": meta["capped"], "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}, fh, indent=1)
        print(name + "c", "rounds", len({ln.split(",")[0] for ln in files["proposals.csv"].splitlines()[1:] if ln}),
              "capped", sorted(meta["capped"]), flush=True)


if __name__ == "__main__":
    main(sys.argv)
